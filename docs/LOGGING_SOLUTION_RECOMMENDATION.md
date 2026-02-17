# Logging Solution Recommendation for Clariona Backend

## Your Current Setup

- **Log files** (from `src/services/main.py` and ecosystem):  
  `data_ingestor.log`, `analysis_worker.log`, `scheduler.log`, `dataset_tailer.log`, `issue_detection.log`, plus PM2 cycle/pipeline logs and collector logs under `logs/collectors/`.
- **Volume**: High (e.g. data_ingestor ~17k+ lines, analysis_worker ~12k+ lines).
- **Format**: Plain text, `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
- **Parameters currently in messages** (embedded in text, not queryable):
  - **Ingestor**: `url`, `platform`, `date`, `user_name`, `user_handle`, `user_location`, `likes`, `retweets`, `comments`, `views`, batch sizes, duplicate counts.
  - **Analysis worker**: `entry_id`, `sentiment`, `topics` count, worker IDs, topic progress (e.g. 70/139), elapsed time, timeout, “Active now” concurrency.

You want to **track a variety of parameters** and be able to search/filter and (optionally) build dashboards.

---

## Recommended Approach

### 1. Application layer: **Structured logging with structlog**

**Why structlog fits your use case**

- **Structured key–value data**: Parameters become first-class fields (e.g. `platform`, `entry_id`, `batch_size`) instead of buried in message strings, so you can query and aggregate later.
- **Context binding**: You can bind `service`, `worker_id`, `entry_id` once and have them on every log line (great for analysis_worker and data_ingestor).
- **Multiple outputs**: JSON for aggregation/tools, logfmt or pretty console for local debugging.
- **Works with your stack**: Can sit on top of Python’s `logging` (your existing `get_logger` / `setup_module_logger` can be gradually migrated).
- **Performance**: Supports fast JSON (e.g. orjson), level filtering, and is used in high-volume production environments.

**What you gain**

- Query by `platform=facebook`, `entry_id=1634622`, `batch_size`, `level=ERROR`, etc.
- Consistent fields across `data_ingestor`, `analysis_worker`, and other services.
- Easy to ship JSON logs to an aggregation backend (Loki, ELK, Datadog, etc.) and use those fields as labels or filters.

**Minimal change path**

- Add **structlog** and optionally **structlog-stdlib** (or use structlog’s standard library integration) so existing `logging` call sites can stay while you switch the formatter to JSON.
- Configure one JSON formatter (e.g. `structlog.processors.JSONRenderer`) for file handlers and keep a human-readable format for console if you want.
- Gradually replace `logger.info("... %s ...", x)` with `logger.info("message", key1=x, key2=y)` so parameters are first-class keys.

---

### 2. Aggregation / querying (optional but recommended)

Once logs are **structured (JSON)** with clear fields, you need a place to aggregate and query them.

| Solution              | Best for                                      | Notes |
|----------------------|-----------------------------------------------|-------|
| **Grafana Loki**     | Lightweight, self-hosted, label-based search  | Indexes labels (e.g. `service`, `level`, `platform`); full text on log body. Fits “track many parameters” if you expose them as labels. Lower resource use than ELK. |
| **ELK (Elasticsearch + Kibana)** | Rich full-text search, complex queries | Heavier (CPU/RAM). Good if you need full-text search over message and many facets. |
| **Datadog / SaaS**   | Managed, no ops, fast setup                  | Cost scales with volume; good if you prefer not to run log infra. |
| **SigNoz**           | Open-source, metrics + traces + logs         | Alternative to Loki/ELK with lower resource use in some benchmarks. |

**Practical recommendation for you**

- Prefer **Grafana Loki** (or SigNoz) if you want self-hosted, low footprint, and good filtering by service, level, and key parameters (e.g. `platform`, `entry_id`, `batch_size`) that you emit as structured fields (and optionally as Loki labels).
- Add a **Promtail** (or similar) sidecar/agent to read your JSON log files and push to Loki; use **Grafana** for dashboards and LogQL queries.

---

## Summary

| Goal                         | Recommendation |
|-----------------------------|----------------|
| **Track many parameters**   | **structlog** with key–value logging (not only free text). |
| **Query/filter by those params** | Emit **JSON** logs; use an **aggregation backend** (e.g. **Loki + Grafana**). |
| **Minimal disruption**      | Integrate structlog with stdlib `logging`; switch formatter to JSON for file handlers; migrate log calls incrementally to structured keys. |
| **Lightweight & self-hosted** | **Grafana Loki + Promtail** (or similar) to ingest JSON logs and query by labels/fields. |

Next step: add **structlog** (and optionally **structlog-stdlib**) to the project, configure a JSON renderer for your existing file handlers in `logging_config.py`, and then start adding structured keys for the parameters you care about (e.g. in `data_ingestor` and `analysis_worker`). After that, you can add Loki + Promtail (or another aggregator) to centralize and query logs.
