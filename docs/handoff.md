# StaySSH Project Handoff

## 📌 Project Status
- **Phase**: Functional & Deployment Complete
- **Current State**: Core bot functionality, robust interactive deployment (`deploy.sh`), UI enhancements (inline buttons, screenshots, aliases), and safety confirmations are fully implemented and verified.
- **Mandate**: **100% total statement coverage** is mandatory for all core modules.
- **Coverage Status**: 
    - **Unit Testing**: achieved **100% Statement Coverage** across all modules (`bot/`, `db/`, `ssh/`, `core/`).
    - **Aggregation**: Coverage is aggregated across Unit, Integration, and E2E tests using `--cov-append`.
    - **Verification**: Enforced via a strict coverage gate in `./scripts/run_local.sh --test`. This script MUST fail if any test fails or if total aggregated coverage is less than 100%.
- **Integration/E2E Tests**: These tests use real credentials from `.env`. Database passwords containing special characters must be URL-encoded (e.g., `$` -> `%24`, `%` -> `%25`).

## 🔄 Iterative Testing & Mitigation Workflow
To maintain the 100% coverage gate, follow this mandatory iterative process:
1. **Run**: Execute `./scripts/run_local.sh --test`.
2. **Inspect**: If it fails, carefully check the console logs for the specific cause (e.g., `InvalidPasswordError`, `InvalidCatalogNameError`, `ImportError`).
3. **Mitigate**: Apply targeted fixes (e.g., URL-encoding credentials in `.env`, fixing broken imports after refactoring, starting dependencies like PostgreSQL).
4. **Repeat**: Run the test script again. The task is only complete when the script returns a success code and confirms 100% aggregated coverage.

## 🛠 Refactoring for Testability
- **Handler Isolation**: All Telegram handlers have been moved from `bot/main.py` to `bot/handlers.py`.
- **Dependency Injection**: Managers (SSH, Tmux) are now injected via `bot_data`, enabling isolated unit testing of handlers with mocks and removing high-coupling issues that previously blocked 100% coverage.

## ⚠️ Known Gaps & Next Steps
1. **Integration/E2E Test Environment**: While tests are fully implemented and use real credentials, they require a correctly configured PostgreSQL instance and valid SSH access to pass. Ensure the database user and password in `.env` are accurate and properly escaped.

## ✨ Key Features Implemented
- **Interactive Terminal Support**: `/key` and `/type` commands with short aliases (`/ky`, `/t`).
- **Interactive UI**: Inline session switching buttons, `/screenshot` (`/ss`) for terminal snapshots.
- **Safety**: `/y` confirmation for `/kill`, `/restart`, and `/config`.
- **Robust Deployment**: Interactive `deploy.sh` script with git reset options and strict immunity for `.env`/`keys/`.

## 🧪 Testing & Quality Assurance
- **Unit Testing**: **100% Statement Coverage** achieved across all modules in the `tmux_ssh_telegram` package.
- **Integration Testing**: Comprehensive suite (`tests/test_integration_*.py`) verifying:
    - **Real DB**: Repository operations against PostgreSQL.
    - **Real SSH/Tmux**: Host connectivity, multi-session management, and output capturing.
    - **Provisioning**: Automatic `tmux` installation on the host if missing (supports `apt`, `yum`, `apk`, `brew`).
    - **Bot Orchestration**: Integrated testing of Telegram handlers with real DB and SSH layers.
    - **Note**: Use `docker-compose up -d db` to provide the database for these tests.
- **E2E Testing**: Full lifecycle verification (`tests/test_e2e_flow.py`) from Telegram handlers down to host command execution.
- **Verification**: Run `./scripts/run_local.sh --test` to execute the full suite.

## ⚙️ Environment Configuration
- **SSH Key**: The correct verified private key is `/Users/atmarammuduli/Documents/DOCs/Oracle-cloud-12may26/ssh-key-2026-05-17-5.key`. This has been updated in `.env`.
- **Database**: PostgreSQL (asyncpg) is required. Use `docker-compose up -d db` for local testing.
- **Admin**: The `ADMIN_USER_ID` is set in `.env` and automatically provisioned in the DB on startup to prevent foreign key violations.

## 📚 Technical Stack
- **Bot**: `python-telegram-bot` (v20+ async)
- **SSH/Tmux**: `asyncssh` + host `tmux`
- **DB**: `PostgreSQL` + `SQLAlchemy` (asyncpg)
- **Validation**: `Pydantic` V2
- **Testing**: `pytest`, `pytest-cov`, `hypothesis`
