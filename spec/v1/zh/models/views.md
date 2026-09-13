---
title: View Model
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 必须对人类友好，因此协议必须允许对象自然投影为：

- 看板、列表、表格、日历、甘特图
- 时间线、活动流、聊天、话题论坛、单线程讨论
- 图谱、树
- 文档
- dashboard、审阅队列、inbox、notification、agent 运行轨迹

这些展示模式都是 View projection。View 本身是一个可签名、可共享、可授权的协议对象，但它拥有的是投影定义的真相，不是被投影对象的协作事实。

## 2. 设计原则

### 2.1 View 有定义真相，但不是对象真相

View 的 `title`、`query`、`kind`、`renderer`、`visible_fields`、`layout`、typed config、共享可见性与 lifecycle `state` 属于 View 自身的 canonical state。它们可以通过 `ak.view.create` / `ak.view.update` 修改、签名、审计和同步。

View 不承载被投影对象的 canonical state。Board Space / List Space / Strand / Message / Morph / Relation 的当前态必须由对应对象事件和 reducer 得到。任何 View projection 输出都必须能追溯到 signed Event、reducer profile 和 causal frontier。

这些对象事实必须从同一套底层结构产生：

```txt
Realm + Actor + Strand + Message + Morph + Relation + Event
```

### 2.2 View.kind 是响应族，不是产品名

协议保留 5 个 `View.kind` 作为 response family：

- `collection`
- `timeline`
- `graph`
- `document`
- `composite`

`board`、`list`、`table`、`calendar`、`gantt`、`chat`、`thread`、`forum`、`dashboard` 都是 renderer，而不是新的 `View.kind`。

### 2.3 Board Space / List Space 是 Space.kind，不是 View.kind

Board Space 与 List Space 是 `Space` 的 `kind`（详见 [realm-and-space.md](./realm-and-space.md)）：

- `Space(kind=board)`
- `Space(kind=list)`

看板和列表投影应表达为：

- `kind="collection" + renderer="board"`
- `kind="collection" + renderer="list"`

View 负责"如何看"，Board Space / List Space 负责"对象如何被组织"。

### 2.4 Query SHOULD 优先面向 Strand / Message / Morph

View 查询 SHOULD 优先使用标准对象类型：

- `strand`
- `message`
- `morph`

Board Space / List Space 作为容器由 `space.kind` 与 `contains` relation 表达。只有开放对象才主要依赖 `morph_kind`。

### 2.5 权限必须逐对象、按 effective scope 与 action scope 裁剪

View 展示 Strand、Message 或跨 Realm Relation 时，必须先按对象 home Realm / Circle effective scope 判断可见性，再按 capability action scope 裁剪可执行操作。Renderer、track name、View filter 都不能授予读取或写入权限。

- 用户能看某个 Strand，仍不代表能执行 `ak.strand.update`、`ak.strand.stage.set`、`ak.strand.move` 或 `ak.message.create`；每个交互写入都要按对应 action 重新鉴权。
- Message timeline 的可见性来自 Strand 的 single effective scope（Realm-default 或 Circle），不是 `discussion` track 自己的 ACL。
- `allowed_tracks` / `strand_track` 这类 action 或通知 scope 只能缩小已授权动作和通知匹配范围，不能创造新的读权。
- Board projection MAY 显示 discussion locked link，但不得泄露未授权 discussion 的消息摘要、成员、统计、最后活动时间或存在性细节，除非 policy 明确允许。

### 2.6 交互写入必须落回真实对象

客户端 MAY 在 View 中提供拖拽、编辑、批量操作和快捷入口，但写入语义必须落到对应标准对象、Relation 或 Account Data：

