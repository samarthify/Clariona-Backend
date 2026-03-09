**ARCHITECTURE DESIGN PLAN**

**Real-Time Issue Detection**

**Command Station**

Sub-second velocity alerting • Incremental clustering • Event-driven ingestion

Feasibility & Implementation Guide

**EXECUTIVE SUMMARY**

This document describes a redesigned architecture for your real-time issue detection command station. The core goal is simple: when a surge of mentions about the same topic arrives in real time, the system must detect it, score its velocity, and fire an alert - all within seconds, not minutes.

The existing pipeline has the right skeleton (event-driven ingestion, Pinecone clustering, incremental assigner) but its velocity and alerting logic is calibrated for a monitoring dashboard. This plan surgically upgrades those two layers without requiring a full rewrite.

**Three Core Changes**

1\. Replace 24h growth-rate windows with sub-minute sliding velocity counters (Redis).

2\. Move alert evaluation inside the incremental assigner - fire on cluster update, not on promotion.

3\. Decouple alert routing from the promotion cycle entirely.

# **1\. Problem Statement**

Your current system has two hard gaps for the command-station use case:

| **Gap** | **Current Behaviour** | **Impact on Command Station** |
| --- | --- | --- |
| Velocity windows | growth_rate = (24h − prev 24h) / prev 24h | A 4-minute payment-outage spike is invisible for hours |
| Alert path | Alert is a side-effect of promotion cycle | Latency is promotion_cycle_interval, not 2-4 s |
| Queue drain | Daemon batches 10 events / 2 s | 500-event spike takes ~100 s to fully process |
| Density gating | density_score required for promotion (unless None) | New clusters may stall behind density threshold |

# **2\. Target Architecture**

The architecture is composed of five layers. Layers 1-3 already exist. Layers 4-5 are new or substantially changed.

| **LAYER 1 - INGESTION (existing)**<br><br>Event-driven mentions arrive pre-bucketed by topic. No changes needed here. |
| --- |
| **LAYER 2 - ANALYSIS WORKER (existing)**<br><br>Sentiment + topic classification. Enqueues up to 3 cluster_queue events per mention (top topics by confidence) with 1536-dim embedding. |
| **LAYER 3 - INCREMENTAL CLUSTER ASSIGNER (upgrade batch size + parallelism)**<br><br>Pinecone ANN lookup → attach or create cluster. Upgrade: dynamic batch sizing + adaptive poll interval under load. |
| **LAYER 4 - VELOCITY TRACKER (new)**<br><br>In-process Redis counters per (topic_key, cluster_id) at 1 min, 5 min, 15 min windows. Updated on every cluster attach/create. Burst ratio = count_1m / baseline_15m. |
| **LAYER 5 - ALERT ENGINE (new)**<br><br>Threshold evaluator runs inline inside the assigner after each cluster update. Fires alert events immediately to an alert_queue. Separate alert dispatcher handles dedup, routing, and cooldown. |

# **3\. Layer 4 - Velocity Tracker (New)**

## **3.1 Why Redis sliding windows**

Postgres is too slow for sub-second counter increments under spike conditions. Redis sorted-set or INCRBY+EXPIRE patterns are O(1) per write and can sustain tens of thousands of updates per second on a single node.

## **3.2 Data model**

| **Redis Key Pattern** | **Description** |
| --- | --- |
| vel:{user_id}:{topic_key}:{cluster_id}:1m | INCR counter, TTL 90 s. Represents mentions in the last ~1 min. |
| vel:{user_id}:{topic_key}:{cluster_id}:5m | INCR counter, TTL 360 s. Represents mentions in the last ~5 min. |
| vel:{user_id}:{topic_key}:{cluster_id}:15m | INCR counter, TTL 1080 s. Used as rolling baseline. |
| vel_alert:{user_id}:{topic_key}:{cluster_id} | Cooldown key, TTL = alert_cooldown_seconds (e.g. 120 s). Prevents alert storms. |

**Implementation Note - Approximation is fine**

These are approximate sliding windows using fixed TTLs, not exact time-series buckets.

For a command station the goal is fast spike detection, not perfect statistical accuracy.

If you need exact windows later, swap in Redis TimeSeries (RedisStack) without changing the interface.

## **3.3 Pseudocode**

class VelocityTracker:

WINDOWS = {'1m': 90, '5m': 360, '15m': 1080}

def record(self, user_id, topic_key, cluster_id) -> VelocitySnapshot:

pipe = redis.pipeline()

for window, ttl in self.WINDOWS.items():

key = f'vel:{user_id}:{topic_key}:{cluster_id}:{window}'

pipe.incr(key)

pipe.expire(key, ttl, xx=False) # only set TTL on new keys

counts = pipe.execute()\[::2\] # every other result is the incr value

return VelocitySnapshot(

count_1m=counts\[0\], count_5m=counts\[1\], count_15m=counts\[2\],

burst_ratio=counts\[0\] / max(counts\[2\] / 15, 1), # 1m vs 15m baseline/min

ts=time.time()

)

