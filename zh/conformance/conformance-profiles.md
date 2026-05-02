# 兼容性与实现 Profile

## 1. 目标

Contrix 是模块化协议。为了避免“实现了 Contrix”变成不可验证的模糊声明，规范 MUST 定义可测试的实现 profile。

每个实现 MUST 声明自己支持的 profile、协议版本和 feature 集合。  
Conformance 测试 SHOULD 以 profile 为单位执行。

## 2. Profile 命名

Profile 名称使用：

```text
cx.profile.<name>.v<major>
```

示例：

- `cx.profile.minimal_client.v1`
- `cx.profile.chat_only_client.v1`
- `cx.profile.kanban_only_client.v1`
- `cx.profile.principal_server_events_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.federation_minimal.v1`
- `cx.profile.mimi_interop.v1`

## 2.1 v1 MVP 分层

为降低实现复杂度，v1 profile 分为三层：

| 层级 | 含义 | 典型内容 |
| --- | --- | --- |
| Core | 声称支持 Contrix v1 的实现必须支持，或在 profile 中明确声明不支持对应角色。 | DID/handle resolver、Event Envelope、per-actor event chain、Space、Room、Board、List、Card、Message、Morph、Relation、Capability、Index query、Sync cursor、Blob hash 校验、标准错误。 |
| Recommended | 主客户端和 Principal Server SHOULD 支持，但轻量实现可以不支持。 | E2EE、push、presence、read receipt、snapshot bootstrap、local full-text search、moderation report。 |
| Extension | 不属于 v1 MVP core，必须以独立 profile 声明。 | MIMI interop、WebRTC call、Applet integration、Agent protocol bridge、Agent Memory advanced lifecycle、sovereign deployment。 |

Document、File、Memory、Run、Poll 在 v1 MVP 中默认是 Morph profile 或 extension profile，不是 core 标准对象。实现不得因为未来可能标准化这些类型，就在 v1 wire contract 中要求对端支持专用对象类型。

为避免 Core 范围过大导致实现无法启动，v1 的首轮互操作验收 SHOULD 拆成三个可运行闭环：

- `cx.profile.core_event_store.v1`：DID / service discovery、Event Envelope validation、event submit/fetch/backfill、per-actor event chain validation、idempotent duplicate handling、standard error。
- `cx.profile.chat_mvp.v1`：在 `core_event_store` 之上支持 Space、`cx.member.state`、Room、`cx.room.member`、Message、Reaction、Redaction、Client Sync timeline 和 history visibility。
- `cx.profile.kanban_mvp.v1`：在 `core_event_store` 之上支持 Space、Board、List、Card、`contains` position Relation、`cx.card.move`、`cx.card.reorder`、Collection projection 和 wait-for query。

`chat_only_client`、`kanban_only_client`、`minimal_client`、`principal_server` 和 `index_node` 可以组合上述闭环声明能力；未声明的闭环不得被对端视为默认可用。

`chat_mvp` 与 `kanban_mvp` 不要求实现任意 Morph renderer、任意 facet reducer 或插件 UI。它们只需要按声明 profile 保留未知 Morph / facet 字段、同步相关 Event、执行 schema/capability 校验，并在必须展示时提供 generic Morph fallback。任何依赖特定 `morph_type` 或 facet 的交互能力 MUST 由额外 profile 显式声明。

## 2.2 v1 启动 Profile

以下 profile 用于把 v1 启动范围降到可实现的产品子集。它们不是 `minimal_client` 的替代品，而是面向具体产品形态的互操作声明。

### `cx.profile.chat_only_client.v1`

适用于只实现聊天/讨论体验的客户端。

MUST 支持：

- DID / handle 解析和 service discovery
- Space bootstrap、Space membership、Room、Room membership、Message、Reaction、Redaction
- 基础 `cx.message.create`、`cx.message.revise`、`cx.message.redact`、`cx.reaction.add`、`cx.reaction.remove`
- 基础 capability check 结果处理和 `cx.message.*` 高频授权快路径
- client sync、timeline pagination、backfill、`state_after`
- Room history visibility 和 linked Room 不继承 Card 权限的裁剪规则

