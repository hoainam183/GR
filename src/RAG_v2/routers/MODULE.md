# Module: `routers`

Source-verified: 2026-05-20 from `routers/auth.py` and `api/main.py`.

## Purpose

`routers` currently contains the auth HTTP router. It is included by `api/main.py` with prefix `/auth`.

Auth helper logic lives in `auth/`; Pydantic user schemas live in `schemas/user.py`; database models live in `models/user.py`.

## File Map

```text
routers/
  auth.py  Microsoft OAuth, manual register/login, profile, logout, admin creation.
```

## Routes

Mounted under `/auth`:

| Method/path | Purpose |
| --- | --- |
| `GET /auth/login` | Return Microsoft OAuth authorization URL. |
| `GET /auth/callback` | OAuth callback, upsert user, issue JWT, redirect. |
| `POST /auth/register` | Manual user registration. |
| `POST /auth/login` | Manual username/password login. |
| `GET /auth/me` | Current user profile. |
| `PATCH /auth/me` | Update profile fields. |
| `POST /auth/logout` | Stateless logout acknowledgement. |
| `POST /auth/admin/create` | Superadmin-created admin account. |

## Auth Behavior

- Microsoft OAuth depends on `auth/microsoft.py`.
- JWT creation/verification depends on `auth/jwt_handler.py`.
- Passwords depend on `auth/password.py`.
- Admin/superadmin checks depend on `auth/rbac.py`.
- User records are stored in Mongo `users`.
- OAuth accepts HUST/SIS identity data and maps it into `UserDocument`.

## Maintenance Notes

- Keep route schemas aligned with `schemas/user.py` and shared/web/mobile auth types.
- Do not put reusable token/password/RBAC helpers here; keep them in `auth/`.
- If adding refresh tokens, update mobile because it currently assumes a single access token.

## Useful Checks

```bash
python -m py_compile routers/auth.py auth/*.py schemas/user.py
python -m pytest tests/test_rbac.py -q -m "not integration"
```
