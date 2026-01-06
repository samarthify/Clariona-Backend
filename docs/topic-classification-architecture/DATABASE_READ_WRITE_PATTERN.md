# Database Read-Write Pattern
## Handling Concurrent Access to sentiment_data Table

**Created**: January 27, 2025  
**Purpose**: Address concerns about reading and writing to the same table during sentiment analysis

---

## 🔍 Current Architecture Pattern

### Current Flow
```
1. READ: Query sentiment_data (raw mentions without sentiment)
   └─> SELECT * FROM sentiment_data WHERE sentiment_label IS NULL

2. PROCESS: Analyze sentiment, topics, emotions
   └─> Run analysis (can take seconds per record)

3. WRITE: Update same sentiment_data records
   └─> UPDATE sentiment_data SET sentiment_label=..., emotion_label=... WHERE entry_id=...
   └─> INSERT INTO mention_topics (mention_id, topic_key, ...)
   └─> INSERT INTO sentiment_embeddings (entry_id, embedding, ...)
```

### The Concern ✅ **VALID**

**Problem**: Reading and writing to the same table simultaneously can cause:

1. **Lock Contention**
   - UPDATE operations lock rows
   - Concurrent reads may wait for locks
   - Can cause deadlocks in worst case

2. **Race Conditions**
   - Multiple workers processing same records
   - Duplicate processing
   - Inconsistent state

3. **Performance Issues**
   - Table-level locks during updates
   - Index maintenance overhead
   - Query slowdowns

4. **Data Consistency**
   - Partial updates if process crashes
   - Need for transaction management

---

## ✅ **Recommended Solutions**

### Solution 1: **Status-Based Processing** (RECOMMENDED)

**Pattern**: Use a status/state column to track processing state

```sql
-- Add processing status column
ALTER TABLE sentiment_data 
ADD COLUMN processing_status VARCHAR(20) DEFAULT 'pending';
-- Values: 'pending', 'processing', 'completed', 'failed'

-- Add index for efficient querying
CREATE INDEX idx_sentiment_data_processing_status 
ON sentiment_data(processing_status) 
WHERE processing_status IN ('pending', 'processing');
```

**Processing Flow**:
```python
# 1. READ: Get records that need processing
records = session.query(SentimentData).filter(
    SentimentData.processing_status == 'pending'
).limit(batch_size).all()

# 2. MARK: Update status to 'processing' (atomic)
for record in records:
    record.processing_status = 'processing'
session.commit()  # Lock these records

# 3. PROCESS: Analyze (no database access during processing)
results = analyze_batch(records)

# 4. WRITE: Update with results
for record, result in zip(records, results):
    record.sentiment_label = result['sentiment_label']
    record.emotion_label = result['emotion_label']
    # ... other fields
    record.processing_status = 'completed'
session.commit()
```

**Benefits**:
- ✅ Prevents duplicate processing
- ✅ Handles failures gracefully
- ✅ Allows retry of failed records
- ✅ Clear processing state

---

### Solution 2: **Separate Processing Queue** (ADVANCED)

**Pattern**: Use a separate table for processing queue

```sql
-- Processing queue table
CREATE TABLE processing_queue (
    id UUID PRIMARY KEY,
    mention_id INTEGER REFERENCES sentiment_data(entry_id),
    status VARCHAR(20) DEFAULT 'queued',
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX idx_processing_queue_status 
ON processing_queue(status) 
WHERE status = 'queued';
```

**Flow**:
1. Insert records into `processing_queue`
2. Workers claim records from queue
3. Process and update `sentiment_data`
4. Mark queue record as completed

**Benefits**:
- ✅ Complete separation of concerns
- ✅ Better monitoring and retry logic
- ✅ Priority-based processing
- ✅ More complex to implement

---

### Solution 3: **Optimistic Locking** (SIMPLE)

**Pattern**: Use version/timestamp to detect conflicts

```sql
-- Add version column
ALTER TABLE sentiment_data 
ADD COLUMN version INTEGER DEFAULT 0;

-- Update with version check
UPDATE sentiment_data 
SET sentiment_label = :sentiment_label,
    version = version + 1
WHERE entry_id = :entry_id 
  AND version = :expected_version;
```

**Flow**:
```python
# 1. READ with version
record = session.query(SentimentData).filter(...).first()
expected_version = record.version

# 2. PROCESS
result = analyze(record.text)

# 3. WRITE with version check
rows_updated = session.query(SentimentData).filter(
    SentimentData.entry_id == record.entry_id,
    SentimentData.version == expected_version
).update({
    'sentiment_label': result['sentiment_label'],
    'version': SentimentData.version + 1
})

if rows_updated == 0:
    # Conflict detected, retry or skip
    logger.warning("Version conflict, skipping update")
```

**Benefits**:
- ✅ Simple to implement
- ✅ Detects conflicts
- ✅ No explicit locking needed
- ⚠️ Requires retry logic

