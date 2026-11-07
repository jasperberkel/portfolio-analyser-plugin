---
name: portfolio-analyser-setup
description: Securely connect the installed Portfolio Analyser plugin to the Portfolio Analyser app and configure one recurring run-analysis job and shared agent profiles. Use when the user asks to set up, connect, prepare, schedule, or automate the plugin in Codex or Claude Code; do not use to run reports immediately or install the app itself.
---

# Portfolio Analyser Setup

Connect the installed plugin through native HTTP MCP and OAuth, verify MCP, and configure recurring jobs without creating duplicates. Plugin installation alone is never authorization to connect or create schedules.

## Advisory access and optional app setup

Read this skill through the native skills interface. Verify the separate `portfolio_exposure` and `build_portfolio_snapshot` tools through host tool discovery. The steps below enable optional account-backed workflows and schedules. These require a reachable application, its OAuth-capable client and user consent. Use the host's own controls for connection, profiles, permissions and scheduling. A hosted agent needs an authenticated reachable MCP endpoint. A local stdio command or loopback URL is usable only from its own machine.

## Detect the host

Determine the current host from the product context and available scheduling tools. Do not ask when it is unambiguous.

- For Codex or ChatGPT desktop scheduling, read [references/codex.md](references/codex.md).
- For Claude Code, read [references/claude-code.md](references/claude-code.md).
- For other hosts, check their OAuth, scheduling and worker support first. Report missing capabilities before attempting the corresponding setup step.

## Connect through native OAuth

The plugin already knows the application's MCP address through the [application configuration](../../config/connection.json).
Never ask users for the application URL, tokens, passwords or connection codes.
Resolve the installed plugin root from this skill's location; do not derive the address from the
working directory, browser, previous chat or another installation.

Run `python3 <plugin-root>/scripts/configure_mcp.py --host codex --dry-run`
(or `--host claude`) to inspect the configured native connection without modifying anything.
The bundled development configuration targets the current local app; production packages must
contain their public HTTPS address. A missing or invalid configuration is a packaging error:
report it and stop, rather than asking the user to supply a URL or trying another installation.

The optional app connection is separate from the read-only advisory tools.
Run `python3 <plugin-root>/scripts/configure_mcp.py --host codex`
(or `--host claude`). This registers exactly one native HTTP entry named `portfolio_analyser`
and opens the native client's OAuth browser login for the configured application.
Only use a supported client version with native HTTP OAuth and preregistered client IDs.
The user signs into their own verified account and explicitly allows the requested scopes.
For Codex the script explicitly sets `mcp_oauth_credentials_store = "keyring"`.
If the system keyring is unavailable, report this client requirement; never select plaintext storage.

Before changing an existing entry, inspect whether it already has the bundled URL and expected client ID.
If it matches and its native tools work, reuse it without running setup again.
Remove only an old Portfolio Analyser bridge entry that belongs to this plugin when upgrading.
Do not touch unrelated MCP servers, schedules or credentials. Never inspect the OAuth token store.

Verify the tools using the host's native tool discovery and `get_current_positions`.
If tools are absent: report the server name, URL, client connection status and whether login or
client reload is needed. If the request fails with 401, use the client's native OAuth login;
403 means missing permission/unverified account; 503 means the auth service cannot be reached.
No shell MCP calls, bridge, direct HTTP tool requests, PATs or environment-token fallbacks are supported.
Do not create or switch schedules until native tools actually work in the host.

## Verify workflow and install profiles

Resolve `<plugin-root>/scripts/workflow.py` and run its discover command. Require run-analysis plus one strategy and the explicit V2 dependency graph with five research tasks; never infer jobs from name suffixes. Verify get_analysis_context, prepare_strategy_context and publish_analysis_run are available on the connected server. Require analysis context contract_version 2 and app migration 0008_users_and_portfolios before scheduling.

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
