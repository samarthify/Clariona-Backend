# Classifier Independence Architecture
## Topic vs Sentiment: Independent Classification, Interdependent Processing

**Created**: January 27, 2025  
**Purpose**: Clarify the relationship between Topic and Sentiment classifiers

---

## Executive Summary

**Yes, Topic Classifier and Sentiment Classifier are INDEPENDENT** in terms of classification logic, but they **come together** in downstream processing (issues, priority, alerts).

---

## Classification Level: ✅ INDEPENDENT

### Topic Classifier
- **Input**: Text content, text embedding
- **Process**: Keyword matching + embedding similarity
- **Output**: List of topics (e.g., ["fuel_pricing", "economic_policy"])
- **Does NOT need sentiment** to classify topics

### Sentiment Classifier
- **Input**: Text content
- **Process**: Emotion detection + polarity analysis
- **Output**: Sentiment label, score, emotions
- **Does NOT need topics** to classify sentiment

### Key Point
```
Topic Classification: "What is this about?" → Topics
Sentiment Classification: "How do people feel?" → Sentiment

These are SEPARATE questions answered INDEPENDENTLY.
```

---

## Processing Flow (Independent Classification)

```
┌─────────────────────────────────────────────────────────────┐
│                    RAW MENTION                               │
│  Text: "Fuel prices are too high, government must act"      │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
    ┌───────────────────────┐  ┌───────────────────────┐
    │  TOPIC CLASSIFIER     │  │  SENTIMENT CLASSIFIER │
    │  (Independent)        │  │  (Independent)        │
    │                       │  │                       │
    │  Input: text +        │  │  Input: text          │
    │         embedding     │  │                       │
    │                       │  │  Process:            │
    │  Process:             │  │  - Polarity          │
    │  - Keyword match      │  │  - Emotion           │
    │  - Embedding sim      │  │  - Influence weight  │
    │                       │  │                       │
    │  Output:              │  │  Output:             │
    │  ["fuel_pricing"]     │  │  - negative          │
    │                       │  │  - score: -0.7      │
    │                       │  │  - emotion: anger   │
    └───────────────────────┘  └───────────────────────┘
                    │                   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────────┐
                    │  STORED IN DATABASE    │
                    │  - mention_topics      │
                    │  - sentiment_data      │
                    └───────────────────────┘
```

---

## Downstream Processing: ⚠️ INTERDEPENDENT

While classification is independent, they **come together** in downstream processing:

### 1. Issue Aggregation

**Where they meet**: Issue sentiment distribution

```python
# When aggregating mentions into an issue
issue = {
    'topic': 'fuel_pricing',  # From Topic Classifier
    'sentiment_distribution': {  # From Sentiment Classifier
        'positive': 0.1,
        'negative': 0.8,
        'neutral': 0.1
    },
    'weighted_sentiment_score': -0.65,  # Aggregated from sentiment
    'emotion_distribution': {  # From Sentiment Classifier
        'anger': 0.6,
        'fear': 0.2,
        ...
    }
}
```

**Dependency**: Issue needs BOTH topic (to know which issue) AND sentiment (to track public reaction)

---

### 2. Issue Priority Calculation

**Where they meet**: Priority score formula

```python
IssuePriorityScore = 
    (VolumeScore × W1) +
    (VelocityScore × W2) +
    (SentimentSeverity × W3) +  # ← Uses sentiment
    (InfluenceScore × W4) +
    (GeographicSpread × W5) +
    (PolicySensitivity × W6) +  # ← Uses topic
    (PersistenceScore × W7)
```

**Dependency**: Priority calculation needs BOTH:
- Topic (for policy sensitivity weight)
- Sentiment (for sentiment severity component)

---

### 3. Alert Triggers

**Where they meet**: Alert generation conditions

```python
# Alert triggers use BOTH
IF IssuePriority >= Threshold AND (
    VelocityTrigger OR 
    SentimentShiftTrigger OR  # ← Uses sentiment
    TopicSensitivityTrigger   # ← Uses topic
) THEN CREATE Alert
```

**Dependency**: Alerts need BOTH topic (sensitivity) and sentiment (shifts)

---

### 4. Topic-Adjusted Sentiment Normalization

**Where they meet**: Sentiment normalization by topic

