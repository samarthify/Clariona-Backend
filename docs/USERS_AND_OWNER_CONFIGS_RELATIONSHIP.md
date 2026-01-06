# Users and Owner Configs Relationship

This document explains how the `users` table and `owner_configs` table are related and how they work together.

---

## Overview

**Important**: `owner_configs` has **NOT** replaced the `users` table. They serve different purposes and work together:

- **`users` table**: Authentication, user management, basic user information
- **`owner_configs` table**: Topic filtering configuration for role-based access

---

## Table Structures

### `users` Table

**Purpose**: Core user authentication and management

**Key Fields**:
- `id` (UUID, Primary Key) - Unique user identifier
- `email` (String, Unique) - User email address
- `username` (String) - Username
- `password_hash` (String) - Hashed password
- `role` (String) - User role (e.g., "president", "minister", "user")
- `ministry` (String) - Ministry assignment (for ministers)
- `name` (String) - User's full name
- `is_admin` (Boolean) - Admin flag
- `created_at`, `last_login` - Timestamps

**Relationships**:
- `sentiment_data` - One-to-many (user has many sentiment data entries)
- `email_configurations` - One-to-many (user has email configs)
- `target_configurations` - One-to-many (user has target individual configs)

### `owner_configs` Table

**Purpose**: Topic filtering configuration for role-based access

**Key Fields**:
- `owner_key` (String, Primary Key) - Computed key from user information
- `owner_name` (String) - Display name
- `owner_type` (String) - "president", "minister", "user"
- `topics` (Array[Text]) - Array of topic_keys this owner cares about
- `priority_topics` (Array[Text]) - High-priority topics
- `is_active` (Boolean) - Whether config is active
- `config_data` (JSONB) - Additional config data (includes user_id)
- `created_at`, `updated_at` - Timestamps

**Note**: There is **NO foreign key** relationship to `users` table.

---

## Relationship Mechanism

The relationship between `users` and `owner_configs` is maintained through a **computed `owner_key`** that is derived from user information.

### Owner Key Generation

**Location**: `scripts/sync_users_to_owner_configs.py` - `create_owner_key()`

**Algorithm**:
```python
def create_owner_key(user: User) -> str:
    if user.role and user.role.lower() == 'president':
        return 'president'
    elif user.ministry:
        ministry_key = user.ministry.lower().replace(' ', '_').replace('-', '_')
        return f'minister_{ministry_key}'
    else:
        return f'user_{str(user.id).replace("-", "_")}'
```

**Examples**:
- **President**: `owner_key = "president"`
- **Minister of Health**: `owner_key = "minister_health"`
- **Minister of Education**: `owner_key = "minister_education"`
- **Regular User (ID: 6440da7f-e630-4b2f-884e-a8721cc9a9c0)**: `owner_key = "user_6440da7f_e630_4b2f_884e_a8721cc9a9c0"`

### User ID Storage

The `user.id` is stored in `owner_configs.config_data` JSONB field:

```json
{
  "user_id": "6440da7f-e630-4b2f-884e-a8721cc9a9c0",
  "user_email": "user@example.com",
  "user_role": "president",
  "user_ministry": null
}
```

**Location**: `scripts/sync_users_to_owner_configs.py` - Line 352-357

---

## Why No Foreign Key?

The `owner_configs` table uses a **computed key** instead of a foreign key because:

1. **Role-Based Grouping**: Multiple users can share the same `owner_key`:
   - All users with `role = "president"` share `owner_key = "president"`
   - All users with `ministry = "health"` share `owner_key = "minister_health"`

2. **Flexibility**: Allows configuration at the role/ministry level, not just individual users

3. **Backward Compatibility**: Supports legacy configurations that may not have direct user mappings

---

## Synchronization

### Manual Sync Script

**Script**: `scripts/sync_users_to_owner_configs.py`

**Purpose**: Creates or updates `owner_configs` entries based on `users` table

**Process**:
1. Reads all users from `users` table
2. For each user:
   - Computes `owner_key` from user information
   - Determines topics based on role/ministry
   - Creates or updates `owner_configs` entry
   - Stores `user.id` in `config_data` JSONB field

**Usage**:
```bash
python scripts/sync_users_to_owner_configs.py
```

### Topic Assignment Logic

**Location**: `scripts/sync_users_to_owner_configs.py` - `sync_user_to_owner_config()`

**Rules**:
- **President**: Gets all president topics (from `PRESIDENT_TOPICS`)
- **Ministers**: Gets topics for their ministry (from `ministry_issues` JSON files)
- **Regular Users**: No topics assigned (empty array)

---

## Querying the Relationship

### Get Owner Config for a User

```python
from api.models import User, OwnerConfig

# Get user
user = db.query(User).filter(User.id == user_id).first()

# Compute owner_key
if user.role and user.role.lower() == 'president':
    owner_key = 'president'
elif user.ministry:
    owner_key = f'minister_{user.ministry.lower().replace(" ", "_")}'
else:
    owner_key = f'user_{str(user.id).replace("-", "_")}'

# Get owner config
owner_config = db.query(OwnerConfig).filter(
    OwnerConfig.owner_key == owner_key,
    OwnerConfig.is_active == True
).first()
```

### Get User from Owner Config

