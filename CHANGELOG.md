# Changelog

本文件记录 Contrix 协议规范在主要发布之间的变化。

格式参考 [Keep a Changelog](https://keepachangelog.com/) 与
[Semantic Versioning](https://semver.org/)。

## [Unreleased]

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

### Changed

- 字段、enum、错误码、envelope 形态在多个文件之间的对齐扫除（详见
  `_report.md`）。
- `tools/artifact_pipeline.py` 流水线作为 registry / mirror 的唯一权威入口。
- **BREAKING (pre-stable)**: Auditable E2EE profile family 重命名。
  `cx.profile.auditable_e2ee.tee_required.v1` → `cx.profile.attested_audit.e2ee.v1`；
  `cx.profile.auditable_e2ee.software_only.v1` → `cx.profile.disclosed_audit.e2ee.v1`。
  动机：旧 family 名 `auditable_e2ee` 共享前缀让"硬件强制"与"流程承诺"看起来等价，
  容易在合规/采购/监管语境被误读为同一保证的强弱。新名字把 enforcement 类别
  显式带入 profile id（`attested` vs `disclosed`），消除统称的歧义空间。
- **BREAKING (pre-stable)**: Space `audit_*` policy 字段重构为两个正交维度。
  删除 `auditable_e2ee: bool` / `auditable_e2ee_profile` / `audit_enforcement_level`；
  新增 `audit_disclosure` 对象（透明度承诺）+ `audit_assurance` enum
  (`attested_hardware` | `disclosed_policy`)。两字段与 profile id 一一映射，schema
  通过 `if/then` 强约束一致。详见
  [`zh/crypto-media/encryption-and-audit.md §3.1`](./zh/crypto-media/encryption-and-audit.md)。
- Constraint 求值算法压扁。`deny` / `quarantine` / `require_review` 三类一律
  "任一命中即生效"，跨 effect 之间不再用 `priority` 排序。`priority` 仅对
  `effect=allow` 有效，且只用于诊断（标识哪条 allow 解释了 ALLOWED）。详见
  [`zh/authz/constraint-schema.md §15`](./zh/authz/constraint-schema.md)。
- Constraint `condition.when` 字符串字段重命名为 `condition.kind`，与 typed flat
  constraint 的命名风格对齐；未注册的 kind MUST fail closed。enum 内容不变。

### Added

- `cx.audit.ryw_receipt` durable event kind（解决 `_report.md` B-13）。在
  `cx.profile.attested_audit.e2ee.v1` 下，RYW receipt 可作 durable Event 进入
  audit log；在 `cx.profile.disclosed_audit.e2ee.v1` 下默认仍是 actor-private /
  ephemeral。
- `audit-ryw-receipt.schema.json` 新增必填字段 `audit_assurance_class`
  (`attested_hardware` | `disclosed_policy`)。Audit Agent MUST 把 Space 声明的
  `audit_assurance` 值原样填入；接收方在 frontier 处发现不一致 MUST fail closed。
- `grant-constraint.schema.json` 新增字段 `evaluation_class`
  (`stateless` | `grant_local` | `space_state` | `external`)，作为授权评估器
  的可缓存性 hint。每个 `constraint_type` 在 `constraint-schema.md §2.3` 有
  canonical 分类；实现 MAY 收紧但 MUST NOT 放宽；`external` 类约束 MUST NOT 缓存。
  这条 hint 让 fast path（仅 stateless + grant_local）可以承载 read marker /
  reaction 等低风险动作的高频授权检查。
- `encryption-and-audit.md §3.1.1` 拆分 join warning 为 `attested_hardware` 与
  `disclosed_policy` 两套 normative MUST 文案，禁止合并。
- `encryption-and-audit.md §3.5` 新增 forbidden-marketing-terms normative 段，
  禁止 `cx.profile.disclosed_audit.e2ee.v1` 的对外材料使用
  "cryptographically enforced audit" / "hardware-bound audit" /
  "TEE-equivalent" 等暗示密码学强制的措辞；conformance suite SHOULD 含
  `forbidden_marketing_terms_check` lint vector。

## [v1-core-rc] - 2026-05-04

### Added

- 第一版 Chinese normative spec 与 machine-readable artifacts 同时锁定；
- Event Envelope、reducer、frontier、snapshot、sync、federation 的 wire fact
  以 `event_id` / actor frontier 为语义单位；
- `core_event_store` / `chat_mvp` / `kanban_mvp` 三个最小实现闭环；
- MLS RFC 9420 群组 E2EE、device verification、authenticated media、
  federation、sovereign deployment、Applet、Agent、MIMI interop、Directory、
  Moderation、Push 等扩展 profile 框架；
- `artifacts/registry/` 下的 contract catalog、event-kind / schema /
  id-kind / operation registry、error code registry、mirror manifest、
  conformance profile registry。

[Unreleased]: ./
[v1-core-rc]: ./
