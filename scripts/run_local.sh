#!/bin/bash

# Configuration
PID_FILE=".tmux_ssh_telegram.pid"
VENV_DIR="venv"
COVERAGE_THRESHOLD=100

# Help function
show_help() {
    echo "Usage: ./scripts/run_local.sh [OPTIONS]"
    echo "Options:"
    echo "  --test        Run all tests with coverage check (100% gate)"
    echo "  --stop        Stop any running bot instances"
    echo "  --help        Show this help message"
}

# Stop bot if running
stop_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "🛑 Stopping StaySSH Bot (PID: $PID)..."
            kill $PID
            rm "$PID_FILE"
            echo "✅ Bot stopped."
        else
            echo "⚠️ PID file found but process not running. Cleaning up..."
            rm "$PID_FILE"
        fi
    else
        echo "ℹ️ No running bot instance found."
    fi
}

# Parse arguments
RUN_TESTS=false
STOP_ONLY=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --test) RUN_TESTS=true ;;
        --stop) STOP_ONLY=true ;;
        --help) show_help; exit 0 ;;
        *) echo "Unknown parameter: $1"; show_help; exit 1 ;;
    esac
    shift
done

# Execute Stop if requested
if [ "$STOP_ONLY" = true ]; then
    stop_bot
    exit 0
fi

# Initial Cleanup
echo "🔍 Checking for running bot instances..."
stop_bot
echo "✅ Cleanup complete."

# Environment Setup
echo "🚀 Starting StaySSH Local Development Environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "🛠️ Installing dependencies..."
# Redirecting to /dev/null for cleaner output unless error
pip install -e . > /dev/null
pip install -e ".[dev]" > /dev/null

# Run Tests if requested
if [ "$RUN_TESTS" = true ]; then
    echo "🧪 Running Unit Tests..."
    # We run unit tests first, clear old coverage data
    pytest --cov=tmux_ssh_telegram --cov-report=term-missing \
        tests/test_bot_batcher.py tests/test_bot_handlers.py tests/test_bot_main.py tests/test_bot_sync.py tests/test_core_config.py \
        tests/test_db_connection.py tests/test_db_repositories.py tests/test_ssh_manager.py tests/test_ssh_tmux.py || { echo "❌ Unit tests failed"; exit 1; }
    
    echo "🧪 Running Integration Tests (Real DB + Real SSH)..."
    RUN_INTEGRATION=true pytest --cov=tmux_ssh_telegram --cov-append tests/test_integration_db.py tests/test_integration_system.py || { echo "❌ Integration tests failed"; exit 1; }
    
    echo "🧪 Running E2E Tests (Real SSH + Real DB)..."
    if [ -f tests/test_e2e_flow.py ]; then
        RUN_E2E=true pytest --cov=tmux_ssh_telegram --cov-append tests/test_e2e_flow.py || { echo "❌ E2E tests failed"; exit 1; }
    else
        echo "⚠️ E2E tests not found."
    fi
    
    echo "📊 Final Aggregated Coverage Report:"
    # Use coverage command directly to enforce the fail-under on aggregated data
    coverage report --fail-under=$COVERAGE_THRESHOLD
    RET=$?
    
    if [ $RET -ne 0 ]; then
        echo "FAIL Required aggregated test coverage of ${COVERAGE_THRESHOLD}% not reached."
        exit 1
    fi
    
    echo "✅ All tests passed with 100% coverage!"
    echo "🚀 Transitioning to bot execution..."
fi

# Run Bot
echo "🤖 Starting StaySSH Bot in background..."
python -m tmux_ssh_telegram.bot.main &
echo $! > "$PID_FILE"
echo "✅ Bot started with PID: $(cat $PID_FILE)"
echo "📝 Logs will appear in the console. Press Ctrl+C to stop (note: background process remains, use --stop to kill)."
wait
