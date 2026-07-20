---
title: 实现 Profile 与一致性要求
status: candidate
normative: true
stability: v1
updated: 2026-07-16
sidebar:
  label: 实现 Profile
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

> 本文是 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的说明视图，非穷尽；完整 profile 矩阵（含 `deployment_profiles`、`hardening_profiles` 等全集）以该 json 为准。

## 1. 目标

Arkret 是模块化协议。为了避免“实现了 Arkret”变成不可验证的模糊声明，规范 MUST 定义可测试的实现 profile。

每个实现 MUST 声明自己支持的 profile、协议版本和 feature 集合。
Conformance 测试 SHOULD 以 profile 为单位执行。

Profile / capability 声明也是异构版本互通的协商基础：兼容性是双方声明能力的交集，未声明的 extension 能力 MUST fail closed。该机制在协议演进中的整体角色见 [overview/evolution-and-compatibility.md](../overview/evolution-and-compatibility.md) §5。

## 2. Profile 命名

Profile 名称使用：

```text
ak.profile.<name>.v<major>
```

示例：

- `ak.profile.minimal_client.v1`
- `ak.profile.principal_server_events_api.v1`
- `ak.profile.principal_server.v1`
- `ak.profile.full_client.v1`
- `ak.profile.e2ee_client.v1`
- `ak.profile.federation_minimal.v1`
- `ak.profile.mimi_interop.v1`

## 2.1 v1 MVP 分层

为降低实现复杂度，v1 profile 分为三个声明层。`artifacts/profiles/conformance-profiles.json.profile_tiers` 是机器可读来源；`v1_profile_catalog` 不是 bundle requirement，实现只声明自己实际支持的 profile、event kind、schema 和 operation。

| 层级 | 含义 | 典型内容 |
| --- | --- | --- |
| Minimal interop floor | 仅声称 v1 Event Store interop 时的最小声明。 | `ak.profile.core_event_store.v1`：Event Envelope、per-actor event chain、events submit/get/list/frontier/backfill、标准错误。 |
| Stable profile catalog | v1 stable catalog 中可独立声明的实现 profile，不构成默认全量包。 | `chat_mvp`、`kanban_mvp`、`minimal_client`、`full_client`、`principal_server`、`identity_registry`、`blob_node`、`push_gateway`、`federation_minimal`、`sovereign_client` 等。 |
| Extension（v1 interop） | 在 v1 stable catalog 中可独立声明，但**只在显式 opt-in 时启用**。未声明的实现遇到这些能力 MUST fail closed。 | `ak.profile.matrix_compat.v1`（Matrix 兼容声明：to-device / `/_arkret/self/keys/*` / push gateway / cross-signing / SAS 与 Matrix 等价语义；账号聚合不声明 Matrix `/sync` wire parity）。 |
| Interop staging extension | **不属于 v1 core interop floor**，跟踪外部演进标准；声明 v1 core 的实现 MAY 完全省略。 | MIMI interop、Applet integration、Agent protocol bridge、TSP integration 等；这些 profile 在外部标准定型后将被稳定版本固定取代。 |

Document、File、Poll 在 v1 MVP 中默认是 Morph profile 或 extension profile，不是 core 标准对象。实现不得因为未来可能标准化这些类型，就在 v1 wire contract 中要求对端支持专用对象类型。

Core identity conformance 要求 DID Core 解析 / 验证抽象、`did:webvh:1.0`（v1 core 默认 principal method 的精确 adapter 版本）、`did:web`（service DID / `personal_node` profile principal）与 `did:key`。所有声明 `ak.profile.principal_server.v1` / `ak.profile.full_client.v1` / `ak.profile.e2ee_client.v1` 的实现 MUST 支持 `did:webvh:1.0` witness / SCID / entry hash chain 验证；method evidence 中的 `parameters.method` MUST 精确等于 `did:webvh:1.0`，缺失或未知版本 MUST `unsupported_did_method`，不得按“当前最新版”解释。组织高保证实现 SHOULD 声明 `ak.profile.org_high_assurance_identity.v1` 并要求 `did:webvh` witness / watcher evidence 强制 threshold ≥ 1。AT Protocol 互通实现 SHOULD 额外声明 `ak.profile.public_network_identity.v1` 并支持 `did:plc` adapter；该 adapter 是 interop 加项，不是 Arkret Core 强制依赖。

v1 的首轮互操作验收 SHOULD 拆成三个可运行闭环：

- `ak.profile.core_event_store.v1`：DID / service discovery、Event Envelope validation、event submit/fetch/backfill、per-actor event chain validation、idempotent duplicate handling、standard error。
- `ak.profile.chat_mvp.v1`：在 `core_event_store` 之上支持 Realm、`ak.member.state`、启用 discussion track 且可设为 primary 的 Strand、Message、Reaction、Redaction、Client Sync timeline 和 history visibility。
- `ak.profile.kanban_mvp.v1`：在 `core_event_store` 之上支持 Space（`kind=board/list`）、Strand、`contains` position Relation、`ak.strand.move`、`ak.strand.reorder`、`ak.space.create`、`ak.space.update`、`ak.space.parent`、客户端 Collection projection 和 wait-for query。

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

Profile 正文中的 prose MUST 项必须能映射到 `artifacts/profiles/conformance-profiles.json#profile_requirements` 的 `required_endpoints` / `required_event_kinds` / `required_schemas` / `required_fixtures` / `feature_discovery`，或在 `prose_requirement_coverage` 中列出对应 registry、fixture 或 conformance runner。没有一一字段的 prose MUST 不得悬空；新增 profile 时 reviewer MUST 拒绝缺少覆盖映射的 prose MUST 清单。

### 2.1.2 可裁剪构建与 profile 声明对账（normative）

§2.1 的"实现只声明自己实际支持的 profile"对可裁剪模块构建（Cargo feature、编译开关、插件拆分等形态的实现或 SDK）有一条显式推论：

- 以可裁剪模块构建的实现 / SDK MUST 保证其 profile 声明面（`ServiceDescribe.claimed_profiles`、`supported_profiles`、SDK 静态导出的 conformance 声明常量等）与**当前构建产物的实际编译能力**一致，而不是与全功能构建的能力一致。
- 构建期裁剪掉某 profile 的任一 MUST 能力（对应 `profile_requirements` 中 `required_endpoints` / `required_event_kinds` / `required_schemas` 的实现模块）时，该构建 MUST 同时摘除该 profile 的声明——通过构建期对账（feature gate 与声明常量联动）或等效守卫实现。裁剪构建（例如 `--no-default-features`）继续静态声明完整 required 面（如 `e2ee_client` 的 required 集合）即违反本条与 §2.1 的声明纪律。
- 对端按 §1 的能力交集原则信任声明面；声明面与编译能力脱钩会把 fail-closed 协商变成 fail-open，因此本条按声明纪律缺陷处理，而非文档瑕疵。

SDK 侧构建期守卫的具体实现形态（feature 矩阵测试、声明常量的 cfg 拼装等）属实现审查范畴，本文不规定唯一做法。

发布单一预编译构建时，顶层 `sdk_artifact.digest` 已唯一绑定该构建。发布源码包或同一 release 下存在多个可裁剪构建时，SDK conformance claim MUST 使用 `build_variants[]` 声明被认证的每个变体：稳定 `variant_id`、规范化 feature/configuration 集的 `feature_set_digest`，以及该变体实际导出的 `claimed_profiles[]`；可读的 `features[]` 只是对 digest 的审计投影。未列变体不在该 claim 的认证范围内。AK-SDK-015 的证据 MUST 引用 `build_variant_inventory`，验证器 MUST 对 variant id 唯一性、profile id 已登记性及 inventory digest 做校验。

## 2.2 场景化 Profile

以下 profile 用于把 v1 启动范围降到可实现的产品子集。它们不是 `minimal_client` 的替代品，而是面向具体产品形态的互操作声明。声明 `ak.profile.chat_mvp.v1` 或 `ak.profile.kanban_mvp.v1` 时，仅实现一个闭环的实现 SHOULD 在 `rejected_event_kinds` 中列出本实现拒绝的另一闭环 wire scope。

### `ak.profile.federation_minimal.v1`

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

