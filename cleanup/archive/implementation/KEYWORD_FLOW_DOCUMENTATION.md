# Keyword Flow Documentation - ACTUAL FLOW

## Overview
This document explains the **ACTUAL** flow of how keywords are passed from target configuration to collectors in the production system. The main entry point is `agent/core.py`, not `configurable_collector.py`.

## Actual Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Entry Point: agent/core.py                               │
│    SentimentAnalysisAgent.collect_data()                    │
│    Input: target_name, queries (from database/API)         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent._get_enabled_collectors_for_target(target_name)   │
│    - Uses TargetConfigManager.get_target_by_name()         │
│    - Gets target_id from matching config                    │
│    - Calls TargetConfigManager.get_enabled_collectors()    │
│    - Returns: ["collect_twitter_apify", "collect_news_apify", ...]│
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. TargetConfigManager.get_enabled_collectors(target_id)   │
│    - Loads TargetConfig from target_configs.json            │
│    - Checks which sources are enabled                       │
│    - Maps source types → collector names using:             │
│      ConfigManager.get_dict("collectors.source_to_collector_mapping")│
│    - Returns: List of collector module names               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Agent._run_collectors_parallel()                        │
│    - Creates queries_json = JSON of [target_name, ...queries]│
│    - For each collector, runs as subprocess:                │
│      python -m src.collectors.{collector_name} --queries {json}│
│    - Collectors run in parallel using ThreadPoolExecutor    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Individual Collector main() function                    │
│    - Parses --queries argument (JSON)                       │
│    - Extracts: target_and_variations = [target, q1, q2...] │
│    - target_and_variations[0] = target name                 │
│    - target_and_variations[1:] = query variations (keywords)│
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Collector Keyword Resolution (Two Paths)                 │
│                                                              │
│    PATH A: Collectors with set_target_config()             │
│    - Collector calls: get_target_by_name(target_name)      │
│    - Sets target_config via set_target_config()            │
│    - Uses _get_target_keywords() which checks:             │
│      1. target_config.sources.<source>.keywords            │
│      2. target_config.keywords                              │
│      3. ConfigManager defaults                             │
│                                                              │
│    PATH B: Apify Collectors (Function-based)               │
│    - Uses queries = target_and_variations[1:]              │
│    - If queries empty, falls back to ConfigManager defaults │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Flow

### Step 1: Agent Core Entry Point

**File**: `src/agent/core.py`

```python
def collect_data(self, target_name: str, queries: List[str], user_id: str):
    # ... 
    enabled_collectors = self._get_enabled_collectors_for_target(target_name)
    queries_json = json.dumps([target_name] + queries)
    collection_results = self._run_collectors_parallel(enabled_collectors, queries_json, user_id)
```

**Key Points**:
- `queries` parameter contains the keyword list
- Combined into `queries_json = [target_name, ...queries]`
- Passed to parallel collector execution

### Step 2: Get Enabled Collectors

**File**: `src/agent/core.py` → `_get_enabled_collectors_for_target()`

```python
def _get_enabled_collectors_for_target(self, target_name: str) -> List[str]:
    from src.collectors.target_config_manager import TargetConfigManager
    config_manager = TargetConfigManager()
    
    target_config = config_manager.get_target_by_name(target_name)
    # Find target_id
    enabled_collectors = config_manager.get_enabled_collectors(target_id)
    return enabled_collectors  # ["collect_twitter_apify", "collect_news_apify", ...]
```

**Key Points**:
- Uses `TargetConfigManager` to find target by name
- Gets enabled collectors for that target
- Returns list of collector module names

### Step 3: TargetConfigManager.get_enabled_collectors()

**File**: `src/collectors/target_config_manager.py`

```python
def get_enabled_collectors(self, target_id: str) -> List[str]:
    target_config = self.get_target_config(target_id)
    
    # Get source-to-collector mapping from ConfigManager
    from config.config_manager import ConfigManager
    config = ConfigManager()
    source_to_collector = config.get_dict("collectors.source_to_collector_mapping", {...})
    
    enabled_collectors = []
    for source_type, source_config in target_config.sources.items():
        if source_config.enabled:
            collector_names = source_to_collector.get(source_type, [])
            enabled_collectors.extend(collector_names)
    
    return enabled_collectors
```

