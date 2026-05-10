---
title: Service HTTP/JSON Binding
---

## 1. 目标

本文定义 Contrix 默认 HTTP/JSON binding 的路径、请求形状和错误响应。

协议核心不强绑定 REST。其他 transport binding MAY 使用 gRPC、WebSocket、SSE、message queue、libp2p 或 IPC，但必须映射到 `service-surface.md` 中定义的等价语义。

## 2. 通用要求

- 请求和响应默认使用 `Content-Type: application/json`。
- 写请求 MUST 支持幂等键或内容 ID 幂等。
- 认证 MAY 使用 bearer token、HTTP Message Signature、DID proof 或 transport-specific binding。
- 服务 MUST 通过 describe / feature discovery 暴露实际支持路径、profile 和限制。
- 错误响应 MUST 使用统一 error schema。
- 认证材料 MUST 放在 header、HTTP Message Signature、mTLS 或 signed proof body 中；受保护 endpoint MUST NOT 接受 query string 认证。
- 未知路径、错误 method、限流、临时不可用和不可见资源 MUST 使用 `api-conventions.md` 中定义的标准错误语义。

### 2.1 REST API 命名空间组织

Contrix 的 HTTP/JSON binding 按 **服务角色与 canonical operation** 组织，而不是按某个产品形态拆成固定的 Client API / Server API / Push API 包。客户端、Principal Server、Events API、Directory、Applet、Push Gateway 等都可以暴露自己的服务面；服务发现决定某个节点实际支持哪些命名空间。

默认 REST 命名空间如下：

| 命名空间 | 主要调用方 | 语义 | 规范文件 |
| --- | --- | --- | --- |
| `/server/*` | 客户端与服务 | 服务描述、feature discovery、auth metadata。 | `service-surface.md`、`api-conventions.md` |
| `/identity/*` | 客户端、服务、registry | DID 文档、key log、DID operation、receipt。 | `service-surface.md`、`identity-did.md` |
| `/events/*` | 客户端、Principal Server、授权 Event 副本 | signed Event 提交、按 ID 读取、批量读取、actor/Space 双向历史查询(query)、流式订阅(subscribe，含历史 catchup)、frontier 查询。 | `operations-sync.md`、`service-surface.md` |
| `/sync/*` | 客户端、Principal Server | account 聚合同步(`POST /sync`)、describe、snapshot head。事件流读取已收敛到 `/events/*`。 | `client-sync.md`、`service-surface.md` |
| `/directory/*` | 客户端、服务 | Space / Organization / Actor / handle 的授权发现与解析。 | `discovery-directory.md` |
| `/blob/*` | 客户端、服务 | Blob 上传、HEAD、authenticated download。 | `media-and-blob.md` |
| `/push/*` | 客户端、Sync、Push Gateway | 推送设备注册、注销、脱敏唤醒投递。 | `push-notifications.md` |
| `/device_messages/*`、`/keys/*` | E2EE 客户端、Principal Server | to-device、one-time key、fallback key、device list 相关操作。 | `device-lifecycle.md` |
| `/authz/*`、`/contrix/v1/check` | 客户端、Events API、Sync、Policy Server | capability 预检查、policy server 签名决策。 | `capabilities.md`、`policy-server.md` |
| `/contrix/v1/ice-config` | 通话客户端、Media Service | TURN/STUN/ICE 短期凭证。 | `webrtc-signaling.md` |
| `/moderation/*` | 客户端、审核服务 | 举报、审核队列或扩展审核入口。 | `governance/content-moderation.md` |
| `/applet/*` | Contrix 服务调用 Applet | applet ping / describe、transaction push、ghost actor / portal 查询。 | `applet-integration.md` |

客户端视角的常用 API 集合通常包括 `/server`、`/identity`、`/events`、`/sync`、`/directory`、`/blob`、`/push`、`/device_messages`、`/keys`、`/authz`。服务间 API 集合通常包括 `/federation`、`/events`、`/sync`、`/authz`、`/contrix/v1/check`、`/applet` 和 `/push/notify`。搜索、inbox、notification 和 View projection 默认是客户端本地派生；若实现提供网络搜索接口，应在扩展 profile 中单独声明。

新增顶层 REST 命名空间前，规范必须同步更新 `service-api-schema.mdx`、feature discovery 返回值和对应 conformance profile。实现不得用未声明路径绕过 canonical operation、capability、幂等、分页或错误语义。

### 2.2 端点契约规则

每个 REST endpoint 的规范定义必须至少包含：

- `operation_id` / canonical operation。
- Path 参数、query 参数和 request body 字段类型。
- 成功响应字段类型。
- 认证方式：`public_metadata`、`user_session`、`device_proof`、`service_signature`、`policy_token`、`applet_signature` 等。
- 访问限制：Space membership、history visibility、capability、service delegation、namespace、plaintext visibility、rate limit、quota。
- 幂等键：写接口使用 `Idempotency-Key` header、`event_id`、`request_id` 或 canonical request hash。
- 失败时使用标准 error envelope。

JSON 示例只用于说明，不构成完整 schema。正式接口定义 MUST 使用字段表说明字段名、位置、类型、是否必填、含义和约束。

默认规则：

- 除明确标记为 `public_metadata` 的 describe / discovery 外，所有 endpoint MUST 认证。
- 认证只证明调用方身份；服务仍 MUST 执行 capability、Space policy、history visibility、service delegation 和 revocation 检查。
- 服务间调用 MUST 使用 HTTP Message Signature 或等价 service DID proof，并绑定 method、target URI、content digest、origin service DID 和 destination service DID。
- 服务间调用的 `origin` / `destination` 必须是 service DID，且必须与 DID Document service endpoint、目标 URL、Space policy / service delegation 和签名 transcript 一致。
- 受保护 endpoint 不得接受 query string 中的 token、API key 或签名材料；临时下载 URL 只能使用短时效、单用途、可撤销的派生 token。
- 返回 `not_found` 的 endpoint MUST 对“不存在”和“存在但不可见”保持一致失败语义，除非调用方已有管理权限。
- 所有批量读取 MUST 支持 `limit` 上限，分页 cursor 必须是不透明 token。
- 路由层 MUST 对 `/api/v1/*` 与 `/contrix/v1/*` 下的未知路径返回 `404 unrecognized_endpoint`，对已知路径的错误 method 返回 `405 method_not_allowed`，且不得进入业务逻辑。

### 2.3 端点契约清单

类型简写：`did` 为 DID URI，`id` 为协议对象 ID，`cursor` / `token` 为 opaque string，`signature` 为 `{kid, alg?, sig}`，`proof` 为 DID / HTTP message / detached JWS proof。`events` 为 Event Envelope 数组。

