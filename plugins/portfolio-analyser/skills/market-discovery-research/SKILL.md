---
name: market-discovery-research
description: Research general market developments and preliminary investment candidates without portfolio data. Use for market discovery and the radar task in run-analysis.
---

# Markt- und Chancenradar

Research the independent market context and up to eight preliminary candidates. Read [discovery](../../references/research/discovery.md) and [events](../../references/research/events.md). Never receive holdings, allocation targets, portfolio-derived history or strategy follow-up. Prior state is only the radar’s own independent report.

## Input and output

For a workflow task read only the supplied input.json and [V2 draft contract](../../references/research-contract-v2.md). Return a complete German Markdown report and `market` research_data in result.json within the assigned output directory. Do not access sibling task directories, the app, its credentials or publication tools. The orchestrator supplies dependencies and owns publication.

For a standalone request use explicitly supplied data and produce a draft only. If required instrument/dossier/portfolio inputs are missing, request those inputs; never fetch personal app context yourself. Do not fabricate workflow IDs or invoke a full run to satisfy a standalone request.

## Datenzugriff

Before research read the shared [connector reference](../../references/research/connectors.md) and [evidence policy](../../references/research/evidence.md). Choose suitable tools available in this host. Public sources are the working default; optional native MCP access is configured separately. Missing decisive data remain explicit gaps, not invented facts.
