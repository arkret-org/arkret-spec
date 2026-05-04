# Object Model Core

## 1. 目标

Contrix 的核心数据模型不是 room-first，也不是万能 `Entity`。它是一张以 Space 为边界、以标准对象和开放 Morph 共同组成的可审计协作图。

核心对象：

- `space`（包含 Space (kind=board) 与 Space (kind=list) 子类型）
- `actor_profile`
- `flow`
- `message`
- `morph`
- `relation`
- `event`
- `view`
- `policy`
- `invite`
- `read_marker`
- `notification`
- `capability`

辅助对象（SDK 内部或非持久化 canonical 对象）：

- `operation`（SDK 内部可寻址中间对象）
- `event_batch_receipt`（可选加速/审计对象）

注：`schema` 不作为独立 `type` 枚举值。Schema 约束通过 `schema_refs` 字段引用和 `cx.schema.define` / `cx.schema.update` state event 管理。`policy` 同时具有 `type` 枚举值和 state event 形态。

字段级结构、必填性、类型和约束见 `data-structures.md`。本文保留核心模型语义和示例，具体 JSON Schema SHOULD 从 `data-structures.md` 与 `schema-registry.md` 生成。

## 2. 基本原则

### 2.1 Space 边界与容器

`space` 有两种规范性 profile：

- `boundary_profile="security_boundary"`：复制、权限、schema、policy、membership、history visibility、加密和索引的硬边界。
- `boundary_profile="container"`：安全边界内的工作流容器，用于稳定 ID、排序、View / Relation anchor 和局部元数据；不形成独立 membership、join rule、history visibility、MLS group、federation topology 或 plaintext-visible service。

标准 `Space.kind` 中，`collaboration`、`personal`、`project`、`organization` 和 `enclave` 默认是 `security_boundary`；`board` 和 `list` 默认是 `container`。实现不得仅凭 `type="space"` 就假定对象一定形成新安全边界，必须按 `boundary_profile` 或由 `kind` 派生的默认值判断。

一个 Space 可以包含多个：

- Flow
- Board
- List
- Document
- Morph

Security-boundary Space MAY 通过 `cx.space.child` / `cx.space.parent` 形成层级或图状组织，但 child security-boundary Space 仍然是独立边界。membership、capability、history visibility、schema、policy 和 encryption key 默认不从 parent 级联到 child；任何继承都必须由 child Space 显式声明。详细规则见 `space-hierarchy.md`。

`boundary_profile="container"` 的 Board/List 不是这里所说的独立 child security boundary。它们可以使用 `cx.space.child` / `cx.space.parent` 或 Relation 表达导航和包含关系，但授权、history、E2EE 和 federation 解析回最近的 security-boundary Space。

### 2.2 Flow 承载主语义

协议不再把同一个协作主题拆成 `subject`、`room`、`card` 三个互相跳转的标准对象。

标准对象本身表达主语义：

- `flow`：统一协作主对象。它承载标题、description、brief、summary 等基础字段，并通过 `kind` 决定默认视角：`card` 偏整理与推进，`room` 偏讨论和协作。
- `message`：Flow `discussion` branch 中的消息。
- `morph`：开放形态对象，用于业务扩展、未知类型和实验对象。
- Space (kind=board) 和 Space (kind=list) 通过 Space 层级表达工作流容器，并管理 `kind="card"` 的 Flow 位置。

标准对象 MAY 暴露 schema/profile 已声明的 `facets` 来辅助展示或查询，但它的核心职责不依赖 facets 才成立。例如 `flow` 天然是共享上下文容器；`kind="card"` 天然适合作为 Space (kind=board)/Space (kind=list) 管理的工作对象；`kind="room"` 天然适合作为讨论入口；`message` 天然属于 Flow `discussion` branch。实现不得要求标准对象先声明 facet 才能承认其主语义。

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
- `replies_to`
- `depends_on`
- `blocks`
- `mentions`
- `assigned_to`
- `references`
- `derived_from`
- `summarized_from`
- `promoted_from_discussion`

Relation 连接的是对象引用。标准字段使用 `from_ref` / `to_ref`，其值可以指向 `flow`、`message`、`morph`、`actor` 或 `space`（包括 Space (kind=board) 和 Space (kind=list)）。

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

同一组 Flow / Message / Morph / Relation 可以投影为：

