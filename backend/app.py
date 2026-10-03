"""
NodeControl License & Download Backend
Flask API for handling free edition download requests,
email verification, code redemption, and license tracking.
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import base64
import json
import os
import secrets
import string
import sqlite3
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps
from urllib.request import Request, urlopen
from urllib.error import URLError

from flask import Flask, request, jsonify
from flask_cors import CORS

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
    ADMIN_TOKEN=os.environ.get("ADMIN_TOKEN", "change-me-in-production"),

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
    LICENSE_REPO=os.environ.get("LICENSE_REPO", "miketpl/node-control-licenses-free"),
    LICENSE_FILE=os.environ.get("LICENSE_FILE", "licenses.json"),
    GITHUB_PAT=os.environ.get("GITHUB_PAT", ""),          # read-only (app license check)
    GITHUB_PAT_WRITE=os.environ.get("GITHUB_PAT_WRITE", ""),  # read/write (license sync)
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Database ─────────────────────────────────────────────────
def get_db():
    """Get a database connection."""
    db = sqlite3.connect(app.config["DB_PATH"])
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    """Create tables if they don't exist, and add any newly-introduced columns."""
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

        CREATE INDEX IF NOT EXISTS idx_licenses_code ON licenses(code);
        CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email);
        CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);
    """)

    # Additive columns for sign-up channel tracking. SQLite has no
    # "ADD COLUMN IF NOT EXISTS" — check existing columns instead.
    existing = {row["name"] for row in db.execute("PRAGMA table_info(licenses)")}
    for col, ddl in (
        ("utm_source",   "utm_source TEXT DEFAULT ''"),
        ("utm_medium",   "utm_medium TEXT DEFAULT ''"),
        ("utm_campaign", "utm_campaign TEXT DEFAULT ''"),
        ("issued_at",    "issued_at TEXT"),
    ):
        if col not in existing:
            db.execute(f"ALTER TABLE licenses ADD COLUMN {ddl}")

    db.commit()
    db.close()


# ── Helpers ──────────────────────────────────────────────────
def generate_code():
    """Generate a download code like NC-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"NC-{part1}-{part2}"


def generate_verify_code():
    """Generate a 6-digit numeric verification code."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def _redact_email(email: str) -> str:
    """Return an email safe to log at INFO: first char + domain only."""
    if not email or "@" not in email:
        return "<redacted>"
    local, _, domain = email.partition("@")
    prefix = local[0] if local else "?"
    return f"{prefix}***@{domain}"


def _clean_utm(value) -> str:
    """Normalise a single UTM value for storage. Cap length; strip control chars."""
    if not value:
        return ""
    s = str(value).strip()[:128]
    return "".join(ch for ch in s if ch.isprintable())


def send_verification_email(to_email, to_name, verify_code, download_code):
    """Send verification email with the download code."""
    cfg = app.config

    if not cfg["SMTP_USER"] or not cfg["SMTP_PASS"]:
        logger.warning("SMTP not configured — skipping email send")
        # Full values only at DEBUG. INFO must not carry email or codes.
        logger.debug(
            "Would send to %s: verify=%s, download=%s",
            to_email, verify_code, download_code,
        )
        return True

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
        logger.info("Verification email sent to %s", _redact_email(to_email))
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", _redact_email(to_email), e)
        return False


def require_admin(f):
    """Decorator to require admin token for endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token != app.config["ADMIN_TOKEN"]:
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
    except URLError:
        return None, None


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
        if resp.status in (200, 201):
            logger.info("GitHub licenses.json updated")
            logger.debug("Commit message: %s", message)
        else:
            logger.error("GitHub sync returned %s", resp.status)


def _add_code_to_licenses(new_code: str):
    """Append a verified license code to licenses.json in GitHub.

    The desktop app reads this file on startup to validate free-tier codes.
    """
    pat = app.config["GITHUB_PAT_WRITE"] or app.config["GITHUB_PAT"]
    if not pat:
        logger.warning("No GitHub PAT configured — skipping license sync")
        return

    current, sha = _get_licenses_json()

    if current is None:
        # File doesn't exist yet — create it with the first code
        current = {"codes": [], "updated": ""}

    if new_code not in current.get("codes", []):
        current.setdefault("codes", []).append(new_code)
        current["updated"] = datetime.utcnow().isoformat()
        _put_licenses_json(current, sha, f"Add code {new_code}")
    else:
        logger.debug("Code already in licenses.json — skipping add")


def _remove_code_from_licenses(code: str):
    """Remove a single revoked license code from licenses.json in GitHub."""
    return _remove_codes_from_licenses([code])


