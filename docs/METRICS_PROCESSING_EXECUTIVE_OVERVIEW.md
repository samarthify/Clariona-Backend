# Executive Overview: Metrics Processing in Main Cycle

**Created**: 2025-01-27  
**Purpose**: Complete executive overview of how metrics are calculated and processed during each main cycle execution

---

## 📋 High-Level Flow

The main cycle processes metrics in **6 sequential phases**, transforming raw data into actionable insights:

```
1. DATA COLLECTION → 2. DATA LOADING → 3. DEDUPLICATION → 
4. SENTIMENT ANALYSIS → 5. LOCATION CLASSIFICATION → 6. ISSUE DETECTION & METRICS
```

**Entry Point**: `run_cycles.sh` → `POST /agent/test-cycle-no-auth` → `agent.run_single_cycle_parallel(user_id)`

---

## 🔄 Phase-by-Phase Metrics Processing

### **PHASE 1: Data Collection** (`collect_data_parallel`)

**Purpose**: Collect raw data from multiple sources

**What Happens**:
- Executes collectors in parallel (Twitter, Facebook, Instagram, TikTok, News, YouTube, RSS, Radio)
- Each collector saves raw CSV files to `data/raw/` directory
- No metrics calculated yet - only raw data collection

**Output**: CSV files with raw mention data

---

### **PHASE 2: Data Loading** (`_push_raw_data_to_db`)

**Purpose**: Load raw CSV files into memory

**What Happens**:
- Scans `data/raw/` for CSV files
- Loads all files into pandas DataFrames
- Converts to in-memory record dictionaries
- Stores in `self._temp_raw_records`

**Output**: In-memory list of raw records (no metrics yet)

---

### **PHASE 3: Deduplication** (`_run_deduplication`)

**Purpose**: Remove duplicates before processing

**What Happens**:
- Uses `DeduplicationService` to compare records by URL, text similarity, published date
- Filters out duplicate records
- Inserts unique records into `sentiment_data` table

**Metrics Calculated**: None (only deduplication stats for logging)

**Database Write**: 
- Table: `sentiment_data` (raw records inserted)

---

### **PHASE 4: Sentiment & Topic Analysis** (`_run_sentiment_batch_update_parallel`)

**Purpose**: Analyze sentiment, emotions, topics, and generate embeddings

**What Happens**:
1. Queries database for records without sentiment analysis (`sentiment_label IS NULL`)
2. Processes in parallel batches using `DataProcessor.batch_get_sentiment()`
3. For each mention, calculates:

**Mention-Level Metrics** (stored in `sentiment_data` table):

| Metric | Description | Calculation Method |
|--------|-------------|-------------------|
| `sentiment_label` | positive/negative/neutral | `PresidentialSentimentAnalyzer` (OpenAI) |
| `sentiment_score` | 0.0-1.0 confidence | From sentiment analysis |
| `sentiment_justification` | Text explanation | From sentiment analysis |
| `emotion_label` | Primary emotion (anger/fear/trust/sadness/joy/disgust) | HuggingFace emotion model |
| `emotion_score` | Emotion confidence (0.0-1.0) | From emotion detection |
| `emotion_distribution` | Full emotion distribution (JSON) | All 6 emotions with probabilities |
| `influence_weight` | 1.0-5.0 based on source type/reach | Formula: source_type + verification + reach factors |
| `confidence_weight` | 0.0-1.0 based on sentiment/emotion confidence | Formula: sentiment_confidence × emotion_confidence |
| `topics[]` | Multiple topic classifications | `TopicClassifier` (embedding-based) |
| `embedding` | 1536-dim vector | OpenAI `text-embedding-3-small` |

**Database Updates**:
- `sentiment_data` table: Updates all sentiment, emotion, and weight fields
- `mention_topics` table: Creates records linking mentions to topics (many-to-many)
- `sentiment_embeddings` table: Stores embedding vectors (linked by `entry_id`)

**Output**: Mentions enriched with sentiment, emotions, topics, and embeddings

---

### **PHASE 5: Location Classification** (`_run_location_batch_update_parallel`)

**Purpose**: Classify geographic location of mentions

**What Happens**:
1. Queries records without location (`location_label IS NULL`)
2. Processes in parallel batches
3. Uses simple location classifier (text analysis)

**Mention-Level Metrics** (stored in `sentiment_data` table):

| Metric | Description |
|--------|-------------|
| `location_label` | Geographic location (e.g., "Lagos", "Abuja", "Kano") |
| `location_confidence` | Confidence score (0.0-1.0) |

**Database Updates**:
- `sentiment_data` table: Updates `location_label` and `location_confidence`

**Output**: Mentions enriched with location data

---

### **PHASE 6: Issue Detection & Metrics Aggregation** (`_run_issue_detection`)

**Purpose**: Detect issues, aggregate metrics, calculate priority and lifecycle

