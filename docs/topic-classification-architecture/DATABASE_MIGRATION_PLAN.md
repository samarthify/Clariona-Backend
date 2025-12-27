# Database Migration Plan: Topics & Mentions Many-to-Many Relationship

## Current Database Schema

### Current Structure
```sql
-- mentions table (current)
CREATE TABLE mentions (
    entry_id UUID PRIMARY KEY,
    text TEXT,
    content TEXT,
    title TEXT,
    source_type VARCHAR(50),
    
    -- Current single ministry classification
    ministry_hint VARCHAR(100),  -- Single ministry
    issue_slug VARCHAR(200),       -- Single issue
    issue_label VARCHAR(500),
    issue_confidence FLOAT,
    
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Current issue storage (file-based)
-- ministry_issues/{ministry_key}.json
```

## New Database Schema

### Option 1: Junction Table (Recommended for Many-to-Many)

```sql
-- mentions table (updated - remove single ministry fields)
CREATE TABLE mentions (
    entry_id UUID PRIMARY KEY,
    text TEXT,
    content TEXT,
    title TEXT,
    source_type VARCHAR(50),
    
    -- Keep sentiment (not topic-specific)
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- NEW: Junction table for many-to-many relationship
CREATE TABLE mention_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mention_id UUID NOT NULL REFERENCES mentions(entry_id) ON DELETE CASCADE,
    topic_key VARCHAR(100) NOT NULL,
    topic_name VARCHAR(200),
    
    -- Issue classification per topic
    issue_slug VARCHAR(200),
    issue_label VARCHAR(500),
    issue_confidence FLOAT,
    
    -- Classification scores
    topic_confidence FLOAT,        -- Overall topic confidence
    keyword_score FLOAT,            -- Keyword matching score
    embedding_score FLOAT,          -- Embedding similarity score
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint: one topic-issue pair per mention
    UNIQUE(mention_id, topic_key, issue_slug)
);

-- Indexes for performance
CREATE INDEX idx_mention_topics_mention_id ON mention_topics(mention_id);
CREATE INDEX idx_mention_topics_topic_key ON mention_topics(topic_key);
CREATE INDEX idx_mention_topics_issue_slug ON mention_topics(issue_slug);

-- Composite index for dashboard queries
CREATE INDEX idx_mention_topics_topic_mention ON mention_topics(topic_key, mention_id);
```

### Option 2: JSONB Column (Simpler, but less queryable)

```sql
-- mentions table with JSONB topics array
CREATE TABLE mentions (
    entry_id UUID PRIMARY KEY,
    text TEXT,
    content TEXT,
    title TEXT,
    source_type VARCHAR(50),
    
    -- Multi-topic classification (JSONB array)
    topics JSONB DEFAULT '[]'::jsonb,
    -- Structure: [
    --   {
    --     "topic": "fuel_pricing",
    --     "topic_name": "Fuel Pricing",
    --     "confidence": 0.85,
    --     "keyword_score": 0.7,
    --     "embedding_score": 0.9,
    --     "issue_slug": "fuel-subsidy-removal",
    --     "issue_label": "Fuel Subsidy Removal",
    --     "issue_confidence": 0.92
    --   },
    --   ...
    -- ]
    
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- GIN index for JSONB queries
CREATE INDEX idx_mentions_topics_gin ON mentions USING GIN (topics);

-- Index for specific topic queries
CREATE INDEX idx_mentions_topics_topic ON mentions USING GIN ((topics -> 'topic'));
```

## Recommended Approach: Junction Table (Option 1)

### Why Junction Table?
✅ **Better for queries**: Easy to filter by topic, count mentions per topic  
✅ **Normalized**: Follows database best practices  
✅ **Flexible**: Easy to add topic-specific metadata later  
✅ **Performance**: Better indexing and query optimization  
✅ **Relationships**: Clear foreign key relationships  

### Database Schema (Final)

