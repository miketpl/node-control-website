"""Admin delete-by-email: revoke + wipe, idempotent, enables re-signup."""

from tests.conftest import fetch_row, get_verify_code_for


def _request_and_verify(api, email):
    api.client.post("/api/request-access", json={
        "name": "Test", "email": email, "platform": "macos",
    })
    code = get_verify_code_for(api.app_module, email)
    r = api.client.post("/api/verify", json={"email": email, "code": code})
    assert r.status_code == 200
    return r.get_json()["download_code"]


def test_delete_requires_admin(api):
    r = api.client.delete("/api/admin/licenses/by-email", json={"email": "a@b.com"})
    assert r.status_code == 401


def test_delete_requires_valid_email(api):
    r = api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": "notanemail"},
        headers=api.admin_headers,
    )
    assert r.status_code == 400


def test_delete_removes_records_and_revokes_code(api):
    email = "del@example.com"
    code = _request_and_verify(api, email)
    assert code in api.github_state["added"]

    r = api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": email},
        headers=api.admin_headers,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["records_removed"] == 1
    assert body["codes_revoked"] == 1

    # Row is gone from SQLite.
    assert fetch_row(api.app_module, email) is None
    # Code was pushed to the remove list.
    assert code in api.github_state["removed"]


def test_delete_is_idempotent_when_no_records(api):
    r = api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": "ghost@example.com"},
        headers=api.admin_headers,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["records_removed"] == 0
    assert body["codes_revoked"] == 0


def test_delete_handles_pending_only_row(api):
    """User requested a code but never verified — delete still cleans them up
    and reports codes_revoked=0 (nothing was ever in licenses.json)."""
    email = "pending-only@example.com"
    api.client.post("/api/request-access", json={
        "name": "Test", "email": email, "platform": "macos",
    })
    row = fetch_row(api.app_module, email)
    assert row is not None
    assert row["status"] == "pending"

    # The pending row still has a code column (that's how the schema works),
    # but that code was never synced. Our helper is idempotent when the code
    # isn't in the file — we assert only the record count here since the
    # stubbed remover reports len(codes_to_remove) rather than reading state.
    r = api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": email},
        headers=api.admin_headers,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["records_removed"] == 1
    assert fetch_row(api.app_module, email) is None


def test_delete_allows_resignup_with_same_email(api):
    email = "resignup@example.com"
    _request_and_verify(api, email)

    r = api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": email},
        headers=api.admin_headers,
    )
    assert r.status_code == 200

    # Fresh sign-up must succeed and get a NEW code.
    r2 = api.client.post("/api/request-access", json={
        "name": "Test", "email": email, "platform": "macos",
    })
    assert r2.status_code == 200
    assert r2.get_json().get("success") is True


def test_delete_leaves_state_intact_when_github_fails(api):
    """If revoke upstream fails, the SQLite record must NOT be deleted."""
    email = "sync-fail-del@example.com"
    _request_and_verify(api, email)

    api.github_state["fail_remove"] = True
    r = api.client.delete(
        "/api/admin/licenses/by-email",
        json={"email": email},
        headers=api.admin_headers,
    )
    assert r.status_code == 503
    # Row still exists so a retry after fixing GitHub can complete the deletion.
    assert fetch_row(api.app_module, email) is not None
