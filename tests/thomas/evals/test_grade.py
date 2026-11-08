import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from grade import EXPOSURE, IMPORT_REFERENCE, IMPORT_SKILL, SNAPSHOT, grade
from live import record_document_locations


CASES = {case['id']: case for case in json.loads(Path(__file__).with_name('cases.json').read_text())}
ROOT = '/container/plugins/portfolio-analyser'


def call(name, arguments, result, is_error=False):
    return {'name': name, 'arguments': arguments, 'result': result, 'is_error': is_error}


def trace(case_id, answer, *calls):
    return {'id': case_id, 'prompt': CASES[case_id]['prompt'], 'plugin_root': ROOT, 'status': 'ok',
            'complete': True, 'assistant_text': answer, 'tool_calls': list(calls)}


def snapshot_call(total='1000'):
    position = {'name': 'Nordstern ETF', 'asset_type': 'ETF', 'currency': 'EUR',
                'quantity': '8.0', 'price': '100', 'market_value': '800'}
    manifest = {'as_of': '2026-10-01', 'base_currency': 'EUR', 'cash_value': '200',
                'reported_total_value': total, 'positions': [position], 'warnings': []}
    snapshot = {'as_of': '2026-10-01', 'base_currency': 'EUR', 'total_value': '1000', 'cash_value': '200'}
    return call(SNAPSHOT, {'manifests': [manifest]}, {'snapshot': snapshot, 'positions': [position.copy()]})


def exposure_trace():
    key = 'ETF:EUR:Nordstern ETF'
    args = {'base_currency': 'EUR', 'total_value': 1250, 'cash_value': 438,
            'positions': [{'asset_type': 'ETF', 'currency': 'EUR', 'name': 'Nordstern ETF', 'market_value': 812}]}
    result = {'portfolio_total': '1250', 'base_currency': 'EUR', 'cash': '438',
              'exposures': [{'instrument_id': key, 'direct': '812', 'portfolio_weight': '0.649600'}],
              'unknown': [f'{key}: Zusammensetzung unvollständig']}
    return trace('exposure', '64,96 Prozent; die Zusammensetzung ist unbekannt.', call(EXPOSURE, args, result))


def verified_reads():
    return [call('read', {'path': ROOT + '/' + IMPORT_SKILL}, 'native skill content'),
            call('read', {'path': ROOT + '/' + IMPORT_REFERENCE},
                 'Pass manifests with reported_total_value to build_portfolio_snapshot.')]


