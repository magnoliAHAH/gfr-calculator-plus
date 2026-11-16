"""Логин, JWT, справочники, health."""
from sqlalchemy import text

from app.db import tx
from tests.integration.conftest import PASSWORD
from tests.integration.helpers import API


def test_login_ok_and_me(client, fresh_org):
    email = fresh_org.users["physician"]["email"]
    r = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["token_type"] == "bearer" and d["user"]["role"] == "physician"
    assert d["user"]["organization_id"] == fresh_org.id
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {d['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == email


def test_wrong_password_and_unknown_user_indistinguishable(client, fresh_org):
    email = fresh_org.users["physician"]["email"]
    a = client.post(f"{API}/auth/login", json={"email": email, "password": "nope"})
    b = client.post(f"{API}/auth/login", json={"email": "ghost@nowhere.test", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_login_case_insensitive_email(client, fresh_org):
    email = fresh_org.users["physician"]["email"].upper()
    assert client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200


def test_oauth2_form_login_for_swagger(client, fresh_org):
    r = client.post(f"{API}/auth/token", data={"username": fresh_org.users["physician"]["email"],
                                              "password": PASSWORD})
    assert r.status_code == 200 and r.json()["access_token"]


def test_deactivated_user_loses_access_immediately(client, fresh_org):
    h = fresh_org.headers("physician")
    assert client.get(f"{API}/auth/me", headers=h).status_code == 200
    with tx(None, privileged=True) as conn:
        conn.execute(text("UPDATE users SET is_active = FALSE WHERE id = :i"),
                     {"i": fresh_org.users["physician"]["id"]})
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401
    login = client.post(f"{API}/auth/login", json={"email": fresh_org.users["physician"]["email"],
                                                    "password": PASSWORD})
    assert login.status_code == 401


def test_deactivated_org_blocks_login(client):
    from tests.integration.conftest import make_org

    org = make_org(seed=False)
    with tx(None, privileged=True) as conn:
        conn.execute(text("UPDATE organizations SET is_active = FALSE WHERE id = :i"), {"i": org.id})
    r = client.post(f"{API}/auth/login", json={"email": org.users["physician"]["email"],
                                               "password": PASSWORD})
    assert r.status_code == 401


def test_garbage_and_missing_tokens_rejected(client):
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get(f"{API}/auth/me").status_code == 401


def test_logout_204(client, fresh_org):
    assert client.post(f"{API}/auth/logout", headers=fresh_org.headers("physician")).status_code == 204


def test_meta_endpoints(client, fresh_org):
    h = fresh_org.headers("physician")
    drugs = client.get(f"{API}/meta/drugs", headers=h).json()
    assert {d["drug_code"] for d in drugs} == {"VANCO_IV", "AMIKACIN_IV", "COLISTIN_IV"}
    ind = client.get(f"{API}/meta/indications", params={"drug_code": "COLISTIN_IV"}, headers=h).json()
    assert ind == ["MDR_gram_negative"]
    assert len(client.get(f"{API}/meta/formulas", headers=h).json()) == 2
    assert len(client.get(f"{API}/meta/override-reasons", headers=h).json()) == 6
    assert client.get(f"{API}/meta/indications", params={"drug_code": "X"}, headers=h).status_code == 404


def test_health(client):
    d = client.get("/health").json()
    assert d["status"] == "ok" and d["db"] == "ok"
    assert client.get("/health/ready").status_code == 200
