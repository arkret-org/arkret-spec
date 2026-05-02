# View Model

## 1. 目标

Contrix 必须对人类友好，因此协议必须允许对象自然投影为：

- 看板、列表、表格、日历、甘特图
- 时间线、活动流、聊天、话题论坛、单线程讨论
- 图谱、树
- 文档
- dashboard、审阅队列、inbox、notification、agent 运行轨迹

这些展示模式都是 View projection。View 本身是一个可签名、可共享、可授权的协议对象，但它拥有的是**投影定义的真相**，不是被投影对象的协作事实。

View 可以持有：

- 查询范围
- 过滤、排序、分组
- renderer / layout / visible fields
- shared saved view 配置
- materialization hint / cache policy（不是缓存内容本身）

View 不拥有：

- Board 包含哪些 List
- List 包含哪些 Card
- Card 的标题、状态、负责人、rank、归档状态
- Room 的成员、消息、E2EE epoch、history visibility
- Relation、Capability、Policy 等协作事实

这些对象事实必须从同一套底层结构产生：

```txt
Space + Actor + Room + Board + List + Card + Message + Morph + Relation + Event
```

View 的职责是观察和组织协作图，而不是替代标准对象、Relation 或 Event 成为新的业务真相源。

## 2. 设计原则

### 2.1 View 有定义真相，但不是对象真相

View 的 `title`、`query`、`kind`、`renderer`、`visible_fields`、`layout`、typed config 和共享可见性属于 View 自身的 canonical state。它们可以通过 `cx.view.create` / `cx.view.update` 修改、签名、审计和同步。

View 不承载被投影对象的 canonical state。Board / List / Card / Room / Message / Morph / Relation 的当前态必须由对应对象事件和 reducer 得到。Index / AppView 输出必须能追溯到 signed Event / Operation、reducer profile 和 causal frontier。

Materialized View cache 只是加速层。缓存丢失、过期或迁移后，系统 MUST 能用 View definition + canonical object graph 重新计算 projection。

### 2.1.1 Shared View 与 Personal View

v1 区分两类 View 状态：

| 类别 | 存储位置 | 写入语义 |
| --- | --- | --- |
| Shared View | Space canonical state | 团队共享的 query、renderer、默认列、共享 filter、共享 layout、review queue 定义等，使用 `cx.view.create` / `cx.view.update`。 |
| Personal View | actor-private account data | 个人排序偏好、临时 filter、列宽、折叠状态、最近打开 tab、本地 pin、密度设置等，使用 `cx.account_data.set` 或等价私有 Event。 |

客户端 MUST NOT 把个人 UI 偏好写入 Space shared View，除非用户明确执行“保存为共享视图”或 Space policy 要求共享配置。Index / AppView 在返回 projection 时 MAY 合并 Shared View 与调用者 Personal View，但必须在响应元数据中保留 shared definition frontier 与 personal preference revision 的区别，避免把个人偏好传播给其他成员。

### 2.2 标准对象优先，Morph 扩展

View 查询 SHOULD 优先使用标准对象类型：

- `room`
- `board`
- `list`
- `card`
- `message`
- `morph`

只有开放对象才主要依赖 `morph_type` 和 `facets`。标准对象 MAY 通过 facets 增加能力，但 View 不应把标准对象降级为 Morph。

### 2.3 同一对象可以进入多个 View

一个 Card 可以同时出现在：

- `collection` 投影 + `renderer=board`
- `collection` 投影 + `renderer=row`
- `collection` 投影 + `renderer=calendar`
- `graph` 投影中的依赖节点
- `timeline` 投影中的上下文锚点

一个 Message 可以同时出现在：

- Room chat timeline
- Card context timeline
- mention inbox
- audit/review timeline

同一个 Morph 也可以通过不同 Relation 同时参与树、图谱、审阅队列和 inbox。

### 2.4 少数响应形态，多种展示 renderer

协议保留 5 个 `View.kind` 作为 response family：