- board
- list
- table
- calendar
- gantt
- chat
- thread
- forum
- graph
- flow activity
- review queue

View 不得发明对象能力，也不得持有对象状态的唯一副本；对象能力来自对象类型、schema/profile 和 capability，facets 只作为已声明能力的查询与投影 hint。Space (kind=board) 包含 Space (kind=list)、Space (kind=list) 包含 Flow、Flow 的字段与位置、Flow `discussion` branch 的消息与成员，都必须由对应标准对象、Relation 和 Event 归约得到。

当用户通过 View 修改协作对象时，写入必须落到真实对象操作。例如 Flow 跨 List 拖拽写为 `cx.flow.move`，同 List 排序写为 `cx.flow.reorder`，修改列顺序写为 `cx.space.update`（更新 Space (kind=list) 的 `rank` 字段），改变 View 的 filter / columns / layout 才写为 `cx.view.update` 或 actor-private account data。

## 3. 通用字段规则

所有 canonical object 字段 MUST 使用 snake_case。

基础字段：

```json
{
  "id": "cx:flow:01js0ke0000000000000000000",
  "type": "flow",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "created_by": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "updated_at": "2026-04-26T00:00:00Z",
  "schema": "cx.schema.flow.v1"
}
```

对象 ID SHOULD 使用带类型前缀的稳定字符串：

- `cx:space:<ulid>`
- `cx:flow:<ulid>`
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
- 哪些 Flow / Morph 类型与 branch profile 可用
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

## 6. Flow

Flow 是 Space 内统一的协作主对象。它取代 Subject / Room / Card 的三实体拆分，直接承载“这件事本身”、一组参与者和围绕它的上下文信息。

Flow 通过三层语义表达差异：

- `kind`：主模式。`card` 默认主入口是 `synthesis` branch；`room` 默认主入口是 `discussion` branch。
- `semantic_kind`：业务语义分类，例如 `initiative`、`decision`、`incident`。
- `branches`：能力分支。`synthesis` branch 承载整理后的正式表达、结构化字段和推进信息；`discussion` branch 承载聊天和讨论 timeline。
- `access`：branch 默认继承与显式 override。缺省情况下 branch 使用同一 Flow / Space 授权体系；只有声明 branch-scoped override 时，才形成独立成员、历史或 E2EE 边界。

由于 `room` 和 `card` 只是同一 Flow 的两种模式，实现 MAY 通过 `cx.flow.convert` 在二者之间切换。转换不会改变 Flow identity，也不要求复制或迁移消息历史。

最小结构：

