# Velocity & Priority Calculation Audit

**Date**: February 28, 2026  
**Purpose**: Comprehensive audit of how velocity is calculated and used in issue priority scoring

---

## Executive Summary

The Clariona Backend calculates **velocity** as a growth rate metric for issues, and uses it as one of four components (10% weight) in the overall priority score. This audit examines:

1. ✅ How velocity is calculated
2. ✅ How velocity is converted to a priority score component
3. ✅ How the final priority score is computed
4. ⚠️ Potential issues and recommendations

---

## 1. Velocity Calculation

### Location
- **File**: `src/processing/issue_detection_engine.py`
- **Function**: `_calculate_volume_and_velocity()`
- **Lines**: 1925-2058

### Algorithm

#### Time Windows
```
Current Window:  [Now - 24h] → [Now]
Previous Window: [Now - 48h] → [Now - 24h]
```

**Configurable**: `processing.issue.volume.time_window_hours` (default: 24 hours)

#### Calculation Steps

1. **Query all mentions** linked to the issue via `issue_mentions` table
2. **Count mentions in each window**:
   - `volume_current_window`: Mentions with `published_at` in last 24 hours
   - `volume_previous_window`: Mentions with `published_at` in 24-48 hours ago
   - Falls back to: `published_date`, `date`, or `created_at` if `published_at` is missing

3. **Calculate velocity_percent**:
   ```python
   if previous_window_count > 0:
       velocity_percent = ((current - previous) / previous) * 100.0
   elif current_window_count > 0:
       velocity_percent = 1000.0  # Infinite growth (capped at 1000%)
   else:
       velocity_percent = 0.0  # No mentions in either window
   ```

4. **Convert to velocity_score (0-100)**:
   ```python
   if velocity_percent >= 100:
       velocity_score = 100.0
   elif velocity_percent >= 0:
       # Linear: 0% → 50, 100% → 100
       velocity_score = 50.0 + (velocity_percent / 100.0 * 50.0)
   else:
       # Linear: -100% → 0, 0% → 50
       velocity_score = max(0.0, 50.0 + (velocity_percent / 100.0 * 50.0))
   ```

### Database Fields
- **Table**: `topic_issues`
- **Fields**:
  - `mention_count` (Integer): Total mentions across all time
  - `volume_current_window` (Integer): Mentions in last 24h
  - `volume_previous_window` (Integer): Mentions in 24-48h ago
  - `velocity_percent` (Float): Growth rate percentage
  - `velocity_score` (Float): Normalized score (0-100)

### Examples

| Current | Previous | Velocity % | Velocity Score | Interpretation |
|---------|----------|------------|----------------|----------------|
| 10      | 5        | +100%      | 100.0          | Doubled (strong growth) |
| 15      | 10       | +50%       | 75.0           | Growing moderately |
| 10      | 10       | 0%         | 50.0           | Stable (no growth) |
| 5       | 10       | -50%       | 25.0           | Declining |
| 10      | 0        | +1000%     | 100.0          | New issue (infinite growth) |
| 0       | 0        | 0%         | 0.0            | No activity |

---

## 2. Priority Score Calculation

### Location
- **File**: `src/processing/issue_priority_calculator.py`
- **Class**: `IssuePriorityCalculator`
- **Function**: `calculate_priority()`
- **Lines**: 114-171

### Formula

```
priority_score = (
    sentiment_weight × sentiment_score +
    volume_weight × volume_score +
    time_weight × time_score +
    velocity_weight × velocity_score
)
```

### Default Weights

| Component | Weight | Configurable Key | Default |
|-----------|--------|------------------|---------|
| Sentiment | 40%    | `processing.issue.priority.sentiment_weight` | 0.4 |
| Volume    | 30%    | `processing.issue.priority.volume_weight` | 0.3 |
| Time      | 20%    | `processing.issue.priority.time_weight` | 0.2 |
| **Velocity** | **10%** | `processing.issue.priority.velocity_weight` | **0.1** |

### Component Score Calculations

#### A. Sentiment Score (0-100)
**Higher score = More negative sentiment = Higher priority**

```python
# Method 1: Use sentiment_index (0-100, where 0=most negative)
sentiment_score = 100.0 - sentiment_index

# Method 2: Use weighted_sentiment_score (-1.0 to 1.0)
sentiment_score = 50.0 - (weighted_sentiment_score * 50.0)
```

| Sentiment Index | Sentiment Score | Priority Impact |
|-----------------|-----------------|-----------------|
| 0 (very negative) | 100 | Maximum priority |
| 50 (neutral) | 50 | Medium priority |
| 100 (very positive) | 0 | Minimum priority |