def _remove_codes_from_licenses(codes_to_remove: list) -> int:
    """Remove multiple codes from licenses.json in one GitHub write.

    Returns the number of codes actually removed (0 if none were present).
    """
    codes_to_remove = [c for c in codes_to_remove if c]
    if not codes_to_remove:
        return 0

    pat = app.config["GITHUB_PAT_WRITE"] or app.config["GITHUB_PAT"]
    if not pat:
        logger.warning("No GitHub PAT configured — skipping license sync")
        return 0

    current, sha = _get_licenses_json()
    if current is None:
        return 0

    codes = current.get("codes", [])
    remove_set = set(codes_to_remove)
    kept = [c for c in codes if c not in remove_set]
    removed_count = len(codes) - len(kept)
    if removed_count == 0:
        logger.debug("No matching codes in licenses.json — nothing to remove")
        return 0

    current["codes"] = kept
    current["updated"] = datetime.utcnow().isoformat()
    msg = (
        f"Revoke code {codes_to_remove[0]}"
        if removed_count == 1
        else f"Revoke {removed_count} codes"
    )
    _put_licenses_json(current, sha, msg)
    return removed_count


# ── API Routes ───────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "nodecontrol-license-api"})


@app.route("/api/request-access", methods=["POST"])
def request_access():
    """
    Step 1: User submits their details to request free access.
    Generates a verification code, emails it, and stores the pending license.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    company = (data.get("company") or "").strip()
    platform = (data.get("platform") or "").strip()
    utm_source = _clean_utm(data.get("utm_source"))
    utm_medium = _clean_utm(data.get("utm_medium"))
    utm_campaign = _clean_utm(data.get("utm_campaign"))

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
            "error": "This email already has an active free license. Check your email for the download code.",
            "already_active": True,
        }), 409

    # Generate codes
    verify_code = generate_verify_code()
    download_code = generate_code()
    now = datetime.utcnow().isoformat()
    ip = request.remote_addr or ""

    if existing and existing["status"] == "pending":
        # Update existing pending request with new codes. Overwrite UTM fields
        # only when the new request actually carries them, so a UTM-less resend
        # doesn't erase the channel captured on the first attempt.
        db.execute("""
            UPDATE licenses SET
                name = ?, company = ?, platform = ?,
                code = ?, created_at = ?, issued_at = ?, ip_address = ?,
                verified_at = ?,
                utm_source   = CASE WHEN ? != '' THEN ? ELSE utm_source   END,
                utm_medium   = CASE WHEN ? != '' THEN ? ELSE utm_medium   END,
                utm_campaign = CASE WHEN ? != '' THEN ? ELSE utm_campaign END
            WHERE id = ?
        """, (
            name, company, platform,
            download_code, now, now, ip,
            f"PENDING:{verify_code}",
            utm_source,   utm_source,
            utm_medium,   utm_medium,
            utm_campaign, utm_campaign,
            existing["id"],
        ))
    else:
        # Create new license record
        db.execute("""
            INSERT INTO licenses (
                code, name, email, company, platform, tier, status,
                created_at, issued_at, verified_at, ip_address,
                utm_source, utm_medium, utm_campaign
            )
            VALUES (?, ?, ?, ?, ?, 'free', 'pending', ?, ?, ?, ?, ?, ?, ?)
        """, (
            download_code, name, email, company, platform,
            now, now, f"PENDING:{verify_code}", ip,
            utm_source, utm_medium, utm_campaign,
        ))

    db.commit()
    db.close()

    # Send verification email
    email_sent = send_verification_email(email, name, verify_code, download_code)

    return jsonify({
        "success": True,
        "message": "Verification code sent to your email. Please check your inbox.",
        "email_sent": email_sent,
        # In development, include the code for testing (remove in production)
        **({"_debug_verify_code": verify_code} if app.debug else {}),
    })


@app.route("/api/verify", methods=["POST"])
def verify_code():
    """
    Step 2: User enters the 6-digit verification code from their email.
    If valid, activates the license and returns the download code.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    utm_source = _clean_utm(data.get("utm_source"))
    utm_medium = _clean_utm(data.get("utm_medium"))
    utm_campaign = _clean_utm(data.get("utm_campaign"))

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

    # Sync to GitHub FIRST. If the app can't validate the code (because the
    # write failed), we must not hand it to the user — the row stays pending
    # and the user can retry verify. This is required so a failed write never
    # issues a code the desktop app rejects.
    try:
        _add_code_to_licenses(license_row["code"])
    except Exception as exc:
        db.close()
        logger.error("License GitHub sync failed for id=%s: %s", license_row["id"], exc)
        return jsonify({
            "error": "Temporary problem issuing your code. Please try verifying again in a moment.",
        }), 503

    # Sync succeeded — activate the row. Only overwrite UTM columns when the
    # verify call actually carried them (covers the new-tab click-through case
    # without erasing values captured at request-access time).
    now = datetime.utcnow().isoformat()
    db.execute("""
        UPDATE licenses SET
            status = 'active',
            verified_at = ?,
            utm_source   = CASE WHEN ? != '' THEN ? ELSE utm_source   END,
            utm_medium   = CASE WHEN ? != '' THEN ? ELSE utm_medium   END,
            utm_campaign = CASE WHEN ? != '' THEN ? ELSE utm_campaign END
        WHERE id = ?
    """, (
        now,
        utm_source,   utm_source,
        utm_medium,   utm_medium,
        utm_campaign, utm_campaign,
        license_row["id"],
    ))
    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "download_code": license_row["code"],
        "tier": "free",
        "message": "Email verified! Here's your download code.",
    })


