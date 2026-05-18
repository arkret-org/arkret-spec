---
title: Client Sync
---

## 1. 目标

Client Sync 是客户端 **账号视角聚合** 同步协议。它在 Events API / sync service 之上提供跨 Space 的稳定 delta 视图（包含 to_device、account_data、device_lists、presence、unread / notification counts），不是裸事件读取——逐 Space 的事件查询和实时订阅请使用 `cx.events.query` / `cx.events.subscribe`。

本文定义 Contrix v1 的客户端账号同步语义，不表示存在 `sync v1` / `sync v2` 两个协议版本。版本演进应由 transport binding 路径、feature discovery 和 conformance profile 表达。

所有 full client 和 E2EE client MUST 支持本文件。

## 2. Endpoint

```http
POST /api/v1/sync
Authorization: Bearer <session_token>
Content-Type: application/json
```

该端点对应 `cx.sync.account`。它聚合跨 Space delta、to_device、account_data、device_lists、presence；不同于 `GET /api/v1/events/subscribe`（按 selector 的事件流订阅）和 `GET /api/v1/events?before=...` / `?after=...`（按 selector 的双向历史查询）。三者可以共享 cursor 与授权规则，但 `operation_id`、响应语义与所属 namespace 不同：account 同步在 `cx.sync.*`，事件读取在 `cx.events.*`。

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前 principal / device。 |
| `since` | body | `cursor` | optional | 上次响应中的 `cursor`（purpose=`stream`）；缺省表示初始同步。 |
| `timeout_ms` | body | `int` | optional | 长轮询等待时间上限。 |
| `set_presence` | body | `enum(online,offline,unavailable)` | optional | 同步时设置当前设备 presence。 |
| `filter` | body | `object` | optional | 过滤条件。 |
| `filter.spaces` | body | `id[]` | optional | 限制返回 Space。 |
| `filter.timeline_limit` | body | `int` | optional | 每个 Space timeline 数量上限。 |
| `filter.lazy_load_members` | body | `boolean` | optional | 是否延迟加载成员。 |
| `filter.include_redundant_members` | body | `boolean` | optional | 是否包含冗余成员状态。 |
| `filter.event_types` | body | `string[]` | optional | 事件类型 allow list。 |
| `filter.not_event_types` | body | `string[]` | optional | 事件类型 deny list。 |
| `subscriptions` | body | `object` | optional | Sliding sync 风格的 Space subscription 配置。 |

请求示例（非完整 schema）：

