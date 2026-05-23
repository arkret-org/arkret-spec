---
title: Client Sync
---

## 1. 目标

Client Sync 是客户端 **账号视角聚合** 推流协议。它在 Events API 之上提供跨 Realm 的稳定 delta 视图（包含 to_device、account_data、device_lists、presence、unread / notification counts），以**长连接 NDJSON 流**的形式由服务端按需推送。它不是裸事件读取——逐 Realm 的事件查询和实时订阅请使用 `cx.events.query` / `cx.events.subscribe`。

`cx.account.subscribe` 与 `cx.events.subscribe` 是对称的两类 streaming 订阅:
- `cx.events.subscribe` 是**逐 Realm / actor 的事件流**(selector 范围内的每条 Event)
- `cx.account.subscribe` 是**账号视角的聚合流**(跨所有 Realm 的 delta 总览 + account-scoped 数据)

两者共享相同的 stream cursor 形态、resume / `dropped` / `resync_required` 恢复语义,差异仅在 selector 与 frame 内容。

本文定义 Contrix v1 的客户端账号同步语义,不表示存在 `sync v1` / `sync v2` 两个协议版本。版本演进应由 transport binding 路径、feature discovery 和 conformance profile 表达。

所有 full client 和 E2EE client MUST 支持本文件。

## 2. Endpoint

```http
GET /api/v1/account/subscribe?catchup=true
Authorization: Bearer <session_token>
Accept: application/x-ndjson
```

上面是 **initial account sync** 的 canonical 调用：不带 `after`，显式设置 `catchup=true`。这里的 `catchup` 不是"返回全部历史记录"，而是要求服务端先发送当前账号 baseline（有限 timeline + 必要 state + account-scoped 当前位置），再以 `catchup_complete` 标记 baseline 完成并进入实时推送。常规网络重连使用 `GET /api/v1/account/subscribe?after=<cursor>&catchup=true` 补齐断线期间的账号 delta；收到 `dropped` frame 后的补洞重连同样使用 `GET /api/v1/account/subscribe?after=<cursor>&catchup=true`。

该端点对应 `cx.account.subscribe`,wire 形态是长连接 NDJSON 流。它聚合跨 Realm delta、to_device、account_data、device_lists、presence;不同于 `GET /api/v1/events/subscribe`(按 selector 的事件流订阅)和 `GET /api/v1/events?before=...` / `?after=...`(按 selector 的双向历史查询)。三者可以共享 cursor 与授权规则,但 `operation_id`、响应语义与所属 namespace 不同:account 同步在 `cx.account.*`,snapshot 入口在 `cx.snapshot.*`,事件读取在 `cx.events.*`。

Account subscribe 的服务边界是当前 authenticated session 绑定的 Principal Server service DID。若同一 principal DID 同时在个人 Principal Server 与组织 Principal Server 上有账号/设备上下文,客户端必须分别维护 session、cursor、to-device queue 和 push registration,并对每个上下文建立独立的 `/account/subscribe` 长连接。某个 Realm 的 timeline / notification delta 只应出现在该成员 effective `delivery_binding.recipient_service_did` 指向的服务上;DID Document 中的默认 Principal Server 不得把其它 Realm-scoped delivery binding 的 delta 聚合进自己的 `/account/subscribe` 流。

### 2.1 Delivery Binding UX 指引（SHOULD）

`delivery_binding` 由 schema 强制存在并显式化，但**用户感知**应保持轻量。客户端 UI SHOULD：

1. **默认不暴露 `delivery_binding` 字段**。普通邀请 / 成员添加 / 加入 Realm 流程中，UI **不展示** `recipient_service_did` 选择控件，除非：
   - 邀请方处于多 Principal Server 登录上下文且没有可推断的默认值（fall back to `explicit`，要求用户选择）；
   - Realm policy 强制 `binding_source ∈ {explicit}` 且邀请方未在该上下文登录（提示用户切换上下文或退出邀请）；
   - 用户主动进入"高级 / 投递设置"面板查看 / 修改。
