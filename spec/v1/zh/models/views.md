---
title: View Model
---

## 1. 目标

Contrix 必须对人类友好，因此协议必须允许对象自然投影为：

- 看板、列表、表格、日历、甘特图
- 时间线、活动流、聊天、话题论坛、单线程讨论
- 图谱、树
- 文档
- dashboard、审阅队列、inbox、notification、agent 运行轨迹

这些展示模式都是 View projection。View 本身是一个可签名、可共享、可授权的协议对象，但它拥有的是投影定义的真相，不是被投影对象的协作事实。

## 2. 设计原则

### 2.1 View 有定义真相，但不是对象真相

View 的 `title`、`query`、`kind`、`renderer`、`visible_fields`、`layout`、typed config 和共享可见性属于 View 自身的 canonical state。它们可以通过 `cx.view.create` / `cx.view.update` 修改、签名、审计和同步。

View 不承载被投影对象的 canonical state。Board Place / List Place / Flow / Message / Morph / Relation 的当前态必须由对应对象事件和 reducer 得到。任何 View projection 输出都必须能追溯到 signed Event、reducer profile 和 causal frontier。

这些对象事实必须从同一套底层结构产生：

```txt
Space + Actor + Flow + Message + Morph + Relation + Event
```

### 2.2 View.kind 是响应族，不是产品名

协议保留 5 个 `View.kind` 作为 response family：

- `collection`
- `timeline`
- `graph`
- `document`
- `composite`

`board`、`list`、`table`、`calendar`、`gantt`、`chat`、`thread`、`forum`、`dashboard` 都是 renderer，而不是新的 `View.kind`。

### 2.3 Board Place / List Place 是 Place.kind，不是 View.kind

Board Place 与 List Place 是 `Place` 的 `kind`（详见 [space-and-place.md](./space-and-place.md)）：

- `Place(kind=board)`
- `Place(kind=list)`

看板和列表投影应表达为：

- `kind=”collection” + renderer=”board”`
- `kind=”collection” + renderer=”list”`

View 负责”如何看”，Board Place / List Place 负责”对象如何被组织”。

### 2.4 Query SHOULD 优先面向 Flow / Message / Morph

View 查询 SHOULD 优先使用标准对象类型：

- `flow`
- `message`
- `morph`

Board Place / List Place 作为容器由 `place.kind` 与 `contains` relation 表达。只有开放对象才主要依赖 `morph_type`。

### 2.5 权限必须逐对象、按有效 track access 裁剪

View 展示 Flow 讨论时，必须分别执行授权裁剪：

- 用户能看 Flow synthesis，只有在有效 access policy 继承或授予 discussion 读取时，才可看 discussion。
- 用户能看 discussion，不自动能改 Flow synthesis。
- Board projection MAY 显示 discussion locked link，但不得泄露 discussion 标题、成员、消息摘要或统计，除非 policy 明确允许。

### 2.6 交互写入必须落回真实对象

客户端 MAY 在 View 中提供拖拽、编辑、批量操作和快捷入口，但写入语义必须落到对应标准对象、Relation 或 Account Data：

| 用户动作 | canonical event |
| --- | --- |
| Flow 拖到另一个 List | `cx.flow.move` |
| Flow 在同一 List 内排序 | `cx.flow.reorder` |
| 修改 Flow 标题、状态、负责人、截止时间 | `cx.flow.update` |
| 切换 Flow 默认 track / 开启 / 关闭 track / 修改 track profile | `cx.flow.tracks.update` |
| 修改 Board Place / List Place 元数据 | `cx.place.update` |
| 发送、编辑、撤回 discussion 消息 | `cx.message.create` / `cx.message.revise` / `cx.message.redact` |
| 改变共享 View filter / sort / group / columns / layout | `cx.view.update` |
| 改变个人 View 偏好、临时 filter、列宽、折叠状态 | actor-private account data |

## 3. View 对象

### 3.1 Schema 与字段

Schema id: `cx.schema.view.v1`

