# Orchestration contract V2

The plugin-root workflow.json explicitly declares six tasks: market, holdings, candidates, valuation, risk and strategy. Four research skills yield five research tasks and four published reports. V1 stays available only for older clients/fixtures; this installed plugin requires a V2 server. Adding a skill does not alter the workflow. Graph extensions require a coordinated contract change.

## Local helper commands

Use Python 3 and scripts/workflow.py. It validates and stores state, never launches models or calls providers.

1. `discover` returns the exact workflow. Pass it to get_analysis_context. If existing_run exists, stop and use its receipt.
2. `init <run-dir> <context.json>` creates a unique state and ready inputs. Keep run directories ignored and private. `status <run-dir>` returns ready_tasks, attempts and task states.
3. `start <run-dir> <task_id>` marks a ready task running and returns its scoped input. Spawn a fresh host Research-Agent with only role/skill/input/output paths, no parent history. Respect host capacity. Failed tasks may be started once more with identical input.
4. `collect <run-dir> <task_id>` validates result.json and unblocks successors; `fail` records interruption. Inspect status after every completion; launch new ready tasks while other branches continue. Empty instrument tasks complete without an agent. Stop after the second failure and publish nothing.
5. When every research task completes, `draft <run-dir>` revalidates all predecessor hashes and creates the five-task packet including research_cutoff. Call prepare_strategy_context and save its response. `prepared <run-dir> <response.json>` materializes strategy input.
6. Run a fresh Strategy-Agent and `strategy <run-dir> <result.json>`. A single needs_research response may target included holdings/candidates/valuation/risk tasks. It invalidates their transitive descendants and strategy, rebuilds inputs on readiness and retains unaffected work. Repeat steps 3–6 once. No feedback to market.
7. `publication <run-dir>` freezes the packet after complete strategy. Call publish_analysis_run with exactly those arguments. Transport uncertainty permits one identical retry, never a new run ID. Stale inputs/day/version or validation errors stop. Read back every receipt ID and verify complete content.

The server independently reconstructs scopes, inputs and predecessor hashes. Both sides use the same pure research contract; a parity test protects the vendored copy. The server aggregates holdings+candidates deterministically into one instrument report with namespaced source IDs. No app writes occur before the complete atomic publication.

## Context and history

R1 receives only its own independent prior state. R2/R3 receive assigned instrument data without portfolio amounts/targets; these scopes still constitute private derived data. R4 receives the supplied portfolio, existing plan and deterministic exposure calculations. Workers never inspect sibling directories or the app. History is explicitly historical and source timestamps do not change on a new run.

One research.core setting includes/excludes the four core reports as a package, not task execution. Other independent reports remain individually selectable. An excluded package contributes neither Markdown nor structured data to strategy. Old report types remain archived after the first V2 run. The full included context must fit host and transport limits; never silently truncate.

All envelope, typed payload and strategy output rules are in [research-contract-v2.md](research-contract-v2.md) and [draft-contract.md](draft-contract.md). Provider-specific instructions are only in [research/connectors.md](research/connectors.md). No new provider connections are part of the default release.
