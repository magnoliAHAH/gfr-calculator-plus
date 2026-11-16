"""Общие хелперы интеграционных тестов."""
API = "/api/v1"


def calc(client, org, role="physician", **kw):
    from tests.integration.conftest import calc_body

    r = client.post(f"{API}/calculate", json=calc_body(**kw), headers=org.headers(role))
    assert r.status_code == 200, r.text
    return r.json()["audit_id"]


def decide(client, org, audit_id, body, role="physician"):
    return client.post(f"{API}/audit/{audit_id}/decision", json=body, headers=org.headers(role))
