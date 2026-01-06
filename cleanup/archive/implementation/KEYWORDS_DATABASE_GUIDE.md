# Keywords Database Storage Guide

## Overview
All collectors now prioritize keywords from ConfigManager, which can load from the `system_configurations` database table. This enables **dynamic keyword editing** without code changes or deployments.

## Database Table: `system_configurations`

**Schema**:
- `category`: String (e.g., `"collectors.keywords.default"` or `"collectors.keywords"`)
- `config_key`: String (e.g., `"youtube"` or `"emir_of_qatar.youtube"`)
- `config_value`: JSONB (array of strings for keywords)
- `config_type`: String (must be `"array"` for keywords)
- `is_active`: Boolean (must be `true` to be loaded)
- `description`: Text (optional, for documentation)

## Configuration Key Structure

### Default Keywords (All Collectors)
**Category**: `collectors.keywords.default`  
**Config Key**: `<collector_name>`

**Supported Collectors**:
- `youtube`
- `twitter`
- `instagram`
- `tiktok`
- `facebook`
- `news_apify`
- `news_from_api`
- `radio_hybrid`
- `radio_gnews`
- `radio_stations`
- `rss`
- `rss_nigerian_qatar_indian`
- `youtube_default_fallback`

### Target-Specific Keywords (Optional Override)
**Category**: `collectors.keywords`  
**Config Key**: `<target_name>.<collector_name>`

**Example**: `emir_of_qatar.youtube`

**Note**: Target names are normalized:
- Spaces → underscores
- Lowercase
- Example: "Emir of Qatar" → `emir_of_qatar`

## SQL Examples

### 1. Store Default YouTube Keywords

```sql
INSERT INTO system_configurations 
    (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.keywords.default',
    'youtube',
    '["emir", "amir", "sheikh tamim", "al thani", "qatar", "doha"]',
    'array',
    'Default fallback keywords for YouTube collector when no target-specific keywords are configured',
    true
);
```

### 2. Store Default Twitter Keywords

```sql
INSERT INTO system_configurations 
    (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.keywords.default',
    'twitter',
    '["qatar", "nigeria", "india", "politics", "news", "government"]',
    'array',
    'Default fallback keywords for Twitter collector when queries are empty',
    true
);
```

### 3. Store Target-Specific Keywords (Emir of Qatar - YouTube)

```sql
INSERT INTO system_configurations 
    (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.keywords',
    'emir_of_qatar.youtube',
    '["qatar", "doha", "sheikh tamim bin hamad", "emir", "amir", "al thani"]',
    'array',
    'Target-specific keywords for Emir of Qatar YouTube collector (overrides defaults)',
    true
);
```

### 4. Store Target-Specific Keywords (Tinubu - Twitter)

```sql
INSERT INTO system_configurations 
    (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.keywords',
    'tinubu.twitter',
    '["tinubu", "bola tinubu", "president tinubu", "nigeria", "nigerian president"]',
    'array',
    'Target-specific keywords for Tinubu Twitter collector (overrides defaults)',
    true
);
```

### 5. Update Existing Keywords

```sql
UPDATE system_configurations
SET config_value = '["qatar", "doha", "sheikh tamim", "gulf", "middle east", "emir"]',
    updated_at = NOW(),
    description = 'Updated default YouTube keywords - added gulf and middle east'
WHERE category = 'collectors.keywords.default'
  AND config_key = 'youtube'
  AND is_active = true;
```

### 6. Disable Keywords (Soft Delete)

```sql
UPDATE system_configurations
SET is_active = false,
    updated_at = NOW()
WHERE category = 'collectors.keywords.default'
  AND config_key = 'youtube';
```

### 7. Bulk Insert All Default Keywords

