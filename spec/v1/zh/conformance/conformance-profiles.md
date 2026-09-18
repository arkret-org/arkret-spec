---
title: 实现 Profile 与一致性要求
status: candidate
normative: true
stability: v1
updated: 2026-09-12
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

Profile / capability 声明也是异构实现互通的协商基础：双方只使用声明能力的交集，未声明的 extension 能力 MUST fail closed。该机制见 [overview/current-contract.md](../overview/current-contract.md) §5。

## 2. Profile 命名

Profile 名称使用：

```text
ak.profile.<name>.v<major>
```

示例：

- `ak.profile.minimal_client.v1`
- `ak.profile.station_events_api.v1`
- `ak.profile.station.v1`
- `ak.profile.full_client.v1`
- `ak.profile.e2ee_client.v1`
- `ak.profile.federation_minimal.v1`
- `ak.profile.mimi_interop.v1`

## 2.1 v1 MVP 分层

为降低实现复杂度，v1 profile 分为四个声明层。`artifacts/profiles/conformance-profiles.json.profile_sets` 是机器可读来源；`v1_profile_catalog` 不是 bundle requirement，实现只声明自己实际支持的 profile、event kind、schema 和 operation。

| 层级 | 含义 | 典型内容 |
| --- | --- | --- |
| Minimal interop floor | 仅声称 v1 Event Store interop 时的最小声明。 | `ak.profile.core_event_store.v1`：Event Envelope、逐 stream authority commit log、events submit/get/list/checkpoint/backfill、标准错误。 |
| Stable profile catalog | v1 stable catalog 中可独立声明的实现 profile，不构成默认全量包。 | `chat_mvp`、`kanban_mvp`、`minimal_client`、`full_client`、`station`、`identity_registry`、`blob_node`、`push_gateway`、`federation_minimal`、`sovereign_client` 等。 |
| Extension（v1 interop） | 在 v1 stable catalog 中可独立声明，但**只在显式 opt-in 时启用**。未声明的实现遇到这些能力 MUST fail closed。 | `ak.profile.encoding.cbor.v1`、`ak.profile.hash.blake3.v1`（编码 / 哈希 扩展：只有对端显式声明后才启用，未声明一侧遇到该编码或哈希 MUST fail closed）。 |
| Interop staging extension | **不属于 v1 core interop floor**，跟踪外部演进标准；声明 v1 core 的实现 MAY 完全省略。 | MIMI interop、Applet integration、Agent protocol bridge 等；这些 profile 在外部标准定型后将被稳定版本固定取代。 |

Document、File、Poll 在 v1 MVP 中默认是 Morph profile 或 extension profile，不是 core 标准对象。实现不得因为未来可能标准化这些类型，就在 v1 wire contract 中要求对端支持专用对象类型。

