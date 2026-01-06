# Execution Flow Map

**Created**: 2025-12-27  
**Purpose**: Complete call tree mapping of the main execution flow from entry point to database writes  
**Status**: Phase 1, Step 1.1 - In Progress

---

## 📋 Overview

This document traces every function call in the main execution path from `run_cycles.sh` through the complete data pipeline to database writes. This is used to identify which code is actually used vs unused.

---

## 🔄 Complete Execution Flow

### Entry Point: `run_cycles.sh`

**File**: `run_cycles.sh` (root directory)  
**Lines**: 72-73

```bash
curl -s -X POST "http://localhost:8000/agent/test-cycle-no-auth?test_user_id=$USER_ID"
```

**What it does**:
- Makes HTTP POST request to backend API
- Passes `user_id` as query parameter
- Monitors `logs/automatic_scheduling.log` for completion

---

### API Endpoint: `/agent/test-cycle-no-auth`

**File**: `src/api/service.py`  
**Lines**: ~1334-1385 (needs verification)

**Function Signature**:
```python
@app.post("/agent/test-cycle-no-auth")
async def test_cycle_no_auth(
    test_user_id: str = Query(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
)
```

**Call Chain**:
1. Extracts `test_user_id` from query params
2. Calls `agent.run_single_cycle_parallel(test_user_id)`
3. Returns immediately (async execution)
4. Logs to `logs/automatic_scheduling.log`

---

### Core Agent: `run_single_cycle_parallel()`

**File**: `src/agent/core.py`  
**Lines**: 1962-2073  
**Class**: `SentimentAnalysisAgent`  
**Method**: `run_single_cycle_parallel(user_id: str)`

**Complete Call Tree**:

```
run_single_cycle_parallel(user_id)
│
├─> Phase 1: Data Collection
│   └─> _run_task(lambda: self.collect_data_parallel(user_id), 'collect_user_{user_id}')
│       │
│       └─> collect_data_parallel(user_id) [line 829]
│           │
│           ├─> db_factory() → creates DB session
│           │
│           ├─> _get_latest_target_config(db, user_id) [line ~789]
│           │   └─> Query TargetIndividualConfiguration table
│           │
│           ├─> _get_enabled_collectors_for_target(target_name) [line 908]
│           │   │
│           │   ├─> TargetConfigManager() [from src.collectors.target_config_manager]
│           │   │   └─> _load_config() [loads config/target_configs.json]
│           │   │
│           │   ├─> config_manager.get_target_by_name(target_name)
│           │   │
│           │   └─> config_manager.get_enabled_collectors(target_id)
│           │
│           └─> _run_collectors_parallel(enabled_collectors, queries_json, user_id) [line 942]
│               │
│               ├─> get_collection_tracker() [from src.utils.collection_tracker]
│               │   └─> CollectionTracker instance
│               │
│               ├─> For each collector:
│               │   ├─> tracker.get_incremental_date_range(user_id, source_type)
│               │   │   └─> Query database for last collection date
│               │   │
│               │   └─> subprocess.run([
│               │       "python", "-m", f"src.collectors.{collector_name}",
│               │       queries_json, user_id
│               │   ])
│               │   └─> Collector executes (separate process)
│               │       └─> Writes CSV to data/raw/{collector_name}_{timestamp}.csv
│               │
│               └─> ThreadPoolExecutor manages parallel execution
│
├─> Phase 2: Load Raw Data
│   └─> _run_task(lambda: self._push_raw_data_to_db(user_id), 'load_raw_{user_id}')
│       │
│       └─> _push_raw_data_to_db(user_id) [line ~2300-2422]
│           │
│           ├─> glob.glob(str(self.base_path / 'data' / 'raw' / '*.csv'))
│           │   └─> Finds all CSV files in data/raw/
│           │
│           ├─> For each CSV file:
│           │   ├─> pd.read_csv(file_path)
│           │   └─> Convert DataFrame rows to dictionaries
│           │
│           └─> Store in self._temp_raw_records (list of dicts)
│
├─> Phase 3: Deduplication
│   └─> _run_task(lambda: self._run_deduplication(user_id), 'dedup_{user_id}')
│       │
│       └─> _run_deduplication(user_id) [line 2423]
│           │
│           ├─> db_factory() → creates DB session
│           │
│           ├─> self.deduplication_service.deduplicate_new_data(
│           │       self._temp_raw_records, db, user_id
│           │   ) [src/utils/deduplication_service.py]
│           │   │
│           │   ├─> find_existing_duplicates(new_records, db, user_id)
│           │   │   ├─> Query SentimentData table for existing records
│           │   │   ├─> normalize_text() for each record
│           │   │   └─> is_similar_text() comparison
│           │   │
│           │   └─> Returns: {
│           │       'unique_records': [...],
│           │       'duplicates': [...],
│           │       'stats': {...}
│           │   }
│           │
│           ├─> deduplication_service.get_deduplication_summary(results)
│           │
│           └─> Bulk insert unique records to database:
│               ├─> For each record in unique_records:
│               │   ├─> _parse_date_string() - Parse date fields
│               │   ├─> _validate_and_clean_location() - Clean location data
│               │   └─> Create SentimentData object
│               │
│               └─> db.bulk_insert_mappings(SentimentData, bulk_data)
│               └─> db.commit()
│
├─> Phase 4: Sentiment & Governance Analysis
│   └─> _run_task(lambda: self._run_sentiment_batch_update_parallel(user_id), 'sentiment_batch_{user_id}')
│       │
│       └─> _run_sentiment_batch_update_parallel(user_id) [line ~2575-2650]
│           │
│           ├─> db_factory() → creates DB session
│           │
│           ├─> Query SentimentData:
│           │   WHERE sentiment_label IS NULL
│           │   AND user_id = user_id
│           │   LIMIT 10000
│           │
│           ├─> Create batches (size = self.sentiment_batch_size, default 150)
│           │
│           └─> _process_sentiment_batches_parallel(batches, user_id) [line 2652]
│               │
│               └─> ThreadPoolExecutor processes batches in parallel
│                   │
│                   └─> For each batch (process_single_batch):
│                       │
│                       ├─> db_factory() → creates DB session for thread
│                       │
│                       ├─> For each record:
│                       │   └─> db.merge(record) - Merge into thread's session
│                       │
│                       ├─> Extract texts from records
│                       │
│                       ├─> self.data_processor.batch_get_sentiment(
│                       │       texts_list, source_types_list, max_workers
│                       │   ) [src/processing/data_processor.py]
│                       │   │
│                       │   ├─> RecordRouter.route_records(texts, source_types)
│                       │   │   └─> Distributes records across model pipelines
│                       │   │
│                       │   ├─> For each model pipeline (parallel):
│                       │   │   ├─> presidential_sentiment_analyzer.analyze(text)
│                       │   │   │   └─> [src/processing/presidential_sentiment_analyzer.py]
│                       │   │   │       ├─> OpenAI API call for sentiment
│                       │   │   │       └─> Returns: sentiment_label, sentiment_score, 
│                       │   │   │                    sentiment_justification, embedding
│                       │   │   │
│                       │   │   └─> governance_analyzer.analyze(text, source_type, sentiment)
│                       │   │       └─> [src/processing/governance_analyzer.py]
│                       │   │           ├─> OpenAI API call for ministry classification
│                       │   │           ├─> OpenAI API call for issue classification
│                       │   │           └─> Returns: ministry_hint, issue_slug, 
│                       │   │                        issue_label, issue_confidence, 
│                       │   │                        issue_keywords
│                       │   │
│                       │   └─> Combine results from all pipelines
│                       │
│                       ├─> For each record + analysis_result:
│                       │   ├─> Update record fields:
│                       │   │   ├─> sentiment_label
│                       │   │   ├─> sentiment_score
│                       │   │   ├─> sentiment_justification
│                       │   │   ├─> ministry_hint
│                       │   │   ├─> issue_slug
│                       │   │   ├─> issue_label
│                       │   │   ├─> issue_confidence
│                       │   │   └─> issue_keywords (JSON)
│                       │   │
│                       │   └─> Store embedding:
│                       │       ├─> Check SentimentEmbedding table for existing
│                       │       ├─> Create/Update SentimentEmbedding record
│                       │       └─> embedding = json.dumps(embedding_data)
│                       │
│                       ├─> db.commit() - Commit all updates
│                       │
│                       └─> Return processed count
│
└─> Phase 5: Location Classification
    └─> _run_task(lambda: self._run_location_batch_update_parallel(user_id), 'location_batch_{user_id}')
        │
        └─> _run_location_batch_update_parallel(user_id) [line ~2780-2850]
            │
            ├─> db_factory() → creates DB session
            │
            ├─> Query SentimentData:
            │   WHERE location_label IS NULL
            │   AND user_id = user_id
            │   LIMIT 10000
            │
            ├─> Create batches (size = self.location_batch_size, default 300)
            │
            └─> _process_location_batches_parallel(batches, user_id) [line ~2923]
                │
                └─> ThreadPoolExecutor processes batches in parallel
                    │
                    └─> For each batch:
                        │
                        ├─> db_factory() → creates DB session for thread
                        │
                        ├─> For each record:
                        │   ├─> Extract text content
                        │   ├─> Simple location classifier (keyword matching)
                        │   │   └─> _classify_location() [defined in core.py]
                        │   │       └─> Keyword matching against location keywords
                        │   │
                        │   └─> Update record:
                        │       ├─> location_label
                        │       └─> location_confidence
                        │
                        ├─> db.commit()
                        │
                        └─> Return processed count
```

