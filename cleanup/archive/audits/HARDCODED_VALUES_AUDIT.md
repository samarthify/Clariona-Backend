# Hardcoded Values Audit

**Created**: 2025-12-27  
**Purpose**: Complete inventory of all hardcoded values that should be moved to configuration  
**Status**: Phase 1, Step 1.3 - In Progress  
**Total Instances Found**: 200+ hardcoded values

---

## 📋 Categories

1. **Paths** - File system paths
2. **Timeouts** - Timeout values in seconds
3. **Thresholds** - Similarity, confidence, score thresholds
4. **Sizes** - Batch sizes, limits, counts
5. **String Lengths** - Database column string lengths
6. **URLs & Origins** - CORS origins, API URLs
7. **Delays** - Sleep delays, wait times
8. **Rate Limits** - API rate limits
9. **Other** - Miscellaneous constants

---

## 1. PATHS

### Hardcoded Path Strings

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 63 | `'logs/agent.log'` | Log file path | `paths.logs_agent` |
| 94 | `'logs/automatic_scheduling.log'` | Scheduling log | `paths.logs_scheduling` |
| 160 | `"config/agent_config.json"` | Config file path | `paths.config_agent` |
| 296 | `'logs/openai_calls.csv'` | OpenAI logging | `paths.logs_openai` |
| 761 | `"logs/openai_calls.csv"` | Default log path | `paths.logs_openai` |
| 951 | `'logs' / 'collectors'` | Collector logs dir | `paths.logs_collectors` |
| ~2300+ | `'data' / 'raw'` | Raw data directory | `paths.data_raw` |

#### `src/api/service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 700 | `"logs/automatic_scheduling.log"` | Log file reference | `paths.logs_scheduling` |
| 753 | `"logs/automatic_scheduling.log"` | Log file reference | `paths.logs_scheduling` |

#### `src/api/presidential_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 47 | `Path("data/processed")` | Processed data dir | `paths.data_processed` |

#### `src/processing/topic_classifier.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 42 | `"config/topic_embeddings.json"` | Embeddings config | `paths.config_topic_embeddings` |

#### `src/processing/topic_embedding_generator.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 161 | `"config/topic_embeddings.json"` | Embeddings config | `paths.config_topic_embeddings` |

#### `src/utils/file_rotation.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 94 | `"data/processed/latest.csv"` | Example path | `paths.data_processed_latest` |

### Base Path Calculations

Multiple files calculate base path differently:
- `src/agent/core.py` line 170: `Path(__file__).parent.parent.parent`
- `src/collectors/configurable_collector.py` line 38: `Path(__file__).parent.parent.parent`
- `src/utils/file_rotation.py` line 24: `Path(__file__).parent.parent.parent`

**Issue**: Duplicate base_path calculations  
**Solution**: Use centralized PathManager

---

## 2. TIMEOUTS

### Timeout Values (seconds)

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 193 | `1000` | Collector timeout (default) | `processing.timeouts.collector_timeout_seconds` |
| 195 | `180` | Apify timeout (default) | `processing.timeouts.apify_timeout_seconds` |
| 196 | `180` | Apify wait (default) | `processing.timeouts.apify_wait_seconds` |
| 197 | `300` | Lock max age (default) | `processing.timeouts.lock_max_age_seconds` |
| 353 | `10` | Scheduler thread join timeout | `processing.timeouts.scheduler_join_timeout` |
| 360 | `10` | Scheduler thread join timeout | `processing.timeouts.scheduler_join_timeout` |
| 374 | `30` | Scheduler timeout | `processing.timeouts.scheduler_timeout` |
| 1694 | `120` | HTTP request timeout | `processing.timeouts.http_request_timeout` |

#### `src/api/database.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 30 | `3600` | Pool recycle | `database.pool_recycle_seconds` |
| 31 | `30` | Pool size | `database.pool_size` |
| 32 | `20` | Max overflow | `database.max_overflow` |
| 32 | `60` | Pool timeout | `database.pool_timeout_seconds` |

#### `src/collectors/configurable_collector.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 41 | `1800` | Collector timeout (30 min) | `processing.timeouts.collector_timeout_seconds` |
| 42 | `7200` | Overall timeout (2 hours) | `processing.timeouts.overall_timeout_seconds` |

