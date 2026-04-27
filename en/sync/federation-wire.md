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

Backfill authorization MUST evaluate the requester service DID against Space policy, membership frontier, service delegation, and plaintext visibility rules. If the requested range contains non-E2EE private content, the requester MUST be a participant Principal Server or an explicitly listed `plaintext_visible_services` entry for that range.

