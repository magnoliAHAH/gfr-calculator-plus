"""Multi-tenancy: изоляция организаций на уровне API и на уровне БД (ТЗ 4.4, 10.2)."""
import pytest
from sqlalchemy import text

from app.db import app_engine, tx
from tests.integration.conftest import calc_body, make_org
from tests.integration.helpers import API, calc, decide


def test_org_b_cannot_see_org_a_audit(client, org_a, org_b):
    aid = calc(client, org_a)
    assert client.get(f"{API}/audit/{aid}", headers=org_b.headers("org_admin")).status_code == 404
    lst = client.get(f"{API}/audit", headers=org_b.headers("org_admin")).json()
    assert aid not in [i["id"] for i in lst["items"]]
    assert client.get(f"{API}/audit/{aid}/verify", headers=org_b.headers("auditor")).status_code == 404
    assert decide(client, org_b, aid, {"decision": "accepted"}, role="org_admin").status_code == 404


def test_org_without_drugs_gets_404(client):
    empty = make_org(seed=False)
    r = client.post(f"{API}/calculate", json=calc_body(), headers=empty.headers("physician"))
    assert r.status_code == 404


def test_each_org_has_independent_chain(client):
    a, b = make_org(), make_org()
    ida = calc(client, a)
    idb = calc(client, b)
    ea = client.get(f"{API}/audit/{ida}", headers=a.headers("auditor")).json()
    eb = client.get(f"{API}/audit/{idb}", headers=b.headers("auditor")).json()
    genesis = "GENESIS_" + "0" * 56
    assert ea["prev_hash"] == genesis and eb["prev_hash"] == genesis  # у каждой организации своя цепочка
    assert client.get(f"{API}/audit/{ida}/verify", headers=a.headers("auditor")).json()["valid"] is True
    assert client.get(f"{API}/audit/{idb}/verify", headers=b.headers("auditor")).json()["valid"] is True


def test_rls_enforced_at_db_level_for_app_role(org_a, org_b):
    """Даже «забыв» WHERE organization_id, роль приложения не видит чужие строки."""
    with tx(org_a.id) as conn:
        orgs = {r[0] for r in conn.execute(text("SELECT DISTINCT organization_id FROM drugs"))}
        assert orgs == {org_a.id}
        assert conn.execute(text("SELECT count(*) FROM users WHERE organization_id = :o"),
                            {"o": org_b.id}).scalar_one() == 0


def test_rls_denies_everything_without_tenant_context(org_a):
    with app_engine().begin() as conn:  # app.organization_id не задан
        assert conn.execute(text("SELECT count(*) FROM drugs")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar_one() == 0


def test_rls_blocks_insert_into_foreign_org(org_a, org_b):
    with pytest.raises(Exception, match="row-level security"):
        with tx(org_a.id) as conn:
            conn.execute(text("INSERT INTO drugs (organization_id, drug_code, drug_name, route) "
                              "VALUES (:o, 'X', 'X', 'IV')"), {"o": org_b.id})


def test_app_role_has_no_bypass(org_a):
    with app_engine().connect() as conn:
        bypass = conn.execute(text("SELECT rolbypassrls OR rolsuper FROM pg_roles "
                                   "WHERE rolname = current_user")).scalar_one()
    assert bypass is False


def test_tenant_context_does_not_leak_between_transactions(org_a, org_b):
    with tx(org_a.id) as conn:
        assert conn.execute(text("SELECT count(*) FROM drugs")).scalar_one() > 0
    with app_engine().begin() as conn:  # тот же пул, новая транзакция без контекста
        assert conn.execute(text("SELECT count(*) FROM drugs")).scalar_one() == 0


def test_app_role_cannot_modify_audit_or_rules(org_a):
    with pytest.raises(Exception):
        with tx(org_a.id) as conn:
            conn.execute(text("UPDATE audit_log SET patient_ref = 'x'"))
    with pytest.raises(Exception):
        with tx(org_a.id) as conn:
            conn.execute(text("UPDATE dosage_rules SET dose_per_kg = 99"))
