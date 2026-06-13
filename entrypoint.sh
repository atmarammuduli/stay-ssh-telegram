#!/bin/sh
set -e

echo "Ensuring database exists..."
python -m scripts.create_db

echo "Initializing database tables..."
python -m tmux_ssh_telegram.db.init_db

echo "Starting bot..."
exec python -m tmux_ssh_telegram.bot.main