Coverage mapping：endpoint 能力由 `required_endpoints` 覆盖；signed Event Envelope、destination binding 与分项结果由 `required_schemas` + `federation-fixture.json` 覆盖；dependency missing / duplicate conflict quarantine 由 `event-envelope-negative-fixture.json` 与 `sync-fixture.json` 覆盖；batch、event size 与 retry 规则由 `scalability-constraints.md` 和 `federation-fixture.json` 覆盖。

MAY 支持 gossip、snapshot-assisted bootstrap、MIMI facade、Applet bridge 和 full-text search。

## 3. 通用强制要求（所有 Profile 必须遵守）

以下要求不依赖具体角色，必须作为可互操作实现的基础：

- 事件名必须符合 `ak.` 命名规则，且标准 `ak.*` Event kind 必须在 `artifacts/registry/event-kind-registry.json` 注册；schema id 必须在 `artifacts/registry/schema-registry.json` 注册。
- Event Envelope MUST 先通过 `ak.schema.event.v1`，再按 `Event.kind` 通过 `ak.schema.event_payload.v1` 对应 payload class；active 标准 kind 未匹配 payload class 或 payload 校验失败时 MUST 返回 `schema_violation`，不得进入 reducer。
- 事件/关系/对象/View 的 `created_at`、`realm_id`、`proof`、`hlc`、`actor_seq`、`prev_refs` / `refs[role=authorized_by]` 在 reducer 与验证逻辑中不能被跳过；版本通过 `Event.requirements.{schema, reducer}` 表达。
- `auth` 约束必须执行，不得通过客户端配置豁免。
- State frontier、snapshot frontier、projection frontier 和 wait-for token MUST 以 `event_id` / actor frontier 为语义单位；`operation_id` 只可表示服务 canonical operation。
- Snapshot manifest MUST 包含 `event_set_commitment`；high-assurance profile MUST 支持 inclusion / omission challenge 或 witness quorum 校验。
- 裸名事件（如 `realm.create`）MUST 被拒绝，不能作为新增标准互操作行为。
- 实现 MUST 对 `causal` 关系、`revoked` 与 `proof` 失效状态进行一致性拒绝（fail-closed），不能“静默接受”。

## 4. Minimal Client

`ak.profile.minimal_client.v1` 适用于只读或轻量写入客户端。

MUST 支持：

- DID / handle 解析
- service discovery
- event 拉取 / backfill
- 本地查询和 projection
- 基础 Strand / Realm / Message / Morph / Relation / Event 解码
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

`ak.profile.full_client.v1` 适用于桌面、Web 和移动主客户端。

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

`ak.profile.e2ee_client.v1` 适用于加密 Realm。

MUST 支持 Full Client 的相关能力，并额外支持：

- MLS RFC 9420 group state
- KeyPackage publish / fetch / verify
- KeyPackage claim / consume / revoke lifecycle
- Welcome / Commit / Proposal event
- MLS Governance Binding：`governance_binding` 的 GroupContext extension 验证 + `covered_seals_cell` 的 reducer 累积
- minimal-metadata pseudonymous credential handling when profile is advertised
- AAD visibility policy handling
- epoch mismatch recovery
- encrypted payload envelope
- encrypted attachment envelope
- encrypted key backup object and backup CRUD for `did_recovery` / `secret_storage` / `mls_history`
- device revocation handling
- lost-device response
- local plaintext search for encrypted content

声明 `ak.profile.mls_governance_binding.full.v1`（即 MLS Governance Binding 的 full 形态，见 `crypto-media/encryption-and-audit.md §2.5`）时，客户端和服务端 MUST 额外验证 commit 携带的 `governance_binding` 覆盖 membership、history visibility、plaintext-visible service、asset privacy、logging、bot / applet / agent policy、moderation policy 与 capability grant / revoke frontier，并 MUST 通过 `covered_seals_cell` coverage gate E2EE DataEvent 的 `seal_ref`。无法验证 `governance_binding` 指向的 Seal view 时，客户端 MUST fail closed，至少不得接受依赖未知应用状态的新 epoch。该 profile 的机器 requirement closure 必须包含 `ak.self.events.query.mls_governance_proof`、`ak.schema.mls_governance_proof_bundle.v1` 与 `mls-governance-proof-fixture.json`；认证器 MUST 分别以 SDK consumer 和 server consumer 角色执行 fixture 登记的 verify / materialize runner，并连同 `ak.vector.scalability.mls_governance_proof_bounds.v1` 输出逐 case 结果。任一角色缺失、只做 schema shape check 或未执行完整 mutation/limit matrix 时不得声明 full profile 通过。

声明 `ak.profile.attested_audit.e2ee.v1` 时，审计 applet release service MUST 提供可验证 remote attestation，并执行 active binding、session request/authorize/notice、sealed `ak.audit.release`、RYW receipt 等待和成员可见 disclosure；RYW receipt 的 `audit_assurance_class` MUST 等于 `attested_hardware`。声明 `ak.profile.disclosed_audit.e2ee.v1` 时，不要求 TEE attestation，但 Realm / Circle policy 和加入 UI MUST 明确展示这是流程性披露；同样不得绕过 Audit Applet Binding + release session 留痕流程；RYW receipt 的 `audit_assurance_class` MUST 等于 `disclosed_policy`。审计 applet 不是 MLS 成员，也不获得实时消息 fanout。两个 profile 不再共享 family 前缀，对外材料 MUST 遵守 `encryption-and-audit.md §3` / `audited-e2ee.md` 的禁用措辞条款，不得将 disclosed 类宣传为密码学/硬件强制审计。

MUST NOT：

- 把明文消息发送给未授权 Sync Service 或受托 search / projection 服务
- 把解密密钥上传给不受信服务
- 在未验证 KeyPackage 所属 DID 的情况下加密给对方
- 在 `governance_binding` 的 policy / membership root 不匹配时继续解密正文（违反 MLS Governance Binding）

## 7. Principal Server Events API

`ak.profile.principal_server_events_api.v1` 适用于 Principal Server 暴露的 Event 提交、读取、回填和 frontier 查询 API。

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

`ak.profile.principal_server.v1` 适用于用户、组织或 agent principal 控制/委托的服务入口。

MUST 支持：

- subscribe / sync stream
- backfill
- account-aggregate streaming subscription (`GET /_arkret/self/account/subscribe`)
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

`ak.profile.identity_registry.v1` 适用于 DID 文档与 key log 服务。

MUST 支持：

- DID resolve
- DID log fetch
- DID operation submit
- cold identity-root / current active update-authority verification（含 method-native pre-rotation 与 spent-key 规则）
- `key_log` validation
- receipt publication
- method adapter metadata

SHOULD 支持：

- witness-only mode
- read replica mode
- raw DID document preservation
- normalized principal view

## 9a. Auth Server

`ak.profile.auth_server.v1` 适用于负责登录因子验证、短期会话授权与 session-grant 生命周期管理的服务（reference implementation：`coauth`）。

MUST 支持：

- service describe（`ak.server.query.describe`）
- `ak.gate.account.command.issue_session_grant` / `/_arkret/gate/account/session-grants` 的规范化签发路径
- 至少一种登录因子（password / passkey / OIDC / SSO / device pairing / recovery challenge）
- 短期、audience-bound `ak.session.grant` 签发
- session_grant TTL 上限远低于 Realm policy review horizon（minutes-to-hours，不得跨越多日）
- session_grant audience 绑定与拒签陌生 audience
- `auth_metadata.account_authority`、`auth_metadata.methods[]`、`auth_metadata.did_binding_methods`

SHOULD 支持：

- session-grant introspection 与 revocation
- `ak.gate.account.command.issue_session_grant` 规范化 HTTP binding
- 采用 account-first onboarding 时，完整实现 `ak.gate.account.exchange.create_handoff` → `ak.gate.account.command.issue_identity_binding_challenge` → `ak.gate.account.command.register`；不得以私有 endpoint、普通 OAuth bearer 或进程内 challenge store 替代
- `ak.self.policy.query.check`（`PolicyCheckOutcome`）
- 多 principal-server delegation target 配置
- DID binding / claim attestation

Auth Server MUST NOT 声明 `ak.profile.identity_registry.v1`、`ak.profile.principal_server.v1` 或 `ak.profile.directory_service.v1`。任何 DID document / key-log 表面 MUST 通过 `compat_surfaces[]` 以 `delegated_resolver` 形式声明，而非自我声称 canonical 权威。

