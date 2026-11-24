"""V2 research contracts and pure calculations. No model, network or app access.

Canonical copy lives in the plugin; API vendors this file. Parity is tested.
"""

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

PACKAGE = "research.core"
LEGACY_TYPES = ("news.finanzen-net", "market.opportunity-research", "portfolio.position-research")
TYPES = ("market.radar", "instrument.discovery", "instrument.research", "valuation.thesis", "portfolio.risk")
TASKS = {
    "market": ("market-radar", [], "market.radar", "radar"),
    "finder": ("instrument-finder", [], "instrument.discovery", "discovery"),
    "holdings": ("instrument-research", [], "instrument.research", "instruments"),
    "candidates": ("instrument-research", ["finder"], "instrument.research", "instruments"),
    "valuation": ("instrument-evaluation", ["holdings", "candidates"], "valuation.thesis", "valuation"),
    "risk": ("portfolio-risk-research", ["holdings"], "portfolio.risk", "risk"),
    "strategy": (
        "portfolio-strategy", ["market", "finder", "holdings", "candidates", "valuation", "risk"],
        "portfolio.strategy", "strategy",
    ),
}

# The service also validates submissions from installed revision-2 clients.
PREVIOUS_TASKS = {
    "market": ("market-discovery-research", [], "market.discovery", "market"),
    "holdings": TASKS["holdings"],
    "candidates": ("instrument-research", ["market"], "instrument.research", "instruments"),
    "valuation": ("valuation-thesis-research", ["holdings", "candidates"], "valuation.thesis", "valuation"),
    "risk": TASKS["risk"],
    "strategy": ("portfolio-strategy", ["market", "holdings", "candidates", "valuation", "risk"],
                 "portfolio.strategy", "strategy"),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(value, required, optional=()):
    require(
        isinstance(value, dict) and set(required) <= value.keys() <= set(required) | set(optional),
        "Missing or unknown fields: " + ", ".join(required),
    )


def string(value):
    require(isinstance(value, str) and bool(value.strip()), "Expected nonblank text")


def strings(value):
    require(isinstance(value, list), "Expected text list")
    for item in value:
        string(item)


def stamp(value):
    string(value)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None and result.utcoffset() is not None, "Timezone required")
    return result


def number(value):
    require(not isinstance(value, bool), "Boolean is not a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid decimal") from exc
    require(result.is_finite(), "Nonfinite number")
    return result


def default_workflow(*, previous=False):
    tasks = PREVIOUS_TASKS if previous else TASKS
    return {
        "contract_version": 2,
        "steps": [
            {
                "task_id": task,
                "skill": skill,
                "stage": "strategy" if task == "strategy" else "research",
                "depends_on": deps,
                "produces": output,
                "payload_type": kind,
                "methodology_revision": "2" if previous else "3",
            }
            for task, (skill, deps, output, kind) in tasks.items()
        ],
    }


def validate_workflow(flow):
    fields(flow, ("contract_version", "steps"))
    require(flow["contract_version"] == 2, "V2 server/plugin required")
    steps = flow["steps"]
    require(isinstance(steps, list) and all(isinstance(s, dict) for s in steps), "Expected task list")
    ids = {s.get("task_id") for s in steps}
    tasks = TASKS if "finder" in ids else PREVIOUS_TASKS
    require(len(steps) == len(tasks) and ids == set(tasks), "Unknown/duplicate task")
    for step in flow["steps"]:
        fields(
            step,
            (
                "task_id",
                "skill",
                "stage",
                "depends_on",
                "produces",
                "payload_type",
                "methodology_revision",
            ),
        )
        skill, deps, output, kind = tasks[step["task_id"]]
        require(
            step["skill"] == skill and step["produces"] == output and step["payload_type"] == kind,
            "Task role/output mismatch",
        )
        require(
            step["stage"] == ("strategy" if kind == "strategy" else "research"),
            "Task stage mismatch",
        )
        require(
            isinstance(step["depends_on"], list) and sorted(step["depends_on"]) == sorted(deps),
            "Unknown, cyclic or unsupported dependencies",
        )
        require(
            bool(re.fullmatch(r"[a-zA-Z0-9._-]{1,80}", step["methodology_revision"])),
            "Invalid method revision",
        )
    return flow


