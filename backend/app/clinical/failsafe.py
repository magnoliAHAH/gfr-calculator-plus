"""Причины fail-safe (раздел 4.1.4 ТЗ)."""
from __future__ import annotations

# Первые 8 — из ТЗ. Последние два добавлены дополнительно (см. README, «Отклонения от ТЗ»):
# missing_weight — вес не передан, а нужен; invalid_anthropometry — IBW <= 0 при заданном росте.
FAILSAFE_DISPLAY: dict[str, str] = {
    "age_out_of_range": "Возраст пациента вне допустимого диапазона для препарата",
    "pregnancy_contraindicated": "Препарат противопоказан при беременности",
    "missing_height_for_weight_rule": "Не указан рост, необходимый для расчёта веса",
    "missing_creatinine": "Не указан креатинин",
    "severe_aki_requires_consult": "Требуется консультация клинического фармаколога",
    "no_matching_bracket": "Для данной функции почек нет подходящего диапазона доз",
    "rrt_mode_not_supported": "Режим заместительной почечной терапии не поддерживается правилом",
    "no_active_rule": "Нет активного правила дозирования для препарата и показания",
    "missing_weight": "Не указан вес пациента",
    "invalid_anthropometry": "Антропометрия не позволяет рассчитать идеальный вес",
}


class FailSafe(Exception):
    """Расчёт заблокирован. Не ошибка системы — штатный клинический исход."""

    def __init__(self, reason: str, details: str):
        if reason not in FAILSAFE_DISPLAY:
            raise ValueError(f"Unknown fail-safe reason: {reason}")
        super().__init__(reason)
        self.reason = reason
        self.details = details

    @property
    def display(self) -> str:
        return FAILSAFE_DISPLAY[self.reason]
