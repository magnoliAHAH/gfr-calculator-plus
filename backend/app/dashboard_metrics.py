"""Расчёт метрик дашборда (ТЗ 4.6, 6.6). Агрегаты считаются по расчётам; решения — по связанным записям."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app import audit

BUCKETS = [(0, 15), (15, 30), (30, 60), (60, 90), (90, 10000)]
BUCKET_LABELS = ["<15", "15-30", "30-60", "60-90", ">=90"]


def pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _round(v) -> float | None:
    return None if v is None else round(float(v), 2)


def compute_metrics(conn, org_id: int, start: datetime, end: datetime) -> dict:
    p = {"o": org_id, "s": start, "e": end}
    base = ("FROM audit_log a LEFT JOIN audit_log dec ON dec.parent_audit_id = a.id "
            "AND dec.record_type = 'decision' WHERE a.organization_id = :o "
            "AND a.record_type = 'calculation' AND a.created_at >= :s AND a.created_at < :e")
    row = conn.execute(text(
        "SELECT count(*) AS total, "
        "count(*) FILTER (WHERE dec.doctor_decision = 'accepted') AS accepted, "
        "count(*) FILTER (WHERE dec.doctor_decision = 'overridden') AS overridden, "
        "count(*) FILTER (WHERE dec.doctor_decision = 'contraindication_acknowledged') AS rejected, "
        "count(*) FILTER (WHERE dec.id IS NULL) AS pending, "
        "count(*) FILTER (WHERE a.calculation_mode = 'blocked_fail_safe') AS failsafe, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY a.calc_duration_ms) AS p50, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY a.calc_duration_ms) AS p95 " + base), p).mappings().one()
    total = row["total"]

    reasons = conn.execute(text(
        "SELECT dec.override_reason_category AS code, count(*) AS n " + base +
        " AND dec.doctor_decision = 'overridden' GROUP BY 1 ORDER BY n DESC, code LIMIT 5"), p).all()
    drugs = conn.execute(text(
        "SELECT d.drug_code AS code, d.drug_name AS name, count(*) AS n "
        "FROM audit_log a JOIN drugs d ON d.id = a.drug_id WHERE a.organization_id = :o "
        "AND a.record_type = 'calculation' AND a.created_at >= :s AND a.created_at < :e "
        "GROUP BY 1, 2 ORDER BY n DESC, code LIMIT 5"), p).all()
    values = [float(v) for (v,) in conn.execute(text(
        "SELECT (a.recommended_dose->'renal_function'->>'value')::float " + base +
        " AND a.calculation_mode = 'bracket_fallback' "
        "AND a.recommended_dose->'renal_function'->>'value' IS NOT NULL"), p)]
    hist = [{"bucket": label, "count": sum(1 for v in values if lo <= v < hi)}
            for label, (lo, hi) in zip(BUCKET_LABELS, BUCKETS)]

    chain = {"valid": True, "total_records": 0, "last_verified_at": None, "first_invalid_id": None}
    last_id = conn.execute(text("SELECT max(id) FROM audit_log WHERE organization_id = :o"),
                           {"o": org_id}).scalar()
    if last_id is not None:
        v = audit.verify_chain(conn, org_id, last_id)
        chain = {"valid": v["valid"], "total_records": v["total_records_checked"],
                 "last_verified_at": v["verified_at"], "first_invalid_id": v["first_invalid_id"]}
    return {
        "period": {"from": start, "to": end},
        "recommendations": {
            "total": total, "accepted": row["accepted"], "overridden": row["overridden"],
            "rejected": row["rejected"], "pending": row["pending"],
            "accepted_pct": pct(row["accepted"], total),
            "overridden_pct": pct(row["overridden"], total),
            "rejected_pct": pct(row["rejected"], total)},
        "override_reasons_top": [{"code": r.code, "count": r.n, "percentage": pct(r.n, row["overridden"])}
                                 for r in reasons],
        "drugs_top": [{"code": r.code, "name": r.name, "count": r.n} for r in drugs],
        "renal_function_histogram": hist,
        "performance": {"p50_ms": _round(row["p50"]), "p95_ms": _round(row["p95"])},
        "audit_chain": chain,
        "failsafe_rate": pct(row["failsafe"], total),
    }
