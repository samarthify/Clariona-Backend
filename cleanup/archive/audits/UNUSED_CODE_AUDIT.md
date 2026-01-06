# Unused Code Audit

**Created**: 2025-12-27  
**Purpose**: Comprehensive audit of unused/legacy code with confidence levels  
**Status**: Phase 1, Step 1.2 - In Progress  
**Based on**: EXECUTION_FLOW_MAP.md, UNUSED_CODE_ANALYSIS.md

---

## 📋 Audit Methodology

### Confidence Levels:
- 🔴 **HIGH**: Confirmed unused, safe to remove - Verified not in execution flow
- 🟡 **MEDIUM**: Likely unused, needs verification - Not in main flow, may be used elsewhere
- 🟢 **LOW**: Might be used, investigate further - Used in endpoints that may or may not be accessed

### Verification Process:
1. Cross-referenced with EXECUTION_FLOW_MAP.md (main execution path)
2. Searched codebase for references
3. Checked if used in API endpoints
4. Verified if used in tests

---

## 🔴 HIGH CONFIDENCE - Safe to Remove

### src/agent/core.py

#### 1. `run()` method
- **Location**: Line ~2995 (in `__main__` block, or deprecated method)
- **Status**: DEPRECATED
- **Evidence**: 
  - Not in execution flow map
  - Logs warning "Main loop is deprecated"
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 2. `process_data()` method
- **Location**: Line ~1260 (if exists)
- **Status**: LEGACY (Sequential processing)
- **Evidence**:
  - Not in execution flow map
  - Replaced by `_run_sentiment_batch_update_parallel()` and `_run_location_batch_update_parallel()`
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 3. `update_metrics()` method
- **Location**: Line ~1962 (if exists)
- **Status**: UNUSED
- **Evidence**:
  - Not in execution flow map
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 4. `optimize_system()` method
- **Location**: Line ~2003 (if exists)
- **Status**: UNUSED
- **Evidence**:
  - Not in execution flow map
  - Uses AutogenAgentSystem (which is also unused)
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 5. `save_config()` method
- **Location**: Line ~2086 (if exists)
- **Status**: DUPLICATE
- **Evidence**:
  - Not in execution flow map
  - Duplicate of `_save_config()` which is used
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 6. `cleanup_old_data()` method
- **Location**: Line ~2096 (if exists)
- **Status**: UNUSED
- **Evidence**:
  - Not in execution flow map
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 7. `_run_collect_and_process()` method
- **Location**: Line ~1954 (if exists)
- **Status**: REDUNDANT WRAPPER
- **Evidence**:
  - Not in execution flow map
  - Just calls `run_single_cycle()` which is a wrapper for `run_single_cycle_parallel()`
  - No direct calls found
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### 8. Unused Imports

##### `AgentBrain` import
- **Location**: Line ~34 (if exists)
- **Status**: NEVER INITIALIZED/USED
- **Evidence**:
  - Not in execution flow map
  - No initialization found
  - No usage found
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE import**

##### `AutogenAgentSystem` import
- **Location**: Line ~35 (if exists)
- **Status**: Only used in `optimize_system()` which is unused
- **Evidence**:
  - Not in execution flow map
  - Only referenced in unused `optimize_system()` method
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE import**

##### `schedule` import
- **Status**: Used in deprecated `run()` method
- **Evidence**:
  - Not in execution flow map
  - Only used in deprecated code
- **Confidence**: 🔴 **HIGH** (if `run()` is removed)
- **Action**: **REMOVE import** (after removing `run()`)

##### `signal` import
- **Status**: Used in deprecated `run()` method
- **Evidence**:
  - Not in execution flow map
  - Only used in deprecated code
- **Confidence**: 🔴 **HIGH** (if `run()` is removed)
- **Action**: **REMOVE import** (after removing `run()`)

##### `inspect` import
- **Status**: Usage unclear
- **Evidence**:
  - Not in execution flow map
  - Need to verify if used elsewhere
- **Confidence**: 🟡 **MEDIUM** (need to verify)
- **Action**: **VERIFY and REMOVE if unused**

---

### src/api/service.py

#### Legacy Deduplication Functions

##### 1. `deduplicate_sentiment_data()` function
- **Location**: Line ~355
- **Status**: LEGACY
- **Evidence**:
  - Not in execution flow map
  - Replaced by `DeduplicationService`
  - No calls found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

