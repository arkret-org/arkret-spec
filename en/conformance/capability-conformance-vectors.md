# Capability Conformance Vectors

## 1. Goal

This file fixes cross-implementation behavior for delegation chains, revoke rollback, and approval constraints.

## 2. Vector names

```text
cx.vector.capability.<scenario>.v1
```

## 3. Vector: Delegation chain

Vector ID:

```text
cx.vector.capability.delegate_chain.v1
```

Input:

```json
{
  "root": { "kind": "cx.capability.grant", "state_key": "space-admin", "subject": "did:uuid:root_admin" },
  "delegation_a": {
    "event_id": "cx:event:01js0d1g000000000000000000",
    "kind": "cx.capability.delegate",
    "state_key": "space-admin-delegate-a",
    "subject": "did:uuid:ops"
  },
  "delegation_b": {
    "event_id": "cx:event:01js0d1h000000000000000000",
    "kind": "cx.capability.delegate",
    "state_key": "invite-ops",
    "subject": "did:uuid:intern",
    "constraints": {
      "audiences": ["did:web:vendor.example"]
    }
  },
  "action_request": {
    "actor_id": "did:uuid:intern",
    "action": "invite.send"
  }
}
```

Expected:

```json
{
  "authorized": true,
  "chain": [
    "cx:event:01js0d1g000000000000000000",
    "cx:event:01js0d1h000000000000000000"
  ]
}
```

## 4. Vector: Revoke rollback

Vector ID:

```text
cx.vector.capability.revoke_rollback.v1
```

Input sequence:

1. grant
2. revoke
3. dependent action event (should fail)
4. rollback revoke

Expected:

- Action is rejected while revoke is active.
- Recomputed under rollback it becomes authorized with explicit rollback evidence.

## 5. Vector: Missing approval constraint

Vector ID:

```text
cx.vector.capability.approval_constraint.v1
```

Input: high-risk `cx.policy.action` requiring approval but lacking enough approvals.

Expected:

- `authorized = false`
- response includes `failure_code = "approval_required"`
- event must enter proposal/review lifecycle, not pass directly.

