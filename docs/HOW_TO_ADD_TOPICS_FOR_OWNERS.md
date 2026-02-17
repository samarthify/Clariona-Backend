# How to Add Topics for Owners (Non-President)

This guide shows you how to configure topics for owners other than the president (e.g., ministers, ministries).

## Overview

Topics for owners are stored in the `owner_configs` table with the following structure:
- `owner_key`: Unique identifier (e.g., `"minister_health"`, `"minister_education"`)
- `owner_name`: Display name (e.g., `"Minister of Health"`)
- `owner_type`: Type of owner (`"president"`, `"minister"`, etc.)
- `topics`: Array of topic keys this owner cares about
- `priority_topics`: Array of high-priority topic keys

---

## Method 1: Create JSON Config File (Recommended)

This is the easiest and most maintainable method.

### Step 1: Create a JSON Config File

Create a file in `config/` directory, e.g., `config/health_minister_config.json`:

```json
{
    "owner": "minister_health",
    "owner_name": "Minister of Health",
    "owner_type": "minister",
    "topics": [
        "healthcare_crisis",
        "healthcare_access",
        "medical_equipment",
        "hospital_funding",
        "public_health"
    ],
    "priority_topics": [
        "healthcare_crisis",
        "healthcare_access"
    ],
    "is_active": true,
    "created_at": "2025-01-27",
    "updated_at": "2025-01-27"
}
```

### Step 2: Load the Config into Database

Run the populate script:

```bash
python scripts/populate_topics_from_json.py
```

This script will:
- Read all JSON config files from `config/` directory
- Create or update `owner_configs` entries in the database
- Validate that topics exist in the `topics` table

### Available Topic Keys

To see all available topic keys, check:
- `config/master_topics.json` - Lists all topics with their keys
- Database: `SELECT topic_key, topic_name FROM topics WHERE is_active = true;`

---

## Method 2: Use Sync Script (For Users in Database)

If you have users (ministers) already in the `users` table, you can sync them automatically.

### Step 1: Update Ministry-to-Topics Mapping

Edit `scripts/sync_users_to_owner_configs.py` and update the `MINISTRY_TO_TOPICS` dictionary:

```python
MINISTRY_TO_TOPICS = {
    'health': [
        'healthcare_crisis',
        'healthcare_access',
        'medical_equipment',
        'hospital_funding'
    ],
    'education': [
        'education_funding',
        'assu_strikes',
        'teacher_salaries',
        'school_infrastructure'
    ],
    # Add more ministries...
}
```

### Step 2: Run Sync Script

```bash
python scripts/sync_users_to_owner_configs.py
```

This will:
- Read all users from `users` table
- Create `owner_configs` entries based on user's role/ministry
- Map topics using `MINISTRY_TO_TOPICS` dictionary

### Owner Key Format

The script generates `owner_key` as:
- President: `"president"`
- Ministers: `"minister_{ministry_name}"` (e.g., `"minister_health"`)
- Regular users: `"user_{user_id}"`

---

## Method 3: Direct Database Update (Advanced)

For direct database manipulation using Python:

### Python Script Example

```python
from api.database import SessionLocal
from api.models import OwnerConfig, Topic

db = SessionLocal()

# Get or create owner config
owner_key = "minister_health"
owner_config = db.query(OwnerConfig).filter(
    OwnerConfig.owner_key == owner_key
).first()

# List of topic keys to assign
topic_keys = [
    "healthcare_crisis",
    "healthcare_access",
    "medical_equipment",
    "hospital_funding"
]

# Verify topics exist
valid_topics = db.query(Topic.topic_key).filter(
    Topic.topic_key.in_(topic_keys),
    Topic.is_active == True
).all()
valid_topic_keys = [t[0] for t in valid_topics]

if owner_config:
    # Update existing
    owner_config.topics = valid_topic_keys
    owner_config.priority_topics = valid_topic_keys[:2]  # First 2 as priority
    owner_config.is_active = True
    print(f"Updated {owner_key} with {len(valid_topic_keys)} topics")
else:
    # Create new
    owner_config = OwnerConfig(
        owner_key=owner_key,
        owner_name="Minister of Health",
        owner_type="minister",
        topics=valid_topic_keys,
        priority_topics=valid_topic_keys[:2],
        is_active=True
    )
    db.add(owner_config)
    print(f"Created {owner_key} with {len(valid_topic_keys)} topics")

db.commit()
db.close()
```

### SQL Direct Update

```sql
-- Update existing owner config
UPDATE owner_configs
SET 
    topics = ARRAY['healthcare_crisis', 'healthcare_access', 'medical_equipment'],
    priority_topics = ARRAY['healthcare_crisis', 'healthcare_access'],
    updated_at = NOW()
WHERE owner_key = 'minister_health';

-- Or insert new
INSERT INTO owner_configs (
    owner_key,
    owner_name,
    owner_type,
    topics,
    priority_topics,
    is_active
) VALUES (
    'minister_health',
    'Minister of Health',
    'minister',
    ARRAY['healthcare_crisis', 'healthcare_access'],
    ARRAY['healthcare_crisis'],
    true
);
```

---

## Verifying Your Configuration

### Check Owner Configs

