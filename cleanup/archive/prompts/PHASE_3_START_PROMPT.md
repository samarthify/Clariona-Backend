# Phase 3 Start Prompt

Copy and paste this prompt into a new chat to start Phase 3:

---

```
I need you to help me implement Phase 3 of a backend cleanup and refactoring project.

## Context

I have a Python FastAPI backend for a data collection, processing, and storage pipeline. Phase 1 (Analysis) and Phase 2 (Configuration System) are complete.

**Phase 2 Complete**:
- ✅ ConfigManager created with database backend support
- ✅ PathManager created for centralized path resolution
- ✅ 64 configuration values migrated to database
- ✅ All tests passing (21/21)

## Phase 3 Goal: Code Deduplication & Consolidation

Remove duplicate code patterns and consolidate shared functionality. Replace scattered implementations with centralized ConfigManager and PathManager.

## What I Need

Please read these key documents from the `cleanup/` folder:

1. **CLEANUP_AND_REFACTORING_PLAN.md** - Master plan, Phase 3 details (Steps 3.0-3.4)
2. **DUPLICATE_CODE_AUDIT.md** - All duplicate code patterns identified
3. **DUPLICATE_FUNCTIONS_AUDIT.md** ✅ - Comprehensive duplicate functions audit with detailed action items (COMPLETE)
4. **PHASE_3_ACTION_ITEMS.md** ✅ - Quick reference checklist for Phase 3 action items
5. **CONFIGURATION_MAP.md** - Current config loading patterns to replace
6. **PHASE_2_COMPLETE_STATUS.md** - What was built in Phase 2

## Phase 3 Steps (from plan)

### Step 3.0: Find and Catalog All Duplicate Functions ✅ COMPLETE
**Status**: ✅ **COMPLETE** - All duplicate functions identified and documented

**What was done**:
- ✅ Searched for duplicate function patterns (normalize_text, parse_date, load_config, etc.)
- ✅ Compared implementations to identify true duplicates
- ✅ Documented canonical versions and duplicates to remove
- ✅ Created comprehensive audit with 9 detailed action items

**Deliverables**:
- ✅ `DUPLICATE_FUNCTIONS_AUDIT.md` - Complete audit with detailed action items
- ✅ `PHASE_3_ACTION_ITEMS.md` - Quick reference checklist

**Findings**: 6 duplicate function groups, 14+ duplicate implementations, ~400-500 lines to remove

**Next**: Start with Action Item 1.1 (Remove duplicate `_run_task()`) - CRITICAL, 15 minutes

---

### Step 3.1: Consolidate Deduplication Logic
- Review all deduplication implementations
- Enhance `DeduplicationService` (make configurable via ConfigManager)
- Remove duplicate implementations
- Update all callers

### Step 3.2: Consolidate Config Loading
- Find all config loading mechanisms
- Replace all with ConfigManager
- Remove duplicate config loading code

### Step 3.3: Consolidate Path Resolution
- Find all `base_path` calculations (30+ instances)
- Replace all with PathManager
- Remove duplicate path code

### Step 3.4: Consolidate All Duplicate Functions (Enhanced)
- Create `src/utils/common.py` and other shared utility modules
- Move canonical functions to shared locations
- Remove ALL duplicate function implementations
- Update all imports and callers
- Verify no breaking changes

## Files to Review

Key files that likely have duplicates:
- `src/agent/core.py` - Config loading, path resolution
- `src/api/service.py` - Config loading, deduplication
- `src/api/presidential_service.py` - Deduplication
- `src/collectors/*.py` - Path resolution, config loading
- `src/processing/*.py` - Path resolution, config loading

## Expected Outcomes

- All config loading uses ConfigManager
- All path resolution uses PathManager
- Single deduplication implementation (DeduplicationService)
- All duplicate functions consolidated into shared utilities
- 500-600+ lines of duplicate code removed
- Single source of truth for all common operations

**IMPORTANT**: Step 3.0 is COMPLETE. Recommended execution order:
1. ✅ Step 3.0: Find and catalog all duplicate functions - COMPLETE
2. **Action Item 1.1**: Remove duplicate `_run_task()` (CRITICAL - 15 min) - START HERE!
3. **Action Item 4.1 + 4.2**: Create `common.py` and `parse_datetime()` (CRITICAL - 3-4 hours)
4. **Action Items 1.2-1.3**: Remove duplicate text normalization/similarity (HIGH - 2 hours)
5. **Action Item 4.3**: Replace all date parsing calls (HIGH - 2-3 hours)
6. **Step 3.3**: Consolidate path resolution (HIGH - 1 day, PathManager ready)
7. **Step 3.2**: Consolidate config loading (MEDIUM - 1 day, ConfigManager ready)
8. **Action Items 1.4, 4.4**: Optional enhancements (MEDIUM - 3-4 hours)

**Reference**: See `DUPLICATE_FUNCTIONS_AUDIT.md` for complete detailed action items with step-by-step instructions.
```

