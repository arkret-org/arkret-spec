# Object Model Core

## 1. 目标

Contrix 的核心数据模型不是 room-first，也不是万能 `Entity`。它是一张以 Space 为边界、以标准对象和开放 Morph 共同组成的可审计协作图。

核心对象：

- `space`
- `actor`
- `subject`
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
- Subject
- Board
- Card
- Document
- Morph

Space MAY 通过 `cx.space.child` / `cx.space.parent` 形成层级或图状组织，但 child Space 仍然是独立边界。membership、capability、history visibility、schema、policy 和 encryption key 默认不从 parent 级联到 child；任何继承都必须由 child Space 显式声明。详细规则见 `space-hierarchy.md`。

### 2.2 标准对象承载主语义

协议不再把 `subject`、`board`、`card`、`room`、`message` 等都压成 `entity_type`。

标准对象本身表达主语义：

- `subject`：语义中心，表示被讨论、推进、引用和沉淀的“东西本身”。
- `room`：讨论容器和消息时间线入口。
- `board`：工作流看板。
- `list`：Board 内的有序泳道/列。
- `card`：有生命周期、状态、负责人、位置和决策沉淀的工作对象。
- `message`：Room 时间线中的消息。
- `morph`：开放形态对象，用于业务扩展、未知类型和实验对象。

标准对象 MAY 暴露 schema/profile 已声明的 `facets` 来辅助展示或查询，但它的核心职责不依赖 facets 才成立。例如 `subject` 天然是语义中心；`card` 天然是可被 Board/List 管理的工作对象；`room` 天然是讨论容器；`message` 天然属于 Room timeline。实现不得要求标准对象先声明 facet 才承认其主语义。

### 2.3 Morph 是开放对象

`morph` 表示协议未固化为标准类型的协作对象。它适合：

- 插件或业务自定义对象
- 未来标准类型的实验阶段
- 外部系统镜像对象
- 低频、弱互操作的扩展数据

Morph 的可见能力可以由 Space schema / Morph profile 声明，并通过 `facets` 暴露给 View、UI、本地搜索或插件。实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。

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
- `has_surface`
- `derived_from`
- `summarized_from`
- `promoted_from_room`

Relation 连接的是对象引用。标准字段使用 `from_ref` / `to_ref`，其值可以指向 `subject`、`room`、`board`、`list`、`card`、`message`、`morph`、`actor` 或 `space`。

#### 2.4.1 跨 Space 引用

Relation 的 `space_id` 表示关系事实所在的源 Space；`from_ref` / `to_ref` MAY 指向其他 Space 的对象、Actor 或 Space。跨 Space 引用只发布引用事实，不复制被引用对象内容，也不授予读取、写入、管理或同步被引用 Space 历史的权限。

创建跨 Space Relation 时，actor MUST 同时满足：

- 对 Relation 所在源 Space 的写入能力。
- 对被引用目标的 discover/reference 能力，或目标 Space policy 允许的等价引用能力。

读取与同步规则：

- 引用 ID、目标类型和目标 `space_id`（若已知）可以作为源 Space 的 Relation metadata 同步。
- 被引用对象的标题、字段、消息、附件、成员、计数、preview 和历史只按目标 Space 的 policy、history visibility、E2EE epoch 与 redaction policy 展开。
- 公共 Space 引用私有 Space 对象时，默认只能展示 opaque ref 或 Lazy Link；除非目标 Space policy 明确允许 preview，不得泄露目标内容、成员、计数或存在性细节。
- Sync / projection 层不得因为源 Space 可见就自动 backfill 目标 Space；跨 Space 展开必须重新执行目标 Space 授权，并在响应 metadata 中标记 `lazy_link`、`locked`、`accessible` 或等价可见性状态。

### 2.5 Event 是事实

所有协作变化最终都落为签名 `event`。

Event 是审计根和 reducer 输入。当前态只是 Event 集合在某个 reducer profile 下的物化结果。

### 2.6 View 是投影定义

`view` 是一等协议对象，但它拥有的是投影定义的真相，而不是被投影对象的协作事实。它定义查询、过滤、排序、分组、renderer、布局、可见字段和共享 saved view 配置。