```python
from api.database import SessionLocal
from api.models import OwnerConfig

db = SessionLocal()
configs = db.query(OwnerConfig).filter(OwnerConfig.is_active == True).all()

for config in configs:
    print(f"{config.owner_name} ({config.owner_key}):")
    print(f"  Topics: {len(config.topics) if config.topics else 0}")
    print(f"  Priority: {len(config.priority_topics) if config.priority_topics else 0}")
    if config.topics:
        print(f"  Topic list: {config.topics}")
```

### Using the Topic Classifier

```python
from processing.topic_classifier import TopicClassifier

classifier = TopicClassifier()

# Get topics for an owner
owner_topics = classifier.get_topics_for_owner('minister_health')
print(f"Topics for health minister: {owner_topics}")

# Filter classifications for owner
classifications = classifier.classify("Hospital funding has been cut...")
filtered = classifier.filter_topics_for_owner(classifications, 'minister_health')
print(f"Filtered topics: {filtered}")
```

---

## Common Owner Keys

Based on the codebase, common owner keys follow these patterns:

- **President**: `"president"`
- **Ministers**: `"minister_{ministry}"` (e.g., `"minister_health"`, `"minister_education"`)
- **Ministries**: Can also use ministry name directly (e.g., `"health"`, `"education"`)

To see existing owner configs:
```sql
SELECT owner_key, owner_name, owner_type, array_length(topics, 1) as topic_count
FROM owner_configs
WHERE is_active = true
ORDER BY owner_type, owner_name;
```

---

## Important: Embeddings vs Owner Configs

### ⚠️ Key Distinction

**Adding topics to owner configs does NOT require updating embeddings** because:

1. **Embeddings are per TOPIC, not per OWNER**
   - Each topic has ONE embedding (stored in `config/topic_embeddings.json`)
   - Owner configs just filter which topics an owner sees
   - No new embeddings are created when assigning topics to owners

2. **When embeddings ARE needed:**
   - Only when you add a **NEW topic** (not just assign existing topics)
   - The new topic needs an embedding generated from its name + description

### Workflow: Adding Topics to Owner Configs

```
Step 1: Assign existing topics to owner
   ↓
Step 2: Embeddings already exist (no action needed)
   ↓
Step 3: Topic classifier uses existing embeddings automatically
```

### Workflow: Adding a NEW Topic

```
Step 1: Add topic to database (via populate_topics_from_json.py)
   ↓
Step 2: Generate embedding for new topic
   ↓
Step 3: Update topic_embeddings.json
   ↓
Step 4: Assign topic to owner config (optional)
```

### How to Update Embeddings (Only for NEW Topics)

If you've added a **new topic** to the database, regenerate embeddings:

```bash
# This reads ALL topics from database and regenerates embeddings
python src/processing/topic_embedding_generator.py
```

This script will:
1. Load all active topics from the `topics` table
2. Generate embeddings for any topics missing from `topic_embeddings.json`
3. Update `config/topic_embeddings.json` with all embeddings

**Note**: This regenerates embeddings for ALL topics, not just new ones. It's safe to run multiple times.

### Checking if Embeddings Exist

```python
from processing.topic_classifier import TopicClassifier

classifier = TopicClassifier()

# Check which topics have embeddings
for topic_key in classifier.master_topics.keys():
    has_embedding = topic_key in classifier.topic_embeddings
    print(f"{topic_key}: {'✓' if has_embedding else '✗'}")

# Or check specific topic
if 'healthcare_crisis' in classifier.topic_embeddings:
    print("Embedding exists!")
else:
    print("Need to generate embedding")
```

---

## Troubleshooting

### Topics Not Showing Up

1. **Verify topics exist**: Check that topic keys exist in `topics` table:
   ```sql
   SELECT topic_key FROM topics WHERE topic_key IN ('healthcare_crisis', 'healthcare_access');
   ```

2. **Check owner config is active**:
   ```sql
   SELECT * FROM owner_configs WHERE owner_key = 'minister_health' AND is_active = true;
   ```

3. **Verify topic keys match exactly**: Topic keys are case-sensitive and must match exactly.

4. **Check if embedding exists** (for embedding-based classification):
   ```python
   # Topic classifier will fall back to keyword-only if embedding missing
   # But embedding-based classification is more accurate
   ```

### Owner Config Not Found

- Ensure `owner_key` matches exactly (case-sensitive)
- Check that `is_active = true`
- Verify the config was committed to database

### Embeddings Missing for Topics

If a topic doesn't have an embedding:
1. The topic classifier will still work using **keyword-only mode**
2. But embedding-based classification (60% weight) won't work
3. To fix: Run `python src/processing/topic_embedding_generator.py`

---

## Best Practices

1. **Use JSON files** for version control and easy updates
2. **Validate topic keys** before assigning (ensure they exist in `topics` table)
3. **Set priority topics** to highlight most important topics for each owner
4. **Keep owner_key consistent** - use a naming convention (e.g., `minister_{ministry}`)
5. **Document changes** - update `updated_at` when modifying configs

---

## Related Files

- `config/president_config.json` - Example config file
- `scripts/populate_topics_from_json.py` - Script to load JSON configs
- `scripts/sync_users_to_owner_configs.py` - Script to sync users to owner configs
- `src/api/models.py` - `OwnerConfig` model definition
- `src/processing/topic_classifier.py` - Methods to query owner topics
