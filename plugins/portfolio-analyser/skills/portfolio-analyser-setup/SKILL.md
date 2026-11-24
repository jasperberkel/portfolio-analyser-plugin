---
name: portfolio-analyser-setup
description: Connect the Trading-Paket and manage requested recurring instrument checks or full portfolio analyses. Use for personal setup and for requests such as “Prüfe Siemens täglich”.
---

# Portfolio Analyser Setup

Connect the installed plugin through native authenticated HTTP MCP, verify MCP, and configure recurring jobs without creating duplicates. Plugin installation alone is never authorization to connect or create schedules.

## Personal connection

“Richte das Trading-Paket ein” requests a personal connection now. The user approves the scopes in their own browser. Normal setup includes automatic earnings monitoring of held individual stocks, with notifications after publication by default. Explain this in the personal connection notice. On Thomas first call `bind_personal_wake({"package":"portfolio-analyser"})` from the requester’s authenticated personal conversation. An explicitly linked surface reuses the same agent, personal grant and job. A new binding selects the private destination for later results. A shared dashboard session can open the profile’s personal inbox. In a group, direct the requester to their private conversation before starting OAuth. The host completes enrollment on its first authorized wake, even for an empty portfolio. On an existing working connection also call `sync_earnings_tracking`. For other hosts report whether a personal wake is available. Full portfolio-analysis jobs and research profiles require their own request.

1. Use the current host's native tool discovery. The personal server is `portfolio_analyser`; the separate `portfolio` tools calculate locally. If the personal read tool is available, call `get_current_positions(check_setup_access=true)` once when the advertised schema supports it, otherwise call it without arguments. Reuse the working connection, including an empty portfolio, when its granted scopes include read, import and analyse. If any of these scopes are missing, initiate the host's permission upgrade instead of claiming full setup. Avoid displaying positions during setup.
2. On a fresh connection or an insufficient-scope response, immediately invoke the host-provided account **connect** action for that server (one call, no arguments). For hosts offering namespaced tools this can be `portfolio_analyser__connect`. Do not ask the user to start it or run a command. Deliver the resulting private, clickable browser sign-in URL only to the requesting user in a direct chat. Never paste callback URLs, tokens or credentials. Describe the requested permissions: read portfolio holdings/history, save uploaded statements with their import report, and publish analysis reports and investment plans. The browser callback finishes setup and displays the result. Tell the user they can close that page after success. Never ask them to send “Fertig”, retry a command, or reply to complete setup. Tool availability on the next normal request suffices. Do not claim success before the callback.
3. For standalone Codex or Claude Code without a connect action, use the installed connection settings and the host's native OAuth login flow. Prefer the active client's browser sign-in API. The bundled `scripts/configure_mcp.py --host codex|claude` supports CLI hosts. Run it on the user's behalf only when needed, accepting consent exclusively in the user's browser. An existing working connection is reused. Never remove a connection, copy a token, or invoke an operator login/delegated system setup for a personal connector. A scope challenge on a live connection uses the same personal connect action in this turn.
4. Full setup requests `portfolio:read`, `portfolio:import`, and `portfolio:analyse` together in one explicit browser consent. This covers the stock earnings monitor. The separate full daily portfolio analysis remains opt-in. A narrower existing grant stays narrow until the user approves the missing permissions. On denial or unavailable connectivity, report the specific state without retrying or publishing anything.

## Recurring instrument checks

When the user requests repeated instrument checks, use [instrument-monitor](../instrument-monitor/SKILL.md) for any requested watchlist changes. Use the user's private Trading connection. An instrument check can use explicit watches with an empty portfolio. A request to add a watch alone only updates the list.

Read `get_investment_monitoring` and inspect the host's existing personal jobs. Use one instrument-monitor job per account for its holdings and watchlist. Reuse it when the user adds another instrument. If the requested scope or timing is narrower than this shared job permits, resolve that difference with the user before changing it. Keep an existing timetable unless the request changes it. For a new recurring monitor, default to daily in the user's time zone.

Use the host's personal scheduler. On Emily, follow the native `schedules-and-watches` guide and use `manage_personal_context` with `schedule_list`, then `schedule_create` or `schedule_update` as needed. Use the title `Trading - instrument-monitor` and the owner's private chat. An existing job that explicitly invokes the former `investment-monitor` skill can be updated in place. Public issuer news can change independently of the connected account, so omit a connection-change trigger. Give the job this instruction:

> Run the installed instrument-monitor skill for my Trading holdings and watchlist. Process due checks and deliver new material events in this private chat. Stay quiet when there is no new event.

After saving or reusing a dedicated job, use `set_investment_monitoring` for any needed enrollment or interval change. The service accepts 6–168 hours and measures eligibility from completion. Keep a service interval shorter than the gap between host runs (for example 6 hours for a daily timetable) so a check finishing late does not skip the next day's run. At gaps of 6 hours or less, explain that an invocation can find research still ineligible. On hosts with a shared package wake, reuse that wake and set the requested interval on the service instead. For legacy Thomas use its existing `bind_personal_wake({"package":"portfolio-analyser"})` binding.

Verify service enrollment and the enabled host job with its next run before confirming. If setup is incomplete, identify which part was saved. When stopping recurring checks, disable instrument monitoring (this cancels its pending alerts) and pause its dedicated job, preserving the watchlist and any shared earnings wake. These operations require neither a full portfolio analysis nor research profile installation.

## Full portfolio analysis only

Apply the following workflow verification, job matching and migration only to an explicitly requested full portfolio analysis.

### Verify workflow and install profiles

Resolve `<plugin-root>/scripts/workflow.py` and run its discover command. Require run-analysis plus one strategy and the explicit V2 dependency graph with six research tasks; never infer jobs from name suffixes. Verify get_analysis_context, prepare_strategy_context and publish_analysis_run are available on the connected server. Verify all six Run Analysis tools, the import tools when needed, and context contract_version 2 before scheduling.

For Codex, run `python3 <plugin-root>/scripts/install_agent_profiles.py <project-root>` to install/update only the two managed project profiles. Do not overwrite an unmanaged collision. Claude Code uses the plugin's bundled agents. Read [host adapters](../../references/agent-adapters.md) and disclose the instruction-based fallback when native profile selection is unavailable. Agent setup is part of an explicitly requested workflow setup, not a side effect of plugin installation.

### Inspect existing jobs

Use the host scheduling tool and inspect saved jobs first. The single target is:

- Skill: run-analysis
- Canonical prompt marker: `[portfolio-analyser:run-analysis]`
- Display name: `Portfolio Analyser - run-analysis`

Match an existing target by exact canonical marker, exact skill invocation or exact display name. Reuse one unambiguous match; do not create a duplicate. Ask which to keep if multiple target jobs match.

For migration, identify only exact legacy markers or skill invocations for finanzen-news-research, market-opportunity-research, portfolio-position-research, portfolio-briefing and portfolio-strategy, or their exact `Portfolio Analyser - <skill>` names. Also recognize the legacy display names `Portfolio Analyser - Position Research`, `Portfolio Analyser - Market Opportunities`, and `Portfolio Analyser - Briefing`. Preserve unrelated jobs and notification preferences. Do not match vague research/briefing text.

### Verify and migrate the schedule

Default proposal: one complete daily run at 10:00 in the user's detected timezone. Show cadence, timezone, new/existing target and exact legacy jobs to pause. Obtain the user's schedule preference only when it has not already been provided. Plugin installation alone does not authorize schedule creation or changes.

Before switching existing jobs, require a successful complete manual run using the updated app/plugin, confirmed through stored strategy, research and exact plan associations. Fixture tests do not count as a live acceptance run. If it fails, report the stage and preserve the existing automation configuration.

After successful acceptance, create/update the target, preserving applicable notification choices, and pause the identified legacy jobs without deleting them. Avoid an active overlap during the switch: prepare the new target paused, pause legacy jobs, then activate the target. If a scheduler mutation fails, read back actual states and restore the pre-switch configuration where possible; never report a completed migration without verifying it. Do not modify unrelated jobs.

Use the host-specific explicit invocation with this prompt:

```text
[portfolio-analyser:run-analysis]
Run the installed run-analysis skill and publish the complete package atomically. Use its recommendation format for the private chat after verified publication. If a required stage fails, preserve drafts and report that stage. If the identical daily context already has a successful run, stay quiet.
```

Save the confirmed recurrence and timezone. Report the effective single schedule, paused legacy jobs, scheduler type and any host limitation. Do not claim profile isolation on a host that only uses role instructions.
