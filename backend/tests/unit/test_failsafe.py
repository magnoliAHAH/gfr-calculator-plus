"""Fail-safe: все причины из ТЗ 4.1.4 + граничные случаи."""
import dataclasses

import pytest

from app.clinical.engine import calculate
from app.clinical.failsafe import FAILSAFE_DISPLAY, FailSafe
from app.clinical.types import CalcInput
from tests.unit.conftest import rules_for


def inp(**kw) -> CalcInput:
    base = dict(age_years=50, sex_at_birth="male", weight_kg=80, height_cm=175, creatinine_umol_l=88.4)
    base.update(kw)
    return CalcInput(**base)


def reason(rules, i) -> str:
    with pytest.raises(FailSafe) as e:
        calculate(rules, i)
    return e.value.reason


def test_no_active_rule():
    assert reason([], inp()) == "no_active_rule"


def test_age_below_min(vanco):
    assert reason(vanco, inp(age_years=17)) == "age_out_of_range"


def test_age_above_max():
    assert reason(rules_for("VANCO_IV", max_age_years=90), inp(age_years=95)) == "age_out_of_range"


def test_age_at_boundaries_ok(vanco):
    assert calculate(vanco, inp(age_years=18)).dose_mg > 0
    assert calculate(vanco, inp(age_years=120)).dose_mg > 0


def test_pregnancy_contraindicated():
    rules = rules_for("VANCO_IV", pregnancy_contraindicated=True)
    assert reason(rules, inp(pregnancy=True)) == "pregnancy_contraindicated"


def test_pregnancy_allowed_when_not_contraindicated(vanco):
    assert calculate(vanco, inp(sex_at_birth="female", pregnancy=True)).dose_mg > 0


def test_missing_height_for_ibw(colistin):
    assert reason(colistin, inp(height_cm=None)) == "missing_height_for_weight_rule"


def test_missing_creatinine(vanco):
    assert reason(vanco, inp(creatinine_umol_l=None)) == "missing_creatinine"


def test_missing_weight_for_cockcroft(vanco):
    assert reason(vanco, inp(weight_kg=None)) == "missing_weight"


def test_demo2_aki_failsafe(vanco):
    # 70 лет, Ж, 60 кг, CrCl ~25, AKI stage 2
    r = reason(vanco, inp(age_years=70, sex_at_birth="female", weight_kg=60, height_cm=None,
                          creatinine_umol_l=145, aki_stage="stage_2"))
    assert r == "severe_aki_requires_consult"


@pytest.mark.parametrize("stage,blocked", [("none", False), ("stage_1", False),
                                           ("stage_2", True), ("stage_3", True)])
def test_aki_default_limit_is_stage_1(vanco, stage, blocked):
    if blocked:
        assert reason(vanco, inp(aki_stage=stage)) == "severe_aki_requires_consult"
    else:
        assert calculate(vanco, inp(aki_stage=stage)).dose_mg > 0


def test_aki_limit_configurable():
    rules = rules_for("VANCO_IV", max_allowed_aki="stage_3")
    assert calculate(rules, inp(aki_stage="stage_3")).dose_mg > 0


def test_no_matching_bracket_gap():
    gap = [r for r in rules_for("VANCO_IV") if r.min_crcl != 30]  # убираем брекет 30–50
    i = inp(creatinine_umol_l=2.0 * 88.4, weight_kg=70, height_cm=None)  # CrCl ~39
    assert reason(gap, i) == "no_matching_bracket"


def test_rrt_not_supported(vanco):
    assert reason(vanco, inp(rrt_mode="hd")) == "rrt_mode_not_supported"


def test_unknown_rrt_mode(vanco):
    assert reason(vanco, inp(rrt_mode="weird")) == "rrt_mode_not_supported"


def test_rrt_rule_used_without_creatinine():
    rrt_rule = dataclasses.replace(
        rules_for("VANCO_IV")[0], id=99, rrt_mode="hd", min_crcl=None, max_crcl=None,
        dose_per_kg=None, dose_mg=750.0, frequency_hours=48,
    )
    rules = rules_for("VANCO_IV") + [rrt_rule]
    rec = calculate(rules, inp(rrt_mode="hd", creatinine_umol_l=None))
    assert rec.dose_mg == 750 and rec.frequency_hours == 48 and rec.renal_value is None
    assert any("RRT" in w for w in rec.warnings)


def test_fixed_dose_rule_with_ckd_epi_needs_no_weight():
    rule = dataclasses.replace(
        rules_for("VANCO_IV")[0], formula_code="ckd_epi_2021", dose_per_kg=None, dose_mg=500.0,
        min_crcl=0, max_crcl=200,
    )
    rec = calculate([rule], inp(weight_kg=None, height_cm=None))
    assert rec.weight is None and rec.dose_mg == 500
    assert rec.to_dict()["renal_function"]["unit"] == "mL/min/1.73m2"


def test_ecmo_gives_warning_not_failsafe(vanco):
    rec = calculate(vanco, inp(ecmo=True))
    assert any("ECMO" in w for w in rec.warnings)


def test_all_tz_reasons_have_display():
    required = {
        "age_out_of_range", "pregnancy_contraindicated", "missing_height_for_weight_rule",
        "missing_creatinine", "severe_aki_requires_consult", "no_matching_bracket",
        "rrt_mode_not_supported", "no_active_rule",
    }
    assert required <= set(FAILSAFE_DISPLAY)


def test_unknown_failsafe_reason_rejected():
    with pytest.raises(ValueError):
        FailSafe("bogus", "x")
