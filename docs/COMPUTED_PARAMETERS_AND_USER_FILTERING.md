# Computed Parameters and User Filtering Guide

This document explains all parameters computed for **mentions**, **issues**, and **topics** during the test cycle no-auth flow, and how user-specific filtering determines what data is shown to each user.

---

## Table of Contents

1. [Test Cycle No-Auth Flow Overview](#test-cycle-no-auth-flow-overview)
2. [Parameters Computed for a Single Mention](#parameters-computed-for-a-single-mention)
3. [Parameters Computed for an Issue](#parameters-computed-for-an-issue)
4. [Parameters Computed for a Topic](#parameters-computed-for-a-topic)
5. [User-Specific Filtering](#user-specific-filtering)
6. [Configuration Guide](#configuration-guide)
7. [Additional Features](#additional-features)

---

## Test Cycle No-Auth Flow Overview

The `/agent/test-cycle-no-auth` endpoint runs a complete processing cycle with the following phases:

1. **Phase 1: Collection** - Collects raw data from various sources (Twitter, Facebook, News, YouTube, RSS)
2. **Phase 2: Data Loading** - Loads collected raw data from CSV files into database
3. **Phase 3: Deduplication** - Removes duplicate records
4. **Phase 4: Sentiment Analysis** - Analyzes sentiment, emotions, topics, and generates embeddings
5. **Phase 5: Location Classification** - Classifies location using keyword/pattern matching
6. **Phase 6: Issue Detection** - Detects issues by clustering similar mentions together (automatic)

---

## Parameters Computed for a Single Mention

A **mention** is a single piece of content (tweet, news article, Facebook post, etc.) stored in the `sentiment_data` table.

### Core Fields (from CSV/Collection)

- `entry_id` - Unique identifier
- `title`, `description`, `content`, `text` - Content fields
- `url`, `source_url` - URLs
- `published_date`, `date`, `published_at` - Timestamps
- `source`, `source_name`, `source_type` - Source information
- `platform` - Platform (twitter, facebook, news, youtube, etc.)
- `user_name`, `user_handle`, `user_avatar` - User information (for social media)
- `retweets`, `likes`, `comments` - Engagement metrics
- `direct_reach`, `cumulative_reach`, `domain_reach` - Reach metrics
- `country`, `user_location` - Location fields
- `query` - Search query used to find this mention
- `run_timestamp` - When this mention was collected
- `user_id` - Which user this mention belongs to

### Computed Parameters (Phase 4: Sentiment Analysis)

#### 1. Sentiment Analysis (OpenAI API Call)

**Computed by**: `PresidentialSentimentAnalyzer.analyze()`

- **`sentiment_label`** (String)
  - Values: `"positive"`, `"negative"`, `"neutral"`
  - Determined from presidential strategic perspective
  
- **`sentiment_score`** (Float)
  - Range: `-1.0` to `1.0`
  - `-1.0` = Most negative, `0.0` = Neutral, `1.0` = Most positive
  - POSITIVE: 0.2-1.0, NEGATIVE: -1.0 to -0.2, NEUTRAL: -0.2 to 0.2

- **`sentiment_justification`** (Text)
  - Strategic reasoning explaining the sentiment
  - Includes recommended action
  - No explicit token limit (typically 50-200 words)

#### 2. Topic Classification (No OpenAI - Uses Embeddings)

**Computed by**: `TopicClassifier.classify()`

- **`topics`** (List[Dict])
  - List of up to 5 topics (configurable via `max_topics`)
  - Each topic contains:
    - `topic` (String) - Topic key (e.g., "health_care", "education")
    - `topic_name` (String) - Human-readable name
    - `confidence` (Float) - Combined confidence score (0.0-1.0)
    - `keyword_score` (Float) - Keyword matching score (0.0-1.0)
    - `embedding_score` (Float) - Embedding similarity score (0.0-1.0)

- **`primary_topic_key`** (String)
  - The topic with highest confidence (first in topics list)

- **`primary_topic_name`** (String)
  - Human-readable name of primary topic

**How Topics Are Classified**:
- Uses keyword matching (40% weight) + embedding similarity (60% weight)
- Compares mention embedding to pre-computed topic embeddings
- Requires minimum score threshold (from config)
- Can match multiple topics (up to 5)

#### 3. Embedding Generation (OpenAI API Call)

**Computed by**: `PresidentialSentimentAnalyzer._get_embedding()`

- **`embedding`** (List[Float])
  - Vector of **1536 floating-point numbers**
  - Model: `text-embedding-3-small`
  - Stored in `sentiment_embeddings` table (linked via `entry_id`)
  - Text truncated to 8000 characters before embedding

#### 4. Emotion Detection (HuggingFace Model - No OpenAI)

**Computed by**: `PresidentialSentimentAnalyzer._analyze_emotion()`

- **`emotion_label`** (String)
  - Primary emotion: `"anger"`, `"fear"`, `"trust"`, `"sadness"`, `"joy"`, `"disgust"`, `"neutral"`
  
- **`emotion_score`** (Float)
  - Confidence of primary emotion (0.0-1.0)

- **`emotion_distribution`** (JSONB)
  - All 6 emotions with their scores:
    ```json
    {
      "anger": 0.4,
      "fear": 0.3,
      "trust": 0.1,
      "sadness": 0.1,
      "joy": 0.05,
      "disgust": 0.05
    }
    ```

#### 5. Weight Calculation

**Computed by**: `PresidentialSentimentAnalyzer._calculate_influence_weight()` and `_calculate_confidence_weight()`

- **`influence_weight`** (Float)
  - Range: `1.0` to `5.0`
  - Based on:
    - Source type (news = higher, social = lower)
    - User verified status (verified = higher)
    - Reach metrics (higher reach = higher weight)
  - Default: `1.0`

- **`confidence_weight`** (Float)
  - Range: `0.0` to `1.0`
  - Based on:
    - Sentiment classification confidence
    - Emotion detection confidence
  - Default: `0.5`

#### 6. Location Classification (Phase 5 - No OpenAI)

**Computed by**: Location classifier (keyword/pattern matching)

- **`location_label`** (String)
  - Classified location (e.g., "Lagos", "Abuja", "Kaduna")

- **`location_confidence`** (Float)
  - Confidence of location classification (0.0-1.0)

#### 7. Issue Mapping Fields (Fallback - Not from Issue Detection)

**Note**: These are simple fallbacks. Actual issue detection happens separately.

- **`issue_label`** (String)
  - Generated from primary topic: `topics[0].replace('_', ' ').title()`
  - Example: "health_care" → "Health Care"

- **`issue_slug`** (String)
  - URL-friendly version of issue_label
  - Example: "health-care"

- **`issue_confidence`** (Float)
  - Calculated from text, sentiment, and confidence

- **`issue_keywords`** (JSON)
  - Extracted keywords from text

- **`ministry_hint`** (String)
  - Inferred ministry from topics

### Summary: Mention Parameters

**Database Table**: `sentiment_data`

**Total Computed Fields**:
- Sentiment: 3 fields (label, score, justification)
- Topics: 3 fields (topics list, primary_topic_key, primary_topic_name)
- Embedding: 1 field (1536-dim vector, stored separately)
- Emotion: 3 fields (label, score, distribution)
- Weights: 2 fields (influence_weight, confidence_weight)
- Location: 2 fields (label, confidence)
- Issue mapping: 5 fields (label, slug, confidence, keywords, ministry_hint)

**Total**: ~19 computed fields per mention

---

## Parameters Computed for an Issue

An **issue** is a cluster of related mentions grouped together, stored in the `topic_issues` table.

**Important**: Issue detection **IS NOW AUTOMATIC** during the main cycle (Phase 6).

**What This Means**:
- ✅ **Mentions ARE processed automatically** - Each mention gets sentiment, topics, emotions, etc.
- ✅ **Topics ARE assigned automatically** - Mentions are classified into topics during Phase 4
- ✅ **Issues ARE created automatically** - Issues (clusters of related mentions) are detected during Phase 6
- ⚠️ **The `issue_label` and `issue_slug` fields in `sentiment_data` are fallbacks** - They're generated from topic names, but actual issues are created in Phase 6

**Issue Detection Process** (Phase 6):
- Automatically runs after location classification
- Detects issues for all topics that have mentions
- Clusters similar mentions together using embeddings
- Creates `TopicIssue` records in `topic_issues` table
- Links mentions to issues via `issue_mentions` table
- ✅ **Calculates volume and velocity** (current/previous window, growth rate)
- ✅ **Calculates sentiment aggregations** (distribution, weighted score, sentiment index, emotions)
- ✅ **Extracts metadata** (top keywords, sources, regions)
- ✅ **Generates issue titles** (from mention text)
- Calculates priority scores, lifecycle states

### Core Fields

- **`id`** (UUID) - Unique identifier
- **`issue_slug`** (String) - URL-friendly identifier (globally unique)
- **`issue_label`** (String) - Human-readable label
- **`issue_title`** (String) - Auto-generated summary
- **`topic_key`** (String) - Primary topic this issue belongs to
- **`primary_topic_key`** (String) - Primary topic reference

### Lifecycle Parameters

**Computed by**: `IssueLifecycleManager.update_lifecycle()`

- **`state`** (String)
  - Values: `"emerging"`, `"active"`, `"escalated"`, `"stabilizing"`, `"resolved"`, `"archived"`
  - **State Logic**:
    - `emerging`: New issue (< 3 mentions OR < 24 hours old)
    - `active`: Growing issue (3+ mentions, increasing velocity)
    - `escalated`: High priority (sentiment_index < 30 AND mention_count >= 10 AND velocity > 0)
    - `stabilizing`: Slowing down (velocity < -20% AND mention_count >= 5)
    - `resolved`: No activity for 7+ days
    - `archived`: Manually archived

- **`status`** (String) - Additional status field

- **`start_time`** (DateTime) - When issue was first detected
- **`last_activity`** (DateTime) - Most recent mention timestamp
- **`resolved_at`** (DateTime) - When issue was resolved

### Volume & Velocity Parameters

**Computed by**: `IssueDetectionEngine._calculate_volume_and_velocity()` (Phase 6)

**When Calculated**: 
- When creating new issues from clusters
- When updating existing issues with new mentions

**Implementation Details**:
- **Time Window**: Default 24 hours (configurable via `processing.issue.volume.time_window_hours`)
- **Current Window**: Last 24 hours from now
- **Previous Window**: 24-48 hours ago

- **`mention_count`** (Integer)
  - Total number of mentions linked to this issue
  - Updated when new mentions are added
  - ✅ **IMPLEMENTED**: Incremented when mentions are linked

- **`volume_current_window`** (Integer)
  - Mentions in current time window (last 24 hours)
  - ✅ **IMPLEMENTED**: Counts mentions with timestamps in current window

- **`volume_previous_window`** (Integer)
  - Mentions in previous time window (24-48 hours ago)
  - ✅ **IMPLEMENTED**: Counts mentions with timestamps in previous window

- **`velocity_percent`** (Float)
  - Growth rate: `((current - previous) / previous) * 100`
  - Positive = growing, Negative = declining
  - Special cases:
    - If `previous_window_count = 0` and `current_window_count > 0`: Set to 1000% (infinite growth)
    - If both are 0: Set to 0%
  - ✅ **IMPLEMENTED**: Calculated from volume windows

- **`velocity_score`** (Float)
  - Normalized velocity score (0-100)
  - Conversion formula:
    - `velocity_percent >= 100`: → 100 score
    - `0 <= velocity_percent < 100`: → `50 + (velocity_percent / 100 * 50)`
    - `velocity_percent < 0`: → `max(0, 50 + (velocity_percent / 100 * 50))`
  - ✅ **IMPLEMENTED**: Calculated from velocity_percent

### Sentiment Aggregation Parameters

**Computed by**: `IssueDetectionEngine._update_issue_sentiment_aggregation()` → `SentimentAggregationService.aggregate_by_issue()` (Phase 6)

**When Calculated**: 
- When creating new issues from clusters
- When updating existing issues with new mentions

**Time Window**: 24 hours (default)

- **`sentiment_distribution`** (JSONB)
  - Distribution of sentiment labels:
    ```json
    {
      "positive": 0.3,
      "negative": 0.6,
      "neutral": 0.1
    }
    ```
  - ✅ **IMPLEMENTED**: Calculated from all mentions linked to issue

- **`weighted_sentiment_score`** (Float)
  - Range: `-1.0` to `1.0`
  - Weighted average of mention sentiment scores
  - Formula: `Σ(sentiment_score × influence_weight × confidence_weight) / Σ(influence_weight)`
  - ✅ **IMPLEMENTED**: Calculated by `WeightedSentimentCalculator`

- **`sentiment_index`** (Float)
  - Range: `0` to `100`
  - Converted from weighted_sentiment_score
  - `0` = Most negative, `50` = Neutral, `100` = Most positive
  - Formula: `(weighted_sentiment_score + 1.0) * 50`
  - ✅ **IMPLEMENTED**: Calculated from weighted_sentiment_score

- **`emotion_distribution`** (JSONB)
  - Aggregated emotion distribution from all mentions:
    ```json
    {
      "anger": 0.4,
      "fear": 0.3,
      "trust": 0.1,
      "sadness": 0.1,
      "joy": 0.05,
      "disgust": 0.05
    }
    ```
  - ✅ **IMPLEMENTED**: Aggregated from mention emotion_distribution fields

- **`emotion_adjusted_severity`** (Float)
  - Severity adjusted by emotion distribution
  - Negative emotions (anger, fear, sadness, disgust) increase severity
  - Positive emotions (joy, trust) decrease severity
  - ✅ **IMPLEMENTED**: Calculated by `SentimentAggregationService`

### Priority Parameters

**Computed by**: `IssuePriorityCalculator.calculate_priority()`

- **`priority_score`** (Float)
  - Range: `0` to `100`
  - Weighted combination of:
    - **Sentiment Score** (40% weight): More negative = higher priority
    - **Volume Score** (30% weight): More mentions = higher priority (logarithmic scaling)
    - **Time Score** (20% weight): More recent = higher priority
    - **Velocity Score** (10% weight): Growing faster = higher priority

- **`priority_band`** (String)
  - Values: `"critical"`, `"high"`, `"medium"`, `"low"`
  - Based on priority_score:
    - `critical`: 80-100
    - `high`: 60-79
    - `medium`: 40-59
    - `low`: 0-39

### Clustering Parameters

- **`cluster_centroid_embedding`** (JSONB)
  - Representative embedding vector for the issue cluster
  - Used to match new mentions to existing issues

- **`similarity_threshold`** (Float)
  - Default: `0.75`
  - Minimum cosine similarity to match mentions to this issue

### Metadata Parameters

**Computed by**: `IssueDetectionEngine._update_issue_metadata()` (Phase 6)

**When Calculated**: 
- When creating new issues from clusters
- When updating existing issues with new mentions

- **`top_keywords`** (Array[String])
  - Most frequent keywords from mentions
  - Extracted from mention text/content/title/description
  - Filters out common words (< 3 chars, stop words)
  - Top 10 keywords by frequency
  - ✅ **IMPLEMENTED**: Extracted from all issue mentions

- **`top_sources`** (Array[String])
  - Most frequent sources/platforms
  - Extracted from `source` or `platform` fields
  - Top 5 sources by frequency
  - ✅ **IMPLEMENTED**: Extracted from all issue mentions

- **`regions_impacted`** (Array[String])
  - Regions mentioned in issue
  - Extracted from `location_label` field of mentions
  - All unique regions (up to 10)
  - ✅ **IMPLEMENTED**: Extracted from mention location_label fields

- **`entities_mentioned`** (JSONB)
  - Entities extracted from mentions
  - ⚠️ **NOT YET IMPLEMENTED**: Placeholder for future entity extraction

- **`issue_title`** (String)
  - Auto-generated summary/title for the issue
  - Generated from first mention's text (truncated to 100 chars)
  - ✅ **IMPLEMENTED**: Generated by `_generate_issue_title()`

- **`is_active`** (Boolean) - Whether issue is active
- **`is_archived`** (Boolean) - Whether issue is archived

### Summary: Issue Parameters

**Database Table**: `topic_issues`

**Total Computed Fields**:
- Core: 5 fields
- Lifecycle: 5 fields
- Volume/Velocity: 5 fields
- Sentiment: 5 fields
- Priority: 2 fields
- Clustering: 2 fields
- Metadata: 5+ fields

**Total**: ~29 computed fields per issue

---

## Parameters Computed for a Topic

A **topic** is a predefined category (e.g., "health_care", "education", "security") stored in the `topics` table.

### Core Fields

- **`topic_key`** (String) - Unique identifier (e.g., "health_care")
- **`topic_name`** (String) - Human-readable name
- **`description`** (Text) - Topic description
- **`is_active`** (Boolean) - Whether topic is active
- **`created_at`**, **`updated_at`** - Timestamps

### Aggregated Sentiment Parameters

**Computed by**: `SentimentAggregationService.aggregate_by_topic()`

These are computed **on-demand** or **periodically** for specific time windows:

- **`weighted_sentiment_score`** (Float)
  - Range: `-1.0` to `1.0`
  - Weighted average of all mentions for this topic

- **`sentiment_index`** (Float)
  - Range: `0` to `100`
  - Converted from weighted_sentiment_score

- **`sentiment_distribution`** (JSONB)
  - Distribution: `{positive: 0.3, negative: 0.6, neutral: 0.1}`

- **`emotion_distribution`** (JSONB)
  - Aggregated emotion distribution

- **`emotion_adjusted_severity`** (Float)
  - Severity adjusted by emotions

- **`mention_count`** (Integer)
  - Total mentions for this topic in time window

- **`total_influence_weight`** (Float)
  - Sum of influence weights for all mentions

**Time Windows Available**:
- `15m` - Last 15 minutes
- `1h` - Last 1 hour
- `24h` - Last 24 hours
- `7d` - Last 7 days
- `30d` - Last 30 days

### Baseline Sentiment Parameters

**Computed by**: `TopicSentimentNormalizer.calculate_baseline_for_topic()`

- **`baseline_sentiment_index`** (Float)
  - Historical baseline sentiment index (0-100)
  - Calculated from mentions in lookback period (default: 30 days)
  - Stored in `topic_sentiment_baselines` table

- **`normalized_sentiment_index`** (Float)
  - Deviation from baseline
  - Formula: `50 + (current_index - baseline_index)`
  - Clamped to 0-100

- **`normalized_score`** (Float)
  - Range: `-1.0` to `1.0`
  - Converted from normalized_index

### Topic Classification Parameters (Per Mention)

For each mention classified to a topic, these are stored in `mention_topics` table:

- **`topic_key`** (String) - Topic identifier
- **`mention_id`** (Integer) - Reference to mention
- **`topic_confidence`** (Float) - Classification confidence (0.0-1.0)
- **`keyword_score`** (Float) - Keyword matching score
- **`embedding_score`** (Float) - Embedding similarity score
- **`is_primary`** (Boolean) - Whether this is the primary topic

### Summary: Topic Parameters

**Database Tables**: `topics`, `topic_sentiment_baselines`, `mention_topics`, `sentiment_aggregations`

**Total Computed Fields**:
- Core: 5 fields
- Aggregated sentiment: 7 fields (per time window)
- Baseline: 3 fields
- Classification (per mention): 5 fields

**Total**: ~20 fields per topic (plus per-mention classification data)

---

## User-Specific Filtering

### How It Works

User-specific filtering determines what data is shown to each user based on their **Target Individual Configuration**.

### 1. Target Individual Configuration

**Database Table**: `target_individual_configurations`

**Fields**:
- **`user_id`** (UUID) - User identifier
- **`individual_name`** (String) - Name of target individual (e.g., "Bola Ahmed Tinubu")
- **`query_variations`** (JSON) - Array of search term variations
  - Example: `["Tinubu", "BAT", "President Tinubu", "Bola Tinubu"]`

### 2. Collection Phase Filtering

**Location**: `src/agent/core.py` - `collect_data_parallel()`

During Phase 1 (Collection), the system:
1. Retrieves user's `TargetIndividualConfiguration` from database
2. Uses `individual_name` + `query_variations` as search queries
3. Collects mentions that match these queries
4. All collected mentions are tagged with `user_id`

**Result**: Each user only collects mentions relevant to their target individual.

### 3. API Endpoint Filtering

**Location**: `src/api/service.py` - `apply_target_filtering_to_media_data()`

When API endpoints return data to users, they apply filtering:

```python
def apply_target_filtering_to_media_data(db: Session, all_data: List, user_id: Optional[str], endpoint_name: str) -> List:
    # Get user's target configuration
    target_config = db.query(models.TargetIndividualConfiguration)\
                     .filter(models.TargetIndividualConfiguration.user_id == user_uuid)\
                     .order_by(models.TargetIndividualConfiguration.created_at.desc())\
                     .first()
    
    if target_config:
        # Filter data by target config
        filtered_data = sentiment_cache.filter_by_target_config(all_data, target_config)
        return filtered_data
```

### 4. Filtering Logic

**Location**: `src/api/data_cache.py` - `filter_by_target_config()`

**Algorithm**:
1. Extract search terms: `[individual_name] + query_variations`
2. Split into individual words (minimum 3 characters)
3. For each mention, check if **ANY** search word appears in:
   - `text`
   - `title`
   - `content`
4. If match found, include mention in filtered results

**Example**:
- Target: "Bola Ahmed Tinubu"
- Query variations: `["Tinubu", "BAT", "President Tinubu"]`
- Search words: `{"bola", "ahmed", "tinubu", "bat", "president"}`
- Mention matches if it contains **any** of these words

### 5. User-Specific Data Flow

```
User A (Target: "Bola Ahmed Tinubu")
  ↓
Collection Phase: Collects mentions containing "Tinubu", "BAT", etc.
  ↓
Sentiment Analysis: Analyzes only User A's mentions
  ↓
API Request: Returns only User A's filtered mentions

User B (Target: "Atiku Abubakar")
  ↓
Collection Phase: Collects mentions containing "Atiku", "AA", etc.
  ↓
Sentiment Analysis: Analyzes only User B's mentions
  ↓
API Request: Returns only User B's filtered mentions
```

### 6. Database-Level Filtering

All mentions are stored with `user_id` field:
- `sentiment_data.user_id` - Links mention to user
- Queries can filter by `user_id` to get user-specific data

---

## Configuration Guide

### 1. Setting Up Target Individual Configuration

**Via Database**:
```sql
INSERT INTO target_individual_configurations (user_id, individual_name, query_variations)
VALUES (
  'user-uuid-here',
  'Bola Ahmed Tinubu',
  '["Tinubu", "BAT", "President Tinubu", "Bola Tinubu"]'::jsonb
);
```

**Via API** (if endpoint exists):
```http
POST /api/target-configs
{
  "individual_name": "Bola Ahmed Tinubu",
  "query_variations": ["Tinubu", "BAT", "President Tinubu"]
}
```

### 2. Configuring Topic Classification

**File**: `config/master_topics.json`

**Structure**:
```json
{
  "health_care": {
    "name": "Health Care",
    "keywords": ["hospital", "health", "medical"],
    "keyword_groups": {
      "AND": [],
      "OR": [["hospital", "clinic"], ["health", "medical"]]
    }
  }
}
```

**Parameters**:
- `keyword_weight` (default: 0.4) - Weight for keyword matching
- `embedding_weight` (default: 0.6) - Weight for embedding similarity
- `min_score_threshold` - Minimum combined score to classify
- `max_topics` (default: 5) - Maximum topics per mention

**Location**: `src/processing/topic_classifier.py`

### 3. Configuring Issue Detection

**Note**: Issue detection **IS NOW AUTOMATIC** during Phase 6 of the test cycle.

**Automatic Process**:
- Runs automatically after Phase 5 (Location Classification)
- Detects issues for all topics that have mentions
- No manual intervention required

**Configuration Parameters** (in config):
- `processing.issue_detection.min_cluster_size` (default: 3) - Minimum mentions per cluster
- `processing.issue_detection.similarity_threshold` (default: 0.75) - Minimum similarity to match
- `processing.issue_detection.issue_similarity_threshold` (default: 0.70) - Similarity threshold for matching to existing issues
- `processing.issue_detection.max_issues_per_topic` - Maximum issues per topic

**Manual Override** (if needed):
If you want to manually trigger issue detection for specific topics:

```python
from src.processing.data_processor import DataProcessor

processor = DataProcessor()
# Detect issues for a specific topic
processor.detect_issues_for_topic("health_care")

# Detect issues for all topics
processor.detect_issues_for_all_topics()
```

**What Happens During Issue Detection** (Phase 6):
- Gets all mentions for each topic (from `mention_topics` table)
- Clusters mentions using embeddings (cosine similarity)
- For each cluster:
  - Checks if it matches an existing issue
  - If match: Updates existing issue with new mentions
  - If new: Creates `TopicIssue` record (if cluster size >= 3)
- Links mentions to issues via `issue_mentions` table
- Calculates priority, lifecycle state, sentiment aggregation

**Result**:
- `TopicIssue` records created/updated in `topic_issues` table
- `IssueMention` records linking mentions to issues
- Issues have priority scores, lifecycle states, sentiment aggregations

### 4. Configuring Sentiment Aggregation

**Time Windows**: `15m`, `1h`, `24h`, `7d`, `30d`

**Configuration**:
- `processing.aggregation.min_mentions` (default: 3) - Minimum mentions for aggregation

**Location**: `src/processing/sentiment_aggregation_service.py`

### 5. Configuring Priority Calculation

**Weights** (configurable):
- `processing.priority.sentiment_weight` (default: 0.4)
- `processing.priority.volume_weight` (default: 0.3)
- `processing.priority.time_weight` (default: 0.2)
- `processing.priority.velocity_weight` (default: 0.1)

**Location**: `src/processing/issue_priority_calculator.py`

### 6. Configuring Lifecycle Management

**Thresholds**:
- `processing.lifecycle.emerging_threshold_hours` (default: 24)
- `processing.lifecycle.resolved_threshold_days` (default: 7)

**Location**: `src/processing/issue_lifecycle_manager.py`

---

## Additional Features

### 1. Sentiment Aggregations

**Purpose**: Pre-computed aggregated sentiment metrics for faster queries

**Storage**: `sentiment_aggregations` table

**Aggregation Types**:
- `topic` - Aggregate by topic_key
- `issue` - Aggregate by issue_id
- `entity` - Aggregate by entity_name (future)

**Computed Metrics**:
- Weighted sentiment score
- Sentiment index
- Sentiment distribution
- Emotion distribution
- Emotion-adjusted severity
- Mention count
- Total influence weight

**Time Windows**: `15m`, `1h`, `24h`, `7d`, `30d`

### 2. Topic Sentiment Baselines

**Purpose**: Historical baseline sentiment for normalization

**Storage**: `topic_sentiment_baselines` table

**Computed**:
- Baseline sentiment index (from historical data)
- Lookback period (default: 30 days)

**Usage**: Normalize current sentiment against historical baseline

### 3. Issue-Mention Linking

**Storage**: `issue_mentions` table

**Fields**:
- `issue_id` - Reference to issue
- `mention_id` - Reference to mention
- `similarity_score` - How similar mention is to issue
- `topic_key` - Topic context

**Purpose**: Track which mentions belong to which issues

### 4. Topic-Issue Linking

**Storage**: `topic_issue_links` table

**Fields**:
- `topic_key` - Topic reference
- `issue_id` - Issue reference
- `is_primary` - Whether this is the primary topic

**Purpose**: Many-to-many relationship between topics and issues

### 5. Owner Configurations

**Purpose**: Role-based topic assignments

**Storage**: `owner_configs` table

**Fields**:
- `owner_key` - User identifier
- `owner_name` - User name
- `owner_type` - "president", "minister", "user"
- `topics` - Array of topic keys
- `priority_topics` - Array of priority topic keys

**Usage**: Assign topics to users based on their role (president, minister, etc.)

---

## Summary

### Mention Parameters (19 fields)
- Sentiment (3), Topics (3), Embedding (1), Emotion (3), Weights (2), Location (2), Issue mapping (5)

### Issue Parameters (29 fields)
- Core (5), Lifecycle (5), Volume/Velocity (5), Sentiment (5), Priority (2), Clustering (2), Metadata (5+)

### Topic Parameters (20+ fields)
- Core (5), Aggregated sentiment (7 per time window), Baseline (3), Classification per mention (5)

### User Filtering
- Based on `TargetIndividualConfiguration` (individual_name + query_variations)
- Applied during collection and API responses
- Filters mentions containing any search word from configuration

### Configuration
- Topics: `config/master_topics.json`
- Issue detection: Must be explicitly called (not automatic)
- Aggregation: Time windows and thresholds configurable
- Priority: Weights configurable
- Lifecycle: Thresholds configurable

---

## Database Storage and Frontend Access

### Database Storage Locations

#### Mention Parameters Storage

**Primary Table**: `sentiment_data`

**All computed fields are stored directly in this table**:

```sql
-- Core fields
entry_id (PRIMARY KEY)
user_id (Foreign Key → users.id)
text, title, content, description
url, source_url, source, source_type, platform
published_date, date, published_at, created_at, run_timestamp

-- Sentiment Analysis (Phase 4)
sentiment_label (VARCHAR)
sentiment_score (FLOAT)
sentiment_justification (TEXT)

-- Emotion Detection (Phase 4)
emotion_label (VARCHAR)
emotion_score (FLOAT)
emotion_distribution (JSONB)

-- Weight Calculation (Phase 4)
influence_weight (FLOAT)
confidence_weight (FLOAT)

-- Location Classification (Phase 5)
location_label (VARCHAR)
location_confidence (FLOAT)

-- Issue Mapping (Fallback)
issue_label (VARCHAR)
issue_slug (VARCHAR)
issue_confidence (FLOAT)
issue_keywords (JSON)
ministry_hint (VARCHAR)
```

**Related Tables**:
- `sentiment_embeddings` - Stores embedding vectors (1536-dim)
  - `entry_id` (Foreign Key → sentiment_data.entry_id)
  - `embedding` (JSONB array of floats)

- `mention_topics` - Stores topic classifications (many-to-many)
  - `mention_id` (Foreign Key → sentiment_data.entry_id)
  - `topic_key` (Foreign Key → topics.topic_key)
  - `topic_confidence` (FLOAT)
  - `keyword_score` (FLOAT)
  - `embedding_score` (FLOAT)
  - `is_primary` (BOOLEAN)

#### Issue Parameters Storage

**Primary Table**: `topic_issues`

```sql
-- Core fields
id (UUID PRIMARY KEY)
issue_slug (VARCHAR UNIQUE)
issue_label (VARCHAR)
issue_title (VARCHAR)
topic_key (Foreign Key → topics.topic_key)
primary_topic_key (Foreign Key → topics.topic_key)

-- Lifecycle
state (VARCHAR) -- emerging, active, escalated, stabilizing, resolved, archived
status (VARCHAR)
start_time (TIMESTAMP)
last_activity (TIMESTAMP)
resolved_at (TIMESTAMP)

-- Volume & Velocity
mention_count (INTEGER)
volume_current_window (INTEGER)
volume_previous_window (INTEGER)
velocity_percent (FLOAT)
velocity_score (FLOAT)

-- Sentiment Aggregation
sentiment_distribution (JSONB)
weighted_sentiment_score (FLOAT)
sentiment_index (FLOAT)
emotion_distribution (JSONB)
emotion_adjusted_severity (FLOAT)

-- Priority
priority_score (FLOAT)
priority_band (VARCHAR)

-- Clustering
cluster_centroid_embedding (JSONB)
similarity_threshold (FLOAT)

-- Metadata
top_keywords (TEXT[])
top_sources (TEXT[])
regions_impacted (TEXT[])
entities_mentioned (JSONB)
is_active (BOOLEAN)
is_archived (BOOLEAN)
```

**Related Tables**:
- `issue_mentions` - Links mentions to issues
  - `issue_id` (Foreign Key → topic_issues.id)
  - `mention_id` (Foreign Key → sentiment_data.entry_id)
  - `similarity_score` (FLOAT)
  - `topic_key` (VARCHAR)

- `topic_issue_links` - Links topics to issues (many-to-many)
  - `topic_key` (Foreign Key → topics.topic_key)
  - `issue_id` (Foreign Key → topic_issues.id)
  - `is_primary` (BOOLEAN)

#### Topic Parameters Storage

**Primary Table**: `topics`

```sql
topic_key (VARCHAR PRIMARY KEY)
topic_name (VARCHAR)
description (TEXT)
is_active (BOOLEAN)
created_at, updated_at (TIMESTAMP)
```

**Related Tables**:
- `topic_sentiment_baselines` - Historical baselines
  - `topic_key` (Foreign Key → topics.topic_key PRIMARY KEY)
  - `baseline_sentiment_index` (FLOAT)
  - `lookback_days` (INTEGER)
  - `calculated_at` (TIMESTAMP)

- `sentiment_aggregations` - Pre-computed aggregations
  - `aggregation_type` (VARCHAR) -- 'topic', 'issue', 'entity'
  - `aggregation_key` (VARCHAR) -- topic_key, issue_id, or entity_name
  - `time_window` (VARCHAR) -- '15m', '1h', '24h', '7d', '30d'
  - `weighted_sentiment_score` (FLOAT)
  - `sentiment_index` (FLOAT)
  - `sentiment_distribution` (JSONB)
  - `emotion_distribution` (JSONB)
  - `emotion_adjusted_severity` (FLOAT)
  - `mention_count` (INTEGER)
  - `total_influence_weight` (FLOAT)
  - `calculated_at` (TIMESTAMP)

- `mention_topics` - Topic classifications per mention (see above)

---

### API Endpoints for Frontend Access

#### Current Endpoints (Presidential Service)

**Base URL**: `/presidential`

**Available Endpoints**:

1. **Get Presidential Report**
   ```
   GET /presidential/report
   ```
   - Returns comprehensive report with mentions, sentiment, topics
   - Requires authentication (user_id from JWT token)
   - Applies user-specific filtering automatically

2. **Get Presidential Metrics**
   ```
   GET /presidential/metrics
   ```
   - Returns key metrics and KPIs
   - Requires authentication
   - User-specific data

3. **Get Analysis for Specific Records**
   ```
   POST /presidential/analyze-records
   Body: [1, 2, 3, ...]  # Array of entry_ids
   ```
   - Returns analysis for specific mention IDs
   - No authentication required (for testing)

#### Recommended Endpoints (To Be Implemented)

Based on the architecture documentation, these endpoints should be created:

**Mentions Endpoints**:
```
GET  /api/v1/mentions                    # List mentions (with filters)
GET  /api/v1/mentions/:id                # Get single mention
GET  /api/v1/mentions/:id/topics         # Get topics for mention
GET  /api/v1/mentions/:id/embedding      # Get embedding vector
```

**Issues Endpoints**:
```
GET    /api/v1/issues                    # List issues (with filters)
GET    /api/v1/issues/:id                # Get issue detail
GET    /api/v1/issues/:id/mentions       # Get mentions for issue
GET    /api/v1/issues/:id/sentiment      # Get sentiment aggregation
POST   /api/v1/issues/:id/merge          # Merge issues
POST   /api/v1/issues/:id/archive        # Archive issue
```

**Topics Endpoints**:
```
GET  /api/v1/topics                      # List all topics
GET  /api/v1/topics/:key                 # Get topic detail
GET  /api/v1/topics/:key/mentions        # Get mentions for topic
GET  /api/v1/topics/:key/sentiment       # Get sentiment aggregation
GET  /api/v1/topics/:key/baseline        # Get sentiment baseline
```

**Sentiment Endpoints**:
```
GET  /api/v1/sentiment/national          # National sentiment
GET  /api/v1/sentiment/topic/:key        # Topic sentiment
GET  /api/v1/sentiment/issue/:id         # Issue sentiment
GET  /api/v1/sentiment/trends            # Sentiment trends over time
```

**Dashboard Endpoints**:
```
GET  /api/v1/dashboard/national          # National dashboard
GET  /api/v1/dashboard/ministry/:id       # Ministry dashboard
GET  /api/v1/dashboard/analyst            # Analyst dashboard
```

---

### Frontend Access Patterns

#### 1. Accessing Mention Data

**Backend Query** (Python/SQLAlchemy):
```python
from api.models import SentimentData, MentionTopic
from sqlalchemy.orm import joinedload

# Get mentions with topics
mentions = db.query(SentimentData)\
    .options(joinedload(SentimentData.embedding))\
    .filter(SentimentData.user_id == user_id)\
    .order_by(desc(SentimentData.created_at))\
    .limit(100)\
    .all()

# Get topics for each mention
for mention in mentions:
    topics = db.query(MentionTopic)\
        .filter(MentionTopic.mention_id == mention.entry_id)\
        .all()
    mention.topics = topics
```

**Frontend API Call** (TypeScript):
```typescript
// Using Axios
const response = await apiClient.get('/api/v1/mentions', {
  params: {
    user_id: currentUser.id,
    limit: 100,
    sort: 'created_at',
    order: 'desc'
  }
});

// Response structure
interface Mention {
  entry_id: number;
  text: string;
  title: string;
  url: string;
  sentiment_label: 'positive' | 'negative' | 'neutral';
  sentiment_score: number;
  sentiment_justification: string;
  emotion_label: string;
  emotion_score: number;
  emotion_distribution: {
    anger: number;
    fear: number;
    trust: number;
    sadness: number;
    joy: number;
    disgust: number;
  };
  influence_weight: number;
  confidence_weight: number;
  location_label: string;
  location_confidence: number;
  topics: Array<{
    topic_key: string;
    topic_name: string;
    confidence: number;
    keyword_score: number;
    embedding_score: number;
    is_primary: boolean;
  }>;
  embedding?: number[]; // 1536-dim vector (optional)
}
```

**React Component Example**:
```typescript
import { useState, useEffect } from 'react';
import apiClient from '@/lib/api-client';

const MentionsList = () => {
  const [mentions, setMentions] = useState<Mention[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMentions = async () => {
      try {
        const response = await apiClient.get('/api/v1/mentions', {
          params: { limit: 50 }
        });
        setMentions(response.data);
      } catch (error) {
        console.error('Failed to fetch mentions:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchMentions();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {mentions.map(mention => (
        <div key={mention.entry_id} className="mention-card">
          <h3>{mention.title}</h3>
          <p>{mention.text}</p>
          <div className="sentiment">
            <span className={`badge ${mention.sentiment_label}`}>
              {mention.sentiment_label}
            </span>
            <span>Score: {mention.sentiment_score.toFixed(2)}</span>
          </div>
          <div className="topics">
            {mention.topics.map(topic => (
              <span key={topic.topic_key} className="topic-tag">
                {topic.topic_name} ({topic.confidence.toFixed(2)})
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
```

#### 2. Accessing Issue Data

**Backend Query**:
```python
from api.models import TopicIssue, IssueMention, SentimentData

# Get issues with aggregated data
issues = db.query(TopicIssue)\
    .filter(
        TopicIssue.is_active == True,
        TopicIssue.user_id == user_id  # If user-specific
    )\
    .order_by(desc(TopicIssue.priority_score))\
    .limit(20)\
    .all()

# Get mentions for an issue
issue_id = issues[0].id
mentions = db.query(SentimentData)\
    .join(IssueMention, SentimentData.entry_id == IssueMention.mention_id)\
    .filter(IssueMention.issue_id == issue_id)\
    .all()
```

**Frontend API Call**:
```typescript
// Get issues
const issuesResponse = await apiClient.get('/api/v1/issues', {
  params: {
    priority: 'critical',
    state: 'active',
    limit: 20
  }
});

// Get mentions for a specific issue
const mentionsResponse = await apiClient.get(
  `/api/v1/issues/${issueId}/mentions`,
  { params: { limit: 50 } }
);

// Response structure
interface Issue {
  id: string;
  issue_slug: string;
  issue_label: string;
  issue_title: string;
  topic_key: string;
  state: 'emerging' | 'active' | 'escalated' | 'stabilizing' | 'resolved' | 'archived';
  mention_count: number;
  velocity_percent: number;
  weighted_sentiment_score: number;
  sentiment_index: number;
  sentiment_distribution: {
    positive: number;
    negative: number;
    neutral: number;
  };
  emotion_distribution: {
    anger: number;
    fear: number;
    trust: number;
    sadness: number;
    joy: number;
    disgust: number;
  };
  priority_score: number;
  priority_band: 'critical' | 'high' | 'medium' | 'low';
  start_time: string;
  last_activity: string;
}
```

**React Component Example**:
```typescript
const IssuesDashboard = () => {
  const [issues, setIssues] = useState<Issue[]>([]);

  useEffect(() => {
    apiClient.get('/api/v1/issues', {
      params: { priority: 'critical', limit: 10 }
    }).then(response => setIssues(response.data));
  }, []);

  return (
    <div className="issues-grid">
      {issues.map(issue => (
        <IssueCard key={issue.id} issue={issue}>
          <h3>{issue.issue_label}</h3>
          <div className="metrics">
            <span>Priority: {issue.priority_band}</span>
            <span>Mentions: {issue.mention_count}</span>
            <span>Sentiment: {issue.sentiment_index.toFixed(1)}</span>
          </div>
          <div className="state-badge">{issue.state}</div>
        </IssueCard>
      ))}
    </div>
  );
};
```

#### 3. Accessing Topic Data

**Backend Query**:
```python
from api.models import Topic, SentimentAggregation, TopicSentimentBaseline

# Get topic with aggregation
topic_key = "health_care"
topic = db.query(Topic).filter(Topic.topic_key == topic_key).first()

# Get sentiment aggregation for time window
aggregation = db.query(SentimentAggregation)\
    .filter(
        SentimentAggregation.aggregation_type == 'topic',
        SentimentAggregation.aggregation_key == topic_key,
        SentimentAggregation.time_window == '24h'
    )\
    .first()

# Get baseline
baseline = db.query(TopicSentimentBaseline)\
    .filter(TopicSentimentBaseline.topic_key == topic_key)\
    .first()
```

**Frontend API Call**:
```typescript
// Get topic detail with sentiment
const topicResponse = await apiClient.get(`/api/v1/topics/${topicKey}`, {
  params: { time_window: '24h' }
});

// Get topic mentions
const mentionsResponse = await apiClient.get(
  `/api/v1/topics/${topicKey}/mentions`,
  { params: { limit: 100 } }
);

// Response structure
interface Topic {
  topic_key: string;
  topic_name: string;
  description: string;
  is_active: boolean;
  sentiment?: {
    weighted_sentiment_score: number;
    sentiment_index: number;
    sentiment_distribution: {
      positive: number;
      negative: number;
      neutral: number;
    };
    emotion_distribution: Record<string, number>;
    mention_count: number;
    time_window: string;
  };
  baseline?: {
    baseline_sentiment_index: number;
    lookback_days: number;
  };
}
```

#### 4. Accessing Aggregated Sentiment Data

**Backend Query**:
```python
from api.processing.sentiment_aggregation_service import SentimentAggregationService

service = SentimentAggregationService()

# Aggregate by topic
topic_aggregation = service.aggregate_by_topic(
    topic_key="health_care",
    time_window="24h"
)

# Aggregate by issue
issue_aggregation = service.aggregate_by_issue(
    issue_id=issue_id,
    time_window="7d"
)
```

**Frontend API Call**:
```typescript
// Get national sentiment
const nationalSentiment = await apiClient.get('/api/v1/sentiment/national', {
  params: { time_window: '7d' }
});

// Get topic sentiment
const topicSentiment = await apiClient.get(
  `/api/v1/sentiment/topic/${topicKey}`,
  { params: { time_window: '24h' } }
);

// Get issue sentiment
const issueSentiment = await apiClient.get(
  `/api/v1/sentiment/issue/${issueId}`,
  { params: { time_window: '7d' } }
);
```

---

### Database Query Examples

#### Example 1: Get User's Mentions with All Computed Parameters

```sql
-- Get mentions with sentiment, emotion, topics
SELECT 
    sd.entry_id,
    sd.text,
    sd.title,
    sd.sentiment_label,
    sd.sentiment_score,
    sd.sentiment_justification,
    sd.emotion_label,
    sd.emotion_score,
    sd.emotion_distribution,
    sd.influence_weight,
    sd.confidence_weight,
    sd.location_label,
    sd.location_confidence,
    sd.issue_label,
    sd.issue_slug,
    sd.ministry_hint,
    -- Get topics via join
    json_agg(
        json_build_object(
            'topic_key', mt.topic_key,
            'confidence', mt.topic_confidence,
            'is_primary', mt.is_primary
        )
    ) as topics
FROM sentiment_data sd
LEFT JOIN mention_topics mt ON sd.entry_id = mt.mention_id
WHERE sd.user_id = :user_id
GROUP BY sd.entry_id
ORDER BY sd.created_at DESC
LIMIT 100;
```

#### Example 2: Get Issues with Aggregated Metrics

```sql
-- Get active issues with priority
SELECT 
    ti.id,
    ti.issue_slug,
    ti.issue_label,
    ti.state,
    ti.priority_score,
    ti.priority_band,
    ti.mention_count,
    ti.velocity_percent,
    ti.weighted_sentiment_score,
    ti.sentiment_index,
    ti.sentiment_distribution,
    ti.emotion_distribution,
    ti.start_time,
    ti.last_activity,
    t.topic_name
FROM topic_issues ti
JOIN topics t ON ti.topic_key = t.topic_key
WHERE ti.is_active = TRUE
  AND ti.is_archived = FALSE
ORDER BY ti.priority_score DESC
LIMIT 20;
```

#### Example 3: Get Topic Aggregation

```sql
-- Get topic sentiment aggregation
SELECT 
    sa.aggregation_key as topic_key,
    sa.time_window,
    sa.weighted_sentiment_score,
    sa.sentiment_index,
    sa.sentiment_distribution,
    sa.emotion_distribution,
    sa.mention_count,
    sa.calculated_at
FROM sentiment_aggregations sa
WHERE sa.aggregation_type = 'topic'
  AND sa.aggregation_key = :topic_key
  AND sa.time_window = :time_window
ORDER BY sa.calculated_at DESC
LIMIT 1;
```

---

### Frontend Integration Best Practices

#### 1. Use React Query / RTK Query for Caching

```typescript
import { useQuery } from '@tanstack/react-query';

const useMentions = (filters: MentionFilters) => {
  return useQuery({
    queryKey: ['mentions', filters],
    queryFn: () => apiClient.get('/api/v1/mentions', { params: filters }),
    staleTime: 30000, // 30 seconds
    cacheTime: 300000, // 5 minutes
  });
};

// Usage in component
const { data: mentions, isLoading } = useMentions({ limit: 50 });
```

#### 2. Implement Pagination

```typescript
const usePaginatedMentions = (page: number, pageSize: number) => {
  return useQuery({
    queryKey: ['mentions', 'paginated', page, pageSize],
    queryFn: () => apiClient.get('/api/v1/mentions', {
      params: {
        page,
        limit: pageSize,
        offset: (page - 1) * pageSize
      }
    }),
  });
};
```

#### 3. Handle User-Specific Filtering

```typescript
// The backend automatically applies user filtering based on JWT token
// Frontend just needs to include the token in requests

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

#### 4. Real-time Updates (WebSocket / Polling)

```typescript
// Poll for new mentions every 30 seconds
useEffect(() => {
  const interval = setInterval(() => {
    refetch(); // React Query refetch
  }, 30000);
  return () => clearInterval(interval);
}, []);
```

---

## Related Documentation

- [TEST_CYCLE_NO_AUTH_FLOW.md](./TEST_CYCLE_NO_AUTH_FLOW.md) - Complete flow documentation
- [OPENAI_API_CALLS.md](./OPENAI_API_CALLS.md) - OpenAI API call details
- [BACKEND_ARCHITECTURE.md](../BACKEND_ARCHITECTURE.md) - System architecture
- [FRONTEND_DATABASE_QUERY_ARCHITECTURE.md](./FRONTEND_DATABASE_QUERY_ARCHITECTURE.md) - API endpoint structure
- [USERS_AND_OWNER_CONFIGS_RELATIONSHIP.md](./USERS_AND_OWNER_CONFIGS_RELATIONSHIP.md) - User configuration details
