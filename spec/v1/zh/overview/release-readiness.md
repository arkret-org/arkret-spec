---
title: 实现就绪与发布门槛
status: candidate
normative: true
stability: v1
updated: 2026-09-20
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret v1 的当前发布基线、机器工件覆盖范围、实现不变量与稳定发布门槛。

## 2. 当前发布基线

实现者应从机器工件与中文规范读取同一套协议事实模型：

- 唯一共享 wire fact 是 Event Envelope
- reducer、snapshot、sync、federation 和 fixture 以 `CommittedEventRef`、独立 authority stream 与 RealmCommit position 为语义单位
- `operation_id` 仅表示服务 canonical operation 或 SDK 内部幂等标识
- 标准 Event kind、服务 operation、schema id、typed ID prefix 均有机器 registry
- OpenAPI、非 HTTP binding、fixture 与中文规范均可回指这些 registry

当前仓库维护单一 candidate v1 规范线，尚未发布 `v1.0.0`（`v1.0.0` 仅是通过 promotion gate 后使用的 release tag；它与 wire-level `protocol_version` 字段值 `"1.0"` 是不同维度，见 [`index.md` §5](../index.md)，两者 MUST NOT 互换）。`spec/v1/artifacts/` 与 `spec/v1/zh/` 必须同时通过 `python tools/artifact_pipeline.py check`（registry drift 检查 + public catalog snapshot hash/count gate + fixture digest gate + `tools/artifact_lint/` 注册表交叉引用 / Markdown 链接 / OpenAPI 形状 lint），核心 profile、schema、fixture、OpenAPI 与中文规范才能共同晋升为正式 v1 发布契约。仓库不同时维护 candidate / stable 两套 public catalog；任何更新都只落在当前 v1 canonical catalog 与唯一 public v1 snapshot 上。

candidate v1 目标基线下，机器 registry 的当前覆盖范围由下表索引。**计数列由 `tools/artifact_lint/`（`check_release_readiness_counts`）对照各 Canonical registry 自动校验**：本表数字与 registry 不一致即为 drift，`artifact_pipeline.py check` 会失败，必须在合并前修复。引用本节时仍 MUST 以各 Canonical 文件为权威来源；本表是受 CI 校验的镜像快照，不得改为自由近似值，MUST NOT 写成 `~N` 等自由近似形态（否则 `check_release_readiness_counts` 无法解析）。

| Registry | 计数（CI 校验，与 registry 精确一致） | Canonical 文件 |
| --- | --- | --- |
| Event kind（active） | 144 | `artifacts/registry/event-kind-registry.json` |
| Schema | 222 | `artifacts/registry/schema-registry.json` |
| Typed ID kind | 50 | `artifacts/registry/id-kind-registry.json` |
| Service operation | 206 | `artifacts/registry/operation-registry.json` |
| Claimable conformance profile | 59 | `artifacts/profiles/conformance-profiles.json` |
| Profile id references | 78 | `artifacts/profiles/conformance-profiles.json` |

上表的 `Schema` 是 **registered schema id** 计数。`artifacts/schemas/` 下的 raw JSON Schema artifact file 数由 pipeline 单独核验；bundle schema id 可登记到现有 schema artifact 的 `$defs`，因此 registered schema id 数可大于 raw file 数。以 `schema-registry.json` 与目录实际内容为准，由 `artifact_pipeline.py check` 精确校验；其中 `ak.schema.event.v1` 直接登记到 `event-envelope.schema.json`（schema body所在文件，不另占独立文件）。发布站点仍然 MUST raw 发布 registry 声明的 JSON Schema 文件及其同目录 `$ref` 目标，registry consumer 也必须递归解析同目录 `$ref`，MUST NOT 只下载 registry 直接列出的文件后停止。

当前候选基线包含三项 wire 约束：(1) `ak.schema.handle_claim.v1.claim_kind` 的合法取值不含服务 / 资源可读名（服务 / 资源可读名使用独立的服务 / 资源 schema；组织分配给用户或 principal 的 handle 使用 `organization_handle`）；(2) `ak.member.identity.update` payload 不重复可从 `identity_payload` 本体推导的 carrier digest，roster cache 使用独立的 `member_display_state_digest`；(3) 直接 DID 邀请（`ak.schema.invite.v1` 中出现 `invitee_account_id` 且不属于 `third_party_invite` 分支）MUST 携带 exact `invitee_account_id` 与 `introduction_evidence_digest`，route material 仅在私有投递链路消费，不进入 durable Invite，使 base invite 不依赖 handle resolve 作为投递授权。current parser 只接受当前 registry/schema 中存在的 canonical 形态，不运行草案迁移层。

