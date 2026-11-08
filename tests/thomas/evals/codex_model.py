"""Adapt one actual OpenClaw model request to one isolated, authenticated Codex CLI turn on macOS."""

import json
import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


TRANSPORT = 'codex-exec-chatgpt-structured-v1'
INSTRUCTIONS = (
    'Act as the assistant for the supplied OpenClaw chat-completions request. '
    'Use its messages in role order, including tool results, and its actual offered tool schemas. '
    'Choose the next assistant response freely. Put its text in content and any function calls in '
    'tool_calls, each with a function name and JSON-encoded arguments object. '
    'The caller executes these calls and returns their results on subsequent requests. '
    'Use no host tools. Return only the requested JSON response.'
)
# The host CLI otherwise attaches the user's global AGENTS.md even in an empty workspace.
# Auth is handled solely by Codex. This additional host rule applies to the CLI process itself.
HOST_RULE = ('(version 1)(allow default)(deny file-read* (regex #"/AGENTS([.]override)?[.]md$") '
             '(regex #"/([.]agents|[.]codex/(skills|plugins|memories|sessions|archived_sessions))(/|$)"))')
DISABLED = ('apps', 'plugins', 'remote_plugin', 'plugin_discovery_prefetch', 'skill_search',
            'skill_mcp_dependency_install', 'hooks', 'multi_agent', 'shell_tool', 'unified_exec',
            'shell_snapshot', 'browser_use', 'browser_use_external', 'computer_use', 'in_app_browser',
            'view_image', 'image_generation', 'artifact', 'sleep_tool', 'tool_suggest', 'goals',
            'workspace_dependencies', 'code_mode', 'code_mode_host', 'unbounded_connection_retries')


def response_schema(names):
    name_schema = {'type': 'string', 'enum': names} if names else {'type': 'string'}
    action = {'type': 'object', 'additionalProperties': False, 'required': ['name', 'arguments'],
              'properties': {'name': name_schema, 'arguments': {'type': 'string'}}}
    return {'type': 'object', 'additionalProperties': False, 'required': ['content', 'tool_calls'],
            'properties': {'content': {'type': 'string'}, 'tool_calls': {'type': 'array', 'items': action}}}


def command(codex, workspace, schema, instructions, model):
    args = ['/usr/bin/sandbox-exec', '-p', HOST_RULE, codex, '--no-daemon', 'exec',
            '--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check', '--json',
            '--model', model, '--cd', str(workspace), '--output-schema', str(schema),
            '--enable', 'skip_host_skill_discovery']
    for flag in DISABLED:
        args.extend(['--disable', flag])
    settings = ['default_permissions="thomas_eval"',
                'permissions.thomas_eval.filesystem={":minimal"="read",":workspace_roots"={"."="read"}}',
                'permissions.thomas_eval.network.enabled=false', 'approval_policy="never"',
                'shell_environment_policy.inherit="none"', 'mcp_servers={}', 'web_search="disabled"',
                'skills.include_instructions=false', 'project_doc_max_bytes=0', 'include_environment_context=false',
                'model_reasoning_effort="high"', 'model_instructions_file=' + json.dumps(str(instructions))]
    for setting in settings:
        args.extend(['-c', setting])
    return [*args, '-']


def startup_notices():
    codex_home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    return {
        'Under-development features enabled: skip_host_skill_discovery. Under-development features are '
        'incomplete and may behave unpredictably. To suppress this warning, set '
        f'`suppress_unstable_features_warning = true` in {codex_home}/config.toml.',
        f'Failed to read global AGENTS.md instructions from `{codex_home}/AGENTS.md`: Operation not permitted (os error 1)',
        'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; '
        'enable `features.code_mode_host` and install `codex-code-mode-host`.',
    }


def model_output(lines, token_cap):
    messages = []
    started = False
    completed = False
    for line in lines.splitlines():
        event = json.loads(line)
        kind = event['type']
        if completed:
            raise ValueError('Codex emitted events after the completed turn')
        if kind == 'thread.started':
            continue
        if kind == 'turn.started' and not started:
            started = True
            continue
        if kind == 'turn.completed':
            tokens = event.get('usage', {}).get('output_tokens')
            if type(tokens) is not int or not 0 <= tokens <= token_cap:
                raise ValueError('Codex output token usage missing or exceeds the requested budget')
            completed = True
            continue
        if kind in ('error', 'turn.failed'):
            raise ValueError('Codex turn failed: ' + diagnostic(event.get('message') or event.get('error')))
        if kind not in ('item.started', 'item.completed'):
            raise ValueError(f'Unexpected Codex turn event: {kind}')
        item = event['item']
        if item.get('type') == 'error':
            message = item.get('message')
            if kind == 'item.completed' and not started and message in startup_notices():
                continue
            raise ValueError('Codex error item: ' + diagnostic(message))
        if item.get('type') not in ('agent_message', 'reasoning'):
            raise ValueError(f'Unexpected outer Codex tool or item: {item.get("type")}')
        if kind == 'item.completed' and item['type'] == 'agent_message':
            messages.append(item['text'])
    if not started or not completed or len(messages) != 1:
        raise ValueError('Codex did not return exactly one completed response')
    return json.loads(messages[0])


