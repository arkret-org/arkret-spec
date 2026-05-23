---
title: Service HTTP/JSON Binding
---

## 1. 目标

本文定义 Contrix 默认 HTTP/JSON binding 的路径、请求形状和错误响应。

Operation 语义本身可映射到不同 transport；但 **v1 core wire conformance 必须提供本文定义的 HTTP/JSON binding**。其他 transport binding（gRPC、WebSocket、SSE、message queue、libp2p 或 IPC）只能作为 extension profile 出现，并且必须映射到 `service-surface.md` 中定义的等价语义。

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
| `/events/*` | 客户端、Principal Server、授权 Event 副本 | signed Event 提交、按 ID 读取、批量读取、actor/Realm 双向历史查询(query)、流式订阅(subscribe，含 bounded catch-up replay)、frontier 查询。 | `operations-sync.md`、`service-surface.md` |
| `/account/*` | 客户端、Principal Server | account 聚合 streaming 订阅(`GET /account/subscribe`)、describe。逐 Realm 的事件流读取走 `/events/*`。 | `client-sync.md`、`service-surface.md` |
| `/snapshot/*` | 客户端、Principal Server | Realm snapshot manifest 入口(`GET /snapshot/head`)。 | `client-sync.md`、`service-surface.md` |
| `/projection/*` | 客户端、Principal Server | 派生 lifecycle projection 读取：Space / Flow / Morph 当前状态列表。 | `realm-and-space.md`、`flow-and-message.md`、`morph.md` |
| `/directory/*` | 客户端、服务 | Realm / Organization / Actor / handle 的授权发现与解析。 | `discovery-directory.md` |
| `/blob/*` | 客户端、服务 | Blob 上传、HEAD、authenticated download。 | `media-and-blob.md` |
| `/push/*` | 客户端、Sync、Push Gateway | 推送设备注册、注销、脱敏唤醒投递。 | `push-notifications.md` |
| `/device_messages/*`、`/keys/*` | E2EE 客户端、Principal Server | to-device、one-time key、fallback key、device list 相关操作。 | `device-lifecycle.md` |
| `/authz/*`、`/policy/check` | 客户端、Events API、Sync、Policy Server | capability 预检查、policy server 签名决策。Canonical path 是 `/api/v1/policy/check`(`cx.policy.check`)。 | `capabilities.md`、`policy-server.md` |
| `/contrix/v1/ice-config` | 通话客户端、Media Service | TURN/STUN/ICE 短期凭证。 | `webrtc-signaling.md` |
| `/moderation/*` | 客户端、审核服务 | 举报、审核队列或扩展审核入口。 | `governance/content-moderation.md` |
| `/applet/*` | Contrix 服务调用 Applet | applet ping / describe、transaction push、ghost actor / portal 查询。 | `applet-integration.md` |

客户端视角的常用 API 集合通常包括 `/server`、`/identity`、`/events`、`/account`、`/snapshot`、`/projection`、`/directory`、`/blob`、`/push`、`/device_messages`、`/keys`、`/authz`。服务间 API 集合通常包括 `/events`、`/account`、`/authz`、`/policy/check`、`/applet` 和 `/push/notify`。搜索、inbox、notification 和 View projection 默认是客户端本地派生；`/projection/*` 只暴露 Space / Flow / Morph lifecycle 派生读模型，且属于 extension surface，必须由服务显式声明支持。

新增顶层 REST 命名空间前，规范必须同步更新 `service-api-schema.mdx`、feature discovery 返回值和对应 conformance profile。实现不得用未声明路径绕过 canonical operation、capability、幂等、分页或错误语义。

### 2.2 端点契约规则

每个 REST endpoint 的规范定义必须至少包含：

- `operation_id` / canonical operation。
- Path 参数、query 参数和 request body 字段类型。
- 成功响应字段类型。
- 认证方式：`public_metadata`、`user_session`、`device_proof`、`service_signature`、`policy_token`、`applet_signature` 等。
- 访问限制：Realm membership、history visibility、capability、service delegation、namespace、plaintext visibility、rate limit、quota。
- 幂等键：写接口使用 `Idempotency-Key` header、`event_id`、`request_id` 或 canonical request hash。
- 失败时使用标准 error envelope。

JSON 示例只用于说明，不构成完整 schema。正式接口定义 MUST 使用字段表说明字段名、位置、类型、是否必填、含义和约束。

默认规则：

- 除明确标记为 `public_metadata` 的 describe / discovery 外，所有 endpoint MUST 认证。
- 认证只证明调用方身份；服务仍 MUST 执行 capability、Realm policy、history visibility、service delegation 和 revocation 检查。
- 服务间调用 MUST 使用 HTTP Message Signature 或等价 service DID proof，并绑定 method、target URI、content digest、origin service DID 和 destination service DID；shared ingress / 多租户 / allowlist endpoint 场景还 MUST 绑定 destination service endpoint digest。
- 服务间调用的 `origin` / `destination` 必须是 service DID，且必须与 DID Document service endpoint、目标 URL、Realm policy / service delegation 和签名 transcript 一致。
- 受保护 endpoint 不得接受 query string 中的 token、API key 或签名材料；临时下载 URL 只能使用短时效、单用途、可撤销的派生 token。
- 返回 `not_found` 的 endpoint MUST 对“不存在”和“存在但不可见”保持一致失败语义，除非调用方已有管理权限。
- 所有批量读取 MUST 支持 `limit` 上限，分页 cursor 必须是不透明 token。
- 路由层 MUST 对 `/api/v1/*` 与 `/contrix/v1/*` 下的未知路径返回 `404 unrecognized_endpoint`，对已知路径的错误 method 返回 `405 method_not_allowed`，且不得进入业务逻辑。

### 2.3 端点契约清单

类型简写：`did` 为 DID URI，`id` 为协议对象 ID，`cursor` / `token` 为 opaque string，`signature` 为 `{kid, alg?, sig}`，`proof` 为 DID / HTTP message / detached JWS proof。`events` 为 Event Envelope 数组。

