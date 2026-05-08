---
title: "Read Receipts & Markers"
---

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

客户端在用户视线停留或明确确认后，以 ephemeral receipt 形式（schema：`cx.schema.read_receipt.v1`）向 Sync Service 发送：

```json
{
  "receipt_type": "read",
  "schema": "cx.schema.read_receipt.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "flow_id": "cx:flow:01js1000000000000000000001",
  "branch": "discussion",
  "actor_id": "did:web:alice.example",
  "event_id": "cx:event:01js1read00000000000000000",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "created_at": "2026-04-26T10:00:00Z"
}
```

| 字段 | 说明 |
|------|------|
| `event_id` | 用户已读的最新那条 Event 的 ID。由于因果性，表示该 Event 及其因果前驱均已读。 |
| `actor_id` | 阅读者 DID。该字段名与协议中其它 actor-引用字段一致；旧草稿使用过 `actor` / `reader`，已统一弃用。 |
| `hlc` | 可选；当 Sync Service 需要按 HLC 合并 / 去重多个 receipts 时由客户端附带。 |

### 2.3 防雪崩与合并

Read Receipt 是高频信号，发送方和 Sync Service 都 MUST 支持合并。客户端 SHOULD debounce 可见区域滚动产生的更新，并且对同一 `(space_id, flow_id, branch/thread, actor)` 在短窗口内只发送最新位置。默认建议窗口为 1 秒，交互结束、窗口失焦或显式“标为已读”时 SHOULD flush 最新位置。

Sync Service MAY 丢弃同一 scope 下较旧的 receipt，只向订阅方广播单调前进的最新位置；不得把每一次滚动增量都 fanout 成独立推送。公开或共享 receipt 的服务端限流维度至少应包含 actor、device、Space 和 Flow。超过频率时 SHOULD 返回或广播 `rate_limited` / `retry_after_ms` 语义，客户端 MUST 按退避合并后重试。

Push Gateway MUST NOT 因 read receipt 产生通知。它只能把 receipt / marker 作为 unread count、push suppression 和 badge recompute 的输入。

### 2.4 隐私控制

用户可以随时关闭发送已读回执。此配置属于 Client Preference，按 (flow, space, default) 顺序解析有效偏好；标准 Key 与字段定义见 [`discovery/client-preferences.md`](./client-preferences.md) §3.7。

- 该偏好同步在用户的加密 account data 中，不公开广播。
- 关闭只影响"是否发送 `cx.receipt.read`"，不影响 §3 私有 Read Marker，也不影响接收他人 receipt 的渲染。
- 客户端收到他人的 `cx.receipt.read` 时，SHOULD 在 UI 上更新已读头像的小图标位置；接收行为不依赖发送偏好。
- 当目标 scope 由 §2.5 声明 `disclosure="required"` 或 `disclosure="disabled"` 时，合规客户端 MUST 按该声明覆盖用户偏好（详见 §2.5）。

### 2.5 Space 披露策略 (Disclosure Policy)

Space MAY 通过 `cx.space.read_receipt_policy` 组件 cell 声明本 Space 内 `cx.receipt.read` 的披露要求。需要让 discussion 时间线与父 Space 在 read receipt policy 上分离时，**不**通过 branch 级别 override（v1 已删除该 hybrid），而是把 discussion 升级为独立 child Space（参见 `Flow.discussion_space_ref`，[`models/data-structures.md` §6.1.1](../models/data-structures.md)），由 child Space 自己声明 `cx.space.read_receipt_policy`。该 policy SHOULD 由 `cx.space.policy_components.components.read_receipt` 引用并纳入 MLS-bound `policy_root`。

```json
{
  "kind": "cx.space.read_receipt_policy",
  "payload": {
    "disclosure": "optional",
    "visibility": "members",
    "scope_overrides_allowed": true
  }
}
```

