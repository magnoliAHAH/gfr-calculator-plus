"""Решение врача по рекомендации (ТЗ 4.2, 6.2).

Решение — новая запись аудита (record_type='decision'), расчёт не изменяется.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import audit
from app.deps import CALCULATE_ROLES, CurrentUser, require_roles, user_tx
from app.errors import ApiError
from app.schemas_audit import DecisionRequest, DecisionResponse

router = APIRouter(tags=["audit"])

MIN_OVERRIDE_TEXT = 5


def _validate(body: DecisionRequest) -> None:
    reason_text = (body.override_reason_text or "").strip()
    if body.decision == "overridden":
        if not body.override_reason_category:
            raise ApiError(400, "Validation error", "override_reason_category is required for overridden")
        if len(reason_text) < MIN_OVERRIDE_TEXT:
            raise ApiError(400, "Validation error",
                           f"override_reason_text must be at least {MIN_OVERRIDE_TEXT} characters")
    elif body.decision == "contraindication_acknowledged" and not reason_text:
        raise ApiError(400, "Validation error",
                       "override_reason_text is required for contraindication_acknowledged")


@router.post("/audit/{audit_id}/decision", response_model=DecisionResponse,
             summary="Принять / переопределить / отклонить рекомендацию",
             responses={409: {"description": "Решение уже установлено"}})
def set_decision(audit_id: int, body: DecisionRequest,
                 user: CurrentUser = Depends(require_roles(*CALCULATE_ROLES))) -> DecisionResponse:
    _validate(body)
    with user_tx(user) as conn:
        calc = conn.execute(
            text("SELECT id, user_id, patient_ref, drug_id, rule_id, rule_version, input_data, "
                 "recommended_dose, calculation_mode FROM audit_log "
                 "WHERE id = :i AND organization_id = :o AND record_type = 'calculation'"),
            {"i": audit_id, "o": user.organization_id}).mappings().first()
        if calc is None or (user.role == "physician" and calc["user_id"] != user.id):
            raise ApiError(404, "Audit record not found", f"Calculation {audit_id} not found")

        if body.override_reason_category:
            known = conn.execute(text("SELECT 1 FROM override_reasons WHERE code = :c"),
                                 {"c": body.override_reason_category}).first()
            if known is None:
                raise ApiError(400, "Validation error", "Unknown override_reason_category")

        now = datetime.now(timezone.utc)
        try:
            # SAVEPOINT: нарушение уникальности не должно ломать внешнюю транзакцию
            with conn.begin_nested():
                dec_id, _ = audit.append_record(conn, {
                    "organization_id": user.organization_id, "user_id": user.id,
                    "patient_ref": calc["patient_ref"], "drug_id": calc["drug_id"],
                    "rule_id": calc["rule_id"], "rule_version": calc["rule_version"],
                    "input_data": calc["input_data"], "recommended_dose": calc["recommended_dose"],
                    "calculation_mode": calc["calculation_mode"], "record_type": "decision",
                    "parent_audit_id": audit_id, "doctor_decision": body.decision,
                    "override_reason_category": body.override_reason_category,
                    "override_reason_text": (body.override_reason_text or "").strip() or None,
                    "override_new_dose_mg": body.new_dose_mg,
                    "override_new_frequency_hours": body.new_frequency_hours,
                    "decision_at": now,
                })
        except IntegrityError:
            raise ApiError(409, "Decision already set",
                           "A decision for this calculation already exists")
    return DecisionResponse(audit_id=audit_id, decision_audit_id=dec_id, decision=body.decision,
                            decision_at=now)
