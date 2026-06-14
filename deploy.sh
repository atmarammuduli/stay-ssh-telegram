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
echo -e "Usage: ./deploy.sh [OPTIONS]"
echo -e "Options:"
echo -e "  --silent    Non-interactive deployment (main branch, hard reset, build, deploy)"
echo -e "This script helps you fetch latest code, build and deploy the bot."
echo ""

# Parse arguments
SILENT_MODE=false
for arg in "$@"; do
    if [ "$arg" == "--silent" ]; then
        SILENT_MODE=true
    fi
done

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
if [ "$SILENT_MODE" == "true" ]; then
    echo -e "${YELLOW}🔄 [SILENT] Fetching, checking out main, and performing hard reset...${NC}"
    git fetch origin --prune
    TARGET_BRANCH="main"
    git checkout $TARGET_BRANCH || git checkout -b $TARGET_BRANCH origin/$TARGET_BRANCH
    git reset --hard origin/$TARGET_BRANCH
    echo -e "${BLUE}ℹ️ Files in .gitignore (.env, keys/, etc.) were NOT touched.${NC}"
    FETCH_GIT="n" # Already handled
else
    read -p "❓ Fetch latest code from git? (y/N): " FETCH_GIT
fi

if [[ "$FETCH_GIT" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🔄 Fetching remote branches...${NC}"
    git fetch origin --prune
    
    # List available remote branches (cleaned up)
    echo -e "${BLUE}Available branches:${NC}"
    git branch -r | grep -v "origin/HEAD" | sed 's/origin\///' | awk '{print "  - "$1}'
    
    # Ask for branch
    read -p "❓ Which branch to deploy? [default: main]: " TARGET_BRANCH
    # If empty or 'y'/'yes', use main
    if [[ -z "$TARGET_BRANCH" || "$TARGET_BRANCH" =~ ^[Yy]([Ee][Ss])?$ ]]; then
        TARGET_BRANCH="main"
    fi
    
    echo -e "${YELLOW}📍 Switching to branch: $TARGET_BRANCH...${NC}"
    git checkout $TARGET_BRANCH || git checkout -b $TARGET_BRANCH origin/$TARGET_BRANCH

    # Ask for update method
    echo -e "❓ Choose update method:"
    echo -e "  [r] Reset (Hard reset to origin, keep ignored files) - DEFAULT"
    echo -e "  [p] Pull (Merge updates, keep local changes)"
    read -p "👉 Selection [r/p]: " UPDATE_METHOD
    
    # Handle logic for 'r' being the default for 'y', 'yes', or empty
    if [[ -z "$UPDATE_METHOD" || "$UPDATE_METHOD" =~ ^[Yy]([Ee][Ss])?$ || "$UPDATE_METHOD" == "r" ]]; then
        echo -e "${RED}⚠️ Performing hard reset to origin/$TARGET_BRANCH...${NC}"
        git reset --hard origin/$TARGET_BRANCH

        # Optional Clean step
        read -p "❓ Also remove other untracked files? (y/N) [Note: .gitignore files are always safe]: " CLEAN_REQ
        if [[ "$CLEAN_REQ" =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}🧹 Cleaning untracked files...${NC}"
            git clean -fd
            echo -e "${GREEN}✅ Branch reset and untracked files cleaned.${NC}"
        else
            echo -e "${GREEN}✅ Branch reset. Untracked files were kept.${NC}"
        fi
        echo -e "${BLUE}ℹ️ Files in .gitignore (.env, keys/, etc.) were NOT touched.${NC}"
    else
        echo -e "${YELLOW}🔄 Pulling updates from origin/$TARGET_BRANCH...${NC}"
        git pull origin $TARGET_BRANCH
        echo -e "${GREEN}✅ Pulled latest changes.${NC}"
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
if [ "$SILENT_MODE" == "true" ]; then
    BUILD_IMAGE="y"
else
    read -p "❓ Build the Docker image? (y/N): " BUILD_IMAGE
fi

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
if [ "$SILENT_MODE" == "true" ]; then
    DEPLOY_BOT="y"
else
    read -p "❓ Deploy the bot now? (y/N): " DEPLOY_BOT
fi

if [[ "$DEPLOY_BOT" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}🚀 Deploying...${NC}"
    $DOCKER_COMPOSE down || true
    $DOCKER_COMPOSE up -d
    echo -e "${GREEN}🔄 Initializing database...${NC}"
    $DOCKER_COMPOSE exec -T bot python -m tmux_ssh_telegram.db.init_db || echo -e "${YELLOW}⚠️ DB init might have failed or skipped.${NC}"
    echo -e "${GREEN}✅ Deployment complete! Showing logs...${NC}"
    echo -e "${BLUE}Press Ctrl+C to exit logs (bot will continue running).${NC}"
    sleep 2
    $DOCKER_COMPOSE logs -f
else
    echo -e "${YELLOW}⏩ Skipping deployment.${NC}"
fi
