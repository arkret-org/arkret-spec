# Object Model Draft

## 1. 目标

Contrix New 的对象模型必须同时支持：

- 人类团队协作
- 多组织协作
- 看板工作流
- 聊天与话题讨论
- 树形任务拆解与复杂依赖图
- AI agent 执行轨迹
- AI agent 长期记忆

因此协议必须围绕 **协作图 + 事件日志 + 视图投影** 来设计，而不是围绕“房间事件”“列和卡片”或“消息时间线”这样的单一 UI 模式。

本协议的核心抽象固定为：

```txt
Space
Actor
Entity
Relation
Event
View
```

一句话定义：

> 在一个 Space 中，Actor 通过 Event 改变 Entity 与 Relation 组成的协作图；View 将这张图投影为聊天、看板、表格、日历、树、图谱、甘特图、审阅队列或其他界面。

## 2. 设计原则

### 2.1 稳定 ID 与显示名称分离

协议引用 MUST 使用稳定 ID，不得使用：

- 标题
- 显示名称
- Handle
- URL 路径

### 2.2 Entity 属于 Space，而不是属于某个 UI

同一个 Entity 可以同时进入多个 View，也可以同时被人类和 agent 使用。

任务卡片、聊天消息、文档、评论、运行记录、记忆、决策、文件元数据都只是不同 `entity_type` 的 Entity。

### 2.3 Relation 是一等对象

对象之间的关系不能全部藏进 Entity 字段。

依赖、阻塞、包含、回复、引用、派生、分配、提及、订阅都 SHOULD 表达为 Relation。

### 2.4 Event 是事实记录

Event 表示“发生了什么”，不应被静默覆盖。

当前态可以由 reducer 归约得到，也可以由 index/appview 物化缓存；但 canonical history MUST 来自授权 Event / operation 集合。

### 2.5 View 只是投影

看板、聊天、表格、日历、树、图谱、甘特图、inbox 都是 View。

View 不拥有底层数据。View 只定义：

- 查询范围
- 关系展开规则
- 分组、排序与布局
- 可见字段
- 交互建议

### 2.6 Schema 约束抽象

协议允许开放 Entity 类型，但不允许无约束 JSON 失控。

Space SHOULD 注册 EntitySchema 与 RelationSchema，用于约束字段、关系、权限动作和默认视图。

## 3. ID 规范

初版建议对象 ID 使用带前缀的稳定字符串，随机部分建议使用 ULID。

核心 ID：

- `cx:space:<ulid>`
- `cx:actor:<ulid>`
- `cx:entity:<ulid>`
- `cx:rel:<ulid>`
- `cx:event:<ulid>`
- `cx:view:<ulid>`
- `cx:schema:<ulid>`
- `cx:policy:<ulid>`
- `cx:invite:<ulid>`
- `cx:read:<ulid>`

语义对象 MAY 使用更具体前缀作为兼容别名，但协议层 SHOULD 归一为 `entity_id`：

- `cx:task:<ulid>` 等价于 `entity_type = "task"`
- `cx:message:<ulid>` 等价于 `entity_type = "message"`
- `cx:doc:<ulid>` 等价于 `entity_type = "document"`
- `cx:run:<ulid>` 等价于 `entity_type = "run"`
- `cx:mem:<ulid>` 等价于 `entity_type = "memory"`

## 4. 核心对象集合

协议核心对象集合固定为：

- `space`
- `actor`
- `entity`
- `relation`
- `event`
- `view`
- `schema`
- `policy`
- `invite`
- `read_marker`

其中：

- `space` 是复制、权限、schema 与 policy 边界
- `actor` 是行动主体，可以是 user、agent、system、integration、team
- `entity` 是所有可协作对象的统一载体
- `relation` 是 Entity 之间的语义链接
- `event` 是协作事实和审计根
- `view` 是展示投影
- `schema` 是字段、关系和动作约束
- `policy` 是保留、可见性、加密与 moderation 默认策略
- `invite` 是加入 Space 的显式引导对象
- `read_marker` 是 actor-private 但可同步的已读状态

