# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.27.1"]
# ///
"""Portable advisory tools for MCP clients. All personal inputs come from the caller."""

import argparse
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, StringConstraints, model_validator
from research_contract import portfolio_risk

ROOT = Path(__file__).resolve().parents[1]
Skill = Literal[
    "instrument-research",
    "market-discovery-research",
    "portfolio-risk-research",
    "valuation-thesis-research",
    "portfolio-strategy",
]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Amount = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=32)]
server = FastMCP(
    "portfolio-advisory", host="127.0.0.1", stateless_http=True, json_response=True
)


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def research_guidance(skill: Skill) -> str:
    """Load a Portfolio Analyser research method and its referenced documents for a chat client."""
    files = {}
    references = (ROOT / "references").resolve()

    def include(path):
        if path in files:
            return
        content = path.read_text(encoding="utf-8")
        files[path] = content
        for link in re.findall(r"\]\(([^)#]+\.md)(?:#[^)]*)?\)", content):
            target = (path.parent / link).resolve()
            if target.is_relative_to(references):
                include(target)

    include(ROOT / "skills" / skill / "SKILL.md")
    return "\n\n".join(f"## {p.relative_to(ROOT)}\n\n{s}" for p, s in files.items())


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], default="stdio"
    )
    server.run(transport=parser.parse_args().transport)