- `collection`
- `timeline`
- `graph`
- `document`
- `composite`

这些 `kind` 只约束响应 contract、cursor 和 frontier，不代表对象职责。新增产品形态 SHOULD 优先新增 renderer / profile，而不是新增顶层 `kind`。

### 2.5 Card / Room 权限独立

View 展示 Card 关联 Room 时，必须分别执行授权裁剪：

- 用户能看 Card，不自动能看 linked Room。
- 用户能看 linked Room，不自动能看 Card。
- Card context view MAY 显示不可见 Room 的 locked link，但不得泄露 Room 标题、成员、消息摘要或统计，除非 Room discovery policy 允许。

### 2.6 交互写入必须落回真实对象

客户端 MAY 在 View 中提供拖拽、编辑、批量操作和快捷入口，但写入语义必须落到对应标准对象、Relation 或 Account Data：

| 用户动作 | canonical operation |
| --- | --- |
| Card 拖到另一个 List | `cx.card.move` |
| Card 在同一 List 内排序 | `cx.card.reorder` |
| List 在 Board 内排序 | `cx.list.reorder` |
| 修改 Card 标题、状态、负责人、截止时间 | `cx.card.update` |
| 修改 Board / List 元数据 | `cx.board.update` / `cx.list.update` |
| 发送、编辑、删除 Room 消息 | `cx.message.create` / `cx.message.revise` / `cx.message.redact` |
| 为 Card 关联或移除 Room | `cx.card.link_room` / `cx.card.unlink_room` |
| 改变共享 View filter / sort / group / columns / layout | `cx.view.update` |
| 改变个人 View 偏好、临时 filter、列宽、折叠状态 | actor-private account data |

Renderer 不能把 UI 内部状态偷偷变成协议事实。若一个交互会改变协作对象的状态、位置、权限、关系或消息历史，它 MUST 写入对应对象或 Relation；只有改变观察方式时才写入 View。

## 3. View 对象

建议字段：

```json
{
  "id": "cx:view:01JS0VW000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "created_by": "did:web:acme.example.com",
  "kind": "collection",
  "renderer": "board",
  "title": "Release Flow",
  "visibility": "shared",
  "query": {
    "object_types": ["card"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "direction": "out",
      "source_ref": "cx:board:01JS0BD000000000000000000",
      "depth": 2
    }
  },
  "collection": {
    "item_object_types": ["card"],
    "item_render": "card",
    "item_order_by": [
      { "field": "rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_id": "cx:board:01JS0BD000000000000000000",
      "container_relation_kind": "contains",
      "item_relation_kind": "contains",
      "hidden_count_policy": "omit"
    }
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at",
    "fields.labels"
  ]
}
```

上述字段是 View 自己拥有的定义真相。它们决定“如何看”对象图，但不改变对象图本身。若 `renderer="board"` 的 View 指向某个 Board，它只是说明使用 board renderer 展示该 Board 及其 List/Card 关系；Board/List/Card 的存在、包含关系和排序仍由 `board`、`list`、`card` 与 `contains` Relation 决定。

## 4. 标准 `kind` 与 `renderer`

| Core kind | 常用 renderer | 必填配置 | 标准投影响应 |
| --- | --- | --- | --- |
| `collection` | `board`, `row`, `table`, `calendar`, `gantt`, `custom` | `collection` | `CollectionProjectionResponse` |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `custom` | `timeline`; 会话类还需要 `conversation` 或 anchor/relation | `TimelineProjectionResponse` |
| `graph` | `graph`, `tree` | `graph` | `GraphProjectionResponse` |
| `document` | `document` | `document` | `DocumentProjectionResponse` |
| `composite` | `dashboard` | `dashboard` | `CompositeProjectionResponse` |

Index / AppView 对非 raw projection MUST 返回 `view_id`、`frontier` 和对应核心原语的标准响应。客户端不得把未知对象数组解释为标准 View projection。

## 5. Query Model

View 应通过结构化 query 表达对象范围。

建议通用查询形状：

