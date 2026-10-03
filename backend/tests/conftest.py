"""Shared fixtures for the NodeControl license API tests.

Each test gets a fresh SQLite DB and a Flask test client that skips SMTP
(the app already handles missing SMTP config by no-op-ing send_verification_email)
and stubs out the GitHub sync helpers so we never hit the network.
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Make backend/ importable when running `pytest` from anywhere.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Fresh app instance with an isolated DB and stubbed GitHub sync.

    Yields a namespace with:
        client         — Flask test client
        app_module     — the reloaded app module (so tests can patch helpers)
        admin_headers  — dict with a valid Authorization header
        github_state   — dict tracking sync helper calls
    """
    db_path = tmp_path / "test-licenses.db"
    admin_token = "test-admin-token"

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("ADMIN_TOKEN", admin_token)
    monkeypatch.setenv("SECRET_KEY", "test")
    # Blank SMTP creds → send_verification_email no-ops.
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASS", "")
    # PATs must be present so the sync helpers proceed past the early-return.
    monkeypatch.setenv("GITHUB_PAT", "test-pat")
    monkeypatch.setenv("GITHUB_PAT_WRITE", "test-pat-write")

    # Ensure a fresh import that re-reads env and re-inits the DB.
    if "app" in sys.modules:
        del sys.modules["app"]
    app_module = importlib.import_module("app")

    github_state = {"added": [], "removed": [], "fail_add": False, "fail_remove": False}

    def fake_add(code):
        if github_state["fail_add"]:
            raise RuntimeError("simulated GitHub add failure")
        github_state["added"].append(code)

    def fake_remove_many(codes):
        codes = [c for c in codes if c]
        if github_state["fail_remove"]:
            raise RuntimeError("simulated GitHub remove failure")
        github_state["removed"].extend(codes)
        return len(codes)

    with patch.object(app_module, "_add_code_to_licenses", side_effect=fake_add), \
         patch.object(app_module, "_remove_codes_from_licenses", side_effect=fake_remove_many):
        client = app_module.app.test_client()

        class Ns:
            pass
        ns = Ns()
        ns.client = client
        ns.app_module = app_module
        ns.admin_headers = {"Authorization": f"Bearer {admin_token}"}
        ns.github_state = github_state
        yield ns


def get_verify_code_for(app_module, email):
    """Read the 6-digit verify code the app stashed in verified_at."""
    db = app_module.get_db()
    row = db.execute(
        "SELECT verified_at FROM licenses WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,),
    ).fetchone()
    db.close()
    stored = row["verified_at"] or ""
    assert stored.startswith("PENDING:"), f"unexpected verified_at: {stored!r}"
    return stored.replace("PENDING:", "")


def fetch_row(app_module, email):
    db = app_module.get_db()
    row = db.execute(
        "SELECT * FROM licenses WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,),
    ).fetchone()
    db.close()
    return row
