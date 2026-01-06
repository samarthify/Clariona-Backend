# Cleanup Quick Start Guide

This is a condensed guide for getting started with the cleanup immediately. For the complete plan, see [`CLEANUP_AND_REFACTORING_PLAN.md`](./CLEANUP_AND_REFACTORING_PLAN.md).

## 🚨 Critical Issues Found

### 1. **Unused/Legacy Code** (~20% of codebase)
- 10+ deprecated methods in `core.py`
- 40+ potentially unused API endpoints
- Legacy deduplication functions
- Unused imports and modules

### 2. **Hardcoded Values** (215+ instances)
- Magic numbers: `0.85`, `100`, `50`, `300`, `500`, `1000`, `180`
- Hardcoded paths: `'logs/'`, `'data/raw'`, `'data/processed'`
- Hardcoded timeouts, batch sizes, thresholds
- Hardcoded CORS origins, URLs

### 3. **Code Duplication**
- Multiple deduplication implementations
- Multiple config loading mechanisms
- Multiple path resolution methods

### 4. **Configuration Chaos**
- Config in JSON files AND code
- Defaults hardcoded in multiple places
- No central configuration manager

---

## 🎯 Immediate Action Plan (Week 1)

### Day 1-2: Create Centralized Configuration System

**Priority: HIGHEST** - This enables all other improvements

1. Create `src/config/config_manager.py`:
   ```python
   from pathlib import Path
   import json
   import os
   from typing import Any, Dict, Optional
   
   class ConfigManager:
       """Centralized configuration management"""
       
       def __init__(self, config_dir: Path = None):
           self.config_dir = config_dir or Path(__file__).parent.parent.parent / "config"
           self._config = {}
           self._load_config()
       
       def _load_config(self):
           # Load defaults
           self._config = self._get_defaults()
           
           # Load from JSON files
           agent_config_path = self.config_dir / "agent_config.json"
           if agent_config_path.exists():
               with open(agent_config_path) as f:
                   agent_config = json.load(f)
                   self._merge_config(self._config, agent_config)
           
           # Override with environment variables
           self._load_env_overrides()
       
       def _get_defaults(self) -> Dict[str, Any]:
           return {
               "paths": {
                   "base": ".",
                   "data_raw": "data/raw",
                   "data_processed": "data/processed",
                   "logs": "logs",
                   "logs_collectors": "logs/collectors",
                   "logs_agent": "logs/agent.log",
                   "logs_scheduling": "logs/automatic_scheduling.log"
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
                       "batch_timeout_seconds": 300,
                       "apify_timeout_seconds": 600,
                       "apify_wait_seconds": 600,
                       "lock_max_age_seconds": 300
                   }
               },
               "deduplication": {
                   "similarity_threshold": 0.85,
                   "text_fields": ["text", "content", "title", "description"],
                   "batch_size": 1000
               },
               # ... more defaults
           }
       
       def get(self, key: str, default=None) -> Any:
           """Get config value using dot notation: 'processing.parallel.max_collector_workers'"""
           keys = key.split('.')
           value = self._config
           for k in keys:
               if isinstance(value, dict) and k in value:
                   value = value[k]
               else:
                   return default
           return value
       
       def _merge_config(self, base: Dict, override: Dict):
           """Recursively merge override into base"""
           for key, value in override.items():
               if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                   self._merge_config(base[key], value)
               else:
                   base[key] = value
       
       def _load_env_overrides(self):
           """Load overrides from environment variables"""
           # Example: DATABASE_URL, OPENAI_API_KEY, etc.
           # Can add specific env var mappings here
           pass
   ```

2. Create `src/config/path_manager.py`:
   ```python
   from pathlib import Path
   from .config_manager import ConfigManager
   
   class PathManager:
       """Centralized path management"""
       
       def __init__(self, config_manager: ConfigManager):
           self.config = config_manager
           self.base_path = Path(config_manager.get("paths.base", ".")).resolve()
       
       @property
       def data_raw(self) -> Path:
           path = self.base_path / self.config.get("paths.data_raw", "data/raw")
           path.mkdir(parents=True, exist_ok=True)
           return path
       
       @property
       def data_processed(self) -> Path:
           path = self.base_path / self.config.get("paths.data_processed", "data/processed")
           path.mkdir(parents=True, exist_ok=True)
           return path
       
       @property
       def logs(self) -> Path:
           path = self.base_path / self.config.get("paths.logs", "logs")
           path.mkdir(parents=True, exist_ok=True)
           return path
       
       @property
       def logs_collectors(self) -> Path:
           path = self.base_path / self.config.get("paths.logs_collectors", "logs/collectors")
           path.mkdir(parents=True, exist_ok=True)
           return path
       
       def get_log_file(self, name: str) -> Path:
           return self.logs / name
   ```

