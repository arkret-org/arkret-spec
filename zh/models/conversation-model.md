# Conversation Model

## 1. 目标

Contrix 的会话模型不再把 `subject`、`room`、`card` 拆成三个需要互相跳转的对象。v1 改为由 `flow` 承载统一 identity，再通过 `discussion` branch 承载会话能力。

## 2. 设计原则

- `flow` 是唯一主对象；`kind` 只决定默认视角。
- `discussion` branch 是会话能力，不是独立对象。
- `message` 永远写入 `flow` 的 `discussion` branch。
- `kind="card"` 默认走 `synthesis` branch，但 MAY 开启 `discussion` branch。
- `kind="room"` 默认走 `discussion` branch，但仍保留统一基础字段与可选 `synthesis` branch。
- `semantic_kind` 承载业务语义分类，例如 `decision`、`incident`、`task_cluster`。
- `cx.flow.convert` 允许在 `card` 和 `room` 模式之间切换，且不改变 Flow identity。

`comment` 和 `message` 都可以存在，但语义不同：

- `comment`：对象上的 durable note / review / approval note，可作为 Flow/Morph 字段或专用 profile。
- `message`：Flow `discussion` branch 时间线中的聊天或讨论消息。

## 3. Flow Discussion Branch

Flow 的 `discussion` branch 适合：

- 团队聊天
- 项目讨论
- Flow 相关审阅
- 卡片上下文讨论
- 外部协作沟通
- agent 运行播报流

示例：

```json
{
  "id": "cx:flow:01js1000000000000000000000",
  "type": "flow",
  "schema": "cx.schema.flow.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "kind": "room",
  "semantic_kind": "initiative",
  "title": "release-engineering",
  "description": "Engineering coordination for release readiness.",
  "brief": "默认以讨论为主入口。",
  "primary_branch": "discussion",
  "branches": {
    "synthesis": {
      "enabled": true
    },
    "discussion": {
      "enabled": true,
      "room_kind": "discussion",
      "history_visibility": "joined",
      "membership_policy_ref": "cx:policy:01js0rp0000000000000000000"
    }
  },
  "created_by": "did:web:alice.example"
}
```

`room_kind` 初版建议支持：

- `discussion`
- `announcement`
- `support`
- `activity`
- `review`
- `external`

## 4. Message

Message 是 Flow `discussion` branch 时间线中的原子消息对象。

示例：

```json
{
  "id": "cx:message:01js1000000000000000000002",
  "type": "message",
  "schema": "cx.schema.message.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "flow_id": "cx:flow:01js1000000000000000000000",
  "branch": "discussion",
  "created_by": "did:web:alice.example.com",
  "content": {
    "format": "markdown",
    "text": "@bob 请确认这个 flow 的 legal 风险。"
  },
  "fields": {
    "revision_root": "cx:message:01js1000000000000000000002",
    "visible_state": "active"
  }
}
```

message 与 flow/reply/mention 的关系使用 Relation 或 message 字段表达：

- `flow(discussion) --contains--> message`
- `message --replies_to--> message`
- `message --mentions--> actor / flow / morph`
- `message --references--> flow / board / morph / blob`

## 5. Flow 模式与转换

Flow 通过 `kind` 和 `primary_branch` 表达默认交互方式：

- `kind="room"`：默认 `primary_branch="discussion"`，适合会话主导的对象。
- `kind="card"`：默认 `primary_branch="synthesis"`，适合状态推进、字段编辑和 Board/List 管理。
- `semantic_kind`：例如 `decision`、`incident`、`research`，用于业务过滤、默认 View 和 agent policy。

`kind="card"` MAY 开启 `discussion` branch。开启后，该 Flow 仍然是同一个对象，只是多了讨论能力。

```json
{
  "kind": "cx.flow.branch.enable",
  "target_ref": "cx:flow:01js0cd0000000000000000000",
  "content": {
    "flow_id": "cx:flow:01js0cd0000000000000000000",
    "branch": "discussion",
    "config": {
      "room_kind": "implementation",
      "history_visibility": "joined"
    }
  }
}
```

Room/Card 互转通过 `cx.flow.convert` 完成：

```json
{
  "kind": "cx.flow.convert",
  "target_ref": "cx:flow:01js0cd0000000000000000000",
  "content": {
    "flow_id": "cx:flow:01js0cd0000000000000000000",
    "to_kind": "room",
    "primary_branch": "discussion",
    "ensure_branches": ["discussion"]
  }
}
```

转换规则：

- 转换不改变 `flow_id`。
- 转换不复制或迁移消息历史。
- 转换到 `kind="room"` 时，若 `discussion` branch 尚未启用，Reducer MUST 自动启用它，或在 policy 禁止时 fail closed。
- 已启用的 `discussion` branch 在转换后继续保留。
- Flow 的 Board/List 位置、字段和讨论历史由各自 reducer 独立维护。

## 6. Discussion Branch Membership

Discussion branch membership 是 Space 内的子范围授权。它不替代 Space membership，也不扩展 Flow `synthesis` branch 的编辑权限。

推荐状态事件：

```json
{
  "kind": "cx.flow.branch.member",
  "state_key": "cx:flow:01js0rm0000000000000000000|discussion|did:web:bob.example",
  "content": {
    "flow_id": "cx:flow:01js0rm0000000000000000000",
    "branch": "discussion",
    "member": "did:web:bob.example",
    "membership": "join",
    "reason": "invited"
  }
}
```

规则：

