# Database-Backed Configuration System Design

**Date**: 2025-01-02  
**Purpose**: Design a database-backed configuration system with frontend UI for non-technical users

---

## 🎯 Overview

**Current System Limitations**:
- ❌ Config stored in JSON files - requires file access and deployment to change
- ❌ No UI for non-technical users to manage configs
- ❌ No audit trail of config changes
- ❌ No user permissions/access control
- ❌ No version history

**Proposed Solution**:
- ✅ Store all configurations in database tables
- ✅ REST API endpoints to read/write config
- ✅ Frontend UI for visual config management
- ✅ Validation on save (using JSON schema)
- ✅ Audit trail and version history
- ✅ User permissions (admin-only or role-based)
- ✅ Backward compatibility with existing ConfigManager

---

## 📊 Database Schema Design

### Option 1: Key-Value Table (Flexible, Simple)

```sql
CREATE TABLE system_configurations (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(255) UNIQUE NOT NULL,  -- e.g., "processing.parallel.max_collector_workers"
    config_value JSONB NOT NULL,              -- Stores any type (int, string, bool, object, array)
    config_type VARCHAR(50) NOT NULL,         -- 'int', 'float', 'bool', 'string', 'json', 'array'
    category VARCHAR(100),                    -- 'processing', 'database', 'api', etc.
    description TEXT,                         -- Human-readable description
    default_value JSONB,                      -- Default value
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),     -- Who last updated
    INDEX idx_config_key (config_key),
    INDEX idx_category (category)
);

-- Audit log for changes
CREATE TABLE configuration_audit_log (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_reason TEXT,
    INDEX idx_config_key (config_key),
    INDEX idx_changed_at (changed_at)
);
```

### Option 2: Hierarchical JSONB Table (Matches Current Structure)

```sql
CREATE TABLE system_configurations (
    id SERIAL PRIMARY KEY,
    config_category VARCHAR(100) NOT NULL,    -- 'processing', 'database', 'api', etc.
    config_data JSONB NOT NULL,               -- Entire category's config as JSON
    schema_version VARCHAR(50) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),
    UNIQUE(config_category),
    INDEX idx_category (config_category)
);

-- Audit log (same as Option 1)
```

### Option 3: Hybrid Approach (Recommended)

```sql
-- Store schema definitions
CREATE TABLE configuration_schemas (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) UNIQUE NOT NULL,    -- 'processing', 'database', etc.
    schema_definition JSONB NOT NULL,         -- JSON schema for validation
    default_values JSONB NOT NULL,            -- Default config values
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Store actual config values (key-value, but organized)
CREATE TABLE system_configurations (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,           -- Foreign key to category
    config_key VARCHAR(255) NOT NULL,         -- e.g., "max_collector_workers" (without category prefix)
    config_value JSONB NOT NULL,
    config_type VARCHAR(50) NOT NULL,
    description TEXT,
    default_value JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),
    FOREIGN KEY (category) REFERENCES configuration_schemas(category),
    UNIQUE(category, config_key),
    INDEX idx_category_key (category, config_key)
);

-- Audit log
CREATE TABLE configuration_audit_log (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    config_key VARCHAR(255) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_reason TEXT
);
```

**Recommendation**: Option 3 (Hybrid) - Best balance of flexibility, validation, and usability

---

## 🔧 Extended ConfigManager Design

### New ConfigManager with DB Support

