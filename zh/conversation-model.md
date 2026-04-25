# Conversation Model Draft

## 1. 目标

Contrix New 虽然不是 chat-first 协议，但必须正式支持：

- 频道式聊天
- 话题式讨论
- thread/reply
- `@mention`
- 编辑
- 撤回
- reaction

并且这些能力要能和 board、item、run、memory 打通，而不是另起一套孤立系统。

## 2. 设计原则

### 2.1 会话是对象图的一部分

会话不是一个独立宇宙。  
会话对象必须能链接到：

- workspace
- board
- item
- run
- memory

### 2.2 会话不应重新成为协议根

Contrix 不回到 room/message-first 模型。

正确做法是：

- 把会话作为正式对象层
- 但仍让 workspace/object graph/repo ops 保持为协议根

### 2.3 durable note 与 timeline message 分开

`comment` 和 `message` 都存在，但语义不同：

- `comment`：对象上的 durable note / review / approval note
- `message`：频道或话题中的 timeline 消息

## 3. 会话对象集合

当前草案建议引入：

- `channel`
- `topic`
- `message`

并定义 `reaction` 为 message 上的标准派生状态。

## 4. Channel

Channel 是长期会话空间。

适合：

- 团队聊天
- board 讨论区
- 组织公告流
- agent 运行播报流

建议字段：

```json
{
  "id": "cx:channel:01JS1000000000000000000000",
  "kind": "channel",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "release-chat",
  "description": "General release coordination chat",
  "channel_kind": "chat",
  "visibility": "workspace",
  "default_topic_mode": "inline",
  "archived": false
}
```

`channel_kind` 初版建议支持：

- `chat`
- `announce`
- `support`
- `activity`

## 5. Topic

Topic 是会话线程或主题对象。

它可以：

- 隶属于某个 channel
- 或直接锚定到某个 object

建议字段：

```json
{
  "id": "cx:topic:01JS1000000000000000000001",
  "kind": "topic",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "anchor_ref": "cx:item:01JS0IT000000000000000000",
  "topic_kind": "thread",
  "title": "Legal review follow-up",
  "status": "open",
  "created_by": "did:web:alice.example.com"
}
```

`anchor_ref` 可以指向：

- `workspace`
- `board`
- `item`
- `run`
- `memory`

这意味着：

- 一个 item 可以有一个默认 topic
- 一个 run 也可以有自己的执行话题

## 6. Message

Message 是时间线中的原子消息对象。

建议字段：

```json
{
  "id": "cx:message:01JS1000000000000000000002",
  "kind": "message",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "topic_id": "cx:topic:01JS1000000000000000000001",
  "sender": "did:web:alice.example.com",
  "reply_to_ref": null,
  "body": {
    "format": "markdown",
    "text": "@bob 请确认这个 item 的 legal 风险。"
  },
  "mentions": [
    {
      "kind": "principal",
      "ref": "did:web:bob.example.com"
    },
    {
      "kind": "object",
      "ref": "cx:item:01JS0IT000000000000000000"
    }
  ],
  "revision_root": "cx:message:01JS1000000000000000000002",
  "visible_state": "active"
}
```

## 7. `@mention` 设计

### 7.1 UI 与协议层分离

UI 可以允许用户输入：

- `@alice.example.com`
- `@bob`
- `@某个 item 标题`

但协议层不能只存裸文本。

### 7.2 Canonical 存储

协议层 SHOULD 存：

- `mentions[].kind = principal | object`
- `mentions[].ref = DID | stable object ID`

这样可以保证：

- Handle 迁移不破坏历史 mention
- object 改名不破坏历史 mention

### 7.3 Mention 通知

mention 通知应是派生结果，而不是 message 真相的一部分。

也就是说：

- message 保存 mention 引用
- inbox/notification 由 index 或 relay 派生

## 8. 编辑、撤回、Reaction

### 8.1 编辑

编辑通过 `message.revise` 形成 revision chain。

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

- `message.react`
- `message.unreact`

归约策略：

- 以 `(message_id, actor, reaction_key)` 为 OR-Set key

## 9. 评论与消息的区别

为避免协议语义混乱，Contrix 应明确：

- `comment` 更适合对象审阅、审批说明、审计性注释
- `message` 更适合连续聊天、thread 对话、频道时间线

如果一个 item 既要有审阅说明，又要有轻量对话：

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

- board/item 当前态
- 当前打开 item 的默认 topic 摘要
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

## 12. 私有与临时信号

以下状态不建议作为 durable shared object：

- typing
- 当前输入草稿
- 临时 presence

它们可以：

- 作为 relay 上的 ephemeral signal
- 或作为 actor-private state

## 13. 初版设计决定

当前草案建议固定：

- `channel/topic/message` 为正式会话对象
- `@mention` 使用结构化 DID/object ref
- 编辑采用 revision chain
- 撤回采用 redaction/tombstone
- reaction 用 OR-Set 收敛
- board/chat/topic 共享同一同步协议，只是 profile 不同

## 14. 后续待细化

下一轮仍需补充：

- 富文本 block 结构
- 附件在 message 中的嵌入语义
- 频道成员可见性与历史权限
- inbox / notification 的正式 schema
