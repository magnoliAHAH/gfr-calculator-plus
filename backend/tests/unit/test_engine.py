"""Клиническое ядро: округление, брекеты, demo-сценарии ТЗ 4.7, колистин, max daily dose."""
import pytest

from app.clinical.engine import calculate, find_bracket, floor_to_step, round_to_step
from app.clinical.types import CalcInput
from tests.unit.conftest import rules_for


def inp(**kw) -> CalcInput:
    base = dict(age_years=50, sex_at_birth="male", weight_kg=80, height_cm=175, creatinine_umol_l=88.4)
    base.update(kw)
    return CalcInput(**base)


# ---------- округление ----------

@pytest.mark.parametrize(
    "value,step,expected",
    [(1352.8, 50, 1350), (1375, 50, 1400), (1374.9, 50, 1350), (1050, 50, 1050),
     (100, 250, 0), (125, 250, 250), (1352.8, 0, 1352.8)],
)
def test_round_to_step(value, step, expected):
    assert round_to_step(value, step) == pytest.approx(expected)


def test_floor_to_step():
    assert floor_to_step(1000, 50) == 1000
    assert floor_to_step(1049.9, 50) == 1000
    assert floor_to_step(0.3 * 3 * 1000, 50) == 900  # защита от float-ошибок


# ---------- брекеты ----------

def test_bracket_lower_inclusive_upper_exclusive(vanco):
    assert find_bracket(vanco, 50).min_crcl == 50      # 50 -> верхний брекет
    assert find_bracket(vanco, 49.999).min_crcl == 30
    assert find_bracket(vanco, 30).min_crcl == 30
    assert find_bracket(vanco, 15).min_crcl == 15
    assert find_bracket(vanco, 14.99).min_crcl == 0
    assert find_bracket(vanco, 0).min_crcl == 0


def test_bracket_none_when_out_of_range(vanco):
    assert find_bracket(vanco, -1) is None
    assert find_bracket(vanco, 999) is None  # верхняя граница исключена


@pytest.mark.parametrize(
    "scr_mgdl,expected_freq",
    [(0.5, 12), (1.3, 12), (2.0, 24), (3.5, 48), (8.0, None)],
)
def test_vanco_frequency_by_renal_function(vanco, scr_mgdl, expected_freq):
    rec = calculate(vanco, inp(creatinine_umol_l=scr_mgdl * 88.4, weight_kg=70, height_cm=None))
    assert rec.frequency_hours == expected_freq


def test_single_dose_has_no_frequency(vanco):
    rec = calculate(vanco, inp(creatinine_umol_l=900, weight_kg=70, height_cm=None))
    d = rec.to_dict()["dose"]
    assert d["frequency_hours"] is None and d["single_dose"] is True


# ---------- demo-сценарии (ТЗ 4.7) ----------

def test_demo1_obesity_vanco_abw(vanco):
    # 45 лет, М, 120 кг, 175 см (BMI 39.2); Cr подобран так, чтобы CrCl ~95
    rec = calculate(vanco, inp(age_years=45, weight_kg=120, height_cm=175, creatinine_umol_l=110.7))
    d = rec.to_dict()
    assert d["weight"]["type"] == "ABW"
    assert d["weight"]["used_kg"] == pytest.approx(90.28, abs=0.01)
    assert d["weight"]["bmi"] == pytest.approx(39.2, abs=0.05)
    assert d["renal_function"]["value"] == pytest.approx(95.0, abs=0.6)
    assert d["dose"]["amount_mg"] == 1350
    assert d["dose"]["frequency_hours"] == 12
    assert d["tdm_required"] is True


def test_demo3_amikacin_renal_adjustment(amikacin):
    # 65 лет, М, 70 кг, CrCl ~25 (Cr 257.9)
    rec = calculate(amikacin, inp(age_years=65, weight_kg=70, height_cm=None, creatinine_umol_l=257.9))
    d = rec.to_dict()
    assert d["renal_function"]["value"] == pytest.approx(25.0, abs=0.2)
    assert d["dose"]["amount_mg"] == 1050
    assert d["dose"]["frequency_hours"] == 48


# ---------- колистин ----------

def test_colistin_uses_strict_ibw(colistin):
    rec = calculate(colistin, inp(weight_kg=120, height_cm=175, creatinine_umol_l=60))
    assert rec.weight.type == "IBW"
    assert rec.dose_mg == pytest.approx(2.5 * 70.47, abs=5)


def test_colistin_loading_dose_bracket(colistin):
    # CG: 40 лет, IBW 70.47, Cr 1.5 mg/dl -> 100*70.47/(72*1.5) = 65.2 -> брекет 50–80
    rec = calculate(colistin, inp(age_years=40, weight_kg=80, height_cm=175, creatinine_umol_l=1.5 * 88.4))
    assert rec.loading_dose_mg is not None
    assert rec.loading_dose_mg > rec.dose_mg
    assert any("Нагрузочная" in w for w in rec.warnings)


# ---------- max daily dose ----------

def test_max_daily_dose_caps_dose():
    rules = rules_for("VANCO_IV", max_daily_dose_mg=2000.0)
    rec = calculate(rules, inp(age_years=45, weight_kg=120, height_cm=175, creatinine_umol_l=110.7))
    assert rec.dose_mg == 1000  # 2000 мг/сут / 2 приёма
    assert rec.capped is True
    assert rec.to_dict()["dose"]["capped_by_max_daily"] is True


def test_max_daily_not_applied_when_below():
    rules = rules_for("VANCO_IV", max_daily_dose_mg=5000.0)
    rec = calculate(rules, inp(age_years=45, weight_kg=120, height_cm=175, creatinine_umol_l=110.7))
    assert rec.dose_mg == 1350 and rec.capped is False
