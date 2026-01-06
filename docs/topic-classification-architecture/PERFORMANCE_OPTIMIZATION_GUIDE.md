# Guide: Performance Optimization

**Last Updated**: 2024-12-19  
**Purpose**: Guide for optimizing performance of the classification system

---

## 📊 Current Performance Baseline

### Measured Performance (from Week 6 tests)

- **Single Text Processing**: ~37 seconds (first run, includes model loading)
- **Batch Processing**: ~2.27 seconds per text
- **Throughput**: 0.44 texts/second
- **Long Text (12,500 chars)**: 7.1 seconds
- **Concurrent Processing**: 30.3 seconds for 3 batches (27 texts)

### Performance Targets

- **Target Throughput**: 1-2 texts/second
- **Target Batch Time**: < 1 second per text
- **Target Aggregation**: < 0.5 seconds per topic

---

## 🎯 Optimization Areas

### 1. Model Loading Optimization

**Current Issue**: Emotion model loads on first use (~10-30 seconds)

**Solution**: Already implemented lazy loading with singleton pattern

```python
# In EmotionAnalyzer - already optimized
class EmotionAnalyzer:
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _load_model(self):
        if self._model is None:
            # Load model only once
            self._model = pipeline(...)
```

**Status**: ✅ Already optimized

---

### 2. Batch Processing Optimization

**Current**: Processing texts sequentially in batches

**Optimization**: Use HuggingFace datasets for batch processing

```python
# Current (sequential)
for text in texts:
    result = analyzer.analyze_emotion(text)

# Optimized (batched)
from transformers import pipeline
from datasets import Dataset

dataset = Dataset.from_dict({"text": texts})
results = emotion_pipeline(dataset, batch_size=32)
```

**Implementation**:
1. Modify `EmotionAnalyzer` to support batch processing
2. Use `pipeline(..., batch_size=32)` for GPU efficiency
3. Process multiple texts in single GPU call

**Expected Improvement**: 2-5x faster for batch processing

---

### 3. Database Query Optimization

**Current**: Individual queries per operation

**Optimization**: Batch queries and use indexes

```python
# Current (individual queries)
for topic_key in topic_keys:
    mentions = session.query(...).filter(...).all()

# Optimized (batch query)
mentions = session.query(...).filter(
    MentionTopic.topic_key.in_(topic_keys)
).all()
```

**Indexes to Verify**:
- `idx_mention_topics_topic` on `mention_topics.topic_key`
- `idx_sentiment_data_created_at` on `sentiment_data.created_at`
- `idx_sentiment_data_processing_status` on `sentiment_data.processing_status`

**Implementation**:
1. Review all database queries
2. Use `IN` clauses for batch operations
3. Verify indexes exist and are used
4. Use `select_related` for joins

**Expected Improvement**: 3-10x faster for aggregation queries

---

### 4. Embedding Generation Optimization

**Current**: One embedding per API call

**Optimization**: Batch embedding generation

```python
# Current
embeddings = []
for text in texts:
    embedding = openai.Embedding.create(input=text)
    embeddings.append(embedding)

# Optimized
embeddings = openai.Embedding.create(input=texts)  # Batch API call
```

**Implementation**:
1. Modify `PresidentialSentimentAnalyzer._get_embedding()` to accept lists
2. Batch multiple texts in single API call
3. Cache embeddings when possible

**Expected Improvement**: 5-10x faster for batch processing

**Note**: OpenAI API supports up to 2048 inputs per batch

---

### 5. Parallel Processing Optimization

**Current**: Parallel Topic + Sentiment, but sequential batches

**Optimization**: True parallel batch processing

```python
# Current
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(process, text) for text in texts]
    results = [f.result() for f in as_completed(futures)]

# Optimized (with batching)
def process_batch(batch):
    # Process entire batch at once
    return process_multiple(batch)

batches = [texts[i:i+32] for i in range(0, len(texts), 32)]
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_batch, batch) for batch in batches]
    results = [item for f in as_completed(futures) for item in f.result()]
```

**Expected Improvement**: 2-4x faster for large batches

---

### 6. Caching Optimization

**Current**: No caching for repeated operations

**Optimization**: Add caching layer

```python
from functools import lru_cache
from cachetools import TTLCache

# Cache topic classifications
@lru_cache(maxsize=1000)
def classify_topic_cached(text_hash: str, embedding_hash: str):
    return classify_topic(text, embedding)

# Cache aggregations (TTL cache)
aggregation_cache = TTLCache(maxsize=100, ttl=300)  # 5 min TTL

def get_aggregation_cached(topic_key: str, time_window: str):
    cache_key = f"{topic_key}:{time_window}"
    if cache_key in aggregation_cache:
        return aggregation_cache[cache_key]
    result = calculate_aggregation(topic_key, time_window)
    aggregation_cache[cache_key] = result
    return result
```

**Implementation**:
1. Cache topic classifications (same text = same topics)
2. Cache aggregations with TTL (5-15 minutes)
3. Cache baseline calculations (30 day TTL)
4. Use Redis for distributed caching (if multiple workers)

**Expected Improvement**: 10-100x faster for repeated queries

---

### 7. Database Connection Pooling

**Current**: New connection per operation

**Optimization**: Connection pooling

```python
# In api/database.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

**Status**: Verify connection pooling is configured

**Expected Improvement**: 2-5x faster for high-concurrency scenarios

---

## 🔧 Implementation Priority

### High Priority (Quick Wins)

1. **Batch Embedding Generation** ⭐
   - Easy to implement
   - Large performance gain
   - Low risk

2. **Database Query Batching** ⭐
   - Easy to implement
   - Good performance gain
   - Low risk

3. **HuggingFace Batch Processing** ⭐
   - Medium effort
   - Good performance gain
   - Addresses GPU warning

### Medium Priority

4. **Caching Layer**
   - Medium effort
   - Very good performance gain
   - Medium risk (cache invalidation)

5. **Parallel Batch Processing**
   - Medium effort
   - Good performance gain
   - Medium risk (complexity)

### Low Priority (Future)

6. **Connection Pooling Tuning**
   - Low effort
   - Moderate gain
   - Low risk

---

## 📝 Optimization Checklist

Before optimizing:

- [ ] Measure current performance (baseline)
- [ ] Identify bottleneck (profiling)
- [ ] Choose optimization strategy
- [ ] Implement optimization
- [ ] Measure improvement
- [ ] Test thoroughly
- [ ] Document changes

---

## 🧪 Performance Testing

### Test Script

```python
import time
from processing.data_processor import DataProcessor

processor = DataProcessor()

# Test single text
start = time.time()
result = processor.get_sentiment("Test text")
single_time = time.time() - start

# Test batch
texts = ["Test text"] * 100
start = time.time()
results = processor.batch_get_sentiment(texts)
batch_time = time.time() - start

print(f"Single: {single_time:.2f}s")
print(f"Batch: {batch_time:.2f}s ({batch_time/100:.3f}s per text)")
print(f"Throughput: {100/batch_time:.2f} texts/second")
```

### Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run operation
processor.batch_get_sentiment(texts)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 slowest functions
```

---

## 📚 Reference

- **DEVELOPER_GUIDE.md** - Code patterns
- **BACKEND_ARCHITECTURE.md** - System architecture
- **Week 6 Test Results** - Current performance baseline

---

**Last Updated**: 2024-12-19





