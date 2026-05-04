# Changelog

本文件记录 Contrix 协议规范在主要发布之间的变化。

格式参考 [Keep a Changelog](https://keepachangelog.com/) 与
[Semantic Versioning](https://semver.org/)。

本仓库尚未发布任何版本。下方条目描述的是 `v1-core-rc` 候选基线的当前内容，
而不是相对任何先前公开版本的差异。

## [Unreleased] — `v1-core-rc`

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