```sql
-- ============================================
-- 1. Mentions Table (Core content)
-- ============================================
CREATE TABLE mentions (
    entry_id UUID PRIMARY KEY,
    text TEXT,
    content TEXT,
    title TEXT,
    description TEXT,
    source_type VARCHAR(50),
    source_url TEXT,
    
    -- Sentiment (not topic-specific)
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    sentiment_justification TEXT,
    
    -- Embedding (for similarity matching)
    embedding JSONB,  -- Store as JSON array [0.123, 0.456, ...]
    embedding_model VARCHAR(50) DEFAULT 'text-embedding-3-small',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    collected_at TIMESTAMP
);

-- ============================================
-- 2. Topics Master Table (Reference)
-- ============================================
CREATE TABLE topics (
    topic_key VARCHAR(100) PRIMARY KEY,
    topic_name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    keywords TEXT[],  -- Array of keywords
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 3. Mention-Topic Junction Table (Many-to-Many)
-- ============================================
CREATE TABLE mention_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mention_id UUID NOT NULL REFERENCES mentions(entry_id) ON DELETE CASCADE,
    topic_key VARCHAR(100) NOT NULL REFERENCES topics(topic_key),
    
    -- Classification scores
    topic_confidence FLOAT NOT NULL,      -- Overall confidence (0.0-1.0)
    keyword_score FLOAT,                 -- Keyword matching score
    embedding_score FLOAT,               -- Embedding similarity score
    
    -- Issue classification (per topic)
    issue_slug VARCHAR(200),
    issue_label VARCHAR(500),
    issue_confidence FLOAT,
    issue_keywords JSONB,                -- Keywords for this issue
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(mention_id, topic_key),  -- One topic classification per mention
    CHECK (topic_confidence >= 0.0 AND topic_confidence <= 1.0)
);

-- ============================================
-- 4. Indexes for Performance
-- ============================================
-- Mention lookups
CREATE INDEX idx_mention_topics_mention_id ON mention_topics(mention_id);
CREATE INDEX idx_mention_topics_created_at ON mention_topics(created_at DESC);

-- Topic filtering (for dashboards)
CREATE INDEX idx_mention_topics_topic_key ON mention_topics(topic_key);
CREATE INDEX idx_mention_topics_topic_confidence ON mention_topics(topic_key, topic_confidence DESC);

-- Issue queries
CREATE INDEX idx_mention_topics_issue_slug ON mention_topics(issue_slug) WHERE issue_slug IS NOT NULL;

-- Composite index for common queries
CREATE INDEX idx_mention_topics_topic_mention ON mention_topics(topic_key, mention_id, topic_confidence DESC);

-- Embedding similarity (if using pgvector extension)
-- CREATE EXTENSION IF NOT EXISTS vector;
-- CREATE INDEX idx_mentions_embedding ON mentions USING ivfflat (embedding vector_cosine_ops);

-- ============================================
-- 5. Topic Issues (Dynamic Issues per Topic)
-- ============================================
CREATE TABLE topic_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_key VARCHAR(100) NOT NULL REFERENCES topics(topic_key) ON DELETE CASCADE,
    issue_slug VARCHAR(200) NOT NULL,
    issue_label VARCHAR(500) NOT NULL,
    
    -- Statistics
    mention_count INTEGER DEFAULT 0,
    max_issues INTEGER DEFAULT 20,  -- Per topic limit
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(topic_key, issue_slug),  -- One issue slug per topic
    CHECK (mention_count >= 0)
);

-- Indexes for issue queries
CREATE INDEX idx_topic_issues_topic_key ON topic_issues(topic_key);
CREATE INDEX idx_topic_issues_issue_slug ON topic_issues(issue_slug);
CREATE INDEX idx_topic_issues_mention_count ON topic_issues(topic_key, mention_count DESC);
CREATE INDEX idx_topic_issues_topic_updated ON topic_issues(topic_key, last_updated DESC);

-- ============================================
-- 6. Owner Configs (Reference Table)
-- ============================================
CREATE TABLE owner_configs (
    owner_key VARCHAR(100) PRIMARY KEY,  -- 'president', 'petroleum_resources', etc.
    owner_name VARCHAR(200) NOT NULL,
    owner_type VARCHAR(50),  -- 'president', 'minister', etc.
    topics TEXT[],  -- Array of topic_keys this owner cares about
    priority_topics TEXT[],  -- High-priority topics
    is_active BOOLEAN DEFAULT TRUE,
    config_data JSONB,  -- Additional config data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for topic membership queries
CREATE INDEX idx_owner_configs_topics ON owner_configs USING GIN (topics);
```

