# Frontend Configuration Management Guide

**Date**: 2025-01-02  
**Purpose**: Guide for building a frontend UI to manage system configurations stored in database

---

## 🎯 Overview

The backend stores all system configurations in database tables. The frontend should query these tables directly and provide a user-friendly interface for non-technical users to manage configurations.

---

## 📊 Database Schema

### Tables to Query

#### 1. `system_configurations`
Main table storing configuration values.

**Schema**:
```sql
CREATE TABLE system_configurations (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,           -- e.g., 'processing', 'database', 'api'
    config_key VARCHAR(255) NOT NULL,         -- e.g., 'max_collector_workers' (without category)
    config_value JSONB NOT NULL,              -- The actual value (int, string, bool, object, array)
    config_type VARCHAR(50) NOT NULL,         -- 'int', 'float', 'bool', 'string', 'json', 'array'
    description TEXT,                         -- Human-readable description
    default_value JSONB,                      -- Default value
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    updated_by UUID REFERENCES users(id),
    UNIQUE(category, config_key)
);
```

**Key Points**:
- Full config key = `{category}.{config_key}` (e.g., `processing.parallel.max_collector_workers`)
- `config_value` is JSONB - can store any type
- `config_type` tells you what type of input to show (number, text, checkbox, etc.)
- Use `is_active = true` to filter active configs only

#### 2. `configuration_schemas` (Optional)
Schema definitions for validation and UI hints.

**Schema**:
```sql
CREATE TABLE configuration_schemas (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) UNIQUE NOT NULL,
    schema_definition JSONB NOT NULL,         -- JSON Schema for validation
    default_values JSONB NOT NULL,            -- Default config values
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Usage**:
- Use `schema_definition` for validation rules (min, max, enum values, etc.)
- Use `default_values` to show what default values are
- Use for generating form UI automatically

#### 3. `configuration_audit_log`
Audit trail of all configuration changes.

**Schema**:
```sql
CREATE TABLE configuration_audit_log (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    config_key VARCHAR(255) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE,
    change_reason TEXT
);
```

**Usage**:
- Show change history
- Who changed what and when
- Revert to previous values

---

## 🔍 Database Queries

### Get All Configurations (Grouped by Category)

```sql
SELECT 
    category,
    config_key,
    config_value,
    config_type,
    description,
    default_value,
    updated_at,
    updated_by
FROM system_configurations
WHERE is_active = true
ORDER BY category, config_key;
```

### Get Configurations for a Specific Category

```sql
SELECT 
    config_key,
    config_value,
    config_type,
    description,
    default_value
FROM system_configurations
WHERE category = 'processing' 
  AND is_active = true
ORDER BY config_key;
```

### Get a Single Configuration Value

```sql
SELECT config_value, config_type, description
FROM system_configurations
WHERE category = 'processing'
  AND config_key = 'parallel.max_collector_workers'
  AND is_active = true;
```

### Get Schema for a Category (for validation/UI hints)

```sql
SELECT schema_definition, default_values, description
FROM configuration_schemas
WHERE category = 'processing';
```

### Get Audit Log

```sql
SELECT 
    category,
    config_key,
    old_value,
    new_value,
    changed_by,
    changed_at,
    change_reason
FROM configuration_audit_log
WHERE category = 'processing'  -- Optional filter
ORDER BY changed_at DESC
LIMIT 100;
```

---

## 🎨 Frontend UI Design

### 1. Configuration Dashboard

**Layout**: Cards/Tabs for each category

```
┌─────────────────────────────────────────────────────┐
│  System Configuration                               │
├─────────────────────────────────────────────────────┤
│  [Processing] [Database] [API] [Deduplication] ... │
│                                                     │
│  Processing Configuration                          │
│  ┌───────────────────────────────────────────────┐ │
│  │ Parallel Processing                           │ │
│  │   Max Collector Workers: [8]                  │ │
│  │   Max Sentiment Workers: [20]                 │ │
│  │   ...                                         │ │
│  │                                               │ │
│  │ Timeouts                                      │ │
│  │   Collector Timeout: [1000] seconds          │ │
│  │   ...                                         │ │
│  │                                               │ │
│  │  [Save Changes] [Reset to Defaults]          │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 2. Form Input Types Based on `config_type`

```typescript
// Map config_type to input component
const getInputComponent = (configType: string, value: any) => {
  switch (configType) {
    case 'int':
    case 'float':
      return <NumberInput value={value} min={min} max={max} />;
    
    case 'bool':
      return <Checkbox checked={value} />;
    
    case 'string':
      return <TextInput value={value} />;
    
    case 'array':
      return <ArrayInput items={value} />;  // Custom array editor
    
    case 'json':
      return <JsonEditor value={value} />;  // JSON editor component
    
    default:
      return <TextInput value={JSON.stringify(value)} />;
  }
};
```

### 3. Validation

Use `configuration_schemas.schema_definition` for validation:

```typescript
// Example: processing.parallel.max_collector_workers
const schema = {
  type: "integer",
  minimum: 1,
  maximum: 50,
  default: 8
};

// Validate on change
if (value < schema.minimum || value > schema.maximum) {
  showError(`Value must be between ${schema.minimum} and ${schema.maximum}`);
}
```

### 4. Save Changes

When user clicks "Save":

