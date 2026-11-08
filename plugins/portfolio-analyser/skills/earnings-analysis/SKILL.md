---
name: earnings-analysis
description: Research earnings previews, actual results and revisions for a single stock. Use for one-off requests, a scoped instrument dossier or a leased earnings task.
---

# Quartalszahlen

Work only on the supplied issuer, fiscal period, phase and cutoff. Follow [earnings](../../references/research/earnings.md), [events](../../references/research/events.md), [data access](../../references/research/connectors.md) and [evidence](../../references/research/evidence.md). Receive any personal context from the caller. Return evidence and a draft. This skill never enrolls, watches, schedules, delivers, publishes a portfolio plan, or calls instrument-research.

Reuse supplied compatible evidence per metric, source version, currency, basis, period and cutoff. Keep original publication and observation times. Investigate only missing or changed facts. If the entire matching version is available, use it without another source fetch.

Use the host's isolated public search and document-open tools. Confirm issuer and fiscal period on the issuer or regulator site. An empty configured packet initiates discovery. Look up dated outside analyst expectations and competing views independently for preview; look up post-release participant assessments and their reasons for review. Follow promising leads to the documents. Search snippets alone cannot support claims. Exclude information not yet public at the requested cutoff. Record dates, publisher/author, locator, uncertainties and unsuccessful searches. Respect source access terms, robots and paywalls. Never send holdings, account identifiers or other personal context in search queries.

For a preview, distinguish dated analyst estimates, management guidance and assumptions. Cite each figure, timestamp, aggregation basis and analyst coverage when available. Identify missing consensus, the downside/upside drivers and conditional impact. A partial release closes the expectation window for disclosed figures. Do not reconstruct a preview retrospectively.

For actuals, verify the document identifies this issuer and fiscal period and contains an actual release. A calendar, conference call, filing title or change of URL alone is insufficient. Distinguish preliminary figures, full release, amendments and forward guidance. For an EDGAR 8-K read the results exhibit and cite the exact exhibit/locator on its facts. The envelope cites the discovered filing. Include operating drivers. Include EPS share class and dilution basis. For the review compare compatible values with the frozen preview. Attribute guidance changes to management. Give positive, neutral and negative possible reactions with uncertainty and time horizon. An observed market move needs its own dated source and interval. With holdings explain hold, reduce and increase conditions against thesis, valuation and constraints. Without holdings explain continued observation and potential entry conditions.

For a leased task return the exact fields in the [monitor contract](../../references/research/earnings-monitor.md). For a one-off, return the German analysis directly with sources and explicit gaps. No account write, notification or order.
