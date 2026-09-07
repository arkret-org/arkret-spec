---
title: 实现就绪与发布门槛
status: candidate
normative: true
stability: v1
updated: 2026-08-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret v1 的当前发布基线、机器工件覆盖范围、实现不变量与稳定发布门槛。

## 2. 当前发布基线

实现者应从机器工件与中文规范读取同一套协议事实模型：

- 唯一共享 wire fact 是 Event Envelope
- reducer、frontier、snapshot、sync、federation 和 fixture 以 `event_id` / actor frontier 为语义单位
- `operation_id` 仅表示服务 canonical operation 或 SDK 内部幂等标识
- 标准 Event kind、服务 operation、schema id、typed ID prefix 均有机器 registry
- OpenAPI、非 HTTP binding、fixture 与中文规范均可回指这些 registry

当前仓库维护单一 candidate v1 规范线，尚未发布 `v1.0.0`（`v1.0.0` 仅是通过 promotion gate 后使用的 release tag；它与 wire-level `protocol_version` 字段值 `"1.0"` 是不同维度，见 [`index.md` §5](../index.md)，两者 MUST NOT 互换）。`spec/v1/artifacts/` 与 `spec/v1/zh/` 必须同时通过 `python tools/artifact_pipeline.py check`（registry drift 检查 + public catalog snapshot hash/count gate + fixture digest gate + `tools/artifact_lint/` 注册表交叉引用 / Markdown 链接 / OpenAPI 形状 lint），核心 profile、schema、fixture、OpenAPI 与中文规范才能共同晋升为正式 v1 发布契约。仓库不同时维护 candidate / stable 两套 public catalog；任何更新都只落在当前 v1 canonical catalog 与唯一 public v1 snapshot 上。

candidate v1 目标基线下，机器 registry 的当前覆盖范围由下表索引。**计数列由 `tools/artifact_lint/`（`check_release_readiness_counts`）对照各 Canonical registry 自动校验**：本表数字与 registry 不一致即为 drift，`artifact_pipeline.py check` 会失败，必须在合并前修复。引用本节时仍 MUST 以各 Canonical 文件为权威来源；本表是受 CI 校验的镜像快照，不得改为自由近似值，MUST NOT 写成 `~N` 等自由近似形态（否则 `check_release_readiness_counts` 无法解析）。

| Registry | 计数（CI 校验，与 registry 精确一致） | Canonical 文件 |
| --- | --- | --- |
| Event kind（active） | 170 | `artifacts/registry/event-kind-registry.json` |
| Schema | 205 | `artifacts/registry/schema-registry.json` |
| Typed ID kind | 58 | `artifacts/registry/id-kind-registry.json` |
| Service operation | 235 | `artifacts/registry/operation-registry.json` |
| Claimable conformance profile | 67 | `artifacts/profiles/conformance-profiles.json` |
| Profile id references | 96 | `artifacts/profiles/conformance-profiles.json` |

上表的 `Schema` 是 **registered schema id** 计数。`artifacts/schemas/` 下的 raw JSON Schema artifact file 数由 pipeline 单独核验；bundle schema id 可登记到现有 schema artifact 的 `$defs`，因此 registered schema id 数可大于 raw file 数。以 `schema-registry.json` 与目录实际内容为准，由 `artifact_pipeline.py check` 精确校验；其中 `ak.schema.event.v1` 直接登记到 `event-envelope.schema.json`（schema body所在文件，不另占独立文件）。发布站点仍然 MUST raw 发布 registry 声明的 JSON Schema 文件及其同目录 `$ref` 目标，registry consumer 也必须递归解析同目录 `$ref`，MUST NOT 只下载 registry 直接列出的文件后停止。

当前候选基线包含三项 wire 约束：(1) `ak.schema.handle_claim.v1.claim_kind` 的合法取值不含服务 / 资源可读名（服务 / 资源可读名使用独立的服务 / 资源 schema；组织分配给用户或 principal 的 handle 使用 `organization_handle`）；(2) `ak.member.identity.update` payload 不重复可从 `identity_payload` 本体推导的 carrier digest，roster cache 使用独立的 `member_display_state_digest`；(3) 直接 DID 邀请（`ak.schema.invite.v1` 中出现 `invitee_account_id` 且不属于 `third_party_invite` 分支）MUST 携带 exact `invitee_account_id` 与 `introduction_evidence_digest`，route material 仅在私有投递链路消费，不进入 durable Invite，使 base invite 不依赖 handle resolve 作为投递授权。current parser 只接受当前 registry/schema 中存在的 canonical 形态，不运行草案迁移层。