```json
{
  "since": "cx:cursor:eyJ2IjoxfQ",
  "timeout_ms": 30000,
  "set_presence": "online",
  "filter": {
    "spaces": ["cx:space:..."],
    "timeline_limit": 50,
    "lazy_load_members": true,
    "include_redundant_members": false,
    "event_types": ["cx.message.*", "cx.flow.*", "cx.space.*", "cx.morph.*"],
    "not_event_types": ["cx.typing"]
  },
  "subscriptions": {
    "space:...": {
      "ranges": [[0, 50]],
      "required_state": [
        ["cx.space.*", ""],
        ["cx.member.state", "$ME"],
        ["cx.view.*", "*"]
      ]
    }
  }
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `cursor` | `cursor` | required | 下次同步使用的 opaque stream cursor（`cx:cursor:<base64url>`，purpose=`stream`）。客户端 MUST 直接作为 `since` 回传，不得解析。 |
| `spaces` | `object` | optional | Contrix 原生 Space 聚合同步结果，按 `join` / `invite` / `knock` / `leave` 分桶；每个 bucket 以 `cx:space:*` 为 key。 |
| `to_device` | `object` | optional | 当前设备 to-device 消息。 |
| `device_lists` | `object` | optional | 设备列表变化。 |
| `presence` | `object` | optional | presence 事件。 |
| `account_data` | `object` | optional | actor-private account data。 |
| `notifications` | `object` | optional | 通知增量。 |

响应示例（非完整 schema）：

```json
{
  "cursor": "cx:cursor:eyJ2IjoxLCJwIjoic3RyZWFtIn0",
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

`spaces.join`、`spaces.invite`、`spaces.knock` 和 `spaces.leave` MUST 是对象；每个对象的 key 是 `cx:space:*`，value 是该 Space 的聚合同步结果。`state`、`state_after`、`ephemeral`、Space-scoped `account_data` 以及顶层 `to_device` / `presence` / `account_data` / `notifications` 都使用事件容器形状：

```json
{
  "events": []
}
```
## 3. Stream Classes

Sync 响应包含以下 stream：

| Stream | 持久性 | 用途 |
| --- | --- | --- |
| `timeline` | 持久 | Space 内 accepted events |
| `state` | 持久 | 当前 state event delta |
| `state_after` | 派生 | timeline 末尾之后的状态，用于正确解释事件 |
| `state_at_window_start` | 派生 | `timeline.limited=true` 时 window 起点 anchor 状态，见 §5 |
| `account_data` | 私有持久 | 标签、UI 偏好、recent emoji、push rules |
| `to_device` | 设备队列 | key verification、secret sharing、device messages |
| `ephemeral` | 短暂 | typing、presence、live cursor |
| `receipts` | 可配置 | read receipt / read marker delta |
| `notifications` | 派生 | inbox / push notification delta |
| `device_lists` | 持久 delta | E2EE device trust 更新 |
| `applet` | 持久/短暂 | Applet delivery receipt、bridge health |
| `blob_status` | 派生 | upload scan、thumbnail、retention 状态 |

客户端 MUST 使用 `cursor` 作为唯一 resume token，不得解析 token 内部结构。

`receipts`、`notifications` 和高频 actor-private `read_marker` delta MAY 被服务端合并；同一 scope 在一个 sync 窗口内只需要返回最新可见位置和最终 unread count。客户端不得要求服务返回每一次中间 read receipt / marker 变化；`cursor` 只承诺覆盖响应中声明的最终 stream positions。

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
    "preview_only": false,
    "prev_cursor": "cx:cursor:eyJ2IjoxLCJwIjoic3RyZWFtIn0"
  },
  "state": {"events": []},
  "state_after": {"events": []},
  "state_at_window_start": {
    "actor_profiles": {},
    "space_metadata": {},
    "e2ee_epoch": null
  },
  "ephemeral": {"events": []},
  "account_data": {"events": []},
  "summary": {
    "joined_member_count": 12,
    "invited_member_count": 1,
    "heroes": ["did:webvh:..."]
  },
  "unread_notifications": {
    "notification_count": 3,
    "highlight_count": 1
  }
}
```

如果 `timeline.limited=true`，客户端 MUST 使用 backfill / pagination 拉取缺口，不得假设 timeline 连续。服务端 SHOULD 在响应中提供 `prev_cursor`、顶层 `cursor`、`snapshot_frontier` 或等价恢复提示；若缺口无法用当前 cursor 恢复，必须返回 `cursor_expired`、`cursor_integrity_invalid`、`stale_frontier` 或 `temporarily_unavailable`，不得静默退化为不完整状态。

`timeline.limited=true` 时，服务端 MUST 二选一返回 `state_at_window_start`（projection-only anchor 状态）或标记 `timeline.preview_only=true`；详见 §5.2。

## 5. State After 与 State At Window Start

### 5.1 State After (timeline 末尾状态)

服务器 SHOULD 在每个 joined Space 中返回 `state_after`，表示 `timeline.events` 应用完成后的 state delta。客户端渲染 timeline 中事件时 MUST 使用事件自己 auth state；渲染 timeline 末尾的当前 UI 时 SHOULD 使用 `state_after`。

这避免客户端用新权限、新成员名或新加密 epoch 错误解释先前事件。

### 5.2 State At Window Start (limited timeline 边界状态)

**协议正确性层面**，Contrix 的事件携带 `prev_refs` 与 `refs[role=authorized_by]`，每个事件自带因果与授权 anchor；reducer / projection 在 gap 期间不会误判 authz 或 state convergence。这部分不依赖额外 gap-boundary 信息。

**渲染正确性层面**，当 `timeline.limited=true` 且 window 内可能包含 actor profile 更新、Space 元数据变更、或 E2EE epoch rotation 时，客户端按"当前 anchor view"渲染 window 起点事件会显示错误的 display name / room name / 加密 epoch。为此，服务端 MUST 在响应该 Space timeline 时二选一：

**(a) 返回 `state_at_window_start`** (推荐路径，projection-only)：

```json
{
  "timeline": {
    "events": [],
    "limited": true,
    "prev_cursor": "cx:cursor:..."
  },
  "state_at_window_start": {
    "actor_profiles": {"did:webvh:...": {"display_name": "...", "avatar_ref": "..."}},
    "space_metadata": {"name": "...", "topic": "...", "join_rule": "..."},
    "e2ee_epoch": {"epoch": 17, "key_ref": "cx:mls:..."}
  }
}
```

- 该字段是 **派生 projection-only 字段**，不参与 state hash / frontier 计算，不进入因果图。
- 字段范围仅限三类 anchor：`actor_profiles`（window 内出现的 actor）、`space_metadata`（Space-level Lattice cell value at window start）、`e2ee_epoch`（window 起点的 MLS epoch hint）。
- 客户端 SHOULD 在渲染 window 内事件时优先用 `state_at_window_start` 而非"当前 anchor view"。
- 服务端可以从 anchor view 的历史 cell value（按 HLC 反向查询）派生该状态；不可用时退路径 (b)。

**(b) 标记 `preview_only=true`** (回退路径)：

```json
{
  "timeline": {
    "events": [],
    "limited": true,
    "preview_only": true,
    "prev_cursor": "cx:cursor:..."
  }
}
```

- 客户端 MUST NOT 在 backfill 完成（即缺口被 `prev_cursor` 拉取并应用）前把该 timeline 渲染为已验证的完整 UI。
- 客户端可以渲染为占位、loading 状态或带 "loading history..." 标签的预览，但不得让用户感知为"完整 timeline"。

> Rationale: Matrix `/sync` limited timeline 同时返回 state delta；Contrix 的 per-event auth state 已覆盖协议层正确性，但渲染层（display name / room avatar / epoch boundary）仍可能错位。`state_at_window_start` 给服务端实现一条轻量恢复路径，`preview_only` 给无法计算历史 anchor 的实现一条安全回退。

## 6. Event Ordering

Client Sync 的事件顺序是展示顺序和增量恢复顺序，不是授权真相本身。授权真相仍由 event hash、`prev_refs`、`refs[role=authorized_by]`、space version 和 reducer 决定。

服务器返回 `timeline.events` 时 MUST 满足：

1. 同一响应内的事件按 deterministic timeline order 排列。
2. 若事件 B 直接依赖事件 A，且 A 在同一响应窗口中可见，则 A MUST 出现在 B 之前。
3. 如果依赖事件因过滤、权限、分页或缺失而不在响应中，B MUST 带有足够 `prev_refs` / `refs[role=authorized_by]`，客户端可 soft fail、backfill 或延迟渲染。
4. 服务器 MUST NOT 使用本地数据库自增 ID、接收顺序或 Sync Service 到达顺序作为跨实现排序依据。

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
- `actor_seq` 只在同一 actor 的已知因果路径内辅助排序；并发 sibling fork 仍由后续 tie-breaker 收敛。
- `event_id` 是最终 tie-breaker。

对于协议状态，客户端 MUST 使用 `event-auth-state-resolution.md` 的 Anchor view 与 Lattice cell value 解释当前态，不得只取 timeline 中最后出现的同 kind Event。

## 7. Large Account and Large Space Sync

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
  "cursor": "cx:cursor:eyJ2IjoxLCJwIjoic3RyZWFtIn0",
  "partial": true,
  "priority": "active_view",
  "spaces": {}
}
```

