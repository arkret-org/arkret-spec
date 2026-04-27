# Service HTTP/JSON Binding Draft

## 1. 目标

本文定义 Contrix 默认 HTTP/JSON binding 的路径、请求形状和错误响应。

协议核心不强绑定 REST。其他 transport binding MAY 使用 gRPC、WebSocket、SSE、message queue、libp2p 或 IPC，但必须映射到 `service-surface.md` 中定义的等价语义。

## 2. 通用要求

- 请求和响应默认使用 `Content-Type: application/json`。
- 写请求 MUST 支持幂等键或内容 ID 幂等。
- 认证 MAY 使用 bearer token、HTTP Message Signature、DID proof 或 transport-specific binding。
- 服务 MUST 通过 describe / feature discovery 暴露实际支持路径、profile 和限制。
- 错误响应 MUST 使用统一 error schema。

### 2.1 REST API 命名空间组织

Contrix 的 HTTP/JSON binding 按 **服务角色与 canonical operation** 组织，而不是按某个产品形态拆成固定的 Client API / Server API / Push API 包。客户端、Principal Server、Repo、Index、Directory、Applet、Push Gateway 等都可以暴露自己的服务面；服务发现决定某个节点实际支持哪些命名空间。

默认 REST 命名空间如下：

| 命名空间 | 主要调用方 | 语义 | 规范文件 |
| --- | --- | --- | --- |
| `/server/*` | 客户端与服务 | 服务描述、feature discovery、auth metadata。 | `service-surface.md`、`api-conventions.md` |
| `/identity/*` | 客户端、服务、registry | DID 文档、key log、DID operation、receipt。 | `service-surface.md`、`identity-did.md` |
| `/repo/*` | 客户端、Principal Server、Repo replica | 签名 commit 提交、operation/commit 读取、repo 增量同步。 | `operations-sync.md`、`service-surface.md` |
| `/sync/*` | 客户端、Principal Server | 客户端聚合同步、Space 增量订阅、backfill、snapshot head。 | `client-sync.md`、`service-surface.md` |
| `/federation/*` | Principal Server 之间 | 跨域 transaction、operation 推送/拉取、成员查询、actor 验证。 | `federation.md`、`federation-wire.md` |
| `/index/*` | 客户端、服务 | Entity 查询、结构化查询、搜索、inbox、notification、Space hierarchy。 | `service-surface.md`、`query-schema.md` |
| `/directory/*` | 客户端、服务 | Space / Organization / Actor / handle 的授权发现与解析。 | `discovery-directory.md` |
| `/blob/*` | 客户端、服务 | Blob 上传、HEAD、authenticated download。 | `media-and-blob.md` |
| `/push/*` | 客户端、Sync / Index、Push Gateway | 推送设备注册、注销、脱敏唤醒投递。 | `push-notifications.md` |
| `/device_messages/*`、`/keys/*` | E2EE 客户端、Principal Server | to-device、one-time key、fallback key、device list 相关操作。 | `device-crypto-verification.md` |
| `/authz/*`、`/contrix/v1/check` | 客户端、Repo、Sync、Policy Server | capability 预检查、policy server 签名决策。 | `capabilities.md`、`policy-server.md` |
| `/contrix/v1/ice-config` | 通话客户端、Media Service | TURN/STUN/ICE 短期凭证。 | `webrtc-signaling.md` |
| `/moderation/*` | 客户端、审核服务 | 举报、审核队列或扩展审核入口。 | `moderation.md` |
| `/applet/*` | Contrix 服务调用 Applet | applet ping / describe、transaction push、ghost actor / portal 查询。 | `applet-integration.md` |

客户端视角的常用 API 集合通常包括 `/server`、`/identity`、`/repo`、`/sync`、`/index`、`/directory`、`/blob`、`/push`、`/device_messages`、`/keys`、`/authz`。服务间 API 集合通常包括 `/federation`、`/repo`、`/sync`、`/authz`、`/contrix/v1/check`、`/applet` 和 `/push/notify`。

新增顶层 REST 命名空间前，规范必须同步更新 `service-api-schema.md`、feature discovery 返回值和对应 conformance profile。实现不得用未声明路径绕过 canonical operation、capability、幂等、分页或错误语义。

### 2.2 端点契约规则

每个 REST endpoint 的规范定义必须至少包含：

- `operation_id` / canonical operation。
- Path 参数、query 参数和 request body 字段类型。
- 成功响应字段类型。
- 认证方式：`public_metadata`、`user_session`、`device_proof`、`service_signature`、`policy_token`、`applet_signature` 等。
- 访问限制：Space membership、history visibility、capability、service delegation、namespace、plaintext visibility、rate limit、quota。
- 幂等键：写接口使用 `Idempotency-Key`、path 中的 `{txn_id}`、`commit_id`、`operation_id` 或 canonical request hash。
- 失败时使用标准 error envelope。

JSON 示例只用于说明，不构成完整 schema。正式接口定义 MUST 使用字段表说明字段名、位置、类型、是否必填、含义和约束。

默认规则：