def position_key(p):
    return p.get("isin") or f"{p['asset_type']}:{p['currency']}:{p.get('symbol') or p['name']}"


def instrument(p):
    return {
        "instrument_id": position_key(p),
        **{k: p.get(k) for k in ("isin", "symbol", "name", "asset_type", "currency")},
    }


def validate_instrument(item):
    fields(item, ("instrument_id", "isin", "symbol", "name", "asset_type", "currency"))
    for key in ("instrument_id", "name", "asset_type", "currency"):
        string(item[key])
    require(item["instrument_id"] == position_key(item), "Instrument identity mismatch")
    require(
        bool(item["isin"] or item["symbol"]),
        "Unresolved instrument identity; put it in deferred instead",
    )


def previous_radar(context):
    reports = context.get("previous_reports", {})
    report = reports.get("market.radar") or reports.get("market.discovery")
    if not report:
        return None
    data = report["research_data"]
    return {
        "schema_version": 1, "kind": "radar",
        "context_markdown": data["context_markdown"], "sources": copy.deepcopy(data["sources"]),
    }


def scoped_history(context, report_type, selected=None):
    if report_type == "market.radar":
        return previous_radar(context)
    previous = context.get("previous_reports", {}).get(report_type)
    data = copy.deepcopy(previous.get("research_data")) if previous else None
    if selected is not None and report_type in ("instrument.research", "valuation.thesis"):
        try:
            from .candidate_memory import restore_dossiers
        except ImportError:
            from candidate_memory import restore_dossiers
        data = restore_dossiers(data, context.get("candidate_memory", []), report_type, selected)
    if not data:
        return None
    if selected is not None:
        data["items"] = [i for i in data["items"] if i["instrument_id"] in selected]
        # Sources are filtered as well; never forward a full merged report to an instrument task.
        used = set()
        for item in data["items"]:
            for key in ("facts", "events", "theses"):
                for record in item.get(key, []):
                    used.update(record.get("source_ids", []))
            used.update(item.get("source_ids", []))
            for exposure in item.get("exposures", []):
                used.update(exposure["source_ids"])
        data["sources"] = [s for s in data["sources"] if s["source_id"] in used]
        if "hypotheses" in data:
            data[
                "hypotheses"
            ] = []  # Current hypotheses arrive through the scoped task, not merged history.
    return data


