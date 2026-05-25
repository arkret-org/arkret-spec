---
title: 实现就绪与发布门槛
status: candidate
normative: false
stability: v1
updated: 2026-05-25
---

## 1. 目标

本文定义 Contrix v1 的当前发布基线、机器工件覆盖范围、实现不变量与稳定发布门槛。

## 2. 当前发布基线

实现者应从机器工件与中文规范读取同一套协议事实模型：

- 唯一共享 wire fact 是 Event Envelope
- reducer、frontier、snapshot、sync、federation 和 fixture 以 `event_id` / actor frontier 为语义单位
- `operation_id` 仅表示服务 canonical operation 或 SDK 内部幂等标识
- 标准 Event kind、服务 operation、schema id、typed ID prefix 均有机器 registry
- OpenAPI、非 HTTP binding、fixture 与中文规范均可回指这些 registry

当前仓库处于 `v1.0.0` stable promotion 候选状态：`spec/v1/artifacts/` 与 `spec/v1/zh/` 必须同时通过 `python tools/artifact_pipeline.py check`（registry drift 检查 + `tools/lint_artifacts.py` 注册表交叉引用 / Markdown 链接 / OpenAPI 形状 lint），核心 profile、schema、fixture、OpenAPI 与中文规范共同构成正式发布契约。CXP-0007 机器契约、版本化 public catalog 快照、站点依赖审计与远端 CI 证据关闭前，不得把当前 HEAD 描述为已发布的 stable 包；历史候选标签也不得用于描述当前正式发布包。

`v1.0.0` 基线下，机器 registry 的当前覆盖范围为：

| Registry | 计数 | Canonical 文件 |
| --- | --- | --- |
| Event kind（active） | 159 | `artifacts/registry/event-kind-registry.json` |
| Schema | 54 | `artifacts/registry/schema-registry.json` |
| Typed ID kind | 41 | `artifacts/registry/id-kind-registry.json` |
| Service operation | 87 | `artifacts/registry/operation-registry.json` |
| Claimable conformance profile | 58 | `artifacts/profiles/conformance-profiles.json` |
| Profile id references | 79 | `artifacts/profiles/conformance-profiles.json` |

上表的 `Schema` 是 **registered schema id** 计数。`artifacts/schemas/` 当前另有 54 个 raw JSON Schema artifact file；其中 `event-schema.json` 是 `cx.schema.event.v1` 的 internal `$ref` target，由已注册的 `event-envelope.schema.json` 引入。发布站点仍然 MUST raw 发布这些同目录 `$ref` 目标文件，registry consumer 也必须递归解析同目录 `$ref`，不能只下载 registry 直接列出的文件后停止。

当前 `conformance-profiles.json` 另含 68 个 `profile_requirements` block 与 4 个 `profile_tiers` 分组；这些矩阵必须与上表中的 claimable profile 集合保持一致。`Profile id references` 是整个 registry graph 内出现的 `cx.profile.*` 字符串去重数，用于交叉引用检查，不等同于实现可直接声明的顶层 profile 数。

> `python tools/artifact_pipeline.py check` 输出按实现 / 部署 / vector / hardening 四类 profile 直接汇总 claimable profile；`tools/lint_artifacts.py` 同时校验 registry graph 中所有 `cx.profile.*` 引用，防止 profile requirement、继承或候选 profile 文本漂移。

执行 `python tools/artifact_pipeline.py check` 时，CLI 输出与上表必须一致；任何不一致都说明
canonical catalog 或派生工件出现 drift，必须在合并前修复。每次新增或退役 registry 项，MUST 同时
按 `CHANGELOG.md` "extension profile 变更登记模板" 记录条目并更新本表。

规范稳定不等于任一实现已经获得完全互操作认证。实现若宣称通过某个 profile，仍必须通过对应 reference validator、reference reducer、reference authz evaluator 与 conformance runner；这些工具和测试结果属于实现认证门槛，而不是降低或替代本规范的 wire contract。

## 2.1 最小实现路径