@app.route("/api/redeem", methods=["POST"])
def redeem():
    """
    Step 3: User enters their download code (NC-XXXX-XXXX) to get download links.
    Validates the code, increments download count, returns URLs.
    """
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
    downloads = _get_latest_download_urls()
    return jsonify({
        "success": True,
        "tier": tier,
        "label": f"{tier.title()} Edition",
        "downloads": downloads,
        "download_count": new_count,
    })


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
    """Revoke/delete a license."""
    db = get_db()
    row = db.execute("SELECT code FROM licenses WHERE id = ?", (license_id,)).fetchone()
    db.execute("UPDATE licenses SET status = 'revoked' WHERE id = ?", (license_id,))
    db.commit()
    db.close()

    if row:
        try:
            _remove_code_from_licenses(row["code"])
        except Exception as exc:
            logger.error(f"License GitHub sync failed (non-fatal): {exc}")

    return jsonify({"success": True, "message": "License revoked"})


@app.route("/api/admin/licenses/by-email", methods=["DELETE"])
@require_admin
def delete_by_email():
    """Delete all sign-up records for an email and revoke any live codes.

    This is the data-deletion path: the email is fully removed from the
    site's store, and any codes it issued are removed from licenses.json
    (revoking them in the desktop app after the next re-validation).

    Idempotent: succeeds for an email with no records, and for a code that
    is already absent from licenses.json.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email is required"}), 400

    db = get_db()
    rows = db.execute(
        "SELECT id, code FROM licenses WHERE email = ?", (email,)
    ).fetchall()

    if not rows:
        db.close()
        logger.info("Delete-by-email: no records for %s", _redact_email(email))
        return jsonify({
            "success": True,
            "records_removed": 0,
            "codes_revoked": 0,
        })

    codes = [r["code"] for r in rows if r["code"]]

    # Revoke on GitHub first. If it fails, do NOT delete the SQLite rows —
    # otherwise the local store loses the record while codes stay valid in
    # licenses.json, and we've lost the link between them.
    codes_revoked = 0
    if codes:
        try:
            codes_revoked = _remove_codes_from_licenses(codes)
        except Exception as exc:
            db.close()
            logger.error(
                "Delete-by-email: GitHub sync failed for %s: %s",
                _redact_email(email), exc,
            )
            return jsonify({
                "error": "Could not revoke codes upstream. Nothing was deleted.",
            }), 503

    db.execute("DELETE FROM licenses WHERE email = ?", (email,))
    db.commit()
    db.close()

    logger.info(
        "Delete-by-email: removed %d record(s), revoked %d code(s) for %s",
        len(rows), codes_revoked, _redact_email(email),
    )
    return jsonify({
        "success": True,
        "records_removed": len(rows),
        "codes_revoked": codes_revoked,
    })


@app.route("/api/admin/stats", methods=["GET"])
@require_admin
def stats():
    """Get license statistics."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM licenses").fetchone()["c"]
    active = db.execute("SELECT COUNT(*) as c FROM licenses WHERE status = 'active'").fetchone()["c"]
    pending = db.execute("SELECT COUNT(*) as c FROM licenses WHERE status = 'pending'").fetchone()["c"]
    total_downloads = db.execute("SELECT SUM(download_count) as c FROM licenses").fetchone()["c"] or 0
    db.close()

    return jsonify({
        "total_licenses": total,
        "active": active,
        "pending": pending,
        "total_downloads": total_downloads,
    })


# ── Init & Run ───────────────────────────────────────────────
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