## Migration Script

### Step 1: Create New Tables

```sql
-- migration_001_create_topics_tables.sql

BEGIN;

-- 1. Create topics master table
CREATE TABLE IF NOT EXISTS topics (
    topic_key VARCHAR(100) PRIMARY KEY,
    topic_name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    keywords TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create mention_topics junction table
CREATE TABLE IF NOT EXISTS mention_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mention_id UUID NOT NULL REFERENCES mentions(entry_id) ON DELETE CASCADE,
    topic_key VARCHAR(100) NOT NULL REFERENCES topics(topic_key),
    topic_confidence FLOAT NOT NULL,
    keyword_score FLOAT,
    embedding_score FLOAT,
    issue_slug VARCHAR(200),
    issue_label VARCHAR(500),
    issue_confidence FLOAT,
    issue_keywords JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mention_id, topic_key),
    CHECK (topic_confidence >= 0.0 AND topic_confidence <= 1.0)
);

-- 3. Create topic_issues table
CREATE TABLE IF NOT EXISTS topic_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_key VARCHAR(100) NOT NULL REFERENCES topics(topic_key) ON DELETE CASCADE,
    issue_slug VARCHAR(200) NOT NULL,
    issue_label VARCHAR(500) NOT NULL,
    mention_count INTEGER DEFAULT 0,
    max_issues INTEGER DEFAULT 20,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic_key, issue_slug),
    CHECK (mention_count >= 0)
);

-- 4. Create owner_configs table
CREATE TABLE IF NOT EXISTS owner_configs (
    owner_key VARCHAR(100) PRIMARY KEY,
    owner_name VARCHAR(200) NOT NULL,
    owner_type VARCHAR(50),
    topics TEXT[],
    priority_topics TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    config_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Create indexes
CREATE INDEX IF NOT EXISTS idx_mention_topics_mention_id ON mention_topics(mention_id);
CREATE INDEX IF NOT EXISTS idx_mention_topics_topic_key ON mention_topics(topic_key);
CREATE INDEX IF NOT EXISTS idx_mention_topics_topic_mention ON mention_topics(topic_key, mention_id, topic_confidence DESC);
CREATE INDEX IF NOT EXISTS idx_topic_issues_topic_key ON topic_issues(topic_key);
CREATE INDEX IF NOT EXISTS idx_topic_issues_mention_count ON topic_issues(topic_key, mention_count DESC);
CREATE INDEX IF NOT EXISTS idx_owner_configs_topics ON owner_configs USING GIN (topics);

COMMIT;
```

### Step 2: Migrate Existing Data

