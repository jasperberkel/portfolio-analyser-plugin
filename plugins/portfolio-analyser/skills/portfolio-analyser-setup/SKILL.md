---
name: portfolio-analyser-setup
description: Securely connect the installed Portfolio Analyser plugin to the local app and configure one recurring run-analysis job and shared agent profiles. Use when the user asks to set up, connect, prepare, schedule, or automate the plugin in Codex or Claude Code; do not use to run reports immediately or install the app itself.
---

# Portfolio Analyser Setup

Pair the installed plugin with the local app, verify MCP, and configure recurring jobs without creating duplicates. Plugin installation alone is never authorization to pair or create schedules.

## Detect the host

Determine the current host from the product context and available scheduling tools. Do not ask when it is unambiguous.

- For Codex or ChatGPT desktop scheduling, read [references/codex.md](references/codex.md).
- For Claude Code, read [references/claude-code.md](references/claude-code.md).
- If neither environment can be identified, explain that the supported targets are Codex and Claude Code and ask which one the user is using.

## Connect the local app

Locate the installed plugin root from this skill's path. The bridge executable is:

- macOS or Linux: `<plugin-root>/bin/portfolio-analyser-bridge`
- Windows: `<plugin-root>\bin\portfolio-analyser-bridge.exe`

Run the bridge's `status` command first. Never print, inspect, request, or persist the long-lived token yourself.

- If status succeeds, continue to schedule discovery without pairing again.
- If the app is unreachable, ask the user to start Portfolio Analyser and stop. Do not create schedules that cannot reach their dependency.
- If no credential exists or it was revoked, tell the user to open `http://localhost:3000/settings`, choose **Verbindungscode erzeugen**, and paste the short-lived code into the conversation.
- On Linux, if the bridge reports that no secure keyring is available, relay its Secret Service guidance and stop. Never fall back to a plaintext file.

After the user supplies a code, detect the current client name and operating system. Run `pair` with `--client` and `--platform`, passing the code only on the process's standard input. The bridge stores the returned token directly in the native credential store. Do not include the code in command-line arguments, logs, summaries, or saved jobs.

Run `status` again. Continue only when it confirms an authenticated MCP handshake. If the host has already started the plugin MCP process without a credential, explain at the end that a plugin reload or new session may be required before tools appear; this does not prevent schedule configuration after the direct status check succeeds.

## Verify workflow and install profiles

Resolve `<plugin-root>/scripts/workflow.py` and run its discover command. Require run-analysis plus one strategy and the registered research descriptors; never infer jobs from name suffixes. Verify get_analysis_context, prepare_strategy_context and publish_analysis_run are available on the connected server. Old app versions must be updated before scheduling.

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
Run the installed run-analysis skill exactly as defined: load app context, execute registered research in parallel subagents, create portfolio strategy, and publish the complete package atomically. If a required dependency, researcher or publication step fails, preserve drafts and report the failure without publishing a partial package. If the identical daily context already has a successful run, stay quiet. Notify only on a newly completed analysis, a failure, or required user action.
```

Save the confirmed recurrence and timezone. Report the effective single schedule, paused legacy jobs, scheduler type and any host limitation. Do not claim profile isolation on a host that only uses role instructions.
