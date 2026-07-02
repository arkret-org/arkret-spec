---
title: Client Sync
status: candidate
normative: true
stability: v1
updated: 2026-07-03
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Client Sync 是客户端 **账号视角聚合** 同步协议。它在 Events API 之上提供跨 Realm 的稳定 delta 视图（包含 to_device、account_data、device_lists、presence、unread / notification counts），由服务端按需推送或以有界长轮询返回。它不是裸事件读取——逐 Realm 的事件查询和实时订阅请使用 `ck.self.events.query.scan` / `ck.self.events.stream.subscribe`。

`ck.self.account.stream.subscribe` 与 `ck.self.events.stream.subscribe` 是对称的两类 streaming 订阅:
- `ck.self.events.stream.subscribe` 是**逐 Realm / actor 的事件流**(selector 范围内的每条 Event)
- `ck.self.account.stream.subscribe` 是**账号视角的聚合流**(跨所有 Realm 的 delta 总览 + account-scoped 数据)

两者共享相同的 stream cursor 形态、resume / `dropped` / `resync_required` 恢复语义，差异仅在 selector 与 frame 内容。

本文定义 Cokret v1 的客户端账号同步语义，不表示存在 `sync v1` / `sync v2` 两个协议版本。版本演进应由 transport binding 路径、feature discovery 和 conformance profile 表达。

所有 full client 和 E2EE client MUST 支持本文件。

## 2. Endpoint

```http
GET /_cokret/self/account/subscribe?catchup=true
Authorization: Bearer <ck.session.grant>
Accept: application/json
```

上面是 **initial account sync** 的 canonical 长轮询调用：不带 `after`，显式设置 `catchup=true`。这里的 `catchup` 不是"返回全部历史记录"，而是要求服务端返回当前账号 baseline（有限 timeline + 必要 state + account-scoped 当前位置）。常规网络重连使用 `GET /_cokret/self/account/subscribe?after=<cursor>&catchup=true` 补齐断线期间的账号 delta；收到 `dropped` frame 后的补洞重连同样使用 `GET /_cokret/self/account/subscribe?after=<cursor>&catchup=true`。

该端点对应 `ck.self.account.stream.subscribe`，HTTP binding 支持两种响应编码：

- `Accept: application/json`：推荐给浏览器和普通客户端的有界长轮询形态。响应体是单个 `SyncOutcome` JSON 对象；当 `after` 存在且没有新 delta 时，服务端 MAY 等待到 `max_wait_ms` / 部署默认窗口后返回空 delta。JSON 响应关闭连接，不发送 `catchup_complete` 行。**cursor 失效返回（normative）**：JSON 形态下 `after` cursor 失效（`cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized` / `stale_frontier`）MUST 以 §5 标准错误 envelope 返回（HTTP 4xx + 对应 error code），而非 NDJSON 的 `dropped` / `resync_required` frame；客户端据此按 §12.3 分支恢复（重新 baseline / backfill）。
- `Accept: application/x-ndjson`：长连接 frame stream 形态。响应体是 `AccountSubscribeFrame` NDJSON；`catchup=true` 时 baseline / catch-up delta 后发送 `catchup_complete`，然后可继续进入实时推送。

两种编码使用相同的 query 参数、cursor、授权与 delta 语义；客户端 MUST 同时把 `SyncOutcome.cursor` 或 cursor-bearing frame 的 `cursor` 作为下一次 `after=` 起点。该端点聚合跨 Realm delta、to_device、account_data、device_lists、presence；不同于 `GET /_cokret/self/events/subscribe`(按 selector 的事件流订阅)和 `GET /_cokret/self/events?before=...` / `?after=...`(按 selector 的双向历史查询)。三者可以共享 cursor 与授权规则，但 `operation_id`、响应语义与所属 namespace 不同：account 同步在 `ck.self.account.*`，snapshot 入口在 `ck.self.snapshot.*`，事件读取在 `ck.self.events.*`（权威 operation namespace 以 [`../../artifacts/registry/operation-registry.json`](../../artifacts/registry/operation-registry.json) 为准，canonical 均带 `ck.self.*` 信任面前缀；`ck.account.*` / `ck.snapshot.*` / `ck.events.*` 只是 surface-group 口语简称，不是 wire operation_id）。

Account subscribe 的服务边界是当前 authenticated session 绑定的 Principal Server service DID。若同一 principal DID 同时在个人 Principal Server 与组织 Principal Server 上有账号/设备上下文，客户端必须分别维护 session、cursor、to-device queue 和 push registration,并对每个上下文建立独立的 `/_cokret/self/account/subscribe` 长连接。某个 Realm 的 timeline / notification delta 只应出现在该成员 effective `delivery_binding.recipient_service_did` 指向的服务上;DID Document 中的默认 Principal Server 不得把其它 Realm-scoped delivery binding 的 delta 聚合进自己的 `/_cokret/self/account/subscribe` 流。

### 2.1 Delivery Binding UX 指引（SHOULD）

`delivery_binding` 由 schema 强制存在并显式化，但**用户感知**应保持轻量。客户端 UI SHOULD：

1. **默认不暴露 `delivery_binding` 字段**。普通邀请 / 成员添加 / 加入 Realm 流程中，UI **不展示** `recipient_service_did` 选择控件，除非：
   - 邀请方处于多 Principal Server 登录上下文且没有可推断的默认值（fall back to `explicit`，要求用户选择）；
   - Realm policy 强制 `binding_source ∈ {explicit}` 且邀请方未在该上下文登录（提示用户切换上下文或退出邀请）；
   - 用户主动进入"高级 / 投递设置"面板查看 / 修改。
2. **成员列表展示绑定上下文**。当某 Realm 内成员的 `delivery_binding.recipient_service_did` 不属于该 actor DID Document 默认 `CokretPrincipalServer` 时，UI SHOULD 在该成员条目附近显示其 binding 上下文（例如 `Bob @ Acme`、`Carol @ Beta`）；当属于默认时 SHOULD 仅显示 actor，不显示 binding。展示形态可使用组织 endorsement 的 `display_name` / `logo` 而不是 raw service DID。
3. **邀请 strand 智能默认**。客户端 SHOULD 按当前邀请方上下文自动提议 binding：
   - 默认使用 [`invite-addressing.md`](./invite-addressing.md) 的 online principal locator 或显式 `subject_id + recipient_service_did` 输入；locator/ref 成功后 UI 显示 `Alice @ Acme` 这类上下文标签，不展示 raw service DID；
   - 用户输入 `@alice:acme.example` / `alice@acme.example` 时，只有在 Directory / Organization 明确支持可选 handle invite/member_add profile 且调用方具备披露授权时，才 MAY 调用 `ck.find.directory.query.resolve_handle(intent="member_add" | "invite")` 获取可验证 candidate；失败时 MUST 回到 locator/address 模式，不得本地合成 remote service DID；
   - 邀请方在 Org-A 内部 Realm 中邀请 → 默认 invitee 也走 Org-A binding（如果 Org-A organization registry 把 invitee 列为成员）；
   - 邀请方在个人 Realm 中邀请 → 默认 invitee DID Document `did_document_default`（若 Realm policy 允许）；
   - 多上下文 invitee + 无明确默认 → 提示用户在已知上下文中选择，**不要静默选择**。
4. **跨上下文切换感知**。客户端在同一 UI 中聚合显示多 Principal Server 的 timeline 时 SHOULD 显式区分上下文（如标签栏 / 子账号面板），避免把工作 / 个人事件混合渲染。聚合通知（badge count / push）按上下文分桶；不允许跨上下文合并未读数。

这些是 SHOULD，不构成 wire 互操作的硬约束；但符合 `ck.profile.full_client.v1` / `ck.profile.e2ee_client.v1` 的实现 SHOULD 在 UX self-check 中覆盖。

请求参数(query string,无 body):

| 参数 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前 principal / device。 |
| `after` | query | `cursor` | optional | 订阅起点 cursor(purpose=`stream`,排除语义),从此 cursor *之后* 开始接收 frame。缺省表示没有可恢复账号 cursor。 |
| `catchup` | query | `boolean` | optional | 默认 `false`。`after` 存在时,`true` 表示服务端先回放 `after=` 之后到当前 frontier 的账号聚合 delta,再发 `catchup_complete` frame,然后切到实时尾部；这不是全量历史。`after` 缺省且 `catchup=true` 是 **initial account sync**:服务端 MUST 先发送覆盖当前账号 baseline 的 `delta` frame(Realm 摘要、必要首屏 state、device list baseline、to_device/account_data/notification 当前位置),再发送 `catchup_complete`。完整历史必须通过 `ck.self.events.query.scan` 分页/区间读取。 |
| `filter` | query (deepObject) | `object` | optional | 过滤条件。语义同 self.events.stream.subscribe。 |
| `filter.realms` | query | `id[]` | optional | 限制返回 Realm。 |
| `filter.timeline_limit` | query | `int` | optional | 每个 Realm timeline 数量上限(per-frame)。 |
| `filter.lazy_load_members` | query | `boolean` | optional | 是否延迟加载成员。 |
| `filter.include_redundant_members` | query | `boolean` | optional | 是否包含冗余成员状态。 |
| `filter.event_types` | query | `string[]` | optional | 事件类型 allow list。 |
| `filter.not_event_types` | query | `string[]` | optional | 事件类型 deny list。 |

Presence 变更不是 account subscribe 的 query 参数。客户端要广播 `online` / `idle` / `dnd` / `offline`（closed set，见 [profiles-presence.md §3.2](../discovery/profiles-presence.md)）presence 状态时，MUST 通过 `POST /_cokret/self/ephemeral` 提交 `ck.presence` ephemeral envelope，并按该 operation 执行 `ck.presence.broadcast` 授权、TTL、幂等和日志最小披露规则。`GET /_cokret/self/account/subscribe` MUST 保持只读：建立、恢复或重放订阅不得触发 presence 广播或其它 server-side mutation。

NDJSON 响应 frame 形态(`application/x-ndjson`,每行一个 JSON 对象):

