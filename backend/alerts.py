"""Instant admin alerts. Counts and licence ids only.

The body is built from an allow-list. A customer address, name, company,
or IP is never copied in, and a mail failure is logged without one.
"""

import html
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

logger = logging.getLogger("alerts")

LONDON = ZoneInfo("Europe/London")

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS admin_alert_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        licence_id INTEGER,
        platform TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_alert_log_created
        ON admin_alert_log(created_at)
    """,
)

# Real alerts in a rolling hour. The summary that follows is not one of them.
ALERT_HOUR_CAP = 30
# A second installer redirect for the same licence and platform inside this
# window is the same download as the click that preceded it.
ALERT_DEDUP_SECONDS = 300

_KINDS = ("free_download", "free_verified", "pro_purchase")

_SUBJECTS = {
    "free_download": "[Node Control] New Free download",
    "free_verified": "[Node Control] New Free sign-up",
    "pro_purchase": "[Node Control] New Pro purchase",
    "summary": "[Node Control] Alert summary",
}

_EVENTS = {
    "free_download": "Free download",
    "free_verified": "Free sign-up",
    "pro_purchase": "Pro purchase",
}

_TIERS = {
    "free_download": "free",
    "free_verified": "free",
    "pro_purchase": "pro",
}

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)
_PATH_RE = re.compile(r"^/[A-Za-z0-9._~/-]*$")
_ATTR_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_IPV6_RE = re.compile(r"^[0-9a-f:]+$")


def queue(payload):
    """Start one alert. Returns immediately. Never raises.

    An empty ADMIN_ALERT_EMAIL turns this into a no-op so the alerts can
    be switched off without a deploy. Only the fields the body is allowed
    to show are kept; anything else on the payload is dropped here.
    """
    if not _address():
        return None
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("kind") or "")
    if kind not in _KINDS:
        return None
    licence_id = _positive_int(payload.get("licence_id"))
    if licence_id is None:
        return None
    safe = {
        "kind": kind,
        "licence_id": licence_id,
        "platform": _plain(payload.get("platform")),
        "arch": _plain(payload.get("arch")),
        "version": _plain(payload.get("version")),
        "utm_source": _plain(payload.get("utm_source")),
        "utm_medium": _plain(payload.get("utm_medium")),
        "utm_campaign": _plain(payload.get("utm_campaign")),
        "referrer": _plain(payload.get("referrer")),
        "landing_page": _plain(payload.get("landing_page")),
    }
    try:
        thread = threading.Thread(target=_guarded, args=(safe,), daemon=True)
        thread.start()
    except Exception:
        logger.error("Admin alert was not sent")
        return None
    return thread


def _guarded(safe):
    try:
        deliver(safe)
    except Exception:
        logger.error("Admin alert was not sent")


def deliver(safe):
    """Claim the alert, then send it. A send failure keeps the claim."""
    address = _address()
    if not address:
        return
    kind = safe.get("kind")
    if kind not in _KINDS:
        return
    licence_id = _positive_int(safe.get("licence_id"))
    if licence_id is None:
        return
    platform = _platform(safe.get("platform"))
    if licence_id in _skip_ids():
        return
    import app as api
    db = api.get_db()
    try:
        db.execute("PRAGMA busy_timeout=5000")
        decision, sent = _claim(db, kind, licence_id, platform)
        if decision == "skip":
            return
        if decision == "summary":
            text = _summary_text(sent)
            subject = _SUBJECTS["summary"]
        else:
            today, all_time = _counts(db, kind)
            text = _event_text(safe, kind, platform, licence_id, today, all_time)
            subject = _SUBJECTS[kind]
        _mail(api, address, subject, text)
    finally:
        db.close()


def _claim(db, kind, licence_id, platform):
    """Reserve one send. 'summary' replaces the event once the hour is full.

    BEGIN IMMEDIATE so two gunicorn workers share one cap. The row stays
    after a mail failure so a retry does not send the same alert again.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = _stamp(now)
    hour_ago = _stamp(now - timedelta(hours=1))
    dedup_ago = _stamp(now - timedelta(seconds=ALERT_DEDUP_SECONDS))
    db.execute("BEGIN IMMEDIATE")
    if kind in ("free_verified", "pro_purchase"):
        prior = db.execute(
            """
            SELECT 1 FROM admin_alert_log
            WHERE kind = ? AND licence_id = ?
            LIMIT 1
            """,
            (kind, licence_id),
        ).fetchone()
        if prior:
            db.rollback()
            return "skip", 0
    if kind == "free_download":
        recent = db.execute(
            """
            SELECT 1 FROM admin_alert_log
            WHERE kind = 'free_download' AND licence_id = ? AND platform = ?
              AND created_at >= ?
            LIMIT 1
            """,
            (licence_id, platform, dedup_ago),
        ).fetchone()
        if recent:
            db.rollback()
            return "skip", 0
    count = db.execute(
        """
        SELECT COUNT(*) AS c FROM admin_alert_log
        WHERE kind IN ('free_download', 'free_verified', 'pro_purchase')
          AND created_at >= ?
        """,
        (hour_ago,),
    ).fetchone()["c"]
    if count >= ALERT_HOUR_CAP:
        summary = db.execute(
            """
            SELECT 1 FROM admin_alert_log
            WHERE kind = 'summary' AND created_at >= ?
            LIMIT 1
            """,
            (hour_ago,),
        ).fetchone()
        if summary:
            db.rollback()
            return "skip", 0
        db.execute(
            """
            INSERT INTO admin_alert_log (kind, licence_id, platform, created_at)
            VALUES ('summary', NULL, '', ?)
            """,
            (stamp,),
        )
        db.commit()
        return "summary", int(count)
    db.execute(
        """
        INSERT INTO admin_alert_log (kind, licence_id, platform, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (kind, licence_id, platform, stamp),
    )
    db.commit()
    return "send", 0


def _mail(api, address, subject, text):
    try:
        ok = api._send_mail(
            address, subject, text, "<pre>" + html.escape(text) + "</pre>",
            log_recipient=False,
        )
    except Exception:
        logger.error("Admin alert was not sent")
        return
    if not ok:
        logger.error("Admin alert was not sent")


def _event_text(safe, kind, platform, licence_id, today, all_time):
    lines = [
        f"Event: {_EVENTS[kind]}",
        f"Tier: {_TIERS[kind]}",
        f"Platform: {platform}",
    ]
    arch = _arch(safe.get("arch"))
    if arch:
        lines.append(f"Arch: {arch}")
    lines.append(f"Version: {_version(safe.get('version'))}")
    lines.append(f"Time: {_london_now()}")
    lines.append(f"Licence id: {licence_id}")
    for label, key in (
        ("Source", "utm_source"),
        ("Medium", "utm_medium"),
        ("Campaign", "utm_campaign"),
    ):
        value = _attr(safe.get(key))
        if value:
            lines.append(f"{label}: {value}")
    referrer = _referrer(safe.get("referrer"))
    if referrer:
        lines.append(f"Referrer: {referrer}")
    landing = _landing(safe.get("landing_page"))
    if landing:
        lines.append(f"Landing page: {landing}")
    lines.append(f"Today: {int(today)}")
    lines.append(f"All time: {int(all_time)}")
    return "\n".join(lines) + "\n"


def _summary_text(sent):
    lines = [
        "Event: Alert summary",
        f"Time: {_london_now()}",
        f"Sent this hour: {int(sent)}",
        "Further alerts this hour will not be sent.",
    ]
    return "\n".join(lines) + "\n"


def _counts(db, kind):
    """Today is Europe/London. The cutoff is naive UTC so it sorts against
    both timestamp shapes stored in SQLite (with and without a trailing Z).
    """
    cutoff = _today_cutoff()
    if kind == "free_download":
        where = "FROM download_events WHERE kind = 'redirect'"
        today_sql = where + " AND created_at >= ?"
    elif kind == "free_verified":
        where = (
            "FROM licenses WHERE tier = 'free' "
            "AND verified_at IS NOT NULL AND verified_at != '' "
            "AND verified_at NOT LIKE 'PENDING:%'"
        )
        today_sql = where + " AND verified_at >= ?"
    elif kind == "pro_purchase":
        where = "FROM pro_keys WHERE source = 'stripe'"
        today_sql = where + " AND created_at >= ?"
    else:
        return 0, 0
    all_time = db.execute(f"SELECT COUNT(*) AS c {where}").fetchone()["c"]
    today = db.execute(f"SELECT COUNT(*) AS c {today_sql}", (cutoff,)).fetchone()["c"]
    return int(today), int(all_time)


def _address():
    import app as api
    return str(api.app.config.get("ADMIN_ALERT_EMAIL") or "").strip()


def _skip_ids():
    import app as api
    raw = str(api.app.config.get("ADMIN_ALERT_SKIP_LICENCE_IDS") or "")
    found = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            number = int(part)
            if number > 0:
                found.add(number)
    return found


def _today_cutoff():
    now = datetime.now(LONDON)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    utc = start.astimezone(timezone.utc).replace(tzinfo=None)
    return utc.strftime("%Y-%m-%dT%H:%M:%S")


def _london_now():
    return datetime.now(LONDON).strftime("%Y-%m-%d %H:%M Europe/London")


def _stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _plain(value):
    if value is None:
        return ""
    return str(value)


def _positive_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def _platform(value):
    text = _plain(value).strip().lower()
    if text in ("mac", "macos", "osx", "darwin"):
        return "mac"
    if text in ("win", "windows"):
        return "win"
    return "unknown"


def _arch(value):
    text = _plain(value).strip().lower()
    if "arm64" in text or "aarch64" in text:
        return "arm64"
    if "x86_64" in text or "amd64" in text or "x64" in text:
        return "x86_64"
    return ""


def _version(value):
    text = _plain(value).strip()
    if text.startswith("v"):
        text = text[1:]
    if _VERSION_RE.match(text):
        return text
    return "unknown"


def _attr(value):
    text = _one_line(value)
    if not text or "@" in text or _IPV4_RE.match(text) or _looks_like_ipv6(text):
        return ""
    if not _ATTR_RE.match(text):
        return ""
    return text


def _referrer(value):
    """Host only. A query string, path, userinfo, or IP address is dropped."""
    text = _one_line(value)
    if not text:
        return ""
    if "://" in text or text.startswith("//"):
        try:
            parsed = urlparse(text if "://" in text else "http:" + text)
        except Exception:
            return ""
        if parsed.username or parsed.password:
            return ""
        text = parsed.hostname or ""
    text = text.lower().strip(".")
    if not text or "@" in text or _IPV4_RE.match(text) or _looks_like_ipv6(text):
        return ""
    if not _HOST_RE.match(text):
        return ""
    return text


def _landing(value):
    text = _one_line(value)
    if not text:
        return ""
    text = text.split("?", 1)[0].split("#", 1)[0]
    if "@" in text or ".." in text or "\\" in text or not text.startswith("/"):
        return ""
    if not _PATH_RE.match(text):
        return ""
    return text[:256]


def _one_line(value):
    text = _plain(value).replace("\r", " ").replace("\n", " ").strip()
    return " ".join(text.split())


def _looks_like_ipv6(value):
    return ":" in value and bool(_IPV6_RE.match(value))
