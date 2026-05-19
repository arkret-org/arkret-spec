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

## Fixture shapes

Every fixture carries `vector_id`, `spec_section`, `title`, and a
`preconditions` block. The **input** and **expected** blocks vary by what
the vector is actually testing — pick the narrowest shape that fits:

### Shape A — single-event reducer fixture

For a single wire Event going through the reducer (most common shape).

```json
{
  "vector_id": "15-X-group-NN",
  "spec_section": "§15.X.N",
  "title": "human-readable case",
  "preconditions": { ... },
  "input_event": {
    "kind": "cx.<event_kind>",
    "realm_id": "cx:realm:<uuidv7>",
    "actor_id": "did:web:<actor>",
    "preconditions": [ ... ],
    "effects": [ ... ],
    "refs": [ ... ],
    "payload": { ... }
  },
  "expected_outcome": {
    "reducer_result": "accepted | failed_precondition | cell_bottom | unauthorized | schema_violation",
    "reason": "<error reason code>",
    "cell_changes": [ ... ]
  }
}
```

`input_event` carries the canonical Contrix Event shape per
[event-schema.json](../../schemas/event-schema.json) — `realm_id` is at
the top of the event (NOT inside `payload`); reducer events carry
`preconditions[]` / `effects[]` directly on the envelope.

For trivial reducer behaviours that don't need to walk the full
envelope (FSM transitions, content-block schema checks, etc.), authors
MAY omit `preconditions[]` / `effects[]` / `refs[]` and rely on the
payload alone — the harness only validates that `expected_outcome`
matches reality.

### Shape B — abstract Move fixture

For tests that exercise lattice / Move algebra independent of any
particular wire event kind (e.g. §8 recovery Move semantics).

```json
{
  "input_move": {
    "lattice_op": { "kind": "set", "value": "..." },
    "predicate": { "op": "head_eq | head_in", "value": "...", "values": [ ... ] },
    "refs": [ { "id": "...", "role": "..." } ]
  },
  "expected_outcome": { ... }
}
```

### Shape C — concurrent Moves → ⊥

For multi-master conflict vectors.

```json
{
  "input_moves": [
    { "lattice_op": {...}, "predicate": {...} },
    { "lattice_op": {...}, "predicate": {...} }
  ],
  "expected_outcome": {
    "reducer_result": "cell_bottom",
    "bottom_diagnostic": { "cells": [...], "heads": [...] }
  }
}
```

### Shape D — multi-watcher race

For idempotence-by-precondition tests where two actors submit the same
transition concurrently.

```json
{
  "input_events": [
    { "kind": "...", "submitter": "A", "payload": {...} },
    { "kind": "...", "submitter": "B", "payload": {...} }
  ],
  "expected_outcomes": [
    { "submitter": "A", "reducer_result": "accepted",          "cell_changes": [...] },
    { "submitter": "B", "reducer_result": "failed_precondition", "reason": "..." }
  ]
}
```

### Shape E — multi-step saga / cascade

For sequences across actors / Realms / deployments.

```json
{
  "input_steps": [
    { "step": 1, "actor": "...", "kind": "...", "payload": {...}, "expected": "accepted" },
    { "step": 2, "actor": "...", "event": { "kind": "...", ... },  "expected": "accepted" }
  ],
  "expected_final_state": { "cell_X": "value", ... },
  "expected_post_state_invariants": [ "..." ]
}
```

Either `expected_final_state` (literal cell-state map) or
`expected_post_state_invariants[]` (prose invariants) MUST be present;
both MAY appear together.

### Shape F — notification delivery invariant

For private-object notifications (NOT reducer events), where the
fixture asserts privacy / redaction behaviour at delivery time.

```json
{
  "fixture_kind": "notification_delivery",
  "input_notification": {
    "schema_ref_doc": "spec/v1/artifacts/schemas/notification.schema.json",
    "id": "cx:notification:<uuidv7>",
    "schema": "cx.schema.notification.v1",
    "actor_id": "did:web:<receiver>",
    "realm_id": "cx:realm:<uuidv7>",
    "source_event_id": "cx:event:<uuidv7>",
    "notification_type": "agent_membership_change",
    "priority": "normal",
    "state": "unread",
    "created_at": "YYYY-MM-DDTHH:MM:SSZ"
  },
  "expected_delivery_invariants": [ "..." ]
}
```

`input_notification` MUST satisfy
[notification.schema.json](../../schemas/notification.schema.json)
(required fields: `id`, `actor_id`, `source_event_id`,
`notification_type`, `priority`, `state`, `created_at`).

**`preview` handling:** the notification schema types `preview` as
`object` (not nullable). In E2EE flows where there is no plaintext to
preview, fixtures and bridges MUST **omit** the `preview` field
entirely — do NOT send `"preview": null`. Acceptable values when the
field is present:

- absent (the E2EE / fully-redacted case)
- an opaque ciphertext object (e.g. `{ "envelope": "<base64>" }`) when
  the bridge needs to ferry an MLS-wrapped blob through the
  notification surface
- a plaintext object only when the source surface is non-E2EE

### Shape G — sub-cases negative vector

For consolidating multiple negative sub-scenarios that share a top-level
shape but differ in why they fail.

```json
{
  "negative": true,
  "sub_cases": [
    { "case_id": "...", "<varies>": "...", "expected_reason": "..." }
  ],
  "input_event_template": { "kind": "...", "payload": { "...": "<sub_case.field>" } },
  "expected_outcome": { "reducer_result": "unauthorized", "reason_per_sub_case": "see sub_cases[*].expected_reason" }
}
```

## Common conventions

- Negative vectors carry `"negative": true` and `reducer_result ≠ "accepted"`.
- All `cx:<kind>:<uuid>` example IDs MUST conform to the per-kind pattern
  in the relevant schema (UUIDv7 form: `[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`).
- For `cx.realm.tombstone` and other events whose payload schema is
  `additionalProperties=false`, the fixture's `input_event.payload` MUST
  carry ONLY the schema-allowed fields. Envelope-level fields like
  `realm_id` / `actor_id` belong on `input_event`, not inside `payload`.
- `evidence_refs[]` cite existing fixture event IDs (or stable example
  IDs) to express cross-vector causality; harness MAY treat them as
  opaque audit pointers.
