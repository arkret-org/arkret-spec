# Conversation Model

## 1. 目标

Contrix 虽然不是 chat-first 协议，但必须正式支持：

- Room
- Message timeline
- thread / reply
- `@mention`
- 编辑
- 撤回
- reaction
- Subject 关联讨论
- Card 关联讨论

会话能力必须能和 Subject、Board、Card、Run、Memory、Morph 等对象打通，但 Room / Message 不再伪装成 Entity。

## 2. 设计原则

### 2.1 Room 是标准对象

Room 是 Space 内的讨论容器。它拥有自己的：

- membership / access policy
- history visibility
- notification policy
- optional E2EE group
- message timeline

Room 不是服务器，也不是 Space。Room 的所有写入仍然受 Space policy、capability、DID signature 和 reducer 约束。

### 2.2 Card 和 Room 严格区分

Card 是工作对象。Room 是讨论容器。

新模型中，Subject 是语义中心，Room 和 Card 都可以作为 Subject 的 surface。Card 仍可以关联 0..N 个 Room，但该关联主要用于兼容、快捷入口或局部上下文；关联关系不传递权限：

- Subject 可见不表示 Room 可见。
- Card 可见不表示 Room 可见。
- Room 可见不表示 Card 可见。
- Room membership 变化不自动改变 Subject 权限。
- Subject surface 变化不自动改变 Room membership。
- Card 权限变化不自动改变 Room membership。
- Room membership 变化不自动改变 Card 权限。
- Card 归档、删除或移动时不自动删除 Room。

这避免了 bound room 的复杂度，也允许一个 Card 同时关联产品、工程、安全、外部供应商或私密决策等多个 Room。

### 2.3 Message 是 Room 时间线单元

Message 是 Room 中的 append-only 消息对象。编辑不重写原消息；撤回使用 redaction/tombstone。

### 2.4 durable note 与 timeline message 分开

`comment` 和 `message` 都可以存在，但语义不同：

- `comment`：对象上的 durable note / review / approval note，可作为 Card/Morph 字段或专用 profile。
- `message`：Room 时间线中的聊天或讨论消息。

## 3. Room

Room 适合：

- 团队聊天
- 项目讨论
- Board 讨论区
- Card 相关讨论
- 审阅/评审讨论
- 外部协作沟通
- agent 运行播报流

示例：

