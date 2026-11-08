"""Run only inside a fresh test container. The model fixture uses loopback."""

import json
import os
import re
import signal
import subprocess
import sys
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

sys.path.insert(0, "/opt/always-on")
from install_package import stage

TOOL = "portfolio__portfolio_exposure"
NATIVE_SKILLS = {
    "earnings-analysis", "earnings-monitor", "instrument-research", "market-discovery-research", "portfolio-analyser-setup", "portfolio-import",
    "portfolio-risk-research", "portfolio-strategy", "run-analysis", "valuation-thesis-research",
}
POSITIONS = {
    "base_currency": "EUR", "total_value": 1000, "cash_value": 200,
    "positions": [{"name": "Fixture ETF", "asset_type": "ETF", "currency": "EUR", "market_value": 800}],
}

MANIFEST = {
    "as_of": "2026-10-01", "base_currency": "EUR", "reported_total_value": "1000",
    "cash_value": "200", "warnings": [], "positions": [
        {**POSITIONS["positions"][0], "market_value": "800", "quantity": "8", "price": "100"},
    ],
}
class Model(BaseHTTPRequestHandler):
    """Ask for one actual tool call, then record its result from the next request."""

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        offered = {tool["function"]["name"] for tool in request["tools"]}
        results = [m["content"] for m in request["messages"] if m["role"] == "tool"]
        self.server.requests.append((offered, results, request["messages"]))
        requests = self.server.tool_calls
        delta, reason = {"content": "Finished"}, "stop"
        if TOOL in offered and len(results) < len(requests):
            tool, arguments = requests[len(results)]
            delta = {"tool_calls": [{"index": 0, "id": f"test_{len(results)}", "type": "function",
                       "function": {"name": tool, "arguments": json.dumps(arguments)}}]}
            reason = "tool_calls"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for part, finish in [({"role": "assistant"}, None), (delta, None), ({}, reason)]:
            chunk = {"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": "fixture", "choices": [{"index": 0, "delta": part, "finish_reason": finish}]}
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


def cli(*args):
    return subprocess.check_output(["openclaw", *args], text=True, timeout=90)


def turn(http, session):
    http.requests = []
    cli("agent", "--local", "--agent", "main", "--session-id", session,
        "--message", f"Calculate the fixture with {TOOL}.", "--timeout", "60", "--json")
    assert http.requests, "OpenClaw did not contact the fixture"
    return http.requests


def check_codex(command):
    """Call MCP directly through the installed Codex client without a model turn."""
    override = "mcp_servers.portfolio.command=" + json.dumps(command)
    with subprocess.Popen(["codex", "app-server", "-c", override], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True) as proc:
        def rpc(identifier, method, params):
            message = {"id": identifier, "method": method, "params": params}
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            for line in proc.stdout:
                response = json.loads(line)
                if response.get("id") == identifier:
                    assert "error" not in response, response
                    return response["result"]
            raise RuntimeError("Codex app-server closed before replying")

        def timeout(*_):
            raise TimeoutError("Codex MCP probe timed out")

        signal.signal(signal.SIGALRM, timeout)
        signal.alarm(45)
        try:
            rpc(1, "initialize", {"clientInfo": {"name": "fixture", "title": "MCP test", "version": "1"},
                                  "capabilities": {"experimentalApi": True}})
            proc.stdin.write('{"method":"initialized"}\n')
            thread = rpc(2, "thread/start", {"ephemeral": True, "cwd": "/tmp", "approvalPolicy": "never"})
            result = rpc(3, "mcpServer/tool/call", {
                "threadId": thread["thread"]["id"], "server": "portfolio", "tool": "portfolio_exposure",
                "arguments": POSITIONS,
            })
            assert not result.get("isError") and result["structuredContent"]["exposures"][0]["portfolio_weight"] == "0.8"
        finally:
            signal.alarm(0)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Codex app-server: actual portfolio_exposure result 80%")


