"""Bounded evidence screening, not a data provider or attractiveness ranking."""

import operator

try:
    from .research_contract import fields, require, number, stamp, validate_instrument
except ImportError:
    from research_contract import fields, require, number, stamp, validate_instrument

OPS = {"gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le}


def screen_opportunities(universe, dossiers, criteria, research_cutoff):
    require(
        isinstance(universe, list) and isinstance(dossiers, list) and criteria,
        "Supply universe, dossiers and explicit criteria",
    )
    cutoff = stamp(research_cutoff)
    identities = {}
    for item in universe:
        validate_instrument(item)
        require(
            item["instrument_id"] not in identities, "Duplicate universe instrument"
        )
        identities[item["instrument_id"]] = item
    by_id = {d["instrument_id"]: d for d in dossiers}
    require(
        len(by_id) == len(dossiers) and set(by_id) <= identities.keys(),
        "Duplicate or out-of-universe dossier",
    )
    for criterion in criteria:
        fields(
            criterion,
            ("metric", "operator", "threshold", "unit", "currency", "period", "basis"),
        )
        require(criterion["operator"] in OPS, "Unknown comparison")
        number(criterion["threshold"])
    results = []
    for key in identities:
        d = by_id.get(key, {})
        sources = {s["source_id"]: s for s in d.get("sources", [])}
        missing, failed, used = [], [], set()
        for rule in criteria:
            matches = [
                f
                for f in d.get("facts", [])
                if all(
                    f.get(k) == rule[k]
                    for k in ("metric", "unit", "currency", "period", "basis")
                )
                and f.get("value_kind") == "actual"
                and f.get("value") is not None
            ]
            if len(matches) != 1:
                missing.append(
                    rule["metric"] + ": missing or ambiguous comparable actual"
                )
                continue
            fact = matches[0]
            references = fact.get("source_ids", [])

            def available(sid):
                source = sources.get(sid)
                if not source:
                    return False
                when = source.get("published_at") or d.get("available_by", {}).get(sid)
                return bool(when and stamp(when) <= cutoff)

            if not references or not all(available(sid) for sid in references):
                missing.append(rule["metric"] + ": point-in-time evidence missing")
                continue
            used.update(references)
            if not OPS[rule["operator"]](
                number(fact["value"]), number(rule["threshold"])
            ):
                failed.append(rule["metric"])
        results.append(
            {
                "instrument": identities[key],
                "status": "unassessed"
                if missing
                else "not_matched"
                if failed
                else "matched",
                "gaps": missing,
                "failed_criteria": failed,
                "sources": [sources[s] for s in sorted(used)],
            }
        )
    return {
        "research_cutoff": cutoff.isoformat(),
        "universe_count": len(universe),
        "supplied_count": len(dossiers),
        "assessed_count": sum(r["status"] != "unassessed" for r in results),
        "criteria": criteria,
        "results": results,
        "meaning": "Matched supplied rules in this explicit universe; not a buy recommendation or a whole-market scan.",
    }
