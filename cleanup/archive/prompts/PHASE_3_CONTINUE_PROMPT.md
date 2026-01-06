# Phase 3 Continuation Prompt

## Context
Continue Phase 3: Code Deduplication & Consolidation. We've completed:
- ✅ Action Item 1.1: Removed duplicate `_run_task()` (80 lines)
- ✅ Action Items 4.1-4.3: Consolidated date parsing (~120 lines removed)
- ✅ Action Item 1.2: Removed duplicate text normalization (~30 lines)
- ✅ Action Item 1.3: Removed duplicate text similarity (~12 lines)
- ✅ Action Item 4.4: Moved type conversion utilities (~32 lines moved)
- ✅ Step 3.2: Consolidated config loading (replaced `core.py` `load_config()` with ConfigManager)
- ✅ Step 3.3: Consolidated path resolution (27 files updated to use PathManager)
- **Total progress**: ~274 lines of duplicate code removed/simplified/moved + centralized config/path management

## Next Steps (Recommended Order)

### Priority 1: Action Item 1.4 - Refactor `remove_similar_content()` (Optional Enhancement)
**Priority**: 🟡 MEDIUM (enhancement, not critical)  
**Time**: 2-3 hours  
**Files to modify**:
- `src/api/presidential_service.py` - Refactor `remove_similar_content()` to use `DeduplicationService` internally

**Reference**: See `cleanup/DUPLICATE_FUNCTIONS_AUDIT.md` Action Item 1.4 for detailed tasks.

**Note**: This is optional - can be done later if time permits.

---

---

### Priority 2: Step 3.2 - Consolidate Config Loading ✅ **COMPLETE**
**Status**: ✅ **COMPLETE**  
**Files Updated**:
- `src/agent/core.py` - Replaced `load_config()` method with ConfigManager
- Specialized config loaders already use PathManager for paths (from Step 3.3)

**Result**: Main duplicate config loading mechanism (`core.py`'s `load_config()`) now uses centralized ConfigManager. Specialized configs (target_configs.json, llm_config.json, etc.) are domain-specific and appropriately handled separately.

---

### Priority 3: Step 3.3 - Consolidate Path Resolution ✅ **COMPLETE**
**Status**: ✅ **COMPLETE**  
**Files Updated**: 27 files
- Core files: `core.py`, `data_processor.py`, `presidential_data_processor.py`
- API files: `database.py`, `middlewares.py`, `auth.py`
- All collector files (17 files): Instagram, Twitter, Facebook, TikTok, News, YouTube, RSS, Radio collectors
- Processing files: `presidential_sentiment_analyzer.py`
- Collector utilities: `target_config_manager.py`, `rss_feed_health_monitor.py`

**Remaining**: ~12 files (mostly utility examples or intentional fallback code)

---

---

## Key Reference Files

### Primary Documentation
- **`cleanup/DUPLICATE_FUNCTIONS_AUDIT.md`** - Complete audit with detailed action items (most important)
- **`cleanup/PHASE_3_ACTION_ITEMS.md`** - Quick reference checklist
- **`cleanup/README.md`** - Progress tracking and overview
- **`cleanup/CLEANUP_AND_REFACTORING_PLAN.md`** - Master plan for all phases

### Code Files Already Modified
- `src/utils/common.py` - ✅ Created (contains `parse_datetime()`)
- `src/agent/core.py` - ✅ Updated (`_parse_date_string()` simplified)
- `src/api/service.py` - ✅ Updated (local `parse_datetime()` removed)
- `src/processing/data_processor.py` - ✅ Updated (`parse_date()` simplified)

### Canonical Implementations to Use
- **Text normalization**: `src/utils/deduplication_service.py` → `DeduplicationService.normalize_text()`
- **Text similarity**: `src/utils/deduplication_service.py` → `DeduplicationService.is_similar_text()`
- **Date parsing**: `src/utils/common.py` → `parse_datetime()`
- **Type conversion**: `src/utils/common.py` → `safe_int()`, `safe_float()`

---
**Status**: Phase 3 - IN PROGRESS (Step 3.1: 3/4 complete, Step 3.2: ✅ COMPLETE, Step 3.3: ✅ COMPLETE, Step 3.4: ✅ COMPLETE)

**Latest Completion**: Step 3.2 - Consolidated config loading by replacing `core.py`'s `load_config()` method with ConfigManager. The main duplicate config loading mechanism is now using the centralized configuration system. Specialized configs remain domain-specific and use PathManager for path resolution.

