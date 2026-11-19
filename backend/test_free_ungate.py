"""Synthetic checks for email-less Free, public downloads and update opt-in."""

import json
import os
import tempfile
import unittest
import uuid
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


class FreeUngateTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.mail = []
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        app.config["ADMIN_ALERT_EMAIL"] = ""
        app.config["FREE_CLAIM_DAILY_CAP"] = "300"
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
        unsub = free_ungate._optin_serializer().dumps({"id": 1})
        gone = self.client.get("/api/free/updates/unsubscribe?t=" + unsub)
        self.assertEqual(gone.status_code, 200)
        self.assertNotIn("ada@example.com", gone.get_data(as_text=True))
        self.assertFalse(trial._updates_opted_in("ada@example.com"))

    def test_claim_returns_the_same_key_for_one_computer(self):
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
        self.assertFalse(second.get_json()["new"])
        self.assertEqual(first.get_json()["licence_key"], second.get_json()["licence_key"])
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
