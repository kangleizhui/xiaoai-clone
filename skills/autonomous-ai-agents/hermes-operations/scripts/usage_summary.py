#!/usr/bin/env python3
"""
hermes-state-db-analytics: usage_summary.py

Prints a complete Hermes Agent usage summary from ~/.hermes/state.db.
Sections: lifetime totals, per-provider, per-model, per-day, today, last 7 days.

Optional: --csv DIR  → also exports daily.csv and sessions.csv into DIR.
Optional: --db PATH  → use a non-default state.db path.
Optional: --days N   → window for the "recent" section (default 7).

No third-party deps. Python 3.8+.
"""
import sqlite3
import os
import argparse
import csv
import datetime
import sys


def open_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        sys.exit(f"state.db not found at {path}")
    return sqlite3.connect(path)


def fmt_int(n):
    return f"{n or 0:,}"


def fmt_usd(n):
    return f"${n or 0:.4f}"


def section(title: str):
    print()
    print("=" * len(title))
    print(title)
    print("=" * len(title))


def lifetime(cur):
    section("Lifetime totals")
    r = cur.execute(
        """
        SELECT COUNT(*),
               SUM(input_tokens), SUM(output_tokens),
               SUM(cache_read_tokens), SUM(cache_write_tokens),
               SUM(reasoning_tokens), SUM(api_call_count),
               SUM(estimated_cost_usd), SUM(actual_cost_usd)
        FROM sessions
        """
    ).fetchone()
    labels = [
        "sessions", "input tokens", "output tokens",
        "cache read", "cache write", "reasoning tokens",
        "api calls", "estimated $", "actual $",
    ]
    for label, value in zip(labels, r):
        if "$" in label:
            print(f"  {label:18s} {fmt_usd(value)}")
        else:
            print(f"  {label:18s} {fmt_int(value)}")


def by_provider(cur):
    section("By billing_provider")
    print(f"  {'provider':15s} {'sess':>5s} {'input':>14s} {'output':>12s} {'est $':>10s}")
    for r in cur.execute(
        """
        SELECT billing_provider, COUNT(*),
               SUM(input_tokens), SUM(output_tokens), SUM(estimated_cost_usd)
        FROM sessions
        GROUP BY billing_provider
        ORDER BY SUM(input_tokens) DESC
        """
    ).fetchall():
        print(
            f"  {(r[0] or '(unknown)')[:15]:15s} {r[1]:>5d} "
            f"{fmt_int(r[2]):>14s} {fmt_int(r[3]):>12s} {fmt_usd(r[4]):>10s}"
        )


