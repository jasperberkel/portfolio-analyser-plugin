# Portfolio Analyser MCP publishing contract

Use the MCP server named `portfolio_analyser` at `http://127.0.0.1:8010/mcp`.

This skill is portfolio-independent:

- do not call `get_current_positions`;
- do not call `publish_portfolio_snapshot_and_analysis`;
- do not create or modify snapshots or positions.

After completing the sourced German report, call:

```text
publish_analysis(
  id="<caller-generated UUID>",
  analysis_type="market.opportunity-research",
  content_markdown="<complete Markdown report>"
)
```

Publish exactly once. A transport-uncertain retry must reuse the same UUID and identical content. A conflicting UUID is a hard failure.

