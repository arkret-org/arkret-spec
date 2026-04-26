# Gap Analysis

This document tracks the remaining gaps between the legacy `contrix-spec` and Contrix New.

Contrix New intentionally does not inherit the Matrix-style room/homeserver root model. The parts worth carrying forward are implementation-level details: API schemas, event schemas, canonical encoding, device/key management, media handling, federation transactions, moderation flows, Applet bridges, and conformance profiles.

Priority gaps:

- P0: request/response schemas for identity, repo, relay, index, blob, and authz.
- P0: standard object/event schema registry.
- P0: canonical JSON, IDs, hashes, signatures, cursors, HLC, and rank encoding.
- P0: conformance profiles and test vectors.
- P1: media/blob metadata, thumbnails, authenticated media, encrypted attachments.
- P1: federation wire transactions, cross-domain joins, backfill authorization, fork detection.
- P1: Applet registration, namespace, transaction, query, and protocol metadata schemas.
- P1: directory/search, moderation, private account state, read markers, notifications.

The Chinese draft is currently the leading source for detailed wording.
