"""Email-less Free licences, public downloads, and update opt-in.

No IP address, raw machine hash, or licence key is written except the key
column the app already stores. Counts and hashes only leave this module.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from flask import jsonify, redirect, request

import licence_v1
import trial

logger = logging.getLogger(__name__)

EXCLUDED_FREE_IDS = (23, 24, 32)
# The redeem box on /free/ stays until this UTC date, then the page hides it.
REDEEM_BOX_UNTIL = "2027-02-17"
_CRAWLER = re.compile(r"bot|spider|crawl|slurp|preview|facebookexternalhit|whatsapp", re.I)
_NC_KEY = re.compile(r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
_meta_cache = {"at": 0.0, "body": None}
_META_TTL = 300


def ensure_schema(db):
    """Tables for claims, opt-in and the daily download count. Existing rows stay."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS free_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_hmac TEXT NOT NULL DEFAULT '',
            licence_id INTEGER NOT NULL,
            install_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute("DROP INDEX IF EXISTS idx_free_claims_machine")
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_free_claims_lookup
        ON free_claims(machine_hmac)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS update_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            email_hash TEXT NOT NULL UNIQUE,
            consent_text_version TEXT NOT NULL DEFAULT '',
            consented_at TEXT NOT NULL DEFAULT '',
            confirmed_at TEXT NOT NULL DEFAULT '',
            unsubscribed_at TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            utm_source TEXT NOT NULL DEFAULT '',
            utm_campaign TEXT NOT NULL DEFAULT '',
            utm_content TEXT NOT NULL DEFAULT ''
        )
        """
    )
    subscriber_cols = {row[1] for row in db.execute("PRAGMA table_info(update_subscribers)")}
    if "licence_id" not in subscriber_cols:
        db.execute("ALTER TABLE update_subscribers ADD COLUMN licence_id INTEGER")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_daily_counts (
            day TEXT NOT NULL,
            kind TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            mailed INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, kind)
        )
        """
    )


def _db():
    return licence_v1._api().get_db()


def _now():
    return licence_v1.utcnow()


def _day(moment=None):
    return (moment or _now()).strftime("%Y-%m-%d")


def _hash_token(value):
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _repeat_mode():
    """new issues another NC- code. same returns the existing one. Empty means new."""
    raw = str(licence_v1._api().app.config.get("FREE_CLAIM_REPEAT") or "").strip().lower()
    if raw == "same":
        return "same"
    return "new"


def _issued(code, new=None):
    """An issued Free key is always an NC- code. The lease, on activate, is free or trial."""
    if not _NC_KEY.match(code or ""):
        return licence_v1.error(503, "upstream_unavailable", "A licence could not be issued.")
    body = {"licence_key": code, "tier": "free", "active": True}
    if new is not None:
        body["new"] = new
    return jsonify(body)


