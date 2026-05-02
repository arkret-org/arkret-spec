# Conformance Profiles

Contrix implementations declare testable profiles rather than claiming generic support.

## Implementation Profiles

- `cx.profile.minimal_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.enterprise_client.v1`
- `cx.profile.principal_server_repo_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.index_node.v1`
- `cx.profile.identity_registry.v1`
- `cx.profile.blob_node.v1`
- `cx.profile.push_gateway.v1`
- `cx.profile.applet_service.v1`
- `cx.profile.agent_runtime.v1`
- `cx.profile.mimi_interop.v1`

## Profile Requirements

`cx.profile.minimal_client.v1` MUST cover DID/handle resolution, service discovery, repo fetch, index query, event decode, cursor pagination, and standard error handling.

`cx.profile.full_client.v1` MUST add local reducer/cache, offline operation replay, Space bootstrap, invite accept/reject, read markers, notifications, blob transfer, and conflict UX.

`cx.profile.e2ee_client.v1` MUST add MLS state, KeyPackage claim/consume/revoke flows, MLS-bound application state root verification, epoch recovery, encrypted payload/attachment handling, minimal-metadata identity links when advertised, AAD visibility policy handling, revoked-device response, and fail-closed encrypted history behavior.

`cx.profile.principal_server_repo_api.v1` MUST cover submit/fetch history, idempotent writes, signature/schema validation, capability precheck, conflict reporting, and content-addressed blob reference validation.

`cx.profile.principal_server.v1` MUST cover client sync (`POST /sync`), sync subscription, backfill, cursor stability, duplicate suppression, encrypted payload forwarding, federation destination service binding verification, and plaintext-visible service enforcement. Principal Servers MUST NOT forward non-E2EE private content or reversible derived plaintext to services absent from the relevant DID delegation or Space policy `plaintext_visible_services`.

`cx.profile.index_node.v1` MUST cover reducer profile declaration, entity/relation/query reconstruction, authorization filtering, stale frontier reporting, wait-for sync tokens, and plaintext-visible declaration / policy enforcement when indexing private plaintext.

`cx.profile.identity_registry.v1` MUST cover DID resolve, DID log fetch, DID operation submit, inception-key validation, receipt publication, and method adapter metadata.

`cx.profile.blob_node.v1` MUST cover upload, download, HEAD metadata, SHA-256 verification, MIME metadata, range-aware authorization, asset privacy policy enforcement, and private blob anti-enumeration behavior.

`cx.profile.push_gateway.v1` MUST cover `register_device`, `unregister_device`, `notify`, minimized blind wakeup payloads, trusted service signature verification, invalid token cleanup, and `rejected[]` reporting. Push gateways MUST NOT ingest plaintext message bodies or treat delivery receipts as read receipts.

`cx.profile.applet_service.v1` MUST cover signed registration, namespace declaration, ping/describe, transaction push, idempotency, actor/space lookup, protocol metadata, accountability metadata, capability enforcement, HTTP message signature verification, and external event deduplication.

`cx.profile.mimi_interop.v1` MUST cover pinned MIMI draft version discovery, `cx.mimi.room_binding`, the MIMI provider endpoint surface, KeyPackage claim lifecycle, MIMI-to-Contrix and Contrix-to-MIMI content mapping, room policy component mapping, private identifier queries, consent isolation, E2EE abuse report franking, asset proxy download policy, and unsupported-draft fail-closed behavior. It MUST NOT replace `space_id`, DID, HLC/event hash, Contrix auth refs, capability checks, MLS epoch checks, or Space policy with MIMI identifiers or provider metadata.

`cx.profile.enterprise_client.v1` MUST cover OIDC / SSO gateway session grants, device inventory, admin-triggered device revocation, auditable E2EE warning UI, compliance audit display, and managed update policy.

`cx.profile.agent_runtime.v1` MUST cover delegated identity, explicit capability grants, scoped action execution, run logs, memory write policy, accountability metadata, and revocation / kill-switch checks.

## Deployment Profiles

The following release/acceptance profiles define deployment shape rather than a single runtime role:

- `cx.profile.personal_node.v1`
- `cx.profile.small_team.v1`
- `cx.profile.organization.v1`
- `cx.profile.high_security_organization.v1`
- `cx.profile.isolated_sovereign_network.v1`

`cx.profile.personal_node.v1` MUST cover co-located principal server/repo/sync/index/blob services, a minimum local admin surface, and local backup/recovery.

`cx.profile.small_team.v1` MUST cover shared Spaces, basic directory and push, moderation queue, and snapshot/backfill.

`cx.profile.organization.v1` MUST cover organization DID delegation, OIDC/account integration, admin account lifecycle, and audit export.

`cx.profile.high_security_organization.v1` MUST cover service DID allowlists, auditable E2EE or controlled plaintext-visible boundaries, break-glass audit, server ACL, and quarantine.

`cx.profile.isolated_sovereign_network.v1` MUST cover private registry/witness infrastructure, closed federation by default, import/export review, and allowlisted external services/applets.

## Fixture Families

Conformance suites should include schema validation, signature verification, idempotency, reducer convergence, authorization, privacy regression, unsupported-feature tests, unknown-field preservation tests, and these fixture families:

- State resolution: `state-resolution-conformance-vectors.md`
- Redaction: `redaction-conformance-vectors.md`
- Capability: `capability-conformance-vectors.md`
- Core sync/encoding vectors: `sync-conformance-vectors.md`, `encoding-conformance-vectors.md`
- Schema evolution: unknown non-critical fields preserved through hash verification, storage, federation forwarding, and backfill; unknown critical features fail closed.
- E2EE hardening: KeyPackage single-use, MLS-bound state root mismatch, minimal-metadata identity link, AAD visibility, E2EE franking report
- MIMI interop: provider directory draft pinning, room binding projection, content roundtrip, identifier query privacy, consent isolation, proxy download policy, unsupported-draft fail-closed
- Machine-readable fixtures: `fixtures/*.json`
