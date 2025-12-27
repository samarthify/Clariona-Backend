# Topic-Based Classification Implementation Plan
## Keyword + Embedding Approach

---

## 1. File Structure

```
Clariona-Backend/
├── config/
│   ├── master_topics.json              # Master topics definitions
│   ├── president_config.json           # President's topic config
│   ├── minister_configs/
│   │   ├── petroleum_resources.json   # Petroleum minister config
│   │   ├── education.json              # Education minister config
│   │   └── ...                         # Other minister configs
│   └── topic_embeddings.json           # Pre-computed topic embeddings
│
├── src/
│   ├── processing/
│   │   ├── topic_classifier.py         # NEW: Topic classification logic
│   │   ├── topic_embedding_generator.py # NEW: Generate topic embeddings
│   │   ├── governance_analyzer.py       # MODIFY: Remove LLM, use topic classifier
│   │   ├── issue_classifier.py         # MODIFY: Change scope from ministry to topic
│   │   └── data_processor.py           # MODIFY: Use topic classifier
│   │
│   └── utils/
│       └── similarity.py               # NEW: Embedding similarity functions
│
└── (topic_issues stored in database)   # CHANGED: From ministry_issues/ JSON files
```

---

## 2. Data Models & Schemas

### 2.1 Master Topics Schema

**File: `config/master_topics.json`**

```json
{
    "topics": {
        "fuel_pricing": {
            "name": "Fuel Pricing",
            "description": "Fuel pricing policies, subsidies, and pump price changes",
            "keywords": [
                "fuel", "petrol", "diesel", "subsidy", "pump price", 
                "pricing", "gasoline", "refinery", "pms", "pms price"
            ],
            "category": "energy"
        },
        "presidential_announcements": {
            "name": "Presidential Announcements",
            "description": "Official statements, declarations, and announcements by the President",
            "keywords": [
                "president", "announced", "declared", "stated", "executive",
                "presidential", "commander in chief", "presidency"
            ],
            "category": "executive"
        },
        "military_operations": {
            "name": "Military Operations",
            "description": "Military activities, operations, and defense matters",
            "keywords": [
                "military", "army", "operation", "troops", "defense",
                "armed forces", "soldiers", "combat", "deployment"
            ],
            "category": "defense"
        },
        "education_funding": {
            "name": "Education Funding",
            "description": "Education budget, funding, and financial allocations",
            "keywords": [
                "education", "funding", "budget", "school", "university",
                "educational", "academic", "scholarship", "tuition"
            ],
            "category": "education"
        },
        "asuu_strikes": {
            "name": "ASUU Strikes",
            "description": "Academic Staff Union of Universities strikes and negotiations",
            "keywords": [
                "asuu", "strike", "lecturers", "academic staff", "university strike",
                "asuu strike", "lecturer strike", "academic union"
            ],
            "category": "education"
        }
        // ... more topics
    },
    "version": "1.0",
    "last_updated": "2024-12-27"
}
```

### 2.2 Minister/President Config Schema

**File: `config/president_config.json`**

```json
{
    "owner": "president",
    "owner_name": "President of Nigeria",
    "topics": [
        "presidential_announcements",
        "fuel_pricing",
        "military_operations",
        "cabinet_appointments",
        "executive_orders"
    ],
    "priority_topics": [
        "presidential_announcements",
        "executive_orders"
    ]
}
```

**File: `config/minister_configs/petroleum_resources.json`**

```json
{
    "owner": "petroleum_resources",
    "owner_name": "Minister of Petroleum Resources",
    "topics": [
        "fuel_pricing",
        "subsidy_removal",
        "oil_exploration",
        "nnpc_operations",
        "energy_security"
    ],
    "priority_topics": [
        "fuel_pricing",
        "subsidy_removal"
    ]
}
```

### 2.3 Topic Embeddings Schema

**File: `config/topic_embeddings.json`**

```json
{
    "version": "1.0",
    "model": "text-embedding-3-small",
    "embeddings": {
        "fuel_pricing": [0.123, 0.456, ...],  // 1536 dimensions
        "presidential_announcements": [0.789, 0.012, ...],
        "military_operations": [0.345, 0.678, ...]
        // ... all topics
    },
    "last_generated": "2024-12-27T10:00:00Z"
}
```

### 2.4 Database Schema Changes

**Current:**
```sql
mentions (
    entry_id,
    ministry_hint,          -- Single ministry
    issue_slug,             -- Single issue
    issue_label,
    ...
)
```