| Endpoint | Request 类型 | Auth / 访问限制 | Success 类型 |
| --- | --- | --- | --- |
| `GET /api/v1/server/describe` | query: none 或 `service_type?` | `public_metadata`；不得返回私有 topology、secret 或未授权 internal endpoint。 | `ServiceDescribe`（`cx.schema.service_describe.v1`；必须含 `service_did`、`trust_domain`、claim-level 字段、`plaintext_visibility`、`development_mode`，且 `development_mode=true` 时 `verified_profiles=[]`） |
| `GET /api/v1/identity/describe` | query: none | `public_metadata`；可限流。 | `ServiceDescribe`；identity-specific 能力通过 `supported_features` / `limits` / 扩展字段表达。 |
| `POST /api/v1/identity/resolve` | body `{did: did, include?: string[]}` | `public_metadata`；private DID MAY require `user_session` 或 presentation proof。 | `{did_document, key_log_head?, seq?, receipts?, method_evidence?}` |
| `GET /api/v1/identity/document` | query `{did: did, version?: string}` | 同 `identity.resolve`。 | `{did_document, head_event_hash?, seq?, receipts?}` |
| `GET /api/v1/identity/log` | query `{did: did, cursor?: cursor, limit?: int}` | public DID 可公开；private / pairwise DID MUST require holder-approved proof。 | `{events[], next_cursor?, has_more}` |
| `POST /api/v1/identity/submit-did-operation` | body `{did: did, did_method: string, seq?: int, prev_event_hash?: string, operation: object, proofs: proof[], policy_context?: object}` | `device_proof` 或 recovery proof；MUST 满足 DID method / key-log 授权；`operation` 是 DID-method-specific 原始操作，不是通用 JSON Patch。 | `{status, did, seq?, head_event_hash?, operation_ref?, receipts?}` |
| `GET /api/v1/identity/receipts` | query `{did: did, head: string}` | 同 DID 可见性；witness 可公开最小 receipt。 | `{receipts[], threshold_met?: boolean}` |
| `GET /api/v1/events/describe` | query none 或 `{actor_id?: did, realm_id?: id}` | `public_metadata` 或 `user_session`；私有 frontier 需认证。 | `ServiceDescribe`；event schema / reducer / signature 能力通过 `supported_features`、`supported_profiles`、`limits` 或扩展字段表达。 |
| `POST /api/v1/events` | body 是 canonical `EventEnvelope`（单事件）或 `{events: EventEnvelope[]}`（批量）。MUST NOT 使用 `{event: ...}` wrapper。 | `user_session` / `device_proof` / `service_signature`；MUST 验证 actor DID、签名、capability、Realm policy、`actor_seq`、`prev_refs`、`refs[role=authorized_by]`。 | `{status, accepted[], duplicate[]?, rejected[]?, actor_frontier?, realm_frontier?, cursor?}` |
| `GET /api/v1/events/{event_id}` | path `{event_id: id}` query `{include_payload?: boolean}` | Event 可见性按 Realm policy / history visibility / E2EE envelope 判断；不可见时返回 `not_found`。 | `{event, visibility?, receipts?}` |
| `POST /api/v1/events/resolve` | body `{event_ids?: id[], event_hashes?: string[], include_payload?: boolean}` | 同 Event read；payload 可见性按 Realm policy / E2EE envelope 判断。 | `{events[], missing[], unauthorized[]?}` |
| `GET /api/v1/events` | query `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object}` | 调用方必须对每个 selector 元素满足读取约束：actor scope 走 actor history visibility；realm scope 走 membership frontier + history visibility + E2EE epoch policy。`realms[]` ∪ 内部、`actors[]` ∪ 内部、二者组合为交集。批次内顺序规则见 §3.3。 | `{events[], next_cursor?, prev_cursor?, has_more}` |
| `GET /api/v1/events/subscribe` | query `{realms?: id[], actors?: did[], after?: cursor, catchup?: boolean}` | 同 `GET /events` 的逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性边界。授权丢失通过 per-realm `unauthorized` 帧通知，不中断整条流。 | event stream frames `{kind: event\|frontier\|heartbeat\|catchup_complete\|epoch_rotation\|dropped\|resync_required\|unauthorized, realm_id?: id, cursor?: cursor, payload?: object}` |
| `GET /api/v1/events/frontier` | query `{actor_id?: did, realm_id?: id}` | 返回调用方可见范围内 frontier；不得泄露不可见 Realm 或 private DID。 | `{frontier, receipts?}` |
| `POST /api/v1/ephemeral` | body `cx.schema.ephemeral_envelope.v1` (`kind` ∈ `cx.presence` / `cx.typing` / `cx.receipt.read` / `cx.call.signal`) | `user_session` 或 service signature；actor 必须可在 `realm_id` 的 ephemeral channel 中广播该 kind，并持有对应 `cx.presence.broadcast` / `cx.typing.broadcast` / `cx.receipt.broadcast` / `cx.call.signal.send` action。 | `{accepted: true, kind, realm_id, dispatched_to?, server_received_at?}`；不生成 Event ID、不推进 actor_seq / Realm frontier。 |
| `GET /api/v1/account/subscribe` | query `{after?: cursor, catchup?: boolean, filter?: object, set_presence?: enum}` | `user_session` bound to principal/device。聚合账号视角 delta(跨 Realm frontier、to_device、account_data、device_lists、presence、unread / notification counts) streaming NDJSON 推送,不是裸事件读。 | `application/x-ndjson` AccountSubscribeFrame 流;frame kinds: `delta` / `catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`。 |
| `POST /api/v1/account/cursor/revoke` | body `{cursor: cursor, reason_code: string, revoke_scope?: enum(this_cursor,same_device,same_session)}` | `user_session` bound to principal/device；high-assurance optional profile。 | `{revoked: boolean, expires_at: datetime}`；撤销命中后的 cursor 使用返回 `cursor_revoked`，不得推进任何 server-side state。 |
| `GET /api/v1/account/describe` | query none | `public_metadata` 或 `user_session`；私有 limits 可认证后返回。 | `ServiceDescribe`；私有 frontier 只能作为认证后扩展字段返回。 |
| `GET /api/v1/snapshot/head` | query `{realm_id: id}` | Realm read；snapshot manifest 必须签名，并包含 `event_set_commitment`。 | `{snapshot_ref, state_hash, frontier, event_set_commitment, verification_hints?, signature}` |
| `GET /api/v1/projection/spaces` | query `{realm_id: id, include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | `user_session` 或服务签名；调用方必须满足该 Realm 的 metadata/read 可见性。 | `{realm_id, spaces[], total, next_cursor?, has_more}`；`spaces[]` 行含 `space_id, realm_id, kind, title, parent_ref?, rank?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `GET /api/v1/projection/flows` | query `{realm_id: id, include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | 同 `cx.projection.spaces`。 | `{realm_id, flows[], total, next_cursor?, has_more}`；`flows[]` 行含 `flow_id, realm_id, title?, summary?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `GET /api/v1/projection/morphs` | query `{realm_id: id, include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | 同 `cx.projection.spaces`。 | `{realm_id, morphs[], total, next_cursor?, has_more}`；`morphs[]` 行含 `morph_id, realm_id, morph_type, title?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `GET /api/v1/directory/describe` | query none | `public_metadata`；可限流。 | `ServiceDescribe`；directory resource / discovery capability 放入 `supported_features` / `limits` / 扩展字段。 |
| `POST /api/v1/directory/search-realms` | body `{query?: string, organization_did?: did, parent_realm_id?: id, requester?: did, proofs?: proof[], cursor?: cursor, limit?: int}` | discoverability + requester proof + policy filtering；隐藏资源不泄露存在性。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-realm` | body `{realm_id?: id, alias?: string, invite_token?: string, signed_link?: string, requester?: did, proofs?: proof[]}` | invite / restricted / secret Realm 按统一 `not_found` 失败。 | `{space_preview, stripped_state?, join_rule?, via_services?}` |
| `POST /api/v1/directory/search-organizations` | body `{query?: string, claims?: object, cursor?: cursor, limit?: int}` | 仅返回公开或授权可发现组织。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-organization` | body `{organization_did?: did, handle?: string, proofs?: proof[]}` | 公开组织 DID 可解析不表示成员或拓扑公开。 | `{organization_preview, did_document_ref?, endorsements?}` |
| `POST /api/v1/directory/search-actors` | body `{query?: string, realm_id?: id, organization_did?: did, cursor?: cursor, limit?: int}` | 不得泄露 pairwise/private DID 或未披露组织账号。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/search-users` | body `{q: string, realm_id?: id, limit?: int, intent?: "mention"\|"invite"\|"member_add"}` | `user_session`; 用于 mention autocomplete / 成员添加候选，必须受共同 Realm / directory policy 限制。请求词不得进入 URL、Referer 或明文 access log。 | `{results[]}`；每项 MAY 含 `{handle, handle_uri, display_name?, verified?, subject?, recipient_service_did?}`，但受限 handle 未授权时不得披露 DID / service DID。 |
| `POST /api/v1/directory/resolve-handle` | body `{handle: string, expected_did?: did, proof_challenge?: string, intent?: "lookup"\|"mention"\|"invite"\|"member_add", realm_id?: id, requester?: did, proofs?: proof[]}` | 按 handle 双向验证规则；受限 / 组织 handle 需 presentation；返回 `recipient_service_did` 时必须有 issuer claim / policy 证明。 | `{did, subject, handle, handle_uri, verified: boolean, claims?, recipient_service_did?, delivery_binding_hint?, source_refs?, expires_at?}` |
| `POST /api/v1/blob/upload` | body binary/multipart + metadata `{realm_id?, sha256?, size, media_type?, filename?, purpose?}`；`Content-Type` optional | `user_session`; upload capability、quota、media policy；私有 blob 绑定 Realm / actor。 | `{blob_ref, size, media_type?, sha256, upload_receipt?}` |
| `HEAD/GET /api/v1/blob/get` | query `{blob_ref: string}` headers `Authorization?`, `Range?`, `X-Contrix-Wait-For?` | 公开 blob 可匿名；header auth 路径必须验证 actor/device/Realm/purpose/expiry；除 §5.4 `cx.blob.presign` 的短 TTL bearer URL 例外外，不得 query string 认证。 | bytes 或 headers `{Content-Length?, Digest?, Cache-Control, Content-Type?, Content-Disposition?, Content-Range?}` |
| `POST /api/v1/push/register-device` | body `{device_id: id, push_gateway: url, push_key: string, platform?: string, app_id?: string, display_name?: string, recipient_service_did?: did}` | `user_session` for same principal/device；registration 作用域绑定当前 Principal Server service DID；push_key 必须被加密或最小披露存储。 | `{ok: true, registration_id?, expires_at?}` |
| `POST /api/v1/push/unregister-device` | body `{device_id: id, push_key?: string, app_id?: string}` | `user_session` for same device/principal 或 device revocation path。 | `{ok: true}` |
| `POST /api/v1/push/notify` | body `{notification: {event_id?, realm_id?, type, sender?, push_hint?, counts?, devices[]}}` | 来自被授权 Sync 或通知服务的 `service_signature`；E2EE 时 MUST 做 blind / 最小化处理。 | `{rejected[]}` |
| `POST /api/v1/device_messages` | header `Idempotency-Key` body `DeviceMessagesPutRequest {messages: {principal_id: {device_id: DeviceMessageTarget {kind, content, expires_at}}}}` | sender `user_session` / device key；目标必须是授权 device；服务端入队前 MUST materialize `DeviceMessageEnvelope` 并绑定 `recipient_principal_id` / `recipient_device_id` / `expires_at`；按 `(sender, Idempotency-Key)` 幂等。验证消息使用 `cx.key.verification.*` kind，且不得作为持久 Event history；缺失、已过期或超过 TTL 上限的消息 MUST reject。 | `{ok: true, delivered?, unknown_devices?}` |
| `GET /api/v1/device_messages` | query `{from?: cursor, limit?: int}` | `user_session` bound to current device；只返回该 device 队列。 | `{events: DeviceMessageEnvelope[], next_cursor?, limited?}` |
| `POST /api/v1/keys/upload` | body `{device_id: id, one_time_keys?: object, fallback_keys?: object, device_signature: signature}` | current device proof；key 必须链接 self-signing / principal key。 | `{one_time_key_counts, fallback_keys?}` |
| `POST /api/v1/keys/query` | body `{device_keys: {principal_id: string[]}, timeout_ms?: int}` | `user_session`; 查询范围可按关系 / Realm 限制。 | `{device_keys, failures?}` |
| `POST /api/v1/keys/claim` | body `{one_time_keys: {principal_id: {device_id: algorithm}}}` | `user_session`; one-time key MUST 原子消费。 | `{one_time_keys, failures?}` |
| `PUT /api/v1/keys/backups/{backup_id}` | path `{backup_id}` body `cx.schema.key_backup.v1` | current device proof / DID proof / recovery proof；path 与 body backup id 必须一致。 | `{status, backup_id, ciphertext_digest}` |
| `GET /api/v1/keys/backups` | query `{backup_class?: string, cursor?: cursor, limit?: int}` | `user_session` bound to current principal/device 或 recovery proof。 | `{backups[], next_cursor?}` |
| `GET /api/v1/keys/backups/{backup_id}` | path `{backup_id}` | 同 principal 当前授权 device、recovery policy 或授权组织恢复服务。 | `cx.schema.key_backup.v1` |
| `DELETE /api/v1/keys/backups/{backup_id}` | path `{backup_id}` | 高风险 device proof、DID proof 或 recovery policy proof。 | `{deleted: true}` |
| `GET /api/v1/authz/effective-grants` | query `{realm_id: id, subject: did, at?: string}` | subject 本人、Realm admin、authorized service；不得枚举无关 subject。 | `{grants[], state_hash?, evaluated_at}` |
| `GET /api/v1/authz/invites` | query `{realm_id?: id, subject: did 或 string, cursor?: cursor}` | subject 本人或 inviter/admin；secret invites 不可枚举。 | `{invites[], next_cursor?}` |
| `POST /api/v1/authz/check` | body `{actor_id: did, action: string, resource?: object, context?: object}` | caller 必须是相关 actor、Events/Sync 预检查服务或 policy-authorized service。 | `{decision, matched_grants?, applied_constraints?, policy_results?, missing_proofs?, frontier?, cache_valid_until?, reason_code?, obligations?}` |
| `POST /api/v1/policy/check` | body `PolicyCheckRequest {request_id, realm_id, request_canonical_hash, action, actor, source, event_preview?, auth_context?}` | `policy_token` / `service_signature`; 只接收最小披露字段。 | `PolicyCheckResponse {request_id, bound_to, decision, reason_code, expires_at, auth_state_hash, policy_frontier_hash, membership_frontier_hash, obligations?, signature}`。 |
| `POST /api/v1/moderation/report` | body `{realm_id: id, target_ref: id, reason: enum, description?: string, reporter: did, evidence_refs?: id[]}` | `user_session`; reporter 必须可见 target；report 仅对 moderators 可见。 | `{report_id, status, routed_to?}` |
| `GET /api/v1/applet/ping` | query none | `public_metadata` 或 `service_signature`；不得泄露 private namespace。 | `{ok, applet_id, service_did, protocol_version}` |
| `GET /api/v1/applet/describe` | query none | `service_signature` SHOULD；public mode 只返回公开 capabilities。 | `ServiceDescribe`；applet protocols / namespaces / auth capability 放入 `supported_features` / `limits` / 扩展字段。 |
| `POST /api/v1/applet/transactions` | header `Idempotency-Key` body `{source_service_did, events: EventEnvelope[], ephemeral?}` | `service_signature`; Applet 必须验证每个 event signature、namespace 和 capability；按 `(source_service_did, Idempotency-Key)` 幂等。 | `{ok: true, rejected?, retry_after_ms?}` |
| `GET /api/v1/applet/actors/{actor_id}` | path `{actor_id}` | `service_signature`; actor_id 必须命中 Applet actor namespace。 | `{exists, actor_id, display_name?, external_ref?}` 或 `not_found` |
| `GET /api/v1/applet/realms/{realm_id_or_alias}` | path `{realm_id_or_alias}` | `service_signature`; 必须命中 portal namespace 或授权查询。 | `{exists, realm_id?, title?, external_ref?}` |
| `GET /api/v1/applet/protocols/{protocol}` | path `{protocol}` | 可 public_metadata；实例列表可要求授权。 | `{protocol, display_name, icon_blob?, field_types, instances?}` |
| `GET /api/v1/applet/third_party/users` | query `{protocol, ...external_ids}` | `service_signature`; 查询字段必须在 registration namespace 内。 | `{actor_id?, exists, external_ref?}` |
| `GET /api/v1/applet/third_party/locations` | query `{protocol, ...external_ids}` | `service_signature`; 查询字段必须在 portal namespace 内。 | `{realm_id?, exists, external_ref?}` |
| `POST /contrix/v1/ice-config` | body `{realm_id: id, call_id: id, actor_id: did, device_id: id, mode: string}` | `user_session`; actor 必须有 call/media capability，Media Service 必须被 Realm policy 委托。 | `{ttl_seconds, ice_servers[], policy, signature}` |
| `POST /api/v1/keys/keypackages/upload` | body `{device_id, keypackages[]}` | `user_session` + 当前 device proof;每条 KeyPackage 必须 self-signed 并通过当前 device 签发。 | `{accepted, rejected?, available_count}` |
| `POST /api/v1/keys/keypackages/claim` | body `{principal_id, count?: int}` | `user_session`;一次性 KeyPackage MUST 原子消费(同 `cx.keys.claim`)。 | `{keypackages[]}` |
| `POST /api/v1/keys/keypackages/consume` | body `{keypackage_ref}` | `service_signature`(MLS group creator 通常是 service-side 调用) 或 `user_session`。 | `{ok: true, consumed_at}` |
| `POST /api/v1/keys/keypackages/revoke` | body `{keypackage_ref, reason?}` | `user_session` + 当前 device proof;不可撤销已消费的 KeyPackage。 | `{ok: true, revoked_at}` |
| `POST /api/v1/directory/announce` | body `{resource_kind, resource_id, discoverability, signatures[]}` | `user_session` 或 `service_signature` 视 resource_kind;principal MUST 签发 announcement 凭据。 | `{ok: true, announcement_id, valid_until?}` |
| `POST /api/v1/directory/withdraw` | body `{announcement_id, reason?}` | `user_session`;只能撤销自己签发的 announcement。 | `{ok: true, withdrawn_at}` |
| `POST /auth/account/session-grants` | body `SessionGrantRequest {principal_id, device_id?, requested_scope?, proof}` | DID-bound signature / paired device proof / passkey assertion / OIDC code exchange proof；此 endpoint **不**挂在 `/api/v1` 下，SDK MUST 走 path-level `servers: https://{host}` 覆盖。请求体 proof MUST 绑定 challenge、audience、request canonical hash、principal 与 device。 | `SessionGrantResponse {principal_id, device_id?, session_grant, expires_at, granted_scope?}` |
| `POST /auth/account/device-pair` | body `{pairing_code, new_device_pubkey, challenge_signature}` | `user_session` + existing device proof + freshly minted pairing code(短 TTL, one-time, audience-bound to this Auth Server origin); endpoint 与 session-grants 同一部署本地 namespace；服务端 MUST 对 `(principal_id, source_device_id, target_origin)` 限速并防重放。 | `{device_id, authorized_event_ref}` |
| `POST /auth/account/oidc/callback` | body `AccountOidcCallbackRequest {state, code, nonce?, redirect_uri?}` | `public_metadata` 的回调入口(OIDC IdP 重定向);服务端 MUST 校验 `state` / `nonce` / `redirect_uri` 并把外部主体映射到 Contrix principal。 | `AccountOidcCallbackResponse {principal_id, session?}` 或 `{redirect_url}` |
| `GET /admin/server/status` | query none | `admin_bearer`(MUST 是 admin role 的 user_session)。该 endpoint **不**挂在 `/api/v1` 下。 | `{service_did, build, uptime_seconds, registry_versions, queues?}` |
| `POST /admin/accounts/{account_id}/status` | path `{account_id}` body `{action: enum(suspend, restore, ...), reason?}` | `admin_bearer`;reducer 同时写 `cx.account.status`(必须由 admin 签发)。 | `{ok: true, status, applied_at}` |
| `POST /admin/devices/{device_id}/revoke` | path `{device_id}` body `{reason?}` | `admin_bearer`;触发 `cx.device.revoked` + capability fanout。 | `{ok: true, revoked_at}` |
| `GET /admin/moderation/queue` | query `{realm_id?, status?, cursor?, limit?}` | `admin_bearer` 与 moderator capability;只返回调用方有 moderation scope 的 Realm。 | `{reports[], next_cursor?}` |
| `GET /api/v1/mimi/provider-directory` | query `{provider_did?, capabilities?: string[]}` | `public_metadata`;provider 列表本身公开。 | `{providers[]}` |
| `POST /api/v1/mimi/key-material` | body `{requester: did, flow_id: id, device_id: id, mimi_room_uri?: string, realm_id?: id, mls_group_id?: string, epoch?: int, proofs?: proof[]}` | `service_signature`(MIMI provider-to-provider) 或 `user_or_service`。 | `{key_packages?, group_info?, failures?, signature?}` |
| `PUT /api/v1/mimi/rooms/{flow_id}/update` | path `{flow_id}` body `cx.schema.mimi_interop.v1` room update | `service_signature`。 | `{ok: true, version}` |
| `POST /api/v1/mimi/rooms/{flow_id}/notify` | path `{flow_id}` body MIMI notify body | `service_signature`。 | `{accepted: true}` |
| `POST /api/v1/mimi/rooms/{flow_id}/messages` | path `{flow_id}` body `{events[]}` | `service_signature`;MIMI 跨 provider message。 | `{accepted[], rejected?[]}` |
| `GET /api/v1/mimi/rooms/{flow_id}/group-info` | path `{flow_id}` | `service_signature` 或 `user_session` (member proof)。 | `OperationResult.data.group_info`（字段对齐 `cx.schema.mimi_interop.v1` 的 MIMI provider directory profile） |
| `POST /api/v1/mimi/consent/request` | body MIMI consent request body | `service_signature` 或 `user_session`。 | `{consent_id, status}` |
| `POST /api/v1/mimi/consent/update` | body MIMI consent update body | `service_signature` 或 `user_session`。 | `{ok: true, applied_at}` |
| `POST /api/v1/mimi/identifiers/query` | body `{identifiers[], proof?}` | `service_signature` 或 `user_session`;不得用于枚举攻击,query MUST 限速。 | `{results[]}` |
| `POST /api/v1/mimi/report-abuse` | body MIMI abuse report body | `user_session` 或 `service_signature`;同 `cx.moderation.report` 互补。 | `{report_id, routed_to?}` |
| `POST /api/v1/mimi/proxy-download` | body `{blob_ref, target_provider_did}` | `service_signature`;MIMI 桥接 blob 时使用;不接受 user_session。 | `{relayed: true, expires_at?}` |

