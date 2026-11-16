"""Управление пользователями организации (ТЗ 4.5.3, 6.5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.deps import USER_ADMIN_ROLES, CurrentUser, require_roles, user_tx
from app.errors import ApiError
from app.schemas_admin import UserAdminOut, UserInvited
from app.security import hash_password, temp_password

router = APIRouter(prefix="/admin/users", tags=["admin"])

ASSIGNABLE = ("org_admin", "pharmacist", "physician", "auditor")
_COLS = "id, email, full_name, role, is_active, must_change_password, created_at"


class UserInvite(BaseModel):
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                       examples=["new.doctor@hospital.ru"])
    full_name: str = Field(min_length=1, max_length=200, examples=["Петров П.П."])
    role: str = Field(examples=["physician"])


class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None


def _check_role(user: CurrentUser, role: str) -> None:
    allowed = ASSIGNABLE + (("super_admin",) if user.is_super_admin else ())
    if role not in allowed:
        raise ApiError(400, "Validation error", f"role must be one of {allowed}")


def _get(conn, user: CurrentUser, user_id: int):
    row = conn.execute(text(f"SELECT {_COLS}, organization_id FROM users WHERE id = :i "
                            "AND organization_id = :o"),
                       {"i": user_id, "o": user.organization_id}).mappings().first()
    if row is None:
        raise ApiError(404, "User not found", f"User {user_id} not found")
    return row


def _last_admin_guard(conn, user: CurrentUser, target) -> None:
    """Нельзя лишить организацию последнего активного org_admin (иначе нужен разработчик)."""
    if target["role"] != "org_admin" or not target["is_active"]:
        return
    others = conn.execute(
        text("SELECT count(*) FROM users WHERE organization_id = :o AND role = 'org_admin' "
             "AND is_active AND id <> :i"), {"o": user.organization_id, "i": target["id"]}).scalar_one()
    if others == 0:
        raise ApiError(409, "Last admin", "Organization must keep at least one active org_admin")


@router.get("", response_model=list[UserAdminOut], summary="Пользователи организации")
def list_users(user: CurrentUser = Depends(require_roles(*USER_ADMIN_ROLES))) -> list[dict]:
    with user_tx(user) as conn:
        rows = conn.execute(text(f"SELECT {_COLS} FROM users WHERE organization_id = :o ORDER BY full_name"),
                            {"o": user.organization_id}).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=UserInvited, status_code=201,
             summary="Пригласить пользователя (временный пароль в ответе)")
def invite(body: UserInvite, user: CurrentUser = Depends(require_roles(*USER_ADMIN_ROLES))) -> dict:
    _check_role(user, body.role)
    password = temp_password()
    try:
        with user_tx(user) as conn:
            row = conn.execute(
                text(f"INSERT INTO users (organization_id, email, full_name, role, password_hash, "
                     f"must_change_password) VALUES (:o, :e, :n, :r, :h, TRUE) RETURNING {_COLS}"),
                {"o": user.organization_id, "e": body.email.strip(), "n": body.full_name,
                 "r": body.role, "h": hash_password(password)}).mappings().one()
    except IntegrityError:
        raise ApiError(409, "User exists", "A user with this email already exists")
    # В пилоте письмо не отправляется: пароль показывается один раз (ТЗ 4.5.3)
    return {**dict(row), "temp_password": password, "setup_url": get_settings().public_base_url + "/login"}


@router.patch("/{user_id}", response_model=UserAdminOut, summary="Изменить роль / активность")
def patch_user(user_id: int, body: UserPatch,
               user: CurrentUser = Depends(require_roles(*USER_ADMIN_ROLES))) -> dict:
    if body.role is not None:
        _check_role(user, body.role)
    with user_tx(user) as conn:
        target = _get(conn, user, user_id)
        if target["role"] == "super_admin" and not user.is_super_admin:
            raise ApiError(403, "Forbidden", "Cannot modify a super_admin")
        losing_admin = (body.role is not None and body.role != "org_admin") or body.is_active is False
        if losing_admin:
            _last_admin_guard(conn, user, target)
        if user_id == user.id and body.is_active is False:
            raise ApiError(409, "Self deactivation", "You cannot deactivate yourself")
        if body.role is not None:
            conn.execute(text("UPDATE users SET role = :r WHERE id = :i"), {"r": body.role, "i": user_id})
        if body.is_active is not None:
            conn.execute(text("UPDATE users SET is_active = :a WHERE id = :i"),
                         {"a": body.is_active, "i": user_id})
        return dict(conn.execute(text(f"SELECT {_COLS} FROM users WHERE id = :i"), {"i": user_id}).mappings().one())


@router.delete("/{user_id}", status_code=204, summary="Деактивировать пользователя (soft delete)")
def deactivate(user_id: int, user: CurrentUser = Depends(require_roles(*USER_ADMIN_ROLES))) -> None:
    patch_user(user_id, UserPatch(is_active=False), user)
