# Clariona Backend - Architecture Documentation

**Version**: 2.5 (Week 6: Testing & Optimization)  
**Last Updated**: 2024-12-19

**Status**: ✅ All 6 weeks of the master plan are complete. The system is production-ready.

## ⚠️ CRITICAL: Backend Purpose & Scope

**This backend system is EXCLUSIVELY a data collection, processing, and storage pipeline.**

### Key Points:
- ✅ **Data Collection**: Collects data from multiple sources (Twitter, Facebook, News, RSS, YouTube, etc.)
- ✅ **Data Processing**: Analyzes and classifies collected data (sentiment, topics, locations, issues)
- ✅ **Data Storage**: Writes processed data directly to PostgreSQL database
- ❌ **NO Frontend**: This backend has ZERO frontend code, UI, or user-facing components
- ❌ **NO Frontend APIs**: Frontend applications read DIRECTLY from the database (via Prisma)
- ✅ **Database-Only**: All output goes to PostgreSQL database tables

### Architecture Separation:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLARIONA BACKEND                        │
│         (Data Collection, Processing & Storage)             │
│                                                             │
│  Collectors → Processing → Database (PostgreSQL)           │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Writes to
                            ▼
                  ┌─────────────────────┐
                  │   PostgreSQL DB      │
                  │  (sentiment_data,    │
                  │   topics, users, etc)│
                  └─────────────────────┘
                            │
                            │ Reads from
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND (Separate Repo)                   │
│         (Next.js, Prisma, User Interface)                   │
│                                                             │
│  Frontend connects DIRECTLY to database via Prisma         │
│  Frontend does NOT communicate with this backend           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Complete System Architecture

### High-Level Pipeline Flow

### High-Level Pipeline Flow (Streaming)

```
1. STREAMING INPUT (src.services.main)
   │
   ├─> SERVICE 1: DATASET TAILER (DatasetTailerService)
   │   └─> Continuously streams new records from Apify (Twitter/Facebook/News)
   │   └─> Inserts raw data -> Deduplication -> DB (sentiment_data)
   │
   ├─> SERVICE 2: LOCAL SCHEDULER (LocalScheduler)
   │   └─> Periodically triggers RSS/YouTube/Radio collectors
   │   └─> Inserts raw data -> Deduplication -> DB (sentiment_data)
   │
   └─> SERVICE 3: ANALYSIS WORKER (Polling Engine)
       │
       ├─> POLLS Database (every 2s)
       │   └─> SELECT * FROM sentiment_data WHERE sentiment_label IS NULL
       │
       ├─> PARALLEL ANALYSIS (10 Workers)
       │   ├─> Sentiment & Emotion (PresidentialSentimentAnalyzer)
       │   ├─> Topic Classification (TopicClassifier)
       │   ├─> Issue Detection (IssueDetectionEngine)
       │   └─> Location Classification (SimpleLocationClassifier)
       │
       └─> UPDATE Database
           └─> Updates records with analysis results (sentiment, topics, issues)
```

---

## 🔄 Detailed Pipeline Execution

### Entry Point: `run_cycles.sh`

**Location**: `run_cycles.sh` (root directory)

**Purpose**: Automated script that triggers agent cycles at regular intervals

**How it works**:
1. Makes HTTP POST request to backend API: `POST /agent/test-cycle-no-auth?test_user_id={USER_ID}`
2. Monitors `logs/automatic_scheduling.log` for cycle completion
3. Waits for specified interval (default: 30 minutes)
4. Repeats indefinitely

