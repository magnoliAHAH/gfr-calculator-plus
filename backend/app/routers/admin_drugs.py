"""Управление препаратами (ТЗ 4.5.1, 6.5). Архивация вместо удаления."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.deps import DRUG_ADMIN_ROLES, RULE_ADMIN_ROLES, CurrentUser, require_roles, user_tx
from app.errors import ApiError
from app.schemas_admin import DrugOut

router = APIRouter(prefix="/admin/drugs", tags=["admin"])

_COLS = ("id, drug_code, drug_name, atc_code, route, formulation, "
         "rounding_step_mg::float AS rounding_step_mg, is_active, created_at")


class DrugCreate(BaseModel):
    drug_code: str = Field(min_length=1, max_length=100, examples=["VANCO_IV"])
    drug_name: str = Field(min_length=1, max_length=200, examples=["Ванкомицин"])
    atc_code: str | None = Field(default=None, max_length=20, examples=["J01XA01"])
    route: str = Field(min_length=1, max_length=50, examples=["IV"])
    formulation: str | None = Field(default=None, max_length=100)
    rounding_step_mg: float = Field(default=250, gt=0, le=10000, description="Шаг округления дозы, мг")


class DrugPatch(BaseModel):
    drug_name: str | None = Field(default=None, min_length=1, max_length=200)
    atc_code: str | None = Field(default=None, max_length=20)
    route: str | None = Field(default=None, min_length=1, max_length=50)
    formulation: str | None = Field(default=None, max_length=100)
    rounding_step_mg: float | None = Field(default=None, gt=0, le=10000)


def _target_org(user: CurrentUser, organization_id: int | None) -> int:
    if organization_id is not None and organization_id != user.organization_id and not user.is_super_admin:
        raise ApiError(403, "Forbidden", "Cannot access another organization")
    return organization_id or user.organization_id


@router.get("", response_model=list[DrugOut], summary="Препараты организации (активные и архивные)")
def list_drugs(include_archived: bool = True, organization_id: int | None = Query(default=None),
               user: CurrentUser = Depends(require_roles(*RULE_ADMIN_ROLES))) -> list[dict]:
    org = _target_org(user, organization_id)
    with user_tx(user) as conn:
        rows = conn.execute(
            text(f"SELECT {_COLS} FROM drugs WHERE organization_id = :o "
                 "AND (:arch OR is_active) ORDER BY drug_name"),
            {"o": org, "arch": include_archived}).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=DrugOut, status_code=201, summary="Создать препарат")
def create_drug(body: DrugCreate, organization_id: int | None = Query(default=None),
                user: CurrentUser = Depends(require_roles(*DRUG_ADMIN_ROLES))) -> dict:
    org = _target_org(user, organization_id)
    try:
        with user_tx(user) as conn:
            row = conn.execute(
                text("INSERT INTO drugs (organization_id, drug_code, drug_name, atc_code, route, "
                     f"formulation, rounding_step_mg) VALUES (:o, :drug_code, :drug_name, :atc_code, "
                     f":route, :formulation, :rounding_step_mg) RETURNING {_COLS}"),
                {"o": org, **body.model_dump()}).mappings().one()
    except IntegrityError:
        raise ApiError(409, "Drug exists", f"Drug '{body.drug_code}' already exists in this organization")
    return dict(row)


@router.patch("/{drug_id}", response_model=DrugOut, summary="Изменить препарат (только не архивный)")
def patch_drug(drug_id: int, body: DrugPatch,
               user: CurrentUser = Depends(require_roles(*DRUG_ADMIN_ROLES))) -> dict:
    changes = body.model_dump(exclude_unset=True, exclude_none=False)
    changes = {k: v for k, v in changes.items() if not (v is None and k in ("drug_name", "route",
                                                                           "rounding_step_mg"))}
    with user_tx(user) as conn:
        drug = _get_drug(conn, user, drug_id)
        if not drug["is_active"]:
            raise ApiError(409, "Drug archived", "Archived drugs cannot be edited")
        if changes:
            sets = ", ".join(f"{k} = :{k}" for k in changes)
            conn.execute(text(f"UPDATE drugs SET {sets} WHERE id = :id"), {**changes, "id": drug_id})
        row = conn.execute(text(f"SELECT {_COLS} FROM drugs WHERE id = :i"), {"i": drug_id}).mappings().one()
    return dict(row)


@router.delete("/{drug_id}", status_code=204, summary="Архивировать препарат (is_active=false)")
def archive_drug(drug_id: int, user: CurrentUser = Depends(require_roles(*DRUG_ADMIN_ROLES))) -> None:
    with user_tx(user) as conn:
        _get_drug(conn, user, drug_id)
        conn.execute(text("UPDATE drugs SET is_active = FALSE WHERE id = :i"), {"i": drug_id})


def _get_drug(conn, user: CurrentUser, drug_id: int):
    q = "SELECT * FROM drugs WHERE id = :i"
    params = {"i": drug_id}
    if not user.is_super_admin:
        q += " AND organization_id = :o"
        params["o"] = user.organization_id
    row = conn.execute(text(q), params).mappings().first()
    if row is None:
        raise ApiError(404, "Drug not found", f"Drug {drug_id} not found")
    return row