**New:**
```sql
mentions (
    entry_id,
    topics,                 -- JSON array of topic-issue pairs
    -- topics: [{"topic": "fuel_pricing", "issue_slug": "...", "issue_label": "..."}, ...]
    ...
)

-- OR separate table for many-to-many relationship
mention_topics (
    mention_id,
    topic_key,
    issue_slug,
    issue_label,
    confidence_score,
    created_at
)
```

---

## 3. Core Implementation

### 3.1 Topic Classifier

**File: `src/processing/topic_classifier.py`**

```python
"""
Topic-based classification using keyword matching and embedding similarity.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger('TopicClassifier')

class TopicClassifier:
    """
    Classifies mentions into multiple topics using keyword matching and embeddings.
    """
    
    def __init__(self, 
                 master_topics_path: str = "config/master_topics.json",
                 topic_embeddings_path: str = "config/topic_embeddings.json",
                 keyword_weight: float = 0.3,
                 embedding_weight: float = 0.7,
                 min_score_threshold: float = 0.5,
                 max_topics: int = 3):
        """
        Initialize topic classifier.
        
        Args:
            master_topics_path: Path to master topics definition
            topic_embeddings_path: Path to pre-computed topic embeddings
            keyword_weight: Weight for keyword matching (0.0-1.0)
            embedding_weight: Weight for embedding similarity (0.0-1.0)
            min_score_threshold: Minimum score to include topic
            max_topics: Maximum number of topics to return
        """
        self.keyword_weight = keyword_weight
        self.embedding_weight = embedding_weight
        self.min_score_threshold = min_score_threshold
        self.max_topics = max_topics
        
        # Load master topics
        self.master_topics = self._load_master_topics(master_topics_path)
        
        # Load topic embeddings
        self.topic_embeddings = self._load_topic_embeddings(topic_embeddings_path)
        
        logger.info(f"TopicClassifier initialized with {len(self.master_topics)} topics")
    
    def _load_master_topics(self, path: str) -> Dict:
        """Load master topics definition."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('topics', {})
        except Exception as e:
            logger.error(f"Error loading master topics: {e}")
            return {}
    
    def _load_topic_embeddings(self, path: str) -> Dict[str, np.ndarray]:
        """Load pre-computed topic embeddings."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                embeddings_dict = data.get('embeddings', {})
                # Convert lists to numpy arrays
                return {
                    topic: np.array(embedding) 
                    for topic, embedding in embeddings_dict.items()
                }
        except Exception as e:
            logger.error(f"Error loading topic embeddings: {e}")
            return {}
    
    def classify(self, text: str, text_embedding: List[float]) -> List[Dict[str, any]]:
        """
        Classify text into multiple topics.
        
        Args:
            text: Text content to classify
            text_embedding: Pre-computed embedding vector (1536 dimensions)
        
        Returns:
            List of topic classifications:
            [
                {
                    "topic": "fuel_pricing",
                    "topic_name": "Fuel Pricing",
                    "confidence": 0.85,
                    "keyword_score": 0.7,
                    "embedding_score": 0.9
                },
                ...
            ]
        """
        if not text or not text.strip():
            return []
        
        if not text_embedding or len(text_embedding) != 1536:
            logger.warning("Invalid embedding provided, using keyword-only classification")
            return self._classify_keyword_only(text)
        
        text_embedding_array = np.array(text_embedding).reshape(1, -1)
        text_lower = text.lower()
        
        topic_scores = []
        
        for topic_key, topic_data in self.master_topics.items():
            # Keyword matching
            keyword_score = self._keyword_match(text_lower, topic_data.get('keywords', []))
            
            # Embedding similarity
            embedding_score = 0.0
            if topic_key in self.topic_embeddings:
                topic_emb = self.topic_embeddings[topic_key].reshape(1, -1)
                similarity = cosine_similarity(text_embedding_array, topic_emb)[0][0]
                embedding_score = float(similarity)
            
            # Combined score
            combined_score = (
                self.keyword_weight * keyword_score +
                self.embedding_weight * embedding_score
            )
            
            if combined_score >= self.min_score_threshold:
                topic_scores.append({
                    "topic": topic_key,
                    "topic_name": topic_data.get('name', topic_key),
                    "confidence": round(combined_score, 3),
                    "keyword_score": round(keyword_score, 3),
                    "embedding_score": round(embedding_score, 3)
                })
        
        # Sort by confidence and return top N
        topic_scores.sort(key=lambda x: x['confidence'], reverse=True)
        return topic_scores[:self.max_topics]
    
    def _keyword_match(self, text_lower: str, keywords: List[str]) -> float:
        """
        Calculate keyword matching score.
        
        Returns normalized score (0.0-1.0) based on keyword matches.
        """
        if not keywords:
            return 0.0
        
        matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
        # Normalize: matches / total keywords, capped at 1.0
        score = min(matches / len(keywords), 1.0)
        
        # Boost score if multiple matches (logarithmic scaling)
        if matches > 0:
            score = min(score * (1 + np.log(matches + 1) / 10), 1.0)
        
        return score
    
    def _classify_keyword_only(self, text: str) -> List[Dict[str, any]]:
        """Fallback classification using only keywords."""
        text_lower = text.lower()
        topic_scores = []
        
        for topic_key, topic_data in self.master_topics.items():
            keyword_score = self._keyword_match(text_lower, topic_data.get('keywords', []))
            
            if keyword_score >= self.min_score_threshold:
                topic_scores.append({
                    "topic": topic_key,
                    "topic_name": topic_data.get('name', topic_key),
                    "confidence": round(keyword_score, 3),
                    "keyword_score": round(keyword_score, 3),
                    "embedding_score": 0.0
                })
        
        topic_scores.sort(key=lambda x: x['confidence'], reverse=True)
        return topic_scores[:self.max_topics]
    
    def get_topics_for_owner(self, owner: str) -> List[str]:
        """
        Get list of topics for a specific owner (president/minister).
        
        Args:
            owner: Owner identifier (e.g., 'president', 'petroleum_resources')
        
        Returns:
            List of topic keys
        """
        config_path = f"config/{owner}_config.json"
        if owner != "president":
            config_path = f"config/minister_configs/{owner}.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('topics', [])
        except Exception as e:
            logger.warning(f"Config not found for {owner}: {e}")
            return []
```

