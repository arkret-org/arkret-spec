# Contrix Machine-Executable Artifacts

This directory holds the canonical machine-readable outputs for Contrix v1:

- `schemas/`: JSON Schema contracts for core objects, Event Envelope payload classes, sync state, blob/media, push, identity, moderation, Agent Authority, and MIMI interop.
- `openapi/`: unified OpenAPI 3.1 service contract.
- `bindings/`: transport-neutral non-HTTP binding registry. Binding artifacts are generated or checked against `registry/operation-registry.json`.
- `fixtures/`: official conformance vectors for encoding, crypto signatures, Event Envelope negative validation, state resolution, redaction, capability, sync, federation, privacy/security, and MIMI interop.
- `profiles/`: implementation and deployment profile manifests.
- `registry/`: schema, ID kind, event-kind, operation, mirror, legacy-compatibility, and registry-index artifacts shared across machine outputs. `registry-manifest.json` is the index of this layer; `id-kind-registry.json` is the source of truth for `cx:<kind>:` typed ID prefixes and storage/wire boundary rules; `operation-registry.json` is the source of truth for canonical service operation IDs; `event-kind-registry.json` is the source of truth for standard `Event.kind` values and their `wire_scope` / `reducer_input` classification; `mirror-manifest.json` is the source of truth for `zh/` machine-artifact mirror paths.
- `lint_artifacts.py`: local consistency lint for registry-first artifact checks.
- `../tools/artifact_pipeline.py`: unified sync/check entrypoint for mirror drift, legacy guards, and registry lint.

The `artifacts/` tree is the canonical machine-readable source. Mirrored files under `zh/conformance/` and `zh/sync/` are derived copies and should be updated from `artifacts/`, not edited as an independent source of truth.

## Unified maintenance pipeline

Run from the repository root:

```sh
python tools/artifact_pipeline.py check
```

The unified pipeline runs three layers in order:

- zh mirror drift check derived from `mirror-manifest.json`
- removed legacy contract guard derived from `legacy-compatibility-policy.json`
- registry-first artifact lint from `artifacts/lint_artifacts.py`

The lint layer checks registry uniqueness, schema file and `$ref` existence, Event.kind coverage in `event-schema.json`, profile-to-test matrix references, OpenAPI and non-HTTP binding operation IDs against `operation-registry.json`, fixture references to event kinds / schemas / profiles / operations / typed ID kinds, crypto fixture canonical hashes, local Markdown link integrity, Markdown examples in `zh/`, deprecated Event.kind alias leakage, and `zh/` mirror drift for canonical schemas, fixtures, OpenAPI, and non-HTTP bindings. The same pipeline runs in `.github/workflows/artifact-lint.yml`.

## Mirror sync

To refresh the derived Chinese mirror files from canonical artifacts:

```sh
python tools/artifact_pipeline.py sync
```

The pipeline reads `artifacts/registry/mirror-manifest.json`, so new mirrored machine-artifact paths should be declared there instead of being hardcoded in multiple places.