def _cap():
    raw = str(licence_v1._api().app.config.get("FREE_CLAIM_DAILY_CAP") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return 300


def _email_less_today(db):
    start = _day()
    end = (_now().date() + timedelta(days=1)).isoformat()
    marks = ",".join("?" * len(EXCLUDED_FREE_IDS))
    row = db.execute(
        f"""
        SELECT COUNT(*) AS c FROM licenses
        WHERE (email IS NULL OR trim(email) = '')
          AND created_at >= ? AND created_at < ?
          AND id NOT IN ({marks})
        """,
        (start, end, *EXCLUDED_FREE_IDS),
    ).fetchone()
    return int(row["c"] or 0)


def _capacity_block(db):
    if _email_less_today(db) < _cap():
        return None
    _note_cap(db)
    tomorrow = (_now().date() + timedelta(days=1))
    wait = int((datetime.combine(tomorrow, datetime.min.time(), timezone.utc) - _now()).total_seconds())
    return licence_v1.error(
        503,
        "claim_capacity",
        "Free sign-up is full for today. Try again tomorrow.",
        retry_after=max(60, wait),
    )


def _note_cap(db):
    day = _day()
    db.execute(
        """
        INSERT INTO admin_daily_counts (day, kind, count, mailed)
        VALUES (?, 'claim_capacity', 1, 0)
        ON CONFLICT(day, kind) DO UPDATE SET count = count + 1
        """,
        (day,),
    )
    row = db.execute(
        "SELECT mailed FROM admin_daily_counts WHERE day = ? AND kind = 'claim_capacity'",
        (day,),
    ).fetchone()
    if row and int(row["mailed"] or 0):
        db.commit()
        return
    db.execute(
        "UPDATE admin_daily_counts SET mailed = 1 WHERE day = ? AND kind = 'claim_capacity'",
        (day,),
    )
    db.commit()
    _mail("Free sign-up cap", "Email-less Free licence cap reached for today.")


def _mail(subject, text):
    api = licence_v1._api()
    address = (api.app.config.get("ADMIN_ALERT_EMAIL") or "").strip()
    if not address:
        return
    try:
        api._send_mail(address, subject, text, "<pre>" + text + "</pre>", log_recipient=False)
    except Exception:
        logger.error("Daily count mail was not sent")


def _count(event, source="none", campaign="none", content="none"):
    day = _day()
    db = _db()
    try:
        db.execute(
            """
            INSERT INTO funnel_daily (day, event, utm_source, utm_campaign, utm_content, count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(day, event, utm_source, utm_campaign, utm_content)
            DO UPDATE SET count = count + 1
            """,
            (day, event, source or "none", campaign or "none", content or "none"),
        )
        db.commit()
    finally:
        db.close()


def _tags(data):
    import app as api
    if not isinstance(data, dict):
        data = {}
    attr = data.get("attribution") if isinstance(data.get("attribution"), dict) else data
    cleaned = api.clean_attribution(attr if isinstance(attr, dict) else {})
    return (
        cleaned.get("utm_source") or "",
        cleaned.get("utm_campaign") or "",
        cleaned.get("utm_content") or "",
        cleaned.get("referrer") or "",
        cleaned.get("landing_page") or "",
    )


def _slug_tags(source, campaign, content):
    return (
        licence_v1._marketing_slug(source),
        licence_v1._marketing_slug(campaign),
        licence_v1._marketing_slug(content),
    )


def _fresh_code(db):
    import app as api
    for _ in range(8):
        code = api.generate_code()
        if not db.execute("SELECT 1 FROM licenses WHERE code = ?", (code,)).fetchone():
            return code
    return ""


def _insert_licence(db, platform, source, source_tag, campaign, content, referrer, landing):
    code = _fresh_code(db)
    if not code:
        return None, None
    now = licence_v1.iso(_now())
    cursor = db.execute(
        """
        INSERT INTO licenses (
            code, name, email, company, platform, tier, status, created_at,
            source, utm_source, utm_campaign, utm_content, referrer, landing_page, ip_address
        ) VALUES (?, '', '', '', ?, 'free', 'active', ?, ?, ?, ?, ?, ?, ?, '')
        """,
        (code, platform or "", now, source, source_tag, campaign, content, referrer, landing),
    )
    return code, int(cursor.lastrowid)


def prune_unactivated_instant_keys(db):
    """Drop unused website keys older than 30 days. Test ids and used licences stay."""
    cutoff = licence_v1.iso(_now() - timedelta(days=30))
    marks = ",".join("?" * len(EXCLUDED_FREE_IDS))
    db.execute(
        f"""
        DELETE FROM licenses
        WHERE source = 'web_instant'
          AND (email IS NULL OR trim(email) = '')
          AND created_at < ?
          AND id NOT IN ({marks})
          AND NOT EXISTS (
              SELECT 1 FROM devices
              WHERE devices.licence_kind = 'free' AND devices.licence_ref = licenses.id
          )
        """,
        (cutoff, *EXCLUDED_FREE_IDS),
    )


def instant_key():
    """Phase 1. The page asks for a key after the download click. No email."""
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    if licence_v1.is_free_paused():
        return licence_v1.free_paused_response()
    data, err = licence_v1._read_json()
    if err:
        return err
    platform = str((data or {}).get("platform") or "").strip().lower()
    if platform not in ("mac", "win"):
        return licence_v1.error(400, "bad_platform", "platform must be mac or win.")
    ip = _hash_token(licence_v1.client_ip())
    limited = licence_v1._enforce_limits("free-instant-key", {"ip": ip})
    if limited:
        _count("free_claim_refused_rate")
        return limited
    source, campaign, content, referrer, landing = _tags(data or {})
    slugs = _slug_tags(source, campaign, content)
    db = _db()
    try:
        prune_unactivated_instant_keys(db)
        blocked = _capacity_block(db)
        if blocked:
            db.commit()
            return blocked
        code, licence_id = _insert_licence(
            db, platform, "web_instant", source, campaign, content, referrer, landing
        )
        if not code:
            db.rollback()
            return licence_v1.error(503, "upstream_unavailable", "A licence could not be issued.")
        db.commit()
    finally:
        db.close()
    _count("free_instant_key_issued", *slugs)
    return _issued(code)


def claim():
    """Phase 2. The app asks for a Free key on first run."""
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    if licence_v1.is_free_paused():
        return licence_v1.free_paused_response()
    data, err = licence_v1._read_json()
    if err:
        return err
    data = data or {}
    ua = licence_v1._parse_user_agent()
    if ua is None:
        return licence_v1.error(400, "bad_request", "User-Agent must identify the Node Control app.")
    install = (request.headers.get("X-NC-Install-Id") or "").strip().lower()
    if not licence_v1.INSTALL_RE.match(install):
        return licence_v1.error(400, "bad_request", "X-NC-Install-Id must be a random UUID version 4.")
    version = data.get("app_version") or ua["version"]
    parsed = licence_v1.parse_version(version if isinstance(version, str) else "")
    if parsed is None:
        return licence_v1.error(400, "bad_version", "The version is not N.N.N.")
    floor = licence_v1.parse_version(licence_v1.effective_minimum("free") or "")
    if floor and parsed < floor:
        latest = licence_v1._latest_known("free")
        shown = latest or ".".join(str(part) for part in floor)
        return licence_v1.error(
            426, "upgrade_required",
            "This version of Node Control is no longer supported. Install the current release.",
            details={"latest_version": shown},
        )
    platform = str(data.get("platform") or ua["platform"] or "").strip().lower()
    if platform not in ("mac", "win"):
        return licence_v1.error(400, "bad_platform", "platform must be mac or win.")
    presented = trial.read_machine_header()
    if presented not in (None, "unavailable") and not trial.HASH_RE.match(presented or ""):
        return licence_v1.error(400, "bad_machine_hash", "X-NC-Machine-Hash is missing or not valid.")
    machine = trial.machine_hmac(presented) if presented and presented != "unavailable" else ""
    ip = _hash_token(licence_v1.client_ip())
    limited = licence_v1._enforce_limits("free-claim", {
        "machine": machine,
        "install": install,
        "ip": ip,
    })
    if limited:
        _count("free_claim_refused_rate")
        return limited
    source, campaign, content, _referrer, _landing = _tags(data)
    slugs = _slug_tags(source, campaign, content)
    db = _db()
    try:
        if machine and _repeat_mode() == "same":
            existing = db.execute(
                """
                SELECT licence_id FROM free_claims
                WHERE machine_hmac = ?
                ORDER BY id DESC LIMIT 1
                """,
                (machine,),
            ).fetchone()
            if existing:
                row = db.execute(
                    "SELECT code, status FROM licenses WHERE id = ?",
                    (int(existing["licence_id"]),),
                ).fetchone()
                if row and row["status"] == "revoked":
                    return licence_v1.error(403, "licence_revoked", "This licence has been revoked.")
                if row and _NC_KEY.match(row["code"] or ""):
                    _count("free_first_run_reclaim", *slugs)
                    return _issued(row["code"], new=False)
        blocked = _capacity_block(db)
        if blocked:
            db.commit()
            return blocked
        code, licence_id = _insert_licence(db, platform, "first_run", source, campaign, content, "", "")
        if not code:
            db.rollback()
            return licence_v1.error(503, "upstream_unavailable", "A licence could not be issued.")
        db.execute(
            """
            INSERT INTO free_claims (machine_hmac, licence_id, install_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (machine, licence_id, install, licence_v1.iso(_now())),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Free claim was not stored")
        return licence_v1.error(503, "upstream_unavailable", "A licence could not be issued.")
    finally:
        db.close()
    if not machine:
        _count("free_claim_refused_no_machine", *slugs)
    _count("free_first_run_claim", *slugs)
    return _issued(code, new=True)


def _release_meta():
    import time
    now = time.time()
    if _meta_cache["body"] and now - _meta_cache["at"] < _META_TTL:
        return _meta_cache["body"], None
    repo = licence_v1._repo_for("free")
    try:
        release = licence_v1._load_release(repo, "latest")
        body = {
            "version": licence_v1._version_of(release),
            "published_at": release.get("published_at") or "",
        }
        for platform in ("mac", "win"):
            described = licence_v1._describe_asset(repo, release, platform, "")
            if not described:
                body[platform] = None
                continue
            body[platform] = {
                "name": described["name"],
                "size": described["size"],
                "sha256": described["sha256"],
            }
    except Exception:
        logger.exception("Free release metadata was not loaded")
        return None, licence_v1.error(503, "upstream_unavailable", "The release service is unavailable. Try again later.")
    _meta_cache["at"] = now
    _meta_cache["body"] = body
    return body, None


def latest_metadata():
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    body, err = _release_meta()
    if err:
        return err
    response = jsonify(body)
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def latest_download(platform):
    if licence_v1.get_flags()["maintenance"]:
        return licence_v1.maintenance_response()
    if platform not in ("mac", "win"):
        return licence_v1.error(404, "not_found", "That download was not found.")
    if licence_v1.is_free_paused():
        return licence_v1.free_paused_response()
    agent = request.headers.get("User-Agent") or ""
    crawler = bool(_CRAWLER.search(agent))
    ip_hash = _hash_token(licence_v1.client_ip())
    if not crawler:
        limited = licence_v1._enforce_limits("free-public-download", {"ip": ip_hash})
        if limited:
            return limited
    repo = licence_v1._repo_for("free")
    try:
        release = licence_v1._load_release(repo, "latest")
        described = licence_v1._describe_asset(repo, release, platform, "")
        if not described:
            return licence_v1.error(404, "no_release", "No installer for that platform is published.")
        location = licence_v1._signed_asset_url(repo, described["asset"])
    except Exception:
        logger.exception("Public Free download redirect failed")
        return licence_v1.error(503, "upstream_unavailable", "The release service is unavailable. Try again later.")
    if not crawler:
        _record_direct(platform, described.get("version") or "", ip_hash)
    response = redirect(location, code=302)
    response.headers["X-Robots-Tag"] = "noindex"
    return response


def _record_direct(platform, version, ip_hash):
    import app as api
    source = request.args.get("utm_source")
    campaign = request.args.get("utm_campaign")
    content = request.args.get("utm_content")
    cleaned = api.clean_attribution({
        "utm_source": source, "utm_campaign": campaign, "utm_content": content,
    })
    db = _db()
    try:
        fresh, _wait = licence_v1.consume_rate(f"direct24:{platform}:{ip_hash}", 1, 86400)
        if not fresh:
            return
        db.execute(
            """
            INSERT INTO download_events (
                license_id, platform, kind, created_at, version, tier,
                utm_source, utm_campaign, utm_content
            ) VALUES (0, ?, 'direct', ?, ?, 'free', ?, ?, ?)
            """,
            (
                platform, licence_v1.iso(_now()), version or None,
                cleaned.get("utm_source") or "",
                cleaned.get("utm_campaign") or "",
                cleaned.get("utm_content") or "",
            ),
        )
        day = _day()
        db.execute(
            """
            INSERT INTO admin_daily_counts (day, kind, count, mailed)
            VALUES (?, 'free_direct', 1, 0)
            ON CONFLICT(day, kind) DO UPDATE SET count = count + 1
            """,
            (day,),
        )
        db.commit()
        _maybe_mail_yesterday(db)
    finally:
        db.close()


def _maybe_mail_yesterday(db):
    yesterday = (_now().date() - timedelta(days=1)).isoformat()
    row = db.execute(
        "SELECT count, mailed FROM admin_daily_counts WHERE day = ? AND kind = 'free_direct'",
        (yesterday,),
    ).fetchone()
    if not row or int(row["mailed"] or 0) or int(row["count"] or 0) < 1:
        return
    db.execute(
        "UPDATE admin_daily_counts SET mailed = 1 WHERE day = ? AND kind = 'free_direct'",
        (yesterday,),
    )
    db.commit()
    _mail("Free downloads", f"Direct Free downloads on {yesterday}: {int(row['count'])}.")


def _free_licence_id(raw_key):
    """Licence id for an NC- key, or None. The key is not logged."""
    text = str(raw_key or "").strip()
    if not text:
        return None
    record, reason = licence_v1._lookup_key(text)
    if reason or not record or record.get("kind") != "free":
        return None
    if record.get("status") == "revoked":
        return None
    return int(record["id"])


def _optin_serializer():
    from itsdangerous import URLSafeTimedSerializer
    secret = (licence_v1._api().app.config.get("SECRET_KEY") or "").strip()
    return URLSafeTimedSerializer(secret, salt="nodecontrol-update-optin")


def subscribe_updates():
    data, err = licence_v1._read_json()
    if err:
        return err
    data = data or {}
    if data.get("consent") is not True:
        return licence_v1.error(400, "bad_request", "Consent is required.")
    email = str(data.get("email") or "").strip().lower()
    if not _EMAIL.match(email) or len(email) > 254:
        return licence_v1.error(400, "bad_request", "email is missing or invalid.")
    version = str(data.get("consent_text_version") or "").strip()[:32]
    if not version:
        return licence_v1.error(400, "bad_request", "consent_text_version is required.")
    source_name = str(data.get("source") or "free_page").strip().lower()
    if source_name not in ("free_page", "app"):
        source_name = "free_page"
    ip = _hash_token(licence_v1.client_ip())
    email_key = trial.email_hash(email)
    limited = licence_v1._enforce_limits("free-optin", {"ip": ip, "email": email_key or _hash_token(email)})
    if limited:
        return limited
    utm_source, utm_campaign, utm_content, _ref, _land = _tags(data)
    licence_id = _free_licence_id(data.get("licence_key"))
    now = licence_v1.iso(_now())
    db = _db()
    unlock_id = None
    try:
        row = db.execute(
            "SELECT id, confirmed_at, unsubscribed_at FROM update_subscribers WHERE email_hash = ?",
            (email_key,),
        ).fetchone()
        if row and (row["confirmed_at"] or "") and not (row["unsubscribed_at"] or ""):
            subscriber_id = int(row["id"])
            if licence_id:
                db.execute(
                    "UPDATE update_subscribers SET licence_id = COALESCE(licence_id, ?) WHERE id = ?",
                    (licence_id, subscriber_id),
                )
                db.execute(
                    """
                    UPDATE licenses SET email = ?
                    WHERE id = ? AND tier = 'free' AND status != 'revoked'
                      AND (email IS NULL OR trim(email) = '')
                    """,
                    (email, licence_id),
                )
                unlock_id = licence_id
            send = False
        elif row:
            db.execute(
                """
                UPDATE update_subscribers
                SET email = ?, consent_text_version = ?, consented_at = ?,
                    confirmed_at = '', unsubscribed_at = '', source = ?,
                    utm_source = ?, utm_campaign = ?, utm_content = ?,
                    licence_id = COALESCE(?, licence_id)
                WHERE id = ?
                """,
                (email, version, now, source_name, utm_source, utm_campaign, utm_content, licence_id, int(row["id"])),
            )
            subscriber_id = int(row["id"])
            send = True
        else:
            cursor = db.execute(
                """
                INSERT INTO update_subscribers (
                    email, email_hash, consent_text_version, consented_at, source,
                    utm_source, utm_campaign, utm_content, licence_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (email, email_key, version, now, source_name, utm_source, utm_campaign, utm_content, licence_id),
            )
            subscriber_id = int(cursor.lastrowid)
            send = True
        db.commit()
    finally:
        db.close()
    slugs = _slug_tags(utm_source, utm_campaign, utm_content)
    _count("free_optin_submit", *slugs)
    if send:
        _send_confirm(email, subscriber_id)
    elif unlock_id:
        trial.try_unlock_after_verified_email(unlock_id)
    return jsonify({"message": "Check your email to confirm."}), 202


def _send_confirm(email, subscriber_id):
    token = _optin_serializer().dumps({"id": int(subscriber_id)})
    api = licence_v1._api()
    base = (api.app.config.get("API_PUBLIC_URL") or "https://api.nodecontrol.io").rstrip("/")
    url = f"{base}/api/free/updates/confirm?t={token}"
    text = (
        "Confirm that you want email when a new version of Node Control ships.\n\n"
        f"{url}\n\nThe link lasts 14 days. If you did not ask for this, ignore it."
    )
    html = f"<p>Confirm that you want email when a new version of Node Control ships.</p><p><a href=\"{url}\">Confirm</a></p>"
    try:
        api._send_mail(email, "Confirm Node Control update email", text, html, log_recipient=False)
    except Exception:
        logger.error("Opt-in confirmation was not sent")


def _page(title, message, status=200):
    from flask import Response
    body = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body><h1>{title}</h1><p>{message}</p></body></html>"
    )
    return Response(body, status=status, mimetype="text/html")


def confirm_updates():
    from itsdangerous import BadSignature, SignatureExpired
    token = (request.args.get("t") or "").strip()
    if not token:
        return _page("Link not valid", "This link is not valid.", 400)
    try:
        data = _optin_serializer().loads(token, max_age=14 * 24 * 3600)
    except SignatureExpired:
        return _page("Link expired", "This link has expired. Submit the form again.", 400)
    except BadSignature:
        return _page("Link not valid", "This link is not valid.", 400)
    subscriber_id = int((data or {}).get("id") or 0)
    db = _db()
    try:
        row = db.execute(
            "SELECT id, email, licence_id, confirmed_at FROM update_subscribers WHERE id = ?",
            (subscriber_id,),
        ).fetchone()
        if not row:
            return _page("Link not valid", "This link is not valid.", 400)
        linked = row["licence_id"]
        address = row["email"] or ""
        if not (row["confirmed_at"] or ""):
            db.execute(
                """
                UPDATE update_subscribers
                SET confirmed_at = ?, unsubscribed_at = ''
                WHERE id = ?
                """,
                (licence_v1.iso(_now()), subscriber_id),
            )
            if linked and address:
                db.execute(
                    """
                    UPDATE licenses SET email = ?
                    WHERE id = ? AND tier = 'free' AND status != 'revoked'
                      AND (email IS NULL OR trim(email) = '')
                    """,
                    (address, int(linked)),
                )
            db.commit()
            fresh = True
        else:
            fresh = False
    finally:
        db.close()
    if fresh:
        _count("free_optin_confirmed")
        if linked:
            trial.try_unlock_after_verified_email(int(linked))
    return _page("Email confirmed", "You will get an email when a new version ships. You can close this page.")


def unsubscribe_updates():
    from itsdangerous import BadSignature, SignatureExpired
    token = (request.args.get("t") or "").strip()
    try:
        data = _optin_serializer().loads(token, max_age=365 * 24 * 3600)
    except (BadSignature, SignatureExpired):
        return _page("Link not valid", "This link is not valid.", 400)
    subscriber_id = int((data or {}).get("id") or 0)
    db = _db()
    try:
        row = db.execute(
            "SELECT id, unsubscribed_at FROM update_subscribers WHERE id = ?",
            (subscriber_id,),
        ).fetchone()
        if not row:
            return _page("Link not valid", "This link is not valid.", 400)
        if not (row["unsubscribed_at"] or ""):
            db.execute(
                "UPDATE update_subscribers SET unsubscribed_at = ? WHERE id = ?",
                (licence_v1.iso(_now()), subscriber_id),
            )
            db.commit()
            fresh = True
        else:
            fresh = False
    finally:
        db.close()
    if fresh:
        _count("free_optin_unsubscribed")
    return _page("Unsubscribed", "You will not get Node Control update email. You can close this page.")


def subscriber_rows(db):
    return [
        ("subscriber", int(row["id"]), row["email"] or "")
        for row in db.execute(
            """
            SELECT id, email FROM update_subscribers
            WHERE confirmed_at != '' AND unsubscribed_at = ''
              AND trim(email) != ''
            """
        )
    ]


def register(flask_app):
    flask_app.add_url_rule("/api/free/instant-key", "free_instant_key", instant_key, methods=["POST"])
    flask_app.add_url_rule(
        "/api/v1/app/free/claim", "v1_free_claim", claim, methods=["POST"]
    )
    flask_app.add_url_rule(
        "/api/v1/download/free/latest", "v1_free_latest_meta", latest_metadata, methods=["GET"]
    )
    flask_app.add_url_rule(
        "/api/v1/download/free/latest/<platform>",
        "v1_free_latest_download",
        latest_download,
        methods=["GET"],
    )
    flask_app.add_url_rule(
        "/api/free/updates/subscribe", "free_updates_subscribe", subscribe_updates, methods=["POST"]
    )
    flask_app.add_url_rule(
        "/api/free/updates/confirm", "free_updates_confirm", confirm_updates, methods=["GET"]
    )
    flask_app.add_url_rule(
        "/api/free/updates/unsubscribe", "free_updates_unsubscribe", unsubscribe_updates, methods=["GET"]
    )
