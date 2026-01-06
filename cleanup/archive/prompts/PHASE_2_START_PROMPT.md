# Phase 2 Start Prompt

Copy and paste this prompt into a new chat to start Phase 2:

---

```
I need you to help me implement Phase 2 of a backend cleanup and refactoring project. 

## Context

I have a Python FastAPI backend for a data collection, processing, and storage pipeline. Phase 1 analysis is complete with comprehensive documentation in the `cleanup/` folder.

**Key Phase 1 Findings**:
- Main execution flow: `run_cycles.sh` → `/agent/test-cycle-no-auth` → `run_single_cycle_parallel()` → 5 phases (Collection → Load → Deduplication → Sentiment → Location)
- 250+ hardcoded values across 16 categories identified
- 1800-2700 lines of unused code identified (will be removed)
- 500-600 lines of duplicate code identified
- 10 config files, 50+ environment variables, no centralized management

## Phase 2 Goal: Configuration System

Create a centralized configuration management system to replace all scattered config loading and hardcoded values.

## What I Need

Please read these key documents from the `cleanup/` folder to understand the current state:

1. **CLEANUP_AND_REFACTORING_PLAN.md** - Master plan, Phase 2 details (Steps 2.1-2.4)
2. **CONFIGURATION_MAP.md** - How configs are currently loaded/used
3. **HARDCODED_VALUES_AUDIT.md** - All hardcoded values to configure (250+, but ~15-20 will be removed with unused code)
4. **DUPLICATE_CODE_AUDIT.md** - Duplicate code patterns (especially config loading and path resolution)
5. **EXECUTION_FLOW_MAP.md** - What code is actually used

## Phase 2 Steps (from plan)

### Step 2.1: Design Config Schema
- Design unified configuration schema
- Define config hierarchy (env vars > config files > defaults)
- Create JSON schema for validation

### Step 2.2: Implement ConfigManager
- Create `src/config/config_manager.py`
- Implement config loading with environment variable override
- Type-safe accessors (get, get_int, get_float, get_path, etc.)
- Dot-notation access (e.g., "processing.parallel.max_collector_workers")

### Step 2.3: Migrate Existing Config Files
- Merge related config files
- Update structure to match new schema
- Ensure backward compatibility during migration

### Step 2.4: Create PathManager
- Create `src/config/path_manager.py`
- Centralize path resolution (replace 30+ duplicate `Path(__file__).parent.parent.parent` calculations)
- Use ConfigManager for path configuration

## Implementation Guidelines

1. **Reference the cleanup documentation** - All analysis is in `cleanup/` folder
2. **Use recommended config structure** from `HARDCODED_VALUES_AUDIT.md` section "Recommended Configuration Structure"
3. **Follow the plan** in `CLEANUP_AND_REFACTORING_PLAN.md` Phase 2
4. **Keep it simple** - Don't over-engineer, focus on replacing current patterns
5. **Backward compatibility** - Existing code should still work during migration

## Questions to Consider

- Should I start with Step 2.1 (design schema) or jump to 2.2 (implement ConfigManager)?
- How should we handle the migration? All at once or gradual?
- Should PathManager be separate or part of ConfigManager?

Let's start Phase 2! What would you like to tackle first?
```

---

**Note**: This prompt provides all necessary context to start Phase 2. The assistant should read the cleanup documentation to understand the current state and proceed with implementation.






