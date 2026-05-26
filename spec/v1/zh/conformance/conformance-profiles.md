---
title: 实现 Profile 与一致性要求
status: candidate
normative: true
stability: v1
updated: 2026-05-25
sidebar:
  label: 实现 Profile
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

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
- `cx.profile.principal_server_events_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.federation_minimal.v1`
- `cx.profile.mimi_interop.v1`

## 2.1 v1 MVP 分层

为降低实现复杂度，v1 profile 分为三个声明层。`artifacts/profiles/conformance-profiles.json.profile_tiers` 是机器可读来源；`v1_profile_catalog` 不是 bundle requirement，实现只声明自己实际支持的 profile、event kind、schema 和 operation。

| 层级 | 含义 | 典型内容 |
| --- | --- | --- |
| Minimal interop floor | 仅声称 v1 Event Store interop 时的最小声明。 | `cx.profile.core_event_store.v1`：Event Envelope、per-actor event chain、events submit/get/list/frontier/backfill、标准错误。 |
| Stable profile catalog | v1 stable catalog 中可独立声明的实现 profile，不构成默认全量包。 | `chat_mvp`、`kanban_mvp`、`minimal_client`、`full_client`、`principal_server`、`identity_registry`、`blob_node`、`push_gateway`、`federation_minimal`、`sovereign_client` 等。 |
| Extension（v1 lattice / interop） | 在 v1 stable catalog 中可独立声明，但**只在显式 opt-in 时启用**。未声明的实现遇到这些能力 MUST fail closed。 | `cx.profile.collaborative_text.v1`（lww_register / rga lattice 扩展）、`cx.profile.matrix_compat.v1`（Matrix 兼容声明：to-device / `/keys/*` / push gateway / cross-signing / SAS 与 Matrix 等价语义；账号聚合不声明 Matrix `/sync` wire parity）。 |
| Interop staging extension | **不属于 v1 core interop floor**，跟踪外部演进标准；声明 v1 core 的实现 MAY 完全省略。 | MIMI interop、Applet integration、Agent protocol bridge、TSP integration 等；这些 profile 在外部标准定型后将被稳定版本固定取代。 |

Document、File、Poll 在 v1 MVP 中默认是 Morph profile 或 extension profile，不是 core 标准对象。实现不得因为未来可能标准化这些类型，就在 v1 wire contract 中要求对端支持专用对象类型。

Core identity conformance 要求 DID Core 解析 / 验证抽象、`did:webvh`（v1 core 默认 principal method）、`did:web`（service DID / `personal_node` profile principal）与 `did:key`。所有声明 `cx.profile.principal_server.v1` / `cx.profile.full_client.v1` / `cx.profile.e2ee_client.v1` 的实现 MUST 支持 `did:webvh` witness / SCID / entry hash chain 验证。组织高保证实现 SHOULD 声明 `cx.profile.org_high_assurance_identity.v1` 并要求 `did:webvh` witness / watcher evidence 强制 threshold ≥ 1。AT Protocol 互通实现 SHOULD 额外声明 `cx.profile.public_network_identity.v1` 并支持 `did:plc` adapter；该 adapter 是 interop 加项，不是 Contrix Core 强制依赖。

v1 的首轮互操作验收 SHOULD 拆成三个可运行闭环：

- `cx.profile.core_event_store.v1`：DID / service discovery、Event Envelope validation、event submit/fetch/backfill、per-actor event chain validation、idempotent duplicate handling、standard error。
- `cx.profile.chat_mvp.v1`：在 `core_event_store` 之上支持 Realm、`cx.member.state`、启用 discussion track 且可设为 primary 的 Flow、Message、Reaction、Redaction、Client Sync timeline 和 history visibility。
- `cx.profile.kanban_mvp.v1`：在 `core_event_store` 之上支持 Space（`kind=board/list`）、Flow、`contains` position Relation、`cx.flow.move`、`cx.flow.reorder`、`cx.space.create`、`cx.space.update`、`cx.space.parent`、客户端 Collection projection 和 wait-for query。

`minimal_client`、`full_client`、`principal_server` 等实现 profile 通过声明所支持的闭环（`chat_mvp` / `kanban_mvp`）表达能力；未声明的闭环不得被对端视为默认可用。希望仅做聊天产品而不实现 board/list 的客户端，应声明 `chat_mvp` 而不实现 `kanban_mvp`，并在 `rejected_event_kinds` 中明确拒绝 board/list 相关 kind。

`chat_mvp` 与 `kanban_mvp` 不要求实现任意 Morph renderer、任意 facet reducer 或插件 UI。它们只需要按声明 profile 保留未知 Morph / facet 字段、同步相关 Event、执行 schema/capability 校验，并在必须展示时提供 generic Morph fallback。任何依赖特定 `morph_type` 或 facet 的交互能力 MUST 由额外 profile 显式声明。

Profile 不支持某个标准能力时的默认行为：

- 写入接收方收到 active 标准 Event kind 时，若该 kind 不在本实现声明的 supported_event_kinds / profile 范围内，且该实现负责该 Realm 的 accepted history，MUST 返回 `unsupported_feature`、`unsupported_event_kind`、`schema_violation` 或 quarantine，不得把未知标准事件 accepted 后静默丢给 reducer。
- 只读客户端或 projection 服务遇到未实现但已 accepted 的标准 Event kind，MAY 保留 raw event、显示 generic fallback 或把对应 projection 标记为 incomplete；不得声称已完整执行该 kind 的 reducer 语义。
- 未知 Morph type、未知非 critical extension field 和未声明 renderer 可以保留并忽略，但不能影响授权、排序、状态机、redaction、E2EE、notification 或 state hash。
- Event 的 `requirements.features[]` 或 `requirements.critical_extensions[]` 出现不支持的标识，或 `requirements.schema[]` / `requirements.reducer` 与本端不匹配时，不支持的一方 MUST fail closed；这条规则优先于 profile 的“可忽略可选功能”。
- `rejected_event_kinds` 表示 profile 必须拒绝或不接收的 wire scope / kind。`optional_extensions` 表示可以不提供交互能力；它不授权实现静默接受依赖该 extension 的 critical Event。

