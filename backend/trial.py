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
import sqlite3
import sys
import tempfile
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
    """Opaque 16-hex ref. No machine-hash key means no ref, not a stand-in."""
    key = _secret()
    if not key:
        return None
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
    if not trial_enabled() or not _secret():
        return {
            "trial_state": "ineligible",
            "reason": "disabled",
            "row": None,
            "active": False,
            "eligible": False,
        }
    digest = email_hash(record.get("email") or "")
    presented_hmac = machine_hmac(presented) if presented and HASH_RE.match(presented) else ""
    db = _db()
    try:
        by_email = _row_for_email(db, digest)
        by_machine = _row_for_machine(db, presented_hmac) if presented_hmac else None
    finally:
        db.close()
    if by_email:
        expires = v1.parse_iso(by_email["expires_at"])
        still = bool(expires and expires > now)
        stored = by_email["machine_hash"] or ""
        if not stored and presented_hmac:
            bound = _bind_empty_machine(by_email["id"], presented_hmac)
            if bound == "bound":
                stored = presented_hmac
            else:
                return {
                    "trial_state": "ineligible",
                    "reason": "machine_used",
                    "row": by_email,
                    "active": False,
                    "eligible": False,
                }
        matched = bool(stored) and stored == presented_hmac
        if not stored and presented in (None, "unavailable"):
            matched = True
        if not matched:
            return {
                "trial_state": "ineligible",
                "reason": "email_used",
                "row": by_email,
                "active": False,
                "eligible": False,
                "no_trial_lease": True,
            }
        if still:
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


def _bind_empty_machine(trial_id, presented_hmac):
    """Attach the first real computer to an email-only trial. 'clash' if that computer is taken."""
    db = _db()
    try:
        try:
            cursor = db.execute(
                """
                UPDATE free_trials SET machine_hash = ?
                WHERE id = ? AND machine_hash = ''
                """,
                (presented_hmac, int(trial_id)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            return "clash"
        fresh = db.execute(
            "SELECT machine_hash FROM free_trials WHERE id = ?", (int(trial_id),)
        ).fetchone()
    finally:
        db.close()
    if fresh and (fresh["machine_hash"] or "") == presented_hmac and cursor.rowcount:
        return "bound"
    if fresh and (fresh["machine_hash"] or "") == presented_hmac:
        return "bound"
    return "clash"


def _insert_trial(record, install_id, presented, how):
    """Insert one trial. A unique-index clash returns None and does not count a start."""
    v1 = _v1()
    now = v1.utcnow()
    started = v1.iso(now)
    expires = v1.iso(now + timedelta(days=TRIAL_DAYS))
    machine = "" if presented == "unavailable" else machine_hmac(presented)
    db = _db()
    try:
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
        except sqlite3.IntegrityError:
            db.rollback()
            return None
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


def _testing():
    try:
        return bool(_v1()._api().app.config.get("TESTING"))
    except Exception:
        return False


def _kid_ok(kid):
    """A test-only kid is loaded only while the process is under test."""
    if not kid:
        return False
    if kid.startswith("test-only") and not _testing():
        return False
    return True


def _load_signing_key(seed_name, kid_name):
    """Return (kid, private key) or None. Does not log the seed."""
    seed_b64 = (os.environ.get(seed_name) or "").strip()
    kid = (os.environ.get(kid_name) or "").strip()
    if not seed_b64 or not _kid_ok(kid):
        return None
    try:
        seed = base64.b64decode(seed_b64)
        key = Ed25519PrivateKey.from_private_bytes(seed)
    except Exception:
        return None
    return kid, key


def signing_keys():
    """Current key first, then the next key, for rotation and verification."""
    loaded = []
    for seed_name, kid_name in (
        ("LEASE_SIGNING_KEY", "LEASE_SIGNING_KID"),
        ("LEASE_SIGNING_KEY_NEXT", "LEASE_SIGNING_KID_NEXT"),
    ):
        item = _load_signing_key(seed_name, kid_name)
        if item:
            loaded.append(item)
    return loaded


def _sign(payload):
    """Sign with the current key only. A refused kid leaves the lease unsigned."""
    current = _load_signing_key("LEASE_SIGNING_KEY", "LEASE_SIGNING_KID")
    if not current:
        return None, None
    _kid, key = current
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = key.sign(body)

    def pack(raw):
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return LEASE_FORMAT, pack(body) + "." + pack(sig)


def verify_lease(token):
    """True when the current or next key verifies the lease bytes."""
    if not token or token.count(".") != 1:
        return False
    body_b64, sig_b64 = token.split(".", 1)

    def unpack(segment):
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))

    try:
        body = unpack(body_b64)
        sig = unpack(sig_b64)
    except Exception:
        return False
    for _kid, key in signing_keys():
        try:
            key.public_key().verify(sig, body)
            return True
        except Exception:
            continue
    return False