#### `src/collectors/collect_tiktok_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 270 | `'180'` | Apify timeout (env default) | `processing.timeouts.apify_timeout_seconds` |
| 438 | `10` | HTTP request timeout | `processing.timeouts.http_request_timeout` |

#### `src/collectors/rss_feed_validator.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 58 | `10` | Feed validation timeout | `collectors.rss.timeout_seconds` |

#### `src/collectors/rss_feed_health_monitor.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 133 | `10` | Feed validation timeout | `collectors.rss.timeout_seconds` |

#### `src/collectors/collect_rss_nigerian_qatar_indian.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 45 | `30` | Feed timeout | `collectors.rss.feed_timeout_seconds` |
| 484 | `600` | Overall timeout (10 min) | `collectors.rss.overall_timeout_seconds` |
| 503 | `5` | Extra buffer time | `collectors.rss.buffer_seconds` |

#### `src/collectors/collect_rss.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 41 | `15` | Feed timeout | `collectors.rss.feed_timeout_seconds` |

#### `src/collectors/rss_ssl_handler.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 144 | `10` | SSL fetch timeout | `collectors.rss.ssl_timeout_seconds` |
| 192 | `10` | Auto SSL timeout | `collectors.rss.ssl_timeout_seconds` |
| 220 | `10` | Socket timeout | `collectors.rss.socket_timeout_seconds` |

#### `src/collectors/collect_radio_stations.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 185 | `15` | HTTP request timeout | `collectors.radio.timeout_seconds` |

#### `src/collectors/collect_radio_hybrid.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 601 | `15` | HTTP request timeout | `collectors.radio.timeout_seconds` |
| 634 | `15` | HTTP request timeout | `collectors.radio.timeout_seconds` |
| 656 | `15` | HTTP request timeout | `collectors.radio.timeout_seconds` |

#### `src/collectors/collect_radio_gnews.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 201 | `30` | HTTP request timeout | `collectors.radio.gnews_timeout_seconds` |
| 316 | `30` | HTTP request timeout | `collectors.radio.gnews_timeout_seconds` |

#### `src/utils/notification_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 53 | `60` | HTTP request timeout | `api.timeouts.http_request_timeout` |

---

## 3. THRESHOLDS

### Similarity & Confidence Thresholds

#### `src/utils/deduplication_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 19 | `0.85` | Similarity threshold | `deduplication.similarity_threshold` |

#### `src/processing/topic_classifier.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 34 | `0.2` | Min score threshold | `processing.topic.min_score_threshold` |
| 208 | `0.85` | Confidence threshold | `processing.topic.confidence_threshold` |
| 263 | `0.3` | Keyword score threshold | `processing.topic.keyword_score_threshold` |
| 263 | `0.5` | Embedding score threshold | `processing.topic.embedding_score_threshold` |

#### `src/utils/notification_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 126 | `0.2` | Positive sentiment threshold | `processing.sentiment.positive_threshold` |
| 127 | `-0.2` | Negative sentiment threshold | `processing.sentiment.negative_threshold` |
| 156 | `0.2` | Positive sentiment threshold | `processing.sentiment.positive_threshold` |
| 158 | `-0.2` | Negative sentiment threshold | `processing.sentiment.negative_threshold` |
| 235 | `0.2` | Positive sentiment threshold | `processing.sentiment.positive_threshold` |
| 235 | `-0.2` | Negative sentiment threshold | `processing.sentiment.negative_threshold` |
| 382 | `0.2` | Positive sentiment threshold | `processing.sentiment.positive_threshold` |
| 383 | `-0.2` | Negative sentiment threshold | `processing.sentiment.negative_threshold` |
| 420 | `0.5` | Count decrease threshold | `processing.comparison.count_decrease_threshold` |
| 510 | `0.2` | Positive sentiment threshold | `processing.sentiment.positive_threshold` |
| 510 | `-0.2` | Negative sentiment threshold | `processing.sentiment.negative_threshold` |

#### `src/processing/presidential_sentiment_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 95 | `0.2` | Positive threshold | `processing.sentiment.positive_threshold` |
| 95 | `-0.2` | Negative threshold | `processing.sentiment.negative_threshold` |
| 487 | `-0.2` | Negative threshold | `processing.sentiment.negative_threshold` |

