"""Verify path is atomic: a failed GitHub write must NOT hand out a code."""

from tests.conftest import fetch_row, get_verify_code_for


def _request(client, email):
    return client.post("/api/request-access", json={
        "name": "Test", "email": email, "platform": "macos",
    })


def test_verify_fails_when_github_sync_fails(api):
    email = "sync-fail@example.com"
    _request(api.client, email)
    code = get_verify_code_for(api.app_module, email)

    api.github_state["fail_add"] = True
    r = api.client.post("/api/verify", json={"email": email, "code": code})

    assert r.status_code == 503
    body = r.get_json()
    assert "download_code" not in body

    # Row still pending, so the user can retry verify without re-doing step 1.
    row = fetch_row(api.app_module, email)
    assert row["status"] == "pending"
    # No code should have been recorded as pushed.
    assert api.github_state["added"] == []


def test_verify_succeeds_and_pushes_when_sync_ok(api):
    email = "sync-ok@example.com"
    _request(api.client, email)
    code = get_verify_code_for(api.app_module, email)

    r = api.client.post("/api/verify", json={"email": email, "code": code})
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["download_code"].startswith("NC-")
    assert api.github_state["added"] == [body["download_code"]]

    row = fetch_row(api.app_module, email)
    assert row["status"] == "active"


def test_retry_verify_after_transient_sync_failure(api):
    """After a transient sync failure, retrying verify with the same code works."""
    email = "retry@example.com"
    _request(api.client, email)
    code = get_verify_code_for(api.app_module, email)

    api.github_state["fail_add"] = True
    r1 = api.client.post("/api/verify", json={"email": email, "code": code})
    assert r1.status_code == 503

    api.github_state["fail_add"] = False
    r2 = api.client.post("/api/verify", json={"email": email, "code": code})
    assert r2.status_code == 200
    assert r2.get_json()["download_code"].startswith("NC-")
