# System Design - StaySSH

## 1. Architecture Overview

```text
[ Telegram App ] <--> [ Telegram API ] <--> [ StaySSH Bot (Docker Container) ]
                                                   |
                                                   +--> [ PostgreSQL DB (External) ]
                                                   |
                                                   +--> [ Host Machine (via SSH) ]
                                                            |
                                                            +--> [ tmux Session A ]
                                                            +--> [ tmux Session B ]
```

### Data Flow
1. **Command Flow**: User sends text to Bot -> Bot checks active session -> Bot sends command to host `tmux send-keys` -> tmux executes on host.
2. **Output Flow**: Bot's Monitor Task periodically polls host `tmux capture-pane` -> New output detected -> Adaptive Batcher decides whether to send immediately or buffer -> Bot sends message(s) to Telegram.
3. **Config Flow**: User sends `/config` -> Bot updates Postgres -> Internal settings cache is invalidated/refreshed.

---

## 2. PostgreSQL Schema

### Table: `users`
- `id`: BIGINT (Primary Key) - Telegram User ID.
- `active_session_id`: INTEGER (Foreign Key to `sessions.id`, Nullable).
- `is_admin`: BOOLEAN (Default: False).
- `created_at`: TIMESTAMP (Default: NOW).

### Table: `sessions`
- `id`: SERIAL (Primary Key).
- `name`: VARCHAR(64) (Unique, Not Null) - The tmux session name.
- `description`: TEXT.
- `status`: VARCHAR(20) (e.g., 'active', 'detached', 'dead').
- `creator_id`: BIGINT (Foreign Key to `users.id`).
- `last_activity`: TIMESTAMP.
- `created_at`: TIMESTAMP (Default: NOW).

### Table: `settings`
- `key`: VARCHAR(64) (Primary Key).
- `value`: TEXT (JSON-encoded or plain string).
- `updated_at`: TIMESTAMP (Default: NOW).

*Default Settings*:
- `BATCH_INTERVAL_MS`: "2000"
- `IDLE_THRESHOLD_MS`: "5000"
- `MAX_LOG_LINES`: "100"
- `POLL_INTERVAL_MS`: "500"
- `LOG_LEVEL`: "INFO"
- `LOG_DIR`: "./logs"

---

## 3. Adaptive Batching State Machine

### States
- **IDLE**: No output sent for > `IDLE_THRESHOLD_MS`.
- **ACTIVE**: Single message sent, waiting to see if more follow.
- **BURST**: Multiple sessions or high-volume output detected; buffering enabled.

### Transitions & Logic

1. **Initial State: IDLE**
   - *Event*: New output received.
   - *Action*: Send output **instantly** to Telegram. Update `last_sent_time`.
   - *Transition*: Move to **ACTIVE**.

2. **State: ACTIVE**
   - *Event*: New output received AND `now - last_sent_time < 500ms`.
   - *Action*: Do not send. Add to buffer.
   - *Transition*: Move to **BURST**.
   - *Event*: Timer expires (`500ms` silence).
   - *Transition*: Move to **IDLE**.

3. **State: BURST**
   - *Event*: New output received.
   - *Action*: Append to buffer. Identify session source.
   - *Event*: Batch Timer (`BATCH_INTERVAL_MS`) triggers.
   - *Action*: Flush buffer. Bundle by session name. Send single Telegram message. Update `last_sent_time`.
   - *Event*: Silence for > `IDLE_THRESHOLD_MS`.
   - *Action*: Move to **IDLE**.

---

## 4. SSH & Tmux Logic Flow

### Session Discovery
- On startup, bot runs `tmux ls -F "#{session_name}"`.
- Cross-references with `sessions` table in DB.
- Any "orphan" tmux sessions found on host are marked as available for attachment.

### Output Differencing
- For each session, bot tracks `last_line_count`.
- `tmux capture-pane -p -t <name>` returns full pane.
- Bot takes `lines[last_line_count:]` to get only new content.
- Handles edge cases like `tmux clear-history` or pane being wiped.