| 用户动作 | canonical event |
| --- | --- |
| Strand 拖到另一个 List | `ak.strand.move` |
| Strand 在同一 List 内排序 | `ak.strand.reorder` |
| 修改 Strand 标题、Description、Synthesis 正文或 profile-defined 截止时间 | `ak.strand.update`（正文两面分别受 `allowed_write_fields` 约束） |
| 推进 Strand 业务阶段 | `ak.strand.stage.set` |
| 添加 / 移除负责人 | `ak.relation.create` / `ak.relation.tombstone`（`relation_kind=assigned_to`） |
| 切换 Strand 默认 track / 开启 / 关闭 track / 修改 track profile | `ak.strand.tracks.update` |
| 修改 Board Space / List Space 元数据 | `ak.space.update` |
| 发送、编辑、撤回 discussion 消息 | `ak.message.create` / `ak.message.revise` / `ak.message.redact` |
| 改变共享 View filter / sort / group / columns / layout | `ak.view.update` |
| 移除共享 View | `ak.view.update` patch `state="tombstoned"` |
| 改变个人 View 偏好、临时 filter、列宽、折叠状态 | actor-private account data |

## 3. View 对象

### 3.1 Schema 与字段

Schema id: `ak.schema.view.v1`

View 是投影定义对象。它的 canonical state 只覆盖"如何看"：query、kind、renderer、typed config、visible fields、layout 和共享配置。它不得作为被投影对象的状态、位置、关系、权限或消息历史的唯一来源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:view` |  | View ID。 |
| `schema` | yes | `ak.schema.view.v1` |  | Schema ID。 |
| `realm_id` | yes | `id:realm` |  | 所属 Realm。 |
| `kind` | yes | `enum(collection, timeline, graph, document, composite)` |  | 核心投影原语。 |
| `renderer` | no | `enum(board, list, table, calendar, gantt, timeline, thread, chat, forum, graph, tree, document, dashboard, custom)` | 不参与真相归约。 | 展示面提示；交互能力仍由对象类型、显式 schema/profile、capability 与 typed config 决定。 |
| `title` | no | `string` |  | View 名称。 |
| `visibility` | no | `enum(private, shared)` | 省略时视为 `shared`：共享写入路径（`ak.view.create` / `ak.view.update`）本就拒绝 `private`（§3.2），因此缺省只有一种合法解释。 | View 共享可见性。 |
| `state` | yes | `enum(active, tombstoned)` | 必须显式给出；`tombstoned` terminal。 | View lifecycle。 |
| `state_changed_at` | conditional | `timestamp` | `state=tombstoned` 时 reducer-derived 必填。 | 终态 accepted 时间。 |
| `query` | yes | `Query` | 见 [`../conformance/query-schema.md`](../conformance/query-schema.md)。 | 数据查询。 |
| `visible_fields` | no | `array<string>` | dot path。 | 展示字段。 |
| `layout` | no | `object` | UI hint，不是权限。 | 布局配置。 |
| `collection` | conditional | `CollectionConfig` | `kind="collection"` 时 MUST 设置。 | 集合投影配置；看板、表格、日历、甘特、队列、矩阵都由该配置表达。 |
| `timeline` | conditional | `TimelineConfig` | `kind="timeline"` 时 MUST 设置。 | 时间线配置。 |
| `graph` | conditional | `GraphConfig` | `kind="graph"` 时 MUST 设置。 | 图/树遍历配置。 |
| `document` | conditional | `DocumentConfig` | `kind="document"` 时 MUST 设置。 | 文档 section 配置。 |
| `dashboard` | conditional | `DashboardConfig` | `kind="composite"` 时 MUST 设置。命名说明：`composite` 是 response family（§2.2 五大 kind 之一），其 v1 唯一 typed config 是 `DashboardConfig`，故配置字段名取 `dashboard`（与 §4 表中 composite 的唯一 renderer `dashboard` 对齐）；composite 的非 dashboard 形态须由 profile-defined `custom` renderer 承载，v1 core 不再为 composite 引入第二个 typed config 字段。 | 仪表盘 widget 配置。 |
| `created_by` | yes | `ActorId` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

**共享 View 终态（normative）**：共享 View 的协议级移除复用 `ak.view.update`：owner 或持有 `ak.view.update` capability 的 actor 提交 patch `set.state="tombstoned"`。Reducer MUST 以 accepted update 的 canonical lifecycle timestamp 写 `state_changed_at`；actor MUST NOT 自报该字段。`tombstoned` 是 terminal：后续任何 update / reconcile 或尝试恢复 `active` MUST `failed_precondition`，`reason_code="view_already_terminal"`。Query / projection MUST 默认排除 tombstoned View；审计或显式 `include_terminal=true` 查询 MAY 返回保留定义的 stub。Private View 可由 owner-private account-data 删除，但一旦以 shared View 发布，移除必须走上述 durable update，不能仅做带外删除。 该接受面与 `state_changed_at` 的拒绝面由 `ak.vector.view.terminal_state_patch.v1` 固化。

**Private View 承载（normative）**：`visibility="private"` 的 View MUST 作为
`ak.views.private.<view_id>` 加密 account data 保存；其 plaintext value 仍按
`ak.schema.view.v1` 校验。`ak.view.create` / `ak.view.update` reducer MUST 拒绝
`visibility="private"`（`schema_violation`, `reason_code="private_view_requires_account_data"`），
不得把 title、query 或 layout 写入共享 Realm cell。查询共享 View 的 operation MUST 只返回
`visibility="shared"`；private View 只经 holder 的 account-data surface 同步。可执行覆盖见
[`../conformance/conformance-vectors.md` §5.11](../conformance/conformance-vectors.md) 的
`ak.vector.account_data.private_view_inbox_binding.v1`。

JSON Schema 对 `kind` 与 typed config 执行互斥约束：`collection` / `timeline` / `graph` / `document` / `composite` 分别只允许携带对应的 `collection` / `timeline` / `graph` / `document` / `dashboard` 配置。`kind="composite"` 的 `dashboard.widgets[]` 至少包含一个 widget；若携带 `renderer`，只能是 `dashboard` 或 profile-defined `custom`。

若某个 UI 操作改变 Strand 所属 List、Strand rank、List rank、Strand discussion Message、Relation 或对象字段，必须使用对应对象 Event；只有改变共享 filter、sort、grouping、visible fields、renderer 或 layout 时才修改 View。个人偏好、临时排序、列宽、折叠状态、本地 pin、选择模式与分页大小 MUST 使用 actor-private account data 或等价私有 Event。

### 3.2 三个 View event 的写入语义（normative）

三个 kind 写**同一个 cell family** `ak.component.view.v1`（`causal_register`、固定 `(depth,EventId)` 单值 current）。
subject 一律是 `id:view` 编码：create 由 `envelope.event_id` 唯一派生该 View 的 id，
update / reconcile 用 `payload.view_id`，两者归一到同一个 cell。

| kind | cell family | subject | 写入 | payload |
| --- | --- | --- | --- | --- |
| `ak.view.create` | `ak.component.view.v1` | `id:view(envelope.event_id)` | `set` 整个 `payload.object` | 创建时的 object snapshot |
| `ak.view.update` | `ak.component.view.v1` | `id:view(payload.view_id)` | 对冻结前态 `apply_patch` `payload.patch` | 增量 patch |
| `ak.view.reconcile` | `ak.component.view.v1` | `id:view(payload.view_id)` | `set` 整个 `payload.definition` | `{view_id, definition}` |

**为什么是一个 family（normative）**：`definition` 引用的就是完整 `view.schema.json`，
它不是另一种业务对象。三条 Event 的载荷区别可以保留，但没有理由为同一个 View 维护三条
权威状态链——那样 `ak.view.update` 的 `apply_patch` 会打在一个**从未被写过**的 cell 上，
而 因果寄存器合同禁止用 registered `initial_value` 补这个洞：基值只能来自注册的 create / genesis 写入。

由此产生三条约束：

- **update / reconcile MUST NOT 创造不存在的 View。**目标 cell 在签名 basis 下没有真实对象基值时
  MUST 拒绝，MUST NOT 把 `null` 或空对象当作隐式初始化，也不得存储任何部分效果。
- **三条写入采用同一 canonical 对象值口径。**cell 中 MUST NOT 保存可自报的 `id`，
  读取时由 subject 派生；`reconcile.definition` 同样 MUST NOT 携带 `id`，
  否则 create 与 reconcile 会在同一个 cell 里留下两种值形状。
- **reconcile 的 whole-value `set` 引用其观察到的唯一 current source。**
  并发但未被观察的分支仍保留为历史候选并参与固定 rank；「已知良好的定义」不是无条件覆盖全部未来写入的特权。

`ak.view.reconcile` 用于把 View 定义**整体**重新同步到一个已知良好的 `ak.schema.view.v1`
对象——典型场景是 schema 演进后重新发布定义。它与另外两者的分工是封闭的：create 只在
View 首次出现时携带 object snapshot；update 携带增量 patch，无法表达"丢弃当前定义、
以这一份为准"；reconcile 则不是增量，MUST 携带完整 `definition`。

因此 reconcile 的 payload MUST 是 `view_reconcile_payload`（`{view_id, definition}` 闭合对象），
**MUST NOT** 复用 create / update 的 `view_payload`：后者的 `{definition}` 分支连 `view_id`
都不要求，而 `view_id` 是 cell subject，缺失即无法定址。

reconcile 不改变 §3.1 的终态规则：目标 View 的 accepted lifecycle state 为 `tombstoned` 时，
reconcile MUST 以 `failed_precondition`、`reason_code="view_already_terminal"` 拒绝。
reconcile 同样 MUST NOT 写入被投影对象的任何 canonical state（§2.1）。
tombstone 只走既有 update 路径：reconcile MUST NOT 把 `active` 改成 `tombstoned`，
也 MUST NOT 复活 terminal View；存在已接受的终态事实时，迟到或并发的 active definition
MUST NOT 绕过该终态 gate。

reconcile 还 MUST 保留目标 View 的 `realm_id`、`created_by`、`created_at` 与身份：
MUST NOT 跨 Realm、MUST NOT 把 `shared` 改成 `private`、
MUST NOT 自报 reducer-derived 的 `state_changed_at`。
其完整 `definition` 要通过与 create / update **相同**的 schema、scope 与内容授权校验。

### 3.3 `CollectionConfig`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_object_kinds` | conditional | `array<string>` | 可由 `item_facets` 替代；至少 1 项。 | 按对象类型过滤可投影为 item/card/row/message 的对象。 |
| `item_facets` | conditional | `array<FacetName>` | 可替代 `item_object_kinds`；至少 1 项。 | 按声明 hint 选择 item，例如 `rankable`、`reviewable`、`replyable`。 |
| `item_render` | no | `enum(card, row, tile, compact, badge, message)` | 仅为共享 presentation hint；缺省时 renderer 按终端形态与可用能力推导，不改变投影结果。看板式展示 SHOULD 为 `card`。 | 建议展示面。 |
| `item_order_by` | yes | `array<SortSpec>` | 至少 1 项。 | item 稳定排序；拖拽类 collection SHOULD 使用 rank。 |
| `display_fields` | no | `array<DisplayColumn>` | dot path。 | 展示字段与格式。 |
| `count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 集合级计数策略。 |
| `grouping` | yes | `CollectionGrouping` |  | 分组/列/时间桶/矩阵配置。 |

**排序通道唯一（normative）**：View 只有两条排序通道，且互不重叠——`query.order_by` 决定**取哪些对象、按什么顺序取**，`collection.item_order_by` 决定 collection 内 item 的**展示稳定序**。v1 **没有**顶层 `sort`：它与 `query.order_by` 形态完全同构、作用面重叠，却没有定义优先级，两者同时出现时结果未定义。需要改排序的实现 MUST 改这两个字段之一。

`selection_policy` 与 `page_size` 是终端/用户私有 presentation 偏好，不是 canonical `CollectionConfig` 字段；客户端 MUST 存入独立的 actor-private account data 偏好或仅保存在本地。`CollectionConfig` 与 `CollectionGrouping` 保留开放配置扩展，但通过 `propertyNames` 明确禁止 `selection_policy`、`page_size` 与 `wip_limit_enforcement` 三个键；这些键在任一配置对象的直接成员位置出现时 MUST 返回 `schema_violation`，不得因值为 `null`、`false` 或名称位于开放扩展区而放行。create object、materialized View 与 update 后的完整 View MUST 应用同一校验；私有 View 使用同一 schema 时也不得把独立偏好混入这两个配置对象。合法自定义配置扩展保持可用，不把开放配置整体收紧为 closed object。

### 3.4 `CollectionGrouping`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | yes | `enum(none, field, relation_container, time_bucket, matrix)` |  | 分组模型。 |
| `field` | conditional | `string` | `mode="field"` 时必填。 | 字段分组路径。 |
| `lanes` | conditional | `array<object>` | `mode="field"` 时必填。 | 字段值列/泳道定义。 |
| `board_space_id` | conditional | `id:space` | `mode="relation_container"` 时必填，指向一个 `ak:space: kind=board`。 | Board Space。 |
| `container_relation_kind` | no | `string` | 默认 `contains`。 | root 到 collection/container 的关系。 |
| `item_relation_kind` | conditional | `string` | `mode="relation_container"` 时必填；不得隐式推断。 | container 到 item 的关系。 |
| `start_field` | conditional | `string` | `mode="time_bucket"` 时必填。 | 时间窗口起点字段。 |
| `end_field` | no | `string` |  | 时间窗口终点字段。 |
| `rows_by` / `columns_by` | conditional | `string` | `mode="matrix"` 时必填。 | 矩阵双轴字段。 |
| `hidden_count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 分组计数授权策略。 |

