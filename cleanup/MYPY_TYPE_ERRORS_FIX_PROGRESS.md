# Mypy Type Errors Fix Progress

**Date**: 2025-01-02  
**Status**: 🚀 **IN PROGRESS**  
**Total Errors**: ~500+  
**Fixed**: ~50+  
**Remaining**: ~450+

---

## ✅ Fixed Issues

### 1. Missing Type Annotations (var-annotated)
- ✅ `src/utils/openai_rate_limiter.py` - Added type annotations for `token_usage: Deque[Tuple[float, int]]` and `retry_counts: Dict[str, int]`
- ✅ `src/utils/multi_model_rate_limiter.py` - Added type annotations for `token_usage` and `retry_counts`
- ✅ `src/collectors/target_config_manager.py` - Added type annotations for `config_data: Dict[str, Any]` and `targets: Dict[str, TargetConfig]`
- ✅ `src/collectors/collect_radio_gnews.py` - Added type annotation for `platform_breakdown: Dict[str, int]` and `articles: List[Dict[str, Any]]`
- ✅ `src/api/models.py` - Added type annotations for `keywords: list[str]`, `topics: list[str]`, `priority_topics: list[str]`

### 2. Implicit Optional Types
- ✅ `src/exceptions.py` - Fixed `details: dict = None` → `details: Optional[dict] = None` and `retry_after: float = None` → `retry_after: Optional[float] = None`
- ✅ `src/collectors/target_config_manager.py` - Fixed dataclass fields: `countries: List[str] = None` → `countries: Optional[List[str]] = None` (and similar for other fields)
- ✅ `src/collectors/target_config_manager.py` - Fixed `__init__` parameter: `config_path: str = None` → `config_path: Optional[str] = None`
- ✅ `src/collectors/run_collectors.py` - Fixed `user_id: str = None` → `user_id: Optional[str] = None`
- ✅ `src/collectors/collect_radio_gnews.py` - Fixed `queries: List[str] = None` → `queries: Optional[List[str]] = None`, `output_file: str = None` → `output_file: Optional[str] = None`, `user_id: str = None` → `user_id: Optional[str] = None`
- ✅ `src/collectors/collect_youtube_api.py` - Fixed `target_and_variations: List[str] = None` → `target_and_variations: Optional[List[str]] = None`, `user_id: str = None` → `user_id: Optional[str] = None`

### 3. SQLAlchemy Base Class Issues
- ✅ `src/api/models.py` - Fixed Base class import using `TYPE_CHECKING` to properly handle type checking

### 4. Missing Imports
- ✅ `src/collectors/collect_radio_gnews.py` - Added `from src.exceptions import ValidationError`

### 5. Additional Fixes (Continued)
- ✅ `src/collectors/collect_twitter_apify.py` - Fixed Optional types, added None checks for run objects
- ✅ `src/collectors/collect_news_apify.py` - Fixed Optional types, added None checks for run objects
- ✅ `src/collectors/collect_tiktok_apify.py` - Added type annotations and None checks
- ✅ `src/collectors/collect_instagram_apify.py` - Added type annotations for query_data, added None checks
- ✅ `src/collectors/collect_facebook_apify.py` - Added type annotations for runs_to_process, added None checks
- ✅ `src/collectors/rss_feed_validator.py` - Fixed Optional types, added type annotations
- ✅ `src/collectors/rss_feed_health_monitor.py` - Fixed Optional types, added type annotations, fixed report dictionary types
- ✅ `src/processing/topic_classifier.py` - Fixed Optional types, added return type annotations
- ✅ `src/processing/record_router.py` - Fixed Optional types
- ✅ `src/utils/deduplication_service.py` - Fixed Optional types, added type annotations
- ✅ `src/utils/similarity.py` - Added return type annotation
- ✅ `src/collectors/incremental_collector.py` - Added return type annotations
- ✅ `src/collectors/collect_rss_nigerian_qatar_indian.py` - Fixed return types for _clean_xml and _fetch_feed_with_requests

---

## 🔄 Remaining Issues (Systematic Fix Needed)

### Pattern 1: Implicit Optional Types in Function Parameters
**Pattern**: `param: Type = None` → Should be `param: Optional[Type] = None`