MAY 支持 Board、List、Card、View projection、Applet、Agent、WebRTC、MIMI 和 E2EE。未声明支持时，客户端不得把这些能力作为必需交互。

### `cx.profile.kanban_only_client.v1`

适用于只实现 Space / Board / List / Card 工作流的客户端。

MUST 支持：

- DID / handle 解析和 service discovery
- Space bootstrap、Board、List、Card、Relation position edge、View collection projection
- `cx.board.*`、`cx.list.*`、`cx.card.create`、`cx.card.update`、`cx.card.move`、`cx.card.reorder`
- Board position 的 CAS / stale reorder 处理和 deterministic conflict record 展示
- 基础 capability check 结果处理和 `cx.card.move` / `cx.card.reorder` 高频授权快路径
- client sync、index query、wait-for、pagination、backfill

MAY 支持 Room / Message。若支持 Card linked Room，必须按 Room membership 独立裁剪。

### `cx.profile.federation_minimal.v1`

适用于最小跨 Principal Server 操作交换。

MUST 支持：

- service DID authentication
- federation transaction idempotency
- destination binding 校验
- signed Event Envelope 逐条验签与授权
- `accepted[]` / `rejected[]` / `quarantine[]` 分项结果
- dependency missing 的 pull / backfill 恢复
- duplicate conflict quarantine
- scalability constraints 中的 batch、event size 和 retry 规则

MAY 支持 gossip、snapshot-assisted bootstrap、MIMI facade、Applet bridge 和 full-text search。

## 3. 通用强制要求（所有 Profile 必须遵守）

以下要求不依赖具体角色，必须作为可互操作实现的基础：

- 事件名必须符合 `cx.` 命名规则，且标准 `cx.*` Event kind 必须在 `artifacts/registry/event-kind-registry.json` 注册；schema id 必须在 `artifacts/registry/schema-registry.json` 注册。
- Event Envelope MUST 先通过 `cx.schema.event.v1`，再按 `Event.kind` 通过 `cx.schema.event_payload.v1` 对应 payload class；active 标准 kind 未匹配 payload class 或 payload 校验失败时 MUST 返回 `schema_violation`，不得进入 reducer。
- 事件/关系/对象/View 的 `type`、`created_at`、`space_id`、`space_version`、`proof`、`hlc`、`actor_seq`、`prev_refs` / `auth_refs` 在 reducer 与验证逻辑中不能被跳过。
- `space_version` 与 `auth` 约束必须执行，不得通过客户端配置豁免。
- State frontier、snapshot frontier、projection frontier 和 wait-for token MUST 以 `event_id` / actor frontier 为语义单位；`operation_id` 只可表示服务 canonical operation 或旧 SDK 本地幂等别名。
- Snapshot manifest MUST 包含 `event_set_commitment`；high-assurance profile MUST 支持 inclusion / omission challenge 或 witness quorum 校验。
- 裸名事件（如 `space.create`）MUST 被拒绝，不能作为新增标准互操作行为。
- 实现 MUST 对 `causal` 关系、`revoked` 与 `proof` 失效状态进行一致性拒绝（fail-closed），不能“静默接受”。

## 4. Minimal Client

`cx.profile.minimal_client.v1` 适用于只读或轻量写入客户端。

MUST 支持：

- DID / handle 解析
- service discovery
- event 拉取 / backfill
- index 查询
- 基础 Room / Board / List / Card / Message / Morph / Relation / Event 解码
- 未知 Morph / facet 字段保留和 generic fallback，不要求专用 renderer
- capability 检查结果处理
- cursor 分页
- 标准错误响应

`minimal_client` 是通用解码与同步基线，不要求实现完整聊天 UI、完整看板 UI、E2EE、Applet、Agent、WebRTC 或 MIMI。实现若只提供聊天或看板产品体验，SHOULD 额外声明 `chat_only_client` 或 `kanban_only_client`，避免把未实现对象误标为可用交互。

MAY 支持：

- 本地 reducer
- E2EE 解密
- 离线写入
- push notification

## 4. Full Client

`cx.profile.full_client.v1` 适用于桌面、Web 和移动主客户端。

MUST 支持 Minimal Client 的全部能力，并额外支持：

