# Module: `routers`

Source-verified: 2026-06-02 from `routers/auth.py`, `auth/*.py`, `schemas/user.py`, `api/main.py`, and web/mobile auth clients.

## Purpose

`routers` currently contains the auth HTTP router. It is included by `api/main.py` with prefix `/auth`.

Auth helper logic lives in `auth/`; Pydantic user schemas live in `schemas/user.py`; database models live in `models/user.py`.

## File Map

```text
routers/
  auth.py  Microsoft OAuth, manual register/login, refresh, profile, logout, admin creation.
```

## Routes

Mounted under `/auth`:

| Method/path | Purpose |
| --- | --- |
| `GET /auth/login` | Return Microsoft OAuth authorization URL. |
| `GET /auth/callback` | OAuth callback, upsert user, issue JWT, redirect. |
| `POST /auth/register` | Manual user registration. |
| `POST /auth/login` | Manual username/password login. |
| `POST /auth/refresh` | Rotate refresh token and issue a new access token. |
| `GET /auth/me` | Current user profile. |
| `PATCH /auth/me` | Update profile fields. |
| `POST /auth/logout` | Revoke refresh token when present and clear web cookie. |
| `POST /auth/admin/create` | Superadmin-created admin account. |

## Auth Behavior

- Microsoft OAuth depends on `auth/microsoft.py`.
- JWT creation/verification depends on `auth/jwt_handler.py`.
- Refresh-token session rotation/revocation depends on `auth/refresh_tokens.py`.
- Passwords depend on `auth/password.py`.
- Admin/superadmin checks depend on `auth/rbac.py`.
- User records are stored in Mongo `users`.
- Refresh sessions are stored in Mongo `refresh_tokens` with only hashed tokens.
- OAuth accepts HUST/SIS identity data and maps it into `UserDocument`.
- OAuth callback sets the web refresh cookie and redirects to the frontend
  without putting credentials in the URL.
- Manual web login sets the HttpOnly refresh cookie. Mobile login must send
  `client_type="mobile"` to receive the JSON `refresh_token`.

## Module Flow

```mermaid
flowchart TD
  Client["web/mobile"] --> Router["/auth routes"]
  Router -->|Microsoft| OAuth["auth/microsoft.py"]
  OAuth --> Upsert["Mongo users upsert"]
  Router -->|manual login/register| Password["auth/password.py"]
  Password --> Upsert
  Upsert --> Access["auth/jwt_handler.create_access_token"]
  Upsert --> Refresh["auth/refresh_tokens.issue_refresh_token"]
  Refresh --> CookieOrJSON["web HttpOnly cookie or mobile JSON refresh_token"]
  Client -->|Bearer| Me["/auth/me and protected routes"]
  Me --> CurrentUser["auth/jwt_handler.get_current_user"]
  Router -->|logout/refresh| Rotate["refresh token rotate/revoke"]
```

External module boundaries:

- Mounted by `api/main.py`; all route helpers and credential logic come from `auth`.
- Request/response bodies are defined in `schemas/user.py`.
- Refresh-token storage and user reads/writes go through `models/database.py`.
- Redirect/cookie behavior must match `frontend` auth-session code and `mobile` SecureStore flow.

## Maintenance Notes

- Keep route schemas aligned with `schemas/user.py` and shared/web/mobile auth types.
- Do not put reusable token/password/RBAC helpers here; keep them in `auth/`.
- Keep cookie settings aligned with frontend deployment:
  `AUTH_REFRESH_COOKIE_NAME`, `AUTH_REFRESH_COOKIE_SECURE`,
  `AUTH_REFRESH_COOKIE_SAMESITE`, and `FRONTEND_BASE_URL`.

## Useful Checks

```bash
python -m py_compile routers/auth.py auth/*.py schemas/user.py
python -m pytest tests/test_auth_refresh.py tests/test_rbac.py -q -m "not integration"
```
