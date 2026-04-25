from datetime import date

import pytest
from holidays import (
    Holiday,
    adjust_due_date,
    holiday_index,
    is_business_day,
    national_holidays,
    next_business_day,
)


class TestNationalHolidays:
    def test_includes_fixed_dates(self) -> None:
        index = holiday_index(2026)
        assert date(2026, 1, 1) in index
        assert date(2026, 4, 21) in index
        assert date(2026, 5, 1) in index
        assert date(2026, 9, 7) in index
        assert date(2026, 10, 12) in index
        assert date(2026, 11, 2) in index
        assert date(2026, 11, 15) in index
        assert date(2026, 12, 25) in index

    def test_easter_movable_holidays_2026(self) -> None:
        # Páscoa 2026 = 5 de abril
        index = holiday_index(2026)
        assert date(2026, 4, 3) in index   # Sexta-feira Santa
        assert date(2026, 2, 16) in index  # Carnaval segunda
        assert date(2026, 2, 17) in index  # Carnaval terça
        assert date(2026, 6, 4) in index   # Corpus Christi

    def test_easter_movable_holidays_2025(self) -> None:
        # Páscoa 2025 = 20 de abril
        index = holiday_index(2025)
        assert date(2025, 4, 18) in index  # Sexta-feira Santa
        assert date(2025, 3, 3) in index   # Carnaval segunda
        assert date(2025, 3, 4) in index   # Carnaval terça
        assert date(2025, 6, 19) in index  # Corpus Christi

    def test_consciencia_negra_only_from_2024(self) -> None:
        assert date(2023, 11, 20) not in holiday_index(2023)
        assert date(2024, 11, 20) in holiday_index(2024)
        assert date(2026, 11, 20) in holiday_index(2026)

    def test_bank_holidays_end_of_year(self) -> None:
        index = holiday_index(2026)
        assert index[date(2026, 12, 24)].kind == "bank"
        assert index[date(2026, 12, 31)].kind == "bank"

    def test_holidays_sorted_and_typed(self) -> None:
        holidays = national_holidays(2026)
        assert all(isinstance(h, Holiday) for h in holidays)
        assert list(holidays) == sorted(holidays, key=lambda h: h.date)


class TestIsBusinessDay:
    def test_weekday_is_business(self) -> None:
        assert is_business_day(date(2026, 3, 4))  # quarta-feira

    def test_saturday_not_business(self) -> None:
        assert not is_business_day(date(2026, 3, 7))  # sábado

    def test_sunday_not_business(self) -> None:
        assert not is_business_day(date(2026, 3, 8))  # domingo

    def test_holiday_not_business(self) -> None:
        assert not is_business_day(date(2026, 1, 1))
        assert not is_business_day(date(2026, 4, 21))

    def test_carnaval_not_business(self) -> None:
        assert not is_business_day(date(2026, 2, 16))
        assert not is_business_day(date(2026, 2, 17))


class TestNextBusinessDay:
    def test_already_business_day(self) -> None:
        assert next_business_day(date(2026, 3, 4)) == date(2026, 3, 4)

    def test_saturday_jumps_to_monday(self) -> None:
        assert next_business_day(date(2026, 3, 7)) == date(2026, 3, 9)

    def test_sunday_jumps_to_monday(self) -> None:
        assert next_business_day(date(2026, 3, 8)) == date(2026, 3, 9)

    def test_skips_holiday_then_weekend(self) -> None:
        # 1/1/2027 é sexta-feira (feriado) -> próxima útil é 4/1
        assert next_business_day(date(2027, 1, 1)) == date(2027, 1, 4)


class TestAdjustDueDate:
    def test_no_adjustment_on_business_day(self) -> None:
        adj = adjust_due_date(date(2026, 3, 4))
        assert adj.adjusted is False
        assert adj.effective == adj.original
        assert adj.reason is None

    def test_saturday_adjusted_to_monday(self) -> None:
        adj = adjust_due_date(date(2026, 3, 7))
        assert adj.adjusted is True
        assert adj.effective == date(2026, 3, 9)
        assert adj.reason == "weekend:saturday"

    def test_sunday_adjusted_to_monday(self) -> None:
        adj = adjust_due_date(date(2026, 3, 8))
        assert adj.adjusted is True
        assert adj.effective == date(2026, 3, 9)
        assert adj.reason == "weekend:sunday"

    def test_holiday_adjusted_with_named_reason(self) -> None:
        # 21/4/2026 é terça (Tiradentes)
        adj = adjust_due_date(date(2026, 4, 21))
        assert adj.adjusted is True
        assert adj.effective == date(2026, 4, 22)
        assert adj.reason is not None
        assert adj.reason.startswith("holiday:Tiradentes")

    def test_chained_holiday_and_weekend(self) -> None:
        # 24/12/2026 (qui) bancário -> 25 (sex) Natal -> 26 (sáb) -> 27 (dom)
        # próximo útil após 24/12/2026 é 28/12 (segunda)
        adj = adjust_due_date(date(2026, 12, 24))
        assert adj.effective == date(2026, 12, 28)
        assert adj.adjusted is True
        assert adj.reason is not None and adj.reason.startswith("holiday:Véspera de Natal")


@pytest.mark.parametrize(
    ("year", "expected_easter"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_easter_dates_via_movable_holidays(year: int, expected_easter: date) -> None:
    """Páscoa não é feriado, mas inferimos via Sexta-feira Santa = Páscoa - 2."""
    from datetime import timedelta

    index = holiday_index(year)
    sexta_santa = expected_easter - timedelta(days=2)
    assert sexta_santa in index
    assert "Sexta-feira Santa" in index[sexta_santa].name