```python
# Some topics are naturally negative
AdjustedSentiment = CurrentSentiment - TopicBaseline

# Example:
# Fuel pricing topic baseline: -0.4 (naturally negative)
# Current sentiment: -0.5
# Adjusted: -0.5 - (-0.4) = -0.1 (less alarming)
```

**Dependency**: Sentiment normalization needs topic to know baseline

---

## Architecture Diagram (Complete Flow)

```
┌─────────────────────────────────────────────────────────────┐
│                    MENTION PROCESSING                        │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
    ┌───────────────────────┐  ┌───────────────────────┐
    │  TOPIC CLASSIFIER     │  │  SENTIMENT CLASSIFIER│
    │  ✅ INDEPENDENT       │  │  ✅ INDEPENDENT       │
    │                       │  │                       │
    │  - Keyword match      │  │  - Polarity           │
    │  - Embedding sim      │  │  - Emotion            │
    │  - No sentiment needed│  │  - No topic needed    │
    │                       │  │                       │
    │  Output: Topics[]     │  │  Output: Sentiment    │
    └───────────────────────┘  └───────────────────────┘
                    │                   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────────┐
                    │  DATABASE STORAGE     │
                    │  - mention_topics     │
                    │  - sentiment_data     │
                    └───────────────────────┘
                              │
                              ▼
                    ┌───────────────────────┐
                    │  ISSUE DETECTION     │
                    │  ⚠️ USES BOTH         │
                    │                       │
                    │  - Topic: Which issue│
                    │  - Sentiment: Track  │
                    │    public reaction    │
                    └───────────────────────┘
                              │
                              ▼
                    ┌───────────────────────┐
                    │  ISSUE PRIORITY       │
                    │  ⚠️ USES BOTH         │
                    │                       │
                    │  - Topic: Sensitivity│
                    │  - Sentiment: Severity│
                    └───────────────────────┘
                              │
                              ▼
                    ┌───────────────────────┐
                    │  ALERT GENERATION     │
                    │  ⚠️ USES BOTH         │
                    │                       │
                    │  - Topic: Sensitivity│
                    │  - Sentiment: Shifts  │
                    └───────────────────────┘
```

---

## Key Points

### ✅ Independence (Classification)

1. **Topic Classifier**:
   - Analyzes: "What is this about?"
   - Uses: Keywords, embeddings
   - Does NOT need sentiment

2. **Sentiment Classifier**:
   - Analyzes: "How do people feel?"
   - Uses: Text content, emotion models
   - Does NOT need topics

### ⚠️ Interdependence (Processing)

1. **Issue Aggregation**:
   - Needs topic to group mentions
   - Needs sentiment to track public reaction

2. **Issue Priority**:
   - Needs topic for policy sensitivity
   - Needs sentiment for severity

3. **Alert Triggers**:
   - Needs topic for sensitivity thresholds
   - Needs sentiment for shift detection

4. **Sentiment Normalization**:
   - Needs topic to know baseline
   - Adjusts sentiment by topic

---

## Implementation Implications

### Can Run in Parallel

```python
# These can run simultaneously (independent)
topic_results = topic_classifier.classify(text, embedding)
sentiment_results = sentiment_classifier.analyze(text)

# Then combine for downstream processing
issue_data = {
    'topics': topic_results,
    'sentiment': sentiment_results
}
```

### Must Combine for Aggregation

```python
# Issue aggregation needs both
def aggregate_issue(issue_id):
    mentions = get_mentions_for_issue(issue_id)
    
    # Combine topic and sentiment
    topics = [m['topic'] for m in mentions]
    sentiments = [m['sentiment'] for m in mentions]
    
    issue = {
        'primary_topic': most_common(topics),
        'sentiment_distribution': aggregate(sentiments),
        'weighted_sentiment': calculate_weighted(sentiments)
    }
```

---

## Summary

| Aspect | Topic Classifier | Sentiment Classifier |
|--------|-----------------|---------------------|
| **Classification** | ✅ Independent | ✅ Independent |
| **Input** | Text + Embedding | Text |
| **Output** | Topics[] | Sentiment + Emotions |
| **Needs Other?** | ❌ No | ❌ No |
| **Used Together?** | ⚠️ Yes (downstream) | ⚠️ Yes (downstream) |

**Answer**: 
- **Classification**: ✅ **YES, they are independent**
- **Processing**: ⚠️ **NO, they come together downstream**

---

**Status**: ✅ Architecture Clarified  
**Last Updated**: January 27, 2025









