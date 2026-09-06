---
name: valuation-thesis-research
description: Evaluate supplied instrument dossiers for valuation, counterarguments and changes in investment theses. Use after instrument research; not for portfolio allocation.
---

# Bewertung und Thesenprüfung

Read [valuation](../../references/research/valuation.md). Evaluate every assigned instrument using the full upstream dossiers and prior theses. Give distinct health, valuation and thesis_change judgments. Recheck decisive sources or research targeted counterarguments when needed; do not ask another agent to do it. Preserve all supplied thesis IDs, evidence and uncertainty. Retain original dates for unchanged theses. No personal allocation or purchase/sale decision.

## Input and output

For a workflow task read only the supplied input.json and [V2 draft contract](../../references/research-contract-v2.md). Return a complete German Markdown report and `valuation` research_data in result.json within the assigned output directory. Do not access sibling task directories, the app, its credentials or publication tools. The orchestrator supplies dependencies and owns publication.

For a standalone request use explicitly supplied data and produce a draft only. If required instrument/dossier/portfolio inputs are missing, request those inputs; never fetch personal app context yourself. Do not fabricate workflow IDs or invoke a full run to satisfy a standalone request.

## Datenzugriff

Before research read the shared [connector reference](../../references/research/connectors.md) and [evidence policy](../../references/research/evidence.md). Choose suitable tools available in this host. Public sources are the working default; optional native MCP access is configured separately. Missing decisive data remain explicit gaps, not invented facts.
