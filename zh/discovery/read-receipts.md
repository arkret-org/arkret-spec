# Read Receipts & Markers

## 1. 目标

在即时通讯与协作中，“已读”状态是消除信息不对称的关键。Contrix 协议将“已读”分为两种机制：

1. **Read Receipt (已读回执)**：公开的或共享的，让**其他人**知道你已经读到哪条消息。
2. **Read Marker (已读游标)**：私有的，让你自己的**多端设备**同步你的阅读进度。

本规范定义了这两种机制的触发与同步方式。

## 2. Read Receipt (已读回执)

已读回执是向同一个 Room 的其他成员广播“我已经看到这条消息了”。

### 2.1 临时性与高频特征

与具体的业务数据不同，已读回执变动极其频繁（用户每次滑动屏幕都会产生），并且其历史记录没有长期保留价值。
因此，Read Receipt MUST 仅作为 **Ephemeral Event** 通过 Sync Service 的 Ephemeral Channel 广播，不写入持久化 Event 因果图中。

### 2.2 广播格式

客户端在用户视线停留或明确确认后，向 Sync Service 发送：

```json
{
  "type": "cx.receipt.read",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "room_id": "cx:room:01JS1000000000000000000001",
  "actor": "did:web:alice.example.com",
  "event_id": "cx:event:01JS1READ00000000000000000",
  "timestamp": "2026-04-26T10:00:00Z"
}
```

| 字段 | 说明 |
|------|------|
| `event_id` | 用户已读的最新那条 Operation 的 ID。由于因果性，表示该 Operation 及其因果前驱均已读。 |

### 2.3 隐私控制

用户可以随时关闭发送已读回执。此配置属于 Client Preference。
客户端收到他人的 `cx.receipt.read` 时，SHOULD 在 UI 上更新已读头像的小图标位置。

## 3. Read Marker (私有游标)

Read Marker 用于多设备同步（例如你在手机上看了消息，电脑端不应再显示未读红点）。这是纯纯的**私有状态**。

### 3.1 存储位置

Read Marker 作为一种持久化的个人状态，MUST 作为加密 account data 或 actor-private Event 保存，而不是提交到发生协作的共享 Space Event history。

### 3.2 格式

```json
{
  "type": "cx.marker.read",
  "body": {
    "space_id": "cx:space:01JS0SP000000000000000000",
    "room_id": "cx:room:01JS1000000000000000000001",
    "event_id": "cx:event:01JS1READ00000000000000000"
  }
}
```

- 该状态被加密存储在用户的 account data 中。
- 用户的其他设备通过同步 account data 的变更，获取最新的游标位置，从而清除本地未读红点。

## 4. 未读计数 (Unread Notification Count)

未读计数是由 **Index 节点** 维护的派生数据。

1. Index 节点监听用户的 account data 拿到最新的 `cx.marker.read`。
2. Index 节点计算 `cx.marker.read` 指向的 `event_id` 之后，该 Room 内产生了多少条新的、应该触发提醒的 Message 或对象事件。
3. 客户端通过 `GET /api/v1/index/notifications` 接口直接获取算好的未读数。

## 5. Thread (子线程) 的已读隔离

在 Thread 模式下，Room timeline 和子 Thread 的阅读进度是分离的。
如果 `cx.receipt.read` 或 `cx.marker.read` 的目标 `event_id` 是一个 Thread 内的回复，它只更新该 Thread 的已读游标，**不**更新父 Room timeline 的游标，反之亦然。