客户端 MUST treat `cursor` as the only resume token. 如果某个 Space 的 timeline 返回 `limited=true`，客户端不得把当前窗口视为完整历史。

## 8. Lazy Loading Members

当 `lazy_load_members=true`：

- 服务器 SHOULD 只返回 timeline 中 sender、被 mention actor、membership changed actor 和 required_state 指定 actor 的 `cx.member.state`。
- 客户端遇到未知 actor 时 MAY 调用 profile/directory API 补全。
- 如果 `include_redundant_members=false`，服务器 SHOULD 避免重复发送客户端已知且未变化的 member state。

## 9. Account Data and Private State

`account_data` 是 principal 或 device 私有状态，不进入 Space canonical state。标准类型：

- `cx.account.tag`
- `cx.account.push_rules`
- `cx.account.recent_emoji`
- `cx.account.view_state`
- `cx.account.ignored_actor`
- `cx.account.direct_space`

Account data MUST 按 principal/device 授权隔离。联邦节点不得向其他 principal 泄露 account data。

## 10. To-Device Delivery

`to_device.events` MUST 只包含当前 access token 对应 device 的消息。

**To-device 投递推断 (normative)**：服务器在收到客户端回传的 `since=<cursor>` 后，**MUST 先按 §12 完整性校验** (MAC/签名 验证 或 stateful handle lookup) 通过，才可将该 cursor 内 `d` (device positions) 之前的 to-device 消息视为已投递并从服务端队列清理。完整性校验失败时 MUST 返回 `cursor_integrity_invalid` 且 **MUST NOT** 推进 to-device 投递状态。客户端如果未处理成功，必须通过本地事务日志恢复。