View 是投影定义对象。它的 canonical state 只覆盖"如何看"：query、kind、renderer、typed config、visible fields、layout 和共享配置。它不得作为被投影对象的状态、位置、关系、权限或消息历史的唯一来源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:view` |  | View ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `kind` | yes | `enum(collection, timeline, graph, document, composite)` |  | 核心投影原语。 |
| `renderer` | no | `enum(board, card, row, table, calendar, gantt, timeline, thread, chat, forum, graph, tree, document, dashboard, custom)` | 不参与真相归约。 | 展示面提示；交互能力仍由对象类型、显式 schema/profile、capability 与 typed config 决定。 |
| `title` | no | `string` |  | View 名称。 |
| `query` | yes | `Query` | 见 [`../conformance/query-schema.md`](../conformance/query-schema.md)。 | 数据查询。 |
| `visible_fields` | no | `array<string>` | dot path。 | 展示字段。 |
| `layout` | no | `object` | UI hint，不是权限。 | 布局配置。 |
| `collection` | conditional | `CollectionConfig` | `kind="collection"` 时 MUST 设置。 | 集合投影配置；看板、表格、日历、甘特、队列、矩阵都由该配置表达。 |
| `timeline` | conditional | `TimelineConfig` | `kind="timeline"` 时 MUST 设置。 | 时间线配置。 |
| `conversation` | conditional | `ConversationConfig` | 会话/讨论类 renderer SHOULD 设置，或 query 必须提供 anchor/relation。 | 会话配置。 |
| `graph` | conditional | `GraphConfig` | `kind="graph"` 时 MUST 设置。 | 图/树遍历配置。 |
| `document` | conditional | `DocumentConfig` | `kind="document"` 时 MUST 设置。 | 文档 section 配置。 |
| `dashboard` | conditional | `DashboardConfig` | `kind="composite"` 时 MUST 设置。 | 仪表盘 widget 配置。 |
| `sort` | no | `array<SortSpec>` | 与 query sort 等价或补充。 | 排序。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

若某个 UI 操作改变 Flow 所属 List、Flow rank、List rank、Flow discussion Message、Relation 或对象字段，必须使用对应对象 Event；只有改变共享 filter、sort、grouping、visible fields、renderer 或 layout 时才修改 View。个人偏好、临时排序、列宽、折叠状态和本地 pin MUST 使用 actor-private account data 或等价私有 Event。

### 3.2 `CollectionConfig`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_object_types` | conditional | `array<string>` | 可由 `item_facets` 替代；至少 1 项。 | 按对象类型过滤可投影为 item/card/row/message 的对象。 |
| `item_facets` | conditional | `array<FacetName>` | 可替代 `item_object_types`；至少 1 项。 | 按声明 hint 选择 item，例如 `rankable`、`reviewable`、`replyable`。 |
| `item_render` | yes | `enum(card, row, tile, compact, badge, message)` | 看板式展示 SHOULD 为 `card`。 | 默认展示面。 |
| `item_order_by` | yes | `array<SortSpec>` | 至少 1 项。 | item 稳定排序；拖拽类 collection SHOULD 使用 rank。 |
| `display_fields` | no | `array<DisplayColumn>` | dot path。 | 展示字段与格式。 |
| `grouping` | yes | `CollectionGrouping` |  | 分组/列/时间桶/矩阵配置。 |
| `selection_policy` | no | `enum(none, single, multiple)` | 默认 `multiple`。 | UI 选择策略。 |
| `count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 集合级计数策略。 |
| `page_size` | no | `integer` | 1..1000。 | 默认分页大小。 |

### 3.3 `CollectionGrouping`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | yes | `enum(none, field, relation_container, time_bucket, matrix)` |  | 分组模型。 |
| `field` | conditional | `string` | `mode="field"` 时必填。 | 字段分组路径。 |
| `lanes` | conditional | `array<object>` | `mode="field"` 时必填。 | 字段值列/泳道定义。 |
| `board_place_id` | conditional | `id:place` | `mode="relation_container"` 时必填，指向一个 `cx:place: kind=board`。 | Board Place。（旧名 `board_id` 已替换为 `board_place_id` 以避免与 Space ID 误读）|
| `container_relation_kind` | no | `string` | 默认 `contains`。 | root 到 collection/container 的关系。 |
| `item_relation_kind` | conditional | `string` | `mode="relation_container"` 时必填；不得隐式推断。 | container 到 item 的关系。 |
| `start_field` | conditional | `string` | `mode="time_bucket"` 时必填。 | 时间窗口起点字段。 |
| `end_field` | no | `string` |  | 时间窗口终点字段。 |
| `rows_by` / `columns_by` | conditional | `string` | `mode="matrix"` 时必填。 | 矩阵双轴字段。 |
| `hidden_count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 分组计数授权策略。 |
| `wip_limit_enforcement` | no | `enum(warn, reject, require_review)` | 默认 `warn`。 | 分组 WIP enforcement；只影响 reducer / review policy，不由 renderer 决定。 |

