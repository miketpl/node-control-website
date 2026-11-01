"""14-day Pro trial for Free licences. App 0.9.46.

The signed lease is the authority. Plain JSON fields are for display and
older clients. A missing signing key leaves lease null so older tests and
a server that is not configured yet keep working.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

TRIAL_VERSION = (0, 9, 46)
TRIAL_DAYS = 14
LEASE_FORMAT = "ed25519-v1"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PREVIEW_ONLY = ["monitor", "discover", "ipam", "firewall_analyser", "meraki_configurator"]
TRIAL_ENTITLEMENTS = ["engineer_tasks_all", "reports_all", "ai_byok", "devices_unlimited"]


def _v1():
    import licence_v1
    return licence_v1


def _db():
    return _v1()._api().get_db()


def trial_enabled():
    return bool(_v1().get_flags().get("free_trial_enabled"))


def _app_ok(version):
    parsed = _v1().parse_version(version or "")
    return bool(parsed and parsed >= TRIAL_VERSION)


def read_machine_header():
    """Return a 64-hex hash, 'unavailable', or None when the header is unusable."""
    from flask import request
    raw = (request.headers.get("X-NC-Machine-Hash") or "").strip().lower()
    if not raw:
        return None
    if raw == "unavailable":
        return "unavailable"
    if HASH_RE.match(raw):
        return raw
    return None


def _secret():
    return (os.environ.get("MACHINE_HASH_KEY") or "").encode("utf-8")


def email_hash(email):
    key = _secret()
    if not key:
        return ""
    return hmac.new(key, ("email:" + (email or "").strip().lower()).encode(), hashlib.sha256).hexdigest()


def machine_hmac(presented):
    key = _secret()
    if not key or not presented or presented == "unavailable":
        return ""
    return hmac.new(key, presented.encode("utf-8"), hashlib.sha256).hexdigest()


def licence_ref(kind, ref):
    key = _secret() or b"unset"
    digest = hmac.new(key, f"ref:{kind}:{int(ref)}".encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def _count(event):
    v1 = _v1()
    day = v1.utcnow().strftime("%Y-%m-%d")
    db = _db()
    try:
        db.execute(
            """
            INSERT INTO funnel_daily (day, event, count) VALUES (?, ?, 1)
            ON CONFLICT(day, event) DO UPDATE SET count = count + 1
            """,
            (day, event),
        )
        db.commit()
    finally:
        db.close()


def _row_for_email(db, digest):
    if not digest:
        return None
    return db.execute(
        "SELECT * FROM free_trials WHERE email_hash = ?", (digest,)
    ).fetchone()


def _row_for_machine(db, digest):
    if not digest:
        return None
    return db.execute(
        "SELECT * FROM free_trials WHERE machine_hash = ?", (digest,)
    ).fetchone()


def _days_left(expires_at, now):
    moment = _v1().parse_iso(expires_at)
    if not moment:
        return 0
    seconds = (moment - now).total_seconds()
    if seconds <= 0:
        return 0
    return int((seconds + 86399) // 86400)


def _state_for(record, presented, version, now):
    """Plain trial view. Does not insert a row."""
    v1 = _v1()
    if record["tier"] == "pro":
        return {
            "trial_state": "not_applicable",
            "reason": None,
            "row": None,
            "active": False,
            "eligible": False,
        }
    if record.get("status") == "revoked":
        return {
            "trial_state": "ineligible",
            "reason": None,
            "row": None,
            "active": False,
            "eligible": False,
            "no_lease": True,
        }
    if not _app_ok(version):
        return {
            "trial_state": "ineligible",
            "reason": "old_app",
            "row": None,
            "active": False,
            "eligible": False,
        }
    if not trial_enabled():
        return {
            "trial_state": "ineligible",
            "reason": "disabled",
            "row": None,
            "active": False,
            "eligible": False,
        }
    digest = email_hash(record.get("email") or "")
    machine = "" if presented in (None, "unavailable") else machine_hmac(presented)
    db = _db()
    try:
        by_email = _row_for_email(db, digest)
        by_machine = _row_for_machine(db, machine) if machine else None
    finally:
        db.close()
    if by_email:
        expires = v1.parse_iso(by_email["expires_at"])
        active = bool(expires and expires > now)
        same_machine = (not machine) or by_email["machine_hash"] == machine
        if not same_machine:
            return {
                "trial_state": "ineligible",
                "reason": "email_used",
                "row": by_email,
                "active": False,
                "eligible": False,
            }
        if active:
            return {
                "trial_state": "active",
                "reason": None,
                "row": by_email,
                "active": True,
                "eligible": True,
            }
        return {
            "trial_state": "ended",
            "reason": None,
            "row": by_email,
            "active": False,
            "eligible": False,
        }
    if by_machine:
        return {
            "trial_state": "ineligible",
            "reason": "machine_used",
            "row": by_machine,
            "active": False,
            "eligible": False,
        }
    return {
        "trial_state": "available",
        "reason": None,
        "row": None,
        "active": False,
        "eligible": True,
    }


def _insert_trial(record, install_id, presented, how):
    v1 = _v1()
    now = v1.utcnow()
    started = v1.iso(now)
    expires = v1.iso(now + timedelta(days=TRIAL_DAYS))
    machine = "" if presented == "unavailable" else machine_hmac(presented)
    db = _db()
    try:
        db.execute(
            """
            INSERT INTO free_trials (
                email_hash, machine_hash, licence_kind, licence_ref, install_id,
                started_at, expires_at, started_how, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email_hash(record.get("email") or ""),
                machine,
                record["kind"],
                int(record["id"]),
                install_id,
                started,
                expires,
                how,
                started,
            ),
        )
        db.commit()
    finally:
        db.close()
    _count("trial_started_auto" if how == "auto" else "trial_started_button")
    return started, expires


