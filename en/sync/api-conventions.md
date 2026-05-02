# HTTP/JSON Binding Conventions

## 1. Goal

This document defines the wire-level conventions for the default Contrix HTTP/JSON binding.

The Contrix protocol core is not tied to REST. Non-HTTP bindings such as gRPC, WebSocket, SSE, libp2p, message queues, or IPC MUST preserve equivalent authentication, authorization, idempotency, pagination, error, and flow-control semantics.

This document applies to identity registry, repo, Sync Service, blob, authz, push gateway, federation, and applet service surfaces unless a more specific document states an exception.

## 2. Transport And Encoding

Production endpoints MUST use HTTPS. Plain HTTP is only allowed for local development, test networks, or controlled intranet simulations.

JSON requests and responses MUST use UTF-8. Contrix canonical JSON fields use snake_case, for example `space_id`, `commit_id`, `service_endpoint`, `verification_method`, and `retry_after_ms`.

External raw standards MAY retain their original field names, such as W3C DID Core `verificationMethod`, but normalized Contrix views, indexes, policy inputs, and reducer inputs MUST map them to snake_case.

JSON requests with a body SHOULD use `Content-Type: application/json`; JSON responses MUST use `Content-Type: application/json`. Blob and media byte streams MAY use other content types, but metadata responses remain JSON.

## 3. Authentication

API calls SHOULD use one of:

- `Authorization: Bearer <session_token>`
- detached JWS request signature
- HTTP Message Signature
- mTLS for controlled enterprise or service-to-service deployments

Regardless of transport authentication, protocol authorization MUST resolve back to actor DID, device / session / agent delegation, capability grants, Space policy, and verified claims or attestations. Services MUST NOT skip capability checks merely because a bearer token exists.

Authentication material MUST be carried in headers, HTTP Message Signatures, mTLS handshakes, or an explicitly signed proof body. Services MUST NOT accept session tokens, access tokens, API keys, signing secrets, or equivalent authentication material in query strings, path segments, or URL fragments.

Protected endpoints that receive `access_token`, `session_token`, `api_key`, `auth`, `signature`, or similar query parameters MUST reject the request unless that endpoint explicitly defines the field as a non-auth business parameter. Rejections SHOULD use `unauthenticated` or `invalid_param`, and sensitive query values must not be written to ordinary access logs.

Short-lived download URLs are allowed only as derived single-blob, single-purpose, revocable, short-expiry capability tokens. They MUST NOT be equivalent to a user session or long-lived capability.

### 3.1 Auth Discovery

Authentication and authorization servers may be separate. Service discovery SHOULD expose auth metadata such as:

```json
{
  "auth_metadata": {
    "oauth_issuer": "https://auth.example.com",
    "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
    "supported_auth_methods": ["passkey", "oidc", "device_pairing", "recovery_challenge"],
    "token_endpoint_auth_methods": ["private_key_jwt", "client_secret_basic"],
    "supported_grant_types": ["authorization_code", "refresh_token"],
    "did_binding_methods": ["session_grant", "did_http_signature"],
    "required_audience": "https://server.example/api/v1"
  }
}
```

OAuth/OIDC `sub`, email, username, or client id MUST NOT be used directly as `actor_id`, grant subject, or event sender. After login, the client or auth gateway MUST create a verifiable session grant, device binding, or DID proof that binds the login session to a DID principal / device.

Resource servers MUST verify token audience, issuer, expiry, nonce / replay protection, and session grant status. Passwords, email codes, and OIDC sessions can authorize protocol writes only after binding to DID / device through `did_binding_methods`.

## 4. Response Envelope

Successful responses SHOULD use the JSON object defined by each endpoint. Endpoints that need a common envelope SHOULD use:

```json
{
  "ok": true,
  "request_id": "cx:req:01JS0KE000000000000000000",
  "result": {}
}
```

Streaming endpoints MAY use newline-delimited JSON, SSE, or WebSocket frames, but each frame SHOULD remain an independent JSON object.

## 5. Error Envelope