```sql
-- migration_002_migrate_existing_data.sql

BEGIN;

-- 1. Populate topics table from master_topics.json
-- (This would be done via Python script, but SQL for reference)
INSERT INTO topics (topic_key, topic_name, description, keywords)
VALUES 
    ('petroleum_resources', 'Petroleum Resources', 'Petroleum and energy resources', ARRAY['oil', 'gas', 'petroleum']),
    ('education', 'Education', 'Education sector', ARRAY['education', 'school', 'university']),
    -- ... more topics from master_topics.json
ON CONFLICT (topic_key) DO NOTHING;

-- 2. Migrate existing mentions to mention_topics
-- Convert single ministry_hint to topic classification
INSERT INTO mention_topics (
    mention_id,
    topic_key,
    topic_confidence,
    issue_slug,
    issue_label,
    issue_confidence
)
SELECT 
    entry_id AS mention_id,
    ministry_hint AS topic_key,  -- Use ministry_hint as topic_key
    1.0 AS topic_confidence,      -- Legacy data gets full confidence
    issue_slug,
    issue_label,
    issue_confidence
FROM mentions
WHERE ministry_hint IS NOT NULL 
  AND ministry_hint != 'non_governance'
  AND EXISTS (SELECT 1 FROM topics WHERE topic_key = mentions.ministry_hint);

-- 3. Migrate existing issues from JSON files to database
-- (This would be done via Python script, but SQL for reference)
-- For each topic, load issues from topic_issues/{topic}.json and insert
-- Example:
INSERT INTO topic_issues (topic_key, issue_slug, issue_label, mention_count, created_at, last_updated)
SELECT 
    'fuel_pricing' AS topic_key,
    issue->>'slug' AS issue_slug,
    issue->>'label' AS issue_label,
    (issue->>'mention_count')::INTEGER AS mention_count,
    (issue->>'created_at')::TIMESTAMP AS created_at,
    (issue->>'last_updated')::TIMESTAMP AS last_updated
FROM jsonb_array_elements(
    (SELECT issues FROM jsonb_build_object('issues', '[...]')::jsonb)
) AS issue
ON CONFLICT (topic_key, issue_slug) DO UPDATE
SET mention_count = EXCLUDED.mention_count,
    last_updated = EXCLUDED.last_updated;

-- 4. Populate owner_configs from config files
INSERT INTO owner_configs (owner_key, owner_name, owner_type, topics)
VALUES 
    ('president', 'President of Nigeria', 'president', 
     ARRAY['presidential_announcements', 'fuel_pricing', 'military_operations']),
    ('petroleum_resources', 'Minister of Petroleum Resources', 'minister',
     ARRAY['fuel_pricing', 'subsidy_removal', 'oil_exploration']),
    -- ... more owners
ON CONFLICT (owner_key) DO UPDATE
SET topics = EXCLUDED.topics,
    updated_at = CURRENT_TIMESTAMP;

COMMIT;
```

### Step 3: Deprecate Old Columns (Optional - Keep for backward compatibility)

```sql
-- migration_003_deprecate_old_columns.sql

BEGIN;

-- Option A: Keep columns but mark as deprecated (recommended for gradual migration)
ALTER TABLE mentions 
ADD COLUMN IF NOT EXISTS ministry_hint_deprecated VARCHAR(100);

-- Copy data to deprecated column
UPDATE mentions 
SET ministry_hint_deprecated = ministry_hint
WHERE ministry_hint IS NOT NULL;

-- Remove old columns (DO THIS AFTER VERIFICATION)
-- ALTER TABLE mentions DROP COLUMN IF EXISTS ministry_hint;
-- ALTER TABLE mentions DROP COLUMN IF EXISTS issue_slug;
-- ALTER TABLE mentions DROP COLUMN IF EXISTS issue_label;
-- ALTER TABLE mentions DROP COLUMN IF EXISTS issue_confidence;

COMMIT;
```

## Query Examples

### Get Mentions for a Specific Owner

```sql
-- Get all mentions for president (has any topic in president's config)
SELECT DISTINCT m.*
FROM mentions m
INNER JOIN mention_topics mt ON m.entry_id = mt.mention_id
INNER JOIN owner_configs oc ON mt.topic_key = ANY(oc.topics)
WHERE oc.owner_key = 'president'
  AND oc.is_active = TRUE
ORDER BY m.created_at DESC;
```

### Get Mentions for a Specific Topic