def _note_ended(row):
    if not row or int(row["ended_reported"] or 0):
        return
    db = _db()
    try:
        db.execute(
            "UPDATE free_trials SET ended_reported = 1 WHERE id = ? AND ended_reported = 0",
            (row["id"],),
        )
        changed = db.execute("SELECT changes() AS c").fetchone()["c"]
        db.commit()
    finally:
        db.close()
    if changed:
        _count("trial_ended")


def _plain_trial(view, now):
    row = view["row"]
    if view["trial_state"] == "not_applicable":
        return None
    started = row["started_at"] if row else None
    expires = row["expires_at"] if row else None
    grace = None
    if row and view["active"]:
        end = _v1().parse_iso(expires)
        cap = now + timedelta(days=7)
        grace = _v1().iso(end if end and end < cap else cap)
    return {
        "active": bool(view["active"]),
        "eligible": bool(view["eligible"]),
        "reason": view["reason"],
        "started_at": _v1()._as_z(started) if started else None,
        "expires_at": _v1()._as_z(expires) if expires else None,
        "days_left": _days_left(expires, now) if expires else 0,
        "grace_until": grace,
    }


def _sign(payload):
    seed_b64 = (os.environ.get("LEASE_SIGNING_KEY") or "").strip()
    kid = (os.environ.get("LEASE_SIGNING_KEY_ID") or "").strip()
    if not seed_b64 or not kid:
        return None, None
    try:
        seed = base64.b64decode(seed_b64)
        key = Ed25519PrivateKey.from_private_bytes(seed)
    except Exception:
        return None, None
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = key.sign(body)

    def pack(raw):
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return LEASE_FORMAT, pack(body) + "." + pack(sig)


def current_and_next_kids():
    kids = []
    if (os.environ.get("LEASE_SIGNING_KEY_ID") or "").strip():
        kids.append(os.environ["LEASE_SIGNING_KEY_ID"].strip())
    nxt = (os.environ.get("LEASE_SIGNING_KEY_ID_NEXT") or "").strip()
    if nxt:
        kids.append(nxt)
    return kids