```python
# Get owner config
owner_config = db.query(OwnerConfig).filter(
    OwnerConfig.owner_key == owner_key
).first()

# Extract user_id from config_data
if owner_config and owner_config.config_data:
    user_id = owner_config.config_data.get('user_id')
    user = db.query(User).filter(User.id == user_id).first()
```

**Note**: Since multiple users can share the same `owner_key`, this will only return one user (the one that created/updated the config).

### Get All Users for an Owner Config

```python
# Get owner config
owner_config = db.query(OwnerConfig).filter(
    OwnerConfig.owner_key == owner_key
).first()

# Find all users that would generate this owner_key
if owner_config.owner_type == 'president':
    users = db.query(User).filter(User.role == 'president').all()
elif owner_config.owner_type == 'minister':
    ministry = owner_config.owner_key.replace('minister_', '').replace('_', ' ')
    users = db.query(User).filter(User.ministry == ministry).all()
else:
    # Regular user - extract from config_data
    user_id = owner_config.config_data.get('user_id')
    users = [db.query(User).filter(User.id == user_id).first()] if user_id else []
```

---

## Use Cases

### 1. Topic Filtering

**Location**: `src/processing/topic_classifier.py`

**Usage**: Filter topics based on user's role/ministry:

```python
# Get owner config for user
owner_key = create_owner_key(user)
owner_config = session.query(OwnerConfig).filter(
    OwnerConfig.owner_key == owner_key,
    OwnerConfig.is_active == True
).first()

# Filter topics
if owner_config and owner_config.topics:
    # Only show topics assigned to this owner
    filtered_topics = [t for t in topics if t in owner_config.topics]
```

### 2. Role-Based Dashboard

**Usage**: Show different dashboards based on user role:

```python
owner_key = create_owner_key(user)
owner_config = db.query(OwnerConfig).filter(
    OwnerConfig.owner_key == owner_key
).first()

if owner_config.owner_type == 'president':
    # Show national dashboard
elif owner_config.owner_type == 'minister':
    # Show ministry-specific dashboard
else:
    # Show user dashboard
```

### 3. Priority Topics

**Usage**: Highlight priority topics for user:

```python
owner_config = get_owner_config_for_user(user)
if owner_config and owner_config.priority_topics:
    # Show priority topics first
    priority = owner_config.priority_topics
```

---

## Data Flow

```
┌─────────────┐
│   users     │
│   table     │
└──────┬──────┘
       │
       │ (computed owner_key)
       │
       ▼
┌─────────────────┐
│  owner_configs  │
│     table       │
└─────────────────┘
       │
       │ (topics array)
       │
       ▼
┌─────────────┐
│   topics    │
│   table     │
└─────────────┘
```

**Flow**:
1. User exists in `users` table
2. `owner_key` is computed from user's role/ministry
3. `owner_configs` entry is created/updated with topics
4. Topics are used to filter data for user

---

## Important Notes

### 1. No Direct Foreign Key

- `owner_configs` does **NOT** have a foreign key to `users`
- Relationship is maintained through computed `owner_key`
- `user.id` is stored in `config_data` JSONB field (informational only)

### 2. One-to-Many Relationship (Conceptual)

- **One user** → **One owner_config** (for regular users)
- **Many users** → **One owner_config** (for president/ministers sharing same role)

### 3. Synchronization Required

- `owner_configs` entries are **NOT** automatically created when users are created
- Must run sync script: `scripts/sync_users_to_owner_configs.py`
- Or manually create/update entries

### 4. Orphan Configs Possible

- `owner_configs` entries can exist without corresponding users
- Use `scripts/show_users_and_owner_configs.py` to find orphan configs

---

## Related Tables

### `target_individual_configurations`

**Purpose**: Data collection targets (what to search for)

**Relationship**: Direct foreign key to `users.id`

```python
class TargetIndividualConfiguration(Base):
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    individual_name = Column(String)
    query_variations = Column(JSON)
```

**Usage**: Defines search terms for data collection (e.g., "Bola Ahmed Tinubu")

### `email_configurations`

**Purpose**: Email notification settings

**Relationship**: Direct foreign key to `users.id`

```python
class EmailConfiguration(Base):
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    recipients = Column(JSON)
    enabled = Column(Boolean)
```

**Usage**: Configures email notifications for users

---

## Summary

| Aspect | Details |
|--------|---------|
| **Relationship Type** | Computed key (no foreign key) |
| **Linking Field** | `owner_key` (computed from user role/ministry) |
| **User ID Storage** | Stored in `config_data` JSONB field |
| **Purpose** | Topic filtering configuration |
| **Sync Required** | Yes (manual script) |
| **One-to-Many** | Yes (multiple users can share same owner_key) |

**Key Points**:
- `users` table: Authentication and user management
- `owner_configs` table: Topic filtering configuration
- Relationship: Computed `owner_key` (no foreign key)
- Sync: Manual script required
- Use Case: Role-based topic filtering

---

## Related Documentation

- [COMPUTED_PARAMETERS_AND_USER_FILTERING.md](./COMPUTED_PARAMETERS_AND_USER_FILTERING.md) - User filtering details
- [DATABASE_CONFIGURATION_SYSTEM_DESIGN.md](./DATABASE_CONFIGURATION_SYSTEM_DESIGN.md) - Configuration system
- [BACKEND_ARCHITECTURE.md](../BACKEND_ARCHITECTURE.md) - System architecture