```json
{
  "id": "cx:flow:01js0fk0000000000000000000",
  "type": "flow",
  "schema": "cx.schema.flow.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "kind": "card",
  "semantic_kind": "initiative",
  "title": "支付重构",
  "description": "统一支付链路、风控回调和退款状态机。",
  "brief": "同步 owner、决策和 blocker。",
  "summary": "内容与讨论收敛在同一个 Flow 内。",
  "body": {
    "format": "markdown",
    "text": "Please finish the final review."
  },
  "fields": {
    "status": "review",
    "priority": "high",
    "due_at": "2026-05-01T00:00:00Z"
  },
  "primary_branch": "synthesis",
  "branches": {
    "synthesis": {
      "enabled": true
    },
    "discussion": {
      "enabled": true,
      "room_kind": "review"
    }
  },
  "access": {
    "defaults": {
      "membership": "inherit_flow",
      "permissions": "inherit_flow",
      "e2ee": "inherit_space"
    },
    "branch_overrides": {
      "discussion": {
        "membership": "branch_scoped",
        "permissions": "branch_scoped",
        "history_visibility": "joined",
        "e2ee": "branch_scoped",
        "encryption_profile": "mls_rfc9420",
        "membership_policy_ref": "cx:policy:01js0rp0000000000000000000"
      }
    }
  },
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Flow 规则：

- Flow identity 只保存一份，`kind` 和 `primary_branch` 只决定默认视角，不创建新的对象副本。
- `synthesis` branch 与 `discussion` branch 可以共享同一标题和基础字段，branch reducer 只负责对应交互面当前态。
- branch access 默认继承 Flow / Space；`discussion` branch 的 membership、history visibility 和 E2EE 只有在显式 override 时才独立收敛，且不得放大 `synthesis` branch 的可见字段。
- `primary_branch` 只是默认入口，不授予读取、写入或管理权限。

## 7. Flow Discussion Branch

Flow 的 `discussion` branch 是会话能力，而不是独立对象。它承载消息时间线和通知 profile；历史可见性、成员表和可选 E2EE group 通过 Flow `access` 或 policy/capability state event 显式声明。

`kind="room"` SHOULD 默认创建并启用 `discussion` branch，且 `primary_branch` SHOULD 为 `discussion`。`kind="card"` MAY 初始只带 `synthesis` branch；需要讨论时再启用 `discussion` branch。

Discussion branch 规则：

- 能看 Flow synthesis 只有在有效 access policy 继承或授予 discussion 读取时，才表示能看 `discussion` branch。
- 能看 `discussion` branch 不表示能改 Flow 的字段、状态或 Board 位置。
- branch-scoped `discussion` membership 不自动改变 Flow assignment、Flow visibility 或 Space membership。
- Flow 从 `card` 转成 `room`，或从 `room` 转成 `card`，都不自动删除已有讨论历史。

## 8. Space (kind=board) / Space (kind=list) / Flow

Space (kind=board) 与 Space (kind=list) 是 `Space` 的工作流容器形态，使用 `cx:space:` ID，但默认 `boundary_profile="container"`。Space (kind=board) 是工作流容器；Space (kind=list) 是 Space (kind=board) 内的列/泳道；Space (kind=board) / Space (kind=list) 默认管理 `kind="card"` 的 Flow。

Space (kind=board) 最小结构：

```json
{
  "id": "cx:space:01js0bd0000000000000000000",
  "type": "space",
  "kind": "board",
  "boundary_profile": "container",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Release Board",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Space (kind=list) 最小结构：

```json
{
  "id": "cx:space:01js01s0000000000000000000",
  "type": "space",
  "kind": "list",
  "boundary_profile": "container",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "Review",
  "rank": "mV",
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Space (kind=board)/Space (kind=list) 中的 Flow 示例：

```json
{
  "id": "cx:flow:01js0cd0000000000000000000",
  "type": "flow",
  "schema": "cx.schema.flow.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "kind": "card",
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

Flow 在 Space (kind=board) / Space (kind=list) 中的位置通过 active `contains` Relation / flow position event 表达，不由 branch 决定，也不要求 Flow canonical object 自带 `board_id` 或 `list_id`。View projection 返回的 `board_id`、`list_id`、`rank` 是投影派生字段。

常见关系：

- `board --contains--> list`
- `list --contains--> flow`
- `flow --assigned_to--> actor`
- `flow --depends_on--> flow`
- `message --references--> flow`

## 9. Message

Message 是 Flow `discussion` branch 时间线中的原子消息对象。

```json
{
  "id": "cx:message:01js0ms0000000000000000000",
  "type": "message",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "flow_id": "cx:flow:01js0fk0000000000000000000",
  "branch": "discussion",
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

Message MAY reply to another Message, mention Actor or object, reference Flow / Morph / Space, or be redacted. 编辑通过 revision chain 表达；撤回通过 redaction/tombstone 表达。

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

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph、Flow branch projection 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象不应为了复用字段而退化为 Morph。

## 11. Relation

最小结构：

```json
{
  "id": "cx:relation:01js0r00000000000000000000",
  "type": "relation",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "relation_kind": "contains",
  "from_ref": "cx:space:01js0bd0000000000000000000",
  "to_ref": "cx:flow:01js0cd0000000000000000000",
  "fields": {
    "rank": "mV"
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
  "kind": "cx.flow.update",
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
    "flow_id": "cx:flow:01js0cd0000000000000000000",
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
  "type": "view",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "schema": "cx.schema.view.v1",
  "kind": "collection",
  "renderer": "board",
  "query": {
    "object_types": ["flow"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "source_ref": "cx:space:01js0bd0000000000000000000",
      "depth": 2
    }
  },
  "collection": {
    "item_object_types": ["flow"],
    "item_render": "card",
    "item_order_by": [
      { "field": "fields.rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_id": "cx:space:01js0bd0000000000000000000",
      "container_relation_kind": "contains",
      "item_relation_kind": "contains"
    }
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at"
  ],
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
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

`notification` SHOULD 是从 Event / Flow / Message / Relation 派生的 inbox projection，不是 canonical truth。

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
