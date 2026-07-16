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

View 的 `title`、`query`、`kind`、`renderer`、`visible_fields`、`layout`、typed config 和共享可见性属于 View 自身的 canonical state。它们可以通过 `ak.view.create` / `ak.view.update` 修改、签名、审计和同步。

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

Board Space / List Space 作为容器由 `space.kind` 与 `contains` relation 表达。只有开放对象才主要依赖 `morph_type`。

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
| 修改 Strand 标题、状态、负责人、截止时间 | `ak.strand.update` |
| 切换 Strand 默认 track / 开启 / 关闭 track / 修改 track profile | `ak.strand.tracks.update` |
| 修改 Board Space / List Space 元数据 | `ak.space.update` |
| 发送、编辑、撤回 discussion 消息 | `ak.message.create` / `ak.message.revise` / `ak.message.redact` |
| 改变共享 View filter / sort / group / columns / layout | `ak.view.update` |
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
| `visibility` | no | `enum(private, shared)` |  | View 共享可见性。 |
| `query` | yes | `Query` | 见 [`../conformance/query-schema.md`](../conformance/query-schema.md)。 | 数据查询。 |
| `visible_fields` | no | `array<string>` | dot path。 | 展示字段。 |
| `layout` | no | `object` | UI hint，不是权限。 | 布局配置。 |
| `collection` | conditional | `CollectionConfig` | `kind="collection"` 时 MUST 设置。 | 集合投影配置；看板、表格、日历、甘特、队列、矩阵都由该配置表达。 |
| `timeline` | conditional | `TimelineConfig` | `kind="timeline"` 时 MUST 设置。 | 时间线配置。 |
| `graph` | conditional | `GraphConfig` | `kind="graph"` 时 MUST 设置。 | 图/树遍历配置。 |
| `document` | conditional | `DocumentConfig` | `kind="document"` 时 MUST 设置。 | 文档 section 配置。 |
| `dashboard` | conditional | `DashboardConfig` | `kind="composite"` 时 MUST 设置。命名说明：`composite` 是 response family（§2.2 五大 kind 之一），其 v1 唯一 typed config 是 `DashboardConfig`，故配置字段名取 `dashboard`（与 §4 表中 composite 的唯一 renderer `dashboard` 对齐）；composite 的非 dashboard 形态须由 profile-defined `custom` renderer 承载，v1 core 不再为 composite 引入第二个 typed config 字段。 | 仪表盘 widget 配置。 |
| `sort` | no | `array<SortSpec>` | 与 query sort 等价或补充。 | 排序。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

JSON Schema 对 `kind` 与 typed config 执行互斥约束：`collection` / `timeline` / `graph` / `document` / `composite` 分别只允许携带对应的 `collection` / `timeline` / `graph` / `document` / `dashboard` 配置。`kind="composite"` 的 `dashboard.widgets[]` 至少包含一个 widget；若携带 `renderer`，只能是 `dashboard` 或 profile-defined `custom`。

