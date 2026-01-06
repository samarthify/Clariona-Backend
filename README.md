# Clariona Backend

**Python FastAPI backend for the Clariona governance intelligence platform.**

## ⚠️ IMPORTANT: Backend Purpose & Scope

**This backend is EXCLUSIVELY a data collection, processing, and storage pipeline.**

### What This Backend Does:
- ✅ **Data Collection**: Collects data from multiple sources (Twitter, Facebook, News, YouTube, RSS, etc.)
- ✅ **Data Processing**: Analyzes and classifies collected data (sentiment, topics, locations, issues) in **Real-Time**.
- ✅ **Data Storage**: Writes all processed data directly to PostgreSQL database
- ✅ **Automation**: Real-Time Streaming & Polling for continuous analysis.

### What This Backend Does NOT Do:
- ❌ **NO Frontend**: This backend has zero frontend code, UI, or user-facing components
- ❌ **NO Frontend APIs**: Frontend applications read DIRECTLY from the PostgreSQL database (via Prisma)
- ❌ **NO User Interface**: All user interaction happens in separate frontend applications

### Architecture:
```
Backend → Collects Data → Processes Data → Writes to PostgreSQL Database
                                                      │
                                                      │
Frontend (Separate) ← Reads DIRECTLY from Database ←─┘
```

**For detailed architecture documentation, see [`BACKEND_ARCHITECTURE.md`](BACKEND_ARCHITECTURE.md)**

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Virtual environment (venv)

### Setup

1. **Create virtual environment**:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Create necessary directories**:
   ```bash
   mkdir -p logs/collectors data/raw data/processed
   ```

5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Start the backend (Streaming Service)**:
   ```bash
   # Starts Collection + Analysis + Scheduling in one unified service
   python -m src.services.main
   ```

## ⚡ Real-Time Streaming Architecture (New)

The backend now operates as a unified **Real-Time Streaming Service**:

1.  **Streaming Data Collection**:
    *   `DatasetTailerService`: Continuously streams new records from Apify (Twitter/News/etc.) in real-time.
    *   `LocalScheduler`: Runs interval-based collectors (RSS/YouTube) periodically.

2.  **Real-Time Analysis (Polling Engine)**:
    *   **AnalysisWorker**: A high-performance polling engine that constantly monitors the database for new unanalyzed records.
    *   **Phase 1: Sentiment**: Classifies sentiment (Positive/Negative/Neutral) and strategic impact.
    *   **Phase 2: Emotion**: Detects emotions (Anger, Fear, Joy, etc.).
    *   **Phase 3: Topics**: Classifies topics and stores in `mention_topics`.
    *   **Phase 4: Issues**: Instantly links mentions to active issues (e.g., "Fuel Scarcity").
    *   **Phase 5: Location**: Detects location granularity.
    *   **Throughput**: Processes ~50 records/batch with 10 parallel workers.
    *   **Self-Healing**: Automatically picks up any missed records from previous runs.

3.  **Unified Entry Point**:
    *   Single command `python -m src.services.main` manages all services (Tailer, Worker, Scheduler).

## 📁 Project Structure

```
backend/
├── src/
│   ├── api/           # FastAPI service and endpoints
│   ├── agent/         # AI agent system
│   ├── collectors/    # Data collection modules
│   ├── processing/    # Data processing and analysis
│   ├── utils/         # Utility functions
│   └── alembic/       # Database migrations
├── config/            # Configuration files
├── scripts/           # Utility scripts
├── tests/             # Test files
├── logs/              # Log files
├── requirements.txt   # Python dependencies
├── run_cycles.sh      # ⚠️ CRITICAL - Agent cycle runner
├── deploy-ec2.sh      # EC2 deployment script
└── ecosystem.config.js # PM2 configuration
```

## ⚠️ Critical Files

### `src/services/main.py` - Unified Streaming Service (Primary)
**This is the CRITICAL entry point** for the backend. It runs the entire pipeline (Tailer + Worker + Scheduler) in a single unified service.

