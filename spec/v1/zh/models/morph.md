---
title: Morph
---

## 1. 目标

`morph`（`cx:morph:`）是 Contrix 协作图中的**开放形态对象**，用于承载协议未固化为标准类型的协作对象。它适合：

- 插件或业务自定义对象
- 未来标准类型的实验阶段
- 外部系统镜像对象
- 低频、弱互操作的扩展数据
- 不要求强互操作的弱结构数据

Morph 是扩展缓冲层，不是标准对象的替代品。Flow、Message 和 Space workflow 的主语义已经由标准对象类型定义；实现不得为了复用字段、renderer 或插件机制而把这些对象改写为 Morph。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Schema 与字段

Schema id: `cx.schema.morph.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:morph` | 以 `cx:morph:` 开头。 | Morph ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `morph_type` | yes | `string` | 标准值见业务 profile，扩展不得使用未注册 `cx.` 前缀。**create-locked**，禁止后续修改。 | 开放类型 / 业务标签。 |
| `facets` | no | `map<FacetConfig>` | 未知 facet 必须由 Space schema / Morph profile 声明。 | Morph 暴露哪些已声明能力 hint。 |
| `title` | no | `string` | SHOULD <= 512 chars。 | 标题。 |
| `summary` | no | `string` |  | 摘要。 |
| `content` | no | `object` | 富文本/blocks 见 [`content-types.md`](./content-types.md)。 | 正文内容。 |
| `encrypted_payload` | no | `EncryptedPayload` | 与 `content` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹 Morph 正文内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 自身属性。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 3. 最小示例

