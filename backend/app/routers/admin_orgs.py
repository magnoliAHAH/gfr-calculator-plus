"""Организации и онбординг (ТЗ 4.4.2, 6.7). Только super_admin."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import tx
from app.deps import CurrentUser, require_roles
from app.errors import ApiError
from app.schemas_admin import OrgCreated, OrgListItem, OrgOut
from app.security import hash_password, temp_password
from app.seeding import SYSTEM_ORG_CODE, seed_org_formulary

router = APIRouter(prefix="/admin/organizations", tags=["organizations"])

_only_super = require_roles("super_admin")


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Городская больница №1"])
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9][a-z0-9_-]*$", examples=["gb1"])
    admin_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200,
                             examples=["head@gb1.ru"])
    admin_full_name: str = Field(min_length=1, max_length=200, examples=["Сидоров С.С."])
    copy_seed: bool = Field(default=True, description="Скопировать seed-препараты и правила")


class OrgPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


@router.get("", response_model=list[OrgListItem], summary="Все организации")
def list_orgs(_: CurrentUser = Depends(_only_super)) -> list[dict]:
    with tx(None, privileged=True) as conn:
        rows = conn.execute(text(
            "SELECT o.id, o.name, o.code, o.is_active, o.created_at, "
            "(SELECT count(*) FROM users u WHERE u.organization_id = o.id) AS users_count, "
            "(SELECT count(*) FROM audit_log a WHERE a.organization_id = o.id "
            " AND a.record_type = 'calculation') AS calculations_count "
            "FROM organizations o ORDER BY o.id")).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=OrgCreated, status_code=201,
             summary="Создать организацию и первого org_admin")
def create_org(body: OrgCreate, user: CurrentUser = Depends(_only_super)) -> dict:
    if body.code == SYSTEM_ORG_CODE:
        raise ApiError(400, "Validation error", f"Code '{SYSTEM_ORG_CODE}' is reserved")
    password = temp_password()
    try:
        with tx(None, privileged=True) as conn:  # одна транзакция: организация + админ + seed
            org_id = conn.execute(
                text("INSERT INTO organizations (name, code) VALUES (:n, :c) RETURNING id"),
                {"n": body.name, "c": body.code}).scalar_one()
            admin_id = conn.execute(
                text("INSERT INTO users (organization_id, email, full_name, role, password_hash, "
                     "must_change_password) VALUES (:o, :e, :n, 'org_admin', :h, TRUE) RETURNING id"),
                {"o": org_id, "e": body.admin_email.strip(), "n": body.admin_full_name,
                 "h": hash_password(password)}).scalar_one()
            seeded = seed_org_formulary(conn, org_id, admin_id) if body.copy_seed else None
    except IntegrityError as exc:
        which = "email" if "users" in str(exc.orig).lower() or "email" in str(exc.orig).lower() else "code"
        raise ApiError(409, "Already exists", f"Organization {which} is already in use")
    return {"id": org_id, "code": body.code, "admin_user_id": admin_id, "admin_email": body.admin_email,
            "temp_password": password, "setup_url": get_settings().public_base_url + "/login",
            "seeded": seeded}


@router.patch("/{org_id}", response_model=OrgOut, summary="Изменить организацию / деактивировать")
def patch_org(org_id: int, body: OrgPatch, _: CurrentUser = Depends(_only_super)) -> dict:
    with tx(None, privileged=True) as conn:
        row = conn.execute(text("SELECT id, code FROM organizations WHERE id = :i"), {"i": org_id}).first()
        if row is None:
            raise ApiError(404, "Organization not found", f"Organization {org_id} not found")
        if row.code == SYSTEM_ORG_CODE and body.is_active is False:
            raise ApiError(409, "System organization", "The system organization cannot be deactivated")
        if body.name is not None:
            conn.execute(text("UPDATE organizations SET name = :n WHERE id = :i"), {"n": body.name, "i": org_id})
        if body.is_active is not None:
            conn.execute(text("UPDATE organizations SET is_active = :a WHERE id = :i"),
                         {"a": body.is_active, "i": org_id})
        return dict(conn.execute(
            text("SELECT id, name, code, is_active, created_at FROM organizations WHERE id = :i"),
            {"i": org_id}).mappings().one())
