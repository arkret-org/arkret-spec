# Service API Schema (Unified OpenAPI)

## 1. Goal

`service-api-schema.md` is the protocol-level registry of canonical operations.

- HTTP/JSON is the reference binding.
- Other transports (gRPC, WebSocket, SSE, message queue, libp2p, IPC) must map to these same canonical operations.
- This file keeps a lightweight, executable-conformant set of operations and references schema locations (`api-conventions.md`, `service-http-binding.md`, `transport-bindings.md`).

## 2. Core rule

All canonical operations MUST use:

- canonical JSON encoding rules from `encoding.md`
- transport-independent `operation_id` values
- the same idempotency, error, and pagination semantics described in `api-conventions.md`
- explicit `protocol_version` and `reducer_profile` capability surface in describe responses
- Contrix protocol fields and feature discovery use `operation_id`; values use `cx.<namespace>.<lower_snake_case>`. The OpenAPI 3.1 field name remains `operationId`, but its value MUST equal the Contrix `operation_id`.

### 2.1 Operation Groups

The unified API schema is grouped by canonical operation. HTTP paths are only the default binding:

| Group | `operation_id` prefix | Default HTTP namespace |
| --- | --- | --- |
| Service discovery | `cx.server.*` | `/server/*` |
| Identity and registry | `cx.identity.*` | `/identity/*` |
| Repo and commit | `cx.repo.*` | `/repo/*` |
| Client and Space sync | `cx.sync.*` | `/sync/*` |
| Federation | `cx.federation.*` | `/federation/*` |
| Query and projection | `cx.index.*` | `/index/*` |
| Directory discovery | `cx.directory.*` | `/directory/*` |
| Blob / media | `cx.blob.*` | `/blob/*` |
| Push | `cx.push.*` | `/push/*` |
| Device crypto | `cx.device_messages.*`, `cx.keys.*` | `/device_messages/*`, `/keys/*` |
| Authorization and policy | `cx.authz.*`, `cx.policy.*` | `/authz/*`, `/contrix/v1/check` |
| Media services | `cx.media.*` | `/contrix/v1/ice-config` |
| Moderation | `cx.moderation.*` | `/moderation/*` |
| Applet | `cx.applet.*` | `/applet/*` |

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
      operationId: cx.server.describe
      responses:
        '200': { description: service profile }

  /identity/resolve:
    post:
      operationId: cx.identity.resolve
      requestBody:
        required: true
      responses:
        '200': { description: did document }
  /identity/describe:
    get:
      operationId: cx.identity.describe_registry

  /identity/document:
    get:
      operationId: cx.identity.get_document

  /identity/log:
    get:
      operationId: cx.identity.get_log

  /identity/submit-did-operation:
    post:
      operationId: cx.identity.submit_did_operation
  /identity/receipts:
    get:
      operationId: cx.identity.get_receipts

  /repo/describe:
    get:
      operationId: cx.repo.describe
  /repo/submit-commit:
    post:
      operationId: cx.repo.submit_commit
  /repo/commits:
    get:
      operationId: cx.repo.list_commits
  /repo/commit:
    get:
      operationId: cx.repo.get_commit

  /repo/operations:
    post:
      operationId: cx.repo.get_operations

  /repo/sync:
    post:
      operationId: cx.repo.sync

  /sync:
    post:
      operationId: cx.sync.client_sync
  /sync/describe:
    get:
      operationId: cx.sync.describe
  /sync/subscribe:
    get:
      operationId: cx.sync.subscribe
  /sync/backfill:
    get:
      operationId: cx.sync.backfill
  /sync/snapshot-head:
    get:
      operationId: cx.sync.get_snapshot_head

  /federation/transactions/{txn_id}:
    put:
      operationId: cx.federation.transaction
  /federation/push-operations:
    post:
      operationId: cx.federation.push_operations
  /federation/pull-operations:
    get:
      operationId: cx.federation.pull_operations
  /federation/space-members:
    get:
      operationId: cx.federation.space_members
  /federation/verify-actor:
    post:
      operationId: cx.federation.verify_actor

  /index/describe:
    get:
      operationId: cx.index.describe
  /index/entity:
    get:
      operationId: cx.index.get_entity
  /index/query:
    post:
      operationId: cx.index.query

  /index/thread:
    get:
      operationId: cx.index.thread
  /index/notifications:
    get:
      operationId: cx.index.notifications
  /index/inbox:
    get:
      operationId: cx.index.inbox
  /index/search:
    post:
      operationId: cx.index.search
  /index/space-hierarchy:
    get:
      operationId: cx.index.space_hierarchy

  /directory/describe:
    get:
      operationId: cx.directory.describe
  /directory/search-spaces:
    post:
      operationId: cx.directory.search_spaces

  /directory/resolve-space:
    post:
      operationId: cx.directory.resolve_space

  /directory/search-organizations:
    post:
      operationId: cx.directory.search_organizations

  /directory/resolve-organization:
    post:
      operationId: cx.directory.resolve_organization

  /directory/search-actors:
    post:
      operationId: cx.directory.search_actors
  /directory/search-users:
    get:
      operationId: cx.directory.search_users

  /directory/resolve-handle:
    post:
      operationId: cx.directory.resolve_handle

  /blob/upload:
    post:
      operationId: cx.blob.upload

  /blob/get:
    head:
      operationId: cx.blob.head
    get:
      operationId: cx.blob.get

  /push/register-device:
    post:
      operationId: cx.push.register_device
  /push/unregister-device:
    post:
      operationId: cx.push.unregister_device
  /push/notify:
    post:
      operationId: cx.push.notify

  /device_messages/{txn_id}:
    put:
      operationId: cx.device_messages.put
  /device_messages:
    get:
      operationId: cx.device_messages.get

  /keys/upload:
    post:
      operationId: cx.keys.upload

  /keys/query:
    post:
      operationId: cx.keys.query

  /keys/claim:
    post:
      operationId: cx.keys.claim

  /authz/check:
    post:
      operationId: cx.authz.check
  /authz/effective-grants:
    get:
      operationId: cx.authz.get_effective_grants
  /authz/invites:
    get:
      operationId: cx.authz.get_invites

  /contrix/v1/check:
    servers:
      - url: https://{host}
    post:
      operationId: cx.policy.check
  /contrix/v1/ice-config:
    servers:
      - url: https://{host}
    post:
      operationId: cx.media.ice_config
  /moderation/report:
    post:
      operationId: cx.moderation.report

  /applet/ping:
    get:
      operationId: cx.applet.ping
  /applet/describe:
    get:
      operationId: cx.applet.describe
  /applet/transactions/{txn_id}:
    put:
      operationId: cx.applet.transaction
  /applet/actors/{actor_id}:
    get:
      operationId: cx.applet.query_actor
  /applet/spaces/{space_id_or_alias}:
    get:
      operationId: cx.applet.query_space
  /applet/protocols/{protocol}:
    get:
      operationId: cx.applet.protocol_metadata
  /applet/third_party/users:
    get:
      operationId: cx.applet.third_party_users
  /applet/third_party/locations:
    get:
      operationId: cx.applet.third_party_locations
