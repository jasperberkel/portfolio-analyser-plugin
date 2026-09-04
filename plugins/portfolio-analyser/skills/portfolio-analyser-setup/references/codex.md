# Codex scheduling

Use Codex scheduled-task or automation tools when they are available.

1. Prefer standalone scheduled tasks rather than chat heartbeats because every skill run should be independent.
2. Resolve the saved Portfolio Analyser project that corresponds to the current checkout. Run each task locally in that project so it can reach the loopback app and the plugin-provided MCP bridge. Do not choose an unrelated project or invent a project identifier.
3. List existing scheduled tasks and apply the matching and duplicate rules from `SKILL.md` before making changes.
4. Put the canonical marker in every prompt and explicitly invoke the skill as `$<skill-name>` so a scheduled run uses the installed skill.
5. Translate the confirmed cadence, time, and timezone into the scheduler's supported recurrence format. Keep tasks active and use the current/default model settings unless the user requested overrides.
6. Do not display raw recurrence syntax unless the user asks for it.

Codex CLI and the IDE extension do not provide the Scheduled management interface. If the current Codex surface has no scheduled-task creation tool, explain that the user must run this setup from ChatGPT/Codex desktop or web rather than silently substituting operating-system cron.
