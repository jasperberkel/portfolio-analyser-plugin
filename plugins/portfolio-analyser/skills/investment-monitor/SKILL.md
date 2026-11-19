---
name: investment-monitor
description: Manage explicitly requested personal monitoring of material changes to long-term investment theses, including holdings and verified watch instruments. One-off research does not subscribe.
---

# Investment monitoring

Read `get_investment_monitoring` through the requesting person's private portfolio connection. On an explicit monitoring request, use `set_investment_monitoring`: enable the account, add a resolved instrument with its existing contract identity as `watch`, or remove its explicit watch by instrument ID. Enabled monitoring covers current positive holdings and explicit watches; discovered candidates are not subscriptions. Default interval is 24 hours. Change cadence only when requested, within the supported 6–168 hours. Disabling cancels pending messages. Read back the settings.

Thomas uses the package's existing personal wake. For first enrollment bind `bind_personal_wake({"package":"portfolio-analyser"})` to the authenticated requester's private conversation. Other hosts need an authorized personal schedule and receipt-backed delivery; do not claim background monitoring without those capabilities. No new subscription or schedule follows from a one-off question, an import or a new candidate.

For a leased research task read [investment event evidence](../../references/research/investment-monitor.md). The package runner handles claims, retries and delivery. Never invoke broker tools, change targets, or execute an investment from a monitoring event. Earnings previews/results retain their existing earnings workflow.
