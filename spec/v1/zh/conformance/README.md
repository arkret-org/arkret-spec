---
title: Cokret v1 一致性工件索引
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

本目录是 Cokret v1 一致性规范的 normative prose 入口。它只承载文字化规范，
conformance 目录只引用 canonical machine artifact，不保存 schema / fixture 镜像副本；唯一来源是
[`spec/v1/artifacts/`](../../artifacts/README.md)，由 `tools/artifact_pipeline.py`
管理。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 文档清单

- `encoding.md`：canonical JSON、hash、proof、HLC（§7）、cursor（§8）、rank、composite state key、encrypted envelope digest（§10）、AEAD nonce 唯一性（§10.1）的 wire 编码与操作伪代码。
- `conformance-vectors.md`：合并的一致性测试向量；域索引以该文件导言与 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为准。
- `scalability-constraints.md`：v1 wire、授权、CBA/Lattice、Board/Relation/View 和 E2EE 的规模上限。
- `schema-registry.md`：标准 schema / event type registry 的说明视图。
- `conformance-profiles.md`：实现 profile 与一致性测试范围。
- `conformance-suite.md`：自动化互操作 suite、向量优先级、组件测试矩阵。
- `query-schema.md`：View / Search / Inbox 可复用查询形状。
- `snapshot-schema.md`：Snapshot manifest、chunk、signature、encrypted envelope。

## 机器构件入口

| 类型 | 位置 |
| --- | --- |
| Registry（contract-catalog 等） | [`spec/v1/artifacts/registry/`](../../artifacts/registry/) |
| Conformance vector registry | [`spec/v1/artifacts/registry/vector-registry.json`](../../artifacts/registry/vector-registry.json) |
| Account Data type registry | [`spec/v1/artifacts/registry/account-data-type-registry.json`](../../artifacts/registry/account-data-type-registry.json) |
| Error code registry | [`spec/v1/artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json) |
| JSON Schema | [`spec/v1/artifacts/schemas/`](../../artifacts/schemas/) |
| Conformance fixture | [`spec/v1/artifacts/fixtures/`](../../artifacts/fixtures/) |
| OpenAPI HTTP binding | [`spec/v1/artifacts/openapi/cokret-service-api.openapi.yaml`](../../artifacts/openapi/cokret-service-api.openapi.yaml) |
| 非 HTTP transport binding（extension profile） | [`spec/v1/artifacts/bindings/non-http-bindings.yaml`](../../artifacts/bindings/non-http-bindings.yaml) |
| Conformance profile 矩阵 | [`spec/v1/artifacts/profiles/conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) |

修改 canonical machine artifact 时，先改 [`spec/v1/artifacts/`](../../artifacts/) 下的 canonical 源，
再执行 `python tools/artifact_pipeline.py generate` 同步派生注册表视图，最后用
`python tools/artifact_pipeline.py check` 验证未发生 drift。

## Markdown JSON 示例校验

完整 wire JSON 示例的 fence MUST 使用 `schema=` 标注本地 artifact schema，例如把 fence header 写为
```` `json schema=schemas/event-envelope.schema.json` ````。

`tools/lint_artifacts.py` 会抽取这些 fence，用本地 JSON Schema resolver 校验相对 `$ref` 与 `https://cokret.org/v1/...` `$id`。片段式示例或非 wire JSON MAY 不标注 `schema=`，但仍会执行 canonical JSON、typed ID、event kind、operation id 与 profile/schema id 的基础扫描。负向 Markdown schema 示例 MUST 写 `expect=invalid first_error="..."`；负向 fixture case MUST 写 `first_expected_error`，用于固定预期失败原因。
