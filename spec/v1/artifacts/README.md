---
title: Artifacts
status: candidate
normative: true
stability: v1
updated: 2026-05-25
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
  - 核心对象、Event Envelope payload、sync、blob/media、push、identity、moderation、MIMI interop 的 JSON Schema。
- `artifacts/openapi/contrix-service-api.openapi.yaml`
  - HTTP/JSON binding shape；与 operation registry 对齐，不构成第二套 operation namespace。
- `artifacts/bindings/non-http-bindings.yaml`
  - gRPC / WS / SSE / MQ / libp2p 等 binding extension profile 概要。
- `artifacts/fixtures/*.json`
  - 一致性测试向量（encoding、crypto signature、Event Envelope 负向、Move/Anchor/Lattice、capability、sync、privacy/security、federation、MIMI 等）。
- `artifacts/reports/*`
  - 具体实现的本地 / CI conformance baseline 报告；不作为协议规范来源，但用于发布前审计和实现成熟度追踪。

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
- `ServiceDescribe.required` 在 OpenAPI 与 `service-describe.schema.json` 之间保持一致，且所有 describe path 返回 `ServiceDescribe`
- registry / artifact 文本中的 `zh/<path>.md`、`schemas/*.json` 与 `artifacts/<path>` 引用必须存在
- active Event.kind 不得写成 `.vN` 版本化名称；core 文档不得残留旧 Room-scope 术语；硬编码 operation count 与占位章节号会被拦截
- 选定完整对象示例的 schema required-field drift（见 `lint_artifacts.py::FULL_MARKDOWN_EXAMPLE_SCHEMAS`）
- Markdown fenced JSON 可以用 ````json schema=schemas/<name>.schema.json` 声明 schema；lint 会对该 JSON 块运行 JSON Schema validation
- `artifacts/fixtures/*.json` 可声明 `schema_validation_cases[]`，对 EventEnvelope、Anchor、Cursor、Invite、ServiceDescribe 等核心对象执行正/负 schema validation
- fixture 中若包含规范正文硬编码 digest（canonical bytes hash、event_digest、range completeness root、governance binding hash 等），CI SHOULD 通过参考实现脚本重算并比对；新增 vector 不得只在 prose 中声明 digest 而无可复算来源。

### 2.1 JSON Schema 校验边界

JSON Schema 只验证 wire object 的结构层。一个标准 Event 只有在同时通过 Event Envelope schema、event-kind registry、active profile requirements、payload class、capability resolution、reducer precondition/effect 和 Anchor/Lattice state 校验后，才能被实现当作协议有效。实现 MUST NOT 把单独的 `schemas/*.schema.json` 通过结果当作 security-sensitive event 的接受条件；schema-only validator 只能用于早期格式拒绝和开发期诊断。

## 3. CI 要求

`.github/workflows/artifact-lint.yml` 在 PR 上以同一入口执行 `generate --check` 与 lint，
保证仓库内协议契约与机器视图一致。任何 PR 修改 `contract-catalog.json`、schemas、fixtures、OpenAPI、profile 或 conformance vector 时，`python tools/artifact_pipeline.py check` 与 `node site/scripts/crossref-check.mjs` 都是发布门禁；不得以手工更新 generated registry 替代 pipeline。
