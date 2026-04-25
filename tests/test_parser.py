"""Testes para utilitários puros de agenda_parser.

Cobertura de parsing de XLSX será adicionada quando tivermos fixtures `.xlsx`
em tests/fixtures/. Por ora, focamos no que é testável sem planilha.
"""

from __future__ import annotations

import pytest
from agenda_parser import (
    PT_MONTH_LABELS,
    SCHEMA_VERSION,
    _agenda_period_from_url,
    _build_due_dates,
    _to_int,
)


class TestSchemaVersion:
    def test_is_1_1_0(self) -> None:
        assert SCHEMA_VERSION == "1.1.0"


class TestAgendaPeriodFromUrl:
    def test_extracts_year_and_month_from_marco(self) -> None:
        url = "https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/marco"
        assert _agenda_period_from_url(url) == (2026, 3)

    def test_extracts_with_trailing_slash(self) -> None:
        url = "https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/janeiro/"
        assert _agenda_period_from_url(url) == (2026, 1)

    def test_handles_accented_month(self) -> None:
        url = "https://exemplo.gov.br/agenda/2026/março"
        assert _agenda_period_from_url(url) == (2026, 3)

    def test_returns_none_for_unknown_month(self) -> None:
        url = "https://exemplo.gov.br/agenda/2026/foo"
        assert _agenda_period_from_url(url) is None

    def test_returns_none_for_empty(self) -> None:
        assert _agenda_period_from_url(None) is None
        assert _agenda_period_from_url("") is None

    def test_returns_none_for_url_without_period(self) -> None:
        assert _agenda_period_from_url("https://example.com/foo/bar") is None


class TestBuildDueDates:
    def test_business_day_no_adjustment(self) -> None:
        # 4/3/2026 é quarta-feira
        result = _build_due_dates(4, 2026, 3)
        assert result["due_date"] == "2026-03-04"
        assert result["effective_due_date"] == "2026-03-04"
        assert result["adjusted"] is False
        assert result["adjustment_reason"] is None

    def test_saturday_prorrogated_to_monday(self) -> None:
        # 7/3/2026 é sábado
        result = _build_due_dates(7, 2026, 3)
        assert result["due_date"] == "2026-03-07"
        assert result["effective_due_date"] == "2026-03-09"
        assert result["adjusted"] is True
        assert result["adjustment_reason"] == "weekend:saturday"

    def test_holiday_prorrogated(self) -> None:
        # 21/4/2026 é Tiradentes (terça)
        result = _build_due_dates(21, 2026, 4)
        assert result["effective_due_date"] == "2026-04-22"
        assert result["adjusted"] is True
        assert "Tiradentes" in (result["adjustment_reason"] or "")

    def test_zero_due_day_is_null(self) -> None:
        # Tributos diários têm due_day=0
        result = _build_due_dates(0, 2026, 3)
        assert result["due_date"] is None
        assert result["effective_due_date"] is None
        assert result["adjusted"] is False

    def test_none_due_day_is_null(self) -> None:
        result = _build_due_dates(None, 2026, 3)
        assert result["due_date"] is None

    def test_missing_period_returns_null(self) -> None:
        assert _build_due_dates(15, None, 3)["due_date"] is None
        assert _build_due_dates(15, 2026, None)["due_date"] is None

    def test_invalid_day_for_month(self) -> None:
        # 31/2 não existe
        result = _build_due_dates(31, 2026, 2)
        assert result["due_date"] is None
        assert result["effective_due_date"] is None


class TestPtMonthLabels:
    def test_all_months_present(self) -> None:
        assert len(PT_MONTH_LABELS) == 12
        assert PT_MONTH_LABELS[1] == "Janeiro"
        assert PT_MONTH_LABELS[12] == "Dezembro"


class TestToInt:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("", None),
            ("  ", None),
            (5, 5),
            (5.0, 5),
            ("5", 5),
            ("5,0", 5),
            ("Imediato", None),
        ],
    )
    def test_various_inputs(self, value: object, expected: int | None) -> None:
        assert _to_int(value) == expected
