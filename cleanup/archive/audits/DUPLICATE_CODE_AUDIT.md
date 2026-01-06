# Duplicate Code Audit

**Created**: 2025-12-27  
**Purpose**: Identify duplicate code patterns that should be consolidated  
**Status**: Phase 1, Step 1.4 - In Progress

---

## 📋 Duplicate Code Categories

1. **Deduplication Logic** - Multiple implementations
2. **Config Loading** - Multiple mechanisms
3. **Path Resolution** - Multiple base_path calculations
4. **Method Duplication** - Duplicate method definitions
5. **Error Handling** - Similar patterns (future improvement)

---

## 1. DEDUPLICATION LOGIC

### Multiple Implementations Found

#### ✅ Canonical Implementation: `DeduplicationService`

**Location**: `src/utils/deduplication_service.py`  
**Status**: ACTIVE - Used in main execution flow  
**Methods**:
- `normalize_text(text: str) -> str` (line 22)
- `is_similar_text(text1: str, text2: str, threshold: float = None) -> bool` (line 41)
- `deduplicate_new_data(new_records, db, user_id)` (line 232)

**Features**:
- Comprehensive text normalization
- Similarity checking with SequenceMatcher
- Database integration
- Configurable threshold (0.85 default)
- Used in `_run_deduplication()` in core.py

---

#### ❌ Legacy Implementation 1: `presidential_service.py`

**Location**: `src/api/presidential_service.py`  
**Status**: LEGACY - Should be removed  
**Methods**:
- `normalize_text_for_dedup(text: str) -> str` (line 478)
- `remove_similar_content(records, similarity_threshold: float = 0.85)` (line 497)
- `deduplicate_sentiment_data(records)` (line 438)

**Similarities to DeduplicationService**:
- Similar normalization logic (lowercase, whitespace, punctuation)
- Similar similarity threshold (0.85)
- Similar text extraction logic

