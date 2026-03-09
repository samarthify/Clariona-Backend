# Velocity Calculation Fixes

**Date**: February 28, 2026  
**Issue**: Zero velocity bug + Missing timestamp consistency validation  
**Status**: ✅ Fixed

---

## Summary of Changes

This document describes the fixes applied to the velocity calculation system based on the audit findings in `VELOCITY_PRIORITY_AUDIT.md`.

---

## Fix 1: Zero Velocity Score Bug

### Problem

**Location**: `src/processing/issue_detection_engine.py`, lines 2056-2057

**Issue**: When an error occurred during velocity calculation, the fallback code set `velocity_score = 0.0`:

```python
# OLD CODE (INCORRECT)
except Exception as e:
    logger.warning(f"Error calculating volume/velocity for issue {issue.id}: {e}")
    issue.velocity_percent = issue.velocity_percent or 0.0
    issue.velocity_score = issue.velocity_score or 0.0  # ❌ WRONG!
```

**Why This Was Wrong**:

According to the velocity scoring formula:
```
velocity_percent = 0% → velocity_score = 50.0 (neutral)
```

But the fallback code was setting `velocity_score = 0.0`, which corresponds to -100% velocity (complete decline), not 0% velocity (stable).

**Impact**:
- Issues with calculation errors would appear to be in severe decline
- Priority scores would be artificially lowered
- Incorrect lifecycle state transitions

### Solution

Changed the fallback to use `50.0` (neutral score) instead of `0.0`:

```python
# NEW CODE (CORRECT)
except Exception as e:
    logger.warning(f"Error calculating volume/velocity for issue {issue.id}: {e}")
    # Set defaults on error - use neutral scores, not zero
    issue.velocity_percent = issue.velocity_percent or 0.0
    # Fixed: Use neutral score (50.0) for zero velocity, not 0.0
    # This matches the formula: 0% velocity → 50.0 score (neutral)
    issue.velocity_score = issue.velocity_score or 50.0  # ✅ CORRECT!
```

**Result**: Errors now correctly default to neutral velocity, not severe decline.

---

## Fix 2: Timestamp Consistency Validation

### Problem

**Location**: `src/processing/issue_detection_engine.py`, lines 1978-2010

**Issue**: The velocity calculation uses fallback logic for timestamps:
```python
# OLD CODE (NO VALIDATION)
if mention.published_at:
    mention_time = mention.published_at
elif mention.published_date:
    mention_time = mention.published_date
elif mention.date:
    mention_time = mention.date
elif mention.created_at:
    mention_time = mention.created_at
```

**Why This Was Problematic**:
- No visibility into which timestamp sources are being used
- Mixing different timestamp sources (e.g., `published_at` vs `created_at`) could lead to inaccurate velocity calculations
- No warning when mentions are missing timestamps entirely

**Example Risk**:
```
Issue A has mentions from mixed sources:
- 50 mentions with published_at (actual publication time)
- 50 mentions with created_at (ingestion time, could be days later)

This mixing could show false velocity trends:
- Actual velocity: +20%
- Calculated velocity: +80% (due to timestamp skew)
```

### Solution

Added comprehensive timestamp source tracking and validation:

```python
# NEW CODE (WITH VALIDATION)

# Track timestamp source statistics for validation
timestamp_sources = {
    'published_at': 0,
    'published_date': 0,
    'date': 0,
    'created_at': 0,
    'missing': 0
}

for mention in mentions:
    mention_time = None
    timestamp_source = None
    
    if mention.published_at:
        mention_time = mention.published_at
        timestamp_source = 'published_at'
    elif mention.published_date:
        mention_time = mention.published_date
        timestamp_source = 'published_date'
    elif mention.date:
        mention_time = mention.date
        timestamp_source = 'date'
    elif mention.created_at:
        mention_time = mention.created_at
        timestamp_source = 'created_at'
    
    if not mention_time:
        timestamp_sources['missing'] += 1
        continue
    
    timestamp_sources[timestamp_source] += 1
    
    # ... rest of calculation ...

# After calculation, validate timestamp consistency
total_with_timestamps = sum(timestamp_sources[k] for k in ['published_at', 'published_date', 'date', 'created_at'])
if total_with_timestamps > 0:
    primary_source_ratio = timestamp_sources['published_at'] / total_with_timestamps
    fallback_ratio = (timestamp_sources['published_date'] + timestamp_sources['date'] + timestamp_sources['created_at']) / total_with_timestamps
    
    # Warn if using mixed timestamp sources (>20% fallback)
    if fallback_ratio > 0.2:
        logger.warning(
            f"Issue {issue.issue_slug}: Mixed timestamp sources detected. "
            f"published_at={timestamp_sources['published_at']}, "
            f"published_date={timestamp_sources['published_date']}, "
            f"date={timestamp_sources['date']}, "
            f"created_at={timestamp_sources['created_at']}, "
            f"missing={timestamp_sources['missing']}. "
            f"This may affect velocity accuracy."
        )
    
    # Warn if any timestamps are missing
    if timestamp_sources['missing'] > 0:
        logger.warning(
            f"Issue {issue.issue_slug}: {timestamp_sources['missing']} mentions have no timestamp. "
            f"These are excluded from velocity calculation."
        )
```

### What This Does

1. **Tracks every timestamp source used**
   - Counts how many mentions use `published_at` (primary)
   - Counts how many use fallback sources
   - Counts how many have no timestamp at all