#### B. Volume Score (0-100)
**Higher volume = Higher priority (with diminishing returns)**

```python
if mention_count == 0:
    return 0.0
else:
    score = 100.0 * (1.0 - math.exp(-mention_count / 20.0))
    return min(100.0, score)
```

| Mention Count | Volume Score |
|---------------|--------------|
| 0             | 0            |
| 3             | ~14          |
| 10            | ~39          |
| 20            | ~63          |
| 50            | ~92          |
| 100+          | 100          |

#### C. Time Score (0-100)
**More recent = Higher priority**

| Age           | Time Score |
|---------------|------------|
| 0-1 hour      | 100        |
| 1-24 hours    | 100 → 70 (linear) |
| 1-7 days      | 70 → 30 (linear) |
| 7-30 days     | 30 → 10 (linear) |
| 90+ days      | 0          |

#### D. Velocity Score (0-100)
**Already calculated** in `_calculate_volume_and_velocity()` (see Section 1)

### Priority Bands

```python
if priority_score >= 80:
    priority_band = 'critical'
elif priority_score >= 60:
    priority_band = 'high'
elif priority_score >= 40:
    priority_band = 'medium'
else:
    priority_band = 'low'
```

---

## 3. When Priority is Calculated

### Automatic Calculation

Priority is calculated **automatically** in these scenarios:

1. **New Issue Creation**
   - When: `IssueDetectionEngine` creates a new issue from a cluster
   - Process: Velocity → Priority → Lifecycle state (in sequence)
   - File: `src/processing/issue_detection_engine.py`, line ~1672

2. **Issue Update with New Mentions**
   - When: Existing issue is matched and updated with new mentions
   - Process: Velocity → Priority → Lifecycle state (in sequence)
   - File: `src/processing/issue_detection_engine.py`, line ~1797

3. **Full Recalculation Mode**
   - When: `IssueDetectionEngine.recalculate_all_issue_metrics()` is called
   - Process: Recalculates ALL metrics for ALL non-archived issues
   - File: `src/processing/issue_detection_engine.py`, line ~362

### Manual Calculation

Can be triggered via:
- `IssuePriorityCalculator.update_issue_priority(issue_id)` - Single issue
- `IssuePriorityCalculator.update_all_priorities(topic_key, limit)` - Bulk update

---

## 4. Data Flow

```
┌─────────────────────────────────────┐
│  New mentions arrive                │
│  (from CSV, X/Twitter, etc.)        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Phase 6: Issue Detection           │
│  (IssueDetectionEngine)             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 1: Clustering & Matching      │
│  - Cluster mentions by similarity   │
│  - Match to existing issues         │
│  - Create issue_mentions links      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 2: Volume & Velocity          │
│  (_calculate_volume_and_velocity)   │
│  ├─ Count: current window (24h)     │
│  ├─ Count: previous window (24-48h) │
│  ├─ Calculate: velocity_percent     │
│  └─ Calculate: velocity_score       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 3: Sentiment Aggregation      │
│  (_update_issue_sentiment_aggreg.)  │
│  ├─ sentiment_distribution          │
│  ├─ weighted_sentiment_score        │
│  ├─ sentiment_index                 │
│  └─ emotion_distribution            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 4: Metadata Extraction        │
│  (_update_issue_metadata)           │
│  ├─ top_keywords                    │
│  ├─ top_sources                     │
│  └─ regions_impacted                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 5: PRIORITY CALCULATION       │
│  (IssuePriorityCalculator)          │
│  ├─ sentiment_score (40%)           │
│  ├─ volume_score (30%)              │
│  ├─ time_score (20%)                │
│  ├─ velocity_score (10%)  ◄─────┐   │
│  ├─ priority_score (0-100)       │   │
│  └─ priority_band (critical/...) │   │
└──────────────┬───────────────────┼───┘
               │                   │
               │          Uses velocity_score
               │          from Step 2
               ▼
┌─────────────────────────────────────┐
│  Step 6: Lifecycle State            │
│  (IssueLifecycleManager)            │
│  - Uses velocity_percent for state  │
│  - States: emerging, active,        │
│    escalated, stabilizing, resolved │
└─────────────────────────────────────┘
```

---

## 5. Audit Findings

### ✅ Strengths

