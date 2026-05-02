# Contrix Machine-Executable Artifacts

This directory holds the canonical machine-readable outputs referenced by `_todos.md`:

- `schemas/`: JSON Schema contracts for core objects, sync state, blob/media, push, identity, and MIMI interop.
- `openapi/`: unified OpenAPI 3.1 service contract.
- `bindings/`: transport-neutral non-HTTP binding registry. Binding artifacts are generated or checked against `registry/operation-registry.json`.
- `fixtures/`: official conformance vectors for encoding, state resolution, redaction, capability, sync, federation, privacy/security, and MIMI interop.
- `profiles/`: implementation and deployment profile manifests.
- `registry/`: schema and operation registries shared across artifacts. `operation-registry.json` is the source of truth for canonical service operation IDs.
