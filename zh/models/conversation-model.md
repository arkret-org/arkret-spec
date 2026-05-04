# Conversation Model

## 1. 目标

Contrix 的会话模型由 `flow` 承载统一 identity，并通过 `discussion` branch 承载会话能力。

## 2. 设计原则

- `flow` 是唯一主对象；resolved primary branch 只决定默认视角。
- `discussion` branch 是会话能力，不是独立对象。
- Branch access 默认继承 Flow / Space；只有显式 branch-scoped override 才引入独立 membership、history visibility 或 E2EE group。
- `message` 永远写入 `flow` 的 `discussion` branch。
- Flow MAY 只启用 `synthesis` branch，也 MAY 同时启用 `discussion` branch。
- `cx.flow.convert` 允许切换 primary branch 标记并确保目标 branch 存在，且不改变 Flow identity。

`comment`（对象评注）与 `message`（讨论消息）语义不同：

- `comment`：对象上的 durable note / review / approval note。不是独立 `type`，而是通过 Morph profile（如 `cx.morph.comment.v1`）或 `message` 子类型实现的**语义模式**。
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
  "title": "release-engineering",
  "description": "Engineering coordination for release readiness.",
  "brief": "默认以讨论为主入口。",
  "branches": [
    {
      "name": "synthesis"
    },
    {
      "name": "discussion",
      "is_primary": true,
      "profile": "discussion",
      "access": {
        "membership": "branch_scoped",
        "permissions": "branch_scoped",
        "history_visibility": "joined",
        "membership_policy_ref": "cx:policy:01js0rp0000000000000000000"
      }
    }
  ],
  "created_by": "did:web:alice.example"
}
```

`name="discussion"` 的 branch `profile` 初版建议支持：

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
    "type": "cx.content.text",
    "body": "@bob 请确认这个 flow 的 legal 风险。",
    "format": "markdown",
    "formatted_body": "<mention did=\"did:web:bob.example.com\">@bob</mention> 请确认这个 flow 的 legal 风险。"
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
- `message --references--> flow / space / morph / blob`

`cx.message.create` / `cx.message.revise` Event payload 中的消息正文 MUST 放在 `payload.content` 字段内，并使用 `content-types.md` 定义的 Content Block。`flow_id`、`message_id`、`reply_to` 等字段只作为路由、目标或关系 metadata，不能替代 `payload.content.type` / `payload.content.body`。

## 5. Flow 默认入口与转换

Flow 通过 resolved primary branch 表达默认交互入口：

- `{"name":"synthesis","is_primary":true}`：默认进入整理、推进和结构化字段编辑界面。
- `{"name":"discussion","is_primary":true}`：默认进入会话界面。

若没有任何 branch 显式设置 `is_primary=true`，且 `synthesis` 与 `discussion` 同时存在，默认入口 MUST 派生为 `synthesis`。只有一个 branch 时默认入口为该唯一 branch；多个非标准 branch 且无法按 profile 派生时必须 fail closed。

业务过滤、默认 View 和 agent policy SHOULD 使用 Space schema/profile、`fields`、Relation、labels 或 Morph profile。Flow 顶层不再定义业务分类字段。

Flow MAY 开启 `discussion` branch。开启后，该 Flow 仍然是同一个对象，只是多了讨论能力。

```json
{
  "kind": "cx.flow.branch.enable",
  "target_ref": "cx:flow:01js0cd0000000000000000000",
  "payload": {
    "flow_id": "cx:flow:01js0cd0000000000000000000",
    "branch": "discussion",
    "config": {
      "profile": "implementation",
      "access": {
        "membership": "branch_scoped",
        "permissions": "branch_scoped",
        "history_visibility": "joined"
      }
    }
  }
}
```

Flow 默认入口切换通过 `cx.flow.branch.set_primary` 或 `cx.flow.convert` 完成：

```json
{
  "kind": "cx.flow.convert",
  "target_ref": "cx:flow:01js0cd0000000000000000000",
  "payload": {
    "flow_id": "cx:flow:01js0cd0000000000000000000",
    "branch": "discussion",
    "ensure_branches": [
      "discussion"
    ]
  }
}
```

转换规则：

- 转换不改变 `flow_id`。
- 转换不复制或迁移消息历史。
- 切换到 `branch="discussion"` 时，若 `discussion` branch 尚不存在，Reducer MUST 自动创建它，或在 policy 禁止时 fail closed。
- 已启用的 `discussion` branch 在转换后继续保留。
- Flow 的 Space (kind=board)/Space (kind=list) 位置、字段和讨论历史由对应 reducer 维护；讨论历史只有在 branch-scoped override 明确声明时，才使用独立 membership / history / E2EE 边界。

## 6. Discussion Branch Membership

Discussion branch membership 是 branch `access` 的显式 override 形态。默认情况下，discussion 继承 Flow / Space 的有效访问规则；只有 `branches[]` 中 `name="discussion"` 的 branch 声明 `access.membership="branch_scoped"` 或等价 policy state 生效时，`cx.flow.branch.member` 才成为该 discussion 的局部参与状态。它不替代 Space membership，也不扩展 Flow `synthesis` branch 的编辑权限。

推荐状态事件：

```json
{
  "kind": "cx.flow.branch.member",
  "state_key": "cx:flow:01js0rm0000000000000000000|discussion|did:web:bob.example",
  "payload": {
    "flow_id": "cx:flow:01js0rm0000000000000000000",
    "branch": "discussion",
    "member": "did:web:bob.example",
    "membership": "join",
    "reason": "invited"
  }
}
```

规则：

- Branch-scoped discussion participant MUST satisfy Space policy。高安全 Space MAY 要求所有 discussion 成员也是 Space member。
- Space policy MAY allow flow-scoped external admission，但该 admission 不授予其他 Flow、Board、Morph 或 Space directory 可见性。
- Branch-scoped discussion membership 只控制该 branch 的消息读取、发送、历史和通知。
- Discussion membership 不改变 Flow assignment、Flow visibility、Board position 或 Space membership。
- `assigned_to`、watchers 或其他 Flow relation 不自动成为 discussion member，除非有效 access policy 明确声明这种映射。

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

reaction 建议通过独立 Event 表达：

- `cx.reaction.add`
- `cx.reaction.remove`

归约策略：

- 以 `(message_id, actor, reaction_key)` 为 OR-Set key。
- 如果 reaction 到达时目标 Message 已经 redacted，reducer 仍 MAY 保留 reaction event 的最小审计事实，但默认 timeline / message view MUST NOT 展示、计数或通知该 reaction，除非 Space policy 明确允许对 tombstone 显示 reaction metadata。
- 如果 reaction 先到达、redaction 后到达，redaction 生效后默认视图 MUST 重新裁剪既有 reaction projection。审计 View MAY 显示 reaction 曾存在，但不得恢复已撤回正文。

> **Snapshot 持久化**：Reaction 状态 MUST 由 reducer 从 `cx.reaction.add` / `cx.reaction.remove` 事件归约得到。若实现使用 snapshot-only restore（不回放完整 event history），snapshot MUST 包含 reaction 的 materialized state（即当前有效的 `(message_id, actor, reaction_key)` 集合）。仅包含 event log 而不包含 reaction materialized state 的 snapshot 在恢复后 MUST 回放缺失的 reaction 事件以重建状态。实现不得假设 reaction 是 ephemeral 的而丢弃其状态。

## 9. 同步模型

### 9.1 Discussion 模式

推荐同步：

- flow metadata
- discussion membership summary
- 最近 N 条消息
- live message/reaction/redaction 增量
- read marker / notification 派生状态

### 9.2 Flow synthesis 上下文模式

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

`history_visibility` enum 与每个值的 **canonical 语义** 由 [`authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md) 唯一定义。任何与该文件描述不一致的解读以那里为准。本节仅复述要点供阅读：

