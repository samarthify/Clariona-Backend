# Backend Repository Setup - Critical Files

## ⚠️ Critical Files for Backend Operation

### `run_cycles.sh` - Agent Cycle Runner

**This is a CRITICAL file** for running automated agent cycles. It:

1. **Triggers agent cycles** via API call to `http://localhost:8000/agent/test-cycle-no-auth`
2. **Monitors cycle completion** by checking logs in `logs/automatic_scheduling.log`
3. **Waits for cycles to complete** before starting the next one
4. **Runs continuously** in a loop with configurable intervals

#### Setup Requirements

1. **Make executable**:
   ```bash
   chmod +x run_cycles.sh
   ```

2. **Ensure logs directory exists**:
   ```bash
   mkdir -p logs
   ```

3. **Configure user ID** (line 5 in script):
   ```bash
   USER_ID="your-user-id-here"  # Update with actual user ID
   ```

4. **Configure interval** (line 6 in script):
   ```bash
   INTERVAL_MINUTES=30  # Wait 30 minutes after cycle completes
   ```

5. **Backend API must be running**:
   - The script calls `http://localhost:8000/agent/test-cycle-no-auth`
   - Ensure backend is running and accessible before starting cycles
   - For remote backend, update the URL in the script

#### Usage

**Run in foreground** (for testing):
```bash
./run_cycles.sh
```

**Run in background** (for production):
```bash
nohup ./run_cycles.sh > logs/cycle-runner.log 2>&1 &
```

**Run with PM2** (recommended for production):
```bash
pm2 start run_cycles.sh --name "cycle-runner" --interpreter bash
pm2 save
pm2 startup
```

#### Dependencies

- Backend API must be running and accessible
- `logs/automatic_scheduling.log` must be writable (created by backend agent)
- `curl` must be installed
- `date` command (standard on Linux/Mac)

#### Configuration with Environment Variables

For better configuration (especially after repository split), you can use environment variables:

```bash
# Set backend URL (if different from localhost:8000)
export BACKEND_URL="http://your-backend-host:8000"

# Set user ID
export USER_ID="your-user-id-here"

# Set interval
export INTERVAL_MINUTES=30

# Set log file path
export LOG_FILE="logs/automatic_scheduling.log"

# Run the script
./run_cycles.sh
```

**Note**: An improved version of this script (`run_cycles.sh.improved`) supports environment variables out of the box. You can replace the original with the improved version if desired.

#### Troubleshooting

**Issue**: Script can't connect to backend
- **Solution**: Check if backend is running: `curl http://localhost:8000/health`
- **Solution**: Update URL in script if backend is on different host/port

**Issue**: Script can't find log file
- **Solution**: Ensure `logs/` directory exists and is writable
- **Solution**: Check if backend agent creates `logs/automatic_scheduling.log`

**Issue**: Cycles not completing
- **Solution**: Check backend logs for errors
- **Solution**: Verify USER_ID is correct
- **Solution**: Increase MAX_WAIT_HOURS if cycles take longer than 6 hours

---

## Other Critical Backend Files

### `ecosystem.config.js` - PM2 Configuration
- Used to run backend API with PM2
- Configure for production deployment

### `deploy-ec2.sh` - EC2 Deployment Script
- Automates backend deployment to EC2
- Sets up virtual environment, installs dependencies

### `requirements.txt` - Python Dependencies
- All Python packages needed for backend
- Install with: `pip install -r requirements.txt`

---

## Recommended Backend Repository Structure

```
clariti-backend/
├── src/                    # Backend source code
│   ├── api/               # FastAPI service
│   ├── agent/             # Agent system
│   ├── collectors/        # Data collectors
│   ├── processing/        # Data processing
│   └── utils/             # Utilities
├── config/                # Configuration files
├── scripts/               # Utility scripts
├── tests/                 # Test files
├── logs/                  # Log files (create empty, .gitkeep)
│   └── collectors/        # Collector logs
├── requirements.txt       # Python dependencies
├── deploy-ec2.sh         # Deployment script
├── ecosystem.config.js   # PM2 config
├── run_cycles.sh         # ⚠️ CRITICAL - Cycle runner
├── troubleshoot.sh       # Troubleshooting script
├── docker-compose.yml    # Docker compose
├── Dockerfile.backend.dev # Backend Dockerfile
├── .env.example          # Environment template
├── .gitignore            # Git ignore
└── README.md             # Documentation
```

---

## Environment Variables Needed

Create `.env` file with:

```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/clariti

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Email Configuration
EMAIL_SERVER=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_SENDER=your_email@gmail.com

# API Keys
YOUTUBE_API_KEY=your_youtube_api_key

# Application
PYTHONPATH=.
NODE_ENV=production
SECRET_KEY=your_secret_key_here

# Logging
LOG_LEVEL=INFO
```

---

## First-Time Setup Checklist

1. [ ] Copy all files from monorepo
2. [ ] Make `run_cycles.sh` executable (`chmod +x run_cycles.sh`)
3. [ ] Create `logs/` directory (`mkdir -p logs/collectors`)
4. [ ] Create `.env` file from `.env.example`
5. [ ] Update `run_cycles.sh` with correct USER_ID
6. [ ] Install Python dependencies (`pip install -r requirements.txt`)
7. [ ] Test backend API starts: `uvicorn src.api.service:app --reload`
8. [ ] Test cycle runner: `./run_cycles.sh` (in separate terminal)
9. [ ] Verify logs are being written to `logs/automatic_scheduling.log`

