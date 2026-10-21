"""Tests for the 0.9.41 licence API. GitHub, Stripe, and SMTP are mocked."""

import hashlib
import json
import multiprocessing
import os
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone
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
        licence_v1.clear_flag_cache()
        db = get_db()
        for table in (
            "licenses", "pro_keys", "pro_subscriptions", "devices", "device_moves",
            "email_codes", "registrations", "telemetry_sessions", "telemetry_monthly",
            "server_flags", "release_cache", "rate_limits", "stripe_events",
        ):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()
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


if __name__ == "__main__":
    unittest.main()
