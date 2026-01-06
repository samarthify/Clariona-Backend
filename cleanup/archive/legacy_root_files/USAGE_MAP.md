# Clariona Backend - Main Operational Flow Usage Map

This document traces the actual execution flow from `run_cycles.sh` to identify what code is actively used vs legacy code.

## 🔄 Main Execution Flow

### Entry Point: `run_cycles.sh`
- **Script**: `run_cycles.sh`
- **Calls**: `POST /agent/test-cycle-no-auth?test_user_id={USER_ID}` via curl
- **Monitors**: `logs/automatic_scheduling.log` for cycle completion

### API Endpoint: `/agent/test-cycle-no-auth`
- **File**: `src/api/service.py` (lines 1334-1385)
- **Calls**: 
  - `agent.run_single_cycle_parallel(user_id)` (if parallel_enabled)
  - `agent._run_automatic_collection(user_id)` (fallback)

---

## ✅ ACTIVELY USED CODE (Main Flow)

### Core Agent Module
**File**: `src/agent/core.py`

#### Key Methods Used:
1. **`run_single_cycle_parallel(user_id)`** (line 1848)
   - Main entry point for parallel cycles
   - Orchestrates all phases

2. **`_run_automatic_collection(user_id)`** (line 607)
   - Wrapper that calls `run_single_cycle_parallel` or `run_single_cycle`
   - Logs cycle start/end to `logs/automatic_scheduling.log`

3. **`collect_data_parallel(user_id)`** (line 832)
   - Collects data from multiple sources in parallel
   - Calls `_get_enabled_collectors_for_target()` → uses `TargetConfigManager`
   - Calls `_run_collectors_parallel()` → executes collectors via subprocess

4. **`_push_raw_data_to_db(user_id)`** (line 2411)
   - Loads CSV files from `data/raw/`
   - Converts to records and stores in `self._temp_raw_records`

5. **`_run_deduplication(user_id)`** (line 2488)
   - Uses `DeduplicationService` to deduplicate records
   - Inserts unique records into database

6. **`_run_sentiment_batch_update_parallel(user_id)`** (line 2643)
   - Processes sentiment analysis in parallel batches
   - Uses `PresidentialSentimentAnalyzer` (via `self.sentiment_analyzer`)

7. **`_run_location_batch_update_parallel(user_id)`** (line 2850)
   - Processes location classification in parallel batches
   - Uses `self.location_classifier` (initialized in `_init_location_classifier`)

#### Helper Methods Used:
- `_get_enabled_collectors_for_target()` (line 911) → Uses `TargetConfigManager`
- `_run_collectors_parallel()` (line 945) → Executes collectors
- `_process_sentiment_batches_parallel()` (line 2712)
- `_process_location_batches_parallel()` (line 2923)
- `_get_latest_target_config()` - Gets target config from DB
- `_init_location_classifier()` (line 2141) - Initializes location classifier

---

### Collectors Module
**Directory**: `src/collectors/`

#### Used Collectors (called via subprocess):
- **`collect_twitter_apify.py`** - Twitter data collection
- **`collect_facebook_apify.py`** - Facebook data collection
- **`collect_instagram_apify.py`** - Instagram data collection
- **`collect_tiktok_apify.py`** - TikTok data collection
- **`collect_news_apify.py`** - News data collection (Apify)
- **`collect_news_from_api.py`** - News data collection (API)
- **`collect_youtube_api.py`** - YouTube data collection
- **`collect_radio_hybrid.py`** - Radio data collection
- **`collect_rss_nigerian_qatar_indian.py`** - RSS feeds
- **`collect_rss.py`** - General RSS feeds
- **`collect_social_searcher_api.py`** - Social Searcher API

#### Collector Infrastructure:
- **`run_collectors.py`** - Used by collectors (called as module)
- **`configurable_collector.py`** - Used by `run_collectors.py`
- **`target_config_manager.py`** - Used by agent to get enabled collectors
- **`target_helper.py`** - Likely used by collectors
- **`incremental_collector.py`** - Likely used for incremental collection

---

### Processing Module
**Directory**: `src/processing/`

#### Used Processors:
- **`presidential_sentiment_analyzer.py`** - Main sentiment analyzer (imported in core.py line 37, used as `self.sentiment_analyzer`)
- **`data_processor.py`** - **ACTIVE** (imported line 38, initialized line 261, used in `_process_sentiment_batches_parallel` line 2747-2751 for batch sentiment + governance analysis)
- **`governance_analyzer.py`** - Used by `data_processor` (two-phase analysis: sentiment + governance)

