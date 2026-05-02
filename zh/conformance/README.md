# Contrix v1 一致性工件索引

本目录汇总 Contrix v1 的一致性规范、测试向量与机器工件入口。

## 目录

- `schemas/`：JSON Schema 工件，覆盖核心对象、sync、blob/media、push、identity、MIMI interop。
- `fixtures/`：官方 JSON fixture，供 `cotest`、SDK 和服务端实现直接消费，包含 crypto signature、MIMI interop 等向量。
- `encoding.md`、`encoding-conformance-vectors.md`：canonical JSON、hash、proof、HLC、cursor、rank。
- `cursor-encoding.md`、`cursor-test-vectors.md`：cursor 编码规范与向量。
- `hlc-specification.md`、`hlc-test-vectors.md`：HLC 文本格式、比较规则与向量。
- `state-resolution-conformance-vectors.md`、`redaction-conformance-vectors.md`、`capability-conformance-vectors.md`、`sync-conformance-vectors.md`：核心行为向量。
- `scalability-constraints.md`：v1 wire、授权、state resolution、Board/Relation/View 和 E2EE 的规模上限。
- `schema-registry.md`、`conformance-profiles.md`、`conformance-suite.md`：registry、profile 与 suite。

语言无关的 canonical 输出位于根目录 [`artifacts`](../../artifacts/README.md)。
