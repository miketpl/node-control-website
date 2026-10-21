"""Admin download alerts. Addresses in this file are example.com only."""

import json
import logging
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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

import alerts
import app as api
import licence_v1
import stripe
from app import app, get_db


ASSET_URL = "https://release-assets.githubusercontent.com/example"
ADMIN = "alerts@example.com"


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


class AdminAlertTests(unittest.TestCase):
    def setUp(self):
        _InlineThread.started = 0
        self.mail = []
        self.thread_patch = patch.object(alerts.threading, "Thread", _InlineThread)
        self.thread_patch.start()
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        self.client = app.test_client()
        app.config["ADMIN_ALERT_EMAIL"] = ADMIN
        app.config["ADMIN_ALERT_SKIP_LICENCE_IDS"] = ""
        app.config["FREE_DOWNLOADS_PAUSED"] = "false"
        app.config["LEGACY_ALLOWLIST_SYNC"] = "false"
        app.config["MAINTENANCE"] = "false"
        app.config["SMTP_USER"] = "tester@example.com"
        app.config["SMTP_PASS"] = "test-pass"
        app.config["KEY_ENCRYPTION_KEY"] = "11" * 32
        licence_v1.set_flag("free_downloads_paused", "false")
        licence_v1.set_flag("maintenance", "false")
        db = get_db()
        for table in (
            "licenses",
            "download_events",
            "admin_alert_log",
            "pro_keys",
            "pro_subscriptions",
            "stripe_events",
            "rate_limits",
        ):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()

    def tearDown(self):
        self.mail_patch.stop()
        self.thread_patch.stop()
        app.config["ADMIN_ALERT_EMAIL"] = ""
        app.config["ADMIN_ALERT_SKIP_LICENCE_IDS"] = ""

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
        return [item for item in self.mail if str(item["subject"]).startswith("[Node Control]")]

    def _insert(self, code="NC-AB12-CD34", **overrides):
        row = {
            "code": code,
            "name": "Pat Example",
            "email": "person@example.com",
            "company": "Example Ltd",
            "platform": "macos",
            "tier": "free",
            "status": "active",
            "created_at": "2026-10-21T12:00:00",
            "verified_at": "2026-10-21T12:05:00",
            "ip_address": "198.51.100.20",
            "utm_source": "linkedin",
            "utm_medium": "social",
            "utm_campaign": "launch",
            "referrer": "https://www.linkedin.com/feed",
            "landing_page": "/",
        }
        row.update(overrides)
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO licenses (
                code, name, email, company, platform, tier, status,
                created_at, verified_at, ip_address,
                utm_source, utm_medium, utm_campaign, referrer, landing_page
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["code"], row["name"], row["email"], row["company"], row["platform"],
                row["tier"], row["status"], row["created_at"], row["verified_at"],
                row["ip_address"], row["utm_source"], row["utm_medium"], row["utm_campaign"],
                row["referrer"], row["landing_page"],
            ),
        )
        db.commit()
        licence_id = cursor.lastrowid
        db.close()
        return licence_id

    def _download(self, licence_id, platform="mac"):
        token = licence_v1.make_free_download_token(licence_id, platform)

        def describe(repo, release, asset_platform, arch):
            if asset_platform == "win":
                name = "NodeControl-Setup-x64.exe"
            else:
                name = "NodeControl-0.9.41.dmg"
            return {
                "name": name,
                "size": 10,
                "sha256": "ab" * 32,
                "asset": {"id": 7, "name": name},
                "version": "0.9.41",
                "published_at": "",
                "notes_markdown": "",
            }

        with patch.object(licence_v1, "_load_release", return_value={"tag_name": "v0.9.41"}), \
             patch.object(licence_v1, "_describe_asset", side_effect=describe), \
             patch.object(licence_v1, "_signed_asset_url", return_value=ASSET_URL):
            return self.client.get(f"/api/v1/download/free/{platform}?t={token}")

    def _assert_closed(self, text, html):
        self.assertNotIn("@", text)
        self.assertNotIn("@", html)
        for line in text.splitlines():
            if not line or line.startswith("Further alerts this hour will not be sent."):
                continue
            label = line.split(":", 1)[0]
            self.assertIn(label, {
                "Event", "Tier", "Platform", "Arch", "Version", "Time",
                "Licence id", "Source", "Medium", "Campaign", "Referrer",
                "Landing page", "Today", "All time", "Sent this hour",
            })

    def test_unset_sends_nothing(self):
        licence_id = self._insert()
        for value in ("", "   "):
            app.config["ADMIN_ALERT_EMAIL"] = value
            started = _InlineThread.started
            res = self._download(licence_id)
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.location, ASSET_URL)
            self.assertEqual(_InlineThread.started, started)
            self.assertEqual(self._admin(), [])
        self.assertIsNone(alerts.queue({
            "kind": "free_download",
            "licence_id": licence_id,
            "email": "person@example.com",
        }))

    def test_one_alert_per_download(self):
        licence_id = self._insert()
        code = "NC-AB12-CD34"
        for kind in ("auto", "click"):
            beacon = self.client.post(
                "/api/download-event",
                data=json.dumps({"code": code, "platform": "mac", "kind": kind}),
                content_type="text/plain",
            )
            self.assertEqual(beacon.status_code, 204)
        self.assertEqual(self._admin(), [])

        first = self._download(licence_id, "mac")
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.location, ASSET_URL)
        mails = self._admin()
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails[0]["subject"], "[Node Control] New Free download")
        self.assertEqual(mails[0]["to"], ADMIN)
        self.assertFalse(mails[0]["log_recipient"])
        text = mails[0]["text"]
        self._assert_closed(text, mails[0]["html"])
        stamp = re.search(r"Time: \d{4}-\d{2}-\d{2} \d{2}:\d{2} Europe/London", text)
        self.assertIsNotNone(stamp)
        self.assertEqual(text, (
            "Event: Free download\n"
            "Tier: free\n"
            "Platform: mac\n"
            "Version: 0.9.41\n"
            f"{stamp.group(0)}\n"
            f"Licence id: {licence_id}\n"
            "Source: linkedin\n"
            "Medium: social\n"
            "Campaign: launch\n"
            "Referrer: www.linkedin.com\n"
            "Landing page: /\n"
            "Today: 1\n"
            "All time: 1\n"
        ))
        self.assertEqual(mails[0]["html"], "<pre>" + text + "</pre>")
        for hidden in ("person@example.com", "Pat Example", "Example Ltd", "198.51.100.20", "NC-"):
            self.assertNotIn(hidden, text)
            self.assertNotIn(hidden, mails[0]["html"])

        again = self._download(licence_id, "mac")
        self.assertEqual(again.status_code, 302)
        self.assertEqual(len(self._admin()), 1)

        windows = self._download(licence_id, "win")
        self.assertEqual(windows.status_code, 302)
        self.assertEqual(len(self._admin()), 2)
        self.assertIn("Platform: win\n", self._admin()[1]["text"])
        self.assertIn("Arch: x86_64\n", self._admin()[1]["text"])
        self.assertNotIn("Arch:", text)

        old = (datetime.now(timezone.utc) - timedelta(minutes=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db = get_db()
        db.execute(
            """
            UPDATE admin_alert_log SET created_at = ?
            WHERE kind = 'free_download' AND platform = 'mac'
            """,
            (old,),
        )
        db.commit()
        db.close()
        later = self._download(licence_id, "mac")
        self.assertEqual(later.status_code, 302)
        self.assertEqual(len(self._admin()), 3)
        self.assertEqual(self._admin()[2]["subject"], "[Node Control] New Free download")

    def test_body_has_no_personal_data(self):
        licence_id = self._insert(
            code="NC-PQ12-ZX98",
            name="Patricia Quinn",
            email="person@example.com",
            company="Acme Widgets",
            ip_address="203.0.113.50",
            utm_campaign="person@example.com",
            referrer="https://www.linkedin.com/in/patricia?e=person@example.com",
            landing_page="/?email=person@example.com",
        )
        res = self._download(licence_id, "mac")
        self.assertEqual(res.status_code, 302)
        mails = self._admin()
        self.assertEqual(len(mails), 1)
        text = mails[0]["text"]
        html = mails[0]["html"]
        self._assert_closed(text, html)
        self.assertIn("Referrer: www.linkedin.com\n", text)
        self.assertIn("Landing page: /\n", text)
        self.assertIn("Source: linkedin\n", text)
        self.assertIn("Medium: social\n", text)
        self.assertNotIn("Campaign:", text)
        self.assertNotIn("/in/", text)
        for hidden in (
            "person@example.com",
            "Patricia",
            "Quinn",
            "Acme",
            "Widgets",
            "203.0.113.50",
            "NC-PQ12-ZX98",
            "NC-",
            "email=",
        ):
            self.assertNotIn(hidden, text)
            self.assertNotIn(hidden, html)

    def test_mail_failure_still_redirects(self):
        licence_id = self._insert()
        handler = _LogCapture()
        root = logging.getLogger()
        root.addHandler(handler)

        def boom(*args, **kwargs):
            raise RuntimeError("smtp refused person@example.com")

        try:
            with patch.object(api, "_send_mail", side_effect=boom):
                res = self._download(licence_id, "mac")
        finally:
            root.removeHandler(handler)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.location, ASSET_URL)
        logged = "\n".join(handler.lines)
        self.assertIn("Admin alert was not sent", logged)
        self.assertNotIn("person@example.com", logged)
        self.assertNotIn(ADMIN, logged)
        db = get_db()
        kept = db.execute("SELECT COUNT(*) AS c FROM admin_alert_log").fetchone()["c"]
        db.close()
        self.assertEqual(kept, 1)
        self.assertEqual(self._admin(), [])

        again = self._download(licence_id, "mac")
        self.assertEqual(again.status_code, 302)
        self.assertEqual(self._admin(), [])

    def test_skip_list_mutes_one_licence(self):
        muted = self._insert(code="NC-MUTE-0001", email="muted@example.com")
        other = self._insert(code="NC-LIVE-0002", email="live@example.com")
        app.config["ADMIN_ALERT_SKIP_LICENCE_IDS"] = f"999, {muted}, 0"
        skipped = self._download(muted, "mac")
        self.assertEqual(skipped.status_code, 302)
        self.assertEqual(self._admin(), [])
        sent = self._download(other, "mac")
        self.assertEqual(sent.status_code, 302)
        self.assertEqual(len(self._admin()), 1)
        self.assertIn(f"Licence id: {other}\n", self._admin()[0]["text"])
        self.assertNotIn(f"Licence id: {muted}\n", self._admin()[0]["text"])

    def test_hour_cap_then_one_summary(self):
        ids = [
            self._insert(code=f"NC-CAP-000{number}", email=f"cap{number}@example.com")
            for number in range(1, 5)
        ]
        with patch.object(alerts, "ALERT_HOUR_CAP", 2):
            for licence_id in ids:
                res = self._download(licence_id, "mac")
                self.assertEqual(res.status_code, 302)
        mails = self._admin()
        self.assertEqual(len(mails), 3)
        self.assertEqual(mails[0]["subject"], "[Node Control] New Free download")
        self.assertEqual(mails[1]["subject"], "[Node Control] New Free download")
        self.assertEqual(mails[2]["subject"], "[Node Control] Alert summary")
        summary = mails[2]["text"]
        self._assert_closed(summary, mails[2]["html"])
        self.assertIn("Sent this hour: 2\n", summary)
        self.assertIn("Further alerts this hour will not be sent.\n", summary)
        self.assertNotIn("Licence id", summary)
        self.assertNotIn("NC-", summary)
        self.assertNotIn("example.com", summary)
        db = get_db()
        extra = db.execute(
            "SELECT COUNT(*) AS c FROM admin_alert_log WHERE kind = 'summary'"
        ).fetchone()["c"]
        db.close()
        self.assertEqual(extra, 1)

    @patch("app.smtplib.SMTP")
    def test_verified_signup_alerts_without_personal_data(self, smtp):
        requested = self.client.post("/api/request-access", json={
            "name": "Patricia Quinn",
            "email": "person@example.com",
            "company": "Acme Widgets",
            "platform": "macos",
            "utm_source": "linkedin",
            "utm_medium": "social",
            "utm_campaign": "launch",
            "referrer": "https://www.linkedin.com/in/patricia",
            "landing_page": "/?email=person@example.com",
        })
        self.assertEqual(requested.status_code, 200)
        self.assertEqual(self._admin(), [])
        db = get_db()
        pending = db.execute(
            "SELECT * FROM licenses WHERE email = ?",
            ("person@example.com",),
        ).fetchone()
        db.execute(
            """
            UPDATE licenses
            SET utm_campaign = ?, referrer = ?, landing_page = ?, ip_address = ?
            WHERE id = ?
            """,
            (
                "person@example.com",
                "https://www.linkedin.com/in/patricia?e=person@example.com",
                "/?email=person@example.com",
                "203.0.113.50",
                pending["id"],
            ),
        )
        db.commit()
        db.close()
        code = pending["verified_at"].split(":", 1)[1]
        verified = self.client.post("/api/verify", json={
            "email": "person@example.com",
            "code": code,
        })
        self.assertEqual(verified.status_code, 200)
        body = verified.get_json()
        self.assertEqual(body["tier"], "free")
        self.assertTrue(body["download_code"].startswith("NC-"))
        self.assertEqual(set(body), {"success", "download_code", "tier", "message"})
        mails = self._admin()
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails[0]["subject"], "[Node Control] New Free sign-up")
        text = mails[0]["text"]
        self._assert_closed(text, mails[0]["html"])
        self.assertIn("Event: Free sign-up\n", text)
        self.assertIn("Tier: free\n", text)
        self.assertIn("Platform: mac\n", text)
        self.assertIn("Version: unknown\n", text)
        self.assertIn(f"Licence id: {pending['id']}\n", text)
        self.assertIn("Source: linkedin\n", text)
        self.assertIn("Medium: social\n", text)
        self.assertNotIn("Campaign:", text)
        self.assertIn("Referrer: www.linkedin.com\n", text)
        self.assertIn("Landing page: /\n", text)
        self.assertIn("Today: 1\n", text)
        self.assertIn("All time: 1\n", text)
        for hidden in (
            "person@example.com",
            "Patricia",
            "Quinn",
            "Acme",
            "203.0.113.50",
            "127.0.0.1",
            body["download_code"],
            "NC-",
        ):
            self.assertNotIn(hidden, text)
            self.assertNotIn(hidden, mails[0]["html"])

    def test_paid_checkout_alerts_without_buyer_details(self):
        subs = {}

        def retrieve(subscription_id):
            return subs[subscription_id]

        def construct(payload, sig, secret):
            if sig != "good" or secret != app.config["STRIPE_WEBHOOK_SECRET"]:
                raise stripe.SignatureVerificationError("bad signature", sig)
            return json.loads(payload)

        app.config["STRIPE_SECRET_KEY"] = "sk_test_x"
        app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        app.config["STRIPE_PRICE_PRO_MONTHLY"] = "price_month"
        app.config["LEGACY_ALLOWLIST_SYNC"] = "false"

        def post(event_id, event_type, obj):
            return self.client.post(
                "/api/stripe/webhook",
                data=json.dumps({"id": event_id, "type": event_type, "data": {"object": obj}}),
                headers={"Stripe-Signature": "good", "Content-Type": "application/json"},
            )

        with patch.object(api.stripe.Subscription, "retrieve", side_effect=retrieve), \
             patch.object(api.stripe.Webhook, "construct_event", side_effect=construct):
            subs["sub_paid"] = {
                "id": "sub_paid",
                "status": "active",
                "customer": "cus_1",
                "current_period_end": 1800000000,
                "cancel_at_period_end": False,
                "metadata": {"plan": "monthly"},
            }
            paid = post("evt_paid", "checkout.session.completed", {
                "id": "cs_paid",
                "mode": "subscription",
                "payment_status": "paid",
                "customer": "cus_1",
                "customer_email": "buyer@example.com",
                "customer_details": {"email": "buyer@example.com", "name": "Ada Lovelace"},
                "subscription": "sub_paid",
                "metadata": {"plan": "monthly"},
            })
            self.assertEqual(paid.status_code, 200)
            self.assertEqual(paid.get_json(), {"received": True})
            welcome = [item for item in self.mail if item["to"] == "buyer@example.com"]
            self.assertEqual(len(welcome), 1)
            self.assertIn("buyer@example.com", welcome[0]["text"])
            self.assertIn("Ada Lovelace", welcome[0]["text"])
            self.assertIn("NCP-", welcome[0]["text"])
            admin = self._admin()
            self.assertEqual(len(admin), 1)
            self.assertEqual(admin[0]["subject"], "[Node Control] New Pro purchase")
            self.assertEqual(admin[0]["to"], ADMIN)
            text = admin[0]["text"]
            self._assert_closed(text, admin[0]["html"])
            self.assertIn("Event: Pro purchase\n", text)
            self.assertIn("Tier: pro\n", text)
            self.assertIn("Platform: unknown\n", text)
            self.assertIn("Version: unknown\n", text)
            self.assertIn("Today: 1\n", text)
            self.assertIn("All time: 1\n", text)
            db = get_db()
            key_id = db.execute(
                "SELECT id FROM pro_keys WHERE subscription_id = 'sub_paid'"
            ).fetchone()["id"]
            db.close()
            self.assertIn(f"Licence id: {key_id}\n", text)
            for hidden in ("buyer@example.com", "Ada", "Lovelace", "NCP-", "cus_1", "sub_paid"):
                self.assertNotIn(hidden, text)
                self.assertNotIn(hidden, admin[0]["html"])

            again = post("evt_paid", "checkout.session.completed", {
                "id": "cs_paid",
                "mode": "subscription",
                "payment_status": "paid",
                "customer_email": "buyer@example.com",
                "customer_details": {"name": "Ada Lovelace"},
                "subscription": "sub_paid",
            })
            self.assertEqual(again.status_code, 200)
            self.assertEqual(len(self._admin()), 1)
            self.assertEqual(len([item for item in self.mail if item["to"] == "buyer@example.com"]), 1)

            renewed = post("evt_invoice", "invoice.paid", {
                "subscription": "sub_paid",
                "customer": "cus_1",
                "customer_email": "buyer@example.com",
            })
            self.assertEqual(renewed.status_code, 200)
            self.assertEqual(len(self._admin()), 1)

            subs["sub_free"] = dict(subs["sub_paid"])
            subs["sub_free"]["id"] = "sub_free"
            unpaid = post("evt_unpaid", "checkout.session.completed", {
                "id": "cs_unpaid",
                "mode": "subscription",
                "payment_status": "no_payment_required",
                "customer": "cus_1",
                "customer_email": "trial@example.com",
                "customer_details": {"email": "trial@example.com", "name": "Trial Person"},
                "subscription": "sub_free",
                "metadata": {"plan": "monthly"},
            })
            self.assertEqual(unpaid.status_code, 200)
            self.assertEqual(len(self._admin()), 1)
            trial_mail = [item for item in self.mail if item["to"] == "trial@example.com"]
            self.assertEqual(len(trial_mail), 1)

            app.config["ADMIN_ALERT_SKIP_LICENCE_IDS"] = str(key_id)
            db = get_db()
            db.execute("DELETE FROM admin_alert_log")
            db.commit()
            db.close()
            self.mail.clear()
            alerts.queue({"kind": "pro_purchase", "licence_id": key_id, "email": "buyer@example.com"})
            self.assertEqual(self._admin(), [])