```json
{
  "id": "cx:morph:0196414b-0000-7000-8000-000000000000",
  "schema": "cx.schema.morph.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "morph_type": "customer_risk",
  "title": "ACME procurement risk",
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
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph、Flow track projection 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象的主语义必须保留在对应标准类型上。

## 4. Morph 类型系统合并优先级

同一 Morph 对象的"类型"信息可能来自四个声明源；任意 reducer / projection / capability 路径在求"该 Morph 是什么 / 允许什么"时必须按下表合并，不得自行选边。优先级数字越低越优先，冲突时高优先级值整体替换低优先级值（不部分混合）：

| 顺序 | 来源 | 作用 | 谁可写 |
| --- | --- | --- | --- |
| 1 | Morph object 的 `schema_refs[]` | **结构 / 验证真源**：决定 `fields` 的 schema、必填性、类型与 transition 规则。 | Morph create / `cx.morph.update` |
| 2 | Space schema `morph_type_profiles[<morph_type>]` | **Space-scoped 收紧**：声明该 `morph_type` 在本 Space 中可暴露的 facets、可写字段子集、必需 schema_refs、必需 capability action。本层 **只能收紧** §1 声明的范围，不得放宽。 | Space schema / Space profile |
| 3 | Morph object 的 `morph_type` (string) | **业务标签 / discoverability key**：用于 query / view / capability `morph_type_allow` 匹配；不引入 reducer 行为。 | Morph create（**create-locked**，禁止后续修改） |
| 4 | Morph object 的 `facets` (map) | **UI / projection hint**：选择默认 renderer、查询过滤、降级展示；MUST NOT 影响授权、状态机、reducer、wire 互操作。 | Morph create / `cx.morph.update` |

合并规则：

- **结构验证**只读取顺序 1 + 2：reducer / schema 校验 `fields` 时合并 §1 声明的字段集合与 §2 在该 Space 中收紧后的子集；§3 / §4 不参与字段验证。
- **类型匹配（capability 的 `morph_type_allow`、resource selector）**只读取顺序 3：`morph_type` 是 wire-stable 字符串 key。它 create-locked 是为了避免授权错位（一旦改 `morph_type`，旧 grant 的 selector 立即失效，是常见漏洞源）。
- **Facets**只在以下三处生效：默认 renderer / view 选择、查询 `item_facets` / `node_facets` 过滤、降级 UI 提示。任何 reducer 行为、状态机、授权判定 MUST NOT 读取 §4。
- **冲突处理**：
  - §1 与 §2 字段集冲突 → §2 胜（Space-scoped 收紧）；§2 试图放宽 §1 → `schema_violation`，Space schema accept 时静态拒绝。
  - `facets` 声明的 hint 字段在 §1/§2 中不存在 → 该 facet 在该 Morph 上 inactive，但 Morph 本身仍合法（facet 是 hint，不是 contract）。
  - `morph_type` 在 Space schema `morph_type_profiles` 中未声明 → §2 取空收紧（即纯 §1）；不得自动放宽到 "all fields allowed"。
  - 同一信息（例如 "可被分配"）同时由 §1 schema field、§2 必需 capability、§4 `assignable` facet 表达 → §1+§2 是真相，§4 仅作为查询提示；UI MUST NOT 仅凭 §4 决定能否调用 assign 操作。

声明者须在四层之间保持一致；只有顺序 1 与 2 是规范来源，§3/§4 的存在不构成"已声明能力"。Reducer / capability / wire 验证路径如违反本表（例如读取 §4 facet 决定授权），即为实现 bug，conformance 套件 MUST 覆盖。

## 5. 标准 Facets

Facets 是 schema-declared capability hints，不是对象身份。标准对象 MAY 暴露 schema/profile 已声明的 facets 来辅助展示或查询，但标准对象的核心语义不依赖 facets 才成立；Morph MAY 使用 facets 帮助 View、本地搜索、UI 和插件做过滤、降级展示和默认 renderer 选择。

Facets MUST NOT 成为授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作的唯一规范来源。这些语义必须由 Space schema / Morph profile / event registry / capability action 明确定义。Facet 配置可以引用这些 profile 或暴露 UI hints，但不能替代它们。

| Facet | 说明 | 典型字段/关系 |
| --- | --- | --- |
| `container` | 提示对象可按显式 relation/profile 作为容器投影。 | `child_object_types`, `relation_kinds`, `ordering`, `exclusive_scope`。 |
| `replyable` | 提示对象可按声明的 reply relation 被回复，形成 thread/discussion。 | `reply_object_types`, `reply_relation_kind`, `time_field`, `redaction_policy`。 |
| `schedulable` | 提示对象有声明的时间窗口，可进入 calendar/gantt 投影。 | `start_field`, `end_field`, `timezone_field`, `dependency_relation_kinds`。 |
| `assignable` | 提示对象有声明的分配字段或关系。 | `assignee_relation_kind` 或 `assignee_field`。 |
| `stateful` | 提示对象有显式 profile 定义的受控状态机。 | `state_field`, `states`, `transition_policy`。 |
| `rankable` | 提示对象有声明的稳定手动排序 rank。 | `rank_field`, `rank_profile`, `collision_policy`。 |
| `reviewable` | 提示对象有声明的审核/审阅状态。 | `review_state_field`, `reviewer_relation_kind`, `priority_field`。 |
| `notifiable` | 提示对象可按声明的 notification profile 派生 notification/inbox/read state。 | `notification_types`, `read_state_policy`。 |
| `documentable` | 提示对象可按声明的 document profile 作为文档或 section root。 | `section_relation_kind`, `section_order_field`, `body_field`。 |
| `renderable` | 提示对象声明允许的默认展示面。 | `renderers`, `title_field`, `summary_field`, `media_field`。 |

`query.facets`、`collection.item_facets` 和 `graph.node_facets` 的数组语义为 AND：候选对象 MUST 同时具备列出的全部 facet。`container.child_facets` 与 `replyable.reply_facets` 使用 `{all?, any?, none?}` 选择器。

## 6. Schema Evolution

标准类型与 Morph 演进 MUST 遵守：

- 新字段优先 optional。
- 既有字段不得静默改变语义。
- reducer 和客户端 MUST 保留未知字段。
- UI 遇到未知 Morph type SHOULD 降级为 generic Morph card。
- 标准对象不得阻止 Space 定义自定义 Morph type。
- 实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。

## 7. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Relation：[relation.md](./relation.md)。
- View facets / projection：[views.md](./views.md)。
- Morph schema：`artifacts/schemas/morph.schema.json`。
- Schema registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
