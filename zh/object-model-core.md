# Object Model Core Draft

## 1. 目标

Contrix 的核心数据模型不是 room，也不是 message，而是一张可审计、可同步、可投影的协作图。

核心对象：

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
- `notification`

字段级结构、必填性、类型和约束见 `data-structures.md`。本文保留核心模型语义和示例，具体 JSON Schema SHOULD 从 `data-structures.md` 与 `schema-registry.md` 生成。

## 2. 基本原则

### 2.1 Space 是边界

`space` 是复制、权限、schema、policy、加密和索引的边界。

一个 Space 可以表现为：

- 项目
- 团队
- 私聊
- 群聊
- 看板
- 文档库
- agent memory scope

但协议层不为这些 UI 形态创建不同根模型。

Space MAY 通过 `cx.space.child` / `cx.space.parent` 形成层级或图状组织，但 child Space 仍然是独立边界。membership、capability、history visibility、schema、policy 和 encryption key 默认不从 parent 级联到 child；任何继承都必须由 child Space 显式声明。详细规则见 `space-hierarchy.md`。

### 2.2 Entity 是协作对象

`entity` 表示任何可被创建、讨论、引用、分配、修改、审计和投影的对象。

常见类型：

- `task`
- `message`
- `topic`
- `channel`
- `board`
- `document`
- `memory`
- `run`
- `file`
- `actor_profile`

### 2.3 Relation 是一等对象

跨对象语义 MUST 使用 `relation` 表达，而不是藏在 Entity 字段里。

常见关系：

- `contains`
- `belongs_to`
- `replies_to`
- `depends_on`
- `blocks`
- `mentions`
- `assigned_to`
- `references`
- `derived_from`

### 2.4 Event 是事实

所有协作变化最终都落为签名 `event`。

Event 是审计根和 reducer 输入。当前态只是 Event 集合在某个 reducer profile 下的物化结果。

### 2.5 View 是投影

`view` 不拥有核心数据。  
它定义查询、过滤、排序、分组、布局和交互提示。

同一组 Entity / Relation 可以投影为：

- kanban
- list
- table
- calendar
- gantt
- chat
- thread
- forum
- graph
- review queue

## 3. 通用字段规则

所有 canonical object 字段 MUST 使用 snake_case。

基础字段：

```json
{
  "id": "cx:entity:01JS0KE000000000000000000",
  "type": "entity",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "created_by": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "updated_at": "2026-04-26T00:00:00Z",
  "schema": "cx.schema.entity.v1"
}
```

对象 ID SHOULD 使用带类型前缀的稳定字符串：

- `cx:space:<ulid>`
- `cx:entity:<ulid>`
- `cx:relation:<ulid>`
- `cx:event:<ulid>`
- `cx:view:<ulid>`
- `cx:grant:<ulid>`

## 4. Space

最小结构：

```json
{
  "id": "cx:space:01JS0SP000000000000000000",
  "type": "space",
  "title": "Launch Plan",
  "created_by_principal": "did:web:acme.example",
  "schema_refs": [
    "cx.schema.core.v1"
  ],
  "policy_ref": "cx:policy:01JS0PL000000000000000000",
  "encryption_profile": "mls_rfc9420",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Space policy 决定：

- 谁能加入
- 谁能读写
- 哪些 Entity type 可用
- 是否加密
- 是否允许外部联邦
- 数据保留与 blob 配额

Space 层级关系不改变上述边界。Parent Space 可以帮助发现和组织 child Space，但不能单方面授予 child Space 的读取、写入、审核或解密能力。

## 5. Actor

Actor 是能执行动作的主体。协议中的 actor identity 根由 DID 定义。

Actor 类型：

- `user`
- `org`
- `team`
- `agent`
- `service`
- `device`
- `integration`

Actor MAY 有对应的 `actor_profile` Entity，便于在协作图中被 mention、assign 或展示。

Accountable actor MUST 记录责任关系，但 accountability 不等于 capability。

## 6. Entity

最小结构：

```json
{
  "id": "cx:entity:01JS0E0000000000000000000",
  "type": "entity",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "task",
  "title": "Review launch checklist",
  "content": {
    "body": "Please finish the final review."
  },
  "fields": {
    "status": "todo",
    "priority": "high",
    "rank": "mV"
  },
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_at": "2026-04-26T00:00:00Z"
}
```

Entity 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。

## 7. Relation

最小结构：

```json
{
  "id": "cx:relation:01JS0R0000000000000000000",
  "type": "relation",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "kind": "assigned_to",
  "from_entity_id": "cx:entity:task1",
  "to_actor_id": "did:web:alice.example",
  "created_by": "did:web:bob.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Canonical 方向由 `from_* -> to_*` 定义。  
反向语义 SHOULD 由查询层或 schema 派生。

## 8. Event

Event 是 reducer 输入和审计事实。

最小 envelope：

```json
{
  "event_id": "cx:event:01JS0EV000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor_id": "did:web:alice.example",
  "type": "cx.entity.update",
  "created_at": "2026-04-26T00:00:00Z",
  "space_version": "cx.space.v1",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [
    "cx:event:01JS0EU000000000000000000"
  ],
  "auth_refs": [
    "cx:space:01JS0SP000000000000000000",
    "cx:event:01JS0MS000000000000000000"
  ],
  "content": {
    "entity_id": "cx:entity:task1",
    "patch": {
      "fields.status": "done"
    }
  },
  "proof": {
    "type": "detached_jws",
    "verification_method": "did:web:alice.example#device-1",
    "jws": "..."
  }
}
```

Event MUST be signed。  
Reducer MUST reject events that fail signature, schema, capability, or causal validation.

## 9. View

View 示例：

```json
{
  "id": "cx:view:01JS0VW000000000000000000",
  "kind": "view",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "view_kind": "kanban",
  "query": {
    "entity_types": ["task"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "group_by": "fields.status",
    "order_by": [
      { "field": "fields.rank", "direction": "asc" }
    ]
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at"
  ]
}
```

## 10. Schema

Schema 约束：

- Entity type
- fields
- relation type
- allowed actions
- default views
- validation rules

Schema evolution MUST be additive by default。新版本 SHOULD 保留未知字段，避免旧客户端破坏数据。

## 11. Policy

Policy 约束：

- capability requirement
- encryption profile
- retention
- visibility
- federation
- moderation
- quota

Policy 是 reducer 和服务节点判断请求是否可接受的输入。

## 12. Invite

Invite 是加入引导对象，不等于 capability grant。

接受 invite 后，相关 capability grant 才进入有效集合。

## 13. Read Marker

`read_marker` 是 actor-private 状态。  
它 SHOULD 存在于私有 repo 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

## 14. Notification

`notification` SHOULD 是从 Event / Entity / Relation 派生的 inbox projection，不是 canonical truth。

## 15. Reducer 规则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 op 保持幂等
- 保留未知字段
- 输出可声明的 reducer profile

## 16. 待细化

- 标准 event type 注册表
- reducer conformance vector
- relation cardinality 规则
- schema evolution 测试
