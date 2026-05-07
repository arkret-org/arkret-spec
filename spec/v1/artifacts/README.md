---
title: Artifacts
---

`artifacts/` 存放 Contrix 的机器可读协议契约（machine-readable contract）。

## 1. 约定与分层

### 1.1 真实来源（Canonical）

- `artifacts/registry/contract-catalog.json`
  - 事件 kind、schema、typed-ID 与 operation 的源定义。
- `artifacts/registry/error-code-registry.json`
  - 错误码体系。
- `artifacts/registry/registry-manifest.json`
  - `artifacts/registry/` 下所有机器注册表索引。
- `artifacts/profiles/conformance-profiles.json`
  - 实现 / 部署 / 向量 / hardening profile 矩阵。
- `artifacts/schemas/*.schema.json`
  - 核心对象、Event Envelope payload、sync、blob/media、push、identity、moderation、Agent Authority、MIMI interop 的 JSON Schema。
- `artifacts/openapi/contrix-service-api.openapi.yaml`
  - HTTP/JSON binding shape；与 operation registry 对齐，不构成第二套 operation namespace。
- `artifacts/bindings/non-http-bindings.yaml`
  - gRPC / WS / SSE / MQ / libp2p 等 v1.1+ extension binding 概要。
- `artifacts/fixtures/*.json`
  - 一致性测试向量（encoding、crypto signature、Event Envelope 负向、state resolution、capability、sync、privacy/security、federation、MIMI 等）。

### 1.2 生成视图（Generated）

以下文件由 `contract-catalog.json` 派生，**不得直接手工编辑**：

- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/operation-registry.json`

派生关系由 `contract-catalog.json#generated_registries` 声明；任何 drift 会在 `python tools/artifact_pipeline.py check` 中阻塞 CI。

## 2. 维护与校验流水线

```bash
python tools/artifact_pipeline.py generate   # 重新生成派生 registry view
python tools/artifact_pipeline.py check      # 对照 catalog 检查派生视图 + 调用 lint_artifacts.py
```

`generate` 重写 `1.2` 中列出的派生文件。`check` 对每个派生文件做精确字符串对比，
然后调用 `tools/lint_artifacts.py`。lint 的覆盖范围：

- 注册表内部交叉引用一致性（event_kind ↔ schema、operation ↔ surface group ↔ profile 等）
- registry-manifest 与实际 `registry/` 文件清单一致
- `artifacts/`、`zh/` 下 Markdown 链接与 schema `$ref` 路径完整性
- OpenAPI 文档形状（必填字段、稳定 operationId 命名等）
- 选定完整对象示例的 schema required-field drift（见 `lint_artifacts.py::FULL_MARKDOWN_EXAMPLE_SCHEMAS`）

## 3. CI 要求

`.github/workflows/artifact-lint.yml` 在 PR 上以同一入口执行 `generate --check` 与 lint，
保证仓库内协议契约与机器视图一致。
