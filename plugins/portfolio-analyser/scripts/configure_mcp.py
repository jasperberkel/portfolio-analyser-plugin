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


def commands(host, url):
    if host == 'codex':
        return [
            ['codex', 'mcp', 'add', NAME, '--url', url, '--oauth-client-id', 'portfolio-codex', '--oauth-resource', url],
        ]
    return [
        ['claude', 'mcp', 'add', '--transport', 'http', '--scope', 'user', '--client-id', 'portfolio-claude', NAME, url],
        ['claude', 'mcp', 'login', NAME],
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude'], required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        url = load_connection()
    except ValueError as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps(commands(args.host, url), indent=2)); return
    if args.host == 'codex':
        require_keyring(Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'config.toml')
    # This canonical name is the one managed by this setup. The plugin itself
    # intentionally contains no MCP entry, preventing duplicate stdio/HTTP tools.
    remove = [args.host, 'mcp', 'remove', NAME]
    if args.host == 'claude': remove += ['--scope', 'user']
    # Native CLIs keep OAuth storage and browser login entirely in the client.
    # Remove is idempotent; a missing entry is harmless, other errors are not.
    existing = subprocess.run([args.host, 'mcp', 'get', NAME], capture_output=True, text=True)
    if existing.returncode == 0:
        subprocess.run(remove, check=True)
    for command in commands(args.host, url): subprocess.run(command, check=True)
    print('Native OAuth connection configured. Reload the plugin/client and verify its native tools.')


if __name__ == '__main__': main()