#### `src/processing/governance_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 188 | `0.85` | Confidence threshold | `processing.governance.confidence_threshold` |
| 359 | `0.5` | Default confidence | `processing.governance.default_confidence` |
| 494 | `0.5` | Placeholder score | `processing.governance.placeholder_score` |
| 495 | `0.5` | Governance relevance | `processing.governance.default_relevance` |
| 495 | `0.1` | Non-governance relevance | `processing.governance.non_governance_relevance` |
| 524 | `0.5` | Placeholder score | `processing.governance.placeholder_score` |

#### `src/processing/data_processor.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 320 | `0.85` | Similarity threshold | `deduplication.similarity_threshold` |
| 912 | `0.5` | Length ratio threshold | `deduplication.length_ratio_threshold` |

#### `src/api/presidential_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 497 | `0.85` | Similarity threshold | `deduplication.similarity_threshold` |

#### `src/collectors/rss_feed_health_monitor.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 29 | `0.5` | Fair health score | `collectors.rss.health_score_fair` |
| 112 | `0.2` | Error penalty | `collectors.rss.error_penalty` |
| 114 | `0.2` | Error penalty | `collectors.rss.error_penalty` |
| 295 | `0.5` | Min health score | `collectors.rss.min_health_score` |

#### `src/collectors/rss_feed_validator.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 60 | `0.5` | Min health score | `collectors.rss.min_health_score` |
| 76 | `0.5` | Min health score (default) | `collectors.rss.min_health_score` |
| 127 | `0.5` | Valid entries ratio | `collectors.rss.min_valid_entries_ratio` |

---

## 4. SIZES (Batch Sizes, Limits, Counts)

### Batch Sizes

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 191 | `50` | Sentiment batch size (default) | `processing.parallel.sentiment_batch_size` |
| 192 | `100` | Location batch size (default) | `processing.parallel.location_batch_size` |
| 189 | `4` | Max sentiment workers (default) | `processing.parallel.max_sentiment_workers` |
| 190 | `2` | Max location workers (default) | `processing.parallel.max_location_workers` |
| 1211 | `100` | Location batch size (default) | `processing.parallel.location_batch_size` |
| 2187 | `100` | Location batch size (default) | `processing.parallel.location_batch_size` |
| 2625 | `self.sentiment_batch_size` | Used from config | Already configurable |
| 2837 | `self.location_batch_size` | Used from config | Already configurable |
| ~2616 | `10000` | Max records per query | `processing.limits.max_records_per_batch` |
| ~2828 | `10000` | Max records per query | `processing.limits.max_records_per_batch` |

#### `src/processing/data_processor.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 894 | `100` | Progress batch size | `processing.batch_sizes.progress_log_interval` |
| 897 | `batch_size` | Uses variable | Already configurable |

#### `src/api/presidential_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 662 | `50` | Batch size | `processing.batch_sizes.presidential_batch_size` |

#### `src/api/admin.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 64 | `100` | Default limit | `api.pagination.default_limit` |
| 192 | `100` | Default limit | `api.pagination.default_limit` |

### Collector Limits

#### `src/collectors/collect_twitter_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 30 | `100` | Max items (default) | `collectors.twitter.max_items_default` |
| 336 | `100` | Max items (default) | `collectors.twitter.max_items_default` |

#### `src/collectors/collect_instagram_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 108 | `100` | Max results (default) | `collectors.instagram.max_results_default` |

#### `src/collectors/collect_tiktok_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 126 | `100` | Max results (default) | `collectors.tiktok.max_results_default` |

#### `src/collectors/incremental_collector.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 106 | `100` | Max items (default) | `collectors.incremental.max_items_default` |

#### `src/collectors/collect_youtube_api.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 236 | `1000` | Max results | `collectors.youtube.max_results` |
| 318 | `1000` | Max results | `collectors.youtube.max_results` |
| 449 | `1000` | Max results | `collectors.youtube.max_results` |
| 454 | `1000` | Max results | `collectors.youtube.max_results` |

#### `src/collectors/collect_news_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 65 | `1000` | Max items (default) | `collectors.news.max_items_default` |

### Token Estimates

#### `src/processing/presidential_sentiment_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 110 | `1000` | Estimated tokens | `processing.tokens.estimated_per_sentiment` |

#### `src/processing/issue_classifier.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 184 | `800` | Estimated tokens | `processing.tokens.estimated_per_issue` |
| 380 | `800` | Estimated tokens | `processing.tokens.estimated_per_issue` |