`conformance-profiles.json` 另含一组 `profile_requirements` block（96）与 `profile_sets` 分组（3）；这两个计数同样由 pipeline 精确校验（非自由近似值），权威计数以该文件为准，这些矩阵必须与上表中的 claimable profile 集合保持一致。`Profile id references` 是整个 registry graph 内出现的 `ak.profile.*` 字符串去重数，用于交叉引用检查，不等同于实现可直接声明的顶层 profile 数。

> `python tools/artifact_pipeline.py check` 输出按实现 / 部署 / hardening 三类 profile 汇总可声明（claimable）profile；`vector-group`（第 16 组）只用于组织测试向量，不是可声明 profile。`tools/artifact_lint/` 同时校验 registry graph 中所有 `ak.profile.*` 引用，防止 profile requirement、继承或候选 profile 文本漂移。

执行 `python tools/artifact_pipeline.py check` 时，CLI 输出与上表必须一致；任何不一致都说明 canonical catalog 或派生工件出现 drift，必须在合并前修复。每次新增或删除 registry 项，MUST 在同一变更中刷新本表。上表计数是当前 candidate v1 canonical tree 的受检快照；其权威性始终以 Canonical 文件与 `artifact_pipeline.py check` 输出为准。未发布阶段不维护历史迁移清单或兼容登记表；这种直接更新 current-v1 canonical 面、不保留 alias / 双读 / deprecated 行的姿态只适用于 `v1.0.0` promotion 之前。pre-GA 的有意合同修订若改变既有 operation / operation bundle closure，MUST 先由普通 `check` 暴露受影响 identity，再显式执行 `python tools/artifact_pipeline.py refresh-operation-closure-locks` 刷新当前 candidate lock；普通 `generate` 不得静默覆盖既有 identity。该刷新入口必须从 canonical `spec/v1/release-metadata.json#release_tag` 判定发布状态，并在 stable promotion 后机械拒绝执行。promotion 原子提交完成后，所有后继变更 MUST 服从 §5.1.1，不能继续援引本段或刷新 candidate lock 作为破坏已发布 wire contract 的许可。

规范稳定不等于任一实现已经获得完全互操作认证。当前仓库的本地工具只提供 artifact / schema / registry / fixture digest 发布门禁；reference validator、reference reducer、reference authz evaluator 与 conformance runner 尚未作为完整认证工具链发布。实现若宣称通过某个 profile，仍必须通过对应 reference validator、reference reducer、reference authz evaluator 与 conformance runner；这些工具和测试结果属于实现认证门槛，而不是降低或替代本规范的 wire contract。

## 2.1 最小实现路径

实现者不需要一次实现全部 v1 surface。推荐按以下 profile 递进，每一阶段只声明自己实际支持的 profile、event kind、schema 和服务 operation。

> 下表「阶段」列使用 profile 短名（如 `core_event_store`、`full_client`），均为全限定 profile id `ak.profile.<name>.v1` 的简写（例如 `full_client` = `ak.profile.full_client.v1`）；wire / describe 声明 MUST 使用全限定 id。

