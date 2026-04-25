from datetime import UTC, datetime

import pytest
from generate_ics import (
    LINE_LIMIT,
    _escape,
    _fold_line,
    _format_date,
    _make_uid,
    build_ics,
)


class TestEscape:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("simples", "simples"),
            ("com,vírgula", "com\\,vírgula"),
            ("com;ponto e vírgula", "com\\;ponto e vírgula"),
            ("com\\barra", "com\\\\barra"),
            ("linha\nnova", "linha\\nnova"),
            ("crlf\r\nstyle", "crlf\\nstyle"),
        ],
    )
    def test_escapes_special_chars(self, raw: str, expected: str) -> None:
        assert _escape(raw) == expected


class TestFoldLine:
    def test_short_line_unchanged(self) -> None:
        line = "BEGIN:VEVENT"
        assert _fold_line(line) == line

    def test_long_line_folded(self) -> None:
        line = "DESCRIPTION:" + ("x" * 200)
        folded = _fold_line(line)
        for chunk in folded.split("\r\n"):
            assert len(chunk.encode("utf-8")) <= LINE_LIMIT + 1  # +1 para o leading space

    def test_continuation_lines_start_with_space(self) -> None:
        folded = _fold_line("X" * 300)
        chunks = folded.split("\r\n")
        for chunk in chunks[1:]:
            assert chunk.startswith(" ")


class TestFormatDate:
    def test_iso_string(self) -> None:
        assert _format_date("2026-03-04") == "20260304"

    def test_date_object(self) -> None:
        from datetime import date

        assert _format_date(date(2026, 3, 4)) == "20260304"


class TestMakeUid:
    def test_stable_for_same_input(self) -> None:
        a = _make_uid("agenda-2026-03", "T-0001")
        b = _make_uid("agenda-2026-03", "T-0001")
        assert a == b
        assert a.endswith("@agenda-tributaria")

    def test_different_for_different_files(self) -> None:
        a = _make_uid("agenda-2026-03", "T-0001")
        b = _make_uid("agenda-2026-04", "T-0001")
        assert a != b


class TestBuildIcs:
    def _payload(self) -> dict:
        return {
            "agenda": {"year": 2026, "month": 3, "label": "Março/2026"},
            "tributos": [
                {
                    "id": "T-0001",
                    "code": 1150,
                    "group": "IOF",
                    "description": "Operações de Crédito",
                    "apuration_period": "fev/2026",
                    "periodicity": "Decendial",
                    "payment_document": "DARF",
                    "due_date": "2026-03-04",
                    "effective_due_date": "2026-03-04",
                    "adjusted": False,
                    "adjustment_reason": None,
                },
                {
                    "id": "T-0002",
                    "code": 9999,
                    "group": "IRRF",
                    "description": "Trabalho assalariado",
                    "due_date": "2026-03-07",
                    "effective_due_date": "2026-03-09",
                    "adjusted": True,
                    "adjustment_reason": "weekend:saturday",
                },
                {
                    "id": "T-0003",
                    "due_type": "daily",
                    "due_day": 0,
                    "effective_due_date": None,
                },
            ],
            "declaracoes": [
                {
                    "id": "D-0001",
                    "interested": "PJ Lucro Real",
                    "description": "DCTFWeb",
                    "reference_period": "fev/2026",
                    "legal_basis": "IN RFB 2.005/2021",
                    "due_date": "2026-03-15",
                    "effective_due_date": "2026-03-16",
                    "adjusted": True,
                    "adjustment_reason": "weekend:sunday",
                },
            ],
        }

    def test_envelope_present(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert ics.startswith("BEGIN:VCALENDAR\r\n")
        assert ics.endswith("END:VCALENDAR\r\n")
        assert "VERSION:2.0" in ics
        assert "PRODID:-//agenda-tributaria//PT-BR//" in ics

    def test_calname_uses_agenda_label(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert "X-WR-CALNAME:Agenda Tributária — Março/2026" in ics

    def test_skips_items_without_effective_due_date(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert ics.count("BEGIN:VEVENT") == 3  # 2 tributos + 1 declaração; o diário fica fora

    def test_includes_alarm(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert "BEGIN:VALARM" in ics
        assert "TRIGGER:-P2D" in ics
        assert "ACTION:DISPLAY" in ics

    def test_dtend_is_day_after_dtstart(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert "DTSTART;VALUE=DATE:20260304" in ics
        assert "DTEND;VALUE=DATE:20260305" in ics

    def test_categories_set(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert "CATEGORIES:Tributo" in ics
        assert "CATEGORIES:Declaração" in ics

    def test_adjusted_event_includes_warning_in_description(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        # desdobra linhas dobradas (CRLF + espaço) antes de procurar
        unfolded = ics.replace("\r\n ", "")
        assert "prorrogado" in unfolded
        assert "weekend:saturday" in unfolded

    def test_summary_uses_group_and_code(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        assert "SUMMARY:IOF (1150)" in ics

    def test_dtstamp_present_and_utc(self) -> None:
        now = datetime(2026, 3, 6, 19, 5, 31, tzinfo=UTC)
        ics = build_ics(self._payload(), file_stem="agenda-2026-03", now=now)
        assert "DTSTAMP:20260306T190531Z" in ics

    def test_uses_crlf_line_endings(self) -> None:
        ics = build_ics(self._payload(), file_stem="agenda-2026-03")
        # RFC 5545 exige CRLF
        assert "\r\n" in ics
        # Não deve ter LF "solto" (sem CR antes)
        assert "\n" not in ics.replace("\r\n", "")