### 3.2 Topic Embedding Generator

**File: `src/processing/topic_embedding_generator.py`**

```python
"""
Generate embeddings for all topics in master topics definition.
Run once to pre-compute topic embeddings.
"""

import json
import os
import openai
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger('TopicEmbeddingGenerator')

class TopicEmbeddingGenerator:
    """Generate embeddings for topics."""
    
    def __init__(self, master_topics_path: str = "config/master_topics.json"):
        self.master_topics_path = master_topics_path
        self.openai_client = None
        self._setup_openai()
    
    def _setup_openai(self):
        """Initialize OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
        else:
            logger.warning("OpenAI API key not available")
    
    def generate_all_embeddings(self, output_path: str = "config/topic_embeddings.json"):
        """
        Generate embeddings for all topics and save to file.
        
        Args:
            output_path: Path to save embeddings JSON file
        """
        if not self.openai_client:
            logger.error("OpenAI client not available")
            return
        
        # Load master topics
        with open(self.master_topics_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            topics = data.get('topics', {})
        
        embeddings = {}
        
        logger.info(f"Generating embeddings for {len(topics)} topics...")
        
        for topic_key, topic_data in topics.items():
            # Create embedding text from name + description
            embedding_text = f"{topic_data.get('name', '')} {topic_data.get('description', '')}"
            
            try:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=embedding_text
                )
                embedding = response.data[0].embedding
                embeddings[topic_key] = embedding
                logger.debug(f"Generated embedding for {topic_key}")
            except Exception as e:
                logger.error(f"Error generating embedding for {topic_key}: {e}")
        
        # Save embeddings
        output_data = {
            "version": "1.0",
            "model": "text-embedding-3-small",
            "embeddings": embeddings,
            "last_generated": json.dumps({"timestamp": "auto-generated"})
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Saved {len(embeddings)} topic embeddings to {output_path}")

# CLI script to generate embeddings
if __name__ == "__main__":
    generator = TopicEmbeddingGenerator()
    generator.generate_all_embeddings()
```

### 3.3 Modified Governance Analyzer

**File: `src/processing/governance_analyzer.py` (MODIFIED)**