`CollectionGrouping` 只定义读取与呈现分组，不承载写入 policy。WIP 上限及其 `warn | reject | require_review` enforcement 的唯一真相源是目标 `Space(kind=list).fields`，见 [`space-hierarchy.md` §6](./space-hierarchy.md)。View 不得携带 `wip_limit_enforcement`；renderer 可以展示目标 List 的 effective policy，但不得从 View 配置生成、覆盖或放宽写入判定。

### 3.5 完整示例

```json
{
  "id": "ak:view:AT3Im0B7Kp3uhOc9ZgnAPWE0qkuAJ_fcxz8Tv7vEwFem",
  "schema": "ak.schema.view.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00Z",
  "kind": "collection",
  "state": "active",
  "renderer": "board",
  "title": "Release Strand",
  "visibility": "shared",
  "query": {
    "object_kinds": ["strand"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "direction": "out",
      "source_ref": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "depth": 2
    }
  },
  "collection": {
    "item_object_kinds": ["strand"],
    "item_render": "card",
    "item_order_by": [
      { "field": "rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "container_relation_kind": "contains",
      "item_relation_kind": "contains",
      "hidden_count_policy": "omit"
    }
  },
  "visible_fields": [
    "metadata.title",
    "metadata.fields.priority",
    "metadata.fields.due_at"
  ]
}
```