- Discussion participant MUST satisfy Space policy。高安全 Space MAY 要求所有 discussion 成员也是 Space member。
- Space policy MAY allow flow-scoped external admission，但该 admission 不授予其他 Flow、Board、Morph 或 Space directory 可见性。
- Discussion membership 只控制该 branch 的消息读取、发送、历史和通知。
- Discussion membership 不改变 Flow assignment、Flow visibility、Board position 或 Space membership。
- `assigned_to`、watchers 或其他 Flow relation 不自动成为 discussion member。

## 7. `@mention` 与引用

为避免正文与引用关系脑裂，消息正文 SHOULD 使用结构化 AST 或带 DID/object ref 的 Markdown 链接。

客户端提交或编辑消息时 MAY 不提交独立 `mentions` Relation。客户端 reducer 可以从 Message content AST 派生 mention 关系和通知，但派生关系不得扩大权限。

消息正文、mention 或 `references` Relation 指向其他 Space 对象时，按 `object-model-core.md` 的跨 Space 引用规则处理。源消息可以暴露 ref 本身和最小引用 metadata；目标对象内容、preview、成员、附件和历史必须重新按目标 Space policy 授权。不可见目标 MUST 呈现为 Lazy Link / locked reference，不得因消息所在 discussion branch 可读而展开。

## 8. 编辑、撤回、Reaction

### 8.1 编辑

编辑通过 `cx.message.revise` 形成 revision chain。

原则：

- 不静默改写原始历史。
- 默认视图显示最新 revision。
- 审计视图可看到 revision 链。

### 8.2 撤回

撤回通过 `cx.message.redact` 实现。

原则：

- 默认视图显示 tombstone。
- 被撤回消息不应继续在普通视图泄露正文。
- 协议不承诺全网物理擦除。

### 8.3 Reaction

reaction 建议通过独立 Operation 表达：

- `cx.reaction.add`
- `cx.reaction.remove`

归约策略：

- 以 `(message_id, actor, reaction_key)` 为 OR-Set key。
- 如果 reaction 到达时目标 Message 已经 redacted，reducer 仍 MAY 保留 reaction event 的最小审计事实，但默认 timeline / message view MUST NOT 展示、计数或通知该 reaction，除非 Space policy 明确允许对 tombstone 显示 reaction metadata。
- 如果 reaction 先到达、redaction 后到达，redaction 生效后默认视图 MUST 重新裁剪既有 reaction projection。审计 View MAY 显示 reaction 曾存在，但不得恢复已撤回正文。

## 9. 同步模型

### 9.1 Discussion 模式

推荐同步：

- flow metadata
- discussion membership summary
- 最近 N 条消息
- live message/reaction/redaction 增量
- read marker / notification 派生状态

### 9.2 Card 上下文模式

推荐同步：

- Flow 当前态
- Flow `synthesis` branch 字段
- discussion branch 启用状态与可见性裁剪后的 preview
- primary branch 最近摘要
- 与 Flow 相关的 relation / message reference / decision summary

Flow context sync 不得因为用户能读 Flow synthesis 就自动拉取不可见 discussion 消息。

## 10. 冲突与收敛

### 10.1 Message 创建

message 创建是 append-only。

时间线排序建议按：

1. 因果前序
2. `hlc`
3. `actor_id`
4. `actor_seq`
5. `event_id`

### 10.2 Message 编辑

并发 revision 并存于 revision chain 中。默认视图显示最新可见 revision。

### 10.3 Message 撤回

若 revision 和 redaction 并发：

- 默认视图 redaction 优先。
- 审计视图仍可保留完整历史。

### 10.4 先收到撤回，后收到原消息

接收方 SHOULD 保留 dangling redaction。待原消息到达后再应用它。

## 11. 临时信号与 Ephemeral State

以下高频变动的交互状态 MUST NOT 作为持久化 Durable Shared Object 写入密码学 Event 链：

- typing
- 当前输入草稿
- 临时在线状态
- 高频 read marker

它们 SHOULD 作为 Sync Service 上的 ephemeral signal，或由各端本地缓存。

## 12. 历史可见性

当新成员加入一个 Flow 的 `discussion` branch 时，他能看到多少历史消息是核心隐私边界。

| 策略值 | 含义 |
| --- | --- |
| `world_readable` | 任何人可见全部历史，包括非成员。 |
| `shared` | 当前成员可见加入前的全部历史。 |
| `joined` | 仅可见该成员正式加入之后的消息。 |
| `invited` | 从被邀请时刻起可见。 |
| `restricted` | 由 Flow/Space policy 与 capability 决定。 |

私密 discussion branch 或 E2EE discussion branch SHOULD 默认为 `joined`。

E2EE discussion branch 中，`history_visibility=joined` 时新成员 MUST NOT 收到加入前的 MLS epoch key。若允许加入前历史共享，必须通过 history sharing policy 显式声明并产生审计事件。普通客户端不得为了潜在历史共享而无限期保留旧 epoch 明文 secret；需要长期保留时必须使用显式 Archive / Audit Node、受保护 key backup 或 legal-hold 边界。

## 13. 设计决定

Contrix v1 固定：

- `flow` 是统一标准对象；`room` / `card` 是 `kind`，不是独立主实体。
- `discussion` branch 是会话能力，不是单独对象。
- `synthesis` branch 承载整理后的正式表达与推进字段。
- `message` 永远属于 Flow `discussion` branch。
- `kind="card"` 可以开启 `discussion` branch。
- `cx.flow.convert` 只切换模式，不改变 identity。
- 编辑采用 revision chain。
- 撤回采用 redaction/tombstone。
- reaction 用 OR-Set 收敛。
- Flow / Message / Board / Morph 共享同一 sync/reducer 基础，但对象语义不同。

## 14. 规范性引用

- `object-model-core.md`
- `data-structures.md`
- `views.md`
- `space-hierarchy.md`
