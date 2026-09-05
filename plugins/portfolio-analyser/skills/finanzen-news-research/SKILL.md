---
name: finanzen-news-research
description: Read current finanzen.net news, create a sourced German market-news report, as a draft for the Portfolio Analyser. Use for finanzen.net news scans and news reports; do not use for portfolio recommendations or broad investment-opportunity screens.
---

# finanzen.net News Research

Create one self-contained German news report for the app's reports collection. Keep the scan independent of portfolio holdings; do not load positions or create portfolio briefings.

## Set the news window

Use the requested period, topics, regions, and report length. By default, cover the last 24 hours up to the invocation time, using `Europe/Berlin` and explicit start/end timestamps with UTC offsets. Scan market-moving company news, macroeconomics, interest rates, equities, ETFs, commodities, currencies, and major crypto assets where relevant news exists.

Aim for 6–10 distinct material developments unless the user specifies otherwise. Prioritize new information and market relevance over popularity. Do not fill a quiet day with older stories or silently extend the time window.

## Read and verify the news

Always browse current sources. Start at [finanzen.net News](https://www.finanzen.net/news/) and follow the relevant news-category or article links. Use domain-restricted search for `site:finanzen.net` when the feed is incomplete or inaccessible; search snippets are discovery aids, not sufficient evidence for the report.

Open the selected articles and capture their direct URLs, titles, publication/update timestamps, and credited authors or agencies when shown. Determine the date from the article, not an undated feed time or search-engine crawl date. Distinguish the event date from the publication date; include an older story only when a substantive update falls inside the requested window, and explain what changed. Mark unknown timestamps instead of inventing them, and exclude stories whose recency cannot be established from the current-news selection.

Consolidate duplicate coverage and repeated intraday updates into one development, using the latest substantive version available at the cutoff. Exclude advertisements, advertorials, affiliate promotions, and automated historical-return articles without a new material event. Attribute agency reporting, company releases, analyst opinions, and unconfirmed claims explicitly. Repetition of the same agency story is not independent confirmation.

Distinguish a potentially persistent change to earnings, financing, regulation, or instrument structure from a transient headline or price reaction. State what is actually new, the mechanism that could matter, the strongest relevant counterinterpretation, and whether follow-up evidence is needed. A new article about an old risk does not itself create urgency. Do not invent a durable effect where only a short-term reaction is observable.

Keep finanzen.net as the news source. Follow primary sources such as company releases, filings, central banks, or statistical agencies to verify material figures or resolve consequential uncertainty; cite these as supplementary evidence. Summarize only accessible content in your own words, link to the articles, and separate reported facts from your interpretation. Do not infer an unread article's contents or copy full articles.

If some articles cannot be read, continue with accessible evidence and describe the coverage gap. If access failures or unverifiable dates prevent establishing current coverage, report that limitation without publishing an empty or fabricated news report. A successfully checked quiet period may produce a short report stating that no material developments were found in the checked coverage; do not claim that no news exists anywhere.

## Write the report

Use a concise German Markdown report with:

- a title, research cutoff, exact news window, and coverage limitations;
- a short summary of the most important developments;
- one section per development with the verified news, publication/event timing, affected companies or markets, possible market significance, and material uncertainty;
- a short cross-market synthesis and concrete next events or data to monitor, where supported by the sources.

Place ordinary Markdown source links beside the claims they support, including a direct finanzen.net article link for every development. Include the credited source and article timestamp when available. Do not leave tool-internal citation markers in the stored Markdown.

Include tickers or ISINs only when verified and useful. Price moves need an observation time, currency or unit, and comparison basis; do not present article-time prices as live quotes. Describe market implications conditionally, without turning the report into personalized buy/sell instructions or unsupported price targets. Explicitly identify news-only evidence: one headline, investigation, analyst view, or ordinary daily price move is not by itself a portfolio trade trigger. Name prompt review only when a verified event and its consequences justify it; keep review urgency separate from trade execution.

## Return the draft

Read [the shared draft contract](../../references/draft-contract.md). Return the complete report with its exact news window and coverage limitations. Never access Portfolio Analyser MCP, publish, or invoke run-analysis yourself. Use supplied run/report IDs when orchestrated. Publication and read-back are the orchestrator's responsibility.
