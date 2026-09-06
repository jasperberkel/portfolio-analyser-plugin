# Portfolio Analyser Plugin

Cross-platform plugin marketplace for Codex and Claude Code. It bundles the Portfolio Analyser workflows while keeping development-only skills in the application repository.

## Included skills

- `portfolio-import`: import and synchronize portfolio documents, then automatically run the complete research and strategy analysis
- `market-discovery-research`: portfolio-independent market radar and up to eight preliminary candidates
- `instrument-research`: facts for assigned holdings or new candidates, with asset-specific evidence
- `valuation-thesis-research`: comparable valuation and durable thesis checks after instrument research
- `portfolio-risk-research`: concentration, fund overlap and existing-plan deviations after holdings research
- `portfolio-strategy`: draft a durable allocation plan and justified next steps from supplied evidence
- `run-analysis`: orchestrate dependent research and atomically publish research, strategy and any plan revision
- `portfolio-analyser-setup`: configure shared agent profiles and one recurring full analysis job for Codex or Claude Code

## Prerequisite

The orchestrator and import/setup workflows expect the local [Portfolio Analyser](https://github.com/jasperberkel/portfolio-analyser) application to be running. The plugin includes its MCP bridge and secure pairing flow; no environment token is needed.

The strategy workflow uses Markdown schema 4 (`portfolio-strategy/4`) and requires app migration `0007_research_v2`. Update the app alongside the plugin. It maintains immutable Markdown investment-plan versions and publishes a separate German daily report comparing the last successful review with current holdings and research. New statements inform observed progress; prices or weight changes do not prove trades. There is no completion/confirmation feature. Older writers receive an upgrade error.

## Install in Codex

Add the GitHub marketplace:

```bash
codex plugin marketplace add jasperberkel/portfolio-analyser-plugin
```

Start Codex, open `/plugins`, install **Portfolio Analyser**, and start a new session.

## Install in Claude Code

```bash
claude plugin marketplace add jasperberkel/portfolio-analyser-plugin
claude plugin install portfolio-analyser@portfolio-analyser
```

In Claude Code, skills are available under the plugin namespace, for example:

```text
/portfolio-analyser:portfolio-import
/portfolio-analyser:market-discovery-research
/portfolio-analyser:instrument-research
/portfolio-analyser:valuation-thesis-research
/portfolio-analyser:portfolio-risk-research
/portfolio-analyser:portfolio-strategy
/portfolio-analyser:run-analysis
/portfolio-analyser:portfolio-analyser-setup
```

## Import a portfolio

Invoke `$portfolio-import` with the portfolio documents (Claude Code: `/portfolio-analyser:portfolio-import`). Once the consolidated snapshot and import report are successfully stored, the skill automatically continues with `run-analysis` in the same task. This applies to the first import and later uploads, with one follow-up per combined snapshot. An explicit import-only request skips the follow-up. If the analysis fails, the successful import remains stored and the result identifies the failed stage.

## Research and data access

Ask `$market-discovery-research` for general market developments and preliminary candidates. Supply an explicit instrument list for `$instrument-research`, dossiers for `$valuation-thesis-research`, or holdings and instrument evidence for `$portfolio-risk-research`. Standalone skills return drafts; run-analysis alone loads app context and publishes.

The three old research skills are replaced. Existing reports remain archived. Public primary sources are the default. Native MCP providers can later be configured/authenticated in the host, with their tools and fallback rules maintained in one [connector reference](plugins/portfolio-analyser/references/research/connectors.md). No provider subscription, Python connection adapter or proxy is required.

## Secure setup and recurring jobs

After installation, ask Codex or Claude Code:

```text
Set up Portfolio Analyser and its recurring research and briefing jobs.
```

The setup skill first asks you to generate a five-minute, single-use code under `http://localhost:3000/settings`. Its bundled helper exchanges that code and stores the permanent credential in macOS Keychain, Windows Credential Manager, or Linux Secret Service. The token is never shown in the app or conversation.

After the MCP handshake and a successful complete manual run, setup creates one daily run-analysis job at 10:00 and pauses the exact legacy jobs. It checks existing schedules before changes. Research participation is defined by the plugin-root V2 workflow.json graph.

Linux requires an installed and unlocked Secret Service such as GNOME Keyring. The setup fails safely instead of writing credentials to a plaintext file.

## Ask an agent to install it

Paste this repository URL into Codex or Claude Code and ask:

```text
Install the Portfolio Analyser plugin marketplace from
https://github.com/jasperberkel/portfolio-analyser-plugin
and install its portfolio-analyser plugin.
```

## Repository layout

```text
.agents/plugins/marketplace.json          Codex marketplace
.claude-plugin/marketplace.json           Claude Code marketplace
plugins/portfolio-analyser/
  .codex-plugin/plugin.json               Codex manifest
  .claude-plugin/plugin.json              Claude Code manifest
  .mcp.json                               Codex MCP descriptor
  .claude-plugin/plugin.json              Claude MCP descriptor and manifest
  bin/                                    Bundled platform binaries
  skills/                                 Shared Agent Skills
```

## Orchestrated analysis (plugin 0.8.0)

Invoke `$run-analysis` (Claude Code: `/portfolio-analyser:run-analysis`). It loads a consistent app context, starts independent market and holdings work concurrently, then schedules candidates, valuation and risk by dependency readiness, prepares the exact evidence for Strategy-Agent, permits one targeted follow-up round, then atomically publishes all research, strategy and an optional complete plan revision. Every research step is required; one retry is permitted before the run stops without publication.

Research and portfolio-strategy skills always create drafts, including individual invocations. They receive partitioned input files and never connect to the portfolio app. The full strategy reads complete reports, not only worker summaries. The long-term plan changes only with substantive justification.

The app must expose get_analysis_context, prepare_strategy_context and publish_analysis_run (migration 0007_research_v2). Update the app before migrating jobs. Existing V4 reads/writes and historical report/plan associations remain supported. `.analysis-runs/` contains ignored local progress and drafts; it is not an autonomous recovery daemon.

The explicit graph distinguishes role, task and report. Five research tasks publish four reports: holdings and candidates merge into one instrument report. A coordinated contract change is required to extend the graph. See [orchestration](plugins/portfolio-analyser/references/orchestration.md) and [V2 contract](plugins/portfolio-analyser/references/research-contract-v2.md). The app supports V1 and V2; this plugin requires V2 and never silently downgrades.

Shared role playbooks have native Claude adapters and an installer for managed Codex project profiles. Where native role selection is unavailable, workers load the playbooks explicitly. This fallback does not enforce tool isolation. See [host adapters](plugins/portfolio-analyser/references/agent-adapters.md).

## Validation and release

Use Python 3.11+ for the plugin test suite: `python -m unittest discover -s tests`. Scripts require no provider credentials. The API vendors the pure research_contract.py file; an API parity test checks that it matches the plugin copy. Keep both copies synchronized on contract edits.

Upgrade the app through migration 0007 before installing plugin 0.8.0. The four core reports share one research.core preference: existing exclusions and the strictest age limit are retained. Both Markdown and structured evidence are excluded together. Additional independent reports remain selectable. Existing schedules are not changed by the release; setup handles explicitly requested schedule migrations.

Adapted Anthropic methods and license are documented in [attribution](plugins/portfolio-analyser/references/anthropic-sources.md). No upstream agent runtime is installed.
