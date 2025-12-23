# Clariti Backend

Python FastAPI backend for the Clariti governance intelligence platform.

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

6. **Start the backend**:
   ```bash
   # Development
   uvicorn src.api.service:app --reload --host 0.0.0.0 --port 8000
   
   # Production (with PM2)
   pm2 start ecosystem.config.js
   ```

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

### `run_cycles.sh` - Agent Cycle Runner
**This is CRITICAL** for running automated agent cycles. See `BACKEND_SETUP_NOTES.md` for detailed setup instructions.

**Quick setup**:
```bash
chmod +x run_cycles.sh
export USER_ID="your-user-id"
export BACKEND_URL="http://localhost:8000"  # If different
./run_cycles.sh
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key
- `EMAIL_SERVER`, `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD` - Email configuration
- `YOUTUBE_API_KEY` - YouTube API key
- `SECRET_KEY` - Application secret key

See `BACKEND_SETUP_NOTES.md` for complete list.

## 📚 Documentation

- **`BACKEND_SETUP_NOTES.md`** - Detailed setup instructions for critical files
- **`run_cycles.sh.improved`** - Enhanced version with environment variable support

## 🐳 Docker

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build manually
docker build -f Dockerfile.backend.dev -t clariti-backend .
docker run -p 8000:8000 clariti-backend
```

## 🔌 API Endpoints

The backend API runs on `http://localhost:8000` (or configured port).

Key endpoints:
- `GET /health` - Health check
- `POST /agent/test-cycle-no-auth` - Trigger agent cycle
- `/api/issues/*` - Issue management
- `/api/auth/*` - Authentication
- `/api/presidential/*` - Presidential analysis

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