**Files to Fix** (estimated ~100+ occurrences):
- `src/collectors/collect_news_from_api.py` - `output_file: str = None`, `user_id: str = None`
- `src/collectors/collect_rss.py` - `queries: List[str] = None`, `output_file: str = None`, `target_name: str = None`, `user_id: str = None`
- `src/collectors/collect_rss_nigerian_qatar_indian.py` - Similar patterns
- `src/collectors/collect_radio_stations.py` - Similar patterns
- `src/collectors/collect_radio_hybrid.py` - Similar patterns
- `src/collectors/collect_twitter_apify.py` - `output_file=None`, `since_date: str = None`, `until_date: str = None`
- `src/collectors/collect_tiktok_apify.py` - `output_file=None`, `user_id: str = None`
- `src/collectors/collect_news_apify.py` - `output_file=None`, `since_date: str = None`, `until_date: str = None`
- `src/collectors/collect_instagram_apify.py` - `output_file=None`, `user_id: str = None`
- `src/collectors/collect_facebook_apify.py` - `output_file=None`, `user_id: str = None`
- `src/collectors/configurable_collector.py` - Multiple functions with `user_id: str = None`
- `src/collectors/rss_feed_validator.py` - `feed_urls: list[str] = None`, `filename: str = None`
- `src/collectors/rss_feed_health_monitor.py` - `feed_urls: list[str] = None`, `timeout: int = None`
- `src/processing/topic_classifier.py` - `keywords: list[str] = None`, `keyword_groups: dict[Any, Any] = None`
- `src/processing/record_router.py` - `models: list[str] = None`, `source_types: list[str] = None`
- `src/api/data_cache.py` - `exclude_keywords: list[str] = None`, `db: Session = None`
- `src/utils/deduplication_service.py` - `threshold: float = None`
- `src/alembic/env.py` - Various Optional issues

**Fix Command Pattern**:
```python
# Before
def function(param: str = None):
    pass

# After
def function(param: Optional[str] = None):
    pass
```

### Pattern 2: Missing Type Annotations for Variables
**Pattern**: Variables without type annotations that mypy can't infer

**Files to Fix**:
- `src/collectors/collect_youtube_api.py` - `channels: dict[<type>, <type>]` (line 92)
- `src/collectors/collect_radio_gnews.py` - Already fixed `articles` and `platform_breakdown`
- `src/collectors/collect_news_from_api.py` - `country_breakdown: dict[<type>, <type>]` (lines 220, 294)
- `src/collectors/collect_radio_stations.py` - `articles: list[<type>]` (line 195), `found_articles: list[<type>]` (line 247)
- `src/collectors/collect_radio_hybrid.py` - `found_articles: list[<type>]` (line 539)
- `src/collectors/collect_instagram_apify.py` - `query_data: list[<type>]` (line 218)
- `src/collectors/collect_facebook_apify.py` - `runs_to_process: list[<type>]` (line 246)
- `src/processing/record_router.py` - `routed: <type>` (line 102), `all_results: list[<type>]` (line 137)
- `src/utils/deduplication_service.py` - `duplicates_map: dict[<type>, <type>]` (line 90)

**Fix Pattern**:
```python
# Before
articles = []

# After
articles: List[Dict[str, Any]] = []
```

### Pattern 3: Return Type Issues (no-any-return)
**Pattern**: Functions returning `Any` when they should return specific types

**Files to Fix** (~50+ occurrences):
- `src/utils/collection_tracker.py` - `_load_tracker_data` returns `Any` instead of `dict[str, Any]`
- `src/collectors/target_config_manager.py` - `get_target_by_name`, `get_collection_settings`, `get_default_sources` return `Any`
- `src/collectors/collect_youtube_api.py` - Multiple `_get_target_keywords` methods return `Any` instead of `list[str]`
- `src/collectors/collect_radio_gnews.py` - `_get_target_keywords` methods return `Any`
- `src/collectors/collect_news_from_api.py` - `_get_target_keywords`, `_get_target_countries` return `Any`
- `src/collectors/collect_radio_stations.py` - `_get_target_keywords` methods return `Any`
- `src/collectors/collect_radio_hybrid.py` - `_get_target_keywords` methods return `Any`
- `src/collectors/collect_youtube_api.py` - `_get_thumbnail_url` returns `Any` instead of `str`
- `src/collectors/rss_feed_validator.py` - `_load_config`, `_get_replacement_feed` return `Any`
- `src/collectors/rss_feed_health_monitor.py` - `_load_health_data`, `_get_feed_health`, `_calculate_health_score` return `Any`
- `src/collectors/configurable_collector.py` - `determine_target` methods return `Any`
- `src/processing/topic_classifier.py` - `get_topics_for_owner` returns `Any`
- `src/processing/topic_classifier.py` - `_get_db_session` returns `Any` instead of `Session`
- `src/config/config_manager.py` - `_convert_env_value` returns `Any`
- `src/utils/similarity.py` - `normalize_embedding` returns `Any`
- `src/collectors/incremental_collector.py` - `collect_facebook_incremental`, `collect_instagram_incremental` return `Any` instead of `int`
- `src/collectors/collect_twitter_apify.py` - `collect_twitter_apify_with_dates` returns `Any` instead of `int`
- `src/collectors/collect_news_apify.py` - `collect_news_apify_with_dates` returns `Any` instead of `int`

**Fix Pattern**:
```python
# Before
def function() -> Any:
    return some_value

# After
def function() -> Dict[str, Any]:  # or appropriate type
    return some_value
```

### Pattern 4: Type Incompatibility Issues
**Pattern**: Various type mismatches

**Categories**:
1. **Assignment Issues**:
   - `float` assigned to `int` variables (e.g., `src/collectors/collect_radio_stations.py:124`, `src/processing/topic_classifier.py:353`)
   - `None` assigned to non-Optional types
   - `Path` assigned to `str` (e.g., `src/collectors/collect_rss.py:565`)