Core identity conformance 要求 DID Core 解析 / 验证抽象、`did:webvh:1.0`（v1 core 唯一 human 注册锚及 MTI/default service adapter）、`did:web`（只作显式 no-history service adapter；human 注册 MUST 以 `unsupported_did_method` 早拒绝）与 `did:key`（用于 deterministic local expansion、设备/Agent 密钥、service evidence 和 `ak.profile.ephemeral_pairwise_principal.v1` 下 exact MLS LeafNode-bound、无账号/PCR/设备目录的 Realm-local actor）。human anchor 的封闭集合只有 `did:webvh`，且 `principal_registration_anchor` 只有 `webvh_registration` 正例；`did:key` 与 `did:web` 均有早拒绝负例。角色资格 MUST 从 `did-method-adapter-registry.json` 的 active adapter 客观属性与 `role_requirements` 推导；profile 的 `allowed_principal_methods`、`allowed_service_methods` 与 `allowed_actor_methods` 是该推导结果的受检副本，不是独立真相源。承担外部身份接纳/解析的 Station、Registry 与独立审计角色 MUST 支持 `did:webvh:1.0` witness / SCID / entry hash chain 验证；full/e2ee 客户端消费自己 Station 的结果，保留 subject、账号、用途与端到端密钥绑定检查，不重放方法历史；自己 Station 的首次接入、重连与认证绑定变化也 MUST 按 [server-trusted-results §1.2](../sync/server-trusted-results.md#12-普通客户端的-station-接入normative) 执行，不能以接入为由恢复历史 verifier。符合性验证须覆盖正常首次接入、预配身份不符、认证权威变化、持久状态重载、并发不同绑定不得覆盖和陌生 redirect 拒绝。以下方法证据验证规则约束接纳该外部证据的服务器/审计角色；method evidence 中的 `parameters.method` MUST 精确等于 `did:webvh:1.0`，缺失或未知版本 MUST `unsupported_did_method`，不得按“当前最新版”解释。组织高保证实现 SHOULD 声明 `ak.profile.organization_high_assurance_identity.v1` 并要求 `did:webvh` witness evidence threshold ≥ 1；`watchers` 只按 adapter 登记为 accepted-but-not-consumed，不参与 authorization。AT Protocol 互通实现 SHOULD 额外声明 `ak.profile.public_network_identity.v1` 并支持 `did:plc` adapter；该 adapter 只产生外部 interop claim，不扩展 v1 principal 创建 allowlist。

v1 的首轮互操作验收 SHOULD 拆成三个可运行闭环：

- `ak.profile.core_event_store.v1`：DID / service discovery、Event Envelope validation、event submit/fetch/backfill、逐 stream RealmCommit position 连续性 validation、idempotent duplicate handling、standard error。
- `ak.profile.chat_mvp.v1`：在 `minimal_client` 之上消费服务器已接纳的 Realm、`ak.member.state`、启用 discussion track 且可设为 primary 的 Strand、Message、Reaction、Redaction、Client Sync timeline 和 history visibility。
- `ak.profile.kanban_mvp.v1`：在 `minimal_client` 之上消费服务器已接纳的 Space（`kind=board/list`）、Strand、`contains` position Relation、`ak.strand.move`、`ak.strand.reorder`、`ak.space.create`、`ak.space.update`、`ak.space.parent`、客户端 Collection projection 和 wait-for query。

`minimal_client`、`full_client`、`station` 等实现 profile 通过声明所支持的闭环（`chat_mvp` / `kanban_mvp`）表达能力；未声明的闭环不得被对端视为默认可用。希望仅做聊天产品而不实现 board/list 的客户端，应声明 `chat_mvp` 而不实现 `kanban_mvp`，并在 `rejected_event_kinds` 中明确拒绝 board/list 相关 kind。

`chat_mvp` 与 `kanban_mvp` 不要求实现任意 Morph renderer、任意 facet reducer 或插件 UI。它们只需要按声明 profile 保留未知 Morph / facet 字段、同步相关 Event、核对 schema 与自己 Station 返回的 capability 结果，并在必须展示时提供 generic Morph fallback。任何依赖特定 `morph_kind` 或 facet 的交互能力 MUST 由额外 profile 显式声明。

Profile 不支持某个标准能力时的默认行为：

- 写入接收方收到 active 标准 Event kind 时，若该 kind 不在本实现声明的 supported_event_kinds / profile 范围内，且该实现负责该 Realm 的 accepted history，MUST 返回 `unsupported_feature`、`unsupported_event_kind`、`schema_violation` 或 quarantine，不得把未知标准事件 accepted 后静默丢给 reducer。
- 只读客户端或 projection 服务遇到未实现但已 accepted 的标准 Event kind，MAY 保留 raw event、显示 generic fallback 或把对应 projection 标记为 incomplete；不得声称已完整执行该 kind 的 reducer 语义。
- 未知 Morph type、未知非 critical extension field 和未声明 renderer 可以保留并忽略，但不能影响授权、排序、状态机、redaction、E2EE、notification 或 state hash。
- Event 的 `requirements.features[]`、`requirements.critical_extensions[]` 或 `requirements.schema[]` 出现不支持的标识时，接收方 MUST fail closed。Fixed reducer semantics 从该 Event 的 authority-commit governance basis 读取；本地未实现时返回 `unsupported_profile`。
- `rejected_event_kinds` 表示 profile 必须拒绝或不接收的 wire scope / kind。`optional_extensions` 表示可以不提供交互能力；它不授权实现静默接受依赖该 extension 的 critical Event。

机器可读默认行为见 `artifacts/profiles/conformance-profiles.json.default_unsupported_behavior`。其中 `must_not_accept`、`must_fail_closed`、`allowed_results` 等字段用于 conformance lint / test，而不是自由文本提示。

Profile 之间的 `inherits` / `depends_on` / `mutually_exclusive_with` 关系以 DAG 形式集中聚合在 [`artifacts/registry/profiles-dependency-graph.json`](../../artifacts/registry/profiles-dependency-graph.json)（canonical mirror，每次新增或修改 profile 关系时 MUST 同步）。该 graph 用于可视化 DAG 工具与 conformance loader：实现 SHOULD 先按 `inherits` 边做拓扑排序，再按 `depends_on` 检查共生约束，最后按 `mutually_exclusive_with` 检查冲突；任一阶段失败 MUST 拒绝 profile claim。

`profile_requirements.enforcement_phases[]` 是封闭执行阶段：`build`、`conformance`、
`startup_claim_guard`、`peer_eligibility`、`runtime_negotiation`、`runtime_admission`。其中：

- `operation_requirements[]` 用 exact `{direction,operation_id,binding_kind}`；`provide` 表示声明方必须提供，`consume` 表示声明方必须能调用/消费。profile 不得用 bundle ID 替代这些 pair。
- `startup_claim_guard` 必须在服务启动公告 profile 前，把本响应所有已登记 bundle 展开的 role-local union 与该 profile 的全部 `provide` pair 对账；任一 pair 不在 union、没有可用 transport endpoint 或被构建 gate 裁掉时，服务 MUST 摘除该 profile claim或启动失败，不能用 profile 反向补出 operation。
- `peer_eligibility` 只用于验证对端 profile/evidence 是否满足业务准入条件，不改变其 Describe 的实时 route union。
- 只有同时提供 `wire_selector_refs[]` 与 `normative_effect_refs[]` 的 requirement 才能声明 `runtime_negotiation` / `runtime_admission`。没有 wire selector/effect 的 profile 仅用于构建、conformance、启动或 peer eligibility，真实业务请求不得每次展开 99 个 block。

这里的 `consume` 清单描述客户端实现需要具备的消费能力，不是要求某一个已连接 Station
提供全部接口的运行时页面门禁。例如 `full_client` 的执行阶段只有 `build` / `conformance`；
新建 Realm 页面不应因该清单还包含 DID 解析、blob 或其它无关操作而整体不可用。
页面、动作和后台任务的可用性按实际依赖的 exact operation/binding、feature 与 limit 判断，
并向实际提供该操作的、已建立信任绑定的服务协商；独立可用的功能不因其它功能缺失被连带关闭。
这不免除客户端的完整 profile conformance 要求，也不允许调用未被目标服务公告的操作。
能力描述尚未取得表示检查未完成，不等同于服务器已明确不支持。

身份托管、服务器内部的 DID method 解析验证、向客户端公开通用解析 API 是不同能力。
WebVH 托管提供签名历史文件，内部解析验证读取并验证方法材料；二者不自动意味着公告了
`ak.root.identity.read.resolve.v1`。使用该公开 API 时，按其提供方的 role-scoped Describe
检查 exact pair；`auth_metadata.account_authority.gate_account_base_url` 只选择账号准入路径，
不能作为该解析 API 已公告或可调用的证据。业务操作返回的已验证身份结果仍按
[服务器信任与结果消费](../sync/server-trusted-results.md) 处理。

### 2.1.1 Profile 数量约束与 Composition 路线（normative for new profiles）

v1 stable + extension catalog 已包含较大的 implementation / deployment / vector / hardening profile 矩阵，组合空间已经较大。为防止 profile 数量进一步爆炸，**新增 implementation profile MUST 满足**以下条件之一：

1. **Capability composition**：新 profile 仅是 "base profile + 一组明确 facet（通过 `requirement_blocks` 引用现有 capability、event_kind、schema、operation 集合）"，不引入未见过的能力。其 `inherits` 字段 MUST 指向已存在的 base profile，`adds` 字段 MUST 是 base 之外明确列出的最小 delta。这种 profile 无需独立 conformance vector，复用 base profile vectors + delta vectors。
2. **新能力闭环**：引入全新能力（例如新对象类型、新 projection family、新 transport binding），同时提交至少一个独立 conformance vector 与 fixture。

不满足两条之一的 profile 提案 MUST 被 reviewer 拒绝；现有 profile 不重组，但新 profile 必须按 composition 形态提出。`requirement_blocks` 已经支持声明引用，可形式化为 `compose: { base: <id>, adds: [<requirement_block_ref>...] }` 字段——该 reserved slot 已留出，但不强制现有 profile 迁移。

实现侧：客户端 SHOULD 在 conformance 声明中暴露 `inherits` 与 `adds` 信息，让对端能在 fast path 中按继承关系做能力命中判断，避免逐 profile 列举。

Profile 正文中的 prose MUST 项必须能映射到 `artifacts/profiles/conformance-profiles.json#profile_requirements` 的 `operation_requirements` / `required_event_kinds` / `required_schemas` / `required_fixtures` / `feature_discovery`，或在 `prose_requirement_coverage` 中列出对应 registry、fixture 或 conformance runner。没有一一字段的 prose MUST 不得悬空；新增 profile 时 reviewer MUST 拒绝缺少覆盖映射的 prose MUST 清单。

`feature_discovery.required[]` 的名字是 conformance runner 要检查的发现字段、行为断言或 UI/配置证据，不是
ServiceDescribe feature identity，也不得被生成器合并进 `supported_features`。profile 的运行时 feature 前置只由顶层
`required_features[]` 表达；其中每一项 MUST 是 `feature-registry.json` 登记的 exact `ak.feature.*.v1`。生成器不得把裸
assertion 名补前缀、映射为 feature，或为缺失项生成未登记 alias。

### 2.1.2 可裁剪构建与 profile 声明对账（normative）

§2.1 的"实现只声明自己实际支持的 profile"对可裁剪模块构建（Cargo feature、编译开关、插件拆分等形态的实现或 SDK）有一条显式推论：

- 以可裁剪模块构建的实现 / SDK MUST 保证其 profile 声明面（`ServiceDescribe.supported_profiles`、SDK 静态导出的 conformance 声明常量等）与**当前构建产物的实际编译能力**一致，而不是与全功能构建的能力一致。
- 构建期裁剪掉某 profile 的任一 MUST 能力（对应 `profile_requirements` 中 `operation_requirements` / `required_event_kinds` / `required_schemas` 的实现模块）时，该构建 MUST 同时摘除该 profile 的声明——通过构建期对账（feature gate 与声明常量联动）或等效守卫实现。裁剪构建（例如 `--no-default-features`）继续静态声明完整 required 面（如 `e2ee_client` 的 required 集合）即违反本条与 §2.1 的声明纪律。
- 对端按 §1 的能力交集原则信任声明面；声明面与编译能力脱钩会把 fail-closed 协商变成 fail-open，因此本条按声明纪律缺陷处理，而非文档瑕疵。

SDK 侧构建期守卫的具体实现形态（feature 矩阵测试、声明常量的 cfg 拼装等）属实现审查范畴，本文不规定唯一做法。

发布单一预编译构建时，顶层 `sdk_artifact.digest` 已唯一绑定该构建。发布源码包或同一 release 下存在多个可裁剪构建时，SDK conformance claim MUST 使用 `build_variants[]` 声明每个被认证变体的 `variant_id`、完整 `features[]`、完整 `configuration` 与实际导出的 `claimed_profiles[]`。features MUST 按 ASCII 严格递增，无启用 feature 时 MUST 显式为空数组；configuration MUST 展开影响行为的默认值，登记带工具命名空间的 target、toolchain、profile、默认 feature 策略和编译选项，键和值遵守 schema 预算且不得含密钥。无法给出完整构建输入时 MUST NOT 签发该变体 claim。整个 inventory 已由 claim proof 与 AK-SDK-015 的 `build_variant_inventory` digest 覆盖，MUST NOT 再携带平行的 `feature_set_digest`。验证器 MUST 核对 inventory 的 canonical digest、变体 id 唯一性、feature 排序和配置预算、已登记 profile；producer MUST 从实际构建输入生成 inventory，审计 MUST 将它与产物及构建日志核对。未列变体不在认证范围内。

## 2.2 场景化 Profile

以下 profile 用于把 v1 启动范围降到可实现的产品子集。它们不是 `minimal_client` 的替代品，而是面向具体产品形态的互操作声明。声明 `ak.profile.chat_mvp.v1` 或 `ak.profile.kanban_mvp.v1` 时，仅实现一个闭环的实现 SHOULD 在 `rejected_event_kinds` 中列出本实现拒绝的另一闭环 wire scope。

### `ak.profile.federation_minimal.v1`

适用于最小跨 Station 操作交换。

MUST 支持：

- service DID authentication
- federation transaction idempotency
- destination binding 校验
- signed Event Envelope 逐条验签与授权
- `accepted[]` / `rejected[]` / `quarantine[]` 分项结果
- dependency missing 的 pull / backfill 恢复
- duplicate conflict quarantine
- scalability constraints 中的 batch、event size 和 retry 规则

Coverage mapping：endpoint 能力由 `operation_requirements` 覆盖；signed Event Envelope、destination binding 与分项结果由 `required_schemas` + `independent-admission-fixture.json` 覆盖；dependency missing / duplicate conflict quarantine 由 `schema-validation-fixture.json` 与 `authority-commit-fixture.json` 覆盖；batch、event size 与 retry 规则由 `scalability-constraints.md` 和 `scalability-limits-fixture.json` 覆盖。

MAY 支持 gossip、snapshot-assisted bootstrap、MIMI facade、Applet bridge 和 full-text search。

### `ak.profile.signal_peer_relay.v1`

这是 Signal Extension 的可选对称 Station profile，只声明 encrypted Signal 的单跳 peer relay，不继承 durable Event federation：

- MUST 支持 `ak.self.signal.command.send.v1`、`ak.self.signal.stream.subscribe.v1` 与 `ak.peer.signal.command.relay.v1`；
- MUST 支持 `ak.schema.signal_envelope.v1`、`ak.schema.signal_relay.v1` 与 `signal-federation-fixture.json`；
- MUST 使用 federation peer HTTP Message Signature、current joined-member ActorId routing projection、producer device proof、signed `scope_ref`、`commit_ref`、三值 `signal_class`、TTL 与 MLS/AAD binding；
- MUST 原样转发 producer envelope，不重签、不改写、不解密重加密，不从 destination 再转发第三 peer；
- request-level 成功只返回 `{"accepted":true}`，不得暴露 recipient/binding/capability/count/per-item outcome；
- operation MUST 是 `idempotency_mechanism=none`、`retry_safe=false`、`uncertain_outcome.strategy=drop_unconfirmed`，不得携带 `Idempotency-Key`；
- Describe 只用 `supported_profiles` + `supported_operation_bundles` 广告；精确 payload kind/target 位于 ciphertext，MUST NOT 添加 `supported_kinds`。

不声明该 profile 的实现仍可独立支持本地 Signal 或 durable federation；它必须省略 peer relay operation 广告，而不是把远端成员能力逐人暴露。

## 3. 通用强制要求（所有 Profile 必须遵守）

以下要求不依赖具体角色，必须作为可互操作实现的基础：

- 事件名必须符合 `ak.` 命名规则，且标准 `ak.*` Event kind 必须在 `artifacts/registry/event-kind-registry.json` 注册；schema id 必须在 `artifacts/registry/schema-registry.json` 注册。
- Event Envelope MUST 先通过 `ak.schema.event.v1`，再按 `Event.kind` 通过 `ak.schema.event_payload.v1` 对应 payload class；active 标准 kind 未匹配 payload class 或 payload 校验失败时 MUST 返回 `schema_violation`，不得进入 reducer。
- 事件/关系/对象/View 的 `created_at`、`realm_id`、`proofs`、`scope_ref`、`actor_id`、`refs[role=authorized_by]` 在 reducer 与验证逻辑中不能被跳过。Event 不携带 `hlc`、`producer_revision`、`domain_refs` 或 `requirements`（封闭禁用集合见 [`../models/event-and-patch.md` §2.2](../models/event-and-patch.md)），因此 SDK MUST NOT 为它们保留读取或校验入口；每个 Event kind 绑定的封闭 typed reducer 由 `event-kind-registry.json` 唯一决定。
- `auth` 约束必须执行，不得通过客户端配置豁免。
- State / snapshot / projection 进度和 wait-for token MUST 以 `CommittedEventRef`、stream ref 与 RealmCommit position 为语义单位；`operation_id` 只可表示服务 canonical operation。
- Snapshot MUST 绑定 `governance_generation`、调用方获准的全部 `visible_stream_heads[]` 与 `retention_and_history_floor`，并由当前治理 Station 签名；接收方 MUST 按 [`realm-state-snapshot-schema.md` §4](./realm-state-snapshot-schema.md) 逐条验证，任一项失败时整份丢弃，MUST NOT 部分采用 rows。snapshot 本身不证明无遗漏，遗漏只能由逐 stream tail 的连续承接排除。
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

- 本地内容显示、解密与离线编辑所需的 reducer；不包含治理授权、RealmCommit 接纳或历史 root 重放
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
- MLS key-access revision binding：`governance_binding.key_access_revision` 的 GroupContext extension 验证 + 当前 winning MLS group-state projection
- minimal-metadata pseudonymous credential handling when profile is advertised
- AAD visibility policy handling
- epoch mismatch recovery
- encrypted payload envelope
- encrypted attachment envelope
- device revocation handling
- lost-device response
- local plaintext search for encrypted content

每个服务器 MUST 从 accepted state 计算并验证会改变当前 MLS epoch 密钥访问资格的闭合 checkpoint：membership、实际 MLS leaf 使用的 device/Agent runtime key、MLS group membership 与 `key_access_revision`。普通 capability、metadata、moderation、routing、contact/consent-only 变化不得令 digest stale；若它们同时产生 member/leaf remove，则只由该 remove 进入 checkpoint。E2EE Event 的普通 admission 授权判定与 MLS checkpoint 正交；服务端不得要求同一 RealmCommit 覆盖自身。

E2EE 客户端消费自己 Account Station 确认的 exact scope/group/epoch/key-access-revision 结果，核对本地 MLS leaves、待签 intent 与 GroupContext extension 的对应关系，执行 MLS Commit/Welcome 密码学处理；MUST NOT 收集治理闭包、验证历史 authority 或自行重建治理 checkpoint。没有所需服务器结果时，仅相关 scope 保持 pending。该服务器 policy profile 的 proof bundle 与完整 verify/materialize mutation/limit runner 属于服务器或独立审计角色，不是普通 full/e2ee 客户端的继承要求；SDK 是共享代码位置，不代表客户端角色。客户端 conformance 覆盖已确认结果消费、错账号/Realm/scope/group/epoch/basis 绑定、pending 与端到端篡改拒绝。

v1 不提供把 MLS 历史密钥 release 给第三方审计主体的 profile。`ak.audit.accessed` 只为已可见材料的特权读取留痕，不授予任何额外解密能力；对外材料 MUST NOT 把它宣传为密码学或硬件强制审计。

MUST NOT：

- 把明文消息发送给未授权 Station sync surface 或受托 search / projection 服务
- 把解密密钥上传给不受信服务
- 在自己 Station 尚未确认 KeyPackage 的 actor/device 授权，或客户端尚未验证 KeyPackage 自签与端到端身份绑定时加密给对方
- 在 MLS transcript/GroupContext 与自己 Station 确认的 exact governance binding 不匹配时继续解密正文

## 7. Station Events API

`ak.profile.station_events_api.v1` 适用于 Station 暴露的 Event 提交、读取、回填和 checkpoint 查询 API。

MUST 支持：

- submit Event
- idempotent write
- event fetch
- event resolve (batch dereference by ID / hash)
- cursor-based history
- actor / Realm stream-head query
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

## 8. Station

`ak.profile.station.v1` 适用于用户、组织或 agent principal 控制/委托的服务入口。

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

- multi-upstream Station federation
- quarantine queue
- witness receipt
- snapshot pointer distribution

Station MUST NOT 成为 Realm 状态的 canonical 真相源。
Station MUST NOT 将非 E2EE 的私有内容或可还原的派生明文转发给未列入相应 DID 委托或 Realm policy `plaintext_visible_services` 的服务。

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

## 9a. Account Authority capability

登录因子验证、短期会话授权与 session-grant 生命周期管理属于 `ak.profile.station.v1` 的 Account Authority capability。`coauth` 是可部署在 Station 认证 TCB 内的 reference component，但不声明公开 role profile、service kind、service registration 或 role-local Describe。

MUST 支持：

- `ak.gate.account.command.issue_session_grant.v1` / `/_arkret/gate/account/session-grants` 的规范化签发路径
- `ak.gate.account.command.refresh_session_grant.v1`、`ak.gate.account.command.revoke_session.v1` 与
  `ak.gate.account.command.introspect_session_grant.v1`
- 至少一种登录因子（password / passkey / OIDC / SSO / device pairing / recovery challenge）
- 短期、audience-bound `ak.session.grant` 签发
- session_grant TTL 上限远低于 Realm policy review horizon（minutes-to-hours，不得跨越多日）
- session_grant audience 绑定与拒签陌生 audience
- issuer ledger 是 issuance、active/revoked/superseded lifecycle、refresh/revoke/cascade/introspection 的唯一
  durable authority；ID/JWT `jti` 必须从 closed issuance preimage 重算
- durable exact replay、same-identity conflicting intent 零写入，以及 expired / revoked|superseded /
  indeterminate replay 的 terminal fail-closed 语义
- `auth_metadata.account_authority`、`auth_metadata.methods[]`、`auth_metadata.did_binding_methods`

SHOULD 支持：

- `ak.gate.account.command.issue_session_grant.v1` 规范化 HTTP binding
- 采用 account-first onboarding 时，完整实现 `ak.gate.account.exchange.create_handoff.v1` → `ak.gate.account.command.issue_identity_binding_challenge.v1` → `ak.gate.account.command.register.v1`；不得以私有 endpoint、普通 OAuth bearer 或进程内 challenge store 替代
- DID binding / claim attestation

部署内部认证组件 MUST NOT 声明任何 Arkret role profile，也不得发布独立 service DID、service registration 或 role-local Describe。DID document / key-log 能力只能由 Station 委托给已登记 resolver，并通过 `interop_surfaces[]` 以 `delegated_resolver` 形式声明。

Station 的 Account Authority capability MUST NOT 把成功的 OIDC / SSO / password 验证直接当作 DID 控制证明。Account-first inception binding 必须按 [`../identity/account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 验证由 entry 0 method-native control key 签发的 fresh proof；普通已发布 DID binding 与下游资源服务器仍 MUST 重新验证 DID control state（见 `guides/migrating-from-matrix.md`）。

部署内部认证组件只可用 issuer key 签自己的 JWT、introspection/status 与 issuer receipt。它 MUST NOT 持有或
请求 principal/root/device private key 或 governance-Station authority key，MUST NOT author SessionGrant genesis/lifecycle Event、查询
subject PCR authoring checkpoint 或依赖 grant Event/typed current result。客户端 DPoP
签 holder/request proof；真正的 principal Event 必须由当前获授权客户端 signer 签署，S2S transport proof
不能替代内层 Event proof。

`development_mode=true` 时，`verified_profiles[]` MUST 为 `[]`（见 `sync/service-surface.md` §3.0）；Conformance Verifier 在 verified-profile suite 通过后才能写入 verified entry。

Release readiness MUST 至少覆盖：签发路径拒绝陌生 audience；returning-human issue 同时验证 AccountHandoff DPoP 与 accepted-device proof 的 request/account/handoff/principal/device/audience/holder/session-intent/时窗绑定；accepted-device key 读取、验签与 current authorization 判定处于同一 linearization；human scope 与 TTL 为 issuer-fixed；issuer domain separation、canonical JWK、ID/JTI recomputation、exact replay/conflict/terminal outcomes；`soft_logged_out` 只能经完整重新认证后的 fresh AccountHandoff 或明确的账户控制动作恢复，而不是 refresh challenge；以及 development mode 下不得声明 verified profile。对应 conformance vector 为 `ak.vector.auth.session_grant_audience_binding.v1`、`ak.vector.session_grant.accepted_device_possession.v1` 与 `ak.vector.auth.session_grant_issuer_record.v1`。

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
| `ak.profile.push_gateway.v1` | `gateway` | 实现网关时必选；MUST `depends_on` `blind_wakeup` | `notify` 操作（注册/注销由 Account Station 提供，见 Push §3.3），`ak.schema.notification.v1`，service DID 校验，notify 响应对 `notification.devices[]` 逐项守恒的 `outcomes[]`（见 [`../discovery/push-notifications.md` §5.2](../discovery/push-notifications.md)），按 exact durable registration 回收失效 route。共享权威存储可直接满足；独立公共 Gateway 必须另声明 registration handoff bundle | `privacy-security-fixture.json` |
| `ak.profile.push_gateway.blind_wakeup.v1` | `gateway` | **默认互操作安全基线**：声明 `push_gateway.v1` 即 MUST 声明 | provider 出向 payload 仅含 `push_target_id`（pairwise pseudonym，按 [`crypto-media/device-lifecycle.md` §5.6](../crypto-media/device-lifecycle.md)）+ 封闭枚举的 `wakeup_kind` / `badge_count` / `unread_increment` / `l10n_key`；MUST NOT 携带 principal DID、sender DID / handle、Realm / Strand / Message id、event id、device verification-method DID URL、reaction 实际值、附件文件名、跨 Realm stable correlation key、IP / geolocation | `privacy-security-fixture.json` |
| `ak.profile.push_gateway.visible_notification.v1` | `gateway` | Opt-in；仅在 Realm policy 列入 `plaintext_visible_services` 且声明 `visible_notification` allowance、接收设备 opt-in、UI 显式标示时声明 | 维持 blind wakeup 之上扩展的最小可见字段集合；MUST NOT 携带正文、DID URL、跨 Realm stable correlation key、IP / geolocation 或未列入 profile 的自由文本；E2EE 默认实现不得依赖该 profile | `privacy-security-fixture.json` |
| `ak.profile.push_gateway.matrix_passthrough.v1` | `interop` | Opt-in；Matrix 互通桥接 | 按 Matrix push gateway 形态承载 passthrough payload；MUST 与 `blind_wakeup.v1` 流量分区，**MUST NOT** 在同一 `(recipient_id, device)` 元组上同时声明两者。**选择此 profile 即接受 Matrix-equivalent metadata 可见性**（典型字段如 `room_id` / `sender` / `event_id` 透传到 Matrix push gateway）。该 profile MUST NOT 与 minimal-metadata Realm 共享同一 `(recipient_id, device)` 元组。 | `privacy-security-fixture.json` |

Station Push 保持可选；声明 `ak.operation_bundle.station.push.v1` MUST 同时提供 `register_device` / `unregister_device`。同部署的 Gateway 单独声明 `push_gateway` 角色，不能把 Gateway profile 作为 Station 的同角色能力扩展。独立存储的公共 Gateway 只有同时声明 `ak.operation_bundle.push_gateway.http_notify.v1` 与 `ak.operation_bundle.push_gateway.registration_handoff.v1`，并满足 [Push §3.4](../discovery/push-notifications.md#34-受信公共-gateway-注册交接normative) 的 source-Station tenant isolation、immutable registration、terminal tombstone 与 signed durable receipt，才能被 Station 选择。

MUST 支持（在所有变体上）：

- `notify`（精确注册授权；不取得 Account self-service 权限）
- blind wakeup payload 最小化（默认基线）
- service DID 或等价受信服务签名校验
- 失效 token 回收
- 按输入设备逐项守恒的 `outcomes[]` 结果回传
- 对公共 Gateway handoff，按 authenticated source Station 隔离存储、日志、访问、worker、cache、备份与删除；禁止跨 Station provider-token equality index
- 对公共 Gateway handoff，exact replay 返回原 signed durable receipt，同 registration 异内容冲突，revoked 与被 successor 取代的前驱均不可复活

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

`ak.profile.traffic_metadata_hardened.v1` 是 service/deployment 级 hardening profile，用于把 federation fanout 时间、batch 大小、Welcome / GroupInfo 大小、push wakeup 和 retry cadence 的侧信道缓解变成可声明、可测试的 MUST 集合。声明该 profile 的服务 MUST 在 `ServiceDescribe.supported_profiles` 中暴露支持面，并对部署配置选中的适用 route 按 `artifacts/profiles/conformance-profiles.json#profile_requirements` 执行。v1 不定义 Realm 级 activation carrier；Realm `schema_refs`、policy bundle 与私有 active-profile 集合均不得声明本 profile。

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
- policy 与 moderation 检查默认 fail closed 或进入 quarantine
- sovereign deployment 下 External Collaboration Realm 默认 E2EE
- MLS Welcome 只发给已批准的外部设备
- 外部 Applet / Agent / transport allowlist
- 跨域事件审计
- grant / invite / membership 撤销
- 外部成员移除后 MLS epoch 轮换
- sender-constrained（proof-of-possession）会话出示：完整规则见 §15.1 与 `conformance-profiles.json#profile_requirements` 的 `additional_requirements.sender_constrained_session_pop_must`

MUST NOT：

- 向外部成员暴露内部 Realm 目录
- 将外部 Station 或 search / projection 服务视为权威
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

依据 [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700)（OAuth 2.0 Security BCP, BCP 240）"优先使用 sender-constrained token" 的指导，Arkret v1 production protected endpoint 的会话出示必须是 proof-of-possession（PoP）：`/_arkret/self/*` 使用 `ak.session.grant` + DPoP；高安全 profile 的所有受保护 `ak.self.*` operation 进一步使用会话 `session_public_key` 的 RFC 9421 HTTP Message Signature。裸 `Authorization: Bearer` 可作为 DPoP / PoP 绑定中的 grant 载体，但不能单独作为受保护 endpoint 的认证成功依据（见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md)）。

在高安全 deployment profile 下，所有受保护 `ak.self.*` operation 的 sender-constrained 出示必须使用 RFC 9421 HTTP Message Signature 形态并绑定 transcript/body。涉及的 profile 与其 `conformance-profiles.json#profile_requirements` 中的 `additional_requirements.sender_constrained_session_pop_must` 一一对应：

- `ak.profile.high_security_organization.v1`
- `ak.profile.sovereign_deployment.v1`（`ak.profile.sovereign_enclave.v1` 经 `inherits` 继承）
- `ak.profile.isolated_sovereign_network.v1`（经 `inherits` 同时继承上述两者，无需重复声明）

这些 profile 下，对所有受保护 `ak.self.*` operation，实现 MUST 要求 RFC 9421 PoP 出示：签名密钥为
`ak.session.grant` 委托的 `session_public_key`。本场景是
[`../sync/service-http-binding.md` §8](../sync/service-http-binding.md) 的
`ak.http_signature.scenario.client_session_pop.v1`，适用的必需覆盖项：

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.client_session_pop.v1 -->
- `@method`、`@target-uri`、`@authority`
- `arkret-operation`
- `content-digest`（条件项：带 body 时必需）
- `idempotency-key`（条件项：参与幂等 / replay key 时必需）
- `x-arkret-wait-for`（条件项：该 header 出现时必需）
<!-- END ak-http-signature-covered-set -->

`created` / `expires` 判据是 [`../sync/service-http-binding.md` §8.3](../sync/service-http-binding.md)
的共享窗口，本页不复制其数值；`encoding.md` §7.2 的 HLC 漂移阈值是另一场景的独立阈值，不得代入。
`ak.self.` 是机器可判定的默认保护面；新增或未知 operation 默认 fail closed。带 body 请求的 exact canonical HTTP content bytes、唯一 RFC 9530 `sha-256` token 与 raw-byte verification MUST 遵循 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md)。纯 `Authorization: Bearer`（无 DPoP / `Signature` / mTLS 绑定）对任何生产 current-v1 受保护 endpoint MUST 被拒绝；operation registry 明确允许匿名 public metadata projection 时，无有效 proof 只能返回该公开 projection，必须按未认证请求处理，不得授予 session / capability 语义。覆盖集的共同基线与其它签名场景见 [`../sync/service-http-binding.md` §8.1](../sync/service-http-binding.md)。

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

