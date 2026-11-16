"""Стратегии выбора веса: все ветки (ТЗ 4.1.2 шаг 3, 10.1)."""
import pytest

from app.clinical.failsafe import FailSafe
from app.clinical.weights import select_weight


def test_tbw_uses_actual_weight():
    w = select_weight("tbw", 80, None, "male")
    assert (w.type, w.used_kg, w.ibw_kg, w.bmi) == ("TBW", 80, None, None)


def test_tbw_requires_weight():
    with pytest.raises(FailSafe) as e:
        select_weight("tbw", None, 175, "male")
    assert e.value.reason == "missing_weight"


@pytest.mark.parametrize("rule", ["ibw", "abw"])
def test_ibw_abw_require_height(rule):
    with pytest.raises(FailSafe) as e:
        select_weight(rule, 80, None, "male")
    assert e.value.reason == "missing_height_for_weight_rule"


def test_ibw_strict_even_if_actual_is_lower():
    # Колистин: строго IBW (175 см, муж. -> ~70.47 кг), хотя пациент весит 50 кг
    w = select_weight("ibw", 50, 175, "male")
    assert w.type == "IBW"
    assert w.used_kg == pytest.approx(70.47, abs=0.01)
    assert w.tbw_kg == 50


def test_ibw_works_without_weight():
    w = select_weight("ibw", None, 175, "male")
    assert w.type == "IBW" and w.tbw_kg is None and w.bmi is None


def test_abw_formula():
    w = select_weight("abw", 120, 175, "male")
    ibw = w.ibw_kg
    assert w.type == "ABW"
    assert w.used_kg == pytest.approx(ibw + 0.4 * (120 - ibw))


def test_abw_requires_weight():
    with pytest.raises(FailSafe) as e:
        select_weight("abw", None, 175, "male")
    assert e.value.reason == "missing_weight"


def test_auto_without_height_falls_back_to_tbw():
    w = select_weight("auto", 80, None, "male")
    assert w.type == "TBW" and w.used_kg == 80


def test_auto_obese_uses_abw():
    w = select_weight("auto", 120, 175, "male")  # BMI 39.2
    assert w.type == "ABW"
    assert w.bmi == pytest.approx(39.18, abs=0.01)
    assert w.used_kg == pytest.approx(90.28, abs=0.01)


def test_auto_bmi_exactly_30_is_obese():
    height = 170
    weight = 30 * (height / 100) ** 2  # BMI ровно 30
    assert select_weight("auto", weight, height, "male").type == "ABW"


def test_auto_just_below_30_not_abw():
    height = 170
    weight = 29.9 * (height / 100) ** 2
    assert select_weight("auto", weight, height, "male").type != "ABW"


def test_auto_underweight_uses_tbw():
    # 175 см муж. IBW ~70.47; пациент 60 кг (BMI 19.6) -> фактический вес
    w = select_weight("auto", 60, 175, "male")
    assert w.type == "TBW" and w.used_kg == 60


def test_auto_normal_above_ibw_uses_ibw():
    # 175 см, 80 кг: BMI 26.1, вес > IBW -> IBW
    w = select_weight("auto", 80, 175, "male")
    assert w.type == "IBW" and w.used_kg == pytest.approx(70.47, abs=0.01)


def test_auto_weight_equal_ibw_uses_ibw():
    ibw = select_weight("ibw", None, 175, "male").used_kg
    assert select_weight("auto", ibw, 175, "male").type == "IBW"


def test_auto_requires_weight():
    with pytest.raises(FailSafe) as e:
        select_weight("auto", None, 175, "male")
    assert e.value.reason == "missing_weight"


def test_female_ibw_lower_than_male():
    m = select_weight("ibw", None, 170, "male").used_kg
    f = select_weight("ibw", None, 170, "female").used_kg
    assert m - f == pytest.approx(4.5)


def test_invalid_anthropometry_when_ibw_not_positive():
    with pytest.raises(FailSafe) as e:
        select_weight("ibw", 50, 100, "female")  # 100 см -> IBW < 0
    assert e.value.reason == "invalid_anthropometry"


def test_unknown_rule_raises_value_error():
    with pytest.raises(ValueError):
        select_weight("nope", 80, 175, "male")