> Rationale: 若服务端仅按语法 / TTL / purpose 校验就接受客户端 `d` 位置，byzantine 客户端 (或被 XSS / 复制日志泄露后被重放的 cursor) 可篡改 `d` 推进 to-device ack，导致 key verification、cross-signing reset、secret sharing 等 to-device 消息被永久丢弃 — 即使诚实客户端重连也拿不回。

To-device 队列过长时，服务器 MAY 返回 `limited=true` 并要求客户端调用：

```http
GET /api/v1/device_messages?from=<cursor>&limit=...
```

该 endpoint 的 `from` cursor 同样 MUST 通过 §12 完整性校验后才能用于服务端读位置推进。

## 11. Filters

Filter MUST 是服务端可验证 JSON，不得包含任意脚本。服务器 MAY 限制：

- 最大 Space 数
- 最大 timeline limit
- 最大 required state 数
- 最大通配符展开量
- 最大等待时间

超限返回 `rate_limited`、`payload_too_large` 或 `invalid_param`，并在 `Retry-After`、`retry_after_ms` 或 `limits` 中说明。

## 12. Cursor Semantics

`cursor`（purpose=`stream`）MUST 绑定：

- principal id
- device id
- service id
- filter hash
- stream positions
- expiry

`cursor`（purpose=`barrier`）由写接口在响应中返回（见 [`api-conventions.md` §8](./api-conventions.md)），用于 `X-Contrix-Wait-For` header；它和 stream cursor 共享 wire 形态 `cx:cursor:<base64url>`，由内部 `purpose` 字段区分。客户端不需要分辨，只需把"写响应里的 cursor"作为 wait-for header、把"`/sync` 响应里的 cursor"作为 `since` 即可。

### 12.1 Cursor Integrity (normative)

无论 stream 还是 barrier cursor，wire 形态 `cx:cursor:<base64url(canonical_json)>` 都 **MUST** 是服务端可验证的同步位置；服务端 **MUST NOT** 仅按语法 / TTL / purpose 校验就把客户端回传的 cursor 当作"可信位置"用于推进 to-device ack、`/sync` since、`X-Contrix-Wait-For` barrier 解除、`dropped` / `resync_required` 恢复或其他不可逆 server-side state。

实现 MUST 选择以下两种 cursor 形态之一（互斥，由 schema `oneOf` 强制）；两种形态都满足"服务端可验证"的安全契约：

**(A) Stateless self-describing cursor**：canonical body 内含 `s` / `d` / `target` 等结构化状态字段，**MUST** 携带 `_mac` 或 `_sig` 中的至少一个：