Auth Server MUST NOT 把成功的 OIDC / SSO / password 验证直接当作 DID 控制证明。Account-first inception binding 必须按 [`../identity/account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 验证由 entry 0 method-native control key 签发的 fresh proof；普通已发布 DID binding 与下游资源服务器仍 MUST 重新验证 DID control state（见 `guides/migrating-from-matrix.md`）。

`development_mode=true` 时，`verified_profiles[]` MUST 为 `[]`（见 `sync/service-surface.md` §3.0）；Conformance Verifier 在 verified-profile suite 通过后才能写入 verified entry。

Release readiness MUST 至少覆盖：签发路径拒绝陌生 audience、session grant TTL 上限、proof 绑定 `challenge` / `audience` / `request_canonical_digest` / principal / device、`soft_logged_out` 恢复需要 fresh DID proof，以及 development mode 下不得声明 verified profile。对应 conformance vector 为 `ak.vector.auth.session_grant_audience_binding.v1` 与 `ak.vector.auth.soft_logout_did_proof.v1`。

## 10. Blob Node

`ak.profile.blob_node.v1` 适用于内容寻址存储。

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

> 三个 `ak.profile.push_gateway.*` profile 等价于一个离散 `payload_disclosure_class ∈ {blind, visible, matrix}` 选择（informative）；部署 MUST 通过 profile id 声明，而非自定义 enum，以保留 conformance gate 粒度。

`ak.profile.push_gateway.v1` 适用于移动端或桌面通知的推送网关。Push gateway 实现 MUST 同时满足下方拆分的三个子 profile 之一或多个组合（默认基线为 blind wakeup，visible / matrix 互通为 opt-in）。

| Profile id | role | 必选 / 可选 | 强制能力 | Fixture |
| --- | --- | --- | --- | --- |
| `ak.profile.push_gateway.v1` | `gateway` | 实现网关时必选；MUST `depends_on` `blind_wakeup` | `register_device` / `unregister_device` / `notify` 三个操作，`ak.schema.notification.v1`，service DID 校验，`rejected[]` 回传，失效 token 回收 | `privacy-security-fixture.json` |
| `ak.profile.push_gateway.blind_wakeup.v1` | `gateway` | **默认互操作安全基线**：声明 `push_gateway.v1` 即 MUST 声明 | provider 出向 payload 仅含 `push_target_id`（pairwise pseudonym，按 [`crypto-media/device-lifecycle.md` §5a](../crypto-media/device-lifecycle.md)）+ 封闭枚举的 `wakeup_kind` / `badge_count` / `unread_increment` / `l10n_key`；MUST NOT 携带 principal DID、sender DID / handle、Realm / Strand / Message id、event id、device DID URL、reaction 实际值、附件文件名、跨 Realm stable correlation key、IP / geolocation | `privacy-security-fixture.json` |
| `ak.profile.push_gateway.visible_notification.v1` | `gateway` | Opt-in；仅在 Realm policy 列入 `plaintext_visible_services` 且声明 `visible_notification` allowance、接收设备 opt-in、UI 显式标示时声明 | 维持 blind wakeup 之上扩展的最小可见字段集合；MUST NOT 携带正文、DID URL、跨 Realm stable correlation key、IP / geolocation 或未列入 profile 的自由文本；E2EE 默认实现不得依赖该 profile | `privacy-security-fixture.json` |
| `ak.profile.push_gateway.matrix_passthrough.v1` | `interop` | Opt-in；Matrix 互通桥接 | 在与 `ak.profile.matrix_compat.v1` 并行的前提下，按 Matrix push gateway 形态承载 passthrough payload；MUST 与 `blind_wakeup.v1` 流量分区，**MUST NOT** 在同一 `(recipient_service_id, device)` 元组上同时声明两者。**选择此 profile 即接受 Matrix-equivalent metadata 可见性**（典型字段如 `room_id` / `sender` / `event_id` 透传到 Matrix push gateway）。该 profile MUST NOT 与 minimal-metadata Realm 共享同一 `(recipient_service_id, device)` 元组。 | `privacy-security-fixture.json` |

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

### 11.1 Traffic Metadata Hardening

`ak.profile.traffic_metadata_hardened.v1` 是部署 / Realm 级 hardening profile，用于把 federation fanout 时间、batch 大小、Welcome / GroupInfo 大小、push wakeup 和 retry cadence 的侧信道缓解变成可声明、可测试的 MUST 集合。声明该 profile 的服务或 Realm MUST 在 `ServiceDescribe.claimed_profiles` / Realm policy profile 集合中暴露其参数，并按 `artifacts/profiles/conformance-profiles.json#profile_requirements` 执行。

MUST 支持：

- `federation_batch_padding`：outbound federation fanout MUST 使用固定或下限 batch size；空批次 / padding entries 计入可观察 batch size。
- `welcome_padding_bucket`：MLS Welcome / GroupInfo blob MUST round up 到声明的 padding bucket（默认 4KiB / 16KiB / 64KiB），不得泄露精确 leaf count。
- `bounded_send_jitter`：fanout 与 retry MUST 使用声明的随机抖动窗口；实现不得用窗口边界编码活动。
- `blind_or_batch_wakeup`：push 默认 MUST 是 `blind_wakeup`、`batch_wakeup` 或 `no_notification`；`visible_notification` 与本 profile 默认不兼容，除非 Realm policy 对该 recipient route 显式 opt out。
- `retry_cadence_padding`：重试节奏 MUST 使用同一 padding / jitter policy，不得让失败原因产生稳定可测的时间形态。
- 至少一种 cross-domain route indirection：`ohttp`、`trusted_relay` 或 `decoy_traffic`。

conformance runner MUST 能观测：batch size bucket、Welcome size bucket、jitter 上下界、push payload disclosure class、retry cadence bucket 与 relay/decoy 开关。实现如果不能提供这些可观测参数，MUST NOT 声明 `ak.profile.traffic_metadata_hardened.v1`。

## 12. Applet Service / Bridge（概要）

详见第 19 节完整定义。

## 13. MIMI Interop Provider Facade

`ak.profile.mimi_interop.v1` 适用于需要与外部 MIMI provider 互通的 facade 服务。

MUST 支持：

- pinned MIMI draft version discovery
- `ak.mimi.room_binding` 生命周期校验
- MIMI provider directory 和 endpoint surface
- KeyPackage claim / consume / revoke lifecycle
- MIMI message 到 Arkret Event Envelope 的映射
- Arkret event 到 MIMI message / receipt 的映射
- room policy component 到 Arkret capability / policy state 的映射
- identifier query 的 private contact discovery
- consent state isolation
- E2EE abuse report franking
- asset privacy policy 下的 proxy / OHTTP 下载策略
- unsupported draft fail-closed

MUST NOT：

- 把 MIMI room id 当作 `realm_id`
- 把 MIMI provider timestamp 当作 Arkret HLC / event creation truth
- 把 MIMI user identifier 当作 DID
- 绕过 Arkret auth refs、capability、MLS epoch 或 Realm policy

## 14. Enterprise Client

`ak.profile.enterprise_client.v1` 适用于企业受控客户端。

MUST 支持 Full Client，并根据 policy 支持：

- OIDC / SSO gateway session grant
- device inventory
- admin-triggered device revocation
- auditable E2EE warning UI
- compliance audit event display
- managed update policy

MUST NOT 在不显示 policy 的情况下静默加入 auditable encrypted Realm。

## 15. Sovereign Deployment

`ak.profile.sovereign_deployment.v1` 适用于军方、关键基础设施、金融核心、情报或其他高安全组织的自建/专属部署。

MUST 支持：

- 组织 DID 控制的服务委托
- 服务 DID allowlist
- 默认 closed federation
- 默认私有目录
- 在 sovereign deployment 下 External Collaboration Realm 的强制 policy（见 [`models/realm-and-space.md` §2.8](../models/realm-and-space.md) 与 [`sync/sovereign-deployment.md` §4](../sync/sovereign-deployment.md)）
- restricted 或 invite-only 外部加入
- Policy Server `closed` 或 `quarantine` 失败模式
- sovereign deployment 下 External Collaboration Realm 默认 E2EE
- MLS Welcome 只发给已批准的外部设备
- 外部 Applet / Agent / transport allowlist
- 跨域事件审计
- grant / invite / membership 撤销
- 外部成员移除后 MLS epoch 轮换
- sender-constrained（proof-of-possession）会话出示：常规写与敏感读 MUST 用 `session_public_key` 的 RFC 9421 HTTP Message Signature 出示（见下文与 `conformance-profiles.json#profile_requirements` 的 `additional_requirements.sender_constrained_session_pop_must`），纯 `Authorization: Bearer`（无 `Signature`）对这些操作 MUST 被拒绝

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

### 15.1 Sender-constrained 会话出示

依据 [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700)（OAuth 2.0 Security BCP, BCP 240）"优先使用 sender-constrained token" 的指导，Arkret v1 production protected endpoint 的会话出示必须是 proof-of-possession（PoP）：`/_arkret/self/*` 使用 `ak.session.grant` + DPoP，常规写与敏感读使用会话 `session_public_key` 的 RFC 9421 HTTP Message Signature 或等价 sender-constrained proof。裸 `Authorization: Bearer` 可作为 DPoP / PoP 绑定中的 grant 载体，但不能单独作为受保护 endpoint 的认证成功依据（见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md)）。

