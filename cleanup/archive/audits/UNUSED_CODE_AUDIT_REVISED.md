# Unused Code Audit - REVISED & COMPREHENSIVE

**Created**: 2025-12-27 (Revised)  
**Purpose**: Comprehensive audit of unused/legacy code by cross-referencing with EXECUTION_FLOW_MAP.md  
**Status**: Phase 4 in progress - Step 4.2 ✅ COMPLETE  
**Methodology**: Check EVERY method/function against actual execution flow  
**Last Updated**: 2025-01-02 (Step 4.2 removals completed)

---

## 📋 Audit Methodology (REVISED)

1. ✅ Extract ALL methods from each file
2. ✅ Cross-reference with EXECUTION_FLOW_MAP.md to identify what's actually called
3. ✅ Search codebase for any other references
4. ✅ Identify hardcoded values in unused code paths
5. ✅ Mark hardcoded values in unused code for REMOVAL (not configuration)

---

## 🔴 HIGH CONFIDENCE - Safe to Remove (Verified Against Execution Flow)

### src/agent/core.py

#### Methods NOT in Execution Flow:

Based on EXECUTION_FLOW_MAP.md, the ONLY methods called in the main execution flow are:

**✅ USED (keep):**
1. `__init__()`
2. `run_single_cycle_parallel()` - Main entry point
3. `collect_data_parallel()` - Phase 1
4. `_push_raw_data_to_db()` - Phase 2
5. `_run_deduplication()` - Phase 3
6. `_run_sentiment_batch_update_parallel()` - Phase 4
7. `_run_location_batch_update_parallel()` - Phase 5
8. `_get_latest_target_config()` - Helper
9. `_get_enabled_collectors_for_target()` - Helper
10. `_run_collectors_parallel()` - Helper
11. `_run_task()` - Helper (task management)
12. `_check_and_release_stuck_lock()` - Helper
13. `_process_sentiment_batches_parallel()` - Helper
14. `_process_location_batches_parallel()` - Helper
15. `_parse_date_string()` - Helper
16. `_validate_and_clean_location()` - Helper
17. `_classify_location()` - Helper (location classification)
18. `_init_location_classifier()` - Helper
19. `load_config()` - Helper
20. `get_status()` - Called by API endpoint

**❌ UNUSED (remove):**

#### 1. Automatic Scheduling Methods (NOT in main flow)

**⚠️ NOTE**: These may be called by scheduler, but NOT by main `run_cycles.sh` flow:

- `start_automatic_scheduling()` [line 305] - Called by API endpoint only
- `stop_automatic_scheduling()` [line 334] - Called by API endpoint only
- `_run_scheduler_loop()` [line 404] - Internal to scheduler
- `_get_active_users()` [line 508] - Called by scheduler
- `_is_user_auto_scheduling_enabled()` [line 527] - Called by scheduler
- `_should_run_collection()` [line 547] - Called by scheduler
- `_run_automatic_collection_tracked()` [line 591] - Called by scheduler
- `_run_automatic_collection()` [line 601] - Called by scheduler (wrapper)
- `get_scheduler_status()` [line 642] - Called by API endpoint

**Confidence**: 🟡 **MEDIUM** - These are used by scheduler, but scheduler is NOT used by main flow.  
**Action**: ✅ **COMPLETED** - Scheduler verified unused (we use run_cycles.sh instead). All scheduler methods removed in Step 4.2.

#### 2. Command Execution Methods (NOT in main flow) - ✅ PARTIALLY REMOVED (Step 4.2)

- `execute_command()` [line 1166] - Called by `/command` API endpoint only - ✅ REMOVED (endpoint removed)
- `start()` [line 1234] - Called via `execute_command()` - Still exists (placeholder methods)
- `stop()` [line 1245] - Called via `execute_command()` - Still exists (placeholder methods)
- `update_location_classifications()` [line 2187] - Called via `execute_command()` - Still exists (may be used elsewhere)

**Confidence**: 🟡 **MEDIUM** - Only used by `/command` endpoint, which is NOT in main flow  
**Action**: ✅ **COMPLETED** - `/command` endpoint removed. `execute_command()` method removed from core.py. `start()` and `stop()` kept as placeholder methods (commented out code).

#### 3. Config Saving Method (NOT in main flow)

- `_save_config()` [line 1221] - Never called in execution flow

**Confidence**: 🔴 **HIGH**  
**Action**: **REMOVE**

