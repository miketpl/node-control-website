"""
NodeControl License & Download Backend
Flask API for handling free edition download requests,
email verification, code redemption, and license tracking.
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import base64
import fcntl
import hmac
import html
import json
import os
import secrets
import string
import sqlite3
import smtplib
import logging
import re
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import stripe
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# ── Configuration ────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins=[
    "https://nodecontrol.io",
    "https://www.nodecontrol.io",
    "http://localhost:*",
    "http://127.0.0.1:*",
])

# Load from environment variables
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", secrets.token_hex(32)),
    DB_PATH=os.environ.get("DB_PATH", "licenses.db"),
    # Empty, or the public placeholder, means the admin API stays off.
    ADMIN_TOKEN=os.environ.get("ADMIN_TOKEN", ""),

    # SMTP settings
    SMTP_HOST=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    SMTP_PORT=int(os.environ.get("SMTP_PORT", 587)),
    SMTP_USER=os.environ.get("SMTP_USER", ""),
    SMTP_PASS=os.environ.get("SMTP_PASS", ""),
    SMTP_FROM=os.environ.get("SMTP_FROM", "noreply@nodecontrol.io"),
    SMTP_FROM_NAME=os.environ.get("SMTP_FROM_NAME", "NodeControl"),

    # Releases repo (public) for free tier downloads
    FREE_RELEASES_REPO=os.environ.get(
        "FREE_RELEASES_REPO", "miketpl/node-control-releases-free"
    ),

    # Code expiry (hours)
    CODE_EXPIRY_HOURS=int(os.environ.get("CODE_EXPIRY_HOURS", 72)),

    # GitHub license repo for free tier validation
    LICENSE_REPO=os.environ.get("LICENSE_REPO", "miketpl/node-control-license-free"),
    LICENSE_FILE=os.environ.get("LICENSE_FILE", "licenses.json"),
    GITHUB_PAT=os.environ.get("GITHUB_PAT", ""),          # read-only (app license check)
    GITHUB_PAT_WRITE=os.environ.get("GITHUB_PAT_WRITE", ""),  # read/write (license sync)

    # Pro subscription. Prices are Stripe Price IDs, not amounts.
    SITE_URL=os.environ.get("SITE_URL", "https://nodecontrol.io"),
    STRIPE_SECRET_KEY=os.environ.get("STRIPE_SECRET_KEY", ""),
    STRIPE_WEBHOOK_SECRET=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
    STRIPE_PRICE_PRO_MONTHLY=os.environ.get("STRIPE_PRICE_PRO_MONTHLY", ""),
    STRIPE_PRICE_PRO_ANNUAL=os.environ.get("STRIPE_PRICE_PRO_ANNUAL", ""),
    # Optional. Empty falls back to GITHUB_PAT_WRITE. That token needs
    # contents:write on miketpl/node-control-registrations.
    GITHUB_PAT_REGISTRATIONS=os.environ.get("GITHUB_PAT_REGISTRATIONS", ""),
    PRO_ALLOWLIST_REPO=os.environ.get("PRO_ALLOWLIST_REPO") or "miketpl/node-control-registrations",
    PRO_ALLOWLIST_PATH=os.environ.get("PRO_ALLOWLIST_PATH") or "allowlist.json",
    PRO_RELEASES_REPO=os.environ.get("PRO_RELEASES_REPO") or "miketpl/node-control-releases-pro",
    PRO_RELEASES_PAT=os.environ.get("PRO_RELEASES_PAT", ""),
    # Falls back to SECRET_KEY when unset. Used to sign Pro download links.
    PRO_DOWNLOAD_SECRET=os.environ.get("PRO_DOWNLOAD_SECRET", ""),
    # Upper bound for a download token. The payload also carries its own exp.
    PRO_DOWNLOAD_TOKEN_MAX_AGE=int(os.environ.get("PRO_DOWNLOAD_TOKEN_MAX_AGE", 7 * 24 * 3600)),

    # 0.9.41. Empty LEGACY_ALLOWLIST_SYNC means the webhook does not write allowlist.json.
    LEGACY_ALLOWLIST_SYNC=os.environ.get("LEGACY_ALLOWLIST_SYNC", ""),
    # Read-only on the private releases-free and releases-pro repos. PRO_RELEASES_PAT is the fallback.
    RELEASES_READ_PAT=os.environ.get("RELEASES_READ_PAT", ""),
    # 32-byte key as 64 hex characters. Encrypts Professional keys so a resend returns the same key.
    KEY_ENCRYPTION_KEY=os.environ.get("KEY_ENCRYPTION_KEY", ""),
    # Empty means paused. Set FREE_DOWNLOADS_PAUSED=false to open Free downloads.
    FREE_DOWNLOADS_PAUSED=os.environ.get("FREE_DOWNLOADS_PAUSED", ""),
    FREE_PAUSED_MESSAGE=os.environ.get("FREE_PAUSED_MESSAGE", ""),
    MAINTENANCE=os.environ.get("MAINTENANCE", ""),
    MIN_SUPPORTED_VERSION_FREE=os.environ.get("MIN_SUPPORTED_VERSION_FREE", "0.9.41"),
    MIN_SUPPORTED_VERSION_PRO=os.environ.get("MIN_SUPPORTED_VERSION_PRO", "0.9.41"),
    TELEMETRY_RETENTION_DAYS=os.environ.get("TELEMETRY_RETENTION_DAYS", "365"),
    TELEMETRY_ACCEPT=os.environ.get("TELEMETRY_ACCEPT", "true"),
    # Empty disables the alert. The default address is the public support mailbox.
    REGISTRATION_ALERT_EMAIL=os.environ.get("REGISTRATION_ALERT_EMAIL", "support@nodecontrol.io"),
    API_PUBLIC_URL=os.environ.get("API_PUBLIC_URL", "https://api.nodecontrol.io"),
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shown on the website when an address already has a free licence.
# This is the support address on nodecontrol.io. Do not invent another.
SUPPORT_EMAIL = "support@nodecontrol.io"
ADMIN_TOKEN_PLACEHOLDER = "change-me-in-production"
EMAIL_SEND_ERROR = (
    "We could not send the verification email. Please try again in a few minutes."
)
LICENCE_SYNC_ERROR = (
    "We could not activate this licence. Nothing was issued. "
    "Please try the same code again in a few minutes."
)


# ── Database ─────────────────────────────────────────────────
def get_db():
    """Get a database connection."""
    db = sqlite3.connect(app.config["DB_PATH"])
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    """Create tables if they don't exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            company TEXT DEFAULT '',
            platform TEXT DEFAULT '',
            tier TEXT DEFAULT 'free',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            verified_at TEXT,
            redeemed_at TEXT,
            download_count INTEGER DEFAULT 0,
            ip_address TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS download_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER NOT NULL,
            platform TEXT DEFAULT '',
            kind TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_download_events_created ON download_events(created_at);

        CREATE INDEX IF NOT EXISTS idx_licenses_code ON licenses(code);
        CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email);
        CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);

        CREATE TABLE IF NOT EXISTS pro_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT DEFAULT '',
            stripe_customer_id TEXT DEFAULT '',
            stripe_subscription_id TEXT UNIQUE,
            stripe_checkout_session_id TEXT DEFAULT '',
            plan TEXT DEFAULT '',
            status TEXT DEFAULT '',
            cancel_at_period_end INTEGER DEFAULT 0,
            current_period_end TEXT DEFAULT '',
            added_to_allowlist INTEGER DEFAULT 0,
            welcomed_at TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_pro_sub_email ON pro_subscriptions(email);

        CREATE TABLE IF NOT EXISTS stripe_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            processed_at TEXT NOT NULL
        );
    """)
    db.commit()
    db.close()


# ── Helpers ──────────────────────────────────────────────────
# Attribution columns on licenses. Added after launch, so existing databases
# get them through ALTER TABLE. Values are short, plain strings or ''.
ATTRIBUTION_FIELDS = {
    "utm_source": 64,
    "utm_medium": 64,
    "utm_campaign": 128,
    "referrer": 128,
    "landing_page": 256,
}


def _schema_already_applied(exc):
    """True when another worker created this column, table, or index first."""
    message = str(exc).lower()
    return "duplicate column name" in message or "already exists" in message


def _add_license_column(db, column):
    """Add one attribution column. A duplicate name means the other worker won."""
    if column not in ATTRIBUTION_FIELDS:
        raise ValueError("unknown licence column")
    try:
        db.execute(f"ALTER TABLE licenses ADD COLUMN {column} TEXT DEFAULT ''")
    except sqlite3.OperationalError as exc:
        if not _schema_already_applied(exc):
            raise


def _apply_schema(db, statement):
    """Run one CREATE TABLE or CREATE INDEX. IF NOT EXISTS, and ignore a race."""
    try:
        db.execute(statement)
    except sqlite3.OperationalError as exc:
        if not _schema_already_applied(exc):
            raise


def migrate_db():
    """Add attribution columns that older databases do not have yet.

    Gunicorn imports the app in each worker, so several processes run this
    at startup. A lock beside the database makes them take turns. Each
    column add still ignores 'duplicate column name' if two slip through.
    """
    lock_path = str(app.config["DB_PATH"]) + ".migrate.lock"
    lock_file = open(lock_path, "a")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        db = get_db()
        try:
            db.execute("PRAGMA busy_timeout=30000")
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            have = {row["name"] for row in db.execute("PRAGMA table_info(licenses)")}
            for column in ATTRIBUTION_FIELDS:
                if column not in have:
                    _add_license_column(db, column)
            _apply_schema(db, """
                CREATE TABLE IF NOT EXISTS download_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_id INTEGER NOT NULL,
                    platform TEXT DEFAULT '',
                    kind TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            _apply_schema(
                db,
                "CREATE INDEX IF NOT EXISTS idx_download_events_created ON download_events(created_at)",
            )
            _apply_schema(
                db,
                "CREATE INDEX IF NOT EXISTS idx_licenses_utm_source ON licenses(utm_source)",
            )
            from licence_v1 import V1_SCHEMA
            for statement in V1_SCHEMA:
                _apply_schema(db, statement)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)
