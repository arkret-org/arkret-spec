---
title: Standard Object Types
---

## 1. 目标

本文定义 Contrix 的标准对象类型。标准对象是一等协议对象，拥有明确的主语义、字段约束和 reducer 行为。

核心字段类型、必填性和通用约束见 `data-structures.md`。本文定义标准对象的业务语义、推荐字段、推荐关系和推荐 facets。

原则：

- 标准类型提供主语义。
- `flow` 是统一协作主对象，承载协作议题、任务、正式表达与讨论轨道。
- `morph` 提供开放扩展。
- `facets` 是由 Space schema / Morph profile 声明的能力提示和查询标签，不替代对象类型，也不单独定义授权、状态机、排序或 reducer 语义。
- View 只定义如何投影对象；它拥有自己的定义状态，但不发明对象能力，也不持有被投影对象的协作事实。

## 2. Flow

`flow` 表示 Space 内被讨论、推进、引用、审阅、执行或沉淀的统一协作对象。Flow 不再定义额外的顶层模式或分类字段；默认入口由 track primary 解析规则决定，业务语义由 Space schema、profile、`fields`、Relation 或 Morph 扩展表达。

Flow 适合：

- 产品/工程 initiative
- 决策或提案
- 事故、客户 case、研究主题
- 跨多个团队的任务簇
- 需要长期沉淀的知识主题
- 外部资产或业务对象的协作锚点
- 会话主导的协作线程

推荐字段：

- `title`
- `description`
- `brief`
- `summary`
- `body`
- `fields`
- `tracks`
- `state`

### 2.1 `tracks`

`tracks` 是 Flow 的 track 定义数组。每个元素至少包含 `name`；`is_primary=true` 是可选显式 primary 标记。

示例：

```json
{
  "tracks": [
    {
      "name": "synthesis",
      "is_primary": true
    },
    {
      "name": "discussion",
      "profile": "discussion",
      "access": {
        "membership": "inherit_flow",
        "permissions": "inherit_flow",
        "history_visibility": "joined",
        "e2ee": "inherit_space"
      }
    }
  ]
}
```

规则：

- 每个 Flow MUST 至少有一个 active track。
- `tracks[].name` 在同一个 Flow 内 MUST 唯一。`synthesis` 与 `discussion` 是 v1 标准 track 名；profile MAY 声明更多 track 名。
- 同一个 Flow 中至多一个 track MAY 设置 `is_primary=true`。多个显式 primary MUST 被 schema / reducer 拒绝。
- 若没有 track 显式设置 `is_primary=true`，Reducer MUST 按确定性规则派生 primary：若存在 `name="synthesis"`，选择 `synthesis`；否则若只有一个 track，选择该 track；否则若 profile 声明了默认 track 且该 track 存在，选择该 track；仍无法唯一确定时 MUST fail closed，要求写入 `cx.flow.track.set_primary` 或等价修复事件。
- `is_primary=false` 与省略 `is_primary` 等价；它不是阻止默认派生的 veto。
- resolved primary 只影响默认打开哪个协作面，不改变 `flow_id`，不授予读取、写入或管理权限。
- track 存在即表示 active；禁用 track 应通过 `cx.flow.track.disable` 从 active track 集合移除或标记为 profile 声明的 archived state，不得留下可写入的 disabled track。
- View 的 renderer 选择 SHOULD 基于 View 定义、对象类型、Space schema/profile、track config 和可见字段；不得要求 Flow 额外声明模式字段。
- 业务语义过滤 SHOULD 使用 Space schema/profile、`fields`、Relation、labels 或 Morph profile；不得通过 Flow 顶层分类字段形成核心协议语义。

### 2.2 `synthesis` track

`synthesis` track 承载 Flow 的整理后正式表达。它不是“摘要专栏”，而是 Flow 当前可被编辑、被引用、被推进的主数据面。

适合放入：

- `title`
- `description`
- `brief`
- `summary`
- `body`
- `fields`
- 状态推进字段
- 结构化业务字段

`body` SHOULD 使用 `content-types.md` 定义的 Content Block；结构化状态和业务字段继续放在 `fields`，不要把可归约状态只藏在富文本正文中。