2. **Argument Type Issues**:
   - `str | None` passed where `str` expected
   - `dict[str, object]` passed where specific dict type expected (HTTP params)

3. **Attribute Access Issues**:
   - Accessing attributes on `None` or `Any | None` types
   - `AttributeValueList` type issues in BeautifulSoup code

4. **Index/Assignment Issues**:
   - Indexing `None` or non-indexable types
   - Assigning to non-assignable types

**Files to Fix**:
- `src/collectors/collect_rss.py` - Path/str issues, return type issues
- `src/collectors/collect_rss_nigerian_qatar_indian.py` - Similar issues
- `src/collectors/collect_radio_stations.py` - AttributeValueList issues, float/int issues
- `src/collectors/collect_radio_hybrid.py` - Similar issues
- `src/collectors/collect_twitter_apify.py` - Indexing None issues
- `src/collectors/collect_tiktok_apify.py` - Type assignment issues
- `src/collectors/collect_news_apify.py` - Indexing issues
- `src/collectors/collect_instagram_apify.py` - Return type issues
- `src/collectors/collect_facebook_apify.py` - Return type issues
- `src/utils/mail_sender.py` - Column/list type issues
- `src/api/data_cache.py` - Column type issues, iterable issues
- `src/utils/scheduled_reports.py` - Thread/None issues, Job attribute issues
- `src/utils/deduplication_service.py` - Type assignment issues
- `src/collectors/rss_ssl_handler.py` - Formatter/Handler type issues
- `src/alembic/env.py` - Dict assignment issues

### Pattern 5: SQLAlchemy Column Type Issues
**Files to Fix**:
- `src/api/models.py` - Already partially fixed, but may need `Mapped` types for SQLAlchemy 2.0+
- `src/utils/mail_sender.py` - Column[Any] vs list[str] issues
- `src/api/data_cache.py` - Column[str] vs list[str] issues

---

## 🛠️ Recommended Fix Strategy

### Phase 1: Fix All Optional Types (Highest Priority)
1. Search for all `param: Type = None` patterns
2. Replace with `param: Optional[Type] = None`
3. Ensure `Optional` is imported from `typing`

**Estimated Time**: 2-3 hours  
**Files**: ~30 files  
**Errors Fixed**: ~150+

### Phase 2: Add Missing Type Annotations
1. Add type annotations for all variables that mypy flags
2. Use appropriate types: `List[Dict[str, Any]]`, `Dict[str, int]`, etc.

**Estimated Time**: 1-2 hours  
**Files**: ~15 files  
**Errors Fixed**: ~50+

### Phase 3: Fix Return Type Annotations
1. Replace `-> Any` with specific return types
2. Use `cast()` or type assertions where necessary

**Estimated Time**: 2-3 hours  
**Files**: ~20 files  
**Errors Fixed**: ~50+

### Phase 4: Fix Type Incompatibility Issues
1. Fix float/int assignments (use `int()` conversion or change type)
2. Fix None checks before attribute access
3. Fix Path/str issues
4. Fix indexing issues with None checks

**Estimated Time**: 3-4 hours  
**Files**: ~25 files  
**Errors Fixed**: ~200+

### Phase 5: Fix SQLAlchemy and Special Cases
1. Use `Mapped` types for SQLAlchemy 2.0+ or add `# type: ignore` comments
2. Fix BeautifulSoup AttributeValueList issues
3. Fix HTTP params type issues

**Estimated Time**: 1-2 hours  
**Files**: ~10 files  
**Errors Fixed**: ~30+

---

## 📝 Quick Reference: Common Fixes

### Fix Optional Parameter
```python
# Before
def func(param: str = None):
    pass

# After
from typing import Optional
def func(param: Optional[str] = None):
    pass
```

### Fix Missing Type Annotation
```python
# Before
articles = []

# After
from typing import List, Dict, Any
articles: List[Dict[str, Any]] = []
```

### Fix Return Type
```python
# Before
def func() -> Any:
    return {"key": "value"}

# After
def func() -> Dict[str, Any]:
    return {"key": "value"}
```

### Fix None Check
```python
# Before
if obj:
    value = obj.attribute

# After
if obj is not None:
    value = obj.attribute
```

### Fix Type Conversion
```python
# Before
count: int = len(items) * 0.5  # Error: float to int

# After
count: int = int(len(items) * 0.5)  # Explicit conversion
# OR
count: float = len(items) * 0.5  # Change type to float
```

---

## ✅ Verification

After fixing all errors, run:
```bash
mypy src --config-file mypy.ini
```

Expected result: No errors (or only acceptable warnings)

---

## 📚 Related Documentation

- `cleanup/PHASE_6_TYPE_HINTS.md` - Type hints progress
- `cleanup/PHASE_6_COMPLETE_SUMMARY.md` - Phase 6 completion summary
- `mypy.ini` - Mypy configuration file

---

**Last Updated**: 2025-01-02  
**Next Steps**: Continue with Phase 1 (Fix All Optional Types)


