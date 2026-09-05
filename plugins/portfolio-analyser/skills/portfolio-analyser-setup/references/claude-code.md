# Claude Code scheduling

Prefer scheduling that can access the local Portfolio Analyser MCP server.

1. If Claude Code Desktop exposes local scheduled-task creation, create or update one durable local task for run-analysis for the current Portfolio Analyser checkout.
2. List existing tasks and apply the matching and duplicate rules from `SKILL.md` before making changes.
3. Put the canonical marker in every prompt and explicitly invoke the skill as `/portfolio-analyser:run-analysis`.
4. If only `CronList`, `CronCreate`, and `CronDelete` are available, explain before writing that these jobs are session-scoped, require Claude Code to remain running, and recurring jobs expire after seven days. Ask whether the user accepts that fallback.
5. For the session-scoped fallback, list jobs first, reuse or replace only unambiguous matches, and create only missing jobs with standard five-field cron expressions in the user's local timezone.
6. Do not use a cloud `/schedule` routine by default: a cloud routine cannot reach a Portfolio Analyser MCP server bound to `127.0.0.1`. Offer cloud routines only when the user confirms that a remotely reachable MCP server or connector is configured.
7. If durable local task creation is unavailable and the user declines session-scoped jobs, give the shortest exact handoff for creating Local routines in Claude Code Desktop. Do not claim they were created.

Claude Code may apply scheduler jitter, so describe the confirmed times as requested start times rather than guaranteed exact execution times.

Pause exact legacy jobs only after a successful complete acceptance run. A scheduler that cannot pause or safely restore the existing jobs needs a user-visible migration decision; do not delete them as an implicit substitute.
