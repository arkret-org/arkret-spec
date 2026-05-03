# Contrix Spec

- 中文版本: [zh/README.md](./zh/README.md)
- English version: not currently published in this repository. Until regenerated, treat `zh/` plus `artifacts/` as the only maintained v1 source.

## Structure

Repository layout is intentionally summarized instead of duplicating a full file tree:

- `artifacts/`: canonical machine-readable v1 contracts, registries, fixtures, OpenAPI, and mirror manifests.
- `zh/`: maintained Chinese normative text plus `zh/conformance/` and `zh/sync/` mirror copies derived from `artifacts/`.
- `.github/workflows/`: CI entrypoints for artifact lint and drift guards.
- `tools/`: repository maintenance scripts such as mirror sync and legacy contract guards.

The Chinese specification under `zh/` is the leading normative text for Contrix v1. `artifacts/` contains machine-readable registries, schemas, OpenAPI descriptions, and fixtures derived from that normative text.

For v1 interoperability, only active entries referenced by `artifacts/registry/*` and `artifacts/profiles/*` are normative machine contracts. Compatibility files kept on disk during model migration do not become active wire contract merely because they still exist in the repository.

Any drift between `zh/` and generated artifacts is a specification bug. Until regenerated artifacts are brought back into sync, implementations MUST follow the Chinese normative text plus the active machine registries, and MUST NOT treat stale legacy compatibility files as the source of truth.

## Legacy contract status (2026-05-03)

The active v1 wire contract no longer includes legacy `subject` / `room` / `card` typed IDs, schema IDs, or the removed subject/room/card event families.

Normative references:

- `artifacts/registry/legacy-compatibility-policy.json`
- `zh/guides/legacy-subject-room-card-to-flow-migration.md`

Artifact maintenance pipeline:

- `python tools/artifact_pipeline.py generate`
- `python tools/artifact_pipeline.py sync`
- `python tools/artifact_pipeline.py check`
- `.github/workflows/artifact-lint.yml`
