"""Local tests for the licence API. SMTP and GitHub are mocked."""

import base64
import json
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

import app as api  # noqa: E402
from app import app, get_db  # noqa: E402


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

    def urlopen(self, req, timeout=10):
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
        app.config["LICENSE_REPO"] = "miketpl/node-control-license-free"
        db = get_db()
        db.execute("DELETE FROM licenses")
        db.commit()
        db.close()

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

    def test_health_reads_database(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["database"], "ok")

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


if __name__ == "__main__":
    unittest.main()
