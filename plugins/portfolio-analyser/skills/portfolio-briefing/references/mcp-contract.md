# Portfolio Briefing MCP contract — schema 3

Use the installed `portfolio_analyser` MCP connection. Transport names retain `dashboard`. An older server must be updated; do not silently downgrade.

## Read once

`get_dashboard_context()` returns `snapshot` (including `id`, `as_of`, `base_currency`, `total_value`, `cash_value`), every `position` with deterministic `portfolio_weight_pct`, complete enabled `reports`, `excluded_reports`, `total_content_chars`, `source_fingerprint`, `existing_briefing_id`, and `plan` (null before the first V3 generation).

Reports include `id`, `analysis_type`, `created_at`, `content_markdown`, and `max_age_days`. The fingerprint covers portfolio, report selection, and plan/confirmation state. Publication after an intervening change is rejected. Successful unchanged generations are discoverable via `existing_briefing_id`; publication itself does not make its result perpetually stale.

The plan contains:

- `id`, `state_version`, `strategy`, `strategy_history`;
- `reconciled_snapshot_id`, `reconciled_as_of`;
- `actions`: stable records with `id`, `status` (`open`, `confirmed`, `superseded`, `resolved`), stored `action` (including `predecessor_id`), `portfolio_snapshot_id`, `snapshot_as_of`, `proposed_at`, `confirmed_at`, `confirmation_date`, `confirmation_history`, and optional `resolution_reason`. The server sets `proposed_at` once for a new action ID; carrying an action or confirming it never restarts its execution window. Older records may have no start timestamp. The stored confirmation date preserves its original local calendar day across later time-zone changes.

Confirmation history is user assertion, not execution data. Action snapshot IDs identify baselines, not enduring instruments.

## Stable instrument identity

Prefer `ISIN:<UPPERCASE ISIN>`. Otherwise use `SYMBOL:<lowercase asset_type>:<UPPERCASE CURRENCY>:<UPPERCASE SYMBOL>`, for example `SYMBOL:crypto:EUR:ETH`. Cash is `CASH`. A bare symbol or a snapshot-specific position UUID cannot be a stable key. Do not merge ambiguous instruments. For symbol-only subjects include `asset_type` and `currency`; all supplied identifiers must agree. New instruments need included report evidence and a qualified key.

## Publish

Call `publish_dashboard_briefing` with:

```text
id = one caller-generated briefing UUID
source_fingerprint = unchanged value from the context
generator = "codex_skill"
generator_version = "portfolio-briefing/3"
schema_version = 3
briefing = {summary, strategy, actions, plan}
```

`briefing.strategy` is the always-visible, plain-language strategic destination before the todos, not merely a list of quotas. `briefing.summary` explains why the current package takes precedence and why relevant new positions are selected or deferred. Keep deeper prioritization, candidate comparisons, assumptions, and calculations in `briefing.plan.strategy.rationale`; do not add unsupported payload fields. `briefing.plan` has:

```json
{
  "expected_state_version": 0,
  "strategy": {
    "id": "strategy UUID; retained across revisions",
    "revision": 1,
    "time_zone": "Europe/Berlin",
    "investment_horizon_days": 1825,
    "rationale": "Why these model targets and tolerances; not a proven optimum.",
    "change_reason": null,
    "allocations": [
      {"instrument_key": "ISIN:IE00EXAMPLE00", "name": "Example ETF", "target_weight_pct": 60, "tolerance_pct": 2},
      {"instrument_key": "CASH", "name": "Cash", "target_weight_pct": 40, "tolerance_pct": 2}
    ]
  }
}
```

This structural example is not an allocation to copy. Allocations cover all current instruments, intended additions, and cash exactly once and total 100%. Use zero targets for intended exits. Reuse the complete stored strategy when unchanged. A change retains its ID, increments its revision by one, and includes a substantive `change_reason`. Set `expected_state_version` from context, or 0 for the first plan.

For an explicit withdrawal, `briefing.plan.resolutions` optionally contains `[{"action_id": "open action UUID", "reason": "documented reason"}]`. Use this for a justified strategy revision that no longer supports the recommendation, or qualifying target attainment; never silently omit an open step or fake an urgent event to cancel it. The stored record retains `resolution_reason` in history. This is not a user confirmation.

### Concrete action

Every non-hold action includes:

