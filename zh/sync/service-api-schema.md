# Service API Schema（统一 OpenAPI）

## 1. 目标

`service-api-schema.md` 是 Contrix **canonical operation** 的统一服务清单。  
HTTP/JSON 是参考绑定；同一操作必须可以无语义损失映射到其它 transport（gRPC、WebSocket、SSE、MQ、libp2p、IPC）。

本文件同时承担：

- operation id 稳定性定义
- 各服务角色最小能力边界
- OpenAPI 与 transport 映射的一致性锚点

请求/响应形状、错误、分页、幂等、同步语义由 `api-conventions.md`、`service-surface.md`、`client-sync.md`、`service-http-binding.md` 共同约束。

## 2. 统一约定

- 所有 canonical operation 均使用 `encoding.md` 的 canonical JSON 与签名输入规则。
- 关键行为不由路径决定，而由 operation id 与数据语义决定。
- 服务发现应返回至少：
  - `protocol_version`
  - `supported_profiles`
  - `supported_features`
  - `supported_bindings`
  - `supported_operations`
  - `supported_reducer_profiles`
  - `supported_schema_profiles`

### 2.1 操作分组

统一 API schema 按 canonical operation 分组。HTTP 路径只是默认 binding：

| 分组 | Canonical operation 前缀 | 默认 HTTP 命名空间 |
| --- | --- | --- |
| 服务发现 | `cx.describe*` | `/server/*` |
| 身份与 registry | `cx.identity*`、`cx.resolveIdentity` | `/identity/*` |
| Repo 与 commit | `cx.repo*`、`cx.submitCommit`、`cx.getOps` | `/repo/*` |
| 客户端同步与 Space 同步 | `cx.clientSync`、`cx.sync*` | `/sync/*` |
| 联邦 | `cx.federation*` | `/federation/*` |
| 查询与投影 | `cx.index*` | `/index/*` |
| 目录发现 | `cx.directory*` | `/directory/*` |
| Blob / media | `cx.blob*`、`cx.uploadBlob`、`cx.getBlob` | `/blob/*` |
| 推送 | `cx.push*` | `/push/*` |
| 设备加密 | `cx.device*`、`cx.keys*` | `/device_messages/*`、`/keys/*` |
| 授权与策略 | `cx.authz*`、`cx.policy*` | `/authz/*`、`/contrix/v1/check` |
| 审核 | `cx.moderation*` | `/moderation/*` |
| Applet | `cx.applet*` | `/applet/*` |

## 3. OpenAPI 参考快照（简化版）

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

## 4. Canonical 操作与 transport 映射

| Canonical Operation | HTTP 参考绑定 | 其他 transport 映射 |
| --- | --- | --- |
| `cx.resolveIdentity` | `POST /identity/resolve` | gRPC `ResolveIdentity` / MQ `identity.resolve` |
| `cx.submitDidOp` | `POST /identity/submit-did-op` | gRPC `SubmitDidOperation` / libp2p stream |
| `cx.getIdentityDocument` / `cx.getIdentityLog` / `cx.getIdentityReceipts` | `GET /identity/document`, `GET /identity/log`, `GET /identity/receipts` | gRPC Identity Registry / witness query |
| `cx.submitCommit` | `POST /repo/submit-commit` | gRPC `SubmitCommit` / 队列 `repo.commit` |
| `cx.getOps` / `cx.syncRepo` / `cx.listRepoCommits` | `POST /repo/ops`, `POST /repo/sync`, `GET /repo/commits` | gRPC `GetOps` / `SyncRepo` |
| `cx.clientSync` | `POST /sync` | WebSocket/SSE client sync channel / `/sync?since...` |
| `cx.subscribeSync` | `GET /sync/subscribe` | WebSocket/SSE stream / pubsub topic |
| `cx.backfillSync` / `cx.getSyncSnapshotHead` | `GET /sync/backfill`, `GET /sync/snapshot-head` | gRPC `BackfillSync` / snapshot pointer |
| `cx.federationTransaction` / `cx.federationPushOps` / `cx.federationPullOps` | `PUT /federation/transactions/{txn_id}`, `POST /federation/push-ops`, `GET /federation/pull-ops` | gRPC Federation Service / signed MQ transaction |
| `cx.indexQuery` / `cx.indexSync` / `cx.indexSearch` | `POST /index/*` | gRPC `IndexQuery` / SSE 查询流 |
| `cx.directorySearch*` | `POST /directory/*` | gRPC Discovery Service |
| `cx.uploadBlob` / `cx.headBlob` / `cx.getBlob` | `POST /blob/upload`, `HEAD/GET /blob/get` | Object-store signed URL binding / gRPC blob service |
| `cx.pushRegisterDevice` / `cx.pushNotify` | `POST /push/register-device`, `POST /push/notify` | APNs/FCM adapter / MQ wakeup topic |
| `cx.putToDeviceMessage` | `PUT /device_messages/{txn_id}` | MQ device topic / 本地 IPC |
| `cx.uploadKeys` / `cx.queryKeys` / `cx.claimKeys` | `POST /keys/upload`, `POST /keys/query`, `POST /keys/claim` | E2EE key service binding |
| `cx.checkAuthorization` | `POST /authz/check` | gRPC / policy 插件回调 |
| `cx.policyServerCheck` | `POST /contrix/v1/check` | policy 本地调用 |
| `cx.moderationReport` | `POST /moderation/report` | Moderation queue / local compliance workflow |
| `cx.appletTransaction` / `cx.appletQueryActor` / `cx.appletQuerySpace` | `PUT /applet/transactions/{txn_id}`, `GET /applet/actors/{actor_id}`, `GET /applet/spaces/{space_id_or_alias}` | Applet webhook / bridge adapter |

## 5. 落地要求

- 任何节点都应能发布一份可下载的 OpenAPI 文档（建议路径 `/.well-known/contrix/openapi.yaml`），并在 service DID metadata 中声明版本和 hash。
- 实现必须保持 operation id 在演进中稳定；若请求字段名变更，必须保留兼容版本或通过 profile 明确协商。
- OpenAPI 只定义形态，不定义核心语义。核心语义仍由本协议对象模型、授权状态、签名、同步与加密规范给出。
- `POST /sync` 是客户端聚合增量同步；`GET /sync/subscribe` 是 Space operation 流订阅；`GET /sync/backfill` 是历史回补。三者不得互相替代，也不得新增未声明的 canonical sync endpoint。
