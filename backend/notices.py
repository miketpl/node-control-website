"""Service notices to licence holders.

The API, the CLI, and the logs report counts only. A customer address is
used to call the mail sender and is not written to a table, a response,
or a log line.
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path

from flask import jsonify, request
from itsdangerous import BadSignature, URLSafeSerializer

import app as api
from licence_v1 import parse_version

logger = logging.getLogger("notices")

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS notices_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template TEXT NOT NULL,
        licence_kind TEXT NOT NULL,
        licence_ref INTEGER NOT NULL,
        sent_at TEXT NOT NULL,
        UNIQUE(template, licence_kind, licence_ref)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notice_opt_outs (
        licence_kind TEXT NOT NULL,
        licence_ref INTEGER NOT NULL,
        opted_out_at TEXT NOT NULL,
        PRIMARY KEY (licence_kind, licence_ref)
    )
    """,
)

AUDIENCES = ("free_downloaded", "free_all", "pro_active", "all")
TEMPLATE_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
KINDS = ("free", "pro", "subscription")
_SALT = "nodecontrol-notice-unsubscribe"
_PLACEHOLDER = "change-me-in-production"
_UNSUBSCRIBE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Unsubscribed</title></head>
<body><p>You will not receive these Node Control notices.</p></body>
</html>
"""


def register(flask_app):
    flask_app.add_url_rule(
        "/api/admin/notify", "admin_notify", admin_notify, methods=["POST"],
    )
    flask_app.add_url_rule(
        "/api/notices/unsubscribe",
        "notice_unsubscribe",
        unsubscribe,
        methods=["GET", "POST"],
    )


def _templates_root():
    return Path(__file__).resolve().parent / "email_templates"


def _template_dir(name):
    if not name or ".." in name or not TEMPLATE_NAME.match(name):
        return None
    root = _templates_root()
    path = (root / name).resolve()
    if path.parent != root:
        return None
    if not path.is_dir():
        return None
    return path


def _load_template(name):
    path = _template_dir(name)
    if path is None:
        return None
    try:
        subject = (path / "subject.txt").read_text(encoding="utf-8").strip()
        text = (path / "body.txt").read_text(encoding="utf-8")
        html = (path / "body.html").read_text(encoding="utf-8")
    except OSError:
        logger.error("Notice template could not be read")
        return None
    if not subject or "{{unsubscribe_url}}" not in text or "{{unsubscribe_url}}" not in html:
        return None
    return subject, text, html


def _secret():
    value = (api.app.config.get("NOTICE_UNSUBSCRIBE_SECRET") or "").strip()
    if not value or value == _PLACEHOLDER:
        return ""
    return value


def _serializer():
    secret = _secret()
    if not secret:
        return None
    return URLSafeSerializer(secret, salt=_SALT)


def _unsubscribe_url(kind, ref):
    serializer = _serializer()
    if serializer is None:
        return ""
    token = serializer.dumps({"k": kind, "r": int(ref)})
    base = (api.app.config.get("API_PUBLIC_URL") or "https://api.nodecontrol.io").rstrip("/")
    return f"{base}/api/notices/unsubscribe?t={token}"


def _throttle_seconds():
    raw = api.app.config.get("NOTICE_THROTTLE_SECONDS")
    if raw is None or str(raw).strip() == "":
        return 0.25
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.25
    if value < 0:
        return 0.0
    if value > 5:
        return 5.0
    return value


def _render(template, url):
    subject, text, html = template
    return (
        subject,
        text.replace("{{unsubscribe_url}}", url),
        html.replace("{{unsubscribe_url}}", url),
    )


def _free_targets(db, downloaded_only):
    sql = """
        SELECT id, email FROM licenses
        WHERE tier = 'free' AND status = 'active'
    """
    if downloaded_only:
        sql += " AND download_count > 0"
    return [("free", row["id"], row["email"] or "") for row in db.execute(sql)]


def _pro_targets(db):
    targets = []
    covered = set()
    keys = db.execute(
        """
        SELECT id, email, subscription_id, source
        FROM pro_keys
        WHERE status = 'active'
        """
    ).fetchall()
    for key in keys:
        sub_id = (key["subscription_id"] or "").strip()
        if key["source"] != "manual" and sub_id:
            sub = db.execute(
                "SELECT status FROM pro_subscriptions WHERE stripe_subscription_id = ?",
                (sub_id,),
            ).fetchone()
            if not sub or sub["status"] not in ("active", "trialing"):
                continue
            covered.add(sub_id)
        targets.append(("pro", key["id"], key["email"] or ""))
    subs = db.execute(
        """
        SELECT id, email, stripe_subscription_id
        FROM pro_subscriptions
        WHERE status IN ('active', 'trialing')
        """
    ).fetchall()
    for sub in subs:
        sub_id = sub["stripe_subscription_id"] or ""
        if sub_id in covered:
            continue
        existing = db.execute(
            "SELECT id FROM pro_keys WHERE subscription_id = ?",
            (sub_id,),
        ).fetchone()
        if existing:
            continue
        targets.append(("subscription", sub["id"], sub["email"] or ""))
    return targets


def _audience(db, name):
    if name == "free_downloaded":
        return _free_targets(db, True)
    if name == "free_all":
        return _free_targets(db, False)
    if name == "pro_active":
        return _pro_targets(db)
    if name == "all":
        return _free_targets(db, False) + _pro_targets(db)
    return None


def _known_versions(db):
    found = {}
    for table in ("registrations", "telemetry_sessions"):
        rows = db.execute(
            f"SELECT licence_kind, licence_ref, app_version FROM {table}"
        )
        for row in rows:
            parsed = parse_version((row["app_version"] or "").strip())
            if parsed is None:
                continue
            key = (row["licence_kind"], int(row["licence_ref"]))
            current = found.get(key)
            if current is None or parsed > current:
                found[key] = parsed
    return found


def _keeps_version(known, kind, ref, below, include_unknown):
    if below is None:
        return True
    version = known.get((kind, int(ref)))
    if version is None:
        return include_unknown
    return version < below


def _already_sent(db, template, kind, ref):
    row = db.execute(
        """
        SELECT 1 FROM notices_sent
        WHERE template = ? AND licence_kind = ? AND licence_ref = ?
        """,
        (template, kind, ref),
    ).fetchone()
    return row is not None


def _opted_out(db, kind, ref):
    row = db.execute(
        """
        SELECT 1 FROM notice_opt_outs
        WHERE licence_kind = ? AND licence_ref = ?
        """,
        (kind, ref),
    ).fetchone()
    return row is not None


def _mark_sent(db, template, kind, ref):
    db.execute(
        """
        INSERT INTO notices_sent (template, licence_kind, licence_ref, sent_at)
        VALUES (?, ?, ?, ?)
        """,
        (template, kind, ref, datetime.utcnow().isoformat()),
    )
    db.commit()


def _usable_address(value):
    value = (value or "").strip()
    if "@" not in value or "." not in value.split("@", 1)[-1]:
        return ""
    return value


def _counts(matched, already, opted, sent, failed, dry_run):
    return {
        "dry_run": bool(dry_run),
        "matched": matched,
        "already_sent": already,
        "opted_out": opted,
        "sent": sent,
        "failed": failed,
    }


@api.require_admin
def admin_notify():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request body"}), 400
    template_name = data.get("template")
    audience_name = data.get("audience")
    if not isinstance(template_name, str) or not isinstance(audience_name, str):
        return jsonify({"error": "template and audience are required"}), 400
    if audience_name not in AUDIENCES:
        return jsonify({"error": "audience is not recognised"}), 400
    dry_run = data.get("dry_run", True)
    include_unknown = data.get("include_unknown_version", False)
    if not isinstance(dry_run, bool) or not isinstance(include_unknown, bool):
        return jsonify({"error": "dry_run and include_unknown_version must be true or false"}), 400
    below_raw = data.get("below_version") or ""
    if below_raw and not isinstance(below_raw, str):
        return jsonify({"error": "below_version must be N.N.N"}), 400
    below = None
    if below_raw:
        below = parse_version(below_raw.strip())
        if below is None:
            return jsonify({"error": "below_version must be N.N.N"}), 400
    loaded = _load_template(template_name.strip())
    if loaded is None:
        return jsonify({"error": "unknown template"}), 404
    if not dry_run and _serializer() is None:
        return jsonify({"error": "notices are not configured"}), 503

    db = api.get_db()
    try:
        targets = _audience(db, audience_name)
        known = _known_versions(db)
        chosen = [
            (kind, ref, address)
            for kind, ref, address in targets
            if _keeps_version(known, kind, ref, below, include_unknown)
        ]
        matched = len(chosen)
        already = 0
        opted = 0
        sent = 0
        failed = 0
        delay = _throttle_seconds()
        pending = []
        for kind, ref, address in chosen:
            if _already_sent(db, template_name.strip(), kind, ref):
                already += 1
                continue
            if _opted_out(db, kind, ref):
                opted += 1
                continue
            pending.append((kind, ref, address))
        if dry_run:
            logger.info(
                "Notice dry run finished matched=%s already_sent=%s opted_out=%s",
                matched, already, opted,
            )
            return jsonify(_counts(matched, already, opted, 0, 0, True))

        for index, (kind, ref, address) in enumerate(pending):
            if index and delay:
                time.sleep(delay)
            if _already_sent(db, template_name.strip(), kind, ref) or _opted_out(db, kind, ref):
                if _already_sent(db, template_name.strip(), kind, ref):
                    already += 1
                else:
                    opted += 1
                continue
            url = _unsubscribe_url(kind, ref)
            if not url:
                failed += 1
                logger.error("Notice was not sent")
                continue
            recipient = _usable_address(address)
            if not recipient:
                failed += 1
                logger.error("Notice was not sent")
                continue
            subject, text, html = _render(loaded, url)
            try:
                ok = api._send_mail(recipient, subject, text, html, log_recipient=False)
            except Exception:
                logger.error("Notice was not sent")
                ok = False
            if not ok:
                failed += 1
                continue
            try:
                _mark_sent(db, template_name.strip(), kind, ref)
            except Exception:
                logger.error("Notice was sent but was not recorded")
                failed += 1
                continue
            sent += 1
    except Exception:
        logger.error("Notice run failed")
        return jsonify({"error": "Notice run failed"}), 500
    finally:
        try:
            db.close()
        except Exception:
            pass
    logger.info(
        "Notice run finished matched=%s already_sent=%s opted_out=%s sent=%s failed=%s",
        matched, already, opted, sent, failed,
    )
    return jsonify(_counts(matched, already, opted, sent, failed, False))


def unsubscribe():
    serializer = _serializer()
    if serializer is None:
        return jsonify({"error": "notices are not configured"}), 503
    token = request.values.get("t") or ""
    try:
        data = serializer.loads(token)
    except BadSignature:
        return jsonify({"error": "That link is not valid."}), 400
    if not isinstance(data, dict):
        return jsonify({"error": "That link is not valid."}), 400
    kind = data.get("k")
    ref = data.get("r")
    if kind not in KINDS or not isinstance(ref, int):
        return jsonify({"error": "That link is not valid."}), 400
    db = api.get_db()
    try:
        db.execute(
            """
            INSERT INTO notice_opt_outs (licence_kind, licence_ref, opted_out_at)
            VALUES (?, ?, ?)
            ON CONFLICT(licence_kind, licence_ref) DO NOTHING
            """,
            (kind, ref, datetime.utcnow().isoformat()),
        )
        db.commit()
    finally:
        db.close()
    logger.info("Notice opt-out recorded")
    return _UNSUBSCRIBE_PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}
