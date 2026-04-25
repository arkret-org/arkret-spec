# Operations And Sync Draft

## 1. 目标

Contrix New 是面向协作对象的分布式发布、传播、查询与收敛协议。

同步层必须同时支持：

- actor 侧可验证发布
- append-only 审计日志
- 当前态快速恢复
- 看板模式同步
- 聊天/话题模式同步
- 离线写入
- 最终一致收敛

## 2. 核心角色

初版建议区分：

- `client`
- `agent`
- `repo`
- `relay`
- `index`
- `blob store`

### 2.1 Repo

Repo 是某个 principal 的发布源。

### 2.2 Relay

Relay 是 workspace 传播层。

### 2.3 Index

Index 是物化与查询层。

### 2.4 Blob Store

Blob Store 负责附件与大对象内容。

## 3. Repo-first 发布模型

Contrix New 采用 repo-first 模型：

1. actor 先写自己的 repo
2. repo 发布 commit
3. relay 聚合 workspace 相关授权 op
4. index 归约为当前态

这套模型同时适用于：

- board/item 更新
- topic/message 流
- run/memory 沉淀

## 4. Repo Commit

初版建议 repo 以 commit 为发布单元。

```json
{
  "commit_id": "cx:commit:01JS0CMT000000000000000000",
  "repo_did": "did:web:alice.example.com",
  "prev_commit": "cx:commit:01JS0CMP000000000000000000",
  "seq": 144,
  "created_at": "2026-04-22T08:30:00Z",
  "ops": [
    "cx:op:01JS0OP000000000000000000",
    "cx:op:01JS0OQ000000000000000000"
  ],
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 5. Operation Envelope

每个 op MUST 具备统一 envelope。

```json
{
  "op_id": "cx:op:01JS0OP000000000000000000",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "actor": "did:web:alice.example.com",
  "type": "cx.item.update",
  "target_ref": "cx:item:01JS0IT000000000000000000",
  "causal": {
    "deps": [
      "cx:op:01JS0OO000000000000000000"
    ],
    "hlc": "2026-04-22T08:31:03.221Z-0007-did:web:alice.example.com",
    "actor_seq": 42
  },
  "body": {},
  "authz_ref": "cx:grant:01JS0GR000000000000000000",
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 6. 为什么需要 `deps + hlc + actor_seq`

单一时间戳不足以支撑协作收敛。

初版建议：

- `deps` 表示直接因果依赖
- `hlc` 表示近实时逻辑时间
- `actor_seq` 表示 actor 本地单调序列

## 7. 操作类型

### 7.1 Workspace / Board / Collection / View

- `cx.workspace.create`
- `cx.workspace.update`
- `cx.board.create`
- `cx.board.update`
- `cx.collection.create`
- `cx.collection.update`
- `cx.collection.move`
- `cx.view.create`
- `cx.view.update`

### 7.2 Item / Comment / Relation / Attachment

- `cx.item.create`
- `cx.item.update`
- `cx.item.move`
- `cx.item.reorder`
- `cx.comment.create`
- `cx.comment.update`
- `cx.comment.redact`
- `cx.relation.create`
- `cx.relation.delete`
- `cx.attachment.add`
- `cx.attachment.remove`

### 7.3 Channel / Topic / Message

- `cx.channel.create`
- `cx.channel.update`
- `cx.channel.archive`
- `cx.topic.create`
- `cx.topic.update`
- `cx.topic.close`
- `cx.topic.reopen`
- `cx.message.create`
- `cx.message.revise`
- `cx.message.redact`
- `cx.message.react`
- `cx.message.unreact`

### 7.4 Run / Memory

- `cx.run.create`
- `cx.run.update`
- `cx.run.complete`
- `cx.run.fail`
- `cx.memory.create`
- `cx.memory.update`
- `cx.memory.confirm`
- `cx.memory.invalidate`
- `cx.memory.supersede`

### 7.5 Capability

- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.revoke`

### 7.6 私有与临时状态

以下状态不建议作为 durable shared op：

- typing
- live presence
- 本地草稿

它们 MAY 通过 relay ephemeral channel 或 actor-private state 同步。

## 8. 操作体原则

非 create 类操作 SHOULD 只携带 delta，而不是完整对象快照。

例如：

- `cx.item.update` 只带字段变更
- `cx.item.move` 只带目标容器和新 rank
- `cx.message.revise` 只带新正文
- `cx.message.redact` 只带目标消息与原因

## 9. 验证流程

任何接收 op 的 repo、relay 或 index，至少应校验：

1. 签名有效
2. actor DID 可解析
3. key 在操作时点有效
4. workspace_id 与 target workspace 一致
5. capability 在操作时点有效
6. causal 依赖不违反基本约束

## 10. Snapshot

Snapshot 是加速层，不是真相源。

```json
{
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "snapshot_id": "cx:snap:01JS0SN000000000000000000",
  "covers_frontier": [
    "cx:op:01JS0OP000000000000000000",
    "cx:op:01JS0OQ000000000000000000"
  ],
  "generated_at": "2026-04-22T08:40:00Z",
  "generator": "did:web:index.example.com",
  "reducer_version": "0.1.0",
  "chunks": [
    {
      "kind": "items",
      "url": "https://index.example.com/cx/snapshots/01/items.json"
    },
    {
      "kind": "messages",
      "url": "https://index.example.com/cx/snapshots/01/messages.json"
    }
  ]
}
```

## 11. 同步面

### 11.1 Repo Sync

用于 actor 历史恢复与审计重放。

### 11.2 Workspace Sync

用于 workspace 级当前态与增量同步。

### 11.3 Firehose Subscription

用于实时事件传播。

### 11.4 Query Surface

用于 view、搜索、memory 检索与 thread 查询。

## 12. Board / Chat / Topic 同步 Profile

### 12.1 Board 模式

默认同步：

- board/item/collection 当前态
- 当前打开 item 的 comment 摘要
- 当前打开 item 的默认 topic 摘要

### 12.2 Chat 模式

默认同步：

- channel metadata
- open topics
- 最近 N 条 messages
- live message/reaction/redaction 增量

### 12.3 Topic 模式

默认同步：

- topic metadata
- anchor object
- 最近 N 条 messages
- 反向 backfill cursor

## 13. 首次加入工作区

推荐流程：

1. 获取 workspace metadata
2. 拉取最近 snapshot manifest
3. 下载 snapshot chunk
4. 从 snapshot frontier 之后拉取增量 op
5. 本地执行 reducer
6. 进入 cursor 增量订阅

## 14. 选择性同步

选择性同步是协议关键能力。

初版至少支持以下过滤维度：

- workspace
- board
- channel
- topic
- object kind
- target refs
- watched items
- watched runs
- changed since cursor

## 15. 冲突与收敛

### 15.1 不追求全局共识

Contrix 初版不引入全网共识链。

它要求：

- 对同一 workspace
- 在同一有效 op 集下
- 所有正确实现的 reducer

最终收敛到相同当前态。

### 15.2 基本排序规则

当两个 op 无显式因果先后关系时，按以下顺序比较：

1. `hlc`
2. `actor`
3. `actor_seq`
4. `op_id`

## 16. 字段级 merge 与对象级收敛

### 16.1 标量字段

例如：

- `title`
- `body`
- `status`
- `priority`

建议：

- LWW by causal order

### 16.2 集合字段

例如：

- `labels`
- `assignees`
- `watchers`

建议：

- OR-Set

### 16.3 排序字段

例如：

- `rank`
- `container_id`

应通过 move/reorder 语义处理。

### 16.4 Message

- `message.create` 是 append-only
- `message.revise` 形成 revision chain
- 默认视图显示最新可见 revision

### 16.5 Reaction

reaction 以 `(message_id, actor, reaction_key)` 为 OR-Set key 收敛。

## 17. 排序模型

拖拽排序建议采用：

- `container_id`
- `rank`

其中 `rank` 建议采用 fractional indexing string。

消息时间线显示顺序建议采用：

- `hlc + actor + actor_seq + op_id`

## 18. Tombstone、Redaction 与恢复

### 18.1 对象删除

对象删除 SHOULD 采用 tombstone。

### 18.2 消息撤回

消息撤回应采用 redaction，而不是物理消失。

语义要求：

- 默认视图显示“已撤回”
- 不应继续在普通视图泄露正文
- 不承诺全网物理擦除

### 18.3 先收到 redaction，后收到原消息

接收方 SHOULD 保留 dangling redaction，并在目标消息到达后应用。

## 19. Blob 同步

Blob 不应强制与元数据同流同步。

建议：

- 元数据先同步
- 内容按需加载
- 通过 hash 校验完整性

## 20. 本地存储建议

客户端 SHOULD 维护三层本地数据：

- raw commits / raw ops
- reduced snapshots
- materialized indexes

## 21. 初版设计决定

当前草案建议固定：

- repo commit 是 actor 发布单元
- op 是共享状态归约单元
- board/chat/topic 共享同一同步协议
- 撤回采用 redaction/tombstone 语义
- 冲突通过固定 reducer 规则收敛

## 22. 后续待细化

下一轮仍需补充：

- cursor 编码
- HLC 文本格式
- snapshot chunk schema
- read marker 的标准同步面
- relay / index 线级接口
