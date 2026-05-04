# Service API Schema（统一 OpenAPI）

## 1. 目标

`service-api-schema.md` 是 Contrix **canonical operation** 的说明性服务清单。  
HTTP/JSON 是参考绑定；同一操作必须可以无语义损失映射到其它 transport（gRPC、WebSocket、SSE、MQ、libp2p、IPC）。

本文件同时承担：

- `operation_id` 稳定性与分层说明
- 各服务角色最小能力边界
- OpenAPI 与 transport 映射的一致性锚点

请求/响应形状、错误、分页、幂等、同步语义由 `api-conventions.md`、`service-surface.md`、`client-sync.md`、`service-http-binding.md` 共同约束。

规范权威关系：

- `artifacts/registry/contract-catalog.json#operation_registry` 是 operation contract 的 canonical source。
- `artifacts/registry/operation-registry.json` 是由 canonical source 生成的机器视图，供实现、SDK、lint 与 transport adapter 直接消费。
- `contrix-service-api.openapi.yaml` 是 HTTP binding 的规范性 shape 文档；它必须与 operation registry 对齐，但不是第二套 operation namespace。
- 本文是说明性地图与治理说明；完整枚举以 canonical source 与生成物为准。

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
| Events | `cx.events.*` | `/events/*` |
| 客户端同步与 Space 同步 | `cx.sync.*` | `/sync/*` |
| 联邦 | `cx.federation.*` | `/federation/*` |
| 目录发现 | `cx.directory.*` | `/directory/*` |
| Blob / media | `cx.blob.*` | `/blob/*` |
| 推送 | `cx.push.*` | `/push/*` |
| 设备加密 | `cx.device_messages.*`、`cx.keys.*` | `/device_messages/*`、`/keys/*` |
| 授权与策略 | `cx.authz.*`、`cx.policy.*` | `/authz/*`、`/contrix/v1/check` |
| 媒体服务 | `cx.media.*` | `/contrix/v1/ice-config` |
| 审核 | `cx.moderation.*` | `/moderation/*` |
| Applet | `cx.applet.*` | `/applet/*` |
| MIMI 互操作 | `cx.mimi.*` | `/mimi/*` |
| 账户与登录 | `cx.account.*` | `/auth/account/*` |
| 管理员与运维 | `cx.admin.*` | `/admin/*` |

## 3. OpenAPI 参考快照（非穷尽示例）

以下 YAML 片段只用于说明 shape 和命名规则，不构成完整 operation 枚举。完整 HTTP operation 集合以 `contrix-service-api.openapi.yaml` 和生成的 operation registry 为准；新增 operation 时应先更新 canonical catalog，再更新生成物。