以下概念不再是协议根对象，而是标准 Entity 类型或 View 类型：

- board
- collection
- item
- channel
- topic
- message
- comment
- attachment
- run
- memory
- notification

## 5. 通用 Envelope

所有 canonical object SHOULD 共享以下基础字段：

```json
{
  "id": "cx:entity:01JS0000000000000000000000",
  "kind": "entity",
  "space_id": "cx:space:01JS0000000000000000000000",
  "created_at": "2026-04-22T08:00:00Z",
  "created_by": "did:web:alice.example.com",
  "updated_at": "2026-04-22T08:05:00Z",
  "updated_by": "did:web:agent.example.com",
  "visibility": "space",
  "archived": false,
  "tombstoned": false,
  "schema_ref": "cx:schema:01JS0SC000000000000000000",
  "version": 7
}
```

## 6. Space

Space 是协作、复制、权限、schema 与 policy 边界。

它可以表达：

- 组织空间
- 项目空间
- 客户协作空间
- 团队空间
- 频道空间
- agent 工作空间

示例：

```json
{
  "id": "cx:space:01JS0SP000000000000000000",
  "kind": "space",
  "space_type": "project",
  "owner": "did:web:acme.example.com",
  "name": "Acme Delivery Space",
  "description": "Cross-org product delivery and agent automation space",
  "visibility": "private",
  "parent_space_id": null,
  "default_policy_ref": "cx:policy:01JS0PL000000000000000000",
  "default_schema_refs": [
    "cx:schema:01JS0SC000000000000000000"
  ],
  "default_view_id": "cx:view:01JS0VW000000000000000000"
}
```

## 7. Actor

Actor 是行动主体，不一定是人。

```json
{
  "id": "did:web:agent.copy.example.com",
  "kind": "actor",
  "actor_type": "agent",
  "display_name": "Copy Review Agent",
  "status": "active",
  "profile_entity_id": "cx:entity:01JS0AE000000000000000000"
}
```

`actor_type` 初版建议：

- `user`
- `agent`
- `system`
- `integration`
- `team`

Actor 的身份根仍然由 [identity.md](./identity.md) 定义。协议中的主体引用 MUST 使用 DID 或稳定 actor ID。

当 Actor 需要进入协作图时，SHOULD 为它创建一个 `entity_type = "actor_profile"` 的 Entity 镜像。这样 `assigned_to`、`mentions`、`contains` 等 Relation 可以始终指向 Entity，避免 Relation 同时支持多种目标类型。

## 8. Entity

Entity 是协议中最重要的协作对象。

它代表任何可被创建、讨论、关联、修改、追踪、授权和投影的东西。

示例：

```json
{
  "id": "cx:entity:01JS0EN000000000000000000",
  "kind": "entity",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "task",
  "schema_version": 1,
  "title": "Finalize onboarding copy review",
  "content": {
    "format": "markdown",
    "text": "Coordinate product, design, legal, and agent-generated suggestions."
  },
  "fields": {
    "status": "in_progress",
    "rank": "mV",
    "priority": "high",
    "due_at": "2026-04-28T00:00:00Z",
    "labels": ["launch", "copy"]
  },
  "created_by": "did:web:alice.example.com",
  "created_at": "2026-04-22T08:00:00Z",
  "updated_by": "did:web:agent.copy.example.com",
  "updated_at": "2026-04-22T08:05:00Z"
}
```

### 8.1 标准 Entity 类型

初版建议标准化以下 `entity_type`：

- `space_profile`
- `actor_profile`
- `task`
- `issue`
- `goal`
- `request`
- `decision`
- `note`
- `document`
- `comment`
- `message`
- `channel`
- `topic`
- `board`
- `collection`
- `attachment`
- `run`
- `memory`
- `schema`
- `policy`
- `invite`
- `read_marker`

