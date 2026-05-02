# Contrix Machine-Executable Artifacts

This directory holds the canonical machine-readable outputs for Contrix v1:

- `schemas/`: JSON Schema contracts for core objects, Event Envelope payload classes, sync state, blob/media, push, identity, moderation, Agent Authority, and MIMI interop.
- `openapi/`: unified OpenAPI 3.1 service contract.
- `bindings/`: transport-neutral non-HTTP binding registry. Binding artifacts are generated or checked against `registry/operation-registry.json`.
- `fixtures/`: official conformance vectors for encoding, crypto signatures, Event Envelope negative validation, state resolution, redaction, capability, sync, federation, privacy/security, and MIMI interop.
- `profiles/`: implementation and deployment profile manifests.
- `registry/`: schema, ID kind, event-kind, and operation registries shared across artifacts. `id-kind-registry.json` is the source of truth for `cx:<kind>:` typed ID prefixes and storage/wire boundary rules; `operation-registry.json` is the source of truth for canonical service operation IDs; `event-kind-registry.json` is the source of truth for standard `Event.kind` values and their `wire_scope` / `reducer_input` classification.
- `lint_artifacts.py`: local consistency lint for registry-first artifact checks.

## Consistency lint

Run from the repository root:

```sh
python artifacts/lint_artifacts.py
```

The lint checks registry uniqueness, schema file and `$ref` existence, Event.kind coverage in `event-schema.json`, profile-to-test matrix references, OpenAPI and non-HTTP binding operation IDs against `operation-registry.json`, fixture references to event kinds / schemas / profiles / operations / typed ID kinds, crypto fixture canonical hashes, Markdown examples in `zh/`, deprecated Event.kind alias leakage, and `zh/` mirror drift for canonical schemas, fixtures, OpenAPI, and non-HTTP bindings. The same command runs in `.github/workflows/artifact-lint.yml`.