- 除明确标记为 `public_metadata` 的 describe / discovery 外，所有 endpoint MUST 认证。
- 认证只证明调用方身份；服务仍 MUST 执行 capability、Space policy、history visibility、service delegation 和 revocation 检查。
- 服务间调用 MUST 使用 HTTP Message Signature 或等价 service DID proof，并绑定 method、target URI、content digest、origin service DID 和 destination service DID。
- 返回 `not_found` 的 endpoint MUST 对“不存在”和“存在但不可见”保持一致失败语义，除非调用方已有管理权限。
- 所有批量读取 MUST 支持 `limit` 上限，分页 cursor 必须是不透明 token。

### 2.3 端点契约清单

类型简写：`did` 为 DID URI，`id` 为协议对象 ID，`cursor` / `token` 为 opaque string，`signature` 为 `{kid, alg?, sig}`，`proof` 为 DID / HTTP message / detached JWS proof。`operations` 仅作 Operation 数组的 wire 字段名。人类可读文档应写全 Operation。

| Endpoint | Request 类型 | Auth / 访问限制 | Success 类型 |
| --- | --- | --- | --- |
| `GET /api/v1/server/describe` | query: none 或 `service_type?` | `public_metadata`；不得返回私有 topology、secret 或未授权 internal endpoint。 | `{service_did, service_type, protocol_version, supported_features[], supported_bindings[], supported_operations[], auth_metadata?, limits}` |
| `GET /api/v1/identity/describe` | query: none | `public_metadata`；可限流。 | `{service_did, registry_mode, supported_receipts[], protocol_version, profiles[]}` |
| `POST /api/v1/identity/resolve` | body `{did: did, include?: string[]}` | `public_metadata`；private DID MAY require `user_session` 或 presentation proof。 | `{did_document, key_log_head?, seq?, receipts?, method_evidence?}` |
| `GET /api/v1/identity/document` | query `{did: did, version?: string}` | 同 `identity.resolve`。 | `{did_document, head_event_hash?, seq?, receipts?}` |
| `GET /api/v1/identity/log` | query `{did: did, cursor?: cursor, limit?: int}` | public DID 可公开；private / pairwise DID MUST require holder-approved proof。 | `{events[], next_cursor?, has_more}` |
| `POST /api/v1/identity/submit-did-operation` | body `{did: did, seq: int, prev_event_hash?: string, patch: object, proofs: proof[]}` | `device_proof` 或 recovery proof；MUST 满足 DID method / key-log 授权。 | `{status, head_event_hash, seq, receipts?}` |
| `GET /api/v1/identity/receipts` | query `{did: did, head: string}` | 同 DID 可见性；witness 可公开最小 receipt。 | `{receipts[], threshold_met?: boolean}` |
| `GET /api/v1/repo/describe` | query `{repo_id?: did}` | `user_session` / `service_signature`；只返回请求方可访问 repo。 | `{repo_did, head_commit, supported_signatures[], limits}` |
| `GET /api/v1/repo/commits` | query `{repo_id: did, cursor?: cursor, limit?: int}` | repo owner、authorized replica、Space policy 或 history visibility 允许。 | `{commits[], next_cursor?, has_more}` |
| `GET /api/v1/repo/commit` | query `{repo_id?: did, commit_id: id}` | 同 repo read；不可见时返回 `not_found`。 | `{commit, operations?, proofs?}` |
| `POST /api/v1/repo/operations` | body `{repo_id?: did, operation_ids?: id[], event_ids?: id[], include_payload?: boolean}` | 同 repo read；payload 可见性按 Space policy / E2EE envelope 判断。 | `{operations[], missing[], unauthorized[]?}` |
| `POST /api/v1/repo/sync` | body `{repo_id: did, since?: cursor, limit?: int, filters?: object}` | repo owner、authorized replica 或 delegated service。 | `{operations[], next_cursor?, has_more}` |
| `POST /api/v1/repo/submit-commit` | body `{repo_id: did, commit: object, expected_head?: string, idempotency_key?: string}` | commit signature + capability；repo MUST 验证 actor DID、device/session、CAS 和 Space policy。 | `{status, commit_id, head_commit?, sync_token}` |
| `POST /api/v1/sync` | body `{since?: token, filter?: object, set_presence?: string, timeout_ms?: int}` | `user_session` bound to principal/device。 | Client Sync response `{next_batch, rooms/spaces?, to_device?, account_data?, device_lists?}` |
| `GET /api/v1/sync/describe` | query none | `public_metadata` 或 `user_session`；私有 limits 可认证后返回。 | `{service_did, supported_sync_profiles[], limits, frontier?}` |
| `GET /api/v1/sync/subscribe` | query `{space_id: id, cursor?: cursor}` | Space read + service delegation；非 E2EE 私有内容只能给 principal / plaintext-visible service。 | event stream frames `{type, seq, cursor?, payload}` |
| `GET /api/v1/sync/backfill` | query `{space_id: id, cursor?: cursor, limit?: int}` | history visibility + membership frontier + E2EE epoch policy。 | `{events[], prev_cursor?, next_cursor?, limited?}` |
| `GET /api/v1/sync/snapshot-head` | query `{space_id: id}` | Space read；snapshot manifest 必须签名。 | `{snapshot_ref, state_hash, frontier, signature}` |
| `PUT /api/v1/federation/transactions/{txn_id}` | path `{txn_id}` body `{origin: did, destination: did, service_binding_ref, operations[], receipts?, frontier?}` | `service_signature`; destination service DID、URL、Space policy 和 service binding 必须一致。 | `{ok: true, accepted[], rejected[], next_retry_at?}` |
| `POST /api/v1/federation/push-operations` | body `{origin: did, destination: did, space_id: id, service_binding_ref, operations[]}` | `service_signature`; origin 必须可接收于该 Space federation policy；每个 operation 独立验签。 | `{accepted[], rejected[], quarantine[]?}` |
| `GET /api/v1/federation/pull-operations` | query `{space_id: id, after_cursor?: cursor, limit?: int}` | `service_signature`; requester 必须有 backfill 权限和明文可见资格。 | `{operations[], snapshot_bootstrap?, next_cursor?, has_more}` |
| `GET /api/v1/federation/space-members` | query `{space_id: id, cursor?: cursor, limit?: int}` | `service_signature`; 仅对参与方 Principal Server 或 policy 允许服务开放。 | `{members[], membership_frontier, next_cursor?}` |
| `POST /api/v1/federation/verify-actor` | body `{actor_id: did, challenge?: string, signed_payload_hash?: string, signature: signature, purpose: string, space_id?: id}` | `service_signature`; 不得作为公开 DID oracle；requester 必须有 federation、join、event-source 或 shared-Space 相关目的。 | `{valid: boolean, actor_id, verified_key_id?, key_log_head?, did_document_ref?, expires_at?, warnings[]}` |
| `GET /api/v1/index/describe` | query none | `public_metadata`；私有 reducer/frontier 可要求认证。 | `{service_did, reducer_profiles[], schema_profiles[], query_features[], frontier?}` |
| `GET /api/v1/index/entity` | query `{entity_id: id, space_id?: id, at?: string}` | caller 必须可读该 Entity 所在 Space / projection。 | `{entity, state_after?, visibility}` |
| `POST /api/v1/index/query` | body `{space_ids?: id[], entity_types?: string[], relation?: object, filters?: object[], order_by?: string, cursor?: cursor, limit?: int, wait_for?: token}` | 查询结果逐项按 capability / history visibility 过滤；支持 `X-Contrix-Wait-For`。 | `{results[], next_cursor?, total_estimate?, frontier?, stale?: boolean}` |
| `GET /api/v1/index/thread` | query `{topic_id: id, cursor?: cursor, limit?: int}` | topic 可读；结果按 message visibility 过滤。 | `{events[] 或 messages[], next_cursor?, state_after?}` |
| `GET /api/v1/index/notifications` | query `{cursor?: cursor, state?: string, limit?: int}` | `user_session`; 只返回当前 principal/device 的通知。 | `{notifications[], counts?, next_cursor?}` |
| `GET /api/v1/index/inbox` | query `{scope?: string, cursor?: cursor, limit?: int}` | `user_session`; holder-private projection 不得给其他 principal。 | `{items[], next_cursor?, frontier?}` |
| `POST /api/v1/index/search` | body `{query: string, space_ids?: id[], entity_types?: string[], time_range?: object, cursor?: cursor, limit?: int}` | 仅可搜索授权范围；E2EE 内容只能由本地索引或 plaintext-visible / TEE profile 处理。 | `{results[], next_cursor?, total_estimate?}` |
| `GET /api/v1/index/space-hierarchy` | query `{space_id: id, depth?: int, include_unconfirmed?: boolean}` | caller 必须可发现 root Space；子项逐项按 discoverability 过滤。 | `{root, children[], edges[], next_cursor?}` |
| `GET /api/v1/directory/describe` | query none | `public_metadata`；可限流。 | `{service_did, resource_types[], discovery_profiles[], restricted_query_proof?: boolean}` |
| `POST /api/v1/directory/search-spaces` | body `{query?: string, organization_did?: did, parent_space_id?: id, requester?: did, proofs?: proof[], cursor?: cursor, limit?: int}` | discoverability + requester proof + policy filtering；隐藏资源不泄露存在性。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-space` | body `{space_id?: id, alias?: string, invite_token?: string, signed_link?: string, requester?: did, proofs?: proof[]}` | invite / restricted / secret Space 按统一 `not_found` 失败。 | `{space_preview, stripped_state?, join_rule?, via_services?}` |
| `POST /api/v1/directory/search-organizations` | body `{query?: string, claims?: object, cursor?: cursor, limit?: int}` | 仅返回公开或授权可发现组织。 | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-organization` | body `{organization_did?: did, handle?: string, proofs?: proof[]}` | 公开组织 DID 可解析不表示成员或拓扑公开。 | `{organization_preview, did_document_ref?, endorsements?}` |
| `POST /api/v1/directory/search-actors` | body `{query?: string, space_id?: id, organization_did?: did, cursor?: cursor, limit?: int}` | 不得泄露 pairwise/private DID 或未披露组织账号。 | `{results[], next_cursor?}` |
| `GET /api/v1/directory/search-users` | query `{q: string, space_id?: id, limit?: int}` | `user_session`; 用于 mention autocomplete，必须受共同 Space / directory policy 限制。 | `{results[]}` |
| `POST /api/v1/directory/resolve-handle` | body `{handle: string, expected_did?: did, proof_challenge?: string}` | 按 handle 双向验证规则；private handle 需 presentation。 | `{did, handle, verified: boolean, claims?}` |
| `POST /api/v1/blob/upload` | body binary/multipart + metadata `{space_id?, sha256?, size, mimetype?, purpose?}` | `user_session`; upload capability、quota、media policy；私有 blob 绑定 Space / actor。 | `{blob_ref, size, mimetype, sha256, upload_receipt?}` |
| `HEAD/GET /api/v1/blob/get` | query `{blob_ref: string}` headers `Authorization?`, `Range?`, `X-Contrix-Wait-For?` | 公开 blob 可匿名；私有 blob 必须验证 actor/device/Space/purpose/expiry。 | bytes 或 headers `{Content-Length, Digest, Cache-Control}` |
| `POST /api/v1/push/register-device` | body `{device_id: id, push_gateway: url, push_key: string, platform?: string, app_id?: string, display_name?: string}` | `user_session` for same principal/device；push_key 必须被加密或最小披露存储。 | `{ok: true, registration_id?, expires_at?}` |
| `POST /api/v1/push/unregister-device` | body `{device_id: id, push_key?: string, app_id?: string}` | `user_session` for same device/principal 或 device revocation path。 | `{ok: true}` |
| `POST /api/v1/push/notify` | body `{notification: {event_id?, space_id?, type, sender?, push_hint?, counts?, devices[]}}` | `service_signature` from authorized Sync / Index；MUST be blind/minimized for E2EE。 | `{rejected[]}` |
| `PUT /api/v1/device_messages/{txn_id}` | path `{txn_id}` body `{messages: {principal_id: {device_id: {type, content}}}}` | sender `user_session` / device key；目标必须是授权 device；按 `(sender, txn_id)` 幂等。 | `{ok: true, delivered?, unknown_devices?}` |
| `GET /api/v1/device_messages` | query `{from?: token, limit?: int}` | `user_session` bound to current device；只返回该 device 队列。 | `{events[], next_batch?, limited?}` |
| `POST /api/v1/keys/upload` | body `{device_id: id, one_time_keys?: object, fallback_keys?: object, device_signature: signature}` | current device proof；key 必须链接 self-signing / principal key。 | `{one_time_key_counts, fallback_keys?}` |
| `POST /api/v1/keys/query` | body `{device_keys: {principal_id: string[]}, timeout_ms?: int}` | `user_session`; 查询范围可按关系 / Space 限制。 | `{device_keys, failures?}` |
| `POST /api/v1/keys/claim` | body `{one_time_keys: {principal_id: {device_id: algorithm}}}` | `user_session`; one-time key MUST 原子消费。 | `{one_time_keys, failures?}` |
| `GET /api/v1/authz/effective-grants` | query `{space_id: id, subject: did, at?: string}` | subject 本人、Space admin、authorized service；不得枚举无关 subject。 | `{grants[], state_hash?, evaluated_at}` |
| `GET /api/v1/authz/invites` | query `{space_id?: id, subject: did 或 string, cursor?: cursor}` | subject 本人或 inviter/admin；secret invites 不可枚举。 | `{invites[], next_cursor?}` |
| `POST /api/v1/authz/check` | body `{actor: did, action: string, resource: object, context?: object}` | caller 必须是相关 actor、Repo/Sync 预检查服务或 policy-authorized service。 | `{allowed: boolean, reason_code?, grants?, obligations?}` |
| `POST /contrix/v1/check` | body `{request_id, space_id?, request_canonical_hash, action, actor, source, event_preview?, auth_context?}` | `policy_token` / `service_signature`; 只接收最小披露字段。 | signed policy decision `{decision, reason_code, expires_at, obligations?, signature}` |
| `POST /api/v1/moderation/report` | body `{space_id: id, target_ref: id, reason: enum, description?: string, reporter: did, evidence_refs?: id[]}` | `user_session`; reporter 必须可见 target；report 仅对 moderators 可见。 | `{report_id, status, routed_to?}` |
| `GET /api/v1/applet/ping` | query none | `public_metadata` 或 `service_signature`；不得泄露 private namespace。 | `{ok, applet_id, service_did, protocol_version}` |
| `GET /api/v1/applet/describe` | query none | `service_signature` SHOULD；public mode 只返回公开 capabilities。 | `{applet_id, service_did, protocols[], namespaces, limits, auth}` |
| `PUT /api/v1/applet/transactions/{txn_id}` | path `{txn_id}` body `{source_service_did, events[], ephemeral?}` | `service_signature`; Applet 必须验证每个 event signature、namespace 和 capability。 | `{ok: true, rejected?, retry_after_ms?}` |
| `GET /api/v1/applet/actors/{actor_id}` | path `{actor_id}` | `service_signature`; actor_id 必须命中 Applet actor namespace。 | `{exists, actor_id, display_name?, external_ref?}` 或 `not_found` |
| `GET /api/v1/applet/spaces/{space_id_or_alias}` | path `{space_id_or_alias}` | `service_signature`; 必须命中 portal namespace 或授权查询。 | `{exists, space_id?, title?, external_ref?}` |
| `GET /api/v1/applet/protocols/{protocol}` | path `{protocol}` | 可 public_metadata；实例列表可要求授权。 | `{protocol, display_name, icon_blob?, field_types, instances?}` |
| `GET /api/v1/applet/third_party/users` | query `{protocol, ...external_ids}` | `service_signature`; 查询字段必须在 registration namespace 内。 | `{actor_id?, exists, external_ref?}` |
| `GET /api/v1/applet/third_party/locations` | query `{protocol, ...external_ids}` | `service_signature`; 查询字段必须在 portal namespace 内。 | `{space_id?, exists, external_ref?}` |
| `POST /contrix/v1/ice-config` | body `{space_id: id, call_id: id, actor_id: did, device_id: id, mode: string}` | `user_session`; actor 必须有 call/media capability，Media Service 必须被 Space policy 委托。 | `{ttl_seconds, ice_servers[], policy, signature}` |