这些类型是语义层，不是新的协议根。

### 8.2 字段边界

Entity 字段 SHOULD 用于对象自身属性，例如：

- 标题
- 正文
- 状态
- 优先级
- 时间
- 排序 token
- 业务标签
- schema 约束的自定义字段

Entity 字段 SHOULD NOT 用于表达复杂跨对象关系。跨对象关系 SHOULD 使用 Relation。

例如：

- 任务属于某个看板：Relation `belongs_to`
- 消息属于某个频道：Relation `belongs_to`
- 消息回复另一条消息：Relation `replies_to`
- 任务依赖另一任务：Relation `depends_on`
- 文档引用某个决策：Relation `references`

## 9. Relation

Relation 表达 Entity 之间的语义链接。

示例：

```json
{
  "id": "cx:rel:01JS0RL000000000000000000",
  "kind": "relation",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "relation_type": "depends_on",
  "from_entity_id": "cx:entity:01JS0TASK0000000000000000",
  "to_entity_id": "cx:entity:01JS0TASK0000000000000001",
  "directed": true,
  "fields": {
    "strength": "hard"
  },
  "created_by": "did:web:alice.example.com",
  "created_at": "2026-04-22T08:10:00Z"
}
```

### 9.1 标准 Relation 类型

初版建议标准化：

- `contains`
- `belongs_to`
- `replies_to`
- `references`
- `depends_on`
- `blocks`
- `duplicates`
- `relates_to`
- `assigned_to`
- `mentions`
- `derived_from`
- `subscribes`
- `supersedes`
- `attached_to`

### 9.2 Relation 与反向语义

Relation 的 canonical 方向由 `from_entity_id -> to_entity_id` 定义。

反向语义 SHOULD 由查询层或 schema 派生，不建议额外写入一条重复反向 Relation，除非业务语义确实不同。

例如：

- `A depends_on B` 的反向显示可以是 `B blocks A`
- 但 canonical 可以只存 `depends_on`

## 10. Event

Event 是协作事实记录。

```json
{
  "id": "cx:event:01JS0EV000000000000000000",
  "kind": "event",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "event_type": "entity.updated",
  "target": {
    "kind": "entity",
    "id": "cx:entity:01JS0EN000000000000000000"
  },
  "payload": {
    "changes": {
      "fields.status": {
        "old": "todo",
        "new": "in_progress"
      }
    }
  },
  "occurred_at": "2026-04-22T08:20:00Z",
  "recorded_at": "2026-04-22T08:20:01Z",
  "transaction_id": "cx:txn:01JS0TX000000000000000000",
  "correlation_id": null,
  "causation_id": null
}
```

### 10.1 标准 Event 类型

底层事件 SHOULD 优先使用通用类型：

- `space.created`
- `space.updated`
- `actor.joined`
- `actor.left`
- `entity.created`
- `entity.updated`
- `entity.deleted`
- `entity.restored`
- `relation.created`
- `relation.updated`
- `relation.deleted`
- `view.created`
- `view.updated`
- `view.deleted`
- `schema.updated`
- `policy.updated`

业务事件 MAY 作为语义糖：

- `message.sent`
- `message.revised`
- `message.redacted`
- `task.assigned`
- `task.status_changed`
- `dependency.added`
- `file.attached`
- `memory.confirmed`
- `run.started`
- `run.finished`

业务事件必须能还原为底层 `entity.*` 或 `relation.*` 事件。

### 10.2 Command 与 Event

客户端 SHOULD 提交 Command，服务端或本地 reducer 验证后生成 Event。

```json
{
  "id": "cx:cmd:01JS0CM000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "command_type": "entity.create",
  "payload": {
    "entity_type": "task",
    "title": "Design collaboration protocol",
    "fields": {
      "status": "todo",
      "priority": "high"
    }
  },
  "idempotency_key": "client-generated-key",
  "requested_at": "2026-04-22T08:00:00Z"
}
```

