# Read Receipts & Markers

## 1. 目标

在即时通讯与协作中，“已读”状态是消除信息不对称的关键。Contrix 协议将“已读”分为两种机制：

1. **Read Receipt (已读回执)**：公开的或共享的，让**其他人**知道你已经读到哪条消息。
2. **Read Marker (已读游标)**：私有的，让你自己的**多端设备**同步你的阅读进度。

本规范定义了这两种机制的触发与同步方式。

## 2. Read Receipt (已读回执)

已读回执是向同一个 Flow `discussion` branch 的可见成员广播“我已经看到这条消息了”。

### 2.1 临时性与高频特征

与具体的业务数据不同，已读回执变动极其频繁（用户每次滑动屏幕都会产生），并且其历史记录没有长期保留价值。
因此，Read Receipt MUST 仅作为 **Ephemeral Event** 通过 Sync Service 的 Ephemeral Channel 广播，不写入持久化 Event 因果图中。

### 2.2 广播格式

客户端在用户视线停留或明确确认后，向 Sync Service 发送：

```json
{
  "kind": "cx.receipt.read",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "flow_id": "cx:flow:01js1000000000000000000001",
  "actor": "did:web:alice.example.com",
  "event_id": "cx:event:01js1read00000000000000000",
  "timestamp": "2026-04-26T10:00:00Z"
}
```

| 字段 | 说明 |
|------|------|
| `event_id` | 用户已读的最新那条 Event 的 ID。由于因果性，表示该 Event 及其因果前驱均已读。 |

### 2.3 防雪崩与合并

Read Receipt 是高频信号，发送方和 Sync Service 都 MUST 支持合并。客户端 SHOULD debounce 可见区域滚动产生的更新，并且对同一 `(space_id, flow_id, branch/thread, actor)` 在短窗口内只发送最新位置。默认建议窗口为 1 秒，交互结束、窗口失焦或显式“标为已读”时 SHOULD flush 最新位置。

Sync Service MAY 丢弃同一 scope 下较旧的 receipt，只向订阅方广播单调前进的最新位置；不得把每一次滚动增量都 fanout 成独立推送。公开或共享 receipt 的服务端限流维度至少应包含 actor、device、Space 和 Flow。超过频率时 SHOULD 返回或广播 `rate_limited` / `retry_after_ms` 语义，客户端 MUST 按退避合并后重试。

Push Gateway MUST NOT 因 read receipt 产生通知。它只能把 receipt / marker 作为 unread count、push suppression 和 badge recompute 的输入。

### 2.4 隐私控制

用户可以随时关闭发送已读回执。此配置属于 Client Preference。
客户端收到他人的 `cx.receipt.read` 时，SHOULD 在 UI 上更新已读头像的小图标位置。

## 3. Read Marker (私有游标)

Read Marker 用于多设备同步（例如你在手机上看了消息，电脑端不应再显示未读红点）。这是纯纯的**私有状态**。

### 3.1 存储位置

Read Marker 作为一种持久化的个人状态，MUST 作为加密 account data 或 actor-private Event 保存，而不是提交到发生协作的共享 Space Event history。

### 3.2 格式

```json
{
  "kind": "cx.read.marker",
  "body": {
    "space_id": "cx:space:01js0sp0000000000000000000",
    "flow_id": "cx:flow:01js1000000000000000000001",
    "event_id": "cx:event:01js1read00000000000000000"
  }
}
```

- 该状态被加密存储在用户的 account data 中。
- 用户的其他设备通过同步 account data 的变更，获取最新的游标位置，从而清除本地未读红点。

### 3.3 写入合并

Read Marker 是 actor-private 持久状态，但仍然是高频更新。客户端 MUST 按 scope 合并，只提交相对本地已知 marker 单调前进的位置；在同一 `(actor_id, device_id, space_id, scope)` 上的连续滚动 SHOULD 以最新位置覆盖待发送更新。默认建议将活跃阅读期间的持久写入 debounce 到 1 秒以上，或在离开 Flow、应用进入后台、手动标记已读时立即 flush。

服务端接收 actor-private `cx.read.marker` 时 SHOULD 按第 5 节合并，而不是保留不可见的全量游标历史。若实现需要审计，可保留最小 device、old/new position 和时间摘要；不得把共享 Space timeline 当作 read marker 的压缩日志。

## 4. 未读计数 (Unread Notification Count)

未读计数是客户端本地或受托 notification service 维护的派生数据。

1. 客户端同步用户的 account data 拿到最新的 `cx.read.marker`。
2. 客户端计算 `cx.read.marker` 指向的 `event_id` 之后，该 Flow discussion branch 内产生了多少条新的、应该触发提醒的 Message 或对象事件。
3. 若部署使用受托 notification service，该服务必须按调用者权限和 `plaintext_visible_services` 规则生成最小化结果。

Notification / unread count 是派生状态。服务 MAY 在一个 sync response 中合并多次 marker、receipt 和 notification rule 变化，只返回最终 count 与必要 frontier；客户端不得把中间 badge 抖动当作协议事件缺失。

## 5. Thread (子线程) 的已读隔离

在 Thread 模式下，Flow discussion timeline 和子 Thread 的阅读进度是分离的。
如果 `cx.receipt.read` 或 `cx.read.marker` 的目标 `event_id` 是一个 Thread 内的回复，它只更新该 Thread 的已读游标，**不**更新父 Flow discussion timeline 的游标，反之亦然。
