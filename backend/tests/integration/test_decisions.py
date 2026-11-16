"""Решения врача: принять / переопределить / отклонить (ТЗ 4.2)."""
from tests.integration.helpers import API, calc, decide


def test_accept_then_second_decision_409(client, fresh_org):
    aid = calc(client, fresh_org)
    r = decide(client, fresh_org, aid, {"decision": "accepted"})
    assert r.status_code == 200 and r.json()["decision"] == "accepted"
    assert decide(client, fresh_org, aid, {"decision": "accepted"}).status_code == 409


def test_override_requires_category_and_text(client, fresh_org):
    aid = calc(client, fresh_org)
    assert decide(client, fresh_org, aid, {"decision": "overridden"}).status_code == 400
    short = {"decision": "overridden", "override_reason_category": "pk_data", "override_reason_text": "abc"}
    assert decide(client, fresh_org, aid, short).status_code == 400
    bad_cat = {"decision": "overridden", "override_reason_category": "zzz",
               "override_reason_text": "long enough"}
    assert decide(client, fresh_org, aid, bad_cat).status_code == 400


def test_failed_validation_does_not_consume_the_decision(client, fresh_org):
    aid = calc(client, fresh_org)
    decide(client, fresh_org, aid, {"decision": "overridden"})
    assert decide(client, fresh_org, aid, {"decision": "accepted"}).status_code == 200


def test_override_visible_in_audit_and_chain_valid(client, fresh_org):
    aid = calc(client, fresh_org)
    body = {"decision": "overridden", "override_reason_category": "clinical_judgment",
            "override_reason_text": "Планируется CRRT", "new_dose_mg": 1000, "new_frequency_hours": 24}
    r = decide(client, fresh_org, aid, body)
    assert r.status_code == 200, r.text
    entry = client.get(f"{API}/audit/{aid}", headers=fresh_org.headers("pharmacist")).json()
    assert entry["doctor_decision"] == "overridden"
    assert entry["override_reason_text"] == "Планируется CRRT"
    assert entry["override_new_dose_mg"] == 1000 and entry["decision_at"]
    dec_id = r.json()["decision_audit_id"]
    v = client.get(f"{API}/audit/{dec_id}/verify", headers=fresh_org.headers("auditor")).json()
    assert v["valid"] is True and v["total_records_checked"] == 2


def test_contraindication_requires_text(client, fresh_org):
    aid = calc(client, fresh_org)
    assert decide(client, fresh_org, aid, {"decision": "contraindication_acknowledged"}).status_code == 400
    ok = decide(client, fresh_org, aid, {"decision": "contraindication_acknowledged",
                                         "override_reason_text": "Аллергия"})
    assert ok.status_code == 200


def test_decision_on_failsafe_allowed(client, fresh_org):
    aid = calc(client, fresh_org, creatinine_umol_l=None)
    body = {"decision": "contraindication_acknowledged", "override_reason_text": "Отказ"}
    assert decide(client, fresh_org, aid, body).status_code == 200


def test_auditor_cannot_decide(client, fresh_org):
    aid = calc(client, fresh_org)
    assert decide(client, fresh_org, aid, {"decision": "accepted"}, role="auditor").status_code == 403


def test_unknown_audit_id_404(client, fresh_org):
    assert decide(client, fresh_org, 999999, {"decision": "accepted"}).status_code == 404


def test_decision_cannot_target_a_decision_record(client, fresh_org):
    aid = calc(client, fresh_org)
    dec_id = decide(client, fresh_org, aid, {"decision": "accepted"}).json()["decision_audit_id"]
    assert decide(client, fresh_org, dec_id, {"decision": "accepted"}).status_code == 404


def test_pending_and_decision_filters(client, fresh_org):
    a1 = calc(client, fresh_org, patient_ref="pa")
    a2 = calc(client, fresh_org, patient_ref="pb")
    decide(client, fresh_org, a2, {"decision": "accepted"})
    h = fresh_org.headers("pharmacist")
    pend = client.get(f"{API}/audit", params={"decision": "pending"}, headers=h).json()
    assert [i["id"] for i in pend["items"]] == [a1]
    acc = client.get(f"{API}/audit", params={"decision": "accepted"}, headers=h).json()
    assert [i["id"] for i in acc["items"]] == [a2] and acc["total"] == 1
    assert client.get(f"{API}/audit", params={"patient_ref": "pa"}, headers=h).json()["total"] == 1


def test_whole_chain_verify_counts_calculations_and_decisions(client, fresh_org):
    aid = calc(client, fresh_org)
    calc(client, fresh_org)
    decide(client, fresh_org, aid, {"decision": "accepted"})
    v = client.get(f"{API}/audit/chain/verify", headers=fresh_org.headers("auditor")).json()
    assert v["valid"] is True and v["total_records_checked"] == 3
    assert client.get(f"{API}/audit/chain/verify", headers=fresh_org.headers("physician")).status_code == 403


def test_whole_chain_verify_on_empty_org(client, fresh_org):
    v = client.get(f"{API}/audit/chain/verify", headers=fresh_org.headers("org_admin")).json()
    assert v["valid"] is True and v["total_records_checked"] == 0


def test_pagination(client, fresh_org):
    for i in range(5):
        calc(client, fresh_org, patient_ref=f"pg{i}")
    h = fresh_org.headers("auditor")
    p1 = client.get(f"{API}/audit", params={"limit": 2, "page": 1}, headers=h).json()
    p3 = client.get(f"{API}/audit", params={"limit": 2, "page": 3}, headers=h).json()
    assert p1["total"] == 5 and len(p1["items"]) == 2 and len(p3["items"]) == 1
    assert p1["items"][0]["id"] > p3["items"][0]["id"]  # новые сверху


def test_physician_sees_only_own_records(client, fresh_org):
    mine = calc(client, fresh_org, role="physician")
    theirs = calc(client, fresh_org, role="pharmacist")
    items = client.get(f"{API}/audit", headers=fresh_org.headers("physician")).json()["items"]
    assert [i["id"] for i in items] == [mine]
    assert client.get(f"{API}/audit/{theirs}", headers=fresh_org.headers("physician")).status_code == 404
    assert decide(client, fresh_org, theirs, {"decision": "accepted"}).status_code == 404
    assert client.get(f"{API}/audit", headers=fresh_org.headers("auditor")).json()["total"] == 2