> **§2.3 表格作用域**: 上表是 v1 core 服务面**所有**已注册 HTTP operation 的 endpoint 契约清单(当前 registry 为 87 条 operation_id；一个 operation_id 对应多个 HTTP 别名时合并展示)。Admin / Auth / MIMI / Keys.keypackages / Directory.announce|withdraw 等子表面也都在表中;之前(2026-05-08 前)版本曾把它们留在独立章节,P-Aud(2026-05-18 审查)合并回 §2.3 以避免"读完 §2.3 仍找不到 operation"的发现问题(Gemini 2.1 / Claude C20)。OpenAPI 是 **HTTP/JSON binding** 的机器可消费最终来源；operation id、event kind、schema id 与 profile id 的全局 canonical source 仍是 `contract-catalog.json` / 对应 registry。本表是人类阅读视图。

跨域 actor 验证响应（通过 `/api/v1/identity/resolve` 与 holder-approved presentation challenge 获得）只能作为缓存加速或辅助诊断。接收方在接受事件、成员变更或设备绑定前，仍 MUST 独立验证 DID Document、key log、签名 transcript、capability 和 Realm policy；不得把对端"验证通过"当成最终授权依据。

### 2.4 字段级 Schema 索引

本节是 REST 端点的字段级 schema 索引。字段写法为 `name: type - 说明`。出现在“必填字段”列的字段为 required；出现在“可选字段”列的字段为 optional。位置若非 body，会显式标注为 `path.`、`query.` 或 `header.`。