### `run_cycles.sh` - Legacy Cycle Runner (Fallback)
**Use only for legacy batch processing**. Triggers cron-based job cycles. See `BACKEND_SETUP_NOTES.md` for details.

## 🎯 Classification System (Complete)

**Status**: ✅ **Production Ready** - All 6 weeks of the master plan are complete.

The backend includes a comprehensive classification system for sentiment analysis, topic classification, issue detection, and aggregation:

### Features

- **Topic Classification** (Week 2): Multi-topic classification using keyword matching and embedding similarity
- **Enhanced Sentiment Analysis** (Week 3): Emotion detection, weighted sentiment scoring, and confidence calculation
- **Issue Detection** (Week 4): Clustering-based issue detection with lifecycle management and priority calculation
- **Aggregation & Trends** (Week 5): Sentiment aggregation, trend calculation, and baseline normalization
- **Testing & Optimization** (Week 6): Comprehensive testing suite and performance optimization

### Performance

- **Throughput**: 0.44 texts/second (baseline)
- **Batch Processing**: ~2.27 seconds per text
- **All Tests Passing**: 9/10 (1 skipped - expected)

### Documentation

- **`docs/topic-classification-architecture/`** - Complete classification system documentation
  - `ADDING_FEATURES_GUIDE.md` - How to add new features
  - `PERFORMANCE_OPTIMIZATION_GUIDE.md` - Performance optimization strategies
  - `THROUGHPUT_IMPROVEMENT_GUIDE.md` - Increasing processing throughput
  - `MASTER_IMPLEMENTATION_PLAN.md` - Complete 6-week implementation reference

## Recent Improvements (Phase 6)

### Error Handling
- **Custom Exception Hierarchy**: Standardized error handling with specific exception types
  - `BackendError` (base) → `ConfigError`, `DatabaseError`, `AnalysisError`, etc.
  - Better error context and debugging information
  - Consistent error handling patterns across modules

### Logging
- **Centralized Logging**: Unified logging configuration via `src/config/logging_config.py`
  - Consistent log formats and levels
  - Module-specific loggers with dedicated files
  - Log rotation and UTF-8 support
  - Configurable via ConfigManager

### Code Quality
- **Type Hints**: Comprehensive type annotations across key modules
  - Better IDE support and autocomplete
  - Improved code maintainability
  - Type-safe function signatures

### Module Organization
- **Standardized Imports**: Consistent import order across all modules
  - Standard library → Third-party → Local imports
  - Clear separation of concerns
  - Better code readability

## 🔧 Configuration

### Configuration System

The backend uses a **centralized configuration system** with database backend support:

- **ConfigManager**: Centralized configuration management with type-safe accessors
- **Database-Backed**: All configuration editable via database (SystemConfiguration table)
- **Environment Variable Overrides**: Highest priority (for deployment-specific values)
- **File-Based Fallbacks**: JSON config files for defaults

### Configuration Categories:

- **Paths**: All file system paths (logs, data, config files)
- **Timeouts**: Database, HTTP, collector, scheduler timeouts
- **Limits**: Batch sizes, max results, max records
- **Thresholds**: Similarity, confidence, score thresholds
- **Model Constants**: String lengths, model names, TPM capacities
- **Collector Settings**: Timeouts, delays, retries, keywords, mappings
- **Prompts**: All LLM prompts used in processing pipeline (configurable templates with variables)
- **Prompt Variables**: Dynamic variables used in prompts (president_name, country, etc.)
- **CORS**: Allowed origins

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key
- `API_BASE_URL` - API base URL (default: http://localhost:8000)
- `EMAIL_SERVER`, `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD` - Email configuration
- `YOUTUBE_API_KEY` - YouTube API key
- `SECRET_KEY` - Application secret key

**Note**: Most configuration is now managed via the database (SystemConfiguration table) or config files. Environment variables are used primarily for deployment-specific values.

### Configurable Prompts

All LLM prompts used in the processing pipeline are now configurable via `ConfigManager`:

- **Presidential Sentiment Analysis**: System message and user prompt templates
- **Governance Classification**: System message and user prompt templates  
- **Issue Classification**: Comparison and consolidation prompt templates

Prompts support template variables (e.g., `{president_name}`, `{text}`, `{ministry}`) and can be customized without code changes. Configure in `config/agent_config.json` or via environment variables.

**Example**:
```json
{
  "processing": {
    "prompts": {
      "presidential_sentiment": {
        "system_message": "You are a strategic advisor to {president_name} analyzing media impact.",
        "user_template": "Analyze media from {president_name}'s perspective...",
        "text_truncate_length": 800
      }
    },
    "prompt_variables": {
      "president_name": "Bola Ahmed Tinubu",
      "country": "Nigeria"
    }
  }
}
```

See `BACKEND_SETUP_NOTES.md` for complete list and `docs/DATABASE_CONFIG_SYSTEM_SUMMARY.md` for configuration management details.

## 📚 Documentation

### Core Documentation
- **`BACKEND_ARCHITECTURE.md`** ⭐ - Complete architecture documentation - Detailed explanation of how the backend works, data flow, database schema, and pipeline execution
- **`DEVELOPER_GUIDE.md`** ⭐ - Complete developer guide - Code standards, patterns, configuration, and best practices
- **`BACKEND_SETUP_NOTES.md`** - Detailed setup instructions for critical files

### Classification System Guides
- **`docs/topic-classification-architecture/`** - Classification system documentation
  - `README.md` - Overview and quick reference
  - `ADDING_FEATURES_GUIDE.md` - How to add new features to the classification system
  - `PERFORMANCE_OPTIMIZATION_GUIDE.md` - Performance optimization strategies
  - `THROUGHPUT_IMPROVEMENT_GUIDE.md` - Increasing processing throughput
  - `MASTER_IMPLEMENTATION_PLAN.md` - Complete 6-week implementation reference

### Cleanup & Refactoring
- **`cleanup/`** 🧹 - Cleanup & Refactoring Documentation
  - `cleanup/CLEANUP_AND_REFACTORING_PLAN.md` - Step-by-step 8-phase cleanup plan
  - `cleanup/CLEANUP_QUICK_START.md` - Quick start guide for immediate action
  - `cleanup/README.md` - Progress tracking and overview

## 🐳 Docker

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build manually
docker build -f Dockerfile.backend.dev -t clariti-backend .
docker run -p 8000:8000 clariti-backend
```

## 🔌 API Endpoints

**Note**: This backend has minimal API endpoints. Most endpoints are for triggering cycles, health checks, and admin operations. **The frontend does NOT use these APIs** - it reads directly from the PostgreSQL database.

The backend API runs on `http://localhost:8000` (or configured port).

Key endpoints:
- `GET /health` - Health check
- `POST /agent/test-cycle-no-auth` - Trigger agent cycle (used by `run_cycles.sh`)
- `/api/issues/*` - Issue management (admin/internal)
- `/api/auth/*` - Authentication (admin/internal)
- `/api/presidential/*` - Presidential analysis (admin/internal)

**For complete API documentation and architecture details, see [`BACKEND_ARCHITECTURE.md`](BACKEND_ARCHITECTURE.md)**

## 📝 Deployment

### EC2 Deployment
```bash
./deploy-ec2.sh
```

### PM2 Production
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## 🔍 Troubleshooting

See `BACKEND_SETUP_NOTES.md` for troubleshooting guides.

Common issues:
- Backend not accessible: Check if running on correct port
- `run_cycles.sh` fails: Ensure backend API is running and accessible
- Database connection errors: Verify `DATABASE_URL` in `.env`

## 📄 License

[Your License Here]