```sql
-- Get all mentions for 'fuel_pricing' topic
SELECT m.*, mt.topic_confidence, mt.issue_slug, mt.issue_label
FROM mentions m
INNER JOIN mention_topics mt ON m.entry_id = mt.mention_id
WHERE mt.topic_key = 'fuel_pricing'
ORDER BY mt.topic_confidence DESC, m.created_at DESC;
```

### Get Topic Statistics

```sql
-- Count mentions per topic
SELECT 
    t.topic_key,
    t.topic_name,
    COUNT(mt.id) AS mention_count,
    AVG(mt.topic_confidence) AS avg_confidence
FROM topics t
LEFT JOIN mention_topics mt ON t.topic_key = mt.topic_key
WHERE t.is_active = TRUE
GROUP BY t.topic_key, t.topic_name
ORDER BY mention_count DESC;
```

### Get Mentions with Multiple Topics

```sql
-- Get mentions that have multiple topics
SELECT 
    m.entry_id,
    m.text,
    COUNT(mt.topic_key) AS topic_count,
    array_agg(mt.topic_key) AS topics
FROM mentions m
INNER JOIN mention_topics mt ON m.entry_id = mt.mention_id
GROUP BY m.entry_id, m.text
HAVING COUNT(mt.topic_key) > 1
ORDER BY topic_count DESC;
```

### Get Issues for a Topic

```sql
-- Get all issues for a specific topic, ordered by mention count
SELECT 
    issue_slug,
    issue_label,
    mention_count,
    created_at,
    last_updated
FROM topic_issues
WHERE topic_key = 'fuel_pricing'
ORDER BY mention_count DESC, last_updated DESC;
```

### Get Top Issues Across All Topics

```sql
-- Get top 10 issues by mention count across all topics
SELECT 
    ti.topic_key,
    t.topic_name,
    ti.issue_slug,
    ti.issue_label,
    ti.mention_count
FROM topic_issues ti
INNER JOIN topics t ON ti.topic_key = t.topic_key
ORDER BY ti.mention_count DESC
LIMIT 10;
```

### Get Issue Statistics per Topic

```sql
-- Count issues and total mentions per topic
SELECT 
    t.topic_key,
    t.topic_name,
    COUNT(ti.id) AS issue_count,
    SUM(ti.mention_count) AS total_mentions,
    AVG(ti.mention_count) AS avg_mentions_per_issue
FROM topics t
LEFT JOIN topic_issues ti ON t.topic_key = ti.topic_key
WHERE t.is_active = TRUE
GROUP BY t.topic_key, t.topic_name
ORDER BY total_mentions DESC;
```

### Get Mentions for a Specific Issue

```sql
-- Get all mentions classified into a specific issue
SELECT 
    m.*,
    mt.topic_key,
    mt.topic_confidence,
    mt.issue_confidence
FROM mentions m
INNER JOIN mention_topics mt ON m.entry_id = mt.mention_id
WHERE mt.topic_key = 'fuel_pricing'
  AND mt.issue_slug = 'fuel-subsidy-removal'
ORDER BY mt.issue_confidence DESC, m.created_at DESC;
```

## Issue Classifier Changes (Database-Based)

### File: `src/processing/issue_classifier.py`

**Changes: Use database instead of JSON files**