机器可读默认行为见 `artifacts/profiles/conformance-profiles.json.default_unsupported_behavior`。其中 `must_not_accept`、`must_fail_closed`、`allowed_results` 等字段用于 conformance lint / test，而不是自由文本提示。

Profile 之间的 `inherits` / `depends_on` / `mutually_exclusive_with` 关系以 DAG 形式集中聚合在 [`artifacts/registry/profiles-dependency-graph.json`](../../artifacts/registry/profiles-dependency-graph.json)（canonical mirror，每次新增或修改 profile 关系时 MUST 同步）。该 graph 用于可视化 DAG 工具与 conformance loader：实现 SHOULD 先按 `inherits` 边做拓扑排序，再按 `depends_on` 检查共生约束，最后按 `mutually_exclusive_with` 检查冲突；任一阶段失败 MUST 拒绝 profile claim。

### 2.1.1 Profile 数量约束与 Composition 路线（normative for new profiles）

v1 stable + extension catalog 已包含较大的 implementation / deployment / vector / hardening profile 矩阵，组合空间已经较大。为防止 profile 数量进一步爆炸，**新增 implementation profile MUST 满足**以下条件之一：

1. **Capability composition**：新 profile 仅是 "base profile + 一组明确 facet（通过 `requirement_blocks` 引用现有 capability、event_kind、schema、operation 集合）"，不引入未见过的能力。其 `inherits` 字段 MUST 指向已存在的 base profile，`adds` 字段 MUST 是 base 之外明确列出的最小 delta。这种 profile 无需独立 conformance vector，复用 base profile vectors + delta vectors。
2. **新能力闭环**：引入全新能力（例如新对象类型、新 lattice family、新 transport binding），同时提交至少一个独立 conformance vector 与 fixture。

不满足两条之一的 profile 提案 MUST 被 reviewer 拒绝；现有 profile 不重组，但新 profile 必须按 composition 形态提出。`requirement_blocks` 已经支持声明引用，可形式化为 `compose: { base: <id>, adds: [<requirement_block_ref>...] }` 字段——该 reserved slot 已留出，但不强制现有 profile 迁移。

实现侧：客户端 SHOULD 在 conformance 声明中暴露 `inherits` 与 `adds` 信息，让对端能在 fast path 中按继承关系做能力命中判断，避免逐 profile 列举。

## 2.2 场景化 Profile

以下 profile 用于把 v1 启动范围降到可实现的产品子集。它们不是 `minimal_client` 的替代品，而是面向具体产品形态的互操作声明。声明 `cx.profile.chat_mvp.v1` 或 `cx.profile.kanban_mvp.v1` 时，仅实现一个闭环的实现 SHOULD 在 `rejected_event_kinds` 中列出本实现拒绝的另一闭环 wire scope。

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
- 事件/关系/对象/View 的 `created_at`、`realm_id`、`proof`、`hlc`、`actor_seq`、`prev_refs` / `refs[role=authorized_by]` 在 reducer 与验证逻辑中不能被跳过；版本通过 `Event.requirements.{schema, reducer}` 表达。
- `auth` 约束必须执行，不得通过客户端配置豁免。
- State frontier、snapshot frontier、projection frontier 和 wait-for token MUST 以 `event_id` / actor frontier 为语义单位；`operation_id` 只可表示服务 canonical operation。
- Snapshot manifest MUST 包含 `event_set_commitment`；high-assurance profile MUST 支持 inclusion / omission challenge 或 witness quorum 校验。
- 裸名事件（如 `realm.create`）MUST 被拒绝，不能作为新增标准互操作行为。
- 实现 MUST 对 `causal` 关系、`revoked` 与 `proof` 失效状态进行一致性拒绝（fail-closed），不能“静默接受”。

## 4. Minimal Client

`cx.profile.minimal_client.v1` 适用于只读或轻量写入客户端。

MUST 支持：

- DID / handle 解析
- service discovery
- event 拉取 / backfill
- 本地查询和 projection
- 基础 Flow / Realm / Message / Morph / Relation / Event 解码
- 未知 Morph / facet 字段保留和 generic fallback，不要求专用 renderer
- capability 检查结果处理
- cursor 分页
- 标准错误响应

`minimal_client` 是通用解码与同步基线，不要求实现完整聊天 UI、完整看板 UI、E2EE、Applet、Agent、WebRTC 或 MIMI。实现若只提供聊天或看板产品体验，SHOULD 直接声明 `chat_mvp` 或 `kanban_mvp`，并在 `rejected_event_kinds` 中明确拒绝未实现的 wire scope，避免把未实现对象误标为可用交互。

MAY 支持：

- 本地 reducer
- E2EE 解密
- 离线写入
- push notification

## 5. Full Client

`cx.profile.full_client.v1` 适用于桌面、Web 和移动主客户端。

MUST 支持 Minimal Client 的全部能力，并额外支持：

- 本地 event cache
- 本地 reducer
- 离线 event 队列
- 幂等重放
- Realm bootstrap
- invite accept / reject
- read cursor
- notification rule
- profile / presence / typing
- blob upload / download
- conflict UX

SHOULD 支持：

- local full-text search
- private account state
- multi-device sync
- export / backup

## 6. E2EE Client

`cx.profile.e2ee_client.v1` 适用于加密 Realm。

MUST 支持 Full Client 的相关能力，并额外支持：