- 允许用户添加任意 Station / Directory / Blob endpoint
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

- Station、Events API、Station sync surface、Blob Store 可以同机合并
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
- sender-constrained（PoP）会话出示：完整适用面、签名绑定与裸 bearer 拒绝规则见 §15.1

`ak.profile.isolated_sovereign_network.v1` MUST cover：

- 私有 registry / witness
- closed federation default
- 导入导出审查
- 外部服务与 applet allowlist

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

### 18.1 Agent Provisioning

`ak.profile.agent_provisioning.v1` 注册 controller-面的 Agent management surface,扩展 `ak.profile.agent_runtime.v1`。

MUST 支持:
- `POST /_arkret/self/agents` (`ak.self.agent.command.provision.v1`) 使用闭合的两段 DID bootstrap。controller 先可恢复地保存 WebVH update key，签署并发布不含 PCR binding 的 entry 0；prepare 接收 caller-supplied `did`，验证其 accepted entry 0 与 managed-controller delegation，创建 private durable reservation 并返回 exact `initial_resolution`、controller PCR、delegation、scope digest 及 service-signed opaque `allocation_handle`，但**不**生成 Agent DID/私钥、分配 Agent PCR id 或发布 canonical Event/typed current result。controller 把该承诺写入本地冻结的 Agent PCR `ak.realm.create`，自算 `event_id` 并取 `principal_control_realm_id = retype(event_id)`，由唯一 controller-signed `ak.agent.provision` 前向声明。commit 只接受 byte-identical reserved bytes，并在一个 reducer transaction 原子派生四个分别闭合且最小的 provision/accountability/selector/realm-id-claim typed results；第二条声明同一 realm id 的 provision 必须拒绝。commit 返回 `awaiting_pcr_genesis`。genesis 必须另一次提交；两条 create admission 路径都必须把其 `initial_resolution` 与 provisioning durable 保存值逐字段比较，再反查 controller PCR 中声明了 `retype(create.event_id)` 的 accepted provision。genesis accepted 后只推进到 `awaiting_did_binding`，Agent、pairing 及 list/get 仍不可见。controller 随后以 entry 0 预承诺 key 签署连续 entry 1，加入 exact create-locked `ArkretPrincipalControlRealm.serviceEndpoint`；只有 entry 1 accepted 后才条件写 Agent active 状态、创建 pairing handle 并返回 `complete`。provision 不物化 Realm grant；Station 不得生成 Agent PCR MLS private state。放弃未提交 genesis 的 reservation 必须走显式 abandonment operation，不得靠过期或垃圾回收静默释放。
- `POST /_arkret/gate/account/agent-key-pair` (`ak.gate.account.command.pair_agent_key.v1`) 校验 current controller/Agent authority、pairing handle、requested-scope disclosure、proof-of-possession 与 accepted authority-committed current results，不得以 history-only backup 为前置。agent 已有 active key 时(runtime replacement re-pairing)必须提交不同 raw signing key，并以单一 controller-signed authorize Event 的精确 `supersedes[]` 原子替换全部既有 active authorization；同 key 续权不属于 replacement。
- Agent 通用 list/get projection 恰好暴露 lifecycle、readiness、presence 三轴；generic readiness 只含主体级 durable blockers，例如 `runtime_key_missing`、`pairing_open`，不得出现 `session_missing`、backup 状态、KP 库存、target Realm grant/membership 或 MLS blocker。`key_state` 只承载 key/handle/authorization，不得重复产品状态或备份状态。pairing poll 的 closed `runtime_state` 仅返回该 handle 的 pairing mode、expiry 和当前步骤所需 refs，不披露其它 Agent/handle/requested scope/grant/PCR history/session。SDK 必须区分 controller、pairing-handle runtime、authorized-key/no-session runtime、authenticated runtime 四种角色；authorized-key/no-session runtime 凭 active authorization 与 PoP 申请 session，不依赖 controller 在线或 generic list/get
- Pairing expiry 关闭并省略 open-handle fields、重算 readiness；尚未首次配对的 Agent 保持 `not_ready` + `runtime_key_missing`，replacement handle 过期则清除 `pairing_open` 且不改变既有 key/grant/lifecycle。上述两者均不得创建、撤销或改写 Realm grant
- `POST /_arkret/self/agents/{agent_id}/renew-pairing` (`ak.self.agent.command.renew_pairing.v1`) 对 bootstrap 状态重开 pairing，或对已持有 active authorized key 且 lifecycle 为 `active | paused` 的 agent 执行 new-key runtime replacement；`active` 无需先 pause，怀疑旧 key 失陷时 SHOULD 先 pause(见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))
- Agent management surface 中 list/get 是 read-only；renew-pairing 只轮换 profile-local pairing artifact，不写 durable Event；pause/resume/deactivate 各写一个 lifecycle Event，其中 deactivate 的 accepted terminal parent gate 直接使全部 child authority ineffective，不接受客户端 revoke bundle；grant attach/detach 分别写 Realm-scoped capability grant/revoke Event
- Longevity-safe 授权链:`ak.agent.key.authorize`、`ak.identity.accountability_grant` 与非 registry-required 的 agent capability grant 的 `expires_at` 均可缺省(revocation-governed);实现 MUST NOT 因缺省 `expires_at` 拒绝这些对象
- Agent provision request 与 list/get projection 使用必填固有字段 `slug`；Agent selector claim `ak.schema.agent_selector_claim.v1` 与 Actor Profile 投影 hint 使用外部引用字段 `agent_slug`，并支持 `@<controller-handle>/<agent_slug>` 输入别名到 agent `subject_account_id`（完整 AccountId）的唯一解析；slug 不是 handle、公开 Directory search/list key 或授权主体
- Draft-only family:`ak.agent.draft.propose` / `ak.agent.action_request` / `ak.agent.action_reject`,materialize 为 controller-owned `ak.agent.draft.v1` encrypted account-data
- Draft approval 状态机:`proposed → approved → published`；`ak.agent.action_approve` 在目标 Realm 安全确认中将 nonce 一次分配给完整 approved_event_id，私有 draft 从该确切结果派生状态
- Event Envelope `actor_id` / `executed_by` / `authorization_ref` attribution，以及从历史 provisioning / registration / accountability evidence 分别验证 accountable actor 与 executor
- Pause/Resume/Deactivate 语义(见 [`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md))
- `display_name`与`avatar_blob_ref`不得进入 provision Event或三个 projection；provision完成后只可用既有 `ak.profile.update` 独立 Event，固定 `actor_id=agent_id`、`executed_by=controller_account_id`与 accepted controller delegation。该独立 operation失败不得回滚 provision complete
- Controller deactivate / suspend 时,accountable Agents 的 active sessions revocation 链失效
- Sidecar exposure 披露：激活新 Agent 前 UI MUST 显式披露其在完成 access/MLS reconciliation 后将获得现有 Sidecar 未来内容访问权（联动 `ak.profile.agent_sidecar.v1`）

MUST NOT:
- 让 provisioning 接受旧的 accountability / selector 两 Event fan-out、为 `ak.self.agent.command.provision.v1` 另造同名 durable Event，或在唯一 `ak.agent.provision` Event 的原子 projection 外加入 Agent Profile、Agent key authorization、Realm capability grant；服务端也不得代签/合成 provision Event 或暴露部分 projection
- 在 `accountability_scope` 保留 singleton-array compatibility，或把 UI字段、未知 prepare字段透传进 canonical projection
- 返回长期 private key、refresh token 或可直接长期调用 Events API 的 bearer token
- 引入 custom URI scheme(`arkret://` 等)
- 把 `agent_slug` 当作 grant subject、actor attribution、membership key、delivery key、Directory search key 或 audit attribution source
- 让服务端生成/托管 Agent PCR MLS private state，跨 actor 读取 Agent backup，以 `single_point_of_failure` 绕过 Agent PCR recovery gate，或备份/克隆 Agent runtime private key

### 18.2 Agent Auth

`ak.profile.agent_auth.v1` 注册 agent runtime 的 authentication surface,与 `ak.profile.agent_provisioning.v1` 解耦。

MUST 支持:
- 复用 `POST /_arkret/gate/account/session-grants` 通过 `proof.proof_kind="agent_key_proof"` 分支
- 独立 schema branch、独立 proof validator、独立 returned scope(交集 from agent key authorization / capability grant / Realm policy / requested scope)
- `agent_scope_request` overlay 与签名 SessionGrant claims 内的 closed `scope_details`；HTTP outcome 不复制该授权材料
- key proof 绑定 `challenge` / `audience_id` / `request_canonical_digest` / agent principal（由 `principal_id` + `proof.verification_method` 一致性 enforced）/ `issued_at` / `expires_at`。Wire 不引入独立 `nonce`；challenge 是唯一随机请求标识。首次验证的 300 秒时窗、签名 transcript、冻结 body 与新鲜 HTTP DPoP 分离，遵循 key-management §3.6.1。相同 challenge 不得重复签发，但符合 §6.2 的 completed exact retry 必须返回原凭证；不同 intent 或 holder 的重放必须拒绝。
- Replay table 覆盖 proof `expires_at` 后的 grace window
- Session TTL 默认 ≤ 15 分钟,profile 可声明更长但 ≤ 60 分钟
- capability 只能由 accepted immutable provision `requested_scope.actions[]` 按 registry 的 exact-any `activation_operations` 选择；key/session、内容 action、runtime attestation、grant/participation 与产品 preset 都不得重新选择或取消。interactive 的 submit、scan、subscribe 任一出现即要求三层覆盖完整 `interactive_chat.mandatory_operations`；KeyPackage upload/consume/revoke 任一出现即要求三层覆盖 `e2ee.mandatory_operations` 的 KeyPackage upload。延迟/离线发布和在线 presence 分别叠加 registry 中对应 feature operation。内容读写能力继续由独立 `ak.event.read` / `ak.message.create` Realm grant 与 participation gate 强制。三层按 provision→key→session 的最高缺失层依次使用 `agent_provision_scope_migration_required`、`agent_key_scope_reauthorization_required`、`agent_session_scope_refresh_required`；server 不得自动补 operation，也不得由 re-pairing 或 session issuance 静默扩大上层 ceiling。
- 在线 Agent presence 必须遵守 [`profiles-presence.md` §3.3](../discovery/profiles-presence.md) 的短 TTL 刷新合同：30 秒 session ceiling 下 SHOULD 每 20–25 秒发送新的加密 `ak.presence`，持久化递增 sequence 与 MLS nonce，无法在 expiry 前安全提交时自然降级为 offline；进程 / stream keepalive 不构成 presence
- Structured human approval request 返回统一错误信封：`error.code=claim_required`，`error.details={reason_code: human_approval_required, approval_request_id}`；details 必须通过 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`，且不得向 agent runtime 展示 CAPTCHA / OTP。实现必须通过 `ak.vector.agent_auth.human_approval_required.v1`

MUST NOT:
- 把 `agent_key_proof` 降级走 password / OIDC / passkey validator fallback
- 在 session grant 中授予 MLS private state、secret storage 或长期 device 权限
- 把 controller 进入 `deactivated` / `suspended` 后的 agent session 视为有效

### 18.3 Agent Delegation Policy

`ak.profile.agent_delegation_policy.v1` 注册 capability vocabulary 与 act-on-behalf attribution 规则。

MUST 支持:
- Effective permission rule:`controller-approved grant AND controller's own delegable authority AND Realm policy AND resource selector / constraints AND agent key scope AND requested session scope AND current revocation / freshness state`,默认拒绝 wildcard
- Canonical constraint vocabulary:`allowed_tracks` / `allowed_strand_ids` / `allowed_data_labels` / `allowed_endpoints` / `rate_limit` / `approval_required` / `controller_approval_required` / `accountability_required`
- Reply-as-agent 与 act-on-behalf wire(`actor_id` / `executed_by` / `authorization_ref`)与双重署名渲染
- act-on-behalf 默认 fresh approval 粒度 `(action, target_strand)` + 短期 temporal window
- Realm policy 必须分别控制 Agent、Bot 与 Applet/Ghost provenance；不得把 Actor Profile `actor_kind` 当作授权来源，Bot 或 Ghost Actor 的 Profile 也不得使用 `actor_kind="agent"`

MUST NOT:
- 让 agent 自动继承 controller 在 Realm 内的最大权限
- 把 `act_on_behalf_allowed` 当作 constraint;它由 attribution + capability + approval 组合表达

### 18.4 Agent Sidecar

`ak.profile.agent_sidecar.v1` 注册独立 `ak.schema.agent_sidecar.v1` 对象、native Sidecar scope 与
controller-owned private AI workspace 行为。它依赖 Agent provisioning、auth 与 MLS profiles，
不继承 Circle conformance。

MUST 支持：

- `ak.sidecar.create` 唯一创世身份：`sidecar_id=retype(event_id,"sidecar")`；payload 只携
  不携完整对象或 reducer-derived 字段。
- `POST /_arkret/self/agent-sidecars:ensure` 的 closed prepare/commit/attach 三阶段；prepare 固定 exact Event
  drafts，new 分支返回 create + context attach，existing 分支只返回 attach；同 operation/key/exact bytes 幂等。
- singleton key `(realm_id,controller_account_id)` 原子保留；不同 genesis Event 争用同一 key 必须 fail closed。
- native `{kind:"sidecar",realm_id,sidecar_id}` scope 进入 Event digest、AAD、query/delivery 与 RealmCommit 验证。
- `ak.sidecar.context.attach` 只登记一个已存在的 source Strand/Relation context，不创建 Strand 或 Relation。
- read surface 返回只读 `desired_agent_ids` 与 `effective_agent_ids`；前者从 ownership、Agent lifecycle/
  runtime-key authorization 与 exact Realm member_state revisions 派生，不可由 operation 写入；后者是其中已完成当前 Sidecar
  MLS/KeyPackage reconciliation 的子集。action grant、participation selection 与 policy 独立约束写入、
  reply、mention、publish 等行为，不形成第二套 MLS roster。
- Sidecar MLS 直接绑定 `sidecar_id` 和 participant authority revisions，不依赖 Circle membership。不同
  `sidecar_id` 的 MLS group 与有效访问独立求值；一个 Realm/Sidecar 的 membership 或 MLS reconciliation
  MUST NOT 改变另一个 Realm/Sidecar 的 desired/effective 集合、投递或 future epoch key。
- Sidecar-private view 可寄宿普通 Strand shell，但不得改变 shared history、计数、未读、搜索、通知或权限。
- 显式 publish 由 controller 确认并创建一条新的普通 Event，不复制 private envelope 或 identifier。
- exchange projection 仅从 accepted native-Sidecar-scoped private history 确定性 fold。

MUST NOT：

- 接受或实现 `ak.sidecar.access.replace`、Sidecar member/invite/join/role/admin surface；
- 创建 backing Circle、Circle membership、private Strand 或 `agent_sidecar_of` Relation；
- 允许 caller 提供 participant/member/Agent selection；
- 将 source Strand 当作 Sidecar security scope，或向 shared surface泄漏 Sidecar private activity；
- 为同一 `(realm_id,controller_account_id)` 创建第二个 non-tombstoned Sidecar。

### 18.5 Agent Participation Policy

`ak.profile.agent_participation_policy.v1` 注册 Agent 的分层 participation ceiling 与 controller selection 面。它继承 `ak.profile.agent_provisioning.v1`。

MUST 支持:
- `ak.self.agent.participation.resource.replace.v1` 与 `ak.self.agent.participation.resource.get.v1`。selection 是 controller
  的私有偏好，唯一 authority 是 controller 所属 Account Authority；它不是 Realm 事实，也不经 peer relay。
  两个 operation 都只允许 controller 访问，并必须使用 bearer+DPoP。Agent runtime 不直接读写该私有状态；
  Account Authority 在签发 Agent session 时按需附带当前 selection/version 与同值的下一次 replace echo
- replace 的 closed body 固定为 `{target_scope,selection,expected_version}`。`target_scope` 是
  `realm{realm_id}|circle{realm_id,circle_id}|strand{realm_id,strand_id}` closed XOR；selection 是 required 五位
  `{reply_message,reaction_add,reaction_remove,accept_third_party_mention,act_on_behalf}`。首次写
  `expected_version=0`，每次成功严格加一；版本不匹配返回 `cas_conflict` 且零写入。GET 与 replace outcome 的每项
  固定为 `{target_scope,selection,version,next_replace_input:{expected_version}}`，其中
  `next_replace_input.expected_version=version`
- selection 本身不授予 capability，也不物化 `ak.capability.grant/revoke`。实际动作必须同时通过普通 Agent
  capability、Agent/controller lifecycle 与 `current_selection ∩ current_deployment_ceiling ∩ current Realm/Circle/
  Strand ceiling`。任一输入 unknown/stale 时 fail closed。Account Authority 可在 session grant 中签发当前
  selection/version 与同值的 `next_replace_input.expected_version`；target service 必须自行读取当前治理 ceiling，
  不得信任 session 中复制的 ceiling/effective
- 产品全局默认只可作为 SDK/UI authoring preference，不进入 admission、session 或服务 receipt。Agent
  pause/deactivate 继续是全局紧急停机；deployment ceiling 是 target 本地运行时安全门，只能进一步拒绝动作，
  不进入 controller selection wire、Realm reducer 或跨服务共识
- Realm/Circle/Strand policy ceiling 复用同一 required 五位 shape，子级只能逐位收紧父级。不得保留缺省继承、
  三位 shape、bit 重命名或把 `reply_message` 隐式扩展为 reaction 权限
- 第三方 mention gate：`accept_third_party_mention=false` 时不得向该 agent 派生 mention notification、inbox row、push wakeup 或 agent subscribe 投影；gate 在 message event fanout 时一次性求值，participation 之后翻转不追溯补发或撤销既有派生（[strand-and-message.md §9.4.5](../models/strand-and-message.md)）
- `reply_message`只映射`ak.message.create`，reaction add/remove分别映射`ak.reaction.add/remove`。
  reply-as-Agent固定`actor_id=agent_id`；act-on-behalf固定`actor_id=controller_account_id,executed_by=agent_id`并携匹配
  controller approval/accountability authorization ref，二者不可混用

MUST NOT:
- 允许 Strand / Circle ceiling 放宽父级 ceiling
- 把 controller-private selection 当作 capability、Realm Event 或跨服务事务参与者
- 在 effective ceiling unknown 或 stale 时默认允许 agent participation

## 19. Applet Service Family

Applet v1 家族适用于运行 Applet 集成服务。`ak.profile.applet_service.v1` 是 base bot-only profile；桥接外部系统、Ghost Actor、portal Realm、delegated acting、E2EE join 和 widget 能力必须通过继承 profile 显式声明。

`ak.profile.applet_service.v1` MUST 支持：

- signed `applet_registration`
- namespace declaration and matching
- ping / describe endpoint
- transaction push endpoint
- transaction idempotency
- transaction push per-delivery authentication record（`delivery_authentication_record`）
- idempotency / replay binding across `Source-Service-ID`、`Destination-Service-ID`、`Idempotency-Key`、canonical body digest and source verification method
- capability enforcement
- HTTP message signature verification（RFC 9421；覆盖集的唯一合同是 `ak.http_signature.scenario.applet_transaction.v1`，正文见 [`../extensions/applet-integration.md` §7.3.1](../extensions/applet-integration.md)）
- event signature verification
- bot actor attribution
- `ak.edge.applet.command.transaction.v1` as operation_id only, never as durable Event kind
- fail-closed reasons for transaction push: `http_signature_required`、`http_signature_invalid`、`signature_window_invalid`、`duplicate_conflict`、`applet_registration_unauthorized`、`applet_namespace_mismatch`

MUST NOT：

- 把 namespace 命中当作写权限
- 静默 impersonate native user
- 在无授权时接收全网 sync stream
- 只凭裸 `Idempotency-Key`、body 内 `source_id` 或首次握手状态接受 transaction push replay
- 在未提示边界的情况下把 E2EE 内容桥接到非 E2EE 网络

`ak.profile.applet_bridge.v1` inherits `ak.profile.applet_service.v1` and MUST 支持：

- resolve actor endpoint
- resolve realm endpoint
- protocol metadata endpoint
- Ghost Actor accountability metadata
- portal Realm metadata
- external event deduplication
- bridge error event
- 执行 `non_event_grant_authority_rules[]`：只有 active `ak.realm.admin` issuer 向同 scope
  已 accepted bridge registration 的 service、按 exact `applet_authority`
  applet/service/epoch binding 签发其已请求的 `ak.applet.ghost.provision` 时允许；owner
  shortcut、缺 profile、错 epoch/subject/scope/constraint 与其它 non-event action 必须
  `grant_exceeds_issuer_authority`

`ak.profile.applet_delegated.v1` inherits `ak.profile.applet_service.v1` and MUST 支持 delegated native-user acting 的 `executed_by` / `authorization_ref` / `applet_id` 校验、dual-signature attribution 与 `registration_epoch` evidence verification。

`ak.profile.applet_e2ee_join.v1` inherits `ak.profile.applet_service.v1` and MUST 支持独立 E2EE join authorization、MLS roster applet-managed 标注，并在缺少授权时 fail closed with `applet_e2ee_join_unauthorized`。

`ak.profile.applet_widget.v1` inherits `ak.profile.applet_service.v1` and MUST 支持 widget origin isolation、CSP、scoped token、consent 与 host session/device-key non-disclosure。

Applet bridge SHOULD 支持：

- third-party user / location lookup
- admin revoke / pause
- per-Realm bridge policy
- Applet health and lag metrics

## 19a. Franking (E2EE Abuse Reporting)

`ak.profile.franking.v1` 适用于在 E2EE Realm 中提供可验证投递证明的服务（典型为 Station sync surface / MIMI provider facade / Station）。

参考：`governance/content-moderation.md` §3.4 与 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) franking 段落。

MUST 支持：

- 在接收 E2EE Event Envelope 时签发七字段 `ak.moderation.franking_proof` 事件，绑定 `realm_id`、目标 `event_id`、`received_by`、`verification_method`、`received_at`、`replay_nonce` 与 `signature`；不得携带派生 digest、sender claim、proof id 或 payload `kind`。
- franking proof `signature` 由 service DID 在 `received_at` 有效的 verification method 签发，覆盖 `ak.franking_proof.signature.v1` 唯一 canonical transcript。
- 每条 franking proof 必须可被独立 verify：重算目标 Event 内容承诺，验证 proof Event 的 producer proof、authority refs 与历史 service/Realm binding。若声明期限内存在，还必须取得 byte-identical durable proof Event、确认安全 RealmCommit 的确切 `existence_anchor` 与完整 checkpoint 祖先；普通 Event 不进入 RealmCommit.delta，且普通发送与验证不得等待该可选证据。仅本地命中不能替代所声明的存在证明。
- 接收 reporter 提交的 `ak.self.moderation.command.report.v1` 时，把 exact durable franking proof Event 与 report Event 绑定为审计链一部分；不得仅信 reporter 单方声称。
- franking proof cache TTL 与 service key rotation 同步：service DID 的 verification method 撤销后，旧 franking proof 仍可历史验证（用历史 key state），但不签发新 franking proof。

MUST NOT：

- 在 franking proof 中包含明文正文、附件文件名、reply 摘录、mention 列表、私有 handle 或解密内容 hash，除非 Realm policy 显式允许该字段。
- 用 franking proof 单独证明明文含义——franking proof 只证明"该密文事件被该 service 在该时间收到"。
- 跨 Realm 复用同一 franking proof（`replay_nonce` 与 `realm_id` 必须进 franking proof 签名）。
- 在没有有效 service DID 绑定的情况下签发 franking proof。

SHOULD 支持：

- franking proof batch endpoint（一次 fetch 多条 franking proof）以减少 audit traffic。
- franking proof inclusion proof：franking proof 可被签入定期 franking-proof log Merkle tree，向举报者证明"该 franking proof 不是后补的"。该 inclusion proof 与 Realm authority stream 独立，因为 franking proof 不进入 Realm authority commit checkpoint（franking proof 是 service-side audit material，不改变协作状态）。
- 显式 `franking_proof_unavailable` 错误码，让 reporter 客户端知道 service 当前不签发 franking proof（如 service downgrade / outage），而不是误以为消息根本未投递。

## 19b. Realtime Media Services

`ak.profile.webrtc_media.v1` 适用于提供 ICE config / TURN / SFU 等 RTC 基础设施的服务。

参考：[`crypto-media/webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)（ICE config / TURN）、[`crypto-media/media-service-binding.md`](../crypto-media/media-service-binding.md)（SFU / 媒体服务绑定）与 [`crypto-media/call-state.md`](../crypto-media/call-state.md)（通话状态）。

MUST 支持：

- ICE config endpoint，返回包含 `ttl_seconds`、`refresh_lead_seconds`、`ice_servers[]`（含 STUN / TURN）、签名的响应。
- per-call pairwise pseudonym 作 TURN `username` 身份段；不得使用 principal DID / handle / 跨呼叫稳定 ID。
- TURN credential REST-style ephemeral 形态（`username = <expiry-unix>:<pseudonym>`，`password = HMAC-SHA256(turn_shared_secret, username)`）。
- TURN shared secret 周期轮换（默认 ≤ 24 小时）；轮换时同时接受新旧 secret，grace ≥ `ttl_seconds`，避免 in-call 集体失败。
- in-call credential refresh：客户端在剩余有效期 ≤ `ttl_seconds * 0.25` 时调用 refresh；server 必须在不中断现有 allocation 的前提下下发新 credential。
- `turn_credential_expired` / `441 Wrong Credentials` / `438 Stale Nonce` 等错误的 `next_retry_at` 响应。
- 高隐私 Realm 的 `turn_required=true` mode（禁止 host/srflx candidate 泄露 IP）。
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
- reducer convergence tests（含 authority-commit projection 向量）
- authority-commit projection vectors（见 `conformance-vectors.md`）
- Event Envelope negative vectors（见 `artifacts/fixtures/sdk-precheck-fixture.json`）
- redaction vectors（见 `conformance-vectors.md`）
- capability vectors（见 `conformance-vectors.md`）
- sync fixture、state-resolution fixture、capability fixture 和 privacy/security fixture（见 `artifacts/fixtures/*.json`）
- authorization tests
- privacy regression tests
- error response tests
- downgrade / unsupported feature tests
- unknown-field rejection / extension-slot preservation tests

所有 profile MUST 能按 `../models/common-fields.md` 与各对象专属文件（`realm-and-space.md` / `strand-and-message.md` / `morph.md` / `relation.md` / `event-and-patch.md` 等）解码和验证其声明支持的核心对象字段。实现 MUST 拒绝 canonical object schema 未声明的未知字段，对 schema 显式声明扩展位（已登记的 `payload.x_*` 槽、`requirements.critical_extensions[].parameters`）中的未识别内容 MUST 保留，并覆盖“schema 未声明字段被拒绝”与“扩展位内容在 hash/signature 校验、存储、联邦转发、backfill 后仍存在”的测试；未知 critical feature MUST fail closed。实现 MUST reject 类型错误、必填字段缺失、非法 enum、非法 ID/hash/timestamp/cursor pattern，以及违反条件必填规则的对象。标准 Event 必须加载 `event-kind-registry.json` 与 `event-payload.schema.json`，确认每个 active durable kind 都有可执行 payload 校验路径。

所有 profile MUST 按 `conformance-vectors.md` 覆盖 canonical JSON、hash、signature binding、Ed25519 detached JWS fixture、HLC 和 cursor 的基础向量。Events API、Full Client 与 E2EE Client MUST 额外覆盖 event digest；Events API 节点 SHOULD 覆盖 event-batch receipt digest；E2EE Client 和 Station MUST 覆盖 encrypted envelope digest。

E2EE profile MUST 额外提供：

- KeyPackage verification vector
- KeyPackage claim single-use vector
- MLS Governance Binding root mismatch vector（`governance_binding` 任一 root 不匹配对应 confirmed RealmCommit state）
- minimal-metadata identity link vector
- AAD visibility vector
- MLS epoch transition vector
- encrypted payload vector
- removed member cannot decrypt vector
- E2EE franking report vector

Client Sync 相关 profile MUST/SHOULD 按 `conformance-vectors.md` 执行对应向量：

- Minimal Client MUST 覆盖基础排序、tie break、pagination gap、backfill order 和 token expiry recovery。
- Chat MVP Client（`ak.profile.chat_mvp.v1`）MUST 覆盖 Strand discussion timeline、message edit/redaction、reaction authority-ordered keyed set、discussion history visibility 和 membership 裁剪。
- Kanban MVP Client（`ak.profile.kanban_mvp.v1`）MUST 覆盖 Board projection、Strand move/reorder、position edge conflict、CAS stale reorder 和 wait-for query。
- Full Client MUST 额外覆盖 snapshot checkpoint、state_after 与 decryption_pending 的 UI / cache 恢复行为。
- E2EE Client MUST 覆盖 MLS epoch backfill、decryption_pending recovery 和 removed member fail closed。
- Station SHOULD 覆盖 duplicate suppression、backfill order、encrypted payload forwarding 和不能转发解密材料。
- Snapshot bootstrap MUST 覆盖 [`realm-state-snapshot-schema.md` §4](./realm-state-snapshot-schema.md) 的五项接收方验证：治理 Station 的 authority bundle 与 `governance_generation` 绑定、snapshot ID 与 canonical body 匹配、Station proof 的 domain separation、每个可见 head 由同 stream tail 连续承接、tail 中每个 Commit 的 producer / authority proof 与 typed reducer 有效；并 MUST 覆盖 `retention_and_history_floor` 的下界语义与整份丢弃行为。

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
- `ak.self.moderation.command.report.v1` payload schema validation
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

Feature discovery MUST 使用
[`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)
的 closed `ServiceDescribe` DTO。完整且可校验的响应示例见
[`service-surface.md` §3](../sync/service-surface.md)；profile 通过
`supported_profiles` / `verified_profiles` 表达，reducer 与 schema
版本不得伪装成独立的顶层 profile 字段。

## 22. 基线 Profile

首个互操作目标 SHOULD 是：

- `minimal_client`
- `chat_mvp`
- `kanban_mvp`
- `station_events_api`
- `station`
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

**证据映射（normative）**：`sdk_conformance_contract` 中 `required_evidence` 含 `vector_result` 的条款 MUST 携带 `vector_evidence`，其余条款 MUST NOT 携带。`vector_evidence.vectors` 点名承载该条款的已登记向量；以 `.*` 结尾的条目只是书写便利，MUST 在当前 spec revision 的 `vector-registry.json` 下展开为非空且不含失活成员的集合。`vector_evidence.decision_points` 逐条登记该义务中可分别观测的判定点，每个判定点 MUST 有条款内唯一的 `id`、一句 `requirement`，以及至少一个取自展开后集合的精确 vector id。门禁只证明这层映射可解析；它不读 `requirement` 的自然语言，也不证明任一向量的语义足以覆盖该判定点——因此判定点在登记或变更时 MUST 经复核，且 MUST NOT 为迁就某份 fixture 现有的 case 把判定点写窄。SDK claim 中 `kind=vector_result` 的证据 MUST 携带 `covers_vectors`，其并集 MUST 是该条款展开后向量集合的子集，并 MUST 覆盖其每个判定点点名的向量；结果 MUST 与 claim 同一 `spec_revision` 并携带不可变摘要。本映射只服务于 SDK claim 的证据记账，MUST NOT 被当作部署 profile 的适用性 selector，也不改变 `evidence_coverage_semantics` 的 acceptable-set 语义。

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
| <a id="ak-sdk-001"></a>1 | Event Envelope MUST 先过 `ak.schema.event.v1` 与 payload class 校验，失败 MUST `schema_violation`，不得进入 reducer（先验证后消费） | 本文 §3 | **V**（`ak.vector.sdk.envelope_precheck_rejects_before_consumption.v1`，观测点是被消费效果的缺席）；"先于消费"的内部顺序为 U |
| <a id="ak-sdk-002"></a>2 | `proofs`、`scope_ref`、`actor_id`、`refs[role=authorized_by]` 在 reducer 与验证逻辑中不能被跳过；`hlc` / `producer_revision` / `domain_refs` / `requirements` 出现在 Event 顶层时 MUST `schema_violation` | 本文 §3 | **V**（`ak.vector.sdk.envelope_forbidden_top_level_fields.v1`）；"库不得暴露跳过入口"为 A |
| <a id="ak-sdk-003"></a>3 | `auth` 约束必须执行，不得通过客户端配置豁免 | 本文 §3 | **U**（配置面审计）；辅以 A（不提供豁免配置项） |
| <a id="ak-sdk-004"></a>4 | 对 `causal` 关系、`revoked` 与 `proof` 失效状态 MUST fail-closed，不得静默接受 | 本文 §3；conformance-vectors §3.4 | **V**（`ak.vector.authority_commit_projection.*` 并发撤销 fail closed 向量） |
| <a id="ak-sdk-005"></a>5 | cursor MUST 当作不透明字符串保存回传；SDK / 应用层 MUST NOT 解析内部字段构造请求 | encoding §8；vector-registry.json（`ak.vector.encoding.cursor_opaque.core.v1`） | **A**（不暴露结构化解码 API）；黑盒仅能以变异 handle cursor 抽样旁证 |
| <a id="ak-sdk-006"></a>6 | canonicalization 失败（duplicate key、malformed UTF-8、隐式 NFC 归一）MUST reject，不得"修复"后继续 hash / 验签 | encoding §2 | **V**（encoding 负例向量） |
| <a id="ak-sdk-007"></a>7 | malformed HLC MUST reject，不得截断、补零或大小写折叠后接受 | encoding §7.1 | **V** |
| <a id="ak-sdk-008"></a>8 | 重试 / 等待期间 `refs[role=authorized_by]` 与领域 `expected_revision` 约束 MUST NOT 放松 | api-conventions §6.2 | **V**（重放向量）；内部重试路径为 U |
| <a id="ak-sdk-009"></a>9 | E2EE：`governance_binding` root 不匹配 MUST NOT 继续解密正文；未验证 KeyPackage 所属 DID 不得加密 | 本文 §6；conformance-vectors §2.5.7 | **V**（root mismatch 拒收向量）；"不解密"的本地行为为 U，KeyPackage DID 验证入口为 A |
| <a id="ak-sdk-010"></a>10 | E2EE：MUST NOT 把明文 / 解密密钥交给未授权 Sync / search / projection 服务 | 本文 §6、§8 | **V**（privacy regression 出向流量观测）为主；本地泄露面为 U |
| <a id="ak-sdk-011"></a>11 | 轻客户端 MUST NOT 以单条 Event 的本地投影结论替代 `RealmCommit` 接纳，也 MUST NOT 让同批次较早 Event 的投影成为后续 Event 的授权依据，MUST hold pending 或 fail closed | conformance-vectors §3.4 | **V**（以 SDK API 输出为观测点） |
| <a id="ak-sdk-012"></a>12 | late key recovery：`T0` 不可见 / key source unauthorized 时 MUST 拒绝解密（先验证后消费） | conformance-vectors §3.6、§3.15 | **V**（`ak.vector.history_access.since_join_prejoin_denied.v1`、`ak.vector.media_binding.e2ee_key_source.v1`） |
| <a id="ak-sdk-013"></a>13 | 未知 critical feature / `requirements` 不匹配 MUST fail closed；未声明 critical 的未知扩展仍 MUST 接纳并逐字节保留 | 本文 §3、§20 | **V**（`ak.vector.sdk.unknown_critical_feature_fail_closed.v1`、`ak.vector.sdk.requirements_mismatch_fail_closed.v1`） |
| <a id="ak-sdk-014"></a>14 | 正式的验证、授权与信任准入路径 MUST 拒绝 `test-material-registry.json` 登记的公开测试签名材料与保留测试标识，签名验证通过不构成准入 | identity/did-usage-and-verification §8 | **V**（`ak.vector.identity.test_signing_material_rejected.v1`、`ak.vector.identity.reserved_test_identifier_rejected.v1`） |
| <a id="ak-sdk-015"></a>15 | 裁剪构建若移除任一已声明 profile 的 MUST 能力，MUST 同时移除该 profile claim；构建产物的 capability inventory 与 claim 必须对账 | 本文 §2.1.2 | **U**（构建配置审计）；辅以 A（公开 API / capability inventory） |
| <a id="ak-sdk-016"></a>16 | 开放注册集中的未知值 MUST 在反序列化时原样保留，不得因本地 registry 快照较旧而使整个对象解码失败 | schema-registry §6.1 | **V**（`ak.vector.encoding.open_registry_unknown_roundtrip.v1`）；辅以 A（非封闭 enum API 形状） |
| <a id="ak-sdk-017"></a>17 | schema 明示的 `x_*` 与 `critical_extensions[].parameters` 未识别内容 MUST 在 decode/encode、存储、联邦转发与 backfill 后逐字节保留，且继续进入 canonical bytes | 本文 §20；schema-registry §6 | **V**（`ak.vector.encoding.extension_slot_roundtrip.v1`）；内部存储/转发路径为 U |
| <a id="ak-sdk-018"></a>18 | `ack_token` MUST 作为不透明字符串原样回传，SDK MUST NOT 解析其内部结构 | client-sync §10.1 | **A**（不暴露结构化解码 API） |
| <a id="ak-sdk-019"></a>19 | `retry_safe=false` 的 operation MUST NOT 自动全量重试；请求内容改变时 MUST 换 request key | api-conventions §6.2 | **A/U**（重试 API 与配置审计） |
| <a id="ak-sdk-020"></a>20 | 客户端 MUST 以 `max(server_hint_delay, jitter(local_backoff_delay))` 组合 `Retry-After` 与本地退避；0/已过期提示不得加速本地梯子，长提示不得按本地上限截断，且不存在忽略服务端提示的配置开关 | api-conventions §9 | **V/U**（注入时钟、配置审计与出向请求观测） |
| <a id="ak-sdk-021"></a>21 | 客户端 MUST 仅按 `has_more` 决定是否继续分页 | api-conventions §7.1 | **V/A**（分页响应向量与 paginator API） |
| <a id="ak-sdk-022"></a>22 | SDK MUST 暴露 canonical confusable check 为可调用 utility | encoding §2.2 | **V/A**（confusable test set 与 public API inventory） |
| <a id="ak-sdk-023"></a>23 | SDK MUST 以 closed types 区分 producer `Event`、authority `RealmCommit` 与 `PlainPayload<T>` / `MlsEncryptedPayload<T>` / 具体 MLS 协议 payload；非法组合必须在网络前 compile-fail/type-error，verified submission 不得再原地修改 | conformance-vectors §3.14 | **V/A**（`ak.vector.sdk.event_type_axes.v1`、compile-fail suite 与 public API inventory） |
| <a id="ak-sdk-024"></a>24 | SDK MUST 在构造 typed describe/ping、写入路由缓存、执行 capability 交集或发起业务请求前消费 bootstrap `protocol_version`；形状合法但不等于 `"1.0"` 时 MUST 返回 `unsupported_protocol_version`，缺失、非字符串或非 canonical 字面时 MUST 返回 `schema_violation` | current-contract §3；service-surface §17 | **V/A**（`ak.vector.service.protocol_version_bootstrap.v1` 与 public API inventory；不得暴露跳过 bootstrap 判别直接构造已验证 service 的入口） |

### 23.3 "仅 API 形状可保证"类的 SDK 实现指引

针对上表 A 级（含 A 补充级）条款，SDK：

- SHOULD NOT 在客户端可达的公开 API 面提供 cursor 结构化解码（base64url 解码 + 内部字段访问）helper；cursor SHOULD 以不透明 newtype / opaque string 类型建模（对应条款 5）。
- SHOULD NOT 提供跳过 proof / schema 验证的公开入口（`verify=false` 参数、insecure 构造器、直接产出"已验证"类型的裸构造函数等）；测试性 bypass 若确需存在，SHOULD 置于非默认 feature / 内部模块，不得从默认公开面可达（对应条款 1、2、9）。
- SHOULD 采用"验证即构造"（parse, don't validate）类型形态：未通过 envelope schema + proof 验证的字节不产出可直接消费的 Event 值类型（对应条款 1、2）。
- SHOULD 把 fail-closed 判定（causal / revoked / proof 失效、未知 critical feature）实现为默认路径；任何放宽行为 SHOULD 是显式、可审计的 opt-in，而非默认参数（对应条款 3、4、13）。
- SHOULD 将开放注册集建模为可保留未知字符串的 non-exhaustive 类型，并为 schema 明示扩展位保留 raw canonical value；不得用封闭 enum 或丢弃未知字段的通用反序列化默认破坏条款 16、17。
- SHOULD 将 cursor 与 `ack_token` 都建模为 opaque newtype，并让 paginator 只消费 `has_more`；自动重试器必须显式消费 operation 的 `retry_safe` 与服务端 `Retry-After`（对应条款 18–21）。条款 21 的 `has_more` 合同只覆盖列表分页：`ak.self.events.read.scan.v1` / `ak.peer.events.read.scan.v1` 既无 cursor 也无 `has_more`，续页由调用方从本批的 `stream_position` 自行推进（[api-conventions §7.2](../sync/api-conventions.md)），SDK 不得把列表 paginator 套到该面上。
- SHOULD 提供不依赖 UI 的 confusable-check public utility，并以 canonical test set 固定输出（对应条款 22）。
- MUST 让 outer shape 与 payload shape 的非法组合无法通过公开构造器产生；raw wire Event 只能进入解析/草稿态，必须显式转换成 immutable verified submission 后才可交给 publication evidence 或 submit API（对应条款 23）。
- SHOULD 让 describe/ping 的公开消费 API 从 raw JSON bootstrap 判别开始，并只在版本精确匹配后产出 typed service 值；不得提供跳过该判别而直接写入已验证路由缓存的公开入口（对应条款 24）。

声明遵循本节的 SDK MUST 发布符合 [`sdk-conformance-claim.schema.json`](../../artifacts/schemas/sdk-conformance-claim.schema.json)（`ak.schema.sdk_conformance_claim.v1`）的 machine-readable claim；`ak.vector.sdk_conformance.claim_validation.v1` 与 `sdk-conformance-claim-fixture.json` 是其可执行证据。SDK 为每个适用 `AK-SDK-NNN` clause 提供一个 `clause_claims[]` 条目，至少给出 `result` 与不可变 `evidence[]` 引用；每条 evidence 都 MUST 携带非零 content digest。V 级证据引用向量结果，A级引用 public API inventory，U 级引用代码 / 配置 / 数据流审计；`not_applicable` 必须携带机器可读理由。SDK release 必须以 `sdk_artifact.uri + sdk_artifact.digest` 绑定确切发布物，同时钉定非零 `spec_revision` 与 `sdk_conformance_contract` 的 canonical digest，防止用新条款解释旧证据或把一份结果移植到另一产物。claim 必须声明 `issued_at`、issuer DID 与 verification method；`proof.signature` 覆盖 UTF-8 `"arkret-sdk-conformance-claim-v1\n"` 加移除顶层 `proof` 后对象的 RFC 8785 JCS bytes，`proof.kid` 必须等于 `issuer.verification_method`。验证器除执行 JSON Schema 外，MUST 验证发布物、证据与 contract digest，解析 spec revision，验证 issuer 当前授权及签名，并执行 clause ID 唯一性与已知 clause 集合检查；任一步失败都不得接受 conformance 声明，重复 clause MUST `duplicate_clause_claim`。验证器还 MUST 按 `sdk_conformance_contract.evidence_coverage_semantics`（`acceptable_set`）强制证据类型覆盖：对每个 `result=pass` / `result=fail` 的 clause claim，MUST 存在至少一条 evidence，且每条 `evidence[].kind` MUST 属于该 clause 在 contract 中登记的 `required_evidence` 集合；仅由该集合外类型佐证的 pass / fail clause MUST 被拒绝。该检查独立于且叠加于上面的 digest / 签名检查，`required_evidence` 采用可接受集合语义（列出可接受的证据类型，而非要求全部类型齐备）。

### 23.4 与机读面的关系

V 级条款的可执行输入仍是 `vector-registry.json` 与 `artifacts/fixtures/*.json`；A / U 级条款的证据仍分别来自 API 面审查和审计。三类结果统一由 `conformance-profiles.json#sdk_conformance_contract` 声明，且与部署 `profile_requirements` 分离。验证器 MUST 拒绝未知 clause ID、重复 clause、缺证据 digest、缺 artifact binding、零值或不匹配的 spec / contract digest、无效或未授权签名、使用表格行号作为 ID，或 claim 钉定的 contract digest 与本地 canonical artifact 不一致的声明。
