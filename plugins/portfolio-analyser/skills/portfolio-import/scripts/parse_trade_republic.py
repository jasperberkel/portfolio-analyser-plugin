"""Extract holdings from recognized Trade Republic securities and crypto PDFs."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PAGES = 100
SNAPSHOT_NAMESPACE = uuid.UUID("ce4e8c73-b028-4f53-b22c-f96d48f4c2d4")
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
NUMBER_RE = r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
DATE_ONLY_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
DATE_PATTERNS = [
    re.compile(
        r"(?:Stichtag|Stand|per|Datum)\s*:?[ ]*(\d{2}\.\d{2}\.\d{4})",
        re.IGNORECASE,
    ),
    re.compile(r"Depot(?:auszug)?\s+(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE),
    re.compile(r"\bzum\s+(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE),
]
SECURITY_START_RE = re.compile(
    rf"^(?P<quantity>{NUMBER_RE})\s+Stk\.\s+(?P<name>.+)$", re.IGNORECASE
)
CRYPTO_SAME_LINE_RE = re.compile(
    rf"^(?P<quantity>{NUMBER_RE})\s+Stk\.\s+(?P<name>.+?)\s+(?P<price>{NUMBER_RE})$",
    re.IGNORECASE,
)
CRYPTO_SYMBOLS = {"bitcoin": "BTC", "ethereum": "ETH"}


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedPosition:
    isin: str | None
    symbol: str | None
    name: str
    asset_type: str
    quantity: str
    price: str
    market_value: str
    currency: str
    average_buy_price: str | None = None
    unrealized_pnl: str | None = None
    unrealized_pnl_pct: str | None = None


@dataclass(frozen=True)
class ParsedDocument:
    as_of: str
    total_value: Decimal
    positions: list[ParsedPosition]
    warnings: list[str]


def parse_decimal(raw: str) -> Decimal:
    cleaned = raw.strip().replace("\u00a0", "").replace(" ", "").replace("€", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ParseError(f"Ungültige Zahl: {raw}") from exc


def decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def extract_pdf_text(path: Path) -> str:
    if path.suffix.lower() != ".pdf":
        raise ParseError("Nur PDF-Dateien werden unterstützt")
    if not path.is_file():
        raise ParseError("PDF-Datei wurde nicht gefunden")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ParseError("PDF ist größer als 20 MB")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ParseError("pypdf fehlt in der Python-Umgebung") from exc

    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ParseError("Passwortgeschützte PDFs werden nicht unterstützt")
    if len(reader.pages) > MAX_PAGES:
        raise ParseError("PDF enthält mehr als 100 Seiten")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def normalized_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def extract_as_of(text: str) -> str:
    for pattern in DATE_PATTERNS:
        if match := pattern.search(text):
            day, month, year = (int(part) for part in match.group(1).split("."))
            return date(year, month, day).isoformat()
    raise ParseError("Stichtag wurde nicht gefunden")


def infer_asset_type(name: str) -> str:
    lowered = name.lower()
    if "etf" in lowered or "ucits" in lowered:
        return "ETF"
    if any(token in lowered for token in ("gold", "silver", "physical metal")):
        return "COMMODITY"
    if any(token in lowered for token in ("bond", "anleihe", "treasury")):
        return "BOND"
    return "STOCK"


def _numbers(line: str) -> list[Decimal]:
    return [parse_decimal(raw) for raw in re.findall(NUMBER_RE, line)]


def _validate_total(position_sum: Decimal, total_value: Decimal, label: str) -> None:
    tolerance = max(Decimal(2), total_value * Decimal("0.02"))
    if abs(total_value - position_sum) > tolerance:
        raise ParseError(
            f"Positionssumme und Gesamtwert der {label} weichen um mehr als die erlaubte "
            "Toleranz ab"
        )


def _securities_total(text: str) -> Decimal:
    match = re.search(
        rf"ANZAHL\s+POSITIONEN:\s*\d+\s+({NUMBER_RE})\s*(?:EUR|€)",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise ParseError("Gesamtwert des Depotauszugs wurde nicht gefunden")
    return parse_decimal(match.group(1))


def _merge_security_lots(positions: list[ParsedPosition]) -> list[ParsedPosition]:
    merged: dict[str, ParsedPosition] = {}
    for position in positions:
        assert position.isin
        existing = merged.get(position.isin)
        if not existing:
            merged[position.isin] = position
            continue
        if existing.currency != position.currency or existing.asset_type != position.asset_type:
            raise ParseError(f"Widersprüchliche Mehrfachposition für ISIN {position.isin}")
        merged[position.isin] = replace(
            existing,
            quantity=decimal_text(
                parse_decimal(existing.quantity) + parse_decimal(position.quantity)
            ),
            market_value=decimal_text(
                parse_decimal(existing.market_value) + parse_decimal(position.market_value)
            ),
        )
    return list(merged.values())


def parse_securities_statement(text: str) -> ParsedDocument:
    lines = normalized_lines(text)
    starts = [
        (index, match)
        for index, line in enumerate(lines)
        if (match := SECURITY_START_RE.match(line))
    ]
    if not starts:
        raise ParseError("Keine Wertpapierpositionen gefunden")

    positions: list[ParsedPosition] = []
    for offset, (start, match) in enumerate(starts):
        end = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        block = lines[start:end]
        isin_match = next(
            (ISIN_RE.search(line) for line in block if "ISIN" in line.upper()), None
        )
        if not isin_match:
            raise ParseError(f"Keine ISIN für Wertpapierposition ab Zeile {start + 1} gefunden")
        isin = isin_match.group(0)
        isin_index = next(index for index, line in enumerate(block) if isin in line)
        amounts = [
            parse_decimal(line)
            for line in block[isin_index + 1 :]
            if re.fullmatch(rf"{NUMBER_RE}(?:\s*(?:EUR|€))?", line, re.IGNORECASE)
            and not DATE_ONLY_RE.fullmatch(line)
        ]
        if len(amounts) < 2:
            raise ParseError(f"Kurs oder Kurswert für ISIN {isin} wurde nicht gefunden")
        quantity = parse_decimal(match.group("quantity"))
        price, market_value = amounts[0], amounts[-1]
        if quantity <= 0 or price < 0 or market_value <= 0:
            raise ParseError(f"Position {isin} enthält ungültige Werte")
        name = match.group("name").strip()[:300]
        positions.append(
            ParsedPosition(
                isin=isin,
                symbol=None,
                name=name,
                asset_type=infer_asset_type(name),
                quantity=decimal_text(quantity),
                price=decimal_text(price),
                market_value=decimal_text(market_value),
                currency="EUR",
            )
        )

    total_value = _securities_total(text)
    position_sum = sum((parse_decimal(item.market_value) for item in positions), Decimal(0))
    _validate_total(position_sum, total_value, "Wertpapierübersicht")
    return ParsedDocument(
        as_of=extract_as_of(text),
        total_value=total_value,
        positions=_merge_security_lots(positions),
        warnings=[],
    )


def _crypto_starts(lines: list[str]) -> list[tuple[int, int, Decimal, str, Decimal]]:
    starts: list[tuple[int, int, Decimal, str, Decimal]] = []
    index = 0
    while index < len(lines):
        if match := CRYPTO_SAME_LINE_RE.match(lines[index]):
            starts.append(
                (
                    index,
                    index + 1,
                    parse_decimal(match.group("quantity")),
                    match.group("name"),
                    parse_decimal(match.group("price")),
                )
            )
            index += 1
            continue
        if (
            re.fullmatch(NUMBER_RE, lines[index])
            and index + 2 < len(lines)
            and re.fullmatch(r"Stk\.", lines[index + 1], re.IGNORECASE)
        ):
            name_price = re.match(
                rf"^(?P<name>.+?)\s+(?P<price>{NUMBER_RE})$", lines[index + 2]
            )
            if name_price:
                starts.append(
                    (
                        index,
                        index + 3,
                        parse_decimal(lines[index]),
                        name_price.group("name"),
                        parse_decimal(name_price.group("price")),
                    )
                )
                index += 3
                continue
        index += 1
    return starts


def _clean_crypto_name(raw: str) -> str:
    match = re.fullmatch(r"(.+?)\s*\((.+)\)", raw.strip())
    if match and match.group(1).casefold() == match.group(2).casefold():
        return match.group(1).strip()
    return raw.strip()


def _crypto_total(text: str) -> Decimal:
    match = re.search(
        rf"SUMME\s+KURSWERTE:\s*({NUMBER_RE})\s*(?:EUR|€)", text, re.IGNORECASE
    )
    if not match:
        raise ParseError("Gesamtwert der Crypto-Übersicht wurde nicht gefunden")
    return parse_decimal(match.group(1))


def parse_crypto_statement(text: str) -> ParsedDocument:
    lines = normalized_lines(text)
    starts = _crypto_starts(lines)
    if not starts:
        raise ParseError("Keine Crypto-Positionen gefunden")

    positions: list[ParsedPosition] = []
    for offset, (start, content_start, quantity, raw_name, price) in enumerate(starts):
        end = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        block = lines[content_start:end]
        date_index = next(
            (index for index, line in enumerate(block) if DATE_ONLY_RE.fullmatch(line)), None
        )
        if date_index is None:
            raise ParseError(
                f"Bewertungsdatum für Crypto-Position ab Zeile {start + 1} fehlt"
            )
        after_date = block[date_index + 1 :]
        buy_and_pnl = next(
            (_numbers(line) for line in after_date if len(_numbers(line)) >= 2), None
        )
        pnl_pct_match = next(
            (
                re.fullmatch(rf"({NUMBER_RE})\s*%", line)
                for line in after_date
                if "%" in line
            ),
            None,
        )
        market_values = [
            parse_decimal(line)
            for line in after_date
            if re.fullmatch(NUMBER_RE, line) and not DATE_ONLY_RE.fullmatch(line)
        ]
        if not buy_and_pnl or not pnl_pct_match or not market_values:
            raise ParseError(
                f"Kaufwert oder Kurswert der Crypto-Position ab Zeile {start + 1} fehlt"
            )
        buy_value, unrealized_pnl = buy_and_pnl[0], buy_and_pnl[1]
        market_value = market_values[-1]
        if quantity <= 0 or price < 0 or buy_value < 0 or market_value <= 0:
            raise ParseError("Crypto-Position enthält ungültige Werte")
        name = _clean_crypto_name(raw_name)
        symbol = CRYPTO_SYMBOLS.get(
            name.casefold(), re.sub(r"[^A-Z0-9]", "", name.upper())[:32]
        )
        positions.append(
            ParsedPosition(
                isin=None,
                symbol=symbol or None,
                name=name[:300],
                asset_type="CRYPTO",
                quantity=decimal_text(quantity),
                price=decimal_text(price),
                market_value=decimal_text(market_value),
                currency="EUR",
                average_buy_price=decimal_text((buy_value / quantity).quantize(Decimal("0.01"))),
                unrealized_pnl=decimal_text(unrealized_pnl),
                unrealized_pnl_pct=decimal_text(parse_decimal(pnl_pct_match.group(1))),
            )
        )

    total_value = _crypto_total(text)
    position_sum = sum((parse_decimal(item.market_value) for item in positions), Decimal(0))
    _validate_total(position_sum, total_value, "Crypto-Übersicht")
    return ParsedDocument(
        as_of=extract_as_of(text),
        total_value=total_value,
        positions=positions,
        warnings=[],
    )


def parse_document(text: str) -> ParsedDocument:
    upper = text.upper()
    if "TRADE REPUBLIC" not in upper:
        raise ParseError("Dokument ist kein erkannter Trade-Republic-Depotauszug")
    if "CRYPTO-ÜBERSICHT" in upper or "CRYPTO-UEBERSICHT" in upper:
        return parse_crypto_statement(text)
    if "DEPOTAUSZUG" in upper:
        return parse_securities_statement(text)
    raise ParseError("Dokument ist keine erkannte Wertpapier- oder Crypto-Übersicht")


def _payload(documents: list[ParsedDocument]) -> dict:
    if not documents:
        raise ParseError("Keine Dokumente übergeben")
    as_of_values = {document.as_of for document in documents}
    if len(as_of_values) != 1:
        raise ParseError("Die Dokumente haben unterschiedliche Stichtage")
    positions = [position for document in documents for position in document.positions]
    identities = [(position.isin or "", position.symbol or "") for position in positions]
    if len(identities) != len(set(identities)):
        raise ParseError("Eine Position kommt in mehreren Dokumenten doppelt vor")
    total_value = sum((document.total_value for document in documents), Decimal(0))
    position_sum = sum((parse_decimal(item.market_value) for item in positions), Decimal(0))
    _validate_total(position_sum, total_value, "kombinierten Portfolioübersicht")
    position_payload = [asdict(item) for item in positions]
    as_of = next(iter(as_of_values))
    canonical = json.dumps(
        {
            "as_of": as_of,
            "base_currency": "EUR",
            "total_value": decimal_text(total_value),
            "cash_value": "0",
            "positions": sorted(
                position_payload,
                key=lambda item: (
                    item.get("isin") or "",
                    item.get("symbol") or "",
                    item["name"],
                ),
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "snapshot": {
            "id": str(uuid.uuid5(SNAPSHOT_NAMESPACE, canonical)),
            "as_of": as_of,
            "base_currency": "EUR",
            "total_value": decimal_text(total_value),
            "cash_value": "0",
        },
        "positions": position_payload,
        "validation": {
            "position_sum": decimal_text(position_sum),
            "warnings": [
                "Die Portfolioauszüge enthalten keinen Cashbestand; Cash wurde mit 0 angesetzt.",
                *[warning for document in documents for warning in document.warnings],
            ],
        },
    }


def parse_statement(text: str) -> dict:
    return _payload([parse_document(text)])


def parse_statements(texts: list[str]) -> dict:
    return _payload([parse_document(text) for text in texts])


def normalized_manifest(texts: list[str]) -> dict:
    payload = parse_statements(texts)
    return {
        "as_of": payload["snapshot"]["as_of"],
        "base_currency": payload["snapshot"]["base_currency"],
        "cash_value": payload["snapshot"]["cash_value"],
        "reported_total_value": payload["snapshot"]["total_value"],
        "positions": payload["positions"],
        "warnings": payload["validation"]["warnings"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Recognized Trade Republic PDF(s)")
    parser.add_argument(
        "--text-input",
        action="store_true",
        help="Read extracted text fixtures instead of PDFs (tests only)",
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Emit a generic source manifest for build_portfolio_snapshot.py",
    )
    args = parser.parse_args()
    try:
        texts = [
            path.read_text(encoding="utf-8") if args.text_input else extract_pdf_text(path)
            for path in args.inputs
        ]
        result = normalized_manifest(texts) if args.manifest else parse_statements(texts)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ParseError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
