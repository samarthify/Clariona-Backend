# Adding New Topics for Ministers - Complete Guide

This guide walks you through adding brand new topics specifically for ministers and setting them up for use.

## Overview

The process involves 4 steps:
1. **Add new topics** to `config/master_topics.json`
2. **Populate topics** to database
3. **Generate embeddings** for new topics
4. **Assign topics** to minister owner configs

---

## Step 1: Add New Topics to master_topics.json

Edit `config/master_topics.json` and add your new topics in the `topics` object.

### Example: Adding a New Topic for Health Minister

```json
{
    "version": "1.0",
    "last_updated": "2025-01-27",
    "topics": {
        // ... existing topics ...
        
        "mental_health_services": {
            "name": "Mental Health Services",
            "description": "Mental health services, psychiatric care, mental health facilities, counseling services, and mental health policy in Nigeria. Includes discussions about mental health awareness, psychiatric hospitals, mental health funding, access to mental health care, and government mental health programs.",
            "keywords": [
                "mental health",
                "psychiatric",
                "psychiatry",
                "mental illness",
                "counseling",
                "therapy",
                "mental health facility",
                "psychiatric hospital",
                "mental health care",
                "mental health services",
                "depression",
                "anxiety",
                "mental health awareness"
            ],
            "category": "health"
        },
        
        "maternal_health": {
            "name": "Maternal Health",
            "description": "Maternal health services, prenatal care, childbirth services, maternal mortality, and women's reproductive health in Nigeria. Includes discussions about maternal healthcare access, maternal mortality rates, prenatal care programs, and maternal health policies.",
            "keywords": [
                "maternal health",
                "maternal mortality",
                "prenatal care",
                "maternity",
                "childbirth",
                "pregnancy",
                "maternal care",
                "maternal healthcare",
                "maternal death",
                "prenatal",
                "antenatal",
                "maternal health services"
            ],
            "category": "health"
        }
    }
}
```

### Topic Structure Requirements

Each topic must have:
- **`topic_key`**: Unique identifier (snake_case, e.g., `"mental_health_services"`)
- **`name`**: Human-readable name (e.g., `"Mental Health Services"`)
- **`description`**: Detailed description (used for embedding generation)
- **`keywords`**: Array of relevant keywords for matching
- **`category`**: Optional category (e.g., `"health"`, `"education"`, `"infrastructure"`)

### Tips for Good Topics

1. **Descriptions should be detailed** - They're used to generate embeddings, so include context
2. **Keywords should be comprehensive** - Include variations, synonyms, and related terms
3. **Use specific topic keys** - Make them descriptive and unique
4. **Choose appropriate categories** - Helps with organization

---

## Step 2: Populate Topics to Database

Run the populate script to add topics to the database:

```bash
python scripts/populate_topics_from_json.py
```

This script will:
- Read `config/master_topics.json`
- Add new topics to the `topics` table
- Skip topics that already exist
- Show progress for each topic added

**Output example:**
```
Populating 2 topics...
  Added topic: mental_health_services - Mental Health Services
  Added topic: maternal_health - Maternal Health
Successfully populated 2 topics
```

---

## Step 3: Generate Embeddings for New Topics

After adding topics to the database, generate embeddings:

```bash
python src/processing/topic_embedding_generator.py
```

This script will:
- Load all active topics from the database
- Generate embeddings for topics missing from `topic_embeddings.json`
- Update `config/topic_embeddings.json` with all embeddings
- Use OpenAI API (requires `OPENAI_API_KEY` environment variable)

**Output example:**
```
Generating embeddings for 38 topics...
Generated embedding for topic: mental_health_services
Generated embedding for topic: maternal_health
Saved 38 topic embeddings to config/topic_embeddings.json
```

**Note**: This regenerates embeddings for ALL topics. It's safe to run multiple times.

---

## Step 4: Assign Topics to Minister Owner Configs

Now assign your new topics to minister owner configs.

### Option A: Create Minister Config File (Recommended)

