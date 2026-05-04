# View Model

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

View 不承载被投影对象的 canonical state。Space (kind=board) / Space (kind=list) / Flow / Message / Morph / Relation 的当前态必须由对应对象事件和 reducer 得到。任何 View projection 输出都必须能追溯到 signed Event、reducer profile 和 causal frontier。

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

### 2.3 Space (kind=board) / Space (kind=list) 是 Space 形态，不是 View.kind

Space (kind=board) 与 Space (kind=list) 是 `Space` 的形态：

- `Space (kind=board)`
- `Space (kind=list)`

看板和列表投影应表达为：

- `kind="collection" + renderer="board"`
- `kind="collection" + renderer="row"` 或 `renderer="list"`

View 负责“如何看”，Space (kind=board) / Space (kind=list) 负责“对象如何被组织”。

### 2.4 Query SHOULD 优先面向 Flow / Message / Morph

View 查询 SHOULD 优先使用标准对象类型：

- `flow`
- `message`
- `morph`

Space (kind=board) / Space (kind=list) 作为容器由 `space.kind` 与 `contains` relation 表达。只有开放对象才主要依赖 `morph_type`。

### 2.5 权限必须逐对象、按有效 branch access 裁剪

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
| 切换 Flow 默认 branch | `cx.flow.convert` / `cx.flow.branch.set_primary` |
| 开启/关闭 discussion branch | `cx.flow.branch.enable` / `cx.flow.branch.disable` |
| 修改 Space (kind=board) / Space (kind=list) 元数据 | `cx.space.update` |
| 发送、编辑、撤回 discussion 消息 | `cx.message.create` / `cx.message.revise` / `cx.message.redact` |
| 改变共享 View filter / sort / group / columns / layout | `cx.view.update` |
| 改变个人 View 偏好、临时 filter、列宽、折叠状态 | actor-private account data |

## 3. View 对象

建议字段：

```json
{
  "id": "cx:view:01js0vw0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
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
      "source_ref": "cx:space:01js0bd0000000000000000000",
      "depth": 2
    }
  },
  "collection": {
    "item_object_types": ["flow"],
    "item_render": "flow_card",
    "item_order_by": [
      { "field": "rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_id": "cx:space:01js0bd0000000000000000000",
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
| `collection` | `board`, `row`, `list`, `table`, `calendar`, `gantt`, `custom` | `collection` | `CollectionProjectionResponse` |
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
    "source_ref": "cx:space:01js0bd0000000000000000000",
    "depth": 2
  }
}
```

### 5.2 Discussion 聊天查询示例

```json
{
  "object_types": ["message"],
  "filters": [
    { "field": "fields.visible_state", "op": "eq", "value": "active" },
    { "field": "flow_id", "op": "eq", "value": "cx:flow:01js1000000000000000000000" },
    { "field": "branch", "op": "eq", "value": "discussion" }
  ],
  "order_by": [
    { "field": "created_at", "direction": "asc" }
  ]
}
```

### 5.3 Flow 上下文查询示例

```json
{
  "anchor_ref": "cx:flow:01js0fk0000000000000000000",
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
| 看板 | Space (kind=board) | 标准 Space 对象，可被引用、授权、讨论和审计。 |
| 列/泳道 | Space (kind=list) | Space (kind=board) 内有序容器。 |
| 卡片 | `flow` | 标准工作对象；是否呈现为卡片由 View renderer 和 item_render 决定。 |
| 卡片属于列 | `Relation{relation_kind="contains", from_ref=list_id, to_ref=flow_id}` | 表示 List 与 Flow 的 canonical 包含关系。 |
| 列属于看板 | `Relation{relation_kind="contains", from_ref=board_id, to_ref=list_id}` | 表示 Board 与 List 的 canonical 包含关系。 |
| 讨论入口 | `branches[]` 中 `name="discussion"` 的 branch | 讨论能力属于同一个 Flow；`branches[].access` 表达继承或 branch-scoped override。 |

### 6.2 Board 不显示全 Space 数据

Board projection MUST NOT 默认显示 Space 中的全部 Flow。实现 MUST 按以下顺序确定可见内容：

1. 根据 View query 找到目标 Board。
2. 查询 `board --contains--> list` 得到列集合。
3. 查询 `list --contains--> flow` 得到候选 Flow。
4. 按 actor 的 Space membership、capability 和有效 branch access 裁剪不可见对象和字段。
5. 按 List/Flow rank 和稳定 tie-break 排序。

### 6.3 Board Projection Response

客户端、SDK 或可选受托 projection 扩展 MAY 为 `View{kind="collection", renderer="board"}` 生成已经物化的 `CollectionProjectionResponse`。响应是派生结果，不是真相源。

```json
{
  "kind": "collection",
  "renderer": "board",
  "view_id": "cx:view:01js0vw0000000000000000000",
  "frontier": ["cx:event:..."],
  "groups": [
    {
      "group_id": "cx:space:01rev1ew000000000000000000",
      "title": "Review",
      "rank": "mV",
      "items": [
        {
          "object": {
            "id": "cx:flow:01task00000000000000000000",
            "title": "Legal review"
          },
          "position": {
            "relation_id": "cx:relation:01p0s000000000000000000000",
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

Discussion chat projection 以 `flow_id + branch=discussion` 为时间线根，主要返回 Message。

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
- Space (kind=board) 和 Space (kind=list) 是 `Space.kind`，不是 `View.kind`。
- 看板拖拽使用 `cx.flow.move` / `cx.flow.reorder`。
- discussion chat 使用 `flow + message`。
- Graph / Tree 遇到跨 Space 必须 lazy link。
- View projection 输出不得成为真相源。

## 11. 规范性引用

- Query JSON schema 见 `../conformance/query-schema.md`。
- Flow / Message 规则见 `conversation-model.md`。
- Flow / Space / Morph 标准对象见 `object-model-standard.md`。
- View 展示字段只是 UI hint，不能扩大读取权限。
