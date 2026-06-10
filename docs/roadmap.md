# StaySSH Project Roadmap & Effort Estimation

## 1. Revised Effort Estimation (Total: ~35-48 Hours)

| Phase | Description | Estimated Effort |
| :--- | :--- | :--- |
| **Design & Tech Specs** | Module/Class/Func contracts, 2.1-2.3 specification, DB Schema ERD. | 6-8 Hours |
| **Infrastructure & CI** | Scaffolding, `run_local.sh`, Mypy/Ruff/Safety/Coverage configuration. | 4-5 Hours |
| **Core SSH/Tmux Engine** | Contract-first implementation, asyncssh wrappers, tmux parsing logic. | 6-8 Hours |
| **Persistence & State** | Postgres models, async migrations, rigorous error handling for DB state. | 5-7 Hours |
| **Telegram & Adaptive Batching** | Multi-session logic, burst-handling state machine, UI/UX refinement. | 6-8 Hours |
| **Rigorous Testing (100% Cov)** | Unit, Property-based (Hypothesis), Stress, and E2E tests. | 6-10 Hours |
| **Deployment & Validation** | `deploy.sh`, Docker Compose, Final audit and documentation. | 2-2 Hours |

*Note: The increase in effort reflects the shift from "standard development" to "high-assurance engineering" (100% coverage, strict contracts, and property-based testing).*

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