规范性 operation contract 以 `artifacts/registry/contract-catalog.json#operation_registry` 为 canonical source；`artifacts/registry/operation-registry.json` 是其生成视图。本表、OpenAPI 与非 HTTP binding 均 MUST 从 canonical source 生成或通过 CI 校验；不得新增 catalog 中不存在的 `operation_id`，也不得在声明支持某 operation 时遗漏对应 catalog 条目。

| `operation_id` | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.server.describe` | 无 | `query.service_type: string - 过滤服务类型` | `ServiceDescribe` | `public_metadata`; 不得返回私有拓扑或 secret。`trust_domain` 与 `plaintext_visibility` 必填；缺失时 callers MUST fail closed。 |
| `cx.identity.describe_registry` | 无 | 无 | `ServiceDescribe` | `public_metadata`; 可限流；identity-specific 字段只能作为扩展字段追加。 |
| `cx.identity.resolve` | `did: did - 待解析 DID` | `include: string[] - 请求附加证据，如 key_log/receipts` | `did_document: object`; `key_log_head: id?`; `seq: int?`; `receipts: object[]?`; `method_evidence: object?` | private / pairwise DID 可要求 presentation proof。 |
| `cx.identity.get_document` | `query.did: did` | `query.version: string - 指定版本或 head` | `did_document: object`; `head_event_hash: string?`; `seq: int?`; `receipts: object[]?` | 可见性同 `cx.identity.resolve`。 |
| `cx.identity.get_log` | `query.did: did` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `has_more: boolean` | private / pairwise DID MUST 要求 holder-approved proof。 |
| `cx.identity.submit_did_operation` | `did: did`; `did_method: string`; `operation: object`; `proofs: proof[]` | `seq: int`; `prev_event_hash: string`; `policy_context: object` | `status: enum(accepted,duplicate,pending)`; `did: did`; `head_event_hash: string?`; `seq: int?`; `operation_ref: string?`; `receipts: object[]?` | MUST 满足 DID method / key-log 授权；`operation` 是 DID-method-specific 原始操作，统一 wrapper 不得把 DID 更新降格为通用 `patch`；幂等键由 DID method operation id / seq / canonical hash 决定。 |
| `cx.identity.get_receipts` | `query.did: did`; `query.head: string` | 无 | `receipts: object[]`; `threshold_met: boolean?` | 只公开最小 witness receipt。 |
| `cx.events.describe` | 无 | `query.actor_id: did`; `query.realm_id: id` | `ServiceDescribe` | public metadata 可公开；私有 frontier 需认证后作为扩展字段返回。 |
| `cx.events.submit` | 单事件提交 body 是 canonical `EventEnvelope` 对象（顶层 `event_id`/`actor_id`/`payload`/`proofs[]` ...）；批量提交 body 是 `{events: EventEnvelope[]}`。MUST NOT 使用 `{event: ...}` wrapper。 | `expected_frontier: object`; `idempotency_key: string` | `status: enum(accepted,duplicate,partial)`; `accepted: id[]`; `duplicate: id[]?`; `rejected: object[]?`; `actor_frontier: object?`; `realm_frontier: object?`; `cursor: cursor?` | MUST 验证 Event signature、DID、capability、Realm policy、`actor_seq`、`prev_refs` 和 `refs[role=authorized_by]`。`cursor` 是 barrier purpose（read-your-writes）。 |
| `cx.events.get` | `path.event_id: id` | `query.include_payload: boolean` | `event: object`; `visibility: object?`; `receipts: object[]?` | 不可见时返回 `not_found`。 |
| `cx.events.resolve` | 至少一个：`event_ids: id[]` 或 `event_hashes: string[]` | `include_payload: boolean` | `events: object[]`; `missing: id[]`; `unauthorized: id[]?` | payload 可见性按 Realm policy / E2EE envelope 判断。 |
| `cx.events.query` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.before: cursor`; `query.after: cursor`; `query.order: enum(default,ascending,descending)=default`; `query.limit: int`; `query.filters: object` | `events: object[]`; `next_cursor: cursor?`; `prev_cursor: cursor?`; `has_more: boolean` | `realms[]` 内部 union、`actors[]` 内部 union、二者组合为 intersection。每个 selector 元素都按对应可见性约束逐项检查：actor scope 走 actor history visibility；realm scope 走 membership frontier + history visibility + E2EE epoch policy。`before` / `after` 均为开区间（排除 cursor 自身），可单独或同时给出形成 `(after, before)` 区间。默认顺序：仅 `before` → descending，仅 `after` → ascending，两者皆给 → descending；`order=ascending|descending` 显式覆盖。响应 `prev_cursor` 永远朝更旧方向、`next_cursor` 永远朝更新方向。仅支持 `before` / `after` / `order` 参数。详见 §3.3。 |
| `cx.events.query_post` | body 至少一个：`realms: id[]` 或 `actors: did[]` | `before: cursor`; `after: cursor`; `order: enum(default,ascending,descending)=default`; `limit: int`; `filters: object` | 与 `cx.events.query` 同 | `cx.events.query` 的 HTTP POST/body 形态。语义、selector 规则、默认顺序、响应 cursor 含义、错误码与 GET 形态完全一致；仅 wire 形态从 query string 变为 JSON body。**何时使用**：`realms[]` / `actors[]` 较大、`filters` 较复杂、或部署侧记录 access log 时担心 query string 泄露 filter 内容。gRPC / MQ 不需要单独绑定（统一走 `Events/Query`）。 |
| `cx.events.subscribe` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.after: cursor`; `query.catchup: boolean=false` | stream frame: `kind: enum(event,frontier,heartbeat,catchup_complete,epoch_rotation,dropped,resync_required,unauthorized)`; `realm_id: id?`; `cursor: cursor?`; `payload: object?` | 同 `cx.events.query` 逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性。`after=<cursor>` 是订阅起点（不含 cursor 本身），与 `cx.events.query` 的 `after=` 同义；subscribe 天然只走未来方向，不接受 `before=` / `order=`。`catchup=true` 只表示从 `after=` 到当前 frontier 的追赶 replay，不表示全量历史；缺省或无 `after` 时只进入 live tail。某 realm 中途授权丢失 MUST 发出 `unauthorized` 帧并继续其他 realm；该帧 payload 至少包含 `reason_code`、`selector`、`retry_after_ms?`，不得包含不可见 Realm 标题、成员或 actor 集合。服务端因容量丢弃发出 `dropped` 帧，客户端必须 reconcile。 |
| `cx.events.frontier` | 至少一个：`query.actor_id: did` 或 `query.realm_id: id` | `query.peer_role: enum(account_client, federation_peer, anonymous_health) = account_client` | `frontier: object`; `receipts: object[]?`; `frontier_root: hash?`; `actor_seq_upper_bounds: object?`; `signature: object?`; `cache_until: datetime?`; `retry_after_ms: int?` | 统一 operation 同时承载 public Events API 与 federation peer frontier probe（federation.md §4.5.1）；`peer_role=federation_peer` MUST 通过 §3 节点间认证 + Realm service binding（`sync_endpoints` 或等价 policy facet）中的 `federation_peer` 角色校验，响应携带完整 `frontier_root` / `actor_seq_upper_bounds` / `signature`；`peer_role=anonymous_health` MUST 仅返回 `frontier_root` 摘要，并携带 `cache_until` 或 `retry_after_ms` 之一以约束轮询频率，服务端 MUST 对 `(realm_id, source_prefix)` 限速。普通 `account_client` 维持既有响应。不得泄露不可见 Realm 或 private DID。 |
| `cx.account.subscribe` | 无 | `query.after: cursor`; `query.catchup: boolean=false`; `query.filter: object`; `query.set_presence: enum(online,offline,unavailable)` | NDJSON 流,每行一个 `AccountSubscribeFrame`(`kind: delta / catchup_complete / frontier / heartbeat / dropped / resync_required / unauthorized`,`delta` 含 `cursor` + `realms?` + `to_device?` + `account_data?` + `device_lists?` + `presence?` + `notifications?`) | `user_session` 必须绑定 principal/device。聚合账号视角 delta streaming push;裸事件读用 `cx.events.query` / `cx.events.subscribe`。`cursor` 是 stream purpose。Initial sync 使用 `catchup=true` 且省略 `after`;baseline 不是完整历史。 |
| `cx.account.cursor_revoke` | `cursor: cursor` | `reason_code: string`; `revoke_scope: enum(this_cursor,same_device,same_session)=this_cursor` | `revoked: boolean`; `expires_at: datetime` | High-assurance optional profile；撤销 cursor authority，详见 [`client-sync.md` §12.2.1](./client-sync.md)。 |
| `cx.account.describe` | 无 | 无 | `ServiceDescribe` | 私有 frontier 可认证后作为扩展字段返回。 |
| `cx.ephemeral.send` | body `cx.schema.ephemeral_envelope.v1` | `proof: object`（按 kind 需要）；payload 内 kind-specific 字段 | `accepted: boolean`; `kind: string`; `realm_id: id`; `dispatched_to: int?`; `server_received_at: datetime?` | broadcast ephemeral channel；只承载 `cx.presence` / `cx.typing` / `cx.receipt.read` / `cx.call.signal`，并分别要求 `cx.presence.broadcast` / `cx.typing.broadcast` / `cx.receipt.broadcast` / `cx.call.signal.send`。MUST NOT 写入 durable Event history，MUST NOT 推进 actor_seq / Realm frontier。拒绝码包括 `ephemeral_kind_not_permitted`、`ephemeral_ttl_out_of_range`、`ephemeral_channel_unavailable`。 |
| `cx.snapshot.head` | `query.realm_id: id` | 无 | `snapshot_ref: id`; `state_hash: string`; `frontier: object`; `event_set_commitment: object`; `verification_hints: object?`; `signature: signature` | snapshot manifest MUST 签名；high-assurance profile MUST 支持 inclusion / omission challenge hints。 |
| `cx.projection.spaces` | `query.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `spaces: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | extension surface；返回 reducer 派生的 Space lifecycle read model，不是真相源；默认不得返回 tombstoned terminal rows。 |
| `cx.projection.flows` | `query.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `flows: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | extension surface；返回 reducer 派生的 Flow lifecycle read model，不是真相源；默认不得返回 redacted terminal rows。 |
| `cx.projection.morphs` | `query.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `morphs: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | extension surface；返回 reducer 派生的 Morph lifecycle read model，不是真相源；默认不得返回 redacted terminal rows。 |
| `cx.directory.describe` | 无 | 无 | `ServiceDescribe` | `public_metadata`; 可限流。Directory-specific 字段可作为扩展字段返回；详见 `../discovery/discovery-directory.md` §8.9。 |
| `cx.directory.search_realms` | 无 | `query: string`; `organization_did: did`; `parent_realm_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | hidden resource 不泄露存在性；每条 result MUST 含 `as_of`/`source_refs`/`policy_revision`/`stale?`/`divergent?`/`via_services?`（discovery-directory.md §9.1）。 |
| `cx.directory.resolve_realm` | 至少一个：`realm_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proofs: proof[]` | `space_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `via_services: did[]` | secret/restricted Realm 使用统一 `not_found`；`via_services` v1 normative，必须给出 host Principal Server service DID。 |
| `cx.directory.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 仅公开或授权可发现组织。 |
| `cx.directory.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | 解析组织不等于公开成员或拓扑。 |
| `cx.directory.search_actors` | 无 | `query: string`; `realm_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 不得泄露 pairwise/private DID。 |
| `cx.directory.search_users` | `body.q: string` | `body.realm_id: id`; `body.limit: int`; `body.intent: enum(mention,invite,member_add)` | `results: object[]` | mention autocomplete / 成员添加候选；受共同 Realm / directory policy 限制；请求词不得进入 URL、Referer 或未脱敏 access log。结果 MAY 包含 handle preview，但未授权时不得披露 `subject` DID 或 `recipient_service_did`。 |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string`; `intent: enum(lookup,mention,invite,member_add)`; `realm_id: id`; `requester: did`; `proofs: proof[]` | `did: did`; `subject: did`; `handle: string`; `handle_uri: uri`; `verified: boolean`; `claims: object[]?`; `recipient_service_did: did?`; `delivery_binding_hint: object?`; `source_refs: id[]?`; `expires_at: timestamp?` | 受限 / 组织 handle 需要 presentation；`recipient_service_did` 只能在 claim 已验证且请求方有权获得该上下文时返回。 |
| `cx.directory.private_contact_discovery` | `requester: did`; `contacts: object[]` | `proofs: proof[]`; `privacy_profile: string`; `padding: object` | `matches: object[]`; `proofs: object[]?`; `retry_after_ms: int?` | MUST 使用 blinded / padded identifier batch；不得返回原始 connection identifier、完整 profile、成员列表或关系图谱。 |
| `cx.directory.announce` | `resource_kind: enum(realm,organization,actor,applet,handle)`; `resource_id: id\|did\|handle`; `discovery_state: object`; `source_refs: id[]`; `as_of: timestamp`; `principal_server_did: did` | `ttl_seconds: int`; `supersedes_announce_id: id` | `announce_id: id`; `indexed_at: timestamp`; `effective_ttl_seconds: int`; `next_revalidation_after: timestamp`; `warnings: string[]?` | 资源 → Directory 的签名 ingest；MUST 验签 + 双向 opt-in；详见 `../discovery/discovery-directory.md` §8.3 / §8.5 / §8.10。 |
| `cx.directory.withdraw` | `resource_id: id\|did\|handle`; `governance_proof: object`; `reason: string` | `effective_at: timestamp` | `withdraw_id: id`; `acked_at: timestamp` | 资源主动撤销 opt-in；Directory MUST 在 ≤ 1h 内停止披露；详见 `../discovery/discovery-directory.md` §8.7。 |
| `cx.directory.subscribe` | `subscriber_did: did`; `resource_filter: object`; `webhook_endpoint: url` | `secret: string`; `expires_at: timestamp` | `subscription_id: id`; `effective_at: timestamp` | pull 模式优化；不替代 freshness 协议（§8.6）。 |
| `cx.blob.upload` | `size: int` | `realm_id: id`; `sha256: string`; `media_type: string`; `filename: string`; `purpose: string`; binary/multipart body; `header.Content-Type: string` | `blob_ref: string`; `size: int`; `media_type: string?`; `sha256: string`; `upload_receipt: object?` | upload capability、quota、media policy；`Content-Type` 缺省为 `application/octet-stream`。 |
| `cx.blob.head` | `query.blob_ref: string` | `header.Authorization: token` 或 `query.presign: token`（与 `Authorization` 互斥）；`header.X-Contrix-Wait-For: cursor` | headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?` | Header auth 路径必须验证 actor/device/Realm/purpose/expiry；presign 路径验证 envelope、TTL、scope、Realm/blob 状态和 issuer service DID，但不能验证当前请求者 audience。不得通过 header 泄露不可见资源。`presign` 形态见 `cx.blob.presign`。 |
| `cx.blob.get` | `query.blob_ref: string` | `header.Authorization: token` 或 `query.presign: token`（与 `Authorization` 互斥）；`header.Range: string`; `header.X-Contrix-Wait-For: cursor` | bytes；headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?`, `Content-Range?`, `Location?` | Header auth 路径必须验证 actor/device/Realm/purpose/expiry；presign 路径只接受 `cx.blob.presign` 发出的短 TTL 单对象 bearer token，验证 envelope、TTL、scope、Realm/blob 状态和 issuer service DID。Range 和 redirect 不得泄露不可见资源。两者同时出现 MUST 拒绝。详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `cx.blob.presign` | `blob_ref: string` | `max_age_seconds: int (<=3600)`; `purpose: enum(media_inline, thumbnail, download)` | `url: uri`; `expires_at: timestamp`; `purpose: string` | 为单个 blob 签发短 TTL（默认 ≤ 5 min，硬上限 ≤ 1h）、单对象、只读、可撤销的 pre-signed URL。**仅用于让浏览器 `<img src>` / `<video src>` 等无法附 Authorization header 的原生标签渲染受保护媒体**。E2EE 附件 ciphertext MUST NOT 通过此机制下发。受 `cx.blob.presign` capability 控制；TTL / scope / purpose 由 grant constraint 收紧。详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `cx.push.register_device` | `device_id: id`; `push_gateway: url`; `push_key: string` | `platform: string`; `app_id: string`; `display_name: string`; `recipient_service_did: did` | `ok: boolean`; `registration_id: id?`; `expires_at: datetime?` | 只能注册当前 principal/device，且 registration 作用域绑定当前 Principal Server service DID；如显式携带 `recipient_service_did`，MUST 等于目标服务 DID。 |
| `cx.push.unregister_device` | `device_id: id` | `push_key: string`; `app_id: string` | `ok: boolean` | same device/principal 或 device revocation path。 |
| `cx.push.notify` | `notification: object` | `notification.event_id: id`; `notification.realm_id: id`; `notification.sender: did`; `notification.push_hint: string`; `notification.counts: object`; `notification.devices: object[]` | `rejected: object[]` | 来自授权 Sync 或 notification service；E2EE 必须脱敏。 |
| `cx.device_messages.put` | `header.Idempotency-Key: string`; `messages: object` | 每个 target 必须含 `kind`、`content`、`expires_at` | `ok: boolean`; `delivered: object?`; `unknown_devices: object?` | `(sender, Idempotency-Key)` 幂等；目标必须是授权 device；过期或超过 TTL 上限的消息必须拒绝或逐项 reject。 |
| `cx.device_messages.get` | 无 | `query.from: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `limited: boolean?` | 只返回当前 device 队列。 |
| `cx.keys.upload` | `device_id: id`; `device_signature: signature` | `one_time_keys: object`; `fallback_keys: object` | `one_time_key_counts: object`; `fallback_keys: object?` | key 必须链接 self-signing / principal key。 |
| `cx.keys.query` | `device_keys: object` | `timeout_ms: int` | `device_keys: object`; `failures: object?` | 查询范围可按关系 / Realm 限制。 |
| `cx.keys.claim` | `one_time_keys: object` | 无 | `one_time_keys: object`; `failures: object?` | one-time key MUST 原子消费。 |
| `cx.keys.keypackages.upload` | `device_id: id`; `key_packages: object[]`; `device_signature: signature` | `expires_at: datetime`; `flow_id: id`; `mls_group_id: string` | `accepted: int`; `rejected: object[]?`; `key_package_refs: id[]?`; `available_count: int?` | MLS KeyPackage MUST 绑定 device key、credential 和 supported cipher suites；服务 SHOULD 返回该 device 当前可见 `available_count` 以支持低水位补充。 |
| `cx.keys.keypackages.claim` | `claims: object[]` | `timeout_ms: int`; `flow_id: id`; `mls_group_id: string` | `key_packages: object[]`; `failures: object?`; `available_count: int?` | KeyPackage claim MUST 原子保留，重复 claim 不得返回同一 one-time package；claimed 过期不得回到 published，claim path 按 `(requester_service_did, target_principal_id)` 限速并做反枚举。 |
| `cx.keys.keypackages.consume` | `key_package_refs: id[]`; `consumer_device_id: id`; `signature: signature` | `flow_id: id`; `epoch: int` | `consumed: id[]`; `failures: object?` | consume MUST 校验 claim holder、epoch 和 package freshness。 |
| `cx.keys.keypackages.revoke` | `key_package_refs: id[]`; `device_id: id`; `signature: signature` | `reason: string` | `revoked: id[]`; `failures: object?` | 只能由 owning device、principal 或授权 admin 撤销。 |
| `cx.keys.backups.put` | `path.backup_id: id`; `backup: object` | `idempotency_key: string` | `status: enum(accepted,duplicate)`; `backup_id: id`; `ciphertext_digest: string` | body MUST validate `cx.schema.key_backup.v1`；path/body backup id 必须一致；服务端不得解密。 |
| `cx.keys.backups.list` | 无 | `query.backup_class: enum(did_recovery,secret_storage,mls_history)`; `query.cursor: cursor`; `query.limit: int` | `backups: object[]`; `next_cursor: cursor?` | 仅返回调用方可见的最小 metadata；不得泄露无关 Realm / group membership。 |
| `cx.keys.backups.get` | `path.backup_id: id` | 无 | `backup: object` | 只返回同 principal 授权 device、recovery policy 或授权恢复服务可见的 encrypted backup object。 |
| `cx.keys.backups.delete` | `path.backup_id: id`; `proof: proof` | `reason: string` | `deleted: boolean` | 高风险删除；不等于 device revoke、DID recovery 或 MLS epoch rotation。 |
| `cx.authz.get_effective_grants` | `query.realm_id: id`; `query.subject: did` | `query.at: string` | `grants: object[]`; `state_hash: string?`; `evaluated_at: datetime` | subject 本人、Realm admin 或授权服务。 |
| `cx.authz.get_invites` | `query.subject: did 或 string` | `query.realm_id: id`; `query.cursor: cursor` | `invites: object[]`; `next_cursor: cursor?` | secret invite 不可枚举。 |
| `cx.authz.check` | `actor_id: did`; `action: string` | `resource: object`; `context: object` | `decision: enum(allow,deny,quarantine,require_review,soft_fail)`; `matched_grants: object[]?`; `applied_constraints: object[]?`; `policy_results: object[]?`; `missing_proofs: object[]?`; `frontier: object?`; `cache_valid_until: datetime?`; `reason_code: string?`; `obligations: object[]?` | Policy allow 不创建 capability；客户端不得把非标准 `allowed` 字段作为规范字段。 |
| `cx.policy.check` | `request_id: string`; `realm_id: id`; `request_canonical_hash: string`; `action: string`; `actor: did`; `source: object` | `device_id: id`; `event_preview: object`; `auth_context: object` | `request_id: string`; `bound_to: object`; `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `reason_code: string`; `expires_at: datetime`; `auth_state_hash: string`; `policy_frontier_hash: string`; `membership_frontier_hash: string`; `obligations: object[]?`; `signature: signature` | 只接收最小披露字段；decision 按 hash/cache frontier 绑定。Canonical HTTP 路径 `POST /api/v1/policy/check`。 |
| `cx.moderation.report` | `realm_id: id`; `target_ref: id`; `reason: enum`; `reporter: did` | `description: string`; `evidence_refs: id[]` | `report_id: id`; `status: string`; `routed_to: did[]?` | reporter 必须可见 target；只对 moderators 可见。 |
| `cx.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 不得泄露 private namespace。 |
| `cx.applet.describe` | 无 | 无 | `ServiceDescribe` | public mode 只返回公开 capabilities；applet-specific 字段作为扩展字段返回。 |
| `cx.applet.transaction` | `header.Idempotency-Key: string`; `source_service_did: did`; `events: EventEnvelope[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet 必须验证 event signature、namespace、capability；按 `(source_service_did, Idempotency-Key)` 幂等。 |
| `cx.applet.query_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 namespace。 |
| `cx.applet.query_realm` | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `cx.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | instance list 可要求授权。 |
| `cx.applet.third_party_users` | `query.protocol: string`; external ids | 无 | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 registration namespace 内。 |
| `cx.applet.third_party_locations` | `query.protocol: string`; external ids | 无 | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `cx.mimi.provider_directory` | 无 | `query.provider_id: string`; `query.features: string[]` | `providers: object[]`; `features: object`; `expires_at: datetime?` | 只返回公开 provider capability，不泄露 Realm membership。 |
| `cx.mimi.key_material` | `requester: did`; `flow_id: id`; `device_id: id` | `mls_group_id: string`; `epoch: int`; `proofs: proof[]` | `key_packages: object[]?`; `group_info: object?`; `failures: object?` | 必须存在 accepted `cx.mimi.room_binding` 且 requester 有对应 room / device 权限。 |
| `cx.mimi.room_update` | `path.flow_id: id`; `mls_group_id: string`; `update: object` | `epoch: int`; `transcript_hash: string`; `sender: did` | `accepted: boolean`; `room_state_ref: id?`; `rejected: object[]?` | 更新必须映射到 Contrix Flow discussion track / Realm policy 授权范围内。 |
| `cx.mimi.notify` | `path.flow_id: id`; `notification: object` | `origin_provider: string`; `routing: object` | `accepted: boolean`; `retry_after_ms: int?` | 只可传递最小 fanout / delivery signal，不得携带未授权明文。 |
| `cx.mimi.submit_message` | `path.flow_id: id`; `sender: did`; `device_id: id`; `ciphertext: object` | `mls_group_id: string`; `epoch: int`; `associated_data: object` | `event_ref: id?`; `delivery: object`; `rejected: object[]?` | 必须校验 MLS epoch、有效 discussion access、capability 和 `cx.mimi.room_binding`。 |
| `cx.mimi.group_info` | `path.flow_id: id` | `query.epoch: int`; `query.include_proof: boolean` | `group_info: object`; `room_binding_ref: id?`; `proofs: object[]?` | 只能返回 requester 授权可见的 MLS groupInfo / room projection。 |
| `cx.mimi.request_consent` | `requester: did`; `target: object`; `purpose: string` | `flow_id: id`; `expires_at: datetime`; `proofs: proof[]` | `consent_id: id`; `status: string`; `challenge: string?` | consent 只表达联系 / invite 意图，不授予 Realm read/write。 |
| `cx.mimi.update_consent` | `consent_id: id`; `decision: enum(accept,deny,revoke)`; `actor: did`; `signature: signature` | `reason: string`; `expires_at: datetime` | `status: string`; `updated_at: datetime`; `event_ref: id?` | 必须绑定原 request、target identity proof 和 replay protection。 |
| `cx.mimi.identifier_query` | `identifiers: object[]` | `requester: did`; `privacy_profile: string`; `proofs: proof[]` | `results: object[]`; `proofs: object[]?` | SHOULD 使用 private contact discovery；不得返回原始通讯录或完整关系图谱。 |
| `cx.mimi.report_abuse` | `flow_id: id`; `target_ref: id`; `reporter: did`; `reason: enum` | `evidence_package: object`; `frank: object`; `description: string` | `report_id: id`; `status: string`; `routed_to: did[]?` | E2EE report 只能向授权 moderation recipient 解密 evidence。 |
| `cx.mimi.proxy_download` | `asset_ref: string`; `requester: did` | `flow_id: id`; `ohttp_context: object`; `range: string` | `download_ref: string`; `headers: object?`; `expires_at: datetime?` | 当 Realm asset privacy policy 要求 proxy/OHTTP 时不得返回 direct object-store URL。 |
| `cx.account.issue_session_grant` | `principal_id: did`; `proof: SessionGrantRequestProof` | `device_id: id`; `requested_scope: string[]` | `principal_id: did`; `device_id: id?`; `session_grant: string`; `expires_at: datetime`; `granted_scope: string[]?` | `proof` MUST 绑定 `proof_kind`、`challenge`、`request_canonical_hash`、`audience`、`expires_at?` 与签名；必须绑定 principal、device key、audience 和最小 scope。 |
| `cx.account.device_pair` | `principal_did: did`; `new_device_key: object`; `pairing_proof: proof` | `display_name: string`; `device_metadata: object` | `device_id: id`; `device_grant: object`; `key_backup_hint: object?` | pairing code / proof 必须短期有效、一次性使用，并绑定目标 Auth Server audience / origin / request canonical hash；服务端 MUST 按 principal、授权源设备和目标 origin 限速。 |
| `cx.account.oidc_callback` | `state: string`; `code: string` | `nonce: string`; `redirect_uri: url` | `principal_id: did?`; `session: SessionGrantResponse?`; `redirect_url: url?` | MUST 校验 state、nonce、服务端配置的 issuer binding 和 DID/account linkage。 |
| `cx.admin.get_server_status` | 无 | `query.include: string[]` | `status: string`; `protocol_version: string`; `features: string[]`; `capacity: object?`; `warnings: string[]?` | 公开响应只能包含 operational metadata；敏感细节需要 admin session。 |
| `cx.admin.update_account_status` | `path.account_id: id`; `status: string`; `moderator: did`; `proof: proof` | `reason: string`; `expires_at: datetime`; `notify: boolean` | `account_id: id`; `status: string`; `event_ref: id?`; `updated_at: datetime` | 必须生成可审计 account lifecycle 状态或 admin receipt。 |
| `cx.admin.revoke_device` | `path.device_id: id`; `moderator: did`; `proof: proof` | `reason: string`; `revoke_sessions: boolean` | `device_id: id`; `revoked: boolean`; `event_ref: id?` | 必须撤销 device grant、session grant 和相关 key package。 |
| `cx.admin.get_moderation_queue` | 无 | `query.realm_id: id`; `query.status: string`; `query.cursor: cursor`; `query.limit: int` | `items: object[]`; `next_cursor: cursor?`; `counts: object?` | 只对授权 moderator / compliance service 可见，证据按 policy 最小披露。 |
| `cx.media.ice_config` | `realm_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `mode: string` | 无 | `ttl_seconds: int`; `ice_servers: object[]`; `policy: object`; `signature: signature` | actor 必须有 call/media capability；Media Service 必须被委托。 |

