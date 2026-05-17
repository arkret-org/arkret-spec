# Agent Workspace — Conformance Vectors

This directory holds per-vector conformance test fixtures for
`cx.profile.agent_workspace.v1`.

Normative spec: [`spec/v1/zh/extensions/agent-workspace-profile.md`](../../../zh/extensions/agent-workspace-profile.md)
Vector enumeration: [§15 of the profile doc](../../../zh/extensions/agent-workspace-profile.md) (44 vectors across 8 groups).

## Registry anchor + per-vector fixtures

The profile's `required_fixtures` list in
[`conformance-profiles.json`](../../profiles/conformance-profiles.json)
points at a single anchor file
[`../../fixtures/agent-workspace-fixture.json`](../../fixtures/agent-workspace-fixture.json),
which **indexes this directory** (vector groups, expected counts, status).
The actual per-vector JSON fixtures land in this directory. Two layers:

- Registry anchor (singular):
  `spec/v1/artifacts/fixtures/agent-workspace-fixture.json` — declares the
  profile + group counts; allows the profile-lint pipeline to require a
  fixture exists.
- Per-vector files (this directory): `15-<group>-<NN>-<title>.json` —
  one JSON file per vector, with input event + expected reducer outcome.

## Vector groups

| Group | Filename prefix | Count | Implemented |
|---|---|---|---|
| 15.1 execution_state FSM | `15-1-execution-` | 12 | 12 |
| 15.2 transparency FSM | `15-2-transparency-` | 4 | 4 |
| 15.3 source_authority FSM | `15-3-source-authority-` | 4 | 4 |
| 15.4 Reservation / recovery | `15-4-reservation-` | 6 | 6 |
| 15.5 mention_redirect | `15-5-mention-redirect-` | 5 | 5 |
| 15.6 import_attestation | `15-6-import-attestation-` | 5 | 5 |
| 15.7 Saga / observe-then-write | `15-7-saga-` | 5 | 5 |
| 15.8 跨域 / 治理 | `15-8-governance-` | 3 | 3 |

**Implemented: 44 / 44**. Coverage summary:

- 15.1 execution_state: full FSM transition matrix (9 legal + 3 illegal terminal/backward exits)
- 15.2 transparency: 2 legal transitions + 2 unreachable-edge rejections
- 15.3 source_authority: 2 legal transitions + 2 audit-preserving sink rejections
- 15.4 reservation/recovery: singleton enforcement, ⊥ collapse, §8 recovery (happy/missing-refs/unauthorized), TTL cleanup
- 15.5 mention_redirect: privacy invariant, target binding, fail-closed, grant validation triple, schema happy path
- 15.6 import_attestation: signature tamper, content tamper, unverifiable origin, missing/verified export attestation
- 15.7 saga / observe-then-write: phase-2 reject, source redact, dual loss, cross-deployment, reverse-publish abort
- 15.8 governance: mirror flow cardinality, E2EE preview redaction, teardown audit anchor

## Vector fixture format

Each vector is a JSON file:

```json
{
  "vector_id": "15-X-group-NN",
  "spec_section": "§15.X.N",
  "title": "human-readable case",
  "preconditions": { ... },
  "input_event": { "kind": "cx.agent_task.*", "payload": { ... } },
  "expected_outcome": {
    "reducer_result": "accepted | failed_precondition | cell_bottom | unauthorized | schema_violation",
    "reason": "<error reason code>",
    "cell_changes": [ ... ]
  }
}
```

Negative vectors carry `"negative": true` and `reducer_result ≠ "accepted"`.

Recovery vectors use `input_move` (full Move shape with `lattice_op`, `predicate`, `refs`) instead of `input_event`.

Multi-step saga / observe-then-write vectors use `input_steps[]` carrying an
ordered list of operations across actors / deployments, with `expected_final_state` summarising
the cells' state after the sequence.