同一组 Subject / Room / Board / List / Card / Message / Morph / Relation 可以投影为：

- board
- list
- table
- calendar
- gantt
- chat
- thread
- forum
- graph
- subject activity
- review queue

View 不得发明对象能力，也不得持有对象状态的唯一副本；对象能力来自对象类型、schema/profile 和 capability，facets 只作为已声明能力的查询与投影 hint。Subject 的 surface、Board 包含 List、List 包含 Card、Card 的字段与位置、Room 的消息与成员，都必须由对应标准对象、Relation 和 Event 归约得到。

当用户通过 View 修改协作对象时，写入必须落到真实对象操作。例如 Card 跨 List 拖拽写为 `cx.card.move`，同 List 排序写为 `cx.card.reorder`，修改列顺序写为 `cx.list.reorder`，改变 View 的 filter / columns / layout 才写为 `cx.view.update` 或 actor-private account data。

## 3. 通用字段规则

所有 canonical object 字段 MUST 使用 snake_case。

基础字段：

```json
{
  "id": "cx:card:01js0ke0000000000000000000",
  "type": "card",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "created_by": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "updated_at": "2026-04-26T00:00:00Z",
  "schema": "cx.schema.card.v1"
}
```

对象 ID SHOULD 使用带类型前缀的稳定字符串：

- `cx:space:<ulid>`
- `cx:subject:<ulid>`
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
- 哪些 Subject / Room / Board / Card / Morph 类型可用
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

## 6. Subject

Subject 是 Space 内的语义中心。它表示一个被讨论、推进、引用、审阅、执行或沉淀的“东西本身”，例如事项、议题、决策、事故、客户 case、研究主题、资产或长期记忆锚点。

Subject 保持很薄。它只承载身份连续性、标题、brief、summary、生命周期、语义分类和 surface 关联。它不承载 Room 的消息时间线、Room membership、E2EE epoch、Card 在 Board/List 中的位置、Card 的工作流 reducer、Message thread 或 Document 正文协作。

最小结构：

