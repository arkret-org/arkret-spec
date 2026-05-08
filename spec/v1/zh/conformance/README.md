---
title: Contrix v1 一致性工件索引
---

本目录是 Contrix v1 一致性规范的 normative prose 入口。它只承载文字化规范，
不再保存 schema / fixture 镜像副本——canonical machine artifact 唯一来源是
[`spec/v1/artifacts/`](../../artifacts/README.md)，由 `tools/artifact_pipeline.py`
管理。

## 文档清单

- `encoding.md`：canonical JSON、hash、proof、HLC（§7）、cursor（§8）、rank、composite state key 的 wire 编码与操作伪代码。
- `conformance-vectors.md`：合并的一致性测试向量（encoding & crypto / Move-Anchor-Lattice / redaction / capability / sync 共 5 个域）。
- `scalability-constraints.md`：v1 wire、授权、Move/Anchor/Lattice、Board/Relation/View 和 E2EE 的规模上限。
- `schema-registry.md`：标准 schema / event type registry 的说明视图。
- `conformance-profiles.md`：实现 profile 与一致性测试范围。
- `conformance-suite.md`：自动化互操作 suite、向量优先级、组件测试矩阵。
- `query-schema.md`：View / Search / Inbox 可复用查询形状。
- `snapshot-schema.md`：Snapshot manifest、chunk、signature、encrypted envelope。

## 机器构件入口

| 类型 | 位置 |
| --- | --- |
| Registry（contract-catalog 等） | [`spec/v1/artifacts/registry/`](../../artifacts/registry/) |
| JSON Schema | [`spec/v1/artifacts/schemas/`](../../artifacts/schemas/) |
| Conformance fixture | [`spec/v1/artifacts/fixtures/`](../../artifacts/fixtures/) |
| OpenAPI HTTP binding | [`spec/v1/artifacts/openapi/contrix-service-api.openapi.yaml`](../../artifacts/openapi/contrix-service-api.openapi.yaml) |
| 非 HTTP transport binding（extension profile） | [`spec/v1/artifacts/bindings/non-http-bindings.yaml`](../../artifacts/bindings/non-http-bindings.yaml) |
| Conformance profile 矩阵 | [`spec/v1/artifacts/profiles/conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) |

修改 canonical machine artifact 时，先改 [`spec/v1/artifacts/`](../../artifacts/) 下的 canonical 源，
再执行 `python tools/artifact_pipeline.py generate` 同步派生注册表视图，最后用
`python tools/artifact_pipeline.py check` 验证未发生 drift。
