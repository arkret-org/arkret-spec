# Client Sync

## 1. 目标

Client Sync 是客户端稳定增量同步协议。它不替代 repo replication，而是在 repo / relay / index 之上提供低延迟、可恢复、可分页、可过滤的客户端视图。

本文定义当前草案唯一的客户端同步语义，不表示存在 `sync v1` / `sync v2` 两个协议版本。版本演进应由 transport binding 路径、feature discovery 和 conformance profile 表达。

所有 full client 和 E2EE client MUST 支持本文件。

## 2. Endpoint

```http
POST /api/v1/sync
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

## 5.1 Event Ordering

Client Sync 的事件顺序是展示顺序和增量恢复顺序，不是授权真相本身。授权真相仍由 event hash、`prev_refs`、`auth_refs`、space version 和 reducer 决定。

服务器返回 `timeline.events` 时 MUST 满足：

1. 同一响应内的事件按 deterministic timeline order 排列。
2. 若事件 B 直接依赖事件 A，且 A 在同一响应窗口中可见，则 A MUST 出现在 B 之前。
3. 如果依赖事件因过滤、权限、分页或缺失而不在响应中，B MUST 带有足够 `prev_refs` / `auth_refs`，客户端可 soft fail、backfill 或延迟渲染。
4. 服务器 MUST NOT 使用本地数据库自增 ID、接收顺序或 Relay 到达顺序作为跨实现排序依据。

默认 timeline order：

```text
causal_depth ASC,
hlc ASC,
actor_id ASC,
actor_seq ASC,
event_id ASC
```

其中：

- `causal_depth` 来自已知 DAG / prev refs。
- `hlc` 用于近实时排序。
- `actor_seq` 保证同一 actor 本地顺序。
- `event_id` 是最终 tie-breaker。

对于 state event，客户端 MUST 使用 `event-auth-state-resolution.md` 的 state resolution 输出解释当前态，不得只取 timeline 中最后出现的同 key state event。

## 5.2 Large Account and Large Space Sync

数据量巨大时，Client Sync MUST 支持分层同步，而不是一次性拉取全部事件。

推荐策略：

- initial sync 只返回 Space 摘要、必要 `required_state` 和有限 timeline。
- 活跃 Space 优先，低优先级 Space 只返回 unread / mention / summary。
- 使用 sliding window subscriptions 拉取当前视图需要的 timeline ranges。
- 使用 `timeline.limited=true` 标记缺口，并通过 backfill / pagination 拉取。
- 使用 lazy loading members，避免同步全量成员状态。
- 使用 snapshot manifest 快速恢复当前态，再从 snapshot frontier 拉取增量。
- Blob、附件、缩略图、全文索引和历史密文按需拉取。
- 客户端本地维护 raw event cache、reduced state cache 和 materialized view cache。

服务器 MAY 对响应进行分片：

```json
{
  "next_batch": "sync_opaque_token",
  "partial": true,
  "priority": "active_view",
  "spaces": {}
}
```

客户端 MUST treat `next_batch` as the only resume token. 如果某个 Space 的 timeline 返回 `limited=true`，客户端不得把当前窗口视为完整历史。

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

## 13. E2EE and MLS Sync Performance

E2EE Space 的同步必须把“事件顺序”和“密钥可用性”分开处理。事件可以先进入本地 raw event cache；解密可以异步完成。

客户端处理加密 timeline 时 SHOULD：

1. 先验证 event envelope、hash、signature、`space_id`、`auth_refs` 和 `prev_refs`。
2. 根据明文 routing metadata 将事件放入 timeline / reducer 队列。
3. 检查事件声明的 `mls_epoch`。
4. 如果本地缺少该 epoch 的 group state，拉取缺失 `cx.mls.*` state event、MLS Commit 和必要 key backup。
5. 如果仍无法解密，将事件标记为 `decryption_pending`，但保留排序位置和引用关系。
6. 当 MLS epoch 补齐后，异步重试解密并更新 materialized view。

服务器和 Relay 不需要解密正文，也不得因为无法解密而改变事件顺序或过滤事件。

为降低大规模 E2EE 同步成本：

- MLS epoch state SHOULD be returned as required state when encrypted timeline includes events from unknown epochs.
- 客户端 SHOULD cache epoch state and ratchet tree by `(space_id, epoch)`.
- 历史 backfill SHOULD request encrypted payload and MLS epoch material in separate ranges.
- 新设备恢复 SHOULD prefer encrypted key backup / secret storage over asking其他成员逐条重发历史密钥。
- 加密附件 SHOULD be lazy-loaded by blob ref and content hash.
- 服务端全文搜索 MUST NOT require plaintext. 加密 Space 搜索应使用本地索引或受控 TEE profile。

如果密钥状态与事件状态出现缺口：

- 缺事件依赖：event MUST remain soft failed until backfill resolves it.
- 缺 MLS epoch：event MAY be accepted as encrypted event but displayed as `decryption_pending`.
- epoch 明确已被移除成员不可访问：客户端 MUST fail closed and not request keys from unauthorized members.
