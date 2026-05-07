# contrix-spec TODO

> 整理日期: 2026-05-07
> 范围: Contrix v1 normative spec、machine-readable artifacts、协议站。
> 当前事实源: `spec/v1/zh/` + `spec/v1/artifacts/` + `tools/artifact_pipeline.py`。

## 当前状态摘要

- `python tools/artifact_pipeline.py check` 当前通过: 110 event kinds、34 schemas、36 typed ID kinds、83 operations、48 profiles。
- `v1.0.0` 已作为稳定基线写入 `CHANGELOG.md`，active wire contract 以 `spec/v1/artifacts/registry/contract-catalog.json` 和派生 registry 为准。
- 规范文本已迁到 `spec/v1/zh/`；根目录和下游仓库中的协议源引用已经同步到当前路径。
- P0（规范源一致性）、P1（协议站改进）、P2（v1.1+ profile）全部完成。唯一剩余开放项是 Q1 英文发布策略。

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