Create `config/minister_configs/health_minister_config.json`:

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
        "mental_health_services",
        "maternal_health"
    ],
    "priority_topics": [
        "healthcare_crisis",
        "mental_health_services",
        "maternal_health"
    ],
    "is_active": true,
    "created_at": "2025-01-27",
    "updated_at": "2025-01-27"
}
```

Then run:
```bash
python scripts/populate_topics_from_json.py
```

This will update the `owner_configs` table with your new topics.

### Option B: Update Existing Config Directly

If you already have a minister config, just add the new topic keys to the `topics` array:

```json
{
    "owner": "minister_health",
    "topics": [
        "healthcare_crisis",
        "healthcare_access",
        "mental_health_services",  // ← Add new topic here
        "maternal_health"          // ← Add new topic here
    ]
}
```

---

## Complete Workflow Example

Let's say you want to add "Rural Healthcare Access" topic for Health Minister:

### 1. Add to master_topics.json

```json
"rural_healthcare_access": {
    "name": "Rural Healthcare Access",
    "description": "Healthcare access in rural areas, rural health facilities, primary healthcare centers in rural communities, and challenges of healthcare delivery in rural Nigeria. Includes discussions about rural health infrastructure, mobile health services, rural health workers, and government programs to improve rural healthcare access.",
    "keywords": [
        "rural health",
        "rural healthcare",
        "rural health facility",
        "primary healthcare",
        "rural clinic",
        "rural hospital",
        "rural health access",
        "rural health services",
        "rural medical care",
        "rural health workers",
        "rural health infrastructure"
    ],
    "category": "health"
}
```

### 2. Populate to Database

```bash
python scripts/populate_topics_from_json.py
```

### 3. Generate Embedding

```bash
python src/processing/topic_embedding_generator.py
```

### 4. Assign to Minister

Update `config/minister_configs/health_minister_config.json`:

```json
{
    "owner": "minister_health",
    "topics": [
        "healthcare_crisis",
        "rural_healthcare_access"  // ← New topic
    ]
}
```

Run populate script again:
```bash
python scripts/populate_topics_from_json.py
```

---

## Verifying Your Setup

### Check Topics in Database

```python
from api.database import SessionLocal
from api.models import Topic

db = SessionLocal()
topics = db.query(Topic).filter(
    Topic.topic_key.in_(['mental_health_services', 'maternal_health']),
    Topic.is_active == True
).all()

for topic in topics:
    print(f"✓ {topic.topic_key}: {topic.topic_name}")
```

### Check Embeddings Exist

```python
from processing.topic_classifier import TopicClassifier

classifier = TopicClassifier()

new_topics = ['mental_health_services', 'maternal_health']
for topic_key in new_topics:
    has_embedding = topic_key in classifier.topic_embeddings
    status = "✓" if has_embedding else "✗"
    print(f"{status} {topic_key}: Embedding {'exists' if has_embedding else 'MISSING'}")
```

### Check Owner Config

```python
from api.database import SessionLocal
from api.models import OwnerConfig

db = SessionLocal()
config = db.query(OwnerConfig).filter(
    OwnerConfig.owner_key == 'minister_health'
).first()

if config:
    print(f"Topics for {config.owner_name}:")
    for topic in config.topics:
        print(f"  - {topic}")
```

### Test Classification

```python
from processing.topic_classifier import TopicClassifier

classifier = TopicClassifier()

# Test text related to your new topic
test_text = "Mental health services in Nigeria need urgent attention. Psychiatric hospitals are underfunded."
test_embedding = None  # Would normally come from OpenAI

results = classifier.classify(test_text, test_embedding)
for result in results:
    print(f"{result['topic_name']}: {result['confidence']:.3f}")
```

---

## Troubleshooting

### Topic Not Appearing in Database

1. **Check JSON syntax**: Validate `master_topics.json` is valid JSON
2. **Verify populate script ran**: Check script output for errors
3. **Check database connection**: Ensure `DATABASE_URL` is set correctly

### Embedding Not Generated

1. **Check OpenAI API key**: Ensure `OPENAI_API_KEY` environment variable is set
2. **Check topic exists**: Verify topic is in database first
3. **Check logs**: Look for error messages in embedding generator output

### Topic Not Classifying Mentions

1. **Verify embedding exists**: Check `topic_embeddings.json` contains your topic
2. **Check keywords**: Ensure keywords match common terms in mentions
3. **Test with embedding**: Classification works better with embeddings (60% weight)
4. **Check thresholds**: Topic might be classified but below confidence threshold

### Owner Config Not Updating

1. **Verify JSON file path**: Check file is in correct location
2. **Check owner_key matches**: Must match exactly (case-sensitive)
3. **Verify populate script ran**: Check script output for updates

---

## Best Practices

1. **Batch additions**: Add multiple topics at once, then run populate + embedding generation once
2. **Test before assigning**: Verify topics work in classification before assigning to ministers
3. **Use descriptive keys**: Topic keys should be clear and follow snake_case convention
4. **Keep descriptions detailed**: Better descriptions = better embeddings = better classification
5. **Version control**: Commit changes to `master_topics.json` for tracking

---

## Quick Reference Commands

```bash
# 1. Add topics to master_topics.json (manual edit)

# 2. Populate topics to database
python scripts/populate_topics_from_json.py

# 3. Generate embeddings
python src/processing/topic_embedding_generator.py

# 4. Assign to ministers (create/update config files, then)
python scripts/populate_topics_from_json.py
```

---

## Related Files

- `config/master_topics.json` - Master topic definitions
- `config/topic_embeddings.json` - Generated topic embeddings
- `config/minister_configs/` - Minister owner configs (create this directory)
- `scripts/populate_topics_from_json.py` - Populate topics and owner configs
- `src/processing/topic_embedding_generator.py` - Generate embeddings
- `src/api/models.py` - Topic and OwnerConfig models
