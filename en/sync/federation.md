# Federation

Contrix federation connects Principal Servers and their delegated repo, sync, index, identity, and blob services across domains.

Federation relies on DID service identities, signed service requests, idempotent transactions, cross-domain Space joins, and backfill authorization. It does not require an independent third-party distribution service; Space operations move between participating Principal Servers or explicitly delegated Space Hosts.

## Service Identity

Each Principal Server, Repo, and Index node MUST have its own service DID. DID Document `service.type` uses protocol registered names such as `ContrixPrincipalServer`; service `describe` responses use runtime `service_type` values such as `principal_server`. Federation authentication MUST verify the binding between service DID, endpoint, request signature, and declared service type.

Service-to-service HTTP requests MUST use HTTP Message Signatures. The signature MUST cover `@method`, `@target-uri`, `@authority`, `content-digest` when a body is present, the request time window such as `created` / `expires`, source service DID, destination service DID, and canonical request hash.

Verification rules:

- Body `origin` / `destination` MUST match the service DIDs in the signature transcript.
- `destination` MUST be the receiver service DID; reverse proxies, multi-tenant hosts, and shared ingress services cannot rely on `Host` alone.
- Requests with bodies MUST include `Content-Digest` over the canonical request body.
- Protected federation endpoints MUST NOT accept query-string authentication.
- Signature failure, destination mismatch, digest mismatch, or expired request windows MUST return the standard error envelope with minimal disclosure.

## Push Flow

When `server-alpha.com` receives a new Operation for a cross-domain Space and another participant Principal Server `server-beta.com` also serves that Space:

1. `server-alpha.com` detects that the Operation belongs to a cross-domain Space.
2. It resolves the peer Principal Server from Space policy, membership, and service delegation.
3. It binds the transaction to a destination service DID and a service binding snapshot.
4. It sends the signed Operation envelope to `server-beta.com`.
5. `server-beta.com` verifies actor signature, Space policy, service delegation, service binding, and causality before accepting.

In this document, Operation means the signed protocol operation envelope, usually represented as a full Event Envelope or an atomic change referenced by a Commit. HTTP paths and wire fields use `push-operations`, `pull-operations`, and `operations`; semantically they carry Operation collections.

Request fields for `POST /api/v1/federation/push-operations`:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `Signature-Input` | header | `string` | required | HTTP Message Signature input; MUST bind `@method`, `@target-uri`, `content-digest`, source service DID, and destination service DID. |
| `Signature` | header | `string` | required | HTTP Message Signature from the source service DID. |
| `Content-Digest` | header | `string` | required | Request body digest covered by the signature. |
| `origin` | body | `did` | required | Source service DID. |
| `destination` | body | `did` | required | Destination service DID; MUST match target URL, DID service endpoint, and Space policy delegation. |
| `space_id` | body | `id` | required | Space for the Operations. |
| `service_binding_ref` | body | `object` | required | Destination service binding snapshot. |
| `service_binding_ref.space_policy_hash` | body | `sha256:<hash>` | required | Space policy hash used by the sender. |
| `service_binding_ref.membership_frontier` | body | `id[]` | required | Membership / policy causal frontier. |
| `service_binding_ref.destination_service_type` | body | `string` | required | Destination service type, for example `principal_server`. |
| `operations` | body | `object[]` | required | Operation array; each item MUST be a complete signed Event Envelope or equivalent Operation envelope. |

Request example (not a complete schema):

```json
{
  "origin": "did:web:server-alpha.com",
  "destination": "did:web:server-beta.com",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "service_binding_ref": {
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:evt:..."],
    "destination_service_type": "principal_server"
  },
  "operations": []
}
```

Response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `accepted` | `id[]` | required | Accepted Operation ids. |
| `rejected` | `object[]` | required | Rejected items; each item SHOULD include `id`, `reason_code`, and auditable detail. |
| `quarantine` | `id[]` | optional | Operation ids held for asynchronous or human review. |