`conformance-profiles.json` 另含一组 `profile_requirements` block（78）与 `profile_sets` 分组（3）；这两个计数同样由 pipeline 精确校验（非自由近似值），权威计数以该文件为准，这些矩阵必须与上表中的 claimable profile 集合保持一致。`Profile id references` 是整个 registry graph 内出现的 `ak.profile.*` 字符串去重数，用于交叉引用检查，不等同于实现可直接声明的顶层 profile 数。

> `python tools/artifact_pipeline.py check` 输出按实现 / 部署 / hardening 三类 profile 汇总可声明（claimable）profile；`vector-group`（第 16 组）只用于组织测试向量，不是可声明 profile。`tools/artifact_lint/` 同时校验 registry graph 中所有 `ak.profile.*` 引用，防止 profile requirement、继承或候选 profile 文本漂移。

执行 `python tools/artifact_pipeline.py check` 时，CLI 输出与上表必须一致；任何不一致都说明 canonical catalog 或派生工件出现 drift，必须在合并前修复。每次新增或删除 registry 项，MUST 在同一变更中刷新本表。上表计数是 current-v1 canonical tree 的受检快照；其权威性以 canonical 文件与 pipeline 输出为准。有意合同修订若改变 operation closure，必须显式运行 `python tools/artifact_pipeline.py refresh-operation-closure-locks` 刷新 current candidate lock；普通 `generate` 不得静默覆盖 identity。

规范稳定不等于任一实现已经获得完全互操作认证。当前仓库的本地工具只提供 artifact / schema / registry / fixture digest 发布门禁；reference validator、reference reducer、reference authz evaluator 与 conformance runner 尚未作为完整认证工具链发布。实现若宣称通过某个 profile，仍必须通过对应 reference validator、reference reducer、reference authz evaluator 与 conformance runner；这些工具和测试结果属于实现认证门槛，而不是降低或替代本规范的 wire contract。

## 2.1 最小实现路径

实现者不需要一次实现全部 v1 surface。推荐按以下 profile 递进，每一阶段只声明自己实际支持的 profile、event kind、schema 和服务 operation。

> 下表「阶段」列使用 profile 短名（如 `core_event_store`、`full_client`），均为全限定 profile id `ak.profile.<name>.v1` 的简写（例如 `full_client` = `ak.profile.full_client.v1`）；wire / describe 声明 MUST 使用全限定 id。

| 阶段 | 必须实现 | 可暂缓 |
| --- | --- | --- |
| `core_event_store` | Event Envelope 验证、canonical JSON / proof、`ak.realm.create`、`ak.member.state`、events submit/get/list/checkpoint、backfill。 | Strand UI、View projection、MLS、federation、blob、push、agent。 |
| `chat_mvp` | Strand discussion track、Message create/revise/redact、reaction、redaction、client sync、history visibility、基础 capability check。 | Board/List、advanced View renderer、MIMI、auditable E2EE、agent runtime。 |
| `kanban_mvp` | Strand create/update/move/reorder、Relation create、container rebalance、View collection projection、rank conflict handling。 | Discussion track、message timeline、E2EE、push、federation。 |
| `full_client` | chat + kanban、blob/media、account-private data、read cursor、notification projection、offline queue 和 conflict records。 | Enterprise governance、MIMI、agent interop、高安全 witness。 |
| `e2ee_client` | MLS KeyPackage lifecycle、proposal/commit/welcome/epoch、decryption_pending、encrypted payload、key withholding/share audit。 | 固定 MLS GroupContext binding 和 MIMI E2EE interop。 |

任何服务或客户端若只实现上表前几阶段，MUST 在 describe / profile discovery 中明确声明不支持的 event kind 和 optional extension，并按 `unsupported_feature`、`unsupported_event_kind`、`projection_incomplete` 或 fail-closed 语义处理，而不是接受后静默丢弃。这些标准状态 / 错误标识的 canonical 语义详见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。

## 3. 工件矩阵

> 「对应工件」列同时列出规范正文与机读工件，权威性按领域划分而不是按扩展名划分：标识符集合、字段形状、operation binding 与 profile membership 以 registry / schema / `contract-registry.json` 为 canonical；状态机、授权、因果、失败恢复与安全语义以 `normative: true` 的中文正文为 canonical；生成的 catalog、站点视图与报告只作 informative 镜像。跨领域不一致必须阻断发布并修复两个来源，不得以“机器文件总是覆盖正文”掩盖语义冲突。

