# Project instructions

Maintain each user-facing skill once under `plugins/portfolio-analyser/skills`. Hosts discover the native SKILL.md files. MCP exposes executable domain tools only. Keep agent runtime adapters in the host repository.

Every push, including documentation changes, must include a version higher than the remote target branch. Use a patch bump by default. Keep both plugin manifests and the Claude marketplace entry in sync, derive the wheel version from the same release, and validate before pushing.

Once per clone run `python3 scripts/publish.py setup` from the root. Use `git publish` (or `git publish origin main`) to perform the version check, automatic bump commit when needed, and fast-forward push.
