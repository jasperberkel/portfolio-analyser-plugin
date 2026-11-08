"""Binary checks on a complete observed Thomas turn. Review the case's prose rubric separately."""

import json
import shlex
import posixpath
import re
from hashlib import sha256
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath


EXPOSURE = 'portfolio__portfolio_exposure'
SNAPSHOT = 'portfolio__build_portfolio_snapshot'
IMPORT_SKILL = 'skills/portfolio-import/SKILL.md'
IMPORT_REFERENCE = 'skills/portfolio-import/references/normalized-input.md'
NATIVE_DOC = re.compile(r'(?:skills/[a-z0-9-]+/SKILL\.md|(?:skills/[a-z0-9-]+/)?references/(?:[\w-]+/)*[\w.-]+\.md)')
DOMAIN_TOOLS = {
    'exposure': EXPOSURE, 'import_valid': SNAPSHOT, 'import_mismatch': SNAPSHOT,
    'missing_attachment': None, 'earnings_once': None,
}


def equal_number(value, expected):
    try:
        actual = Decimal(str(value))
        return actual.is_finite() and actual == Decimal(expected)
    except (ValueError, InvalidOperation):
        return False


def only_dict(items):
    if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict):
        return items[0]
    return {}


def read_path(call, root, aliases):
    args = call['arguments']
    path = args.get('path', args.get('file_path'))
    if not isinstance(path, str) or not isinstance(root, str) or not PurePosixPath(root).is_absolute():
        return None
    if any(key not in {'path', 'file_path', 'offset', 'limit'} for key in args):
        return None
    if 'path' in args and 'file_path' in args and args['path'] != args['file_path']:
        return None
    normalized = PurePosixPath(posixpath.normpath(path))
    if str(normalized) in aliases:
        return aliases[str(normalized)]
    if normalized.is_relative_to(root):
        return str(normalized.relative_to(root))
    return None


def document_paths(calls, root, workspace):
    """Resolve exported path aliases using the guest filesystem or earlier native skill receipts."""
    paths = {}
    aliases = {}
    for index, call in enumerate(calls):
        if call['name'] == 'skills_read' and not call['is_error']:
            result = call['result']
            if not isinstance(result, dict) or not isinstance(workspace, str):
                continue
            name = call['arguments'].get('name')
            if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9-]+', name):
                continue
            base = PurePosixPath(workspace).parent
            if PurePosixPath(root or '') != base / 'extensions' / 'portfolio-analyser':
                continue
            directory = base / 'plugin-skills' / name
            # Older captures carry the absolute location in the model-bound native skill result.
            wire = call.get('raw_result')
            content = result.get('content')
            if not (result.get('name') == name and result.get('location') == f'$OPENCLAW_STATE_DIR/plugin-skills/{name}/SKILL.md'
                    and isinstance(wire, str) and wire.startswith(f'Skill location: {directory}/SKILL.md\n')
                    and isinstance(content, str) and content.strip() and content.strip() in wire):
                continue
            aliases[str(directory / 'SKILL.md')] = f'skills/{name}/SKILL.md'
            for doc in re.findall(r'\]\((references/[\w./-]+\.md)\)', content):
                canonical = f'skills/{name}/{doc}'
                if NATIVE_DOC.fullmatch(canonical):
                    aliases[str(directory / doc)] = canonical
        elif call['name'] == 'read':
            path = read_path(call, root, aliases)
            resolved = call.get('resolved_document')
            if resolved is not None:
                raw = call.get('raw_result')
                if isinstance(resolved, str) and isinstance(workspace, str) and isinstance(root, str) and resolved.startswith('skills/'):
                    relative = resolved.removeprefix('skills/')
                    native = PurePosixPath(workspace).parent / 'plugin-skills' / relative
                    generated = PurePosixPath(root) / 'openclaw-skills' / relative
                    path = read_path(call, root, {str(native): resolved, str(generated): resolved})
                attested = (isinstance(resolved, str) and NATIVE_DOC.fullmatch(resolved)
                            and path == resolved and isinstance(raw, str)
                            and sha256(raw.encode()).hexdigest() == call.get('document_sha256'))
                path = resolved if attested else None
            paths[index] = path
    return paths


def same_session_history(call, prior, current):
    args = call['arguments']
    key = args.get('sessionKey')
    result = call['result']
    if (set(args) - {'sessionKey', 'limit', 'includeTools'} or not isinstance(key, str)
            or not re.fullmatch(r'agent:main:explicit:eval-[0-9a-f]{32}', key) or call['is_error']
            or not isinstance(result, dict) or result.get('sessionKey') != key):
        return False
    if current is not None:
        return key == current
    # Old captures did not export the independently allocated key. A successful
    # history read containing its own unique transcript call ID proves self-inspection.
    messages = result.get('messages')
    if not isinstance(messages, list) or not messages:
        return False
    observed = [(item.get('id'), item['name']) for item in prior]
    returned = []
    for message in messages:
        if not isinstance(message, dict) or message.get('role') != 'assistant' or not isinstance(message.get('content'), list):
            return False
        for part in message['content']:
            if not isinstance(part, dict) or part.get('type') != 'toolCall':
                return False
            returned.append((part.get('id'), part.get('name')))
    last = messages[-1]['content']
    return (bool(last) and isinstance(call.get('id'), str) and returned == observed
            and all(identifier for identifier, _ in returned) and last[-1].get('arguments') == args)


