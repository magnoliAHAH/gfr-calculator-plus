"""CSV импорт/экспорт правил (ТЗ 4.5.2)."""
from tests.integration.conftest import calc_body
from tests.integration.helpers import API
from tests.integration.test_admin_drugs import drug_id

HEADER = "drug_code,indication,formula,weight_rule,min_crcl,max_crcl,dose_mg,frequency_hours,tdm,source"
GOOD_ROWS = (
    "VANCO_IV,sepsis_bacteremia,cockcroft_gault,tbw,0,50,,24,true,Local,10\n"
    "VANCO_IV,sepsis_bacteremia,cockcroft_gault,tbw,50,999,,12,false,Local,10\n"
)
GOOD = HEADER + ",dose_per_kg\n" + GOOD_ROWS


def upload(client, org, content: str, role="pharmacist"):
    return client.post(f"{API}/admin/rules/import", headers=org.headers(role),
                       files={"file": ("rules.csv", content.encode("utf-8"), "text/csv")})


def physician_calc(client, org):
    return client.post(f"{API}/calculate", json=calc_body(), headers=org.headers("physician")).json()


def test_import_creates_new_version_and_affects_calculation(client, fresh_org):
    r = upload(client, fresh_org, GOOD)
    assert r.status_code == 201, r.text
    assert r.json()["imported"][0]["version"] == 2
    d = physician_calc(client, fresh_org)
    assert d["rule_version"] == 2 and d["dose"]["amount_mg"] == 1200


def test_export_contains_active_rules_and_round_trips(client, fresh_org):
    did = drug_id(client, fresh_org)
    r = client.get(f"{API}/admin/rules/export", params={"drug_id": did},
                   headers=fresh_org.headers("pharmacist"))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().split("\n")
    assert lines[0].startswith("drug_code,indication,formula,weight_rule,min_crcl,max_crcl,dose_mg")
    assert len(lines) == 1 + 4 and all(line.startswith("VANCO_IV") for line in lines[1:])
    again = upload(client, fresh_org, r.text)  # экспорт можно импортировать обратно
    assert again.status_code == 201, again.text
    d = physician_calc(client, fresh_org)
    assert d["rule_version"] == 2 and d["dose"]["amount_mg"] == 1350  # те же значения


def test_import_is_atomic_on_errors(client, fresh_org):
    bad = GOOD + "NO_SUCH_DRUG,x,cockcroft_gault,tbw,0,50,,24,true,Local,10\n"
    assert upload(client, fresh_org, bad).status_code == 400
    assert physician_calc(client, fresh_org)["rule_version"] == 1  # ничего не импортировано


def test_import_reports_row_numbers(client, fresh_org):
    bad = HEADER + ",dose_per_kg\nVANCO_IV,s,cockcroft_gault,tbw,50,10,,24,true,L,10\n"
    r = upload(client, fresh_org, bad)
    assert r.status_code == 400
    assert r.json()["errors"][0]["row"] == 2


def test_import_rejects_missing_columns_non_utf8_and_empty(client, fresh_org):
    assert upload(client, fresh_org, "drug_code,indication\nA,B\n").status_code == 400
    assert upload(client, fresh_org, HEADER + "\n").status_code == 400
    r = client.post(f"{API}/admin/rules/import", headers=fresh_org.headers("pharmacist"),
                    files={"file": ("r.csv", "привет".encode("cp1251"), "text/csv")})
    assert r.status_code == 400


def test_import_permissions(client, fresh_org):
    for role in ("physician", "auditor"):
        assert upload(client, fresh_org, GOOD, role=role).status_code == 403


def test_export_neutralizes_formula_injection():
    from app.rules_csv import render_csv

    out = render_csv([{"drug_code": "A", "indication": "i", "formula_code": "f", "weight_rule": "tbw",
                       "source": "=HYPERLINK(1)", "clinical_note": "@x", "tdm_required": False}])
    assert "'=HYPERLINK(1)" in out and "'@x" in out
