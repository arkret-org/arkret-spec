# Client Sync v2

## 1. 目标

`sync-v2` 是客户端稳定增量同步协议。它不替代 repo replication，而是在 repo / relay / index 之上提供低延迟、可恢复、可分页、可过滤的客户端视图。

所有 full client 和 E2EE client MUST 支持本文件。

## 2. Endpoint

```http
POST /api/v2/sync
Authorization: Bearer <access_token>
Content-Type: application/json
```

请求：

```json
{
  "since": "sync_opaque_token",
  "timeout_ms": 30000,
  "set_presence": "online",
  "filter": {
    "spaces": ["space:..."],
    "timeline_limit": 50,
    "lazy_load_members": true,
    "include_redundant_members": false,
    "event_types": ["cx.message.*", "cx.entity.*"],
    "not_event_types": ["cx.typing"]
  },
  "subscriptions": {
    "space:...": {
      "ranges": [[0, 50]],
      "required_state": [
        ["cx.space.*", ""],
        ["cx.member.state", "$ME"],
        ["cx.view.definition", "*"]
      ]
    }
  }
}
```

响应：

```json
{
  "next_batch": "sync_opaque_token_2",
  "rooms": {},
  "spaces": {
    "join": {},
    "invite": {},
    "knock": {},
    "leave": {}
  },
  "to_device": {"events": []},
  "device_lists": {"changed": [], "left": []},
  "presence": {"events": []},
  "account_data": {"events": []},
  "notifications": {"events": []}
}
```

`rooms` 字段仅为兼容 bridge MAY 使用；Contrix 原生实现 SHOULD 使用 `spaces`。

## 3. Stream Classes

Sync 响应包含以下 stream：

| Stream | 持久性 | 用途 |
| --- | --- | --- |
| `timeline` | 持久 | Space 内 accepted events |
| `state` | 持久 | 当前 state event delta |
| `state_after` | 派生 | timeline 末尾之后的状态，用于正确解释事件 |
| `account_data` | 私有持久 | 标签、UI 偏好、recent emoji、push rules |
| `to_device` | 设备队列 | key verification、secret sharing、device messages |
| `ephemeral` | 短暂 | typing、presence、live cursor |
| `receipts` | 可配置 | read receipt / read marker delta |
| `notifications` | 派生 | inbox / push notification delta |
| `device_lists` | 持久 delta | E2EE device trust 更新 |
| `applet` | 持久/短暂 | Applet delivery receipt、bridge health |
| `blob_status` | 派生 | upload scan、thumbnail、retention 状态 |

客户端 MUST 使用 `next_batch` 作为唯一 resume token，不得解析 token 内部结构。

## 4. Space Buckets

`spaces` 按当前 membership 分桶：

- `join`
- `invite`
- `knock`
- `leave`

每个 Space 响应：

```json
{
  "timeline": {
    "events": [],
    "limited": false,
    "prev_batch": "page_token"
  },
  "state": {"events": []},
  "state_after": {"events": []},
  "ephemeral": {"events": []},
  "account_data": {"events": []},
  "summary": {
    "joined_member_count": 12,
    "invited_member_count": 1,
    "heroes": ["did:uuid:..."]
  },
  "unread_notifications": {
    "notification_count": 3,
    "highlight_count": 1
  }
}
```

如果 `timeline.limited=true`，客户端 MUST 使用 backfill / pagination 拉取缺口，不得假设 timeline 连续。

## 5. State After

服务器 SHOULD 在每个 joined Space 中返回 `state_after`，表示 `timeline.events` 应用完成后的 state delta。客户端渲染 timeline 中事件时 MUST 使用事件自己 auth state；渲染 timeline 末尾的当前 UI 时 SHOULD 使用 `state_after`。

这避免客户端用新权限、新成员名或新加密 epoch 错误解释旧事件。

## 6. Lazy Loading Members

当 `lazy_load_members=true`：

- 服务器 SHOULD 只返回 timeline 中 sender、被 mention actor、membership changed actor 和 required_state 指定 actor 的 `cx.member.state`。
- 客户端遇到未知 actor 时 MAY 调用 profile/directory API 补全。
- 如果 `include_redundant_members=false`，服务器 SHOULD 避免重复发送客户端已知且未变化的 member state。

## 7. Account Data and Private State

`account_data` 是 principal 或 device 私有状态，不进入 Space canonical state。标准类型：

- `cx.account.tag`
- `cx.account.push_rules`
- `cx.account.recent_emoji`
- `cx.account.view_state`
- `cx.account.ignored_actor`
- `cx.account.direct_space`

Account data MUST 按 principal/device 授权隔离。联邦节点不得向其他 principal 泄露 account data。

## 8. To-Device Delivery

`to_device.events` MUST 只包含当前 access token 对应 device 的消息。服务器在发送某个 `next_batch` 后 MAY 认为其中 to-device 已投递；客户端如果未处理成功，必须通过本地事务日志恢复。

To-device 队列过长时，服务器 MAY 返回 `limited=true` 并要求客户端调用：

```http
GET /api/v1/device_messages?from=<token>&limit=...
```

## 9. Filters

Filter MUST 是服务端可验证 JSON，不得包含任意脚本。服务器 MAY 限制：

- 最大 Space 数
- 最大 timeline limit
- 最大 required state 数
- 最大通配符展开量
- 最大等待时间

超限返回 `M_LIMIT_EXCEEDED`，并在 `retry_after_ms` 或 `limits` 中说明。

## 10. Token Semantics

`next_batch` MUST 绑定：

- principal id
- device id
- service id
- filter hash
- stream positions
- expiry

服务端 MAY 拒绝过期 token，并返回 `M_SYNC_TOKEN_EXPIRED`。客户端应回退到 initial sync。

## 11. Initial Sync

没有 `since` 时为 initial sync。服务器 SHOULD：

- 返回用户当前 joined/invited/knocked Spaces 的摘要。
- 对活跃 Space 返回有限 timeline。
- 返回足够 `required_state` 让客户端首屏可渲染。
- 返回 device list delta 的完整 baseline。

大型账户 MAY 使用 sliding window subscriptions，避免一次性返回所有 Space。

## 12. E2EE Requirements

E2EE client 在处理 encrypted event 前 MUST：

- 检查 `device_lists` 是否有变更。
- 检查 Space encryption epoch。
- 拉取缺失 KeyPackage / group secret。
- 对无法解密事件记录 `decryption_pending`，不得静默丢弃。

服务器 MUST NOT 因无法解密而过滤 encrypted event。

