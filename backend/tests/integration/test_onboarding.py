"""Онбординг организации одним запросом (ТЗ 4.4.2): без участия разработчика."""
from sqlalchemy import text

from app.db import tx
from app.security import hash_password
from tests.integration.conftest import calc_body
from tests.integration.helpers import API


def super_admin_headers():
    from app.security import create_access_token

    with tx(None, privileged=True) as conn:
        org = conn.execute(text("INSERT INTO organizations (name, code) VALUES ('System', 'system') "
                                "ON CONFLICT (code) DO UPDATE SET name = 'System' RETURNING id")).scalar_one()
        row = conn.execute(text("SELECT id FROM users WHERE email = 'root@system.test'")).first()
        uid = row[0] if row else conn.execute(
            text("INSERT INTO users (organization_id, email, full_name, role, password_hash) "
                 "VALUES (:o, 'root@system.test', 'Root', 'super_admin', :h) RETURNING id"),
            {"o": org, "h": hash_password("x-root-pass")}).scalar_one()
    return {"Authorization": f"Bearer {create_access_token(uid, org, 'super_admin')}"}


def test_one_request_gives_working_admin_and_formulary(client):
    sa = super_admin_headers()
    body = {"name": "Новая больница", "code": "newhosp", "admin_email": "head@newhosp.test",
            "admin_full_name": "Главный Врач"}
    r = client.post(f"{API}/admin/organizations", json=body, headers=sa)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["temp_password"] and d["setup_url"] and d["seeded"] == {"drugs_added": 3, "rules_added": 13}
    login = client.post(f"{API}/auth/login", json={"email": body["admin_email"], "password": d["temp_password"]})
    assert login.status_code == 200 and login.json()["user"]["role"] == "org_admin"
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    drugs = client.get(f"{API}/meta/drugs", headers=h).json()
    assert len(drugs) == 3
    calc = client.post(f"{API}/calculate", json=calc_body(), headers=h)
    assert calc.status_code == 200 and calc.json()["dose"]["amount_mg"] == 1350


def test_onboarding_without_seed_gives_empty_formulary(client):
    sa = super_admin_headers()
    body = {"name": "Пустая", "code": "emptyorg", "admin_email": "a@emptyorg.test",
            "admin_full_name": "A", "copy_seed": False}
    r = client.post(f"{API}/admin/organizations", json=body, headers=sa)
    assert r.status_code == 201 and r.json()["seeded"] is None


def test_duplicate_code_or_email_is_409_and_atomic(client):
    sa = super_admin_headers()
    body = {"name": "Dup", "code": "dupcode", "admin_email": "a@dup.test", "admin_full_name": "A"}
    assert client.post(f"{API}/admin/organizations", json=body, headers=sa).status_code == 201
    assert client.post(f"{API}/admin/organizations", json=body, headers=sa).status_code == 409
    same_email = body | {"code": "dupcode2"}
    assert client.post(f"{API}/admin/organizations", json=same_email, headers=sa).status_code == 409
    codes = [o["code"] for o in client.get(f"{API}/admin/organizations", headers=sa).json()]
    assert "dupcode2" not in codes  # откат: «половинчатой» организации не осталось


def test_only_super_admin_can_manage_organizations(client, fresh_org):
    body = {"name": "X", "code": "xorg", "admin_email": "a@x.test", "admin_full_name": "A"}
    for role in ("org_admin", "pharmacist", "physician", "auditor"):
        h = fresh_org.headers(role)
        assert client.post(f"{API}/admin/organizations", json=body, headers=h).status_code == 403, role
        assert client.get(f"{API}/admin/organizations", headers=h).status_code == 403, role


def test_reserved_code_and_bad_code_rejected(client):
    sa = super_admin_headers()
    for code in ("system", "Bad Code", "x"):
        body = {"name": "X", "code": code, "admin_email": "q@q.test", "admin_full_name": "A"}
        assert client.post(f"{API}/admin/organizations", json=body, headers=sa).status_code == 400, code


def test_deactivated_org_users_are_locked_out(client):
    sa = super_admin_headers()
    body = {"name": "Temp", "code": "temporg", "admin_email": "a@temporg.test", "admin_full_name": "A"}
    d = client.post(f"{API}/admin/organizations", json=body, headers=sa).json()
    token = client.post(f"{API}/auth/login", json={"email": body["admin_email"],
                                                    "password": d["temp_password"]}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get(f"{API}/auth/me", headers=h).status_code == 200
    assert client.patch(f"{API}/admin/organizations/{d['id']}", json={"is_active": False},
                        headers=sa).status_code == 200
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401


def test_super_admin_sees_all_orgs_but_system_org_protected(client, org_a):
    sa = super_admin_headers()
    orgs = client.get(f"{API}/admin/organizations", headers=sa).json()
    assert org_a.id in [o["id"] for o in orgs]
    system = next(o for o in orgs if o["code"] == "system")
    r = client.patch(f"{API}/admin/organizations/{system['id']}", json={"is_active": False}, headers=sa)
    assert r.status_code == 409