#### `src/processing/governance_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 234 | `1200` | Estimated tokens | `processing.tokens.estimated_per_governance` |
| 378 | `2200` | Estimated tokens | `processing.tokens.estimated_per_governance_combined` |

#### `src/processing/topic_embedding_generator.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 142 | `2200` | Estimated tokens | `processing.tokens.estimated_per_embedding` |

---

## 5. STRING LENGTHS (Database Columns)

### `src/api/models.py`

All string length constraints:

| Line | Value | Column | Suggested Config Key |
|------|-------|--------|---------------------|
| 16 | `100` | username | `models.string_lengths.medium` |
| 18 | `50` | role | `models.string_lengths.short` |
| 19 | `50` | ministry | `models.string_lengths.short` |
| 20 | `200` | name | `models.string_lengths.long` |
| 96 | `50` | ministry_hint | `models.string_lengths.short` |
| 217 | `50` | embedding_model | `models.string_lengths.short` |
| 231 | `100` | topic_key | `models.string_lengths.medium` |
| 232 | `200` | topic_name | `models.string_lengths.long` |
| 234 | `50` | category | `models.string_lengths.short` |
| 249 | `100` | topic_key | `models.string_lengths.medium` |
| 250 | `200` | issue_slug | `models.string_lengths.long` |
| 251 | `500` | issue_label | `models.string_lengths.very_long` |
| 276 | `100` | topic_key | `models.string_lengths.medium` |
| 284 | `200` | issue_slug | `models.string_lengths.long` |
| 285 | `500` | issue_label | `models.string_lengths.very_long` |
| 307 | `100` | owner_key | `models.string_lengths.medium` |
| 308 | `200` | owner_name | `models.string_lengths.long` |
| 309 | `50` | owner_type | `models.string_lengths.short` |

**Suggested Constants**:
- `short = 50`
- `medium = 100`
- `long = 200`
- `very_long = 500`

---

## 6. URLS & ORIGINS

### CORS Origins

#### `src/api/service.py`

| Lines | Values | Current Usage | Suggested Config Key |
|-------|--------|---------------|---------------------|
| 47-54 | `["http://localhost:3000", "http://13.202.48.110:3000", "http://localhost:3001", "http://13.202.48.110:3001", "https://*.railway.app", "https://*.up.railway.app"]` | CORS origins | `api.cors_origins` |

---

## 7. DELAYS (Sleep/Wait Times)

### Sleep Delays (seconds)

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 377 | `1` | Sleep on retry | `processing.delays.retry_sleep_seconds` |
| 418 | `300` | Sleep when no active users (5 min) | `processing.delays.no_users_sleep_seconds` |
| 484 | `1` | Sleep on retry | `processing.delays.retry_sleep_seconds` |
| 503 | `60` | Sleep on error (1 min) | `processing.delays.error_sleep_seconds` |

#### `src/collectors/collect_tiktok_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 283 | `3` | Delay between runs | `collectors.tiktok.delay_between_runs_seconds` |
| 392 | `5` | Delay between actors | `collectors.tiktok.delay_between_actors_seconds` |

#### `src/collectors/collect_youtube_api.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 310 | `0.1` | Rate limit delay | `collectors.youtube.rate_limit_delay_seconds` |
| 384 | `0.1` | Rate limit delay | `collectors.youtube.rate_limit_delay_seconds` |
| 491 | `1` | Delay | `collectors.youtube.delay_seconds` |

#### `src/collectors/collect_news_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 119 | `2` | Delay between query runs | `collectors.news.delay_between_queries_seconds` |
| 242 | `5` | Delay between actors | `collectors.news.delay_between_actors_seconds` |

#### `src/collectors/collect_social_searcher_api.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 217 | `2` | Delay | `collectors.social_searcher.delay_seconds` |

#### `src/collectors/collect_rss_nigerian_qatar_indian.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 515 | `1` | Delay | `collectors.rss.delay_seconds` |

#### `src/collectors/collect_rss.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 416 | `1` | Delay | `collectors.rss.delay_seconds` |

#### `src/collectors/collect_radio_stations.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 192 | `2` | Wait before retry | `collectors.radio.retry_wait_seconds` |

#### `src/collectors/collect_radio_hybrid.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 608 | `2` | Wait before retry | `collectors.radio.retry_wait_seconds` |

#### `src/collectors/collect_radio_gnews.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 263 | `1` | Delay | `collectors.radio.gnews_delay_seconds` |
| 378 | `1` | Delay | `collectors.radio.gnews_delay_seconds` |

