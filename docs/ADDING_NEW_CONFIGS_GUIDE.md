# Guide: Adding New Configuration Values to Database

**Date**: 2025-01-02  
**Purpose**: Step-by-step guide for adding new configuration values to the database

---

## 🎯 Overview

This guide shows you how to add new configuration values to the `system_configurations` table. There are multiple ways to do this depending on your needs.

---

## 📋 Methods

### Method 1: Add via SQL (Quick & Simple)

**Best for**: Adding a few configs manually, testing, or one-off additions

```sql
-- Example: Add a new timeout config
INSERT INTO system_configurations (
    category,
    config_key,
    config_value,
    config_type,
    description,
    default_value,
    is_active
) VALUES (
    'processing',
    'timeouts.new_timeout_seconds',
    '300',
    'int',
    'Timeout for new operation in seconds',
    '300',
    true
);
```

**Key Points**:
- `category` - The top-level category (e.g., 'processing', 'database', 'api')
- `config_key` - The full key path within the category (can include dots for nesting)
- `config_value` - The actual value (JSONB, so you can store JSON for complex values)
- `config_type` - One of: 'int', 'float', 'bool', 'string', 'array', 'json'
- Use `default_value` to store the default so you can reset later

---

### Method 2: Add via Python Script (Recommended for Multiple Configs)

**Best for**: Adding multiple configs, programmatic addition, or when you want validation

Create a script (e.g., `scripts/add_config.py`):

```python
"""
Script to add new configuration values to database.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import SystemConfiguration

def add_config(
    category: str,
    config_key: str,
    config_value: any,
    config_type: str,
    description: str = None,
    default_value: any = None
):
    """Add a new configuration value."""
    db = SessionLocal()
    try:
        # Check if exists
        existing = db.query(SystemConfiguration).filter(
            SystemConfiguration.category == category,
            SystemConfiguration.config_key == config_key
        ).first()
        
        if existing:
            print(f"Config already exists: {category}.{config_key}")
            return
        
        # Create new config
        config = SystemConfiguration(
            category=category,
            config_key=config_key,
            config_value=config_value,
            config_type=config_type,
            description=description,
            default_value=default_value or config_value,
            is_active=True
        )
        
        db.add(config)
        db.commit()
        print(f"Added: {category}.{config_key} = {config_value}")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

# Example usage
if __name__ == '__main__':
    # Add a new config
    add_config(
        category='processing',
        config_key='timeouts.new_timeout_seconds',
        config_value=300,
        config_type='int',
        description='Timeout for new operation in seconds',
        default_value=300
    )
```

**Run it**:
```bash
python scripts/add_config.py
```

---

### Method 3: Add via Frontend UI (Once Built)

**Best for**: Non-technical users, regular operations

Once the frontend UI is built:
1. Navigate to the configuration page
2. Select the appropriate category
3. Click "Add New Config" button
4. Fill in the form:
   - Key: `timeouts.new_timeout_seconds`
   - Value: `300`
   - Type: `int`
   - Description: `Timeout for new operation in seconds`
5. Click "Save"

---

### Method 4: Update ConfigManager Defaults + Re-run Population Script

**Best for**: Adding configs that should be part of the default system

1. **Update ConfigManager defaults** (`src/config/config_manager.py`):

```python
def _get_default_config(self) -> Dict[str, Any]:
    return {
        # ... existing configs ...
        "processing": {
            # ... existing processing configs ...
            "timeouts": {
                # ... existing timeouts ...
                "new_timeout_seconds": 300  # NEW CONFIG
            }
        }
    }
```

2. **Re-run population script**:

```bash
python scripts/populate_config_database.py
```

This will:
- Detect new configs in defaults
- Add them to database if they don't exist
- Update existing configs if values changed
- Skip configs that already exist in DB

---

## 📝 Step-by-Step Examples

### Example 1: Add a Simple Integer Config

**Goal**: Add `processing.parallel.max_workers_override` = 12

**SQL Method**:
```sql
INSERT INTO system_configurations (
    category, config_key, config_value, config_type, description, default_value, is_active
) VALUES (
    'processing',
    'parallel.max_workers_override',
    '12',
    'int',
    'Override for maximum workers (0 = use default)',
    '0',
    true
);
```

**Python Method**:
```python
from src.api.database import SessionLocal
from src.api.models import SystemConfiguration

db = SessionLocal()
config = SystemConfiguration(
    category='processing',
    config_key='parallel.max_workers_override',
    config_value=12,
    config_type='int',
    description='Override for maximum workers (0 = use default)',
    default_value=0
)
db.add(config)
db.commit()
```

---

### Example 2: Add a Boolean Config

**Goal**: Add `api.enable_rate_limiting` = true

```sql
INSERT INTO system_configurations (
    category, config_key, config_value, config_type, description, default_value, is_active
) VALUES (
    'api',
    'enable_rate_limiting',
    'true',
    'bool',
    'Enable API rate limiting',
    'true',
    true
);
```

---

### Example 3: Add a String Config

**Goal**: Add `logging.log_level` = "INFO"

```sql
INSERT INTO system_configurations (
    category, config_key, config_value, config_type, description, default_value, is_active
) VALUES (
    'logging',
    'log_level',
    '"INFO"',
    'string',
    'Logging level (DEBUG, INFO, WARNING, ERROR)',
    '"INFO"',
    true
);
```

