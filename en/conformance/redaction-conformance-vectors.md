# Redaction Conformance Vectors

## 1. Goal

This file defines redaction processing, field preservation, and visibility behavior under policy constraints.
Redaction is tested as a verifier-visible masking operation, not deletion.

Vector naming:

```text
cx.vector.redaction.<scenario>.v1
```

## 2. Vector: Preserve fields

Vector ID:

```text
cx.vector.redaction.preserve_fields.v1
```

Input:

```json
{
  "target_event": {
    "event_id": "cx:event:01js0mrec000000000000000000",
    "kind": "cx.message.create",
    "content": {
      "body": "private notes",
      "mentions": ["@bob"],
      "attachments": ["hash:img1", "hash:img2"]
    }
  },
  "redaction_event": {
    "event_id": "cx:event:01js0rmov000000000000000000",
    "kind": "cx.redaction",
    "content": {
      "redacts": "cx:event:01js0mrec000000000000000000",
      "reason_code": "policy_recall"
    }
  }
}
```

Expected result:

```json
{
  "event_id": "cx:event:01js0mrec000000000000000000",
  "state": "redacted",
  "kept_envelope_fields": [
    "event_id",
    "kind",
    "space_id",
    "space_version",
    "actor_id",
    "created_at",
    "hlc",
    "prev_refs",
    "auth_refs",
    "proofs",
    "hashes",
    "redacted_by",
    "redaction_reason_code"
  ]
}
```

Failure conditions:

- treating redaction as full deletion.
- retaining non-envelope fields.
- changing `event_id` or `hlc`.

## 3. Vector: Policy scope with redaction

Vector ID:

```text
cx.vector.redaction.policy_scope.v1
```

Input timeline:

1. message create
2. policy quarantine
3. redaction

Expected:

- projection keeps event position in timeline.
- redacted event body is hidden, but redaction evidence remains.
- archived/frozen content keeps timeline order and does not become fully deleted.

## 4. Vector: Hard erasure receipt

Vector ID:

```text
cx.vector.redaction.hard_erasure_receipt.v1
```

Expected:

- hard erasure removes payload bytes and derived plaintext from the tested storage boundary.
- the implementation retains a verification stub with original event id, original canonical hash or payload digest, redaction event id, erasure reason, executing service DID, time, and signed receipt.
- backfill returns the redacted / erased stub and does not fabricate a replacement event.
- legal hold blocks hard erasure while preserving redacted presentation.

