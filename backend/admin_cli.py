#!/usr/bin/env python3
"""Call the NodeControl licence admin API.

The token comes from the environment. List, revoke, flags, and Pro key
commands call the API. They do not open the database. On the Spark the
API listens on 127.0.0.1:5000. From anywhere else set
API_BASE=https://api.nodecontrol.io.

`maintenance --local` is the exception. It opens the database in this
process, rolls up old telemetry, and does not issue a licence key.
Nothing in this file runs unless you pass a subcommand.

    export ADMIN_TOKEN='…'
    python3 admin_cli.py list
    python3 admin_cli.py list --status active
    python3 admin_cli.py revoke --code NC-ABCD-2345
    python3 admin_cli.py revoke --email person@example.com
    python3 admin_cli.py stats --since 2026-10-12 --until 2026-10-19
    python3 admin_cli.py flags get
    python3 admin_cli.py flags set free_downloads_paused false
    python3 admin_cli.py pro-key issue --email person@example.com
    python3 admin_cli.py pro-key revoke --id 12
    python3 admin_cli.py reset-device --licence NC-ABCD-2345
    python3 admin_cli.py pro-resync --subscription sub_123
    python3 admin_cli.py maintenance --local
    python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_downloaded --below-version 0.9.41 --include-unknown-version --dry-run
    python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_downloaded --below-version 0.9.41 --include-unknown-version --confirm
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


def api(method, path, payload=None, timeout=30):
    data = None
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        _base() + path,
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def _print_json(status, payload):
    if status < 200 or status >= 300:
        _die(status, payload)
    print(json.dumps(payload, indent=2))


def cmd_flags_get(_args):
    _print_json(*api("GET", "/api/admin/flags"))


def cmd_flags_set(args):
    if args.key in ("free_downloads_paused", "maintenance"):
        value = args.value.strip().lower() in ("1", "true", "yes", "on")
    else:
        value = args.value
    _print_json(*api("PUT", "/api/admin/flags", {args.key: value}))


def cmd_pro_issue(args):
    _print_json(*api("POST", "/api/admin/pro-keys", {"email": args.email}))


def cmd_pro_revoke(args):
    _print_json(*api("POST", f"/api/admin/pro-keys/{int(args.id)}/revoke"))


def cmd_reset_device(args):
    quoted = urllib.request.quote(args.licence, safe="")
    _print_json(*api("POST", "/api/admin/devices/" + quoted + "/reset"))


def cmd_resync(args):
    _print_json(*api("POST", "/api/admin/pro/resync", {"subscription_id": args.subscription}))


def cmd_maintenance(_args):
    """Roll up old telemetry in this process. Does not issue a licence key."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import app  # loads ~/node-control-website/.env and migrates
    import licence_v1
    print(json.dumps(licence_v1.run_maintenance()))


def cmd_notify(args):
    """Send one notice template. Prints counts only."""
    if args.dry_run and args.confirm:
        print("Pass either --dry-run or --confirm.", file=sys.stderr)
        sys.exit(2)
    if not args.dry_run and not args.confirm:
        print("A real send needs --confirm. Use --dry-run to count only.", file=sys.stderr)
        sys.exit(2)
    payload = {
        "template": args.template,
        "audience": args.audience,
        "dry_run": bool(args.dry_run),
        "include_unknown_version": bool(args.include_unknown_version),
    }
    if args.below_version:
        payload["below_version"] = args.below_version
    status, body = api("POST", "/api/admin/notify", payload, timeout=600)
    if status != 200 or not isinstance(body, dict):
        print(f"API {status}: request failed", file=sys.stderr)
        sys.exit(1)
    for key in ("matched", "already_sent", "opted_out", "sent", "failed"):
        value = body.get(key)
        if not isinstance(value, int):
            print("API response was not counts.", file=sys.stderr)
            sys.exit(1)
        print(f"{key} {value}")


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

    flags = sub.add_parser("flags", help="Read or set the kill-switch flags")
    flags_sub = flags.add_subparsers(dest="flags_command", required=True)
    flags_get = flags_sub.add_parser("get", help="Show the current flags")
    flags_get.set_defaults(func=cmd_flags_get)
    flags_set = flags_sub.add_parser("set", help="Set one flag. Takes effect within 10 seconds")
    flags_set.add_argument("key")
    flags_set.add_argument("value")
    flags_set.set_defaults(func=cmd_flags_set)

    pro_key = sub.add_parser("pro-key", help="Issue or revoke a manual Professional key")
    pro_sub = pro_key.add_subparsers(dest="pro_command", required=True)
    issue = pro_sub.add_parser("issue", help="Create a key for a hand-added beta address")
    issue.add_argument("--email", required=True)
    issue.set_defaults(func=cmd_pro_issue)
    pro_revoke = pro_sub.add_parser("revoke", help="Revoke one Professional key by id")
    pro_revoke.add_argument("--id", required=True, type=int)
    pro_revoke.set_defaults(func=cmd_pro_revoke)

    reset = sub.add_parser("reset-device", help="Clear the active device and the move counter")
    reset.add_argument("--licence", required=True, help="NC- or NCP- key")
    reset.set_defaults(func=cmd_reset_device)

    resync = sub.add_parser("pro-resync", help="Re-read one Stripe subscription")
    resync.add_argument("--subscription", required=True)
    resync.set_defaults(func=cmd_resync)

    maintenance = sub.add_parser(
        "maintenance",
        help="Roll up telemetry older than the retention window. Does not issue keys",
    )
    maintenance.add_argument(
        "--local",
        action="store_true",
        required=True,
        help="Open the database in this process",
    )
    maintenance.set_defaults(func=cmd_maintenance)

    notify = sub.add_parser("notify", help="Send a service notice. Prints counts only")
    notify.add_argument("--template", required=True)
    notify.add_argument(
        "--audience",
        required=True,
        choices=("free_downloaded", "free_all", "pro_active", "all"),
    )
    notify.add_argument("--below-version", default="", help="Only licences whose newest known version is below this")
    notify.add_argument(
        "--include-unknown-version",
        action="store_true",
        help="With --below-version, also include licences with no known version",
    )
    notify.add_argument("--dry-run", action="store_true", help="Count only. Nothing is sent")
    notify.add_argument("--confirm", action="store_true", help="Send. Required for a real run")
    notify.set_defaults(func=cmd_notify)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