### 2.3 `discussion` track

`discussion` track 承载会话能力，而不是独立对象。它包含：

- Message timeline
- timeline / notification profile
- 讨论相关 track-local UI hint fields

推荐字段：

- `profile`
- `fields`

`profile` 初版建议支持：

- `discussion`
- `announcement`
- `support`
- `activity`
- `review`
- `external`

规则：

- `profile` 是 discussion track 的 UI / 语义 hint，不是自动授权后门。
- `announcement`、`review` 等 posting 约束 MUST 通过 capability / policy 表达，不得只靠 `profile` 字符串隐式生效。
- `activity` SHOULD 允许系统/agent 产生状态播报，但 reducer 仍按普通 Message timeline 处理。
- Track 不携带独立 access：membership、permission、history visibility 与 E2EE 完全继承父 Space。需要让 discussion 拥有独立访问域时，必须升级到 child Space 并通过 `Flow.discussion_space_ref` 引用（详见 [`data-structures.md`](./data-structures.md) §6.1.1）。
- `discussion` track membership 不从 `assigned_to`、`watchers` 或其他 Flow relation 隐式派生；若实现需要此类映射，必须在父 Space（或 `discussion_space_ref` Space）的 capability / policy 中可审计地声明。
- 当 `discussion` track 不存在或不处于 active 状态时，`cx.message.create`、`cx.message.revise`、`cx.message.redact` MUST 被拒绝，错误语义 SHOULD 为 `discussion_track_disabled` 或等价 fail-closed 结果。

### 2.4 Track 与 Access 模型

`tracks[]` **只**表达 track 是否存在、哪个 track 是默认入口、以及 track 的 UI / 时间线 profile。它不携带 access、membership、history visibility 或 E2EE 字段——早期 v1 草案曾允许 `tracks[].access` 子对象表达 `track_scoped` 的 hybrid 模型，该机制已被移除。

Access 模型现在只有两种形态：

| 形态 | 触发 | 语义 |
| --- | --- | --- |
| 继承父 Space（默认） | `Flow.discussion_space_ref` 未设置 | discussion 时间线、成员、history visibility、E2EE 完全继承父 Space。 |
| 独立 child Space | `Flow.discussion_space_ref = cx:space:...` | 所有 discussion 写入 child Space；child Space 是独立安全边界，按其自身 policy 收敛。 |

```json
{
  "tracks": [
    { "name": "synthesis", "is_primary": true },
    { "name": "discussion", "profile": "review" }
  ],
  "discussion_space_ref": "cx:space:01js0ds0000000000000000000"
}
```

规则：

- `synthesis` track 字段级限制使用 capability constraints；不为 `synthesis` 单独创建成员表或 access 域。
- `discussion_space_ref` 的生命周期由独立 `cx.space.*` event 管理；Flow 不能通过修改自身字段间接 reinit / archive child Space。

### 2.5 转换

`cx.flow.track.set_primary` 在同一个 Flow 内把目标 `track` 标记为唯一 primary；目标 track 在该事件生效前 MUST 已启用，或与同一批次中的 `cx.flow.track.enable` 一起生效。

规则：

- 转换不改变 `flow_id`。
- 转换不复制或迁移消息历史。
- 切换到 `track="discussion"` 时，若 `discussion` track 尚不存在，必须先写入 `cx.flow.track.enable`；单独的 `set_primary` MUST fail closed / reject，不得隐式创建 track。
- 切换到其他 track 时，不得自动删除 `discussion` track 或既有消息；若需要关闭讨论，必须显式使用 `cx.flow.track.disable` 或 profile 声明的 archive 语义。
- 转换不自动移除 Board Place/List Place 中的 `contains` Relation；是否保留位置由独立的 workflow policy 或后续 `cx.flow.move` 决定。

### 2.6 常见关系

- `List Place --contains--> flow`
- `flow --assigned_to--> actor`
- `flow --depends_on--> flow`
- `flow --blocks--> flow`
- `flow --references--> flow / morph / message / blob`
- `flow --derived_from--> flow / morph`
- `flow --summarized_from--> message`
- `flow --promoted_from_discussion--> message`

