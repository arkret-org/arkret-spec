# Conversation Model Draft

## 1. 目标

Contrix 虽然不是 chat-first 协议，但必须正式支持：

- 频道式聊天
- 话题式讨论
- thread/reply
- `@mention`
- 编辑
- 撤回
- reaction

并且这些能力要能和 board、task、run、memory 等 Entity 打通，而不是另起一套孤立系统。

## 2. 设计原则

### 2.1 会话是对象图的一部分

会话不是一个独立宇宙。  
会话对象必须能链接到：

- space
- board Entity
- task Entity
- run Entity
- memory Entity

### 2.2 会话不应重新成为协议根

Contrix 不回到 room/message-first 模型。

正确做法是：

- 把会话作为标准 Entity 类型
- 但仍让 `Space + Actor + Entity + Relation + Event + View` 保持为协议根

### 2.3 durable note 与 timeline message 分开

`comment` 和 `message` 都存在，但语义不同：

- `comment`：对象上的 durable note / review / approval note
- `message`：频道或话题中的 timeline 消息

## 3. 会话对象集合

当前草案建议标准化以下 `entity_type`：

- `channel`
- `topic`
- `message`

并定义 `reaction` 为 message Entity 上的标准派生状态。

## 4. Channel

Channel 是长期会话空间，对应 `entity_type = "channel"`。

适合：

- 团队聊天
- board 讨论区
- 组织公告流
- agent 运行播报流

建议字段：

```json
{
  "id": "cx:channel:01JS1000000000000000000000",
  "type": "entity",
  "schema": "cx.schema.entity.v1",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "channel",
  "title": "release-chat",
  "content": {
    "format": "text",
    "text": "General release coordination chat"
  },
  "fields": {
    "channel_kind": "chat",
    "visibility": "space",
    "default_topic_mode": "inline",
    "archived": false
  }
}
```

`channel_kind` 初版建议支持：

- `chat`
- `announce`
- `support`
- `activity`

## 5. Topic

Topic 是会话线程或主题对象，对应 `entity_type = "topic"`。

它可以：

- 通过 `belongs_to` Relation 隶属于某个 channel
- 通过 `attached_to` Relation 直接锚定到某个 Entity

建议字段：

```json
{
  "id": "cx:topic:01JS1000000000000000000001",
  "type": "entity",
  "schema": "cx.schema.entity.v1",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "topic",
  "title": "Legal review follow-up",
  "fields": {
    "topic_kind": "thread",
    "status": "open"
  },
  "created_by": "did:web:alice.example.com"
}
```

topic 与 channel、anchor object 的关系使用 Relation 表达：

- `topic --belongs_to--> channel`
- `topic --attached_to--> board/task/run/memory/document`

这意味着：

- 一个 task Entity 可以有一个默认 topic
- 一个 run Entity 也可以有自己的执行话题

## 6. Message

Message 是时间线中的原子消息对象，对应 `entity_type = "message"`。

建议字段：

```json
{
  "id": "cx:message:01JS1000000000000000000002",
  "type": "entity",
  "schema": "cx.schema.entity.v1",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "message",
  "created_by": "did:web:alice.example.com",
  "content": {
    "format": "markdown",
    "text": "@bob 请确认这个 item 的 legal 风险。"
  },
  "fields": {
    "revision_root": "cx:message:01JS1000000000000000000002",
    "visible_state": "active"
  }
}
```

message 与 topic/channel/reply/mention 的关系使用 Relation 表达：

- `message --belongs_to--> topic`
- `message --belongs_to--> channel`
- `message --replies_to--> message`
- `message --mentions--> actor_profile/task/document`

## 7. `@mention` 与引用的派生设计

### 7.1 避免正文与引用的“脑裂 (Split-Brain)”

如果协议强制要求客户端在正文保留 `@alice` 文本的同时，还必须手动发送一个对应的 `relation.create (mentions)` Op，这极易导致状态分裂。若用户反复编辑 (Revise) 文本修改 Mention 对象，客户端的 Bug 或网络丢包会使得文本内容和底层的 `mentions` Relation 产生严重的不一致。

### 7.2 基于 AST 的隐式派生原则

为解决此问题，协议要求：
- `message` 的 `content` 字段 MUST 使用结构化的 AST (如 Prosemirror JSON) 或是带有明确特殊标记的 Markdown (如 `[Alice](did:uuid:...)`)。
- 客户端在提交或编辑消息时，**不需要也不应该**手动提交额外的 `mentions` Relation Op。
- **派生真相 (Derived Truth)**：当 Index 节点或 Reducer 解析这条 Message 时，它通过解析内容 AST 中的 DID 节点，**自动在内存和索引层面派生出**对于目标主体的 Mention 关系和 Inbox 通知。

