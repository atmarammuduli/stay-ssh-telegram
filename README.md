# StaySSH Telegram Bot

A robust, production-ready SSH Telegram bot that provides a secure gateway to your Docker host or any remote server. It leverages `tmux` for session persistence, multi-session management, and adaptive output delivery.

## 🚀 Quick Start (Deployment)

We provide a robust interactive deployment script for easy setup on any system.

```bash
chmod +x deploy.sh
./deploy.sh
```

### Deployment Features:
-   **Interactive Git Updates**: Choose between a standard `git pull` or a `git reset --hard` (Default) to ensure a clean codebase.
-   **Immune Config**: Your `.env` and `keys/` directory are **strictly immune** to resets and cleaning via `.gitignore` protection.
-   **Optional Cleaning**: Optionally remove other untracked files while keeping your config safe.
-   **Auto-Detection**: Automatically detects and uses `docker compose` (V2) or `docker-compose` (V1).
-   **Auto-Initialization**: Handles database setup and starts log tailing automatically.

---

## 🛠 Command Reference & Aliases

StaySSH supports short aliases for all commands to make mobile usage faster.

| Command | Alias | Description |
| :--- | :--- | :--- |
| `/sessions` | `/ls` | List sessions with **interactive buttons**. |
| `/switch` | `/sw` | Switch bot context to a specific session. |
| `/screenshot` | `/ss` | Capture a **full-screen snapshot** (sees footers/status). |
| `/status` | `/s` | Show connection and active session info. |
| `/new` | `/n` | Create and select a new tmux session. |
| `/kill` | `/k` | Force kill a session and its processes. |
| `/log` | `/l` | View the last N lines of terminal history. |
| `/key` | `/ky` | Send special keys (e.g., `Escape`, `Tab`, `C-c`). |
| `/type` | `/t` | Send raw text **without** a newline (Enter). |
| `/config` | `/c` | View or update bot settings (e.g., batch interval). |
| `/restart` | `/r` | Hard restart the bot process/container. |

---

## 📖 Interactive Usage Guide

StaySSH is designed for heavy CLI usage (Gemini, nano, vim).

### 1. Basic Commands
Send any text as a normal message. The bot appends `Enter` (C-m) automatically.
- *Input*: `ls -la`
- *Action*: Executes `ls -la` on host.

### 2. The `/type` | `/t` Command (No Enter)
Use this for passwords or partial commands (for Tab completion).
- *Input*: `/t mysecretpassword` (followed by `/ky Enter`)

### 3. Using `nano` or `vim`
1.  **Open**: Send `nano myfile.txt`.
2.  **Navigate**: Use `/ky Up`, `/ky Down`, etc.
3.  **Edit**: Send text messages to insert content.
4.  **Save & Exit (nano)**: `/ky C-o` -> `/ky Enter` -> `/ky C-x`.
5.  **Save & Exit (vim)**: `/ky Escape` -> `:wq`.

### 4. Interactive CLIs (e.g., Gemini CLI)
-   **Snapshots**: Use `/ss` at any time to see the **entire terminal screen**, including the fixed Gemini footer, quota, and branch info.
-   **Interrupt**: Use `/ky C-c` to cancel long-running model tasks.

---

## 📂 Project Structure

-   `tmux_ssh_telegram/bot/`: Telegram handlers and message batching logic.
-   `tmux_ssh_telegram/ssh/`: SSH connectivity and tmux orchestration.
-   `tmux_ssh_telegram/db/`: Async SQLAlchemy models and repositories.
-   `docs/`: Detailed technical specifications and handoff docs.
-   `scripts/`: Management and lifecycle utilities.

## 🧪 Testing & Quality

We maintain **100% Statement Coverage** for core logic.

```bash
# Run unit, integration, and E2E tests
./scripts/run_local.sh --test
```