| `kind` | 是否含 `cursor` | 含义 |
| --- | --- | --- |
| `delta` | required | 一次 account-aggregate 增量推送(realms / to_device / account_data / device_lists / presence / notifications)。客户端 MUST 把 `cursor` 作为下次重连的 `after=` 起点。 |
| `catchup_complete` | required | catch-up replay 或 initial baseline 完成，后续 frame 是实时推送。`catchup=true` 才会出现;`catchup=false` 时不会出现。 |
| `frontier` | required | 仅推进 cursor,不带数据；用于服务端在 quiescent 期周期性确认订阅仍连通。 |
| `heartbeat` | absent | 防中间层断流的 keepalive。 |
| `dropped` | required | 服务端无法从当前 cursor 继续推送(buffer 溢出 / 服务重启等),`cursor` 是建议的 account catch-up 起点。`dropped` frame 的 `cursor` 为 REQUIRED;服务端没有可用补齐 cursor 时 MUST 改发 `resync_required`,不得发送无 cursor 的 `dropped`。客户端 MUST 重新建立 `ck.self.account.stream.subscribe?after=<cursor>&catchup=true` 重放账号聚合 delta;若重放后的某个 Realm timeline 仍标记 `limited=true`,再用 `ck.self.events.query.scan` 按该 Realm 的 `prev_cursor` / `next_cursor` 补齐裸 Event 缺口。MAY 携带 `reconnect_after_ms`。 |
| `resync_required` | absent | 服务端无法定位任何可用 catch-up 起点(本地状态彻底失效)。客户端 MUST 清空本地 cursor 缓存，从零重新建立订阅。MAY 携带 `reconnect_after_ms`。 |
| `unauthorized` | absent | 当前 session 不再有权限消费该流；客户端 MUST 重新认证或退出。 |

frame schema 见 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json)(`ck.schema.account_subscribe_frame.v1`)。

> **与 `ck.self.events.stream.subscribe` 帧集合的差异**：account-aggregate 流**有意不**包含 `ck.self.events.stream.subscribe` 的 `event` 与 `epoch_rotation` 控制帧。self.account.stream.subscribe 是跨 Realm 聚合视角，MLS epoch 变化不作为独立控制帧出现，而是在各 Realm `delta` 内通过 `state_after` / `state_at_window_start.e2ee_epoch`（见 §5）表达；需要逐 Realm 的 `epoch_rotation` 边界提示时使用 `ck.self.events.stream.subscribe`。其余控制帧（`catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`）与 `ck.self.events.stream.subscribe` 对齐。

`delta` frame 示例:

```json
{
  "kind": "delta",
  "cursor": "ck:cursor:<opaque-valid-stream-cursor>",
  "realms": {
    "ck:realm:0196419b-0000-7000-8000-000000000000": {
      "timeline": {
        "events": [],
        "limited": false
      },
      "state": {"events": []},
      "account_data": {"events": []}
    }
  },
  "to_device": {"messages": []},
  "device_lists": {"changed": [], "left": []},
  "account_data": {"events": []},
  "presence": {"events": []},
  "notifications": {"events": []}
}
```

控制 frame 示例:

```text
{"kind": "catchup_complete", "cursor": "ck:cursor:..."}
{"kind": "frontier", "cursor": "ck:cursor:..."}
{"kind": "heartbeat"}
{"kind": "dropped", "cursor": "ck:cursor:...", "reconnect_after_ms": 5000}
{"kind": "resync_required", "reconnect_after_ms": 10000}
{"kind": "unauthorized"}
```

`realms` MUST 是以 `ck:realm:*` 为 key 的对象；value 是该 Realm 的聚合同步结果。membership state 的完整枚举是 `join` / `invite` / `knock` / `leave` / `ban`，它们是事件 payload / `ck.member.state` projection 取值，不再作为 `realms` 外层 bucket；其中只有 `join` / `invite` / `knock` 进入 roster（`members[]`），`leave` / `ban` 不进入 roster（见 §中 roster `members[]` 定义）。`state`、`state_after`、`ephemeral`、Realm-scoped `account_data` 以及顶层 `presence` / `account_data` / `notifications` 都使用事件容器形状:

```json
{
  "events": []
}
```

顶层 `to_device` 不是事件容器；它使用 `DeviceMessageEnvelope[]` 承载形态 `{messages, ack_token?, limited?, next_cursor?, lost?}`，schema 为 `account-subscribe-frame.schema.json#/$defs/device_message_container`。`messages[]` 中的对象不得作为 durable Event Envelope 处理。

### 2.2 连接管理与重连

客户端 MUST 维护一个长期存在的 `/_cokret/self/account/subscribe` 连接，并:

1. **原子持久化 frame 与 cursor**: 客户端 MUST 在同一本地事务中持久化 frame payload(timeline 事件、state、account_data、device_lists 等)与该 frame 的 `cursor`,之后才把它用作重连 `after=` 起点;MUST NOT 在 payload 落盘前单独推进本地 cursor 高水位。"先存 cursor、后落数据"的实现会在崩溃时产生本地静默缺口——其中 `device_lists` 缺口只能靠重做 initial sync 恢复。to-device 消息的投递安全由 §10.1 显式 ack 在协议层保证，不依赖本条；但 SHOULD 同样与 cursor 同事务落盘以减少重连后的重复处理。仅带 cursor 不带数据的 frame(`frontier` / `catchup_complete`)直接更新本地高水位即可。
2. **网络断开**: 若没有服务端 `reconnect_after_ms` 或 HTTP `Retry-After` 指令，立即用最近 `cursor` 作为 `after=` 重连，并设置 `catchup=true`,确保断线期间的账号聚合 delta 不被跳过。若服务端返回 `cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized`,按 §12.3 恢复。
3. **`dropped` frame**: 用 frame 自带的 `cursor` 重新建立 `GET /_cokret/self/account/subscribe?after=<cursor>&catchup=true`,让服务端重放账号聚合 delta；若 frame 携带 `reconnect_after_ms`,MUST 先等待该时长。不得只用 `ck.self.events.query.scan` 恢复，因为 `to_device`、`account_data`、`device_lists`、presence 与 notifications 不属于裸 Realm Event 查询面。
4. **`resync_required` frame**: 清空本地 cursor 缓存，重新建立连接(`after=` 缺省 + `catchup=true`)执行 initial account sync;若 frame 携带 `reconnect_after_ms`,MUST 先等待该时长。大型 Realm 的当前态可走 snapshot bootstrap,见 §12.3 与 §13。
5. **`unauthorized` frame**: 关闭连接，触发 session 刷新或退出登录。
6. **建议 reconnect 退避**: 指数退避，起始 1s,最大 60s;`dropped` / `resync_required` 未携带 `reconnect_after_ms` 时可立即重连以缩短数据不一致窗口。客户端收到 `reconnect_after_ms`、HTTP `Retry-After` 或错误 body `retry_after_ms` 时，MUST 优先遵守服务端指令，并 SHOULD 加 jitter 避免同批客户端同步重连。

`reconnect_after_ms` 是 200 stream control frame 内的重连保持时间，不是错误响应字段。服务端发送后 MUST 按至少 `(principal_id, device_id, operation_id, filter_digest)` 维度强制执行；在保持时间内的同 scope `/_cokret/self/account/subscribe` 请求 MUST 返回 `429 rate_limited` 并设置 `Retry-After`，且不得推进 account subscribe position、barrier wait 或 dropped recovery state（to-device 队列删除只由 §10.1 显式 ack 驱动，本就与 subscribe cursor 无关）。服务端 MAY 在实现中加入 source IP / session id / trust domain 等更细维度，但不得把该限制扩大到无关 API。

## 3. Stream Classes

Account subscribe `delta` frame 包含以下 stream：

| Stream | 持久性 | 用途 |
| --- | --- | --- |
| `timeline` | 持久 | Realm 内 accepted events |
| `state` | 持久 | 当前 state event delta |
| `state_after` | 派生 | timeline 末尾之后的状态，用于正确解释事件 |
| `state_at_window_start` | 派生 | `timeline.limited=true` 时 window 起点 seal 状态，见 §5 |
| `account_data` | 私有持久 | 标签、UI 偏好、recent emoji、push rules |
| `to_device` | 设备队列 | key verification、secret sharing、device messages（队列删除只由 §10.1 显式 ack 驱动，不随 cursor 推进） |
| `ephemeral` | 短暂 | typing、presence、live cursor |
| `receipts` | 可配置 | read receipt / read cursor delta（逻辑类，无独立 wire 字段；承载于 per-Realm `ephemeral` / `account_data`，见下表） |
| `notifications` | 派生 | inbox / push notification delta |
| `device_lists` | 持久 delta | E2EE device trust 更新 |
| `applet` | 持久/短暂 | Applet delivery receipt、bridge health（逻辑类，无独立 wire 字段；承载于 per-Realm `timeline` / `ephemeral`，见下表） |
| `blob_status` | 派生 | upload scan、thumbnail、retention 状态（逻辑类，无独立 wire 字段；承载于 per-Realm `timeline`，见下表） |

客户端 MUST 使用 `cursor` 作为唯一 resume token，不得解析 token 内部结构。

**各 stream class 在 frame 中的承载位置**（与 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json) 对齐）：

| Stream | 承载位置 |
| --- | --- |
| `timeline` / `state` / `state_after` / `state_at_window_start` / `ephemeral` | per-Realm：`delta.realms[<realm_id>]` 内的同名字段（§4） |
| `to_device` / `device_lists` | `delta` 顶层同名字段（跨 Realm，不分桶到具体 Realm） |
| `account_data` | 双位置：Realm-scoped 私有数据进 `delta.realms[<realm_id>].account_data`；account-scoped 进 `delta` 顶层 `account_data` |
| `presence` | `delta` 顶层同名字段（跨 Realm，不分桶到具体 Realm） |
| `receipts` | per-Realm：read receipt / read cursor delta 随对应 Realm 投递，承载于 `delta.realms[<realm_id>].ephemeral`（read receipt 临时位）与 `account_data`（actor-private `read_cursor` 高水位）；服务端 MAY 按下文合并 |
| `notifications` | `delta` 顶层 `notifications`；per-Realm 未读计数另由 `delta.realms[<realm_id>].unread_notifications` 表达（§4） |
| `applet` | per-Realm 派生：Applet delivery receipt / bridge health 作为对应 Realm 的事件随 `delta.realms[<realm_id>].timeline` / `ephemeral` 投递 |
| `blob_status` | per-Realm 派生：upload scan / thumbnail / retention 状态作为对应 Realm 的派生事件随 `delta.realms[<realm_id>].timeline` 投递 |

顶层 `delta` 与 per-Realm entry 的对象 schema 均允许 `additionalProperties:true` 以容纳这些 stream class 的承载字段；上表给出 v1 canonical 承载位置，实现不得自行另设外层分桶。`receipts` / `applet` / `blob_status` 不在顶层 `delta` 另立独立 bucket。

