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

### 2.1 Operation Groups

The unified API schema is grouped by canonical operation. HTTP paths are only the default binding:

| Group | Canonical operation prefix | Default HTTP namespace |
| --- | --- | --- |
| Service discovery | `cx.describe*` | `/server/*` |
| Identity and registry | `cx.identity*`, `cx.resolveIdentity` | `/identity/*` |
| Repo and commit | `cx.repo*`, `cx.submitCommit`, `cx.getOps` | `/repo/*` |
| Client and Space sync | `cx.clientSync`, `cx.sync*` | `/sync/*` |
| Federation | `cx.federation*` | `/federation/*` |
| Query and projection | `cx.index*` | `/index/*` |
| Directory discovery | `cx.directory*` | `/directory/*` |
| Blob / media | `cx.blob*`, `cx.uploadBlob`, `cx.getBlob` | `/blob/*` |
| Push | `cx.push*` | `/push/*` |
| Device crypto | `cx.device*`, `cx.keys*` | `/device_messages/*`, `/keys/*` |
| Authorization and policy | `cx.authz*`, `cx.policy*` | `/authz/*`, `/contrix/v1/check` |
| Moderation | `cx.moderation*` | `/moderation/*` |
| Applet | `cx.applet*` | `/applet/*` |

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
  /identity/describe:
    get:
      operationId: cx.describeIdentityRegistry

  /identity/document:
    get:
      operationId: cx.getIdentityDocument

  /identity/log:
    get:
      operationId: cx.getIdentityLog

  /identity/submit-did-op:
    post:
      operationId: cx.submitDidOp
  /identity/receipts:
    get:
      operationId: cx.getIdentityReceipts

  /repo/describe:
    get:
      operationId: cx.describeRepo
  /repo/submit-commit:
    post:
      operationId: cx.submitCommit
  /repo/commits:
    get:
      operationId: cx.listRepoCommits
  /repo/commit:
    get:
      operationId: cx.getRepoCommit

  /repo/ops:
    post:
      operationId: cx.getOps

  /repo/sync:
    post:
      operationId: cx.syncRepo

  /sync:
    post:
      operationId: cx.clientSync
  /sync/describe:
    get:
      operationId: cx.describeSync
  /sync/subscribe:
    get:
      operationId: cx.subscribeSync
  /sync/backfill:
    get:
      operationId: cx.backfillSync
  /sync/snapshot-head:
    get:
      operationId: cx.getSyncSnapshotHead

  /federation/transactions/{txn_id}:
    put:
      operationId: cx.federationTransaction
  /federation/push-ops:
    post:
      operationId: cx.federationPushOps
  /federation/pull-ops:
    get:
      operationId: cx.federationPullOps
  /federation/space-members:
    get:
      operationId: cx.federationSpaceMembers
  /federation/verify-actor:
    post:
      operationId: cx.federationVerifyActor

  /index/describe:
    get:
      operationId: cx.describeIndex
  /index/entity:
    get:
      operationId: cx.indexGetEntity
  /index/query:
    post:
      operationId: cx.indexQuery

  /index/sync:
    post:
      operationId: cx.indexSync
  /index/thread:
    get:
      operationId: cx.indexThread
  /index/notifications:
    get:
      operationId: cx.indexNotifications
  /index/inbox:
    get:
      operationId: cx.indexInbox
  /index/search:
    post:
      operationId: cx.indexSearch
  /index/space-hierarchy:
    get:
      operationId: cx.indexSpaceHierarchy

  /directory/describe:
    get:
      operationId: cx.describeDirectory
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
    head:
      operationId: cx.headBlob
    get:
      operationId: cx.getBlob

  /push/register-device:
    post:
      operationId: cx.pushRegisterDevice
  /push/unregister-device:
    post:
      operationId: cx.pushUnregisterDevice
  /push/notify:
    post:
      operationId: cx.pushNotify

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
  /moderation/report:
    post:
      operationId: cx.moderationReport

  /applet/ping:
    get:
      operationId: cx.appletPing
  /applet/describe:
    get:
      operationId: cx.appletDescribe
  /applet/transactions/{txn_id}:
    put:
      operationId: cx.appletTransaction
  /applet/actors/{actor_id}:
    get:
      operationId: cx.appletQueryActor
  /applet/spaces/{space_id_or_alias}:
    get:
      operationId: cx.appletQuerySpace
  /applet/protocols/{protocol}:
    get:
      operationId: cx.appletProtocolMetadata
  /applet/third_party/users:
    get:
      operationId: cx.appletThirdPartyUsers
  /applet/third_party/locations:
    get:
      operationId: cx.appletThirdPartyLocations