上述字段是 View 自己拥有的定义真相。它们决定“如何看”对象图，但不改变对象图本身。

## 4. 标准 `kind` 与 `renderer`

| Core kind | 常用 renderer | 必填配置 | 标准投影响应 |
| --- | --- | --- | --- |
| `collection` | `board`, `list`, `table`, `calendar`, `gantt`, `custom` | `collection` | 客户端本地派生结果（非 v1 wire response） |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `custom` | `timeline` | `TimelineProjectionView` |
| `graph` | `graph`, `tree`, `custom` | `graph` | `GraphProjectionView` |
| `document` | `document`, `custom` | `document` | `DocumentProjectionView` |
| `composite` | `dashboard`, `custom` | `dashboard` | `CompositeProjectionView` |

> `renderer` 的全局枚举(§3.1)允许 `custom` 用于**所有** kind:`custom` 是 profile-defined 展示面 escape hatch,本表每行的常用 renderer 之外都 MAY 取 `custom`(由 profile 声明语义),不参与真相归约。

`calendar` / `gantt` 只是 `collection` 的 renderer，不引入新的 `View.kind`，也不引入新的真相源。[`calendar-event.md`](./calendar-event.md) 定义的 `CalendarOccurrenceProjection` 与 `CalendarRsvpProjection` 是**客户端本地派生模型**，由已授权 Event 集合、schedule revision frontier 与 CBS cell heads 计算得出；v1 **不**把它们注册为独立 View kind 或远端 Calendar API。实现 MAY 用 `collection` + `calendar` renderer 展示这些结果，但 MUST NOT 用 View projection 缓存回写 RSVP 或 schedule 状态，也 MUST NOT 让 View 输出突破 Calendar Strand 的 effective scope 与 history visibility。

