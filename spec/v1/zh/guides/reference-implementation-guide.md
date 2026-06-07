---
title: Reference Implementation Guide
status: candidate
normative: false
stability: v1
updated: 2026-05-25
sidebar:
  label: Reference Impl
---

本指南描述实现方如何消费本仓库的 canonical 输出。它不是完整实现清单；发布、认证与 profile 声明以 [`conformance-suite.md`](../conformance/conformance-suite.md)、[`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 和 `artifacts/fixtures/` 为准。

> **另见** [`artifact-consumption.md`](./artifact-consumption.md)：本指南聚焦"按何种顺序接入 artifact 生成 stub / 跑一致性向量";artifact 消费指南聚焦"哪些 artifact 是 source of truth 及其消费边界"。二者配合阅读。

## 1. 推荐接入顺序

1. 读取根目录 [`artifacts/registry/schema-registry.json`](../../artifacts/registry/schema-registry.json)、[`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 与 [`operation-registry.json`](../../artifacts/registry/operation-registry.json)。
   若需要判断 canonical source、surface tier 和 generated view 的关系，先读 [`artifacts/registry/contract-catalog.json`](../../artifacts/registry/contract-catalog.json)。
2. 用 `artifacts/schemas/` 的 JSON Schema 做结构校验。
3. 用 [`artifacts/openapi/cokret-service-api.openapi.yaml`](../../artifacts/openapi/cokret-service-api.openapi.yaml) 生成服务 stub、client 或 contract tests。
4. 用 `artifacts/fixtures/` 运行一致性向量。
5. 依据 [`conformance-profiles.md`](../conformance/conformance-profiles.md) 与 `artifacts/profiles/conformance-profiles.json` 声明实现 profile。
6. 产测与契约边界应以 active contract fixtures、registry 和 conformance profile 为准。

## 2. 实现提示

- 写路径的幂等键要求以 [`../sync/service-http-binding.md`](../sync/service-http-binding.md) 和 OpenAPI artifact 为准。
- 结构校验、signature、hash、capability、policy 与 MLS 验证的顺序以各 canonical schema、authz、crypto 和 sync 文档为准；实现时不要把 JSON Schema 通过视为完整接收。
- `operation_id`、`Event.kind`、schema id、profile id 是稳定契约锚点，来源分别是 registry 与 profile artifact。
- 长期认证材料只放在 header / proof / mTLS 等已登记认证面；query string 只承载 selector / cursor / pagination 等非长期凭据字段。
- 对非 active contract 输入的拒绝基线，须使用 conformance fixtures 与 active registry 的标准序列验证，不接受口头约定替代。

## 3. 产出建议

- SDK：typed builders + validators。
- 服务端：OpenAPI contract test + fixture runner。
- 客户端：schema decode + sync/profile regression。
- `cotest`：以 profile 为单位输出 pass/fail 与 coverage。

## 4. 交接基线

- 下游对齐清单：`artifacts/fixtures/` 与 `artifacts/profiles/conformance-profiles.json`
- 黑盒拒绝基线：`artifacts/fixtures/*` 中与 conformance profile 对齐的 reject/mutation 套件