---

## 🎯 **Recommended Approach for New System**

### Hybrid: Status + Batch Processing

**Implementation**:

1. **Add Processing Status Column**
```python
# In migration (already done for other fields)
processing_status = Column(String(20), default='pending', index=True)
processing_started_at = Column(DateTime(timezone=True), nullable=True)
processing_completed_at = Column(DateTime(timezone=True), nullable=True)
processing_error = Column(Text, nullable=True)
```

2. **Processing Pattern**
```python
class SentimentProcessor:
    def process_batch(self, batch_size: int = 100):
        session = SessionLocal()
        try:
            # 1. Claim records (atomic)
            records = session.query(SentimentData).filter(
                SentimentData.processing_status == 'pending',
                SentimentData.sentiment_label.is_(None)  # Not yet processed
            ).limit(batch_size).with_for_update(skip_locked=True).all()
            
            if not records:
                return 0
            
            # 2. Mark as processing
            for record in records:
                record.processing_status = 'processing'
                record.processing_started_at = datetime.now()
            session.commit()
            
            # 3. Process (no DB access)
            results = self.analyze_parallel(records)
            
            # 4. Update results
            for record, result in zip(records, results):
                record.sentiment_label = result['sentiment_label']
                record.emotion_label = result['emotion_label']
                record.emotion_score = result['emotion_score']
                record.influence_weight = result['influence_weight']
                record.processing_status = 'completed'
                record.processing_completed_at = datetime.now()
                
                # Write to related tables
                self._store_topics(record, result['topics'])
                self._store_embedding(record, result['embedding'])
            
            session.commit()
            return len(records)
            
        except Exception as e:
            session.rollback()
            # Mark as failed for retry
            for record in records:
                record.processing_status = 'failed'
                record.processing_error = str(e)
            session.commit()
            raise
        finally:
            session.close()
```

3. **Key Features**:
   - ✅ `WITH FOR UPDATE SKIP LOCKED`: Prevents lock contention
   - ✅ Atomic status updates
   - ✅ Batch processing for efficiency
   - ✅ Error handling with retry capability
   - ✅ Separate writes to related tables

---

## 📊 **Performance Considerations**

### Database-Level Optimizations

1. **Indexes**
```sql
-- For efficient pending record queries
CREATE INDEX idx_sentiment_data_processing 
ON sentiment_data(processing_status, sentiment_label) 
WHERE processing_status = 'pending' AND sentiment_label IS NULL;

-- For time-based queries
CREATE INDEX idx_sentiment_data_processing_time 
ON sentiment_data(processing_started_at) 
WHERE processing_status = 'processing';
```

2. **Connection Pooling**
- Use connection pool (SQLAlchemy default)
- Limit concurrent connections
- Reuse connections efficiently

3. **Batch Sizes**
- Optimal batch size: 50-200 records
- Balance between memory and DB round-trips
- Adjust based on processing time

4. **Transaction Management**
- Keep transactions short
- Commit frequently (every batch)
- Use savepoints for partial rollback

---

## 🔄 **Migration Strategy**

### Phase 1: Add Status Column (Week 2)
- Add `processing_status` column
- Set all existing records to 'completed'
- New records default to 'pending'

### Phase 2: Update Processing Logic (Week 2-3)
- Modify `DataProcessor` to use status-based pattern
- Implement `WITH FOR UPDATE SKIP LOCKED`
- Add error handling

### Phase 3: Monitoring (Week 5)
- Track processing metrics
- Alert on stuck records
- Retry failed records

---

## ✅ **Best Practices**

1. **Always use transactions**
   ```python
   with session.begin():
       # All operations in one transaction
   ```

2. **Use SELECT FOR UPDATE SKIP LOCKED**
   ```python
   records = session.query(Model).filter(...).with_for_update(skip_locked=True).all()
   ```

3. **Keep transactions short**
   - Process outside transaction
   - Only lock during claim/update

4. **Handle failures gracefully**
   - Mark as failed, not delete
   - Allow retry
   - Log errors

5. **Monitor processing**
   - Track pending count
   - Alert on stuck records
   - Monitor processing time

---

## 📝 **Summary**

**Your concern is valid!** Reading and writing to the same table requires careful handling.

**Recommended Solution**: 
- ✅ Use `processing_status` column
- ✅ Use `WITH FOR UPDATE SKIP LOCKED` for claiming records
- ✅ Process in batches
- ✅ Update status atomically
- ✅ Handle errors with retry capability

**This pattern is:**
- ✅ Safe (prevents duplicate processing)
- ✅ Efficient (minimal locking)
- ✅ Scalable (multiple workers)
- ✅ Reliable (handles failures)

---

**Status**: 📋 Ready for Implementation  
**Next Step**: Add `processing_status` column in Week 2 migration







