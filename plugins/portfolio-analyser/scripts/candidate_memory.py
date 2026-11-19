"""Pure candidate history projection; contains no holdings or personal allocations."""

from copy import deepcopy


def merge_candidates(previous, reports, observed_at):
    memory = {r["instrument_id"]: deepcopy(r) for r in previous}
    by_type = {r["analysis_type"]: r["research_data"] for r in reports}
    market = by_type.get("market.discovery", {})
    for candidate in market.get("candidates", []):
        key = candidate["instrument"]["instrument_id"]
        row = memory.setdefault(
            key, {"instrument_id": key, "first_seen_at": observed_at, "research": {}}
        )
        row.update(
            candidate=deepcopy(candidate),
            last_seen_at=observed_at,
            sources=[
                deepcopy(s)
                for s in market["sources"]
                if s["source_id"] in candidate["source_ids"]
            ],
        )
    for kind in ("instrument.research", "valuation.thesis"):
        data = by_type.get(kind, {})
        for item in data.get("items", []):
            if item["instrument_id"] not in memory:
                continue
            row = memory[item["instrument_id"]]
            # Each saved dossier keeps its own source namespace and original timestamps.
            refs = set(item.get("source_ids", []))
            for name in ("facts", "events", "exposures", "theses"):
                for fact in item.get(name, []):
                    refs.update(fact.get("source_ids", []))
            row["research"][kind] = {
                "item": deepcopy(item),
                "sources": [
                    deepcopy(s)
                    for s in data.get("sources", [])
                    if s["source_id"] in refs
                ],
            }
            row["last_reviewed_at"] = observed_at
            if kind == "valuation.thesis":
                theses = item.get("theses", [])
                row["state"] = (
                    "invalidated"
                    if theses and all(t["status"] == "invalidated" for t in theses)
                    else "research_gap"
                    if item.get("gaps")
                    else "reviewed"
                )
    for row in memory.values():
        row.setdefault("state", "research_needed")
    return [memory[k] for k in sorted(memory)]


def radar_history(memory):
    # Valuation judgments and personal selection must not steer independent discovery.
    return [
        {
            k: deepcopy(row[k])
            for k in (
                "instrument_id",
                "candidate",
                "sources",
                "first_seen_at",
                "last_seen_at",
            )
        }
        for row in memory
    ]


def restore_dossiers(previous, memory, report_type, selected):
    data = deepcopy(previous) if previous else {"sources": [], "items": []}
    current = {item["instrument_id"] for item in data["items"]}
    for row in memory:
        if row["instrument_id"] not in selected or row["instrument_id"] in current:
            continue
        saved = row.get("research", {}).get(report_type)
        if not saved:
            continue
        item = deepcopy(saved["item"])
        prefix = row["instrument_id"] + ":memory:"
        for record in [
            item,
            *(
                f
                for name in ("facts", "events", "exposures", "theses")
                for f in item.get(name, [])
            ),
        ]:
            if "source_ids" in record:
                record["source_ids"] = [prefix + s for s in record["source_ids"]]
        data["items"].append(item)
        data["sources"].extend(
            {**s, "source_id": prefix + s["source_id"]} for s in saved["sources"]
        )
    return data if data["items"] else previous
