# Project instructions

Maintain each user-facing skill once under `plugins/portfolio-analyser/skills`. The advisory MCP catalog reads its name, description, instructions and references there. Keep agent runtime adapters in the host repository.

Every push, including documentation changes, must include a version higher than the remote target branch. Use a patch bump by default. Keep both plugin manifests and the Claude marketplace entry in sync, derive the wheel version from the same release, and validate before pushing.
