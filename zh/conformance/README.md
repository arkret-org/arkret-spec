# Contrix v1 一致性工件索引

本目录汇总 Contrix v1 的一致性规范、测试向量与机器工件入口。

注意：本目录中的 `schemas/` 与 `fixtures/` 是根目录 `artifacts/` 的镜像副本，不是独立真相源。修改 canonical machine artifact 时，应先改 `artifacts/`，再用 `python tools/artifact_pipeline.py sync` 同步到本目录。镜像路径清单由 `artifacts/registry/mirror-manifest.json` 统一声明。

## 目录

- `schemas/`：JSON Schema 工件，覆盖核心对象、Event Envelope payload classes、sync、blob/media、push、identity、moderation、Agent Authority、MIMI interop。
- `fixtures/`：官方 JSON fixture，供 `cotest`、SDK 和服务端实现直接消费，包含 crypto signature、Event Envelope 负向验证、reject baseline、state resolution、capability、sync、privacy/security、MIMI interop 等向量。
- `encoding.md`、`encoding-conformance-vectors.md`：canonical JSON、hash、proof、HLC、cursor、rank。
- `cursor-encoding.md`、`cursor-test-vectors.md`：cursor 编码规范与向量。
- `hlc-specification.md`、`hlc-test-vectors.md`：HLC 文本格式、比较规则与向量。
- `state-resolution-conformance-vectors.md`、`redaction-conformance-vectors.md`、`capability-conformance-vectors.md`、`sync-conformance-vectors.md`：核心行为向量。
- `scalability-constraints.md`：v1 wire、授权、state resolution、Board/Relation/View 和 E2EE 的规模上限。
- `schema-registry.md`、`conformance-profiles.md`、`conformance-suite.md`：registry、profile 与 suite。

语言无关的 canonical 输出位于根目录 [`artifacts`](../../artifacts/README.md)。
