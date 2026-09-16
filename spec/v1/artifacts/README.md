---
title: Artifacts
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

`artifacts/` 存放 Arkret 的机器可读协议契约（machine-readable contract）。

## 1. 约定与分层

### 1.1 真实来源（Canonical）

- `artifacts/registry/contract-registry.json`
  - 事件 kind、schema、typed-ID 与 operation 的源定义。
- `artifacts/registry/error-code-registry.json`
  - 错误码体系。
  - Realm fixed reducer semantics、共识语义范围、支持的 authority-ordered projection、conformance vector group 与显式 upgrade edge。
- `artifacts/registry/registry-manifest.json`
  - `artifacts/registry/` 下所有机器注册表索引。
- `artifacts/profiles/conformance-profiles.json`
  - 实现 / 部署 / 向量 / hardening profile 矩阵。
- `artifacts/schemas/*.schema.json`
  - 核心对象、Event Envelope payload、sync、blob/media、push、identity、moderation、MIMI interop 的 JSON Schema。
- `artifacts/openapi/arkret-service-api.openapi.yaml`
  - HTTP/JSON binding shape；与 operation registry 对齐，不构成第二套 operation namespace。
- `artifacts/bindings/non-http-bindings.yaml`
  - gRPC / WS / SSE / MQ / libp2p 等 binding extension profile 概要。
- `artifacts/fixtures/*.json`
  - 一致性测试向量（encoding、crypto signature、Event Envelope 负向、authority-commit/authority-ordered projection、capability、sync、privacy/security、federation、MIMI 等）。
- `artifacts/deployment-probes.json`
  - 部署层机器探针，覆盖 TLS 握手、运维 posture 等不属于 object-model conformance vector 的可验收要求。
- `artifacts/reports/*`
  - **协议契约派生报告**（如 `operation-schema-index.json`、`operation-completeness-report.json`、`fixture-digests.json`，头部带 `source_of_truth: false` + `generated_from` / `generated_by`，是从 `contract-registry.json` 等契约真源派生的生成视图）。不作为协议规范来源，随契约真源由 pipeline 重生成。

### 1.2 生成视图（Generated）

以下文件由 `contract-registry.json` 派生，**不得直接手工编辑**：

- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/operation-registry.json`

派生关系由 `contract-registry.json#derived_registry_views` 声明；任何 drift 会在 `python tools/artifact_pipeline.py check` 中阻塞 CI。

### 1.3 同源生成 / 手工同步矩阵（normative）

`event-payload.schema.json`、`event-envelope.schema.json`、`event-kind-registry.json`、`contract-registry.json` 与 `schema-registry.md` 必须保持单一真源对齐，具体责任划分如下：

| Artifact | 角色 | 真源 / 同步方式 |
| --- | --- | --- |
| `artifacts/registry/contract-registry.json` | canonical | event kind / schema / typed-ID / operation 的唯一源定义（`source_of_truth: true`）。 |
| `artifacts/registry/event-kind-registry.json` | generated | 由 `contract-registry.json#event_kind_registry` 经 `artifact_pipeline.py generate` 派生；不得手工编辑。 |
| `artifacts/registry/schema-registry.json` | generated | 由 `contract-registry.json#schema_registry` 派生；schema_id → 文件位置的机器视图。 |
| `artifacts/schemas/event-payload.schema.json` | canonical | 手工撰写的 JSON Schema（payload class 与各 `$defs/*_payload`）。新增 payload class 时必须同时在 `contract-registry.json` 注册对应 `event_kind` + `schema_id`，使派生 registry 与 schema 文件互相覆盖。 |
| `artifacts/schemas/event-envelope.schema.json` | canonical | 手工撰写的 Event Envelope JSON Schema；其 payload 取值空间通过 `event-kind-registry.json` 与 payload schema 的 `$defs` 闭合，而非在 envelope 内重复枚举。 |
| `zh/conformance/schema-registry.md` | prose 镜像 | 是 `schema-registry.json` 的人类可读叙述视图；二者必须一致。`tools/artifact_pipeline.py check` + `tools/artifact_lint` 对 schema_id 集合、文件路径与 `$ref` 完整性做交叉校验，drift 阻塞 CI。 |

判定规则：

- canonical artifact（schemas / contract-registry）是手工真源；generated registry view 必须由 pipeline 重生成，绝不手工补丁。
- 新增或修改某 `ak.*` event kind 时，`contract-registry.json`、对应 payload schema `$defs`、由此派生的 `event-kind-registry.json` / `schema-registry.json` 与 `schema-registry.md` 必须在同一变更内一致更新；只改其一即视为 drift。
- 每个 active 标准 Event kind **MUST** 在 `contract-registry.json` 中显式声明唯一 `payload_schema_ref`，且该引用 **MUST** 与 `event-envelope.schema.json` 对该 kind 的唯一 payload dispatch 完全一致并解析到现存 schema 位置。消费方 **MUST NOT** 从 kind 拼写、schema 命名约定或通用 fallback 推断 payload schema；缺失、悬空、重复或分叉的绑定必须 fail closed。
- 任意一处的 schema_id / event_kind / typed-ID 出现而其余真源缺失，`artifact_pipeline.py check` 与 `artifact_lint` 会拦截。

