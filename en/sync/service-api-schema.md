# Service API Schema (Unified OpenAPI)

## 1. Goal

`service-api-schema.md` is the protocol-level registry of canonical operations.

- HTTP/JSON is the reference binding.
- Other transports (gRPC, WebSocket, SSE, message queue, libp2p, IPC) must map to these same canonical operations.
- This file keeps a lightweight, executable-conformant set of operations and references schema locations (`api-conventions.md`, `service-http-binding.md`, `transport-bindings.md`).

## 2. Core rule

All canonical operations MUST use:

- canonical JSON encoding rules from `encoding.md`
- transport-independent operation ids in `Operation-Id` (or equivalent)
- the same idempotency, error, and pagination semantics described in `api-conventions.md`
- explicit `protocol_version` and `reducer_profile` capability surface in describe responses

## 3. Unified OpenAPI surface (reference snapshot)

```yaml
openapi: 3.1.0
info:
  title: Contrix Service API
  version: 0.2.0
  x-conformance-profile: cx.profile.conformance.v1
servers:
  - url: https://{host}/api/v1
    variables:
      host: { default: localhost }

components:
  parameters:
    SyncToken:
      name: next_batch
      in: query
      schema: { type: string }
    CXCursor:
      name: cursor
      in: query
      schema: { type: string }

paths:
  /server/describe:
    get:
      operationId: cx.describeService
      responses:
        '200': { description: service profile }

  /identity/resolve:
    post:
      operationId: cx.resolveIdentity
      requestBody:
        required: true
      responses:
        '200': { description: did document }

  /identity/document:
    get:
      operationId: cx.getIdentityDocument

  /identity/log:
    get:
      operationId: cx.getIdentityLog

  /identity/submit-did-op:
    post:
      operationId: cx.submitDidOp

  /repo/submit-commit:
    post:
      operationId: cx.submitCommit

  /repo/ops:
    post:
      operationId: cx.getOps

  /repo/sync:
    post:
      operationId: cx.syncRepo

  /sync/subscribe:
    get:
      operationId: cx.subscribeSync

  /index/query:
    post:
      operationId: cx.indexQuery

  /index/sync:
    post:
      operationId: cx.indexSync

  /directory/search-spaces:
    post:
      operationId: cx.directorySearchSpaces

  /directory/resolve-space:
    post:
      operationId: cx.directoryResolveSpace

  /directory/search-organizations:
    post:
      operationId: cx.directorySearchOrganizations

  /directory/resolve-organization:
    post:
      operationId: cx.directoryResolveOrganization

  /directory/search-actors:
    post:
      operationId: cx.directorySearchActors

  /directory/resolve-handle:
    post:
      operationId: cx.directoryResolveHandle

  /blob/upload:
    post:
      operationId: cx.uploadBlob

  /blob/get:
    get:
      operationId: cx.getBlob

  /device_messages/{txn_id}:
    put:
      operationId: cx.putToDeviceMessage

  /keys/upload:
    post:
      operationId: cx.uploadKeys

  /keys/query:
    post:
      operationId: cx.queryKeys

  /keys/claim:
    post:
      operationId: cx.claimKeys

  /authz/check:
    post:
      operationId: cx.checkAuthorization

  /contrix/v1/check:
    post:
      operationId: cx.policyServerCheck

  /sync:
    post:
      operationId: cx.clientSync
```

## 4. Canonical operation mapping

The following mapping binds each canonical operation to a transport implementation:

| Canonical Operation | Primary Binding | Alternate Binding |
| --- | --- | --- |
| cx.resolveIdentity | `POST /identity/resolve` | gRPC `ResolveIdentity` / MQ `identity.resolve` |
| cx.submitDidOp | `POST /identity/submit-did-op` | gRPC `SubmitDidOperation` / libp2p stream |
| cx.submitCommit / cx.syncRepo | `POST /repo/*` | gRPC `SubmitCommit` / Queue `repo.commit` |
| cx.clientSync | `POST /sync` | `GET /sync?since...` / WebSocket stream / SSE channel |
| cx.subscribeSync | `GET /sync/subscribe` | WebSocket frame `/sync/stream` / pubsub topic |
| cx.indexQuery / cx.indexSync | `POST /index/*` | gRPC `IndexQuery` / SSE search stream |
| cx.directorySearch* | `POST /directory/*` | gRPC discovery service |
| cx.putToDeviceMessage | `PUT /device_messages/{txn_id}` | MQ device-topic direct / ephemeral transport |
| cx.checkAuthorization | `POST /authz/check` | gRPC / local policy plugin callback |
| cx.policyServerCheck | `POST /contrix/v1/check` | policy plugin local call / REST mirror |

All operation ids MUST be stable across versions and treated as the conformance target.

## 5. Implementation guidance

- `service-api-schema.md` provides operation names and canonical binding contracts; request/response shapes are sourced from `service-surface.md`, `client-sync.md`, `policy-server.md`, and `device-crypto-verification.md`.
- Implementations SHOULD ship an OpenAPI document generated from this section and publish it at `/.well-known/contrix/openapi.yaml` (or equivalent signed reference in DID document service metadata).
- Tests for cross-transport interoperability should assert operation semantics are preserved even when payload transport changes.
- OpenAPI does **not** define protocol behavior alone; behavior remains in the canonical object, auth, and sync specs.