| Endpoint | Request 类型 | Auth / 访问限制 | Success 类型 |
| --- | --- | --- | --- |
| `GET /api/v1/server/describe` | query: none 或 `service_type?` | `public_metadata`；不得返回私有 topology、secret 或未授权 internal endpoint。 | `{service_did, service_type, protocol_version, supported_features[], supported_bindings[], supported_operations[], auth_metadata?, limits?, rate_limit_policy?, rate_limit_policy_ref?}` |
| `GET /api/v1/identity/describe` | query: none | `public_metadata`；可限流。 | `{service_did, registry_mode, supported_receipts[], protocol_version, profiles[]}` |
| `POST /api/v1/identity/resolve` | body `{did: did, include?: string[]}` | `public_metadata`；private DID MAY require `user_session` 或 presentation proof。 | `{did_document, key_log_head?, seq?, receipts?, method_evidence?}` |
| `GET /api/v1/identity/document` | query `{did: did, version?: string}` | 同 `identity.resolve`。 | `{did_document, head_event_hash?, seq?, receipts?}` |
| `GET /api/v1/identity/log` | query `{did: did, cursor?: cursor, limit?: int}` | public DID 可公开；private / pairwise DID MUST require holder-approved proof。 | `{events[], next_cursor?, has_more}` |
| `POST /api/v1/identity/submit-did-operation` | body `{did: did, seq: int, prev_event_hash?: string, patch: object, proofs: proof[]}` | `device_proof` 或 recovery proof；MUST 满足 DID method / key-log 授权。 | `{status, head_event_hash, seq, receipts?}` |
| `GET /api/v1/identity/receipts` | query `{did: did, head: string}` | 同 DID 可见性；witness 可公开最小 receipt。 | `{receipts[], threshold_met?: boolean}` |
| `GET /api/v1/events/describe` | query none 或 `{actor_id?: did, space_id?: id}` | `public_metadata` 或 `user_session`；私有 frontier 需认证。 | `{service_did, supported_event_schemas[], supported_reducer_profiles[], supported_signatures[], limits}` |
| `POST /api/v1/events` | body `EventEnvelope` 或 `{events: EventEnvelope[]}` | `user_session` / `device_proof` / `service_signature`；MUST 验证 actor DID、签名、capability、Space policy、`actor_seq`、`prev_refs`、`auth_refs`。 | `{status, accepted[], duplicate[]?, rejected[]?, actor_frontier?, space_frontier?, cursor?}` |
| `GET /api/v1/events/{event_id}` | path `{event_id: id}` query `{include_payload?: boolean}` | Event 可见性按 Space policy / history visibility / E2EE envelope 判断；不可见时返回 `not_found`。 | `{event, visibility?, receipts?}` |
| `POST /api/v1/events/batch-get` | body `{event_ids?: id[], event_hashes?: string[], include_payload?: boolean}` | 同 Event read；payload 可见性按 Space policy / E2EE envelope 判断。 | `{events[], missing[], unauthorized[]?}` |
| `GET /api/v1/events` | query `{spaces?: id[], actors?: did[], from?: cursor, until?: cursor, direction?: forward\|backward, limit?: int, filters?: object}` | 调用方必须对每个 selector 元素满足读取约束：actor scope 走 actor history visibility；space scope 走 membership frontier + history visibility + E2EE epoch policy。`spaces[]` ∪ 内部、`actors[]` ∪ 内部、二者组合为交集。 | `{events[], next_cursor?, prev_cursor?, has_more}` |
| `GET /api/v1/events/subscribe` | query `{spaces?: id[], actors?: did[], from?: cursor, include_history?: boolean}` | 同 `GET /events` 的逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性边界。授权丢失通过 per-space `unauthorized` 帧通知，不中断整条流。 | event stream frames `{kind: event\|frontier\|heartbeat\|catchup_complete\|epoch_rotation\|dropped\|resync_required\|unauthorized, space_id?: id, cursor?: cursor, payload?: object}` |
| `GET /api/v1/events/frontier` | query `{actor_id?: did, space_id?: id}` | 返回调用方可见范围内 frontier；不得泄露不可见 Space 或 private DID。 | `{frontier, receipts?}` |
| `POST /api/v1/sync` | body `{since?: cursor, filter?: object, set_presence?: string, timeout_ms?: int}` | `user_session` bound to principal/device。聚合账号视角 delta（跨 Space frontier、to_device、account_data、device_lists、presence、unread / notification counts），不是裸事件读。 | Account sync response `{cursor, spaces?, to_device?, account_data?, device_lists?}` |
| `GET /api/v1/sync/describe` | query none | `public_metadata` 或 `user_session`；私有 limits 可认证后返回。 | `{service_did, supported_sync_profiles[], limits, frontier?}` |
| `GET /api/v1/sync/snapshot-head` | query `{space_id: id}` | Space read；snapshot manifest 必须签名，并包含 `event_set_commitment`。 | `{snapshot_ref, state_hash, frontier, event_set_commitment, verification_hints?, signature}` |
| `GET /api/v1/directory/describe` | query none | `public_metadata`；可限流。 | `{service_did, resource_types[], discovery_profiles[], restricted_query_proof?: boolean}` |
| `POST /api/v1/directory/search-spaces` | body `{query?: string, organization_did?: did, parent_space_id?: id, requester?: did, proofs?: proof[], cursor?: cursor, limit?: int}` | discoverability + requester proof + policy filtering；隐藏资源不泄露存在性。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-space` | body `{space_id?: id, alias?: string, invite_token?: string, signed_link?: string, requester?: did, proofs?: proof[]}` | invite / restricted / secret Space 按统一 `not_found` 失败。 | `{space_preview, stripped_state?, join_rule?, via_services?}` |
| `POST /api/v1/directory/search-organizations` | body `{query?: string, claims?: object, cursor?: cursor, limit?: int}` | 仅返回公开或授权可发现组织。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-organization` | body `{organization_did?: did, handle?: string, proofs?: proof[]}` | 公开组织 DID 可解析不表示成员或拓扑公开。 | `{organization_preview, did_document_ref?, endorsements?}` |
| `POST /api/v1/directory/search-actors` | body `{query?: string, space_id?: id, organization_did?: did, cursor?: cursor, limit?: int}` | 不得泄露 pairwise/private DID 或未披露组织账号。 | `{results[], next_cursor?}` |
| `GET /api/v1/directory/search-users` | query `{q: string, space_id?: id, limit?: int}` | `user_session`; 用于 mention autocomplete，必须受共同 Space / directory policy 限制。 | `{results[]}` |
| `POST /api/v1/directory/resolve-handle` | body `{handle: string, expected_did?: did, proof_challenge?: string}` | 按 handle 双向验证规则；private handle 需 presentation。 | `{did, handle, verified: boolean, claims?}` |
| `POST /api/v1/blob/upload` | body binary/multipart + metadata `{space_id?, sha256?, size, media_type?, filename?, purpose?}`；`Content-Type` optional | `user_session`; upload capability、quota、media policy；私有 blob 绑定 Space / actor。 | `{blob_ref, size, media_type?, sha256, upload_receipt?}` |
| `HEAD/GET /api/v1/blob/get` | query `{blob_ref: string}` headers `Authorization?`, `Range?`, `X-Contrix-Wait-For?` | 公开 blob 可匿名；私有 blob 必须验证 actor/device/Space/purpose/expiry；不得 query string 认证。 | bytes 或 headers `{Content-Length?, Digest?, Cache-Control, Content-Type?, Content-Disposition?, Content-Range?}` |
| `POST /api/v1/push/register-device` | body `{device_id: id, push_gateway: url, push_key: string, platform?: string, app_id?: string, display_name?: string}` | `user_session` for same principal/device；push_key 必须被加密或最小披露存储。 | `{ok: true, registration_id?, expires_at?}` |
| `POST /api/v1/push/unregister-device` | body `{device_id: id, push_key?: string, app_id?: string}` | `user_session` for same device/principal 或 device revocation path。 | `{ok: true}` |
| `POST /api/v1/push/notify` | body `{notification: {event_id?, space_id?, type, sender?, push_hint?, counts?, devices[]}}` | 来自被授权 Sync 或通知服务的 `service_signature`；E2EE 时 MUST 做 blind / 最小化处理。 | `{rejected[]}` |
| `POST /api/v1/device_messages` | header `Idempotency-Key` body `DeviceMessagesPutRequest {messages: {principal_id: {device_id: DeviceMessageTarget {kind, content, expires_at}}}}` | sender `user_session` / device key；目标必须是授权 device；服务端入队前 MUST materialize `DeviceMessageEnvelope` 并绑定 `recipient_principal_id` / `recipient_device_id` / `expires_at`；按 `(sender, Idempotency-Key)` 幂等。验证消息使用 `cx.key.verification.*` kind，且不得作为持久 Event history；缺失、已过期或超过 TTL 上限的消息 MUST reject。 | `{ok: true, delivered?, unknown_devices?}` |
| `GET /api/v1/device_messages` | query `{from?: cursor, limit?: int}` | `user_session` bound to current device；只返回该 device 队列。 | `{events: DeviceMessageEnvelope[], next_cursor?, limited?}` |
| `POST /api/v1/keys/upload` | body `{device_id: id, one_time_keys?: object, fallback_keys?: object, device_signature: signature}` | current device proof；key 必须链接 self-signing / principal key。 | `{one_time_key_counts, fallback_keys?}` |
| `POST /api/v1/keys/query` | body `{device_keys: {principal_id: string[]}, timeout_ms?: int}` | `user_session`; 查询范围可按关系 / Space 限制。 | `{device_keys, failures?}` |
| `POST /api/v1/keys/claim` | body `{one_time_keys: {principal_id: {device_id: algorithm}}}` | `user_session`; one-time key MUST 原子消费。 | `{one_time_keys, failures?}` |
| `PUT /api/v1/keys/backups/{backup_id}` | path `{backup_id}` body `cx.schema.key_backup.v1` | current device proof / DID proof / recovery proof；path 与 body backup id 必须一致。 | `{status, backup_id, ciphertext_digest}` |
| `GET /api/v1/keys/backups` | query `{backup_class?: string, cursor?: cursor, limit?: int}` | `user_session` bound to current principal/device 或 recovery proof。 | `{backups[], next_cursor?}` |
| `GET /api/v1/keys/backups/{backup_id}` | path `{backup_id}` | 同 principal 当前授权 device、recovery policy 或授权组织恢复服务。 | `cx.schema.key_backup.v1` |
| `DELETE /api/v1/keys/backups/{backup_id}` | path `{backup_id}` | 高风险 device proof、DID proof 或 recovery policy proof。 | `{deleted: true}` |
| `GET /api/v1/authz/effective-grants` | query `{space_id: id, subject: did, at?: string}` | subject 本人、Space admin、authorized service；不得枚举无关 subject。 | `{grants[], state_hash?, evaluated_at}` |
| `GET /api/v1/authz/invites` | query `{space_id?: id, subject: did 或 string, cursor?: cursor}` | subject 本人或 inviter/admin；secret invites 不可枚举。 | `{invites[], next_cursor?}` |
| `POST /api/v1/authz/check` | body `{actor: did, action: string, resource: object, context?: object}` | caller 必须是相关 actor、Events/Sync 预检查服务或 policy-authorized service。 | `{decision, matched_grants?, applied_constraints?, policy_results?, missing_proofs?, frontier?, cache_valid_until?, reason_code?, obligations?}` |
| `POST /contrix/v1/check` | body `{request_id, space_id?, request_canonical_hash, action, actor, source, event_preview?, auth_context?}` | `policy_token` / `service_signature`; 只接收最小披露字段。 | signed policy decision `{decision, reason_code, expires_at, obligations?, signature}` |
| `POST /api/v1/moderation/report` | body `{space_id: id, target_ref: id, reason: enum, description?: string, reporter: did, evidence_refs?: id[]}` | `user_session`; reporter 必须可见 target；report 仅对 moderators 可见。 | `{report_id, status, routed_to?}` |
| `GET /api/v1/applet/ping` | query none | `public_metadata` 或 `service_signature`；不得泄露 private namespace。 | `{ok, applet_id, service_did, protocol_version}` |
| `GET /api/v1/applet/describe` | query none | `service_signature` SHOULD；public mode 只返回公开 capabilities。 | `{applet_id, service_did, protocols[], namespaces, limits, auth}` |
| `POST /api/v1/applet/transactions` | header `Idempotency-Key` body `{source_service_did, events[], ephemeral?}` | `service_signature`; Applet 必须验证每个 event signature、namespace 和 capability；按 `(source_service_did, Idempotency-Key)` 幂等。 | `{ok: true, rejected?, retry_after_ms?}` |
| `GET /api/v1/applet/actors/{actor_id}` | path `{actor_id}` | `service_signature`; actor_id 必须命中 Applet actor namespace。 | `{exists, actor_id, display_name?, external_ref?}` 或 `not_found` |
| `GET /api/v1/applet/spaces/{space_id_or_alias}` | path `{space_id_or_alias}` | `service_signature`; 必须命中 portal namespace 或授权查询。 | `{exists, space_id?, title?, external_ref?}` |
| `GET /api/v1/applet/protocols/{protocol}` | path `{protocol}` | 可 public_metadata；实例列表可要求授权。 | `{protocol, display_name, icon_blob?, field_types, instances?}` |
| `GET /api/v1/applet/third_party/users` | query `{protocol, ...external_ids}` | `service_signature`; 查询字段必须在 registration namespace 内。 | `{actor_id?, exists, external_ref?}` |
| `GET /api/v1/applet/third_party/locations` | query `{protocol, ...external_ids}` | `service_signature`; 查询字段必须在 portal namespace 内。 | `{space_id?, exists, external_ref?}` |
| `POST /contrix/v1/ice-config` | body `{space_id: id, call_id: id, actor_id: did, device_id: id, mode: string}` | `user_session`; actor 必须有 call/media capability，Media Service 必须被 Space policy 委托。 | `{ttl_seconds, ice_servers[], policy, signature}` |