```python
from sqlalchemy.orm import Session
from models import TopicIssue  # Database model

class IssueClassifier:
    def __init__(self, db_session: Session, model: str = "gpt-5-nano"):
        """
        Initialize issue classifier with database session.
        
        Args:
            db_session: Database session for querying/updating issues
            model: Model to use (for AI classification if needed)
        """
        self.db = db_session
        self.model = model
        self.openai_client = None
        self.max_issues_per_topic = 20
        self.setup_openai()
    
    def load_topic_issues(self, topic: str) -> Dict:
        """
        Load existing issue labels for a topic from database.
        
        Returns:
            {
                "topic": "fuel_pricing",
                "issue_count": 3,
                "max_issues": 20,
                "issues": [
                    {
                        "slug": "fuel-subsidy-removal",
                        "label": "Fuel Subsidy Removal",
                        "mention_count": 150,
                        "created_at": "2025-11-02T10:00:00",
                        "last_updated": "2025-11-02T15:30:00"
                    },
                    ...
                ]
            }
        """
        # Query issues from database
        issues = self.db.query(TopicIssue).filter(
            TopicIssue.topic_key == topic
        ).order_by(TopicIssue.mention_count.desc()).all()
        
        issues_list = [
            {
                "slug": issue.issue_slug,
                "label": issue.issue_label,
                "mention_count": issue.mention_count,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "last_updated": issue.last_updated.isoformat() if issue.last_updated else None
            }
            for issue in issues
        ]
        
        return {
            "topic": topic,
            "issue_count": len(issues_list),
            "max_issues": self.max_issues_per_topic,
            "issues": issues_list
        }
    
    def save_topic_issue(self, topic: str, issue_slug: str, issue_label: str, 
                        mention_count: int = 1) -> TopicIssue:
        """
        Save or update issue in database.
        
        Returns:
            TopicIssue database object
        """
        # Check if issue exists
        existing = self.db.query(TopicIssue).filter(
            TopicIssue.topic_key == topic,
            TopicIssue.issue_slug == issue_slug
        ).first()
        
        if existing:
            # Update existing
            existing.mention_count = mention_count
            existing.last_updated = datetime.now()
            self.db.commit()
            return existing
        else:
            # Create new
            new_issue = TopicIssue(
                topic_key=topic,
                issue_slug=issue_slug,
                issue_label=issue_label,
                mention_count=mention_count,
                max_issues=self.max_issues_per_topic
            )
            self.db.add(new_issue)
            self.db.commit()
            return new_issue
    
    def increment_issue_mention_count(self, topic: str, issue_slug: str):
        """Increment mention count for an issue."""
        issue = self.db.query(TopicIssue).filter(
            TopicIssue.topic_key == topic,
            TopicIssue.issue_slug == issue_slug
        ).first()
        
        if issue:
            issue.mention_count += 1
            issue.last_updated = datetime.now()
            self.db.commit()
    
    def classify_issue(self, text: str, topic: str) -> Tuple[str, str]:
        """
        Classify a mention into an issue within the topic.
        
        Args:
            text: The text content to classify
            topic: The topic category (CHANGED from ministry)
        
        Returns:
            (issue_slug, issue_label) tuple
        """
        # Load existing issues from database
        topic_data = self.load_topic_issues(topic)
        existing_issues = topic_data.get('issues', [])
        max_issues = topic_data.get('max_issues', self.max_issues_per_topic)
        
        # If over limit, trim to top N by mention count
        if len(existing_issues) > max_issues:
            logger.warning(f"Topic {topic} has {len(existing_issues)} issues, exceeding limit. Trimming.")
            # Keep only top N issues in database
            issues_to_keep = sorted(existing_issues, 
                                  key=lambda x: x.get('mention_count', 0), 
                                  reverse=True)[:max_issues]
            # Delete excess issues (implement cleanup method)
            self._trim_topic_issues(topic, [i['slug'] for i in issues_to_keep])
            existing_issues = issues_to_keep
        
        # Rest of classification logic stays the same
        # - If no issues, create first one
        # - If at max, use consolidation
        # - Otherwise, compare and match/create
        
        # ... (same AI classification logic as before)
        
        # When creating/updating issues, use save_topic_issue() instead of file write
        # When incrementing counts, use increment_issue_mention_count()
```

**Key Changes:**
- ✅ **Storage**: Database table `topic_issues` instead of JSON files
- ✅ **Scope**: Topic instead of ministry
- ✅ **Logic**: Same dynamic issue creation, just database-backed
- ✅ **Queries**: Use SQLAlchemy ORM instead of file I/O
- ✅ **Performance**: Database indexes for fast lookups

