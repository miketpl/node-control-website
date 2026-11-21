"""Synthetic checks for email-less Free, public downloads and update opt-in."""

import json
import os
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from unittest.mock import patch

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FREE_DOWNLOADS_PAUSED"] = "false"
os.environ["KEY_ENCRYPTION_KEY"] = "22" * 32
os.environ["MACHINE_HASH_KEY"] = "test-only-machine-hash-key"
os.environ["API_PUBLIC_URL"] = "https://api.nodecontrol.io"

import app as api
import free_ungate
import licence_v1
import trial
from app import app, get_db

ASSET = "https://release-assets.example/free"
ALERT_TO = "alerts@example.com"


class _NowThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class FreeUngateTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.mail = []
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        app.config["ADMIN_ALERT_EMAIL"] = ""
        app.config["FREE_CLAIM_DAILY_CAP"] = "300"
        app.config["FREE_CLAIM_REPEAT"] = ""
        app.config["FREE_DOWNLOADS_PAUSED"] = "false"
        licence_v1.set_flag("free_downloads_paused", "false")
        licence_v1.set_flag("free_trial_enabled", "true")
        db = get_db()
        for table in (
            "licenses", "devices", "free_trials", "funnel_daily", "download_events",
            "free_claims", "update_subscribers", "admin_daily_counts", "rate_limits",
        ):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()

    def tearDown(self):
        self.mail_patch.stop()

    def _send(self, *args, **kwargs):
        self.mail.append(args)
        return True

    def _describe(self, repo, release, platform, arch):
        name = "NodeControl-Free.dmg" if platform == "mac" else "NodeControl-Free.exe"
        return {
            "name": name, "size": 12, "sha256": "ab" * 32,
            "asset": {"id": 9, "name": name}, "version": "0.9.48",
            "published_at": "2026-11-01T00:00:00Z", "notes_markdown": "",
        }

    def test_empty_email_hash_uses_the_licence_id(self):
        one = trial.email_hash("", 41)
        two = trial.email_hash("", 42)
        same = trial.email_hash("ada@example.com", 41)
        plain = trial.email_hash("ada@example.com")
        self.assertNotEqual(one, two)
        self.assertEqual(same, plain)
        self.assertNotEqual(one, plain)
        record = {"tier": "free", "kind": "free", "id": 41, "email": "", "status": "active"}
        view = trial._state_for(record, "unavailable", "0.9.48", licence_v1.utcnow())
        self.assertEqual(view["reason"], "no_machine")
        missing = trial._state_for(record, None, "0.9.48", licence_v1.utcnow())
        self.assertEqual(missing["reason"], "no_machine")

    def test_two_email_less_licences_share_a_machine_once(self):
        first = {"tier": "free", "kind": "free", "id": 51, "email": "", "status": "active"}
        second = {"tier": "free", "kind": "free", "id": 52, "email": "", "status": "active"}
        machine = "cd" * 32
        other = "ef" * 32
        self.assertIsNotNone(trial._insert_trial(first, "install-1", machine, "auto"))
        self.assertIsNotNone(trial._insert_trial(second, "install-2", other, "auto"))
        self.assertIsNone(trial._insert_trial(
            {"tier": "free", "kind": "free", "id": 53, "email": "", "status": "active"},
            "install-3", machine, "auto",
        ))

    def test_instant_key_and_public_download_and_opt_in(self):
        issued = self.client.post("/api/free/instant-key", json={"platform": "mac", "utm_source": "linkedin"})
        self.assertEqual(issued.status_code, 200)
        key = issued.get_json()["licence_key"]
        self.assertTrue(key.startswith("NC-"))
        db = get_db()
        row = db.execute("SELECT email, source, status, ip_address FROM licenses WHERE code = ?", (key,)).fetchone()
        db.close()
        self.assertEqual(row["email"], "")
        self.assertEqual(row["source"], "web_instant")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["ip_address"], "")
        self.assertNotIn(key, json.dumps(self.client.get(
            "/api/admin/stats/v1",
            headers={"Authorization": "Bearer test-admin-token"},
        ).get_json().get("marketing")))

        app.config["FREE_CLAIM_DAILY_CAP"] = "1"
        blocked = self.client.post("/api/free/instant-key", json={"platform": "win"})
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.get_json()["error"]["code"], "claim_capacity")
        app.config["FREE_CLAIM_DAILY_CAP"] = "300"

        with patch.object(licence_v1, "_load_release", return_value={"tag_name": "v0.9.48", "published_at": "2026-11-01T00:00:00Z", "assets": []}), \
             patch.object(licence_v1, "_describe_asset", side_effect=self._describe), \
             patch.object(licence_v1, "_signed_asset_url", return_value=ASSET):
            meta = self.client.get("/api/v1/download/free/latest")
            self.assertEqual(meta.status_code, 200)
            self.assertEqual(meta.headers.get("X-Robots-Tag"), "noindex")
            self.assertEqual(meta.get_json()["mac"]["sha256"], "ab" * 32)
            first = self.client.get("/api/v1/download/free/latest/mac?utm_source=linkedin&utm_campaign=launch")
            self.assertEqual(first.status_code, 302)
            self.assertEqual(first.location, ASSET)
            second = self.client.get("/api/v1/download/free/latest/mac?utm_source=linkedin")
            self.assertEqual(second.status_code, 302)
        db = get_db()
        rows = db.execute(
            "SELECT license_id, kind, utm_source, utm_campaign FROM download_events WHERE kind = 'direct'"
        ).fetchall()
        db.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["license_id"], 0)
        self.assertEqual(rows[0]["utm_source"], "linkedin")
        self.assertEqual(rows[0]["utm_campaign"], "launch")

        opted = self.client.post("/api/free/updates/subscribe", json={
            "email": "ada@example.com", "consent": True, "consent_text_version": "v1",
        })
        self.assertEqual(opted.status_code, 202)
        self.assertEqual(opted.get_json()["message"], "Check your email to confirm.")
        self.assertNotIn("ada@example.com", opted.get_data(as_text=True))
        self.assertTrue(self.mail)
        link = [line for line in self.mail[0][2].splitlines() if line.startswith("http")][0]
        token = link.split("t=", 1)[1]
        confirmed = self.client.get("/api/free/updates/confirm?t=" + token)
        self.assertEqual(confirmed.status_code, 200)
        self.assertNotIn("ada@example.com", confirmed.get_data(as_text=True))
        self.assertTrue(trial._updates_opted_in("ada@example.com"))
        gone = self.client.get("/api/free/updates/unsubscribe?t=" + token)
        self.assertEqual(gone.status_code, 200)
        self.assertNotIn("ada@example.com", gone.get_data(as_text=True))
        self.assertFalse(trial._updates_opted_in("ada@example.com"))

    def test_claim_issues_a_new_key_for_the_same_computer(self):
        machine = "12" * 32
        headers = {
            "User-Agent": "NodeControl/0.9.48 (free; mac; arm64)",
            "X-NC-Install-Id": str(uuid.uuid4()),
            "X-NC-Machine-Hash": machine,
        }
        body = {"platform": "mac", "arch": "arm64", "app_version": "0.9.48"}
        first = self.client.post("/api/v1/app/free/claim", json=body, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["new"])
        second = self.client.post("/api/v1/app/free/claim", json=body, headers=headers)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["new"])
        self.assertNotEqual(first.get_json()["licence_key"], second.get_json()["licence_key"])
        self.assertRegex(first.get_json()["licence_key"], r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertRegex(second.get_json()["licence_key"], r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertEqual(first.get_json()["tier"], "free")
        self.assertEqual(second.get_json()["tier"], "free")
        bare = dict(headers)
        bare["X-NC-Machine-Hash"] = "unavailable"
        bare["X-NC-Install-Id"] = str(uuid.uuid4())
        other = self.client.post("/api/v1/app/free/claim", json=body, headers=bare)
        self.assertEqual(other.status_code, 200)
        self.assertNotEqual(other.get_json()["licence_key"], first.get_json()["licence_key"])
        db = get_db()
        stored = db.execute("SELECT machine_hmac FROM free_claims").fetchall()
        db.close()
        self.assertNotIn(machine, "".join(row["machine_hmac"] for row in stored))
        app.config["FREE_CLAIM_REPEAT"] = "same"
        again = self.client.post("/api/v1/app/free/claim", json=body, headers=headers)
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.get_json()["new"])
        self.assertEqual(again.get_json()["licence_key"], second.get_json()["licence_key"])

    def _claim(self, machine, install=None):
        headers = {
            "User-Agent": "NodeControl/0.9.48 (free; mac; arm64)",
            "X-NC-Install-Id": install or str(uuid.uuid4()),
            "X-NC-Machine-Hash": machine,
        }
        return self.client.post(
            "/api/v1/app/free/claim",
            json={"platform": "mac", "arch": "arm64", "app_version": "0.9.48"},
            headers=headers,
        )

    def _activate(self, key, machine, install):
        return self.client.post(
            "/api/v1/app/activate",
            json={"tier": "free", "app_version": "0.9.48", "platform": "mac", "arch": "arm64"},
            headers={
                "Authorization": "Bearer " + key,
                "User-Agent": "NodeControl/0.9.48 (free; mac; arm64)",
                "X-NC-Install-Id": install,
                "X-NC-Machine-Hash": machine,
            },
        )

    def _confirm_optin(self, email, licence_key=None):
        body = {"email": email, "consent": True, "consent_text_version": "v1"}
        if licence_key:
            body["licence_key"] = licence_key
        before = len(self.mail)
        opted = self.client.post("/api/free/updates/subscribe", json=body)
        self.assertEqual(opted.status_code, 202)
        self.assertNotIn(email, opted.get_data(as_text=True))
        if len(self.mail) == before:
            return opted
        link = [line for line in self.mail[-1][2].splitlines() if line.startswith("http")][0]
        token = link.split("t=", 1)[1]
        confirmed = self.client.get("/api/free/updates/confirm?t=" + token)
        self.assertEqual(confirmed.status_code, 200)
        self.assertNotIn(email, confirmed.get_data(as_text=True))
        return confirmed

    def _trial_count(self):
        db = get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM free_trials").fetchone()["c"]
        db.close()
        return count

    def _assert_free_lease(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["tier"], "free")
        licence = body["licence"]
        self.assertEqual(licence["edition"], "free")
        self.assertNotEqual(licence["entitlements"], ["all"])
        self.assertIsNotNone(licence["trial"])
        self.assertNotEqual(licence["edition"], "pro")

    def test_fresh_hash_starts_a_trial_and_a_missing_hash_does_not(self):
        machine = "ab" * 32
        install = str(uuid.uuid4())
        issued = self._claim(machine, install)
        self.assertRegex(issued.get_json()["licence_key"], r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        started = self._activate(issued.get_json()["licence_key"], machine, install)
        self._assert_free_lease(started)
        self.assertTrue(started.get_json()["licence"]["trial"]["active"])
        self.assertEqual(self._trial_count(), 1)

        bare = self._claim("unavailable")
        self.assertRegex(bare.get_json()["licence_key"], r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        quiet = self._activate(bare.get_json()["licence_key"], "unavailable", str(uuid.uuid4()))
        self._assert_free_lease(quiet)
        self.assertFalse(quiet.get_json()["licence"]["trial"]["active"])
        self.assertEqual(self._trial_count(), 1)

        instant = self.client.post("/api/free/instant-key", json={"platform": "mac"})
        self.assertEqual(instant.status_code, 200)
        self.assertRegex(instant.get_json()["licence_key"], r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertEqual(instant.get_json()["tier"], "free")
        self.assertNotIn("pro", instant.get_json()["tier"])

    def test_repeat_defaults_to_a_new_key(self):
        machine = "cd" * 32
        app.config["FREE_CLAIM_REPEAT"] = ""
        first = self._claim(machine)
        app.config["FREE_CLAIM_REPEAT"] = "nope"
        second = self._claim(machine)
        self.assertTrue(second.get_json()["new"])
        self.assertNotEqual(second.get_json()["licence_key"], first.get_json()["licence_key"])
        self.assertRegex(second.get_json()["licence_key"], r"^NC-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        app.config["FREE_CLAIM_REPEAT"] = "same"
        again = self._claim(machine)
        self.assertFalse(again.get_json()["new"])
        self.assertEqual(again.get_json()["licence_key"], second.get_json()["licence_key"])

    def test_new_code_does_not_grant_a_second_trial(self):
        machine = "ef" * 32
        install = str(uuid.uuid4())
        app.config["FREE_CLAIM_REPEAT"] = ""
        first = self._claim(machine, install)
        started = self._activate(first.get_json()["licence_key"], machine, install)
        self.assertTrue(started.get_json()["licence"]["trial"]["active"])
        second_install = str(uuid.uuid4())
        second = self._claim(machine, second_install)
        self.assertNotEqual(second.get_json()["licence_key"], first.get_json()["licence_key"])
        again = self._activate(second.get_json()["licence_key"], machine, second_install)
        self._assert_free_lease(again)
        self.assertFalse(again.get_json()["licence"]["trial"]["active"])
        self.assertEqual(again.get_json()["licence"]["trial"]["reason"], "machine_used")
        self._confirm_optin("ada@example.com", second.get_json()["licence_key"])
        self.assertEqual(self._trial_count(), 1)

    def test_reinstall_still_uses_the_cap_and_the_rate_limit(self):
        app.config["FREE_CLAIM_REPEAT"] = ""
        app.config["FREE_CLAIM_DAILY_CAP"] = "1"
        first = self._claim("a1" * 32)
        self.assertEqual(first.status_code, 200)
        blocked = self._claim("b2" * 32)
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.get_json()["error"]["code"], "claim_capacity")
        app.config["FREE_CLAIM_DAILY_CAP"] = "300"
        machine = "c3" * 32
        for _ in range(5):
            self.assertEqual(self._claim(machine).status_code, 200)
        limited = self._claim(machine)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.get_json()["error"]["code"], "rate_limited")

    def test_confirmed_email_unlocks_one_trial(self):
        issued = self.client.post("/api/free/instant-key", json={"platform": "win"})
        key = issued.get_json()["licence_key"]
        self._confirm_optin("ada@example.com", key)
        db = get_db()
        row = db.execute("SELECT email FROM licenses WHERE code = ?", (key,)).fetchone()
        db.close()
        self.assertEqual(row["email"], "ada@example.com")
        self.assertEqual(self._trial_count(), 1)
        install = str(uuid.uuid4())
        started = self._activate(key, "d4" * 32, install)
        self._assert_free_lease(started)
        self.assertTrue(started.get_json()["licence"]["trial"]["active"])
        other = self.client.post("/api/free/instant-key", json={"platform": "mac"})
        self._confirm_optin("ada@example.com", other.get_json()["licence_key"])
        self.assertEqual(self._trial_count(), 1)

    def _public_download(self, platform="mac", query="", headers=None):
        stack = ExitStack()
        stack.enter_context(patch.object(free_ungate.threading, "Thread", _NowThread))
        stack.enter_context(patch.object(
            licence_v1, "_load_release",
            return_value={"tag_name": "v0.9.48", "published_at": "2026-11-01T00:00:00Z", "assets": []},
        ))
        stack.enter_context(patch.object(licence_v1, "_describe_asset", side_effect=self._describe))
        stack.enter_context(patch.object(licence_v1, "_signed_asset_url", return_value=ASSET))
        self.addCleanup(stack.close)
        stack.__enter__()
        return self.client.get(
            "/api/v1/download/free/latest/" + platform + query,
            headers=headers,
        )

    def _direct_count(self):
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) AS c FROM download_events WHERE kind = 'direct'"
        ).fetchone()["c"]
        db.close()
        return count

    def test_public_download_alert_fires(self):
        app.config["ADMIN_ALERT_EMAIL"] = ALERT_TO
        app.config["FREE_DOWNLOAD_ALERTS"] = ""
        app.config["FREE_DOWNLOAD_ALERT_DAILY_CAP"] = ""
        self.assertEqual(free_ungate._alert_cap(), 1000)
        sent = self._public_download(
            query="?utm_source=linkedin&utm_medium=cpc&utm_campaign=launch&utm_content=ad",
            headers={"Referer": "https://news.ycombinator.com/item?id=1"},
        )
        self.assertEqual(sent.status_code, 302)
        self.assertEqual(sent.location, ASSET)
        self.assertEqual(len(self.mail), 1)
        self.assertEqual(self.mail[0][0], ALERT_TO)
        self.assertEqual(self.mail[0][1], "Node Control Free download (mac)")
        text = self.mail[0][2]
        prefix = free_ungate._hash_token("127.0.0.1")[:12]
        self.assertIn("Platform: mac\n", text)
        self.assertIn("Version: 0.9.48\n", text)
        self.assertIn("Source: linkedin\n", text)
        self.assertIn("Medium: cpc\n", text)
        self.assertIn("Campaign: launch\n", text)
        self.assertIn("Content: ad\n", text)
        self.assertIn("Today: 1\n", text)
        self.assertIn("Likely crawler: no\n", text)
        self.assertIn("Repeat within 24h: no\n", text)
        self.assertIn(f"Client: {prefix}\n", text)
        self.assertIn("Referrer: news.ycombinator.com\n", text)
        self.assertNotIn(free_ungate._hash_token("127.0.0.1"), text)
        self.assertRegex(text, r"Time: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        self.assertNotIn("127.0.0.1", text)
        self.assertNotIn("@", text)
        self.assertNotIn("/item", text)

    def test_public_download_alert_includes_crawlers_and_obeys_the_switch(self):
        app.config["ADMIN_ALERT_EMAIL"] = ALERT_TO
        app.config["FREE_DOWNLOAD_ALERTS"] = "false"
        quiet = self._public_download(headers={"CF-Connecting-IP": "203.0.113.10"})
        self.assertEqual(quiet.status_code, 302)
        self.assertEqual(self.mail, [])
        self.assertEqual(self._direct_count(), 1)
        app.config["FREE_DOWNLOAD_ALERTS"] = "true"
        bot_agent = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        bot = self._public_download(headers={
            "User-Agent": bot_agent,
            "CF-Connecting-IP": "203.0.113.11",
        })
        self.assertEqual(bot.status_code, 302)
        self.assertEqual(len(self.mail), 1)
        self.assertIn("Likely crawler: yes\n", self.mail[0][2])
        self.assertIn("User-Agent: " + bot_agent + "\n", self.mail[0][2])
        self.assertNotIn("203.0.113.11", self.mail[0][2])
        self.assertEqual(self._direct_count(), 1)
        again = self._public_download(headers={
            "User-Agent": bot_agent,
            "CF-Connecting-IP": "203.0.113.11",
        })
        self.assertEqual(again.status_code, 302)
        self.assertEqual(len(self.mail), 2)
        self.assertIn("Repeat within 24h: yes\n", self.mail[1][2])
        self.assertEqual(self._direct_count(), 1)
        head = self.client.head("/api/v1/download/free/latest/win")
        self.assertIn(head.status_code, (200, 302))
        self.assertEqual(len(self.mail), 2)

    def test_public_download_alert_repeats_and_stops_at_the_cap(self):
        app.config["ADMIN_ALERT_EMAIL"] = ALERT_TO
        app.config["FREE_DOWNLOAD_ALERTS"] = "true"
        app.config["FREE_DOWNLOAD_ALERT_DAILY_CAP"] = "2"
        headers = {"CF-Connecting-IP": "203.0.113.20"}
        self.assertEqual(self._public_download(headers=headers).status_code, 302)
        self.assertEqual(self._public_download(headers=headers).status_code, 302)
        self.assertEqual(len(self.mail), 2)
        self.assertIn("Repeat within 24h: no\n", self.mail[0][2])
        self.assertIn("Repeat within 24h: yes\n", self.mail[1][2])
        prefix = free_ungate._hash_token("203.0.113.20")[:12]
        self.assertIn(f"Client: {prefix}\n", self.mail[0][2])
        self.assertNotIn("203.0.113.20", self.mail[0][2])
        self.assertNotIn("203.0.113.20", self.mail[1][2])
        self.assertNotIn(free_ungate._hash_token("203.0.113.20"), self.mail[0][2])
        other = {"CF-Connecting-IP": "203.0.113.21"}
        self.assertEqual(self._public_download(headers=other).status_code, 302)
        self.assertEqual(len(self.mail), 2)
        self.assertEqual(self._direct_count(), 2)

    def test_public_download_alert_mail_failure_still_redirects(self):
        app.config["ADMIN_ALERT_EMAIL"] = ALERT_TO
        app.config["FREE_DOWNLOAD_ALERTS"] = "true"
        self.mail_patch.stop()
        failed = patch.object(api, "_send_mail", side_effect=RuntimeError("smtp down"))
        failed.start()
        self.addCleanup(failed.stop)
        self.addCleanup(self.mail_patch.start)
        with self.assertLogs("free_ungate", level="ERROR") as caught:
            sent = self._public_download(headers={"CF-Connecting-IP": "203.0.113.30"})
        self.assertEqual(sent.status_code, 302)
        self.assertEqual(sent.location, ASSET)
        logged = "\n".join(caught.output)
        self.assertIn("Admin alert was not sent", logged)
        self.assertNotIn("203.0.113.30", logged)
        self.assertNotIn(ALERT_TO, logged)
        self.assertNotIn("smtp down", logged)
