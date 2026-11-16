"""Админка: препараты (ТЗ 4.5.1)."""
from tests.integration.conftest import calc_body
from tests.integration.helpers import API


def drug_id(client, org, code="VANCO_IV"):
    rows = client.get(f"{API}/admin/drugs", headers=org.headers("org_admin")).json()
    return next(d["id"] for d in rows if d["drug_code"] == code)


def test_drug_crud_and_archive(client, fresh_org):
    h = fresh_org.headers("org_admin")
    body = {"drug_code": "MERO_IV", "drug_name": "Меропенем", "route": "IV", "rounding_step_mg": 100}
    r = client.post(f"{API}/admin/drugs", json=body, headers=h)
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert client.post(f"{API}/admin/drugs", json=body, headers=h).status_code == 409
    p = client.patch(f"{API}/admin/drugs/{did}", json={"drug_name": "Меропенем 1 г"}, headers=h)
    assert p.status_code == 200 and p.json()["drug_name"] == "Меропенем 1 г"
    assert client.delete(f"{API}/admin/drugs/{did}", headers=h).status_code == 204
    assert client.patch(f"{API}/admin/drugs/{did}", json={"drug_name": "x"}, headers=h).status_code == 409
    active = {d["drug_code"] for d in client.get(f"{API}/meta/drugs", headers=h).json()}
    assert "MERO_IV" not in active  # архивный не виден врачу
    archived = client.get(f"{API}/admin/drugs", headers=h).json()
    assert any(d["id"] == did and d["is_active"] is False for d in archived)  # но не удалён


def test_archived_drug_blocks_calculation(client, fresh_org):
    did = drug_id(client, fresh_org)
    client.delete(f"{API}/admin/drugs/{did}", headers=fresh_org.headers("org_admin"))
    r = client.post(f"{API}/calculate", json=calc_body(), headers=fresh_org.headers("physician"))
    assert r.status_code == 404


def test_drug_admin_permissions(client, fresh_org):
    body = {"drug_name": "X", "route": "IV"}
    for role, status in (("pharmacist", 403), ("physician", 403), ("auditor", 403), ("org_admin", 201)):
        r = client.post(f"{API}/admin/drugs", json=body | {"drug_code": f"X_{role}"},
                        headers=fresh_org.headers(role))
        assert r.status_code == status, role
    assert client.get(f"{API}/admin/drugs", headers=fresh_org.headers("pharmacist")).status_code == 200
    assert client.get(f"{API}/admin/drugs", headers=fresh_org.headers("physician")).status_code == 403


def test_cannot_touch_other_org_drug(client, org_a, org_b):
    did = drug_id(client, org_a)
    assert client.delete(f"{API}/admin/drugs/{did}", headers=org_b.headers("org_admin")).status_code == 404
    assert client.get(f"{API}/admin/drugs/{did}/rules", headers=org_b.headers("org_admin")).status_code == 404