实现者不需要一次实现全部 v1 surface。推荐按以下 profile 递进，每一阶段只声明自己实际支持的 profile、event kind、schema 和服务 operation：

| 阶段 | 必须实现 | 可暂缓 |
| --- | --- | --- |
| `core_event_store` | Event Envelope 验证、canonical JSON / proof、`cx.realm.create`、`cx.member.state`、events submit/get/list/frontier、backfill。 | Flow UI、View projection、MLS、federation、blob、push、agent。 |
| `chat_mvp` | Flow discussion track、Message create/revise/redact、reaction、redaction、client sync、history visibility、基础 capability check。 | Board/List、advanced View renderer、MIMI、auditable E2EE、agent runtime。 |
| `kanban_mvp` | Flow create/update/move/reorder、Relation create、container rebalance、View collection projection、rank conflict handling。 | Discussion track、message timeline、E2EE、push、federation。 |
| `full_client` | chat + kanban、blob/media、account-private data、read cursor、notification projection、offline queue 和 conflict records。 | Enterprise governance、MIMI、agent interop、高安全 witness。 |
| `e2ee_client` | MLS KeyPackage lifecycle、proposal/commit/welcome/epoch、decryption_pending、encrypted payload、key withholding/share audit。 | `mls_governance_binding.full`、minimal-metadata、auditable E2EE 和 MIMI E2EE interop。 |

任何服务或客户端若只实现上表前几阶段，MUST 在 describe / profile discovery 中明确声明不支持的 event kind 和 optional extension，并按 `unsupported_feature`、`unsupported_event_kind`、`projection_incomplete` 或 fail-closed 语义处理，而不是接受后静默丢弃。

## 3. 工件矩阵

| 主题 | 对应工件 | 当前要求 |
| --- | --- | --- |
| 唯一事实 envelope | `zh/sync/operations-sync.md`, `artifacts/schemas/event-schema.json`, `artifacts/schemas/event-payload.schema.json` | Event Envelope 是唯一共享 wire fact；Operation 只用于服务 operation 或 SDK 内部构造路径。 |
| Event kind 与 payload | `artifacts/registry/event-kind-registry.json`, `artifacts/schemas/event-payload.schema.json` | active 标准 kind 必须选择对应 payload class，失败即 `schema_violation`。 |
| 服务 operation 映射 | `artifacts/registry/contract-catalog.json`, `artifacts/registry/operation-registry.json`, `artifacts/openapi/contrix-service-api.openapi.yaml`, `artifacts/bindings/non-http-bindings.yaml` | `contract-catalog.json#operation_registry` 是 operation 的 canonical source。 |
| Schema registry | `artifacts/registry/schema-registry.json`, `zh/conformance/schema-registry.md` | 对象、Event、snapshot、moderation、MIMI 等 schema 已注册。 |
| Typed ID prefix | `artifacts/registry/id-kind-registry.json` | 标准 `cx:<kind>:` prefix 以机器注册表为准。 |
| Profile 矩阵 | `zh/conformance/conformance-profiles.md`, `artifacts/profiles/conformance-profiles.json` | `core_event_store`、`chat_mvp`、`kanban_mvp` 与客户端/服务角色可独立声明。 |
| Conformance vectors | `artifacts/fixtures/*.json` | encoding、crypto、Move/Anchor/Lattice、redaction、capability、sync、privacy/security、federation、MIMI 均有机器 fixture 入口。 |
| Snapshot 约束 | `artifacts/schemas/snapshot.schema.json`, `zh/conformance/snapshot-schema.md`, `zh/sync/operations-sync.md` | manifest 必须包含 `event_set_commitment`；高保障 profile 支持 inclusion / omission challenge。 |
| Moderation / abuse | `artifacts/schemas/moderation-report.schema.json`, `artifacts/schemas/moderation-queue-item.schema.json`, OpenAPI moderation endpoints | report、queue item、E2EE evidence / franking 边界有 schema 与服务绑定。 |
| Privacy / security | `artifacts/fixtures/privacy-security-fixture.json`, `artifacts/fixtures/membership-delivery-binding-fixture.json`, `zh/conformance/conformance-profiles.md` | hidden resource、private contact discovery、plaintext-visible service、private blob、blind push、membership delivery binding 有回归向量。 |