- 本地 event cache
- 本地 reducer
- 离线 event 队列
- 幂等重放
- Space bootstrap
- invite accept / reject
- read marker
- notification rule
- profile / presence / typing
- blob upload / download
- conflict UX

SHOULD 支持：

- local full-text search
- private account state
- multi-device sync
- export / backup

## 5. E2EE Client

`cx.profile.e2ee_client.v1` 适用于加密 Space。

MUST 支持 Full Client 的相关能力，并额外支持：

- MLS RFC 9420 group state
- KeyPackage publish / fetch / verify
- KeyPackage claim / consume / revoke lifecycle
- Welcome / Commit / Proposal event
- MLS-bound application state root verification
- minimal-metadata pseudonymous credential handling when profile is advertised
- AAD visibility policy handling
- epoch mismatch recovery
- encrypted payload envelope
- encrypted attachment envelope
- device revocation handling
- lost-device response
- local plaintext search for encrypted content

声明 `cx.profile.mls_state_binding.full.v1` 时，客户端和服务端 MUST 额外验证 MLS application state root 覆盖 membership、history visibility、plaintext-visible service、asset privacy、logging、bot / applet / agent policy、moderation policy 与 capability grant / revoke frontier。无法验证该 root 时，客户端 MUST fail closed，至少不得接受依赖未知应用状态的新 epoch。

MUST NOT：

- 把明文消息发送给 sync service / index
- 把解密密钥上传给不受信服务
- 在未验证 KeyPackage 所属 DID 的情况下加密给对方
- 在 MLS-bound policy / membership root 不匹配时继续解密正文

## 6. Principal Server Events API

`cx.profile.principal_server_events_api.v1` 适用于 Principal Server 暴露的 Event 提交、读取、回填和 frontier 查询 API。

MUST 支持：

- submit Event
- idempotent write
- event fetch
- event batch-get
- cursor-based history
- actor / Space frontier query
- signature verification
- schema validation
- capability precheck
- conflict reporting
- content-addressed blob reference validation

SHOULD 支持：

- snapshot generation
- witness receipt
- event batch receipt
- rate limiting
- quota accounting

## 7. Principal Server

`cx.profile.principal_server.v1` 适用于用户、组织或 agent principal 控制/委托的服务入口。

MUST 支持：

- subscribe / sync stream
- backfill
- client sync (`POST /sync`)
- cursor stability
- duplicate suppression
- encrypted payload forwarding
- authorization-aware routing metadata
- service describe
- service binding verification for federation destinations
- plaintext-visible service enforcement

SHOULD 支持：

- multi-upstream Principal Server federation
- quarantine queue
- witness receipt
- snapshot pointer distribution

Principal Server MUST NOT become the canonical truth source for Space state.
Principal Server MUST NOT forward non-E2EE private content or reversible derived plaintext to services absent from the relevant DID delegation or Space policy `plaintext_visible_services`.

## 8. Index Node

`cx.profile.index_node.v1` 适用于查询和物化节点。

MUST 支持：

- reducer profile declaration
- object current-state query
- relation query
- structured query
- notification / inbox materialization
- authorization filtering
- stale frontier reporting
- `X-Contrix-Wait-For` 或等价 sync token
- plaintext-visible declaration and policy enforcement when indexing private plaintext

SHOULD 支持：

- full-text search for plaintext Space
- local-only search coordination for encrypted Space
- explain / debug endpoint for reducer state

Index Node MUST NOT be treated as an authority unless its output can be traced to signed Event Envelopes and declared reducer profile.

## 9. Identity Registry Node

`cx.profile.identity_registry.v1` 适用于 DID 文档与 key log 服务。

MUST 支持：

- DID resolve
- DID log fetch
- DID operation submit
- `inception_key` verification
- `key_log` validation
- receipt publication
- method adapter metadata

SHOULD 支持：

- witness-only mode
- read replica mode
- raw DID document preservation
- normalized principal view

## 10. Blob Node

`cx.profile.blob_node.v1` 适用于内容寻址存储。

MUST 支持：

- upload
- download
- HEAD metadata
- SHA-256 digest verification
- size limit
- MIME metadata
- authorization-aware access
- asset privacy policy enforcement

SHOULD 支持：