```python
class ConfigManager:
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        base_path: Optional[Path] = None,
        validate: bool = True,
        use_database: bool = False,  # NEW: Enable DB-backed config
        db_session: Optional[Session] = None  # NEW: DB session
    ):
        """
        Load configuration from:
        1. Default values (hardcoded)
        2. JSON config files (fallback if DB not available)
        3. Database (if use_database=True)
        4. Environment variables (highest priority, always override)
        """
        self.use_database = use_database
        self.db_session = db_session
        
        # Load from DB if enabled, otherwise from files
        if use_database and db_session:
            self._load_from_database()
        else:
            self._load_from_files()
        
        # Environment variables always override (last)
        self._apply_env_overrides()
        
        # Validate
        if validate:
            self._validate_config()
    
    def _load_from_database(self):
        """Load configuration from database."""
        from .models import SystemConfiguration
        
        query = self.db_session.query(SystemConfiguration).filter(
            SystemConfiguration.is_active == True
        )
        
        configs = query.all()
        
        # Build config dict from DB records
        for config in configs:
            # Set nested value using dot notation
            full_key = f"{config.category}.{config.config_key}"
            self._set_nested(full_key, config.config_value)
    
    def save_to_database(self, key: str, value: Any, user_id: Optional[UUID] = None):
        """Save a config value to database."""
        from .models import SystemConfiguration, ConfigurationAuditLog
        
        # Parse key (e.g., "processing.parallel.max_collector_workers")
        parts = key.split('.')
        category = parts[0]
        config_key = '.'.join(parts[1:])
        
        # Get or create config record
        config = self.db_session.query(SystemConfiguration).filter(
            SystemConfiguration.category == category,
            SystemConfiguration.config_key == config_key
        ).first()
        
        old_value = config.config_value if config else None
        
        if config:
            # Update existing
            config.config_value = value
            config.updated_by = user_id
            config.updated_at = datetime.utcnow()
        else:
            # Create new
            config = SystemConfiguration(
                category=category,
                config_key=config_key,
                config_value=value,
                config_type=self._infer_type(value),
                updated_by=user_id
            )
            self.db_session.add(config)
        
        # Audit log
        audit = ConfigurationAuditLog(
            category=category,
            config_key=config_key,
            old_value=old_value,
            new_value=value,
            changed_by=user_id
        )
        self.db_session.add(audit)
        
        self.db_session.commit()
        
        # Reload config
        self.reload()
```

---

## 🌐 API Endpoints Design

```python
# src/api/config_service.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/config", tags=["configuration"])

class ConfigValue(BaseModel):
    key: str
    value: Any
    type: str
    description: Optional[str] = None

class ConfigCategory(BaseModel):
    category: str
    configs: List[ConfigValue]

# GET /api/config - Get all configurations
@router.get("/", response_model=List[ConfigCategory])
async def get_all_configs(
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get all configurations (admin only or read-only access)"""
    # Check permissions
    if not is_admin(user_id):
        raise HTTPException(403, "Admin access required")
    
    # Query database
    # Return organized by category
    
# GET /api/config/{category} - Get config by category
@router.get("/{category}", response_model=ConfigCategory)
async def get_config_category(
    category: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get configurations for a specific category"""
    
# GET /api/config/{category}/{key} - Get single config value
@router.get("/{category}/{key:path}")
async def get_config_value(
    category: str,
    key: str,
    db: Session = Depends(get_db)
):
    """Get a single configuration value"""
    config_manager = ConfigManager(use_database=True, db_session=db)
    full_key = f"{category}.{key}"
    return {"key": full_key, "value": config_manager.get(full_key)}

# PUT /api/config/{category}/{key} - Update single config value
@router.put("/{category}/{key:path}")
async def update_config_value(
    category: str,
    key: str,
    value: Any,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Update a configuration value (admin only)"""
    if not is_admin(user_id):
        raise HTTPException(403, "Admin access required")
    
    config_manager = ConfigManager(use_database=True, db_session=db)
    full_key = f"{category}.{key}"
    
    # Validate value (using schema)
    if not config_manager._validate_value(full_key, value):
        raise HTTPException(400, "Invalid value")
    
    # Save to database
    config_manager.save_to_database(full_key, value, user_id, reason)
    
    return {"success": True, "key": full_key, "value": value}

# POST /api/config/bulk - Update multiple configs
@router.post("/bulk")
async def update_configs_bulk(
    updates: List[ConfigValue],
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Update multiple configuration values at once"""
    
# GET /api/config/audit - Get audit log
@router.get("/audit")
async def get_config_audit_log(
    category: Optional[str] = None,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get configuration change audit log (admin only)"""

# POST /api/config/reset/{category} - Reset category to defaults
@router.post("/reset/{category}")
async def reset_config_category(
    category: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Reset a category's config to default values"""
```