- MLS RFC 9420 group state
- KeyPackage publish / fetch / verify
- KeyPackage claim / consume / revoke lifecycle
- Welcome / Commit / Proposal event
- MLS Governance Binding：`governance_binding` 的 GroupContext extension 验证 + `covered_frontier_cell` 的 reducer 累积
- minimal-metadata pseudonymous credential handling when profile is advertised
- AAD visibility policy handling
- epoch mismatch recovery
- encrypted payload envelope
- encrypted attachment envelope
- encrypted key backup object and backup CRUD for `did_recovery` / `secret_storage` / `mls_history`
- device revocation handling
- lost-device response
- local plaintext search for encrypted content

声明 `cx.profile.mls_governance_binding.full.v1`（即 MLS Governance Binding 的 full 形态，见 `crypto-media/encryption-and-audit.md §2.5`）时，客户端和服务端 MUST 额外验证 commit 携带的 `governance_binding` 覆盖 membership、history visibility、plaintext-visible service、asset privacy、logging、bot / applet / agent policy、moderation policy 与 capability grant / revoke frontier，并 MUST 通过 `covered_frontier_cell` precondition gate E2EE message Move。无法验证 `governance_binding` 指向的 Anchor view 时，客户端 MUST fail closed，至少不得接受依赖未知应用状态的新 epoch。

声明 `cx.profile.attested_audit.e2ee.v1` 时，Audit Agent MUST 提供可验证 remote attestation，并执行 `cx.audit.accessed` 先写后解密、RYW receipt 等待和成员可见 disclosure；RYW receipt 的 `audit_assurance_class` MUST 等于 `attested_hardware`。声明 `cx.profile.disclosed_audit.e2ee.v1` 时，不要求 TEE attestation，但 Realm policy 和加入 UI MUST 明确展示该降级（按 `encryption-and-audit.md §3.1.1` 的 disclosed 文案）；同样不得绕过 `cx.audit.accessed` 留痕流程；RYW receipt 的 `audit_assurance_class` MUST 等于 `disclosed_policy`。两个 profile 不再共享 family 前缀，对外材料 MUST 遵守 `encryption-and-audit.md §3.5` 的禁用措辞条款，不得将 disclosed 类宣传为密码学/硬件强制审计。

MUST NOT：

- 把明文消息发送给未授权 sync service 或受托 search / projection 服务
- 把解密密钥上传给不受信服务
- 在未验证 KeyPackage 所属 DID 的情况下加密给对方
- 在 `governance_binding` 的 policy / membership root 不匹配时继续解密正文（违反 MLS Governance Binding）

## 7. Principal Server Events API

`cx.profile.principal_server_events_api.v1` 适用于 Principal Server 暴露的 Event 提交、读取、回填和 frontier 查询 API。

MUST 支持：

- submit Event
- idempotent write
- event fetch
- event resolve (batch dereference by ID / hash)
- cursor-based history
- actor / Realm frontier query
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

## 8. Principal Server

`cx.profile.principal_server.v1` 适用于用户、组织或 agent principal 控制/委托的服务入口。

MUST 支持：

- subscribe / sync stream
- backfill
- account-aggregate streaming subscription (`GET /account/subscribe`)
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

Principal Server MUST NOT 成为 Realm 状态的 canonical 真相源。
Principal Server MUST NOT 将非 E2EE 的私有内容或可还原的派生明文转发给未列入相应 DID 委托或 Realm policy `plaintext_visible_services` 的服务。

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

## 9a. Auth Server

`cx.profile.auth_server.v1` 适用于负责登录因子验证、短期会话授权与 session-grant 生命周期管理的服务（reference implementation：`coauth`）。

MUST 支持：

- service describe（`cx.server.describe`）
- `cx.account.issue_session_grant` / `/auth/account/session-grants` 的规范化签发路径
- 至少一种登录因子（password / passkey / OIDC / SSO / device pairing / recovery challenge）
- 短期、audience-bound `cx.session.grant` 签发
- session_grant TTL 上限远低于 Realm policy review horizon（minutes-to-hours，不得跨越多日）
- session_grant audience 绑定与拒签陌生 audience
- `auth_metadata`（issuer DID、`supported_auth_methods`、`token_endpoint_auth_methods`、`session_grant_scope`、`required_audience`）

SHOULD 支持：

- session-grant introspection 与 revocation
- `cx.account.issue_session_grant` 规范化 HTTP binding
- `cx.policy.check`（v2 PolicyCheckResponse）
- 多 principal-server delegation target 配置
- did binding / claim attestation

Auth Server MUST NOT 声明 `cx.profile.identity_registry.v1`、`cx.profile.principal_server.v1` 或 `cx.profile.directory_service.v1`。任何 DID document / key-log 表面 MUST 通过 `compat_surfaces[]` 以 `delegated_resolver` 形式声明，而非自我声称 canonical 权威。

Auth Server MUST NOT 把成功的 OIDC / SSO / password 验证直接当作 DID 控制证明；下游资源服务器仍 MUST 重新验证 DID control state（见 `guides/migrating-from-matrix.md`）。

`development_mode=true` 时，`verified_profiles[]` MUST 为 `[]`（见 `sync/service-surface.md` §3.0）；cotest 在 verified-profile suite 通过后才能写入 verified entry。

Release readiness MUST 至少覆盖：签发路径拒绝陌生 audience、session grant TTL 上限、proof 绑定 `challenge` / `audience` / `request_canonical_digest` / principal / device、`soft_logged_out` 恢复需要 fresh DID proof，以及 development mode 下不得声明 verified profile。对应 conformance vector 为 `cx.vector.auth.session_grant_audience_binding.v1` 与 `cx.vector.auth.soft_logout_did_proof.v1`。

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

## 11. Push Gateway