def build_input(context, flow, run_id, task_id, accepted, *, followup_round=0, questions=None):
    validate_workflow(flow)
    step = next(s for s in flow["steps"] if s["task_id"] == task_id)
    require(task_id != "strategy", "Strategy needs server prepared context")
    require(all(d in accepted for d in step["depends_on"]), "Dependencies not complete")
    require(followup_round in (0, 1), "Only one follow-up round")
    questions = questions or []
    strings(questions)
    require(not questions or followup_round == 1, "Questions require follow-up")
    require(
        task_id not in ("market", "finder") or not questions and followup_round == 0,
        "No strategy feedback to market radar or discovery",
    )
    dashboard = context.get("dashboard", {})
    held_by_id = {}
    if task_id in ("holdings", "risk", "candidates"):
        for position in dashboard["positions"]:
            held_by_id.setdefault(position_key(position), instrument(position))
    if task_id in ("holdings", "risk"):
        selected = list(held_by_id.values())
    elif task_id == "candidates":
        discovery_id, = step["depends_on"]
        discovery = accepted[discovery_id]["research_data"]
        selected = [
            c["instrument"]
            for c in discovery["candidates"]
            if c["instrument"]["instrument_id"] not in held_by_id
        ]
    elif task_id == "valuation":
        selected = [
            i["instrument"]
            for d in ("holdings", "candidates")
            for i in accepted[d]["research_data"]["items"]
        ]
    else:
        selected = []
    ids = sorted(i["instrument_id"] for i in selected)
    require(len(ids) == len(set(ids)), "Duplicate instruments in scope")
    data = {
        "contract_version": 2,
        "run_id": str(run_id),
        "task_id": task_id,
        "report_id": str(uuid.uuid5(uuid.UUID(str(run_id)), task_id)),
        "skill": step["skill"],
        "analysis_type": step["produces"],
        "payload_type": step["payload_type"],
        "methodology_revision": step["methodology_revision"],
        "research_cutoff": stamp(context["research_cutoff"]).isoformat(),
        "snapshot_id": dashboard["snapshot"]["id"]
        if task_id in ("holdings", "risk", "valuation")
        else None,
        "selected": ids,
        "instruments": sorted(selected, key=lambda i: i["instrument_id"]),
        "dependency_hashes": {d: digest(accepted[d]) for d in step["depends_on"]},
        "dependencies": {d: accepted[d]["research_data"] for d in step["depends_on"]},
        "previous_state": scoped_history(
            context, step["produces"], None if task_id in ("market", "finder") else ids
        ),
        "followup_round": followup_round,
        "questions": questions,
    }
    if task_id == "finder":
        radar = previous_radar(context)
        if radar:
            data["market_context"] = radar
    if step["payload_type"] in ("discovery", "market") and context.get("candidate_memory"):
        try:
            from .candidate_memory import discovery_history
        except ImportError:
            from candidate_memory import discovery_history
        data["candidate_history"] = discovery_history(context["candidate_memory"])
    if task_id == "risk":
        data["current_portfolio"] = {k: dashboard[k] for k in ("snapshot", "positions")}
        data["plan"] = dashboard.get("plan")
        data["calculations"] = portfolio_risk(
            data["current_portfolio"], accepted["holdings"]["research_data"]
        )
    # Pass discovery evidence for the assigned candidates and keep portfolio details private.
    if task_id == "candidates":
        data["candidate_hypotheses"] = [
            c["hypothesis"] for c in discovery["candidates"]
        ]
        data["dependencies"][discovery_id] = {
            "candidates": [
                c
                for c in discovery["candidates"]
                if c["instrument"]["instrument_id"] in ids
            ]
        }
        used_sources = {
            source
            for candidate in data["dependencies"][discovery_id]["candidates"]
            for source in candidate["source_ids"]
        }
        data["dependencies"][discovery_id]["sources"] = [
            source
            for source in discovery["sources"]
            if source["source_id"] in used_sources
        ]
    if task_id == "valuation":
        data["hypotheses"] = accepted["candidates"]["research_data"].get("hypotheses", [])
    data["input_hash"] = digest(data)
    return data


def source_refs(ids, known):
    strings(ids)
    require(len(ids) == len(set(ids)) and set(ids) <= known, "Unknown/duplicate source reference")


