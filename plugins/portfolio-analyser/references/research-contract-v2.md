# Research task contract V2

Use the orchestrator's input.json. Copy these fields verbatim into result.json: contract_version, run_id, task_id, skill, analysis_type, methodology_revision, input_hash, dependency_hashes, followup_round, questions, snapshot_id. Set id to report_id. Add content_markdown (complete German report), researched_at (actual timezone-aware completion timestamp), status (complete, partial or failed), coverage {selected, researched, uncovered}, gaps (text list) and research_data. Complete results account for every input.selected identifier; incomplete work is never accepted. Missing facts within a completed investigation belong in gaps.

Do not compute hashes or invent supplied run/report/instrument identifiers. For a genuinely new thesis or event, generate one UUID and prefix it with instrument_id plus :thesis: or :event:; preserve that ID thereafter. Assign new local source_id/fact_id values consistently within the task. The helper generates input hashes, deterministic task IDs and scope. The server independently reconstructs the input and validates coverage and predecessor versions. Metadata is not optional.

## Shared data records

All payloads have schema_version: 1, kind and sources. Arrays may be empty when the investigation establishes no data; explain missing evidence in gaps. Sources: {source_id, url, title, published_at, accessed_at, locator}. Dates use ISO-8601 with timezone; published_at may be null if unknown. Source IDs are local to each task and every reference must resolve in that task's sources. Copy inherited sources when citing them. Data published after research_cutoff cannot substantiate the run. Future event dates are allowed.

Instrument: {instrument_id, isin, symbol, name, asset_type, currency}. Copy assigned instruments exactly. Identifiers use ISIN, otherwise asset_type:currency:symbol (supplied holdings without symbol may use name). New candidates require a resolved symbol or ISIN; describe unresolved possibilities in deferred instead.

Fact: {fact_id, metric, value, unit, currency, period, basis, value_kind, source_ids, gap}. value is number/text, or null with a nonblank gap. currency is an ISO currency or null for nonmonetary metrics. period and basis are explicit; value_kind is actual/guidance/consensus/assumption. Facts with values need sources. Keep numeric values as decimal strings. Dates and qualifiers may be explained in metric/basis; do not mislabel observed values as point-in-time historical consensus.

Event: {event_id, title, scheduled_at, certainty, first_seen_at, changed_at, outcome, source_ids}. scheduled_at may be null; certainty is confirmed/estimated/unknown. outcome may be null until observed. Preserve existing records and original dates; changed_at reflects a substantive update only.

Exposure: {instrument_id, weight, as_of, source_ids}. weight is a decimal fraction from 0 to 1, as_of is the dated composition timestamp, source_ids must be nonempty. Include only documented fund constituents, each once; partial lists are explicitly incomplete.

Thesis: {thesis_id, claim, status, first_seen_at, changed_at, counterevidence, invalidation, source_ids}. status is new/supported/weakened/invalidated/uncertain. counterevidence is a text list. Preserve supplied IDs, first_seen_at and unchanged changed_at; retain invalidated records. New research theses use research_cutoff for first_seen_at and changed_at. Track supplied candidate hypotheses as uncertain if evidence is insufficient; do not promote them to supported theses. A new research thesis is not an assertion about the user's original purchase motivation.

## Payloads

- **market:** {schema_version, kind: "market", sources, context_markdown, candidates, deferred}. Each candidate is {instrument, hypothesis, risks, questions, source_ids}; risks/questions/deferred are text lists. At most eight unique candidates, each sourced. Coverage is input.selected (empty for this portfolio-independent scan).
- **instruments:** {schema_version, kind: "instruments", sources, items, hypotheses}. Each item is {instrument_id, instrument, content_markdown, facts, events, exposures, gaps}. hypotheses is a neutral text list; carry supplied candidate hypotheses into it. One item per assigned instrument.
- **valuation:** {schema_version, kind: "valuation", sources, items}. Each item is {instrument_id, health, valuation, thesis_change, content_markdown, theses, source_ids, gaps}. Health, valuation and thesis change are separate concise judgments with uncertainty. One item per assigned instrument.
- **risk:** {schema_version, kind: "risk", sources, items, calculations, findings}. Each item is {instrument_id, content_markdown, source_ids, gaps}. Copy input.calculations unchanged, then explain it and its limits. findings is a text list and covers portfolio-level risks including cash. One item per held instrument, even with sparse data.

## Follow-up and history

Read previous_state as historical evidence, never as fresh data. Only the assigned instrument subset is provided. Preserve its tracked events/theses. A follow-up contains questions and the original scope, new input_hash and current predecessor versions; return a full replacement. Never read sibling task files. The helper invalidates downstream tasks and allows only one follow-up round. No strategy-originated follow-up may target market.

## Strategy V2

The document payload stays Markdown V4. Use the strategy result in draft-contract.md with contract_version: 2. Follow-up requests use {task_id, questions}, not skill names. Allowed targets are holdings, candidates, valuation, risk and only when the core package is included. Copy the prepared evidence token; read all included Markdown and research_data. Existing plans/strategies are historical reasoning, not a way to reintroduce excluded research as current evidence.