若某个 UI 操作改变 Strand 所属 List、Strand rank、List rank、Strand discussion Message、Relation 或对象字段，必须使用对应对象 Event；只有改变共享 filter、sort、grouping、visible fields、renderer 或 layout 时才修改 View。个人偏好、临时排序、列宽、折叠状态和本地 pin MUST 使用 actor-private account data 或等价私有 Event。

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
| `board_space_id` | conditional | `id:space` | `mode="relation_container"` 时必填，指向一个 `ak:space: kind=board`。 | Board Space。 |
| `container_relation_kind` | no | `string` | 默认 `contains`。 | root 到 collection/container 的关系。 |
| `item_relation_kind` | conditional | `string` | `mode="relation_container"` 时必填；不得隐式推断。 | container 到 item 的关系。 |
| `start_field` | conditional | `string` | `mode="time_bucket"` 时必填。 | 时间窗口起点字段。 |
| `end_field` | no | `string` |  | 时间窗口终点字段。 |
| `rows_by` / `columns_by` | conditional | `string` | `mode="matrix"` 时必填。 | 矩阵双轴字段。 |
| `hidden_count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 分组计数授权策略。 |

`CollectionGrouping` 只定义读取与呈现分组，不承载写入 policy。WIP 上限及其 `warn | reject | require_review` enforcement 的唯一真相源是目标 `Space(kind=list).fields`，见 [`space-hierarchy.md` §6](./space-hierarchy.md)。View 不得携带 `wip_limit_enforcement`；renderer 可以展示目标 List 的 effective policy，但不得从 View 配置生成、覆盖或放宽写入判定。

### 3.4 完整示例

```json
{
  "id": "ak:view:019641be-0000-7000-8000-000000000000",
  "schema": "ak.schema.view.v1",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "created_by": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example",
  "created_at": "2026-04-26T00:00:00Z",
  "kind": "collection",
  "renderer": "board",
  "title": "Release Strand",
  "visibility": "shared",
  "query": {
    "object_types": ["strand"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "direction": "out",
      "source_ref": "ak:space:019640b6-8000-7000-8000-000000000000",
      "depth": 2
    }
  },
  "collection": {
    "item_object_types": ["strand"],
    "item_render": "card",
    "item_order_by": [
      { "field": "rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
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
| `collection` | `board`, `list`, `table`, `calendar`, `gantt`, `custom` | `collection` | `CollectionProjectionView` |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `custom` | `timeline` | `TimelineProjectionView` |
| `graph` | `graph`, `tree`, `custom` | `graph` | `GraphProjectionView` |
| `document` | `document`, `custom` | `document` | `DocumentProjectionView` |
| `composite` | `dashboard`, `custom` | `dashboard` | `CompositeProjectionView` |

> `renderer` 的全局枚举(§3.1)允许 `custom` 用于**所有** kind:`custom` 是 profile-defined 展示面 escape hatch,本表每行的常用 renderer 之外都 MAY 取 `custom`(由 profile 声明语义),不参与真相归约。

## 5. Query Model

View 应通过结构化 query 表达对象范围。

建议通用查询形状：

```json
{
  "object_types": ["strand", "morph"],
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
    "object_types": ["strand"],
    "filters": [
    { "field": "metadata.fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "state", "op": "eq", "value": "active" }
  ],
  "relation": {
    "kind": "contains",
    "direction": "out",
    "source_ref": "ak:space:019640b6-8000-7000-8000-000000000000",
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
    { "field": "strand_id", "op": "eq", "value": "ak:strand:01964200-0000-7000-8000-000000000000" },
    { "field": "track_name", "op": "eq", "value": "discussion" }
  ],
  "order_by": [
    { "field": "created_at", "direction": "asc" }
  ]
}
```

### 5.3 Strand 上下文查询示例

```json
{
  "context_ref": "ak:strand:019640f9-8000-7000-8000-000000000000",
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

Strand context MUST NOT 因为 actor 可读 Strand synthesis 就展开未被有效 access policy 授权的 discussion timeline。

## 6. Board Projection

### 6.1 概念映射

| 产品概念 | 协议对象 | 说明 |
| --- | --- | --- |
| 看板 | Board Space | 标准 Space 对象；授权、历史、E2EE 与 policy 仍解析到其 home Realm。 |
| 列/泳道 | List Space | Board Space 内有序容器。 |
| 卡片 | `strand` | 标准工作对象；是否呈现为卡片由 View renderer 和 item_render 决定。 |
| 卡片属于列 | `Relation{relation_kind="contains", from_ref=list_id, to_ref=strand_id}` | 表示 List 与 Strand 的 canonical 包含关系。 |
| 列属于看板 | `Relation{relation_kind="contains", from_ref=board_id, to_ref=list_id}` | 表示 Board 与 List 的 canonical 包含关系。 |
| 讨论入口 | `tracks` map 中 key `discussion` 对应的 entry | 讨论能力属于同一个 Strand；access 完全继承 Strand 的 effective scope（由 `Strand.scope_circle_id` 决定，null=Realm-default，否则=该 [Circle](./circle.md)）。 |

### 6.2 Board 不显示全 Realm 数据

Board projection MUST NOT 默认显示 Realm 中的全部 Strand。实现 MUST 按以下顺序确定可见内容：

1. 根据 View query 找到目标 Board。
2. 查询 `board --contains--> list` 得到列集合。
3. 查询 `list --contains--> strand` 得到候选 Strand。
4. 按 actor 的 Realm membership、capability 和 `allowed_tracks` action scope 裁剪不可见对象和字段。track scope 只缩小已授权动作范围，不授予独立 track-level ACL。
5. 按 List/Strand rank 和稳定 tie-break 排序。

### 6.3 Board Projection Response

客户端、SDK 或可选受托 projection 扩展 MAY 为 `View{kind="collection", renderer="board"}` 生成已经物化的 `CollectionProjectionView`。响应是派生结果，不是真相源。

```json
{
  "projection": "collection",
  "renderer": "board",
  "view_id": "ak:view:019641be-0000-7000-8000-000000000000",
  "frontier": {
    "state_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "event_ids": ["ak:event:019641be-0000-7000-8000-000000000001"]
  },
  "groups": [
    {
      "key": "ak:space:019641be-0000-7000-8000-000000000010",
      "title": "Review",
      "rank": "mV",
      "limited": false,
      "items": [
        {
          "object": {
            "id": "ak:strand:019641be-0000-7000-8000-000000000011",
            "type": "strand",
            "title": "Legal review"
          },
          "position": {
            "model": "relation",
            "scope_container_id": "ak:space:019641be-0000-7000-8000-000000000009",
            "container_id": "ak:space:019641be-0000-7000-8000-000000000010",
            "relation_kind": "contains",
            "relation_id": "ak:relation:019641be-0000-7000-8000-000000000012",
            "rank": "mV"
          },
          "state": {
            "discussion": {
              "enabled": true,
              "visibility": "locked",
              "lazy_link": true
            }
          }
        }
      ]
    }
  ]
}
```

可选受托 projection 服务若声明 `ak.self.views.collection_projection.command.materialize`，MUST 以 `POST /_arkret/self/views/{view_id}/projection` 暴露上面的 `CollectionProjectionView` 形态，request body 只承载分页参数（`schemas/view.schema.json#/$defs/view_projection_request_body`）。该 operation 只物化 `View{kind="collection"}`，其它 View projection 仍可由客户端本地或未来 profile 定义的受托面计算。

单个 document Morph 的受托读取面是 `GET /_arkret/self/realms/{realm_id}/morphs/{morph_id}`（operation `ak.self.morph.resource.get`）。响应 schema 为 `schemas/view.schema.json#/$defs/document_morph_projection_outcome`，用于返回授权可见的 `document`、`versions`、`relations`、`comments` 与 `cursor_presence` 派生数据；它不是 document 的 canonical state，客户端仍以 Morph/Relation/Message/Event 历史和返回的 projection frontier 做校验。

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
