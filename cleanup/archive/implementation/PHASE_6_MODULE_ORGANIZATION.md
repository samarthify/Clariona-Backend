# Phase 6.3: Improve Module Organization

**Status**: 🚀 **IN PROGRESS**

## Overview

This step focuses on improving code organization, ensuring clear module boundaries, and standardizing import structures.

## Current Issues Identified

### 1. Import Organization
- Inconsistent import ordering
- Mixed absolute and relative imports
- Some imports scattered throughout files
- Path manipulation code mixed with imports

### 2. Module Responsibilities
- API layer should only handle HTTP requests/responses
- Business logic should be in service/processing layers
- Utility functions should be in utils
- Config logic should be in config module

### 3. Import Path Issues
- Some files use `sys.path.append()` for imports
- Inconsistent path manipulation patterns
- Some files have path setup code mixed with imports

## Standard Import Order

Following PEP 8 and best practices:

1. **Standard library imports** (os, sys, logging, etc.)
2. **Third-party imports** (fastapi, sqlalchemy, pandas, etc.)
3. **Local application imports** (from src.* or relative imports)
4. **Path setup** (if needed for imports)
5. **Module-level configuration** (logging setup, constants, etc.)

## Tasks

### Task 1: Standardize Import Order ✅ **IN PROGRESS**

**Files to Update**:
- `src/api/service.py` - Reorganize imports
- `src/api/presidential_service.py` - Reorganize imports
- `src/agent/core.py` - Reorganize imports
- `src/processing/*.py` - Reorganize imports
- `src/collectors/*.py` - Reorganize imports

**Standard Pattern**:
```python
# 1. Standard library
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any

# 2. Third-party
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

# 3. Local imports - config first
from config.path_manager import PathManager
from config.config_manager import ConfigManager
from config.logging_config import get_logger

# 4. Local imports - exceptions
from exceptions import APIError, DatabaseError

# 5. Local imports - utils
from utils.common import parse_datetime

# 6. Local imports - processing/agent/api
from processing.data_processor import DataProcessor
from agent.core import SentimentAnalysisAgent

# 7. Module-level setup
logger = get_logger(__name__)
```

### Task 2: Improve Import Path Handling

**Current Issues**:
- Multiple files use `sys.path.append()` or `sys.path.insert()`
- Inconsistent path manipulation

**Solution**:
- Use relative imports where possible
- Use absolute imports from `src.*` where needed
- Centralize path setup if necessary
- Document why path manipulation is needed

### Task 3: Ensure Separation of Concerns

**Review and Fix**:
- ✅ Business logic should not be in API layer
- ✅ API layer should only handle HTTP concerns
- ✅ Processing logic in processing modules
- ✅ Utility functions in utils modules
- ✅ Config logic in config modules

## Progress

### Completed
- ✅ Created module organization documentation
- ✅ Identified import organization issues
- ✅ Defined standard import order pattern
- ✅ Standardized import order in 8+ key modules:
  - API modules: `service.py`, `presidential_service.py`
  - Processing modules: `presidential_sentiment_analyzer.py`, `governance_analyzer.py`, `issue_classifier.py`
  - Agent module: `core.py`
  - Collector modules: `collect_rss.py`, `collect_radio_gnews.py`

### In Progress
- 🚀 Reviewing separation of concerns
- 🚀 Ensuring proper module boundaries

### Pending
- [ ] Review all modules for separation of concerns
- [ ] Move any misplaced business logic
- [ ] Improve import path handling
- [ ] Document module responsibilities

