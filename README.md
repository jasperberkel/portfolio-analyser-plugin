# Portfolio Analyser Plugin

The package supplies ten native Agent Skills. Each host discovers the name and description from its installed skill files and reads the selected SKILL.md and references on demand. The accompanying stdio MCP server runs two calculations: `build_portfolio_snapshot` reconciles normalized import manifests and `portfolio_exposure` computes direct and indirect weights. Neither starts a model.

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

- `earnings-analysis`: one-off and scheduled earnings previews, comparable actuals, revisions and dated scenarios
- `earnings-monitor`: authenticated stock tracking, delivery modes and the persistent event workflow
- `portfolio-import`: import portfolio documents with their report and continue to analysis with the analysis permission
- `market-discovery-research`: portfolio-independent market radar and up to eight preliminary candidates
- `instrument-research`: facts for assigned holdings or new candidates, with asset-specific evidence
- `valuation-thesis-research`: comparable valuation and durable thesis checks after instrument research
- `portfolio-risk-research`: concentration, fund overlap and existing-plan deviations after holdings research
- `portfolio-strategy`: draft a durable allocation plan and justified next steps from supplied evidence
- `run-analysis`: orchestrate dependent research and atomically publish research, strategy and any plan revision
- `portfolio-analyser-setup`: connect the personal portfolio service; configure profiles or a recurring job when explicitly requested

## Prerequisite

Setup and workflow helpers require Python 3.11 or newer. The host needs native HTTP MCP and the configured service authentication. Browser setup requires a reachable OAuth issuer and compatible client registration.

Import and analysis use a separately authorized private portfolio service. The default local connection is `http://127.0.0.1:8766/mcp`, named `portfolio_analyser`. Ask the host “Richte das Trading-Paket ein”. The existing setup skill starts personal browser sign-in, requesting read, import and publication of analysis reports and investment plans together. The browser confirms completion. A narrower existing grant needs explicit consent before it gains any additional right. A remote host needs a reachable service endpoint.

A complete run needs the six V2 analysis tools, fresh host workers, source access and a writable private workspace. The service stores immutable Markdown plan versions, reports and their original snapshot associations. Holdings changes do not establish executed trades.

## Import a portfolio

Invoke `$portfolio-import` with the portfolio documents (Claude Code: `/portfolio-analyser:portfolio-import`). Once the consolidated snapshot and import report are successfully stored, the skill can continue with `run-analysis` in the same task when the client has analysis permission. This applies to the first import and later uploads, with one follow-up per combined snapshot. An explicit import-only request skips the follow-up. If the analysis fails, the successful import remains stored and the result identifies the failed stage.

## Research and data access

Ask `$market-discovery-research` for general market developments and preliminary candidates. Supply an explicit instrument list for `$instrument-research`, dossiers for `$valuation-thesis-research`, or holdings and instrument evidence for `$portfolio-risk-research`. Standalone skills return drafts; run-analysis alone loads app context and publishes.

The three old research skills are replaced. Existing reports remain archived. Public primary sources are the default. Native MCP providers can later be configured/authenticated in the host, with their tools and fallback rules maintained in one [connector reference](plugins/portfolio-analyser/references/research/connectors.md). No provider subscription, Python connection adapter or proxy is required.

## Secure setup and recurring jobs

After installation, ask Codex or Claude Code:

```text
Richte das Trading-Paket ein.
```

The optional private service uses native authenticated HTTP MCP. The host manages credentials and schedules. After a successful manual run, setup can configure one daily job at the requested time and reconcile existing jobs. The two calculation tools run independently of this setup.

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

The service must expose the V2 context, preparation, publication and detail tools required by the run-analysis skill. Verify a complete manual run before migrating jobs. `.analysis-runs/` contains ignored local progress and drafts; it is not an autonomous recovery daemon.

The explicit graph distinguishes role, task and report. Five research tasks publish four reports: holdings and candidates merge into one instrument report. A coordinated contract change is required to extend the graph. See [orchestration](plugins/portfolio-analyser/references/orchestration.md) and [V2 contract](plugins/portfolio-analyser/references/research-contract-v2.md). This plugin requires the V2 analysis contract.

Shared role playbooks have native Claude adapters and an installer for managed Codex project profiles. Where native role selection is unavailable, workers load the playbooks explicitly. This fallback does not enforce tool isolation. See [host adapters](plugins/portfolio-analyser/references/agent-adapters.md).

## Validation and release

Use Python 3.11+ for the plugin test suite: `python -m unittest discover -s tests`. Scripts require no provider credentials. The API vendors the pure research_contract.py file; an API parity test checks that it matches the plugin copy. Keep both copies synchronized on contract edits.

Adapted Anthropic methods and license are documented in [attribution](plugins/portfolio-analyser/references/anthropic-sources.md).

Existing schedules are switched only after a successful complete native analysis run.

## Application endpoint configuration

The publisher sets `plugins/portfolio-analyser/config/connection.json`. Setup resolves this file
relative to the installed plugin, so it also works from a cache or an unrelated working directory.
Users do not pass a URL. `configure_mcp.py --host codex` (or `--host claude`) starts the native
connection; `--dry-run` previews it without changing client configuration.

The current package uses `environment: development`, `authentication: oauth` and
`http://127.0.0.1:8766/mcp`. For hosted OAuth set `environment: production` and the
actual public HTTPS `mcp_url` in that same publisher-managed file. There is no hosted domain
configured yet. Production mode rejects loopback and HTTP URLs. Invalid packages fail with a
configuration error and never ask the user to repair them by entering an address.

## Publish a versioned branch

From the repository root, run `python3 scripts/publish.py setup` once per clone. This installs the repository-local `git publish` alias and pre-push check. Existing custom hooks require integration before setup.

Commit your changes, then run `git publish`. It targets the current branch’s upstream (default: the same branch name on origin). For an explicit destination use `git publish origin main`. The command fetches the actual push destination, requires a fast-forward, and compares all three manifests. It preserves a higher release version or commits an automatic patch increase based on the remote version. The bump commit contains only the version files. Python wheel metadata derives from the Codex manifest. A successful retry with no new commits leaves the version unchanged.

Plain `git push` uses the pre-push check and rejects a stale version. Run `git publish` for automatic preparation and publication. GitHub Actions independently checks version consistency on branch pushes and against the target of pull requests. Repository administrators can require the `version` check in branch protection for merges.

### Thomas installation and monitoring

Build the wheel with `python3 -m pip wheel --no-deps . -w /tmp/trading-wheels`. In the Thomas checkout, set `THOMAS_CONNECTOR_PORT=8766` and `THOMAS_CONNECTOR_VOLUME=local-mcp-connectors` in the environment before running Compose or updating an existing local setup. Run `python3 infrastructure/always-on/update_package.py --wheel /path/to/the.whl`. The setup skill binds this package through the dashboard. Standalone clients continue to discover the native skills and MCP descriptors.

The wheel owns the monitoring workflow in `scripts/earnings_wake.mjs`, including due checks, research, formatting, delivery preparation and acknowledgement. The personal service checks authority and stores the result. Migration preserves existing private chat IDs and the transcript idempotency keys used before 0.12.1.

Portable host tests and model-routing evals live in `tests/thomas/`. Set `THOMAS_RUNTIME` to the host's `infrastructure/always-on` directory. Run `tests/thomas/tests/test-bundle.sh WHEEL` for the offline gateway and Codex integration. Run `python3 tests/thomas/evals/live.py --help` for the optional real-model runs and their separate transport-only controls. Financial test criteria belong here.
