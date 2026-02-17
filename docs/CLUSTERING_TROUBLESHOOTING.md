# Clustering Troubleshooting Guide

## Problem: No Clusters Forming

### Root Causes Identified

1. **DBSCAN `min_samples` too high (was 50)**
   - DBSCAN requires at least `min_samples` points to form a core cluster
   - With `min_samples=50`, any time window with <50 mentions gets marked as noise
   - **Fixed**: Lowered to `10` (allows smaller clusters to form)

2. **Double filtering by `min_cluster_size` (was 50)**
   - Even if DBSCAN creates clusters, they're filtered again by `min_cluster_size`
   - **Fixed**: Lowered to `10` (matches DBSCAN min_samples)

3. **DBSCAN `eps` too strict (was 0.25)**
   - For cosine distance, `eps=0.25` means similarity >= 0.75 (1 - 0.25)
   - This is quite strict for high-dimensional embeddings
   - **Fixed**: Increased to `0.3` (allows similarity >= 0.70)

4. **Time window splitting**
   - Mentions are grouped into 1-week windows (168 hours)
   - If mentions span multiple weeks, they're split into separate groups
   - Each group needs to independently meet `min_samples` threshold
   - **Recommendation**: Consider increasing time window or disabling time grouping for initial testing

5. **Promotion mode enabled**
   - When `promotion.enabled=True`, clusters are persisted but NOT immediately turned into issues
   - You need to run `promote_clusters_for_topic()` separately to create issues
   - **Check**: Are you looking for clusters in `processing_clusters` table or issues in `topic_issues`?

## Current Configuration (After Fix)

```json
{
  "processing": {
    "issue": {
      "clustering": {
        "similarity_threshold": 0.5,
        "min_cluster_size": 10,  // Lowered from 50
        "time_window_hours": 168
      },
      "dbscan": {
        "enabled": true,
        "eps": 0.3,  // Increased from 0.25 (allows similarity >= 0.70)
        "min_samples": 10  // Lowered from 50
      }
    }
  }
}
```

## Recommendations for Further Tuning

### If Still No Clusters:

1. **Lower `min_samples` further** (try 5-8)
   - Allows even smaller clusters to form
   - Risk: May create too many small, noisy clusters

2. **Increase `eps`** (try 0.35-0.4)
   - Allows looser similarity (similarity >= 0.60-0.65)
   - Risk: May merge unrelated mentions

3. **Disable time window grouping** (set `time_window_hours: 0`)
   - Clusters across all time periods
   - Risk: May create clusters spanning very long time periods

4. **Check your data**:
   - How many mentions per topic?
   - How many mentions per week?
   - Do mentions have valid embeddings (not zero vectors)?

### If Too Many Small Clusters:

1. **Increase `min_samples`** (try 15-20)
2. **Increase `min_cluster_size`** (try 15-20)
3. **Decrease `eps`** (try 0.25-0.28)

### If Clusters Too Loose (unrelated mentions):

1. **Decrease `eps`** (try 0.2-0.25)
2. **Increase `similarity_threshold`** (try 0.6-0.7)

## Testing Your Configuration

Run this to see what's happening:

```python
from src.processing.issue_clustering_service import IssueClusteringService
from src.processing.issue_detection_engine import IssueDetectionEngine

# Test clustering
clustering = IssueClusteringService()
mentions = [...]  # Your mentions
clusters = clustering.cluster_mentions(mentions, topic_key="your_topic")
print(f"Found {len(clusters)} clusters")
for i, cluster in enumerate(clusters):
    print(f"Cluster {i}: {len(cluster)} mentions")
```

## Understanding DBSCAN Parameters

- **`eps`**: Maximum distance (cosine) between two points to be considered neighbors
  - Lower = tighter clusters (higher similarity required)
  - Higher = looser clusters (lower similarity allowed)
  - For cosine: `eps=0.3` means similarity >= 0.70

- **`min_samples`**: Minimum number of points in a neighborhood to form a core cluster
  - Lower = allows smaller clusters
  - Higher = requires larger clusters
  - Points not meeting this are marked as noise (-1)

- **`min_cluster_size`**: Final filter after DBSCAN
  - Clusters smaller than this are discarded
  - Should be <= `min_samples` (otherwise redundant)

## Debugging Steps

1. **Check mention count per topic**:
   ```sql
   SELECT topic_key, COUNT(*) as mention_count
   FROM sentiment_data
   GROUP BY topic_key
   ORDER BY mention_count DESC;
   ```

2. **Check mention count per week**:
   ```sql
   SELECT 
     topic_key,
     DATE_TRUNC('week', run_timestamp) as week,
     COUNT(*) as mention_count
   FROM sentiment_data
   GROUP BY topic_key, week
   ORDER BY week DESC, mention_count DESC;
   ```

3. **Check embeddings**:
   ```sql
   SELECT 
     COUNT(*) as total,
     COUNT(CASE WHEN embedding IS NULL THEN 1 END) as null_embeddings,
     COUNT(CASE WHEN embedding = '[]'::jsonb THEN 1 END) as empty_embeddings
   FROM sentiment_embedding;
   ```

4. **Check existing clusters**:
   ```sql
   SELECT 
     topic_key,
     status,
     COUNT(*) as cluster_count,
     AVG(size) as avg_size,
     MIN(size) as min_size,
     MAX(size) as max_size
   FROM processing_clusters
   GROUP BY topic_key, status;
   ```