`receipts`、`notifications` 和高频 actor-private `read_cursor` delta MAY 被服务端合并；同一 scope 在一个 account subscribe frame 内只需要返回最新可见位置和最终 unread count。客户端不得要求服务返回每一次中间 read receipt / marker 变化；`cursor` 只承诺覆盖 frame 中声明的最终 stream positions。

## 4. Realm Buckets

`realms` 不按 membership 做外层分桶；它始终以 `ck:realm:*` 为 key。当前 membership 是每个 Realm bucket 内的状态字段 / `ck.member.state` projection，取值可为 `join`、`invite`、`knock`、`leave` 或 `ban`（完整枚举见 §2 首次定义），不得把这些值提升为 `realms` 的外层 key。

每个 Realm 响应：

```json
{
  "timeline": {
    "events": [],
    "limited": false,
    "preview_only": false,
    "prev_cursor": "ck:cursor:<opaque-valid-stream-cursor>"
  },
  "state": {"events": []},
  "state_after": {"events": []},
  "state_at_window_start": {
    "actor_profiles": {},
    "realm_metadata": {},
    "e2ee_epoch": null
  },
  "ephemeral": {"events": []},
  "account_data": {"events": []},
  "summary": {
    "joined_member_count": 12,
    "invited_member_count": 1,
    "heroes": ["did:webvh:..."]
  },
  "members": [],
  "members_limited": true,
  "members_next_cursor": "ck:cursor:<opaque-valid-stream-cursor>",
  "unread_notifications": {
    "notification_count": 3,
    "highlight_count": 1
  }
}
```

如果 `timeline.limited=true`，客户端 MUST 使用 backfill / pagination 拉取缺口，不得假设 timeline 连续。服务端 SHOULD 在响应中提供 `prev_cursor`、顶层 `cursor`、`snapshot_frontier` 或等价恢复提示；若缺口无法用当前 cursor 恢复，必须返回 `cursor_expired`、`cursor_integrity_invalid`、`stale_frontier` 或 `temporarily_unavailable`，不得静默退化为不完整状态。这些返回触发的恢复分支不同，客户端 MUST 区分处理：

- `cursor_expired` / `cursor_integrity_invalid`：cursor 本端状态失效（TTL 超时或 tamper / 未知 handle / cross-binding）。客户端 MUST 清空本地 cursor 缓存并从 initial sync 重做（重新建立 `ck.self.account.stream.subscribe`，`after=` 缺省 + `catchup=true`），与 §12.3 一致；不能用旧 cursor 继续 backfill。
- `stale_frontier`：cursor 本身仍有效，只是服务 frontier 落后于请求所需 causal frontier。客户端 MUST NOT 清 cursor 重做 initial sync，而是按 §12.3 等待 / backfill——先以 `account/describe` 或 `snapshot/head` 取当前 frontier，再从该 frontier 起点用现有 cursor backfill 补齐缺口。
- `temporarily_unavailable`：可重试瞬态；按 `retry_after_ms` / `Retry-After` 退避后用同一 cursor 重试。

`timeline.limited=true` 时，服务端 MUST 二选一返回 `state_at_window_start`（projection-only seal 状态）或标记 `timeline.preview_only=true`；详见 §5.2。

## 5. State After 与 State At Window Start

### 5.1 State After (timeline 末尾状态)

服务器 SHOULD 在每个 joined Realm 中返回 `state_after`，表示 `timeline.events` 应用完成后的 state delta。客户端渲染 timeline 中事件时 MUST 使用事件自己 auth state；渲染 timeline 末尾的当前 UI 时 SHOULD 使用 `state_after`。

这避免客户端用新权限、新成员名或新加密 epoch 错误解释先前事件。

### 5.2 State At Window Start (limited timeline 边界状态)

**协议正确性层面**，Cokret 的事件携带 `prev_refs` 与 `refs[role=authorized_by]`，每个事件自带因果与授权 seal；reducer / projection 在 gap 期间不会误判 authz 或 state convergence。这部分不依赖额外 gap-boundary 信息。

**渲染正确性层面**，当 `timeline.limited=true` 且 window 内可能包含 actor profile 更新、Realm / Strand / Space 元数据变更、或 E2EE epoch rotation 时，客户端按"当前 seal view"渲染 window 起点事件会显示错误的 display name / Realm/Strand/Space display metadata / 加密 epoch。为此，服务端 MUST 在响应该 Realm timeline 时二选一：

**(a) 返回 `state_at_window_start`** (推荐路径，projection-only)：

```json
{
  "timeline": {
    "events": [],
    "limited": true,
    "prev_cursor": "ck:cursor:..."
  },
  "state_at_window_start": {
    "actor_profiles": {"did:webvh:...": {"display_name": "...", "avatar_blob_ref": "..."}},
    "realm_metadata": {"title": "...", "summary": "...", "join_rule": "..."},
    "e2ee_epoch": {"epoch": 17, "key_ref": "ck:mls:..."}
  }
}
```

- 该字段是 **派生 projection-only 字段**，不参与 state hash / frontier 计算，不进入因果图。
- 字段范围仅限三类 context：`actor_profiles`（window 内出现的 actor）、`realm_metadata`（Realm-level Lattice cell value at window start）、`e2ee_epoch`（window 起点的 MLS epoch hint）。
- 客户端 SHOULD 在渲染 window 内事件时优先用 `state_at_window_start` 而非"当前查询 basis"。
- 服务端可以沿 Seal DAG 回溯控制面 basis，并按 DataEvent 因果闭包或观察性 `data_event_set_root` 定位 window 起点，再按各 Lattice 的 deterministic join 取 cell value 派生该状态；不可用时退路径 (b)。HLC 只能作为定位候选历史 view 的非权威索引 hint，MUST NOT 作为 cell value 选择键或状态判断依据。
- **单一 canonical 定位规则（normative）**：上一条提到 window 起点可由 DataEvent 因果闭包或观察性 `data_event_set_root` 定位，但这两条路径对同一 limited timeline 的 window 起点**可能定位到不同的 cell view**（渲染层 display name / `realm_metadata` / `e2ee_epoch` 错位），"是否分歧"本身没有确定判据。为消除双路径歧义，凡实现选择给出 `state_at_window_start` 确定值，**MUST**（不再是 SHOULD）使用唯一 canonical 定位规则：**以该 limited timeline 首事件的 `prev_refs` 因果闭包在最近 Seal basis 下的 deterministic join 取 cell value**。该规则是确定性算法，对同一输入跨实现产出同一渲染投影，因此不存在"两条路径产出不同 cell view"的合法分歧。由于本字段是 projection-only、不入协议状态，实现仍 MUST NOT 把它当作权威 cell value 对外承诺；当实现无法按上述 canonical 规则计算出确定值（例如缺 Seal basis 或缺首事件因果闭包）时，MUST 回退到路径 (b)（`preview_only=true`），不得输出非 canonical 定位规则得出的 `state_at_window_start`。

**(b) 标记 `preview_only=true`** (回退路径)：

```json
{
  "timeline": {
    "events": [],
    "limited": true,
    "preview_only": true,
    "prev_cursor": "ck:cursor:..."
  }
}
```

- 客户端 MUST NOT 在 backfill 完成（即缺口被 `prev_cursor` 拉取并应用）前把该 timeline 渲染为已验证的完整 UI。
- 客户端可以渲染为占位、loading 状态或带 "loading history..." 标签的预览，但不得让用户感知为"完整 timeline"。

> Rationale: Matrix `/sync` limited timeline 同时返回 state delta；Cokret 的 per-event auth state 已覆盖协议层正确性，但渲染层（display name / Realm or Strand avatar / epoch boundary）仍可能错位。`state_at_window_start` 给服务端实现一条轻量恢复路径，`preview_only` 给无法计算历史 seal 的实现一条安全回退。

## 6. Event Ordering

Client Sync 的事件顺序是展示顺序和增量恢复顺序，不是授权真相本身。授权真相仍由 event hash、`prev_refs`、`refs[role=authorized_by]`、realm version 和 reducer 决定。

服务器返回 `timeline.events` 时 MUST 满足：

1. 同一响应内的事件按 deterministic timeline projection order 排列。
2. 若事件 B 通过 `prev_refs`、`refs[role="after"]`、`causal_refs` 或 payload 物化的 reply/reference edge（如 `replies_to`）直接依赖事件 A，且 A 在同一响应窗口中可见，则 A MUST 出现在 B 之前。
3. 如果依赖事件因过滤、权限、分页或缺失而不在响应中，B MUST 保留原始 Event Envelope 中客户端可见的完整 `prev_refs[]` 与 `refs[]` 条目；客户端把其中未在本响应出现、且本地 store 未命中的 `prev_refs[]` 或 `refs[role=authorized_by]` 判为 backfill 目标，并在补齐前 soft fail 或延迟渲染。若某个依赖引用本身因权限不可见，服务端不得伪造占位引用；该事件按 `timeline.limited=true` / `preview_only=true` 或对应 `unauthorized` 诊断处理。
4. 服务器 MUST NOT 使用本地数据库自增 ID、接收顺序或 Sync Service 到达顺序作为跨实现排序依据。

Canonical default timeline projection order（不输入 canonical state、授权判断或 winner 选择；请求未显式声明并协商其它 profile 排序时，服务器 MUST 使用本顺序）：

```text
causal_depth ASC,
hlc ASC,
actor_id ASC,
actor_seq ASC,
event_id ASC
```

其中：

- `causal_depth` 来自已知 DAG：`prev_refs ∪ refs[role="after"] ∪ causal_refs ∪ payload 物化的 reply/reference edge`。
- `hlc` 用于近实时排序。
- `actor_seq` 只在同一 actor 的已知因果路径内辅助排序；并发 sibling fork 仍由后续 tie-breaker 收敛。
- `event_id` 是最终 tie-breaker。