3. Update `src/agent/core.py` to use ConfigManager:
   ```python
   from src.config.config_manager import ConfigManager
   from src.config.path_manager import PathManager
   
   class SentimentAnalysisAgent:
       def __init__(self, db_factory: sessionmaker, config_path="config/agent_config.json"):
           # Initialize config managers
           self.config_manager = ConfigManager(Path(config_path).parent)
           self.path_manager = PathManager(self.config_manager)
           
           # Use config instead of hardcoded values
           parallel_config = self.config_manager.get("processing.parallel", {})
           self.max_collector_workers = parallel_config.get("max_collector_workers", 8)
           self.max_sentiment_workers = parallel_config.get("max_sentiment_workers", 20)
           # ... etc
   ```

---

### Day 3: Remove Obvious Unused Code

**Priority: HIGH** - Quick wins, reduces codebase size

1. Remove from `src/agent/core.py`:
   ```python
   # REMOVE these methods:
   - run()  # Deprecated
   - process_data()  # Legacy sequential
   - update_metrics()  # Unused
   - optimize_system()  # Unused
   - save_config()  # Duplicate
   - cleanup_old_data()  # Unused
   - _run_collect_and_process()  # Redundant wrapper
   
   # REMOVE these imports:
   - from agent.brain import AgentBrain
   - from agent.autogen_agents import AutogenAgentSystem
   ```

2. Remove from `src/api/service.py`:
   ```python
   # REMOVE debug/test endpoints:
   - /debug-auth
   - /debug/*
   - /api/test
   
   # REMOVE legacy deduplication functions:
   - deduplicate_sentiment_data()
   - normalize_text_for_dedup()
   - remove_similar_content()
   - remove_similar_content_optimized()
   ```

3. Test that main flow still works:
   ```bash
   # Run a test cycle
   ./run_cycles.sh
   # Check logs for errors
   ```

---

### Day 4: Replace Hardcoded Paths

**Priority: HIGH** - High visibility improvement

1. Replace all hardcoded paths in `src/agent/core.py`:
   ```python
   # BEFORE:
   log_file = 'logs/agent.log'
   data_dir = Path('data/raw')
   
   # AFTER:
   log_file = str(self.path_manager.get_log_file('agent.log'))
   data_dir = self.path_manager.data_raw
   ```

2. Update collectors to use PathManager
3. Update `src/api/service.py` paths
4. Test paths are resolved correctly

---

### Day 5: Consolidate Deduplication

**Priority: MEDIUM** - Removes duplication

1. Ensure `DeduplicationService` is complete and configurable
2. Remove duplicate deduplication code:
   - From `service.py`
   - From `presidential_service.py`
3. Update all callers to use `DeduplicationService`
4. Make `DeduplicationService` use ConfigManager:
   ```python
   class DeduplicationService:
       def __init__(self, config_manager: ConfigManager = None):
           if config_manager is None:
               from src.config.config_manager import ConfigManager
               config_manager = ConfigManager()
           
           self.config = config_manager
           self.similarity_threshold = self.config.get("deduplication.similarity_threshold", 0.85)
           self.text_fields = self.config.get("deduplication.text_fields", ["text", "content", "title", "description"])
   ```

---

## 📊 Progress Tracking

After Week 1, you should have:
- ✅ Centralized configuration system
- ✅ Path management system
- ✅ Removed obvious unused code
- ✅ No hardcoded paths
- ✅ Single deduplication implementation

**Estimated code reduction**: 10-15%
**Estimated maintainability improvement**: 30-40%

---

## 🎯 Next Steps (Week 2+)

After Week 1, continue with:
1. **Replace remaining hardcoded values** (timeouts, thresholds, limits)
2. **Remove more unused endpoints** (verify usage first)
3. **Consolidate config loading** (all code uses ConfigManager)
4. **Add type hints** (improve code quality)
5. **Improve error handling** (standardize exceptions)
6. **Create tests** (ensure reliability)

See [`CLEANUP_AND_REFACTORING_PLAN.md`](./CLEANUP_AND_REFACTORING_PLAN.md) for complete plan.

---

## ⚠️ Important Notes

1. **Test frequently**: After each change, test the main flow
2. **Keep backups**: Commit after each successful change
3. **Document decisions**: Note why you're removing/changing code
4. **Incremental changes**: Don't try to do everything at once
5. **Verify before removing**: Double-check that code is truly unused

---

## 🔍 Verification Checklist

After each change:

- [ ] Code still runs without errors
- [ ] Main execution flow works (`run_cycles.sh` → cycle execution)
- [ ] Configuration is loaded correctly
- [ ] Paths resolve correctly
- [ ] No obvious regressions
- [ ] Logs look correct

---

**Remember**: This is a marathon, not a sprint. Focus on high-impact changes first, and make incremental improvements. Each week of cleanup makes the codebase significantly more maintainable.

