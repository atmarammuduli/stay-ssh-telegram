# StaySSH Telegram Bot

A robust, production-ready SSH Telegram bot that provides a secure gateway to your Docker host or any remote server. It leverages `tmux` for session persistence, multi-session management, and adaptive output delivery.

## 🚀 Key Features

-   **Session Persistence**: Close Telegram and come back later; your terminal state is preserved via `tmux`.
-   **Multi-Session Support**: Manage multiple independent terminal sessions on the same host.
-   **Interactive Terminal Support**: Send special keys (Escape, Ctrl+C) and type raw text to operate apps like `vim`, `nano`, or interactive CLIs.
-   **Adaptive Batching**: Intelligently bundles output to avoid Telegram rate limits while maintaining snappy responsiveness.
-   **Auto-Provisioning**: Automatically installs `tmux` on the host if it's missing (supports apt, yum, apk, brew).
-   **Robust Security**: Strict admin-only access and encrypted SSH communication.

## 🛠 Setup & Installation

### Prerequisites
-   Python 3.9+
-   PostgreSQL (Running locally or via Docker)
-   An SSH host with a private key (RSA/PEM)
-   A Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### 1. Clone & Install
```bash
git clone https://github.com/youruser/tmux_ssh_telegram-telegram.git
cd tmux_ssh_telegram-telegram
# The run script handles venv creation automatically
./scripts/run_local.sh --test
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your details:
-   `TELEGRAM_TOKEN`: Your bot token.
-   `ADMIN_USER_ID`: Your numeric Telegram ID.
-   `HOST_SSH_URL`: `ssh://user@ip:port`
-   `SSH_KEY_PATH`: Absolute path to your private key.
-   `DATABASE_URL`: `postgresql+asyncpg://user:pass@localhost:5432/tmux_ssh_telegram`

### 3. Run (Local)
```bash
# Start in background with logging
./scripts/run_local.sh
```

### 4. Run (Docker)
Ensure you have Docker and Docker Compose installed.

1.  **Deploy using the script**:
    We provide a robust deployment script that handles environment setup and naming consistency.
    ```bash
    chmod +x deploy.sh
    ./deploy.sh
    ```

2.  **Configure `.env` for Docker**:
    If your database is running on the local host (outside Docker), update your `DATABASE_URL` to use `host.docker.internal` instead of `localhost`. 
    
    Also, ensure your `SSH_KEY_PATH` points to the **internal container path**. Since `./keys` is mapped to `/app/keys`, your `.env` should look like this:
    ```env
    DATABASE_URL=postgresql+asyncpg://user:pass@host.docker.internal:5432/tmux_ssh_telegram
    SSH_KEY_PATH=/app/keys/your_key_file
    ```

---

## 📖 Interactive Usage Guide

StaySSH is designed to handle interactive CLI tools. Since Telegram is message-based, follow these patterns:

### 1. Basic Commands
Send any text as a normal message. The bot appends an `Enter` automatically.
- *Input*: `ls -la`
- *Action*: Executes `ls -la` on host.

### 2. The `/type` Command (No Enter)
Use `/type` when you need to provide input **without** sending a newline. This is essential for:
- **Passwords**: `/type mysecretpassword` (followed by `/key Enter`)
- **Partial Commands**: Type half a command, then use `/key Tab` for completion.

### 3. Using `nano` or `vim`
1.  **Open**: Send `nano myfile.txt`.
2.  **Navigate**: Use `/key Up`, `/key Down`, etc.
3.  **Edit**: Send text messages to insert content.
4.  **Save & Exit (nano)**:
    -   Send `/key C-o` (Write Out)
    -   Send `/key Enter` (Confirm filename)
    -   Send `/key C-x` (Exit)
5.  **Save & Exit (vim)**:
    -   Send `/key Escape`
    -   Send `:wq` (this sends `:wq` + Enter)

### 4. Interactive CLIs (e.g., Gemini CLI)
If a tool asks a Yes/No question:
-   Send `y` or `n`.
-   If it requires a specific key to confirm, use `/key Enter`.

---

## ⌨️ Supported Keys & Combos

The `/key` command supports any standard tmux/X11 key name:

-   **Navigation**: `Up`, `Down`, `Left`, `Right`, `PageUp`, `PageDown`, `Home`, `End`
-   **Editing**: `Tab`, `BSpace` (Backspace), `Delete`, `Enter`, `Escape`, `Space`
-   **Function Keys**: `F1` through `F12`
-   **Control Combos**: `C-c` (Interrupt), `C-d` (EOF), `C-z` (Suspend), `C-l` (Clear Screen), `C-a`, `C-b`, etc.

---

## 🛠 Command Reference

### Session Management
-   `/new <name>`: Create a new detached tmux session on the host and select it.
-   `/sessions`: List all active tmux sessions on the host.
-   `/switch <name>`: Switch the bot's active context to an existing session.
-   `/kill <name>`: Terminate a tmux session on the host.
-   `/status`: Show current connection info and the name of the active session.

### Bot Administration
-   `/config`: View or update settings (e.g., `BATCH_INTERVAL_MS`).
-   `/restart`: Force the bot process to restart.

---

## 🧪 Testing & Quality

We maintain **100% Statement Coverage** for core logic.

```bash
# Run unit, integration, and E2E tests
./scripts/run_local.sh --test
```

-   **Unit Tests**: Mocked interactions; no external services required.
-   **Integration Tests**: Real DB + Real SSH verification.
-   **E2E Tests**: Full flow from Telegram handlers to Host Shell.

---

## 📂 Project Structure

-   `tmux_ssh_telegram/bot/`: Telegram handlers and message batching logic.
-   `tmux_ssh_telegram/ssh/`: SSH connectivity and tmux orchestration.
-   `tmux_ssh_telegram/db/`: Async SQLAlchemy models and repositories.
-   `docs/`: Detailed technical specifications and handoff docs.
-   `scripts/`: Management and lifecycle utilities.