```typescript
// Update database directly
const updateConfig = async (category: string, key: string, value: any, userId: string) => {
  await supabase
    .from('system_configurations')
    .update({
      config_value: value,
      updated_by: userId,
      updated_at: new Date().toISOString()
    })
    .eq('category', category)
    .eq('config_key', key)
    .eq('is_active', true);
  
  // Also create audit log entry
  await supabase
    .from('configuration_audit_log')
    .insert({
      category,
      config_key: key,
      old_value: oldValue,
      new_value: value,
      changed_by: userId,
      change_reason: reason
    });
};
```

---

## 🔐 Permissions

**Recommended**: Only admin users can edit configurations.

Check user permissions:
```sql
SELECT is_admin FROM users WHERE id = :user_id;
```

**Frontend Logic**:
- **Admin users**: Full read/write access
- **Non-admin users**: Read-only view (disable inputs, hide Save buttons)

---

## 📝 Example Frontend Component Structure

### React/Vue Component Example

```typescript
// ConfigCategory.tsx
interface ConfigItem {
  config_key: string;
  config_value: any;
  config_type: string;
  description?: string;
  default_value?: any;
}

const ConfigCategory = ({ category, isAdmin }: Props) => {
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [schema, setSchema] = useState<any>(null);
  
  useEffect(() => {
    // Load configs for category
    loadConfigs(category).then(setConfigs);
    
    // Load schema for validation hints
    loadSchema(category).then(setSchema);
  }, [category]);
  
  const handleSave = async (key: string, value: any) => {
    if (!isAdmin) return;
    
    // Validate
    if (!validateValue(key, value, schema)) {
      showError('Invalid value');
      return;
    }
    
    // Update database
    await updateConfig(category, key, value, userId);
    
    // Refresh
    loadConfigs(category).then(setConfigs);
  };
  
  return (
    <Card title={`${category} Configuration`}>
      {configs.map(config => (
        <ConfigInput
          key={config.config_key}
          label={formatLabel(config.config_key)}
          type={config.config_type}
          value={config.config_value}
          defaultValue={config.default_value}
          description={config.description}
          schema={schema?.properties?.[config.config_key]}
          disabled={!isAdmin}
          onChange={(value) => handleSave(config.config_key, value)}
        />
      ))}
      
      {isAdmin && (
        <Button onClick={handleSaveAll}>Save All Changes</Button>
      )}
    </Card>
  );
};
```

---

## 🔄 Best Practices

### 1. Group Related Configs
Organize by sections (e.g., "Parallel Processing", "Timeouts", "Limits")

### 2. Show Defaults
Display default values so users know what to reset to

### 3. Validation Feedback
- Real-time validation as user types
- Show min/max constraints
- Show description/help text
- Error messages for invalid values

### 4. Audit Trail UI
- Show change history in a sidebar or modal
- Display: who changed, what, when, why
- Option to revert to previous value

### 5. Bulk Operations
- "Save All" button for the entire category
- "Reset Category to Defaults" button
- "Export/Import" configuration (future enhancement)

### 6. Search/Filter
- Search by config key or description
- Filter by category
- Quick access to frequently changed configs

---

## 📋 Implementation Checklist

### Phase 1: Basic CRUD
- [ ] Query `system_configurations` table
- [ ] Display configs grouped by category
- [ ] Form inputs based on `config_type`
- [ ] Update config values in database
- [ ] Basic validation

### Phase 2: Enhanced Features
- [ ] Load `configuration_schemas` for validation hints
- [ ] Show default values
- [ ] Audit log viewer
- [ ] Revert to previous value from audit log

### Phase 3: Advanced Features
- [ ] Permission checks (admin-only editing)
- [ ] Bulk update operations
- [ ] Reset to defaults
- [ ] Export/import configurations
- [ ] Configuration templates/presets

---

## 🔗 Integration with Backend

The backend's `ConfigManager` reads from these tables:

```python
# Backend code automatically loads from database
config = ConfigManager(use_database=True, db_session=db)
workers = config.get_int('processing.parallel.max_collector_workers', 8)
```

**Important**: After updating configs in the database, the backend will pick them up on next reload or restart. You may want to add a "reload config" API endpoint if you need immediate effect.

---

## 📚 Example Queries (Supabase/PostgreSQL)

### Get all configs (Supabase JS)

```javascript
const { data, error } = await supabase
  .from('system_configurations')
  .select('*')
  .eq('is_active', true)
  .order('category', { ascending: true })
  .order('config_key', { ascending: true });
```

### Update a config

```javascript
const { error } = await supabase
  .from('system_configurations')
  .update({
    config_value: 12,
    updated_by: userId,
    updated_at: new Date().toISOString()
  })
  .eq('category', 'processing')
  .eq('config_key', 'parallel.max_collector_workers')
  .eq('is_active', true);
```

### Create audit log entry

```javascript
const { error } = await supabase
  .from('configuration_audit_log')
  .insert({
    category: 'processing',
    config_key: 'parallel.max_collector_workers',
    old_value: 8,
    new_value: 12,
    changed_by: userId,
    change_reason: 'Increased for higher throughput'
  });
```

---

## 🎯 Summary

1. **Query `system_configurations`** to get all config values
2. **Use `config_type`** to determine input component type
3. **Use `configuration_schemas`** for validation rules and UI hints
4. **Update `system_configurations`** directly when saving
5. **Insert into `configuration_audit_log`** to track changes
6. **Check `users.is_admin`** for permission control

The frontend queries the database directly - no API endpoints needed!












