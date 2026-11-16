"""Просмотр аудита и верификация цепочки (ТЗ 4.3.3, 6.3)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app import audit
from app.deps import AUDIT_VIEW_ROLES, DASHBOARD_ROLES, CurrentUser, require_roles, user_tx
from app.errors import ApiError
from app.schemas_audit import AuditEntry, AuditPage, VerifyResponse

router = APIRouter(tags=["audit"])

# Расчёт + присоединённое к нему решение врача (если есть): в списке одна строка на расчёт.
SELECT_ENTRY = """
SELECT a.*, u.full_name AS user_full_name, d.drug_code, d.drug_name,
       dec.doctor_decision AS dec_decision, dec.override_reason_category AS dec_cat,
       dec.override_reason_text AS dec_text, dec.override_new_dose_mg AS dec_dose,
       dec.override_new_frequency_hours AS dec_freq, dec.decision_at AS dec_at
FROM audit_log a
JOIN users u ON u.id = a.user_id
LEFT JOIN drugs d ON d.id = a.drug_id
LEFT JOIN audit_log dec ON dec.parent_audit_id = a.id AND dec.record_type = 'decision'
"""


def _f(v):
    return None if v is None else float(v)


def to_entry(r) -> AuditEntry:
    has_dec = r["record_type"] == "calculation" and r["dec_decision"] is not None
    return AuditEntry(
        id=r["id"], created_at=r["created_at"], record_type=r["record_type"],
        parent_audit_id=r["parent_audit_id"],
        user={"id": r["user_id"], "full_name": r["user_full_name"]},
        patient_ref=r["patient_ref"],
        drug=None if r["drug_code"] is None else {"code": r["drug_code"], "name": r["drug_name"]},
        rule_id=r["rule_id"], rule_version=r["rule_version"],
        input_data=r["input_data"], recommended_dose=r["recommended_dose"],
        calculation_mode=r["calculation_mode"],
        doctor_decision=r["dec_decision"] if has_dec else r["doctor_decision"],
        override_reason_category=r["dec_cat"] if has_dec else r["override_reason_category"],
        override_reason_text=r["dec_text"] if has_dec else r["override_reason_text"],
        override_new_dose_mg=_f(r["dec_dose"] if has_dec else r["override_new_dose_mg"]),
        override_new_frequency_hours=r["dec_freq"] if has_dec else r["override_new_frequency_hours"],
        decision_at=r["dec_at"] if has_dec else r["decision_at"],
        record_hash=r["record_hash"], prev_hash=r["prev_hash"],
    )


def visible_filter(user: CurrentUser) -> tuple[str, dict]:
    """physician видит только свои записи (ТЗ 3.2: «свои»), остальные — всю организацию."""
    if user.role == "physician":
        return "a.user_id = :uid", {"uid": user.id}
    return "TRUE", {}


@router.get("/audit", response_model=AuditPage, summary="Список аудита (по расчётам)")
def list_audit(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    drug: str | None = Query(default=None, description="Код препарата"),
    decision: str | None = Query(default=None, description="pending/accepted/overridden/..."),
    patient_ref: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_roles(*AUDIT_VIEW_ROLES)),
) -> AuditPage:
    vis, params = visible_filter(user)
    where = [vis, "a.record_type = 'calculation'", "a.organization_id = :org"]
    params["org"] = user.organization_id
    if from_:
        where.append("a.created_at >= :from_")
        params["from_"] = from_
    if to:
        where.append("a.created_at < :to")
        params["to"] = to
    if drug:
        where.append("d.drug_code = :drug")
        params["drug"] = drug
    if patient_ref:
        where.append("a.patient_ref = :pref")
        params["pref"] = patient_ref
    if decision == "pending":
        where.append("dec.id IS NULL")
    elif decision:
        where.append("dec.doctor_decision = :decision")
        params["decision"] = decision
    clause = " AND ".join(where)
    with user_tx(user) as conn:
        total = conn.execute(
            text("SELECT count(*) FROM audit_log a LEFT JOIN drugs d ON d.id = a.drug_id "
                 "LEFT JOIN audit_log dec ON dec.parent_audit_id = a.id AND dec.record_type = 'decision' "
                 f"WHERE {clause}"), params).scalar_one()
        rows = conn.execute(
            text(f"{SELECT_ENTRY} WHERE {clause} ORDER BY a.created_at DESC, a.id DESC "
                 "LIMIT :limit OFFSET :offset"),
            {**params, "limit": limit, "offset": (page - 1) * limit}).mappings().all()
    return AuditPage(items=[to_entry(r) for r in rows], total=total, page=page, limit=limit)


@router.get("/audit/chain/verify", response_model=VerifyResponse,
            summary="Проверить всю HMAC-цепочку организации (для бейджа целостности)")
def verify_whole_chain(user: CurrentUser = Depends(require_roles(*DASHBOARD_ROLES))) -> VerifyResponse:
    # Объявлен ДО /audit/{audit_id}, иначе 'chain' разбирался бы как audit_id.
    # Роль physician исключена: он видит только свои записи, а цепочка общая для организации.
    with user_tx(user) as conn:
        last_id = conn.execute(text("SELECT max(id) FROM audit_log WHERE organization_id = :o"),
                               {"o": user.organization_id}).scalar()
        if last_id is None:
            return VerifyResponse(valid=True, first_invalid_id=None, total_records_checked=0,
                                  verified_at=datetime.now(timezone.utc))
        return VerifyResponse(**audit.verify_chain(conn, user.organization_id, last_id))


@router.get("/audit/{audit_id}", response_model=AuditEntry, summary="Запись аудита")
def get_audit(audit_id: int, user: CurrentUser = Depends(require_roles(*AUDIT_VIEW_ROLES))) -> AuditEntry:
    vis, params = visible_filter(user)
    with user_tx(user) as conn:
        row = conn.execute(
            text(f"{SELECT_ENTRY} WHERE a.id = :id AND a.organization_id = :org AND {vis}"),
            {"id": audit_id, "org": user.organization_id, **params}).mappings().first()
    if row is None:
        raise ApiError(404, "Audit record not found", f"Audit record {audit_id} not found")
    return to_entry(row)


@router.get("/audit/{audit_id}/verify", response_model=VerifyResponse,
            summary="Проверить HMAC-цепочку от первой записи до указанной")
def verify(audit_id: int, user: CurrentUser = Depends(require_roles(*AUDIT_VIEW_ROLES))) -> VerifyResponse:
    vis, params = visible_filter(user)
    with user_tx(user) as conn:
        exists = conn.execute(
            text(f"SELECT 1 FROM audit_log a WHERE a.id = :i AND a.organization_id = :o AND {vis}"),
            {"i": audit_id, "o": user.organization_id, **params}).first()
        if exists is None:
            raise ApiError(404, "Audit record not found", f"Audit record {audit_id} not found")
        return VerifyResponse(**audit.verify_chain(conn, user.organization_id, audit_id))
