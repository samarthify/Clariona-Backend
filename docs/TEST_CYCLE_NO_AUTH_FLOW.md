# `/agent/test-cycle-no-auth` Endpoint Flow & OpenAI API Calls

This document traces the complete flow of the `/agent/test-cycle-no-auth` endpoint and lists **ONLY** the OpenAI API calls made during execution.

---

## 📍 Endpoint Location

**File**: `src/api/service.py`  
**Line**: 259  
**Method**: `test_single_cycle_no_auth()`

---

## 🔄 Complete Flow

### Entry Point
```
POST /agent/test-cycle-no-auth
  ↓
test_single_cycle_no_auth()
  ↓
agent.run_single_cycle_parallel(user_id)  [or agent._run_automatic_collection() which also calls run_single_cycle_parallel]
```

---

## 📋 Phase-by-Phase Breakdown

### **Phase 1: Collection** 
**Method**: `collect_data_parallel(user_id)`  
**File**: `src/agent/core.py` (line 1526)  
**OpenAI Calls**: ❌ **NONE**  
**Purpose**: Collects raw data from various sources (Twitter, Facebook, News, YouTube, RSS, etc.)

---

### **Phase 2: Data Loading**
**Method**: `_push_raw_data_to_db(user_id)`  
**File**: `src/agent/core.py` (line 1540)  
**OpenAI Calls**: ❌ **NONE**  
**Purpose**: Loads collected raw data from CSV files into database

---

### **Phase 3: Deduplication**
**Method**: `_run_deduplication(user_id)`  
**File**: `src/agent/core.py` (line 1558)  
**OpenAI Calls**: ❌ **NONE**  
**Purpose**: Removes duplicate records before processing

---

### **Phase 4: Sentiment Analysis** ⚠️ **OPENAI CALLS HERE**
**Method**: `_run_sentiment_batch_update_parallel(user_id)`  
**File**: `src/agent/core.py` (line 1583)  
**OpenAI Calls**: ✅ **YES** (see details below)

**Flow**:
```
_run_sentiment_batch_update_parallel(user_id)
  ↓
_process_sentiment_batches_parallel(batches, user_id)
  ↓
process_single_batch(batch_data)
  ↓
self.data_processor.batch_get_sentiment(texts_list, source_types_list)
  ↓
self.get_sentiment(text, source_type)  [called for each text]
  ↓
self.sentiment_analyzer.analyze(text, source_type)
  ↓
┌─────────────────────────────────────┐
│  OpenAI API Call #1: Sentiment     │
│  _call_openai_for_presidential_    │
│  sentiment(text)                    │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│  OpenAI API Call #2: Embedding      │
│  _get_embedding(text)               │
└─────────────────────────────────────┘
```

---

### **Phase 5: Location Classification**
**Method**: `_run_location_batch_update_parallel(user_id)`  
**File**: `src/agent/core.py` (line 1599)  
**OpenAI Calls**: ❌ **NONE**  
**Purpose**: Classifies location using keyword/pattern matching (no OpenAI)

---

### **Phase 6: Issue Detection** ⚠️ **AUTOMATIC**
**Method**: `_run_issue_detection(user_id)`  
**File**: `src/agent/core.py` (line ~1610)  
**OpenAI Calls**: ❌ **NONE** (uses embeddings + clustering)  
**Purpose**: Detects issues by clustering similar mentions together

**Flow**:
```
_run_issue_detection(user_id)
  ↓
self.data_processor.detect_issues_for_all_topics()
  ↓
IssueDetectionEngine.detect_issues(topic_key)
  ↓
Cluster mentions using embeddings (cosine similarity)
  ↓
Create/update TopicIssue records
  ↓
Link mentions to issues via issue_mentions table
```

**Process**:
1. Gets all topics that have mentions (from `mention_topics` table)
2. For each topic:
   - Gets unprocessed mentions for the topic
   - Clusters mentions using embeddings (cosine similarity)
   - For each cluster:
     - Checks if matches existing issue (similarity threshold: 0.70)
     - If match: Updates existing issue with new mentions
     - If new: Creates `TopicIssue` record (if cluster size >= 3)
   - Links mentions to issues via `issue_mentions` table
   - Calculates priority scores, lifecycle states, sentiment aggregations

**What Gets Created**:
- `TopicIssue` records in `topic_issues` table
- `IssueMention` records linking mentions to issues
- `TopicIssueLink` records linking topics to issues
- Issue slug, label, priority, lifecycle state

**Configuration**:
- `processing.issue_detection.min_cluster_size` (default: 3) - Minimum mentions per cluster
- `processing.issue_detection.similarity_threshold` (default: 0.75) - Clustering similarity threshold
- `processing.issue_detection.issue_similarity_threshold` (default: 0.70) - Similarity threshold for matching to existing issues

