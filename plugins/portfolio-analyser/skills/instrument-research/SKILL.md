---
name: instrument-research
description: Research facts for an explicitly supplied instrument list, including stocks, ETFs/ETCs and crypto. Use for holdings or discovered candidates; not personal allocation decisions.
---

# Instrumentenresearch

Investigate every supplied instrument using [asset evidence](../../references/research/asset-evidence.md). For corporate results read [earnings](../../references/research/earnings.md); for tracked or upcoming events read [events](../../references/research/events.md). Supply dated facts, strengths, weaknesses and gaps, without final valuation or allocations. Carry neutral candidate hypotheses into hypotheses. Do not expand scope to unassigned investment candidates. Contextual peer facts may be included within an assigned dossier. Preserve instrument identities and previous events.

## Input and output

For a workflow task read only the supplied input.json and [V2 draft contract](../../references/research-contract-v2.md). Return a complete German Markdown report and `instruments` research_data in result.json within the assigned output directory. Do not access sibling task directories, the app, its credentials or publication tools. The orchestrator supplies dependencies and owns publication.

For a standalone request use explicitly supplied data and produce a draft only. If required instrument/dossier/portfolio inputs are missing, request those inputs; never fetch personal app context yourself. Do not fabricate workflow IDs or invoke a full run to satisfy a standalone request.

## Datenzugriff

Before research read the shared [connector reference](../../references/research/connectors.md) and [evidence policy](../../references/research/evidence.md). Choose suitable tools available in this host. Public sources are the working default; optional native MCP access is configured separately. Missing decisive data remain explicit gaps, not invented facts.
