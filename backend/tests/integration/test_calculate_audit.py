"""/calculate end-to-end с реальной БД: расчёт -> аудит -> решение -> верификация цепочки."""
import pytest
from sqlalchemy import text

from app.db import tx
from tests.integration.conftest import calc_body

URL = "/api/v1/calculate"


def post(client, org, body, role="physician"):
    return client.post(URL, json=body, headers=org.headers(role))


def test_demo1_obesity(client, org_a):
    r = post(client, org_a, calc_body())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["calculation_mode"] == "bracket_fallback"
    assert d["weight"]["type"] == "ABW"
    assert d["dose"]["amount_mg"] == 1350 and d["dose"]["frequency_hours"] == 12
    assert d["tdm_required"] is True and d["rule_version"] == 1
    assert d["formula"]["source"].startswith("IDSA")


def test_demo2_aki_failsafe_is_200_with_reason(client, org_a):
    body = calc_body(age_years=70, sex_at_birth="female", weight_kg=60, height_cm=None,
                     creatinine_umol_l=145, aki_stage="stage_2")
    r = post(client, org_a, body)
    assert r.status_code == 200
    d = r.json()
    assert d["calculation_mode"] == "blocked_fail_safe"
    assert d["no_recommendation_reason"] == "severe_aki_requires_consult"
    assert "audit_id" in d


def test_demo3_amikacin(client, org_a):
    body = calc_body(drug_code="AMIKACIN_IV", age_years=65, weight_kg=70, height_cm=None,
                     creatinine_umol_l=257.9)
    r = post(client, org_a, body)
    d = r.json()
    assert "dose" in d, r.text
    assert d["dose"]["amount_mg"] == 1050 and d["dose"]["frequency_hours"] == 48


def test_unknown_drug_404_problem_details(client, org_a):
    r = post(client, org_a, calc_body(drug_code="NOPE"))
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404 and body["correlation_id"]


def test_unknown_indication_404(client, org_a):
    assert post(client, org_a, calc_body(indication="nonsense")).status_code == 404


def test_validation_400_has_no_input_values(client, org_a):
    r = post(client, org_a, calc_body(weight_kg=5, patient_ref="Иванов Иван Иванович"))
    assert r.status_code == 400
    assert "Иванов" not in r.text  # PHI не эхоится в ответ об ошибке
    assert any(e["field"] == "weight_kg" for e in r.json()["errors"])


def test_auditor_cannot_calculate(client, org_a):
    assert post(client, org_a, calc_body(), role="auditor").status_code == 403


def test_unauthenticated_401(client):
    assert client.post(URL, json=calc_body()).status_code == 401


def test_audit_written_per_calculation_and_chain_valid(client, fresh_org):
    ids = [post(client, fresh_org, calc_body(patient_ref=f"p{i}")).json()["audit_id"] for i in range(3)]
    ids.append(post(client, fresh_org, calc_body(aki_stage="stage_3")).json()["audit_id"])
    v = client.get(f"/api/v1/audit/{ids[-1]}/verify", headers=fresh_org.headers("auditor")).json()
    assert v == {**v, "valid": True, "first_invalid_id": None, "total_records_checked": 4}
    first = client.get(f"/api/v1/audit/{ids[0]}", headers=fresh_org.headers("auditor")).json()
    assert first["prev_hash"] == "GENESIS_" + "0" * 56
    second = client.get(f"/api/v1/audit/{ids[1]}", headers=fresh_org.headers("auditor")).json()
    assert second["prev_hash"] == first["record_hash"]


def test_fail_safe_recorded_in_audit(client, fresh_org):
    aid = post(client, fresh_org, calc_body(creatinine_umol_l=None)).json()["audit_id"]
    e = client.get(f"/api/v1/audit/{aid}", headers=fresh_org.headers("pharmacist")).json()
    assert e["calculation_mode"] == "blocked_fail_safe"
    assert e["recommended_dose"]["no_rec_reason"] == "missing_creatinine"


def test_tampering_breaks_chain_at_exact_record(client, fresh_org):
    ids = [post(client, fresh_org, calc_body(patient_ref=f"t{i}")).json()["audit_id"] for i in range(4)]
    # Обходим триггер append-only от имени владельца (имитация злоумышленника с доступом к БД)
    with tx(None, privileged=True) as conn:
        conn.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_immutable"))
        conn.execute(text("UPDATE audit_log SET patient_ref = 'tampered' WHERE id = :i"), {"i": ids[1]})
        conn.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_immutable"))
    v = client.get(f"/api/v1/audit/{ids[3]}/verify", headers=fresh_org.headers("auditor")).json()
    assert v["valid"] is False and v["first_invalid_id"] == ids[1]
    ok = client.get(f"/api/v1/audit/{ids[0]}/verify", headers=fresh_org.headers("auditor")).json()
    assert ok["valid"] is True


def test_audit_log_is_append_only_even_for_owner(client, fresh_org):
    aid = post(client, fresh_org, calc_body()).json()["audit_id"]
    for sql in ("UPDATE audit_log SET patient_ref = 'x' WHERE id = :i", "DELETE FROM audit_log WHERE id = :i"):
        with pytest.raises(Exception, match="append-only"):
            with tx(None, privileged=True) as conn:
                conn.execute(text(sql), {"i": aid})