_PATH_RE = re.compile(r"^/[A-Za-z0-9._~/-]*$")
_IP_RE = re.compile(r"^[A-Za-z0-9.:]+$")

# Download events are a public POST. The per-licence cap is in SQLite, so it
# holds across workers. The address cap is in memory, per worker.
DOWNLOAD_EVENT_IP_LIMIT = 60
DOWNLOAD_EVENT_IP_WINDOW = 3600
DOWNLOAD_EVENT_LICENCE_CAP = 24
DOWNLOAD_EVENT_BODY_LIMIT = 1024
_download_event_lock = threading.Lock()
_download_event_hits = {}


def _clean_host(value):
    """Host name only. A full URL is reduced to its host. Anything else is dropped."""
    value = str(value or "").strip()
    if not value:
        return ""
    if "://" in value or value.startswith("//"):
        try:
            value = urlparse(value if "://" in value else "http:" + value).hostname or ""
        except Exception:
            return ""
    value = value.lower().strip(".")[:128]
    if not _HOST_RE.match(value):
        return ""
    return value


def _clean_path(value):
    """Site path only. Query strings and full URLs are dropped."""
    value = str(value or "").strip().split("?", 1)[0].split("#", 1)[0]
    if not value.startswith("/") or ".." in value or "\\" in value:
        return ""
    if not _PATH_RE.match(value):
        return ""
    return value[:256]


def clean_attribution(data):
    """Return the attribution fields from a request body, trimmed and bounded.

    Source, medium and campaign are lower-cased and limited to letters,
    digits, dot, dash and underscore, so the weekly report groups cleanly.
    The referrer is a host name. The landing page is a path.
    """
    if not isinstance(data, dict):
        data = {}
    out = {}
    for field, limit in ATTRIBUTION_FIELDS.items():
        if field == "referrer":
            out[field] = _clean_host(data.get(field))
        elif field == "landing_page":
            out[field] = _clean_path(data.get(field))
        else:
            value = str(data.get(field) or "").strip()[:limit]
            value = "".join(ch for ch in value.lower() if ch.isalnum() or ch in "._-")
            out[field] = value
    return out


def _client_ip():
    """Visitor address.

    The Spark is reached through a Cloudflare tunnel, so the peer is loopback
    and the client address is CF-Connecting-IP. Any other peer is used as-is.
    """
    import licence_v1
    return licence_v1.client_ip()


def _download_event_ip_allowed(ip):
    """Shared SQLite cap so both gunicorn workers count the same addresses."""
    import hashlib
    import licence_v1
    bucket = "ep:download-event:ip:" + hashlib.sha256((ip or "").encode()).hexdigest()
    allowed, _wait = licence_v1.consume_rate(bucket, DOWNLOAD_EVENT_IP_LIMIT, DOWNLOAD_EVENT_IP_WINDOW)
    return allowed


def reset_download_event_limits():
    with _download_event_lock:
        _download_event_hits.clear()
    try:
        db = get_db()
        db.execute("DELETE FROM rate_limits WHERE bucket LIKE 'ep:download-event:%'")
        db.commit()
        db.close()
    except Exception:
        logger.exception("Could not reset download-event rate limits")


def _utc_day(value, default):
    """Accept YYYY-MM-DD. An empty value uses the default. Anything else is rejected."""
    if value is None or str(value).strip() == "":
        return default
    raw = str(value).strip()
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return raw


def generate_code():
    """Generate a download code like NC-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"NC-{part1}-{part2}"


def generate_verify_code():
    """Generate a 6-digit numeric verification code."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def send_verification_email(to_email, to_name, verify_code, download_code):
    """Send verification email with the download code."""
    cfg = app.config

    if not cfg["SMTP_USER"] or not cfg["SMTP_PASS"]:
        logger.warning("SMTP not configured — verification email was not sent")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your NodeControl Download Code: {verify_code}"
    msg["From"] = f'{cfg["SMTP_FROM_NAME"]} <{cfg["SMTP_FROM"]}>'
    msg["To"] = to_email

    text_body = f"""Hi {to_name},

Thanks for requesting NodeControl Free Edition!

Your verification code is: {verify_code}

Enter this code on the download page to get your permanent download code.

This verification code expires in {cfg['CODE_EXPIRY_HOURS']} hours.

---
NodeControl by The Promised LAN
https://nodecontrol.io
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0b0f14; color: #c8cdd3; padding: 40px 20px;">
  <div style="max-width: 500px; margin: 0 auto; background: #12171e; border-radius: 12px; padding: 40px; border: 1px solid rgba(0,232,255,0.1);">
    <div style="text-align: center; margin-bottom: 30px;">
      <h1 style="color: #ffffff; font-size: 24px; margin: 0;">Node<span style="color: #00e8ff;">Control</span></h1>
      <p style="color: #636b75; font-size: 13px; margin: 4px 0 0;">by The Promised LAN</p>
    </div>

    <p>Hi {to_name},</p>
    <p>Thanks for requesting <strong>NodeControl Free Edition</strong>!</p>

    <p>Your verification code is:</p>
    <div style="text-align: center; margin: 24px 0;">
      <div style="display: inline-block; background: #1a2030; border: 2px solid #00e8ff; border-radius: 8px; padding: 16px 32px; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #00e8ff; font-family: monospace;">
        {verify_code}
      </div>
    </div>

    <p>Enter this code on the <a href="https://nodecontrol.io/#download" style="color: #00e8ff;">download page</a> to get your permanent download code and start downloading.</p>

    <p style="color: #636b75; font-size: 13px; margin-top: 30px;">This verification code expires in {cfg['CODE_EXPIRY_HOURS']} hours.</p>

    <hr style="border: none; border-top: 1px solid #1e2530; margin: 30px 0;">
    <p style="color: #636b75; font-size: 12px; text-align: center;">
      NodeControl &mdash; Automate Everything<br>
      <a href="https://nodecontrol.io" style="color: #00e8ff;">nodecontrol.io</a>
    </p>
  </div>
</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as server:
            server.starttls()
            server.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            server.send_message(msg)
        logger.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def _admin_is_configured():
    """Admin stays off until a real token is set."""
    token = app.config.get("ADMIN_TOKEN") or ""
    return bool(token) and token != ADMIN_TOKEN_PLACEHOLDER


def require_admin(f):
    """Decorator to require admin token for endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        configured = app.config.get("ADMIN_TOKEN") or ""
        if not _admin_is_configured():
            return jsonify({"error": "admin disabled"}), 503
        header = request.headers.get("Authorization", "")
        presented = header[7:] if header.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(presented, configured):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Download URL resolver ───────────────────────────────────

