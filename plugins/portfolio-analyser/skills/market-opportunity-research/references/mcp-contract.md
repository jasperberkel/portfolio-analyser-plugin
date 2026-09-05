# Portfolio Analyser MCP publishing contract

Use the MCP server named `portfolio_analyser` at `http://127.0.0.1:8010/mcp`.

This skill is portfolio-independent:

- do not call `get_current_positions`;
- do not call `publish_portfolio_snapshot_and_analysis`;
- do not create or modify snapshots or positions.

For comparison, call `list_analyses(analysis_type="market.opportunity-research", limit=1)` and read the returned report with `get_analysis(id="<returned UUID>")` when available. Metadata is newest first. Use only this portfolio-independent report as the baseline, never portfolio holdings. No prior report or a read failure is a comparison gap; continue current research and do not claim that the thesis is unchanged without a baseline.

After completing the sourced German report, call:

```text
publish_analysis(
  id="<caller-generated UUID>",
  analysis_type="market.opportunity-research",
  content_markdown="<complete Markdown report>"
)
```

Publish exactly once. A transport-uncertain retry must reuse the same UUID and identical content. A conflicting UUID is a hard failure.