def by_model(cur, limit=15):
    section(f"By model (top {limit})")
    print(
        f"  {'model':35s} {'sess':>5s} {'input':>14s} {'output':>12s} {'calls':>7s}"
    )
    for r in cur.execute(
        """
        SELECT model, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(api_call_count)
        FROM sessions
        GROUP BY model
        ORDER BY SUM(input_tokens) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall():
        print(
            f"  {(r[0] or '(none)')[:35]:35s} {r[1]:>5d} "
            f"{fmt_int(r[2]):>14s} {fmt_int(r[3]):>12s} {fmt_int(r[4]):>7s}"
        )


def daily(cur, days=30):
    section(f"By day (last {days})")
    print(
        f"  {'date':12s} {'sess':>5s} {'calls':>7s} {'input':>14s} {'output':>12s} {'cache':>14s} {'est $':>10s}"
    )
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
    rows = cur.execute(
        """
        SELECT date(started_at, 'unixepoch', 'localtime') AS day,
               COUNT(*), SUM(api_call_count),
               SUM(input_tokens), SUM(output_tokens),
               SUM(cache_read_tokens), SUM(estimated_cost_usd)
        FROM sessions
        WHERE started_at >= ?
        GROUP BY day ORDER BY day DESC
        """,
        (cutoff,),
    ).fetchall()
    for r in rows:
        print(
            f"  {r[0]:12s} {r[1]:>5d} {fmt_int(r[2]):>7s} "
            f"{fmt_int(r[3]):>14s} {fmt_int(r[4]):>12s} "
            f"{fmt_int(r[5]):>14s} {fmt_usd(r[6]):>10s}"
        )
    return rows


def window(cur, label, days):
    section(label)
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
    r = cur.execute(
        """
        SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens),
               SUM(api_call_count), SUM(estimated_cost_usd)
        FROM sessions WHERE started_at >= ?
        """,
        (cutoff,),
    ).fetchone()
    print(
        f"  sessions={r[0]}  input={fmt_int(r[1])}  output={fmt_int(r[2])}  "
        f"api_calls={fmt_int(r[3])}  est={fmt_usd(r[4])}"
    )


def today(cur):
    section("Today (local)")
    start = (
        datetime.datetime.now()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )
    r = cur.execute(
        """
        SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens),
               SUM(api_call_count), SUM(estimated_cost_usd)
        FROM sessions WHERE started_at >= ?
        """,
        (start,),
    ).fetchone()
    print(
        f"  sessions={r[0]}  input={fmt_int(r[1])}  output={fmt_int(r[2])}  "
        f"api_calls={fmt_int(r[3])}  est={fmt_usd(r[4])}"
    )


def export_csv(cur, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # daily
    daily_path = os.path.join(out_dir, f"hermes_daily_{ts}.csv")
    with open(daily_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "date", "sessions", "api_calls", "input_tokens",
                "output_tokens", "cache_read", "estimated_usd",
            ]
        )
        for r in cur.execute(
            """
            SELECT date(started_at, 'unixepoch', 'localtime') AS day,
                   COUNT(*), SUM(api_call_count),
                   SUM(input_tokens), SUM(output_tokens),
                   SUM(cache_read_tokens), SUM(estimated_cost_usd)
            FROM sessions
            GROUP BY day ORDER BY day DESC
            """
        ).fetchall():
            w.writerow(
                [r[0], r[1], r[2] or 0, r[3] or 0, r[4] or 0,
                 r[5] or 0, f"{r[6] or 0:.4f}"]
            )
    # sessions
    sess_path = os.path.join(out_dir, f"hermes_sessions_{ts}.csv")
    with open(sess_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "session_id", "model", "source", "start",
                "messages", "api_calls", "input", "output",
                "cache_read", "estimated_usd", "title",
            ]
        )
        for r in cur.execute(
            """
            SELECT id, model, source,
                   datetime(started_at, 'unixepoch', 'localtime'),
                   message_count, api_call_count,
                   input_tokens, output_tokens, cache_read_tokens,
                   estimated_cost_usd, title
            FROM sessions
            ORDER BY started_at DESC
            """
        ).fetchall():
            w.writerow(
                [
                    r[0], r[1], r[2], r[3], r[4], r[5],
                    r[6] or 0, r[7] or 0, r[8] or 0,
                    f"{r[9] or 0:.4f}", (r[10] or "")[:120],
                ]
            )
    section("CSV exports")
    print(f"  daily:    {daily_path}")
    print(f"  sessions: {sess_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db",
        default=os.path.expanduser("~/.hermes/state.db"),
        help="Path to state.db (default: ~/.hermes/state.db)",
    )
    ap.add_argument("--days", type=int, default=7, help="Recent window size in days")
    ap.add_argument("--csv", metavar="DIR", help="Also export daily.csv + sessions.csv into DIR")
    args = ap.parse_args()

    con = open_db(args.db)
    cur = con.cursor()

    lifetime(cur)
    by_provider(cur)
    by_model(cur)
    daily(cur, days=max(args.days, 30))
    today(cur)
    window(cur, f"Last {args.days} day(s)", args.days)

    if args.csv:
        export_csv(cur, args.csv)


if __name__ == "__main__":
    main()