| 阶段 | 必须实现 | 可暂缓 |
| --- | --- | --- |
| `core_event_store` | Event Envelope 验证、canonical JSON / proof、`ak.realm.create`、`ak.member.state`、events submit/get/list/frontier、backfill。 | Strand UI、View projection、MLS、federation、blob、push、agent。 |
| `chat_mvp` | Strand discussion track、Message create/revise/redact、reaction、redaction、client sync、history visibility、基础 capability check。 | Board/List、advanced View renderer、MIMI、auditable E2EE、agent runtime。 |
| `kanban_mvp` | Strand create/update/move/reorder、Relation create、container rebalance、View collection projection、rank conflict handling。 | Discussion track、message timeline、E2EE、push、federation。 |
| `full_client` | chat + kanban、blob/media、account-private data、read cursor、notification projection、offline queue 和 conflict records。 | Enterprise governance、MIMI、agent interop、高安全 witness。 |
| `e2ee_client` | MLS KeyPackage lifecycle、proposal/commit/welcome/epoch、decryption_pending、encrypted payload、key withholding/share audit。 | `mls_governance_binding.full`、minimal-metadata、auditable E2EE 和 MIMI E2EE interop。 |

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
| Conformance vectors | `artifacts/fixtures/*.json` | encoding、crypto、CBS/Lattice、redaction、capability、sync、privacy/security、federation、MIMI 均有机器 fixture 入口。 |
| Snapshot 约束 | `artifacts/schemas/realm-state-snapshot.schema.json`, `zh/conformance/realm-state-snapshot-schema.md`, `zh/sync/operations-sync.md` | manifest 必须包含 `event_set_commitment`；高保障 profile 支持 inclusion / omission challenge。 |
| Moderation / abuse | `artifacts/schemas/moderation-report.schema.json`, `artifacts/schemas/moderation-evidence.schema.json`, `artifacts/schemas/moderation-queue-item.schema.json`, OpenAPI moderation endpoints | signed report request、queue item、E2EE evidence / franking 边界有独立且无循环依赖的 schema 与服务绑定。 |
| Privacy / security | `artifacts/fixtures/privacy-security-fixture.json`, `artifacts/fixtures/fanout-route-miss-fixture.json`, `zh/conformance/conformance-profiles.md` | hidden resource、private contact discovery、plaintext-visible service、private blob、blind push、membership ActorId routing projection 有回归向量。 |

## 4. 必须保持的不变量

- 标准 `ak.*` Event kind 必须出现在 `event-kind-registry.json`，MUST NOT 只写在 Markdown 中
- Event Envelope 必须先验证 envelope schema，再验证 kind-selected payload schema，最后才进入 auth / reducer
- Snapshot 签名不能单独证明无遗漏；实现必须校验 `event_set_commitment`
- Sync、Directory、Blob、Push、Moderation、Agent 和受托 search / projection 等服务 MUST NOT 绕过 capability、Realm policy、history visibility、plaintext-visible service 或 E2EE 边界
- canonical object schema 未声明的未知字段必须被 schema validation 拒绝；schema 显式声明扩展位（已登记的 `payload.x_*` 槽、`requirements.critical_extensions[].parameters`）中的未识别内容必须在 canonical bytes、存储、转发和 backfill 中保留
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
- Circle stable gate MUST 闭合签名 Event `scope_ref`、对象 `effective_scope` projection、DataEvent / Seal output shape、Seal canonical bytes、`content_encryption_floor` 机器契约、`confidential_discussion_of` Relation 契约，以及 Circle scope conformance vector cluster；否则 release notes 必须明确 de-scope，且 MUST NOT 把这些项当作 v1.0 wire contract 宣布。
- `/en/v1/...` 页面 MUST NOT 作为英文 normative 文本发布；权威 prose 仍是 `spec/v1/zh/`。除非未来另行接受新的语言政策提案，本规范不承诺提供完整英文版。
- 站点生产依赖 MUST NOT 存在未处理的 high / moderate `npm audit` finding；如需例外，必须在 release-readiness report 中记录影响面与补偿措施。
- promotion 提交 MUST 同时把 §5.1.1 的 post-GA 变更控制作为后继发布门禁启用；stable tag、stable public catalog snapshot 与签名 conformance claim 共同构成后继兼容性比较的不可变基线。

### 5.1.1 stable promotion 后的变更控制

`v1.0.0` promotion 的原子提交是 pre-GA 激进修订与 post-GA 兼容维护的唯一分界。该提交之后，以下规则适用于全部 v1 patch / minor 发布、catalog 刷新与 registry 变更：