def apply_to_payload(payload, record, install_id, app_version, auto_start=False):
    v1 = _v1()
    now = v1.utcnow()
    presented = read_machine_header()
    if record.get("status") == "revoked" or (
        record["tier"] == "pro" and _row_blocks_lease(record)
    ):
        payload["lease"] = None
        payload["lease_format"] = None
        return payload
    if (
        auto_start
        and record["tier"] == "free"
        and _app_ok(app_version)
        and trial_enabled()
        and _secret()
    ):
        if presented == "unavailable" or (presented and HASH_RE.match(presented)):
            view = _state_for(record, presented, app_version, now)
            if view["trial_state"] == "available":
                _insert_trial(record, install_id, presented, "auto")
            elif view["reason"] in ("email_used", "machine_used"):
                _count("trial_refused_" + view["reason"])
    view = _state_for(record, presented, app_version, now)
    if view["trial_state"] == "ended":
        _note_ended(view["row"])
    payload["edition"] = "pro" if record["tier"] == "pro" else "free"
    payload["server_time"] = v1.iso(now)
    payload["trial"] = _plain_trial(view, now)
    if view["active"]:
        payload["entitlements"] = list(TRIAL_ENTITLEMENTS)
        payload["preview_only"] = list(PREVIEW_ONLY)
    elif record["tier"] == "pro":
        payload["entitlements"] = ["all"]
        payload["preview_only"] = []
    else:
        payload["entitlements"] = []
        payload["preview_only"] = list(PREVIEW_ONLY)
    if view.get("no_lease"):
        payload["lease"] = None
        payload["lease_format"] = None
        return payload
    issued = now
    grace_end = issued + timedelta(days=7)
    trial_end = None
    if view["row"]:
        trial_end = v1.parse_iso(view["row"]["expires_at"])
    if view["active"] and trial_end:
        lease_end = grace_end if grace_end < trial_end else trial_end
    else:
        lease_end = grace_end
    minimum = payload.get("update", {}).get("min_supported_version") or ""
    signed = {
        "v": 1,
        "kid": (os.environ.get("LEASE_SIGNING_KEY_ID") or "").strip(),
        "install_id": install_id,
        "machine_hash_echo": presented or "",
        "licence_ref": licence_ref(record["kind"], record["id"]),
        "edition": payload["edition"],
        "server_time": payload["server_time"],
        "trial": payload["trial"],
        "trial_state": view["trial_state"],
        "reason": view["reason"],
        "entitlements": payload["entitlements"],
        "preview_only": payload["preview_only"],
        "issued_at": v1.iso(issued),
        "lease_expires_at": v1.iso(lease_end),
        "min_supported_version": minimum or "",
    }
    lease_format, lease = _sign(signed)
    payload["lease_format"] = lease_format
    payload["lease"] = lease
    return payload


def _row_blocks_lease(record):
    """A test-mode Professional key is treated like a revoked key: no lease."""
    if record["tier"] != "pro":
        return False
    v1 = _v1()
    if v1.test_events_allowed():
        return False
    return v1._row_is_test(record)


