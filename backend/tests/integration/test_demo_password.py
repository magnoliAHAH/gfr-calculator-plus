"""Публичный demo mode (ТЗ 4.7) и смена временного пароля."""
from sqlalchemy import text

from app.db import tx
from tests.integration.conftest import PASSWORD, make_org
from tests.integration.helpers import API


def audit_count() -> int:
    with tx(None, privileged=True) as conn:
        return conn.execute(text("SELECT count(*) FROM audit_log")).scalar_one()


def test_demo_scenarios_are_public_and_complete(client):
    r = client.get(f"{API}/demo/scenarios")  # без токена
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert ids == ["obesity", "aki", "renal"]
    assert all(s["message"] and s["request"]["drug_code"] for s in r.json())


def test_demo_drugs_are_public_with_indications(client):
    r = client.get(f"{API}/demo/drugs")
    assert r.status_code == 200
    by_code = {d["drug_code"]: d for d in r.json()}
    assert set(by_code) == {"VANCO_IV", "AMIKACIN_IV", "COLISTIN_IV"}
    assert by_code["COLISTIN_IV"]["indications"] == ["MDR_gram_negative"]
    assert by_code["VANCO_IV"]["drug_name"] == "Ванкомицин"


def test_each_demo_scenario_gives_documented_result(client):
    by_id = {s["id"]: s for s in client.get(f"{API}/demo/scenarios").json()}
    obesity = client.post(f"{API}/demo/calculate", json=by_id["obesity"]["request"]).json()
    assert obesity["dose"]["amount_mg"] == 1350 and obesity["dose"]["frequency_hours"] == 12
    assert obesity["weight"]["type"] == "ABW" and obesity["tdm_required"] is True
    aki = client.post(f"{API}/demo/calculate", json=by_id["aki"]["request"]).json()
    assert aki["calculation_mode"] == "blocked_fail_safe"
    assert aki["no_recommendation_reason"] == "severe_aki_requires_consult"
    renal = client.post(f"{API}/demo/calculate", json=by_id["renal"]["request"]).json()
    assert renal["dose"]["amount_mg"] == 1050 and renal["dose"]["frequency_hours"] == 48


def test_demo_never_writes_to_audit(client):
    before = audit_count()
    for s in client.get(f"{API}/demo/scenarios").json():
        r = client.post(f"{API}/demo/calculate", json=s["request"])
        assert r.status_code == 200 and r.json()["audit_id"] == 0
    assert audit_count() == before


def test_demo_rejects_unknown_drug_and_bad_input(client):
    base = client.get(f"{API}/demo/scenarios").json()[0]["request"]
    assert client.post(f"{API}/demo/calculate", json=base | {"drug_code": "X"}).status_code == 404
    assert client.post(f"{API}/demo/calculate", json=base | {"indication": "x"}).status_code == 404
    assert client.post(f"{API}/demo/calculate", json=base | {"weight_kg": 1}).status_code == 400


# ---------- смена пароля ----------

def login(client, email, password):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def test_invited_user_must_change_password_then_flag_clears(client, fresh_org):
    h = fresh_org.headers("org_admin")
    body = {"email": "temp.user@test.local", "full_name": "Temp", "role": "physician"}
    temp = client.post(f"{API}/admin/users", json=body, headers=h).json()["temp_password"]
    first = login(client, body["email"], temp).json()
    assert first["user"]["must_change_password"] is True
    th = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.get(f"{API}/auth/me", headers=th).json()["must_change_password"] is True
    new_pw = "Brand-new-pass-77"
    r = client.post(f"{API}/auth/change-password", headers=th,
                    json={"current_password": temp, "new_password": new_pw})
    assert r.status_code == 204
    assert login(client, body["email"], temp).status_code == 401
    again = login(client, body["email"], new_pw)
    assert again.status_code == 200 and again.json()["user"]["must_change_password"] is False


def test_change_password_validation(client, fresh_org):
    h = fresh_org.headers("physician")
    wrong = client.post(f"{API}/auth/change-password", headers=h,
                        json={"current_password": "nope", "new_password": "Another-long-pass-1"})
    assert wrong.status_code == 400
    short = client.post(f"{API}/auth/change-password", headers=h,
                        json={"current_password": PASSWORD, "new_password": "short"})
    assert short.status_code == 400
    same = client.post(f"{API}/auth/change-password", headers=h,
                       json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert same.status_code == 400
    too_long = client.post(f"{API}/auth/change-password", headers=h,
                           json={"current_password": PASSWORD, "new_password": "ж" * 40})
    assert too_long.status_code == 400  # 80 байт в UTF-8 > лимита bcrypt 72


def test_change_password_requires_auth(client):
    r = client.post(f"{API}/auth/change-password",
                    json={"current_password": "x", "new_password": "Another-long-pass-1"})
    assert r.status_code == 401


def test_super_admin_flag_and_login_path(client):
    org = make_org(seed=False)
    r = login(client, org.users["org_admin"]["email"], PASSWORD)
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is False