## 3. Board Place

Board Place 是 `Place` 的看板形态，ID 使用 `cx:place:` 格式（`kind=board`）。Place 永远住在某 Space 内，不形成自己的 membership / E2EE / federation 边界——授权透明回退到 `space_id` 指向的 Space。看板类型、泳道策略、WIP 规则和自定义 workflow profile SHOULD 进入 `fields` 或 Place schema。

推荐字段：

- `title`
- `summary`
- `rank`
- `fields`（包含 `default_view_id` 等）
- `state` / `state_changed_at`（统一生命周期字段，详见 [`data-structures.md`](./data-structures.md) §4a）

常见关系：

- `Board Place --contains--> List Place`
- `Board Place --has_default_view--> view`

## 4. List Place

List Place 是 `Place` 的列/泳道形态，ID 使用 `cx:place:` 格式（`kind=list`）。List Place 通过 `parent_ref` 挂载到 Board Place（或同 Space 内的其他 Place）下，由 `cx.place.parent` reducer-input 管理（cas-register, bottom=reject）。

推荐字段：

- `title`
- `summary`
- `rank`
- `fields`（包含 `wip_limit` 等）
- `state` / `state_changed_at`（统一生命周期字段，详见 [`data-structures.md`](./data-structures.md) §4a）

常见关系：

- `Board Place --contains--> List Place`
- `List Place --contains--> flow`

## 5. Message

`message` 表示 Flow `discussion` track 时间线中的原子消息。

推荐字段：

- `flow_id`
- `track`
- `content`
- `attachments`
- `revision_root`
- `edited_at`
- `visible_state`
- `redaction_ref`

常见关系：

- `flow(discussion) --contains--> message`
- `message --replies_to--> message`
- `message --mentions--> actor / flow / morph`
- `message --references--> flow / morph / blob`

Message 创建是 append-only。编辑通过 revision chain；撤回通过 redaction/tombstone。

未加密消息的 `content` MUST 是 `content-types.md` 定义的 Content Block。E2EE 消息使用 `payload.encrypted_payload` 承载同一 Content Block 的 canonical encrypted envelope；`flow_id`、`message_id`、`reply_to` 等字段只表达归属、目标或关系。

### 5.1 Chat 模式示例

讨论型 Space 的最小实施序列：创建 Flow（`discussion` 默认 primary）→
（如需要独立访问域）创建 child Space 并设置 `Flow.discussion_space_ref` →
加入成员 → 发消息 → 编辑 / 撤回 / reaction。

```json
[
  {
    "kind": "cx.flow.create",
    "payload": {
      "object": {
        "id": "cx:flow:01js0fk0000000000000000000",
        "schema": "cx.schema.flow.v1",
        "space_id": "cx:space:01js0sp0000000000000000000",
        "title": "项目同步",
        "tracks": [
          { "name": "discussion", "is_primary": true }
        ],
        "created_by": "did:web:alice.example",
        "created_at": "2026-04-26T00:00:00Z"
      }
    }
  },
  {
    "kind": "cx.flow.track.enable",
    "target_ref": "cx:flow:01js0fk0000000000000000000",
    "payload": {
      "flow_id": "cx:flow:01js0fk0000000000000000000",
      "track": "discussion"
    }
  },
  {
    "kind": "cx.message.create",
    "payload": {
      "flow_id": "cx:flow:01js0fk0000000000000000000",
      "track": "discussion",
      "content": {
        "type": "cx.content.text",
        "body": "@bob 请确认这个 flow 的 legal 风险。",
        "format": "markdown"
      }
    }
  }
]
```

`@mention` 与 reference：消息正文 SHOULD 使用结构化 AST 或带 DID/object ref 的
Markdown 链接。客户端 reducer 可从 Message content AST 派生 mention 关系和通知，
但派生关系不得扩大权限。跨 Space 引用按 `object-model-core.md` 的跨 Space
规则处理：源消息可暴露 ref 与最小 metadata，目标对象内容与 preview 必须重新按
目标 Space policy 授权。