1. **Well-structured calculation**: Velocity is calculated systematically with clear time windows
2. **Proper normalization**: velocity_score is normalized to 0-100 for consistency
3. **Reasonable defaults**: 10% weight for velocity is appropriate (growth matters, but not as much as sentiment/volume)
4. **Configurable**: All weights and time windows can be adjusted via ConfigManager
5. **Handles edge cases**: Properly handles zero-division (new issues, no activity)
6. **Dual metrics**: Both `velocity_percent` (raw) and `velocity_score` (normalized) are stored
7. **Used in lifecycle**: Velocity also affects issue state (escalated, stabilizing)

### ⚠️ Potential Issues

#### 1. **Timestamp Field Priority**
**Issue**: The velocity calculation uses fallback logic for timestamps:
```python
mention_time = published_at or published_date or date or created_at
```

**Risk**: Inconsistent timestamp sources could lead to inaccurate velocity calculations.

**Example**: 
- Old data might only have `created_at` (ingestion time)
- New data has `published_at` (actual publication time)
- Mixing these could show false velocity trends

**Recommendation**: 
- Standardize on one timestamp field (preferably `published_at`)
- Add data quality checks to ensure timestamp consistency
- Log warnings when fallback timestamps are used

#### 2. **24-Hour Window Rigidity**
**Issue**: Fixed 24-hour windows may not capture all patterns:
- Breaking news: Minutes/hours matter more than days
- Slow-burn issues: Days/weeks matter more than hours

**Current**: `time_window_hours = 24` (configurable but not adaptive)

**Recommendation**:
- Add issue-type-specific windows:
  - `breaking`: 1-4 hours
  - `emerging`: 12-24 hours  
  - `sustained`: 3-7 days
- Store `time_window_type` field (already exists in schema!)
- Use different windows per issue type

#### 3. **Infinite Growth Cap (1000%)**
**Issue**: When an issue has no previous mentions but has current mentions:
```python
velocity_percent = 1000.0  # Infinite growth capped at 1000%
```

**Risk**: All "new" issues get the same 1000% velocity, losing nuance:
- 1 new mention = 1000% velocity
- 100 new mentions = 1000% velocity

**Impact on Priority**: 
- velocity_score = 100.0 for all new issues
- Final priority contribution: 0.1 × 100 = 10 points (out of 100)

**Recommendation**:
- Consider using absolute volume for new issues instead of infinite growth
- Alternative formula for new issues:
  ```python
  if previous_window_count == 0 and current_window_count > 0:
      # Use volume-based score instead of fixed 1000%
      velocity_score = min(100.0, current_window_count * 10)  # 10 mentions = 100 score
  ```

#### 4. **Velocity Weight is Low (10%)**
**Issue**: Velocity only contributes 10% to priority score

**Analysis**:
- Sentiment: 40% (most important)
- Volume: 30% (second most)
- Time: 20% (third)
- Velocity: 10% (least important)

**Scenarios Where This May Be Problematic**:
- Rapidly growing issue with moderate sentiment/volume might not escalate quickly
- Example:
  - Issue A: 50 mentions → 100 mentions (100% growth), negative sentiment
  - Issue B: 100 mentions → 110 mentions (10% growth), very negative sentiment
  - Issue B will score higher despite A growing faster

**Recommendation**:
- Consider increasing velocity weight for **escalation** scenarios
- Add configurable "escalation mode" with higher velocity weight:
  ```python
  if issue.state == 'emerging' and velocity_percent > 50:
      # Use escalation weights
      velocity_weight = 0.25  # Increase from 10% to 25%
      volume_weight = 0.25    # Decrease from 30% to 25%
  ```

#### 5. **No Velocity Trend Analysis**
**Issue**: Only compares two time windows (24h vs previous 24h)

**Missing**: 
- Multi-period trends (is velocity accelerating or decelerating?)
- Velocity momentum (growing → growing faster vs. growing → slowing down)

**Example**:
```
Period 1: 10 mentions
Period 2: 20 mentions (+100%)
Period 3: 25 mentions (+25%)
```
Current: Only sees +25% velocity
Better: Recognize deceleration from +100% → +25%

**Recommendation**:
- Add `velocity_trend` field: "accelerating", "stable", "decelerating"
- Store historical velocity in JSONB array
- Use trend in priority calculation

#### 6. **Zero Activity Issues**
**Issue**: Issues with no mentions in both windows get:
```python
velocity_percent = 0.0
velocity_score = 0.0  # But normalized formula gives 50.0!
```

**Bug**: There's an inconsistency:
- Direct assignment: `velocity_score = 0.0`
- But formula says: `0% velocity → 50.0 score`

**Location**: Line 2056-2057 in `issue_detection_engine.py`

