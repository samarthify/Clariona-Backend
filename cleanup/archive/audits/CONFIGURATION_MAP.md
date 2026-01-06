# Configuration Usage Map

**Created**: 2025-12-27  
**Purpose**: Document how configuration is currently loaded, accessed, and used throughout the codebase  
**Status**: Phase 1, Step 1.5 - In Progress

---

## 📋 Overview

This document maps all configuration usage patterns in the codebase, including:
- Configuration files and their locations
- How configs are loaded
- Where configs are accessed
- Configuration dependencies between modules
- Environment variable usage patterns

---

## 1. CONFIGURATION FILES

### Available Configuration Files

| File | Location | Purpose | Loaded By |
|------|----------|---------|-----------|
| `agent_config.json` | `config/agent_config.json` | Main agent configuration (intervals, parallel processing, timeouts) | `SentimentAnalysisAgent` |
| `target_configs.json` | `config/target_configs.json` | Target-specific collector configurations | `TargetConfigManager`, API endpoints |
| `llm_config.json` | `config/llm_config.json` | LLM/AI model configuration (OpenRouter, OpenAI) | `AutogenAgentSystem` |
| `topic_embeddings.json` | `config/topic_embeddings.json` | Topic embeddings for classification | `TopicClassifier`, `TopicEmbeddingGenerator` |
| `master_topics.json` | `config/master_topics.json` | Master topic definitions | `TopicClassifier` (fallback) |
| `default_config.json` | `config/default_config.json` | Default configuration template | ⚠️ Unused (legacy?) |
| `president_config.json` | `config/president_config.json` | President-specific configuration | ⚠️ Potentially unused |
| `facebook_targets.json` | `config/facebook_targets.json` | Facebook-specific targets | ⚠️ Potentially unused |
| `youtube_tv_channels.json` | `config/youtube_tv_channels.json` | YouTube TV channel mappings | `YouTubeAPICollector` |
| `brain_state.json` | `config/brain_state.json` | Agent brain state | `AgentBrain` (if used) |

---

## 2. CONFIGURATION LOADING PATTERNS

### Pattern 1: Direct JSON File Loading

**Used By**: Most modules  
**Pattern**:
```python
with open(config_path, 'r') as f:
    config = json.load(f)
```

**Instances**:
- `src/agent/core.py` - `load_config()` method (line 769)
- `src/collectors/target_config_manager.py` - `_load_config()` method (line 56)
- `src/api/service.py` - `/target-configs` endpoints (lines 553, 574)
- `src/collectors/rss_feed_validator.py` - `_load_config()` method (line 62)
- `src/agent/autogen_agents.py` - `_load_config_list()` method (line 44+)
- `src/processing/topic_classifier.py` - `_load_topics_from_json_fallback()` (line 134+)

**Issues**:
- No centralized loading
- Different error handling strategies
- Duplicate path calculations
- No validation
- No environment variable override

---

### Pattern 2: Environment Variable Loading

**Used By**: Database, Auth, Collectors, LLM modules  
**Pattern**:
```python
from dotenv import load_dotenv
load_dotenv(dotenv_path=env_path)
value = os.getenv("VAR_NAME", default_value)
```

**Locations**:
- `src/api/database.py` - Loads `.env` from `config/.env` (line 9-14)
- `src/api/auth.py` - Loads `.env` from `config/.env` (line 13-15)
- `src/api/middlewares.py` - Loads `.env` from `config/.env` (line 78-81)
- `src/processing/presidential_sentiment_analyzer.py` - Loads `.env` from `config/.env` (line 35-37)
- `src/agent/autogen_agents.py` - Loads `.env` from `src/agent/.env` (line 17-19)
- `src/collectors/*.py` - Multiple collectors load `.env` from various locations

**Environment Variables Used**:

#### Database
- `DATABASE_URL` - Database connection string

