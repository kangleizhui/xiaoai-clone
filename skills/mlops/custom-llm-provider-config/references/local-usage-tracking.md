# Local Usage Tracking — Hermes `state.db` Fallback

Volcano Engine Ark / Coding Plan **does not expose a public billing or usage OpenAPI**. The only
official way to see token consumption, call counts, or quota use is to log into
https://console.volcengine.com/ark → 资源管理 / 调用统计 / 费用账单 manually.

When the user asks "how many tokens did I use" / "how much did I spend" / "which model used the most",
fall back to Hermes' own local accounting in `~/.hermes/state.db`. It records every session's
input/output/cache tokens, API call count, provider, model, and estimated cost.

This is **provider-agnostic** — works for any backend, not just Volcano — but Volcano users hit it
most often because Volcano doesn't have a billing API.

## Schema (relevant columns of `sessions` table)

```
id                       TEXT   PRIMARY KEY   -- session UUID, e.g. 20260525_040147_48a9dc71
source                   TEXT                  -- 'cli' / 'qq' / 'telegram' / ...
model                    TEXT                  -- e.g. 'ark-code-latest', 'deepseek-v4-pro'
billing_provider         TEXT                  -- 'custom', 'deepseek', 'openai', ...
billing_base_url         TEXT                  -- distinguishes ark coding/v3 vs api/v3 etc.
billing_mode             TEXT
started_at               REAL                  -- unix epoch seconds
ended_at                 REAL
message_count            INTEGER
api_call_count           INTEGER               -- LLM round-trips (request count)
input_tokens             INTEGER
output_tokens            INTEGER
cache_read_tokens        INTEGER               -- prompt cache hits (often huge for ark)
cache_write_tokens       INTEGER
reasoning_tokens         INTEGER               -- only set by reasoning models
estimated_cost_usd       REAL                  -- best-effort, based on Hermes pricing tables
actual_cost_usd          REAL                  -- usually 0 — providers rarely return real bill
cost_status              TEXT
title                    TEXT
```

Note: `sqlite3` CLI is **not installed by default** on these Tencent Cloud Debian boxes. Use
Python's stdlib `sqlite3` via `execute_code` or `python3 -c`.

## Recipes

### 1. All-time totals + per-provider + per-model breakdown

```python
import sqlite3, os
con = sqlite3.connect(os.path.expanduser("~/.hermes/state.db"))
cur = con.cursor()

row = cur.execute("""
  SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens),
         SUM(cache_read_tokens), SUM(api_call_count),
         SUM(estimated_cost_usd)
  FROM sessions
""").fetchone()
print(f"sessions={row[0]} in={row[1]:,} out={row[2]:,} cache_r={row[3]:,} "
      f"calls={row[4]} est=${row[5] or 0:.4f}")

print("\nBy provider:")
for r in cur.execute("""
  SELECT billing_provider, COUNT(*), SUM(input_tokens), SUM(output_tokens),
         SUM(estimated_cost_usd)
  FROM sessions GROUP BY billing_provider ORDER BY SUM(input_tokens) DESC
"""):
    print(f"  {r[0] or '(unknown)':12s} sessions={r[1]} in={r[2] or 0:,} "
          f"out={r[3] or 0:,} est=${r[4] or 0:.4f}")

print("\nBy model:")
for r in cur.execute("""
  SELECT model, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(api_call_count)
  FROM sessions GROUP BY model ORDER BY SUM(input_tokens) DESC LIMIT 15
"""):
    print(f"  {(r[0] or '(none)')[:35]:35s} sessions={r[1]} in={r[2] or 0:,} "
          f"out={r[3] or 0:,} calls={r[4] or 0}")
```

### 2. Per-day usage (last N days)

```python
import sqlite3, os, datetime
con = sqlite3.connect(os.path.expanduser("~/.hermes/state.db"))
for r in con.execute("""
  SELECT date(started_at, 'unixepoch', 'localtime') AS day,
         COUNT(*) AS sessions,
         SUM(api_call_count) AS calls,
         SUM(input_tokens) AS in_tok,
         SUM(output_tokens) AS out_tok,
         SUM(cache_read_tokens) AS cache_r,
         SUM(estimated_cost_usd) AS est
  FROM sessions
  GROUP BY day
  ORDER BY day DESC LIMIT 30
"""):
    print(f"{r[0]} sess={r[1]} calls={r[2] or 0} in={r[3] or 0:,} "
          f"out={r[4] or 0:,} cache_r={r[5] or 0:,} est=${r[6] or 0:.4f}")
```

### 3. Today / last 7 days

```python
import sqlite3, os, datetime
con = sqlite3.connect(os.path.expanduser("~/.hermes/state.db"))
today_start = datetime.datetime.now().replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
week_start  = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()

for label, since in [("today", today_start), ("last 7d", week_start)]:
    r = con.execute("""
      SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens),
             SUM(api_call_count), SUM(estimated_cost_usd)
      FROM sessions WHERE started_at >= ?
    """, (since,)).fetchone()
    print(f"{label:7s} sess={r[0]} in={r[1] or 0:,} out={r[2] or 0:,} "
          f"calls={r[3] or 0} est=${r[4] or 0:.4f}")
```

### 4. CSV export for the user

```python
import sqlite3, os, csv, datetime
con = sqlite3.connect(os.path.expanduser("~/.hermes/state.db"))
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = "/tmp"  # or ~/.openclaw/media/qqbot for QQ delivery
os.makedirs(out_dir, exist_ok=True)
path = f"{out_dir}/hermes_tokens_sessions_{ts}.csv"

with open(path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["session_id","model","source","started_at","msgs","api_calls",
                "input","output","cache_read","est_usd","title"])
    for r in con.execute("""
      SELECT id, model, source,
             datetime(started_at, 'unixepoch', 'localtime'),
             message_count, api_call_count,
             input_tokens, output_tokens, cache_read_tokens,
             estimated_cost_usd, title
      FROM sessions ORDER BY started_at DESC
    """):
        w.writerow([*r[:6], r[6] or 0, r[7] or 0, r[8] or 0,
                    f"{r[9] or 0:.4f}", (r[10] or "")[:60]])
print(path)
```

## Caveats / interpretation

- **`actual_cost_usd` is almost always 0.** Providers seldom return billed-cost in API responses, so
  Hermes can only show `estimated_cost_usd` from its built-in pricing tables. For Volcano Coding Plan
  this estimate is **especially misleading** — Coding Plan is a flat-rate subscription billed by
  request count against quota, not by token. The dollar figure is just "what this would have cost on
  the regular Ark API."
- **`cache_read_tokens` is often >> `input_tokens`.** This is normal — prompt caching counts each
  cache-hit token as a "read." Don't sum it into total input.
- **`api_call_count` is the only number that maps to Coding Plan quota consumption.** If the user
  wants "am I close to my quota," `api_call_count` over the billing period is the answer.
- **The DB only contains sessions that ran on THIS machine through THIS Hermes install.** It does
  not capture usage from other clients, other accounts, or the Volcano TUI. For account-wide truth,
  the user still has to log into the Volcano console.
- **`billing_provider='custom'` is ambiguous** — Volcano Coding Plan, OpenRouter, and any other
  OpenAI-compatible endpoint all show as `custom`. Disambiguate via `billing_base_url` if needed.
