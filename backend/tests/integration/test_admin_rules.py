"""Админка: версионирование правил (ТЗ 4.5.2)."""
from tests.integration.conftest import calc_body
from tests.integration.helpers import API
from tests.integration.test_admin_drugs import drug_id

NEW_RULE = {
    "indication": "sepsis_bacteremia", "formula_code": "cockcroft_gault", "weight_rule": "tbw",
    "source": "Local protocol 2026",
    "brackets": [
        {"min_crcl": 0, "max_crcl": 50, "dose_per_kg": 10, "frequency_hours": 24, "tdm_required": True},
        {"min_crcl": 50, "max_crcl": 999, "dose_per_kg": 10, "frequency_hours": 12},
    ],
}


def physician_calc(client, org):
    return client.post(f"{API}/calculate", json=calc_body(), headers=org.headers("physician")).json()


def test_new_version_retires_old_and_changes_calculation(client, fresh_org):
    h = fresh_org.headers("pharmacist")
    did = drug_id(client, fresh_org)
    before = physician_calc(client, fresh_org)
    assert before["rule_version"] == 1 and before["weight"]["type"] == "ABW"
    r = client.post(f"{API}/admin/drugs/{did}/rules", json=NEW_RULE, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["retired_rows"] == 4
    after = physician_calc(client, fresh_org)
    assert after["rule_version"] == 2 and after["weight"]["type"] == "TBW"
    assert after["dose"]["amount_mg"] == 1200  # 10 мг/кг * 120 кг
    old = client.get(f"{API}/audit/{before['audit_id']}", headers=fresh_org.headers("auditor")).json()
    assert old["rule_version"] == 1  # история не переписана
    groups = client.get(f"{API}/admin/drugs/{did}/rules", headers=h).json()["versions"]
    assert [(g["version"], g["is_active"]) for g in groups] == [(2, True), (1, False)]


def test_invalid_rule_is_rejected_and_old_version_stays_active(client, fresh_org):
    h = fresh_org.headers("org_admin")
    did = drug_id(client, fresh_org)
    overlap = NEW_RULE | {"brackets": [
        {"min_crcl": 0, "max_crcl": 60, "dose_per_kg": 10},
        {"min_crcl": 50, "max_crcl": 100, "dose_per_kg": 10}]}
    assert client.post(f"{API}/admin/drugs/{did}/rules", json=overlap, headers=h).status_code == 400
    nodose = NEW_RULE | {"brackets": [{"min_crcl": 0, "max_crcl": 50}]}
    assert client.post(f"{API}/admin/drugs/{did}/rules", json=nodose, headers=h).status_code == 400
    badformula = NEW_RULE | {"formula_code": "magic"}
    assert client.post(f"{API}/admin/drugs/{did}/rules", json=badformula, headers=h).status_code == 400
    assert physician_calc(client, fresh_org)["rule_version"] == 1


def test_rules_admin_permissions(client, fresh_org):
    did = drug_id(client, fresh_org)
    for role, status in (("physician", 403), ("auditor", 403), ("pharmacist", 201)):
        r = client.post(f"{API}/admin/drugs/{did}/rules", json=NEW_RULE, headers=fresh_org.headers(role))
        assert r.status_code == status, role


def test_retire_rule_leads_to_no_active_rule_failsafe(client, fresh_org):
    h = fresh_org.headers("org_admin")
    did = drug_id(client, fresh_org)
    rules = client.get(f"{API}/admin/drugs/{did}/rules", headers=h).json()["versions"][0]["rules"]
    for rule in rules:
        assert client.delete(f"{API}/admin/rules/{rule['id']}", headers=h).status_code == 204
    assert client.delete(f"{API}/admin/rules/{rules[0]['id']}", headers=h).status_code == 404
    r = physician_calc(client, fresh_org)
    assert r["calculation_mode"] == "blocked_fail_safe"
    assert r["no_recommendation_reason"] == "no_active_rule"


def test_rules_are_immutable_in_db(client, fresh_org):
    import pytest
    from sqlalchemy import text

    from app.db import tx

    did = drug_id(client, fresh_org)
    with pytest.raises(Exception, match="immutable"):
        with tx(None, privileged=True) as conn:
            conn.execute(text("UPDATE dosage_rules SET dose_per_kg = 99 WHERE drug_id = :d"), {"d": did})
    with pytest.raises(Exception, match="cannot be deleted"):
        with tx(None, privileged=True) as conn:
            conn.execute(text("DELETE FROM dosage_rules WHERE drug_id = :d"), {"d": did})
