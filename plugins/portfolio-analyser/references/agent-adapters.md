# Host adapters

Use the same role playbooks and skills on both hosts. A role is an execution profile; a skill owns methodology. No per-research-skill agent definition is necessary.

- Claude Code: select plugin agents `portfolio-analyser:research-agent` and `portfolio-analyser:strategy-agent` through the available Agent tool. Supply the plugin root, exact role/skill/task paths and output location. The definitions inherit the model and expose role-appropriate tools. Shell access is not an enforced network firewall.
- Codex: setup can install managed project TOML profiles with `python3 <plugin-root>/scripts/install_agent_profiles.py <project-root>`. They register `portfolio-research-agent` and `portfolio-strategy-agent` on hosts supporting custom profiles. Re-run after plugin updates; unrelated files are never overwritten. The files intentionally omit model/reasoning overrides.
- If the host's spawn API cannot select a custom profile, spawn a general subagent with the corresponding role playbook and explicit skill path. Start with no parent conversation history (`fork_turns="none"` where available). This fallback is instruction-based, not technically enforced tool isolation. Never pretend that reading a role file changes runtime permissions.
- If a host has no subagent API, stop with a capability error. Do not launch paid external model APIs or pretend sequential main-context work was parallel.

Researchers get only the inputs declared in workflow.json. Market/news workers must never inherit portfolio data. Strategy gets the complete prepared context including all included reports. Both can write only their assigned artifacts by instruction; the orchestrator alone connects to the app and updates run state.
