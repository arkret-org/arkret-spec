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
