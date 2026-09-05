---
name: portfolio-position-research
description: Research all current portfolio positions by default, or an explicitly selected subset, using supplied holdings and current sources. Draft comparable health, valuation, thesis-change, and risk evidence in German; requires supplied portfolio data.
---

# Portfolio Position Research

Research the current portfolio and produce one current, evidence-based German report from supplied portfolio data. Cover every position unless the user explicitly selects a subset.

## Select positions

1. Read [the shared draft contract](../../references/draft-contract.md). Use supplied `current_portfolio`; stop and name missing data when the snapshot or required position list is absent (an explicitly empty list is valid for a cash-only portfolio). Never use Portfolio Analyser MCP or invoke run-analysis yourself.
2. Resolve the selector from the invoking prompt:
   - no selector: every position;
   - `alle` / `all`: every position;
   - `Top N` / `größte N`: the N highest market values;
   - `Bottom N` / `kleinste N`: the N lowest market values;
   - names, ISINs, or symbols: exactly those positions.
3. Compare market values as decimals. For equal values, sort by ISIN, symbol, then name. Match explicit identifiers before names; require an unambiguous name match. Ask only when an explicit selector is ambiguous or absent from the current portfolio.
4. Record the snapshot date, portfolio total, selected market values, and each selected position's portfolio weight. Never substitute a different position silently.
5. Read the supplied `previous_report` when available, to distinguish new evidence from an unchanged thesis. A missing comparison is not evidence of no change.

For a cash-only portfolio, state that no instruments are held, record the snapshot cash and return complete zero-position coverage. Do not invent holdings to research.

## Research current evidence

Always browse for every selected position, even when a previous report exists. Use the invocation date as the research cutoff and the default outlook horizon of 6–12 months unless the user specifies another horizon.

Read [references/research-rubric.md](references/research-rubric.md). Apply the same decision-relevant checks to every selected position, including smaller positions; do not silently reduce an all-positions run to the largest holdings. Reuse shared sources and keep each section compact. If coverage cannot be completed, label the report partial and enumerate uncovered positions rather than treating them as healthy or held.

Compare relevant holdings within common risk groups, such as BTC and ETH or overlapping US-tech shares and ETFs. Explain whether any difference rests on instrument evidence, portfolio concentration, or missing data; a larger holding is not automatically the worse investment. Explicit subset requests remain exact: name unresearched alternatives as gaps, without expanding the research silently.

Distinguish:

- **Fakten:** observable portfolio and source data;
- **Einordnung:** operating/protocol health, distinct from dated valuation or price attractiveness;
- **Ausblick:** conditional prospects, changes versus the prior thesis, counterevidence, and any evidence-based urgency.

Do not treat price momentum as business health, issue buy/sell orders, promise returns, or present the report as suitability advice.

## Report and return

Write one self-contained German Markdown report. Include the selector, snapshot date, research cutoff, source links, a concise portfolio-level synthesis, and a section for every selected position. Explicitly answer:

- Was ist zuletzt passiert?
- Wie robust, gemischt, angespannt oder spekulativ ist die Position aktuell, und warum?
- Welche Faktoren könnten sie im gewählten Zeitraum stärken oder schwächen?
- Was lässt sich über die aktuelle Bewertung sagen, was ist gegenüber dem Vorbericht neu, und welches Gegenargument spricht gegen eine Änderung?
- Ist ein dringlicher neuer Befund belegt oder geht es nur um längerfristige Konzentration? Welche Evidenz fehlt?

End with a compact cross-position synthesis of common risks, relevant alternatives, and research limits. Research does not choose allocation targets or trade sizes; an outlook horizon is not an execution deadline.

Before publication, check the completed report against the selected snapshot identifiers: every selected position must appear once in its own section heading with its ISIN, symbol, or unambiguous name. Include a short coverage checklist with selected/researched/uncovered counts and any uncovered identifiers. An all-positions report is complete only when every selected position has current-source research; unavailable evidence must be an explicit gap, not an omitted position.

Return the complete draft using the shared contract. In orchestrated runs cover all supplied positions and copy `run_id`, `report_id` and `snapshot_id` from the task. Single invocations may use an explicit subset, but still return only a draft. Publication is the orchestrator's responsibility.