#### `src/processing/presidential_sentiment_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 180 | `1.0` | Rate limit delay | `processing.delays.rate_limit_delay_seconds` |

#### `src/processing/issue_classifier.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 235 | `1.0` | Rate limit delay | `processing.delays.rate_limit_delay_seconds` |
| 432 | `1.0` | Rate limit delay | `processing.delays.rate_limit_delay_seconds` |

#### `src/processing/governance_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 286 | `1.0` | Rate limit delay | `processing.delays.rate_limit_delay_seconds` |

#### `src/utils/scheduled_reports.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 164 | `5` | Thread join timeout | `utils.scheduler.thread_join_timeout_seconds` |
| 173 | `1` | Sleep | `utils.scheduler.sleep_seconds` |
| 199 | `1` | Sleep | `utils.scheduler.sleep_seconds` |

#### `src/utils/openai_rate_limiter.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 113 | `1.0` | Sleep increment | `utils.rate_limiter.sleep_increment_seconds` |

#### `src/utils/multi_model_rate_limiter.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 86 | `1.0` | Sleep increment | `utils.rate_limiter.sleep_increment_seconds` |

---

## 8. RATE LIMITS

### API Rate Limits

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 758 | `{"twitter": 100, "news": 50}` | Rate limits (default) | `processing.rate_limits` |

---

## 9. OTHER CONSTANTS

### Default Values

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 188 | `3` | Max collector workers (default) | `processing.parallel.max_collector_workers` |

### HTTP Status Codes

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 1698 | `200`, `300` | HTTP success range | `api.http.success_status_range` |

### Temperature Values (LLM)

#### `src/processing/sentiment_analyzer_huggingface.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 212 | `0.2` | LLM temperature | `processing.llm.temperature` |

#### `src/processing/sentiment_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 193 | `0.2` | LLM temperature | `processing.llm.temperature` |

### Default Scores

#### `src/processing/sentiment_analyzer_huggingface.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 107 | `0.5` | Default neutral score | `processing.sentiment.default_neutral_score` |
| 163 | `0.5` | Default neutral score | `processing.sentiment.default_neutral_score` |
| 255 | `0.5` | Default neutral score | `processing.sentiment.default_neutral_score` |
| 311 | `0.5` | Default neutral score | `processing.sentiment.default_neutral_score` |
| 320 | `0.5` | Default neutral score | `processing.sentiment.default_neutral_score` |
| 396 | `0.5` | Default neutral score | `processing.sentiment.default_neutral_score` |

#### `src/processing/sentiment_analyzer.py`

Multiple instances of `0.5` as default neutral score.

---

## 10. LLM CONFIGURATION VALUES

### LLM Model Defaults

#### `config/llm_config.json`

| Value | Current Usage | Suggested Config Key |
|-------|---------------|---------------------|
| `0.7` | Default temperature | `processing.llm.temperature` |
| `2000` | Default max_tokens | `processing.llm.max_tokens` |
| `"http://localhost:3000"` | HTTP-Referer header | `api.http_referer` |
| `"Local Development"` | X-Title header | `api.http_title` |

#### `src/processing/sentiment_analyzer_huggingface.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 211 | `100` | Max tokens for LLM call | `processing.llm.max_tokens_sentiment` |

#### `src/processing/sentiment_analyzer.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 192 | `100` | Max tokens for LLM call | `processing.llm.max_tokens_sentiment` |

#### `src/agent/llm_providers.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 72 | `0.7` | Default temperature | `processing.llm.temperature` |
| 157 | `0.7` | Default temperature | `processing.llm.temperature` |
| 158 | `2000` | Default max_tokens | `processing.llm.max_tokens` |

---

## 11. COLLECTOR LIMITS & ARRAY SLICING

### Array Slicing Limits (First N Items)

#### `src/collectors/collect_facebook_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 376 | `[:10]` | Limit to first 10 posts | `collectors.facebook.max_posts_per_page` |
| 440 | `[:10]` | Limit to first 10 posts | `collectors.facebook.max_posts_per_page` |
| 538 | `[:10]` | Limit to first 10 posts | `collectors.facebook.max_posts_per_page` |