`cx.profile.push_gateway.v1` 适用于移动端或桌面通知的推送网关。Push gateway 实现 MUST 同时满足下方拆分的三个子 profile 之一或多个组合（默认基线为 blind wakeup，visible / matrix 互通为 opt-in）。

| Profile id | role | 必选 / 可选 | 强制能力 | Fixture |
| --- | --- | --- | --- | --- |
| `cx.profile.push_gateway.v1` | `gateway` | 实现网关时必选；MUST `depends_on` `blind_wakeup` | `register_device` / `unregister_device` / `notify` 三个操作，`cx.schema.notification.v1`，service DID 校验，`rejected[]` 回传，失效 token 回收 | `privacy-security-fixture.json` |
| `cx.profile.push_gateway.blind_wakeup.v1` | `gateway` | **默认互操作安全基线**：声明 `push_gateway.v1` 即 MUST 声明 | provider 出向 payload 仅含 `push_target_id`（pairwise pseudonym，按 [`crypto-media/device-lifecycle.md` §5a](../crypto-media/device-lifecycle.md)）+ 封闭枚举的 `wakeup_kind` / `badge_count` / `unread_increment` / `l10n_key`；MUST NOT 携带 principal DID、sender DID / handle、Realm / Flow / Message id、event id、device DID URL、reaction 实际值、附件文件名、跨 Realm stable correlation key、IP / geolocation | `privacy-security-fixture.json` |
| `cx.profile.push_gateway.visible_notification.v1` | `gateway` | Opt-in；仅在 Realm policy 列入 `plaintext_visible_services` 且声明 `visible_notification` allowance、接收设备 opt-in、UI 显式标示时声明 | 维持 blind wakeup 之上扩展的最小可见字段集合；MUST NOT 携带正文、DID URL、跨 Realm stable correlation key、IP / geolocation 或未列入 profile 的自由文本；E2EE 默认实现不得依赖该 profile | `privacy-security-fixture.json` |
| `cx.profile.push_gateway.matrix_passthrough.v1` | `interop` | Opt-in；Matrix 互通桥接 | 在与 `cx.profile.matrix_compat.v1` 并行的前提下，按 Matrix push gateway 形态承载 passthrough payload；MUST 与 `blind_wakeup.v1` 流量分区，**MUST NOT** 在同一 `(recipient_service_did, device)` 元组上同时声明两者 | `privacy-security-fixture.json` |

MUST 支持（在所有变体上）：

- `register_device`
- `unregister_device`
- `notify`
- blind wakeup payload 最小化（默认基线）
- service DID 或等价受信服务签名校验
- 失效 token 回收
- `rejected[]` 结果回传

MUST NOT：

- 接收或存储消息明文
- 把 delivery receipt 当作 read receipt
- 以长期共享 token 作为多网关高可用方案
- 把 `blind_wakeup` 当作可省略的 optional extension（违反默认安全基线）
- 在同一投递元组上混用 `blind_wakeup.v1` 与 `matrix_passthrough.v1`

SHOULD 支持：

- per-gateway registration
- token 分片或短期授权
- 高优先级与静音规则透传

## 12. Applet Service / Bridge（概要）

详见第 19 节完整定义。

## 13. MIMI Interop Provider Facade

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

- 把 MIMI room id 当作 `realm_id`
- 把 MIMI provider timestamp 当作 Contrix HLC / event creation truth
- 把 MIMI user identifier 当作 DID
- 绕过 Contrix auth refs、capability、MLS epoch 或 Realm policy

## 14. Enterprise Client

`cx.profile.enterprise_client.v1` 适用于企业受控客户端。

MUST 支持 Full Client，并根据 policy 支持：

- OIDC / SSO gateway session grant
- device inventory
- admin-triggered device revocation
- auditable E2EE warning UI
- compliance audit event display
- managed update policy

MUST NOT 在不显示 policy 的情况下静默加入 auditable encrypted Realm。

## 15. Sovereign Deployment

`cx.profile.sovereign_deployment.v1` 适用于军方、关键基础设施、金融核心、情报或其他高安全组织的自建/专属部署。

MUST 支持：

- 组织 DID 控制的服务委托
- 服务 DID allowlist
- 默认 closed federation
- 默认私有目录
- 在 sovereign deployment 下 External Collaboration Realm 的强制 policy（见 [`models/realm-and-space.md` §2.7](../models/realm-and-space.md) 与 [`sync/sovereign-deployment.md` §4](../sync/sovereign-deployment.md)）
- restricted 或 invite-only 外部加入
- Policy Server `closed` 或 `quarantine` 失败模式
- sovereign deployment 下 External Collaboration Realm 默认 E2EE
- MLS Welcome 只发给已批准的外部设备
- 外部 Applet / Agent / transport allowlist
- 跨域事件审计
- grant / invite / membership 撤销
- 外部成员移除后 MLS epoch 轮换

MUST NOT：

- 向外部成员暴露内部 Realm 目录
- 将外部 Principal Server 或 search / projection 服务视为权威
- 默认允许公共 federation
- 在无显式 capability 和 policy 时允许外部 Applet 或 Agent handoff

SHOULD 支持：

- 隔离协作 enclave
- 导入导出审查元数据
- 数据分类标签
- 硬件保护的服务密钥
- 离线 witness receipt
- 带签名审计的 break-glass 流程

## 16. Sovereign Client

`cx.profile.sovereign_client.v1` 适用于接入 sovereign deployment 的受控客户端。

MUST 支持：

- 由组织 DID 或治理服务 DID 签名的托管配置
- Resolver 信任域钉扎
- 仅通过已批准 resolver / witness / watcher 解析内部 DID
- 服务 DID allowlist 执行
- 拒绝内部 principal 的公共 registry / 公共目录
- 设备状态检查
- 远程 session 和设备撤销
- 默认 E2EE
- 分类标签与外部成员策略展示
- 本地导出控制
- 审计日志生成