#### 4. Wrapper Methods (REDUNDANT)

- `run_single_cycle()` [line 1958] - Just wraps `run_single_cycle_parallel()`

**Confidence**: 🟡 **MEDIUM** - May be called by scheduler  
**Action**: **VERIFY** and remove if not needed

#### 5. Email Configuration Method (NOT in main flow)

- `_get_email_config_for_user()` [line 813] - Only called in scheduler code (unused path)

**Confidence**: 🟡 **MEDIUM**  
**Action**: **VERIFY** - if scheduler removed, this goes too

---

### src/processing/data_processor.py

#### Methods Actually Used (from execution flow):

From EXECUTION_FLOW_MAP.md, only these are called:
- `batch_get_sentiment()` - Called by `_process_sentiment_batches_parallel()`
- `get_sentiment()` - Called by `batch_get_sentiment()` (fallback)

#### Methods NOT Used:

1. **`process_data()`** [line 851]
   - **Evidence**: Only called in `if __name__ == "__main__"` block (line 1083)
   - **Not in execution flow**: Not called by agent
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**
   - **Hardcoded values to REMOVE** (not config):
     - `batch_size = 100` [line 894]
     - `random.seed(42)` [line 65] - if only used here
     - `len_ratio < 0.5` [line 912]

2. **`load_raw_data()`** [likely exists]
   - **Evidence**: Only called by `process_data()`
   - **Confidence**: 🔴 **HIGH** (if `process_data()` removed)
   - **Action**: **REMOVE**

3. **`save_processed_data()`** [line 1072]
   - **Evidence**: Only called by `process_files()` and `process_data()`
   - **Confidence**: 🟡 **MEDIUM** (need to check `process_files()`)
   - **Action**: **VERIFY**

4. **`process_files()`** [line 976]
   - **Evidence**: Only called in `if __name__ == "__main__"` or standalone
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: **VERIFY** if used anywhere

5. **`normalize_text()`** [line 306]
   - **Evidence**: Only called by `process_data()` (legacy deduplication)
   - **Confidence**: 🔴 **HIGH** (replaced by `DeduplicationService.normalize_text()`)
   - **Action**: **REMOVE**
   - **Hardcoded values to REMOVE** (not config):
     - All hardcoded regex patterns in normalization

6. **`is_similar_text()`** [line 320]
   - **Evidence**: Only called by `process_data()` (legacy deduplication)
   - **Confidence**: 🔴 **HIGH** (replaced by `DeduplicationService.is_similar_text()`)
   - **Action**: **REMOVE**
   - **Hardcoded values to REMOVE** (not config):
     - `threshold=0.85` [line 320]
     - `len(text1) < 10` [line 326]

7. **`parse_date()`** [line 333]
   - **Evidence**: ✅ **USED** - Called by `core.py` in `_parse_date_string()` and `_push_raw_data_to_db()`
   - **Confidence**: ✅ **KEEP**
   - **Action**: **KEEP** - This method is actively used

8. **`deduplicate_data()`** [if exists]
   - **Evidence**: Only called by `process_data()` or `process_files()`
   - **Confidence**: 🔴 **HIGH** (if those removed)
   - **Action**: **REMOVE**

---

### src/api/service.py

#### Endpoints NOT in Main Execution Flow:

From EXECUTION_FLOW_MAP.md, ONLY this endpoint is called:
- ✅ `/agent/test-cycle-no-auth` [line 708] - **USED** - Called by `run_cycles.sh`

#### Endpoints to VERIFY/REMOVE:

1. **`/status`** [line 218]
   - **Evidence**: Not in execution flow
   - **Confidence**: 🟡 **MEDIUM** - May be used by monitoring
   - **Action**: **VERIFY** usage

2. **`/command`** [line 224]
   - **Evidence**: Not in execution flow
   - **Calls**: `agent.execute_command()`, `agent.start()`, `agent.stop()`
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: **VERIFY** - If unused, remove endpoint AND command methods

3. **`/data/update`** [line 280]
   - **Evidence**: Not in execution flow (legacy data insertion method)
   - **Confidence**: 🔴 **HIGH** - Legacy, replaced by pipeline
   - **Action**: **REMOVE**

4. **`/latest-data`** [line 364]
   - **Evidence**: Not in execution flow
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: **VERIFY**