### 3.4 完整示例

```json
{
  "id": "cx:view:019641be-0000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "created_by": "did:web:acme.example.com",
  "kind": "collection",
  "renderer": "board",
  "title": "Release Flow",
  "visibility": "shared",
  "query": {
    "object_types": ["flow"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "direction": "out",
      "source_ref": "cx:place:019640b6-8000-7000-8000-000000000000",
      "depth": 2
    }
  },
  "collection": {
    "item_object_types": ["flow"],
    "item_render": "card",
    "item_order_by": [
      { "field": "rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_place_id": "cx:place:019640b6-8000-7000-8000-000000000000",
      "container_relation_kind": "contains",
      "item_relation_kind": "contains",
      "hidden_count_policy": "omit"
    }
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at"
  ]
}
```

上述字段是 View 自己拥有的定义真相。它们决定“如何看”对象图，但不改变对象图本身。

## 4. 标准 `kind` 与 `renderer`

| Core kind | 常用 renderer | 必填配置 | 标准投影响应 |
| --- | --- | --- | --- |
| `collection` | `board`, `list`, `table`, `calendar`, `gantt`, `custom` | `collection` | `CollectionProjectionResponse` |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `custom` | `timeline` | `TimelineProjectionResponse` |
| `graph` | `graph`, `tree` | `graph` | `GraphProjectionResponse` |
| `document` | `document` | `document` | `DocumentProjectionResponse` |
| `composite` | `dashboard` | `dashboard` | `CompositeProjectionResponse` |

## 5. Query Model

View 应通过结构化 query 表达对象范围。

建议通用查询形状：

```json
{
  "object_types": ["flow", "morph"],
  "facets": ["reviewable"],
  "filters": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] }
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
    "object_types": ["flow"],
    "filters": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "state", "op": "eq", "value": "active" }
  ],
  "relation": {
    "kind": "contains",
    "direction": "out",
    "source_ref": "cx:space:019640b6-8000-7000-8000-000000000000",
    "depth": 2
  }
}
```

### 5.2 Discussion 聊天查询示例

```json
{
  "object_types": ["message"],
  "filters": [
    { "field": "state", "op": "eq", "value": "active" },
    { "field": "flow_id", "op": "eq", "value": "cx:flow:01964200-0000-7000-8000-000000000000" },
    { "field": "track", "op": "eq", "value": "discussion" }
  ],
  "order_by": [
    { "field": "created_at", "direction": "asc" }
  ]
}
```

### 5.3 Flow 上下文查询示例

```json
{
  "anchor_ref": "cx:flow:019640f9-8000-7000-8000-000000000000",
  "include": [
    "relations",
    "synthesis",
    "discussion_preview",
    "activity_events",
    "audit_events"
  ],
  "authorization": {
    "locked_discussion_policy": "lazy_link"
  }
}
```

Flow context MUST NOT 因为 actor 可读 Flow synthesis 就展开未被有效 access policy 授权的 discussion timeline。

## 6. Board Projection

### 6.1 概念映射

| 产品概念 | 协议对象 | 说明 |
| --- | --- | --- |
| 看板 | Board Place | 标准 Space 对象，可被引用、授权、讨论和审计。 |
| 列/泳道 | List Place | Board Place 内有序容器。 |
| 卡片 | `flow` | 标准工作对象；是否呈现为卡片由 View renderer 和 item_render 决定。 |
| 卡片属于列 | `Relation{relation_kind="contains", from_ref=list_id, to_ref=flow_id}` | 表示 List 与 Flow 的 canonical 包含关系。 |
| 列属于看板 | `Relation{relation_kind="contains", from_ref=board_id, to_ref=list_id}` | 表示 Board 与 List 的 canonical 包含关系。 |
| 讨论入口 | `tracks` map 中 key `discussion` 对应的 entry | 讨论能力属于同一个 Flow；access 完全继承父 Space，独立访问域通过 `Flow.discussion_space_ref` 升级到 child Space。 |