## 5. Query Model

View 应通过结构化 query 表达对象范围。

建议通用查询形状：

```json
{
  "object_kinds": ["strand", "morph"],
  "facets": ["reviewable"],
  "filters": [
    { "field": "metadata.fields.status", "op": "in", "value": ["todo", "in_progress"] }
  ],
  "relation": {
    "kind": "depends_on",
    "direction": "out",
    "depth": 2
  },
  "order_by": [
    { "field": "updated_at", "direction": "desc" }
  ],
  "limit": 100
}
```

### 5.1 看板查询示例

```json
{
    "object_kinds": ["strand"],
    "filters": [
    { "field": "metadata.fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "state", "op": "eq", "value": "active" }
  ],
  "relation": {
    "kind": "contains",
    "direction": "out",
    "source_ref": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
    "depth": 2
  }
}
```

### 5.2 Discussion 聊天查询示例

```json
{
  "object_kinds": ["message"],
  "filters": [
    { "field": "state", "op": "eq", "value": "active" },
    { "field": "strand_id", "op": "eq", "value": "ak:strand:AbhmeQ4M4-eW5loBbZkKXaGD-nYJmCb0CFGR5f42neL-" },
    { "field": "track_name", "op": "eq", "value": "discussion" }
  ],
  "order_by": [
    { "field": "created_at", "direction": "asc" }
  ]
}
```