跨域 actor 验证响应（通过 `/api/v1/identity/resolve` 与 holder-approved presentation challenge 获得）只能作为缓存加速或辅助诊断。接收方在接受事件、成员变更或设备绑定前，仍 MUST 独立验证 DID Document、key log、签名 transcript、capability 和 Space policy；不得把对端"验证通过"当成最终授权依据。

### 2.4 字段级 Schema 索引

本节是 REST 端点的字段级 schema 索引。字段写法为 `name: type - 说明`。出现在“必填字段”列的字段为 required；出现在“可选字段”列的字段为 optional。位置若非 body，会显式标注为 `path.`、`query.` 或 `header.`。

规范性 operation contract 以 `artifacts/registry/contract-catalog.json#operation_registry` 为 canonical source；`artifacts/registry/operation-registry.json` 是其生成视图。本表、OpenAPI 与非 HTTP binding 均 MUST 从 canonical source 生成或通过 CI 校验；不得新增 catalog 中不存在的 `operation_id`，也不得在声明支持某 operation 时遗漏对应 catalog 条目。

| `operation_id` | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.server.describe` | 无 | `query.service_type: string - 过滤服务类型` | `service_did: did - 服务 DID`; `service_type: string - 运行时服务类型`; `protocol_version: string`; `supported_features: string[]`; `supported_bindings: object[]`; `supported_operations: operation_id[]`; `auth_metadata: object?`; `limits: object?`; `rate_limit_policy: object?`; `rate_limit_policy_ref: string?` | `public_metadata`; 不得返回私有拓扑或 secret。 |
| `cx.identity.describe_registry` | 无 | 无 | `service_did: did`; `registry_mode: enum(writer,witness,replica)`; `supported_receipts: string[]`; `protocol_version: string`; `profiles: string[]` | `public_metadata`; 可限流。 |
| `cx.identity.resolve` | `did: did - 待解析 DID` | `include: string[] - 请求附加证据，如 key_log/receipts` | `did_document: object`; `key_log_head: id?`; `seq: int?`; `receipts: object[]?`; `method_evidence: object?` | private / pairwise DID 可要求 presentation proof。 |
| `cx.identity.get_document` | `query.did: did` | `query.version: string - 指定版本或 head` | `did_document: object`; `head_event_hash: string?`; `seq: int?`; `receipts: object[]?` | 可见性同 `cx.identity.resolve`。 |
| `cx.identity.get_log` | `query.did: did` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `has_more: boolean` | private / pairwise DID MUST 要求 holder-approved proof。 |
| `cx.identity.submit_did_operation` | `did: did`; `seq: int`; `patch: object`; `proofs: proof[]` | `prev_event_hash: string` | `status: enum(accepted,duplicate)`; `head_event_hash: string`; `seq: int`; `receipts: object[]?` | MUST 满足 DID method / key-log 授权；`did+seq` 幂等。 |
| `cx.identity.get_receipts` | `query.did: did`; `query.head: string` | 无 | `receipts: object[]`; `threshold_met: boolean?` | 只公开最小 witness receipt。 |
| `cx.events.describe` | 无 | `query.actor_id: did`; `query.space_id: id` | `service_did: did`; `supported_event_schemas: string[]`; `supported_reducer_profiles: string[]`; `supported_signatures: string[]`; `limits: object?` | public metadata 可公开；私有 frontier 需认证。 |
| `cx.events.submit` | `event: object` 或 `events: object[]` | `expected_frontier: object`; `idempotency_key: string` | `status: enum(accepted,duplicate,partial)`; `accepted: id[]`; `duplicate: id[]?`; `rejected: object[]?`; `actor_frontier: object?`; `space_frontier: object?`; `cursor: cursor?` | MUST 验证 Event signature、DID、capability、Space policy、`actor_seq`、`prev_refs` 和 `auth_refs`。`cursor` 是 barrier purpose（read-your-writes）。 |
| `cx.events.get` | `path.event_id: id` | `query.include_payload: boolean` | `event: object`; `visibility: object?`; `receipts: object[]?` | 不可见时返回 `not_found`。 |
| `cx.events.batch_get` | 至少一个：`event_ids: id[]` 或 `event_hashes: string[]` | `include_payload: boolean` | `events: object[]`; `missing: id[]`; `unauthorized: id[]?` | payload 可见性按 Space policy / E2EE envelope 判断。 |
| `cx.events.query` | 至少一个：`query.spaces: id[]` 或 `query.actors: did[]` | `query.from: cursor`; `query.until: cursor`; `query.direction: enum(forward,backward)=forward`; `query.limit: int`; `query.filters: object` | `events: object[]`; `next_cursor: cursor?`; `prev_cursor: cursor?`; `has_more: boolean` | `spaces[]` 内部 union、`actors[]` 内部 union、二者组合为 intersection。每个 selector 元素都按对应可见性约束逐项检查：actor scope 走 actor history visibility；space scope 走 membership frontier + history visibility + E2EE epoch policy。`from`/`until` 可定义闭区间；`direction=backward` 时返回向更早 cursor 走的页。 |
| `cx.events.subscribe` | 至少一个：`query.spaces: id[]` 或 `query.actors: did[]` | `query.from: cursor`; `query.include_history: boolean=true` | stream frame: `kind: enum(event,frontier,heartbeat,catchup_complete,epoch_rotation,dropped,resync_required,unauthorized)`; `space_id: id?`; `cursor: cursor?`; `payload: object?` | 同 `cx.events.query` 逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性。`include_history=true` 时先吐历史再以 `catchup_complete` 帧切到实时；某 space 中途授权丢失发出 `unauthorized` 帧并继续其他 space；服务端因容量丢弃发出 `dropped` 帧，客户端必须 reconcile。 |
| `cx.events.frontier` | 至少一个：`query.actor_id: did` 或 `query.space_id: id` | 无 | `frontier: object`; `receipts: object[]?` | 不得泄露不可见 Space 或 private DID。 |
| `cx.sync.account` | 无 | `since: cursor`; `filter: object`; `set_presence: enum(online,offline,unavailable)`; `timeout_ms: int` | `cursor: cursor`; `spaces: object?`; `to_device: object?`; `account_data: object?`; `device_lists: object?` | `user_session` 必须绑定 principal/device。聚合账号视角 delta（跨 Space frontier、to_device、account_data、device_lists、presence），不是裸事件读；裸事件读用 `cx.events.query` / `cx.events.subscribe`。`cursor` 是 stream purpose。 |
| `cx.sync.describe` | 无 | 无 | `service_did: did`; `supported_sync_profiles: string[]`; `limits: object`; `frontier: object?` | 私有 frontier 可认证后返回。 |
| `cx.sync.get_snapshot_head` | `query.space_id: id` | 无 | `snapshot_ref: id`; `state_hash: string`; `frontier: object`; `event_set_commitment: object`; `verification_hints: object?`; `signature: signature` | snapshot manifest MUST 签名；high-assurance profile MUST 支持 inclusion / omission challenge hints。 |
| `cx.directory.describe` | 无 | 无 | `service_did: did`; `resource_types: string[]`; `discovery_profiles: string[]`; `restricted_query_proof: boolean?`; `ingest_modes: array<push \| pull>`; `accept_policy_kind: enum`; `accept_policy_ref: object?`; `default_ttl_seconds: int`; `max_ttl_seconds: int`; `revalidation_grace_seconds: int`; `accepted_resource_kinds: enum[]`; `accepted_did_methods: string[]`; `takedown_contact: did\|url?`; `rate_limits: object?` | `public_metadata`; 可限流。详见 `discovery/discovery-directory.md` §8.9。 |
| `cx.directory.search_spaces` | 无 | `query: string`; `organization_did: did`; `parent_space_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | hidden resource 不泄露存在性；每条 result MUST 含 `as_of`/`source_refs`/`policy_revision`/`stale?`/`divergent?`/`via_services?`（discovery-directory.md §9.1）。 |
| `cx.directory.resolve_space` | 至少一个：`space_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proofs: proof[]` | `space_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `via_services: did[]` | secret/restricted Space 使用统一 `not_found`；`via_services` v1 normative，必须给出 host Principal Server service DID。 |
| `cx.directory.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 仅公开或授权可发现组织。 |
| `cx.directory.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | 解析组织不等于公开成员或拓扑。 |
| `cx.directory.search_actors` | 无 | `query: string`; `space_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 不得泄露 pairwise/private DID。 |
| `cx.directory.search_users` | `query.q: string` | `query.space_id: id`; `query.limit: int` | `results: object[]` | mention autocomplete；受共同 Space / directory policy 限制。 |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string` | `did: did`; `handle: string`; `verified: boolean`; `claims: object[]?` | private handle 需要 presentation。 |
| `cx.directory.private_contact_discovery` | `requester: did`; `contacts: object[]` | `proofs: proof[]`; `privacy_profile: string`; `padding: object` | `matches: object[]`; `proofs: object[]?`; `retry_after_ms: int?` | MUST 使用 blinded / padded identifier batch；不得返回原始 connection identifier、完整 profile、成员列表或关系图谱。 |
| `cx.directory.announce` | `resource_kind: enum(space,organization,actor,applet,handle)`; `resource_id: id\|did\|handle`; `discovery_state: object`; `source_refs: id[]`; `as_of: timestamp`; `principal_server_did: did` | `ttl_seconds: int`; `supersedes_announce_id: id` | `announce_id: id`; `indexed_at: timestamp`; `effective_ttl_seconds: int`; `next_revalidation_after: timestamp`; `warnings: string[]?` | 资源 → Directory 的签名 ingest；MUST 验签 + 双向 opt-in；详见 `discovery/discovery-directory.md` §8.3 / §8.5 / §8.10。 |
| `cx.directory.withdraw` | `resource_id: id\|did\|handle`; `governance_proof: object`; `reason: string` | `effective_at: timestamp` | `withdraw_id: id`; `acked_at: timestamp` | 资源主动撤销 opt-in；Directory MUST 在 ≤ 1h 内停止披露；详见 `discovery/discovery-directory.md` §8.7。 |
| `cx.directory.subscribe` | `subscriber_did: did`; `resource_filter: object`; `webhook_endpoint: url` | `secret: string`; `expires_at: timestamp` | `subscription_id: id`; `effective_at: timestamp` | pull 模式优化；不替代 freshness 协议（§8.6）。 |
| `cx.blob.upload` | `size: int` | `space_id: id`; `sha256: string`; `media_type: string`; `filename: string`; `purpose: string`; binary/multipart body; `header.Content-Type: string` | `blob_ref: string`; `size: int`; `media_type: string?`; `sha256: string`; `upload_receipt: object?` | upload capability、quota、media policy；`Content-Type` 缺省为 `application/octet-stream`。 |
| `cx.blob.head` | `query.blob_ref: string` | `header.Authorization: token`; `header.X-Contrix-Wait-For: cursor` | headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?` | 私有 blob 必须验证 actor/device/Space/purpose/expiry；不得通过 header 泄露不可见资源。 |
| `cx.blob.get` | `query.blob_ref: string` | `header.Authorization: token`; `header.Range: string`; `header.X-Contrix-Wait-For: cursor` | bytes；headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?`, `Content-Range?`, `Location?` | 私有 blob 必须验证 actor/device/Space/purpose/expiry；Range 和 redirect 不得泄露不可见资源。 |
| `cx.push.register_device` | `device_id: id`; `push_gateway: url`; `push_key: string` | `platform: string`; `app_id: string`; `display_name: string` | `ok: boolean`; `registration_id: id?`; `expires_at: datetime?` | 只能注册当前 principal/device。 |
| `cx.push.unregister_device` | `device_id: id` | `push_key: string`; `app_id: string` | `ok: boolean` | same device/principal 或 device revocation path。 |
| `cx.push.notify` | `notification: object` | `notification.event_id: id`; `notification.space_id: id`; `notification.sender: did`; `notification.push_hint: string`; `notification.counts: object`; `notification.devices: object[]` | `rejected: object[]` | 来自授权 Sync 或 notification service；E2EE 必须脱敏。 |
| `cx.device_messages.put` | `header.Idempotency-Key: string`; `messages: object` | 每个 target 必须含 `kind`、`content`、`expires_at` | `ok: boolean`; `delivered: object?`; `unknown_devices: object?` | `(sender, Idempotency-Key)` 幂等；目标必须是授权 device；过期或超过 TTL 上限的消息必须拒绝或逐项 reject。 |
| `cx.device_messages.get` | 无 | `query.from: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `limited: boolean?` | 只返回当前 device 队列。 |
| `cx.keys.upload` | `device_id: id`; `device_signature: signature` | `one_time_keys: object`; `fallback_keys: object` | `one_time_key_counts: object`; `fallback_keys: object?` | key 必须链接 self-signing / principal key。 |
| `cx.keys.query` | `device_keys: object` | `timeout_ms: int` | `device_keys: object`; `failures: object?` | 查询范围可按关系 / Space 限制。 |
| `cx.keys.claim` | `one_time_keys: object` | 无 | `one_time_keys: object`; `failures: object?` | one-time key MUST 原子消费。 |
| `cx.keys.keypackages.upload` | `device_id: id`; `key_packages: object[]`; `device_signature: signature` | `expires_at: datetime`; `flow_id: id`; `mls_group_id: string` | `accepted: int`; `rejected: object[]?`; `key_package_refs: id[]?` | MLS KeyPackage MUST 绑定 device key、credential 和 supported cipher suites。 |
| `cx.keys.keypackages.claim` | `claims: object[]` | `timeout_ms: int`; `flow_id: id`; `mls_group_id: string` | `key_packages: object[]`; `failures: object?` | KeyPackage claim MUST 原子保留，重复 claim 不得返回同一 one-time package。 |
| `cx.keys.keypackages.consume` | `key_package_refs: id[]`; `consumer_device_id: id`; `signature: signature` | `flow_id: id`; `epoch: int` | `consumed: id[]`; `failures: object?` | consume MUST 校验 claim holder、epoch 和 package freshness。 |
| `cx.keys.keypackages.revoke` | `key_package_refs: id[]`; `device_id: id`; `signature: signature` | `reason: string` | `revoked: id[]`; `failures: object?` | 只能由 owning device、principal 或授权 admin 撤销。 |
| `cx.keys.backups.put` | `path.backup_id: id`; `backup: object` | `idempotency_key: string` | `status: enum(accepted,duplicate)`; `backup_id: id`; `ciphertext_digest: string` | body MUST validate `cx.schema.key_backup.v1`；path/body backup id 必须一致；服务端不得解密。 |
| `cx.keys.backups.list` | 无 | `query.backup_class: enum(did_recovery,secret_storage,mls_history)`; `query.cursor: cursor`; `query.limit: int` | `backups: object[]`; `next_cursor: cursor?` | 仅返回调用方可见的最小 metadata；不得泄露无关 Space / group membership。 |
| `cx.keys.backups.get` | `path.backup_id: id` | 无 | `backup: object` | 只返回同 principal 授权 device、recovery policy 或授权恢复服务可见的 encrypted backup object。 |
| `cx.keys.backups.delete` | `path.backup_id: id`; `proof: proof` | `reason: string` | `deleted: boolean` | 高风险删除；不等于 device revoke、DID recovery 或 MLS epoch rotation。 |
| `cx.authz.get_effective_grants` | `query.space_id: id`; `query.subject: did` | `query.at: string` | `grants: object[]`; `state_hash: string?`; `evaluated_at: datetime` | subject 本人、Space admin 或授权服务。 |
| `cx.authz.get_invites` | `query.subject: did 或 string` | `query.space_id: id`; `query.cursor: cursor` | `invites: object[]`; `next_cursor: cursor?` | secret invite 不可枚举。 |
| `cx.authz.check` | `actor: did`; `action: string`; `resource: object` | `context: object` | `decision: enum(allow,deny,quarantine,require_review,soft_fail)`; `matched_grants: object[]?`; `applied_constraints: object[]?`; `policy_results: object[]?`; `missing_proofs: object[]?`; `frontier: object?`; `cache_valid_until: datetime?`; `reason_code: string?`; `obligations: object[]?` | Policy allow 不创建 capability；客户端不得把非标准 `allowed` 字段作为规范字段。 |
| `cx.policy.check` | `request_id: string`; `request_canonical_hash: string`; `action: string`; `actor: did`; `source: object` | `space_id: id`; `event_preview: object`; `auth_context: object` | `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `reason_code: string`; `expires_at: datetime`; `obligations: object[]?`; `signature: signature` | 只接收最小披露字段；decision 按 hash 缓存。 |
| `cx.moderation.report` | `space_id: id`; `target_ref: id`; `reason: enum`; `reporter: did` | `description: string`; `evidence_refs: id[]` | `report_id: id`; `status: string`; `routed_to: did[]?` | reporter 必须可见 target；只对 moderators 可见。 |
| `cx.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 不得泄露 private namespace。 |
| `cx.applet.describe` | 无 | 无 | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | public mode 只返回公开 capabilities。 |
| `cx.applet.transaction` | `header.Idempotency-Key: string`; `source_service_did: did`; `events: object[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet 必须验证 event signature、namespace、capability；按 `(source_service_did, Idempotency-Key)` 幂等。 |
| `cx.applet.query_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 namespace。 |
| `cx.applet.query_space` | `path.space_id_or_alias: string` | 无 | `exists: boolean`; `space_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `cx.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | instance list 可要求授权。 |
| `cx.applet.third_party_users` | `query.protocol: string`; external ids | 无 | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 registration namespace 内。 |
| `cx.applet.third_party_locations` | `query.protocol: string`; external ids | 无 | `space_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `cx.mimi.provider_directory` | 无 | `query.provider_id: string`; `query.features: string[]` | `providers: object[]`; `features: object`; `expires_at: datetime?` | 只返回公开 provider capability，不泄露 Space membership。 |
| `cx.mimi.key_material` | `requester: did`; `flow_id: id`; `device_id: id` | `mls_group_id: string`; `epoch: int`; `proofs: proof[]` | `key_packages: object[]?`; `group_info: object?`; `failures: object?` | 必须存在 accepted `cx.mimi.room_binding` 且 requester 有对应 room / device 权限。 |
| `cx.mimi.room_update` | `path.flow_id: id`; `mls_group_id: string`; `update: object` | `epoch: int`; `transcript_hash: string`; `sender: did` | `accepted: boolean`; `room_state_ref: id?`; `rejected: object[]?` | 更新必须映射到 Contrix Flow discussion track / Space policy 授权范围内。 |
| `cx.mimi.notify` | `path.flow_id: id`; `notification: object` | `origin_provider: string`; `routing: object` | `accepted: boolean`; `retry_after_ms: int?` | 只可传递最小 fanout / delivery signal，不得携带未授权明文。 |
| `cx.mimi.submit_message` | `path.flow_id: id`; `sender: did`; `device_id: id`; `ciphertext: object` | `mls_group_id: string`; `epoch: int`; `associated_data: object` | `event_ref: id?`; `delivery: object`; `rejected: object[]?` | 必须校验 MLS epoch、有效 discussion access、capability 和 `cx.mimi.room_binding`。 |
| `cx.mimi.group_info` | `path.flow_id: id` | `query.epoch: int`; `query.include_proof: boolean` | `group_info: object`; `room_binding_ref: id?`; `proofs: object[]?` | 只能返回 requester 授权可见的 MLS groupInfo / room projection。 |
| `cx.mimi.request_consent` | `requester: did`; `target: object`; `purpose: string` | `flow_id: id`; `expires_at: datetime`; `proofs: proof[]` | `consent_id: id`; `status: string`; `challenge: string?` | consent 只表达联系 / invite 意图，不授予 Space read/write。 |
| `cx.mimi.update_consent` | `consent_id: id`; `decision: enum(accept,deny,revoke)`; `actor: did`; `signature: signature` | `reason: string`; `expires_at: datetime` | `status: string`; `updated_at: datetime`; `event_ref: id?` | 必须绑定原 request、target identity proof 和 replay protection。 |
| `cx.mimi.identifier_query` | `identifiers: object[]` | `requester: did`; `privacy_profile: string`; `proofs: proof[]` | `results: object[]`; `proofs: object[]?` | SHOULD 使用 private contact discovery；不得返回原始通讯录或完整关系图谱。 |
| `cx.mimi.report_abuse` | `flow_id: id`; `target_ref: id`; `reporter: did`; `reason: enum` | `evidence_package: object`; `frank: object`; `description: string` | `report_id: id`; `status: string`; `routed_to: did[]?` | E2EE report 只能向授权 moderation recipient 解密 evidence。 |
| `cx.mimi.proxy_download` | `asset_ref: string`; `requester: did` | `flow_id: id`; `ohttp_context: object`; `range: string` | `download_ref: string`; `headers: object?`; `expires_at: datetime?` | 当 Space asset privacy policy 要求 proxy/OHTTP 时不得返回 direct object-store URL。 |
| `cx.account.issue_session_grant` | `principal_did: did`; `device_id: id`; `requested_scopes: string[]`; `proof: proof` | `expires_at: datetime`; `audience: string`; `constraints: object` | `session_grant: object`; `expires_at: datetime`; `capability_refs: id[]?` | 必须绑定 principal、device key、audience 和最小 scope。 |
| `cx.account.device_pair` | `principal_did: did`; `new_device_key: object`; `pairing_proof: proof` | `display_name: string`; `device_metadata: object` | `device_id: id`; `device_grant: object`; `key_backup_hint: object?` | pairing code / proof 必须短期有效且一次性使用。 |
| `cx.account.oidc_callback` | `issuer: url`; `code: string`; `state: string` | `redirect_uri: url`; `nonce: string`; `device_id: id` | `principal_did: did`; `session_grant: object`; `account_status: string` | MUST 校验 state、nonce、issuer binding 和 DID/account linkage。 |
| `cx.admin.get_server_status` | 无 | `query.include: string[]` | `status: string`; `protocol_version: string`; `features: string[]`; `capacity: object?`; `warnings: string[]?` | 公开响应只能包含 operational metadata；敏感细节需要 admin session。 |
| `cx.admin.update_account_status` | `path.account_id: id`; `status: string`; `moderator: did`; `proof: proof` | `reason: string`; `expires_at: datetime`; `notify: boolean` | `account_id: id`; `status: string`; `event_ref: id?`; `updated_at: datetime` | 必须生成可审计 account lifecycle 状态或 admin receipt。 |
| `cx.admin.revoke_device` | `path.device_id: id`; `moderator: did`; `proof: proof` | `reason: string`; `revoke_sessions: boolean` | `device_id: id`; `revoked: boolean`; `event_ref: id?` | 必须撤销 device grant、session grant 和相关 key package。 |
| `cx.admin.get_moderation_queue` | 无 | `query.space_id: id`; `query.status: string`; `query.cursor: cursor`; `query.limit: int` | `items: object[]`; `next_cursor: cursor?`; `counts: object?` | 只对授权 moderator / compliance service 可见，证据按 policy 最小披露。 |
| `cx.media.ice_config` | `space_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `mode: string` | 无 | `ttl_seconds: int`; `ice_servers: object[]`; `policy: object`; `signature: signature` | actor 必须有 call/media capability；Media Service 必须被委托。 |