`POST /api/v1/federation/verify-actor` 的响应只能作为缓存加速或辅助诊断。接收方在接受事件、成员变更或设备绑定前，仍 MUST 独立验证 DID Document、key log、签名 transcript、capability 和 Space policy；不得把对端“验证通过”当成最终授权依据。

### 2.4 字段级 Schema 索引

本节是 REST 端点的字段级 schema 索引。字段写法为 `name: type - 说明`。出现在“必填字段”列的字段为 required；出现在“可选字段”列的字段为 optional。位置若非 body，会显式标注为 `path.`、`query.` 或 `header.`。

| `operation_id` | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.server.describe` | 无 | `query.service_type: string - 过滤服务类型` | `service_did: did - 服务 DID`; `service_type: string - 运行时服务类型`; `protocol_version: string`; `supported_features: string[]`; `supported_bindings: object[]`; `supported_operations: operation_id[]`; `auth_metadata: object?`; `limits: object?` | `public_metadata`; 不得返回私有拓扑或 secret。 |
| `cx.identity.describe_registry` | 无 | 无 | `service_did: did`; `registry_mode: enum(writer,witness,replica)`; `supported_receipts: string[]`; `protocol_version: string`; `profiles: string[]` | `public_metadata`; 可限流。 |
| `cx.identity.resolve` | `did: did - 待解析 DID` | `include: string[] - 请求附加证据，如 key_log/receipts` | `did_document: object`; `key_log_head: id?`; `seq: int?`; `receipts: object[]?`; `method_evidence: object?` | private / pairwise DID 可要求 presentation proof。 |
| `cx.identity.get_document` | `query.did: did` | `query.version: string - 指定版本或 head` | `did_document: object`; `head_event_hash: string?`; `seq: int?`; `receipts: object[]?` | 可见性同 `cx.identity.resolve`。 |
| `cx.identity.get_log` | `query.did: did` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `has_more: boolean` | private / pairwise DID MUST 要求 holder-approved proof。 |
| `cx.identity.submit_did_operation` | `did: did`; `seq: int`; `patch: object`; `proofs: proof[]` | `prev_event_hash: string` | `status: enum(accepted,duplicate)`; `head_event_hash: string`; `seq: int`; `receipts: object[]?` | MUST 满足 DID method / key-log 授权；`did+seq` 幂等。 |
| `cx.identity.get_receipts` | `query.did: did`; `query.head: string` | 无 | `receipts: object[]`; `threshold_met: boolean?` | 只公开最小 witness receipt。 |
| `cx.repo.describe` | 无 | `query.repo_id: did` | `repo_did: did`; `head_commit: id`; `supported_signatures: string[]`; `limits: object?` | 只返回请求方可访问 repo。 |
| `cx.repo.list_commits` | `query.repo_id: did` | `query.cursor: cursor`; `query.limit: int` | `commits: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 受 repo read、history visibility 和 Space policy 限制。 |
| `cx.repo.get_commit` | `query.commit_id: id` | `query.repo_id: did`; `query.include_operations: boolean` | `commit: object`; `operations: object[]?`; `proofs: object[]?` | 不可见时返回 `not_found`。 |
| `cx.repo.get_operations` | 至少一个：`operation_ids: id[]` 或 `event_ids: id[]` | `repo_id: did`; `include_payload: boolean` | `operations: object[]`; `missing: id[]`; `unauthorized: id[]?` | payload 可见性按 Space policy / E2EE envelope 判断。 |
| `cx.repo.sync` | `repo_id: did` | `since: cursor`; `limit: int`; `filters: object` | `operations: object[]`; `next_cursor: cursor?`; `has_more: boolean` | repo owner、authorized replica 或 delegated service。 |
| `cx.repo.submit_commit` | `repo_id: did`; `commit: object` | `expected_head: string`; `idempotency_key: string` | `status: enum(accepted,duplicate)`; `commit_id: id`; `head_commit: id?`; `sync_token: token` | MUST 验证 commit signature、CAS、capability 和 Space policy。 |
| `cx.sync.client_sync` | 无 | `since: token`; `filter: object`; `set_presence: enum(online,offline,unavailable)`; `timeout_ms: int` | `next_batch: token`; `spaces: object?`; `to_device: object?`; `account_data: object?`; `device_lists: object?` | `user_session` 必须绑定 principal/device。 |
| `cx.sync.describe` | 无 | 无 | `service_did: did`; `supported_sync_profiles: string[]`; `limits: object`; `frontier: object?` | 私有 frontier 可认证后返回。 |
| `cx.sync.subscribe` | `query.space_id: id` | `query.cursor: cursor` | stream frame: `type: string`; `seq: int`; `cursor: cursor?`; `payload: object` | Space read + service delegation；明文私有内容只给授权边界。 |
| `cx.sync.backfill` | `query.space_id: id` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `prev_cursor: cursor?`; `next_cursor: cursor?`; `limited: boolean?` | history visibility、membership frontier、E2EE epoch policy。 |
| `cx.sync.get_snapshot_head` | `query.space_id: id` | 无 | `snapshot_ref: id`; `state_hash: string`; `frontier: object`; `signature: signature` | snapshot manifest MUST 签名。 |
| `cx.federation.transaction` | `path.txn_id: id`; `origin: did`; `destination: did`; `service_binding_ref: object`; `operations: object[]` | `receipts: object[]`; `frontier: object` | `ok: boolean`; `accepted: id[]`; `rejected: object[]`; `next_retry_at: datetime?` | `service_signature`; destination DID、URL、policy 和 binding 必须一致。 |
| `cx.federation.push_operations` | `origin: did`; `destination: did`; `space_id: id`; `service_binding_ref: object`; `operations: object[]` | 无 | `accepted: id[]`; `rejected: object[]`; `quarantine: id[]?` | 每个 operation 独立验签和授权。 |
| `cx.federation.pull_operations` | `query.space_id: id` | `query.after_cursor: cursor`; `query.limit: int` | `operations: object[]`; `snapshot_bootstrap?: object`; `next_cursor: cursor?`; `has_more: boolean` | requester 必须有 backfill 权限和明文可见资格。 |
| `cx.federation.space_members` | `query.space_id: id` | `query.cursor: cursor`; `query.limit: int` | `members: object[]`; `membership_frontier: object`; `next_cursor: cursor?` | 仅参与方 Principal Server 或 policy 允许服务。 |
| `cx.federation.verify_actor` | `actor_id: did`; `purpose: enum(event_source,federation_join,device_binding)`; `signature: signature` | `space_id: id`; `challenge: string`; `signed_payload_hash: string` | `valid: boolean`; `actor_id: did`; `verified_key_id: string?`; `key_log_head: id?`; `did_document_ref: string?`; `expires_at: datetime?`; `warnings: string[]` | 只作缓存/诊断；不得替代本地 DID、key log、capability 和 Space policy 验证。 |
| `cx.index.describe` | 无 | 无 | `service_did: did`; `reducer_profiles: string[]`; `schema_profiles: string[]`; `query_features: string[]`; `frontier: object?` | private reducer/frontier 可要求认证。 |
| `cx.index.get_entity` | `query.entity_id: id` | `query.space_id: id`; `query.at: string` | `entity: object`; `state_after: string?`; `visibility: string` | caller 必须可读 Entity 所属 Space / projection。 |
| `cx.index.query` | 无 | `space_ids: id[]`; `entity_types: string[]`; `relation: object`; `filters: object[]`; `order_by: string`; `cursor: cursor`; `limit: int`; `wait_for: token`; `header.X-Contrix-Wait-For: token` | `results: object[]`; `next_cursor: cursor?`; `total_estimate: int?`; `frontier: object?`; `stale: boolean?` | 结果逐项按 capability/history visibility 过滤。 |
| `cx.index.thread` | `query.topic_id: id` | `query.cursor: cursor`; `query.limit: int` | `events: object[]?`; `messages: object[]?`; `next_cursor: cursor?`; `state_after: string?` | topic 可读；message 逐项过滤。 |
| `cx.index.notifications` | 无 | `query.cursor: cursor`; `query.state: string`; `query.limit: int` | `notifications: object[]`; `counts: object?`; `next_cursor: cursor?` | 只返回当前 principal/device 通知。 |
| `cx.index.inbox` | 无 | `query.scope: string`; `query.cursor: cursor`; `query.limit: int` | `items: object[]`; `next_cursor: cursor?`; `frontier: object?` | holder-private projection 不得跨 principal 泄露。 |
| `cx.index.search` | `query: string` | `space_ids: id[]`; `entity_types: string[]`; `time_range: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `total_estimate: int?` | E2EE 内容只允许本地索引、plaintext-visible 或 TEE profile。 |
| `cx.index.space_hierarchy` | `query.space_id: id` | `query.depth: int`; `query.include_unconfirmed: boolean` | `root: object`; `children: object[]`; `edges: object[]`; `next_cursor: cursor?` | root 和子项逐项按 discoverability 过滤。 |
| `cx.directory.describe` | 无 | 无 | `service_did: did`; `resource_types: string[]`; `discovery_profiles: string[]`; `restricted_query_proof: boolean?` | `public_metadata`; 可限流。 |
| `cx.directory.search_spaces` | 无 | `query: string`; `organization_did: did`; `parent_space_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | hidden resource 不泄露存在性。 |
| `cx.directory.resolve_space` | 至少一个：`space_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proofs: proof[]` | `space_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `via_services: did[]?` | secret/restricted Space 使用统一 `not_found`。 |
| `cx.directory.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 仅公开或授权可发现组织。 |
| `cx.directory.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | 解析组织不等于公开成员或拓扑。 |
| `cx.directory.search_actors` | 无 | `query: string`; `space_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 不得泄露 pairwise/private DID。 |
| `cx.directory.search_users` | `query.q: string` | `query.space_id: id`; `query.limit: int` | `results: object[]` | mention autocomplete；受共同 Space / directory policy 限制。 |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string` | `did: did`; `handle: string`; `verified: boolean`; `claims: object[]?` | private handle 需要 presentation。 |
| `cx.blob.upload` | `size: int` | `space_id: id`; `sha256: string`; `mimetype: string`; `purpose: string`; binary/multipart body | `blob_ref: string`; `size: int`; `mimetype: string?`; `sha256: string`; `upload_receipt: object?` | upload capability、quota、media policy。 |
| `cx.blob.head` | `query.blob_ref: string` | `header.Authorization: token`; `header.X-Contrix-Wait-For: token` | headers 包含 `Content-Length?`, `Digest?`, `Cache-Control?`, `Content-Type?` | 私有 blob 必须验证 actor/device/Space/purpose/expiry；不得通过 header 泄露不可见资源。 |
| `cx.blob.get` | `query.blob_ref: string` | `header.Authorization: token`; `header.Range: string`; `header.X-Contrix-Wait-For: token` | bytes；headers 包含 `Content-Length?`, `Digest?`, `Cache-Control?`, `Content-Type?` | 私有 blob 必须验证 actor/device/Space/purpose/expiry；Range 不得泄露不可见资源。 |
| `cx.push.register_device` | `device_id: id`; `push_gateway: url`; `push_key: string` | `platform: string`; `app_id: string`; `display_name: string` | `ok: boolean`; `registration_id: id?`; `expires_at: datetime?` | 只能注册当前 principal/device。 |
| `cx.push.unregister_device` | `device_id: id` | `push_key: string`; `app_id: string` | `ok: boolean` | same device/principal 或 device revocation path。 |
| `cx.push.notify` | `notification: object` | `notification.event_id: id`; `notification.space_id: id`; `notification.sender: did`; `notification.push_hint: string`; `notification.counts: object`; `notification.devices: object[]` | `rejected: object[]` | 来自授权 Sync/Index；E2EE 必须脱敏。 |
| `cx.device_messages.put` | `path.txn_id: id`; `messages: object` | 无 | `ok: boolean`; `delivered: object?`; `unknown_devices: object?` | sender + txn_id 幂等；目标必须是授权 device。 |
| `cx.device_messages.get` | 无 | `query.from: token`; `query.limit: int` | `events: object[]`; `next_batch: token?`; `limited: boolean?` | 只返回当前 device 队列。 |
| `cx.keys.upload` | `device_id: id`; `device_signature: signature` | `one_time_keys: object`; `fallback_keys: object` | `one_time_key_counts: object`; `fallback_keys: object?` | key 必须链接 self-signing / principal key。 |
| `cx.keys.query` | `device_keys: object` | `timeout_ms: int` | `device_keys: object`; `failures: object?` | 查询范围可按关系 / Space 限制。 |
| `cx.keys.claim` | `one_time_keys: object` | 无 | `one_time_keys: object`; `failures: object?` | one-time key MUST 原子消费。 |
| `cx.authz.get_effective_grants` | `query.space_id: id`; `query.subject: did` | `query.at: string` | `grants: object[]`; `state_hash: string?`; `evaluated_at: datetime` | subject 本人、Space admin 或授权服务。 |
| `cx.authz.get_invites` | `query.subject: did 或 string` | `query.space_id: id`; `query.cursor: cursor` | `invites: object[]`; `next_cursor: cursor?` | secret invite 不可枚举。 |
| `cx.authz.check` | `actor: did`; `action: string`; `resource: object` | `context: object` | `allowed: boolean`; `reason_code: string?`; `grants: object[]?`; `obligations: object[]?` | Policy allow 不创建 capability。 |
| `cx.policy.check` | `request_id: string`; `request_canonical_hash: string`; `action: string`; `actor: did`; `source: object` | `space_id: id`; `event_preview: object`; `auth_context: object` | `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `reason_code: string`; `expires_at: datetime`; `obligations: object[]?`; `signature: signature` | 只接收最小披露字段；decision 按 hash 缓存。 |
| `cx.moderation.report` | `space_id: id`; `target_ref: id`; `reason: enum`; `reporter: did` | `description: string`; `evidence_refs: id[]` | `report_id: id`; `status: string`; `routed_to: did[]?` | reporter 必须可见 target；只对 moderators 可见。 |
| `cx.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 不得泄露 private namespace。 |
| `cx.applet.describe` | 无 | 无 | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | public mode 只返回公开 capabilities。 |
| `cx.applet.transaction` | `path.txn_id: id`; `source_service_did: did`; `events: object[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet 必须验证 event signature、namespace、capability。 |
| `cx.applet.query_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 namespace。 |
| `cx.applet.query_space` | `path.space_id_or_alias: string` | 无 | `exists: boolean`; `space_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `cx.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | instance list 可要求授权。 |
| `cx.applet.third_party_users` | `query.protocol: string`; external ids | 无 | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 registration namespace 内。 |
| `cx.applet.third_party_locations` | `query.protocol: string`; external ids | 无 | `space_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `cx.media.ice_config` | `space_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `mode: string` | 无 | `ttl_seconds: int`; `ice_servers: object[]`; `policy: object`; `signature: signature` | actor 必须有 call/media capability；Media Service 必须被委托。 |

## 3. Repo API

### 3.1 提交 commit

```text
POST /api/v1/repo/submit-commit
```

请求示例（非完整 schema）：

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "commit": {
    "commit_id": "cx:commit:01JS0KE...",
    "prev": ["cx:commit:01JS0KD..."],
    "operations": [],
    "signature": {}
  }
}
```

响应示例（非完整 schema）：

```json
{
  "status": "accepted",
  "commit_id": "cx:commit:01JS0KE...",
  "sync_token": "opaque"
}
```

若 CAS (`expected_state_hash`) 校验失败，返回 `409 cas_conflict`。

Repo 的协议级写入单元是签名 commit。实现 MAY 在 SDK 或本地接口中接受单个 operation，但在进入网络传播、同步或审计前 MUST 将其封装进签名 commit；接收方不得把未归属 commit 的裸 operation 当作 canonical history。

### 3.2 同步增量

```text
POST /api/v1/repo/sync
```

请求示例（非完整 schema）：

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "since": "cursor-or-operation-id",
  "limit": 500
}
```

响应示例（非完整 schema）：

```json
{
  "operations": [],
  "next_cursor": "opaque",
  "has_more": true
}
```

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
    "verification_method": [],
    "service": []
  },
  "key_log_head": "cx:keyevt:01JS...",
  "seq": 5
}
```