### 6.2 Board 不显示全 Space 数据

Board projection MUST NOT 默认显示 Space 中的全部 Flow。实现 MUST 按以下顺序确定可见内容：

1. 根据 View query 找到目标 Board。
2. 查询 `board --contains--> list` 得到列集合。
3. 查询 `list --contains--> flow` 得到候选 Flow。
4. 按 actor 的 Space membership、capability 和有效 track access 裁剪不可见对象和字段。
5. 按 List/Flow rank 和稳定 tie-break 排序。

### 6.3 Board Projection Response

客户端、SDK 或可选受托 projection 扩展 MAY 为 `View{kind="collection", renderer="board"}` 生成已经物化的 `CollectionProjectionResponse`。响应是派生结果，不是真相源。

```json
{
  "kind": "collection",
  "renderer": "board",
  "view_id": "cx:view:019641be-0000-7000-8000-000000000000",
  "frontier": ["cx:event:..."],
  "groups": [
    {
      "group_id": "cx:space:01c3b617-7000-7000-8000-000000000000",
      "title": "Review",
      "rank": "mV",
      "items": [
        {
          "object": {
            "id": "cx:flow:01d2b330-0000-7000-8000-000000000000",
            "title": "Legal review"
          },
          "position": {
            "relation_id": "cx:relation:01b03200-0000-7000-8000-000000000000",
            "rank": "mV"
          },
          "discussion": {
            "enabled": true,
            "visibility": "locked",
            "lazy_link": true
          }
        }
      ]
    }
  ]
}
```

## 7. Timeline / Chat Projection

Discussion chat projection 以 `flow_id + track=discussion` 为时间线根，主要返回 Message。

Flow context timeline 可以混合：

- Flow update events
- discussion 可见 Message 摘要
- Relation changes
- review / approval notes
- agent protocol session activity

混合 timeline 必须保持每个来源对象的权限裁剪，不能因为进入同一上下文投影而合并权限。

## 8. Graph / Tree Projection

Graph projection 可展开 Flow、Morph、Message、Board 等对象之间的 Relation。

去中心化网络中，Space 构成严格权限边界。Projection executor 在执行带有 `depth` 的深度查询时，遇到跨 Space 引用 MUST 截断并返回 Lazy Link，不能自动跨 Space 拼接图谱。

## 9. 排序与计数

排序规则：

1. 明确 Relation rank 优先。
2. 无 rank 时使用对象字段排序。
3. 同一排序键完全相同时，tie-break MUST 依次使用 `rank_source_event_hlc`、`rank_source_actor_id`、`rank_source_event_id`、对象 id。

计数规则：

- 普通客户端可见计数 MUST 基于权限裁剪后的 visible items。
- 除非 policy 明确允许聚合泄漏，否则不得返回隐藏对象的精确数量。

## 10. 设计决定

Contrix v1 固定：

- View 投影 Flow、Message、Morph 和 Space workflow。
- Board Place 和 List Place 是 `Place.kind`，不是 `View.kind`。
- 看板拖拽使用 `cx.flow.move` / `cx.flow.reorder`。
- discussion chat 使用 `flow + message`。
- Graph / Tree 遇到跨 Space 必须 lazy link。
- View projection 输出不得成为真相源。

## 11. 规范性引用

- Query JSON schema 见 `../conformance/query-schema.md`。
- Flow / Message 规则见 [flow-and-message.md](./flow-and-message.md)。
- Space / Place 语义见 [space-and-place.md](./space-and-place.md)。
- Morph / facets 见 [morph.md](./morph.md)。
- Relation 基数与跨 Space 见 [relation.md](./relation.md)。
- View 展示字段只是 UI hint，不能扩大读取权限。