```python
# Remove LLM-based classification, use TopicClassifier instead

from .topic_classifier import TopicClassifier

class GovernanceAnalyzer:
    def __init__(self, enable_issue_classification: bool = True):
        self.enable_issue_classification = enable_issue_classification
        self.topic_classifier = TopicClassifier()
        self.issue_classifier = None
        
        if self.enable_issue_classification:
            from .issue_classifier import IssueClassifier
            self.issue_classifier = IssueClassifier()
    
    def analyze(self, text: str, source_type: str = None, 
                sentiment: str = None, text_embedding: List[float] = None) -> Dict[str, Any]:
        """
        Analyze text and return topic classifications.
        
        Args:
            text: Text to analyze
            source_type: Source type (optional)
            sentiment: Pre-computed sentiment (optional)
            text_embedding: Pre-computed text embedding (required)
        
        Returns:
            {
                'topics': [
                    {
                        'topic': 'fuel_pricing',
                        'topic_name': 'Fuel Pricing',
                        'confidence': 0.85,
                        'issue_slug': 'fuel-subsidy-removal',
                        'issue_label': 'Fuel Subsidy Removal'
                    },
                    ...
                ],
                'sentiment': sentiment,
                ...
            }
        """
        if not text or not text.strip():
            return self._get_default_result(sentiment=sentiment)
        
        if not text_embedding:
            logger.warning("No embedding provided, cannot classify topics")
            return self._get_default_result(sentiment=sentiment)
        
        try:
            # Step 1: Classify into topics
            topic_classifications = self.topic_classifier.classify(text, text_embedding)
            
            if not topic_classifications:
                return self._get_default_result(sentiment=sentiment)
            
            # Step 2: Classify issues for each topic
            result_topics = []
            for topic_class in topic_classifications:
                topic_key = topic_class['topic']
                
                # Classify issue within this topic
                issue_slug = None
                issue_label = None
                
                if self.enable_issue_classification and self.issue_classifier:
                    issue_slug, issue_label = self.issue_classifier.classify_issue(
                        text, topic_key  # Changed: topic instead of ministry
                    )
                
                result_topics.append({
                    'topic': topic_key,
                    'topic_name': topic_class['topic_name'],
                    'confidence': topic_class['confidence'],
                    'keyword_score': topic_class.get('keyword_score', 0),
                    'embedding_score': topic_class.get('embedding_score', 0),
                    'issue_slug': issue_slug,
                    'issue_label': issue_label
                })
            
            return {
                'topics': result_topics,
                'sentiment': sentiment or 'neutral',
                'is_governance_content': len(result_topics) > 0,
                'page_type': self._determine_page_type(sentiment)
            }
            
        except Exception as e:
            logger.error(f"Error in topic analysis: {e}")
            return self._get_default_result(error=str(e), sentiment=sentiment)
```

### 3.4 Modified Issue Classifier (Database-Based)

**File: `src/processing/issue_classifier.py` (MODIFIED)**

```python
# Change from JSON files to database, scope from ministry to topic

from sqlalchemy.orm import Session
from models import TopicIssue
from datetime import datetime

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
        self.max_issues_per_topic = 20
        self.openai_client = None
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
        """Save or update issue in database."""
        existing = self.db.query(TopicIssue).filter(
            TopicIssue.topic_key == topic,
            TopicIssue.issue_slug == issue_slug
        ).first()
        
        if existing:
            existing.mention_count = mention_count
            existing.last_updated = datetime.now()
            self.db.commit()
            return existing
        else:
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
            topic: The topic category (changed from ministry)
        
        Returns:
            (issue_slug, issue_label) tuple
        """
        # Load existing issues from database
        topic_data = self.load_topic_issues(topic)
        existing_issues = topic_data.get('issues', [])
        
        # ... rest of classification logic stays the same
        # - Same AI comparison logic
        # - Same 20 issue limit
        # - Same matching/consolidation
        
        # When creating/updating, use save_topic_issue()
        # When incrementing, use increment_issue_mention_count()
```

**Key Changes:**
- ✅ **Storage**: Database table `topic_issues` instead of JSON files
- ✅ **Scope**: Topic instead of ministry  
- ✅ **Interface**: Database session instead of file paths
- ✅ **Logic**: Same dynamic issue creation, just database-backed

---

## 4. Integration Points

### 4.1 Data Processor Integration

**File: `src/processing/data_processor.py` (MODIFIED)**

```python
def batch_get_sentiment(self, texts: List[str], source_types: List[str] = None, 
                       max_workers: int = 20) -> List[Dict[str, Any]]:
    """
    Batch process with topic classification.
    """
    # ... existing code to get embeddings ...
    
    # For each text:
    # 1. Get sentiment (existing)
    # 2. Get embedding (existing)
    # 3. Classify topics (NEW)
    # 4. Classify issues per topic (MODIFIED)
    
    for i, text in enumerate(texts):
        embedding = embeddings[i]
        sentiment_result = sentiment_results[i]
        
        # Topic classification
        governance_result = self.governance_analyzer.analyze(
            text, 
            source_types[i] if source_types else None,
            sentiment_result['sentiment_label'],
            embedding  # Pass embedding
        )
        
        # Combine results
        combined_result = {
            **sentiment_result,
            'topics': governance_result.get('topics', []),
            # ... other fields
        }
```

