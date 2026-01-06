# OpenAI API Calls - Complete Reference

This document lists **ALL** places where OpenAI API calls are made in the codebase.

## 📍 Summary

**Total OpenAI API Call Locations: 10**

### By Type:
- **Chat/Responses API**: 6 calls
- **Embeddings API**: 4 calls

### ⚠️ Important Note:
- **Emotion Detection (anger, fear, trust, sadness, joy, disgust)**: Uses **HuggingFace model** (`j-hartmann/emotion-english-distilroberta-base`), **NOT OpenAI**. This is a local model that runs on the server - no API calls.

### By Module:
- `presidential_sentiment_analyzer.py`: 3 calls (1 responses, 2 embeddings)
- `governance_analyzer.py`: 3 calls (1 responses, 2 embeddings)
- `issue_classifier.py`: 2 calls (2 responses)
- `topic_embedding_generator.py`: 1 call (1 embeddings)
- `sentiment_analyzer.py`: 1 call (1 chat completions)
- `sentiment_analyzer_huggingface.py`: 1 call (1 chat completions)
- `llm_providers.py`: 1 call (1 chat completions)

---

## 🔍 Detailed Locations

### 1. **Presidential Sentiment Analysis** 
**File**: `src/processing/presidential_sentiment_analyzer.py`

#### 1.1 Sentiment Analysis (Responses API)
- **Method**: `_call_openai_for_presidential_sentiment()` (line 207)
- **Line**: 228
- **API Call**: `openai_client.responses.create()`
- **Model**: `self.model` (gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano)
- **Purpose**: Analyze sentiment from President's perspective
- **Estimated Tokens**: ~1000 tokens
- **When Called**: Every time a record needs sentiment analysis
- **Rate Limiter**: MultiModelRateLimiter

**System Message** (from config or default):
```
You are a strategic advisor to {president_name} analyzing media impact.
```
Default: `"You are a strategic advisor to Bola Ahmed Tinubu analyzing media impact."`

**User Prompt** (from config or default):
```
Analyze media from {president_name}'s perspective. Evaluate: Does this help or hurt the President's power/reputation/governance?

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
```

**Example with actual data**:
- `president_name`: "Bola Ahmed Tinubu" (from config: `processing.prompt_variables.president_name`)
- `text`: Truncated to 800 characters (configurable via `processing.prompts.presidential_sentiment.text_truncate_length`)

**What it gets back**:
- Sentiment label (positive/negative/neutral)
- Sentiment score (-1.0 to 1.0)
- Justification (text explanation)
- Topics (comma-separated list)

```python
response = self.openai_client.responses.create(
    model=self.model,
    input=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_prompt}
    ],
    store=False
)
```

#### 1.2 Single Text Embedding
- **Method**: `_get_embedding()` (line 542)
- **Line**: 552
- **API Call**: `openai_client.embeddings.create()`
- **Model**: `text-embedding-3-small` (from config: `models.embedding_model`)
- **Purpose**: Generate embedding for a single text
- **Estimated Tokens**: ~2200 tokens per text
- **When Called**: When generating embedding for sentiment analysis result

**Input Data**:
- **Text**: The actual text content from the record (truncated to 8000 characters)
- **No prompt**: Embeddings API doesn't use prompts, just raw text

**What it gets back**:
- **Embedding vector**: Array of 1536 floating-point numbers representing semantic meaning

**Example**:
```python
# Input: "The Nigerian government has announced a major healthcare reform..."
# Output: [0.0123, -0.0456, 0.0789, ...] (1536 dimensions)
```

```python
response = self.openai_client.embeddings.create(
    model=self._get_embedding_model(),  # "text-embedding-3-small"
    input=text_for_embedding  # Text truncated to 8000 chars
)
# Returns: response.data[0].embedding (1536-dim vector)
```

#### 1.3 Batch Embeddings
- **Method**: `_get_embeddings_batch()` (line 563)
- **Line**: 583
- **API Call**: `openai_client.embeddings.create()`
- **Model**: `text-embedding-3-small`
- **Purpose**: Generate embeddings for multiple texts in one batch
- **Estimated Tokens**: ~2200 tokens × number of texts
- **When Called**: When batch processing multiple records

**Input Data**:
- **Texts**: List of text strings (each truncated to 8000 characters)
- **No prompt**: Embeddings API doesn't use prompts, just raw text
- **Batch size**: Can handle up to 2048 texts per batch (OpenAI limit)

**What it gets back**:
- **Embeddings**: List of 1536-dim vectors, one per input text (same order)

**Example**:
```python
# Input: [
#   "The Nigerian government has announced healthcare reform...",
#   "Education funding needs urgent attention...",
#   "Infrastructure projects are progressing well..."
# ]
# Output: [
#   [0.0123, -0.0456, ...],  # 1536 dims for text 1
#   [0.0234, -0.0567, ...],  # 1536 dims for text 2
#   [0.0345, -0.0678, ...]   # 1536 dims for text 3
# ]
```

