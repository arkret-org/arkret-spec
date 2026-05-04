# Contrix Spec

- Chinese version: [zh/README.md](./zh/README.md)
- English version: not currently published in this repository. Until regenerated, treat `zh/` plus `artifacts/` as the only maintained v1 source.

## Structure

Repository layout is intentionally summarized instead of duplicating a full file tree:

- `artifacts/`: canonical machine-readable v1 contracts, registries, fixtures, OpenAPI, and mirror manifests.
- `zh/`: maintained Chinese normative text plus `zh/conformance/` and `zh/sync/` mirror copies derived from `artifacts/`.
- `.github/workflows/`: CI entrypoints for artifact lint and drift guards.
- `tools/`: repository maintenance scripts for mirror sync, artifact checks, and drift checks.

The Chinese specification under `zh/` is the leading human-readable normative text for Contrix v1. For machine-verifiable contracts, `artifacts/registry/contract-catalog.json`, the active generated registries, `artifacts/registry/error-code-registry.json`, `artifacts/profiles/conformance-profiles.json`, JSON Schemas, OpenAPI, bindings, and fixtures are the canonical machine-readable sources listed in `zh/spec-map.md`.

For v1 interoperability, only active entries referenced by `artifacts/registry/*` and `artifacts/profiles/*` are normative machine contracts.

Any drift between `zh/` and generated artifacts is a specification bug. For event/schema/id/operation/error/profile wire contracts, implementations MUST follow the active machine registries and schemas. For reducer, authorization, privacy, security, and deployment semantics not fully expressible in machine artifacts, implementations MUST follow the Chinese normative text. Non-active generated artifacts MUST NOT be treated as wire truth.

Artifact maintenance pipeline:

- `python tools/artifact_pipeline.py generate`
- `python tools/artifact_pipeline.py sync`
- `python tools/artifact_pipeline.py check`
- `.github/workflows/artifact-lint.yml`
