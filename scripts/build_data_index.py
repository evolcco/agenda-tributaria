from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

PT_MONTH_LABEL = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def infer_period_from_page_url(page_url: str | None) -> tuple[int, int] | None:
    if not page_url:
        return None

    match = re.search(r"/(20\d{2})/([A-Za-zÀ-ÿ-]+)(?:/|$)", page_url)
    if not match:
        return None

    year = int(match.group(1))
    slug = (
        match.group(2)
        .lower()
        .replace("ç", "c")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("-", " ")
    )
    token = slug.split(" ")[0]
    month = PT_MONTHS.get(token)
    if month is None:
        return None

    return (year, month)


def format_period(year: int | None, month: int | None) -> str | None:
    if not year or not month:
        return None
    label = PT_MONTH_LABEL.get(month)
    if not label:
        return None
    return f"{label}/{year}"


def build_index(data_dir: Path) -> dict[str, Any]:
    dedup: dict[str, dict[str, Any]] = {}

    for file in sorted(data_dir.glob("agenda-*.json")):
        if file.name == "index.json":
            continue

        payload = load_json(file)
        source = payload.get("source", {})
        comp = payload.get("competence", {})
        agenda = payload.get("agenda") or {}
        payload_generated_at = payload.get("generated_at")
        competence_year = comp.get("year")
        competence_month = comp.get("month")
        competence_label = comp.get("label")

        agenda_year = agenda.get("year")
        agenda_month = agenda.get("month")
        agenda_label = agenda.get("label")
        if not (agenda_year and agenda_month):
            inferred = infer_period_from_page_url(source.get("monthly_page_url"))
            if inferred is not None:
                agenda_year, agenda_month = inferred
                agenda_label = format_period(agenda_year, agenda_month)

        year = agenda_year or competence_year
        month = agenda_month or competence_month
        label = agenda_label or competence_label or file.stem

        ics_path = file.with_suffix(".ics")
        entry = {
            "file": file.name,
            "ics_file": ics_path.name if ics_path.exists() else None,
            "year": year,
            "month": month,
            "label": label,
            "payload_generated_at": payload_generated_at,
            "agenda_year": agenda_year,
            "agenda_month": agenda_month,
            "agenda_label": agenda_label,
            "competence_year": competence_year,
            "competence_month": competence_month,
            "competence_label": competence_label,
            "counts": payload.get("counts", {}),
            "schema_version": payload.get("schema_version"),
            "source_monthly_page_url": source.get("monthly_page_url"),
            "source_xlsx_url": source.get("xlsx_url"),
        }

        dedup_key = source.get("monthly_page_url") or file.name
        existing = dedup.get(dedup_key)
        if existing is None or (payload_generated_at or "") > (existing.get("payload_generated_at") or ""):
            dedup[dedup_key] = entry

    months = sorted(
        dedup.values(),
        key=lambda item: (item.get("year") or 0, item.get("month") or 0),
        reverse=True,
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "months": months,
    }


def main() -> None:
    data_dir = Path("data")
    payload = build_index(data_dir)
    output = data_dir / "index.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
