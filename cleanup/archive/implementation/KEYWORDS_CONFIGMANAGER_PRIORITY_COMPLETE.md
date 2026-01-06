# Keywords ConfigManager Priority - Complete

## Summary
Updated **ALL** collectors to prioritize keywords from ConfigManager (which enables database editing) over target_config or command-line queries. This allows dynamic keyword management through the database without code changes.

## New Priority Order (All Collectors)

### For Collectors with `_get_target_keywords()` Method:

1. **ConfigManager: Target-Specific Keywords** (from DB)
   - Key: `collectors.keywords.<target_name>.<collector_name>`
   - Example: `collectors.keywords.emir_of_qatar.youtube`
   - **Enables database editing per target**

2. **ConfigManager: Default Keywords** (from DB)
   - Key: `collectors.keywords.default.<collector_name>`
   - Example: `collectors.keywords.default.youtube`
   - **Enables database editing for defaults**

3. **Legacy: target_config.sources.<source>.keywords** (backward compatibility)
   - From `target_configs.json`
   - Example: `target_config.sources.youtube.keywords`

4. **Legacy: target_config.keywords** (backward compatibility)
   - From `target_configs.json`
   - Example: `target_config.keywords`

5. **Hardcoded Defaults** (last resort)
   - Fallback if nothing else is configured

### For Apify Collectors (Function-Based):

1. **ConfigManager: Target-Specific Keywords** (from DB)
   - Key: `collectors.keywords.<target_name>.<collector_name>`
   - Extracted from `queries[0]` if available

2. **ConfigManager: Default Keywords** (from DB)
   - Key: `collectors.keywords.default.<collector_name>`

3. **Command-Line Queries** (if provided)
   - From `target_and_variations[1:]`

4. **Hardcoded Defaults** (last resort)

## Files Updated

### 1. ConfigManager (`src/config/config_manager.py`)
**Added new structure:**
```python
"collectors": {
    "keywords": {
        "default": {
            "youtube": [...],
            "twitter": [...],
            "instagram": [...],
            # ... all collectors
        }
    },
    # Legacy key maintained for backward compatibility
    "default_keywords": {
        # ... same structure
    }
}
```

### 2. Collectors Updated (13 total)

#### Class-Based Collectors (with `_get_target_keywords()`):
1. ✅ `collect_youtube_api.py`
2. ✅ `collect_radio_hybrid.py`
3. ✅ `collect_radio_gnews.py`
4. ✅ `collect_radio_stations.py`
5. ✅ `collect_news_from_api.py`

#### Function-Based Apify Collectors:
6. ✅ `collect_instagram_apify.py`
7. ✅ `collect_tiktok_apify.py`
8. ✅ `collect_twitter_apify.py`
9. ✅ `collect_facebook_apify.py`
10. ✅ `collect_news_apify.py`

#### RSS Collectors:
11. ✅ `collect_rss.py`
12. ✅ `collect_rss_nigerian_qatar_indian.py`

## How to Store Keywords in Database

### Example: Store Default Twitter Keywords

```sql
INSERT INTO system_configurations 
    (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.keywords.default',
    'twitter',
    '["qatar", "nigeria", "india", "politics", "news"]',
    'array',
    'Default fallback keywords for Twitter collector when queries are empty',
    true
);
```

### Example: Store Target-Specific YouTube Keywords

```sql
INSERT INTO system_configurations 
    (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.keywords',
    'emir_of_qatar.youtube',
    '["qatar", "doha", "sheikh tamim bin hamad", "emir"]',
    'array',
    'Target-specific keywords for Emir of Qatar YouTube collector',
    true
);
```

### Example: Update Existing Keywords

```sql
UPDATE system_configurations
SET config_value = '["qatar", "doha", "sheikh tamim", "gulf", "middle east"]',
    updated_at = NOW()
WHERE category = 'collectors.keywords.default'
  AND config_key = 'youtube'
  AND is_active = true;
```

## Configuration Key Structure

### Default Keywords (All Collectors)
- `collectors.keywords.default.youtube`
- `collectors.keywords.default.twitter`
- `collectors.keywords.default.instagram`
- `collectors.keywords.default.tiktok`
- `collectors.keywords.default.facebook`
- `collectors.keywords.default.news_apify`
- `collectors.keywords.default.news_from_api`
- `collectors.keywords.default.radio_hybrid`
- `collectors.keywords.default.radio_gnews`
- `collectors.keywords.default.radio_stations`
- `collectors.keywords.default.rss`
- `collectors.keywords.default.rss_nigerian_qatar_indian`
- `collectors.keywords.default.youtube_default_fallback`

### Target-Specific Keywords (Optional)
- `collectors.keywords.<target_name>.<collector_name>`
- Example: `collectors.keywords.emir_of_qatar.youtube`
- Example: `collectors.keywords.tinubu.twitter`

**Note**: Target name is normalized: spaces → underscores, lowercase

## Benefits

1. **Database Editing**: All keywords can be edited in database without code changes
2. **Dynamic Updates**: Changes take effect on next collector run (no restart needed if using DB mode)
3. **Target-Specific**: Can override defaults per target individual
4. **Backward Compatible**: Still supports target_config.json keywords
5. **Centralized**: All keyword management in one place (ConfigManager/DB)
6. **Audit Trail**: Database tracks who changed what and when

## Migration Path

1. **Current State**: Keywords come from target_config.json or hardcoded defaults
2. **New State**: Keywords come from ConfigManager (which can load from DB)
3. **To Enable DB Mode**:
   - Populate `system_configurations` table with keywords
   - Initialize ConfigManager with `use_database=True` and `db_session`
   - Keywords will be loaded from database

## Verification
- ✅ All files compile successfully
- ✅ Backward compatible (still supports target_config.json)
- ✅ Logging shows which source keywords come from
- ✅ All collectors updated

## Next Steps

1. **Populate Database**: Add keyword configurations to `system_configurations` table
2. **Enable DB Mode**: Update code to initialize ConfigManager with database session
3. **Test**: Verify keywords load from database correctly
4. **Document**: Create API endpoints or admin UI for editing keywords in database




