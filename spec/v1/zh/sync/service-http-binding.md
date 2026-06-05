---
title: Service HTTP/JSON Binding
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Cokret 默认 HTTP/JSON binding 的路径、请求形状和错误响应。

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

Cokret 的 HTTP/JSON binding 按 **服务角色与 canonical operation** 组织，而不是按某个产品形态拆成固定的 Client API / Server API / Push API 包。客户端、Principal Server、Events API、Directory、Applet、Push Gateway 等都可以暴露自己的服务面；服务发现决定某个节点实际支持哪些命名空间。

所有 path 都在 negative-space 根 `/_cokret/` 之下，且**不含版本段**。`/_cokret/` 之后的第一段是 **trust-surface classifier（信任面分类器）**：它编码"调用方↔服务"的信任关系和攻击面类别。本文保留"信任同心圆"作为解释隐喻，但正式规则是"第一段 = 信任面分类"，不是授权结论。

| 信任面段 | 信任关系 | 承接命名空间 |
| --- | --- | --- |
| `self` | 本人已认证会话 | events·account·rtc·blob·keys·authz·policy·projection·agents·device_messages·moderation·snapshot·ephemeral·applets |
| `gate` | 认证入口 | account（auth / session-grant） |
| `root` | 身份信任根：DID / key log / receipt；不是 Unix/root 管理员权限 | identity |
| `find` | 目录发现 | directory |
| `peer` | 对等 Cokret 服务器 | federation server↔server wire（保留命名分支，见 `federation.md`；不承接 client/service operation 集合） |
| `open` | 外部协议互通面；表示 non-Cokret protocol interop，不表示 public / no-auth access | mimi |
| `edge` | 推送 / 桥接网关 | push·applet |

读 URL 即读攻击面：`/_cokret/self/...` 是调用方本人的会话面，`/_cokret/open/...` 一眼就是在跟外部协议或外部 provider 打交道。但信任面段本身 **MUST NOT** 被实现解释为授权通过、安全级别达标或明文可见许可。每个 operation 仍必须按自身契约执行 session、capability、DID proof、Realm policy、history visibility、service delegation、rate limit 和最小披露校验；路径段只帮助路由、审计、中间件和读者快速识别攻击面。pre-auth 的根级能力广告位于根 meta 位 `GET /_cokret/describe`（`ck.server.describe`）；其余 `*.describe` 各自跟随所在段。版本不进 path，由 `*.describe` / `supported_operations` 协商（可选 `Cokret-Protocol-Version` header）。versionless + 协议内协商如何支撑新旧实现互通，见 [overview/evolution-and-compatibility.md](../overview/evolution-and-compatibility.md) §6。

默认 REST 命名空间如下：

| 命名空间 | 主要调用方 | 语义 | 规范文件 |
| --- | --- | --- | --- |
| `/_cokret/describe` | 客户端与服务 | 根级服务描述、feature discovery、auth metadata（pre-auth）。 | `service-surface.md`、`api-conventions.md` |
| `/_cokret/gate/account/*` | 客户端、Principal Server | 账户认证入口：注册 / account binding、session-grant 签发与撤销、设备配对、OIDC 回调、agent key pairing。 | `service-surface.md`、`api-conventions.md` |
| `/_cokret/root/identity/*` | 客户端、服务、registry | 身份信任根：DID 文档、key log、DID operation、receipt；`root` 不是管理员权限面。 | `service-surface.md`、`identity-did.md` |
| `/_cokret/self/events/*` | 客户端、Principal Server、授权 Event 副本 | signed Event 提交、按 ID 读取、批量读取、actor/Realm 双向历史查询(query)、流式订阅(subscribe，含 bounded catch-up replay)、frontier 查询。 | `operations-sync.md`、`service-surface.md` |
| `/_cokret/self/account/*` | 客户端、Principal Server | account viewer 自读、profile 更新、account 聚合 streaming 订阅(`GET /_cokret/self/account/subscribe`)、describe 与 cursor revoke。逐 Realm 的事件流读取走 `/_cokret/self/events/*`。 | `client-sync.md`、`service-surface.md`、`profiles-presence.md` |
| `/_cokret/self/snapshot/*` | 客户端、Principal Server | Realm snapshot manifest 入口(`GET /_cokret/self/snapshot/head`)。 | `client-sync.md`、`service-surface.md` |
| `/_cokret/self/projection/*` | 客户端、Principal Server | 派生 lifecycle projection 读取：Space / Flow / Morph 当前状态列表。 | `realm-and-space.md`、`flow-and-message.md`、`morph.md` |
| `/_cokret/self/applets/*` | 客户端、Realm admin | self/admin 信任面的 Applet 安装聚合操作：install 预览、install、revoke（`ck.applet.install.preview` / `ck.applet.install` / `ck.applet.revoke`）。Applet 运行时桥接面在 `/_cokret/edge/applet/*`。 | `applet-integration.md` |
| `/_cokret/find/directory/*` | 客户端、服务 | Realm / Organization / Actor / handle 的授权发现与解析。 | `discovery-directory.md` |
| `/_cokret/self/blob/*` | 客户端、服务 | Blob 上传、HEAD、authenticated download。 | `media-and-blob.md` |
| `/_cokret/edge/push/*` | 客户端、Sync、Push Gateway | 推送设备注册、注销、脱敏唤醒投递。 | `push-notifications.md` |
| `/_cokret/self/device_messages/*`、`/_cokret/self/keys/*` | E2EE 客户端、Principal Server | to-device、one-time key、fallback key、device list 相关操作。 | `device-lifecycle.md` |
| `/_cokret/self/authz/*`、`/_cokret/self/policy/check` | 客户端、Events API、Sync、Policy Server | capability 预检查、policy server 签名决策。Canonical path 是 `/_cokret/self/policy/check`(`ck.policy.check`)。 | `capabilities.md`、`policy-server.md` |
| `/_cokret/self/rtc/ice-config` | 通话客户端、Realtime Media Server | TURN/STUN/ICE 短期凭证。 | `webrtc-signaling.md` |
| `/_cokret/self/moderation/*` | 客户端、审核服务 | 举报、审核队列或扩展审核入口。 | `governance/content-moderation.md` |
| `/_cokret/edge/applet/*` | Cokret 服务调用 Applet | applet ping / describe、transaction push、Ghost Actor / portal 查询。 | `applet-integration.md` |
| `/_cokret/open/mimi/*` | Cokret 服务、MIMI provider facade | 外部协议互通；`open` 表示 interop surface，不表示公开免认证访问。 | `mimi-interop.md` |

客户端视角的常用 API 集合通常包括 `/_cokret/describe`、`/_cokret/root/identity/*`、`/_cokret/self/events/*`、`/_cokret/self/account/*`、`/_cokret/self/snapshot/*`、`/_cokret/self/projection/*`、`/_cokret/find/directory/*`、`/_cokret/self/blob/*`、`/_cokret/edge/push/*`、`/_cokret/self/device_messages/*`、`/_cokret/self/keys/*`、`/_cokret/self/authz/*`。服务间 API 集合通常包括 `/_cokret/self/events/*`、`/_cokret/self/account/*`、`/_cokret/self/authz/*`、`/_cokret/self/policy/check`、`/_cokret/edge/applet/*` 和 `/_cokret/edge/push/notify`。搜索、inbox、notification 和 View projection 默认是客户端本地派生；`/_cokret/self/projection/*` 只暴露 Space / Flow / Morph lifecycle 派生读模型，且属于 extension surface，必须由服务显式声明支持。

路径风格约束：新增 HTTP path SHOULD 使用 kebab-case 资源名和清晰的资源/动作边界。现有 `/_cokret/self/device_messages`、`/_cokret/self/blob/get`、`/_cokret/self/agent-sidecar-threads:ensure` 是已注册 v1 binding 的兼容性例外；它们不构成新路径的命名模板。新增例外必须先进入 canonical operation catalog，并在本文件说明为什么不能使用常规资源路径。

新增顶层 REST 命名空间前，规范必须同步更新 `contract-catalog.json#operation_registry`、OpenAPI path、必要的 request/response schema refs、feature discovery 返回值和对应 conformance profile；`artifacts/reports/operation-schema-index.json` 由 pipeline 生成并用于复核 DTO 字段集合。实现不得用未声明路径绕过 canonical operation、capability、幂等、分页或错误语义。

### 2.2 端点契约规则

每个 REST endpoint 的规范定义必须至少包含：

- `operation_id` / canonical operation。
- Path 参数、query 参数和 request body 字段类型。
- 成功响应字段类型。
- 认证方式：`public_metadata`、`user_session`、`device_proof`、`service_signature`、`policy_token`、`applet_signature` 等。
- 访问限制：Realm membership、history visibility、capability、service delegation、namespace、plaintext visibility、rate limit、quota。
- 幂等键：写接口使用 `Idempotency-Key` header、`event_id`、`request_id` 或 canonical request hash。
- 失败时使用标准 error envelope。

JSON 示例只用于说明，不构成完整 schema。正式接口定义 MUST 以 `contract-catalog.json#operation_registry`、OpenAPI binding 和被 `request_schema_ref` / `response_schema_ref` 指向的 JSON Schema 为准；字段表只提供人类阅读索引，字段集合快照由 [`operation-schema-index.json`](../../artifacts/reports/operation-schema-index.json) 生成。

默认规则：

- 除明确标记为 `public_metadata` 的 describe / discovery 外，所有 endpoint MUST 认证。
- 认证只证明调用方身份；服务仍 MUST 执行 capability、Realm policy、history visibility、service delegation 和 revocation 检查。
- 服务间调用 MUST 使用 HTTP Message Signature 或等价 service DID proof，并绑定 method、target URI、content digest、origin service DID 和 destination service DID；shared ingress / 多租户 / allowlist endpoint 场景还 MUST 绑定 destination service endpoint digest。
- 服务间调用的 `origin` / `destination` 必须是 service DID，且必须与 DID Document service endpoint、目标 URL、Realm policy / service delegation 和签名 transcript 一致。
- 受保护 endpoint 不得接受 query string 中的 token、API key 或签名材料；临时下载 URL 只能使用短时效、单用途、可撤销的派生 token。
- 返回 `not_found` 的 endpoint MUST 对“不存在”和“存在但不可见”保持一致失败语义，除非调用方已有管理权限。
- 所有批量读取 MUST 支持 `limit` 上限，分页 cursor 必须是不透明 token。
- 路由层 MUST 对 `/_cokret/*` 下的未知路径返回 `404 unrecognized_endpoint`，对已知路径的错误 method 返回 `405 method_not_allowed`，且不得进入业务逻辑。

### 2.3 端点契约清单

类型简写：`did` 为 DID URI，`id` 为协议对象 ID，`cursor` / `token` 为 opaque string，`signature` 为 `{kid, alg?, sig}`，`proof` 为 DID / HTTP message / detached JWS proof。`events` 为 Event Envelope 数组。

