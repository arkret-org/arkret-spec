---
title: Flow & Message
---

## 1. 目标

本文定义 Contrix 协作图中两个最常用的对象：

- **Flow**（`cx:flow:`）：Space 内统一的协作主对象，承载"这件事本身"。
- **Message**（`cx:message:`）：Flow `discussion` track 时间线中的原子消息。

Flow 通过 `tracks` map 表达多种能力面，并可选通过 `discussion_space_ref` 把讨论升级到独立 child Space。Track 模型、access 规则、conflict 收敛、ephemeral 信号都在本文一处讲完。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Flow 概览

Flow 是 Space 内被讨论、推进、引用、审阅、执行或沉淀的统一协作对象。它直接承载"这件事本身"、一组参与者和围绕它的上下文信息。

Flow 适合：

- 产品/工程 initiative
- 决策或提案
- 事故、客户 case、研究主题
- 跨多个团队的任务簇
- 需要长期沉淀的知识主题
- 外部资产或业务对象的协作锚点
- 会话主导的协作线程

Flow 不再定义额外的顶层模式或分类字段；默认入口由 track primary 解析规则决定，业务语义由 Space schema、profile、`fields`、Relation 或 Morph 扩展表达。业务语义分类不属于 Flow 顶层字段。实现 SHOULD 通过 Space schema/profile、`fields`、Relation、labels 或 Morph profile 表达业务类型，并通过 View 定义选择 renderer。

## 3. Flow Schema 与字段

Schema id: `cx.schema.flow.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:flow` | 以 `cx:flow:` 开头。 | Flow ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `title` | yes | `string` | 1..512 chars。 | 标题。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 一句话/一段话简介。 |
| `body` | no | `ContentBlock` | 见 [`content-types.md`](./content-types.md)。 | 富文本正文。 |
| `encrypted_payload` | conditional | `EncryptedPayload` | 与 `body` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹 Flow synthesis 正文或附件内容。 |
| `tracks` | yes | `map<TrackName, FlowTrack>` | 至少 1 个 key；key 唯一性由 map 结构保证；至多 1 个 entry `is_primary=true`。 | 轨道定义、默认入口与轨道访问继承。 |
| `discussion_space_ref` | no | `id:space` | 必须是同 organization / federation 范围内的 Space。 | 该 Flow 的 discussion 时间线、成员、E2EE group 由该 child Space 承载。详见 §5。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.1 最小示例