Resolver MUST return enough method-specific evidence for clients to verify control history.

## 5. Sync API

### 5.1 客户端增量同步

```text
POST /api/v1/sync
```

该端点对应 `cx.sync.client_sync`，用于客户端按 account / Space filter 拉取稳定增量视图。请求与响应形状见 `client-sync.md`。

### 5.2 Space 增量流订阅

```text
GET /api/v1/sync/subscribe?space_id=<space_id>&cursor=<cursor>
```

Frame:

```json
{
  "type": "event",
  "seq": 106,
  "payload": {}
}
```

同一语义流 MAY 通过 WebSocket、SSE 或长轮询承载，但 HTTP/JSON 默认参考路径是 `/api/v1/sync/subscribe`。`/sync/stream` 仅用于具体 transport 的内部帧名，不定义为新的 canonical operation。

## 6. Directory API

```text
POST /api/v1/directory/search-spaces
POST /api/v1/directory/resolve-space
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

Directory endpoints MUST apply resource discoverability, requester proof, moderation policy and authorization filtering per result.

For hidden or unauthorized resources, `resolve-*` SHOULD return an indistinguishable `not_found`.

## 7. Blob API

### 7.1 上传

```text
POST /api/v1/blob/upload
```

Content type MAY be `application/octet-stream` or `multipart/form-data`.

响应示例（非完整 schema）：

```json
{
  "blob_ref": "cx:blob:sha256:e3b0...",
  "size": 102450,
  "mimetype": "image/png"
}
```

### 7.2 下载

```text
HEAD /api/v1/blob/get?blob_ref=<blob_ref>
GET /api/v1/blob/get?blob_ref=<blob_ref>
```

客户端 MUST 重新计算内容哈希并与 `blob_ref` 比对。

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

| 错误码 | HTTP Status | 含义 |
| --- | --- | --- |
| `invalid_signature` | 401 | 签名校验失败。 |
| `auth_expired` | 401 | 认证令牌或 grant 已过期。 |
| `capability_denied` | 403 | 当前 actor 无所需权限。 |
| `space_frozen` | 403 | Space 冻结或归档。 |
| `not_found` | 404 | 目标不存在或对请求方不可见。 |
| `cas_conflict` | 409 | `expected_state_hash` 不匹配。 |
| `epoch_mismatch` | 409 | MLS epoch 版本过期。 |
| `quota_exceeded` | 413 | 配额超限。 |
| `temporarily_unavailable` | 503 | 服务暂不可用。 |
| `rate_limited` | 429 | 请求频率超限。 |
| `unknown_did` | 422 | DID 无法解析。 |
| `schema_violation` | 422 | payload 不符合 schema。 |
| `internal_error` | 500 | 节点内部错误。 |

客户端收到 `429` 或 `503` MUST 遵守 `retry_after_ms`。收到 `409` SHOULD 拉取最新状态后退避重试。

## 10. 安全与抗滥用

服务端 SHOULD 在高风险入口实施一致性失败语义：

- 对目录/resolve 查询、join 探测、公开元数据接口，未授权请求不应返回可区分 `not_found` 与 `forbidden` 的信息差异。
- 联邦入口与 policy check 入口应记录来源 service DID + 来源域名哈希，结合 `rate_limited` 与 `temporarily_unavailable` 作回压。
- 对来源签名缺失/验证失败的入口请求，应优先走 reject + audit，不得影响已认证正常来源的可用性。