```json
{
  "id": "cx:room:01js1000000000000000000000",
  "type": "room",
  "schema": "cx.schema.room.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "title": "release-engineering",
  "summary": "Engineering coordination for release readiness.",
  "room_kind": "discussion",
  "history_visibility": "joined",
  "membership_policy_ref": "cx:policy:01js0rp0000000000000000000",
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

Message 是 Room 时间线中的原子消息对象。

示例：

```json
{
  "id": "cx:message:01js1000000000000000000002",
  "type": "message",
  "schema": "cx.schema.message.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "room_id": "cx:room:01js1000000000000000000000",
  "created_by": "did:web:alice.example.com",
  "content": {
    "format": "markdown",
    "text": "@bob 请确认这个 card 的 legal 风险。"
  },
  "fields": {
    "revision_root": "cx:message:01js1000000000000000000002",
    "visible_state": "active"
  }
}
```

message 与 room/reply/mention 的关系使用 Relation 或 message 字段表达：

- `room --contains--> message`
- `message --replies_to--> message`
- `message --mentions--> actor / card / morph / room`
- `message --references--> card / board / morph / blob`

## 5. Subject、Card 与 Room 关联

推荐模型：

```json
{
  "type": "relation",
  "relation_kind": "has_surface",
  "from_ref": "cx:subject:01js0sb0000000000000000000",
  "to_ref": "cx:room:01js0rm0000000000000000000",
  "fields": {
    "surface_role": "primary_discussion",
    "primary": true
  }
}
```

Subject 也可以关联 Card surface：

```json
{
  "type": "relation",
  "relation_kind": "has_surface",
  "from_ref": "cx:subject:01js0sb0000000000000000000",
  "to_ref": "cx:card:01js0cd0000000000000000000",
  "fields": {
    "surface_role": "status_card",
    "primary": true
  }
}
```

`has_surface` 只表达语义聚合，不授予读取、写入或管理权限。客户端展示 Subject 时，必须按当前 actor 对每个 surface 的可见性裁剪 Room timeline、Message preview、Card 状态和附件摘要。

兼容模型：

Card 关联 Room 使用 Relation：

```json
{
  "type": "relation",
  "relation_kind": "links_room",
  "from_ref": "cx:card:01js0cd0000000000000000000",
  "to_ref": "cx:room:01js0rm0000000000000000000",
  "fields": {
    "purpose": "implementation_discussion",
    "primary": false
  }
}
```

一个 Card MAY 有一个 `primary_room`：

```json
{
  "type": "relation",
  "relation_kind": "primary_room",
  "from_ref": "cx:card:01js0cd0000000000000000000",
  "to_ref": "cx:room:01js0rm0000000000000000000"
}
```

`primary_room` 只表示 UI 默认讨论入口，不授予读取、写入或管理权限。

推荐 `purpose`：

- `general`
- `design`
- `implementation`
- `review`
- `incident`
- `external_partner`
- `private`
- `archive`

## 6. Room Membership

Room membership 是 Space 内的子范围授权。它不替代 Space membership，也不扩展 Card 权限。

推荐状态事件：

```json
{
  "kind": "cx.room.member",
  "state_key": "cx:room:01js0rm0000000000000000000|did:web:bob.example",
  "content": {
    "room_id": "cx:room:01js0rm0000000000000000000",
    "member": "did:web:bob.example",
    "membership": "join",
    "reason": "invited"
  }
}
```

规则：

- Room participant MUST satisfy Space policy。高安全 Space MAY 要求所有 Room 成员也是 Space member。
- Space policy MAY allow room-scoped external admission，但该 admission 不授予其他 Subject、Room、Board、Card 或 Space directory 可见性。
- Room membership 只控制该 Room 的消息读取、发送、历史和通知。
- Room membership 不改变 Card assignment、Card visibility、Board position 或 Space membership。

## 7. `@mention` 与引用

为避免正文与引用关系脑裂，消息正文 SHOULD 使用结构化 AST 或带 DID/object ref 的 Markdown 链接。

客户端提交或编辑消息时 MAY 不提交独立 `mentions` Relation。客户端 reducer 可以从 Message content AST 派生 mention 关系和通知，但派生关系不得扩大权限。

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

### 9.1 Room 模式

推荐同步：

- room metadata
- room membership summary
- 最近 N 条消息
- live message/reaction/redaction 增量
- read marker / notification 派生状态

### 9.2 Card 上下文模式

推荐同步：

- card 当前态
- linked room 列表及可见性裁剪后的 preview
- primary room 最近摘要
- 与 card 相关的 relation / message reference / decision summary

Subject/Card context sync 不得因为用户能读 Subject 或 Card 就自动拉取不可见 Room 消息。

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

当新成员加入一个 Room 或 Space 时，他能看到多少历史消息是核心隐私边界。

| 策略值 | 含义 |
| --- | --- |
| `world_readable` | 任何人可见全部历史，包括非成员。 |
| `shared` | 当前成员可见加入前的全部历史。 |
| `joined` | 仅可见该成员正式加入之后的消息。 |
| `invited` | 从被邀请时刻起可见。 |
| `restricted` | 由 Room/Space policy 与 capability 决定。 |

私密 Room 或 E2EE Room SHOULD 默认为 `joined`。

E2EE Room 中，`history_visibility=joined` 时新成员 MUST NOT 收到加入前的 MLS epoch key。若允许加入前历史共享，必须通过 history sharing policy 显式声明并产生审计事件。普通客户端不得为了潜在历史共享而无限期保留旧 epoch 明文 secret；需要长期保留时必须使用显式 Archive / Audit Node、受保护 key backup 或 legal-hold 边界。

## 13. 设计决定

Contrix v1 固定：

- Room / Message 是标准对象，不再是 Entity 语义标签。
- Subject 是语义中心；Room 和 Card 可以作为 Subject surface。
- Card 可关联 0..N 个 Room。
- Card 和 Room 权限完全独立；关联 relation 不传递权限。
- `primary_room` 只是 UI 默认入口。
- 编辑采用 revision chain。
- 撤回采用 redaction/tombstone。
- reaction 用 OR-Set 收敛。
- Subject/Board/Card/Room 共享同一 sync/reducer 基础，但对象语义不同。

## 14. 规范性引用

- 富文本 block 结构见 `content-types.md`。消息正文必须使用注册 content block 或按未知 block 降级规则保留。
- 附件在 message 中的嵌入语义见 `content-types.md` 与 `../crypto-media/media-and-blob.md`；附件安全边界由 blob auth、hash 校验、MIME 清理和 E2EE envelope 共同决定。
- Inbox / notification schema 见 `../discovery/read-notification-schema.md`、`../discovery/push-notifications.md` 和 `../models/data-structures.md`。Notification 是派生投影，不得作为 canonical truth。