def stream(answer, names, model):
    if not isinstance(answer, dict) or set(answer) != {'content', 'tool_calls'}:
        raise ValueError('Invalid Codex completion envelope')
    content, actions = answer['content'], answer['tool_calls']
    if not isinstance(content, str) or not isinstance(actions, list) or not (content.strip() or actions):
        raise ValueError('Codex returned neither assistant content nor tool calls')
    calls = []
    for index, action in enumerate(actions):
        if (not isinstance(action, dict) or set(action) != {'name', 'arguments'} or action['name'] not in names
                or not isinstance(action['arguments'], str) or not isinstance(json.loads(action['arguments']), dict)):
            raise ValueError('Codex returned an invalid offered tool call')
        calls.append({'index': index, 'id': 'call_' + uuid.uuid4().hex, 'type': 'function', 'function': action})
    delta = {'role': 'assistant'}
    if content:
        delta['content'] = content
    if calls:
        delta['tool_calls'] = calls
    base = {'id': 'chatcmpl-' + uuid.uuid4().hex, 'object': 'chat.completion.chunk',
            'created': int(time.time()), 'model': model}
    frames = []
    for payload, reason in [(delta, None), ({}, 'tool_calls' if calls else 'stop')]:
        frame = {**base, 'choices': [{'index': 0, 'delta': payload, 'finish_reason': reason}]}
        frames.append(('data: ' + json.dumps(frame) + '\n\n').encode())
    return b''.join([*frames, b'data: [DONE]\n\n'])


def failure_kind(proc):
    return failure_category(proc.stdout + proc.stderr)


def failure_category(text):
    message = text.casefold()
    categories = {
        'authentication or account access': ('not logged in', 'unauthorized', '401', 'authentication', 'please sign in'),
        'rate or usage limit': ('rate limit', 'usage limit', '429', 'quota exceeded'),
        'incompatible configuration or CLI option': ('unexpected argument', 'unknown field', 'unknown feature', 'error loading config', 'invalid value'),
        'sandbox or filesystem denial': ('operation not permitted', 'permission denied', 'sandbox_apply'),
        'provider connection': ('websocket', 'failed to connect', 'connection refused', 'network error'),
        'model or schema rejected': ('unsupported model', 'model was not found', 'invalid schema', 'response_format'),
    }
    return next((label for label, needles in categories.items() if any(s in message for s in needles)), 'CLI or provider failure')


def diagnostic(message):
    # Never forward provider text, local paths, credentials or prompt echoes into trace files.
    text = str(message or '')
    fingerprint = hashlib.sha256(text.encode()).hexdigest()[:12]
    return f'{failure_category(text)} (diagnostic {fingerprint})'


def completion(payload, *, model, timeout, token_cap):
    """Use native login without opening any credential file; emit guest-consumable SSE."""
    codex = shutil.which('codex')
    if platform.system() != 'Darwin' or not codex or not Path('/usr/bin/sandbox-exec').is_file():
        raise ValueError('This login transport requires macOS Seatbelt and the authenticated Codex CLI')
    if payload.get('model') != model or timeout <= 0 or token_cap <= 0 or not payload.get('messages'):
        raise ValueError('Invalid model request or budget')
    names = [tool['function']['name'] for tool in payload.get('tools', []) if tool.get('type') == 'function']
    if len(names) != len(payload.get('tools', [])) or len(set(names)) != len(names):
        raise ValueError('Unsupported or duplicate provider tool definitions')
    with tempfile.TemporaryDirectory(prefix='thomas-codex-') as directory:
        root = Path(directory)
        workspace = root / 'workspace'
        workspace.mkdir()
        schema = root / 'response.json'
        schema.write_text(json.dumps(response_schema(names)))
        instructions = root / 'instructions.txt'
        instructions.write_text(INSTRUCTIONS)
        # Carry login's normal home/keychain, not other providers' keys or production agent state.
        env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'CODEX_HOME')
               if key in os.environ}
        try:
            proc = subprocess.run(command(codex, workspace, schema, instructions, model), cwd=workspace,
                                  env=env, input=json.dumps(payload, ensure_ascii=False), text=True,
                                  capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Codex exceeded the model request deadline') from exc
        if proc.returncode:
            raise ValueError(f'Codex exec failed (exit {proc.returncode}, {failure_kind(proc)})')
        return stream(model_output(proc.stdout, token_cap), names, model)
