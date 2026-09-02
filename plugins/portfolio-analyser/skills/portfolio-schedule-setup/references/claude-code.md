# Claude Code scheduling

Prefer scheduling that can access the local Portfolio Analyser MCP server.

1. If Claude Code Desktop exposes local scheduled-task creation, create or update three durable local tasks for the current Portfolio Analyser checkout.
2. If only `CronList`, `CronCreate`, and `CronDelete` are available, explain before writing that these tasks are session-scoped, require Claude Code to remain running, and recurring tasks expire after seven days. Ask whether the user accepts that fallback.
3. For the session-scoped fallback, list jobs first. Replace only jobs with the stable names from `SKILL.md`, then create the three recurring jobs with standard five-field cron expressions in the user's local timezone.
4. Do not use a cloud `/schedule` routine by default: a cloud routine cannot reach a Portfolio Analyser MCP server bound to `127.0.0.1`. Offer cloud routines only when the user confirms that a remotely reachable MCP server or connector is configured.
5. If durable local task creation is unavailable and the user declines session-scoped jobs, give the shortest exact handoff for creating the three Local routines in Claude Code Desktop. Do not claim they were created.

Claude Code may apply scheduler jitter, so describe the confirmed times as requested start times rather than guaranteed exact execution times.
