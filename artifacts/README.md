# Artifacts

`artifacts/` holds the machine-readable protocol contract for the Contrix spec.

## Canonical registry sources

- `artifacts/registry/contract-catalog.json`: canonical source for the generated Event.kind, schema, typed-ID, and operation registries.
- `artifacts/registry/error-code-registry.json`: canonical error code registry.
- `artifacts/registry/legacy-compatibility-policy.json`: canonical registry of removed or transitional contract families.
- `artifacts/registry/mirror-manifest.json`: canonical declaration of artifact -> `zh/` mirror mappings.
- `artifacts/registry/registry-manifest.json`: canonical index of every machine-readable registry file under `artifacts/registry/`.

## Generated registry views

These files are derived from `artifacts/registry/contract-catalog.json` and must not be edited directly.

- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/operation-registry.json`

## Unified maintenance pipeline

Use one entrypoint for generation, mirror sync, and contract checks.

```bash
python tools/artifact_pipeline.py generate
python tools/artifact_pipeline.py sync
python tools/artifact_pipeline.py check
```

`check` performs three layers in one pass:

- generated registry drift detection against `contract-catalog.json`
- legacy contract reintroduction guard derived from `legacy-compatibility-policy.json`
- registry-first artifact lint from `artifacts/lint_artifacts.py`, including mirror drift and Markdown/link checks

`generate` / `sync` / `check` also print:

- forbidden pattern summary derived from `legacy-compatibility-policy.json`
- profile summary derived from `artifacts/profiles/conformance-profiles.json`
- registry diff status for generated registry views and generated Markdown inventories

CI runs the same entrypoint through `.github/workflows/artifact-lint.yml`.
