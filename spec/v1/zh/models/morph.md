---
title: Morph
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

`morph`（`ak:morph:`）是 Arkret 协作图中的**开放形态对象**，用于承载协议未固化为标准类型的协作对象。它适合：

- 插件或业务自定义对象
- 未来标准类型的实验阶段
- 外部系统镜像对象
- 低频、弱互操作的扩展数据
- 不要求强互操作的弱结构数据

Morph 是扩展缓冲层，不是标准对象的替代品。Strand、Message 和 Realm workflow 的主语义已经由标准对象类型定义；实现不得为了复用字段、renderer 或插件机制而把这些对象改写为 Morph。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Schema 与字段

Schema id: `ak.schema.morph.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:morph` | 以 `ak:morph:` 开头。 | Morph ID。 |
| `schema` | yes | `ak.schema.morph.v1` | const。 | 容器 self-schema。 |
| `realm_id` | yes | `id:realm` |  | 所属 Realm。 |
| `schema_refs` | yes | `array<string>` | 至少 1 项，唯一。 | `fields` 结构验证的权威 schema 集合；`morph_kind` / `facets` 不能替代。 |
| `morph_kind` | yes | `string` | 标准值见业务 profile，扩展不得使用未注册 `ak.` 前缀。**create-locked**，禁止后续修改。 | 开放类型 / 业务标签。 |
| `facets` | no | `map<FacetConfig>` | 未知 facet 必须由 Realm schema / Morph profile 声明。`facets` map 的总 canonical size **计入** Morph 对象的 256 KiB 上限（与 `fields` 同一 budget，见 [`../conformance/scalability-constraints.md` §2](../conformance/scalability-constraints.md)）；不另设独立 facet 条数上限，超出对象总上限 MUST reject（`payload_too_large` / `schema_violation`）。 | Morph 暴露哪些已声明能力 hint。 |
| `metadata` | no | `object` | MAY 携带 `title` / `summary` 及 profile 定义的展示 metadata。与 `encrypted_metadata` 至多一个且不得并存（mutually exclusive, optional）。effective `metadata_encryption_floor` 要求加密对应 metadata 时 MUST 省略（改用 `encrypted_metadata`）。 | 用户可读 Morph metadata；Morph 业务字段仍在顶层 `fields`。MLS / E2EE 下按 `metadata_encryption_floor` 决定是否必须放入 `encrypted_metadata`。 |
| `encrypted_metadata` | no | `EncryptedPayload` | 与 `metadata` 至多一个且不得并存（mutually exclusive, optional）；plaintext 是同一个 Morph metadata object。effective `metadata_encryption_floor` 要求加密 Morph metadata（E2EE profile）时 MUST 提供本字段；不要求时二者皆可省（Morph 无用户可读 metadata 时允许都不写）。 | E2EE 场景下包裹 Morph metadata。 |
| `content` | no | `object` | 富文本/parts 见 [`content-types.md`](./content-types.md)。 | 正文内容。 |
| `encrypted_content` | no | `EncryptedPayload` | 与 `content` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹 Morph 正文内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 自身属性。 |
| `scope_circle_id` | no | `id:circle` | scope 派生、CBA 基线校验、签名 `scope_ref` 对照与 rebind 规则以 [`circle.md` §6](./circle.md) 为唯一权威。 | 将 Morph 落入窄于 Realm 的 [Circle](./circle.md) scope。 |
| `state` | no | `enum(active, archived, redacted)` | lifecycle 转换与 reason_code 以 [common-fields.md §5.1](./common-fields.md) 的 Morph 行为唯一权威；`archived` 可逆，唯一不可逆终态是 `redacted`。 | 物化状态（物理生命周期）。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `stage` | no | `enum(draft, proposed, planned, in_progress, blocked, done, cancelled, superseded)` | 枚举、唯一写入路径、reserved-name guard 与 reducer 规则以 [common-fields.md §5.3](./common-fields.md) 为唯一权威。generic Morph 可省略；需要进度轴的 `morph_kind` profile MAY 收紧为 create 必填，缺失时首条 `ak.morph.stage.set` 可初始化为任一合法值。 | 可选业务进度阶段（与 `state` 正交）。 |
| `stage_changed_at` | conditional | `timestamp` | **Reducer-derived**：每次 `stage` 实际变更时由 reducer 用触发 event 的 `created_at` 覆盖写入；same-value self-transition 不更新本字段。 | 最近一次 stage 转换时间。 |
| `created_by` | yes | `ActorId` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

