#!/bin/bash

# Configuration
PID_FILE=".stayssh.pid"
VENV_DIR="venv"

# Help function
show_help() {
    echo "Usage: ./scripts/run_local.sh [OPTIONS]"
    echo "Options:"
    echo "  --clean    Remove virtual environment and local cache before starting"
    echo "  --stop     Stop the running bot instance"
    echo "  --help     Show this help message"
}

# Stop function
stop_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "🛑 Stopping StaySSH Bot (PID: $PID)..."
            kill "$PID"
            rm "$PID_FILE"
            echo "✅ Stopped."
        else
            echo "⚠️ PID file found but process is not running. Cleaning up..."
            rm "$PID_FILE"
        fi
    else
        echo "ℹ️ No running instance found (no PID file)."
    fi
}

# Parse arguments
CLEAN=false
for arg in "$@"; do
    case $arg in
        --clean) CLEAN=true ;;
        --stop) stop_bot; exit 0 ;;
        --help) show_help; exit 0 ;;
    esac
done

# Exit on error
set -e

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

# Initialize Database
echo "🔄 Initializing Database..."
python -m stayssh.db.init_db

# Run the bot and save PID
echo "🤖 Starting StaySSH Bot..."
python -m stayssh.bot.main &
echo $! > "$PID_FILE"
echo "✅ Bot started with PID: $(cat $PID_FILE)"
echo "📝 Logs will appear in the console. Press Ctrl+C to stop (note: background process remains, use --stop to kill)."
wait
