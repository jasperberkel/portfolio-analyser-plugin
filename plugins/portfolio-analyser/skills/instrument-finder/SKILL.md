---
name: instrument-finder
description: Find specific stocks, ETFs, ETCs or crypto assets worth investigating for potential mispricing. Use for open-ended or scoped investment idea searches, including without a market report or portfolio.
---

# Instrument finder

Start from the user's search question and available public evidence. A request such as “Finde potenziell unterbewertete europäische Industrieaktien” is sufficient. Search issuer filings, product documents and comparable instrument data directly. If a relevant market overview is already supplied, its dated findings and sources can suggest leads. Verify them for the research cutoff. Proceed independently when it is absent or stale. Start even when there is no portfolio, prior radar run or structured screening dataset.

Use the [candidate selection rules](../../references/research/discovery.md), [source routing](../../references/research/connectors.md) and [evidence rules](../../references/research/evidence.md). With a suitable dataset, use [screen_opportunities](../../references/research/structured-tools.md) and state which instruments were actually assessed. Return up to eight identified candidates, each with a sourced preliminary hypothesis, risks, a concrete question for instrument research and a review trigger. Look for potential overvaluation as well as undervaluation when relevant to the request. Zero credible candidates is a valid result.

For a standalone request return a German draft. In a full run, take the search scope from the assigned input. When present, use historical `market_context` for leads and `candidate_history` to revisit open questions or material new evidence. Research current public sources through the assigned cutoff. Use the [V2 draft contract](../../references/research-contract-v2.md) and write the complete German report and `discovery` payload to the assigned result file. The orchestrator passes candidates to instrument research and handles publication. A discovery result creates no personal watch.