处理模型：

```txt
Command -> Validate -> Event -> Reduce Current State -> Notify Views
```

## 11. View

View 是独立对象，详细行为见 [views.md](./views.md)。

它定义如何把 Entity + Relation + Event 投影为人类或 agent 可用的界面。

示例：

```json
{
  "id": "cx:view:01JS0VW000000000000000000",
  "kind": "view",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "view_type": "kanban",
  "name": "Release Flow",
  "visibility": "shared",
  "query": {
    "entity_types": ["task", "issue"],
    "filter": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ]
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

标准 `view_type` 包括：

- `chat`
- `kanban`
- `table`
- `list`
- `calendar`
- `gantt`
- `graph`
- `tree`
- `timeline`
- `feed`
- `document`
- `matrix`
- `dashboard`
- `inbox`
- `review_queue`

## 12. 标准语义类型建模

本节说明旧草案中的 board、item、message 等概念如何落到统一模型。

### 12.1 Board / Collection / Card

看板不是协议根。看板由 Entity、Relation 和 View 表达：

- board: `entity_type = "board"`
- collection/lane: `entity_type = "collection"`
- card/task: `entity_type = "task"` 或其他工作对象类型
- board 包含 collection: `board --contains--> collection`
- collection 包含 task: `collection --contains--> task`
- kanban 展示: `view_type = "kanban"`

### 12.2 Chat / Channel / Topic / Message

聊天不是协议根。聊天由 Entity、Relation 和 View 表达：

- channel: `entity_type = "channel"`
- topic/thread: `entity_type = "topic"`
- message: `entity_type = "message"`
- topic 属于 channel: `topic --belongs_to--> channel`
- message 属于 topic 或 channel: `message --belongs_to--> topic`
- message 回复 message: `message --replies_to--> message`
- chat 展示: `view_type = "chat"` 或 `view_type = "thread"`

消息正文 SHOULD 存在 Entity 的 `content` 中；mention MUST 同时落为结构化 Relation：

```json
{
  "relation_type": "mentions",
  "from_entity_id": "cx:entity:message_1",
  "to_entity_id": "cx:entity:actor_profile_bob"
}
```

### 12.3 Task Dependency Graph

复杂依赖图不需要特殊对象：

- task: `entity_type = "task"`
- dependency: `relation_type = "depends_on"`
- blocker: 可由 `depends_on` 反向显示，或用 `blocks` 作为显式业务 Relation
- graph 展示: `view_type = "graph"`
- tree 展示: `view_type = "tree"`，使用 `contains` 或 `belongs_to`

### 12.4 Document / Comment

文档与评论也是 Entity：

- document: `entity_type = "document"`
- comment: `entity_type = "comment"`
- comment 锚定目标: `comment --attached_to--> target`
- comment 回复 comment: `comment --replies_to--> comment`

`comment` 定位为 durable review/note，不等同于实时聊天消息。

### 12.5 Run / Memory

AI agent 相关对象仍是一等 Entity：

- run: `entity_type = "run"`
- memory: `entity_type = "memory"`
- run 输入: `run --references--> source`
- run 输出: `run --derived_from--> source` 或 `output --derived_from--> run`
- memory 来源: `memory --derived_from--> message/comment/run/document`

Memory 不等于 embedding chunk。向量索引属于派生层。

## 13. Schema

Contrix 必须支持自定义字段，但不建议允许完全无约束 JSON 扩展。

Schema SHOULD 定义 Entity 类型、字段类型、允许关系、默认视图和动作语义。

示例：

```json
{
  "id": "cx:schema:01JS0SC000000000000000000",
  "kind": "schema",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "schema_type": "entity",
  "entity_type": "task",
  "version": 1,
  "fields": {
    "status": {
      "type": "enum",
      "required": true,
      "options": ["todo", "in_progress", "done"]
    },
    "priority": {
      "type": "enum",
      "required": false,
      "options": ["low", "medium", "high"]
    },
    "due_at": {
      "type": "datetime",
      "required": false
    }
  },
  "allowed_relations": {
    "outgoing": ["depends_on", "blocks", "belongs_to", "references", "assigned_to"],
    "incoming": ["contains", "blocks", "references", "attached_to"]
  },
  "default_views": ["kanban", "table", "graph"]
}
```

建议字段类型：

- `text`
- `number`
- `bool`
- `date`
- `datetime`
- `enum`
- `multi_enum`
- `actor_ref`
- `entity_ref`
- `url`
- `json`

## 14. Policy

Policy 是正式对象，而不是实现私货。

示例：

```json
{
  "id": "cx:policy:01JS0PL000000000000000000",
  "kind": "policy",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "name": "space-default-policy",
  "retention": {
    "message_days": 3650,
    "event_log_days": 3650,
    "candidate_memory_days": 90
  },
  "default_visibility": "space",
  "redaction_mode": "tombstone",
  "encryption_profile": "space-envelope-v1",
  "allow_external_relays": true
}
```

Policy SHOULD 至少覆盖：

- retention
- default visibility
- redaction display
- encryption profile
- relay / blob / export defaults

## 15. Invite

去中心化协作里，“别人如何加入 Space”不能只靠产品私有链接。

Contrix 应支持显式 `invite` 对象。它可以是专门对象，也可以落为 `entity_type = "invite"`。

```json
{
  "id": "cx:invite:01JS0IV000000000000000000",
  "kind": "invite",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject_did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "subject_handle": "alice.example.com",
  "proposed_role": "contributor",
  "proposed_grant_refs": [
    "cx:grant:01JS0GR000000000000000000"
  ],
  "expires_at": "2026-05-01T00:00:00Z",
  "status": "pending"
}
```

`invite` 本身不等于 capability grant。接受 invite 后，相关 grant 才进入生效集合。

## 16. Read Marker 与 Notification

`read_marker` 是 actor-private 的 durable state：

```json
{
  "id": "cx:read:01JS0RD000000000000000000",
  "kind": "read_marker",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "owner": "did:web:alice.example.com",
  "scope_kind": "view",
  "scope_ref": "cx:view:01JS0VW000000000000000000",
  "last_seen_event_id": "cx:event:01JS0EV000000000000000000",
  "last_seen_hlc": "2026-04-22T08:31:03.221Z-0007-did:web:alice.example.com",
  "updated_at": "2026-04-22T08:40:00Z"
}
```

通知不应成为 canonical truth object。

`notification` SHOULD 是由 Event、Entity 与 Relation 派生的 inbox projection，例如：

- `mentions`
- `assigned_to`
- `invite`
- `run.failed`
- `memory.review_requested`

## 17. 派生数据

以下内容不应作为 canonical truth object 保存：

- embedding 向量
- 搜索倒排索引
- UI 本地布局缓存
- 临时排序缓存
- LLM 上下文窗口
- typing/presence 瞬时状态
- notification materialization

这些都属于派生层或临时信号层。

## 18. 初版设计决定

当前草案固定：

- 协议根抽象为 `Space + Actor + Entity + Relation + Event + View`
- `Entity` 是协作对象，不属于任何特定 View
- `Relation` 是一等公民，不藏在 Entity 字段里
- `Event` 是事实记录和审计根
- `View` 是投影，不拥有核心数据
- `Command` 表达意图，`Event` 表达事实
- `Schema` 约束 Entity 与 Relation，避免抽象退化成混乱 JSON
- board、chat、task、message、run、memory 都是语义层，而不是协议根

## 19. 后续待细化

下一轮仍需明确：

- EntitySchema / RelationSchema 正式 JSON Schema
- Event envelope 与签名格式
- Command request/response schema
- ViewQuery 正式 schema
- read marker 与 notification 的正式查询面
- message 富文本 block 结构
- Space 历史可见性规则
- memory supersession / invalidation 语义
