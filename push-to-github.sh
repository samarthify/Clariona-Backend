#!/bin/bash

# Helper script to push backend repository to GitHub/GitLab
# Usage: ./push-to-github.sh <repository-url>

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Repository URL required"
    echo ""
    echo "Usage: ./push-to-github.sh <repository-url>"
    echo ""
    echo "Example:"
    echo "  ./push-to-github.sh https://github.com/yourusername/clariti-backend.git"
    echo "  ./push-to-github.sh git@github.com:yourusername/clariti-backend.git"
    echo ""
    exit 1
fi

REPO_URL="$1"

echo "🚀 Setting up remote and pushing to repository..."
echo "Repository URL: $REPO_URL"
echo ""

# Check if remote already exists
if git remote | grep -q "^origin$"; then
    echo "⚠️  Remote 'origin' already exists. Updating..."
    git remote set-url origin "$REPO_URL"
else
    echo "✅ Adding remote 'origin'..."
    git remote add origin "$REPO_URL"
fi

# Verify remote
echo ""
echo "📋 Current remotes:"
git remote -v

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo ""
echo "ranch: $CURRENT_BRANCH"

# Push to remote
echo ""
echo "📤 Pushing to remote repository..."
git push -u origin "$CURRENT_BRANCH"

echo ""
echo "✅ Successfully pushed to remote repository!"
echo ""
echo "Next steps:"
echo "  1. Verify your repository on GitHub/GitLab"
echo "  2. Set up environment variables (copy ENV_TEMPLATE.txt to .env)"
echo "  3. Follow MIGRATION_CHECKLIST.md for complete setup"

