"""Synthetic financial evidence, deliberately not connected to a live portfolio."""

import copy
import uuid
from datetime import datetime, timezone

import research_contract as c

SOLAR = {
    "instrument_id": "DE0000000001",
    "isin": "DE0000000001",
    "symbol": "SOL",
    "name": "Solar AG",
    "asset_type": "STOCK",
    "currency": "EUR",
}
BATTERY = {
    "instrument_id": "DE0000000002",
    "isin": "DE0000000002",
    "symbol": "BAT",
    "name": "Batterie AG",
    "asset_type": "STOCK",
    "currency": "EUR",
}
ETF = {
    "instrument_id": "IE0000000001",
    "isin": "IE0000000001",
    "symbol": "WORLD",
    "name": "Welt-ETF",
    "asset_type": "ETF",
    "currency": "EUR",
}


def context():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "contract_version": 2,
        "research_cutoff": now,
        "source_fingerprint": "a" * 64,
        "workflow_fingerprint": "b" * 64,
        "existing_run": None,
        "previous_reports": {},
        "dashboard": {
            "snapshot": {
                "id": str(uuid.uuid4()),
                "base_currency": "EUR",
                "total_value": "1000",
                "cash_value": "100",
            },
            "positions": [
                {**i, "market_value": amount}
                for i, amount in [(ETF, "600"), (SOLAR, "300")]
            ],
            "plan": {"version": 1, "content_markdown": "PRIVATE ALLOCATION"},
            "previous_briefing": {"content_markdown": "PRIVATE PREVIOUS STRATEGY"},
        },
    }


def result(task, *, candidates=None):
    now = task["research_cutoff"]
    source = {
        "source_id": "issuer",
        "url": "https://example.com/fake-report",
        "title": "Synthetic issuer report",
        "published_at": now,
        "accessed_at": now,
        "locator": "Synthetic fixture, page 1",
    }
    value = {
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
    value.update(
        id=task["report_id"],
        content_markdown="# Testbericht\n\nSynthetische Evidenz.",
        researched_at=now,
        status="complete",
        coverage={
            "selected": task["selected"],
            "researched": task["selected"],
            "uncovered": [],
        },
        gaps=[],
    )
    kind = task["payload_type"]
    data = {"schema_version": 1, "kind": kind, "sources": [source]}
    if kind == "market":
        data.update(
            context_markdown="Speichertechnik prüfen.",
            deferred=[],
            candidates=[
                {
                    "instrument": i,
                    "hypothesis": "Speichertechnik könnte wachsen.",
                    "risks": ["Bewertung ungeprüft"],
                    "questions": ["Tragen Zahlen und Bewertung die These?"],
                    "source_ids": ["issuer"],
                }
                for i in ([BATTERY] if candidates is None else candidates)
            ],
        )
    else:
        data["items"] = []
        for instrument in task["instruments"]:
            item = {
                "instrument_id": instrument["instrument_id"],
                "content_markdown": instrument["name"] + ": geprüft.",
                "gaps": [],
            }
            if kind == "instruments":
                item.update(
                    instrument=instrument,
                    facts=[
                        {
                            "fact_id": "margin",
                            "metric": "operating_margin",
                            "value": "15",
                            "unit": "percent",
                            "currency": None,
                            "period": "2026-Q2",
                            "basis": "GAAP",
                            "value_kind": "actual",
                            "source_ids": ["issuer"],
                            "gap": None,
                        }
                    ],
                    events=[],
                    exposures=[],
                )
                if instrument["asset_type"] == "ETF":
                    item["exposures"] = [
                        {
                            "instrument_id": SOLAR["instrument_id"],
                            "weight": "0.10",
                            "as_of": now,
                            "source_ids": ["issuer"],
                        }
                    ]
            elif kind == "valuation":
                item.update(
                    health="Gemischt",
                    valuation="Kein belegter günstiger Einstieg",
                    thesis_change="Geschwächt",
                    source_ids=["issuer"],
                    theses=[
                        {
                            "thesis_id": instrument["instrument_id"] + ":margin",
                            "claim": "Marge bleibt stabil.",
                            "status": "weakened",
                            "first_seen_at": now,
                            "changed_at": now,
                            "counterevidence": ["Marge gesunken."],
                            "invalidation": "Anhaltender Margenrückgang.",
                            "source_ids": ["issuer"],
                        }
                    ],
                )
            else:
                item["source_ids"] = ["issuer"]
            if kind == "valuation" and task.get("previous_state"):
                previous = next(
                    (
                        i
                        for i in task["previous_state"]["items"]
                        if i["instrument_id"] == item["instrument_id"]
                    ),
                    None,
                )
                if previous:
                    item["theses"] = copy.deepcopy(previous["theses"])
            data["items"].append(item)
        if kind == "instruments":
            data["hypotheses"] = task.get("candidate_hypotheses", [])
        if kind == "risk":
            data.update(
                calculations=task["calculations"],
                findings=["Direkte und indirekte Konzentration prüfen."],
            )
    value["research_data"] = data
    return value


def bundle(ctx, candidates=None):
    flow = c.default_workflow()
    run_id = str(uuid.uuid4())
    rows = {}
    for task_id in ("market", "holdings", "candidates", "valuation", "risk"):
        task = c.build_input(ctx, flow, run_id, task_id, rows)
        row = (
            c.empty_result(task)
            if task["payload_type"] == "instruments" and not task["selected"]
            else result(task, candidates=candidates)
        )
        c.validate_result(row, task)
        rows[task_id] = row
    return {
        "workflow": flow,
        "run_id": run_id,
        "source_fingerprint": ctx["source_fingerprint"],
        "research_cutoff": ctx["research_cutoff"],
        "research": list(rows.values()),
    }
