# Contrix v1 Conformance Artifact Index

This directory collects the Contrix v1 conformance documents, test vectors, and machine-readable mirrors.

## Contents

- `schemas/`: JSON Schema artifacts for core objects, sync state, blob/media, push, and identity.
- `fixtures/`: official JSON fixtures consumable by `cotest`, SDKs, and service implementations.
- `encoding.md`, `encoding-conformance-vectors.md`: canonical JSON, hash, proof, HLC, cursor, and rank rules.
- `cursor-encoding.md`, `cursor-test-vectors.md`: cursor format and vectors.
- `hlc-specification.md`, `hlc-test-vectors.md`: HLC format, comparison rules, and vectors.
- `state-resolution-conformance-vectors.md`, `redaction-conformance-vectors.md`, `capability-conformance-vectors.md`, `sync-conformance-vectors.md`: behavioral vector families.
- `schema-registry.md`, `conformance-profiles.md`, `conformance-suite.md`: registry, profile, and suite definitions.

Language-neutral canonical outputs live in [`artifacts`](../../artifacts/README.md).
