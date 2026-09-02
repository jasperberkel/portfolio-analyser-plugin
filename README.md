# Portfolio Analyser Plugin

Cross-platform plugin marketplace for Codex and Claude Code. It bundles the Portfolio Analyser workflows while keeping development-only skills in the application repository.

## Included skills

- `portfolio-import`: import and synchronize portfolio documents
- `portfolio-position-research`: research current portfolio positions
- `market-opportunity-research`: research non-personalized market opportunities
- `portfolio-briefing`: turn the current portfolio and reports into actionable recommendations
- `portfolio-analyser-setup`: discover and configure recurring research and briefing jobs for Codex or Claude Code

## Prerequisite

The skills expect the [Portfolio Analyser](https://github.com/jasperberkel/portfolio-analyser) application and its `portfolio_analyser` MCP server to be running and configured. The scheduling skill configures jobs but does not install or start the application.

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
/portfolio-analyser:portfolio-briefing
/portfolio-analyser:portfolio-analyser-setup
```

## Configure recurring jobs

After installation, ask Codex or Claude Code:

```text
Set up the recurring Portfolio Analyser research and briefing jobs.
```

The setup skill detects the host and dynamically discovers all plugin skills ending in `-research` or `-briefing`. It checks existing schedules before making changes, then proposes research jobs daily at 10:00 and briefing jobs daily at 11:00. Future skills using either suffix are included automatically.

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
  skills/                                 Shared Agent Skills
```
