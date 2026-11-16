"""Дашборд метрик (ТЗ 4.6)."""
from tests.integration.helpers import API, calc, decide


def test_dashboard_metrics(client, fresh_org):
    a1 = calc(client, fresh_org)
    a2 = calc(client, fresh_org)
    a3 = calc(client, fresh_org)
    calc(client, fresh_org, creatinine_umol_l=None)  # fail-safe
    decide(client, fresh_org, a1, {"decision": "accepted"})
    decide(client, fresh_org, a2, {"decision": "overridden", "override_reason_category": "pk_data",
                                   "override_reason_text": "TDM данные"})
    decide(client, fresh_org, a3, {"decision": "contraindication_acknowledged",
                                   "override_reason_text": "Аллергия"})
    m = client.get(f"{API}/dashboard/metrics", headers=fresh_org.headers("org_admin")).json()
    rec = m["recommendations"]
    assert (rec["total"], rec["accepted"], rec["overridden"], rec["rejected"], rec["pending"]) == (4, 1, 1, 1, 1)
    assert rec["accepted_pct"] == 25.0
    assert m["failsafe_rate"] == 25.0
    assert m["override_reasons_top"] == [{"code": "pk_data", "count": 1, "percentage": 100.0}]
    assert m["drugs_top"][0]["code"] == "VANCO_IV" and m["drugs_top"][0]["count"] == 4
    assert sum(b["count"] for b in m["renal_function_histogram"]) == 3  # fail-safe без CrCl не считается
    assert m["audit_chain"]["valid"] is True and m["audit_chain"]["total_records"] == 7
    assert m["performance"]["p95_ms"] is not None and m["performance"]["p95_ms"] < 1500


def test_dashboard_empty_org_and_permissions(client, fresh_org):
    m = client.get(f"{API}/dashboard/metrics", headers=fresh_org.headers("auditor")).json()
    assert m["recommendations"]["total"] == 0 and m["failsafe_rate"] == 0.0
    assert m["audit_chain"]["valid"] is True
    assert client.get(f"{API}/dashboard/metrics", headers=fresh_org.headers("physician")).status_code == 403


def test_dashboard_is_tenant_isolated(client, org_a, org_b):
    calc(client, org_a)
    m = client.get(f"{API}/dashboard/metrics", headers=org_b.headers("org_admin")).json()
    assert m["recommendations"]["total"] == 0


def test_dashboard_period_filter_and_csv_export(client, fresh_org):
    calc(client, fresh_org)
    h = fresh_org.headers("pharmacist")
    old = client.get(f"{API}/dashboard/metrics",
                     params={"from": "2020-01-01T00:00:00Z", "to": "2020-02-01T00:00:00Z"}, headers=h).json()
    assert old["recommendations"]["total"] == 0
    r = client.get(f"{API}/dashboard/export", headers=h)
    assert r.status_code == 200 and "recommendations,total,1" in r.text
