# StaySSH Telegram Bot

A robust, production-ready SSH Telegram bot with `tmux` persistence and adaptive delivery. Manage your remote servers directly from Telegram with high reliability and zero-hassle session management.

## 🚀 Key Features

- **Persistent Sessions**: Powered by `tmux` on the host, your processes keep running even if you disconnect.
- **Adaptive Batching**: Snappy output delivery when idle, efficient batching during command bursts.
- **Async & Fast**: Built with `python-telegram-bot` v20+ and `asyncssh`.
- **Quality Ensured**: Strict 100% test coverage requirement for all commits.
- **Database Driven**: Tracks user sessions and configurations in PostgreSQL.

## 🛠️ Local Development & Workflow

We use a consolidated management script `scripts/run_local.sh` to handle all phases of development.

### 1. Setup

Clone the repo and configure your environment:
```bash
cp .env.example .env
# Edit .env with your Telegram Token, SSH credentials, and DB URL
```

### 2. Running the Bot

To start the bot locally (this will automatically initialize the database and kill any stale instances):
```bash
./scripts/run_local.sh
```

### 3. Testing Pipeline

Run the full testing lifecycle (Unit -> Integration -> E2E):
```bash
./scripts/run_local.sh --test
```
- **Unit Tests**: Fast, uses mocks.
- **Integration Tests**: Requires a real PostgreSQL database (uses `RUN_INTEGRATION=true`).
- **E2E Tests**: Requires real SSH access to the host (uses `RUN_E2E=true`).

### 4. The Commit Gate (Quality Control)

We enforce a **100% Coverage Gate**. You cannot commit using our automated workflow unless all tests pass and coverage is perfect.

To verify and commit:
```bash
./scripts/run_local.sh --commit
```
If the gate is proved (100% coverage), the script will prompt you for a commit message and handle the `git add/commit` for you.

## 🐳 Deployment (Docker)

The bot is fully containerized. Use Docker Compose to spin up the bot and database:

```bash
docker-compose up -d
# Initialize DB inside the container
docker-compose exec bot python -m stayssh.db.init_db
```

## 📚 Documentation

Detailed technical docs can be found in the `docs/` folder:
- [Architecture](docs/architecture.md)
- [Design Specifications](docs/design.md)
- [Project Handoff](docs/handoff.md)
- [Test Plan](docs/tests.md)
