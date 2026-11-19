"""Deterministic, non-executing portfolio transitions. Values are in snapshot currency."""

from copy import deepcopy
from decimal import localcontext

try:
    from .research_contract import (
        fields,
        require,
        number,
        position_key,
        validate_instrument,
        portfolio_risk,
        digest,
    )
except ImportError:
    from research_contract import (
        fields,
        require,
        number,
        position_key,
        validate_instrument,
        portfolio_risk,
        digest,
    )


def allocation_rules(value):
    fields(value, ("currency", "targets", "max_exposure", "cash_buffer", "rationale"))
    require(
        len(value["currency"]) == 3 and value["currency"].isupper(),
        "Invalid rule currency",
    )
    require(
        isinstance(value["rationale"], str) and value["rationale"].strip(),
        "Rules need an explicit rationale",
    )
    for key in ("targets", "max_exposure"):
        require(isinstance(value[key], dict), "Expected instrument weight mapping")
        for instrument, weight in value[key].items():
            require(
                isinstance(instrument, str)
                and instrument.strip()
                and 0 <= number(weight) <= 1,
                "Invalid rule weight",
            )
    require(
        not value["targets"] or sum(map(number, value["targets"].values())) == 1,
        "Target weights must total 100%, including CASH",
    )
    require(number(value["cash_buffer"]) >= 0, "Negative cash buffer")
    return value


def _evaluate_portfolio_proposal(
    portfolio, plan_version, proposal, rules=None, dossiers=None
):
    fields(
        proposal,
        ("snapshot_id", "plan_version", "changes", "cost_reserve", "conditional_sales"),
    )
    snapshot = portfolio["snapshot"]
    require(
        proposal["snapshot_id"] == snapshot["id"]
        and proposal["plan_version"] == plan_version,
        "Proposal snapshot or plan version is stale",
    )
    require(
        type(proposal["conditional_sales"]) is bool, "conditional_sales must be boolean"
    )
    require(isinstance(proposal["changes"], list), "Changes must be a list")
    costs, cash, total = map(
        number,
        (proposal["cost_reserve"], snapshot["cash_value"], snapshot["total_value"]),
    )
    require(costs >= 0 and total > 0 and cash >= 0, "Invalid portfolio or costs")
    base = snapshot["base_currency"]
    positions = {}
    for p in portfolio["positions"]:
        key = position_key(p)
        require(
            key not in positions
            and p["currency"] == base
            and number(p["market_value"]) >= 0,
            "Duplicate position, missing FX or negative value",
        )
        positions[key] = deepcopy(p)
    require(
        cash + sum(number(p["market_value"]) for p in positions.values()) == total,
        "Portfolio does not reconcile",
    )
    if rules is not None:
        allocation_rules(rules)
        require(rules["currency"] == base, "Rule currency mismatch")
    gaps = (
        []
        if rules
        else ["No structured allocation rules; no limits inferred from plan prose."]
    )
    if costs == 0:
        gaps.append("Zero cost reserve; fees and taxes have not been allowed for.")
    errors, seen, buys, sales = [], set(), number(0), number(0)
    for change in proposal["changes"]:
        fields(change, ("instrument", "value_change"))
        i = change["instrument"]
        validate_instrument(i)
        key = i["instrument_id"]
        require(
            key not in seen and i["currency"] == base, "Duplicate change or missing FX"
        )
        seen.add(key)
        delta = number(change["value_change"])
        require(delta != 0, "Omit zero changes")
        if key in positions:
            require(
                all(
                    positions[key].get(k) == i.get(k)
                    for k in ("asset_type", "isin", "symbol")
                ),
                "Changed instrument identity",
            )
        p = positions.setdefault(key, {**i, "market_value": "0"})
        value = number(p["market_value"]) + delta
        if value < 0:
            errors.append(key + ": proposed sale exceeds recorded holding")
        p["market_value"] = str(value)
        buys += max(delta, 0)
        sales += max(-delta, 0)
    buffer = number(rules["cash_buffer"]) if rules else number(0)
    needed = max(number(0), buys + costs + buffer - cash)
    if needed and not proposal["conditional_sales"]:
        errors.append(
            "Purchases depend on unexecuted sales; conditional_sales must be explicit"
        )
    after_cash = cash + sales - buys - costs
    if after_cash < buffer:
        errors.append("Insufficient funding or cash buffer")
    if total - costs <= 0:
        errors.append("Costs exhaust portfolio")
    evidence = dossiers or {"items": []}
    before = portfolio_risk(portfolio, evidence)
    after = None
    weights, drift = {}, {}
    if (
        not any(number(p["market_value"]) < 0 for p in positions.values())
        and after_cash >= 0
        and total > costs
    ):
        after_portfolio = {
            "snapshot": {
                **snapshot,
                "cash_value": str(after_cash),
                "total_value": str(total - costs),
            },
            "positions": [
                p for p in positions.values() if number(p["market_value"]) > 0
            ],
        }
        after = portfolio_risk(after_portfolio, evidence)
        weights = {
            position_key(p): str(number(p["market_value"]) / (total - costs))
            for p in after_portfolio["positions"]
        }
        weights["CASH"] = str(after_cash / (total - costs))
        for key, target in (rules or {}).get("targets", {}).items():
            drift[key] = str(number(weights.get(key, "0")) - number(target))
        exposure = {
            p["instrument_id"]: number(p["portfolio_weight"])
            for p in after["exposures"]
        }
        for key, limit in (rules or {}).get("max_exposure", {}).items():
            if exposure.get(key, number(0)) > number(limit):
                errors.append(key + ": direct and indirect exposure exceeds limit")
        gaps.extend(after["unknown"])
    return {
        "status": "blocked" if errors else "incomplete" if gaps else "pass",
        "violations": errors,
        "gaps": gaps,
        "before": before,
        "after": after,
        "weights": weights,
        "target_drift": drift,
        "conditional_sale_proceeds_required": str(needed),
        "cash_after": str(after_cash),
        "cost_reserve": str(costs),
        "snapshot_id": snapshot["id"],
        "plan_version": plan_version,
        "input_fingerprint": digest(
            {
                "portfolio": portfolio,
                "plan_version": plan_version,
                "proposal": proposal,
                "rules": rules,
                "dossiers": evidence,
            }
        ),
    }


