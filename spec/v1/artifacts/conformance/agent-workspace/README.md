# Agent Workspace — Conformance Vectors

This directory holds conformance test vectors for `cx.profile.agent_workspace.v1`.

Normative spec: [`spec/v1/zh/extensions/agent-workspace-profile.md`](../../../zh/extensions/agent-workspace-profile.md)
Vector enumeration: [§15 of the profile doc](../../../zh/extensions/agent-workspace-profile.md) (43 vectors across 8 groups).

## Vector groups

| Group | Filename prefix | Count | Spec section |
|---|---|---|---|
| 15.1 execution_state FSM | `15-1-execution-` | 12 | §15.1 |
| 15.2 transparency FSM | `15-2-transparency-` | 4 | §15.2 |
| 15.3 source_authority FSM | `15-3-source-authority-` | 4 | §15.3 |
| 15.4 Reservation / recovery | `15-4-reservation-` | 6 | §15.4 |
| 15.5 mention_redirect | `15-5-mention-redirect-` | 5 | §15.5 |
| 15.6 import_attestation | `15-6-import-attestation-` | 5 | §15.6 |
| 15.7 Saga / observe-then-write | `15-7-saga-` | 5 | §15.7 |
| 15.8 跨域 / 治理 | `15-8-governance-` | 3 | §15.8 |

**Total: 43 vectors**

## Vector fixture format

Each vector is a JSON file:

```json
{
  "vector_id": "15-1-execution-01",
  "title": "[create] → pending_source_stub",
  "preconditions": [
    { "kind": "frontier", "...": "..." }
  ],
  "input_event": {
    "kind": "cx.agent_task.create",
    "...": "..."
  },
  "expected_outcome": {
    "reducer_result": "accepted",
    "cell_changes": [
      { "cell": "agent_task.<id>.execution_state", "before": null, "after": "pending_source_stub" }
    ]
  }
}
```

Negative vectors set `expected_outcome.reducer_result` to one of:
- `failed_precondition` (with `reason`)
- `failed_bottom`
- `unauthorized`
- `schema_violation`

## Status

⚠️ **Fixtures NOT yet implemented**. This README and directory structure are placeholders.
See [`_agent_workspace_artifact_todos.md`](../../../../../_agent_workspace_artifact_todos.md) §3 for the implementation backlog.

Implementers SHOULD provide fixtures before claiming conformance to `cx.profile.agent_workspace.v1`.