---

## 🔍 OpenAI API Calls in Detail

### **Call #1: Presidential Sentiment Analysis**

**Location**: `src/processing/presidential_sentiment_analyzer.py`  
**Method**: `_call_openai_for_presidential_sentiment()` (line 207)  
**Line**: 228  
**API**: `openai_client.responses.create()`

**When Called**: 
- Once per record during Phase 4 (Sentiment Analysis)
- For up to **500 records** (configurable via `processing.limits.max_records_per_batch`)
- Processed in **batches of 150** (configurable via `parallel_processing.sentiment_batch_size`)

**Model**: 
- `gpt-5-mini`, `gpt-5-nano`, `gpt-4.1-mini`, or `gpt-4.1-nano` (from config: `models.llm_models.available`)

**Input**:
```python
{
    "model": self.model,  # e.g., "gpt-5-mini"
    "input": [
        {
            "role": "system",
            "content": "You are a strategic advisor to {president_name} analyzing media impact."
        },
        {
            "role": "user",
            "content": """Analyze media from {president_name}'s perspective. Evaluate: Does this help or hurt the President's power/reputation/governance?

Categories:
- POSITIVE: Strengthens image/agenda, builds political capital
- NEGATIVE: Threatens image/agenda, creates problems
- NEUTRAL: No material impact

Response format:
Sentiment: [POSITIVE/NEGATIVE/NEUTRAL]
Sentiment Score: [-1.0 to 1.0] (POSITIVE: 0.2-1.0, NEGATIVE: -1.0 to -0.2, NEUTRAL: -0.2 to 0.2)
Justification: [Brief strategic reasoning]
Topics: [comma-separated topics]

Text: "{text}"
"""
        }
    ],
    "store": False
}
```

**Variables**:
- `{president_name}`: From config `processing.prompt_variables.president_name` (default: "Bola Ahmed Tinubu")
- `{text}`: Record text truncated to 800 characters (configurable via `processing.prompts.presidential_sentiment.text_truncate_length`)

**Returns**:
- Sentiment label (positive/negative/neutral)
- Sentiment score (-1.0 to 1.0)
- Justification (text explanation)
- Topics (comma-separated list)

**Justification Response Size**:
- **No explicit `max_tokens` limit** specified in API call (uses model default)
- **Prompt requests**: "Brief strategic reasoning" (encourages concise responses)
- **Typical size**: ~50-200 words (~100-400 tokens) based on prompt guidance
- **Database storage**: `Text` type (PostgreSQL) - can store up to ~1GB, effectively unlimited
- **Final stored value**: Justification + Recommended Action combined (line 394)
- **No truncation**: Full response is stored as-is

**Rate Limiter**: `MultiModelRateLimiter`  
**Estimated Tokens**: ~1000 tokens per call (input + output)

---

### **Call #2: Text Embedding Generation**

**Location**: `src/processing/presidential_sentiment_analyzer.py`  
**Method**: `_get_embedding()` (line 542)  
**Line**: 552  
**API**: `openai_client.embeddings.create()`

**When Called**: 
- Once per record during Phase 4 (Sentiment Analysis)
- For up to **500 records** (same as sentiment analysis)
- **Note**: Can be batched using `_get_embeddings_batch()` (line 563) if implemented

**Model**: `text-embedding-3-small` (from config: `models.embedding_model`)

**Input**:
```python
{
    "model": "text-embedding-3-small",
    "input": text_for_embedding  # Text truncated to 8000 characters
}
```

**Returns**:
- Embedding vector: Array of **1536 floating-point numbers**

**Rate Limiter**: `RateLimiter`  
**Estimated Tokens**: ~2200 tokens per text

**Batch Option**:
- If using `_get_embeddings_batch()` (line 583), multiple texts can be sent in one API call
- Batch size: Up to 2048 texts per batch (OpenAI limit)
- **Benefit**: Reduces API calls from N to 1 per batch

---

## 🔍 Issue Classification (NOT in Main Cycle)

### **Call #3: Issue Classification** ⚠️ **NOT CALLED IN MAIN CYCLE**

**Location**: `src/processing/issue_classifier.py`  
**Method**: `_classify_with_comparison()` (line 275)  
**Line**: 292  
**API**: `openai_client.responses.create()`

**Status**: ❌ **NOT CALLED** during `/agent/test-cycle-no-auth` endpoint

**Why Not Called**:
- `GovernanceAnalyzer.analyze()` is initialized but **not invoked** in the main sentiment pipeline
- `DataProcessor.get_sentiment()` only calls `PresidentialSentimentAnalyzer.analyze()`
- Issue classification would only run if `GovernanceAnalyzer.analyze()` is explicitly called