**Recommendation**: Fix the fallback to match the formula:
```python
issue.velocity_percent = 0.0
issue.velocity_score = 50.0  # Neutral score, not zero
```

#### 7. **Sentiment Already Includes Velocity**
**Issue**: Issues with growing negative sentiment are already captured by sentiment_score

**Analysis**:
- If an issue is growing (high velocity), it likely has:
  - More recent mentions → higher time_score
  - More mentions overall → higher volume_score
  - More negative mentions → higher sentiment_score

**Risk**: Velocity might be **redundant** rather than additive

**Recommendation**:
- Analyze correlation between velocity and other components
- Consider if velocity should be a **multiplier** rather than additive:
  ```python
  priority_score = base_score * (1 + velocity_boost)
  where velocity_boost = (velocity_percent / 100) * 0.2  # 20% boost for 100% growth
  ```

---

## 6. Configuration Audit

### Current Configuration Keys

| Key | Default | Location | Mutable? |
|-----|---------|----------|----------|
| `processing.issue.volume.time_window_hours` | 24 | Database | ✅ |
| `processing.issue.priority.sentiment_weight` | 0.4 | Database | ✅ |
| `processing.issue.priority.volume_weight` | 0.3 | Database | ✅ |
| `processing.issue.priority.time_weight` | 0.2 | Database | ✅ |
| `processing.issue.priority.velocity_weight` | 0.1 | Database | ✅ |

### Hardcoded Values

⚠️ **Found in code**:
- `velocity_percent = 1000.0` (max cap for infinite growth) - Line 2022
- `velocity_score = 100.0` (max score) - Lines 2035
- Time window fallback: 24 hours - Line 1946

**Recommendation**: Move hardcoded values to configuration

---

## 7. Testing Recommendations

### Test Cases to Add

1. **Velocity Calculation Tests**:
   ```python
   def test_velocity_with_missing_timestamps():
       # Test fallback to published_date, date, created_at
   
   def test_velocity_timezone_handling():
       # Test UTC vs naive datetime handling
   
   def test_velocity_edge_cases():
       # Test 0→0, 0→N, N→0, N→N scenarios
   ```

2. **Priority Component Tests**:
   ```python
   def test_priority_velocity_contribution():
       # Isolate velocity's impact on final score
   
   def test_priority_with_zero_velocity():
       # Ensure consistent scoring for zero velocity
   ```

3. **Integration Tests**:
   ```python
   def test_priority_with_growing_issue():
       # Test full pipeline for growing issue
   
   def test_priority_vs_lifecycle():
       # Ensure priority and lifecycle state align
   ```

---

## 8. Recommendations Summary

### High Priority

1. ✅ **Fix zero velocity scoring bug** (Line 2056-2057)
   - Change `velocity_score = 0.0` to `velocity_score = 50.0` for consistency

2. ⚠️ **Add timestamp consistency checks**
   - Log warnings when fallback timestamps are used
   - Add data quality metrics

3. ⚠️ **Document velocity behavior**
   - Add inline comments explaining 1000% cap rationale
   - Document expected behavior for new issues

### Medium Priority

4. 🔧 **Consider adaptive time windows**
   - Use `time_window_type` field from schema
   - Different windows for breaking vs sustained issues

5. 🔧 **Improve new issue velocity scoring**
   - Replace 1000% flat cap with volume-based score

6. 🔧 **Add velocity trend analysis**
   - Store historical velocity
   - Detect acceleration vs deceleration

### Low Priority (Research)

7. 📊 **Analyze velocity correlation**
   - Measure correlation between velocity and other components
   - Determine if velocity is redundant

8. 📊 **Test alternative velocity formulas**
   - Multiplicative boost instead of additive
   - Non-linear velocity scoring

9. 📊 **Consider escalation-specific weights**
   - Higher velocity weight for emerging issues

---

## 9. Code Quality Assessment

### Maintainability: ✅ Good
- Clear function names and docstrings
- Modular design (separate calculators)
- Proper error handling

### Performance: ✅ Good
- Efficient queries (filters by issue_id)
- Minimal database round-trips
- Proper indexing on timestamp fields

### Testability: ⚠️ Moderate
- Unit tests exist but limited coverage
- Missing edge case tests
- No velocity-specific integration tests

### Configuration: ✅ Excellent
- All weights configurable
- Database-backed configuration
- Clear defaults with fallbacks

---

## 10. Conclusion

The velocity calculation and priority system is **well-designed and functional**, with proper normalization, edge case handling, and configurability. However, there are several areas for improvement:

### Critical Fixes Needed:
1. Fix zero velocity scoring inconsistency

