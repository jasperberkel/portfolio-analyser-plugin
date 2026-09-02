---
name: portfolio-analyser-setup
description: Prepare the installed Portfolio Analyser plugin and configure recurring jobs for all of its research and briefing skills. Use when the user asks to set up, prepare, schedule, or automate the plugin in Codex or Claude Code; do not use to run reports immediately or install the app itself.
---

# Portfolio Analyser Setup

Prepare the installed plugin and configure recurring jobs without creating duplicates.

## Detect the host

Determine the current host from the product context and available scheduling tools. Do not ask when it is unambiguous.

- For Codex or ChatGPT desktop scheduling, read [references/codex.md](references/codex.md).
- For Claude Code, read [references/claude-code.md](references/claude-code.md).
- If neither environment can be identified, explain that the supported targets are Codex and Claude Code and ask which one the user is using.

Verify that the `portfolio_analyser` MCP tools are configured. If they are not, warn that scheduled runs require the local Portfolio Analyser app and MCP server to be available, but continue the schedule setup when the user wants to proceed.

## Discover schedulable skills

Inspect the skills bundled in the installed `portfolio-analyser` plugin. Prefer the host's installed-plugin inventory; otherwise inspect the plugin's `skills/` directory and read each skill's frontmatter `name`.

Build the target set dynamically:

- Every skill name ending exactly in `-research` is a research job. Propose daily at 10:00.
- Every skill name ending exactly in `-briefing` is a briefing job. Propose daily at 11:00.

Do not hard-code the current skill names. Sort each group lexicographically so the proposal and result are deterministic. If no matching skills are installed, report that and create nothing.

For every target skill named `<skill-name>`, use these stable identifiers:

- Canonical prompt marker: `[portfolio-analyser:<skill-name>]`
- Display name: `Portfolio Analyser - <skill-name>`

Always include the canonical marker in the saved prompt, even when the scheduler has a separate name field.

## Inspect existing jobs

List existing scheduled jobs before asking for confirmation or writing changes. Match a job to a target skill in this order:

1. Its prompt contains the exact canonical marker.
2. Its prompt explicitly invokes the exact target skill.
3. Its name exactly equals the stable display name.
4. For migration only, recognize these legacy names:
   - `Portfolio Analyser - Position Research` → `portfolio-position-research`
   - `Portfolio Analyser - Market Opportunities` → `market-opportunity-research`
   - `Portfolio Analyser - Briefing` → `portfolio-briefing`

Never match on a vague phrase such as `research` or `briefing`. Preserve unrelated jobs.

- No match: mark the target as new.
- One match: reuse and update that job after confirmation.
- More than one match: do not create another job. Report the duplicates and ask which one to keep before deleting or consolidating anything. Never delete a job without explicit confirmation.

## Confirm the schedule

Present every discovered skill with its proposed cadence, local wall-clock time, detected timezone, and whether its job is new or existing. Ask once whether the user accepts the proposal or wants different frequencies, times, or timezone.

Default proposal:

- All `*-research` skills: daily at 10:00
- All `*-briefing` skills: daily at 11:00
- Timezone: the user's detected local timezone

The later briefing time intentionally gives research jobs time to finish. Wait for the answer. Plugin installation alone is not authorization to create scheduled jobs. If the user already supplied all schedule values, summarize them and continue without asking the same question again.

## Create or update jobs

After confirmation, update the single matching job for each target skill and create only missing jobs. Use the platform-specific explicit invocation described in the relevant reference file.

Derive each prompt from this template:

```text
[portfolio-analyser:<skill-name>]
Run the installed <skill-name> skill exactly as defined and complete its full workflow. If a required dependency, the Portfolio Analyser app, or its MCP server is unavailable, report the failure and do not fabricate results or publication.
```

Use the confirmed recurrence and timezone. Do not modify jobs unrelated to this plugin. Afterward, report every effective schedule, its timezone, whether it was created or updated, the scheduler type, and any host-specific limitation.