```yaml
openapi: 3.1.0
info:
  title: Contrix Service API
  version: 1.0.0
  x-conformance-profile: cx.profile.core_event_store.v1
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
  /identity/submit-did-operation:
    post:
      operationId: cx.identity.submit_did_operation
  /identity/receipts:
    get:
      operationId: cx.identity.get_receipts

  /events/describe:
    get:
      operationId: cx.events.describe
  /events:
    post:
      operationId: cx.events.submit
    get:
      operationId: cx.events.list
  /events/{event_id}:
    get:
      operationId: cx.events.get
  /events/batch-get:
    post:
      operationId: cx.events.batch_get
  /events/frontier:
    get:
      operationId: cx.events.frontier

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
  /directory/private-contact-discovery:
    post:
      operationId: cx.directory.private_contact_discovery

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
  /keys/keypackages/upload:
    post:
      operationId: cx.keys.keypackages.upload
  /keys/keypackages/claim:
    post:
      operationId: cx.keys.keypackages.claim
  /keys/keypackages/consume:
    post:
      operationId: cx.keys.keypackages.consume
  /keys/keypackages/revoke:
    post:
      operationId: cx.keys.keypackages.revoke

  /auth/account/session-grants:
    post:
      operationId: cx.account.issue_session_grant
  /auth/account/device-pair:
    post:
      operationId: cx.account.device_pair
  /auth/account/oidc/callback:
    post:
      operationId: cx.account.oidc_callback

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
  /admin/server/status:
    get:
      operationId: cx.admin.get_server_status
  /admin/moderation/queue:
    get:
      operationId: cx.admin.get_moderation_queue
  /admin/devices/{device_id}/revoke:
    post:
      operationId: cx.admin.revoke_device
  /admin/accounts/{account_id}/status:
    post:
      operationId: cx.admin.update_account_status

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
| `cx.identity.submit_did_operation` | `POST /identity/submit-did-operation` | gRPC `SubmitDidOperation` / libp2p stream |
| `cx.identity.get_document` / `cx.identity.get_log` / `cx.identity.get_receipts` | `GET /identity/document`, `GET /identity/log`, `GET /identity/receipts` | gRPC Identity Registry / witness query |
| `cx.events.submit` | `POST /events` | gRPC `Events/Submit` / 队列 `events.submit` |
| `cx.events.get` / `cx.events.batch_get` / `cx.events.list` / `cx.events.frontier` | `GET /events/{event_id}`, `POST /events/batch-get`, `GET /events`, `GET /events/frontier` | gRPC `Events/Get` / `Events/BatchGet` / `Events/List` / `Events/Frontier` |
| `cx.sync.client_sync` | `POST /sync` | WebSocket/SSE client sync channel / `/sync?since...` |
| `cx.sync.subscribe` | `GET /sync/subscribe` | WebSocket/SSE stream / pubsub topic |
| `cx.sync.backfill` / `cx.sync.get_snapshot_head` | `GET /sync/backfill`, `GET /sync/snapshot-head` | gRPC `BackfillSync` / snapshot pointer |
| `cx.federation.transaction` / `cx.federation.push_operations` / `cx.federation.pull_operations` | `PUT /federation/transactions/{txn_id}`, `POST /federation/push-operations`, `GET /federation/pull-operations` | gRPC Federation Service / signed MQ transaction |
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

### 4.1 Generated Full Inventory

下表是从 `artifacts/registry/contract-catalog.json#operation_registry` 生成的完整 operation inventory，用于 CI 校验 Markdown / registry / OpenAPI 的差集是否为空。不要手工编辑 marker 之间的内容。