## 3. Events API

### 3.1 提交 Event

```text
POST /api/v1/events
```

请求示例（非完整 schema）：

```json
{
  "event": {
    "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
    "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
    "actor_id": "did:web:alice.example.com",
    "actor_seq": 42,
    "kind": "cx.flow.update",
    "created_at": "2026-04-22T08:30:00Z",
    "hlc": "01970e589d21-0007-a13f9c2e",
    "prev_refs": [
      "cx:event:019640ed-0000-7000-8000-000000000000"
    ],
    "auth_refs": [
      "cx:event:0196410c-0000-7000-8000-000000000000"
    ],
    "payload": {},
    "proofs": []
  }
}
```

响应示例（非完整 schema）：

```json
{
  "status": "accepted",
  "accepted": ["cx:event:019640ed-8000-7000-8000-000000000000"],
  "actor_frontier": {
    "actor_id": "did:web:alice.example.com",
    "actor_seq": 42,
    "event_id": "cx:event:019640ed-8000-7000-8000-000000000000"
  },
  "cursor": "cx:cursor:eyJ2IjoxLCJwIjoiYmFycmllciJ9"
}
```

若 `expected_frontier` 校验失败，返回 `409 cas_conflict`。协议级写入单元是 signed Event Envelope；实现 MAY 在 SDK 或本地接口中接受 operation builder，但在进入网络传播、同步或审计前 MUST 转换为 Event Envelope。接收方不得要求 Event 先归属某个 batch receipt、checkpoint 或 predecessor commit 才承认其 canonical history 地位。

