"""Token-free licence API for Node Control 0.9.41.

The contract is ENDPOINTS.md. Paths are under /api/v1. The desktop app
sends a licence key and a random install id. It holds no server secret.

Imported by app.py after the database helpers exist. This module does not
import app at load time, so migrate_db can load V1_SCHEMA without a cycle.
"""

import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import g, jsonify, redirect, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
BODY_LIMIT = 16 * 1024
MOVE_LIMIT = 2
MOVE_WINDOW = timedelta(days=30)
CODE_TTL_SECONDS = 900
CODE_MAX_ATTEMPTS = 5
GRACE_DAYS = 7
FLAG_CACHE_SECONDS = 10
RELEASE_CACHE_SECONDS = 60
FREE_LINK_TTL = 30 * 60
# First-install links for a hand-added Professional key. The app updates itself after that.
PRO_BETA_LINK_TTL = 7 * 24 * 3600
REVEAL_TTL = 24 * 3600
ASSET_URL_TTL = 300
MAINTENANCE_RETRY = 300
PAUSED_RETRY = 3600

FREE_KEY_RE = re.compile(r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
PRO_KEY_RE = re.compile(r"^NCP-[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){3}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
UA_RE = re.compile(
    r"^NodeControl/(\d+\.\d+\.\d+) \((free|pro|ai); (mac|win); (arm64|x86_64)\)$"
)
INSTALL_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
TASK_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
SESSION_RE = re.compile(r"^[0-9a-f]{16}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TASK_ALLOW = {
    "health_checks",
    "l2_topologies",
    "l3_topologies",
    "wan_topologies",
    "ping_scans",
    "config_pushes",
    "config_backups",
    "file_transfers",
    "packet_captures",
    "library_updates",
    "config_from_file",
    "save_configs",
    "interface_config_pushes",
    "scripts_run",
    # Keys match controllers/tasks.py in the app.
    "config_compliance_audits",
    "config_compliance_remediations",
    "hostname_refreshes",
    "device_type_verifications",
    "variable_discoveries",
    "ise_password_changes",
    "find_device_searches",
}
DROP_FIELDS = {"user_name", "company", "hostname", "machine_id", "machine_hash"}
FLAG_KEYS = (
    "free_downloads_paused",
    "free_paused_message",
    "maintenance",
    "min_supported_version_free",
    "min_supported_version_pro",
)
PAUSED_MESSAGE = (
    "Node Control Free downloads are temporarily paused while we ship an update "
    "(v0.9.41). Please check back soon."
)

# Checked in this order. Each window is its own bucket: the key includes
# the scope and the window length. The daily window and the 00:00 UTC
# hour both start at the same second, so a shared name would count
# one request twice during that hour.
LIMITS = {
    "activate": (("key", 10, 3600), ("ip", 30, 3600)),
    "licence-check": (("key", 30, 3600), ("ip", 60, 3600)),
    "deactivate": (("key", 5, 3600), ("ip", 20, 3600)),
    "move": (("key", 3, 3600), ("key-day", 5, 86400), ("ip", 10, 3600)),
    "move-confirm": (("key", 10, 3600), ("ip", 20, 3600)),
    "update-check": (("key", 30, 3600), ("ip", 120, 3600)),
    "download": (("key", 10, 3600), ("key-day", 30, 86400), ("ip", 30, 3600)),
    "register": (("key", 3, 86400), ("ip", 5, 3600)),
    "telemetry": (("install", 60, 3600), ("ip", 300, 3600)),
    "telemetry-delete": (("key", 3, 86400), ("ip", 10, 3600)),
    "resend": (("email", 3, 3600), ("ip", 10, 3600)),
    "resend-confirm": (("email", 10, 3600), ("ip", 20, 3600)),
    "free-download": (("licence", 10, 3600), ("ip", 30, 3600)),
    # Same numbers as a Free installer link. A separate name so the counters do not mix.
    "pro-download": (("licence", 10, 3600), ("ip", 30, 3600)),
    # One click starts checkout. Polling the result is a separate counter.
    "app-checkout": (("install", 10, 3600), ("ip", 20, 3600)),
    # The app polls about every 5 seconds for up to 30 minutes (about 360 calls).
    "purchase-status": (("install", 600, 3600), ("ip", 1200, 3600)),
}

V1_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS pro_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_hash TEXT UNIQUE NOT NULL,
        key_last4 TEXT NOT NULL,
        reveal_blob TEXT,
        email TEXT NOT NULL,
        subscription_id TEXT UNIQUE,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        plan TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        revoked_at TEXT DEFAULT '',
        reveal_until TEXT DEFAULT '',
        free_license_id INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pro_keys_email ON pro_keys(email)",
    """
    CREATE TABLE IF NOT EXISTS purchase_intents (
        id TEXT PRIMARY KEY,
        free_license_id INTEGER NOT NULL,
        install_id TEXT NOT NULL,
        plan TEXT NOT NULL,
        status TEXT NOT NULL,
        stripe_session_id TEXT DEFAULT '',
        pro_key_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_purchase_intents_licence
    ON purchase_intents(free_license_id, install_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licence_kind TEXT NOT NULL,
        licence_ref INTEGER NOT NULL,
        install_id TEXT NOT NULL,
        platform TEXT DEFAULT '',
        arch TEXT DEFAULT '',
        activated_at TEXT NOT NULL,
        last_seen_at TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 0,
        UNIQUE(licence_kind, licence_ref, install_id)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_one_active
    ON devices(licence_kind, licence_ref) WHERE active = 1
    """,
    """
    CREATE TABLE IF NOT EXISTS device_moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licence_kind TEXT NOT NULL,
        licence_ref INTEGER NOT NULL,
        from_install_id TEXT DEFAULT '',
        to_install_id TEXT NOT NULL,
        moved_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_device_moves_recent
    ON device_moves(licence_kind, licence_ref, moved_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS email_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purpose TEXT NOT NULL,
        licence_kind TEXT DEFAULT '',
        licence_ref INTEGER DEFAULT 0,
        email TEXT DEFAULT '',
        code_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licence_kind TEXT NOT NULL,
        licence_ref INTEGER NOT NULL,
        install_id TEXT NOT NULL,
        registration_token TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        org TEXT DEFAULT '',
        role TEXT DEFAULT '',
        app_version TEXT DEFAULT '',
        os_family TEXT DEFAULT '',
        os_major TEXT DEFAULT '',
        arch TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(licence_kind, licence_ref, install_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS telemetry_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licence_ref INTEGER NOT NULL,
        licence_kind TEXT NOT NULL,
        install_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        tier TEXT DEFAULT '',
        app_version TEXT DEFAULT '',
        os_family TEXT DEFAULT '',
        os_major TEXT DEFAULT '',
        arch TEXT DEFAULT '',
        session_start_date TEXT DEFAULT '',
        duration_s INTEGER DEFAULT 0,
        connections_opened INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        tasks_json TEXT DEFAULT '{}',
        first_received_at TEXT NOT NULL,
        last_received_at TEXT NOT NULL,
        UNIQUE(install_id, session_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_telemetry_licence
    ON telemetry_sessions(licence_kind, licence_ref, last_received_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS telemetry_monthly (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT NOT NULL,
        tier TEXT DEFAULT '',
        app_version TEXT DEFAULT '',
        os_family TEXT DEFAULT '',
        counter_name TEXT NOT NULL,
        total INTEGER NOT NULL,
        session_count INTEGER NOT NULL,
        install_count INTEGER NOT NULL,
        UNIQUE(month, tier, app_version, os_family, counter_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS server_flags (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS release_cache (
        repo TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        fetched_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rate_limits (
        bucket TEXT NOT NULL,
        window_start INTEGER NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY (bucket, window_start)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS update_check_daily (
        day TEXT NOT NULL,
        tier TEXT NOT NULL,
        platform TEXT NOT NULL,
        app_version TEXT NOT NULL,
        count INTEGER NOT NULL,
        UNIQUE(day, tier, platform, app_version)
    )
    """,
)

_flag_cache = {"at": 0.0, "values": None}
_cap_warned = set()


def _api():
    import app as api
    return api


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _as_z(value):
    if not value:
        return None
    text = str(value)
    if text.endswith("Z") or "+" in text:
        return text
    return text + "Z"


def iso(moment):
    if isinstance(moment, str):
        return moment
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def parse_version(value):
    if not isinstance(value, str) or not VERSION_RE.match(value):
        return None
    return tuple(int(part) for part in value.split("."))


def _env_bool(name, default):
    raw = __import__("os").environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _config_bool(name, default):
    api = _api()
    raw = api.app.config.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def clear_flag_cache():
    _flag_cache["at"] = 0.0
    _flag_cache["values"] = None


def _flag_defaults():
    api = _api()
    paused = _config_bool("FREE_DOWNLOADS_PAUSED", True)
    message = (api.app.config.get("FREE_PAUSED_MESSAGE") or PAUSED_MESSAGE).strip()
    return {
        "free_downloads_paused": "true" if paused else "false",
        "free_paused_message": message or PAUSED_MESSAGE,
        "maintenance": "true" if _config_bool("MAINTENANCE", False) else "false",
        "min_supported_version_free": (
            api.app.config.get("MIN_SUPPORTED_VERSION_FREE") or ""
        ).strip(),
        "min_supported_version_pro": (
            api.app.config.get("MIN_SUPPORTED_VERSION_PRO") or ""
        ).strip(),
    }


def get_flags():
    now = time.time()
    if _flag_cache["values"] is not None and now - _flag_cache["at"] < FLAG_CACHE_SECONDS:
        return _flag_cache["values"]
    defaults = _flag_defaults()
    api = _api()
    db = api.get_db()
    try:
        rows = db.execute("SELECT key, value FROM server_flags").fetchall()
    except Exception:
        rows = []
    finally:
        db.close()
    stored = {row["key"]: row["value"] for row in rows}
    merged = dict(defaults)
    for key in FLAG_KEYS:
        if key in stored and stored[key] != "":
            merged[key] = stored[key]
    values = {
        "free_downloads_paused": merged["free_downloads_paused"].lower() == "true",
        "message": merged["free_paused_message"],
        "maintenance": merged["maintenance"].lower() == "true",
        "min_supported_version": {
            "free": merged["min_supported_version_free"],
            "pro": merged["min_supported_version_pro"],
        },
    }
    _flag_cache["at"] = now
    _flag_cache["values"] = values
    return values


def set_flag(key, value):
    if key not in FLAG_KEYS:
        raise ValueError("unknown flag")
    api = _api()
    db = api.get_db()
    db.execute("PRAGMA busy_timeout=5000")
    db.execute(
        """
        INSERT INTO server_flags (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, str(value), iso(utcnow())),
    )
    db.commit()
    db.close()
    clear_flag_cache()


def clear_flag(key):
    if key not in FLAG_KEYS:
        raise ValueError("unknown flag")
    api = _api()
    db = api.get_db()
    db.execute("DELETE FROM server_flags WHERE key = ?", (key,))
    db.commit()
    db.close()
    clear_flag_cache()


def is_free_paused():
    return bool(get_flags()["free_downloads_paused"])


def new_request_id():
    return "r_" + secrets.token_hex(8)


def error(status, code, message, retry_after=None, details=None):
    request_id = getattr(g, "request_id", "") or new_request_id()
    body = {"error": {"code": code, "message": message}, "request_id": request_id}
    if retry_after is not None:
        body["error"]["retry_after"] = int(retry_after)
    if details:
        body["error"]["details"] = details
    response = jsonify(body)
    response.status_code = status
    response.headers["X-NC-API-Version"] = "1"
    response.headers["X-Request-Id"] = request_id
    response.headers["Cache-Control"] = "no-store"
    if retry_after is not None:
        response.headers["Retry-After"] = str(int(retry_after))
    return response


def free_paused_response():
    message = get_flags()["message"] or PAUSED_MESSAGE
    return error(503, "free_paused", message, retry_after=PAUSED_RETRY)


def maintenance_response():
    return error(
        503,
        "maintenance",
        "Node Control is briefly unavailable. Try again shortly.",
        retry_after=MAINTENANCE_RETRY,
    )


def _has_control_chars(value):
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def clean_text(value, limit):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("bad type")
    text = value.strip()
    if _has_control_chars(text) or len(text) > limit:
        raise ValueError("bad text")
    return text


def client_ip():
    """Client address for rate limits.

    cloudflared on the Spark connects from loopback and sets
    CF-Connecting-IP. Any other peer is used as-is. Client-supplied
    forwarding headers are ignored.
    """
    remote = (request.remote_addr or "").strip()
    if remote in ("127.0.0.1", "::1"):
        forwarded = (request.headers.get("CF-Connecting-IP") or "").strip()
        if forwarded and len(forwarded) <= 64 and re.match(r"^[A-Za-z0-9.:]+$", forwarded):
            return forwarded
    return remote


def _key_material():
    raw = (_api().app.config.get("KEY_ENCRYPTION_KEY") or "").strip()
    if not raw:
        raise RuntimeError("KEY_ENCRYPTION_KEY is not set")
    if re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        return bytes.fromhex(raw)
    try:
        decoded = base64.b64decode(raw, validate=True)
    except Exception:
        decoded = b""
    if len(decoded) == 32:
        return decoded
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_secret(plaintext):
    nonce = secrets.token_bytes(12)
    cipher = AESGCM(_key_material()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + cipher).decode("ascii")


def decrypt_secret(blob):
    raw = base64.b64decode(blob)
    return AESGCM(_key_material()).decrypt(raw[:12], raw[12:], None).decode("utf-8")


def normalise_key(value):
    text = str(value or "").strip().upper().replace(" ", "-")
    text = re.sub(r"-+", "-", text)
    return text


def hash_key(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_pro_key():
    number = int.from_bytes(secrets.token_bytes(10), "big")
    chars = []
    for _ in range(16):
        chars.append(CROCKFORD[number & 31])
        number >>= 5
    body = "".join(reversed(chars))
    return "NCP-" + "-".join(body[i:i + 4] for i in range(0, 16, 4))


def _code_secret():
    api = _api()
    secret = (api.app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("SECRET_KEY is not set")
    return secret.encode("utf-8")


def hash_code(code):
    return hmac.new(_code_secret(), code.encode("utf-8"), hashlib.sha256).hexdigest()


def mask_email(email):
    local, _, domain = (email or "").partition("@")
    host, dot, tld = domain.rpartition(".")
    def hide(part):
        if not part:
            return "•"
        return part[0] + "•••"
    if not dot:
        return hide(local) + "@" + hide(domain)
    return hide(local) + "@" + hide(host) + "." + tld


def consume_rate(bucket, limit, window_seconds):
    """Shared counter. True when this call is still inside the limit."""
    now = int(time.time())
    window_start = now - (now % int(window_seconds))
    api = _api()
    db = api.get_db()
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """
            INSERT INTO rate_limits (bucket, window_start, count)
            VALUES (?, ?, 1)
            ON CONFLICT(bucket, window_start) DO UPDATE SET count = count + 1
            RETURNING count
            """,
            (bucket, window_start),
        ).fetchone()
        db.commit()
        count = int(row["count"])
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if count > int(limit):
        return False, max(1, window_start + int(window_seconds) - now)
    return True, 0


def _limit_bucket(endpoint, scope, window, token):
    """One counter per endpoint, scope and window length.

    window_start alone is not enough. At 00:00 UTC the hourly and daily
    windows share a start time, so they need different bucket names.
    """
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"ep:{endpoint}:{scope}:{int(window)}:{digest}"


def _enforce_limits(endpoint, parts):
    retry = 0
    allowed = True
    for scope, limit, window in LIMITS.get(endpoint, ()):
        if scope == "key-day":
            token = parts.get("key") or ""
        elif scope == "licence":
            token = str(parts.get("licence") or "")
        else:
            token = parts.get(scope) or ""
        if not token:
            continue
        bucket = _limit_bucket(endpoint, scope, window, token)
        ok, wait = consume_rate(bucket, limit, window)
        if not ok:
            allowed = False
            retry = max(retry, wait)
    if not allowed:
        return error(429, "rate_limited", "Too many requests. Try again later.", retry_after=retry)
    return None


def _note_bad_key(ip):
    bucket = "badkey:ip:" + hashlib.sha256(ip.encode()).hexdigest()
    ok, wait = consume_rate(bucket, 10, 3600)
    if not ok:
        return error(429, "rate_limited", "Too many requests. Try again later.", retry_after=wait)
    return None


def releases_pat():
    api = _api()
    pat = (api.app.config.get("RELEASES_READ_PAT") or "").strip()
    if not pat:
        pat = (api.app.config.get("PRO_RELEASES_PAT") or "").strip()
    return pat


def _repo_for(kind):
    api = _api()
    if kind == "pro":
        return (api.app.config.get("PRO_RELEASES_REPO") or "").strip()
    return (api.app.config.get("FREE_RELEASES_REPO") or "").strip()


def _github_json(url, pat):
    api = _api()
    status, _headers, body = api._github_request(api._github_req(url, pat))
    if status != 200:
        raise RuntimeError(f"GitHub HTTP {status}")
    return json.loads(body.decode("utf-8"))


def _load_release(repo, version):
    """Latest published release, or one tag. Drafts and prereleases are ignored."""
    pat = releases_pat()
    if not pat or not repo:
        raise RuntimeError("release token is not set")
    api = _api()
    cache_key = repo + "|" + (version or "latest")
    db = api.get_db()
    cached = db.execute(
        "SELECT payload, fetched_at FROM release_cache WHERE repo = ?",
        (cache_key,),
    ).fetchone()
    db.close()
    now = int(time.time())
    if cached and now - int(cached["fetched_at"]) < RELEASE_CACHE_SECONDS:
        return json.loads(cached["payload"])
    if version and version != "latest":
        url = f"https://api.github.com/repos/{repo}/releases/tags/v{version}"
    else:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
    payload = _github_json(url, pat)
    if payload.get("draft") or payload.get("prerelease"):
        raise LookupError("no published release")
    db = api.get_db()
    db.execute(
        """
        INSERT INTO release_cache (repo, payload, fetched_at) VALUES (?, ?, ?)
        ON CONFLICT(repo) DO UPDATE SET payload = excluded.payload, fetched_at = excluded.fetched_at
        """,
        (cache_key, json.dumps(payload), now),
    )
    db.commit()
    db.close()
    return payload


def _version_of(release):
    tag = str(release.get("tag_name") or "")
    if tag.startswith("v"):
        tag = tag[1:]
    if parse_version(tag) is None:
        name = str(release.get("name") or "")
        match = re.search(r"(\d+\.\d+\.\d+)", name)
        tag = match.group(1) if match else ""
    return tag


def _asset_for(release, platform, arch):
    ext = ".dmg" if platform == "mac" else ".exe"
    matches = []
    for item in release.get("assets") or []:
        name = item.get("name") or ""
        if name.lower().endswith(ext):
            matches.append(item)
    if not matches:
        return None
    arch_tokens = {
        "arm64": ("arm64", "aarch64"),
        "x86_64": ("x86_64", "amd64", "x64"),
    }.get(arch or "", ())
    for item in matches:
        lowered = (item.get("name") or "").lower()
        if any(token in lowered for token in arch_tokens):
            return item
    return matches[0]


def _sha256_of(repo, asset):
    digest = str(asset.get("digest") or "")
    if digest.lower().startswith("sha256:"):
        hex_digest = digest.split(":", 1)[1].strip().lower()
        if SHA256_RE.match(hex_digest):
            return hex_digest
    pat = releases_pat()
    sums = None
    for item in []:
        pass
    # The caller passes the release assets via asset's sibling lookup.
    return ""


def _sha256_from_release(repo, release, asset):
    direct = _sha256_of(repo, asset)
    if direct:
        return direct
    sums_asset = None
    for item in release.get("assets") or []:
        if (item.get("name") or "").upper() in ("SHA256SUMS", "SHA256SUMS.TXT"):
            sums_asset = item
            break
    if not sums_asset:
        return ""
    api = _api()
    pat = releases_pat()
    status, headers, body = api._github_request(
        api._github_req(
            f"https://api.github.com/repos/{repo}/releases/assets/{sums_asset['id']}",
            pat,
            accept="application/octet-stream",
        ),
        follow_redirects=False,
    )
    if status in (301, 302, 303, 307, 308):
        location = ""
        for key, value in headers.items():
            if str(key).lower() == "location":
                location = value
        if not location or (pat and pat in location):
            return ""
        from urllib.request import urlopen
        with urlopen(location, timeout=15) as resp:
            body = resp.read()
    elif status != 200:
        return ""
    wanted = (asset.get("name") or "").lower()
    for line in body.decode("utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        digest = parts[0].strip().lower()
        name = parts[-1].lstrip("*").lower()
        if name == wanted and SHA256_RE.match(digest):
            return digest
    return ""


def _signed_asset_url(repo, asset):
    api = _api()
    pat = releases_pat()
    status, headers, _body = api._github_request(
        api._github_req(
            f"https://api.github.com/repos/{repo}/releases/assets/{asset['id']}",
            pat,
            accept="application/octet-stream",
        ),
        follow_redirects=False,
    )
    if status not in (301, 302, 303, 307, 308):
        raise RuntimeError(f"asset redirect HTTP {status}")
    location = ""
    for key, value in headers.items():
        if str(key).lower() == "location":
            location = value
    if not location or (pat and pat in location):
        raise RuntimeError("asset redirect was missing a usable URL")
    return location


def _describe_asset(repo, release, platform, arch):
    asset = _asset_for(release, platform, arch)
    if not asset:
        return None
    digest = _sha256_from_release(repo, release, asset)
    if not digest:
        raise RuntimeError("checksum missing")
    return {
        "name": asset.get("name") or "",
        "size": int(asset.get("size") or 0),
        "sha256": digest,
        "asset": asset,
        "version": _version_of(release),
        "published_at": release.get("published_at") or "",
        "notes_markdown": release.get("body") or "",
    }


def _public_base():
    configured = (_api().app.config.get("API_PUBLIC_URL") or "").strip().rstrip("/")
    return configured or "https://api.nodecontrol.io"


def _free_serializer():
    api = _api()
    secret = (api.app.config.get("PRO_DOWNLOAD_SECRET") or "").strip()
    if not secret:
        secret = (api.app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("download signing secret is not set")
    return URLSafeTimedSerializer(secret, salt="nodecontrol-free-download")


def make_free_download_token(license_id, platform):
    payload = {
        "lic": int(license_id),
        "platform": platform,
        "exp": int(time.time()) + FREE_LINK_TTL,
    }
    return _free_serializer().dumps(payload)


def read_free_download_token(token):
    try:
        data = _free_serializer().loads(token, max_age=FREE_LINK_TTL)
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    if int(data.get("exp") or 0) < int(time.time()):
        return None, "expired"
    if data.get("platform") not in ("mac", "win"):
        return None, "invalid"
    return data, ""


def free_redeem_links(license_id):
    base = _public_base()
    links = {}
    for platform in ("mac", "win"):
        token = make_free_download_token(license_id, platform)
        links[platform] = f"{base}{API_PREFIX}/download/free/{platform}?t={token}"
    return links


def _pro_beta_serializer():
    api = _api()
    secret = (api.app.config.get("PRO_DOWNLOAD_SECRET") or "").strip()
    if not secret:
        secret = (api.app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("download signing secret is not set")
    return URLSafeTimedSerializer(secret, salt="nodecontrol-pro-beta-download")


def make_pro_beta_download_token(key_id, platform):
    payload = {
        "kid": int(key_id),
        "platform": platform,
        "exp": int(time.time()) + PRO_BETA_LINK_TTL,
    }
    return _pro_beta_serializer().dumps(payload)


def read_pro_beta_download_token(token):
    try:
        data = _pro_beta_serializer().loads(token, max_age=PRO_BETA_LINK_TTL)
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    if int(data.get("exp") or 0) < int(time.time()):
        return None, "expired"
    if data.get("platform") not in ("mac", "win"):
        return None, "invalid"
    if int(data.get("kid") or 0) < 1:
        return None, "invalid"
    return data, ""


def pro_beta_download_links(key_id):
    base = _public_base()
    links = {}
    for platform in ("mac", "win"):
        token = make_pro_beta_download_token(key_id, platform)
        links[platform] = f"{base}{API_PREFIX}/download/pro/{platform}?t={token}"
    return links


def _lookup_key(raw_key):
    """Return (record, error_response). record is None when error_response is set."""
    key = normalise_key(raw_key)
    api = _api()
    db = api.get_db()
    try:
        if FREE_KEY_RE.match(key):
            row = db.execute(
                "SELECT * FROM licenses WHERE code = ?",
                (key,),
            ).fetchone()
            if not row:
                return None, "invalid"
            if row["status"] == "revoked":
                return None, "revoked"
            if row["status"] != "active":
                return None, "invalid"
            return {
                "kind": "free",
                "id": row["id"],
                "key": key,
                "email": row["email"],
                "status": row["status"],
                "tier": "free",
                "plan": None,
                "current_period_end": None,
                "cancel_at_period_end": None,
                "subscription_status": "active",
            }, ""
        if PRO_KEY_RE.match(key):
            digest = hash_key(key)
            row = db.execute(
                "SELECT * FROM pro_keys WHERE key_hash = ?",
                (digest,),
            ).fetchone()
            if not row or not hmac.compare_digest(row["key_hash"], digest):
                return None, "invalid"
            if row["status"] == "revoked":
                return None, "revoked"
            sub_status = "active"
            period_end = None
            cancel = False
            plan = row["plan"] or None
            if row["source"] != "manual":
                sub = None
                if row["subscription_id"]:
                    sub = db.execute(
                        "SELECT * FROM pro_subscriptions WHERE stripe_subscription_id = ?",
                        (row["subscription_id"],),
                    ).fetchone()
                sub_status = sub["status"] if sub else ""
                if sub_status not in ("active", "trialing"):
                    return None, "subscription_inactive"
                period_end = (sub["current_period_end"] or None) if sub else None
                cancel = bool(sub["cancel_at_period_end"]) if sub else False
                plan = (sub["plan"] if sub and sub["plan"] else plan) or None
            return {
                "kind": "pro",
                "id": row["id"],
                "key": key,
                "email": row["email"],
                "status": row["status"],
                "tier": "pro",
                "plan": plan,
                "current_period_end": period_end,
                "cancel_at_period_end": cancel,
                "subscription_status": sub_status,
                "source": row["source"],
            }, ""
        return None, "invalid"
    finally:
        db.close()


def _moves(kind, ref):
    cutoff = iso(utcnow() - MOVE_WINDOW)
    api = _api()
    db = api.get_db()
    rows = db.execute(
        """
        SELECT moved_at FROM device_moves
        WHERE licence_kind = ? AND licence_ref = ? AND moved_at >= ?
        ORDER BY moved_at
        """,
        (kind, ref, cutoff),
    ).fetchall()
    db.close()
    remaining = max(0, MOVE_LIMIT - len(rows))
    next_at = None
    if rows and remaining == 0:
        oldest = parse_iso(rows[0]["moved_at"])
        if oldest:
            next_at = iso(oldest + MOVE_WINDOW)
    return remaining, next_at


def _active_device(kind, ref):
    api = _api()
    db = api.get_db()
    row = db.execute(
        """
        SELECT * FROM devices
        WHERE licence_kind = ? AND licence_ref = ? AND active = 1
        """,
        (kind, ref),
    ).fetchone()
    db.close()
    return row


def _latest_device(kind, ref):
    api = _api()
    db = api.get_db()
    row = db.execute(
        """
        SELECT * FROM devices
        WHERE licence_kind = ? AND licence_ref = ?
        ORDER BY last_seen_at DESC, id DESC LIMIT 1
        """,
        (kind, ref),
    ).fetchone()
    db.close()
    return row


def _previous_install(kind, ref):
    """The install this key was last bound to.

    Move rows are the record of a bind. The first activation has no move
    row, so that device is the previous install. Timestamps are whole
    seconds, so last_seen_at cannot order two binds in the same second.
    """
    api = _api()
    db = api.get_db()
    move = db.execute(
        """
        SELECT to_install_id FROM device_moves
        WHERE licence_kind = ? AND licence_ref = ?
        ORDER BY id DESC LIMIT 1
        """,
        (kind, ref),
    ).fetchone()
    if move:
        db.close()
        return move["to_install_id"]
    device = db.execute(
        """
        SELECT install_id FROM devices
        WHERE licence_kind = ? AND licence_ref = ?
        ORDER BY id ASC LIMIT 1
        """,
        (kind, ref),
    ).fetchone()
    db.close()
    return device["install_id"] if device else ""


def licence_payload(record, install_id, app_version):
    now = utcnow()
    minimum = effective_minimum(record["tier"])
    current = parse_version(app_version or "")
    floor = parse_version(minimum)
    device = _active_device(record["kind"], record["id"])
    if device is None:
        device = _latest_device(record["kind"], record["id"])
    remaining, _next = _moves(record["kind"], record["id"])
    return {
        "status": "active",
        "tier": record["tier"],
        "plan": record["plan"] if record["tier"] == "pro" else None,
        "current_period_end": _as_z(record["current_period_end"]) if record["tier"] == "pro" else None,
        "cancel_at_period_end": (
            bool(record["cancel_at_period_end"]) if record["tier"] == "pro" else None
        ),
        "grace_period_days": GRACE_DAYS,
        "checked_at": iso(now),
        "next_check_after": iso(now + timedelta(hours=24)),
        "device": {
            "install_id": install_id,
            "activated_at": (device["activated_at"] if device else iso(now)),
            "moves_remaining": remaining,
        },
        "update": {
            "min_supported_version": minimum,
            "force_update": bool(current and floor and current < floor),
        },
        "lease": None,
        "lease_format": None,
    }


def _bind_device(record, install_id, platform, arch, count_move, previous_install):
    api = _api()
    now = iso(utcnow())
    db = api.get_db()
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE devices SET active = 0 WHERE licence_kind = ? AND licence_ref = ? AND active = 1",
            (record["kind"], record["id"]),
        )
        existing = db.execute(
            """
            SELECT id, activated_at FROM devices
            WHERE licence_kind = ? AND licence_ref = ? AND install_id = ?
            """,
            (record["kind"], record["id"], install_id),
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE devices
                SET active = 1, last_seen_at = ?, platform = ?, arch = ?
                WHERE id = ?
                """,
                (now, platform or "", arch or "", existing["id"]),
            )
        else:
            db.execute(
                """
                INSERT INTO devices (
                    licence_kind, licence_ref, install_id, platform, arch,
                    activated_at, last_seen_at, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (record["kind"], record["id"], install_id, platform or "", arch or "", now, now),
            )
        if count_move:
            db.execute(
                """
                INSERT INTO device_moves (
                    licence_kind, licence_ref, from_install_id, to_install_id, moved_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (record["kind"], record["id"], previous_install or "", install_id, now),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _touch_seen(record, install_id):
    api = _api()
    db = api.get_db()
    db.execute(
        """
        UPDATE devices SET last_seen_at = ?
        WHERE licence_kind = ? AND licence_ref = ? AND install_id = ? AND active = 1
        """,
        (iso(utcnow()), record["kind"], record["id"], install_id),
    )
    db.commit()
    db.close()


def _auth_failure(reason):
    if reason == "revoked":
        return error(403, "revoked", "This licence has been revoked.")
    if reason == "subscription_inactive":
        return error(403, "subscription_inactive", "Your Professional subscription is not active.")
    return error(401, "invalid_key", "That licence key was not recognised.")


def _parse_user_agent():
    match = UA_RE.match((request.headers.get("User-Agent") or "").strip())
    if not match:
        return None
    return {
        "version": match.group(1),
        "tier": match.group(2),
        "platform": match.group(3),
        "arch": match.group(4),
    }


def _read_json():
    raw = request.get_data(cache=True) or b""
    if len(raw) > BODY_LIMIT:
        return None, error(413, "payload_too_large", "The request body is too large.")
    if not raw:
        return {}, None
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error(400, "bad_request", "Malformed JSON, missing field or bad type.")
    return data, None


def _guard(endpoint, needs_device=False, check_version=True, body_tier=True):
    if get_flags()["maintenance"]:
        return None, maintenance_response()
    data, err = _read_json()
    if err:
        return None, err
    ip = client_ip()
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        return None, error(401, "missing_key", "A licence key is required.")
    raw_key = header.split(" ", 1)[1].strip()
    if not raw_key:
        return None, error(401, "missing_key", "A licence key is required.")
    record, reason = _lookup_key(raw_key)
    if reason == "invalid":
        limited = _note_bad_key(ip)
        if limited:
            return None, limited
    if reason:
        return None, _auth_failure(reason)
    install = (request.headers.get("X-NC-Install-Id") or "").strip().lower()
    if not INSTALL_RE.match(install):
        return None, error(400, "bad_request", "X-NC-Install-Id must be a random UUID version 4.")
    ua = _parse_user_agent()
    if ua is None:
        return None, error(400, "bad_request", "User-Agent must identify the Node Control app.")
    version = data.get("app_version") or data.get("current_version") or ua["version"]
    if check_version:
        parsed = parse_version(version if isinstance(version, str) else "")
        if parsed is None:
            return None, error(400, "bad_version", "The version is not N.N.N.")
        floor = parse_version(effective_minimum(record["tier"]) or "")
        if floor and parsed < floor:
            latest = _latest_known(record["tier"])
            shown = latest or ".".join(str(part) for part in floor)
            return None, error(
                426,
                "upgrade_required",
                "This version of Node Control is no longer supported. Install the current release.",
                details={"latest_version": shown},
            )
    limited = _enforce_limits(endpoint, {
        "key": record["key"],
        "ip": ip,
        "install": install,
        "licence": str(record["id"]),
    })
    if limited:
        return None, limited
    if body_tier and "tier" in data and data.get("tier") not in (None, ""):
        if data.get("tier") not in ("free", "pro"):
            return None, error(400, "bad_request", "tier must be free or pro.")
        if data.get("tier") != record["tier"]:
            return None, error(403, "tier_mismatch", "This licence is for a different edition.")
    if needs_device:
        active = _active_device(record["kind"], record["id"])
        if not active or active["install_id"] != install:
            remaining, _next = _moves(record["kind"], record["id"])
            last_seen = active["last_seen_at"] if active else None
            return None, error(
                403,
                "device_not_active",
                "This licence is active on another computer.",
                details={
                    "can_move": remaining > 0,
                    "moves_remaining": remaining,
                    "active_device_last_seen": last_seen,
                },
            )
        _touch_seen(record, install)
    return {
        "record": record,
        "install_id": install,
        "ua": ua,
        "body": data,
        "ip": ip,
        "version": version if isinstance(version, str) else ua["version"],
    }, None


def _latest_known(kind):
    try:
        release = _load_release(_repo_for(kind), "latest")
        return _version_of(release)
    except Exception:
        return ""


def effective_minimum(tier):
    """Configured floor, capped so it is never above the latest published release.

    An empty configuration means no minimum. When the published release
    cannot be read, the configured floor is left as it is.
    """
    configured = (get_flags()["min_supported_version"].get(tier) or "").strip()
    if parse_version(configured) is None:
        return None
    latest = _latest_known(tier)
    latest_parsed = parse_version(latest) if latest else None
    if latest_parsed and parse_version(configured) > latest_parsed:
        marker = (tier, configured, latest)
        if marker not in _cap_warned:
            _cap_warned.add(marker)
            logger.warning(
                "Minimum version for %s is %s, above the latest published release %s. Reporting %s.",
                tier,
                configured,
                latest,
                latest,
            )
        return latest
    return configured


def _platform_of(body, ua):
    platform = body.get("platform") or (ua or {}).get("platform")
    if platform not in ("mac", "win"):
        return None
    return platform


def _arch_of(body, ua):
    arch = body.get("arch") or (ua or {}).get("arch")
    if arch not in ("arm64", "x86_64"):
        return None
    return arch


def activate():
    ctx, err = _guard("activate", needs_device=False)
    if err:
        return err
    body = ctx["body"]
    platform = _platform_of(body, ctx["ua"])
    arch = _arch_of(body, ctx["ua"])
    if "platform" in body and body.get("platform") not in ("mac", "win"):
        return error(400, "bad_platform", "platform must be mac or win.")
    if platform is None:
        return error(400, "bad_platform", "platform must be mac or win.")
    if arch is None:
        return error(400, "bad_request", "arch must be arm64 or x86_64.")
    if "tier" not in body:
        return error(400, "bad_request", "tier is required.")
    record = ctx["record"]
    active = _active_device(record["kind"], record["id"])
    if active and active["install_id"] == ctx["install_id"]:
        _touch_seen(record, ctx["install_id"])
        return jsonify({
            "active": True,
            "tier": record["tier"],
            "licence": licence_payload(record, ctx["install_id"], ctx["version"]),
        })
    if active and active["install_id"] != ctx["install_id"]:
        remaining, _next = _moves(record["kind"], record["id"])
        return error(
            403,
            "device_not_active",
            "This licence is active on another computer.",
            details={
                "can_move": remaining > 0,
                "moves_remaining": remaining,
                "active_device_last_seen": active["last_seen_at"],
            },
        )
    previous_install = _previous_install(record["kind"], record["id"])
    count_move = bool(previous_install and previous_install != ctx["install_id"])
    if count_move:
        remaining, next_at = _moves(record["kind"], record["id"])
        if remaining <= 0:
            return error(
                403,
                "move_limit",
                "This licence has used its device moves for the last 30 days.",
                details={"next_move_at": next_at},
            )
    _bind_device(
        record,
        ctx["install_id"],
        platform,
        arch,
        count_move,
        previous_install,
    )
    return jsonify({
        "active": True,
        "tier": record["tier"],
        "licence": licence_payload(record, ctx["install_id"], ctx["version"]),
    })


def licence_check():
    ctx, err = _guard("licence-check", needs_device=True)
    if err:
        return err
    platform = _platform_of(ctx["body"], ctx["ua"])
    if "platform" in ctx["body"] and ctx["body"].get("platform") not in ("mac", "win"):
        return error(400, "bad_platform", "platform must be mac or win.")
    if platform is None:
        return error(400, "bad_platform", "platform must be mac or win.")
    if _arch_of(ctx["body"], ctx["ua"]) is None:
        return error(400, "bad_request", "arch must be arm64 or x86_64.")
    return jsonify(licence_payload(ctx["record"], ctx["install_id"], ctx["version"]))


def deactivate():
    ctx, err = _guard("deactivate", needs_device=True, body_tier=False)
    if err:
        return err
    record = ctx["record"]
    api = _api()
    db = api.get_db()
    db.execute(
        """
        UPDATE devices SET active = 0, last_seen_at = ?
        WHERE licence_kind = ? AND licence_ref = ? AND install_id = ? AND active = 1
        """,
        (iso(utcnow()), record["kind"], record["id"], ctx["install_id"]),
    )
    db.commit()
    db.close()
    remaining, _next = _moves(record["kind"], record["id"])
    return jsonify({"deactivated": True, "moves_remaining": remaining})


def _issue_code(purpose, email, kind="", ref=0):
    code = f"{secrets.randbelow(1000000):06d}"
    api = _api()
    now = utcnow()
    db = api.get_db()
    db.execute(
        "DELETE FROM email_codes WHERE purpose = ? AND email = ? AND licence_kind = ? AND licence_ref = ?",
        (purpose, email.lower(), kind, ref),
    )
    db.execute(
        """
        INSERT INTO email_codes (
            purpose, licence_kind, licence_ref, email, code_hash, expires_at, attempts, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            purpose,
            kind,
            ref,
            email.lower(),
            hash_code(code),
            iso(now + timedelta(seconds=CODE_TTL_SECONDS)),
            iso(now),
        ),
    )
    db.commit()
    db.close()
    return code


def _check_code(purpose, email, code, kind="", ref=0):
    if not isinstance(code, str) or not re.fullmatch(r"\d{6}", code.strip()):
        return error(
            403,
            "code_invalid",
            "That code is wrong or has expired.",
            details={"attempts_remaining": CODE_MAX_ATTEMPTS},
        )
    api = _api()
    db = api.get_db()
    row = db.execute(
        """
        SELECT * FROM email_codes
        WHERE purpose = ? AND email = ? AND licence_kind = ? AND licence_ref = ?
        ORDER BY id DESC LIMIT 1
        """,
        (purpose, email.lower(), kind, ref),
    ).fetchone()
    if not row:
        db.close()
        return error(
            403,
            "code_invalid",
            "That code is wrong or has expired.",
            details={"attempts_remaining": 0},
        )
    expires = parse_iso(row["expires_at"])
    if row["attempts"] >= CODE_MAX_ATTEMPTS or not expires or expires < utcnow():
        db.close()
        return error(
            403,
            "code_invalid",
            "That code is wrong or has expired.",
            details={"attempts_remaining": 0},
        )
    presented = hash_code(code.strip())
    if not hmac.compare_digest(presented, row["code_hash"]):
        attempts = int(row["attempts"]) + 1
        db.execute("UPDATE email_codes SET attempts = ? WHERE id = ?", (attempts, row["id"]))
        db.commit()
        db.close()
        return error(
            403,
            "code_invalid",
            "That code is wrong or has expired.",
            details={"attempts_remaining": max(0, CODE_MAX_ATTEMPTS - attempts)},
        )
    db.execute("DELETE FROM email_codes WHERE id = ?", (row["id"],))
    db.commit()
    db.close()
    return None


def device_move():
    ctx, err = _guard("move", needs_device=False, body_tier=False)
    if err:
        return err
    record = ctx["record"]
    active = _active_device(record["kind"], record["id"])
    if active and active["install_id"] == ctx["install_id"]:
        return error(400, "bad_request", "This computer is already the active device.")
    if not active:
        return error(
            400,
            "bad_request",
            "There is no active device on this licence. Activate this computer instead.",
        )
    remaining, next_at = _moves(record["kind"], record["id"])
    if remaining <= 0:
        return error(
            403,
            "move_limit",
            "This licence has used its device moves for the last 30 days.",
            details={"next_move_at": next_at},
        )
    code = _issue_code("move", record["email"], record["kind"], record["id"])
    sent = _api()._send_mail(
        record["email"],
        "Confirm moving your Node Control licence",
        (
            "A request was made to move your Node Control licence to another computer.\n\n"
            f"Code: {code}\n\n"
            "The code expires in 15 minutes. If you did not ask for this, ignore this email.\n"
        ),
        f"<p>Code: <strong>{code}</strong></p><p>The code expires in 15 minutes.</p>",
    )
    if not sent:
        return error(500, "internal", "We could not send the confirmation email. Try again in a few minutes.")
    return jsonify({
        "code_sent": True,
        "sent_to": mask_email(record["email"]),
        "expires_in": CODE_TTL_SECONDS,
    }), 202


def device_move_confirm():
    ctx, err = _guard("move-confirm", needs_device=False, body_tier=False)
    if err:
        return err
    record = ctx["record"]
    remaining, next_at = _moves(record["kind"], record["id"])
    active = _active_device(record["kind"], record["id"])
    same = active and active["install_id"] == ctx["install_id"]
    if not same and remaining <= 0:
        return error(
            403,
            "move_limit",
            "This licence has used its device moves for the last 30 days.",
            details={"next_move_at": next_at},
        )
    failed = _check_code(
        "move", record["email"], str(ctx["body"].get("code") or ""), record["kind"], record["id"]
    )
    if failed:
        return failed
    if not same:
        previous = active["install_id"] if active else ""
        _bind_device(record, ctx["install_id"], ctx["ua"]["platform"], ctx["ua"]["arch"], True, previous)
        remaining = max(0, remaining - 1)
    return jsonify({
        "active": True,
        "moves_remaining": remaining,
        "licence": licence_payload(record, ctx["install_id"], ctx["version"]),
    })


def record_update_check(tier, platform, app_version):
    """Count one accepted update check. No IP, key, or install id is stored."""
    day = utcnow().strftime("%Y-%m-%d")
    tier = str(tier or "")[:32]
    platform = str(platform or "")[:16]
    app_version = str(app_version or "")[:32]
    try:
        api = _api()
        db = api.get_db()
    except Exception:
        logger.exception("Update check was not counted")
        return
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """
            INSERT INTO update_check_daily (day, tier, platform, app_version, count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(day, tier, platform, app_version) DO UPDATE SET count = count + 1
            """,
            (day, tier, platform, app_version),
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("Update check was not counted")
    finally:
        db.close()


def update_check():
    ctx, err = _guard("update-check", needs_device=True, check_version=False)
    if err:
        return err
    body = ctx["body"]
    platform = body.get("platform")
    if platform not in ("mac", "win"):
        return error(400, "bad_platform", "platform must be mac or win.")
    if _arch_of(body, ctx["ua"]) is None:
        return error(400, "bad_request", "arch must be arm64 or x86_64.")
    current = body.get("current_version")
    if parse_version(current if isinstance(current, str) else "") is None:
        return error(400, "bad_version", "The version is not N.N.N.")
    channel = body.get("channel") or "stable"
    if channel != "stable":
        return error(400, "bad_request", "channel must be stable.")
    record = ctx["record"]
    record_update_check(record["tier"], platform, current)
    flags = get_flags()
    minimum = effective_minimum(record["tier"])
    paused = record["tier"] == "free" and flags["free_downloads_paused"]
    floor = parse_version(minimum) if minimum else None
    force = bool(floor and parse_version(current) < floor)
    try:
        release = _load_release(_repo_for(record["tier"]), "latest")
        described = _describe_asset(_repo_for(record["tier"]), release, platform, body.get("arch"))
    except LookupError:
        return error(404, "no_release", "No published release is available for this edition.")
    except Exception:
        logger.exception("Update check could not read the release")
        if paused:
            return jsonify({
                "update_available": False,
                "latest_version": "",
                "published_at": "",
                "notes_markdown": "",
                "min_supported_version": minimum,
                "force_update": force,
                "paused": True,
                "message": flags["message"] or PAUSED_MESSAGE,
                "asset": None,
            })
        return error(503, "upstream_unavailable", "The release service is unavailable. Try again later.")
    if not described:
        if paused:
            return jsonify({
                "update_available": False,
                "latest_version": "",
                "published_at": "",
                "notes_markdown": "",
                "min_supported_version": minimum,
                "force_update": force,
                "paused": True,
                "message": flags["message"] or PAUSED_MESSAGE,
                "asset": None,
            })
        return error(404, "no_release", "No installer for that platform is published.")
    latest = described["version"]
    newer = bool(parse_version(latest) and parse_version(latest) > parse_version(current))
    return jsonify({
        "update_available": bool(newer and not paused),
        "latest_version": latest,
        "published_at": described["published_at"],
        "notes_markdown": described["notes_markdown"],
        "min_supported_version": minimum,
        "force_update": force,
        "paused": paused,
        "message": (flags["message"] or PAUSED_MESSAGE) if paused else "",
        "asset": {
            "name": described["name"],
            "size": described["size"],
            "sha256": described["sha256"],
        },
    })


def app_download():
    ctx, err = _guard("download", needs_device=True, check_version=False, body_tier=False)
    if err:
        return err
    body = ctx["body"]
    platform = body.get("platform")
    if platform not in ("mac", "win"):
        return error(400, "bad_platform", "platform must be mac or win.")
    version = body.get("version")
    if version != "latest" and parse_version(version if isinstance(version, str) else "") is None:
        return error(400, "bad_version", "The version is not N.N.N.")
    record = ctx["record"]
    if record["tier"] == "free" and get_flags()["free_downloads_paused"]:
        return free_paused_response()
    repo = _repo_for(record["tier"])
    try:
        release = _load_release(repo, version if version != "latest" else "latest")
        described = _describe_asset(repo, release, platform, ctx["ua"]["arch"])
        if not described:
            return error(404, "no_release", "No installer for that platform is published.")
        if version != "latest" and described["version"] != version:
            return error(404, "no_release", "That version is not published.")
        url = _signed_asset_url(repo, described["asset"])
    except LookupError:
        return error(404, "no_release", "No published release is available for this edition.")
    except Exception:
        logger.exception("App download could not sign a release URL")
        return error(503, "upstream_unavailable", "The release service is unavailable. Nothing was installed.")
    return jsonify({
        "url": url,
        "expires_in": ASSET_URL_TTL,
        "name": described["name"],
        "size": described["size"],
        "sha256": described["sha256"],
        "version": described["version"],
    })


def register_install():
    ctx, err = _guard("register", needs_device=True, body_tier=False)
    if err:
        return err
    body = ctx["body"]
    try:
        token = clean_text(body.get("registration_token"), 64)
        name = clean_text(body.get("name"), 100)
        email = clean_text(body.get("email"), 254).lower()
        org = clean_text(body.get("org") or "", 100)
        role = clean_text(body.get("role") or "", 100)
        app_version = clean_text(body.get("app_version"), 32)
        os_family = clean_text(body.get("os_family"), 32)
        os_major = clean_text(body.get("os_major"), 16)
        arch = clean_text(body.get("arch"), 16)
    except ValueError:
        return error(400, "bad_request", "A registration field is missing, too long, or has an unexpected character.")
    if not token or not name or "@" not in email or "." not in email:
        return error(400, "bad_request", "name, email, and registration_token are required.")
    if parse_version(app_version) is None:
        return error(400, "bad_version", "The version is not N.N.N.")
    if arch not in ("arm64", "x86_64"):
        return error(400, "bad_request", "arch must be arm64 or x86_64.")
    record = ctx["record"]
    api = _api()
    db = api.get_db()
    by_token = db.execute(
        "SELECT * FROM registrations WHERE registration_token = ?",
        (token,),
    ).fetchone()
    if by_token:
        db.close()
        if by_token["install_id"] == ctx["install_id"] and by_token["email"] == email:
            return jsonify({"registered": True})
        return error(409, "already_registered", "This install is already registered with a different email.")
    existing = db.execute(
        """
        SELECT * FROM registrations
        WHERE licence_kind = ? AND licence_ref = ? AND install_id = ?
        """,
        (record["kind"], record["id"], ctx["install_id"]),
    ).fetchone()
    if existing:
        db.close()
        if existing["email"] != email:
            return error(409, "already_registered", "This install is already registered with a different email.")
        return jsonify({"registered": True})
    now = iso(utcnow())
    db.execute(
        """
        INSERT INTO registrations (
            licence_kind, licence_ref, install_id, registration_token, name, email,
            org, role, app_version, os_family, os_major, arch, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["kind"], record["id"], ctx["install_id"], token, name, email,
            org, role, app_version, os_family, os_major, arch, now,
        ),
    )
    db.commit()
    db.close()
    _send_registration_alert(record, name, email, org, role, app_version, os_family)
    return jsonify({"registered": True}), 201


def _send_registration_alert(record, name, email, org, role, app_version, os_family):
    api = _api()
    target = (api.app.config.get("REGISTRATION_ALERT_EMAIL") or "support@nodecontrol.io").strip()
    if not target:
        return
    last4 = record["key"][-4:]
    text = (
        "A Node Control install registered.\n\n"
        f"Edition: {record['tier']}\n"
        f"Key ending: {last4}\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Organisation: {org}\n"
        f"Role: {role}\n"
        f"App: {app_version}\n"
        f"OS: {os_family}\n"
    )
    try:
        api._send_mail(target, "Node Control registration", text, "<pre>" + text + "</pre>")
    except Exception:
        logger.exception("Registration alert was not sent")


def _int_field(value, upper):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("bad int")
    if value < 0 or value > upper:
        raise ValueError("bad int")
    return value


def telemetry_post():
    ctx, err = _guard("telemetry", needs_device=True)
    if err:
        return err
    body = ctx["body"]
    for forbidden in DROP_FIELDS:
        body.pop(forbidden, None)
    if body.get("schema") != 1:
        return error(400, "bad_request", "schema must be 1.")
    session_id = body.get("session_id")
    if not isinstance(session_id, str) or not SESSION_RE.match(session_id):
        return error(400, "bad_request", "session_id must be 16 lowercase hex characters.")
    if parse_iso(body.get("session_start_at") if isinstance(body.get("session_start_at"), str) else "") is None:
        return error(400, "bad_request", "session_start_at must be an ISO-8601 time.")
    if parse_iso(body.get("last_flush_at") if isinstance(body.get("last_flush_at"), str) else "") is None:
        return error(400, "bad_request", "last_flush_at must be an ISO-8601 time.")
    try:
        app_version = clean_text(body.get("app_version"), 32)
        os_family = clean_text(body.get("os_family"), 32)
        os_major = clean_text(body.get("os_major"), 16)
        arch = clean_text(body.get("arch"), 16)
        duration = _int_field(body.get("session_duration_s"), 86400 * 8)
        connections = _int_field(body.get("connections_opened"), 1000000)
        errors = _int_field(body.get("errors"), 1000000)
    except ValueError:
        return error(400, "bad_request", "A telemetry field is missing or the wrong type.")
    if parse_version(app_version) is None:
        return error(400, "bad_version", "The version is not N.N.N.")
    if arch not in ("arm64", "x86_64"):
        return error(400, "bad_request", "arch must be arm64 or x86_64.")
    tasks = body.get("tasks") or {}
    if not isinstance(tasks, dict) or len(tasks) > 64:
        return error(400, "bad_request", "tasks must be an object of at most 64 counters.")
    stored = {}
    for name, value in tasks.items():
        if not isinstance(name, str) or not TASK_KEY_RE.match(name):
            return error(400, "bad_request", "A task name is not allowed.")
        try:
            number = _int_field(value, 1000000)
        except ValueError:
            return error(400, "bad_request", "A task count must be an integer from 0 to 1000000.")
        if name in TASK_ALLOW:
            stored[name] = number
    record = ctx["record"]
    if not _config_bool("TELEMETRY_ACCEPT", True):
        return jsonify({"accepted": True}), 202
    start = parse_iso(body["session_start_at"])
    day = start.strftime("%Y-%m-%d")
    now = iso(utcnow())
    api = _api()
    db = api.get_db()
    db.execute(
        """
        INSERT INTO telemetry_sessions (
            licence_ref, licence_kind, install_id, session_id, tier, app_version,
            os_family, os_major, arch, session_start_date, duration_s,
            connections_opened, errors, tasks_json, first_received_at, last_received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(install_id, session_id) DO UPDATE SET
            duration_s = excluded.duration_s,
            connections_opened = excluded.connections_opened,
            errors = excluded.errors,
            tasks_json = excluded.tasks_json,
            app_version = excluded.app_version,
            os_family = excluded.os_family,
            os_major = excluded.os_major,
            arch = excluded.arch,
            last_received_at = excluded.last_received_at
        """,
        (
            record["id"], record["kind"], ctx["install_id"], session_id, record["tier"],
            app_version, os_family, os_major, arch, day, duration, connections, errors,
            json.dumps(stored, sort_keys=True), now, now,
        ),
    )
    db.commit()
    db.close()
    return jsonify({"accepted": True}), 202


def telemetry_delete():
    ctx, err = _guard("telemetry-delete", needs_device=False, body_tier=False)
    if err:
        return err
    record = ctx["record"]
    api = _api()
    db = api.get_db()
    cursor = db.execute(
        "DELETE FROM telemetry_sessions WHERE licence_kind = ? AND licence_ref = ?",
        (record["kind"], record["id"]),
    )
    deleted = cursor.rowcount
    db.commit()
    db.close()
    return jsonify({"deleted": deleted})


def _usable_pro_key_rows(email):
    """Active keys this address can still use, newest first.

    A manual key counts while its row is active. A Stripe key counts only
    while the subscription is active or trialing.
    """
    api = _api()
    db = api.get_db()
    try:
        rows = db.execute(
            """
            SELECT * FROM pro_keys
            WHERE email = ? AND status = 'active' AND reveal_blob != ''
            ORDER BY id DESC
            """,
            (email,),
        ).fetchall()
        usable = []
        for row in rows:
            if row["source"] == "manual":
                usable.append(row)
                continue
            if not row["subscription_id"]:
                continue
            sub = db.execute(
                "SELECT status FROM pro_subscriptions WHERE stripe_subscription_id = ?",
                (row["subscription_id"],),
            ).fetchone()
            if sub and sub["status"] in ("active", "trialing"):
                usable.append(row)
        return usable
    finally:
        db.close()


def _recovery_choice(rows):
    """One key for the app to activate.

    Prefer a key that has no active device, so a second computer can be
    set up without taking the seat of the first. If every key already has
    a computer, use the most recently issued key.
    """
    for row in rows:
        if _active_device("pro", row["id"]) is None:
            return row
    return rows[0]


def _recovery_key_mail(plains):
    text_keys = "\n\n".join(plains)
    text = (
        "Your Professional licence keys:\n\n"
        f"{text_keys}\n\n"
        "Enter one key in Welcome to Node Control.\n\n"
        "Each key is active on one computer at a time.\n"
    )
    parts = ["<p>Your Professional licence keys:</p>"]
    for plain in plains:
        parts.append(f"<p><strong>{html.escape(plain)}</strong></p>")
    parts.append("<p>Enter one key in Welcome to Node Control.</p>")
    parts.append("<p>Each key is active on one computer at a time.</p>")
    return text, "".join(parts)


def pro_key_resend():
    if get_flags()["maintenance"]:
        return maintenance_response()
    data, err = _read_json()
    if err:
        return err
    try:
        email = clean_text(data.get("email"), 254).lower()
    except ValueError:
        return error(400, "bad_request", "email is missing or invalid.")
    if "@" not in email or "." not in email:
        return error(400, "bad_request", "email is missing or invalid.")
    ip = client_ip()
    limited = _enforce_limits("resend", {"email": email, "ip": ip, "key": email})
    if limited:
        return limited
    if _usable_pro_key_rows(email):
        code = _issue_code("pro_resend", email)
        api = _api()
        api._send_mail(
            email,
            "Your Node Control Professional key",
            f"Code: {code}\n\nThe code expires in 15 minutes. If you did not ask for this, ignore this email.\n",
            f"<p>Code: <strong>{code}</strong></p>",
        )
    return jsonify({"code_sent": True, "expires_in": CODE_TTL_SECONDS}), 202


def pro_key_resend_confirm():
    if get_flags()["maintenance"]:
        return maintenance_response()
    data, err = _read_json()
    if err:
        return err
    try:
        email = clean_text(data.get("email"), 254).lower()
    except ValueError:
        return error(400, "bad_request", "email is missing or invalid.")
    if "@" not in email:
        return error(400, "bad_request", "email is missing or invalid.")
    limited = _enforce_limits("resend-confirm", {"email": email, "ip": client_ip(), "key": email})
    if limited:
        return limited
    failed = _check_code("pro_resend", email, str(data.get("code") or ""))
    if failed:
        return failed
    rows = _usable_pro_key_rows(email)
    revealed = []
    for row in rows:
        try:
            plain = decrypt_secret(row["reveal_blob"])
        except Exception:
            logger.error("Could not recover a Professional key")
            continue
        if plain:
            revealed.append((row, plain))
    if not revealed:
        return error(403, "code_invalid", "That code is wrong or has expired.", details={"attempts_remaining": 0})
    chosen = _recovery_choice([row for row, _plain in revealed])
    plain = next(item for row, item in revealed if row["id"] == chosen["id"])
    plains = [item for _row, item in revealed]
    text, html_body = _recovery_key_mail(plains)
    api = _api()
    api._send_mail(email, "Your Node Control Professional key", text, html_body)
    logger.info("Resent Professional key ending %s", chosen["key_last4"])
    return jsonify({"licence_key": plain, "tier": "pro"})


def download_free(platform):
    if get_flags()["maintenance"]:
        return maintenance_response()
    if platform not in ("mac", "win"):
        return error(404, "not_found", "That download was not found.")
    if is_free_paused():
        return free_paused_response()
    token = request.args.get("t") or ""
    data, reason = read_free_download_token(token)
    if reason or not data or data.get("platform") != platform:
        return error(403, "code_invalid", "Enter your code again.")
    ip = client_ip()
    limited = _enforce_limits("free-download", {
        "licence": str(data.get("lic")),
        "ip": ip,
        "key": str(data.get("lic")),
    })
    if limited:
        return limited
    api = _api()
    db = api.get_db()
    row = db.execute(
        "SELECT id, status FROM licenses WHERE id = ?",
        (int(data["lic"]),),
    ).fetchone()
    if not row or row["status"] != "active":
        db.close()
        return error(403, "code_invalid", "Enter your code again.")
    db.execute(
        "INSERT INTO download_events (license_id, platform, kind, created_at) VALUES (?, ?, 'redirect', ?)",
        (row["id"], platform, iso(utcnow())),
    )
    db.commit()
    db.close()
    repo = _repo_for("free")
    try:
        release = _load_release(repo, "latest")
        described = _describe_asset(repo, release, platform, "")
        if not described:
            return error(404, "no_release", "No installer for that platform is published.")
        location = _signed_asset_url(repo, described["asset"])
    except Exception:
        logger.exception("Free download redirect failed")
        return error(503, "upstream_unavailable", "The release service is unavailable. Try again later.")
    # click and auto are beacons for this same file. The redirect is the
    # download. Mail must not change the 302 or the location.
    _queue_free_download_alert(row["id"], platform, described)
    return redirect(location, code=302)


def _queue_free_download_alert(license_id, platform, described):
    try:
        import alerts
        api = _api()
        db = api.get_db()
        try:
            full = db.execute(
                """
                SELECT utm_source, utm_medium, utm_campaign, referrer, landing_page
                FROM licenses WHERE id = ?
                """,
                (license_id,),
            ).fetchone()
        finally:
            db.close()
        payload = {
            "kind": "free_download",
            "licence_id": license_id,
            "platform": platform,
            "arch": (described or {}).get("name") or "",
            "version": (described or {}).get("version") or "",
        }
        if full:
            payload["utm_source"] = full["utm_source"] or ""
            payload["utm_medium"] = full["utm_medium"] or ""
            payload["utm_campaign"] = full["utm_campaign"] or ""
            payload["referrer"] = full["referrer"] or ""
            payload["landing_page"] = full["landing_page"] or ""
        alerts.queue(payload)
    except Exception:
        logging.getLogger("alerts").error("Admin alert was not sent")


def download_pro_beta(platform):
    """First-install link for a hand-added Professional key. One key, one computer."""
    if get_flags()["maintenance"]:
        return maintenance_response()
    if platform not in ("mac", "win"):
        return error(404, "not_found", "That download was not found.")
    data, reason = read_pro_beta_download_token(request.args.get("t") or "")
    if reason or not data or data.get("platform") != platform:
        return error(403, "link_expired", "This download link has expired.")
    key_id = int(data["kid"])
    limited = _enforce_limits("pro-download", {
        "licence": str(key_id),
        "ip": client_ip(),
        "key": str(key_id),
    })
    if limited:
        return limited
    api = _api()
    db = api.get_db()
    row = db.execute(
        "SELECT id, status, source FROM pro_keys WHERE id = ?",
        (key_id,),
    ).fetchone()
    db.close()
    if not row or row["source"] != "manual":
        return error(403, "link_expired", "This download link is not valid.")
    if row["status"] == "revoked":
        return error(403, "revoked", "This licence key has been revoked.")
    if row["status"] != "active":
        return error(403, "link_expired", "This download link is not valid.")
    try:
        location = api._pro_asset_redirect(platform)
    except Exception:
        logger.exception("Pro beta download redirect failed")
        return error(503, "upstream_unavailable", "The release service is unavailable. Try again later.")
    try:
        db = api.get_db()
        try:
            db.execute(
                """
                INSERT INTO download_events (license_id, platform, kind, created_at)
                VALUES (?, ?, 'pro_redirect', ?)
                """,
                (row["id"], platform, iso(utcnow())),
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.error("Pro beta download was not recorded")
    try:
        import alerts
        alerts.queue({
            "kind": "pro_beta_download",
            "licence_id": row["id"],
            "platform": platform,
        })
    except Exception:
        logging.getLogger("alerts").error("Admin alert was not sent")
    return redirect(location, code=302)


def status():
    flags = get_flags()
    latest = {"free": "", "pro": ""}
    for kind in ("free", "pro"):
        latest[kind] = _latest_known(kind) or flags["min_supported_version"].get(kind) or ""
    response = jsonify({
        "free_downloads_paused": flags["free_downloads_paused"],
        "message": flags["message"] if flags["free_downloads_paused"] else "",
        "maintenance": flags["maintenance"],
        "min_supported_version": {
            "free": effective_minimum("free"),
            "pro": effective_minimum("pro"),
        },
        "latest_version": latest,
        "server_time": iso(utcnow()),
    })
    response.headers["Cache-Control"] = "public, max-age=60"
    return response


def ensure_stripe_pro_key(subscription_id, email, plan):
    """Create the NCP- key once per Stripe subscription. The same key is kept."""
    api = _api()
    email = (email or "").strip().lower()
    db = api.get_db()
    existing = db.execute(
        "SELECT id FROM pro_keys WHERE subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    db.close()
    if existing:
        return existing["id"]
    plain = generate_pro_key()
    now = utcnow()
    blob = encrypt_secret(plain)
    db = api.get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        again = db.execute(
            "SELECT id FROM pro_keys WHERE subscription_id = ?",
            (subscription_id,),
        ).fetchone()
        if again:
            db.commit()
            return again["id"]
        cursor = db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, reveal_blob, email, subscription_id, source,
                status, plan, created_at, reveal_until
            ) VALUES (?, ?, ?, ?, ?, 'stripe', 'active', ?, ?, ?)
            """,
            (
                hash_key(plain),
                plain[-4:],
                blob,
                email,
                subscription_id,
                plan or "",
                iso(now),
                iso(now + timedelta(seconds=REVEAL_TTL)),
            ),
        )
        db.commit()
        logger.info("Issued Professional key ending %s", plain[-4:])
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        db.rollback()
        db2 = api.get_db()
        row = db2.execute(
            "SELECT id FROM pro_keys WHERE subscription_id = ?",
            (subscription_id,),
        ).fetchone()
        db2.close()
        if row:
            return row["id"]
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def plaintext_for_subscription(subscription_id):
    api = _api()
    db = api.get_db()
    row = db.execute(
        "SELECT reveal_blob, key_last4 FROM pro_keys WHERE subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    db.close()
    if not row or not row["reveal_blob"]:
        return ""
    return decrypt_secret(row["reveal_blob"])


def reveal_pro_key_for_session(subscription_id):
    api = _api()
    db = api.get_db()
    row = db.execute(
        "SELECT reveal_blob, reveal_until FROM pro_keys WHERE subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    db.close()
    if not row or not row["reveal_blob"]:
        return None
    until = parse_iso(row["reveal_until"])
    if not until or until < utcnow():
        return None
    return decrypt_secret(row["reveal_blob"])


def issue_manual_pro_key(email):
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email:
        raise ValueError("email is required")
    plain = generate_pro_key()
    now = utcnow()
    api = _api()
    db = api.get_db()
    cursor = db.execute(
        """
        INSERT INTO pro_keys (
            key_hash, key_last4, reveal_blob, email, subscription_id, source,
            status, plan, created_at, reveal_until
        ) VALUES (?, ?, ?, ?, NULL, 'manual', 'active', '', ?, ?)
        """,
        (
            hash_key(plain),
            plain[-4:],
            encrypt_secret(plain),
            email,
            iso(now),
            iso(now + timedelta(seconds=REVEAL_TTL)),
        ),
    )
    db.commit()
    key_id = cursor.lastrowid
    db.close()
    logger.info("Issued manual Professional key ending %s", plain[-4:])
    emailed = _send_manual_key_email(email, key_id, plain)
    return {"id": key_id, "email": email, "licence_key": plain, "emailed": bool(emailed), "source": "manual"}


def _html_download_link(url, label):
    """A labelled link, with the full address still visible underneath."""
    href = html.escape(url, quote=True)
    shown = html.escape(url)
    return (
        f'<p><a href="{href}"><strong>{html.escape(label)}</strong></a></p>'
        "<p>If the link doesn't work, copy this address:<br>"
        f'<a href="{href}">{shown}</a></p>'
    )


def _beta_download_message(plain, links):
    """Plain text and HTML for the first-install mail. No customer address."""
    mac = links["mac"]
    win = links["win"]
    if plain:
        key_text = f"Your Node Control Professional key is:\n\n{plain}\n\n"
        key_html = (
            "<p>Your Node Control Professional key is:</p>"
            f"<p><strong>{html.escape(plain)}</strong></p>"
        )
    else:
        key_text = (
            "The key itself is not in this email. "
            "In the app, choose Email me a code to recover it.\n\n"
        )
        key_html = (
            "<p>The key itself is not in this email. "
            "In the app, choose Email me a code to recover it.</p>"
        )
    text = (
        f"{key_text}"
        f"Mac:\n{mac}\n\n"
        f"Windows:\n{win}\n\n"
        "Install Node Control.\n\n"
        "Open Node Control.\n\n"
        "Enter the key in Welcome to Node Control.\n\n"
        "These links are for the first install. After that, the app updates itself.\n\n"
        "The links expire after 7 days. The key is active on one computer at a time.\n\n"
        "Mike\n"
    )
    html_body = (
        f"{key_html}"
        f"{_html_download_link(mac, 'Download for Mac')}"
        f"{_html_download_link(win, 'Download for Windows')}"
        "<p>Install Node Control.</p>"
        "<p>Open Node Control.</p>"
        "<p>Enter the key in Welcome to Node Control.</p>"
        "<p>These links are for the first install. After that, the app updates itself.</p>"
        "<p>The links expire after 7 days. The key is active on one computer at a time.</p>"
        "<p>Mike</p>"
    )
    return "Your Node Control Professional key", text, html_body


def _send_manual_key_email(email, key_id, plain):
    api = _api()
    try:
        links = pro_beta_download_links(key_id)
        subject, text, html_body = _beta_download_message(plain, links)
        return api._send_mail(email, subject, text, html_body)
    except Exception:
        logger.error("Manual key email was not sent")
        return False


def send_manual_pro_links(key_id):
    """Send the first-install mail again. The key string is not changed."""
    api = _api()
    db = api.get_db()
    row = db.execute(
        "SELECT id, email, source, status, reveal_blob, key_last4 FROM pro_keys WHERE id = ?",
        (int(key_id),),
    ).fetchone()
    db.close()
    if not row or row["source"] != "manual" or row["status"] != "active":
        return None
    plain = ""
    if row["reveal_blob"]:
        try:
            plain = decrypt_secret(row["reveal_blob"])
        except Exception:
            logger.error("Could not read a Professional key for the download email")
            plain = ""
    emailed = _send_manual_key_email(row["email"], row["id"], plain or None)
    return {"id": int(row["id"]), "sent": 1 if emailed else 0, "revealed": bool(plain)}


def revoke_pro_key(key_id):
    api = _api()
    db = api.get_db()
    cursor = db.execute(
        """
        UPDATE pro_keys SET status = 'revoked', revoked_at = ?
        WHERE id = ? AND status != 'revoked'
        """,
        (iso(utcnow()), int(key_id)),
    )
    db.commit()
    changed = cursor.rowcount
    db.close()
    return changed


def reset_device(licence):
    record, reason = _lookup_key(licence)
    if reason or not record:
        return None
    api = _api()
    db = api.get_db()
    db.execute(
        "DELETE FROM devices WHERE licence_kind = ? AND licence_ref = ?",
        (record["kind"], record["id"]),
    )
    db.execute(
        "DELETE FROM device_moves WHERE licence_kind = ? AND licence_ref = ?",
        (record["kind"], record["id"]),
    )
    db.commit()
    db.close()
    return record


def run_maintenance():
    """Fold telemetry older than the retention window, then prune counters."""
    api = _api()
    days = int(api.app.config.get("TELEMETRY_RETENTION_DAYS") or 365)
    cutoff = iso(utcnow() - timedelta(days=days))
    db = api.get_db()
    rows = db.execute(
        "SELECT * FROM telemetry_sessions WHERE last_received_at < ?",
        (cutoff,),
    ).fetchall()
    grouped = {}
    installs = {}
    sessions = {}
    for row in rows:
        month = (row["session_start_date"] or "")[:7]
        if len(month) != 7:
            continue
        base = (month, row["tier"] or "", row["app_version"] or "", row["os_family"] or "")
        try:
            tasks = json.loads(row["tasks_json"] or "{}")
        except json.JSONDecodeError:
            tasks = {}
        counters = {
            "duration_s": int(row["duration_s"] or 0),
            "connections_opened": int(row["connections_opened"] or 0),
            "errors": int(row["errors"] or 0),
        }
        for name, value in tasks.items():
            counters[name] = int(value)
        for name, value in counters.items():
            key = base + (name,)
            bucket = grouped.setdefault(key, {"total": 0, "sessions": set(), "installs": set()})
            bucket["total"] += value
            bucket["sessions"].add((row["install_id"], row["session_id"]))
            bucket["installs"].add(row["install_id"])
        sessions[base] = sessions.get(base, 0)
        installs[base] = installs.get(base)
    for key, bucket in grouped.items():
        month, tier, app_version, os_family, counter = key
        db.execute(
            """
            INSERT INTO telemetry_monthly (
                month, tier, app_version, os_family, counter_name, total, session_count, install_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(month, tier, app_version, os_family, counter_name) DO UPDATE SET
                total = total + excluded.total,
                session_count = session_count + excluded.session_count,
                install_count = install_count + excluded.install_count
            """,
            (
                month, tier, app_version, os_family, counter, bucket["total"],
                len(bucket["sessions"]), len(bucket["installs"]),
            ),
        )
    deleted = 0
    if rows:
        ids = [row["id"] for row in rows]
        deleted = 0
        for offset in range(0, len(ids), 200):
            chunk = ids[offset:offset + 200]
            marks = ",".join("?" for _ in chunk)
            cursor = db.execute(
                f"DELETE FROM telemetry_sessions WHERE id IN ({marks})",
                chunk,
            )
            deleted += cursor.rowcount
    stale_window = int(time.time()) - 2 * 86400
    db.execute("DELETE FROM rate_limits WHERE window_start < ?", (stale_window,))
    db.execute("DELETE FROM email_codes WHERE expires_at < ?", (iso(utcnow()),))
    db.commit()
    db.close()
    return {"telemetry_rolled": len(rows), "telemetry_deleted": deleted}


def _admin_flags_get():
    flags = get_flags()
    return jsonify({
        "free_downloads_paused": flags["free_downloads_paused"],
        "free_paused_message": flags["message"],
        "maintenance": flags["maintenance"],
        "min_supported_version_free": flags["min_supported_version"]["free"],
        "min_supported_version_pro": flags["min_supported_version"]["pro"],
    })


def _admin_flags_put():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "No flags were sent"}), 400
    for key, value in data.items():
        if key not in FLAG_KEYS:
            return jsonify({"error": "Unknown flag"}), 400
        if key in ("free_downloads_paused", "maintenance"):
            set_flag(key, "true" if value in (True, "true", "1", 1) else "false")
        else:
            set_flag(key, str(value).strip())
    return _admin_flags_get()


def _admin_pro_keys_get():
    api = _api()
    db = api.get_db()
    rows = db.execute(
        """
        SELECT id, key_last4, email, subscription_id, source, status, plan, created_at, revoked_at
        FROM pro_keys ORDER BY id DESC
        """
    ).fetchall()
    db.close()
    return jsonify({"keys": [dict(row) for row in rows]})


def _admin_pro_keys_post():
    data = request.get_json(silent=True) or {}
    try:
        issued = issue_manual_pro_key((data.get("email") or ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Manual Professional key was not issued")
        return jsonify({"error": "The key was not issued"}), 500
    return jsonify(issued), 201


def _admin_pro_key_revoke(key_id):
    changed = revoke_pro_key(key_id)
    if not changed:
        return jsonify({"error": "not found"}), 404
    return jsonify({"revoked": True, "id": int(key_id)})


def _admin_pro_key_send_links(key_id):
    try:
        result = send_manual_pro_links(key_id)
    except Exception:
        logger.error("Manual download links were not sent")
        return jsonify({"error": "The links were not sent"}), 500
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


def _admin_device_reset(licence):
    record = reset_device(licence)
    if not record:
        return jsonify({"error": "not found"}), 404
    return jsonify({"reset": True, "tier": record["tier"]})


def _admin_resync():
    data = request.get_json(silent=True) or {}
    subscription_id = (data.get("subscription_id") or "").strip()
    if not subscription_id:
        return jsonify({"error": "subscription_id is required"}), 400
    api = _api()
    sub = api._load_subscription(subscription_id)
    api._handle_subscription_change(sub, deleted=False)
    return jsonify({"synced": True, "subscription_id": subscription_id, "status": sub.get("status")})


# Flask raises these before a view runs (unknown path, wrong method,
# oversized body, uncaught exception). Views that return their own
# response, including the legacy {"error": "..."} bodies, are left as
# they are. Paths outside /api/ keep Flask's normal HTML.
_STATUS_ERRORS = {
    400: ("bad_request", "Malformed JSON, missing field or bad type."),
    404: ("not_found", "That resource was not found."),
    405: ("method_not_allowed", "That method is not allowed."),
    413: ("payload_too_large", "The request body is too large."),
    429: ("rate_limited", "Too many requests. Try again later."),
    500: ("internal_error", "Something went wrong."),
}


def _api_error_response(err):
    if not (request.path or "").startswith("/api/"):
        return err.get_response()
    status = int(getattr(err, "code", None) or 500)
    code, message = _STATUS_ERRORS.get(status, ("internal_error", "Something went wrong."))
    return error(status, code, message)


def _labelled(rows, fields):
    """One object per group: the label fields that apply, plus a count."""
    items = []
    for row in rows:
        item = {field: row[field] for field in fields}
        item["count"] = int(row["count"] or 0)
        items.append(item)
    return items


def _rollup_bounds(since, until):
    """Month strings for telemetry_monthly. until on the 1st excludes that month."""
    start = since[:7]
    end = until[:7]
    exclusive = len(until) >= 10 and until[8:10] == "01"
    return start, end, exclusive


_USAGE_TIERS = ("free", "pro", "ai")


def _usage_number(value):
    """A stored counter. Bool is a subclass of int and is not a count."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _median(sorted_values):
    count = len(sorted_values)
    if count == 0:
        return 0
    middle = count // 2
    if count % 2:
        return int(sorted_values[middle])
    left = int(sorted_values[middle - 1])
    right = int(sorted_values[middle])
    average = (left + right) / 2
    if average.is_integer():
        return int(average)
    return average


def _nearest_rank(sorted_values, numerator, denominator):
    """Nearest-rank percentile. p90 is numerator 9, denominator 10."""
    count = len(sorted_values)
    if count == 0:
        return 0
    rank = (numerator * count + denominator - 1) // denominator
    index = min(count - 1, max(0, rank - 1))
    return int(sorted_values[index])


def _count_by_label(db, column):
    """Distinct installs per a fixed telemetry column. Blank labels are omitted."""
    rows = db.execute(
        f"""
        SELECT COALESCE({column}, '') AS label, COUNT(DISTINCT install_id) AS count
        FROM telemetry_sessions
        GROUP BY {column}
        ORDER BY label
        """
    ).fetchall()
    return {row["label"]: int(row["count"] or 0) for row in rows if row["label"]}


def _usage_counts(db, now):
    """Counts from telemetry_sessions and telemetry_monthly.

    No install ids leave this function. Monthly rows have already summed
    installs inside each month, so adding install_count can count one
    install again when it spans two months. Session rows are still distinct.
    Opt-outs are not stored, so this object has no opt-out count.
    """
    cutoffs = {
        "1": iso(now - timedelta(days=1)),
        "7": iso(now - timedelta(days=7)),
        "30": iso(now - timedelta(days=30)),
    }
    active = {label: {tier: 0 for tier in _USAGE_TIERS} for label in cutoffs}
    seen = db.execute(
        """
        SELECT COALESCE(tier, '') AS tier, install_id, MAX(last_received_at) AS seen
        FROM telemetry_sessions
        WHERE last_received_at >= ?
        GROUP BY tier, install_id
        """,
        (cutoffs["30"],),
    ).fetchall()
    for row in seen:
        tier = row["tier"]
        for label, cutoff in cutoffs.items():
            if (row["seen"] or "") < cutoff:
                continue
            bucket = active[label]
            if tier not in bucket:
                bucket[tier] = 0
            bucket[tier] += 1

    today = now.date()
    start_day = (today - timedelta(days=29)).isoformat()
    end_day = today.isoformat()
    per_day = {
        row["day"]: int(row["count"] or 0)
        for row in db.execute(
            """
            SELECT session_start_date AS day, COUNT(*) AS count
            FROM telemetry_sessions
            WHERE session_start_date >= ? AND session_start_date <= ?
            GROUP BY session_start_date
            """,
            (start_day, end_day),
        )
    }
    sessions_per_day = []
    for offset in range(29, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        sessions_per_day.append({"day": day, "sessions": per_day.get(day, 0)})

    uses = {}
    session_hits = {}
    install_hits = {}
    for row in db.execute("SELECT install_id, tasks_json FROM telemetry_sessions"):
        try:
            parsed = json.loads(row["tasks_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        for name, value in parsed.items():
            if not isinstance(name, str) or not name:
                continue
            number = _usage_number(value)
            if number is None:
                continue
            uses[name] = uses.get(name, 0) + number
            if number <= 0:
                continue
            session_hits[name] = session_hits.get(name, 0) + 1
            install_hits.setdefault(name, set()).add(row["install_id"])

    extra_duration = 0
    extra_connections = 0
    extra_errors = 0
    monthly_installs = {}
    for row in db.execute(
        """
        SELECT counter_name,
               COALESCE(SUM(total), 0) AS total,
               COALESCE(SUM(session_count), 0) AS sessions,
               COALESCE(SUM(install_count), 0) AS installs
        FROM telemetry_monthly
        GROUP BY counter_name
        """
    ):
        name = row["counter_name"] or ""
        total = int(row["total"] or 0)
        if name == "duration_s":
            extra_duration += total
        elif name == "connections_opened":
            extra_connections += total
        elif name == "errors":
            extra_errors += total
        elif name:
            uses[name] = uses.get(name, 0) + total
            session_hits[name] = session_hits.get(name, 0) + int(row["sessions"] or 0)
            monthly_installs[name] = monthly_installs.get(name, 0) + int(row["installs"] or 0)

    tasks = {}
    for name in sorted(set(uses) | set(session_hits) | set(monthly_installs)):
        task_uses = int(uses.get(name, 0))
        task_sessions = int(session_hits.get(name, 0))
        task_installs = len(install_hits.get(name, ())) + int(monthly_installs.get(name, 0))
        if task_uses == 0 and task_sessions == 0 and task_installs == 0:
            continue
        tasks[name] = {
            "uses": task_uses,
            "sessions": task_sessions,
            "installs": task_installs,
        }

    durations = []
    connections = extra_connections
    errors = extra_errors
    for row in db.execute(
        "SELECT duration_s, connections_opened, errors FROM telemetry_sessions"
    ):
        durations.append(int(row["duration_s"] or 0))
        connections += int(row["connections_opened"] or 0)
        errors += int(row["errors"] or 0)
    durations.sort()
    total_seconds = sum(durations) + extra_duration
    return {
        "active_installs": active,
        "sessions_per_day": sessions_per_day,
        "tasks": tasks,
        "session_length": {
            "median_s": _median(durations),
            "p90_s": _nearest_rank(durations, 9, 10),
            "total_hours": round(total_seconds / 3600, 2),
        },
        "connections": connections,
        "errors": errors,
        "installs_by_app_version": _count_by_label(db, "app_version"),
        "installs_by_os": _count_by_label(db, "os_family"),
        "installs_by_os_version": _count_by_label(db, "os_major"),
        "installs_by_chip": _count_by_label(db, "arch"),
    }


def admin_stats_v1():
    """Aggregate counts for a read-only dashboard. No emails, keys, install ids, or IPs.

    Device resets are not stored: the admin reset deletes the device rows.
    Move requests are not kept after the code is used. Telemetry has no
    separate event log and no opt-out deletion log. Rate-limit rows are
    request counters, not 429 outcomes. Stripe checkout downloads are not
    recorded. A hand-added key's first-install redirect is stored as kind
    pro_redirect and is left out of the free downloads count.
    """
    api = _api()
    since = api._utc_day(request.args.get("since"), "0000-01-01")
    until = api._utc_day(request.args.get("until"), "9999-12-31")
    if since is None or until is None:
        return jsonify({"error": "since and until must be YYYY-MM-DD"}), 400
    window = (since, until)
    db = api.get_db()
    try:
        licences = _labelled(db.execute(
            """
            SELECT
                tier,
                status,
                CASE
                    WHEN COALESCE(utm_source, '') != '' THEN utm_source
                    WHEN COALESCE(referrer, '') != '' THEN 'ref:' || referrer
                    ELSE '(direct)'
                END AS source,
                COUNT(*) AS count
            FROM licenses
            WHERE created_at >= ? AND created_at < ?
            GROUP BY tier, status, source
            ORDER BY tier, status, source
            """,
            window,
        ).fetchall(), ("tier", "status", "source"))
        pro_keys = _labelled(db.execute(
            """
            SELECT status, COALESCE(plan, '') AS plan, COUNT(*) AS count
            FROM pro_keys
            WHERE created_at >= ? AND created_at < ?
            GROUP BY status, plan
            ORDER BY status, plan
            """,
            window,
        ).fetchall(), ("status", "plan"))
        device_moves = _labelled(db.execute(
            """
            SELECT licence_kind AS tier, 'confirmed' AS status, COUNT(*) AS count
            FROM device_moves
            WHERE moved_at >= ? AND moved_at < ?
            GROUP BY licence_kind
            ORDER BY tier
            """,
            window,
        ).fetchall(), ("tier", "status"))
        # Current seats. Windowing by activated_at would hide seats activated earlier.
        devices = _labelled(db.execute(
            """
            SELECT licence_kind AS tier, COALESCE(platform, '') AS platform, COUNT(*) AS count
            FROM devices
            WHERE active = 1
            GROUP BY licence_kind, platform
            ORDER BY tier, platform
            """
        ).fetchall(), ("tier", "platform"))
        registrations = int(db.execute(
            """
            SELECT COUNT(*) AS count FROM registrations
            WHERE created_at >= ? AND created_at < ?
            """,
            window,
        ).fetchone()["count"] or 0)
        sessions = db.execute(
            """
            SELECT
                'sessions' AS status,
                COALESCE(tier, '') AS tier,
                COALESCE(app_version, '') AS version,
                COALESCE(os_family, '') AS os,
                COUNT(*) AS count
            FROM telemetry_sessions
            WHERE last_received_at >= ? AND last_received_at < ?
            GROUP BY tier, app_version, os_family
            ORDER BY tier, version, os
            """,
            window,
        ).fetchall()
        installs = db.execute(
            """
            SELECT 'installs' AS status, COALESCE(tier, '') AS tier, COUNT(DISTINCT install_id) AS count
            FROM telemetry_sessions
            WHERE last_received_at >= ? AND last_received_at < ?
            GROUP BY tier
            ORDER BY tier
            """,
            window,
        ).fetchall()
        month_start, month_end, month_exclusive = _rollup_bounds(since, until)
        if month_exclusive:
            rollup_sql = """
                SELECT
                    'rollups' AS status,
                    month,
                    COALESCE(tier, '') AS tier,
                    COALESCE(app_version, '') AS version,
                    COALESCE(os_family, '') AS os,
                    MAX(session_count) AS count
                FROM telemetry_monthly
                WHERE month >= ? AND month < ?
                GROUP BY month, tier, app_version, os_family
                ORDER BY month, tier, version, os
            """
        else:
            rollup_sql = """
                SELECT
                    'rollups' AS status,
                    month,
                    COALESCE(tier, '') AS tier,
                    COALESCE(app_version, '') AS version,
                    COALESCE(os_family, '') AS os,
                    MAX(session_count) AS count
                FROM telemetry_monthly
                WHERE month >= ? AND month <= ?
                GROUP BY month, tier, app_version, os_family
                ORDER BY month, tier, version, os
            """
        rollups = db.execute(rollup_sql, (month_start, month_end)).fetchall()
        usage = _usage_counts(db, utcnow())
        telemetry = (
            _labelled(sessions, ("status", "tier", "version", "os"))
            + _labelled(installs, ("status", "tier"))
            + _labelled(rollups, ("status", "month", "tier", "version", "os"))
        )
        downloads = _labelled(db.execute(
            """
            SELECT 'free' AS tier, COALESCE(platform, '') AS platform, COUNT(*) AS count
            FROM download_events
            WHERE kind = 'redirect' AND created_at >= ? AND created_at < ?
            GROUP BY platform
            ORDER BY platform
            """,
            window,
        ).fetchall(), ("tier", "platform"))
        update_checks = _labelled(db.execute(
            """
            SELECT
                day,
                tier,
                platform,
                app_version AS version,
                SUM(count) AS count
            FROM update_check_daily
            WHERE day >= ? AND day < ?
            GROUP BY day, tier, platform, app_version
            ORDER BY day, tier, platform, app_version
            """,
            window,
        ).fetchall(), ("day", "tier", "platform", "version"))
    finally:
        db.close()

    flags = get_flags()
    try:
        db_bytes = os.path.getsize(api.app.config["DB_PATH"])
    except OSError:
        db_bytes = 0
    free_min = (flags["min_supported_version"].get("free") or "").strip() or None
    pro_min = (flags["min_supported_version"].get("pro") or "").strip() or None
    return jsonify({
        "window": {"since": since, "until": until},
        "licences": licences,
        "pro_keys": pro_keys,
        "device_moves": device_moves,
        "devices": devices,
        "registrations": registrations,
        "telemetry": telemetry,
        "usage": usage,
        "downloads": downloads,
        "update_checks": update_checks,
        "flags": {
            "free_downloads_paused": flags["free_downloads_paused"],
            "maintenance": flags["maintenance"],
            "min_supported_version_free": free_min,
            "min_supported_version_pro": pro_min,
        },
        "db_bytes": db_bytes,
        "generated_at": iso(utcnow()),
    })


def _block_test_pro_key(key_id):
    """Refuse a test-mode Professional key when that guard is installed and the flag is off.

    The column and the helper arrive with the test-mode change. Until then a
    missing column means there is nothing to refuse.
    """
    blocker = globals().get("refuse_test_key_id")
    if blocker:
        return blocker(key_id)
    if not key_id:
        return None
    allowed = _config_bool("STRIPE_ALLOW_TEST_EVENTS", False)
    if allowed:
        return None
    api = _api()
    db = api.get_db()
    try:
        try:
            row = db.execute(
                "SELECT is_test FROM pro_keys WHERE id = ?",
                (int(key_id),),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    finally:
        db.close()
    try:
        flagged = int(row["is_test"] or 0) == 1 if row else False
    except (KeyError, IndexError, TypeError, ValueError):
        flagged = False
    if not flagged:
        return None
    return error(403, "test_key", "This Professional key was issued in Stripe test mode.")


def app_checkout():
    """Start Stripe Checkout for a Free licence, tied to this install."""
    ctx, err = _guard("app-checkout", needs_device=False)
    if err:
        return err
    record = ctx["record"]
    if record["kind"] != "free":
        return error(403, "tier_mismatch", "Upgrade starts from a Free licence.")
    plan = ctx["body"].get("plan")
    if plan not in ("monthly", "annual"):
        return error(400, "bad_request", "plan must be monthly or annual.")
    now = utcnow()
    intent_id = secrets.token_hex(16)
    expires = now + timedelta(hours=24)
    api = _api()
    db = api.get_db()
    db.execute(
        """
        INSERT INTO purchase_intents (
            id, free_license_id, install_id, plan, status, stripe_session_id,
            pro_key_id, created_at, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, 'pending', '', NULL, ?, ?, ?)
        """,
        (intent_id, record["id"], ctx["install_id"], plan, iso(now), iso(now), iso(expires)),
    )
    db.commit()
    db.close()
    try:
        session = api.create_app_checkout_session(record.get("email") or "", plan, intent_id)
    except Exception:
        logger.exception("App checkout session was not created")
        db = api.get_db()
        db.execute(
            "UPDATE purchase_intents SET status = 'expired', updated_at = ? WHERE id = ?",
            (iso(utcnow()), intent_id),
        )
        db.commit()
        db.close()
        return error(502, "upstream", "Checkout could not be started.")
    url = (session or {}).get("url") or ""
    session_id = (session or {}).get("id") or ""
    if not url:
        db = api.get_db()
        db.execute(
            "UPDATE purchase_intents SET status = 'expired', updated_at = ? WHERE id = ?",
            (iso(utcnow()), intent_id),
        )
        db.commit()
        db.close()
        return error(502, "upstream", "Checkout could not be started.")
    db = api.get_db()
    db.execute(
        "UPDATE purchase_intents SET stripe_session_id = ?, updated_at = ? WHERE id = ?",
        (session_id, iso(utcnow()), intent_id),
    )
    db.commit()
    db.close()
    return jsonify({
        "url": url,
        "intent_id": intent_id,
        "expires_at": iso(expires),
    })


def _intent_for_caller(record, install_id, intent_id):
    api = _api()
    db = api.get_db()
    try:
        row = db.execute(
            "SELECT * FROM purchase_intents WHERE id = ?",
            (intent_id,),
        ).fetchone()
    finally:
        db.close()
    if not row:
        return None
    if int(row["free_license_id"]) != int(record["id"]) or row["install_id"] != install_id:
        return None
    return row


def purchase_status():
    """Poll a Free-to-Pro purchase. The Professional key is returned once."""
    ctx, err = _guard("purchase-status", needs_device=False)
    if err:
        return err
    record = ctx["record"]
    if record["kind"] != "free":
        return error(403, "tier_mismatch", "This purchase belongs to a Free licence.")
    try:
        intent_id = clean_text(ctx["body"].get("intent_id"), 64)
    except ValueError:
        return error(400, "bad_request", "intent_id is required.")
    if not intent_id:
        return error(400, "bad_request", "intent_id is required.")
    row = _intent_for_caller(record, ctx["install_id"], intent_id)
    if not row:
        return error(404, "not_found", "That purchase was not found.")
    plan = row["plan"]
    if row["status"] == "claimed":
        return jsonify({"status": "claimed", "plan": plan})
    if row["status"] == "expired":
        return jsonify({"status": "expired", "plan": plan})
    expires = parse_iso(row["expires_at"])
    if not expires or expires < utcnow():
        if row["status"] != "expired":
            api = _api()
            db = api.get_db()
            db.execute(
                """
                UPDATE purchase_intents SET status = 'expired', updated_at = ?
                WHERE id = ? AND status != 'claimed'
                """,
                (iso(utcnow()), intent_id),
            )
            db.commit()
            db.close()
        return jsonify({"status": "expired", "plan": plan})
    if row["status"] != "paid" or not row["pro_key_id"]:
        return jsonify({"status": "pending", "plan": plan})
    blocked = _block_test_pro_key(row["pro_key_id"])
    if blocked:
        return blocked
    api = _api()
    db = api.get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute(
            "SELECT * FROM purchase_intents WHERE id = ?",
            (intent_id,),
        ).fetchone()
        if (
            not current
            or int(current["free_license_id"]) != int(record["id"])
            or current["install_id"] != ctx["install_id"]
            or current["status"] != "paid"
            or not current["pro_key_id"]
        ):
            db.commit()
            status_name = current["status"] if current else "pending"
            if status_name == "claimed":
                return jsonify({"status": "claimed", "plan": plan})
            return jsonify({"status": "pending", "plan": plan})
        key_row = db.execute(
            "SELECT reveal_blob FROM pro_keys WHERE id = ?",
            (current["pro_key_id"],),
        ).fetchone()
        if not key_row or not key_row["reveal_blob"]:
            db.commit()
            return jsonify({"status": "pending", "plan": plan})
        plain = decrypt_secret(key_row["reveal_blob"])
        claimed = db.execute(
            """
            UPDATE purchase_intents SET status = 'claimed', updated_at = ?
            WHERE id = ? AND status = 'paid'
              AND free_license_id = ? AND install_id = ?
            """,
            (iso(utcnow()), intent_id, record["id"], ctx["install_id"]),
        )
        if claimed.rowcount != 1:
            db.commit()
            return jsonify({"status": "claimed", "plan": plan})
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Purchase status could not reveal a key")
        return error(500, "internal", "The Professional key could not be read.")
    finally:
        db.close()
    return jsonify({"status": "paid", "plan": plan, "licence_key": plain})


def register(flask_app):
    """Attach /api/v1 routes. Called once from app.py after the tables exist."""
    api = _api()
    for status_code in _STATUS_ERRORS:
        flask_app.register_error_handler(status_code, _api_error_response)

    @flask_app.before_request
    def _v1_request_id():
        if request.path.startswith(API_PREFIX):
            g.request_id = new_request_id()
            raw = request.get_data(cache=True) or b""
            if len(raw) > BODY_LIMIT and request.method in ("POST", "PUT", "DELETE"):
                return error(413, "payload_too_large", "The request body is too large.")

    @flask_app.after_request
    def _v1_headers(response):
        if request.path.startswith(API_PREFIX):
            response.headers.setdefault("X-NC-API-Version", "1")
            response.headers.setdefault("X-Request-Id", getattr(g, "request_id", ""))
            if request.path != API_PREFIX + "/status":
                if "Cache-Control" not in response.headers:
                    response.headers["Cache-Control"] = "no-store"
        return response

    flask_app.add_url_rule(API_PREFIX + "/status", "v1_status", status, methods=["GET"])
    flask_app.add_url_rule(API_PREFIX + "/app/activate", "v1_activate", activate, methods=["POST"])
    flask_app.add_url_rule(API_PREFIX + "/app/licence/check", "v1_licence_check", licence_check, methods=["POST"])
    flask_app.add_url_rule(API_PREFIX + "/app/device/deactivate", "v1_deactivate", deactivate, methods=["POST"])
    flask_app.add_url_rule(API_PREFIX + "/app/device/move", "v1_move", device_move, methods=["POST"])
    flask_app.add_url_rule(
        API_PREFIX + "/app/device/move/confirm", "v1_move_confirm", device_move_confirm, methods=["POST"]
    )
    flask_app.add_url_rule(API_PREFIX + "/app/update-check", "v1_update_check", update_check, methods=["POST"])
    flask_app.add_url_rule(API_PREFIX + "/app/download", "v1_download", app_download, methods=["POST"])
    flask_app.add_url_rule(API_PREFIX + "/app/checkout", "v1_app_checkout", app_checkout, methods=["POST"])
    flask_app.add_url_rule(
        API_PREFIX + "/app/purchase/status", "v1_purchase_status", purchase_status, methods=["POST"]
    )
    flask_app.add_url_rule(API_PREFIX + "/app/register", "v1_register", register_install, methods=["POST"])
    flask_app.add_url_rule(API_PREFIX + "/app/telemetry", "v1_telemetry", telemetry_post, methods=["POST"])
    flask_app.add_url_rule(
        API_PREFIX + "/app/telemetry", "v1_telemetry_delete", telemetry_delete, methods=["DELETE"]
    )
    flask_app.add_url_rule(API_PREFIX + "/pro/key/resend", "v1_resend", pro_key_resend, methods=["POST"])
    flask_app.add_url_rule(
        API_PREFIX + "/pro/key/resend/confirm", "v1_resend_confirm", pro_key_resend_confirm, methods=["POST"]
    )
    flask_app.add_url_rule(
        API_PREFIX + "/download/free/<platform>", "v1_download_free", download_free, methods=["GET"]
    )
    flask_app.add_url_rule(
        API_PREFIX + "/download/pro/<platform>", "v1_download_pro_beta", download_pro_beta, methods=["GET"]
    )

    flask_app.add_url_rule(
        "/api/admin/flags",
        "admin_flags_get",
        api.require_admin_read(_admin_flags_get),
        methods=["GET"],
    )
    flask_app.add_url_rule(
        "/api/admin/flags",
        "admin_flags_put",
        api.require_admin(_admin_flags_put),
        methods=["PUT"],
    )
    flask_app.add_url_rule(
        "/api/admin/pro-keys",
        "admin_pro_keys_list",
        api.require_admin(_admin_pro_keys_get),
        methods=["GET"],
    )
    flask_app.add_url_rule(
        "/api/admin/stats/v1",
        "admin_stats_v1",
        api.require_admin_read(admin_stats_v1),
        methods=["GET"],
    )
    flask_app.add_url_rule(
        "/api/admin/pro-keys",
        "admin_pro_keys_issue",
        api.require_admin(_admin_pro_keys_post),
        methods=["POST"],
    )
    flask_app.add_url_rule(
        "/api/admin/pro-keys/<int:key_id>/revoke",
        "admin_pro_key_revoke",
        api.require_admin(_admin_pro_key_revoke),
        methods=["POST"],
    )
    flask_app.add_url_rule(
        "/api/admin/pro-keys/<int:key_id>/send-links",
        "admin_pro_key_send_links",
        api.require_admin(_admin_pro_key_send_links),
        methods=["POST"],
    )
    flask_app.add_url_rule(
        "/api/admin/devices/<licence>/reset",
        "admin_device_reset",
        api.require_admin(_admin_device_reset),
        methods=["POST"],
    )
    flask_app.add_url_rule(
        "/api/admin/pro/resync",
        "admin_pro_resync",
        api.require_admin(_admin_resync),
        methods=["POST"],
    )