对于协议状态，客户端 MUST 使用 `event-auth-state-resolution.md` 的 CBA query basis 与 Lattice cell value 解释当前态，不得只取 timeline 中最后出现的同 kind Event。

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
  "cursor": "ck:cursor:<opaque-valid-stream-cursor>",
  "partial": true,
  "priority": "active_view",
  "realms": {}
}
```

客户端 MUST treat `cursor` as the only resume token. 如果某个 Realm 的 timeline 返回 `limited=true`，客户端不得把当前窗口视为完整历史。

## 8. Lazy Loading Members

当 `lazy_load_members=true`：

- 服务器 SHOULD 只返回 timeline 中 sender、被 mention actor、membership changed actor 和 required_state 指定 actor 的 `ck.member.state`。
- 客户端遇到未知 actor 时 MAY 通过 `ck.self.events.query.scan` 补拉当前 effective `ck.member.state` / `ck.member.identity.update` events；需要当前 handle 展示时，MUST 使用本节定义的 handle-claim source（roster 内联或 `ck.find.directory.query.list_handles_for_subject`），不得把 profile / identity event 中的 handle 字符串当作授权事实。
- 如果 `include_redundant_members=false`，服务器 SHOULD 避免重复发送客户端已知且未变化的 member state。

### 8.1 Member Roster, Identity Projection, and Handle Claims

`state.events` 中的 `ck.member.state` 是成员资格的权威真相源；它由 reducer 决策，携带完整 `actor_id`、`membership`、`delivery_binding`、proof refs 等字段。客户端按 seal view + Lattice cell value 解释这些事件。

为给客户端列表视图（成员侧栏、participant 标识、@mention 自动补全初始集）提供一份轻量 roster，服务端 MAY 在每个 Realm 响应里附带 `members[]` 字段。`members[]` 是 `ck.member.state` cell、当前 effective `ck.member.identity.update` set 和当前可见 handle-claim set 的派生 hint，不参与 state hash / frontier 计算，也不替代逐事件验证。`members[]` MUST NOT 把 display name 或裸 handle 字符串直接作为 roster 字段回填；若返回 handle，MUST 作为完整签名 `ck.schema.handle_claim.v1` evidence 或其 digest/ref 返回。

成员展示信息由两类 source 合成：

- `ck.member.identity.update`：Realm-scoped display/subject projection。它表达 `actor_id -> subject_id` 披露、display name、avatar 等 UI profile 信息；它不是 handle lifecycle 的权威源。
- `ck.schema.handle_claim.v1`：handle 授权事实。handle 的分配、重分配、撤销和过期由 Principal Server / Organization / Directory issuer 签发的 claim 决定，用户 profile 或 MemberIdentity event 不能单方面声明 handle。

`ck.member.identity.update` 不是 `ck.profile.update` 的字段级 delta；它是 append-only 的 **segment replacement event**：新事件通过 `payload.replaces[]` 明确声明自己替代哪些旧身份事件。旧事件仍然保留在历史中，只是不再进入当前 display projection。管理员后期修改或新增用户 handle 时，不需要也不得伪造用户的 `ck.member.identity.update`；服务端和客户端通过刷新当前 handle-claim set 更新显示。

```json
{
  "members": [
    {
      "actor_id": "did:key:z6MkRealmPairwise...",
      "membership": "join",
      "identity_event_ids": [
        "ck:event:0196419b-0000-7000-8000-000000000001"
      ],
      "handle_claim_digests": [
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ],
      "handle_claims": [
        {
          "schema": "ck.schema.handle_claim.v1",
          "handle": "alice:acme.example",
          "subject": "did:webvh:zQmPr8...",
          "issuer": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example",
          "binding_state": "verified",
          "created_at": "2026-05-27T00:00:00Z",
          "expires_at": "2026-06-27T00:00:00Z",
          "proofs": [
            {
              "kind": "detached_jws",
              "alg": "EdDSA",
              "verification_method": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example#key-1",
              "payload_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
              "created_at": "2026-05-27T00:00:00Z",
              "jws": "aaa.bbb.ccc"
            }
          ]
        }
      ],
      "member_display_state_digest": "sha256:..."
    }
  ],
  "members_limited": false
}
```

`members[]` entry 字段规范：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `actor_id` | DID | MUST | 等于当前 effective `ck.member.state` cell subject / `payload.actor_id`。高隐私 Realm 中 MAY 是 Realm-scoped pairwise DID；作为**长期 membership key** 的 pairwise DID MUST 由 `did:webvh` 派生（可持久解析 / 轮换 / 撤销）或在部署 `method_policy` 中显式豁免，MUST NOT 使用被标为 `ephemeral_only` 的 `did:key`（见 [`sovereign-deployment.md` §3.1](./sovereign-deployment.md)）。真实 principal 的披露由当前 effective `ck.member.identity.update` events 决定。 |
| `membership` | enum | MUST | 当前 effective membership，取 `join` / `invite` / `knock`。leave / ban 不进入 roster。 |
| `subject_id` | DID | MAY | handle claim 的 `subject` 对应的 holder / principal DID，不是 Realm `actor_id`。当当前响应已经按 Realm disclosure policy 向调用方披露该 member 的 principal / holder DID 时可返回。若 subject 仅在 encrypted MemberIdentity 中披露，服务端 MAY 省略，由客户端解密后再走 `ck.find.directory.query.list_handles_for_subject`。返回 `identity_events`、`handle_claim_digests`、`handle_claims` 或 `handle_claims_limited` 时该字段 MUST 存在。 |
| `identity_event_ids` | event id array | MAY | 当前 effective `ck.member.identity.update` event ids。客户端 MAY 按这些 id backfill 原始事件；服务端 MAY 把这些原始 Event envelope 内联到 `identity_events[]` 或 `state.events`。 |
| `handle_claim_digests` | hash array | MAY | 当前对调用方可见且可用于该 Realm context 的 effective handle claims 的 canonical digest 集合。每个 digest 按 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) 的 `claim_digest(c)` 定义计算。该字段是跨上下文稳定标识，MUST NOT 在 `subject_id` 未披露时返回。 |
| `handle_claims` | handle claim array | MAY | 可选内联的完整 `ck.schema.handle_claim.v1` objects。它们是当前 handle 授权 evidence，不是 roster 自己生成的 display 字段。该字段 MUST NOT 在 `subject_id` 未披露时返回；若返回，每个 claim 的 `subject` MUST 等于 `subject_id`。服务端 MAY 因隐私、体积或 freshness 省略，客户端可用 `subject_id` 调 `ck.find.directory.query.list_handles_for_subject` 补拉。 |
| `handle_claims_limited` | boolean | MAY | `true` 表示 `handle_claims[]` 被截断或仅含 digest hints；客户端 MUST NOT 把缺失 claim 解释为该 subject 没有 handle。该字段只在 `subject_id` 已披露且 handle claim set 对调用方可见时返回。 |
| `member_display_state_digest` | hash | MAY | `sha256` over RFC 8785 JCS canonical JSON：`{realm_id, actor_id, effective_events:[{event_id, segment, payload_digest}], handle_claims:[{claim_digest,binding_state,expires_at}]}`，其中 `effective_events` 按 `(segment,event_id)` 排序，`handle_claims` 按 `(claim_digest)` 排序。用于 roster display cache 失效和重复响应去重；不同于 `ck.member.identity.update` 事件内的 `identity_payload_digest`。 |
| `identity_events` | Event array | MAY | 可选内联的原始 `ck.member.identity.update` Event envelope。服务端不得把它改写成查询时合成 payload。该字段可能明文或可解密地披露同一 member `subject_id`，因此 `subject_id` 未披露时 MUST 省略。 |

`handle_claim_digests[]` 是跨上下文稳定的 claim identifier；完整 `handle_claims[]` 又直接携带 claim `subject`，`identity_events[]` 也可能披露 `MemberIdentity.subject_id`。因此，当 `subject_id` 因 Realm disclosure policy 未披露时，服务端 MUST 同时省略 `identity_events`、`handle_claim_digests`、`handle_claims` 和 `handle_claims_limited`，不得把 digest hint 或原始 identity event 当作隐私安全的替代披露。返回完整 `handle_claims[]` 时，服务端 MUST 确保每个 claim 的 `subject` 等于同一 roster entry 的 `subject_id`；不匹配的 claim MUST 被丢弃或导致该 roster entry 失败 closed。

`member_display_state_digest` 只覆盖影响 roster display selection 的 stable 输入：effective identity event references 与当前可见 handle claim 的 `claim_digest` / `binding_state` / `expires_at`。Issuer 仅刷新 `verified_at`、签名打包顺序或其它非语义 freshness hint 时，该 digest MAY 保持不变；需要强制刷新证据新鲜度的服务应使用 claim cache TTL、`as_of` 或重新拉取 claim evidence，而不是通过 digest churn 表达 freshness。

`ck.member.identity.update` payload 形态：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:key:z6MkRealmPairwise...",
  "segment": "member_identity",
  "replaces": [
    {
      "event_id": "ck:event:0196419a-0000-7000-8000-000000000001",
      "payload_digest": "sha256:..."
    }
  ],
  "identity_payload": {
    "encrypted_payload": {
      "scheme": "mls-rfc9420",
      "version": "1.0",
      "group_id": "base64url",
      "epoch": 12,
      "content_type": "application/vnd.cokret.member-identity+json",
      "ciphertext": "base64url",
      "aad_visibility_event_id": "routing_digest",
      "aad": {
        "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
        "event_kind": "ck.member.identity.update",
        "event_ref_digest": "sha256:..."
      },
      "key_ref": {
        "algorithm": "MLS",
        "group_state_ref": "ck:event:01964148-0000-7000-8000-000000000000"
      },
      "payload_digest": "sha256:...",
      "aad_digest": "sha256:..."
    }
  },
  "identity_payload_digest": "sha256:...",
  "expected_state_digest": "sha256:..."
}
```

当前 effective 身份事件集合的计算规则：