def validate_payload(data, kind, selected, cutoff):
    common = ("schema_version", "kind", "sources")
    extras = {
        "market": ("context_markdown", "candidates", "deferred"),  # revision 2
        "radar": ("context_markdown",),
        "discovery": ("candidates", "deferred"),
        "instruments": ("items", "hypotheses"),
        "valuation": ("items",),
        "risk": ("items", "calculations", "findings"),
    }
    fields(data, common + extras[kind])
    require(data["schema_version"] == 1 and data["kind"] == kind, "Payload type/version mismatch")
    require(isinstance(data["sources"], list), "Sources must be a list")
    source_ids = set()
    for source in data["sources"]:
        fields(source, ("source_id", "url", "title", "published_at", "accessed_at", "locator"))
        for key in ("source_id", "url", "title", "locator"):
            string(source[key])
        require(source["url"].startswith(("https://", "http://")), "Source requires HTTP URL")
        require(source["source_id"] not in source_ids, "Duplicate source ID")
        source_ids.add(source["source_id"])
        stamp(source["accessed_at"])
        if source["published_at"] is not None:
            require(stamp(source["published_at"]) <= stamp(cutoff), "Source published after cutoff")
    if kind in ("radar", "market"):
        string(data["context_markdown"])
    if kind == "radar":
        return
    if kind in ("discovery", "market"):
        strings(data["deferred"])
        require(
            isinstance(data["candidates"], list) and len(data["candidates"]) <= 8,
            "At most eight candidates",
        )
        ids = []
        for candidate in data["candidates"]:
            fields(candidate, ("instrument", "hypothesis", "risks", "questions", "source_ids"), ("review_trigger", "review_after"))
            if "review_trigger" in candidate:
                string(candidate["review_trigger"])
            if candidate.get("review_after") is not None:
                require(stamp(candidate["review_after"]) >= stamp(cutoff), "Candidate review date precedes research cutoff")
            validate_instrument(candidate["instrument"])
            ids.append(candidate["instrument"]["instrument_id"])
            string(candidate["hypothesis"])
            strings(candidate["risks"])
            strings(candidate["questions"])
            source_refs(candidate["source_ids"], source_ids)
            require(candidate["source_ids"], "Candidate needs evidence")
        require(len(ids) == len(set(ids)), "Duplicate candidate")
        return
    require(isinstance(data["items"], list), "Items must be a list")
    ids = [i["instrument_id"] for i in data["items"]]
    require(
        len(ids) == len(set(ids)) and set(ids) == set(selected),
        "Payload must cover exact assigned scope",
    )
    for item in data["items"]:
        if kind == "instruments":
            fields(
                item,
                (
                    "instrument_id",
                    "instrument",
                    "content_markdown",
                    "facts",
                    "events",
                    "exposures",
                    "gaps",
                ),
            )
            # Holdings with no ticker remain researchable using their supplied identity.
            require(
                item["instrument_id"] == item["instrument"]["instrument_id"],
                "Dossier identity mismatch",
            )
            string(item["content_markdown"])
            strings(item["gaps"])
            facts = set()
            for fact in item["facts"]:
                fields(
                    fact,
                    (
                        "fact_id",
                        "metric",
                        "value",
                        "unit",
                        "currency",
                        "period",
                        "basis",
                        "value_kind",
                        "source_ids",
                        "gap",
                    ),
                )
                for key in ("fact_id", "metric", "unit", "period", "basis"):
                    string(fact[key])
                require(
                    fact["value_kind"] in ("actual", "guidance", "consensus", "assumption"),
                    "Invalid fact kind",
                )
                require(fact["fact_id"] not in facts, "Duplicate fact ID")
                facts.add(fact["fact_id"])
                source_refs(fact["source_ids"], source_ids)
                if fact["value"] is None:
                    string(fact["gap"])
                else:
                    require(
                        isinstance(fact["value"], (str, int, float))
                        and not isinstance(fact["value"], bool),
                        "Invalid fact value",
                    )
                    require(bool(fact["source_ids"]), "Fact needs source")
                if fact["currency"] is not None:
                    require(bool(re.fullmatch("[A-Z]{3}", fact["currency"])), "Invalid currency")
            event_ids = set()
            for event in item["events"]:
                fields(
                    event,
                    (
                        "event_id",
                        "title",
                        "scheduled_at",
                        "certainty",
                        "first_seen_at",
                        "changed_at",
                        "outcome",
                        "source_ids",
                    ),
                )
                require(event["event_id"] not in event_ids, "Duplicate event ID")
                event_ids.add(event["event_id"])
                require(
                    event["certainty"] in ("confirmed", "estimated", "unknown"),
                    "Invalid event certainty",
                )
                if event["scheduled_at"] is not None:
                    stamp(event["scheduled_at"])
                require(
                    stamp(event["first_seen_at"]) <= stamp(event["changed_at"]) <= stamp(cutoff),
                    "Invalid event timeline",
                )
                source_refs(event["source_ids"], source_ids)
            exposure_ids = set()
            for exposure in item["exposures"]:
                fields(exposure, ("instrument_id", "weight", "as_of", "source_ids"))
                string(exposure["instrument_id"])
                require(exposure["instrument_id"] not in exposure_ids, "Duplicate fund constituent")
                exposure_ids.add(exposure["instrument_id"])
                require(0 <= number(exposure["weight"]) <= 1, "Exposure weight outside 0..1")
                require(stamp(exposure["as_of"]) <= stamp(cutoff), "Future exposure")
                source_refs(exposure["source_ids"], source_ids)
                require(exposure["source_ids"], "Exposure needs evidence")
            require(
                sum((number(e["weight"]) for e in item["exposures"]), Decimal(0)) <= 1,
                "Exposures exceed 100%",
            )
        elif kind == "valuation":
            fields(
                item,
                (
                    "instrument_id",
                    "health",
                    "valuation",
                    "thesis_change",
                    "content_markdown",
                    "theses",
                    "source_ids",
                    "gaps",
                ),
            )
            for key in ("health", "valuation", "thesis_change", "content_markdown"):
                string(item[key])
            strings(item["gaps"])
            source_refs(item["source_ids"], source_ids)
            thesis_ids = set()
            for thesis in item["theses"]:
                fields(
                    thesis,
                    (
                        "thesis_id",
                        "claim",
                        "status",
                        "first_seen_at",
                        "changed_at",
                        "counterevidence",
                        "invalidation",
                        "source_ids",
                    ),
                )
                for key in ("thesis_id", "claim", "invalidation"):
                    string(thesis[key])
                require(thesis["thesis_id"] not in thesis_ids, "Duplicate thesis ID")
                thesis_ids.add(thesis["thesis_id"])
                require(
                    thesis["status"]
                    in ("new", "supported", "weakened", "invalidated", "uncertain"),
                    "Invalid thesis status",
                )
                strings(thesis["counterevidence"])
                require(
                    stamp(thesis["first_seen_at"]) <= stamp(thesis["changed_at"]) <= stamp(cutoff),
                    "Invalid thesis timeline",
                )
                source_refs(thesis["source_ids"], source_ids)
        else:
            fields(item, ("instrument_id", "content_markdown", "source_ids", "gaps"))
            string(item["content_markdown"])
            strings(item["gaps"])
            source_refs(item["source_ids"], source_ids)
    if kind == "instruments":
        strings(data["hypotheses"])
    if kind == "risk":
        strings(data["findings"])