def evaluate_portfolio_proposal(
    portfolio, plan_version, proposal, rules=None, dossiers=None
):
    with localcontext() as context:
        context.prec = 80
        return _evaluate_portfolio_proposal(
            portfolio, plan_version, proposal, rules, dossiers
        )


def evaluate_plan_targets(portfolio, plan_version, rules, dossiers):
    """Check the stated final allocation separately from a smaller immediate proposal."""
    allocation_rules(rules)
    if not rules["targets"]:
        return None
    with localcontext() as context:
        context.prec = 80
        total = number(portfolio["snapshot"]["total_value"])
        identities = {position_key(p): p for p in portfolio["positions"]}
        identities.update(
            {
                i["instrument_id"]: i["instrument"]
                for i in dossiers.get("items", [])
                if i.get("instrument")
            }
        )
        current = {
            position_key(p): number(p["market_value"]) for p in portfolio["positions"]
        }
        changes = []
        for key in (set(current) | set(rules["targets"])) - {"CASH"}:
            require(
                key in identities,
                "Target instrument requires researched identity: " + key,
            )
            delta = total * number(rules["targets"].get(key, "0")) - current.get(
                key, number(0)
            )
            if delta:
                raw = identities[key]
                identity = {
                    "instrument_id": key,
                    **{
                        k: raw.get(k)
                        for k in ("isin", "symbol", "name", "asset_type", "currency")
                    },
                }
                changes.append({"instrument": identity, "value_change": str(delta)})
        proposal = {
            "snapshot_id": portfolio["snapshot"]["id"],
            "plan_version": plan_version,
            "changes": changes,
            "cost_reserve": "0",
            "conditional_sales": True,
        }
        check = _evaluate_portfolio_proposal(
            portfolio, plan_version, proposal, rules, dossiers
        )
        check["purpose"] = (
            "Final allocation at snapshot values; excludes future implementation costs."
        )
        return check
