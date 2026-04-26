# Gap Analysis

This document tracks implementation gaps that remain before Contrix New can be treated as a stable interoperable protocol.

It only describes the current protocol's implementation gaps. The Chinese draft is currently the leading source for detailed wording.

Priority gaps:

- P0: conformance test vectors for canonical JSON, event hashes, signatures, state resolution, redaction, capability checks, sync cursors, and Applet transactions.
- P0/P1: default HTTP binding OpenAPI plus equivalent mappings for gRPC, WebSocket/SSE, message queues, and P2P transports.
- P0: machine-verifiable schema registry for standard `cx.*` object and event types.
- P1: federation hardening, including service DID authentication, replay protection, cross-domain join, backfill, fork detection, and quarantine.
- P1: directory/search/preview behavior with authorization filtering and minimum disclosure.
- P1: moderation, abuse handling, appeals, server ACLs, and policy-list subscription schemas.
- P1: production deployment profiles for personal nodes, enterprise nodes, relays, E2EE clients, Applet bridges, media/SFU services, policy servers, and agent runtimes.
