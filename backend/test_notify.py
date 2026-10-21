"""Service notices. Addresses in this file are example.com only."""

import io
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("SMTP_USER", "tester@example.com")
os.environ.setdefault("SMTP_PASS", "test-pass")
os.environ.setdefault("FREE_DOWNLOADS_PAUSED", "false")
os.environ.setdefault("KEY_ENCRYPTION_KEY", "11" * 32)

import admin_cli
import app as api
from app import app, get_db


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.mail = []
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        self.client = app.test_client()
        app.config["ADMIN_TOKEN"] = "test-admin-token"
        app.config["ADMIN_READ_TOKEN"] = "test-read-token"
        app.config["NOTICE_UNSUBSCRIBE_SECRET"] = "test-unsubscribe-secret"
        app.config["NOTICE_THROTTLE_SECONDS"] = "0"
        app.config["API_PUBLIC_URL"] = "https://api.nodecontrol.io"
        db = get_db()
        for table in (
            "licenses", "pro_keys", "pro_subscriptions", "registrations",
            "telemetry_sessions", "notices_sent", "notice_opt_outs",
        ):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()

    def tearDown(self):
        self.mail_patch.stop()

    def _send(self, to_email, subject, text_body, html_body, log_recipient=True):
        self.mail.append({
            "to": to_email,
            "subject": subject,
            "text": text_body,
            "html": html_body,
            "log_recipient": log_recipient,
        })
        return True

    def _free(self, code, email, status="active", downloads=0):
        db = get_db()
        db.execute(
            """
            INSERT INTO licenses (
                code, name, email, company, platform, tier, status, created_at, download_count
            ) VALUES (?, 'Person', ?, '', 'macos', 'free', ?, '2026-10-21T00:00:00', ?)
            """,
            (code, email, status, downloads),
        )
        db.commit()
        row_id = db.execute("SELECT id FROM licenses WHERE code = ?", (code,)).fetchone()["id"]
        db.close()
        return row_id

    def _pro_key(self, email, status="active", source="manual", sub_id="", sub_status="active"):
        db = get_db()
        if sub_id:
            db.execute(
                """
                INSERT INTO pro_subscriptions (
                    email, name, stripe_subscription_id, plan, status,
                    created_at, updated_at
                ) VALUES (?, 'Person', ?, 'monthly', ?, '2026-10-21T00:00:00', '2026-10-21T00:00:00')
                """,
                (email, sub_id, sub_status),
            )
        db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, email, subscription_id, source, status, plan, created_at
            ) VALUES (?, 'WXYZ', ?, ?, ?, ?, 'monthly', '2026-10-21T00:00:00')
            """,
            (f"hash-{email}", email, sub_id, source, status),
        )
        db.commit()
        row_id = db.execute(
            "SELECT id FROM pro_keys WHERE key_hash = ?", (f"hash-{email}",)
        ).fetchone()["id"]
        db.close()
        return row_id

    def _version(self, kind, ref, version, table="registrations"):
        db = get_db()
        if table == "registrations":
            db.execute(
                """
                INSERT INTO registrations (
                    licence_kind, licence_ref, install_id, registration_token,
                    name, email, app_version, created_at
                ) VALUES (?, ?, ?, ?, 'Person', 'reg@example.com', ?, '2026-10-21T00:00:00')
                """,
                (kind, ref, f"inst-{kind}-{ref}-{version}", f"tok-{kind}-{ref}-{version}", version),
            )
        else:
            db.execute(
                """
                INSERT INTO telemetry_sessions (
                    licence_ref, licence_kind, install_id, session_id, app_version,
                    first_received_at, last_received_at
                ) VALUES (?, ?, ?, ?, ?, '2026-10-21T00:00:00', '2026-10-22T00:00:00')
                """,
                (ref, kind, f"inst-{kind}-{ref}", f"sess-{version}", version),
            )
        db.commit()
        db.close()

    def _notify(self, **extra):
        body = {
            "template": "upgrade-0.9.41",
            "audience": "free_downloaded",
            "dry_run": True,
        }
        body.update(extra)
        return self.client.post(
            "/api/admin/notify",
            json=body,
            headers={"Authorization": "Bearer test-admin-token"},
        )

    def test_read_token_is_rejected(self):
        res = self.client.post(
            "/api/admin/notify",
            json={"template": "upgrade-0.9.41", "audience": "free_all", "dry_run": True},
            headers={"Authorization": "Bearer test-read-token"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertNotIn("@", res.get_data(as_text=True))
        self.assertEqual(self.mail, [])

    def test_audiences_versions_and_dry_run_send_nothing(self):
        downloaded = self._free("NC-DOWN-0001", "down@example.com", downloads=2)
        self._free("NC-NONE-0001", "none@example.com", downloads=0)
        self._free("NC-PEND-0001", "pend@example.com", status="pending", downloads=3)
        self._version("free", downloaded, "0.9.40")
        quiet = self._free("NC-NEW-0001", "new@example.com", downloads=1)
        self._version("free", quiet, "0.9.41")
        unknown = self._free("NC-UNK-0001", "unknown@example.com", downloads=1)
        manual = self._pro_key("manual@example.com")
        inactive = self._pro_key(
            "oldsub@example.com", source="stripe", sub_id="sub_old", sub_status="canceled",
        )
        self._pro_key("live@example.com", source="stripe", sub_id="sub_live", sub_status="active")

        dry = self._notify(audience="free_downloaded", below_version="0.9.41")
        self.assertEqual(dry.status_code, 200)
        body = dry.get_json()
        self.assertEqual(body["matched"], 1)
        self.assertEqual(body["sent"], 0)
        self.assertTrue(body["dry_run"])
        self.assertEqual(self.mail, [])
        self.assertNotIn("@", dry.get_data(as_text=True))
        db = get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) AS c FROM notices_sent").fetchone()["c"], 0)
        cols = {row["name"] for row in db.execute("PRAGMA table_info(notices_sent)")}
        db.close()
        self.assertNotIn("email", cols)
        self.assertNotIn("name", cols)

        with_unknown = self._notify(
            audience="free_downloaded",
            below_version="0.9.41",
            include_unknown_version=True,
        )
        self.assertEqual(with_unknown.get_json()["matched"], 2)

        everyone = self._notify(audience="free_all", dry_run=True)
        self.assertEqual(everyone.get_json()["matched"], 4)

        pros = self._notify(audience="pro_active")
        self.assertEqual(pros.get_json()["matched"], 2)
        self.assertNotIn(inactive, (manual,))

        both = self._notify(audience="all")
        self.assertEqual(both.get_json()["matched"], 6)

        self._version("free", unknown, "0.9.39", table="telemetry_sessions")
        self._version("free", downloaded, "0.9.41", table="telemetry_sessions")
        newer = self._notify(audience="free_downloaded", below_version="0.9.41", include_unknown_version=True)
        self.assertEqual(newer.get_json()["matched"], 1)

    def test_send_dedupes_and_opt_out_and_hides_addresses(self):
        self._free("NC-MAIL-0001", "person@example.com", downloads=1)
        with self.assertLogs("notices", level="INFO") as logs:
            sent = self._notify(audience="free_downloaded", dry_run=False)
        self.assertEqual(sent.status_code, 200)
        body = sent.get_json()
        self.assertEqual(body["sent"], 1)
        self.assertEqual(body["failed"], 0)
        self.assertEqual(len(self.mail), 1)
        self.assertFalse(self.mail[0]["log_recipient"])
        self.assertEqual(self.mail[0]["subject"], "Please update Node Control Free to 0.9.41")
        self.assertIn("<ol>", self.mail[0]["html"])
        self.assertIn("<li>", self.mail[0]["html"])
        self.assertIn("unsubscribe", self.mail[0]["text"])
        self.assertNotIn("person@example.com", self.mail[0]["text"])
        self.assertNotIn("person@example.com", self.mail[0]["html"])
        self.assertNotIn("person@example.com", sent.get_data(as_text=True))
        self.assertNotIn("person@example.com", "\n".join(logs.output))
        self.assertNotIn("Person", sent.get_data(as_text=True))

        again = self._notify(audience="free_downloaded", dry_run=False)
        self.assertEqual(again.get_json()["already_sent"], 1)
        self.assertEqual(again.get_json()["sent"], 0)
        self.assertEqual(len(self.mail), 1)

        link = self.mail[0]["text"].split("open ", 1)[1].strip()
        token = link.split("t=", 1)[1]
        opted = self.client.get("/api/notices/unsubscribe?t=" + token)
        self.assertEqual(opted.status_code, 200)
        self.assertNotIn("@", opted.get_data(as_text=True))
        db = get_db()
        db.execute("DELETE FROM notices_sent")
        db.commit()
        db.close()
        after = self._notify(audience="free_downloaded", dry_run=False)
        self.assertEqual(after.get_json()["opted_out"], 1)
        self.assertEqual(after.get_json()["sent"], 0)
        self.assertEqual(len(self.mail), 1)

    def test_failed_send_is_a_count_and_is_not_logged_with_the_address(self):
        self._free("NC-FAIL-0001", "person@example.com", downloads=1)

        def boom(*_args, **_kwargs):
            raise RuntimeError("mailbox rejected person@example.com")

        self.mail_patch.stop()
        with patch.object(api, "_send_mail", side_effect=boom):
            with self.assertLogs("notices", level="ERROR") as logs:
                res = self._notify(audience="free_downloaded", dry_run=False)
        self.mail_patch.start()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["failed"], 1)
        self.assertEqual(res.get_json()["sent"], 0)
        self.assertNotIn("person@example.com", res.get_data(as_text=True))
        self.assertNotIn("person@example.com", "\n".join(logs.output))
        db = get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) AS c FROM notices_sent").fetchone()["c"], 0)
        db.close()

    def test_real_send_without_a_secret_sends_nothing(self):
        self._free("NC-NOSEC-001", "person@example.com", downloads=1)
        app.config["NOTICE_UNSUBSCRIBE_SECRET"] = ""
        res = self._notify(audience="free_downloaded", dry_run=False)
        self.assertEqual(res.status_code, 503)
        self.assertEqual(self.mail, [])
        self.assertNotIn("@", res.get_data(as_text=True))

    def test_cli_prints_counts_only(self):
        leaked = {
            "dry_run": True,
            "matched": 4,
            "already_sent": 1,
            "opted_out": 1,
            "sent": 0,
            "failed": 0,
            "email": "person@example.com",
            "name": "Person",
        }
        with patch("admin_cli.api", return_value=(200, leaked)) as called:
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                admin_cli.main([
                    "notify", "--template", "upgrade-0.9.41",
                    "--audience", "free_downloaded",
                    "--below-version", "0.9.41",
                    "--include-unknown-version",
                    "--dry-run",
                ])
        text = stdout.getvalue()
        self.assertEqual(
            text,
            "matched 4\nalready_sent 1\nopted_out 1\nsent 0\nfailed 0\n",
        )
        self.assertNotIn("example.com", text)
        body = called.call_args[0][2]
        self.assertTrue(body["dry_run"])
        self.assertEqual(body["below_version"], "0.9.41")
        self.assertTrue(body["include_unknown_version"])

        with patch("admin_cli.api", return_value=(200, dict(leaked, dry_run=False, sent=2))) as called:
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                admin_cli.main([
                    "notify", "--template", "upgrade-0.9.41",
                    "--audience", "free_all", "--confirm",
                ])
        self.assertIn("sent 2\n", stdout.getvalue())
        self.assertFalse(called.call_args[0][2]["dry_run"])
        self.assertNotIn("example.com", stdout.getvalue())

        with self.assertRaises(SystemExit) as missing:
            admin_cli.main(["notify", "--template", "upgrade-0.9.41", "--audience", "all"])
        self.assertEqual(missing.exception.code, 2)

    def _free_at(self, row_id, code, email, status="active", downloads=1):
        db = get_db()
        db.execute(
            """
            INSERT INTO licenses (
                id, code, name, email, company, platform, tier, status, created_at, download_count
            ) VALUES (?, ?, 'Person', ?, '', 'macos', 'free', ?, '2026-10-21T00:00:00', ?)
            """,
            (row_id, code, email, status, downloads),
        )
        db.commit()
        db.close()
        return row_id

    def test_licence_ids_narrow_audience_and_hide_the_ids(self):
        keep = self._free_at(22, "NC-KEEP-0022", "keep@example.com", downloads=1)
        self._free_at(25, "NC-SKIP-0025", "skip@example.com", downloads=1)
        self._free_at(30, "NC-NONE-0030", "none@example.com", downloads=0)
        self._free_at(31, "NC-PEND-0031", "pend@example.com", status="pending", downloads=3)
        self._version("free", keep, "0.9.40")
        self._version("free", 25, "0.9.41")

        with self.assertLogs("notices", level="INFO") as logs:
            narrowed = self._notify(licence_ids=[22, 25, 999001])
        self.assertEqual(narrowed.status_code, 200)
        body = narrowed.get_json()
        self.assertEqual(body["matched"], 2)
        self.assertEqual(body["not_matched"], 1)
        self.assertEqual(body["sent"], 0)
        self.assertTrue(body["dry_run"])
        text = narrowed.get_data(as_text=True)
        log_text = "\n".join(logs.output)
        for secret in ("keep@example.com", "skip@example.com", "NC-KEEP-0022", "999001", "22", "25"):
            self.assertNotIn(secret, text)
            self.assertNotIn(secret, log_text)
        self.assertIn("not_matched=1", log_text)
        self.assertEqual(self.mail, [])

        outside = self._notify(audience="free_downloaded", licence_ids=[30, 31])
        self.assertEqual(outside.get_json()["matched"], 0)
        self.assertEqual(outside.get_json()["not_matched"], 2)
        self.assertNotIn("none@example.com", outside.get_data(as_text=True))
        self.assertNotIn("30", outside.get_data(as_text=True))

        versioned = self._notify(
            audience="free_downloaded",
            licence_ids=[22, 25],
            below_version="0.9.41",
        )
        self.assertEqual(versioned.get_json()["matched"], 1)
        self.assertEqual(versioned.get_json()["not_matched"], 0)

        plain = self._notify(audience="free_downloaded")
        self.assertNotIn("not_matched", plain.get_json())

    def test_exclude_licence_ids_and_filters_still_apply(self):
        self._free_at(22, "NC-KEEP-0022", "keep@example.com", downloads=1)
        self._free_at(25, "NC-DROP-0025", "drop@example.com", downloads=1)
        self._free_at(40, "NC-ALSO-0040", "also@example.com", downloads=1)
        sent = self._notify(
            audience="free_all",
            exclude_licence_ids=[25, 999002],
            dry_run=False,
        )
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.get_json()["sent"], 2)
        self.assertEqual(sent.get_json()["not_matched"], 1)
        self.assertEqual({item["to"] for item in self.mail}, {"keep@example.com", "also@example.com"})
        self.assertNotIn("drop@example.com", sent.get_data(as_text=True))
        self.assertNotIn("999002", sent.get_data(as_text=True))
        self.assertNotIn("25", sent.get_data(as_text=True))

        both = self._notify(
            audience="free_all",
            licence_ids=[22, 25, 40, 999003],
            exclude_licence_ids=[25, 999004],
            dry_run=True,
        )
        self.assertEqual(both.get_json()["matched"], 2)
        self.assertEqual(both.get_json()["not_matched"], 2)
        self.assertNotIn("999003", both.get_data(as_text=True))
        self.assertNotIn("999004", both.get_data(as_text=True))

        again = self._notify(audience="free_all", licence_ids=[22], dry_run=False)
        self.assertEqual(again.get_json()["already_sent"], 1)
        self.assertEqual(again.get_json()["sent"], 0)
        self.assertEqual(again.get_json()["not_matched"], 0)
        self.assertEqual(len(self.mail), 2)

        self.mail.clear()
        db = get_db()
        db.execute("DELETE FROM notices_sent")
        db.execute(
            """
            INSERT INTO notice_opt_outs (licence_kind, licence_ref, opted_out_at)
            VALUES ('free', 40, '2026-10-21T00:00:00')
            """
        )
        db.commit()
        db.close()
        opted = self._notify(audience="free_all", licence_ids=[40], dry_run=False)
        self.assertEqual(opted.get_json()["opted_out"], 1)
        self.assertEqual(opted.get_json()["sent"], 0)
        self.assertEqual(self.mail, [])

    def test_pro_licence_id_uses_the_key_id(self):
        free_id = self._free_at(22, "NC-FREE-0022", "free@example.com", downloads=1)
        pro_id = self._pro_key("live@example.com")
        res = self._notify(audience="pro_active", licence_ids=[pro_id, free_id, 999005])
        body = res.get_json()
        if pro_id == free_id:
            self.assertEqual(body["matched"], 1)
            self.assertEqual(body["not_matched"], 1)
        else:
            self.assertEqual(body["matched"], 1)
            self.assertEqual(body["not_matched"], 2)
        self.assertNotIn("live@example.com", res.get_data(as_text=True))
        self.assertNotIn("free@example.com", res.get_data(as_text=True))
        self.assertEqual(
            set(body),
            {"dry_run", "matched", "already_sent", "opted_out", "sent", "failed", "not_matched"},
        )

    def test_bad_licence_ids_are_rejected_without_details(self):
        self._free_at(22, "NC-KEEP-0022", "keep@example.com", downloads=1)
        rejected = [
            {"licence_ids": "22"},
            {"licence_ids": ["22"]},
            {"licence_ids": [True]},
            {"licence_ids": [0]},
            {"licence_ids": [-3]},
            {"licence_ids": [1.5]},
            {"licence_ids": [22, {"id": 25}]},
            {"licence_ids": ["keep@example.com"]},
            {"exclude_licence_ids": "25"},
            {"exclude_licence_ids": [False]},
        ]
        for extra in rejected:
            res = self._notify(**extra)
            self.assertEqual(res.status_code, 400)
            text = res.get_data(as_text=True)
            self.assertNotIn("@", text)
            self.assertNotIn("keep@example.com", text)
            self.assertNotIn("NC-KEEP", text)
        self.assertEqual(self.mail, [])

    def test_cli_licence_id_flags_print_counts_only(self):
        leaked = {
            "dry_run": True,
            "matched": 1,
            "already_sent": 0,
            "opted_out": 0,
            "sent": 0,
            "failed": 0,
            "not_matched": 1,
            "email": "person@example.com",
            "name": "Person",
            "ids": [22, 25],
        }
        with patch("admin_cli.api", return_value=(200, leaked)) as called:
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                admin_cli.main([
                    "notify", "--template", "upgrade-0.9.41",
                    "--audience", "free_downloaded",
                    "--licence-id", "22,25",
                    "--licence-id", "30",
                    "--exclude-licence-id", "8",
                    "--exclude-licence-id", "9,8",
                    "--dry-run",
                ])
        text = stdout.getvalue()
        self.assertEqual(
            text,
            "matched 1\nalready_sent 0\nopted_out 0\nsent 0\nfailed 0\nnot_matched 1\n",
        )
        self.assertNotIn("example.com", text)
        self.assertNotIn("Person", text)
        body = called.call_args[0][2]
        self.assertEqual(body["licence_ids"], [22, 25, 30])
        self.assertEqual(body["exclude_licence_ids"], [8, 9])
        self.assertTrue(body["dry_run"])

        with patch("admin_cli.api", return_value=(200, leaked)) as called:
            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as bad:
                    admin_cli.main([
                        "notify", "--template", "upgrade-0.9.41",
                        "--audience", "free_all",
                        "--licence-id", "22,person@example.com",
                        "--dry-run",
                    ])
        self.assertEqual(bad.exception.code, 2)
        self.assertNotIn("@", stderr.getvalue())
        self.assertNotIn("example.com", stderr.getvalue())
        called.assert_not_called()


if __name__ == "__main__":
    unittest.main()
