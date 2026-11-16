"""Правила дозирования: версии, импорт/экспорт CSV (ТЗ 4.5.2, 6.5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import text

from app import rules_csv
from app.deps import RULE_ADMIN_ROLES, CurrentUser, require_roles, user_tx
from app.errors import ApiError
from app.rules_service import create_rule_version, require_drug
from app.rules_specs import RuleVersionSpec
from app.schemas_admin import ImportResult, RuleListOut, RuleVersionCreated

router = APIRouter(tags=["admin"])

_RULE_COLS = ("id, drug_id, version, indication, formula_code, weight_rule, rrt_mode, "
              "min_crcl::float AS min_crcl, max_crcl::float AS max_crcl, max_allowed_aki, "
              "min_age_years, max_age_years, pregnancy_contraindicated, dose_mg::float AS dose_mg, "
              "dose_per_kg::float AS dose_per_kg, loading_dose_per_kg::float AS loading_dose_per_kg, "
              "frequency_hours, infusion_duration_min, max_daily_dose_mg::float AS max_daily_dose_mg, "
              "tdm_required, clinical_note, source, effective_from, retired_at, created_at, created_by")


@router.get("/admin/drugs/{drug_id}/rules", response_model=RuleListOut,
            summary="Правила препарата, сгруппированы по версиям")
def list_rules(drug_id: int, user: CurrentUser = Depends(require_roles(*RULE_ADMIN_ROLES))) -> dict:
    with user_tx(user) as conn:
        require_drug(conn, user.organization_id, drug_id)
        rows = conn.execute(
            text(f"SELECT {_RULE_COLS} FROM dosage_rules WHERE drug_id = :d AND organization_id = :o "
                 "ORDER BY indication, version DESC, rrt_mode, min_crcl NULLS LAST"),
            {"d": drug_id, "o": user.organization_id}).mappings().all()
    groups: dict[tuple[str, int], dict] = {}
    for r in rows:
        g = groups.setdefault((r["indication"], r["version"]), {
            "indication": r["indication"], "version": r["version"],
            "is_active": r["retired_at"] is None, "retired_at": r["retired_at"], "rules": []})
        g["rules"].append(dict(r))
        g["is_active"] = g["is_active"] and r["retired_at"] is None
    return {"drug_id": drug_id, "versions": list(groups.values())}


@router.post("/admin/drugs/{drug_id}/rules", response_model=RuleVersionCreated, status_code=201,
             summary="Создать новую версию правил показания (старая версия закрывается)")
def create_version(drug_id: int, spec: RuleVersionSpec,
                   user: CurrentUser = Depends(require_roles(*RULE_ADMIN_ROLES))) -> dict:
    with user_tx(user) as conn:
        drug = require_drug(conn, user.organization_id, drug_id)
        if not drug["is_active"]:
            raise ApiError(409, "Drug archived", "Cannot add rules to an archived drug")
        return create_rule_version(conn, user.organization_id, drug_id, spec, user.id)


@router.delete("/admin/rules/{rule_id}", status_code=204, summary="Закрыть (retire) правило")
def retire_rule(rule_id: int, user: CurrentUser = Depends(require_roles(*RULE_ADMIN_ROLES))) -> None:
    with user_tx(user) as conn:
        row = conn.execute(
            text("UPDATE dosage_rules SET retired_at = now() WHERE id = :i AND organization_id = :o "
                 "AND retired_at IS NULL RETURNING id"),
            {"i": rule_id, "o": user.organization_id}).first()
        if row is None:
            raise ApiError(404, "Rule not found", f"Active rule {rule_id} not found")


@router.post("/admin/rules/import", response_model=ImportResult, status_code=201,
             summary="Импорт правил из CSV (multipart)")
async def import_rules(file: UploadFile = File(...),
                       user: CurrentUser = Depends(require_roles(*RULE_ADMIN_ROLES))) -> dict:
    raw = await file.read(rules_csv.MAX_BYTES + 1)
    specs = rules_csv.parse_csv(raw)  # любая ошибка — 400, ничего не импортируется
    results = []
    with user_tx(user) as conn:  # одна транзакция: всё или ничего
        for (drug_code, _), spec in specs.items():
            drug = conn.execute(
                text("SELECT id, is_active FROM drugs WHERE drug_code = :c AND organization_id = :o"),
                {"c": drug_code, "o": user.organization_id}).mappings().first()
            if drug is None or not drug["is_active"]:
                raise ApiError(400, "Invalid CSV", f"Unknown or archived drug_code '{drug_code}'; "
                                                   "nothing was imported")
            results.append({"drug_code": drug_code,
                            **create_rule_version(conn, user.organization_id, drug["id"], spec, user.id)})
    return {"imported": results}


@router.get("/admin/rules/export", summary="Экспорт активных правил в CSV")
def export_rules(drug_id: int | None = Query(default=None),
                 user: CurrentUser = Depends(require_roles(*RULE_ADMIN_ROLES))) -> Response:
    q = ("SELECT r.*, d.drug_code FROM dosage_rules r JOIN drugs d ON d.id = r.drug_id "
         "WHERE r.organization_id = :o AND r.retired_at IS NULL")
    params: dict = {"o": user.organization_id}
    if drug_id is not None:
        q += " AND r.drug_id = :d"
        params["d"] = drug_id
    with user_tx(user) as conn:
        rows = [dict(r) for r in conn.execute(
            text(q + " ORDER BY d.drug_code, r.indication, r.rrt_mode, r.min_crcl"), params).mappings()]
    for r in rows:
        for k in ("min_crcl", "max_crcl", "dose_mg", "dose_per_kg", "loading_dose_per_kg",
                  "max_daily_dose_mg"):
            r[k] = None if r[k] is None else float(r[k])
    return Response(rules_csv.render_csv(rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="dosage_rules.csv"'})
