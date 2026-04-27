# Federation Wire Protocol

Federation uses DID-authenticated service-to-service transactions.

Required areas:

- HTTP Message Signatures
- idempotent transactions
- cross-domain join
- backfill authorization
- frontier exchange
- fork detection
- quarantine queue

Principal Server, sync, repo, and index services MUST verify operation signatures, schema, capabilities, and source service authority.

## Service Authentication

Every federation service MUST have a service DID. Federation requests MUST use HTTP Message Signatures bound to:

- method
- target URI
- authority
- date
- content digest
- source service DID
- destination service DID
- canonical request hash

Rules:

- `origin` and `destination` MUST appear in the signature transcript and must match the body fields.
- `destination` MUST be the requested service DID; host, SNI, IP address, or URL alone is not a destination identity.
- Requests with bodies MUST carry `Content-Digest`; receivers MUST verify the digest against the body.
- Signatures SHOULD include `created` and `expires`; expired signatures, excessive future skew, and repeated nonces / request ids MUST be rejected or quarantined.
- Federation endpoints MUST NOT accept authentication material in query strings.
- Signature failure, destination mismatch, and body hash mismatch MUST use the standard JSON error envelope.

## Transaction Envelope

HTTP binding:

```text
PUT /api/v1/federation/transactions/{txn_id}
```

Request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `txn_id` | path | `id` | required | Idempotent transaction id; the path value MUST match `txn_id` in the body. |
| `origin` | body | `did` | required | Source service DID. |
| `destination` | body | `did` | required | Destination service DID; MUST match HTTP Message Signature, target URL, DID service endpoint, Space policy, and `service_binding_ref`. |
| `service_binding_ref` | body | `object` | required | Destination service binding snapshot. |
| `service_binding_ref.space_policy_hash` | body | `sha256:<hash>` | required | Space policy version or hash. |
| `service_binding_ref.membership_frontier` | body | `id[]` | required | Membership / policy causal frontier. |
| `service_binding_ref.destination_service_type` | body | `string` | required | Destination service type, for example `principal_server`. |
| `operations` | body | `object[]` | required | Signed Operation Envelope array; each item is independently signature and authorization checked. |
| `receipts` | body | `object[]` | optional | Receipt / witness evidence related to this transaction. |
| `frontier` | body | `object` | optional | Sender causal frontier. |
| `created_at` | body | `datetime` | optional | Sender creation time; MUST NOT be used as authorization by itself. |
| `request_canonical_hash` | body | `sha256:<hash>` | optional | Canonical body hash; when present it MUST match `Content-Digest` and the signature transcript. |

Request example (not a complete schema):

```json
{
  "txn_id": "cx:txn:01JS0TX000000000000000000",
  "origin": "did:web:server.a.example",
  "destination": "did:web:server.b.example",
  "service_binding_ref": {
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:evt:..."],
    "destination_service_type": "principal_server"
  },
  "operations": [],
  "receipts": [],
  "frontier": {},
  "created_at": "2026-04-26T00:00:00Z"
}
```

`origin` and `destination` MUST be service DIDs. The receiver MUST verify that `destination` matches the request signature, target URL, DID service endpoint, Space policy, and `service_binding_ref`; mismatches MUST be rejected or quarantined.

Replay and idempotency rules:

- Receivers MUST use `(origin, destination, txn_id)` as the transaction idempotency key.
- Same idempotency key plus same canonical request hash MUST return a semantically equivalent response.
- Same idempotency key plus different canonical request hash MUST return `duplicate_conflict`.
- Expired signatures, repeated nonces, high failure rates, or anomalous source behavior MAY be quarantined, but queueing in quarantine is not operation acceptance.
- Each Operation is accepted only after Actor signature, schema, capability, Space policy, service delegation, and causal dependencies all pass. The transaction signature proves only the transport source.

Response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | Whether the transaction was processed; `true` does not imply every operation was accepted. |
| `accepted` | `id[]` | required | Accepted operation IDs. |
| `rejected` | `object[]` | required | Rejected items; each item SHOULD include `id`, `reason_code`, and diagnostic detail. |
| `next_retry_at` | `datetime` | optional | Retry time for rate-limited, temporarily unavailable, or dependency-missing cases. |

Error responses MUST use the standard error envelope from `api-conventions.md`. Federation endpoints MUST NOT use array-wrapped responses or encode business failures inside HTTP `200`.

Recommended `reason_code` values:

| `reason_code` | Meaning |
| --- | --- |
| `invalid_signature` | Service or Actor signature is invalid. |
| `destination_mismatch` | `destination` does not match signature, URL, DID service endpoint, or policy binding. |
| `duplicate_conflict` | Same transaction / Operation id maps to different content. |
| `dependency_missing` | Causal dependency is missing and may be recovered by backfill or snapshot bootstrap. |
| `capability_denied` | Actor, service, or Space policy denies the request. |
| `schema_violation` | Operation or transaction schema is invalid. |
| `temporarily_unavailable` | Dependency, frontier, or local queue is temporarily unavailable. |
| `rate_limited` | Source is rate-limited; response SHOULD include `Retry-After`. |

Backfill authorization MUST evaluate the requester service DID against Space policy, membership frontier, service delegation, and plaintext visibility rules. If the requested range contains non-E2EE private content, the requester MUST be a participant Principal Server or an explicitly listed `plaintext_visible_services` entry for that range.

Backfill responses MUST preserve original signed Operation envelopes. Services MUST NOT rewrite Actor signatures, forge senders, replace timestamps, or downgrade invisible plaintext into stripped previews unless Space policy explicitly allows that preview type.

## Fork Evidence

If two histories contain conflicting commits with the same id but different hashes, services MUST quarantine and report `duplicate_conflict`.

When a conflict comes from the same Actor or Repo with different signed heads, receivers SHOULD retain a minimal evidence set: conflicting commit id, hash, signing key id, source service DID, receive time, and related frontier. Evidence must not include unauthorized plaintext payloads.


