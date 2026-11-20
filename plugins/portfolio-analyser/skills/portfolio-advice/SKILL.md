---
name: portfolio-advice
description: Show saved personal investment ideas and portfolio recommendations. Explain an earlier suggestion or earnings alert when asked “Warum hast du das empfohlen?”.
---

# Portfolio advice

Use the requesting user's personal portfolio connection. This is a read of the saved advice. A request for a fresh portfolio analysis uses [run-analysis](../run-analysis/SKILL.md).

For current suggestions read `get_dashboard_briefing()`. It contains the published strategy, its plan, its original holdings and the reports actually used. Check `get_current_positions()` before presenting an amount or allocation as current. When the snapshot changed or a time-sensitive condition has expired, identify the suggestion as historical. Avoid carrying an old purchase, sale or amount into today's advice. If there is no saved strategy, say so and explain that a portfolio analysis can produce the first suggestion. A researched candidate becomes a proposed purchase only when the strategy selects and funds it.

## Chat answer

Lead with the most useful supported action and its decisive reason, in plain German. Include any condition needed to act safely, such as selling another position first or preserving a cash reserve. Mention a promising candidate as an idea to watch, with the observation that would make it worth revisiting. Add another idea only if it materially changes the user's choices. If keeping the portfolio as it is makes sense, say why. Keep the first answer to a short paragraph or a few brief bullets. Retain the full evidence and other considered candidates in the saved reports.

## A question about an earlier message

Identify the instrument, reporting period and original recommendation from the conversation. For a portfolio suggestion use the original strategy ID with `get_dashboard_briefing(id=...)`. If the ID is missing, use `list_analyses(analysis_type="portfolio.strategy")` and match the dated strategy to the cited suggestion. Explain its decisive evidence, strongest counterargument or review trigger as relevant, linking the primary source. Keep later developments dated separately.

For a quarterly alert resolve the issuer with `list_earnings_tracking` when needed, then use `get_earnings_evidence(issuer_key=...)`. Match the original period and document version. For a material-event alert use its observation and linked primary source. Say when the original basis cannot be verified. Ask a short identifying question only when the message remains ambiguous. A request for reasons leaves subscriptions, portfolio plans and schedules alone.