**Key Points**:
- Checks which sources are enabled in `target_configs.json`
- Maps source types to collector names using `ConfigManager`
- Returns collector module names (e.g., `"collect_twitter_apify"`)

### Step 4: Parallel Execution

**File**: `src/agent/core.py` → `_run_collectors_parallel()`

```python
def _run_collectors_parallel(self, collectors: List[str], queries_json: str, user_id: str):
    def run_single_collector(collector_name: str) -> bool:
        command = [
            sys.executable, "-m", f"src.collectors.{collector_name}", 
            "--queries", queries_json
        ]
        # Add incremental dates if needed
        # Run subprocess...
    
    # Run all collectors in parallel
    with ThreadPoolExecutor(max_workers=self.max_collector_workers) as executor:
        futures = {executor.submit(run_single_collector, name): name for name in collectors}
        # Wait for completion...
```

**Key Points**:
- Each collector runs as a **separate Python subprocess**
- `queries_json` is passed as `--queries` command-line argument
- Collectors run in parallel using `ThreadPoolExecutor`
- Each collector has its own log file

### Step 5: Collector main() Function

**Example**: `src/collectors/collect_twitter_apify.py`

```python
def main(target_and_variations: List[str], user_id: str = None):
    target_name = target_and_variations[0]  # "Emir of Qatar"
    queries = target_and_variations[1:]      # ["Qatar", "Sheikh Tamim", ...]
    
    # Call collection function
    collect_twitter_apify(queries=queries, ...)
```

**Key Points**:
- `target_and_variations[0]` = target name
- `target_and_variations[1:]` = keywords/queries
- These come from the `--queries` JSON argument

### Step 6: Keyword Resolution in Collectors

#### Path A: Collectors with `set_target_config()` Method

**Example**: `src/collectors/collect_youtube_api.py`

```python
def main(target_and_variations: List[str], user_id: str = None):
    target_name = target_and_variations[0]
    
    # Get target config
    from .target_config_manager import get_target_by_name
    target_config = get_target_by_name(target_name)
    if target_config:
        collector.set_target_config(target_config)
    
    # Collector uses _get_target_keywords()
    def _get_target_keywords(self) -> List[str]:
        # Priority 1: Source-specific keywords
        if self.target_config.sources.get('youtube').keywords:
            return self.target_config.sources['youtube'].keywords
        
        # Priority 2: Top-level target keywords
        if self.target_config.keywords:
            return self.target_config.keywords
        
        # Priority 3: ConfigManager defaults
        from config.config_manager import ConfigManager
        config = ConfigManager()
        return config.get_list("collectors.default_keywords.youtube", [...])
```

**Collectors using this path**:
- `collect_youtube_api.py`
- `collect_radio_hybrid.py`
- `collect_radio_gnews.py`
- `collect_radio_stations.py`
- `collect_news_from_api.py`

#### Path B: Apify Collectors (Function-based)

**Example**: `src/collectors/collect_twitter_apify.py`

```python
def main(target_and_variations: List[str], user_id: str = None):
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]  # Keywords from command line
    
    collect_twitter_apify(queries=queries, ...)

def collect_twitter_apify(queries: List[str], ...):
    # Use fallback keywords if queries is empty
    if not queries:
        from config.config_manager import ConfigManager
        config = ConfigManager()
        queries = config.get_list("collectors.default_keywords.twitter", [...])
    
    # Use queries for collection...
```

**Collectors using this path**:
- `collect_twitter_apify.py`
- `collect_instagram_apify.py`
- `collect_tiktok_apify.py`
- `collect_facebook_apify.py`
- `collect_news_apify.py`

## Keyword Sources Priority

### For Collectors with `set_target_config()`:

1. **Source-Specific Keywords** (from `target_configs.json`)
   - `targets.<target_id>.sources.<source_type>.keywords`
   - Example: `targets.emir.sources.youtube.keywords = ["qatar", "doha"]`

2. **Top-Level Target Keywords** (from `target_configs.json`)
   - `targets.<target_id>.keywords`
   - Example: `targets.emir.keywords = ["emir", "amir", "sheikh tamim"]`