- 候选集是同一 `(realm_id, actor_id, segment)` 下 accepted 的 `ck.member.identity.update` events。
- `payload.replaces[].payload_digest` 是被替代事件完整 `payload.identity_payload` carrier wrapper（`{member_identity: ...}` 或 `{encrypted_payload: ...}`）的 RFC 8785 JCS canonical JSON bytes 的 `sha256` digest。
- 若 accepted event `B` 的 `replaces[]` 引用 accepted event `A`，且 `payload_digest` 等于 `A.payload.identity_payload` 的 digest，则 `A` 在当前 projection 中被 `B` 替代。
- `replaces[]` 引用未知 event、其它 `(realm_id, actor_id, segment)` 的 event，或 digest 不匹配时，该 replacement edge 无效；实现 MUST NOT 因此把被引用 event 从 effective set 移除。
- 当前 effective set 是候选集中未被有效 replacement edge 指向的事件集合。成员身份查询 / roster hint SHOULD 只返回这个 effective set；历史 backfill / audit 查询 MAY 返回已被替代的旧事件。
- effective set MAY 因并发写入或 replacement 冲突包含多个未被替代的事件。查询层 MUST 原样暴露该多值状态，MUST NOT 按本地排序、到达顺序或 last-writer-wins 规则静默收敛为单一 MemberIdentity。需要单一 MemberIdentity 的显示路径（例如 mention renderer）MUST 按 [`identity/identity-handles.md` §3.8.2](../identity/identity-handles.md) 处理：不唯一即 Realm-scoped projection 路径失败，进入 live / as-of resolve 或 fallback。
- `identity_payload_digest` 是当前事件 `payload.identity_payload` carrier wrapper 的 digest，只用于 payload cache / 去重，不代表当前 effective set。
- `expected_state_digest` 是可选 optimistic concurrency guard。若存在，它 MUST 等于 writer 观察到的同一 `(realm_id, actor_id, segment)` 当前 effective set digest：`sha256` over RFC 8785 JCS canonical JSON `{realm_id, actor_id, segment, effective_events:[{event_id, segment, payload_digest}]}`，其中 `effective_events` 按 `(segment,event_id)` 排序。不匹配时服务端 / reducer MUST reject 或 quarantine，不得把该事件作为有效 replacement 应用。它不同于 `identity_payload_digest`，也不同于 roster 的 `member_display_state_digest`。

MemberIdentity 明文对象形态（`identity_payload.member_identity`，或 `encrypted_payload.ciphertext` 解密结果）：

```json
{
  "schema": "ck.schema.member_identity.v1",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:key:z6MkRealmPairwise...",
  "subject_id": "did:webvh:zQmPr8...",
  "display_profile": {
    "display_name": "Alice Zhang",
    "avatar_blob_ref": "ck:blob:sha256:..."
  },
  "asserted_at": "2026-05-27T00:00:00Z",
  "expires_at": "2026-06-27T00:00:00Z",
  "proof": {
    "verification_method": "did:webvh:zQmPr8...#key-1",
    "signature_algorithm": "Ed25519",
    "payload_digest": "sha256:...",
    "signature": "base64url..."
  }
}
```

MemberIdentity replacement 规则：

- v1 core 只定义 `segment="member_identity"`，因此每次替代旧身份事件时，新事件的 `identity_payload` MUST 携带完整 MemberIdentity。用户只修改 display name 时，客户端也必须读取本地当前 effective MemberIdentity，应用本地修改后重新封装完整对象；不得只发送 `{display_name: ...}`。
- 更窄且互不重叠的 segment（例如 `display_profile` / `subject_disclosure`）需要后续 schema / profile revision 扩展 `segment` 枚举或定义新的 payload schema；v1 receiver MUST reject unknown segment values。扩展后的每个 segment 内仍然是完整替换：如果一个新事件替代某个旧 segment event，它必须包含该 segment 的所有数据，即使本次只改变其中一个字段。
- v1 MemberIdentity payload MUST NOT carry `primary_handle`、`handles[]` 或其它 handle 字符串字段。handle 是 issuer claim lifecycle 的输出，不是用户 profile / identity event 的输入；客户端需要展示 `@alice:acme.example` 时，MUST 从当前可见 `ck.schema.handle_claim.v1` set 运行 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) primary handle selection。
- canonical handle string 仍为 `alice:acme.example`；`@alice:acme.example` 的 `@` 是 mention/UI sigil，不属于 handle。`alice@acme.example` 只可作为输入别名，normalize 后不得进入签名 transcript、claim、cache key 或 MemberIdentity。
- MemberIdentity 只负责 Realm-scoped display projection：`subject_id` 披露、display name、avatar 和其它未来 display-profile segment。mention / reply / quote 等 actor 引用字段 MUST 按 [`identity/identity-handles.md` §3.8](../identity/identity-handles.md) 使用 `subject_id` 而不是 handle 字符串；handle claim 只影响显示和可读寻址，不影响 grant subject、actor attribution、membership key、delivery 决策或 audit attribution。
- handle、display name 和 avatar 只用于 UI / mention / member picker，不得用于 grant subject、actor 归因、membership key、delivery 决策或 audit attribution。
- `ck.profile.update` 继续表示 principal-scoped actor profile 的字段级 delta；`ck.profile.realm_override` 继续表示 Realm-scoped profile override。二者 MAY 作为客户端构造 MemberIdentity display fields 的输入；handle fields MUST 来自当前 effective handle claims。
- `identity_payload.encrypted_payload` MUST 复用 [`encrypted-envelope.schema.json`](../../artifacts/schemas/encrypted-envelope.schema.json)。明文 MemberIdentity 是 `ciphertext` 解密结果；`content_type` SHOULD 使用 `application/vnd.cokret.member-identity+json`。
- 加密 MemberIdentity MUST 由成员设备或被 Realm policy 授权的身份 issuer 设备生成。Sync / Principal / Federation Service MUST 存储和返回原始 encrypted payload 或其事件引用，不得因客户端查询而重加密、重封包或推进 MLS sender generation。
- 客户端解密时按 `group_id`、`epoch` 和 `key_ref.group_state_ref` 查找本地 MLS group state；缺少 epoch 时按 §15 标记 `decryption_pending` 并补拉 `ck.mls.*` state / Welcome / winning Commit / 授权 history key material。
- 客户端 MUST 验证 MemberIdentity 的 `realm_id`、`actor_id`、`subject_id`、`proof.payload_digest`、签名链和 Realm disclosure policy；`proof.payload_digest` MUST 等于移除顶层 `proof` 字段后的 MemberIdentity 对象的 RFC 8785 JCS canonical JSON bytes 的 `sha256` digest，签名也 MUST 覆盖同一 canonical bytes。任一失败时不得把该 event 提升为 verified display identity。

Handle claim 获取与刷新规则：

- 注册、邀请链接、管理员预分配、管理员后期修改、重签和撤销 handle 都落到 issuer / Auth Server / 部署本地 `ck.schema.handle_claim.v1` lifecycle。Cokret v1 core 不定义用户如何申请、管理员如何收到通知、谁有权审批、审批状态如何流转或客户端如何在 bootstrap 中领取自己的 claim。
- 客户端不得通过 `ck.profile.update`、`ck.profile.realm_override` 或 `ck.member.identity.update` 自行设置 handle。无论 claim 来自 Auth Server bootstrap、issuer 本地 API、设备迁移恢复、Directory resolve 还是 roster 内联，客户端只有在 schema、issuer trust、proof、audience、expiry 和 revocation 状态验证通过后，才能把它作为 handle 授权事实。
- 已知 `subject_id`、需要渲染 Realm member 当前 handle 时，客户端调用 `ck.find.directory.query.list_handles_for_subject`，或使用 roster entry 内联的 `handle_claims[]` / `handle_claim_digests[]`。已知 handle 字符串、需要解析到 subject 或投递绑定时，继续使用 `ck.find.directory.query.resolve_handle`。
- roster / member picker / mention autocomplete 的当前 handle projection MUST 由当前可见 handle-claim set + Realm policy 运行 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) 得出。`ck.member.identity.update` 事件的 churn 不应成为 handle 更新传播的必要条件。
- 若 `member_display_state_digest` 因 handle-claim set 变化而改变，服务端 SHOULD 在下一次 `/_cokret/self/account/subscribe` delta 中发送新的 roster entry 或使客户端相关 cache 失效；无法内联完整 claims 时，MUST 至少让 `handle_claim_digests` 或 digest 缺失状态发生可观察变化。

`lazy_load_members=true` 时，服务端 MAY 截断 `members[]` 为 timeline 涉及的 actor + `summary.heroes` 子集，但此时 MUST 设置 `members_limited=true`，并 SHOULD 提供 `members_next_cursor` 或等价分页提示。客户端看到 `members_limited=true` MUST NOT 把 `members[]` 当作完整成员列表。`members[]` 的去重键是 `actor_id`；同一 `actor_id` 出现多次时客户端 MUST 保留首条并忽略后续。

`summary` 中的 `heroes` 与本节 `members[]` 互补：`heroes` 是当成员数超过显示阈值时挑选的少量代表性 DID，`members[]` 是当前响应内可投影的 roster 条目集合；完整性由 `members_limited` / pagination 明确表达。

## 9. Account Data and Private State

`account_data` 是 principal 或 device 私有状态，不进入 Realm canonical state。标准类型：

标准 Account Data key/pattern 的机器索引是 [`account-data-type-registry.json`](../../artifacts/registry/account-data-type-registry.json)。当前标准集包括：

- `ck.tags.realm.<realm_id>`
- `ck.push_rules`
- `ck.dnd_schedule`
- `ck.collections.stickers`
- `ck.client.ui_state`
- `ck.account.blocklist`
- `ck.contacts.actor.<did>`
- `ck.contacts.realm.<realm_id>`
- `ck.presence.visibility`
- `ck.presence.preference`
- `ck.read_receipt.preferences`
- `ck.account.invite_quarantine`

Account data MUST 按 principal/device 授权隔离。联邦节点不得向其他 principal 泄露 account data。

## 10. To-Device Delivery

`to_device.messages` MUST 只包含当前 session credential 对应 device 的消息。

### 10.0 主接收路径与补拉路径 (normative)

`/_cokret/self/account/subscribe` 与 `GET /_cokret/self/device_messages` 暴露的是同一个 per-device to-device 队列的两种读取形态；二者不代表两套消息源，也不允许客户端把同一 kind 分流到两套互不一致的处理器。

`ck.self.account.stream.subscribe` 是 full client / E2EE client 的主接收路径。客户端维护长连接后，服务端 SHOULD 在 `delta.to_device.messages[]` 中推送当前设备的验证请求、SAS/QR 交换、secret sharing、device-list 相关私有消息；客户端 MUST 把这里收到的 `DeviceMessageEnvelope` 交给与 `ck.self.device_messages.query.list` 相同的 to-device dispatcher，并在持久化处理完成后按 §10.1 使用 `ack_token` 显式确认。

`GET /_cokret/self/device_messages?from=<cursor>&limit=n` 是补拉 / 轮询路径，只用于下列情况：

1. `delta.to_device.limited=true` 时，用 `delta.to_device.next_cursor` 继续分页读取队列。
2. 客户端本地 dispatcher 崩溃、account subscribe 暂未建立、或前台验证小流程尚未启动完整账号同步时，用于补拉未确认消息。
3. 非 full-client 的窄实现（例如只做设备验证的登录前/登录中 UI）在持有受限 fresh-device session grant 时，可短轮询本设备队列以完成同一笔验证 transcript。

