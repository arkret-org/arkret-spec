# Gap Analysis

This document tracks implementation gaps that remain before Contrix can be treated as a stable interoperable protocol.

It only describes the current protocol's implementation gaps. The Chinese draft is currently the leading source for detailed wording.

Priority gaps:

- P0: conformance test vectors for canonical JSON, event hashes, signatures, state resolution, redaction, capability checks, sync cursors, and Applet transactions.
- P0/P1: executable OpenAPI for the default HTTP binding, including the common error envelope, security schemes without query-string auth, media headers, `404 unrecognized_endpoint`, `405 method_not_allowed`, and `429 Retry-After`; plus equivalent mappings for gRPC, WebSocket/SSE, message queues, and P2P transports.
- P0: machine-verifiable schema registry for standard `cx.*` object and event types.
- P1: federation hardening conformance vectors, including destination binding, canonical request hash replay protection, cross-domain join, backfill, fork detection, quarantine, and snapshot-assisted bootstrap.
- P1: directory/search/preview behavior with authorization filtering and minimum disclosure.
- P1: moderation, abuse handling, appeals, server ACLs, and policy-list subscription schemas.
- P1: production deployment profiles for personal nodes, enterprise nodes, Principal Servers, E2EE clients, Applet bridges, media/SFU services, policy servers, and agent runtimes.

The protocol text now covers REST safety conventions, authenticated media access, media response headers, redirect boundaries, and federation destination binding. Remaining work is primarily executable schema, OpenAPI generation, and conformance fixtures.