**Benefits of batch**:
- **Cost**: Same cost as individual calls, but faster
- **Rate Limits**: Counts as 1 API call instead of N calls
- **Efficiency**: Processes up to 2048 texts in one request

```python
response = self.openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=texts_for_embedding  # List of texts, each truncated to 8000 chars
)
# Returns: response.data (list of embeddings in same order as input)
```

---

### 2. **Governance/Ministry Classification**
**File**: `src/processing/governance_analyzer.py`

#### 2.1 Ministry Classification (Responses API)
- **Method**: `_analyze_with_openai()` (line 236)
- **Line**: 252
- **API Call**: `openai_client.responses.create()`
- **Model**: `self.model` (gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano)
- **Purpose**: Classify ministry/issue for governance analysis
- **Estimated Tokens**: ~1200 tokens
- **When Called**: When classifying ministry/issue (legacy, may not be used)
- **Rate Limiter**: MultiModelRateLimiter

```python
response = self.openai_client.responses.create(
    model=self.model,
    input=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_prompt}
    ],
    store=False
)
```

#### 2.2 Single Text Embedding
- **Method**: `_get_embedding()` (line 461)
- **Line**: 468
- **API Call**: `openai_client.embeddings.create()`
- **Model**: `text-embedding-3-small`
- **Purpose**: Generate embedding for governance analysis
- **Estimated Tokens**: ~2200 tokens
- **When Called**: When generating embedding for governance classification

```python
response = self.openai_client.embeddings.create(
    model=self._get_embedding_model(),
    input=text[:8000]
)
```

#### 2.3 Batch Embeddings
- **Method**: `_get_embeddings_batch()` (line 480)
- **Line**: 499
- **API Call**: `openai_client.embeddings.create()`
- **Model**: `text-embedding-3-small`
- **Purpose**: Generate embeddings for multiple texts in batch
- **Estimated Tokens**: ~2200 tokens × number of texts
- **When Called**: When batch processing governance classifications

```python
response = self.openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=texts_for_embedding
)
```

---

### 3. **Issue Classification**
**File**: `src/processing/issue_classifier.py`

#### 3.1 Issue Classification (Responses API)
- **Method**: `_classify_with_comparison()` (line 275)
- **Line**: 292
- **API Call**: `openai_client.responses.create()`
- **Model**: `self.model` (gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano)
- **Purpose**: Compare new mention to existing issues and decide match or create new
- **Estimated Tokens**: ~800 tokens
- **When Called**: When classifying issues for mentions
- **Rate Limiter**: MultiModelRateLimiter

```python
response = self.openai_client.responses.create(
    model=self.model,
    input=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_prompt}
    ],
    store=False
)
```

#### 3.2 Forced Issue Match (Responses API)
- **Method**: `_classify_with_comparison_forced_match()` (line 480)
- **Line**: 498
- **API Call**: `openai_client.responses.create()`
- **Model**: `self.model` (gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano)
- **Purpose**: Force match to existing issue when at 20 issue limit
- **Estimated Tokens**: ~800 tokens
- **When Called**: When at issue limit and need to consolidate
- **Rate Limiter**: MultiModelRateLimiter

```python
response = self.openai_client.responses.create(
    model=self.model,
    input=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_prompt}
    ],
    store=False
)
```

---

### 4. **Topic Embedding Generation**
**File**: `src/processing/topic_embedding_generator.py`

#### 4.1 Topic Embedding
- **Method**: `generate_embedding()` (line 130)
- **Line**: 149
- **API Call**: `openai_client.embeddings.create()`
- **Model**: `text-embedding-3-small`
- **Purpose**: Generate embedding for topic keywords/description
- **Estimated Tokens**: ~2200 tokens
- **When Called**: When initializing topics or updating topic embeddings

```python
response = self.openai_client.embeddings.create(
    model=self._get_embedding_model(),
    input=embedding_text[:8000]
)
```

---

### 5. **Legacy Sentiment Analyzers** (May not be actively used)

#### 5.1 Sentiment Analyzer (Chat Completions)
**File**: `src/processing/sentiment_analyzer.py`
- **Method**: `_call_chatgpt_for_sentiment()` (line 154)
- **Line**: 186
- **API Call**: `openai_client.chat.completions.create()`
- **Model**: `gpt-4.1-nano`
- **Purpose**: Legacy sentiment analysis (may not be used)
- **When Called**: If legacy analyzer is used

```python
response = self.openai_client.chat.completions.create(
    model="gpt-4.1-nano",
    messages=[...],
    max_tokens=100,
    temperature=0.2
)
```

#### 5.2 HuggingFace Sentiment Analyzer (Chat Completions)
**File**: `src/processing/sentiment_analyzer_huggingface.py`
- **Method**: `_call_chatgpt_for_sentiment()` (line 181)
- **Line**: 205
- **API Call**: `openai_client.chat.completions.create()`
- **Model**: `gpt-4.1-nano`
- **Purpose**: Legacy sentiment refinement (may not be used)
- **When Called**: If legacy analyzer is used

```python
response = self.openai_client.chat.completions.create(
    model="gpt-4.1-nano",
    messages=[...],
    max_tokens=100,
    temperature=0.2
)
```

