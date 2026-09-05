#!/usr/bin/env python3
"""Install managed Codex project role profiles without overwriting unrelated profiles."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "# Managed by portfolio-analyser: agent-profile-v1\n"


def install(project):
    directory = Path(project).resolve() / ".codex" / "agents"
    profiles = {}
    for role in ("research-agent", "strategy-agent"):
        instructions = (ROOT / "roles" / f"{role}.md").read_text(encoding="utf-8")
        instructions += (
            "\nRead the exact skill and task paths supplied in your delegated prompt.\n"
        )
        # JSON strings are valid TOML basic strings; no install-cache paths survive upgrades.
        profiles[directory / f"portfolio-{role}.toml"] = (
            MARKER
            + f'name = "portfolio-{role}"\n'
            + f'description = "Portfolio Analyser {role}; use supplied skill and input."\n'
            + "developer_instructions = "
            + json.dumps(instructions, ensure_ascii=False)
            + "\n"
        )
    for path in profiles:
        if path.exists() and not path.read_text(encoding="utf-8").startswith(MARKER):
            raise ValueError(f"Unmanaged profile exists: {path}; no files changed")
    directory.mkdir(parents=True, exist_ok=True)
    for path, text in profiles.items():
        path.write_text(text, encoding="utf-8")
    return [str(path) for path in profiles]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    print("\n".join(install(parser.parse_args().project)))
