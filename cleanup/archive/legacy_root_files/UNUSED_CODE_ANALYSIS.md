# Unused Code Analysis - service.py and core.py

## 📋 Summary

This document identifies unused code, legacy methods, and potentially removable endpoints in `src/api/service.py` and `src/agent/core.py`.

---

## 🔴 src/agent/core.py - Unused/Legacy Methods

### ❌ NEVER CALLED Methods:

1. **`run()`** (line 2136)
   - **Status**: DEPRECATED
   - **Evidence**: Just logs warning, does nothing
   - **Action**: Can be removed

2. **`start()`** (line 1237)
   - **Status**: USED VIA COMMAND
   - **Evidence**: Called from `execute_command()` when command is "start" (line 1174)
   - **Action**: Keep if `/command` endpoint is used

3. **`stop()`** (line 1248)
   - **Status**: USED VIA COMMAND
   - **Evidence**: Called from `execute_command()` when command is "stop" (line 1177)
   - **Action**: Keep if `/command` endpoint is used

4. **`process_data()`** (line 1260)
   - **Status**: LEGACY (Sequential processing)
   - **Evidence**: Replaced by `_run_sentiment_batch_update_parallel()` and `_run_location_batch_update_parallel()`
   - **Action**: Can be removed (old sequential method)

5. **`update_metrics()`** (line 1962)
   - **Status**: UNUSED
   - **Evidence**: Never called in main flow or from service.py
   - **Action**: Can be removed

6. **`optimize_system()`** (line 2003)
   - **Status**: UNUSED
   - **Evidence**: Async method, never called from service.py or main flow
   - **Action**: Can be removed