```json
{
  "id": "cx:flow:019640f9-8000-7000-8000-000000000000",
  "schema": "cx.schema.flow.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "title": "支付重构",
  "summary": "统一支付链路、风控回调和退款状态机；同步 owner、决策与 blocker。",
  "body": {
    "kind": "cx.content.text",
    "body": "Please finish the final review.",
    "format": "markdown",
    "formatted_body": "Please finish the final review."
  },
  "fields": {
    "status": "review",
    "priority": "high",
    "due_at": "2026-05-01T00:00:00Z"
  },
  "tracks": {
    "synthesis": { "is_primary": true },
    "discussion": { "profile": "review" }
  },
  "discussion_space_ref": "cx:space:019640dc-8000-7000-8000-000000000000",
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 4. Tracks 模型

`tracks` 是 active track 定义 map：

- key 是 track 稳定名（`TrackName = ^[a-z][a-z0-9_]{0,63}$`）；
- value 是该 track 的配置对象；
- `is_primary=true` 是可选显式 primary 标记。

标准 track name 为 `synthesis` 与 `discussion`，profile MAY 声明更多 track name。

### 4.1 `FlowTrack` 字段

track 名是 `tracks` map 的 key，不重复在 value 中。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `is_primary` | no | `boolean` | 同一 Flow 至多一个 track 为 true；省略或 false 均表示无显式 primary。 | 是否为显式默认入口。 |
| `profile` | no | `string` | 由 Space schema/profile 定义；标准 discussion profile 可用 `discussion`、`announcement`、`support`、`activity`、`review`、`external`。 | track 交互 profile（pure UI hint）。 |
| `template` | no | `string` | track profile 可声明结构模板。 | 模板引用。 |
| `fields` | no | `object` |  | track-local 扩展字段（pure UI hint，不影响访问）。 |

### 4.2 `synthesis` track

`synthesis` track 承载 Flow 的整理后正式表达。它不是"摘要专栏"，而是 Flow 当前可被编辑、被引用、被推进的主数据面。

适合放入：

- `title`
- `summary`
- `body`
- `fields`
- 状态推进字段
- 结构化业务字段

`body` SHOULD 使用 `content-types.md` 定义的 Content Block；结构化状态和业务字段继续放在 `fields`，不要把可归约状态只藏在富文本正文中。

### 4.3 `discussion` track

`discussion` track 承载会话能力，而不是独立对象。它包含：

- Message timeline
- timeline / notification profile
- 讨论相关 track-local UI hint fields

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
- `discussion` track membership 不从 `assigned_to`、`watchers` 或其他 Flow relation 隐式派生；若实现需要此类映射，必须在父 Space（或 `discussion_space_ref` Space）的 capability / policy 中可审计地声明。
- 当 `discussion` track 不存在或不处于 active 状态时，`cx.message.create`、`cx.message.revise`、`cx.message.redact` MUST 被拒绝，错误语义 SHOULD 为 `discussion_track_disabled` 或等价 fail-closed 结果。

### 4.4 Track 是纯展示标识，不是 access 域

**Track 是纯展示 / 时间线分段标识，不携带独立的 membership / 权限 / history visibility / E2EE**。Track 的访问语义完全继承自所属 Space（或 `discussion_space_ref` 指向的 child Space，见 §5）。

早期 v1 草案曾允许 track 配置内嵌 `access` 子对象表达 `track_scoped` 的 hybrid 模型，该机制已被移除——任何需要独立访问域的 discussion 必须升级为 child Space。

`assigned_to`、watchers 或其他业务关系不会自动成为 discussion 成员，除非 Space policy 明确把它们映射为授权条件。

### 4.5 Primary track 解析规则

若没有显式 `is_primary=true`，Reducer MUST 按确定性规则派生 primary：

1. 若恰好一个 track entry 设置 `is_primary=true`，对应 key 是 primary。
2. 若没有显式 primary 且 `tracks` 中存在 key `synthesis`，`synthesis` 是 primary。
3. 若没有显式 primary 且 map 只有一个 key，该唯一 key 是 primary。
4. 若没有显式 primary，且 profile 声明了可验证默认 track 且该 key 存在于 `tracks`，使用该默认 track。
5. 仍无法唯一确定时，Reducer MUST fail closed，要求写入 `cx.flow.track.set_primary` 或等价修复事件。

`is_primary=false` 与省略 `is_primary` 等价；它不是阻止默认派生的 veto。

resolved primary 只影响默认打开哪个协作面，不改变 `flow_id`，不授予读取、写入或管理权限。

### 4.6 Track 转换

`cx.flow.track.set_primary` 在同一个 Flow 内把目标 `track` 标记为唯一 primary；目标 track 在该事件生效前 MUST 已启用，或与同一批次中的 `cx.flow.track.enable` 一起生效。

规则：

- 转换不改变 `flow_id`。
- 转换不复制或迁移消息历史。
- 切换到 `track="discussion"` 时，若 `discussion` track 尚不存在，必须先写入 `cx.flow.track.enable`；单独的 `set_primary` MUST fail closed / reject，不得隐式创建 track。
- 切换到其他 track 时，不得自动删除 `discussion` track 或既有消息；若需要关闭讨论，必须显式使用 `cx.flow.track.disable` 或 profile 声明的 archive 语义。
- 转换不自动移除 Board Place/List Place 中的 `contains` Relation；是否保留位置由独立的 workflow policy 或后续 `cx.flow.move` 决定。
- `cx.flow.track.set_primary` / `cx.flow.track.enable` 只改变默认入口或 track 启用状态，不得隐式创建或迁移 child Space；child Space 的生命周期由独立 `cx.space.*` event 管理。

### 4.7 Track 启用 / 禁用

- track 在 map 中存在即表示 active。
- 禁用 track 应通过 `cx.flow.track.disable` 从 `tracks` map 中移除该 key 或标记为 profile 声明的 archived state，不得留下可写入的 disabled track。
- View 的 renderer 选择 SHOULD 基于 View 定义、对象类型、Space schema/profile、track config 和可见字段；不得要求 Flow 额外声明模式字段。

## 5. Discussion 独立 Space (`discussion_space_ref`)

需要让 discussion 拥有独立 membership、history visibility 或 MLS group 时，**不再**通过 track hybrid 表达，而是创建一个 child Space 并通过 `Flow.discussion_space_ref` 引用：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `discussion_space_ref` | no | `id:space` | 必须是同 organization / federation 范围内的 Space。 | 该 Flow 的 discussion 时间线、成员、E2EE group 由该子 Space 承载。 |

```json
{
  "tracks": {
    "synthesis": { "is_primary": true },
    "discussion": { "profile": "review" }
  },
  "discussion_space_ref": "cx:space:019640dc-8000-7000-8000-000000000000"
}
```

规则：

- 未设置 `discussion_space_ref` 时，discussion 时间线事件直接写在 Flow 所属 Space，访问规则完全等于父 Space。能看父 Space 的 actor 即可看 discussion 时间线（按父 Space history visibility）。
- 设置 `discussion_space_ref` 时，所有 discussion-side `cx.message.*` / `cx.reaction.*` / track membership 写入 MUST 使用该 child Space 的 `space_id`；child Space 是独立的安全边界，按其自身 policy 收敛。能否看 discussion 由 child Space 自身 access policy 决定，与父 Space 的 Flow synthesis 可见性无关。Flow synthesis 和 discussion 是两个独立 reducer 视图，不共享 cell。
- 能看 `discussion` 不表示能改 Flow 的字段、状态或 Board 位置（这些仍按父 Space capability 判断）。
- 同一 Flow MUST NOT 同时存在 track hybrid（不存在）+ child Space 引用——hybrid 已废弃，只有 child Space 一种方式。
- `discussion_space_ref` 启用 MLS 时，对应 MLS group 绑定该 child Space；E2EE 边界、membership frontier、`covered_frontier_cell` 都按 child Space 自身收敛。
- `discussion_space_ref` 的生命周期由独立 `cx.space.*` event 管理；Flow 不能通过修改自身字段间接 reinit / archive child Space。
- Flow 的 parent Space 与 `discussion_space_ref` Space 之间的关系建议用 `cx.space.parent` / `cx.space.child` 或独立的 governance 关系表达；reducer 不强制 hierarchy，授权仍按各自 Space policy 独立判断。
- 切换 primary track 不会自动删除已有讨论历史。

### 5.1 Track / discussion_space_ref 关系图

下图把 Flow 的 track 模型和 child Space 升级路径画在一起。Flow 只有一份 identity，`tracks` map 的 key 决定可用协作面，是否设置 `discussion_space_ref` 决定 discussion 的访问域落在哪个 Space。

```mermaid
flowchart LR
    subgraph Parent ["cx:space: — Parent Space（capability / E2EE 边界）"]
        direction TB
        Flow["cx:flow:<br/>title / summary / body / fields"]
        Syn["tracks.synthesis<br/>（正式表达，默认 primary）"]
        Dis["tracks.discussion<br/>（会话能力面，纯展示标识）"]
        ParentMsgs["cx:message: ×N<br/>（默认：写在 Parent Space）"]

        Flow -- "tracks 配置" --> Syn
        Flow -- "tracks 配置" --> Dis
        Dis -- "未设 discussion_space_ref" --> ParentMsgs
    end

    subgraph Child ["cx:space: — Child Space（独立 capability / E2EE 边界）"]
        direction TB
        ChildMsgs["cx:message: ×N<br/>（按 child Space policy）"]
        ChildMLS["独立 MLS group / membership / history visibility"]
        ChildMsgs --- ChildMLS
    end

    Flow -. "discussion_space_ref（一旦设置）" .-> Child
    Dis -- "设 discussion_space_ref" --> ChildMsgs