- encrypted attachment metadata
- thumbnail / preview derivation
- provider proxy 或 OHTTP relay 下载模式
- GC grace period
- legal hold
- unsafe media flag

## 10.5 Push Gateway

`cx.profile.push_gateway.v1` 适用于移动端或桌面通知的推送网关。

MUST 支持：

- `register_device`
- `unregister_device`
- `notify`
- blind wakeup payload 最小化
- service DID 或等价受信服务签名校验
- 失效 token 回收
- `rejected[]` 结果回传

MUST NOT：

- 接收或存储消息明文
- 把 delivery receipt 当作 read receipt
- 以长期共享 token 作为多网关高可用方案

SHOULD 支持：

- per-gateway registration
- token 分片或短期授权
- 高优先级与静音规则透传

## 10.6 Applet Service / Bridge

`cx.profile.applet_service.v1` 适用于桥接外部系统和运行 Applet 集成服务。  

## 10.7 MIMI Interop Provider Facade

`cx.profile.mimi_interop.v1` 适用于需要与外部 MIMI provider 互通的 facade 服务。

MUST 支持：

- pinned MIMI draft version discovery
- `cx.mimi.room_binding` 生命周期校验
- MIMI provider directory 和 endpoint surface
- KeyPackage claim / consume / revoke lifecycle
- MIMI message 到 Contrix Event Envelope 的映射
- Contrix event 到 MIMI message / receipt 的映射
- room policy component 到 Contrix capability / policy state 的映射
- identifier query 的 private contact discovery
- consent state isolation
- E2EE abuse report franking
- asset privacy policy 下的 proxy / OHTTP 下载策略
- unsupported draft fail-closed

MUST NOT：

- 把 MIMI room id 当作 `space_id`
- 把 MIMI provider timestamp 当作 Contrix HLC / event creation truth
- 把 MIMI user identifier 当作 DID
- 绕过 Contrix auth refs、capability、MLS epoch 或 Space policy

## 11. Enterprise Client

`cx.profile.enterprise_client.v1` 适用于企业受控客户端。

MUST 支持 Full Client，并根据 policy 支持：

- OIDC / SSO gateway session grant
- device inventory
- admin-triggered device revocation
- auditable E2EE warning UI
- compliance audit event display
- managed update policy

MUST NOT 在不显示 policy 的情况下静默加入 auditable encrypted Space。

## 11.5 Sovereign Deployment

`cx.profile.sovereign_deployment.v1` 适用于军方、关键基础设施、金融核心、情报或其他高安全组织的自建/专属部署。

MUST support:

- Organization DID controlled service delegation
- service DID allowlist
- closed federation default
- private directory default
- controlled collaboration Space
- restricted or invite-only external join
- policy server `closed` or `quarantine` fail mode
- E2EE default for controlled collaboration
- MLS Welcome only to approved external devices
- external Applet / Agent / transport allowlist
- cross-domain event audit
- grant / invite / membership revocation
- MLS epoch rotation after external removal

MUST NOT:

- expose internal Space directory to external members
- treat external Principal Server / Index as authority
- allow public federation by default
- allow external Applet or Agent handoff without explicit capability and policy

SHOULD support:

- isolated collaboration enclave
- import/export review metadata
- data classification labels
- hardware-backed service keys
- offline witness receipts
- break-glass workflow with signed audit

## 11.6 Sovereign Client

`cx.profile.sovereign_client.v1` 适用于接入 sovereign deployment 的受控客户端。

MUST support:

- managed configuration signed by organization DID or governance service DID
- resolver trust domain pinning
- internal `did:uuid` resolution through approved registry / witness only
- service DID allowlist enforcement
- rejection of public registry / public directory for internal principals
- device posture check
- remote session and device revocation
- E2EE default
- classification and external member policy display
- local export controls
- audit log generation

MUST NOT:

- let users add arbitrary Principal Server / Index / Directory / Blob endpoints
- resolve internal `did:uuid` through public registry by default
- silently join Space with external members or auditable E2EE
- expose private organization directory to public search
- enable public search, Applet or Agent handoff unless policy allows

SHOULD support:

- hardware-backed device keys
- offline resolver bundles
- smart card / platform authenticator
- policy-controlled copy, screenshot and bulk export restrictions
- emergency wipe