## 3. Events API

### 3.1 提交 Event

```text
POST /api/v1/events
```

单事件提交 request body 直接是 canonical `EventEnvelope` 对象（**不**用任何 `{event: ...}` wrapper）。批量提交 request body 是 `{events: EventEnvelope[]}`。

单事件请求示例（非完整 schema）：

```json
{
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 42,
  "kind": "cx.flow.update",
  "created_at": "2026-04-22T08:30:00Z",
  "hlc": "01970e589d21-0007-a13f9c2e",
  "prev_refs": [
    "cx:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "cx:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "payload": {
    "flow_id": "cx:flow:019640c6-8000-7000-8000-000000000000",
    "patch": { "fields.status": "done" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#device-1",
      "payload_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "created_at": "2026-04-22T08:30:00Z",
      "jws": "..."
    }
  ]
}
```

批量请求示例（非完整 schema）：

```json
{
  "events": [
    { "event_id": "cx:event:...", "realm_id": "cx:realm:...", "actor_id": "did:web:...", "actor_seq": 42, "kind": "cx.flow.update", "...": "..." },
    { "event_id": "cx:event:...", "realm_id": "cx:realm:...", "actor_id": "did:web:...", "actor_seq": 43, "kind": "cx.message.create", "...": "..." }
  ]
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
  "cursor": "cx:cursor:<opaque-valid-barrier-cursor>"
}
```

