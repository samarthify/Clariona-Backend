# Developer Guide - Clariona Backend

**Version**: 2.5 (Week 6: Testing & Optimization)  
**Date**: 2024-12-19

This guide provides comprehensive information for developers working on the Clariona Backend codebase.

---

## 📋 Table of Contents

1. [Getting Started](#getting-started)
2. [Code Structure](#code-structure)
3. [Configuration System](#configuration-system)
4. [Path Management](#path-management)
5. [Error Handling](#error-handling)
6. [Logging](#logging)
7. [Coding Standards](#coding-standards)
8. [Type Hints](#type-hints)
9. [Testing](#testing)
10. [Database](#database)
11. [Common Patterns](#common-patterns)

---

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Git

### Setup

1. **Clone Repository**:
```bash
git clone <repository-url>
cd Clariona-Backend
```

2. **Create Virtual Environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

4. **Setup Environment Variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run Database Migrations**:
```bash
alembic upgrade head
```

6. **Populate Configuration Database** (Optional):
```bash
python scripts/populate_config_database.py
```

7. **Run the Unified Streaming Service**:
```bash
# Starts Collection + Analysis + Scheduling in one process
python -m src.services.main
```

### Project Structure

```
Clariona-Backend/
├── src/
│   ├── agent/              # Core agent orchestration
│   ├── api/                # FastAPI service
│   ├── config/             # Configuration management
│   ├── collectors/         # Data collection modules
│   ├── processing/         # Data processing and analysis
│   ├── utils/              # Utility services
│   ├── exceptions.py       # Custom exception classes
│   └── alembic/            # Database migrations
├── config/                 # Configuration files
├── data/                   # Data directories
├── logs/                   # Log files
├── tests/                  # Test files
└── scripts/                # Utility scripts
```

---

## Code Structure

### Module Organization

The codebase follows a clear separation of concerns:

#### 1. **Agent Layer** (`src/agent/`)
- **Purpose**: Orchestrates the complete data pipeline
- **Key Files**:
  - `core.py` - Main `SentimentAnalysisAgent` class
  - `llm_providers.py` - LLM provider abstractions

#### 2. **API Layer** (`src/api/`)
- **Purpose**: FastAPI endpoints (minimal, mostly for triggering cycles)
- **Key Files**:
  - `service.py` - API endpoints
  - `models.py` - SQLAlchemy database models
  - `database.py` - Database session factory
  - `auth.py` - Authentication

#### 3. **Configuration Layer** (`src/config/`)
- **Purpose**: Centralized configuration and path management
- **Key Files**:
  - `config_manager.py` - Configuration management
  - `path_manager.py` - Path management
  - `logging_config.py` - Logging configuration

#### 4. **Collectors Layer** (`src/collectors/`)
- **Purpose**: Data collection from various sources
- **Key Files**:
  - `collect_*.py` - Individual collectors (Twitter, Facebook, News, etc.)
  - `run_collectors.py` - Collector execution orchestrator
  - `target_config_manager.py` - Collector configuration

#### 5. **Processing Layer** (`src/processing/`)
- **Purpose**: Data processing and analysis
- **Key Files**:
  - `data_processor.py` - Main processing orchestrator
  - `presidential_sentiment_analyzer.py` - Sentiment analysis
  - `governance_analyzer.py` - Ministry/issue classification
  - `topic_classifier.py` - Topic-based classification (Week 2)
  - `emotion_analyzer.py` - Emotion detection (Week 3)
  - `sentiment_weight_calculator.py` - Influence weight calculation (Week 3)
  - `weighted_sentiment_calculator.py` - Weighted sentiment scoring (Week 3)
  - `issue_clustering_service.py` - Issue clustering (Week 4)
  - `issue_detection_engine.py` - Issue detection and management (Week 4)
  - `issue_lifecycle_manager.py` - Issue lifecycle management (Week 4)
  - `issue_priority_calculator.py` - Issue priority calculation (Week 4)
  - `sentiment_aggregation_service.py` - Sentiment aggregation (Week 5)
  - `sentiment_trend_calculator.py` - Sentiment trend calculation (Week 5)
  - `topic_sentiment_normalizer.py` - Topic sentiment normalization (Week 5)

#### 6. **Utils Layer** (`src/utils/`)
- **Purpose**: Shared utility functions
- **Key Files**:
  - `deduplication_service.py` - Deduplication logic
  - `common.py` - Common utility functions
  - `collection_tracker.py` - Collection tracking

### Import Order

Follow this standard import order:

```python
# 1. Standard library imports
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# 2. Third-party imports
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

# 3. Local imports - config (first)
from src.config.path_manager import PathManager
from src.config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# 4. Local imports - exceptions
from exceptions import ConfigError, CollectionError, ProcessingError

# 5. Local imports - utils
from src.utils.common import parse_datetime, safe_int

# 6. Local imports - processing/agent/api
from src.processing.data_processor import DataProcessor
from src.agent.core import SentimentAnalysisAgent

# 7. Module-level setup
logger = get_logger(__name__)
```

---

## Configuration System

### ConfigManager

**Purpose**: Centralized configuration management with support for multiple sources.

**Usage**:
```python
from src.config.config_manager import ConfigManager

# Initialize ConfigManager
config = ConfigManager()

# Access configuration values
max_workers = config.get_int('processing.parallel.max_collector_workers', 8)
timeout = config.get_int('collectors.twitter.timeout', 300)
similarity = config.get_float('deduplication.similarity_threshold', 0.85)
enabled = config.get_bool('collectors.twitter.enabled', True)
keywords = config.get_list('collectors.twitter.keywords', [])
settings = config.get_dict('collectors.twitter', {})
log_path = config.get_path('paths.logs', 'logs')
```

### Configuration Priority

1. **Environment Variables** (highest priority)
2. **Database Configuration** (if `use_database=True`)
3. **JSON Config Files** (`config/` directory)
4. **Default Values** (hardcoded in ConfigManager)

### Database-Backed Configuration

**For Runtime Configuration Editing**:
```python
from src.config.config_manager import ConfigManager
from src.api.database import SessionLocal

db = SessionLocal()
config = ConfigManager(use_database=True, db_session=db)
# Configuration is now loaded from SystemConfiguration table
```

**See**: `docs/FRONTEND_CONFIG_MANAGEMENT_GUIDE.md` for frontend integration.

### Adding New Configuration

**See**: `docs/ADDING_NEW_CONFIGS_GUIDE.md` for detailed instructions.

**Quick Steps**:
1. Add default value to `ConfigManager._get_default_config()`
2. Add to database (if using database-backed config)
3. Use in code: `config.get('your.new.key', default_value)`

---

## Path Management

### PathManager

**Purpose**: Centralized path management, eliminating hardcoded path calculations.

**Usage**:
```python
from src.config.path_manager import PathManager

# Initialize PathManager
paths = PathManager()

# Access common paths
data_raw = paths.data_raw  # data/raw/ (auto-creates directory)
data_processed = paths.data_processed  # data/processed/
logs_dir = paths.logs  # logs/
config_dir = paths.config_dir  # config/

# Get custom log files
log_file = paths.get_log_file("my_log.log", subdirectory="custom")
collector_log = paths.get_collector_log_dir("twitter")
```

### Available Path Properties

- `paths.data_raw` - Raw data directory
- `paths.data_processed` - Processed data directory
- `paths.logs` - Logs directory
- `paths.logs_agent` - Agent log file
- `paths.logs_scheduling` - Scheduling log file
- `paths.logs_collectors` - Collectors log directory
- `paths.logs_openai` - OpenAI calls log file
- `paths.config_dir` - Configuration directory
- `paths.config_agent` - Agent config file
- `paths.config_topic_embeddings` - Topic embeddings config file

**Note**: All directory paths automatically create the directory if it doesn't exist.

---

## Error Handling

### Custom Exceptions

**Purpose**: Structured error handling with consistent error messages.

**Exception Hierarchy**:
```
BackendError (base class)
├── ConfigError - Configuration errors
├── PathError - Path-related errors
├── CollectionError - Data collection errors
├── ProcessingError - Data processing errors
│   └── AnalysisError - Analysis-specific errors
├── DatabaseError - Database operation errors
├── APIError - API-related errors
├── ValidationError - Data validation errors
├── RateLimitError - Rate limit errors (with retry_after)
├── OpenAIError - OpenAI API errors
├── NetworkError - Network-related errors
├── FileError - File operation errors
└── LockError - Lock-related errors
```

### Usage

**Raising Exceptions**:
```python
from exceptions import ConfigError, CollectionError

# Simple error
if not config_key:
    raise ConfigError("Configuration key is required")

# Error with details
if not config_path.exists():
    raise ConfigError(
        f"Config file not found: {config_path}",
        details={"config_path": str(config_path), "context": "initialization"}
    )

# Rate limit error with retry_after
if rate_limit_exceeded:
    raise RateLimitError(
        "Rate limit exceeded",
        retry_after=60.0,  # seconds
        details={"endpoint": endpoint, "limit": limit}
    )
```

**Catching Exceptions**:
```python
from exceptions import ConfigError, CollectionError, BackendError

try:
    # Some operation
    config = ConfigManager()
except ConfigError as e:
    logger.error(f"Configuration error: {e.message}", extra=e.details)
    # Handle config error
except CollectionError as e:
    logger.error(f"Collection error: {e.message}", extra=e.details)
    # Handle collection error
except BackendError as e:
    logger.error(f"Backend error: {e.message}", extra=e.details)
    # Handle any backend error
```

---

## Logging

### Setup

**At Application Start**:
```python
from src.config.logging_config import setup_logging
from src.config.config_manager import ConfigManager
from src.config.path_manager import PathManager

config = ConfigManager()
paths = PathManager(config)
setup_logging(config_manager=config, path_manager=paths)
```

### Usage in Modules

**Get Logger**:
```python
from src.config.logging_config import get_logger

logger = get_logger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
logger.critical("Critical message")
```

### Configuration

**Via ConfigManager**:
- `logging.level` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logging.format` - Log message format
- `logging.file_path` - Log file path
- `logging.max_bytes` - Maximum log file size before rotation
- `logging.backup_count` - Number of backup log files to keep

### Log Files

- `logs/backend.log` - Main backend log (rotated)
- `logs/agent.log` - Agent-specific log
- `logs/automatic_scheduling.log` - Cycle scheduling log
- `logs/collectors/` - Collector-specific logs

---

## Coding Standards

### Code Style

- **PEP 8**: Follow Python PEP 8 style guide
- **Type Hints**: Use type hints for all function signatures
- **Docstrings**: Add docstrings to all public functions and classes
- **Line Length**: Maximum 120 characters (soft limit)

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `ConfigManager`, `PathManager`)
- **Functions/Methods**: `snake_case` (e.g., `get_config`, `setup_logging`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_WORKERS`, `DEFAULT_TIMEOUT`)
- **Variables**: `snake_case` (e.g., `max_workers`, `config_path`)

### Function Signatures

**Always include type hints**:
```python
def process_data(
    data: List[Dict[str, Any]],
    config: Optional[ConfigManager] = None,
    timeout: int = 300
) -> List[Dict[str, Any]]:
    """
    Process data with optional configuration.
    
    Args:
        data: List of data records to process
        config: Optional ConfigManager instance
        timeout: Processing timeout in seconds
    
    Returns:
        List of processed data records
    
    Raises:
        ProcessingError: If processing fails
    """
    pass
```

### Docstrings

**Use Google-style docstrings**:
```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of the function.
    
    Longer description if needed, explaining what the function does,
    any important details, or usage examples.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this exception is raised
    
    Example:
        >>> result = function_name("test", 42)
        >>> print(result)
        True
    """
    pass
```

### Error Handling

**Always use custom exceptions**:
```python
from exceptions import ConfigError, ProcessingError

# Good
if not config_path.exists():
    raise ConfigError(f"Config file not found: {config_path}")

# Bad
if not config_path.exists():
    raise ValueError(f"Config file not found: {config_path}")
```

### Configuration Access

**Always use ConfigManager**:
```python
from src.config.config_manager import ConfigManager

config = ConfigManager()
timeout = config.get_int('collectors.twitter.timeout', 300)

# Good - uses ConfigManager
# Bad - hardcoded value: timeout = 300
```

### Path Management

**Always use PathManager**:
```python
from src.config.path_manager import PathManager

paths = PathManager()
data_dir = paths.data_raw

# Good - uses PathManager
# Bad - hardcoded: data_dir = Path("data/raw")
```

---

## Type Hints

### Basic Types

```python
from typing import Dict, List, Any, Optional, Union

def process_data(
    data: List[Dict[str, Any]],
    config: Optional[ConfigManager] = None
) -> Dict[str, Any]:
    pass
```

### Optional Types

**Use `Optional[T]` for nullable values**:
```python
from typing import Optional

def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    pass
```

### Return Types

**Always specify return types**:
```python
def get_value() -> int:
    return 42

def process_data() -> List[Dict[str, Any]]:
    return []

def may_return_none() -> Optional[str]:
    return None
```

### Type Checking

**Run mypy**:
```bash
mypy src/
```

**Configuration**: See `mypy.ini` for mypy configuration.

---

## Testing

### Running Tests

**All Tests**:
```bash
pytest tests/
```

**Specific Test File**:
```bash
pytest tests/test_config_manager.py
```

**With Coverage**:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Writing Tests

**Test Structure**:
```python
import pytest
from src.config.config_manager import ConfigManager

class TestConfigManager:
    def test_get_int(self):
        config = ConfigManager()
        value = config.get_int('processing.parallel.max_collector_workers', 8)
        assert value == 8
    
    def test_get_with_default(self):
        config = ConfigManager()
        value = config.get('non.existent.key', 'default')
        assert value == 'default'
```

### Test Organization

- **Unit Tests**: `tests/test_*.py` - Test individual functions/classes
- **Integration Tests**: `tests/test_integration.py` - Test component interactions
- **Manual Tests**: `tests/test_manual_*.py` - Manual verification scripts

---

## Database

### Models

**Location**: `src/api/models.py`

**Key Models**:
- `SentimentData` - Main data table
- `SystemConfiguration` - Runtime configuration
- `Topic` - Topic definitions
- `OwnerConfig` - Owner/topic configurations

### Database Session

**Usage**:
```python
from src.api.database import SessionLocal

db = SessionLocal()
try:
    # Use database session
    records = db.query(models.SentimentData).all()
finally:
    db.close()
```

### Migrations

**Create Migration**:
```bash
alembic revision --autogenerate -m "description"
```

**Run Migrations**:
```bash
alembic upgrade head
```

**Rollback**:
```bash
alembic downgrade -1
```

---

## Common Patterns

### Topic Classification Pattern (Week 2)

**New**: Parallel Topic + Sentiment Classification

The `DataProcessor` now runs Topic and Sentiment classification in parallel:

```python
from processing.data_processor import DataProcessor

processor = DataProcessor()
result = processor.get_sentiment(text="Your text here")

# Result includes:
# - sentiment_label, sentiment_score, sentiment_justification
# - topics: List of topic classifications
# - primary_topic_key, primary_topic_name
# - embedding: 1536-dim vector
```

**Direct TopicClassifier Usage**:
```python
from processing.topic_classifier import TopicClassifier

classifier = TopicClassifier()
topics = classifier.classify(text="Your text", text_embedding=embedding)
# Returns: [{topic, topic_name, confidence, keyword_score, embedding_score}, ...]
```

**Storing Topics in Database**:
```python
from api.models import MentionTopic

for topic in result['topics']:
    mention_topic = MentionTopic(
        mention_id=mention_id,
        topic_key=topic['topic'],  # Note: TopicClassifier uses 'topic' key
        topic_confidence=topic['confidence'],
        keyword_score=topic.get('keyword_score'),
        embedding_score=topic.get('embedding_score')
    )
    session.add(mention_topic)
```

### Safe Concurrent Processing Pattern (Week 2)

**Pattern**: Using `processing_status` for safe concurrent processing

```python
from api.models import SentimentData
from datetime import datetime

# 1. Claim records (atomic, with SKIP LOCKED)
records = session.query(SentimentData).filter(
    SentimentData.processing_status == 'pending',
    SentimentData.sentiment_label.is_(None)
).with_for_update(skip_locked=True).limit(100).all()

# 2. Mark as processing
for record in records:
    record.processing_status = 'processing'
    record.processing_started_at = datetime.now()
session.commit()

# 3. Process (no DB access during processing)
# ... process records ...

# 4. Update results
for record in records:
    record.processing_status = 'completed'
    record.processing_completed_at = datetime.now()
session.commit()
```

- Always handle failures and mark as 'failed' for retry

### Polling Analysis Pattern (New)

**Purpose**: High-throughput real-time analysis without complex queue management.

```python
from src.services.analysis_worker import AnalysisWorker

# Initialize worker with parallel threads
worker = AnalysisWorker(
    max_workers=10,        # 10 parallel analysis threads
    poll_interval=2.0,     # Poll every 2 seconds
    batch_size=50          # Process 50 records per batch
)

# Start polling loop
worker.start()
```

**Key Optimizations**:
- **Database Index**: Uses index on `sentiment_label` for instant SELECTs.
- **Self-Healing**: Automatically picks up any records missed by previous runs.
- **Parallelism**: Uses `ThreadPoolExecutor` to parallelize OpenAI API calls.

---

### Emotion Detection Pattern (Week 3)

**New**: Detect emotions in addition to sentiment polarity

```python
from processing.emotion_analyzer import EmotionAnalyzer

analyzer = EmotionAnalyzer()
result = analyzer.analyze_emotion("I'm furious about the fuel price increase!")

# Returns:
# {
#     'emotion_label': 'anger',
#     'emotion_score': 0.75,
#     'emotion_distribution': {
#         'anger': 0.75,
#         'fear': 0.15,
#         'sadness': 0.05,
#         'trust': 0.02,
#         'joy': 0.02,
#         'disgust': 0.01
#     }
# }
```

**Emotions Detected**: Anger, Fear, Trust, Sadness, Joy, Disgust

---

### Sentiment Weight Calculation Pattern (Week 3)

**New**: Calculate influence and confidence weights

```python
from processing.sentiment_weight_calculator import SentimentWeightCalculator

calculator = SentimentWeightCalculator()

# Calculate influence weight (1.0-5.0)
influence_weight = calculator.calculate_influence_weight(
    source_type="twitter",
    user_verified=True,
    reach=100000
)
# Returns: ~1.95 (1.0 base * 1.5 verified * 1.3 high reach)

# Calculate confidence weight (0.0-1.0)
confidence_weight = calculator.calculate_confidence_weight(
    sentiment_score=-0.8,
    emotion_score=0.7
)
# Returns: 0.75 (average of sentiment and emotion confidence)
```

**Weight Ranges**:
- Influence: 1.0 (citizen post) to 5.0 (presidency statement)
- Confidence: 0.0 (uncertain) to 1.0 (very confident)

---

### Weighted Sentiment Calculation Pattern (Week 3)

**New**: Calculate weighted sentiment scores and sentiment index

```python
from processing.weighted_sentiment_calculator import WeightedSentimentCalculator

calculator = WeightedSentimentCalculator()

mentions = [
    {'sentiment_label': 'negative', 'sentiment_score': -0.8, 
     'influence_weight': 5.0, 'confidence_weight': 0.9},
    {'sentiment_label': 'positive', 'sentiment_score': 0.5,
     'influence_weight': 1.0, 'confidence_weight': 0.7},
]

result = calculator.calculate_weighted_sentiment(mentions)
# Returns:
# {
#     'weighted_sentiment_score': -0.58,  # Weighted average
#     'sentiment_index': 21.0,            # 0-100 scale (0=most negative, 100=most positive)
#     'mention_count': 2,
#     'total_influence_weight': 6.0
# }

# Convert single score to index
index = calculator.calculate_sentiment_index(-0.8)
# Returns: 10.0 (on 0-100 scale)
```

**Sentiment Index**: 0 (most negative) to 100 (most positive), 50 = neutral

---

### Issue Detection Pattern (Week 4)

**New**: Clustering-based issue detection from mentions

```python
from processing.data_processor import DataProcessor

processor = DataProcessor()

# Detect issues for a specific topic
issues = processor.detect_issues_for_topic('healthcare', limit=100)

# Returns list of created/updated issues:
# [
#     {
#         'issue_id': 'uuid',
#         'issue_slug': 'healthcare-20241219-abc123',
#         'action': 'created',  # or 'updated'
#         'mentions_count': 5
#     },
#     ...
# ]

# Detect issues for all topics
all_issues = processor.detect_issues_for_all_topics(limit_per_topic=50)
# Returns: {'topic_key': [issues], ...}
```

**Issue Detection Process**:
1. Get mentions for topic (without existing issues)
2. Cluster similar mentions (embedding similarity + time proximity)
3. Match clusters to existing issues
4. Create new issues OR update existing issues
5. Calculate priority and update lifecycle

---

### Issue Clustering Pattern (Week 4)

**New**: Group similar mentions into clusters

```python
from processing.issue_clustering_service import IssueClusteringService

clustering_service = IssueClusteringService(
    similarity_threshold=0.75,  # Embedding similarity threshold
    min_cluster_size=3,         # Minimum mentions per cluster
    time_window_hours=24        # Time window for clustering
)

# Cluster mentions for a topic
clusters = clustering_service.cluster_mentions(mentions, 'healthcare')

# Returns: List of clusters, each containing similar mentions
# [
#     [mention1, mention2, mention3],  # Cluster 1
#     [mention4, mention5],            # Cluster 2
#     ...
# ]
```

**Clustering Algorithm**:
- Uses embedding cosine similarity (threshold: 0.75)
- Groups mentions within time window (24 hours)
- Minimum cluster size: 3 mentions
- Calculates cluster centroid for matching

---

### Issue Lifecycle Management Pattern (Week 4)

**New**: Automatic lifecycle state management

```python
from processing.issue_lifecycle_manager import IssueLifecycleManager

manager = IssueLifecycleManager()

# Update issue lifecycle based on metrics
result = manager.update_lifecycle(issue, session)

# Returns:
# {
#     'state': 'active',  # emerging, active, escalated, stabilizing, resolved, archived
#     'reason': 'High mention count and negative sentiment',
#     'transitions': []
# }
```

**Lifecycle States**:
- `emerging` - New issue (< 3 mentions or < 24 hours)
- `active` - Growing issue (3+ mentions, increasing)
- `escalated` - High priority (negative sentiment, high volume)
- `stabilizing` - Slowing down (decreasing mentions)
- `resolved` - No new mentions (7+ days inactive)
- `archived` - Manually archived

**Automatic Transitions**:
- Based on mention count, sentiment, time, and velocity
- State changes logged with reasons

---

### Issue Priority Calculation Pattern (Week 4)

**New**: Multi-factor priority scoring

```python
from processing.issue_priority_calculator import IssuePriorityCalculator

calculator = IssuePriorityCalculator()

# Calculate priority for an issue
result = calculator.calculate_priority(issue, session)

# Returns:
# {
#     'priority_score': 75.5,      # 0-100
#     'priority_band': 'high',     # critical, high, medium, low
#     'sentiment_score': 30.0,     # Component scores
#     'volume_score': 25.0,
#     'time_score': 20.5
# }
```

**Priority Formula**:
```
priority_score = (
    sentiment_weight * sentiment_score +
    volume_weight * volume_score +
    time_weight * time_score
)
```

**Priority Bands**:
- `critical`: 80-100 (urgent action needed)
- `high`: 60-79 (important, monitor closely)
- `medium`: 40-59 (standard priority)
- `low`: 0-39 (low priority)

**Factors**:
- **Sentiment**: Negative sentiment increases priority
- **Volume**: More mentions = higher priority
- **Time**: Recent activity = higher priority
- **Velocity**: Rapid growth = higher priority

---

### Issue Database Storage Pattern (Week 4)

**New**: Store issues and relationships

```python
from api.models import TopicIssue, IssueMention, TopicIssueLink

# Issue record (topic_issues table)
issue = TopicIssue(
    id=uuid4(),
    issue_slug='healthcare-20241219-abc123',
    issue_label='Healthcare Access Issues',
    topic_key='healthcare',
    primary_topic_key='healthcare',
    state='active',
    priority_score=75.5,
    priority_band='high',
    mention_count=10,
    start_time=datetime.now() - timedelta(days=2),
    last_activity=datetime.now()
)

# Mention link (issue_mentions table)
issue_mention = IssueMention(
    id=uuid4(),
    issue_id=issue.id,
    mention_id=mention.entry_id,
    similarity_score=0.85,
    topic_key='healthcare'
)

# Topic link (topic_issue_links table)
topic_link = TopicIssueLink(
    id=uuid4(),
    topic_key='healthcare',
    issue_id=issue.id,
    mention_count=10
)
```

**Database Tables**:
- `topic_issues`: Issue definitions with lifecycle and priority
- `issue_mentions`: Junction table linking mentions to issues
- `topic_issue_links`: Many-to-many relationship between topics and issues

---

### Sentiment Aggregation Pattern (Week 5)

**New**: Aggregate sentiment by topic, issue, or entity across time windows

```python
from processing.data_processor import DataProcessor

processor = DataProcessor()

# Aggregate sentiment for a topic
aggregation = processor.aggregate_sentiment_for_topic('healthcare', time_window='24h')

# Returns:
# {
#     'aggregation_type': 'topic',
#     'aggregation_key': 'healthcare',
#     'time_window': '24h',
#     'weighted_sentiment_score': -0.25,
#     'sentiment_index': 37.5,  # 0-100 scale
#     'sentiment_distribution': {'positive': 0.2, 'negative': 0.6, 'neutral': 0.2},
#     'emotion_distribution': {'anger': 0.4, 'fear': 0.3, ...},
#     'emotion_adjusted_severity': 0.65,
#     'mention_count': 150,
#     'total_influence_weight': 320.5
# }
```

**Time Windows**: `15m`, `1h`, `24h`, `7d`, `30d`

**Aggregation Types**: `topic`, `issue`, `entity`

---

### Sentiment Trend Pattern (Week 5)

**New**: Calculate sentiment trends by comparing current vs previous periods

```python
from processing.data_processor import DataProcessor

processor = DataProcessor()

# Calculate trend for a topic
trend = processor.calculate_trend_for_topic('healthcare', time_window='24h')

# Returns:
# {
#     'aggregation_type': 'topic',
#     'aggregation_key': 'healthcare',
#     'time_window': '24h',
#     'current_sentiment_index': 65.5,
#     'previous_sentiment_index': 58.2,
#     'trend_direction': 'improving',  # or 'deteriorating', 'stable'
#     'trend_magnitude': 7.3,
#     'period_start': datetime(...),
#     'period_end': datetime(...),
#     ...
# }
```

**Trend Directions**:
- `improving`: Sentiment increased by >= 5.0 points
- `deteriorating`: Sentiment decreased by <= -5.0 points
- `stable`: Change within ±2.0 points

---

### Sentiment Normalization Pattern (Week 5)

**New**: Normalize sentiment scores against topic-specific baselines

```python
from processing.data_processor import DataProcessor

processor = DataProcessor()

# Normalize sentiment against topic baseline
normalized = processor.normalize_sentiment_for_topic('healthcare', current_sentiment_index=65.0)

# Returns:
# {
#     'normalized_index': 56.5,  # Adjusted for baseline
#     'baseline_index': 58.5,    # Topic baseline
#     'deviation': 6.5,          # Deviation from baseline
#     'normalized_score': 0.13,  # -1.0 to 1.0
#     'current_index': 65.0
# }
```

**Why Normalize**: Different topics have different baseline sentiment levels. Normalization allows fair comparison across topics.

---

### Aggregation Pipeline Pattern (Week 5)

**New**: Run complete aggregation pipeline for all topics

```python
from processing.data_processor import DataProcessor

processor = DataProcessor()

# Run complete pipeline
results = processor.run_aggregation_pipeline(
    time_window='24h',
    include_trends=True,
    include_normalization=True,
    limit=10  # Process first 10 topics
)

# Returns:
# {
#     'aggregations': {'topic_key': {...}, ...},
#     'trends': {'topic_key': {...}, ...},
#     'normalized': {'topic_key': {...}, ...},
#     'time_window': '24h',
#     'processed_at': datetime(...)
# }
```

**Pipeline Steps**:
1. Aggregate sentiment for all topics
2. Calculate trends (compare current vs previous)
3. Normalize aggregations (adjust for baselines)

---

### Configuration Pattern

```python
from src.config.config_manager import ConfigManager

config = ConfigManager()
value = config.get_int('key.path', default_value)
```

### Path Pattern

```python
from src.config.path_manager import PathManager

paths = PathManager()
data_dir = paths.data_raw
```

### Logging Pattern

```python
from src.config.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Processing started")
```

### Error Handling Pattern

```python
from exceptions import ConfigError

try:
    # Operation
    pass
except ConfigError as e:
    logger.error(f"Error: {e.message}", extra=e.details)
    # Handle error
```

### Database Pattern

```python
from src.api.database import SessionLocal
from src.api import models

db = SessionLocal()
try:
    records = db.query(models.SentimentData).all()
finally:
    db.close()
```

---

## Additional Resources

- `BACKEND_ARCHITECTURE.md` - Complete architecture documentation
- `MIGRATION_GUIDE.md` - Migration guide for cleanup changes
- `docs/FRONTEND_CONFIG_MANAGEMENT_GUIDE.md` - Frontend configuration guide
- `docs/ADDING_NEW_CONFIGS_GUIDE.md` - Adding new configuration guide
- `cleanup/README.md` - Cleanup progress and status

---

**Last Updated**: 2024-12-19  
**Version**: 2.5 (Week 6: Testing & Optimization)

**Status**: ✅ All 6 weeks of the master plan are complete. The system is production-ready.

