"""POST /calculate (ТЗ 4.1, 6.2): загрузка правил -> клиническое ядро -> аудит."""
from __future__ import annotations

import time
from typing import Union

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app import audit
from app.clinical.engine import calculate
from app.clinical.failsafe import FailSafe
from app.clinical.types import CalcInput, RuleData
from app.deps import CALCULATE_ROLES, CurrentUser, require_roles, user_tx
from app.errors import ApiError
from app.metrics import CALCULATE_TOTAL
from app.schemas import CalculateRequest, FailSafeResponse, Recommendation

router = APIRouter(tags=["calculate"])

_RULE_FIELDS = (
    "id", "version", "formula_code", "weight_rule", "source", "rrt_mode", "min_crcl", "max_crcl",
    "max_allowed_aki", "dose_mg", "dose_per_kg", "loading_dose_per_kg", "frequency_hours",
    "infusion_duration_min", "max_daily_dose_mg", "tdm_required", "clinical_note", "min_age_years",
    "max_age_years", "pregnancy_contraindicated",
)
_FLOAT_FIELDS = {"min_crcl", "max_crcl", "dose_mg", "dose_per_kg", "loading_dose_per_kg",
                 "max_daily_dose_mg"}


def to_rule_data(row, rounding_step_mg: float) -> RuleData:
    data = {}
    for f in _RULE_FIELDS:
        v = row[f]
        data[f] = float(v) if (f in _FLOAT_FIELDS and v is not None) else v
    return RuleData(rounding_step_mg=float(rounding_step_mg), **data)


def _input_snapshot(body: CalculateRequest) -> dict:
    return body.model_dump(mode="json")


@router.post(
    "/calculate",
    response_model=Union[Recommendation, FailSafeResponse],
    summary="Рассчитать дозу",
    description="Возвращает Recommendation либо FailSafe (различаются по `calculation_mode`). "
                "Fail-safe — штатный исход, HTTP 200. Каждый расчёт пишется в аудит.",
    responses={400: {"description": "Ошибка валидации (ProblemDetails)"},
               404: {"description": "Препарат не найден (ProblemDetails)"}},
)
def calculate_dose(body: CalculateRequest,
                   user: CurrentUser = Depends(require_roles(*CALCULATE_ROLES))):
    started = time.perf_counter()
    snapshot = _input_snapshot(body)

    with user_tx(user) as conn:
        drug = conn.execute(
            text("SELECT id, rounding_step_mg FROM drugs "
                 "WHERE drug_code = :c AND is_active AND organization_id = :o"),
            {"c": body.drug_code, "o": user.organization_id},
        ).mappings().first()
        if drug is None:
            raise ApiError(404, "Drug not found", f"Drug '{body.drug_code}' not found or inactive")

        rule_rows = conn.execute(
            text("SELECT * FROM dosage_rules WHERE drug_id = :d AND indication = :i "
                 "AND retired_at IS NULL AND organization_id = :o"),
            {"d": drug["id"], "i": body.indication, "o": user.organization_id},
        ).mappings().all()
        rules = [to_rule_data(r, drug["rounding_step_mg"]) for r in rule_rows]

        # Если у препарата нет ни одного правила для этого показания, но есть для других,
        # показание, скорее всего, введено неверно — это 404, а не клинический fail-safe.
        if not rules:
            known = conn.execute(
                text("SELECT 1 FROM dosage_rules WHERE drug_id = :d AND retired_at IS NULL LIMIT 1"),
                {"d": drug["id"]},
            ).first()
            if known is not None:
                raise ApiError(404, "Indication not found",
                               f"No active rule for indication '{body.indication}'")

        inp = CalcInput(
            age_years=body.age_years, sex_at_birth=body.sex_at_birth, aki_stage=body.aki_stage,
            rrt_mode=body.rrt_mode, pregnancy=body.pregnancy, ecmo=body.ecmo,
            weight_kg=body.weight_kg, height_cm=body.height_cm,
            creatinine_umol_l=body.creatinine_umol_l,
        )

        failsafe: FailSafe | None = None
        rec = None
        try:
            rec = calculate(rules, inp)
        except FailSafe as fs:
            failsafe = fs

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        base = {
            "organization_id": user.organization_id, "user_id": user.id,
            "patient_ref": body.patient_ref, "drug_id": drug["id"], "input_data": snapshot,
            "record_type": "calculation", "doctor_decision": "pending",
            "calc_duration_ms": duration_ms,
        }

        if failsafe is not None:
            result = {
                "calculation_mode": "blocked_fail_safe",
                "no_recommendation_reason": failsafe.reason,
                "no_recommendation_display": failsafe.display,
                "details": failsafe.details,
            }
            first = rules[0] if rules else None
            audit_id, created = audit.append_record(conn, {
                **base, "rule_id": first.id if first else None,
                "rule_version": first.version if first else None,
                "recommended_dose": {"no_rec_reason": failsafe.reason, **result},
                "calculation_mode": "blocked_fail_safe",
            })
            CALCULATE_TOTAL.labels("fail_safe").inc()
            return FailSafeResponse(audit_id=audit_id, generated_at=created, **result)

        result = rec.to_dict()
        audit_id, created = audit.append_record(conn, {
            **base, "rule_id": rec.rule.id, "rule_version": rec.rule.version,
            "recommended_dose": result, "calculation_mode": "bracket_fallback",
        })
    CALCULATE_TOTAL.labels("recommendation").inc()
    return Recommendation(audit_id=audit_id, calculation_mode="bracket_fallback",
                          generated_at=created, **result)