#### API Keys
- `OPENAI_API_KEY` - OpenAI API key
- `OPENROUTER_API_KEY` - OpenRouter API key
- `YOUTUBE_API_KEY` - YouTube Data API key
- `APIFY_API_TOKEN` - Apify API token
- `GNEWS_API_KEY` - GNews API key
- `NEWSAPI_KEY` - NewsAPI key
- `MEDIASTACK_API_KEY` - MediaStack API key
- `SOCIAL_SEARCHER_API_KEY` - Social Searcher API key
- `BRAVE_API_KEY` - Brave Search API key
- `SUPABASE_JWT_SECRET` - JWT secret for auth
- `REACT_APP_SUPABASE_URL` - Supabase URL (used by collectors)
- `REACT_APP_SUPABASE_ANON_KEY` - Supabase anon key (used by collectors)

#### Email
- `EMAIL_SERVER` - SMTP server
- `EMAIL_PORT` - SMTP port (default: 587)
- `EMAIL_USERNAME` - SMTP username
- `EMAIL_PASSWORD` - SMTP password
- `EMAIL_SENDER` - Sender email address
- `EMAIL_RECIPIENTS` - Comma-separated recipients
- `EMAIL_NOTIFICATION_ENABLED` - Enable/disable email notifications
- `NOTIFY_ON_COLLECTION` - Notify on collection
- `NOTIFY_ON_PROCESSING` - Notify on processing
- `NOTIFY_ON_ANALYSIS` - Notify on analysis
- `REPORT_RECIPIENTS` - Report recipients

