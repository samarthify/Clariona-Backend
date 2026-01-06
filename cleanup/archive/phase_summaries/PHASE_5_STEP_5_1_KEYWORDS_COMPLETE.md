# Phase 5, Step 5.1: Keywords Replacement - Complete

## Summary
Replaced all hardcoded fallback keywords in collectors with centralized configuration values from `ConfigManager`.

## Files Updated

### 1. Configuration (`src/config/config_manager.py`)
**Added new configuration section:**
- `collectors.default_keywords.youtube`: Default YouTube keywords
- `collectors.default_keywords.youtube_default_fallback`: Default fallback for YouTube target variations
- `collectors.default_keywords.radio_hybrid`: Default radio hybrid keywords
- `collectors.default_keywords.radio_gnews`: Default GNews radio keywords
- `collectors.default_keywords.radio_stations`: Default radio stations keywords
- `collectors.default_keywords.rss`: Default RSS keywords
- `collectors.default_keywords.rss_nigerian_qatar_indian`: Default RSS Nigerian/Qatar/Indian keywords
- `collectors.default_keywords.news_from_api`: Default news-from-api keywords

### 2. Collectors Updated

#### `src/collectors/collect_youtube_api.py`
- **Line 170**: Replaced `["emir", "amir", "sheikh tamim", "al thani"]` with `config.get_list("collectors.default_keywords.youtube", ...)`
- **Line 209**: Replaced hardcoded keywords in `_should_include_video()` with config lookup
- **Line 416**: Replaced `["emir"]` default fallback with `config.get_list("collectors.default_keywords.youtube_default_fallback", ...)`

#### `src/collectors/collect_radio_hybrid.py`
- **Line 281**: Replaced `["nigeria", "government", "politics", "economy", "news"]` with `config.get_list("collectors.default_keywords.radio_hybrid", ...)`

#### `src/collectors/collect_radio_gnews.py`
- **Line 138**: Replaced `["nigeria", "government", "politics", "economy", "news"]` with `config.get_list("collectors.default_keywords.radio_gnews", ...)`

#### `src/collectors/collect_radio_stations.py`
- **Line 131**: Replaced `["nigeria", "government", "politics", "economy", "news"]` with `config.get_list("collectors.default_keywords.radio_stations", ...)`

#### `src/collectors/collect_rss.py`
- **Lines 452-455**: Replaced hardcoded default keywords list with `config.get_list("collectors.default_keywords.rss", ...)`

#### `src/collectors/collect_rss_nigerian_qatar_indian.py`
- **Lines 605-609**: Replaced hardcoded default keywords list with `config.get_list("collectors.default_keywords.rss_nigerian_qatar_indian", ...)`

#### `src/collectors/collect_news_from_api.py`
- **Lines 69-78**: Replaced hardcoded keyword list with config lookup, with fallback to target config keywords first

## Statistics
- **Files Updated**: 8 files
- **Hardcoded Keyword Lists Replaced**: 8 locations
- **New Config Keys Added**: 8 keys
- **Backward Compatibility**: All defaults match original hardcoded values

## Notes

### Keywords Not Replaced (Intentionally)
1. **Example/Test Keywords**: Keywords in example documentation (Instagram, TikTok) and test code (`configurable_collector.py`, `collect_radio_gnews.py` test queries) were left as-is since they're not production code.

2. **Country Detection Keywords**: Keywords used for country detection heuristics (e.g., in `collect_instagram_apify.py` line 448) were left as-is since they're domain-specific detection logic.

3. **Content Filtering Keywords**: The large keyword lists in `collect_radio_hybrid.py` (lines 510-518, 549-557) used for filtering news content were left as-is. These are domain-specific filtering keywords, not fallback keywords. They could be made configurable in a future enhancement if needed.

## Verification
- ✅ All files compile successfully
- ✅ No linter errors
- ✅ Backward compatible (defaults match original values)

## Next Steps
Continue with remaining Step 5.1 tasks or proceed to Step 5.2 (Replace Hardcoded Timeouts & Limits).