---

## 🔍 Helper Functions Called

### Task Management

**`_run_task(task_func: Callable, task_name: str)`** [line 1880]
- Handles task execution, locking, error handling
- Calls `_check_and_release_stuck_lock()` if needed
- Updates `self.task_status`
- Logs task execution

**`_check_and_release_stuck_lock(task_name: str)`** [line ~1713]
- Checks if lock is stuck (exceeded max age)
- Releases lock if stuck
- Logs stuck lock release

### Database & Configuration

**`_get_latest_target_config(db: Session, user_id: str)`** [line ~789]
- Queries `TargetIndividualConfiguration` table
- Returns latest config for user

**`_parse_date_string(date_str)`** [used in deduplication]
- Parses various date formats
- Returns datetime or None

**`_validate_and_clean_location(location)`** [line ~680]
- Validates and cleans location strings
- Returns cleaned location or None

### Location Classification

**`_classify_location(text: str)`** [defined in core.py, ~line 2141]
- Simple keyword-based location classifier
- Returns location_label and confidence

---

## 📦 External Dependencies

### Modules Imported and Used

1. **`src.collectors.target_config_manager`**
   - `TargetConfigManager` class
   - Used in `_get_enabled_collectors_for_target()`

2. **`src.utils.collection_tracker`**
   - `get_collection_tracker()` function
   - `CollectionTracker` class
   - Used in `_run_collectors_parallel()`

3. **`src.utils.deduplication_service`**
   - `DeduplicationService` class
   - Used in `_run_deduplication()`

4. **`src.processing.data_processor`**
   - `DataProcessor` class
   - Used in `_process_sentiment_batches_parallel()`

5. **`src.processing.presidential_sentiment_analyzer`**
   - `PresidentialSentimentAnalyzer` class
   - Used by `DataProcessor.batch_get_sentiment()`

6. **`src.processing.governance_analyzer`**
   - `GovernanceAnalyzer` class
   - Used by `DataProcessor.batch_get_sentiment()`

7. **`src.processing.record_router`**
   - `RecordRouter` class (likely)
   - Used by `DataProcessor.batch_get_sentiment()`

8. **`src.api.models`**
   - `SentimentData` model
   - `SentimentEmbedding` model
   - `TargetIndividualConfiguration` model
   - Used throughout for database operations

9. **`src.api.database`**
   - `SessionLocal` (db_factory)
   - Used for all database operations

---

## 🗄️ Database Operations

### Tables Accessed

1. **`target_individual_configurations`**
   - READ: `_get_latest_target_config()`

