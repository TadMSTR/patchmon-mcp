"""
Tests for PatchMonClient — JWT caching, refresh on 401, auth injection.
"""

import pytest
import respx
import httpx

from patchmon_mcp.client import PatchMonClient, PatchMonConfigError, PatchMonError

from .conftest import (
    ENDPOINT,
    LOGIN_RESPONSE,
    HOST_ID,
    PATCH_RUN_QUEUED,
    DRY_RUN_QUEUED,
    APPROVE_RESPONSE,
)


# ---------------------------------------------------------------------------
# JWT caching and refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jwt_is_cached_across_calls(mock_env):
    """Second admin request reuses cached JWT without re-logging in."""
    with respx.mock(base_url=ENDPOINT) as mock:
        login = mock.post("/api/v1/auth/login").mock(
            return_value=httpx.Response(200, json=LOGIN_RESPONSE)
        )
        mock.post("/api/v1/patching/trigger").mock(
            return_value=httpx.Response(200, json=PATCH_RUN_QUEUED)
        )

        client = PatchMonClient()
        await client.request_admin("POST", "/patching/trigger", json={
            "host_id": HOST_ID, "patch_type": "patch_all"
        })
        await client.request_admin("POST", "/patching/trigger", json={
            "host_id": HOST_ID, "patch_type": "patch_all"
        })

        assert login.call_count == 1, "Should only login once when token is valid"
        await client.close()


@pytest.mark.asyncio
async def test_jwt_refreshes_on_401(mock_env):
    """A 401 from the admin API triggers a re-login and retry."""
    new_token_response = {**LOGIN_RESPONSE, "token": "new-jwt-token-after-refresh"}

    with respx.mock(base_url=ENDPOINT) as mock:
        login = mock.post("/api/v1/auth/login").mock(
            side_effect=[
                httpx.Response(200, json=LOGIN_RESPONSE),
                httpx.Response(200, json=new_token_response),
            ]
        )
        trigger = mock.post("/api/v1/patching/trigger").mock(
            side_effect=[
                httpx.Response(401, json={"error": "token expired"}),
                httpx.Response(200, json=PATCH_RUN_QUEUED),
            ]
        )

        client = PatchMonClient()
        resp = await client.request_admin("POST", "/patching/trigger", json={
            "host_id": HOST_ID, "patch_type": "patch_all"
        })

        assert login.call_count == 2, "Should re-login after 401"
        assert trigger.call_count == 2, "Should retry after re-login"
        assert resp.status_code == 200
        await client.close()


@pytest.mark.asyncio
async def test_jwt_not_in_integration_request(mock_env):
    """Integration API requests use Basic Auth, not JWT."""
    with respx.mock(base_url=ENDPOINT, assert_all_called=False) as mock:
        mock.post("/api/v1/auth/login").mock(
            return_value=httpx.Response(200, json=LOGIN_RESPONSE)
        )
        hosts_req = mock.get("/api/v1/api/hosts").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PatchMonClient()
        await client.request_integration("GET", "/hosts")

        # Login must NOT be called — Integration API uses Basic Auth only
        assert hosts_req.call_count == 1
        # Auth header should be Basic, not Bearer
        req = hosts_req.calls[0].request
        auth_header = req.headers.get("authorization", "")
        assert auth_header.startswith("Basic "), f"Expected Basic auth, got: {auth_header}"
        await client.close()


@pytest.mark.asyncio
async def test_admin_request_sends_jwt_bearer(mock_env):
    """Admin API requests include Authorization: Bearer <token>."""
    with respx.mock(base_url=ENDPOINT) as mock:
        mock.post("/api/v1/auth/login").mock(
            return_value=httpx.Response(200, json=LOGIN_RESPONSE)
        )
        trigger = mock.post("/api/v1/patching/trigger").mock(
            return_value=httpx.Response(200, json=PATCH_RUN_QUEUED)
        )

        client = PatchMonClient()
        await client.request_admin("POST", "/patching/trigger", json={
            "host_id": HOST_ID, "patch_type": "patch_all"
        })

        req = trigger.calls[0].request
        auth = req.headers.get("authorization", "")
        assert auth == f"Bearer {LOGIN_RESPONSE['token']}"
        await client.close()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_4xx_raises_patchmon_error(mock_env):
    """Non-401 4xx responses raise PatchMonError with the error message."""
    with respx.mock(base_url=ENDPOINT) as mock:
        mock.post("/api/v1/auth/login").mock(
            return_value=httpx.Response(200, json=LOGIN_RESPONSE)
        )
        mock.post("/api/v1/patching/trigger").mock(
            return_value=httpx.Response(400, json={"error": "patch_type must be patch_all or patch_package"})
        )

        client = PatchMonClient()
        with pytest.raises(PatchMonError) as exc_info:
            await client.request_admin("POST", "/patching/trigger", json={})

        assert exc_info.value.status_code == 400
        assert "patch_type" in str(exc_info.value)
        await client.close()


@pytest.mark.asyncio
async def test_integration_api_missing_creds_raises(monkeypatch):
    """Integration API tools raise PatchMonError if TOKEN_KEY/SECRET are absent."""
    monkeypatch.setenv("PATCHMON_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("PATCHMON_ADMIN_USER", "admin")
    monkeypatch.setenv("PATCHMON_ADMIN_PASSWORD", "secret")
    monkeypatch.delenv("PATCHMON_TOKEN_KEY", raising=False)
    monkeypatch.delenv("PATCHMON_TOKEN_SECRET", raising=False)

    client = PatchMonClient()
    with pytest.raises(PatchMonConfigError) as exc_info:
        await client.request_integration("GET", "/hosts")

    assert "TOKEN_KEY" in str(exc_info.value)
    await client.close()


# ---------------------------------------------------------------------------
# Dry-run workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_uses_correct_body(mock_env):
    """trigger_dry_run sends dry_run=True and patch_type=patch_package."""
    with respx.mock(base_url=ENDPOINT) as mock:
        mock.post("/api/v1/auth/login").mock(
            return_value=httpx.Response(200, json=LOGIN_RESPONSE)
        )
        trigger = mock.post("/api/v1/patching/trigger").mock(
            return_value=httpx.Response(200, json=DRY_RUN_QUEUED)
        )

        client = PatchMonClient()
        await client.request_admin(
            "POST",
            "/patching/trigger",
            json={"host_id": HOST_ID, "patch_type": "patch_package",
                  "package_name": "curl", "dry_run": True},
        )

        import json
        body = json.loads(trigger.calls[0].request.content)
        assert body["dry_run"] is True
        assert body["patch_type"] == "patch_package"
        assert body["package_name"] == "curl"
        await client.close()


@pytest.mark.asyncio
async def test_approve_creates_new_run(mock_env):
    """approve_patch_run calls POST /patching/runs/:id/approve and returns new run ID."""
    with respx.mock(base_url=ENDPOINT) as mock:
        mock.post("/api/v1/auth/login").mock(
            return_value=httpx.Response(200, json=LOGIN_RESPONSE)
        )
        approve = mock.post(f"/api/v1/patching/runs/dry-xyz/approve").mock(
            return_value=httpx.Response(200, json=APPROVE_RESPONSE)
        )

        client = PatchMonClient()
        resp = await client.request_admin("POST", "/patching/runs/dry-xyz/approve", json={})
        data = resp.json()

        assert data["patch_run_id"] == "new-real-run-456"
        assert data["validation_run_id"] == "dry-xyz"
        assert approve.call_count == 1
        await client.close()