在高安全 deployment profile 下，常规写与敏感读的 sender-constrained 出示必须使用 RFC 9421 HTTP Message Signature 形态并绑定 transcript/body。涉及的 profile 与其 `conformance-profiles.json#profile_requirements` 中的 `additional_requirements.sender_constrained_session_pop_must` 一一对应：

- `ak.profile.high_security_organization.v1`
- `ak.profile.sovereign_deployment.v1`（`ak.profile.sovereign_enclave.v1` 经 `inherits` 继承）
- `ak.profile.isolated_sovereign_network.v1`（经 `inherits` 同时继承上述两者，无需重复声明）

这些 profile 下，对常规写（任何推进 `actor_seq` / Realm frontier 或产生持久副作用的请求）与敏感读，实现 MUST 要求 RFC 9421 PoP 出示：签名密钥为 `ak.session.grant` 委托的 `session_public_key`，覆盖 `@method` / `@target-uri` / `@authority`、`content-digest`（带 body 时）与参与幂等的 `Idempotency-Key`，`created` / `expires` 落在既有 replay window 内（量级见 [`../sync/federation.md` §3.2](../sync/federation.md) 与 [`encoding.md` §6](./encoding.md)）。带 body 请求的 exact canonical HTTP content bytes、唯一 RFC 9530 `sha-256` token 与 raw-byte verification MUST 遵循 [`../sync/service-http-binding.md` §2.5.1](../sync/service-http-binding.md)。纯 `Authorization: Bearer`（无 DPoP / `Signature` / mTLS 绑定）对任何生产 current-v1 受保护 endpoint MUST 被拒绝；公开 metadata surface 若返回 public response，必须按未认证请求处理，不得授予 session / capability 语义。PoP header 形态见 [`../sync/service-http-binding.md` §2.5.2](../sync/service-http-binding.md)。

## 16. Sovereign Client

`ak.profile.sovereign_client.v1` 适用于接入 sovereign deployment 的受控客户端。

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

Deployment profile 用于发布与验收，不替代实现 profile。完整 deployment profile 集合以 [`artifacts/profiles/conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `deployment_profiles` 为准；本节为非穷尽说明视图，包括以下 profile 等：

- `ak.profile.personal_node.v1`
- `ak.profile.small_team.v1`
- `ak.profile.organization.v1`
- `ak.profile.high_security_organization.v1`
- `ak.profile.isolated_sovereign_network.v1`

`ak.profile.personal_node.v1` MUST cover：

- Principal Server、Events API、Sync Service、Blob Store 可以同机合并
- 默认最小管理员面
- 本地备份与恢复

`ak.profile.small_team.v1` MUST cover：

- 多用户共享 Realm
- 基础目录与推送
- moderation queue
- snapshot / backfill

`ak.profile.organization.v1` MUST cover：

- organization DID 委托
- OIDC / account integration
- admin account lifecycle
- 审计导出

`ak.profile.high_security_organization.v1` MUST cover：

- service DID allowlist
- auditable E2EE 或受控 plaintext-visible boundary
- break-glass audit
- server ACL 和 quarantine
- sender-constrained（PoP）会话出示：常规写与敏感读 MUST 用 `session_public_key` 的 RFC 9421 HTTP Message Signature 出示；生产 current-v1 受保护 endpoint 对裸 bearer 的拒绝规则见 §15.1

`ak.profile.isolated_sovereign_network.v1` MUST cover：

- 私有 registry / witness
- closed federation default
- 导入导出审查
- 外部服务与 applet allowlist

`ak.profile.accountable_principals.strict_reject.v1` 是 deployment hardening profile。声明该 profile 的 Realm / deployment MUST 在 `Actor Profile.accountable_principal_ids[]` 中任一 DID 缺少 active `ak.identity.accountability_grant` 时拒绝整个 `ak.profile.create` / `ak.profile.update` Event（`failed_precondition`, reason=`accountability_grant_missing`），不得使用默认的"strip unverifiable entry + audit log"路径。未声明该 profile 时，默认行为仍是 [`models/actor.md` §3.3.1](../models/actor.md) 的剔除 + audit log。

## 18. Agent Runtime

`ak.profile.agent_runtime.v1` 适用于 AI agent、bot、automation。

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

### 18.1 Personal Agent Provisioning

`ak.profile.personal_agent_provisioning.v1` 注册 controller-面的 personal native agent management surface,扩展 `ak.profile.agent_runtime.v1`。

MUST 支持:
- `POST /_arkret/self/agents` (`ak.self.agent.command.provision`) 分配 managed Agent DID / Agent PCR binding，在 Agent DID accepted inception history 的唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 只固定域分离 `requested_scope_digest`，完整 `requested_scope` 保持 controller-private，在 controller PCR 仅写 `ak.identity.accountability_grant` + selector claim；必填且 immutable 的 `requested_scope` 记录 Agent key/session 的全局权限硬上限，但 provisioning 不得物化任何 Realm grant；后续 Agent key scope、Realm grant、participation 与 session request 可更窄但不得超过该上限；返回 `requested_scope_digest`、`pcr_recovery.status=pending` + pairing request，controller 必须重算 digest 后再继续，并通过 verifier/audience/challenge-bound 的 `ak.schema.agent_requested_scope_disclosure.v1` 私有出示完整 scope；controller E2EE client 再本地生成并提交 Agent PCR MLS/genesis/Profile state，服务端不得生成 MLS private state
- controller-owned `backup_class=mls_history` active series 按 [`../identity/key-management.md` §7.5.6](../identity/key-management.md) 备份 Agent PCR state：managed binding 进入 public index、plaintext keybag 与 AAD，使用 controller `recovery_public_key` / current recovery policy；Agent runtime private key 永不备份，也不为 Agent 生成独立 24 词
- `POST /_arkret/gate/account/agent-key-pair` (`ak.gate.account.command.pair_agent_key`) 必须先验证 `pcr_recovery.status=ready`，再校验 `verification_method` 与 `agent_id` 一致性并写入 `ak.agent.key.authorize`；agent 已有 active key 时(runtime replacement re-pairing)以单一 controller-signed authorize Event 的精确 `supersedes[]` 原子替换全部既有 active authorization
- Provisioning `status` 枚举:`pending_runtime_key` / `active` / `paused` / `pairing_expired` / `deactivated`(`pairing_expired` 仅描述从未完成首次配对的 agent；仅 `paused` 可带 open replacement handle，该 handle 是属性而非状态)
- Pairing expiry 仅把尚未首次配对的 agent 投影为 `pairing_expired`，不得创建、撤销或改写任何 Realm grant；runtime replacement handle 过期无副作用
- `POST /_arkret/self/agents/{agent_id}/renew-pairing` (`ak.self.agent.command.renew_pairing`) 对 bootstrap 状态重开 pairing，或仅对 `paused` agent 执行 runtime replacement；`active` 必须先 pause(见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))
- Agent management surface 中 list/get 是 read-only；renew-pairing 只轮换 profile-local pairing artifact，不写 durable Event；pause/resume/deactivate 写 lifecycle Event；grant attach/detach 分别写 Realm-scoped capability grant/revoke Event
- Longevity-safe 授权链:`ak.agent.key.authorize`、`ak.identity.accountability_grant` 与非 registry-required 的 agent capability grant 的 `expires_at` 均可缺省(revocation-governed);实现 MUST NOT 因缺省 `expires_at` 拒绝这些对象
- Agent provision request 与 list/get projection 使用必填固有字段 `slug`；native personal agent selector claim `ak.schema.agent_selector_claim.v1` 与 Actor Profile 投影 hint 使用外部引用字段 `agent_slug`，并支持 `@<controller-handle>/<agent_slug>` 输入别名到 agent `subject_id` 的唯一解析；slug 不是 handle、公开 Directory search/list key 或授权主体
- Draft-only family:`ak.agent.draft.propose` / `ak.agent.action_request` / `ak.agent.action_approve` / `ak.agent.action_reject`,materialize 为 controller-owned `ak.agent.draft.v1` encrypted account-data
- Draft approval 状态机:`proposed → approved → published`,approval nonce atomic consume
- Event Envelope `executed_by` / `authorization_ref` / reducer-stamped `actor_kind` projection
- Pause/Resume/Deactivate 语义(见 [`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md))
- Controller deactivate / suspend 时,accountable native agents 的 active sessions revocation 链失效
- Sidecar exposure 披露：激活新 Agent 前 UI MUST 显式披露其在完成 access/MLS reconciliation 后将获得现有 Sidecar 未来内容访问权（联动 `ak.profile.agent_sidecar.v1`）

