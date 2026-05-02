# Contrix v1 protocol improvement TODOs

This file tracks structural protocol fixes raised during the May 2026 technical review. Status values:

- `done`: implemented in this repository.
- `next`: should be handled before calling v1 stable.
- `later`: useful, but not blocking the next v1 draft.

## P0

| Status | Item | Target |
| --- | --- | --- |
| done | Define layered startup profiles: chat-only, kanban-only, and minimal federation, so "Contrix v1" is not synonymous with full product scope. | `zh/conformance/conformance-profiles.md`, `artifacts/profiles/conformance-profiles.json` |
| done | Add v1 scalability constraints with concrete upper bounds for sync pages, federation batches, auth refs, delegation depth, conflict sets, and object graph expansion. | `zh/conformance/scalability-constraints.md` |
| done | Make capability snapshot / bitmap cache mandatory for high-frequency write paths and define invalidation semantics. | `zh/authz/capabilities.md` |
| done | Resolve the Card/Board/List contradiction: Card can exist outside a Board, while Board position is represented by canonical position edges and projected fields. | `zh/models/*`, `zh/conformance/schemas/card.schema.json`, `artifacts/schemas/card.schema.json` |
| done | Add deterministic state-resolution complexity limits and snapshot fallback thresholds. | `zh/authz/event-auth-state-resolution.md` |
| next | Produce executable conformance fixtures for the new profile split and scalability limits. | `artifacts/fixtures/*`, conformance runner |

## P1

| Status | Item | Target |
| --- | --- | --- |
| done | Clarify Canonical Operation vs Operation Envelope vs Event Envelope so the wire format and reducer input are not confused. | `zh/models/data-structures.md`, `zh/sync/operations-sync.md` |
| done | Split View semantics into Shared View and Personal View preference paths. | `zh/models/views.md`, `zh/models/data-structures.md` |
| done | Make MLS state binding cheaper for the base E2EE profile and move full binding to an explicit hardening profile. | `zh/crypto-media/encryption-and-audit.md` |
| next | Add recovery playbooks for long-lived `soft_failed`, partial federation acceptance, index/repo divergence, and network partition healing. | `zh/guides/recovery.md` |
| next | Tighten schema evolution: semantic versioning, reducer profile migration, and encrypted unknown-field rules. | `zh/conformance/schema-registry.md`, `zh/models/object-model-standard.md` |
| next | Add migration/adoption guide from personal node to small team to organization to sovereign deployment. | `zh/guides/adoption-path.md` |

## P2

| Status | Item | Target |
| --- | --- | --- |
| later | Decide whether `did:uuid` remains a MUST in public v1 or moves to a native/sovereign profile while `did:web` / `did:key` become baseline. | `zh/identity/identity-did.md` |
| later | Define a non-TEE auditable E2EE fallback profile and explicitly label weaker guarantees. | `zh/crypto-media/encryption-and-audit.md` |
| later | Archive or regenerate stale English docs after the Chinese/artifacts source stabilizes. | `en/`, `README.md` |
| later | Add UX guidance for drag conflicts: optimistic update, CAS conflict, stale reorder handling, and recovery UI. | `zh/models/views.md`, implementation guide |