#### `src/collectors/collect_radio_hybrid.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 373 | `[:5]` | Limit to 5 pagination pages | `collectors.radio.max_pagination_pages` |
| 571 | `[:25]` | Limit to 25 articles per page | `collectors.radio.max_articles_per_page` |
| 699 | `[:20]` | Limit to 20 entries per feed | `collectors.radio.max_feed_entries` |

#### `src/collectors/collect_radio_stations.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 290 | `[:25]` | Limit to 25 articles per station | `collectors.radio.max_articles_per_station` |

---

## 12. INCREMENTAL COLLECTOR CONFIGURATION

### Lookback Days & Overlap Hours

#### `src/collectors/incremental_collector.py`

| Line | Value | Source Type | Current Usage | Suggested Config Key |
|------|-------|-------------|---------------|---------------------|
| 29 | `3` | Twitter | Default lookback days | `collectors.incremental.twitter.default_lookback_days` |
| 30 | `14` | Twitter | Max lookback days | `collectors.incremental.twitter.max_lookback_days` |
| 31 | `2` | Twitter | Overlap hours | `collectors.incremental.twitter.overlap_hours` |
| 34 | `7` | News | Default lookback days | `collectors.incremental.news.default_lookback_days` |
| 35 | `30` | News | Max lookback days | `collectors.incremental.news.max_lookback_days` |
| 36 | `6` | News | Overlap hours | `collectors.incremental.news.overlap_hours` |
| 39 | `3` | Facebook | Default lookback days | `collectors.incremental.facebook.default_lookback_days` |
| 40 | `14` | Facebook | Max lookback days | `collectors.incremental.facebook.max_lookback_days` |
| 41 | `2` | Facebook | Overlap hours | `collectors.incremental.facebook.overlap_hours` |
| 44 | `3` | Instagram | Default lookback days | `collectors.incremental.instagram.default_lookback_days` |
| 45 | `14` | Instagram | Max lookback days | `collectors.incremental.instagram.max_lookback_days` |
| 46 | `2` | Instagram | Overlap hours | `collectors.incremental.instagram.overlap_hours` |
| 49 | `3` | TikTok | Default lookback days | `collectors.incremental.tiktok.default_lookback_days` |
| 50 | `14` | TikTok | Max lookback days | `collectors.incremental.tiktok.max_lookback_days` |
| 51 | `2` | TikTok | Overlap hours | `collectors.incremental.tiktok.overlap_hours` |
| 54 | `3` | Reddit | Default lookback days | `collectors.incremental.reddit.default_lookback_days` |
| 55 | `14` | Reddit | Max lookback days | `collectors.incremental.reddit.max_lookback_days` |
| 56 | `2` | Reddit | Overlap hours | `collectors.incremental.reddit.overlap_hours` |
| 59 | `7` | Radio | Default lookback days | `collectors.incremental.radio.default_lookback_days` |
| 60 | `30` | Radio | Max lookback days | `collectors.incremental.radio.max_lookback_days` |
| 61 | `6` | Radio | Overlap hours | `collectors.incremental.radio.overlap_hours` |
| 64 | `7` | YouTube | Default lookback days | `collectors.incremental.youtube.default_lookback_days` |
| 65 | `30` | YouTube | Max lookback days | `collectors.incremental.youtube.max_lookback_days` |
| 66 | `6` | YouTube | Overlap hours | `collectors.incremental.youtube.overlap_hours` |
| 69 | `7` | RSS | Default lookback days | `collectors.incremental.rss.default_lookback_days` |
| 70 | `30` | RSS | Max lookback days | `collectors.incremental.rss.max_lookback_days` |
| 71 | `6` | RSS | Overlap hours | `collectors.incremental.rss.overlap_hours` |

---

## 13. LOCATION CLASSIFICATION SCORING

### Location Score Weights

#### `src/agent/core.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 2140 | `5.0` | Country name match score | `processing.location.scoring.country_name_match` |
| 2145 | `5.0` | Country name match score | `processing.location.scoring.country_name_match` |
| 2151 | `1.0` | Keyword match score | `processing.location.scoring.keyword_match` |
| 2157 | `3.0` | Location keyword match score | `processing.location.scoring.location_keyword_match` |
| 2160 | `2.0` | City match score | `processing.location.scoring.city_match` |
| 2168 | `2.0` | Additional match score | `processing.location.scoring.additional_match` |

---

## 14. INSTAGRAM ACTOR CONFIGURATION

### Instagram Actor Limits