3. **ConfigManager Default Keywords** (from `config_manager.py`)
   - `collectors.default_keywords.<collector_name>`
   - Example: `collectors.default_keywords.youtube = ["emir", "amir", ...]`

### For Apify Collectors:

1. **Command-Line Queries** (from `target_and_variations[1:]`)
   - Passed via `--queries` JSON argument
   - Example: `["Emir of Qatar", "Qatar", "Sheikh Tamim"]` → queries = `["Qatar", "Sheikh Tamim"]`

2. **ConfigManager Default Keywords** (fallback if queries empty)
   - `collectors.default_keywords.<collector_name>`
   - Example: `collectors.default_keywords.twitter = ["qatar", "nigeria", ...]`

## Source-to-Collector Mapping

**Location**: `config/config_manager.py` → `collectors.source_to_collector_mapping`

```python
"source_to_collector_mapping": {
    "news": ["collect_news_from_api", "collect_news_apify"],
    "twitter": ["collect_twitter_apify"],
    "facebook": ["collect_facebook_apify"],
    "rss": ["collect_rss_nigerian_qatar_indian"],
    "youtube": ["collect_youtube_api"],
    "radio": ["collect_radio_hybrid"],
    "reddit": ["collect_reddit_apify"],
    "instagram": ["collect_instagram_apify"],
    "tiktok": ["collect_tiktok_apify"],
    "linkedin": ["collect_linkedin"]
}
```

**Usage**: `TargetConfigManager.get_enabled_collectors()` uses this mapping to determine which collector modules to run for each enabled source type.

## Example: Complete Flow for Twitter Collector

1. **Agent Entry**: 
   - `agent.collect_data(target_name="Emir of Qatar", queries=["Qatar", "Sheikh Tamim"], user_id="123")`

2. **Get Enabled Collectors**:
   - `_get_enabled_collectors_for_target("Emir of Qatar")`
   - Finds target_id = "emir"
   - Checks `target_configs.json`: `sources.twitter.enabled = true`
   - Maps `twitter` → `["collect_twitter_apify"]` using ConfigManager
   - Returns: `["collect_twitter_apify"]`

3. **Parallel Execution**:
   - Creates `queries_json = '["Emir of Qatar", "Qatar", "Sheikh Tamim"]'`
   - Runs: `python -m src.collectors.collect_twitter_apify --queries '["Emir of Qatar", "Qatar", "Sheikh Tamim"]'`

4. **Collector main()**:
   - Parses JSON: `target_and_variations = ["Emir of Qatar", "Qatar", "Sheikh Tamim"]`
   - Extracts: `queries = ["Qatar", "Sheikh Tamim"]`

5. **Collection Function**:
   - `collect_twitter_apify(queries=["Qatar", "Sheikh Tamim"], ...)`
   - Uses queries for Twitter API calls

## Configuration Files

### `config/target_configs.json`
```json
{
  "targets": {
    "emir": {
      "keywords": ["emir", "amir", "sheikh tamim"],
      "sources": {
        "twitter": {
          "enabled": true,
          "keywords": ["qatar", "doha", "sheikh tamim bin hamad"]
        },
        "youtube": {
          "enabled": true,
          "keywords": ["qatar", "doha"]
        }
      }
    }
  }
}
```

### `config/config_manager.py`
```python
"collectors": {
  "source_to_collector_mapping": {
    "twitter": ["collect_twitter_apify"],
    "youtube": ["collect_youtube_api"],
    # ...
  },
  "default_keywords": {
    "twitter": ["qatar", "nigeria", "india", "politics", "news"],
    "youtube": ["emir", "amir", "sheikh tamim", "al thani"],
    # ...
  }
}
```

## Important Notes

1. **Main Flow is Parallel Subprocess Execution**: Collectors run as separate Python processes, not through ConfigurableCollector class.

2. **Keywords Come from Two Places**:
   - Command-line `--queries` argument (for Apify collectors)
   - Target config via `set_target_config()` (for class-based collectors)

3. **Source-to-Collector Mapping is Centralized**: Now in ConfigManager, not hardcoded in TargetConfigManager.

4. **Fallback Chain**: All collectors have fallback keywords from ConfigManager if no keywords are provided.

5. **Parallel Execution**: Multiple collectors run simultaneously using ThreadPoolExecutor, each in its own subprocess with its own log file.
