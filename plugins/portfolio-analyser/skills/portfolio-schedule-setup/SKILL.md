---
name: portfolio-schedule-setup
description: Configure recurring Portfolio Analyser research and briefing jobs after plugin installation. Use when the user asks to prepare, set up, schedule, or automate the plugin in Codex or Claude Code; do not use to run reports immediately or install the app itself.
---

# Portfolio Schedule Setup

Configure recurring jobs for the installed Portfolio Analyser research and briefing skills.

## Detect the host

Determine the current host from the product context and available scheduling tools. Do not ask when it is unambiguous.

- For Codex or ChatGPT desktop scheduling, read [references/codex.md](references/codex.md).
- For Claude Code, read [references/claude-code.md](references/claude-code.md).
- If neither environment can be identified, explain that the supported targets are Codex and Claude Code and ask which one the user is using.

Verify that the three target skills are installed. Also verify that the `portfolio_analyser` MCP tools are configured or clearly warn that scheduled runs require the local Portfolio Analyser app and MCP server to be available.

## Confirm the schedule

Before creating or changing jobs, inspect existing schedules and ask the user to confirm cadence, times, and timezone. Offer this default:

- Portfolio position research: daily at 10:00
- Market opportunity research: daily at 10:00
- Portfolio briefing: daily at 11:00
- Timezone: the user's detected local timezone

Use a concise question such as:

> Vorschlag: Positions- und Marktresearch täglich um 10:00 Uhr, danach das Briefing täglich um 11:00 Uhr, Zeitzone Europe/Berlin. Soll ich das so einrichten oder möchtest du Rhythmus, Uhrzeiten oder Zeitzone ändern?

Wait for the answer. Do not treat installation of the plugin as authorization to create scheduled jobs. If the user already supplied every schedule value, summarize those values and continue without asking the same question again.

## Create or update the jobs

Create three independent recurring jobs with these stable names and prompts:

1. **Portfolio Analyser - Position Research**
   - Run the installed `portfolio-position-research` skill for the five largest current portfolio positions.
   - Research current health, outlook, risks, catalysts, and news, then publish a sourced German report to Portfolio Analyser.
   - If the portfolio or MCP service is unavailable, report the failure and never fabricate results.
2. **Portfolio Analyser - Market Opportunities**
   - Run the installed `market-opportunity-research` skill across its supported asset classes.
   - Publish a sourced German watchlist report to Portfolio Analyser without tailoring it to the user's portfolio.
   - If the MCP service is unavailable, report the failure and never fabricate publication.
3. **Portfolio Analyser - Briefing**
   - Run the installed `portfolio-briefing` skill using the current portfolio and latest completed enabled reports.
   - Publish the resulting German portfolio briefing.
   - If the day's research reports are not yet complete, use the latest completed reports and state their dates rather than inventing fresh research.

Use the confirmed cadence and local wall-clock times. The later briefing time is intentional so the research jobs can finish first.

List existing jobs before writing. Match by the stable names above and update matching jobs instead of creating duplicates. Preserve unrelated jobs. Afterward, report the three effective schedules, timezone, scheduler type, and any host-specific limitation.

If a scheduler has no separate name field, start each saved prompt with its stable name in square brackets and use that marker for matching, for example `[Portfolio Analyser - Briefing]`.
