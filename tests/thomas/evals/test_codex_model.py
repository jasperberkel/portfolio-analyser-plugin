import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_model import command, completion, failure_kind, model_output, startup_notices, stream


def events(answer, tokens=15):
    return '\n'.join(json.dumps(e) for e in [
        {'type': 'thread.started'}, {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(answer)}},
        {'type': 'turn.completed', 'usage': {'output_tokens': tokens}}])


class CodexModelTest(unittest.TestCase):
    def test_only_exact_pre_turn_isolation_warnings_are_tolerated(self):
        answer = {'content': 'Fertig', 'tool_calls': []}
        lines = events(answer).splitlines()
        notices = [json.dumps({'type': 'item.completed', 'item': {'type': 'error', 'message': msg}})
                   for msg in startup_notices()]
        self.assertEqual(model_output('\n'.join([lines[0], *notices, *lines[1:]]), 50), answer)
        for diagnostic in (notices[0], json.dumps({'type': 'item.completed', 'item': {
                'type': 'error', 'message': 'Unauthorized Bearer fake-sensitive-secret'}})):
            with self.assertRaisesRegex(ValueError, 'Codex error item') as caught:
                model_output('\n'.join([*lines[:2], diagnostic, *lines[2:]]), 50)
            self.assertNotIn('fake-sensitive-secret', str(caught.exception))
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            model_output('\n'.join(notices), 50)

    def test_neutral_multiple_tool_calls_use_unique_ids(self):
        action = {'name': 'inspect', 'arguments': '{"page":7}'}
        out = stream(model_output(events({'content': '', 'tool_calls': [action, action]}), 50), ['inspect'], 'test')
        frame = json.loads(out.splitlines()[0][6:]); actions = frame['choices'][0]['delta']['tool_calls']
        self.assertEqual([a['function'] for a in actions], [action, action])
        self.assertEqual(len({a['id'] for a in actions}), 2)
        self.assertIn(b'"finish_reason": "tool_calls"', out)

    def test_unexpected_outer_actions_truncation_and_foreign_tools_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outer Codex'):
            model_output('{"type":"item.completed","item":{"type":"command_execution"}}', 50)
        with self.assertRaisesRegex(ValueError, 'budget'):
            model_output(events({'content': 'Fertig', 'tool_calls': []}, 51), 50)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            model_output('{"type":"turn.started"}', 50)
        with self.assertRaisesRegex(ValueError, 'invalid offered tool'):
            stream({'content': '', 'tool_calls': [{'name':'elsewhere', 'arguments': '{}'}]}, ['inspect'], 'test')

    def test_standalone_invocation_uses_only_guest_request(self):
        payload = {'model': 'example', 'messages': [{'role': 'user', 'content': 'Beispiel'}], 'tools': []}
        def check(args, **kwargs):
            self.assertEqual(json.loads(kwargs['input']), payload)
            self.assertEqual(list(Path(kwargs['cwd']).iterdir()), [])
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertIn('--ephemeral', args)
            self.assertIn('--ignore-user-config', args)
            self.assertNotIn('example', Path(args[args.index('--output-schema') + 1]).read_text())
            return subprocess.CompletedProcess(args, 0, stdout=events({'content': 'Antwort', 'tool_calls': []}))
        with patch('codex_model.platform.system', return_value='Darwin'), patch('codex_model.shutil.which', return_value='/bin/codex'), \
             patch('codex_model.Path.is_file', return_value=True), patch('codex_model.subprocess.run', side_effect=check) as run:
            body = completion(payload, model='example', timeout=30, token_cap=50)
        run.assert_called_once()
        self.assertIn(b'"content": "Antwort"', body)
        self.assertIn(b'"finish_reason": "stop"', body)

    def test_tool_restrictions_and_ephemeral_state(self):
        argv = command('codex', Path('/fixture'), Path('/schema'), Path('/instructions'), 'sample')
        self.assertEqual(argv[:2], ['/usr/bin/sandbox-exec', '-p'])
        for feature in ('plugins', 'apps', 'shell_tool', 'skill_search', 'multi_agent'):
            self.assertIn(('--disable', feature), zip(argv, argv[1:]))
        self.assertIn('permissions.thomas_eval.network.enabled=false', argv)
        self.assertIn('model_reasoning_effort="high"', argv)
        self.assertIn('web_search="disabled"', argv)

    def test_failure_classification_does_not_return_diagnostic_contents(self):
        for detail, expected in [('401 Unauthorized secret-value', 'authentication or account access'),
                                 ('unknown feature abc', 'incompatible configuration or CLI option')]:
            proc = subprocess.CompletedProcess([], 1, stdout='', stderr=detail)
            self.assertEqual(failure_kind(proc), expected)


if __name__ == '__main__':
    unittest.main()