**This is where ALL issue-level metrics are calculated.**

**What Happens**:

#### Step 1: Issue Detection (`IssueDetectionEngine.detect_issues_for_all_topics()`)

1. **Clustering**: Groups mentions by topic using embedding similarity
2. **Issue Matching**: Matches clusters to existing issues or creates new ones
3. **Mention Linking**: Links mentions to issues via `issue_mentions` table

#### Step 2: Metrics Calculation (for each issue)

When an issue is created or updated, the following metrics are calculated:

---

## 📊 Complete Metrics Breakdown

### **A. Volume & Velocity Metrics**

**Calculated By**: `IssueDetectionEngine._calculate_volume_and_velocity()`

**When**: Every time an issue is created or updated with new mentions

**Time Window**: 24 hours (configurable via `processing.issue.volume.time_window_hours`)

| Metric | Description | Calculation |
|--------|-------------|-------------|
| `mention_count` | Total mentions linked to issue | Count of `issue_mentions` records |
| `volume_current_window` | Mentions in last 24 hours | Count mentions where `published_at` is within last 24h |
| `volume_previous_window` | Mentions 24-48 hours ago | Count mentions where `published_at` is 24-48h ago |
| `velocity_percent` | Growth rate percentage | `((current - previous) / previous) × 100`<br>Special: If previous=0 and current>0 → 1000% |
| `velocity_score` | Normalized velocity (0-100) | `velocity_percent >= 100` → 100<br>`0 ≤ velocity_percent < 100` → `50 + (velocity_percent / 100 × 50)`<br>`velocity_percent < 0` → `max(0, 50 + (velocity_percent / 100 × 50))` |

**Database Field**: `topic_issues` table

---

### **B. Sentiment Aggregation Metrics**

**Calculated By**: `SentimentAggregationService.aggregate_by_issue()` → `IssueDetectionEngine._update_issue_sentiment_aggregation()`

**When**: Every time an issue is created or updated with new mentions

**Time Window**: 24 hours (default)

**Process**:
1. Retrieves all mentions linked to issue within time window
2. Calculates weighted sentiment using `WeightedSentimentCalculator`
3. Aggregates sentiment distribution, emotions, and severity

| Metric | Description | Calculation |
|--------|-------------|-------------|
| `sentiment_distribution` | Distribution of sentiment labels | `{positive: 0.3, negative: 0.6, neutral: 0.1}` |
| `weighted_sentiment_score` | Weighted average sentiment (-1.0 to 1.0) | Weighted by `influence_weight` and `confidence_weight` |
| `sentiment_index` | Converted sentiment score (0-100) | `(weighted_sentiment_score + 1.0) / 2.0 × 100`<br>0 = most negative, 100 = most positive |
| `emotion_distribution` | Aggregated emotion distribution | `{anger: 0.4, fear: 0.3, trust: 0.1, ...}` |
| `emotion_adjusted_severity` | Severity adjusted by emotions | Formula considers negative emotions (anger, fear) |

**Database Fields**: `topic_issues` table

**Also Stored**: `sentiment_aggregations` table (for historical tracking)

---

### **C. Metadata Metrics**

**Calculated By**: `IssueDetectionEngine._update_issue_metadata()`

**When**: Every time an issue is created or updated with new mentions

| Metric | Description | Calculation |
|--------|-------------|-------------|
| `top_keywords` | Top 10 most frequent keywords | Extract from mention texts, filter common words, count frequency |
| `top_sources` | Top 5 most frequent sources/platforms | Count occurrences of `source` or `platform` fields |
| `regions_impacted` | Unique regions (up to 10) | Extract from `location_label` fields, deduplicate |

**Database Fields**: `topic_issues` table (JSONB arrays)

---

### **D. Priority Metrics**

**Calculated By**: `IssuePriorityCalculator.calculate_priority()`

**When**: Every time an issue is created or updated with new mentions

**Formula**: Weighted combination of 4 factors

```
priority_score = (
    sentiment_weight × sentiment_score +
    volume_weight × volume_score +
    time_weight × time_score +
    velocity_weight × velocity_score
)
```

**Default Weights** (configurable):
- `sentiment_weight`: 0.4 (40%)
- `volume_weight`: 0.3 (30%)
- `time_weight`: 0.2 (20%)
- `velocity_weight`: 0.1 (10%)

**Component Scores** (each normalized to 0-100):

| Component | Calculation |
|-----------|-------------|
| `sentiment_score` | `100 - sentiment_index` (more negative = higher priority) |
| `volume_score` | Logarithmic: `100 × (1 - e^(-mention_count/20))` |
| `time_score` | Recency-based: 0h → 100, 24h → 70, 7d → 30, 30d → 10, 90d+ → 0 |
| `velocity_score` | Same as `velocity_score` metric (0-100) |