若 `expected_frontier` 校验失败，返回 `409 cas_conflict`。协议级写入单元是 signed Event Envelope；实现 MAY 在 SDK 或本地接口中接受 operation builder，但在进入网络传播、同步或审计前 MUST 转换为 Event Envelope。接收方不得要求 Event 先归属某个 batch receipt、checkpoint 或 predecessor commit 才承认其 canonical history 地位。

`events[]` 批量提交按数组顺序处理。已接受的前序项可以被同批后续项的 `prev_refs`、`refs[role=authorized_by]` 或显式 payload reference 解析；后续项不得引用同批中尚未处理、已拒绝或隔离的 Event 作为已接受事实。单项失败不回滚整批，响应必须把成功项列入 `accepted[]`，幂等重复列入 `duplicate[]`，失败项列入 `rejected[]` 或等价隔离结果。

### 3.2 批量获取 Event

```text
POST /api/v1/events/resolve
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
GET /api/v1/events?realms=<id>&before=<cursor>&limit=500          # 历史 backfill（最近未历史）
GET /api/v1/events?actors=<did>&after=<cursor>&limit=500           # 从已知 frontier 追上（catch-up）
GET /api/v1/events?realms=<id>&actors=<did>&after=<Y>&before=<X>   # 区间查询（Y, X）开区间
```

