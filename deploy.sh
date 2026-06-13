#!/bin/bash
# deploy.sh - Interactive deployment script for StaySSH Telegram Bot

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print Usage
echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}   StaySSH Telegram Bot Deployment Utility${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "Usage: ./deploy.sh"
echo -e "This script helps you fetch latest code, build and deploy the bot."
echo ""

# 0. Check if we are in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: pyproject.toml not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Detect Docker Compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}❌ Error: Neither 'docker compose' (V2) nor 'docker-compose' (V1) was found.${NC}"
    echo -e "${YELLOW}Please install Docker Compose before running this script.${NC}"
    exit 1
fi

echo -e "${BLUE}ℹ️ Using '$DOCKER_COMPOSE' for deployment.${NC}"

# 1. Ask to fetch latest from git
read -p "❓ Fetch latest code from git? (y/N): " FETCH_GIT
if [[ "$FETCH_GIT" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🔄 Fetching remote branches...${NC}"
    git fetch origin --prune
    
    # List available remote branches (cleaned up)
    echo -e "${BLUE}Available branches:${NC}"
    git branch -r | grep -v "origin/HEAD" | sed 's/origin\///' | awk '{print "  - "$1}'
    
    # Ask for branch
    read -p "❓ Which branch to deploy? [default: main]: " TARGET_BRANCH
    TARGET_BRANCH=${TARGET_BRANCH:-main}
    
    # Backup .env
    if [ -f .env ]; then
        cp .env .env.bak
        echo -e "${BLUE}💾 Backed up .env to .env.bak${NC}"
    fi
    
    echo -e "${YELLOW}📍 Checking out and resetting to origin/$TARGET_BRANCH...${NC}"
    
    # Perform clean checkout
    git checkout $TARGET_BRANCH || git checkout -b $TARGET_BRANCH origin/$TARGET_BRANCH
    git reset --hard origin/$TARGET_BRANCH
    git clean -fd
    
    # Restore .env
    if [ -f .env.bak ]; then
        mv .env.bak .env
        echo -e "${BLUE}✅ Restored .env from backup.${NC}"
    fi
fi

# 2. Validate environment
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo -e "${YELLOW}⚠️ .env file missing. Creating from .env.example...${NC}"
        cp .env.example .env
        echo -e "${RED}❗ Please edit .env with your configuration before continuing.${NC}"
        exit 1
    else
        echo -e "${RED}❌ Error: .env and .env.example missing.${NC}"
        exit 1
    fi
fi

# 3. Fix potential naming issues
# The codebase expects the package folder to be 'tmux_ssh_telegram'
if [ ! -d "tmux_ssh_telegram" ]; then
    echo -e "${YELLOW}🔍 'tmux_ssh_telegram' directory not found.${NC}"
    POTENTIAL_DIR=$(ls -d */ | grep -E "stay[-_]ssh|telegram" | grep -v "venv" | grep -v "tests" | grep -v "docs" | head -n 1 | sed 's/\///')
    
    if [ ! -z "$POTENTIAL_DIR" ]; then
        echo -e "${YELLOW}⚠️ Found potential source directory: '$POTENTIAL_DIR'${NC}"
        echo -e "${GREEN}🔄 Renaming '$POTENTIAL_DIR' to 'tmux_ssh_telegram' to match codebase imports...${NC}"
        mv "$POTENTIAL_DIR" tmux_ssh_telegram
    else
        echo -e "${RED}❌ Error: Could not find the source directory.${NC}"
        exit 1
    fi
fi

# 4. Ask to build
read -p "❓ Build the Docker image? (y/N): " BUILD_IMAGE
if [[ "$BUILD_IMAGE" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}🐳 Building Docker image...${NC}"
    $DOCKER_COMPOSE build --no-cache
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Build failed!${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Build successful.${NC}"
fi

# 5. Ask to deploy
read -p "❓ Deploy the bot now? (y/N): " DEPLOY_BOT
if [[ "$DEPLOY_BOT" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}🚀 Deploying...${NC}"
    
    # Stop existing container if running
    echo -e "${YELLOW}🛑 Stopping existing container (if any)...${NC}"
    $DOCKER_COMPOSE down || true
    
    # Start up
    echo -e "${GREEN}🆙 Starting containers...${NC}"
    $DOCKER_COMPOSE up -d
    
    # Initialize DB
    echo -e "${GREEN}🔄 Initializing database...${NC}"
    $DOCKER_COMPOSE exec -T bot python -m tmux_ssh_telegram.db.init_db || echo -e "${YELLOW}⚠️ DB init might have failed or skipped.${NC}"
    
    echo -e "${GREEN}✅ Deployment complete! Showing logs...${NC}"
    echo -e "${BLUE}Press Ctrl+C to exit logs (bot will continue running).${NC}"
    sleep 2
    $DOCKER_COMPOSE logs -f
else
    echo -e "${YELLOW}⏩ Skipping deployment.${NC}"
fi
