# Phase 3: Next Steps Prompt

## Context
Continue Phase 3: Code Deduplication & Consolidation. We've completed:
- ✅ Action Item 1.1: Removed duplicate `_run_task()` (80 lines)
- ✅ Action Items 4.1-4.3: Consolidated date parsing (~120 lines removed)
- ✅ Action Item 1.2: Removed duplicate text normalization (~30 lines)
- ✅ Action Item 1.3: Removed duplicate text similarity (~12 lines)
- ✅ Action Item 1.4: Refactored `remove_similar_content()` to use DeduplicationService
- ✅ Action Item 4.4: Moved type conversion utilities (~32 lines moved)
- ✅ Step 3.2: Consolidated config loading (replaced `core.py` `load_config()` with ConfigManager)
- ✅ Step 3.3: Consolidated path resolution (27 files updated to use PathManager)
- **Total progress**: ~274 lines of duplicate code removed/simplified/moved + centralized config/path management + enhanced consistency

## Current Status

### Phase 3 Progress Summary
- ✅ Step 3.0: Complete - All duplicate functions identified and cataloged
- ✅ Step 3.1: Complete - All 4 action items complete (~122 lines removed + consistency improvements)
  - ✅ Action Item 1.1: Removed duplicate `_run_task()` (80 lines)
  - ✅ Action Item 1.2: Removed duplicate text normalization (~30 lines)
  - ✅ Action Item 1.3: Removed duplicate text similarity (~12 lines)
  - ✅ Action Item 1.4: Refactored `remove_similar_content()` to use DeduplicationService
- ✅ Step 3.2: Complete - Consolidated config loading
- ✅ Step 3.3: Complete - Consolidated path resolution (27 files)
- ✅ Step 3.4: Complete - Consolidated duplicate functions (~152 lines)

## Next Steps (Recommended Order)

### ✅ Phase 3 Complete!

All Phase 3 action items are now complete:
- ✅ Step 3.1: All deduplication function consolidations complete
- ✅ Step 3.2: Config loading consolidated
- ✅ Step 3.3: Path resolution consolidated (27 files)
- ✅ Step 3.4: Date parsing and type conversion utilities consolidated

### Recommended: Move to Phase 4 or Phase 5

Since Phase 3 is complete, you can now proceed to:
- **Phase 4**: Remove Unused Code (cleanup) - See `cleanup/UNUSED_CODE_AUDIT_REVISED.md`
- **Phase 5**: Replace Hardcoded Values (move hardcoded Apify parameters, timeouts, etc. to ConfigManager) - See `cleanup/HARDCODED_VALUES_AUDIT.md`

---

## Key Reference Files

### Primary Documentation
- **`cleanup/CLEANUP_AND_REFACTORING_PLAN.md`** - Master plan for all phases (most comprehensive)
- **`cleanup/DUPLICATE_FUNCTIONS_AUDIT.md`** - Complete audit with detailed action items
- **`cleanup/PHASE_3_ACTION_ITEMS.md`** - Quick reference checklist
- **`cleanup/README.md`** - Progress tracking and overview

### Code Files Already Modified
- `src/utils/common.py` - ✅ Created (contains `parse_datetime()`, `safe_int()`, `safe_float()`)
- `src/agent/core.py` - ✅ Updated (uses ConfigManager, PathManager, DeduplicationService, common utils)
- `src/api/service.py` - ✅ Updated (uses `parse_datetime()`)
- `src/processing/data_processor.py` - ✅ Updated (uses PathManager, DeduplicationService, common utils)
- `src/api/presidential_service.py` - ✅ Updated (uses DeduplicationService)
- 27+ files - ✅ Updated to use PathManager

### Canonical Implementations to Use
- **Text normalization**: `src/utils/deduplication_service.py` → `DeduplicationService.normalize_text()`
- **Text similarity**: `src/utils/deduplication_service.py` → `DeduplicationService.is_similar_text()`
- **Date parsing**: `src/utils/common.py` → `parse_datetime()`
- **Type conversion**: `src/utils/common.py` → `safe_int()`, `safe_float()`
- **Path management**: `src/config/path_manager.py` → `PathManager()`
- **Config management**: `src/config/config_manager.py` → `ConfigManager()`

---

## Summary of Completed Work

### Code Deduplication Achievements
1. **Function Consolidation**: Removed ~274 lines of duplicate code
   - Duplicate `_run_task()` method (80 lines)
   - Duplicate text normalization/similarity functions (~42 lines)
   - Duplicate date parsing implementations (~120 lines simplified)
   - Type conversion utilities moved to common module (~32 lines)

2. **Path Consolidation**: 27 files updated
   - All major collector files now use PathManager
   - Core processing files use PathManager
   - API files use PathManager
   - Eliminated 30+ duplicate `Path(__file__).parent.parent.parent` patterns

3. **Config Consolidation**: Main duplicate removed
   - `core.py` `load_config()` now uses ConfigManager
   - Specialized configs use PathManager for path resolution

### Phase 3 Complete! ✅

All action items in Phase 3 are now complete:
- ✅ Step 3.1: All deduplication functions consolidated (including `remove_similar_content()` refactor)
- ✅ Step 3.2: Config loading consolidated
- ✅ Step 3.3: Path resolution consolidated
- ✅ Step 3.4: Date parsing and type conversion utilities consolidated

---

**Status**: Phase 3 - ✅ **COMPLETE**

**Latest Completion**: Step 3.1, Action Item 1.4 - Refactored `remove_similar_content()` to use `DeduplicationService.is_similar_text()` instead of word-based Jaccard similarity. This ensures consistency across the codebase and uses the canonical similarity check. The function now properly leverages the shared deduplication service.

