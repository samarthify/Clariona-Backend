# Quick Start: Adding New Configs

**The simplest way to add new configs to the database.**

---

## ✅ Super Simple Method (SQL)

Just run this SQL query:

```sql
INSERT INTO system_configurations (
    category,
    config_key,
    config_value,
    config_type,
    description,
    default_value,
    is_active
) VALUES (
    'processing',                    -- Category name
    'parallel.max_workers_new',      -- Config key (within category)
    12,                              -- Value
    'int',                           -- Type: 'int', 'float', 'bool', 'string', 'array', 'json'
    'New max workers setting',       -- Description (optional but recommended)
    12,                              -- Default value
    true                             -- Is active
);
```

**That's it!** The config is now in the database and accessible via ConfigManager.

---

## 📝 Type Quick Reference

| Value | config_type | Example |
|-------|-------------|---------|
| Number | `'int'` | `42` |
| Decimal | `'float'` | `3.14` |
| True/False | `'bool'` | `true` |
| Text | `'string'` | `"hello"` |
| List | `'array'` | `[1, 2, 3]` |
| Object | `'json'` | `{"key": "value"}` |

---

## 🔍 Verify It Worked

```python
from src.api.database import SessionLocal
from src.config import ConfigManager

db = SessionLocal()
config = ConfigManager(use_database=True, db_session=db)
value = config.get('processing.parallel.max_workers_new')
print(value)  # Should print: 12
```

Or query the database:

```sql
SELECT * FROM system_configurations 
WHERE category = 'processing' 
  AND config_key = 'parallel.max_workers_new';
```

---

## 📚 For More Details

See `docs/ADDING_NEW_CONFIGS_GUIDE.md` for:
- Multiple methods (SQL, Python, Frontend UI)
- Detailed examples
- Best practices
- Troubleshooting

---

**That's all you need to know!** Adding configs is just inserting a row into the database. 🎉












