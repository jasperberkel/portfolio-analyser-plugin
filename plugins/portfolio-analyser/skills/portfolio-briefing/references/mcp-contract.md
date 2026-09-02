# Portfolio Briefing MCP contract

Use the MCP server named `portfolio_analyser` at `http://127.0.0.1:8010/mcp`.

The existing MCP tool names contain `dashboard` for transport compatibility. They do not constrain where or how the structured result is presented.

## Read

Call `get_dashboard_context()` once. It returns:

```json
{
  "snapshot": { "id": "UUID", "total_value": "decimal", "base_currency": "EUR" },
  "positions": [
    {
      "id": "UUID",
      "name": "string",
      "isin": "optional",
      "symbol": "optional",
      "asset_type": "string",
      "portfolio_weight_pct": "decimal"
    }
  ],
  "reports": [
    {
      "id": "UUID",
      "analysis_type": "string",
      "created_at": "ISO-8601",
      "content_markdown": "complete report",
      "max_age_days": 7
    }
  ],
  "excluded_reports": [
    {
      "analysis_type": "string",
      "analysis_id": "UUID",
      "reason": "stale",
      "max_age_days": 7,
      "created_at": "ISO-8601"
    }
  ],
  "source_fingerprint": "64 lowercase hex characters",
  "total_content_chars": 12345,
  "existing_briefing_id": null
}
```

## Publish

Call `publish_dashboard_briefing` with one complete payload:

```json
{
  "id": "caller-generated UUID",
  "source_fingerprint": "value returned by get_dashboard_context",
  "generator": "codex_skill",
  "generator_version": "portfolio-briefing/1",
  "schema_version": 1,
  "briefing": {
    "summary": "German portfolio synthesis",
    "actions": [
      {
        "priority": 1,
        "action": "reduce",
        "subject": {
          "kind": "instrument",
          "name": "Example AG",
          "position_id": "UUID",
          "isin": "optional",
          "symbol": "optional"
        },
        "target_weight_pct": 8,
        "rationale": "German evidence-based rationale",
        "horizon_days": 30,
        "confidence": "high",
        "evidence_refs": [
          { "source_type": "portfolio_snapshot", "source_id": "snapshot UUID" },
          { "source_type": "analysis", "source_id": "included analysis UUID" }
        ]
      }
    ]
  }
}
```

Rules enforced by the server:

- actions: `buy`, `sell`, `increase`, `reduce`, `hold`, or `rebalance`;
- subject kinds: `portfolio`, `cash`, `asset_class`, or `instrument`;
- instrument subjects require a position ID, ISIN, or symbol;
- priorities must be unique integers from 1 to 10;
- all actions except `hold` require a final `target_weight_pct` from 0 to 100;
- `sell` requires target weight 0 and `buy` requires a target above 0;
- `hold` must omit `target_weight_pct`;
- `horizon_days` must be between 0 and 3650;
- `confidence` is `low`, `medium`, or `high`;
- evidence IDs must belong to the returned snapshot or included reports;
- `sell`, `increase`, `reduce`, and `hold` require an existing portfolio subject;
- `increase` and `buy` targets must exceed an existing subject's current weight;
- `reduce` targets must be below its current weight.

The server rejects publication if the source fingerprint has changed. A successful retry with an already stored generation returns `created=false` and the stored briefing ID.