## 11.7 Deployment Profiles

以下 deployment profile 用于发布与验收，不替代实现 profile：

- `cx.profile.personal_node.v1`
- `cx.profile.small_team.v1`
- `cx.profile.organization.v1`
- `cx.profile.high_security_organization.v1`
- `cx.profile.isolated_sovereign_network.v1`

`cx.profile.personal_node.v1` MUST cover：

- principal server、events、sync、index、blob 可以同机合并
- 默认最小管理员面
- 本地备份与恢复

`cx.profile.small_team.v1` MUST cover：

- 多用户共享 Space
- 基础目录与推送
- moderation queue
- snapshot / backfill

`cx.profile.organization.v1` MUST cover：

- organization DID 委托
- OIDC / account integration
- admin account lifecycle
- 审计导出

`cx.profile.high_security_organization.v1` MUST cover：

- service DID allowlist
- auditable E2EE 或受控 plaintext-visible boundary
- break-glass audit
- server ACL 和 quarantine

`cx.profile.isolated_sovereign_network.v1` MUST cover：

- 私有 registry / witness
- closed federation default
- 导入导出审查
- 外部服务与 applet allowlist

## 12. Agent Runtime

`cx.profile.agent_runtime.v1` 适用于 AI agent、bot、automation。

MUST 支持：

- DID 或 delegated actor identity
- explicit capability grant
- `cx.schema.agent_authority.v1` authority panel
- scoped action execution
- owner presence / trigger policy
- declared knowledge sources and memory visibility
- join policy that rejects owner-permission inheritance
- run log
- memory write policy
- accountability metadata
- kill switch / revocation check

SHOULD 支持：

- proposal mode for high-risk actions
- approval constraint
- deterministic replay metadata
- tool call audit envelope

## 13. Applet Service / Bridge

`cx.profile.applet_service.v1` 适用于桥接外部系统和运行 Applet 集成服务。

MUST 支持：

- signed `applet_registration`
- namespace declaration and matching
- ping / describe endpoint
- transaction push endpoint
- transaction idempotency
- query actor endpoint
- query space endpoint
- protocol metadata endpoint
- ghost actor accountability metadata
- portal Space metadata
- capability enforcement
- HTTP message signature verification
- event signature verification
- external event deduplication

MUST NOT：

- 把 namespace 命中当作写权限
- 静默 impersonate native user
- 在无授权时接收全网 sync stream
- 在未提示边界的情况下把 E2EE 内容桥接到非 E2EE 网络

SHOULD 支持：

- third-party user / location lookup
- bridge error event
- admin revoke / pause
- per-Space bridge policy
- Applet health and lag metrics

## 14. Conformance 测试要求

每个 profile SHOULD 提供：

- schema validation tests
- signature verification tests
- idempotency tests
- reducer convergence tests（含 state resolution 向量）
- state resolution state vectors（见 `state-resolution-conformance-vectors.md`）
- Event Envelope negative vectors（见 `artifacts/fixtures/event-envelope-negative-fixture.json` 与中文镜像）
- redaction vectors（见 `redaction-conformance-vectors.md`）
- capability vectors（见 `capability-conformance-vectors.md`）
- sync fixture、state-resolution fixture、capability fixture 和 privacy/security fixture（见 `artifacts/fixtures/*.json` 与中文镜像）
- authorization tests
- privacy regression tests
- error response tests
- downgrade / unsupported feature tests
- unknown-field preservation tests

所有 profile MUST 能按 `data-structures.md` 解码和验证其声明支持的核心对象字段。实现 MUST 在 canonical object 中保留未知 non-critical 字段，并覆盖“hash/signature 校验、存储、联邦转发、backfill 后字段仍存在”的测试；未知 critical feature MUST fail closed。实现 MUST reject 类型错误、必填字段缺失、非法 enum、非法 ID/hash/timestamp/cursor pattern，以及违反条件必填规则的对象。标准 Event 必须加载 `event-kind-registry.json` 与 `event-payload.schema.json`，确认每个 active durable kind 都有可执行 payload 校验路径。

