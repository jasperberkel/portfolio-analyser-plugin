---
name: market-opportunity-research
description: Research current non-personalized market opportunities across listed stocks, retail-accessible ETFs and ETCs, major crypto assets, and commodities, then draft a sourced German watchlist report. Use for general investment ideas and market screens; do not inspect or tailor conclusions to the user's portfolio.
---

# Market Opportunity Research

Create a current, evidence-based German market-opportunity report without reading or considering the user's portfolio.

## Define the scan

Use constraints from the invoking prompt: asset classes, regions, themes, horizon, risk level, number of candidates, exclusions, and whether broker availability must be verified.

When the user gives no constraints:

- scan listed stocks, UCITS ETFs or retail-accessible ETCs, major crypto assets, and commodities;
- cover near-term (0–6 months), medium-term (6–24 months), and long-term (2–7 years) theses;
- produce a compact shortlist of up to 8 candidates, with no minimum; fewer or no convincing opportunities is a valid result;
- exclude leverage products, CFDs, options, penny stocks, illiquid tokens, and private securities.

Do not call `get_current_positions` or otherwise personalize the scan from portfolio data.

## Discover and verify candidates

Read [references/research-rubric.md](references/research-rubric.md). Always browse using the invocation date as the research cutoff. Read [the shared draft contract](../../references/draft-contract.md) and the supplied `previous_report` when available, to distinguish changed evidence from a repeated thesis; no prior report is a comparison gap, not proof of no change.

Start with a broad evidence scan before choosing candidates. Identify current macro, industry, regulatory, supply/demand, technology, and capital-market developments. Then verify every shortlisted instrument independently.

Compare genuinely different economic drivers, not just several beneficiaries of one popular theme. Resolve the decision-critical valuation or product-economics checks for the strongest candidates during this research run; prefer fewer well-supported candidates to a longer list that defers every decisive check. Remain portfolio-independent and do not manufacture a candidate or purchase signal to fill a category.

Prefer primary sources: issuer filings and results, fund-provider product pages and KIDs, exchanges, central banks, regulators, statistical agencies, protocol foundations, and commodity or energy agencies. Use reputable independent reporting for material events that primary sources do not establish or when outside scrutiny is necessary.

For each candidate:

- establish the exact name, ticker or ISIN, asset type, and investment vehicle;
- check recent news and the newest available fundamental, fund, protocol, or supply/demand evidence;
- evaluate thesis quality, valuation or product structure, liquidity, catalysts, risks, and invalidation conditions;
- distinguish operating/protocol strength from dated price attractiveness; identify the strongest counterargument, a reason against acting now, and what actually changed;
- assign a horizon, risk level, evidence-based tendency, and confidence;
- verify Trade Republic or another named broker's availability only from a reliable current source. Otherwise say that broker availability was not verified.

Treat “Geheimtipps” as a separate speculative-radar category. Require public tradability, adequate liquidity, credible disclosures, and an evidence-backed thesis. Never use rumors, social-media hype, promotional token claims, or low-float price action as the thesis.

## Write the report

Write one self-contained German Markdown report with inline source links. Include:

- scope, research cutoff, horizons, and material limitations;
- current market context;
- a ranked shortlist with identifiers, thesis, horizon, catalyst, principal risk, tendency, and confidence;
- a detailed section for every candidate;
- a separate speculative-radar section when justified;
- rejected or watch-only themes when current evidence does not support inclusion;
- cross-candidate risks and concrete events or metrics to monitor.

Separate observable facts, interpretation, and conditional scenarios. Use base, upside, and downside cases. Do not issue buy/sell orders, promise returns, imply that a candidate is suitable for the user, or use unsupported price targets. “Interessant” means worthy of further research, not a recommendation. Explicitly distinguish watch-only ideas from any evidence of current price attractiveness; a watchlist place or positive business outlook must not become a downstream purchase signal by itself. Separately state whether the evidence supports comparing a structural role (for example broad exposure or short-duration liquidity), even without an underpricing thesis. Name any unresolved blocker as a research gap, not an assignment to the user or proof that the investment is bad.

## Return the draft

Return the complete report using the shared draft contract. Never access Portfolio Analyser MCP, publish, or invoke run-analysis yourself. Use the supplied run/report IDs in orchestrated runs. A missing prior report is an explicit comparison gap and does not prevent fresh research.