#### 3.3.1 Selector

`realms` / `actors` 都是数组（`realms=A&realms=B`）；同一参数的多个值之间是 union，跨参数（realms × actors）是 intersection。

#### 3.3.2 边界参数 `before` / `after`（v1 wire 形态）

| 参数 | 类型 | 必填 | 语义 |
| --- | --- | --- | --- |
| `before` | `cursor` | optional | 返回此 cursor *之前*（**不含**该 cursor 指向的位置）的最近一批 Event。"之前" = 比此 cursor 更旧的事件方向。 |
| `after` | `cursor` | optional | 返回此 cursor *之后*（**不含**）的最近一批 Event。"之后" = 比此 cursor 更新的事件方向。 |
| `order` | `enum(default, ascending, descending)` | optional | 默认 `default` 按下方"近邻先返回"规则；`ascending` / `descending` 显式强制顺序。 |
| `limit` | `int` | optional | 服务端 enforce 上限（见 [`scalability-constraints.md`](../conformance/scalability-constraints.md)）。 |

规则：

- `before` 与 `after` 都是 **排除** 语义 — Contrix cursor 是位置 token 而不是 event 引用，"位置之前/之后"不包含 cursor 标记的边界本身。这与 Stripe `starting_after`/`ending_before`、Relay GraphQL `after`/`before` 等业界惯例一致。
- 两参数都可省略；都不给时服务端按隐式 `before=<server_head>` 处理（即"最新首屏 + 可继续历史 backfill"）。
- 两参数都给即为开区间 `(after, before)` 查询。
- v1 wire 只接受 `before` / `after` / `order`；任何其他游标方向参数 MUST 返回 `invalid_param`。

#### 3.3.3 默认顺序规则："近邻先返回"

`order=default` 时，批次内事件按**距离 anchor cursor 的远近**排序，离 anchor 最近的事件排第一位：

| 给定参数 | 默认 `order` | 物理意义 |
| --- | --- | --- |
| 仅 `before=X` | **descending**（newest first） | 离 X 最近的 = 比 X 略旧的事件，即"X 之前最近发生的事"。UI 友好。 |
| 仅 `after=Y` | **ascending**（oldest first） | 离 Y 最近的 = 比 Y 略新的事件，即"Y 之后最早发生的事"。reducer / catch-up 友好。 |
| 都给（区间） | **descending** | 区间内 UI-导向默认；想按 causal 顺序应用时显式 `order=ascending`。 |
| 都不给 | **descending** | 等价于 `before=<server_head>`，最新事件首屏。 |

`order=ascending` / `order=descending` 显式覆盖上述默认；批次内的事件顺序在所有情况下都按 `(causal_depth, hlc, actor_id, actor_seq, event_id)` 的字典序解决 ties，详见 [`operations-sync.md` §16](./operations-sync.md)。

#### 3.3.4 响应

```json
{
  "events": [],
  "prev_cursor": "opaque",
  "next_cursor": "opaque",
  "has_more": true
}
```

响应 cursor 含义在 v1 中是**绝对**的，与请求是 `before` 还是 `after`、`order` 取何值无关：

| 响应字段 | 含义 | 下一次调用 |
| --- | --- | --- |
| `prev_cursor` | 朝**更旧事件**方向的延续位置（位于本批次较旧端之外） | 传给下次请求的 `before=` 取更旧一批 |
| `next_cursor` | 朝**更新事件**方向的延续位置（位于本批次较新端之外） | 传给下次请求的 `after=` 取更新一批 |
| `has_more` | 等价于 `has_more_before`：是否在 `prev_cursor` 指向的**更旧事件**方向上仍有可拉取 Event。客户端到达 oldest accessible event 时 `has_more=false`。`has_more` 不反映 `next_cursor` 方向是否有事件——`next_cursor` 永远有效（朝未来推进），但其指向的事件可能尚未发生。 |  |

边界场景：

- **客户端已经追到最新 head**（`after=` 调用暂时无新事件）：响应 `events=[]`、`prev_cursor` 仍可指向当前可见 head 之前的位置（可继续 `before=prev_cursor` 翻历史）、`next_cursor` 指向未来推进点、`has_more=true` 当更旧方向仍有可读历史时。
- **客户端到达 oldest accessible event**（不允许再往更旧拉）：`prev_cursor=null`、`has_more=false`。
- **超过 visibility 边界**：返回 `not_found` 而不是空批次，避免泄露不可见 Realm 的存在性。