## 4. 必须保持的不变量

- 标准 `cx.*` Event kind 必须出现在 `event-kind-registry.json`，不得只写在 Markdown 中
- Event Envelope 必须先验证 envelope schema，再验证 kind-selected payload schema，最后才进入 auth / reducer
- Snapshot 签名不能单独证明无遗漏；实现必须校验 `event_set_commitment`
- Sync、Directory、Blob、Push、Moderation、Agent 和受托 search / projection 等服务不得绕过 capability、Realm policy、history visibility、plaintext-visible service 或 E2EE 边界
- 未知 non-critical 字段必须在 canonical bytes、存储、转发和 backfill 中保留
- 未知 critical extension 必须 fail closed

## 5. 发布门槛

### 5.1 `v1.0.0` stable promotion gate

- `zh/` 与 `artifacts/` registry lint 通过
- `core_event_store`、`chat_mvp`、`kanban_mvp` 的 schema、fixture、profile 已冻结；若 accepted proposal 改动这些 surface，必须在 freeze 前同步 schema / fixture / profile / vector，而不是只更新 prose
- OpenAPI 不得包含未发布生成器报告、占位 body 说明或 operation-level 非法字段
- fixture 与 Markdown JSON 示例不得使用非 active wire 字段、未注册 Event kind 或任何 schema-invalid wire shape。所有标记为正向的 fixture / vector MUST 先通过本地 JSON Schema resolver 校验；负向 fixture MUST 先满足基础 envelope shape，并在声明的目标错误处失败，不能被更早的 schema 错误掩盖。
- 站点构建产物与线上 `$id` URL MUST 以 raw JSON 发布所有 registry 声明的 JSON Schema artifact，Content-Type SHOULD 为 `application/schema+json`，至少为 `application/json`；不得让 schema `$id` 解析到 HTML 文档。
- 版本化 public catalog 快照 MUST 与发布说明中的语义一致：若 `contract-catalog-<version>.json` 是冻结 baseline，当前 release 必须发布新的 versioned snapshot；若同名快照代表当前 release，则必须由 CI 用 count/hash gate 证明它与 canonical catalog 一致。
- CXP-0007 stable gate MUST 闭合 `effective_scope` submit-input / reducer-output schema 角色、Message / Anchor output shape、Anchor leaf canonical bytes、`content_encryption_floor` 机器契约、`confidential_discussion_of` Relation 契约，以及 Circle/effective-scope conformance vector cluster；否则 release notes 必须明确 de-scope，且不得把这些项当作 v1.0 wire contract 宣布。
- 英文 mirror 完成前，`/en/v1/...` fallback 页面不得作为英文 normative 文本发布；权威 prose 仍是 `spec/v1/zh/`。
- 站点生产依赖不得存在未处理的 high / moderate `npm audit` finding；如需例外，必须在 release-readiness report 中记录影响面与补偿措施。

### 5.2 `v1-interop-preview` 实现互操作预览

- 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量
- 能重放官方 sync / state / capability fixture

### 5.3 `v1-conformance-certified` 实现认证

- reference validator、reference reducer、reference authz evaluator 与 conformance runner 已发布
- canonical JSON、Event Envelope negative vectors、Move/Anchor/Lattice、capability、privacy/security、sync 与 snapshot vectors 由 CI 执行
- 公开发布的翻译与附属文档不得偏离同一 registry 与 fixture 基线

## 6. 工程交付要求

- 为实现认证提供官方 reference validator / reducer / authz 包
- 用 CI 自动校验 Markdown 示例、OpenAPI、registry、schema 与 fixture 一致性
- 从 OpenAPI / JSON Schema 生成 SDK 类型与 contract tests
- 对宽泛 payload schema 提供 reference validator 中的语义校验，不能只凭 JSON Schema 宣称完全互操作
