"""Valida o schema dos JSONs em vencimento-guias/.

Uso:
    python scripts/validate_vencimento_guias.py vencimento-guias/2026-04.json
    python scripts/validate_vencimento_guias.py vencimento-guias/   # valida todos

Sem dependências externas (Python stdlib).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ALLOWED_CATEGORY_IDS = {"municipal", "estadual", "federal"}
ALLOWED_ICONS = {"city", "building", "landmark"}


class ValidationError(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_item(item: Any, ctx: str) -> None:
    _require(isinstance(item, dict), f"{ctx}: item deve ser objeto")
    assert isinstance(item, dict)

    due_day = item.get("due_day")
    is_int = isinstance(due_day, int) and not isinstance(due_day, bool)
    if is_int:
        assert isinstance(due_day, int)
        _require(1 <= due_day <= 31, f"{ctx}: due_day numérico deve estar entre 1 e 31 (got {due_day})")
    else:
        _require(
            due_day == "last_business_day",
            f"{ctx}: due_day deve ser inteiro 1-31 ou \"last_business_day\" (got {due_day!r})",
        )

    _require(_is_non_empty_string(item.get("title")), f"{ctx}: title obrigatório (string não vazia)")

    for optional in ("subtitle", "note"):
        if optional in item:
            _require(
                isinstance(item[optional], str),
                f"{ctx}: {optional} deve ser string quando presente",
            )

    if "cities" in item:
        cities = item["cities"]
        _require(
            isinstance(cities, list) and all(isinstance(c, str) for c in cities),
            f"{ctx}: cities deve ser lista de strings",
        )


def _validate_category(category: Any, ctx: str) -> None:
    _require(isinstance(category, dict), f"{ctx}: categoria deve ser objeto")
    assert isinstance(category, dict)

    cat_id = category.get("id")
    _require(
        cat_id in ALLOWED_CATEGORY_IDS,
        f"{ctx}: id deve ser um de {sorted(ALLOWED_CATEGORY_IDS)} (got {cat_id!r})",
    )

    _require(_is_non_empty_string(category.get("label")), f"{ctx}: label obrigatório")

    icon = category.get("icon")
    _require(
        icon in ALLOWED_ICONS,
        f"{ctx}: icon deve ser um de {sorted(ALLOWED_ICONS)} (got {icon!r})",
    )

    color = category.get("color")
    _require(
        isinstance(color, str) and color.startswith("#") and len(color) in (4, 7),
        f"{ctx}: color deve ser hex tipo #RRGGBB (got {color!r})",
    )

    items = category.get("items")
    _require(isinstance(items, list) and len(items) > 0, f"{ctx}: items deve ser lista não vazia")
    assert isinstance(items, list)
    for idx, item in enumerate(items):
        _validate_item(item, f"{ctx}.items[{idx}]")


def validate_payload(payload: Any, file_label: str) -> None:
    _require(isinstance(payload, dict), f"{file_label}: payload deve ser objeto")
    assert isinstance(payload, dict)

    _require(_is_non_empty_string(payload.get("schema_version")), f"{file_label}: schema_version obrigatório")

    year = payload.get("year")
    month = payload.get("month")
    _require(
        isinstance(year, int) and not isinstance(year, bool) and 2000 <= year <= 2100,
        f"{file_label}: year deve ser inteiro entre 2000 e 2100 (got {year!r})",
    )
    _require(
        isinstance(month, int) and not isinstance(month, bool) and 1 <= month <= 12,
        f"{file_label}: month deve ser inteiro entre 1 e 12 (got {month!r})",
    )

    _require(_is_non_empty_string(payload.get("label")), f"{file_label}: label obrigatório")

    categories = payload.get("categories")
    _require(
        isinstance(categories, list) and len(categories) > 0,
        f"{file_label}: categories deve ser lista não vazia",
    )
    assert isinstance(categories, list)

    seen_ids: set[str] = set()
    for idx, cat in enumerate(categories):
        _validate_category(cat, f"{file_label}.categories[{idx}]")
        cat_id = cat["id"]
        _require(cat_id not in seen_ids, f"{file_label}.categories[{idx}]: id duplicado: {cat_id!r}")
        seen_ids.add(cat_id)

    footnotes = payload.get("footnotes", [])
    _require(
        isinstance(footnotes, list) and all(isinstance(n, str) for n in footnotes),
        f"{file_label}: footnotes deve ser lista de strings",
    )


def validate_file(path: Path) -> None:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload, path.name)


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: python scripts/validate_vencimento_guias.py <arquivo.json|diretório>", file=sys.stderr)
        sys.exit(2)

    target = Path(sys.argv[1])

    if target.is_dir():
        files = sorted(target.glob("*.json"))
        if not files:
            print(f"Nenhum .json encontrado em {target}", file=sys.stderr)
            sys.exit(2)
    elif target.is_file():
        files = [target]
    else:
        print(f"Caminho inválido: {target}", file=sys.stderr)
        sys.exit(2)

    errors: list[str] = []
    for path in files:
        try:
            validate_file(path)
            print(f"OK: {path}")
        except (ValidationError, json.JSONDecodeError) as exc:
            errors.append(f"FAIL: {path}: {exc}")
            print(f"FAIL: {path}: {exc}", file=sys.stderr)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
