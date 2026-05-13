"""Role-Based Access Control (RBAC) — FastAPI dependencies.

Provides reusable dependencies that enforce role requirements on
protected routes.  Use as ``Depends(require_admin)`` or
``Depends(require_superadmin)``.

Roles
-----
- ``student`` — default role, can use the chatbot.
- ``admin``   — can upload/manage documents via the admin pipeline.
- Superadmin  — env-var-based; not a DB role but an overlay that grants
  ability to create admin accounts.

Usage::

    from auth.rbac import require_admin, require_superadmin

    @router.post("/admin/documents")
    async def upload(user: Annotated[UserDocument, Depends(require_admin)]):
        ...

    @router.post("/auth/admin/create")
    async def create_admin(user: Annotated[UserDocument, Depends(require_superadmin)]):
        ...
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, HTTPException, status

from auth.jwt_handler import get_current_user
from models.user import UserDocument


async def require_admin(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
) -> UserDocument:
    """FastAPI dependency that enforces ``role == 'admin'``.

    Any user whose ``role`` field is not ``"admin"`` receives a
    **403 Forbidden** response.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def require_superadmin(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
) -> UserDocument:
    """FastAPI dependency that enforces superadmin status.

    Superadmin is determined by the ``SUPERADMIN_USER_IDS`` environment
    variable (comma-separated list of MongoDB ObjectId strings).
    """
    superadmin_ids_raw = os.environ.get("SUPERADMIN_USER_IDS", "")
    superadmin_ids = {
        s.strip() for s in superadmin_ids_raw.split(",") if s.strip()
    }

    user_id = str(current_user.id)

    if user_id not in superadmin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required",
        )
    return current_user