2. **Warns when timestamp sources are mixed** (>20% fallback)
   - Example output:
     ```
     WARNING: Issue government-policy-criticism-123: Mixed timestamp sources detected.
     published_at=50, published_date=20, date=15, created_at=10, missing=5.
     This may affect velocity accuracy.
     ```

3. **Warns when timestamps are missing**
   - Example output:
     ```
     WARNING: Issue health-care-issues-456: 12 mentions have no timestamp.
     These are excluded from velocity calculation.
     ```

4. **Helps identify data quality issues**
   - Operations teams can see which issues have inconsistent data
   - Can prioritize data cleaning efforts based on warnings
   - Provides audit trail for velocity accuracy

---

## Testing

### Test File Created

**Location**: `tests/test_velocity_fixes.py`

**Test Coverage**:

1. ✅ `test_zero_velocity_error_fallback()` - Verifies error fallback uses 50.0
2. ✅ `test_zero_velocity_score_calculation()` - Tests 0% → 50.0 mapping
3. ✅ `test_timestamp_consistency_validation()` - Tests warning logs
4. ✅ `test_velocity_scores_for_various_percentages()` - Tests formula correctness
5. ✅ `test_timestamp_source_tracking()` - Tests tracking logic
6. ✅ `test_formula_matches_priority_calculator()` - Tests consistency

### Running Tests

```bash
# Run all velocity tests
pytest tests/test_velocity_fixes.py -v

# Run with coverage
pytest tests/test_velocity_fixes.py --cov=src.processing.issue_detection_engine --cov-report=html

# Run specific test
pytest tests/test_velocity_fixes.py::TestVelocityFixes::test_zero_velocity_error_fallback -v
```

---

## Verification Checklist

- [x] **Code changes made**
  - [x] Fixed zero velocity score bug (line 2102)
  - [x] Added timestamp source tracking (lines 1978-2009)
  - [x] Added timestamp validation warnings (lines 2063-2086)

- [x] **Documentation updated**
  - [x] Created `VELOCITY_PRIORITY_AUDIT.md` (comprehensive audit)
  - [x] Created `VELOCITY_FIXES.md` (this document)

- [x] **Tests created**
  - [x] Created `tests/test_velocity_fixes.py`
  - [x] Added 6 test cases covering both fixes

- [x] **No linter errors**
  - [x] Verified with ReadLints tool

---

## Impact Assessment

### Positive Impact

1. **More accurate priority scores**
   - Errors now default to neutral (50.0) instead of severe decline (0.0)
   - Issues won't be incorrectly de-prioritized due to calculation errors

2. **Better data quality visibility**
   - Teams can now see when timestamp sources are mixed
   - Can identify and fix data quality issues proactively
   - Audit trail for velocity accuracy

3. **Improved debugging**
   - Clear warnings when velocity calculations may be inaccurate
   - Easier to diagnose issues with velocity calculations

### Backward Compatibility

✅ **Fully backward compatible**
- No changes to database schema
- No changes to API contracts
- No changes to calculation formulas (only error handling)
- Existing issues will continue to work normally

### Performance Impact

✅ **Negligible performance impact**
- Timestamp tracking: O(n) where n = number of mentions per issue
- Validation checks: O(1) after counting
- Extra logging: Only when thresholds are exceeded

---

## Monitoring Recommendations

### After Deployment

1. **Monitor warning logs** for timestamp consistency issues:
   ```bash
   # Check for mixed timestamp warnings
   grep "Mixed timestamp sources detected" /path/to/logs/*.log | wc -l
   
   # Check for missing timestamp warnings
   grep "mentions have no timestamp" /path/to/logs/*.log | wc -l
   ```

2. **Track velocity_score distribution**:
   ```sql
   -- Check for issues with neutral velocity (should not be majority)
   SELECT 
       COUNT(*) as total_issues,
       COUNT(CASE WHEN velocity_score = 50.0 THEN 1 END) as neutral_velocity,
       COUNT(CASE WHEN velocity_score > 50.0 THEN 1 END) as growing,
       COUNT(CASE WHEN velocity_score < 50.0 THEN 1 END) as declining
   FROM topic_issues
   WHERE is_archived = false;
   ```

3. **Analyze timestamp source usage**:
   - If many warnings about mixed timestamps, consider:
     - Standardizing timestamp fields across data sources
     - Adding data validation at ingestion time
     - Backfilling missing `published_at` fields

---

## Future Enhancements

Based on the audit, consider implementing these enhancements:

### High Priority
- [ ] Add adaptive time windows (breaking vs sustained issues)
- [ ] Improve new issue velocity scoring (replace 1000% cap)

### Medium Priority
- [ ] Add velocity trend analysis (acceleration/deceleration)
- [ ] Store historical velocity in JSONB array

### Research Needed
- [ ] Analyze correlation between velocity and other priority components
- [ ] Test multiplicative velocity boost (instead of additive)

---

## References

- **Audit Report**: `docs/VELOCITY_PRIORITY_AUDIT.md`
- **Test File**: `tests/test_velocity_fixes.py`
- **Implementation**: `src/processing/issue_detection_engine.py`
- **Priority Calculator**: `src/processing/issue_priority_calculator.py`

---

**Status**: ✅ Ready for deployment

**Reviewed by**: AI Assistant  
**Date**: February 28, 2026
