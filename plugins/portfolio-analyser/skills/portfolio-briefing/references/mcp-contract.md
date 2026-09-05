# Portfolio Briefing MCP contract — schema 4

Use the installed `portfolio_analyser` MCP connection. An older server must be updated; never downgrade the publication format.

## Default context

`get_dashboard_context()` returns:

- `snapshot`: current `id`, holdings `as_of`, `base_currency`, `total_value`, `cash_value`, `created_at`.
- `positions`: all current positions with quantity, price, market value, identifiers and `portfolio_weight_pct`.
- `reports`: complete latest enabled, nonexpired research with `id`, `analysis_type`, `created_at`, `content_markdown`, `max_age_days`.
- `excluded_reports`: stale report metadata; not evidence.
- `plan`: current immutable version, or null. Fields: `id` (version UUID), `plan_id` (stable plan UUID), `version`, `content_markdown`, `created_at`, `change_reason`, `migrated`.
- `previous_briefing`: last successful report, or null. Includes `id`, `title`, `report_date`, `generated_at`, `schema_version`, `payload: {title, content_markdown}`, `portfolio_snapshot_id`, `snapshot_as_of`, `plan_version_id`, `source_analysis_ids`, `sources`, and generator/fingerprint metadata.
- `previous_portfolio`: that report's original snapshot and complete positions, separate from current holdings; null without a previous report.
- `report_date`: server date in Europe/Berlin. `source_fingerprint`: exact opaque publication input token. `review_state_version`: internal concurrency metadata, never a trade count. `total_content_chars`: loaded research, plan and prior report text size. `existing_briefing_id`: already successful review of this daily context, otherwise null.

A new Berlin calendar day permits a review with unchanged holdings and research. Changed input data can permit another report on the same day. Publication itself never causes another required generation. The input/result fingerprint pair identifies the same successful review before and after its atomic state change. A failed publication leaves the last successful report visible. History is immutable.

## Optional history reads

- `list_dashboard_briefings(limit=20, cursor=null)` → `{items, next_cursor}` with report metadata, no full Markdown.
- `get_dashboard_briefing(id)` → full report and its exact `plan_version_id`.
- `list_portfolio_plan_versions(limit=20, cursor=null)` → `{items, next_cursor}` with version metadata, no full Markdown.
- `get_portfolio_plan_version(id)` → complete exact version.

Limits are 1–100. Pass `next_cursor` unchanged. Fetch a historical report's `plan_version_id` to see its actual associated plan; never substitute the current version. Migrated legacy reports may have no determinable association. Their text remains readable and is labelled historical.

Equivalent REST reads: `/api/v1/dashboard/briefings`, `/briefings/{id}`, `/plan/current`, `/plan/versions`, `/plan/versions/{id}` beneath `/api/v1/dashboard`; the existing `/api/v1/dashboard/briefing/current` returns `{briefing, plan, is_stale, stale_reasons}`. List endpoints accept `limit` and `cursor`. There is no confirmation endpoint.

## Atomic publication

`publish_dashboard_briefing` accepts:

```json
{
  "id": "one caller-generated report UUID",
  "source_fingerprint": "unchanged 64-character token from context",
  "generator": "codex_skill",
  "generator_version": "portfolio-briefing/4",
  "schema_version": 4,
  "expected_plan_version": 0,
  "briefing": {
    "title": "Erste Prüfung des importierten Depots",
    "content_markdown": "Der Anlageplan steht; für die aktuelle Entscheidung fehlen noch vergleichbare Bewertungsdaten.\n\nHier folgt die frei gegliederte, belegte Einordnung des tatsächlichen Depots."
  },
  "plan_update": {
    "content_markdown": "# Anlageplan\n\nHier steht der vollständige, aus dem tatsächlichen Kontext begründete langfristige Plan einschließlich Zielen, Finanzierung und Risiken.",
    "change_reason": "Erstmaliger Anlageplan auf Grundlage des importierten Portfolios."
  }
}
```

This is a structural example, not a finished report or prescribed allocation. Use actual UUIDs, evidence and content. First publication: `expected_plan_version=0` and a complete `plan_update`. Later: use `context.plan.version`. Omit `plan_update` when the plan is unchanged. For a substantive revision supply the complete replacement Markdown and a specific `change_reason`; do not send a patch or choose a new plan identity/version. The server preserves `plan_id`, increments `version` only when content changes and attaches the exact version to the report. Identical text (normalized line endings and surrounding whitespace) creates no revision, even if submitted again with a different reason.

Markdown may be short or long with freely chosen headings, paragraphs, lists and tables. There are no summary/strategy/action fields, mandatory hold, action count or old short field limits. Technical ceilings: title 300 characters, each Markdown document 2,000,000 characters, change reason 20,000 characters. Nonblank content is required. Raw HTML is not executable or rendered as HTML; use Markdown.

Report day, publication time, snapshot association and research references are set by the server, never supplied by the skill. Cite included evidence inside the Markdown as appropriate. Do not add unsupported fields.

Success: `{id, created}`. Identical retries return the original ID with `created=false`; concurrent requests for the same successful context resolve to the stored winner or a conflict, never another review. Reusing an ID with changed arguments is rejected. A stale input, wrong expected plan version or invalid initial plan fails atomically. V1–V3 writers receive a clear upgrade error and cannot change a V4 plan.