**Priority Bands**:
- `priority_score ≥ 80` → `priority_band = 'critical'`
- `priority_score ≥ 60` → `priority_band = 'high'`
- `priority_score ≥ 40` → `priority_band = 'medium'`
- `priority_score < 40` → `priority_band = 'low'`

**Database Fields**: `topic_issues.priority_score`, `topic_issues.priority_band`

---

### **E. Lifecycle State Metrics**

**Calculated By**: `IssueLifecycleManager.calculate_state()`

**When**: Every time an issue is created or updated with new mentions

**States** (in priority order):

| State | Conditions |
|-------|------------|
| `archived` | Manually archived (never auto-changed) |
| `resolved` | No activity for 7+ days (configurable: `resolved_threshold_days`) |
| `emerging` | Age < 24 hours OR mention_count < 3 |
| `escalated` | sentiment_index < 30 AND mention_count ≥ 10 AND velocity > 0 |
| `stabilizing` | velocity < -20% AND mention_count ≥ 5 |
| `active` | mention_count ≥ 3 AND velocity ≥ 0 (default growing issue) |

**Database Fields**: `topic_issues.state`, `topic_issues.state_reason`

---

### **F. Issue Title Generation**

**Calculated By**: `IssueDetectionEngine._generate_issue_title()`

**When**: When creating new issues (if `issue_title` is not set)

**Process**: Extracts representative text from mention texts to generate a summary title

**Database Field**: `topic_issues.issue_title`

---

## 🔄 Recalculation Logic

### **New Issues**
When a new issue is created from a cluster:
1. ✅ Volume & Velocity calculated
2. ✅ Sentiment Aggregation calculated
3. ✅ Metadata extracted
4. ✅ Priority calculated
5. ✅ Lifecycle state determined
6. ✅ Issue title generated

### **Existing Issues**
When an existing issue is updated with new mentions:
1. ✅ Volume & Velocity **recalculated** (all mentions, not just new ones)
2. ✅ Sentiment Aggregation **recalculated** (all mentions in time window)
3. ✅ Metadata **recalculated** (all mentions)
4. ✅ Priority **recalculated** (uses latest metrics)
5. ✅ Lifecycle state **recalculated** (uses latest metrics)

### **Full Recalculation Mode**
When `recalculate_existing=True` (e.g., `use_existing_data=true`):
- All existing issues are **fully recalculated** even if no new mentions
- Ensures all metrics are up-to-date with latest data

---

## 📈 Data Flow Summary

```
Raw Data (CSV)
    ↓
sentiment_data table (mentions)
    ↓
Phase 4: Sentiment Analysis
    ├─→ sentiment_data (updated with sentiment/emotions/weights)
    ├─→ mention_topics (topic classifications)
    └─→ sentiment_embeddings (embedding vectors)
    ↓
Phase 5: Location Classification
    └─→ sentiment_data (updated with location)
    ↓
Phase 6: Issue Detection
    ├─→ Clustering & Matching
    ├─→ issue_mentions (links mentions to issues)
    └─→ topic_issues (issues with ALL metrics)
        ├─→ Volume & Velocity
        ├─→ Sentiment Aggregation
        ├─→ Metadata
        ├─→ Priority
        └─→ Lifecycle State
```

---

## 🎯 Key Points for Executives

1. **Metrics are calculated incrementally**: Each phase builds on the previous one
2. **Issue-level metrics are comprehensive**: Volume, velocity, sentiment, priority, and lifecycle all calculated automatically
3. **Recalculation ensures accuracy**: Existing issues are recalculated when new mentions are added
4. **Time windows are configurable**: Default 24 hours, but adjustable via config
5. **Priority is multi-factor**: Combines sentiment, volume, recency, and growth rate
6. **Lifecycle is automatic**: Issues transition between states based on metrics
7. **All metrics stored in database**: Available for frontend queries and reporting

---

## 📝 Configuration

Metrics calculation can be configured via `config/llm_config.json`:

```json
{
  "processing": {
    "issue": {
      "volume": {
        "time_window_hours": 24
      },
      "priority": {
        "sentiment_weight": 0.4,
        "volume_weight": 0.3,
        "time_weight": 0.2,
        "velocity_weight": 0.1
      }
    },
    "aggregation": {
      "min_mentions": 3
    }
  }
}
```

---

## 🔍 Database Tables Involved

| Table | Purpose | Metrics Stored |
|-------|---------|----------------|
| `sentiment_data` | Individual mentions | sentiment, emotions, weights, location |
| `mention_topics` | Topic classifications | Links mentions to topics |
| `sentiment_embeddings` | Embedding vectors | 1536-dim vectors for clustering |
| `topic_issues` | Issues | **ALL issue-level metrics** |
| `issue_mentions` | Issue-mention links | Links mentions to issues |
| `sentiment_aggregations` | Historical aggregations | Sentiment aggregation snapshots |
| `topic_issue_links` | Topic-issue links | Links topics to issues |

---

**End of Executive Overview**
