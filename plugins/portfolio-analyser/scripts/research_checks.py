#!/usr/bin/env python3
"""Deterministic research calculations; no data access or credential handling."""

import argparse
import json
from pathlib import Path

from research_contract import compare_facts, portfolio_risk

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["compare", "risk"])
    parser.add_argument("input")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text())
    result = (
        compare_facts(data["actual"], data["baseline"])
        if args.operation == "compare"
        else portfolio_risk(data["portfolio"], data["dossiers"])
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
