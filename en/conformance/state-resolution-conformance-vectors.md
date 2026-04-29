# State Resolution Conformance Vectors

## 1. Goal

This file turns state resolution and conflict arbitration semantics into reproducible vectors from `event-auth-state-resolution.md`.

Each implementation MUST report:

- `vector_id`
- `input`
- `resolved_state`
- `conflict_records`
- `transcript_order`

Unless noted otherwise, all vectors run under `space_version = "1"`.

## 2. Vector naming

```text
cx.vector.state_resolution.<scenario>.v1
```

Vectors in this file require:

- canonical validation, schema checks, signature checks, and auth refs before reduction.
- deterministic reducer result for each candidate branch set.
- consistent `event_id` ordering and conflict records across nodes.

## 3. Vector: Concurrent membership conflict

Vector ID:

```text
cx.vector.state_resolution.conflict_membership.v1
```

Input:

```json
{
  "space_id": "cx:space:01js0ms000000000000000000",
  "base_state": {
    "event_id": "cx:event:01js0base000000000000000000",
    "kind": "cx.member.state",
    "state_key": "did:uuid:alice",
    "content": { "membership": "join" }
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0m1b000000000000000000",
      "kind": "cx.member.state",
      "state_key": "did:uuid:alice",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:admin_a",
      "hlc": "01970e589d21-0004-a13f9c2e",
      "causal_depth": 10,
      "content": { "membership": "ban", "reason": "policy" }
    },
    {
      "event_id": "cx:event:01js0m1a000000000000000000",
      "kind": "cx.member.state",
      "state_key": "did:uuid:alice",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:admin_b",
      "hlc": "01970e589d21-0004-a13f9d2e",
      "causal_depth": 10,
      "content": { "membership": "leave", "reason": "requested" }
    },
    {
      "event_id": "cx:event:01js0m1c000000000000000000",
      "kind": "cx.member.state",
      "state_key": "did:uuid:alice",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:admin_c",
      "hlc": "01970e589d21-0004-a13f9f2e",
      "causal_depth": 10,
      "content": { "membership": "invite", "reason": "recovery" }
    }
  ],
  "auth_state": {
    "admin_a": "creator",
    "admin_b": "admin",
    "admin_c": "member"
  }
}
```

Expected:

```json
{
  "membership": "ban",
  "membership_epoch": "m_10",
  "source_event_id": "cx:event:01js0m1b000000000000000000"
}
```

## 4. Vector: Capability-dependent rebind

Vector ID:

```text
cx.vector.state_resolution.capability_rebind.v1
```

Input:

```json
{
  "base_state": {
    "kind": "cx.capability.grant",
    "state_key": "cap-chan-post",
    "content": {
      "subject": "did:uuid:alice",
      "actions": ["message.send"],
      "state": "active"
    }
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0g1e000000000000000000",
      "kind": "cx.capability.grant",
      "state_key": "cap-chan-post",
      "space_version": "1",
      "actor_id": "did:uuid:moderator_1",
      "hlc": "01970e589d22-0001-11111111",
      "causal_depth": 8
    },
    {
      "event_id": "cx:event:01js0r1e000000000000000000",
      "kind": "cx.capability.revoke",
      "state_key": "cap-chan-post",
      "space_version": "1",
      "actor_id": "did:uuid:member_x",
      "hlc": "01970e589d22-0001-22222222",
      "causal_depth": 9,
      "content": { "target_capability_id": "cap-chan-post" }
    },
    {
      "event_id": "cx:event:01js0g1f000000000000000000",
      "kind": "cx.capability.grant",
      "state_key": "cap-chan-post",
      "space_version": "1",
      "actor_id": "did:uuid:moderator_2",
      "hlc": "01970e589d22-0001-33333333",
      "causal_depth": 9,
      "content": {
        "subject": "did:uuid:alice",
        "actions": ["message.send", "message.react"]
      }
    }
  ]
}
```

Expected:

```json
{
  "resolved_state": {
    "kind": "cx.capability.grant",
    "state_key": "cap-chan-post",
    "content": {
      "subject": "did:uuid:alice",
      "actions": ["message.send", "message.react"]
    },
    "source_event_id": "cx:event:01js0g1f000000000000000000"
  }
}
```

## 5. Vector: Space governance schema conflict

Vector ID:

```text
cx.vector.state_resolution.schema_update.v1
```

Input:

```json
{
  "base_state": {
    "kind": "cx.space.policy",
    "state_key": "space_policy",
    "content": { "max_message_length": 4096, "allow_file_types": ["jpg", "png"] }
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0s1a000000000000000000",
      "kind": "cx.space.policy",
      "state_key": "space_policy",
      "space_version": "1",
      "actor_id": "did:web:adminspace.example",
      "hlc": "01970e589d23-0010-11111111",
      "causal_depth": 12,
      "content": { "max_message_length": 1024, "allow_file_types": ["jpg"] }
    },
    {
      "event_id": "cx:event:01js0s1b000000000000000000",
      "kind": "cx.space.policy",
      "state_key": "space_policy",
      "space_version": "1",
      "actor_id": "did:web:adminspace.example",
      "hlc": "01970e589d23-0010-22222222",
      "causal_depth": 12,
      "content": { "max_message_length": 2048, "allow_file_types": ["jpg", "png", "pdf"] }
    }
  ]
}
```

Expected winner:

```text
cx:event:01js0s1b000000000000000000
```

## 6. Vector: Kanban atomic task move

Vector ID:

```text
cx.vector.state_resolution.kanban_atomic_task_move.v1
```

Two concurrent `cx.field_position.move` operations writing the same `(view_id, entity_id, group_by)` MUST resolve as one atomic position register. The winning operation supplies both the column value and rank; implementations MUST NOT combine `to_value` from one operation with `rank` from another. Legacy `cx.task.move` maps to the same reducer as a compatibility alias.

Expected behavior is captured by `artifacts/fixtures/state-resolution-fixture.json` case `kanban_atomic_task_move`.

## 7. Vector: Kanban relation rebalance assignment

Vector ID:

```text
cx.vector.state_resolution.kanban_relation_rebalance_assignment.v1
```

`cx.container.rebalance` MUST rewrite ranks for all active edges in the target container using the `cx.rank.lexofractional.v1` assignment formula. For the three-edge vector, expected ranks are `F`, `V`, and `k` in the reducer's stable order. Rebalance MUST NOT add, delete, move, or reorder membership edges.

Expected behavior is captured by `artifacts/fixtures/state-resolution-fixture.json` case `relation_rebalance_assignment`.

## 8. Vector: Kanban relation rebalance CAS conflict

Vector ID:

```text
cx.vector.state_resolution.kanban_relation_rebalance_cas_conflict.v1
```

If `expected_state_hash` does not match the untrimmed canonical ordered set hash, reducers MUST reject the entire `cx.container.rebalance` operation and MUST NOT partially apply assignments. Legacy `cx.relation.rebalance` maps to the same reducer as a compatibility alias.

Expected behavior is captured by `artifacts/fixtures/state-resolution-fixture.json` case `relation_rebalance_cas_conflict`.

