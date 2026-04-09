"""Microsoft OAuth 2.0 helper functions.

Handles building the authorization URL, exchanging the authorization code
for tokens, and fetching the signed-in user's profile from Graph API.

All settings are read from environment variables at call-time (not at
module import) so that tests can monkeypatch os.environ safely.
"""

from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

# ─── Microsoft OAuth 2.0 constants ───────────────────────────────────────────

_AUTHORITY = "https://login.microsoftonline.com"
_GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"
# Scopes requested during the auth flow.
_SCOPES = "openid profile email User.Read"


def _settings() -> tuple[str, str, str, str]:
    """Read Microsoft OAuth settings from environment variables.

    Returns:
        (tenant_id, client_id, client_secret, redirect_uri)
    """
    return (
        os.environ.get("MICROSOFT_TENANT_ID", "common"),
        os.environ["MICROSOFT_CLIENT_ID"],
        os.environ["MICROSOFT_CLIENT_SECRET"],
        os.environ.get(
            "MICROSOFT_REDIRECT_URI",
            "http://localhost:8000/auth/callback",
        ),
    )


# ─── Public API ───────────────────────────────────────────────────────────────


def get_authorization_url() -> str:
    """Build the Microsoft OAuth 2.0 authorization URL.

    The frontend should redirect the user to this URL to begin the
    OAuth flow.  After the user authenticates, Microsoft redirects back
    to MICROSOFT_REDIRECT_URI with a ``code`` query parameter.

    Returns:
        Fully-qualified authorization URL string.
    """
    tenant_id, client_id, _, redirect_uri = _settings()

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": _SCOPES,
        # response_mode=query keeps the code in the URL query string so
        # FastAPI can read it with Query(...).
        "response_mode": "query",
    }
    return f"{_AUTHORITY}/{tenant_id}/oauth2/v2.0/authorize?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    """Exchange an authorization code for Microsoft tokens.

    POSTs to the Microsoft token endpoint and returns the full token
    response dict, which includes ``access_token``, ``id_token``, and
    ``refresh_token`` (if offline_access was requested).

    Args:
        code: The ``code`` value received in the OAuth callback.

    Returns:
        Token response dict from Microsoft.

    Raises:
        HTTPException 502: If the token endpoint returns a non-2xx response.
    """
    tenant_id, client_id, client_secret, redirect_uri = _settings()
    token_url = f"{_AUTHORITY}/{tenant_id}/oauth2/v2.0/token"

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Microsoft token endpoint returned an error",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Microsoft authentication service",
            ) from exc

    return response.json()


async def get_microsoft_user_info(access_token: str) -> dict:
    """Fetch the signed-in user's profile from Microsoft Graph API.

    Calls ``GET /v1.0/me`` and returns the JSON body, which includes:
    - ``id``                 — stable Microsoft account OID (never log this)
    - ``displayName``        — e.g. "Nguyen Hoai Nam"
    - ``mail``               — primary SMTP address (may be None for some tenants)
    - ``userPrincipalName``  — fallback UPN, always present

    Args:
        access_token: A valid Microsoft Graph access token.

    Returns:
        User info dict from Graph API.

    Raises:
        HTTPException 502: If Graph API returns a non-2xx response.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                _GRAPH_ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Microsoft Graph API returned an error",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Microsoft Graph API",
            ) from exc

    return response.json()
