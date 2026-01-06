# Guide: Increasing Throughput

**Last Updated**: 2024-12-19  
**Purpose**: Guide for increasing system throughput (texts processed per second)

---

## 📊 Current Throughput

### Baseline (from Week 6 tests)

- **Current Throughput**: 0.44 texts/second
- **Batch Processing**: ~2.27 seconds per text
- **Target Throughput**: 1-2 texts/second (2-4x improvement)

---

## 🚀 Throughput Improvement Strategies

### 1. Batch API Calls

**Current**: One API call per text

**Optimization**: Batch multiple texts in single API call

```python
# Current (0.44 texts/second)
for text in texts:
    embedding = openai.Embedding.create(input=text)
    sentiment = openai.ChatCompletion.create(...)

# Optimized (target: 2+ texts/second)
# Batch embeddings (up to 2048 inputs)
embeddings = openai.Embedding.create(input=texts[:100])

# Batch sentiment (if API supports)
# Or use parallel requests
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(analyze_sentiment, text) for text in texts]
    results = [f.result() for f in as_completed(futures)]
```

**Expected Improvement**: 3-5x throughput

**Implementation**:
1. Modify `PresidentialSentimentAnalyzer` to batch embeddings
2. Use `ThreadPoolExecutor` for parallel sentiment analysis
3. Batch size: 50-100 texts per batch

---

### 2. GPU Batch Processing

**Current**: Sequential GPU processing (causes warning)

**Optimization**: Use HuggingFace datasets for batch processing

```python
# Current (sequential - slow)
for text in texts:
    emotions = emotion_pipeline(text)

# Optimized (batched - fast)
from datasets import Dataset

dataset = Dataset.from_dict({"text": texts})
emotions = emotion_pipeline(dataset, batch_size=32)
```

**Expected Improvement**: 5-10x for emotion detection

**Implementation**:
1. Modify `EmotionAnalyzer.analyze_emotion()` to accept lists
2. Use `pipeline(..., batch_size=32)` for GPU batches
3. Process 32 texts at once on GPU

---

### 3. Parallel Worker Optimization

**Current**: Limited parallel workers

**Optimization**: Increase workers and optimize distribution

```python
# Current
max_workers = 5

# Optimized
max_workers = min(20, len(texts))  # Scale with workload

# Use process pool for CPU-bound tasks
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(process_text, texts))
```

**Expected Improvement**: 2-4x throughput

**Implementation**:
1. Increase `max_workers` in `batch_get_sentiment()`
2. Use `ProcessPoolExecutor` for CPU-bound tasks
3. Use `ThreadPoolExecutor` for I/O-bound tasks (API calls)

---

### 4. Database Write Batching

**Current**: Individual inserts

**Optimization**: Batch inserts

```python
# Current (slow)
for result in results:
    session.add(SentimentData(...))
    session.commit()

# Optimized (fast)
session.bulk_insert_mappings(SentimentData, results)
session.commit()
```

**Expected Improvement**: 5-10x for database writes

**Implementation**:
1. Use `bulk_insert_mappings()` for batch inserts
2. Batch size: 100-500 records per commit
3. Use `bulk_update_mappings()` for updates

---

### 5. Async Processing

**Current**: Synchronous processing

**Optimization**: Async/await for I/O operations

```python
import asyncio
import aiohttp

async def process_text_async(text: str):
    async with aiohttp.ClientSession() as session:
        # Async API calls
        embedding = await get_embedding_async(session, text)
        sentiment = await get_sentiment_async(session, text)
        return combine_results(embedding, sentiment)

async def process_batch_async(texts: List[str]):
    tasks = [process_text_async(text) for text in texts]
    return await asyncio.gather(*tasks)
```

**Expected Improvement**: 3-5x throughput for I/O-bound operations

**Implementation**:
1. Convert API calls to async
2. Use `aiohttp` for async HTTP requests
3. Use `asyncio.gather()` for parallel async operations

---

### 6. Preprocessing Pipeline

**Current**: Process everything on-demand

**Optimization**: Preprocess and cache

```python
# Preprocess common operations
def preprocess_texts(texts: List[str]) -> List[Dict]:
    """Preprocess texts in batch."""
    # Batch tokenization
    # Batch normalization
    # Cache results
    return preprocessed

# Then process preprocessed data
def process_preprocessed(preprocessed: List[Dict]):
    """Process preprocessed data."""
    # Faster processing
    pass
```

