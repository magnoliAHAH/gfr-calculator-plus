"""Seed-данные: справочники и 3 препарата (ТЗ 4.1.5).

!!! ВСЕ КЛИНИЧЕСКИЕ ЗНАЧЕНИЯ ТРЕБУЮТ УТВЕРЖДЕНИЯ КЛИНИЧЕСКИМ ФАРМАКОЛОГОМ ДО ПИЛОТА !!!

Отклонения от ТЗ (подробнее в README):
  * rounding_step_mg ванкомицина/амикацина = 50 мг (в ТЗ по умолчанию 250), иначе demo-сценарии
    из ТЗ 4.7 (1350 мг, 1050 мг) недостижимы.
  * max_daily_dose_mg ванкомицина = None. В ТЗ указано 2000 мг/сут, но это противоречит
    demo-сценарию 1 (1350 мг q12h = 2700 мг/сут). VANCO_MAX_DAILY_MG_PER_TZ хранит значение из ТЗ.
  * Колистин, CrCl 50–80: «день 1 — 2.5 мг/кг, далее 1.9 мг/кг» моделируется через
    loading_dose_per_kg (новая колонка, в схеме ТЗ её нет).
"""
from __future__ import annotations

OVERRIDE_REASONS = [
    ("clinical_judgment", "Клиническое суждение", "clinical"),
    ("palliative", "Паллиативная цель", "clinical"),
    ("dialysis_schedule", "График диализа", "clinical"),
    ("pk_data", "Данные TDM/PK", "data"),
    ("mdr_pathogen", "MDR-возбудитель", "microbiology"),
    ("other", "Другое", "other"),
]

VANCO_MAX_DAILY_MG_PER_TZ = 2000.0  # не применяется в seed, см. docstring

DRUGS = [
    {
        "drug_code": "VANCO_IV",
        "drug_name": "Ванкомицин",
        "atc_code": "J01XA01",
        "route": "IV",
        "formulation": "порошок для инфузий",
        "rounding_step_mg": 50,
    },
    {
        "drug_code": "AMIKACIN_IV",
        "drug_name": "Амикацин",
        "atc_code": "J01GB06",
        "route": "IV",
        "formulation": "раствор для инфузий",
        "rounding_step_mg": 50,
    },
    {
        "drug_code": "COLISTIN_IV",
        "drug_name": "Колистин (CMS)",
        "atc_code": "J01XB01",
        "route": "IV",
        "formulation": "колистиметат натрия, дозы по CBA",
        "rounding_step_mg": 5,
    },
]

_INF = 999  # верхняя граница «CrCl >= X»; в схеме max_crcl NOT NULL и NUMERIC(6,2) (<= 9999.99)


def _brackets(drug, indication, weight_rule, source, tdm, rows, **common):
    out = []
    for min_c, max_c, per_kg, freq, *extra in rows:
        rule = {
            "drug_code": drug,
            "indication": indication,
            "formula_code": "cockcroft_gault",
            "weight_rule": weight_rule,
            "rrt_mode": "none",
            "min_crcl": min_c,
            "max_crcl": max_c,
            "dose_per_kg": per_kg,
            "frequency_hours": freq,
            "tdm_required": tdm,
            "source": source,
        }
        rule.update(common)
        if extra:
            rule.update(extra[0])
        out.append(rule)
    return out


RULES = (
    _brackets(
        "VANCO_IV", "sepsis_bacteremia", "auto", "IDSA 2020 Vancomycin Guidelines", True,
        [
            (50, _INF, 15, 12),
            (30, 50, 15, 24),
            (15, 30, 15, 48),
            (0, 15, 15, None),  # однократно, далее по уровню концентрации
        ],
        clinical_note="Контроль уровня ванкомицина в крови перед 4-й дозой.",
    )
    + _brackets(
        "AMIKACIN_IV", "sepsis_bacteremia", "auto", "Sanford Guide 2024", True,
        [
            (60, _INF, 15, 24),
            (40, 60, 15, 36),
            (20, 40, 15, 48),
            (0, 20, 15, None),
        ],
    )
    + _brackets(
        "COLISTIN_IV", "MDR_gram_negative", "ibw", "International Consensus 2019", True,
        [
            (80, _INF, 2.5, 12),
            (50, 80, 1.9, 12, {"loading_dose_per_kg": 2.5}),
            (30, 50, 1.9, 12),
            (10, 30, 1.25, 12),
            (0, 10, 1.25, 36),
        ],
        clinical_note="Дозы указаны в пересчёте на колистин-базу (CBA). TDM желателен.",
    )
)
