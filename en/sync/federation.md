# Federation

Contrix federation connects Principal Servers and their delegated repo, sync, index, identity, and blob services across domains.

Federation relies on DID service identities, signed service requests, idempotent transactions, cross-domain Space joins, and backfill authorization. It does not require an independent third-party distribution service; Space operations move between participating Principal Servers or explicitly delegated Space Hosts.

## Service Identity

Each Principal Server, Repo, and Index node MUST have its own service DID. DID Document `service.type` uses protocol registered names such as `ContrixPrincipalServer`; service `describe` responses use runtime `service_type` values such as `principal_server`. Federation authentication MUST verify the binding between service DID, endpoint, request signature, and declared service type.

## Push Flow

When `server-alpha.com` receives a new Operation for a cross-domain Space and another participant Principal Server `server-beta.com` also serves that Space:

1. `server-alpha.com` detects that the Operation belongs to a cross-domain Space.
2. It resolves the peer Principal Server from Space policy, membership, and service delegation.
3. It binds the transaction to a destination service DID and a service binding snapshot.
4. It sends the signed Operation envelope to `server-beta.com`.
5. `server-beta.com` verifies actor signature, Space policy, service delegation, service binding, and causality before accepting.

In this document, Operation means the signed protocol operation envelope, usually represented as a full Event Envelope or an atomic change referenced by a Commit. HTTP paths and wire fields use `push-ops`, `pull-ops`, and `ops`; semantically they carry Operation collections.

Request fields for `POST /api/v1/federation/push-ops`:

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
| `ops` | body | `object[]` | required | Operation array; each item MUST be a complete signed Event Envelope or equivalent Operation envelope. |

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
  "ops": []
}
```

Response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `accepted` | `id[]` | required | Accepted Operation ids. |
| `rejected` | `object[]` | required | Rejected items; each item SHOULD include `id`, `reason_code`, and auditable detail. |
| `quarantine` | `id[]` | optional | Operation ids held for asynchronous or human review. |

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

## Federation API Binding

Default HTTP binding:

```text
POST /api/v1/federation/push-ops
GET /api/v1/federation/pull-ops?space_id=<id>&after_cursor=<cursor>&limit=<n>
GET /api/v1/federation/space-members?space_id=<id>
POST /api/v1/federation/verify-actor
```

`POST /api/v1/federation/push-ops` uses the request and response fields defined in Push Flow above. Canonical operation: `cx.federation.push_ops`.

`GET /api/v1/federation/pull-ops` request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `space_id` | query | `id` | required | Space to backfill. |
| `after_cursor` | query | `cursor` | optional | Return Operations after this cursor. |
| `limit` | query | `int` | optional | Maximum result count; server MUST enforce a maximum. |

`GET /api/v1/federation/pull-ops` response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `ops` | `object[]` | required | Operation array; each item MUST preserve the original signed envelope. |
| `next_cursor` | `cursor` | optional | Cursor for the next page. |
| `has_more` | `boolean` | required | Whether more visible Operations are available. |

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

