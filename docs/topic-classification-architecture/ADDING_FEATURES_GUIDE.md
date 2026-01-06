# Guide: Adding New Features to the Classification System

**Last Updated**: 2024-12-19  
**Purpose**: Guide for developers adding new features to the classification system

---

## 📋 Overview

This guide provides patterns and best practices for adding new features to the classification system while maintaining code quality, performance, and consistency.

---

## 🏗️ Architecture Overview

### Current System Components

1. **Classification Layer**
   - `TopicClassifier` - Multi-topic classification
   - `PresidentialSentimentAnalyzer` - Sentiment analysis
   - `EmotionAnalyzer` - Emotion detection

2. **Processing Layer**
   - `DataProcessor` - Main orchestrator
   - `IssueDetectionEngine` - Issue detection
   - `SentimentAggregationService` - Aggregation

3. **Database Layer**
   - PostgreSQL with SQLAlchemy ORM
   - Alembic migrations

---

## ✅ Code Standards (MUST FOLLOW)

### 1. Import Order
```python
# Standard library imports
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Third-party imports
from sqlalchemy.orm import Session
import numpy as np

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from config.logging_config import get_logger
from config.path_manager import PathManager

# Local imports - processing/database
from processing.xxx import XXX
from api.models import XXX
```

### 2. Logging
```python
# Always use centralized logging
from config.logging_config import get_logger

logger = get_logger(__name__)

# Use appropriate log levels
logger.debug("Detailed debugging info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### 3. Configuration
```python
# Never hardcode values - use ConfigManager
from config.config_manager import ConfigManager

config = ConfigManager()
value = config.get_int('processing.feature.setting', default_value)
threshold = config.get_float('processing.feature.threshold', 0.5)
enabled = config.get_bool('processing.feature.enabled', True)
```

### 4. Path Management
```python
# Use PathManager for all file paths
from config.path_manager import PathManager

paths = PathManager()
data_dir = paths.data_raw
config_file = paths.config_file
```

### 5. Error Handling
```python
# Always handle errors gracefully
try:
    # Operation
    result = process_data()
except SpecificException as e:
    logger.error(f"Error processing data: {e}", exc_info=True)
    # Return safe default or re-raise
    return default_value
```

---

## 🆕 Adding a New Classification Feature

### Step 1: Create the Class

**File**: `src/processing/new_feature.py`

```python
"""
New Feature - Description of what it does.

Week X: Feature description
"""

# Standard library imports
from typing import Dict, List, Any, Optional
import sys
from pathlib import Path

# Third-party imports
from sqlalchemy.orm import Session

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from config.logging_config import get_logger

# Local imports - database
from api.database import SessionLocal
from api.models import XXX

# Module-level setup
logger = get_logger(__name__)


class NewFeature:
    """
    Description of the new feature.
    
    Week X: Feature implementation
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the feature."""
        # Load configuration
        try:
            config = ConfigManager()
            self.setting = config.get_float('processing.feature.setting', 0.5)
        except Exception as e:
            logger.warning(f"Could not load ConfigManager: {e}. Using defaults.")
            self.setting = 0.5
        
        self.db = db_session
        logger.debug("NewFeature initialized")
    
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data and return results."""
        try:
            # Processing logic
            result = self._calculate(data)
            return result
        except Exception as e:
            logger.error(f"Error processing data: {e}", exc_info=True)
            raise
```

### Step 2: Integrate into DataProcessor

**File**: `src/processing/data_processor.py`

```python
# In __init__
try:
    from .new_feature import NewFeature
    self.new_feature = NewFeature()
    logger.debug("NewFeature initialized")
except Exception as e:
    logger.warning(f"Could not initialize NewFeature: {e}")
    self.new_feature = None

# Add method
def process_with_new_feature(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Process data with new feature."""
    if not self.new_feature:
        logger.warning("NewFeature not initialized")
        return {}
    
    return self.new_feature.process(data)