| 主题 | 对应工件 | 当前要求 |
| --- | --- | --- |
| 唯一事实 envelope | `zh/sync/operations-sync.md`, `artifacts/schemas/event-envelope.schema.json`, `artifacts/schemas/event-payload.schema.json` | Event Envelope 是唯一共享 wire fact；Operation 只用于服务 operation 或 SDK 内部构造路径。 |
| Event kind 与 payload | `artifacts/registry/event-kind-registry.json`, `artifacts/schemas/event-payload.schema.json` | active 标准 kind 必须选择对应 payload class，失败即 `schema_violation`。 |
| 服务 operation 映射 | `artifacts/registry/contract-registry.json`, `artifacts/registry/operation-registry.json`, `artifacts/reports/operation-schema-index.json`, `artifacts/openapi/arkret-service-api.openapi.yaml`, `artifacts/bindings/non-http-bindings.yaml` | `contract-registry.json#operation_registry` 是 operation 的 canonical source；`operation-schema-index.json` 是由 schema refs 生成的 DTO 字段集合索引。 |
| Schema registry | `artifacts/registry/schema-registry.json`, `zh/conformance/schema-registry.md` | 对象、Event、snapshot、moderation、MIMI 等 schema 已注册。 |
| Typed ID prefix | `artifacts/registry/id-kind-registry.json` | 标准 `ak:<kind>:` prefix 以机器注册表为准。 |
| Profile 矩阵 | `zh/conformance/conformance-profiles.md`, `artifacts/profiles/conformance-profiles.json` | `core_event_store`、`chat_mvp`、`kanban_mvp` 与客户端/服务角色可独立声明。 |
| Conformance vectors | `artifacts/fixtures/*.json` | encoding、crypto、authority-commit projection、redaction、capability、sync、privacy/security、federation、MIMI 均有机器 fixture 入口。 |
| Snapshot 约束 | `artifacts/schemas/realm-state-snapshot.schema.json`, `zh/conformance/realm-state-snapshot-schema.md`, `zh/sync/operations-sync.md` | snapshot 绑定 `governance_generation`、可见 stream heads 与 history floor，由当前治理 Station 签名；验证失败整份丢弃。 |
| Moderation / abuse | `artifacts/schemas/moderation-report.schema.json`, `artifacts/schemas/moderation-evidence.schema.json`, `artifacts/schemas/moderation-queue-item.schema.json`, OpenAPI moderation endpoints | signed report request、queue item、E2EE evidence / franking 边界有独立且无循环依赖的 schema 与服务绑定。 |
| Privacy / security | `artifacts/fixtures/privacy-security-fixture.json`, `artifacts/fixtures/fanout-route-miss-fixture.json`, `zh/conformance/conformance-profiles.md` | hidden resource、private contact discovery、plaintext-visible service、private blob、blind push、membership ActorId routing projection 有回归向量。 |

## 4. 必须保持的不变量

- 标准 `ak.*` Event kind 必须出现在 `event-kind-registry.json`，MUST NOT 只写在 Markdown 中
- Event Envelope 必须先验证 envelope schema，再验证 kind-selected payload schema，最后才进入 auth / reducer
- Snapshot 签名不能单独证明无遗漏；实现必须逐 stream 用同 stream tail 承接每个 `visible_stream_heads[]`
- Sync、Directory、Blob、Push、Moderation、Agent 和受托 search / projection 等服务 MUST NOT 绕过 capability、Realm policy、history visibility、plaintext-visible service 或 E2EE 边界
- canonical object schema 未声明的未知字段必须被 schema validation 拒绝；具体 schema 显式声明的 `x_*` 扩展槽中的未识别内容必须在 canonical bytes、存储、转发和 backfill 中保留；current-v1 不存在通用 `requirements` / `critical_extensions` carrier
- 未知 critical extension 必须 fail closed

## 5. 发布门槛

### 5.1 `v1.0.0` 目标 stable promotion gate

