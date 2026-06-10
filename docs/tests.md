# Test Cases & Test Suites - StaySSH

## 1. Unit Test Suite (Target: 100% Branch Coverage)

### 1.1 `stayssh.core.config`
- **T-CORE-01**: Verify settings are loaded from environment variables.
- **T-CORE-02**: Verify settings are loaded from DB and cached.
- **T-CORE-03**: Verify invalid setting types raise `InvalidConfigTypeError`.

### 1.2 `stayssh.ssh.tmux` (Logic only - Mapped to `capture_diff`)
- **T-SSH-01**: `capture_diff` returns empty string if line count hasn't changed.
- **T-SSH-02**: `capture_diff` returns only new lines if line count increased.
- **T-SSH-03**: `capture_diff` handles "pane cleared" scenario (line count reset).
- **T-SSH-04**: Verify parsing of `tmux ls` output into `List[SessionDTO]`.

### 1.3 `stayssh.bot.batcher` (Adaptive Batching)
- **T-BOT-01**: **Property-Based Testing (Hypothesis)**: Generate random sequences of output bursts. Verify that:
    - No output is lost.
    - Telegram character limits (4096) are never exceeded (buffer splits correctly).
    - Batch timer never exceeds `BATCH_INTERVAL_MS` + jitter.
- **T-BOT-02**: Verify transition from IDLE -> ACTIVE on first message.
- **T-BOT-03**: Verify transition from ACTIVE -> BURST on high-frequency messages.
- **T-BOT-04**: Verify transition BURST -> IDLE after silence threshold.

---

## 2. Integration Test Suite

### 2.1 Database (PostgreSQL)
- **T-DB-01**: Verify async connection pool initialization.
- **T-DB-02**: Verify user/session CRUD operations maintain referential integrity.
- **T-DB-03**: Verify session status updates persist across bot restarts.

### 2.2 SSH Mocking (Contract Verification)
- **T-INT-01**: Simulate SSH connection drop. Verify `SSHManager` raises `SSHDisconnectedError` and triggers bot notification.
- **T-INT-02**: Simulate `tmux` not installed on host. Verify graceful error handling.

---

## 3. Concurrency & Stress Tests

### 3.1 High-Volume Logging
- **T-STRESS-01**: Simulate 10 concurrent sessions emitting 100 lines/second each.
- **Requirement**: Bot must not crash; CPU usage must remain stable; Message batching must consolidate logs into < 1 message/2 seconds per session group.

### 3.2 Race Conditions
- **T-STRESS-02**: Simulate concurrent `/switch` and `/kill` commands for the same session.
- **Requirement**: DB state must remain consistent; SSH commands must not overlap or corrupt.

---

## 4. End-to-End (E2E) Test Suite

### 4.1 Happy Path
- **T-E2E-01**: Telegram Mock -> `/new test` -> SSH `tmux new` -> Output `hello` -> Telegram Mock.
- **T-E2E-02**: Telegram Mock -> `/log 10` -> SSH `tmux capture-pane` -> Telegram Mock.

### 4.2 Recovery Path
- **T-E2E-03**: Bot Process Kill -> Bot Restart -> `tmux ls` Discovery -> Resume monitoring without user intervention.
