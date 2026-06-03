---
title: 实现就绪与发布门槛
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Contrix v1 的当前发布基线、机器工件覆盖范围、实现不变量与稳定发布门槛。

## 2. 当前发布基线

实现者应从机器工件与中文规范读取同一套协议事实模型：

- 唯一共享 wire fact 是 Event Envelope
- reducer、frontier、snapshot、sync、federation 和 fixture 以 `event_id` / actor frontier 为语义单位
- `operation_id` 仅表示服务 canonical operation 或 SDK 内部幂等标识
- 标准 Event kind、服务 operation、schema id、typed ID prefix 均有机器 registry
- OpenAPI、非 HTTP binding、fixture 与中文规范均可回指这些 registry

当前仓库维护单一 `v1.0.0` 规范线（`v1.0.0` 是仓库发布 / release tag；它与 wire-level `protocol_version` 字段值 `"1.0"` 是不同维度，见 [`index.md` §5](../index.md)，两者 MUST NOT 互换）：`spec/v1/artifacts/` 与 `spec/v1/zh/` 必须同时通过 `python tools/artifact_pipeline.py check`（registry drift 检查 + public catalog snapshot hash/count gate + fixture digest gate + `tools/lint_artifacts.py` 注册表交叉引用 / Markdown 链接 / OpenAPI 形状 lint），核心 profile、schema、fixture、OpenAPI 与中文规范共同构成正式 v1 发布契约。仓库不同时维护 rc / stable 两套 public catalog；任何更新都只落在当前 v1 canonical catalog 与唯一 public v1 snapshot 上。

`v1.0.0` 基线下，机器 registry 的当前覆盖范围由下表索引。**计数列由 `tools/lint_artifacts.py`（`check_release_readiness_counts`）对照各 Canonical registry 自动校验**：本表数字与 registry 不一致即为 drift，`artifact_pipeline.py check` 会失败，必须在合并前修复。引用本节时仍 MUST 以各 Canonical 文件为权威来源；本表是受 CI 校验的镜像快照，不得改为自由近似值（曾出现把计数写成 `~N` 导致校验器无法解析的回归）。

| Registry | 计数（CI 校验，与 registry 精确一致） | Canonical 文件 |
| --- | --- | --- |
| Event kind（active） | 168 | `artifacts/registry/event-kind-registry.json` |
| Schema | 60 | `artifacts/registry/schema-registry.json` |
| Typed ID kind | 44 | `artifacts/registry/id-kind-registry.json` |
| Service operation | 101 | `artifacts/registry/operation-registry.json` |
| Claimable conformance profile | 68 | `artifacts/profiles/conformance-profiles.json` |
| Profile id references | 89 | `artifacts/profiles/conformance-profiles.json` |

上表的 `Schema` 是 **registered schema id** 计数。`artifacts/schemas/` 下的 raw JSON Schema artifact file 数（快照约 60）以 `schema-registry.json` 与目录实际内容为准，由 `artifact_pipeline.py check` 校验；其中 `cx.schema.event.v1` 直接登记到 `event-envelope.schema.json`（schema body 所在文件）。发布站点仍然 MUST raw 发布 registry 声明的 JSON Schema 文件及其同目录 `$ref` 目标，registry consumer 也必须递归解析同目录 `$ref`，MUST NOT 只下载 registry 直接列出的文件后停止。

当前候选基线包含两个 wire-breaking cleanup：`cx.schema.handle_claim.v1.claim_kind` 不再允许 draft-era `service_handle`（服务 / 资源可读名必须迁移到独立服务 / 资源 schema；组织分配给用户或 principal 的 handle 使用 `organization_handle`），并且 `cx.member.identity.update` payload 中旧草案字段 `identity_state_digest` 已更名为 `identity_payload_digest`，以避免与 roster `member_display_state_digest` 混淆。实现者 MUST NOT 同时接受旧名和新名作为等价字段，除非在本地迁移层先把旧草案数据正规化后再进入 v1 validator。

`conformance-profiles.json` 另含一组 `profile_requirements` block（快照约 78）与 `profile_tiers` 分组（快照约 4）；权威计数以该文件为准并由 pipeline 校验，这些矩阵必须与上表中的 claimable profile 集合保持一致。`Profile id references` 是整个 registry graph 内出现的 `cx.profile.*` 字符串去重数，用于交叉引用检查，不等同于实现可直接声明的顶层 profile 数。

> `python tools/artifact_pipeline.py check` 输出按实现 / 部署 / vector / hardening 四类 profile 直接汇总 claimable profile；`tools/lint_artifacts.py` 同时校验 registry graph 中所有 `cx.profile.*` 引用，防止 profile requirement、继承或候选 profile 文本漂移。

执行 `python tools/artifact_pipeline.py check` 时，CLI 输出与上表必须一致；任何不一致都说明
canonical catalog 或派生工件出现 drift，必须在合并前修复。每次新增或退役 registry 项，MUST 同时
按 `CHANGELOG.md` "extension profile 变更登记模板" 记录条目；上表计数为生成快照，可在 drift 暴露后刷新，但其权威性始终以 Canonical 文件与 `artifact_pipeline.py check` 输出为准。

