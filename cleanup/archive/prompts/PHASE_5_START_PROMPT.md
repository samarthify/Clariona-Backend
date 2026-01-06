# Phase 5: Replace Hardcoded Values - Start Prompt

**Created**: 2025-01-02  
**Purpose**: Comprehensive guide to start Phase 5 with all context and details  
**Status**: Phase 5 in progress - Step 5.1 ✅ **COMPLETE**, Step 5.2 starting  
**Previous Phase**: Phase 4 - ✅ **COMPLETE**

---

## 📋 Context Summary

Phase 4 (Remove Unused Code) is complete:
- ✅ All unused methods removed from `core.py`
- ✅ All unused endpoints removed from `service.py` (~750+ lines)
- ✅ Legacy collector system removed (~60 lines)
- ✅ Unused files removed (`brain.py`, `autogen_agents.py` - ~706 lines)
- **Total removed**: ~1519+ lines

Now moving to **Phase 5: Replace Hardcoded Values** - Replace all hardcoded values with configuration system.

---

## 🎯 Phase 5 Goal

Replace all hardcoded values with centralized configuration:
- **Estimated values to replace**: ~230-235 hardcoded values (after removing unused code)
- **Target**: All paths, timeouts, thresholds, sizes, URLs, and other constants from config
- **Benefit**: Easier maintenance, environment-specific configs, no code changes for config updates

---

## 📊 Phase 5 Overview

Phase 5 consists of 5 steps:

1. **Step 5.1**: Replace hardcoded paths (1-2 days)
2. **Step 5.2**: Replace hardcoded timeouts & limits (1-2 days)
3. **Step 5.3**: Replace hardcoded thresholds (1 day)
4. **Step 5.4**: Replace model constants (1 day)
5. **Step 5.5**: Replace URLs & CORS (1 day)

**Total Estimated Time**: 5-7 days

---

## 🔍 Detailed Phase 5 Steps

### Step 5.1: Replace Hardcoded Paths

**Time**: 1-2 days  
**Priority**: 🔴 HIGH  
**Infrastructure**: PathManager (already exists from Phase 2)

#### Tasks:

1. **Add missing path properties to PathManager**:
   - `logs_agent` - Already exists ✅
   - `logs_scheduling` - Already exists ✅
   - `logs_collectors` - Already exists ✅
   - `logs_openai` - Already exists ✅
   - `config_agent` - Add if missing
   - `config_topic_embeddings` - Add if missing
   - `data_processed_latest` - Add if missing

2. **Replace hardcoded paths in files**:
   - `src/agent/core.py` - Replace log paths, config paths, data paths
   - `src/api/service.py` - Replace log path references
   - `src/api/presidential_service.py` - Replace `data/processed` path
   - `src/processing/topic_classifier.py` - Replace `config/topic_embeddings.json`
   - `src/processing/topic_embedding_generator.py` - Replace `config/topic_embeddings.json`
   - `src/utils/file_rotation.py` - Replace example paths
   - All collectors - Replace any hardcoded paths

3. **Remove duplicate base_path calculations**:
   - Replace `Path(__file__).parent.parent.parent` with `PathManager().base_path`
   - Files to update:
     - `src/agent/core.py` (if still exists)
     - `src/collectors/configurable_collector.py` (if still exists)
     - `src/utils/file_rotation.py` (if still exists)

#### Verification Checklist:
- [ ] All path properties added to PathManager
- [ ] All hardcoded path strings replaced
- [ ] All base_path calculations replaced
- [ ] Code compiles without errors
- [ ] Paths work correctly (directories created automatically)

#### Expected Result:
- All paths use PathManager
- No hardcoded path strings remaining
- Centralized path management

---

### Step 5.2: Replace Hardcoded Timeouts & Limits

**Time**: 1-2 days  
**Priority**: 🔴 HIGH  
**Infrastructure**: ConfigManager (already exists from Phase 2)

#### Tasks:

1. **Add timeout/limit config keys to default_config.json**:
   - `processing.timeouts.collector_timeout_seconds` (default: 1000)
   - `processing.timeouts.apify_timeout_seconds` (default: 180)
   - `processing.timeouts.apify_wait_seconds` (default: 180)
   - `processing.timeouts.lock_max_age_seconds` (default: 300)
   - `processing.timeouts.http_request_timeout` (default: 120)
   - `processing.timeouts.overall_timeout_seconds` (default: 7200)
   - `database.pool_recycle_seconds` (default: 3600)
   - `database.pool_size` (default: 30)
   - `database.max_overflow` (default: 20)
   - `database.pool_timeout_seconds` (default: 60)
   - `collectors.rss.timeout_seconds` (default: 10)
   - `collectors.rss.feed_timeout_seconds` (default: 30)
   - `collectors.rss.overall_timeout_seconds` (default: 600)
   - `collectors.rss.buffer_seconds` (default: 5)
   - `collectors.rss.ssl_timeout_seconds` (default: 10)
   - `collectors.rss.socket_timeout_seconds` (default: 10)
   - `collectors.radio.timeout_seconds` (default: 15)
   - `collectors.radio.gnews_timeout_seconds` (default: 30)
   - `api.timeouts.http_request_timeout` (default: 60)

2. **Add batch size/limit config keys**:
   - `processing.batch.sentiment_batch_size` (default: 50)
   - `processing.batch.location_batch_size` (default: 50)
   - `processing.batch.max_results` (default: varies)
   - `processing.batch.max_records` (default: varies)
   - `processing.batch.progress_log_interval` (default: varies)

3. **Replace hardcoded timeouts/limits in files**:
   - `src/agent/core.py` - Replace all timeout values
   - `src/api/database.py` - Replace pool settings
   - `src/collectors/configurable_collector.py` - Replace timeouts
   - `src/collectors/*.py` - Replace collector-specific timeouts
   - `src/utils/deduplication_service.py` - Replace batch sizes
   - `src/processing/data_processor.py` - Replace batch sizes

#### Verification Checklist:
- [ ] All timeout/limit config keys added
- [ ] All hardcoded timeouts replaced
- [ ] All hardcoded limits replaced
- [ ] Code compiles without errors
- [ ] Default values work correctly

#### Expected Result:
- All timeouts/limits from config
- No magic numbers for timeouts/limits

---

### Step 5.3: Replace Hardcoded Thresholds

**Time**: 1 day  
**Priority**: 🟡 MEDIUM  
**Infrastructure**: ConfigManager

#### Tasks:

1. **Add threshold config keys to default_config.json**:
   - `deduplication.similarity_threshold` (default: 0.85)
   - `processing.topic.min_score_threshold` (default: 0.2)
   - Any other confidence/score thresholds

2. **Replace hardcoded thresholds in files**:
   - `src/utils/deduplication_service.py` - Replace similarity threshold
   - `src/processing/topic_classifier.py` - Replace score thresholds
   - Any other threshold usage

#### Verification Checklist:
- [ ] All threshold config keys added
- [ ] All hardcoded thresholds replaced
- [ ] Code compiles without errors
- [ ] Thresholds work correctly

#### Expected Result:
- All thresholds from config

---

### Step 5.4: Replace Hardcoded Model Constants

**Time**: 1 day  
**Priority**: 🟡 MEDIUM  
**Infrastructure**: ConfigManager

#### Tasks:

1. **Add model constant config keys to default_config.json**:
   - `models.string_lengths.*` - String length limits for database columns
   - `models.embedding_model` - Embedding model name
   - `models.llm_models.*` - LLM model names

2. **Replace hardcoded model constants in files**:
   - `src/api/models.py` - Replace string lengths
   - `src/processing/presidential_sentiment_analyzer.py` - Replace model names

#### Verification Checklist:
- [ ] All model constant config keys added
- [ ] All hardcoded model constants replaced
- [ ] Code compiles without errors
- [ ] Models work correctly

#### Expected Result:
- Model constants from config
- Updated model definitions

---

### Step 5.5: Replace Hardcoded URLs & CORS

