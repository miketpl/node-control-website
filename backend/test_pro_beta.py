"""First-install links for a hand-added Professional key.

Addresses in this file are example.com only. One key is one computer.
"""

import io
import logging
import os
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("SMTP_USER", "")
os.environ.setdefault("SMTP_PASS", "")
os.environ.setdefault("FREE_DOWNLOADS_PAUSED", "false")
os.environ.setdefault("KEY_ENCRYPTION_KEY", "11" * 32)
os.environ.setdefault("LEGACY_ALLOWLIST_SYNC", "false")
os.environ.setdefault("API_PUBLIC_URL", "https://api.nodecontrol.io")

import admin_cli
import alerts
import app as api
import licence_v1
from app import app, get_db


ASSET = "https://release-assets.githubusercontent.com/pro?sig=1"
ADMIN = "alerts@example.com"
ADDRESS = "beta@example.com"


class _InlineThread:
    started = 0

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self):
        type(self).started += 1
        self._target(*self._args, **self._kwargs)


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))
        if record.exc_info and record.exc_info[1] is not None:
            self.lines.append(repr(record.exc_info[1]))


class ProBetaTests(unittest.TestCase):
    def setUp(self):
        _InlineThread.started = 0
        self.mail = []
        self.client = app.test_client()
        self.thread_patch = patch.object(alerts.threading, "Thread", _InlineThread)
        self.thread_patch.start()
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        self._public = app.config.get("API_PUBLIC_URL")
        app.config["API_PUBLIC_URL"] = "https://api.nodecontrol.io"
        app.config["ADMIN_TOKEN"] = "test-admin-token"
        app.config["ADMIN_READ_TOKEN"] = ""
        app.config["ADMIN_ALERT_EMAIL"] = ""
        app.config["ADMIN_ALERT_SKIP_LICENCE_IDS"] = ""
        app.config["KEY_ENCRYPTION_KEY"] = "11" * 32
        app.config["FREE_DOWNLOADS_PAUSED"] = "false"
        licence_v1.set_flag("free_downloads_paused", "false")
        licence_v1.set_flag("maintenance", "false")
        licence_v1.clear_flag_cache()
        db = get_db()
        for table in (
            "pro_keys",
            "pro_subscriptions",
            "devices",
            "device_moves",
            "email_codes",
            "download_events",
            "admin_alert_log",
            "rate_limits",
            "licenses",
        ):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()

    def tearDown(self):
        self.mail_patch.stop()
        self.thread_patch.stop()
        app.config["API_PUBLIC_URL"] = self._public
        app.config["ADMIN_ALERT_EMAIL"] = ""
        app.config["ADMIN_READ_TOKEN"] = ""
        app.config["ADMIN_ALERT_SKIP_LICENCE_IDS"] = ""
        licence_v1.set_flag("free_downloads_paused", "false")
        licence_v1.set_flag("maintenance", "false")
        licence_v1.clear_flag_cache()

    def _send(self, to_email, subject, text_body, html_body, log_recipient=True):
        self.mail.append({
            "to": to_email,
            "subject": subject,
            "text": text_body,
            "html": html_body,
            "log_recipient": log_recipient,
        })
        return True

    def _admin(self):
        return {"Authorization": "Bearer test-admin-token"}

    def _headers(self, key, install):
        return {
            "Authorization": f"Bearer {key}",
            "X-NC-Install-Id": install,
            "User-Agent": "NodeControl/0.9.41 (pro; mac; arm64)",
            "Content-Type": "application/json",
        }

    def _issue(self, email=ADDRESS):
        res = self.client.post(
            "/api/admin/pro-keys",
            json={"email": email},
            headers=self._admin(),
        )
        self.assertEqual(res.status_code, 201, res.get_data(as_text=True))
        body = res.get_json()
        self.assertEqual(
            set(body),
            {"id", "email", "licence_key", "emailed", "source"},
        )
        self.assertEqual(body["email"], email)
        self.assertEqual(body["source"], "manual")
        self.assertTrue(body["emailed"])
        self.assertTrue(body["licence_key"].startswith("NCP-"))
        return body

    def _path(self, key_id, platform="mac"):
        token = licence_v1.make_pro_beta_download_token(key_id, platform)
        return f"/api/v1/download/pro/{platform}?t={token}"

    def _activate(self, key, install):
        return self.client.post(
            "/api/v1/app/activate",
            json={"tier": "pro", "app_version": "0.9.41", "platform": "mac", "arch": "arm64"},
            headers=self._headers(key, install),
        )

    def _check(self, key, install):
        return self.client.post(
            "/api/v1/app/licence/check",
            json={"tier": "pro", "app_version": "0.9.41", "platform": "mac", "arch": "arm64"},
            headers=self._headers(key, install),
        )

    def _clear_limits(self):
        db = get_db()
        db.execute("DELETE FROM rate_limits")
        db.execute("DELETE FROM email_codes")
        db.commit()
        db.close()

    def _recover(self, email):
        self._clear_limits()
        before = len(self.mail)
        sent = self.client.post("/api/v1/pro/key/resend", json={"email": email})
        self.assertEqual(sent.status_code, 202)
        self.assertEqual(sent.get_json()["code_sent"], True)
        self.assertGreater(len(self.mail), before)
        code = self.mail[-1]["text"].split("Code: ", 1)[1][:6]
        self.assertEqual(len(code), 6)
        confirmed = self.client.post(
            "/api/v1/pro/key/resend/confirm",
            json={"email": email, "code": code},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.get_data(as_text=True))
        body = confirmed.get_json()
        self.assertEqual(set(body), {"licence_key", "tier"})
        self.assertIsInstance(body["licence_key"], str)
        self.assertEqual(body["tier"], "pro")
        self.assertNotIn(email, self.mail[-1]["text"])
        self.assertNotIn(email, self.mail[-1]["html"])
        self.assertNotIn("@", self.mail[-1]["text"])
        self.assertNotIn("@", self.mail[-1]["html"])
        return body, self.mail[-1]

    def _insert_stripe(self, email, sub_status="active"):
        plain = licence_v1.generate_pro_key()
        sub_id = "sub_" + uuid.uuid4().hex[:12]
        now = licence_v1.iso(licence_v1.utcnow())
        db = get_db()
        db.execute(
            """
            INSERT INTO pro_subscriptions (
                email, stripe_subscription_id, plan, status, cancel_at_period_end,
                current_period_end, created_at, updated_at
            ) VALUES (?, ?, 'monthly', ?, 0, '2026-11-21T00:00:00Z', ?, ?)
            """,
            (email, sub_id, sub_status, now, now),
        )
        cursor = db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, reveal_blob, email, subscription_id, source, status,
                plan, created_at, reveal_until
            ) VALUES (?, ?, ?, ?, ?, 'stripe', 'active', 'monthly', ?, ?)
            """,
            (
                licence_v1.hash_key(plain),
                plain[-4:],
                licence_v1.encrypt_secret(plain),
                email,
                sub_id,
                now,
                now,
            ),
        )
        db.commit()
        key_id = cursor.lastrowid
        db.close()
        return plain, key_id

    def test_issue_email_links_the_installer(self):
        issued = self._issue()
        letter = self.mail[-1]
        self.assertEqual(letter["to"], ADDRESS)
        self.assertEqual(letter["subject"], "Your Node Control Professional key")
        text = letter["text"]
        html = letter["html"]
        self.assertIn("\n\n", text)
        self.assertIn("<p>", html)
        self.assertIn(issued["licence_key"], text)
        self.assertIn(issued["licence_key"], html)
        self.assertIn("/api/v1/download/pro/mac?t=", text)
        self.assertIn("/api/v1/download/pro/win?t=", text)
        self.assertIn("/api/v1/download/pro/mac?t=", html)
        self.assertIn("/api/v1/download/pro/win?t=", html)
        self.assertTrue(text.strip().endswith("Mike"))
        self.assertIn("<p>Mike</p>", html)
        for phrase in (
            "Install Node Control.",
            "Open Node Control.",
            "Enter the key in Welcome to Node Control.",
            "These links are for the first install. After that, the app updates itself.",
            "The links expire after 7 days.",
            "The key is active on one computer at a time.",
        ):
            self.assertIn(phrase, text)
            self.assertIn(phrase, html)
        self.assertNotIn("The Promised", text)
        self.assertNotIn("The Promised", html)
        self.assertNotIn(ADDRESS, text)
        self.assertNotIn(ADDRESS, html)
        self.assertNotIn("@", text)
        self.assertNotIn("@", html)

        mac = next(line for line in text.splitlines() if "/api/v1/download/pro/mac?t=" in line)
        path = mac.split(".io", 1)[1]
        with patch.object(api, "_pro_asset_redirect", return_value=ASSET) as redirect:
            followed = self.client.get(path)
        self.assertEqual(followed.status_code, 302)
        self.assertEqual(followed.location, ASSET)
        redirect.assert_called_once_with("mac")

        free_token = licence_v1.make_free_download_token(issued["id"], "mac")
        crossed = self.client.get("/api/v1/download/pro/mac?t=" + free_token)
        self.assertEqual(crossed.status_code, 403)
        self.assertEqual(crossed.get_json()["error"]["code"], "link_expired")
        pro_token = path.split("t=", 1)[1]
        other = self.client.get("/api/v1/download/free/mac?t=" + pro_token)
        self.assertEqual(other.status_code, 403)
        self.assertEqual(other.get_json()["error"]["code"], "code_invalid")

    def test_revoked_expired_and_foreign_keys(self):
        issued = self._issue()
        path = self._path(issued["id"])
        revoked = self.client.post(
            f"/api/admin/pro-keys/{issued['id']}/revoke",
            headers=self._admin(),
        )
        self.assertEqual(revoked.status_code, 200)
        with patch.object(api, "_pro_asset_redirect", return_value=ASSET) as redirect:
            denied = self.client.get(path)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["error"]["code"], "revoked")
        self.assertIn("revoked", denied.get_json()["error"]["message"])
        redirect.assert_not_called()

        fresh = self._issue("other@example.com")
        expired = licence_v1._pro_beta_serializer().dumps({
            "kid": fresh["id"],
            "platform": "mac",
            "exp": int(time.time()) - 5,
        })
        old = self.client.get("/api/v1/download/pro/mac?t=" + expired)
        self.assertEqual(old.status_code, 403)
        self.assertEqual(old.get_json()["error"]["code"], "link_expired")
        self.assertIn("expired", old.get_json()["error"]["message"])

        mismatched = self.client.get(self._path(fresh["id"], "mac").replace("/mac?", "/win?", 1))
        self.assertEqual(mismatched.status_code, 403)
        self.assertEqual(mismatched.get_json()["error"]["code"], "link_expired")

        missing = self.client.get("/api/v1/download/pro/linux")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["error"]["code"], "not_found")

        plain, stripe_id = self._insert_stripe("buyer@example.com")
        stripe_link = self.client.get(self._path(stripe_id))
        self.assertEqual(stripe_link.status_code, 403)
        self.assertEqual(stripe_link.get_json()["error"]["message"], "This download link is not valid.")
        self.assertNotIn(plain, stripe_link.get_data(as_text=True))

        db = get_db()
        db.execute("UPDATE pro_keys SET status = 'replaced' WHERE id = ?", (fresh["id"],))
        db.commit()
        db.close()
        replaced = self.client.get(self._path(fresh["id"]))
        self.assertEqual(replaced.status_code, 403)
        self.assertEqual(replaced.get_json()["error"]["message"], "This download link is not valid.")

        licence_v1.set_flag("maintenance", "true")
        licence_v1.clear_flag_cache()
        paused = self.client.get(self._path(fresh["id"]))
        self.assertEqual(paused.status_code, 503)
        self.assertEqual(paused.get_json()["error"]["code"], "maintenance")

    def test_rate_limit_ignores_the_free_pause(self):
        issued = self._issue()
        path = self._path(issued["id"])
        licence_v1.set_flag("free_downloads_paused", "true")
        licence_v1.clear_flag_cache()
        with patch.object(api, "_pro_asset_redirect", return_value=ASSET) as redirect:
            for _ in range(10):
                ok = self.client.get(path)
                self.assertEqual(ok.status_code, 302)
                self.assertEqual(ok.location, ASSET)
            blocked = self.client.get(path)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.get_json()["error"]["code"], "rate_limited")
        self.assertEqual(redirect.call_count, 10)

        with patch.object(api, "_pro_asset_redirect", side_effect=RuntimeError("github down")):
            self._clear_limits()
            down = self.client.get(path)
        self.assertEqual(down.status_code, 503)
        self.assertEqual(down.get_json()["error"]["code"], "upstream_unavailable")

    def test_download_is_recorded_and_alerted_once(self):
        issued = self._issue()
        path = self._path(issued["id"])
        app.config["ADMIN_ALERT_EMAIL"] = ADMIN
        with patch.object(api, "_pro_asset_redirect", return_value=ASSET):
            first = self.client.get(path)
            second = self.client.get(path)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        db = get_db()
        rows = db.execute(
            "SELECT license_id, platform, kind FROM download_events ORDER BY id"
        ).fetchall()
        db.close()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["license_id"], issued["id"])
            self.assertEqual(row["platform"], "mac")
            self.assertEqual(row["kind"], "pro_redirect")
        notes = [item for item in self.mail if item["subject"].startswith("[Node Control]")]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["subject"], "[Node Control] New Pro beta download")
        self.assertEqual(notes[0]["to"], ADMIN)
        self.assertIn("Event: Pro beta download", notes[0]["text"])
        self.assertIn("Tier: pro", notes[0]["text"])
        self.assertIn(f"Licence id: {issued['id']}", notes[0]["text"])
        self.assertIn("Version: unknown", notes[0]["text"])
        self.assertNotIn("Arch:", notes[0]["text"])
        self.assertNotIn("@", notes[0]["text"])
        self.assertNotIn("@", notes[0]["html"])
        self.assertNotIn(ADDRESS, notes[0]["text"])
        self.assertEqual(_InlineThread.started, 2)

        quiet = _InlineThread.started
        app.config["ADMIN_ALERT_EMAIL"] = ""
        with patch.object(api, "_pro_asset_redirect", return_value=ASSET):
            self._clear_limits()
            again = self.client.get(self._path(issued["id"], "win"))
        self.assertEqual(again.status_code, 302)
        self.assertEqual(_InlineThread.started, quiet)
        self.assertEqual(
            len([item for item in self.mail if item["subject"].startswith("[Node Control]")]),
            1,
        )

    def test_alert_and_record_failures_still_redirect(self):
        issued = self._issue("muted@example.com")
        path = self._path(issued["id"])
        app.config["ADMIN_ALERT_EMAIL"] = ADMIN
        logs = _LogCapture()
        logging.getLogger("alerts").addHandler(logs)
        logging.getLogger("licence_v1").addHandler(logs)

        def boom(*_args, **_kwargs):
            raise RuntimeError("smtp refused person@example.com")

        try:
            with patch.object(api, "_pro_asset_redirect", return_value=ASSET), \
                 patch.object(api, "_send_mail", side_effect=boom):
                res = self.client.get(path)
        finally:
            logging.getLogger("alerts").removeHandler(logs)
            logging.getLogger("licence_v1").removeHandler(logs)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.location, ASSET)
        logged = "\n".join(logs.lines)
        self.assertIn("Admin alert was not sent", logged)
        self.assertNotIn("person@example.com", logged)
        self.assertNotIn("smtp refused", logged)
        self.assertNotIn("@", logged)

        db = get_db()
        db.execute(
            """
            CREATE TRIGGER fail_pro_redirect
            BEFORE INSERT ON download_events
            WHEN NEW.kind = 'pro_redirect'
            BEGIN
                SELECT RAISE(ABORT, 'disk full');
            END
            """
        )
        db.commit()
        db.close()
        record_logs = _LogCapture()
        logging.getLogger("licence_v1").addHandler(record_logs)
        try:
            with patch.object(api, "_pro_asset_redirect", return_value=ASSET):
                self._clear_limits()
                kept = self.client.get(self._path(issued["id"], "win"))
        finally:
            logging.getLogger("licence_v1").removeHandler(record_logs)
            db = get_db()
            db.execute("DROP TRIGGER IF EXISTS fail_pro_redirect")
            db.commit()
            db.close()
        self.assertEqual(kept.status_code, 302)
        self.assertEqual(kept.location, ASSET)
        recorded = "\n".join(record_logs.lines)
        self.assertIn("Pro beta download was not recorded", recorded)
        self.assertNotIn("@", recorded)

    def test_send_links_keeps_the_key(self):
        issued = self._issue()
        db = get_db()
        before = db.execute(
            "SELECT key_hash FROM pro_keys WHERE id = ?",
            (issued["id"],),
        ).fetchone()["key_hash"]
        db.close()
        self.mail.clear()
        resent = self.client.post(
            f"/api/admin/pro-keys/{issued['id']}/send-links",
            headers=self._admin(),
        )
        self.assertEqual(resent.status_code, 200)
        body = resent.get_json()
        self.assertEqual(set(body), {"id", "sent", "revealed"})
        self.assertEqual(body["id"], issued["id"])
        self.assertEqual(body["sent"], 1)
        self.assertIs(body["revealed"], True)
        self.assertNotIn("@", resent.get_data(as_text=True))
        self.assertIn(issued["licence_key"], self.mail[-1]["text"])
        self.assertIn("/api/v1/download/pro/mac?t=", self.mail[-1]["text"])
        db = get_db()
        after = db.execute(
            "SELECT key_hash, status FROM pro_keys WHERE id = ?",
            (issued["id"],),
        ).fetchone()
        db.close()
        self.assertEqual(after["key_hash"], before)
        self.assertEqual(after["status"], "active")

        app.config["ADMIN_READ_TOKEN"] = "read-secret"
        reader = self.client.post(
            f"/api/admin/pro-keys/{issued['id']}/send-links",
            headers={"Authorization": "Bearer read-secret"},
        )
        self.assertEqual(reader.status_code, 401)
        self.assertNotIn("@", reader.get_data(as_text=True))

        missing = self.client.post(
            "/api/admin/pro-keys/99999/send-links",
            headers=self._admin(),
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json(), {"error": "not found"})
        self.assertNotIn(ADDRESS, missing.get_data(as_text=True))

        _plain, stripe_id = self._insert_stripe("buyer@example.com")
        stripe = self.client.post(
            f"/api/admin/pro-keys/{stripe_id}/send-links",
            headers=self._admin(),
        )
        self.assertEqual(stripe.status_code, 404)
        self.assertNotIn("buyer@example.com", stripe.get_data(as_text=True))

        self.client.post(
            f"/api/admin/pro-keys/{issued['id']}/revoke",
            headers=self._admin(),
        )
        gone = self.client.post(
            f"/api/admin/pro-keys/{issued['id']}/send-links",
            headers=self._admin(),
        )
        self.assertEqual(gone.status_code, 404)

        hidden = self._issue("hidden@example.com")
        db = get_db()
        db.execute("UPDATE pro_keys SET reveal_blob = '' WHERE id = ?", (hidden["id"],))
        db.commit()
        db.close()
        self.mail.clear()
        blank = self.client.post(
            f"/api/admin/pro-keys/{hidden['id']}/send-links",
            headers=self._admin(),
        )
        self.assertEqual(blank.status_code, 200)
        self.assertEqual(blank.get_json()["sent"], 1)
        self.assertIs(blank.get_json()["revealed"], False)
        self.assertIn("Email me a code", self.mail[-1]["text"])
        self.assertIn("/api/v1/download/pro/win?t=", self.mail[-1]["text"])
        self.assertNotIn("NCP-", self.mail[-1]["text"])
        self.assertNotIn("hidden@example.com", self.mail[-1]["text"])

        corrupt = self._issue("corrupt@example.com")
        db = get_db()
        db.execute(
            "UPDATE pro_keys SET reveal_blob = 'not-a-blob' WHERE id = ?",
            (corrupt["id"],),
        )
        db.commit()
        db.close()
        self.mail.clear()
        broken = self.client.post(
            f"/api/admin/pro-keys/{corrupt['id']}/send-links",
            headers=self._admin(),
        )
        self.assertEqual(broken.get_json()["revealed"], False)
        self.assertIn("Email me a code", self.mail[-1]["text"])
        self.assertNotIn("NCP-", self.mail[-1]["text"])

        self.mail_patch.stop()
        quiet = patch.object(api, "_send_mail", return_value=False)
        quiet.start()
        try:
            unsent = self.client.post(
                f"/api/admin/pro-keys/{corrupt['id']}/send-links",
                headers=self._admin(),
            )
        finally:
            quiet.stop()
            self.mail_patch.start()
        self.assertEqual(unsent.status_code, 200)
        self.assertEqual(unsent.get_json()["sent"], 0)
        db = get_db()
        still = db.execute(
            "SELECT key_hash FROM pro_keys WHERE id = ?",
            (corrupt["id"],),
        ).fetchone()["key_hash"]
        db.close()
        self.assertTrue(still)

        logs = _LogCapture()
        logging.getLogger("licence_v1").addHandler(logs)
        try:
            with patch.object(
                licence_v1,
                "send_manual_pro_links",
                side_effect=RuntimeError("fail person@example.com"),
            ):
                failed = self.client.post(
                    f"/api/admin/pro-keys/{hidden['id']}/send-links",
                    headers=self._admin(),
                )
        finally:
            logging.getLogger("licence_v1").removeHandler(logs)
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(failed.get_json()["error"], "The links were not sent")
        self.assertNotIn("person@example.com", failed.get_data(as_text=True))
        self.assertNotIn("@", "\n".join(logs.lines))

    def test_send_links_command_prints_counts_only(self):
        leaked = {"id": 7, "sent": 1, "revealed": True, "email": "beta@example.com"}
        with patch("admin_cli.api", return_value=(200, leaked)) as called:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                admin_cli.main(["pro-key", "send-links", "--id", "7"])
        self.assertEqual(stdout.getvalue(), "sent 1\nid 7\n")
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn("@", stdout.getvalue())
        self.assertEqual(called.call_args[0][0], "POST")
        self.assertEqual(called.call_args[0][1], "/api/admin/pro-keys/7/send-links")

        with patch("admin_cli.api", return_value=(404, {"error": "not found", "email": ADDRESS})):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as failed:
                    admin_cli.main(["pro-key", "send-links", "--id", "8"])
        self.assertEqual(failed.exception.code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "The links were not sent.\n")
        self.assertNotIn("@", stderr.getvalue())

        with patch("admin_cli.api", return_value=(200, {"id": 7, "sent": True, "email": ADDRESS})):
            stderr = io.StringIO()
            with patch("sys.stdout", io.StringIO()), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as bad_type:
                    admin_cli.main(["pro-key", "send-links", "--id", "7"])
        self.assertEqual(bad_type.exception.code, 1)
        self.assertEqual(stderr.getvalue(), "API response was not counts.\n")
        self.assertNotIn("@", stderr.getvalue())

    def test_recovery_returns_one_unused_key(self):
        email = "seats@example.com"
        older = self._issue(email)
        newer = self._issue(email)
        self.assertNotEqual(older["licence_key"], newer["licence_key"])
        self.assertGreater(newer["id"], older["id"])

        unknown = self.client.post("/api/v1/pro/key/resend", json={"email": "nobody@example.com"})
        self.assertEqual(unknown.status_code, 202)
        self.assertTrue(self.mail[-1]["subject"].startswith("Your Node Control"))
        self.assertNotIn("Code: ", self.mail[-1]["text"])

        body, letter = self._recover(email)
        self.assertEqual(body["licence_key"], newer["licence_key"])
        self.assertIn(older["licence_key"], letter["text"])
        self.assertIn(newer["licence_key"], letter["text"])
        self.assertIn("<p><strong>", letter["html"])
        self.assertIn("Enter one key in Welcome to Node Control.", letter["text"])
        self.assertIn("Each key is active on one computer at a time.", letter["text"])
        self.assertEqual(letter["subject"], "Your Node Control Professional key")

        install_new = str(uuid.uuid4())
        install_old = str(uuid.uuid4())
        self.assertEqual(self._activate(newer["licence_key"], install_new).status_code, 200)
        body, letter = self._recover(email)
        self.assertEqual(body["licence_key"], older["licence_key"])
        self.assertIn(older["licence_key"], letter["text"])
        self.assertIn(newer["licence_key"], letter["text"])

        self.assertEqual(self._activate(older["licence_key"], install_old).status_code, 200)
        self.assertEqual(self._check(newer["licence_key"], install_new).status_code, 200)
        self.assertEqual(self._check(older["licence_key"], install_old).status_code, 200)
        body, _letter = self._recover(email)
        self.assertEqual(body["licence_key"], newer["licence_key"])

        third = self._issue(email)
        body, letter = self._recover(email)
        self.assertEqual(body["licence_key"], third["licence_key"])
        for key in (older["licence_key"], newer["licence_key"], third["licence_key"]):
            self.assertIn(key, letter["text"])
        self.assertEqual(self._check(older["licence_key"], install_old).status_code, 200)
        self.assertEqual(self._check(newer["licence_key"], install_new).status_code, 200)
        db = get_db()
        seats = db.execute(
            """
            SELECT licence_ref, install_id FROM devices
            WHERE licence_kind = 'pro' AND active = 1
            ORDER BY licence_ref
            """
        ).fetchall()
        db.close()
        self.assertEqual(
            [(row["licence_ref"], row["install_id"]) for row in seats],
            [(older["id"], install_old), (newer["id"], install_new)],
        )

    def test_recovery_skips_a_seated_newer_stripe_key(self):
        email = "mixed@example.com"
        manual = self._issue(email)
        stripe_plain, stripe_id = self._insert_stripe(email)
        self.assertGreater(stripe_id, manual["id"])
        install = str(uuid.uuid4())
        self.assertEqual(self._activate(stripe_plain, install).status_code, 200)
        body, letter = self._recover(email)
        self.assertEqual(body["licence_key"], manual["licence_key"])
        self.assertIn(stripe_plain, letter["text"])
        self.assertIn(manual["licence_key"], letter["text"])
        manual_install = str(uuid.uuid4())
        self.assertEqual(self._activate(manual["licence_key"], manual_install).status_code, 200)
        body, _letter = self._recover(email)
        self.assertEqual(body["licence_key"], stripe_plain)
        self.assertEqual(self._check(stripe_plain, install).status_code, 200)
        self.assertEqual(self._check(manual["licence_key"], manual_install).status_code, 200)

    def test_canceled_subscription_does_not_block_a_manual_key(self):
        email = "closed@example.com"
        stripe_plain, _stripe_id = self._insert_stripe(email, sub_status="canceled")
        before = len(self.mail)
        quiet = self.client.post("/api/v1/pro/key/resend", json={"email": email})
        self.assertEqual(quiet.status_code, 202)
        self.assertEqual(len(self.mail), before)
        manual = self._issue(email)
        body, letter = self._recover(email)
        self.assertEqual(body["licence_key"], manual["licence_key"])
        self.assertIn(manual["licence_key"], letter["text"])
        self.assertNotIn(stripe_plain, letter["text"])
