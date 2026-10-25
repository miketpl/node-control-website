"""Pro subscription checkout, webhooks, allow-list, and gated downloads."""

import base64
import html
import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASS"] = ""
os.environ["FREE_DOWNLOADS_PAUSED"] = "false"
os.environ["KEY_ENCRYPTION_KEY"] = "11" * 32
os.environ["LEGACY_ALLOWLIST_SYNC"] = "false"

import stripe
import app
import licence_v1


BETA_DOC = {
    "allowed_emails": ["Beta.User@Example.com"],
    "grace_period_days": 7,
    "kept": "yes",
}


class GitHubFake:
    def __init__(self):
        self.doc = json.loads(json.dumps(BETA_DOC))
        self.sha = "sha-1"
        self.puts = 0
        self.fail_next_puts = 0
        self.calls = []
        self.release_assets = [
            {"id": 11, "name": "Node.Control-pro.dmg"},
            {"id": 12, "name": "Node.Control-pro-Setup.exe"},
        ]

    def __call__(self, req, timeout=15, follow_redirects=True):
        auth = req.headers.get("Authorization")
        self.calls.append((req.full_url, req.get_method(), auth, follow_redirects))
        url = req.full_url
        if "/releases/latest" in url:
            return 200, {}, json.dumps({"assets": self.release_assets}).encode()
        if "/releases/assets/" in url:
            asset_id = url.rstrip("/").split("/")[-1]
            name = "mac" if asset_id == "11" else "win"
            return 302, {"Location": f"https://objects.example/{name}?sig=short"}, b""
        if "allowlist.json" in url and req.get_method() == "GET":
            payload = {
                "content": base64.b64encode(json.dumps(self.doc).encode()).decode(),
                "sha": self.sha,
                "encoding": "base64",
            }
            return 200, {}, json.dumps(payload).encode()
        if "allowlist.json" in url and req.get_method() == "PUT":
            if self.fail_next_puts:
                self.fail_next_puts -= 1
                return 409, {}, b""
            body = json.loads(req.data.decode())
            if body.get("sha") != self.sha or body.get("branch") != "main":
                return 409, {}, b""
            self.doc = json.loads(base64.b64decode(body["content"]))
            self.puts += 1
            self.sha = f"sha-{self.puts + 1}"
            return 200, {}, b"{}"
        return 404, {}, b""


class ProBillingTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.github = GitHubFake()
        self.github_patch = patch.object(app, "_github_request", self.github)
        self.github_patch.start()
        self.welcomes = []
        self.welcome_patch = patch.object(
            app, "_send_pro_welcome", side_effect=self._welcome
        )
        self.welcome_patch.start()
        self.subs = {}
        self.retrieve_patch = patch.object(
            app.stripe.Subscription, "retrieve", side_effect=self._retrieve
        )
        self.retrieve_patch.start()
        self.construct_patch = patch.object(
            app.stripe.Webhook, "construct_event", side_effect=self._construct
        )
        self.construct_patch.start()
        app.app.config["STRIPE_SECRET_KEY"] = "sk_test_x"
        app.app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        app.app.config["STRIPE_PRICE_PRO_MONTHLY"] = "price_month"
        app.app.config["STRIPE_PRICE_PRO_ANNUAL"] = "price_year"
        app.app.config["GITHUB_PAT_WRITE"] = "ghp_write_token"
        app.app.config["GITHUB_PAT_REGISTRATIONS"] = ""
        app.app.config["PRO_RELEASES_PAT"] = "ghp_releases_secret"
        app.app.config["PRO_DOWNLOAD_SECRET"] = "download-secret"
        app.app.config["SITE_URL"] = "https://nodecontrol.io"
        app.app.config["KEY_ENCRYPTION_KEY"] = "11" * 32
        app.app.config["LEGACY_ALLOWLIST_SYNC"] = ""
        app.app.config["FREE_DOWNLOADS_PAUSED"] = "false"
        db = app.get_db()
        db.execute("DELETE FROM pro_subscriptions")
        db.execute("DELETE FROM stripe_events")
        db.execute("DELETE FROM pro_keys")
        db.commit()
        db.close()

    def tearDown(self):
        self.construct_patch.stop()
        self.retrieve_patch.stop()
        self.welcome_patch.stop()
        self.github_patch.stop()

    def _welcome(self, row):
        self.welcomes.append(dict(row))
        return True

    def _retrieve(self, subscription_id):
        return self.subs[subscription_id]

    def _construct(self, payload, sig, secret):
        if sig != "good" or secret != app.app.config["STRIPE_WEBHOOK_SECRET"]:
            raise stripe.SignatureVerificationError("bad signature", sig)
        return json.loads(payload)

    def _sub(self, subscription_id, status="active", period_end=1800000000, plan="monthly"):
        self.subs[subscription_id] = {
            "id": subscription_id,
            "status": status,
            "customer": "cus_1",
            "current_period_end": period_end,
            "cancel_at_period_end": False,
            "metadata": {"plan": plan},
        }
        return self.subs[subscription_id]

    def _post_event(self, event_id, event_type, obj, sig="good"):
        payload = json.dumps({"id": event_id, "type": event_type, "data": {"object": obj}})
        return self.client.post(
            "/api/stripe/webhook",
            data=payload,
            headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
        )

    def _checkout(self, event_id, subscription_id, email, session_id="cs_test_1", plan="monthly"):
        self._sub(subscription_id, plan=plan)
        return self._post_event(event_id, "checkout.session.completed", {
            "id": session_id,
            "mode": "subscription",
            "payment_status": "paid",
            "customer": "cus_1",
            "customer_email": email,
            "customer_details": {"email": email, "name": "Ada"},
            "subscription": subscription_id,
            "metadata": {"plan": plan},
        })

    def test_checkout_session_uses_subscription_and_tax(self):
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return {"url": "https://checkout.stripe.test/c/pay", "id": "cs_1"}

        with patch.object(app.stripe.checkout.Session, "create", side_effect=create):
            res = self.client.post("/api/checkout", json={"plan": "annual", "email": "Ada@Example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["url"], "https://checkout.stripe.test/c/pay")
        self.assertEqual(captured["mode"], "subscription")
        self.assertEqual(captured["line_items"], [{"price": "price_year", "quantity": 1}])
        self.assertEqual(captured["automatic_tax"], {"enabled": True})
        self.assertEqual(captured["billing_address_collection"], "required")
        self.assertEqual(captured["tax_id_collection"], {"enabled": True})
        self.assertEqual(captured["customer_email"], "ada@example.com")
        self.assertIn("pro-success.html?session_id={CHECKOUT_SESSION_ID}", captured["success_url"])
        self.assertTrue(captured["cancel_url"].endswith("/#pricing"))

        res = self.client.post("/api/checkout", json={"plan": "weekly"})
        self.assertEqual(res.status_code, 400)
        app.app.config["STRIPE_PRICE_PRO_MONTHLY"] = ""
        res = self.client.post("/api/checkout", json={"plan": "monthly"})
        self.assertEqual(res.status_code, 503)

    def test_webhook_signature_and_idempotency(self):
        bad = self._post_event("evt_bad", "checkout.session.completed", {}, sig="nope")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.github.puts, 0)

        ok = self._checkout("evt_1", "sub_new", "payer@example.com")
        self.assertEqual(ok.status_code, 200)
        again = self._checkout("evt_1", "sub_new", "payer@example.com")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.github.puts, 0)
        self.assertEqual(len(self.welcomes), 1)
        self.assertEqual(self.github.doc["allowed_emails"], ["Beta.User@Example.com"])
        self.assertEqual(self.github.doc["grace_period_days"], 7)
        self.assertEqual(self.github.doc["kept"], "yes")
        db = app.get_db()
        keys = db.execute("SELECT COUNT(*) AS c FROM pro_keys WHERE subscription_id = 'sub_new'").fetchone()["c"]
        db.close()
        self.assertEqual(keys, 1)

    def test_hand_added_beta_email_is_not_removed(self):
        before = json.loads(json.dumps(self.github.doc))
        granted = self._checkout("evt_beta", "sub_beta", "Beta.User@Example.com")
        self.assertEqual(granted.status_code, 200)
        self.assertEqual(self.github.puts, 0)
        self.assertEqual(self.github.doc, before)
        row = app._get_pro_row_by_subscription("sub_beta")
        self.assertEqual(row["added_to_allowlist"], 0)

        ended = self._post_event("evt_beta_end", "customer.subscription.deleted", {
            "id": "sub_beta",
            "status": "canceled",
            "customer": "cus_1",
            "cancel_at_period_end": False,
        })
        self.assertEqual(ended.status_code, 200)
        self.assertEqual(self.github.puts, 0)
        self.assertEqual(self.github.doc, before)
        self.assertEqual(self.github.doc["allowed_emails"], ["Beta.User@Example.com"])

    def test_stripe_subscriber_is_removed_without_touching_beta_users(self):
        granted = self._checkout("evt_pay", "sub_pay", "payer@example.com")
        self.assertEqual(granted.status_code, 200)
        emails = [item.lower() for item in self.github.doc["allowed_emails"]]
        self.assertIn("beta.user@example.com", emails)
        self.assertNotIn("payer@example.com", emails)
        self.assertEqual(self.github.puts, 0)
        self.assertEqual(self.github.doc["grace_period_days"], 7)

        ended = self._post_event("evt_pay_end", "customer.subscription.deleted", {
            "id": "sub_pay",
            "status": "canceled",
            "customer": "cus_1",
        })
        self.assertEqual(ended.status_code, 200)
        emails = [item.lower() for item in self.github.doc["allowed_emails"]]
        self.assertNotIn("payer@example.com", emails)
        self.assertIn("beta.user@example.com", emails)
        self.assertEqual(self.github.doc["grace_period_days"], 7)
        self.assertEqual(self.github.doc["kept"], "yes")
        self.assertEqual(app._get_pro_row_by_subscription("sub_pay")["status"], "canceled")

    def test_second_active_subscription_keeps_the_email(self):
        self._checkout("evt_a", "sub_a", "payer@example.com", session_id="cs_a")
        self._checkout("evt_b", "sub_b", "payer@example.com", session_id="cs_b")
        row_b = app._get_pro_row_by_subscription("sub_b")
        self.assertEqual(row_b["added_to_allowlist"], 0)

        first = self._post_event("evt_a_end", "customer.subscription.deleted", {
            "id": "sub_a", "status": "canceled", "customer": "cus_1",
        })
        self.assertEqual(first.status_code, 200)
        self.assertNotIn("payer@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])
        self.assertEqual(app._get_pro_row_by_subscription("sub_a")["status"], "canceled")
        self.assertEqual(app._get_pro_row_by_subscription("sub_b")["status"], "active")

        second = self._post_event("evt_b_end", "customer.subscription.deleted", {
            "id": "sub_b", "status": "canceled", "customer": "cus_1",
        })
        self.assertEqual(second.status_code, 200)
        self.assertNotIn("payer@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])
        self.assertIn("beta.user@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])
        self.assertEqual(app._get_pro_row_by_subscription("sub_b")["status"], "canceled")
        self.assertEqual(self.github.puts, 0)

    def test_cancel_at_period_end_and_failed_payment_keep_access_until_it_ends(self):
        self._checkout("evt_live", "sub_live", "payer@example.com")
        puts_after_add = self.github.puts
        updated = self._post_event("evt_cancel_later", "customer.subscription.updated", {
            "id": "sub_live",
            "status": "active",
            "customer": "cus_1",
            "cancel_at_period_end": True,
            "current_period_end": 1800000000,
            "metadata": {"plan": "monthly"},
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.github.puts, puts_after_add)
        self.assertNotIn("payer@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])
        self.assertEqual(app._get_pro_row_by_subscription("sub_live")["status"], "active")

        self.subs["sub_live"]["status"] = "active"
        failed = self._post_event("evt_fail_open", "invoice.payment_failed", {
            "subscription": "sub_live",
            "customer_email": "payer@example.com",
        })
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(app._get_pro_row_by_subscription("sub_live")["status"], "active")
        self.assertNotIn("payer@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])

        self.subs["sub_live"]["status"] = "past_due"
        failed_closed = self._post_event("evt_fail_closed", "invoice.payment_failed", {
            "subscription": "sub_live",
            "customer_email": "payer@example.com",
        })
        self.assertEqual(failed_closed.status_code, 200)
        self.assertNotIn("payer@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])
        self.assertIn("beta.user@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])

    def test_invoice_paid_refreshes_the_period(self):
        self._checkout("evt_seed", "sub_seed", "payer@example.com")
        self.subs["sub_seed"]["current_period_end"] = 1900000000
        res = self._post_event("evt_invoice", "invoice.paid", {
            "subscription": "sub_seed",
            "customer": "cus_1",
            "customer_email": "payer@example.com",
        })
        self.assertEqual(res.status_code, 200)
        row = app._get_pro_row_by_subscription("sub_seed")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["current_period_end"], app._period_end_iso(self.subs["sub_seed"]))
        self.assertEqual(len(self.welcomes), 1)

    def test_allowlist_retries_a_conflict_and_uses_the_write_pat(self):
        # Allow-list sync is off, so a GitHub 409 cannot fail checkout.
        self.github.fail_next_puts = 1
        res = self._checkout("evt_retry", "sub_retry", "payer@example.com")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.github.puts, 0)
        self.assertNotIn("payer@example.com", [e.lower() for e in self.github.doc["allowed_emails"]])

        self.github.doc = json.loads(json.dumps(BETA_DOC))
        app.app.config["GITHUB_PAT_REGISTRATIONS"] = "ghp_regs_token"
        db = app.get_db()
        db.execute("DELETE FROM pro_subscriptions")
        db.execute("DELETE FROM stripe_events")
        db.execute("DELETE FROM pro_keys")
        db.commit()
        db.close()
        res = self._checkout("evt_regs", "sub_regs", "second@example.com")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.github.puts, 0)
        self.assertNotIn("second@example.com", self.github.doc["allowed_emails"])
        self.assertEqual(app._get_pro_row_by_subscription("sub_regs")["email"], "second@example.com")

    def test_download_token_is_gated(self):
        self._checkout("evt_dl", "sub_dl", "payer@example.com", session_id="cs_dl")
        with patch.object(app.stripe.checkout.Session, "retrieve", return_value={
            "id": "cs_dl",
            "status": "complete",
            "payment_status": "paid",
            "subscription": "sub_dl",
        }):
            session = self.client.get("/api/pro/session?session_id=cs_dl")
        self.assertEqual(session.status_code, 200)
        body = session.get_json()
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["email"], "payer@example.com")
        mac = self.client.get("/api/pro/download?token=" + body["downloads"]["mac"])
        self.assertEqual(mac.status_code, 302)
        self.assertEqual(mac.location, "https://objects.example/mac?sig=short")
        self.assertNotIn("ghp_releases_secret", mac.location)
        self.assertNotIn("ghp_releases_secret", mac.get_data(as_text=True))

        expired = app._make_download_token("payer@example.com", "sub_dl", "win", ttl_seconds=-10)
        denied = self.client.get("/api/pro/download?token=" + expired)
        self.assertEqual(denied.status_code, 403)

        calls_before = len(self.github.calls)
        db = app.get_db()
        db.execute("UPDATE pro_subscriptions SET status = 'canceled' WHERE stripe_subscription_id = 'sub_dl'")
        db.commit()
        db.close()
        fresh = app._make_download_token("payer@example.com", "sub_dl", "mac")
        inactive = self.client.get("/api/pro/download?token=" + fresh)
        self.assertEqual(inactive.status_code, 403)
        self.assertEqual(len(self.github.calls), calls_before)
        junk = self.client.get("/api/pro/download?token=not-a-token")
        self.assertEqual(junk.status_code, 403)

    def test_portal_response_does_not_reveal_the_address(self):
        self._checkout("evt_portal", "sub_portal", "payer@example.com")
        sent = []

        def send(email, url):
            sent.append((email, url))
            return True

        with patch.object(app, "_send_portal_email", side_effect=send), \
             patch.object(app.stripe.billing_portal.Session, "create", return_value={"url": "https://billing.stripe.test/session"}):
            known = self.client.post("/api/portal", json={"email": "payer@example.com"})
            unknown = self.client.post("/api/portal", json={"email": "nobody@example.com"})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.get_json(), unknown.get_json())
        self.assertEqual(sent, [("payer@example.com", "https://billing.stripe.test/session")])

    def test_failed_welcome_is_not_marked_so_stripe_can_retry(self):
        self.welcome_patch.stop()
        failed = patch.object(app, "_send_pro_welcome", return_value=False)
        failed.start()
        try:
            res = self._checkout("evt_mail", "sub_mail", "payer@example.com")
        finally:
            failed.stop()
        self.assertEqual(res.status_code, 500)
        db = app.get_db()
        marked = db.execute(
            "SELECT event_id FROM stripe_events WHERE event_id = 'evt_mail'"
        ).fetchone()
        db.close()
        self.assertIsNone(marked)
        self.welcome_patch.start()
        ok = self._checkout("evt_mail", "sub_mail", "payer@example.com")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(len(self.welcomes), 1)
        self.assertEqual(app._get_pro_row_by_subscription("sub_mail")["email"], "payer@example.com")
        self.assertNotIn("payer@example.com", [item.lower() for item in self.github.doc["allowed_emails"]])
        self.assertIn("beta.user@example.com", [item.lower() for item in self.github.doc["allowed_emails"]])

    def test_welcome_and_portal_html_are_clickable(self):
        captured = []

        def capture(to_email, subject, text_body, html_body, log_recipient=True):
            captured.append((to_email, subject, text_body, html_body))
            return True

        def token(email, subscription_id, platform, ttl_seconds=app.DOWNLOAD_EMAIL_TTL):
            self.assertEqual(email, "payer@example.com")
            self.assertEqual(subscription_id, "sub_html")
            self.assertEqual(ttl_seconds, app.DOWNLOAD_EMAIL_TTL)
            return platform + '&sig=1"x'

        self.welcome_patch.stop()
        row = {
            "plan": "monthly",
            "name": "Ada",
            "email": "payer@example.com",
            "stripe_subscription_id": "sub_html",
            "stripe_checkout_session_id": "",
        }
        try:
            with patch.object(app, "_send_mail", side_effect=capture), \
                 patch.object(app, "_make_download_token", side_effect=token), \
                 patch.object(licence_v1, "plaintext_for_subscription", return_value="NCP-AAAA-BBBB"):
                self.assertTrue(app._send_pro_welcome(row))
            session = dict(row)
            session["plan"] = "annual"
            session["stripe_checkout_session_id"] = 'cs_1&x="y'

            def unexpected_token(*_args, **_kwargs):
                raise AssertionError("a checkout session must keep its success-page link")

            with patch.object(app, "_send_mail", side_effect=capture), \
                 patch.object(app, "_make_download_token", side_effect=unexpected_token), \
                 patch.object(licence_v1, "plaintext_for_subscription", return_value=""):
                self.assertTrue(app._send_pro_welcome(session))
            portal = 'https://billing.stripe.test/p?a=1&b=2"x'
            with patch.object(app, "_send_mail", side_effect=capture):
                self.assertTrue(app._send_portal_email("payer@example.com", portal))
        finally:
            self.welcome_patch.start()

        _to, subject, text, html_body = captured[0]
        mac_url = 'https://api.nodecontrol.io/api/pro/download?token=mac&sig=1"x'
        win_url = 'https://api.nodecontrol.io/api/pro/download?token=win&sig=1"x'
        self.assertEqual(subject, "Your Node Control Professional subscription")
        self.assertIn("macOS: " + mac_url + "\n", text)
        self.assertIn("Windows: " + win_url + "\n", text)
        self.assertIn("These links last 24 hours and only work while the subscription is active.", text)
        self.assertIn("Professional, £25/month ex VAT", text)
        self.assertIn("NCP-AAAA-BBBB", text)
        self.assertIn("https://nodecontrol.io/#manage", text)
        self.assertNotIn("<a", text)
        self.assertIn(f'href="{html.escape(mac_url, quote=True)}"', html_body)
        self.assertIn(f'href="{html.escape(win_url, quote=True)}"', html_body)
        self.assertIn(">Download for Mac</", html_body)
        self.assertIn(">Download for Windows</", html_body)
        self.assertIn("If the link doesn't work, copy this address:", html_body)
        self.assertIn("These links last 24 hours and only work while the subscription is active.", html_body)
        self.assertNotIn('href="' + mac_url + '"', html_body)
        self.assertNotIn("&sig=", html_body)

        _to, subject, text, html_body = captured[1]
        page = 'https://nodecontrol.io/pro-success.html?session_id=cs_1&x="y'
        self.assertIn(page + "\n", text)
        self.assertIn("Professional, £255/year ex VAT", text)
        self.assertNotIn("api/pro/download?token=", text)
        self.assertNotIn("<a", text)
        self.assertIn(f'href="{html.escape(page, quote=True)}"', html_body)
        self.assertIn(">Download Pro</", html_body)
        self.assertNotIn('href="' + page + '"', html_body)

        _to, subject, text, html_body = captured[2]
        self.assertEqual(subject, "Manage your Node Control subscription")
        self.assertIn("\n" + portal + "\n", text)
        self.assertIn("The link expires. If it does, request another from https://nodecontrol.io/#manage", text)
        self.assertNotIn("<a", text)
        self.assertIn(f'href="{html.escape(portal, quote=True)}"', html_body)
        self.assertIn('href="https://nodecontrol.io/#manage"', html_body)
        self.assertIn(">Cancel or update the card</", html_body)
        self.assertNotIn('href="' + portal + '"', html_body)
        self.assertNotIn("&b=", html_body)

    def test_public_stripe_routes_are_rate_limited(self):
        def checkout(ip):
            return self.client.post(
                "/api/checkout",
                json={"plan": "monthly"},
                headers={"CF-Connecting-IP": ip},
            )

        with patch.object(
            app.stripe.checkout.Session, "create",
            return_value={"url": "https://checkout.stripe.test/c/pay", "id": "cs_rate"},
        ):
            for _ in range(10):
                allowed = checkout("203.0.113.10")
                self.assertEqual(allowed.status_code, 200)
            blocked = checkout("203.0.113.10")
            other = checkout("203.0.113.11")
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers["Retry-After"]), 0)
        self.assertEqual(blocked.get_json()["error"], "Too many requests. Try again later.")
        self.assertEqual(other.status_code, 200)

        generic = {
            "success": True,
            "message": "If that address has a Professional subscription, we sent a link to manage it.",
        }

        def portal(ip, email):
            return self.client.post(
                "/api/portal",
                json={"email": email},
                headers={"CF-Connecting-IP": ip},
            )

        for _ in range(3):
            known = portal("203.0.113.20", "Person@Example.com")
            self.assertEqual(known.status_code, 200)
            self.assertEqual(known.get_json(), generic)
        limited_email = portal("203.0.113.20", "person@example.com")
        self.assertEqual(limited_email.status_code, 429)
        self.assertEqual(limited_email.get_json(), generic)
        self.assertGreater(int(limited_email.headers["Retry-After"]), 0)
        still_open = portal("203.0.113.20", "other@example.com")
        self.assertEqual(still_open.status_code, 200)
        self.assertEqual(still_open.get_json(), generic)
        for n in range(8):
            res = portal("203.0.113.21", f"user{n}@example.com")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json(), generic)
        # Two of the ten are already used by the email-limit checks above? No, different IP.
        # 203.0.113.21 has 8. Two more, then the eleventh.
        self.assertEqual(portal("203.0.113.21", "user8@example.com").status_code, 200)
        self.assertEqual(portal("203.0.113.21", "user9@example.com").status_code, 200)
        ip_blocked = portal("203.0.113.21", "user10@example.com")
        self.assertEqual(ip_blocked.status_code, 429)
        self.assertEqual(ip_blocked.get_json(), generic)
        unknown = portal("203.0.113.22", "nobody@example.com")
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.get_json(), generic)

        def session(ip, session_id="cs_rate_session"):
            return self.client.get(
                "/api/pro/session?session_id=" + session_id,
                headers={"CF-Connecting-IP": ip},
            )

        with patch.object(app.stripe.checkout.Session, "retrieve", return_value={"status": "open"}):
            for _ in range(30):
                self.assertNotEqual(session("203.0.113.30").status_code, 429)
            ip_session = session("203.0.113.30")
            for n in range(60):
                self.assertNotEqual(session(f"203.0.113.{40 + n}", "cs_same").status_code, 429)
            same_session = session("198.51.100.9", "cs_same")
        self.assertEqual(ip_session.status_code, 429)
        self.assertIn("Retry-After", ip_session.headers)
        self.assertEqual(same_session.status_code, 429)
        self.assertIn("Retry-After", same_session.headers)

        def download(ip):
            return self.client.get(
                "/api/pro/download?token=not-a-token",
                headers={"CF-Connecting-IP": ip},
            )

        for _ in range(20):
            self.assertEqual(download("203.0.113.90").status_code, 403)
        limited_download = download("203.0.113.90")
        self.assertEqual(limited_download.status_code, 429)
        self.assertGreater(int(limited_download.headers["Retry-After"]), 0)
        self.assertEqual(download("203.0.113.91").status_code, 403)

    def test_allowlist_defaults_are_the_live_repo(self):
        source_path = os.path.join(os.path.dirname(__file__), "app.py")
        with open(source_path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('miketpl/node-control-registrations', source)
        self.assertIn('allowlist.json', source)
        self.assertIn("added_to_allowlist", source)
        self.assertIn("LEGACY_ALLOWLIST_SYNC", source)
        self.assertFalse(app._legacy_allowlist_enabled())


if __name__ == "__main__":
    unittest.main()
