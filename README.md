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
git clone https://github.com/youruser/stayssh-telegram.git
cd stayssh-telegram
# The run script handles venv creation automatically
./scripts/run_local.sh --test
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your details:
-   `TELEGRAM_TOKEN`: Your bot token.
-   `ADMIN_USER_ID`: Your numeric Telegram ID.
-   `HOST_SSH_URL`: `ssh://user@ip:port`
-   `SSH_KEY_PATH`: Absolute path to your private key.
-   `DATABASE_URL`: `postgresql+asyncpg://user:pass@localhost:5432/stayssh`

### 3. Run (Local)
```bash
# Start in background with logging
./scripts/run_local.sh
```

### 4. Run (Docker)
Ensure you have Docker and Docker Compose installed. The bot is configured to use an **external database** (either on the host or a remote server).

2.  **Configure `.env` for Docker**:
    If your database is running on the local host (outside Docker), update your `DATABASE_URL` to use `host.docker.internal` instead of `localhost`. 
    
    Also, ensure your `SSH_KEY_PATH` points to the **internal container path**. Since `./keys` is mapped to `/app/keys`, your `.env` should look like this:
    ```env
    DATABASE_URL=postgresql+asyncpg://user:pass@host.docker.internal:5432/stayssh
    SSH_KEY_PATH=/app/keys/your_key_file
    ```

3.  **Start the Bot**:
    ```bash
    # Build and start services
    docker-compose up -d --build

    # Initialize Database (first time only)
    docker-compose exec bot python -m stayssh.db.init_db
    ```

---

## 📖 Command Reference

The bot handles commands and raw text input. Ensure you have an **active session** selected before sending raw commands.

### Session Management
-   `/new <name>`: Create a new detached tmux session on the host and select it.
-   `/sessions`: List all active tmux sessions on the host.
-   `/switch <name>`: Switch the bot's active context to an existing session.
-   `/kill <name>`: Terminate a tmux session on the host.
-   `/status`: Show current connection info and the name of the active session.

### Terminal Interaction
-   **`<Any Text>`**: Send text followed by `Enter` (C-m) to the active session.
-   `/type <text>`: Type text raw into the session **without** sending an `Enter` (useful for passwords or partial commands).
-   `/key <key_name>`: Send a special tmux key sequence.
    -   *Examples*: `/key Escape`, `/key C-c` (Ctrl+C), `/key Up`, `/key Down`, `/key Tab`.
-   `/log <n>`: Capture and display the last `N` lines of history from the active pane (default: 20).

### Bot Administration
-   `/config`: View current bot settings.
-   `/config set <key> <value>`: Update settings (e.g., `BATCH_INTERVAL_MS`) on the fly.
-   `/restart`: Force the bot container/process to restart.

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

-   `stayssh/bot/`: Telegram handlers and message batching logic.
-   `stayssh/ssh/`: SSH connectivity and tmux orchestration.
-   `stayssh/db/`: Async SQLAlchemy models and repositories.
-   `docs/`: Detailed technical specifications and handoff docs.
-   `scripts/`: Management and lifecycle utilities.