2. **成员列表展示绑定上下文**。当某 Realm 内成员的 `delivery_binding.recipient_service_did` 不属于该 actor DID Document 默认 `ContrixPrincipalServer` 时，UI SHOULD 在该成员条目附近显示其 binding 上下文（例如 `Bob @ Acme`、`Carol @ Beta`）；当属于默认时 SHOULD 仅显示 actor，不显示 binding。展示形态可使用组织 endorsement 的 `display_name` / `logo` 而不是 raw service DID。
3. **邀请 flow 智能默认**。客户端 SHOULD 按当前邀请方上下文自动提议 binding：
   - 用户输入 `@alice:acme.example` / `alice@acme.example` 时，先走 `cx.directory.resolve_handle(intent="member_add")` 得到 `subject` DID 与 `delivery_binding_hint`，UI 显示 `Alice @ Acme` 这类上下文标签，不展示 raw service DID；
   - 邀请方在 Org-A 内部 Realm 中邀请 → 默认 invitee 也走 Org-A binding（如果 Org-A organization registry 把 invitee 列为成员）；
   - 邀请方在个人 Realm 中邀请 → 默认 invitee DID Document `did_document_default`（若 Realm policy 允许）；
   - 多上下文 invitee + 无明确默认 → 提示用户在已知上下文中选择，**不要静默选择**。
4. **跨上下文切换感知**。客户端在同一 UI 中聚合显示多 Principal Server 的 timeline 时 SHOULD 显式区分上下文（如标签栏 / 子账号面板），避免把工作 / 个人事件混合渲染。聚合通知（badge count / push）按上下文分桶；不允许跨上下文合并未读数。

这些是 SHOULD，不构成 wire 互操作的硬约束；但符合 `cx.profile.full_client.v1` / `cx.profile.e2ee_client.v1` 的实现 SHOULD 在 UX self-check 中覆盖。

请求参数(query string,无 body):

| 参数 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前 principal / device。 |
| `after` | query | `cursor` | optional | 订阅起点 cursor(purpose=`stream`,排除语义),从此 cursor *之后* 开始接收 frame。缺省表示没有可恢复账号 cursor。 |
| `catchup` | query | `boolean` | optional | 默认 `false`。`after` 存在时,`true` 表示服务端先回放 `after=` 之后到当前 frontier 的账号聚合 delta,再发 `catchup_complete` frame,然后切到实时尾部;这不是全量历史。`after` 缺省且 `catchup=true` 是 **initial account sync**:服务端 MUST 先发送覆盖当前账号 baseline 的 `delta` frame(Realm 摘要、必要首屏 state、device list baseline、to_device/account_data/notification 当前位置),再发送 `catchup_complete`。完整历史必须通过 `cx.events.query` 分页/区间读取。 |
| `set_presence` | query | `enum(online,offline,unavailable)` | optional | 连接建立时设置当前设备 presence,服务端在 frame 推送过程中向其他 Realm 广播。 |
| `filter` | query (deepObject) | `object` | optional | 过滤条件。语义同 events.subscribe。 |
| `filter.realms` | query | `id[]` | optional | 限制返回 Realm。 |
| `filter.timeline_limit` | query | `int` | optional | 每个 Realm timeline 数量上限(per-frame)。 |
| `filter.lazy_load_members` | query | `boolean` | optional | 是否延迟加载成员。 |
| `filter.include_redundant_members` | query | `boolean` | optional | 是否包含冗余成员状态。 |
| `filter.event_types` | query | `string[]` | optional | 事件类型 allow list。 |
| `filter.not_event_types` | query | `string[]` | optional | 事件类型 deny list。 |

响应 frame 形态(`application/x-ndjson`,每行一个 JSON 对象):