**Differences**:
- Simpler normalization (doesn't remove URLs)
- Different similarity check algorithm
- Works with model objects instead of dicts

**Used By**: 
- `deduplicate_sentiment_data()` function
- Called from `process_existing_data_with_presidential_analysis()` endpoint

**Action**: 🔴 **REMOVE** - Replace with `DeduplicationService`

---

#### ❌ Legacy Implementation 2: `data_processor.py`

**Location**: `src/processing/data_processor.py`  
**Status**: LEGACY - Likely unused  
**Methods**:
- `normalize_text(self, text)` (line 306)
- `is_similar_text(self, text1, text2, threshold=0.85)` (line 320)

**Similarities to DeduplicationService**:
- Identical logic to DeduplicationService
- Same threshold default (0.85)
- Same normalization steps

**Used By**: 
- `process_data()` method (which is legacy/unused)

**Action**: 🔴 **REMOVE** - Already replaced by `DeduplicationService`

---

#### ⚠️ Disabled Implementation: `data_cache.py`

**Location**: `src/api/data_cache.py`  
**Status**: DISABLED (commented out)  
**Method**:
- `deduplicate_data(data)` (line 253)

**Features**:
- Simple hash-based deduplication
- Currently disabled (returns data as-is)

**Action**: 🟡 **VERIFY** if needed, otherwise remove

---

### Consolidation Plan

**Keep**: `DeduplicationService` (canonical, actively used)  
**Remove**: 
1. `normalize_text_for_dedup()` from `presidential_service.py`
2. `remove_similar_content()` from `presidential_service.py`
3. `deduplicate_sentiment_data()` from `presidential_service.py` (or refactor to use DeduplicationService)
4. `normalize_text()` from `data_processor.py`
5. `is_similar_text()` from `data_processor.py`
6. `deduplicate_data()` from `data_cache.py` (if not needed)

**Refactor Required**:
- Update `presidential_service.py` to use `DeduplicationService` if deduplication is still needed

---

## 2. CONFIG LOADING

### Multiple Config Loading Mechanisms

#### Pattern 1: Direct JSON File Reading

**Locations**:
- `src/agent/core.py` - `load_config()` (line 745)
- `src/collectors/target_config_manager.py` - `_load_config()` (line 49)
- `src/collectors/rss_feed_validator.py` - `_load_config()` (line 62)
- `src/processing/topic_classifier.py` - `_load_topics_from_json_fallback()` (line 134)

**Pattern**:
```python
with open(config_path, 'r') as f:
    config = json.load(f)
```

**Issue**: Each implementation has slightly different error handling and default merging

**Action**: 🟡 **CONSOLIDATE** - Create centralized ConfigManager

---

#### Pattern 2: Environment Variable Loading

**Locations**:
- `src/api/database.py` - Loads .env from config directory
- `src/api/auth.py` - Loads .env from config directory  
- `src/api/middlewares.py` - Loads .env from config directory
- `src/processing/presidential_sentiment_analyzer.py` - Loads .env from config directory
- `src/agent/autogen_agents.py` - Loads .env from agent directory

**Pattern**:
```python
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / 'config' / '.env'
load_dotenv(dotenv_path=env_path)
```

**Issue**: Multiple places load .env, sometimes from different locations

**Action**: 🟡 **CONSOLIDATE** - Single .env loading in ConfigManager

---

#### Pattern 3: Path-based Config Discovery

**Locations**:
- `src/processing/topic_classifier.py` - Finds config directory
- `src/processing/topic_embedding_generator.py` - Finds config directory

**Pattern**:
```python
config_dir = Path(__file__).parent.parent.parent / 'config'
```

**Issue**: Duplicate path calculations

**Action**: 🟡 **CONSOLIDATE** - Use PathManager

---

## 3. PATH RESOLUTION

### Multiple Base Path Calculations

**Locations**: 30+ files calculate base_path the same way:

```python
base_path = Path(__file__).parent.parent.parent
```

**Files with this pattern**:
- `src/agent/core.py` (line 170)
- `src/collectors/configurable_collector.py` (line 38)
- `src/collectors/collect_news_from_api.py` (line 29)
- `src/collectors/collect_youtube_api.py` (line 54)
- `src/collectors/collect_rss_nigerian_qatar_indian.py` (line 39)
- `src/collectors/collect_rss.py` (line 35)
- `src/collectors/collect_radio_stations.py` (line 34)
- `src/collectors/collect_radio_hybrid.py` (line 36)
- `src/collectors/collect_radio_gnews.py` (line 29)
- `src/collectors/rss_feed_health_monitor.py` (line 21)
- `src/processing/data_processor.py` (line 39)
- `src/processing/presidential_data_processor.py` (line 35)
- `src/processing/sentiment_analyzer_huggingface.py` (line 17)
- `src/utils/file_rotation.py` (line 24)
- `src/utils/mail_sender.py` (line 18)
- `src/utils/notification_service.py` (line 25)
- Many more...

**Issue**: 
- Duplicated in 30+ files
- Hard to change if project structure changes
- Inconsistent if some files use different depth

**Action**: 🔴 **HIGH PRIORITY** - Create PathManager, replace all instances

**Estimated Impact**: 
- Remove ~30 lines of duplicate code
- Centralize path management
- Make paths configurable

---

## 4. METHOD DUPLICATION

### Duplicate Method: `_run_task()`

**Location**: `src/agent/core.py`  
**Duplicates**: 
- Line 1310: First definition
- Line 1880: Second definition (identical code)

**Status**: ❌ **DUPLICATE DEFINITION** - Python will use the second definition

**Evidence**: 
- Both methods have identical signatures
- Both have nearly identical implementations
- Minor differences in logging and error handling

**Action**: 🔴 **REMOVE ONE** - Keep the more complete version (likely the second one)

**Recommendation**: 
- Keep version at line 1880 (more recent, appears more complete)
- Remove version at line 1310
- Verify all calls work with remaining version

---

## 5. DATE PARSING (Potential Duplication)

### Date Parsing Logic

**Locations**:
- `src/agent/core.py` - `_parse_date_string()` (used in deduplication)
- `src/processing/data_processor.py` - `parse_date()` (line 333)

**Similarities**:
- Both parse various date formats
- Both handle Twitter date format
- Both handle ISO formats
- Both return datetime or None

**Differences**:
- Slight differences in format handling
- Different error handling

**Action**: 🟡 **CONSIDER CONSOLIDATION** - May want to create shared date parser utility

---

## 📊 Summary Statistics

### Duplicate Code by Category:

| Category | Instances | Lines of Duplicate Code | Priority |
|----------|-----------|------------------------|----------|
| Deduplication Logic | 4 implementations | ~200-300 lines | 🔴 HIGH |
| Config Loading | 5+ mechanisms | ~100-150 lines | 🟡 MEDIUM |
| Path Resolution | 30+ instances | ~30 lines | 🔴 HIGH |
| Method Duplication | 1 duplicate method | ~80 lines | 🔴 HIGH |
| Date Parsing | 2 implementations | ~100 lines | 🟡 MEDIUM |

**Total Estimated Duplicate Code**: ~500-600 lines

**Removal Potential**: ~400-500 lines (after consolidation)

---

## 🎯 Consolidation Recommendations

### Priority 1 (High Impact):

1. **Consolidate Deduplication Logic** 🔴
   - Keep: `DeduplicationService`
   - Remove: 3 legacy implementations
   - Impact: ~200-300 lines removed, single source of truth

2. **Create PathManager** 🔴
   - Replace 30+ base_path calculations
   - Impact: ~30 lines removed, centralized path management

3. **Remove Duplicate `_run_task()` Method** 🔴
   - Keep: One version (line 1880)
   - Remove: Other version (line 1310)
   - Impact: ~80 lines removed, eliminate confusion

### Priority 2 (Medium Impact):

4. **Consolidate Config Loading** 🟡
   - Create centralized ConfigManager
   - Impact: ~100-150 lines simplified, consistent config access

5. **Consolidate Date Parsing** 🟡
   - Create shared date parser utility
   - Impact: ~100 lines simplified, consistent date handling

---

## ✅ Action Items

### Immediate Actions:

1. [ ] Remove duplicate `_run_task()` method (keep line 1880, remove line 1310)
2. [ ] Remove legacy deduplication functions from `presidential_service.py`
3. [ ] Remove legacy deduplication methods from `data_processor.py`
4. [ ] Create PathManager utility
5. [ ] Replace all base_path calculations with PathManager

### Phase 2 Actions:

6. [ ] Create centralized ConfigManager
7. [ ] Consolidate all config loading to use ConfigManager
8. [ ] Create shared date parser utility (optional)

---

## 📝 Notes

### Deduplication Consolidation Considerations:

- `presidential_service.py` functions work with SQLAlchemy model objects
- `DeduplicationService` works with dictionaries
- May need adapter/converter if consolidating

### Path Resolution Considerations:

- Some files may need paths relative to their location
- PathManager should handle both absolute and relative paths
- Consider symlinks and different project structures

### Config Loading Considerations:

- Different configs have different structures
- Some configs need validation
- Environment variable override priority needs to be consistent

---

**Last Updated**: 2025-12-27  
**Status**: Initial audit complete - ready for consolidation implementation






