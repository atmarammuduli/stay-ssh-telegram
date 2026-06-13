# StaySSH Project Roadmap & Effort Estimation

## 1. Revised Effort Estimation (Total: ~35-48 Hours)

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Design & Tech Specs** | Module/Class/Func contracts, 2.1-2.3 specification, DB Schema ERD. | ✅ COMPLETE |
| **Infrastructure & CI** | Scaffolding, `run_local.sh`, Static analysis setup. | ✅ COMPLETE |
| **Core Engine & Persistence**| Contract-first implementation of SSH, Tmux, and DB. | ✅ COMPLETE |
| **Telegram & Adaptive Batching** | Adaptive logic and UI/UX with strict state machines. | ✅ COMPLETE |
| **Testing (100% Cov)** | Unit, Property, Stress, and E2E tests. | ✅ COMPLETE |
| **Deployment & UI Polish** | `deploy.sh`, Inline Buttons, Screenshots, Aliases. | ✅ COMPLETE |

---

## 2. Technical Analysis & Progress
- **Adaptive Batching**: Successfully implemented a state machine that switches between immediate delivery (low latency) and bundled updates (high throughput/anti-spam).
- **Session Persistence**: Tmux-on-host strategy ensures zero data loss during bot restarts.
- **Modularity**: Strict DTO-based communication between SSH/DB and Bot modules.
- **Coverage**: Current coverage is ~75% and rising; tests are verified via `run_local.sh --test`.

---

## 2. Refined Workflow

### Step 1: Final System Design
- **Architecture Diagram**: Data flow between Telegram, Postgres, and Host SSH.
- **Postgres Schema**: ERD and relational constraints.
- **Adaptive Batching State Machine**: Detailed logic for Idle vs. Burst states.

### Step 2: Technical Specifications & Contracts
- **2.1 Module Contracts**: Define boundaries and public APIs for `bot`, `ssh`, `db`, and `core`.
- **2.2 Class/File Contracts**: Define responsibilities, state invariants, and lifecycle for each class (e.g., `TmuxSession`, `SSHManager`).
- **2.3 Function Contracts**: Define inputs (types/bounds), outputs (types/structure), and side-effects for every function.
- **Type Safety**: Use `Pydantic` for data validation and `Mypy` for strict static analysis.

### Step 3: Comprehensive Testing Strategy (Target: 100% Coverage)
- **3.1 Unit Tests**:
    - **Logic Tests**: Diffing algorithms and adaptive timers.
    - **Property-Based Testing**: Use `Hypothesis` to test batching logic with random output bursts to find edge cases.
- **3.2 Integration Tests**:
    - **Database**: Verify all CRUD operations and migrations.
    - **Tmux Mocking**: Verify SSH commands against a mock tmux environment.
- **3.3 Concurrency Stress Tests**:
    - Simulate 10+ concurrent high-volume sessions to verify batching and rate-limiting.
- **3.4 End-to-End (E2E)**:
    - Real command flow from Telegram mock client to local host tmux.

## 3. Quality Metrics & Guardrails
- **Coverage**: 100% statement and branch coverage required.
- **Linting/Style**: `Ruff` and `Black` for strict adherence to PEP8.
- **Complexity**: `Radon` or `Xenon` to ensure cyclomatic complexity stays low.
- **Dependency Audit**: `Safety` to check for vulnerable packages.

### Step 4: Implementation
- Iterative coding following the Tech Specs.

### Step 5: Testing & Deployment
- `run_local.sh`: Spins up local Postgres + Bot (direct Python execution).
- `deploy.sh`: Builds and launches via Docker Compose for production/host use.
