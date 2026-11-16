"""Клиническое ядро: алгоритм из раздела 4.1.2 ТЗ.

Модуль не знает про БД и HTTP. На вход — список активных правил (RuleData) и CalcInput,
на выход — Recommendation либо исключение FailSafe. Аудит (шаг 8) делает вызывающий слой.
"""
from __future__ import annotations

import math

from app.clinical.failsafe import FailSafe
from app.clinical.formulas import FORMULAS, compute_renal_function
from app.clinical.types import AKI_ORDER, SUPPORTED_RRT, CalcInput, Recommendation, RuleData
from app.clinical.weights import WeightResult, select_weight

_EPS = 1e-9


def round_to_step(value: float, step: float) -> float:
    """Округление до ближайшего кратного step (середина — вверх)."""
    if step <= 0:
        return value
    return math.floor(value / step + 0.5 + _EPS) * step


def floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor(value / step + _EPS) * step


def _by_min_crcl(rules: list[RuleData]) -> list[RuleData]:
    return sorted(rules, key=lambda r: r.min_crcl if r.min_crcl is not None else float("-inf"))


def find_bracket(rules: list[RuleData], renal_value: float) -> RuleData | None:
    """Брекет: min_crcl <= value < max_crcl (нижняя граница включительно, верхняя нет)."""
    for rule in _by_min_crcl(rules):
        if rule.min_crcl is None or rule.max_crcl is None:
            continue
        if rule.min_crcl <= renal_value < rule.max_crcl:
            return rule
    return None


def _validate_patient(rule: RuleData, inp: CalcInput) -> None:
    if inp.age_years < rule.min_age_years or inp.age_years > rule.max_age_years:
        raise FailSafe(
            "age_out_of_range",
            f"Возраст {inp.age_years:g} лет вне диапазона {rule.min_age_years}–{rule.max_age_years} "
            "для данного правила.",
        )
    if inp.pregnancy and rule.pregnancy_contraindicated:
        raise FailSafe("pregnancy_contraindicated", "Препарат противопоказан при беременности.")


def calculate(rules: list[RuleData], inp: CalcInput) -> Recommendation:
    """Шаги 1–7 алгоритма. `rules` — все активные правила для (препарат, показание, организация)."""
    # 1. Активные правила
    if not rules:
        raise FailSafe("no_active_rule", "Для препарата и показания нет активного правила.")

    # 6 (часть). Правила нужного RRT-режима
    if inp.rrt_mode not in SUPPORTED_RRT:
        raise FailSafe("rrt_mode_not_supported", f"Неизвестный режим RRT: {inp.rrt_mode}.")
    mode_rules = [r for r in rules if r.rrt_mode == inp.rrt_mode]
    if not mode_rules:
        if inp.rrt_mode == "none":
            raise FailSafe("no_matching_bracket", "Нет правил для пациента без RRT.")
        raise FailSafe(
            "rrt_mode_not_supported",
            f"Для режима RRT «{inp.rrt_mode}» у препарата нет правила.",
        )
    # Формула, правило веса, возрастные и AKI-ограничения общие для группы брекетов:
    # берём их из брекета с наименьшим min_crcl.
    ref = _by_min_crcl(mode_rules)[0]

    # 2. Возраст / беременность. ECMO в ТЗ не имеет fail-safe причины — даёт предупреждение.
    _validate_patient(ref, inp)

    # 5. AKI (проверяем до тяжёлых расчётов — результат всё равно был бы заблокирован)
    if AKI_ORDER[inp.aki_stage] > AKI_ORDER[ref.max_allowed_aki]:
        raise FailSafe(
            "severe_aki_requires_consult",
            f"У пациента AKI {inp.aki_stage}, максимально допустимо для правила: "
            f"{ref.max_allowed_aki}. Дозирование требует индивидуального подхода.",
        )

    formula = FORMULAS[ref.formula_code]
    needs_weight = formula.requires_weight or any(r.dose_per_kg is not None for r in mode_rules)

    # 3. Вес
    weight: WeightResult | None = None
    if needs_weight:
        weight = select_weight(ref.weight_rule, inp.weight_kg, inp.height_cm, inp.sex_at_birth)

    # 4. Почечная метрика. При RRT не считается: брекет определяется режимом.
    renal_value: float | None = None
    bracket = ref
    if inp.rrt_mode == "none":
        if inp.creatinine_umol_l is None:
            raise FailSafe("missing_creatinine", "Для расчёта функции почек необходим креатинин.")
        renal_value = compute_renal_function(
            ref.formula_code,
            inp.age_years,
            weight.used_kg if weight else inp.weight_kg,
            inp.creatinine_umol_l,
            inp.sex_at_birth,
        )
        # 6. Брекет
        bracket = find_bracket(mode_rules, renal_value)
        if bracket is None:
            raise FailSafe(
                "no_matching_bracket",
                f"Для значения {renal_value:.1f} {formula.output_unit} нет подходящего диапазона.",
            )

    # 7. Доза
    return _build_dose(bracket, weight, renal_value, inp)


def _build_dose(
    rule: RuleData, weight: WeightResult | None, renal_value: float | None, inp: CalcInput
) -> Recommendation:
    step = rule.rounding_step_mg
    warnings: list[str] = []

    if rule.dose_mg is not None:
        raw = rule.dose_mg
    else:
        if weight is None:
            raise FailSafe("missing_weight", "Для расчёта дозы необходим вес пациента.")
        raw = rule.dose_per_kg * weight.used_kg
    dose = round_to_step(raw, step)

    capped = False
    if rule.max_daily_dose_mg is not None:
        doses_per_day = 24 / rule.frequency_hours if rule.frequency_hours else 1
        if dose * doses_per_day > rule.max_daily_dose_mg + _EPS:
            dose = floor_to_step(rule.max_daily_dose_mg / doses_per_day, step)
            capped = True
            warnings.append(
                f"Доза ограничена максимальной суточной дозой {rule.max_daily_dose_mg:g} мг."
            )

    loading = None
    if rule.loading_dose_per_kg is not None and weight is not None:
        loading = round_to_step(rule.loading_dose_per_kg * weight.used_kg, step)
        warnings.append(f"Нагрузочная доза в первые сутки: {loading:g} мг.")

    if rule.tdm_required:
        warnings.append("Требуется контроль концентрации препарата (TDM).")
    if inp.ecmo:
        warnings.append("Пациент на ECMO: фармакокинетика может отличаться, оцените дозу клинически.")
    if inp.rrt_mode != "none":
        warnings.append(f"Доза подобрана для режима RRT: {inp.rrt_mode}.")
    if rule.clinical_note:
        warnings.append(rule.clinical_note)

    return Recommendation(
        rule=rule,
        weight=weight,
        renal_value=renal_value,
        dose_mg=dose,
        frequency_hours=rule.frequency_hours,
        loading_dose_mg=loading,
        capped=capped,
        warnings=warnings,
    )