MUST NOT:
- 为 provisioning 引入独立 durable `ak.self.agent.command.provision` Event，或在 provision fan-out 中加入 Agent Profile、Agent key authorization、Realm capability grant；`ak.self.agent.command.provision` 只作为 aggregate operation id 存在，其 durable outputs 仅为 controller PCR 中既有 accountability / selector Event
- 返回长期 private key、refresh token 或可直接长期调用 Events API 的 bearer token
- 引入 custom URI scheme(`arkret://` 等)
- 把 `agent_slug` 当作 grant subject、actor attribution、membership key、delivery key、Directory search key 或 audit attribution source
- 让服务端生成/托管 Agent PCR MLS private state，跨 actor 读取 Agent backup，以 `single_point_of_failure` 绕过 managed-PCR recovery gate，或备份/克隆 Agent runtime private key

### 18.2 Agent Auth

`ak.profile.agent_auth.v1` 注册 agent runtime 的 authentication surface,与 `ak.profile.personal_agent_provisioning.v1` 解耦。

MUST 支持:
- 复用 `POST /_arkret/gate/account/session-grants` 通过 `proof.proof_kind="agent_key_proof"` 分支
- 独立 schema branch、独立 proof validator、独立 returned scope(交集 from agent key authorization / capability grant / Realm policy / requested scope)
- `agent_scope_request` overlay 与 `scope_details` response overlay
- key proof 绑定 `challenge`(也充当 per-request nonce,服务端 MUST 在 replay window 内拒绝同值) / `audience` / `request_canonical_digest` / agent principal(由 `principal_id` + `proof.verification_method` 一致性 enforced) / `expires_at`。Wire 不引入独立的 `nonce` 字段；agent proof schema 仅有 `challenge`,它就是 nonce 概念的承载者
- Replay table 覆盖 proof `expires_at` 后的 grace window
- Session TTL 默认 ≤ 15 分钟,profile 可声明更长但 ≤ 60 分钟
- Structured human approval request 返回统一错误信封：`error.code=claim_required`，`error.details={reason_code: human_approval_required, approval_request_id}`；details 必须通过 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`，且不得向 agent runtime 展示 CAPTCHA / OTP。实现必须通过 `ak.vector.agent_auth.human_approval_required.v1`

MUST NOT:
- 把 `agent_key_proof` 降级走 password / OIDC / passkey validator fallback
- 在 session grant 中授予 E2EE history key、secret storage 或长期 device 权限
- 把 controller 进入 `deactivated` / `suspended` 后的 agent session 视为有效

### 18.3 Agent Delegation Policy

`ak.profile.agent_delegation_policy.v1` 注册 capability vocabulary 与 act-on-behalf attribution 规则。

MUST 支持:
- Effective permission rule:`controller-approved grant AND controller's own delegable authority AND Realm policy AND resource selector / constraints AND agent key scope AND requested session scope AND current revocation / freshness state`,默认拒绝 wildcard
- Canonical constraint vocabulary:`allowed_tracks` / `allowed_strand_ids` / `allowed_data_classes` / `allowed_endpoints` / `rate_limit` / `approval_required` / `controller_approval_required` / `accountability_required`
- Reply-as-agent 与 act-on-behalf wire(`actor_id` / `executed_by` / `authorization_ref`)与双重署名渲染
- act-on-behalf 默认 fresh approval 粒度 `(action, target_strand)` + 短期 temporal window
- Realm policy 必须能分别控制 native personal agent 与 Applet / Ghost Actor

MUST NOT:
- 让 agent 自动继承 controller 在 Realm 内的最大权限
- 把 `act_on_behalf_allowed` 当作 constraint;它由 attribution + capability + approval 组合表达

### 18.4 Agent Sidecar

`ak.profile.agent_sidecar.v1` 注册独立 `ak.schema.agent_sidecar.v1` 对象及其 controller-owned private AI workspace 行为。它依赖 Circle backing-scope、MLS、personal agent provisioning 与 auth profiles，但 Sidecar 本身不是 Circle profile。

MUST 支持:
- `POST /_arkret/self/agent-sidecars:ensure`（`ak.self.agent.sidecar.command.ensure`）幂等返回 `{ok, sidecar_id, private_strand_id, private_relation_id, access_readiness, pending_access_reconciliations}`；pending 数组始终存在
- `GET /_arkret/self/agent-sidecars/{sidecar_id}` 与 list query 作为唯一 canonical read surface，返回强类型 Sidecar + desired/effective access；普通 Circle API 不得代替
- `context_ref` polymorphic descriptor(`relation_id` 单独 / `strand_id` 加可选 `track_name` + 可选 seal)
- Closed request schema(reject unknown top-level fields)
- Fixed reuse：Sidecar `(realm_id, controller_id)`；private Strand `(sidecar_id, normalized_context_ref)`
- `ak.sidecar.create`、backing Circle、初始 access、private Strand 与 Relation 原子建立；caller 不提供 Circle shape/ID
- `eligible_sidecar_agent(realm, controller, agent)` 派生 desired access；backing Circle membership/MLS state 只由 reducer/service 主动 fan-out
- desired access、effective access、backing membership、MLS/device readiness 分离投影；发送只在安全交集 ready 后开放
- `addressed_agent_ids[]` per-ensure ephemeral(服务端不持久化);MUST NOT 包含 controller 自身
- 历史 backfill 经由 application-level resend（显式 plaintext 披露）；不得使用 MLS exporter secret / past commit secret
- Cross-Realm fan-out：Agent deactivate 只影响该 Agent 实际进入 desired access 的 Sidecars 及其 backing scopes
- `agent_sidecar_of` relation kind(weak-semantic、non-structural、non-cascading);`fields` 不含 `target_realm_id`
- Sidecar 及其 backing Circle/private Strand 不出现在普通 Circle、Realm-wide navigation、board/list、public search 或 scope picker
- 多 agent publish 时 `actor_id` / `executed_by` MUST 是单一签发 agent principal
- Retention 继承目标 Realm,profile 可收紧不可放宽
- `ak.agent.sidecar_projection.v1` controller-private encrypted account-data SHOULD 注册(跨设备 UI 一致性)

MUST NOT:
- 在目标公开 Strand 写 target-side reverse `agent_sidecar_of` relation
- 修改目标 Strand `tracks` map 或写入 target-side metadata / Relation / watch / unread / search / notification state
- 接受 caller-provided `participant_model`、member list、Circle title/display/join rule 或 backing Circle id
- 为同一 `(realm_id, controller_id)` 创建第二个 non-tombstoned Sidecar 或第二个 active backing Circle

### 18.5 Agent Participation Policy

`ak.profile.agent_participation_policy.v1` 注册 native personal agent 的分层 participation ceiling 与 controller selection 面。它继承 `ak.profile.personal_agent_provisioning.v1`。

