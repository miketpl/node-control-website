"""Local tests for the licence API. SMTP and GitHub are mocked."""

import argparse
import base64
import json
import multiprocessing
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

_DB = tempfile.NamedTemporaryFile(prefix="nc-lic-test-", suffix=".db", delete=False)
os.environ["DB_PATH"] = _DB.name
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["SMTP_USER"] = "tester@example.com"
os.environ["SMTP_PASS"] = "test-pass"
os.environ["GITHUB_PAT"] = "test-read-token"
os.environ["GITHUB_PAT_WRITE"] = "test-write-token"
os.environ["LICENSE_REPO"] = "miketpl/node-control-license-free"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FREE_DOWNLOADS_PAUSED"] = "false"
os.environ["KEY_ENCRYPTION_KEY"] = "11" * 32

import app as api  # noqa: E402
from app import app, get_db  # noqa: E402


def _migrate_in_child(db_path):
    """Run in a second process, the way a second gunicorn worker does."""
    api.app.config["DB_PATH"] = db_path
    api.migrate_db()


class FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class GitHubFake:
    def __init__(self):
        self.codes = []
        self.sha = "sha-1"
        self.fail = False
        self.calls = []

    def urlopen(self, req, timeout=10):
        self.calls.append(req.full_url)
        if self.fail:
            raise HTTPError(req.full_url, 503, "unavailable", hdrs=None, fp=None)
        if req.get_method() == "GET":
            content = json.dumps({"codes": list(self.codes), "updated": ""}).encode("utf-8")
            return FakeResp(200, {
                "content": base64.b64encode(content).decode("ascii"),
                "sha": self.sha,
            })
        if req.get_method() == "PUT":
            body = json.loads(req.data.decode("utf-8"))
            decoded = json.loads(base64.b64decode(body["content"]))
            self.codes = list(decoded.get("codes", []))
            self.sha = "sha-next"
            return FakeResp(201, {})
        raise AssertionError(req.get_method())