---

### Example 4: Add an Array Config

**Goal**: Add `api.allowed_ips` = ["127.0.0.1", "192.168.1.1"]

```sql
INSERT INTO system_configurations (
    category, config_key, config_value, config_type, description, default_value, is_active
) VALUES (
    'api',
    'allowed_ips',
    '["127.0.0.1", "192.168.1.1"]',
    'array',
    'List of allowed IP addresses',
    '[]',
    true
);
```

**Note**: For JSONB columns, use JSON format string or JSONB literal.

---

### Example 5: Add a Complex Object Config

**Goal**: Add a nested object config

```sql
INSERT INTO system_configurations (
    category, config_key, config_value, config_type, description, default_value, is_active
) VALUES (
    'processing',
    'retry_policy',
    '{"max_retries": 3, "backoff_multiplier": 2, "initial_delay": 1}',
    'json',
    'Retry policy configuration',
    '{"max_retries": 3, "backoff_multiplier": 2, "initial_delay": 1}',
    true
);
```

---

## 🔧 Helper Functions

### Type Inference

When adding configs, use these type mappings:

| Python Type | config_type | JSONB Example |
|------------|-------------|---------------|
| `int` | `'int'` | `42` |
| `float` | `'float'` | `3.14` |
| `bool` | `'bool'` | `true` |
| `str` | `'string'` | `"hello"` |
| `list` | `'array'` | `[1, 2, 3]` |
| `dict` | `'json'` | `{"key": "value"}` |

### Infer Type Function

```python
def infer_type(value: Any) -> str:
    """Infer config_type from Python value."""
    if isinstance(value, bool):
        return 'bool'
    elif isinstance(value, int):
        return 'int'
    elif isinstance(value, float):
        return 'float'
    elif isinstance(value, str):
        return 'string'
    elif isinstance(value, list):
        return 'array'
    elif isinstance(value, dict):
        return 'json'
    else:
        return 'string'  # Default
```

---

## ✅ Verification

After adding configs, verify they work:

```python
from src.api.database import SessionLocal
from src.config import ConfigManager

db = SessionLocal()
config = ConfigManager(use_database=True, db_session=db)

# Try to access your new config
value = config.get('processing.timeouts.new_timeout_seconds')
print(f"New config value: {value}")
```

Or query database directly:

```sql
SELECT * FROM system_configurations 
WHERE category = 'processing' 
  AND config_key LIKE '%new_timeout%';
```

---

## 🔄 Updating Existing Configs

### Update Value

```sql
UPDATE system_configurations
SET config_value = '500',
    updated_at = NOW()
WHERE category = 'processing'
  AND config_key = 'timeouts.new_timeout_seconds';
```

### Deactivate Config (Soft Delete)

```sql
UPDATE system_configurations
SET is_active = false
WHERE category = 'processing'
  AND config_key = 'timeouts.new_timeout_seconds';
```

### Reactivate Config

```sql
UPDATE system_configurations
SET is_active = true
WHERE category = 'processing'
  AND config_key = 'timeouts.new_timeout_seconds';
```

---

## 📚 Best Practices

1. **Use Descriptive Keys**: 
   - ✅ Good: `processing.timeouts.collector_timeout_seconds`
   - ❌ Bad: `timeout1`

2. **Always Set Description**: Helps users understand what the config does

3. **Set Default Values**: Makes it easy to reset configs later

4. **Use Appropriate Types**: Don't store numbers as strings

5. **Group Related Configs**: Use consistent category names

6. **Document in Code**: If adding to ConfigManager defaults, add comments

7. **Test After Adding**: Verify the config is accessible via ConfigManager

---

## 🚨 Common Issues

### Issue: Config not showing up in ConfigManager

**Solution**: 
- Check `is_active = true`
- Verify category and config_key match exactly
- Make sure ConfigManager is using `use_database=True`
- Check for typos in category/key

### Issue: Type mismatch

**Solution**: 
- Ensure `config_type` matches the actual value type
- For JSONB, use proper JSON format
- Check that config_value is valid JSONB

### Issue: Duplicate key error

**Solution**: 
- Check if config already exists: `SELECT * FROM system_configurations WHERE category = '...' AND config_key = '...'`
- Update existing instead of inserting new
- Or delete old one first

---

## 📝 Summary Checklist

When adding a new config:

- [ ] Decide on category and key name
- [ ] Determine appropriate config_type
- [ ] Write description
- [ ] Set default_value
- [ ] Insert into database (via SQL, Python, or UI)
- [ ] Verify it appears in queries
- [ ] Test accessing via ConfigManager
- [ ] (Optional) Update ConfigManager defaults for future migrations
- [ ] (Optional) Update schema documentation

---

## 🔗 Related Documentation

- `docs/FRONTEND_CONFIG_MANAGEMENT_GUIDE.md` - Frontend implementation guide
- `docs/DATABASE_CONFIG_SYSTEM_SUMMARY.md` - System overview
- `docs/DATABASE_CONFIGURATION_SYSTEM_DESIGN.md` - Design document

---

**That's it!** Adding new configs is as simple as inserting a row into the `system_configurations` table. The system is designed to be flexible and easy to extend.












