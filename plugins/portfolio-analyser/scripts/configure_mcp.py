#!/usr/bin/env python3
"""Configure the native client. Never read OAuth credentials or call app tools."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
from urllib.parse import urlparse

NAME = "portfolio_analyser"
CONNECTION_CONFIG = Path(__file__).resolve().parents[1] / "config" / "connection.json"


def validate_url(value):
    url = urlparse(value)
    local = url.hostname in ("localhost", "127.0.0.1", "::1")
    if (url.scheme != "https" and not (url.scheme == "http" and local)) or not url.hostname:
        raise ValueError("MCP URL requires HTTPS (HTTP allowed only on loopback)")
    if url.username or url.password or url.query or url.fragment or url.path != "/mcp":
        raise ValueError("Plugin MCP URL must end in /mcp without credentials, query or fragment")
    return value



def load_connection(path=CONNECTION_CONFIG):
    """The application publisher configures the endpoint, never the end user."""
    try:
        config = json.loads(path.read_text())
        environment = config.get('environment')
        if environment not in ('development', 'production'):
            raise ValueError('Plugin connection environment must be development or production')
        authentication = config.get('authentication', 'oauth')
        if authentication not in ('local-grant', 'oauth'):
            raise ValueError('Unknown portfolio service authentication')
        if authentication == 'local-grant' and environment != 'development':
            raise ValueError('Local grants are only supported in development')
        url = validate_url(config['mcp_url'])
        parsed = urlparse(url)
        if environment == 'production' and (parsed.scheme != 'https' or parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Production plugin requires its public HTTPS MCP address')
        return url
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Plugin connection configuration is missing or invalid; repair the plugin package') from exc


def require_keyring(path):
    """Change only the top-level setting; preserve all unrelated config text."""
    original = path.read_text() if path.exists() else ""
    parsed = tomllib.loads(original)
    if parsed.get("mcp_oauth_credentials_store") == "keyring": return
    lines = original.splitlines(keepends=True)
    root_end = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    root = ''.join(lines[:root_end])
    pattern = r'(?m)^\s*mcp_oauth_credentials_store\s*=.*$'
    setting = 'mcp_oauth_credentials_store = "keyring"'
    root = re.sub(pattern, setting, root) if re.search(pattern, root) else setting + '\n' + root
    updated = root + ''.join(lines[root_end:])
    tomllib.loads(updated)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.mcp-config-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(updated)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def commands(host, url, local_grant=False):
    if local_grant:
        parsed = urlparse(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1', 'localhost'):
            raise ValueError('Local grants require a loopback HTTP endpoint')
        if host == 'codex':
            return [['codex', 'mcp', 'add', NAME, '--url', url, '--bearer-token-env-var', 'TRADING_PORTFOLIO_TOKEN']]
        return [['claude', 'mcp', 'add', '--transport', 'http', '--scope', 'user', NAME, url,
                 '--header', 'Authorization: Bearer ${TRADING_PORTFOLIO_TOKEN}']]

    if host == 'codex':
        return [
            ['codex', 'mcp', 'add', NAME, '--url', url, '--oauth-resource', url],
            ['codex', 'mcp', 'login', NAME, '--scopes', 'portfolio:read,portfolio:import'],
        ]
    return [
        ['claude', 'mcp', 'add', '--transport', 'http', '--scope', 'user', NAME, url],
        ['claude', 'mcp', 'login', NAME],
    ]


def remaining_commands(host, existing_config, url, local_grant, planned):
    """Reuse an entry at this URL, or upgrade only our own legacy token reference."""
    if host == 'codex':
        transport = json.loads(existing_config).get('transport', {})
        token_ref = transport.get('bearer_token_env_var')
        if transport.get('url') == url:
            if token_ref == ('TRADING_PORTFOLIO_TOKEN' if local_grant else None):
                return planned[1:]
            if not local_grant and token_ref == 'TRADING_PORTFOLIO_TOKEN':
                return planned[:1]
    elif url in existing_config.split():
        if local_grant:
            if 'TRADING_PORTFOLIO_TOKEN' in existing_config:
                return []
        elif 'Authorization:' not in existing_config:
            return planned[1:]
    raise ValueError('A different connection already owns this name. Review its existing configuration.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude'], required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        url = load_connection()
        local_grant = json.loads(CONNECTION_CONFIG.read_text()).get('authentication') == 'local-grant'
        native_commands = commands(args.host, url, local_grant)
    except ValueError as exc:
        parser.error(str(exc))
    if args.dry_run:
        fresh = native_commands[:1] if args.host == 'codex' and not local_grant else native_commands
        print(json.dumps(fresh, indent=2))
        return
    if local_grant and not os.environ.get('TRADING_PORTFOLIO_TOKEN'):
        parser.error('Start the native host with the operator-issued TRADING_PORTFOLIO_TOKEN')
    if args.host == 'codex' and not local_grant:
        require_keyring(Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'config.toml')
    inspect_command = [args.host, 'mcp', 'get', NAME]
    if args.host == 'codex':
        inspect_command.append('--json')
    existing = subprocess.run(inspect_command, capture_output=True, text=True)
    if existing.returncode == 0:
        try:
            native_commands = remaining_commands(args.host, existing.stdout, url, local_grant, native_commands)
        except ValueError as exc:
            parser.error(str(exc))
    elif args.host == 'codex' and not local_grant:
        # This CLI starts OAuth while adding a new HTTP entry. Login explicitly only
        # for an existing entry that the host determined still needs authorization.
        native_commands = native_commands[:1]
    for command in native_commands:
        subprocess.run(command, check=True)
    print('Native HTTP connection configured. Reload the host and verify its native tools.')


if __name__ == '__main__': main()
