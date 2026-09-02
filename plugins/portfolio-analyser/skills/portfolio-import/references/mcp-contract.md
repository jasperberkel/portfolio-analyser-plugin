# Portfolio Analyser MCP contract

Use the MCP server named `portfolio_analyser` at `http://127.0.0.1:8010/mcp`.

## Read tools

- `get_current_positions()` returns `{snapshot, positions}`. `snapshot` is `null` before the first import.
- `list_analyses(analysis_type?, since?, limit?)` returns metadata only. Use an ISO-8601 `since` value.
- `get_analysis(id)` returns the complete Markdown report.

## Portfolio publish

Call `publish_portfolio_snapshot_and_analysis(snapshot, positions, analysis)` with the validated snapshot-builder output and:

```json
{
  "analysis": {
    "id": "caller-generated UUID",
    "analysis_type": "portfolio.initial",
    "content_markdown": "complete report"
  }
}
```

The snapshot ID is deterministic and already supplied by the builder. Do not add fields containing source filenames, account identifiers, or extracted raw text. The historical `portfolio.initial` analysis type remains unchanged for app compatibility and is also used for later imports. A retry must reuse both IDs and identical payloads. A conflicting ID is a hard failure.

## Future analysis-only jobs

Scheduled skills use `get_current_positions()` for context and publish exactly one completed Markdown result with `publish_analysis(id, analysis_type, content_markdown)`. They do not create run records, partial reports, or structured research items.
