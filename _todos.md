# contrix-spec TODO

> 整理日期: 2026-05-07
> 范围: Contrix v1 normative spec、machine-readable artifacts、协议站。
> 当前事实源: `spec/v1/zh/` + `spec/v1/artifacts/` + `tools/artifact_pipeline.py`。

## 当前状态摘要

- `python tools/artifact_pipeline.py check` 当前通过: 110 event kinds、34 schemas、36 typed ID kinds、83 operations、48 profiles。
- `v1.0.0` 已作为稳定基线写入 `CHANGELOG.md`，active wire contract 以 `spec/v1/artifacts/registry/contract-catalog.json` 和派生 registry 为准。
- 规范文本已迁到 `spec/v1/zh/`；根目录和下游仓库中的协议源引用已经同步到当前路径。
- 协议侧开放项以后统一写入本文件。

## 标记说明

- `[ ]` 未完成
- `[~]` 部分完成 / 等下游或外部决策
- `[x]` 已完成，保留为短 changelog
- `🅿` parallel-safe: 单文档 / 单 artifact / 单 site 页面
- `🔒` sequential: 改 canonical registry/schema/profile，会触发下游同步
- `⚠` high-risk: wire contract / conformance profile / 发布边界变更

## P0 · 规范源一致性

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| S1 🔒 | `[x]` | 修正 event kind 数量叙述漂移 | `CHANGELOG.md` | 已确认 `cx.flow.convert` 移除（110 → 109）后，`cx.profile.create` 在 actor_profile 评审中加回到 110；CHANGELOG batch 7 段加注释，并在 R1.8 之后新增 "actor_profile + gatekeeper 收尾" 段记录 actor_profile / 18 BLOCKER 修复。 |
| S2 🅿 | `[x]` | 清理旧路径引用 | `spec/v1/zh/spec-map.md`、`spec/v1/zh/overview/release-readiness.md` | `spec-map.md` 中 `zh/sync/contrix-service-api.openapi.yaml` 改为 `artifacts/openapi/contrix-service-api.openapi.yaml`（OpenAPI 已迁到 artifacts/）；`release-readiness.md` 工件矩阵移除已不存在的 `zh/conformance/fixtures/*.json`。下游仓库的旧 `contrix-spec/zh/` 引用属跨项目工作，登记到根 `_todos.md`。 |
| S3 🅿 | `[x]` | 清理旧审计报告引用 | `tools/lint_artifacts.py` | 当前仓库无 `_report.md`；`tools/lint_artifacts.py::check_openapi_contract_shape` 已把 `_report.md` 列入 OpenAPI 禁用词，CI 自动阻止新引用。下游仓库残留属跨项目工作，登记到根 `_todos.md`。 |
| S4 🔒 | `[x]` | 建立 profile / registry 变更登记模板 | `CHANGELOG.md` | 在 `CHANGELOG.md` 顶部新增 "v1.1+ 变更登记模板" 段，规定每次 registry / schema / profile 变更必须列变更类型、影响 artifact、canonical 变更、派生同步、conformance impact、fixture 重生成、prose 同步与迁移指南。 |

## P1 · v1.1+ profile 与扩展面

| # | 状态 | 任务 | 文件 | 并行性 |
|---|---|---|---|---|
| P1 🅿 | `[x]` | `did:webvh` high-trust profile 文本化 | `spec/v1/zh/identity/identity-did.md` §3.3、`conformance-profiles.json` `cx.profile.org_high_assurance_identity.v1` | profile 已注册为 `identity_extension_profiles`，`did:webvh_witness` / `did:webvh_watcher` 列入 optional_extensions，`history_bearing_did_method` 是必需 feature；prose §3.3 描述 SCID / entry hash chain / controller proof 验证要求。 |
| P2 🅿 | `[x]` | non-HTTP binding profile 发布边界 | `spec/v1/zh/sync/transport-bindings.md`、`spec/v1/artifacts/bindings/non-http-bindings.yaml` | core 锁定 HTTP/JSON 为 normative；gRPC / WS / SSE / MQ / libp2p 全部声明为 v1.1+ extension binding；`non-http-bindings.yaml` 顶部声明 v1.1+ extension reference 状态。 |
| P3 🅿 | `[x]` | Applet / Agent / MIMI extension conformance profile 明确化 | `conformance-profiles.json` `profile_tiers.v1_1_extension_implementation` | `cx.profile.applet_service.v1` / `cx.profile.agent_runtime.v1` / `cx.profile.mimi_interop.v1` 已列入 v1.1+ extension tier，并在 `tier_rules` 中说明可选性与外部标准成熟后替换路径。 |
| P4 🅿 | `[x]` | CBOR deterministic encoding extension profile | `spec/v1/zh/conformance/encoding.md` §2.1、`conformance-profiles.json` `encoding_extension_profiles` | `cx.profile.encoding.cbor.v1` 已注册为 encoding extension profile；core v1 仍以 canonical JSON 为唯一 normative encoding。 |
| P5 🔒 | `[x]` | constraint family 下游迁移注记 | `spec/v1/zh/authz/constraint-schema.md` §3 | §3 包含完整 v0→v1 family 命名映射（`approval_workflow` → `claim_based{subtype=approval}` 等）以及 14→8 收敛说明；下游 SDK / cotest 用此段翻译既有 grant。 |

## P2 · 协议站与发布质量

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| Q1 🅿 | `[~]` | 英文 normative 发布策略 | `spec/v1/en/index.md`、site | 现状: `spec/v1/en/index.md` 声明英文 normative "not yet published"，请读者回退到中文 + artifacts。仍需正式决定: 隐藏 `/en/` 路由、保留 placeholder + preview 标签，或安排 v1.0 英文版翻译。决定后再更新本条。 |
| Q2 🅿 | `[x]` | site crossref / schema rendering gate | `.github/workflows/site.yml` | PR gate 已固定 `npm run check` + `npm run crossref` + `npm run build`，并把 `site/dist` 上传为 artifact；任一步失败会阻塞合并。 |
| Q3 🅿 | `[x]` | release-readiness 页面同步 artifact 计数 | `spec/v1/zh/overview/release-readiness.md` §2 | 新增 registry 计数表（110 event kinds / 34 schemas / 36 typed ID / 83 operations / 48 profiles）并要求与 `tools/artifact_pipeline.py check` 输出一致；新增/退役 registry 项 MUST 同步本表。 |

## 跨项目登记

跨项目执行项不在本文件展开，统一放根 [`../_todos.md`](../_todos.md)。本文件只保留协议源自身需要完成的工作。

## 已完成（changelog）

- `[x]` v1.0.0 registry / schema / fixture artifact lint 当前通过。
- `[x]` active wire contract 已迁到 `spec/v1/artifacts/`，root `artifacts/` 仅为历史目录/兼容残留。
- `[x]` 2026-05-07 整批: S1-S4、P1-P5、Q2-Q3 全部完成；CHANGELOG 增加 v1.1+ 变更登记模板与 actor_profile + gatekeeper 收尾段；release-readiness 增加 registry 计数表；spec-map / release-readiness 修复失效路径。Q1 仍待英文发布策略决策。
