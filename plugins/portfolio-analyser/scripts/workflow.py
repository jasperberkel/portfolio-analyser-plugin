#!/usr/bin/env python3
"""Local orchestration state/validation. Never starts models or connects to the app."""

import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "current_portfolio",
    "previous_report",
    "plan",
    "previous_strategy",
    "strategy_context",
}
MAX_BYTES = 15 * 1024 * 1024


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pending.replace(path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def packet(value):
    require(
        len(json.dumps(value, ensure_ascii=True).encode()) < MAX_BYTES,
        "Packet exceeds the MCP transport limit; not truncated",
    )
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def discover(root=ROOT):
    steps = []
    for file in sorted((Path(root) / "skills").glob("*/workflow.json")):
        require(
            file.resolve().is_relative_to(Path(root).resolve()),
            "Workflow escapes plugin",
        )
        step = read(file)
        require(
            set(step) == {"contract_version", "skill", "stage", "requires", "produces"},
            f"Unknown or missing workflow fields: {file}",
        )
        require(step["contract_version"] == 1, "Unsupported contract version")
        require(
            step["skill"] == file.parent.name
            and len(step["skill"]) <= 64
            and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", step["skill"]),
            "Invalid skill identity",
        )
        require(step["stage"] in ("research", "strategy"), "Invalid workflow stage")
        require(
            isinstance(step["requires"], list)
            and all(isinstance(x, str) for x in step["requires"]),
            "Invalid requires",
        )
        require(set(step["requires"]) <= INPUTS, "Unknown context input")
        require(len(set(step["requires"])) == len(step["requires"]), "Duplicate inputs")
        require(
            isinstance(step["produces"], str)
            and len(step["produces"]) <= 160
            and re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", step["produces"]),
            "Invalid report type",
        )
        if step["stage"] == "research":
            require(
                "strategy_context" not in step["requires"],
                "Research/strategy dependency cycle",
            )
        else:
            require(
                step["requires"] == ["strategy_context"],
                "Strategy needs prepared context",
            )
        require((file.parent / "SKILL.md").is_file(), "Missing SKILL.md")
        steps.append(step)
    require(2 <= len(steps) <= 100, "Expected research and strategy steps")
    require(
        sum(s["stage"] == "strategy" for s in steps) == 1,
        "Expected exactly one strategy",
    )
    for key in ("skill", "produces"):
        require(len({s[key] for s in steps}) == len(steps), f"Duplicate {key}")
    return {"contract_version": 1, "steps": steps}


def position_key(p):
    return (
        p.get("isin")
        or f"{p['asset_type']}:{p['currency']}:{p.get('symbol') or p['name']}"
    )


def make_input(step, context, run_id):
    dashboard = context["dashboard"]
    data = {
        "contract_version": 1,
        "run_id": run_id,
        "report_id": str(uuid.uuid4()),
        "skill": step["skill"],
        "analysis_type": step["produces"],
        "research_cutoff": context["research_cutoff"],
        "followup_round": 0,
    }
    for key in step["requires"]:
        if key == "current_portfolio":
            data[key] = {k: dashboard[k] for k in ("snapshot", "positions")}
        elif key == "previous_report":
            data[key] = context["previous_reports"].get(step["produces"])
        elif key == "plan":
            data[key] = dashboard["plan"]
        elif key == "previous_strategy":
            data[key] = {
                k: dashboard[k] for k in ("previous_briefing", "previous_portfolio")
            }
    return data


def initialize(folder, context, workflow):
    folder = Path(folder)
    require(
        not (folder / "state.json").exists(),
        "Run already initialized; resume explicitly",
    )
    require(context.get("contract_version") == 1, "Unsupported server context")
    require(
        context.get("existing_run") is None,
        "This daily context already has a successful run",
    )
    require(
        context["dashboard"].get("snapshot"),
        "A complete run requires a portfolio snapshot",
    )
    run_id = str(uuid.uuid4())
    tasks = {}
    for step in workflow["steps"]:
        if step["stage"] == "research":
            tasks[step["skill"]] = {"status": "pending", "attempts": 0}
            write(
                folder / step["skill"] / "input.json", make_input(step, context, run_id)
            )
    state = {
        "run_id": run_id,
        "workflow": workflow,
        "source_fingerprint": context["source_fingerprint"],
        "followup_round": 0,
        "tasks": tasks,
        "strategy_status": "pending",
        "stopped": False,
    }
    write(folder / "context.json", context)
    write(folder / "state.json", state)
    return state


def validate_result(result, task):
    expected = {
        "contract_version",
        "id",
        "run_id",
        "skill",
        "analysis_type",
        "content_markdown",
        "researched_at",
        "snapshot_id",
        "status",
        "coverage",
        "gaps",
    }
    require(set(result) == expected, "Missing or unknown research result fields")
    require(result["contract_version"] == 1, "Unsupported result version")
    for field in ("run_id", "skill", "analysis_type"):
        require(result[field] == task[field], f"Result {field} mismatch")
    require(result["id"] == task["report_id"], "Result report ID mismatch")
    require(
        isinstance(result["content_markdown"], str)
        and result["content_markdown"].strip(),
        "Empty report",
    )
    require(
        len(result["content_markdown"]) <= 2_000_000, "Report exceeds document limit"
    )
    require(
        isinstance(result["researched_at"], str),
        "Research time must be an ISO timestamp",
    )
    stamp = datetime.fromisoformat(result["researched_at"].replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "Research time requires a timezone")
    require(stamp <= datetime.now(timezone.utc), "Research timestamp is in the future")
    require(
        isinstance(result["gaps"], list)
        and all(isinstance(x, str) for x in result["gaps"]),
        "Invalid gaps",
    )
    coverage = result["coverage"]
    require(
        set(coverage) == {"selected", "researched", "uncovered"},
        "Invalid coverage fields",
    )
    for items in coverage.values():
        require(
            isinstance(items, list)
            and all(isinstance(x, str) and x.strip() for x in items),
            "Coverage must contain identifiers",
        )
        require(len(set(items)) == len(items), "Duplicate coverage identifiers")
    require(
        result["status"] == "complete" and not coverage["uncovered"],
        "Research incomplete",
    )
    require(
        set(coverage["selected"]) == set(coverage["researched"]),
        "Missing research coverage",
    )
    if "current_portfolio" in task:
        p = task["current_portfolio"]
        require(result["snapshot_id"] == p["snapshot"]["id"], "Snapshot mismatch")
        require(
            set(coverage["selected"]) == {position_key(x) for x in p["positions"]},
            "Must research every supplied position",
        )
    else:
        require(result["snapshot_id"] is None, "Independent research has no snapshot")
    packet(result)


def read_state(folder):
    return read(Path(folder) / "state.json")


def ready(state):
    require(not state["stopped"], "Run stopped after two failed attempts")
    require(
        all(t["status"] == "complete" for t in state["tasks"].values()),
        "All research must complete before strategy",
    )


def start(folder, skill):
    state = read_state(folder)
    require(not state["stopped"], "Run stopped")
    task = state["tasks"][skill]
    require(task["status"] in ("pending", "failed"), "Task already running or complete")
    require(task["attempts"] < 2, "Retry limit reached")
    task.update(status="running", attempts=task["attempts"] + 1)
    write(Path(folder) / "state.json", state)
    return read(Path(folder) / skill / "input.json")


def collect(folder, skill, failed=False):
    folder = Path(folder)
    state = read_state(folder)
    require(state["tasks"][skill]["status"] == "running", "Task not running")
    error = None
    try:
        require(not failed, "Agent failed or was interrupted")
        result = read(folder / skill / "result.json")
        validate_result(result, read(folder / skill / "input.json"))
        write(folder / skill / "accepted.json", result)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        error = str(exc)
    task = state["tasks"][skill]
    task["status"] = "failed" if error else "complete"
    task["error"] = error
    if error and task["attempts"] >= 2:
        state["stopped"] = True
    write(folder / "state.json", state)
    return state


def draft(folder):
    state = read_state(folder)
    ready(state)
    return packet(
        {
            "run_id": state["run_id"],
            "workflow": state["workflow"],
            "source_fingerprint": state["source_fingerprint"],
            "research": [
                read(Path(folder) / skill / "accepted.json")
                for skill in sorted(state["tasks"])
            ],
        }
    )


def prepared(folder, value):
    folder = Path(folder)
    state = read_state(folder)
    current = draft(folder)
    require(
        value["source_fingerprint"] == state["source_fingerprint"],
        "Prepared source mismatch",
    )
    require(
        re.fullmatch("[0-9a-f]{64}", value["evidence_fingerprint"]),
        "Invalid evidence token",
    )
    data = {
        "contract_version": 1,
        "run_id": state["run_id"],
        "followup_round": state["followup_round"],
        "research_steps": [
            s for s in state["workflow"]["steps"] if s["stage"] == "research"
        ],
        "strategy_context": value,
    }
    write(folder / "strategy" / "input.json", data)
    state["prepared_draft_hash"] = fingerprint(current)
    state["strategy_status"] = "ready"
    write(folder / "state.json", state)
    return data


def accept_strategy(folder, value):
    folder = Path(folder)
    state = read_state(folder)
    ready(state)
    require(state["strategy_status"] == "ready", "Strategy context is not ready")
    require(
        state["prepared_draft_hash"] == fingerprint(draft(folder)),
        "Draft changed after prepare",
    )
    task = read(folder / "strategy" / "input.json")
    require(
        value["contract_version"] == 1 and value["run_id"] == state["run_id"],
        "Strategy run mismatch",
    )
    require(
        value["evidence_fingerprint"]
        == task["strategy_context"]["evidence_fingerprint"],
        "Strategy evidence mismatch",
    )
    if value["status"] == "needs_research":
        require(
            set(value)
            == {
                "contract_version",
                "run_id",
                "evidence_fingerprint",
                "status",
                "requests",
            },
            "Invalid research request fields",
        )
        require(state["followup_round"] == 0, "Only one follow-up round is permitted")
        requests = value["requests"]
        require(isinstance(requests, list) and requests, "Empty follow-up round")
        require(
            len({r["skill"] for r in requests}) == len(requests),
            "Group questions by skill",
        )
        for request in requests:
            require(set(request) == {"skill", "questions"}, "Invalid follow-up request")
            require(request["skill"] in state["tasks"], "Unknown researcher")
            step = next(
                s for s in state["workflow"]["steps"] if s["skill"] == request["skill"]
            )
            included = {
                r["analysis_type"]
                for r in task["strategy_context"]["dashboard"]["reports"]
            }
            require(
                step["produces"] in included,
                "Excluded research cannot receive strategy followups",
            )
            require(
                isinstance(request["questions"], list)
                and request["questions"]
                and all(isinstance(q, str) and q.strip() for q in request["questions"]),
                "Empty questions",
            )
        # Validate the whole batch before changing any task.
        for request in requests:
            skill = request["skill"]
            inputs = read(folder / skill / "input.json")
            inputs.update(
                followup_round=1,
                questions=request["questions"],
                current_draft=read(folder / skill / "accepted.json"),
            )
            write(folder / skill / "input.json", inputs)
            state["tasks"][skill] = {"status": "pending", "attempts": 0}
        state.update(followup_round=1, strategy_status="pending")
    else:
        require(value["status"] == "complete", "Strategy incomplete")
        require(
            set(value)
            <= {
                "contract_version",
                "run_id",
                "evidence_fingerprint",
                "status",
                "strategy",
                "expected_plan_version",
                "plan_update",
            },
            "Unknown fields",
        )
        document = value["strategy"]
        require(
            set(document) == {"title", "content_markdown"}, "Invalid strategy document"
        )
        require(
            isinstance(document["title"], str)
            and 0 < len(document["title"].strip()) <= 300
            and not any(c in document["title"] for c in "\r\n\0"),
            "Invalid title",
        )
        require(
            isinstance(document["content_markdown"], str)
            and 0 < len(document["content_markdown"].strip()) <= 2_000_000,
            "Invalid strategy text",
        )
        plan = task["strategy_context"]["dashboard"]["plan"]
        require(
            value["expected_plan_version"] == (plan["version"] if plan else 0),
            "Plan mismatch",
        )
        require(
            plan or value.get("plan_update"), "First strategy requires a complete plan"
        )
        if value.get("plan_update"):
            update = value["plan_update"]
            require(
                set(update) == {"content_markdown", "change_reason"},
                "Invalid plan update",
            )
            for key, limit in [
                ("content_markdown", 2_000_000),
                ("change_reason", 20_000),
            ]:
                require(
                    isinstance(update[key], str)
                    and 0 < len(update[key].strip()) <= limit,
                    f"Invalid plan {key}",
                )
        write(folder / "strategy" / "accepted.json", packet(value))
        state["strategy_status"] = "complete"
    write(folder / "state.json", state)
    return state


def publication(folder):
    state = read_state(folder)
    require(state["strategy_status"] == "complete", "Strategy not complete")
    result = draft(folder)
    require(
        state["prepared_draft_hash"] == fingerprint(result),
        "Research changed after strategy",
    )
    strategy = read(Path(folder) / "strategy" / "accepted.json")
    result.update(
        {
            k: strategy[k]
            for k in ("evidence_fingerprint", "strategy", "expected_plan_version")
        }
    )
    if strategy.get("plan_update"):
        result["plan_update"] = strategy["plan_update"]
    packet(result)
    path = Path(folder) / "publication.json"
    require(
        not path.exists() or read(path) == result, "Frozen publication cannot change"
    )
    write(path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "discover",
            "init",
            "status",
            "start",
            "collect",
            "fail",
            "draft",
            "prepared",
            "strategy",
            "publication",
        ],
    )
    parser.add_argument("run_dir", nargs="?")
    parser.add_argument("argument", nargs="?")
    args = parser.parse_args()
    cmd, folder, arg = args.command, args.run_dir, args.argument
    if cmd == "discover":
        result = discover()
    elif cmd == "init":
        result = initialize(folder, read(arg), discover())
    elif cmd == "status":
        result = read_state(folder)
    elif cmd == "start":
        result = start(folder, arg)
    elif cmd in ("collect", "fail"):
        result = collect(folder, arg, failed=cmd == "fail")
    elif cmd == "draft":
        result = draft(folder)
    elif cmd == "prepared":
        result = prepared(folder, read(arg))
    elif cmd == "strategy":
        result = accept_strategy(folder, read(arg))
    else:
        result = publication(folder)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Workflow stopped: {exc}", file=sys.stderr)
        sys.exit(1)