Error responses MUST use the standard JSON error envelope from `api-conventions.md`. Per-Operation failures in a batch SHOULD go into `rejected[]`; whole-request authentication failure, destination mismatch, schema parse failure, or rate limiting SHOULD return the corresponding HTTP error. `rate_limited` and predictable `temporarily_unavailable` responses SHOULD include `Retry-After`.

Recipient service binding rules:

- An actor DID MAY declare its controlled or delegated `ContrixPrincipalServer` endpoint.
- Organization DID or Space policy MAY assign a Principal Server for organization members, managed devices, or a specific Space.
- `sync_endpoints` list only shared Space Hosts or organization Principal Servers explicitly delegated by Space policy; it does not authorize arbitrary third parties to receive private content.
- Federation transactions MUST bind destination service DID, Space policy hash/version, membership frontier, and target endpoint.
- After service delegation revocation or member removal, non-encrypted private content MUST NOT be pushed to the old service DID after the effective causal point; historical backfill must be re-evaluated under the new visibility and history policy.

## Space Host / Sync Endpoints

Space metadata MAY contain `sync_endpoints` for explicitly delegated shared Space Hosts or organization Principal Servers:

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "sync_endpoints": [
    {
      "did": "did:web:server-alpha.com",
      "endpoint": "https://server-alpha.com/api/v1",
      "role": "primary",
      "service_type": "principal_server",
      "plaintext_visible": true
    }
  ]
}
```

If `plaintext_visible` is true, the service DID MUST also appear in Space policy `plaintext_visible_services`. If false, the service may only receive public content, encrypted envelopes, irreversible hashes, or policy-allowed stripped previews.

## Domain Bootstrap Cache

DID Document service entries are the authority for federation service discovery. Domain bootstrap MAY expose:

```text
GET https://<domain>/.well-known/contrix/server
```

The response only locates candidate service endpoints; it does not authorize federation. Receivers still MUST verify service DID, DID Document, describe response, TLS name, HTTP Message Signature, Space policy / service delegation, and `destination` binding.

Discovery caching rules:

- Cache according to HTTP cache headers.
- Without explicit cache time, clients MAY use a default TTL up to 24 hours.
- Positive caches SHOULD be capped locally, with 48 hours as a recommended upper bound.
- Negative caches must use a short TTL or exponential backoff so a temporary failure does not break cross-domain sync for too long.
- Service delegation revocation, DID Document key-log updates, or Space policy changes must invalidate affected local cache entries by version / hash.

## Federation API Binding

Default HTTP binding:

```text
POST /api/v1/federation/push-operations
GET /api/v1/federation/pull-operations?space_id=<id>&after_cursor=<cursor>&limit=<n>
GET /api/v1/federation/space-members?space_id=<id>
POST /api/v1/federation/verify-actor
```

`POST /api/v1/federation/push-operations` uses the request and response fields defined in Push Flow above. Canonical operation: `cx.federation.push_operations`.

`GET /api/v1/federation/pull-operations` request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `space_id` | query | `id` | required | Space to backfill. |
| `after_cursor` | query | `cursor` | optional | Return Operations after this cursor. |
| `limit` | query | `int` | optional | Maximum result count; server MUST enforce a maximum. |

`GET /api/v1/federation/pull-operations` response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `operations` | `object[]` | required | Operation array; each item MUST preserve the original signed envelope. |
| `snapshot_bootstrap` | `object` | optional | Optional snapshot assist object for bootstrap fast-path. If present, receivers MUST validate its signature and frontier consistency before using it. |
| `next_cursor` | `cursor` | optional | Cursor for the next page. |
| `has_more` | `boolean` | required | Whether more visible Operations are available. |

`snapshot_bootstrap` fields (when present):

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `snapshot_ref` | `id` | optional | Checkpoint snapshot identifier. |
| `state_hash` | `string` | optional | State root/digest that must match the checkpointed frontier. |
| `snapshot_frontier` | `id[]` | optional | Frontier that operations after this cursor must join against. |
| `state_signature` | `object` | optional | Signature over `snapshot_ref`, `state_hash`, and `snapshot_frontier`. |
| `state_signature.issuer` | `did` | optional | Issuer DID used for bootstrap trust. |
| `state_signature.alg` | `string` | optional | Signature algorithm / key type. |
| `state_signature.sig` | `string` | optional | Detached signature bytes. |

`GET /api/v1/federation/space-members` request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `space_id` | query | `id` | required | Space whose members are queried. |
| `cursor` | query | `cursor` | optional | Pagination cursor. |
| `limit` | query | `int` | optional | Maximum result count; server MUST enforce a maximum. |

`GET /api/v1/federation/space-members` response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `members` | `object[]` | required | Member summaries filtered by requester visibility and Space policy. |
| `membership_frontier` | `object` | required | Causal frontier for the membership view. |
| `next_cursor` | `cursor` | optional | Cursor for the next page. |

`verify-actor` helps a federation participant when it lacks local DID / key-log cache. It is not a public DID oracle and is not final authorization.

Request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `actor_id` | body | `did` | required | Actor DID to verify. |
| `purpose` | body | `enum(event_source,federation_join,device_binding)` | required | Verification purpose; the server MUST include it in authorization and rate-limit decisions. |
| `space_id` | body | `id` | optional; required for Space-scoped purposes | Related Space ID; binds Space policy, membership, and plaintext visibility. |
| `challenge` | body | `base64url string` | optional; required for challenge verification | Short-lived random challenge generated by the requester; the server MUST reject expired or replayed challenges. |
| `signed_payload_hash` | body | `sha256:<base64url-or-hex>` | optional; required when verifying a concrete event or device binding | Canonical hash of the payload being verified; MUST be bound into the signature transcript. |
| `signature` | body | `object` | required | Actor device-key or delegated signature. |
| `signature.kid` | body | `did-url` | required | Signing key id; MUST belong to the current or verifiable historical key log for `actor_id`. |
| `signature.alg` | body | `string` | optional | Signature algorithm; if present, it MUST match the key type in the DID Document/key log. |
| `signature.sig` | body | `base64url string` | required | Detached signature over the canonical verification payload. |

The canonical verification payload covered by `signature.sig` MUST bind at least `actor_id`, `purpose`, `space_id` if present, `challenge` if present, `signed_payload_hash` if present, requester service DID, destination service DID, and the request time window. This prevents replay across purposes, Spaces, or services.

Request example (not a complete schema):

```json
{
  "actor_id": "did:uuid:...",
  "purpose": "event_source",
  "space_id": "cx:space:...",
  "challenge": "base64url...",
  "signed_payload_hash": "sha256:...",
  "signature": {
    "kid": "did:uuid:...#device-a",
    "alg": "Ed25519",
    "sig": "base64url..."
  }
}
```

Response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `valid` | `boolean` | required | Whether signature, DID/key-log, and purpose constraints verified; it is not final authorization. |
| `actor_id` | `did` | required | Echo of the verified Actor DID; MUST match the request. |
| `verified_key_id` | `did-url` | required when `valid=true` | Key id that verified successfully. |
| `key_log_head` | `id` | optional | Key-log head used by the server; receivers may use it to refresh local cache. |
| `did_document_ref` | `sha256:<hash>` | optional | DID Document canonical hash or equivalent reference. |
| `expires_at` | `datetime` | required when `valid=true` | Latest cache time for this helper result; MUST NOT exceed local policy TTL. |
| `warnings` | `string[]` | required | Non-fatal warnings; empty array when absent. |

Response example (not a complete schema):

```json
{
  "valid": true,
  "actor_id": "did:uuid:...",
  "verified_key_id": "did:uuid:...#device-a",
  "key_log_head": "cx:keyevt:...",
  "did_document_ref": "sha256:...",
  "expires_at": "2026-04-26T00:05:00Z",
  "warnings": []
}
```

Requests MUST use HTTP Message Signature from the source service DID. `purpose` MUST be `event_source`, `federation_join`, `device_binding`, or an equivalent purpose allowed by Space policy. The requester must be a participant Principal Server, delegated Space Host, or service authorized for the related federation / join flow. The response is only a cache or diagnostic hint; receivers still independently verify DID document, key log, signature transcript, capability, and Space policy before accepting events, membership changes, or device bindings.

## 9. Interoperability Roadmap and Hardening

The following items are not all mandatory in the first stable profile. They are organized by criticality:

### 9.1 Federation-aware Snapshot Synchronization and Validation (Required for complete bootstrap correctness)

When a Principal Server needs long-range recovery from another domain, snapshot-assisted bootstrap is required for operability under normal network conditions. `GET /api/v1/federation/pull-operations` MAY return `snapshot_bootstrap`:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `snapshot_ref` | `id` | optional | Snapshot id that can be used as a checkpoint. |
| `state_hash` | `string` | optional | Snapshot state hash (commit-compatible digest). |
| `snapshot_frontier` | `id[]` | optional | Frontier covered by the snapshot. |
| `state_signature` | `object` | optional | Signature over the snapshot metadata; receivers MUST verify signature and frontier alignment before use. |

Receiver requirements:

- Verify snapshot signature and `state_hash` first.
- Start operation replay from `snapshot_frontier`; never treat a snapshot as a trustless new genesis.
- On snapshot verification failure, fall back to operation-only replay and move the peer into soft quarantine or rate-limited mode.

### 9.2 Multi-Principal Server Gossip / Batch Sync (Performance enhancement)

This is an optional optimization.

- Batch transport must preserve the signed envelope for each operation and support operation-level deduplication.
- Forwarding nodes must not rewrite envelopes or alter canonical order guarantees.
- A batch success is not equivalent to final authorization.
- Batch-level request hash/chunk digest SHOULD be supplied for replay/flood detection.

If an implementation enables multi-hop gossip rather than direct push/pull, each federation transaction MUST carry transport-level path metadata covered by the service-to-service signature, such as `relay_path`, `hop_count`, and `max_hops`. A receiver MUST reject or quarantine a transaction when its own service DID already appears in the path, when `origin` or `destination` is inconsistent with the signature transcript, or when `max_hops` is exceeded. Path metadata does not replace operation signatures and is not part of the actor's canonical event.

Forwarders MUST deduplicate by operation id and canonical operation hash before fanout. They SHOULD keep a bounded per `(space_id, operation_id, peer_service_did)` replay cache and MUST apply per-origin, per-space, and per-peer in-flight limits. When queues exceed local policy, services return `rate_limited` or `temporarily_unavailable` with `Retry-After`; they MUST NOT create unbounded retry storms.

### 9.3 Cross-domain delegation and propagation control (Required security boundary)

Cross-domain delegation must remain explicit:

- No implicit cross-domain delegation or rights cascade is allowed.
- Delegation must be expressed by explicit grant/delegate operations binding target space/service/subject, scope, optional expiry, and revocation behavior.
- Delegated authority must be auditable, bounded by depth/scope, and revocable.
- If a delegation chain cannot be revalidated end-to-end, receivers MUST reject with authorization failure.

### 9.4 Federation reputation systems (Optional ecosystem layer)

Reputation can be implemented as a local anti-abuse layer only.

- It MAY guide queueing, throttling, and sampling, but MUST NOT replace signature verification and Space policy authorization.
- Reputation logic MUST not suppress valid events without explicit authorization signals.
- Error responses under suspicion should remain explicit (`temporarily_unavailable`, `rate_limited`, `quarantine`) and retry-compatible.


