# Changelog

本文件记录 Contrix 协议规范在主要发布之间的变化。

格式参考 [Keep a Changelog](https://keepachangelog.com/) 与
[Semantic Versioning](https://semver.org/)。

本仓库尚未发布任何版本。下方条目描述的是 `v1-core-rc` 候选基线的当前内容，
而不是相对任何先前公开版本的差异。

## [Unreleased] — `v1-core-rc`

### 协议评审驱动的简化（2026-05-05，第四批：constraint 14→8 collapse + encoding 合并 + federation dedup）

#### Round 9 — Constraint 类型 14 → 8 family + subtype discriminator

- `grant-constraint.schema.json` `constraint_type` enum 从 15 收敛为 8（`temporal`, `field_access`,
  `type_restriction`, `scope_limitation`, `delegation_control`, `quota`, `claim_based`,
  `confidentiality`），新增 `subtype` 字段保留原 14 类型的子语义。
- 新增 `applies_to_actions[]` 让 `temporal` 吸收 v0 的 `edit_window` / `redact_window`。
- `constraint-schema.md` §2.2 表从 14 行 + 2 例外行重构为 8 family + subtype 表；§2.3 evaluation_class
  表从 19 行简化为 17 行（按 `(family, subtype)` 索引）；新增 v0→v1 family 命名映射 table 用于翻译既有
  grant；§6.3、§8、§9、§10、§11、§12、§13、§14 章节标题更新以反映 family/subtype 归属。
- 16 处 JSON 示例迁移到新形态：`approval_workflow` → `claim_based{subtype=approval}`；
  `accountability` → `claim_based{subtype=accountability}`；`encryption_requirement` →
  `confidentiality{subtype=encryption}`；`visibility_control` → `confidentiality{subtype=visibility}`；
  `container_move` → `scope_limitation`；`rate_limiting` → `quota{subtype=rate}`；`resource_limit` →
  `quota{subtype=resource}`；`edit_window` → `temporal{subtype=edit_window}`。
- conformance-profiles.json 增加 `cx.profile.constraint.device_session.v1`。

#### Round 10 — Encoding 文档收敛

- 删除 `zh/conformance/hlc-specification.md`：操作伪代码（send / receive / compare）与验证规则
  并入 `encoding.md` §7.1-§7.3。
- 删除 `zh/conformance/cursor-encoding.md`：客户端契约 / canonical 内部结构 / 验证规则 /
  cursor 可迁移性 (服务器之间 reparse) / 一致性要求 并入 `encoding.md` §8.1-§8.6。
- `encoding.md` §2.1 新增 "备用 canonical encoding (profile-gated)"：注册 `cx.profile.encoding.cbor.v1`
  作为未来 CBOR (RFC 8949) deterministic encoding 的扩展点；引入 `encoding_extension_profiles`
  顶级字段到 conformance-profiles.json。
- conformance/README.md 更新文件清单。

#### federation.md ⇌ federation-wire.md 去重

- 删除 `zh/sync/federation-wire.md`（原 170 行）。federation.md §3.2 删除自指 `federation-wire.md §2`
  的注释，新增 §4.5 Fork Detection / Frontier Exchange（来自原 federation-wire.md §6 的 frontier
  exchange shape `{space_id, heads[], max_hlc, witness_receipts[]}` 与 duplicate_conflict 处理规则）。
- 4 处跨文件引用 (`security/server-threat-model`, `spec-map`, `service-http-binding`, `federation`
  本身) 重定向到 federation.md。spec-map 中重复行去重。

### 协议评审驱动的简化（2026-05-05，第三批：真删 + Event Envelope requirements 合并 + plane 重组 + conformance-vectors 合一）

#### 真删之前仅标 deprecated 的字段 / 注册表项

- `space_version`：从 `event-schema.json` / `space.schema.json` 完全删除（不仅是 required 列表）；
  `crypto-signature-fixture` 重新生成 canonical bytes / payload_hash / binding_hash / signed JWS（用
  test private key 重新签名并验证通过）；`event-envelope-negative-fixture` 11 个 event 全部清理；
  `encoding-conformance-vectors` 中的 canonical bytes vector + digest 重算。所有 .md 中 `space_version`
  提法删除或改写为指向 `reducer_profile_ref`。
- `cx.flow.convert`：从 `contract-catalog.json` event_kind_registry 删除（110 → 109 active kinds）；
  `event-schema.json` 移除对应 if/then 分支与 `flow_convert_payload` $def；prose 全部改为
  `cx.flow.branch.set_primary` + `cx.flow.branch.enable` 组合。
- `cx:operation:` typed-id：从 `id_kind_registry` 删除（37 → 36）；`cx.schema.operation.v1` 从 schema_registry
  删除（35 → 34）；`operation.schema.json` 与 zh 镜像完全删除；data-structures.md §18（Canonical
  Operation Object）删除，§19 Field Patch 重新编号为 §18。
- `constraint.priority`：从 `grant-constraint.schema.json` properties 删除；§2.1 base schema 不再列
  priority；§15 求值伪代码不再使用 priority；§6.3 container_move 示例移除 priority。

#### Event Envelope 4 个 profile/feature 字段 → 单一 requirements{} 对象

- `schema_profile_refs[]` / `reducer_profile_ref` / `required_features[]` / `critical_extensions[]`
  四个顶级字段从 wire schema 移除，合并为单一 `requirements: {schema[], reducer, features[],
  critical_extensions[]}`。
- `crypto-signature-fixture` 重新生成（canonical bytes、digest、签名全部更新；用 test private key
  重新签名并 Ed25519 公钥验证通过）。`event-envelope-negative-fixture` 11 个 event 收敛。所有 prose
  reference 更新（data-structures, operations-sync, api-conventions, service-http-binding,
  schema-registry, conformance-profiles, conformance-suite, event-auth-state-resolution,
  contract-catalog 描述文本）。

#### Read Marker / Relation.state / Notification

- Read Marker：删除 `timeline_order_key`（"may speed up comparison" — 不是 wire 必要，比较顺序
  应由客户端按 HLC 实现）。schema + prose 同步。
- `Relation.state` enum：`active|deleted|redacted` → `active|tombstone`；删除/撤回原因仅记录在
  `cx.relation.delete` / `cx.redaction` 事件上。
- `object-model-core.md` 核心对象列表：`notification` / `read_marker` 从 canonical 列表降级为
  "派生对象（不是 canonical truth，由 client / SDK 从 Event 集合本地计算）"。

#### Round 7 plane 重组

- 新 `zh/governance/` 目录，`authz/moderation.md` → `governance/content-moderation.md`。
- `authz/account-lifecycle.md` → `identity/account-lifecycle.md`（账号生命周期是 identity 概念，不是
  capability authorization）。
- 合并 `crypto-media/devices-and-auth.md` + `device-crypto-verification.md` → 单一 `device-lifecycle.md`
  （13 + 26 KB → 26 KB merged，重复内容被消除；§1-§3 来自 devices-and-auth 的 login/auth boundaries +
  pairing + SSO，§4-§15 来自 device-crypto-verification 的 device identity / signing / list sync /
  to-device / OTKs / KeyPackage claim / verification / secret storage / key backup / cross-signing /
  applet device delegation）。
- 全部跨文件引用更新。spec-map 中两条 device-lifecycle.md 重复条目去重；过期描述（identity-did
  默认值、event-auth-state-resolution scope）刷新。

#### Round 6 (audited E2EE) — 已在 batch 6 完成，本批不重做

#### R1.8 conformance-vectors 合并

- 5 个 `*-conformance-vectors.md`（encoding / state-resolution / redaction / capability / sync）合并为
  单一 `conformance-vectors.md`，按 §1-§5 分组。约 1,300 行整合。
- 所有跨文件引用全部更新（11 处 .md / .json）。
- 删除原 5 个文件。

#### 待 v1.1+ 的工作（写入 _todos.md）

- Round 9 constraint 类型 14→8 collapse：每个合并对需要新的 subtype discriminator 设计 + 全部
  fixture 迁移；不能简单的 rename。
- Round 10 encoding 演进（CBOR profile / HLC 并入 encoding.md）。
- v1.1+ profile id 正式登记到 conformance-profiles.json（webvh / tsp / audited_e2ee / binding 系列）。
- federation.md ↔ federation-wire.md 去重。

### 协议评审驱动的简化（2026-05-05，第二批：Round 6 + Round 8 子集）

#### Round 6 — Audited E2EE 拆出独立 hardening profile

- 新建 [`zh/crypto-media/audited-e2ee.md`](zh/crypto-media/audited-e2ee.md)：承载
  `cx.profile.attested_audit.e2ee.v1` 与 `cx.profile.disclosed_audit.e2ee.v1` 两类
  audited E2EE profile 的完整 normative：audit policy declaration、join warning canonical
  文案、audit agent entry、强制留痕 (`cx.audit.accessed`)、RYW receipt schema、transparency
  surface、forbidden marketing terms。
- `zh/crypto-media/encryption-and-audit.md` §3 缩为概览 stub 指向 audited-e2ee.md；文件从
  708 行 → 538 行（−24%）。Core E2EE / MLS 内容（§2 / §4-§7）完全保留，与 audit profile
  正交。
- `zh/spec-map.md` 增加 audited-e2ee.md 入口。

#### Round 8（子集）— 字段层 deprecation 标记

- `cx.flow.convert` event kind：在 `zh/sync/operations-sync.md` §9.4 与（已存在的）多处
  prose 中加 deprecation note，建议新写入方使用 `cx.flow.branch.set_primary` +
  `cx.flow.branch.enable`。registry 条目保持 active 以兼容现有实现，目标 v1.1+ 移除。
- `cx.schema.operation.v1` / `cx:operation:` typed-id：在 `zh/models/data-structures.md`
  §18 加 deprecation note，明确 Operation 是 SDK 内部 builder 中间对象，从未上 wire；
  v1.1+ 将移到 SDK guidance（不再作为 protocol normative 对象）。
- `constraint.priority` 字段：在 `zh/authz/constraint-schema.md` §2.1 标记为
  deprecated diagnostic，仅对 `effect=allow` 有诊断意义；新写入方 SHOULD 省略，可能在
  v1.1+ 从 schema 完全移除。

这三处 deprecation 都是 **prose-only**（注册表与 schema 保持向后兼容），目标是在 v1.1+
正式移除时不会破坏既有实现。

### 协议评审驱动的简化（2026-05-05）

基于全仓评审，本轮收敛掉了一批与 Matrix room state 风格继承的复杂性预算与对仍在演进外部
标准的 normative 绑定。详细任务清单见仓库根目录的 `_todos.md`。

#### Round 1 — 文件级合并（删除冗余文件）

- 删除 `zh/conformance/cursor-test-vectors.md`，向量入口并入 `cursor-encoding.md` §3.2。
- 删除 `zh/conformance/hlc-test-vectors.md`，向量入口并入 `hlc-specification.md` §3.4。
- 删除 `zh/discovery/read-notification-schema.md`，schema 与 query 形状并入 `read-receipts.md` §6。
- 删除 `zh/authz/grant-constraint-schema.md`，grant context 示例并入 `constraint-schema.md` §20.3。
- 删除 `zh/identity/progressive-disclosure.md`，渐进披露语义并入 `identity-handles.md` §16。
- 删除 `zh/models/conversation-model.md`，chat 模式示例与冲突规则并入 `object-model-standard.md` §5.1-§5.3。
- 删除 `zh/crypto-media/encrypted-envelope-schema.md`，envelope wire 形态、AAD 序列化、
  payload_digest 计算与解密错误码并入 `encryption-and-audit.md` §2.3.1-§2.3.4；schema 仍由
  `artifacts/schemas/encrypted-envelope.schema.json` 承载。

#### Round 2 — 状态解析与 Matrix 包袱去除（核心语义变更）

- **重写 `zh/authz/event-auth-state-resolution.md`**（882 行 → 685 行，约 −22%）：
  - **Lattice authority 替换为 quarantine-on-fork**：去除 §9.3.2 的 `governance_layer × authority_kind`
    二维 lattice 与派生 `auth_weight` 表。并发 fork 同 `(kind, state_key)` 由 reducer
    quarantine 全部非 winner 候选并要求 admin 显式介入，winner 不再由权重表自动选边。
  - **`space_version` 标记为 deprecated wire 字段**：版本演进通过 `reducer_profile_ref` /
    `schema_profile_refs` / `cx.space.upgrade` 表达。读取方 MUST 容忍兼容字段；新写入方
    SHOULD 省略。
  - 简化 §4.1 partial_auth_state：v1 默认 `max_offline_backlog_ms = 30 天`；离线超过窗口
    后必须重新拉 frontier 才能写入，去除 `soft_failed` / `partial_auth_state` 长期复活
    路径作为 normative 要求。
  - 简化 §6 history_sharing / policy_components / plaintext_visible_services：保留 auth state
    边界条款，完整 schema 与撤销语义指向 `crypto-media/encryption-and-audit.md` 与
    `sync/service-surface.md`。
  - 简化 §6.6 Organization Ownership：保留 6 步验证清单，详细 schema 指向 `identity/identity-did.md`。
- 同步更新 `artifacts/schemas/event-schema.json` 与 `space.schema.json`：把 `space_version` 从
  `required` 数组移除，字段 description 改为 deprecated 说明。
- 同步更新 `zh/models/data-structures.md`：Space §4 与 Event Envelope §9 的 `space_version`
  改为 `no (deprecated)` 必填性。

#### Round 3 — 外部互操作下沉为 v1.1+ extension

- `zh/extensions/mimi-interop.md` 顶部增加 v1.1+ extension banner：MIMI 仍是 IETF
  Internet-Draft；v1 core 不要求实现 MIMI provider facade。
- `zh/extensions/agent-protocol-interop.md` banner：A2A / ACP / MCP bridge 都未标准化（IBM
  Research 已宣布 ACP 并入 A2A）；v1 core 不要求实现 agent-protocol upgrade。
- `zh/extensions/applet-integration.md` banner：Applet registry 与审核 SLA 仍在演进；v1
  core 不要求实现。
- `zh/sync/service-surface.md` §9 (MIMI Provider Facade) 缩为单段指针，详细路径下沉到 extension。
- `artifacts/profiles/conformance-profiles.json` 增加 `profile_tiers` 顶级字段：
  - `v1_core_implementation` 列出 14 个 v1 core 必需 implementation profile。
  - `v1_1_extension_implementation` 列出 `applet_service` / `agent_runtime` / `mimi_interop`
    三个 v1.1+ extension。
  - `tier_rules` 解释 v1 core 与 extension 的 conformance 边界。

#### Round 4 — DID method 默认值收敛

- v1 core 默认 principal DID method 从 `did:webvh` 改为 **`did:web`**。理由：`did:web`
  生态成熟、HTTPS + 域名部署门槛低；`did:webvh` 仍在 W3C CCG 演进中。需要可审计身份历史的部署
  SHOULD 升级为 `did:webvh`（high-trust profile）。
- `did:plc`（AT Protocol interop）、`did:pkh`（钱包绑定）、KERI 系列、TSP transport 全部下沉为
  **v1.1+ interop extension**；v1 core 实现不要求支持。
- 同步更新：`zh/identity/identity-did.md` §3-§3.4、`zh/identity/tsp-integration.md` 顶部 banner、
  `zh/README.md`、`zh/overview/architecture.md` §2.8、`zh/overview/matrix-core-differences.md`。

#### Round 5 — Transport 路径锁定

- v1 core 互操作 transport **锁定为 HTTP/JSON**。`zh/sync/transport-bindings.md` 顶部声明
  HTTP/JSON 是 normative，gRPC / WebSocket / SSE / message queue / libp2p binding 全部
  下沉为 v1.1+ extension binding profile。
- `artifacts/bindings/non-http-bindings.yaml` 顶部增加 v1.1+ extension 状态注释；文件保留
  作为 extension binding 设计参考。

#### 仓库结构变更

- 删除文件：8 个（cursor-test-vectors / hlc-test-vectors / read-notification-schema /
  grant-constraint-schema / progressive-disclosure / conversation-model /
  encrypted-envelope-schema；以及一批 zh/spec-map.md 入口）。
- normative `zh/` 文本累计减少约 2,500 行（含 event-auth-state-resolution.md 的 197 行）。
- 机器约束（`artifacts/registry/`、`artifacts/schemas/`、`artifacts/profiles/`）保持向前
  兼容：v1 readers 必须容忍 deprecated 字段；既有 fixture 不要求重写。

### 发布候选状态

- 仓库当前发布状态为 `v1-core-rc`（候选基线）。详见
  [`zh/overview/release-readiness.md`](./zh/overview/release-readiness.md).
- 在以下条件全部满足前，仓库 / 标签不得宣称 `v1.0-stable`：
  1. 至少两个独立实现通过同一 reference validator 的
     `cx.profile.core_event_store.v1` 向量；
  2. reference validator / reference reducer / reference authz evaluator /
     conformance runner 已发布；
  3. canonical JSON、Event Envelope negative vectors、state resolution、
     capability、privacy/security、sync 与 snapshot vectors 由 CI 执行；
  4. 公开发布的翻译与附属文档不偏离同一 registry / fixture 基线。

### 当前基线内容

- 中文规范与机器可读 artifacts 同时锁定；中文文本是人类可读 normative
  来源，artifacts 是机器可验证 wire 真相源。
- Event Envelope、reducer、frontier、snapshot、sync、federation 的 wire fact
  以 `event_id` / actor frontier 为语义单位。
- `core_event_store` / `chat_mvp` / `kanban_mvp` 三个最小实现闭环。
- MLS RFC 9420 群组 E2EE、device verification、authenticated media、
  federation、sovereign deployment、Applet、Agent、MIMI interop、Directory、
  Moderation、Push 等扩展 profile。
- Audited E2EE 双 profile：`cx.profile.attested_audit.e2ee.v1`（硬件 attestation
  强制）与 `cx.profile.disclosed_audit.e2ee.v1`（流程性披露，无密码学强制）。
  Space policy 通过 `audit_disclosure` 对象 + `audit_assurance` enum 声明；UI
  join warning 与对外材料按 `encryption-and-audit.md` §3.1.1 / §3.5 normative
  分类与禁用措辞执行。
- Capability + constraint 求值规则：`deny` / `quarantine` / `require_review`
  一律"任一命中即生效"；`priority` 仅对 `effect=allow` 有诊断意义；每个
  constraint type 在 `constraint-schema.md` §2.3 有 canonical
  `evaluation_class`，授权评估器据此分 fast / slow path。
- `artifacts/registry/` 下的 contract catalog、event-kind / schema /
  id-kind / operation registry、error code registry、mirror manifest、
  conformance profile registry。
- `tools/artifact_pipeline.py` 流水线作为 registry / mirror 的唯一权威入口。

[Unreleased]: ./
