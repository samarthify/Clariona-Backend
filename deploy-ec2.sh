#!/bin/bash
# Quick deployment script for Clariti backend on EC2
# Run this script on your EC2 instance after SSH'ing in

set -e  # Exit on error

echo "🚀 Starting Clariti Backend Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo -e "${RED}Cannot detect OS. Exiting.${NC}"
    exit 1
fi

echo -e "${GREEN}Detected OS: $OS${NC}"

# Install system dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt update
    sudo apt install -y python3.11 python3.11-venv python3-pip git postgresql-client libpq-dev build-essential gcc g++
elif [ "$OS" = "amzn" ] || [ "$OS" = "amazon" ]; then
    sudo dnf update -y
    sudo dnf install -y python3.11 python3.11-pip git postgresql15 libpq-devel
    sudo dnf groupinstall -y "Development Tools"
else
    echo -e "${RED}Unsupported OS. Please install Python 3.11, pip, and git manually.${NC}"
    exit 1
fi

# Check if we're in the project directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${YELLOW}requirements.txt not found. Checking if we need to clone the repo...${NC}"
    if [ ! -d "Clariti-1.0" ]; then
        echo -e "${RED}Please either:${NC}"
        echo -e "${RED}1. Run this script from the project directory, or${NC}"
        echo -e "${RED}2. Clone the repository first: git clone <your-repo-url>${NC}"
        exit 1
    else
        cd Clariti-1.0
    fi
fi

# Create virtual environment
echo -e "${YELLOW}Creating Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
else
    echo -e "${GREEN}Virtual environment already exists.${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}requirements.txt not found!${NC}"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo -e "${YELLOW}Creating .env template...${NC}"
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://user:password@host:5432/clariti

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Application
PYTHONPATH=$(pwd)
NODE_ENV=production
EOF
    echo -e "${RED}Please edit .env file with your actual configuration!${NC}"
    echo -e "${YELLOW}Run: nano .env${NC}"
    read -p "Press Enter after you've configured .env file..."
fi

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p logs/collectors data/raw data/processed config ministry_issues

# Test import
echo -e "${YELLOW}Testing Python imports...${NC}"
python3 -c "import fastapi; import uvicorn; print('✅ Dependencies OK')" || {
    echo -e "${RED}❌ Import test failed!${NC}"
    exit 1
}

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${GREEN}To start the server, run:${NC}"
echo -e "${YELLOW}source venv/bin/activate${NC}"
echo -e "${YELLOW}uvicorn src.api.service:app --host 0.0.0.0 --port 8000${NC}"
echo ""
echo -e "${GREEN}Or with Gunicorn (recommended for production):${NC}"
echo -e "${YELLOW}source venv/bin/activate${NC}"
echo -e "${YELLOW}gunicorn src.api.service:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000${NC}"