##### 2. `normalize_text_for_dedup()` function
- **Location**: Line ~393
- **Status**: LEGACY
- **Evidence**:
  - Not in execution flow map
  - Used by `deduplicate_sentiment_data()` which is unused
  - No other calls found
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

##### 3. `remove_similar_content()` function
- **Location**: Line ~412
- **Status**: LEGACY
- **Evidence**:
  - Not in execution flow map
  - Old deduplication method
  - No calls found
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

##### 4. `remove_similar_content_optimized()` function
- **Location**: Line ~480
- **Status**: LEGACY
- **Evidence**:
  - Not in execution flow map
  - Old deduplication method
  - No calls found
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

#### Debug/Test Endpoints

##### 5. `/debug-auth` endpoint
- **Location**: Line ~535
- **Status**: DEBUG ENDPOINT
- **Evidence**:
  - Not in execution flow map
  - Debug endpoint, not for production
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE** (or move to debug-only mode)

##### 6. `/debug/*` endpoints
- **Location**: Lines ~4979, 5008, 5022
- **Status**: DEBUG ENDPOINTS
- **Evidence**:
  - Not in execution flow map
  - Debug endpoints
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE** (or move to debug-only mode)

##### 7. `/api/test` endpoint
- **Location**: Line ~4997
- **Status**: TEST ENDPOINT
- **Evidence**:
  - Not in execution flow map
  - Test endpoint
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE**

---

### src/agent/brain.py

#### Entire File
- **Status**: NEVER USED
- **Evidence**:
  - `AgentBrain` class imported but never initialized
  - Not in execution flow map
  - No usage found in codebase
- **Confidence**: 🔴 **HIGH**
- **Action**: **REMOVE entire file** (after removing import)

---

### src/agent/autogen_agents.py

#### Entire File (Potentially)
- **Status**: ONLY USED IN UNUSED METHOD
- **Evidence**:
  - `AutogenAgentSystem` only used in `optimize_system()` which is unused
  - Not in execution flow map
- **Confidence**: 🔴 **HIGH** (if `optimize_system()` is removed)
- **Action**: **REMOVE entire file** (after removing `optimize_system()` and import)

---

### src/collectors/run_collectors.py

#### Legacy Collector System

##### `run_legacy_collectors()` function
- **Location**: Line ~82
- **Status**: LEGACY
- **Evidence**:
  - Not in execution flow map (main flow uses configurable collectors)
  - Fallback only, likely never called
- **Confidence**: 🟡 **MEDIUM** (fallback, may be safety net)
- **Action**: **VERIFY if fallback is needed, then REMOVE**

---

## 🟡 MEDIUM CONFIDENCE - Needs Verification

### src/agent/core.py

#### 1. `start()` method
- **Location**: Line ~1234
- **Status**: USED VIA COMMAND ENDPOINT
- **Evidence**:
  - Not in main execution flow
  - Called from `execute_command()` when command is "start"
  - Depends on `/command` endpoint usage
- **Confidence**: 🟡 **MEDIUM**
- **Action**: **VERIFY** if `/command` endpoint is used, then decide

#### 2. `stop()` method
- **Location**: Line ~1245
- **Status**: USED VIA COMMAND ENDPOINT
- **Evidence**:
  - Not in main execution flow
  - Called from `execute_command()` when command is "stop"
  - Depends on `/command` endpoint usage
- **Confidence**: 🟡 **MEDIUM**
- **Action**: **VERIFY** if `/command` endpoint is used, then decide

#### 3. `update_location_classifications()` method
- **Location**: Line ~2252 (if exists)
- **Status**: USED VIA COMMAND ENDPOINT
- **Evidence**:
  - Not in main execution flow
  - Called from `execute_command()` when command is "update_location_classifications"
  - Depends on `/command` endpoint usage
- **Confidence**: 🟡 **MEDIUM**
- **Action**: **VERIFY** if `/command` endpoint is used, then decide

#### 4. `execute_command()` method
- **Status**: USED BY API ENDPOINT
- **Evidence**:
  - Called from `/command` endpoint
  - Not in main execution flow
  - Depends on endpoint usage
- **Confidence**: 🟡 **MEDIUM**
- **Action**: **VERIFY** if `/command` endpoint is used

---

### src/api/service.py

#### Potentially Unused Endpoints

**Note**: Since frontend reads directly from database (not via API), most endpoints may be unused. Need to verify:

1. `/status` endpoint
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

2. `/command` endpoint
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

3. `/data/update` endpoint
   - **Confidence**: 🟡 **MEDIUM** (legacy, may be replaced)
   - **Action**: VERIFY if still needed

