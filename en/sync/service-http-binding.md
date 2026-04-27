# Service HTTP/JSON Binding Draft

## 1. Goal

This document defines the default HTTP/JSON binding request and response shape used for service interoperability.

Contrix protocol is not hard-coupled to REST semantics. Other transport bindings MAY use gRPC, WebSocket, SSE, message queue, or libp2p as long as they preserve the same operation semantics, authentication/authorization rules, idempotency, pagination, streaming, errors, and flow-control behavior.

## 2. General Requirements

- Requests and responses use `Content-Type: application/json` by default.
- Write requests MUST support idempotency via idempotency key or content-id style deduplication.
- Authentication MAY use bearer token, HTTP Message Signature, DID proof, or a transport-native equivalent.
- Services MUST expose `describe` / feature discovery for supported paths, profiles, and limits.
- Error responses MUST use a stable error schema.

## 3. Repo API

### 3.1 Submit Operation

```text
POST /api/v1/repo/submit-op
```

Request:

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "op": {}
}
```

Response:

```json
{
  "status": "accepted",
  "commit_id": "cx:commit:01JS0KE...",
  "sync_token": "opaque"
}
```

When `expected_state_hash` verification fails, return `409 cas_conflict`.

### 3.2 Incremental Sync

```text
POST /api/v1/repo/sync
```

Request:

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "since": "cursor-or-op-id",
  "limit": 500
}
```

Response:

```json
{
  "ops": [],
  "next_cursor": "opaque",
  "has_more": true
}
```

## 4. Identity API

```text
POST /api/v1/identity/resolve
```

Request:

```json
{
  "did": "did:web:alice.example"
}
```

Response:

```json
{
  "did_document": {
    "id": "did:web:alice.example",
    "verification_method": [],
    "service": []
  },
  "key_log_head": "cx:keyevt:01JS...",
  "seq": 5
}
```

The resolver MUST return enough method-specific evidence for clients to verify control history.

## 5. Relay API

```text
GET /api/v1/relay/firehose?space_id=<space_id>&cursor=<cursor>
```

Frame:

```json
{
  "type": "event",
  "seq": 106,
  "payload": {}
}
```

The same semantic stream MAY be exposed via WebSocket, SSE, or long polling.

## 6. Directory API

```text
POST /api/v1/directory/search-spaces
POST /api/v1/directory/resolve-space
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

Directory endpoints MUST apply discoverability checks, requestor proof, moderation policy, and authorization filtering per result.

For hidden or unauthorized resources, `resolve-*` SHOULD return an indistinguishable `not_found`.

## 7. Blob API

### 7.1 Upload

```text
POST /api/v1/blob/upload
```

Content type MAY be `application/octet-stream` or `multipart/form-data`.

Response:

```json
{
  "blob_ref": "cx:blob:sha256:e3b0...",
  "size": 102450,
  "mimetype": "image/png"
}
```

### 7.2 Download

```text
HEAD /api/v1/blob/get?blob_ref=<blob_ref>
GET /api/v1/blob/get?blob_ref=<blob_ref>
```

Clients MUST re-check hash value against `blob_ref`.

## 8. Standard Error Response

```json
{
  "ok": false,
  "error": {
    "code": "cas_conflict",
    "message": "expected_state_hash mismatch",
    "retry_after_ms": 2000
  }
}
```

## 9. Standard Error Codes

| Code | HTTP Status | Meaning |
| --- | --- | --- |
| `invalid_signature` | 401 | Signature verification failed. |
| `auth_expired` | 401 | Authentication token or grant has expired. |
| `capability_denied` | 403 | Caller lacks required capability. |
| `space_frozen` | 403 | Space is frozen or archived. |
| `not_found` | 404 | Resource missing or not visible. |
| `cas_conflict` | 409 | `expected_state_hash` mismatch. |
| `epoch_mismatch` | 409 | MLS epoch is stale. |
| `quota_exceeded` | 413 | Quota exceeded. |
| `rate_limited` | 429 | Request rate exceeded. |
| `unknown_did` | 422 | DID resolution failed. |
| `schema_violation` | 422 | Payload does not match schema. |
| `internal_error` | 500 | Internal node error. |

Clients receiving `429` MUST honor `retry_after_ms`; clients receiving `409` SHOULD retry after backing off and fetching latest state.

## 10. Security and Abuse Defense

Services SHOULD use identical failure semantics for high-risk paths:

- Directory lookup, join probing, and public metadata endpoints SHOULD NOT return distinguishable information between `not_found` and `forbidden`.
- Federation and policy-check edges SHOULD log source service DID and source domain hash, then apply `rate_limited` / `temporarily_unavailable` controls.
- Requests with missing/invalid signatures SHOULD be rejected with audit trails while preserving normal service availability for authenticated principals.

