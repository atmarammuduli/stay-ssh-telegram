#!/bin/bash

# Configuration
PID_FILE=".stayssh.pid"
VENV_DIR="venv"
COVERAGE_THRESHOLD=100

# Help function
show_help() {
    echo "Usage: ./scripts/run_local.sh [OPTIONS]"
    echo "Options:"
    echo "  --clean    Remove virtual environment and local cache before starting"
    echo "  --stop     Stop the running bot instance"
    echo "  --test     Run all tests (Unit -> Integration -> E2E) sequentially"
    echo "  --commit   Run tests and commit changes if coverage is ${COVERAGE_THRESHOLD}%"
    echo "  --help     Show this help message"
}

stop_bot() {
    echo "🔍 Checking for running bot instances..."
    
    # 1. Try stopping via PID file
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🛑 Stopping StaySSH Bot (PID: $PID) via PID file..."
            kill -9 $PID 2>/dev/null || true
            echo "✅ Stopped PID $PID."
        fi
        rm -f "$PID_FILE"
    fi
    
    # 2. Try pkill as first fallback
    pkill -9 -f "stayssh.bot.main" 2>/dev/null || true
    
    # 3. Final aggressive sweep using ps/grep/awk
    PIDS=$(ps aux | grep "stayssh.bot.main" | grep -v grep | awk '{print $2}')
    if [ ! -z "$PIDS" ]; then
        echo "🛑 Killing lingering bot processes: $PIDS"
        echo "$PIDS" | xargs kill -9 2>/dev/null || true
    fi
    
    echo "✅ Cleanup complete."
}

# Parse arguments
CLEAN=false
RUN_TESTS=false
COMMIT_GATE=false
for arg in "$@"; do
    case $arg in
        --clean) CLEAN=true ;;
        --stop) stop_bot; exit 0 ;;
        --test) RUN_TESTS=true ;;
        --commit) COMMIT_GATE=true; RUN_TESTS=true ;;
        --help) show_help; exit 0 ;;
    esac
done

# Exit on error
set -e

# Always stop the previous bot instance on startup (Kill on startup only)
stop_bot || true

echo "🚀 Starting StaySSH Local Development Environment..."

# Handle clean start
if [ "$CLEAN" = true ]; then
    echo "🧹 Cleaning environment..."
    rm -rf "$VENV_DIR"
    find . -type d -name "__pycache__" -exec rm -rf {} +
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env not found. Copying .env.example to .env..."
    cp .env.example .env
    echo "❗ Please edit .env with your credentials before running again."
    exit 1
fi

# Export variables from .env
set -a
source .env
set +a

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "🛠️ Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"

# Run Tests if requested
if [ "$RUN_TESTS" = true ]; then
    echo "🧪 Running Unit Tests with Coverage Gate (${COVERAGE_THRESHOLD}%)..."
    pytest --cov=stayssh --cov-report=term-missing --cov-fail-under=$COVERAGE_THRESHOLD \
        tests/test_bot_batcher.py tests/test_bot_main.py tests/test_bot_sync.py tests/test_core_config.py \
        tests/test_db_connection.py tests/test_db_repositories.py tests/test_ssh_manager.py tests/test_ssh_tmux.py
    
    echo "🧪 Running Integration Tests (Real DB + Real SSH)..."
    RUN_INTEGRATION=true pytest tests/test_integration_db.py tests/test_integration_system.py
    
    echo "🧪 Running E2E Tests (Real SSH + Real DB)..."
    if [ -f tests/test_e2e_flow.py ]; then
        RUN_E2E=true pytest tests/test_e2e_flow.py
    else
        echo "ℹ️ No E2E tests found yet. Skipping..."
    fi
    
    echo "✅ All tests passed with ${COVERAGE_THRESHOLD}% coverage!"
    
    if [ "$COMMIT_GATE" = true ]; then
        echo "🚀 Coverage Gate Proved! Entering Commit Phase..."
        echo -n "📝 Enter commit message: "
        read commit_msg
        if [ -z "$commit_msg" ]; then
            echo "❌ Commit aborted: No message provided."
            exit 1
        fi
        git add .
        git commit -m "$commit_msg"
        echo "✅ Changes committed successfully."
    fi
    
    if [ "$COMMIT_GATE" = false ]; then
        echo "Proceeding to start the bot..."
    else
        exit 0
    fi
fi

# Initialize Database
echo "🔄 Creating Database (if not exists)..."
python -m scripts.create_db

echo "🔄 Initializing Database Tables..."
python -m stayssh.db.init_db

# Run the bot and save PID
echo "🤖 Starting StaySSH Bot..."
python -m stayssh.bot.main &
echo $! > "$PID_FILE"
echo "✅ Bot started with PID: $(cat $PID_FILE)"
echo "📝 Logs will appear in the console. Press Ctrl+C to stop (note: background process remains, use --stop to kill)."
wait