> `stage` 取值的非规范说明：Morph 上 `draft → proposed → done → superseded` 是常见的文档/草案推进路径，仅为示例性参考，枚举的完整取值与转换规则仍以 8 值统一口径（见 [common-fields.md §5.3](./common-fields.md)）为准。

### 2.1 Event 家族

本表为人类可读说明视图；完整集合与 `wire_scope` / `reducer_input` / lattice 属性以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准，capability action 以 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 为准，lifecycle 状态校验模板见 [`common-fields.md` §5.1 / §5.2](./common-fields.md)。

| event kind | reducer_input | payload 形态 | capability action | 前置 / 说明 |
| --- | --- | --- | --- | --- |
| `ak.morph.create` | yes | full object | `ak.morph.create` | 创建 Morph；`morph_kind` create-locked，`stage` 可选（profile 可收紧），`schema_refs[]` ≥1。reducer 固化 `effective_scope`（见 §6.1 / [circle.md §6](./circle.md)）。 |
| `ak.morph.update` | yes | `ak.schema.patch.v1` | `ak.morph.update` | 改 `fields` / `metadata` / `facets` / `content`。patch path `morph_kind` / `schema_refs` / `stage` / `stage_changed_at` MUST `schema_violation`。 |
| `ak.morph.stage.set` | yes | stage transition payload | `ak.morph.stage.set` | 唯一改 / 初始化 `stage` 的路径；缺失轴的首写可取任一合法值，`stage_changed_at` reducer-derived；后续转换合法性见 [common-fields.md §5.3](./common-fields.md)。 |
| `ak.morph.archive` | yes | object_lifecycle_payload | `ak.morph.archive` | `active → archived`（可逆中间态，非终态）；源状态非 `active` 时 `morph_not_active`。 |
| `ak.morph.restore` | yes | object_lifecycle_payload | `ak.morph.restore` | `archived → active`；源状态非 `archived` 时 `morph_not_archived`。 |
| `ak.redaction`（指向 Morph） | yes | redaction_payload | `ak.redaction` | 进入唯一不可逆终态 `redacted`；源状态 MUST ∈ `{active, archived}`，否则 `morph_already_terminal`。 |

## 3. 最小示例