**Expected Improvement**: 1.5-2x throughput

---

### 7. Queue-Based Processing

**Current**: Synchronous batch processing

**Optimization**: Queue-based async processing

```python
from queue import Queue
from threading import Thread

class ProcessingQueue:
    def __init__(self, num_workers=10):
        self.queue = Queue()
        self.workers = [Thread(target=self._worker) for _ in range(num_workers)]
        for w in self.workers:
            w.start()
    
    def _worker(self):
        while True:
            text = self.queue.get()
            if text is None:
                break
            process_text(text)
            self.queue.task_done()
    
    def add(self, text: str):
        self.queue.put(text)
```

**Expected Improvement**: Better resource utilization, 2-3x throughput

---

## 🎯 Recommended Implementation Order

### Phase 1: Quick Wins (1-2 days)

1. **Batch Embedding Generation** ⭐⭐⭐
   - Easy, high impact
   - Expected: 3-5x improvement

2. **Database Batch Inserts** ⭐⭐
   - Easy, medium impact
   - Expected: 5-10x for writes

3. **Increase Worker Count** ⭐
   - Very easy, low-medium impact
   - Expected: 1.5-2x improvement

### Phase 2: Medium Effort (3-5 days)

4. **GPU Batch Processing** ⭐⭐⭐
   - Medium effort, high impact
   - Expected: 5-10x for emotion detection

5. **Parallel API Calls** ⭐⭐
   - Medium effort, medium-high impact
   - Expected: 2-4x improvement

### Phase 3: Advanced (1-2 weeks)

6. **Async Processing** ⭐⭐⭐
   - High effort, high impact
   - Expected: 3-5x improvement

7. **Queue-Based Processing** ⭐⭐
   - High effort, medium-high impact
   - Expected: 2-3x improvement

---

## 📊 Expected Results

### Current State
- Throughput: 0.44 texts/second
- Batch time: 2.27 seconds/text

### After Phase 1
- Throughput: 1.5-2 texts/second (3-4x)
- Batch time: 0.5-0.7 seconds/text

### After Phase 2
- Throughput: 3-5 texts/second (7-10x)
- Batch time: 0.2-0.3 seconds/text

### After Phase 3
- Throughput: 5-10 texts/second (10-20x)
- Batch time: 0.1-0.2 seconds/text

---

## 🔍 Monitoring Throughput

### Metrics to Track

```python
class ThroughputMonitor:
    def __init__(self):
        self.start_time = None
        self.processed = 0
    
    def start(self):
        self.start_time = time.time()
        self.processed = 0
    
    def increment(self):
        self.processed += 1
    
    def get_throughput(self):
        if self.start_time is None:
            return 0
        elapsed = time.time() - self.start_time
        return self.processed / elapsed if elapsed > 0 else 0
    
    def log_stats(self):
        throughput = self.get_throughput()
        logger.info(f"Processed: {self.processed}, Throughput: {throughput:.2f} texts/second")
```

### Usage

```python
monitor = ThroughputMonitor()
monitor.start()

for text in texts:
    process_text(text)
    monitor.increment()

monitor.log_stats()
```

---

## ⚠️ Considerations

### Rate Limits
- OpenAI API has rate limits (TPM, RPM)
- Monitor rate limit usage
- Implement backoff/retry logic

### Memory Usage
- Batch processing uses more memory
- Monitor memory usage
- Adjust batch sizes based on available memory

### Database Load
- Batch inserts increase database load
- Monitor database connections
- Use connection pooling

### Error Handling
- Batch processing: one failure affects batch
- Implement partial failure handling
- Retry failed items individually

---

## 📝 Implementation Checklist

- [ ] Measure current throughput (baseline)
- [ ] Identify bottleneck (profiling)
- [ ] Choose optimization strategy
- [ ] Implement optimization
- [ ] Test with real data
- [ ] Measure improvement
- [ ] Monitor for errors
- [ ] Document changes

---

## 📚 Reference

- **PERFORMANCE_OPTIMIZATION_GUIDE.md** - General performance tips
- **DEVELOPER_GUIDE.md** - Code patterns
- **Week 6 Test Results** - Current baseline

---

**Last Updated**: 2024-12-19





