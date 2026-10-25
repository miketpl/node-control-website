"""Local tests for the licence API. SMTP and GitHub are mocked."""

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
        db.commit()
        db.close()
        api.reset_download_event_limits()

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
        res = self._request()
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertNotIn("download_code", body)
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()
        row = self._pending()
        self.assertEqual(row["status"], "pending")
        self.assertTrue(row["verified_at"].startswith("PENDING:"))

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

        smtp.return_value.__enter__.side_effect = None
        retried = self._request()
        self.assertEqual(retried.status_code, 200)
        self.assertTrue(retried.get_json()["success"])
        self.assertEqual(self._pending()["status"], "pending")

    @patch("app.smtplib.SMTP")
    def test_failed_resend_keeps_the_previous_pending_code(self, smtp):
        first = self._request()
        self.assertEqual(first.status_code, 200)
        original = self._verify_code()

        smtp.return_value.__enter__.side_effect = OSError("smtp down")
        failed = self._request()
        self.assertEqual(failed.status_code, 502)
        self.assertEqual(self._verify_code(), original)
        self.assertEqual(self._pending()["status"], "pending")

    @patch("app.smtplib.SMTP")
    def test_verify_github_failure_hides_the_code_and_allows_retry(self, smtp):
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        self.github.fail = True
        failed = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        self.assertEqual(failed.status_code, 502)
        body = failed.get_json()
        self.assertFalse(body["success"])
        self.assertNotIn("download_code", body)
        self.assertEqual(self.github.codes, [])
        self.assertEqual(self._pending()["status"], "pending")
        self.assertEqual(self._verify_code(), code)

        self.github.fail = False
        ok = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        self.assertEqual(ok.status_code, 200)
        issued = ok.get_json()["download_code"]
        self.assertTrue(issued.startswith("NC-"))
        self.assertIn(issued, self.github.codes)
        self.assertEqual(self._pending()["status"], "active")

    @patch("app.smtplib.SMTP")
    def test_verify_without_a_write_token_does_not_activate(self, smtp):
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        app.config["GITHUB_PAT"] = ""
        app.config["GITHUB_PAT_WRITE"] = ""
        res = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        self.assertEqual(res.status_code, 502)
        self.assertNotIn("download_code", res.get_json())
        self.assertEqual(self._pending()["status"], "pending")

    @patch("app.smtplib.SMTP")
    def test_verify_and_redeem_need_no_github_pat_when_legacy_sync_is_false(self, smtp):
        app.config["LEGACY_ALLOWLIST_SYNC"] = "false"
        app.config["GITHUB_PAT"] = ""
        app.config["GITHUB_PAT_WRITE"] = ""
        self.github.fail = True
        self.github.calls = []
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        verified = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        self.assertEqual(verified.status_code, 200)
        issued = verified.get_json()["download_code"]
        self.assertTrue(issued.startswith("NC-"))
        self.assertEqual(self._pending()["status"], "active")
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
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        verified = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        self.assertEqual(verified.status_code, 200)
        issued = verified.get_json()["download_code"]
        self.assertIn(issued, self.github.codes)
        self.assertTrue(any("licenses.json" in url for url in self.github.calls))
        self.assertEqual(self._pending()["status"], "active")

    @patch("app.smtplib.SMTP")
    def test_already_active_points_at_support(self, smtp):
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        verified = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        self.assertEqual(verified.status_code, 200)
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
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        verified = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        issued = verified.get_json()["download_code"]
        self.assertIn(issued, self.github.codes)
        self.github.fail = True
        res = self.client.delete(
            f"/api/admin/licenses/{self._pending()['id']}",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(res.status_code, 502)
        self.assertFalse(res.get_json()["success"])
        self.assertEqual(self._pending()["status"], "active")
        self.assertIn(issued, self.github.codes)

    @patch("app.smtplib.SMTP")
    def test_revoke_removes_the_code_from_github_and_sqlite(self, smtp):
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        verified = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        issued = verified.get_json()["download_code"]
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
        self.assertEqual(self._request().status_code, 200)
        code = self._verify_code()
        verified = self.client.post("/api/verify", json={"email": "person@example.com", "code": code})
        issued = verified.get_json()["download_code"]

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
        self.assertEqual(self._pending()["status"], "active")
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

        self.assertEqual(self._request("cli-user@example.com").status_code, 200)
        code = self._verify_code("cli-user@example.com")
        verified = self.client.post("/api/verify", json={"email": "cli-user@example.com", "code": code})
        self.assertEqual(verified.status_code, 200)
        issued = verified.get_json()["download_code"]

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
        self.client.post("/api/request-access", json={
            "name": "Person", "email": "dl@example.com", "platform": "macos", "utm_source": "x",
        })
        code = self._verify_code("dl@example.com")
        issued = self.client.post("/api/verify", json={"email": "dl@example.com", "code": code}).get_json()["download_code"]

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
        self.assertEqual(sources["x"]["verified"], 1)
        self.assertEqual(body["download_events"], [{"platform": "mac", "kind": "auto", "events": 1, "licences": 1}])
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
        self.client.post("/api/request-access", json={
            "name": "Person", "email": "cap@example.com", "platform": "macos",
        })
        code = self._verify_code("cap@example.com")
        issued = self.client.post("/api/verify", json={"email": "cap@example.com", "code": code}).get_json()["download_code"]
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
        for column in ("utm_source", "utm_medium", "utm_campaign", "referrer", "landing_page"):
            self.assertIn(column, cols)
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
            key_cols = {row["name"] for row in db.execute("PRAGMA table_info(pro_keys)")}
            intents = db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'purchase_intents'"
            ).fetchone()
        finally:
            db.close()
            os.unlink(path.name)
            lock = path.name + ".migrate.lock"
            if os.path.exists(lock):
                os.unlink(lock)

        for column in ("utm_source", "utm_medium", "utm_campaign", "referrer", "landing_page"):
            self.assertIn(column, cols)
        self.assertEqual(row["email"], "part@example.com")
        self.assertEqual(row["utm_source"], "linkedin")
        self.assertEqual(row["utm_medium"], "social")
        self.assertEqual(row["utm_campaign"], "launch")
        self.assertEqual(row["download_count"], 3)
        self.assertEqual(row["referrer"], "")
        self.assertEqual(row["landing_page"], "")
        self.assertIsNotNone(index)
        self.assertIsNotNone(events)
        self.assertIn("free_license_id", key_cols)
        self.assertIsNotNone(intents)

    def test_migrate_adds_free_license_id_to_an_existing_pro_keys_table(self):
        path = tempfile.NamedTemporaryFile(prefix="nc-migrate-pro-", suffix=".db", delete=False)
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
               (code, name, email, created_at, download_count)
               VALUES (?, ?, ?, ?, 1)""",
            ("NC-PART-0003", "Person", "part@example.com", "2026-01-03T00:00:00"),
        )
        raw.execute("""
            CREATE TABLE pro_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                key_last4 TEXT NOT NULL,
                email TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        raw.execute(
            """INSERT INTO pro_keys (key_hash, key_last4, email, source, status, created_at)
               VALUES ('hash', '1234', 'kept@example.com', 'manual', 'active', '2026-01-03T00:00:00')"""
        )
        raw.commit()
        raw.close()

        ctx = multiprocessing.get_context("fork")
        proc = ctx.Process(target=_migrate_in_child, args=(path.name,))
        proc.start()
        proc.join(15)
        self.assertFalse(proc.is_alive())
        self.assertEqual(proc.exitcode, 0, f"migrate process exited {proc.exitcode}")

        db = sqlite3.connect(path.name)
        db.row_factory = sqlite3.Row
        try:
            cols = {row["name"] for row in db.execute("PRAGMA table_info(pro_keys)")}
            row = db.execute("SELECT email, free_license_id FROM pro_keys").fetchone()
            intents = db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'purchase_intents'"
            ).fetchone()
        finally:
            db.close()
            os.unlink(path.name)
            lock = path.name + ".migrate.lock"
            if os.path.exists(lock):
                os.unlink(lock)
        self.assertIn("free_license_id", cols)
        self.assertEqual(row["email"], "kept@example.com")
        self.assertIsNone(row["free_license_id"])
        self.assertIsNotNone(intents)

        empty = sqlite3.connect(":memory:")
        try:
            api._add_free_license_column(empty)
        finally:
            empty.close()


if __name__ == "__main__":
    unittest.main()
