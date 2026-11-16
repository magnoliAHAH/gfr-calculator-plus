"""Аудит: однофазная HMAC-цепочка (ТЗ 4.3).

Цепочка своя у каждой организации (chain_id = 'org_<id>'): иначе RLS не позволил бы организации
проверить цепочку с чужими записями. Записи неизменяемы (триггер в БД), поэтому решение врача —
отдельная запись типа 'decision', ссылающаяся на расчёт через parent_audit_id.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.errors import ApiError
from app.metrics import AUDIT_CHAIN_ERRORS

GENESIS_HASH = "GENESIS_" + "0" * 56
_LOCK_NAMESPACE = 7001


def hmac_key() -> bytes:
    key = get_settings().hmac_key
    if len(key) < 16:
        # Graceful degradation (ТЗ 8.2): без ключа не выдаём «молчаливых» рекомендаций.
        AUDIT_CHAIN_ERRORS.inc()
        raise ApiError(503, "Service unavailable", "Audit HMAC key is not configured")
    return key.encode("utf-8")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(timezone.utc).isoformat()


def _num(value) -> float | None:
    # Колонка NUMERIC(10,2) округляет до 2 знаков: хешируем то, что реально будет прочитано из БД
    return None if value is None else round(float(Decimal(str(value))), 2)


def build_payload(rec: dict) -> dict:
    """Хешируемые поля. Первые 13 — из ТЗ 4.3.2; остальные добавлены, чтобы значения новых
    колонок (тип записи, ссылка на расчёт, новая доза) тоже были защищены от подмены."""
    return {
        "organization_id": rec["organization_id"],
        "user_id": rec["user_id"],
        "patient_ref": rec["patient_ref"],
        "created_at_iso": _iso(rec["created_at"]),
        "drug_id": rec.get("drug_id"),
        "rule_id": rec.get("rule_id"),
        "rule_version": rec.get("rule_version"),
        "input_data": rec["input_data"],
        "recommended_dose": rec.get("recommended_dose"),
        "calculation_mode": rec["calculation_mode"],
        "doctor_decision": rec["doctor_decision"],
        "override_reason_category": rec.get("override_reason_category"),
        "override_reason_text": rec.get("override_reason_text"),
        "record_type": rec["record_type"],
        "parent_audit_id": rec.get("parent_audit_id"),
        "override_new_dose_mg": _num(rec.get("override_new_dose_mg")),
        "override_new_frequency_hours": rec.get("override_new_frequency_hours"),
        "decision_at_iso": _iso(rec.get("decision_at")),
    }


def compute_hash(key: bytes, prev_hash: str, payload: dict) -> str:
    message = (prev_hash + "|" + canonical_json(payload)).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


_INSERT_SQL = text(
    """
    INSERT INTO audit_log (
        organization_id, created_at, record_type, parent_audit_id, user_id, patient_ref,
        drug_id, rule_id, rule_version, input_data, recommended_dose, calculation_mode,
        calc_duration_ms, doctor_decision, override_reason_category, override_reason_text,
        override_new_dose_mg, override_new_frequency_hours, decision_at,
        prev_hash, record_hash, is_demo)
    VALUES (
        :organization_id, :created_at, :record_type, :parent_audit_id, :user_id, :patient_ref,
        :drug_id, :rule_id, :rule_version, CAST(:input_data AS JSONB),
        CAST(:recommended_dose AS JSONB), :calculation_mode,
        :calc_duration_ms, :doctor_decision, :override_reason_category, :override_reason_text,
        :override_new_dose_mg, :override_new_frequency_hours, :decision_at,
        :prev_hash, :record_hash, FALSE)
    RETURNING id
    """
)

_COLUMNS = (
    "organization_id", "created_at", "record_type", "parent_audit_id", "user_id", "patient_ref",
    "drug_id", "rule_id", "rule_version", "calculation_mode", "calc_duration_ms", "doctor_decision",
    "override_reason_category", "override_reason_text", "override_new_dose_mg",
    "override_new_frequency_hours", "decision_at",
)


def append_record(conn: Connection, rec: dict) -> tuple[int, datetime]:
    """Добавляет запись в цепочку организации. Вызывать внутри открытой транзакции.

    Транзакционный advisory-lock сериализует писателей одной организации, SELECT ... FOR UPDATE
    на audit_chain_tip защищает от гонок при нескольких инстансах API.
    """
    key = hmac_key()
    org = rec["organization_id"]
    chain_id = f"org_{org}"
    conn.execute(text("SELECT pg_advisory_xact_lock(:ns, :org)"), {"ns": _LOCK_NAMESPACE, "org": org})
    conn.execute(
        text(
            "INSERT INTO audit_chain_tip (chain_id, organization_id, last_audit_id, last_hash) "
            "VALUES (:c, :o, NULL, :g) ON CONFLICT (chain_id) DO NOTHING"
        ),
        {"c": chain_id, "o": org, "g": GENESIS_HASH},
    )
    prev_hash = conn.execute(
        text("SELECT last_hash FROM audit_chain_tip WHERE chain_id = :c FOR UPDATE"), {"c": chain_id}
    ).scalar_one()

    # Микросекундная точность = точность TIMESTAMPTZ: хеш совпадёт с прочитанным из БД значением
    rec = {**rec, "created_at": datetime.now(timezone.utc)}
    record_hash = compute_hash(key, prev_hash, build_payload(rec))

    params = {c: rec.get(c) for c in _COLUMNS}
    params["input_data"] = json.dumps(rec["input_data"], ensure_ascii=False)
    params["recommended_dose"] = (
        None if rec.get("recommended_dose") is None
        else json.dumps(rec["recommended_dose"], ensure_ascii=False)
    )
    params["prev_hash"] = prev_hash
    params["record_hash"] = record_hash
    audit_id = conn.execute(_INSERT_SQL, params).scalar_one()

    conn.execute(
        text(
            "UPDATE audit_chain_tip SET last_audit_id = :i, last_hash = :h, updated_at = now() "
            "WHERE chain_id = :c"
        ),
        {"i": audit_id, "h": record_hash, "c": chain_id},
    )
    return audit_id, rec["created_at"]


def verify_chain(conn: Connection, org_id: int, upto_id: int) -> dict:
    """Пересчитывает HMAC всех записей организации от первой до upto_id включительно."""
    key = hmac_key()
    rows = conn.execute(
        text("SELECT * FROM audit_log WHERE organization_id = :o AND id <= :u ORDER BY id"),
        {"o": org_id, "u": upto_id},
    ).mappings()

    prev = GENESIS_HASH
    checked = 0
    first_invalid = None
    for row in rows:
        checked += 1
        expected = compute_hash(key, row["prev_hash"], build_payload(dict(row)))
        linked = hmac.compare_digest(row["prev_hash"], prev)
        authentic = hmac.compare_digest(expected, row["record_hash"])
        if not (linked and authentic):
            first_invalid = row["id"]
            break
        prev = row["record_hash"]

    if first_invalid is not None:
        AUDIT_CHAIN_ERRORS.inc()
    return {
        "valid": first_invalid is None,
        "first_invalid_id": first_invalid,
        "total_records_checked": checked,
        "verified_at": datetime.now(timezone.utc),
    }