4. `/latest-data` endpoint
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

5. `/cache/*` endpoints
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

6. `/comparison-data` endpoint
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

7. `/metrics` endpoint
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

8. `/config` endpoints
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

9. `/email/*` endpoints
   - **Confidence**: 🟡 **MEDIUM**
   - **Action**: VERIFY usage

10. `/agent/trigger-run-parallel` endpoint
    - **Confidence**: 🟡 **MEDIUM** (duplicate of `/agent/test-cycle-no-auth`)
    - **Action**: VERIFY if both needed

11. `/agent/automatic-scheduling/*` endpoints
    - **Confidence**: 🟡 **MEDIUM** (run_cycles.sh doesn't use them)
    - **Action**: VERIFY usage

12. `/agent/test-cycle` endpoint
    - **Confidence**: 🟡 **MEDIUM** (duplicate of `/agent/test-cycle-no-auth`)
    - **Action**: VERIFY if both needed

13. `/user/register` endpoint
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY usage

14. `/media-sources/*` endpoints
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY usage

15. `/sentiment-feedback` endpoint
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY usage

16. `/policy-impact` endpoint
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY usage

17. `/showcase/add-data` endpoint
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY usage

18. React app serving endpoints
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY if backend serves frontend

19. WebSocket functionality
    - **Confidence**: 🟡 **MEDIUM**
    - **Action**: VERIFY usage

---

### Helper Functions

#### `get_latest_run_timestamp()` function (service.py)
- **Location**: Line ~346
- **Confidence**: 🟡 **MEDIUM**
- **Action**: **VERIFY** usage

#### `extract_policy_name()` function (service.py)
- **Location**: Line ~4778
- **Used by**: `/policy-impact` endpoint
- **Confidence**: 🟡 **MEDIUM** (depends on endpoint usage)
- **Action**: **VERIFY** if endpoint is used

#### `extract_headline_from_text()` function (service.py)
- **Location**: Line ~4827
- **Used by**: `/showcase/add-data` endpoint
- **Confidence**: 🟡 **MEDIUM** (depends on endpoint usage)
- **Action**: **VERIFY** if endpoint is used

---

## 🟢 LOW CONFIDENCE - Keep for Now

### Admin/Configuration Endpoints

These may be used by admins or configuration tools:

1. `/admin/*` endpoints
   - **Confidence**: 🟢 **LOW** (may be used by admins)
   - **Action**: **KEEP** for now, verify later

2. Config management endpoints
   - **Confidence**: 🟢 **LOW** (may be used for configuration)
   - **Action**: **KEEP** for now, verify later

---

## 📊 Summary Statistics

### High Confidence Removals:
- **Methods**: 7 from `core.py`
- **Imports**: 4-5 from `core.py`
- **Functions**: 4 from `service.py`
- **Endpoints**: 3-4 debug/test endpoints
- **Files**: 2 (`brain.py`, potentially `autogen_agents.py`)

### Estimated Code Reduction:
- **core.py**: ~200-300 lines (methods + imports)
- **service.py**: ~200-400 lines (functions + endpoints)
- **Total**: ~400-700 lines (~5-10% of codebase)

---

## ✅ Verification Checklist

Before removing any code:

- [ ] Create backup branch
- [ ] Run tests to establish baseline
- [ ] Remove high-confidence items first
- [ ] Verify tests still pass
- [ ] Check logs for any errors
- [ ] Test main execution flow (`run_cycles.sh`)
- [ ] Document removed items
- [ ] Update documentation

---

## 📝 Removal Priority

### Phase 1 (Safe Removals - High Confidence):
1. Remove unused imports from `core.py`
2. Remove deprecated `run()` method
3. Remove unused methods: `update_metrics()`, `optimize_system()`, `save_config()`, `cleanup_old_data()`, `process_data()`
4. Remove `_run_collect_and_process()` wrapper
5. Remove `brain.py` file (after removing import)
6. Remove `autogen_agents.py` file (after removing `optimize_system()`)
7. Remove legacy deduplication functions from `service.py`
8. Remove debug/test endpoints from `service.py`

### Phase 2 (After Verification - Medium Confidence):
1. Verify `/command` endpoint usage
2. If unused, remove `start()`, `stop()`, `update_location_classifications()`, `execute_command()`
3. Verify other API endpoint usage
4. Remove unused endpoints after verification

---

**Last Updated**: 2025-12-27  
**Status**: Initial audit - needs line number verification and final confirmation