5. **`/config`** (GET/POST) [lines 434, 439]
   - **Evidence**: Not in execution flow
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: **VERIFY**

6. **`/target`** (GET/POST) [lines 452, 488]
   - **Evidence**: Not in execution flow (targets come from DB)
   - **Confidence**: 🟡 **MEDIUM** - May be used for config management
   - **Action**: **VERIFY**

7. **`/target-configs`** (GET/POST) [lines 541, 561]
   - **Evidence**: Not in execution flow (configs loaded directly)
   - **Confidence**: 🟡 **MEDIUM** - May be used for config management
   - **Action**: **VERIFY**

8. **`/agent/trigger-run-parallel`** [line 589]
   - **Evidence**: Not in execution flow (duplicate of `/agent/test-cycle-no-auth`)
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

9. **`/agent/automatic-scheduling/*`** [lines 611, 632, 653]
   - **Evidence**: Not in execution flow (scheduler not used)
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: **VERIFY** - If scheduler unused, REMOVE

10. **`/agent/test-cycle`** [line 669]
    - **Evidence**: Not in execution flow (duplicate, requires auth)
    - **Confidence**: 🔴 **HIGH**
    - **Action**: **REMOVE**

11. **`/user/register`** [line 772]
    - **Evidence**: Not in execution flow
    - **Confidence**: 🟡 **MEDIUM** - May be used for user management
    - **Action**: **VERIFY**

12. **`/admin/sync-users`** [line 807]
    - **Evidence**: Not in execution flow
    - **Confidence**: 🟡 **MEDIUM** - Admin function
    - **Action**: **VERIFY**

13. **React app serving endpoints** [lines 962-1016]
    - **Evidence**: Backend shouldn't serve frontend
    - **Confidence**: 🔴 **HIGH**
    - **Action**: **REMOVE**

14. **WebSocket endpoints** [line 200]
    - **Evidence**: Not in execution flow
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: **VERIFY**

15. **Debug endpoints** [`.env`, `.git`, etc.] [lines 84-89]
    - **Evidence**: Security risk
    - **Confidence**: 🔴 **HIGH**
    - **Action**: **REMOVE**

#### Helper Functions NOT Used:

1. **`deduplicate_sentiment_data()`** [line ~438]
   - **Evidence**: Legacy, replaced by `DeduplicationService`
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

2. **`normalize_text_for_dedup()`** [line ~478]
   - **Evidence**: Legacy, replaced by `DeduplicationService`
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

3. **`remove_similar_content()`** [line ~497]
   - **Evidence**: Legacy, replaced by `DeduplicationService`
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

4. **`remove_similar_content_optimized()`** [if exists]
   - **Evidence**: Legacy
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

5. **`get_latest_run_timestamp()`** [line ~346]
   - **Evidence**: Not in execution flow
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: **VERIFY**

6. **`extract_policy_name()`** [line ~4778]
   - **Evidence**: Only used by `/policy-impact` endpoint (unused)
   - **Confidence**: 🔴 **HIGH** (if endpoint removed)
   - **Action**: **REMOVE** with endpoint

7. **`extract_headline_from_text()`** [line ~4827]
   - **Evidence**: Only used by `/showcase/add-data` endpoint (unused)
   - **Confidence**: 🔴 **HIGH** (if endpoint removed)
   - **Action**: **REMOVE** with endpoint

---

### src/agent/brain.py

#### Entire File
- **Evidence**: `AgentBrain` imported but never initialized or called
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE entire file**

---

### src/agent/autogen_agents.py

#### Entire File
- **Evidence**: `AutogenAgentSystem` only used in `optimize_system()` which is unused
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE entire file**

---

### src/api/presidential_service.py

#### Legacy Deduplication Functions

1. **`deduplicate_sentiment_data()`** [line 438]
   - **Evidence**: Legacy, replaced by `DeduplicationService`
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

2. **`normalize_text_for_dedup()`** [line 478]
   - **Evidence**: Legacy
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

3. **`remove_similar_content()`** [line 497]
   - **Evidence**: Legacy
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

**Hardcoded values to REMOVE** (not config):
- `similarity_threshold: float = 0.85` [line 497]

---

### src/collectors/run_collectors.py

#### Legacy Functions

1. **`run_legacy_collectors()`** [line 82]
   - **Evidence**: Not in execution flow (configurable collectors used instead)
   - **Confidence**: 🔴 **HIGH**
   - **Action**: **REMOVE**

---