def get_snapshot(self, user_id, topic_key, cluster_id) -> VelocitySnapshot:

\# Read-only, used by dashboards / promotion ranking

...

# **4\. Layer 5 - Alert Engine (New)**

## **4.1 Inline threshold evaluation**

The alert check runs synchronously inside the incremental assigner immediately after every cluster attach or create operation. It adds negligible latency (one Redis read for the cooldown key) but guarantees alerts fire within the same 2-4 s window as clustering.

\# Inside IncrementalClusterAssigner.\_process_event():

\# 1. Cluster attach / create (existing code)

cluster = self.\_attach_or_create(event)

\# 2. Update velocity counters (NEW)

snap = velocity_tracker.record(event.user_id, event.topic_key, cluster.id)

\# 3. Evaluate thresholds (NEW)

alert = alert_evaluator.evaluate(cluster, snap)

\# 4. Emit alert if triggered (NEW - non-blocking)

if alert:

alert_queue.put_nowait(alert) # never blocks the assigner

## **4.2 Alert evaluator - threshold matrix**

All thresholds are config-driven. The evaluator returns the highest-severity alert that fires, or None.

| **Alert Level** | **Trigger Condition** | **Suggested Default** |
| --- | --- | --- |
| CRITICAL | burst_ratio ≥ 10 AND count_1m ≥ 20 | Immediate page / webhook |
| HIGH | burst_ratio ≥ 5 AND count_5m ≥ 30 | Slack / PagerDuty |
| MEDIUM | burst_ratio ≥ 3 AND count_15m ≥ 50 | Dashboard banner |
| INFO | count_5m ≥ threshold_info (e.g. 15) | Log / dashboard only |

burst_ratio is the key signal. It normalises raw count against the cluster's own recent baseline, so a cluster that always gets 100 mentions/min does not generate false alerts - only genuine spikes do.

## **4.3 Alert dispatcher (separate thread)**

The dispatcher consumes from alert_queue and handles:

- Deduplication: if vel_alert:{key} exists in Redis, suppress (cooldown active).
- Cooldown write: SET vel_alert:{key} 1 EX alert_cooldown_seconds on first fire.
- Routing: webhook, Slack, PagerDuty, email - config-driven per severity level.
- Persistence: write AlertEvent to Postgres for audit trail and dashboard replay.
- Re-evaluation: after cooldown expires, if cluster is still spiking, fire again.

**Why separate thread for dispatcher?**

The assigner must never block waiting for an HTTP webhook call.

put_nowait() into an asyncio queue or threading.Queue is microsecond-level.

The dispatcher can retry failed webhooks without affecting clustering throughput.

# **5\. Layer 3 - Assigner Upgrades**

## **5.1 Dynamic batch sizing**

The current fixed batch of 10 events / 2 s is fine under normal load but creates drain lag during spikes. Replace with adaptive sizing:

| **queue_depth** | **batch_size / poll_interval** |
| --- | --- |
| < 50 | 10 events / 2 s (current behaviour, no change) |
| 50 - 200 | 50 events / 1 s |
| 200 - 500 | 100 events / 0.5 s |
| \> 500 | 200 events / 0.25 s + spawn second worker thread |

This is a config table, not hard-coded logic. The assigner reads it on startup. You can tune it per deployment without code changes.

## **5.2 Parallel Pinecone queries**

When batch_size > 50, fire Pinecone queries concurrently using asyncio.gather() or a ThreadPoolExecutor. Each query is independent (different embedding, same filter). This keeps per-event latency flat even as batch size grows.

## **5.3 Circuit breaker unchanged**

Keep the existing 5-failure / 60 s cooldown circuit breaker on Pinecone. Under the new parallel query model, a single failed query does not trip the breaker - only 5 consecutive failures on the same slot do.

# **6\. Promotion & Ranking - Velocity Integration**

The promotion cycle does not need to change structurally. It should, however, replace the 24h growth_rate with the live velocity snapshot from Redis when scoring clusters:

\# Before (stale):

score = size \* max(density, 0.0001) \* (1.0 + growth_rate_24h)

\# After (live):

snap = velocity_tracker.get_snapshot(user_id, topic_key, cluster_id)

velocity_factor = math.log1p(snap.burst_ratio) # log-scale to avoid domination

score = size \* max(density, 0.0001) \* (1.0 + velocity_factor)

log1p() prevents a single 100x burst from completely dominating the ranking over many smaller but sustained clusters. Tune the weight if needed.

# **7\. Feasibility Assessment**

## **7.1 New dependencies**

| **Dependency** | **Notes** |
| --- | --- |
| Redis (or Redis-compatible) | Already likely in your stack for queuing. If not, add as a sidecar. Minimal ops overhead. |
| alert_queue (in-process) | threading.Queue or asyncio.Queue - zero new infrastructure. |
| AlertEvent table (Postgres) | One new table, ~5 columns. Add in a migration. |
| Webhook client | httpx or requests - already in most Python stacks. |

