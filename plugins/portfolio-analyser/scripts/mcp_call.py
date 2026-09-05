#!/usr/bin/env python3
"""Call orchestrator MCP tools through the paired native bridge; never handle credentials."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "get_analysis_context",
    "prepare_strategy_context",
    "publish_analysis_run",
    "get_analysis",
    "get_dashboard_briefing",
    "get_portfolio_plan_version",
}


def call(tool, arguments, bridge=None, timeout=90):
    if tool not in ALLOWED and tool != "list":
        raise ValueError("This client is limited to the analysis workflow tools")
    executable = Path(bridge) if bridge else ROOT / "bin" / "portfolio-analyser-bridge"
    if not executable.exists():
        executable = executable.with_suffix(".exe")
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "run-analysis", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list" if tool == "list" else "tools/call",
            "params": {} if tool == "list" else {"name": tool, "arguments": arguments},
        },
    ]
    wire = (
        "\n".join(json.dumps(message, ensure_ascii=True) for message in messages) + "\n"
    )
    if any(len(line.encode()) >= 15 * 1024 * 1024 for line in wire.splitlines()):
        raise ValueError("MCP packet too large; not truncated")
    # communicate closes stdin and waits; no orphaned bridge or credential logging.
    process = subprocess.run(
        [str(executable), "mcp"],
        input=wire,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    responses = [
        json.loads(line) for line in process.stdout.splitlines() if line.strip()
    ]
    initialized = next((r for r in responses if r.get("id") == 1), {})
    if "error" in initialized or "result" not in initialized:
        raise RuntimeError("MCP initialization failed; check bridge status")
    response = next((r for r in responses if r.get("id") == 2), None)
    if response is None:
        raise RuntimeError(
            "MCP returned no tool response; publication outcome may be uncertain"
        )
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "MCP request failed"))
    result = response["result"]
    if result.get("isError"):
        text = "\n".join(c.get("text", "") for c in result.get("content", []))
        raise RuntimeError(text or "MCP tool failed")
    if tool == "list":
        return result
    # MCP Python versions expose either direct structured content or a result wrapper.
    if "structuredContent" in result:
        structured = result["structuredContent"]
        return structured["result"] if set(structured) == {"result"} else structured
    texts = [c["text"] for c in result.get("content", []) if c.get("type") == "text"]
    if len(texts) != 1:
        raise RuntimeError("Unexpected MCP result shape")
    return json.loads(texts[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=sorted(ALLOWED | {"list"}))
    parser.add_argument("--arguments", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bridge", type=Path)
    args = parser.parse_args()
    result = call(
        args.tool,
        json.loads(args.arguments.read_text()) if args.arguments else {},
        args.bridge,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"MCP {args.tool}: saved {args.output}")


if __name__ == "__main__":
    main()