规范稳定不等于任一实现已经获得完全互操作认证。当前仓库的本地工具只提供 artifact / schema / registry / fixture digest 发布门禁；reference validator、reference reducer、reference authz evaluator 与 conformance runner 尚未作为完整认证工具链发布。实现若宣称通过某个 profile，仍必须通过对应 reference validator、reference reducer、reference authz evaluator 与 conformance runner；这些工具和测试结果属于实现认证门槛，而不是降低或替代本规范的 wire contract。

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
| 唯一事实 envelope | `zh/sync/operations-sync.md`, `artifacts/schemas/event-envelope.schema.json`, `artifacts/schemas/event-payload.schema.json` | Event Envelope 是唯一共享 wire fact；Operation 只用于服务 operation 或 SDK 内部构造路径。 |
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

- 标准 `cx.*` Event kind 必须出现在 `event-kind-registry.json`，MUST NOT 只写在 Markdown 中
- Event Envelope 必须先验证 envelope schema，再验证 kind-selected payload schema，最后才进入 auth / reducer
- Snapshot 签名不能单独证明无遗漏；实现必须校验 `event_set_commitment`
- Sync、Directory、Blob、Push、Moderation、Agent 和受托 search / projection 等服务 MUST NOT 绕过 capability、Realm policy、history visibility、plaintext-visible service 或 E2EE 边界
- 未知 non-critical 字段必须在 canonical bytes、存储、转发和 backfill 中保留
- 未知 critical extension 必须 fail closed

## 5. 发布门槛

### 5.1 `v1.0.0` stable promotion gate

- `zh/` 与 `artifacts/` registry lint 通过
- `core_event_store`、`chat_mvp`、`kanban_mvp` 的 schema、fixture、profile 已冻结；若 accepted proposal 改动这些 surface，必须在 freeze 前同步 schema / fixture / profile / vector，而不是只更新 prose
- OpenAPI MUST NOT 包含未发布生成器报告、占位 body 说明或 operation-level 非法字段
- fixture 与 Markdown JSON 示例 MUST NOT 使用非 active wire 字段、未注册 Event kind 或任何 schema-invalid wire shape。所有标记为正向的 fixture / vector MUST 先通过本地 JSON Schema resolver 校验；负向 fixture MUST 先满足基础 envelope shape，并在声明的目标错误处失败，MUST NOT 被更早的 schema 错误掩盖。
- 站点构建产物与线上 `$id` URL MUST 以 raw JSON 发布所有 registry 声明的 JSON Schema artifact，Content-Type SHOULD 为 `application/schema+json`，至少为 `application/json`；MUST NOT 让 schema `$id` 解析到 HTML 文档。
- Public catalog snapshot MUST 与发布说明中的语义一致：`site/src/lib/site-meta.ts#specReleaseTag` 指向当前 `v1.0.0`；仓库只保留 `site/public/v1/contract-catalog-1.0.0.json` 这一个当前 v1 snapshot，并由 `python tools/artifact_pipeline.py check` 的 hash/count/Circle-presence gate 校验它与 `artifacts/registry/contract-catalog.json` byte-identical。
- CXP-0007 stable gate MUST 闭合 `effective_scope` submit-input / reducer-output schema 角色、Message / Anchor output shape、Anchor leaf canonical bytes、`content_encryption_floor` 机器契约、`confidential_discussion_of` Relation 契约，以及 Circle/effective-scope conformance vector cluster；否则 release notes 必须明确 de-scope，且 MUST NOT 把这些项当作 v1.0 wire contract 宣布。
- 英文 mirror 完成前，`/en/v1/...` fallback 页面 MUST NOT 作为英文 normative 文本发布；权威 prose 仍是 `spec/v1/zh/`。
- 站点生产依赖 MUST NOT 存在未处理的 high / moderate `npm audit` finding；如需例外，必须在 release-readiness report 中记录影响面与补偿措施。

### 5.2 `v1-interop-preview` 实现互操作预览

- 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量
- 能重放官方 sync / state / capability fixture

### 5.3 `v1-conformance-certified` 实现认证

- reference validator、reference reducer、reference authz evaluator 与 conformance runner 已发布
- canonical JSON、Event Envelope negative vectors、Move/Anchor/Lattice、capability、privacy/security、sync 与 snapshot vectors 由 CI 执行
- 公开发布的翻译与附属文档 MUST NOT 偏离同一 registry 与 fixture 基线

## 6. 工程交付要求

- 为实现认证提供官方 reference validator / reducer / authz 包
- 用 CI 自动校验 Markdown 示例、OpenAPI、registry、schema 与 fixture 一致性
- 从 OpenAPI / JSON Schema 生成 SDK 类型与 contract tests
- 对宽泛 payload schema 提供 reference validator 中的语义校验，MUST NOT 只凭 JSON Schema 宣称完全互操作