#### Application
- `API_BASE_URL` - Base URL for API (default: http://localhost:8000)
- `BACKEND_URL` - Backend URL for cycle runner
- `COLLECTOR_USER_ID` - User ID for collectors
- `PYTHONPATH` - Python path
- `NODE_ENV` - Node environment
- `SECRET_KEY` - Application secret key
- `LOG_LEVEL` - Logging level (default: INFO)
- `PYTHONIOENCODING` - Python IO encoding (set to 'utf-8')

#### Apify Configuration
- `APIFY_TIMEOUT_SECONDS` - Apify timeout (default: 180)
- `APIFY_WAIT_SECONDS` - Apify wait time (default: 180)

**Issues**:
- Multiple `.env` file locations
- Inconsistent default values
- No validation
- Scattered throughout codebase
- Hard to track all env vars

---

### Pattern 3: Default Value Merging

**Used By**: `SentimentAnalysisAgent.load_config()`  
**Pattern**:
```python
default_config = {...}
loaded_config = json.load(f)
merged_config = default_config.copy()
merged_config.update(loaded_config)
```

**Location**: `src/agent/core.py` line 745-787

**Features**:
- Has default fallback
- Merges with file config
- Saves default if file missing
- Handles errors gracefully

**Issues**:
- Only used in one place
- Defaults are hardcoded
- No environment variable override
- No validation

---

### Pattern 4: Config Path Calculation

**Pattern**: `Path(__file__).parent.parent.parent / "config" / "filename.json"`

**Used In**:
- `src/agent/core.py` line 160: `config_path="config/agent_config.json"` (relative, resolved in `__init__`)
- `src/collectors/target_config_manager.py` line 42: Absolute path calculation
- `src/api/service.py` line 545: Absolute path calculation
- `src/processing/topic_classifier.py` line 60: Absolute path calculation
- `src/processing/topic_embedding_generator.py` line 172: Absolute path calculation
- `src/collectors/rss_feed_validator.py`: Base path calculation
- Many more...

**Issues**:
- Duplicated in 20+ files
- Hard to change if structure changes
- Inconsistent (some relative, some absolute)

---

## 3. CONFIGURATION ACCESS PATTERNS

### Pattern 1: Dictionary `.get()` Access

**Used By**: `SentimentAnalysisAgent`  
**Pattern**:
```python
self.config = self.load_config()
parallel_config = self.config.get('parallel_processing', {})
max_workers = parallel_config.get('max_collector_workers', 3)
```

**Locations**:
- `src/agent/core.py` lines 187-297: Extensive use of nested `.get()` calls

**Example**:
```python
parallel_config = self.config.get('parallel_processing', {})
self.max_collector_workers = parallel_config.get('max_collector_workers', 3)
self.max_sentiment_workers = parallel_config.get('max_sentiment_workers', 4)
self.sentiment_batch_size = parallel_config.get('sentiment_batch_size', 50)
self.location_batch_size = parallel_config.get('location_batch_size', 100)
```

**Issues**:
- Deeply nested `.get()` calls
- Default values scattered
- Hard to track all config keys used
- No type checking

---

### Pattern 2: Direct Attribute Access

**Used By**: `TargetConfigManager`, `TargetConfig` dataclass  
**Pattern**:
```python
@dataclass
class TargetConfig:
    name: str
    sources: Dict[str, TargetSourceConfig]
    
# Access:
target_config.sources['twitter'].enabled
```

**Locations**:
- `src/collectors/target_config_manager.py` - Uses dataclasses for type safety

**Advantages**:
- Type-safe
- IDE autocomplete
- Clear structure

**Issues**:
- Only used for target configs
- Not consistent across codebase

---

### Pattern 3: Environment Variable Direct Access

**Pattern**:
```python
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found")
```

**Locations**: Throughout codebase

**Issues**:
- No centralized access
- Inconsistent error handling
- Default values scattered
- Hard to mock in tests

---

## 4. CONFIGURATION DEPENDENCIES

### Dependency Graph

```
┌─────────────────────┐
│  agent_config.json  │
└──────────┬──────────┘
           │
           ├─> SentimentAnalysisAgent (core.py)
           │   ├─> Parallel processing settings
           │   ├─> Timeouts
           │   ├─> Scheduling intervals
           │   ├─> OpenAI logging config
           │   └─> Rate limits
           │
┌──────────┴──────────┐
│ target_configs.json │
└──────────┬──────────┘
           │
           ├─> TargetConfigManager
           │   └─> All collectors
           │       ├─> Twitter collector
           │       ├─> Facebook collector
           │       ├─> Instagram collector
           │       ├─> TikTok collector
           │       ├─> News collector
           │       ├─> RSS collector
           │       ├─> YouTube collector
           │       └─> Radio collector
           │
           └─> API endpoints (service.py)
               ├─> GET /target-configs
               └─> POST /target-configs

┌─────────────────────┐
│   llm_config.json   │
└──────────┬──────────┘
           │
           └─> AutogenAgentSystem
               └─> LLM providers

┌─────────────────────┐
│topic_embeddings.json│
└──────────┬──────────┘
           │
           ├─> TopicClassifier
           └─> TopicEmbeddingGenerator

┌─────────────────────┐
│ master_topics.json  │
└──────────┬──────────┘
           │
           └─> TopicClassifier (fallback)

┌─────────────────────┐
│youtube_tv_channels  │
│      .json          │
└──────────┬──────────┘
           │
           └─> YouTubeAPICollector

┌─────────────────────┐
│   .env file(s)      │
└──────────┬──────────┘
           │
           ├─> Database connection
           ├─> API keys (OpenAI, YouTube, etc.)
           ├─> Email configuration
           ├─> Authentication secrets
           └─> Application settings
```

---

## 5. CONFIGURATION ACCESS BY MODULE

### `src/agent/core.py` (SentimentAnalysisAgent)

**Config File**: `agent_config.json`

**Access Pattern**: `self.config.get(...)`

**Config Keys Accessed**:
- `parallel_processing.max_collector_workers` (default: 3)
- `parallel_processing.max_sentiment_workers` (default: 4)
- `parallel_processing.max_location_workers` (default: 2)
- `parallel_processing.sentiment_batch_size` (default: 50)
- `parallel_processing.location_batch_size` (default: 100)
- `parallel_processing.collector_timeout_seconds` (default: 1000)
- `parallel_processing.batch_timeout_seconds` (default: None)
- `parallel_processing.apify_timeout_seconds` (default: 180)
- `parallel_processing.apify_wait_seconds` (default: 180)
- `parallel_processing.lock_max_age_seconds` (default: 300)
- `parallel_processing.enabled` (default: True)
- `openai_logging.enabled` (default: False)
- `openai_logging.log_path` (default: 'logs/openai_calls.csv')
- `openai_logging.max_chars` (default: 2000)
- `openai_logging.redact_prompts` (default: False)
- `auto_scheduling.enabled` (default: False)
- `auto_scheduling.cycle_interval_minutes` (default: from collection_interval_minutes)
- `auto_scheduling.continuous_mode` (default: False)
- `auto_scheduling.stop_after_first_cycle` (default: False)
- `auto_scheduling.max_consecutive_cycles` (default: 0)
- `auto_scheduling.enabled_user_ids` (default: [])
- `collection_interval_minutes` (default: 60)
- `processing_interval_minutes` (default: 120)
- `cleanup_interval_hours` (default: 24)
- `rate_limits.twitter` (default: 100)
- `rate_limits.news` (default: 50)

---

### `src/collectors/target_config_manager.py` (TargetConfigManager)

**Config File**: `target_configs.json`

**Access Pattern**: Parsed into dataclasses

**Structure**:
```json
{
  "targets": {
    "target_id": {
      "name": "...",
      "sources": {
        "twitter": {
          "enabled": true,
          "countries": [],
          "keywords": [],
          "locations": [],
          "filters": {}
        }
      },
      "sentiment_rules": {}
    }
  }
}
```

**Used By**: All collector modules

---

### `src/collectors/configurable_collector.py` (ConfigurableCollector)

**Hardcoded Values**:
- `collector_timeout = 1800` (30 minutes)
- `overall_timeout = 7200` (2 hours)
- Collector module mappings (hardcoded dictionary)

**Should Use**: `agent_config.json` for timeouts

---

### `src/processing/topic_classifier.py` (TopicClassifier)

**Config Files**:
- `topic_embeddings.json` (primary)
- `master_topics.json` (fallback from DB)

**Access Pattern**: Direct file loading

---

### `src/agent/autogen_agents.py` (AutogenAgentSystem)

**Config File**: `llm_config.json`

**Access Pattern**: Loads config_list, merges with env vars

**Features**:
- Resolves environment variable placeholders (`${VAR_NAME}`)
- Adds OpenRouter config if key present
- Adds OpenAI config if key present

---

### `src/api/service.py` (FastAPI App)

**Config Files**:
- `target_configs.json` (via endpoints)

**Access Pattern**: Direct file I/O in endpoints

**Endpoints**:
- `GET /target-configs` - Reads file
- `POST /target-configs` - Writes file

---

### `src/api/database.py`

**Environment Variable**: `DATABASE_URL`

**Access Pattern**: `os.getenv("DATABASE_URL")`

**Hardcoded Values**:
- `pool_size=30`
- `max_overflow=20`
- `pool_recycle=3600`
- `pool_timeout=60`

**Should Use**: Configuration file

---

### `src/utils/mail_config.py`

**Environment Variables**:
- `EMAIL_RECIPIENTS`
- `EMAIL_NOTIFICATION_ENABLED`
- `NOTIFY_ON_COLLECTION`
- `NOTIFY_ON_PROCESSING`
- `NOTIFY_ON_ANALYSIS`

**Access Pattern**: Module-level constants loaded at import

---

### `src/utils/mail_sender.py`

**Environment Variables**:
- `EMAIL_SERVER`
- `EMAIL_PORT`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`
- `EMAIL_SENDER`

**Access Pattern**: Loaded in `__init__`

---

## 6. CONFIGURATION ISSUES & PROBLEMS

### Critical Issues

1. **No Centralized Configuration Management**
   - Each module loads configs independently
   - No single source of truth
   - Duplicate loading logic

2. **Inconsistent Configuration Access**
   - Mix of dictionary `.get()`, direct access, env vars
   - No consistent API
   - Hard to mock in tests

3. **Hardcoded Default Values Scattered**
   - Defaults defined in multiple places
   - Same defaults repeated in different files
   - Hard to change globally

4. **No Configuration Validation**
   - No schema validation
   - Errors only discovered at runtime
   - No type checking

5. **Multiple .env File Locations**
   - `config/.env`
   - `src/agent/.env`
   - `src/collectors/.env` (various)
   - Hard to track all env vars

6. **No Environment Variable Override System**
   - Can't override config file values with env vars
   - Inconsistent precedence rules
   - Some use env, some use files, no standard

7. **Configuration Path Duplication**
   - `Path(__file__).parent.parent.parent` repeated 30+ times
   - Hard to change project structure

8. **No Hot Reload**
   - Config changes require restart
   - Can't update configs at runtime

9. **Unused Configuration Files**
   - `default_config.json` (legacy?)
   - `president_config.json` (unused?)
   - `facebook_targets.json` (unused?)

10. **Missing Configuration Documentation**
    - No documentation of config keys
    - No examples
    - No schema definitions

---

## 7. CONFIGURATION USAGE STATISTICS

### Files That Load Configuration

- **JSON Config Files**: 10 files
- **Environment Variables**: 50+ different variables
- **Modules Loading Configs**: ~30 modules
- **Config Path Calculations**: 30+ instances
- **Default Values**: 100+ hardcoded defaults

### Configuration Access Patterns

- **Dictionary `.get()`**: ~50 instances
- **Direct Env Var Access**: ~100 instances
- **Direct File Loading**: ~20 instances
- **Dataclass Access**: 1 module (TargetConfigManager)

---

## 8. RECOMMENDATIONS

### Immediate Actions

1. **Create Centralized ConfigManager**
   - Single point of configuration loading
   - Consistent API across codebase
   - Environment variable override support

2. **Consolidate Configuration Files**
   - Merge related configs
   - Remove unused files
   - Standardize structure

3. **Create Configuration Schema**
   - JSON Schema validation
   - Type definitions
   - Documentation

4. **Standardize Path Resolution**
   - Create PathManager utility
   - Single base path calculation
   - Configurable paths

5. **Document All Configuration Options**
   - Config key reference
   - Environment variable list
   - Examples

### Long-term Improvements

6. **Add Configuration Validation**
   - Schema validation on load
   - Type checking
   - Required field validation

7. **Implement Hot Reload** (optional)
   - Watch config files
   - Reload on change
   - Notify dependent modules

8. **Create Configuration UI** (optional)
   - Web interface for config management
   - Validation feedback
   - Preview changes

---

## 9. CONFIGURATION MIGRATION PLAN

### Phase 1: Create ConfigManager
- [ ] Design ConfigManager API
- [ ] Implement base ConfigManager
- [ ] Add path resolution
- [ ] Add environment variable override

### Phase 2: Migrate Existing Configs
- [ ] Migrate `agent_config.json` usage
- [ ] Migrate `target_configs.json` usage
- [ ] Migrate `llm_config.json` usage
- [ ] Migrate environment variables

### Phase 3: Consolidate & Cleanup
- [ ] Remove duplicate config loading
- [ ] Remove unused config files
- [ ] Standardize config access patterns
- [ ] Add validation

### Phase 4: Documentation
- [ ] Document all config keys
- [ ] Create configuration guide
- [ ] Add examples
- [ ] Update README

---

**Last Updated**: 2025-12-27  
**Status**: ✅ Configuration usage mapped - Ready for Phase 2 implementation