### 4.2 Database Updates

**Migration Script: `migrations/add_topics_column.sql`**

```sql
-- Add topics column (JSON array)
ALTER TABLE mentions ADD COLUMN topics JSONB DEFAULT '[]'::jsonb;

-- Create index for topic queries
CREATE INDEX idx_mentions_topics ON mentions USING GIN (topics);

-- Migration: Convert existing ministry_hint to topics format
UPDATE mentions 
SET topics = jsonb_build_array(
    jsonb_build_object(
        'topic', ministry_hint,
        'topic_name', (SELECT name FROM ministries WHERE key = ministry_hint),
        'confidence', 1.0,
        'issue_slug', issue_slug,
        'issue_label', issue_label
    )
)
WHERE ministry_hint IS NOT NULL AND ministry_hint != 'non_governance';
```

---

## 5. Dashboard Filtering

**File: `src/api/dashboard.py` (NEW/MODIFIED)**

```python
def get_mentions_for_owner(owner: str, filters: Dict = None):
    """
    Get mentions for a specific owner (president/minister).
    
    Args:
        owner: Owner identifier ('president', 'petroleum_resources', etc.)
        filters: Additional filters
    
    Returns:
        List of mentions that have topics matching owner's config
    """
    # Load owner config
    topic_classifier = TopicClassifier()
    owner_topics = topic_classifier.get_topics_for_owner(owner)
    
    if not owner_topics:
        return []
    
    # Query mentions with topics matching owner's topics
    # Using PostgreSQL JSONB queries
    query = """
        SELECT * FROM mentions
        WHERE topics @> ANY(
            SELECT jsonb_build_array(jsonb_build_object('topic', topic))
            FROM unnest(%s::text[]) AS topic
        )
    """
    
    # Execute query with owner_topics
    # ... return results
```

---

## 6. Implementation Steps

### Phase 1: Setup (Day 1)
1. ✅ Create `config/master_topics.json` with initial topics
2. ✅ Create `config/president_config.json` and minister configs
3. ✅ Run `TopicEmbeddingGenerator` to create `config/topic_embeddings.json`
4. ✅ Create `TopicClassifier` class

### Phase 2: Integration (Day 2)
1. ✅ Modify `GovernanceAnalyzer` to use `TopicClassifier`
2. ✅ Modify `IssueClassifier` to be topic-scoped
3. ✅ Update `DataProcessor` to pass embeddings to topic classifier
4. ✅ Test classification pipeline

### Phase 3: Database & Storage (Day 3)
1. ✅ Add `topics` column to mentions table
2. ✅ Update issue storage from `ministry_issues/` to `topic_issues/`
3. ✅ Create migration script for existing data
4. ✅ Update dashboard queries

### Phase 4: Testing & Tuning (Day 4)
1. ✅ Test with sample mentions
2. ✅ Tune keyword lists and weights
3. ✅ Validate topic assignments
4. ✅ Performance testing

---

## 7. Configuration Examples

### Example: Master Topics (excerpt)

```json
{
    "topics": {
        "fuel_pricing": {
            "name": "Fuel Pricing",
            "description": "Fuel pricing policies, subsidies, and pump price changes affecting petroleum products",
            "keywords": ["fuel", "petrol", "diesel", "subsidy", "pump price", "pricing", "gasoline"],
            "category": "energy"
        }
    }
}
```

### Example: President Config

```json
{
    "owner": "president",
    "topics": [
        "presidential_announcements",
        "fuel_pricing",
        "military_operations",
        "cabinet_appointments"
    ]
}
```

---

## 8. Key Changes Summary

| Component | Current | New |
|-----------|---------|-----|
| **Classification** | LLM-based, single ministry | Keyword + Embedding, multiple topics |
| **Storage** | `ministry_issues/{ministry}.json` | `topic_issues/{topic}.json` |
| **Database** | `ministry_hint` (single) | `topics` (JSON array) |
| **Issue Scope** | Per ministry | Per topic |
| **Dashboard** | Filter by ministry | Filter by topic membership |
| **API Calls** | Required for classification | Only for embedding generation (one-time) |

---

## 9. Benefits

✅ **Fast**: Local computation, no API calls  
✅ **Cheap**: No per-classification costs  
✅ **Reliable**: No API failures  
✅ **Scalable**: Batch processing friendly  
✅ **Transparent**: Can debug keyword/embedding matches  
✅ **Flexible**: Easy to add/modify topics and keywords  

---

*Implementation Plan v1.0*