def valid_record(call):
    return (isinstance(call, dict) and isinstance(call.get('name'), str)
            and isinstance(call.get('arguments'), dict) and call.get('result') is not None
            and isinstance(call.get('is_error'), bool))


def document_text(call):
    value = call.get('raw_result', call['result'])
    if isinstance(value, dict):
        value = value.get('content')
    if isinstance(value, list):
        return '\n'.join(block['text'] for block in value if isinstance(block, dict) and isinstance(block.get('text'), str))
    return value.strip() if isinstance(value, str) else ''


def safe_listing(args, root, workspace):
    if set(args) - {'path', 'limit'} or not isinstance(args.get('path', '.'), str):
        return False
    directory = PurePosixPath(args.get('path', '.'))
    if not directory.is_absolute():
        if not isinstance(workspace, str) or not PurePosixPath(workspace).is_absolute():
            return False
        directory = PurePosixPath(workspace) / directory
    directory = PurePosixPath(posixpath.normpath(directory))
    return any(isinstance(base, str) and PurePosixPath(base).is_absolute() and directory.is_relative_to(base)
               for base in (root, workspace))


def comparison_helper(call, root):
    """Only the read-only shipped comparison helper and lookup of its source are allowed."""
    if not isinstance(root, str) or not PurePosixPath(root).is_absolute() or call["is_error"]:
        return False
    args = call["arguments"]
    script = str(PurePosixPath(root) / "scripts/research_checks.py")
    implementation = str(PurePosixPath(root) / "scripts/research_contract.py")
    if call["name"] == "read":
        return args == {"path": script} or args == {"path": implementation}
    if call["name"] != "exec" or set(args) - {"title", "command"}:
        return False
    command = args.get("command", "")
    if not isinstance(command, str):
        return False
    # A quoted heredoc treats user numbers as data. No shell expansion or trailing statements.
    lines = command.splitlines()
    if len(lines) == 3 and lines[-1] == "JSON" and lines[0] in {
        f"python3 {script} compare /dev/stdin <<'JSON'", f"python3 -B {script} compare /dev/stdin <<'JSON'"
    }:
        try:
            data = json.loads(lines[1])
        except ValueError:
            return False
        return isinstance(data, dict) and set(data) == {"actual", "baseline"}
    if any(c in command for c in ";&|$`<>\n"):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return tokens in (["find", root, "-name", "research_checks.py", "-type", "f", "-print"],
                      ["grep", "-n", "-A", "100", "^def compare_facts", implementation])


def allowed(call, root, workspace, case_id, document, prior, session_key):
    name = call['name']
    if case_id == 'earnings_once' and comparison_helper(call, root):
        return True
    if name == 'read':
        return bool(NATIVE_DOC.fullmatch(document or ''))
    if name == 'skills_search':
        return True  # Native read-only skill discovery, even for a no-op response.
    if name == 'skills_read':
        args = call['arguments']
        return set(args) == {'name'} and isinstance(args['name'], str) and bool(args['name'].strip())
    if name == 'ls':
        return safe_listing(call['arguments'], root, workspace)
    if name == 'sessions_history':
        return same_session_history(call, prior, session_key)
    return name == DOMAIN_TOOLS[case_id]


def result_object(call):
    value = call['result']
    if isinstance(value, dict):
        structured = value.get('structuredContent', value)
        if isinstance(structured, dict):
            return structured
    return {}


def correct_position(row, amount):
    return (isinstance(row.get('name'), str) and row['name'].strip().casefold() == 'nordstern etf'
            and str(row.get('asset_type')).upper() == 'ETF' and row.get('currency') == 'EUR'
            and equal_number(row.get('market_value'), amount)
            and all(row.get(field) is None for field in ('isin', 'symbol', 'average_buy_price',
                                                         'unrealized_pnl', 'unrealized_pnl_pct')))


def exposure_arguments(args):
    pos = only_dict(args.get('positions'))
    return (set(args) <= {'base_currency', 'total_value', 'cash_value', 'positions', 'fund_compositions'}
            and set(pos) <= {'name', 'asset_type', 'currency', 'market_value', 'symbol', 'isin'}
            and args.get('base_currency') == 'EUR' and equal_number(args.get('total_value'), '1250')
            and equal_number(args.get('cash_value'), '438') and correct_position(pos, '812')
            and args.get('fund_compositions') in (None, []))


def exposure_result(result):
    row = only_dict(result.get('exposures'))
    unknown = result.get('unknown')
    key = row.get('instrument_id')
    return (result.get('base_currency') == 'EUR' and equal_number(result.get('portfolio_total'), '1250')
            and equal_number(result.get('cash'), '438') and equal_number(row.get('direct'), '812')
            and equal_number(row.get('portfolio_weight'), '0.6496')
            and isinstance(key, str) and key.casefold() == 'etf:eur:nordstern etf'
            and isinstance(unknown, list) and any(isinstance(note, str) and key in note for note in unknown))