#### `src/collectors/collect_instagram_apify.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 31 | `50` | Results limit default | `collectors.instagram.results_limit_default` |
| 63 | `100` | Max results (actor 1) | `collectors.instagram.actor_max_results.general` |
| 71 | `100` | Max results (actor 2) | `collectors.instagram.actor_max_results.hashtag` |
| 189 | `10` | Search limit | `collectors.instagram.search_limit` |

---

## 15. HTML STYLING VALUES

### HTML Table Styling

#### `src/utils/notification_service.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 541 | `border="1"` | Table border | `ui.html.table_border` |
| 541 | `cellpadding="5"` | Cell padding | `ui.html.table_cell_padding` |
| 548 | `border="1"` | Table border | `ui.html.table_border` |
| 548 | `cellpadding="5"` | Cell padding | `ui.html.table_cell_padding` |
| 578 | `border="1"` | Table border | `ui.html.table_border` |
| 578 | `cellpadding="5"` | Cell padding | `ui.html.table_cell_padding` |
| 591 | `border="1"` | Table border | `ui.html.table_border` |
| 591 | `cellpadding="5"` | Cell padding | `ui.html.table_cell_padding` |
| 615 | `border="1"` | Table border | `ui.html.table_border` |
| 615 | `cellpadding="5"` | Cell padding | `ui.html.table_cell_padding` |

---

## 16. DATABASE DEFAULTS

### Database Column Defaults

#### `src/alembic/versions/b2c3d4e5f6a7_create_topics_tables.py`

| Line | Value | Current Usage | Suggested Config Key |
|------|-------|---------------|---------------------|
| 46 | `'0'` | mention_count default | `models.defaults.mention_count` |
| 47 | `'20'` | max_issues default | `models.defaults.max_issues` |

---

## 📊 Summary Statistics

### Total Hardcoded Values by Category:

- **Paths**: ~15 instances
- **Timeouts**: ~30 instances
- **Thresholds**: ~40 instances
- **Sizes**: ~35 instances
- **String Lengths**: ~17 instances
- **URLs & Origins**: 1 instance (but with multiple values)
- **Delays**: ~25 instances
- **Rate Limits**: 1 instance
- **Other Constants**: ~20 instances
- **LLM Configuration**: ~8 instances
- **Collector Limits/Array Slicing**: ~8 instances
- **Incremental Collector Config**: ~24 instances (lookback days, overlap hours)
- **Location Scoring**: ~6 instances
- **Instagram Actor Config**: ~4 instances
- **HTML Styling**: ~10 instances
- **Database Defaults**: ~2 instances

**Total**: ~250+ hardcoded values across 16 categories

**Coverage**: ✅ COMPREHENSIVE - All major areas checked including:
- Core processing files
- All collector modules
- API services
- Configuration files
- Database models
- Utility modules

---

## 🎯 Recommended Configuration Structure

