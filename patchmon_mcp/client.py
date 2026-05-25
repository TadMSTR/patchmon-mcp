"""
PatchMon HTTP client — dual-auth.

Integration API (/api/v1/api/*): HTTP Basic Auth with TOKEN_KEY:TOKEN_SECRET.
Admin API (/api/v1/*):           JWT from POST /api/v1/auth/login, cached in-process.
JWT is refreshed automatically on 401 or when approaching expiry.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger(__name__)


class PatchMonError(Exception):
    """Raised when PatchMon returns an error response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"PatchMon error {status_code}: {message}")


class PatchMonConfigError(Exception):
    """Raised for missing or invalid configuration (not an HTTP error)."""


class PatchMonClient:
    """
    Async HTTP client for PatchMon.

    A single instance should be reused for the lifetime of the MCP server
    so the JWT cache and httpx connection pool are shared across tool calls.
    """

    def __init__(self) -> None:
        endpoint = os.environ.get("PATCHMON_ENDPOINT", "").rstrip("/")
        if not endpoint:
            raise RuntimeError("PATCHMON_ENDPOINT is required")

        self._admin_user = os.environ.get("PATCHMON_ADMIN_USER", "")
        self._admin_password = os.environ.get("PATCHMON_ADMIN_PASSWORD", "")
        if not self._admin_user or not self._admin_password:
            raise RuntimeError("PATCHMON_ADMIN_USER and PATCHMON_ADMIN_PASSWORD are required")

        self._token_key = os.environ.get("PATCHMON_TOKEN_KEY")
        self._token_secret = os.environ.get("PATCHMON_TOKEN_SECRET")

        self._jwt: Optional[str] = None
        self._jwt_expires_at: Optional[datetime] = None

        self._http = httpx.AsyncClient(
            base_url=endpoint,
            timeout=30.0,
            headers={"Accept": "application/json"},
            trust_env=False,
        )

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # JWT auth helpers
    # ------------------------------------------------------------------

    async def _login(self) -> str:
        """POST /api/v1/auth/login and cache the returned token."""
        resp = await self._http.post(
            "/api/v1/auth/login",
            json={"username": self._admin_user, "password": self._admin_password},
        )
        _raise_for_status(resp)
        data = resp.json()
        token: str = data["token"]
        # expires_at is ISO 8601 with Z suffix
        expires_at_str: str = data.get("expires_at", "")
        if expires_at_str:
            self._jwt_expires_at = datetime.fromisoformat(
                expires_at_str.replace("Z", "+00:00")
            )
        else:
            # Fallback: treat as 1 hour from now
            self._jwt_expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        self._jwt = token
        log.debug("jwt_refreshed", expires_at=expires_at_str)
        return token

    async def _get_jwt(self) -> str:
        """Return a valid JWT, refreshing if expired or absent."""
        now = datetime.now(tz=timezone.utc)
        if (
            self._jwt is not None
            and self._jwt_expires_at is not None
            and now < self._jwt_expires_at - timedelta(seconds=30)
        ):
            return self._jwt
        return await self._login()

    # ------------------------------------------------------------------
    # Admin API  (/api/v1/*)
    # ------------------------------------------------------------------

    async def request_admin(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request to the admin API with JWT. Retry once on 401."""
        token = await self._get_jwt()
        resp = await self._http.request(
            method,
            f"/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        if resp.status_code == 401:
            # Force refresh and retry once
            self._jwt = None
            token = await self._login()
            resp = await self._http.request(
                method,
                f"/api/v1{path}",
                headers={"Authorization": f"Bearer {token}"},
                **kwargs,
            )
        _raise_for_status(resp)
        return resp

    # ------------------------------------------------------------------
    # Integration API  (/api/v1/api/*)
    # ------------------------------------------------------------------

    def _integration_auth(self) -> tuple[str, str]:
        if not self._token_key or not self._token_secret:
            raise PatchMonConfigError(
                "PATCHMON_TOKEN_KEY and PATCHMON_TOKEN_SECRET are required for "
                "Integration API tools (read-only host/package data)."
            )
        return (self._token_key, self._token_secret)

    async def request_integration(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request to the Integration API with Basic Auth."""
        auth = self._integration_auth()
        resp = await self._http.request(
            method,
            f"/api/v1/api{path}",
            auth=auth,
            **kwargs,
        )
        _raise_for_status(resp)
        return resp


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _raise_for_status(resp: httpx.Response) -> None:
    """Raise PatchMonError for 4xx/5xx, preserving the JSON error message."""
    if resp.is_success:
        return
    try:
        msg = resp.json().get("error", resp.text)
    except Exception:
        msg = resp.text or resp.reason_phrase
    raise PatchMonError(resp.status_code, msg)


# Module-level singleton — created on first import, shared across tool calls.
_client: Optional[PatchMonClient] = None


def get_client() -> PatchMonClient:
    global _client
    if _client is None:
        _client = PatchMonClient()
    return _client
