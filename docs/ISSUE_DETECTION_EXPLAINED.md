# Issue Detection: Automatic vs Manual

## Quick Answer

**"Issues are not generated automatically"** means:

- ✅ **Mentions ARE processed automatically** during the test cycle
- ✅ **Topics ARE assigned automatically** during the test cycle  
- ❌ **Issues are NOT created automatically** - you must run issue detection separately

---

## What Happens Automatically (During Test Cycle)

When you run `/agent/test-cycle-no-auth`, these things happen **automatically**:

```
Phase 1: Collection
  ↓
Phase 2: Data Loading
  ↓
Phase 3: Deduplication
  ↓
Phase 4: Sentiment Analysis
  ├─ Sentiment: ✅ Computed automatically
  ├─ Topics: ✅ Assigned automatically
  ├─ Emotions: ✅ Detected automatically
  ├─ Embeddings: ✅ Generated automatically
  └─ Issues: ❌ NOT created automatically
  ↓
Phase 5: Location Classification
```

### What You Get After Automatic Processing

**For Each Mention** (`sentiment_data` table):
- ✅ `sentiment_label`, `sentiment_score`, `sentiment_justification`
- ✅ `emotion_label`, `emotion_score`, `emotion_distribution`
- ✅ `influence_weight`, `confidence_weight`
- ✅ `location_label`, `location_confidence`
- ✅ `issue_label`, `issue_slug` ⚠️ **BUT these are just fallbacks!**

**For Each Mention-Topic Link** (`mention_topics` table):
- ✅ `topic_key` - Which topics this mention belongs to
- ✅ `topic_confidence` - How confident the classification is
- ✅ `keyword_score`, `embedding_score`

**What You DON'T Get**:
- ❌ No `TopicIssue` records in `topic_issues` table
- ❌ No `IssueMention` records linking mentions to issues
- ❌ No issue priority scores, lifecycle states, or aggregations

---

## What Are "Issues" vs "Topics"?

### Topics (Automatic)
- **What**: Predefined categories (e.g., "health_care", "education", "security")
- **When**: Assigned automatically during Phase 4
- **How**: Keyword matching + embedding similarity
- **Example**: A mention about "hospital funding" gets topic "health_care"

### Issues (Manual)
- **What**: Clusters of related mentions that form a specific problem/event
- **When**: Created manually via issue detection
- **How**: Clustering similar mentions together using embeddings
- **Example**: Multiple mentions about "Lagos General Hospital power outage" cluster into one issue

**Analogy**:
- **Topic** = "Health Care" (broad category)
- **Issue** = "Lagos Hospital Power Outage Crisis" (specific problem)

---

## The Confusion: `issue_label` Field

**Important**: The `issue_label` and `issue_slug` fields in `sentiment_data` table are **NOT real issues**!

They are **simple fallbacks** generated from topic names:

```python
# This happens automatically in Phase 4
issue_label = topics[0].replace('_', ' ').title()
# Example: "health_care" → "Health Care"
```

**These are NOT actual issues** because:
- They don't cluster related mentions together
- They don't have priority scores or lifecycle states
- They don't aggregate sentiment across multiple mentions
- They're just topic names formatted differently

**Real issues** are in the `topic_issues` table and are created by the `IssueDetectionEngine`.

---

## How to Actually Create Issues

### Step 1: Run the Main Cycle (Automatic)

```bash
POST /agent/test-cycle-no-auth
```

This processes mentions and assigns topics, but **does NOT create issues**.

### Step 2: Run Issue Detection (Manual)

**Option A: Python Script**

```python
from src.processing.data_processor import DataProcessor

processor = DataProcessor()

# Detect issues for one topic
issues = processor.detect_issues_for_topic("health_care")
print(f"Created/updated {len(issues)} issues")

# OR detect issues for all topics
all_issues = processor.detect_issues_for_all_topics()
```

**Option B: Create API Endpoint** (recommended)

```python
@app.post("/api/v1/issues/detect")
async def detect_issues(
    topic_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    processor = DataProcessor()
    
    if topic_key:
        issues = processor.detect_issues_for_topic(topic_key)
    else:
        all_issues = processor.detect_issues_for_all_topics()
        issues = [i for issues_list in all_issues.values() for i in issues_list]
    
    return {"detected": len(issues), "issues": issues}
```

### Step 3: What Happens During Issue Detection