## **7.2 Code surface area**

| **Component** | **Estimated LOC** | **Risk** |
| --- | --- | --- |
| VelocityTracker class | ~80 LOC | Low - pure Redis I/O |
| AlertEvaluator class | ~60 LOC | Low - threshold comparisons |
| AlertDispatcher thread | ~120 LOC | Low - queue consumer + HTTP |
| Assigner integration | ~40 LOC delta | Low - 4 lines shown above |
| Dynamic batch sizing | ~50 LOC delta | Low - replace fixed constants |
| Promotion score update | ~5 LOC delta | Trivial |
| DB migration | 1 table | Trivial |

**Total estimated effort**

New code: ~310 LOC across 3 new classes.

Changed code: ~95 LOC delta in existing files.

Infrastructure: Redis (may already exist), 1 Postgres migration.

Estimated engineering time: 3-5 days for an engineer familiar with the existing codebase.

# **8\. Migration Plan**

The migration is additive - no existing code is deleted until the new path is proven in production.

| **Phase** | **What** | **Rollback** |
| --- | --- | --- |
| Phase 1 (1 day) | Add VelocityTracker. Wire into assigner. Log velocity snapshots only - no alerts yet. Validate burst_ratio values look correct. | Remove 4 lines from assigner. |
| Phase 2 (1 day) | Add AlertEvaluator + AlertDispatcher. Route alerts to log file only. Tune thresholds against real traffic. | Set alert_engine_enabled=false in config. |
| Phase 3 (1 day) | Enable webhook / Slack routing for HIGH + CRITICAL. Monitor false-positive rate. | Set routing targets to log-only. |
| Phase 4 (1 day) | Update promotion score formula. Enable dynamic batch sizing. Run load test. | Feature-flag each change independently. |
| Phase 5 (ongoing) | Remove 24h growth_rate from Postgres. Deprecate batch DBSCAN path once incremental covers >99% of mentions. | Keep DBSCAN code, just disable via config. |

# **9\. Configuration Reference**

All new parameters live under processing.issue.realtime_alerts in your existing config structure.

| **Config Key** | **Default / Notes** |
| --- | --- |
| alert_engine_enabled | false - feature flag, flip to true in Phase 2 |
| velocity.windows | {1m: 90, 5m: 360, 15m: 1080} - TTLs in seconds |
| thresholds.critical.burst_ratio | 10.0 |
| thresholds.critical.count_1m | 20  |
| thresholds.high.burst_ratio | 5.0 |
| thresholds.high.count_5m | 30  |
| thresholds.medium.burst_ratio | 3.0 |
| thresholds.medium.count_15m | 50  |
| thresholds.info.count_5m | 15  |
| alert_cooldown_seconds | 120 - prevents alert storms per cluster |
| dispatcher.routes.critical | webhook_url + pagerduty_key |
| dispatcher.routes.high | slack_webhook |
| dispatcher.routes.medium | dashboard_only |
| batch_sizing.thresholds | \[50, 200, 500\] - queue depths for tier changes |
| batch_sizing.sizes | \[10, 50, 100, 200\] - batch sizes per tier |

# **10\. What Stays the Same**

This architecture does not touch the following - they are already correct for the use case:

- Pinecone ANN clustering with attach_similarity_threshold=0.70
- cluster_queue event structure (entry_id, topic_key, user_id, embedding)
- Cluster merge and expiry logic (\_merge_clusters, \_expire_clusters)
- Promotion eligibility rules (density_score=None passes through)
- Issue creation conditions (\_check_issue_conditions)
- DBSCAN batch path as a straggler/backfill safety net
- Tenant isolation via user_id filtering in Pinecone and Postgres
- Circuit breaker on Pinecone (5 failures / 60 s cooldown)

# **11\. End-to-End Latency Profile**

Measured from mention arriving at the analysis worker to alert being dispatched:

| **Stage** | **Latency** | **Notes** |
| --- | --- | --- |
| Analysis worker (sentiment + topic) | ~800 ms | Existing, no change |
| cluster_queue enqueue | < 1 ms | In-process |
| Assigner poll + Pinecone query | ~400 ms | P95 with parallelism |
| Cluster attach/create + PG write | ~80 ms | Existing |
| VelocityTracker.record() Redis | < 5 ms | Pipeline write |
| AlertEvaluator.evaluate() | < 1 ms | In-process threshold check |
| alert_queue.put_nowait() | < 0.1 ms | Non-blocking |
| AlertDispatcher webhook call | ~200 ms | Async, does not block assigner |
| TOTAL (mention → alert fired) | ~1.3 - 1.5 s | P95 under normal load |

**Compare to current system**

Current: mention → alert requires a full promotion cycle. Promotion runs every issue_poll_interval (typically 30-120 s).

New: mention → alert in ~1.5 s P95.

Improvement: 20x - 80x latency reduction for alert firing.

Real-Time Issue Detection Command Station • Architecture Design Plan • Feasibility Review