### 5.3 Strand 上下文权限裁剪

使用 `query.schema.json#/$defs/query_request_body` 登记的 `context_ref` 查询 Strand 时，projection
MUST NOT 因为 actor 可读 Strand synthesis 就展开未被有效 access policy 授权的 discussion timeline。
请求不得携带该 closed schema 未声明的投影或授权控制字段。

## 6. Board Projection

### 6.1 概念映射

| 产品概念 | 协议对象 | 说明 |
| --- | --- | --- |
| 看板 | Board Space | 标准 Space 对象；授权、历史、E2EE 与 policy 仍解析到其 home Realm。 |
| 列/泳道 | List Space | Board Space 内有序容器。 |
| 卡片 | `strand` | 标准工作对象；是否呈现为卡片由 View renderer 和 item_render 决定。 |
| 卡片属于列 | 派生 `contains` projection | 真源是 `ak.component.strand.position.v1:<board_space_id>:<strand_id>` position cell；写入走 `ak.strand.move` / `ak.strand.reorder`，不得创建 canonical Relation。 |
| 列属于看板 | 派生 `contains` projection | 真源是 `ak.component.space.parent.v1:<list_space_id>` parent cell；写入走 `ak.space.parent`，不得创建 canonical Relation。 |
| 讨论入口 | `tracks` map 中 key `discussion` 对应的 entry | 讨论能力属于同一个 Strand；access 完全继承 Strand 的 effective scope（由 `Strand.scope_circle_id` 决定，null=Realm-default，否则=该 [Circle](./circle.md)）。 |