```json schema=schemas/morph.schema.json
{
  "id": "ak:morph:AUou5-JrNP1W6Qhnuc2zBUyVzxpczt67dSwhviS8m2TC",
  "schema": "ak.schema.morph.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "schema_refs": ["ak.schema.morph.customer_risk.v1"],
  "morph_kind": "customer_risk",
  "metadata": {
    "title": "ACME procurement risk"
  },
  "facets": {
    "stateful": {
      "state_field": "fields.status"
    },
    "renderable": {
      "renderers": ["card", "row"]
    }
  },
  "fields": {
    "status": "open",
    "severity": "high"
  },
  "stage": "in_progress",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw","principal_server_id":"ak:did_core:webvh:z6mkfixtureprincipalserverexample"}},
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

> **示例规则**：顶层 `schema` 必须是容器 self-schema `ak.schema.morph.v1`，它仅定义 Morph 容器形态；`schema_refs[]` 是 §4 顺序 1 的结构验证真源，必须列出**业务字段** schema id——上例使用配套的参考业务 schema [`ak.schema.morph.customer_risk.v1`](../../artifacts/schemas/morph-customer-risk.schema.json)，它声明 `fields.status` / `fields.severity` 的允许取值集合。JSON Schema 与 Realm `morph_kind_profiles` 都不定义通用 before→after 状态机；确需状态机时必须由具名具体 reducer 冻结。同名容器 schema `ak.schema.morph.v1` MUST NOT 被列入 `schema_refs[]` 当作业务 schema。

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph、Strand track projection 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象的主语义必须保留在对应标准类型上。

## 4. Morph 类型系统合并优先级

> Machine-readable canonical: [`artifacts/registry/morph-kind-decision-table.json`](../../artifacts/registry/morph-kind-decision-table.json) 。下表与该 artifact 双向同步；有歧义时以 artifact 为准，本表为人类可读视图。

### 4.0 决策矩阵 (Normative summary)

在进入 4 源合并表之前，先列出 Morph 上每类决策问题应当从**唯一来源**读取——所有 reducer / projection / authz / UI 实现 MUST 按下表选源，**禁止跨源混合或回退**。不在表内的决策问题 SHOULD 抑制（不读 morph_kind / facets 当作业务行为依据）。

| 决策问题 | 唯一来源 | 不得读取 |
| --- | --- | --- |
| 字段是否合法 / 是否必填 / 类型正确 | §4 顺序 1 (`schema_refs[]`) ∩ 顺序 2 (`morph_kind_profiles`) | morph_kind, facets |
| capability `allowed_morph_kinds` / resource selector 匹配 | §4 顺序 3 (`morph_kind` 字符串) | schema_refs, facets |
| 默认 renderer / `query.item_facets` / `graph.node_facets` 过滤 / UI 降级 hint | §4 顺序 4 (`facets`) | schema_refs, morph_kind |
| 是否可调用某 capability action | capability grant + Realm policy（reducer-input event 自身的 capability 校验） | morph_kind, facets, schema_refs |
| `schema_refs[]` | `ak.morph.create` 写入的固定集合 | 任何 update、facet / morph_kind 推断 |

任何实现违反本表（典型错误：UI 按 `facets.assignable` 显示 assign 按钮**且**绕过 capability 检查，或 reducer 按 `morph_kind` 决定字段验证集合）即为实现 bug，conformance 套件 MUST 覆盖反例。

同一 Morph 对象的"类型"信息可能来自四个声明源；任意 reducer / projection / capability 路径在求"该 Morph 是什么 / 允许什么"时必须按下表合并，不得自行选边。优先级数字越低越优先，冲突时高优先级值整体替换低优先级值（不部分混合）：

| 顺序 | 来源 | 作用 | 谁可写 |
| --- | --- | --- | --- |
| 1 | Morph object 的 `schema_refs[]` | **结构 / 验证真源**：决定 `fields` 的 schema、必填性与类型。 | Morph create（**create-locked**） |
| 2 | Realm schema `morph_kind_profiles[<morph_kind>]` | **Realm-scoped 收紧**：声明该 `morph_kind` 在本 Realm 中可暴露的 facets、可写字段子集、必需 schema_refs、必需 capability action。本层 **只能收紧** §1 声明的范围，不得放宽。 | `ak.realm.schema` state event（写入 `ak.component.realm.schema.v1` cell，与 `schema_refs` 同载；声明形态见 [governance-objects.md §2.3](./governance-objects.md)） |
| 3 | Morph object 的 `morph_kind` (string) | **业务标签 / discoverability key**：用于 query / view / capability `allowed_morph_kinds` 匹配；不引入 reducer 行为。 | Morph create（**create-locked**，禁止后续修改） |
| 4 | Morph object 的 `facets` (map) | **UI / projection hint**：选择默认 renderer、查询过滤、降级展示；MUST NOT 影响授权、状态机、reducer、wire 互操作。 | Morph create / `ak.morph.update` |

合并规则：

- **结构验证**只读取顺序 1 + 2：reducer / schema 校验 `fields` 时合并 §1 声明的字段集合与 §2 在该 Realm 中收紧后的子集；§3 / §4 不参与字段验证。
- **类型匹配（capability 的 `allowed_morph_kinds`、resource selector）**只读取顺序 3：`morph_kind` 是 wire-stable 字符串 key。它 create-locked 是为了避免授权错位（一旦改 `morph_kind`，旧 grant 的 selector 立即失效，是常见漏洞源）。
- **Facets**只在以下三处生效：默认 renderer / view 选择、查询 `item_facets` / `node_facets` 过滤、降级 UI 提示。任何 reducer 行为、状态机、授权判定 MUST NOT 读取 §4。
- **冲突处理**：
  - §1 与 §2 字段集冲突 → §2 胜（Realm-scoped 收紧）；§2 试图放宽 §1 → `schema_violation`，Realm schema accept 时静态拒绝。
  - `facets` 声明的 hint 字段在 §1/§2 中不存在 → 该 facet 在该 Morph 上 inactive，但 Morph 本身仍合法（facet 是 hint，不是 contract）。
  - `morph_kind` 在 Realm schema `morph_kind_profiles` 中未声明 → §2 取空收紧（即纯 §1）；不得自动放宽到 "all fields allowed"。
  - 同一信息（例如 "可被分配"）同时由 §1 schema field、§2 必需 capability、§4 `assignable` facet 表达 → §1+§2 是真相，§4 仅作为查询提示；UI MUST NOT 仅凭 §4 决定能否调用 assign 操作。

声明者须在四层之间保持一致；只有顺序 1 与 2 是规范来源，§3/§4 的存在不构成"已声明能力"。Reducer / capability / wire 验证路径如违反本表（例如读取 §4 facet 决定授权），即为实现 bug，conformance 套件 MUST 覆盖。

### 4.1 Schema Refs 固定规则（Normative）

`morph_kind` 与 `schema_refs[]` 均在 `ak.morph.create` 时确定并 create-locked。它们共同决定字段验证与 capability selector 的稳定含义。`ak.morph.update` 的 patch 出现 `morph_kind` 或 `schema_refs` 时 MUST 以 `schema_violation` 拒绝；Realm `morph_kind_profiles` 只能收紧已声明 schema 的字段集合，不能替换或扩张它。

## 5. 标准 Facets

Facets 是 schema-declared **UI / projection hints**，不是对象身份，也不是任何 normative 行为的依据。标准对象 MAY 暴露 schema/profile 已声明的 facets 来辅助展示或查询；Morph MAY 使用 facets 帮助 View、本地搜索、UI 和插件做过滤、降级展示和默认 renderer 选择。Strand `track.profile`（[`strand-and-message.md` §4.3](./strand-and-message.md)）是同一 declared UI-hint 纪律在 track 上的窄投影；两者承载对象不同，但都不得改变授权、状态机、reducer 或 wire 互操作。

**Facets 不参与的决策**（与 §4.0 决策矩阵保持一致，本节只重申以避免实现误读）：

- 授权（capability check、capability `allowed_morph_kinds`、resource selector）
- 状态机 transition
- 排序 / Lattice join / Control Move precondition
- reducer 行为（接受 / 拒绝 / soft fail）
- event kind 接受规则
- wire 互操作（canonical bytes / event digest / signature）

任何把 facet 当作上述决策唯一来源的实现属于实现 bug。Facet 配置可以引用相应 Realm schema / Morph profile / event kind registry / capability action 作为权威声明，但 facet 自身不替代它们。

| Facet | 说明 | 典型字段/关系 |
| --- | --- | --- |
| `container` | 提示对象可按显式 relation/profile 作为容器投影。 | `child_object_kinds`, `relation_kinds`, `ordering`, `exclusive_scope`。 |
| `replyable` | 提示对象可按声明的 reply relation 被回复，形成 thread/discussion。 | `reply_object_kinds`, `reply_relation_kind`, `time_field`, `redaction_policy`。 |
| `schedulable` | 提示对象有声明的时间窗口，可进入 calendar/gantt 投影。 | `start_field`, `end_field`, `timezone_field`, `dependency_relation_kinds`。 |
| `assignable` | 提示对象有声明的分配字段或关系。 | `assignee_relation_kind` 或 `assignee_field`。 |
| `stateful` | 提示对象有显式 profile 定义的受控状态机。 | `state_field`, `states`, `transition_policy`。 |
| `rankable` | 提示对象有声明的稳定手动排序 rank。 | `rank_field`, `rank_profile`, `collision_policy`。 |
| `reviewable` | 提示对象有声明的审核/审阅状态。 | `review_state_field`, `reviewer_relation_kind`, `priority_field`。 |
| `notifiable` | 提示对象可按声明的 notification profile 派生 notification/inbox/read state。 | `notification_kinds`, `read_state_policy`。 |
| `documentable` | 提示对象可按声明的 document profile 作为文档或 section root。 | `section_relation_kind`, `section_order_field`, `body_field`。 |
| `renderable` | 提示对象声明允许的默认展示面。 | `renderers`, `title_field`, `summary_field`, `media_field`。 |

`query.facets`、`collection.item_facets` 和 `graph.node_facets` 的数组语义为 AND：候选对象 MUST 同时具备列出的全部 facet。`container.child_facets` 与 `replyable.reply_facets` 使用 `{all?, any?, none?}` 选择器。

### 5.1 Facet 与 RelationProfile / Schema 约束冲突时的仲裁（normative）

当一个 facet hint 在 cardinality / required-ness / state machine 等维度上与同名概念在 [`relation.md` §5](./relation.md) 的 **RelationProfile** 或 [`common-fields.md` §5`](./common-fields.md) 的标准状态机发生**冲突**时（典型例：`assignable` facet 提示单值分配，但 Realm 注册的 `assigned_to` RelationProfile 声明 `cardinality=many_to_one`），适用以下仲裁规则：