Errors MUST use:

```json
{
  "ok": false,
  "error": {
    "code": "capability_denied",
    "message": "actor does not have entity.update on this task",
    "retry_after_ms": null,
    "details": {}
  },
  "request_id": "cx:req:01JS0KE000000000000000000"
}
```

`message` is diagnostic text and MUST NOT be used for stable client logic. Clients use `error.code` as the primary category.

### 5.1 Standard Error Codes

| code | HTTP status | Meaning |
| --- | ---: | --- |
| `bad_json` | 400 | JSON cannot be parsed. |
| `bad_query` | 400 | Query parameters cannot be parsed or violate schema. |
| `schema_violation` | 400 / 422 | Request does not match schema. |
| `missing_param` | 400 | Required parameter is missing. |
| `invalid_param` | 400 | Parameter value is invalid. |
| `unauthenticated` | 401 | Authentication material is missing or cannot be verified. |
| `auth_expired` | 401 | Session or grant expired. |
| `soft_logged_out` | 401 | Session was softly logged out; clients re-authenticate while preserving local device keys. |
| `invalid_signature` | 401 | Signature verification failed. |
| `capability_denied` | 403 | Capability or policy denies the request. |
| `claim_required` | 403 | Required claim / presentation is missing. |
| `not_found` | 404 | Target does not exist or is not visible to the caller. |
| `unrecognized_endpoint` | 404 | Path is under a protocol namespace but is not implemented or declared by this service. |
| `method_not_allowed` | 405 | HTTP method is not supported for a known path. |
| `conflict` | 409 | Generic state conflict. |
| `cas_conflict` | 409 | `expected_state_hash` mismatch. |
| `epoch_mismatch` | 409 | Encryption epoch is stale. |
| `duplicate_conflict` | 409 | Same idempotency key maps to different content. |
| `payload_too_large` | 413 | Request body or blob exceeds limits. |
| `quota_exceeded` | 413 / 402 | Storage, bandwidth, or compute quota exceeded. |
| `rate_limited` | 429 | Request rate exceeded. |
| `timeout` | 504 / 408 | Long-poll, frontier wait, or upstream request timed out. |
| `stale_frontier` | 409 / 503 | Local auth or sync frontier has not reached the requested point. |
| `sync_token_expired` | 400 / 410 | Client sync token expired; fall back to initial sync or snapshot bootstrap. |
| `unsupported_feature` | 501 | Service does not support the feature. |
| `internal_error` | 500 | Internal service error. |
| `temporarily_unavailable` | 503 | Service is temporarily unavailable. |

### 5.2 Unknown Paths And Methods

Requests under `/api/v1/*` and `/contrix/v1/*` MUST return standard JSON errors. Services MUST NOT return HTML, plaintext framework errors, or stack traces.

- Unknown or unimplemented paths MUST return HTTP `404` with `unrecognized_endpoint`.
- Known paths with unsupported HTTP methods MUST return HTTP `405` with `method_not_allowed` and SHOULD include the `Allow` header.
- These failures MUST terminate at routing time and must not trigger business logic, queue writes, expensive parsing, or observable side effects.
- Clients and federation peers use `describe.supported_operations`, OpenAPI, and feature discovery to determine support. They MUST NOT rely on non-standard 404 bodies.

## 6. Idempotency

All write endpoints MUST support idempotent retry.

Write requests SHOULD carry one of:

- `operation_id`
- `commit_id`
- `request_id`
- endpoint-specific `idempotency_key`

Rules:

- Same idempotency key plus same canonical request body MUST return a semantically equivalent result.
- Same idempotency key plus different canonical request body MUST return `duplicate_conflict`.
- Services SHOULD record the idempotency key and canonical request hash.
- Federation and service-to-service writes MUST bind the hash into the signature transcript or transaction replay cache.

## 7. Pagination And Cursors

List endpoints SHOULD use cursor pagination:

```json
{
  "items": [],
  "next_cursor": "cx:cursor:...",
  "has_more": false
}
```