### 6.2 Board 不显示全 Realm 数据

Board projection MUST NOT 默认显示 Realm 中的全部 Strand。实现 MUST 按以下顺序确定可见内容：

1. 根据 View query 找到目标 Board。
2. 查询 `board --contains--> list` 得到列集合。
3. 查询 `list --contains--> strand` 得到候选 Strand。
4. 按 actor 的 Realm membership、capability 和 `allowed_tracks` action scope 裁剪不可见对象和字段。track scope 只缩小已授权动作范围，不授予独立 track-level ACL。
5. 按 List/Strand rank 和稳定 tie-break 排序。

### 6.3 Board 本地派生边界

Board 展示由客户端按 §6.2 从已授权对象图本地派生，不登记独立的 v1 wire response 类型，也不要求服务端提供 View projection HTTP 入口。

单个 document Morph 的受托读取面是 `GET /_arkret/self/realms/{realm_id}/morphs/{morph_id}`（operation `ak.self.morph.resource.get.v1`）。响应 schema 为 `schemas/view.schema.json#/$defs/document_morph_projection_outcome`，用于返回授权可见的 `document`、`versions`、`relations`、`comments` 与 `cursor_presence` 派生数据；它不是 document 的 canonical state，客户端仍以 Morph/Relation/Message/Event 历史和返回的 projection frontier 做校验。

## 7. Timeline / Chat Projection

Discussion chat projection 以 `strand_id + track_name=discussion` 为时间线根，主要返回 Message。

Strand context timeline 可以混合：

- Strand update events
- discussion 可见 Message 摘要
- Relation changes
- review / approval notes
- agent protocol session activity

混合 timeline 必须保持每个来源对象的权限裁剪，不能因为进入同一上下文投影而合并权限。

## 8. Graph / Tree Projection

Graph projection 可展开 Strand、Morph、Message、Board 等对象之间的 Relation。

去中心化网络中，Realm 构成严格权限边界。Projection executor 在执行带有 `depth` 的深度查询时，遇到跨 Realm 引用 MUST 截断并返回 Lazy Link，不能自动跨 Realm 拼接图谱。

## 9. 排序与计数

排序规则：

1. 明确 Relation rank 优先。
2. 无 rank 时使用对象字段排序。
3. 同一排序键完全相同时，tie-break MUST 依次使用 `rank_source_event_hlc`、`rank_source_actor_id`、`rank_source_event_id`、对象 id。

   其中 `rank_source_event_hlc` / `rank_source_actor_id` / `rank_source_event_id` 是 projection 派生量，分别取自决定该条目当前排序位次的来源 Event 的 `hlc`、`actor_id` 与 event id（见 [`event-and-patch.md`](./event-and-patch.md) §2.2 Event Envelope），并非对象上的独立 wire 字段。

计数规则：

- 普通客户端可见计数 MUST 基于权限裁剪后的 visible items。
- 除非 policy 明确允许聚合泄漏，否则不得返回隐藏对象的精确数量。

## 10. 设计决定

Arkret v1 固定：

- View 投影 Strand、Message、Morph 和 Realm workflow。
- Board Space 和 List Space 是 `Space.kind`，不是 `View.kind`。
- 看板拖拽使用 `ak.strand.move` / `ak.strand.reorder`。
- discussion chat 使用 `strand + message`。
- Graph / Tree 遇到跨 Realm 必须 lazy link。
- View projection 输出不得成为真相源。

## 11. 规范性引用

- Query JSON schema 见 [`../conformance/query-schema.md`](../conformance/query-schema.md)。
- Strand / Message 规则见 [strand-and-message.md](./strand-and-message.md)。
- Realm / Space 语义见 [realm-and-space.md](./realm-and-space.md)。
- Morph / facets 见 [morph.md](./morph.md)。
- Relation 基数与跨 Realm 见 [relation.md](./relation.md)。
- View 展示字段只是 UI hint，不能扩大读取权限。