`events[]` 批量提交按数组顺序处理。已接受的前序项可以被同批后续项的 `prev_refs`、`auth_refs` 或显式 payload reference 解析；后续项不得引用同批中尚未处理、已拒绝或隔离的 Event 作为已接受事实。单项失败不回滚整批，响应必须把成功项列入 `accepted[]`，幂等重复列入 `duplicate[]`，失败项列入 `rejected[]` 或等价隔离结果。

### 3.2 批量获取 Event

```text
POST /api/v1/events/batch-get
```

请求示例（非完整 schema）：

```json
{
  "event_ids": ["cx:event:019640ed-8000-7000-8000-000000000000"],
  "include_payload": true
}
```

响应示例（非完整 schema）：

```json
{
  "events": [],
  "missing": [],
  "unauthorized": []
}
```

### 3.3 查询 / 回填 Event（`cx.events.query`）

```text
GET /api/v1/events?spaces=<id>&from=<cursor>&direction=forward&limit=500
GET /api/v1/events?actors=<did>&from=<cursor>&direction=backward&limit=500
GET /api/v1/events?spaces=<id>&actors=<did>&from=<cursor>&until=<cursor>
```

`spaces`/`actors` 都是数组（`spaces=A&spaces=B`）；同一参数的多个值之间是 union，跨参数（spaces × actors）是 intersection。`direction=forward` 是默认值；`direction=backward` 用来回填历史。`from` 和 `until` 可同时给出形成闭区间。

