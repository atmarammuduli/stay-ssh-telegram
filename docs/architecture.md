# Implementation Plan - SSH Telegram Bot (StaySSH)

## Objective
Build a Dockerized Telegram bot that provides a robust SSH gateway to a **Docker host machine**, leveraging `tmux` for session persistence, multi-session management, and recovery.

## Technology Stack
- **Language**: Python 3.11+ (Async)
- **Telegram Library**: `python-telegram-bot` (v20+)
- **SSH Library**: `asyncssh`
- **Database**: PostgreSQL (External) - for persistence of sessions, active state, and user settings.
- **ORM**: `SQLAlchemy` (Async) or `Tortoise-ORM`.
- **Session Backend**: `tmux` (installed on the **Host machine**, not inside the container).

## Key Components

### 1. Host SSH & Tmux Integration
- **Host Discovery**: The bot connects to the Docker host via SSH (using host IP/socket).
- **Tmux Wrapper**:
    - `tmux ls`: Used to discover existing sessions on the host.
    - `tmux new-session -d -s <name>`: Create new background sessions.
    - `tmux capture-pane`: Periodically poll for new output.
- **Seamless Reattach**: On bot restart, it queries `tmux ls` on the host to resume monitoring active sessions stored in Postgres.

### 2. Dynamic Configuration & Persistence
- **Postgres Schema**:
    - `sessions`: ID, tmux_name, status, last_activity, creator_id.
    - `settings`: Key-value pairs for bot config (batch_interval, log_level, etc.).
- **On-the-fly Config**:
    - `/config set <key> <value>`: Updates the DB.
    - `/config reload`: Triggers a logic reload.
    - `/restart`: High-level command to trigger a container restart (requires Docker socket mount or a wrapper script).

### 3. Output Monitor & Adaptive Batcher
- **Background task per active session**:
    - Periodically polls `tmux capture-pane -p`.
    - Identifies new output via line-count/content diffing.
- **Adaptive Delivery Logic**:
    - **Idle State**: If no output has been sent recently and a new line appears, send it **immediately** (0ms delay) to ensure the UI feels snappy.
    - **Burst State**: If multiple lines arrive or if output is detected from *any* session while another is recently sent, switch to **Batch Mode**.
    - **Batch Mode**: Buffer all output across all sessions and flush to Telegram every X seconds (configurable, e.g., 2s).
    - **Auto-Reset**: Return to Idle State after Y seconds of silence.
- **Session Header**: In Batch Mode, prefix bundled messages with the session name (e.g., `[Session: WebServer] ...`) to maintain context.

### 4. Telegram Interface
- `/start`: Auth and help.
- `/new <name>`: New tmux session on host.
- `/sessions`: List all host tmux sessions (both bot-created and pre-existing).
- `/attach <name>`: Attach the bot's monitor to an existing host session.
- `/switch <id>`: Switch context.
- `/log <n> [session]`: Fetch the last `n` lines of output from the current (or specified) session in a single block. Uses `tmux capture-pane -S -<n>` to retrieve historical buffer.
- `/config`: View/Edit bot settings.
- `/restart`: Restarts the bot container to apply deep changes.

### 5. Docker Deployment
- **Mounts**: 
    - `/var/run/docker.sock` (Optional: for `/restart` command to work via Docker API).
    - SSH keys for host access.
- **Environment**: `DATABASE_URL`, `TELEGRAM_TOKEN`, `HOST_SSH_URL`.

## Proposed Steps

1.  **Project Initialization**: Set up `asyncssh`, `sqlalchemy`, and `python-telegram-bot`.
2.  **Database Layer**: Define Postgres schema and async migration/init logic.
3.  **Host Discovery Logic**: Implement `tmux ls` parser to find existing sessions on the host.
4.  **SSH/Tmux Execution**: Build the core async wrapper for host commands.
5.  **Config Management**: Implement the dynamic settings system in Postgres.
6.  **Bot Interface**: Build handlers for session management and config.
7.  **Container Management**: Implement the `/restart` logic using the Docker SDK.
8.  **Batching & Monitoring**: Finalize the output polling and differencing logic.
9.  **Dockerization**: Multi-stage build with optimized Alpine image.
