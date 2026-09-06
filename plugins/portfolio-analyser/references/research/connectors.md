# Research data access

This is the single provider/tool routing reference for all research skills. It is an instruction file, not an executable adapter. Read it before collecting data. Source citations retain actual provider names.

## Current configuration

Public sources are the default. No premium financial connector is required or installed by this workflow. Use the host's available web search/fetch tools to find and read primary issuer filings, investor-relations releases, fund issuer holdings/product documents, central-bank/statistical publications and official protocol records. Reputable independent reporting may establish contrary evidence. The app's portfolio bridge is not a research data provider and remains orchestrator-only.

## Optional native MCP connections

When a connection has been configured and authenticated in the host, inspect its actually available tools and their input schemas. Choose by required dataset, coverage, period and access rights, not merely the presence of a server. Call its native tools directly. Do not invent tool names, use the app bridge to proxy it, install software, buy access or create API credential scripts.

Maintain provider-specific instructions only in this section. Example future mapping (not an active dependency): Daloopa can identify companies with `discover_companies`, discover series with `discover_company_series`, retrieve values with `get_company_fundamentals`, and retrieve documents with `discover_company_documents` / `get_document_content`. Verify the connected server exposes these tools and inspect their schemas before use. This example does not guarantee a licensed dataset or host access.

For a future provider add: supported datasets/assets; configured server and actual tool names; minimal call sequence; identifier/period/unit conventions; limitations and fallback. Keep connection URLs and host connection settings in native MCP configuration; never put credentials here. Update Claude/Codex research-profile tool permissions during connector setup. A Markdown instruction cannot grant runtime tool access. Keep optional providers optional in dependency declarations.

## Fallback and normalization

If absent, unauthorized, unsupported, or missing the required data, use public primary sources. For a transient failure allow one retry, then switch source or state the gap. Authentication and subscriptions are a later setup task, not part of a research run.

Inspect the returned schema, extract only decision-relevant evidence into the research contract, retain URLs/locators and date each figure. Never equate fiscal periods, currencies, adjusted/unadjusted numbers or guidance/consensus. Missing data remain null with a reason; no fictional zeros. For conflicts inspect definitions and primary evidence. A successful schema check does not verify a source's truth.