def start_request():
    v1 = _v1()
    ctx, err = v1._guard("trial-start", needs_device=True)
    if err:
        return err
    record = ctx["record"]
    if record["kind"] != "free":
        return v1.error(403, "tier_mismatch", "This licence is for a different edition.")
    if not _app_ok(ctx["version"]):
        _count("trial_refused_old_app")
        return v1.error(
            409, "trial_unavailable", "This version of Node Control cannot start a trial.",
            details={"reason": "old_app"},
        )
    if not trial_enabled() or not _secret():
        _count("trial_refused_disabled")
        return v1.error(
            409, "trial_unavailable", "The Pro trial is not available.",
            details={"reason": "disabled"},
        )
    presented = read_machine_header()
    if presented is None:
        return v1.error(400, "bad_machine_hash", "X-NC-Machine-Hash is missing or not valid.")
    now = v1.utcnow()
    view = _state_for(record, presented, ctx["version"], now)
    if view["trial_state"] == "active":
        body = v1.licence_payload(record, ctx["install_id"], ctx["version"])
        return __import__("flask").jsonify({
            "active": True,
            "tier": record["tier"],
            "licence": body,
        })
    if view["reason"] in ("email_used", "machine_used"):
        _count("trial_refused_" + view["reason"])
        return v1.error(
            409, "trial_used", "This trial has already been used.",
            details={"reason": view["reason"]},
        )
    if view["trial_state"] == "ended":
        _count("trial_refused_email_used")
        return v1.error(
            409, "trial_used", "This trial has already been used.",
            details={"reason": "email_used"},
        )
    _insert_trial(record, ctx["install_id"], presented, "button")
    body = v1.licence_payload(record, ctx["install_id"], ctx["version"])
    return __import__("flask").jsonify({
        "active": True,
        "tier": record["tier"],
        "licence": body,
    })


def reset_trial(trial_id, confirm):
    """Delete one trial row. Dry run unless confirm is true. Prints counts only."""
    db = _db()
    try:
        row = db.execute("SELECT id FROM free_trials WHERE id = ?", (int(trial_id),)).fetchone()
        if not row:
            print("no trial with that id")
            return 1
        if not confirm:
            print(f"would delete trial {int(trial_id)}")
            return 0
        db.execute("DELETE FROM free_trials WHERE id = ?", (int(trial_id),))
        db.commit()
    finally:
        db.close()
    print(f"deleted trial {int(trial_id)}")
    return 0


def _template_opt_out(name):
    import notices
    path = notices._template_dir(name)
    if path is None:
        return True
    meta = path / "meta.json"
    if not meta.is_file():
        return True
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return bool(data.get("respect_opt_out", True))


def run_reminders(confirm):
    """Day 11 and day 14 trial reminders. Prints counts only."""
    import notices
    v1 = _v1()
    today = v1.utcnow().date()
    db = _db()
    try:
        rows = db.execute(
            """
            SELECT t.*, l.email FROM free_trials t
            JOIN licenses l ON l.id = t.licence_ref
            WHERE t.licence_kind = 'free'
            """
        ).fetchall()
    finally:
        db.close()
    due = []
    for row in rows:
        started = v1.parse_iso(row["started_at"])
        if not started:
            continue
        day = (today - started.date()).days + 1
        if day == 11:
            due.append((row, "trial-day11"))
        elif day == 14:
            due.append((row, "trial-day14"))
    matched = len(due)
    already = opted = sent = failed = 0
    for row, template in due:
        db = _db()
        try:
            if notices._already_sent(db, template, "free", row["licence_ref"]):
                already += 1
                continue
            if _template_opt_out(template) and notices._opted_out(db, "free", row["licence_ref"]):
                opted += 1
                continue
        finally:
            db.close()
        if not confirm:
            continue
        loaded = notices._load_template(template)
        url = notices._unsubscribe_url("free", row["licence_ref"])
        if not loaded or not url:
            failed += 1
            continue
        subject, text, html = notices._render(loaded, url)
        ok = v1._api()._send_mail(row["email"], subject, text, html, log_recipient=False)
        if not ok:
            failed += 1
            continue
        db = _db()
        try:
            notices._mark_sent(db, template, "free", row["licence_ref"])
        finally:
            db.close()
        sent += 1
    print(f"matched {matched}")
    print(f"already_sent {already}")
    print(f"opted_out {opted}")
    print(f"sent {0 if not confirm else sent}")
    print(f"failed {0 if not confirm else failed}")
    return 0


def keygen():
    """Print the public key and key id. The private key is not printed."""
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    kid = "k" + secrets.token_hex(4)
    text = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    print(f"key_id={kid}")
    print(f"public_key={text}")
