# Object Model Core

## 1. 目标

Contrix 的核心数据模型不是 room-first，也不是万能 `Entity`。它是一张以 Space 为边界、以标准对象和开放 Morph 共同组成的可审计协作图。

核心对象：

- `space`
- `actor`
- `room`
- `board`
- `list`
- `card`
- `message`
- `morph`
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

### 2.1 Space 是协作边界

`space` 是复制、权限、schema、policy、membership、history visibility、加密和索引的边界。

一个 Space 可以包含多个：

- Room
- Board
- Card
- Document
- Run
- Memory
- Morph

Space MAY 通过 `cx.space.child` / `cx.space.parent` 形成层级或图状组织，但 child Space 仍然是独立边界。membership、capability、history visibility、schema、policy 和 encryption key 默认不从 parent 级联到 child；任何继承都必须由 child Space 显式声明。详细规则见 `space-hierarchy.md`。

### 2.2 标准对象承载主语义

协议不再把 `board`、`card`、`room`、`message`、`run`、`memory` 等都压成 `entity_type`。

标准对象本身表达主语义：

- `room`：讨论容器和消息时间线入口。
- `board`：工作流看板。
- `list`：Board 内的有序泳道/列。
- `card`：有生命周期、状态、负责人、位置和决策沉淀的工作对象。
- `message`：Room 时间线中的消息。
- `morph`：开放形态对象，用于业务扩展、未知类型和实验对象。

标准对象 MAY 暴露 schema/profile 已声明的 `facets` 来辅助展示或查询，但它的核心职责不依赖 facets 才成立。例如 `card` 天然是可被 Board/List 管理的工作对象；`room` 天然是讨论容器；`message` 天然属于 Room timeline。实现不得要求标准对象先声明 facet 才承认其主语义。

### 2.3 Morph 是开放对象

`morph` 表示协议未固化为标准类型的协作对象。它适合：

- 插件或业务自定义对象
- 未来标准类型的实验阶段
- 外部系统镜像对象
- 低频、弱互操作的扩展数据

Morph 的可见能力可以由 Space schema / Morph profile 声明，并通过 `facets` 暴露给 Index、View、UI 或插件。实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。

Facet 字符串本身不是规范性 reducer 或授权来源。任何会改变写入权限、状态转换、排序、包含关系、事件有效性或跨实现 wire 行为的能力，MUST 由明确 schema/profile/event kind/capability action 定义。

### 2.4 Relation 是一等对象

跨对象语义 MUST 使用 `relation` 表达，而不是藏在对象字段里。

常见关系：

- `contains`
- `belongs_to`
- `links_room`
- `primary_room`
- `replies_to`
- `depends_on`
- `blocks`
- `mentions`
- `assigned_to`
- `references`
- `derived_from`
- `summarized_from`
- `promoted_from_room`

Relation 连接的是对象引用。标准字段使用 `from_ref` / `to_ref`，其值可以指向 `room`、`board`、`list`、`card`、`message`、`morph`、`actor` 或 `space`。

### 2.5 Event 是事实

所有协作变化最终都落为签名 `event`。

Event 是审计根和 reducer 输入。当前态只是 Event 集合在某个 reducer profile 下的物化结果。

### 2.6 View 是投影定义

`view` 是一等协议对象，但它拥有的是投影定义的真相，而不是被投影对象的协作事实。它定义查询、过滤、排序、分组、renderer、布局、可见字段和共享 saved view 配置。

同一组 Room / Board / List / Card / Message / Morph / Relation 可以投影为：

- board
- list
- table
- calendar
- gantt
- chat
- thread
- forum
- graph
- review queue

View 不得发明对象能力，也不得持有对象状态的唯一副本；对象能力来自对象类型、schema/profile 和 capability，facets 只作为已声明能力的查询与投影 hint。Board 包含 List、List 包含 Card、Card 的字段与位置、Room 的消息与成员，都必须由对应标准对象、Relation 和 Event 归约得到。

当用户通过 View 修改协作对象时，写入必须落到真实对象操作。例如 Card 跨 List 拖拽写为 `cx.card.move`，同 List 排序写为 `cx.card.reorder`，修改列顺序写为 `cx.list.reorder`，改变 View 的 filter / columns / layout 才写为 `cx.view.update` 或 actor-private account data。

