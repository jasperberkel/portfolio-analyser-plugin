---
name: portfolio-analyser-setup
description: Securely connect the installed Portfolio Analyser plugin to the Portfolio Analyser app and configure one recurring run-analysis job and shared agent profiles. Use when the user asks to set up, connect, prepare, schedule, or automate the plugin in Codex or Claude Code; do not use to run reports immediately or install the app itself.
---

# Portfolio Analyser Setup

Connect the installed plugin through native authenticated HTTP MCP, verify MCP, and configure recurring jobs without creating duplicates. Plugin installation alone is never authorization to connect or create schedules.

## Advisory access and optional app setup

Read this skill through the native skills interface. Verify the separate `portfolio_exposure` and `build_portfolio_snapshot` tools through host tool discovery. The steps below enable optional account-backed workflows and schedules. These require a reachable application, its supported native authentication and user consent. Use the host's own controls for connection, profiles, permissions and scheduling. A hosted agent needs an authenticated reachable MCP endpoint. A local stdio command or loopback URL is usable only from its own machine.

## Detect the host

Determine the current host from the product context and available scheduling tools. Do not ask when it is unambiguous.

- For Codex or ChatGPT desktop scheduling, read [references/codex.md](references/codex.md).
- For Claude Code, read [references/claude-code.md](references/claude-code.md).
- For other hosts, check their OAuth, scheduling and worker support first. Report missing capabilities before attempting the corresponding setup step.

## Connect the private MCP service

Read [connection.json](../../config/connection.json) relative to this installed skill. The packaged local pilot uses a loopback HTTP endpoint and an expiring, operator-issued grant. The operator starts the native host with `TRADING_PORTFOLIO_TOKEN` supplied privately. Never request or print the token. Read access suffices for inspection, import permission for a snapshot with its report, and analysis permission for publishing a run. A combined grant supports the automatic import-to-analysis handoff.

Check native tool discovery first. Reuse a working, operator-configured `portfolio_analyser` connection, including a custom pilot port. For the bundled default, inspect `python3 <plugin-root>/scripts/configure_mcp.py --host codex --dry-run` (or `--host claude`). On explicit setup run it without `--dry-run`. Only replace the named entry when it belongs to this workflow. The registered command references the host environment variable by name. Never pass its value to an agent, shell command line or project file.

For a production package configured with HTTPS/OAuth, use the native client login, client registration and Codex keyring. The loopback pilot has its own grant mechanism. A hosted agent needs an operator-provisioned reachable authenticated service.

Verify native tools and `get_current_positions`. On 401 check host credential provisioning or expiry, on permission denial check the account grant. Use native MCP for portfolio I/O. Connect workers only after the orchestrator can read the service.

## Verify workflow and install profiles

Resolve `<plugin-root>/scripts/workflow.py` and run its discover command. Require run-analysis plus one strategy and the explicit V2 dependency graph with five research tasks; never infer jobs from name suffixes. Verify get_analysis_context, prepare_strategy_context and publish_analysis_run are available on the connected server. Verify all six Run Analysis tools, the import tools when needed, and context contract_version 2 before scheduling.

For Codex, run `python3 <plugin-root>/scripts/install_agent_profiles.py <project-root>` to install/update only the two managed project profiles. Do not overwrite an unmanaged collision. Claude Code uses the plugin's bundled agents. Read [host adapters](../../references/agent-adapters.md) and disclose the instruction-based fallback when native profile selection is unavailable. Agent setup is part of an explicitly requested workflow setup, not a side effect of plugin installation.

## Inspect existing jobs

Use the host scheduling tool and inspect saved jobs first. The single target is:

- Skill: run-analysis
- Canonical prompt marker: `[portfolio-analyser:run-analysis]`
- Display name: `Portfolio Analyser - run-analysis`

Match an existing target by exact canonical marker, exact skill invocation or exact display name. Reuse one unambiguous match; do not create a duplicate. Ask which to keep if multiple target jobs match.

For migration, identify only exact legacy markers or skill invocations for finanzen-news-research, market-opportunity-research, portfolio-position-research, portfolio-briefing and portfolio-strategy, or their exact `Portfolio Analyser - <skill>` names. Also recognize the legacy display names `Portfolio Analyser - Position Research`, `Portfolio Analyser - Market Opportunities`, and `Portfolio Analyser - Briefing`. Preserve unrelated jobs and notification preferences. Do not match vague research/briefing text.

## Verify and migrate the schedule

Default proposal: one complete daily run at 10:00 in the user's detected timezone. Show cadence, timezone, new/existing target and exact legacy jobs to pause. Obtain the user's schedule preference only when it has not already been provided. Plugin installation alone does not authorize schedule creation or changes.

Before switching existing jobs, require a successful complete manual run using the updated app/plugin, confirmed through stored strategy, research and exact plan associations. Fixture tests do not count as a live acceptance run. If it fails, report the stage and preserve the existing automation configuration.

After successful acceptance, create/update the target, preserving applicable notification choices, and pause the identified legacy jobs without deleting them. Avoid an active overlap during the switch: prepare the new target paused, pause legacy jobs, then activate the target. If a scheduler mutation fails, read back actual states and restore the pre-switch configuration where possible; never report a completed migration without verifying it. Do not modify unrelated jobs.

Use the host-specific explicit invocation with this prompt:

```text
[portfolio-analyser:run-analysis]
Run the installed run-analysis skill exactly as defined: load app context, execute ready research tasks in dependency order, parallelizing independent tasks, create portfolio strategy, and publish the complete package atomically. If a required dependency, researcher or publication step fails, preserve drafts and report the failure without publishing a partial package. If the identical daily context already has a successful run, stay quiet. Notify only on a newly completed analysis, a failure, or required user action.
```

Save the confirmed recurrence and timezone. Report the effective single schedule, paused legacy jobs, scheduler type and any host limitation. Do not claim profile isolation on a host that only uses role instructions.
