# View Model Draft

## 1. 目标

Contrix New 必须对人类友好，因此协议必须允许对象自然投影为：

- 看板
- 列表
- 表格
- 日历
- 时间线
- 图谱
- 活动流
- 聊天
- 话题论坛
- 单线程讨论
- 记忆审阅队列
- agent 运行轨迹

这些展示模式都必须从同一套底层结构产生：

```txt
Space + Actor + Entity + Relation + Event
```

View 的职责是观察和组织这张协作图，而不是定义新的数据真相。

## 2. 设计原则

### 2.1 View 不是对象真相

view 不承载底层对象的唯一真相状态。

### 2.2 同一对象可以进入多个 view

一个 task Entity 可以同时出现在：

- kanban
- list
- calendar
- thread anchor

一个 message Entity 可以同时出现在：

- chat timeline
- topic thread
- activity feed

同一个 Entity 还可以通过不同 Relation 同时参与树、图谱、甘特图和 inbox。

### 2.3 Shared / Private / System 并存

初版建议支持：

- `shared`
- `private`
- `system`

### 2.4 统一上下文投影（Context Timeline）

同一件事情可能同时需要看板列、依赖图、聊天时间线。  
这类需求不应依赖单一 view，而应使用统一上下文投影：

- 以锚点对象为中心（`anchor_entity_id`）；
- 同时抓取与锚点有关的实体、关系和事件；
- 按统一时序排序（`hlc` 为主，`event_id` 作为稳定 tie-break）；
- 在 UI 上按时间线展示，并允许客户端按卡片/关系/消息分段。

这意味着真相仍是 `Event` + `Entity` + `Relation`，`View` 只是读时组织方式。

## 3. View 对象

建议字段：

```json
{
  "id": "cx:view:01JS0VW000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "created_by": "did:web:acme.example.com",
  "kind": "kanban",
  "name": "Release Flow",
  "visibility": "shared",
  "query": {
    "entity_types": ["task", "issue"],
    "filters": [
      { "field": "archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "from_entity_id": "cx:entity:01JS0BD000000000000000000",
      "depth": 2
    }
  },
  "group_by": "fields.status",
  "order_by": [
    { "field": "fields.rank", "direction": "asc" }
  ],
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at",
    "fields.labels"
  ]
}
```

## 4. 标准 `kind`

### 4.1 工作对象视图

- `kanban`
- `list`
- `table`
- `calendar`
- `timeline`
- `graph`
- `tree`
- `gantt`
- `matrix`
- `document`
- `dashboard`

### 4.2 会话视图

- `chat`
- `forum`
- `thread`
- `activity`
- `inbox`
- `notifications`

### 4.3 审阅与 agent 视图

- `memory_review`
- `agent_runs`
- `context_timeline`

## 5. Query Model

View 应通过结构化 query 表达对象范围。

建议通用查询形状：

```json
{
  "entity_types": ["task"],
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
  "entity_types": ["task", "issue"],
  "filters": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "archived", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "contains",
    "from_entity_id": "cx:entity:01JS0BD000000000000000000",
    "depth": 2
  }
}
```

### 5.2 聊天查询示例

```json
{
  "entity_types": ["message"],
  "filters": [
    { "field": "fields.redacted", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "belongs_to",
    "to_entity_id": "cx:entity:01JS1000000000000000000000",
    "direction": "out"
  }
}
```

### 5.3 话题查询示例

```json
{
  "entity_types": ["topic"],
  "filters": [
    { "field": "fields.status", "op": "eq", "value": "open" }
  ],
  "relation": {
    "kind": "attached_to",
    "to_entity_id": "cx:entity:01JS0TASK0000000000000000",
    "direction": "out"
  }
}
```

### 5.4 通知查询示例

```json
{
  "entity_types": ["message", "task", "invite", "run", "memory"],
  "filters": [
    { "field": "derived.notification_state", "op": "eq", "value": "unread" },
    { "field": "derived.recipient", "op": "eq", "value": "did:web:alice.example.com" }
  ]
}
```

### 5.5 依赖图查询示例

```json
{
  "entity_types": ["task"],
  "relation": {
    "kind": "depends_on",
    "direction": "out",
    "depth": 4
  }
}
```

### 5.6 树形查询示例

```json
{
  "entity_types": ["task", "document", "collection"],
  "relation": {
    "kind": "contains",
    "direction": "out",
    "depth": 8
  }
}
```

### 5.7 跨域深度查询与惰性链接 (Lazy Link)

去中心化网络中，`Space` 构成了严格的权限边界。协议明确禁止 Index 节点在执行带有 `depth` 的深度查询时自动跨越 Space 边界追踪数据，以防止未授权的数据泄露与性能级联。

