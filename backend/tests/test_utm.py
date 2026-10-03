"""UTM persistence + carry-through across request-access and verify."""

from tests.conftest import fetch_row, get_verify_code_for


def _request_access(client, email, **extra):
    body = {
        "name": "Test User",
        "email": email,
        "platform": "macos",
        "company": "Acme",
    }
    body.update(extra)
    return client.post("/api/request-access", json=body)


def test_utm_persisted_on_request_access(api):
    r = _request_access(
        api.client,
        "utm1@example.com",
        utm_source="hacker-news",
        utm_medium="referral",
        utm_campaign="launch-week",
    )
    assert r.status_code == 200
    row = fetch_row(api.app_module, "utm1@example.com")
    assert row["utm_source"] == "hacker-news"
    assert row["utm_medium"] == "referral"
    assert row["utm_campaign"] == "launch-week"
    # issued_at is set at request-access moment
    assert row["issued_at"] == row["created_at"]


def test_utm_carried_through_verify_without_body_values(api):
    """When verify has no utm_*, values stored at request-access survive."""
    email = "utm2@example.com"
    _request_access(
        api.client, email,
        utm_source="google", utm_medium="cpc", utm_campaign="brand",
    )
    code = get_verify_code_for(api.app_module, email)

    r = api.client.post("/api/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.get_json()

    row = fetch_row(api.app_module, email)
    assert row["status"] == "active"
    assert row["utm_source"] == "google"
    assert row["utm_medium"] == "cpc"
    assert row["utm_campaign"] == "brand"


def test_verify_utm_overrides_when_provided(api):
    """A verify request that includes utm_* wins over what request-access stored.

    Covers the new-tab / click-through case where UTMs are re-captured on the
    landing that opens the verify step.
    """
    email = "utm3@example.com"
    _request_access(
        api.client, email,
        utm_source="google", utm_medium="cpc", utm_campaign="brand",
    )
    code = get_verify_code_for(api.app_module, email)

    r = api.client.post("/api/verify", json={
        "email": email, "code": code,
        "utm_source": "twitter", "utm_medium": "social", "utm_campaign": "relaunch",
    })
    assert r.status_code == 200

    row = fetch_row(api.app_module, email)
    assert row["utm_source"] == "twitter"
    assert row["utm_medium"] == "social"
    assert row["utm_campaign"] == "relaunch"


def test_utmless_resend_does_not_erase_captured_channel(api):
    """A second request-access without utm_* must not wipe the first one's UTMs."""
    email = "utm4@example.com"
    _request_access(
        api.client, email,
        utm_source="reddit", utm_medium="post", utm_campaign="ama",
    )
    _request_access(api.client, email)  # resend, no utm_*

    row = fetch_row(api.app_module, email)
    assert row["utm_source"] == "reddit"
    assert row["utm_medium"] == "post"
    assert row["utm_campaign"] == "ama"


def test_code_format_matches_desktop_join_key(api):
    """Code is uppercase NC-XXXX-XXXX so it joins with desktop telemetry."""
    email = "join@example.com"
    _request_access(api.client, email)
    code = get_verify_code_for(api.app_module, email)
    api.client.post("/api/verify", json={"email": email, "code": code})

    row = fetch_row(api.app_module, email)
    assert row["code"] == row["code"].upper()
    assert row["code"].startswith("NC-")
    parts = row["code"].split("-")
    assert len(parts) == 3 and len(parts[1]) == 4 and len(parts[2]) == 4