**When It WOULD Be Called** (if enabled):
- Only when `GovernanceAnalyzer.analyze()` is invoked (not in current main cycle)
- For records classified into a ministry (not "non_governance")
- When `enable_issue_classification=True` (default: True, but analyzer not called)

**Model**: 
- `gpt-5-mini`, `gpt-5-nano`, `gpt-4.1-mini`, or `gpt-4.1-nano` (from config)

**Input**:
```python
{
    "model": self.model,  # e.g., "gpt-5-nano"
    "input": [
        {
            "role": "system",
            "content": "You are a governance analyst classifying mentions into specific issues within ministries."
        },
        {
            "role": "user",
            "content": """Classify this mention into an existing issue or create new one.

Ministry: {ministry}
Existing Issues: {existing_issues_list}

Response format (JSON):
{
    "matches_existing": true/false,
    "matched_issue_slug": "issue-slug" (if matches),
    "new_issue_label": "New Issue Label" (if creating new),
    "reasoning": "Brief explanation"
}

Text: "{text}"
"""
        }
    ],
    "store": False
}
```

**Returns**:
- JSON with `matches_existing`, `matched_issue_slug` or `new_issue_label`, and `reasoning`
- If matches existing: Returns existing issue slug and label
- If creating new: Creates new issue (up to 20 per ministry)

**Rate Limiter**: `MultiModelRateLimiter`  
**Estimated Tokens**: ~800 tokens per call

---

### **Call #4: Forced Issue Match** (Consolidation Mode)

**Location**: `src/processing/issue_classifier.py`  
**Method**: `_classify_with_comparison_forced_match()` (line 480)  
**Line**: 498  
**API**: `openai_client.responses.create()`

**Status**: ❌ **NOT CALLED** during `/agent/test-cycle-no-auth` endpoint

**When It WOULD Be Called** (if enabled):
- Only when at the **20 issue limit** for a ministry
- Forces consolidation - must match to existing issue (no new issues allowed)
- Same conditions as Call #3 (GovernanceAnalyzer must be invoked)

**Model**: Same as Call #3

**Input**: Similar to Call #3, but with `is_consolidation=True` flag in prompt

**Returns**: JSON with forced match to existing issue (never creates new)

**Rate Limiter**: `MultiModelRateLimiter`  
**Estimated Tokens**: ~800 tokens per call

---

## 🔍 How Issue Detection Actually Works (IssueDetectionEngine)

### **Issue Detection Process** (NO OpenAI Calls)

**System**: `IssueDetectionEngine` (Week 4 - Clustering-based)  
**Status**: ✅ **AUTOMATICALLY CALLED** during Phase 6 of main cycle  
**OpenAI Calls**: ❌ **NONE** (uses embeddings + clustering)

**How Issues Are Created**:

1. **During Phase 4 (Sentiment Analysis)**:
   - Topics are classified for each record (using embeddings + cosine similarity)
   - Topics stored in `mention_topics` table
   - **NO issue detection happens here**

2. **Issue Detection (Phase 6 - Automatic)**:
   - Automatically called during main cycle: `_run_issue_detection(user_id)`
   - Processes all topics that have mentions
   - **Process**:
     ```
     detect_issues(topic_key)
       ↓
     Get mentions for topic (from mention_topics table)
       ↓
     Cluster mentions using embeddings (cosine similarity)
       ↓
     For each cluster:
       - Check if matches existing issue (similarity threshold)
       - If matches: Update existing issue
       - If new: Create TopicIssue record (if conditions met)
       - Link mentions via issue_mentions table
     ```

3. **Issue Creation Conditions**:
   - Minimum cluster size (default: 3 mentions)
   - Similarity threshold (default: 0.75)
   - Temporal proximity (within time window)
   - Volume/velocity thresholds

4. **What Gets Created**:
   - `TopicIssue` record in `topic_issues` table
   - `IssueMention` records linking mentions to issue
   - `TopicIssueLink` records linking topic to issue
   - Issue slug, label, priority, lifecycle state

5. **Issue Fields in SentimentData**:
   - `issue_label` and `issue_slug` in `SentimentData` table are **simple fallbacks** (line 384-385)
   - Generated from topic name: `topics[0].replace('_', ' ').title()`
   - **NOT** from actual issue detection
   - Actual issues are in `topic_issues` table, linked via `issue_mentions`

**Key Points**:
- ✅ **NO OpenAI API calls** - uses pre-generated embeddings
- ✅ **Clustering-based** - groups similar mentions together
- ✅ **Topic-based** - issues are created per topic
- ✅ **Automatic** - runs automatically during Phase 6
- ✅ **Part of main cycle** - integrated into test cycle flow