```

## 4. Canonical operation mapping

The following mapping binds each canonical operation to a transport implementation:

| `operation_id` | Primary Binding | Alternate Binding |
| --- | --- | --- |
| `cx.identity.resolve` | `POST /identity/resolve` | gRPC `ResolveIdentity` / MQ `identity.resolve` |
| `cx.identity.submit_did_operation` | `POST /identity/submit-did-operation` | gRPC `SubmitDidOperation` / libp2p stream |
| `cx.identity.get_document` / `cx.identity.get_log` / `cx.identity.get_receipts` | `GET /identity/document`, `GET /identity/log`, `GET /identity/receipts` | gRPC Identity Registry / witness query |
| `cx.repo.submit_commit` | `POST /repo/submit-commit` | gRPC `SubmitCommit` / Queue `repo.commit` |
| `cx.repo.get_operations` / `cx.repo.sync` / `cx.repo.list_commits` | `POST /repo/operations`, `POST /repo/sync`, `GET /repo/commits` | gRPC `GetOperations` / `SyncRepo` |
| `cx.sync.client_sync` | `POST /sync` | WebSocket/SSE client sync channel / `GET /sync?since...` |
| `cx.sync.subscribe` | `GET /sync/subscribe` | WebSocket/SSE stream / pubsub topic |
| `cx.sync.backfill` / `cx.sync.get_snapshot_head` | `GET /sync/backfill`, `GET /sync/snapshot-head` | gRPC `BackfillSync` / snapshot pointer |
| `cx.federation.transaction` / `cx.federation.push_operations` / `cx.federation.pull_operations` | `PUT /federation/transactions/{txn_id}`, `POST /federation/push-operations`, `GET /federation/pull-operations` | gRPC Federation Service / signed MQ transaction |
| `cx.index.query` / `cx.index.search` | `POST /index/*` | gRPC `IndexQuery` / SSE search stream |
| `cx.directory.search_*` / `cx.directory.resolve_*` | `POST /directory/*`, `GET /directory/search-users` | gRPC discovery service |
| `cx.blob.upload` / `cx.blob.head` / `cx.blob.get` | `POST /blob/upload`, `HEAD/GET /blob/get` | Object-store signed URL binding / gRPC blob service |
| `cx.push.register_device` / `cx.push.notify` | `POST /push/register-device`, `POST /push/notify` | APNs/FCM adapter / MQ wakeup topic |
| `cx.device_messages.put` / `cx.device_messages.get` | `PUT /device_messages/{txn_id}`, `GET /device_messages` | MQ device-topic direct / ephemeral transport |
| `cx.keys.upload` / `cx.keys.query` / `cx.keys.claim` | `POST /keys/upload`, `POST /keys/query`, `POST /keys/claim` | E2EE key service binding |
| `cx.authz.check` / `cx.authz.get_effective_grants` / `cx.authz.get_invites` | `POST /authz/check`, `GET /authz/effective-grants`, `GET /authz/invites` | gRPC / local policy plugin callback |
| `cx.policy.check` | `POST /contrix/v1/check` | policy plugin local call / REST mirror |
| `cx.media.ice_config` | `POST /contrix/v1/ice-config` | Media service / TURN credential adapter |
| `cx.moderation.report` | `POST /moderation/report` | moderation queue / local compliance workflow |
| `cx.applet.transaction` / `cx.applet.query_actor` / `cx.applet.query_space` | `PUT /applet/transactions/{txn_id}`, `GET /applet/actors/{actor_id}`, `GET /applet/spaces/{space_id_or_alias}` | Applet webhook / bridge adapter |

All `operation_id` values MUST be stable across versions and treated as the conformance target.

## 5. Implementation guidance

- `service-api-schema.md` provides operation names and canonical binding contracts; request/response shapes are sourced from `service-surface.md`, `client-sync.md`, `policy-server.md`, and `device-crypto-verification.md`.
- Implementations SHOULD ship an OpenAPI document generated from this section and publish it at `/.well-known/contrix/openapi.yaml` (or equivalent signed reference in DID document service metadata).
- Tests for cross-transport interoperability should assert operation semantics are preserved even when payload transport changes.
- OpenAPI does **not** define protocol behavior alone; behavior remains in the canonical object, auth, and sync specs.
- `/contrix/v1/*` is a service-local absolute path, not a child of `/api/v1`. Generated OpenAPI documents must use path-level `servers` for these paths or publish them in a separate document.
- `POST /sync` is client aggregate incremental sync; `GET /sync/subscribe` is Space operation stream subscription; `GET /sync/backfill` is historical backfill. They MUST NOT be treated as interchangeable sync endpoints.
- Generated OpenAPI MUST reference the common error envelope and include standard responses for `404 unrecognized_endpoint`, `405 method_not_allowed`, `429 rate_limited`, and `503 temporarily_unavailable`.
- OpenAPI security schemes MUST NOT define query-string token authentication. Protected endpoints may only use headers, signatures, mTLS, signed proof bodies, or equivalent transport bindings.
- Blob / media endpoint schemas MUST explicitly declare `Content-Type`, `Content-Disposition`, `Range`, `Content-Range`, `Location`, and cache header behavior so headers cannot leak invisible resources.