**Time**: 1 day  
**Priority**: 🟡 MEDIUM  
**Infrastructure**: ConfigManager

#### Tasks:

1. **Add URL/CORS config keys to default_config.json**:
   - `api.cors.origins` - CORS allowed origins
   - `api.urls.*` - API URLs (if hardcoded)

2. **Replace hardcoded URLs/CORS in files**:
   - `src/api/service.py` - Replace CORS origins

#### Verification Checklist:
- [ ] All URL/CORS config keys added
- [ ] All hardcoded URLs/CORS replaced
- [ ] Code compiles without errors
- [ ] CORS works correctly

#### Expected Result:
- CORS from config
- No hardcoded URLs

---

## 📊 Summary of Values to Replace

### High Priority Removals:

| Category | Count | Priority | Files Affected |
|----------|-------|----------|----------------|
| Paths | ~15-20 | 🔴 HIGH | core.py, service.py, collectors, processing |
| Timeouts | ~30-40 | 🔴 HIGH | core.py, database.py, collectors |
| Limits/Batch Sizes | ~20-30 | 🔴 HIGH | core.py, data_processor.py, deduplication |
| Thresholds | ~5-10 | 🟡 MEDIUM | deduplication_service.py, topic_classifier.py |
| Model Constants | ~10-15 | 🟡 MEDIUM | models.py, sentiment_analyzer.py |
| URLs/CORS | ~5-10 | 🟡 MEDIUM | service.py |

**Total Estimated**: ~230-235 hardcoded values

---

## 📝 Key Reference Documents

### Primary Documentation:
- **`cleanup/HARDCODED_VALUES_AUDIT.md`** - Complete inventory of all hardcoded values with line numbers and suggested config keys
- **`cleanup/CLEANUP_AND_REFACTORING_PLAN.md`** - Phase 5 overview (lines 645-758)
- **`cleanup/HARDCODED_VALUES_IN_UNUSED_CODE.md`** - Hardcoded values in unused code (already removed in Phase 4)

### Infrastructure Available:
- **`src/config/config_manager.py`** - ConfigManager class (from Phase 2)
- **`src/config/path_manager.py`** - PathManager class (from Phase 2)
- **`config/default_config.json`** - Default configuration file (needs expansion)

### Code Files to Modify:
- `src/agent/core.py` - Paths, timeouts, limits
- `src/api/service.py` - Paths, CORS
- `src/api/database.py` - Timeouts, pool settings
- `src/collectors/*.py` - Paths, timeouts
- `src/processing/*.py` - Paths, thresholds
- `src/utils/*.py` - Paths, thresholds, batch sizes
- `src/api/models.py` - Model constants

---

## ⚠️ Important Notes

### 1. Use Existing Infrastructure
- **PathManager** already exists with some properties - extend it as needed
- **ConfigManager** already exists - use it for all config access
- **default_config.json** exists but is minimal - expand it with all new keys

### 2. Backward Compatibility
- Keep default values in code/config for backward compatibility
- Environment variables can override (via ConfigManager)
- Don't break existing functionality

### 3. Incremental Approach
- Replace values incrementally by file/category
- Test after each replacement
- Keep backups/branches

### 4. Testing After Each Step
- Test main execution flow after each step
- Ensure `run_cycles.sh` still works
- Verify no broken functionality

---

## ✅ Verification Checklist (After Each Step)

After completing each step, verify:
- [ ] Code compiles without errors
- [ ] Main execution flow still works (`run_cycles.sh` → `/agent/test-cycle-no-auth`)
- [ ] No broken functionality
- [ ] Config values are accessible via ConfigManager
- [ ] Default values work correctly
- [ ] Environment variable overrides work (if applicable)

---

## 🎯 Success Criteria

Phase 5 is complete when:
- ✅ All hardcoded paths replaced with PathManager
- ✅ All hardcoded timeouts/limits replaced with ConfigManager
- ✅ All hardcoded thresholds replaced with ConfigManager
- ✅ All model constants replaced with ConfigManager
- ✅ All URLs/CORS replaced with ConfigManager
- ✅ Code compiles without errors
- ✅ Main execution flow still works
- ✅ ~230-235 hardcoded values replaced