2. **`sentiment_data`**
   - READ: Deduplication queries, sentiment/location batch queries
   - WRITE: Bulk insert in deduplication, UPDATE in sentiment/location analysis

3. **`sentiment_embeddings`**
   - READ: Check for existing embeddings
   - WRITE: Insert/update embeddings

4. **`collection_tracker`** (if table exists)
   - READ: Get last collection dates
   - WRITE: Update collection dates

---

## 📁 File System Operations

### Files Read

1. **`config/target_configs.json`**
   - Read by `TargetConfigManager._load_config()`

2. **`data/raw/*.csv`**
   - Read by `_push_raw_data_to_db()`
   - Glob pattern: `data/raw/*.csv`

### Files Written

1. **`data/raw/{collector_name}_{timestamp}.csv`**
   - Written by individual collectors (separate processes)

2. **`logs/automatic_scheduling.log`**
   - Written by auto_schedule_logger throughout execution

3. **`logs/collectors/{collector_name}/{collector_name}_{timestamp}.log`**
   - Written by collectors (separate processes)

4. **`logs/agent.log`**
   - Written by logger throughout execution

---

## 🔄 Subprocess Calls

### Collector Execution

Each collector runs as a separate Python process:

```python
subprocess.run([
    sys.executable, "-m", f"src.collectors.{collector_name}",
    queries_json, user_id
])
```

**Collectors executed**:
- `collect_twitter_apify`
- `collect_facebook_apify`
- `collect_instagram_apify`
- `collect_tiktok_apify`
- `collect_news_apify`
- `collect_news_from_api`
- `collect_youtube_api`
- `collect_radio_hybrid`
- `collect_rss_nigerian_qatar_indian`
- `collect_rss`
- `collect_social_searcher_api`

Each collector:
1. Imports `run_collectors.py`
2. Calls `run_configurable_collector(target_and_variations, user_id)`
3. Writes CSV to `data/raw/`

---

## 📊 Summary Statistics

### Execution Phases
- **5 phases** total
- **3 parallel processing phases** (collection, sentiment, location)
- **2 sequential phases** (data loading, deduplication)

### Database Queries
- **~5-10 queries per cycle** (excluding batch operations)
- **1 bulk insert** for unique records
- **Multiple UPDATE queries** in batches

### External API Calls
- **OpenAI API**: Called by `PresidentialSentimentAnalyzer` and `GovernanceAnalyzer`
- **Collector APIs**: Called by individual collectors (Apify, YouTube, etc.)

### File I/O
- **Read**: Config files, CSV files, log files
- **Write**: CSV files, log files

---

## 🔍 Notes

1. **Parallel Processing**: 
   - Collection: ThreadPoolExecutor with configurable workers
   - Sentiment: ThreadPoolExecutor with configurable workers
   - Location: ThreadPoolExecutor with configurable workers

2. **Database Sessions**:
   - New session created for each phase
   - Separate sessions for each thread in parallel processing
   - Sessions properly closed after use

3. **Error Handling**:
   - Each phase wrapped in try/except
   - Errors logged but don't stop entire cycle
   - Failed phases reported in logs

4. **Locking**:
   - `_run_task()` uses lock to prevent concurrent cycles
   - Lock stored in `self.task_status`
   - Stuck locks automatically released after timeout

---

## ✅ Verification Checklist

- [x] Entry point identified (`run_cycles.sh`)
- [x] API endpoint identified (`/agent/test-cycle-no-auth`)
- [x] Main method identified (`run_single_cycle_parallel`)
- [x] All 5 phases mapped
- [x] Helper functions identified
- [x] External dependencies listed
- [x] Database operations documented
- [x] File I/O operations documented
- [ ] Line numbers verified (need to check exact line numbers)
- [ ] Subprocess calls verified (need to check exact implementation)

---

## 📝 Next Steps

1. Verify exact line numbers for all functions
2. Add call depth/level indicators
3. Document parameter types and return values
4. Add timing information (if available)
5. Cross-reference with UNUSED_CODE_ANALYSIS.md

---

**Last Updated**: 2025-12-27  
**Status**: Initial draft - needs line number verification and refinement













