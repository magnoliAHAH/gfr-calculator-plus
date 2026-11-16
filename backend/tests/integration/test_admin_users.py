"""Админка: пользователи (ТЗ 4.5.3, 3.2)."""
from tests.integration.helpers import API


def test_invite_and_login_with_temp_password(client, fresh_org):
    h = fresh_org.headers("org_admin")
    body = {"email": "new.doc@test.local", "full_name": "Новый Врач", "role": "physician"}
    r = client.post(f"{API}/admin/users", json=body, headers=h)
    assert r.status_code == 201, r.text
    login = client.post(f"{API}/auth/login", json={"email": body["email"], "password": r.json()["temp_password"]})
    assert login.status_code == 200 and login.json()["user"]["organization_id"] == fresh_org.id
    assert client.post(f"{API}/admin/users", json=body, headers=h).status_code == 409


def test_cannot_invite_super_admin_or_unknown_role(client, fresh_org):
    h = fresh_org.headers("org_admin")
    for role in ("super_admin", "root"):
        body = {"email": f"{role}@x.test", "full_name": "X", "role": role}
        assert client.post(f"{API}/admin/users", json=body, headers=h).status_code == 400


def test_role_change_takes_effect_immediately(client, fresh_org):
    h = fresh_org.headers("org_admin")
    uid = fresh_org.users["physician"]["id"]
    assert client.patch(f"{API}/admin/users/{uid}", json={"role": "auditor"}, headers=h).status_code == 200
    # токен физика ещё несёт старую роль, но проверяется роль из БД -> auditor не может считать
    from tests.integration.conftest import calc_body

    r = client.post(f"{API}/calculate", json=calc_body(), headers=fresh_org.headers("physician"))
    assert r.status_code in (401, 403)


def test_deactivate_user(client, fresh_org):
    h = fresh_org.headers("org_admin")
    uid = fresh_org.users["physician"]["id"]
    assert client.delete(f"{API}/admin/users/{uid}", headers=h).status_code == 204
    assert client.get(f"{API}/auth/me", headers=fresh_org.headers("physician")).status_code == 401


def test_cannot_remove_last_org_admin_or_self(client, fresh_org):
    h = fresh_org.headers("org_admin")
    me = fresh_org.users["org_admin"]["id"]
    assert client.patch(f"{API}/admin/users/{me}", json={"is_active": False}, headers=h).status_code == 409
    assert client.patch(f"{API}/admin/users/{me}", json={"role": "physician"}, headers=h).status_code == 409


def test_permissions_and_isolation(client, org_a, org_b):
    assert client.get(f"{API}/admin/users", headers=org_a.headers("pharmacist")).status_code == 403
    uid_a = org_a.users["physician"]["id"]
    r = client.patch(f"{API}/admin/users/{uid_a}", json={"is_active": False},
                     headers=org_b.headers("org_admin"))
    assert r.status_code == 404
    emails = {u["email"] for u in client.get(f"{API}/admin/users", headers=org_b.headers("org_admin")).json()}
    assert not any(e.endswith(f"@{org_a.code}.test") for e in emails)