MUST NOT：

- 允许用户添加任意 Principal Server / Directory / Blob endpoint
- 默认通过公共 resolver endpoint 解析内部 principal
- 静默加入包含外部成员或可审计 E2EE 的 Realm
- 向公共搜索暴露私有组织目录
- 在 policy 未允许时启用公共搜索、Applet 或 Agent handoff

SHOULD 支持：

- 硬件保护设备密钥
- 离线 resolver bundle
- 智能卡 / 平台认证器
- Policy 控制的复制、截图和批量导出限制
- 紧急擦除

## 17. Deployment Profiles

以下 deployment profile 用于发布与验收，不替代实现 profile：

- `cx.profile.personal_node.v1`
- `cx.profile.small_team.v1`
- `cx.profile.organization.v1`
- `cx.profile.high_security_organization.v1`
- `cx.profile.isolated_sovereign_network.v1`

`cx.profile.personal_node.v1` MUST cover：

- principal server、events、sync、blob 可以同机合并
- 默认最小管理员面
- 本地备份与恢复

`cx.profile.small_team.v1` MUST cover：

- 多用户共享 Realm
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

## 18. Agent Runtime

`cx.profile.agent_runtime.v1` 适用于 AI agent、bot、automation。

MUST 支持：

- DID 或 delegated actor identity
- explicit capability grant
- scoped action execution
- owner presence / trigger policy
- declared knowledge sources
- join policy that rejects owner-permission inheritance
- protocol session audit metadata
- accountability metadata
- kill switch / revocation check

SHOULD 支持：

- proposal mode for high-risk actions
- approval constraint
- deterministic replay metadata
- tool call audit envelope

### 18.1 Personal Agent Provisioning (CXP-0008)

`cx.profile.personal_agent_provisioning.v1` 注册 controller-面的 personal native agent management surface,扩展 `cx.profile.agent_runtime.v1`。