MUST 支持:
- `ak.self.agent.participation.resource.replace`
- `ak.self.agent.participation.resource.get`
- deployment ⊇ Realm ⊇ Circle ⊇ Strand 的 tighten-only ceiling 校验
- effective participation = provision-derived global ceiling ∩ deployment/Realm/Circle/Strand governance ceiling ∩ controller selection；`reply` 要求 provision actions 同时含 `ak.message.create` 与 `ak.reaction.add`，`accept_third_party_mention` 要求 `ak.event.read`，`act_on_behalf` 要求 `ak.message.create` 加适用的 controller approval / accountability constraints
- provision-derived participation ceiling MUST 从完整 `requested_scope` 现场派生，不得由调用方直接提供预计算三位；缺 `ak.reaction.add` 时 `reply=false`，缺适用于 `ak.message.create` 的 `claim_based{subtype=approval|accountability}` mandatory constraint 时 `act_on_behalf=false`
- 第三方 mention gate：`accept_third_party_mention=false` 时不得向该 agent 派生 mention notification、inbox row、push wakeup 或 agent subscribe 投影；gate 在 message event fanout 时一次性求值，participation 之后翻转不追溯补发或撤销既有派生（[strand-and-message.md §9.4.5](../models/strand-and-message.md)）
- `scope_details.participation[]` session overlay，形态与 `agent-operations.schema.json#/$defs/agent_participation_entry` 对齐

MUST NOT:
- 允许 Strand / Circle ceiling 放宽父级 ceiling
- 把 controller selection 当作安全边界；服务端仍必须通过 capability、dispatcher 和 reducer 强制执行
- 在 effective ceiling unknown 或 stale 时默认允许 agent participation

## 19. Applet Service Family

Applet v1 家族适用于运行 Applet 集成服务。`ak.profile.applet_service.v1` 是 base bot-only profile；桥接外部系统、Ghost Actor、portal Realm、delegated acting、E2EE join 和 widget 能力必须通过继承 profile 显式声明。

`ak.profile.applet_service.v1` MUST 支持：

- signed `applet_registration`
- namespace declaration and matching
- ping / describe endpoint
- transaction push endpoint
- transaction idempotency
- transaction push per-delivery source signature anchor（`source_signature_anchor`）
- idempotency / replay binding across `Source-Service-ID`、`Destination-Service-ID`、`Idempotency-Key`、canonical body digest and source verification method
- capability enforcement
- HTTP message signature verification（RFC 9421，覆盖 `@method` / `@target-uri` / `@authority` / `content-digest` / `source-service-id` / `destination-service-id` / `idempotency-key`）
- event signature verification
- bot actor attribution
- `ak.edge.applet.command.transaction` as operation_id only, never as durable Event kind
- fail-closed reasons for transaction push: `http_signature_required`、`http_signature_invalid`、`signature_window_invalid`、`duplicate_conflict`、`applet_registration_unauthorized`、`applet_namespace_mismatch`

MUST NOT：

- 把 namespace 命中当作写权限
- 静默 impersonate native user
- 在无授权时接收全网 sync stream
- 只凭裸 `Idempotency-Key`、body 内 `source_service_id` 或首次握手状态接受 transaction push replay
- 在未提示边界的情况下把 E2EE 内容桥接到非 E2EE 网络

`ak.profile.applet_bridge.v1` inherits `ak.profile.applet_service.v1` and MUST 支持：

- resolve actor endpoint
- resolve realm endpoint
- protocol metadata endpoint
- Ghost Actor accountability metadata
- portal Realm metadata
- external event deduplication
- bridge error event

`ak.profile.applet_delegated.v1` inherits `ak.profile.applet_service.v1` and MUST 支持 delegated native-user acting 的 `executed_by` / `authorization_ref` / `applet_id` 校验、dual-signature attribution 与 `registration_epoch` evidence verification。

`ak.profile.applet_e2ee_join.v1` inherits `ak.profile.applet_service.v1` and MUST 支持独立 E2EE join authorization、MLS roster applet-managed 标注，并在缺少授权时 fail closed with `applet_e2ee_join_unauthorized`。

`ak.profile.applet_widget.v1` inherits `ak.profile.applet_service.v1` and MUST 支持 widget origin isolation、CSP、scoped token、consent 与 host session/device-key non-disclosure。

Applet bridge SHOULD 支持：

- third-party user / location lookup
- admin revoke / pause
- per-Realm bridge policy
- Applet health and lag metrics

## 19a. Franking (E2EE Abuse Reporting)

`ak.profile.franking.v1` 适用于在 E2EE Realm 中提供可验证投递证明的服务（典型为 Sync Service / MIMI provider facade / Principal Server）。

参考：`governance/content-moderation.md` §3.4 与 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) franking 段落。

MUST 支持：

- 在接收 E2EE Event Envelope 时签发 `ak.moderation.franking_proof` 事件，绑定 `event_id`、`ciphertext_digest`、`aad_digest`、`sender_claim` (含 mls_group_id + epoch)、`received_by` (service DID)、`received_at`、`replay_nonce`。
- franking proof `signature` 由 service DID 当前有效 verification method 签发，覆盖 franking proof canonical bytes。
- 每条 franking proof 必须可被独立 verify：service DID Document 解析 + verification method 有效期 + Realm service binding 校验 + payload hash 重算。
- 接收 reporter 提交的 `ak.self.moderation.command.report` 时，把 franking proof ID 与 report ID 绑定为审计链一部分；不得仅信 reporter 单方声称。
- franking proof cache TTL 与 service key rotation 同步：service DID 的 verification method 撤销后，旧 franking proof 仍可历史验证（用历史 key state），但不签发新 franking proof。

MUST NOT：

- 在 franking proof 中包含明文正文、附件文件名、reply 摘录、mention 列表、私有 handle 或解密内容 hash，除非 Realm policy 显式允许该字段。
- 用 franking proof 单独证明明文含义——franking proof 只证明"该密文事件被该 service 在该时间收到"。
- 跨 Realm 复用同一 franking proof（`replay_nonce` 与 `realm_id` 必须进 franking proof 签名）。
- 在没有有效 service DID 绑定的情况下签发 franking proof。

SHOULD 支持：

- franking proof batch endpoint（一次 fetch 多条 franking proof）以减少 audit traffic。
- franking proof inclusion proof：franking proof 可被签入定期 franking-proof log Merkle tree，向举报者证明"该 franking proof 不是后补的"。该 inclusion proof 与 Seal state_root 独立，因为 franking proof 不进入 Realm seal frontier（franking proof 是 service-side audit material，不改变协作状态）。
- 显式 `franking_proof_unavailable` 错误码，让 reporter 客户端知道 service 当前不签发 franking proof（如 service downgrade / outage），而不是误以为消息根本未投递。

## 19b. Realtime Media Server

`ak.profile.webrtc_media.v1` 适用于提供 ICE config / TURN / SFU 等 RTC 基础设施的服务。