- `world_readable`：任何 actor 可读取明文或已授权公开内容。
- `shared`：当前和历史成员可读取加入前历史。
- `invited`：被邀请 actor 可读取 stripped preview state（**不是**"从被邀请时刻起的全部消息"——前者是 preview，后者是普通成员可读范围）。
- `joined`：仅加入后历史默认可见。
- `restricted`：必须满足 Space policy 中 `allowed_selectors`、claim、capability 或等价 history access proof；无法验证时按 `joined` 或更严格规则 fail closed。

私密 discussion branch 或通过 access override 启用 E2EE 的 discussion branch SHOULD 默认为 `joined`。

Branch-scoped E2EE discussion 中，`history_visibility=joined` 时新成员 MUST NOT 收到加入前的 MLS epoch key。若允许加入前历史共享，必须通过 `cx.space.policy.set` (state_key=`history_sharing`) 显式声明并产生审计事件（详见 event-auth-state-resolution.md §6 history sharing policy）。普通客户端不得为了潜在历史共享而无限期保留先前 epoch 明文 secret；需要长期保留时必须使用显式 Archive / Audit Node、受保护 key backup 或 legal-hold 边界。

## 13. 设计决定

Contrix v1 固定：

- `flow` 是统一标准对象；默认入口由 branch primary 解析规则表达，不再有 Flow 模式字段。
- `discussion` branch 是会话能力，不是单独对象。
- `synthesis` branch 承载整理后的正式表达与推进字段。
- `message` 永远属于 Flow `discussion` branch。
- Flow 可以同时启用 `synthesis` 与 `discussion` branch。
- `cx.flow.convert` 只切换默认入口或确保 branch 存在，不改变 identity。
- 编辑采用 revision chain。
- 撤回采用 redaction/tombstone。
- reaction 用 OR-Set 收敛。
- Flow / Message / Board / Morph 共享同一 sync/reducer 基础，但对象语义不同。

## 14. 规范性引用

- `object-model-core.md`
- `data-structures.md`
- `views.md`
- `space-hierarchy.md`