响应示例（非完整 schema）：

```json
{
  "events": [],
  "next_cursor": "opaque",
  "prev_cursor": "opaque",
  "has_more": true
}
```

`next_cursor` 在请求方向上继续走；`prev_cursor` 允许客户端反向继续（替代旧 `cx.sync.backfill` 的双向语义）。

### 3.4 流式订阅 Event（`cx.events.subscribe`）

```text
GET /api/v1/events/subscribe?spaces=<id>&from=<cursor>&include_history=true
```

支持多 space / actor 一次订阅；`include_history=true` 时服务端先吐历史，再发出 `catchup_complete` 帧切到实时尾部。

Frame:

```json
{ "kind": "event", "space_id": "cx:space:01...", "cursor": "opaque", "payload": {} }
{ "kind": "catchup_complete", "space_id": "cx:space:01...", "cursor": "opaque" }
{ "kind": "frontier", "space_id": "cx:space:01...", "cursor": "opaque" }
{ "kind": "heartbeat" }
{ "kind": "epoch_rotation", "space_id": "cx:space:01...", "payload": {"new_epoch": 17} }
{ "kind": "dropped", "space_id": "cx:space:01...", "cursor": "opaque" }
{ "kind": "unauthorized", "space_id": "cx:space:01..." }
{ "kind": "resync_required", "space_id": "cx:space:01..." }
```

