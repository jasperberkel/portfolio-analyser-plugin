---
name: market-radar
description: Explain material market and sector developments, what has changed since the previous radar and which markets may be affected. Use for a market overview.
---

# Market radar

Produce a German market overview using the host's available public sources. Cover developments with plausible effects across sectors or asset classes. Read the [radar methodology](../../references/research/market-radar.md), [source routing](../../references/research/connectors.md) and [evidence rules](../../references/research/evidence.md). Include dates, primary sources, uncertainties and the distinction between observed facts and inferred effects. Keep instrument selection in the [instrument finder](../instrument-finder/SKILL.md).

A standalone request can start with a topic or a general market question. Return a draft. When a previous overview is available, use it as a comparison baseline. A first overview establishes its own baseline from current sources.

In a full run, read the assigned input and the [V2 draft contract](../../references/research-contract-v2.md). Compare reporting through `research_cutoff` with `previous_state.context_markdown` when present. Include the same nonempty section headed `## Marktrelevante Änderungen seit dem letzten Radar` in both `content_markdown` and `research_data.context_markdown`. Retain dated, still-relevant observations in the saved context. Write the complete report and the `radar` payload to the assigned result file. The orchestrator handles private app access and publication.