#### 3.3.5 POST/body 形态（`cx.events.query_post`）

```text
POST /api/v1/events/query
Content-Type: application/json

{
  "realms": ["cx:realm:..."],
  "actors": ["did:webvh:..."],
  "before": "cx:cursor:...",
  "after": "cx:cursor:...",
  "order": "default",
  "limit": 200,
  "filters": { "kind": ["cx.message.create"] }
}
```

POST 形态与 GET 形态**完全等价**：参数集（`realms` / `actors` / `before` / `after` / `order` / `limit` / `filters`）、默认顺序规则（§3.3.3）、响应 cursor 绝对方向（§3.3.4）一律相同；只是 wire 形态从 query string 变为 JSON body。

**何时使用 POST**：
- URL 长度风险：`realms[]` 或 `actors[]` 列表较大、`filters` 是嵌套 object 时，URL 容易超过代理 / CDN / 负载均衡器的实际上限（常见 4–8 KiB）
- 隐私 / 日志风险：部署侧的 HTTP access log 通常会完整记录 URL；query string 中的 filter 字段（含可能的敏感 keyword、`actor_id` 列表）会被无差别采集
- 兼容受限客户端：某些 HTTP 中间层会规范化或丢失复杂的 `style: deepObject` 参数

`cx.events.query_post` 是 **HTTP-专属** operation id；gRPC 与 MQ 的 wire 形态本就是 body-based，统一使用 `cx.events.query` / `Events/Query` / `events.query` 即可，不需要单独的 `_post` 命名。

**选择规则**：
- 简单查询（仅 `before` / `after` / `limit`，少量 realms/actors）→ `GET /events`，cacheable、可被代理优化
- 复杂查询（大型 selector / 复杂 filters）→ `POST /events/query`

服务端 SHOULD 同时实现两个 endpoint；客户端可以按场景自由选择，**不需要协商**。`cx.events.query_post` 写入注册表（`operation-registry.json`）以保证 SDK 生成器、conformance 测试与 server.describe 能机器可读地枚举该 alternate binding。

### 3.4 流式订阅 Event（`cx.events.subscribe`）

```text
GET /api/v1/events/subscribe?realms=<id>&after=<cursor>&catchup=true
```

`after=<cursor>` 表示订阅起点：从该 cursor *之后*（排除）开始接收事件，与 [`cx.events.query`](#33-查询--回填-eventcxeventsquery) 的 `after=` 同义。Subscribe 天然只有"朝未来推进"一个方向，不接受 `before=` / `order=`；想要历史回填请用 `cx.events.query`。

支持多 realm / actor 一次订阅；`catchup=true` 时服务端只回放 `after=` 到当前 frontier 的追赶区间，再发出 `catchup_complete` 帧切到实时尾部。完整历史必须通过 `GET /events` 的 `before` / `after` 分页或区间查询读取。


HTTP 200 response `Content-Type` MUST be `application/x-ndjson`。Frame 每行一个独立 JSON 对象：

```text
{ "kind": "event", "realm_id": "cx:realm:01...", "cursor": "opaque", "payload": {} }
{ "kind": "catchup_complete", "realm_id": "cx:realm:01...", "cursor": "opaque" }
{ "kind": "frontier", "realm_id": "cx:realm:01...", "cursor": "opaque" }
{ "kind": "heartbeat" }
{ "kind": "epoch_rotation", "realm_id": "cx:realm:01...", "payload": {"new_epoch": 17} }
{ "kind": "dropped", "realm_id": "cx:realm:01...", "cursor": "opaque" }
{ "kind": "unauthorized", "realm_id": "cx:realm:01..." }
{ "kind": "resync_required", "realm_id": "cx:realm:01..." }
```

客户端必须把 `dropped` 与 `resync_required` 当作硬信号——前者要求按 cursor 重新 `cx.events.query` 补齐，后者要求重建本地状态。`kind="dropped"` frame 的 `cursor` 为 REQUIRED；服务端没有可用补齐 cursor 时 MUST 发送 `resync_required`，不得发送无 cursor 的 `dropped`。

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
  "key_log_head": "cx:keyevt:019642b0-0000-7000-8000-000000000005",
  "seq": 5
}
```

Resolver MUST 返回足够的方法相关证据，使客户端能够验证 control history。

## 5. Account API

`/account/*` 在 v1 只承载 **account 聚合 streaming**（跨 Realm frontier、to_device、account_data、device_lists、presence、unread / notification counts）；snapshot manifest 入口独立放在 `/snapshot/*`。逐 Realm 的事件读取与流式订阅走 `/events/*`（`cx.events.query`、`cx.events.subscribe`），见 §3.3 / §3.4。

### 5.1 账号聚合订阅（`cx.account.subscribe`）

```text
GET /api/v1/account/subscribe?catchup=true                         # initial account sync baseline
GET /api/v1/account/subscribe?after=<cursor>                        # live tail after external reconciliation
GET /api/v1/account/subscribe?after=<cursor>&catchup=true           # reconnect / dropped catch-up
```

该端点对应 `cx.account.subscribe`,wire 形态是长连接 NDJSON 流。客户端建立长连接后,服务端按 account / Realm filter 推送 `delta` frame(跨 Realm delta + to_device + account_data + device_lists + presence + notifications)与控制 frame(`catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`)。请求参数、frame schema 与重连规则见 [`client-sync.md`](./client-sync.md) §2。

它与 `cx.events.subscribe` 是对称的两类 streaming 订阅(account-aggregate vs per-Realm event log),共享 cursor / `dropped` / `resync_required` 控制模型,但恢复面不同:`account.subscribe` 的 `dropped` 用 `GET /account/subscribe?after=<cursor>&catchup=true` 重放账号聚合 delta;裸 Event 缺口才使用 `cx.events.query`。`catchup=true` 不表示全量历史;完整历史读取必须走 `cx.events.query`。它不是裸事件读取——裸事件读取请使用 `cx.events.query` / `cx.events.subscribe`。

## 6. Snapshot API

`/snapshot/*` 提供 Realm snapshot manifest 入口；snapshot 是派生的当前态缓存,客户端使用前 MUST 校验签名、签名者授权、`state_hash` 和每个 chunk digest（见 [`service-surface.md` §11](./service-surface.md)）。

### 6.1 当前 snapshot manifest（`cx.snapshot.head`）

```text
GET /api/v1/snapshot/head?realm_id=<id>
```

该端点对应 `cx.snapshot.head`，返回当前推荐 snapshot manifest 指针（不含 chunk bytes）。客户端通过 manifest 中的 `chunks[].chunk_ref` 走 blob surface 取实际数据。snapshot 不是真相源,校验失败时客户端 MUST 回退到 Event history replay。

## 7. Directory API

```text
POST /api/v1/directory/search-realms
POST /api/v1/directory/resolve-realm
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/search-users
POST /api/v1/directory/resolve-handle
```

Directory 端点 MUST 在每个结果上分别应用资源可发现性、请求方证明、审核策略与授权过滤。

对于隐藏或未授权访问的资源，`resolve-*` SHOULD 返回与"不存在"不可区分的 `not_found`。

## 8. Blob API

### 8.1 上传

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

### 8.2 下载

```text
HEAD /api/v1/blob/get?blob_ref=<blob_ref>
GET /api/v1/blob/get?blob_ref=<blob_ref>
```

客户端 MUST 重新计算内容哈希并与 `blob_ref` 比对。
若哈希不匹配，客户端 MUST 拒绝响应并丢弃内容；服务端在上传、代理或镜像校验时发现不匹配 MUST 返回 `422 digest_mismatch`。

## 9. 标准错误响应

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

## 10. 标准错误码

标准错误码、HTTP 状态码与逐项 reason_code 的 **canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。本节不再在 Markdown 中维护并行表格；任何新增 / 修改 / 删除错误码 MUST 先更新 registry。

`api-conventions.md` §5.1 是该 registry 的解释性 narrative 视图（解释每个 code 的使用场景）；它本身也以 registry 为准，发现差异时以 registry 为准。

实现使用规则：

- 客户端收到 `429` MUST 优先遵守 `Retry-After` header；若缺失再使用 body 中的 `retry_after_ms`。`503` 在带有 `Retry-After` 时也必须按该时间退避。收到 `409` SHOULD 拉取最新状态后退避重试。
- `unsupported_feature` 用于 `Event.requirements.features[]` / `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `cx.*` Event kind；二者不得互相替代。
- 通用 `conflict` 仅作为抽象 base code 出现在 narrative；实现 SHOULD 返回 registry 中更精确的 409 子 code（`cas_conflict` / `causal_conflict` / `dependency_missing` / `duplicate_conflict` / `epoch_mismatch` / `rank_exhausted` / `stale_frontier` / `state_mismatch` / `discussion_track_disabled` / `key_unavailable`）。

## 11. 安全与抗滥用

服务端 SHOULD 在高风险入口实施一致性失败语义：

- 对目录/resolve 查询、join 探测、公开元数据接口，未授权请求不应返回可区分 `not_found` 与 `forbidden` 的信息差异。
- 联邦入口与 policy check 入口应记录来源 service DID + 来源域名哈希，结合 `rate_limited` 与 `temporarily_unavailable` 作回压。
- 对来源签名缺失/验证失败的入口请求，应优先走 reject + audit，不得影响已认证正常来源的可用性。
- 对 URL 中携带认证材料的请求，应 reject + redact log，不得进入正常认证 fallback。