- `_mac`：HMAC over canonical bytes (除 `_mac` 自身外的所有字段)，密钥由 issuing service 持有，算法 MUST 是 HMAC-SHA-256 或更强。
- `_sig`：detached signature over same canonical bytes，密钥使用 issuing service 的 cursor-signing key。
- transcript MUST 绑定：`purpose`、principal id、device id、service DID / service id、filter hash、stream positions（`s` / `d`）、`target`（barrier 时）、`x`、issuer key id。

**(B) Stateful opaque handle cursor**：canonical body 缩为 `{v, purpose, t, x, h}`，无 `s` / `d` / `target`；`h` 是 issuing service 生成的不可猜测 handle（解码后熵 ≥ 128 bit），service 内部维护 handle → `(principal, device, service, filter_hash, purpose, positions, target?, expiry)` 映射。Handle 校验本身就是完整性校验 — 不可加 `_mac` / `_sig`。这是 Matrix `next_batch` / MSC4186 `pos` 的等价形式，适合不想引入 MAC/签名密钥管理的实现。

### 12.2 校验流程 (normative)

任何 endpoint 在使用客户端回传的 cursor 推进 server-side state 之前，MUST 执行：

1. 解析 `cx:cursor:<base64url>` 并按 `cursor.schema.json` 校验语法、`purpose`、TTL (`x` 未过期)。语法/TTL 失败映射 `cursor_invalid` / `cursor_expired`。
2. **完整性校验**:
   - 若 body 含 `h`：以 `h` 查 issuing service 本地表，校验 handle 存在、未过期、未撤销，且绑定的 `(principal, device, service, filter_hash, purpose)` 与当前 authenticated request 匹配。
   - 若 body 含 `_mac` / `_sig`：以 issuing service 的当前 cursor key (按 `issuer_kid` 选取) 校验 MAC/signature；transcript 必须重算一致，且绑定字段与当前 authenticated request 匹配。
3. 任一校验失败 → 返回 `cursor_integrity_invalid`，**MUST NOT** 推进任何 server-side state。
4. 校验通过后才可读 cursor 内部 `s` / `d` / `target`（stateless 形态）或 handle 解析出的 positions（stateful 形态），并用于推进同步状态。

`cursor_integrity_invalid` 与 `cursor_expired` 语义不同：前者是 tamper / 未知 handle / cross-binding，后者是 TTL 超时。客户端对 `cursor_integrity_invalid` 的恢复路径与 `cursor_expired` 一致（重做 initial sync），但客户端 SHOULD 把它视为本端 cursor 状态被污染的信号，清理本地 cursor 缓存。

### 12.3 过期或缺口恢复流程

1. 客户端保留本地 `cursor`、filter hash、未确认写入和最后可验证 frontier。
2. 收到 `cursor_expired` / `cursor_integrity_invalid` / `stale_frontier` 后，先调用 `sync/describe` 或 `sync/snapshot-head` 获取当前 frontier 与推荐 snapshot。
3. 若 snapshot 可用，客户端 MUST 验证签名、签名者授权、state hash、frontier 和 chunk digest 后再采用。
4. 从 snapshot frontier 或服务返回的 backfill 起点执行 `sync/backfill`，补齐缺口后再恢复 `sync/subscribe` 或 `POST /sync`。
5. 若 snapshot 校验失败，客户端 MUST 回退到 Event history replay 或 Event-only backfill，并可将来源标记为 degraded。

## 13. Initial Sync

没有 `since` 时为 initial sync。服务器 SHOULD：

- 返回用户当前 joined/invited/knocked Spaces 的摘要。
- 对活跃 Space 返回有限 timeline。
- 返回足够 `required_state` 让客户端首屏可渲染。
- 返回 device list delta 的完整 baseline。

大型账户 MAY 使用 sliding window subscriptions，避免一次性返回所有 Space。

## 14. E2EE Requirements

E2EE client 在处理 encrypted event 前 MUST：

- 检查 `device_lists` 是否有变更。
- 检查 Space encryption epoch。
- 拉取缺失 KeyPackage / group secret。
- 对无法解密事件记录 `decryption_pending`，不得静默丢弃。

