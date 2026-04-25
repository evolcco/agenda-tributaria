"""Feriados nacionais e regra de dia útil para vencimentos da RFB.

Regra padrão (Lei 9.430/96, art. 18): vencimento de tributo federal que cai em
dia sem expediente bancário é PRORROGADO para o primeiro dia útil seguinte.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache


@dataclass(frozen=True)
class Holiday:
    date: date
    name: str
    kind: str


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=32)
def national_holidays(year: int) -> tuple[Holiday, ...]:
    """Feriados nacionais + bancários relevantes para vencimentos federais.

    Inclui Carnaval, Sexta-feira Santa, Corpus Christi (móveis) e
    24/12 e 31/12 (sem expediente bancário pela ANBIMA).

    Consciência Negra (20/11) é nacional desde 2024 (Lei 14.759/2023).
    """
    easter = _easter_sunday(year)

    holidays = [
        Holiday(date(year, 1, 1), "Confraternização Universal", "fixed"),
        Holiday(easter - timedelta(days=48), "Carnaval (segunda)", "movable"),
        Holiday(easter - timedelta(days=47), "Carnaval (terça)", "movable"),
        Holiday(easter - timedelta(days=2), "Sexta-feira Santa", "movable"),
        Holiday(date(year, 4, 21), "Tiradentes", "fixed"),
        Holiday(date(year, 5, 1), "Dia do Trabalho", "fixed"),
        Holiday(easter + timedelta(days=60), "Corpus Christi", "movable"),
        Holiday(date(year, 9, 7), "Independência", "fixed"),
        Holiday(date(year, 10, 12), "Nossa Senhora Aparecida", "fixed"),
        Holiday(date(year, 11, 2), "Finados", "fixed"),
        Holiday(date(year, 11, 15), "Proclamação da República", "fixed"),
        Holiday(date(year, 12, 25), "Natal", "fixed"),
        Holiday(date(year, 12, 24), "Véspera de Natal (sem expediente bancário)", "bank"),
        Holiday(date(year, 12, 31), "Véspera de Ano Novo (sem expediente bancário)", "bank"),
    ]

    if year >= 2024:
        holidays.append(Holiday(date(year, 11, 20), "Consciência Negra", "fixed"))

    return tuple(sorted(holidays, key=lambda h: h.date))


def holiday_index(year: int) -> dict[date, Holiday]:
    return {h.date: h for h in national_holidays(year)}


def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:  # 5=sábado, 6=domingo
        return False
    return d not in holiday_index(d.year)


def next_business_day(d: date) -> date:
    cur = d
    while not is_business_day(cur):
        cur = cur + timedelta(days=1)
    return cur


@dataclass(frozen=True)
class Adjustment:
    original: date
    effective: date
    adjusted: bool
    reason: str | None


def adjust_due_date(d: date) -> Adjustment:
    """Aplica a regra de prorrogação da Lei 9.430/96 art. 18."""
    if is_business_day(d):
        return Adjustment(original=d, effective=d, adjusted=False, reason=None)

    effective = next_business_day(d)
    if d.weekday() == 5:
        reason = "weekend:saturday"
    elif d.weekday() == 6:
        reason = "weekend:sunday"
    else:
        holiday = holiday_index(d.year).get(d)
        reason = f"holiday:{holiday.name}" if holiday else "holiday:unknown"

    return Adjustment(original=d, effective=effective, adjusted=True, reason=reason)
