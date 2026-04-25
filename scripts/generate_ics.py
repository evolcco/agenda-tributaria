"""Gera arquivo .ics (RFC 5545) a partir de um agenda-YYYY-MM.json.

Cada item com `effective_due_date` vira um VEVENT all-day, com VALARM 2 dias antes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

PRODID = "-//agenda-tributaria//PT-BR//"
ALARM_DAYS_BEFORE = 2
LINE_LIMIT = 75


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold_line(line: str) -> str:
    """Dobra linhas longas conforme RFC 5545 §3.1 (CRLF + espaço a cada 75 octetos)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= LINE_LIMIT:
        return line

    parts: list[bytes] = []
    cursor = 0
    while cursor < len(encoded):
        chunk = encoded[cursor : cursor + LINE_LIMIT]
        parts.append(chunk)
        cursor += LINE_LIMIT

    decoded_parts = [parts[0].decode("utf-8", errors="ignore")]
    for chunk in parts[1:]:
        decoded_parts.append(" " + chunk.decode("utf-8", errors="ignore"))
    return "\r\n".join(decoded_parts)


def _format_date(value: str | date) -> str:
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.strftime("%Y%m%d")


def _format_dtstamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _make_uid(file_stem: str, item_id: str) -> str:
    digest = hashlib.sha1(f"{file_stem}:{item_id}".encode()).hexdigest()[:12]
    return f"{item_id}-{digest}@agenda-tributaria"


def _tributo_summary(item: dict[str, Any]) -> str:
    code = item.get("code")
    group = item.get("group") or "Tributo"
    if code:
        return f"{group} ({code})"
    return group


def _declaracao_summary(item: dict[str, Any]) -> str:
    desc = item.get("description") or "Declaração"
    return desc[:80]


def _tributo_description(item: dict[str, Any]) -> str:
    parts = [
        item.get("description"),
        f"Período de apuração: {item.get('apuration_period')}" if item.get("apuration_period") else None,
        f"Periodicidade: {item.get('periodicity')}" if item.get("periodicity") else None,
        f"Documento: {item.get('payment_document')}" if item.get("payment_document") else None,
    ]
    if item.get("adjusted"):
        parts.append(
            f"⚠️ Vencimento original {item['due_date']} prorrogado ({item.get('adjustment_reason')})"
        )
    return "\n".join(p for p in parts if p)


def _declaracao_description(item: dict[str, Any]) -> str:
    parts = [
        f"Interessado: {item.get('interested')}" if item.get("interested") else None,
        f"Período de referência: {item.get('reference_period')}" if item.get("reference_period") else None,
        f"Base normativa: {item.get('legal_basis')}" if item.get("legal_basis") else None,
    ]
    if item.get("adjusted"):
        parts.append(
            f"⚠️ Prazo original {item['due_date']} prorrogado ({item.get('adjustment_reason')})"
        )
    return "\n".join(p for p in parts if p)


def _build_event(
    *,
    file_stem: str,
    item: dict[str, Any],
    summary: str,
    description: str,
    category: str,
    dtstamp: datetime,
) -> list[str]:
    effective = item.get("effective_due_date")
    if not effective:
        return []

    start_date = date.fromisoformat(effective)
    start_str = _format_date(start_date)
    end_str = _format_date(start_date + timedelta(days=1))
    uid = _make_uid(file_stem, item.get("id") or summary)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_format_dtstamp(dtstamp)}",
        f"DTSTART;VALUE=DATE:{start_str}",
        f"DTEND;VALUE=DATE:{end_str}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"CATEGORIES:{category}",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"TRIGGER:-P{ALARM_DAYS_BEFORE}D",
        f"DESCRIPTION:{_escape(f'Vencimento em {ALARM_DAYS_BEFORE} dias: {summary}')}",
        "END:VALARM",
        "END:VEVENT",
    ]
    return [_fold_line(line) for line in lines]


def build_ics(payload: dict[str, Any], *, file_stem: str, now: datetime | None = None) -> str:
    dtstamp = now or datetime.now(UTC)

    agenda = payload.get("agenda") or {}
    label = agenda.get("label") or "Agenda Tributária"
    name = f"Agenda Tributária — {label}"

    body: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        "X-WR-TIMEZONE:America/Sao_Paulo",
    ]

    for item in payload.get("tributos", []):
        body.extend(
            _build_event(
                file_stem=file_stem,
                item=item,
                summary=_tributo_summary(item),
                description=_tributo_description(item),
                category="Tributo",
                dtstamp=dtstamp,
            )
        )

    for item in payload.get("declaracoes", []):
        body.extend(
            _build_event(
                file_stem=file_stem,
                item=item,
                summary=_declaracao_summary(item),
                description=_declaracao_description(item),
                category="Declaração",
                dtstamp=dtstamp,
            )
        )

    body.append("END:VCALENDAR")
    return "\r\n".join(body) + "\r\n"


def generate_for_file(json_path: Path, output_path: Path | None = None) -> Path:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    ics = build_ics(payload, file_stem=json_path.stem)

    if output_path is None:
        output_path = json_path.with_suffix(".ics")

    output_path.write_text(ics, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera .ics a partir de agenda-*.json")
    parser.add_argument("--input", type=Path, help="JSON de entrada (omita para processar todos)")
    parser.add_argument("--output", type=Path, help="ICS de saída (apenas com --input)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    if args.input is not None:
        out = generate_for_file(args.input, args.output)
        print(out)
        return

    for json_path in sorted(args.data_dir.glob("agenda-*.json")):
        if json_path.name == "index.json":
            continue
        out = generate_for_file(json_path)
        print(out)


if __name__ == "__main__":
    main()
