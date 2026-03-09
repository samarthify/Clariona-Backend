# Velocity Priority Fixes - Summary

**Date**: February 28, 2026  
**Status**: ✅ Complete and Tested

---

## What Was Done

Based on the velocity priority audit, we identified and fixed two critical issues in the velocity calculation system.

---

## 1. Zero Velocity Bug Fix ✅

### The Problem
When an error occurred during velocity calculation, the system was setting `velocity_score = 0.0`. However, according to the velocity scoring formula, 0% velocity should map to 50.0 (neutral), not 0.0 (complete decline).

### The Fix
```python
# Before (WRONG)
issue.velocity_score = issue.velocity_score or 0.0  # ❌

# After (CORRECT)
issue.velocity_score = issue.velocity_score or 50.0  # ✅
```

### Why This Matters
- **0.0** = -100% velocity (complete decline, lowest priority)
- **50.0** = 0% velocity (stable, neutral priority)

Issues with calculation errors were being incorrectly treated as severely declining, lowering their priority scores artificially.

---

## 2. Timestamp Consistency Validation ✅

### The Problem
The velocity calculation uses fallback logic for timestamps (published_at → published_date → date → created_at), but there was no visibility into:
- Which timestamp sources are being used
- Whether mixing sources is affecting accuracy
- How many mentions are missing timestamps

### The Fix
Added comprehensive tracking and validation:

1. **Tracks every timestamp source used**
   ```python
   timestamp_sources = {
       'published_at': 0,      # Primary source
       'published_date': 0,    # Fallback 1
       'date': 0,              # Fallback 2
       'created_at': 0,        # Fallback 3
       'missing': 0            # No timestamp
   }
   ```

2. **Warns when >20% of mentions use fallback timestamps**
   ```
   WARNING: Issue xyz: Mixed timestamp sources detected.
   published_at=50, published_date=20, date=15, created_at=10, missing=5.
   This may affect velocity accuracy.
   ```

3. **Warns when mentions have no timestamps**
   ```
   WARNING: Issue xyz: 12 mentions have no timestamp.
   These are excluded from velocity calculation.
   ```

### Why This Matters
- Provides data quality visibility
- Helps identify issues with inaccurate velocity calculations
- Enables proactive data cleaning

---

## Test Results ✅

All 6 tests pass:

```bash
tests/test_velocity_fixes.py::TestVelocityFixes::test_zero_velocity_error_fallback PASSED
tests/test_velocity_fixes.py::TestVelocityFixes::test_zero_velocity_score_calculation PASSED
tests/test_velocity_fixes.py::TestVelocityFixes::test_timestamp_consistency_validation PASSED
tests/test_velocity_fixes.py::TestVelocityFixes::test_velocity_scores_for_various_percentages PASSED
tests/test_velocity_fixes.py::TestVelocityFixes::test_timestamp_source_tracking PASSED
tests/test_velocity_fixes.py::TestVelocityFormulaConsistency::test_formula_matches_priority_calculator PASSED

======================== 6 passed, 2 warnings in 19.00s ========================
```

---

## Files Changed

### Production Code
- **`src/processing/issue_detection_engine.py`**
  - Fixed zero velocity bug (line 2102)
  - Added timestamp tracking (lines 1978-2009)
  - Added validation warnings (lines 2063-2086)

### Documentation
- **`docs/VELOCITY_PRIORITY_AUDIT.md`** - Comprehensive audit report
- **`docs/VELOCITY_FIXES.md`** - Detailed fix documentation
- **`docs/VELOCITY_FIXES_SUMMARY.md`** - This summary (quick reference)

### Tests
- **`tests/test_velocity_fixes.py`** - Complete test suite (6 test cases)

---

## Impact

### ✅ Benefits
1. **More accurate priority scores** - Errors default to neutral, not decline
2. **Better data quality visibility** - Warnings highlight timestamp inconsistencies
3. **Improved debugging** - Clear logs for troubleshooting velocity issues
4. **Backward compatible** - No breaking changes, existing data unaffected
5. **Negligible performance impact** - O(n) tracking, only logs when thresholds exceeded

### 📊 What to Monitor

After deployment, monitor:

1. **Warning frequency**:
   ```bash
   grep "Mixed timestamp sources" /path/to/logs/*.log | wc -l
   grep "mentions have no timestamp" /path/to/logs/*.log | wc -l
   ```

2. **Velocity score distribution**:
   ```sql
   SELECT 
       COUNT(*) as total,
       COUNT(CASE WHEN velocity_score = 50.0 THEN 1 END) as neutral,
       COUNT(CASE WHEN velocity_score > 50.0 THEN 1 END) as growing,
       COUNT(CASE WHEN velocity_score < 50.0 THEN 1 END) as declining
   FROM topic_issues
   WHERE is_archived = false;
   ```

---

## Quick Reference

### Velocity Score Formula
```
velocity_percent >= 100%  →  velocity_score = 100 (max)
velocity_percent = 50%    →  velocity_score = 75
velocity_percent = 0%     →  velocity_score = 50 (neutral) ✅ FIXED
velocity_percent = -50%   →  velocity_score = 25
velocity_percent = -100%  →  velocity_score = 0 (min)
```

### Priority Score Formula
```
priority_score = 
    0.4 × sentiment_score +
    0.3 × volume_score +
    0.2 × time_score +
    0.1 × velocity_score  ← Uses velocity_score (0-100)
```

### Timestamp Fallback Order
```
1. published_at      (primary - actual publication time)
2. published_date    (fallback 1)
3. date              (fallback 2)
4. created_at        (fallback 3 - ingestion time)
5. None              (excluded from calculation)
```

---

## Next Steps (Optional Enhancements)

From the audit, consider these future improvements:

### High Priority
- [ ] Add adaptive time windows (breaking vs sustained issues)
- [ ] Improve new issue velocity scoring (replace 1000% cap)

### Medium Priority
- [ ] Add velocity trend analysis (acceleration/deceleration)
- [ ] Store historical velocity in JSONB array

### Research
- [ ] Analyze correlation between velocity and other priority components
- [ ] Test multiplicative velocity boost (instead of additive)

---

## Conclusion

✅ **Both fixes are implemented, tested, and ready for production.**

The velocity calculation system now:
1. Correctly handles error cases with neutral scores
2. Provides visibility into timestamp data quality
3. Has comprehensive test coverage
4. Is fully backward compatible

**No deployment blockers. Safe to merge and deploy.**

---

## Related Documents

- **Full Audit**: `docs/VELOCITY_PRIORITY_AUDIT.md` (comprehensive analysis)
- **Fix Details**: `docs/VELOCITY_FIXES.md` (implementation details)
- **Tests**: `tests/test_velocity_fixes.py` (test suite)
- **Implementation**: `src/processing/issue_detection_engine.py` (code changes)

---

**Questions or Issues?** Review the full audit report or test suite for details.