服务器 MUST NOT 因无法解密而过滤 encrypted event。

## 15. E2EE and MLS Sync Performance

E2EE Space 的同步必须把“事件顺序”和“密钥可用性”分开处理。事件可以先进入本地 raw event cache；解密可以异步完成。

客户端处理加密 timeline 时 SHOULD：

1. 先验证 event envelope、hash、signature、`space_id`、`refs[role=authorized_by]` 和 `prev_refs`。
2. 根据明文 routing metadata 将事件放入 timeline / reducer 队列。
3. 检查事件声明的 `mls_epoch`。
4. 如果本地缺少该 epoch 的 group state，拉取缺失 `cx.mls.*` state event、MLS Commit 和必要 key backup。
5. 如果仍无法解密，将事件标记为 `decryption_pending`，但保留排序位置和引用关系。
6. 当 MLS epoch 补齐后，异步重试解密并更新 materialized view。

服务器和 Sync Service 不需要解密正文，也不得因为无法解密而改变事件顺序或过滤事件。

为降低大规模 E2EE 同步成本：

- 当加密 timeline 中包含未知 epoch 的事件时，MLS epoch state SHOULD 作为 required state 返回。
- 客户端 SHOULD 按 `(space_id, epoch)` 缓存 epoch state 与 ratchet tree。
- 历史 backfill SHOULD 把加密 payload 与 MLS epoch 材料分成不同的范围请求。
- 新设备恢复 SHOULD 优先使用加密密钥备份 / secret storage，而非向其他成员逐条重发历史密钥。
- 加密附件 SHOULD 通过 blob ref 与 content hash 进行懒加载。
- 服务端全文搜索 MUST NOT 要求 plaintext；加密 Space 的搜索应使用本地索引或受控的 TEE profile。

如果密钥状态与事件状态出现缺口：

- 缺事件依赖：event MUST remain soft failed until backfill resolves it.
- 缺 MLS epoch：event MAY be accepted as encrypted event but displayed as `decryption_pending`.
- epoch 明确已被移除成员不可访问：客户端 MUST fail closed and not request keys from unauthorized members.

### 15.1 `decryption_pending` timeout and recovery

客户端首次把某事件标记为 `decryption_pending` 时 MUST 记录 `first_pending_at`、缺失的 `(space_id, flow_id?, track?, group_id, epoch)`、已尝试的恢复 source 和最近一次错误。默认 `decryption_pending_timeout` 为 7 天；Space policy 或实现 profile MAY 声明更短值，高保障 profile SHOULD 更短，但不得无限期保持无诊断 pending。

在 timeout 前，客户端 SHOULD 按以下顺序恢复：

1. 拉取缺失的 `cx.mls.*` state event、winner `cx.mls.commit`、Welcome 和 `governance_binding` 依赖。
2. 查询本 actor 授权设备的 encrypted key backup / secret storage。
3. 在 history sharing policy 允许时，请求当前授权 peer 对指定 epoch range 发送 key share。
4. 若 Space policy 声明 Archive Node / Audit Node / Key Recovery Service，可向该受托服务请求最小 epoch range。

当连续 epoch 缺口超过 `epoch_gap_recovery_threshold`（默认 32 个 epoch）或本地 backfill 预算耗尽时，客户端 SHOULD 切换到 range-based recovery：按 epoch 区间请求 key material、MLS Commit chain 和必要 snapshot proof，而不是逐消息重试。任何 key share 都必须绑定接收 principal、device、epoch range、policy hash 和发送设备签名；不得向已被移除、未授权或无法验证的成员请求密钥。

超过 `decryption_pending_timeout` 后，客户端 MUST 将用户可见投影标记为 `decryption_failed`，保留 metadata-only 占位、排序位置、引用关系和重试诊断，并向用户显示不可解密状态。若之后合法 key material 到达，客户端 MAY 重新解密并把状态从 `decryption_failed` 恢复为 verified content，但必须保留恢复审计记录。