所有 profile MUST 按 `encoding-conformance-vectors.md` 覆盖 canonical JSON、hash、signature binding、Ed25519 detached JWS fixture、HLC 和 cursor 的基础向量。Events API、Index、Full Client 与 E2EE Client MUST 额外覆盖 event digest；Events API 节点 SHOULD 覆盖 event-batch receipt digest；E2EE Client 和 Principal Server MUST 覆盖 encrypted envelope digest。

E2EE profile MUST 额外提供：

- KeyPackage verification vector
- KeyPackage claim single-use vector
- MLS-bound state root mismatch vector
- minimal-metadata identity link vector
- AAD visibility vector
- MLS epoch transition vector
- encrypted payload vector
- removed member cannot decrypt vector
- E2EE franking report vector

Client Sync 相关 profile MUST/SHOULD 按 `sync-conformance-vectors.md` 执行对应向量：

- Minimal Client MUST 覆盖基础排序、tie break、pagination gap、backfill order 和 token expiry recovery。
- Chat-only Client MUST 覆盖 Room timeline、message edit/redaction、reaction OR-Set、Room history visibility 和 linked Room 裁剪。
- Kanban-only Client MUST 覆盖 Board projection、Card move/reorder、position edge conflict、CAS stale reorder 和 wait-for query。
- Full Client MUST 额外覆盖 snapshot frontier、state_after 与 decryption_pending 的 UI / cache 恢复行为。
- E2EE Client MUST 覆盖 MLS epoch backfill、decryption_pending recovery 和 removed member fail closed。
- Index Node MUST 覆盖 deterministic timeline order、causal barrier 和 stale frontier reporting。
- Principal Server SHOULD 覆盖 duplicate suppression、backfill order、encrypted payload forwarding 和不能转发解密材料。
- Snapshot bootstrap MUST 覆盖 `event_set_commitment` root、covered frontier、conflict/soft-fail/quarantine 摘要和 inclusion / omission challenge hint。

Privacy / security hardening profile MUST 额外覆盖：

- hidden Space resolve 的不可见/不存在响应同形态
- private contact discovery 的 batch padding 与 cardinality protection
- plaintext-visible service 对私有正文处理的强制拒绝
- private blob HEAD / Range anti-enumeration
- blind wakeup push payload 最小披露

Moderation profile MUST 额外覆盖：

- `cx.schema.moderation_report.v1`
- `cx.schema.moderation_queue_item.v1`
- `cx.moderation.report` payload schema validation
- E2EE evidence package / frank 只向授权 moderation recipient 披露

Identity profile MUST 额外提供：

- `did:uuid` bit layout vector
- `inception_key` hash vector
- key rotation vector
- recovery vector
- pairwise DID unlinkability checks

Applet Service / Bridge profile MUST 额外提供：

- registration signature vector
- namespace conflict vector
- duplicate transaction vector
- ghost actor mapping vector
- portal Space mapping vector
- unauthorized write rejection vector

MIMI Interop profile MUST 额外提供：

- provider directory draft pinning vector
- room binding projection vector
- content roundtrip vector
- identifier query privacy vector
- consent isolation vector
- proxy download policy vector
- unsupported draft fail-closed vector

## 15. Feature Discovery 示例

```json
{
  "service_did": "did:web:index.example.com",
  "service_type": "ContrixIndex",
  "protocol_version": "1.0",
  "supported_profiles": [
    "cx.profile.index_node.v1"
  ],
  "supported_features": [
    "structured_query",
    "notification_index",
    "wait_for_sync_token"
  ],
  "reducer_profiles": [
    "cx.reducer.v1"
  ],
  "schema_profiles": [
    "cx.schema.event.v1"
  ]
}
```

## 16. 初版决定

首个互操作目标 SHOULD 是：

- `minimal_client`
- `chat_only_client`
- `kanban_only_client`
- `principal_server_events_api`
- `principal_server`
- `federation_minimal`
- `index_node`
- `identity_registry`
- `blob_node`
- `push_gateway`
- `applet_service`
- `mimi_interop`

`full_client` 和 `e2ee_client` 是产品可用性的目标 profile。  
`enterprise_client` 和 `agent_runtime` 是高价值扩展 profile，但不应阻塞基础互操作。
