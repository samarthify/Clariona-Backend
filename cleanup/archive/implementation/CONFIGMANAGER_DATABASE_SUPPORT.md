# ConfigManager Database Support

## Overview
`ConfigManager` was implemented to support loading configuration from a **database table** (`SystemConfiguration`) in addition to JSON files and environment variables. This allows for dynamic configuration management without code changes.

## Database Table: `SystemConfiguration`

**Table Name**: `system_configurations`

**Schema** (from `src/api/models.py`):
```python
class SystemConfiguration(Base):
    __tablename__ = 'system_configurations'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(100), nullable=False, index=True)      # e.g., "collectors"
    config_key = Column(String(255), nullable=False)                 # e.g., "default_max_items"
    config_value = Column(JSONB, nullable=False)                     # The actual value (any type)
    config_type = Column(String(50), nullable=False)                  # 'int', 'float', 'bool', 'string', 'json', 'array'
    description = Column(Text)                                         # Optional description
    default_value = Column(JSONB)                                     # Default value if not set
    is_active = Column(Boolean, default=True)                         # Enable/disable config
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        UniqueConstraint('category', 'config_key', name='uq_category_config_key'),
        Index('idx_category_key', 'category', 'config_key'),
    )
```

## How It Works

### 1. Initialization

```python
from config.config_manager import ConfigManager
from src.api.database import SessionLocal

# With database support
db_session = SessionLocal()
config = ConfigManager(use_database=True, db_session=db_session)

# Without database (default - uses files)
config = ConfigManager()  # use_database=False by default
```

### 2. Configuration Loading Priority

ConfigManager loads configuration in this order (later sources override earlier ones):

1. **Default values** (hardcoded in `_get_default_config()`)
2. **JSON config files** (`config/agent_config.json`, etc.)
3. **Database** (`SystemConfiguration` table) - **if `use_database=True`**
4. **Environment variables** (highest priority, always applied)

### 3. Database Loading Logic

**File**: `src/config/config_manager.py` → `_load_from_database()`

```python
def _load_from_database(self):
    """Load configuration from database."""
    from src.api.models import SystemConfiguration
    
    # Query all active configurations
    query = self.db_session.query(SystemConfiguration).filter(
        SystemConfiguration.is_active == True
    )
    configs = query.all()
    
    # Build config dict from DB records
    for config in configs:
        # Set nested value using dot notation (category.key)
        full_key = f"{config.category}.{config.config_key}"
        value = config.config_value
        self._set_nested(full_key, value)
```

**Key Points**:
- Only loads configurations where `is_active = True`
- Uses dot notation: `category.config_key` → `category.config_key` in config dict
- Example: `category="collectors"`, `config_key="default_max_items"` → `collectors.default_max_items`

### 4. Example Database Records

To store configuration in the database:

```sql
-- Example: Set Twitter default max items
INSERT INTO system_configurations (category, config_key, config_value, config_type, is_active)
VALUES ('collectors', 'default_max_items', '200', 'int', true);

-- Example: Set default keywords (array)
INSERT INTO system_configurations (category, config_key, config_value, config_type, is_active)
VALUES ('collectors.default_keywords', 'twitter', '["qatar", "nigeria", "politics"]', 'array', true);

-- Example: Set nested config (JSON object)
INSERT INTO system_configurations (category, config_key, config_value, config_type, is_active)
VALUES ('collectors', 'source_to_collector_mapping', 
        '{"twitter": ["collect_twitter_apify"], "youtube": ["collect_youtube_api"]}', 
        'json', true);
```

### 5. Accessing Configuration

```python
# Works the same whether loaded from DB or files
config = ConfigManager(use_database=True, db_session=db_session)

# Get value (checks DB if use_database=True, otherwise files)
max_items = config.get_int("collectors.twitter.default_max_items", 100)
keywords = config.get_list("collectors.default_keywords.twitter", [])
```

## Current Usage

**Important**: Currently, `ConfigManager` is **NOT** being used with database mode in the codebase. All instances use the default file-based mode:

```python
# Current usage (file-based)
config = ConfigManager()  # use_database=False by default
```

**Why?**
- Database mode requires a `db_session` parameter
- Most code doesn't have database session available at ConfigManager initialization
- File-based mode is simpler and works for most use cases

## Benefits of Database Mode

1. **Dynamic Configuration**: Change config values without code deployment
2. **User Management**: Track who changed what (`updated_by` field)
3. **Audit Trail**: `ConfigurationAuditLog` table tracks all changes
4. **Environment-Specific**: Different configs for dev/staging/prod
5. **Runtime Updates**: Can reload config from DB without restarting

## Migration Path

To use database mode, you would need to:

1. **Initialize with DB session**:
```python
from src.api.database import SessionLocal
db = SessionLocal()
config = ConfigManager(use_database=True, db_session=db)
```

2. **Populate database** with configuration values:
   - Migrate existing JSON config to database
   - Or use database as override layer (keep JSON for defaults)

3. **Update code** that creates ConfigManager instances to pass `db_session`

## New Configuration Keys Added

All the new configuration keys we added in Phase 5 can be stored in the database:

- `collectors.default_keywords.*` (all keyword defaults)
- `collectors.source_to_collector_mapping.*` (source mappings)
- `collectors.timeouts.*` (timeout values)
- `collectors.retries.*` (retry counts)
- `collectors.apify.*` (Apify-specific configs)
- `collectors.incremental.*` (incremental collection settings)

**Example**:
```sql
-- Store default Twitter keywords in database
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active)
VALUES (
    'collectors.default_keywords',
    'twitter',
    '["qatar", "nigeria", "india", "politics", "news"]',
    'array',
    'Default fallback keywords for Twitter collector when queries are empty',
    true
);
```

## Summary

- ✅ ConfigManager **supports** database storage via `SystemConfiguration` table
- ✅ Database mode is **optional** (default is file-based)
- ✅ Currently **not used** in production (all instances use file-based mode)
- ✅ Can be **enabled** by passing `use_database=True` and `db_session` to ConfigManager
- ✅ All new Phase 5 config keys **can be stored** in database if needed




