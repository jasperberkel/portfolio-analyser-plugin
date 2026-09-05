# Orchestration contract — version 1

`workflow.json` in each participating skill contains `contract_version: 1`, exact `skill`, `stage` (research/strategy), `requires`, and stable `produces`. All registered research is mandatory; exactly one strategy is required. Discovery is confined to this plugin. Adding a compatible research descriptor needs no orchestrator edit. Unknown inputs/versions, duplicate skills/types or dependency cycles fail preflight. App report enabled/max_age settings affect strategy evidence, not research execution.

Inputs currently supported: current_portfolio, previous_report (same report type or null), plan, previous_strategy (report and original holdings), strategy_context (strategy phase only). Describe required inputs explicitly; do not infer them from skill names. A research stage requiring current_portfolio must cover all supplied positions in a full run. Read [draft-contract.md](draft-contract.md) for exact worker output formats.

## Local helper protocol

Use an absolute helper path and an absolute run directory. All commands return JSON and use no network. Supply file contents to MCP as structured objects, never JSON serialized inside a string. `.analysis-runs/` is excluded from Git. If a different project lacks that ignore rule, use its ignored scratch directory or a persistent user-owned directory outside Git.

1. `python3 <helper> discover` → workflow. Call `get_analysis_context(workflow=...)`. Save response as context-input.json outside the chosen new run directory; inspect existing_run first.
2. `python3 <helper> init <run-dir> <context-input.json>` → state, partitioned `<skill>/input.json`. The returned run_id is authoritative.
3. `python3 <helper> start <run-dir> <skill>` before spawning each attempt. Worker writes `<run-dir>/<skill>/result.json`.
4. `python3 <helper> collect <run-dir> <skill>` validates and saves accepted.json, or marks failure. Use `fail` instead if the worker crashed/interrupted without a result. `status` shows pending/running/complete/failed, attempt counts and stopped. Each round allows two attempts per affected researcher. Do not collect a stale result after a failed attempt; use fail.
5. `python3 <helper> draft <run-dir>` only succeeds after all required results complete. Call `prepare_strategy_context(draft=<output>)`, save response, then `python3 <helper> prepared <run-dir> <response.json>`. This creates strategy/input.json.
6. Worker writes strategy/result.json. `python3 <helper> strategy <run-dir> <result.json>` validates it. needs_research reopens requested research tasks with full current drafts. Repeat 3–6 once for them. Final strategy must use the newly prepared evidence token.
7. `python3 <helper> publication <run-dir>` freezes publication.json. Call `publish_analysis_run(publication=<output>)` and save the returned receipt. No publication in a requested dry run.

Progress survives interruption on disk, but no background job or automatic recovery daemon is created. An interrupted running task must be accounted for with fail before a bounded retry. Before reusing drafts, reload get_analysis_context with the same workflow and compare source_fingerprint and report day. Stop on a mismatch; never rewrite the frozen context to make old work appear current. Validate content freshness as well as IDs. The helper is not a substitute for agent quality review.

## MCP inputs and outputs

- `get_analysis_context(workflow)` returns contract_version, workflow_fingerprint, source_fingerprint, research_cutoff, dashboard, previous_reports, report_settings, existing_run. dashboard retains V4 names: snapshot, positions, plan, previous_briefing, previous_portfolio, reports, excluded_reports and report_date. Missing comparisons are explicit null values.
- `prepare_strategy_context(draft)` accepts run_id, workflow, source_fingerprint and the complete list of research results. It returns source_fingerprint, evidence_fingerprint and dashboard. This call is read-only. New drafts replace previous reports of their types; unrelated enabled nonexpired reports remain. Excluded drafts are still part of the eventual upload but never strategy evidence.
- `publish_analysis_run(publication)` adds evidence_fingerprint, strategy `{title, content_markdown}`, expected_plan_version and optional plan_update `{content_markdown, change_reason}` to the same draft. It atomically stores all reports, a `portfolio-strategy/4` strategy, any full plan revision and a durable receipt. All contexts, sizes, IDs and coverage are rechecked by the server. Receipt: run_id, created, strategy_id, plan_version_id, research_ids.

Fingerprint values are opaque, distinct tokens. Never calculate or edit them in prompts. Source state includes the server's Berlin date, portfolio/review state, report baselines and preferences; evidence additionally binds the exact drafts and selected full reports. Reports' researched_at is their document creation timestamp; publication time belongs to the strategy and run receipt. Cite dates of underlying facts in Markdown.

Identical retries return the same receipt with created=false. Concurrent callers for the same source/workflow may receive the saved winner's receipt. Same UUID with different arguments is an error. No stage may publish individual reports to work around a failure. Unknown or oversized contexts fail without truncation: configured content ceiling defaults to 600,000 characters; packets must remain below the bridge's 16 MiB transport ceiling (helper/server use 15 MiB).

## Secure bridge fallback

Prefer host-provided MCP tools. If a desktop session has not refreshed its tool catalog but the paired bridge is available, the orchestrator can use `python3 <plugin-root>/scripts/mcp_call.py list --output <tools.json>` to inspect the real server, and `python3 <plugin-root>/scripts/mcp_call.py <tool> --arguments <arguments.json> --output <result.json>` to call the same MCP tools. Arguments are their exact outer wrapper, e.g. `{"workflow": ...}`, `{"draft": ...}` or `{"publication": ...}`. This is actual MCP over the existing secure bridge, not a REST bypass. It does not read, print or store the token. No automatic retries are performed; an uncertain publish follows the same single-retry rule. Workers must not use this client. An older server missing the required tools still stops the run.
