---
name: portfolio-briefing
description: Consolidate the current portfolio and the latest enabled app reports into direct, evidence-linked portfolio actions and publish a structured portfolio briefing. Use when the user asks to create or refresh portfolio recommendations; do not use for standalone research reports.
---

# Portfolio Briefing

Create one structured German portfolio briefing from the exact context selected by the local Portfolio Analyser. The output contract is independent of where or how the app presents it.

## Load the context

Read [references/mcp-contract.md](references/mcp-contract.md), then call `get_dashboard_context` exactly once.

Stop without publishing when the app has no current portfolio, rejects the combined report size, or returns an `existing_briefing_id`. In the last case, tell the user that a portfolio briefing already reflects the current portfolio, reports, and settings.

Use only the returned snapshot, positions, reports, and deterministic weights. Do not browse, refresh research, truncate reports, or infer information from reports listed under `excluded_reports`. Mention material evidence gaps in the summary.

## Decide concrete actions

Produce a concise portfolio-level summary and 1–10 prioritized actions in German. Direct `buy`, `sell`, `increase`, `reduce`, `hold`, and `rebalance` proposals are allowed. Every non-`hold` action must state an exact final portfolio weight.

Existing positions may be referenced by their returned `position_id`, ISIN, or symbol. Recommend a new instrument only when a returned report identifies and supports it; include its ISIN or symbol. Resolve conflicting reports explicitly in the rationale instead of silently choosing one view.

Every action needs evidence from the current snapshot, one or more included analyses, or both. Never reference an excluded or absent analysis. Do not claim live prices, promise returns, or execute an order.

## Publish once

Validate the complete payload against the contract before writing. Generate one UUID and call `publish_dashboard_briefing` exactly once with:

- `generator="codex_skill"`
- `generator_version="portfolio-briefing/1"`
- `schema_version=1`
- the unchanged `source_fingerprint` returned by `get_dashboard_context`

Retry a transport-uncertain publication at most once with the same UUID and identical payload. A changed-context or validation error is a hard failure; report it without publishing a replacement.