---

### 6. **LLM Provider** (Generic)
**File**: `src/agent/llm_providers.py`

#### 6.1 Generic LLM Call
- **Method**: `generate()` (line 143)
- **Line**: 154
- **API Call**: `client.chat.completions.create()`
- **Model**: Configurable
- **Purpose**: Generic LLM provider interface
- **When Called**: If LLM provider is used directly

```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    **kwargs
)
```

---

## 🔄 Call Flow in Data Processing Pipeline

### Main Processing Flow (`DataProcessor.get_sentiment()`):

1. **Presidential Sentiment Analysis** (Line 228 in `presidential_sentiment_analyzer.py`)
   - Calls: `_call_openai_for_presidential_sentiment()`
   - API: `responses.create()` - **1 call per record**

2. **Emotion Detection** (Line 613 in `presidential_sentiment_analyzer.py` → `emotion_analyzer.py`)
   - Calls: `EmotionAnalyzer.analyze_emotion()`
   - **NO OpenAI API**: Uses HuggingFace model `j-hartmann/emotion-english-distilroberta-base`
   - Runs locally on server (no API calls, no cost)
   - Detects: anger, fear, trust, sadness, joy, disgust

3. **Embedding Generation** (Line 552 or 583 in `presidential_sentiment_analyzer.py`)
   - Calls: `_get_embedding()` or `_get_embeddings_batch()`
   - API: `embeddings.create()` - **1 call per record** (or 1 batch call for multiple)

4. **Topic Classification** (Uses embeddings, but topic embeddings are pre-generated)
   - Topic embeddings generated once during initialization
   - Uses cosine similarity, no API calls during classification

### Batch Processing Flow (`_run_sentiment_batch_update_parallel()`):

For **500 records** processed in **batches of 150**:

1. **Sentiment Analysis**: 500 × 1 = **500 API calls** (`responses.create()`)
2. **Embeddings**: 500 × 1 = **500 API calls** (`embeddings.create()`) OR **~4 batch calls** (if using batch)

**Total per cycle**: ~500-1000 API calls (depending on batch vs individual embedding calls)

---

## 💰 Cost Estimation

### Per Record:
- Sentiment Analysis: ~1000 tokens × $0.001/1K tokens = **$0.001**
- Embedding: ~2200 tokens × $0.00013/1K tokens = **$0.0003**

**Total per record**: ~$0.0013

### Per Batch (500 records):
- Sentiment: 500 × $0.001 = **$0.50**
- Embeddings: 500 × $0.0003 = **$0.15** (or ~$0.001 if batched)

**Total per batch**: ~$0.50 - $0.65

---

## ⚙️ Rate Limiting

All API calls use rate limiters:
- **MultiModelRateLimiter**: For responses API (sentiment, governance, issues)
- **RateLimiter**: For embeddings API

Models have different TPM (tokens per minute) limits:
- `gpt-5-mini`: 500,000 TPM
- `gpt-5-nano`: 200,000 TPM
- `gpt-4.1-mini`: 200,000 TPM
- `gpt-4.1-nano`: 200,000 TPM
- `text-embedding-3-small`: 1,000,000 TPM

---

---

## 🧠 Emotion Detection (NOT OpenAI)

**File**: `src/processing/emotion_analyzer.py`

### Emotion Detection Details

- **Method**: `analyze_emotion()` (line 127)
- **Model**: HuggingFace `j-hartmann/emotion-english-distilroberta-base` (local model)
- **NO OpenAI API**: Runs locally on server using transformers library
- **Purpose**: Detect 6 emotions: anger, fear, trust, sadness, joy, disgust
- **When Called**: During sentiment analysis (Week 3 enhancement)

**How it works**:
1. Uses HuggingFace transformers pipeline
2. Model runs locally (downloaded once, cached)
3. Returns emotion distribution with scores for all 6 emotions
4. Falls back to keyword matching if model unavailable

**Input**: Raw text (truncated to 512 chars)
**Output**: 
```python
{
    'emotion_label': 'anger',  # Primary emotion
    'emotion_score': 0.85,     # Confidence (0-1)
    'emotion_distribution': {
        'anger': 0.85,
        'fear': 0.05,
        'trust': 0.02,
        'sadness': 0.03,
        'joy': 0.02,
        'disgust': 0.03
    }
}
```

**Cost**: **$0** (runs locally, no API calls)

---

## 📝 Notes

1. **Emotion Detection**: Uses HuggingFace model, NOT OpenAI. Runs locally with no API costs.

2. **Legacy Analyzers**: `sentiment_analyzer.py` and `sentiment_analyzer_huggingface.py` may not be actively used. The main pipeline uses `PresidentialSentimentAnalyzer`.

3. **Governance Analyzer**: May not be actively used if topic classification replaced it.

4. **Batch Embeddings**: Using batch embeddings API can significantly reduce API calls and costs.

5. **Issue Classification**: Only called when classifying issues, not for every record.

6. **Topic Embeddings**: Generated once during initialization, not per record.