<!-- BEGIN GENERATED OPERATION INVENTORY -->
| Tier | Surface | `operation_id` | HTTP | gRPC | MQ |
| --- | --- | --- | --- | --- | --- |
| `core` | `service_discovery` | `cx.server.describe` | `GET /server/describe` | `Server/Describe` | `server.describe` |
| `core` | `identity_registry` | `cx.identity.describe_registry` | `GET /identity/describe` | `Identity/DescribeRegistry` | `identity.describe_registry` |
| `core` | `identity_registry` | `cx.identity.resolve` | `POST /identity/resolve` | `Identity/Resolve` | `identity.resolve` |
| `core` | `identity_registry` | `cx.identity.get_document` | `GET /identity/document` | `Identity/GetDocument` | `identity.get_document` |
| `core` | `identity_registry` | `cx.identity.get_log` | `GET /identity/log` | `Identity/GetLog` | `identity.get_log` |
| `core` | `identity_registry` | `cx.identity.get_receipts` | `GET /identity/receipts` | `Identity/GetReceipts` | `identity.get_receipts` |
| `core` | `identity_registry` | `cx.identity.submit_did_operation` | `POST /identity/submit-did-operation` | `Identity/SubmitDidOperation` | `identity.submit_did_operation` |
| `core` | `events_sync` | `cx.events.describe` | `GET /events/describe` | `Events/Describe` | `events.describe` |
| `core` | `events_sync` | `cx.events.submit` | `POST /events` | `Events/Submit` | `events.submit` |
| `core` | `events_sync` | `cx.events.get` | `GET /events/{event_id}` | `Events/Get` | `events.get` |
| `core` | `events_sync` | `cx.events.batch_get` | `POST /events/batch-get` | `Events/BatchGet` | `events.batch_get` |
| `core` | `events_sync` | `cx.events.list` | `GET /events` | `Events/List` | `events.list` |
| `core` | `events_sync` | `cx.events.frontier` | `GET /events/frontier` | `Events/Frontier` | `events.frontier` |
| `core` | `events_sync` | `cx.sync.client_sync` | `POST /sync` | `Sync/ClientSync` | `sync.client_sync` |
| `core` | `events_sync` | `cx.sync.describe` | `GET /sync/describe` | `Sync/Describe` | `sync.describe` |
| `core` | `events_sync` | `cx.sync.subscribe` | `GET /sync/subscribe` | `Sync/Subscribe` | `sync.subscribe` |
| `core` | `events_sync` | `cx.sync.backfill` | `GET /sync/backfill` | `Sync/Backfill` | `sync.backfill` |
| `core` | `events_sync` | `cx.sync.get_snapshot_head` | `GET /sync/snapshot-head` | `Sync/GetSnapshotHead` | `sync.get_snapshot_head` |
| `extension` | `federation` | `cx.federation.transaction` | `PUT /federation/transactions/{txn_id}` | `Federation/Transaction` | `federation.transaction` |
| `extension` | `federation` | `cx.federation.push_operations` | `POST /federation/push-operations` | `Federation/PushOperations` | `federation.push_operations` |
| `extension` | `federation` | `cx.federation.pull_operations` | `GET /federation/pull-operations` | `Federation/PullOperations` | `federation.pull_operations` |
| `extension` | `federation` | `cx.federation.space_members` | `GET /federation/space-members` | `Federation/SpaceMembers` | `federation.space_members` |
| `extension` | `federation` | `cx.federation.verify_actor` | `POST /federation/verify-actor` | `Federation/VerifyActor` | `federation.verify_actor` |
| `extension` | `directory_discovery` | `cx.directory.describe` | `GET /directory/describe` | `Directory/Describe` | `directory.describe` |
| `extension` | `directory_discovery` | `cx.directory.search_spaces` | `POST /directory/search-spaces` | `Directory/SearchSpaces` | `directory.search_spaces` |
| `extension` | `directory_discovery` | `cx.directory.resolve_space` | `POST /directory/resolve-space` | `Directory/ResolveSpace` | `directory.resolve_space` |
| `extension` | `directory_discovery` | `cx.directory.search_organizations` | `POST /directory/search-organizations` | `Directory/SearchOrganizations` | `directory.search_organizations` |
| `extension` | `directory_discovery` | `cx.directory.resolve_organization` | `POST /directory/resolve-organization` | `Directory/ResolveOrganization` | `directory.resolve_organization` |
| `extension` | `directory_discovery` | `cx.directory.search_actors` | `POST /directory/search-actors` | `Directory/SearchActors` | `directory.search_actors` |
| `extension` | `directory_discovery` | `cx.directory.search_users` | `GET /directory/search-users` | `Directory/SearchUsers` | `directory.search_users` |
| `extension` | `directory_discovery` | `cx.directory.resolve_handle` | `POST /directory/resolve-handle` | `Directory/ResolveHandle` | `directory.resolve_handle` |
| `extension` | `directory_discovery` | `cx.directory.private_contact_discovery` | `POST /directory/private-contact-discovery` | `Directory/PrivateContactDiscovery` | `directory.private_contact_discovery` |
| `extension` | `blob_media` | `cx.blob.upload` | `POST /blob/upload` | `Blob/Upload` | `blob.upload` |
| `extension` | `blob_media` | `cx.blob.head` | `HEAD /blob/get` | `Blob/Head` | `blob.head` |
| `extension` | `blob_media` | `cx.blob.get` | `GET /blob/get` | `Blob/Get` | `blob.get` |
| `extension` | `blob_media` | `cx.media.ice_config` | `POST /contrix/v1/ice-config` | `Media/IceConfig` | `media.ice_config` |
| `extension` | `authz_policy` | `cx.authz.check` | `POST /authz/check` | `Authz/Check` | `authz.check` |
| `extension` | `authz_policy` | `cx.authz.get_effective_grants` | `GET /authz/effective-grants` | `Authz/GetEffectiveGrants` | `authz.get_effective_grants` |
| `extension` | `authz_policy` | `cx.authz.get_invites` | `GET /authz/invites` | `Authz/GetInvites` | `authz.get_invites` |
| `extension` | `authz_policy` | `cx.policy.check` | `POST /contrix/v1/check` | `Policy/Check` | `policy.check` |
| `extension` | `device_and_keys` | `cx.device_messages.put` | `PUT /device_messages/{txn_id}` | `DeviceMessages/Put` | `device_messages.put` |
| `extension` | `device_and_keys` | `cx.device_messages.get` | `GET /device_messages` | `DeviceMessages/Get` | `device_messages.get` |
| `extension` | `device_and_keys` | `cx.keys.upload` | `POST /keys/upload` | `Keys/Upload` | `keys.upload` |
| `extension` | `device_and_keys` | `cx.keys.query` | `POST /keys/query` | `Keys/Query` | `keys.query` |
| `extension` | `device_and_keys` | `cx.keys.claim` | `POST /keys/claim` | `Keys/Claim` | `keys.claim` |
| `extension` | `device_and_keys` | `cx.keys.keypackages.upload` | `POST /keys/keypackages/upload` | `Keys/KeyPackagesUpload` | `keys.keypackages.upload` |
| `extension` | `device_and_keys` | `cx.keys.keypackages.claim` | `POST /keys/keypackages/claim` | `Keys/KeyPackagesClaim` | `keys.keypackages.claim` |
| `extension` | `device_and_keys` | `cx.keys.keypackages.consume` | `POST /keys/keypackages/consume` | `Keys/KeyPackagesConsume` | `keys.keypackages.consume` |
| `extension` | `device_and_keys` | `cx.keys.keypackages.revoke` | `POST /keys/keypackages/revoke` | `Keys/KeyPackagesRevoke` | `keys.keypackages.revoke` |
| `extension` | `push` | `cx.push.register_device` | `POST /push/register-device` | `Push/RegisterDevice` | `push.register_device` |
| `extension` | `push` | `cx.push.unregister_device` | `POST /push/unregister-device` | `Push/UnregisterDevice` | `push.unregister_device` |
| `extension` | `push` | `cx.push.notify` | `POST /push/notify` | `Push/Notify` | `push.notify` |
| `extension` | `applet` | `cx.applet.ping` | `GET /applet/ping` | `Applet/Ping` | `applet.ping` |
| `extension` | `applet` | `cx.applet.describe` | `GET /applet/describe` | `Applet/Describe` | `applet.describe` |
| `extension` | `applet` | `cx.applet.transaction` | `PUT /applet/transactions/{txn_id}` | `Applet/Transaction` | `applet.transaction` |
| `extension` | `applet` | `cx.applet.query_actor` | `GET /applet/actors/{actor_id}` | `Applet/QueryActor` | `applet.query_actor` |
| `extension` | `applet` | `cx.applet.query_space` | `GET /applet/spaces/{space_id_or_alias}` | `Applet/QuerySpace` | `applet.query_space` |
| `extension` | `applet` | `cx.applet.protocol_metadata` | `GET /applet/protocols/{protocol}` | `Applet/ProtocolMetadata` | `applet.protocol_metadata` |
| `extension` | `applet` | `cx.applet.third_party_users` | `GET /applet/third_party/users` | `Applet/ThirdPartyUsers` | `applet.third_party_users` |
| `extension` | `applet` | `cx.applet.third_party_locations` | `GET /applet/third_party/locations` | `Applet/ThirdPartyLocations` | `applet.third_party_locations` |
| `extension` | `mimi_interop` | `cx.mimi.provider_directory` | `GET /mimi/provider-directory` | `Mimi/ProviderDirectory` | `mimi.provider_directory` |
| `extension` | `mimi_interop` | `cx.mimi.group_info` | `GET /mimi/rooms/{flow_id}/group-info` | `Mimi/GroupInfo` | `mimi.group_info` |
| `extension` | `mimi_interop` | `cx.mimi.key_material` | `POST /mimi/key-material` | `Mimi/KeyMaterial` | `mimi.key_material` |
| `extension` | `mimi_interop` | `cx.mimi.submit_message` | `POST /mimi/rooms/{flow_id}/messages` | `Mimi/SubmitMessage` | `mimi.submit_message` |
| `extension` | `mimi_interop` | `cx.mimi.room_update` | `PUT /mimi/rooms/{flow_id}/update` | `Mimi/RoomUpdate` | `mimi.room_update` |
| `extension` | `mimi_interop` | `cx.mimi.request_consent` | `POST /mimi/consent/request` | `Mimi/RequestConsent` | `mimi.request_consent` |
| `extension` | `mimi_interop` | `cx.mimi.update_consent` | `POST /mimi/consent/update` | `Mimi/UpdateConsent` | `mimi.update_consent` |
| `extension` | `mimi_interop` | `cx.mimi.identifier_query` | `POST /mimi/identifiers/query` | `Mimi/IdentifierQuery` | `mimi.identifier_query` |
| `extension` | `mimi_interop` | `cx.mimi.notify` | `POST /mimi/rooms/{flow_id}/notify` | `Mimi/Notify` | `mimi.notify` |
| `extension` | `mimi_interop` | `cx.mimi.report_abuse` | `POST /mimi/report-abuse` | `Mimi/ReportAbuse` | `mimi.report_abuse` |
| `extension` | `mimi_interop` | `cx.mimi.proxy_download` | `POST /mimi/proxy-download` | `Mimi/ProxyDownload` | `mimi.proxy_download` |
| `deployment_local` | `account_auth` | `cx.account.device_pair` | `POST /auth/account/device-pair` | `Account/DevicePair` | `account.device_pair` |
| `deployment_local` | `account_auth` | `cx.account.issue_session_grant` | `POST /auth/account/session-grants` | `Account/IssueSessionGrant` | `account.issue_session_grant` |
| `deployment_local` | `account_auth` | `cx.account.oidc_callback` | `POST /auth/account/oidc/callback` | `Account/OidcCallback` | `account.oidc_callback` |
| `deployment_local` | `admin_operator` | `cx.admin.get_moderation_queue` | `GET /admin/moderation/queue` | `Admin/GetModerationQueue` | `admin.get_moderation_queue` |
| `deployment_local` | `admin_operator` | `cx.admin.get_server_status` | `GET /admin/server/status` | `Admin/GetServerStatus` | `admin.get_server_status` |
| `deployment_local` | `admin_operator` | `cx.admin.revoke_device` | `POST /admin/devices/{device_id}/revoke` | `Admin/RevokeDevice` | `admin.revoke_device` |
| `deployment_local` | `admin_operator` | `cx.admin.update_account_status` | `POST /admin/accounts/{account_id}/status` | `Admin/UpdateAccountStatus` | `admin.update_account_status` |
| `deployment_local` | `admin_operator` | `cx.moderation.report` | `POST /moderation/report` | `Moderation/Report` | `moderation.report` |
<!-- END GENERATED OPERATION INVENTORY -->