## 3. 通用字段规则

所有 canonical object 字段 MUST 使用 snake_case。

基础字段：

```json
{
  "id": "cx:card:01js0ke0000000000000000000",
  "type": "card",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "created_by": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "updated_at": "2026-04-26T00:00:00Z",
  "schema": "cx.schema.card.v1"
}
```

对象 ID SHOULD 使用带类型前缀的稳定字符串：

- `cx:space:<ulid>`
- `cx:room:<ulid>`
- `cx:board:<ulid>`
- `cx:list:<ulid>`
- `cx:card:<ulid>`
- `cx:message:<ulid>`
- `cx:morph:<ulid>`
- `cx:relation:<ulid>`
- `cx:event:<ulid>`
- `cx:view:<ulid>`
- `cx:grant:<ulid>`

## 4. Space

最小结构：

```json
{
  "id": "cx:space:01js0sp0000000000000000000",
  "type": "space",
  "title": "Launch Plan",
  "created_by_principal": "did:web:acme.example",
  "schema_refs": [
    "cx.schema.space.v1"
  ],
  "policy_ref": "cx:policy:01js0p10000000000000000000",
  "encryption_profile": "mls_rfc9420",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Space policy 决定：

- 谁能加入 Space
- 哪些 Room / Board / Card / Morph 类型可用
- 哪些服务可同步、索引或看见明文
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

Actor MAY 有对应的 `actor_profile` 对象，便于在协作图中被 mention、assign 或展示。

Accountable actor MUST 记录责任关系，但 accountability 不等于 capability。

## 6. Room

Room 是 Space 内的讨论容器。它承载一个或多个消息时间线、通知规则、历史可见性和可选 E2EE group。

Room 可以独立于 Card 存在，也可以通过 Relation 被 Card 关联。Card 可关联 0..N 个 Room；Room 的 membership、policy、history visibility 和 E2EE 独立于 Card。

最小结构：

```json
{
  "id": "cx:room:01js0rm0000000000000000000",
  "type": "room",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Engineering review",
  "summary": "Implementation discussion for the launch plan.",
  "room_kind": "discussion",
  "membership_policy_ref": "cx:policy:01js0rp0000000000000000000",
  "history_visibility": "joined",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Room 规则：

- 能看 Card 不表示能看关联 Room。
- 能看 Room 不表示能看关联 Card。
- Card 成员或负责人变化不自动改变 Room membership。
- Room membership 变化不自动改变 Card 权限。
- Card 删除、归档或移动时不自动删除 Room；只 MAY tombstone 或更新 `links_room` Relation。

## 7. Board / List / Card

Board 是工作流容器。List 是 Board 内的列/泳道。Card 是可执行、可跟踪、可沉淀的工作对象。

Board 最小结构：

```json
{
  "id": "cx:board:01js0bd0000000000000000000",
  "type": "board",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Release Board",
  "board_kind": "kanban",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

List 最小结构：

```json
{
  "id": "cx:list:01js01s0000000000000000000",
  "type": "list",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Review",
  "rank": "mV",
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Card 最小结构：

```json
{
  "id": "cx:card:01js0cd0000000000000000000",
  "type": "card",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Review launch checklist",
  "body": {
    "format": "markdown",
    "text": "Please finish the final review."
  },
  "fields": {
    "status": "review",
    "priority": "high",
    "due_at": "2026-05-01T00:00:00Z"
  },
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_at": "2026-04-26T00:00:00Z"
}
```

Card 在 Board/List 中的位置通过 active `contains` Relation / card position event 表达，不由 Room 决定，也不要求 Card canonical object 自带 `board_id` 或 `list_id`。Index / AppView 返回的 `board_id`、`list_id`、`rank` 是投影派生字段。

常见关系：

- `board --contains--> list`
- `list --contains--> card`
- `card --links_room--> room`
- `card --primary_room--> room`
- `card --assigned_to--> actor`
- `card --depends_on--> card`

## 8. Message

Message 是 Room 时间线中的原子消息对象。

```json
{
  "id": "cx:message:01js0ms0000000000000000000",
  "type": "message",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "room_id": "cx:room:01js0rm0000000000000000000",
  "created_by": "did:web:alice.example",
  "content": {
    "format": "markdown",
    "text": "@bob 请确认这个 item 的 legal 风险。"
  },
  "fields": {
    "revision_root": "cx:message:01js0ms0000000000000000000",
    "visible_state": "active"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

Message MAY reply to another Message, mention Actor or object, reference Card / Morph / Room, or be redacted. 编辑通过 revision chain 表达；撤回通过 redaction/tombstone 表达。

## 9. Morph

Morph 是开放对象。

```json
{
  "id": "cx:morph:01js0mp0000000000000000000",
  "type": "morph",
  "space_id": "cx:space:01js0sp0000000000000000000",
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

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象不应为了复用字段而退化为 Morph。

## 10. Relation

最小结构：

```json
{
  "id": "cx:relation:01js0r00000000000000000000",
  "type": "relation",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "relation_kind": "links_room",
  "from_ref": "cx:card:01js0cd0000000000000000000",
  "to_ref": "cx:room:01js0rm0000000000000000000",
  "fields": {
    "purpose": "implementation_discussion",
    "primary": false
  },
  "created_by": "did:web:bob.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Canonical 方向由 `from_ref -> to_ref` 定义。反向语义 SHOULD 由查询层或 schema 派生。

## 11. Event

Event 是 reducer 输入和审计事实。

最小 envelope：

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "actor_id": "did:web:alice.example",
  "kind": "cx.card.update",
  "created_at": "2026-04-26T00:00:00Z",
  "space_version": "1",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [
    "cx:event:01js0ev0000000000000000000"
  ],
  "auth_refs": [
    "cx:space:01js0sp0000000000000000000",
    "cx:event:01js0ms0000000000000000000"
  ],
  "content": {
    "card_id": "cx:card:01js0cd0000000000000000000",
    "patch": {
      "fields.status": "done"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "verification_method": "did:web:alice.example#device-1",
      "jws": "..."
    }
  ]
}
```

Event MUST be signed。Reducer MUST reject events that fail signature, schema, capability, or causal validation.

## 12. View

View 示例：

```json
{
  "id": "cx:view:01js0vw0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "kind": "collection",
  "renderer": "board",
  "query": {
    "object_types": ["card"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "source_ref": "cx:board:01js0bd0000000000000000000",
      "depth": 2
    }
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at"
  ]
}
```

## 13. Schema

Schema 约束：

- 标准对象类型
- Morph type 和 facets
- fields
- relation type
- allowed actions
- default views
- validation rules

Schema evolution MUST be additive by default。新版本 SHOULD 保留未知字段，避免旧客户端破坏数据。

## 14. Policy

Policy 约束：

- capability requirement
- object type / facet requirement
- encryption profile
- retention
- visibility
- federation
- moderation
- quota

Policy 是 reducer 和服务节点判断请求是否可接受的输入。

## 15. Invite

Invite 是加入引导对象，不等于 capability grant。

接受 invite 后，相关 capability grant 才进入有效集合。

## 16. Read Marker

`read_marker` 是 actor-private 状态。它 SHOULD 存在于私有 account data 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

## 17. Notification

`notification` SHOULD 是从 Event / Message / Room / Card / Relation 派生的 inbox projection，不是 canonical truth。

## 18. Reducer 规则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Operation 保持幂等
- 保留未知字段
- 输出可声明的 reducer profile

## 19. 规范性引用

- 标准 event type 注册表见 `../conformance/schema-registry.md`。
- Reducer conformance vector 见 `../conformance/state-resolution-conformance-vectors.md`、`../conformance/redaction-conformance-vectors.md` 和 `../conformance/sync-conformance-vectors.md`。
- Relation cardinality 规则由 `data-structures.md`、`object-model-standard.md` 和各业务 profile 共同定义；未声明可多重的关系 MUST 按 `(space_id, relation_kind, from_ref, to_ref)` 去重。
- Schema evolution 测试见 `../conformance/conformance-profiles.md`。未知字段必须保留，但不得绕过 schema、capability、policy 或 encryption 约束。