MUST 支持:
- `POST /api/v1/agents` (`cx.agent.provision`) 编排 Actor Profile + `cx.identity.accountability_grant` + 初始 `cx.capability.grant`(带 `effective_after_first_authorized_key=true` flag)+ pairing request
- `POST /auth/account/agent-key-pair` (`cx.account.agent_key_pair`) 校验 `verification_method` 与 `agent_principal_id` 一致性后写入 `cx.agent.key.authorize`,清除 effective_after_first_authorized_key
- Provisioning `status` 枚举:`pending_runtime_key` / `active` / `paused` / `pairing_expired` / `deactivated`
- Pairing expiry 自动 `cx.capability.revoke` pending grants
- Agent management operations(list/get/pause/resume/revoke/rotate-key/grant attach/detach)写入 durable lifecycle events
- Draft-only family:`cx.agent.draft.propose` / `cx.agent.action_request` / `cx.agent.action_approve` / `cx.agent.action_reject`,materialize 为 controller-owned `cx.agent.draft.v1` encrypted account-data
- Draft approval 状态机:`proposed → approved → published`,approval nonce atomic consume
- Event Envelope `executed_by` / `authorization_ref` / reducer-stamped `actor_kind` projection
- Pause/Resume/Deactivate 语义(见 [`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md))
- Controller deactivate / suspend 时,accountable native agents 的 active sessions revocation 链失效
- Sidecar exposure 披露:激活新 agent 前 UI MUST 显式披露其将获得现有 sidecar 访问权(联动 CXP-0009)

MUST NOT:
- 注册独立 `cx.agent.provision` aggregate durable event(provisioning operation fan-out 到既有子事件)
- 返回长期 private key、refresh token 或可直接长期调用 Events API 的 bearer token
- 引入 custom URI scheme(`contrix://` 等)

### 18.2 Agent Auth (CXP-0008)

`cx.profile.agent_auth.v1` 注册 agent runtime 的 authentication surface,与 `cx.profile.personal_agent_provisioning.v1` 解耦。

MUST 支持:
- 复用 `POST /auth/account/session-grants` 通过 `proof.proof_kind="agent_key_proof"` 分支
- 独立 schema branch、独立 proof validator、独立 returned scope(交集 from agent key authorization / capability grant / Realm policy / requested scope)
- `agent_scope_request` overlay 与 `scope_details` response overlay
- key proof 绑定 challenge / audience / request canonical digest / agent principal / `verification_method` / nonce / expiry
- Replay table 覆盖 proof `expires_at` 后的 grace window
- Session TTL 默认 ≤ 15 分钟,profile 可声明更长但 ≤ 60 分钟
- Structured human approval request 返回(`code=claim_required` / `reason_code=human_approval_required` / `approval_request_id`),不向 agent runtime 展示 CAPTCHA / OTP

MUST NOT:
- 把 `agent_key_proof` 降级走 password / OIDC / passkey validator fallback
- 在 session grant 中授予 E2EE history key、secret storage 或长期 device 权限
- 把 controller 进入 `deactivated` / `suspended` 后的 agent session 视为有效

### 18.3 Agent Delegation Policy (CXP-0008)

`cx.profile.agent_delegation_policy.v1` 注册 capability vocabulary 与 act-on-behalf attribution 规则。

MUST 支持:
- Effective permission rule:`controller-approved grant AND controller's own delegable authority AND Realm policy AND resource selector / constraints AND agent key scope AND requested session scope AND current revocation / freshness state`,默认拒绝 wildcard
- Canonical constraint vocabulary:`allowed_tracks` / `allowed_flow_refs` / `allowed_data_classes` / `allowed_endpoints` / `rate_limit` / `approval_required` / `controller_approval_required` / `accountability_required`
- Reply-as-agent 与 act-on-behalf wire(`actor_id` / `executed_by` / `authorization_ref`)与双重署名渲染
- act-on-behalf 默认 fresh approval 粒度 `(action, target_flow)` + 短期 temporal window
- Realm policy 必须能分别控制 native personal agent 与 Applet / Ghost Actor

MUST NOT:
- 让 agent 自动继承 controller 在 Realm 内的最大权限
- 把 `act_on_behalf_allowed` 当作 constraint;它由 attribution + capability + approval 组合表达

### 18.4 Agent Sidecar Thread (CXP-0009)

`cx.profile.agent_sidecar_thread.v1` 注册 controller 与 controller 的 native AI agents 之间的私聊上下文线程。依赖 CXP-0007 / CXP-0008。

MUST 支持:
- `POST /api/v1/agent-sidecar-threads:ensure` (`cx.agent.sidecar_thread.ensure`) idempotent operation,返回 `{ok, private_circle_id, private_flow_id, private_relation_id, pending_member_reconciliation?}`
- `context_ref` polymorphic descriptor(`relation_id` 单独 / `flow_id` 加可选 `track` + 可选 anchor)
- Closed request schema(reject unknown top-level fields)
- Fixed reuse:Flow `(controller_principal_id, normalized_context_ref)`、Circle `(realm_id, controller_principal_id)`
- 派生 `controller_agent_circle_key`(canonical realm_id + canonical DID + UTF-8 + SHA-256 + base32 + 24 字符小写)
- Sidecar Circle `display.short_name = "AI-" + controller_agent_circle_key[:12].upper()`,short_name 碰撞且 caller 非 member 时 generic `failed_precondition` `reason=sidecar_create_denied`
- `eligible_sidecar_agent(realm, controller, agent)` predicate;Circle membership 主动 fan-out `cx.circle.member.state`(不被动 reconcile)
- Eligibility / MLS membership 三态(eligible+active / pending join / not eligible)
- `addressed_agent_principal_ids[]` per-ensure ephemeral(服务端不持久化);MUST 不包含 controller 自身
- 历史 backfill 经由 application-level resend(显式 plaintext 披露)而非 MLS exporter secret
- Cross-Realm fan-out:agent deactivate 只影响该 agent 实际所在的 sidecar Circles
- `agent_sidecar_of` relation kind(weak-semantic、non-structural、non-cascading);`fields` 不含 `target_realm_id`
- Sidecar private Flow 不出现在 Realm-wide navigation / board / list / public search(profile-specific reducer rule:`scope_circle_id` 指向 sidecar Circle 的 Flow 过滤)
- 多 agent publish 时 `actor_id` / `executed_by` MUST 是单一签发 agent principal
- Retention 继承目标 Realm,profile 可收紧不可放宽
- `cx.agent.sidecar_projection.v1` controller-private encrypted account-data SHOULD 注册(跨设备 UI 一致性)

MUST NOT:
- 在目标公开 Flow 写 target-side reverse `agent_sidecar_of` relation
- 修改目标 Flow `tracks` map 或写入 target-side metadata / Relation / watch / unread / search / notification state
- 接受 `participant_model` 等替代 reuse 字段;invariant 9 是 v1 取舍
- 为单个 sidecar 偷偷创建第二个 Circle 以绕开 invariant 9

## 19. Applet Service / Bridge

`cx.profile.applet_service.v1` 适用于桥接外部系统和运行 Applet 集成服务。

MUST 支持：

- signed `applet_registration`
- namespace declaration and matching
- ping / describe endpoint
- transaction push endpoint
- transaction idempotency
- resolve actor endpoint
- resolve realm endpoint
- protocol metadata endpoint
- ghost actor accountability metadata
- portal Realm metadata
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
- per-Realm bridge policy
- Applet health and lag metrics

## 19a. Franking (E2EE Abuse Reporting)

`cx.profile.franking.v1` 适用于在 E2EE Realm 中提供可验证投递证明的服务（典型为 Sync Service / MIMI provider facade / Principal Server）。

参考：`governance/content-moderation.md` §3.4 与 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) franking 段落。

MUST 支持：

- 在接收 E2EE Event Envelope 时签发 `cx.moderation.franking_proof` 事件，绑定 `event_id`、`ciphertext_digest`、`aad_digest`、`sender_claim` (含 mls_group_id + epoch)、`received_by` (service DID)、`received_at`、`replay_nonce`。
- franking proof `signature` 由 service DID 当前有效 verification method 签发，覆盖 franking proof canonical bytes。
- 每条 franking proof 必须可被独立 verify：service DID Document 解析 + verification method 有效期 + Realm service binding 校验 + payload hash 重算。
- 接收 reporter 提交的 `cx.moderation.report` 时，把 franking proof ID 与 report ID 绑定为审计链一部分；不得仅信 reporter 单方声称。
- franking proof cache TTL 与 service key rotation 同步：service DID 的 verification method 撤销后，旧 franking proof 仍可历史验证（用历史 key state），但不签发新 franking proof。

MUST NOT：

- 在 franking proof 中包含明文正文、附件文件名、reply 摘录、mention 列表、私有 handle 或解密内容 hash，除非 Realm policy 显式允许该字段。
- 用 franking proof 单独证明明文含义——franking proof 只证明"该密文事件被该 service 在该时间收到"。
- 跨 Realm 复用同一 franking proof（`replay_nonce` 与 `realm_id` 必须进 franking proof 签名）。
- 在没有有效 service DID 绑定的情况下签发 franking proof。

SHOULD 支持：

- franking proof batch endpoint（一次 fetch 多条 franking proof）以减少 audit traffic。
- franking proof inclusion proof：franking proof 可被签入定期 franking-proof log Merkle tree，向举报者证明"该 franking proof 不是后补的"。该 inclusion proof 与 Anchor state_root 独立，因为 franking proof 不进入 Realm anchor frontier（franking proof 是 service-side audit material，不改变协作状态）。
- 显式 `franking_proof_unavailable` 错误码，让 reporter 客户端知道 service 当前不签发 franking proof（如 service downgrade / outage），而不是误以为消息根本未投递。

## 19b. WebRTC Media Service

`cx.profile.webrtc_media.v1` 适用于提供 ICE config / TURN / SFU 等 RTC 基础设施的服务。

参考：[`crypto-media/webrtc-signaling.md`](../crypto-media/webrtc-signaling.md) §6–§13。

MUST 支持：

- ICE config endpoint，返回包含 `ttl_seconds`、`refresh_lead_seconds`、`ice_servers[]`（含 STUN / TURN）、签名的响应。
- per-call pairwise pseudonym 作 TURN `username` 身份段；不得使用 principal DID / handle / 跨呼叫稳定 ID。
- TURN credential REST-style ephemeral 形态（`username = <expiry-unix>:<pseudonym>`，`password = HMAC-SHA256(turn_shared_secret, username)`）。
- TURN shared secret 周期轮换（默认 ≤ 24 小时）；轮换时同时接受新旧 secret，grace ≥ `ttl_seconds`，避免 in-call 集体失败。
- in-call credential refresh：客户端在剩余有效期 ≤ `ttl_seconds * 0.25` 时调用 refresh；server 必须在不中断现有 allocation 的前提下下发新 credential。
- `turn_credential_expired` / `441 Wrong Credentials` / `438 Stale Nonce` 等错误的 `next_retry_at` 响应。
- 高隐私 Realm 的 `force_turn=true` mode（禁止 host/srflx candidate 泄露 IP）。
- ICE config 响应签名（service DID detached signature 或 authenticated TLS + service DID 绑定）。

MUST NOT：

- 把 principal DID、handle、邮箱或跨呼叫稳定 ID 作为 TURN username。
- 在响应中暴露除 `ice_servers[]` 之外的 Realm metadata（成员数、Realm ID、call topic）。
- 在 SFU 路径透明转发未加密媒体——E2EE 通话的 audio/video 必须使用 SFrame 或等价 frame-level 加密，SFU 只看 cipher frames。

SHOULD 支持：

- per-tenant TURN credential 隔离。
- 多 region failover：refresh 时返回 region-aware `ice_servers[]`。
- credential issuance audit log（仅记录 expiry + pseudonym hash，不记录 principal binding）。

## 19c. Stateless Cursor (`cx.profile.stateless_cursor.v1`)

v1 core 默认 cursor 形态是 stateful opaque handle（参见 [`sync/client-sync.md` §12.1](../sync/client-sync.md)）：cursor body 缩为 `{v, purpose, t, x, h}`，由 issuing service 内部表把 `h` 解析到完整状态，无需密钥管理。绝大多数实现 SHOULD 使用 core 形态。

本 opt-in profile 为需要 stateless 自描述 cursor（cursor body 内含 `s` / `d` / `target` / `issuer_kid` 并以 `_mac` 或 `_sig` 绑定 transcript）的实现提供契约。典型使用场景：

- Service mesh 内多副本无共享 cursor 状态存储，需要 cursor 在副本之间自验。
- High-assurance 部署希望客户端能离线审计 cursor 完整性（MAC / 签名校验链）。

声明 `cx.profile.stateless_cursor.v1` 的实现 MUST：

- 在 cursor body 中除 core 必填字段 `{v, purpose, t, x}` 外，**禁止**携带 `h`，**MUST** 携带 `issuer_kid` 与 `_mac` 或 `_sig` 之一；其余必填字段按 cursor purpose 决定：stream cursor 携带 `s`（per-Realm frontier）与/或 `d`（device-message stream positions）；barrier cursor 携带 `target`。
- `_mac` 是 HMAC over canonical bytes（除 `_mac` 自身外的所有字段），密钥由 issuing service 持有，算法 MUST 是 HMAC-SHA-256 或更强。
- `_sig` 是 detached signature over same canonical bytes，密钥使用 issuing service 的 cursor-signing key（按 `issuer_kid` 解析）。
- transcript 绑定 MUST 覆盖：`purpose`、`principal_id`、`device_id`、`service_id`、`filter_hash`、stream positions（`s` / `d`）、`target`（barrier 时）、`x`、`issuer_kid`。
- 收到 cursor 时按 [`sync/client-sync.md` §12.2](../sync/client-sync.md) §第 4 步处理：缺 `h` 但满足上述 transcript 校验则放行；transcript 不匹配返回 `cursor_integrity_invalid`。
- ServiceDescribe `supported_features[]` MUST 含 `stateless_cursor`，供 client 通过 feature discovery 判断是否可发送 stateless cursor。
- `cursor.schema.json` core schema 之上 MUST 通过 profile 自带 schema overlay 接受额外字段；core consumer 不实现该 overlay 即正确地拒绝 stateless cursor（fail-closed）。

不声明本 profile 的实现 MUST 把缺 `h` 的 cursor 直接判为 `cursor_integrity_invalid`，**不得**尝试 transcript 校验作为后备路径——这避免了核心实现需要维护 cursor signing key、key rotation 与 cross-issuer key trust list。

Fixture：`schema-validation-fixture.json` 的 `cursor_valid_stateless_*` 条目集合是本 profile 的最小验证向量；core profile 在不声明 `cx.profile.stateless_cursor.v1` 时 MUST 在同一组 fixture 上回退到 `cursor_integrity_invalid`。

## 20. Conformance 测试要求

每个 profile SHOULD 提供：

- schema validation tests
- signature verification tests
- idempotency tests
- reducer convergence tests（含 Move/Anchor/Lattice 向量）
- Move/Anchor/Lattice vectors（见 `conformance-vectors.md`）
- Event Envelope negative vectors（见 `artifacts/fixtures/event-envelope-negative-fixture.json`）
- redaction vectors（见 `conformance-vectors.md`）
- capability vectors（见 `conformance-vectors.md`）
- sync fixture、state-resolution fixture、capability fixture 和 privacy/security fixture（见 `artifacts/fixtures/*.json`）
- authorization tests
- privacy regression tests
- error response tests
- downgrade / unsupported feature tests
- unknown-field preservation tests

所有 profile MUST 能按 `../models/common-fields.md` 与各对象专属文件（`realm-and-space.md` / `flow-and-message.md` / `morph.md` / `relation.md` / `event-and-patch.md` 等）解码和验证其声明支持的核心对象字段。实现 MUST 在 canonical object 中保留未知 non-critical 字段，并覆盖“hash/signature 校验、存储、联邦转发、backfill 后字段仍存在”的测试；未知 critical feature MUST fail closed。实现 MUST reject 类型错误、必填字段缺失、非法 enum、非法 ID/hash/timestamp/cursor pattern，以及违反条件必填规则的对象。标准 Event 必须加载 `event-kind-registry.json` 与 `event-payload.schema.json`，确认每个 active durable kind 都有可执行 payload 校验路径。

所有 profile MUST 按 `conformance-vectors.md` 覆盖 canonical JSON、hash、signature binding、Ed25519 detached JWS fixture、HLC 和 cursor 的基础向量。Events API、Full Client 与 E2EE Client MUST 额外覆盖 event digest；Events API 节点 SHOULD 覆盖 event-batch receipt digest；E2EE Client 和 Principal Server MUST 覆盖 encrypted envelope digest。

E2EE profile MUST 额外提供：

- KeyPackage verification vector
- KeyPackage claim single-use vector
- MLS Governance Binding root mismatch vector（`governance_binding` 任一 root 不匹配 Anchor view）
- minimal-metadata identity link vector
- AAD visibility vector
- MLS epoch transition vector
- encrypted payload vector
- removed member cannot decrypt vector
- E2EE franking report vector

Client Sync 相关 profile MUST/SHOULD 按 `conformance-vectors.md` 执行对应向量：

- Minimal Client MUST 覆盖基础排序、tie break、pagination gap、backfill order 和 token expiry recovery。
- Chat-only Client MUST 覆盖 Flow discussion timeline、message edit/redaction、reaction OR-Set、discussion history visibility 和 membership 裁剪。
- Kanban-only Client MUST 覆盖 Board projection、Flow move/reorder、position edge conflict、CAS stale reorder 和 wait-for query。
- Full Client MUST 额外覆盖 snapshot frontier、state_after 与 decryption_pending 的 UI / cache 恢复行为。
- E2EE Client MUST 覆盖 MLS epoch backfill、decryption_pending recovery 和 removed member fail closed。
- Principal Server SHOULD 覆盖 duplicate suppression、backfill order、encrypted payload forwarding 和不能转发解密材料。
- Snapshot bootstrap MUST 覆盖 `event_set_commitment` root、covered frontier、conflict/soft-fail/quarantine 摘要和 inclusion / omission challenge hint。

Privacy / security hardening profile MUST 额外覆盖：

- hidden Realm resolve 的不可见/不存在响应同形态
- private contact discovery 的 batch padding 与 cardinality protection
- plaintext-visible service 对私有正文处理的强制拒绝
- private blob HEAD / Range anti-enumeration
- blind wakeup push payload 最小披露

Moderation profile MUST 额外覆盖：

- `cx.schema.moderation_report.v1`
- `cx.schema.moderation_queue_item.v1`
- `cx.moderation.report` payload schema validation
- E2EE evidence package / franking proof 只向授权 moderation recipient 披露

Identity profile MUST 额外提供：

- `did:webvh` method adapter vector（`did.jsonl` 解析、SCID 派生、entry hash chain 验证、controller proof、witness evidence）
- `did:web` resolver vector
- `did:key` local resolver vector
- key rotation vector
- recovery vector
- pairwise DID unlinkability checks
- AT Protocol interop profile MUST 额外提供 `did:plc` adapter vector

Applet Service / Bridge profile MUST 额外提供：

- registration signature vector
- namespace conflict vector
- duplicate transaction vector
- ghost actor mapping vector
- portal Realm mapping vector
- unauthorized write rejection vector

MIMI Interop profile MUST 额外提供：

- provider directory draft pinning vector
- room binding projection vector
- content roundtrip vector
- identifier query privacy vector
- consent isolation vector
- proxy download policy vector
- unsupported draft fail-closed vector

## 21. Feature Discovery 示例

```json
{
  "service_did": "did:web:server.example.com",
  "service_type": "principal_server",
  "protocol_version": "1.0",
  "supported_profiles": [
    "cx.profile.principal_server.v1"
  ],
  "supported_features": [
    "sync_stream",
    "snapshot_bootstrap",
    "plaintext_visibility_classes"
  ],
  "reducer_profiles": [
    "cx.reducer.v1"
  ],
  "schema_profiles": [
    "cx.schema.event.v1"
  ]
}
```

## 22. 基线 Profile

首个互操作目标 SHOULD 是：

- `minimal_client`
- `chat_mvp`
- `kanban_mvp`
- `principal_server_events_api`
- `principal_server`
- `federation_minimal`
- `identity_registry`
- `blob_node`
- `push_gateway`
- `applet_service`
- `mimi_interop`

`full_client` 和 `e2ee_client` 是产品可用性的目标 profile。  
`enterprise_client` 和 `agent_runtime` 是高价值扩展 profile，但不应阻塞基础互操作。
