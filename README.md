# Contrix Spec

- 中文版本: [zh/README.md](./zh/README.md)
- English version: [en/README.md](./en/README.md)（当前英文翻译在 2026-05 对象模型重构后已标记为 stale；以 `zh/` 与 `artifacts/` 为准）

## Structure

```text
contrix-spec/
  artifacts/
    README.md
    bindings/
      non-http-bindings.yaml
    fixtures/
      capability-fixture.json
      crypto-signature-fixture.json
      encoding-fixture.json
      event-envelope-negative-fixture.json
      federation-fixture.json
      privacy-security-fixture.json
      redaction-fixture.json
      state-resolution-fixture.json
      sync-fixture.json
    openapi/
      contrix-service-api.openapi.yaml
    profiles/
      conformance-profiles.json
    registry/
      error-code-registry.json
      event-kind-registry.json
      id-kind-registry.json
      operation-registry.json
      schema-registry.json
    schemas/
      *.schema.json
  zh/
    README.md
    spec-map.md
    guides/
      reference-implementation-guide.md
    overview/
      architecture.md
      matrix-core-differences.md
      design-questions.md
      gap-analysis.md
      glossary.md
    identity/
      identity-did.md
      identity-handles.md
      key-management.md
      progressive-disclosure.md
      tsp-integration.md
    models/
      object-model-core.md
      object-model-standard.md
      data-structures.md
      conversation-model.md
      views.md
      content-types.md
      space-hierarchy.md
    authz/
      capabilities.md
      grant-constraint-schema.md
      event-auth-state-resolution.md
      policy-server.md
      moderation.md
      account-lifecycle.md
    sync/
      operations-sync.md
      client-sync.md
      service-surface.md
      service-http-binding.md
      service-api-schema.md
      api-conventions.md
      transport-bindings.md
      federation.md
      federation-wire.md
      sovereign-deployment.md
      third-party-invites.md
    discovery/
      discovery-directory.md
      profiles-presence.md
      client-preferences.md
      push-notifications.md
      read-receipts.md
      read-notification-schema.md
    crypto-media/
      device-crypto-verification.md
      devices-and-auth.md
      encryption-and-audit.md
      media-and-blob.md
      webrtc-signaling.md
    extensions/
      applet-integration.md
      applet-schema.md
      agent-protocol-interop.md
      mimi-interop.md
    conformance/
      README.md
      fixtures/
        *.json
      schemas/
        *.json
      encoding.md
      encoding-conformance-vectors.md
      cursor-test-vectors.md
      hlc-test-vectors.md
      snapshot-schema.md
      schema-registry.md
      query-schema.md
      state-resolution-conformance-vectors.md
      redaction-conformance-vectors.md
      capability-conformance-vectors.md
      conformance-suite.md
      conformance-profiles.md
      sync-conformance-vectors.md
    security/
      server-threat-model.md
  en/
    README.md
    spec-map.md
    guides/
      reference-implementation-guide.md
    overview/
      architecture.md
      matrix-core-differences.md
      design-questions.md
      gap-analysis.md
      glossary.md
    identity/
      identity-did.md
      identity-handles.md
      key-management.md
      progressive-disclosure.md
      tsp-integration.md
    models/
      object-model-core.md
      object-model-standard.md
      data-structures.md
      conversation-model.md
      views.md
      content-types.md
      space-hierarchy.md
    authz/
      capabilities.md
      grant-constraint-schema.md
      event-auth-state-resolution.md
      policy-server.md
      moderation.md
      account-lifecycle.md
    sync/
      operations-sync.md
      client-sync.md
      service-surface.md
      service-http-binding.md
      service-api-schema.md
      api-conventions.md
      transport-bindings.md
      federation.md
      federation-wire.md
      sovereign-deployment.md
      third-party-invites.md
    discovery/
      discovery-directory.md
      profiles-presence.md
      client-preferences.md
      push-notifications.md
      read-receipts.md
      read-notification-schema.md
    crypto-media/
      device-crypto-verification.md
      devices-and-auth.md
      encryption-and-audit.md
      media-and-blob.md
      webrtc-signaling.md
    extensions/
      applet-integration.md
      applet-schema.md
      agent-protocol-interop.md
      mimi-interop.md
    conformance/
      README.md
      fixtures/
        *.json
      schemas/
        *.json
      encoding.md
      encoding-conformance-vectors.md
      cursor-test-vectors.md
      hlc-test-vectors.md
      snapshot-schema.md
      schema-registry.md
      query-schema.md
      state-resolution-conformance-vectors.md
      redaction-conformance-vectors.md
      capability-conformance-vectors.md
      conformance-suite.md
      conformance-profiles.md
      sync-conformance-vectors.md
    security/
      server-threat-model.md
```

The Chinese specification under `zh/` is the leading normative text for Contrix v1. `artifacts/` contains machine-readable registries, schemas, OpenAPI descriptions, and fixtures derived from that normative text.

For v1 interoperability, only active entries referenced by `artifacts/registry/*` and `artifacts/profiles/*` are normative machine contracts. Compatibility files kept on disk during model migration do not become active wire contract merely because they still exist in the repository.

Any drift between `zh/` and generated artifacts is a specification bug. Until regenerated artifacts are brought back into sync, implementations MUST follow the Chinese normative text plus the active machine registries, and MUST NOT treat stale legacy compatibility files as the source of truth.

## Legacy contract status (2026-05-03)

The active v1 wire contract no longer includes `subject` / `room` / `card` typed IDs, schema IDs, or `cx.subject.*` / `cx.room.*` / `cx.card.*` event kinds.

Normative references:

- `artifacts/registry/legacy-compatibility-policy.json`
- `zh/guides/legacy-subject-room-card-to-flow-migration.md`

CI guard:

- `tools/check_no_legacy_contracts.py`
- `.github/workflows/artifact-lint.yml`