```

### Step 3: Add Database Models (if needed)

**File**: `src/api/models.py`

```python
class NewFeatureData(Base):
    """Table for new feature data."""
    __tablename__ = 'new_feature_data'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Add columns
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Step 4: Create Migration (if needed)

**File**: `src/alembic/versions/XXXX_add_new_feature.py`

```python
def upgrade():
    # Check if table exists
    if not table_exists('new_feature_data'):
        op.create_table(
            'new_feature_data',
            # Column definitions
        )
```

### Step 5: Add Configuration

**File**: `config.yaml` (or ConfigManager)

```yaml
processing:
  feature:
    setting: 0.5
    threshold: 0.3
    enabled: true
```

---

## 🔧 Adding a New Aggregation Feature

### Pattern

```python
class NewAggregationService:
    """Aggregate data by dimension."""
    
    def __init__(self, db_session: Optional[Session] = None):
        # Initialize with ConfigManager
        # Set up database session
    
    def aggregate_by_dimension(
        self,
        dimension_key: str,
        time_window: str = '24h'
    ) -> Optional[Dict[str, Any]]:
        """Aggregate by dimension."""
        # Get data
        # Calculate aggregation
        # Store in database
        # Return result
```

### Integration

```python
# In DataProcessor
self.aggregation_service = NewAggregationService()

def aggregate_new_dimension(self, key: str) -> Dict[str, Any]:
    return self.aggregation_service.aggregate_by_dimension(key)
```

---

## 🧪 Testing New Features

### Test File Structure

**File**: `tests/test_new_feature.py`

```python
"""
Test script for New Feature
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.new_feature import NewFeature
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_new_feature():
    """Test new feature."""
    feature = NewFeature()
    result = feature.process(test_data)
    assert result is not None
    return True


def run_all_tests():
    """Run all tests."""
    results = {}
    try:
        results['test1'] = test_new_feature()
        # Count successes
        passed = sum(1 for v in results.values() if v is True)
        logger.info(f"✅ Passed: {passed}")
        return passed == len(results)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
```

---

## 📝 Documentation Requirements

### 1. Update DEVELOPER_GUIDE.md
- Add new pattern section
- Include code examples
- Document configuration options

### 2. Update BACKEND_ARCHITECTURE.md
- Add component to architecture diagram
- Document data flow
- Update version number

### 3. Code Comments
- Docstrings for all classes/methods
- Type hints throughout
- Inline comments for complex logic

---

## 🔍 Common Patterns

### Database Session Management
```python
def _get_db_session(self) -> Session:
    """Get database session."""
    if self.db:
        return self.db
    return SessionLocal()

def _close_db_session(self, session: Session):
    """Close session if we created it."""
    if not self.db and session:
        session.close()
```

### Configuration with Fallbacks
```python
try:
    config = ConfigManager()
    value = config.get_float('key.path', default_value)
except Exception as e:
    logger.warning(f"Could not load config: {e}. Using default.")
    value = default_value
```

### Error Handling Pattern
```python
try:
    result = operation()
    return result
except SpecificError as e:
    logger.error(f"Error: {e}", exc_info=True)
    # Handle error
    return safe_default
finally:
    # Cleanup
    cleanup()
```

---

## ✅ Checklist

Before submitting a new feature:

- [ ] Follows import order (standard → third-party → local)
- [ ] Uses `get_logger(__name__)` for logging
- [ ] Uses `ConfigManager` for all configuration
- [ ] Uses `PathManager` for file paths
- [ ] Has comprehensive error handling
- [ ] Includes type hints
- [ ] Has docstrings for all public methods
- [ ] Includes unit tests
- [ ] Updates DEVELOPER_GUIDE.md
- [ ] Updates BACKEND_ARCHITECTURE.md
- [ ] No hardcoded values
- [ ] Database operations use transactions
- [ ] Proper session management

---

## 📚 Reference

- **DEVELOPER_GUIDE.md** - Complete coding standards
- **BACKEND_ARCHITECTURE.md** - System architecture
- **MASTER_IMPLEMENTATION_PLAN.md** - Implementation patterns

---

**Last Updated**: 2024-12-19