一旦 full client 的 account subscribe 已经运行，客户端 SHOULD 停止为同一 `(principal_id, device_id)` 维持独立的 SAS 轮询循环；继续轮询只应作为检测到 `limited`、`dropped`、本地处理失败或显式用户前台流程的短期恢复手段。无论消息来自主路径还是补拉路径，ack、去重、过期、`lost` 处理和 transaction 幂等规则完全相同。

### 10.1 显式投递确认 (normative)

To-device 队列删除由**显式 ack** 驱动，与 stream cursor 解耦；任何 cursor（`after=` / `from=`）都 **MUST NOT** 触发队列删除：

1. **`ack_token` 签发**：服务端在每个携带非空 `to_device.messages` 的 `delta` frame 中 MUST 附带 `to_device.ack_token`；`GET /_cokret/self/device_messages` 的每个非空响应页同样 MUST 携带顶层 `ack_token`。`ack_token` 是 server-issued 不透明确认令牌，绑定 `(principal_id, device_id, 该批次的队列高水位)`，覆盖该批次及其之前所有已投递消息。它**不是 cursor**：不使用 `ck:cursor:` wire 形态，不进入 cursor schema / TTL / purpose 体系；客户端 MUST 把它当作不透明字符串原样回传。令牌 MUST 不可伪造：不可猜测（解码后熵 ≥ 128 bit）或等价的服务端查表绑定。**wire 形态（normative）**：`ack_token` MUST 是单个 UTF-8 字符串，且 MUST NOT 超过 1024 字节；客户端按不透明字符串原样回传、不解析其内部结构，服务端 MUST 拒绝超长或非 UTF-8 的 token（`invalid_param`）。该上界保证跨实现可移植，避免无界 token。
2. **显式 ack**：客户端仅在该 `ack_token` 覆盖位置（含）之前的**所有已投递消息**都已持久化处理完成（密钥材料、verification transcript、secret 已落盘）后，MUST 调用 `ck.self.device_messages.command.ack`（`POST /_cokret/self/device_messages/ack`，body `{ack_token}`）。确认是**累计且单调**的：服务端删除该令牌覆盖位置（含）之前的全部已投递消息；ack 一个早于当前确认位置的令牌是合法 no-op，返回 `{ok: true}` 且 MUST NOT 回退确认位置。并行 dispatcher MUST 维护"最高已连续持久化队列位点"，MUST NOT ack 覆盖位置晚于任何未持久化消息的 token。该操作天然幂等，不需要 `Idempotency-Key`。
3. **ack 校验**：服务端 MUST 校验 `ack_token` 绑定与当前 authenticated `(principal_id, device_id)` 匹配；unknown / 过期 / cross-binding 令牌 MUST 返回 `invalid_param`（reason `invalid_ack_token`）且 MUST NOT 删除任何排队消息。
4. **cursor 只读**：`/_cokret/self/account/subscribe` 的 `after=` 与 `GET /_cokret/self/device_messages` 的 `from=` 只决定读取 / 续传位置。客户端建立新的 subscribe 连接时（无论 `after=` 位置），服务端 MUST 重新投递所有未确认、未过期的 to-device 消息；客户端 MUST 容忍重复投递，并按消息内容的事务标识（`transaction_id` / `request_id` 等）幂等处理。
5. **过期与丢失信号**：未确认消息仍受 `DeviceMessageEnvelope.expires_at` 与 [`device-lifecycle.md` §7](../crypto-media/device-lifecycle.md) 队列 TTL 约束，过期 MUST 清除。服务端自该设备上次确认位置以来因过期或容量约束丢弃过未确认消息时，SHOULD 在下一个含 `to_device` 的响应中设置 `to_device.lost=true`；客户端收到后 SHOULD 触发密钥恢复路径（key backup / key re-request），MUST NOT 静默假设队列完整。**E2EE client profile 升级（normative）**：对声明 `ck.profile.e2ee_client.v1` 的客户端及其服务对端，由于丢弃的未确认 to-device 消息可能承载不可再生的 MLS Welcome / secret share / key material，上述两个 SHOULD 升为 **MUST**——服务端丢弃过该设备未确认消息时 **MUST** 设置 `to_device.lost=true`；客户端见到 `to_device.lost=true` 时 **MUST** 进入 key re-request / key backup 恢复路径，**MUST NOT** 静默把队列当作完整，以免 E2EE 密钥材料永久丢失而不被检出。
6. **`ack_token` 独立于 stream cursor 生命周期（normative）**：`dropped` / `resync_required` frame、`cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized` 失效、以及任何清空本地 cursor 缓存的恢复动作，均 **MUST NOT** 使既有未确认的 `ack_token` 失效。`ack_token` 绑定的是 `(principal_id, device_id, to-device 队列高水位)`，与 stream cursor（`after=` / `from=`）的 wire 形态、TTL、purpose 和 revocation 体系完全独立（见 §10.1 第 1 条与 §12）。客户端在 cursor 失效 / dropped / resync 后重建订阅时，仍 MAY 用先前持有的有效 `ack_token` 确认已持久化处理的批次；服务端 MUST 仍按 §10.1 第 3 条校验该 token 的 `(principal_id, device_id)` 绑定并执行累计删除，不得仅因 stream cursor 已被重置就把该 token 当作 unknown / cross-binding 拒绝。该口径与 §12.2.1（cursor revoke 不影响已签发 `ack_token`）一致。

> Rationale: cursor 前进表达的是「客户端收到了 frame」，安全删除需要的是「客户端已把载荷持久化」。把删除绑在 cursor 推进上（Matrix `/sync` 的隐式 ack 模型）会留下崩溃窗口：客户端收到 frame、cursor 已推进、但 MLS Welcome / secret share 尚未落盘即崩溃 → 消息被服务端删除、密钥材料永久丢失。显式 ack 把两个语义拆开后，cursor 不再是 to-device 不可逆删除的闸门；§12 的 cursor 完整性校验仍然原样保留——它防护的是伪造 / 跨绑定位点导致的静默缺口（含 `device_lists` 缺口的 E2EE 后果）、barrier 存在性预言机与 catch-up 成本放大，而非 to-device 删除。

### 10.2 队列分页

To-device 队列过长时，服务器 MAY 在 account subscribe `delta.to_device` 容器中返回 `limited=true`。当 `delta.to_device.limited=true` 时，服务端 MUST 同时返回 `delta.to_device.next_cursor`，客户端 MUST 用该 cursor 调用：

```http
GET /_cokret/self/device_messages?from=<cursor>&limit=...
```

该 endpoint 的 `from` cursor 同样 MUST 通过 §12 完整性校验后才能用作读取位置；该读取位置是只读的，MUST NOT 触发队列删除（删除只经 §10.1 显式 ack）。`from=` 是 `ck.self.device_messages.query.list` 的历史例外命名（见 [`api-conventions.md` §7.1](./api-conventions.md)）；新增接口 MUST 用 `before` / `after`，不得把 `from=` 当作推荐形态。客户端 MUST NOT 把 account subscribe 顶层 `cursor` 当成 to-device 队列分页 cursor；顶层 `cursor` 只用于 account stream resume，to-device 队列分页只使用 `delta.to_device.next_cursor`。

## 11. Filters

Filter MUST 是服务端可验证 JSON，不得包含任意脚本。服务器 MAY 限制：

- 最大 Realm 数
- 最大 timeline limit
- 最大 required state 数
- 最大通配符展开量
- 最大等待时间

超限返回 `rate_limited`、`payload_too_large` 或 `invalid_param`，并在 `Retry-After`、`retry_after_ms` 或 `limits` 中说明。

`filter_digest` 的 canonical 计算（normative）：

1. 将 query deepObject 解析为 JSON filter object；未提供 `filter` 时，normalized filter 是空对象 `{}`。
2. 省略所有未出现的 optional 字段；不得把实现默认值写入 normalized filter。
3. 对集合语义字段 `realms`、`event_types`、`not_event_types`，在计算 digest 前按元素字符串 lexicographic 排序并去重；其它数组若未来由 profile 引入，profile MUST 声明 order-is-semantic 或 sorted，未声明时不得进入 cursor binding。
4. 按 RFC 8785 JCS 对 normalized filter 编码为 UTF-8 bytes，计算 `filter_digest = "sha256:" || hex(sha256(jcs_bytes))`。

服务端签发 stream cursor、强制 `reconnect_after_ms` cooldown 或验证 cursor binding 时 MUST 使用同一 `filter_digest`；客户端若持久化 cursor，也 SHOULD 同步持久化该 digest 以便诊断 `cursor_integrity_invalid`。

### 11.1 Events 面的 query-scope digest（normative）

`ck.self.events.query.scan`、`ck.self.events.stream.subscribe`、`ck.peer.events.query.scan`（含各 binding variant，如 `ck.self.events.query.scan_body`）签发的 stream cursor，其绑定中的 `filter_digest` MUST 覆盖**完整查询作用域**，不只是 `filters`：

1. normalized scope object 包含全部**非位置性**、决定结果集合或结果形状的请求参数：selector（`realms`、`actors`）、`filters` object、`order`，以及 profile 引入的等价参数。
2. 位置性参数（`before` / `after` / `limit` / cursor 本身）与认证材料 MUST NOT 进入 digest——它们随每次调用变化，不属于作用域身份。
3. 集合语义字段（`realms`、`actors`、`event_types`、`not_event_types`）在计算前按元素字符串 lexicographic 排序并去重；未提供的 optional 字段省略，不得把实现默认值写入 normalized scope。
4. 按 RFC 8785 JCS 编码为 UTF-8 bytes 计算 `sha256`，规则与本节 `filter_digest` 一致。

客户端在与签发 scope 不同的查询作用域下回传 cursor（例如更换了 `actors` selector 或 `order`），服务端 MUST 视为 binding 不匹配并返回 `cursor_integrity_invalid`，MUST NOT 按新 scope 继续续读——跨 scope 复用 cursor 会产生静默跳读（新 scope 包含、旧 scope 排除的事件被跳过）或权限边界混淆。字段名继续沿用 `filter_digest`；在 events 面它语义上是 query-scope digest。

## 12. Cursor Semantics

`cursor`（purpose=`stream`）MUST 绑定：

- principal id
- device id
- service id
- `filter_digest`（account 面为 §11 filter digest；events 面为 §11.1 query-scope digest，覆盖完整 selector + filters + order）
- stream positions
- expiry