def _get_latest_download_urls() -> dict:
    """Fetch the latest release from the free releases repo and return
    direct browser_download_url links keyed by platform (mac/win).
    Falls back to the releases page URL on any failure.
    """
    repo = app.config["FREE_RELEASES_REPO"]
    fallback = f"https://github.com/{repo}/releases/latest"
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assets = data.get("assets", [])
        urls = {"mac": fallback, "win": fallback}
        for asset in assets:
            name = (asset.get("name") or "").lower()
            dl = asset.get("browser_download_url", "")
            if name.endswith(".dmg"):
                urls["mac"] = dl
            elif name.endswith(".exe"):
                urls["win"] = dl
        return urls
    except Exception as exc:
        logger.warning(f"Failed to resolve download URLs: {exc}")
        return {"mac": fallback, "win": fallback}


# ── GitHub License Sync ──────────────────────────────────────

def _github_headers(write=False):
    """Common headers for GitHub Contents API calls.

    Uses GITHUB_PAT_WRITE for mutations, falls back to GITHUB_PAT.
    """
    pat = app.config["GITHUB_PAT_WRITE"] if write else app.config["GITHUB_PAT"]
    if not pat:
        pat = app.config["GITHUB_PAT_WRITE"] or app.config["GITHUB_PAT"]
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def _get_licenses_json():
    """Fetch current licenses.json from GitHub.

    Returns (parsed_dict, file_sha) or (None, None) if the file
    doesn't exist yet.
    """
    repo = app.config["LICENSE_REPO"]
    filepath = app.config["LICENSE_FILE"]
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}"

    try:
        req = Request(url, headers=_github_headers())
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = json.loads(
                base64.b64decode(data["content"]).decode("utf-8")
            )
            return content, data["sha"]
    except HTTPError as exc:
        # A missing file is an empty list. Anything else is a failed sync.
        if exc.code == 404:
            return None, None
        raise


def _put_licenses_json(content: dict, sha: str | None, message: str):
    """Write licenses.json back to GitHub via the Contents API."""
    repo = app.config["LICENSE_REPO"]
    filepath = app.config["LICENSE_FILE"]
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}"

    content_b64 = base64.b64encode(
        json.dumps(content, indent=2).encode("utf-8")
    ).decode("utf-8")

    body = {"message": message, "content": content_b64}
    if sha:
        body["sha"] = sha

    req = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=_github_headers(write=True),
        method="PUT",
    )
    with urlopen(req, timeout=15) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"GitHub sync returned {resp.status}")
        logger.info(f"GitHub licenses.json updated: {message}")


def _add_code_to_licenses(new_code: str):
    """Append a verified license code to licenses.json in GitHub.

    The desktop app reads this file on startup to validate free-tier codes.
    Raises if the file cannot be updated. Callers must not tell the user
    the licence is active unless this returns.
    """
    pat = app.config["GITHUB_PAT_WRITE"] or app.config["GITHUB_PAT"]
    if not pat:
        raise RuntimeError("No GitHub PAT configured for licence sync")

    current, sha = _get_licenses_json()

    if current is None:
        # File doesn't exist yet — create it with the first code
        current = {"codes": [], "updated": ""}

    if new_code not in current.get("codes", []):
        current.setdefault("codes", []).append(new_code)
        current["updated"] = datetime.utcnow().isoformat()
        _put_licenses_json(current, sha, f"Add code {new_code}")
    else:
        logger.info(f"Code {new_code} already in licenses.json — skipping")


def _remove_code_from_licenses(code: str):
    """Remove a revoked license code from licenses.json in GitHub."""
    pat = app.config["GITHUB_PAT_WRITE"] or app.config["GITHUB_PAT"]
    if not pat:
        raise RuntimeError("No GitHub PAT configured for licence sync")

    current, sha = _get_licenses_json()
    if current is None:
        return

    codes = current.get("codes", [])
    if code in codes:
        codes.remove(code)
        current["updated"] = datetime.utcnow().isoformat()
        _put_licenses_json(current, sha, f"Revoke code {code}")
    else:
        logger.info(f"Code {code} not in licenses.json — nothing to remove")


# ── Pro subscriptions ────────────────────────────────────────
# Professional is a Stripe subscription. Access is an email on
# allowlist.json in miketpl/node-control-registrations.
# That file is already live and contains hand-added beta users.
# This code only removes an email when a pro_subscriptions row says
# this system added it, the subscription that added it has ended,
# and no other subscription for that email is still active.

ACTIVE_SUB_STATUSES = ("active", "trialing")
ENDING_SUB_STATUSES = ("past_due", "unpaid", "canceled", "incomplete_expired")
PORTAL_STATUSES = ("active", "trialing", "past_due", "unpaid")
DOWNLOAD_PAGE_TTL = 30 * 60
DOWNLOAD_EMAIL_TTL = 24 * 3600


class AllowlistError(RuntimeError):
    pass


