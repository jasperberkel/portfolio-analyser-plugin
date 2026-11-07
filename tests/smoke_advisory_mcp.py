# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.27.1"]
# ///
"""Exercise the same stdio entrypoint an independent chat client registers."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = (
    Path(__file__).resolve().parents[1]
    / "plugins/portfolio-analyser/scripts/advisory_mcp.py"
)


async def check():
    async with (
        stdio_client(
            StdioServerParameters(command=sys.executable, args=[str(SERVER)])
        ) as streams,
        ClientSession(*streams) as client,
    ):
        await client.initialize()
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "research_guidance",
            "portfolio_exposure",
        }
        skill_names = [
            "market-discovery-research",
            "instrument-research",
            "portfolio-risk-research",
            "valuation-thesis-research",
            "portfolio-strategy",
        ]
        for skill in skill_names:
            result = await client.call_tool("research_guidance", {"skill": skill})
            assert (
                not result.isError
                and "references/research-contract-v2.md" in result.content[0].text
            )
        invalid = await client.call_tool(
            "research_guidance", {"skill": "../../outside"}
        )
        assert invalid.isError
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
        "Independent MCP client: 5 methods, exposure calculation and invalid inputs verified."
    )
