---
name: portfolio-risk-research
description: Analyze concentration, fund overlap and existing plan deviations using supplied holdings and instrument evidence. Use after holdings research; not to set new portfolio targets.
---

# Portfolio-Struktur und Risiko

Read [portfolio risk](../../references/research/portfolio-risk.md). Use supplied current_portfolio, plan, holdings dossiers and calculations. Explain meaningful risks and unknown exposure, with one item per supplied instrument plus portfolio-level findings. Copy calculations exactly; they were computed deterministically. Cash-only portfolios still receive a portfolio-level report. Do not set targets or draft a competing plan.

## Input and output

For a workflow task read only the supplied input.json and [V2 draft contract](../../references/research-contract-v2.md). Return a complete German Markdown report and `risk` research_data in result.json within the assigned output directory. Do not access sibling task directories, the app, its credentials or publication tools. The orchestrator supplies dependencies and owns publication.

For a standalone request use explicitly supplied data and produce a draft only. If required instrument/dossier/portfolio inputs are missing, request those inputs; never fetch personal app context yourself. Do not fabricate workflow IDs or invoke a full run to satisfy a standalone request.

## Datenzugriff

Before research read the shared [connector reference](../../references/research/connectors.md) and [evidence policy](../../references/research/evidence.md). Choose suitable tools available in this host. Public sources are the working default; optional native MCP access is configured separately. Missing decisive data remain explicit gaps, not invented facts.
