"""Gera vencimento-guias/index.json a partir dos JSONs do diretório.

Uso:
    python scripts/build_vencimento_guias_index.py <input_dir> <output_path>

Saída ordenada por ano/mês desc (mais recente primeiro).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_index(input_dir: Path) -> dict[str, Any]:
    months: list[dict[str, Any]] = []

    for path in sorted(input_dir.glob("*.json")):
        if path.name == "index.json":
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"WARN: pulando {path.name}: {exc}", file=sys.stderr)
            continue

        year = payload.get("year")
        month = payload.get("month")
        label = payload.get("label")

        if not isinstance(year, int) or not isinstance(month, int):
            print(f"WARN: {path.name}: year/month inválidos, pulando", file=sys.stderr)
            continue

        months.append({
            "file": path.name,
            "year": year,
            "month": month,
            "label": label or f"{year}-{month:02d}",
        })

    months.sort(key=lambda m: (m["year"], m["month"]), reverse=True)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "months": months,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("uso: build_vencimento_guias_index.py <input_dir> <output_path>", file=sys.stderr)
        sys.exit(2)

    input_dir = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_dir.is_dir():
        print(f"diretório inválido: {input_dir}", file=sys.stderr)
        sys.exit(2)

    payload = build_index(input_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK: {output_path} ({len(payload['months'])} meses)")


if __name__ == "__main__":
    main()
