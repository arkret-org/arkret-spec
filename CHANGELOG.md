# Changelog

本文件记录 Contrix 协议规范在主要发布之间的变化。

格式参考 [Keep a Changelog](https://keepachangelog.com/) 与
[Semantic Versioning](https://semver.org/)。

本仓库尚未发布任何版本。下方条目描述的是 `v1-core-rc` 候选基线的当前内容，
而不是相对任何先前公开版本的差异。

## [Unreleased] — `v1-core-rc`

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