def main(wheel, previous=None):
    config = Path.home() / ".openclaw/openclaw.json"
    assert not config.exists() and os.getuid() != 0, "requires an empty disposable home"
    with ThreadingHTTPServer(("127.0.0.1", 0), Model) as http:
        port = http.server_port
        config.parent.mkdir()
        config.write_text(json.dumps({
            "gateway": {"mode": "local"},
            "tools": {"profile": "coding", "toolSearch": False},
            "agents": {"entries": {"main": {}}, "defaults": {"model": {"primary": "lab/fixture"}}},
            "models": {"providers": {"lab": {"baseUrl": f"http://127.0.0.1:{port}/v1",
                       "api": "openai-completions", "apiKey": "offline-fixture",
                       "models": [{"id": "fixture", "name": "fixture", "contextWindow": 128000}]}}},
        }))
        Thread(target=http.serve_forever, daemon=True).start()
        http.tool_calls = []
        assert all(TOOL not in offered for offered, _, _ in turn(http, "before-install"))
        store = Path.home() / ".local/share/thomas/portfolio-advisory"
        if previous:
            _, staged = stage(previous)
            cli("plugins", "install", "--force", "--accept-capabilities", str(staged))
            before = json.loads(cli("plugins", "inspect", "portfolio-analyser", "--json"))["plugin"]["version"]
        _, staged = stage(wheel)
        cli("plugins", "install", "--force", "--accept-capabilities", str(staged))
        command = json.loads((staged / ".mcp.json").read_text())["mcpServers"]["portfolio"]
        info = json.loads(cli("plugins", "inspect", "portfolio-analyser", "--runtime", "--json"))
        installed = Path(info["plugin"]["rootDir"])
        with zipfile.ZipFile(wheel) as archive:
            packaged_skills = {
                Path(name).parent.name for name in archive.namelist()
                if name.startswith("portfolio_advisory/skills/") and name.endswith("/SKILL.md")
            }
            assert packaged_skills == NATIVE_SKILLS, packaged_skills ^ NATIVE_SKILLS
            for reference in ("normalized-input.md", "mcp-contract.md"):
                assert archive.read(f"portfolio_advisory/skills/portfolio-import/references/{reference}")
            version = json.loads(archive.read("portfolio_advisory/.codex-plugin/plugin.json"))["version"]
        assert info["plugin"]["version"] == version
        if previous:
            assert before != version
            print(f"Upgraded {before} to {version}")
        with zipfile.ZipFile(wheel) as archive:
            # Compare all runtime content including scripts, nested references and roles.
            for name in archive.namelist():
                path = Path(name)
                if path.parts[0] != "portfolio_advisory" or name.endswith("/"):
                    continue
                if path.parts[1].startswith("."):
                    continue
                assert (installed.joinpath(*path.parts[1:])).read_bytes() == archive.read(name), name
        rows = json.loads(cli("skills", "list", "--json"))["skills"]
        portfolio = [row for row in rows if row["name"] in NATIVE_SKILLS]
        assert {row["name"] for row in portfolio} == NATIVE_SKILLS
        assert all(row["eligible"] and row["description"] for row in portfolio)
        assert not json.loads(config.read_text()).get("mcp", {}).get("servers")
        http.tool_calls = [("skills_read", {"name": "portfolio-risk-research"})]
        _, skill_text, _ = turn(http, "native-skill-reference")[-1]
        link = re.search(r"\[portfolio risk\]\(([^)]+)\)", skill_text[0])
        risk_reference = installed / "references/research/portfolio-risk.md"
        assert link and Path(link[1]) == risk_reference, skill_text[0]
        http.tool_calls = [
            ("read", {"path": str(installed / "skills/portfolio-import/SKILL.md")}),
            ("portfolio__build_portfolio_snapshot", {"manifests": [MANIFEST]}),
            (TOOL, POSITIONS),
            ("read", {"path": link[1]}),
        ]
        calls = turn(http, "bundle-only")
        offered, values, _ = calls[-1]
        assert {name for name in offered if name.startswith("portfolio__")} == {
            "portfolio__build_portfolio_snapshot", TOOL,
        }, sorted(offered)
        assert len(values) == len(http.tool_calls), (offered, len(values))
        assert "publish_portfolio_snapshot_and_analysis" in values[0], values[0][:800]
        start = json.dumps(calls[0][2], ensure_ascii=False)
        visible = [row["name"] for row in portfolio if row["name"] in start and row["description"] in start]
        print(f"First embedded request: {len(visible)} exact native names/descriptions; {visible}", flush=True)
        assert set(visible) == NATIVE_SKILLS, f"Missing on first turn: {NATIVE_SKILLS - set(visible)}"
        def structured(text):
            assert "structuredContent:\n" in text, text[:900]
            return json.JSONDecoder().raw_decode(text.split("structuredContent:\n", 1)[1])[0]
        assert structured(values[1])["snapshot"]["total_value"] == "1000"
        assert structured(values[2])["exposures"][0]["portfolio_weight"] == "0.8"
        assert risk_reference.read_text().strip() in values[3], values[3][:800]
        http.shutdown()
        print(f"Bundle {version}: {len(NATIVE_SKILLS)} native skills, import and linked risk reference read, EUR 1000 snapshot, 80% ETF")
    print(cli("plugins", "update", "portfolio-analyser", "--dry-run"))
    # Exercise the documented reinstall through stdin and the actual host entry point.
    with wheel.open("rb") as stream:
        subprocess.run([sys.executable, "/opt/always-on/install_package.py", wheel.name], stdin=stream, check=True)
    assert json.loads(config.read_text())["mcp"]["servers"]["portfolio"]["command"] == command["command"]
    assert TOOL in json.loads(cli("mcp", "probe", "portfolio", "--json"))["tools"]
    print("Managed connection verified")
    check_codex(command["command"])


if __name__ == "__main__":
    main(*(Path(arg) for arg in sys.argv[1:]))