**截断与回退规则**：
当 Index 在图谱展开过程中遇到指向外部 Space 的 `target_ref` 时，MUST 立即中止该分支的展开。Index 应向查询方返回一个不含底层属性的 **惰性链接 (Lazy Link)**，结构如下：
```json
{
  "id": "cx:entity:external_01",
  "kind": "lazy_link",
  "space_id": "cx:space:target_space_02"
}
```
跨域图谱的完整拼接由 **客户端 (Client)** 负责。如果客户端确定当前 Actor 拥有 `cx:space:target_space_02` 的访问权限，则可主动向该目标 Space 对应的 Index 节点发起二次图查询并自行在 UI 层拼接。

### 5.8 统一上下文查询示例

围绕任务对象聚合其进展、关系、消息与审阅活动：

```json
{
  "anchor_entity_id": "cx:entity:01JS0TASK000000000000000000",
  "entity_types": ["task", "message", "topic", "memory", "relation"],
  "filters": [
    { "field": "fields.archived", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "contains",
    "direction": "both",
    "source_entity_id": "cx:entity:01JS0TASK000000000000000000",
    "depth": 3
  },
  "order_by": [
    { "field": "event_hlc", "direction": "asc" }
  ],
  "context": {
    "event_kinds": [
      "cx.entity.update",
      "cx.relation.create",
      "cx.relation.move",
      "cx.message.create",
      "cx.task.assign",
      "cx.redaction",
      "cx.memory.create"
    ],
    "relation_kinds": [
      "contains",
      "assigned_to",
      "depends_on",
      "replies_to",
      "mentions"
    ],
    "event_tiebreak": "event_id"
  }
}
```

实现要求（context_timeline）：

- `event_hlc` 为上下文时间线排序主键；无 `event_hlc` 时回退 `created_at`，并打上 `timestamp_untrusted` 标记；
- `event_id` 作为 tie-break，保证同序事件排序稳定；
- 未授权对象/关系不得泄漏“存在与不存在”信息，只能裁剪不可见项；
- 同一 `space_frontier` 与同一权限上下文下，重复查询结果应保持可重放一致顺序。

## 6. 分组、排序、显示

### 6.1 `group_by`

初版建议支持：

- `status`
- `assignee`
- `priority`
- `memory_kind`
- `run_status`
- `channel`
- `topic_status`
- `custom:<field_name>`

### 6.2 `order_by`

初版建议支持：

- `rank`
- `created_at`
- `updated_at`
- `due_at`
- `priority`
- `started_at`
- `ended_at`
- `last_message_at`

### 6.3 `visible_fields`

共享最小展示约定，客户端可在不违反权限的前提下做本地增强。

## 7. 标准投影原则

### 7.1 Kanban

Kanban 视图的 canonical 输入应是：

- `entity_type = "board"`
- `entity_type = "collection"`
- `entity_type = "task"` 或其他工作对象
- `kind = "contains"` / `belongs_to`
- `kind = "kanban"`

而不是某种 UI 私有列数组。

#### 7.1.1 看板投影模型

看板 UI 中的元素 MUST 映射到协议对象，而不是只存在于客户端本地状态：

| UI 概念 | Canonical 数据 | 说明 |
| --- | --- | --- |
| 看板 | `Entity{entity_type="board"}` | 看板本身是一个 Entity，可被引用、授权、讨论和审计。 |
| 视图配置 | `View{kind="kanban"}` | 定义查询范围、列来源、排序和展示字段。 |
| 列 | `fields.<group_by>` 的枚举值，或 `Entity{entity_type="collection"}` | 简单工作流用字段分组；复杂工作流用 collection 实体。 |
| 卡片 | `Entity{entity_type="task"}` 或 `issue` / 自定义工作对象 | 卡片不是单独 UI 数据，而是业务 Entity。 |
| 卡片属于看板 | `Relation{kind="contains"}` 或 `belongs_to` | 表示 board/collection 与 task 的包含关系。 |
| 卡片列位置 | `fields.status`，或 task 到 collection 的 Relation | 取决于列模型。 |
| 列内顺序 | `fields.rank` 或 Relation `fields.rank` | 推荐 Fractional Indexing string。 |
| 卡片展示字段 | View `visible_fields` | 只决定显示，不提升权限。 |

Kanban View MUST NOT 默认显示 Space 中的全部数据。实现 MUST 按以下顺序确定可见内容：

1. 先执行 `View.query`，得到该 View 的候选对象集合。
2. 再按 actor 的 Space membership、capability、history visibility、field authorization 裁剪不可见对象和字段。
3. 再按 `kanban.column_model` 计算列和卡片位置。
4. 最后按 `visible_fields` 与客户端展示规则渲染卡片。