**Benefits:**
- ✅ **Consistency**: All data in database
- ✅ **Queryable**: Can query issues across topics easily
- ✅ **Transactional**: ACID guarantees
- ✅ **Scalable**: Better performance than file I/O
- ✅ **Backup**: Database backups include issues

## Database Model Definition

### SQLAlchemy Model: `src/models.py`

```python
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, ARRAY, JSONB, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class Topic(Base):
    """Master topics table."""
    __tablename__ = 'topics'
    
    topic_key = Column(String(100), primary_key=True)
    topic_name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50))
    keywords = Column(ARRAY(Text))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TopicIssue(Base):
    """Dynamic issues per topic (stored in database)."""
    __tablename__ = 'topic_issues'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_key = Column(String(100), ForeignKey('topics.topic_key', ondelete='CASCADE'), nullable=False)
    issue_slug = Column(String(200), nullable=False)
    issue_label = Column(String(500), nullable=False)
    mention_count = Column(Integer, default=0)
    max_issues = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('topic_key', 'issue_slug', name='uq_topic_issue'),
        CheckConstraint('mention_count >= 0', name='check_mention_count_positive')
    )
    
    # Relationship
    topic = relationship('Topic', backref='issues')

class MentionTopic(Base):
    """Junction table: many-to-many relationship between mentions and topics."""
    __tablename__ = 'mention_topics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mention_id = Column(UUID(as_uuid=True), ForeignKey('mentions.entry_id', ondelete='CASCADE'), nullable=False)
    topic_key = Column(String(100), ForeignKey('topics.topic_key'), nullable=False)
    
    # Classification scores
    topic_confidence = Column(Float, nullable=False)
    keyword_score = Column(Float)
    embedding_score = Column(Float)
    
    # Issue classification (per topic)
    issue_slug = Column(String(200))
    issue_label = Column(String(500))
    issue_confidence = Column(Float)
    issue_keywords = Column(JSONB)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('mention_id', 'topic_key', name='uq_mention_topic'),
        CheckConstraint('topic_confidence >= 0.0 AND topic_confidence <= 1.0', name='check_confidence_range')
    )
    
    # Relationships
    mention = relationship('Mention', backref='topic_classifications')
    topic = relationship('Topic', backref='mention_classifications')

class OwnerConfig(Base):
    """Owner (president/minister) configurations."""
    __tablename__ = 'owner_configs'
    
    owner_key = Column(String(100), primary_key=True)
    owner_name = Column(String(200), nullable=False)
    owner_type = Column(String(50))  # 'president', 'minister', etc.
    topics = Column(ARRAY(Text))  # Array of topic_keys
    priority_topics = Column(ARRAY(Text))
    is_active = Column(Boolean, default=True)
    config_data = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## Summary

### Database Changes
✅ **Junction table** (`mention_topics`) for many-to-many relationship  
✅ **Topics master table** for reference data  
✅ **Topic issues table** (`topic_issues`) for database-backed issue storage  
✅ **Owner configs table** for dashboard filtering  
✅ **Proper indexes** for performance  
✅ **Migration scripts** for existing data  

### Issue Classifier Changes
✅ **Database-backed**: Issues stored in `topic_issues` table instead of JSON files  
✅ **Scope change**: Topic instead of ministry  
✅ **Same logic**: Dynamic issue creation unchanged  
✅ **Same structure**: 20 issues per topic (was per ministry)  
✅ **Better performance**: Database queries instead of file I/O  

### Benefits
✅ **Normalized**: Proper many-to-many relationship  
✅ **Queryable**: Easy to filter by topic, owner, issue  
✅ **Scalable**: Handles multiple topics per mention efficiently  
✅ **Consistent**: All data in database (topics, issues, mentions)  
✅ **Transactional**: ACID guarantees for issue updates  
✅ **Backward compatible**: Can keep old columns during migration  

---

*Migration Plan v1.0 - Updated with Database-Backed Issues*

