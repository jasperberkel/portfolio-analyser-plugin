# Codex scheduling

Use Codex scheduled-task or automation tools when they are available.

1. Prefer three standalone scheduled tasks rather than chat heartbeats, because each report run should be independent.
2. Resolve the saved Portfolio Analyser project that corresponds to the current checkout. Run each task locally in that project so it can use the local MCP configuration. Do not choose an unrelated project or invent a project identifier.
3. Inspect existing scheduled tasks first. Update tasks with the stable names from `SKILL.md`; create only missing tasks.
4. Translate the confirmed cadence, time, and timezone into the scheduler's supported recurrence format. Keep tasks active and use the current/default model settings unless the user requested overrides.
5. Do not display raw recurrence syntax unless the user asks for it.

Codex CLI and the IDE extension do not provide the Scheduled management interface. If the current Codex surface has no scheduled-task creation tool, explain that the user must run this setup from ChatGPT/Codex desktop or web rather than silently substituting operating-system cron.