字段：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `disclosure` | `enum(required, optional, disabled)` | `optional` | 披露要求级别。`required` = 合规客户端 MUST 在该 scope 发送 receipt；`optional` = 完全交给 Client Preference；`disabled` = 客户端与 Sync Service MUST NOT 在该 scope 转发 `cx.receipt.read`。 |
| `visibility` | `enum(public, members, private)` | `members` | receipt 可见性。`public` = Space 可见性允许的全部观察者；`members` = 仅 branch 成员；`private` = 仅消息发送者本人（Sync Service 按发送者 fanout，不广播给其他成员）。 |
| `scope_overrides_allowed` | `bool` | `true` | 是否允许 child Space（如 `Flow.discussion_space_ref` 指向的子 Space）声明独立、收紧（不放宽）的 read receipt policy。父 Space 设为 `false` 时，所有 child Space 的 receipt policy MUST 等于或宽松于父策略；reducer 拒绝违规声明。 |

规则：

- 该策略是**软声明 / 合规承诺**，不是密码学强制。`cx.receipt.read` 由客户端自愿生成，恶意或不合规客户端始终可以"看了不报"，与 audited E2EE 的 RYW receipt（[`crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md) §4）不同。Space policy MUST NOT 把 `cx.receipt.read` 当作密码学审计回执使用。
- 客户端 MUST 在 join Space / 进入 Flow 时明示当前生效 `disclosure` 与 `visibility`，并在用户偏好 UI 中标注该 scope 的开关是否被 policy 锁定。
- `disclosure="required"`：合规客户端 MUST 不允许用户在该 scope 把 `cx.read_receipt.preferences` 设为 `send=false`，并 SHOULD 在每次进入 branch 时按 §2.2 发送至少一条覆盖当前可见 head 的 receipt。
- `disclosure="disabled"`：合规客户端 MUST NOT 生成该 scope 的 `cx.receipt.read`；Sync Service 收到时 SHOULD 丢弃并返回或广播 `policy_violation` 语义。Read Marker 不受影响。
- `visibility="private"`：Sync Service MUST 仅向 receipt 引用的 `event_id` 的发送者 fanout，不得广播给其他成员。Push Gateway 同样不得据此产生通知。
- Child Space policy 收紧父 Space policy 的方向一律允许（`required` → `disabled`、`public` → `private` 等更严方向）；放宽方向（如父 `disabled` → 子 `required`）SHOULD 被 reducer 拒绝，除非父声明了 `scope_overrides_allowed=true` 且明确允许。
- 与 §2.3 防雪崩规则共存：即便 `disclosure="required"`，客户端仍 MUST 按 debounce / merge 规则发送，不得为合规绕开限流。

## 3. Read Marker (私有游标)

Read Marker 用于多设备同步（例如你在手机上看了消息，电脑端不应再显示未读红点）。这是纯纯的**私有状态**。

### 3.1 存储位置

Read Marker 作为一种持久化的个人状态，MUST 作为加密 account data 或 actor-private Event 保存，而不是提交到发生协作的共享 Space Event history。

### 3.2 格式

Read marker schema：`cx.schema.read_marker.v1`。Marker 是 actor-private 持久状态，存放在加密 account data 或 actor-private stream 中，因此其 `id` 字段是 actor 控制下的标识符（例如 account-data key），不属于 typed-id-registry 的 wire object kind：按 §6.1 / §6.6 绑定 `(actor_id, space_id, scope, position, hlc, device_id)`：

```json
{
  "id": "read_marker_alice_flow_discussion_01",
  "schema": "cx.schema.read_marker.v1",
  "actor_id": "did:web:alice.example",
  "device_id": "cx:device:01js0ke0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "scope": {
    "kind": "flow_discussion",
    "ref": "cx:flow:01js1000000000000000000001"
  },
  "position": {
    "event_id": "cx:event:01js1rd0000000000000000000",
    "hlc": "01970e589d21-0004-a13f9c2e"
  },
  "updated_at": "2026-04-26T10:00:00Z"
}
```

- 该状态被加密存储在用户的 account data 中或单独 actor-private stream 中。
- 用户的其他设备通过同步 account data 的变更，获取最新的游标位置，从而清除本地未读红点。
- 多设备并发 marker 收敛 = HLC 取大；HLC 相等时按 device_id 字典序确定的顺序作为 actor-internal tiebreaker。

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

## 6. Schema 与 Notification Projection

### 6.1 Read Marker 字段

Read marker 是 actor-private 状态。最小结构示例：

```json
{
  "actor_id": "did:web:alice.example",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "scope": {
    "kind": "flow_discussion",
    "ref": "cx:flow:01js0r00m00000000000000000"
  },
  "position": {
    "event_id": "cx:event:01js0ev0000000000000000000",
    "hlc": "01970e589d21-0004-a13f9c2e"
  },
  "updated_at": "2026-04-26T00:00:00Z"
}
```

字段层级约束以 [`models/data-structures.md`](../models/data-structures.md) §15 为准。

### 6.2 Receipt 公开形态

Receipt 可以公开或私有，取决于 Space policy。schema：`cx.schema.read_receipt.v1`：

```json
{
  "receipt_type": "read",
  "schema": "cx.schema.read_receipt.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "flow_id": "cx:flow:01js1000000000000000000001",
  "branch": "discussion",
  "actor_id": "did:web:alice.example",
  "event_id": "cx:event:01js1read00000000000000000",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 6.3 Notification 派生 projection

Notification 是派生 projection，不是 canonical truth。schema：`cx.schema.notification.v1`：

```json
{
  "id": "cx:notif:01js0nf0000000000000000000",
  "schema": "cx.schema.notification.v1",
  "actor_id": "did:web:alice.example",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "flow_id": "cx:flow:01js1000000000000000000001",
  "branch": "discussion",
  "source_event_id": "cx:event:01js1mn0000000000000000000",
  "source_ref": "cx:message:01js1msg000000000000000000",
  "notification_type": "mention",
  "state": "unread",
  "priority": "normal",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 6.4 Query 形状

客户端本地 notification query：

```text
state=unread, cursor=<cursor>, limit=<int>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `state` | query | `string` | optional | 通知状态过滤，例如 `unread`。 |
| `cursor` | query | `cursor` | optional | 分页 cursor。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `notifications` | `object[]` | required | 当前 principal/device 可见通知。 |
| `counts` | `object` | optional | 未读数等聚合计数。 |
| `next_cursor` | `cursor` | optional | 下一页 cursor。 |

响应示例（非完整 schema）：

```json
{
  "notifications": [],
  "next_cursor": null,
  "counts": {}
}
```

### 6.5 多设备合并

多设备 read marker 合并规则：

- 同一 scope 取 causally latest marker
- 并发 marker 取 HLC 最大
- HLC 相同按 device id tie-break

Notification state SHOULD be derived from read marker + notification rule。

同一 actor / scope 的 read marker 更新 MAY 在传输层批处理；接收端只需要观察最终单调位置。服务端 SHOULD 合并短窗口内的 marker、receipt 和 notification projection 更新，并在 sync response 中携带覆盖这些输入的 frontier 或 sync token。Push / notification 服务不得为每个 read marker 变化生成独立通知；它只能重新计算 unread count、badge 和 push suppression。

### 6.6 跨设备同步语义

`cx.read.marker` 是 actor-private event，默认进入 principal 的 encrypted account data / actor-private stream，不进入共享 Space timeline，也不推进 Space reducer frontier。它仍然必须由当前 actor 或授权 device/session 签名，并绑定 `actor_id`、`space_id`、scope、position、HLC 和 device id。

跨设备已读同步流程：

1. 设备本地读到某个 scope 的位置后，提交或更新 actor-private `cx.read.marker`。
2. Principal Server / Sync Service 只向同一 principal 的授权设备返回该 marker，可通过 `account_data` 或 `receipts` stream 增量同步。
3. 每个设备按 §6.5 规则合并同一 scope 的 marker，重新派生本地 notification state、unread count 和 push suppression state。
4. 派生 notification 的 `state=read/unread` 不得作为共享 Space 事实写回；需要公开已读回执时，必须使用 Space policy 允许的 `cx.receipt.read` ephemeral / receipt stream，并与 private read marker 分开授权。
5. 当 marker 指向的 target event 对某设备不可见、缺失或被 redacted，客户端 MUST 保留 marker 但把对应 projection 标记为 `target_missing` / `redacted`，不得回退到更早 marker 造成未读计数反弹。

Notification projection MUST 绑定 read marker frontier、notification rule frontier 和 source event frontier。服务端返回 unread count 时 SHOULD 附带这些 frontier 或 sync token；客户端发现 frontier 落后时必须重新派生或请求增量，而不是把 push provider 的角标当作协议真相。
