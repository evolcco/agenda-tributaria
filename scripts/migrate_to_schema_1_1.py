"""Migra JSONs existentes para o schema 1.1.0.

Adiciona `agenda`, `due_date`, `effective_due_date`, `adjusted`, `adjustment_reason`
sem precisar reprocessar a planilha XLSX original. Usa a URL da página mensal
para inferir o ano/mês da agenda.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agenda_parser import (
    PT_MONTH_LABELS,
    SCHEMA_VERSION,
    _agenda_period_from_url,
    _build_due_dates,
)


def migrate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source") or {}
    agenda_block = payload.get("agenda") or {}
    agenda_year = agenda_block.get("year")
    agenda_month = agenda_block.get("month")

    if not (agenda_year and agenda_month):
        period = _agenda_period_from_url(source.get("monthly_page_url"))
        if period is not None:
            agenda_year, agenda_month = period

    if agenda_year and agenda_month:
        payload["agenda"] = {
            "year": agenda_year,
            "month": agenda_month,
            "label": f"{PT_MONTH_LABELS[agenda_month]}/{agenda_year}",
        }
    else:
        payload["agenda"] = None

    adjusted_count = 0
    for collection_name in ("tributos", "declaracoes"):
        for item in payload.get(collection_name, []):
            dates = _build_due_dates(item.get("due_day"), agenda_year, agenda_month)
            item.update(dates)
            if dates["adjusted"]:
                adjusted_count += 1

    counts = payload.setdefault("counts", {})
    counts["adjusted"] = adjusted_count

    payload["schema_version"] = SCHEMA_VERSION
    return payload


def migrate_file(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    migrated = migrate_payload(payload)
    path.write_text(
        json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra JSONs para schema 1.1.0")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    files = sorted(args.data_dir.glob("agenda-*.json"))
    if not files:
        print("Nenhum agenda-*.json encontrado em", args.data_dir)
        return

    for file in files:
        if file.name == "index.json":
            continue
        migrate_file(file)
        print("migrado:", file.name)


if __name__ == "__main__":
    main()