`cursor`（purpose=`barrier`）由写接口在响应中返回（见 [`api-conventions.md` §8](./api-conventions.md)），用于 `X-Cokret-Wait-For` header；它和 stream cursor 共享 wire 形态 `ck:cursor:<base64url>`，由内部 `purpose` 字段区分。客户端不需要分辨，只需把"写响应里的 cursor"作为 wait-for header、把"`/_cokret/self/account/subscribe` frame 里的 cursor"作为下次 `after=` 重连参数即可。

### 12.1 Cursor Integrity (normative)

无论 stream 还是 barrier cursor，wire 形态 `ck:cursor:<base64url(canonical_json)>` 都 **MUST** 是服务端可验证的同步位置；服务端 **MUST NOT** 仅按语法 / TTL / purpose 校验就把客户端回传的 cursor 当作"可信位置"用于 `/_cokret/self/account/subscribe` `after=` resume 起点、`X-Cokret-Wait-For` barrier 解除、`dropped` / `resync_required` 恢复或其他不可逆 server-side state。v1 不存在 cursor 驱动的 to-device ack：to-device 队列删除只由 §10.1 显式 ack 驱动，cursor 的 to-device position 仅决定续传读取位置。

**v1 core 采用单一 stateful opaque handle 形态**：canonical body 为 `{v, purpose, t, x, h}`，其中 `h` 是 issuing service 生成的不可猜测 handle（解码后熵 ≥ 128 bit），service 内部维护 handle → `(principal_id, device_id, service_id, filter_digest, purpose, positions, target?, expiry)` 映射。Handle 查表本身就是完整性校验 —— 无需在线 transcript 校验，无需 `_mac` / `_sig`，无需 `issuer_kid` 密钥管理。这是 Matrix `next_batch` / MSC4186 `pos` 的等价形式。

服务端 SHOULD 将 handle → binding 映射持久化（或以其它方式保证其跨进程重启存活），使服务重启不会把所有未过期 cursor 同时变成未知 handle、迫使全部客户端按 §12.3 重做 initial sync。仅内存实现不违反完整性契约（未知 handle 仍按 `cursor_integrity_invalid` 失败 closed），但其重启代价随活跃客户端数线性放大；持久化实现 SHOULD 同时对未过期 handle 做超出 TTL 的及时清理（例如客户端出示更新 cursor 即可证明严格更旧的同流 handle 已被取代），避免 handle 表无界增长。

对生产级部署，上述耐久性从 SHOULD 升级为 MUST：声明 `ck.profile.small_team.v1`、`ck.profile.organization.v1`、`ck.profile.high_security_organization.v1`、`ck.profile.sovereign_deployment.v1`、`ck.profile.sovereign_enclave.v1` 或 `ck.profile.isolated_sovereign_network.v1` 任一 deployment profile 的服务，MUST 保证未过期 cursor handle 绑定跨进程重启可解析，且 MUST 实现 TTL GC 与被取代 handle 的前进清理；常规重启或计划内升级把全部活跃客户端打回 initial sync 视为不满足该 profile 声明。

`ck.profile.personal_node.v1`（个人/开发单机）的 personal_node cursor handle 持久化默认维持 SHOULD；**但启用 E2EE 时升级（normative）**：当该 personal_node 服务于启用 E2EE 的账号（承载 `ck.profile.e2ee_client.v1` 客户端或 `encryption_profile=mls_rfc9420` Realm）时，未过期 cursor handle 绑定的跨进程重启持久化 **MUST** 实现；若实现确实无法持久化该绑定，则每次重启后 **MUST** 对受影响客户端强制重发完整 `device_lists` baseline（等同 initial sync 的 device list 全量 baseline）。理由：重启即丢 cursor 会把 E2EE 设备信任刷新静默退化为全量重置，而 `device_lists` 缺口只能靠重做 initial sync 恢复（见 §2.2 第 1 条）；二者必择其一，不得让 E2EE 设备信任在重启后处于既不持久也不强制重建的状态。

### 12.2 校验流程 (normative)

任何 endpoint 在使用客户端回传的 cursor 推进 server-side state 之前，MUST 执行：

1. 解析 `ck:cursor:<base64url>` 并按 `cursor.schema.json` 校验语法、`purpose`、TTL (`x` 未过期)。语法/参数失败映射顶层 `invalid_param`（reason `invalid_cursor`）；TTL 失败映射 `cursor_expired`。
2. **Handle 查表完整性校验**：以 `h` 查 issuing service 本地表，校验 handle 存在、未过期、未撤销，且绑定的 `(principal_id, device_id, service_id, filter_digest, purpose)` 与当前 authenticated request 匹配；任一失败 → 返回 `cursor_integrity_invalid`，**MUST NOT** 推进任何 server-side state。
3. 校验通过后才可读 handle 解析出的 positions（stream cursors）或 target（barrier cursors），并用于推进同步状态。

`cursor_integrity_invalid` 与 `cursor_expired` 语义不同：前者是 tamper / 未知 handle / cross-binding，后者是 TTL 超时。客户端对 `cursor_integrity_invalid` 的恢复路径与 `cursor_expired` 一致（重做 initial sync），但客户端 SHOULD 把它视为本端 cursor 状态被污染的信号，清理本地 cursor 缓存。

### 12.2.1 Cursor Revoke（high-assurance optional）

声明 high-assurance cursor revoke capability（ServiceDescribe `supported_features[]` 含 `cursor_revoke_high_assurance`）的服务 MUST 支持主动撤销 cursor：

```text
POST /_cokret/self/account/cursor/revoke
```

请求体至少包含 `{cursor, reason_code, revoke_scope}`；`revoke_scope` 取值为 `this_cursor` / `same_session` / `same_device`，缺省 `revoke_scope=this_cursor`。

`revoke_scope` 范围的 normative 定义（与 [`identity/account-lifecycle.md`](../identity/account-lifecycle.md) 中的 session/device 标识对齐）：

- session 抽象为 `(principal_id, device_id, issued_at, session_id)` 四元组，由签发 cursor 的服务在派发时记录在 cursor handle metadata 中。
- `this_cursor`：仅撤销当前提交的 cursor 本体（按 stateful handle 匹配）。
- `same_session`：撤销与当前 cursor 同 `(principal_id, device_id, issued_at, session_id)` 的所有未过期 cursor（含同会话内派发的派生 cursor）。
- `same_device`：撤销与当前 cursor 同 `(principal_id, device_id)` 的所有未过期 cursor（跨会话）。
- 当 cursor 来自浏览器或其它无稳定 `device_id` 的环境时，`same_device` MUST 在效果上退化为 `this_cursor`（服务端不得猜测设备同一性），并在响应 `revoke_scope_effective="this_cursor"` 中显式回执，以避免客户端误以为全设备已撤销。

服务端接受后 MUST 将对应 cursor 写入 cursor revocation set（按 stateful handle 匹配），保留时间不少于该服务声明的最长 cursor TTL（stream / barrier cursor 的 TTL 硬上限唯一 canonical 数值见 [`encoding.md` §8.3 规则 9](../conformance/encoding.md)，本节不重复字面数值）。撤销命中时，任何 endpoint MUST 返回 `cursor_revoked`，并且不得推进 subscription position、barrier wait 或 dropped recovery state（to-device 队列删除不经 cursor，见 §10.1；cursor revoke 不影响已签发 `ack_token` 的有效性）。

Cursor revoke 不能替代 cursor integrity：服务端仍必须先做 §12.2 完整性校验；完整性失败返回 `cursor_integrity_invalid`，不泄露该 cursor 是否曾被 revoke。

### 12.3 过期或缺口恢复流程

恢复流程按触发原因分成两类互斥分支，客户端 MUST 先按 §4 的分类判定原因再进入对应分支；两类分支对"旧 cursor 是否可继续复用"的处理**根本不同**，不得混用同一套 `after=` 取值。

> **frontier 不是 cursor（前置约定）**：`account/describe`（`ServiceDescribe` 私有 frontier 扩展字段）与 `snapshot/head`（`ck.schema.snapshot.v1` manifest 的 `frontier.event_ids`）返回的 frontier 是 **boundary head event id 集合**，不是 stream cursor（`ck:cursor:<base64url>`）。`ck.self.events.query.scan` / `ck.self.account.stream.subscribe` 的 `before=` / `after=` 参数类型严格是 `cursor`（见 [`service-http-binding.md` §3.3.2](./service-http-binding.md)），任何其它边界参数 MUST 触发 `invalid_param`。因此客户端 **MUST NOT** 把 frontier event id 直接填入 `after=` / `before=`；frontier 在恢复中只作为 backfill 的**集合停止判据**：必须命中 `frontier.event_ids` 中的每一个 head，且已拉窗口内所有可见事件的 `prev_refs` / critical refs 因果闭包要么已解析、要么落在已验证的 `event_set_commitment` 覆盖集内，才算接上当前态。续传位置由 `events.query` 响应返回的 `prev_cursor` / `next_cursor` 决定。

#### 12.3.1 `cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized`（旧 cursor MUST 废弃）

cursor 本端状态失效（TTL 超时，或 tamper / 未知 handle / cross-binding，或 cursor 由另一服务签发即 `cursor_unrecognized`）。旧 cursor 不再是可信同步位置：

1. 客户端 MUST 清空本地 cursor 缓存（含该流的 `after=` 高水位）；**MUST NOT** 把已失效的旧 cursor 复用为任何 `after=` / `before=` 起点或 backfill 续传位置。`filter_digest`、未确认写入和最后可验证 frontier 可保留用于 backfill 停止判定，但 frontier 不得当作 cursor 使用。
2. 客户端从下列两条合法新起点二选一，二者都不复用旧 cursor：
   - **(A) 重做 initial sync**：无 `after` 重新建立 `ck.self.account.stream.subscribe?catchup=true`（`after=` 缺省 + `catchup=true`），由服务端发 baseline `delta` 重新签发新 cursor。
   - **(B) snapshot 加速 bootstrap**：调用 `ck.self.snapshot.query.manifest_head` 取 `ck.schema.snapshot.v1` manifest，MUST 先验证签名、签名者授权、`state_digest`、`frontier`、`event_set_commitment` 和每个 chunk digest（[`service-http-binding.md` §6.1](./service-http-binding.md)、§13）。验证通过后把 `frontier.event_ids` 作为该 Realm 已知态边界，再以 `ck.self.events.query.scan` **从 server head 向更旧方向 backfill**（省略 `after`，即隐式 `before=<server_head>`，并用响应 `prev_cursor` 作为下一页 `before=`），直到 `frontier.event_ids` 中每一个 head 都已在本地命中，且窗口内所有已拉事件的 `prev_refs` / critical refs 因果闭包要么已解析、要么落在已验证的 `event_set_commitment` 覆盖集内；在此之前 timeline MUST 保持 `limited` / provisional，不得声称历史完整。账号聚合面仍按 (A) 重新建立 subscribe 取得新 cursor。
