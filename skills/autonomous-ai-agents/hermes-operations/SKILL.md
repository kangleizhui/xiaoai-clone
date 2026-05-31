---
name: hermes-operations
description: Operate and observe a Hermes Agent instance — cron jobs, state DB analytics, usage tracking, and internal maintenance.
when_to_use:
  - User wants a recurring watchdog, health check, or scheduled script
  - User asks "how many tokens did I use", "export session history", or "what did this cost"
  - User wants to query Hermes internal state (sessions, messages, skills)
---

# Hermes Operations

This skill covers running and observing Hermes Agent itself: scheduling automated tasks and querying the local state database.

## CronJob Script Mode

Hermes has a built-in scheduler (`cronjob` tool) with two modes:
- **Agent mode** (`no_agent=False`): an LLM runs a prompt each tick.
- **Script mode** (`no_agent=True`): runs a script file and delivers stdout verbatim.

Use script mode for silent watchdogs and fixed-output tasks.

### Critical Rules

- `script` must be a **filename relative to `~/.hermes/scripts/`**, not inline code.
- `.sh`/`.bash` → runs via `bash`; everything else → runs via Python.
- **Never** use absolute paths; they are rejected.

### Silent Watchdog Pattern

Design scripts to stay quiet when healthy:

```bash
#!/bin/bash
usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$usage" -gt 80 ]; then
    echo "⚠️ Disk usage: ${usage}%"
fi
# Empty stdout → no message sent
```

Non-zero exit or timeout sends an error alert; non-empty stdout is delivered verbatim.

### Delivery Modes

| `deliver` | Behavior |
|-----------|----------|
| (omit) or `origin` | Auto-deliver to origin chat |
| `local` | No delivery, save only |
| `all` | Fan out to every connected channel |
| `platform:chat_id` | Specific destination |

### Workflow

1. Write script to `~/.hermes/scripts/<name>.sh`.
2. Test manually: `bash ~/.hermes/scripts/<name>.sh`.
3. Create job with `no_agent=True` and `script='<name>.sh'`.
4. Verify with `cronjob(action='list')`.

## State DB Analytics

Hermes stores session history, token counts, and cost estimates in `~/.hermes/state.db` (SQLite, WAL mode).

### Schema Essentials

| Table | Key Columns |
|-------|-------------|
| `sessions` | `id`, `model`, `started_at`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `api_call_count`, `estimated_cost_usd`, `billing_provider` |
| `messages` | `session_id`, `role`, `tool_name`, `token_count`, `timestamp` |

### Querying

Use Python's stdlib `sqlite3` — the `sqlite3` CLI is often not installed.

```python
import sqlite3, os
con = sqlite3.connect(os.path.expanduser("~/.hermes/state.db"))
```

Key recipes:
- **Lifetime summary**: `SELECT SUM(input_tokens), SUM(output_tokens), SUM(api_call_count) FROM sessions;`
- **Per-model breakdown**: `GROUP BY model ORDER BY SUM(input_tokens) DESC`
- **Per-day timeline**: `SELECT date(started_at, 'unixepoch', 'localtime') AS day, ... FROM sessions GROUP BY day`
- **CSV export**: read rows, write with `csv.writer`.

Always pass `'localtime'` to SQLite `date()` — `started_at` is UTC epoch.

### Interpretation Rules

1. `actual_cost_usd` is almost always 0. Treat `estimated_cost_usd` as a rough indicator only.
2. **Cache reads can dwarf raw input** — don't multiply `input_tokens + cache_read_tokens` by the headline price.
3. **Volcano Ark Coding Plan** bills by call count / subscription, not tokens. Token totals are recorded but don't map 1:1 to quota.
4. `api_call_count` is usually more interesting than token count for spotting heavy tool use.

### Pitfalls

- **Read-only queries are safe while Hermes is running.** Avoid writes — WAL mode handles concurrent reads but writes need exclusive access.
- **Schema drifts** across Hermes versions. Run `PRAGMA table_info(sessions)` if a column seems missing.

## References

- `scripts/usage_summary.py` — ready-to-run script that prints lifetime, per-model, per-provider, and per-day summaries.