`cursor` MUST be opaque. Clients MUST NOT parse it to infer ordering or permissions. Services MAY cap `limit`; requests above the cap SHOULD either use the maximum allowed value or return `invalid_param`.

## 8. Read-Your-Writes

Successful writes SHOULD return `sync_token`:

```json
{
  "status": "accepted",
  "commit_id": "cx:commit:01JS0KE000000000000000000",
  "sync_token": "cx:sync:..."
}
```

Read endpoints SHOULD accept:

```text
X-Contrix-Wait-For: <sync_token>
```

If the service reaches that causal frontier before timeout, it returns normally. Otherwise it SHOULD return `temporarily_unavailable`, `timeout`, or `stale_frontier` with the current frontier.

## 9. Rate Limit

Services MAY rate-limit by actor DID, device id, session id, source IP, Space id, endpoint, blob byte quota, and service DID.

`429 rate_limited` responses MUST set `Retry-After`. `503 temporarily_unavailable` SHOULD set `Retry-After` when recovery time is predictable. `Retry-After` uses standard HTTP seconds or HTTP date format.

The body MAY also include:

```json
{
  "retry_after_ms": 2000
}
```

When both values are present, clients MUST prefer `Retry-After`. `retry_after_ms` is for non-HTTP bindings and fine-grained diagnostics and SHOULD match the header. Clients and peer services MUST apply backoff per actor / service DID / endpoint to avoid retry amplification.

## 10. CORS And Browser Clients

Browser-facing services SHOULD support CORS preflight.

Recommended headers:

```text
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, Content-Digest, Digest, Idempotency-Key, X-Contrix-Wait-For, X-Contrix-Request-Id
Access-Control-Expose-Headers: Retry-After, Content-Digest, Digest, Content-Disposition, Content-Range, Location, X-Contrix-Request-Id
```

Services MUST NOT execute write logic for `OPTIONS` preflight requests. `Access-Control-Allow-Methods` SHOULD reflect the service's actual methods. Services MUST NOT allow `CONNECT` or `TRACE` through CORS.

Browser-accessible private endpoints must not rely on cookies as the only authentication mechanism; use `Authorization` headers or device-bound proof.

## 11. Version And Feature Discovery

Each service SHOULD expose a describe endpoint returning:

- `protocol_version`
- `service_type`
- `service_did`
- `supported_features`
- `supported_profiles`
- `auth_metadata`
- `max_body_bytes`
- `rate_limit_policy_ref`

Clients MUST enable optional features based on discovery and cannot assume every node supports the full protocol.

### 11.1 Discovery Cache And Delegation

Service endpoints in DID Documents are the authority for service identity and endpoint binding. Domain bootstrap MAY expose endpoint summaries through `/.well-known/contrix/server` or equivalent signed metadata, but receivers still MUST verify:

- HTTPS/TLS name matches the returned endpoint.
- service DID, DID Document service entry, describe response, and HTTP Message Signature bind to the same service.
- Space policy or actor / organization service delegation allows the service role.
- metadata hash / version is not revoked or expired by local policy.

Discovery results SHOULD be cached according to HTTP cache headers. Without explicit cache time, clients MAY use a default TTL up to 24 hours. Implementations SHOULD cap positive caches, with 48 hours as a recommended upper bound, and use shorter TTLs or exponential backoff for negative caches.

## 12. Security Requirements

Service implementations MUST:

- validate all inputs against schema
- verify signatures independently from capabilities
- verify content hashes for blobs, snapshots, and chunks
- prevent errors from leaking the existence of invisible resources
- enforce quotas for expensive queries
- protect public endpoints against abuse
- reject authentication material in URL query strings or paths
- use minimum-disclosure errors for unknown paths, wrong methods, invisible resources, and authorization failures
- apply allowlist / policy checks to external URLs used in downloads, redirects, discovery, and federation

Service implementations SHOULD:

- record auditable security logs without plaintext leakage
- require stronger authentication for administrative actions
- apply reputation / quarantine policy to federation writes