class AllowlistConflict(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _header_map(headers):
    if not headers:
        return {}
    try:
        return {key: value for key, value in headers.items()}
    except Exception:
        return {}


def _github_request(req, timeout=15, follow_redirects=True):
    """Return (status, headers, body). Does not follow redirects when asked not to."""
    try:
        if follow_redirects:
            opener_cm = urlopen(req, timeout=timeout)
        else:
            opener_cm = build_opener(_NoRedirect).open(req, timeout=timeout)
        with opener_cm as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            return status, _header_map(resp.headers), resp.read()
    except HTTPError as exc:
        raw = b""
        if exc.fp is not None:
            try:
                raw = exc.read()
            except Exception:
                raw = b""
        return exc.code, _header_map(exc.headers), raw


def _github_req(url, pat, accept="application/vnd.github+json", data=None, method=None):
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": accept,
        "User-Agent": "nodecontrol-license-api",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None and method is None:
        method = "PUT"
    return Request(url, data=data, headers=headers, method=method)


def _as_mapping(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return dict(obj)


def _stripe_id(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return _as_mapping(value).get("id") or ""


def _registrations_pat():
    """Token for allowlist.json. Prefer the dedicated PAT, else the existing write PAT."""
    pat = (app.config.get("GITHUB_PAT_REGISTRATIONS") or "").strip()
    if not pat:
        pat = (app.config.get("GITHUB_PAT_WRITE") or "").strip()
    if not pat:
        raise AllowlistError(
            "No GitHub token for the Pro allow-list. Set GITHUB_PAT_REGISTRATIONS, "
            "or reuse GITHUB_PAT_WRITE if that token has contents:write on "
            "miketpl/node-control-registrations."
        )
    return pat


def _allowlist_target():
    repo = (app.config.get("PRO_ALLOWLIST_REPO") or "").strip()
    path = (app.config.get("PRO_ALLOWLIST_PATH") or "").strip()
    if not repo or not path:
        raise AllowlistError("PRO_ALLOWLIST_REPO and PRO_ALLOWLIST_PATH must be set.")
    return repo, path


def _normalize_emails(emails):
    out = []
    seen = set()
    for item in emails or []:
        if not isinstance(item, str):
            continue
        norm = item.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def _get_allowlist():
    repo, path = _allowlist_target()
    status, _headers, body = _github_request(_github_req(
        f"https://api.github.com/repos/{repo}/contents/{path}?ref=main",
        _registrations_pat(),
    ))
    if status == 404:
        raise AllowlistError(
            f"Allow-list file {repo}/{path} was not found on main. "
            "Refusing to create a new file, because the live list must not be replaced."
        )
    if status != 200:
        raise AllowlistError(f"Could not read the Pro allow-list: HTTP {status}")
    payload = json.loads(body.decode("utf-8"))
    content = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
    if not isinstance(content, dict):
        raise AllowlistError("Pro allow-list JSON must be an object.")
    sha = payload.get("sha") or ""
    if not sha:
        raise AllowlistError("Pro allow-list response had no sha.")
    return content, sha


def _put_allowlist(content, sha, message):
    repo, path = _allowlist_target()
    encoded = base64.b64encode(
        json.dumps(content, indent=2).encode("utf-8")
    ).decode("utf-8")
    body = json.dumps({
        "message": message,
        "content": encoded,
        "sha": sha,
        "branch": "main",
    }).encode("utf-8")
    status, _headers, _resp = _github_request(_github_req(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        _registrations_pat(),
        data=body,
        method="PUT",
    ))
    if status == 409:
        raise AllowlistConflict()
    if status not in (200, 201):
        raise AllowlistError(f"Could not write the Pro allow-list: HTTP {status}")


def _mutate_allowlist(mutator, message):
    last_error = None
    for _attempt in range(4):
        doc, sha = _get_allowlist()
        if not mutator(doc):
            return doc
        try:
            _put_allowlist(doc, sha, message)
            return doc
        except AllowlistConflict as exc:
            last_error = exc
            logger.warning("Pro allow-list write conflicted. Retrying.")
    raise AllowlistError("Pro allow-list update conflicted too many times.") from last_error


def _allowlist_contains(email):
    doc, _sha = _get_allowlist()
    return email.strip().lower() in _normalize_emails(doc.get("allowed_emails") or [])


def _add_email_to_allowlist(email):
    """Add one subscriber. Other keys, including grace_period_days, stay as they are."""
    email = email.strip().lower()

    def mutator(doc):
        emails = _normalize_emails(doc.get("allowed_emails") or [])
        if email in emails:
            return False
        emails.append(email)
        doc["allowed_emails"] = emails
        return True

    _mutate_allowlist(mutator, f"Add Pro subscriber {email}")


def _remove_email_from_allowlist(email):
    email = email.strip().lower()

    def mutator(doc):
        emails = _normalize_emails(doc.get("allowed_emails") or [])
        if email not in emails:
            return False
        doc["allowed_emails"] = [item for item in emails if item != email]
        return True

    _mutate_allowlist(mutator, f"Remove Pro subscriber {email}")


def _get_pro_row_by_subscription(subscription_id):
    if not subscription_id:
        return None
    db = get_db()
    row = db.execute(
        "SELECT * FROM pro_subscriptions WHERE stripe_subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    db.close()
    return row


def _rows_for_email(email):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM pro_subscriptions WHERE email = ?",
        (email.strip().lower(),),
    ).fetchall()
    db.close()
    return rows


def _should_remove_from_allowlist(email, ending_subscription_id):
    """Remove only an email this system added for Stripe.

    A hand-added beta address has no added_to_allowlist flag, so a later
    subscription for that same address must not take it off the list.
    A second active subscription for an address we did add also keeps it.
    """
    rows = _rows_for_email(email)
    if not rows or not any(row["added_to_allowlist"] for row in rows):
        return False
    for row in rows:
        if row["stripe_subscription_id"] == ending_subscription_id:
            continue
        if row["status"] in ACTIVE_SUB_STATUSES:
            return False
    return True


def _upsert_pro_subscription(fields):
    now = datetime.utcnow().isoformat()
    subscription_id = fields["stripe_subscription_id"]
    db = get_db()
    existing = db.execute(
        "SELECT * FROM pro_subscriptions WHERE stripe_subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    if existing:
        added = 1 if existing["added_to_allowlist"] or fields.get("added_to_allowlist") else 0
        welcomed = existing["welcomed_at"] or fields.get("welcomed_at") or ""
        db.execute(
            """UPDATE pro_subscriptions SET
                email = ?, name = ?, stripe_customer_id = ?,
                stripe_checkout_session_id = ?, plan = ?, status = ?,
                cancel_at_period_end = ?, current_period_end = ?,
                added_to_allowlist = ?, welcomed_at = ?, updated_at = ?
               WHERE id = ?""",
            (
                fields.get("email") or existing["email"],
                fields.get("name") or existing["name"] or "",
                fields.get("stripe_customer_id") or existing["stripe_customer_id"] or "",
                fields.get("stripe_checkout_session_id") or existing["stripe_checkout_session_id"] or "",
                fields.get("plan") or existing["plan"] or "",
                fields.get("status") or existing["status"],
                1 if fields.get("cancel_at_period_end") else 0,
                fields.get("current_period_end") or existing["current_period_end"] or "",
                added,
                welcomed,
                now,
                existing["id"],
            ),
        )
    else:
        db.execute(
            """INSERT INTO pro_subscriptions (
                email, name, stripe_customer_id, stripe_subscription_id,
                stripe_checkout_session_id, plan, status, cancel_at_period_end,
                current_period_end, added_to_allowlist, welcomed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fields["email"],
                fields.get("name") or "",
                fields.get("stripe_customer_id") or "",
                subscription_id,
                fields.get("stripe_checkout_session_id") or "",
                fields.get("plan") or "",
                fields.get("status") or "",
                1 if fields.get("cancel_at_period_end") else 0,
                fields.get("current_period_end") or "",
                1 if fields.get("added_to_allowlist") else 0,
                fields.get("welcomed_at") or "",
                now,
                now,
            ),
        )
    db.commit()
    row = db.execute(
        "SELECT * FROM pro_subscriptions WHERE stripe_subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    db.close()
    return row


def _set_welcomed(row_id):
    now = datetime.utcnow().isoformat()
    db = get_db()
    db.execute(
        "UPDATE pro_subscriptions SET welcomed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, row_id),
    )
    db.commit()
    db.close()


def _period_end_iso(sub):
    end = sub.get("current_period_end")
    if not end:
        items = ((sub.get("items") or {}).get("data") or [])
        if items:
            end = items[0].get("current_period_end")
    if not end:
        return ""
    return datetime.utcfromtimestamp(int(end)).isoformat()


def _plan_from(sub, fallback=""):
    meta = sub.get("metadata") or {}
    plan = (meta.get("plan") or fallback or "").strip()
    if plan in ("monthly", "annual"):
        return plan
    price_id = ""
    items = ((sub.get("items") or {}).get("data") or [])
    if items:
        price = items[0].get("price") or {}
        price_id = price if isinstance(price, str) else (price.get("id") or "")
    if price_id and price_id == (app.config.get("STRIPE_PRICE_PRO_ANNUAL") or ""):
        return "annual"
    if price_id and price_id == (app.config.get("STRIPE_PRICE_PRO_MONTHLY") or ""):
        return "monthly"
    return "monthly"


def _customer_email_from_stripe(customer_id):
    if not customer_id or not (app.config.get("STRIPE_SECRET_KEY") or ""):
        return ""
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]
    customer = _as_mapping(stripe.Customer.retrieve(customer_id))
    return (customer.get("email") or "").strip().lower()


def _email_for_subscription(subscription_id, stripe_sub):
    row = _get_pro_row_by_subscription(subscription_id)
    if row and row["email"]:
        return row["email"]
    return _customer_email_from_stripe(_stripe_id((stripe_sub or {}).get("customer")))


def _send_mail(to_email, subject, text_body, html_body):
    cfg = app.config
    if not cfg.get("SMTP_USER") or not cfg.get("SMTP_PASS"):
        logger.error("SMTP not configured — email to %s was not sent", to_email)
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f'{cfg["SMTP_FROM_NAME"]} <{cfg["SMTP_FROM"]}>'
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as server:
            server.starttls()
            server.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            server.send_message(msg)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


def _send_pro_welcome(row):
    site = (app.config.get("SITE_URL") or "https://nodecontrol.io").rstrip("/")
    if row["plan"] == "annual":
        plan_text = "Professional, £255/year ex VAT (£21.25/mo billed annually, ex VAT, save 15%)"
    else:
        plan_text = "Professional, £25/month ex VAT"
    import licence_v1
    plain_key = ""
    try:
        plain_key = licence_v1.plaintext_for_subscription(row["stripe_subscription_id"])
    except Exception:
        logger.exception("Professional key was not added to the welcome email")
        raise
    key_text = ""
    if plain_key:
        key_text = (
            "Your Professional licence key:\n"
            f"{plain_key}\n\n"
            "In the app, open Welcome to Node Control and enter this key.\n"
            "If you lose it, ask for it again. The same key is sent.\n\n"
        )
    session_id = row["stripe_checkout_session_id"] or ""
    if session_id:
        download_text = f"{site}/pro-success.html?session_id={session_id}"
    else:
        mac = _make_download_token(
            row["email"], row["stripe_subscription_id"], "mac", DOWNLOAD_EMAIL_TTL
        )
        win = _make_download_token(
            row["email"], row["stripe_subscription_id"], "win", DOWNLOAD_EMAIL_TTL
        )
        download_text = (
            "macOS: https://api.nodecontrol.io/api/pro/download?token=" + mac + "\n"
            "Windows: https://api.nodecontrol.io/api/pro/download?token=" + win + "\n"
            "These links last 24 hours and only work while the subscription is active."
        )
    text = (
        f"Hi {row['name'] or 'there'},\n\n"
        "Your Node Control Professional subscription is active.\n"
        f"Plan: {plan_text}\n\n"
        f"{key_text}"
        "The subscription email is:\n"
        f"{row['email']}\n\n"
        "Download Pro:\n"
        f"{download_text}\n\n"
        "To cancel or update the card, request a link here:\n"
        f"{site}/#manage\n\n"
        "Cancelling stops the next renewal. Access continues until the end of the "
        "period already paid. After that the app blocks, once its 7-day offline "
        "grace runs out if it cannot check in.\n\n"
        "---\n"
        "Node Control by The Promised LAN\n"
        f"{site}\n"
    )
    html_body = (
        '<pre style="font-family: sans-serif; white-space: pre-wrap;">'
        + html.escape(text)
        + "</pre>"
    )
    return _send_mail(
        row["email"], "Your Node Control Professional subscription", text, html_body
    )


def _send_portal_email(email, portal_url):
    site = (app.config.get("SITE_URL") or "https://nodecontrol.io").rstrip("/")
    text = (
        "Hi,\n\n"
        "Use this link to cancel Node Control Professional or update the card:\n"
        f"{portal_url}\n\n"
        f"The link expires. If it does, request another from {site}/#manage\n\n"
        "---\n"
        "Node Control by The Promised LAN\n"
        f"{site}\n"
    )
    return _send_mail(
        email,
        "Manage your Node Control subscription",
        text,
        "<pre>" + html.escape(text) + "</pre>",
    )


def _legacy_allowlist_enabled():
    """0.9.40 allowlist.json writes. Off unless LEGACY_ALLOWLIST_SYNC is true."""
    raw = str(app.config.get("LEGACY_ALLOWLIST_SYNC") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _grant_pro_access(
    email, name, customer_id, subscription_id, session_id, plan, status,
    period_end, cancel_at_period_end,
):
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise AllowlistError("Stripe event had no customer email")
    if not subscription_id:
        raise AllowlistError("Stripe event had no subscription id")
    existing = _get_pro_row_by_subscription(subscription_id)
    if not _legacy_allowlist_enabled():
        # Checkout must not depend on GITHUB_PAT_REGISTRATIONS. The 0.9.41
        # app uses the NCP- key, not allowlist.json.
        ours = 1 if existing and existing["added_to_allowlist"] else 0
    elif existing and existing["added_to_allowlist"]:
        ours = 1
    else:
        # Decide before the GitHub write. An address already on the list
        # was put there by hand, or by an earlier subscription, and this
        # row must not claim it.
        ours = 0 if _allowlist_contains(email) else 1
    _upsert_pro_subscription({
        "email": email,
        "name": name or "",
        "stripe_customer_id": customer_id or "",
        "stripe_subscription_id": subscription_id,
        "stripe_checkout_session_id": session_id or "",
        "plan": plan,
        "status": status or "active",
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_end": period_end or "",
        "added_to_allowlist": ours,
    })
    if _legacy_allowlist_enabled() and ours:
        _add_email_to_allowlist(email)
    import licence_v1
    licence_v1.ensure_stripe_pro_key(subscription_id, email, plan)
    row = _get_pro_row_by_subscription(subscription_id)
    if not row["welcomed_at"]:
        if not _send_pro_welcome(row):
            raise RuntimeError("Welcome email was not sent")
        _set_welcomed(row["id"])
    return _get_pro_row_by_subscription(subscription_id)


def _end_pro_access(email, subscription_id, status, cancel_at_period_end, period_end):
    existing = _get_pro_row_by_subscription(subscription_id)
    if not existing:
        logger.error(
            "No pro_subscriptions row for %s. The allow-list was not changed.",
            subscription_id,
        )
        return
    email = (email or existing["email"] or "").strip().lower()
    removed = False
    try:
        if (
            _legacy_allowlist_enabled()
            and email
            and _should_remove_from_allowlist(email, subscription_id)
        ):
            _remove_email_from_allowlist(email)
            removed = True
        _upsert_pro_subscription({
            "email": email,
            "name": existing["name"],
            "stripe_customer_id": existing["stripe_customer_id"],
            "stripe_subscription_id": subscription_id,
            "stripe_checkout_session_id": existing["stripe_checkout_session_id"],
            "plan": existing["plan"],
            "status": status or "canceled",
            "cancel_at_period_end": cancel_at_period_end,
            "current_period_end": period_end or existing["current_period_end"],
            "added_to_allowlist": existing["added_to_allowlist"],
        })
    except Exception:
        if removed:
            try:
                _add_email_to_allowlist(email)
            except Exception:
                logger.exception("Could not restore %s on the allow-list", email)
        raise


def _load_subscription(subscription_id):
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]
    return _as_mapping(stripe.Subscription.retrieve(subscription_id))


def _handle_checkout_completed(session):
    session = _as_mapping(session)
    if session.get("mode") not in (None, "subscription"):
        return
    if session.get("payment_status") not in ("paid", "no_payment_required"):
        logger.info("Checkout %s is not paid yet", session.get("id"))
        return
    subscription_id = _stripe_id(session.get("subscription"))
    if not subscription_id:
        raise RuntimeError("Checkout session has no subscription")
    sub = _load_subscription(subscription_id)
    details = session.get("customer_details") or {}
    email = (session.get("customer_email") or details.get("email") or "").strip().lower()
    _grant_pro_access(
        email=email,
        name=details.get("name") or "",
        customer_id=_stripe_id(session.get("customer")),
        subscription_id=subscription_id,
        session_id=session.get("id") or "",
        plan=_plan_from(sub, (session.get("metadata") or {}).get("plan")),
        status=sub.get("status") or "active",
        period_end=_period_end_iso(sub),
        cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
    )


def _handle_invoice_paid(invoice):
    invoice = _as_mapping(invoice)
    subscription_id = _stripe_id(invoice.get("subscription"))
    if not subscription_id:
        return
    sub = _load_subscription(subscription_id)
    if sub.get("status") not in ACTIVE_SUB_STATUSES:
        raise RuntimeError("Paid invoice did not leave the subscription active")
    existing = _get_pro_row_by_subscription(subscription_id)
    email = (invoice.get("customer_email") or "").strip().lower()
    if not email:
        email = _email_for_subscription(subscription_id, sub)
    _grant_pro_access(
        email=email,
        name=(existing["name"] if existing else ""),
        customer_id=_stripe_id(invoice.get("customer")) or _stripe_id(sub.get("customer")),
        subscription_id=subscription_id,
        session_id=(existing["stripe_checkout_session_id"] if existing else ""),
        plan=_plan_from(sub, existing["plan"] if existing else ""),
        status=sub.get("status") or "active",
        period_end=_period_end_iso(sub),
        cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
    )


def _handle_subscription_change(sub, deleted=False):
    sub = _as_mapping(sub)
    subscription_id = sub.get("id") or ""
    status = "canceled" if deleted else (sub.get("status") or "")
    cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    period_end = _period_end_iso(sub)
    email = _email_for_subscription(subscription_id, sub)
    if status in ACTIVE_SUB_STATUSES:
        # cancel_at_period_end stays active until Stripe ends the subscription.
        existing = _get_pro_row_by_subscription(subscription_id)
        if not existing:
            raise RuntimeError(f"No local row for active subscription {subscription_id}")
        if _legacy_allowlist_enabled() and existing["added_to_allowlist"] and email:
            _add_email_to_allowlist(email)
        _upsert_pro_subscription({
            "email": email or existing["email"],
            "stripe_subscription_id": subscription_id,
            "status": status,
            "cancel_at_period_end": cancel_at_period_end,
            "current_period_end": period_end,
            "added_to_allowlist": existing["added_to_allowlist"],
            "stripe_customer_id": _stripe_id(sub.get("customer")) or existing["stripe_customer_id"],
            "plan": _plan_from(sub, existing["plan"]),
        })
        return
    if status not in ENDING_SUB_STATUSES and not deleted:
        existing = _get_pro_row_by_subscription(subscription_id)
        if existing:
            _upsert_pro_subscription({
                "email": existing["email"],
                "stripe_subscription_id": subscription_id,
                "status": status or existing["status"],
                "cancel_at_period_end": cancel_at_period_end,
                "current_period_end": period_end,
                "added_to_allowlist": existing["added_to_allowlist"],
            })
        return
    _end_pro_access(email, subscription_id, status or "canceled", cancel_at_period_end, period_end)


def _handle_payment_failed(invoice):
    invoice = _as_mapping(invoice)
    subscription_id = _stripe_id(invoice.get("subscription"))
    if not subscription_id:
        return
    sub = _load_subscription(subscription_id)
    if sub.get("status") in ENDING_SUB_STATUSES:
        _handle_subscription_change(sub, deleted=False)
        return
    logger.info(
        "Payment failed for %s but status is %s. Access stays.",
        subscription_id,
        sub.get("status"),
    )


def _event_processed(event_id):
    db = get_db()
    row = db.execute(
        "SELECT event_id FROM stripe_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    db.close()
    return row is not None


def _mark_event(event_id, event_type):
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO stripe_events (event_id, event_type, processed_at) VALUES (?, ?, ?)",
        (event_id, event_type, datetime.utcnow().isoformat()),
    )
    db.commit()
    db.close()


def _download_serializer():
    secret = (app.config.get("PRO_DOWNLOAD_SECRET") or "").strip()
    if not secret:
        secret = (app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("PRO_DOWNLOAD_SECRET is not set")
    return URLSafeTimedSerializer(secret, salt="nodecontrol-pro-download")


def _make_download_token(email, subscription_id, platform, ttl_seconds=DOWNLOAD_PAGE_TTL):
    payload = {
        "email": email,
        "sub": subscription_id,
        "platform": platform,
        "exp": int(time.time()) + int(ttl_seconds),
    }
    return _download_serializer().dumps(payload)


def _read_download_token(token):
    ceiling = int(app.config.get("PRO_DOWNLOAD_TOKEN_MAX_AGE") or (7 * 24 * 3600))
    try:
        data = _download_serializer().loads(token, max_age=ceiling)
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    if int(data.get("exp") or 0) < int(time.time()):
        return None, "expired"
    return data, ""


def _pro_asset_redirect(platform):
    import licence_v1
    pat = licence_v1.releases_pat()
    repo = (app.config.get("PRO_RELEASES_REPO") or "").strip()
    if not pat or not repo:
        raise RuntimeError("RELEASES_READ_PAT or PRO_RELEASES_REPO is not set")
    ext = ".dmg" if platform == "mac" else ".exe"
    status, _headers, body = _github_request(_github_req(
        f"https://api.github.com/repos/{repo}/releases/latest",
        pat,
    ))
    if status != 200:
        raise RuntimeError(f"Pro releases/latest returned HTTP {status}")
    release = json.loads(body.decode("utf-8"))
    asset = None
    for item in release.get("assets") or []:
        if (item.get("name") or "").lower().endswith(ext):
            asset = item
            break
    if not asset:
        raise RuntimeError(f"No {ext} asset on the latest Pro release")
    status, headers, _body = _github_request(
        _github_req(
            f"https://api.github.com/repos/{repo}/releases/assets/{asset['id']}",
            pat,
            accept="application/octet-stream",
        ),
        follow_redirects=False,
    )
    if status not in (301, 302, 303, 307, 308):
        raise RuntimeError(f"Pro asset redirect returned HTTP {status}")
    location = ""
    for key, value in headers.items():
        if str(key).lower() == "location":
            location = value
    if not location or pat in location:
        raise RuntimeError("Pro asset redirect was missing a usable URL")
    return location


@app.route("/api/checkout", methods=["POST"])
def pro_checkout():
    """Start a Professional subscription Checkout Session."""
    data = request.get_json(silent=True) or {}
    plan = (data.get("plan") or "").strip()
    if plan not in ("monthly", "annual"):
        return jsonify({"error": "plan must be monthly or annual"}), 400
    price = (
        app.config.get("STRIPE_PRICE_PRO_MONTHLY")
        if plan == "monthly"
        else app.config.get("STRIPE_PRICE_PRO_ANNUAL")
    )
    if not (app.config.get("STRIPE_SECRET_KEY") or "").strip() or not (price or "").strip():
        logger.error("Stripe checkout is not configured")
        return jsonify({"error": "Checkout is not configured"}), 503
    email = (data.get("email") or "").strip().lower()
    site = (app.config.get("SITE_URL") or "https://nodecontrol.io").rstrip("/")
    params = {
        "mode": "subscription",
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": site + "/pro-success.html?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": site + "/#pricing",
        "automatic_tax": {"enabled": True},
        "billing_address_collection": "required",
        "tax_id_collection": {"enabled": True},
        "metadata": {"plan": plan},
        "subscription_data": {"metadata": {"plan": plan}},
    }
    if email and "@" in email:
        params["customer_email"] = email
    try:
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]
        session = _as_mapping(stripe.checkout.Session.create(**params))
    except Exception:
        logger.exception("Stripe checkout session failed")
        return jsonify({"error": "Checkout could not be started"}), 502
    url = session.get("url") or ""
    if not url:
        return jsonify({"error": "Checkout could not be started"}), 502
    return jsonify({"url": url})


@app.route("/api/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Stripe subscription events. Signature required. Fail closed so Stripe retries."""
    secret = (app.config.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not set")
        return jsonify({"error": "Webhook is not configured"}), 503
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        logger.warning("Rejected Stripe webhook: %s", exc)
        return jsonify({"error": "Invalid signature"}), 400
    event = _as_mapping(event)
    event_id = event.get("id") or ""
    event_type = event.get("type") or ""
    if not event_id:
        return jsonify({"error": "Event has no id"}), 400
    if _event_processed(event_id):
        return jsonify({"received": True})
    try:
        obj = (event.get("data") or {}).get("object") or {}
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(obj)
        elif event_type == "invoice.paid":
            _handle_invoice_paid(obj)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_change(obj, deleted=False)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_change(obj, deleted=True)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(obj)
        _mark_event(event_id, event_type)
    except Exception:
        logger.exception("Stripe webhook %s (%s) failed", event_id, event_type)
        return jsonify({"error": "Handler failed"}), 500
    return jsonify({"received": True})


@app.route("/api/pro/session", methods=["GET"])
def pro_session():
    """Success page: confirm the Checkout Session is paid, then mint download tokens."""
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not (app.config.get("STRIPE_SECRET_KEY") or "").strip():
        return jsonify({"error": "Checkout is not configured"}), 503
    try:
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]
        session = _as_mapping(stripe.checkout.Session.retrieve(session_id))
    except Exception:
        logger.exception("Could not retrieve checkout session")
        return jsonify({"error": "Could not read that checkout session"}), 400
    paid = session.get("payment_status") in ("paid", "no_payment_required")
    if session.get("status") != "complete" or not paid:
        return jsonify({"status": "unpaid"})
    subscription_id = _stripe_id(session.get("subscription"))
    row = _get_pro_row_by_subscription(subscription_id) if subscription_id else None
    if not row or row["status"] not in ACTIVE_SUB_STATUSES:
        return jsonify({"status": "processing"})
    try:
        downloads = {
            "mac": _make_download_token(row["email"], row["stripe_subscription_id"], "mac"),
            "win": _make_download_token(row["email"], row["stripe_subscription_id"], "win"),
        }
    except Exception:
        logger.exception("Could not sign download tokens")
        return jsonify({"error": "Downloads are not configured"}), 503
    licence_key = None
    try:
        import licence_v1
        licence_key = licence_v1.reveal_pro_key_for_session(row["stripe_subscription_id"])
    except Exception:
        logger.exception("Could not reveal the Professional key on the success page")
    return jsonify({
        "status": "active",
        "email": row["email"],
        "plan": row["plan"],
        "downloads": downloads,
        "licence_key": licence_key,
    })


@app.route("/api/pro/download", methods=["GET"])
def pro_download():
    """Redeem a short-lived token for a redirect to the private Pro installer."""
    data, err = _read_download_token(request.args.get("token", ""))
    if err == "expired":
        return jsonify({
            "error": "This download link has expired. Open the link in your email again.",
        }), 403
    if not data or data.get("platform") not in ("mac", "win"):
        return jsonify({"error": "Invalid download link"}), 403
    row = _get_pro_row_by_subscription(data.get("sub"))
    if (
        not row
        or row["email"] != data.get("email")
        or row["status"] not in ACTIVE_SUB_STATUSES
    ):
        return jsonify({"error": "This subscription is not active"}), 403
    try:
        location = _pro_asset_redirect(data["platform"])
    except Exception:
        logger.exception("Pro download failed")
        return jsonify({"error": "The installer is not available right now"}), 503
    return redirect(location, code=302)


@app.route("/api/portal", methods=["POST"])
def pro_portal():
    """Email a Customer Portal link. The response does not say whether the address exists."""
    generic = {
        "success": True,
        "message": "If that address has a Professional subscription, we sent a link to manage it.",
    }
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify(generic)
    try:
        db = get_db()
        row = db.execute(
            """SELECT stripe_customer_id FROM pro_subscriptions
               WHERE email = ?
                 AND status IN ('active', 'trialing', 'past_due', 'unpaid')
                 AND stripe_customer_id != ''
               ORDER BY id DESC LIMIT 1""",
            (email,),
        ).fetchone()
        db.close()
        if not row or not (app.config.get("STRIPE_SECRET_KEY") or "").strip():
            if row and not (app.config.get("STRIPE_SECRET_KEY") or "").strip():
                logger.error("STRIPE_SECRET_KEY is not set")
            return jsonify(generic)
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]
        site = (app.config.get("SITE_URL") or "https://nodecontrol.io").rstrip("/")
        portal = _as_mapping(stripe.billing_portal.Session.create(
            customer=row["stripe_customer_id"],
            return_url=site + "/#manage",
        ))
        url = portal.get("url") or ""
        if url:
            sent = _send_portal_email(email, url)
            if not sent:
                logger.error("Portal link for a subscriber was not emailed")
    except Exception:
        logger.exception("Customer portal link failed")
    return jsonify(generic)



# ── API Routes ───────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint. Confirms the process is up and SQLite answers."""
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
        db.close()
    except Exception:
        logger.exception("Health check could not read the licence database")
        return jsonify({
            "status": "error",
            "service": "nodecontrol-license-api",
            "database": "unavailable",
        }), 503
    return jsonify({
        "status": "ok",
        "service": "nodecontrol-license-api",
        "database": "ok",
    })


@app.route("/api/request-access", methods=["POST"])
def request_access():
    """
    Step 1: User submits their details to request free access.
    Generates a verification code, emails it, and stores the pending license.
    """
    import licence_v1
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    if licence_v1.is_free_paused():
        return licence_v1.free_paused_response()

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    company = (data.get("company") or "").strip()
    platform = (data.get("platform") or "").strip()
    attr = clean_attribution(data)

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    if "@" not in email or "." not in email:
        return jsonify({"error": "Invalid email address"}), 400

    db = get_db()

    # Check if there's already a pending/active license for this email
    existing = db.execute(
        "SELECT * FROM licenses WHERE email = ? AND tier = 'free' ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()

    if existing and existing["status"] == "active":
        db.close()
        return jsonify({
            "error": (
                "This email already has a licence. Use a different email address, "
                f"or contact {SUPPORT_EMAIL} to have the old licence revoked."
            ),
            "already_active": True,
        }), 409

    # Generate codes
    verify_code = generate_verify_code()
    download_code = generate_code()
    now = datetime.utcnow().isoformat()
    ip = request.remote_addr or ""
    pending_marker = f"PENDING:{verify_code}"

    # Remember enough to undo this write if the email never goes out.
    # A pending row whose code was never emailed must not be what a retry sees.
    inserted_id = None
    previous = dict(existing) if existing and existing["status"] == "pending" else None

    if previous:
        # A retry without attribution keeps what the first attempt recorded.
        db.execute("""
            UPDATE licenses SET
                name = ?, company = ?, platform = ?,
                code = ?, created_at = ?, verified_at = ?, ip_address = ?,
                utm_source = COALESCE(NULLIF(?, ''), utm_source),
                utm_medium = COALESCE(NULLIF(?, ''), utm_medium),
                utm_campaign = COALESCE(NULLIF(?, ''), utm_campaign),
                referrer = COALESCE(NULLIF(?, ''), referrer),
                landing_page = COALESCE(NULLIF(?, ''), landing_page)
            WHERE id = ?
        """, (name, company, platform, download_code, now, pending_marker, ip,
              attr["utm_source"], attr["utm_medium"], attr["utm_campaign"],
              attr["referrer"], attr["landing_page"], previous["id"]))
    else:
        cursor = db.execute("""
            INSERT INTO licenses (code, name, email, company, platform, tier, status, created_at, verified_at, ip_address,
                                  utm_source, utm_medium, utm_campaign, referrer, landing_page)
            VALUES (?, ?, ?, ?, ?, 'free', 'pending', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (download_code, name, email, company, platform, now, pending_marker, ip,
              attr["utm_source"], attr["utm_medium"], attr["utm_campaign"],
              attr["referrer"], attr["landing_page"]))
        inserted_id = cursor.lastrowid

    db.commit()
    db.close()

    email_sent = send_verification_email(email, name, verify_code, download_code)
    if not email_sent:
        db = get_db()
        if inserted_id is not None:
            db.execute("DELETE FROM licenses WHERE id = ?", (inserted_id,))
        elif previous:
            db.execute("""
                UPDATE licenses SET
                    name = ?, company = ?, platform = ?,
                    code = ?, created_at = ?, verified_at = ?, ip_address = ?,
                    utm_source = ?, utm_medium = ?, utm_campaign = ?,
                    referrer = ?, landing_page = ?
                WHERE id = ?
            """, (
                previous["name"], previous["company"], previous["platform"],
                previous["code"], previous["created_at"], previous["verified_at"],
                previous["ip_address"],
                previous["utm_source"], previous["utm_medium"], previous["utm_campaign"],
                previous["referrer"], previous["landing_page"],
                previous["id"],
            ))
        db.commit()
        db.close()
        logger.error("Verification email failed for %s; pending licence was not kept", email)
        return jsonify({"success": False, "error": EMAIL_SEND_ERROR}), 502

    return jsonify({
        "success": True,
        "message": "Verification code sent to your email. Please check your inbox.",
        "email_sent": True,
        # In development, include the code for testing (remove in production)
        **({"_debug_verify_code": verify_code} if app.debug else {}),
    })


@app.route("/api/verify", methods=["POST"])
def verify_code():
    """
    Step 2: User enters the 6-digit verification code from their email.
    If valid, activates the license and returns the download code.
    """
    import licence_v1
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    if licence_v1.is_free_paused():
        return licence_v1.free_paused_response()

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    if not email or not code:
        return jsonify({"error": "Email and verification code are required"}), 400

    db = get_db()

    # Find the pending license for this email
    license_row = db.execute(
        "SELECT * FROM licenses WHERE email = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()

    if not license_row:
        db.close()
        return jsonify({"error": "No pending request found for this email"}), 404

    # Check if the verify code matches
    stored_verify = license_row["verified_at"] or ""
    if not stored_verify.startswith("PENDING:"):
        db.close()
        return jsonify({"error": "Invalid state. Please request a new code."}), 400

    expected_code = stored_verify.replace("PENDING:", "")
    if code != expected_code:
        db.close()
        return jsonify({"error": "Invalid verification code. Please try again."}), 400

    # Check expiry
    created = datetime.fromisoformat(license_row["created_at"])
    expiry = created + timedelta(hours=app.config["CODE_EXPIRY_HOURS"])
    if datetime.utcnow() > expiry:
        db.close()
        return jsonify({"error": "Verification code expired. Please request a new one."}), 400

    download_code = license_row["code"]
    license_id = license_row["id"]
    db.close()

    # Publish first. The row stays pending until GitHub has the code, so a
    # failure leaves the same 6-digit code usable and the page never shows
    # an NC- code the app would reject.
    try:
        _add_code_to_licenses(download_code)
    except Exception as exc:
        logger.error(f"License GitHub sync failed: {exc}")
        return jsonify({"success": False, "error": LICENCE_SYNC_ERROR}), 502

    now = datetime.utcnow().isoformat()
    db = get_db()
    db.execute("""
        UPDATE licenses SET status = 'active', verified_at = ?
        WHERE id = ? AND status = 'pending'
    """, (now, license_id))
    db.commit()
    updated = db.execute(
        "SELECT status FROM licenses WHERE id = ?", (license_id,)
    ).fetchone()
    db.close()

    if not updated or updated["status"] != "active":
        logger.error("Licence %s was published to GitHub but the database row was not activated", license_id)
        return jsonify({"success": False, "error": LICENCE_SYNC_ERROR}), 502

    return jsonify({
        "success": True,
        "download_code": download_code,
        "tier": "free",
        "message": "Email verified! Here's your download code.",
    })


@app.route("/api/redeem", methods=["POST"])
def redeem():
    """
    Step 3: User enters their download code (NC-XXXX-XXXX) to get download links.
    Validates the code, increments download count, returns URLs.
    """
    import licence_v1
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    if licence_v1.is_free_paused():
        return licence_v1.free_paused_response()

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    code = (data.get("code") or "").strip().upper().replace(" ", "-")

    if not code:
        return jsonify({"error": "Please enter a download code"}), 400

    db = get_db()

    license_row = db.execute(
        "SELECT * FROM licenses WHERE code = ? AND status = 'active'",
        (code,)
    ).fetchone()

    if not license_row:
        db.close()
        return jsonify({"error": "Invalid or inactive code. Please check and try again."}), 404

    # Increment download count and record redemption
    now = datetime.utcnow().isoformat()
    new_count = (license_row["download_count"] or 0) + 1
    db.execute("""
        UPDATE licenses SET download_count = ?, redeemed_at = ?
        WHERE id = ?
    """, (new_count, now, license_row["id"]))
    db.commit()
    db.close()

    tier = license_row["tier"]
    try:
        downloads = licence_v1.free_redeem_links(license_row["id"])
    except Exception:
        logger.exception("Could not sign free download links")
        return jsonify({"success": False, "error": "Downloads are not configured"}), 503
    return jsonify({
        "success": True,
        "tier": tier,
        "label": f"{tier.title()} Edition",
        "downloads": downloads,
        "download_count": new_count,
    })


@app.route("/api/download-event", methods=["POST"])
def download_event():
    """Record that the site started or offered an installer download.

    The site sends this with navigator.sendBeacon as text/plain, so the body
    is parsed with force=True. Only an active code is recorded. The response
    is always 204, so the endpoint cannot be used to test whether a code exists.
    """
    raw = request.get_data(cache=True) or b""
    if len(raw) > DOWNLOAD_EVENT_BODY_LIMIT:
        return ("", 204)
    if not _download_event_ip_allowed(_client_ip()):
        return ("", 204)

    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return ("", 204)
    code = str(data.get("code") or "").strip().upper()[:32]
    platform = str(data.get("platform") or "").strip().lower()
    kind = str(data.get("kind") or "").strip().lower()
    if platform not in ("mac", "win") or kind not in ("auto", "click"):
        return ("", 204)

    db = get_db()
    row = db.execute(
        "SELECT id FROM licenses WHERE code = ? AND status = 'active'", (code,)
    ).fetchone()
    if row:
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        count = db.execute(
            "SELECT COUNT(*) AS c FROM download_events WHERE license_id = ? AND created_at >= ?",
            (row["id"], cutoff),
        ).fetchone()["c"]
        if count < DOWNLOAD_EVENT_LICENCE_CAP:
            db.execute(
                "INSERT INTO download_events (license_id, platform, kind, created_at) VALUES (?, ?, ?, ?)",
                (row["id"], platform, kind, datetime.utcnow().isoformat()),
            )
            db.commit()
    db.close()
    return ("", 204)


# ── Admin Routes ─────────────────────────────────────────────

@app.route("/api/admin/licenses", methods=["GET"])
@require_admin
def list_licenses():
    """List all licenses with optional filtering."""
    status = request.args.get("status")
    tier = request.args.get("tier")
    search = request.args.get("search")

    db = get_db()
    query = "SELECT * FROM licenses WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if search:
        query += " AND (email LIKE ? OR name LIKE ? OR company LIKE ? OR code LIKE ?)"
        params.extend([f"%{search}%"] * 4)

    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()
    db.close()

    return jsonify({
        "licenses": [dict(row) for row in rows],
        "total": len(rows),
    })


@app.route("/api/admin/licenses/<int:license_id>", methods=["DELETE"])
@require_admin
def revoke_license(license_id):
    """Revoke a license in GitHub and SQLite together.

    GitHub is updated first. If that fails, SQLite is left as it was, so
    the database never says revoked while the app still accepts the code.
    """
    db = get_db()
    row = db.execute(
        "SELECT id, code, status FROM licenses WHERE id = ?", (license_id,)
    ).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "Licence not found"}), 404
    code = row["code"]
    db.close()

    try:
        _remove_code_from_licenses(code)
    except Exception as exc:
        logger.error(f"License GitHub revoke failed: {exc}")
        return jsonify({
            "success": False,
            "error": (
                "Licence was not revoked. The GitHub licence list could not "
                "be updated, so the database was left unchanged."
            ),
        }), 502

    db = get_db()
    try:
        db.execute(
            "UPDATE licenses SET status = 'revoked' WHERE id = ?", (license_id,)
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"SQLite revoke failed after GitHub removal: {exc}")
        try:
            _add_code_to_licenses(code)
        except Exception as restore_exc:
            logger.error(f"Could not restore {code} to GitHub after a database failure: {restore_exc}")
            db.close()
            return jsonify({
                "success": False,
                "error": (
                    "Licence list update failed part-way. The code was removed "
                    "from GitHub but the database could not be marked revoked, "
                    "and putting the code back also failed. Check both before retrying."
                ),
            }), 500
        db.close()
        return jsonify({
            "success": False,
            "error": (
                "Licence was not revoked. The database update failed and the "
                "GitHub licence list was restored."
            ),
        }), 502
    db.close()

    return jsonify({"success": True, "message": "License revoked"})


@app.route("/api/admin/stats", methods=["GET"])
@require_admin
def stats():
    """Get license statistics."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM licenses").fetchone()["c"]
    active = db.execute("SELECT COUNT(*) as c FROM licenses WHERE status = 'active'").fetchone()["c"]
    pending = db.execute("SELECT COUNT(*) as c FROM licenses WHERE status = 'pending'").fetchone()["c"]
    total_downloads = db.execute("SELECT SUM(download_count) as c FROM licenses").fetchone()["c"] or 0

    # Optional window for the weekly report: ?since=2026-10-12&until=2026-10-19 (UTC dates).
    since = _utc_day(request.args.get("since"), "0000-01-01")
    until = _utc_day(request.args.get("until"), "9999-12-31")
    if since is None or until is None:
        db.close()
        return jsonify({"error": "since and until must be YYYY-MM-DD"}), 400
    by_source = [dict(r) for r in db.execute("""
        SELECT
            CASE
                WHEN utm_source != '' THEN utm_source
                WHEN referrer != '' THEN 'ref:' || referrer
                ELSE '(direct)'
            END AS source,
            COALESCE(NULLIF(utm_medium, ''), '-') AS medium,
            COUNT(*) AS requested,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS verified,
            SUM(CASE WHEN download_count > 0 THEN 1 ELSE 0 END) AS redeemed
        FROM licenses
        WHERE tier = 'free' AND created_at >= ? AND created_at < ?
        GROUP BY source, medium
        ORDER BY requested DESC
    """, (since, until))]
    download_events = [dict(r) for r in db.execute("""
        SELECT platform, kind, COUNT(*) AS events, COUNT(DISTINCT license_id) AS licences
        FROM download_events
        WHERE created_at >= ? AND created_at < ?
        GROUP BY platform, kind
        ORDER BY platform, kind
    """, (since, until))]
    db.close()

    return jsonify({
        "total_licenses": total,
        "active": active,
        "pending": pending,
        "total_downloads": total_downloads,
        "window": {"since": since, "until": until},
        "by_source": by_source,
        "download_events": download_events,
    })


# ── Init & Run ───────────────────────────────────────────────
with app.app_context():
    init_db()
    migrate_db()
    import licence_v1
    licence_v1.register(app)

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