```
1. Get mentions for topic (from mention_topics table)
   ↓
2. Cluster mentions using embeddings (cosine similarity)
   ↓
3. For each cluster:
   ├─ Check if matches existing issue
   ├─ If match: Update existing issue
   └─ If new: Create TopicIssue record (if cluster size >= 3)
   ↓
4. Link mentions to issues (via issue_mentions table)
   ↓
5. Calculate:
   ├─ Priority score
   ├─ Lifecycle state
   ├─ Sentiment aggregation
   └─ Volume/velocity metrics
```

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  AUTOMATIC: Test Cycle No-Auth                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Mention 1: "Hospital needs funding"                  │
│    ↓                                                    │
│  ✅ Sentiment: negative (-0.7)                        │
│  ✅ Topic: health_care (confidence: 0.85)              │
│  ✅ Emotion: sadness (0.6)                              │
│  ✅ Embedding: [0.123, -0.456, ...] (1536 dims)        │
│  ⚠️  issue_label: "Health Care" (fallback only!)       │
│                                                         │
│  Mention 2: "Doctors strike over pay"                  │
│    ↓                                                    │
│  ✅ Sentiment: negative (-0.8)                          │
│  ✅ Topic: health_care (confidence: 0.90)              │
│  ✅ Emotion: anger (0.7)                                │
│  ✅ Embedding: [0.234, -0.567, ...] (1536 dims)         │
│  ⚠️  issue_label: "Health Care" (fallback only!)       │
│                                                         │
│  Mention 3: "Lagos hospital power outage"              │
│    ↓                                                    │
│  ✅ Sentiment: negative (-0.6)                          │
│  ✅ Topic: health_care (confidence: 0.75)               │
│  ✅ Emotion: fear (0.5)                                 │
│  ✅ Embedding: [0.345, -0.678, ...] (1536 dims)        │
│  ⚠️  issue_label: "Health Care" (fallback only!)       │
│                                                         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  MANUAL: Issue Detection (Must Run Separately)         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Topic: health_care                                     │
│    ↓                                                    │
│  Get all mentions with topic "health_care"              │
│    ↓                                                    │
│  Cluster mentions by embedding similarity               │
│    ↓                                                    │
│  Cluster 1: [Mention 1, Mention 2]                     │
│    → Similarity: 0.82 (high)                           │
│    → Creates Issue: "Healthcare Funding Crisis"        │
│                                                         │
│  Cluster 2: [Mention 3]                                 │
│    → Only 1 mention (needs 3+ to create issue)        │
│    → No issue created                                   │
│                                                         │
│  Result:                                                │
│  ✅ Issue created in topic_issues table                 │
│  ✅ Mentions linked via issue_mentions table            │
│  ✅ Priority score calculated: 75 (high)                │
│  ✅ Lifecycle state: "active"                           │
│  ✅ Sentiment aggregation: -0.75 (very negative)        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Why Issues Are Not Automatic

**Reasons**:

1. **Computational Cost**: Clustering analysis is expensive (requires comparing all mentions)
2. **Not Always Needed**: Not all use cases need issue detection
3. **Control**: Allows manual control over when/how issues are created
4. **Frequency**: Can be run periodically (e.g., daily) rather than on every cycle
5. **Flexibility**: Can detect issues for specific topics only

**Best Practice**:
- Run main cycle frequently (e.g., every hour) to process new mentions
- Run issue detection less frequently (e.g., daily) to create/update issues

---

## Summary

| Feature | Automatic? | When | Where Stored |
|---------|-----------|------|--------------|
| **Mentions** | ✅ Yes | Phase 1-2 | `sentiment_data` |
| **Sentiment** | ✅ Yes | Phase 4 | `sentiment_data` |
| **Topics** | ✅ Yes | Phase 4 | `mention_topics` |
| **Emotions** | ✅ Yes | Phase 4 | `sentiment_data` |
| **Embeddings** | ✅ Yes | Phase 4 | `sentiment_embeddings` |
| **Locations** | ✅ Yes | Phase 5 | `sentiment_data` |
| **Issues** | ❌ No | Manual | `topic_issues` |

**To Create Issues**:
1. Run test cycle (automatic) ✅
2. Run issue detection (manual) ⚠️

---

## Related Documentation

- [COMPUTED_PARAMETERS_AND_USER_FILTERING.md](./COMPUTED_PARAMETERS_AND_USER_FILTERING.md) - Complete parameter documentation
- [TEST_CYCLE_NO_AUTH_FLOW.md](./TEST_CYCLE_NO_AUTH_FLOW.md) - Test cycle flow details