1. **冻结面。** 已发布 canonical schema 的 `$id` 与 bytes、Event kind / operation id / error token 的既有语义、reducer profile 的 admission / cell projection / lattice join / state root / security frontier 语义，以及已发布 vector id 的判定结果均 MUST 保持不可变。active registry id MUST NOT 被删除、改名、复用为另一语义或用 alias 隐式重定向。必须改变共识语义时，MUST 新增 reducer profile；首个及每个后继 profile 都必须满足 `reducer-profile-registry.json#upgrade_release_gate`，在同一发布中提供 source→target edge 与完整升级正负向量，不得原地改变 `ak.reducer.core.v1`。
2. **兼容新增。** 新 id / schema / operation 只有在旧 receiver 对未协商值的既有 fail-closed 或开放集规则仍成立、旧 canonical bytes 与历史验签结果不变、producer 在使用前完成相应 schema / feature / profile 协商，并补齐 mixed-version 正负向量时，才 MAY 在 v1 线新增。任何改变既有对象 accepted/rejected 集、授权、可见性、排序、收敛或密码学认证输入的变更都不是“澄清”，MUST 走新 versioned id 或新 reducer profile。
3. **退役状态先于退役行。** 当前 candidate registry 不引入 `deprecated` / `retired` 行。首次计划退役之前，accepted compatibility proposal MUST 在同一变更中先定义受影响 registry 的 closed status 词表、每个状态的 producer / receiver 行为、catalog diff lint 和 mixed-version vectors，并同步修订 [`schema-registry.md` §6.1(c)](../conformance/schema-registry.md) 的 pre-GA active-only 规则；在这些前置项落地前，active 行 MUST NOT 改为其它状态。不得先添加一条 `deprecated` 行再补消费者语义。
4. **两阶段退役与最短观测窗口。** 合法退役必须按 `active → deprecated → retired` 两阶段推进。进入 `deprecated` 的 stable catalog 必须同时公布替代项或明确的功能移除理由、迁移与回滚说明、最后允许 producer 发送的条件和兼容向量；该 catalog 公开之时才开始观测窗口。`deprecated → retired` 之间 MUST 至少经过连续 180 天，且最后 90 天不得有未解决的 critical/high 兼容事故，并须有至少两个独立实现通过旧 producer / 新 receiver 与新 producer / 旧 receiver 的适用 mixed-version runner 证据。观测数据 MUST 聚合且隐私最小化，不得为了退役统计收集 Event payload、Realm 成员关系或可识别用户轨迹。
5. **retired 不等于删除历史解释器。** `retired` 后 producer MUST NOT 新发或新选择该 id；receiver 仍 MUST 保留解析、验签、历史 replay / export 与审计所需的旧 row 和 schema bytes。已经进入任一 stable v1 catalog 的 durable Event kind、schema、reducer profile、算法 selector 与错误语义在 v1 stable 线内 MUST NOT 从 catalog 物理删除。服务 operation 若被 retired，也必须保留可判定的稳定错误或 capability-negotiation 结果，不得让旧客户端落入无法归因的 transport failure。
6. **紧急安全例外。** 已公开利用且继续发送会造成高危损害时，安全公告 MAY 立即禁止 producer 使用，不必等待 180 天；但该例外 MUST 同时给出稳定 fail-closed 行为、受影响版本、替代路径与回滚条件，且 MUST NOT 删除历史解析 / 验签材料或重写既有 bytes。紧急禁发后的常规 `retired` 标记与 catalog 证据仍须补齐本节其余要求。
7. **可审计发布。** 每个 post-GA 发布 MUST 保存前一 stable catalog 到新 catalog 的机器可读 diff，并把每项变化分类为 additive、deprecating、retiring 或 emergency-security；release gate MUST 拒绝未分类的删除、语义替换、冻结 bytes 漂移、未满窗口的 retirement，以及 reducer successor 缺 edge / vector 的发布。stable tag 绑定的旧 snapshot 永不重生成；修正只能产生新的 release 与新 snapshot。

### 5.2 `v1-interop-preview` 实现互操作预览

> **门槛依赖（normative）**：本 gate 与 §5.3 依赖 §6 的 reference validator / reducer / authz / conformance runner 交付；如 §2 所述这些工具**尚未**作为完整认证工具链发布。因此当前规范只能保持 candidate；§5.2 的双实现互操作证据与 §5.3 的可执行 runner 是 §5.1 stable promotion 的前置条件，工具或证据缺失时 MUST 阻断 `v1.0.0` tag。

- 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量
- 能重放官方 sync / state / capability fixture

### 5.3 `v1-conformance-certified` 实现认证

- reference validator、reference reducer、reference authz evaluator 与 conformance runner 已发布
- canonical JSON、Event Envelope negative vectors、CBS/Lattice、capability、privacy/security、sync 与 snapshot vectors 由 CI 执行
- 公开发布的翻译与附属文档 MUST NOT 偏离同一 registry 与 fixture 基线

## 6. 工程交付要求

- 为实现认证提供官方 reference validator / reducer / authz 包
- 用 CI 自动校验 Markdown 示例、OpenAPI、registry、schema 与 fixture 一致性
- 从 OpenAPI / JSON Schema 生成 SDK 类型与 contract tests
- 对宽泛 payload schema 提供 reference validator 中的语义校验，MUST NOT 只凭 JSON Schema 宣称完全互操作
