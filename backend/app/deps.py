"""Аутентификация и RBAC (ТЗ 3.2).

Пользователь перечитывается из БД на каждый запрос: деактивация и смена роли действуют сразу,
а не через 24 часа. Организация для RLS берётся из токена/БД, не из запроса.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text

from app.db import tx
from app.errors import ApiError
from app.security import decode_access_token

# Кнопка Authorize в Swagger шлёт форму (OAuth2 password flow): ей нужен /auth/token, а не JSON-/auth/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

ALL_ROLES = ("super_admin", "org_admin", "pharmacist", "physician", "auditor")
CALCULATE_ROLES = ("super_admin", "org_admin", "pharmacist", "physician")
AUDIT_VIEW_ROLES = ("super_admin", "org_admin", "pharmacist", "physician", "auditor")
DASHBOARD_ROLES = ("super_admin", "org_admin", "pharmacist", "auditor")
RULE_ADMIN_ROLES = ("super_admin", "org_admin", "pharmacist")
DRUG_ADMIN_ROLES = ("super_admin", "org_admin")
USER_ADMIN_ROLES = ("super_admin", "org_admin")


@dataclass(frozen=True)
class CurrentUser:
    id: int
    organization_id: int
    role: str
    email: str
    full_name: str
    organization_name: str
    must_change_password: bool = False

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    @property
    def privileged(self) -> bool:
        """super_admin работает под ролью БД с BYPASSRLS (ТЗ 4.4.1)."""
        return self.is_super_admin


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> CurrentUser:
    if not token:
        raise ApiError(401, "Not authenticated", "Authorization header is missing",
                       headers={"WWW-Authenticate": "Bearer"})
    claims = decode_access_token(token)
    # super_admin читает под владельцем схемы (RLS обходится), остальные — под cdss_app + tenant
    is_super = claims.get("role") == "super_admin"
    with tx(claims["organization_id"], privileged=is_super) as conn:
        row = conn.execute(
            text(
                "SELECT u.id, u.organization_id, u.role, u.email, u.full_name, u.is_active, "
                "u.must_change_password, o.name AS org_name, o.is_active AS org_active "
                "FROM users u JOIN organizations o ON o.id = u.organization_id WHERE u.id = :i"
            ),
            {"i": claims["user_id"]},
        ).mappings().first()
    if row is None or not row["is_active"] or not row["org_active"]:
        raise ApiError(401, "Not authenticated", "User is inactive or does not exist")
    return CurrentUser(row["id"], row["organization_id"], row["role"], row["email"],
                       row["full_name"], row["org_name"], row["must_change_password"])


def require_roles(*roles: str):
    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise ApiError(403, "Forbidden", "Insufficient permissions for this action")
        return user

    return checker


def user_tx(user: CurrentUser):
    """Транзакция с tenant-контекстом пользователя."""
    return tx(user.organization_id, privileged=user.privileged)