因此，Space 中的其他数据仍然是协议数据，但不一定属于当前看板：

- 不满足 `View.query` 的 Entity MUST NOT 出现在该看板中。
- 满足查询但类型不是 View 允许的 card type 的对象 SHOULD 作为投影输入处理，不直接显示为卡片。
- Relation、Event、Capability、Policy、Audit 等对象通常作为投影、授权或审计输入，不作为普通 Kanban 卡片显示。
- `message`、`topic`、`document`、`run`、`memory` 等 Entity 只有在 View 明确把它们列入 `query.entity_types` 并定义 card 显示规则时，才 MAY 作为卡片显示。
- 无权读取的对象或字段 MUST 被裁剪；实现 MUST NOT 用空列、计数或错误信息泄露不可见对象是否存在。

#### 7.1.2 字段分组列模型

简单看板 SHOULD 使用字段分组列模型。此时列不是 durable Entity，而是某个字段的合法取值。

示例 Board Entity：

```json
{
  "id": "cx:entity:01board",
  "type": "entity",
  "space_id": "cx:space:01space",
  "entity_type": "board",
  "title": "Product Launch",
  "fields": {
    "workflow_field": "fields.status",
    "workflow_values": ["todo", "in_progress", "review", "done"]
  }
}
```

示例 Kanban View：

```json
{
  "id": "cx:view:01view",
  "space_id": "cx:space:01space",
  "kind": "kanban",
  "title": "Launch Flow",
  "query": {
    "space_ids": ["cx:space:01space"],
    "entity_types": ["task"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "belongs_to",
      "direction": "out",
      "target_entity_id": "cx:entity:01board"
    },
    "order_by": [
      { "field": "fields.rank", "direction": "asc", "nulls": "last" }
    ]
  },
  "kanban": {
    "column_model": "field_value",
    "group_by": "fields.status",
    "columns": [
      { "key": "todo", "title": "Todo" },
      { "key": "in_progress", "title": "In Progress" },
      { "key": "review", "title": "Review" },
      { "key": "done", "title": "Done" }
    ],
    "card_order_by": [
      { "field": "fields.rank", "direction": "asc", "nulls": "last" }
    ]
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at",
    "fields.labels"
  ]
}
```

示例 Task Entity：

```json
{
  "id": "cx:entity:01task",
  "type": "entity",
  "space_id": "cx:space:01space",
  "entity_type": "task",
  "title": "Finalize release notes",
  "fields": {
    "status": "review",
    "rank": "mV",
    "priority": "high"
  }
}
```

字段分组列模型的投影规则：

1. 先执行 `View.query` 得到候选卡片集合。
2. 对每个卡片读取 `group_by` 指向的字段，例如 `fields.status`。
3. 字段值匹配 `kanban.columns[*].key` 的卡片进入对应列。
4. 字段缺失或值未知时，客户端 SHOULD 放入系统列 `__uncategorized`，或按 View policy 隐藏。
5. 列内按 `card_order_by` 排序；若排序字段缺失，使用 `nulls` 规则和 timeline tie breaker。

在该模型中，把卡片从 `todo` 拖到 `review` MUST 产生对 task 的更新事件，例如：

```json
{
  "type": "cx.entity.update",
  "content": {
    "entity_id": "cx:entity:01task",
    "patch": {
      "fields.status": "review",
      "fields.rank": "mV"
    }
  }
}
```

#### 7.1.3 Collection 列模型

复杂看板 SHOULD 使用 Collection 列模型。此时每一列都是 `Entity{entity_type="collection"}`，适合需要列级权限、列 WIP 限制、列说明、列归档、跨看板复用或列讨论的场景。

示例列 Entity：

```json
{
  "id": "cx:entity:01col_review",
  "type": "entity",
  "space_id": "cx:space:01space",
  "entity_type": "collection",
  "title": "Review",
  "fields": {
    "collection_kind": "kanban_column",
    "wip_limit": 5,
    "rank": "h0"
  }
}
```

Board 包含列：

```json
{
  "id": "cx:relation:01board_col",
  "type": "relation",
  "space_id": "cx:space:01space",
  "kind": "contains",
  "from_entity_id": "cx:entity:01board",
  "to_entity_id": "cx:entity:01col_review",
  "fields": {
    "rank": "h0"
  }
}
```

列包含卡片：

```json
{
  "id": "cx:relation:01col_task",
  "type": "relation",
  "space_id": "cx:space:01space",
  "kind": "contains",
  "from_entity_id": "cx:entity:01col_review",
  "to_entity_id": "cx:entity:01task",
  "fields": {
    "rank": "mV"
  }
}
```

Collection 列模型的投影规则：