def validate_continuity(data, previous):
    if not previous:
        return
    old_items = {i["instrument_id"]: i for i in previous.get("items", [])}
    for item in data.get("items", []):
        old = old_items.get(item["instrument_id"], {})
        for key, id_key in (("theses", "thesis_id"), ("events", "event_id")):
            old_records = {v[id_key]: v for v in old.get(key, [])}
            records = {v[id_key]: v for v in item.get(key, [])}
            require(set(old_records) <= records.keys(), "Do not discard tracked theses/events")
            for identifier in old_records.keys() & records.keys():
                before, after = old_records[identifier], records[identifier]
                require(after["first_seen_at"] == before["first_seen_at"], "Original date changed")

                def substantive(v):
                    return {k: x for k, x in v.items() if k not in ("changed_at", "source_ids")}

                if substantive(before) == substantive(after):
                    require(
                        after["changed_at"] == before["changed_at"], "Unchanged state was redated"
                    )
                else:
                    require(
                        stamp(after["changed_at"]) >= stamp(before["changed_at"]),
                        "State date moved backwards",
                    )


def validate_result(result, task):
    fields(
        result,
        (
            "contract_version",
            "id",
            "run_id",
            "task_id",
            "skill",
            "analysis_type",
            "methodology_revision",
            "input_hash",
            "dependency_hashes",
            "followup_round",
            "questions",
            "content_markdown",
            "researched_at",
            "snapshot_id",
            "status",
            "coverage",
            "gaps",
            "research_data",
        ),
    )
    for key in (
        "contract_version",
        "run_id",
        "task_id",
        "skill",
        "analysis_type",
        "methodology_revision",
        "input_hash",
        "dependency_hashes",
        "followup_round",
        "questions",
        "snapshot_id",
    ):
        require(result[key] == task[key], "Result input/provenance mismatch: " + key)
    require(result["id"] == task["report_id"], "Result ID mismatch")
    string(result["content_markdown"])
    require(result["status"] == "complete", "Incomplete research")
    require(
        stamp(result["researched_at"]) >= stamp(task["research_cutoff"]), "Research predates run"
    )
    fields(result["coverage"], ("selected", "researched", "uncovered"))
    for key in ("selected", "researched"):
        ids = result["coverage"][key]
        require(
            isinstance(ids, list)
            and len(ids) == len(set(ids))
            and set(ids) == set(task["selected"]),
            "Missing coverage",
        )
    require(result["coverage"]["uncovered"] == [], "Uncovered instruments")
    strings(result["gaps"])
    validate_payload(
        result["research_data"], task["payload_type"], task["selected"], task["research_cutoff"]
    )
    validate_continuity(result["research_data"], task["previous_state"])
    if task["payload_type"] == "instruments":
        expected = {i["instrument_id"]: i for i in task["instruments"]}
        require(
            all(
                i["instrument"] == expected[i["instrument_id"]]
                for i in result["research_data"]["items"]
            ),
            "Instrument changed",
        )
        require(
            result["research_data"]["hypotheses"] == task.get("candidate_hypotheses", []),
            "Candidate hypotheses changed",
        )
    if task["task_id"] == "risk":
        require(
            result["research_data"]["calculations"] == task["calculations"],
            "Risk calculations changed",
        )
    return result


