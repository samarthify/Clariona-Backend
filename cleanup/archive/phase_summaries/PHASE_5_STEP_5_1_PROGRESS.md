# Phase 5, Step 5.1: Replace Hardcoded Paths - IN PROGRESS

**Started**: 2025-01-02  
**Status**: ⏳ **IN PROGRESS**  
**Progress**: 2/6 files completed

---

## 📋 Summary

Step 5.1 is replacing all hardcoded path strings with PathManager usage. PathManager already exists from Phase 2 and has most required properties.

---

## ✅ Completed

### 1. src/agent/core.py ✅

**Paths replaced:**
- `'logs/agent.log'` → `_path_manager.logs_agent` (module-level logging)
- `'logs/automatic_scheduling.log'` → `_path_manager.logs_scheduling` (module-level logging)
- `config_path="config/agent_config.json"` → `config_path=None` with `PathManager().config_agent` default
- `'logs/openai_calls.csv'` → `self.path_manager.logs_openai` (2 instances)

**Changes:**
- Added module-level `_path_manager = PathManager()` for logging setup
- Updated `__init__` to use PathManager for default config path
- Replaced all hardcoded log paths with PathManager properties

**Lines changed**: ~15 lines

### 2. src/api/service.py ✅

**Paths replaced:**
- `"logs/automatic_scheduling.log"` → `_path_manager.logs_scheduling` (2 instances in response)

**Changes:**
- Added PathManager import
- Added module-level `_path_manager = PathManager()`
- Updated endpoint response to use PathManager for log file path

**Lines changed**: ~5 lines

### 3. src/api/presidential_service.py ✅

**Paths replaced:**
- `Path("data/processed")` → `PathManager().data_processed`

**Changes:**
- Added PathManager import
- Replaced hardcoded processed data directory path

**Lines changed**: ~3 lines

### 4. src/processing/topic_classifier.py ✅

**Paths replaced:**
- `"config/topic_embeddings.json"` → `PathManager().config_topic_embeddings`

**Changes:**
- Updated default path handling to use PathManager

**Lines changed**: ~2 lines

### 5. src/processing/topic_embedding_generator.py ✅

**Paths replaced:**
- `config_dir / 'topic_embeddings.json'` → `PathManager().config_topic_embeddings`

**Changes:**
- Updated to use PathManager property directly

**Lines changed**: ~2 lines

### 6. Apify Hardcoded Values in Collectors ✅

**Config keys added to ConfigManager:**
- `collectors.apify.default_date_range_days` (default: 7)
- `collectors.apify.default_since_date` (default: "2021-01-01_00:00:00_UTC")
- `collectors.apify.twitter.*` - All Twitter filter defaults (min_retweets, min_faves, filter_verified, etc.)
- `collectors.apify.tiktok.default_oldest_post_date` (default: "1 day")

**Files updated:**
- `src/collectors/collect_twitter_apify.py`:
  - Replaced `timedelta(days=7)` with config value
  - Replaced `"2021-01-01_00:00:00_UTC"` with config value
  - Replaced all filter defaults (min_retweets: 0, min_faves: 0, etc.) with config values
  
- `src/collectors/collect_tiktok_apify.py`:
  - Replaced `"1 day"` hardcoded value with config value

**Lines changed**: ~30 lines

---

## 📊 Statistics

- **Files completed**: 5/6 (paths) + 2 collectors (Apify values)
- **Paths replaced**: ~10 hardcoded paths
- **Apify values replaced**: ~15 hardcoded values
- **Config keys added**: ~15 new config keys
- **Code compiles**: ✅ Verified

---

## 🔄 Remaining Tasks

### 6. src/utils/file_rotation.py
- [ ] Check for example paths (if any)
- [ ] Replace with PathManager if found

### 7. Collectors - Additional Path Checks
- [ ] Check for any remaining hardcoded paths in collector files
- [ ] Replace with PathManager if found

### 8. Base Path Calculations
- [ ] Replace `Path(__file__).parent.parent.parent` patterns with `PathManager().base_path`
- [ ] Files to check:
  - `src/collectors/configurable_collector.py` (if still exists)
  - `src/utils/file_rotation.py` (if still exists)

### 9. Other Apify Collectors
- [ ] Check `collect_instagram_apify.py` for hardcoded date/filter values
- [ ] Check `collect_facebook_apify.py` for hardcoded date/filter values
- [ ] Check `collect_news_apify.py` for hardcoded date/filter values
- [ ] Replace with ConfigManager if found

---

## 📝 Notes

- PathManager already has all required properties:
  - ✅ `logs_agent`
  - ✅ `logs_scheduling`
  - ✅ `logs_collectors`
  - ✅ `logs_openai`
  - ✅ `config_agent`
  - ✅ `config_topic_embeddings`
  - ✅ `data_raw`
  - ✅ `data_processed`

- Module-level PathManager instances are used for logging setup (before class instantiation)

---

**Last Updated**: 2025-01-02

