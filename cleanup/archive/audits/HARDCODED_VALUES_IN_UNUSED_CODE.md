# Hardcoded Values in Unused Code (REMOVE, Don't Configure)

**Created**: 2025-12-27  
**Purpose**: Identify hardcoded values in code paths that will be REMOVED (so we don't waste time creating configs for them)  
**Status**: Phase 1, Step 1.2 Supplemental

---

## 📋 Methodology

This document cross-references:
1. **HARDCODED_VALUES_AUDIT.md** - All hardcoded values found
2. **UNUSED_CODE_AUDIT_REVISED.md** - Code identified for removal
3. **EXECUTION_FLOW_MAP.md** - What's actually used

**Result**: List of hardcoded values that are in unused code paths - these should be REMOVED along with the code, NOT configured.

---

## 🔴 Hardcoded Values in Code to be REMOVED

### DataProcessor.process_data() - TO BE REMOVED

**Method**: `src/processing/data_processor.py::process_data()` [line 851]  
**Status**: ❌ UNUSED - Only called in `if __name__ == "__main__"` block  
**Action**: **REMOVE entire method**

**Hardcoded Values in This Method** (REMOVE, don't configure):

| Line | Value | Type | Action |
|------|-------|------|--------|
| 894 | `batch_size = 100` | Batch size | **REMOVE** (with method) |
| 912 | `len_ratio < 0.5` | Threshold | **REMOVE** (with method) |
| 876 | `datetime.now().strftime('%Y-%m-%d')` | Default date | **REMOVE** (with method) |
| 905 | `range(idx1 + 1, min(idx1 + 1000, total_rows))` | Comparison window (1000) | **REMOVE** (with method) |

**Note**: `random.seed(42)` on line 65 - **VERIFY** if used elsewhere. If only in this method, **REMOVE**.

---

### DataProcessor.normalize_text() - TO BE REMOVED

**Method**: `src/processing/data_processor.py::normalize_text()` [line 306]  
**Status**: ❌ UNUSED - Only called by `process_data()` (which is unused)  
**Action**: **REMOVE entire method** (replaced by `DeduplicationService.normalize_text()`)

**Hardcoded Values in This Method** (REMOVE, don't configure):

| Line | Value | Type | Action |
|------|-------|------|--------|
| 313 | `re.sub(r'\s+', ' ', text)` | Regex pattern | **REMOVE** (with method) |
| 315 | `re.sub(r'https?://\S+', '', text)` | Regex pattern | **REMOVE** (with method) |
| 317 | `re.sub(r'[^\w\s.,?!-]', '', text)` | Regex pattern | **REMOVE** (with method) |

**Note**: These regex patterns are duplicated in `DeduplicationService`, so removing this method doesn't lose functionality.

---

### DataProcessor.is_similar_text() - TO BE REMOVED

**Method**: `src/processing/data_processor.py::is_similar_text()` [line 320]  
**Status**: ❌ UNUSED - Only called by `process_data()` (which is unused)  
**Action**: **REMOVE entire method** (replaced by `DeduplicationService.is_similar_text()`)

**Hardcoded Values in This Method** (REMOVE, don't configure):

| Line | Value | Type | Action |
|------|-------|------|--------|
| 320 | `threshold=0.85` | Default threshold | **REMOVE** (with method) |
| 326 | `len(text1) < 10` | Short text length check | **REMOVE** (with method) |
| 326 | `len(text2) < 10` | Short text length check | **REMOVE** (with method) |

**Note**: Same values exist in `DeduplicationService`, so no functionality lost.

---

### DataProcessor.load_raw_data() - TO BE REMOVED

**Method**: `src/processing/data_processor.py::load_raw_data()` [if exists]  
**Status**: ❌ UNUSED - Only called by `process_data()`  
**Action**: **REMOVE entire method** (if exists)

**Hardcoded Values**: Check if method exists and remove all values in it.

---

### DataProcessor.save_processed_data() - TO BE VERIFIED

**Method**: `src/processing/data_processor.py::save_processed_data()` [line 1072]  
**Status**: 🟡 UNUSED - Only called by `process_files()` and `process_data()`  
**Action**: **VERIFY** - If `process_files()` is unused, REMOVE this method too.

**Hardcoded Values**: None significant (just file operations)

---

### DataProcessor.process_files() - TO BE VERIFIED

**Method**: `src/processing/data_processor.py::process_files()` [line 976]  
**Status**: 🟡 UNUSED - Only called in `if __name__ == "__main__"` or standalone  
**Action**: **VERIFY** - If unused, REMOVE entire method.

**Hardcoded Values**: Check method for any hardcoded values if it exists.

---

### presidential_service.py Deduplication Functions - TO BE REMOVED

#### normalize_text_for_dedup()

**Function**: `src/api/presidential_service.py::normalize_text_for_dedup()` [line 478]  
**Status**: ❌ UNUSED - Legacy deduplication  
**Action**: **REMOVE entire function**

**Hardcoded Values** (REMOVE, don't configure):

| Line | Value | Type | Action |
|------|-------|------|--------|
| 486 | `text.lower()` | Text processing | **REMOVE** (with function) |
| 489 | `' '.join(text.split())` | Whitespace normalization | **REMOVE** (with function) |
| 493 | `re.sub(r'[^\w\s]', '', text)` | Regex pattern | **REMOVE** (with function) |

#### remove_similar_content()

**Function**: `src/api/presidential_service.py::remove_similar_content()` [line 497]  
**Status**: ❌ UNUSED - Legacy deduplication  
**Action**: **REMOVE entire function**

**Hardcoded Values** (REMOVE, don't configure):

| Line | Value | Type | Action |
|------|-------|------|--------|
| 497 | `similarity_threshold: float = 0.85` | Default threshold | **REMOVE** (with function) |
| Various | Similarity comparison logic | Algorithm | **REMOVE** (with function) |

#### deduplicate_sentiment_data()

**Function**: `src/api/presidential_service.py::deduplicate_sentiment_data()` [line 438]  
**Status**: ❌ UNUSED - Legacy deduplication  
**Action**: **REMOVE entire function**

**Hardcoded Values**: None significant (calls other functions to be removed)

---

### service.py Legacy Deduplication Functions - TO BE REMOVED

Same as above, but in `src/api/service.py`:
- `deduplicate_sentiment_data()`
- `normalize_text_for_dedup()`
- `remove_similar_content()`
- `remove_similar_content_optimized()` (if exists)

**Action**: **REMOVE all hardcoded values in these functions** (with the functions)

---

## 🟡 Hardcoded Values in Code to be VERIFIED

### Scheduler Code (if scheduler is unused)

If scheduler is removed, these hardcoded values go too:

**File**: `src/agent/core.py`

| Line | Value | Type | Action |
|------|-------|------|--------|
| 377 | `time.sleep(1)` | Retry sleep | **VERIFY** - Remove if scheduler removed |
| 418 | `time.sleep(300)` | No users sleep (5 min) | **VERIFY** - Remove if scheduler removed |
| 484 | `time.sleep(1)` | Retry sleep | **VERIFY** - Remove if scheduler removed |
| 503 | `time.sleep(60)` | Error sleep | **VERIFY** - Remove if scheduler removed |
| 497 | `sleep_time = 30 if self.continuous_mode else 60` | Sleep time | **VERIFY** - Remove if scheduler removed |

**Note**: These values are in `HARDCODED_VALUES_AUDIT.md` as "delays" to configure.  
**Action**: If scheduler code is removed, REMOVE these from the config plan (don't configure unused code).

---

### Command Execution Methods (if `/command` endpoint unused)

If `/command` endpoint is removed, these methods and their hardcoded values go too:

**File**: `src/agent/core.py`

| Method | Hardcoded Values | Action |
|--------|-----------------|--------|
| `execute_command()` | None significant | **VERIFY** - Remove if endpoint unused |
| `start()` | None significant | **VERIFY** - Remove if endpoint unused |
| `stop()` | None significant | **VERIFY** - Remove if endpoint unused |
| `update_location_classifications()` | `batch_size: int = 100` [line 2187] | **VERIFY** - Remove if endpoint unused |

---

## 📊 Summary: Hardcoded Values to REMOVE (Not Configure)

### High Confidence Removals:

| Category | Count | Examples |
|----------|-------|----------|
| Batch sizes | 2 | `batch_size = 100` (process_data) |
| Thresholds | 4 | `0.85`, `0.5`, `len < 10` |
| Regex patterns | 5 | Various text normalization patterns |
| Sleep delays | 0-5 | If scheduler removed |
| Comparison windows | 1 | `1000` (similarity comparison) |

**Total Hardcoded Values to REMOVE**: ~15-20 values (don't configure these!)

---

## ✅ Action Plan

### Step 1: Remove Unused Code First

1. Remove `process_data()` and related methods
   - **Result**: Remove ~10 hardcoded values from config plan

2. Remove legacy deduplication functions
   - **Result**: Remove ~5 hardcoded values from config plan

3. Verify and remove scheduler (if unused)
   - **Result**: Remove ~5 hardcoded values from config plan

4. Verify and remove command execution (if unused)
   - **Result**: Remove ~1 hardcoded value from config plan

### Step 2: Update Hardcoded Values Audit

5. After removing unused code:
   - Remove hardcoded values from `HARDCODED_VALUES_AUDIT.md` that were in removed code
   - Update counts: ~250+ → ~230-235 (after removing unused code values)

### Step 3: Configure Only Active Code

6. Only create configs for hardcoded values in ACTIVE code paths
   - Don't waste time configuring unused code
   - Focus configuration effort on what's actually used

---

## 🎯 Key Insight

**~15-20 hardcoded values (~8-10% of total) are in unused code paths.**

**Action**: Remove the code FIRST, then update the hardcoded values audit.  
**Result**: Less code to maintain + fewer config values to manage = Cleaner codebase!

---

**Last Updated**: 2025-12-27  
**Status**: Cross-reference complete - Ready to remove unused code first