1. **RelationProfile / Schema / Event kind registry / Capability action 在所有 reducer 与 wire 层面胜出**（与 §4.0 决策矩阵一致）：reducer MUST 按这些权威声明评估 cardinality、required-ness、transition、precondition 与 wire 拒绝。
2. **Facet 在冲突时降级为 UI 提示**：UI / View / Inbox / 客户端搜索 SHOULD 继续根据 facet 调整渲染或筛选，但 facet 中暗示的约束 MUST NOT 被反向用于授权、Control Move precondition、reducer 接受/拒绝或 wire 校验。
3. **schema_refs[] 与 morph_kind_profiles 的 facet 声明视为 schema-bound hint**：reducer 不在 facet 层强制相同 facet 在跨 schema / profile 间一致，但 conformance lint SHOULD 标记"facet 与 RelationProfile / Schema 冲突"，提示规范文档维护者澄清意图。
4. 实现 MUST NOT 把 facet 当作"沉默约束"——即 facet 不出现于 wire 上不代表约束被满足/不满足，约束只由 RelationProfile / Schema 决定。

如此 facet 在 UI / hints 域与 RelationProfile 在 normative 域分工明确，避免两套来源静默互相覆盖。

### 5.2 Profile-declared generic container events（normative）

`ak.container.move_item` / `ak.container.rebalance` 是 Realm profile 明确启用的通用容器 Control Move，不由 `container` facet 激活。Profile MUST 声明允许的 `(container object type, item object type, relation_kind)` 三元组；未声明三元组 MUST `unsupported_feature`，facet 出现与否不改变结果。标准 Space(board/list) → Strand placement 继续使用 `ak.strand.move` / `ak.strand.reorder`，MUST NOT 同时启用 generic container event，以避免双 truth source；generic 事件只服务 profile-defined Morph/Strand 等非标准容器。