| Endpoint | Request 类型 | Auth / 访问限制 | Success 类型 |
| --- | --- | --- | --- |
| `GET /_cokret/describe` | query: none 或 `service_type?` | `public_metadata`；不得返回私有 topology、secret 或未授权 internal endpoint。 | `ServiceDescribe`（`ck.schema.service_describe.v1`；必须含 `service_did`、`trust_domain`、claim-level 字段、`plaintext_visibility`、`development_mode`，且 `development_mode=true` 时 `verified_profiles=[]`） |
| `GET /_cokret/root/identity/describe` | query: none | `public_metadata`；可限流。 | `ServiceDescribe`；identity-specific 能力通过 `supported_features` / `limits` / 扩展字段表达。 |
| `POST /_cokret/root/identity/resolve` | body `{did: did, include?: string[]}` | `public_metadata`；private DID MAY require `user_session` 或 presentation proof。 | `{did_document, key_log_head?, seq?, receipts?, method_evidence?}` |
| `GET /_cokret/root/identity/document` | query `{did: did, version?: string}` | 同 `identity.resolve`。 | `{did_document, head_event_digest?, seq?, receipts?}` |
| `GET /_cokret/root/identity/log` | query `{did: did, cursor?: cursor, limit?: int}` | public DID 可公开；private / pairwise DID MUST require holder-approved proof。 | `{events[], next_cursor?, has_more}` |
| `POST /_cokret/root/identity/submit-did-operation` | body `{did: did, did_method: string, seq?: int, prev_event_digest?: string, operation: object, proofs: proof[], policy_context?: object}` | `device_proof` 或 recovery proof；MUST 满足 DID method / key-log 授权；`operation` 是 DID-method-specific 原始操作，不是通用 JSON Patch。 | `{status, did, seq?, head_event_digest?, operation_ref?, receipts?}` |
| `GET /_cokret/root/identity/receipts` | query `{did: did, head: string}` | 同 DID 可见性；witness 可公开最小 receipt。 | `{receipts[], threshold_met?: boolean}` |
| `GET /_cokret/self/events/describe` | query none 或 `{actor_id?: did, realm_id?: id}` | `public_metadata` 或 `user_session`；私有 frontier 需认证。 | `ServiceDescribe`；event schema / reducer / signature 能力通过 `supported_features`、`supported_profiles`、`limits` 或扩展字段表达。 |
| `POST /_cokret/self/events` | body 是 `EventSubmitEnvelope`（单事件）或 `{events: EventSubmitEnvelope[]}`（批量）；submit 输入 MUST NOT 携带 reducer-managed accepted-output 字段（如 `actor_kind` / `effective_scope`）。MUST NOT 使用 `{event: ...}` wrapper。 | `user_session` / `device_proof` / `service_signature`；MUST 验证 actor DID、签名、capability、Realm policy、`actor_seq`、`prev_refs`、`refs[role=authorized_by]`。 | `{status, accepted[], duplicate[]?, rejected[]?, actor_frontier?, realm_frontier?, cursor?}` |
| `GET /_cokret/self/events/{event_id}` | path `{event_id: id}` query `{include_payload?: boolean}` | Event 可见性按 Realm policy / history visibility / E2EE envelope 判断；不可见时返回 `not_found`。 | `{event, visibility?, receipts?}` |
| `POST /_cokret/self/events/resolve` | body `{event_ids?: id[], event_digests?: string[], include_payload?: boolean}` | 同 Event read；payload 可见性按 Realm policy / E2EE envelope 判断。 | `{events[], missing[], unauthorized[]?}` |
| `GET /_cokret/self/events` | query `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object}` | 调用方必须对每个 selector 元素满足读取约束：actor scope 走 actor history visibility；realm scope 走 membership frontier + history visibility + E2EE epoch policy。`realms[]` ∪ 内部、`actors[]` ∪ 内部、二者组合为交集。批次内顺序规则见 §3.3。 | `{events[], next_cursor?, prev_cursor?, has_more}` |
| `POST /_cokret/self/events/query` | body `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object}` | 同 `GET /_cokret/self/events`（`ck.events.query` 的 HTTP POST/body binding variant，registry `binding_variant_of="ck.events.query"`）。 | `{events[], next_cursor?, prev_cursor?, has_more}`；语义与 GET 形态完全一致，仅 wire 形态从 query string 变为 JSON body。 |
| `GET /_cokret/self/events/subscribe` | query `{realms?: id[], actors?: did[], after?: cursor, catchup?: boolean}` | 同 `GET /_cokret/self/events` 的逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性边界。授权丢失通过 per-realm `unauthorized` 帧通知，不中断整条流。 | event stream frames `{kind: event\|frontier\|heartbeat\|catchup_complete\|epoch_rotation\|dropped\|resync_required\|unauthorized, realm_id?: id, cursor?: cursor, payload?: object, reconnect_after_ms?: int}` |
| `GET /_cokret/self/events/frontier` | query `{actor_id?: did, realm_id?: id}` | 返回调用方可见范围内 frontier；不得泄露不可见 Realm 或 private DID。 | `{frontier, receipts?}` |
| `POST /_cokret/self/ephemeral` | body `ck.schema.ephemeral_envelope.v1` (`kind` ∈ `ck.presence` / `ck.typing` / `ck.receipt.read` / `ck.call.signal`) | `user_session` 或 service signature；actor 必须可在 `realm_id` 的 ephemeral channel 中广播该 kind，并持有对应 `ck.presence.broadcast` / `ck.typing.broadcast` / `ck.receipt.broadcast` / `ck.call.signal.send` action。 | `{accepted: true, kind, realm_id, dispatched_to?, server_received_at?}`；不生成 Event ID、不推进 actor_seq / Realm frontier。 |
| `POST /_cokret/self/rtc/token` | body `{realm_id: id, call_id: id, actor_id: did, device_id: id, focus_id: string, capability_refs?: id[], desired_media?: object}` | `user_session` 或 device proof；调用方 MUST 持 `ck.call.join`，并根据 `desired_media` 持 `ck.call.screen_share` 等子 capability；token issuer DID MUST 出现在 `ck.realm.media_service.service_id` 锚定列表；当 `ck.call.state.session_focus` 已存在，请求的 `focus_id` MUST 等于该值（否则 `focus_mismatch`）。 | `{focus_id, type, connect_url, backend_token, participant_identity, participant_binding, expires_at, service_signature}`；`expires_at - now ≤ 600s`（SHOULD ≤ 300s）。`participant_binding.scheme="ck.media.participant_binding.v1"`，覆盖 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)`。媒体服务 token exchange；详见 [`../crypto-media/media-service-binding.md` §3](../crypto-media/media-service-binding.md)。 |
| `GET /_cokret/self/account/viewer` | query none | `user_session` bound to principal/device。返回当前 holder 的账号主体投影，不是服务能力 describe。 | `AccountViewerResponse {principal_id, primary_handle_claim?, primary_handle_claim_ref?, handle_claim_digests?, state, devices[], profile?}`；不得返回未签名裸 `handle` 作为权威身份。 |
| `GET /_cokret/self/account/subscribe` | query `{after?: cursor, catchup?: boolean, filter?: object, set_presence?: enum}` | `user_session` bound to principal/device。聚合账号视角 delta(跨 Realm frontier、to_device、account_data、device_lists、presence、unread / notification counts) streaming NDJSON 推送，不是裸事件读。 | `application/x-ndjson` AccountSubscribeFrame 流;frame kinds: `delta` / `catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`;`dropped` / `resync_required` 可带 `reconnect_after_ms`。 |
| `POST /_cokret/self/account/profile` | body `UpdateProfileRequest {patch}`；`patch` 为 `ck.patch.v1`，路径仅限 `display_name` / `avatar_blob_ref` / `profile_fields.<key>` | `user_session` bound to principal/device。`bio` 归入 `profile_fields.bio`；协议路径不接受 `avatar_url`、`handle`、lifecycle、principal、actor_kind、accountability 或 auth 字段。 | `UpdateProfileResponse {profile: ActorProfile}`；服务端 MUST 写入或等价产生 `ck.profile.update` / Actor Profile projection。 |
| `POST /_cokret/self/account/cursor/revoke` | body `{cursor: cursor, reason_code: string, revoke_scope?: enum(this_cursor,same_device,same_session)}` | `user_session` bound to principal/device；high-assurance optional profile。 | `{revoked: boolean, expires_at: datetime}`；撤销命中后的 cursor 使用返回 `cursor_revoked`，不得推进任何 server-side state。 |
| `GET /_cokret/self/account/describe` | query none | `public_metadata` 或 `user_session`；私有 limits 可认证后返回。 | `ServiceDescribe`；私有 frontier 只能作为认证后扩展字段返回。 |
| `POST /_cokret/self/contacts/request` | body `schemas/contact-operations.schema.json#/$defs/contact_request_request` | `user_session` bound to requester principal；requester 只能写自己的 contact request fact 与 requester-side consent grant。 | `schemas/contact-operations.schema.json#/$defs/contact_request_response`；投递签名 request envelope 给 target，不能替 target 写 consent 或 accepted fact。 |
| `POST /_cokret/self/contacts/respond` | body `schemas/contact-operations.schema.json#/$defs/contact_respond_request` | `user_session` bound to request target；accept 同步写 target-controlled consent grants。 | `schemas/contact-operations.schema.json#/$defs/contact_respond_response`；reject 不写 consent。 |
| `GET /_cokret/self/contacts` | query `{state?: enum, cursor?: cursor, limit?: int}` | `user_session` bound to holder principal；只返回 holder 可验证 contact projection 与本地备注合并视图。 | `schemas/contact-operations.schema.json#/$defs/contact_list_response`；`effective_scopes[]` 若出现必须等价于 `bidirectional_scopes[]`。 |
| `POST /_cokret/self/contacts/tombstone` | body `schemas/contact-operations.schema.json#/$defs/contact_tombstone_request` | `user_session` bound to holder principal；默认只撤销 contact-managed active consent dots。 | `schemas/contact-operations.schema.json#/$defs/contact_tombstone_response`；不得默认撤销同 peer 的独立组织 invite 授权。 |
| `POST /_cokret/self/direct-conversations/resolve` | body `schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_request` | `user_session`；MUST 同时验证 accepted contact 与 target holder 的 active `direct_message` / `any` consent。 | `schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_response`；create=true 时幂等创建 canonical DM Realm + main Flow + binding。 |
| `GET /_cokret/self/snapshot/head` | query `{realm_id: id}` | Realm read；snapshot manifest 必须签名，并包含 `event_set_commitment`、`created_by`、`created_at`、`authority_binding`（与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 一致）。high-assurance profile MUST 校验 `authority_binding` 证明 `created_by` 在 `created_at` 时被 Realm policy / witness quorum 授权。 | `{snapshot_ref, state_digest, frontier, event_set_commitment, created_by, created_at, authority_binding, verification_hints?, signature}` |
| `GET /_cokret/self/projection/spaces` | query `{realm_id: id, include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | `user_session` 或服务签名；调用方必须满足该 Realm 的 metadata/read 可见性。 | `{realm_id, spaces[], total, next_cursor?, has_more}`；`spaces[]` 行含 `space_id, realm_id, kind, title, parent_space_id?, rank?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `GET /_cokret/self/projection/flows` | query `{realm_id: id, include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | 同 `ck.projection.spaces`。 | `{realm_id, flows[], total, next_cursor?, has_more}`；`flows[]` 行可含从 plaintext-visible `metadata.title` / `metadata.summary` 派生的 `title?` / `summary?`，以及 `flow_id, realm_id, board_space_id?, list_space_id?, rank?, state, created_by?, created_at?, updated_at?, state_changed_at?`。`board_space_id/list_space_id/rank` 是从 `ck.component.flow.position.v1` cell 派生的只读 view 字段，不是 Flow object 的 canonical truth；当 metadata 加密且服务端不可见时 `title` / `summary` MUST 省略或为 `null`。 |
| `GET /_cokret/self/projection/morphs` | query `{realm_id: id, include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | 同 `ck.projection.spaces`。 | `{realm_id, morphs[], total, next_cursor?, has_more}`；`morphs[]` 行含 `morph_id, realm_id, morph_type, title?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `GET /_cokret/find/directory/describe` | query none | `public_metadata`；可限流。 | `ServiceDescribe`；directory resource / discovery capability 放入 `supported_features` / `limits` / 扩展字段。 |
| `POST /_cokret/find/directory/search-realms` | body `schemas/directory-operations.schema.json#/$defs/search_realms_request` | discoverability + requester proof + policy filtering；隐藏资源不泄露存在性。 | `schemas/directory-operations.schema.json#/$defs/search_realms_response` |
| `POST /_cokret/find/directory/resolve-realm` | body `schemas/directory-operations.schema.json#/$defs/resolve_realm_request` | invite / restricted / secret Realm 按统一 `not_found` 失败。 | `schemas/directory-operations.schema.json#/$defs/resolve_realm_response` |
| `POST /_cokret/find/directory/resolve-target` | body `schemas/directory-operations.schema.json#/$defs/resolve_target_request` | 对象级地址解析（`resolve_realm` 泛化）；`invite` / `preview` token 必须按 target descriptor 与 effective link type 校验；未授权统一 `not_found`。详见 [`../discovery/object-addressing.md` §6](../discovery/object-addressing.md)。 | `schemas/directory-operations.schema.json#/$defs/resolve_target_response`；preview token 成功时只返回 `ck.realm.preview_policy` 允许字段，除非另有 join routing 权限否则省略 `join_candidates[]`。 |
| `POST /_cokret/find/directory/search-organizations` | body `schemas/directory-operations.schema.json#/$defs/search_organizations_request` | 仅返回公开或授权可发现组织。 | `schemas/directory-operations.schema.json#/$defs/search_organizations_response` |
| `POST /_cokret/find/directory/resolve-organization` | body `schemas/directory-operations.schema.json#/$defs/resolve_organization_request` | 公开组织 DID 可解析不表示成员或拓扑公开。 | `schemas/directory-operations.schema.json#/$defs/resolve_organization_response` |
| `POST /_cokret/find/directory/search-actors` | body `schemas/directory-operations.schema.json#/$defs/search_actors_request` | 不得泄露 pairwise/private DID 或未披露组织账号。 | `schemas/directory-operations.schema.json#/$defs/search_actors_response` |
| `POST /_cokret/find/directory/search-users` | body `schemas/directory-operations.schema.json#/$defs/search_users_request` | `user_session`; 用于 mention autocomplete / 成员添加候选，必须受共同 Realm / directory policy 限制。请求词不得进入 URL、Referer 或明文 access log。 | `schemas/directory-operations.schema.json#/$defs/search_users_response`；每项 MAY 含 `{handle, display_name?, verified?, subject?}`，但受限 handle 未授权时不得披露 DID / delivery binding。 |
| `POST /_cokret/find/directory/resolve-handle` | body `schemas/directory-operations.schema.json#/$defs/resolve_handle_request` | 按 handle 双向验证规则；受限 / 组织 handle 需 presentation；返回 `member_delivery_binding` 时必须有 issuer claim / policy 证明。 | `schemas/directory-operations.schema.json#/$defs/resolve_handle_response` |
| `POST /_cokret/find/directory/list-handles-for-subject` | body `schemas/directory-operations.schema.json#/$defs/list_handles_for_subject_request` | 按 subject visibility、issuer trust、audience、requester policy 和 Realm intent 过滤；不得因为共同 Realm membership 单独披露受限组织 handle。 | `ck.schema.list_handles_for_subject_response.v1`：`{subject, claims[], primary_handle?, as_of, next_cursor?, has_more}`；`claims[]` 是当前 context 可见 signed handle claims，且 `claims[].subject` MUST 等于响应 `subject`。 |
| `POST /_cokret/self/blob/upload` | `multipart/form-data` body `schemas/blob-operations.schema.json#/$defs/upload_request`，其中 `content` 是二进制 part。 | `user_session`; upload capability、quota、media policy；私有 blob 绑定 Realm / actor。 | `schemas/blob-operations.schema.json#/$defs/upload_response` |
| `HEAD/GET /_cokret/self/blob/get` | query `{blob_ref: string}` headers `Authorization?`, `Range?`, `X-Cokret-Wait-For?` | 公开 blob 可匿名；header auth 路径必须验证 actor/device/Realm/purpose/expiry；除 §5.4 `ck.blob.presign` 的短 TTL bearer URL 例外外，不得 query string 认证。 | bytes 或 headers `{Content-Length?, Digest?, Cache-Control, Content-Type?, Content-Disposition?, Content-Range?}` |
| `POST /_cokret/self/blob/presign` | body `{blob_ref: string, max_age_seconds?: int (<=3600), purpose?: enum(media_inline, thumbnail, download)}` | `user_session`; 受 `ck.blob.presign` capability 控制；为单个 blob 签发短 TTL（默认 ≤ 5 min，硬上限 ≤ 1h）、单对象、只读、可撤销 pre-signed URL。仅供浏览器 `<img src>` / `<video src>` 等原生标签渲染受保护媒体；E2EE 附件 ciphertext MUST NOT 经此下发。 | `{url, expires_at, purpose}`；详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `POST /_cokret/edge/push/register-device` | body `{device_id: id, push_gateway: url, push_key: string, platform?: string, app_id?: string, display_name?: string, recipient_service_did?: did}` | `user_session` for same principal/device；registration 作用域绑定当前 Principal Server service DID；push_key 必须被加密或最小披露存储。 | `{ok: true, registration_id?, expires_at?}` |
| `POST /_cokret/edge/push/unregister-device` | body `{device_id: id, push_key?: string, app_id?: string}` | `user_session` for same device/principal 或 device revocation path。 | `{ok: true}` |
| `POST /_cokret/edge/push/notify` | body `schemas/push-operations.schema.json#/$defs/notify_request`；默认 `notification` 为 blind 形态 `{push_target_id, wakeup_kind, push_hint?, counts?, devices[]}`，可见通知必须使用互斥的 profile-gated visible 形态。 | 来自被授权 Sync 或通知服务的 `service_signature`；默认 MUST 遵守 `ck.profile.push_gateway.blind_wakeup.v1`，不得携带 event / realm / sender 识别字段。`visible_notification` 只在 profile、Realm policy、设备 opt-in 和 UI disclosure 同时满足时允许。 | `schemas/push-operations.schema.json#/$defs/notify_response` |
| `POST /_cokret/self/device_messages` | header `Idempotency-Key` body `DeviceMessagesPutRequest {messages: {principal_id: {device_id: DeviceMessageTarget {kind, content, expires_at}}}}` | sender `user_session` / device key；目标必须是授权 device；服务端入队前 MUST materialize `DeviceMessageEnvelope` 并绑定 `recipient_principal_id` / `recipient_device_id` / `expires_at`；按 `(sender, Idempotency-Key)` 幂等。验证消息使用 `ck.key.verification.*` kind，且不得作为持久 Event history；缺失、已过期或超过 TTL 上限的消息 MUST reject。 | `{ok: true, delivered?, unknown_devices?}` |
| `GET /_cokret/self/device_messages` | query `{from?: cursor, limit?: int}` | `user_session` bound to current device；只返回该 device 队列。 | `{messages: DeviceMessageEnvelope[], next_cursor?, has_more, limited?}` |
| `POST /_cokret/self/keys/upload` | body `{device_id: id, one_time_keys?: object, fallback_keys?: object, device_signature: signature}` | current device proof；key 必须链接 self-signing / principal key。 | `{one_time_key_counts, fallback_keys?}` |
| `POST /_cokret/self/keys/query` | body `{device_keys: {principal_id: string[]}, timeout_ms?: int}` | `user_session`; 查询范围可按关系 / Realm 限制。 | `{device_keys, failures?}` |
| `POST /_cokret/self/keys/claim` | body `{one_time_keys: {principal_id: {device_id: algorithm}}}` | `user_session`; one-time key MUST 原子消费。 | `{one_time_keys, failures?}` |
| `PUT /_cokret/self/keys/backups/{backup_id}` | path `{backup_id}` body `ck.schema.key_backup.v1` | current device proof / DID proof / recovery proof；path 与 body backup id 必须一致。 | `{status, backup_id, ciphertext_digest}` |
| `GET /_cokret/self/keys/backups` | query `{series_id?: id, backup_class?: string, cursor?: cursor, limit?: int}` | `user_session` bound to current principal/device 或 recovery proof。 | `{backups[], next_cursor?, has_more}` |
| `GET /_cokret/self/keys/backups/{backup_id}` | path `{backup_id}` | 同 principal 当前授权 device、recovery policy 或授权组织恢复服务。 | `ck.schema.key_backup.v1` |
| `DELETE /_cokret/self/keys/backups/{backup_id}` | path `{backup_id}` body `{proof, reason?}` | 高风险 device proof、DID proof 或 recovery policy proof。 | `{deleted: true, backup_id?}` |
| `POST /_cokret/root/identity/recovery-sessions` | body `ck.schema.recovery_session.v1#/$defs/create_request` | 创建 device recovery session；server MUST snapshot active recovery policy and accepted `ssk_generation`, issue a 256-bit one-time challenge, and set TTL <= 900s. | `ck.schema.recovery_session.v1` |
| `GET /_cokret/root/identity/recovery-sessions/{recovery_session_id}` | path `{recovery_session_id}` | 仅 session principal / requesting device / authorized recovery coordinator 可见；不得枚举他人 session。 | `ck.schema.recovery_session.v1` |
| `POST /_cokret/root/identity/recovery-sessions/{recovery_session_id}/proofs` | path `{recovery_session_id}` body `ck.schema.recovery_session.v1#/$defs/proof_submit_request` | proof MUST verify against the server-reconstructed canonical transcript and echo the session challenge. | `ck.schema.recovery_session.v1#/$defs/proof_submit_response` |
| `POST /_cokret/root/identity/recovery-sessions/{recovery_session_id}/complete` | path `{recovery_session_id}` body `ck.schema.recovery_session.v1#/$defs/complete_request` | Requires `state=verified`; MUST emit accepted `ck.device.authorize` and `ck.device.list_update` before returning completed. | `ck.schema.recovery_session.v1#/$defs/complete_response` |
| `GET /_cokret/self/authz/effective-grants` | query `{realm_id: id, subject: did, at?: string}` | subject 本人、Realm admin、authorized service；不得枚举无关 subject。 | `{grants[], state_digest?, evaluated_at}` |
| `GET /_cokret/self/authz/invites` | query `{realm_id?: id, subject: did 或 string, cursor?: cursor}` | subject 本人或 inviter/admin；secret invites 不可枚举。 | `schemas/authz-operations.schema.json#/$defs/get_invites_response` |
| `POST /_cokret/self/authz/check` | body `{actor_id: did, action: string, resource?: object, context?: object}` | caller 必须是相关 actor、Events/Sync 预检查服务或 policy-authorized service。 | `{decision, matched_grants?, applied_constraints?, policy_results?, missing_proofs?, frontier?, freshness_state?, last_known_frontier_age_ms?, anchorer_status?, cache_expires_at?, reason_code?, retry_after_ms?, obligations?}` |
| `POST /_cokret/self/policy/check` | body `PolicyCheckRequest {request_id, realm_id, request_canonical_digest, action, actor, source, event_preview?, auth_context?}` | `policy_token` / `service_signature`; 只接收最小披露字段。 | `PolicyCheckResponse {request_id, bound_to, decision, reason_code, expires_at, auth_state_digest, policy_frontier_digest, membership_frontier_digest, obligations?, signature}`。 |
| `POST /_cokret/self/moderation/report` | body `{realm_id: id, target_ref: id, report_reason_code: enum, description?: string, reporter: did, evidence_refs?: id[]}` | `user_session`; reporter 必须可见 target；report 仅对 moderators 可见。 | `{report_id, status, routed_to?}` |
| `POST /_cokret/self/applets/install/preview` | body `schemas/applet-install-operations.schema.json#/$defs/preview_request` `{applet_package, effective_scope, approval_request}` | `user_session`; self/admin aggregate operation；只读预览，不写 Realm history。 | `InstallPlan`（`schemas/applet-install-plan.schema.json`）；返回 canonical `plan_digest`。 |
| `POST /_cokret/self/applets/install` | header `Idempotency-Key` body `schemas/applet-install-operations.schema.json#/$defs/install_request` `{plan_digest, applet_package, effective_scope, approved_scopes, ...}` | `user_session`; self/admin aggregate operation；MUST 重算 plan，`plan_digest` 不匹配返回 `applet_install_plan_mismatch`；不创建 durable `ck.applet.install` event。 | `schemas/applet-install-operations.schema.json#/$defs/install_response` |
| `POST /_cokret/self/applets/{applet_id}/revoke` | path `{applet_id}` body `schemas/applet-install-operations.schema.json#/$defs/revoke_request` `{effective_scope, reason_code, revoke_mode}` | `user_session`; self/admin aggregate operation；撤销 bound grants / widget tokens / delegated sessions。 | `schemas/applet-install-operations.schema.json#/$defs/revoke_response` |
| `GET /_cokret/edge/applet/ping` | query none | `public_metadata` 或 `service_signature`；不得泄露 private namespace。 | `schemas/applet-edge-operations.schema.json#/$defs/ping_response` |
| `GET /_cokret/edge/applet/describe` | query none | `service_signature` SHOULD；public mode 只返回公开 capabilities。 | `ServiceDescribe`；applet protocols / namespaces / auth capability 放入 `supported_features` / `limits` / 扩展字段。 |
| `POST /_cokret/edge/applet/transactions` | header `Idempotency-Key` body `schemas/applet-edge-operations.schema.json#/$defs/transaction_request` | `service_signature`; Applet 必须验证每个 event signature、namespace 和 capability；按 `(source_service_did, Idempotency-Key)` 幂等。 | `schemas/applet-edge-operations.schema.json#/$defs/transaction_response` |
| `GET /_cokret/edge/applet/actors/{actor_id}` | path `{actor_id}` | `service_signature`; actor_id 必须命中 Applet actor namespace。 | `schemas/applet-edge-operations.schema.json#/$defs/resolve_actor_response` 或 `not_found` |
| `GET /_cokret/edge/applet/realms/{realm_id_or_alias}` | path `{realm_id_or_alias}` | `service_signature`; 必须命中 portal namespace 或授权查询。 | `schemas/applet-edge-operations.schema.json#/$defs/resolve_realm_response` |
| `GET /_cokret/edge/applet/protocols/{protocol}` | path `{protocol}` | 可 public_metadata；实例列表可要求授权。 | `schemas/applet-edge-operations.schema.json#/$defs/protocol_metadata_response` |
| `GET /_cokret/edge/applet/third_party/users` | query `{protocol, external_id, instance_id?}` | `service_signature`; 查询字段必须在 registration namespace 内。 | `schemas/applet-edge-operations.schema.json#/$defs/third_party_user_response` |
| `GET /_cokret/edge/applet/third_party/locations` | query `{protocol, external_id, instance_id?}` | `service_signature`; 查询字段必须在 portal namespace 内。 | `schemas/applet-edge-operations.schema.json#/$defs/third_party_location_response` |
| `POST /_cokret/self/rtc/ice-config` | body `schemas/media-operations.schema.json#/$defs/ice_config_request` | `user_session`; actor 必须有 call/media capability，Realtime Media Server 必须被 Realm policy 委托。 | `schemas/ice-config-response.schema.json` |
| `POST /_cokret/self/keys/keypackages/upload` | body `{principal_id, device_id, key_packages[], device_signature, expires_at?, flow_id?, mls_group_id?}` | `user_session` + 当前 device proof;每条 KeyPackage 必须 self-signed 并通过当前 device 签发。 | `{accepted, rejected?, key_package_refs?, available_count?}` |
| `POST /_cokret/self/keys/keypackages/claim` | body `{target_principal_id, intended_realm_id, requester, required_capabilities[], claim_nonce, expires_at, target_device_ids?, minimal_metadata_allowed?, timeout_ms?, flow_id?, mls_group_id?, proofs?}` | `user_session`;一次性 KeyPackage MUST 原子 claim(同 `ck.keys.claim`)。 | `{claims[], failures?, available_count?}` |
| `POST /_cokret/self/keys/keypackages/consume` | body `{key_package_refs[], consumer_device_id, signature, flow_id?, epoch?}` | `service_signature`(MLS group creator 通常是 service-side 调用) 或 `user_session`。 | `{consumed[], failures?}` |
| `POST /_cokret/self/keys/keypackages/revoke` | body `{key_package_refs[], device_id, signature, reason?}` | `user_session` + 当前 device proof;不可撤销已消费的 KeyPackage。 | `{revoked[], failures?}` |
| `POST /_cokret/find/directory/announce` | body `{resource_kind, resource_id, discovery_state, source_refs, as_of, principal_server_did, ttl_seconds?, supersedes_announce_id?}` | `user_session` 或 `service_signature` 视 resource_kind；principal/server MUST 签发 discovery state 与 ingest request。 | `{announce_id, indexed_at, effective_ttl_seconds, next_revalidation_after, warnings?}` |
| `POST /_cokret/find/directory/withdraw` | body `{resource_id, governance_proof, reason?, effective_at?}` | `user_session` 或 `service_signature`；必须由 resource governance key 证明撤销权。 | `{withdrawal_ref, acked_at}` |
| `POST /_cokret/find/directory/push/register` | body `schemas/directory-operations.schema.json#/$defs/push_register_request` `{subscriber_did, resource_filter, webhook_endpoint, secret?, expires_at?}` | `user_session` 或 `service_signature`；directory 变更 push webhook 注册，仅作为 pull 模式优化，不替代 freshness 协议。 | `schemas/directory-operations.schema.json#/$defs/push_register_response` |
| `POST /_cokret/gate/account/register` | body `AccountRegisterRequest {principal_id, display_name?, device_id?, proof?}` | bootstrap proof / DID-bound signature / paired device proof / holder-bound Authorization、与 `ck.account.issue_session_grant` 同 proof 词汇。`principal_id` 是 DID；不得接受旧 `did` 字段或裸 `handle` 字段。 | `AccountResponse {principal_id, state, devices[], primary_handle_claim?, primary_handle_claim_ref?, handle_claim_digests?, profile?}`；首次 handle 只能通过 signed handle claim / digest / ref 出现。 |
| `POST /_cokret/gate/account/session-grants` | body `SessionGrantRequest {principal_id, device_id?, requested_scope?, proof}` | DID-bound signature / paired device proof / passkey assertion / OIDC code exchange proof。请求体 proof MUST 绑定 challenge、audience、request canonical hash、principal 与 device。 | `SessionGrantResponse {principal_id, device_id?, session_grant, expires_at, granted_scope?}` |
| `POST /_cokret/gate/account/session-grants/revoke` | body 可省略，或 `SessionRevokeRequest {target_grant_id?, target_device_id?, all_sessions?, proof?}` | `user_session` 撤当前 session；跨 grant / device / all_sessions 需要 fresh DID/device proof 或显式 capability。三个 selector 互斥，target 必须属于当前 principal。 | `SessionRevokeResponse {revoked_count, revoked_grant_ids?}`；撤 session grant / access token，不撤 device authorization，不隐式写 `ck.account.status`。 |
| `POST /_cokret/gate/account/device-pair` | body `{pairing_code, new_device_pubkey, challenge_signature}` | `user_session` + existing device proof + freshly minted pairing code(短 TTL, one-time, audience-bound to this Auth Server origin); endpoint 与 session-grants 同一部署本地 namespace；服务端 MUST 对 `(principal_id, source_device_id, target_origin)` 限速并防重放。 | `{device_id, authorized_event_ref}` |
| `POST /_cokret/gate/account/agent-key-pair` | body `{agent_principal_id, verification_method, public_key, proof_of_possession, runtime_attestation?}` | `user_session` + pairing request。`verification_method` 的 DID 部分 MUST 与 `agent_principal_id` bit-identical，不匹配 `failed_precondition` / `verification_method_principal_mismatch`。 | `{ok: true, authorized_event_ref}` |
| `GET /_cokret/self/agents` | query `{cursor?, limit?, state?}` | `user_session` bound to controller principal；只列出调用方可管理的 native personal agent。 | `{agents[], next_cursor?, has_more}` |
| `POST /_cokret/self/agents` | body `{display_name?, requested_scope?, accountability?, pairing_ttl_ms?}` | controller `user_session`；编排 Actor Profile、accountability_grant、初始 capability grant 与 runtime pairing request。 | `{agent_principal_id, pairing_request_id, pairing_code?, expires_at}` |
| `GET /_cokret/self/agents/{agent_principal_id}` | path `{agent_principal_id}` | controller `user_session` 或 policy-authorized admin。 | `{agent, status, grants?, key_state?}` |
| `POST /_cokret/self/agents/{agent_principal_id}/pause` | path `{agent_principal_id}` body `{reason?}` | controller-only；暂停 agent 并拒绝新 agent session grant。 | `{ok: true, status: "paused"}` |
| `POST /_cokret/self/agents/{agent_principal_id}/resume` | path `{agent_principal_id}` body `{sidecar_exposure_ack?}` | controller-only；必须重新校验 controller/agent/key/grant freshness，并在 pause 期间新增 sidecar exposure 时要求显式确认。 | `{ok: true, status: "active"}` |
| `POST /_cokret/self/agents/{agent_principal_id}/deactivate` | path `{agent_principal_id}` body `{reason?}` | controller-only terminal transition；fan-out agent key revoke、capability revoke 与 runtime endpoint revoke。URL 路径与 op id `ck.agent.deactivate` 保持一致。 | `{ok: true, status: "deactivated"}` |
| `POST /_cokret/self/agents/{agent_principal_id}/rotate-key` | path `{agent_principal_id}` body `{replacement_key, proof_of_possession}` | controller + active agent key policy；不得扩大 agent key scope 或延长有效期。 | `{ok: true, authorized_event_ref}` |
| `POST /_cokret/self/agents/{agent_principal_id}/grants` | path `{agent_principal_id}` body `{grant}` | controller grant authority；grant subject 必须是该 agent principal，且不得超过 controller 可委托范围。 | `{ok: true, grant_id}` |
| `DELETE /_cokret/self/agents/{agent_principal_id}/grants/{grant_id}` | path `{agent_principal_id, grant_id}` | controller grant authority；撤销或解绑 agent grant，后续 agent action proof fail closed。 | `{ok: true, revoked_at}` |
| `POST /_cokret/self/agent-sidecar-threads:ensure` | body `{realm_id, controller_principal_id, agent_principal_id}` | controller `user_session` + `ck.agent.sidecar_thread.ensure`；在 eligibility、Circle membership active，且若 Circle 为 MLS-backed 则 MLS membership active 后，才 fanout notification/context。 | `{ok: true, private_circle_id, private_flow_id, private_relation_id, pending_member_reconciliation?}` |
| `POST /_cokret/gate/account/oidc/callback` | body `AccountOidcCallbackRequest {state, code, nonce?, redirect_uri?}` | `public_metadata` 的回调入口(OIDC IdP 重定向);服务端 MUST 校验 `state` / `nonce` / `redirect_uri` 并把外部主体映射到 Cokret principal。 | `AccountOidcCallbackResponse {principal_id, session?}` 或 `{redirect_url}` |
| `GET /_cokret/open/mimi/provider-directory` | query `{provider_did?, capabilities?: string[]}` | `public_metadata`;provider 列表本身公开。 | `{providers[]}` |
| `POST /_cokret/open/mimi/key-material` | body `schemas/mimi-operations.schema.json#/$defs/key_material_request` | `service_signature`(MIMI provider-to-provider) 或 `user_or_service`。 | `schemas/mimi-operations.schema.json#/$defs/key_material_response` |
| `PUT /_cokret/open/mimi/flows/{flow_id}/update` | path `{flow_id}` body `schemas/mimi-operations.schema.json#/$defs/room_update_request` | `service_signature`。 | `schemas/mimi-operations.schema.json#/$defs/room_update_response` |
| `POST /_cokret/open/mimi/flows/{flow_id}/notify` | path `{flow_id}` body `schemas/mimi-operations.schema.json#/$defs/notify_request` | `service_signature`。 | `schemas/mimi-operations.schema.json#/$defs/notify_response` |
| `POST /_cokret/open/mimi/flows/{flow_id}/messages` | path `{flow_id}` body `schemas/mimi-operations.schema.json#/$defs/submit_message_request` | `service_signature`;MIMI 跨 provider message。 | `schemas/mimi-operations.schema.json#/$defs/submit_message_response` |
| `GET /_cokret/open/mimi/flows/{flow_id}/group-info` | path `{flow_id}` query `{epoch?, include_proof?}` | `service_signature` 或 `user_session` (member proof)。 | `schemas/mimi-operations.schema.json#/$defs/group_info_response` |
| `POST /_cokret/open/mimi/consent/request` | body `schemas/mimi-operations.schema.json#/$defs/request_consent_request` | `service_signature` 或 `user_session`。 | `schemas/mimi-operations.schema.json#/$defs/request_consent_response` |
| `POST /_cokret/open/mimi/consent/update` | body `schemas/mimi-operations.schema.json#/$defs/update_consent_request` | `service_signature` 或 `user_session`。 | `schemas/mimi-operations.schema.json#/$defs/update_consent_response` |
| `POST /_cokret/open/mimi/identifiers/query` | body `schemas/mimi-operations.schema.json#/$defs/identifier_query_request` | `service_signature` 或 `user_session`;不得用于枚举攻击,query MUST 限速。 | `schemas/mimi-operations.schema.json#/$defs/identifier_query_response` |
| `POST /_cokret/open/mimi/report-abuse` | body `schemas/mimi-operations.schema.json#/$defs/report_abuse_request` | `user_session` 或 `service_signature`;同 `ck.moderation.report` 互补。 | `schemas/mimi-operations.schema.json#/$defs/report_abuse_response` |
| `POST /_cokret/open/mimi/proxy-download` | body `schemas/mimi-operations.schema.json#/$defs/proxy_download_request` | `service_signature`;MIMI 桥接 blob 时使用；不接受 user_session。 | `schemas/mimi-operations.schema.json#/$defs/proxy_download_response` |

> **§2.3 表格作用域**: 上表是 v1 core 服务面**所有**已注册 HTTP operation 的 endpoint 契约清单(operation_id 的权威计数由 generated registry 视图 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 维护，本文不硬编码数字；一个 operation_id 对应多个 HTTP 别名时合并展示)。Auth / MIMI / Keys.keypackages / Directory.announce|withdraw 等子表面也都在表中；先前版本曾把部分子表面留在独立章节，现已合并回 §2.3 以保证 operation discovery 完整。OpenAPI 是 **HTTP/JSON binding** 的机器可消费最终来源；operation id、event kind、schema id 与 profile id 的全局 canonical source 仍是 `contract-catalog.json` / 对应 registry；operation DTO 字段集合的生成索引为 [`operation-schema-index.json`](../../artifacts/reports/operation-schema-index.json)。本表是人类阅读视图。

> **错误码映射**: 每个 operation_id 的 operation-specific 错误码集合（在通用 `unauthenticated` / `auth_expired` / `schema_violation` / `rate_limited` / `internal_error` / `service_unavailable` 等通用失败面之外）由 [`artifacts/registry/operations-error-mapping.json`](../../artifacts/registry/operations-error-mapping.json) 给出。错误码语义见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。

#### 2.3.1 Wire-level JSON 示例

以下三段示例展示 §2.3 表中三类典型 binding。所有 fence 标 `schema=schemas/event-envelope.schema.json expect=valid`(canonical `ck.schema.event.v1` artifact),与 [`event-and-patch.md` §2.3](../models/event-and-patch.md) 的 canonical Event Envelope shape 一致。每条 envelope 均为 reducer-input event,因此携带顶层 `preconditions[]` / `effects[]` / `anchor_ref` 三件套(详见 [`event-and-patch.md` §2.2](../models/event-and-patch.md))。

**示例 A — `POST /_cokret/self/events`(单事件提交,`ck.message.create`)**:

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 4,
  "kind": "ck.message.create",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": ["ck:event:019640ed-0000-7000-8000-000000000000"],
  "refs": [
    { "id": "ck:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "preconditions": [
    {
      "cell": "ck:cell:ck.component.flow.discussion.timeline.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "predicate": { "op": "head_eq", "value": { "head_event_id": "ck:event:019640ed-0000-7000-8000-000000000000" } }
    }
  ],
  "effects": [
    {
      "cell": "ck:cell:ck.component.flow.discussion.timeline.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "append", "value": { "message_id": "ck:message:019640ed-8000-7000-8000-000000000000" } }
    }
  ],
  "anchor_ref": "ck:anchor:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "flow_id": "ck:flow:019640c6-8000-7000-8000-000000000000",
    "track_name": "discussion",
    "content": { "kind": "ck.content.text", "body": "Sample message" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

**示例 B — `GET /_cokret/self/events?realms=...&after=...&limit=2`(分页响应,`events[]` 中的一条 `ck.message.create`)**:

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ck:event:019640ed-9000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:bob.example",
  "actor_seq": 7,
  "kind": "ck.message.create",
  "created_at": "2026-04-26T00:01:00Z",
  "hlc": "01970e589d34-0001-c00ff00f",
  "prev_refs": ["ck:event:019640ed-8500-7000-8000-000000000000"],
  "refs": [
    { "id": "ck:grant:0196410c-1000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "preconditions": [
    {
      "cell": "ck:cell:ck.component.flow.discussion.timeline.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "predicate": { "op": "head_eq", "value": { "head_event_id": "ck:event:019640ed-8500-7000-8000-000000000000" } }
    }
  ],
  "effects": [
    {
      "cell": "ck:cell:ck.component.flow.discussion.timeline.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "append", "value": { "message_id": "ck:message:019640ed-9000-7000-8000-000000000000" } }
    }
  ],
  "anchor_ref": "ck:anchor:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "flow_id": "ck:flow:019640c6-8000-7000-8000-000000000000",
    "track_name": "discussion",
    "content": { "kind": "ck.content.text", "body": "Reply" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:bob.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:01:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

外层分页响应形如 `{events: [<示例 A>, <示例 B>], next_cursor: "<opaque>", has_more: true}`(`events[]` 顺序见 §3.3,`next_cursor` 永远朝更新方向)。

**示例 C — `GET /_cokret/self/events/subscribe`(NDJSON stream frame 的 `ck.reaction.add` payload)**:

每一帧为一行 JSON;`event` kind frame 携带完整 envelope:

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ck:event:019640ee-0000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:carol.example",
  "actor_seq": 12,
  "kind": "ck.reaction.add",
  "created_at": "2026-04-26T00:02:00Z",
  "hlc": "01970e589d40-0002-c00fbeef",
  "prev_refs": ["ck:event:019640ed-9000-7000-8000-000000000000"],
  "refs": [
    { "id": "ck:grant:0196410c-2000-7000-8000-000000000000", "role": "authorized_by", "critical": true },
    { "id": "ck:event:019640ed-8000-7000-8000-000000000000", "role": "parent_event", "critical": false }
  ],
  "preconditions": [
    {
      "cell": "ck:cell:ck.component.message.reactions.v1:ck:message:019640ed-8000-7000-8000-000000000000",
      "predicate": { "op": "satisfies", "value": { "actor_id": "did:web:carol.example", "key": "+1", "absent": true } }
    }
  ],
  "effects": [
    {
      "cell": "ck:cell:ck.component.message.reactions.v1:ck:message:019640ed-8000-7000-8000-000000000000",
      "op": { "kind": "add", "value": { "actor_id": "did:web:carol.example", "key": "+1" } }
    }
  ],
  "anchor_ref": "ck:anchor:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "target_ref": "ck:message:019640ed-8000-7000-8000-000000000000",
    "key": "+1"
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:carol.example#device-2",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:02:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

订阅外层帧形如 `{"kind":"event","realm_id":"ck:realm:...","cursor":"<opaque>","payload":<上面 envelope>}`,详见 §2.3 `ck.events.subscribe` 行与 [`client-sync.md`](./client-sync.md) §12。

跨域 actor 验证响应（通过 `/_cokret/root/identity/resolve` 与 holder-approved presentation challenge 获得）只能作为缓存加速或辅助诊断。接收方在接受事件、成员变更或设备绑定前，仍 MUST 独立验证 DID Document、key log、签名 transcript、capability 和 Realm policy；不得把对端"验证通过"当成最终授权依据。

### 2.4 字段级 Schema 索引

本节是 REST 端点的字段级人类索引。字段写法为 `name: type - 说明`。出现在“必填字段”列的字段为该索引中的 required 摘要；出现在“可选字段”列的字段为 optional 摘要。位置若非 body，会显式标注为 `path.`、`query.` 或 `header.`。机器契约已存在时，“约束”列必须指向 `schema_ref`；完整字段集合、required 性、closed/open 状态以 JSON Schema 和 pipeline 生成的 [`operation-schema-index.json`](../../artifacts/reports/operation-schema-index.json) 为准。字段顺序按 operation DTO 顺序：target / identity 字段、scope 字段、auth/proof 字段、option 字段、body/content 字段、result 字段、audit/time 字段。

规范性 operation contract 以 `artifacts/registry/contract-catalog.json#operation_registry` 为 canonical source；`artifacts/registry/operation-registry.json` 与 `artifacts/reports/operation-schema-index.json` 是其生成视图。本表、OpenAPI 与非 HTTP binding 均 MUST 从 canonical source 生成或通过 CI 校验；不得新增 catalog 中不存在的 `operation_id`，也不得在声明支持某 operation 时遗漏对应 catalog 条目。

#### 2.4.1 Binding completeness index

`binding_completeness` 由 operation registry 派生：声明 `request_schema_ref` / `response_schema_ref` 且 OpenAPI 指向同一 schema fragment 的 operation 为 `typed_schema`；未来 profile 若重新引入通用 `OperationRequest` / `OperationResult` binding,该 operation 必须声明为 `generic_binding`；若该 generic row 带 `migration_plan`，则对实现者显式标为 `migration_required`。`migration_required` operation 不得被宣称为 generated-SDK complete；SDK、gateway validator 与 conformance runner MUST 继续读取对应字段表、profile gate、capability、policy 和 canonical digest 规则，直到 dedicated DTO schema 落地。

当前无 `migration_required` operation。未列出的 operation 在 registry 中已经是 `typed_schema`、无 body 的 status response，或不使用 generic operation envelope。

| `operation_id` | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `ck.server.describe` | 无 | `query.service_type: string - 过滤服务类型` | `ServiceDescribe` | `public_metadata`; 不得返回私有拓扑或 secret。`trust_domain` 与 `plaintext_visibility` 必填；缺失时 callers MUST fail closed。 |
| `ck.identity.describe_registry` | 无 | 无 | `ServiceDescribe` | `public_metadata`; 可限流；identity-specific 字段只能作为扩展字段追加。 |
| `ck.identity.resolve` | `did: did - 待解析 DID` | `include: string[] - 请求附加证据，如 key_log/receipts` | `did_document: object`; `key_log_head: id?`; `seq: int?`; `receipts: object[]?`; `method_evidence: object?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityResolveRequest / schemas/service-operation-dtos.schema.json#/$defs/IdentityResolveResponse。private / pairwise DID 可要求 presentation proof。 |
| `ck.identity.get_document` | `query.did: did` | `query.version: string - 指定版本或 head` | `did_document: object`; `head_event_digest: string?`; `seq: int?`; `receipts: object[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityGetDocumentResponse。可见性同 `ck.identity.resolve`。 |
| `ck.identity.get_log` | `query.did: did` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `has_more: boolean` | private / pairwise DID MUST 要求 holder-approved proof。 |
| `ck.identity.submit_did_operation` | `did: did`; `did_method: string`; `operation: object`; `proofs: proof[]` | `seq: int`; `prev_event_digest: string`; `policy_context: object` | `status: enum(accepted,duplicate,pending)`; `did: did`; `head_event_digest: string?`; `seq: int?`; `operation_ref: string?`; `receipts: object[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DidOperationSubmitRequest / schemas/service-operation-dtos.schema.json#/$defs/DidOperationSubmitResponse。MUST 满足 DID method / key-log 授权；`operation` 是 DID-method-specific 原始操作，统一 wrapper 不得把 DID 更新降格为通用 `patch`；幂等键由 DID method operation id / seq / canonical hash 决定。 |
| `ck.identity.get_receipts` | `query.did: did`; `query.head: string` | 无 | `receipts: object[]`; `threshold_met: boolean?` | 只公开最小 witness receipt。 |
| `ck.events.describe` | 无 | `query.actor_id: did`; `query.realm_id: id` | `ServiceDescribe` | public metadata 可公开；私有 frontier 需认证后作为扩展字段返回。 |
| `ck.events.submit` | 单事件提交 body 是 `EventSubmitEnvelope` 对象（顶层 `event_id`/`actor_id`/`payload`/`proofs[]` ...，但不含 reducer-managed accepted-output 字段）；批量提交 body 是 `{events: EventSubmitEnvelope[]}`。MUST NOT 使用 `{event: ...}` wrapper。 | `expected_frontier: object`; `idempotency_key: string` | `status: enum(accepted,duplicate,partial)`; `accepted: id[]`; `duplicate: id[]?`; `rejected: object[]?`; `actor_frontier: object?`; `realm_frontier: object?`; `cursor: cursor?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsSubmitRequest / schemas/service-operation-dtos.schema.json#/$defs/EventsSubmitResponse。MUST 验证 Event signature、DID、capability、Realm policy、`actor_seq`、`prev_refs` 和 `refs[role=authorized_by]`。同一 `event_id` 对应不同 canonical 内容时 MUST 以 `duplicate_conflict`（409）拒绝（见 [operations-sync.md](./operations-sync.md) §15），不得退化为 `causal_conflict` / `state_mismatch`。`cursor` 是 barrier purpose（read-your-writes）。 |
| `ck.events.get` | `path.event_id: id` | `query.include_payload: boolean` | `event: object`; `visibility: object?`; `receipts: object[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventGetResponse。不可见时返回 `not_found`。 |
| `ck.events.resolve` | 至少一个：`event_ids: id[]` 或 `event_digests: string[]` | `include_payload: boolean` | `events: object[]`; `missing: id[]`; `unauthorized: id[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsResolveRequest / schemas/service-operation-dtos.schema.json#/$defs/EventsResolveResponse。payload 可见性按 Realm policy / E2EE envelope 判断。 |
| `ck.events.query` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.before: cursor`; `query.after: cursor`; `query.order: enum(default,ascending,descending)=default`; `query.limit: int`; `query.filters: object` | `events: object[]`; `next_cursor: cursor?`; `prev_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryResponse。`realms[]` 内部 union、`actors[]` 内部 union、二者组合为 intersection。每个 selector 元素都按对应可见性约束逐项检查：actor scope 走 actor history visibility；realm scope 走 membership frontier + history visibility + E2EE epoch policy。`before` / `after` 均为开区间（排除 cursor 自身），可单独或同时给出形成 `(after, before)` 区间。默认顺序：仅 `before` → descending，仅 `after` → ascending，两者皆给 → descending；`order=ascending\|descending` 显式覆盖。响应 `prev_cursor` 永远朝更旧方向、`next_cursor` 永远朝更新方向。仅支持 `before` / `after` / `order` 参数。详见 §3.3。 |
| `ck.events.query_post` | body 至少一个：`realms: id[]` 或 `actors: did[]` | `before: cursor`; `after: cursor`; `order: enum(default,ascending,descending)=default`; `limit: int`; `filters: object` | 与 `ck.events.query` 同 | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryPostRequest / schemas/service-operation-dtos.schema.json#/$defs/EventsQueryResponse。`ck.events.query` 的 HTTP POST/body binding variant（registry `binding_variant_of="ck.events.query"`）。语义、selector 规则、默认顺序、响应 cursor 含义、错误码与 GET 形态完全一致；仅 wire 形态从 query string 变为 JSON body。**何时使用**：`realms[]` / `actors[]` 较大、`filters` 较复杂、或部署侧记录 access log 时担心 query string 泄露 filter 内容。gRPC / MQ 不需要单独绑定（统一走 `Events/Query`）。 |
| `ck.events.subscribe` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.after: cursor`; `query.catchup: boolean=false` | stream frame: `kind: enum(event,frontier,heartbeat,catchup_complete,epoch_rotation,dropped,resync_required,unauthorized)`; `realm_id: id?`; `cursor: cursor?`; `payload: object?`;`reconnect_after_ms: int?` | 同 `ck.events.query` 逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性。`after=<cursor>` 是订阅起点（不含 cursor 本身），与 `ck.events.query` 的 `after=` 同义；subscribe 天然只走未来方向，不接受 `before=` / `order=`。`catchup=true` 只表示从 `after=` 到当前 frontier 的追赶 replay，不表示全量历史；缺省或无 `after` 时只进入 live tail。某 realm 中途授权丢失 MUST 发出 `unauthorized` 帧并继续其他 realm；该帧 payload 至少包含 `reason_code`、`selector`、`retry_after_ms?`，不得包含不可见 Realm 标题、成员或 actor 集合。服务端因容量丢弃发出 `dropped` 帧，客户端必须 reconcile；`dropped` / `resync_required` MAY 携带 `reconnect_after_ms`，约束下一次同 scope 订阅重连。 |
| `ck.events.frontier` | 至少一个：`query.actor_id: did` 或 `query.realm_id: id` | `query.peer_role: enum(account_client, federation_peer, anonymous_health) = account_client` | `frontier: object`; `receipts: object[]?`; `frontier_root: hash?`; `actor_seq_upper_bounds: object?`; `signature: object?`; `cache_expires_at: datetime?`; `retry_after_ms: int?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsFrontierResponse。统一 operation 同时承载 public Events API 与 federation peer frontier probe（federation.md §4.5.1）；`peer_role=federation_peer` MUST 通过 §3 节点间认证 + Realm service binding（`sync_endpoints` 或等价 policy facet）中的 `federation_peer` 角色校验，响应携带完整 `frontier_root` / `actor_seq_upper_bounds` / `signature`；`peer_role=anonymous_health` MUST 仅返回 `frontier_root` 摘要，并携带 `cache_expires_at` 或 `retry_after_ms` 之一以约束轮询频率，服务端 MUST 对 `(realm_id, source_prefix)` 限速。普通 `account_client` 维持既有响应。不得泄露不可见 Realm 或 private DID。**`peer_role=anonymous_health` 例外**：不复用 `ck.events.query` 的 `realms[] OR actors[]` 强制规则；响应仅包含 `frontier_root` 摘要 + `cache_expires_at`。 |
| `ck.account.viewer` | 无 | 无 | `principal_id: did`; `primary_handle_claim?: HandleClaim`; `primary_handle_claim_ref?: string`; `handle_claim_digests?: hash[]`; `state: enum(active,soft_logged_out,locked,suspended,deactivated,erasure_pending)`; `devices: object[]`; `profile?: ActorProfile` | `schema_ref=schemas/account-operations.schema.json#/$defs/viewer_response`。`user_session` 必须绑定 principal/device；`primary_handle_claim` 与 `primary_handle_claim_ref` 互斥；不得返回 unsigned bare handle。 |
| `ck.account.subscribe` | 无 | `query.after: cursor`; `query.catchup: boolean=false`; `query.filter: object`; `query.set_presence: enum(online,offline,unavailable)` | NDJSON 流，每行一个 `AccountSubscribeFrame`(`kind: delta / catchup_complete / frontier / heartbeat / dropped / resync_required / unauthorized`,`delta` 含 `cursor` + `realms?` + `to_device?` + `account_data?` + `device_lists?` + `presence?` + `notifications?`;`dropped` / `resync_required` 可含 `reconnect_after_ms`) | `user_session` 必须绑定 principal/device。聚合账号视角 delta streaming push;裸事件读用 `ck.events.query` / `ck.events.subscribe`。`cursor` 是 stream purpose。Initial sync 使用 `catchup=true` 且省略 `after`;baseline 不是完整历史。 |
| `ck.account.update_profile` | `patch: ck.patch.v1` | 无 | `profile: ActorProfile` | schema_ref=schemas/account-operations.schema.json#/$defs/update_profile_response。`schema_ref=schemas/account-operations.schema.json#/$defs/update_profile_request` / `#/$defs/update_profile_response`。允许 path 仅 `display_name` / `avatar_blob_ref` / `profile_fields.<key>`；`bio` 迁移为 `profile_fields.bio`；`avatar_url` 仅可在兼容层转 Blob，不进入协议 body。 |
| `ck.account.cursor_revoke` | `cursor: cursor` | `reason_code: string`; `revoke_scope: enum(this_cursor,same_device,same_session)=this_cursor` | `revoked: boolean`; `expires_at: datetime` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountCursorRevokeRequest / schemas/service-operation-dtos.schema.json#/$defs/AccountCursorRevokeResponse。High-assurance optional profile；撤销 cursor authority，详见 [`client-sync.md` §12.2.1](./client-sync.md)。 |
| `ck.account.describe` | 无 | 无 | `ServiceDescribe` | 私有 frontier 可认证后作为扩展字段返回。 |
| `ck.contact.request` | `target: did`; `requested_scopes: consent_scope[]`; `idempotency_key: string?` | 无 | `request_event_ref: id`; `requester_consent_refs: id[]`; `state: string` | schema_ref=schemas/contact-operations.schema.json#/$defs/contact_request_response。`schema_ref=schemas/contact-operations.schema.json#/$defs/contact_request_request` / `#/$defs/contact_request_response`。requester 只能写自己的 request fact；若请求 scope，必须同步写 requester-side consent grant。 |
| `ck.contact.respond` | `request_id: id`; `requester: did`; `action: enum(accept,reject)` | `granted_scopes: consent_scope[]` | `response_event_ref: id`; `consent_grant_refs: id[]?`; `state: string` | schema_ref=schemas/contact-operations.schema.json#/$defs/contact_respond_response。`schema_ref=schemas/contact-operations.schema.json#/$defs/contact_respond_request` / `#/$defs/contact_respond_response`。只有 target 可 accept/reject；accept 写 target-controlled consent grants，reject 不写 consent。 |
| `ck.contact.list` | 无 | `state: enum?`; `cursor: cursor`; `limit: int` | `contacts: object[]`; `next_cursor: cursor?`; `has_more: boolean` | `schema_ref=schemas/contact-operations.schema.json#/$defs/contact_list_response`。从 contact facts 投影；方向化 scopes 必须区分 `granted_by_me[]`、`granted_to_me[]`、`bidirectional_scopes[]`。 |
| `ck.contact.tombstone` | `contact: did` | `revoke_scopes: consent_scope[]`; `full_peer_revoke: boolean=false` | `tombstone_event_ref: id`; `consent_revoke_refs: id[]`; `state: string` | schema_ref=schemas/contact-operations.schema.json#/$defs/contact_tombstone_response。`schema_ref=schemas/contact-operations.schema.json#/$defs/contact_tombstone_request` / `#/$defs/contact_tombstone_response`。默认 revoke holder 给 peer 的 contact-managed active dots，不误删同 peer 的独立 consent。 |
| `ck.direct_conversation.resolve` | `peer: did` | `create: boolean=false`; `idempotency_key: string?` | `realm_id: id?`; `main_flow_id: id?`; `binding_event_ref: id?`; `state: string`; `created: boolean?` | schema_ref=schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_response。`schema_ref=schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_request` / `#/$defs/direct_conversation_resolve_response`。accepted contact + `direct_message` consent 双 gate；orphan Realm 不得作为默认入口返回。 |
| `ck.ephemeral.send` | body `ck.schema.ephemeral_envelope.v1` | `proof: object`（按 kind 需要）；payload 内 kind-specific 字段 | `accepted: boolean`; `kind: string`; `realm_id: id`; `dispatched_to: int?`; `server_received_at: datetime?` | schema_ref=schemas/ephemeral-envelope.schema.json / schemas/service-operation-dtos.schema.json#/$defs/EphemeralSubmitResponse。broadcast ephemeral channel；只承载 `ck.presence` / `ck.typing` / `ck.receipt.read` / `ck.call.signal`，并分别要求 `ck.presence.broadcast` / `ck.typing.broadcast` / `ck.receipt.broadcast` / `ck.call.signal.send`。MUST NOT 写入 durable Event history，MUST NOT 推进 actor_seq / Realm frontier。拒绝码包括 `ephemeral_kind_not_permitted`、`ephemeral_ttl_out_of_range`、`ephemeral_channel_unavailable`。 |
| `ck.call.media.token_exchange` | body `realm_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `focus_id: string` | `capability_refs: id[]`; `desired_media: object` | `focus_id: string`; `type: string`; `connect_url: string`; `backend_token: string`; `participant_identity: string`; `participant_binding: object`; `expires_at: datetime`; `service_signature: object` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeRequest / schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeResponse。Media service token exchange，等价于 MSC4195 `lk-jwt-service`。TTL `expires_at ≤ 600s`；token issuer DID MUST 出现在 `ck.realm.media_service.service_id` 锚定列表。拒绝码：`focus_mismatch`、`unknown_focus_type`、`token_issuer_unauthorised`、`mls_governance_binding_stale`、`media_plaintext_service_not_authorised`、`capability_denied`、`media_service_foci_required`。详见 [`../crypto-media/media-service-binding.md` §3](../crypto-media/media-service-binding.md)。 |
| `ck.snapshot.head` | `query.realm_id: id` | 无 | `snapshot_ref: id`; `state_digest: string`; `frontier: object`; `event_set_commitment: object`; `created_by: did`; `created_at: datetime`; `authority_binding: object`; `verification_hints: object?`; `signature: signature` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SnapshotHeadResponse。snapshot manifest MUST 签名；signer 必须是 Realm owner、Realm policy 授权的 snapshot issuer 或 witness quorum 成员（`created_by`、`created_at`、`authority_binding` 与签名 transcript 绑定，命名与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 对齐）；high-assurance profile MUST 支持 inclusion / omission challenge hints。 |
| `ck.projection.spaces` | `query.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `spaces: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionSpacesResponse。extension surface；返回 reducer 派生的 Space lifecycle read model，不是真相源；默认不得返回 tombstoned terminal rows。 |
| `ck.projection.flows` | `query.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `flows: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionFlowsResponse。extension surface；返回 reducer 派生的 Flow lifecycle read model，不是真相源；默认不得返回 redacted terminal rows。 |
| `ck.projection.morphs` | `query.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `morphs: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionMorphsResponse。extension surface；返回 reducer 派生的 Morph lifecycle read model，不是真相源；默认不得返回 redacted terminal rows。 |
| `ck.directory.describe` | 无 | 无 | `ServiceDescribe` | `public_metadata`; 可限流。Directory-specific 字段可作为扩展字段返回；详见 `../discovery/discovery-directory.md` §8.9。 |
| `ck.directory.search_realms` | 无 | `query: string`; `organization_did: did`; `source_realm_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/directory-operations.schema.json#/$defs/search_realms_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/search_realms_request` / `#/$defs/search_realms_response`。hidden resource 不泄露存在性；每条 result MUST 含 `as_of`/`source_refs`/`policy_revision`/`stale?`/`divergent?`（discovery-directory.md §9.1）；`join_candidates[]` MAY 省略以避免在搜索结果泄露服务拓扑，客户端 join 前必须 resolve。 |
| `ck.directory.resolve_realm` | 至少一个：`realm_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proofs: proof[]` | `realm_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `join_candidates?: object[]` | schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_realm_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_realm_request` / `#/$defs/resolve_realm_response`。secret/restricted Realm 使用统一 `not_found`；`join_candidates[]` 是规范 join ingress 列表，元素符合 `ck.schema.realm_join_candidate.v1`。支持结构化 candidate 且可披露 join 路由时 MUST 返回；没有 `join_candidates[]` 的响应不能直接用于提交 join material。 |
| `ck.directory.resolve_target` | `address: string` | `requester: did`; `proofs: proof[]`; `token: string` | `target_kind: enum(realm,flow,message)`; `realm_preview: object?`; `object_preview: object?`; `join_rule: string?`; `as_of`/`source_refs`/`join_candidates?` 等 §9.1 通用字段 | schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_target_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_target_request` / `#/$defs/resolve_target_response`。`resolve_realm` 的对象级泛化，realm 解析委托 `resolve_realm` 并继承 candidate routing 语义；`invite` / `preview` token 按 target descriptor + effective link type 校验（[`../discovery/object-addressing.md` §4.2](../discovery/object-addressing.md)）；preview token 只授权 preview policy 允许字段；未授权统一 `not_found`。 |
| `ck.directory.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/directory-operations.schema.json#/$defs/search_organizations_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/search_organizations_request` / `#/$defs/search_organizations_response`。仅公开或授权可发现组织。 |
| `ck.directory.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_organization_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_organization_request` / `#/$defs/resolve_organization_response`。解析组织不等于公开成员或拓扑。 |
| `ck.directory.search_actors` | 无 | `query: string`; `realm_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | schema_ref=schemas/directory-operations.schema.json#/$defs/search_actors_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/search_actors_request` / `#/$defs/search_actors_response`。不得泄露 pairwise/private DID。 |
| `ck.directory.search_users` | `body.query: string` | `body.realm_id: id`; `body.limit: int`; `body.intent: enum(mention,invite,member_add)` | `results: object[]`; `has_more: boolean` | schema_ref=schemas/directory-operations.schema.json#/$defs/search_users_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/search_users_request` / `#/$defs/search_users_response`。mention autocomplete / 成员添加候选；受共同 Realm / directory policy 限制；请求词不得进入 URL、Referer 或未脱敏 access log。结果 MAY 包含 handle preview，但未授权时不得披露 `subject` DID 或 `member_delivery_binding`。 |
| `ck.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string`; `intent: enum(lookup,mention,invite,member_add)`; `realm_id: id`; `requester: did`; `proofs: proof[]` | `did: did`; `subject: did`; `handle: string`; `verified: boolean`; `claims: object[]?`; `member_delivery_binding: object?`; `source_refs: id[]?`; `expires_at: timestamp?` | schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_handle_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/resolve_handle_request` / `#/$defs/resolve_handle_response`。受限 / 组织 handle 需要 presentation；响应 `handle` 是 canonical `user:domain`；投递服务 DID 只通过 `member_delivery_binding.recipient_service_did` 返回。 |
| `ck.directory.list_handles_for_subject` | `subject: did` | `realm_id: id`; `intent: enum(lookup,mention,invite,member_add)`; `requester: did`; `proof_challenge: string`; `proofs: proof[]`; `as_of: datetime`; `cursor: cursor`; `limit: int` | `subject: did`; `claims: object[]`; `primary_handle: string?`; `as_of: datetime`; `next_cursor: cursor?`; `has_more: boolean` | `schema_ref=schemas/directory-operations.schema.json#/$defs/list_handles_for_subject_request` / `schemas/list-handles-for-subject-response.schema.json`。holder/principal DID + context → current visible claims；`subject` 不是 Realm `actor_id`。必须按 disclosure policy、issuer trust、audience 和 Realm intent 过滤；不能因共同 Realm 单独披露受限 handle。 |
| `ck.directory.private_contact_discovery` | `requester: did`; `contacts: object[]` | `proofs: proof[]`; `privacy_profile: string`; `padding: object` | `matches: object[]`; `proofs: object[]?`; `retry_after_ms: int?` | schema_ref=schemas/directory-operations.schema.json#/$defs/private_contact_discovery_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/private_contact_discovery_request` / `#/$defs/private_contact_discovery_response`。MUST 使用 blinded / padded identifier batch；响应 MAY 含最小 invite/consent handoff stub，但不得返回 contact request handoff token、原始 connection identifier、完整 profile、成员列表、Realm membership 或关系图谱。 |
| `ck.directory.announce` | `resource_kind: enum(realm,organization,actor,applet,handle)`; `resource_id: id\|did\|handle`; `discovery_state: object`; `source_refs: id[]`; `as_of: timestamp`; `principal_server_did: did` | `ttl_seconds: int`; `supersedes_announce_id: ck:announce:<uuidv7>` | `announce_id: ck:announce:<uuidv7>`; `indexed_at: timestamp`; `effective_ttl_seconds: int`; `next_revalidation_after: timestamp`; `warnings: string[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryAnnounceRequest / schemas/service-operation-dtos.schema.json#/$defs/DirectoryAnnounceResponse。资源 → Directory 的签名 ingest；`announce_id` 是 Directory-local typed ID，不是跨 Directory 全局对象权威；MUST 验签 + 双向 opt-in；详见 `../discovery/discovery-directory.md` §8.3 / §8.5 / §8.10。 |
| `ck.directory.withdraw` | `resource_id: id\|did\|handle`; `governance_proof: object`; `reason: string` | `effective_at: timestamp` | `withdrawal_ref: string`; `acked_at: timestamp` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryWithdrawRequest / schemas/service-operation-dtos.schema.json#/$defs/DirectoryWithdrawResponse。资源主动撤销 opt-in；`withdrawal_ref` 是 Directory-local audit reference，不是注册 typed ID。Directory MUST 在 ≤ 1h 内停止披露；详见 `../discovery/discovery-directory.md` §8.7。 |
| `ck.directory.push.register` | `subscriber_did: did`; `resource_filter: object`; `webhook_endpoint: url` | `secret: string`; `expires_at: timestamp` | `subscription_id: id`; `effective_at: timestamp` | schema_ref=schemas/directory-operations.schema.json#/$defs/push_register_response。`schema_ref=schemas/directory-operations.schema.json#/$defs/push_register_request` / `#/$defs/push_register_response`。push webhook 注册；仅作为 pull 模式优化，不替代 freshness 协议（§8.6）。 |
| `ck.blob.upload` | `content: binary`; `size_bytes: int` | `realm_id: id`; `content_digest: string`; `media_type: string`; `filename: string`; `purpose: string` | `blob_ref: string`; `size_bytes: int`; `media_type: string?`; `content_digest: string`; `upload_receipt: object?` | schema_ref=schemas/blob-operations.schema.json#/$defs/upload_response。`schema_ref=schemas/blob-operations.schema.json#/$defs/upload_request` / `#/$defs/upload_response`。upload capability、quota、media policy；`content` part Content-Type 缺省为 `application/octet-stream`。`size_bytes` 可由客户端声明，也可由服务端在响应中按实际接收字节计算后返回；二者不一致时 MUST `digest_mismatch` 或 `invalid_param`。 |
| `ck.blob.head` | `query.blob_ref: string` | `header.Authorization: token` 或 `query.presign: token`（与 `Authorization` 互斥）；`header.X-Cokret-Wait-For: cursor` | headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?` | Header auth 路径必须验证 actor/device/Realm/purpose/expiry；presign 路径验证 envelope、TTL、scope、Realm/blob 状态和 issuer service DID，但不能验证当前请求者 audience。不得通过 header 泄露不可见资源。`presign` 形态见 `ck.blob.presign`。 |
| `ck.blob.get` | `query.blob_ref: string` | `header.Authorization: token` 或 `query.presign: token`（与 `Authorization` 互斥）；`header.Range: string`; `header.X-Cokret-Wait-For: cursor` | bytes；headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?`, `Content-Range?`, `Location?` | Header auth 路径必须验证 actor/device/Realm/purpose/expiry；presign 路径只接受 `ck.blob.presign` 发出的短 TTL 单对象 bearer token，验证 envelope、TTL、scope、Realm/blob 状态和 issuer service DID。Range 和 redirect 不得泄露不可见资源。两者同时出现 MUST 拒绝。详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `ck.blob.presign` | `blob_ref: string` | `max_age_seconds: int (<=3600)`; `purpose: enum(media_inline, thumbnail, download)` | `url: uri`; `expires_at: timestamp`; `purpose: string` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/BlobPresignRequest / schemas/service-operation-dtos.schema.json#/$defs/BlobPresignResponse。为单个 blob 签发短 TTL（默认 ≤ 5 min，硬上限 ≤ 1h）、单对象、只读、可撤销的 pre-signed URL。**仅用于让浏览器 `<img src>` / `<video src>` 等无法附 Authorization header 的原生标签渲染受保护媒体**。E2EE 附件 ciphertext MUST NOT 通过此机制下发。受 `ck.blob.presign` capability 控制；TTL / scope / purpose 由 grant constraint 收紧。详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `ck.push.register_device` | `device_id: id`; `push_gateway: url`; `push_key: string` | `platform: string`; `app_id: string`; `display_name: string`; `recipient_service_did: did` | `ok: boolean`; `registration_id: id?`; `expires_at: datetime?` | schema_ref=schemas/push-operations.schema.json#/$defs/register_device_response。`schema_ref=schemas/push-operations.schema.json#/$defs/register_device_request` / `#/$defs/register_device_response`。只能注册当前 principal/device，且 registration 作用域绑定当前 Principal Server service DID；如显式携带 `recipient_service_did`，MUST 等于目标服务 DID。 |
| `ck.push.unregister_device` | `device_id: id` | `push_key: string`; `app_id: string` | `ok: boolean` | schema_ref=schemas/push-operations.schema.json#/$defs/unregister_device_response。`schema_ref=schemas/push-operations.schema.json#/$defs/unregister_device_request` / `#/$defs/unregister_device_response`。same device/principal 或 device revocation path。 |
| `ck.push.notify` | `notification.push_target_id: string`; `notification.wakeup_kind: enum(message,mention,reaction,call_invite,generic)`; `notification.devices: object[]` | `notification.push_hint: string`; `notification.counts: object`; visible profile only: `notification.event_id: id`, `notification.realm_id: id`, `notification.sender_actor_id: did` | `rejected: object[]` | schema_ref=schemas/push-operations.schema.json#/$defs/notify_response。`schema_ref=schemas/push-operations.schema.json#/$defs/notify_request` / `#/$defs/notify_response`。来自授权 Sync 或 notification service；默认 blind wakeup 请求 MUST NOT 携带 event / realm / sender 字段。visible 字段只在 `ck.profile.push_gateway.visible_notification.v1` 且 Realm policy + device opt-in + UI disclosure 通过时允许。`service_signature` 的 transcript MUST 绑定 `push_target_id` 所对应 registration 的 registration service DID（即 `ck.push.register_device` 注册作用域绑定的 Principal Server service DID）；且发起 notify 的来源服务 DID MUST 出现在该设备 registration 的 `recipient_service_did` 投递链内。push gateway MUST 拒绝来源服务不在目标设备投递链内、或 transcript 未绑定该 registration service DID 的请求（`capability_denied`），以阻止跨 Realm / 跨 Principal Server 的 push 注入。 |
| `ck.device_messages.put` | `header.Idempotency-Key: string`; `messages: object` | 每个 target 必须含 `kind`、`content`、`expires_at` | `ok: boolean`; `delivered: object?`; `unknown_devices: object?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesPutRequest / schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesPutResponse。`(sender, Idempotency-Key)` 幂等；目标必须是授权 device；过期或超过 TTL 上限的消息必须拒绝或逐项 reject。 |
| `ck.device_messages.get` | 无 | `query.from: cursor`; `query.limit: int` | `messages: object[]`; `next_cursor: cursor?`; `has_more: boolean`; `limited: boolean?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesGetResponse。响应字段 `messages[]` 含 `DeviceMessageEnvelope` 对象, 不是 Event Envelope; 只返回当前 device 队列。 |
| `ck.keys.upload` | `device_id: id`; `device_signature: signature` | `one_time_keys: object`; `fallback_keys: object` | `one_time_key_counts: object`; `fallback_keys: object?` | schema_ref=schemas/keys-operations.schema.json#/$defs/upload_response。`schema_ref=schemas/keys-operations.schema.json#/$defs/upload_request` / `#/$defs/upload_response`。key 必须链接 self-signing / principal key。 |
| `ck.keys.query` | `device_keys: object` | `timeout_ms: int` | `device_keys: object`; `failures: object[]?` | schema_ref=schemas/keys-operations.schema.json#/$defs/query_response。`schema_ref=schemas/keys-operations.schema.json#/$defs/query_request` / `#/$defs/query_response`。查询范围可按关系 / Realm 限制。 |
| `ck.keys.claim` | `one_time_keys: object` | 无 | `one_time_keys: object`; `failures: object[]?` | schema_ref=schemas/keys-operations.schema.json#/$defs/claim_response。`schema_ref=schemas/keys-operations.schema.json#/$defs/claim_request` / `#/$defs/claim_response`。one-time key MUST 原子消费。 |
| `ck.keys.keypackages.upload` | `principal_id: did`; `device_id: id`; `key_packages: object[]`; `device_signature: signature` | `expires_at: datetime`; `flow_id: id`; `mls_group_id: string` | `accepted: int`; `rejected: object[]?`; `key_package_refs: id[]?`; `available_count: int?` | schema_ref=schemas/keypackage-operations.schema.json#/$defs/upload_response。`schema_ref=schemas/keypackage-operations.schema.json#/$defs/upload_request` / `#/$defs/upload_response`。MLS KeyPackage MUST 绑定 device key、credential 和 supported cipher suites；服务 SHOULD 返回该 device 当前可见 `available_count` 以支持低水位补充。 |
| `ck.keys.keypackages.claim` | `target_principal_id: did`; `intended_realm_id: id`; `requester: did`; `required_capabilities: string[]`; `claim_nonce: string`; `expires_at: datetime` | `target_device_ids: id[]`; `minimal_metadata_allowed: boolean`; `timeout_ms: int`; `flow_id: id`; `mls_group_id: string`; `proofs: proof[]` | `claims: object[]`; `failures: object[]?`; `available_count: int?` | schema_ref=schemas/keypackage-operations.schema.json#/$defs/claim_response。`schema_ref=schemas/keypackage-operations.schema.json#/$defs/claim_request` / `#/$defs/claim_response`。KeyPackage claim MUST 原子保留，重复 claim 不得返回同一 one-time package；claimed 过期不得回到 published，claim path 按 `(requester_service_did, target_principal_id)` 限速并做反枚举。 |
| `ck.keys.keypackages.consume` | `key_package_refs: id[]`; `consumer_device_id: id`; `signature: signature` | `claim_ids: string[]`; `welcome_ref: ref`; `realm_id: id`; `flow_id: id`; `mls_group_id: string`; `epoch: int` | `consumed: id[]`; `failures: object[]?` | schema_ref=schemas/keypackage-operations.schema.json#/$defs/consume_response。`schema_ref=schemas/keypackage-operations.schema.json#/$defs/consume_request` / `#/$defs/consume_response`。consume MUST 校验 claim holder、epoch 和 package freshness。 |
| `ck.keys.keypackages.revoke` | `key_package_refs: id[]`; `device_id: id`; `signature: signature` | `reason: string` | `revoked: id[]`; `failures: object[]?` | schema_ref=schemas/keypackage-operations.schema.json#/$defs/revoke_response。`schema_ref=schemas/keypackage-operations.schema.json#/$defs/revoke_request` / `#/$defs/revoke_response`。只能由 owning device、principal 或授权 admin 撤销。 |
| `ck.keys.backups.put` | `path.backup_id: id`; `backup: object` | `idempotency_key: string` | `status: enum(accepted,duplicate)`; `backup_id: id`; `ciphertext_digest: string` | `schema_ref=schemas/key-backup.schema.json` / `schemas/keys-operations.schema.json#/$defs/backups_put_response`。path/body backup id 必须一致；服务端不得解密。 |
| `ck.keys.backups.list` | 无 | `query.series_id: id?`; `query.backup_class: enum(ck.schema.key_backup.v1.backup_class)`; `query.cursor: cursor`; `query.limit: int` | `backups: object[]`; `next_cursor: cursor?`; `has_more: boolean` | `schema_ref=schemas/keys-operations.schema.json#/$defs/backups_list_response`。仅返回调用方可见的最小 metadata；不得泄露无关 Realm / group membership。 |
| `ck.keys.backups.get` | `path.backup_id: id` | 无 | `backup: object` | `schema_ref=schemas/key-backup.schema.json`。只返回同 principal 授权 device、recovery policy 或授权恢复服务可见的 encrypted backup object。 |
| `ck.keys.backups.delete` | `path.backup_id: id`; `proof: proof` | `reason: string` | `deleted: boolean`; `backup_id: id?` | schema_ref=schemas/keys-operations.schema.json#/$defs/backups_delete_response。`schema_ref=schemas/keys-operations.schema.json#/$defs/backups_delete_request` / `#/$defs/backups_delete_response`。高风险删除；不等于 device revoke、DID recovery 或 MLS epoch rotation。 |
| `ck.authz.get_effective_grants` | `query.realm_id: id`; `query.subject: did` | `query.at: string` | `grants: object[]`; `state_digest: string?`; `evaluated_at: datetime` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/GrantListResponse。subject 本人、Realm admin 或授权服务。 |
| `ck.authz.get_invites` | `query.subject: did 或 string` | `query.realm_id: id`; `query.cursor: cursor` | `invites: object[]`; `next_cursor: cursor?`; `has_more: boolean` | `schema_ref=schemas/authz-operations.schema.json#/$defs/get_invites_response`。secret invite 不可枚举。 |
| `ck.authz.check` | `actor_id: did`; `action: string` | `resource: object`; `context: object` | `decision: enum(allow,deny,quarantine,require_review,soft_fail)`; `matched_grants: object[]?`; `applied_constraints: object[]?`; `policy_results: object[]?`; `missing_proofs: object[]?`; `frontier: object?`; `freshness_state: enum(fresh,stale,unknown)?`; `last_known_frontier_age_ms: int?`; `anchorer_status: enum(fresh,lagging,unreachable,unknown)?`; `cache_expires_at: datetime?`; `reason_code: string?`; `retry_after_ms: int?`; `obligations: object[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthzCheckRequest / schemas/service-operation-dtos.schema.json#/$defs/AuthzCheckResponse。Policy allow 不创建 capability；客户端不得把非标准 `allowed` 字段作为规范字段；`freshness_state=stale/unknown` 且高风险动作时 MUST fail closed，reason_code 使用 `revocation_freshness_unknown`。 |
| `ck.policy.check` | `request_id: string`; `realm_id: id`; `request_canonical_digest: string`; `action: string`; `actor: did`; `source: object` | `device_id: id`; `event_preview: object`; `auth_context: object` | `request_id: string`; `bound_to: object`; `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `reason_code: string`; `expires_at: datetime`; `auth_state_digest: string`; `policy_frontier_digest: string`; `membership_frontier_digest: string`; `obligations: object[]?`; `signature: signature` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/PolicyCheckRequest / schemas/service-operation-dtos.schema.json#/$defs/PolicyCheckResponse。只接收最小披露字段；decision 按 hash/cache frontier 绑定。Canonical HTTP 路径 `POST /_cokret/self/policy/check`。 |
| `ck.moderation.report` | `realm_id: id`; `target_ref: id`; `report_reason_code: enum`; `reporter: did` | `description: string`; `evidence_refs: id[]` | `report_id: id`; `status: string`; `routed_to: did[]?` | schema_ref=schemas/moderation-report.schema.json / schemas/service-operation-dtos.schema.json#/$defs/ModerationReportResponse。reporter 必须可见 target；只对 moderators 可见。 |
| `ck.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | `schema_ref=schemas/applet-edge-operations.schema.json#/$defs/ping_response`。不得泄露 private namespace。 |
| `ck.applet.describe` | 无 | 无 | `ServiceDescribe` | public mode 只返回公开 capabilities；applet-specific 字段作为扩展字段返回。 |
| `ck.applet.install.preview` | `applet_package: object`; `effective_scope: object`; `approval_request: object` | 无 | `InstallPlan` | `schema_ref=schemas/applet-install-operations.schema.json#/$defs/preview_request` / `schemas/applet-install-plan.schema.json`。self/admin aggregate operation；只读预览，不写 Realm history；返回 canonical `plan_digest`。 |
| `ck.applet.install` | `header.Idempotency-Key: string`; `plan_digest: hash`; `applet_package: object`; `effective_scope: object`; `approved_scopes: object[]` | `actor_policy: object`; `e2ee_policy: object`; `widget_policy: object` | `ok: boolean`; `install_id: string`; `registration_event_ref: ref?`; `registration_epoch: hash`; `bot_actor_id: did`; `capability_grant_refs: ref[]`; `membership_event_refs: ref[]`; `e2ee_authorization_refs: ref[]`; `widget_policy_ref: ref?`; `effective_status: enum(installed,partially_installed,rejected)`; `rejected: object[]` | schema_ref=schemas/applet-install-operations.schema.json#/$defs/install_response。`schema_ref=schemas/applet-install-operations.schema.json#/$defs/install_request` / `#/$defs/install_response`。self/admin aggregate operation；MUST 重新计算 plan，`plan_digest` 不匹配返回 `applet_install_plan_mismatch`；不创建 durable `ck.applet.install` event。 |
| `ck.applet.revoke` | `header.Idempotency-Key: string`; `path.applet_id: id`; `effective_scope: object`; `reason_code: string`; `revoke_mode: enum(revoke_all,revoke_runtime_only,revoke_widget_only,revoke_delegated_sessions)` | 无 | `ok: boolean`; `revoked_refs: ref[]?`; `rejected: object[]?` | schema_ref=schemas/applet-install-operations.schema.json#/$defs/revoke_response。`schema_ref=schemas/applet-install-operations.schema.json#/$defs/revoke_request` / `#/$defs/revoke_response`。self/admin aggregate operation；撤销 bound grants / widget tokens / delegated sessions；revoke 后未来写入返回 `applet_revoked` 或更细 reason。 |
| `ck.applet.transaction` | `header.Idempotency-Key: string`; `source_service_did: did`; `events: EventEnvelope[]` | `ephemeral: EphemeralEnvelope[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | schema_ref=schemas/applet-edge-operations.schema.json#/$defs/transaction_response。`schema_ref=schemas/applet-edge-operations.schema.json#/$defs/transaction_request` / `#/$defs/transaction_response`。Applet 必须验证 event signature、namespace、capability；按 `(source_service_did, Idempotency-Key)` 幂等。 |
| `ck.applet.resolve_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | `schema_ref=schemas/applet-edge-operations.schema.json#/$defs/resolve_actor_response`。actor_id 必须命中 namespace。 |
| `ck.applet.resolve_realm` | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | `schema_ref=schemas/applet-edge-operations.schema.json#/$defs/resolve_realm_response`。必须命中 portal namespace 或授权查询。 |
| `ck.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_types: object`; `instances: object[]?` | `schema_ref=schemas/applet-edge-operations.schema.json#/$defs/protocol_metadata_response`。instance list 可要求授权。 |
| `ck.applet.third_party_users` | `query.protocol: string`; `query.external_id: string` | `query.instance_id: string` | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | `schema_ref=schemas/applet-edge-operations.schema.json#/$defs/third_party_user_response`。查询字段必须在 registration namespace 内。 |
| `ck.applet.third_party_locations` | `query.protocol: string`; `query.external_id: string` | `query.instance_id: string` | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | `schema_ref=schemas/applet-edge-operations.schema.json#/$defs/third_party_location_response`。查询字段必须在 portal namespace 内。 |
| `ck.mimi.provider_directory` | 无 | `query.provider_id: string`; `query.features: string[]` | `providers: object[]`; `features: object`; `expires_at: datetime?` | schema_ref=schemas/mimi-interop.schema.json。只返回公开 provider capability，不泄露 Realm membership。 |
| `ck.mimi.key_material` | `requester: did`; `flow_id: id`; `device_id: id` | `mimi_room_uri: string`; `realm_id: id`; `mls_group_id: string`; `epoch: int`; `proofs: proof[]` | `key_packages: object[]?`; `group_info: object?`; `failures: object[]?`; `signature: signature?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/key_material_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/key_material_request` / `#/$defs/key_material_response`。必须存在 accepted `ck.mimi.room_binding` 且 requester 有对应 room / device 权限。 |
| `ck.mimi.room_update` | `path.flow_id: id`; `mls_group_id: string`; `update: object` | `epoch: int`; `confirmed_transcript_hash: string`; `sender_actor_id: did` | `accepted: boolean`; `room_state_ref: id?`; `rejected: object[]?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/room_update_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/room_update_request` / `#/$defs/room_update_response`。更新必须映射到 Cokret Flow discussion track / Realm policy 授权范围内；`confirmed_transcript_hash` 沿用 MLS/MIMI 外部标准字段名。 |
| `ck.mimi.notify` | `path.flow_id: id`; `notification: object` | `origin_provider: did`; `routing: object` | `accepted: boolean`; `retry_after_ms: int?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/notify_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/notify_request` / `#/$defs/notify_response`。只可传递最小 fanout / delivery signal，不得携带未授权明文。 |
| `ck.mimi.submit_message` | `path.flow_id: id`; `sender_actor_id: did`; `device_id: id`; `ciphertext: object` | `mls_group_id: string`; `epoch: int`; `associated_data: object` | `event_ref: id?`; `delivery: object`; `rejected: object[]?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/submit_message_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/submit_message_request` / `#/$defs/submit_message_response`。必须校验 MLS epoch、有效 discussion access、capability 和 `ck.mimi.room_binding`。 |
| `ck.mimi.group_info` | `path.flow_id: id` | `query.epoch: int`; `query.include_proof: boolean` | `group_info: object`; `room_binding_ref: id?`; `proofs: proof[]?` | `schema_ref=schemas/mimi-operations.schema.json#/$defs/group_info_response`。只能返回 requester 授权可见的 MLS groupInfo / room projection。 |
| `ck.mimi.request_consent` | `requester: did`; `target: object`; `purpose: enum(invite,direct_message,voice_call,video_call,presence,any)` | `flow_id: id`; `expires_at: datetime`; `proofs: proof[]` | `consent_id: id`; `status: string`; `challenge: string?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/request_consent_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/request_consent_request` / `#/$defs/request_consent_response`。consent 只表达联系 / invite 意图，不授予 Realm read/write。 |
| `ck.mimi.update_consent` | `consent_id: id`; `decision: enum(accept,deny,revoke)`; `actor: did`; `signature: signature` | `reason: string`; `expires_at: datetime` | `status: string`; `updated_at: datetime`; `event_ref: id?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/update_consent_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/update_consent_request` / `#/$defs/update_consent_response`。必须绑定原 request、target identity proof 和 replay protection。 |
| `ck.mimi.identifier_query` | `identifiers: object[]` | `requester: did`; `privacy_profile: string`; `proofs: proof[]` | `results: object[]`; `proofs: proof[]?`; `has_more: boolean` | schema_ref=schemas/mimi-operations.schema.json#/$defs/identifier_query_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/identifier_query_request` / `#/$defs/identifier_query_response`。SHOULD 使用 private contact discovery；不得返回原始通讯录或完整关系图谱。 |
| `ck.mimi.report_abuse` | `flow_id: id`; `target_ref: string`; `reporter: did`; `abuse_reason_code: string` | `evidence_package: object`; `franking_proof: object`; `description: string` | `report_id: id`; `status: string`; `routed_to: did[]?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/report_abuse_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/report_abuse_request` / `#/$defs/report_abuse_response`。E2EE report 只能向授权 moderation recipient 解密 evidence。 |
| `ck.mimi.proxy_download` | `asset_ref: string`; `requester: did` | `flow_id: id`; `ohttp_context: object`; `range: string` | `download_ref: string`; `headers: object?`; `expires_at: datetime?` | schema_ref=schemas/mimi-operations.schema.json#/$defs/proxy_download_response。`schema_ref=schemas/mimi-operations.schema.json#/$defs/proxy_download_request` / `#/$defs/proxy_download_response`。当 Realm asset privacy policy 要求 proxy/OHTTP 时不得返回 direct object-store URL。 |
| `ck.account.register` | `principal_id: did` | `display_name: string`; `device_id: id`; `proof: AccountLifecycleProof` | `principal_id: did`; `state: enum(active,soft_logged_out,locked,suspended,deactivated,erasure_pending)`; `devices: object[]`; `primary_handle_claim?: HandleClaim`; `primary_handle_claim_ref?: string`; `handle_claim_digests?: hash[]`; `profile?: ActorProfile` | schema_ref=schemas/account-operations.schema.json#/$defs/account_response。`schema_ref=schemas/account-operations.schema.json#/$defs/register_request` / `#/$defs/account_response`。wire break:旧 `did` 改 `principal_id`，旧 `handle` 字段删除；handle 只能经 signed claim / digest / ref。 |
| `ck.account.issue_session_grant` | `principal_id: did`; `proof: SessionGrantRequestProof` | `device_id: id`; `requested_scope: string[]` | `principal_id: did`; `device_id: id?`; `session_grant: string`; `expires_at: datetime`; `granted_scope: string[]?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantRequest / schemas/service-operation-dtos.schema.json#/$defs/SessionGrantResponse。`proof` MUST 绑定 `proof_kind`、`challenge`、`request_canonical_digest`、`audience`、`expires_at?` 与签名；必须绑定 principal、device key、audience 和最小 scope。 |
| `ck.account.session_revoke` | 无 | `target_grant_id: id`; `target_device_id: id`; `all_sessions: true`; `proof: AccountLifecycleProof` | `revoked_count: int`; `revoked_grant_ids?: id[]` | schema_ref=schemas/account-operations.schema.json#/$defs/session_revoke_response。`schema_ref=schemas/account-operations.schema.json#/$defs/session_revoke_request` / `#/$defs/session_revoke_response`。空 body 撤当前 session；三个 selector 互斥；跨 grant/device/all_sessions 需要 fresh proof；不撤 device authorization。 |
| `ck.account.device_pair` | `pairing_code: string`; `new_device_pubkey: object`; `challenge_signature: signature` | `display_name: string`; `device_metadata: object` | `device_id: id`; `authorized_event_ref: ref`; `device_grant: object?`; `key_backup_hint: object?` | schema_ref=schemas/agent-operations.schema.json#/$defs/device_pair_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/device_pair_request` / `#/$defs/device_pair_response`。pairing code / proof 必须短期有效、一次性使用，并绑定目标 Auth Server audience / origin / request canonical hash；服务端 MUST 按 principal、授权源设备和目标 origin 限速。 |
| `ck.account.agent_key_pair` | `agent_principal_id: did`; `verification_method: did_url`; `public_key: object`; `proof_of_possession: proof` | `runtime_attestation: object` | `ok: boolean`; `authorized_event_ref: ref` | schema_ref=schemas/agent-operations.schema.json#/$defs/agent_key_pair_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/agent_key_pair_request` / `#/$defs/agent_key_pair_response`。`verification_method` 的 DID 部分 MUST 与 `agent_principal_id` bit-identical。 |
| `ck.agent.provision` | 无 | `display_name: string`; `requested_scope: object`; `accountability: object`; `pairing_ttl_ms: int` | `agent_principal_id: did`; `pairing_request_id: string`; `pairing_code: string?`; `expires_at: datetime` | schema_ref=schemas/agent-operations.schema.json#/$defs/provision_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/provision_request` / `#/$defs/provision_response`。编排 Actor Profile、accountability_grant、初始 capability grant 与 runtime pairing request；不创建 durable `ck.agent.provision` event。 |
| `ck.agent.list` | 无 | `query.cursor: cursor`; `query.limit: int`; `query.state: string` | `agents: object[]`; `next_cursor: cursor?`; `has_more: boolean` | `schema_ref=schemas/agent-operations.schema.json#/$defs/list_response`。只列出调用方可管理的 native personal agent。 |
| `ck.agent.get` | `path.agent_principal_id: did` | 无 | `agent: object`; `status: enum(pending_runtime_key,active,pairing_expired,paused,deactivated)`; `grants: object[]?`; `key_state: object?` | `schema_ref=schemas/agent-operations.schema.json#/$defs/get_response`。只返回 controller 或 policy-authorized admin 可见的 agent projection。 |
| `ck.agent.pause` | `path.agent_principal_id: did` | `reason: string` | `ok: boolean`; `status: enum(paused)` | schema_ref=schemas/agent-operations.schema.json#/$defs/lifecycle_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/pause_request` / `#/$defs/lifecycle_response`。暂停 agent 并拒绝新 agent session grant。 |
| `ck.agent.resume` | `path.agent_principal_id: did` | `sidecar_exposure_ack: object` | `ok: boolean`; `status: enum(active)` | schema_ref=schemas/agent-operations.schema.json#/$defs/lifecycle_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/resume_request` / `#/$defs/lifecycle_response`。必须重新校验 controller/agent/key/grant freshness；新增 sidecar exposure 时要求显式确认。 |
| `ck.agent.deactivate` | `path.agent_principal_id: did` | `reason: string` | `ok: boolean`; `status: enum(deactivated)` | schema_ref=schemas/agent-operations.schema.json#/$defs/lifecycle_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/deactivate_request` / `#/$defs/lifecycle_response`。terminal transition；fan-out agent key revoke、capability revoke 与 runtime endpoint revoke。 |
| `ck.agent.rotate_key` | `path.agent_principal_id: did`; `replacement_key: object`; `proof_of_possession: proof` | 无 | `ok: boolean`; `authorized_event_ref: ref` | schema_ref=schemas/agent-operations.schema.json#/$defs/rotate_key_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/rotate_key_request` / `#/$defs/rotate_key_response`。不得扩大 agent key scope 或延长有效期。 |
| `ck.agent.grant.attach` | `path.agent_principal_id: did`; `grant: object` | 无 | `ok: boolean`; `grant_id: id` | schema_ref=schemas/agent-operations.schema.json#/$defs/grant_attach_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/grant_attach_request` / `#/$defs/grant_attach_response`。grant subject 必须是该 agent principal，且不得超过 controller 可委托范围。 |
| `ck.agent.grant.detach` | `path.agent_principal_id: did`; `path.grant_id: id` | 无 | `ok: boolean`; `revoked_at: datetime` | `schema_ref=schemas/agent-operations.schema.json#/$defs/grant_detach_response`。撤销或解绑 agent grant，后续 agent action proof fail closed。 |
| `ck.agent.sidecar_thread.ensure` | `realm_id: id`; `controller_principal_id: did`; `agent_principal_id: did` | 无 | `ok: boolean`; `private_circle_id: id`; `private_flow_id: id`; `private_relation_id: id`; `pending_member_reconciliation: object[]?` | schema_ref=schemas/agent-operations.schema.json#/$defs/sidecar_thread_ensure_response。`schema_ref=schemas/agent-operations.schema.json#/$defs/sidecar_thread_ensure_request` / `#/$defs/sidecar_thread_ensure_response`。idempotent ensure；在 eligibility、Circle membership active，且 MLS-backed Circle 的 MLS membership active 后才 fanout。 |
| `ck.account.oidc_callback` | `state: string`; `code: string` | `nonce: string`; `redirect_uri: url` | `principal_id: did?`; `session: SessionGrantResponse?`; `redirect_url: url?` | schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountOidcCallbackRequest / schemas/service-operation-dtos.schema.json#/$defs/AccountOidcCallbackResponse。MUST 校验 state、nonce、服务端配置的 issuer binding 和 DID/account linkage。 |
| `ck.media.ice_config` | `realm_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `mode: enum(p2p,sfu,turn)` | 无 | `ttl_seconds: int`; `refresh_lead_seconds: int`; `issued_at: datetime`; `issued_at_bucket: datetime`; `bucket_seconds: int`; `ice_servers: object[]`; `constraints: object?`; `signature: signature` | `schema_ref=schemas/media-operations.schema.json#/$defs/ice_config_request` / `schemas/ice-config-response.schema.json`。actor 必须有 call/media capability；Realtime Media Server 必须被委托；TURN pseudonym bucket 固定 300s。 |

## 3. Events API

### 3.1 提交 Event

```text
POST /_cokret/self/events
```

单事件提交 request body 直接是 `EventSubmitEnvelope` 对象（**不**用任何 `{event: ...}` wrapper）。批量提交 request body 是 `{events: EventSubmitEnvelope[]}`。服务接受后返回的 get/query/subscribe 路径暴露 accepted `EventEnvelope`；submit input 与 accepted/read envelope 不得混用。

单事件请求示例（非完整 schema）：

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 42,
  "kind": "ck.flow.update",
  "created_at": "2026-04-22T08:30:00Z",
  "hlc": "01970e589d21-0007-a13f9c2e",
  "prev_refs": [
    "ck:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "ck:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "preconditions": [],
  "effects": [
    {
      "cell": "ck:cell:ck.component.flow.metadata.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "op": {
        "kind": "set",
        "value": {
          "metadata.fields.review_status": "approved"
        }
      }
    }
  ],
  "anchor_ref": "ck:anchor:sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "payload": {
    "flow_id": "ck:flow:019640c6-8000-7000-8000-000000000000",
    "patch": { "metadata.fields.review_status": "approved" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#device-1",
      "event_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
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
    { "event_id": "ck:event:...", "realm_id": "ck:realm:...", "actor_id": "did:web:...", "actor_seq": 42, "kind": "ck.flow.update", "...": "..." },
    { "event_id": "ck:event:...", "realm_id": "ck:realm:...", "actor_id": "did:web:...", "actor_seq": 43, "kind": "ck.message.create", "...": "..." }
  ]
}
```

响应示例（非完整 schema）：

```json
{
  "status": "accepted",
  "accepted": ["ck:event:019640ed-8000-7000-8000-000000000000"],
  "actor_frontier": {
    "actor_id": "did:web:alice.example.com",
    "actor_seq": 42,
    "event_id": "ck:event:019640ed-8000-7000-8000-000000000000"
  },
  "cursor": "ck:cursor:<opaque-valid-barrier-cursor>"
}
```

若非 reducer 写入的乐观 `expected_frontier` 校验失败，返回 `409 cas_conflict`。Reducer-input Move 的 cell precondition / `head_eq` 失败按对应 reducer 语义返回 `failed_precondition`（例如 `ck.flow.move` / `ck.flow.reorder` 的 `expected_position` 不匹配），不得把这类失败旁路成 `cas_conflict`。协议级写入单元是 signed Event Envelope；实现 MAY 在 SDK 或本地接口中接受 operation builder，但在进入网络传播、同步或审计前 MUST 转换为 Event Envelope。接收方不得要求 Event 先归属某个 batch receipt、checkpoint 或 predecessor commit 才承认其 canonical history 地位。

`events[]` 批量提交按数组顺序处理。已接受的前序项可以被同批后续项用于解析 bytes、Event ID、actor chain、`prev_refs` 或显式 payload-level causal reference；但**授权可见性不因此提前生效**。`refs[role=authorized_by]` 只有在被引用的 grant / authority 已存在于该后续 Event 的 `anchor_ref` pre-state 中时，才能参与授权判定。同批前序 Event 若创建、delegate、恢复或扩权某个 grant，依赖该 grant 的后续 Event MUST 等到后续 Anchor 覆盖该 grant 后再提交，或被当前批次拒绝/隔离；`refs(role="after")` 只表达后续 Anchor 的排序约束，不让同一 Anchor 内的新 effect 被读取为授权状态。后续项不得引用同批中尚未处理、已拒绝或隔离的 Event 作为已接受事实。单项失败不回滚整批，响应必须把成功项列入 `accepted[]`，幂等重复列入 `duplicate[]`，失败项列入 `rejected[]` 或等价隔离结果。

**`status` 判别规则（normative）**：响应顶层 `status` 字段 MUST 按下述规则唯一确定，便于客户端不需要逐项扫描即可判断处理结果：

- `status=accepted` **仅当** `rejected[]` 为 empty **且** `quarantine[]` 为 empty（所有项均已成功接受或视为幂等重复）。
- `status=duplicate` **仅当** `accepted[]` 中所有项都是 duplicate（即被识别为已存在 event id，`duplicate[]` 与 `accepted[]` 等价），且 `rejected[]` / `quarantine[]` 均为 empty。
- 其他所有场景（包括部分成功 + 部分拒绝、部分成功 + 部分隔离、全部拒绝、空 batch 等）一律 `status=partial`，此时响应中 `rejected[]` 与 `quarantine[]` 至少之一 MUST 非 empty，且不得把 `partial` 上报为 `accepted`。

实现 MUST NOT 把 `status=partial` 简化为 `accepted` 以便利客户端处理；客户端 MUST 在 `partial` 时根据 `rejected[]` / `quarantine[]` 决定是否重试或上报。

### 3.2 批量获取 Event

```text
POST /_cokret/self/events/resolve
```

请求示例（非完整 schema）：

```json
{
  "event_ids": ["ck:event:019640ed-8000-7000-8000-000000000000"],
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

### 3.3 查询 / 回填 Event（`ck.events.query`）

```text
GET /_cokret/self/events?realms=<id>&before=<cursor>&limit=500          # 历史 backfill（cursor 之前最近的一批历史事件，向更旧方向取一页）
GET /_cokret/self/events?actors=<did>&after=<cursor>&limit=500           # 从已知 frontier 追上（catch-up）
GET /_cokret/self/events?realms=<id>&actors=<did>&after=<Y>&before=<X>   # 区间查询（Y, X）开区间
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

- `before` 与 `after` 都是 **排除** 语义 — Cokret cursor 是位置 token 而不是 event 引用，"位置之前/之后"不包含 cursor 标记的边界本身。这与 Stripe `starting_after`/`ending_before`、Relay GraphQL `after`/`before` 等业界惯例一致。
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

#### 3.3.5 POST/body 形态（`ck.events.query_post`）

```text
POST /_cokret/self/events/query
Content-Type: application/json

{
  "realms": ["ck:realm:..."],
  "actors": ["did:webvh:..."],
  "before": "ck:cursor:...",
  "after": "ck:cursor:...",
  "order": "default",
  "limit": 200,
  "filters": { "kind": ["ck.message.create"] }
}
```

POST 形态与 GET 形态**完全等价**：参数集（`realms` / `actors` / `before` / `after` / `order` / `limit` / `filters`）、默认顺序规则（§3.3.3）、响应 cursor 绝对方向（§3.3.4）一律相同；只是 wire 形态从 query string 变为 JSON body。

**何时使用 POST**：
- URL 长度风险：`realms[]` 或 `actors[]` 列表较大、`filters` 是嵌套 object 时，URL 容易超过代理 / CDN / 负载均衡器的实际上限（常见 4–8 KiB）
- 隐私 / 日志风险：部署侧的 HTTP access log 通常会完整记录 URL；query string 中的 filter 字段（含可能的敏感 keyword、`actor_id` 列表）会被无差别采集
- 兼容受限客户端：某些 HTTP 中间层会规范化或丢失复杂的 `style: deepObject` 参数

`ck.events.query_post` 是 `ck.events.query` 的 **HTTP-专属 binding variant**，不是独立语义 operation。gRPC 与 MQ 的 wire 形态本就是 body-based，统一使用 `ck.events.query` / `Events/Query` / `events.query` 即可，不需要单独的 `_post` 命名。

**选择规则**：
- 简单查询（仅 `before` / `after` / `limit`，少量 realms/actors）→ `GET /_cokret/self/events`，cacheable、可被代理优化
- 复杂查询（大型 selector / 复杂 filters）→ `POST /_cokret/self/events/query`

**可测试的 GET / POST 边界**：客户端在满足以下任一条件时 **SHOULD** 使用 `ck.events.query_post` 而非 GET 形态，而不是依赖主观判断：

- (a) 请求含 `filters` object；
- (b) `realms[]` / `actors[]` 及其它 selector 项合计超过实现声明的 GET selector 上限（默认阈值 8）；
- (c) selector / filter 含敏感主体关系（如可暴露联系人图谱的 `actor_id` 列表或敏感 keyword）。

当部署侧在 `ServiceDescribe` / feature discovery 标记 query-logging 风险（如反向代理会完整记录 query string）时，客户端 **MUST** 使用 POST。GET query 仅适用于无 `filters`、selector 项少且不敏感的简单查询。

上述"GET selector 上限"由 `ServiceDescribe.limits.max_get_query_selectors` 机器声明；缺省值为 8。客户端在 selector 总数（`realms[]` + `actors[]`）超过该值，或 `filters` 包含不应进入 URL / Referer / access log 的敏感条件时，SHOULD 使用 `POST /_cokret/self/events/query`。

服务端 SHOULD 同时实现两个 endpoint；客户端可以按场景自由选择，**不需要协商**。`ck.events.query_post` 在注册表（`operation-registry.json`）中通过 `binding_variant_of="ck.events.query"` 标记，以保证 SDK 生成器、conformance 测试与 server.describe 能机器可读地枚举该 alternate binding，同时授权、审计和指标归并到 `ck.events.query`。

**`binding_variant_of` conformance 矩阵规则**：当 operation B 声明 `binding_variant_of=A` 时，B 与 A 共享 selector / cursor / cursor-direction / projection 测试集合，只独立测试 wire encoding（query string vs JSON body）。conformance suite 不需要为 variant 重复跑业务逻辑测试。

### 3.4 流式订阅 Event（`ck.events.subscribe`）

```text
GET /_cokret/self/events/subscribe?realms=<id>&after=<cursor>&catchup=true
```

`after=<cursor>` 表示订阅起点：从该 cursor *之后*（排除）开始接收事件，与 [`ck.events.query`](#33-查询--回填-eventckeventsquery) 的 `after=` 同义。Subscribe 天然只有"朝未来推进"一个方向，不接受 `before=` / `order=`；想要历史回填请用 `ck.events.query`。

支持多 realm / actor 一次订阅；`catchup=true` 时服务端只回放 `after=` 到当前 frontier 的追赶区间，再发出 `catchup_complete` 帧切到实时尾部。完整历史必须通过 `GET /_cokret/self/events` 的 `before` / `after` 分页或区间查询读取。


HTTP 200 response `Content-Type` MUST be `application/x-ndjson`。Frame 每行一个独立 JSON 对象：

```text
{ "kind": "event", "realm_id": "ck:realm:01...", "cursor": "opaque", "payload": {} }
{ "kind": "catchup_complete", "realm_id": "ck:realm:01...", "cursor": "opaque" }
{ "kind": "frontier", "realm_id": "ck:realm:01...", "cursor": "opaque" }
{ "kind": "heartbeat" }
{ "kind": "epoch_rotation", "realm_id": "ck:realm:01...", "payload": {"new_epoch": 17} }
{ "kind": "dropped", "realm_id": "ck:realm:01...", "cursor": "opaque", "reconnect_after_ms": 5000 }
{ "kind": "unauthorized", "realm_id": "ck:realm:01..." }
{ "kind": "resync_required", "realm_id": "ck:realm:01...", "reconnect_after_ms": 10000 }
```

客户端必须把 `dropped` 与 `resync_required` 当作硬信号——前者要求按 cursor 重新 `ck.events.query` 补齐，后者要求重建本地状态。`kind="dropped"` frame 的 `cursor` 为 REQUIRED；服务端没有可用补齐 cursor 时 MUST 发送 `resync_required`，不得发送无 cursor 的 `dropped`。

Dropped / resync-required control frame MAY 携带顶层 `reconnect_after_ms`，表示客户端在为同一 authenticated caller + selector/filter scope 打开下一条 `ck.events.subscribe` 连接前必须等待的最小毫秒数。该字段不是错误响应的 `retry_after_ms`，不约束无关 API 调用；服务端一旦发送该字段，MUST 在对应 cooldown scope 内强制执行，过早重连 MUST 返回 `429 rate_limited` 并设置 `Retry-After`，且不得推进 cursor、ack 或其它不可逆订阅状态。客户端 SHOULD 在该延迟上加入 jitter。

## 4. Identity API

```text
POST /_cokret/root/identity/resolve
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
  "key_log_head": "ck:key_event:019642b0-0000-7000-8000-000000000005",
  "seq": 5
}
```

Resolver MUST 返回足够的方法相关证据，使客户端能够验证 control history。

## 5. Account API

`/_cokret/self/account/*` 承载当前 authenticated principal/device 的账号视角能力：一次性 viewer 自读、Actor Profile 自服务更新、account 聚合 streaming（跨 Realm frontier、to_device、account_data、device_lists、presence、unread / notification counts）、account describe 与 cursor revoke。snapshot manifest 入口独立放在 `/_cokret/self/snapshot/*`。逐 Realm 的事件读取与流式订阅走 `/_cokret/self/events/*`（`ck.events.query`、`ck.events.subscribe`），见 §3.3 / §3.4。

注册与 session revoke 属认证生命周期，落 `/_cokret/gate/account/*`，与 `ck.account.issue_session_grant` 共认证面。Handle 申请、审批、预分配、重签、撤销和管理员分配仍属于 issuer / coauth / 部署治理流程；Cokret account self-service endpoint 不得接受裸 `handle` 字段，也不得把未签名 handle 字符串返回为权威身份。实现如需管理面 MUST 使用自己的 negative-space root（例如 `/_soland/admin/*`），不得放在 `/_cokret/` 协议命名空间下。

### 5.1 账号 viewer 与 profile 自服务

```text
GET  /_cokret/self/account/viewer
POST /_cokret/self/account/profile
```

`ck.account.viewer` 返回当前 holder-bound account projection。响应中的 `state` 必须使用 account lifecycle 闭合枚举；`primary_handle_claim` 若存在必须是完整可验证的 `ck.schema.handle_claim.v1`，否则只能返回 `primary_handle_claim_ref` / `handle_claim_digests[]` 供客户端刷新本地 claim cache。viewer 与 `ck.account.describe` 不同：前者返回主体身份投影，后者返回服务能力。

`ck.account.update_profile` 的协议 body 是 `UpdateProfileRequest {patch}`，其中 `patch` 是 `ck.patch.v1`，允许路径仅 `display_name`、`avatar_blob_ref`、`profile_fields.<key>`。`bio` 不是 Actor Profile 顶层 canonical 字段，迁移时必须写入 `profile_fields.bio`；`avatar_url` 不是协议字段，只能在实现兼容层上传 / 解析为 Blob 后写入 `avatar_blob_ref`。`handle`、`status`、`principal_id`、`actor_kind`、`accountable_principal_ids` 与任何 authorization / lifecycle / handle-claim 字段 MUST reject。

`ck.account.update_profile` 是 holder-bound service wrapper，不是新的 profile 真相源。服务端接受后 MUST 写入或等价产生 `ck.profile.update` / Actor Profile projection。它**不隐式**触发 `ck.directory.announce` 或 `ck.account_data.set`；需要可发现 profile 或跨设备 UI/avatar 状态同步的客户端 / 服务，MUST 继续显式走对应 Directory / Account Data 路径，直到部署 profile 另行声明更强 fan-out 契约。

### 5.2 账号聚合订阅（`ck.account.subscribe`）

```text
GET /_cokret/self/account/subscribe?catchup=true                         # initial account sync baseline
GET /_cokret/self/account/subscribe?after=<cursor>                        # live tail after external reconciliation
GET /_cokret/self/account/subscribe?after=<cursor>&catchup=true           # reconnect / dropped catch-up
```

该端点对应 `ck.account.subscribe`,wire 形态是长连接 NDJSON 流。客户端建立长连接后，服务端按 account / Realm filter 推送 `delta` frame(跨 Realm delta + to_device + account_data + device_lists + presence + notifications)与控制 frame(`catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`)。请求参数、frame schema 与重连规则见 [`client-sync.md`](./client-sync.md) §2。

它与 `ck.events.subscribe` 是对称的两类 streaming 订阅(account-aggregate vs per-Realm event log),共享 cursor / `dropped` / `resync_required` 控制模型，但恢复面不同:`account.subscribe` 的 `dropped` 用 `GET /_cokret/self/account/subscribe?after=<cursor>&catchup=true` 重放账号聚合 delta;裸 Event 缺口才使用 `ck.events.query`。`catchup=true` 不表示全量历史；完整历史读取必须走 `ck.events.query`。它不是裸事件读取——裸事件读取请使用 `ck.events.query` / `ck.events.subscribe`。

Dropped / resync-required control frame MAY 携带 `reconnect_after_ms`。客户端在同一 principal/device/filter scope 重新建立 `/_cokret/self/account/subscribe` 之前 MUST 至少等待该时长；服务端 MUST 对过早重连返回 `429 rate_limited` + `Retry-After`，并且不得推进 to-device ack、account subscribe position 或 dropped recovery state。

## 6. Snapshot API

`/_cokret/self/snapshot/*` 提供 Realm snapshot manifest 入口；snapshot 是派生的当前态缓存，客户端使用前 MUST 校验签名、签名者授权、`state_digest` 和每个 chunk digest（见 [`service-surface.md` §11](./service-surface.md)）。

### 6.1 当前 snapshot manifest（`ck.snapshot.head`）

```text
GET /_cokret/self/snapshot/head?realm_id=<id>
```

该端点对应 `ck.snapshot.head`，返回当前推荐 snapshot manifest 指针（不含 chunk bytes）。客户端通过 manifest 中的 `chunks[].chunk_ref` 走 blob surface 取实际数据。snapshot 不是真相源，校验失败时客户端 MUST 回退到 Event history replay。

## 7. Directory API

```text
POST /_cokret/find/directory/search-realms
POST /_cokret/find/directory/resolve-realm
POST /_cokret/find/directory/resolve-target
POST /_cokret/find/directory/search-organizations
POST /_cokret/find/directory/resolve-organization
POST /_cokret/find/directory/search-actors
POST /_cokret/find/directory/search-users
POST /_cokret/find/directory/resolve-handle
POST /_cokret/find/directory/list-handles-for-subject
```

Directory 端点 MUST 在每个结果上分别应用资源可发现性、请求方证明、审核策略与授权过滤。

对于隐藏或未授权访问的资源，`resolve-*` SHOULD 返回与"不存在"不可区分的 `not_found`。

## 8. Blob API

### 8.1 上传

```text
POST /_cokret/self/blob/upload
```

Content type MAY 取 `application/octet-stream` 或 `multipart/form-data`。

响应示例（非完整 schema）：

```json
{
  "blob_ref": "ck:blob:sha256:e3b0...",
  "content_digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "size_bytes": 102450,
  "media_type": "image/png"
}
```

### 8.2 下载

```text
HEAD /_cokret/self/blob/get?blob_ref=<blob_ref>
GET /_cokret/self/blob/get?blob_ref=<blob_ref>
```

客户端 MUST 重新计算内容哈希并与 `blob_ref` 比对。
若哈希不匹配，客户端 MUST 拒绝响应并丢弃内容；服务端在上传、代理或镜像校验时发现不匹配 MUST 返回 `422 digest_mismatch`。

## 9. 标准错误响应

```json
{
  "ok": false,
  "error": {
    "code": "cas_conflict",
    "message": "expected_state_digest mismatch",
    "retry_after_ms": 2000
  }
}
```

## 10. 标准错误码

标准错误码、HTTP 状态码与逐项 reason_code 的 **canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。本节不再在 Markdown 中维护并行表格；任何新增 / 修改 / 删除错误码 MUST 先更新 registry。

`api-conventions.md` §5.1 是该 registry 的解释性 narrative 视图（解释每个 code 的使用场景）；它本身也以 registry 为准，发现差异时以 registry 为准。

实现使用规则：

- 客户端收到 `429` MUST 优先遵守 `Retry-After` header；若缺失再使用 body 中的 `retry_after_ms`。`503` 在带有 `Retry-After` 时也必须按该时间退避。收到 `409` SHOULD 拉取最新状态后退避重试。
- `unsupported_feature` 用于 `Event.requirements.features[]` / `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `ck.*` Event kind；二者不得互相替代。
- 通用 `conflict` 仅作为抽象 base code 出现在 narrative；实现 SHOULD 返回 registry 中更精确的 409 子 code（`cas_conflict` / `causal_conflict` / `dependency_missing` / `duplicate_conflict` / `epoch_mismatch` / `rank_exhausted` / `stale_frontier` / `state_mismatch` / `discussion_track_disabled` / `key_unavailable`）。

## 11. 安全与抗滥用

服务端 SHOULD 在高风险入口实施一致性失败语义：

- 对目录/resolve 查询、join 探测、公开元数据接口，未授权请求不应返回可区分 `not_found` 与 `forbidden` 的信息差异。
- 联邦入口与 policy check 入口应记录来源 service DID + 来源域名哈希，结合 `rate_limited` 与 `temporarily_unavailable` 作回压。
- 对来源签名缺失/验证失败的入口请求，应优先走 reject + audit，不得影响已认证正常来源的可用性。
- 对 URL 中携带认证材料的请求，应 reject + redact log，不得进入正常认证 fallback。
