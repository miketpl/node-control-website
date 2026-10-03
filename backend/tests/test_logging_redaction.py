"""Emails and codes must never appear in INFO-level logs (or higher)."""

import logging

from tests.conftest import get_verify_code_for


def test_no_email_or_code_at_info_or_above(api, caplog):
    email = "logtest@example.com"

    caplog.set_level(logging.INFO, logger="app")
    api.client.post("/api/request-access", json={
        "name": "Test", "email": email, "platform": "macos",
    })
    code = get_verify_code_for(api.app_module, email)
    r = api.client.post("/api/verify", json={"email": email, "code": code})
    assert r.status_code == 200
    download_code = r.get_json()["download_code"]

    api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": email},
        headers=api.admin_headers,
    )

    for record in caplog.records:
        if record.levelno < logging.INFO:
            continue
        msg = record.getMessage()
        assert email not in msg, f"email leaked at {record.levelname}: {msg}"
        assert download_code not in msg, f"code leaked at {record.levelname}: {msg}"
        assert code not in msg, f"verify code leaked at {record.levelname}: {msg}"