---

## 📊 API Call Summary

### Per Record:
- **1 call** to `responses.create()` (sentiment analysis)
- **1 call** to `embeddings.create()` (embedding) OR **1 batch call** for multiple texts

### Per Cycle (500 records max):
- **500 calls** to `responses.create()` (sentiment analysis)
- **500 calls** to `embeddings.create()` (individual) OR **~4 batch calls** (if batched: 500 ÷ 150 = ~4 batches)

**Total**: ~500-1000 API calls per cycle (depending on batch vs individual embedding calls)

---

## ⚠️ Important Notes

1. **Emotion Detection**: Uses **HuggingFace model** (`j-hartmann/emotion-english-distilroberta-base`), **NOT OpenAI**. No API calls.

2. **Topic Classification**: Uses **pre-generated topic embeddings** and cosine similarity. No OpenAI calls during classification.

3. **Location Classification**: Uses **keyword/pattern matching**. No OpenAI calls.

4. **Issue Classification & Detection**: 
   - **Two Different Systems**:
   
   **A. IssueClassifier (Legacy - NOT USED)**:
   - **Status**: ❌ **NOT CALLED** during `/agent/test-cycle-no-auth` endpoint flow
   - **Why**: `GovernanceAnalyzer.analyze()` is not called in the main sentiment pipeline (`DataProcessor.get_sentiment()` only uses `PresidentialSentimentAnalyzer`)
   - **When it WOULD be called**: Only if `GovernanceAnalyzer.analyze()` is explicitly invoked (not in current main cycle)
   - **If enabled, would make**: 1-2 OpenAI API calls per record (depending on issue count and consolidation mode)
     - **Call #1**: `_classify_with_comparison()` (line 292) - Compare to existing issues, may create new
     - **Call #2**: `_classify_with_comparison_forced_match()` (line 498) - Only if at 20 issue limit (forced consolidation)
   - **API**: `openai_client.responses.create()` 
   - **Model**: `gpt-5-mini`, `gpt-5-nano`, `gpt-4.1-mini`, or `gpt-4.1-nano`
   - **Estimated Tokens**: ~800 tokens per call
   - **Purpose**: Classify mentions into specific issues within a ministry (max 20 issues per ministry)
   - **Rate Limiter**: `MultiModelRateLimiter`
   
   **B. IssueDetectionEngine (Active - Week 4 System)**:
   - **Status**: ✅ **AVAILABLE** but **NOT AUTOMATICALLY CALLED** during main cycle
   - **How Issues Are Created**:
     1. **Topics are classified** during Phase 4 (sentiment analysis) - uses embeddings + cosine similarity (NO OpenAI)
     2. **Issues are detected separately** via `IssueDetectionEngine.detect_issues()` - clustering-based (NO OpenAI)
     3. **Process**: 
        - Groups mentions by topic (from `mention_topics` table)
        - Clusters similar mentions using embeddings (cosine similarity)
        - Creates `TopicIssue` records from clusters (if conditions met: min cluster size, similarity threshold)
        - Links mentions to issues via `issue_mentions` table
     4. **NO OpenAI API calls** - uses pre-generated embeddings and clustering algorithms
     5. **When called**: Must be explicitly invoked via `DataProcessor.detect_issues_for_topic()` or `detect_issues_for_all_topics()`
     6. **Issue fields in SentimentData**: `issue_label` and `issue_slug` are populated from topics (simple fallback, line 384-385 in `presidential_sentiment_analyzer.py`), NOT from actual issue detection
     7. **Actual issues**: Stored in `topic_issues` table, linked via `issue_mentions` junction table

5. **Batch Processing**: 
   - Sentiment analysis: Processed in batches of 150 (parallel workers)
   - Embeddings: Can be batched (up to 2048 texts per batch) to reduce API calls

6. **Rate Limiting**: All OpenAI calls use rate limiters:
   - `MultiModelRateLimiter` for sentiment (responses API)
   - `RateLimiter` for embeddings

---

## 💰 Cost Estimation (Per Cycle)

### Per Record:
- Sentiment Analysis: ~1000 tokens × $0.001/1K tokens = **$0.001**
- Embedding: ~2200 tokens × $0.00013/1K tokens = **$0.0003**

**Total per record**: ~$0.0013

### Per Cycle (500 records):
- Sentiment: 500 × $0.001 = **$0.50**
- Embeddings: 500 × $0.0003 = **$0.15** (or ~$0.001 if batched)

**Total per cycle**: ~$0.50 - $0.65

---

## 🔗 Related Documentation

- **Complete OpenAI API Calls Reference**: `docs/OPENAI_API_CALLS.md`
- **Backend Architecture**: `BACKEND_ARCHITECTURE.md`