| `kind` | 是否含 `cursor` | 含义 |
| --- | --- | --- |
| `delta` | required | 一次 account-aggregate 增量推送(realms / to_device / account_data / device_lists / presence / notifications)。客户端 MUST 把 `cursor` 作为下次重连的 `after=` 起点。 |
| `catchup_complete` | required | catch-up replay 或 initial baseline 完成,后续 frame 是实时推送。`catchup=true` 才会出现;`catchup=false` 时不会出现。 |
| `frontier` | required | 仅推进 cursor,不带数据;用于服务端在 quiescent 期周期性确认订阅仍连通。 |
| `heartbeat` | absent | 防中间层断流的 keepalive。 |
| `dropped` | required | 服务端无法从当前 cursor 继续推送(buffer 溢出 / 服务重启等),`cursor` 是建议的 account catch-up 起点。客户端 MUST 重新建立 `cx.account.subscribe?after=<cursor>&catchup=true` 重放账号聚合 delta;若重放后的某个 Realm timeline 仍标记 `limited=true`,再用 `cx.events.query` 按该 Realm 的 `prev_cursor` / `next_cursor` 补齐裸 Event 缺口。 |
| `resync_required` | absent | 服务端无法定位任何可用 catch-up 起点(本地状态彻底失效)。客户端 MUST 清空本地 cursor 缓存,从零重新建立订阅。 |
| `unauthorized` | absent | 当前 session 不再有权限消费该流;客户端 MUST 重新认证或退出。 |

frame schema 见 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json)(`cx.schema.account_subscribe_frame.v1`)。

`delta` frame 示例:

```json
{
  "kind": "delta",
  "cursor": "cx:cursor:<opaque-valid-stream-cursor>",
  "realms": {
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

控制 frame 示例:

```text
{"kind": "catchup_complete", "cursor": "cx:cursor:..."}
{"kind": "frontier", "cursor": "cx:cursor:..."}
{"kind": "heartbeat"}
{"kind": "dropped", "cursor": "cx:cursor:..."}
{"kind": "resync_required"}
{"kind": "unauthorized"}
```

`realms.join`、`realms.invite`、`realms.knock` 和 `realms.leave` MUST 是对象;每个对象的 key 是 `cx:realm:*`,value 是该 Realm 的聚合同步结果。`state`、`state_after`、`ephemeral`、Realm-scoped `account_data` 以及顶层 `to_device` / `presence` / `account_data` / `notifications` 都使用事件容器形状:

```json
{
  "events": []
}
```

### 2.2 连接管理与重连

客户端 MUST 维护一个长期存在的 `/account/subscribe` 连接,并:

1. **持久化最近收到的 `cursor`**(任何带 cursor 的 frame 都更新本地高水位)。
2. **网络断开**: 立即用最近 `cursor` 作为 `after=` 重连,并设置 `catchup=true`,确保断线期间的账号聚合 delta 不被跳过。若服务端返回 `cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized`,按 §12.3 恢复。
3. **`dropped` frame**: 用 frame 自带的 `cursor` 重新建立 `GET /account/subscribe?after=<cursor>&catchup=true`,让服务端重放账号聚合 delta。不得只用 `cx.events.query` 恢复,因为 `to_device`、`account_data`、`device_lists`、presence 与 notifications 不属于裸 Realm Event 查询面。
4. **`resync_required` frame**: 清空本地 cursor 缓存,重新建立连接(`after=` 缺省 + `catchup=true`)执行 initial account sync;大型 Realm 的当前态可走 snapshot bootstrap,见 §13。
5. **`unauthorized` frame**: 关闭连接,触发 session 刷新或退出登录。
6. **建议 reconnect 退避**: 指数退避,起始 1s,最大 60s;`dropped` / `resync_required` 后立即重连(不退避)以缩短数据不一致窗口。

## 3. Stream Classes

Account subscribe `delta` frame 包含以下 stream：

| Stream | 持久性 | 用途 |
| --- | --- | --- |
| `timeline` | 持久 | Realm 内 accepted events |
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

`receipts`、`notifications` 和高频 actor-private `read_marker` delta MAY 被服务端合并；同一 scope 在一个 account subscribe frame 内只需要返回最新可见位置和最终 unread count。客户端不得要求服务返回每一次中间 read receipt / marker 变化；`cursor` 只承诺覆盖 frame 中声明的最终 stream positions。

## 4. Realm Buckets

`realms` 按当前 membership 分桶：

- `join`
- `invite`
- `knock`
- `leave`

每个 Realm 响应：

```json
{
  "timeline": {
    "events": [],
    "limited": false,
    "preview_only": false,
    "prev_cursor": "cx:cursor:<opaque-valid-stream-cursor>"
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

服务器 SHOULD 在每个 joined Realm 中返回 `state_after`，表示 `timeline.events` 应用完成后的 state delta。客户端渲染 timeline 中事件时 MUST 使用事件自己 auth state；渲染 timeline 末尾的当前 UI 时 SHOULD 使用 `state_after`。

这避免客户端用新权限、新成员名或新加密 epoch 错误解释先前事件。

### 5.2 State At Window Start (limited timeline 边界状态)

**协议正确性层面**，Contrix 的事件携带 `prev_refs` 与 `refs[role=authorized_by]`，每个事件自带因果与授权 anchor；reducer / projection 在 gap 期间不会误判 authz 或 state convergence。这部分不依赖额外 gap-boundary 信息。

**渲染正确性层面**，当 `timeline.limited=true` 且 window 内可能包含 actor profile 更新、Realm / Flow / Space 元数据变更、或 E2EE epoch rotation 时，客户端按"当前 anchor view"渲染 window 起点事件会显示错误的 display name / Realm/Flow/Space display metadata / 加密 epoch。为此，服务端 MUST 在响应该 Realm timeline 时二选一：

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
- 字段范围仅限三类 anchor：`actor_profiles`（window 内出现的 actor）、`space_metadata`（Realm-level Lattice cell value at window start）、`e2ee_epoch`（window 起点的 MLS epoch hint）。
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

> Rationale: Matrix `/sync` limited timeline 同时返回 state delta；Contrix 的 per-event auth state 已覆盖协议层正确性，但渲染层（display name / Realm or Flow avatar / epoch boundary）仍可能错位。`state_at_window_start` 给服务端实现一条轻量恢复路径，`preview_only` 给无法计算历史 anchor 的实现一条安全回退。

## 6. Event Ordering

Client Sync 的事件顺序是展示顺序和增量恢复顺序，不是授权真相本身。授权真相仍由 event hash、`prev_refs`、`refs[role=authorized_by]`、realm version 和 reducer 决定。

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

## 7. Large Account and Large Realm Sync

数据量巨大时，Client Sync MUST 支持分层同步，而不是一次性拉取全部事件。

推荐策略：

- initial account sync baseline 只返回 Realm 摘要、必要 `required_state` 和有限 timeline。
- 活跃 Realm 优先，低优先级 Realm 只返回 unread / mention / summary。
- 使用 sliding window subscriptions 拉取当前视图需要的 timeline ranges。
- 使用 `timeline.limited=true` 标记缺口，并通过 backfill / pagination 拉取。
- 使用 lazy loading members，避免同步全量成员状态。
- 使用 snapshot manifest 快速恢复当前态，再从 snapshot frontier 拉取增量。
- Blob、附件、缩略图、全文索引和历史密文按需拉取。
- 客户端本地维护 raw event cache、reduced state cache 和 materialized view cache。

服务器 MAY 对响应进行分片：

```json
{
  "cursor": "cx:cursor:<opaque-valid-stream-cursor>",
  "partial": true,
  "priority": "active_view",
  "realms": {}
}
```

客户端 MUST treat `cursor` as the only resume token. 如果某个 Realm 的 timeline 返回 `limited=true`，客户端不得把当前窗口视为完整历史。

## 8. Lazy Loading Members

当 `lazy_load_members=true`：

- 服务器 SHOULD 只返回 timeline 中 sender、被 mention actor、membership changed actor 和 required_state 指定 actor 的 `cx.member.state`。
- 客户端遇到未知 actor 时 MAY 调用 profile/directory API 补全。
- 如果 `include_redundant_members=false`，服务器 SHOULD 避免重复发送客户端已知且未变化的 member state。

## 9. Account Data and Private State

`account_data` 是 principal 或 device 私有状态，不进入 Realm canonical state。标准类型：

标准 Account Data key/pattern 的机器索引是 [`account-data-type-registry.json`](../../artifacts/registry/account-data-type-registry.json)。当前标准集包括：

- `cx.tags.realm.<realm_id>`
- `cx.push_rules`
- `cx.dnd_schedule`
- `cx.collections.stickers`
- `cx.client.ui_state`
- `cx.account.blocklist`
- `cx.contacts.actor.<did>`
- `cx.contacts.realm.<realm_id>`
- `cx.read_receipt.preferences`

Account data MUST 按 principal/device 授权隔离。联邦节点不得向其他 principal 泄露 account data。

## 10. To-Device Delivery

`to_device.events` MUST 只包含当前 access token 对应 device 的消息。

**To-device 投递推断 (normative)**：服务器在收到客户端回传的 `after=<cursor>` 后，**MUST 先按 §12 完整性校验** (MAC/签名 验证 或 stateful handle lookup) 通过，才可将该 cursor 内 `d` (device positions) 之前的 to-device 消息视为已投递并从服务端队列清理。完整性校验失败时 MUST 返回 `cursor_integrity_invalid` 且 **MUST NOT** 推进 to-device 投递状态。客户端如果未处理成功，必须通过本地事务日志恢复。

> Rationale: 若服务端仅按语法 / TTL / purpose 校验就接受客户端 `d` 位置，byzantine 客户端 (或被 XSS / 复制日志泄露后被重放的 cursor) 可篡改 `d` 推进 to-device ack，导致 key verification、cross-signing reset、secret sharing 等 to-device 消息被永久丢弃 — 即使诚实客户端重连也拿不回。

To-device 队列过长时，服务器 MAY 返回 `limited=true` 并要求客户端调用：

```http
GET /api/v1/device_messages?from=<cursor>&limit=...
```

该 endpoint 的 `from` cursor 同样 MUST 通过 §12 完整性校验后才能用于服务端读位置推进。

## 11. Filters

Filter MUST 是服务端可验证 JSON，不得包含任意脚本。服务器 MAY 限制：

- 最大 Realm 数
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

`cursor`（purpose=`barrier`）由写接口在响应中返回（见 [`api-conventions.md` §8](./api-conventions.md)），用于 `X-Contrix-Wait-For` header；它和 stream cursor 共享 wire 形态 `cx:cursor:<base64url>`，由内部 `purpose` 字段区分。客户端不需要分辨，只需把"写响应里的 cursor"作为 wait-for header、把"`/account/subscribe` frame 里的 cursor"作为下次 `after=` 重连参数即可。

### 12.1 Cursor Integrity (normative)

无论 stream 还是 barrier cursor，wire 形态 `cx:cursor:<base64url(canonical_json)>` 都 **MUST** 是服务端可验证的同步位置；服务端 **MUST NOT** 仅按语法 / TTL / purpose 校验就把客户端回传的 cursor 当作"可信位置"用于推进 to-device ack、`/account/subscribe` `after=` resume 起点、`X-Contrix-Wait-For` barrier 解除、`dropped` / `resync_required` 恢复或其他不可逆 server-side state。

实现 MUST 选择以下两种 cursor 形态之一（互斥，由 schema `oneOf` 强制）；两种形态都满足"服务端可验证"的安全契约：

**(A) Stateless self-describing cursor**：canonical body 内含 `s` / `d` / `target` 等结构化状态字段，**MUST** 携带 `_mac` 或 `_sig` 中的至少一个：

- `_mac`：HMAC over canonical bytes (除 `_mac` 自身外的所有字段)，密钥由 issuing service 持有，算法 MUST 是 HMAC-SHA-256 或更强。
- `_sig`：detached signature over same canonical bytes，密钥使用 issuing service 的 cursor-signing key。
- transcript MUST 绑定：`purpose`、principal id、device id、service DID / service id、filter hash、stream positions（`s` / `d`）、`target`（barrier 时）、`x`、issuer key id。

**(B) Stateful opaque handle cursor**：canonical body 缩为 `{v, purpose, t, x, h}`，无 `s` / `d` / `target`；`h` 是 issuing service 生成的不可猜测 handle（解码后熵 ≥ 128 bit），service 内部维护 handle → `(principal, device, service, filter_hash, purpose, positions, target?, expiry)` 映射。Handle 校验本身就是完整性校验 — 不可加 `_mac` / `_sig`。这是 Matrix `next_batch` / MSC4186 `pos` 的等价形式，适合不想引入 MAC/签名密钥管理的实现。

### 12.2 校验流程 (normative)

任何 endpoint 在使用客户端回传的 cursor 推进 server-side state 之前，MUST 执行：

1. 解析 `cx:cursor:<base64url>` 并按 `cursor.schema.json` 校验语法、`purpose`、TTL (`x` 未过期)。语法/参数失败映射顶层 `invalid_param`（reason `invalid_cursor`）；TTL 失败映射 `cursor_expired`。
2. **完整性校验**:
   - 若 body 含 `h`：以 `h` 查 issuing service 本地表，校验 handle 存在、未过期、未撤销，且绑定的 `(principal, device, service, filter_hash, purpose)` 与当前 authenticated request 匹配。
   - 若 body 含 `_mac` / `_sig`：以 issuing service 的当前 cursor key (按 `issuer_kid` 选取) 校验 MAC/signature；transcript 必须重算一致，且绑定字段与当前 authenticated request 匹配。
3. 任一校验失败 → 返回 `cursor_integrity_invalid`，**MUST NOT** 推进任何 server-side state。
4. 校验通过后才可读 cursor 内部 `s` / `d` / `target`（stateless 形态）或 handle 解析出的 positions（stateful 形态），并用于推进同步状态。

`cursor_integrity_invalid` 与 `cursor_expired` 语义不同：前者是 tamper / 未知 handle / cross-binding，后者是 TTL 超时。客户端对 `cursor_integrity_invalid` 的恢复路径与 `cursor_expired` 一致（重做 initial sync），但客户端 SHOULD 把它视为本端 cursor 状态被污染的信号，清理本地 cursor 缓存。

### 12.2.1 Cursor Revoke（high-assurance optional）

声明 high-assurance cursor revoke capability（ServiceDescribe `supported_features[]` 含 `cursor_revoke_high_assurance`）的服务 MUST 支持主动撤销 cursor：

```text
POST /api/v1/account/cursor/revoke
```

请求体至少包含 `{cursor, reason_code, revoke_scope}`；`revoke_scope` 取值为 `this_cursor` / `same_device` / `same_session`。

`revoke_scope` 范围的 normative 定义（与 [`identity/account-lifecycle.md`](../identity/account-lifecycle.md) 中的 session/device 标识对齐）：

- session 抽象为 `(principal_id, device_id, issued_at, session_id)` 四元组，由签发 cursor 的服务在派发时记录在 cursor signing material 或 cursor revocation set 元数据中。
- `this_cursor`：仅撤销当前提交的 cursor 本体（按 `_mac` / `_sig` digest 或 stateful handle 匹配）。
- `same_session`：撤销与当前 cursor 同 `(principal_id, device_id, issued_at, session_id)` 的所有未过期 cursor（含同会话内派发的派生 cursor）。
- `same_device`：撤销与当前 cursor 同 `(principal_id, device_id)` 的所有未过期 cursor（跨会话）。
- 当 cursor 来自浏览器或其它无稳定 `device_id` 的环境时，`same_device` MUST 在效果上退化为 `this_cursor`（服务端不得猜测设备同一性），并在响应 `revoke_scope_effective="this_cursor"` 中显式回执，以避免客户端误以为全设备已撤销。

服务端接受后 MUST 将对应 stateless cursor 的 `_mac` / `_sig` digest 或 stateful handle 写入 cursor revocation set，保留时间不少于该服务声明的最长 cursor TTL（stream cursor 默认 7 天，barrier cursor 1 小时）。撤销命中时，任何 endpoint MUST 返回 `cursor_revoked`，并且不得推进 to-device ack、subscription position、barrier wait 或 dropped recovery state。

Cursor revoke 不能替代 cursor integrity：服务端仍必须先做 §12.2 完整性校验；完整性失败返回 `cursor_integrity_invalid`，不泄露该 cursor 是否曾被 revoke。

### 12.3 过期或缺口恢复流程

1. 客户端保留本地 `cursor`、filter hash、未确认写入和最后可验证 frontier。
2. 收到 `cursor_expired` / `cursor_integrity_invalid` / `stale_frontier` 后，先调用 `account/describe` 或 `snapshot/head` 获取当前 frontier 与推荐 snapshot。
3. 若 snapshot 可用，客户端 MUST 验证签名、签名者授权、state hash、frontier 和 chunk digest 后再采用。
4. 从 snapshot frontier 或服务返回的 backfill 起点执行 `cx.events.query`（`GET /events?after=<cursor>`），补齐 Realm Event 缺口;账号聚合缺口则重新建立 `cx.account.subscribe?after=<cursor>&catchup=true` 重放。
5. 若 snapshot 校验失败，客户端 MUST 回退到 Event history replay 或 Event-only backfill，并可将来源标记为 degraded。

## 13. Initial Sync

Initial sync 的账号入口是:

```http
GET /api/v1/account/subscribe?catchup=true
Accept: application/x-ndjson
```

也就是不带 `after`,并显式请求 `catchup=true`。服务器 MUST 先发送至少一个 `delta` frame 作为账号 baseline,再发送 `catchup_complete`,然后继续保持连接进入实时推送。Baseline 不是完整历史记录；它只覆盖客户端首屏与账号状态恢复所需的当前视图。Baseline `delta` SHOULD：

- 返回用户当前 joined/invited/knocked Realms 的摘要。
- 对活跃 Realm 返回有限 timeline。
- 返回足够 `required_state` 让客户端首屏可渲染。
- 返回 device list delta 的完整 baseline。

大型账户 MAY 使用 sliding window subscriptions，避免一次性返回所有 Realm。

## 14. E2EE Requirements

E2EE client 在处理 encrypted event 前 MUST：

- 检查 `device_lists` 是否有变更。
- 检查 Realm encryption epoch。
- 拉取缺失 KeyPackage / group secret。
- 对无法解密事件记录 `decryption_pending`，不得静默丢弃。

服务器 MUST NOT 因无法解密而过滤 encrypted event。

## 15. E2EE and MLS Sync Performance

E2EE Realm 的同步必须把“事件顺序”和“密钥可用性”分开处理。事件可以先进入本地 raw event cache；解密可以异步完成。

客户端处理加密 timeline 时 SHOULD：

1. 先验证 event envelope、hash、signature、`realm_id`、`refs[role=authorized_by]` 和 `prev_refs`。
2. 根据明文 routing metadata 将事件放入 timeline / reducer 队列。
3. 检查事件声明的 `mls_epoch`。
4. 如果本地缺少该 epoch 的 group state，拉取缺失 `cx.mls.*` state event、MLS Commit 和必要 key backup。
5. 如果仍无法解密，将事件标记为 `decryption_pending`，但保留排序位置和引用关系。
6. 当 MLS epoch 补齐后，异步重试解密并更新 materialized view。

服务器和 Sync Service 不需要解密正文，也不得因为无法解密而改变事件顺序或过滤事件。

为降低大规模 E2EE 同步成本：

- 当加密 timeline 中包含未知 epoch 的事件时，MLS epoch state SHOULD 作为 required state 返回。
- 客户端 SHOULD 按 `(realm_id, epoch)` 缓存 epoch state 与 ratchet tree。
- 历史 backfill SHOULD 把加密 payload 与 MLS epoch 材料分成不同的范围请求。
- 新设备恢复 SHOULD 优先使用加密密钥备份 / secret storage，而非向其他成员逐条重发历史密钥。
- 加密附件 SHOULD 通过 blob ref 与 content hash 进行懒加载。
- 服务端全文搜索 MUST NOT 要求 plaintext；加密 Realm 的搜索应使用本地索引或受控的 TEE profile。

如果密钥状态与事件状态出现缺口：

- 缺事件依赖：event MUST remain soft failed until backfill resolves it.
- 缺 MLS epoch：event MAY be accepted as encrypted event but displayed as `decryption_pending`.
- epoch 明确已被移除成员不可访问：客户端 MUST fail closed and not request keys from unauthorized members.

### 15.1 `decryption_pending` timeout and recovery

客户端首次把某事件标记为 `decryption_pending` 时 MUST 记录 `first_pending_at`、缺失的 `(realm_id, flow_id?, track?, group_id, epoch)`、已尝试的恢复 source 和最近一次错误。默认 `decryption_pending_timeout` 为 7 天；Realm policy 或实现 profile MAY 声明更短值，高保障 profile SHOULD 更短，但不得无限期保持无诊断 pending。

在 timeout 前，客户端 SHOULD 按以下顺序恢复：

1. 拉取缺失的 `cx.mls.*` state event、winner `cx.mls.commit`、Welcome 和 `governance_binding` 依赖。
2. 查询本 actor 授权设备的 encrypted key backup / secret storage。
3. 在 history sharing policy 允许时，请求当前授权 peer 对指定 epoch range 发送 key share。
4. 若 Realm policy 声明 Archive Node / Audit Node / Key Recovery Service，可向该受托服务请求最小 epoch range。

当连续 epoch 缺口超过 `epoch_gap_recovery_threshold`（默认 32 个 epoch）或本地 backfill 预算耗尽时，客户端 SHOULD 切换到 range-based recovery：按 epoch 区间请求 key material、MLS Commit chain 和必要 snapshot proof，而不是逐消息重试。任何 key share 都必须绑定接收 principal、device、epoch range、policy hash 和发送设备签名；不得向已被移除、未授权或无法验证的成员请求密钥。

超过 `decryption_pending_timeout` 后，客户端 MUST 将用户可见投影标记为 `decryption_failed`，保留 metadata-only 占位、排序位置、引用关系和重试诊断，并向用户显示不可解密状态。若之后合法 key material 到达，客户端 MAY 重新解密并把状态从 `decryption_failed` 恢复为 verified content，但该 MAY 受 [`encryption-and-audit.md` §2.3.5](../crypto-media/encryption-and-audit.md) late key recovery 状态机约束：必须通过原始接收时刻 T0 的 membership / history / key scope 校验，UI 必须显示 late recovery timeline marker；audit profile 下必须先 emit `cx.audit.accessed` 并取得 RYW receipt 后才可显示明文。恢复审计记录必须保留，不得静默替换原 metadata-only 占位。