参考：[`crypto-media/webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)（ICE config / TURN）、[`crypto-media/media-service-binding.md`](../crypto-media/media-service-binding.md)（SFU / 媒体服务绑定）与 [`crypto-media/call-state.md`](../crypto-media/call-state.md)（通话状态）。

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

## 20. Conformance 测试要求

每个 profile SHOULD 提供：

- schema validation tests
- signature verification tests
- idempotency tests
- reducer convergence tests（含 CBA/Lattice 向量）
- CBA/Lattice vectors（见 `conformance-vectors.md`）
- Event Envelope negative vectors（见 `artifacts/fixtures/event-envelope-negative-fixture.json`）
- redaction vectors（见 `conformance-vectors.md`）
- capability vectors（见 `conformance-vectors.md`）
- sync fixture、state-resolution fixture、capability fixture 和 privacy/security fixture（见 `artifacts/fixtures/*.json`）
- authorization tests
- privacy regression tests
- error response tests
- downgrade / unsupported feature tests
- unknown-field rejection / extension-slot preservation tests

所有 profile MUST 能按 `../models/common-fields.md` 与各对象专属文件（`realm-and-space.md` / `strand-and-message.md` / `morph.md` / `relation.md` / `event-and-patch.md` 等）解码和验证其声明支持的核心对象字段。实现 MUST 拒绝 canonical object schema 未声明的未知字段，对 schema 显式声明扩展位（已登记的 `payload.x_*` 槽、`requirements.critical_extensions[].parameters`）中的未识别内容 MUST 保留，并覆盖“schema 未声明字段被拒绝”与“扩展位内容在 hash/signature 校验、存储、联邦转发、backfill 后仍存在”的测试；未知 critical feature MUST fail closed。实现 MUST reject 类型错误、必填字段缺失、非法 enum、非法 ID/hash/timestamp/cursor pattern，以及违反条件必填规则的对象。标准 Event 必须加载 `event-kind-registry.json` 与 `event-payload.schema.json`，确认每个 active durable kind 都有可执行 payload 校验路径。

所有 profile MUST 按 `conformance-vectors.md` 覆盖 canonical JSON、hash、signature binding、Ed25519 detached JWS fixture、HLC 和 cursor 的基础向量。Events API、Full Client 与 E2EE Client MUST 额外覆盖 event digest；Events API 节点 SHOULD 覆盖 event-batch receipt digest；E2EE Client 和 Principal Server MUST 覆盖 encrypted envelope digest。

E2EE profile MUST 额外提供：

- KeyPackage verification vector
- KeyPackage claim single-use vector
- MLS Governance Binding root mismatch vector（`governance_binding` 任一 root 不匹配 Seal view）
- minimal-metadata identity link vector
- AAD visibility vector
- MLS epoch transition vector
- encrypted payload vector
- removed member cannot decrypt vector
- E2EE franking report vector

Client Sync 相关 profile MUST/SHOULD 按 `conformance-vectors.md` 执行对应向量：

- Minimal Client MUST 覆盖基础排序、tie break、pagination gap、backfill order 和 token expiry recovery。
- Chat MVP Client（`ak.profile.chat_mvp.v1`）MUST 覆盖 Strand discussion timeline、message edit/redaction、reaction OR-Set、discussion history visibility 和 membership 裁剪。
- Kanban MVP Client（`ak.profile.kanban_mvp.v1`）MUST 覆盖 Board projection、Strand move/reorder、position edge conflict、CAS stale reorder 和 wait-for query。
- Full Client MUST 额外覆盖 snapshot frontier、state_after 与 decryption_pending 的 UI / cache 恢复行为。
- E2EE Client MUST 覆盖 MLS epoch backfill、decryption_pending recovery 和 removed member fail closed。
- Principal Server SHOULD 覆盖 duplicate suppression、backfill order、encrypted payload forwarding 和不能转发解密材料。
- Snapshot bootstrap MUST 覆盖 `event_set_commitment` root、covered event set、conflict/soft-fail/quarantine 摘要和 inclusion / omission challenge hint。

上述 Minimal Client 与 Chat MVP 的 prose MUST 覆盖项在 `conformance-profiles.json#profile_requirements` 中通过 `required_fixtures` 和 `prose_requirement_coverage` 建立映射；实现声明 profile 时必须同时提供这些 fixture / runner 的通过结果。

Privacy / security hardening profile MUST 额外覆盖：

- hidden Realm resolve 的不可见/不存在响应同形态
- private contact discovery 的 batch padding 与 cardinality protection
- plaintext-visible service 对私有正文处理的强制拒绝
- private blob HEAD / Range anti-enumeration
- blind wakeup push payload 最小披露

Moderation profile MUST 额外覆盖：

- `ak.schema.moderation_report.v1`
- `ak.schema.moderation_queue_item.v1`
- `ak.self.moderation.command.report` payload schema validation
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
- Ghost Actor mapping vector
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
  "service_id": "did:webvh:z6h868X7rdVapSQTt7ehsQB8v:server.example.com",
  "service_type": "principal_server",
  "protocol_version": "1.0",
  "supported_profiles": [
    "ak.profile.principal_server.v1"
  ],
  "supported_features": [
    "sync_stream",
    "snapshot_bootstrap",
    "plaintext_visibility_classes"
  ],
  "reducer_profiles": [
    "ak.profile.federation_minimal.v1"
  ],
  "schema_profiles": [
    "ak.schema.event.v1"
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

## 23. 库 / SDK 一致性说明

Conformance 面此前全部以部署形态 profile 为单位（`profile_requirements` 只绑 endpoints / event kinds / schemas / fixtures）。但本文与 [conformance-vectors.md](./conformance-vectors.md) 中存在一批**客户端侧 MUST**，它们约束的是实现内部行为或库 API 形状（例如"proof 验证不能被跳过""cursor MUST NOT 被结构化解析"），部署级黑盒测试无法完整覆盖。本节为库 / SDK（区别于部署形态 client）提供统一的可测性分级、条款映射与 API 形状实现指引。

部署 profile 的 vector 集合不得从本节表格反推；其唯一算法见 [`conformance-suite.md` §2](./conformance-suite.md) 的向量适用性闭包，并由 `vector-registry.json` 的显式 selector 与 `profile_requirements` 的继承后 fixture closure 共同决定。

**本节定位（normative for grading and claims）**：本节不新增 profile、不新增 wire MUST、不扩展部署用途的 `profile_requirements`；表中条款全部是既有条款的重述，其覆盖映射仍在各原始定义位置（§2.1.1 的悬空禁令不因本节复述而重复计数）。`conformance-profiles.json#sdk_conformance_contract` 为这些条款提供独立机读 claim 面：稳定 `clause_id`、V/A/U 等级、证据类型和 claim 必填字段。SDK 声明不得复用 deployment profile 字段，也不得以易漂移的表格行号代替 clause ID。

**收录规则（normative）**：任何约束客户端/SDK 内部行为、公开 API 形状或自动网络行为，且部署黑盒 profile 不能完整证明的 MUST / MUST NOT，MUST 在本节分配稳定 clause ID；新增或修改此类条款时 reviewer MUST 同步评估并更新 `sdk_conformance_contract`。未列入本契约的 prose 条款不在 SDK claim 的签名覆盖范围内，但其规范力不因此降低；不得用未知私有 clause ID扩展封闭 claim。

### 23.1 可测性三级

| 等级 | 名称 | 含义 | 核查手段 |
| --- | --- | --- | --- |
| **V** | 黑盒向量可测 | 条款违反会在 wire 可观测行为（接受/拒绝、错误码、出向流量）上暴露 | `vector-registry.json` 中的 conformance vector 与 `artifacts/fixtures/*.json` |
| **A** | 仅 API 形状可保证 | 条款约束库内部行为，黑盒不可靠观测；但可以通过**不提供违规捷径的公开 API 面**在类型/接口层面结构性排除 | SDK 公开 API 面审查（§23.3 指引） |
| **U** | 仅审计可保证 | 条款既非 wire 可观测、也无法靠 API 形状排除（涉及配置面、内部执行顺序或数据流向） | 代码审计 / 实现自述 + 抽样复核 |

一条 prose MUST 可以同时命中多级：拒收行为是 V，"不得提供跳过入口"是 A，内部顺序是 U。分级取**最强可达手段**标注，并列出补充级。

### 23.2 客户端侧 MUST 条款的可测性映射

| # | 条款（摘述） | 真相源 | 分级 |
| --- | --- | --- | --- |
| <a id="ak-sdk-001"></a>1 | Event Envelope MUST 先过 `ak.schema.event.v1` 与 payload class 校验，失败 MUST `schema_violation`，不得进入 reducer（先验证后消费） | 本文 §3 | **V**（`ak.vector.envelope.negative_admission.v1` / `event-envelope-negative-fixture.json`）；"先于消费"的内部顺序为 U |
| <a id="ak-sdk-002"></a>2 | `proof`、`hlc`、`actor_seq`、`prev_refs`、`refs[role=authorized_by]` 在 reducer 与验证逻辑中不能被跳过 | 本文 §3 | **V**（负例向量拒收）；"库不得暴露跳过入口"为 A |
| <a id="ak-sdk-003"></a>3 | `auth` 约束必须执行，不得通过客户端配置豁免 | 本文 §3 | **U**（配置面审计）；辅以 A（不提供豁免配置项） |
| <a id="ak-sdk-004"></a>4 | 对 `causal` 关系、`revoked` 与 `proof` 失效状态 MUST fail-closed，不得静默接受 | 本文 §3；conformance-vectors §2.19 | **V**（`ak.vector.cba_lattice.*` 并发撤销 fail closed 向量） |
| <a id="ak-sdk-005"></a>5 | cursor MUST 当作不透明字符串保存回传；SDK / 应用层 MUST NOT 解析内部字段构造请求 | conformance-vectors §1.11（`ak.vector.encoding.cursor_opaque.core.v1`） | **A**（不暴露结构化解码 API）；黑盒仅能以变异 handle cursor 抽样旁证 |
| <a id="ak-sdk-006"></a>6 | canonicalization 失败（duplicate key、malformed UTF-8、隐式 NFC 归一）MUST reject，不得"修复"后继续 hash / 验签 | conformance-vectors §1.4–1.5 | **V**（encoding 负例向量） |
| <a id="ak-sdk-007"></a>7 | malformed HLC MUST reject，不得截断、补零或大小写折叠后接受 | conformance-vectors §1.9–1.10 | **V** |
| <a id="ak-sdk-008"></a>8 | 重试 / 等待期间 `prev_refs`、`refs[role=authorized_by]`、`actor_seq` 约束 MUST NOT 放松 | conformance-vectors §1.10 | **V**（重放向量）；内部重试路径为 U |
| <a id="ak-sdk-009"></a>9 | E2EE：`governance_binding` root 不匹配 MUST NOT 继续解密正文；未验证 KeyPackage 所属 DID 不得加密 | 本文 §6；conformance-vectors §2.5.1 | **V**（root mismatch 拒收向量）；"不解密"的本地行为为 U，KeyPackage DID 验证入口为 A |
| <a id="ak-sdk-010"></a>10 | E2EE：MUST NOT 把明文 / 解密密钥交给未授权 Sync / search / projection 服务 | 本文 §6、§8 | **V**（privacy regression 出向流量观测）为主；本地泄露面为 U |
| <a id="ak-sdk-011"></a>11 | 轻客户端 MUST NOT 用单 leaf 授权结论接受 DataEvent，MUST hold pending 或 fail closed | conformance-vectors §2.19 Case C | **V**（以 SDK API 输出为观测点） |
| <a id="ak-sdk-012"></a>12 | late key recovery：`T0` 不可见 / key source unauthorized 时 MUST 拒绝解密（先验证后消费） | conformance-vectors late_key_recovery 向量族 | **V** |
| <a id="ak-sdk-013"></a>13 | 未知 critical feature / `requirements` 不匹配 MUST fail closed | 本文 §3、§20 | **V**（downgrade / unsupported feature tests） |
| <a id="ak-sdk-014"></a>14 | 生产 profile MUST 拒绝测试 DID、测试 key id、测试 trust domain | conformance-vectors §1.14 | **V** |
| <a id="ak-sdk-015"></a>15 | 裁剪构建若移除任一已声明 profile 的 MUST 能力，MUST 同时移除该 profile claim；构建产物的 capability inventory 与 claim 必须对账 | 本文 §2.1.2 | **U**（构建配置审计）；辅以 A（公开 API / capability inventory） |
| <a id="ak-sdk-016"></a>16 | 开放注册集中的未知值 MUST 在反序列化时原样保留，不得因本地 registry 快照较旧而使整个对象解码失败 | schema-registry §6.1 | **V**（`ak.vector.encoding.open_registry_unknown_roundtrip.v1`）；辅以 A（非封闭 enum API 形状） |
| <a id="ak-sdk-017"></a>17 | schema 明示的 `x_*` 与 `critical_extensions[].parameters` 未识别内容 MUST 在 decode/encode、存储、联邦转发与 backfill 后逐字节保留，且继续进入 canonical bytes | 本文 §20；schema-registry §6 | **V**（`ak.vector.encoding.extension_slot_roundtrip.v1`）；内部存储/转发路径为 U |
| <a id="ak-sdk-018"></a>18 | `ack_token` MUST 作为不透明字符串原样回传，SDK MUST NOT 解析其内部结构 | client-sync §10.1 | **A**（不暴露结构化解码 API） |
| <a id="ak-sdk-019"></a>19 | `retry_safe=false` 的 operation MUST NOT 自动全量重试；请求内容改变时 MUST 换 request key | api-conventions §6.2 | **A/U**（重试 API 与配置审计） |
| <a id="ak-sdk-020"></a>20 | 客户端 MUST 优先遵循 `Retry-After`，不得按本地上限截断后提前重试 | api-conventions §9 | **V/U**（注入时钟与出向请求观测） |
| <a id="ak-sdk-021"></a>21 | 客户端 MUST 仅按 `has_more` 决定是否继续分页 | api-conventions §7.1 | **V/A**（分页响应向量与 paginator API） |
| <a id="ak-sdk-022"></a>22 | SDK MUST 暴露 canonical confusable check 为可调用 utility | encoding §2.1 | **V/A**（confusable test set 与 public API inventory） |

### 23.3 "仅 API 形状可保证"类的 SDK 实现指引

针对上表 A 级（含 A 补充级）条款，SDK：

- SHOULD NOT 在客户端可达的公开 API 面提供 cursor 结构化解码（base64url 解码 + 内部字段访问）helper；cursor SHOULD 以不透明 newtype / opaque string 类型建模（对应条款 5）。
- SHOULD NOT 提供跳过 proof / schema 验证的公开入口（`verify=false` 参数、insecure 构造器、直接产出"已验证"类型的裸构造函数等）；测试性 bypass 若确需存在，SHOULD 置于非默认 feature / 内部模块，不得从默认公开面可达（对应条款 1、2、9）。
- SHOULD 采用"验证即构造"（parse, don't validate）类型形态：未通过 envelope schema + proof 验证的字节不产出可直接消费的 Event 值类型（对应条款 1、2）。
- SHOULD 把 fail-closed 判定（causal / revoked / proof 失效、未知 critical feature）实现为默认路径；任何放宽行为 SHOULD 是显式、可审计的 opt-in，而非默认参数（对应条款 3、4、13）。
- SHOULD 将开放注册集建模为可保留未知字符串的 non-exhaustive 类型，并为 schema 明示扩展位保留 raw canonical value；不得用封闭 enum 或丢弃未知字段的通用反序列化默认破坏条款 16、17。
- SHOULD 将 cursor 与 `ack_token` 都建模为 opaque newtype，并让 paginator 只消费 `has_more`；自动重试器必须显式消费 operation 的 `retry_safe` 与服务端 `Retry-After`（对应条款 18–21）。
- SHOULD 提供不依赖 UI 的 confusable-check public utility，并以 canonical test set 固定输出（对应条款 22）。

声明遵循本节的 SDK MUST 发布符合 [`sdk-conformance-claim.schema.json`](../../artifacts/schemas/sdk-conformance-claim.schema.json)（`ak.schema.sdk_conformance_claim.v1`）的 machine-readable claim；`ak.vector.sdk_conformance.claim_validation.v1` 与 `sdk-conformance-claim-fixture.json` 是其可执行证据。SDK 为每个适用 `AK-SDK-NNN` clause 提供一个 `clause_claims[]` 条目，至少给出 `result` 与不可变 `evidence[]` 引用；每条 evidence 都 MUST 携带非零 content digest。V 级证据引用向量结果，A级引用 public API inventory，U 级引用代码 / 配置 / 数据流审计；`not_applicable` 必须携带机器可读理由。SDK release 必须以 `sdk_artifact.uri + sdk_artifact.digest` 绑定确切发布物，同时钉定非零 `spec_revision` 与 `sdk_conformance_contract` 的 canonical digest，防止用新条款解释旧证据或把一份结果移植到另一产物。claim 必须声明 `issued_at`、issuer DID 与 verification method；`proof.signature` 覆盖 UTF-8 `"arkret-sdk-conformance-claim-v1\n"` 加移除顶层 `proof` 后对象的 RFC 8785 JCS bytes，`proof.kid` 必须等于 `issuer.verification_method`。验证器除执行 JSON Schema 外，MUST 验证发布物、证据与 contract digest，解析 spec revision，验证 issuer 当前授权及签名，并执行 clause ID 唯一性与已知 clause 集合检查；任一步失败都不得接受 conformance 声明，重复 clause MUST `duplicate_clause_claim`。

### 23.4 与机读面的关系

V 级条款的可执行输入仍是 `vector-registry.json` 与 `artifacts/fixtures/*.json`；A / U 级条款的证据仍分别来自 API 面审查和审计。三类结果统一由 `conformance-profiles.json#sdk_conformance_contract` 声明，且与部署 `profile_requirements` 分离。验证器 MUST 拒绝未知 clause ID、重复 clause、缺证据 digest、缺 artifact binding、零值或不匹配的 spec / contract digest、无效或未授权签名、使用表格行号作为 ID，或 claim 钉定的 contract digest 与本地 canonical artifact 不一致的声明。
