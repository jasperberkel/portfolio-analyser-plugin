# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.27.1"]
# ///
"""Exercise the same stdio entrypoint an independent chat client registers."""

import asyncio
import shutil
from pathlib import Path
import yaml

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "plugins/portfolio-analyser"
)


async def check():
    async with (
        stdio_client(
            StdioServerParameters(command=shutil.which("portfolio-advisory") or "portfolio-advisory")
        ) as streams,
        ClientSession(*streams) as client,
    ):
        await client.initialize()
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "list_skills", "read_skill", "build_portfolio_snapshot", "portfolio_exposure",
        }
        catalog = await client.call_tool("list_skills", {})
        assert not catalog.isError
        entries = catalog.structuredContent["result"]
        expected = {path.parent.name: path for path in (SOURCE / "skills").glob("*/SKILL.md")}
        assert {entry["name"] for entry in entries} == set(expected)
        for entry in entries:
            name = entry["name"]
            source = expected[name].read_text()
            assert entry["description"] == yaml.safe_load(source.split("---", 2)[1])["description"]
            result = await client.call_tool("read_skill", {"name": name})
            assert not result.isError and source in result.content[0].text
            refs = {
                "portfolio-import": ["references/mcp-contract.md", "references/normalized-input.md"],
                "portfolio-analyser-setup": ["references/codex.md", "references/claude-code.md", "config/connection.json"],
                "run-analysis": ["workflow.json", "roles/research-agent.md", "roles/strategy-agent.md"],
            }
            for ref in refs.get(name, ["references/research-contract-v2.md"]):
                path = SOURCE / ref
                if not path.is_file():
                    path = expected[name].parent / ref
                assert f"## {path.relative_to(SOURCE)}\n\n{path.read_text()}" in result.content[0].text
        for name in ("../../outside", "missing-skill"):
            assert (await client.call_tool("read_skill", {"name": name})).isError
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
        "Independent MCP client: skill catalog, references, snapshot, exposure and invalid inputs verified."
    )