`ak.container.move_item` payload 为封闭 `container_move_item_payload`：`item_ref`、目标 `container_ref`、`relation_kind`、`rank` 必填，`from_container_ref` 与 `expected_position_digest` 可选。它写 `ak.component.container.position.v1:(container_ref,item_ref)` 的 `cas_register + bottom=reject` cell；同一 item 在 profile 声明 exclusive 时，reducer MUST 原子移除旧 container position 并写新位置。`expected_position_digest` 若存在，必须等于当前 position cell canonical digest，否则 `failed_precondition` `cas_conflict`。排序按 [`../conformance/encoding.md`](../conformance/encoding.md) rank + canonical tie-break；不得由 facet、HLC 或到达顺序选 winner。

`ak.container.rebalance` payload 为封闭 `container_rebalance_payload`：`container_ref`、`relation_kind`、`positions[]`、`expected_order_digest` 必填。`positions[].item_ref` MUST 唯一，rank MUST 唯一且符合 canonical rank grammar；整批原子写 `ak.component.container.order.v1:<container_ref>` 的 `cas_register + bottom=reject` cell。`expected_order_digest` 不匹配时整个 Move `cas_conflict`，不得部分改 rank。单次最多 10,000 positions；更大容器必须分层或由 profile 提供独立分页 rebalance 方案。

## 6. Schema Contract

Morph `schema_refs[]` 的固定规则见 [§4.1](#41-schema-refs-固定规则normative)。

- 新字段优先 optional。
- 既有字段不得静默改变语义。
- reducer 和客户端 MUST 保留 schema 允许但实现未识别的字段（Morph payload 由 Realm 注册 schema 定义；canonical envelope 层 schema 未声明的字段按 [event-and-patch.md](./event-and-patch.md) §2.2 拒绝）。
- UI 遇到未知 Morph kind SHOULD 降级为 generic Morph card。
- 标准对象不得阻止 Realm 定义自定义 Morph kind。
- 实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。

## 7. 规范性引用

- 公共字段、stage 轴（§5.3）：[common-fields.md](./common-fields.md)。
- Relation：[relation.md](./relation.md)。
- View facets / projection：[views.md](./views.md)。
- Morph schema：`artifacts/schemas/morph.schema.json`。
- Morph kind 合并决策表（canonical）：[`artifacts/registry/morph-kind-decision-table.json`](../../artifacts/registry/morph-kind-decision-table.json)。
- Schema registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Stage 事件 payload：`artifacts/schemas/event-payload.schema.json#/$defs/morph_stage_set_payload`。
- Stage 事件 / capability 注册：`artifacts/registry/event-kind-registry.json`、`artifacts/registry/capability-action-registry.json`。
- Stage 字段 forbidden-wire 规则：`artifacts/registry/forbidden-wire-fields.json`。