class LicenceApiTests(unittest.TestCase):
    def setUp(self):
        self.github = GitHubFake()
        self.urlopen_patch = patch("app.urlopen", self.github.urlopen)
        self.urlopen_patch.start()
        self.client = app.test_client()
        app.config["SMTP_USER"] = "tester@example.com"
        app.config["SMTP_PASS"] = "test-pass"
        app.config["GITHUB_PAT"] = "test-read-token"
        app.config["GITHUB_PAT_WRITE"] = "test-write-token"
        app.config["ADMIN_TOKEN"] = "test-admin-token"
        app.config["ADMIN_READ_TOKEN"] = ""
        app.config["LEGACY_ALLOWLIST_SYNC"] = "true"
        app.config["LICENSE_REPO"] = "miketpl/node-control-license-free"
        db = get_db()
        db.execute("DELETE FROM licenses")
        db.execute("DELETE FROM download_events")
        db.execute("DELETE FROM funnel_daily")
        db.commit()
        db.close()
        api.reset_download_event_limits()
        api.reset_funnel_limits()

    def tearDown(self):
        self.urlopen_patch.stop()

    def _request(self, email="person@example.com", name="Person"):
        return self.client.post("/api/request-access", json={
            "name": name,
            "email": email,
            "company": "Example",
            "platform": "macos",
        })

    def _pending(self, email="person@example.com"):
        db = get_db()
        row = db.execute(
            "SELECT * FROM licenses WHERE email = ? ORDER BY id DESC LIMIT 1",
            (email,),
        ).fetchone()
        db.close()
        return row

    def _verify_code(self, email="person@example.com"):
        row = self._pending(email)
        self.assertIsNotNone(row)
        stored = row["verified_at"] or ""
        self.assertTrue(stored.startswith("PENDING:"))
        return stored.split(":", 1)[1]

    def _confirm(self, email="person@example.com"):
        row = self._pending(email)
        self.assertEqual(row["status"], "unverified")
        token = api.make_email_confirm_token(row["id"])
        res = self.client.get("/api/confirm-email?token=" + token)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Email confirmed", res.data)
        self.assertEqual(self._pending(email)["status"], "active")
        return res

    def _legacy_pending(self, email="legacy@example.com", verify="123456", code="NC-LEG1-LEG1"):
        db = get_db()
        db.execute(
            """
            INSERT INTO licenses (
                code, name, email, company, platform, tier, status, created_at, verified_at
            ) VALUES (?, '', ?, '', 'macos', 'free', 'pending', ?, ?)
            """,
            (code, email, datetime.utcnow().isoformat(), f"PENDING:{verify}"),
        )
        db.commit()
        db.close()
        return code

    def test_repo_name_and_env_example(self):
        root = Path(__file__).resolve().parent
        app_src = (root / "app.py").read_text()
        example = (root / ".env.example").read_text()
        self.assertIn('os.environ.get("LICENSE_REPO", "miketpl/node-control-license-free")', app_src)
        self.assertNotIn("node-control-licenses-free", app_src)
        self.assertIn("LICENSE_REPO=miketpl/node-control-license-free", example)
        self.assertIn("GITHUB_PAT_WRITE=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", example)
        self.assertIn("ADMIN_TOKEN=change-me-in-production", example)
        self.assertIn("ADMIN_READ_TOKEN=change-me-in-production", example)
        self.assertIn('os.environ.get("MIN_SUPPORTED_VERSION_FREE", "")', app_src)
        self.assertNotIn("MIN_SUPPORTED_VERSION_FREE=0.9.41", example)
        self.assertIn("until 0.9.41 is published", example)

    def test_health_reads_database(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["database"], "ok")

    def test_health_git_sha_uses_env_then_startup(self):
        previous = os.environ.get("GIT_SHA")
        os.environ["GIT_SHA"] = "deadbee"
        try:
            res = self.client.get("/api/health")
            body = res.get_json()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(body["git_sha"], "deadbee")
            self.assertEqual(body["status"], "ok")
            self.assertEqual(body["service"], "nodecontrol-license-api")
            self.assertEqual(body["database"], "ok")
        finally:
            if previous is None:
                os.environ.pop("GIT_SHA", None)
            else:
                os.environ["GIT_SHA"] = previous
        again = self.client.get("/api/health").get_json()
        self.assertEqual(again["git_sha"], api.GIT_SHA_AT_START)
        self.assertNotEqual(again["git_sha"], "deadbee")
        self.assertEqual(again["status"], "ok")
        self.assertEqual(again["service"], "nodecontrol-license-api")
        self.assertEqual(again["database"], "ok")

        os.environ.pop("GIT_SHA", None)
        with patch("app.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=2)):
            self.assertEqual(api._resolve_git_sha(), "unknown")
        self.assertEqual(api.GIT_SHA_AT_START, again["git_sha"])
        if previous is not None:
            os.environ["GIT_SHA"] = previous

    def test_health_reports_git_sha_when_the_database_is_down(self):
        with patch("app.get_db", side_effect=sqlite3.OperationalError("closed")):
            res = self.client.get("/api/health")
        body = res.get_json()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["service"], "nodecontrol-license-api")
        self.assertEqual(body["database"], "unavailable")
        self.assertEqual(body["git_sha"], api.deployed_git_sha())

    @patch("app.smtplib.SMTP")
    def test_request_sends_mail_and_stores_pending(self, smtp):
        res = self.client.post("/api/request-access", json={
            "email": "person@example.com", "platform": "macos",
        })
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertTrue(body["download_code"].startswith("NC-"))
        self.assertIn("/api/v1/download/free/mac?t=", body["downloads"]["mac"])
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()
        row = self._pending()
        self.assertEqual(row["name"], "")
        self.assertEqual(row["status"], "unverified")
        self.assertEqual(row["verified_at"], "")
        self.assertNotIn("PENDING:", row["verified_at"] or "")
        sent = smtp.return_value.__enter__.return_value.send_message.call_args[0][0]
        text = sent.get_payload(0).get_payload()
        self.assertIn("Hi there,", text)
        self.assertIn(body["download_code"], text)
        self.assertIn("/api/confirm-email?token=", text)
        self.assertNotIn("Hi ,", text)

    @patch("app.smtplib.SMTP")
    def test_same_email_reuses_the_unverified_licence(self, smtp):
        first = self._request()
        code = first.get_json()["download_code"]
        created = self._pending()["created_at"]
        again = self._request()
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.get_json()["download_code"], code)
        db = get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM licenses").fetchone()["c"]
        db.close()
        self.assertEqual(count, 1)
        self.assertEqual(self._pending()["created_at"], created)
        self.assertEqual(self.github.codes, [code])

    @patch("app.smtplib.SMTP")
    def test_one_reminder_after_a_day_and_not_before(self, smtp):
        self.assertEqual(self._request().status_code, 200)
        young = api.send_unverified_reminders()
        self.assertEqual(young, {"sent": 0, "failed": 0})
        db = get_db()
        db.execute(
            "UPDATE licenses SET created_at = ? WHERE email = ?",
            ((datetime.utcnow() - timedelta(hours=30)).isoformat(), "person@example.com"),
        )
        db.commit()
        db.close()
        smtp.return_value.__enter__.return_value.send_message.reset_mock()
        first = api.send_unverified_reminders()
        self.assertEqual(first["sent"], 1)
        self.assertEqual(first["failed"], 0)
        self.assertTrue(self._pending()["reminder_sent_at"])
        message = smtp.return_value.__enter__.return_value.send_message.call_args[0][0]
        self.assertEqual(message["Subject"], "Confirm your Node Control email")
        second = api.send_unverified_reminders()
        self.assertEqual(second["sent"], 0)
        self._confirm()
        self.assertEqual(self._pending()["status"], "active")

    def test_smtp_unconfigured_is_an_error_and_leaves_no_row(self):
        app.config["SMTP_USER"] = ""
        app.config["SMTP_PASS"] = ""
        res = self._request()
        self.assertEqual(res.status_code, 502)
        body = res.get_json()
        self.assertFalse(body["success"])
        self.assertIn("could not send", body["error"])
        self.assertIsNone(self._pending())

    @patch("app.smtplib.SMTP")
    def test_smtp_failure_rolls_back_and_retry_works(self, smtp):
        smtp.return_value.__enter__.side_effect = OSError("smtp down")
        failed = self._request()
        self.assertEqual(failed.status_code, 502)
        self.assertFalse(failed.get_json()["success"])
        self.assertIsNone(self._pending())
        self.assertEqual(self.github.codes, [])

        smtp.return_value.__enter__.side_effect = None
        retried = self._request()
        self.assertEqual(retried.status_code, 200)
        self.assertTrue(retried.get_json()["success"])
        self.assertEqual(self._pending()["status"], "unverified")

    @patch("app.smtplib.SMTP")
    def test_failed_resend_keeps_the_previous_pending_code(self, smtp):
        first = self._request()
        self.assertEqual(first.status_code, 200)
        original = first.get_json()["download_code"]

        smtp.return_value.__enter__.side_effect = OSError("smtp down")
        failed = self._request()
        self.assertEqual(failed.status_code, 502)
        row = self._pending()
        self.assertEqual(row["code"], original)
        self.assertEqual(row["status"], "unverified")

    @patch("app.smtplib.SMTP")
    def test_verify_github_failure_hides_the_code_and_allows_retry(self, smtp):
        self.github.fail = True
        failed = self._request()
        self.assertEqual(failed.status_code, 502)
        body = failed.get_json()
        self.assertFalse(body["success"])
        self.assertNotIn("download_code", body)
        self.assertEqual(self.github.codes, [])
        self.assertIsNone(self._pending())

        self.github.fail = False
        ok = self._request()
        self.assertEqual(ok.status_code, 200)
        issued = ok.get_json()["download_code"]
        self.assertTrue(issued.startswith("NC-"))
        self.assertIn(issued, self.github.codes)
        self.assertEqual(self._pending()["status"], "unverified")

    @patch("app.smtplib.SMTP")
    def test_legacy_six_digit_code_still_activates(self, smtp):
        issued = self._legacy_pending()
        failed = self.client.post("/api/verify", json={"email": "legacy@example.com", "code": "000000"})
        self.assertEqual(failed.status_code, 400)
        self.github.fail = True
        hidden = self.client.post("/api/verify", json={"email": "legacy@example.com", "code": "123456"})
        self.assertEqual(hidden.status_code, 502)
        self.assertNotIn("download_code", hidden.get_json())
        self.assertEqual(self._pending("legacy@example.com")["status"], "pending")
        self.github.fail = False
        ok = self.client.post("/api/verify", json={"email": "legacy@example.com", "code": "123456"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["download_code"], issued)
        self.assertEqual(self._pending("legacy@example.com")["status"], "active")
        self.assertIn(issued, self.github.codes)

    @patch("app.smtplib.SMTP")
    def test_verify_without_a_write_token_does_not_activate(self, smtp):
        app.config["GITHUB_PAT"] = ""
        app.config["GITHUB_PAT_WRITE"] = ""
        res = self._request()
        self.assertEqual(res.status_code, 502)
        self.assertNotIn("download_code", res.get_json())
        self.assertIsNone(self._pending())

    @patch("app.smtplib.SMTP")
    def test_verify_and_redeem_need_no_github_pat_when_legacy_sync_is_false(self, smtp):
        app.config["LEGACY_ALLOWLIST_SYNC"] = "false"
        app.config["GITHUB_PAT"] = ""
        app.config["GITHUB_PAT_WRITE"] = ""
        self.github.fail = True
        self.github.calls = []
        requested = self._request()
        self.assertEqual(requested.status_code, 200)
        issued = requested.get_json()["download_code"]
        self.assertTrue(issued.startswith("NC-"))
        self.assertEqual(self._pending()["status"], "unverified")
        self.assertEqual(self.github.calls, [])
        self.assertEqual(self.github.codes, [])

        redeemed = self.client.post("/api/redeem", json={"code": issued})
        self.assertEqual(redeemed.status_code, 200)
        body = redeemed.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["download_count"], 1)
        self.assertIn("/api/v1/download/free/mac?t=", body["downloads"]["mac"])
        self.assertIn("/api/v1/download/free/win?t=", body["downloads"]["win"])
        self.assertEqual(self.github.calls, [])

        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")
        self.assertEqual(self.github.calls, [])

        revoked = self.client.delete(
            f"/api/admin/licenses/{self._pending()['id']}",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(self._pending()["status"], "revoked")
        self.assertEqual(self.github.calls, [])
        self.assertEqual(self.github.codes, [])

        with patch("app.urlopen", side_effect=AssertionError("github was called")):
            api._add_code_to_licenses("NC-SKIP-0001")
            api._remove_code_from_licenses("NC-SKIP-0001")
            with self.assertRaises(RuntimeError):
                api._github_headers()
            with self.assertRaises(RuntimeError):
                api._get_licenses_json()
            with self.assertRaises(api.AllowlistError):
                api._registrations_pat()

    @patch("app.smtplib.SMTP")
    def test_legacy_sync_publishes_the_code_when_enabled(self, smtp):
        app.config["LEGACY_ALLOWLIST_SYNC"] = "true"
        requested = self._request()
        self.assertEqual(requested.status_code, 200)
        issued = requested.get_json()["download_code"]
        self.assertIn(issued, self.github.codes)
        self.assertTrue(any("licenses.json" in url for url in self.github.calls))
        self.assertEqual(self._pending()["status"], "unverified")

    @patch("app.smtplib.SMTP")
    def test_already_active_points_at_support(self, smtp):
        self.assertEqual(self._request().status_code, 200)
        self._confirm()
        again = self._request()
        self.assertEqual(again.status_code, 409)
        message = again.get_json()["error"]
        self.assertIn("support@nodecontrol.io", message)
        self.assertIn("already has a licence", message)
        self.assertNotIn("Check your email", message)

    def test_admin_disabled_for_missing_or_placeholder_token(self):
        for token in ("", "change-me-in-production"):
            app.config["ADMIN_TOKEN"] = token
            res = self.client.get("/api/admin/licenses")
            self.assertEqual(res.status_code, 503)
            self.assertEqual(res.get_json()["error"], "admin disabled")
            stats = self.client.get("/api/admin/stats")
            self.assertEqual(stats.status_code, 503)

    def test_admin_rejects_a_wrong_token(self):
        res = self.client.get(
            "/api/admin/licenses",
            headers={"Authorization": "Bearer no"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "Unauthorized")

    @patch("app.smtplib.SMTP")
    def test_revoke_keeps_sqlite_when_github_fails(self, smtp):
        requested = self._request()
        self.assertEqual(requested.status_code, 200)
        issued = requested.get_json()["download_code"]
        self.assertIn(issued, self.github.codes)
        self.github.fail = True
        res = self.client.delete(
            f"/api/admin/licenses/{self._pending()['id']}",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(res.status_code, 502)
        self.assertFalse(res.get_json()["success"])
        self.assertEqual(self._pending()["status"], "unverified")
        self.assertIn(issued, self.github.codes)

    @patch("app.smtplib.SMTP")
    def test_revoke_removes_the_code_from_github_and_sqlite(self, smtp):
        requested = self._request()
        self.assertEqual(requested.status_code, 200)
        issued = requested.get_json()["download_code"]
        res = self.client.delete(
            f"/api/admin/licenses/{self._pending()['id']}",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])
        self.assertEqual(self._pending()["status"], "revoked")
        self.assertNotIn(issued, self.github.codes)

    @patch("app.smtplib.SMTP")
    def test_revoke_restores_github_if_sqlite_update_fails(self, smtp):
        requested = self._request()
        self.assertEqual(requested.status_code, 200)
        issued = requested.get_json()["download_code"]

        def flaky_db():
            db = get_db()

            class Proxy:
                def execute(self, sql, params=()):
                    if "status = 'revoked'" in sql:
                        raise sqlite3.OperationalError("disk full")
                    return db.execute(sql, params)

                def commit(self):
                    return db.commit()

                def rollback(self):
                    return db.rollback()

                def close(self):
                    return db.close()

            return Proxy()

        with patch("app.get_db", flaky_db):
            res = self.client.delete(
                f"/api/admin/licenses/{self._pending()['id']}",
                headers={"Authorization": "Bearer test-admin-token"},
            )
        self.assertEqual(res.status_code, 502)
        self.assertIn("restored", res.get_json()["error"])
        self.assertEqual(self._pending()["status"], "unverified")
        self.assertIn(issued, self.github.codes)

    def test_cli_refuses_the_placeholder_token(self):
        env = os.environ.copy()
        env["ADMIN_TOKEN"] = "change-me-in-production"
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("admin_cli.py")), "list"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("placeholder", proc.stderr)

    @patch("app.smtplib.SMTP")
    def test_cli_lists_and_revokes_by_email(self, smtp):
        from werkzeug.serving import make_server

        requested = self._request("cli-user@example.com")
        self.assertEqual(requested.status_code, 200)
        issued = requested.get_json()["download_code"]
        self._confirm("cli-user@example.com")

        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = os.environ.copy()
        env["ADMIN_TOKEN"] = "test-admin-token"
        env["API_BASE"] = f"http://127.0.0.1:{server.server_port}"
        cli = str(Path(__file__).with_name("admin_cli.py"))
        try:
            listed = subprocess.run(
                [sys.executable, cli, "list", "--status", "active"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn("cli-user@example.com", listed.stdout)
            self.assertIn(issued, listed.stdout)
            revoked = subprocess.run(
                [sys.executable, cli, "revoke", "--email", "cli-user@example.com"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(revoked.returncode, 0, revoked.stderr)
            self.assertIn(issued, revoked.stdout)
        finally:
            server.shutdown()
            thread.join(timeout=5)

        self.assertEqual(self._pending("cli-user@example.com")["status"], "revoked")
        self.assertNotIn(issued, self.github.codes)

    @patch("app.smtplib.SMTP")
    def test_attribution_is_stored_and_cleaned(self, smtp):
        res = self.client.post("/api/request-access", json={
            "name": "Person", "email": "utm@example.com", "company": "", "platform": "windows",
            "utm_source": "LinkedIn", "utm_medium": "social", "utm_campaign": "launch<script>",
            "referrer": "www.linkedin.com", "landing_page": "/",
        })
        self.assertEqual(res.status_code, 200)
        row = self._pending("utm@example.com")
        self.assertEqual(row["utm_source"], "linkedin")
        self.assertEqual(row["utm_medium"], "social")
        self.assertEqual(row["utm_campaign"], "launchscript")
        self.assertEqual(row["utm_content"], "")
        self.assertEqual(row["referrer"], "www.linkedin.com")
        self.assertEqual(row["landing_page"], "/")

    @patch("app.smtplib.SMTP")
    def test_resend_without_attribution_keeps_the_first_values(self, smtp):
        self.client.post("/api/request-access", json={
            "name": "Person", "email": "keep@example.com", "platform": "macos",
            "utm_source": "youtube", "utm_medium": "video",
        })
        self.client.post("/api/request-access", json={
            "name": "Person", "email": "keep@example.com", "platform": "macos",
        })
        row = self._pending("keep@example.com")
        self.assertEqual(row["utm_source"], "youtube")
        self.assertEqual(row["utm_medium"], "video")

    @patch("app.smtplib.SMTP")
    def test_download_event_needs_an_active_code_and_shows_in_stats(self, smtp):
        requested = self.client.post("/api/request-access", json={
            "name": "Person", "email": "dl@example.com", "platform": "macos", "utm_source": "x",
        })
        issued = requested.get_json()["download_code"]

        # sendBeacon posts text/plain
        ok = self.client.post("/api/download-event", data=json.dumps(
            {"code": issued, "platform": "mac", "kind": "auto"}), content_type="text/plain")
        self.assertEqual(ok.status_code, 204)
        bad = self.client.post("/api/download-event", data=json.dumps(
            {"code": "NC-NOPE-NOPE", "platform": "mac", "kind": "auto"}), content_type="text/plain")
        self.assertEqual(bad.status_code, 204)

        stats = self.client.get("/api/admin/stats", headers={"Authorization": "Bearer test-admin-token"})
        self.assertEqual(stats.status_code, 200)
        body = stats.get_json()
        sources = {row["source"]: row for row in body["by_source"]}
        self.assertEqual(sources["x"]["verified"], 0)
        self.assertEqual(sources["x"]["unverified"], 1)
        self.assertEqual(body["unverified"], 1)
        self.assertEqual(body["download_events"], [{
            "platform": "mac", "kind": "auto",
            "utm_source": "none", "utm_campaign": "none", "utm_content": "none",
            "events": 1, "licences": 1,
        }])
        self._confirm("dl@example.com")
        after = self.client.get(
            "/api/admin/stats", headers={"Authorization": "Bearer test-admin-token"}
        ).get_json()
        sources = {row["source"]: row for row in after["by_source"]}
        self.assertEqual(sources["x"]["verified"], 1)
        self.assertEqual(sources["x"]["unverified"], 0)
        hidden = self.client.get("/api/admin/stats")
        self.assertEqual(hidden.status_code, 401)

    @patch("app.smtplib.SMTP")
    def test_attribution_drops_urls_and_query_strings(self, smtp):
        res = self.client.post("/api/request-access", json={
            "name": "Person", "email": "ref@example.com", "platform": "macos",
            "referrer": "https://www.linkedin.com/in/someone?email=person@example.com",
            "landing_page": "/?utm_source=linkedin#free-edition",
        })
        self.assertEqual(res.status_code, 200)
        row = self._pending("ref@example.com")
        self.assertEqual(row["referrer"], "www.linkedin.com")
        self.assertEqual(row["landing_page"], "/")
        junk = self.client.post("/api/request-access", json={
            "name": "Person", "email": "junk@example.com", "platform": "macos",
            "referrer": "not a host", "landing_page": "https://evil.example/steal",
        })
        self.assertEqual(junk.status_code, 200)
        junk_row = self._pending("junk@example.com")
        self.assertEqual(junk_row["referrer"], "")
        self.assertEqual(junk_row["landing_page"], "")

    @patch("app.smtplib.SMTP")
    def test_download_event_is_capped_and_ignores_junk(self, smtp):
        requested = self.client.post("/api/request-access", json={
            "name": "Person", "email": "cap@example.com", "platform": "macos",
        })
        issued = requested.get_json()["download_code"]
        original = api.DOWNLOAD_EVENT_LICENCE_CAP
        api.DOWNLOAD_EVENT_LICENCE_CAP = 2
        try:
            for _ in range(4):
                res = self.client.post("/api/download-event", data=json.dumps(
                    {"code": issued, "platform": "win", "kind": "click"}), content_type="text/plain")
                self.assertEqual(res.status_code, 204)
            odd = self.client.post("/api/download-event", data=json.dumps(
                {"code": issued, "platform": "linux", "kind": "click"}), content_type="text/plain")
            self.assertEqual(odd.status_code, 204)
            huge = self.client.post(
                "/api/download-event",
                data=b"x" * (api.DOWNLOAD_EVENT_BODY_LIMIT + 1),
                content_type="text/plain",
            )
            self.assertEqual(huge.status_code, 204)
        finally:
            api.DOWNLOAD_EVENT_LICENCE_CAP = original
        db = get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM download_events").fetchone()["c"]
        db.close()
        self.assertEqual(count, 2)

    def test_funnel_event_counts_a_utc_day_and_nothing_else(self):
        plain = self.client.post(
            "/api/funnel-event",
            data=b"free_section_view",
            content_type="text/plain",
            headers={"Origin": "https://nodecontrol.io", "CF-Connecting-IP": "203.0.113.10"},
        )
        self.assertEqual(plain.status_code, 204)
        self.assertEqual(
            plain.headers.get("Access-Control-Allow-Origin"),
            "https://nodecontrol.io",
        )
        beacon = self.client.post(
            "/api/download-event",
            data=b"{}",
            content_type="text/plain",
            headers={"Origin": "https://nodecontrol.io"},
        )
        self.assertEqual(
            plain.headers.get("Access-Control-Allow-Origin"),
            beacon.headers.get("Access-Control-Allow-Origin"),
        )
        as_json = self.client.post(
            "/api/funnel-event",
            json={"event": "free_form_start"},
            headers={"CF-Connecting-IP": "203.0.113.10"},
        )
        self.assertEqual(as_json.status_code, 204)
        wrapped = self.client.post(
            "/api/funnel-event",
            data=json.dumps({"event": "free_form_submit"}),
            content_type="text/plain",
            headers={"CF-Connecting-IP": "203.0.113.10"},
        )
        self.assertEqual(wrapped.status_code, 204)
        ignored = self.client.post(
            "/api/funnel-event",
            data=b"not_an_event",
            content_type="text/plain",
            headers={"CF-Connecting-IP": "203.0.113.10"},
        )
        self.assertEqual(ignored.status_code, 204)
        huge = self.client.post(
            "/api/funnel-event",
            data=b"x" * (api.FUNNEL_BODY_LIMIT + 1),
            content_type="text/plain",
            headers={"CF-Connecting-IP": "203.0.113.10"},
        )
        self.assertEqual(huge.status_code, 204)

        db = get_db()
        cols = [row["name"] for row in db.execute("PRAGMA table_info(funnel_daily)")]
        rows = db.execute(
            "SELECT day, event, utm_source, utm_campaign, utm_content, count FROM funnel_daily ORDER BY event"
        ).fetchall()
        db.close()
        self.assertEqual(
            cols, ["day", "event", "utm_source", "utm_campaign", "utm_content", "count"]
        )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(
            [(row["day"], row["event"], row["utm_source"], row["utm_campaign"], row["utm_content"], row["count"]) for row in rows],
            [
                (today, "free_form_start", "none", "none", "none", 1),
                (today, "free_form_submit", "none", "none", "none", 1),
                (today, "free_section_view", "none", "none", "none", 1),
            ],
        )

    def test_funnel_event_rate_limit_is_memory_only(self):
        self.assertEqual(api.FUNNEL_IP_LIMIT, 30)
        original = api.FUNNEL_IP_LIMIT
        api.FUNNEL_IP_LIMIT = 2
        try:
            headers = {"CF-Connecting-IP": "203.0.113.40"}
            for _ in range(2):
                res = self.client.post(
                    "/api/funnel-event", data=b"free_section_view",
                    content_type="text/plain", headers=headers,
                )
                self.assertEqual(res.status_code, 204)
            blocked = self.client.post(
                "/api/funnel-event", data=b"free_section_view",
                content_type="text/plain", headers=headers,
            )
            self.assertEqual(blocked.status_code, 204)
            other = self.client.post(
                "/api/funnel-event", data=b"free_form_start",
                content_type="text/plain",
                headers={"CF-Connecting-IP": "203.0.113.41"},
            )
            self.assertEqual(other.status_code, 204)
        finally:
            api.FUNNEL_IP_LIMIT = original
        db = get_db()
        rows = {
            row["event"]: row["count"]
            for row in db.execute("SELECT event, count FROM funnel_daily")
        }
        rate_rows = db.execute(
            "SELECT COUNT(*) AS c FROM rate_limits WHERE bucket LIKE '%funnel%'"
        ).fetchone()["c"]
        db.close()
        self.assertEqual(rows.get("free_section_view"), 2)
        self.assertEqual(rows.get("free_form_start"), 1)
        self.assertEqual(rate_rows, 0)
        self.assertNotIn("203.0.113.40", json.dumps(rows))

    def test_funnel_command_is_read_only_and_prints_uk_days(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        import admin_cli
        uk_today = datetime.now(ZoneInfo("Europe/London")).date()
        yesterday = (uk_today - timedelta(days=1)).isoformat()
        today = uk_today.isoformat()
        db = get_db()
        db.execute(
            "INSERT INTO funnel_daily (day, event, count) VALUES (?, ?, ?)",
            (today, "free_section_view", 10),
        )
        db.execute(
            "INSERT INTO funnel_daily (day, event, count) VALUES (?, ?, ?)",
            (today, "free_form_start", 4),
        )
        db.execute(
            "INSERT INTO funnel_daily (day, event, count) VALUES (?, ?, ?)",
            (today, "free_form_submit", 1),
        )
        db.execute(
            "INSERT INTO funnel_daily (day, event, count) VALUES (?, ?, ?)",
            (yesterday, "free_section_view", 2),
        )
        db.commit()
        db.close()

        previous = os.environ.get("DB_PATH")
        os.environ["DB_PATH"] = app.config["DB_PATH"]
        try:
            with patch("sys.stdout", new_callable=StringIO) as out:
                admin_cli.cmd_funnel(argparse.Namespace(days=2))
            text = out.getvalue()
            with self.assertRaises(sqlite3.OperationalError):
                raw = admin_cli.open_funnel_db()
                try:
                    raw.execute(
                        "INSERT INTO funnel_daily (day, event, count) VALUES ('2000-01-01', 'free_section_view', 1)"
                    )
                finally:
                    raw.close()
        finally:
            if previous is None:
                os.environ.pop("DB_PATH", None)
            else:
                os.environ["DB_PATH"] = previous

        lines = text.strip().splitlines()
        self.assertEqual(
            lines[0],
            "day\tfree_section_view\tfree_form_start\tfree_form_submit\t"
            "form_start/section_view\tsubmit/form_start",
        )
        self.assertTrue(lines[1].startswith(yesterday + "\t2\t0\t0\t0.0%\t-"))
        self.assertTrue(lines[2].startswith(today + "\t10\t4\t1\t40.0%\t25.0%"))
        db = get_db()
        still = db.execute(
            "SELECT count FROM funnel_daily WHERE day = ? AND event = ?",
            (today, "free_section_view"),
        ).fetchone()["count"]
        db.close()
        self.assertEqual(still, 10)

    def test_funnel_tags_are_normalised_and_counted_apart(self):
        self.assertEqual(api.normalise_funnel_tag(None), "none")
        self.assertEqual(api.normalise_funnel_tag("   "), "none")
        self.assertEqual(api.normalise_funnel_tag("  LinkedIn  "), "linkedin")
        self.assertEqual(api.normalise_funnel_tag("ok.name-1_a"), "ok.name-1_a")
        self.assertEqual(api.normalise_funnel_tag("a" * 70), "a" * 64)
        self.assertEqual(api.normalise_funnel_tag("launch<script>"), "other")
        self.assertEqual(api.normalise_funnel_tag("hello world"), "other")
        self.assertEqual(api.normalise_funnel_tag("café"), "other")

        headers = {"CF-Connecting-IP": "203.0.113.77"}
        first = self.client.post(
            "/api/funnel-event",
            data=json.dumps({
                "event": "free_section_view",
                "utm_source": "LinkedIn",
                "utm_campaign": "Launch Day",
            }),
            content_type="text/plain",
            headers=headers,
        )
        second = self.client.post(
            "/api/funnel-event",
            data=json.dumps({
                "event": "free_section_view",
                "utm_source": "linkedin",
                "utm_campaign": "launch-day",
            }),
            content_type="text/plain",
            headers=headers,
        )
        plain = self.client.post(
            "/api/funnel-event",
            data=b"free_section_view",
            content_type="text/plain",
            headers=headers,
        )
        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 204)
        self.assertEqual(plain.status_code, 204)
        db = get_db()
        rows = db.execute(
            """
            SELECT utm_source, utm_campaign, count FROM funnel_daily
            WHERE event = 'free_section_view' ORDER BY utm_campaign
            """
        ).fetchall()
        stored = json.dumps([tuple(row) for row in rows])
        db.close()
        self.assertEqual(
            [tuple(row) for row in rows],
            [
                ("linkedin", "launch-day", 1),
                ("none", "none", 1),
                ("linkedin", "other", 1),
            ],
        )
        self.assertNotIn("203.0.113.77", stored)
        self.assertNotIn("LinkedIn", stored)

    def test_old_funnel_table_keeps_its_rows_as_none(self):
        path = tempfile.NamedTemporaryFile(prefix="nc-old-funnel-", suffix=".db", delete=False)
        path.close()
        raw = sqlite3.connect(path.name)
        raw.execute(
            """
            CREATE TABLE funnel_daily (
                day TEXT NOT NULL,
                event TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, event)
            )
            """
        )
        raw.execute(
            "INSERT INTO funnel_daily (day, event, count) VALUES ('2026-10-01', 'free_section_view', 7)"
        )
        raw.commit()
        try:
            api._migrate_funnel_daily(raw)
            api._migrate_funnel_daily(raw)
            raw.commit()
            cols = [row[1] for row in raw.execute("PRAGMA table_info(funnel_daily)")]
            row = raw.execute("SELECT * FROM funnel_daily").fetchone()
            raw.execute(
                """
                INSERT INTO funnel_daily (day, event, utm_source, utm_campaign, count)
                VALUES ('2026-10-01', 'free_section_view', 'linkedin', 'launch', 3)
                """
            )
            raw.commit()
            count = raw.execute("SELECT COUNT(*) FROM funnel_daily").fetchone()[0]
            kept = raw.execute(
                """
                SELECT count FROM funnel_daily
                WHERE utm_source = 'none' AND utm_campaign = 'none'
                """
            ).fetchone()[0]
        finally:
            raw.close()
            os.unlink(path.name)
        self.assertEqual(
            cols, ["day", "event", "utm_source", "utm_campaign", "utm_content", "count"]
        )
        self.assertEqual(row[0], "2026-10-01")
        self.assertEqual(row[1], "free_section_view")
        self.assertEqual(row[2], "none")
        self.assertEqual(row[3], "none")
        self.assertEqual(row[4], "none")
        self.assertEqual(row[5], 7)
        self.assertEqual(count, 2)
        self.assertEqual(kept, 7)

    def test_campaign_rows_keep_their_counts_when_content_is_added(self):
        path = tempfile.NamedTemporaryFile(prefix="nc-funnel-content-", suffix=".db", delete=False)
        path.close()
        raw = sqlite3.connect(path.name)
        raw.row_factory = sqlite3.Row
        raw.execute(
            """
            CREATE TABLE funnel_daily (
                day TEXT NOT NULL,
                event TEXT NOT NULL,
                utm_source TEXT NOT NULL DEFAULT 'none',
                utm_campaign TEXT NOT NULL DEFAULT 'none',
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, event, utm_source, utm_campaign)
            )
            """
        )
        raw.execute(
            """
            INSERT INTO funnel_daily (day, event, utm_source, utm_campaign, count)
            VALUES ('2026-10-02', 'free_form_submit', 'reddit', 'blitz-reddit-ads', 5)
            """
        )
        raw.execute(
            """
            INSERT INTO funnel_daily (day, event, utm_source, utm_campaign, count)
            VALUES ('2026-10-02', 'free_form_submit', 'reddit', 'paid30-launch', 2)
            """
        )
        raw.commit()
        try:
            api._migrate_funnel_daily(raw)
            api._migrate_funnel_daily(raw)
            raw.commit()
            rows = raw.execute(
                """
                SELECT utm_campaign, utm_content, count FROM funnel_daily
                ORDER BY utm_campaign
                """
            ).fetchall()
        finally:
            raw.close()
            os.unlink(path.name)
        self.assertEqual(
            [tuple(row) for row in rows],
            [("blitz-reddit-ads", "none", 5), ("paid30-launch", "none", 2)],
        )

    @patch("app.smtplib.SMTP")
    def test_utm_content_is_counted_with_the_campaign(self, smtp):
        raw_content = "V1<script>" + ("x" * 200)
        cleaned = "".join(
            ch for ch in raw_content.strip()[:128].lower()
            if ch.isalnum() or ch in "._-"
        )
        signed = self.client.post("/api/request-access", json={
            "name": "Person",
            "email": "creative@example.com",
            "platform": "macos",
            "utm_source": "reddit",
            "utm_campaign": "paid30-launch",
            "utm_content": raw_content,
        })
        self.assertEqual(signed.status_code, 200)
        row = self._pending("creative@example.com")
        self.assertEqual(row["utm_source"], "reddit")
        self.assertEqual(row["utm_campaign"], "paid30-launch")
        self.assertEqual(row["utm_content"], cleaned)
        self.assertLessEqual(len(row["utm_content"]), 128)
        self.assertEqual(row["status"], "unverified")

        issued = signed.get_json()["download_code"]
        beacon = self.client.post(
            "/api/download-event",
            data=json.dumps({
                "code": issued,
                "platform": "mac",
                "kind": "click",
                "utm_source": "reddit",
                "utm_campaign": "blitz-reddit-ads",
                "utm_content": "v2",
            }),
            content_type="text/plain",
        )
        self.assertEqual(beacon.status_code, 204)
        db = get_db()
        event = db.execute(
            "SELECT utm_source, utm_campaign, utm_content FROM download_events"
        ).fetchone()
        db.close()
        self.assertEqual(tuple(event), ("reddit", "blitz-reddit-ads", "v2"))

        headers = {"CF-Connecting-IP": "203.0.113.88"}
        for content in ("v1", "v2", "v1"):
            res = self.client.post(
                "/api/funnel-event",
                data=json.dumps({
                    "event": "free_form_submit",
                    "utm_source": "reddit",
                    "utm_campaign": "paid30-launch",
                    "utm_content": content,
                }),
                content_type="text/plain",
                headers=headers,
            )
            self.assertEqual(res.status_code, 204)
        long = self.client.post(
            "/api/funnel-event",
            data=json.dumps({
                "event": "free_form_submit",
                "utm_source": "reddit",
                "utm_campaign": "paid30-launch",
                "utm_content": "c" * 80,
            }),
            content_type="text/plain",
            headers=headers,
        )
        self.assertEqual(long.status_code, 204)
        db = get_db()
        counts = db.execute(
            """
            SELECT utm_content, count FROM funnel_daily
            WHERE event = 'free_form_submit' AND utm_campaign = 'paid30-launch'
            ORDER BY utm_content
            """
        ).fetchall()
        db.close()
        self.assertEqual(
            [tuple(item) for item in counts],
            [("c" * 64, 1), ("v1", 2), ("v2", 1)],
        )

        self._confirm("creative@example.com")
        stats = self.client.get(
            "/api/admin/stats", headers={"Authorization": "Bearer test-admin-token"}
        )
        body = stats.get_json()
        campaigns = {
            (item["utm_campaign"], item["utm_content"]): item
            for item in body["by_campaign"]
        }
        creative = campaigns[("paid30-launch", cleaned)]
        self.assertEqual(creative["source"], "reddit")
        self.assertEqual(creative["requested"], 1)
        self.assertEqual(creative["verified"], 1)
        downloads = body["download_events"]
        self.assertEqual(downloads[0]["utm_content"], "v2")
        self.assertEqual(downloads[0]["utm_campaign"], "blitz-reddit-ads")

    def test_funnel_command_by_campaign_splits_the_day(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        import admin_cli
        uk_today = datetime.now(ZoneInfo("Europe/London")).date().isoformat()
        db = get_db()
        db.execute(
            """
            INSERT INTO funnel_daily (day, event, utm_source, utm_campaign, count)
            VALUES (?, 'free_section_view', 'linkedin', 'launch', 6)
            """,
            (uk_today,),
        )
        db.execute(
            """
            INSERT INTO funnel_daily (day, event, utm_source, utm_campaign, count)
            VALUES (?, 'free_section_view', 'none', 'none', 4)
            """,
            (uk_today,),
        )
        db.commit()
        db.close()
        previous = os.environ.get("DB_PATH")
        os.environ["DB_PATH"] = app.config["DB_PATH"]
        try:
            with patch("sys.stdout", new_callable=StringIO) as totals:
                admin_cli.cmd_funnel(argparse.Namespace(days=1, by_campaign=False))
            with patch("sys.stdout", new_callable=StringIO) as split:
                admin_cli.cmd_funnel(argparse.Namespace(days=1, by_campaign=True))
        finally:
            if previous is None:
                os.environ.pop("DB_PATH", None)
            else:
                os.environ["DB_PATH"] = previous
        total_lines = totals.getvalue().strip().splitlines()
        self.assertTrue(total_lines[1].startswith(uk_today + "\t10\t0\t0\t"))
        split_lines = split.getvalue().strip().splitlines()
        self.assertEqual(
            split_lines[0], "day\tutm_source\tutm_campaign\tutm_content\tevent\tcount"
        )
        self.assertEqual(
            split_lines[1:],
            [
                f"{uk_today}\tlinkedin\tlaunch\tnone\tfree_section_view\t6",
                f"{uk_today}\tnone\tnone\tnone\tfree_section_view\t4",
            ],
        )

    def test_migration_keeps_an_existing_row_on_the_old_schema(self):
        old = tempfile.NamedTemporaryFile(prefix="nc-old-lic-", suffix=".db", delete=False)
        old.close()
        raw = sqlite3.connect(old.name)
        raw.execute("""
            CREATE TABLE licenses (
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
            )
        """)
        raw.execute(
            """INSERT INTO licenses
               (code, name, email, company, platform, tier, status, created_at, download_count)
               VALUES (?, ?, ?, ?, ?, 'free', 'active', ?, 2)""",
            ("NC-KEEP-ROW1", "Person", "kept@example.com", "Example", "macos", "2026-01-01T00:00:00"),
        )
        raw.commit()
        raw.close()

        previous = app.config["DB_PATH"]
        app.config["DB_PATH"] = old.name
        try:
            api.init_db()
            api.migrate_db()
            api.migrate_db()
            db = get_db()
            cols = {row["name"] for row in db.execute("PRAGMA table_info(licenses)")}
            row = db.execute(
                "SELECT * FROM licenses WHERE code = ?", ("NC-KEEP-ROW1",)
            ).fetchone()
            events = db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'download_events'"
            ).fetchone()
            db.close()
        finally:
            app.config["DB_PATH"] = previous
            os.unlink(old.name)

        self.assertIsNotNone(row)
        self.assertEqual(row["email"], "kept@example.com")
        self.assertEqual(row["name"], "Person")
        self.assertEqual(row["download_count"], 2)
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["utm_source"], "")
        self.assertEqual(row["referrer"], "")
        self.assertIsNotNone(events)
        for column in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "referrer", "landing_page"):
            self.assertIn(column, cols)
        self.assertEqual(row["utm_content"], "")
        os.unlink(old.name + ".migrate.lock")

    def test_adding_a_column_twice_is_not_an_error(self):
        path = tempfile.NamedTemporaryFile(prefix="nc-dup-col-", suffix=".db", delete=False)
        path.close()
        raw = sqlite3.connect(path.name)
        raw.execute("""
            CREATE TABLE licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                landing_page TEXT DEFAULT ''
            )
        """)
        raw.execute(
            "INSERT INTO licenses (code, name, email, created_at, landing_page) VALUES (?, ?, ?, ?, ?)",
            ("NC-PART-0001", "Person", "part@example.com", "2026-01-01T00:00:00", ""),
        )
        raw.commit()
        try:
            api._add_license_column(raw, "landing_page")
            api._add_license_column(raw, "landing_page")
            raw.commit()
            cols = {row[1] for row in raw.execute("PRAGMA table_info(licenses)")}
            row = raw.execute(
                "SELECT email FROM licenses WHERE code = ?", ("NC-PART-0001",)
            ).fetchone()
        finally:
            raw.close()
            os.unlink(path.name)
        self.assertIn("landing_page", cols)
        self.assertEqual(row[0], "part@example.com")

    def test_two_processes_can_migrate_a_partly_updated_database(self):
        path = tempfile.NamedTemporaryFile(prefix="nc-migrate-race-", suffix=".db", delete=False)
        path.close()
        raw = sqlite3.connect(path.name)
        raw.execute("""
            CREATE TABLE licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                tier TEXT DEFAULT 'free',
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                verified_at TEXT,
                redeemed_at TEXT,
                download_count INTEGER DEFAULT 0,
                ip_address TEXT DEFAULT '',
                utm_source TEXT DEFAULT '',
                utm_medium TEXT DEFAULT '',
                utm_campaign TEXT DEFAULT ''
            )
        """)
        raw.execute(
            """INSERT INTO licenses
               (code, name, email, created_at, download_count, utm_source, utm_medium, utm_campaign)
               VALUES (?, ?, ?, ?, 3, ?, ?, ?)""",
            ("NC-PART-0002", "Person", "part@example.com", "2026-01-02T00:00:00", "linkedin", "social", "launch"),
        )
        raw.commit()
        raw.close()

        ctx = multiprocessing.get_context("fork")
        procs = [
            ctx.Process(target=_migrate_in_child, args=(path.name,))
            for _ in range(2)
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(15)
            self.assertFalse(proc.is_alive())
            self.assertEqual(proc.exitcode, 0, f"migrate process exited {proc.exitcode}")

        db = sqlite3.connect(path.name)
        db.row_factory = sqlite3.Row
        try:
            cols = {row["name"] for row in db.execute("PRAGMA table_info(licenses)")}
            row = db.execute(
                "SELECT * FROM licenses WHERE code = ?", ("NC-PART-0002",)
            ).fetchone()
            index = db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_licenses_utm_source'"
            ).fetchone()
            events = db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'download_events'"
            ).fetchone()
        finally:
            db.close()
            os.unlink(path.name)
            lock = path.name + ".migrate.lock"
            if os.path.exists(lock):
                os.unlink(lock)

        for column in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "referrer", "landing_page"):
            self.assertIn(column, cols)
        self.assertEqual(row["utm_content"], "")
        self.assertEqual(row["email"], "part@example.com")
        self.assertEqual(row["utm_source"], "linkedin")
        self.assertEqual(row["utm_medium"], "social")
        self.assertEqual(row["utm_campaign"], "launch")
        self.assertEqual(row["download_count"], 3)
        self.assertEqual(row["referrer"], "")
        self.assertEqual(row["landing_page"], "")
        self.assertIsNotNone(index)
        self.assertIsNotNone(events)


if __name__ == "__main__":
    unittest.main()