```

## 4. Canonical operation mapping

The following mapping binds each canonical operation to a transport implementation:

| Canonical Operation | Primary Binding | Alternate Binding |
| --- | --- | --- |
| cx.resolveIdentity | `POST /identity/resolve` | gRPC `ResolveIdentity` / MQ `identity.resolve` |
| cx.submitDidOp | `POST /identity/submit-did-op` | gRPC `SubmitDidOperation` / libp2p stream |
| cx.getIdentityDocument / cx.getIdentityLog / cx.getIdentityReceipts | `GET /identity/document`, `GET /identity/log`, `GET /identity/receipts` | gRPC Identity Registry / witness query |
| cx.submitCommit | `POST /repo/submit-commit` | gRPC `SubmitCommit` / Queue `repo.commit` |
| cx.getOps / cx.syncRepo / cx.listRepoCommits | `POST /repo/ops`, `POST /repo/sync`, `GET /repo/commits` | gRPC `GetOps` / `SyncRepo` |
| cx.clientSync | `POST /sync` | WebSocket/SSE client sync channel / `GET /sync?since...` |
| cx.subscribeSync | `GET /sync/subscribe` | WebSocket/SSE stream / pubsub topic |
| cx.backfillSync / cx.getSyncSnapshotHead | `GET /sync/backfill`, `GET /sync/snapshot-head` | gRPC `BackfillSync` / snapshot pointer |
| cx.federationTransaction / cx.federationPushOps / cx.federationPullOps | `PUT /federation/transactions/{txn_id}`, `POST /federation/push-ops`, `GET /federation/pull-ops` | gRPC Federation Service / signed MQ transaction |
| cx.indexQuery / cx.indexSync / cx.indexSearch | `POST /index/*` | gRPC `IndexQuery` / SSE search stream |
| cx.directorySearch* | `POST /directory/*` | gRPC discovery service |
| cx.uploadBlob / cx.headBlob / cx.getBlob | `POST /blob/upload`, `HEAD/GET /blob/get` | Object-store signed URL binding / gRPC blob service |
| cx.pushRegisterDevice / cx.pushNotify | `POST /push/register-device`, `POST /push/notify` | APNs/FCM adapter / MQ wakeup topic |
| cx.putToDeviceMessage | `PUT /device_messages/{txn_id}` | MQ device-topic direct / ephemeral transport |
| cx.uploadKeys / cx.queryKeys / cx.claimKeys | `POST /keys/upload`, `POST /keys/query`, `POST /keys/claim` | E2EE key service binding |
| cx.checkAuthorization | `POST /authz/check` | gRPC / local policy plugin callback |
| cx.policyServerCheck | `POST /contrix/v1/check` | policy plugin local call / REST mirror |
| cx.moderationReport | `POST /moderation/report` | moderation queue / local compliance workflow |
| cx.appletTransaction / cx.appletQueryActor / cx.appletQuerySpace | `PUT /applet/transactions/{txn_id}`, `GET /applet/actors/{actor_id}`, `GET /applet/spaces/{space_id_or_alias}` | Applet webhook / bridge adapter |

All operation ids MUST be stable across versions and treated as the conformance target.

## 5. Implementation guidance

- `service-api-schema.md` provides operation names and canonical binding contracts; request/response shapes are sourced from `service-surface.md`, `client-sync.md`, `policy-server.md`, and `device-crypto-verification.md`.
- Implementations SHOULD ship an OpenAPI document generated from this section and publish it at `/.well-known/contrix/openapi.yaml` (or equivalent signed reference in DID document service metadata).
- Tests for cross-transport interoperability should assert operation semantics are preserved even when payload transport changes.
- OpenAPI does **not** define protocol behavior alone; behavior remains in the canonical object, auth, and sync specs.
- `POST /sync` is client aggregate incremental sync; `GET /sync/subscribe` is Space operation stream subscription; `GET /sync/backfill` is historical backfill. They MUST NOT be treated as interchangeable sync endpoints.

