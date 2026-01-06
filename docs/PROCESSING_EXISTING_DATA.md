# Processing Existing Data with Complete Metrics

This guide explains how to process existing data that already has embeddings and sentiment labels to populate all tables with complete metrics (volume, velocity, sentiment aggregation, metadata, etc.).

## Overview

When you have existing data in the database with embeddings and sentiment labels, you can skip the collection phase and run the processing pipeline to:

1. ✅ Fill in missing fields (emotion, topics, location, etc.)
2. ✅ Create/update issues from mentions
3. ✅ Calculate volume and velocity metrics
4. ✅ Aggregate sentiment data
5. ✅ Extract metadata (keywords, sources, regions)
6. ✅ Generate issue titles
7. ✅ Calculate priority scores and lifecycle states

## How to Use

### API Endpoint

Use the `/agent/test-cycle-no-auth` endpoint with `use_existing_data=true`:

```bash
curl -X POST "http://localhost:8000/agent/test-cycle-no-auth?test_user_id=YOUR_USER_ID&use_existing_data=true"
```

### What Happens

When `use_existing_data=true`:

**Skipped Phases:**
- ❌ Phase 1: Data Collection (skipped)
- ❌ Phase 2: Data Loading (skipped)
- ❌ Phase 3: Deduplication (skipped)

**Processed Phases:**
- ✅ Phase 4: Sentiment Analysis
  - Processes ONLY records that have BOTH embedding AND sentiment (filters in query)
  - Skips OpenAI calls entirely - uses existing embeddings/sentiment
  - Fills in missing fields using local processing:
    - Emotion detection (HuggingFace model - no OpenAI)
    - Topic classification (uses existing embeddings - no OpenAI)
    - Weights (calculated locally - no OpenAI)

- ✅ Phase 5: Location Classification
  - Classifies location for all records

- ✅ Phase 6: Issue Detection
  - Creates new issues from unprocessed mentions
  - Updates existing issues with new mentions
  - **Recalculates all existing issues** to populate:
    - Volume & Velocity (current/previous window, growth rate)
    - Sentiment Aggregation (distribution, weighted score, sentiment index)
    - Metadata (top keywords, sources, regions)
    - Issue titles
    - Priority scores
    - Lifecycle states

## What Gets Calculated

### For Each Mention (Phase 4)
- Emotion detection (if missing)
- Topics classification (if missing)
- Weights (influence_weight, confidence_weight)
- Issue mapping fields (if missing)

### For Each Issue (Phase 6)

**Volume & Velocity:**
- `volume_current_window`: Mentions in last 24 hours
- `volume_previous_window`: Mentions 24-48 hours ago
- `velocity_percent`: Growth rate `((current - previous) / previous) * 100`
- `velocity_score`: Normalized velocity score (0-100)

**Sentiment Aggregation:**
- `sentiment_distribution`: Distribution of positive/negative/neutral
- `weighted_sentiment_score`: Weighted average sentiment (-1.0 to 1.0)
- `sentiment_index`: Converted sentiment score (0-100)
- `emotion_distribution`: Aggregated emotion distribution
- `emotion_adjusted_severity`: Severity adjusted by emotions

**Metadata:**
- `top_keywords`: Top 10 most frequent keywords
- `top_sources`: Top 5 most frequent sources/platforms
- `regions_impacted`: Unique regions from location_label (up to 10)
- `issue_title`: Auto-generated title from mention text

**Priority & Lifecycle:**
- `priority_score`: Calculated priority (0-100)
- `priority_band`: Priority band (critical/high/medium/low)
- `state`: Lifecycle state (emerging/active/escalated/stabilizing/resolved)

## Configuration

### Batch Size Limits

Default limits can be configured in `config/llm_config.json`:

```json
{
  "processing": {
    "limits": {
      "max_records_per_batch": 5000  // Max records processed in Phase 4
    }
  }
}
```

### Volume/Velocity Time Window

Default time window is 24 hours. Can be configured:

```json
{
  "processing": {
    "issue": {
      "volume": {
        "time_window_hours": 24  // Time window for volume calculation
      }
    }
  }
}
```

## Example Usage

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/agent/test-cycle-no-auth",
    params={
        "test_user_id": "your-user-id",
        "use_existing_data": True
    }
)

print(response.json())
```

### cURL (Linux/Mac/Git Bash)

```bash
curl -X POST \
  "http://localhost:8000/agent/test-cycle-no-auth?test_user_id=your-user-id&use_existing_data=true" \
  -H "Content-Type: application/json"
```

### PowerShell (Windows)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/agent/test-cycle-no-auth?test_user_id=your-user-id&use_existing_data=true" -Method POST
```

Or using curl.exe:

```powershell
curl.exe -X POST "http://localhost:8000/agent/test-cycle-no-auth?test_user_id=your-user-id&use_existing_data=true"
```

## Monitoring Progress

Check the log file for detailed progress:

```bash
tail -f logs/automatic_scheduling.log
```

You'll see logs like:
```
[PHASE 1-3: SKIPPED] User: xxx | Mode: Use Existing Data
[PHASE 4: SENTIMENT ANALYSIS START] User: xxx
[PHASE 4: SENTIMENT] Records: 5000 | Use Existing: True
[PHASE 5: LOCATION CLASSIFICATION START] User: xxx
[PHASE 6: ISSUE DETECTION START] User: xxx
[PHASE 6: ISSUE DETECTION END] User: xxx | Status: SUCCESS
```

## Notes

- **OpenAI Calls**: When `use_existing_data=true`, **NO OpenAI calls are made**. The system only processes records that already have both embeddings and sentiment, and uses local processing (HuggingFace for emotions, topic classifier for topics) to fill in missing fields.

- **Record Filtering**: Only records with BOTH embedding AND sentiment are processed. Records missing either are skipped entirely.

- **Processing Time**: Processing existing data is faster than full collection since it skips data collection and uses existing embeddings when available.

- **Recalculation**: All existing issues are automatically recalculated to ensure volume/velocity, sentiment aggregation, and metadata are up-to-date.

- **Incremental Processing**: If you have more than 5000 records, you may need to run multiple times or increase the `max_records_per_batch` limit.

## Troubleshooting

### No records processed
- Check that records exist for the user_id
- Verify `user_id` matches records in database

### Issues not created/updated
- Ensure mentions have topics assigned (Phase 4 must complete)
- Check that mentions have embeddings (required for clustering)

### Volume/velocity showing zeros
- Verify mentions have timestamps (published_at, published_date, date, or created_at)
- Check that time windows contain mentions

### Missing sentiment aggregation
- Ensure mentions have sentiment_label and sentiment_score
- Check that mentions are linked to issues via issue_mentions table