def empty_result(task):
    require(
        task["payload_type"] in ("instruments", "valuation") and not task["selected"],
        "Only empty instrument/valuation work is automatic",
    )
    result = {
        k: copy.deepcopy(task[k])
        for k in (
            "contract_version",
            "run_id",
            "task_id",
            "skill",
            "analysis_type",
            "methodology_revision",
            "input_hash",
            "dependency_hashes",
            "followup_round",
            "questions",
            "snapshot_id",
        )
    }
    result.update(
        id=task["report_id"],
        content_markdown="Keine Instrumente in diesem Auftrag.",
        researched_at=task["research_cutoff"],
        status="complete",
        coverage={"selected": [], "researched": [], "uncovered": []},
        gaps=[],
        research_data={
            "schema_version": 1,
            "kind": "instruments",
            "sources": [],
            "items": [],
            "hypotheses": task.get("candidate_hypotheses", []),
        },
    )
    if task["payload_type"] == "valuation":
        result["research_data"] = {
            "schema_version": 1,
            "kind": "valuation",
            "sources": [],
            "items": [],
        }
    return result


def portfolio_risk(portfolio, dossiers):
    """One-level fund look-through; missing composition remains an explicit unknown.

    Values are usable only in snapshot base currency. A currency conversion is never guessed.
    """
    snapshot = portfolio["snapshot"]
    total = number(snapshot["total_value"])
    require(total >= 0, "Negative portfolio total")
    base = snapshot["base_currency"]
    by_id = {i["instrument_id"]: i for i in dossiers["items"]}
    direct, indirect, unknown, composition_dates = {}, {}, [], []
    for p in portfolio["positions"]:
        key = position_key(p)
        if p["currency"] != base:
            unknown.append(key + ": Währungsumrechnung fehlt")
            continue
        amount = number(p["market_value"])
        require(amount >= 0, "Negative holding value")
        direct[key] = direct.get(key, Decimal(0)) + amount
        item = by_id.get(key, {})
        if p["asset_type"].upper() in ("ETF", "ETC", "FUND"):
            exposures = item.get("exposures", [])
            known_weight = sum((number(e["weight"]) for e in exposures), Decimal(0))
            if known_weight < 1:
                unknown.append(key + ": Zusammensetzung unvollständig")
            for e in exposures:
                target = e["instrument_id"]
                indirect[target] = indirect.get(target, Decimal(0)) + amount * number(e["weight"])
                composition_dates.append(
                    {"fund": key, "instrument_id": target, "as_of": e["as_of"]}
                )
    rows = []
    for key in sorted(direct.keys() | indirect.keys()):
        exposure = direct.get(key, Decimal(0)) + indirect.get(key, Decimal(0))
        rows.append(
            {
                "instrument_id": key,
                "direct": str(direct.get(key, Decimal(0))),
                "indirect": str(indirect.get(key, Decimal(0))),
                "total": str(exposure),
                "portfolio_weight": str(exposure / total) if total else None,
            }
        )
    return {
        "base_currency": base,
        "portfolio_total": str(total),
        "cash": str(number(snapshot["cash_value"])),
        "exposures": rows,
        "unknown": unknown,
        "composition_dates": composition_dates,
        "aggregation": "Direct holdings and underlying exposures overlap; do not sum all rows.",
    }