```json
{
  "object_types": ["card", "morph"],
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

`object_types` 选择标准对象类型。`facets` 只用于需要能力过滤时，尤其是 Morph 或带扩展能力的标准对象。

### 5.1 看板查询示例

```json
{
  "object_types": ["card"],
  "filters": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "archived", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "contains",
    "direction": "out",
    "source_ref": "cx:board:01JS0BD000000000000000000",
    "depth": 2
  }
}
```

### 5.2 Room 聊天查询示例

```json
{
  "object_types": ["message"],
  "filters": [
    { "field": "fields.visible_state", "op": "eq", "value": "active" },
    { "field": "room_id", "op": "eq", "value": "cx:room:01JS1000000000000000000000" }
  ],
  "order_by": [
    { "field": "created_at", "direction": "asc" }
  ]
}
```

### 5.3 Card 上下文查询示例

```json
{
  "anchor_ref": "cx:card:01JS0CD000000000000000000",
  "include": [
    "relations",
    "linked_rooms",
    "recent_messages",
    "dependent_cards",
    "audit_events"
  ],
  "authorization": {
    "locked_room_policy": "lazy_link"
  }
}
```

## 6. Board Projection

### 6.1 概念映射

| 产品概念 | 协议对象 | 说明 |
| --- | --- | --- |
| 看板 | `board` | 标准对象，可被引用、授权、讨论和审计。 |
| 列/泳道 | `list` | Board 内有序容器。 |
| 卡片 | `card` | 标准工作对象。 |
| 卡片属于列 | `Relation{relation_kind="contains", from_ref=list_id, to_ref=card_id}` | 表示 List 与 Card 的 canonical 包含关系；投影中的 `list_id` 是派生字段。 |
| 列属于看板 | `Relation{relation_kind="contains", from_ref=board_id, to_ref=list_id}` | 表示 Board 与 List 的 canonical 包含关系；List 对象中的 `board_id` 不得作为唯一真相源。 |
| Card 讨论 | `Relation{relation_kind="links_room"}` 或 `primary_room` | 不传递权限。 |

### 6.2 Board 不显示全 Space 数据

Board projection MUST NOT 默认显示 Space 中的全部 Card。实现 MUST 按以下顺序确定可见内容：

1. 根据 View query 找到目标 Board。
2. 查询 `board --contains--> list` 得到列集合。
3. 查询 `list --contains--> card` 得到候选 Card。
4. 按 actor 的 Space membership、capability、history visibility、Room/Card access policy 裁剪不可见对象和字段。
5. 按 List/Card rank 和稳定 tie-break 排序。

不在这些 Relation 下的 Card 仍是协议数据，但不属于该 Board 的默认投影。

Board projection MAY 在返回项中携带派生 `board_id`、`list_id`、`rank` 和 `position_relation_id`，用于渲染和 CAS 交互。这些字段必须可追溯到 active `contains` Relation、rank source event 和 reducer frontier；客户端不得把它们回写为 Card canonical fields。

在 Board projection 中拖拽或重排对象时，View 只提供交互入口。实际写入 MUST 使用 `cx.card.move`、`cx.card.reorder` 或 `cx.list.reorder`。实现不得把新的列位置只保存到 View layout 或 materialized projection cache 中。

### 6.3 示例 Board / List / Card

```json
{
  "id": "cx:board:01board",
  "type": "board",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "title": "Launch Board",
  "board_kind": "kanban"
}
```

```json
{
  "id": "cx:list:01review",
  "type": "list",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "board_id": "cx:board:01board",
  "title": "Review",
  "rank": "mV"
}
```

```json
{
  "id": "cx:card:01task",
  "type": "card",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "title": "Legal review",
  "fields": {
    "status": "review",
    "priority": "high",
    "due_at": "2026-05-01T00:00:00Z"
  }
}
```

### 6.4 Card Move

把 Card 从一个 List 拖到另一个 List SHOULD 产生 `cx.card.move`：

```json
{
  "kind": "cx.card.move",
  "target_ref": "cx:card:01task",
  "content": {
    "board_id": "cx:board:01board",
    "card_id": "cx:card:01task",
    "from_list_id": "cx:list:01todo",
    "to_list_id": "cx:list:01review",
    "rank": "mV",
    "expected_position": {
      "list_id": "cx:list:01todo",
      "rank": "h0",
      "relation_id": "cx:relation:01old"
    }
  }
}
```

Reducer 语义：

1. 验证 actor 对 board、from list、to list 和 card 的 move/reorder 权限。
2. 验证 `to_list_id` 属于目标 Board。
3. 关闭同一 `(board_id, card_id)` 下其他 active list position edge。
4. 创建或更新 `to_list_id --contains--> card_id` 的 active Relation，并设置 rank。
5. 对相同 Operation 保持幂等。

### 6.5 Card Reorder

同一 List 内排序 SHOULD 使用 `cx.card.reorder`：

```json
{
  "kind": "cx.card.reorder",
  "target_ref": "cx:card:01task",
  "content": {
    "board_id": "cx:board:01board",
    "list_id": "cx:list:01review",
    "card_id": "cx:card:01task",
    "rank": "mV",
    "expected_position": {
      "rank": "h0",
      "relation_id": "cx:relation:01pos"
    }
  }
}
```

### 6.6 Board Projection Response

Index / AppView MAY 为 `View{kind="collection", renderer="board"}` 返回已经物化的 `CollectionProjectionResponse`。响应是派生结果，不是真相源。

```json
{
  "kind": "collection",
  "renderer": "board",
  "view_id": "cx:view:01JS0VW000000000000000000",
  "frontier": ["cx:event:..."],
  "groups": [
    {
      "group_id": "cx:list:01review",
      "title": "Review",
      "rank": "mV",
      "items": [
        {
          "object": {
            "id": "cx:card:01task",
            "type": "card",
            "title": "Legal review"
          },
          "position": {
            "relation_id": "cx:relation:01pos",
            "rank": "mV"
          },
          "linked_rooms": [
            {
              "room_id": "cx:room:01review",
              "visibility": "accessible",
              "purpose": "review"
            },
            {
              "room_id": "cx:room:01private",
              "visibility": "locked",
              "lazy_link": true
            }
          ]
        }
      ]
    }
  ]
}
```

## 7. Timeline / Chat Projection

Room chat projection 以 `room_id` 为时间线根，主要返回 Message。

Card context timeline 可以混合：

- Card update events
- linked Room 可见 Message 摘要
- Relation changes
- Review / approval notes
- Run / agent activity

混合 timeline 必须保持每个来源对象的权限裁剪，不能因为进入同一上下文投影而合并权限。

## 8. Graph / Tree Projection

Graph projection 可展开 Card、Morph、Room、Board 等对象之间的 Relation。

去中心化网络中，Space 构成严格权限边界。Index 节点在执行带有 `depth` 的深度查询时，遇到跨 Space 引用 MUST 截断并返回 Lazy Link，不能自动跨 Space 拼接图谱。

Lazy Link 示例：

```json
{
  "ref": "cx:card:external_01",
  "space_id": "cx:space:external",
  "lazy_link": true,
  "edge_kind": "references"
}
```

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

- View 投影标准对象和 Morph，不再以 Entity 为中心。
- Board 是标准对象，List 是标准对象，Card 是标准对象。
- Card 和 Room 可关联，但权限独立。
- 看板拖拽使用 `cx.card.move` / `cx.card.reorder`。
- Room chat 使用 `room + message`。
- Graph / Tree 遇到跨 Space 必须 lazy link。
- View / Index 输出不得成为真相源。

## 11. 规范性引用

- Query JSON schema 见 `../conformance/query-schema.md`。
- Room / Message 规则见 `conversation-model.md`。
- Board / List / Card / Morph 标准对象见 `object-model-standard.md`。
- View 展示字段只是 UI hint，不能扩大读取权限。
