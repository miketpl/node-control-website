"""14-day Pro trial. The signing key in tests/fixtures is test-only."""

import base64
import json
import logging
import os
import stat
import tempfile
import unittest
import uuid
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

import app as api
import licence_v1
import notices
import trial
from app import app, get_db

FIXTURE = Path(__file__).resolve().parent / "tests" / "fixtures" / "lease_signing_test_only.txt"


def _load_fixture():
    values = {}
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("TEST"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _decode(segment):
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.github = patch.object(api, "_github_request", return_value=(200, {}, b"{}"))
        self.github.start()
        self.mail = []
        self.mail_patch = patch.object(api, "_send_mail", side_effect=self._send)
        self.mail_patch.start()
        app.config["MIN_SUPPORTED_VERSION_FREE"] = "0.9.41"
        app.config["MIN_SUPPORTED_VERSION_PRO"] = "0.9.41"
        app.config["NOTICE_UNSUBSCRIBE_SECRET"] = "test-notice-secret"
        app.config["API_PUBLIC_URL"] = "https://api.nodecontrol.io"
        keys = _load_fixture()
        self.public = keys["public_key_b64"]
        os.environ["LEASE_SIGNING_KEY"] = keys["private_seed_b64"]
        os.environ["LEASE_SIGNING_KEY_ID"] = keys["key_id"]
        os.environ["LEASE_SIGNING_KEY_ID_NEXT"] = "test-only-k2"
        os.environ["MACHINE_HASH_KEY"] = "test-only-machine-hash-key"
        db = get_db()
        for table in ("licenses", "devices", "device_moves", "free_trials", "funnel_daily",
                      "notices_sent", "notice_opt_outs", "pro_keys", "server_flags",
                      "rate_limits"):
            db.execute(f"DELETE FROM {table}")
        db.commit()
        db.close()
        licence_v1.clear_flag_cache()
        licence_v1.set_flag("free_trial_enabled", "true")
        self.install = str(uuid.uuid4())
        self.machine = "ab" * 32

    def tearDown(self):
        self.github.stop()
        self.mail_patch.stop()
        licence_v1.clear_flag("free_trial_enabled")
        for name in (
            "LEASE_SIGNING_KEY", "LEASE_SIGNING_KEY_ID", "LEASE_SIGNING_KEY_ID_NEXT",
            "MACHINE_HASH_KEY",
        ):
            os.environ.pop(name, None)

    def _send(self, *args, **kwargs):
        self.mail.append(args)
        return True

    def _insert(self, code="NC-TRAL-0001", email="trial@example.com"):
        db = get_db()
        db.execute(
            """
            INSERT INTO licenses (code, name, email, company, platform, tier, status, created_at)
            VALUES (?, 'Person', ?, '', 'macos', 'free', 'active', '2026-01-01T00:00:00')
            """,
            (code, email),
        )
        db.commit()
        db.close()
        return code

    def _headers(self, key, install=None, version="0.9.46", machine=None):
        headers = {
            "Authorization": "Bearer " + key,
            "User-Agent": f"NodeControl/{version} (free; mac; arm64)",
            "X-NC-Install-Id": install or self.install,
        }
        if machine is not None:
            headers["X-NC-Machine-Hash"] = machine
        return headers

    def _activate(self, key, version="0.9.46", machine=None, install=None):
        return self.client.post(
            "/api/v1/app/activate",
            json={"tier": "free", "app_version": version, "platform": "mac", "arch": "arm64"},
            headers=self._headers(key, install, version, machine if machine is not None else self.machine),
        )

    def _open_lease(self, token):
        body_b64, sig_b64 = token.split(".")
        body = _decode(body_b64)
        Ed25519PublicKey.from_public_bytes(_decode(self.public)).verify(_decode(sig_b64), body)
        return json.loads(body)

    def test_new_licence_auto_starts_and_signs_a_capped_lease(self):
        code = self._insert()
        res = self._activate(code)
        self.assertEqual(res.status_code, 200)
        licence = res.get_json()["licence"]
        self.assertEqual(licence["tier"], "free")
        self.assertEqual(licence["lease_format"], "ed25519-v1")
        self.assertIn("devices_unlimited", licence["entitlements"])
        signed = self._open_lease(licence["lease"])
        self.assertEqual(signed["trial_state"], "active")
        self.assertEqual(signed["kid"], "test-only-k1")
        self.assertEqual(signed["min_supported_version"], "0.9.41")
        self.assertEqual(signed["machine_hash_echo"], self.machine)
        self.assertLessEqual(signed["lease_expires_at"], signed["trial"]["expires_at"])
        self.assertIn("test-only-k2", trial.current_and_next_kids())
        db = get_db()
        stored = db.execute("SELECT machine_hash, email_hash FROM free_trials").fetchone()
        counted = db.execute(
            "SELECT count FROM funnel_daily WHERE event = 'trial_started_auto'"
        ).fetchone()["count"]
        db.close()
        self.assertNotEqual(stored["machine_hash"], self.machine)
        self.assertEqual(len(stored["machine_hash"]), 64)
        self.assertEqual(counted, 1)

    def test_old_app_does_not_start_and_bad_hash_is_400(self):
        code = self._insert()
        old = self._activate(code, version="0.9.45")
        self.assertEqual(old.status_code, 200)
        self.assertEqual(old.get_json()["licence"]["trial"]["reason"], "old_app")
        self.assertIsNone(get_db().execute("SELECT id FROM free_trials").fetchone() or None)
        bad = self.client.post(
            "/api/v1/app/trial/start",
            json={"tier": "free", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers=self._headers(code, machine="not-a-hash"),
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.get_json()["error"]["code"], "bad_machine_hash")

    def test_existing_licence_is_opt_in_and_start_is_idempotent(self):
        code = self._insert()
        self._activate(code, version="0.9.41", machine=None)
        later = self.client.post(
            "/api/v1/app/licence/check",
            json={"tier": "free", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers=self._headers(code, machine=self.machine),
        )
        self.assertEqual(later.status_code, 200)
        trial_body = later.get_json()["trial"]
        self.assertFalse(trial_body["active"])
        self.assertTrue(trial_body["eligible"])
        first = self.client.post(
            "/api/v1/app/trial/start",
            json={"tier": "free", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers=self._headers(code, machine=self.machine),
        )
        self.assertEqual(first.status_code, 200)
        started = first.get_json()["licence"]["trial"]["started_at"]
        second = self.client.post(
            "/api/v1/app/trial/start",
            json={"tier": "free", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers=self._headers(code, machine=self.machine),
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["licence"]["trial"]["started_at"], started)
        db = get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) AS c FROM free_trials").fetchone()["c"], 1)
        db.close()

    def test_one_trial_per_email_and_per_machine(self):
        first = self._insert("NC-TRAL-0001", "one@example.com")
        self._activate(first)
        other = self._insert("NC-TRAL-0002", "two@example.com")
        used = self._activate(other)
        self.assertEqual(used.get_json()["licence"]["trial"]["reason"], "machine_used")
        same = self._insert("NC-TRAL-0003", "one@example.com")
        install = str(uuid.uuid4())
        refused = self._activate(same, machine="cd" * 32, install=install)
        self.assertEqual(refused.get_json()["licence"]["trial"]["reason"], "email_used")
        again = self.client.post(
            "/api/v1/app/trial/start",
            json={"tier": "free", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers=self._headers(same, install=install, machine="cd" * 32),
        )
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.get_json()["error"]["code"], "trial_used")
        self.assertEqual(again.get_json()["error"]["details"]["reason"], "email_used")

    def test_unavailable_machine_id_uses_the_email_only(self):
        code = self._insert()
        res = self._activate(code, machine="unavailable")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["licence"]["trial"]["active"])
        db = get_db()
        self.assertEqual(db.execute("SELECT machine_hash FROM free_trials").fetchone()["machine_hash"], "")
        db.close()

    def test_flag_off_blocks_auto_start_and_the_button(self):
        licence_v1.set_flag("free_trial_enabled", "false")
        code = self._insert()
        res = self._activate(code)
        self.assertEqual(res.get_json()["licence"]["trial"]["reason"], "disabled")
        started = self.client.post(
            "/api/v1/app/trial/start",
            json={"tier": "free", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers=self._headers(code),
        )
        self.assertEqual(started.status_code, 409)
        self.assertEqual(started.get_json()["error"]["code"], "trial_unavailable")
        self.assertEqual(started.get_json()["error"]["details"]["reason"], "disabled")

    def test_revoked_and_test_key_return_no_lease(self):
        code = self._insert("NC-REV1-REV1")
        db = get_db()
        db.execute("UPDATE licenses SET status = 'revoked' WHERE code = ?", (code,))
        db.commit()
        db.close()
        revoked = self._activate(code)
        self.assertEqual(revoked.status_code, 403)
        self.assertNotIn("lease", revoked.get_json())
        plain = licence_v1.generate_pro_key()
        now = licence_v1.iso(licence_v1.utcnow())
        db = get_db()
        db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, email, source, status, plan, created_at, is_test
            ) VALUES (?, ?, 'pro@example.com', 'manual', 'active', 'monthly', ?, 1)
            """,
            (licence_v1.hash_key(plain), plain[-4:], now),
        )
        db.commit()
        db.close()
        app.config["STRIPE_ALLOW_TEST_EVENTS"] = ""
        tested = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "pro", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers={
                "Authorization": "Bearer " + plain,
                "User-Agent": "NodeControl/0.9.46 (pro; mac; arm64)",
                "X-NC-Install-Id": str(uuid.uuid4()),
                "X-NC-Machine-Hash": self.machine,
            },
        )
        self.assertEqual(tested.status_code, 403)
        self.assertEqual(tested.get_json()["error"]["code"], "test_key")
        self.assertNotIn("lease", json.dumps(tested.get_json()))
        app.config["STRIPE_ALLOW_TEST_EVENTS"] = "1"
        allowed = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "pro", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers={
                "Authorization": "Bearer " + plain,
                "User-Agent": "NodeControl/0.9.46 (pro; mac; arm64)",
                "X-NC-Install-Id": str(uuid.uuid4()),
                "X-NC-Machine-Hash": self.machine,
            },
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.get_json()["licence"]["lease_format"], "ed25519-v1")
        app.config["STRIPE_ALLOW_TEST_EVENTS"] = ""

    def test_reset_is_dry_run_until_confirm_and_reminders_ignore_opt_out(self):
        code = self._insert()
        self._activate(code)
        db = get_db()
        trial_id = db.execute("SELECT id FROM free_trials").fetchone()["id"]
        started = licence_v1.utcnow() - timedelta(days=10)
        db.execute("UPDATE free_trials SET started_at = ? WHERE id = ?", (licence_v1.iso(started), trial_id))
        db.execute(
            "INSERT INTO notice_opt_outs (licence_kind, licence_ref, opted_out_at) VALUES ('free', 1, '2026-01-01T00:00:00')"
        )
        db.commit()
        ref = db.execute("SELECT licence_ref FROM free_trials").fetchone()["licence_ref"]
        db.execute("DELETE FROM notice_opt_outs")
        db.execute(
            "INSERT INTO notice_opt_outs (licence_kind, licence_ref, opted_out_at) VALUES ('free', ?, '2026-01-01T00:00:00')",
            (ref,),
        )
        db.commit()
        db.close()
        out = StringIO()
        with patch("sys.stdout", out):
            self.assertEqual(trial.reset_trial(trial_id, False), 0)
        self.assertIn("would delete", out.getvalue())
        self.assertIsNotNone(get_db().execute("SELECT id FROM free_trials").fetchone())
        out = StringIO()
        with patch("sys.stdout", out):
            trial.run_reminders(False)
        self.assertIn("matched 1", out.getvalue())
        self.assertEqual(self.mail, [])
        self.assertIsNone(notices._load_template("trial-0.9.46") and None)
        self.assertIsNotNone(notices._load_template("trial-0.9.46"))
        self.assertTrue(trial._template_opt_out("trial-0.9.46"))
        self.assertFalse(trial._template_opt_out("trial-day11"))
        with patch("sys.stdout", StringIO()):
            trial.reset_trial(trial_id, True)
        self.assertIsNone(get_db().execute("SELECT id FROM free_trials").fetchone())

    def test_pro_key_is_not_a_trial_and_signs_all_entitlements(self):
        plain = licence_v1.generate_pro_key()
        now = licence_v1.iso(licence_v1.utcnow())
        db = get_db()
        db.execute(
            """
            INSERT INTO pro_keys (
                key_hash, key_last4, email, source, status, plan, created_at, is_test
            ) VALUES (?, ?, 'pro@example.com', 'manual', 'active', 'monthly', ?, 0)
            """,
            (licence_v1.hash_key(plain), plain[-4:], now),
        )
        db.commit()
        db.close()
        res = self.client.post(
            "/api/v1/app/activate",
            json={"tier": "pro", "app_version": "0.9.46", "platform": "mac", "arch": "arm64"},
            headers={
                "Authorization": "Bearer " + plain,
                "User-Agent": "NodeControl/0.9.46 (pro; mac; arm64)",
                "X-NC-Install-Id": str(uuid.uuid4()),
                "X-NC-Machine-Hash": self.machine,
            },
        )
        self.assertEqual(res.status_code, 200)
        licence = res.get_json()["licence"]
        self.assertEqual(licence["tier"], "pro")
        self.assertIsNone(licence["trial"])
        self.assertEqual(licence["entitlements"], ["all"])
        signed = self._open_lease(licence["lease"])
        self.assertEqual(signed["trial_state"], "not_applicable")
        self.assertEqual(signed["edition"], "pro")
        db = get_db()
        self.assertIsNone(db.execute("SELECT id FROM free_trials").fetchone())
        db.close()

    def _keygen(self, path, next_key=False, overwrite=False):
        stdout, stderr, logged = StringIO(), StringIO(), StringIO()
        handler = logging.StreamHandler(logged)
        root = logging.getLogger()
        previous = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
        try:
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = trial.keygen(path, next_key=next_key, overwrite=overwrite)
        finally:
            root.removeHandler(handler)
            root.setLevel(previous)
        return code, stdout.getvalue(), stderr.getvalue(), logged.getvalue()

    def _seed_forms(self, seed):
        standard = base64.b64encode(seed).decode("ascii")
        url = base64.urlsafe_b64encode(seed).decode("ascii")
        return {standard, standard.rstrip("="), url, url.rstrip("="), seed.hex()}

    def _assert_secret_hidden(self, captured, seed):
        for form in self._seed_forms(seed):
            self.assertNotIn(form, captured)

    def _read_env_value(self, path, name):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            parsed = trial._assignment(line)
            if parsed and parsed[0] == name:
                return parsed[1]
        return None

    def test_keygen_creates_mode_600_and_hides_the_private_key(self):
        folder = tempfile.mkdtemp(prefix="nc-lease-")
        path = os.path.join(folder, ".env")
        code, out, err, logged = self._keygen(path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        seed = base64.b64decode(self._read_env_value(path, "LEASE_SIGNING_KEY"))
        self.assertEqual(len(seed), 32)
        captured = out + err + logged
        self._assert_secret_hidden(captured, seed)
        self.assertIn("key_id=", out)
        self.assertIn("public_key=", out)
        self.assertIn("env_file=" + os.path.abspath(path), out)
        self.assertNotIn("PRIVATE", out.upper())

    def test_keygen_keeps_other_lines_and_tightens_the_mode(self):
        folder = tempfile.mkdtemp(prefix="nc-lease-")
        path = os.path.join(folder, ".env")
        original = "SMTP_FROM_NAME=Node Control\n# LEASE_SIGNING_KEY=do-not-touch\nEMPTY=\n"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(original)
        os.chmod(path, 0o644)
        code, out, err, logged = self._keygen(path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        text = Path(path).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(original))
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        seed = base64.b64decode(self._read_env_value(path, "LEASE_SIGNING_KEY"))
        self._assert_secret_hidden(out + err + logged, seed)

    def test_keygen_refuses_a_set_key_unless_overwrite(self):
        import admin_cli
        folder = tempfile.mkdtemp(prefix="nc-lease-")
        path = os.path.join(folder, ".env")
        original = "SMTP_FROM_NAME=Node Control\nLEASE_SIGNING_KEY=already-set\n"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(original)
        os.chmod(path, 0o644)
        before = Path(path).read_bytes()
        code, out, err, logged = self._keygen(path)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("already set", err)
        self.assertNotIn("already-set", err)
        self.assertNotIn("already-set", logged)
        self.assertEqual(Path(path).read_bytes(), before)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644)
        with patch("sys.stdout", StringIO()), patch("sys.stderr", StringIO()):
            with self.assertRaises(SystemExit) as caught:
                admin_cli.main(["lease-keygen", "--env-file", path])
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(Path(path).read_bytes(), before)
        code, out, err, logged = self._keygen(path, overwrite=True)
        self.assertEqual(code, 0)
        text = Path(path).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("SMTP_FROM_NAME=Node Control\n"))
        self.assertNotIn("already-set", text)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        seed = base64.b64decode(self._read_env_value(path, "LEASE_SIGNING_KEY"))
        self._assert_secret_hidden(out + err + logged, seed)

    def test_keygen_next_writes_the_next_variables(self):
        folder = tempfile.mkdtemp(prefix="nc-lease-")
        path = os.path.join(folder, ".env")
        original = "LEASE_SIGNING_KEY=current-seed\nLEASE_SIGNING_KEY_ID=kcurrent\n"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(original)
        code, out, err, logged = self._keygen(path, next_key=True)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        text = Path(path).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(original))
        self.assertEqual(self._read_env_value(path, "LEASE_SIGNING_KEY"), "current-seed")
        self.assertEqual(self._read_env_value(path, "LEASE_SIGNING_KEY_ID"), "kcurrent")
        seed = base64.b64decode(self._read_env_value(path, "LEASE_SIGNING_KEY_NEXT"))
        self.assertEqual(len(seed), 32)
        self.assertTrue(self._read_env_value(path, "LEASE_SIGNING_KEY_ID_NEXT").startswith("k"))
        self._assert_secret_hidden(out + err + logged, seed)

    def test_keygen_seed_signs_a_lease_the_printed_key_verifies(self):
        from dotenv import dotenv_values
        folder = tempfile.mkdtemp(prefix="nc-lease-")
        path = os.path.join(folder, ".env")
        code, out, err, logged = self._keygen(path)
        self.assertEqual(code, 0)
        loaded = dotenv_values(path)
        seed = base64.b64decode(loaded["LEASE_SIGNING_KEY"])
        self._assert_secret_hidden(out + err + logged, seed)
        fields = {}
        for line in out.splitlines():
            if "=" in line:
                name, value = line.split("=", 1)
                fields[name] = value
        self.assertEqual(loaded["LEASE_SIGNING_KEY_ID"], fields["key_id"])
        os.environ["LEASE_SIGNING_KEY"] = loaded["LEASE_SIGNING_KEY"]
        os.environ["LEASE_SIGNING_KEY_ID"] = loaded["LEASE_SIGNING_KEY_ID"]
        lease_format, token = trial._sign({"v": 1, "hello": "lease"})
        self.assertEqual(lease_format, "ed25519-v1")
        body_b64, sig_b64 = token.split(".")
        body = _decode(body_b64)
        Ed25519PublicKey.from_public_bytes(_decode(fields["public_key"])).verify(
            _decode(sig_b64), body
        )
        derived = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
        self.assertEqual(base64.urlsafe_b64encode(derived).decode("ascii").rstrip("="), fields["public_key"])


if __name__ == "__main__":
    unittest.main()
