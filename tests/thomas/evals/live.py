"""Run one fresh, network-disabled OpenClaw container per synthetic prompt.

The host relays model decisions through either an explicit OpenAI-compatible
HTTPS endpoint or an opt-in Codex login with structured CLI decisions. The
scorecard, provider credentials, host filesystem and real Thomas home remain
outside the guest. --transport-smoke uses a local scripted response.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else None
HARNESS = "openclaw agent --local / embedded / openai-completions"
LIMIT = 16 * 1024 * 1024


def emit(stream, value):
    stream.write(json.dumps(value, ensure_ascii=True) + "\n")
    stream.flush()


def receive(stream):
    line = stream.readline()
    if not line:
        raise EOFError("Relay closed")
    return json.loads(line)


class Loopback(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        if self.path != "/v1/chat/completions" or not 0 < size <= LIMIT:
            self.send_error(400)
            return
        payload = json.loads(self.rfile.read(size))
        emit(sys.stdout, {"provider_request": payload})
        header = receive(sys.stdin)
        self.send_response(header["status"])
        self.send_header("Content-Type", header["content_type"])
        self.end_headers()
        while True:
            chunk = receive(sys.stdin)["chunk"]
            if chunk is None:
                break
            self.wfile.write(base64.b64decode(chunk))
            self.wfile.flush()

    def log_message(self, *args):
        pass


def parse_result(message):
    content = message["content"]
    if not message["toolName"].startswith("portfolio__"):
        return content
    details = message.get("details")
    if isinstance(details, dict) and "structuredContent" in details:
        return details
    for block in content:
        text = block.get("text", "")
        if "structuredContent:\n" in text:
            structured, _ = json.JSONDecoder().raw_decode(text.split("structuredContent:\n", 1)[1].lstrip())
            return {"structuredContent": structured}
    return content


def session_trace(workspace, session):
    subprocess.run(["openclaw", "sessions", "export-trajectory", "--agent", "main",
                    "--session-key", "agent:main:explicit:" + session, "--workspace", str(workspace),
                    "--output", "proof", "--json"], check=True, stdin=subprocess.DEVNULL,
                   stdout=sys.stderr, timeout=60)
    export = workspace / ".openclaw/trajectory-exports/proof/events.jsonl"
    events = [json.loads(line) for line in export.read_text().splitlines()]
    transcript = sorted((e for e in events if e["source"] == "transcript"), key=lambda e: e["sourceSeq"])
    messages = [e["data"]["message"] for e in transcript
                if e["type"] in ("user.message", "assistant.message", "tool.result")]
    calls = {}
    final = ""
    for message in messages:
        if message["role"] == "assistant":
            final = ""
            for part in message["content"]:
                if part["type"] == "toolCall":
                    cid = part["id"]
                    if cid in calls:
                        raise ValueError("Duplicate tool call")
                    calls[cid] = {"id": cid, "name": part["name"], "arguments": part["arguments"]}
                if part["type"] == "text":
                    final += part["text"]
        elif message["role"] == "toolResult":
            call = calls[message["toolCallId"]]
            if "result" in call or call["name"] != message["toolName"] or type(message.get("isError")) is not bool:
                raise ValueError("Unpaired or ambiguous tool result")
            # Exported text may be shortened. The host also checks the exact
            # result reported back to the provider before marking a turn complete.
            call.update(result=message.get("details") or message["content"],
                        raw_result=message["content"], is_error=message["isError"])
    if not messages or messages[-1].get("role") != "assistant" or messages[-1].get("stopReason") != "stop":
        raise ValueError("Session did not end in a completed assistant response")
    if not final.strip() or any("result" not in c for c in calls.values()):
        raise ValueError("Missing final text or tool result")
    return {"assistant_text": final, "tool_calls": list(calls.values()), "session_key": "agent:main:explicit:" + session}


def record_document_locations(trace, plugin_root):
    root = Path(plugin_root).resolve(strict=True)
    for call in trace["tool_calls"]:
        if call["name"] != "read" or call["is_error"]:
            continue
        path = call["arguments"].get("path", call["arguments"].get("file_path"))
        if not isinstance(path, str):
            continue
        if path.startswith("$OPENCLAW_STATE_DIR/"):
            path = str(Path.home() / ".openclaw" / path.removeprefix("$OPENCLAW_STATE_DIR/"))
        # OpenClaw's read normalizes relative segments before following a directory symlink.
        location = Path(os.path.normpath(path))
        if not location.is_absolute():
            continue
        try:
            resolved = location.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_relative_to(root) and resolved.is_file() and resolved.suffix == ".md":
            relative = resolved.relative_to(root)
            if relative.parts[0] == "openclaw-skills":
                original = Path("skills", *relative.parts[1:])
                if resolved.name != "SKILL.md" and (not (root / original).is_file() or
                                                      resolved.read_bytes() != (root / original).read_bytes()):
                    continue
                relative = original
            call["resolved_document"] = str(relative)
            call["document_sha256"] = hashlib.sha256(resolved.read_bytes()).hexdigest()


def guest():
    cfg = receive(sys.stdin)
    state = Path.home() / ".openclaw"
    if state.exists() or os.getuid() != 1000:
        raise RuntimeError("Disposable node home required")
    state.mkdir()
    wheel = Path("/wheels") / cfg["filename"]
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != cfg["wheel_sha256"]:
        raise ValueError("Image wheel hash mismatch")
    with HTTPServer(("127.0.0.1", 0), Loopback) as relay:
        model = cfg["model"]
        workspace = state / "workspace"
        workspace.mkdir()
        config = {"gateway": {"mode": "local"}, "tools": {"profile": "coding", "toolSearch": False},
                  "agents": {"entries": {"main": {"name": "Thomas"}},
                             "defaults": {"workspace": str(workspace), "skipBootstrap": True,
                                          "model": {"primary": "lab/" + model}}},
                  "models": {"providers": {"lab": {"baseUrl": f"http://127.0.0.1:{relay.server_port}/v1",
                             "api": "openai-completions", "apiKey": "relay", "models": [
                                 {"id": model, "name": model, "contextWindow": 128000}]}}}}
        (state / "openclaw.json").write_text(json.dumps(config))
        with wheel.open("rb") as stream:
            subprocess.run([sys.executable, "/opt/always-on/install_package.py", wheel.name],
                           check=True, stdin=stream, stdout=sys.stderr, timeout=180)
        info = json.loads(subprocess.check_output([
            "openclaw", "plugins", "inspect", "portfolio-analyser", "--json"], stdin=subprocess.DEVNULL, timeout=60))
        threading.Thread(target=relay.serve_forever, daemon=True).start()
        session = "eval-" + uuid.uuid4().hex
        turn = subprocess.run(["openclaw", "agent", "--local", "--agent", "main", "--session-id",
                               session, "--message", cfg["prompt"], "--json",
                               "--timeout", str(cfg["timeout"])], timeout=cfg["timeout"] + 30,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
        turn.check_returncode()
        trace = session_trace(workspace, session)
        record_document_locations(trace, info["plugin"]["rootDir"])
        cli_response = json.loads(turn.stdout)
        delivered = cli_response.get("result", cli_response)
        text = "\n".join(p["text"] for p in delivered["payloads"] if p.get("text"))
        if not text.strip():
            raise ValueError("OpenClaw returned no final text to the caller")
        trace["assistant_text"] = text
        trace.update(plugin_root=info["plugin"]["rootDir"], plugin_version=info["plugin"]["version"],
                     workspace_root=str(workspace))
        emit(sys.stdout, {"trace": trace})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def relay_request(proc, payload, model, endpoint, key, smoke, timeout, token_cap, codex_login=False, case_id=None):
    """Send response bytes back unchanged; the guest cannot choose a URL or key."""
    if payload.get("model") != model:
        raise ValueError("OpenClaw requested a different model")
    field = "max_tokens" if "max_tokens" in payload else "max_completion_tokens"
    payload[field] = min(payload.get(field) or token_cap, token_cap)
    payload["n"] = 1
    if smoke or codex_login:
        body = (smoke_body(payload, model, case_id) if smoke else
                codex_completion(payload, model, timeout, token_cap))
        emit(proc.stdin, {"status": 200, "content_type": "text/event-stream"})
        emit(proc.stdin, {"chunk": base64.b64encode(body).decode()})
    else:
        request = Request(endpoint, json.dumps(payload).encode(), {
            "Authorization": "Bearer " + key, "Content-Type": "application/json"})
        opener = build_opener(NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            emit(proc.stdin, {"status": response.status, "content_type": response.headers.get_content_type()})
            size = 0
            while chunk := response.read1(16384):
                size += len(chunk)
                if size > LIMIT:
                    raise ValueError("Provider response too large")
                emit(proc.stdin, {"chunk": base64.b64encode(chunk).decode()})
    emit(proc.stdin, {"chunk": None})


def codex_completion(payload, model, timeout, token_cap):
    # Host-only adapter. Its login is never available to the OpenClaw process.
    from codex_model import completion

    return completion(payload, model=model, timeout=timeout, token_cap=token_cap)


def smoke_body(payload, model, case_id=None):
    completed = len([m for m in payload["messages"] if m["role"] == "tool"])
    if case_id == "earnings_once":
        if completed:
            delta, reason = {"content":"Der Umsatz liegt 4 Prozent über dem Vorabstand. Der EPS-Konsens fehlt. Ohne Bestand weiter beobachten."}, "stop"
        else:
            delta = {"tool_calls":[{"index":0,"id":"earnings_skill","type":"function","function":{
                "name":"skills_read","arguments":json.dumps({"name":"earnings-analysis"})}}]}
            reason="tool_calls"
    elif completed >= 2:
        delta, reason = {"content": "Transport smoke completed."}, "stop"
    else:
        name, args = ("read", {"path": "/opt/always-on/openclaw.json"}) if completed == 0 else (
            "portfolio__portfolio_exposure",
            {"base_currency": "EUR", "total_value": 1000, "cash_value": 200, "positions": [
                {"name": "Smoke ETF", "asset_type": "ETF", "currency": "EUR", "market_value": 800}]})
        delta = {"tool_calls": [{"index": 0, "id": f"smoke_{completed}", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]}
        reason = "tool_calls"
    pieces = [({"role": "assistant"}, None), (delta, None), ({}, reason)]
    def frame(delta, reason):
        event = {"id": "smoke", "object": "chat.completion.chunk", "created": 1, "model": model,
                 "choices": [{"index": 0, "delta": delta, "finish_reason": reason}]}
        return ("data: " + json.dumps(event) + "\n\n").encode()
    return b"".join(frame(*p) for p in pieces) + b"data: [DONE]\n\n"


def wire_history(payload, history, result_content=None):
    """Preserve observations at the model boundary without serializing credentials."""
    offered = [tool["function"]["name"] for tool in payload.get("tools", []) if tool.get("type") == "function"]
    results = []
    calls = []
    for msg in payload["messages"]:
        if msg.get("role") == "tool":
            results.append(msg["tool_call_id"])
            if result_content is not None:
                result_content[msg["tool_call_id"]] = msg["content"]
        for call in msg.get("tool_calls", []):
            calls.append({"id": call["id"], "name": call["function"]["name"],
                          "arguments": json.loads(call["function"]["arguments"])})
    context_sha = hashlib.sha256(json.dumps(payload["messages"], sort_keys=True).encode()).hexdigest()
    if any(request["context_sha256"] == context_sha for request in history):
        raise RuntimeError("Refused a model retry with the same conversation history")
    history.append({"context_sha256": context_sha, "offered_tools": offered, "calls": calls,
                    "result_ids": results})


def verify_wire(trace, history, result_content=None):
    if not history:
        raise ValueError("No model request observed")
    # The provider adapter may strip punctuation from transcript IDs. Pair
    # the ordered calls and require unique provider IDs with a result each.
    executed = trace["tool_calls"]
    observed = {c["id"]: c for h in history for c in h["calls"]}
    results = {cid for h in history for cid in h["result_ids"]}
    if [c["name"] for c in executed] != [c["name"] for c in observed.values()] or results != set(observed):
        raise ValueError("Model history and tool execution trace disagree")
    # Export intentionally redacts home/workspace prefixes. The actual
    # arguments OpenClaw placed on the model boundary retain those paths.
    for call, wire in zip(executed, observed.values()):
        call["wire_id"] = wire["id"]
        call["arguments"] = wire["arguments"]
        if result_content is not None:
            # The support export shortens long strings. Preserve the complete
            # result that the model received, including native skill contents.
            raw = result_content[wire["id"]]
            call["raw_result"] = raw
            blocks = [{"type": "text", "text": raw}] if isinstance(raw, str) else raw
            parsed = parse_result({"toolName": call["name"], "content": blocks})
            if isinstance(parsed, dict) or not isinstance(call["result"], dict):
                call["result"] = parsed


def run_case(image, cfg, endpoint, key, smoke):
    name = "thomas-eval-" + uuid.uuid4().hex
    command = ["docker", "run", "--rm", "-i", "--name", name, "--network", "none", "--read-only",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "1000:1000",
               "--tmpfs", "/home/node:exec,uid=1000,gid=1000,mode=0700",
               "--tmpfs", "/tmp:mode=1777", "--entrypoint", "python3", image, "-u", "-c",
               Path(__file__).read_text(), "__guest"]
    history = []
    result_content = {}
    record = {"id": cfg["id"], "prompt": cfg["prompt"], "model": cfg["model"], "harness": HARNESS,
              "wheel_sha256": cfg["wheel_sha256"], "image_id": image,
              "transport": cfg["transport"], "model_request_limit": cfg["max_requests"],
              "completion_token_limit": None if cfg["codex_login"] else cfg["max_tokens"],
              "complete": False, "status": "infrastructure_error",
              "assistant_text": "", "tool_calls": [], "model_requests": history}
    if cfg["codex_login"]:
        record.update(cli_output_tokens_postcheck=cfg["max_tokens"], reasoning_effort="high")
    with tempfile.TemporaryFile(mode="w+") as err:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True)
        timer = threading.Timer(cfg["timeout"] + 300, proc.kill)
        timer.start()
        try:
            emit(proc.stdin, cfg)
            trace = None
            deadline = None
            for line in proc.stdout:
                event = json.loads(line)
                if "provider_request" in event:
                    payload = event["provider_request"]
                    if len(history) >= cfg["max_requests"]:
                        record.update(status="budget_exhausted", error="Case model request budget exhausted")
                        return record
                    if deadline is None:
                        deadline = time.monotonic() + cfg["timeout"]
                    remaining = int(deadline - time.monotonic())
                    if remaining < 1:
                        record.update(status="budget_exhausted", error="Model decision time budget exhausted")
                        return record
                    wire_history(payload, history, result_content)
                    try:
                        relay_request(proc, payload, cfg["model"], endpoint, key, smoke,
                                      remaining, cfg["max_tokens"], cfg["codex_login"], cfg["id"])
                    except (HTTPError, URLError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                        record.update(status="provider_error", error=str(exc))
                        return record
                else:
                    if trace is not None or set(event) != {"trace"}:
                        raise ValueError("Invalid guest event")
                    trace = event["trace"]
            if proc.wait() or trace is None:
                err.seek(0)
                raise RuntimeError("Guest failed: " + err.read()[-3000:])
            record.update(trace)
            verify_wire(trace, history, result_content)
            if smoke and cfg["id"]=="earnings_once":
                calls=trace["tool_calls"]
                if [c["name"] for c in calls] != ["skills_read"] or calls[0]["is_error"] or "earnings-analysis" not in str(calls[0]["result"]):
                    raise ValueError("Earnings specialist was not read in the isolated turn")
            elif smoke:
                calls = trace["tool_calls"]
                if [c["name"] for c in calls] != ["read", "portfolio__portfolio_exposure"] or any(c["is_error"] for c in calls):
                    raise ValueError("Smoke read/calculation did not execute successfully")
                if calls[1]["result"]["structuredContent"]["exposures"][0]["portfolio_weight"] != "0.8":
                    raise ValueError("Smoke calculation did not return the expected 80%")
            required = {"portfolio__portfolio_exposure", "portfolio__build_portfolio_snapshot", "read"}
            if not required.issubset(history[0]["offered_tools"]):
                record.update(status="capability_error", error="Missing required native tools in initial model request")
                return record
            record.update(status="transport_smoke" if smoke else "ok", complete=True)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            record["error"] = str(exc)
        finally:
            timer.cancel()
            proc.stdin.close()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
    return record


@contextmanager
def eval_image(wheel, existing):
    if existing:
        yield subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", existing], text=True).strip()
        return
    prefix = "thomas-eval-" + uuid.uuid4().hex
    runtime, image = prefix + "-runtime", prefix + "-wheel"
    try:
        subprocess.run(["docker", "build", "-t", runtime, os.environ["THOMAS_RUNTIME"]], check=True)
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            shutil.copy2(wheel, stage / wheel.name)
            dockerfile = (ROOT / "tests/Dockerfile").read_text()
            (stage / "Dockerfile").write_text(dockerfile.replace("thomas-portability-runtime:local", runtime))
            subprocess.run(["docker", "build", "-t", image, tmp], check=True)
        yield subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True).strip()
    finally:
        subprocess.run(["docker", "image", "rm", image, runtime], capture_output=True)


def earnings_web_eval(args):
    allowed_roots = ("portfolio_advisory/skills/earnings-", "portfolio_advisory/references/research/",
                     "portfolio_advisory/scripts/earnings_research.mjs")
    with tempfile.TemporaryDirectory(prefix="thomas-earnings-eval-") as stage:
        with zipfile.ZipFile(args.wheel) as wheel:
            for name in wheel.namelist():
                if name.startswith(allowed_roots) and ".." not in Path(name).parts:
                    wheel.extract(name, stage)
        environment = dict(os.environ, EARNINGS_EVAL_MODEL=args.model,
                           EARNINGS_EVAL_MAX_REQUESTS=str(args.max_requests),
                           EARNINGS_EVAL_TIMEOUT=str(args.timeout), EARNINGS_EVAL_MAX_TOKENS=str(args.max_tokens),
                           EARNINGS_EVAL_WHEEL_SHA256=hashlib.sha256(args.wheel.read_bytes()).hexdigest())
        return subprocess.run(["node", str(ROOT/"evals/earnings_web.mjs"), str(Path(stage)/"portfolio_advisory"),
                               str(args.out), *(args.case or [])], env=environment).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-live", action="store_true")
    mode.add_argument("--transport-smoke", action="store_true")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--earnings-web", action="store_true", help="Exercise the installed earnings skills against dated search/open fixtures")
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--case", action="append", help="Case to run (repeatable)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    backend = parser.add_mutually_exclusive_group()
    backend.add_argument("--base-url", help="HTTPS OpenAI-compatible API base ending in /v1")
    backend.add_argument("--codex-login", action="store_true",
                         help="Use host Codex login for structured decisions, one ephemeral CLI per request")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--image", help="Reuse a prepared test image containing the exact wheel in /wheels")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-requests", type=int, default=8, help="Max model requests per case")
    parser.add_argument("--max-tokens", type=int, default=1200,
                        help="Completion limit per API request. With --codex-login, check usage after each turn")
    args = parser.parse_args()
    key = endpoint = None
    transport = "local-scripted-smoke"
    if args.codex_login:
        if not args.run_live:
            parser.error("--codex-login requires --run-live")
        from codex_model import TRANSPORT
        transport = TRANSPORT
    elif args.run_live:
        url = urlsplit(args.base_url or "")
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            parser.error("--run-live requires an HTTPS --base-url without credentials/query/fragment")
        endpoint = args.base_url.rstrip("/") + "/chat/completions"
        key = os.getenv(args.api_key_env)
        if not key:
            parser.error("Set the provider API key in " + args.api_key_env)
        transport = "openai-chat-completions"
    if min(args.timeout, args.max_requests, args.max_tokens) < 1:
        parser.error("Timeout and budgets must be positive")
    if args.earnings_web:
        if not args.run_live or not args.codex_login:
            parser.error("--earnings-web uses --run-live --codex-login")
        return earnings_web_eval(args)
    cases = json.loads(args.cases.read_text())
    cases = cases["cases"] if isinstance(cases, dict) else cases
    ids = [c["id"] for c in cases]
    if (not cases or len(ids) != len(set(ids)) or
        any(not re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids) or
        any(not isinstance(c["prompt"], str) or not c["prompt"].strip() for c in cases)):
        parser.error("Expected uniquely named cases with nonempty prompts")
    if args.case:
        if set(args.case) - set(ids):
            parser.error(f"Unknown case; choose from {ids}")
        cases = [c for c in cases if c["id"] in args.case]
        ids = [c["id"] for c in cases]
    sha = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    args.out.mkdir(parents=True, exist_ok=True)
    if any((args.out / (i + ".json")).exists() for i in ids):
        parser.error("Output already contains traces for these cases")
    failed = False
    with eval_image(args.wheel, args.image) as image:
        for case in cases:
            cfg = {"id": case["id"], "prompt": case["prompt"], "filename": args.wheel.name,
                   "wheel_sha256": sha, "timeout": args.timeout, "model": args.model,
                   "max_requests": args.max_requests, "max_tokens": args.max_tokens,
                   "transport": transport, "codex_login": args.codex_login}
            record = run_case(image, cfg, endpoint, key, args.transport_smoke)
            with (args.out / (case["id"] + ".json")).open("x") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
            print(case["id"], record["status"], flush=True)
            failed |= not record["complete"]
    return int(failed)


if __name__ == "__main__":
    if sys.argv[1:] == ["__guest"]:
        guest()
    else:
        raise SystemExit(main())
