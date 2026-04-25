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

## 3. View 对象

建议字段：

```json
{
  "id": "cx:view:01JS0VW000000000000000000",
  "kind": "view",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "owner": "did:web:acme.example.com",
  "view_type": "kanban",
  "name": "Release Flow",
  "visibility": "shared",
  "query": {
    "entity_types": ["task", "issue"],
    "filter": [
      { "field": "archived", "op": "neq", "value": true }
    ],
    "relation": {
      "type": "contains",
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

## 4. 标准 `view_type`

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

## 5. Query Model

View 应通过结构化 query 表达对象范围。

建议通用查询形状：

```json
{
  "entity_types": ["task"],
  "filter": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] }
  ],
  "relation": {
    "type": "depends_on",
    "direction": "outgoing",
    "depth": 2
  },
  "sort": [
    { "field": "updated_at", "direction": "desc" }
  ],
  "limit": 100
}
```

### 5.1 看板查询示例

```json
{
  "entity_types": ["task", "issue"],
  "filter": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "archived", "op": "eq", "value": false }
  ],
  "relation": {
    "type": "contains",
    "from_entity_id": "cx:entity:01JS0BD000000000000000000",
    "depth": 2
  }
}
```

### 5.2 聊天查询示例

```json
{
  "entity_types": ["message"],
  "filter": [
    { "field": "fields.redacted", "op": "eq", "value": false }
  ],
  "relation": {
    "type": "belongs_to",
    "to_entity_id": "cx:entity:01JS1000000000000000000000",
    "direction": "outgoing"
  }
}
```

### 5.3 话题查询示例

```json
{
  "entity_types": ["topic"],
  "filter": [
    { "field": "fields.status", "op": "eq", "value": "open" }
  ],
  "relation": {
    "type": "attached_to",
    "to_entity_id": "cx:entity:01JS0TASK0000000000000000",
    "direction": "outgoing"
  }
}
```

### 5.4 通知查询示例

```json
{
  "entity_types": ["message", "task", "invite", "run", "memory"],
  "filter": [
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
    "type": "depends_on",
    "direction": "outgoing",
    "depth": 4
  }
}
```

### 5.6 树形查询示例

```json
{
  "entity_types": ["task", "document", "collection"],
  "relation": {
    "type": "contains",
    "direction": "outgoing",
    "depth": 8
  }
}
```

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
- `relation_type = "contains"` / `belongs_to`
- `view_type = "kanban"`

而不是某种 UI 私有列数组。

### 7.2 Chat

Chat 视图的 canonical 输入应是：

- `entity_type = "channel"`
- `entity_type = "topic"`
- `entity_type = "message"`
- `relation_type = "belongs_to"` / `replies_to` / `mentions`

### 7.3 Topic

Thread/topic 视图的 canonical 输入应是：

- `entity_type = "topic"`
- `entity_type = "message"`
- `relation_type = "attached_to"` / `belongs_to` / `replies_to`

### 7.4 Graph

Graph 视图的 canonical 输入应是：

- 任意 `entity_type`
- 一个或多个 `relation_type`
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

属于 workspace，对团队可见。

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
- 标准化 `kanban/chat/forum/thread/inbox/notifications/tree/graph/gantt` 等 view_type
- 看板与聊天是标准投影，不是协议根
- Shared / private / system 并存

## 13. 后续待细化

下一轮仍需补充：

- query JSON 正式 schema
- 默认 card/chat/thread 展示约定
- system view 生成规则