- `zh/` 与 `artifacts/` registry lint 通过
- 官方最小 reference validator、reducer、authz evaluator 与 conformance runner 已发布，并由发布 CI 实际执行 core behavioral vectors；仅校验 registry/schema/digest 不满足 stable promotion。
- `event-kind-vector-gap-registry.json` 中 `critical` 与 `high` 条目必须为零；`tools/release_gate.py` 在 release tag 切换为 `v1.0.0` 后机械阻断任何剩余 critical/high gap。`normal` backlog 可保留，但 release notes MUST 明确列出且不得把登记本身称为行为覆盖证据。
- 至少两个相互独立、共享代码不构成同一实现的实现必须通过同一 runner 的 `core_event_store`、sync/state/capability 与安全负向向量；结果必须以绑定实现 artifact digest、spec revision 与 contract digest 的签名 conformance claim 留档。
- `core_event_store`、`chat_mvp`、`kanban_mvp` 的 schema、fixture、profile 已冻结；若 accepted proposal 改动这些 surface，必须在 freeze 前同步 schema / fixture / profile / vector，而不是只更新 prose
- OpenAPI MUST NOT 包含未发布生成器报告、占位 body 说明或 operation-level 非法字段
- fixture 与 Markdown JSON 示例 MUST NOT 使用非 active wire 字段、未注册 Event kind 或任何 schema-invalid wire shape。所有标记为正向的 fixture / vector MUST 先通过本地 JSON Schema resolver 校验；负向 fixture MUST 先满足基础 envelope shape，并在声明的目标错误处失败，MUST NOT 被更早的 schema 错误掩盖。
- 站点构建产物与线上 `$id` URL MUST 以 raw JSON 发布所有 registry 声明的 JSON Schema artifact，Content-Type SHOULD 为 `application/schema+json`，至少为 `application/json`；MUST NOT 让 schema `$id` 解析到 HTML 文档。
- Public catalog snapshot MUST 与发布状态一致并受版本控制：`spec/v1/release-metadata.json#release_tag` 是规范工具、release gate、站点展示与 public snapshot 命名共同消费的唯一机器源，site-local TypeScript 不得复制其字面量。stable promotion 前该值固定为 `v1.0.0-candidate`，Git tree 中只允许 `site/public/v1/contract-registry-1.0.0-candidate.json`；`artifact_pipeline.py generate` 刷新它，`check` 校验唯一文件名、受跟踪实物及其与 `artifacts/registry/contract-registry.json` byte identity。promotion 只能在所有 gate 通过后原子切换 `release_tag` 为 `v1.0.0`、删除旧 candidate snapshot、生成并提交 `contract-registry-1.0.0.json`；release tag 直接绑定该 tracked 文件。
- Circle stable gate MUST 闭合签名 Event `scope_ref`、对象 `effective_scope` projection、Event / RealmCommit output shape、RealmCommit canonical bytes、MLS 激活不可逆机器契约、`confidential_discussion_of` Relation 契约，以及 Circle scope conformance vector cluster；否则 release notes 必须明确 de-scope，且 MUST NOT 把这些项当作 v1.0 wire contract 宣布。
- `/en/v1/...` 页面 MUST NOT 作为英文 normative 文本发布；权威 prose 仍是 `spec/v1/zh/`。除非未来另行接受新的语言政策提案，本规范不承诺提供完整英文版。
- 站点生产依赖 MUST NOT 存在未处理的 high / moderate `npm audit` finding；如需例外，必须在 release-readiness report 中记录影响面与补偿措施。
- current-v1 尚未发布；本仓的 canonical schema、registry、正文、fixture 与 SDK 必须在 promotion 前保持单一自洽合同，不维护替代合同或双解释路径。

### 5.2 `v1-interop-preview` 实现互操作预览

> **门槛依赖（normative）**：本 gate 与 §5.3 依赖 §6 的 reference validator / reducer / authz / conformance runner 交付；如 §2 所述这些工具**尚未**作为完整认证工具链发布。因此当前规范只能保持 candidate；§5.2 的双实现互操作证据与 §5.3 的可执行 runner 是 §5.1 stable promotion 的前置条件，工具或证据缺失时 MUST 阻断 `v1.0.0` tag。

- 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量
- 能重放官方 sync / state / capability fixture

### 5.3 `v1-conformance-certified` 实现认证

- reference validator、reference reducer、reference authz evaluator 与 conformance runner 已发布
- canonical JSON、Event Envelope negative vectors、authority-commit projection、capability、privacy/security、sync 与 snapshot vectors 由 CI 执行
- 公开发布的翻译与附属文档 MUST NOT 偏离同一 registry 与 fixture 基线

## 6. 工程交付要求

- 为实现认证提供官方 reference validator / reducer / authz 包
- 用 CI 自动校验 Markdown 示例、OpenAPI、registry、schema 与 fixture 一致性
- 从 OpenAPI / JSON Schema 生成 SDK 类型与 contract tests
- 对宽泛 payload schema 提供 reference validator 中的语义校验，MUST NOT 只凭 JSON Schema 宣称完全互操作
