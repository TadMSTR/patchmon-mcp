"""Test fixtures for patchmon-mcp."""

import pytest
import respx
import httpx


ENDPOINT = "http://localhost:3005"

LOGIN_RESPONSE = {
    "token": "test-jwt-token-abc123",
    "refresh_token": "test-refresh-token",
    "expires_at": "2099-12-31T23:59:59Z",
    "expires_in": 3600,
    "message": "Login successful",
    "user": {"id": "user-1", "username": "admin"},
}

HOST_ID = "a5c9a0a2-189f-452e-b73c-08c0c6ebb363"

PATCH_RUN_QUEUED = {
    "job_id": "patch-run-abc123",
    "message": "Patch queued",
    "patch_run_id": "abc123",
    "queued": True,
    "run_at": "2026-05-25T12:00:00Z",
}

PATCH_RUN_DETAIL = {
    "id": "abc123",
    "job_id": "patch-run-abc123",
    "host_id": HOST_ID,
    "status": "completed",
    "dry_run": False,
    "patch_type": "patch_all",
    "package_name": None,
    "packages_affected": ["curl", "libssl3"],
    "shell_output": "$ apt-get upgrade -y\ncurl upgraded.\n",
    "error_message": None,
    "created_at": "2026-05-25T12:00:00Z",
    "started_at": "2026-05-25T12:00:01Z",
    "completed_at": "2026-05-25T12:00:10Z",
    "approved_by_username": None,
    "triggered_by_username": "admin",
    "validation_run_id": None,
}

DRY_RUN_QUEUED = {
    "job_id": "patch-run-dry-xyz",
    "message": "Dry run queued",
    "patch_run_id": "dry-xyz",
    "queued": True,
    "run_at": "2026-05-25T12:00:00Z",
}

DRY_RUN_DETAIL = {
    "id": "dry-xyz",
    "job_id": "patch-run-dry-xyz",
    "host_id": HOST_ID,
    "status": "validated",
    "dry_run": True,
    "patch_type": "patch_package",
    "package_name": "curl",
    "packages_affected": None,
    "shell_output": "$ apt-get -s install curl\ncurl is already the newest version.\n",
    "error_message": None,
    "created_at": "2026-05-25T12:00:00Z",
    "started_at": "2026-05-25T12:00:01Z",
    "completed_at": "2026-05-25T12:00:03Z",
    "approved_by_username": None,
    "triggered_by_username": "admin",
    "validation_run_id": None,
}

APPROVE_RESPONSE = {
    "message": "Approved - new patch run created",
    "patch_run_id": "new-real-run-456",
    "run_at": "2026-05-25T12:01:00Z",
    "validation_run_id": "dry-xyz",
}


@pytest.fixture(autouse=True)
def reset_client_singleton():
    """Reset the module-level client singleton between tests."""
    import patchmon_mcp.client as client_module
    client_module._client = None
    yield
    client_module._client = None


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("PATCHMON_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("PATCHMON_ADMIN_USER", "admin")
    monkeypatch.setenv("PATCHMON_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("PATCHMON_TOKEN_KEY", "patchmon_ae_testkey")
    monkeypatch.setenv("PATCHMON_TOKEN_SECRET", "testsecret")
