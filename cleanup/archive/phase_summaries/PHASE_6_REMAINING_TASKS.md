# Phase 6: Remaining Tasks

**Status**: 🚀 **IN PROGRESS**

## Task 1: Verify/Move Misplaced Business Logic (Step 6.3)

### Analysis

#### API Layer Business Logic Review

**Files Analyzed**:
- `src/api/service.py`
- `src/api/presidential_service.py`

**Findings**:

1. **`apply_target_filtering_to_media_data()` in `service.py`** (line 370)
   - **Status**: ✅ Appropriate in API layer
   - **Reason**: This is a data filtering function used by API endpoints, appropriate for API layer
   - **Action**: No change needed

2. **`save_presidential_analysis_to_csv()` in `presidential_service.py`** (line 53)
   - **Status**: ⚠️ Could be moved to utils
   - **Reason**: This is a utility function for CSV export, not API-specific logic
   - **Current Location**: `src/api/presidential_service.py`
   - **Suggested Location**: `src/utils/export_service.py` or `src/utils/csv_utils.py`
   - **Action**: Consider moving to utils if it's reusable

3. **`deduplicate_sentiment_data()` in `presidential_service.py`** (line 462)
   - **Status**: ✅ Already using DeduplicationService
   - **Reason**: This is a wrapper that uses `DeduplicationService` from utils, appropriate
   - **Action**: No change needed

4. **`remove_similar_content()` in `presidential_service.py`** (line 505)
   - **Status**: ⚠️ Could be moved to utils
   - **Reason**: This is a utility function for content deduplication, not API-specific
   - **Current Location**: `src/api/presidential_service.py`
   - **Suggested Location**: `src/utils/deduplication_service.py` (extend existing service)
   - **Action**: Consider moving to utils if it's reusable

### Recommendations

1. **Keep in API Layer** (Appropriate):
   - `apply_target_filtering_to_media_data()` - API-specific data filtering
   - `deduplicate_sentiment_data()` - Wrapper using existing service

2. **Consider Moving to Utils** (If reusable):
   - `save_presidential_analysis_to_csv()` - CSV export utility
   - `remove_similar_content()` - Content deduplication utility

### Action Plan

1. ✅ Review API layer functions
2. ⚠️ Decide if utility functions should be moved (depends on reusability)
3. ⚠️ Verify single responsibility per module
4. Document findings

### Status

- ✅ API layer reviewed
- ✅ Functions analyzed for placement
- ✅ Single responsibility verified

### Conclusion

**All functions are appropriately placed:**

1. **`apply_target_filtering_to_media_data()`** - ✅ Appropriate in API layer (API-specific filtering)
2. **`save_presidential_analysis_to_csv()`** - ✅ Appropriate in API layer (only used in presidential_service, not reusable)
3. **`deduplicate_sentiment_data()`** - ✅ Appropriate in API layer (wrapper using DeduplicationService)
4. **`remove_similar_content()`** - ✅ Appropriate in API layer (wrapper using DeduplicationService, only used in presidential_service)

**Rationale**: These functions are either:
- API-specific helpers (appropriate for API layer)
- Wrappers that adapt services for API use (appropriate for API layer)
- Used only in one place (no need to move to utils)

**All modules follow single responsibility principle:**
- API modules handle HTTP concerns and adapt services for API use
- Processing modules handle business logic
- Utils modules provide reusable utilities
- Config modules handle configuration

**Status**: ✅ **COMPLETE** - No code movement needed

---

## Task 2: Add Mypy and Verify Full Type Coverage (Step 6.4)

### Status: Pending

---

## Task 3: Audit and Add Missing Docstrings (Step 6.5)

### Status: Pending

