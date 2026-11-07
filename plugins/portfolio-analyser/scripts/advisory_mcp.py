# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.27.1"]
# ///
"""Portable advisory tools for MCP clients. All personal inputs come from the caller."""

import argparse
import sys
from datetime import date
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Annotated

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


class ToolsOnlyServer(FastMCP):
    """Register just the two MCP protocol methods used by this tool server."""

    def _setup_handlers(self) -> None:
        # FastMCP 1.x otherwise advertises empty prompt and resource catalogs.
        self._mcp_server.list_tools()(self.list_tools)
        self._mcp_server.call_tool(validate_input=False)(self.call_tool)


server = ToolsOnlyServer(
    "portfolio-advisory", host="127.0.0.1", stateless_http=True, json_response=True
)


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
