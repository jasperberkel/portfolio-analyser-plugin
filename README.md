# Portfolio Analyser Plugin

Cross-platform plugin marketplace for Codex and Claude Code. It bundles the Portfolio Analyser workflows while keeping development-only skills in the application repository.

## Included skills

- `portfolio-import`: import and synchronize portfolio documents
- `portfolio-position-research`: research every current position by default, or an explicitly requested subset, with comparable health, valuation, and thesis-change evidence
- `market-opportunity-research`: research up to eight non-personalized market opportunities without a minimum quota
- `finanzen-news-research`: read finanzen.net news and return a sourced German draft
- `portfolio-strategy`: draft a durable allocation plan and justified next steps from supplied evidence
- `run-analysis`: orchestrate parallel research and atomically publish research, strategy and any plan revision
- `portfolio-analyser-setup`: configure shared agent profiles and one recurring full analysis job for Codex or Claude Code

## Prerequisite

The orchestrator and import/setup workflows expect the local [Portfolio Analyser](https://github.com/jasperberkel/portfolio-analyser) application to be running. The plugin includes its MCP bridge and secure pairing flow; no environment token is needed.

The strategy workflow uses Markdown schema 4 (`portfolio-strategy/4`) and requires app migration `0006_analysis_runs`. Update the app alongside the plugin. It maintains immutable Markdown investment-plan versions and publishes a separate German daily report comparing the last successful review with current holdings and research. New statements inform observed progress; prices or weight changes do not prove trades. There is no completion/confirmation feature. Older writers receive an upgrade error.

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
/portfolio-analyser:portfolio-position-research
/portfolio-analyser:market-opportunity-research
/portfolio-analyser:finanzen-news-research
/portfolio-analyser:portfolio-strategy
/portfolio-analyser:run-analysis
/portfolio-analyser:portfolio-analyser-setup
```

## Create a news report

For a news report on demand, ask:

```text
Use $finanzen-news-research to summarize the latest finanzen.net news
and return the German report as a draft.
```

The news skill defaults to the last 24 hours and returns a `news.finanzen-net` draft without requiring portfolio holdings. Only run-analysis loads app data and publishes results.

## Secure setup and recurring jobs

After installation, ask Codex or Claude Code:

```text
Set up Portfolio Analyser and its recurring research and briefing jobs.
```

The setup skill first asks you to generate a five-minute, single-use code under `http://localhost:3000/settings`. Its bundled helper exchanges that code and stores the permanent credential in macOS Keychain, Windows Credential Manager, or Linux Secret Service. The token is never shown in the app or conversation.

After the MCP handshake and a successful complete manual run, setup creates one daily run-analysis job at 10:00 and pauses the exact legacy jobs. It checks existing schedules before changes. Research participation is discovered from explicit workflow.json contracts, not skill-name suffixes.

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

## Orchestrated analysis (plugin 0.7.0)

Invoke `$run-analysis` (Claude Code: `/portfolio-analyser:run-analysis`). It loads a consistent app context, uses Research-Agent workers in parallel, prepares the exact evidence for Strategy-Agent, permits one targeted follow-up round, then atomically publishes all research, strategy and an optional complete plan revision. Every research step is required; one retry is permitted before the run stops without publication.

Research and portfolio-strategy skills always create drafts, including individual invocations. They receive partitioned input files and never connect to the portfolio app. The full strategy reads complete reports, not only worker summaries. The long-term plan changes only with substantive justification.

The app must expose get_analysis_context, prepare_strategy_context and publish_analysis_run (migration 0006_analysis_runs). Update the app before migrating jobs. Existing V4 reads/writes and historical report/plan associations remain supported. `.analysis-runs/` contains ignored local progress and drafts; it is not an autonomous recovery daemon.

To add research, add a focused skill plus workflow.json declaring contract_version, skill, research stage, supported required inputs and unique output type. See [orchestration](plugins/portfolio-analyser/references/orchestration.md) and [draft contract](plugins/portfolio-analyser/references/draft-contract.md). Compatible additions require no orchestrator edits.

Shared role playbooks have native Claude adapters and an installer for managed Codex project profiles. Where native role selection is unavailable, workers load the playbooks explicitly. This fallback does not enforce tool isolation. See [host adapters](plugins/portfolio-analyser/references/agent-adapters.md).
