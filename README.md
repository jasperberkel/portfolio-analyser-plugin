# Portfolio Analyser Plugin

Cross-platform plugin marketplace for Codex and Claude Code. It bundles the Portfolio Analyser workflows while keeping development-only skills in the application repository.

## Included skills

- `portfolio-import`: import and synchronize portfolio documents
- `portfolio-position-research`: research every current position by default, or an explicitly requested subset, with comparable health, valuation, and thesis-change evidence
- `market-opportunity-research`: research up to eight non-personalized market opportunities without a minimum quota
- `finanzen-news-research`: read finanzen.net news and publish a sourced German report through MCP
- `portfolio-briefing`: maintain a stable allocation plan with funded next steps, separate long-term goals, and user-confirmed progress
- `portfolio-analyser-setup`: discover and configure recurring research and briefing jobs for Codex or Claude Code

## Prerequisite

The skills expect the local [Portfolio Analyser](https://github.com/jasperberkel/portfolio-analyser) application to be running. The plugin includes its MCP bridge and secure pairing flow; no environment token is needed.

The updated briefing workflow requires app schema 3 (`portfolio-briefing/3`). Update the app alongside the plugin; the skill does not silently downgrade to older briefing formats. Confirming an action in the app records only a user assertion, never a broker execution or cash balance. Later statements drive revised follow-up recommendations; ordinary daily research does not automatically create another tranche.

## Install in Codex

Add the GitHub marketplace:

```bash
codex plugin marketplace add jasperberkel/portfolio-analyser-plugin
```

Start Codex, open `/plugins`, install **Portfolio Analyser**, and start a new session.

## Install in Claude Code

```bash
claude plugin marketplace add jasperberkel/portfolio-analyser-plugin
claude plugin install portfolio-analyser@portfolio-analyser
```

In Claude Code, skills are available under the plugin namespace, for example:

```text
/portfolio-analyser:portfolio-import
/portfolio-analyser:portfolio-position-research
/portfolio-analyser:market-opportunity-research
/portfolio-analyser:finanzen-news-research
/portfolio-analyser:portfolio-briefing
/portfolio-analyser:portfolio-analyser-setup
```

## Create a news report

For a news report on demand, ask:

```text
Use $finanzen-news-research to summarize the latest finanzen.net news
and upload the German report to Portfolio Analyser.
```

The news skill defaults to the last 24 hours and stores reports as `news.finanzen-net`, without requiring portfolio holdings. It verifies the saved report through MCP after publication.

## Secure setup and recurring jobs

After installation, ask Codex or Claude Code:

```text
Set up Portfolio Analyser and its recurring research and briefing jobs.
```

The setup skill first asks you to generate a five-minute, single-use code under `http://localhost:3000/settings`. Its bundled helper exchanges that code and stores the permanent credential in macOS Keychain, Windows Credential Manager, or Linux Secret Service. The token is never shown in the app or conversation.

After a successful MCP handshake, the skill dynamically discovers all plugin skills ending in `-research` or `-briefing`. It checks existing schedules before making changes, then proposes research jobs daily at 10:00 and briefing jobs daily at 11:00. Future skills using either suffix are included automatically.

Linux requires an installed and unlocked Secret Service such as GNOME Keyring. The setup fails safely instead of writing credentials to a plaintext file.

## Ask an agent to install it

Paste this repository URL into Codex or Claude Code and ask:

```text
Install the Portfolio Analyser plugin marketplace from
https://github.com/jasperberkel/portfolio-analyser-plugin
and install its portfolio-analyser plugin.
```

## Repository layout

```text
.agents/plugins/marketplace.json          Codex marketplace
.claude-plugin/marketplace.json           Claude Code marketplace
plugins/portfolio-analyser/
  .codex-plugin/plugin.json               Codex manifest
  .claude-plugin/plugin.json              Claude Code manifest
  .mcp.json                               Codex MCP descriptor
  .claude-plugin/plugin.json              Claude MCP descriptor and manifest
  bin/                                    Bundled platform binaries
  skills/                                 Shared Agent Skills
```
