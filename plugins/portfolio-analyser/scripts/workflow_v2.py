"""Dependency-aware V2 scheduler. Agent execution belongs to the host orchestrator."""

import copy
import uuid
from pathlib import Path

import research_contract as c


def api():
    # Functions are supplied by workflow.py; avoid a second state implementation.
    return HOST


def accepted(folder, state):
    return {
        k: api().read(Path(folder) / k / "accepted.json")
        for k, v in state["tasks"].items()
        if v["status"] == "complete"
    }


def refresh(folder, state):
    for step in state["workflow"]["steps"]:
        task_id = step["task_id"]
        if task_id == "strategy":
            continue
        record = state["tasks"][task_id]
        if record["status"] != "blocked":
            continue
        parents = accepted(folder, state)
        if not all(d in parents for d in step["depends_on"]):
            continue
        context = api().read(Path(folder) / "context.json")
        task = c.build_input(
            context,
            state["workflow"],
            state["run_id"],
            task_id,
            parents,
            followup_round=0 if task_id == "market" else state["followup_round"],
            questions=record.get("questions", []),
        )
        api().write(Path(folder) / task_id / "input.json", task)
        record["status"] = "pending"
        if (
            task["payload_type"] in ("instruments", "valuation")
            and not task["selected"]
        ):
            result = c.empty_result(task)
            c.validate_result(result, task)
            api().write(Path(folder) / task_id / "accepted.json", result)
            record["status"] = "complete"
    state["ready_tasks"] = [
        k
        for k, v in state["tasks"].items()
        if v["status"] in ("pending", "failed")
        and v["attempts"] < 2
        and not state["stopped"]
    ]
    api().write(Path(folder) / "state.json", state)
    return state


def initialize(folder, context, workflow):
    c.validate_workflow(workflow)
    c.require(
        context.get("contract_version") == 2,
        "Upgrade the app: V2 required; no V1 downgrade",
    )
    c.require(not (Path(folder) / "state.json").exists(), "Run already initialized")
    c.require(
        not context.get("existing_run"), "This context already has a successful run"
    )
    c.require(context["dashboard"].get("snapshot"), "Portfolio snapshot required")
    state = {
        "run_id": str(uuid.uuid4()),
        "workflow": workflow,
        "source_fingerprint": context["source_fingerprint"],
        "followup_round": 0,
        "tasks": {
            k: {"status": "blocked", "attempts": 0} for k in c.TASKS if k != "strategy"
        },
        "strategy_status": "pending",
        "stopped": False,
    }
    api().write(Path(folder) / "context.json", context)
    return refresh(folder, state)


def start(folder, task_id):
    state = api().read_state(folder)
    c.require(not state["stopped"], "Run stopped")
    c.require(task_id in state["tasks"], "Unknown task")
    task = state["tasks"][task_id]
    c.require(
        task["status"] in ("pending", "failed") and task["attempts"] < 2,
        "Task not ready or retry limit reached",
    )
    task.update(status="running", attempts=task["attempts"] + 1)
    state["ready_tasks"] = [
        k
        for k, v in state["tasks"].items()
        if v["status"] in ("pending", "failed") and v["attempts"] < 2
    ]
    api().write(Path(folder) / "state.json", state)
    return api().read(Path(folder) / task_id / "input.json")


def collect(folder, task_id, failed=False):
    state = api().read_state(folder)
    task = state["tasks"][task_id]
    c.require(task["status"] == "running", "Task is not running")
    try:
        c.require(not failed, "Agent failed")
        result = api().read(Path(folder) / task_id / "result.json")
        c.validate_result(result, api().read(Path(folder) / task_id / "input.json"))
        api().packet(result)
        api().write(Path(folder) / task_id / "accepted.json", result)
        task.update(status="complete", error=None)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        task.update(status="failed", error=str(exc))
        if task["attempts"] >= 2:
            state["stopped"] = True
    return refresh(folder, state)


def draft(folder):
    state = api().read_state(folder)
    api().ready(state)
    context = api().read(Path(folder) / "context.json")
    rows = accepted(folder, state)
    # Rebuild every input, not only stored per-task files, to reject stale descendants.
    for task_id, row in rows.items():
        task = c.build_input(
            context,
            state["workflow"],
            state["run_id"],
            task_id,
            rows,
            followup_round=row["followup_round"],
            questions=row["questions"],
        )
        c.validate_result(row, task)
    return api().packet(
        {
            "run_id": state["run_id"],
            "workflow": state["workflow"],
            "research_cutoff": context["research_cutoff"],
            "source_fingerprint": state["source_fingerprint"],
            "research": [rows[k] for k in sorted(rows)],
        }
    )


def invalidate(folder, task_ids, questions=None):
    state = api().read_state(folder)
    invalid = set(task_ids)
    c.require(
        invalid <= state["tasks"].keys() and "market" not in invalid,
        "Invalid follow-up target",
    )
    while True:
        more = {
            s["task_id"]
            for s in state["workflow"]["steps"]
            if s["task_id"] != "strategy" and set(s["depends_on"]) & invalid
        }
        if more <= invalid:
            break
        invalid |= more
    for task_id in invalid:
        state["tasks"][task_id] = {
            "status": "blocked",
            "attempts": 0,
            "questions": (questions or {}).get(task_id, []),
        }
    state.update(strategy_status="pending", followup_round=1)
    state.pop("prepared_draft_hash", None)
    return refresh(folder, state)


def accept_strategy(folder, value, legacy_accept):
    state = api().read_state(folder)
    c.require(value["contract_version"] == 2, "V2 strategy required")
    c.require(state["strategy_status"] == "ready", "Strategy not ready")
    api().ready(state)
    c.require(
        state["prepared_draft_hash"] == api().fingerprint(draft(folder)),
        "Research changed after prepare",
    )
    task = api().read(Path(folder) / "strategy" / "input.json")
    c.require(
        value["run_id"] == state["run_id"]
        and value["evidence_fingerprint"]
        == task["strategy_context"]["evidence_fingerprint"],
        "Strategy provenance mismatch",
    )
    if value["status"] == "needs_research":
        c.fields(
            value,
            (
                "contract_version",
                "run_id",
                "evidence_fingerprint",
                "status",
                "requests",
            ),
        )
        c.require(state["followup_round"] == 0, "Only one follow-up round")
        requests = value["requests"]
        c.require(isinstance(requests, list) and requests, "Empty follow-up")
        questions = {}
        included = {
            r["analysis_type"] for r in task["strategy_context"]["dashboard"]["reports"]
        }
        for request in requests:
            c.fields(request, ("task_id", "questions"))
            target = request["task_id"]
            c.require(
                target in state["tasks"]
                and target != "market"
                and target not in questions,
                "Invalid or private follow-up target",
            )
            c.require(
                c.TASKS[target][2] in included,
                "Excluded research cannot receive follow-ups",
            )
            c.strings(request["questions"])
            c.require(request["questions"], "Empty follow-up questions")
            questions[target] = request["questions"]
        return invalidate(folder, questions, questions)
    # Reuse existing complete strategy/plan validation, preserving V4 behavior.
    legacy_value = copy.deepcopy(value)
    legacy_value["contract_version"] = 1
    result = legacy_accept(folder, legacy_value)
    saved = api().read(Path(folder) / "strategy" / "accepted.json")
    saved["contract_version"] = 2
    api().write(Path(folder) / "strategy" / "accepted.json", saved)
    return result