---

## 🎨 Frontend UI Design

### Features Needed:

1. **Configuration Dashboard**
   - List all configuration categories
   - Visual cards/tabs for each category
   - Search/filter functionality

2. **Category View**
   - Display all configs in a category
   - Organized sections (e.g., "Parallel Processing", "Timeouts", "Limits")
   - Form inputs based on config type:
     - Number inputs for int/float
     - Text inputs for strings
     - Checkboxes for booleans
     - JSON editor for complex objects
     - Array editor for lists

3. **Validation Feedback**
   - Real-time validation as user types
   - Show min/max constraints
   - Show description/help text
   - Error messages for invalid values

4. **Save & Reload**
   - Save button per category or per config
   - "Apply Changes" button with confirmation
   - Option to reload config without saving
   - Success/error notifications

5. **Audit Trail**
   - View change history
   - Who changed what and when
   - Ability to revert to previous values
   - Export audit log

6. **Permissions**
   - Admin-only access (or role-based)
   - Read-only view for non-admins
   - Permission checks before save

### Example Frontend Components (React/Vue):

```tsx
// ConfigurationCategory.tsx
<Card title="Processing Configuration">
  <ConfigSection title="Parallel Processing">
    <ConfigInput
      label="Max Collector Workers"
      key="processing.parallel.max_collector_workers"
      type="number"
      min={1}
      max={50}
      description="Maximum number of collector worker threads"
      value={config.processing.parallel.max_collector_workers}
      onChange={handleChange}
    />
    {/* More inputs... */}
  </ConfigSection>
  
  <Button onClick={handleSave}>Save Changes</Button>
</Card>
```

---

## 🔄 Migration Strategy

### Phase 1: Dual Mode (Backward Compatible)
- ConfigManager supports both file-based and DB-based config
- Use `use_database` flag to choose mode
- Files serve as fallback if DB not available
- Existing code continues to work

### Phase 2: Initial Data Migration
- Script to migrate existing JSON configs to database
- Populate `configuration_schemas` table from `config.schema.json`
- Populate `system_configurations` from current config files

### Phase 3: API & Frontend
- Create API endpoints
- Build frontend UI
- Test with real users

### Phase 4: Full Migration
- Switch default to DB mode
- Keep file support for backwards compatibility
- Document new system

---

## ✅ Benefits

1. **Non-Technical Users**: Manage configs through UI without code knowledge
2. **Audit Trail**: Track all changes with user attribution
3. **Validation**: Enforce schema rules at save time
4. **Permissions**: Control who can change what
5. **Version History**: Revert to previous values
6. **Multi-Environment**: Different configs per environment (dev/staging/prod)
7. **Real-time Updates**: Changes take effect immediately (with reload)
8. **Better UX**: Visual forms instead of JSON editing

---

## 🚀 Implementation Priority

**High Priority** (Phase 3 enhancement):
1. Database schema creation
2. Extended ConfigManager with DB support
3. API endpoints for config management
4. Initial data migration script

**Medium Priority**:
5. Frontend UI for config management
6. Audit log viewer
7. Permission system integration

**Low Priority**:
8. Config templates/presets
9. Export/import configs
10. Multi-environment support

---

## 📝 Next Steps

1. **Create database models** (`src/api/models.py`)
2. **Extend ConfigManager** to support database backend
3. **Create migration script** to populate initial config data
4. **Create API endpoints** (`src/api/config_service.py`)
5. **Build frontend UI** (separate frontend project or API docs)
6. **Update documentation**

Would you like me to start implementing this? I can begin with:
1. Database models
2. Extended ConfigManager
3. API endpoints
4. Migration script