#### Processing Infrastructure:
- **`record_router.py`** - Possibly used for routing (not confirmed in main flow)
- **`sentiment_analyzer.py`** - Not directly imported/used (presidential_sentiment_analyzer used instead)

---

### Utils Module
**Directory**: `src/utils/`

#### Used Utilities:
- **`deduplication_service.py`** - **ACTIVE** (used in `_run_deduplication`)
- **`collection_tracker.py`** - **ACTIVE** (used for incremental date ranges in `_run_collectors_parallel`)
- **`notification_service.py`** - **PARTIALLY USED** (imported lines 33-34, `send_processing_notification` called in old code around line 1668, but unclear if that code path is executed)

---

### API Module
**Directory**: `src/api/`

#### Used Files:
- **`service.py`** - Main FastAPI app, endpoint handlers
- **`database.py`** - Database session factory
- **`models.py`** - Database models (SentimentData, User, TargetIndividualConfiguration, etc.)
- **`auth.py`** - Authentication (used by some endpoints)

---

### Config Files
**Directory**: `config/`

#### Used Config:
- **`agent_config.json`** - Agent configuration
- **`target_configs.json`** - Target configurations (used by TargetConfigManager)
- **`llm_config.json`** - LLM configuration

---

## ⚠️ POTENTIALLY LEGACY / UNUSED CODE

### Agent Module Legacy Code:
- **`run()` method** (line 2136) - **DEPRECATED** - Just logs warning, does nothing
- **`collect_data()` method** - Old sequential collection (not used in parallel flow)
- **`process_data()` method** - Old processing method (replaced by parallel batch methods)
- **`optimize_system()` method** (line 2003) - Uses AutogenAgentSystem, but unclear if called
- **`update_metrics()` method** (line 1962) - Old metrics updating, unclear usage
- **`cleanup_old_data()` method** (line 2096) - Old data cleanup, unclear usage
- **`_run_collect_and_process()` method** (line 1954) - Legacy wrapper

### Unused Collectors:
- All files in `src/collectors/unused/` directory - **ALREADY DELETED** ✅

### Processing Module:
- **`issue_classifier.py`** - Possibly unused (not imported in core.py)
- **`governance_categories.py`** - Possibly unused
- **`presidential_data_processor.py`** - Possibly legacy (different from presidential_sentiment_analyzer)

### Utils Module:
- **`mail_sender.py`** - Mail sending (imported but usage unclear)
- **`mail_config.py`** - Mail config (imported but usage unclear)
- **`scheduled_reports.py`** - Reports (imported but usage unclear)
- **`file_rotation.py`** - File rotation (imported but usage unclear)
- **`multi_model_rate_limiter.py`** - Rate limiting (unclear usage)
- **`openai_rate_limiter.py`** - Rate limiting (unclear usage)
- **`sentiment_change_example.py`** - Example file
- **`notification_example.py`** - Example file

### API Module:
- **`admin.py`** - Admin routes (included but may not be used)
- **`presidential_service.py`** - Presidential endpoints (included but may not be used)
- **`data_cache.py`** - Data caching (may be used by API endpoints)

### Agent Infrastructure:
- **`brain.py`** - AgentBrain (imported line 34, **NEVER INITIALIZED/USED** ❌)
- **`autogen_agents.py`** - AutogenAgentSystem (imported line 35, used in `optimize_system()` but that method is **NOT CALLED** in main flow ❌)

### Scripts:
- **`run_cycles.sh.improved`** - Enhanced version, but `run_cycles.sh` is what's used
- **`deploy-ec2.sh`** - Deployment script (used for deployment, not runtime)
- **`troubleshoot.sh`** - Troubleshooting script (utility, not runtime)
- All files in `scripts/` directory - Utility scripts, not part of main flow

### Tests:
- All files in `tests/` directory - Test files, not runtime

---

## 📊 Summary

### Active Flow:
1. `run_cycles.sh` → API endpoint → `run_single_cycle_parallel()` 
2. Phase 1: Collection (parallel collectors via subprocess)
3. Phase 2: Load raw data to DB
4. Phase 3: Deduplication
5. Phase 4: Sentiment analysis (parallel batches)
6. Phase 5: Location classification (parallel batches)

### Key Dependencies:
- **Collectors**: Run as subprocess modules via `python -m src.collectors.{collector_name}`
- **TargetConfigManager**: Determines which collectors are enabled
- **DeduplicationService**: Removes duplicates
- **PresidentialSentimentAnalyzer**: Performs sentiment analysis
- **Location Classifier**: Simple classifier (defined in core.py)

### Legacy Code Indicators:
- Methods marked as "DEPRECATED" in docstrings
- Old sequential processing methods not called in parallel flow
- Example/test files
- Unused imports or modules not referenced in main flow

