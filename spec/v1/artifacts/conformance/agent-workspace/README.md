# Agent Workspace — Conformance Vectors

This directory holds conformance test vectors for `cx.profile.agent_workspace.v1`.

Normative spec: [`spec/v1/zh/extensions/agent-workspace-profile.md`](../../../zh/extensions/agent-workspace-profile.md)
Vector enumeration: [§15 of the profile doc](../../../zh/extensions/agent-workspace-profile.md) (43 vectors across 8 groups).

## Vector groups

| Group | Filename prefix | Count | Implemented |
|---|---|---|---|
| 15.1 execution_state FSM | `15-1-execution-` | 12 | 3 (01, 03, 10) |
| 15.2 transparency FSM | `15-2-transparency-` | 4 | 2 (01, 03) |
| 15.3 source_authority FSM | `15-3-source-authority-` | 4 | 1 (01) |
| 15.4 Reservation / recovery | `15-4-reservation-` | 6 | 3 (01, 02, 03) |
| 15.5 mention_redirect | `15-5-mention-redirect-` | 5 | 0 |
| 15.6 import_attestation | `15-6-import-attestation-` | 5 | 0 |
| 15.7 Saga / observe-then-write | `15-7-saga-` | 5 | 0 |
| 15.8 跨域 / 治理 | `15-8-governance-` | 3 | 0 |

**Implemented: 9 / 43**. The 9 land vectors cover the highest-priority correctness invariants:

- Initial 3-cell state on task create (§15.1.1)
- Phase 3 reconcile happy path (§15.1.3)
- Illegal terminal-exit transition (§15.1.10)
- Observe-then-write transparency loss (§15.2)
- Unreachable Rev 7 transition rejected (§15.2)
- Observe-then-write source_authority revoke (§15.3)
- Empty-sentinel singleton enforcement (§15.4.21)
- Multi-master ⊥ collapse (§15.4.22)
- §8 recovery Move with lex-min (§15.4.23)

The remaining 34 are tracked in `_agent_workspace_artifact_todos.md` §3 and on the proposal repo's open conformance backlog. They follow the same JSON shape as the existing fixtures and SHOULD be authored by implementers as they integrate.

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