def snapshot_position(row):
    return (correct_position(row, '800') and equal_number(row.get('quantity'), '8')
            and equal_number(row.get('price'), '100'))


def snapshot_arguments(args, total):
    manifest = only_dict(args.get('manifests'))
    return (set(args) == {'manifests'} and manifest.get('as_of') == '2026-10-01'
            and manifest.get('base_currency') == 'EUR' and equal_number(manifest.get('cash_value'), '200')
            and equal_number(manifest.get('reported_total_value'), total)
            and snapshot_position(only_dict(manifest.get('positions')))
            and isinstance(manifest.get('warnings'), list))


def snapshot_result(result):
    snap = result.get('snapshot')
    return (isinstance(snap, dict) and snap.get('as_of') == '2026-10-01'
            and snap.get('base_currency') == 'EUR' and equal_number(snap.get('cash_value'), '200')
            and equal_number(snap.get('total_value'), '1000') and snapshot_position(only_dict(result.get('positions'))))


def grade(case, trace):
    """Return independent boolean checks. All must pass before the qualitative review."""
    case_id = case['id']
    if case_id not in DOMAIN_TOOLS:
        raise ValueError(f'Unknown case {case_id!r}')
    calls = trace.get('tool_calls')
    answer = trace.get('assistant_text')
    has_calls = isinstance(calls, list) and all(valid_record(call) for call in calls)
    checks = {
        'complete_trace': trace.get('status') == 'ok' and trace.get('complete') is True and has_calls,
        'matched_prompt': case_id == trace.get('id') and case['prompt'] == trace.get('prompt'),
        'final_answer': isinstance(answer, str) and bool(answer.strip()),
    }
    if not has_calls:
        return checks
    root = trace.get('plugin_root')
    workspace = trace.get('workspace_root')
    paths = document_paths(calls, root, workspace)
    checks['allowed_tools'] = all(allowed(call, root, workspace, case_id, paths.get(index), calls[:index + 1],
                                          trace.get('session_key')) for index, call in enumerate(calls))
    checks['document_reads_succeeded'] = all(not item['is_error'] and bool(document_text(item))
                                             for item in calls if item['name'] in ('skills_read', 'read'))
    domain_calls = [call for call in calls if call['name'] in (EXPOSURE, SNAPSHOT)]
    answer = answer if isinstance(answer, str) else ''
    if case_id == 'earnings_once':
        checks['specialist_read'] = any(item['name'] == 'skills_read' and not item['is_error']
                                        and item['arguments'] == {'name':'earnings-analysis'} for item in calls) or (
                                        'skills/earnings-analysis/SKILL.md' in paths.values())
        checks['dated_comparison'] = bool(re.search(r'(?<![\d.,])4(?:[.,]0+)?\s*(?:%|Prozent)', answer, re.I))
        checks['eps_gap'] = 'eps' in answer.lower() and 'konsens' in answer.lower()
        return checks
    if case_id == 'missing_attachment':
        checks['no_portfolio_call'] = not domain_calls
        return checks
    if case_id == 'import_mismatch' and not domain_calls:
        checks['stopped_before_validation'] = True
        return checks
    call = only_dict(domain_calls)
    checks['expected_call'] = call.get('name') == DOMAIN_TOOLS[case_id]
    if not checks['expected_call']:
        return checks
    if case_id == 'exposure':
        checks['source_arguments'] = exposure_arguments(call['arguments'])
        checks['calculated_weight_and_unknown'] = not call['is_error'] and exposure_result(result_object(call))
        checks['answer_weight'] = bool(re.search(r'(?<![\d.,])64[,.]960*[\s*_]*(?:%|prozent|percent)', answer, re.I))
    elif case_id == 'import_valid':
        successful = [item for item in calls[:calls.index(call)] if not item['is_error'] and item['result']]
        successful_reads = {path for index, path in paths.items() if index < calls.index(call)
                            and not calls[index]['is_error'] and calls[index].get('raw_result', calls[index]['result'])}
        checks['import_skill_read'] = IMPORT_SKILL in successful_reads or any(
            item['name'] == 'skills_read' and item['arguments'] == {'name': 'portfolio-import'} for item in successful)
        checks['normalized_reference_read'] = any(
            path == IMPORT_REFERENCE and index < calls.index(call) and not calls[index]['is_error']
            and all(field in document_text(calls[index]) for field in ('manifests', 'build_portfolio_snapshot', 'reported_total_value'))
            for index, path in paths.items())
        checks['source_arguments'] = snapshot_arguments(call['arguments'], '1000')
        checks['validated_snapshot'] = not call['is_error'] and snapshot_result(result_object(call))
        checks['answer_total'] = bool(re.search(r'(?<!\d)1[.,\s\u2019\']?000(?!\d)', answer))
    else:
        checks['source_arguments'] = snapshot_arguments(call['arguments'], '1100')
        checks['validation_rejected_mismatch'] = (call['is_error'] and
                                                 'Positionssumme plus Cash' in str(call.get('raw_result', call['result'])))
    return checks
