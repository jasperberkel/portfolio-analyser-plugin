# Event tracking

Adapted from catalyst-calendar; see ../anthropic-sources.md.

Verify issuer/protocol dates. Distinguish confirmed, estimated and unknown; record timezone or a precise uncertainty statement. Keep stable event IDs and first_seen_at. Change changed_at only for a substantive date/status/outcome change. Preserve past events and record their observed outcomes rather than rolling dates forward. Upcoming dates may exceed research_cutoff; evidence supporting them must have been available at cutoff. No calendar integrations, notifications or trading instructions.
