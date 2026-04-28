# Conformance Profiles

Contrix implementations declare testable profiles.

Initial profiles:

- `cx.profile.minimal_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.principal_server_repo_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.index_node.v1`
- `cx.profile.identity_registry.v1`
- `cx.profile.blob_node.v1`
- `cx.profile.enterprise_client.v1`
- `cx.profile.agent_runtime.v1`
- `cx.profile.applet_bridge.v1`

Conformance suites should include schema validation, signature verification, idempotency, reducer convergence, authorization, privacy regression, and unsupported-feature tests.

`cx.profile.principal_server.v1` MUST cover client sync (`POST /sync`), sync subscription, backfill, cursor stability, duplicate suppression, encrypted payload forwarding, federation destination service binding verification, and plaintext-visible service enforcement. Principal Servers MUST NOT forward non-E2EE private content or reversible derived plaintext to services absent from relevant DID delegation or Space policy `plaintext_visible_services`.

`cx.profile.index_node.v1` MUST cover reducer profile declaration, query reconstruction, authorization filtering, stale frontier reporting, wait-for sync tokens, and plaintext-visible declaration / policy enforcement when indexing private plaintext.

This draft also requires state/capability/redaction fixture families:

- State resolution: `state-resolution-conformance-vectors.md`
- Redaction: `redaction-conformance-vectors.md`
- Capability: `capability-conformance-vectors.md`
- Core sync/encoding vectors: `sync-conformance-vectors.md`, `encoding-conformance-vectors.md`

