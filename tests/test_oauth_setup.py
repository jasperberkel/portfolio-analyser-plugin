import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/portfolio-analyser'
spec = importlib.util.spec_from_file_location('configure_mcp', ROOT / 'scripts/configure_mcp.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class OAuthSetupTests(unittest.TestCase):
    def test_keyring_update_preserves_unrelated_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('model = "saved-model"\n# keep\n[mcp_servers.other]\nurl = "https://other.example/mcp"\n')
            setup.require_keyring(path)
            first = path.read_text()
            setup.require_keyring(path)
            self.assertEqual(path.read_text(), first)
            data = tomllib.loads(first)
            self.assertEqual(data['mcp_oauth_credentials_store'], 'keyring')
            self.assertEqual(data['mcp_servers']['other']['url'], 'https://other.example/mcp')
            self.assertIn('# keep', first)

    def test_only_native_http_oauth_commands(self):
        for host in ['codex', 'claude']:
            commands = setup.commands(host, 'https://portfolio.example/mcp')
            self.assertEqual(commands[0][0], host)
            self.assertIn('portfolio_analyser', commands[0])
            self.assertNotIn('--client-secret', commands[0])
            self.assertNotIn('--bearer-token-env-var', commands[0])
        self.assertEqual(set(json.loads((ROOT / '.mcp.json').read_text())['mcpServers']), {'portfolio'})
        self.assertFalse((ROOT / 'bin').exists())
        self.assertFalse((ROOT / 'scripts/mcp_call.py').exists())

    def test_url_validation(self):
        self.assertEqual(setup.validate_url('http://localhost:3000/mcp'), 'http://localhost:3000/mcp')
        for value in ['http://public.example/mcp', 'https://user:secret@portfolio.example/mcp', 'https://portfolio.example/mcp?token=x']:
            with self.assertRaises(ValueError): setup.validate_url(value)


class BundledConnectionTests(unittest.TestCase):
    def test_setup_uses_bundled_address_without_user_input(self):
        for host in ('codex', 'claude'):
            with tempfile.TemporaryDirectory() as directory:
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/configure_mcp.py'),
                    '--host', host, '--dry-run'], cwd=directory, capture_output=True, text=True, check=True)
                commands = json.loads(result.stdout)
                self.assertIn(setup.load_connection(), commands[0])
                self.assertEqual(commands[0][0], host)

    def test_installed_package_resolves_its_own_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / 'installed-plugin'
            (installed / 'scripts').mkdir(parents=True)
            (installed / 'config').mkdir()
            shutil.copy(ROOT / 'scripts/configure_mcp.py', installed / 'scripts/configure_mcp.py')
            (installed / 'config/connection.json').write_text(json.dumps({
                'environment': 'production', 'mcp_url': 'https://portfolio.example/mcp'}))
            result = subprocess.run([sys.executable, str(installed / 'scripts/configure_mcp.py'),
                '--host', 'codex', '--dry-run'], cwd=directory, capture_output=True, text=True, check=True)
            self.assertIn('https://portfolio.example/mcp', json.loads(result.stdout)[0])
            self.assertNotIn('localhost', result.stdout)

    def test_invalid_packaged_config_fails_without_url_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'connection.json'
            with self.assertRaisesRegex(ValueError, 'configuration'):
                setup.load_connection(path)
            for configuration in [
                {'environment': 'production', 'mcp_url': 'http://localhost:3300/mcp'},
                {'environment': 'production', 'mcp_url': 'https://localhost/mcp'},
                {'environment': 'production', 'mcp_url': 'http://portfolio.example/mcp'},
                {'environment': 'unknown', 'mcp_url': 'https://portfolio.example/mcp'},
                {'environment': 'production'},
            ]:
                path.write_text(json.dumps(configuration))
                with self.subTest(configuration=configuration), self.assertRaises(ValueError):
                    setup.load_connection(path)