1. 从 board 出发查询 `contains` 到 `collection` 的 Relation，得到列集合。
2. 列按 board->collection Relation 的 `fields.rank` 排序；缺失时按 collection `fields.rank` 和 ID tie breaker。
3. 对每个 collection 查询 `contains` 到 task/issue 的 Relation，得到该列卡片。
4. 卡片按 collection->card Relation 的 `fields.rank` 排序。
5. 同一张卡片若被多个 active column 包含，reducer MUST 按 Space version 的冲突规则保留一个有效位置，或将其标记为 conflict 交给客户端解决。

在该模型中，把卡片从列 A 拖到列 B SHOULD 产生 relation move 语义，而不是只改 `fields.status`：

```json
{
  "type": "cx.relation.move",
  "content": {
    "entity_id": "cx:entity:01task",
    "from_container_id": "cx:entity:01col_todo",
    "to_container_id": "cx:entity:01col_review",
    "rank": "mV"
  }
}
```

`cx.relation.move` 的 reducer 语义等价于：删除旧 active containment edge，并创建或更新新 containment edge。实现 MUST 保持该操作幂等。

#### 7.1.4 两种列模型的选择

| 场景 | 推荐模型 | 原因 |
| --- | --- | --- |
| 普通任务状态流转 | 字段分组列模型 | 数据更简单，跨 list/table/calendar 投影自然。 |
| 需要列级权限或 WIP limit | Collection 列模型 | 列本身需要成为可授权对象。 |
| 一张卡片可能进入多个分组视角 | 字段分组列模型 + 多 View | 避免重复 containment。 |
| 列有讨论、归档、负责人、自动化规则 | Collection 列模型 | 列需要 Entity 能力。 |
| 从 Trello/Jira 等桥接导入 | Collection 列模型 MAY 更合适 | 外部列通常有自己的 ID 和配置。 |

两种模型 MAY 共存，但同一个 Kanban View MUST 明确 `kanban.column_model`。客户端 MUST NOT 同时用 `fields.status` 和 collection containment 推导同一张卡片的主列，除非 View 显式声明冲突解决规则。

### 7.2 Chat

Chat 视图的 canonical 输入应是：

- `entity_type = "channel"`
- `entity_type = "topic"`
- `entity_type = "message"`
- `kind = "belongs_to"` / `replies_to` / `mentions`

### 7.3 Topic

Thread/topic 视图的 canonical 输入应是：

- `entity_type = "topic"`
- `entity_type = "message"`
- `kind = "attached_to"` / `belongs_to` / `replies_to`

### 7.4 Graph

Graph 视图的 canonical 输入应是：

- 任意 `entity_type`
- 一个或多个 `kind`
- 展开方向与深度

例如任务依赖图使用 `depends_on`，知识图谱使用 `references` / `derived_from`。

### 7.5 Tree

Tree 视图的 canonical 输入应是：

- 任意可分层 Entity
- `contains` 或 `belongs_to` Relation
- root Entity 与展开深度

## 8. 人类友好性要求

实现 SHOULD 至少保证：

1. 每个核心对象都有默认标题与摘要
2. task Entity 能自然投影为 card 或 row
3. message Entity 能自然投影为 timeline bubble 或 row
4. topic Entity 能自然投影为 forum thread row
5. memory Entity 能自然投影为 review row 或 graph node
6. run Entity 能自然投影为 timeline row 或 activity block
7. notification 能自然投影为 inbox row 或 badge source

## 9. Shared / Private / System

### 9.1 Shared

属于 space，对团队可见。

### 9.2 Private

仅本地保存，或保存在 actor 私有 repo。

### 9.3 System

由协议或产品自动生成，例如：

- Assigned to Me
- Needs Review
- Candidate Memories
- Failed Agent Runs
- Mentioned Messages
- Notifications
- Unread Topics

## 10. 视图权限

创建和修改共享视图应受 capability 控制。

若 view query 命中了用户无权读取的对象，返回结果 MUST 被裁剪。

## 11. 视图退化与兼容

当底层字段或 schema 变化时，view 应优雅退化，而不是破坏数据。

例如：

- 缺少字段时显示 warning
- 被撤回消息显示 tombstone
- graph 缺少 relation 时跳过对应边

## 12. 初版设计决定

当前草案建议固定：

- View 是独立对象
- Query 先采用结构化 JSON
- 标准化 `kanban/chat/forum/thread/inbox/notifications/tree/graph/gantt` 等 kind
- 看板与聊天是标准投影，不是协议根
- Shared / private / system 并存

## 13. 后续待细化

下一轮仍需补充：

- query JSON 正式 schema
- 默认 card/chat/thread 展示约定
- system view 生成规则
