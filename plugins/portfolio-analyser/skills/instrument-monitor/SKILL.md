---
name: instrument-monitor
description: Manage the user's instrument watchlist and check held or watched instruments for material changes to their investment theses.
---

# Instrument monitoring

Read the requesting user's watchlist with `get_investment_monitoring` on their personal Trading connection. To add a requested instrument, resolve its identity and pass it as `watch` to `set_investment_monitoring`. To remove an explicit watch, pass its instrument ID as `remove`. If the list already matches the request, reuse it. Otherwise write only the requested watchlist change and read it back. A one-off research question or a discovery candidate creates no watch. When monitoring is active, it covers both explicit watches and current holdings with a positive value.

For a monitor run, use the package's [instrument dispatch](../../scripts/earnings_wake.mjs) (`dispatchInvestment`) or follow the same steps with native tools. Check `check_due_investment_events`, then claim ready work with `claim_due_investment_events` for the authenticated private destination. An idle result ends the run. A run reads the existing settings and leaves enrollment and the watchlist alone.

For a research claim follow [instrument event evidence](../../references/research/instrument-monitor.md) and submit the result and actual web trace with `complete_investment_check`. For a delivery claim, verify `prepare_investment_delivery` for that delivery ID and destination, deliver once, and record the verified receipt with `ack_investment_delivery`. Recover an uncertain send from that private chat before retrying. Check for further ready work after each completed claim so a new alert can be delivered in the same run. Report findings without changing the portfolio or placing trades. Earnings previews and results belong to the earnings workflow.
