# News report MCP contract

Use the configured MCP server named `portfolio_analyser` (default local endpoint: `http://127.0.0.1:8010/mcp`). Discover its tools if they are not already loaded; the host may prefix their names. Use the MCP tools rather than direct database writes or an invented reports endpoint.

The app stores reports as analyses. No separate registration of `news.finanzen-net` is needed. This workflow requires no portfolio snapshot and does not change positions, report settings, or schedules.

## Publish the complete report

Generate one UUID for this report and call `publish_analysis` with exactly these arguments:

```text
publish_analysis(
  id="<caller-generated UUID>",
  analysis_type="news.finanzen-net",
  content_markdown="<complete German Markdown report with source links>"
)
```

- `id`: a valid UUID, retained unchanged for recovery.
- `analysis_type`: always `news.finanzen-net`; put dates and topics in the report, not in the type.
- `content_markdown`: the full report as a string, containing visible content and at most 2,000,000 characters. Do not send a file path, summary, or JSON-encoded document in place of the Markdown.

Success returns `{ "id": "<UUID>", "created": true }`. An identical repeat returns the same ID with `created: false`, which is also success. The same UUID with different type or content is a conflict.

## Verify and recover

After a successful publish, call `get_analysis(id="<same UUID>")`. Confirm that its `id`, `analysis_type`, and `content_markdown` match the submitted report. The response also contains the server-assigned `created_at` timestamp.

Create at most one stored report per invocation:

- If the publish response is lost or times out, first try `get_analysis` with the same UUID. A matching report confirms success.
- If the report is absent or its storage status remains unknown because of a transport failure, retry publication at most once with the same UUID and identical arguments. Verify any successful retry by reading it back.
- A validation error, authorization error, UUID conflict, or mismatched read-back is a hard failure. Explain it; do not generate a replacement UUID or change the payload to bypass the error.
- If a successful write is confirmed but read-back fails, report that verification is incomplete and do not republish. If storage status remains unknown after recovery, retain the UUID and report that uncertainty.
- If the MCP tools or server are unavailable, return or save the completed report for later upload and state the blocker. Never claim a successful upload without confirmation.

Do not call `publish_portfolio_snapshot_and_analysis`, `get_dashboard_context`, or `publish_dashboard_briefing` for this standalone news report.
