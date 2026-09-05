# Codex scheduling

Use the available automation_update tool and its actual schema. Use standalone local cron only when the user explicitly requests one job per complete run; otherwise follow the host's heartbeat default. The requested migration from separate research jobs to a single independent daily analysis authorizes the standalone local job here.

Resolve the saved Portfolio Analyser project using list_projects. Existing automation files can be inspected read-only for IDs and full fields. Preserve the current model, reasoning and notification settings unless explicitly overridden. Migration target: one explicit `$run-analysis` invocation with its canonical marker. Never write automation TOML manually or use operating-system cron as a substitute.

Use the confirmed timezone and supported recurrence format; do not display raw recurrence syntax. Verify the installed plugin and a complete manual run before changing existing schedules. If scheduling tools are unavailable, give a short desktop handoff and do not claim the jobs changed.