class GraderTest(unittest.TestCase):
    def test_earnings_oneoff_reuses_supplied_facts_without_write(self):
        answer = "Umsatz 4 % über der Erwartung. Der EPS-Konsens fehlt."
        read = call('skills_read', {'name':'earnings-analysis'}, {'content':'Earnings research'})
        observed = trace('earnings_once', answer, read)
        self.assertTrue(all(grade(CASES['earnings_once'], observed).values()))
        observed['tool_calls'].append(call('set_earnings_tracking', {'action':'watch'}, {'ok':True}))
        self.assertFalse(grade(CASES['earnings_once'], observed)['allowed_tools'])

    def checks(self, observed):
        return grade(CASES[observed['id']], observed)

    def assertPass(self, observed):
        checks = self.checks(observed)
        self.assertTrue(all(type(value) is bool for value in checks.values()), checks)
        self.assertTrue(all(checks.values()), checks)

    def test_exposure_uses_both_observed_input_and_output(self):
        observed = exposure_trace()
        self.assertPass(observed)
        observed['tool_calls'][0]['arguments']['cash_value'] = '437'
        self.assertFalse(self.checks(observed)['source_arguments'])
        observed['tool_calls'][0]['result']['unknown'] = []
        self.assertFalse(self.checks(observed)['calculated_weight_and_unknown'])
        observed['assistant_text'] = '65 %'
        self.assertFalse(self.checks(observed)['answer_weight'])

    def test_correct_text_without_tool_fails(self):
        self.assertFalse(self.checks(trace('exposure', '64,96 % im ETF.'))['expected_call'])

    def test_import_valid(self):
        observed = trace('import_valid', 'Gesamtwert 1.000,00 EUR.', *verified_reads(), snapshot_call())
        self.assertPass(observed)
        observed['tool_calls'][1]['is_error'] = True
        self.assertFalse(self.checks(observed)['normalized_reference_read'])
        observed['tool_calls'][-1]['result']['positions'][0]['quantity'] = '9'
        self.assertFalse(self.checks(observed)['validated_snapshot'])

    def test_native_skill_read_is_a_valid_route(self):
        skill = call('skills_read', {'name': 'portfolio-import'}, 'native skill instructions')
        ref = verified_reads()[1]
        observed = trace('import_valid', 'Depotwert 1000 EUR.', skill, ref, snapshot_call())
        self.assertPass(observed)
        observed['tool_calls'] = [ref, snapshot_call(), skill]
        self.assertFalse(self.checks(observed)['import_skill_read'])

    def test_native_alias_must_be_proven_and_contain_the_reference(self):
        state = '/home/node/.openclaw'
        alias = state + '/plugin-skills/portfolio-import/'
        skill_text = 'Use [normalized input](references/normalized-input.md).'
        skill = call('skills_read', {'name': 'portfolio-import'}, {
            'name': 'portfolio-import', 'content': skill_text,
            'location': '$OPENCLAW_STATE_DIR/plugin-skills/portfolio-import/SKILL.md'})
        skill['raw_result'] = 'Skill location: ' + alias + 'SKILL.md\n' + skill_text
        ref = verified_reads()[1]
        ref['arguments']['path'] = alias + 'references/normalized-input.md'
        ref['raw_result'] = ref['result']
        observed = trace('import_valid', '1000 EUR', skill, ref, snapshot_call())
        observed.update(plugin_root=state + '/extensions/portfolio-analyser', workspace_root=state + '/workspace')
        self.assertPass(observed)
        del skill['raw_result']
        self.assertFalse(self.checks(observed)['allowed_tools'])
        ref.update(resolved_document=IMPORT_REFERENCE, document_sha256=sha256(ref['raw_result'].encode()).hexdigest())
        self.assertPass(observed)
        ref['raw_result'] = 'unknown contents'
        self.assertFalse(self.checks(observed)['normalized_reference_read'])
        self.assertFalse(self.checks(observed)['allowed_tools'])
        ref['is_error'] = True
        self.assertFalse(self.checks(observed)['document_reads_succeeded'])

    def test_guest_proves_generated_native_copy_against_installed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'plugin'
            source = root / IMPORT_REFERENCE
            source.parent.mkdir(parents=True)
            source.write_text('manifest reference')
            generated = root / 'openclaw-skills' / Path(IMPORT_REFERENCE).relative_to('skills')
            generated.parent.mkdir(parents=True)
            generated.write_bytes(source.read_bytes())
            alias = Path(tmp) / 'visible-skill'
            alias.symlink_to(generated.parent.parent)
            item = call('read', {'path': str(alias / 'references/normalized-input.md')}, source.read_text())
            record_document_locations({'tool_calls': [item]}, str(root))
            self.assertEqual(item['resolved_document'], IMPORT_REFERENCE)
            self.assertEqual(item['document_sha256'], sha256(source.read_bytes()).hexdigest())
            item.pop('resolved_document')
            item.pop('document_sha256')
            generated.write_text('different contents')
            record_document_locations({'tool_calls': [item]}, str(root))
            self.assertNotIn('resolved_document', item)

    def test_only_same_synthetic_session_history_is_allowed(self):
        session = 'agent:main:explicit:eval-' + '1' * 32
        other = 'agent:main:explicit:eval-' + '2' * 32
        history = call('sessions_history', {'sessionKey': session}, {'sessionKey': session})
        history['id'] = 'unique-self-id'
        observed = trace('missing_attachment', 'Bitte den fehlenden Auszug hochladen.', history)
        observed['session_key'] = session
        self.assertPass(observed)
        observed['session_key'] = other
        self.assertFalse(self.checks(observed)['allowed_tools'])
        del observed['session_key']
        self.assertFalse(self.checks(observed)['allowed_tools'])
        history['result']['messages'] = [{'role': 'assistant', 'content': [
            {'type': 'toolCall', 'id': history['id'], 'name': 'sessions_history', 'arguments': {'sessionKey': session}}]}]
        self.assertPass(observed)
        history['result']['messages'][0]['content'][0]['id'] = 'other-session-call'
        self.assertFalse(self.checks(observed)['allowed_tools'])

    def test_missing_file_can_inspect_disposable_workspace(self):
        listing = call('ls', {}, [])
        observed = trace('missing_attachment', 'Bitte lade den Auszug hoch.', listing)
        observed['workspace_root'] = '/home/node/.openclaw/workspace'
        self.assertPass(observed)
        listing['arguments'] = {'path': '/home/node/.openclaw/workspace/../secrets'}
        self.assertFalse(self.checks(observed)['allowed_tools'])

    def test_mismatch_accepts_early_stop_or_observed_rejection(self):
        observed = trace('import_mismatch', 'Ausgewiesen sind 1.100 EUR, berechnet 1.000 EUR. Bitte klären.')
        self.assertPass(observed)
        rejection = snapshot_call('1100')
        rejection.update(result={'message': 'Positionssumme plus Cash weicht vom angegebenen Gesamtwert ab'}, is_error=True)
        observed['tool_calls'].append(rejection)
        self.assertPass(observed)
        rejection['result'] = {'message': 'Fehlende Pflichtfelder'}
        self.assertFalse(self.checks(observed)['validation_rejected_mismatch'])
        rejection['raw_result'] = 'Manifest 1: Positionssumme plus Cash weicht vom angegebenen Gesamtwert ab'
        self.assertPass(observed)
        observed['tool_calls'] = [snapshot_call('1000')]
        self.assertFalse(self.checks(observed)['source_arguments'])
        self.assertFalse(self.checks(observed)['validation_rejected_mismatch'])

    def test_missing_data_declines_even_if_a_tool_supplies_defaults(self):
        observed = trace('missing_attachment', 'Bitte lade deinen Depotauszug hoch.')
        self.assertPass(observed)
        observed['tool_calls'].append(snapshot_call())
        self.assertFalse(self.checks(observed)['allowed_tools'])
        self.assertFalse(self.checks(observed)['no_portfolio_call'])

    def test_read_only_comparison_rejects_extra_shell_actions(self):
        from grade import comparison_helper
        helper = ROOT + "/scripts/research_checks.py"
        cmd = f"python3 -B {helper} compare /dev/stdin <<'JSON'\n" + '{"actual":{},"baseline":{}}' + "\nJSON"
        self.assertTrue(comparison_helper(call("exec", {"command":cmd}, "result"), ROOT))
        for extra in ("\nrm file", "; cat /secrets", "\nJSON\necho forged"):
            self.assertFalse(comparison_helper(call("exec", {"command":cmd+extra}, "result"), ROOT))

    def test_unknown_names_incomplete_inputs_and_traces_fail_closed(self):
        for bad in (call('exec', {}, 'ok'), call('other__portfolio_exposure', {}, 'ok'),
                    call('read', {'path': '/secrets/' + IMPORT_SKILL}, 'ok'),
                    call('read', {'path': ROOT + '/../credentials'}, 'ok')):
            with self.subTest(bad=bad):
                observed = trace('missing_attachment', 'Bitte lade den Auszug hoch.', bad)
                self.assertFalse(self.checks(observed)['allowed_tools'])
        observed = exposure_trace()
        del observed['tool_calls'][0]['is_error']
        self.assertFalse(self.checks(observed)['complete_trace'])
        observed = trace('missing_attachment', 'Bitte lade den Auszug hoch.')
        observed.update(complete=False, prompt='unrelated')
        self.assertFalse(self.checks(observed)['complete_trace'])
        self.assertFalse(self.checks(observed)['matched_prompt'])


if __name__ == '__main__':
    unittest.main()
