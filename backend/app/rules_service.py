"""Версионирование правил дозирования (ТЗ 4.5.2).

Набор брекетов одного (препарат, показание) — это одна «версия». Правило нельзя редактировать:
новая версия создаётся целиком, а все активные строки прежней версии получают retired_at.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import ApiError
from app.rules_specs import RuleVersionSpec

_INSERT = text(
    "INSERT INTO dosage_rules (organization_id, drug_id, version, indication, formula_code, "
    "weight_rule, rrt_mode, min_crcl, max_crcl, max_allowed_aki, min_age_years, max_age_years, "
    "pregnancy_contraindicated, dose_mg, dose_per_kg, loading_dose_per_kg, frequency_hours, "
    "infusion_duration_min, max_daily_dose_mg, tdm_required, clinical_note, source, created_by) "
    "VALUES (:o, :d, :v, :indication, :formula_code, :weight_rule, :rrt_mode, :min_crcl, :max_crcl, "
    ":max_allowed_aki, :min_age_years, :max_age_years, :pregnancy_contraindicated, :dose_mg, "
    ":dose_per_kg, :loading_dose_per_kg, :frequency_hours, :infusion_duration_min, "
    ":max_daily_dose_mg, :tdm_required, :clinical_note, :source, :cb)"
)


def create_rule_version(conn: Connection, org_id: int, drug_id: int, spec: RuleVersionSpec,
                        created_by: int | None) -> dict:
    """Ретайрит активные строки показания и вставляет новую версию (в транзакции вызывающего)."""
    key = {"d": drug_id, "i": spec.indication, "o": org_id}
    # Сериализуем конкурентные создания версий одного показания
    conn.execute(text("SELECT pg_advisory_xact_lock(7002, :d)"), {"d": drug_id})
    current = conn.execute(
        text("SELECT COALESCE(max(version), 0) FROM dosage_rules "
             "WHERE drug_id = :d AND indication = :i AND organization_id = :o"), key).scalar_one()
    retired = conn.execute(
        text("UPDATE dosage_rules SET retired_at = now() WHERE drug_id = :d AND indication = :i "
             "AND organization_id = :o AND retired_at IS NULL"), key).rowcount
    version = current + 1
    head = spec.model_dump(exclude={"brackets"})
    for b in spec.brackets:
        conn.execute(_INSERT, {"o": org_id, "d": drug_id, "v": version, "cb": created_by,
                               **head, **b.model_dump()})
    return {"indication": spec.indication, "version": version, "brackets": len(spec.brackets),
            "retired_rows": retired}


def require_drug(conn: Connection, org_id: int, drug_id: int):
    row = conn.execute(text("SELECT * FROM drugs WHERE id = :i AND organization_id = :o"),
                       {"i": drug_id, "o": org_id}).mappings().first()
    if row is None:
        raise ApiError(404, "Drug not found", f"Drug {drug_id} not found")
    return row