同一语义流 MAY 通过 WebSocket、SSE 或长轮询承载，但 HTTP/JSON 默认参考路径是 `/api/v1/events/subscribe`。`/sync/stream` 仅用于具体 transport 的内部帧名，不定义为新的 canonical operation。客户端必须把 `dropped` 与 `resync_required` 当作硬信号——前者要求按 cursor 重新 `cx.events.query` 补齐，后者要求重建本地状态。

## 4. Identity API

```text
POST /api/v1/identity/resolve
```

请求示例（非完整 schema）：

```json
{
  "did": "did:web:alice.example"
}
```

响应示例（非完整 schema）：

```json
{
  "did_document": {
    "id": "did:web:alice.example",
    "verificationMethod": [],
    "service": []
  },
  "key_log_head": "cx:keyevt:01JS...",
  "seq": 5
}
```

Resolver MUST 返回足够的方法相关证据，使客户端能够验证 control history。

## 5. Sync API

`/sync/*` 在 v1 只承载 **account 聚合**（跨 Space frontier、to_device、account_data、device_lists、presence、unread / notification counts）和 snapshot manifest。逐 Space 的事件读取与流式订阅已收敛到 `/events/*`（`cx.events.query`、`cx.events.subscribe`），见 §3.3 / §3.4。

### 5.1 账号聚合同步（`cx.sync.account`）

