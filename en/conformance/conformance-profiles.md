# Conformance Profiles

Contrix implementations declare testable profiles.

Initial profiles:

- `cx.profile.minimal_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.repo_node.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.index_node.v1`
- `cx.profile.identity_registry.v1`
- `cx.profile.blob_node.v1`
- `cx.profile.enterprise_client.v1`
- `cx.profile.agent_runtime.v1`
- `cx.profile.applet_bridge.v1`

Conformance suites should include schema validation, signature verification, idempotency, reducer convergence, authorization, privacy regression, and unsupported-feature tests.

This draft also requires state/capability/redaction fixture families:

- State resolution: `state-resolution-conformance-vectors.md`
- Redaction: `redaction-conformance-vectors.md`
- Capability: `capability-conformance-vectors.md`
- Core sync/encoding vectors: `sync-conformance-vectors.md`, `encoding-conformance-vectors.md`