```

读图要点：

- Track 是纯展示 / 时间线分段标识，不携带独立 access；`synthesis` 与 `discussion` 都继承 Parent Space 的 capability。
- `cx.flow.track.set_primary` 只切换默认入口，不复制对象、不迁移历史；切到 `discussion` 必须先 enable 该 track。
- 想给 discussion 独立 membership / E2EE / history 时，**必须**升级为 child Space 并通过 `discussion_space_ref` 引用——hybrid 模式（早期草案的 track 内嵌 access）已废弃。
- 能看 discussion 不等于能改 Flow synthesis 字段或 Board 位置；后者仍按 Parent Space capability 判断。

## 6. Flow 行为规则

- Flow identity 只保存一份，resolved primary track 只决定默认视角，不创建新的对象副本。
- `tracks` 是 map，key 唯一性由结构保证；至多一个 active track MAY 设置 `is_primary=true`。
- 多个显式 primary MUST 被 reducer 拒绝。
- `synthesis` track 与 `discussion` track 共享同一标题和基础字段；track 不存在独立 access 域。
- `synthesis` track 字段级限制使用 capability constraints；不为 `synthesis` 单独创建成员表或 access 域。
- `is_primary` 只是默认入口标记，不授予读取、写入或管理权限。

## 7. Flow 常见关系

- `List Place --contains--> flow`
- `flow --assigned_to--> actor`
- `flow --depends_on--> flow`
- `flow --blocks--> flow`
- `flow --references--> flow / morph / message / blob`
- `flow --derived_from--> flow / morph`
- `flow --summarized_from--> message`
- `flow --promoted_from_discussion--> message`

`assigned_to` 与 `contains` 的基数和跨 Space 规则见 [relation.md](./relation.md) §3-§4。

## 8. Message

### 8.1 概览

Message 是 Flow `discussion` track 时间线中的原子消息对象。

Message 创建是 append-only。编辑通过 revision chain；撤回通过 redaction/tombstone。

未加密消息的 `content` MUST 是 `content-types.md` 定义的 Content Block。E2EE 消息使用 `payload.encrypted_payload` 承载同一 Content Block 的 canonical encrypted envelope；`flow_id`、`message_id`、`reply_to` 等字段只表达归属、目标或关系。

Message MAY reply to another Message, mention Actor or object, reference Flow / Morph / Space, or be redacted.

### 8.2 Schema 与字段

Schema id: `cx.schema.message.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:message` | 以 `cx:message:` 开头。 | Message ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `flow_id` | yes | `id:flow` |  | 所属 Flow。 |
| `track` | yes | `string` | 必须匹配 `^[a-z][a-z0-9_]{0,63}$`，并且必须是目标 Flow 当前 active 的 track name。v1 reducer 默认只识别 `discussion`；profile 可声明额外 track name 承载 Message timeline，但 v1 wire 互操作 SHOULD 使用 `discussion`。 | 所属 Flow 轨道。 |
| `content` | conditional | `object` | 富文本/blocks 见 `content-types.md`；`state=active` 且未加密时必填。 | 消息正文。 |
| `encrypted_payload` | conditional | `EncryptedPayload` | 与 `content` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹消息正文与附件内容。 |
| `state` | yes | `enum(active, redacted, deleted)` | 默认 `active`。`redacted` 由 `cx.message.redact` reducer 设置（content 被替换为 redaction tombstone 但消息槽保留）；`deleted` 表示消息整体被治理或 retention 清除（content / encrypted_payload MUST 被清空，仅保留 envelope 元数据用于审计）。**与 Flow.state / Place.state 在顶层 schema 上对齐**，不再用 `fields.visible_state` 表达可见性。 | 消息生命周期状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `revision_root` | no | `id:message` | 第一条 revision MUST 等于 `id`；后续 revision 引用 chain 起点。同一 `revision_root` 下的 revision 形成有序 chain，由 `cx.message.revise` reducer 维护。 | revision chain 起点（顶层 schema-validated）。 |
| `edited_at` | no | `timestamp` | revision chain 中 latest revise event 的 `created_at`；首次 create 后未编辑时缺省。MUST 不早于 `created_at`。 | 最近一次编辑时间。 |
| `redaction_ref` | conditional | `id:event` | `state=redacted` 时必填，指向触发 redaction 的 `cx.message.redact` event；其他 state MUST 缺省。 | redaction event 引用。 |
| `attachments` | no | `array` | 按 profile 声明，通常通过 Relation `attached_to` 表达。 | 附件 hint。 |
| `fields` | no | `object` | 客户端 metadata、reaction summary 等扩展字段；不再承载 revision / visibility 状态。 | 扩展字段。 |
| `created_by` | yes | `did` |  | 发送者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

> **schema 迁移说明**：早期草案把 `revision_root` / `visible_state` 藏在 `fields` 黑盒中，缺乏 schema 验证、易被实现各自命名。v1 把这些字段提升到顶层；同时用 `state` 顶层枚举替代 `fields.visible_state`、用 `redacted: true` 单一 boolean。`fields.revision_root` / `fields.visible_state` / `fields.redacted` 在 v1 wire 上 MUST 被拒绝（`schema_violation`），不接受双源并存。

### 8.3 最小示例

```json
{
  "id": "cx:message:0196414c-8000-7000-8000-000000000000",
  "schema": "cx.schema.message.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "flow_id": "cx:flow:019640f9-8000-7000-8000-000000000000",
  "track": "discussion",
  "created_by": "did:web:alice.example",
  "content": {
    "kind": "cx.content.text",
    "body": "@bob 请确认这个 item 的 legal 风险。",
    "format": "markdown",
    "formatted_body": "<mention did=\"did:web:bob.example\">@bob</mention> 请确认这个 item 的 legal 风险。"
  },
  "state": "active",
  "revision_root": "cx:message:0196414c-8000-7000-8000-000000000000",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 8.4 Chat 模式示例

讨论型 Space 的最小实施序列：创建 Flow（`discussion` 默认 primary）→
（如需要独立访问域）创建 child Space 并设置 `Flow.discussion_space_ref` →
加入成员 → 发消息 → 编辑 / 撤回 / reaction。

```json
[
  {
    "kind": "cx.flow.create",
    "payload": {
      "object": {
        "id": "cx:flow:019640f9-8000-7000-8000-000000000000",
        "schema": "cx.schema.flow.v1",
        "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
        "title": "项目同步",
        "tracks": {
          "discussion": { "is_primary": true }
        },
        "created_by": "did:web:alice.example",
        "created_at": "2026-04-26T00:00:00Z"
      }
    }
  },
  {
    "kind": "cx.flow.track.enable",
    "target_ref": "cx:flow:019640f9-8000-7000-8000-000000000000",
    "payload": {
      "flow_id": "cx:flow:019640f9-8000-7000-8000-000000000000",
      "track": "discussion"
    }
  },
  {
    "kind": "cx.message.create",
    "payload": {
      "flow_id": "cx:flow:019640f9-8000-7000-8000-000000000000",
      "track": "discussion",
      "content": {
        "kind": "cx.content.text",
        "body": "@bob 请确认这个 flow 的 legal 风险。",
        "format": "markdown"
      }
    }
  }
]
```

`@mention` 与 reference：消息正文 SHOULD 使用结构化 AST 或带 DID/object ref 的
Markdown 链接。客户端 reducer 可从 Message content AST 派生 mention 关系和通知，
但派生关系不得扩大权限。跨 Space 引用按 [relation.md](./relation.md) §4 的跨 Space
规则处理：源消息可暴露 ref 与最小 metadata，目标对象内容与 preview 必须重新按
目标 Space policy 授权。

### 8.5 冲突与收敛规则

Message timeline 的同步与 reducer 行为：

| 场景 | 收敛规则 |
| --- | --- |
| Message 创建 | append-only。Timeline 排序 = causal_depth → HLC → actor_id → actor_seq → event_id。 |
| Message 编辑 | 并发 revision 共存于 revision chain；默认视图显示最新可见 revision。 |
| Message 撤回 | 若 revision 与 redaction 并发，默认视图 redaction 优先；审计视图保留完整历史。 |
| 撤回先到、原消息后到 | 接收方 SHOULD 保留 dangling redaction，待原消息到达后再应用。 |
| Reaction | OR-Set 收敛；同一 actor 对同一 emoji 的 add/remove 由因果关系决定最终成员。 |

历史可见性枚举与 canonical 语义见 [`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)。

### 8.6 Ephemeral 信号

以下高频交互状态 MUST NOT 作为持久化共享对象写入 Event 链：

- typing
- 当前输入草稿
- 临时在线状态
- 高频 read marker

它们 SHOULD 作为 Sync Service 上的 ephemeral signal，或由各端本地缓存。Read
receipt / read marker 的具体规则见 [`../discovery/read-receipts.md`](../discovery/read-receipts.md)。

### 8.7 Message 常见关系

- `flow(discussion) --contains--> message`
- `message --replies_to--> message`
- `message --mentions--> actor / flow / morph`
- `message --references--> flow / morph / blob`

## 9. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Place / Flow 位置语义：[space-and-place.md](./space-and-place.md) §4.6。
- Relation 基数与跨 Space：[relation.md](./relation.md)。
- Content Block：[content-types.md](./content-types.md)。
- Read receipts / read markers：[`../discovery/read-receipts.md`](../discovery/read-receipts.md)。
- 历史可见性 / E2EE：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Flow / Message schema：`artifacts/schemas/flow.schema.json`、`artifacts/schemas/message.schema.json`。
