# Source-to-Collector Mapping - Moved to ConfigManager

## Summary
The source-to-collector mapping that determines which collector modules to run for each source type has been moved from hardcoded values in `target_config_manager.py` to centralized configuration in `ConfigManager`.

## Changes Made

### 1. ConfigManager (`src/config/config_manager.py`)
**Added new configuration section:**
```python
"collectors": {
    "source_to_collector_mapping": {
        "news": ["collect_news_from_api", "collect_news_apify"],
        "twitter": ["collect_twitter_apify"],
        "facebook": ["collect_facebook_apify"],
        "rss": ["collect_rss_nigerian_qatar_indian"],
        "youtube": ["collect_youtube_api"],
        "radio": ["collect_radio_hybrid"],
        "reddit": ["collect_reddit_apify"],
        "instagram": ["collect_instagram_apify"],
        "tiktok": ["collect_tiktok_apify"],
        "linkedin": ["collect_linkedin"]
    }
}
```

### 2. TargetConfigManager (`src/collectors/target_config_manager.py`)
**Updated `get_enabled_collectors()` method:**
- Now loads mapping from `ConfigManager.get_dict("collectors.source_to_collector_mapping", ...)`
- Falls back to hardcoded defaults if ConfigManager fails
- Maintains backward compatibility

## How It Works

1. **TargetConfigManager.get_enabled_collectors(target_id)**:
   - Gets target config from `target_configs.json`
   - Checks which sources are enabled
   - Loads source-to-collector mapping from ConfigManager
   - Maps enabled sources to collector module names
   - Returns list of collector names (e.g., `["collect_twitter_apify", "collect_news_apify"]`)

2. **Agent Core** (`src/agent/core.py`):
   - Calls `_get_enabled_collectors_for_target(target_name)`
   - Uses the returned collector names to run collectors in parallel

## Benefits

1. **Centralized Configuration**: Mapping can be changed without code modifications
2. **Flexibility**: Easy to add new collectors or change which collectors run for each source
3. **Backward Compatibility**: Falls back to hardcoded defaults if ConfigManager fails
4. **Consistency**: All collector configuration now in one place (ConfigManager)

## Usage Example

```python
# In target_configs.json
{
  "targets": {
    "emir": {
      "sources": {
        "twitter": {"enabled": true},
        "youtube": {"enabled": true}
      }
    }
  }
}

# ConfigManager maps:
# twitter → ["collect_twitter_apify"]
# youtube → ["collect_youtube_api"]

# Result: ["collect_twitter_apify", "collect_youtube_api"]
```

## Verification
- ✅ Code compiles successfully
- ✅ Backward compatible (fallback to defaults)
- ✅ Used by agent/core.py for parallel collector execution