## 2. 维护与校验流水线

```bash
python tools/artifact_pipeline.py generate   # 重新生成派生 registry view
python tools/regenerate_fixture_digests.py   # 从 canonical input 单向重算 SHA-256 KAT
python -m tools.artifact_lint                # 单独运行跨构件 lint
python tools/artifact_pipeline.py check      # 对照 catalog 检查派生视图 + 调用 artifact_lint
```

`generate` 重写 `1.2` 中列出的派生文件。`check` 对每个派生文件做精确字符串对比，
然后调用 `python -m tools.artifact_lint`。lint 的覆盖范围：

- 注册表内部交叉引用一致性（event_kind ↔ schema、operation ↔ surface group ↔ profile 等）
- registry-manifest 与实际 `registry/` 文件清单一致
- `artifacts/`、`zh/` 下 Markdown 链接与 schema `$ref` 路径完整性
- OpenAPI 文档形状（必填字段、稳定 operationId 命名等）
- `ServiceDescribe.required` 在 OpenAPI 与 `service-describe.schema.json` 之间保持一致，且所有 describe path 返回 `ServiceDescribe`
- registry / artifact 文本中的 `zh/<path>.md`、`schemas/*.json` 与 `artifacts/<path>` 引用必须存在
- active Event.kind 不得写成 `.vN` 版本化名称；core 文档不得残留旧 Room-scope 术语；硬编码 operation count 与占位章节号会被拦截
- 选定完整对象示例的 schema required-field drift（见 `tools/artifact_lint/core.py::FULL_MARKDOWN_EXAMPLE_SCHEMAS`）
- Markdown fenced JSON 可以用 ````json schema=schemas/<name>.schema.json` 声明 schema；lint 会对该 JSON 块运行 JSON Schema validation
- `artifacts/fixtures/*.json` 可声明 `schema_validation_cases[]`，对 EventEnvelope、RealmCommit、Cursor、Invite、ServiceDescribe 等核心对象执行正/负 schema validation
- fixture 中的 canonical input、canonical bytes、digest 与 signature MUST 由上述参考脚本单向重算并由 lint 比对；不得手工维护互不闭合的 input / expected bytes / digest / signature，也不得只在 prose 中声明不可复算值。
- 只验证 JSON Schema 形态、而不验证密码学 transcript 的 fixture MUST 声明 `fixture_kind="schema_only"`，并在 description 中明确占位 nonce / ciphertext / signature 不构成 cryptographic conformance vector。`fixture_kind="schema_only"` 的占位值不得被 release 文案宣传为真实加密、签名或 digest 向量。

### 2.1 JSON Schema 校验边界

JSON Schema 只验证 wire object 的结构层。一个标准 Event 只有在同时通过 Event Envelope schema、event-kind registry、active profile requirements、payload class、capability resolution、reducer precondition/projection 和 RealmCommit/authority-ordered projection state 校验后，才能被实现当作协议有效。实现 MUST NOT 把单独的 `schemas/*.schema.json` 通过结果当作 security-sensitive event 的接受条件；schema-only validator 只能用于早期格式拒绝和开发期诊断。

## 3. CI 要求

`.github/workflows/artifact-lint.yml` 在 PR 上以同一入口执行 `generate --check` 与 lint，
保证仓库内协议契约与机器视图一致。任何 PR 修改 `contract-registry.json`、schemas、fixtures、OpenAPI、profile 或 conformance vector 时，`python tools/artifact_pipeline.py check` 与 `node site/scripts/crossref-check.mjs` 都是发布门禁；不得以手工更新 generated registry 替代 pipeline。

### 3.1 下游同步约定（normative）

下游仓库（SDK、soland、cotest 等）从本仓 artifact 同步时，MUST 保持与 §1.3 同源真源一致的 payload shape 与 typed current result state metadata：

- 同步的真源是 `artifacts/` 下的 canonical schemas + `contract-registry.json` 及其派生 registry view；下游不得引入自己的第二套 event kind / schema namespace。
- **禁止生成 `round*.rs` 一类“轮次文件”**：下游不得把每一次 spec 同步落成 `round1.rs` / `round2.rs` / `round_*.rs` 之类按导入轮次累加的文件。同步必须收敛为按对象 / 模块组织的稳定生成产物（每个 schema 或 registry 对应一个稳定命名的生成单元），使重复同步是幂等替换而非追加。
- typed current result state metadata（`event-kind-registry.json` 的 `execution`、`domain reducer`、`value_shape`、`result_family`、`result_selector`）是 reducer 行为的真源；下游 reducer 必须从该 registry 读取，不得在代码里另行硬编码与 registry 漂移的取值。
