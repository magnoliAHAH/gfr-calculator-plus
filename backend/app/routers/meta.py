"""Справочники (ТЗ 6.4)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.deps import CurrentUser, get_current_user, user_tx
from app.errors import ApiError
from app.schemas_admin import DrugMetaOut, FormulaOut, OverrideReasonOut

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/formulas", response_model=list[FormulaOut], summary="Справочник формул")
def formulas(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    with user_tx(user) as conn:
        rows = conn.execute(text("SELECT * FROM formulas ORDER BY code")).mappings().all()
    return [dict(r) for r in rows]


@router.get("/override-reasons", response_model=list[OverrideReasonOut],
            summary="Категории переопределения")
def override_reasons(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    with user_tx(user) as conn:
        rows = conn.execute(text("SELECT * FROM override_reasons ORDER BY code")).mappings().all()
    return [dict(r) for r in rows]


@router.get("/drugs", response_model=list[DrugMetaOut],
            summary="Активные препараты текущей организации")
def drugs(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    with user_tx(user) as conn:
        rows = conn.execute(
            text(
                "SELECT id, drug_code, drug_name, atc_code, route, formulation, rounding_step_mg::float "
                "AS rounding_step_mg FROM drugs WHERE is_active AND organization_id = :o ORDER BY drug_name"
            ),
            {"o": user.organization_id},
        ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/indications", summary="Показания препарата (по активным правилам)")
def indications(drug_code: str = Query(description="Код препарата", examples=["VANCO_IV"]),
                user: CurrentUser = Depends(get_current_user)) -> list[str]:
    with user_tx(user) as conn:
        drug = conn.execute(
            text("SELECT id FROM drugs WHERE drug_code = :c AND is_active AND organization_id = :o"),
            {"c": drug_code, "o": user.organization_id},
        ).first()
        if drug is None:
            raise ApiError(404, "Drug not found", f"Drug '{drug_code}' not found or inactive")
        rows = conn.execute(
            text("SELECT DISTINCT indication FROM dosage_rules WHERE drug_id = :d AND retired_at IS NULL "
                 "ORDER BY indication"),
            {"d": drug[0]},
        ).all()
    return [r[0] for r in rows]
