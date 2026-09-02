# Portfolio Analyser MCP contract

Use the MCP server named `portfolio_analyser` at `http://127.0.0.1:8010/mcp`.

## Read current positions

Call `get_current_positions()`. It returns:

```json
{
  "snapshot": {
    "id": "UUID",
    "as_of": "YYYY-MM-DD",
    "base_currency": "EUR",
    "total_value": "decimal",
    "cash_value": "decimal",
    "created_at": "ISO-8601"
  },
  "positions": [
    {
      "isin": "optional",
      "symbol": "optional",
      "name": "string",
      "asset_type": "string",
      "quantity": "decimal",
      "price": "decimal",
      "market_value": "decimal",
      "currency": "string"
    }
  ]
}
```

Do not infer live prices from this response. The values belong to the snapshot date.

## Publish the completed report

Call:

```text
publish_analysis(
  id="<caller-generated UUID>",
  analysis_type="portfolio.position-research",
  content_markdown="<complete German Markdown report>"
)
```

Publish only after selection and research are complete. Never call `publish_portfolio_snapshot_and_analysis`: this skill does not modify positions or snapshots. A retry must reuse the same UUID and identical content; a conflicting UUID is a hard failure.

