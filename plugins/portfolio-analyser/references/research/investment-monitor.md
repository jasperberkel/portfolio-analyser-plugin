# Material investment events

Investigate only the assigned public instrument identities and the fixed `research_cutoff`. Cover every assigned identity once in `researched`; a failed source search remains an explicit gap. Current holdings amounts and allocation targets are not supplied and must not be sent to search providers.

Look for dated primary evidence of guidance changes, dilution/capital changes, accounting corrections, refinancing/solvency issues, governance changes, material fund/product changes or a change to the operating thesis. A price breakout, volume spike or price decline alone is not a material thesis event. Treat headlines as leads, open the source, and separate `observation`, `thesis_effect` and `review_reason`. Use German prose and name the uncertainty that affects the assessment. Do not infer valuation attractiveness from price movement.

Read `known_events` as historical evidence. Reuse each known `event_key` for the same underlying event, including corrections; do not create a key from today's access time or a rewritten title. New keys identify a stable issuer event or announcement. Return unchanged observations only when needed to establish continuity; the service deduplicates source revisions and unchanged observations. A correction states what changed in the underlying facts. Syndicated versions of the same announcement are not separate events.

Each event uses the supplied JSON schema: instrument ID, event key, allowed kind, title, observation, thesis effect, review reason and dated source. Cite only a source actually opened during this claim, retaining its true observation time. Day-only publications require `published_on` and `publication_zone`; the whole publication day must precede the cutoff. Unknown publication dates cannot establish a new material event. Return `events: []` for a quiet check and explain material access gaps.

The model produces evidence and a reason to review. It never submits an order, changes an allocation plan or treats the review date as an execution deadline. An event report is separate from a completed portfolio analysis. Existing atomically published analysis runs and their required research coverage remain unchanged.

Use supplied `theses` as the dated research baseline and identify which supported assumption changed. They are historical, not new evidence. Without a prior thesis, explain the supported business/product implication and state that no prior investment assumption was supplied. Do not invent a purchase motive.

The private chat opens with `review_reason`. Write one short German sentence naming what is worth reconsidering or watching. In `observation` give the decisive new fact, and in `thesis_effect` explain its consequence. Keep any condition in the same sentence as the suggestion.