### Enhancements to Consider:
2. Add timestamp consistency validation
3. Implement adaptive time windows
4. Improve new issue velocity scoring
5. Add velocity trend analysis

### Research Needed:
6. Analyze velocity correlation with other factors
7. Test alternative weighting schemes

**Overall Assessment**: ✅ Production-ready with minor improvements recommended

---

## Appendix: Example Calculations

### Example 1: Growing Issue

**Data**:
- Current window: 50 mentions
- Previous window: 25 mentions
- Sentiment index: 30 (negative)
- Age: 12 hours

**Calculation**:
```
velocity_percent = ((50-25)/25)*100 = 100%
velocity_score = 100.0  (≥100% rule)

sentiment_score = 100 - 30 = 70
volume_score = 100*(1-e^(-50/20)) = 91.8
time_score = 100 - (12/24*30) = 85
velocity_score = 100

priority_score = 0.4*70 + 0.3*91.8 + 0.2*85 + 0.1*100
               = 28 + 27.5 + 17 + 10
               = 82.5

priority_band = "critical" (≥80)
```

### Example 2: Declining Issue

**Data**:
- Current window: 10 mentions
- Previous window: 30 mentions
- Sentiment index: 50 (neutral)
- Age: 5 days

**Calculation**:
```
velocity_percent = ((10-30)/30)*100 = -66.7%
velocity_score = max(0, 50 + (-66.7/100*50)) = 16.7

sentiment_score = 100 - 50 = 50
volume_score = 100*(1-e^(-10/20)) = 39.3
time_score = 70 - ((5-1)/6*40) = 43.3
velocity_score = 16.7

priority_score = 0.4*50 + 0.3*39.3 + 0.2*43.3 + 0.1*16.7
               = 20 + 11.8 + 8.7 + 1.7
               = 42.2

priority_band = "medium" (40-59)
```

### Example 3: New Issue

**Data**:
- Current window: 5 mentions
- Previous window: 0 mentions
- Sentiment index: 20 (very negative)
- Age: 2 hours

**Calculation**:
```
velocity_percent = 1000%  (infinite growth cap)
velocity_score = 100.0

sentiment_score = 100 - 20 = 80
volume_score = 100*(1-e^(-5/20)) = 22.1
time_score = 100 - (2/24*30) = 97.5
velocity_score = 100

priority_score = 0.4*80 + 0.3*22.1 + 0.2*97.5 + 0.1*100
               = 32 + 6.6 + 19.5 + 10
               = 68.1

priority_band = "high" (60-79)
```

---

**End of Audit Report**

---

## Update: Fixes Implemented (February 28, 2026)

### ✅ Critical Fixes Completed

1. **Zero Velocity Bug Fixed** ✅
   - Changed error fallback from `velocity_score = 0.0` to `velocity_score = 50.0`
   - Location: `src/processing/issue_detection_engine.py`, line 2102
   - Status: ✅ Implemented and tested

2. **Timestamp Consistency Validation Added** ✅
   - Tracks timestamp sources (published_at, published_date, date, created_at, missing)
   - Warns when >20% of mentions use fallback timestamps
   - Warns when mentions have missing timestamps
   - Location: `src/processing/issue_detection_engine.py`, lines 1978-2086
   - Status: ✅ Implemented and tested

### Test Results

```
tests/test_velocity_fixes.py::TestVelocityFixes::test_zero_velocity_error_fallback PASSED [ 16%]
tests/test_velocity_fixes.py::TestVelocityFixes::test_zero_velocity_score_calculation PASSED [ 33%]
tests/test_velocity_fixes.py::TestVelocityFixes::test_timestamp_consistency_validation PASSED [ 50%]
tests/test_velocity_fixes.py::TestVelocityFixes::test_velocity_scores_for_various_percentages PASSED [ 66%]
tests/test_velocity_fixes.py::TestVelocityFixes::test_timestamp_source_tracking PASSED [ 83%]
tests/test_velocity_fixes.py::TestVelocityFormulaConsistency::test_formula_matches_priority_calculator PASSED [100%]

======================== 6 passed, 2 warnings in 19.00s ========================
```

### Files Modified

- ✅ `src/processing/issue_detection_engine.py` - Applied fixes
- ✅ `docs/VELOCITY_FIXES.md` - Detailed fix documentation
- ✅ `tests/test_velocity_fixes.py` - Comprehensive test suite (6 tests, all passing)
- ✅ `docs/VELOCITY_PRIORITY_AUDIT.md` - Original audit report

### Status: Ready for Production ✅
