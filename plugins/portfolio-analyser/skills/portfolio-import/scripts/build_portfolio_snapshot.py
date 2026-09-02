"""Validate normalized portfolio manifests and build one deterministic app snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_POSITIONS = 10_000
SNAPSHOT_NAMESPACE = uuid.UUID("ce4e8c73-b028-4f53-b22c-f96d48f4c2d4")
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
MANIFEST_FIELDS = {
    "as_of",
    "base_currency",
    "cash_value",
    "reported_total_value",
    "positions",
    "warnings",
}
POSITION_FIELDS = {
    "isin",
    "symbol",
    "name",
    "asset_type",
    "quantity",
    "price",
    "market_value",
    "currency",
    "average_buy_price",
    "unrealized_pnl",
    "unrealized_pnl_pct",
}
REQUIRED_POSITION_FIELDS = {
    "name",
    "asset_type",
    "quantity",
    "price",
    "market_value",
    "currency",
}


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Position:
    isin: str | None
    symbol: str | None
    name: str
    asset_type: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    currency: str
    average_buy_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_pct: Decimal | None = None


@dataclass(frozen=True)
class Manifest:
    as_of: str
    base_currency: str
    cash_value: Decimal
    positions: list[Position]
    warnings: list[str]


def _decimal(raw: Any, label: str, *, allow_negative: bool = False) -> Decimal:
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError(f"{label} muss ein Dezimalwert als String sein")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValidationError(f"{label} ist keine gültige Dezimalzahl") from exc
    if not value.is_finite() or (not allow_negative and value < 0):
        raise ValidationError(f"{label} enthält einen ungültigen Wert")
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _clean_text(raw: Any, label: str, max_length: int) -> str:
    if not isinstance(raw, str):
        raise ValidationError(f"{label} muss Text sein")
    value = re.sub(r"\s+", " ", raw).strip()
    if not value or len(value) > max_length or "\0" in value:
        raise ValidationError(f"{label} ist leer oder zu lang")
    return value


def _optional_identifier(raw: Any, label: str, max_length: int) -> str | None:
    if raw is None:
        return None
    value = _clean_text(raw, label, max_length).upper()
    return value


def _position(raw: Any, base_currency: str, index: int) -> Position:
    label = f"Position {index + 1}"
    if not isinstance(raw, dict):
        raise ValidationError(f"{label} muss ein JSON-Objekt sein")
    unexpected = set(raw) - POSITION_FIELDS
    missing = REQUIRED_POSITION_FIELDS - set(raw)
    if unexpected:
        raise ValidationError(f"{label} enthält nicht erlaubte Felder: {sorted(unexpected)}")
    if missing:
        raise ValidationError(f"{label} fehlen Pflichtfelder: {sorted(missing)}")

    isin = _optional_identifier(raw.get("isin"), f"{label}.isin", 12)
    if isin and not ISIN_RE.fullmatch(isin):
        raise ValidationError(f"{label}.isin ist keine gültig formatierte ISIN")
    symbol = _optional_identifier(raw.get("symbol"), f"{label}.symbol", 32)
    name = _clean_text(raw["name"], f"{label}.name", 300)
    asset_type = _clean_text(raw["asset_type"], f"{label}.asset_type", 64).upper()
    currency = _clean_text(raw["currency"], f"{label}.currency", 3).upper()
    if not CURRENCY_RE.fullmatch(currency):
        raise ValidationError(f"{label}.currency ist kein ISO-Währungscode")
    if currency != base_currency:
        raise ValidationError(
            f"{label}.currency muss der Basiswährung {base_currency} entsprechen"
        )

    average_buy_price = raw.get("average_buy_price")
    unrealized_pnl = raw.get("unrealized_pnl")
    unrealized_pnl_pct = raw.get("unrealized_pnl_pct")
    return Position(
        isin=isin,
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        quantity=_decimal(raw["quantity"], f"{label}.quantity"),
        price=_decimal(raw["price"], f"{label}.price"),
        market_value=_decimal(raw["market_value"], f"{label}.market_value"),
        currency=currency,
        average_buy_price=(
            _decimal(average_buy_price, f"{label}.average_buy_price")
            if average_buy_price is not None
            else None
        ),
        unrealized_pnl=(
            _decimal(unrealized_pnl, f"{label}.unrealized_pnl", allow_negative=True)
            if unrealized_pnl is not None
            else None
        ),
        unrealized_pnl_pct=(
            _decimal(
                unrealized_pnl_pct,
                f"{label}.unrealized_pnl_pct",
                allow_negative=True,
            )
            if unrealized_pnl_pct is not None
            else None
        ),
    )


def _validate_reported_total(calculated: Decimal, reported: Decimal, label: str) -> None:
    tolerance = max(Decimal("0.02"), abs(reported) * Decimal("0.001"))
    if abs(calculated - reported) > tolerance:
        raise ValidationError(
            f"{label}: Positionssumme plus Cash weicht vom angegebenen Gesamtwert ab"
        )


def parse_manifest(raw: Any, label: str = "Manifest") -> Manifest:
    if not isinstance(raw, dict):
        raise ValidationError(f"{label} muss ein JSON-Objekt sein")
    unexpected = set(raw) - MANIFEST_FIELDS
    required = {"as_of", "base_currency", "cash_value", "positions", "warnings"}
    missing = required - set(raw)
    if unexpected:
        raise ValidationError(f"{label} enthält nicht erlaubte Felder: {sorted(unexpected)}")
    if missing:
        raise ValidationError(f"{label} fehlen Pflichtfelder: {sorted(missing)}")

    as_of = _clean_text(raw["as_of"], f"{label}.as_of", 10)
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValidationError(f"{label}.as_of muss YYYY-MM-DD entsprechen") from exc

    base_currency = _clean_text(
        raw["base_currency"], f"{label}.base_currency", 3
    ).upper()
    if not CURRENCY_RE.fullmatch(base_currency):
        raise ValidationError(f"{label}.base_currency ist kein ISO-Währungscode")
    cash_value = _decimal(raw["cash_value"], f"{label}.cash_value")

    position_values = raw["positions"]
    if not isinstance(position_values, list) or len(position_values) > MAX_POSITIONS:
        raise ValidationError(f"{label}.positions ist keine gültige Positionsliste")
    positions = [
        _position(item, base_currency, index) for index, item in enumerate(position_values)
    ]

    warning_values = raw["warnings"]
    if not isinstance(warning_values, list) or len(warning_values) > 100:
        raise ValidationError(f"{label}.warnings ist keine gültige Warnungsliste")
    warnings = [
        _clean_text(item, f"{label}.warnings[{index}]", 500)
        for index, item in enumerate(warning_values)
    ]

    calculated = sum((item.market_value for item in positions), Decimal(0)) + cash_value
    if calculated <= 0:
        raise ValidationError(f"{label} enthält keinen positiven Portfoliowert")
    if "reported_total_value" in raw and raw["reported_total_value"] is not None:
        reported = _decimal(raw["reported_total_value"], f"{label}.reported_total_value")
        _validate_reported_total(calculated, reported, label)
    else:
        warnings.append(f"{label}: Die Quelle enthält keinen Gesamtwert.")

    return Manifest(
        as_of=as_of,
        base_currency=base_currency,
        cash_value=cash_value,
        positions=positions,
        warnings=warnings,
    )


def _identity(position: Position) -> tuple[str, ...]:
    if position.isin:
        return ("isin", position.isin)
    if position.symbol:
        return ("symbol", position.asset_type, position.symbol)
    normalized_name = "".join(
        character for character in position.name.casefold() if character.isalnum()
    )
    if not normalized_name:
        normalized_name = position.name.casefold()
    return ("name", position.asset_type, normalized_name)


def _merge(existing: Position, incoming: Position) -> Position:
    if existing.asset_type != incoming.asset_type or existing.currency != incoming.currency:
        raise ValidationError(f"Widersprüchliche Daten für {existing.name}")
    if existing.isin and incoming.isin and existing.isin != incoming.isin:
        raise ValidationError(f"Widersprüchliche ISIN für {existing.name}")
    if existing.symbol and incoming.symbol and existing.symbol != incoming.symbol:
        raise ValidationError(f"Widersprüchliches Symbol für {existing.name}")

    quantity = existing.quantity + incoming.quantity
    market_value = existing.market_value + incoming.market_value
    price = market_value / quantity if quantity else max(existing.price, incoming.price)
    average_buy_price = None
    if existing.average_buy_price is not None and incoming.average_buy_price is not None:
        average_buy_price = (
            (
                existing.average_buy_price * existing.quantity
                + incoming.average_buy_price * incoming.quantity
            )
            / quantity
            if quantity
            else Decimal(0)
        )
    unrealized_pnl = None
    unrealized_pnl_pct = None
    if existing.unrealized_pnl is not None and incoming.unrealized_pnl is not None:
        unrealized_pnl = existing.unrealized_pnl + incoming.unrealized_pnl
        cost_value = market_value - unrealized_pnl
        if cost_value:
            unrealized_pnl_pct = unrealized_pnl / cost_value * Decimal(100)

    return replace(
        existing,
        isin=existing.isin or incoming.isin,
        symbol=existing.symbol or incoming.symbol,
        name=min((existing.name, incoming.name), key=lambda value: value.casefold()),
        quantity=quantity,
        price=price,
        market_value=market_value,
        average_buy_price=average_buy_price,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl_pct,
    )


def _position_payload(position: Position) -> dict[str, str | None]:
    return {
        "isin": position.isin,
        "symbol": position.symbol,
        "name": position.name,
        "asset_type": position.asset_type,
        "quantity": _decimal_text(position.quantity),
        "price": _decimal_text(position.price),
        "market_value": _decimal_text(position.market_value),
        "currency": position.currency,
        "average_buy_price": (
            _decimal_text(position.average_buy_price)
            if position.average_buy_price is not None
            else None
        ),
        "unrealized_pnl": (
            _decimal_text(position.unrealized_pnl)
            if position.unrealized_pnl is not None
            else None
        ),
        "unrealized_pnl_pct": (
            _decimal_text(position.unrealized_pnl_pct)
            if position.unrealized_pnl_pct is not None
            else None
        ),
    }


def build_payload(raw_manifests: list[Any]) -> dict[str, Any]:
    if not raw_manifests:
        raise ValidationError("Keine Manifeste übergeben")
    manifests = [
        parse_manifest(raw, f"Manifest {index + 1}")
        for index, raw in enumerate(raw_manifests)
    ]
    as_of_values = {manifest.as_of for manifest in manifests}
    currency_values = {manifest.base_currency for manifest in manifests}
    if len(as_of_values) != 1:
        raise ValidationError("Die Manifeste haben unterschiedliche Bewertungsdaten")
    if len(currency_values) != 1:
        raise ValidationError("Die Manifeste haben unterschiedliche Basiswährungen")

    merged: dict[tuple[str, ...], Position] = {}
    for manifest in manifests:
        for position in manifest.positions:
            key = _identity(position)
            merged[key] = _merge(merged[key], position) if key in merged else position

    positions = sorted(
        (_position_payload(item) for item in merged.values()),
        key=lambda item: (
            item["isin"] or "",
            item["symbol"] or "",
            item["name"] or "",
        ),
    )
    cash_value = sum((manifest.cash_value for manifest in manifests), Decimal(0))
    position_sum = sum(
        (_decimal(item["market_value"], "market_value") for item in positions),
        Decimal(0),
    )
    total_value = position_sum + cash_value
    as_of = next(iter(as_of_values))
    base_currency = next(iter(currency_values))
    canonical = json.dumps(
        {
            "as_of": as_of,
            "base_currency": base_currency,
            "total_value": _decimal_text(total_value),
            "cash_value": _decimal_text(cash_value),
            "positions": positions,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "snapshot": {
            "id": str(uuid.uuid5(SNAPSHOT_NAMESPACE, canonical)),
            "as_of": as_of,
            "base_currency": base_currency,
            "total_value": _decimal_text(total_value),
            "cash_value": _decimal_text(cash_value),
        },
        "positions": positions,
        "validation": {
            "source_count": len(manifests),
            "position_sum": _decimal_text(position_sum),
            "warnings": [warning for manifest in manifests for warning in manifest.warnings],
        },
    }


def _load_manifest(path: Path) -> Any:
    if not path.is_file():
        raise ValidationError(f"Manifest wurde nicht gefunden: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValidationError(f"Manifest ist größer als 5 MB: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Manifest ist kein gültiges UTF-8-JSON: {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Normalized JSON manifest(s)")
    args = parser.parse_args()
    try:
        result = build_payload([_load_manifest(path) for path in args.inputs])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ValidationError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