```text
POST /api/v1/sync
```

该端点对应 `cx.sync.account`，用于客户端按 account / Space filter 拉取稳定的跨 Space delta 视图（含 to_device、account_data、device_lists、presence）。请求与响应形状见 `client-sync.md`。它不是裸事件读取——裸事件读取请使用 `cx.events.query` / `cx.events.subscribe`。

## 6. Directory API

```text
POST /api/v1/directory/search-spaces
POST /api/v1/directory/resolve-space
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

Directory 端点 MUST 在每个结果上分别应用资源可发现性、请求方证明、审核策略与授权过滤。

对于隐藏或未授权访问的资源，`resolve-*` SHOULD 返回与"不存在"不可区分的 `not_found`。

## 7. Blob API

### 7.1 上传

```text
POST /api/v1/blob/upload
```

Content type MAY 取 `application/octet-stream` 或 `multipart/form-data`。

响应示例（非完整 schema）：

```json
{
  "blob_ref": "cx:blob:sha256:e3b0...",
  "size": 102450,
  "media_type": "image/png"
}
```

### 7.2 下载

```text
HEAD /api/v1/blob/get?blob_ref=<blob_ref>
GET /api/v1/blob/get?blob_ref=<blob_ref>
```

客户端 MUST 重新计算内容哈希并与 `blob_ref` 比对。
若哈希不匹配，客户端 MUST 拒绝响应并丢弃内容；服务端在上传、代理或镜像校验时发现不匹配 MUST 返回 `422 digest_mismatch`。

## 8. 标准错误响应

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

## 9. 标准错误码

标准错误码、HTTP 状态码与逐项 reason_code 的 **canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。本节不再在 Markdown 中维护并行表格；任何新增 / 修改 / 删除错误码 MUST 先更新 registry。

`api-conventions.md` §5.1 是该 registry 的解释性 narrative 视图（解释每个 code 的使用场景）；它本身也以 registry 为准，发现差异时以 registry 为准。

实现使用规则：

- 客户端收到 `429` MUST 优先遵守 `Retry-After` header；若缺失再使用 body 中的 `retry_after_ms`。`503` 在带有 `Retry-After` 时也必须按该时间退避。收到 `409` SHOULD 拉取最新状态后退避重试。
- `unsupported_feature` 用于 `Event.requirements.features[]` / `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `cx.*` Event kind；二者不得互相替代。
- 通用 `conflict` 仅作为抽象 base code 出现在 narrative；实现 SHOULD 返回 registry 中更精确的 409 子 code（`cas_conflict` / `causal_conflict` / `dependency_missing` / `duplicate_conflict` / `epoch_mismatch` / `rank_exhausted` / `stale_frontier` / `state_mismatch` / `discussion_track_disabled` / `key_unavailable`）。

## 10. 安全与抗滥用

服务端 SHOULD 在高风险入口实施一致性失败语义：

- 对目录/resolve 查询、join 探测、公开元数据接口，未授权请求不应返回可区分 `not_found` 与 `forbidden` 的信息差异。
- 联邦入口与 policy check 入口应记录来源 service DID + 来源域名哈希，结合 `rate_limited` 与 `temporarily_unavailable` 作回压。
- 对来源签名缺失/验证失败的入口请求，应优先走 reject + audit，不得影响已认证正常来源的可用性。
- 对 URL 中携带认证材料的请求，应 reject + redact log，不得进入正常认证 fallback。
