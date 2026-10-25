"""Tests for the 0.9.41 licence API. GitHub, Stripe, and SMTP are mocked."""

import hashlib
import json
import multiprocessing
import os
import secrets
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SMTP_USER"] = "tester@example.com"
os.environ["SMTP_PASS"] = "test-pass"
os.environ["FREE_DOWNLOADS_PAUSED"] = "false"
os.environ["KEY_ENCRYPTION_KEY"] = "22" * 32
os.environ["LEGACY_ALLOWLIST_SYNC"] = "false"
os.environ["RELEASES_READ_PAT"] = "ghp_releases_read"
os.environ["API_PUBLIC_URL"] = "https://api.nodecontrol.io"
os.environ["REGISTRATION_ALERT_EMAIL"] = "support@nodecontrol.io"

import app as api
import licence_v1
from app import app, get_db


def _test_limited():
    from flask import abort
    abort(429)


def _test_explode():
    raise RuntimeError("sql password=secret-value")


def _test_page_explode():
    raise RuntimeError("page-secret")


# Registered at import, before the first request. These paths exist only
# in the test process.
app.add_url_rule("/api/v1/__limited", "v1_test_limited", _test_limited, methods=["GET"])
app.add_url_rule("/api/v1/__explode", "v1_test_explode", _test_explode, methods=["GET"])
app.add_url_rule("/site-explode", "site_test_explode", _test_page_explode, methods=["GET"])


def _rate_child(db_path, bucket, limit, count, queue):
    """Run in a second process. The database path is passed in, not taken from import time."""
    os.environ["DB_PATH"] = db_path
    os.environ["FREE_DOWNLOADS_PAUSED"] = "false"
    os.environ["KEY_ENCRYPTION_KEY"] = "22" * 32
    try:
        import app as child_app
        import licence_v1 as v1
        child_app.app.config["DB_PATH"] = db_path
        child_app.init_db()
        child_app.migrate_db()
        allowed = 0
        for _ in range(count):
            ok, _wait = v1.consume_rate(bucket, limit, 3600)
            if ok:
                allowed += 1
    except Exception as exc:
        queue.put(("error", str(exc)))
        return
    queue.put(allowed)


HEX_A = "ab" * 32
HEX_B = "cd" * 32


def _release(tag="v0.9.41", digest=True, draft=False, sums=False):
    version = tag[1:]
    dmg = {"id": 101, "name": f"Node.Control.Free-{version}.dmg", "size": 11}
    exe = {"id": 102, "name": f"Node.Control.Free-{version}-Setup.exe", "size": 22}
    assets = [dmg, exe]
    if digest:
        dmg["digest"] = "sha256:" + HEX_A
        exe["digest"] = "sha256:" + HEX_B
    if sums:
        assets.append({"id": 201, "name": "SHA256SUMS", "size": 80})
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": False,
        "published_at": "2026-10-21T12:00:00Z",
        "body": "### Fixes\n- a fix",
        "assets": assets,
    }


class ReleaseFake:
    def __init__(self):
        self.urls = []
        self.fail = False
        self.draft = False
        self.digest = True
        self.sums = False

    def __call__(self, req, timeout=15, follow_redirects=True):
        url = req.full_url
        self.urls.append(url)
        if self.fail:
            return 503, {}, b""
        if "/releases/assets/201" in url:
            text = f"{HEX_A}  Node.Control.Free-0.9.41.dmg\n{HEX_B}  Node.Control.Free-0.9.41-Setup.exe\n"
            return 200, {}, text.encode()
        if "/releases/assets/" in url:
            asset = url.rstrip("/").split("/")[-1]
            kind = "mac" if asset == "101" else "win"
            return 302, {"Location": f"https://release-assets.githubusercontent.com/{kind}?sig=1"}, b""
        tag = "v0.9.42" if "/tags/v0.9.42" in url else "v0.9.41"
        payload = _release(tag, digest=self.digest, draft=self.draft, sums=self.sums)
        return 200, {}, json.dumps(payload).encode()


