# Module: `auth`

Source-verified: 2026-05-25 from `auth/*.py` and `routers/auth.py`.

## Purpose

`auth` contains authentication and authorization primitives used by FastAPI routes. It does not register routes itself; HTTP endpoints live in `routers/auth.py`.

## File Map

```text
auth/
  jwt_handler.py    JWT creation/verification and FastAPI current-user dependencies.
  refresh_tokens.py Opaque refresh-token sessions, rotation, hashing, revocation.
  microsoft.py      Microsoft OAuth URL, token exchange, user-info retrieval.
  password.py       Password hashing and verification helpers.
  rbac.py           Admin and superadmin dependencies.
```

## JWT Contract

`create_access_token(user_id, email, role="student")` creates tokens with:

- `sub`: MongoDB user id
- `email`
- `role`
- `typ`: `access`
- `jti`
- `iat`
- `exp`

Access token lifetime defaults to `JWT_ACCESS_EXPIRE_MINUTES=15`. Legacy
`JWT_EXPIRE_MINUTES` is still accepted as a fallback for existing deployments
and tests. `access_token_expires_in_seconds()` exposes the response `expires_in`
value.

`verify_token(token)` validates signature/expiry and returns payload.

FastAPI dependencies:

- `get_current_user()` requires a valid Bearer token and DB user.
- `get_optional_current_user()` returns `None` when no/invalid auth is present.

Chat routes use optional auth. Admin/session destructive routes require strict auth.

## Refresh Token Sessions

`refresh_tokens.py` issues opaque random refresh tokens and stores only a
SHA-256 hash in MongoDB collection `refresh_tokens`.

Stored fields include:

- `token_hash`
- `user_id`
- `family_id`
- `expires_at`
- `last_used_at`
- `revoked_at`
- `replaced_by`
- `client_type`

Default refresh lifetime is `JWT_REFRESH_EXPIRE_DAYS=30` with idle timeout
`JWT_REFRESH_IDLE_DAYS=7`. Refresh rotates the token on every use. Reuse of a
revoked token revokes the full token family.

Web clients receive refresh tokens through an HttpOnly cookie. Mobile clients
receive/send the opaque refresh token in API JSON and store it in SecureStore.

## Microsoft OAuth

`microsoft.py` owns:

- `_settings()`
- `get_authorization_url()`
- `exchange_code_for_token(code)`
- `get_microsoft_user_info(access_token)`

The router layer validates accepted HUST/SIS identity behavior and persists users.

## Passwords

`password.py` wraps password hashing/verification. Do not compare plain text passwords in routes.

## RBAC

`rbac.py` provides:

- `require_admin()`: current user must have role `admin` or satisfy superadmin overlay.
- `require_superadmin()`: current user id must be in `SUPERADMIN_USER_IDS`.

Superadmin is not a DB role; it is a configured overlay.

## Maintenance Notes

- If JWT payload fields change, update `schemas/user.py`, frontend/mobile auth stores, and tests.
- If refresh-token session fields change, update `models/database.py` indexes,
  `routers/auth.py`, web/mobile auth clients, and refresh tests.
- Keep route-level auth rules in `routers/auth.py` and admin routes explicit.
- Never trust body-supplied `user_id` when a Bearer token is present.

## Useful Checks

```bash
python -m py_compile auth/*.py routers/auth.py
python -m pytest tests/test_auth_refresh.py tests/test_rbac.py -q -m "not integration"
```
