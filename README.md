# Portfolio Analyser Plugin

The package supplies eight native Agent Skills. Each host discovers the name and description from its installed skill files and reads the selected SKILL.md and references on demand. The accompanying stdio MCP server runs two calculations: `build_portfolio_snapshot` reconciles normalized import manifests and `portfolio_exposure` computes direct and indirect weights. Neither starts a model.

## Local host installation

From this checkout, with `uv` available on the host PATH and Python 3.11+ available to it, run the commands for your host. Installing the plugin registers both its native skills and its local calculation server. The first tool call can download Python dependencies. Open a fresh session after installation.

**Codex**

```sh
codex plugin marketplace add "$PWD"
codex plugin add portfolio-analyser@portfolio-analyser
```

**Claude Code**

```sh
claude plugin marketplace add "$PWD"
claude plugin install portfolio-analyser@portfolio-analyser
```

For a local update, advance this checkout and install the new plugin version in Codex, or run `claude plugin update portfolio-analyser@portfolio-analyser` in Claude Code. Use the matching host's plugin inspection to check the effective version.

## Calculation-only MCP clients

In a Python 3.11+ virtual environment:

```sh
python -m pip install .
portfolio-advisory --help
python tests/smoke_advisory_mcp.py
```

Register the installed `portfolio-advisory` executable as the client's stdio command. Such clients receive the two tools. A host must also support native Agent Skills to use the research instructions. App publication requires an authorized app connection. Research requires the host's evidence sources, import requires attachment access, and full runs also need writable task storage and workers. A remote client requires an authenticated reachable connection supplied by its operator.

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

Setup and workflow helpers require Python 3.11 or newer. Native Codex/Claude Code must support HTTP MCP, OAuth and preregistered public client IDs.

The orchestrator and import/setup workflows expect the configured [Portfolio Analyser](https://github.com/jasperberkel/portfolio-analyser) application to be running. Run the setup skill to connect using native HTTP MCP and OAuth. The plugin supplies the application address automatically; users only sign in and approve access. The client securely stores its tokens; there is no bridge, connection code, PAT or shell fallback.

The strategy workflow uses Markdown schema 4 (`portfolio-strategy/4`) and requires app migration `0008_users_and_portfolios`. Update the app alongside the plugin. It maintains immutable Markdown investment-plan versions and publishes a separate German daily report comparing the last successful review with current holdings and research. New statements inform observed progress; prices or weight changes do not prove trades. There is no completion/confirmation feature. Older writers receive an upgrade error.

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

The optional app workflow uses native HTTP MCP and OAuth. The host manages credentials and schedules. After a successful manual run, setup can configure one daily job at the requested time and reconcile existing jobs. The two calculation tools run independently of this setup.

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
  scripts/advisory_mcp.py                 Standalone advisory MCP server
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

Version 0.9.0 requires the multi-user app migration `0008_users_and_portfolios`. Run the setup skill and sign in to a verified account; no address entry is needed. Existing schedules are switched only after a successful complete native analysis run.

## Application endpoint configuration

The publisher sets `plugins/portfolio-analyser/config/connection.json`. Setup resolves this file
relative to the installed plugin, so it also works from a cache or an unrelated working directory.
Users do not pass a URL. `configure_mcp.py --host codex` (or `--host claude`) starts the native
connection; `--dry-run` previews it without changing client configuration.

The current package explicitly uses `environment: development` and the local app at
`http://localhost:3300/mcp`. Before a hosted release, set `environment: production` and the
actual public HTTPS `mcp_url` in that same publisher-managed file. There is no hosted domain
configured yet. Production mode rejects loopback and HTTP URLs. Invalid packages fail with a
configuration error and never ask the user to repair them by entering an address.
