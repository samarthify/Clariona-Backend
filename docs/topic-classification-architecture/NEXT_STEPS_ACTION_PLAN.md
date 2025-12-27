# Next Steps Action Plan
## Topic-Based Classification Implementation

---

## Current Status
✅ **Planning Complete**: Architecture, database schema, and implementation plan documented  
⏳ **Ready to Start**: Phase 1 - Setup

---

## Immediate Next Steps (In Order)

### Step 1: Create Master Topics Configuration
**Priority: HIGH | Estimated Time: 2-3 hours**

**Action**: Create `config/master_topics.json` with initial topic definitions

**What to do:**
1. Create the file: `config/master_topics.json`
2. Define initial topics (start with 10-15 core topics):
   - `fuel_pricing`
   - `presidential_announcements`
   - `military_operations`
   - `education_funding`
   - `asuu_strikes`
   - `healthcare_crisis`
   - `security_threats`
   - `budget_allocation`
   - `infrastructure_projects`
   - `corruption_cases`
   - ... (expand based on current ministry categories)

3. For each topic, include:
   - `name`: Human-readable name
   - `description`: Detailed description (used for embedding generation)
   - `keywords`: Array of relevant keywords
   - `category`: Optional category grouping

**Example structure:**
```json
{
    "version": "1.0",
    "topics": {
        "fuel_pricing": {
            "name": "Fuel Pricing",
            "description": "Fuel pricing policies, subsidies, and pump price changes affecting petroleum products in Nigeria",
            "keywords": ["fuel", "petrol", "diesel", "subsidy", "pump price", "pricing", "gasoline"],
            "category": "energy"
        }
    }
}
```

**Files to create:**
- `config/master_topics.json`

---

### Step 2: Create Owner Configurations
**Priority: HIGH | Estimated Time: 1-2 hours**

**Action**: Create config files for president and ministers

**What to do:**
1. Create `config/president_config.json`:
   - List topics the president cares about
   - Include priority topics

2. Create `config/minister_configs/` directory
3. Create config files for each minister:
   - `petroleum_resources.json`
   - `education.json`
   - `health_social_welfare.json`
   - ... (one per minister)

**Example structure:**
```json
{
    "owner": "president",
    "owner_name": "President of Nigeria",
    "topics": [
        "presidential_announcements",
        "fuel_pricing",
        "military_operations",
        "cabinet_appointments"
    ],
    "priority_topics": [
        "presidential_announcements"
    ]
}
```

**Files to create:**
- `config/president_config.json`
- `config/minister_configs/petroleum_resources.json`
- `config/minister_configs/education.json`
- ... (other minister configs)

---

### Step 3: Generate Topic Embeddings
**Priority: HIGH | Estimated Time: 30 minutes**

**Action**: Create and run `TopicEmbeddingGenerator` to generate embeddings

**What to do:**
1. Create `src/processing/topic_embedding_generator.py`
   - Use code from implementation plan
   - Generates embeddings for all topics in master_topics.json

2. Run the generator:
   ```bash
   python src/processing/topic_embedding_generator.py
   ```

3. Verify output: `config/topic_embeddings.json` is created

**Files to create:**
- `src/processing/topic_embedding_generator.py`

**Files generated:**
- `config/topic_embeddings.json`

---

### Step 4: Create Topic Classifier
**Priority: HIGH | Estimated Time: 3-4 hours**

**Action**: Implement `TopicClassifier` class

**What to do:**
1. Create `src/processing/topic_classifier.py`
2. Implement core methods:
   - `__init__()`: Load master topics and embeddings
   - `classify()`: Main classification method
   - `_keyword_match()`: Keyword matching logic
   - `_classify_keyword_only()`: Fallback method
   - `get_topics_for_owner()`: Load owner configs

3. Add utility: `src/utils/similarity.py` for cosine similarity

4. Test with sample texts

**Files to create:**
- `src/processing/topic_classifier.py`
- `src/utils/similarity.py`

**Dependencies:**
- `numpy` (for array operations)
- `sklearn` (for cosine similarity) OR implement manually

---

### Step 5: Database Schema Setup
**Priority: HIGH | Estimated Time: 2-3 hours**

**Action**: Create database tables and migrations

**What to do:**
1. Create migration file: `migrations/001_create_topics_tables.sql`
   - Create `topics` table
   - Create `topic_issues` table
   - Create `mention_topics` junction table
   - Create `owner_configs` table
   - Create all indexes

2. Create SQLAlchemy models: `src/models.py` (add new models)
   - `Topic`
   - `TopicIssue`
   - `MentionTopic`
   - `OwnerConfig`

3. Run migration:
   ```bash
   # Apply migration
   psql -d your_database -f migrations/001_create_topics_tables.sql
   ```

4. Populate `topics` table from `master_topics.json` (Python script)

**Files to create:**
- `migrations/001_create_topics_tables.sql`
- `scripts/populate_topics_table.py` (one-time script)

**Files to modify:**
- `src/models.py` (add new models)

---

