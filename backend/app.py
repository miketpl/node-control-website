"""
NodeControl License & Download Backend
Flask API for handling free edition download requests,
email verification, code redemption, and license tracking.
"""

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

    # Download URLs
    FREE_MAC_URL=os.environ.get(
        "FREE_MAC_URL",
        "https://github.com/miketpl/node-control-releases-free/releases/latest/download/Node.Control-free-0.9.17.dmg"
    ),
    FREE_WIN_URL=os.environ.get(
        "FREE_WIN_URL",
        "https://github.com/miketpl/node-control-releases-free/releases/latest/download/NodeControl-free-0.9.17-Setup.exe"
    ),

    # Code expiry (hours)
    CODE_EXPIRY_HOURS=int(os.environ.get("CODE_EXPIRY_HOURS", 72)),
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

        CREATE INDEX IF NOT EXISTS idx_licenses_code ON licenses(code);
        CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email);
        CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);
    """)
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


def send_verification_email(to_email, to_name, verify_code, download_code):
    """Send verification email with the download code."""
    cfg = app.config

    if not cfg["SMTP_USER"] or not cfg["SMTP_PASS"]:
        logger.warning("SMTP not configured — skipping email send")
        logger.info(f"Would send to {to_email}: verify={verify_code}, download={download_code}")
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
        logger.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
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
        # Update existing pending request with new codes
        db.execute("""
            UPDATE licenses SET
                name = ?, company = ?, platform = ?,
                code = ?, created_at = ?, ip_address = ?
            WHERE id = ?
        """, (name, company, platform, download_code, now, ip, existing["id"]))

        # Store verify code in a separate field (we reuse ip_address temporarily,
        # or better, add a verify_code column)
        db.execute("""
            UPDATE licenses SET verified_at = ?
            WHERE id = ?
        """, (f"PENDING:{verify_code}", existing["id"]))
    else:
        # Create new license record
        db.execute("""
            INSERT INTO licenses (code, name, email, company, platform, tier, status, created_at, verified_at, ip_address)
            VALUES (?, ?, ?, ?, ?, 'free', 'pending', ?, ?, ?)
        """, (download_code, name, email, company, platform, now, f"PENDING:{verify_code}", ip))

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

    # Activate the license
    now = datetime.utcnow().isoformat()
    db.execute("""
        UPDATE licenses SET status = 'active', verified_at = ?
        WHERE id = ?
    """, (now, license_row["id"]))
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
    return jsonify({
        "success": True,
        "tier": tier,
        "label": f"{tier.title()} Edition",
        "downloads": {
            "mac": app.config["FREE_MAC_URL"],
            "win": app.config["FREE_WIN_URL"],
        },
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
    db.execute("UPDATE licenses SET status = 'revoked' WHERE id = ?", (license_id,))
    db.commit()
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
