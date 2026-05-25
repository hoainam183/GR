"""Authentication router — Microsoft OAuth 2.0 + JWT endpoints.

Endpoints:
    GET  /auth/login           — Returns the Microsoft authorization URL.
    GET  /auth/callback        — Handles the OAuth callback; issues a JWT.
    GET  /auth/me              — Returns the current user's public profile.
    PATCH /auth/me             — Updates the current user's profile.
    POST /auth/logout          — Stateless logout (instructs FE to drop token).

All protected routes require a valid ``Authorization: Bearer <JWT>`` header,
resolved via the :func:`~auth.jwt_handler.get_current_user` dependency.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.jwt_handler import (
    access_token_expires_in_seconds,
    create_access_token,
    get_current_user,
)
from auth.microsoft import (
    exchange_code_for_token,
    get_authorization_url,
    get_microsoft_user_info,
)
from auth.password import hash_password, verify_password
from auth.refresh_tokens import (
    create_refresh_session,
    refresh_token_max_age_seconds,
    revoke_refresh_token,
    rotate_refresh_token,
)
from models.database import USERS_COLLECTION, get_database
from models.user import UserDocument
from schemas.user import (
    AdminCreateRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLoginRequest,
    UserManualCreate,
    UserPublic,
    UserUpdate,
)
from utils.parse_hust_email import parse_hust_email

router = APIRouter()

# Only @sis.hust.edu.vn addresses are allowed.
_HUST_DOMAIN = "@sis.hust.edu.vn"
# Frontend base URL — where the user is redirected after authentication.
_FRONTEND_BASE = os.environ.get("FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
_REFRESH_COOKIE_NAME = os.environ.get("AUTH_REFRESH_COOKIE_NAME", "refresh_token")


def _cookie_secure() -> bool:
    configured = os.environ.get("AUTH_REFRESH_COOKIE_SECURE")
    if configured is not None:
        return configured.lower() in {"1", "true", "yes", "on"}
    return _FRONTEND_BASE.startswith("https://")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE_NAME,
        token,
        max_age=refresh_token_max_age_seconds(),
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite=os.environ.get("AUTH_REFRESH_COOKIE_SAMESITE", "lax"),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        _REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite=os.environ.get("AUTH_REFRESH_COOKIE_SAMESITE", "lax"),
    )


def _token_response(
    *,
    access_token: str,
    user: UserPublic,
    refresh_token: str | None = None,
) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_token_expires_in_seconds(),
        user=user,
        refresh_token=refresh_token,
    )


# ─── /auth/login ──────────────────────────────────────────────────────────────


@router.get("/login", summary="Start Microsoft OAuth flow")
async def login_oauth() -> dict:
    """Return the Microsoft authorization URL.

    The frontend should redirect the user to the returned URL.  Microsoft will
    ask the user to sign in and then redirect back to the configured
    ``MICROSOFT_REDIRECT_URI`` with a ``code`` query parameter.

    Returns:
        ``{"authorization_url": "https://login.microsoftonline.com/..."}``
    """
    return {"authorization_url": get_authorization_url()}


# ─── /auth/callback ───────────────────────────────────────────────────────────


@router.get("/callback", summary="Microsoft OAuth callback — issues JWT")
async def callback(
    code: Annotated[str, Query(description="Authorization code from Microsoft")],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> RedirectResponse:
    """Handle the Microsoft OAuth 2.0 callback.

    Flow:
    1. Exchange ``code`` for Microsoft tokens.
    2. Fetch the user's profile from Graph API.
    3. Validate their email ends with ``@sis.hust.edu.vn`` (403 if not).
    4. Parse HUST metadata from the email via ``parse_hust_email()``.
    5. Upsert the user in MongoDB.
    6. Issue a JWT.
    7. Redirect the user to the appropriate frontend page.

    Redirect targets (token delivered via HttpOnly refresh cookie, NOT the URL):
    - New user or incomplete profile → ``/complete-profile``
    - Existing user with complete profile → ``/chat``

    The frontend then calls ``POST /auth/refresh`` (which sends the cookie automatically)
    to obtain a short-lived access JWT.
    """
    # ── Step 1: Exchange code → Microsoft tokens ──────────────────────────────
    token_response = await exchange_code_for_token(code)
    ms_access_token: str | None = token_response.get("access_token")
    if not ms_access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Microsoft did not return an access token",
        )

    # ── Step 2: Fetch user profile from Graph API ─────────────────────────────
    ms_user = await get_microsoft_user_info(ms_access_token)

    # ── Step 3: Strict HUST domain validation ─────────────────────────────────
    # Microsoft returns `mail` for Exchange-backed accounts and
    # `userPrincipalName` (UPN) as a reliable fallback.  We check both so
    # that either field being valid is sufficient.
    mail: str = (ms_user.get("mail") or "").strip().lower()
    upn: str = (ms_user.get("userPrincipalName") or "").strip().lower()

    hust_email: str | None = None
    if mail.endswith(_HUST_DOMAIN):
        hust_email = mail
    elif upn.endswith(_HUST_DOMAIN):
        hust_email = upn

    if hust_email is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access is restricted to {_HUST_DOMAIN} email addresses. "
                "Please sign in with your HUST student account."
            ),
        )

    # microsoft_id is the stable OID claim — never logged or returned to clients.
    microsoft_id: str = ms_user.get("id", "")

    # ── Step 4: Parse HUST metadata from email ────────────────────────────────
    try:
        parsed = parse_hust_email(hust_email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse student metadata from email: {exc}",
        ) from exc

    # ── Step 5: Upsert user in MongoDB ────────────────────────────────────────
    now = datetime.now(timezone.utc)
    existing_doc = await db[USERS_COLLECTION].find_one(
        {"microsoft_id": microsoft_id}
    )

    if existing_doc is None:
        # New user — build the full document and insert it.
        # display_name from Graph API is preferred; fall back to parsed value.
        display_name: str = (ms_user.get("displayName") or "").strip()
        new_user = UserCreate(
            microsoft_id=microsoft_id,
            email=hust_email,
            full_name=display_name or parsed["full_name"],
            student_id=parsed["student_id"],
            cohort=parsed["cohort"],
            major=parsed["major"],
        )
        document = {
            **new_user.model_dump(),
            "is_profile_complete": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login_at": now,
        }
        result = await db[USERS_COLLECTION].insert_one(document)
        user_id = str(result.inserted_id)
        is_profile_complete = False
    else:
        # Existing user — refresh last_login_at only; leave everything else intact.
        await db[USERS_COLLECTION].update_one(
            {"_id": existing_doc["_id"]},
            {"$set": {"last_login_at": now}},
        )
        user_id = str(existing_doc["_id"])
        is_profile_complete = bool(existing_doc.get("is_profile_complete", False))

    # ── Step 6: Issue JWT ─────────────────────────────────────────────────────
    # Fetch role from DB for existing users; new users default to "student".
    user_role = "student"
    if existing_doc is not None:
        user_role = existing_doc.get("role", "student")
    refresh_token = await create_refresh_session(
        db,
        user_id=user_id,
        client_type="web",
    )

    # ── Step 7: Redirect to frontend ─────────────────────────────────────────
    if is_profile_complete:
        redirect_url = f"{_FRONTEND_BASE}/chat"
    else:
        redirect_url = f"{_FRONTEND_BASE}/complete-profile"

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    _set_refresh_cookie(response, refresh_token)
    return response


# ─── /auth/register ───────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user with username/password",
)
async def register(
    body: UserManualCreate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> UserPublic:
    """Create a new manual account.

    Checks that ``username`` is unique, hashes the password with bcrypt, and
    inserts a new user document.  Returns the public user profile.
    """
    # Uniqueness check on username
    existing = await db[USERS_COLLECTION].find_one({"username": body.username})
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken.",
        )

    now = datetime.now(timezone.utc)
    # Build document, omitting None-valued fields so sparse unique indexes
    # (email, microsoft_id) don't treat absent fields as duplicate null values.
    _raw = {
        "username": body.username,
        "password_hash": hash_password(body.password),
        "full_name": body.full_name,
        "student_id": body.student_id,
        "cohort": body.cohort,
        "major": body.major,
        "major_code": body.major_code,
        "is_profile_complete": True,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "last_login_at": now,
    }
    document = {k: v for k, v in _raw.items() if v is not None}
    result = await db[USERS_COLLECTION].insert_one(document)
    inserted = await db[USERS_COLLECTION].find_one({"_id": result.inserted_id})
    if inserted is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created user document.",
        )
    return UserPublic.from_document(inserted)


# ─── /auth/login (username/password) ─────────────────────────────────────────


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with username and password",
)
async def login(
    body: UserLoginRequest,
    response: Response,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> TokenResponse:
    """Authenticate with username + password, return a JWT.

    Looks up the user by ``username``, verifies the bcrypt password hash, and
    issues a JWT token identical in structure to the OAuth flow.
    """
    doc = await db[USERS_COLLECTION].find_one({"username": body.username})
    if doc is None or not doc.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    # Update last login timestamp
    now = datetime.now(timezone.utc)
    await db[USERS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_login_at": now}},
    )

    user_id = str(doc["_id"])
    user_role = doc.get("role", "student")
    # Use username as the email claim (informational; get_current_user only uses sub)
    jwt_token = create_access_token(user_id=user_id, email=body.username, role=user_role)
    client_type = "mobile" if body.client_type == "mobile" else "web"
    refresh_token = await create_refresh_session(
        db,
        user_id=user_id,
        client_type=client_type,
    )
    if client_type == "web":
        _set_refresh_cookie(response, refresh_token)

    return _token_response(
        access_token=jwt_token,
        user=UserPublic.from_document(doc),
        refresh_token=refresh_token if client_type == "mobile" else None,
    )


# ─── /auth/me  (GET) ──────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue a new access token",
)
async def refresh(
    response: Response,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    body: RefreshRequest | None = Body(default=None),
    refresh_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    """Rotate a web cookie or mobile refresh token and issue a new access token."""
    raw_refresh = body.refresh_token if body and body.refresh_token else refresh_cookie
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
        )

    client_type = "mobile" if body and body.client_type == "mobile" else "web"
    next_refresh, user = await rotate_refresh_token(
        db,
        raw_refresh,
        client_type=client_type,
    )
    email_claim = user.email or user.username or str(user.id)
    access_token = create_access_token(
        user_id=str(user.id),
        email=email_claim,
        role=user.role,
    )
    if client_type == "web":
        _set_refresh_cookie(response, next_refresh)

    return _token_response(
        access_token=access_token,
        user=UserPublic.model_validate(user.model_dump(by_alias=True)),
        refresh_token=next_refresh if client_type == "mobile" else None,
    )


@router.get("/me", response_model=UserPublic, summary="Get current user profile")
async def get_me(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
) -> UserPublic:
    """Return the authenticated user's public profile.

    Requires ``Authorization: Bearer <JWT>``.
    """
    # model_dump(by_alias=True) ensures ``_id`` is serialised correctly.
    return UserPublic.model_validate(current_user.model_dump(by_alias=True))


# ─── /auth/me  (PATCH) ────────────────────────────────────────────────────────


@router.patch("/me", response_model=UserPublic, summary="Update current user profile")
async def update_me(
    body: UserUpdate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> UserPublic:
    """Partially update the authenticated user's profile.

    Accepts any subset of ``full_name``, ``student_id``, ``cohort``, ``major``.
    On success the user's ``is_profile_complete`` flag is set to ``True`` and
    ``updated_at`` is refreshed server-side.

    Requires ``Authorization: Bearer <JWT>``.
    """
    update_data = body.to_update_dict()  # injects updated_at automatically
    # Mark the profile as complete on any successful PATCH.
    update_data["is_profile_complete"] = True

    object_id = ObjectId(current_user.id)
    await db[USERS_COLLECTION].update_one(
        {"_id": object_id},
        {"$set": update_data},
    )

    updated_doc = await db[USERS_COLLECTION].find_one({"_id": object_id})
    if updated_doc is None:
        # Should never happen — the user was verified moments ago.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User record disappeared during update",
        )

    return UserPublic.from_document(updated_doc)


# ─── /auth/logout ─────────────────────────────────────────────────────────────


@router.post("/logout", summary="Log out and revoke the refresh token when present")
async def logout(
    response: Response,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    request: Request,
    body: RefreshRequest | None = Body(default=None),
) -> dict:
    """Revoke the refresh token if supplied, then clear the browser cookie."""
    raw_refresh = (
        body.refresh_token
        if body and body.refresh_token
        else request.cookies.get(_REFRESH_COOKIE_NAME)
    )
    if raw_refresh:
        await revoke_refresh_token(db, raw_refresh)
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


# ─── /auth/admin/create ───────────────────────────────────────────────────────


@router.post(
    "/admin/create",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create an admin account (superadmin only)",
)
async def create_admin(
    body: AdminCreateRequest,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> UserPublic:
    """Create a new admin account.

    Only superadmin users (whose ObjectId is listed in the
    ``SUPERADMIN_USER_IDS`` environment variable) may call this endpoint.

    The created user will have ``role = "admin"`` and
    ``is_profile_complete = True``.
    """
    import os

    # ── Superadmin check ──────────────────────────────────────────────────────
    superadmin_ids_raw = os.environ.get("SUPERADMIN_USER_IDS", "")
    superadmin_ids = {
        s.strip() for s in superadmin_ids_raw.split(",") if s.strip()
    }
    if str(current_user.id) not in superadmin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required",
        )

    # ── Uniqueness check ──────────────────────────────────────────────────────
    existing = await db[USERS_COLLECTION].find_one({"username": body.username})
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken.",
        )

    now = datetime.now(timezone.utc)
    document = {
        "username": body.username,
        "password_hash": hash_password(body.password),
        "full_name": body.full_name,
        "student_id": body.student_id,
        "cohort": body.cohort,
        "major": body.major,
        "major_code": body.major_code,
        "role": "admin",
        "is_profile_complete": True,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "last_login_at": now,
    }
    result = await db[USERS_COLLECTION].insert_one(document)
    inserted = await db[USERS_COLLECTION].find_one({"_id": result.inserted_id})
    if inserted is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created admin document.",
        )
    return UserPublic.from_document(inserted)