### Step 6: Modify Issue Classifier
**Priority: MEDIUM | Estimated Time: 2-3 hours**

**Action**: Update `IssueClassifier` to use database and topic scope

**What to do:**
1. Modify `src/processing/issue_classifier.py`:
   - Change `__init__()` to accept `db_session` instead of `storage_dir`
   - Update `load_topic_issues()` to query database
   - Update `save_topic_issue()` to write to database
   - Add `increment_issue_mention_count()` method
   - Change all `ministry` references to `topic`

2. Test with database

**Files to modify:**
- `src/processing/issue_classifier.py`

---

### Step 7: Modify Governance Analyzer
**Priority: MEDIUM | Estimated Time: 2-3 hours**

**Action**: Update `GovernanceAnalyzer` to use `TopicClassifier`

**What to do:**
1. Modify `src/processing/governance_analyzer.py`:
   - Remove LLM-based classification code
   - Add `TopicClassifier` initialization
   - Update `analyze()` method to:
     - Accept `text_embedding` parameter
     - Use `TopicClassifier.classify()` instead of OpenAI
     - Return multiple topics instead of single ministry

2. Update return structure to include topics array

**Files to modify:**
- `src/processing/governance_analyzer.py`

---

### Step 8: Update Data Processor
**Priority: MEDIUM | Estimated Time: 2-3 hours**

**Action**: Integrate topic classification into processing pipeline

**What to do:**
1. Modify `src/processing/data_processor.py`:
   - Update `batch_get_sentiment()` to:
     - Pass embeddings to `GovernanceAnalyzer`
     - Handle multiple topics per mention
     - Store topics in `mention_topics` table

2. Update result structure

**Files to modify:**
- `src/processing/data_processor.py`

---

### Step 9: Data Migration
**Priority: MEDIUM | Estimated Time: 3-4 hours**

**Action**: Migrate existing data to new schema

**What to do:**
1. Create migration script: `migrations/002_migrate_existing_data.sql`
   - Migrate mentions: `ministry_hint` → `mention_topics` table
   - Migrate issues: JSON files → `topic_issues` table
   - Populate `owner_configs` table

2. Create Python migration script: `scripts/migrate_issues_to_database.py`
   - Read existing `ministry_issues/*.json` files
   - Insert into `topic_issues` table

3. Test migration on staging database first

**Files to create:**
- `migrations/002_migrate_existing_data.sql`
- `scripts/migrate_issues_to_database.py`

---

### Step 10: Update Dashboard Queries
**Priority: MEDIUM | Estimated Time: 2-3 hours**

**Action**: Update API endpoints to use new topic-based filtering

**What to do:**
1. Find dashboard/API files that query mentions
2. Update queries to:
   - Filter by `mention_topics` table
   - Join with `owner_configs` for owner filtering
   - Handle multiple topics per mention

3. Test dashboard filtering

**Files to modify:**
- API endpoint files (location depends on your structure)
- Dashboard query functions

---

## Recommended Implementation Order

### Week 1: Foundation
1. ✅ **Step 1**: Create master topics config
2. ✅ **Step 2**: Create owner configs
3. ✅ **Step 3**: Generate topic embeddings
4. ✅ **Step 4**: Create topic classifier
5. ✅ **Step 5**: Database schema setup

### Week 2: Integration
6. ✅ **Step 6**: Modify issue classifier
7. ✅ **Step 7**: Modify governance analyzer
8. ✅ **Step 8**: Update data processor

### Week 3: Migration & Testing
9. ✅ **Step 9**: Data migration
10. ✅ **Step 10**: Update dashboard queries
11. ✅ **Testing**: End-to-end testing
12. ✅ **Tuning**: Adjust keywords, weights, thresholds

---

## Quick Start (Minimal Viable Implementation)

If you want to get something working quickly:

1. **Create 5-10 core topics** in `master_topics.json`
2. **Create president config** with those topics
3. **Generate embeddings** for those topics
4. **Create TopicClassifier** (basic version)
5. **Test classification** on sample texts
6. **Iterate** and expand

---

## Testing Checklist

After each step, test:
- [ ] Config files load correctly
- [ ] Embeddings generated successfully
- [ ] Topic classifier returns results
- [ ] Database tables created
- [ ] Issue classifier works with database
- [ ] Governance analyzer uses topic classifier
- [ ] Data processor handles multiple topics
- [ ] Dashboard queries work correctly

---

## Dependencies to Install

```bash
pip install numpy scikit-learn  # For similarity calculations
# (Other dependencies should already be installed)
```

---

## Questions to Answer Before Starting

1. **How many topics to start with?** (Recommend: 15-20 core topics)
2. **Which ministers to configure first?** (Recommend: 5-10 most active)
3. **Database migration strategy?** (Full migration vs. gradual)
4. **Backward compatibility?** (Keep old columns temporarily?)

---

## Next Immediate Action

**START HERE**: Create `config/master_topics.json` with initial topic definitions.

This is the foundation - everything else depends on having topics defined.

---

*Action Plan v1.0 - Ready to Execute*