**Configuration**:
- `USER_ID`: Target user ID for collection cycles
- `INTERVAL_MINUTES`: Wait time between cycles (default: 30)
- `BACKEND_URL`: Backend API URL (default: http://localhost:8000)

---

### API Endpoint: `/agent/test-cycle-no-auth`

**Location**: `src/api/service.py` (lines 1334-1385)

**Purpose**: Receives cycle trigger and starts agent processing

**How it works**:
1. Receives `user_id` from query parameter
2. Calls `agent.run_single_cycle_parallel(user_id)`
3. Returns immediately (processing happens asynchronously)
4. Logs cycle start/end to `logs/automatic_scheduling.log`

---

### Core Agent: `SentimentAnalysisAgent`

**Location**: `src/agent/core.py`

**Purpose**: Orchestrates entire data collection, processing, and storage pipeline

**Main Method**: `run_single_cycle_parallel(user_id: str)`

**Execution Flow**:

#### PHASE 1: Streaming Ingestion (`DatasetTailerService`)

**Purpose**: Continuously stream new data from Apify actors to the backend in real-time.

**Process**:
1. **DatasetTailer**: Connects to Apify Datasets.
2. **Stream**: Polls for *new* items only (incremental update).
3. **Ingest**: Passes raw items to `DataIngestor`.

**Supported Sources**:
- Twitter/X (Apify)
- News Articles (Apify)
- Facebook/Instagram/TikTok (Apify)

**Legacy/Periodic Collectors**:
- RSS Feeds (`LocalScheduler` triggers these)
- YouTube (`LocalScheduler` triggers these)
- Radio (`LocalScheduler` triggers these)

---

#### PHASE 2: Ingestion & Deduplication (`DataIngestor`)

**Purpose**: Standardize, deduplicate, and insert records into the database immediately.

**Process**:
1. **Standardize**: Convert raw source JSON into `SentimentData` model format.
2. **Deduplicate**: Check `original_id` (from source) or URL against database.
   - If exists: Update engagement metrics (likes, retweets) only.
   - If new: Insert full record with `sentiment_label = NULL`.
3. **Insert**: Commit to PostgreSQL `sentiment_data` table.

**Outcome**: Clean, unique record in DB ready for analysis.

---

#### PHASE 3: Real-Time Analysis (`AnalysisWorker`)

**Component**: `src.services.analysis_worker`

**Process**:
1. **Poll**: Every 2 seconds, worker asks DB: "Give me up to 50 records where `sentiment_label` is NULL."
2. **Analyze**: In parallel threads (default 10), run all classifiers:
   *   **Sentiment**: `PresidentialSentimentAnalyzer` (Sentiment + 6 Emotions)
   *   **Topics**: `TopicClassifier` (Multi-label classification)
   *   **Issues**: `IssueDetectionEngine` (Cluster & Detect Issues)
   *   **Location**: `SimpleLocationClassifier` (Geographic mapping)
3. **Commit**: Update record with all analysis results in one transaction.

**Advantages**:
- **Speed**: processing starts within seconds of ingestion.
- **Reliability**: If worker crashes, unanalyzed records remain NULL and are picked up by next restart.

---

#### PHASE 6: Issue Detection & Aggregation

**Purpose**: Detect issues, aggregate sentiment, calculate trends, and normalize baselines

**Week 4: Issue Detection System**
- **Issue Clustering**: Groups similar mentions into clusters using embedding similarity
- **Issue Detection**: Detects new issues from clusters, matches to existing issues
- **Issue Lifecycle**: Manages issue states (emerging, active, escalated, stabilizing, resolved, archived)
- **Issue Priority**: Calculates multi-factor priority scores (sentiment, volume, time, velocity)

**Week 5: Aggregation & Integration**
- **Sentiment Aggregation**: Aggregates sentiment by topic, issue, or entity across time windows
- **Sentiment Trends**: Calculates trends (improving/deteriorating/stable) by comparing periods
- **Topic Sentiment Normalization**: Calculates baseline sentiment per topic and normalizes current sentiment

**Database Updates**:
- Table: `topic_issues` (creates/updates issues) - **Week 4**
- Table: `issue_mentions` (links mentions to issues) - **Week 4**
- Table: `topic_issue_links` (links topics to issues) - **Week 4**
- Table: `sentiment_aggregations` (stores aggregated sentiment) - **Week 5**
- Table: `sentiment_trends` (stores trend calculations) - **Week 5**
- Table: `topic_sentiment_baselines` (stores baseline sentiment) - **Week 5**

**Output**: Issues detected, sentiment aggregated, trends calculated, baselines normalized

---

#### Week 6: Testing & Optimization ✅

**Status**: All 6 weeks of the master plan are complete. The system is production-ready.

**Testing Completed**:
- ✅ Unit tests for all components
- ✅ Integration tests for full pipeline
- ✅ Performance tests (throughput: 0.44 texts/second)
- ✅ Database integration tests
- ✅ Concurrent processing tests
- ✅ Error handling tests
- ✅ Data consistency tests

**Performance Baseline**:
- Single text processing: ~37 seconds (first run, includes model loading)
- Batch processing: ~2.27 seconds per text
- Throughput: 0.44 texts/second
- All tests passing: 9/10 (1 skipped - expected)

**See**: `docs/topic-classification-architecture/PERFORMANCE_OPTIMIZATION_GUIDE.md` and `THROUGHPUT_IMPROVEMENT_GUIDE.md` for optimization strategies.

---

## 🗄️ Database Schema & Tables

### Core Tables

#### 1. `users`
**Purpose**: User accounts (for data collection targeting)

**Key Fields**:
- `id` (UUID, Primary Key)
- `email`, `username`, `password_hash`
- `role` (president, minister, etc.)
- `ministry` (ministry assignment)
- `is_admin` (admin flag)

**Usage**: Links collected data to specific users/targets

---

#### 2. `sentiment_data`
**Purpose**: Main table storing all collected and processed mentions

**Key Fields**:

**Identity**:
- `entry_id` (Integer, Primary Key, Auto-increment)
- `user_id` (UUID, Foreign Key → `users.id`)
- `run_timestamp` (DateTime) - When this record was collected
- `created_at` (DateTime) - Record creation time

**Raw Data** (from collectors):
- `title`, `description`, `content`, `text`
- `url`, `source`, `source_url`, `source_type`, `source_name`
- `published_date`, `published_at`, `date`
- `platform` (twitter, facebook, news, etc.)
- `query` (search query used)
- `language`, `country`
- `original_id` (ID from source platform)

**Social Metrics** (for social media):
- `retweets`, `likes`, `comments`, `direct_reach`, `cumulative_reach`
- `user_name`, `user_handle`, `user_avatar`, `user_location`

**Analysis Results**:
- `sentiment_label` (positive, negative, neutral)
- `sentiment_score` (float, 0-1)
- `sentiment_justification` (text explanation)
- `location_label` (geographic location)
- `location_confidence` (float, 0-1)
- `ministry_hint` (classified ministry)
- `issue_slug`, `issue_label` (classified issue)
- `issue_confidence` (float, 0-1)
- `issue_keywords` (JSON array)

**Indexes**:
- `ix_sentiment_data_run_timestamp` (on `run_timestamp`)
- `ix_sentiment_data_platform` (on `platform`)
- `ix_sentiment_data_user_id` (on `user_id`)

---

#### 3. `sentiment_embeddings`
**Purpose**: Vector embeddings for semantic similarity/search

**Key Fields**:
- `entry_id` (Integer, Primary Key, Foreign Key → `sentiment_data.entry_id`)
- `embedding` (JSON array) - Vector embedding (typically 1536 dimensions)
- `embedding_model` (String) - Model used (default: 'text-embedding-3-small')
- `created_at` (DateTime)

**Usage**: Enables semantic search and similarity matching

---

#### 4. `topics`
**Purpose**: Master topics for topic-based classification

**Key Fields**:
- `topic_key` (String, Primary Key) - Unique topic identifier
- `topic_name` (String) - Display name
- `description` (Text) - Topic description
- `category` (String) - Topic category
- `keywords` (Array[Text]) - Keyword array for matching
- `keyword_groups` (JSONB) - AND/OR keyword logic groups
- `is_active` (Boolean) - Active flag
- `created_at` (DateTime)

**Usage**: Defines available topics for classification

---

#### 5. `topic_issues`
**Purpose**: Dynamic issues per topic (stored in database)

**Key Fields**:
- `id` (UUID, Primary Key)
- `topic_key` (String, Foreign Key → `topics.topic_key`)
- `issue_slug` (String) - Issue identifier
- `issue_label` (String) - Issue display name
- `mention_count` (Integer) - Count of mentions for this issue
- `max_issues` (Integer) - Maximum issues per topic (default: 20)
- `created_at`, `last_updated` (DateTime)

**Constraints**:
- Unique: (`topic_key`, `issue_slug`)

**Usage**: Stores issues that belong to each topic

---

#### 6. `mention_topics`
**Purpose**: Junction table linking mentions to topics (many-to-many)

**Key Fields**:
- `id` (UUID, Primary Key)
- `mention_id` (Integer, Foreign Key → `sentiment_data.entry_id`)
- `topic_key` (String, Foreign Key → `topics.topic_key`)
- `topic_confidence` (Float, 0-1) - Topic match confidence
- `keyword_score` (Float) - Keyword matching score
- `embedding_score` (Float) - Embedding similarity score
- `issue_slug`, `issue_label` - Issue classification within topic (Week 4)
- `issue_confidence` (Float) - Issue match confidence (Week 4)
- `issue_keywords` (JSONB) - Keywords that matched for issue (Week 4)
- `created_at`, `updated_at` (DateTime)

**Week 2 Usage**: Stores multiple topic classifications per mention from `TopicClassifier`

**Constraints**:
- Unique: (`mention_id`, `topic_key`)

**Usage**: Stores topic classifications for each mention (supports multiple topics per mention)

---

#### 7. `owner_configs`
**Purpose**: Configuration for owners (president/ministers) defining which topics they care about

**Key Fields**:
- `owner_key` (String, Primary Key) - Unique owner identifier
- `owner_name` (String) - Owner display name
- `owner_type` (String) - 'president', 'minister', etc.
- `topics` (Array[Text]) - Array of topic_keys this owner cares about
- `priority_topics` (Array[Text]) - High-priority topics
- `is_active` (Boolean)
- `config_data` (JSONB) - Additional configuration
- `created_at`, `updated_at` (DateTime)

**Usage**: Defines topic filters for each owner/user

---

#### 8. `target_individual_configurations`
**Purpose**: Configuration for data collection targets

**Key Fields**:
- `id` (Integer, Primary Key)
- `user_id` (UUID, Foreign Key → `users.id`)
- `individual_name` (String) - Target person/entity name
- `query_variations` (JSON) - Array of search query variations
- `created_at` (DateTime)

**Usage**: Defines what to search for when collecting data

---

#### 9. `email_configurations`
**Purpose**: Email notification configuration

**Key Fields**:
- `id` (Integer, Primary Key)
- `user_id` (UUID, Foreign Key → `users.id`)
- `provider`, `smtp_server`
- `enabled` (Boolean)
- `recipients` (JSON) - Array of email addresses
- `notify_on_collection`, `notify_on_processing`, `notify_on_analysis` (Boolean flags)
- `created_at` (DateTime)

**Usage**: Configures email notifications for collection/processing events

---

#### 10. `user_system_usage`
**Purpose**: API usage tracking and logging

**Key Fields**:
- `id` (Integer, Primary Key)
- `user_id` (UUID, Foreign Key → `users.id`)
- `endpoint` (String) - API endpoint called
- `timestamp` (DateTime)
- `execution_time_ms` (Integer)
- `data_size` (Integer) - Data processed in bytes
- `status_code` (Integer)
- `is_error` (Boolean)
- `error_message` (Text)

**Usage**: Tracks API usage and performance metrics

---

#### 11. `issue_mentions` (Week 4)
**Purpose**: Links individual mentions to detected issues

**Key Fields**:
- `id` (UUID, Primary Key)
- `issue_id` (UUID, Foreign Key → `topic_issues.id`)
- `mention_id` (Integer, Foreign Key → `sentiment_data.entry_id`)
- `cluster_id` (String) - Cluster identifier from clustering
- `similarity_score` (Float) - Similarity to issue
- `detected_at` (DateTime) - When issue was detected
- `created_at` (DateTime)

**Usage**: Tracks which mentions belong to which issues

---

#### 12. `topic_issue_links` (Week 4)
**Purpose**: Links topics to issues (many-to-many)

**Key Fields**:
- `id` (UUID, Primary Key)
- `topic_key` (String, Foreign Key → `topics.topic_key`)
- `issue_id` (UUID, Foreign Key → `topic_issues.id`)
- `is_primary` (Boolean) - Primary topic for this issue
- `created_at` (DateTime)

**Usage**: Tracks which topics are associated with which issues

---

#### 13. `sentiment_aggregations` (Week 5)
**Purpose**: Stores aggregated sentiment data by topic, issue, or entity

**Key Fields**:
- `id` (UUID, Primary Key)
- `aggregation_type` (String) - 'topic', 'issue', 'entity'
- `aggregation_key` (String) - Topic key, issue ID, or entity name
- `time_window` (String) - '15m', '1h', '24h', '7d', '30d'
- `window_start` (DateTime) - Start of time window
- `window_end` (DateTime) - End of time window
- `mention_count` (Integer) - Number of mentions
- `weighted_sentiment_score` (Float) - Weighted average sentiment
- `sentiment_distribution` (JSONB) - Distribution of sentiment labels
- `emotion_distribution` (JSONB) - Distribution of emotions
- `emotion_adjusted_severity` (Float) - Severity adjusted for emotions
- `created_at`, `updated_at` (DateTime)

**Usage**: Stores pre-calculated sentiment aggregations for fast queries

---

#### 14. `sentiment_trends` (Week 5)
**Purpose**: Stores sentiment trend calculations

**Key Fields**:
- `id` (UUID, Primary Key)
- `trend_type` (String) - 'topic', 'issue', 'entity'
- `trend_key` (String) - Topic key, issue ID, or entity name
- `time_window` (String) - '15m', '1h', '24h', '7d', '30d'
- `current_period_start` (DateTime)
- `current_period_end` (DateTime)
- `previous_period_start` (DateTime)
- `previous_period_end` (DateTime)
- `trend_direction` (String) - 'improving', 'deteriorating', 'stable'
- `trend_magnitude` (Float) - Magnitude of change
- `current_sentiment` (Float) - Current period sentiment
- `previous_sentiment` (Float) - Previous period sentiment
- `created_at`, `updated_at` (DateTime)

**Usage**: Stores trend calculations for identifying improving/deteriorating sentiment

---

#### 15. `topic_sentiment_baselines` (Week 5)
**Purpose**: Stores baseline sentiment values per topic for normalization

**Key Fields**:
- `id` (UUID, Primary Key)
- `topic_key` (String, Foreign Key → `topics.topic_key`)
- `baseline_period_start` (DateTime) - Start of baseline period
- `baseline_period_end` (DateTime) - End of baseline period
- `baseline_sentiment_score` (Float) - Average sentiment in baseline period
- `baseline_mention_count` (Integer) - Number of mentions in baseline
- `normalized_sentiment_score` (Float) - Current normalized sentiment
- `deviation_from_baseline` (Float) - Deviation from baseline
- `created_at`, `updated_at` (DateTime)

**Usage**: Stores baseline sentiment for each topic to normalize current sentiment

---

## 📂 Directory Structure

```
Clariona-Backend/
├── src/
│   ├── agent/              # Core agent orchestration
│   │   ├── core.py         # Main SentimentAnalysisAgent class
│   │   └── llm_providers.py
│   │
│   ├── api/                # FastAPI service
│   │   ├── service.py      # API endpoints (minimal, mostly for triggering cycles)
│   │   ├── models.py       # SQLAlchemy database models
│   │   ├── database.py     # Database session factory
│   │   └── auth.py         # Authentication (minimal usage)
│   │
│   ├── config/             # Configuration management (NEW)
│   │   ├── config_manager.py    # Centralized configuration management
│   │   ├── path_manager.py      # Centralized path management
│   │   └── logging_config.py    # Centralized logging configuration
│   │
│   ├── collectors/         # Data collection modules
│   │   ├── collect_twitter_apify.py
│   │   ├── collect_facebook_apify.py
│   │   ├── collect_news_apify.py
│   │   ├── collect_youtube_api.py
│   │   ├── collect_rss.py
│   │   ├── run_collectors.py        # Collector execution orchestrator
│   │   ├── configurable_collector.py
│   │   └── target_config_manager.py # Determines enabled collectors
│   │
│   ├── processing/         # Data processing and analysis
│   │   ├── data_processor.py           # Main processing orchestrator
│   │   ├── presidential_sentiment_analyzer.py  # Sentiment analysis
│   │   ├── governance_analyzer.py      # Ministry/issue classification
│   │   ├── topic_classifier.py         # Topic-based classification (Week 2)
│   │   ├── emotion_analyzer.py         # Emotion detection (Week 3)
│   │   ├── sentiment_weight_calculator.py  # Influence weight calculation (Week 3)
│   │   ├── weighted_sentiment_calculator.py  # Weighted sentiment scoring (Week 3)
│   │   ├── issue_clustering_service.py  # Issue clustering (Week 4)
│   │   ├── issue_detection_engine.py   # Issue detection and management (Week 4)
│   │   ├── issue_lifecycle_manager.py   # Issue lifecycle management (Week 4)
│   │   ├── issue_priority_calculator.py  # Issue priority calculation (Week 4)
│   │   ├── sentiment_aggregation_service.py  # Sentiment aggregation (Week 5)
│   │   ├── sentiment_trend_calculator.py  # Sentiment trend calculation (Week 5)
│   │   ├── topic_sentiment_normalizer.py  # Topic sentiment normalization (Week 5)
│   │   └── record_router.py            # Routes records across parallel pipelines
│   │
│   ├── utils/              # Utility services
│   │   ├── deduplication_service.py    # Removes duplicate records
│   │   ├── collection_tracker.py       # Tracks collection date ranges
│   │   ├── notification_service.py     # Email notifications
│   │   └── common.py                   # Common utility functions
│   │
│   ├── exceptions.py        # Custom exception classes (NEW)
│   │
│   └── alembic/            # Database migrations
│       └── versions/       # Migration scripts
│
├── config/                 # Configuration files
│   ├── agent_config.json
│   ├── target_configs.json  # Collector enable/disable per target
│   ├── llm_config.json
│   └── *.json              # Other config files
│
├── data/
│   ├── raw/                # Raw CSV files from collectors (temporary)
│   └── processed/          # Processed data files (if any)
│
├── logs/
│   ├── automatic_scheduling.log  # Cycle execution logs
│   ├── agent.log           # Agent logs
│   ├── backend.log         # Main backend log (NEW)
│   └── collectors/         # Collector-specific logs
│
├── scripts/                # Utility scripts (not part of main flow)
│
├── run_cycles.sh           # ⚠️ CRITICAL: Cycle trigger script
├── ecosystem.config.js     # PM2 configuration
├── docker-compose.yml      # Docker setup
└── requirements.txt        # Python dependencies
```

---

## 🔌 API Endpoints (Minimal)

**Important**: This backend has MINIMAL API endpoints. Most endpoints are for:
- Triggering cycles
- Health checks
- Admin operations

**The frontend does NOT use these APIs** - it reads directly from the database.

### Key Endpoints:

#### `POST /agent/test-cycle-no-auth?test_user_id={user_id}`
- **Purpose**: Trigger agent cycle for data collection/processing
- **Usage**: Called by `run_cycles.sh`
- **Returns**: Immediate response (processing is async)

#### `GET /health`
- **Purpose**: Health check
- **Usage**: Monitoring/deployment checks

#### `POST /data/update`
- **Purpose**: Upload processed data to database
- **Usage**: Internal use (may be legacy)

#### Other endpoints:
- Admin endpoints (`/admin/*`)
- Presidential analysis endpoints (`/api/presidential/*`)
- Authentication endpoints (`/api/auth/*`)

**Note**: These endpoints are minimal and mostly for backend operation/administration. Frontend applications connect directly to PostgreSQL via Prisma.

---

## ⚙️ Configuration System

The backend uses a **centralized configuration system** that provides a single source of truth for all configuration values. This system replaces hardcoded values throughout the codebase and enables database-backed configuration management.

### ConfigManager

**Location**: `src/config/config_manager.py`

**Purpose**: Centralized configuration management with support for multiple sources and database backend.

**Features**:
- **Multiple Configuration Sources**: Loads from defaults, JSON files, environment variables, and database
- **Priority Order**: Environment variables > Database > JSON files > Defaults
- **Type-Safe Accessors**: `get()`, `get_int()`, `get_float()`, `get_bool()`, `get_list()`, `get_dict()`, `get_path()`
- **Dot-Notation Access**: Access nested config with `"processing.parallel.max_collector_workers"`
- **Database Backend**: Optional database-backed configuration for runtime editing via frontend

**Usage Example**:
```python
from src.config.config_manager import ConfigManager

# Initialize ConfigManager
config = ConfigManager()

# Access configuration values
max_workers = config.get_int('processing.parallel.max_collector_workers', 8)
similarity_threshold = config.get_float('deduplication.similarity_threshold', 0.85)
timeout = config.get_int('collectors.twitter.timeout', 300)

# With database backend (for runtime configuration)
from src.api.database import SessionLocal
db = SessionLocal()
config = ConfigManager(use_database=True, db_session=db)
# Configuration can now be edited via database and will be loaded automatically
```

**Configuration Structure**:
The configuration is organized hierarchically:
- `processing.*` - Processing pipeline settings
- `collectors.*` - Collector-specific settings
- `database.*` - Database connection settings
- `logging.*` - Logging configuration
- `paths.*` - Path configuration
- `deduplication.*` - Deduplication settings
- `llm.*` - LLM model settings
- `api.*` - API settings

### PathManager

**Location**: `src/config/path_manager.py`

**Purpose**: Centralized path management, eliminating duplicate path calculations throughout the codebase.

**Features**:
- **Automatic Directory Creation**: Creates directories if they don't exist
- **Configurable Paths**: Paths can be configured via ConfigManager
- **Consistent Access**: Provides properties for all common paths

**Usage Example**:
```python
from src.config.path_manager import PathManager

# Initialize PathManager (creates ConfigManager internally)
paths = PathManager()

# Access common paths
raw_data_dir = paths.data_raw  # data/raw/
processed_data_dir = paths.data_processed  # data/processed/
logs_dir = paths.logs  # logs/
config_dir = paths.config_dir  # config/

# Get collector-specific log directory
collector_log_dir = paths.get_collector_log_dir("twitter")  # logs/collectors/twitter/
```

**Available Path Properties**:
- `data_raw` - Raw data directory
- `data_processed` - Processed data directory
- `logs` - Logs directory
- `logs_agent` - Agent log file
- `logs_scheduling` - Scheduling log file
- `logs_collectors` - Collectors log directory
- `logs_openai` - OpenAI calls log file
- `config_dir` - Configuration directory
- `config_agent` - Agent config file
- `config_topic_embeddings` - Topic embeddings config file

### Environment Variables (`.env`)

```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/clariti

# OpenAI (for sentiment/analysis)
OPENAI_API_KEY=your_openai_api_key

# Email (for notifications)
EMAIL_SERVER=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# API Keys
YOUTUBE_API_KEY=your_youtube_api_key

# Application
PYTHONPATH=.
SECRET_KEY=your_secret_key
LOG_LEVEL=INFO
```

### Configuration Files (`config/`)

#### `target_configs.json`
Defines which collectors are enabled for each target individual:
```json
{
  "target_name": {
    "enabled_collectors": ["twitter", "facebook", "news", "rss"]
  }
}
```

#### `agent_config.json`
Agent execution configuration:
- Parallel worker counts
- Batch sizes
- Timeouts
- Retry logic

**Note**: This file is automatically loaded and merged by ConfigManager.

#### `llm_config.json`
LLM model configuration:
- Model names
- API endpoints
- Rate limits

### Database-Backed Configuration

**Location**: `src/api/models.py` (SystemConfiguration, ConfigurationSchema tables)

**Purpose**: Enable runtime configuration editing via frontend without code changes.

**Features**:
- **Runtime Editing**: Configuration can be edited via database (frontend can update directly)
- **Audit Trail**: All configuration changes are logged
- **Validation**: Configuration schema ensures valid values
- **Priority**: Database config overrides file-based config (but not environment variables)

**Usage**:
```python
from src.config.config_manager import ConfigManager
from src.api.database import SessionLocal

db = SessionLocal()
config = ConfigManager(use_database=True, db_session=db)
# Configuration is now loaded from database
# Frontend can update SystemConfiguration table directly
```

**Configuration Categories** (in database):
- Processing settings
- Collector settings
- Database settings
- Logging settings
- Path settings
- Deduplication settings
- LLM settings
- API settings
- And more...

See `docs/FRONTEND_CONFIG_MANAGEMENT_GUIDE.md` for frontend integration details.

---

## 🔄 Data Flow Summary

### Complete Cycle Flow:

1. **Trigger** → `run_cycles.sh` calls API endpoint
2. **Collection** → Collectors gather data from multiple sources → Save to CSV
3. **Loading** → Load CSV files into memory
4. **Deduplication** → Remove duplicates → Insert into `sentiment_data` table
5. **Sentiment Analysis** → Analyze sentiment → Update `sentiment_data` table
6. **Governance Classification** → Classify ministry/issue → Update `sentiment_data` table
7. **Location Classification** → Classify location → Update `sentiment_data` table
8. **Complete** → All data is now in database

### Database Write Operations:

- **Phase 3 (Deduplication)**: INSERT into `sentiment_data`
- **Phase 4 (Sentiment)**: UPDATE `sentiment_data`, INSERT into `sentiment_embeddings`
- **Phase 5 (Location)**: UPDATE `sentiment_data`

**All writes go to PostgreSQL database. No files, no frontend APIs, no external services.**

---

## 🚫 What This Backend Does NOT Do

### ❌ Frontend Functionality
- No UI components
- No user interface
- No frontend APIs (frontend reads directly from database)
- No REST APIs for frontend consumption
- No GraphQL endpoints
- No web sockets for real-time updates (minimal WebSocket support exists but not for frontend)

### ❌ User-Facing Features
- No authentication UI
- No user management UI
- No data visualization
- No dashboards
- No reports (email reports exist, but no UI)

### ❌ Direct Frontend Communication
- Frontend applications do NOT call this backend's APIs
- Frontend applications connect DIRECTLY to PostgreSQL database via Prisma ORM
- Backend and Frontend are completely decoupled

---

## ✅ What This Backend DOES Do

### ✅ Data Collection
- Collects from 10+ sources (Twitter, Facebook, News, YouTube, RSS, etc.)
- Runs collectors in parallel for efficiency
- Saves raw data to CSV files temporarily

### ✅ Data Processing
- Sentiment analysis (positive/negative/neutral with scores)
- Governance classification (ministry + issue)
- Location classification
- Topic classification (if implemented)
- Deduplication

### ✅ Data Storage
- Writes all processed data to PostgreSQL database
- Creates embeddings for semantic search
- Links data to users/targets
- Maintains referential integrity

### ✅ Automation
- Automated cycles via `run_cycles.sh`
- Scheduled execution
- Error handling and retry logic
- Logging and monitoring

---

## 📝 Key Files Reference

### Entry Points:
- `run_cycles.sh` - Cycle trigger script
- `src/api/service.py` - FastAPI app and endpoints
- `src/agent/core.py` - Main agent orchestration

### Core Processing:
- `src/agent/core.py` - `run_single_cycle_parallel()` - Main cycle execution
- `src/processing/data_processor.py` - Data processing orchestrator
- `src/processing/presidential_sentiment_analyzer.py` - Sentiment analysis
- `src/processing/governance_analyzer.py` - Ministry/issue classification

### Data Collection:
- `src/collectors/run_collectors.py` - Collector execution
- `src/collectors/target_config_manager.py` - Collector configuration
- Individual collectors in `src/collectors/collect_*.py`

### Database:
- `src/api/models.py` - SQLAlchemy models
- `src/api/database.py` - Database session factory
- `src/alembic/versions/` - Database migrations

### Utilities:
- `src/utils/deduplication_service.py` - Deduplication logic
- `src/utils/collection_tracker.py` - Collection tracking

---

## 🏗️ Infrastructure Components

### Error Handling

**Location**: `src/exceptions.py`

**Purpose**: Custom exception classes for structured error handling throughout the backend.

**Exception Hierarchy**:
```
BackendError (base class)
├── ConfigError - Configuration errors
├── PathError - Path-related errors
├── CollectionError - Data collection errors
├── ProcessingError - Data processing errors
│   └── AnalysisError - Analysis-specific errors (sentiment, governance)
├── DatabaseError - Database operation errors
├── APIError - API-related errors
├── ValidationError - Data validation errors
├── RateLimitError - Rate limit errors (with retry_after)
├── OpenAIError - OpenAI API errors
├── NetworkError - Network-related errors
├── FileError - File operation errors
└── LockError - Lock-related errors
```

**Usage Example**:
```python
from exceptions import ConfigError, CollectionError

try:
    config = ConfigManager()
    value = config.get('some.key')
except ConfigError as e:
    logger.error(f"Configuration error: {e.message}", extra=e.details)
    # Handle error
```

**Benefits**:
- Structured error handling
- Consistent error messages
- Easy to catch specific error types
- Supports error details for debugging

---

### Logging System

**Location**: `src/config/logging_config.py`

**Purpose**: Centralized logging configuration for consistent logging across all modules.

**Features**:
- **Configurable Log Levels**: Set via ConfigManager or environment variables
- **Multiple Handlers**: Console and file handlers
- **Log Rotation**: Automatic log file rotation (configurable size and backup count)
- **UTF-8 Support**: Proper encoding for Windows systems
- **Module-Specific Loggers**: Support for dedicated loggers per module

**Usage Example**:
```python
from src.config.logging_config import setup_logging, get_logger
from src.config.config_manager import ConfigManager
from src.config.path_manager import PathManager

# Setup logging at application startup
config = ConfigManager()
paths = PathManager(config)
setup_logging(config_manager=config, path_manager=paths)

# Use logger in modules
logger = get_logger(__name__)
logger.info("Processing started")
logger.error("Error occurred", exc_info=True)
```

**Configuration** (via ConfigManager):
- `logging.level` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logging.format` - Log message format
- `logging.file_path` - Log file path
- `logging.max_bytes` - Maximum log file size before rotation
- `logging.backup_count` - Number of backup log files to keep

**Log Files**:
- `logs/backend.log` - Main backend log (rotated)
- `logs/agent.log` - Agent-specific log
- `logs/automatic_scheduling.log` - Cycle scheduling log
- `logs/collectors/` - Collector-specific logs

---

## 🔍 Troubleshooting

### Common Issues:

1. **Cycles not starting**
   - Check if backend API is running: `curl http://localhost:8000/health`
   - Check `run_cycles.sh` USER_ID configuration
   - Check backend logs: `logs/backend.log` or `logs/agent.log`

2. **Collectors not running**
   - Check `config/target_configs.json` for enabled collectors
   - Check collector logs: `logs/collectors/`
   - Verify API keys (YouTube, Apify, etc.)
   - Check ConfigManager for collector-specific settings

3. **Database connection errors**
   - Verify `DATABASE_URL` in `.env`
   - Check PostgreSQL is running and accessible
   - Verify database credentials
   - Check database pool settings in ConfigManager

4. **Processing failures**
   - Check OpenAI API key in `.env`
   - Check processing logs: `logs/backend.log`
   - Verify database tables exist (run migrations: `alembic upgrade head`)
   - Check ConfigManager for processing settings (batch sizes, timeouts, etc.)

5. **Configuration issues**
   - Verify configuration files in `config/` directory
   - Check environment variables override settings
   - If using database config, verify `SystemConfiguration` table is populated
   - Check logs for ConfigError exceptions

6. **Path-related errors**
   - Verify PathManager is initialized correctly
   - Check that directories exist or can be created
   - Check path configuration in ConfigManager

---

## 📚 Additional Documentation

### Backend Documentation
- `BACKEND_SETUP_NOTES.md` - Detailed setup instructions for critical files
- `docs/topic-classification-architecture/` - Topic classification system docs

### Configuration Documentation
- `docs/FRONTEND_CONFIG_MANAGEMENT_GUIDE.md` - Frontend guide for managing configuration via database
- `docs/ADDING_NEW_CONFIGS_GUIDE.md` - Guide for adding new configuration values
- `docs/QUICK_START_ADDING_CONFIGS.md` - Quick start for adding configs

### Cleanup Documentation
- `cleanup/README.md` - Cleanup progress and status (COMPLETE)
- `cleanup/CLEANUP_AND_REFACTORING_PLAN.md` - Master cleanup plan (historical reference)

---

## 🎯 Summary

**This backend is a pure data pipeline:**

1. **Collects** data from multiple sources
2. **Processes** data (sentiment, classification, analysis)
3. **Stores** data in PostgreSQL database
4. **Automates** via scheduled cycles

**It has NO frontend. It ONLY interacts with the database.**

**Frontend applications read directly from the database via Prisma ORM - they do NOT communicate with this backend.**

This separation allows:
- ✅ Backend to focus solely on data pipeline
- ✅ Frontend to focus solely on user experience
- ✅ Independent deployment and scaling
- ✅ Technology independence (backend: Python/FastAPI, frontend: Next.js/TypeScript)






