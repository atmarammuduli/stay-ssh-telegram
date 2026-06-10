# Technical Specifications & Communication Contracts - StaySSH

## 1. Inter-Module Dependency Map
To ensure high modularity, the following dependency rules apply:
- **Core** -> No dependencies.
- **DB** -> Core (Models).
- **SSH** -> Core (Models).
- **Bot** -> Core, DB, SSH.
*No circular dependencies are permitted. All modules communicate via the DTOs defined in Section 2.*

---

## 2. Data Transfer Objects (DTOs) - The Shared Language
These Pydantic models define the *only* way data crosses module boundaries.

### `stayssh.core.models.SessionDTO`
- `id: int`, `name: str`, `status: SessionStatus`, `last_activity: datetime`.

### `stayssh.core.models.TmuxOutputDTO`
- `session_name: str`, `content: str`, `line_count: int`, `is_truncated: bool`.

### `stayssh.core.models.CommandResultDTO`
- `exit_code: int`, `stdout: str`, `stderr: str`, `duration: float`.

---

## 3. Communication Protocols (Class & Method Levels)

### Protocol: Bot <-> SSH (Output Polling)
1. **Request**: `bot.Monitor` calls `ssh.capture_diff(name, last_ln)`.
2. **Contract**: `ssh` returns a `TmuxOutputDTO`.
3. **Requirement**: If SSH is disconnected, `ssh` must NOT return None; it must raise `SSHDisconnectedError`.

### Protocol: Bot <-> DB (Persistence)
1. **Request**: `bot.Handler` calls `db.update_session_status(id, status)`.
2. **Contract**: `db` returns a `bool` (success/fail).
3. **Constraint**: `db` operations are atomic and use a connection pool.

---

## 4. Error Propagation & Handling Contracts
Each module has a "Boundary Exception" that it must use when communicating with other modules:

- **SSH Module**: Raises `SSHBaseError` subclasses (`ConnectionError`, `TmuxError`).
- **DB Module**: Raises `DBBaseError` subclasses (`IntegrityError`, `TimeoutError`).
- **Bot Module**: Catches all `SSHBaseError` and `DBBaseError` to provide user-friendly Telegram feedback.

---

## 5. Exhaustive Function Contracts (2.3)
*(Detailed table of every function, its DTO inputs, DTO outputs, and potential Exceptions - see exhaustive list below)*

| Module.Function | Input DTOs | Output DTOs | Exceptions | Side Effects |
| :--- | :--- | :--- | :--- | :--- |
| `db.get_sessions` | None | `List[SessionDTO]` | `DBTimeout` | Read-only |
| `ssh.run_raw` | `str` (cmd) | `CommandResultDTO` | `SSHExecError` | Remote Exec |
| `ssh.get_diff` | `str, int` | `TmuxOutputDTO` | `TmuxError` | Remote Read |
| `bot.send_out` | `TmuxOutputDTO`| `bool` | `TelegramAPIError`| Network I/O |