---

## 🚀 Getting Started

### Recommended Order:
1. Start with **Step 5.1** (paths) - High impact, PathManager already exists
2. Then **Step 5.2** (timeouts/limits) - High impact, many values
3. Then **Step 5.3** (thresholds) - Medium impact
4. Then **Step 5.4** (model constants) - Medium impact
5. Finally **Step 5.5** (URLs/CORS) - Medium impact

### First Steps:
1. Read `HARDCODED_VALUES_AUDIT.md` for detailed list
2. Review existing PathManager properties
3. Start with Step 5.1 - add missing path properties and replace hardcoded paths
4. Test main flow after each replacement
5. Document what was replaced

---

## 📊 Progress Tracking

### Step 5.1: Replace hardcoded paths ✅ **COMPLETE** (All paths + All collector values + Keywords)
- [x] Missing path properties added to PathManager (already exist)
- [x] Hardcoded paths replaced in core.py ✅
- [x] Hardcoded paths replaced in service.py ✅
- [x] Hardcoded paths replaced in processing files ✅
- [x] Hardcoded paths replaced in presidential_service.py ✅
- [x] Apify hardcoded values replaced (Twitter, TikTok, Instagram, News) ✅
- [x] Incremental collector hardcoded values replaced ✅
- [x] All collector timeouts, delays, limits, retries replaced (13 collectors) ✅
- [x] **All keywords now prioritize ConfigManager** (enables DB editing) ✅
  - Updated 13 collectors to check ConfigManager first
  - Supports target-specific keywords: `collectors.keywords.<target>.<collector>`
  - Supports default keywords: `collectors.keywords.default.<collector>`
  - Backward compatible with target_config.json
- [x] **Source-to-collector mapping moved to ConfigManager** ✅
  - `collectors.source_to_collector_mapping` now in ConfigManager
  - Enables dynamic collector mapping via database
- [x] Code tested (compiles successfully)
- [x] Documentation created:
  - KEYWORD_FLOW_DOCUMENTATION.md (actual flow with parallel execution)
  - KEYWORDS_DATABASE_GUIDE.md (SQL examples for DB storage)
  - KEYWORDS_CONFIGMANAGER_PRIORITY_COMPLETE.md (implementation summary)
  - CONFIGMANAGER_DATABASE_SUPPORT.md (DB support documentation)
  - SOURCE_TO_COLLECTOR_MAPPING_COMPLETE.md (mapping centralization)
- [ ] Base path calculations replaced (minor cleanup - optional)

### Step 5.2: Replace hardcoded timeouts & limits ⏳ **IN PROGRESS**
- [x] Collector timeouts/limits (completed in Step 5.1) ✅
- [x] Collector batch sizes (from parallel_processing config) ✅
- [ ] Database pool settings (database.py):
  - [ ] `pool_size=30` → `database.pool_size`
  - [ ] `max_overflow=20` → `database.max_overflow`
  - [ ] `pool_recycle=3600` → `database.pool_recycle_seconds`
  - [ ] `pool_timeout=60` → `database.pool_timeout_seconds`
- [ ] HTTP request timeouts (core.py):
  - [ ] `timeout=120` in requests.post() → `processing.timeouts.http_request_timeout`
- [ ] Batch size defaults (core.py):
  - [ ] `batch_size=100` in update_location_classifications → config
- [ ] Code tested

### Step 5.3: Replace hardcoded thresholds
- [ ] Threshold config keys added
- [ ] Hardcoded thresholds replaced
- [ ] Code tested

### Step 5.4: Replace model constants
- [ ] Model constant config keys added
- [ ] Hardcoded model constants replaced
- [ ] Code tested

### Step 5.5: Replace URLs & CORS
- [ ] URL/CORS config keys added
- [ ] Hardcoded URLs/CORS replaced
- [ ] Code tested

---

**Status**: Phase 5 in progress - Step 5.1 starting  
**Last Updated**: 2025-01-02

