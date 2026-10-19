#!/usr/bin/env python3
"""Call the NodeControl licence admin API.

The token comes from the environment. This script does not open the
database. On the VPS the API listens on 127.0.0.1:5000. From anywhere
else set API_BASE=https://api.nodecontrol.io.

    export ADMIN_TOKEN='…'
    python3 admin_cli.py list
    python3 admin_cli.py list --status active
    python3 admin_cli.py revoke --code NC-ABCD-2345
    python3 admin_cli.py revoke --email person@example.com
    python3 admin_cli.py stats --since 2026-10-12 --until 2026-10-19
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

PLACEHOLDER = "change-me-in-production"


def _token():
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token or token == PLACEHOLDER:
        print(
            "ADMIN_TOKEN is unset or still the placeholder. Admin API is disabled.",
            file=sys.stderr,
        )
        sys.exit(2)
    return token


def _base():
    return os.environ.get("API_BASE", "http://127.0.0.1:5000").rstrip("/")


def api(method, path):
    req = urllib.request.Request(
        _base() + path,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw or exc.reason}
        return exc.code, payload


def _die(status, payload):
    message = payload.get("error") if isinstance(payload, dict) else payload
    print(f"API {status}: {message}", file=sys.stderr)
    sys.exit(1)


def cmd_list(args):
    query = []
    if args.status:
        query.append("status=" + urllib.request.quote(args.status))
    if args.search:
        query.append("search=" + urllib.request.quote(args.search))
    path = "/api/admin/licenses"
    if query:
        path += "?" + "&".join(query)
    status, payload = api("GET", path)
    if status != 200:
        _die(status, payload)
    rows = payload.get("licenses", [])
    if not rows:
        print("No licences.")
        return
    for row in rows:
        print(
            f"{row.get('id')}\t{row.get('status')}\t{row.get('email')}\t"
            f"{row.get('code')}\t{row.get('created_at')}"
        )
    print(f"{len(rows)} licence(s)")


def _matches(row, code, email):
    if code:
        return (row.get("code") or "").upper() == code.upper()
    if email:
        return (row.get("email") or "").lower() == email.lower()
    return False


def cmd_revoke(args):
    if bool(args.code) == bool(args.email):
        print("Pass exactly one of --code or --email.", file=sys.stderr)
        sys.exit(2)
    search = args.code or args.email
    status, payload = api("GET", "/api/admin/licenses?search=" + urllib.request.quote(search))
    if status != 200:
        _die(status, payload)
    rows = [row for row in payload.get("licenses", []) if _matches(row, args.code, args.email)]
    if not rows:
        print("No licence matched.", file=sys.stderr)
        sys.exit(1)
    pending = [row for row in rows if row.get("status") != "revoked"]
    targets = pending or rows
    for row in targets:
        code_status, body = api("DELETE", f"/api/admin/licenses/{row['id']}")
        if code_status != 200 or not body.get("success"):
            _die(code_status, body)
        print(f"Revoked {row.get('code')} ({row.get('email')}), id {row.get('id')}")


def cmd_stats(args):
    query = []
    if args.since:
        query.append("since=" + urllib.request.quote(args.since))
    if args.until:
        query.append("until=" + urllib.request.quote(args.until))
    path = "/api/admin/stats" + ("?" + "&".join(query) if query else "")
    status, payload = api("GET", path)
    if status != 200:
        _die(status, payload)
    print(
        f"All time: {payload.get('total_licenses')} licences, "
        f"{payload.get('active')} active, {payload.get('pending')} pending, "
        f"{payload.get('total_downloads')} redeems"
    )
    window = payload.get("window", {})
    print(f"Window {window.get('since')} to {window.get('until')} (UTC)")
    print("source\tmedium\trequested\tverified\tredeemed")
    for row in payload.get("by_source", []):
        print(
            f"{row['source']}\t{row['medium']}\t{row['requested']}\t"
            f"{row['verified']}\t{row['redeemed']}"
        )
    print("platform\tkind\tevents\tlicences")
    for row in payload.get("download_events", []):
        print(f"{row['platform']}\t{row['kind']}\t{row['events']}\t{row['licences']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="NodeControl licence admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List licences")
    list_cmd.add_argument("--status", help="pending, active, or revoked")
    list_cmd.add_argument("--search", help="email, name, company, or code")
    list_cmd.set_defaults(func=cmd_list)

    revoke_cmd = sub.add_parser("revoke", help="Revoke by code or email")
    revoke_cmd.add_argument("--code", help="NC-XXXX-XXXX")
    revoke_cmd.add_argument("--email", help="exact email address")
    revoke_cmd.set_defaults(func=cmd_revoke)

    stats_cmd = sub.add_parser("stats", help="Registrations by source, and download events")
    stats_cmd.add_argument("--since", help="UTC date, inclusive, e.g. 2026-10-12")
    stats_cmd.add_argument("--until", help="UTC date, exclusive, e.g. 2026-10-19")
    stats_cmd.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
