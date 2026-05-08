# contrix-spec TODO

> 整理日期: 2026-05-08
> 范围: Contrix v1 normative spec、machine-readable artifacts、协议站。
> 当前事实源: `spec/v1/zh/` + `spec/v1/artifacts/` + `tools/artifact_pipeline.py`。

## 当前状态摘要

- `python tools/artifact_pipeline.py check` 当前通过: 129 event kinds、37 schemas、36 typed ID kinds、83 operations、53 profiles。
- `v1.0.0` 已作为稳定基线写入 `CHANGELOG.md`，active wire contract 以 `spec/v1/artifacts/registry/contract-catalog.json` 和派生 registry 为准。
- 规范文本已迁到 `spec/v1/zh/`；根目录和下游仓库中的协议源引用已经同步到当前路径。
- P0（规范源一致性）、P1（协议站改进）、P2（v1.1+ profile）、Move·Anchor·Lattice 重构（MAL-1..6）全部完成。Bottom diagnostics OpenAPI DTO 已落入 `contrix-service-api.openapi.yaml`。
- 唯一剩余开放项是 Q1 英文发布策略（等待 product 决定）。

## 标记说明

- `[ ]` 未完成
- `[~]` 部分完成 / 等下游或外部决策
- `[x]` 已完成，保留为短 changelog
- `🅿` parallel-safe: 单文档 / 单 artifact / 单 site 页面
- `🔒` sequential: 改 canonical registry/schema/profile，会触发下游同步
- `⚠` high-risk: wire contract / conformance profile / 发布边界变更

## 开放任务

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| Q1 🅿 | `[~]` | 英文 normative 发布策略 | `spec/v1/en/index.md`、site | 现状: `spec/v1/en/index.md` 声明英文 normative "not yet published"，请读者回退到中文 + artifacts。仍需正式决定: 隐藏 `/en/` 路由、保留 placeholder + preview 标签，或安排 v1.0 英文版翻译。决定后再更新本条。 |
| MAL-1 ⚠ | `[x]` | consent-model.md §3-§9 重写为 Move/Anchor/Lattice 表述 | `spec/v1/zh/identity/consent-model.md` | grant=add tag / revoke=remove tag on consent cell or-set；invite gate 改为 cell join 查询；MIMI interop 改为 Move 构造。保留 holder-private、不进入协作 Space、与 capability 正交三条不变量。 |
| MAL-2 🅿 | `[x]` | sync / federation / operations-sync / service-surface 二轮 reread | `spec/v1/zh/sync/*` | 已确认主线文档无 "host writer / writer_model / host endorsement" 漏网；旧 "state slot" 表述在 space-hierarchy.md / device-lifecycle.md / profiles-presence.md / matrix-core-differences.md / consent-model.md 已统一改为 cell + lattice 措辞。 |
| MAL-3 🅿 | `[x]` | conformance-vectors.md 加入 move-anchor-lattice-fixture 4 vector 显式枚举 | `spec/v1/zh/conformance/conformance-vectors.md` | 已加入 §2.2-2.5 normative 枚举（multi_cell_ban_revoke / cas_bottom / anchor_batch_pre_state / mls_covered_frontier）。 |
| MAL-4 🅿 | `[x]` | 为每个核心 Lattice type 补参考实现章节 | `spec/v1/zh/authz/event-auth-state-resolution.md` §5.3 | or-set / mv-register / cas-register / fsm / counter / ordered-log 各 normative join + validate_op 伪代码；§5.4 禁止 profile 引入新 lattice type。 |
| MAL-5 🅿 | `[x]` | Bottom diagnostics typed schema + sync/events/state API 暴露 | `spec/v1/artifacts/schemas/bottom.schema.json`、`spec/v1/zh/sync/service-surface.md` §5.5 | 新增 `cx.schema.bottom.v1` typed schema（kind 6 种、cells/move_ids/anchor_view/heads/details/escalated_at 字段）；service-surface §5.5 documented Move state 字段 + Bottom 暴露规则。registry/lint 通过：127 event kinds、37 schemas、52 profiles。 |
| MAL-6 🅿 | `[x]` | Anchor compaction / recovery Anchor conformance vectors | `spec/v1/artifacts/fixtures/move-anchor-lattice-fixture.json`、`spec/v1/zh/conformance/conformance-vectors.md` §2.6-2.8 | 新增 4 vector：anchorer_cell_bottom_pauses_space_until_recovery / signed_compaction_anchor_equals_effective_view / anchor_dag_genesis_and_multi_leaf_join（含 4 case 矩阵） |
| MAL-7 🅿 | `[x]` | Bottom diagnostics OpenAPI DTO | `spec/v1/artifacts/openapi/contrix-service-api.openapi.yaml`、`spec/v1/artifacts/schemas/client-sync-response.schema.json` | 在 OpenAPI components 加入 `BottomDiagnostic`（$ref bottom.schema.json）、`MoveStateView`（move_id+move_state+bottom 枚举）、`CellQueryEnvelope`（cell/status/value/heads/bottom）三个 typed DTO；client-sync-response 增补 `move_states[]` / `bottoms[]` 两个 typed 字段，使 §5.5 wire 形态对 codegen 可见。 |
| RR-1 ⚠ 🔒 | `[x]` | Read Receipt policy 机器 registry 对齐 | `spec/v1/artifacts/registry/contract-catalog.json`、`spec/v1/artifacts/schemas/event-schema.json`、`spec/v1/zh/conformance/schema-registry.md` | (2026-05-08) `cx.space.read_receipt_policy`（cas-register / bottom=reject / cell_subject=null）与 `cx.flow.branch.read_receipt_policy`（cas-register / bottom=reject / composite cell_subject `envelope.flow_id`+`payload.branch`）已在 `contract-catalog.json` 登记，`event-schema.json` enum 跟进，doc registry 表追加 2 行。`python tools/artifact_pipeline.py generate` 重写 `event-kind-registry.json` / `schema-registry.json` / `id-kind-registry.json` / `operation-registry.json`，`check` 全绿：129 event kinds（127→129）、37 schemas、36 typed ID kinds、83 operations、53 profiles。仍需 SDK / soland / yougen / cotest 端的 typed model 与 fanout 行为，见根 `_todos.md` C14.B-E。 |

## 已完成（changelog）

- `[x]` v1.0.0 registry / schema / fixture artifact lint 当前通过。
- `[x]` active wire contract 已迁到 `spec/v1/artifacts/`。
- `[x]` P0 R1-R9: contract-catalog 路径修正、`.mdx` 扩展名统一、federation.md 去重、"中文镜像"措辞清理、conformance README 重写、artifacts README 重写、release-readiness mirror lint 修正、CHANGELOG 模板修正、artifact_pipeline docstring 校正。
- `[x]` P1 W1-W11: astro check 修复、占位 URL 替换、catalog 详情页面包屑、首页 stats 对齐、OpenAPI 主题联动、SEO/OG 英文双开关、hero CTA 对齐、operations surface 跳转、event-kinds 分类筛选。
- `[x]` P2 P1-P5: `did:webvh` profile 文本化、non-HTTP binding 发布边界、Applet/Agent/MIMI extension profile、CBOR encoding profile、constraint family 迁移注记。
- `[x]` Q2 site crossref / schema rendering gate。
- `[x]` Q3 release-readiness 页面同步 artifact 计数。

## 跨项目登记

跨项目执行项不在本文件展开，统一放根 [`../_todos.md`](../_todos.md)。本文件只保留协议源自身需要完成的工作。