```sql
-- YouTube
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'youtube', '["emir", "amir", "sheikh tamim", "al thani"]', 'array', 'Default YouTube keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- Twitter
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'twitter', '["qatar", "nigeria", "india", "politics", "news"]', 'array', 'Default Twitter keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- Instagram
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'instagram', '["qatar", "doha", "sheikh tamim", "nigeria", "lagos", "abuja"]', 'array', 'Default Instagram keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- TikTok
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'tiktok', '["nigeria", "tinubu", "lagos", "qatar", "doha"]', 'array', 'Default TikTok keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- Facebook
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'facebook', '["qatar", "nigeria", "india", "news", "politics"]', 'array', 'Default Facebook keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- News Apify
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'news_apify', '["qatar", "nigeria", "india", "politics", "news", "government"]', 'array', 'Default News Apify keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- News from API
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'news_from_api', '["Asiwaju Bola Ahmed Adekunle Tinubu", "President of the Federal Republic of Nigeria", "Bola Tinubu", "Bola Ahmed Tinubu", "President of Nigeria", "Tinubu", "Bola", "nigeria"]', 'array', 'Default News from API keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- Radio Hybrid
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'radio_hybrid', '["nigeria", "government", "politics", "economy", "news"]', 'array', 'Default Radio Hybrid keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- Radio GNews
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'radio_gnews', '["nigeria", "government", "politics", "economy", "news"]', 'array', 'Default Radio GNews keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- Radio Stations
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'radio_stations', '["nigeria", "government", "politics", "economy", "news"]', 'array', 'Default Radio Stations keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- RSS
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'rss', '["middle east", "qatar", "nigeria", "gulf", "arab", "islamic", "oil", "energy", "politics", "diplomacy", "trade", "business"]', 'array', 'Default RSS keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();

-- RSS Nigerian/Qatar/Indian
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES ('collectors.keywords.default', 'rss_nigerian_qatar_indian', '["nigeria", "qatar", "india", "africa", "middle east", "gulf", "arab", "nigerian", "qatari", "indian", "politics", "business", "economy", "oil", "gas", "energy", "trade", "diplomacy"]', 'array', 'Default RSS Nigerian/Qatar/Indian keywords', true)
ON CONFLICT (category, config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW();
```

## Query Examples

### View All Keyword Configurations

```sql
SELECT 
    category,
    config_key,
    config_value,
    description,
    is_active,
    updated_at
FROM system_configurations
WHERE category LIKE 'collectors.keywords%'
ORDER BY category, config_key;
```

### View Default Keywords for All Collectors

```sql
SELECT 
    config_key AS collector_name,
    config_value AS keywords,
    description,
    updated_at
FROM system_configurations
WHERE category = 'collectors.keywords.default'
  AND is_active = true
ORDER BY config_key;
```

### View Target-Specific Keywords

```sql
SELECT 
    config_key AS target_collector,
    config_value AS keywords,
    description,
    updated_at
FROM system_configurations
WHERE category = 'collectors.keywords'
  AND is_active = true
ORDER BY config_key;
```

### Find Keywords for Specific Collector

```sql
-- Default keywords
SELECT config_value
FROM system_configurations
WHERE category = 'collectors.keywords.default'
  AND config_key = 'youtube'
  AND is_active = true;

-- Target-specific keywords
SELECT config_value
FROM system_configurations
WHERE category = 'collectors.keywords'
  AND config_key LIKE '%.youtube'
  AND is_active = true;
```

## Priority Resolution

When a collector requests keywords, ConfigManager resolves them in this order:

1. **Target-Specific** (from DB): `collectors.keywords.<target_name>.<collector>`
2. **Default** (from DB): `collectors.keywords.default.<collector>`
3. **Legacy target_config**: From `target_configs.json` (backward compatibility)
4. **Hardcoded**: Fallback defaults in code

## Enabling Database Mode

To use database-stored keywords, initialize ConfigManager with database support:

```python
from config.config_manager import ConfigManager
from src.api.database import SessionLocal

# Get database session
db_session = SessionLocal()

# Initialize ConfigManager with database mode
config = ConfigManager(use_database=True, db_session=db_session)

# Keywords will now be loaded from database
keywords = config.get_list("collectors.keywords.default.youtube", [])
```

**Note**: Currently, all ConfigManager instances use file-based mode (default). To enable database mode, you would need to:
1. Pass `use_database=True` and `db_session` when creating ConfigManager
2. Ensure `system_configurations` table is populated with keywords

## Benefits

1. **Dynamic Editing**: Change keywords without code deployment
2. **Target-Specific**: Override defaults per target individual
3. **Audit Trail**: Track who changed what and when
4. **Environment-Specific**: Different keywords for dev/staging/prod
5. **Runtime Updates**: Changes take effect on next collector run

## Migration Checklist

- [x] Updated all collectors to prioritize ConfigManager keywords
- [x] Added new `collectors.keywords.default.*` structure
- [x] Maintained backward compatibility with `default_keywords.*`
- [x] Added target-specific keyword support
- [ ] Populate database with default keywords
- [ ] Enable database mode in ConfigManager initialization
- [ ] Create admin UI/API for keyword management
- [ ] Test database keyword loading




