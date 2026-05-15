"""JWT creation, verification, and FastAPI dependency for protected routes.

Uses python-jose (``jose``) with HS256 by default.  The secret and
algorithm are read from environment variables at runtime so that tests
can override them safely.

Typical usage in a route:

    from auth.jwt_handler import get_current_user
    from models.user import UserDocument
    from typing import Annotated
    from fastapi import Depends

    @router.get("/me")
    async def me(user: Annotated[UserDocument, Depends(get_current_user)]):
        ...
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.database import USERS_COLLECTION, get_database
from models.user import UserDocument

# ─── OAuth2 scheme — extracts Bearer token from the Authorization header ──────
# tokenUrl is only used by OpenAPI docs; the real login flow is /auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _jwt_settings() -> tuple[str, str, int]:
    """Read JWT settings from environment."""
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not set. "
            "Set it to a long, random secret before starting the server."
        )
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
    return secret, algorithm, expire_minutes


# ─── Public API ───────────────────────────────────────────────────────────────


def create_access_token(user_id: str, email: str, role: str = "student") -> str:
    """Sign and return a JWT for the given user.

    The token payload contains:
    - ``sub``   — MongoDB ``_id`` as a plain string (used to look up the user).
    - ``email`` — HUST email address (informational, do not trust without DB check).
    - ``role``  — User role (``student`` | ``admin``).
    - ``iat``   — issued-at timestamp (UTC).
    - ``exp``   — expiry timestamp (UTC, offset by JWT_EXPIRE_MINUTES).

    Args:
        user_id: String representation of the user's MongoDB ObjectId.
        email:   Validated HUST email address.
        role:    User role, defaults to ``"student"``.

    Returns:
        Signed JWT string.
    """
    secret, algorithm, expire_minutes = _jwt_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def verify_token(token: str) -> dict:
    """Decode and validate a JWT, returning its payload dict.

    Args:
        token: The raw JWT string (without the ``Bearer`` prefix).

    Returns:
        Decoded payload dict containing at minimum ``sub`` and ``email``.

    Raises:
        HTTPException 401: If the token is malformed, has an invalid
            signature, or has expired.
    """
    secret, algorithm, _ = _jwt_settings()
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> UserDocument:
    """FastAPI dependency — resolve a Bearer JWT to a live UserDocument.

    Validates the token, extracts ``sub`` (the MongoDB ObjectId string),
    fetches the document from the ``users`` collection, and verifies the
    account is still active.

    Args:
        token: Injected by the OAuth2PasswordBearer scheme.
        db:    Injected Motor database dependency.

    Returns:
        The authenticated and active :class:`~models.user.UserDocument`.

    Raises:
        HTTPException 401: Token invalid/expired, user not found, or account inactive.
    """
    payload = verify_token(token)

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate that user_id is a legal ObjectId before hitting MongoDB.
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains an invalid user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    doc = await db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = UserDocument.model_validate(doc)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(optional_bearer_scheme),
    ],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> UserDocument | None:
    """Resolve a Bearer JWT when present, otherwise return ``None``.

    Missing credentials are allowed so legacy unauthenticated chat clients keep
    working. Malformed or expired credentials still fail with ``401`` because a
    client that sends an Authorization header is explicitly attempting auth.
    """
    if credentials is None:
        return None

    payload = verify_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id or not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains an invalid user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    doc = await db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = UserDocument.model_validate(doc)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