3. 若 snapshot 校验失败、manifest 不可用或服务端未宣告 `ck.self.snapshot.query.manifest_head`，客户端 MUST 回退到 (A) 的 initial sync 或纯 Event history replay，**不得**把未验证 snapshot 作为 accepted state，也不得退回复用旧 cursor。

#### 12.3.2 `stale_frontier`（旧 cursor 仍有效，可继续 backfill）

cursor 本身仍有效，只是服务 frontier 落后于请求所需 causal frontier。此分支 **MUST NOT** 清 cursor 重做 initial sync：

1. 客户端保留本地 `cursor`、`filter_digest`、未确认写入和最后可验证 frontier。
2. 按 `retry_after_ms` / `Retry-After` 退避后，用**现有 cursor** 重试 / 等待 frontier 推进；需要补洞时，可先调用 `account/describe` 或 `snapshot/head` 读当前 frontier 作为停止判据，再用**现有 cursor** 的 `prev_cursor` / `next_cursor` 续传 `ck.self.events.query.scan` 补齐缺口。snapshot 采用前同样 MUST 完成上述全部校验。

#### 12.3.3 Range completeness（两分支共用）

服务端声明 `events_query_range_completeness` feature 时，客户端 SHOULD 在恢复 backfill 的 `ck.self.events.query.scan` 调用上设置 `include_completeness=true`，并在补齐后按 [`service-http-binding.md` §3.3.6](./service-http-binding.md) 验证覆盖该缺口区间的 `ck.attestation.range_completeness`——cursor + `has_more` 只证明"拿到了页"，attestation 才证明"该区间没有事件被静默扣下"。验证失败（`range_completeness_root_mismatch` / `range_completeness_actor_seq_gap` / `witness_disagreement`）时 MUST 把该区间标记 degraded 并 fail closed，不得向用户展示"历史完整"。high-assurance Realm（`security_class=high_assurance` 或 `ck.profile.federation.high_assurance.v1`）下该 SHOULD 升级为 MUST。

## 13. Initial Sync

Initial sync 的账号入口是:

```http
GET /_cokret/self/account/subscribe?catchup=true
Accept: application/json
```

也就是不带 `after`,并显式请求 `catchup=true`。使用 JSON 长轮询时，服务器 MUST 返回一个覆盖当前账号 baseline 的 `SyncOutcome`；使用 NDJSON stream 时，服务器 MUST 先发送至少一个 `delta` frame 作为账号 baseline,再发送 `catchup_complete`,然后 MAY 继续保持连接进入实时推送。Baseline 不是完整历史记录；它只覆盖客户端首屏与账号状态恢复所需的当前视图。Baseline `delta` / `SyncOutcome` SHOULD：

- 返回用户当前 joined/invited/knocked Realms 的摘要。
- 对活跃 Realm 返回有限 timeline。
- 返回足够 `required_state` 让客户端首屏可渲染。
- 返回 device list delta 的完整 baseline。

大型账户 MAY 使用 sliding window subscriptions，避免一次性返回所有 Realm。

大型 Realm 的当前态 MAY 在 initial sync 中通过 snapshot bootstrap 加速：客户端先调用 `ck.self.snapshot.query.manifest_head` 获取 `ck.schema.snapshot.v1` manifest，完成签名、authority binding、`event_set_commitment`、`state_digest` 与 chunk digest 校验后，把 snapshot frontier 作为该 Realm 的恢复起点；随后仍 MUST 从该 frontier 之后继续执行 `ck.self.events.query.scan` / backfill，直至账号 baseline 与 Realm event stream 收敛。snapshot 校验失败、manifest 不可用或服务端未宣告 `ck.self.snapshot.query.manifest_head` 时，客户端 MUST 回退到原始 Event history replay，不得把未验证 snapshot 作为 accepted state。

## 14. E2EE Requirements

E2EE client 在处理 encrypted event 前 MUST：

- 检查 `device_lists` 是否有变更。
- 检查 Realm encryption epoch。
- 拉取缺失 KeyPackage / group secret。
- 对无法解密事件记录 `decryption_pending`，不得静默丢弃。

服务器 MUST NOT 因无法解密而过滤 encrypted event。

### 14.1 解密缓存与历史密钥的本地静态加密 (normative)

`e2ee_required` Realm 的客户端在本地持久化解密产物与密钥材料时 MUST 满足以下约束。本节针对客户端 at-rest 层(Web 的 localStorage / IndexedDB、原生磁盘、OS 缓存),与服务端零知识承诺正交。

- **解密明文缓存**:解密后保留的 reduced state cache、materialized view cache,以及为渲染前向保密(逐条 ratchet,密钥用后即焚)消息而缓存的解密明文——包括远端成员消息明文缓存与作者自身明文侧车——MUST 以静态加密形式持久化，或仅驻内存;**MUST NOT** 以明文写入任何持久化存储。
- **历史密钥材料**:join 前历史解密所需的密钥材料(per-`(realm, epoch)` `history_secret`、exporter 派生密钥，或等价的逐条解密密钥)MUST 存于硬化密钥存储，其保护级别 MUST 等同于账户 MLS secret(在 Web 上即非导出 SubtleCrypto 密钥 + IndexedDB 层);**MUST NOT** 以明文落盘，且 **MUST NOT** 镜像到弱化的同步/首屏存储层(如 localStorage)。
- **静态加密包裹密钥的归属**:用于上述明文缓存静态加密的 at-rest 包裹密钥本身 MUST 存于硬化密钥存储。当硬化存储不可用时，客户端 MUST fail closed——缓存仅驻内存、**MUST NOT** 以明文落盘兜底，除非用户显式 opt-in 并被告知降级风险。
- **生命周期擦除**:设备 lock、软登出与设备吊销后，客户端 SHOULD 丢弃驻内存的 at-rest 包裹密钥并清除解密明文缓存，使已落盘的密文不可再解(本机范围；无法远程擦除其他设备)。

实现侧自检(descriptive):落盘完成后直接读取持久化存储的原始字节，对加密 Realm 的解密明文与历史密钥 **MUST NOT** 命中已知明文/密钥字节；此自检作为防止"新增内联字段又把敏感数据明文落盘"的回归守卫。交叉引用见 [`encryption-and-audit.md` §5.6](../crypto-media/encryption-and-audit.md)。

## 15. E2EE and MLS Sync Performance

E2EE Realm 的同步必须把“事件顺序”和“密钥可用性”分开处理。事件可以先进入本地 raw event cache；解密可以异步完成。

客户端处理加密 timeline 时 SHOULD：

1. 先验证 event envelope、hash、signature、`realm_id`、`refs[role=authorized_by]` 和 `prev_refs`。
2. 根据明文 routing metadata 将事件放入 timeline / reducer 队列。
3. 检查事件声明的 `mls_epoch`。
4. 如果本地缺少该 epoch 的 group state，拉取缺失 `ck.mls.*` state event、MLS Commit 和必要 key backup。
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

客户端首次把某事件标记为 `decryption_pending` 时 MUST 记录 `first_pending_at`、缺失的 `(realm_id, strand_id?, track_name?, group_id, epoch)`、已尝试的恢复 source 和最近一次错误。默认 `decryption_pending_timeout` 为 7 天；Realm policy 或实现 profile MAY 声明更短值，高保障 profile SHOULD 更短，但不得无限期保持无诊断 pending。

**`first_pending_at` 计时基准（normative）**：`first_pending_at` MUST 取该 pending 事件自身的因果时间——`hlc`（首选）或 `created_at`，而 **MUST NOT** 取 per-device 本地墙钟"首次见到该事件"的时刻。这使 `decryption_pending_timeout` 在 **account 维度单调**：同一事件在不同设备、重启或重新 initial sync 后重新进入 pending 时，timeout deadline（`first_pending_at + decryption_pending_timeout`）保持稳定，不会因换设备或重启而把 7 天窗口刷新重置。若实现需要跨设备协调 pending 诊断状态，SHOULD 通过 account-data 同步 `first_pending_at`（取各设备记录中**最早**的因果时间），使 timeout 判定不被任何单设备的较晚墙钟首见时刻推后。

在 timeout 前，客户端 SHOULD 按以下顺序恢复：

1. 拉取缺失的 `ck.mls.*` state event、winner `ck.mls.commit`、Welcome 和 `governance_binding` 依赖。
2. 查询本 actor 授权设备的 encrypted key backup / secret storage。
3. 在 history sharing policy 允许时，请求当前授权 peer 对指定 epoch range 发送 key share。
4. 若 Realm policy 声明 Archive Node / Audit Node / Key Recovery Service，可向该受托服务请求最小 epoch range。

当连续 epoch 缺口超过 `epoch_gap_recovery_threshold`（默认 32 个 epoch）或本地 backfill 预算耗尽时，客户端 SHOULD 切换到 range-based recovery：按 epoch 区间请求 key material、MLS Commit chain 和必要 snapshot proof，而不是逐消息重试。任何 key share 都必须绑定接收 principal、device、epoch range、policy hash 和发送设备签名；不得向已被移除、未授权或无法验证的成员请求密钥。

超过 `decryption_pending_timeout` 后，客户端 MUST 将用户可见投影标记为 `decryption_failed`，保留 metadata-only 占位、排序位置、引用关系和重试诊断，并向用户显示不可解密状态。若之后合法 key material 到达，客户端 MAY 重新解密并把状态从 `decryption_failed` 恢复为 verified content，但该 MAY 受 [`encryption-and-audit.md` §2.3.5](../crypto-media/encryption-and-audit.md) late key recovery 状态机约束：必须通过原始接收时刻 T0 的 membership / history / key scope 校验，UI 必须显示 late recovery timeline marker；audit profile 下必须先 emit `ck.audit.accessed` 并取得 RYW receipt 后才可显示明文。恢复审计记录必须保留，不得静默替换原 metadata-only 占位。
