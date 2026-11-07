# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.27.1", "PyYAML>=6,<7"]
# ///
"""Portable advisory tools for MCP clients. All personal inputs come from the caller."""

import argparse
import re
import sys
from datetime import date
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Annotated

import yaml

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, StringConstraints, model_validator

ROOT = Path(__file__).resolve().parents[1]
if __package__:
    from .research_contract import portfolio_risk
    import_root = __package__.split(".")[0] + "."
else:
    from research_contract import portfolio_risk
    sys.path.insert(0, str(ROOT))
    import_root = ""

# The same import helper also handles the hyphenated Agent Skills directory.
build_payload = import_module(
    import_root + "skills.portfolio-import.scripts.build_portfolio_snapshot"
).build_payload
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Amount = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=32)]
server = FastMCP(
    "portfolio-advisory", host="127.0.0.1", stateless_http=True, json_response=True
)


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def list_skills() -> list[dict[str, str]]:
    """List available skills and short descriptions. Use read_skill for one method."""
    catalog = []
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        front, header, _ = path.read_text(encoding="utf-8").split("---", 2)
        metadata = yaml.safe_load(header)
        if front.strip() or metadata["name"] != path.parent.name:
            raise ValueError(f"Invalid skill metadata in {path.parent.name}")
        catalog.append({"name": metadata["name"], "description": metadata["description"]})
    return catalog


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def read_skill(name: str) -> str:
    """Read one skill and its packaged references. Request linked skills separately."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Invalid skill name")
    skill = ROOT / "skills" / name / "SKILL.md"
    if not skill.is_file() or not skill.resolve().is_relative_to(ROOT):
        raise ValueError("Unknown skill")
    files = {}

    def include(path):
        if path in files:
            return
        content = path.read_text(encoding="utf-8")
        files[path] = content
        for link in re.findall(r"\]\(([^)#]+\.(?:md|json))(?:#[^)]*)?\)", content):
            if "://" in link or link.startswith("/"):
                continue
            target = (path.parent / link).resolve()
            if target.is_relative_to(ROOT) and target.name != "SKILL.md":
                include(target)

    include(skill)
    return "\n\n".join(f"## {p.relative_to(ROOT)}\n\n{s}" for p, s in files.items())


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def build_portfolio_snapshot(manifests: list[dict[str, object]]) -> dict[str, object]:
    """Validate and merge normalized source manifests from portfolio-import, without publishing."""
    return build_payload(manifests)


class Position(BaseModel):
    name: Text
    asset_type: Text
    currency: Currency
    market_value: Amount
    isin: Text | None = None
    symbol: Text | None = None


class Constituent(BaseModel):
    instrument_id: Text
    weight: Annotated[Decimal, Field(ge=0, le=1)]
    as_of: date


class FundComposition(BaseModel):
    instrument_id: Text
    exposures: list[Constituent]

    @model_validator(mode="after")
    def valid_weights(self):
        ids = [item.instrument_id for item in self.exposures]
        if len(ids) != len(set(ids)) or sum(item.weight for item in self.exposures) > 1:
            raise ValueError("Fund constituents must be unique and total at most 100%.")
        return self


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def portfolio_exposure(
    base_currency: Currency,
    total_value: Amount,
    cash_value: Amount,
    positions: list[Position],
    fund_compositions: list[FundComposition] | None = None,
) -> dict[str, object]:
    """Calculate portfolio weights from a supplied snapshot, including dated optional fund holdings.

    Use the reported total in base_currency, including cash. Position market values are in
    each position's currency. Use fractional constituent weights. Missing FX or composition
    is reported as unknown. Fund identifiers match the position ISIN or TYPE:CURRENCY:symbol/name.
    """
    funds = fund_compositions or []
    if len({fund.instrument_id for fund in funds}) != len(funds):
        raise ValueError("Supply at most one dated composition per fund.")
    portfolio = {
        "snapshot": {
            "base_currency": base_currency,
            "cash_value": cash_value,
            "total_value": total_value,
        },
        "positions": [p.model_dump(mode="json") for p in positions],
    }
    return portfolio_risk(
        portfolio, {"items": [f.model_dump(mode="json") for f in funds]}
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], default="stdio"
    )
    server.run(transport=parser.parse_args().transport)


if __name__ == "__main__":
    main()
