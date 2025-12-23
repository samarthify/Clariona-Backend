# Backend Repository Migration Checklist

This folder contains all backend files ready to be moved to a new repository.

## ✅ Files Included

### Core Backend Code
- ✅ `src/` - All Python backend source code
- ✅ `config/` - Backend configuration files
- ✅ `scripts/` - Python utility scripts
- ✅ `tests/` - Python test files

### Configuration & Setup
- ✅ `requirements.txt` - Python dependencies
- ✅ `docker-compose.yml` - Backend Docker Compose configuration
- ✅ `.gitignore` - Git ignore file for Python projects
- ✅ `ENV_TEMPLATE.txt` - Environment variable template

### Critical Scripts
- ✅ `run_cycles.sh` - ⚠️ **CRITICAL** Agent cycle runner (executable)
- ✅ `run_cycles.sh.improved` - Enhanced version with env var support
- ✅ `deploy-ec2.sh` - EC2 deployment script (executable)
- ✅ `troubleshoot.sh` - Troubleshooting script (executable)
- ✅ `ecosystem.config.js` - PM2 configuration

### Documentation
- ✅ `README.md` - Main backend documentation
- ✅ `BACKEND_SETUP_NOTES.md` - Detailed setup notes for critical files

### Infrastructure
- ✅ `docker/` - Docker configuration files
  - `docker/postgres/init.sql` - Database initialization script

### Directories Created
- ✅ `logs/` - Log files directory (empty, ready for use)

## 📋 Next Steps

### 1. Create New Repository
```bash
# On GitHub/GitLab, create a new repository named "clariti-backend"
```

### 2. Initialize Git in Backend Folder
```bash
cd backend
git init
git add .
git commit -m "Initial backend repository - migrated from monorepo"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

### 3. Setup Environment
```bash
# Create .env file from template
cp ENV_TEMPLATE.txt .env
# Edit .env with your actual configuration
nano .env  # or use your preferred editor
```

### 4. Install Dependencies
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Verify Critical Files
```bash
# Ensure run_cycles.sh is executable
chmod +x run_cycles.sh deploy-ec2.sh troubleshoot.sh

# Verify scripts work
./run_cycles.sh --help  # Should show usage or start running
```

### 6. Test Backend
```bash
# Start backend API
uvicorn src.api.service:app --reload

# In another terminal, test health endpoint
curl http://localhost:8000/health
```

## ⚠️ Important Notes

1. **run_cycles.sh is CRITICAL** - Make sure it's executable and configured correctly
2. **Environment Variables** - Copy `ENV_TEMPLATE.txt` to `.env` and configure all values
3. **Database** - Ensure PostgreSQL is accessible and schema is set up
4. **Logs Directory** - The `logs/` folder is created but empty. Backend will populate it.
5. **Docker** - If using Docker, check `docker-compose.yml` configuration

## 🔗 Related Files in Original Repo

After migration, remember to:
- Update frontend to point to new backend URL
- Remove backend files from original repo (or keep for reference)
- Update CORS settings in backend to allow frontend origin
- Coordinate database access between frontend (Prisma) and backend (SQLAlchemy)

## 📚 Documentation Reference

- See `README.md` for general setup
- See `BACKEND_SETUP_NOTES.md` for detailed critical file setup
- See `run_cycles.sh.improved` for enhanced cycle runner with env var support