这种“单一数据源 (Single Source of Truth)”确保了即使发生任何编辑，通知状态都能和正文保持 100% 的绝对一致。

## 8. 编辑、撤回、Reaction

### 8.1 编辑

编辑通过 `cx.message.revise` 形成 revision chain。

原则：

- 不静默改写原始历史
- 默认视图显示最新 revision
- 审计视图可看到 revision 链

### 8.2 撤回

撤回通过 `message.redact` 实现。

原则：

- 默认视图显示 tombstone
- 被撤回消息不应继续在普通视图泄露正文
- 协议不承诺全网物理擦除

### 8.3 Reaction

reaction 建议通过独立 op 表达：

- `cx.reaction.add`
- `cx.reaction.remove`

归约策略：

- 以 `(message_id, actor, reaction_key)` 为 OR-Set key

## 9. 评论与消息的区别

为避免协议语义混乱，Contrix 应明确：

- `comment` 更适合对象审阅、审批说明、审计性注释
- `message` 更适合连续聊天、thread 对话、频道时间线

如果一个 task Entity 既要有审阅说明，又要有轻量对话：

- 审阅意见写 `comment`
- 即时讨论写 `topic/message`

## 10. 同步模型

### 10.1 Chat 模式

推荐同步：

- channel metadata
- open topics
- 最近 N 条消息
- live message/reaction/redaction 增量

### 10.2 Topic 模式

推荐同步：

- topic metadata
- anchor object
- 最近 N 条 message
- 反向 backfill cursor

### 10.3 Board 模式

推荐同步：

- board/task 当前态
- 当前打开 task 的默认 topic 摘要
- 最近评论和最近消息摘要

## 11. 冲突与收敛

### 11.1 Message 创建

message 创建是 append-only。

时间线排序建议按：

1. `hlc`
2. `actor`
3. `actor_seq`
4. `op_id`

### 11.2 Message 编辑

并发 revision 并存于 revision chain 中。  
默认视图显示最新可见 revision。

### 11.3 Message 撤回

若 revision 和 redaction 并发：

- 默认视图 redaction 优先
- 审计视图仍可保留完整历史

### 11.4 先收到撤回，后收到原消息

接收方 SHOULD 保留 dangling redaction。  
待原消息到达后再应用它。

## 12. 临时信号与 Ephemeral State

以下高频变动的交互状态会引发极其严重的写放大，MUST NOT 作为持久化的 Durable Shared Object 写入密码学 Repo 链中：

- `read_marker` (已读回执)
- `typing` (正在输入状态)
- 当前输入草稿
- 临时在线状态 (Presence)

它们 SHOULD：
- 作为 Relay 上的 Ephemeral Signal（通过旁路 WebSocket 短时广播）。
- 由各端本地在内存或缓存中记录，不强求全局长久一致性。

## 13. 初版设计决定

当前草案建议固定：

- `channel/topic/message` 为标准 Entity 类型，不是协议根
- `@mention` 使用结构化 DID/entity ref，并落成 Relation
- 编辑采用 revision chain
- 撤回采用 redaction/tombstone
- reaction 用 OR-Set 收敛
- board/chat/topic/tree/graph 共享同一同步协议，只是 profile 和 View 不同

## 14. 历史可见性 (History Visibility)

当新成员加入一个 Channel 或 Space 时，他能看到多少历史消息是一个核心隐私边界。协议通过 `history_visibility` 策略字段控制此行为。

### 14.1 策略值

| 策略值 | 含义 |
|--------|------|
| `world_readable` | 任何人可见全部历史，包括非 Space 成员 |
| `shared` | 当前成员可见加入前的全部历史 |
| `joined` | 仅可见该成员正式加入 (join) 时间点之后的消息 |
| `invited` | 从被邀请 (invite) 时刻起可见 |

### 14.2 默认值
- Channel 默认为 `shared`。
- 私密 Channel 或涉及 E2EE 的 Space 建议默认为 `joined`。

### 14.3 与 E2EE 的交互
- 当 `history_visibility` 为 `joined` 时，新成员 MUST NOT 收到加入前的 MLS Epoch 密钥。因此即使 Relay 转发了历史密文，新成员也在密码学层面无法解密。
- 当 `history_visibility` 为 `shared` 时，邀请者的客户端 MAY 通过 MLS 的 `Welcome` 消息中附带历史 Epoch 密钥，使新成员能够回溯解密加入前的内容。

### 14.4 变更规则
- `history_visibility` 的变更本身是一个 `cx.policy.set` 操作，需要 `space.admin` 权限。
- 变更仅影响变更后的新消息对新加入者的可见性，不追溯改变已有成员的可见范围。

## 15. 后续待细化

下一轮仍需补充：

- 富文本 block 结构
- 附件在 message 中的嵌入语义
- inbox / notification 的正式 schema