def compare_facts(actual, baseline):
    for key in ("metric", "unit", "currency", "period", "basis"):
        require(actual[key] == baseline[key], "Noncomparable fact: " + key)
    require(actual["value_kind"] == "actual", "Actual value required")
    a, b = number(actual["value"]), number(baseline["value"])
    return {
        "difference": str(a - b),
        "relative_difference": str((a - b) / b) if b > 0 else None,
        "difference_unit": "percentage_points" if actual["unit"] == "percent" else actual["unit"],
        "comparison_kind": baseline["value_kind"],
    }


def aggregate(results, run_id):
    """Publish each report separately, merging only the two instrument dossier tasks."""
    reports = []
    groups = [("market",), ("holdings", "candidates"), ("valuation",), ("risk",)]
    if "finder" in results:
        groups.insert(1, ("finder",))
    for group in groups:
        rows = [results[k] for k in group]
        data = copy.deepcopy(rows[0]["research_data"])
        if len(rows) > 1:
            data = {
                "schema_version": 1,
                "kind": "instruments",
                "sources": [],
                "items": [],
                "hypotheses": [],
            }

            def remap(value, prefix):
                if isinstance(value, list):
                    return [remap(v, prefix) for v in value]
                if isinstance(value, dict):
                    return {
                        k: (v if v.startswith(prefix) else prefix + v)
                        if k == "source_id"
                        else [x if x.startswith(prefix) else prefix + x for x in v]
                        if k == "source_ids"
                        else remap(v, prefix)
                        for k, v in value.items()
                    }
                return value

            for task, row in zip(group, rows, strict=True):
                part = remap(row["research_data"], task + ":")
                for key in ("sources", "items", "hypotheses"):
                    data[key].extend(part[key])
        reports.append(
            {
                "id": str(uuid.uuid5(uuid.UUID(str(run_id)), "report:" + rows[0]["analysis_type"])),
                "analysis_type": rows[0]["analysis_type"],
                "content_markdown": "\n\n---\n\n".join(r["content_markdown"] for r in rows),
                "researched_at": max((r["researched_at"] for r in rows), key=stamp),
                "research_data": data,
            }
        )
    return reports


def validate_investment_strategy(value, prepared):
    """Shared proposal gate; service recomputes independently before atomic publication."""
    try:
        from .portfolio_proposals import evaluate_portfolio_proposal, evaluate_plan_targets, allocation_rules
    except ImportError:
        from portfolio_proposals import evaluate_portfolio_proposal, evaluate_plan_targets, allocation_rules
    dashboard = prepared["dashboard"]
    plan = dashboard.get("plan")
    if prepared.get("investment_contract_version") == 1:
        require("proposal" in value, "Investment contract requires proposal (null for no allocation change)")
    update = value.get("plan_update") or {}
    rules = update.get("allocation_rules", (plan or {}).get("allocation_rules"))
    if "allocation_rules" in update or rules is not None:
        allocation_rules(rules)
    proposal = value.get("proposal")
    if proposal is None and not (update and rules):
        return None
    evidence = {"items": []}
    for report in dashboard.get("reports", []):
        if report["analysis_type"] == "instrument.research":
            evidence["items"].extend(report["research_data"]["items"])
    target_check = None
    if update and rules:
        target_check = evaluate_plan_targets({k: dashboard[k] for k in ("snapshot", "positions")}, plan["version"] if plan else 0, rules, evidence)
        require(not target_check or not target_check["violations"], "Invalid plan targets: " + "; ".join((target_check or {}).get("violations", [])))
    if proposal is None:
        return {"target_check": target_check} if target_check else None
    evaluation = evaluate_portfolio_proposal(
        {k: dashboard[k] for k in ("snapshot", "positions")},
        plan["version"] if plan else 0, proposal, rules, evidence)
    require(not evaluation["violations"], "Invalid portfolio proposal: " + "; ".join(evaluation["violations"]))
    evaluation["target_check"] = target_check
    return evaluation