7. **`save_config()`** (line 2086)
   - **Status**: UNUSED
   - **Evidence**: Never called (there's `_save_config()` which is used)
   - **Action**: Can be removed (duplicate of `_save_config()`)

8. **`cleanup_old_data()`** (line 2096)
   - **Status**: UNUSED
   - **Evidence**: Never called from service.py or main flow
   - **Action**: Can be removed

9. **`update_location_classifications()`** (line 2252)
   - **Status**: USED VIA COMMAND
   - **Evidence**: Called from `execute_command()` when command is "update_location_classifications" (line 1215)
   - **Action**: Keep if `/command` endpoint is used

10. **`_run_collect_and_process()`** (line 1954)
    - **Status**: LEGACY WRAPPER
    - **Evidence**: Just calls `run_single_cycle()`, which is a wrapper for `run_single_cycle_parallel()`
    - **Action**: Can be removed (redundant wrapper)

### ⚠️ POTENTIALLY UNUSED (Need Verification):

1. **`_get_email_config_for_user()`** (line 816)
   - **Status**: UNCLEAR
   - **Evidence**: Defined but usage unclear
   - **Action**: Check if used in notification code

2. **`_check_and_release_stuck_lock()`** (line 1713)
   - **Status**: USED
   - **Evidence**: Called from `_run_task()` (line 1771)
   - **Action**: Keep (used internally)

### ✅ ACTIVELY USED Methods (DO NOT REMOVE):

- `__init__()` - Initialization
- `run_single_cycle_parallel()` - **MAIN FLOW**
- `_run_automatic_collection()` - **MAIN FLOW**
- `collect_data_parallel()` - **MAIN FLOW**
- `_push_raw_data_to_db()` - **MAIN FLOW**
- `_run_deduplication()` - **MAIN FLOW**
- `_run_sentiment_batch_update_parallel()` - **MAIN FLOW**
- `_run_location_batch_update_parallel()` - **MAIN FLOW**
- `get_status()` - Called from `/status` endpoint
- `execute_command()` - Called from `/command` endpoint
- `start_automatic_scheduling()` - Called from `/agent/automatic-scheduling/start`
- `stop_automatic_scheduling()` - Called from `/agent/automatic-scheduling/stop`
- `get_scheduler_status()` - Called from `/agent/automatic-scheduling/status`
- `_get_latest_target_config()` - Used in collection
- `_get_enabled_collectors_for_target()` - Used in collection
- `_run_collectors_parallel()` - Used in collection
- `_process_sentiment_batches_parallel()` - Used in sentiment analysis
- `_process_location_batches_parallel()` - Used in location classification
- `_init_location_classifier()` - Used in initialization
- `_save_config()` - Used internally
- `_run_task()` - Used for task execution
- `load_config()` - Used in initialization

### 🗑️ Unused Imports (Can Remove):

1. **`AgentBrain`** (line 34)
   - **Status**: NEVER INITIALIZED/USED
   - **Action**: Remove import

2. **`AutogenAgentSystem`** (line 35)
   - **Status**: Only used in `optimize_system()` which is never called
   - **Action**: Remove import (if removing `optimize_system()`)

3. **`schedule`** (line 3)
   - **Status**: Used in deprecated `run()` method and `optimize_system()`
   - **Action**: Check if used elsewhere, likely can remove

4. **`signal`** (line 12)
   - **Status**: Used in deprecated `run()` method
   - **Action**: Can remove if `run()` is removed

5. **`inspect`** (line 37)
   - **Status**: Usage unclear
   - **Action**: Verify if used, likely can remove

---

## 🔴 src/api/service.py - Unused/Legacy Endpoints & Code

### ❌ POTENTIALLY UNUSED Endpoints:

1. **`/status`** (line 218)
   - **Status**: UNCLEAR
   - **Evidence**: Endpoint exists but may not be used by frontend
   - **Action**: Verify frontend usage

2. **`/command`** (line 224)
   - **Status**: UNCLEAR
   - **Evidence**: Endpoint exists, calls `agent.execute_command()`
   - **Action**: Verify frontend usage

3. **`/data/update`** (line 261)
   - **Status**: LEGACY
   - **Evidence**: Old data update endpoint, replaced by collection flow
   - **Action**: Verify if still needed

4. **`/debug-auth`** (line 535)
   - **Status**: DEBUG ENDPOINT
   - **Evidence**: Debug endpoint, likely not used in production
   - **Action**: Remove or keep for debugging

5. **`/latest-data`** (line 575)
   - **Status**: UNCLEAR
   - **Evidence**: Endpoint exists
   - **Action**: Verify frontend usage

6. **`/cache/*`** endpoints (lines 645, 672, 693)
   - **Status**: UNCLEAR
   - **Evidence**: Cache management endpoints
   - **Action**: Verify frontend usage

7. **`/comparison-data`** (line 705)
   - **Status**: UNCLEAR
   - **Evidence**: Endpoint exists
   - **Action**: Verify frontend usage

8. **`/metrics`** (line 751)
   - **Status**: UNCLEAR
   - **Evidence**: Endpoint exists
   - **Action**: Verify frontend usage

9. **`/config`** endpoints (lines 764, 769)
   - **Status**: UNCLEAR
   - **Evidence**: Config management endpoints
   - **Action**: Verify frontend usage

10. **`/email/*`** endpoints (lines 807-1051)
    - **Status**: UNCLEAR
    - **Evidence**: Multiple email-related endpoints
    - **Action**: Verify frontend usage

11. **`/agent/trigger-run-parallel`** (line 1215)
    - **Status**: DUPLICATE
    - **Evidence**: Similar to `/agent/test-cycle-no-auth` but requires auth
    - **Action**: Verify if both are needed

12. **`/agent/automatic-scheduling/*`** (lines 1237-1286)
    - **Status**: UNCLEAR
    - **Evidence**: Scheduling endpoints, but `run_cycles.sh` doesn't use them
    - **Action**: Verify if used by frontend or other systems

13. **`/agent/test-cycle`** (line 1295)
    - **Status**: DUPLICATE
    - **Evidence**: Similar to `/agent/test-cycle-no-auth` but requires auth
    - **Action**: Verify if both are needed

14. **`/user/register`** (line 1398)
    - **Status**: UNCLEAR
    - **Evidence**: User registration endpoint
    - **Action**: Verify frontend usage

15. **`/admin/sync-users`** (line 1433)
    - **Status**: ADMIN
    - **Evidence**: Admin endpoint
    - **Action**: Verify if used

16. **`/media-sources/*`** endpoints (lines 1575, 2431, 2784, 3087, 3893, 4406)
    - **Status**: UNCLEAR
    - **Evidence**: Multiple media source endpoints (newspapers, twitter, television, radio, online, facebook)
    - **Action**: Verify frontend usage

17. **`/sentiment-feedback`** (line 3825)
    - **Status**: UNCLEAR
    - **Evidence**: Feedback endpoint
    - **Action**: Verify frontend usage

18. **`/policy-impact`** (line 4574)
    - **Status**: UNCLEAR
    - **Evidence**: Policy impact endpoint
    - **Action**: Verify frontend usage

19. **`/showcase/add-data`** (line 4846)
    - **Status**: UNCLEAR
    - **Evidence**: Showcase endpoint
    - **Action**: Verify frontend usage

20. **`/debug/*`** endpoints (lines 4979, 5008, 5022)
    - **Status**: DEBUG
    - **Evidence**: Debug endpoints
    - **Action**: Remove or keep for debugging

21. **`/api/test`** (line 4997)
    - **Status**: TEST
    - **Evidence**: Test endpoint
    - **Action**: Remove

22. **React app serving endpoints** (lines 5044-5099)
    - **Status**: UNCLEAR
    - **Evidence**: Endpoints for serving React app
    - **Action**: Verify if backend serves frontend or if separate

### ✅ ACTIVELY USED Endpoints (DO NOT REMOVE):

- `GET /health` - Health check (line 69)
- `POST /agent/test-cycle-no-auth` - **MAIN FLOW** (line 1334)
- `GET /target` - Get target config (line 1079)
- `POST /target` - Update target config (line 1114)
- `GET /target-configs` - Get target configs (line 1167)
- `POST /target-configs` - Update target configs (line 1187)

### 🗑️ Unused Helper Functions:

1. **`deduplicate_sentiment_data()`** (line 355)
   - **Status**: LEGACY
   - **Evidence**: Old deduplication, replaced by `DeduplicationService`
   - **Action**: Can be removed

2. **`normalize_text_for_dedup()`** (line 393)
   - **Status**: LEGACY
   - **Evidence**: Used by old deduplication
   - **Action**: Can be removed if `deduplicate_sentiment_data()` is removed

3. **`remove_similar_content()`** (line 412)
   - **Status**: LEGACY
   - **Evidence**: Old deduplication method
   - **Action**: Can be removed

4. **`remove_similar_content_optimized()`** (line 480)
   - **Status**: LEGACY
   - **Evidence**: Old deduplication method
   - **Action**: Can be removed

5. **`get_latest_run_timestamp()`** (line 346)
   - **Status**: UNCLEAR
   - **Evidence**: Usage unclear
   - **Action**: Verify if used

6. **`extract_policy_name()`** (line 4778)
   - **Status**: UNCLEAR
   - **Evidence**: Used in `/policy-impact` endpoint
   - **Action**: Keep if endpoint is used

7. **`extract_headline_from_text()`** (line 4827)
   - **Status**: UNCLEAR
   - **Evidence**: Used in `/showcase/add-data` endpoint
   - **Action**: Keep if endpoint is used

### 🗑️ Unused Imports (Can Remove):

1. **`WebSocket`** (line 1)
   - **Status**: Used in websocket endpoint
   - **Action**: Keep if websocket is used

2. **`StaticFiles`** (line 4)
   - **Status**: UNCLEAR
   - **Evidence**: May be used for React app serving
   - **Action**: Verify usage

3. **`MailSender`** (line 27)
   - **Status**: UNCLEAR
   - **Evidence**: Imported but usage unclear
   - **Action**: Verify if used in email endpoints

4. **`ReportScheduler`** (line 28)
   - **Status**: USED
   - **Evidence**: Used in email scheduling endpoints
   - **Action**: Keep

### ⚠️ Potentially Unused Code Blocks:

1. **WebSocket functionality** (lines 113-216)
   - **Status**: UNCLEAR
   - **Evidence**: WebSocket endpoint exists but may not be used by frontend
   - **Action**: Verify frontend usage

2. **`broadcast_update()` function** (line 188)
   - **Status**: UNCLEAR
   - **Evidence**: Called from `/command` and `/target` endpoints
   - **Action**: Keep if websocket is used

3. **React app serving code** (lines 5044-5099)
   - **Status**: UNCLEAR
   - **Evidence**: Code for serving React app from backend
   - **Action**: Verify if backend serves frontend

---

## 📊 Summary Statistics

### core.py:
- **Total methods**: ~53
- **Unused/Legacy methods**: ~10 (19%)
- **Unused imports**: ~5

### service.py:
- **Total endpoints**: ~59
- **Potentially unused endpoints**: ~40+ (68%)
- **Unused helper functions**: ~7
- **Unused imports**: ~3

---

## 🎯 Recommended Actions

### High Priority (Safe to Remove):
1. Remove deprecated `run()` method from core.py
2. Remove unused `start()`, `stop()` methods from core.py
3. Remove legacy `process_data()` method from core.py
4. Remove unused `update_metrics()`, `optimize_system()`, `save_config()`, `cleanup_old_data()` from core.py
5. Remove unused `AgentBrain` and `AutogenAgentSystem` imports
6. Remove debug/test endpoints from service.py
7. Remove legacy deduplication functions from service.py

### Medium Priority (Verify First):
1. Verify which endpoints are actually used by frontend
2. Verify websocket usage
3. Verify email endpoint usage
4. Verify media-source endpoint usage

### Low Priority (Keep for Now):
1. Admin endpoints (may be used by admins)
2. Config endpoints (may be used for configuration)
3. React app serving (if backend serves frontend)