### 5.2 冲突与收敛规则

Message timeline 的同步与 reducer 行为：

| 场景 | 收敛规则 |
| --- | --- |
| Message 创建 | append-only。Timeline 排序 = causal_depth → HLC → actor_id → actor_seq → event_id。 |
| Message 编辑 | 并发 revision 共存于 revision chain；默认视图显示最新可见 revision。 |
| Message 撤回 | 若 revision 与 redaction 并发，默认视图 redaction 优先；审计视图保留完整历史。 |
| 撤回先到、原消息后到 | 接收方 SHOULD 保留 dangling redaction，待原消息到达后再应用。 |
| Reaction | OR-Set 收敛；同一 actor 对同一 emoji 的 add/remove 由因果关系决定最终成员。 |

历史可见性枚举与 canonical 语义见 [`authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)。

### 5.3 Ephemeral 信号

以下高频交互状态 MUST NOT 作为持久化共享对象写入 Event 链：

- typing
- 当前输入草稿
- 临时在线状态
- 高频 read marker

它们 SHOULD 作为 Sync Service 上的 ephemeral signal，或由各端本地缓存。Read
receipt / read marker 的具体规则见 [`discovery/read-receipts.md`](../discovery/read-receipts.md)。

## 6. Morph

`morph` 是开放形态对象，用于承载 schema / profile 声明的扩展业务类型。

Morph 适合：

- 自定义业务对象
- 插件对象
- 外部系统镜像对象
- 未来标准类型的试验对象
- 不要求强互操作的弱结构数据

Morph 是扩展缓冲层，不是标准对象的替代品。Flow、Message 和 Space workflow 的主语义已经由标准对象类型定义；实现不得为了复用字段、renderer 或插件机制而把这些对象改写为 Morph。

推荐字段：

- `morph_type`
- `title`
- `summary`
- `content`
- `fields`
- `facets`

## 7. Actor Profile

`actor_profile` 是 Actor 在协作图中的展示镜像。

它用于：

- mention
- assignment
- display
- team membership view

Actor Profile 不替代 DID，也不成为权限主键。

## 8. 标准 Facets

Facets 是 schema-declared capability hints，不是对象身份。标准对象 MAY 暴露 schema/profile 已声明的 facets 来辅助展示或查询，但标准对象的核心语义不依赖 facets 才成立；Morph MAY 使用 facets 帮助 View、本地搜索、UI 和插件做过滤、降级展示和默认 renderer 选择。

Facets MUST NOT 成为授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作的唯一规范来源。这些语义必须由 Space schema / Morph profile / event registry / capability action 明确定义。Facet 配置可以引用这些 profile 或暴露 UI hints，但不能替代它们。

| Facet | 说明 |
| --- | --- |
| `container` | 可包含、排序或移动其他对象。 |
| `replyable` | 可被回复，形成 thread / discussion。 |
| `schedulable` | 有时间窗口，可进入 calendar / gantt。 |
| `assignable` | 可分配给 actor / team / agent。 |
| `stateful` | 有受控状态机。 |
| `rankable` | 有稳定手动排序 rank。 |
| `reviewable` | 可进入审核/审阅队列。 |
| `notifiable` | 可派生 notification / inbox / read state。 |
| `documentable` | 可作为文档或 section root。 |
| `renderable` | 声明允许的默认展示面。 |

## 9. Schema Evolution

标准类型演进 MUST 遵守：

- 新字段优先 optional。
- 既有字段不得静默改变语义。
- reducer 和客户端 MUST 保留未知字段。
- UI 遇到未知 Morph type SHOULD 降级为 generic Morph card。
- 标准对象不得阻止 Space 定义自定义 Morph type。

## 10. 规范性引用

- Flow / Message / track 规则见 §5.1-§5.3 与 `object-model-core.md` §6-§9。
- Flow / Space / Message 的核心字段见 `data-structures.md`。
- View 投影规则见 `views.md`。
- 授权规则见 `../authz/capabilities.md` 与 `../authz/event-auth-state-resolution.md`。
