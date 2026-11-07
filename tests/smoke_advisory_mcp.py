# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.27.1"]
# ///
"""Exercise the same stdio entrypoint an independent chat client registers."""

import asyncio
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def check():
    async with (
        stdio_client(
            StdioServerParameters(command=shutil.which("portfolio-advisory") or "portfolio-advisory")
        ) as streams,
        ClientSession(*streams) as client,
    ):
        capabilities = (await client.initialize()).capabilities
        assert capabilities.tools and capabilities.resources is None and capabilities.prompts is None
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "build_portfolio_snapshot", "portfolio_exposure",
        }
        manifest = {
            "as_of": "2026-10-01", "base_currency": "EUR", "cash_value": "200",
            "reported_total_value": "1000", "warnings": [], "positions": [{
                "name": "Example ETF", "asset_type": "ETF", "currency": "EUR",
                "quantity": "8", "price": "100", "market_value": "800",
            }],
        }
        snapshot = await client.call_tool("build_portfolio_snapshot", {"manifests": [manifest]})
        assert not snapshot.isError, snapshot.content
        assert snapshot.structuredContent["snapshot"]["total_value"] == "1000"
        manifest["reported_total_value"] = "1100"
        assert (await client.call_tool("build_portfolio_snapshot", {"manifests": [manifest]})).isError
        data = {
            "base_currency": "EUR",
            "total_value": "1000",
            "cash_value": "200",
            "positions": [
                {
                    "name": "Example Fund",
                    "isin": "FUND",
                    "asset_type": "ETF",
                    "currency": "EUR",
                    "market_value": "800",
                },
            ],
            "fund_compositions": [
                {
                    "instrument_id": "FUND",
                    "exposures": [
                        {
                            "instrument_id": "Example Co",
                            "weight": "0.25",
                            "as_of": "2026-10-01",
                        }
                    ],
                }
            ],
        }
        result = await client.call_tool("portfolio_exposure", data)
        assert not result.isError, result.content
        rows = {
            row["instrument_id"]: row for row in result.structuredContent["exposures"]
        }
        assert rows["Example Co"]["portfolio_weight"] == "0.20"
        assert rows["FUND"]["portfolio_weight"] == "0.8"
        assert result.structuredContent["unknown"]
        data["fund_compositions"][0]["exposures"][0]["weight"] = "1.5"
        assert (await client.call_tool("portfolio_exposure", data)).isError


if __name__ == "__main__":
    asyncio.run(check())
    print(
        "Independent MCP client: only two tools, valid and invalid snapshots and exposures verified."
    )
