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

Principal Server, sync, repo, and index services MUST verify event signatures, schema, capabilities, and source service authority.

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
| `events` | body | `object[]` | required | Signed Event Envelope array; each item is independently signature and authorization checked. |
| `receipts` | body | `object[]` | optional | Receipt / witness evidence related to this transaction. |
| `frontier` | body | `object` | optional | Sender causal frontier. |
| `created_at` | body | `datetime` | optional | Sender creation time; MUST NOT be used as authorization by itself. |

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
  "events": [],
  "receipts": [],
  "frontier": {},
  "created_at": "2026-04-26T00:00:00Z"
}
```

`origin` and `destination` MUST be service DIDs. The receiver MUST verify that `destination` matches the request signature, target URL, DID service endpoint, Space policy, and `service_binding_ref`; mismatches MUST be rejected or quarantined.

Response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | Whether the transaction was processed; `true` does not imply every event was accepted. |
| `accepted` | `id[]` | required | Accepted event / operation ids. |
| `rejected` | `object[]` | required | Rejected items; each item SHOULD include `id`, `reason_code`, and diagnostic detail. |
| `next_retry_at` | `datetime` | optional | Retry time for rate-limited, temporarily unavailable, or dependency-missing cases. |

Backfill authorization MUST evaluate the requester service DID against Space policy, membership frontier, service delegation, and plaintext visibility rules. If the requested range contains non-E2EE private content, the requester MUST be a participant Principal Server or an explicitly listed `plaintext_visible_services` entry for that range.

