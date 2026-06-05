---
title: Reference Implementation Guide
status: candidate
normative: false
stability: v1
updated: 2026-05-25
sidebar:
  label: Reference Impl
---

本指南描述实现方如何消费本仓库的 canonical 输出。

> **另见** [`artifact-consumption.md`](./artifact-consumption.md)：本指南聚焦"按何种顺序接入 artifact 生成 stub / 跑一致性向量";artifact 消费指南聚焦"哪些 artifact 是 source of truth 及其消费边界"。二者配合阅读。

## 1. 推荐接入顺序

1. 读取根目录 [`artifacts/registry/schema-registry.json`](../../artifacts/registry/schema-registry.json)、[`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 与 [`operation-registry.json`](../../artifacts/registry/operation-registry.json)。
   若需要判断 canonical source、surface tier 和 generated view 的关系，先读 [`artifacts/registry/contract-catalog.json`](../../artifacts/registry/contract-catalog.json)。
2. 用 `artifacts/schemas/` 的 JSON Schema 做结构校验。
3. 用 [`artifacts/openapi/cokret-service-api.openapi.yaml`](../../artifacts/openapi/cokret-service-api.openapi.yaml) 生成服务 stub、client 或 contract tests。
4. 用 `artifacts/fixtures/` 运行一致性向量。
5. 依据 `conformance-profiles.md` 与 `artifacts/profiles/conformance-profiles.json` 声明实现 profile。
6. 产测与契约边界应以 active contract fixtures、registry 和 conformance profile 为准。

## 2. 实现要求

- 所有写路径 MUST 支持幂等键。
- 结构校验通过后，仍 MUST 独立执行 signature、hash、capability、policy 与 MLS 验证。
- `operation_id`、`Event.kind`、schema id、profile id MUST 视为稳定契约锚点。
- query string MUST NOT 承载长期认证材料。
- 对非 active contract 输入的拒绝基线，须使用 conformance fixtures 与 active registry 的标准序列验证，不接受口头约定替代。

## 3. 产出建议

- SDK：typed builders + validators。
- 服务端：OpenAPI contract test + fixture runner。
- 客户端：schema decode + sync/profile regression。
- `cotest`：以 profile 为单位输出 pass/fail 与 coverage。

## 4. 交接基线

- 下游对齐清单：`artifacts/fixtures/` 与 `artifacts/profiles/conformance-profiles.json`
- 黑盒拒绝基线：`artifacts/fixtures/*` 中与 conformance profile 对齐的 reject/mutation 套件