```json
{
  "id": "cx:subject:01js0sb0000000000000000000",
  "type": "subject",
  "schema": "cx.schema.subject.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "支付重构",
  "brief": "统一支付链路、风控回调和退款状态机。",
  "subject_kind": "initiative",
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

推荐 `subject_kind`：

- `topic`
- `initiative`
- `decision`
- `incident`
- `customer_case`
- `proposal`
- `research`
- `task_cluster`
- `asset`
- `custom`

Subject 与协作 surface 的关系使用 `has_surface`：

- `subject --has_surface--> card`
- `subject --has_surface--> room`
- `subject --has_surface--> morph`
- `subject --has_surface--> view`
- `subject --has_surface--> message`

`has_surface` 的 `fields.surface_role` SHOULD 说明 surface 用途，例如 `status_card`、`primary_discussion`、`review_discussion`、`external_discussion`、`design_doc`、`decision_log`、`activity_view`。同一 Subject MAY 有多个 surface；若某个 role 只允许一个 primary surface，Reducer MUST 按该 profile 的唯一性规则收敛。

Subject 权限只控制 Subject 自身字段和 surface 关系。能读 Subject 不代表能读所有 surface；能进 Room 不代表能改 Subject；能改 Card 不代表能管理 Subject surface。Surface 内容仍由各自对象权限、membership、history visibility、E2EE 和 policy 判断。

Subject activity / timeline 是派生 projection，而不是新的 canonical log。它可以聚合 Subject 事件、surface relation 变化、Card 状态变化、可见 Room 消息摘要和 Document 更新。

## 7. Room

Room 是 Space 内的讨论容器。它承载一个或多个消息时间线、通知规则、历史可见性和可选 E2EE group。

Room 可以独立存在，也可以作为 Subject 的讨论 surface，或通过兼容 Relation 被 Card 关联。Card 可关联 0..N 个 Room；Room 的 membership、policy、history visibility 和 E2EE 独立于 Subject 和 Card。

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
- 能看 Subject 不表示能看它的关联 Room。
- 能看 Room 不表示能看关联 Card。
- Room membership 不授予 Subject 更新或 surface 管理权限。
- Card 成员或负责人变化不自动改变 Room membership。
- Room membership 变化不自动改变 Card 权限。
- Card 删除、归档或移动时不自动删除 Room；只 MAY tombstone 或更新 `links_room` Relation。

## 8. Board / List / Card

Board / List 可作为 `Space.kind` 的工作流容器形态（`kind=board`、`kind=list`）。与其语义一致的标准对象仍保留 `board` / `list` 标识和关系建模路径，便于与已有事件、capability 和 migration 保持兼容。

Board 是工作流容器。List 是 Board 内的列/泳道。Card 是可执行、可跟踪、可沉淀的工作对象，也可以作为 Subject 的状态推进 surface。

Board 最小结构：

```json
{
  "id": "cx:board:01js0bd0000000000000000000",
  "type": "board",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Release Board",
  "kind": "kanban",
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

Card 在 Board/List 中的位置通过 active `contains` Relation / card position event 表达，不由 Subject 或 Room 决定，也不要求 Card canonical object 自带 `board_id` 或 `list_id`。View projection 返回的 `board_id`、`list_id`、`rank` 是投影派生字段。

常见关系：

- `board --contains--> list`
- `list --contains--> card`
- `subject --has_surface--> card`
- `subject --has_surface--> room`
- `card --links_room--> room`
- `card --primary_room--> room`
- `card --assigned_to--> actor`
- `card --depends_on--> card`

## 9. Message

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

Message MAY reply to another Message, mention Actor or object, reference Subject / Card / Morph / Room, or be redacted. 编辑通过 revision chain 表达；撤回通过 redaction/tombstone 表达。

## 10. Morph

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

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph、Subject surface 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象不应为了复用字段而退化为 Morph。

## 11. Relation

最小结构：

```json
{
  "id": "cx:relation:01js0r00000000000000000000",
  "type": "relation",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "relation_kind": "has_surface",
  "from_ref": "cx:subject:01js0sb0000000000000000000",
  "to_ref": "cx:room:01js0rm0000000000000000000",
  "fields": {
    "surface_role": "implementation_discussion",
    "primary": false
  },
  "created_by": "did:web:bob.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Canonical 方向由 `from_ref -> to_ref` 定义。反向语义 SHOULD 由查询层或 schema 派生。

## 12. Event

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
    "cx:event:01js0et0000000000000000000"
  ],
  "auth_refs": [
    "cx:event:01js0sp0000000000000000000",
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

## 13. View

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

## 14. Schema

Schema 约束：

- 标准对象类型
- Morph type 和 facets
- fields
- relation type
- allowed actions
- default views
- validation rules

Schema evolution MUST be additive by default。新版本 SHOULD 保留未知字段，避免旧客户端破坏数据。

## 15. Policy

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

## 16. Invite

Invite 是加入引导对象，不等于 capability grant。

接受 invite 后，相关 capability grant 才进入有效集合。

## 17. Read Marker

`read_marker` 是 actor-private 状态。它 SHOULD 存在于私有 account data 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

## 18. Notification

`notification` SHOULD 是从 Event / Subject / Message / Room / Card / Relation 派生的 inbox projection，不是 canonical truth。

## 19. Reducer 规则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Operation 保持幂等
- 保留未知字段
- 输出可声明的 reducer profile

## 20. 规范性引用

- 标准 event type 注册表见 `../conformance/schema-registry.md`。
- Reducer conformance vector 见 `../conformance/state-resolution-conformance-vectors.md`、`../conformance/redaction-conformance-vectors.md` 和 `../conformance/sync-conformance-vectors.md`。
- Relation cardinality 规则由 `data-structures.md`、`object-model-standard.md` 和各业务 profile 共同定义；未声明可多重的关系 MUST 按 `(space_id, relation_kind, from_ref, to_ref)` 去重。
- Schema evolution 测试见 `../conformance/conformance-profiles.md`。未知字段必须保留，但不得绕过 schema、capability、policy 或 encryption 约束。
