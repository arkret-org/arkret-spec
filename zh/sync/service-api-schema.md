# Service API Schema（统一 OpenAPI）

## 1. 目标

`service-api-schema.md` 是 Contrix **canonical operation** 的统一服务清单。  
HTTP/JSON 是参考绑定；同一操作必须可以无语义损失映射到其它 transport（gRPC、WebSocket、SSE、MQ、libp2p、IPC）。

本文件同时承担：

- `operation_id` 稳定性定义
- 各服务角色最小能力边界
- OpenAPI 与 transport 映射的一致性锚点

请求/响应形状、错误、分页、幂等、同步语义由 `api-conventions.md`、`service-surface.md`、`client-sync.md`、`service-http-binding.md` 共同约束。

## 2. 统一约定

- 所有 canonical operation 均使用 `encoding.md` 的 canonical JSON 与签名输入规则。
- 关键行为不由路径决定，而由 `operation_id` 与数据语义决定。
- Contrix 协议字段和 feature discovery 使用 `operation_id`，取值使用 `cx.<namespace>.<lower_snake_case>`。OpenAPI 3.1 标准字段名仍为 `operationId`，但其值 MUST 等于对应的 Contrix `operation_id`。
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

| 分组 | `operation_id` 前缀 | 默认 HTTP 命名空间 |
| --- | --- | --- |
| 服务发现 | `cx.server.*` | `/server/*` |
| 身份与 registry | `cx.identity.*` | `/identity/*` |
| Repo 与 commit | `cx.repo.*` | `/repo/*` |
| 客户端同步与 Space 同步 | `cx.sync.*` | `/sync/*` |
| 联邦 | `cx.federation.*` | `/federation/*` |
| 查询与投影 | `cx.index.*` | `/index/*` |
| 目录发现 | `cx.directory.*` | `/directory/*` |
| Blob / media | `cx.blob.*` | `/blob/*` |
| 推送 | `cx.push.*` | `/push/*` |
| 设备加密 | `cx.device_messages.*`、`cx.keys.*` | `/device_messages/*`、`/keys/*` |
| 授权与策略 | `cx.authz.*`、`cx.policy.*` | `/authz/*`、`/contrix/v1/check` |
| 媒体服务 | `cx.media.*` | `/contrix/v1/ice-config` |
| 审核 | `cx.moderation.*` | `/moderation/*` |
| Applet | `cx.applet.*` | `/applet/*` |

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
      operationId: cx.server.describe
      responses:
        '200': { description: service profile }

  /identity/resolve:
    post:
      operationId: cx.identity.resolve
  /identity/describe:
    get:
      operationId: cx.identity.describe_registry
  /identity/document:
    get:
      operationId: cx.identity.get_document
  /identity/log:
    get:
      operationId: cx.identity.get_log
  /identity/submit-did-op:
    post:
      operationId: cx.identity.submit_did_op
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
  /repo/ops:
    post:
      operationId: cx.repo.get_ops
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
  /federation/push-ops:
    post:
      operationId: cx.federation.push_ops
  /federation/pull-ops:
    get:
      operationId: cx.federation.pull_ops
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
  /index/sync:
    post:
      operationId: cx.index.sync
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

## 4. Canonical 操作与 transport 映射

| `operation_id` | HTTP 参考绑定 | 其他 transport 映射 |
| --- | --- | --- |
| `cx.identity.resolve` | `POST /identity/resolve` | gRPC `ResolveIdentity` / MQ `identity.resolve` |
| `cx.identity.submit_did_op` | `POST /identity/submit-did-op` | gRPC `SubmitDidOperation` / libp2p stream |
| `cx.identity.get_document` / `cx.identity.get_log` / `cx.identity.get_receipts` | `GET /identity/document`, `GET /identity/log`, `GET /identity/receipts` | gRPC Identity Registry / witness query |
| `cx.repo.submit_commit` | `POST /repo/submit-commit` | gRPC `SubmitCommit` / 队列 `repo.commit` |
| `cx.repo.get_ops` / `cx.repo.sync` / `cx.repo.list_commits` | `POST /repo/ops`, `POST /repo/sync`, `GET /repo/commits` | gRPC `GetOps` / `SyncRepo` |
| `cx.sync.client_sync` | `POST /sync` | WebSocket/SSE client sync channel / `/sync?since...` |
| `cx.sync.subscribe` | `GET /sync/subscribe` | WebSocket/SSE stream / pubsub topic |
| `cx.sync.backfill` / `cx.sync.get_snapshot_head` | `GET /sync/backfill`, `GET /sync/snapshot-head` | gRPC `BackfillSync` / snapshot pointer |
| `cx.federation.transaction` / `cx.federation.push_ops` / `cx.federation.pull_ops` | `PUT /federation/transactions/{txn_id}`, `POST /federation/push-ops`, `GET /federation/pull-ops` | gRPC Federation Service / signed MQ transaction |
| `cx.index.query` / `cx.index.sync` / `cx.index.search` | `POST /index/*` | gRPC `IndexQuery` / SSE 查询流 |
| `cx.directory.search_*` / `cx.directory.resolve_*` | `POST /directory/*`, `GET /directory/search-users` | gRPC Discovery Service |
| `cx.blob.upload` / `cx.blob.head` / `cx.blob.get` | `POST /blob/upload`, `HEAD/GET /blob/get` | Object-store signed URL binding / gRPC blob service |
| `cx.push.register_device` / `cx.push.notify` | `POST /push/register-device`, `POST /push/notify` | APNs/FCM adapter / MQ wakeup topic |
| `cx.device_messages.put` / `cx.device_messages.get` | `PUT /device_messages/{txn_id}`, `GET /device_messages` | MQ device topic / 本地 IPC |
| `cx.keys.upload` / `cx.keys.query` / `cx.keys.claim` | `POST /keys/upload`, `POST /keys/query`, `POST /keys/claim` | E2EE key service binding |
| `cx.authz.check` / `cx.authz.get_effective_grants` / `cx.authz.get_invites` | `POST /authz/check`, `GET /authz/effective-grants`, `GET /authz/invites` | gRPC / policy 插件回调 |
| `cx.policy.check` | `POST /contrix/v1/check` | policy 本地调用 |
| `cx.media.ice_config` | `POST /contrix/v1/ice-config` | Media service / TURN credential adapter |
| `cx.moderation.report` | `POST /moderation/report` | Moderation queue / local compliance workflow |
| `cx.applet.transaction` / `cx.applet.query_actor` / `cx.applet.query_space` | `PUT /applet/transactions/{txn_id}`, `GET /applet/actors/{actor_id}`, `GET /applet/spaces/{space_id_or_alias}` | Applet webhook / bridge adapter |

## 5. 落地要求

- 任何节点都应能发布一份可下载的 OpenAPI 文档（建议路径 `/.well-known/contrix/openapi.yaml`），并在 service DID metadata 中声明版本和 hash。
- 实现必须保持 `operation_id` 在演进中稳定；若请求字段名变更，必须保留兼容版本或通过 profile 明确协商。
- OpenAPI 只定义形态，不定义核心语义。核心语义仍由本协议对象模型、授权状态、签名、同步与加密规范给出。
- `/contrix/v1/*` 是服务本地绝对路径，不挂在 `/api/v1` 下。生成 OpenAPI 时必须为这些 path 使用 path-level `servers` 或拆成独立文档。
- `POST /sync` 是客户端聚合增量同步；`GET /sync/subscribe` 是 Space operation 流订阅；`GET /sync/backfill` 是历史回补。三者不得互相替代，也不得新增未声明的 canonical sync endpoint。