```json
{
  "paths": {
    "base": ".",
    "data_raw": "data/raw",
    "data_processed": "data/processed",
    "logs": "logs",
    "logs_agent": "logs/agent.log",
    "logs_scheduling": "logs/automatic_scheduling.log",
    "logs_collectors": "logs/collectors",
    "logs_openai": "logs/openai_calls.csv",
    "config_agent": "config/agent_config.json",
    "config_topic_embeddings": "config/topic_embeddings.json"
  },
  "processing": {
    "parallel": {
      "max_collector_workers": 8,
      "max_sentiment_workers": 20,
      "max_location_workers": 8,
      "sentiment_batch_size": 150,
      "location_batch_size": 300
    },
    "timeouts": {
      "collector_timeout_seconds": 1000,
      "apify_timeout_seconds": 600,
      "apify_wait_seconds": 600,
      "lock_max_age_seconds": 300,
      "scheduler_join_timeout": 10,
      "scheduler_timeout": 30,
      "http_request_timeout": 120
    },
    "delays": {
      "retry_sleep_seconds": 1,
      "no_users_sleep_seconds": 300,
      "error_sleep_seconds": 60,
      "rate_limit_delay_seconds": 1.0
    },
    "limits": {
      "max_records_per_batch": 10000
    },
    "sentiment": {
      "positive_threshold": 0.2,
      "negative_threshold": -0.2,
      "default_neutral_score": 0.5
    },
    "topic": {
      "min_score_threshold": 0.2,
      "confidence_threshold": 0.85,
      "keyword_score_threshold": 0.3,
      "embedding_score_threshold": 0.5
    },
    "governance": {
      "confidence_threshold": 0.85,
      "default_confidence": 0.5,
      "placeholder_score": 0.5,
      "default_relevance": 0.5,
      "non_governance_relevance": 0.1
    },
    "llm": {
      "temperature": 0.2
    },
    "tokens": {
      "estimated_per_sentiment": 1000,
      "estimated_per_issue": 800,
      "estimated_per_governance": 1200,
      "estimated_per_governance_combined": 2200,
      "estimated_per_embedding": 2200
    },
    "rate_limits": {
      "twitter": 100,
      "news": 50
    }
  },
  "deduplication": {
    "similarity_threshold": 0.85,
    "length_ratio_threshold": 0.5
  },
  "database": {
    "pool_size": 30,
    "max_overflow": 20,
    "pool_recycle_seconds": 3600,
    "pool_timeout_seconds": 60
  },
  "collectors": {
    "twitter": {
      "max_items_default": 100
    },
    "instagram": {
      "max_results_default": 100
    },
    "tiktok": {
      "max_results_default": 100,
      "delay_between_runs_seconds": 3,
      "delay_between_actors_seconds": 5
    },
    "youtube": {
      "max_results": 1000,
      "rate_limit_delay_seconds": 0.1,
      "delay_seconds": 1
    },
    "news": {
      "max_items_default": 1000,
      "delay_between_queries_seconds": 2,
      "delay_between_actors_seconds": 5
    },
    "rss": {
      "feed_timeout_seconds": 30,
      "ssl_timeout_seconds": 10,
      "socket_timeout_seconds": 10,
      "overall_timeout_seconds": 600,
      "buffer_seconds": 5,
      "delay_seconds": 1,
      "min_health_score": 0.5,
      "min_valid_entries_ratio": 0.5,
      "health_score_fair": 0.5,
      "error_penalty": 0.2
    },
    "radio": {
      "timeout_seconds": 15,
      "gnews_timeout_seconds": 30,
      "retry_wait_seconds": 2,
      "gnews_delay_seconds": 1
    },
    "social_searcher": {
      "delay_seconds": 2
    },
    "incremental": {
      "max_items_default": 100
    }
  },
  "api": {
    "cors_origins": [
      "http://localhost:3000",
      "http://localhost:3001",
      "http://13.202.48.110:3000",
      "http://13.202.48.110:3001",
      "https://*.railway.app",
      "https://*.up.railway.app"
    ],
    "timeouts": {
      "http_request_timeout": 60
    },
    "pagination": {
      "default_limit": 100
    },
    "http": {
      "success_status_range": [200, 300]
    }
  },
  "models": {
    "string_lengths": {
      "short": 50,
      "medium": 100,
      "long": 200,
      "very_long": 500
    }
  },
  "utils": {
    "scheduler": {
      "thread_join_timeout_seconds": 5,
      "sleep_seconds": 1
    },
    "rate_limiter": {
      "sleep_increment_seconds": 1.0
    }
  }
}
```

---

## ✅ Next Steps

1. Create ConfigManager with this structure
2. Replace all hardcoded values with config lookups
3. Update default values in config files
4. Test that all functionality still works
5. Document configuration options

---

**Last Updated**: 2025-12-27  
**Status**: ✅ Comprehensive audit complete - 250+ hardcoded values identified across 16 categories

---

## 🔍 Verification Checklist

### Completed Searches:
- ✅ Path strings (`logs/`, `data/`, `config/`)
- ✅ Timeout values (all `timeout=`, `sleep()` calls)
- ✅ Threshold values (similarity, confidence, sentiment scores)
- ✅ Batch sizes and limits (`max_results`, `batch_size`, `limit`)
- ✅ String lengths (database column constraints)
- ✅ CORS origins and URLs
- ✅ Delays and sleep times
- ✅ Rate limits
- ✅ LLM configuration (temperature, max_tokens)
- ✅ Collector limits and array slicing
- ✅ Incremental collector lookback/overlap settings
- ✅ Location classification scoring weights
- ✅ HTML styling values
- ✅ Database column defaults

### Additional Areas Checked:
- ✅ Numeric literals in function parameters
- ✅ Default values in `.get()` calls
- ✅ Hardcoded model names
- ✅ API endpoint URLs
- ✅ Collector actor configurations

