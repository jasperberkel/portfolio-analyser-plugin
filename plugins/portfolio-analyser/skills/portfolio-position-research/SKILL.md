---
name: portfolio-position-research
description: Select current positions from the local Portfolio Analyser via MCP, research their latest health, outlook, risks, catalysts, and news online, and publish a sourced German report. Use for top, bottom, all, or explicitly named portfolio-position research; do not use without a portfolio in the app.
---

# Portfolio Position Research

Research a user-selected subset of the current portfolio and produce one current, evidence-based German report in the local Portfolio Analyser app.

## Select positions

1. Read [references/mcp-contract.md](references/mcp-contract.md), then call `get_current_positions`. Stop if the app has no snapshot or positions.
2. Resolve the selector from the invoking prompt:
   - no selector: the five largest positions;
   - `alle` / `all`: every position;
   - `Top N` / `größte N`: the N highest market values;
   - `Bottom N` / `kleinste N`: the N lowest market values;
   - names, ISINs, or symbols: exactly those positions.
3. Compare market values as decimals. For equal values, sort by ISIN, symbol, then name. Match explicit identifiers before names; require an unambiguous name match. Ask only when an explicit selector is ambiguous or absent from the current portfolio.
4. Record the snapshot date, portfolio total, selected market values, and each selected position's portfolio weight. Never substitute a different position silently.

## Research current evidence

Always browse for every selected position, even when a previous report exists. Use the invocation date as the research cutoff and the default outlook horizon of 6–12 months unless the user specifies another horizon.

Read [references/research-rubric.md](references/research-rubric.md). Prefer dated issuer, fund-provider, exchange, filing, protocol-foundation, and regulator sources. Research the latest results or product facts plus material news, guidance, catalysts, and risks. If no material recent news exists, state that rather than filling the gap with speculation.

Distinguish:

- **Fakten:** observable portfolio and source data;
- **Einordnung:** what the evidence suggests about current health;
- **Ausblick:** a conditional direction with confidence and upside/downside drivers.

Do not treat price momentum as business health, issue buy/sell orders, promise returns, or present the report as suitability advice.

## Report and publish

Write one self-contained German Markdown report. Include the selector, snapshot date, research cutoff, source links, a concise portfolio-level synthesis, and a section for every selected position. Explicitly answer:

- Was ist zuletzt passiert?
- Wie robust, gemischt, angespannt oder spekulativ ist die Position aktuell, und warum?
- Welche Faktoren könnten sie im gewählten Zeitraum stärken oder schwächen?
- Ist die evidenzbasierte Tendenz eher positiv, gemischt oder negativ, und wie hoch ist die Konfidenz?

Generate one analysis UUID and call `publish_analysis` exactly once with analysis type `portfolio.position-research` after the complete report is ready. Invoking this skill authorizes publication to the local app unless the user explicitly asks for a conversation-only report. Retry a transport-uncertain publish at most once with the same UUID and identical content.
