"""HMAC-цепочка: known-answer тест и свойства канонизации (ТЗ 4.3.2, 10.1)."""
import hashlib
import hmac
from datetime import datetime, timezone

from app.audit import GENESIS_HASH, build_payload, canonical_json, compute_hash

KEY = b"0123456789abcdef0123456789abcdef"

REC = {
    "organization_id": 1,
    "user_id": 2,
    "patient_ref": "p_abc123",
    "created_at": datetime(2026, 1, 15, 14, 32, 0, 123456, tzinfo=timezone.utc),
    "drug_id": 3,
    "rule_id": 45,
    "rule_version": 1,
    "input_data": {"weight_kg": 120, "age_years": 45, "sex_at_birth": "male"},
    "recommended_dose": {"dose": {"amount_mg": 1350.0}},
    "calculation_mode": "bracket_fallback",
    "doctor_decision": "pending",
    "record_type": "calculation",
}


def test_genesis_format():
    assert GENESIS_HASH == "GENESIS_" + "0" * 56
    assert len(GENESIS_HASH) == 64


def test_canonical_json_sorted_no_spaces():
    assert canonical_json({"b": 1, "a": {"d": 2, "c": [1, 2]}}) == '{"a":{"c":[1,2],"d":2},"b":1}'


def test_canonical_json_keeps_unicode():
    assert canonical_json({"t": "Планируется CRRT"}) == '{"t":"Планируется CRRT"}'


def test_known_answer_independent_computation():
    """Ожидаемое значение собрано вручную, без вызова compute_hash/build_payload."""
    payload = (
        '{"calculation_mode":"bracket_fallback","created_at_iso":"2026-01-15T14:32:00.123456+00:00",'
        '"decision_at_iso":null,"doctor_decision":"pending","drug_id":3,'
        '"input_data":{"age_years":45,"sex_at_birth":"male","weight_kg":120},'
        '"organization_id":1,"override_new_dose_mg":null,"override_new_frequency_hours":null,'
        '"override_reason_category":null,"override_reason_text":null,"parent_audit_id":null,'
        '"patient_ref":"p_abc123","recommended_dose":{"dose":{"amount_mg":1350.0}},'
        '"record_type":"calculation","rule_id":45,"rule_version":1,"user_id":2}'
    )
    expected = hmac.new(KEY, (GENESIS_HASH + "|" + payload).encode(), hashlib.sha256).hexdigest()
    assert canonical_json(build_payload(REC)) == payload
    assert compute_hash(KEY, GENESIS_HASH, build_payload(REC)) == expected


def test_hash_depends_on_prev_hash():
    p = build_payload(REC)
    assert compute_hash(KEY, GENESIS_HASH, p) != compute_hash(KEY, "a" * 64, p)


def test_hash_depends_on_key():
    p = build_payload(REC)
    assert compute_hash(KEY, GENESIS_HASH, p) != compute_hash(b"x" * 32, GENESIS_HASH, p)


def test_hash_detects_any_field_change():
    base = compute_hash(KEY, GENESIS_HASH, build_payload(REC))
    for field, value in [
        ("patient_ref", "p_other"), ("rule_version", 2), ("doctor_decision", "accepted"),
        ("input_data", {"weight_kg": 121, "age_years": 45, "sex_at_birth": "male"}),
        ("override_reason_text", "x"), ("override_new_dose_mg", 100),
    ]:
        changed = compute_hash(KEY, GENESIS_HASH, build_payload({**REC, field: value}))
        assert changed != base, field


def test_timestamp_normalised_to_utc():
    from datetime import timedelta

    local = REC["created_at"].astimezone(timezone(timedelta(hours=3)))
    assert build_payload({**REC, "created_at": local}) == build_payload(REC)


def test_new_dose_rounded_like_db_numeric():
    a = build_payload({**REC, "override_new_dose_mg": 1350})
    b = build_payload({**REC, "override_new_dose_mg": "1350.00"})
    assert a == b
