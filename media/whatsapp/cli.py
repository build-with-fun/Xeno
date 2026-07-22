#!/usr/bin/env python3
"""CLI admin client for the WhatsApp bot.

A convenient command-line interface to the admin API. No need for curl
or Postman — just run:

    python cli.py health
    python cli.py pending
    python cli.py approve 12345 --reply "Yes, I'll be there"
    python cli.py reject 12345 --reason "Spam"
    python cli.py metrics
    python cli.py status
    python cli.py stop

Configuration is read from .env (ADMIN_HOST, ADMIN_PORT, ADMIN_API_TOKEN).
Override with --host, --port, --token flags.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)


def get_config(args) -> tuple[str, str]:
    """Return (base_url, auth_header)."""
    host = args.host or os.getenv("ADMIN_HOST", "127.0.0.1")
    port = args.port or os.getenv("ADMIN_PORT", "5000")
    token = args.token or os.getenv("ADMIN_API_TOKEN", "")
    base = f"http://{host}:{port}"
    auth = {"Authorization": f"Bearer {token}"} if token and token != "change-this-to-a-long-random-string" else {}
    return base, auth


def api_get(base: str, auth: dict, path: str) -> dict:
    r = requests.get(f"{base}{path}", headers=auth, timeout=10)
    r.raise_for_status()
    return r.json()


def api_post(base: str, auth: dict, path: str, data: dict) -> dict:
    r = requests.post(f"{base}{path}", json=data, headers=auth, timeout=10)
    r.raise_for_status()
    return r.json()


def api_put(base: str, auth: dict, path: str, data: dict) -> dict:
    r = requests.put(f"{base}{path}", json=data, headers=auth, timeout=10)
    r.raise_for_status()
    return r.json()


def print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def print_table(items: list, columns: list[str]) -> None:
    """Print a list of dicts as a simple table."""
    if not items:
        print("  (none)")
        return
    # Calculate column widths
    widths = {c: len(c) for c in columns}
    for item in items:
        for c in columns:
            widths[c] = max(widths[c], len(str(item.get(c, "")[:40])))
    # Header
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("-" * len(header))
    # Rows
    for item in items:
        row = "  ".join(str(item.get(c, ""))[:40].ljust(widths[c]) for c in columns)
        print(row)


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_health(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, "/api/health")
    print(f"Status: {data['status'].upper()}")
    print(f"Uptime: {data['uptime_seconds']:.0f}s")
    print()
    print("Checks:")
    for check in data.get("checks", []):
        status = "OK" if check["healthy"] else "FAIL"
        print(f"  [{status}] {check['name']}: {check['message']} ({check['duration_ms']:.0f}ms)")


def cmd_pending(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, "/api/pending")
    items = data.get("items", [])
    print(f"Pending approvals: {data.get('count', len(items))}")
    print()
    if items:
        print_table(items, ["msg_id", "contact", "timestamp", "risk_level"])
        print()
        for item in items:
            decision = item.get("decision", {})
            print(f"  #{item['msg_id']} from {item['contact']}:")
            print(f"    Risk: {decision.get('risk_level', '?')} — {decision.get('reason', '')[:80]}")
            msgs = item.get("messages", [])
            for m in msgs[:3]:
                print(f"    [{m.get('label', '?')}] {m.get('content', '')[:60]}")
            if len(msgs) > 3:
                print(f"    ... and {len(msgs) - 3} more")
            print()


def cmd_queue(args) -> None:
    base, auth = get_config(args)
    status = args.status or None
    path = f"/api/queue?status={status}" if status else "/api/queue"
    data = api_get(base, auth, path)
    items = data.get("items", [])
    print(f"Queue items: {data.get('count', len(items))}")
    print()
    if items:
        print_table(items, ["msg_id", "contact", "timestamp", "status"])


def cmd_approve(args) -> None:
    base, auth = get_config(args)
    data = {"msg_id": args.msg_id}
    if args.reply:
        data["custom_reply"] = args.reply
    if args.context:
        data["custom_context"] = args.context
    result = api_post(base, auth, "/api/approve", data)
    print(f"Approved #{args.msg_id}")
    if args.reply:
        print(f"  Custom reply: {args.reply[:80]}")


def cmd_reject(args) -> None:
    base, auth = get_config(args)
    data = {"msg_id": args.msg_id, "reason": args.reason or ""}
    result = api_post(base, auth, "/api/reject", data)
    print(f"Rejected #{args.msg_id}")
    if args.reason:
        print(f"  Reason: {args.reason}")


def cmd_metrics(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, "/api/metrics")
    print(f"Uptime: {data.get('uptime_seconds', 0):.0f}s")
    print()
    print("Counters:")
    counters = data.get("counters", {})
    for k in sorted(counters.keys()):
        print(f"  {k}: {counters[k]}")
    print()
    print("Gauges:")
    gauges = data.get("gauges", {})
    for k in sorted(gauges.keys()):
        print(f"  {k}: {gauges[k]}")
    if data.get("histograms"):
        print()
        print("Histograms:")
        for k, h in data["histograms"].items():
            print(f"  {k}:")
            for stat in ("count", "avg", "p50", "p95", "p99", "max"):
                if stat in h:
                    print(f"    {stat}: {h[stat]}")


def cmd_analytics(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, f"/api/analytics?days={args.days}")
    files = data.get("files", [])
    print(f"Analytics for last {args.days} days:")
    print()
    for f in files:
        print(f"  {f.get('date', '?')}:")
        print(f"    Messages received: {f.get('total_messages_received', 0)}")
        print(f"    Replies sent:      {f.get('total_replies_sent', 0)}")
        print(f"    Approvals needed:  {f.get('approvals_needed', 0)}")
        print(f"    Approvals approved:{f.get('approvals_approved', 0)}")
        print(f"    Send failures:     {f.get('send_failures', 0)}")
        print(f"    Keyword alerts:    {f.get('keyword_alerts', 0)}")
        print(f"    Active contacts:   {len(f.get('contacts_active', []))}")
        ai = f.get("ai_provider_usage", {})
        if ai:
            print(f"    AI usage:          {ai}")
        print()


def cmd_keywords(args) -> None:
    base, auth = get_config(args)
    if args.set:
        # Read keywords from --set (comma-separated) or file
        if args.set == "-":
            kw_text = sys.stdin.read()
            keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
        elif os.path.isfile(args.set):
            with open(args.set) as f:
                keywords = [k.strip() for k in f.read().split(",") if k.strip()]
        else:
            keywords = [k.strip() for k in args.set.split(",") if k.strip()]
        result = api_put(base, auth, "/api/keywords", {"keywords": keywords})
        print(f"Updated keywords: {result.get('count', len(keywords))} keywords")
    else:
        data = api_get(base, auth, "/api/keywords")
        keywords = data.get("keywords", [])
        print(f"Alert keywords ({len(keywords)}):")
        for kw in keywords:
            print(f"  - {kw}")


def cmd_alerts(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, f"/api/alerts?limit={args.limit}")
    alerts = data.get("alerts", [])
    print(f"Recent alerts ({len(alerts)}):")
    print()
    for a in alerts:
        print(f"  [{a.get('timestamp', '')[:19]}] {a.get('contact', '?')}: "
              f"keyword='{a.get('keyword', '?')}'")
        print(f"    Snippet: {a.get('snippet', '')[:80]}")
        print()


def cmd_retry(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, "/api/retry")
    print(f"Retry queue: {data.get('count', 0)} items")
    print()
    items = data.get("items", [])
    for item in items:
        print(f"  {item.get('contact', '?')}: attempt {item.get('attempt', 0)}, "
              f"next at {item.get('next_retry_at', '')[:19]}")
        print(f"    Reply: {item.get('reply', '')[:60]}")
        print()


def cmd_rate_limit(args) -> None:
    base, auth = get_config(args)
    data = api_get(base, auth, f"/api/rate-limit/{args.contact}")
    print(f"Rate-limit status for {args.contact}:")
    print(f"  Replies last hour: {data.get('replies_last_hour', 0)}")
    print(f"  Max per hour:      {data.get('max_per_hour', 0)}")
    print(f"  Blocked:           {data.get('blocked', False)}")
    if data.get("blocked"):
        print(f"  Blocked until:     {data.get('blocked_until', 0)}")


def cmd_stop(args) -> None:
    base, auth = get_config(args)
    result = api_post(base, auth, "/api/bot/stop", {})
    print("Stop signal sent. Bot will shut down gracefully.")


def cmd_status(args) -> None:
    """Summary of everything."""
    base, auth = get_config(args)
    print("=== WhatsApp Bot Status ===")
    print()
    try:
        health_data = api_get(base, auth, "/api/health")
        print(f"Health: {health_data['status'].upper()} "
              f"(uptime: {health_data['uptime_seconds']:.0f}s)")
        for check in health_data.get("checks", []):
            icon = "OK" if check["healthy"] else "!!"
            print(f"  [{icon}] {check['name']}: {check['message']}")
    except Exception as e:
        print(f"Health: UNREACHABLE ({e})")
        return
    print()
    try:
        pending = api_get(base, auth, "/api/pending")
        print(f"Pending approvals: {pending.get('count', 0)}")
    except Exception:
        pass
    try:
        retry = api_get(base, auth, "/api/retry")
        print(f"Retry queue:       {retry.get('count', 0)}")
    except Exception:
        pass
    try:
        metrics = api_get(base, auth, "/api/metrics")
        counters = metrics.get("counters", {})
        sent = counters.get("send_success{method=wpp}", 0) + \
               counters.get("send_success{method=clipboard}", 0) + \
               counters.get("send_success{method=keyboard}", 0)
        failed = counters.get("send_failures", 0)
        print(f"Messages sent:     {sent}")
        print(f"Send failures:     {failed}")
    except Exception:
        pass


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="WhatsApp Bot v2 — CLI admin client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s health                          # check bot health
  %(prog)s pending                         # list pending approvals
  %(prog)s approve 12345                   # approve with AI-generated reply
  %(prog)s approve 12345 --reply "Yes!"    # approve with custom reply
  %(prog)s reject 12345 --reason "spam"    # reject
  %(prog)s metrics                         # show counters & histograms
  %(prog)s status                          # one-shot summary
  %(prog)s stop                            # graceful shutdown
""",
    )
    p.add_argument("--host", help="Admin API host (default: from .env)")
    p.add_argument("--port", help="Admin API port (default: from .env)")
    p.add_argument("--token", help="Admin API token (default: from .env)")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Show health check results")
    sub.add_parser("pending", help="List pending approvals")
    sub.add_parser("queue", help="List all queue items").add_argument(
        "--status", choices=["pending", "approved", "rejected", "processing", "sent", "failed"]
    )
    sub.add_parser("metrics", help="Show metrics (counters, gauges, histograms)")
    sub.add_parser("retry", help="Show retry queue")
    sub.add_parser("status", help="One-shot summary of everything")
    sub.add_parser("stop", help="Send graceful stop signal")

    a = sub.add_parser("approve", help="Approve a pending message")
    a.add_argument("msg_id", type=int)
    a.add_argument("--reply", help="Custom reply text (default: AI-generated)")
    a.add_argument("--context", help="Custom context for AI reply")

    r = sub.add_parser("reject", help="Reject a pending message")
    r.add_argument("msg_id", type=int)
    r.add_argument("--reason", help="Rejection reason")

    an = sub.add_parser("analytics", help="Show analytics")
    an.add_argument("--days", type=int, default=7, help="Number of days (default: 7)")

    k = sub.add_parser("keywords", help="Get or set alert keywords")
    k.add_argument("--set", metavar="VALUE",
                   help="Set keywords (comma-separated, '-' for stdin, or filename)")

    al = sub.add_parser("alerts", help="Show recent keyword alerts")
    al.add_argument("--limit", type=int, default=20)

    rl = sub.add_parser("rate-limit", help="Show rate-limit status for a contact")
    rl.add_argument("contact")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "health": cmd_health,
        "pending": cmd_pending,
        "queue": cmd_queue,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "metrics": cmd_metrics,
        "analytics": cmd_analytics,
        "keywords": cmd_keywords,
        "alerts": cmd_alerts,
        "retry": cmd_retry,
        "rate-limit": cmd_rate_limit,
        "stop": cmd_stop,
        "status": cmd_status,
    }
    fn = commands.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)
    try:
        fn(args)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to admin API. Is the bot running?")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