## 5. 落地要求

- 任何新增、重命名或删除 `operation_id` 的提案，必须先更新 `artifacts/registry/contract-catalog.json` 中的 `operation_registry`，再生成 registry / OpenAPI / 文档视图。
- 任何节点都应能发布一份可下载的 OpenAPI 文档（建议路径 `/.well-known/contrix/openapi.yaml`），并在 service DID metadata 中声明版本和 hash。
- 实现必须保持 `operation_id` 在演进中稳定；若请求字段名变更，必须通过 profile、schema 版本或 feature discovery 明确协商。
- OpenAPI 只定义形态，不定义核心语义。核心语义仍由本协议对象模型、授权状态、签名、同步与加密规范给出。
- 实现不得因为支持 core Event/Sync 就默认声称支持目录、MIMI、账户、管理员或 E2EE key-management surface；这些能力必须通过 `supported_operations`、`supported_profiles` 或两者同时显式声明。
- `/contrix/v1/*` 是服务本地绝对路径，不挂在 `/api/v1` 下。生成 OpenAPI 时必须为这些 path 使用 path-level `servers` 或拆成独立文档。
- `POST /sync` 是客户端聚合增量同步；`GET /sync/subscribe` 是 Space Event 流订阅；`GET /sync/backfill` 是历史回补。三者不得互相替代，也不得新增未声明的 canonical sync endpoint。
- 生成的 OpenAPI MUST 引用统一 error envelope，覆盖 `404 unrecognized_endpoint`、`405 method_not_allowed`、`429 rate_limited` 与 `503 temporarily_unavailable` 的标准响应。
- OpenAPI security scheme MUST NOT 定义 query string token 认证；受保护 endpoint 只能使用 header / signature / mTLS / signed proof body 等认证方式。
- Blob / media endpoint 的 schema MUST 显式声明 `Content-Type`、`Content-Disposition`、`Range`、`Content-Range`、`Location` 和缓存头行为，避免通过 header 泄露不可见资源。

