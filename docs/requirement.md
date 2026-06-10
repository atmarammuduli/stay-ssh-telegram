# SSH Telegram Bot Requirements (StaySSH)

## Overview
A Docker-deployable Telegram bot that serves as a robust SSH gateway to a **host machine**. It leverages `tmux` on the host for session persistence, multi-session management, and seamless recovery, with all state persisted in an external PostgreSQL database.

## Core Features

### 1. Host-Level SSH & Session Management
- **Host Gateway**: Access and manage the Docker host machine's shell, not just the container's internal shell.
- **Tmux Discovery**: Automatically discover and attach to existing `tmux` sessions running on the host.
- **Multi-Session**: Create, list, switch, and kill multiple independent `tmux` sessions.
- **Persistence**: Sessions remain active on the host even if the bot container restarts or the SSH connection drops.

### 2. Command Execution & Feedback
- **Real-time Interaction**: Pass commands from Telegram to the host and receive output.
- **Intelligent Batching**: Club host responses within a configurable window (e.g., 2-3 seconds) to prevent Telegram notification spam.
- **Output Diffing**: Only send new lines of output since the last update to keep the chat history clean.

### 3. Dynamic Configuration & Persistence
- **External Persistence**: Use PostgreSQL to store session metadata, active states, and user preferences.
- **On-the-fly Config**: Modify bot settings (batch intervals, log levels, connection details) directly via Telegram commands.
- **Self-Management**: A `/restart` command to trigger a container restart to apply deep configuration changes.

### 4. Monitoring & Recovery
- **Automatic Re-attach**: On bot startup, it resumes monitoring active sessions by syncing with the host's `tmux` state.
- **Status Reporting**: Check process status (e.g., "Command X running for Y minutes").
- **Error Notifications**: Internal application errors and SSH connectivity issues are reported directly to the Telegram channel.
- **Persistent Logging**: Application logs are stored in a configurable local directory (e.g., `logs/`), which maps to `/var/log` on the host when containerized, using a rotation strategy.

## Technical Requirements
- **Language**: Python 3.11+ (Asyncio)
- **Libraries**: `python-telegram-bot`, `asyncssh`, `SQLAlchemy`.
- **Backend**: PostgreSQL (External).
- **Deployment**: 
    - Docker container.
    - Requires SSH access to the host (keys/socket).
    - Optional: Docker socket mount for self-restart capability.

## User Interface (Telegram)
- `/new <name>`: Start a new named session on the host.
- `/sessions`: List all available host tmux sessions.
- `/attach <name>`: Attach the bot's monitor to an existing host session.
- `/switch <id>`: Switch the current active context.
- `/config`: View and modify bot settings on the fly.
- `/restart`: Force a bot container restart.
- `<Any Text>`: Sent as a command to the active session.
