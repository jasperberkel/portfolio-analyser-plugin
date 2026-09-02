# Normalized portfolio input

Create one JSON manifest per non-overlapping logical source, then pass all manifests to `scripts/build_portfolio_snapshot.py`. A manifest contains only:

```json
{
  "as_of": "2026-08-31",
  "base_currency": "EUR",
  "cash_value": "125.40",
  "reported_total_value": "1025.40",
  "positions": [
    {
      "isin": "IE00BK5BQT80",
      "symbol": null,
      "name": "Example World UCITS ETF",
      "asset_type": "ETF",
      "quantity": "9",
      "price": "100",
      "market_value": "900",
      "currency": "EUR",
      "average_buy_price": null,
      "unrealized_pnl": null,
      "unrealized_pnl_pct": null
    }
  ],
  "warnings": []
}
```

Rules:

- `as_of`, `base_currency`, `cash_value`, `positions`, and `warnings` are required. `reported_total_value` is optional only when the source does not state a total.
- All dates must describe the same effective valuation date. All manifests must use the same three-letter base currency.
- Decimal values are strings with `.` as decimal separator and no thousands separators or currency symbols.
- `market_value`, `price`, cash, cost data, and profit/loss values must be expressed in `base_currency`; set `currency` to that currency. Preserve original-currency exposure in the Markdown report, not in the snapshot fields.
- Use a valid ISIN when present. Otherwise use a reliable symbol. Leave an unknown identifier `null`; never guess it. Name plus asset type is the last-resort identity for manual documents.
- Use concise asset types such as `STOCK`, `ETF`, `FUND`, `BOND`, `CRYPTO`, `COMMODITY`, or `CASH_EQUIVALENT`. Do not silently classify an ambiguous instrument.
- Each manifest must represent a non-overlapping source slice. Exclude superseded or duplicated statements before building. Equal instruments from genuinely different accounts or complementary slices are merged by the builder.
- If the source omits cash, use `"0"` and add a warning. If it explicitly confirms zero cash, no warning is needed.
- If a source total exists, include it. The builder checks it against positions plus cash with a small rounding tolerance.
- Do not put filenames, broker account IDs, personal data, free-form extracted text, citations, or extra fields into a manifest.

Run:

```bash
python scripts/build_portfolio_snapshot.py <manifest.json> [<manifest.json> ...]
```

The result contains exactly `snapshot`, `positions`, and `validation`. Publish only `snapshot` and `positions`; carry validation warnings into the report.