class V1Tests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.mail = []
        self.github = ReleaseFake()
        self.github_patch = patch.object(api, "_github_request", self.github)
        self.github_patch.start()
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        app.config["ADMIN_TOKEN"] = "test-admin-token"
        app.config["ADMIN_READ_TOKEN"] = ""
        app.config["MIN_SUPPORTED_VERSION_FREE"] = "0.9.41"
        app.config["MIN_SUPPORTED_VERSION_PRO"] = "0.9.41"
        db = get_db()
        for table in (
            "licenses", "pro_keys", "pro_subscriptions", "devices", "device_moves",
            "email_codes", "registrations", "telemetry_sessions", "telemetry_monthly",
            "server_flags", "release_cache", "rate_limits", "stripe_events",
            "download_events", "update_check_daily",
            "notices_sent", "notice_opt_outs", "purchase_intents",
        ):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()
        licence_v1.clear_flag_cache()
        self.free = self._insert_free()
        self.install_a = str(uuid.uuid4())
        self.install_b = str(uuid.uuid4())

    def tearDown(self):
        self.mail_patch.stop()
        self.github_patch.stop()

    def _send(self, to_email, subject, text_body, html_body):
        self.mail.append({"to": to_email, "subject": subject, "text": text_body})
        return True

    def _insert_free(self, code="NC-AB12-CD34", email="free@example.com", status="active"):
        db = get_db()
        db.execute(
            """
            INSERT INTO licenses (code, name, email, company, platform, tier, status, created_at)
            VALUES (?, 'Person', ?, '', 'macos', 'free', ?, '2026-10-21T00:00:00')
            """,
            (code, email, status),
        )
        db.commit()
        row_id = db.execute("SELECT id FROM licenses WHERE code = ?", (code,)).fetchone()["id"]
        db.close()
        return {"id": row_id, "code": code, "email": email}

    def _insert_pro(self, email="pro@example.com", status="active", source="stripe", sub_status="active"):
        plain = licence_v1.generate_pro_key()
        db = get_db()
        sub_id = "sub_test" if source == "stripe" else None
        if source == "stripe":
            db.execute(
                """
                INSERT INTO pro_subscriptions (
                    email, stripe_subscription_id, plan, status, cancel_at_period_end,
                    current_period_end, created_at, updated_at
                ) VALUES (?, 'sub_test', 'monthly', ?, 0, '2026-11-21T00:00:00', '2026-10-21T00:00:00', '2026-10-21T00:00:00')
                """,
                (email, sub_status),
            )
        now = licence_v1.iso(licence_v1.utcnow())
        db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, reveal_blob, email, subscription_id, source, status,
                plan, created_at, reveal_until
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', 'monthly', ?, ?)
            """,
            (
                licence_v1.hash_key(plain), plain[-4:], licence_v1.encrypt_secret(plain),
                email, sub_id, source, now, now,
            ),
        )
        db.commit()
        db.close()
        return plain

    def _headers(self, key, install, version="0.9.41", tier="free", platform="mac", arch="arm64"):
        return {
            "Authorization": f"Bearer {key}",
            "X-NC-Install-Id": install,
            "User-Agent": f"NodeControl/{version} ({tier}; {platform}; {arch})",
            "Content-Type": "application/json",
        }

    def _activate(self, key, install, tier="free", version="0.9.41"):
        return self.client.post(
            "/api/v1/app/activate",
            json={"tier": tier, "app_version": version, "platform": "mac", "arch": "arm64"},
            headers=self._headers(key, install, version=version, tier=tier),
        )

    def _body(self, response):
        return response.get_json()

    def test_status_is_public(self):
        res = self.client.get("/api/v1/status")
        self.assertEqual(res.status_code, 200)
        body = self._body(res)
        self.assertFalse(body["free_downloads_paused"])
        self.assertEqual(body["min_supported_version"]["free"], "0.9.41")
        self.assertNotIn("lease", body)
        self.assertEqual(res.headers["X-NC-API-Version"], "1")
        self.assertIn("max-age=60", res.headers["Cache-Control"])
        self.assertTrue(body["latest_version"]["free"])

    def test_auth_and_validation_errors(self):
        missing = self.client.post("/api/v1/app/activate", json={})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(self._body(missing)["error"]["code"], "missing_key")

        bad = self._activate("NC-NOPE-NOPE", self.install_a)
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(self._body(bad)["error"]["code"], "invalid_key")

        self._insert_free("NC-REV1-REV1", status="revoked")
        revoked = self._activate("NC-REV1-REV1", self.install_a)
        self.assertEqual(revoked.status_code, 403)
        self.assertEqual(self._body(revoked)["error"]["code"], "revoked")

        mismatch = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "pro", "app_version": "0.9.41", "platform": "mac", "arch": "arm64"},
            headers=self._headers(self.free["code"], self.install_a, tier="pro"),
        )
        self.assertEqual(mismatch.status_code, 403)
        self.assertEqual(self._body(mismatch)["error"]["code"], "tier_mismatch")

        bad_version = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "free", "app_version": "0.9", "platform": "mac", "arch": "arm64"},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(bad_version.status_code, 400)
        self.assertEqual(self._body(bad_version)["error"]["code"], "bad_version")

        bad_platform = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "free", "app_version": "0.9.41", "platform": "linux", "arch": "arm64"},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(bad_platform.status_code, 400)
        self.assertEqual(self._body(bad_platform)["error"]["code"], "bad_platform")

        malformed = self.client.post(
            "/api/v1/app/activate",
            data=b"{",
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(self._body(malformed)["error"]["code"], "bad_request")

        huge = self.client.post(
            "/api/v1/app/telemetry",
            data=b'{"schema":1' + b" " * (16 * 1024),
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(huge.status_code, 413)
        self.assertEqual(self._body(huge)["error"]["code"], "payload_too_large")

        missing_path = self.client.get("/api/v1/download/free/linux")
        self.assertEqual(missing_path.status_code, 404)
        self.assertEqual(self._body(missing_path)["error"]["code"], "not_found")

    def test_upgrade_required_except_update_and_download(self):
        old = self._activate(self.free["code"], self.install_a, version="0.9.40")
        self.assertEqual(old.status_code, 426)
        self.assertEqual(self._body(old)["error"]["code"], "upgrade_required")
        self.assertIn("latest_version", self._body(old)["error"]["details"])

        self._activate(self.free["code"], self.install_a)
        checked = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.40", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a, version="0.9.40"),
        )
        self.assertEqual(checked.status_code, 200)
        self.assertTrue(checked.get_json()["force_update"])
        licence = self.client.post(
            "/api/v1/app/licence/check",
            json={"tier": "free", "app_version": "0.9.41", "platform": "mac", "arch": "arm64"},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(licence.status_code, 200)
        self.assertIsNone(licence.get_json()["lease"])
        self.assertIsNone(licence.get_json()["lease_format"])

        downloaded = self.client.post(
            "/api/v1/app/download",
            json={"version": "latest", "platform": "mac"},
            headers=self._headers(self.free["code"], self.install_a, version="0.9.40"),
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.get_json()["sha256"], HEX_A)

    def test_device_binding_move_limit_and_admin_reset(self):
        first = self._activate(self.free["code"], self.install_a)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["licence"]["lease"] is None)
        self.assertIsNone(first.get_json()["licence"]["lease_format"])
        self.assertIsNone(first.get_json()["licence"]["plan"])

        second = self._activate(self.free["code"], self.install_b)
        self.assertEqual(second.status_code, 403)
        details = self._body(second)["error"]["details"]
        self.assertEqual(self._body(second)["error"]["code"], "device_not_active")
        self.assertTrue(details["can_move"])
        self.assertEqual(details["moves_remaining"], 2)

        check = self.client.post(
            "/api/v1/app/licence/check",
            json={"tier": "free", "app_version": "0.9.41", "platform": "win", "arch": "x86_64"},
            headers=self._headers(self.free["code"], self.install_b, platform="win", arch="x86_64"),
        )
        self.assertEqual(check.status_code, 403)
        self.assertEqual(self._body(check)["error"]["code"], "device_not_active")

        moved = self.client.post(
            "/api/v1/app/device/move",
            json={},
            headers=self._headers(self.free["code"], self.install_b),
        )
        self.assertEqual(moved.status_code, 202)
        self.assertTrue(moved.get_json()["code_sent"])
        self.assertIn("•••", moved.get_json()["sent_to"])
        code = self.mail[-1]["text"].split("Code: ", 1)[1][:6]
        wrong = self.client.post(
            "/api/v1/app/device/move/confirm",
            json={"code": "000000"},
            headers=self._headers(self.free["code"], self.install_b),
        )
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(self._body(wrong)["error"]["code"], "code_invalid")
        self.assertEqual(self._body(wrong)["error"]["details"]["attempts_remaining"], 4)

        confirmed = self.client.post(
            "/api/v1/app/device/move/confirm",
            json={"code": code},
            headers=self._headers(self.free["code"], self.install_b),
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.get_json()["moves_remaining"], 1)
        self.assertIsNone(confirmed.get_json()["licence"]["lease"])

        # deactivate then activate counts the second move, then the next one is refused
        off = self.client.post(
            "/api/v1/app/device/deactivate",
            json={},
            headers=self._headers(self.free["code"], self.install_b),
        )
        self.assertEqual(off.status_code, 200)
        again = self._activate(self.free["code"], self.install_a)
        self.assertEqual(again.status_code, 200)
        off_a = self.client.post(
            "/api/v1/app/device/deactivate",
            json={},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(off_a.status_code, 200)
        blocked = self._activate(self.free["code"], self.install_b)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(self._body(blocked)["error"]["code"], "move_limit")
        self.assertIn("next_move_at", self._body(blocked)["error"]["details"])

        reset = self.client.post(
            "/api/admin/devices/" + self.free["code"] + "/reset",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(reset.status_code, 200)
        fresh = self._activate(self.free["code"], self.install_b)
        self.assertEqual(fresh.status_code, 200)

    def test_updates_downloads_and_free_pause(self):
        self._activate(self.free["code"], self.install_a)
        pro = self._insert_pro()
        pro_install = str(uuid.uuid4())
        self.assertEqual(self._activate(pro, pro_install, tier="pro").status_code, 200)
        self.github.urls.clear()
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        pro_check = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "pro", "current_version": "0.9.41", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(pro, pro_install, tier="pro"),
        )
        self.assertEqual(pro_check.status_code, 200)
        self.assertTrue(any("node-control-releases-pro" in url for url in self.github.urls))
        self.assertFalse(any("node-control-releases-free" in url for url in self.github.urls))

        self.github.urls.clear()
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        free_check = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "win",
                "arch": "x86_64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a, platform="win", arch="x86_64"),
        )
        self.assertEqual(free_check.status_code, 200)
        self.assertEqual(free_check.get_json()["asset"]["sha256"], HEX_B)
        self.assertTrue(any("node-control-releases-free" in url for url in self.github.urls))

        self.github.digest = False
        self.github.sums = True
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        summed = self.client.post(
            "/api/v1/app/download",
            json={"version": "0.9.41", "platform": "mac"},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(summed.status_code, 200)
        self.assertEqual(summed.get_json()["sha256"], HEX_A)
        self.assertNotIn("ghp_releases_read", summed.get_json()["url"])

        self.github.sums = False
        self.github.digest = False
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        bare = self.client.post(
            "/api/v1/app/download",
            json={"version": "latest", "platform": "mac"},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(bare.status_code, 503)
        self.assertEqual(self._body(bare)["error"]["code"], "upstream_unavailable")

        self.github.digest = True
        self.github.draft = True
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        draft = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(draft.status_code, 404)
        self.assertEqual(self._body(draft)["error"]["code"], "no_release")

        licence_v1.set_flag("free_downloads_paused", "true")
        self.github.draft = False
        self.github.fail = False
        paused_check = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(paused_check.status_code, 200)
        self.assertTrue(paused_check.get_json()["paused"])
        self.assertFalse(paused_check.get_json()["update_available"])
        paused_dl = self.client.post(
            "/api/v1/app/download",
            json={"version": "latest", "platform": "mac"},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(paused_dl.status_code, 503)
        self.assertEqual(self._body(paused_dl)["error"]["code"], "free_paused")
        paused_form = self.client.post("/api/request-access", json={"name": "A", "email": "a@b.co"})
        self.assertEqual(paused_form.status_code, 503)
        self.assertEqual(self._body(paused_form)["error"]["code"], "free_paused")
        paused_redeem = self.client.post("/api/redeem", json={"code": self.free["code"]})
        self.assertEqual(paused_redeem.status_code, 503)
        token = licence_v1.make_free_download_token(self.free["id"], "mac")
        paused_get = self.client.get("/api/v1/download/free/mac?t=" + token)
        self.assertEqual(paused_get.status_code, 503)

        licence_v1.set_flag("free_downloads_paused", "false")
        self.github.digest = True
        self.github.draft = False
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        redeem = self.client.post("/api/redeem", json={"code": self.free["code"]})
        self.assertEqual(redeem.status_code, 200)
        downloads = redeem.get_json()["downloads"]
        self.assertIn("/api/v1/download/free/mac?t=", downloads["mac"])
        self.assertIn("/api/v1/download/free/win?t=", downloads["win"])
        self.assertTrue(downloads["mac"].startswith("https://api.nodecontrol.io/"))
        followed = self.client.get(downloads["mac"].split(".io", 1)[1])
        self.assertEqual(followed.status_code, 302)
        self.assertIn("release-assets.githubusercontent.com", followed.location)
        db = get_db()
        kind = db.execute("SELECT kind FROM download_events").fetchone()["kind"]
        db.close()
        self.assertEqual(kind, "redirect")

        expired = licence_v1._free_serializer().dumps({
            "lic": self.free["id"], "platform": "mac", "exp": int(time.time()) - 5,
        })
        denied = self.client.get("/api/v1/download/free/mac?t=" + expired)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self._body(denied)["error"]["code"], "code_invalid")

    def test_pro_key_resend_and_inactive_subscription(self):
        plain = self._insert_pro()
        unknown = self.client.post("/api/v1/pro/key/resend", json={"email": "nobody@example.com"})
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(self.mail, [])
        known = self.client.post("/api/v1/pro/key/resend", json={"email": "pro@example.com"})
        self.assertEqual(known.status_code, 202)
        self.assertEqual(known.get_json()["code_sent"], True)
        code = self.mail[-1]["text"].split("Code: ", 1)[1][:6]
        for _ in range(4):
            bad = self.client.post(
                "/api/v1/pro/key/resend/confirm",
                json={"email": "pro@example.com", "code": "111111"},
            )
            self.assertEqual(bad.status_code, 403)
        last = self.client.post(
            "/api/v1/pro/key/resend/confirm",
            json={"email": "pro@example.com", "code": "111111"},
        )
        self.assertEqual(self._body(last)["error"]["details"]["attempts_remaining"], 0)
        # A fresh code still works and returns the same key.
        self.client.post("/api/v1/pro/key/resend", json={"email": "pro@example.com"})
        code = self.mail[-1]["text"].split("Code: ", 1)[1][:6]
        ok = self.client.post(
            "/api/v1/pro/key/resend/confirm",
            json={"email": "pro@example.com", "code": code},
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["licence_key"], plain)

        db = get_db()
        db.execute("UPDATE pro_subscriptions SET status = 'canceled' WHERE stripe_subscription_id = 'sub_test'")
        db.commit()
        db.close()
        inactive = self._activate(plain, str(uuid.uuid4()), tier="pro")
        self.assertEqual(inactive.status_code, 403)
        self.assertEqual(self._body(inactive)["error"]["code"], "subscription_inactive")

        manual = self.client.post(
            "/api/admin/pro-keys",
            json={"email": "beta@example.com"},
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(manual.status_code, 201)
        self.assertTrue(manual.get_json()["licence_key"].startswith("NCP-"))
        self.assertEqual(self._activate(manual.get_json()["licence_key"], str(uuid.uuid4()), tier="pro").status_code, 200)

    def test_same_pro_key_is_issued_once(self):
        first = licence_v1.ensure_stripe_pro_key("sub_once", "once@example.com", "annual")
        second = licence_v1.ensure_stripe_pro_key("sub_once", "once@example.com", "annual")
        self.assertEqual(first, second)
        db = get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM pro_keys").fetchone()["c"]
        db.close()
        self.assertEqual(count, 1)
        shown = licence_v1.reveal_pro_key_for_session("sub_once")
        self.assertTrue(shown.startswith("NCP-"))
        db = get_db()
        db.execute(
            "UPDATE pro_keys SET reveal_until = '2020-01-01T00:00:00Z' WHERE subscription_id = 'sub_once'"
        )
        db.commit()
        db.close()
        self.assertIsNone(licence_v1.reveal_pro_key_for_session("sub_once"))
        self.assertEqual(licence_v1.plaintext_for_subscription("sub_once"), shown)

    def test_registration_stays_in_the_database(self):
        self._activate(self.free["code"], self.install_a)
        self.github.urls.clear()
        payload = {
            "registration_token": str(uuid.uuid4()),
            "name": "Person",
            "email": "person@example.com",
            "org": "Example",
            "role": "Engineer",
            "app_version": "0.9.41",
            "os_family": "macOS",
            "os_major": "15",
            "arch": "arm64",
        }
        created = self.client.post(
            "/api/v1/app/register",
            json=payload,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(created.status_code, 201)
        again = self.client.post(
            "/api/v1/app/register",
            json=payload,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(again.status_code, 200)
        payload["email"] = "other@example.com"
        payload["registration_token"] = str(uuid.uuid4())
        clash = self.client.post(
            "/api/v1/app/register",
            json=payload,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(clash.status_code, 409)
        self.assertEqual(self._body(clash)["error"]["code"], "already_registered")
        self.assertTrue(any(item["to"] == "support@nodecontrol.io" for item in self.mail))
        self.assertFalse(any("api.github.com" in url for url in self.github.urls))

    def test_telemetry_drops_forbidden_fields_and_rolls_up(self):
        self._activate(self.free["code"], self.install_a)
        body = {
            "schema": 1,
            "session_id": "abcdef0123456789",
            "session_start_at": "2026-10-21T08:00:00Z",
            "last_flush_at": "2026-10-21T09:00:00Z",
            "app_version": "0.9.41",
            "tier": "free",
            "os_family": "macOS",
            "os_major": "15",
            "arch": "arm64",
            "session_duration_s": 10,
            "tasks": {"l2_topologies": 2, "not_a_real_counter": 4},
            "connections_opened": 3,
            "errors": 0,
            "user_name": "Hidden",
            "company": "Hidden Co",
            "hostname": "laptop",
            "machine_id": "hash",
            "machine_hash": "hash",
        }
        accepted = self.client.post(
            "/api/v1/app/telemetry",
            json=body,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(accepted.status_code, 202)
        body["session_duration_s"] = 25
        again = self.client.post(
            "/api/v1/app/telemetry",
            json=body,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(again.status_code, 202)
        db = get_db()
        rows = db.execute("SELECT * FROM telemetry_sessions").fetchall()
        self.assertEqual(len(rows), 1)
        stored = json.dumps(dict(rows[0]))
        self.assertNotIn("Hidden", stored)
        self.assertNotIn("laptop", stored)
        self.assertNotIn("machine", stored.lower())
        self.assertEqual(rows[0]["duration_s"], 25)
        self.assertEqual(json.loads(rows[0]["tasks_json"]), {"l2_topologies": 2})
        db.execute(
            "UPDATE telemetry_sessions SET last_received_at = '2020-01-01T00:00:00Z'"
        )
        db.commit()
        db.close()
        result = licence_v1.run_maintenance()
        self.assertEqual(result["telemetry_deleted"], 1)
        db = get_db()
        left = db.execute("SELECT COUNT(*) AS c FROM telemetry_sessions").fetchone()["c"]
        monthly = db.execute(
            "SELECT total FROM telemetry_monthly WHERE counter_name = 'l2_topologies'"
        ).fetchone()
        db.close()
        self.assertEqual(left, 0)
        self.assertEqual(monthly["total"], 2)

        self._activate(self.free["code"], self.install_a)
        kept = self.client.post(
            "/api/v1/app/telemetry",
            json=body,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(kept.status_code, 202)
        removed = self.client.delete(
            "/api/v1/app/telemetry",
            json={},
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(removed.status_code, 200)
        self.assertGreaterEqual(removed.get_json()["deleted"], 1)

    def test_telemetry_stores_the_extra_task_counters(self):
        self._activate(self.free["code"], self.install_a)
        expected = {
            "config_compliance_audits": 1,
            "config_compliance_remediations": 2,
            "hostname_refreshes": 3,
            "device_type_verifications": 4,
            "variable_discoveries": 5,
            "ise_password_changes": 6,
            "find_device_searches": 7,
        }
        guessed = {
            "compliance_audits": 11,
            "compliance_remediations": 12,
            "device_type_checks": 13,
            "variable_discovery": 14,
            "find_device": 15,
        }
        body = {
            "schema": 1,
            "session_id": "0123456789abcdef",
            "session_start_at": "2026-10-21T08:00:00Z",
            "last_flush_at": "2026-10-21T09:00:00Z",
            "app_version": "0.9.41",
            "tier": "free",
            "os_family": "Linux",
            "os_major": "6",
            "arch": "x86_64",
            "session_duration_s": 10,
            "tasks": {**expected, **guessed, "not_a_real_counter": 9},
            "connections_opened": 1,
            "errors": 0,
        }
        accepted = self.client.post(
            "/api/v1/app/telemetry",
            json=body,
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(accepted.status_code, 202)
        db = get_db()
        row = db.execute("SELECT tasks_json FROM telemetry_sessions").fetchone()
        db.close()
        stored = json.loads(row["tasks_json"])
        self.assertEqual(stored, expected)
        for name in guessed:
            self.assertNotIn(name, stored)

    def test_rate_limit_and_client_ip(self):
        for _ in range(10):
            res = self._activate(self.free["code"], self.install_a)
            self.assertEqual(res.status_code, 200)
        blocked = self._activate(self.free["code"], self.install_a)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(self._body(blocked)["error"]["code"], "rate_limited")
        self.assertIn("Retry-After", blocked.headers)

        for n in range(10):
            res = self._activate(f"NC-BAD{n}-XXXX", self.install_b)
            self.assertEqual(res.status_code, 401)
        flood = self._activate("NC-BAD9-XXXX", self.install_b)
        self.assertEqual(flood.status_code, 429)

        spoofed = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "free", "app_version": "0.9.41", "platform": "mac", "arch": "arm64"},
            headers={
                **self._headers("NC-SPO1-OFED", str(uuid.uuid4())),
                "CF-Connecting-IP": "203.0.113.50",
            },
            environ_base={"REMOTE_ADDR": "198.51.100.8"},
        )
        self.assertEqual(spoofed.status_code, 401)
        trusted = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "free", "app_version": "0.9.41", "platform": "mac", "arch": "arm64"},
            headers={
                **self._headers("NC-SPO2-OFED", str(uuid.uuid4())),
                "CF-Connecting-IP": "203.0.113.77",
            },
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(trusted.status_code, 401)
        db = get_db()
        buckets = [row["bucket"] for row in db.execute("SELECT bucket FROM rate_limits")]
        db.close()
        far = "badkey:ip:" + hashlib.sha256(b"198.51.100.8").hexdigest()
        header_ip = "badkey:ip:" + hashlib.sha256(b"203.0.113.50").hexdigest()
        tunnel = "badkey:ip:" + hashlib.sha256(b"203.0.113.77").hexdigest()
        self.assertIn(far, buckets)
        self.assertNotIn(header_ip, buckets)
        self.assertIn(tunnel, buckets)

    def test_rate_limit_is_shared_by_two_processes(self):
        bucket = "ep:shared-test:ip:" + hashlib.sha256(b"shared").hexdigest()
        queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_rate_child,
            args=(app.config["DB_PATH"], bucket, 6, 4, queue),
        )
        proc.start()
        local = 0
        for _ in range(4):
            ok, _wait = licence_v1.consume_rate(bucket, 6, 3600)
            if ok:
                local += 1
        proc.join(10)
        remote = queue.get(timeout=5)
        if isinstance(remote, tuple):
            self.fail(remote[1])
        self.assertEqual(local + remote, 6)

    def test_admin_flags_revoke_and_resync(self):
        denied = self.client.get("/api/admin/flags")
        self.assertEqual(denied.status_code, 401)
        headers = {"Authorization": "Bearer test-admin-token"}
        updated = self.client.put(
            "/api/admin/flags",
            json={
                "free_downloads_paused": True,
                "free_paused_message": "Paused for the update.",
            },
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()["free_downloads_paused"])
        self.assertEqual(updated.get_json()["free_paused_message"], "Paused for the update.")
        listed = self.client.get("/api/admin/flags", headers=headers)
        self.assertEqual(listed.status_code, 200)
        unknown = self.client.put(
            "/api/admin/flags",
            json={"nope": "1"},
            headers=headers,
        )
        self.assertEqual(unknown.status_code, 400)
        licence_v1.set_flag("free_downloads_paused", "false")

        issued = self.client.post(
            "/api/admin/pro-keys",
            json={"email": "beta2@example.com"},
            headers=headers,
        )
        self.assertEqual(issued.status_code, 201)
        key_id = issued.get_json()["id"]
        revoked = self.client.post(
            f"/api/admin/pro-keys/{key_id}/revoke",
            headers=headers,
        )
        self.assertEqual(revoked.status_code, 200)
        missing = self.client.post(
            f"/api/admin/pro-keys/{key_id}/revoke",
            headers=headers,
        )
        self.assertEqual(missing.status_code, 404)

        self._insert_pro(email="resync@example.com")
        with patch.object(
            api.stripe.Subscription,
            "retrieve",
            return_value={
                "id": "sub_test",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": 1795000000,
                "customer": "cus_test",
                "metadata": {},
                "items": {"data": []},
            },
        ):
            synced = self.client.post(
                "/api/admin/pro/resync",
                json={"subscription_id": "sub_test"},
                headers=headers,
            )
        self.assertEqual(synced.status_code, 200)
        self.assertEqual(synced.get_json()["status"], "active")

    def test_maintenance_flag(self):
        licence_v1.set_flag("maintenance", "true")
        res = self._activate(self.free["code"], self.install_a)
        self.assertEqual(res.status_code, 503)
        self.assertEqual(self._body(res)["error"]["code"], "maintenance")
        self.assertIn("Retry-After", res.headers)
        status = self.client.get("/api/v1/status")
        self.assertTrue(status.get_json()["maintenance"])
        licence_v1.set_flag("maintenance", "false")

    def _window_counts(self, endpoint, scope):
        prefix = f"ep:{endpoint}:{scope}:"
        db = get_db()
        rows = db.execute("SELECT bucket, count FROM rate_limits").fetchall()
        db.close()
        return {
            row["bucket"]: row["count"]
            for row in rows
            if row["bucket"].startswith(prefix)
        }

    def test_hourly_and_daily_limits_do_not_share_the_midnight_hour(self):
        # 00:30 UTC: the hour window and the day window start at the same second.
        moment = datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc)
        stamp = moment.timestamp()
        self.assertEqual(int(stamp) - (int(stamp) % 3600), int(stamp) - (int(stamp) % 86400))
        self._activate(self.free["code"], self.install_a)
        download = {
            "version": "latest",
            "platform": "mac",
        }
        with patch("licence_v1.time.time", return_value=stamp):
            statuses = []
            for _ in range(10):
                res = self.client.post(
                    "/api/v1/app/download",
                    json=download,
                    headers=self._headers(self.free["code"], self.install_a),
                )
                statuses.append(res.status_code)
            blocked = self.client.post(
                "/api/v1/app/download",
                json=download,
                headers=self._headers(self.free["code"], self.install_a),
            )
        self.assertEqual(statuses, [200] * 10)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(self._body(blocked)["error"]["code"], "rate_limited")
        hourly = self._window_counts("download", "key")
        daily = self._window_counts("download", "key-day")
        self.assertEqual(list(hourly.values()), [11])
        self.assertEqual(list(daily.values()), [11])
        self.assertIn(":3600:", next(iter(hourly)))
        self.assertIn(":86400:", next(iter(daily)))

        with patch("licence_v1.time.time", return_value=stamp):
            move_statuses = []
            for _ in range(3):
                res = self.client.post(
                    "/api/v1/app/device/move",
                    json={},
                    headers=self._headers(self.free["code"], self.install_b),
                )
                move_statuses.append(res.status_code)
            move_blocked = self.client.post(
                "/api/v1/app/device/move",
                json={},
                headers=self._headers(self.free["code"], self.install_b),
            )
        self.assertEqual(move_statuses, [202, 202, 202])
        self.assertEqual(move_blocked.status_code, 429)
        self.assertEqual(self._body(move_blocked)["error"]["code"], "rate_limited")
        move_hour = self._window_counts("move", "key")
        move_day = self._window_counts("move", "key-day")
        self.assertEqual(list(move_hour.values()), [4])
        self.assertEqual(list(move_day.values()), [4])
        self.assertTrue(all(":3600:" in bucket for bucket in move_hour))
        self.assertTrue(all(":86400:" in bucket for bucket in move_day))

    def test_api_errors_are_json_without_traces(self):
        missing = self.client.get("/api/v1/does-not-exist")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(self._body(missing)["error"]["code"], "not_found")
        self.assertTrue(self._body(missing)["request_id"])
        self.assertNotIn("Traceback", missing.get_data(as_text=True))

        wrong = self.client.post("/api/v1/status", json={})
        self.assertEqual(wrong.status_code, 405)
        self.assertEqual(self._body(wrong)["error"]["code"], "method_not_allowed")

        malformed = self.client.post(
            "/api/request-access",
            data=b"{",
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(self._body(malformed)["error"]["code"], "bad_request")
        self.assertNotIn("Traceback", malformed.get_data(as_text=True))

        legacy = self.client.post("/api/checkout", json={"plan": "weekly"})
        self.assertEqual(legacy.status_code, 400)
        self.assertEqual(legacy.get_json()["error"], "plan must be monthly or annual")

        page = self.client.get("/not-a-website-page")
        self.assertEqual(page.status_code, 404)
        self.assertIn("html", page.content_type)
        self.assertNotIn(b"request_id", page.data)

        previous_limit = app.config.get("MAX_CONTENT_LENGTH")
        app.config["MAX_CONTENT_LENGTH"] = 32
        try:
            huge = self.client.post(
                "/api/redeem",
                data=b"{" + b" " * 80,
                content_type="application/json",
            )
        finally:
            app.config["MAX_CONTENT_LENGTH"] = previous_limit
        self.assertEqual(huge.status_code, 413)
        self.assertEqual(self._body(huge)["error"]["code"], "payload_too_large")
        self.assertNotIn("Traceback", huge.get_data(as_text=True))

        capped = self.client.get("/api/v1/__limited")
        self.assertEqual(capped.status_code, 429)
        self.assertEqual(self._body(capped)["error"]["code"], "rate_limited")

        boom = self.client.get("/api/v1/__explode")
        body = boom.get_data(as_text=True)
        self.assertEqual(boom.status_code, 500)
        self.assertEqual(boom.get_json()["error"]["code"], "internal_error")
        self.assertNotIn("secret-value", body)
        self.assertNotIn("Traceback", body)

        page_boom = self.client.get("/site-explode")
        self.assertEqual(page_boom.status_code, 500)
        self.assertIn("html", page_boom.content_type)
        self.assertNotIn(b"internal_error", page_boom.data)
        self.assertNotIn(b"page-secret", page_boom.data)

    def test_internal_error_when_move_mail_fails(self):
        self._activate(self.free["code"], self.install_a)
        self.mail_patch.stop()
        failed = patch.object(api, "_send_mail", return_value=False)
        failed.start()
        try:
            res = self.client.post(
                "/api/v1/app/device/move",
                json={},
                headers=self._headers(self.free["code"], self.install_b),
            )
        finally:
            failed.stop()
            self.mail_patch.start()
        self.assertEqual(res.status_code, 500)
        self.assertEqual(self._body(res)["error"]["code"], "internal")

    def test_admin_read_token_is_rejected_on_writes(self):
        app.config["ADMIN_READ_TOKEN"] = "test-read-token"
        read = {"Authorization": "Bearer test-read-token"}
        write = {"Authorization": "Bearer test-admin-token"}
        try:
            for path in (
                "/api/admin/stats",
                "/api/admin/flags",
                "/api/admin/stats/v1",
            ):
                allowed = self.client.get(path, headers=read)
                self.assertEqual(allowed.status_code, 200, path)
                text = allowed.get_data(as_text=True)
                self.assertNotIn("free@example.com", text)
                self.assertNotIn(self.free["code"], text)
                self.assertNotIn(self.install_a, text)
                self.assertNotIn(self.install_b, text)
                also = self.client.get(path, headers=write)
                self.assertEqual(also.status_code, 200, path)
            self.assertEqual(
                self.client.get("/api/admin/licenses", headers=write).status_code, 200
            )
            self.assertEqual(
                self.client.get("/api/admin/pro-keys", headers=write).status_code, 200
            )
            denied = (
                ("GET", "/api/admin/licenses", None),
                ("GET", "/api/admin/pro-keys", None),
                ("PUT", "/api/admin/flags", {"maintenance": False}),
                ("POST", "/api/admin/pro-keys", {"email": "x@example.com"}),
                ("POST", "/api/admin/pro-keys/1/revoke", None),
                ("POST", "/api/admin/devices/" + self.free["code"] + "/reset", None),
                ("POST", "/api/admin/pro/resync", {"subscription_id": "sub_test"}),
                ("DELETE", "/api/admin/licenses/1", None),
            )
            for method, path, payload in denied:
                res = self.client.open(path, method=method, json=payload, headers=read)
                self.assertEqual(res.status_code, 401, path)
                self.assertEqual(res.get_json()["error"], "Unauthorized")
            placeholder = self.client.get(
                "/api/admin/stats/v1",
                headers={"Authorization": "Bearer change-me-in-production"},
            )
            self.assertEqual(placeholder.status_code, 401)
            self.assertEqual(self.client.get("/api/admin/stats/v1").status_code, 401)

            app.config["ADMIN_TOKEN"] = "change-me-in-production"
            app.config["ADMIN_READ_TOKEN"] = "change-me-in-production"
            disabled = self.client.get(
                "/api/admin/stats/v1",
                headers={"Authorization": "Bearer test-read-token"},
            )
            self.assertEqual(disabled.status_code, 503)

            app.config["ADMIN_TOKEN"] = ""
            app.config["ADMIN_READ_TOKEN"] = "test-read-token"
            still = self.client.get("/api/admin/stats/v1", headers=read)
            self.assertEqual(still.status_code, 200)
            hidden = self.client.get("/api/admin/pro-keys", headers=read)
            self.assertEqual(hidden.status_code, 503)
            self.assertEqual(hidden.get_json()["error"], "admin disabled")
            blocked = self.client.put(
                "/api/admin/flags",
                json={"maintenance": False},
                headers=read,
            )
            self.assertEqual(blocked.status_code, 503)
            self.assertEqual(blocked.get_json()["error"], "admin disabled")
        finally:
            app.config["ADMIN_TOKEN"] = "test-admin-token"
            app.config["ADMIN_READ_TOKEN"] = ""

    def test_update_check_daily_count_and_stats(self):
        api.migrate_db()
        api.migrate_db()
        missed = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(missed.status_code, 403)
        self._activate(self.free["code"], self.install_a)
        bad = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "linux",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(bad.status_code, 400)
        db = get_db()
        self.assertEqual(
            db.execute("SELECT COUNT(*) AS c FROM update_check_daily").fetchone()["c"], 0
        )
        db.close()

        self.github.fail = True
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        failed = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(failed.status_code, 503)
        self.github.fail = False
        db = get_db()
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        for _ in range(2):
            ok = self.client.post(
                "/api/v1/app/update-check",
                json={
                    "tier": "free", "current_version": "0.9.41", "platform": "mac",
                    "arch": "arm64", "channel": "stable",
                },
                headers=self._headers(self.free["code"], self.install_a),
            )
            self.assertEqual(ok.status_code, 200)
        db = get_db()
        cols = {row["name"] for row in db.execute("PRAGMA table_info(update_check_daily)")}
        row = db.execute(
            "SELECT day, tier, platform, app_version, count FROM update_check_daily"
        ).fetchone()
        db.close()
        self.assertEqual(cols, {"day", "tier", "platform", "app_version", "count"})
        self.assertEqual(row["count"], 3)
        self.assertEqual(row["tier"], "free")
        self.assertEqual(row["platform"], "mac")
        self.assertEqual(row["app_version"], "0.9.41")
        self.assertEqual(len(row["day"]), 10)

        with patch.object(api, "get_db", side_effect=RuntimeError("busy")):
            licence_v1.record_update_check("free", "mac", "0.9.41")

        listed = self.client.get(
            "/api/admin/stats/v1",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(listed.status_code, 200)
        checks = listed.get_json()["update_checks"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["tier"], "free")
        self.assertEqual(checks[0]["platform"], "mac")
        self.assertEqual(checks[0]["version"], "0.9.41")
        self.assertEqual(checks[0]["count"], 3)
        self.assertEqual(checks[0]["day"], row["day"])
        self.assertNotIn("month", checks[0])
        narrow = self.client.get(
            "/api/admin/stats/v1?since=2099-01-01&until=2099-01-02",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(narrow.get_json()["update_checks"], [])

    def test_stats_v1_counts_have_no_pii(self):
        plain = self._insert_pro()
        self._activate(self.free["code"], self.install_a)
        db = get_db()
        db.execute(
            """
            UPDATE licenses
            SET utm_source = 'newsletter', utm_medium = 'email', ip_address = '203.0.113.50'
            WHERE id = ?
            """,
            (self.free["id"],),
        )
        db.execute(
            """
            INSERT INTO licenses (
                code, name, email, company, platform, tier, status, created_at,
                utm_source, referrer, ip_address
            ) VALUES (
                'NC-REF1-REF1', 'Person', 'ref@example.com', '', 'macos', 'free', 'pending',
                '2026-10-21T00:00:00', '', 'example.com', '198.51.100.20'
            )
            """
        )
        db.execute(
            """
            INSERT INTO licenses (
                code, name, email, company, platform, tier, status, created_at, ip_address
            ) VALUES (
                'NC-DIR1-DIR1', 'Person', 'direct@example.com', '', 'macos', 'free', 'pending',
                '2026-10-21T00:00:00', '192.0.2.10'
            )
            """
        )
        db.execute(
            """
            INSERT INTO device_moves (
                licence_kind, licence_ref, from_install_id, to_install_id, moved_at
            ) VALUES ('free', ?, 'from-install', ?, '2026-10-21T01:00:00Z')
            """,
            (self.free["id"], self.install_a),
        )
        db.execute(
            """
            INSERT INTO registrations (
                licence_kind, licence_ref, install_id, registration_token, name, email, created_at
            ) VALUES ('free', ?, ?, 'tok-1', 'Person', 'reg@example.com', '2026-10-21T02:00:00Z')
            """,
            (self.free["id"], self.install_a),
        )
        db.execute(
            """
            INSERT INTO telemetry_sessions (
                licence_ref, licence_kind, install_id, session_id, tier, app_version, os_family,
                first_received_at, last_received_at
            ) VALUES (?, 'free', ?, 'abcdabcdabcdabcd', 'free', '0.9.41', 'mac', ?, ?)
            """,
            (self.free["id"], self.install_a, "2026-10-21T03:00:00Z", "2026-10-21T03:00:00Z"),
        )
        db.execute(
            """
            INSERT INTO telemetry_monthly (
                month, tier, app_version, os_family, counter_name, total, session_count, install_count
            ) VALUES ('2026-10', 'free', '0.9.41', 'mac', 'errors', 4, 2, 1)
            """
        )
        db.execute(
            """
            INSERT INTO download_events (license_id, platform, kind, created_at)
            VALUES (?, 'mac', 'redirect', '2026-10-21T04:00:00Z')
            """,
            (self.free["id"],),
        )
        db.commit()
        db.close()

        res = self.client.get(
            "/api/admin/stats/v1",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(
            set(body),
            {
                "window", "licences", "pro_keys", "device_moves", "devices",
                "registrations", "telemetry", "usage", "downloads", "update_checks",
                "flags", "db_bytes", "generated_at",
            },
        )
        text = res.get_data(as_text=True)
        secrets = (
            "free@example.com", "pro@example.com", "ref@example.com",
            "direct@example.com", "reg@example.com", plain, self.free["code"],
            "NC-REF1-REF1", "NC-DIR1-DIR1", self.install_a,
            "203.0.113.50", "198.51.100.20", "192.0.2.10", "tok-1",
            "from-install", "abcdabcdabcdabcd",
        )
        for secret in secrets:
            self.assertNotIn(secret, text)
        self.assertNotIn("device_resets", text)
        self.assertNotIn("moves_requested", text)
        self.assertNotIn("opt_out", text)
        self.assertNotIn("rate_limit", text)

        sources = {(row["tier"], row["status"], row["source"]): row["count"] for row in body["licences"]}
        self.assertEqual(sources[("free", "active", "newsletter")], 1)
        self.assertEqual(sources[("free", "pending", "ref:example.com")], 1)
        self.assertEqual(sources[("free", "pending", "(direct)")], 1)
        for row in body["licences"]:
            self.assertEqual(set(row), {"tier", "status", "source", "count"})
        self.assertEqual(body["pro_keys"], [{"status": "active", "plan": "monthly", "count": 1}])
        self.assertEqual(body["device_moves"], [{"tier": "free", "status": "confirmed", "count": 1}])
        self.assertNotIn("activations", body)
        self.assertEqual(body["devices"], [{"tier": "free", "platform": "mac", "count": 1}])
        self.assertEqual(body["registrations"], 1)
        self.assertIsInstance(body["registrations"], int)
        sessions = [row for row in body["telemetry"] if row["status"] == "sessions"]
        installs = [row for row in body["telemetry"] if row["status"] == "installs"]
        rollups = [row for row in body["telemetry"] if row["status"] == "rollups"]
        self.assertEqual(sessions, [{
            "status": "sessions", "tier": "free", "version": "0.9.41", "os": "mac", "count": 1,
        }])
        self.assertEqual(installs, [{"status": "installs", "tier": "free", "count": 1}])
        self.assertEqual(rollups, [{
            "status": "rollups", "month": "2026-10", "tier": "free",
            "version": "0.9.41", "os": "mac", "count": 2,
        }])
        self.assertEqual(body["downloads"], [{"tier": "free", "platform": "mac", "count": 1}])
        self.assertEqual(body["update_checks"], [])
        self.assertIsInstance(body["db_bytes"], int)
        self.assertGreater(body["db_bytes"], 0)
        self.assertTrue(body["generated_at"].endswith("Z"))
        self.assertFalse(body["flags"]["free_downloads_paused"])
        self.assertEqual(body["flags"]["min_supported_version_free"], "0.9.41")
        self.assertEqual(body["window"]["since"], "0000-01-01")
        app.config["ADMIN_READ_TOKEN"] = "test-read-token"
        try:
            read = {"Authorization": "Bearer test-read-token"}
            for path in ("/api/admin/stats", "/api/admin/stats/v1", "/api/admin/flags"):
                viewed = self.client.get(path, headers=read)
                self.assertEqual(viewed.status_code, 200, path)
                payload = viewed.get_data(as_text=True)
                for secret in secrets:
                    self.assertNotIn(secret, payload, path)
            locked = self.client.get("/api/admin/pro-keys", headers=read)
            self.assertEqual(locked.status_code, 401)
            self.assertNotIn("pro@example.com", locked.get_data(as_text=True))
            self.assertNotIn(plain, locked.get_data(as_text=True))
        finally:
            app.config["ADMIN_READ_TOKEN"] = ""
        bad = self.client.get(
            "/api/admin/stats/v1?since=nope",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(bad.status_code, 400)

    def test_admin_stats_usage_is_counts_only(self):
        headers = {"Authorization": "Bearer test-admin-token"}
        locked = self.client.get("/api/admin/stats/v1")
        self.assertEqual(locked.status_code, 401)
        wrong = self.client.get(
            "/api/admin/stats/v1",
            headers={"Authorization": "Bearer no-such-token"},
        )
        self.assertEqual(wrong.status_code, 401)

        empty = self.client.get("/api/admin/stats/v1", headers=headers)
        self.assertEqual(empty.status_code, 200)
        usage = empty.get_json()["usage"]
        self.assertEqual(usage["active_installs"]["1"], {"free": 0, "pro": 0, "ai": 0})
        self.assertEqual(usage["active_installs"]["7"], {"free": 0, "pro": 0, "ai": 0})
        self.assertEqual(usage["active_installs"]["30"], {"free": 0, "pro": 0, "ai": 0})
        self.assertEqual(len(usage["sessions_per_day"]), 30)
        self.assertEqual(sum(day["sessions"] for day in usage["sessions_per_day"]), 0)
        self.assertEqual(usage["tasks"], {})
        self.assertEqual(usage["session_length"], {"median_s": 0, "p90_s": 0, "total_hours": 0})
        self.assertEqual(usage["connections"], 0)
        self.assertEqual(usage["errors"], 0)
        self.assertEqual(usage["installs_by_app_version"], {})
        self.assertEqual(usage["installs_by_os"], {})
        self.assertEqual(usage["installs_by_os_version"], {})
        self.assertEqual(usage["installs_by_chip"], {})
        self.assertNotIn("opt_out", empty.get_data(as_text=True))

        now = datetime.now(timezone.utc).replace(microsecond=0)

        def stamp(days_ago):
            return (now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

        def day(days_ago):
            return (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        rows = (
            ("inst-1", "s111111111111111", "free", "1.2.3", "Linux", "6", "x86_64", 0, 10, 1, 1,
             json.dumps({"l2_topologies": 3, "health_checks": 0})),
            ("inst-1", "s222222222222222", "free", "1.2.3", "Linux", "6", "x86_64", 10, 20, 2, 0,
             json.dumps({"l2_topologies": 1})),
            ("inst-2", "s333333333333333", "pro", "1.2.3", "Linux", "6", "arm64", 0, 30, 4, 2,
             json.dumps({"config_backups": 2, "skipped": "nope"})),
            ("inst-3", "s444444444444444", "ai", "2.0.0", "macOS", "15", "arm64", 20, 40, 0, 0,
             "not-json"),
            ("inst-4", "s555555555555555", "free", "9.9.9", "Linux", "5", "x86_64", 40, 100, 8, 3,
             json.dumps({"find_device": 4})),
        )
        db = get_db()
        for install, session, tier, version, os_family, os_major, arch, days_ago, duration, connections, errors, tasks in rows:
            moment = stamp(days_ago)
            db.execute(
                """
                INSERT INTO telemetry_sessions (
                    licence_ref, licence_kind, install_id, session_id, tier, app_version,
                    os_family, os_major, arch, session_start_date, duration_s,
                    connections_opened, errors, tasks_json, first_received_at, last_received_at
                ) VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tier, install, session, tier, version, os_family, os_major, arch,
                    day(days_ago), duration, connections, errors, tasks, moment, moment,
                ),
            )
        db.execute(
            """
            INSERT INTO telemetry_monthly (
                month, tier, app_version, os_family, counter_name, total, session_count, install_count
            ) VALUES
                ('2026-01', 'free', '1.2.3', 'Linux', 'l2_topologies', 10, 4, 2),
                ('2026-01', 'free', '1.2.3', 'Linux', 'duration_s', 1600, 4, 2),
                ('2026-01', 'free', '1.2.3', 'Linux', 'connections_opened', 5, 4, 2),
                ('2026-01', 'free', '1.2.3', 'Linux', 'errors', 6, 4, 2)
            """
        )
        db.commit()
        db.close()

        app.config["ADMIN_READ_TOKEN"] = "test-read-token"
        try:
            res = self.client.get(
                "/api/admin/stats/v1",
                headers={"Authorization": "Bearer test-read-token"},
            )
        finally:
            app.config["ADMIN_READ_TOKEN"] = ""
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        usage = body["usage"]
        self.assertEqual(usage["active_installs"]["1"], {"free": 1, "pro": 1, "ai": 0})
        self.assertEqual(usage["active_installs"]["7"], {"free": 1, "pro": 1, "ai": 0})
        self.assertEqual(usage["active_installs"]["30"], {"free": 1, "pro": 1, "ai": 1})
        by_day = {item["day"]: item["sessions"] for item in usage["sessions_per_day"]}
        self.assertEqual(len(by_day), 30)
        self.assertEqual(by_day[day(0)], 2)
        self.assertEqual(by_day[day(10)], 1)
        self.assertEqual(by_day[day(20)], 1)
        self.assertNotIn(day(40), by_day)
        self.assertEqual(usage["tasks"]["l2_topologies"], {"uses": 14, "sessions": 6, "installs": 3})
        self.assertEqual(usage["tasks"]["config_backups"], {"uses": 2, "sessions": 1, "installs": 1})
        self.assertEqual(usage["tasks"]["find_device"], {"uses": 4, "sessions": 1, "installs": 1})
        self.assertNotIn("health_checks", usage["tasks"])
        self.assertNotIn("skipped", usage["tasks"])
        self.assertEqual(usage["session_length"]["median_s"], 30)
        self.assertEqual(usage["session_length"]["p90_s"], 100)
        self.assertEqual(usage["session_length"]["total_hours"], 0.5)
        self.assertEqual(usage["connections"], 20)
        self.assertEqual(usage["errors"], 12)
        self.assertEqual(usage["installs_by_app_version"], {"1.2.3": 2, "2.0.0": 1, "9.9.9": 1})
        self.assertEqual(usage["installs_by_os"], {"Linux": 3, "macOS": 1})
        self.assertEqual(usage["installs_by_os_version"], {"5": 1, "6": 2, "15": 1})
        self.assertEqual(usage["installs_by_chip"], {"arm64": 2, "x86_64": 2})
        text = res.get_data(as_text=True)
        for secret in ("inst-1", "inst-2", "inst-3", "inst-4", "s111111111111111"):
            self.assertNotIn(secret, text)
        self.assertNotIn("opt_out", text)
        self.assertIn("telemetry", body)
        self.assertIn("licences", body)

    def test_minimum_version_is_unset_or_capped_to_the_release(self):
        app.config["MIN_SUPPORTED_VERSION_FREE"] = ""
        app.config["MIN_SUPPORTED_VERSION_PRO"] = ""
        licence_v1.clear_flag_cache()
        status = self.client.get("/api/v1/status")
        self.assertIsNone(status.get_json()["min_supported_version"]["free"])
        self.assertIsNone(status.get_json()["min_supported_version"]["pro"])
        old = self._activate(self.free["code"], self.install_a, version="0.9.40")
        self.assertEqual(old.status_code, 200)
        checked = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.40", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a, version="0.9.40"),
        )
        self.assertEqual(checked.status_code, 200)
        self.assertIsNone(checked.get_json()["min_supported_version"])
        self.assertFalse(checked.get_json()["force_update"])

        db = get_db()
        db.execute("DELETE FROM devices")
        db.execute("DELETE FROM release_cache")
        db.commit()
        db.close()
        app.config["MIN_SUPPORTED_VERSION_FREE"] = "0.9.42"
        app.config["MIN_SUPPORTED_VERSION_PRO"] = "0.9.42"
        licence_v1.clear_flag_cache()
        licence_v1._cap_warned.clear()
        with self.assertLogs("licence_v1", level="WARNING") as logs:
            capped = self.client.get("/api/v1/status")
        self.assertEqual(capped.get_json()["min_supported_version"]["free"], "0.9.41")
        self.assertEqual(capped.get_json()["min_supported_version"]["pro"], "0.9.41")
        self.assertEqual(capped.get_json()["latest_version"]["free"], "0.9.41")
        self.assertTrue(any("0.9.42" in line and "0.9.41" in line for line in logs.output))

        current = self._activate(self.free["code"], self.install_a, version="0.9.41")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(
            current.get_json()["licence"]["update"]["min_supported_version"], "0.9.41"
        )
        self.assertFalse(current.get_json()["licence"]["update"]["force_update"])
        behind = self._activate(self.free["code"], self.install_b, version="0.9.40")
        self.assertEqual(behind.status_code, 426)
        looked = self.client.post(
            "/api/v1/app/update-check",
            json={
                "tier": "free", "current_version": "0.9.41", "platform": "mac",
                "arch": "arm64", "channel": "stable",
            },
            headers=self._headers(self.free["code"], self.install_a),
        )
        self.assertEqual(looked.status_code, 200)
        self.assertEqual(looked.get_json()["min_supported_version"], "0.9.41")
        self.assertFalse(looked.get_json()["force_update"])

    def _stripe_ready(self):
        app.config["STRIPE_SECRET_KEY"] = "sk_test_x"
        app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        app.config["STRIPE_PRICE_PRO_MONTHLY"] = "price_month"
        app.config["STRIPE_PRICE_PRO_ANNUAL"] = "price_year"
        app.config["SITE_URL"] = "https://nodecontrol.io"
        app.config["STRIPE_ALLOW_TEST_EVENTS"] = ""

    def _post_app_checkout(self, plan="monthly", key=None, install=None, headers=None):
        sent = headers or self._headers(key or self.free["code"], install or self.install_a)
        return self.client.post("/api/v1/app/checkout", json={"plan": plan}, headers=sent)

    def _post_purchase_status(self, intent_id, key=None, install=None, headers=None):
        sent = headers or self._headers(key or self.free["code"], install or self.install_a)
        return self.client.post(
            "/api/v1/app/purchase/status",
            json={"intent_id": intent_id},
            headers=sent,
        )

    def test_app_checkout_starts_a_session_for_this_install(self):
        self._stripe_ready()
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return {"url": "https://checkout.stripe.test/c/pay", "id": "cs_app_1"}

        with patch.object(api.stripe.checkout.Session, "create", side_effect=create):
            res = self._post_app_checkout(plan="annual")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["url"], "https://checkout.stripe.test/c/pay")
        self.assertEqual(len(body["intent_id"]), 32)
        self.assertTrue(body["expires_at"].endswith("Z"))
        self.assertEqual(captured["client_reference_id"], body["intent_id"])
        self.assertEqual(captured["metadata"]["intent_id"], body["intent_id"])
        self.assertEqual(captured["metadata"]["source"], "app")
        self.assertEqual(captured["metadata"]["plan"], "annual")
        self.assertEqual(captured["mode"], "subscription")
        self.assertEqual(captured["line_items"], [{"price": "price_year", "quantity": 1}])
        self.assertEqual(captured["customer_email"], "free@example.com")
        self.assertIn("pro-success.html?session_id={CHECKOUT_SESSION_ID}&from=app", captured["success_url"])
        self.assertTrue(captured["cancel_url"].endswith("/#pricing"))
        db = get_db()
        row = db.execute(
            "SELECT * FROM purchase_intents WHERE id = ?",
            (body["intent_id"],),
        ).fetchone()
        db.close()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["free_license_id"], self.free["id"])
        self.assertEqual(row["install_id"], self.install_a)
        self.assertEqual(row["plan"], "annual")
        self.assertEqual(row["stripe_session_id"], "cs_app_1")
        page = os.path.join(os.path.dirname(__file__), "..", "pro-success.html")
        with open(page, encoding="utf-8") as handle:
            html_page = handle.read()
        self.assertIn('id="proAppReturn"', html_page)
        self.assertIn("params.get('from') === 'app'", html_page)
        self.assertIn("go back to Node Control", html_page)

    def test_app_checkout_rejects_bad_callers_and_a_down_stripe(self):
        self._stripe_ready()
        missing = self.client.post("/api/v1/app/checkout", json={"plan": "monthly"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.get_json()["error"]["code"], "missing_key")

        bad_plan = self._post_app_checkout(plan="weekly")
        self.assertEqual(bad_plan.status_code, 400)
        self.assertEqual(bad_plan.get_json()["error"]["code"], "bad_request")

        pro_key = self._insert_pro()
        pro = self._post_app_checkout(key=pro_key, headers=self._headers(
            pro_key, self.install_a, tier="pro",
        ))
        self.assertEqual(pro.status_code, 403)
        self.assertEqual(pro.get_json()["error"]["code"], "tier_mismatch")

        db = get_db()
        before = db.execute("SELECT COUNT(*) AS c FROM purchase_intents").fetchone()["c"]
        db.close()
        self.assertEqual(before, 0)

        with patch.object(api.stripe.checkout.Session, "create", side_effect=RuntimeError("down")):
            failed = self._post_app_checkout()
        self.assertEqual(failed.status_code, 502)
        self.assertEqual(failed.get_json()["error"]["code"], "upstream")
        db = get_db()
        row = db.execute(
            "SELECT status FROM purchase_intents WHERE install_id = ?",
            (self.install_a,),
        ).fetchone()
        db.close()
        self.assertEqual(row["status"], "expired")
        seen = self._post_purchase_status("not-a-real-intent")
        self.assertEqual(seen.status_code, 404)
        db = get_db()
        intent_id = db.execute(
            "SELECT id FROM purchase_intents WHERE install_id = ?",
            (self.install_a,),
        ).fetchone()["id"]
        db.close()
        expired = self._post_purchase_status(intent_id)
        self.assertEqual(expired.status_code, 200)
        self.assertEqual(expired.get_json()["status"], "expired")
        self.assertNotIn("licence_key", expired.get_json())

    def test_webhook_links_the_upgrade_and_the_key_is_claimed_once(self):
        self._stripe_ready()
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return {"url": "https://checkout.stripe.test/c/pay", "id": "cs_app_link"}

        with patch.object(api.stripe.checkout.Session, "create", side_effect=create):
            started = self._post_app_checkout()
        self.assertEqual(started.status_code, 200)
        intent_id = started.get_json()["intent_id"]
        event = {
            "id": "evt_app_link",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_app_link",
                "mode": "subscription",
                "payment_status": "paid",
                "customer": "cus_1",
                "customer_email": "free@example.com",
                "customer_details": {"email": "free@example.com", "name": "Person"},
                "subscription": "sub_app_link",
                "client_reference_id": intent_id,
                "metadata": {"plan": "monthly", "intent_id": intent_id, "source": "app"},
            }},
        }
        sub = {
            "id": "sub_app_link",
            "status": "active",
            "customer": "cus_1",
            "current_period_end": 1800000000,
            "cancel_at_period_end": False,
            "metadata": {"plan": "monthly"},
        }
        with patch.object(api.stripe.Webhook, "construct_event", return_value=event), \
             patch.object(api.stripe.Subscription, "retrieve", return_value=sub):
            hook = self.client.post(
                "/api/stripe/webhook",
                data=json.dumps(event),
                headers={"Stripe-Signature": "good", "Content-Type": "application/json"},
            )
        self.assertEqual(hook.status_code, 200)
        self.assertTrue(any(item["to"] == "free@example.com" for item in self.mail))
        db = get_db()
        intent = db.execute(
            "SELECT * FROM purchase_intents WHERE id = ?",
            (intent_id,),
        ).fetchone()
        key = db.execute(
            "SELECT * FROM pro_keys WHERE subscription_id = 'sub_app_link'"
        ).fetchone()
        db.close()
        self.assertEqual(intent["status"], "paid")
        self.assertEqual(intent["pro_key_id"], key["id"])
        self.assertEqual(key["free_license_id"], self.free["id"])

        other = self._insert_free("NC-CD56-EF78", "other@example.com")
        wrong_install = self._post_purchase_status(intent_id, install=self.install_b)
        self.assertEqual(wrong_install.status_code, 404)
        self.assertNotIn("licence_key", wrong_install.get_json())
        wrong_licence = self._post_purchase_status(intent_id, key=other["code"])
        self.assertEqual(wrong_licence.status_code, 404)
        self.assertNotIn("NCP-", wrong_licence.get_data(as_text=True))
        db = get_db()
        still = db.execute(
            "SELECT status FROM purchase_intents WHERE id = ?",
            (intent_id,),
        ).fetchone()
        db.close()
        self.assertEqual(still["status"], "paid")

        first = self._post_purchase_status(intent_id)
        self.assertEqual(first.status_code, 200)
        paid = first.get_json()
        self.assertEqual(paid["status"], "paid")
        self.assertEqual(paid["plan"], "monthly")
        self.assertTrue(paid["licence_key"].startswith("NCP-"))
        second = self._post_purchase_status(intent_id)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json(), {"status": "claimed", "plan": "monthly"})
        self.assertNotIn(paid["licence_key"], second.get_data(as_text=True))

    def test_purchase_status_expires_without_returning_a_key(self):
        plain = self._insert_pro(email="payer@example.com")
        db = get_db()
        key_id = db.execute(
            "SELECT id FROM pro_keys WHERE email = 'payer@example.com'"
        ).fetchone()["id"]
        past = licence_v1.iso(licence_v1.utcnow() - timedelta(minutes=5))
        future = licence_v1.iso(licence_v1.utcnow() + timedelta(hours=2))
        now = licence_v1.iso(licence_v1.utcnow())
        db.execute(
            """
            INSERT INTO purchase_intents (
                id, free_license_id, install_id, plan, status, stripe_session_id,
                pro_key_id, created_at, updated_at, expires_at
            ) VALUES ('intent-past', ?, ?, 'monthly', 'paid', 'cs_past', ?, ?, ?, ?)
            """,
            (self.free["id"], self.install_a, key_id, now, now, past),
        )
        db.execute(
            """
            INSERT INTO purchase_intents (
                id, free_license_id, install_id, plan, status, stripe_session_id,
                pro_key_id, created_at, updated_at, expires_at
            ) VALUES ('intent-open', ?, ?, 'annual', 'paid', '', NULL, ?, ?, ?)
            """,
            (self.free["id"], self.install_a, now, now, future),
        )
        db.commit()
        db.close()

        expired = self._post_purchase_status("intent-past")
        self.assertEqual(expired.status_code, 200)
        self.assertEqual(expired.get_json(), {"status": "expired", "plan": "monthly"})
        self.assertNotIn(plain, expired.get_data(as_text=True))
        waiting = self._post_purchase_status("intent-open")
        self.assertEqual(waiting.get_json(), {"status": "pending", "plan": "annual"})
        db = get_db()
        past_row = db.execute(
            "SELECT status FROM purchase_intents WHERE id = 'intent-past'"
        ).fetchone()
        open_row = db.execute(
            "SELECT status FROM purchase_intents WHERE id = 'intent-open'"
        ).fetchone()
        db.close()
        self.assertEqual(past_row["status"], "expired")
        self.assertEqual(open_row["status"], "paid")

    def test_app_upgrade_rate_limits_and_refuses_a_test_key_when_the_flag_is_off(self):
        self._stripe_ready()
        headers = self._headers(self.free["code"], self.install_a)
        headers["CF-Connecting-IP"] = "203.0.113.80"

        def create(**kwargs):
            return {"url": "https://checkout.stripe.test/c/pay", "id": "cs_burst"}

        with patch.object(api.stripe.checkout.Session, "create", side_effect=create):
            for _ in range(10):
                ok = self.client.post(
                    "/api/v1/app/checkout", json={"plan": "monthly"}, headers=headers,
                )
                self.assertEqual(ok.status_code, 200)
            blocked = self.client.post(
                "/api/v1/app/checkout", json={"plan": "monthly"}, headers=headers,
            )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.get_json()["error"]["code"], "rate_limited")
        self.assertIn("Retry-After", blocked.headers)
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) AS c FROM purchase_intents WHERE install_id = ?",
            (self.install_a,),
        ).fetchone()["c"]
        db.close()
        self.assertEqual(count, 10)

        other = self._headers(self.free["code"], self.install_b)
        other["CF-Connecting-IP"] = "203.0.113.81"
        with patch.object(api.stripe.checkout.Session, "create", side_effect=create):
            still = self.client.post(
                "/api/v1/app/checkout", json={"plan": "monthly"}, headers=other,
            )
        self.assertEqual(still.status_code, 200)

        status_headers = self._headers(self.free["code"], self.install_a)
        status_headers["CF-Connecting-IP"] = "203.0.113.82"
        bucket = licence_v1._limit_bucket("purchase-status", "install", 3600, self.install_a)
        now = int(time.time())
        window = now - (now % 3600)
        db = get_db()
        db.execute(
            "INSERT INTO rate_limits (bucket, window_start, count) VALUES (?, ?, 600)",
            (bucket, window),
        )
        db.commit()
        db.close()
        limited = self.client.post(
            "/api/v1/app/purchase/status",
            json={"intent_id": "intent-limited"},
            headers=status_headers,
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.get_json()["error"]["code"], "rate_limited")
        self.assertIn("Retry-After", limited.headers)

        db = get_db()
        db.execute("DELETE FROM rate_limits")
        have = {row[1] for row in db.execute("PRAGMA table_info(pro_keys)")}
        if "is_test" not in have:
            db.execute("ALTER TABLE pro_keys ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
        plain = licence_v1.generate_pro_key()
        now_iso = licence_v1.iso(licence_v1.utcnow())
        future = licence_v1.iso(licence_v1.utcnow() + timedelta(hours=2))
        cursor = db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, reveal_blob, email, subscription_id, source, status,
                plan, created_at, reveal_until, is_test
            ) VALUES (?, ?, ?, 'payer@example.com', 'sub_test_mode', 'stripe', 'active',
                      'monthly', ?, ?, 1)
            """,
            (
                licence_v1.hash_key(plain), plain[-4:], licence_v1.encrypt_secret(plain),
                now_iso, now_iso,
            ),
        )
        key_id = cursor.lastrowid
        db.execute(
            """
            INSERT INTO purchase_intents (
                id, free_license_id, install_id, plan, status, stripe_session_id,
                pro_key_id, created_at, updated_at, expires_at
            ) VALUES ('intent-test', ?, ?, 'monthly', 'paid', 'cs_test_mode', ?, ?, ?, ?)
            """,
            (self.free["id"], self.install_a, key_id, now_iso, now_iso, future),
        )
        db.commit()
        db.close()
        app.config["STRIPE_ALLOW_TEST_EVENTS"] = ""
        refused = self._post_purchase_status("intent-test", headers=status_headers)
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(refused.get_json()["error"]["code"], "test_key")
        self.assertNotIn(plain, refused.get_data(as_text=True))
        db = get_db()
        self.assertEqual(
            db.execute("SELECT status FROM purchase_intents WHERE id = 'intent-test'").fetchone()["status"],
            "paid",
        )
        db.close()
        app.config["STRIPE_ALLOW_TEST_EVENTS"] = "1"
        try:
            allowed = self._post_purchase_status("intent-test", headers=status_headers)
        finally:
            app.config["STRIPE_ALLOW_TEST_EVENTS"] = ""
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.get_json()["licence_key"], plain)
        self.assertEqual(allowed.get_json()["status"], "paid")


if __name__ == "__main__":
    unittest.main()