```json
{
  "id": "stable action UUID",
  "priority": 1,
  "action": "reduce",
  "subject": {"kind": "instrument", "name": "Example ETF", "isin": "IE00EXAMPLE00"},
  "instrument_key": "ISIN:IE00EXAMPLE00",
  "target_weight_pct": 60,
  "next_target_weight_pct": 68,
  "rationale": "One short investment or concentration reason.",
  "horizon_days": 1825,
  "confidence": "medium",
  "reason_kind": "risk_reallocation",
  "review_after": "2026-09-19T10:00:00+02:00",
  "execution_window_days": 14,
  "alternatives": "No change versus this reduction and relevant substitutes; why this path was selected.",
  "pacing_rationale": "Why this step balances continued exposure, uncertainty, and costs.",
  "funding_action_ids": [],
  "predecessor_id": null,
  "replacement_reason": null,
  "evidence_refs": [{"source_type": "portfolio_snapshot", "source_id": "current snapshot UUID"}]
}
```

The example assumes a current share above 68%; use actual context values and dates.

- Actions: `buy`, `increase`, `reduce`, `sell`; `sell` has final target 0 even for a staged partial exit. Non-hold subject: concrete instrument or cash.
- `target_weight_pct`: final share equal to the strategy target.
- `next_target_weight_pct`: next share strictly in the direction from current to final, without overshoot. This difference determines the displayed next amount.
- `reason_kind`: `risk_reallocation`, `opportunity`, or `urgent_deterioration`.
- `review_after`: timezone-aware ISO timestamp in the future at publication for NEW actions; earliest review, not an automatic next step. Retain existing dates when carrying an unchanged action. `execution_window_days`: one current-step window anchored to the server's original `proposed_at`, not a rolling window from the latest briefing. An expired window does not authorize a new action or catch-up orders. `horizon_days`: investment horizon.
- `funding_action_ids`: if total purchases exceed recorded cash, EVERY purchase names ALL sales supporting this executable package. The server uses this conservative joint-package rule, not independent per-card cash budgets. A checkbox earns no funding credit. Both next and final package allocations must reconcile with recorded holdings/cash; untouched holdings remain held. Optional cash-action targets must match their respective package residuals within €0.01, with the final also matching the strategy cash target; cash is not another funding source.
- `predecessor_id`: terminal prior action when a qualifying import permits a residual step. `replacement_reason`: explicit reason when a documented strategy revision replaces an OPEN recommendation without claiming progress; this need not be urgent. Confirmed actions still require a qualifying new statement. Do not link an old ancestor with an existing successor.
- Evidence is `{source_type: "analysis" | "portfolio_snapshot", source_id: UUID}`, exclusively from this context. No user confirmation fields may be generated.

Summary ≤500 characters; visible strategy ≤400; rationale ≤240; subject name ≤80. Unique priorities, at most five changes plus one hold, no duplicate instrument recommendations. Retain an unchanged open action's ID and execution intent; new words or reports do not advance its target.

### Consolidated hold

```json
{
  "priority": 6,
  "action": "hold",
  "subject": {"kind": "remaining_positions", "name": "Alle übrigen Positionen"},
  "rationale": "Für zusätzliche Umschichtungen gibt es derzeit keinen ausreichend starken Grund.",
  "horizon_days": 365,
  "confidence": "medium",
  "evidence_refs": [{"source_type": "portfolio_snapshot", "source_id": "current snapshot UUID"}]
}
```

Holds omit targets and execution metadata. The optional group is at most once, last by priority, for untouched current instruments, not cash or individually traded holdings.

Zero trades still requires one justified hold in `actions`, not an empty array. With no instrument positions (all cash), use a single `portfolio` hold rather than an empty remaining-positions group.

## Progress and recovery

Briefing and plan updates commit atomically. New IDs for an already recommended instrument need a linked transition; a new report, checkbox, or elapsed review alone is insufficient. Date-only snapshots must postdate the confirmation day in the strategy time zone. Preserve history when progress is ambiguous.

For a previously recommended instrument, link the most recent terminal record, including a `resolved` one if later drift justifies another step. Never omit a confirmed ancestor's later successor. Unchanged open actions may be carried across a newer snapshot without advancing their target; their original baseline is retained and the dashboard suppresses obsolete amounts. Recalculated steps require the qualifying successor transition. Refresh evidence references from the current context, not excluded historical reports.

Carry immutable execution intent exactly: action type, instrument key, final/next targets, review date, execution window, reason category, funding IDs, and predecessor. A carried action on an obsolete snapshot is display/history only; do not use its old delta to fund a new executable package. A same-snapshot pending purchase may retain its original dependency on an already-confirmed sale without re-emitting that sale. It remains conditional on available proceeds, never treated as verified cash.

Success returns `{id, created}`. An identical retry returns the stored generation with `created=false`. Retry only a transport-uncertain write, once at most, with identical UUID/content. Validation, UUID conflict, or changed-context errors are hard failures; preserve the draft and report the blocker.

Only the web app lets the user confirm/undo with `PUT /api/v1/dashboard/actions/{id}/confirmation`, body `{confirmed, expected_state_version}`. This skill never calls it. No holdings, quantities, or cash are changed.