## 🎯 Hardcoded Values in UNUSED Code (REMOVE, don't configure)

### DataProcessor.process_data() [TO BE REMOVED]

- `batch_size = 100` [line 894] - **REMOVE** (entire method)
- `len_ratio < 0.5` [line 912] - **REMOVE** (entire method)
- `random.seed(42)` [line 65] - **VERIFY** if only used here, then **REMOVE**

### DataProcessor.normalize_text() [TO BE REMOVED]

- All regex patterns - **REMOVE** (entire method)
- All hardcoded text processing logic - **REMOVE** (entire method)

### DataProcessor.is_similar_text() [TO BE REMOVED]

- `threshold=0.85` [line 320] - **REMOVE** (entire method)
- `len(text1) < 10` [line 326] - **REMOVE** (entire method)

### presidential_service.py deduplication functions [TO BE REMOVED]

- `similarity_threshold: float = 0.85` [line 497] - **REMOVE** (entire function)

---

## 📊 Summary Statistics (REVISED)

### High Confidence Removals:

**Files to Remove Entirely:**
- `src/agent/brain.py` - Entire file
- `src/agent/autogen_agents.py` - Entire file (if `optimize_system()` removed)

**Methods to Remove:**
- `core.py`: 10+ methods (scheduler, commands, config saving)
- `data_processor.py`: 5-8 methods (legacy processing)
- `service.py`: 20+ endpoints + helper functions
- `presidential_service.py`: 3 deduplication functions

**Estimated Code Reduction:**
- **core.py**: ~500-800 lines (methods + scheduler code)
- **data_processor.py**: ~200-300 lines (legacy methods)
- **service.py**: ~1000-1500 lines (endpoints + helpers)
- **presidential_service.py**: ~100 lines (deduplication functions)
- **Total**: ~1800-2700 lines (~15-25% of codebase)

**Hardcoded Values in Unused Code:**
- ~20-30 hardcoded values in methods that will be REMOVED
- **DO NOT** create config for these - just REMOVE the code

---

## ✅ Action Plan (REVISED)

### Phase 1: Remove High-Confidence Unused Code

1. **Remove legacy processing methods from `data_processor.py`:**
   - Remove `process_data()` and all its hardcoded values
   - Remove `normalize_text()`, `is_similar_text()`, `parse_date()` if unused
   - Remove `load_raw_data()`, `save_processed_data()` if unused
   - **Result**: Remove ~200-300 lines + ~10 hardcoded values

2. **Remove scheduler code from `core.py`** (if scheduler unused):
   - Remove all scheduler methods
   - Remove scheduler thread management
   - Remove `_get_email_config_for_user()` if only used by scheduler
   - **Result**: Remove ~300-400 lines + hardcoded values

3. **Remove command execution from `core.py`** (if `/command` endpoint unused):
   - Remove `execute_command()`, `start()`, `stop()`, `update_location_classifications()`
   - **Result**: Remove ~100-200 lines

4. **Remove legacy deduplication functions:**
   - Remove from `service.py`: `deduplicate_sentiment_data()`, `normalize_text_for_dedup()`, `remove_similar_content()`
   - Remove from `presidential_service.py`: same functions
   - **Result**: Remove ~200-300 lines + ~5 hardcoded values

5. **Remove unused endpoints from `service.py`:**
   - Remove debug endpoints (`.env`, `.git`, etc.)
   - Remove duplicate endpoints (`/agent/test-cycle`, `/agent/trigger-run-parallel`)
   - Remove legacy endpoints (`/data/update`)
   - Remove React app serving
   - **Result**: Remove ~500-800 lines

6. **Remove entire unused files:**
   - Remove `src/agent/brain.py`
   - Remove `src/agent/autogen_agents.py` (if `optimize_system()` removed)
   - **Result**: Remove ~500-1000 lines

### Phase 2: Verify Medium-Confidence Items

7. **Verify scheduler usage:**
   - Check if scheduler is actually used
   - If not, remove all scheduler code

8. **Verify API endpoint usage:**
   - Check which endpoints are actually called
   - Remove unused endpoints

### Phase 3: Update Hardcoded Values Audit

9. **After removing unused code:**
   - Remove hardcoded values that were in unused code
   - Only configure hardcoded values in ACTIVE code paths

---

**Last Updated**: 2025-12-27 (REVISED)  
**Status**: Comprehensive audit - Ready for removal phase

