"""Формулы против вручную посчитанных reference-кейсов (ТЗ 4.1.3, 10.1)."""
import pytest

from app.clinical.formulas import (
    adjusted_body_weight,
    body_mass_index,
    ckd_epi_2021,
    cockcroft_gault,
    ideal_body_weight,
    interpret_renal_function,
)

# Cr 88.4 мкмоль/л == ровно 1.0 мг/дл, что упрощает ручной расчёт.
CR_1 = 88.4


# (age, weight, cr_umol, sex, expected)  expected = (140-age)*w/(72*cr_mgdl) [*0.85]
CG_CASES = [
    (45, 90, CR_1, "male", 95 * 90 / 72),
    (45, 90, CR_1, "female", 95 * 90 / 72 * 0.85),
    (70, 60, CR_1 * 2, "female", 70 * 60 / (72 * 2) * 0.85),
    (65, 70, CR_1 * 1.5, "male", 75 * 70 / (72 * 1.5)),
    (30, 80, CR_1 * 0.8, "male", 110 * 80 / (72 * 0.8)),
    (80, 55, CR_1 * 3, "female", 60 * 55 / (72 * 3) * 0.85),
    (18, 65, CR_1, "female", 122 * 65 / 72 * 0.85),
    (100, 50, CR_1, "male", 40 * 50 / 72),
    (55, 120, CR_1 * 4, "male", 85 * 120 / (72 * 4)),
    (40, 70, 884, "male", 100 * 70 / (72 * 10)),  # Cr 10 мг/дл
    (60, 75, 44.2, "female", 80 * 75 / (72 * 0.5) * 0.85),  # Cr 0.5 мг/дл
]


@pytest.mark.parametrize("age,weight,cr,sex,expected", CG_CASES)
def test_cockcroft_gault(age, weight, cr, sex, expected):
    assert cockcroft_gault(age, weight, cr, sex) == pytest.approx(expected, rel=1e-9)


# РЕГРЕССИОННЫЕ значения: числа зафиксированы по выводу реализации формулы из ТЗ 4.1.3,
# независимой сверки с эталоном (калькулятор NKF) не было.
# TODO: клинический фармаколог должен сверить кейсы с эталоном.
CKD_CASES = [
    (40, CR_1, "male", 97.6),
    (60, CR_1, "male", 86.0),
    (40, CR_1, "female", 74.0),   # SCr 1.0 > k=0.7
    (60, 70.72, "female", 84.3),  # SCr 0.8
    (70, 132.6, "male", 49.0),    # SCr 1.5
    (25, 53.04, "female", 128.0), # SCr 0.6 < k
    (50, 176.8, "male", 39.0),    # SCr 2.0
    (80, 265.2, "female", 15.0),  # SCr 3.0
    (30, 79.56, "male", 117.0),   # SCr 0.9 == k
    (65, 106.08, "male", 67.1),   # SCr 1.2
]


@pytest.mark.parametrize("age,cr,sex,expected", CKD_CASES)
def test_ckd_epi_2021_regression_values(age, cr, sex, expected):
    assert ckd_epi_2021(age, cr, sex) == pytest.approx(expected, abs=1.0)


def test_ckd_epi_2021_exact_male_k_boundary():
    # SCr == k: оба множителя ratio^x равны 1, остаётся 142 * 0.9938^age
    assert ckd_epi_2021(30, 0.9 * 88.4, "male") == pytest.approx(142 * 0.9938**30, rel=1e-9)


def test_ckd_epi_2021_female_factor():
    male_like = 142 * (1.0 / 0.7) ** -1.2 * 0.9938**40
    assert ckd_epi_2021(40, CR_1, "female") == pytest.approx(male_like * 1.012, rel=1e-9)


# Devine: рост в дюймах = cm/2.54
IBW_CASES = [
    (175, "male", 50 + 2.3 * (175 / 2.54 - 60)),
    (175, "female", 45.5 + 2.3 * (175 / 2.54 - 60)),
    (152.4, "male", 50.0),    # ровно 60 дюймов
    (152.4, "female", 45.5),
    (180, "male", 50 + 2.3 * (180 / 2.54 - 60)),
    (160, "female", 45.5 + 2.3 * (160 / 2.54 - 60)),
    (190, "male", 50 + 2.3 * (190 / 2.54 - 60)),
    (165, "female", 45.5 + 2.3 * (165 / 2.54 - 60)),
    (170, "male", 50 + 2.3 * (170 / 2.54 - 60)),
    (200, "male", 50 + 2.3 * (200 / 2.54 - 60)),
]


@pytest.mark.parametrize("height,sex,expected", IBW_CASES)
def test_ideal_body_weight(height, sex, expected):
    assert ideal_body_weight(height, sex) == pytest.approx(expected, rel=1e-9)


def test_ibw_known_value_175cm_male():
    assert ideal_body_weight(175, "male") == pytest.approx(70.47, abs=0.01)


def test_adjusted_body_weight():
    assert adjusted_body_weight(120, 70) == pytest.approx(90.0)
    assert adjusted_body_weight(100, 100) == pytest.approx(100.0)
    assert adjusted_body_weight(150, 60) == pytest.approx(96.0)


def test_bmi():
    assert body_mass_index(120, 175) == pytest.approx(39.18, abs=0.01)
    assert body_mass_index(70, 170) == pytest.approx(24.22, abs=0.01)


@pytest.mark.parametrize(
    "value,expected",
    [(95, "normal"), (90, "normal"), (75, "mild_impairment"), (45, "moderate_impairment"),
     (20, "severe_impairment"), (5, "kidney_failure")],
)
def test_interpretation(value, expected):
    assert interpret_renal_function(value) == expected
