"""Normalize supplied SEC companyfacts, without network access or forward-looking data.

Original implementation using the documented SEC API. Filing dates have day precision:
same-day filings are excluded until that whole New York day precedes the cutoff.
"""

from datetime import date, datetime, time, timedelta
from decimal import localcontext
from hashlib import sha256
from zoneinfo import ZoneInfo

try:
    from .research_contract import number, stamp, require
except ImportError:
    from research_contract import number, stamp, require

METRICS = {
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("ifrs-full", "Revenue"),
    ],
    "net_income": [("us-gaap", "NetIncomeLoss"), ("ifrs-full", "ProfitLoss")],
    "operating_income": [
        ("us-gaap", "OperatingIncomeLoss"),
        ("ifrs-full", "ProfitLossFromOperatingActivities"),
    ],
    "operating_cash_flow": [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
    ],
    "diluted_eps": [
        ("us-gaap", "EarningsPerShareDiluted"),
        ("ifrs-full", "DilutedEarningsLossPerShare"),
    ],
}


def _normalize_company_facts(companyfacts, research_cutoff, accessed_at, expected_cik):
    """Return contract-compatible facts/sources plus explicit gaps; never fetch a URL.

    Durations retain their exact bounds. Only additive flows can be differenced;
    EPS, currencies and taxonomy concepts are never mixed or silently converted.
    """
    cutoff, accessed = stamp(research_cutoff), stamp(accessed_at)
    require(accessed >= cutoff, "Access time must not precede research cutoff")
    cik = str(int(companyfacts["cik"]))
    require(cik == str(int(expected_cik)), "Companyfacts issuer mismatch")
    facts, sources, gaps, availability = [], {}, [], {}
    for metric, concepts in METRICS.items():
        selected = {}
        for taxonomy, concept in concepts:
            units = (
                companyfacts.get("facts", {})
                .get(taxonomy, {})
                .get(concept, {})
                .get("units", {})
            )
            for unit, rows in units.items():
                currency = unit.removesuffix("/shares")
                if (
                    len(currency) != 3
                    or not currency.isalpha()
                    or not currency.isupper()
                ):
                    gaps.append(f"{metric}: unsupported unit {unit}")
                    continue
                if (metric == "diluted_eps") != unit.endswith("/shares"):
                    gaps.append(f"{metric}: incompatible unit {unit}")
                    continue
                latest = {}
                for row in rows:
                    if row.get("form", "").split("/")[0] not in {
                        "10-Q",
                        "10-K",
                        "20-F",
                        "40-F",
                    }:
                        continue
                    if (
                        not row.get("start")
                        or not row.get("filed")
                        or not row.get("accn")
                    ):
                        continue
                    filed = date.fromisoformat(row["filed"])
                    available = datetime.combine(
                        filed + timedelta(days=1), time(), ZoneInfo("America/New_York")
                    )
                    if available > cutoff:
                        continue
                    start, end = (
                        date.fromisoformat(row["start"]),
                        date.fromisoformat(row["end"]),
                    )
                    require(start <= end <= filed, "Invalid financial reporting period")
                    key = (row["start"], row["end"], unit)
                    rank = (row["filed"], row["accn"])
                    if key in latest and rank == latest[key][0]:
                        require(
                            number(row["val"]) == number(latest[key][1]["val"]),
                            "Conflicting facts in one filing",
                        )
                    if key not in latest or rank > latest[key][0]:
                        latest[key] = (rank, row)
                for key, (_, row) in latest.items():
                    # Prefer the first configured concept; never label a different unit as its value.
                    if key in selected:
                        continue
                    accession = row["accn"]
                    require(
                        all(c.isdigit() or c == "-" for c in accession),
                        "Invalid accession",
                    )
                    sid = (
                        "sec:" + sha256(f"{cik}:{accession}".encode()).hexdigest()[:20]
                    )
                    availability[sid] = datetime.combine(
                        date.fromisoformat(row["filed"]) + timedelta(days=1),
                        time(),
                        ZoneInfo("America/New_York"),
                    ).isoformat()
                    sources[sid] = {
                        "source_id": sid,
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/",
                        "title": f"SEC {row['form']} filed {row['filed']}",
                        "published_at": None,
                        "accessed_at": accessed.isoformat(),
                        "locator": f"Accession {accession}; filing date {row['filed']} (day precision)",
                    }
                    selected[key] = {
                        "metric": metric,
                        "value": str(number(row["val"])),
                        "unit": "currency_per_share"
                        if metric == "diluted_eps"
                        else "currency",
                        "currency": currency,
                        "period": key[0] + "/" + key[1],
                        "basis": taxonomy + ":" + concept,
                        "value_kind": "actual",
                        "source_ids": [sid],
                        "gap": None,
                    }
        values = list(selected.values())
        if not values:
            gaps.append(metric + ": no comparable filed data available by cutoff")
        if metric != "diluted_eps":
            # Derive a quarter/half-year from compatible cumulative flows only.
            for whole in list(values):
                start, end = map(date.fromisoformat, whole["period"].split("/"))
                previous = [
                    v
                    for v in values
                    if v["period"].split("/")[0] == start.isoformat()
                    and v["period"].split("/")[1] < end.isoformat()
                    and (v["basis"], v["currency"])
                    == (whole["basis"], whole["currency"])
                ]
                if not previous:
                    continue
                prior = max(previous, key=lambda v: v["period"])
                sub_start = date.fromisoformat(
                    prior["period"].split("/")[1]
                ) + timedelta(days=1)
                period = sub_start.isoformat() + "/" + end.isoformat()
                if not 70 <= (end - sub_start).days <= 200 or any(
                    v["period"] == period and v["currency"] == whole["currency"]
                    for v in values
                ):
                    continue
                values.append(
                    {
                        **whole,
                        "period": period,
                        "value": str(number(whole["value"]) - number(prior["value"])),
                        "basis": whole["basis"] + "; derived cumulative difference",
                        "source_ids": sorted(
                            set(whole["source_ids"] + prior["source_ids"])
                        ),
                    }
                )
            quarters = sorted(
                [
                    v
                    for v in values
                    if 70
                    <= (
                        date.fromisoformat(v["period"].split("/")[1])
                        - date.fromisoformat(v["period"].split("/")[0])
                    ).days
                    <= 110
                ],
                key=lambda v: v["period"],
            )
            groups = {}
            for value in quarters:
                groups.setdefault(
                    (value["basis"].split(";")[0], value["currency"]), []
                ).append(value)
            for (basis, currency), series in groups.items():
                for index in range(3, len(series)):
                    window = series[index - 3 : index + 1]
                    bounds = [
                        tuple(map(date.fromisoformat, v["period"].split("/")))
                        for v in window
                    ]
                    if (
                        not all(
                            bounds[n][1] + timedelta(days=1) == bounds[n + 1][0]
                            for n in range(3)
                        )
                        or not 350 <= (bounds[-1][1] - bounds[0][0]).days <= 380
                    ):
                        continue
                    values.append(
                        {
                            **window[-1],
                            "period": bounds[0][0].isoformat()
                            + "/"
                            + bounds[-1][1].isoformat(),
                            "value": str(sum(number(v["value"]) for v in window)),
                            "basis": basis + "; trailing twelve months derived",
                            "currency": currency,
                            "source_ids": sorted(
                                {s for v in window for s in v["source_ids"]}
                            ),
                        }
                    )
        for value in values:
            value["fact_id"] = (
                "fundamental:"
                + sha256(
                    repr(
                        (metric, value["period"], value["currency"], value["basis"])
                    ).encode()
                ).hexdigest()[:20]
            )
            facts.append(value)
    return {
        "facts": facts,
        "sources": list(sources.values()),
        "gaps": sorted(set(gaps)),
        "research_cutoff": cutoff.isoformat(),
        "cik": cik,
        "available_by": availability,
        "limitations": [
            "Entity-wide standard taxonomy facts only; inspect original filings for segments, custom tags and non-GAAP figures.",
            "Filing dates do not establish an intraday publication time. No derived EPS or inferred analyst consensus.",
        ],
    }


def normalize_company_facts(companyfacts, research_cutoff, accessed_at, expected_cik):
    with localcontext() as context:
        context.prec = 80
        return _normalize_company_facts(
            companyfacts, research_cutoff, accessed_at, expected_cik
        )