def current_and_next_kids():
    """Kids the app should accept. A test-only kid is omitted outside tests."""
    kids = []
    for name in ("LEASE_SIGNING_KID", "LEASE_SIGNING_KID_NEXT"):
        kid = (os.environ.get(name) or "").strip()
        if _kid_ok(kid):
            kids.append(kid)
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
    if view.get("no_lease") or view.get("no_trial_lease"):
        payload["lease"] = None
        payload["lease_format"] = None
        return payload
    ref = licence_ref(record["kind"], record["id"])
    if ref is None:
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
        "kid": (os.environ.get("LEASE_SIGNING_KID") or "").strip(),
        "kids": current_and_next_kids(),
        "install_id": install_id,
        "machine_hash_echo": presented or "",
        "licence_ref": ref,
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
    inserted = _insert_trial(record, ctx["install_id"], presented, "button")
    if inserted is None:
        view = _state_for(record, presented, ctx["version"], now)
        if view["trial_state"] == "active":
            body = v1.licence_payload(record, ctx["install_id"], ctx["version"])
            return __import__("flask").jsonify({
                "active": True,
                "tier": record["tier"],
                "licence": body,
            })
        reason = view["reason"] if view["reason"] in ("email_used", "machine_used") else "email_used"
        _count("trial_refused_" + reason)
        return v1.error(
            409, "trial_used", "This trial has already been used.",
            details={"reason": reason},
        )
    body = v1.licence_payload(record, ctx["install_id"], ctx["version"])
    return __import__("flask").jsonify({
        "active": True,
        "tier": record["tier"],
        "licence": body,
    })


def reset_by_email(email, confirm):
    """Find a trial by the keyed email hash. Prints the id only, never the address."""
    digest = email_hash(email or "")
    if not digest:
        print("MACHINE_HASH_KEY is not set", file=sys.stderr)
        return 1
    db = _db()
    try:
        row = db.execute(
            "SELECT id FROM free_trials WHERE email_hash = ?", (digest,)
        ).fetchone()
    finally:
        db.close()
    if not row:
        print("no matching trial")
        return 1
    return reset_trial(row["id"], confirm)


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
            SELECT t.*, l.email, l.status AS licence_status, l.tier AS licence_tier
            FROM free_trials t
            JOIN licenses l ON l.id = t.licence_ref
            WHERE t.licence_kind = 'free'
            """
        ).fetchall()
        upgraded = {
            int(item["free_license_id"])
            for item in db.execute(
                """
                SELECT free_license_id FROM pro_keys
                WHERE status = 'active' AND free_license_id IS NOT NULL
                """
            ).fetchall()
            if item["free_license_id"]
        }
    finally:
        db.close()
    due = []
    now = v1.utcnow()
    for row in rows:
        if (row["licence_status"] or "") == "revoked":
            continue
        if (row["licence_tier"] or "") == "pro":
            continue
        if int(row["licence_ref"]) in upgraded:
            continue
        started = v1.parse_iso(row["started_at"])
        expires = v1.parse_iso(row["expires_at"])
        if not started or not expires:
            continue
        grace_end = expires + timedelta(days=v1.GRACE_DAYS)
        if now > grace_end:
            continue
        day = (today - started.date()).days + 1
        if 11 <= day <= 13:
            due.append((row, "trial-day11"))
        elif day >= 14:
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


_ENV_ASSIGN = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(?P<value>.*)$"
)


def default_env_file():
    """The server .env, one directory above backend/."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, ".env")


def _line_ending(line):
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return ""


def _assignment(line):
    """Return (name, value) for an assignment line. Comments are not assignments."""
    ending = _line_ending(line)
    body = line[:-len(ending)] if ending else line
    if body.lstrip(" \t").startswith("#"):
        return None
    match = _ENV_ASSIGN.match(body)
    if not match:
        return None
    return match.group("name"), match.group("value")


def _value_set(value):
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    return bool(text.strip())


def _atomic_write(path, data):
    """Write data via a temp file in the same directory, then rename. Mode 600."""
    parent = os.path.dirname(path) or "."
    fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=".lease-key-", suffix=".tmp")
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, 0o600)
        os.close(fd)
        fd = None
        os.replace(tmp_name, path)
        tmp_name = None
        os.chmod(path, 0o600)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def keygen(env_file=None, next_key=False, overwrite=False):
    """Write a new lease seed into an env file. Print only the public key and id.

    The private seed is standard base64 of 32 bytes, which is what the lease
    signer decodes. It is not printed, logged, or put in an error message.
    Returns 0 on success and 1 when the existing key is left untouched.
    """
    path = os.path.abspath(env_file or default_env_file())
    key_name = "LEASE_SIGNING_KEY_NEXT" if next_key else "LEASE_SIGNING_KEY"
    id_name = "LEASE_SIGNING_KID_NEXT" if next_key else "LEASE_SIGNING_KID"
    if os.path.exists(path):
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError:
            print("Could not read the env file.", file=sys.stderr)
            return 1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            print("The env file is not UTF-8.", file=sys.stderr)
            return 1
    else:
        text = ""
    lines = text.splitlines(keepends=True)
    for line in lines:
        parsed = _assignment(line)
        if parsed and parsed[0] == key_name and _value_set(parsed[1]) and not overwrite:
            print(
                f"{key_name} is already set in {path}. Pass --overwrite to replace it.",
                file=sys.stderr,
            )
            return 1
    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    encoded = base64.b64encode(seed).decode("ascii")
    kid = "k" + secrets.token_hex(4)
    public_text = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    wanted = {key_name: encoded, id_name: kid}
    seen = set()
    out = []
    for line in lines:
        parsed = _assignment(line)
        if parsed and parsed[0] in wanted:
            ending = _line_ending(line) or "\n"
            out.append(f"{parsed[0]}={wanted[parsed[0]]}{ending}")
            seen.add(parsed[0])
        else:
            out.append(line)
    missing = [name for name in (key_name, id_name) if name not in seen]
    if missing:
        if out and not _line_ending(out[-1]):
            out[-1] = out[-1] + "\n"
        for name in missing:
            out.append(f"{name}={wanted[name]}\n")
    try:
        _atomic_write(path, "".join(out).encode("utf-8"))
    except OSError:
        print("Could not write the env file.", file=sys.stderr)
        return 1
    print(f"key_id={kid}")
    print(f"public_key={public_text}")
    print(f"env_file={path}")
    return 0
