---
title: Client Sync
status: candidate
normative: true
stability: v1
updated: 2026-07-29
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Client Sync 是客户端 **账号视角聚合** 同步协议。它在 Events API 之上提供跨 Realm 的稳定 delta 视图（包含 to_device、account_data、device_lists、unread / notification counts），由服务端通过 `ak.self.account.stream.subscribe.v1` 的有界长轮询按需返回。它不是裸事件读取——逐 Realm 的事件查询和实时订阅请使用 `ak.self.events.read.scan.v1` / `ak.self.events.stream.subscribe.v1`。

`ak.self.account.stream.subscribe.v1` 与 `ak.self.events.stream.subscribe.v1` 是对称的两类 streaming 订阅:
- `ak.self.events.stream.subscribe.v1` 是**逐 Realm / actor 的事件流**(selector 范围内的每条 Event)
- `ak.self.account.stream.subscribe.v1` 是**账号视角的聚合流**(跨所有 Realm 的 delta 总览 + account-scoped 数据)

两者共享相同的 stream cursor 形态、resume / `dropped` / `resync_required` 恢复语义，差异仅在 selector 与 frame 内容。

本文定义 Arkret v1 的客户端账号同步语义。能力差异由 feature discovery 与 conformance profile 表达；transport path 不携带版本段。

所有 full client 和 E2EE client MUST 支持本文件。

## 2. Endpoint

```http
GET /_arkret/self/account/subscribe?catchup=true
Authorization: DPoP <ak.session.grant>
Accept: application/x-ndjson
```

上面是 **initial account sync** 的 canonical frame 调用：不带 `after`，显式设置 `catchup=true`。这里的 `catchup` 不是"返回全部历史记录"，而是要求服务端先发送当前账号 baseline（有限 timeline + 必要 state + account-scoped 当前位置），本轮预算用尽或到达本轮边界后发送 `catchup_complete`；各 baseline 的完成由 §2.3 分别声明。后续请求使用 `GET /_arkret/self/account/subscribe?after=<cursor>&catchup=true` 进入有界长轮询；收到 `dropped` frame 后的补洞重连使用同一方式。

该端点对应 `ak.self.account.stream.subscribe.v1`，HTTP binding 返回 `application/x-ndjson` 的 `AccountSubscribeFrame` 有界响应。Initial sync 立即返回；带 `after` 的请求若已有可见 delta 也立即返回；否则服务端 MUST 等待数据或部署默认窗口（v1 默认 30 秒）到期，期间不得先发送空 `delta` / `catchup_complete` 使客户端误判本轮已完成。数据到达时返回 delta；窗口到期仍无数据时返回仅推进 cursor 的 `frontier`。`catchup=true` 时本轮数据 frame 后发送 `catchup_complete`，随后关闭本轮响应；客户端持久化 cursor 后立即发起下一轮长轮询。客户端 MUST 把 cursor-bearing frame 的 `cursor` 作为下一次 `after=` 起点。该端点聚合跨 Realm delta、to_device、account_data、device_lists 与 notifications；不同于 `GET /_arkret/self/events/subscribe`（按 selector 的事件流订阅）、`QUERY /_arkret/self/events`（JSON content 携带 `before` / `after` 的双向历史读取）以及独立的加密 Signal rail。三者可以共享 cursor 与授权规则，但 `operation_id`、响应语义与所属 namespace 不同：account 同步在 `ak.self.account.*`，snapshot 入口在 `ak.self.realm_state_snapshot.*`，事件读取在 `ak.self.events.*`（权威 operation namespace 以 [`../../artifacts/registry/operation-registry.json`](../../artifacts/registry/operation-registry.json) 为准，canonical 均带 `ak.self.*` 信任面前缀；`ak.account.*` / `ak.realm_state_snapshot.*` / `ak.events.*` 只是 surface-group 口语简称，不是 wire operation_id）。

Account subscribe 的服务边界是 authenticated session 绑定的 exact `AccountId`，即
`(station_id, principal_id)`。同一 `principal_id` 在不同 Station 上形成不同账号；
客户端必须为每个账号分别维护 session、cursor、to-device queue、push registration 与订阅序列。
Realm timeline / notification delta 只进入其成员 `ActorId` 中 account 分支所指账号的流；不得按裸
`principal_id` 合并，也不得从 DID Document 猜测另一账号。

### 2.1 多账号上下文 UX 指引（SHOULD）

客户端在同一 UI 中聚合多个 AccountId 的 timeline 时 SHOULD 显式区分账号上下文（例如
`Alice @ Acme`、`Alice @ Personal`）。展示可以使用组织 endorsement 的名称或图标代替 raw DID，
但内部选择与比较必须保留完整 AccountId。通知与未读数按 AccountId 分桶；不允许因
`principal_id` 相同而合并两个账号。

请求参数(query string,无 body):

| 参数 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前 principal / device。 |
| `X-Arkret-Wait-For` | header | `cursor` | optional | RYW barrier（purpose=`barrier`）。服务端在发送本轮第一个 account frame 前 MUST 等待 account projection frontier 覆盖 cursor 绑定 target；最长等待当前长轮询窗口（v1 默认 30 秒）。窗口内未覆盖时返回 `temporarily_unavailable` / `timeout` 与当前 frontier，不得先发送会被误认为满足 barrier 的 `delta` / `frontier`。WebSocket profile 的 account `parameters.wait_for` 是本 header 的等价投影。 |
| `after` | query | `cursor` | optional | 订阅起点 cursor(purpose=`stream`,排除语义),从此 cursor *之后* 开始接收 frame。缺省表示没有可恢复账号 cursor。 |
| `catchup` | query | `boolean` | optional | 默认 `false`。`after` 存在时,`true` 表示服务端返回 `after=` 之后到当前 frontier 的账号聚合 delta,再发 `catchup_complete` frame并结束本轮响应；这不是全量历史。`after` 缺省且 `catchup=true` 是 **initial account sync**:服务端 MUST 先发送覆盖当前账号 baseline 的 `delta` frame(Realm 摘要、必要首屏 state、device list baseline、to_device/account_data/notification 当前位置),再发送 `catchup_complete`。完整历史必须通过 `ak.self.events.read.scan.v1` 分页/区间读取。 |
| `filter` | query (JSON value) | `object` | optional | 单个 percent-encoded RFC 8785 JSON object；详情选择按 §2.3，与 events selector 独立。 |
| `filter.realm_ids` | query | `RealmId[]` | optional | 最多 16 个详情 Realm；缺省或空集合不返回任何 Realm 详情，全局通道仍持续。 |
| `filter.strand_ids` | query | `StrandId[]` | optional | 最多 32 个目标，必须属于已选 Realm 且独立授权；缺省选择各 Realm 当前 default Strand。 |
| `realm_list` | query (JSON value) | `RealmListRequest {after?, limit?}` | optional | 摘要快照分页，limit 默认 20、1–100；initial 缺省等价第一页，增量缺省不继续枚举。 |
| `replace_filter` | query | `boolean` | optional | 默认 false；true 必须携 after 与 filter，按 §2.3 原子替换详情兴趣。 |
| `filter.timeline_limit` | query | `int` | optional | 每 Realm 每 frame 默认 20、0–100；按目标 Strand 合并，受全局字节预算裁剪。 |
| `filter.lazy_load_members` | query | `boolean` | optional | 默认 true；成员页最多 100 行，false 也只启动有界分页，不内联完整名单。 |
| `filter.include_redundant_members` | query | `boolean` | optional | 默认 false；true 仍受 100 行和字节预算，不改变名单完整性。 |
| `filter.event_kinds` | query | `string[]` | optional | Event kind allow list。 |
| `filter.not_event_kinds` | query | `string[]` | optional | Event kind deny list。 |

Presence 不属于 account aggregate。客户端通过可选
[`Signal Extension`](./signal.md) 发送和接收加密 presence；`GET
/_arkret/self/account/subscribe` MUST 保持只读，且不得投递 `SignalEnvelope`。

NDJSON 响应 frame 形态(`application/x-ndjson`,每行一个 JSON 对象):

| `kind` | 是否含 `cursor` | 含义 |
| --- | --- | --- |
| `delta` | required | 一次 account-aggregate 增量推送(realms / to_device / account_data / device_lists / notifications)。客户端 MUST 把 `cursor` 作为下次重连的 `after=` 起点。 |
| `catchup_complete` | required | 本轮有界 catch-up 交付结束；不声明全部账号或 Realm baseline 完成。`catchup=true` 才会出现;`catchup=false` 时不会出现。 |
| `frontier` | required | 仅推进 cursor,不带数据；用于带 `after` 的长轮询在默认 30 秒窗口无变化时完成本轮响应。 |
| `heartbeat` | absent | 防中间层断流的 keepalive。 |
| `dropped` | required | 服务端无法从当前 cursor 继续推送(buffer 溢出 / 服务重启等),`cursor` 是建议的 account catch-up 起点。`dropped` frame 的 `cursor` 为 REQUIRED;服务端没有可用补齐 cursor 时 MUST 改发 `resync_required`,不得发送无 cursor 的 `dropped`。客户端 MUST 重新建立 `ak.self.account.stream.subscribe.v1?after=<cursor>&catchup=true` 重放账号聚合 delta;若重放后的某个 Realm timeline 仍标记 `limited=true`,再用 `ak.self.events.read.scan.v1` 按该 Realm 的 `prev_cursor` / `next_cursor` 补齐裸 Event 缺口。MAY 携带 `reconnect_after_ms`。 |
| `resync_required` | absent | 服务端无法定位任何可用 catch-up 起点(本地状态彻底失效)。客户端 MUST 清空本地 cursor 缓存，从零重新建立订阅。MAY 携带 `reconnect_after_ms`。 |
| `unauthorized` | absent | 当前 session 不再有权限消费该流；客户端 MUST 重新认证或退出。 |

frame schema 见 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json)(`ak.schema.account_subscribe_frame.v1`)。

> **与 `ak.self.events.stream.subscribe.v1` 帧集合的差异**：account-aggregate 流**有意不**包含 `ak.self.events.stream.subscribe.v1` 的 `event` 与 `epoch_rotation` 控制帧。self.account.stream.subscribe 是跨 Realm 聚合视角，MLS epoch 变化不作为独立控制帧出现，而是在各 Realm `delta` 内通过当前 MLS epoch cell 结果 / `state_at_window_start.e2ee_epoch`（见 §5）表达；需要逐 Realm 的 `epoch_rotation` 边界提示时使用 `ak.self.events.stream.subscribe.v1`。其余控制帧（`catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`）与 `ak.self.events.stream.subscribe.v1` 对齐。

`delta` frame 示例:

```json
{
  "kind": "delta",
  "cursor": "ak:cursor:<opaque-valid-stream-cursor>",
  "realms": {
    "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5": {
      "timeline": {
        "events": [],
        "limited": false
      },
      "state": {"events": []},
      "account_data": {"events": []}
    }
  },
  "to_device": {"messages": []},
  "device_lists": {"changed_ids": [], "left_ids": []},
  "account_data": {
    "events": [],
    "station_cas": {"upserts": [], "removals": []}
  },
  "notifications": {"items": []}
}
```

控制 frame 示例:

```text
{"kind": "catchup_complete", "cursor": "ak:cursor:..."}
{"kind": "frontier", "cursor": "ak:cursor:..."}
{"kind": "heartbeat"}
{"kind": "dropped", "cursor": "ak:cursor:...", "reconnect_after_ms": 5000}
{"kind": "resync_required", "reconnect_after_ms": 10000}
{"kind": "unauthorized"}
```

`realms` MUST 是以 `ak:realm:*` 为 key 的对象；value 是该 Realm 的聚合同步结果。membership state 的完整枚举是 `join` / `knock` / `leave` / `ban`，它们是事件 payload / `ak.member.state` projection 取值，不再作为 `realms` 外层 bucket；其中只有 `join` / `knock` 进入 roster（`member_roster.entries[]`），`leave` / `ban` 不进入 roster（见 §8.1 roster `member_roster.entries[]` 定义）。Invite 是独立 pending workflow，只能从调用方私有 Invite inbox / delivery projection 展示，不得推造 membership cell 或 roster row。Realm-scoped `account_data` 使用事件容器形状；当前状态仅使用 [current results](./current-results.md) 的闭合类型，不携 `state` / `state_after`：

```json
{
  "events": []
}
```

顶层 `account_data` 使用闭合双分支 `{events, station_cas?}`：`events[]` 只承载 durable holder-authored actor-private `Event`；`station_cas` 只承载 registry 中 `writer_authorities` 含 `station_cas` 的行，形状为 `{upserts, removals}`。两类真相源不得互相合成或镜像。
`SignalEnvelope` 只出现在 `ak.self.signal.stream.subscribe.v1`，不得为了复用本流容器而包装
成 durable Event，也不得恢复旧的 presence/receipt/call 聚合对象。
`ak.profile.signal_message_stream.v1` 的 `ak.message.stream` 正文预览同样只在该 Signal rail
解密后处理；它没有 account/events cursor、catch-up、ack 或 backfill。客户端的丢帧恢复、
attempt 选择与 final 替换 MUST 按 [`signal.md` §7](./signal.md#7-message-正文流式预览-payload-profile)
执行，不得把预览写入 `timeline.events[]`。

顶层 `notifications` 与 `to_device` 都不是事件容器。`notifications` 使用 §3.1 的闭合 `{items: NotificationDelta[]}`，其中的普通当前行与 Agent approval 共用同一条通道；`to_device` 使用 `DeviceMessageEnvelope[]` 承载形态 `{messages, ack_token?, limited?, next_cursor?, lost?}`，schema 为 `account-subscribe-frame.schema.json#/$defs/device_message_container`。两者中的对象均不得作为 durable Event Envelope 处理。

### 2.2 连接管理与重连

客户端 MUST 维护一个连续的 `/_arkret/self/account/subscribe` 有界长轮询序列，并:

1. **原子持久化 frame 与 cursor**: 客户端 MUST 在同一本地事务中持久化 frame payload(timeline 事件、state、account_data、device_lists 等)与该 frame 的 `cursor`,之后才把它用作重连 `after=` 起点;MUST NOT 在 payload 落盘前单独推进本地 cursor 高水位。`account_data.station_cas` 的 upsert/remove 与 revision 高水位也属于这笔事务。"先存 cursor、后落数据"的实现会在崩溃时产生本地静默缺口——其中 `device_lists` 或 Station-CAS 缺口只能靠重做 initial sync 恢复。to-device 消息的投递安全由 §10.1 显式 ack 在协议层保证，不依赖本条；但 SHOULD 同样与 cursor 同事务落盘以减少重连后的重复处理。仅带 cursor 不带数据的 frame(`frontier` / `catchup_complete`)直接更新本地高水位即可。
2. **正常续轮与网络断开**: 正常收到 `delta` / `frontier` 并完成本轮响应后，若没有服务端 `reconnect_after_ms` 或 HTTP `Retry-After` 指令，MUST 立即用最近 `cursor` 作为 `after=` 发起下一轮请求，并设置 `catchup=true`；网络断开时使用相同规则重连，确保断线期间的账号聚合 delta 不被跳过。若服务端返回 `cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized`,按 §12.3 恢复。客户端 MUST NOT 在服务端 30 秒等待窗口之外再固定 sleep 5 秒，否则会平白增加实时延迟。
3. **`dropped` frame**: 用 frame 自带的 `cursor` 重新建立 `GET /_arkret/self/account/subscribe?after=<cursor>&catchup=true`,让服务端重放账号聚合 delta；若 frame 携带 `reconnect_after_ms`,MUST 先等待该时长。不得只用 `ak.self.events.read.scan.v1` 恢复，因为 `to_device`、`account_data`、`device_lists` 与 notifications 不属于裸 Realm Event 查询面。
4. **`resync_required` frame**: 清空本地 cursor 缓存，重新建立连接(`after=` 缺省 + `catchup=true`)执行 initial account sync;若 frame 携带 `reconnect_after_ms`,MUST 先等待该时长。大型 Realm 的当前态可走 snapshot bootstrap,见 §12.3 与 §13。
5. **`unauthorized` frame**: 关闭连接，触发 session 刷新或退出登录。
6. **建议 reconnect 退避**: 指数退避，起始 1s,最大 60s;`dropped` / `resync_required` 未携带 `reconnect_after_ms` 时可立即重连以缩短数据不一致窗口。客户端收到 `reconnect_after_ms`、HTTP `Retry-After` 或错误 body `retry_after_ms` 时，MUST 优先遵守服务端指令，并 SHOULD 加 jitter 避免同批客户端同步重连。

`reconnect_after_ms` 是 200 stream control frame 内的重连保持时间，不是错误响应字段。服务端发送后 MUST 按至少 `(account_id, device_id, operation_id, filter_digest)` 维度强制执行；在保持时间内的同 scope `/_arkret/self/account/subscribe` 请求 MUST 返回 `429 rate_limited` 并设置 `Retry-After`，且不得推进 account subscribe position、barrier wait 或 dropped recovery state（to-device 队列删除只由 §10.1 显式 ack 驱动，本就与 subscribe cursor 无关）。服务端 MAY 在实现中加入 source IP / session id / trust domain 等更细维度，但不得把该限制扩大到无关 API。

### 2.3 按需列表、详情与分段 baseline（normative）

本节是同一 v1 account subscribe 的默认合同，不定义第二个同步 endpoint/profile。请求是 closed
`AccountSubscribeRequest {after?, catchup?, filter?, realm_list?, replace_filter?}`；HTTP query 与
WebSocket account open parameters 使用同一字段名（`filter.realm_ids`，删除旧 HTTP `realms` 别名）。
WebSocket `wait_for` 仍是 HTTP header 的投影。未知字段拒绝；`subscriptions` 不恢复为扩展旁路。
HTTP 的 filter 与 realm_list 各自是至多出现一次的 query parameter，值为 percent-encoded RFC 8785 canonical JSON object；
先按 query percent decoding 一次，再检查 UTF-8、重复成员、canonical bytes 和 closed schema。`filter={}`、
`filter={"realm_ids":[]}` 与 `realm_list={}` 均可无歧义表达；传输时花括号/引号等按 URL 编码。
标量 after/catchup/replace_filter 仍是普通单值 query；任何重复参数、未知参数、旧 filter.* / realm_list.* dotted 参数
或 bracket/deepObject 别名均 param_invalid，不能静默忽略。JSON 缺省、显式空对象、空数组和 false 按原样保留，
不以私有哨兵、空字符串或补写默认字段替代。WS account parameters 直接携同一 JSON 对象，不额外字符串化。


**列表与当前权限。** 无 account after 的 initial 请求缺省读取第一页；增量请求只有显式 realm_list 才取新页。
`RealmListRequest {after?, limit?}` 的 after 仅接受本列表签发的 continuation；缺省建立新冻结快照，limit 默认 20、范围 1–100。
`realm_list` 结果为 `RealmListPage {snapshot_cursor, snapshot_revision, items, next_cursor?}`；仅以 next_cursor 存在表示还有下一页；
存在 next_cursor 时 items MUST 非空。`snapshot_cursor` 只标识本列表快照，不是账号恢复位置；不得放入 account after。
items 为 closed `RealmRow {realm_id, revision, activity_position, membership, title?, default_strand_id?}`，
只返回本 exact authenticated ActorId 当前合法可见的 join/knock Realm；pending Invite 仍走私有 inbox。
knock 只含该状态依法可见的摘要，不泄露成员级 title/default Strand；无权限字段省略不表示其不存在。

服务器在首个列表页冻结有界读索引的 snapshot watermark，输出 snapshot_revision（只用于新旧行比较，不是 cursor）；按 `activity_position` 降序、相同时 RealmId
无符号 UTF-8 升序选页。activity_position 是持久账号摘要投影的单调非负安全整数，发生可见摘要变化时分配；
不得采用客户端时间或从消息历史临时排序。revision 是该 Realm 摘要及失效记录共享的持久严格递增账号位置。
翻页复用冻结顺序和内容，但每页交付前重新检查当前读取权限；撤权项略过；join 降为 knock 时仅可返回当前 knock 允许的字段，不得交付冻结 join 行中的私有 title/default Strand；扫描继续位置仍前进，允许空非终页。
每次最多扫描 200 条索引记录，达到扫描/输出条数或 1 MiB canonical 列表页字节预算后返回继续位置；
不得 offset 扫描、建立全账号内存快照或读取全部消息后再切片。快照/版本行的持久保留必须覆盖所签 cursor 的生命周期；
不能继续时按既有 cursor_expired/unrecognized/integrity_invalid 恢复，不冒充空终页。

`realm_list_changes {upserts, removals}` 是不受详情 filter 影响的账号增量；removal 为 `{realm_id, revision}`。
两数组合计最多 100 项，按 revision 升序（同 revision 按 RealmId 字节序），同 Realm 在一 frame 只保留最后结果。
从持久 account-summary change index 有界读取，cursor 只推进已交付前缀或已证明不向该账号披露的记录。
首次建立 account baseline 与列表 snapshot 的位置必须来自同一读取边界；cursor 保留此后的摘要变化，分页期间持续交付。
客户端按 RealmId/revision 合并：较旧快照行不能覆盖已安装新 upsert/removal，重复行幂等。
列表完成仅说明冻结列表枚举结束，不能删除快照后新增项；重做列表需按同一 snapshot 分段暂存已见键，终页才删除
未见且不晚于该快照的旧项。快照期间的较新 tombstone 保留到该快照失效/完成，不能因消息重排复活 leave Realm。

**详情兴趣。** filter.realm_ids 最多 16 项，缺省/空集合表示无详情，彻底删除“None/空等于全部 Realm”语义。
filter.strand_ids 最多 32 项，每个必须属于某个已选 Realm；服务器分别检查目标 Strand 及其 effective scope 的当前读取授权。
不存在/不可见目标统一 not_found，不因本 API 披露父 Realm/私有 Circle；非法跨 Realm 组合 param_invalid。
省略 strands 选择各已选 Realm 在该 baseline basis 下的当前 default Strand；Realm 没有合法默认目标时只交付
合法摘要/当前 Realm 结果，目标状态仍 pending，不猜测首个 Strand。显式 strands 选择只影响所列目标；其余 Realm 可只有
必要 Realm 当前结果。相同目标去重，重叠 UI 消费者在客户端合并需求：timeline 取最大，成员需求取并集并受硬上限。
state 只交付 Realm 与所选目标的当前对象/操作必要结果及当前窗口显示依赖，不内联所有 Strand/旧修订/全 roster。
filter 的 kind allow/deny 只裁剪 timeline，不裁掉安全基线、失效或账号通道。成员页最多 100 行，limited/next_cursor
沿既有 member_roster 合同；lazy_load_members=false 也不能突破分页预算。名单未列出不是 leave。

**兴趣替换。** 普通 after 仍严格绑定原 filter_digest。replace_filter=true 必须显式携 after 与完整新 filter，
服务器先认证 cursor 的签发 Station、exact AccountId、device/session 及 operation/purpose/TTL/revoke，只有 detail
filter 不同可按本分支转换；不能跳过其它绑定，也不能把列表/history/to-device cursor 当旧账号位置。
转换保留账号全局位置及仍适用的 Realm 位置；新目标、增大的 timeline/成员需求、默认目标变化立即建立局部 baseline，
即使没有新 Event 也必须补发，不等待下一次写入。缩小/移除只停止详情交付，不产生 leave/removal，不取消已提交操作。
旧 cursor 保持不可变；exact 请求重试产生相同逻辑 cut/补发范围，派生 token 可不同。新 cut 建立与 delta 起点须原子读取，
期间撤权/Commit 不得丢失。SDK 记录本请求的规范化 filter_digest，客户端以
会话 generation、请求序号与已选 filter_digest 拒绝迟到响应，未安装响应的 cursor 不能覆盖当前 cursor。取消旧请求后仍从最后
已安装 cursor 转换。不得用清空全账号 cursor 实现每次切换。HTTP 与 WS 重开 channel 使用完全相同合同。

**全局安全与分段完整性。** `realm_invalidations` 为最多 100 项的 `{realm_id, revision}`；scope 权限、membership/
incarnation、key-access、相关 quarantine 等变化使该账号已有该 Realm 当前结果失效时，通过账号持久投影发送。
仅对账号已可见或已收到过的 Realm 披露 ID。它不包含新授权、不等同 leave；客户端暂停受影响操作并重新查询自己 Station。
真正 leave/ban/隐藏变化还发列表 removal。全局设备/会话撤销、to-device/ACK、account data、通知和已知 Realm 失效
均不受详情窗口过滤；增量同样分段，cursor 不得一次跳过未安装的尾段。消息范围缩小不删除本地合法保留的历史。

账号 baseline 使用 `baseline {snapshot_cursor, channels, completed_channels}`，channel 闭合集合为
`account_data_events | station_cas | device_lists | notifications`。channels 非空，completed_channels 必须是其子集。
同一 snapshot 内每通道可跨 frame/round；携数据的该通道属于本快照，不能在同 frame 混入该通道更新 delta。
更新 delta 可在快照分段之间立即交付；客户端按键保留快照后更新覆盖，不能让后到的旧 baseline 覆盖撤销或新值。
相同快照的所有分段持久安装后，只有 completed_channels 声明的通道才允许清理未出现旧项；中间页、空中间页及
catchup_complete 不清理集合。零项通道也显式完成。移除 station_cas.complete，避免两个不一致的完成载体。
详情 `realms[id].baseline {snapshot_cursor, cut_revision, coverage, complete}` 按 [current results](./current-results.md) 的精确覆盖和版本规则声明目标当前结果交付完成；
不授予读取/发送，不声称 timeline、全部成员或其它 Realm 完成。该 Realm 失效通知到达后，旧 baseline 的后续段/complete 不能解除 pending；必须重建当前目标 baseline，丢弃旧 snapshot 的迟到段。current query/MLS 仍按各自逐操作 gate。
快照标识与 cursor/context 一起原子安装；本地不得只保留最后一段冒充整套 baseline。不得自动继续枚举列表来完成账号 baseline。

**固定预算与继续。** 每 canonical account frame ≤8 MiB，每 HTTP round ≤16 MiB 且 ≤16 frames；编码 wire 单 frame
≤16 MiB，读取/解析前执行上限。客户端 pending ≤2 frames 且 ≤16 MiB canonical，满时 backpressure；服务端 pending
同上，无法续传时 dropped/resync_required。WS account data 的 payload 遵循同限额，若协商 WS frame 更小则使用 HTTP，
不得截断 frame。列表页 ≤1 MiB，列表/变更/失效各 ≤100 项（列表索引扫描 ≤200）；state/account-data/device/notification
单集合每 frame ≤100 项，timeline 每 Realm 默认20、0–100；全部同时受 frame/round bytes 裁剪。大 Event 仍遵守既有
1 MiB envelope 上限，不降低或截断 MLS 原子材料；一个合法最大 Event 应可置于空 data frame 后推进。
若附加证据/状态超过 frame，移至后续分段/现有明确的按引用读取合同，不能悄悄丢项或无限空页；不存在合法分割方式时
只令该目标当前结果不可用并返回现行 limit_exceeded，服务器仍交付其它通道，不能循环推进该目标 cursor。其唯一载体是 `realms[id].unavailable {error_code}`，
error_code 闭合为 frontier_unavailable/limit_exceeded/temporarily_unavailable/not_found；该 entry 不得同时携其它详情字段。
not_found 对不存在/不可见统一，且仅可回显调用方明确请求的 Realm ID，不能枚举未知对象。
只要存在可交付项，每轮必须交付至少一项或明确恢复错误；达到预算时 cursor 保留所有未完成子通道的继续位置，下一轮立即续取。
服务器保留 P0 安全/交付控制独立配额，摘要/当前目标有公平最低配额；单个冷 Realm 的治理验证不能占满全局读取工作池。
HTTP 30 秒等待只适用于没有可交付增量/未完成 baseline/显式列表页；存在上述工作立即返回有界 round。

最近窗口缺更早内容使用既有 limited/prev_cursor，不强制回填到 Realm 创建。history gap、列表页未完、state 分段未完是
三个独立事实；只有需要该目标 state 的操作等待相应 baseline。当前消息发送不等待旧消息、完整名单、头像或其它 Realm。

## 3. Stream Classes

Account subscribe `delta` frame 包含以下 stream：

| Stream | 持久性 | 用途 |
| --- | --- | --- |
| `timeline` | 持久 | Realm 内 accepted events |
| `current` | 持久投影 | 服务器已裁决的完整 cell/object 当前结果、因果 heads、移除及不可用 |
| `state_at_window_start` | 派生 | `timeline.limited=true` 时 window 起点 seal 状态，见 §5 |
| `account_data` | 私有持久 | 标签、UI 偏好、recent emoji、push rules |
| `to_device` | 设备队列 | key verification、secret sharing、device messages（队列删除只由 §10.1 显式 ack 驱动，不随 cursor 推进） |
| `receipts` | 可配置 | actor-private read cursor delta（逻辑类，无独立 wire 字段；承载于 per-Realm `account_data`；加密 read receipt 走独立 Signal rail） |
| `notifications` | 派生 | 账号 inbox 当前行与 Agent runtime approval delta（§3.1） |
| `device_lists` | 持久 delta | E2EE device trust 更新 |
| `applet` | 持久 | Applet delivery receipt、bridge health（逻辑类，无独立 wire 字段；承载于 per-Realm `timeline`，见下表） |
| `blob_status` | 派生 | upload scan、thumbnail、retention 状态（逻辑类，无独立 wire 字段；承载于 per-Realm `timeline`，见下表） |

客户端 MUST 使用 `cursor` 作为唯一 resume token，不得解析 token 内部结构。

**各 stream class 在 frame 中的承载位置**（与 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json) 对齐）：

| Stream | 承载位置 |
| --- | --- |
| `timeline` / `current` / `state_at_window_start` | per-Realm：`delta.realms[<realm_id>]` 内的同名字段（§4） |
| `to_device` / `device_lists` | `delta` 顶层同名字段（跨 Realm，不分桶到具体 Realm） |
| `account_data` | 双位置：Realm-scoped 私有数据进 `delta.realms[<realm_id>].account_data`；account-scoped 进 `delta` 顶层 `account_data` |
| `receipts` | per-Realm：actor-private `read_cursor` 高水位承载于 `delta.realms[<realm_id>].account_data`；`ak.receipt.read` 只走独立 Signal rail，不进入本 frame |
| `notifications` | `delta` 顶层 `notifications`；per-Realm 未读计数另由 `delta.realms[<realm_id>].unread_notifications` 表达（§4） |
| `applet` | per-Realm 派生：Applet delivery receipt / bridge health 作为对应 Realm 的事件随 `delta.realms[<realm_id>].timeline` 投递 |
| `blob_status` | per-Realm 派生：upload scan / thumbnail / retention 状态作为对应 Realm 的派生事件随 `delta.realms[<realm_id>].timeline` 投递 |

顶层 `delta` 与 per-Realm entry 都是 closed DTO（`additionalProperties:false`）；上表及 `account-subscribe-frame.schema.json` 给出 v1 全部 canonical 承载位置，实现不得自行另设字段或外层分桶。新增 stream class 必须先登记并更新 schema/profile；`receipts` / `applet` / `blob_status` 不在顶层 `delta` 另立独立 bucket。

`device_lists` 的 wire 形态固定为 `{changed_ids: ActorId[], left_ids: ActorId[]}`。两个数组都 MUST 存在，并按完整 ActorId 去重；元素不是裸 principal DID 或 `device_id`。`changed_ids` 表示该完整 Actor 的权威 device list 已变化，客户端 MUST 通过该 ActorId 携带的 Station 路由重新查询对应设备投影；`left_ids` 表示该完整 Actor 已离开调用方可见范围，客户端 MUST 只删除该 Actor 的缓存设备信任投影。同 DID 在其他 Station 的 Actor 不得被合并、误刷新或一并删除。此跨 Realm 的可见性 delta 不等同于 Station-local `to_device` 消息发送请求中的 principal map key（见 `crypto-media/device-lifecycle.md` 的 `ak.self.device_messages.command.send.v1` 边界）。

`notifications` 和高频 actor-private `read_cursor` delta MAY 被服务端合并；同一 scope 在一个 account subscribe frame 内只需要返回最新可见位置和最终 unread count。加密 `ak.receipt.read` 不在本流中，服务端不得解密或对其做语义合并。客户端不得要求服务返回每一次中间 private read-cursor 变化；`cursor` 只承诺覆盖 frame 中声明的最终 stream positions。

### 3.1 Account notification delta（normative）

顶层 `notifications` 的 wire 形态固定为 `{items: NotificationDelta[]}`，不再复用 `{events: EventEnvelope[]}`。`NotificationDelta` 是闭合对象 `{id, action, data?}`：`action` 只能为 `upsert | remove`，`id` 形态是唯一分支判别式——`ak:notification:<uuidv7>` 选择 §3.1.1 的 Agent runtime approval 分支，`ak:notification_projection:<44 字符 token>` 选择 §3.1.2 的普通源 Event 当前行分支。v1 只有这两个分支；容器不携带没有分支选择作用的 notification/data kind 镜像，也不存在第二套通知列表 operation：`ak.edge.push.command.notify.v1` 是投递面，权限 action `ak.notification.read` / `ak.notification.ack` 不是 operation，两者都不能当作通知读取入口。

- 校验顺序 MUST 是先按 `id` 形态选定分支、再按该分支校验 `data`。分支交叉（`ak:notification_projection:*` 携 Agent approval data，或 `ak:notification:*` 携普通当前行）MUST fail closed，不得按另一分支解释。
- 客户端 projector MUST 按 `upsert=按同 id 插入或完整替换`、`remove=删除` 应用 delta；把所有 action 都当 insert 的实现不得声明支持该 notification delta。
- 两个分支共用同一条通道：同一 `items[]` 数组、同一严格单调 projection position、同一 `baseline` 的 `notifications` 通道，以及 §2.3 的每帧 count/bytes 与 round/frame 预算（该集合每 frame ≤100 项，并同时受 frame/round 字节裁剪）。服务端不得为其中一个分支另开集合、另开 cursor 或另设配额。
- Notification 是 account-private projection，不是 Realm Event。服务端必须从认证的 provision/session 上下文派生接收者（`controller_account_id` / `recipient_id`），调用方不得提交它们；selection、session 与 cursor 必须直接绑定完整 `AccountId`，不得另以裸 principal 加本地账号 sidecar 拼接。本通道不受详情 Realm 窗口与 `filter` 过滤（§2.3）。

#### 3.1.1 Agent runtime approval 分支（`ak:notification:<uuidv7>`）

- `upsert` 的 `data` MUST 含 `approval_request_id`、`agent_id`、`requested_at`、`expires_at`，并且不得含 pairing code、runtime public key、PoP、attestation、display name 或 slug。客户端必须在显示和审批前通过认证的 `ak.self.agent.resource.get.v1` 读取当前完整投影。
- `remove` 的 `data` MAY 省略；若存在，必须是闭合 `{reason}`，其中 `reason` 只能为 `approved | expired | renewed | deactivated | superseded`。
- `upsert` 后，客户端 MUST 重读 Agent，要求当前 `approval_request_id` 相同、`key_state.pairing_request_id` / `pairing_expires_at` 共同表明 pairing 仍 open 且未过期，并要求通用 `agent.readiness.blockers` 含 `pairing_open`；当前 active authorization 集合为空时还必须含 `runtime_key_missing`；非空时必须披露将被精确 supersede 的 key 与授权 Event，并显示 runtime key replacement 警告。通用 view/key_state 不含 `runtime_state`；该字段只在 runtime pairing poll 响应出现。lifecycle 意图与 open handle 不互锁，pause / resume 不被 replacement 阻塞。服务端在 handle consumed 或过期后 MUST 原子清除上述 open-handle 投影（以及 `pairing_code`）并重算 readiness。审批前 MUST 再次读取或依赖服务端 current-request CAS。匹配 `remove` 必须关闭 prompt并清除本地缓存。Local dismiss 只影响当前设备 UI，不写 durable dismissed state。

该分支的 notification 没有 `realm_id`，不得经过 `realm_id_accessible`。

#### 3.1.2 普通源 Event 当前行分支（`ak:notification_projection:*`）

`upsert` 的 `data` 是闭合对象 [`notification.schema.json#/$defs/ordinary_projection_content`](../../artifacts/schemas/notification.schema.json#/$defs/ordinary_projection_content)，逐字复用 `ak.schema.notification.v1` 的字段形状，只承载接收者自己 Station 能权威声明的内容：`realm_id`、`source_event_id`、`notification_kind`、`priority`、`created_at` 必填，`source_ref`、`strand_id`、`track_name`、`preview`、`updated_at` 可选。它不重复 `id`（由该行的 `id` 承载）、不携 `schema`、不携 `actor_id`（接收者就是本次认证账号）、也不携 `state`。`notification_kind` 是 `ordinary_notification_kind` 的 11 值子集；`invite` 走独立的私有 Invite delivery 载体，`agent` 属于 §3.1.1，二者都不出现在本分支。

`remove` 的 `data` 是闭合 `{reason}`，MUST 存在，`reason` 只能取：

| `reason` | 含义 |
| --- | --- |
| `source_removed` | 源 Event 被 redact / tombstone，或已超出该账号对该来源的历史可见范围。 |
| `access_revoked` | 接收者对该源 scope 的当前读取授权消失（leave / ban / 能力撤销 / quarantine / key-access 变化）。 |
| `expired` | 部署的通知保留边界把该行挤出当前集合。 |
| `superseded` | 同一 source Event 已由更具体 `notification_kind` 的投影按 [`../models/private-objects.md` §3.3](../models/private-objects.md) 的去重规则取代。 |

`reason` 只表达服务端可观测的原因。read / dismissed / archived 是 holder-private inbox 处置，永远不产生 `remove`，也不写入本通道。

**身份与去重。** `items[].id` MUST 是 [`../discovery/read-receipts.md` §6.3](../discovery/read-receipts.md) 与 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `notification_projection` 派生结果。客户端 MUST 用自己的完整 `AccountId` 与该行的 `realm_id` / `source_event_id` / `notification_kind` 重算该 token 并逐字节比较；不一致 MUST 丢弃该行且不得安装，同时不得因此删除已安装的其它行。同一 `(接收账号, realm_id, source_event_id, notification_kind)` 至多一行；重复 `upsert` 是整行替换，不是追加。

**当前授权与 preview。** 服务端 MUST 在构造每个 frame 时按接收者的**当前**读取授权重新判定该行，冻结的列表页与 baseline 分段同样适用：授权收缩后 MUST NOT 因为源 Event 在冻结时刻曾可见就交付该行或其 `preview`，MUST 改为交付 `remove` 并把 `reason` 置为 `access_revoked`。`preview` 仍遵守 [`../models/private-objects.md` §3.4](../models/private-objects.md)：E2EE / redaction / history-limited 下必须为空或已授权脱敏摘要，服务端不得解密源正文重建 preview，也不得借通知投影扩大源 Message 的明文可见性。若 `preview` 使该行超出 §2.3 的 frame 预算，服务端 MUST 省略 `preview` 后交付该行，MUST NOT 丢弃该行或让通道停滞。

**与 holder-private inbox 的合并（唯一状态真源）。** 本分支只承载当前可见性与内容，不承载 inbox 状态：

- `read` / `unread` 仍由 read cursor 派生；`dismissed` / `archived` 仍只写 `ak.notifications.inbox.<notification_id>`（[`../discovery/client-preferences.md` §3.2](../discovery/client-preferences.md)，按 account-data CAS 收敛）。该 key 尾部的 `<notification_id>` MUST 与本行 `id` 完全相等。
- 客户端展示用的 `ak.schema.notification.v1` 对象由客户端本地组合：`id` 取该行 `id`，`schema` 取常量，`actor_id` 取本账号完整 account ActorId，`state` 由上述两个私有真源重算，其余字段取 `data`。服务端不得代填 `state`，也不得把 inbox 处置写进本通道。
- 当前行与 inbox key 是两条独立记录：inbox 条目存在但没有当前行时 MUST NOT 复活该通知；当前行存在而没有 inbox 条目时按 read cursor 派生 `unread` / `read`。
- 收到 `remove` 后客户端 MUST 删除本地当前行；对应的 `ak.notifications.inbox.<notification_id>` MAY 由持有者客户端按 account-data CAS 自行删除，服务端 MUST NOT 代写或代删该 key。
- 本分支不改写源 Event、不生成 recipient-authored Event，也不进入 `account_data.events[]`。

**分页冻结期的覆盖规则。** baseline 分段或列表分页进行中发生的 read / archive 只落在 account-data 通道，本通道的任何分段都不携带、也不重置 inbox 状态。分段进行中发生的 `remove` 或新 `upsert` 作为更新 delta 立即交付；客户端 MUST 按 §2.3 保留快照之后的更新，较晚到达的旧快照分段只记为「该快照已见键」，MUST NOT 用旧内容覆盖新 `upsert`，更不得复活已删除行。

#### 3.1.3 通道位置、baseline 与增量（两分支共用）

每次 upsert/remove 都 MUST 在持久化事务中分配严格单调的 notification projection position；不得用可改写的 `created_at` 加 id 拼 position。两个分支共用同一序列，opaque account cursor 内部保存其 high-water。

Initial sync 的 `notifications` baseline MUST 覆盖当前 account context 下该通道的完整当前集合：全部仍 open 的 `agent_runtime_approval`，以及接收者当前仍可见的全部普通当前行，都作为 `action=upsert` 交付。该集合按 §2.3 分段，可跨 frame/round；客户端仅在 `baseline.completed_channels` 包含 `notifications` 后，才删除同一快照所有已安装分段均未出现且未被更新 delta 覆盖的行。中间页、空中间页与 `catchup_complete` 都不触发删除。Incremental sync 只返回 cursor position 之后的变化；终止 tombstone 至少保留到 account cursor 最大生命周期加安全窗口。填不满 `after` 到当前 frontier 的区间时 MUST 返回 `dropped` / `resync_required`，不得静默跳过。

普通当前行的集合 MUST 有界：服务端按部署保留边界从最旧开始逐出，逐出 MUST 以 `reason` 为 `expired` 的 `remove` 显式表达，不得静默消失；源 Event redaction、retention 到期与当前授权收缩同样必须发出对应 `remove`。该逐出不适用于 Agent approval 子集：即使普通通知历史受限，也不得截断仍 open 的 approval。

服务端提交 projection 事务后 MAY 发 account-context-scoped 内存 wakeup 以降低长轮询延迟。持久 projection 与 cursor 是权威；丢失 wakeup 后，有界 long poll 超时或重连必须仍可从 durable position 恢复，不要求仅为 wakeup 建 durable outbox。Push provider 只能收到现有 blind wakeup，notification body、preview、Agent DID 和 approval id 均不得进入 provider-visible payload。

### 3.2 Agent signer 按需结果（normative）

self account-subscribe 不再携 `agent_signer_evidence_bundle` 或公开治理闭包。需要 Agent signer key 的客户端按 [server-trusted-results §5.6](server-trusted-results.md#56-按次-current-与精确历史签名公钥) 向自己的 Station 查询：current 每次验证发起查询，只允许同次/在途合并，不把结果用于未来 Signal；historical 绑定 exact Event/receiver/完整 actor/method，并允许精确缓存。Event 不新增字段，也不把结果写入 producer canonical bytes。Station 验证公共授权，客户端保留真实 producer signature、MLS、TTL、AAD/AEAD 与 replay。Peer portable evidence 与服务器验证不受 self 字段删除影响。

Station 按本次请求者当前读取资格披露 exact historical key；不得借 initial sync 枚举 Agent 私有
scope，也不得因历史 signer 已退出而把有效历史签名判为未授权。minimal-metadata Realm bucket 不触发
ordinary Agent/device principal 查询。历史缓存按完整 recipient Account、Realm、实际 signer ActorId、
verification_method、event_id、receiver_id 和 frozen signer_evidence_ref 绑定；同坐标冲突不得覆盖成
已验证。缺项保持本次任务 verification_pending，不降级为当前 directory 或 MLS leaf-only 授权。
current 结果不跨消息缓存；backfill 和 live 按需处理都保留真实 producer/MLS 内容密码学。

`realms` 不按 membership 做外层分桶；它始终以 `ak:realm:*` 为 key。当前 membership 是每个 Realm bucket 内的状态字段 / `ak.member.state` projection，取值可为 `join`、`knock`、`leave` 或 `ban`（完整枚举见 §2 首次定义），不得把这些值提升为 `realms` 的外层 key。待处理 Invite 只来自调用方私有 Invite inbox，不是该字段的第五种取值。

每个 Realm 响应：

```json
{
  "timeline": {
    "events": [],
    "limited": false,
    "preview_only": false,
    "prev_cursor": "ak:cursor:<opaque-valid-stream-cursor>"
  },
  "current": {"entries": []},
  "state_at_window_start": {
    "actor_profiles": [],
    "realm_metadata": {},
    "e2ee_epoch": null
  },
  "account_data": {"events": []},
  "summary": {
    "joined_member_count": 12,
    "heroes": ["did:webvh:..."]
  },
  "member_roster": {
    "entries": [],
    "limited": true,
    "next_cursor": "ak:cursor:<opaque-valid-stream-cursor>"
  },
  "unread_notifications": {
    "notification_count": 3,
    "highlight_count": 1
  }
}
```

如果 `timeline.limited=true`，客户端不得假设历史连续；只有用户请求更早窗口或当前内容所需依赖时才使用 backfill / pagination，limited 本身不触发全历史加载。服务端 SHOULD 在响应中提供 `prev_cursor`、顶层 `cursor`、`realm_state_snapshot_frontier` 或等价恢复提示。若 cursor 本身已失效，必须返回 `cursor_expired` 或 `cursor_integrity_invalid`；若 cursor 仍有效但当前服务状态暂时不能完成恢复，则返回 `frontier_stale` 或 `temporarily_unavailable`。服务端不得静默退化为不完整状态，客户端 MUST 按以下分支区分处理：

- `cursor_expired` / `cursor_integrity_invalid`：cursor 本端状态失效（TTL 超时或 tamper / 未知 handle / cross-binding）。客户端 MUST 清空本地 cursor 缓存并从 initial sync 重做（重新建立 `ak.self.account.stream.subscribe.v1`，`after=` 缺省 + `catchup=true`），与 §12.3 一致；不能用旧 cursor 继续 backfill。
- `frontier_stale`：cursor 本身仍有效，只是服务 frontier 落后于请求所需 causal frontier。客户端 MUST NOT 清 cursor 重做 initial sync，而是按 §12.3 等待 / backfill——先以 `account/describe` 或 `snapshot/head` 取当前 frontier，再从该 frontier 起点用现有 cursor backfill 补齐缺口。
- `temporarily_unavailable`：可重试瞬态；按 `retry_after_ms` / `Retry-After` 退避后用同一 cursor 重试。

`timeline.limited=true` 时，服务端 MUST 二选一返回 `state_at_window_start`（projection-only seal 状态）或标记 `timeline.preview_only=true`；详见 §5.2。

## 4. Realm Buckets

## 5. 当前结果与历史展示上下文

### 5.1 服务器当前结果

`current` 只按 [current results](./current-results.md) 的 selector/revision 安装。
旧 `state` / `state_after` 容器已移除；客户端不对 timeline 应用 reducer 来计算当前状态。
当前治理、ordinary Event 的固定因果 winner、删除、已登记的领域 Bottom 和可见性均由自己的 Station 裁决。
历史展示上下文不能覆盖当前结果；当前结果也不改写历史消息的端到端认证或密文。

### 5.2 State At Window Start (limited timeline 边界状态)

**协议正确性层面**，Arkret 的普通 Event 携带 `prev_refs` Event 因果边、不可变授权引用和签名 `auth_context.authority_refs`；安全命令使用 `seal_basis`，Signal 使用自己的 `seal_ref`。各分支分别固定授权求值坐标，reducer / projection 在 gap 期间不会把当前展示状态冒充历史授权或收敛证据。这部分不依赖额外 gap-boundary 信息。

**渲染正确性层面**，当 `timeline.limited=true` 且 window 内可能包含 actor profile 更新、Realm / Strand / Space 元数据变更、或 E2EE epoch rotation 时，客户端若用当前普通数据投影和当前 confirmed MLS state 渲染 window 起点事件，会显示错误的 display name / Realm/Strand/Space display metadata / 加密 epoch。为此，服务端 MUST 在响应该 Realm timeline 时二选一：

**(a) 返回 `state_at_window_start`** (推荐路径，projection-only)：

```json
{
  "timeline": {
    "events": [],
    "limited": true,
    "prev_cursor": "ak:cursor:..."
  },
  "state_at_window_start": {
    "actor_profiles": [{"actor_id": {"kind": "account", "account_id": {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}}, "display_name": "...", "avatar_blob_ref": "..."}],
    "realm_metadata": {"title": "...", "summary": "...", "join_rule": "...", "collaboration_role": "direct_conversation"},
    "e2ee_epoch": {"epoch": 17, "key_ref": "ak:mls:..."}
  }
}
```

- 该字段是 **派生 projection-only 字段**，不参与 state hash / frontier 计算，不进入因果图。
- 字段范围仅限三类 context：`actor_profiles`（window 内出现的 actor）、`realm_metadata`（Realm-level Lattice cell value at window start）、`e2ee_epoch`（window 起点的 MLS epoch hint）。
- 三个字段都必须出现；`actor_profiles` 为 closed entry array，每行必须携完整 `actor_id: ActorId`，其余只允许 `display_name` / `avatar_blob_ref`；按 RFC 8785 JCS(actor_id) 的无符号 UTF-8 字节升序排列，同一 ActorId 不得重复（即使 display 字段不同）。它不是以 principal DID 为 key 的 map；同一 principal 在两个 Station 上的 account 必须保留各自 ActorId 和显示投影，客户端不得合并。`realm_metadata` 只允许 `title` / `summary` / `join_rule` / `collaboration_role`。`collaboration_role` 仅在服务端已验证注册 profile 与 Realm genesis discriminator 后输出，v1 唯一值为 `direct_conversation`；客户端不得从 title、category、tag 或成员数重建该字段。`e2ee_epoch` 必须为 `null` 或 `{epoch: non-negative integer, key_ref: non-empty string}`。各层对象均为 closed DTO，未知字段必须按 `schema_violation` 拒绝。
- 客户端 SHOULD 在渲染 window 内事件时优先用 `state_at_window_start` 而非"当前查询 basis"。
- 服务端按事件的已签授权上下文与因果闭包重放历史投影；HLC 只用于查找候选，不选择 Cell 值。
- **窗口起点（normative）**：`state_at_window_start` 使用窗口首事件逐字携带的 `auth_context.authority_refs` 与完整 `prev_refs` 因果闭包，并按该上下文适用的已验证关闭集合重算。缺任一必要依赖时使用下述回退路径，不能另选“最近”Seal。该值只是渲染投影，不授予当前操作权限。

**(b) 标记 `preview_only=true`** (回退路径)：

```json
{
  "timeline": {
    "events": [],
    "limited": true,
    "preview_only": true,
    "prev_cursor": "ak:cursor:..."
  }
}
```

- 客户端 MUST NOT 在 backfill 完成（即缺口被 `prev_cursor` 拉取并应用）前把该 timeline 渲染为已验证的完整 UI。
- 客户端可以渲染为占位、loading 状态或带 "loading history..." 标签的预览，但不得让用户感知为"完整 timeline"。

> Rationale: Matrix `/sync` limited timeline 同时返回 state delta；Arkret 的 per-event auth state 已覆盖协议层正确性，但渲染层（display name / Realm or Strand avatar / epoch boundary）仍可能错位。`state_at_window_start` 给服务端实现一条轻量恢复路径，`preview_only` 给无法计算历史 seal 的实现一条安全回退。

## 6. Event Ordering

Client Sync 的事件顺序是展示顺序和增量恢复顺序，不是授权真相本身。授权真相仍由 event hash、`prev_refs`、`refs[role=authorized_by]`、realm version 和 reducer 决定。

服务器返回 `timeline.events` 时 MUST 满足：

1. 同一响应内的事件按 deterministic timeline projection order 排列。
2. 若事件 B 通过 `prev_refs`、`refs[role="after"]`、`causal_refs` 或 payload 物化的 reply/reference edge（如 `replies_to`）直接依赖事件 A，且 A 在同一响应窗口中可见，则 A MUST 出现在 B 之前。
3. 若内容依赖因过滤、权限、分页或缺失不在窗口内，原始可见 refs 保留；客户端只按实际展示、附件或 MLS 密码学需要读取已知 exact refs。不能为了验证治理而补齐所有 prev_refs、authorized_by grants 或 Seal 历史；服务器负责当前/历史接纳和权限判断。不可见引用不得伪造占位；有限窗口按 limited/preview_only 或明确错误处理。
4. 服务器 MUST NOT 使用本地数据库自增 ID、接收顺序或 Station sync surface 到达顺序作为跨实现排序依据。

Canonical default timeline projection order（不输入 canonical state、授权判断或 winner 选择；请求未显式声明并协商其它 profile 排序时，服务器 MUST 使用本顺序）：

该排序的 canonical 定义、`causal_depth` 边集、HLC 缺省值与 provisional 重排规则的单一真相源是 [`encoding.md` §7.3](../conformance/encoding.md)；本节只说明同步投影如何消费该顺序。

```text
causal_depth ASC,
hlc ASC,
actor_id ASC,
actor_seq ASC,
event_id ASC
```

各键的精确定义与缺边时行为均以 `encoding.md` §7.3 为准；Station 同步面不得在本节另行扩展 `causal_depth` 边集或定义本地 tie-break。
- `event_id` 是最终 tie-breaker。

对于当前协议状态，客户端 MUST 安装自己的 Station 返回的 typed current result；不得重跑 CBS/Lattice 或取 timeline 中最后出现的同 kind Event。

## 7. Large Account and Large Realm Sync

数据量巨大时，Client Sync MUST 支持分层同步，而不是一次性拉取全部事件。

推荐策略：

- initial account sync baseline 只返回 Realm 摘要、必要 `required_state` 和有限 timeline。
- 活跃 Realm 优先，低优先级 Realm 只返回 unread / mention / summary。
- 使用 §2.3 有界详情兴趣拉取当前视图需要的 timeline ranges。
- 使用 `timeline.limited=true` 标记缺口，并通过 backfill / pagination 拉取。
- 使用 lazy loading members，避免同步全量成员状态。
- 使用服务器有界 current-result baseline 恢复当前态，独立验证型 snapshot 留给 peer/auditor。
- Blob、附件、缩略图、全文索引和历史密文按需拉取。
- 客户端本地维护原始内容缓存、版本化 current-result 存储及展示缓存，不维护客户端治理 reduced-state cache。

服务器 MAY 对响应进行分片：

```json
{
  "cursor": "ak:cursor:<opaque-valid-stream-cursor>",
  "partial": true,
  "priority": "active_view",
  "realms": {}
}
```

客户端 MUST treat `cursor` as the only resume token. 如果某个 Realm 的 timeline 返回 `limited=true`，客户端不得把当前窗口视为完整历史。

## 8. Lazy Loading Members

当 `lazy_load_members=true`，服务器只交付当前窗口所需完整 ActorId 的当前成员结果和 roster，覆盖范围由 current baseline.coverage.members 明确列出。客户端遇到未知成员时扩大所需窗口或查询已有服务器当前接口，不扫描成员历史求有效状态。include_redundant_members=false 允许省略未变化增量，不改变基线完整性规则。

### 8.1 Member Roster, Identity Projection, and Handle Claims

membership 当前值由自己的 Station 按 accepted 状态裁决，客户端安装 current member cell 与 server-trusted roster；不下载 proof refs 或重放 Seal。ActorId 始终包含完整 AccountId/Station，不能按 principal 合并不同账户。

`member_roster.entries[]` 是同一当前视图的轻量已裁决成员/identity 引用与 handle-claim 集。它不参与 state hash/frontier，也不要求逐事件治理验证。旧 hint 优先级和“本地验证历史覆盖 roster”的规则已删除。客户端可用于成员展示及幂等 reconciliation 调度，但实际 KeyPackage/MLS/发送操作仍执行自己的 Station 当前 gate 与真实 E2E 校验。

- limited=true 或缺字段不能从缺席推断 leave/ban、删除叶或清除发送暂停；完整 roster 也不能代替实际 winning Commit。
- entries、current member result 与同版本基线矛盾时是同步协议冲突；拒绝并重新查询 Station，不任意选一份。
- 服务端逐页检查当前权限；不把尚未 accepted、已 leave/ban 或不同 incarnation 的成员标成 join。成员 all 分页不能阻塞首屏和无关操作。
- 展示名字不等于 handle 授权。现有 identity/handle carrier 保留，Station 负责 effective set 与当前可见性；客户端保留内容/E2E 使用所需真实认证，而非借 handle/identity 引用重建治理历史。

成员展示信息由两类 source 合成：

- `ak.member.identity.update`：Realm-scoped display/subject projection。它表达 `actor_id -> subject_actor_id` 披露、display name、avatar 等 UI profile 信息；它不是 handle lifecycle 的权威源。
- `ak.schema.handle_claim.v1`：handle 授权事实。handle 的分配、重分配、撤销和过期由 Station / Organization / Directory issuer 签发的 claim 决定，用户 profile 或 MemberIdentity event 不能单方面声明 handle。

`ak.member.identity.update` 不是 `ak.profile.update` 的字段级 delta；它是 append-only 的 **segment replacement event**：新事件通过 `payload.replaces[]` 明确声明自己替代哪些旧身份事件。旧事件仍然保留在历史中，只是不再进入当前 display projection。管理员后期修改或新增用户 handle 时，不需要也不得伪造用户的 `ak.member.identity.update`；服务端和客户端通过刷新当前 handle-claim set 更新显示。

```json
{
  "member_roster": {
    "entries": [
      {
      "actor_id": {
        "kind": "account",
        "account_id": {
          "principal_id": "ak:did_core:key:z6MkRealmPairwise...",
          "station_id": "ak:did_core:webvh:z6MkStation..."
        }
      },
      "membership": "join",
      "subject_account_id": {
        "principal_id": "ak:did_core:webvh:zQmPr8...",
        "station_id": "ak:did_core:webvh:z6MkStation..."
      },
      "identity_event_ids": [
        "ak:event:AQwfxZZieb7Udz28u8Z_wXvR3hFpZzHl4sWKOICaiKC6"
      ],
      "member_display_state_digest": "sha256:...",
      "handle_claim_digests": [
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ],
      "handle_claims": [
        {
          "schema": "ak.schema.handle_claim.v1",
          "claim": {
            "schema": "ak.schema.handle_claim_core.v1",
            "handle": "alice:acme.example",
            "handle_aliases": [],
            "subject_account_id": {
              "principal_id": "ak:did_core:webvh:zQmPr8...",
              "station_id": "ak:did_core:webvh:z6MkStation..."
            },
            "issuer_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
            "claim": { "kind": "handle_binding" },
            "visibility": "public",
            "audience": null,
            "issued_at": "2026-05-27T00:00:00.000Z",
            "expires_at": "2026-06-27T00:00:00.000Z",
            "source_refs": [],
            "proofs": ["issuer_attestation proof", "holder_acceptance proof"]
          },
          "status": "verified",
          "as_of": "2026-05-27T00:01:00.000Z",
          "verifier_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
          "verified_at": "2026-05-27T00:01:00.000Z",
          "revocation": null,
          "fresh_until": "2026-05-27T00:06:00.000Z",
          "status_proof": "status_attestation proof"
        }
      ]
      }
    ],
    "limited": false
  }
}
```

`member_roster.entries[]` entry 字段规范：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `actor_id` | `ActorId` | MUST | 等于当前 effective `ak.member.state` cell subject / `payload.member_id`，按完整 Actor（包括 AccountId 的 principal 与 Station 分量）比较，不能降格为裸 DID。高隐私 Realm 中 principal 分量 MAY 使用 Realm-scoped pairwise DID；作为**长期 membership key** 的 pairwise DID MUST 由 `did:webvh` 派生（可持久解析 / 轮换 / 撤销）或在部署 `method_policy` 中显式豁免，MUST NOT 使用被标为 `ephemeral_only` 的 `did:key`（见 [`sovereign-deployment.md` §3.1](./sovereign-deployment.md)）。真实 principal 的披露由当前 effective `ak.member.identity.update` events 决定。 |
| `membership` | enum | MUST | 当前 effective membership，取 `join` / `knock`。leave / ban 不进入 roster；Invite 不产生 roster entry。 |
| `subject_account_id` | `AccountId` | MAY | 该 member 的完整 durable 账号标识，principal 与 Station 两个分量都在。它不是 Realm `actor_id`：高隐私 Realm 中 `actor_id` 的 principal 分量可能是 Realm-scoped pairwise DID，而本字段始终是 handle claim 所绑定的 exact AccountId。当当前响应已按 Realm disclosure policy 向调用方披露该 member 的 subject 时返回；subject 仅在 encrypted MemberIdentity 中披露时 MUST 省略本字段。本字段就是 [`identity/identity-handles.md` §3.2](../identity/identity-handles.md) 要求的 `ActorId -> AccountId` 显示投影在 roster 上的承载，比较 MUST 逐字比较两个分量，MUST NOT 降格为 principal core。返回 `identity_events`、`handle_claim_digests`、`handle_claims` 或 `handle_claims_limited` 时该字段 MUST 存在。 |
| `identity_event_ids` | event id array | MAY | 当前 effective `ak.member.identity.update` event ids。客户端 MAY 按这些 id backfill 原始事件；服务端 MAY 把这些原始 Event envelope 内联到 `identity_events[]` ；不得恢复 `state.events`。 |
| `member_display_state_digest` | hash | MAY | `sha256` over RFC 8785 JCS canonical JSON：`{realm_id, actor_id, effective_events:[{event_id, segment, payload_digest}], handle_claims:[{claim_digest,status,revocation_digest,fresh_until}]}`，其中 `effective_events` 按 `(segment,event_id)` 排序，`handle_claims` 按 `(claim_digest)` 排序。用于 roster display cache 失效和重复响应去重；不同于本地从 `ak.member.identity.update.payload.identity_payload` 推导的 carrier digest。 |
| `identity_events` | Event array | MAY | 可选内联的原始 `ak.member.identity.update` Event envelope。服务端不得把它改写成查询时合成 payload。该字段可能明文或可解密地披露同一 member 的 `MemberIdentity.subject_actor_id`，因此 `subject_account_id` 未披露时 MUST 省略。 |
| `handle_claim_digests` | hash array | MAY | 当前对调用方可见且可用于该 Realm context 的 effective handle claims 的 canonical digest 集合。每个 digest 按 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) 的 `claim_digest(c)` 定义计算。该字段是跨上下文稳定标识，MUST NOT 在 `subject_account_id` 未披露时返回。 |
| `handle_claims` | handle claim array | MAY | 可选内联的完整 `ak.schema.handle_claim.v1` status views。它们是当前 handle 授权 evidence，不是 roster 自己生成的 display 字段。该字段 MUST NOT 在 `subject_account_id` 未披露时返回；若返回，每个 `claim.claim.subject_account_id` MUST 逐字等于同一 entry 的 `subject_account_id`（两个分量都相等）。服务端 MAY 因隐私、体积或 freshness 省略；客户端需要补拉时直接用本字段的 exact AccountId 调用 `ak.find.directory.read.list_handles_for_subject.v1`。 |
| `handle_claims_limited` | boolean | MAY | `true` 表示 `handle_claims[]` 被截断或仅含 digest hints；客户端 MUST NOT 把缺失 claim 解释为该 subject 没有 handle。该字段只在 `subject_account_id` 已披露且 handle claim set 对调用方可见时返回。 |

`handle_claim_digests[]` 是跨上下文稳定的 claim identifier；完整 `handle_claims[]` 又直接携带 `claim.subject_account_id`，`identity_events[]` 也可能披露 `MemberIdentity.subject_actor_id`。因此，当 `subject_account_id` 因 Realm disclosure policy 未披露时，服务端 MUST 同时省略 `identity_events`、`handle_claim_digests`、`handle_claims` 和 `handle_claims_limited`，不得把 digest hint 或原始 identity event 当作隐私安全的替代披露；这四项对 `subject_account_id` 的依赖同时由 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json) `#/$defs/member_roster_entry` 的 `dependentRequired` 机械保证。返回完整 `handle_claims[]` 时，服务端 MUST 确保每个 `claim.claim.subject_account_id` 逐字等于同一 roster entry 的 `subject_account_id`；只有 principal 分量相等的 claim MUST 被丢弃或导致该 roster entry 失败 closed，这与 [`discovery/discovery-directory.md`](../discovery/discovery-directory.md) 对 `ak.find.directory.read.list_handles_for_subject.v1` 的「不得把同 principal 的另一 Station 账号合并」是同一条规则。

本字段与 MemberIdentity 的 `subject_actor_id` 承担不同角色，不是同一次改名留下的两个形态：MemberIdentity 披露的是完整 `ActorId`（`account` 或 `service` 分支）的 durable subject；roster 的 `subject_account_id` 承担的是 subject 披露开关与 handle claim evidence 的锚点，而 `ak.schema.handle_claim_core.v1` 只绑定 `AccountId`，因此 `service` 分支的 subject 既不产生本字段也不产生 `handle_claims[]`。roster subject 披露与否只由 Realm disclosure policy 决定；一旦披露即为完整账号，规范不提供"只披露 principal 分量"的中间档——`handle_claims[]` 内的 `claim.subject_account_id` 本身就携带 `station_id`，任何只省略 roster 字段的做法都不能减少已披露信息。

`member_display_state_digest` 覆盖 effective identity event references 与当前可见 HandleClaim status view 的 `status` / `fresh_until`，以及从其 `claim` 按 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) 重算的 `claim_digest` 和从其 `revocation` 重算的 `revocation_digest`（`revocation=null` 时为 `null`）；这两个 digest 只是摘要输入的派生值，status view wire 本身不携带它们。只重打包等价 proof 不改变它；重新签发 freshness、状态迁移或撤销都会改变它，使 roster display cache 不能越过 signed `fresh_until` 继续复用。`binding_state` 不是该摘要的独立投影，也不得从本地数据库行补造。

`ak.member.identity.update` payload 形态：

```json
{
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "member_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:key:z6MkRealmPairwise...",
      "station_id": "ak:did_core:webvh:z6MkStation..."
    }
  },
  "segment": "member_identity",
  "replaces": [
    {
      "event_id": "ak:event:AbAwFrBpyl1m3hDxTuNCwawM5w8GGXya0t7ZG85Tl57t",
      "payload_digest": "sha256:..."
    }
  ],
  "identity_payload": {
    "encrypted_payload": {
      "version": "1.0",
      "content_type": "application/vnd.arkret.member-identity+json",
      "encryption_context": {
        "epoch": 12,
        "group_state_ref": "ak:event:Af-qizSfVETcKiliXG093VVneO4nQF194ZXGkMWJijix"
      },
      "ciphertext": "base64url"
    }
  },
  "expected_state_digest": "sha256:..."
}
```

当前 effective 身份事件集合的计算规则：

- 候选集是同一 `(realm_id, member_id, segment)` 下 accepted 的 `ak.member.identity.update` events。
- `payload.replaces[].payload_digest` 是被替代事件完整 `payload.identity_payload` carrier wrapper（`{member_identity: ...}` 或 `{encrypted_payload: ...}`）的 RFC 8785 JCS canonical JSON bytes 的 `sha256` digest。
- 若 accepted event `B` 的 `replaces[]` 引用 accepted event `A`，且 `payload_digest` 等于 `A.payload.identity_payload` 的 digest，则 `A` 在当前 projection 中被 `B` 替代。
- `replaces[]` 引用未知 event、其它 `(realm_id, member_id, segment)` 的 event，或 digest 不匹配时，该 replacement edge 无效（reason `member_identity_replacement_digest_mismatch`）；实现 MUST NOT 因此把被引用 event 从 effective set 移除。
- 当前 effective set 是候选集中未被有效 replacement edge 指向的事件集合。成员身份查询 / roster hint SHOULD 只返回这个 effective set；历史 backfill / audit 查询 MAY 返回已被替代的旧事件。
- effective set MAY 因并发写入或 replacement 冲突包含多个未被替代的事件。查询层 MUST 原样暴露该多值状态，MUST NOT 按本地排序、到达顺序或 last-writer-wins 规则静默收敛为单一 MemberIdentity。需要单一 MemberIdentity 的显示路径（例如 mention renderer）MUST 按 [`identity/identity-handles.md` §3.8.2](../identity/identity-handles.md) 处理：不唯一即 Realm-scoped projection 路径失败，进入 live / as-of resolve 或 fallback。
- 当前事件 `payload.identity_payload` carrier wrapper 的 digest 由消费者从本体本地推导，只用于 payload cache / replacement edge 校验，不在 wire 上重复。
- `expected_state_digest` 是可选 optimistic concurrency guard。若存在，它 MUST 等于 writer 观察到的同一 `(realm_id, member_id, segment)` 当前 effective set digest：`sha256` over RFC 8785 JCS canonical JSON `{realm_id, member_id, segment, effective_events:[{event_id, segment, payload_digest}]}`，其中 `effective_events` 按 `(segment,event_id)` 排序。不匹配时服务端 / reducer MUST 以 `member_identity_state_mismatch` reject 或 quarantine，不得把该事件作为有效 replacement 应用。它不同于本地 carrier digest，也不同于 roster 的 `member_display_state_digest`。

MemberIdentity 明文对象形态（`identity_payload.member_identity`，或 `encrypted_payload.ciphertext` 解密结果）：

```json
{
  "schema": "ak.schema.member_identity.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:key:z6MkRealmPairwise...",
      "station_id": "ak:did_core:webvh:z6MkStation..."
    }
  },
  "subject_actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:zQmPr8...",
      "station_id": "ak:did_core:webvh:z6MkStation..."
    }
  },
  "display_profile": {
    "display_name": "Alice Zhang",
    "avatar_blob_ref": "ak:blob:sha256:..."
  },
  "asserted_at": "2026-05-27T00:00:00Z",
  "expires_at": "2026-06-27T00:00:00Z",
  "proof": {
    "verification_method": "did:webvh:zQmPr8...#key-1",
    "payload_digest": "sha256:...",
    "signature": "base64url...",
    "signature_algorithm": "Ed25519"
  }
}
```

MemberIdentity replacement 规则：

- v1 core 只定义 `segment="member_identity"`，因此每次替代旧身份事件时，新事件的 `identity_payload` MUST 携带完整 MemberIdentity。用户只修改 display name 时，客户端也必须读取本地当前 effective MemberIdentity，应用本地修改后重新封装完整对象；不得只发送 `{display_name: ...}`。
- 更窄且互不重叠的 segment（例如 `display_profile` / `subject_disclosure`）需要后续 schema / profile revision 扩展 `segment` 枚举或定义新的 payload schema；v1 receiver MUST reject unknown segment values，reason 为 `member_identity_unknown_segment`。扩展后的每个 segment 内仍然是完整替换：如果一个新事件替代某个旧 segment event，它必须包含该 segment 的所有数据，即使本次只改变其中一个字段。
- v1 MemberIdentity payload MUST NOT carry `primary_handle`、`handles[]` 或其它 handle 字符串字段。handle 是 issuer claim lifecycle 的输出，不是用户 profile / identity event 的输入；客户端需要展示 `@alice:acme.example` 时，MUST 从当前可见 `ak.schema.handle_claim.v1` set 运行 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) primary handle selection。
- canonical handle string 仍为 `alice:acme.example`；`@alice:acme.example` 的 `@` 是 mention/UI sigil，不属于 handle。`alice@acme.example` 只可作为输入别名，normalize 后不得进入签名 transcript、claim、cache key 或 MemberIdentity。
- MemberIdentity 只负责 Realm-scoped display projection：`subject_actor_id` 披露、display name、avatar 和其它未来 display-profile segment。`subject_actor_id` 是完整 `ActorId`，account 分支保留 Station 分量；mention / reply / quote 等 actor 引用字段 MUST 使用 [`identity/identity-handles.md` §3.8](../identity/identity-handles.md) 定义的权威 subject 引用字段而不是 handle 字符串；handle claim 只影响显示和可读寻址，不影响 grant subject、actor attribution、membership key、delivery 决策或 audit attribution。
- handle、display name 和 avatar 只用于 UI / mention / member picker，不得用于 grant subject、actor 归因、membership key、delivery 决策或 audit attribution。
- `ak.profile.update` 继续表示 principal-scoped actor profile 的字段级 delta；`ak.profile.realm_override` 继续表示 Realm-scoped profile override。二者 MAY 作为客户端构造 MemberIdentity display fields 的输入；handle fields MUST 来自当前 effective handle claims。
- `identity_payload.encrypted_payload` MUST 复用 [`encrypted-envelope.schema.json`](../../artifacts/schemas/encrypted-envelope.schema.json)。明文 MemberIdentity 是 `ciphertext` 解密结果；`content_type` SHOULD 使用 `application/vnd.arkret.member-identity+json`。
- 加密 MemberIdentity MUST 由成员设备或被 Realm policy 授权的身份 issuer 设备生成。Sync / Principal / Federation Service MUST 存储和返回原始 encrypted payload 或其事件引用，不得因客户端查询而重加密、重封包或推进 MLS sender generation。
- 客户端解密时按 `group_id`、`epoch` 和 `key_ref.group_state_ref` 查找本地 MLS group state；缺少 epoch 时按 §15 标记 `decryption_pending` 并补拉 `ak.mls.*` state / Welcome / winning Commit / 授权 history key material。
- 客户端 MUST 验证 MemberIdentity 的 `realm_id`、`actor_id`、`subject_actor_id`、`proof.payload_digest`、签名链和 Realm disclosure policy；`proof.payload_digest` MUST 等于移除顶层 `proof` 字段后的 MemberIdentity 对象的 RFC 8785 JCS canonical JSON bytes 的 `sha256` digest，签名也 MUST 覆盖同一 canonical bytes。任一失败（reason `member_identity_proof_invalid`）时不得把该 event 提升为 verified display identity。

Handle claim 获取与刷新规则：

- 注册、邀请链接、管理员预分配、管理员后期修改、重签和撤销 handle 都落到 issuer / Auth Server / 部署本地 `ak.schema.handle_claim.v1` lifecycle。Arkret v1 core 不定义用户如何申请、管理员如何收到通知、谁有权审批、审批状态如何流转或客户端如何在 bootstrap 中领取自己的 claim。
- 客户端不得通过 `ak.profile.update`、`ak.profile.realm_override` 或 `ak.member.identity.update` 自行设置 handle。无论 claim 来自 Auth Server bootstrap、issuer 本地 API、设备迁移恢复、Directory resolve 还是 roster 内联，客户端只有在 schema、issuer trust、proof、audience、expiry 和 revocation 状态验证通过后，才能把它作为 handle 授权事实。
- 需要渲染 Realm member 当前 handle 时，客户端使用 roster entry 内联的 `handle_claims[]` / `handle_claim_digests[]`，或用同一 entry 的 `subject_account_id` 调用 `ak.find.directory.read.list_handles_for_subject.v1`。roster 未披露 `subject_account_id`（或 MemberIdentity 的 `subject_actor_id` 落在 `service` 分支）时，没有可用于该 subject 的 handle claim 查询输入，客户端 MUST 等待 subject disclosure 或使用已内联 evidence，MUST NOT 用 Realm `actor_id`、pairwise principal 或任何单分量拼装查询参数。已知 handle 字符串、需要解析到账号或投递绑定时，继续使用 `ak.find.directory.read.resolve_handle.v1`。
- roster / member picker / mention autocomplete 的当前 handle projection MUST 由当前可见 handle-claim set + Realm policy 运行 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) 得出。`ak.member.identity.update` 事件的 churn 不应成为 handle 更新传播的必要条件。
- 若 `member_display_state_digest` 因 handle-claim set 变化而改变，服务端 SHOULD 在下一次 `/_arkret/self/account/subscribe` delta 中发送新的 roster entry 或使客户端相关 cache 失效；无法内联完整 claims 时，MUST 至少让 `handle_claim_digests` 或 digest 缺失状态发生可观察变化。

`lazy_load_members=true` 时，服务端 MAY 截断 `member_roster.entries[]` 为 timeline 涉及的 actor + `summary.heroes` 子集，但此时 MUST 设置 `member_roster.limited=true`，并 SHOULD 提供 `member_roster.next_cursor` 或等价分页提示。客户端看到 `member_roster.limited=true` MUST NOT 把 `member_roster.entries[]` 当作完整成员列表。`member_roster.entries[]` 的去重键是 `actor_id`；同一 `actor_id` 出现多次时客户端 MUST 保留首条并忽略后续。

`summary` 中的 `heroes` 与本节 `member_roster.entries[]` 互补：`heroes` 是当成员数超过显示阈值时挑选的少量代表性 DID，`member_roster.entries[]` 是当前响应内可投影的 roster 条目集合；完整性由 `member_roster.limited` / pagination 明确表达。

## 9. Account Data and Private State

`account_data` 是 principal 或 device 私有状态，不进入 Realm canonical state。标准类型：

标准 Account Data key/pattern 的机器索引是 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)。当前标准集包括：

- `ak.tags.realm.<realm_id>`
- `ak.push_rules`
- `ak.dnd_schedule`
- `ak.collections.stickers`
- `ak.client.ui_state`
- `ak.account.blocklist`
- `ak.contacts.actor.<principal_key>`
- `ak.contacts.realm.<realm_id>`
- `ak.presence.visibility`
- `ak.presence.preference`
- `ak.read_receipt.preferences`
- `ak.account.holder_quarantine`
- `ak.account.invite_delivery`

Account data MUST 按 principal/device 授权隔离。联邦节点不得向其他 principal 泄露 account data。

存储模型、value 加密与跨设备并发写入契约的单一真源是 [`../models/account-data.md`](../models/account-data.md)：每个 key 是 server-versioned compare-and-set whole-value register，写入携带 `expected_revision`，领域 merge 规则在客户端明文上执行。

`ak.account.invite_delivery` 与 `ak.account.holder_quarantine` 是 registry 声明的 `station_cas` plaintext cell。它们的权威 revision/value 同时由 account-data list/get 诊断面与本 sync frame 顶层 `account_data.station_cas` 投影：initial sync 分段 baseline 必须最终覆盖当前 registry 中所有 holder-readable Station-CAS live row；增量用 `upserts[]` / `removals[]` 表达 cursor 覆盖后的最终 revision，同 key 可合并为窗口内最后一项。baseline 分段的 `removals` 必须为空；仅在 `baseline.completed_channels` 包含 `station_cas` 时，对该快照所有已安装分段作完整集合替换，保留快照后更高 revision 的 upsert/remove。删除旧 `station_cas.complete` 字段，不得在任一分段到达时先清空 live set。它们不是 holder-authored Event，MUST NOT 出现在 `account_data.events[]`，也不得为了填充该 Event container 而合成 `ak.account_data.set`。

每个 upsert 逐字复用 `account-data-operations.schema.json#/$defs/account_data_entry`；remove 携带 `account_data_key`、`revision`、`updated_at`。客户端对每个 key 只接受更高 revision；普通增量的更低 revision MUST fail closed；同一仍有效 baseline 的较旧行只记为快照已见键并忽略其旧值，保留已安装的新 revision，不把这种正常分页重叠当作增量回滚；同 revision 的不同 value / tombstone MUST 视为同步冲突并触发 resync。服务端 MUST 把 accepted Station-CAS 写入、该 key 的投影位置推进与可重放变更记录放在同一事务；cursor 必须覆盖该位置。变更记录保留期 MUST 不短于 cursor TTL 与 `account_data_tombstone_retention_ms` 的较大者；无法填满 `after` 到当前 frontier 的区间时必须返回 `dropped` / `resync_required`，不得静默跳过。`to_device` 中的 `ak.account_data.update` 仅是低延迟唤醒/加速器，不是第三个真相源，也不能代替上述 baseline 与增量。

本段的 baseline 完整性、缺席不等于删除、revision 单调性、同 key 窗口合并、两类真相源不得互相合成，以及填不满区间必须 `dropped` / `resync_required` 这几条，由 `ak.vector.sync.station_cas_account_data.v1` 固化（[`../conformance/conformance-vectors.md` §5.12](../conformance/conformance-vectors.md)）。

## 10. To-Device Delivery

`to_device.messages` MUST 只包含当前 session credential 对应 device 的消息。

### 10.0 主接收路径与补拉路径 (normative)

`/_arkret/self/account/subscribe` 与 `GET /_arkret/self/device_messages` 暴露的是同一个 per-device to-device 队列的两种读取形态；二者不代表两套消息源，也不允许客户端把同一 kind 分流到两套互不一致的处理器。

`ak.self.account.stream.subscribe.v1` 是 full client / E2EE client 的主接收路径。客户端维护连续长轮询后，服务端 SHOULD 在 `delta.to_device.messages[]` 中返回当前设备的验证请求、SAS/QR 交换、secret sharing、device-list 相关私有消息；客户端 MUST 把这里收到的 `DeviceMessageEnvelope` 交给与 `ak.self.device_messages.read.list.v1` 相同的 to-device dispatcher，并在持久化处理完成后按 §10.1 使用 `ack_token` 显式确认。

`GET /_arkret/self/device_messages?after=<cursor>&limit=n` 是补拉 / 轮询路径，只用于下列情况：

1. `delta.to_device.limited=true` 时，用 `delta.to_device.next_cursor` 继续分页读取队列。
2. 客户端本地 dispatcher 崩溃、account subscribe 暂未建立、或前台验证小流程尚未启动完整账号同步时，用于补拉未确认消息。
一旦 full client 的 account subscribe 已经运行，客户端 SHOULD 停止为同一 `(account_id, device_id)` 维持独立的 SAS 轮询循环；继续轮询只应作为检测到 `limited`、`dropped`、本地处理失败或显式用户前台流程的短期恢复手段。无论消息来自主路径还是补拉路径，ack、去重、过期、`lost` 处理和 transaction 幂等规则完全相同。

### 10.1 显式投递确认 (normative)

To-device 队列删除由**显式 ack** 驱动，与 stream cursor 解耦；account stream 与 to-device queue 使用的 `after=` cursor 都 **MUST NOT** 触发队列删除：

1. **`ack_token` 签发**：服务端在每个携带非空 `to_device.messages` 的 `delta` frame 中 MUST 附带 `to_device.ack_token`；`GET /_arkret/self/device_messages` 的每个非空响应页同样 MUST 携带顶层 `ack_token`。`ack_token` 是 server-issued 不透明确认令牌，绑定 `(account_id, device_id, 该批次的队列高水位)`，覆盖该批次及其之前所有已投递消息。它**不是 cursor**：不使用 `ak:cursor:` wire 形态，不进入 cursor schema / TTL / purpose 体系；客户端 MUST 把它当作不透明字符串原样回传。令牌 MUST 不可伪造：不可猜测（解码后熵 ≥ 128 bit）或等价的服务端查表绑定。**wire 形态（normative）**：`ack_token` MUST 是单个 UTF-8 字符串，且 MUST NOT 超过 1024 字节；客户端按不透明字符串原样回传、不解析其内部结构，服务端 MUST 拒绝超长或非 UTF-8 的 token（`param_invalid`）。该上界保证跨实现可移植，避免无界 token。
2. **显式 ack**：客户端仅在该 `ack_token` 覆盖位置（含）之前的**所有已投递消息**都已持久化处理完成（密钥材料、verification transcript、secret 已落盘）后，MUST 调用 `ak.self.device_messages.command.ack.v1`（`POST /_arkret/self/device_messages/ack`，body `{ack_token}`）。确认是**累计且单调**的：服务端删除该令牌覆盖位置（含）之前的全部已投递消息；ack 一个早于当前确认位置的令牌是合法 no-op，返回 `{pruned_count: 0}` 且 MUST NOT 回退确认位置。并行 dispatcher MUST 维护"最高已连续持久化队列位点"，MUST NOT ack 覆盖位置晚于任何未持久化消息的 token。该操作天然幂等，不需要 `Idempotency-Key`。
3. **ack 校验**：服务端 MUST 校验 `ack_token` 绑定与当前 authenticated `(account_id, device_id)` 匹配；unknown / 过期 / cross-binding 令牌 MUST 返回 `param_invalid`（reason `invalid_ack_token`）且 MUST NOT 删除任何排队消息。
4. **cursor 只读与 envelope 幂等**：`/_arkret/self/account/subscribe` 与 `GET /_arkret/self/device_messages` 的 `after=` 都只决定读取 / 续传位置。客户端建立新的 subscribe 连接时（无论 `after=` 位置），服务端 MUST 重新投递所有未确认、未过期的 to-device 消息，并原样保留 `DeviceMessageEnvelope.device_message_id`。客户端 MUST 在执行 handler 副作用前查询 durable closed-sender 去重记录：human device 使用 `(sender_account_id,sender_device_id,device_message_id)`，Agent 使用 `(sender_agent_id,device_message_id)`，Station service 使用 `(sender_id,device_message_id)`。同 key 且已成功持久化的消息只恢复完成位点、不得再次执行 handler，随后仍可参与累计 ack。kind-specific `transaction_id` / `request_id` 只关联验证、secret 或其它业务 transcript，不得作为通用 envelope 去重键。相同 `device_message_id` 但 envelope canonical 内容不同视为协议冲突，MUST fail closed，不得覆盖既有去重记录。
5. **过期与丢失信号**：未确认消息仍受 `DeviceMessageEnvelope.expires_at` 与 [`device-lifecycle.md` §7](../crypto-media/device-lifecycle.md) 队列 TTL 约束，过期 MUST 清除。服务端自该设备上次确认位置以来因过期或容量约束丢弃过未确认消息时，SHOULD 在下一个含 `to_device` 的响应中设置 `to_device.lost=true`；客户端收到后 SHOULD 触发密钥恢复路径（key backup / key re-request），MUST NOT 静默假设队列完整。**E2EE client profile 升级（normative）**：对声明 `ak.profile.e2ee_client.v1` 的客户端及其服务对端，由于丢弃的未确认 to-device 消息可能承载不可再生的 MLS Welcome / secret share / key material，上述两个 SHOULD 升为 **MUST**——服务端丢弃过该设备未确认消息时 **MUST** 设置 `to_device.lost=true`；客户端见到 `to_device.lost=true` 时 **MUST** 进入 key re-request / key backup 恢复路径，**MUST NOT** 静默把队列当作完整，以免 E2EE 密钥材料永久丢失而不被检出。
6. **`ack_token` 独立于 stream cursor 生命周期（normative）**：`dropped` / `resync_required` frame、`cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized` 失效、以及任何清空本地 cursor 缓存的恢复动作，均 **MUST NOT** 使既有未确认的 `ack_token` 失效。`ack_token` 绑定的是 `(account_id, device_id, to-device 队列高水位)`，与 stream cursor 的 wire 形态、TTL、purpose 和 revocation 体系完全独立（见 §10.1 第 1 条与 §12）。客户端在 cursor 失效 / dropped / resync 后重建订阅时，仍 MAY 用先前持有的有效 `ack_token` 确认已持久化处理的批次；服务端 MUST 仍按 §10.1 第 3 条校验该 token 的 `(account_id, device_id)` 绑定并执行累计删除，不得仅因 stream cursor 已被重置就把该 token 当作 unknown / cross-binding 拒绝。该口径与 §12.2.1（cursor revoke 不影响已签发 `ack_token`）一致。

> Rationale: cursor 前进表达的是「客户端收到了 frame」，安全删除需要的是「客户端已把载荷持久化」。把删除绑在 cursor 推进上（Matrix `/sync` 的隐式 ack 模型）会留下崩溃窗口：客户端收到 frame、cursor 已推进、但 MLS Welcome / secret share 尚未落盘即崩溃 → 消息被服务端删除、密钥材料永久丢失。显式 ack 把两个语义拆开后，cursor 不再是 to-device 不可逆删除的闸门；§12 的 cursor 完整性校验仍然原样保留——它防护的是伪造 / 跨绑定位点导致的静默缺口（含 `device_lists` 缺口的 E2EE 后果）、barrier 存在性预言机与 catch-up 成本放大，而非 to-device 删除。

### 10.2 队列分页

To-device 队列过长时，服务器 MAY 在 account subscribe `delta.to_device` 容器中返回 `limited=true`。当 `delta.to_device.limited=true` 时，服务端 MUST 同时返回 `delta.to_device.next_cursor`，客户端 MUST 用该 cursor 调用：

```http
GET /_arkret/self/device_messages?after=<cursor>&limit=...
```

该 endpoint 的 `after` cursor 同样 MUST 通过 §12 完整性校验后才能用作读取位置；该读取位置是只读的，MUST NOT 触发队列删除（删除只经 §10.1 显式 ack）。`after=` 表示从该队列位置之后继续读取，并与响应 `next_cursor` 配对；`from=` / `start_at=` 均不是该 operation 的合法别名。客户端 MUST NOT 把 account subscribe 顶层 `cursor` 当成 to-device 队列分页 cursor；顶层 `cursor` 只用于 account stream resume，to-device 队列分页只使用 `delta.to_device.next_cursor`。

## 11. Filters

Filter MUST 是服务端可验证 JSON，不得包含任意脚本。本面默认和硬上限见 §2.3；服务器 MAY 进一步降低部署预算，但不得使一个合法单 Event 无法取得。其它过滤面可限制：

- 最大 Realm 数
- 最大 timeline limit
- 最大 required state 数
- 最大通配符展开量
- 最大等待时间

超限返回 `rate_limited`、`payload_too_large` 或 `param_invalid`，并在 `Retry-After`、`retry_after_ms` 或 `limits` 中说明。

`filter_digest` 的 canonical 计算（normative）：

1. 将单个 percent-encoded query filter 解码并校验为 canonical JSON object；未提供 `filter` 时，normalized filter 是空对象 `{}`。
2. 省略所有未出现的 optional 字段；不得把实现默认值写入 normalized filter。
3. 对集合语义字段 `realm_ids`、`strand_ids`、`event_kinds`、`not_event_kinds`，在计算 digest 前按元素字符串 lexicographic 排序并去重；其它数组若未来由 profile 引入，profile MUST 声明 order-is-semantic 或 sorted，未声明时不得进入 cursor binding。
4. 按 RFC 8785 JCS 对 normalized filter 编码为 UTF-8 bytes，计算 `filter_digest = "sha256:" || hex(sha256(jcs_bytes))`。

`realm_list.after`、`realm_list.limit`、`replace_filter` 是分页位置或显式转换动作，不进入 detail filter_digest。列表 cursor 另绑定固定列表排序和 snapshot，不能用作 account after。

服务端签发 stream cursor、强制 `reconnect_after_ms` cooldown 或验证 cursor binding 时 MUST 使用同一 `filter_digest`；客户端若持久化 cursor，也 SHOULD 同步持久化该 digest 以便诊断 `cursor_integrity_invalid`。

### 11.1 Events 面的 query-scope digest（normative）

`ak.self.events.read.scan.v1`、`ak.self.events.stream.subscribe.v1`、`ak.peer.events.read.scan.v1` 签发的 stream cursor，其绑定中的 `filter_digest` MUST 覆盖**完整查询作用域**，不只是 `filters`：

1. normalized scope object 包含全部**非位置性**、决定结果集合或结果形状的请求参数：selector（`realms`、`actors`）、`filters` object、`order`，以及 profile 引入的等价参数。
2. 位置性参数（`before` / `after` / `limit` / cursor 本身）与认证材料 MUST NOT 进入 digest——它们随每次调用变化，不属于作用域身份。
3. 集合语义字段（`realms`、`actors`、`event_kinds`、`not_event_kinds`）在计算前按元素字符串 lexicographic 排序并去重；未提供的 optional 字段省略，不得把实现默认值写入 normalized scope。
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

`cursor`（purpose=`barrier`）由写接口在响应中返回（见 [`api-conventions.md` §8](./api-conventions.md)），用于 `X-Arkret-Wait-For` header；它和 stream cursor 共享 wire 形态 `ak:cursor:<base64url>`，由内部 `purpose` 字段区分。客户端不需要分辨，只需把"写响应里的 cursor"作为 wait-for header、把"`/_arkret/self/account/subscribe` frame 里的 cursor"作为下次 `after=` 重连参数即可。

### 12.1 Cursor Integrity (normative)

无论 stream 还是 barrier cursor，wire 形态 `ak:cursor:<base64url(canonical_json)>` 都 **MUST** 是服务端可验证的同步位置；服务端 **MUST NOT** 仅按语法 / TTL / purpose 校验就把客户端回传的 cursor 当作"可信位置"用于 `/_arkret/self/account/subscribe` `after=` resume 起点、`X-Arkret-Wait-For` barrier 解除、`dropped` / `resync_required` 恢复或其他不可逆 server-side state。v1 不存在 cursor 驱动的 to-device ack：to-device 队列删除只由 §10.1 显式 ack 驱动，cursor 的 to-device position 仅决定续传读取位置。

**v1 core 采用单一 stateful opaque handle 形态**：canonical body 为 `{v, purpose, issued_at, expires_at, h}`，其中两个 instant 均为 canonical `.sssZ` string，`h` 是 issuing service 生成的不可猜测 handle（解码后熵 ≥ 128 bit），service 内部维护 handle → `(account_id, device_id, filter_digest, purpose, positions, target?, expiry)` 映射。这里 `account_id` 是完整 exact AccountId，已经包含 Station 分量；不得再以裸 `principal_id` 或 `service_id` sidecar 补齐账号身份。Handle 查表本身就是完整性校验 —— 无需在线 transcript 校验，无需 `_mac` / `_sig`，无需 `issuer_kid` 密钥管理。这是 Matrix `next_batch` / MSC4186 `pos` 的等价形式。

服务端 SHOULD 将 handle → binding 映射持久化（或以其它方式保证其跨进程重启存活），使服务重启不会把所有未过期 cursor 同时变成未知 handle、迫使全部客户端按 §12.3 重做 initial sync。仅内存实现不违反完整性契约（未知 handle 仍按 `cursor_integrity_invalid` 失败 closed），但其重启代价随活跃客户端数线性放大；持久化实现 SHOULD 同时对未过期 handle 做超出 TTL 的及时清理（到期后清理，或仅清理可证明不再被重试/并发在途响应引用的 handle；出示更新 cursor 本身不足以证明旧 handle 可删），避免 handle 表无界增长。

对生产级部署，上述耐久性从 SHOULD 升级为 MUST：声明 `ak.profile.small_team.v1`、`ak.profile.organization.v1`、`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1`、`ak.profile.sovereign_enclave.v1` 或 `ak.profile.isolated_sovereign_network.v1` 任一 deployment profile 的服务，MUST 保证未过期 cursor handle 绑定跨进程重启可解析，且 MUST 实现 TTL GC 与被取代 handle 的前进清理；常规重启或计划内升级把全部活跃客户端打回 initial sync 视为不满足该 profile 声明。

`ak.profile.personal_node.v1`（个人/开发单机）的 personal_node cursor handle 持久化默认维持 SHOULD；**但启用 E2EE 时升级（normative）**：当该 personal_node 服务于启用 E2EE 的账号（承载 `ak.profile.e2ee_client.v1` 客户端或 `encryption_profile=mls_rfc9420` Realm）时，未过期 cursor handle 绑定的跨进程重启持久化 **MUST** 实现；若实现确实无法持久化该绑定，则每次重启后 **MUST** 对受影响客户端强制重发完整 `device_lists` baseline（等同 initial sync 的 device list 全量 baseline）。理由：重启即丢 cursor 会把 E2EE 设备信任刷新静默退化为全量重置，而 `device_lists` 缺口只能靠重做 initial sync 恢复（见 §2.2 第 1 条）；二者必择其一，不得让 E2EE 设备信任在重启后处于既不持久也不强制重建的状态。

### 12.2 校验流程 (normative)

任何 endpoint 在使用客户端回传的 cursor 推进 server-side state 之前，MUST 执行：

1. 解析 `ak:cursor:<base64url>` 并按 `cursor.schema.json` 校验语法、`purpose`、TTL（`expires_at` 未过期）。语法/参数失败映射顶层 `param_invalid`（reason `invalid_cursor`）；TTL 失败映射 `cursor_expired`。
2. **Handle 查表完整性校验**：以 `h` 查 issuing service 本地表，校验 handle 存在、未过期、未撤销，且绑定的 `(account_id, device_id, filter_digest, purpose)` 与当前 authenticated request 匹配；`account_id` 必须是认证会话派生的完整 exact AccountId，不能拆成 principal + service sidecar。任一失败 → 返回 `cursor_integrity_invalid`，**MUST NOT** 推进任何 server-side state。
3. 校验通过后才可读 handle 解析出的 positions（stream cursors）或 target（barrier cursors），并用于推进同步状态。

`cursor_integrity_invalid` 与 `cursor_expired` 语义不同：前者是 tamper / 未知 handle / cross-binding，后者是 TTL 超时。客户端对 `cursor_integrity_invalid` 的恢复路径与 `cursor_expired` 一致（重做 initial sync），但客户端 SHOULD 把它视为本端 cursor 状态被污染的信号，清理本地 cursor 缓存。

### 12.2.1 Cursor Revoke（high-assurance optional）

声明 high-assurance cursor revoke capability（ServiceDescribe `supported_features[]` 含 `ak.feature.cursor_revoke_high_assurance.v1`）的服务 MUST 支持主动撤销 cursor：

```text
POST /_arkret/self/account/cursor/revoke
```

请求体至少包含 `{cursor, reason_code, revoke_scope}`；`revoke_scope` 取值为 `this_cursor` / `same_session` / `same_device`，缺省 `revoke_scope=this_cursor`。

`revoke_scope` 范围的 normative 定义（与 [`identity/account-lifecycle.md`](../identity/account-lifecycle.md) 中的 session/device 标识对齐）：

- session 抽象为 `(account_id, device_id, issued_at, session_id)` 四元组，由签发 cursor 的服务在派发时记录在 cursor handle metadata 中。
- `this_cursor`：仅撤销当前提交的 cursor 本体（按 stateful handle 匹配）。
- `same_session`：撤销与当前 cursor 同 `(account_id, device_id, issued_at, session_id)` 的所有未过期 cursor（含同会话内派发的派生 cursor）。
- `same_device`：撤销与当前 cursor 同 `(account_id, device_id)` 的所有未过期 cursor（跨会话）。
- 当 cursor 来自浏览器或其它无稳定 `device_id` 的环境时，`same_device` MUST 在效果上退化为 `this_cursor`（服务端不得猜测设备同一性），并在响应 `revoke_scope_effective="this_cursor"` 中显式回执，以避免客户端误以为全设备已撤销。

服务端接受后 MUST 将对应 cursor 写入 cursor revocation set（按 stateful handle 匹配），保留时间不少于该服务声明的最长 cursor TTL（stream / barrier cursor 的 TTL 硬上限唯一 canonical 数值见 [`encoding.md` §8.3 规则 9](../conformance/encoding.md)，本节不重复字面数值）。撤销命中时，任何 endpoint MUST 返回 `cursor_revoked`，并且不得推进 subscription position、barrier wait 或 dropped recovery state（to-device 队列删除不经 cursor，见 §10.1；cursor revoke 不影响已签发 `ack_token` 的有效性）。

Cursor revoke 不能替代 cursor integrity：服务端仍必须先做 §12.2 完整性校验；完整性失败返回 `cursor_integrity_invalid`，不泄露该 cursor 是否曾被 revoke。

### 12.3 过期或缺口恢复流程

恢复流程按触发原因分成两类互斥分支，客户端 MUST 先按 §4 的分类判定原因再进入对应分支；两类分支对"旧 cursor 是否可继续复用"的处理**根本不同**，不得混用同一套 `after=` 取值。

> **frontier 不是 cursor（前置约定）**：frontier Event IDs 和 Seal basis 是服务器结果的语义边界，`before` / `after` 只接受注册 cursor。客户端核对响应与请求的账号、Realm、filter 和 basis 绑定，使用标准响应的 `prev_cursor` / `next_cursor` 恢复；不以遍历所有 heads/prev_refs 或证明 event_set_commitment 完整性作为采用自己 Station 结果的条件。

按需内容恢复仍可返回完整 Event、RedactedEventView 或 ReferenceLockedEventStub；客户端遵守访问裁剪、消息身份和端到端认证，但不为验证自己 Station 的裁剪声明而拉取隐藏 Event 或治理证明。具体内容依赖未到达时保留该内容 pending，不把它升级为账号级历史重放门禁。

#### 12.3.1 `cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized`（旧 cursor MUST 废弃）

cursor 本端状态失效（TTL 超时，或 tamper / 未知 handle / cross-binding，或 cursor 由另一服务签发即 `cursor_unrecognized`）。旧 cursor 不再是可信同步位置：

1. 客户端 MUST 清空本地 cursor 缓存（含该流的 `after=` 高水位）；**MUST NOT** 把已失效的旧 cursor 复用为任何 `after=` / `before=` 起点或 backfill 续传位置。`filter_digest`、未确认写入和最后由自己 Station 确认的 frontier 可保留用于 backfill 停止判定，但 frontier 不得当作 cursor 使用。
2. 客户端从下列两条合法新起点二选一，二者都不复用旧 cursor：
   - **(A) 重做 initial sync**：无 `after` 重新建立 `ak.self.account.stream.subscribe.v1?catchup=true`（`after=` 缺省 + `catchup=true`），由服务端发 baseline `delta` 重新签发新 cursor。
   - **(B) snapshot 加速目标 bootstrap**：调用标准 snapshot manifest/head；客户端核对自己 Station 来源、exact Realm/basis、格式、所取 chunk hash 与适用端到端认证，按目标范围安装当前视图。账号聚合面仍按 (A) 取得新 cursor。新窗口使用标准响应的历史 cursor；未取旧页保持 limited，不把 frontier 当 cursor，也不遍历 heads/prev_refs/event_set_commitment 来证明服务器治理结果。
3. snapshot 不可用或所需 chunk 认证失败时，只为该 Realm 请求自己 Station 的当前基线或保持 pending；不得回退客户端治理历史重放。独立审计/备份工具的完整性证明不属于普通新设备登录路径。

#### 12.3.2 `frontier_stale`（旧 cursor 仍有效，可继续 backfill）

cursor 本身仍有效，只是服务 frontier 落后于请求所需 causal frontier。此分支 **MUST NOT** 清 cursor 重做 initial sync：

1. 客户端保留本地 `cursor`、`filter_digest`、未确认写入和最后由自己 Station 确认的 frontier。
2. 按 `retry_after_ms` / `Retry-After` 退避后，用**现有 cursor** 重试 / 等待 frontier 推进；需要补洞时，可先调用 `account/describe` 或 `snapshot/head` 读当前 frontier 作为停止判据，再用**现有 cursor** 的 `prev_cursor` / `next_cursor` 续传 `ak.self.events.read.scan.v1` 补齐缺口。snapshot 采用前核对自己 Station 来源、请求绑定、格式和内容认证，不验证治理历史。

#### 12.3.3 历史完整性边界（两分支共用）

同步完成表示自己 Station 已确认的请求范围和同步位置已处理，不证明所有潜在来源都从未隐瞒数据。客户端不得宣称独立检测自己 Station 的恶意历史省略；正常可用性以服务器 accepted 结果、当前授权和端到端认证为依据，不能因为客户端没有独立 omission proof 而拒绝已经确认的结果。来自外部服务的接受依据仍由自己 Station 验证。

## 13. Initial Sync

Initial sync 的账号入口是:

```http
GET /_arkret/self/account/subscribe?catchup=true
Accept: application/x-ndjson
```

也就是不带 `after`,并显式请求 `catchup=true`。服务器 MUST 先发送至少一个有界 `delta` frame 作为账号 baseline 分段，再发送 `catchup_complete` 并结束本轮响应；未完成通道按 cursor 在后续轮继续，客户端随后使用该 cursor 发起有界长轮询。Baseline 不是完整历史记录；它只覆盖客户端首屏与账号状态恢复所需的当前视图。Baseline `delta` SHOULD：

- 返回用户当前 joined/knocked Realms 的 membership 摘要；另可从既有私有 Invite inbox / delivery CAS→private fanout 返回待处理邀请展示，但不得把它编码为 Realm membership 或 roster row。
- 对活跃 Realm 返回有限 timeline。
- 按已选目标返回足够当前 state 使该页面可渲染；不恢复未登记的 required_state 请求字段。
- 分段返回 device list baseline；仅 `baseline.completed_channels` 声明该集合完成。
- 顶层 `account_data.station_cas` 按 §2.3 分段覆盖所有 holder-readable live row；filter 不裁掉该集合，baseline removals 为空。零行也要显式完成 `station_cas` 通道；删除只在该快照终段安装后执行。

此外，同一 baseline 的全部已安装分段 MUST 最终覆盖当前 account context 下 `notifications` 通道的完整当前集合：
全部仍 open 的 `agent_runtime_approval`，以及接收者当前仍可见的全部普通 `ak:notification_projection:*` 当前行，
都作为 `action=upsert` 返回（§3.1.3）。普通行受部署保留边界与当前授权裁剪，被裁剪的行必须以显式 `remove` 退出；
即使普通通知历史受限，也不得截断仍 open 的 `agent_runtime_approval` 子集。

对本次请求包含且当前 membership 为 join 的 Realm，服务器 MUST 按 [current results §4](./current-results.md#4-精确覆盖的分段基线) 提供创建固定安全属性、当前政策结果、default Strand pointer 和所需 Strand 当前对象。history_access 只裁剪旧内容，不得裁掉当前必要结果。发送权限和 MLS authoring/accepted-artifact 继续使用逐操作服务器 gate；缺必要结果仅阻塞依赖该结果的操作，不阻塞所有 Realm、首屏、完整成员名单或旧历史。不得恢复 state.events、客户端治理证明或不存在的 Strand.is_default 镜像字段。

大型账户使用 §2.3 的有界摘要页与显式详情兴趣，避免一次性返回所有 Realm。

大型 Realm 的当前态 MAY 通过自己 Station 已验证的 Snapshot 加速。客户端核对来源、请求 Realm/basis、格式、chunk 内容 hash 和端到端认证，按需安装当前视图并使用标准 cursor 接续内容增量；MUST NOT 下载全 Realm 历史来证明 Snapshot。manifest 不可用或服务器未宣告 snapshot operation 时，请求相关 Realm 的服务器基线或保持该 Realm pending；不回退客户端治理重放。

### 13.1 渐进加载与目标就绪

首页可见、目标可读、目标可发、当前窗口完成和全部账号 baseline 完成 MUST 分别判断；本节不新增 wire ready boolean。
客户端取得首个已确认的有界摘要页/局部 baseline 后 SHOULD 展示账号导航，不等待其它 Realm 的治理验证、密钥恢复、完整名单、旧消息或附件。
窗口未包含的 Realm、member 或 state 不等于 leave、ban 或删除；只有对应 operation 声明的完整集合边界或明确删除才能驱动删除。

| 阶段 | 可展示或执行的内容 | 必需条件 |
| --- | --- | --- |
| 发现摘要 | 名称、提示与允许披露的 pending 状态 | 自己 Station 的结果或明确标注的目录提示；不取得 membership 或正文权限 |
| 加入推进 | 申请受理、等待与失败 | 标准加入/邀请流程；已提交、已排队与已 accepted 不互换 |
| 当前目标授权 | 读取或准备一个具体动作 | Station 已确认 exact 账号/设备/目标/scope、accepted basis、当前 membership/incarnation、相应能力与 policy |
| 设备密码状态 | 加密目标上的应用消息认证和生成 | 本设备可用的正确 MLS group/epoch、已接纳 winning transition 与匹配的治理结果；实际 RFC 9420 验证通过 |
| 当前窗口 | 最近消息及必要显示状态 | 标准有界窗口已安装，limited/gap/继续位置明确；单条正文通过适用的认证/解密 |
| 按需扩展 | 旧窗口、更多名单及媒体 | 对应范围的当前授权、分页/retention 与独立资源预算 |

对于一个具体发送动作，只要会话/设备、目标当前授权、exact authoring 输入与适用的本机密码状态均满足正式 gate，客户端 MUST 允许继续标准提交，
不以最近消息窗口或其余页面资源尚未完成阻止该动作。合法空 Realm 不要求先取得第一条历史消息；合法只读范围不以 write capability 作为显示正文的前置。
每次提交仍由服务器重新 admission；本地排队不表示 accepted，准备成功或 UI 可发不等于权限租约。加密失败 MUST NOT 自动改用明文。

旧消息按其真实历史 epoch/binding 与当前历史访问范围处理，不强制等于当前 epoch；旧页缺钥不得阻止已满足条件的新消息提交。
MLS 所需 tree、Commit/Welcome 与设备私钥仍必须完整处理，不能用空状态、截断树或任意最新 artifact 假装就绪。

账号/设备失效、leave/ban、相关 scope 的 key-access 变化及 durable ACK MUST 有独立推进配额，不能被 Realm 窗口过滤或历史任务饥饿。
当前用户动作关键依赖优先于最近窗口，最近窗口优先于后台旧历史/完整名单；同 Realm 重复工作 SHOULD 合并，慢 Realm MUST 独立等待并允许取消。
实现 MUST 对请求并发、解析/物化字节、任务队列与单次 CPU 工作设置有限预算；浏览器中的 CPU 密集步骤使用 worker 或可让出的分片。
仅把完整历史循环放入 async 函数不满足此要求；不得每个同步 tick 对所有 Realm 历史重新扫描或重放治理。
账号安全集合的完整性规则仍适用，但首页渲染与不依赖该集合的读取无需等待全部 baseline；敏感操作等待自身必需的会话/设备状态。

验收 MUST 分别记录首个摘要可见、目标可读、目标可提交、服务端 accepted、对端解密及窗口/全局 baseline 完成；按钮可用或没有崩溃不代表端到端完成。
冷 Station、暖 Station、新设备及重启恢复分别计量；不承诺与真实密码学输入规模无关的固定时间。列表分页与需求变化须使用已登记的单一同步合同，
本节不使未登记的 sliding/subscriptions 字段或私有 endpoint 成为合法 wire。

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
- **历史密钥材料**:join 前历史解密所需的密钥材料按 `(effective_scope,epoch)`（等价地按 canonical derived `mls_group_id,epoch`）分区；`history_secret`、exporter 派生密钥或等价逐条解密密钥 MUST 存于硬化密钥存储，其保护级别 MUST 等同于账户 MLS secret(在 Web 上即非导出 SubtleCrypto 密钥 + IndexedDB 层);**MUST NOT** 以明文落盘，且 **MUST NOT** 镜像到弱化的同步/首屏存储层(如 localStorage)。
- **静态加密包裹密钥的归属**:用于上述明文缓存静态加密的 at-rest 包裹密钥本身 MUST 存于硬化密钥存储。当硬化存储不可用时，客户端 MUST fail closed——缓存仅驻内存、**MUST NOT** 以明文落盘兜底，除非用户显式 opt-in 并被告知降级风险。
- **生命周期擦除**:设备 lock、软登出与设备吊销后，客户端 SHOULD 丢弃驻内存的 at-rest 包裹密钥并清除解密明文缓存，使已落盘的密文不可再解(本机范围；无法远程擦除其他设备)。

实现侧自检(descriptive):落盘完成后直接读取持久化存储的原始字节，对加密 Realm 的解密明文与历史密钥 **MUST NOT** 命中已知明文/密钥字节；此自检作为防止"新增内联字段又把敏感数据明文落盘"的回归守卫。交叉引用见 [`encryption-and-audit.md` §5.6](../crypto-media/encryption-and-audit.md)。

### 14.2 History-only multi-candidate store（normative）

History response、portable backup restore 与 RHRK archive 的 material 只写 history-only store。received material 全局 key 为
`(effective_scope,mls_group_id,epoch,candidate_digest)`，origin 不参与 bytes 身份；每 scope/group/epoch 最多 8 份 resident secret material。
新实例取得不可变 `material_received_sequence`，同 bytes/新 origin 不刷新；bytes 驱逐后 refetch 才取得新 sequence。独立
`CandidateOriginAttribution=(material_key,origin_domain,origin_ref)` 账本另存稳定 `origin_quota_domain`；response 按 source sender、RHRK 按 holder/key tuple、
portable backup 按 series/producer 配额，具体 response/archive/envelope 只进 retrieval ref。每 candidate 最多 4 条、每 exact quota domain/epoch 最多 64 条、
每 epoch 总计 256 条，固定 30 日 TTL 且 duplicate/refetch 不续期；确定性裁剪顺序见 history-visibility §7。
本机 verified MLS state 直接导出项另记为
`local_authoritative`，不占 received 槽且永不驱逐。

AEAD 成功或失败只向独立 `EventCandidateBinding=(event_binding_key,candidate_digest,outcome)` 账本写入 exact Event attribution，
不含/不推导 origin，均不得把 secret bytes pin 住或建立 epoch-level winner。超配额时先驱逐 unbound/failure-only material，再驱逐
success-bound material；同级按 `(material_received_sequence,candidate_digest)` 升序，只删除 bytes/sequence 并保留有界 tombstone 以便 refetch。
Event binding 账本每 epoch 最多 256 条、30 日不可延长 expiry；其裁剪不得改写 replay ledger 或 `local_authoritative`。完整规则与唯一常量见 history-visibility §7 及
history-recovery scalability registry。

Receiver 必须先 durable 保存 request private key/pending intent，再创建 request。source 必须先取得 manifest 的
accepted/duplicate 小型 receipt；manifest 尚未 accepted 时提交 chunk，release service 必须以 dependency missing 零写入拒绝，
不得建立 pending chunk、response record 或 attestation。Receiver 只在 manifest descriptor、自己 Station 的 receipt-bound 治理/释放结果、service record、
release attestation 与 HPKE 全部验证后原子安装。每个 response record 写入
`installed|cryptographically_rejected|superseded_duplicate|service_record_lost` disposition 后才可 ack；manifest 的
`installed` 只表示 descriptor 已安装，不完成任何 epoch coverage，reject/lost 同样不完成 coverage。

永久终态按 `(scope,epoch,authorization incarnation,endpoint incarnation,reason)` 隔离。只有完整 direct Seal replay 结合 current 单向收紧 history_access 与 incarnation/join floor
证明 T0 不可逆排除时使用 `decryption_unavailable_by_policy`；standard MLS Event 未覆盖 endpoint initial Add/Welcome 时
使用 `decryption_unavailable_by_profile_floor`。T1 暂时失权、source 离线、proof/chunk 缺失仍可恢复，不得停止重试。

## 15. E2EE and MLS Sync Performance

E2EE Realm 的同步必须把“事件顺序”和“密钥可用性”分开处理。事件可以先进入本地 raw event cache；解密可以异步完成。

客户端处理加密 timeline 时 SHOULD：

1. 先验证 event envelope、hash、signature、`realm_id`、`refs[role=authorized_by]` 和 `prev_refs`。
2. 根据明文 routing metadata 将事件放入 timeline / reducer 队列。
3. 检查事件声明的 `mls_epoch`。
4. 如果本地缺少该 epoch 的 group state，拉取缺失 `ak.mls.*` state event、MLS Commit 和必要 key backup。
5. 如果仍无法解密，将事件标记为 `decryption_pending`，但保留排序位置和引用关系。
6. 当 MLS epoch 补齐后，异步重试解密并更新 materialized view。

服务器和 Station sync surface 不需要解密正文，也不得因为无法解密而改变事件顺序或过滤事件。

为降低大规模 E2EE 同步成本：

- 当加密 timeline 中包含未知 epoch 的事件时，MLS epoch state SHOULD 作为 required state 返回。
- 客户端 SHOULD 按 `(canonical_mls_group_id, epoch)` 缓存 active epoch state 与 ratchet tree；Realm-default 与同 Realm 内各 Circle 的独立 group 不得碰撞。
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

> 此处对 `hlc` / `created_at` 的使用**不越** [`../conformance/encoding.md` §7](../conformance/encoding.md) 的 HLC advisory 边界：它只驱动**客户端本地**的解密诊断 UI（何时把某消息从 `decryption_pending` 标为 `decryption_failed`），不进入授权决策、Lattice 收敛、Control Move precondition 或 Seal finality。由于基准取自 producer 可控字段，实现 **MUST** 对该 deadline 施加 future 上界钳制，避免异常 producer 把某消息的 `decryption_failed` 判定推向远未来而长期滞留无诊断 pending：当基准取 `hlc` 时，该值已受 [`../conformance/encoding.md` §7](../conformance/encoding.md) 的 HLC drift 校验（`hard_future_skew_ms`，默认 300_000）在入站时钳制；当 `hlc` 缺省而回退到 `created_at` 时，实现 **MUST** 以同一 `hard_future_skew_ms` 上界对 `first_pending_at` 相对本地时钟做等价钳制（`created_at` 不经 §7 HLC 校验，须由本诊断路径自行施加该上界）。



在 timeout 前，客户端 SHOULD 按以下顺序恢复；其中第 3 项在后述条件满足时是 MUST，不是可选 UX：

1. 拉取缺失的 `ak.mls.*` state event、winner `ak.mls.commit`、Welcome 和 `governance_binding` 依赖。
2. 查询本 actor 授权设备的 encrypted key backup / secret storage。
3. 对声明 `ak.profile.e2ee_client.v1` 与 `ak.feature.history_key_recovery.v1`、且 current scope 为
   `content_scheme=mls_exporter_aead_v1` + `history_access=all_history_for_current_members` 的客户端，MUST
   按 [`history-visibility.md` §6.1](../governance/history-visibility.md) 自动创建/恢复 private history-key request、持续读取
   response stream，并作为 eligible current peer 自动耐久响应。其它 policy/profile 只在明确允许时 MAY 请求
   current authorized peer 对指定 epoch range 发送 key share。
4. 若 Realm policy 声明 Archive Node / Audit Node / Key Recovery Service，可向该受托服务请求最小 epoch range。

以上顺序是恢复优先级，不构成跨阶段或跨 scope 的全局屏障。强制 history-key 恢复的实际前置满足后 MUST 独立推进；
成员证明与 MLS lineage 就绪是不同阶段，不得形成 membership → Add → join epoch → membership 的循环。
单项失败、丢失通知与用户可见 timeout 的处理遵循 [`history-visibility.md` §6.1](../governance/history-visibility.md)。

当连续 epoch 缺口超过 `epoch_gap_recovery_threshold`（默认 32 个 epoch）或本地 backfill 预算耗尽时，客户端 SHOULD 切换到 range-based recovery：按 epoch 区间请求 key material、MLS Commit chain 和必要 snapshot proof，而不是逐消息重试。任何 key share 都必须绑定接收 principal、device、epoch range、policy hash 和发送设备签名；不得向已被移除、未授权或无法验证的成员请求密钥。

对上述强制 history-key 恢复，空 response page 不是完成、失败或可 ACK 的页；客户端必须保留原 high-water 并有界退避续读。
暂时没有响应只能记为 `awaiting_authorized_source_response`，不得在无受验证证据时推断“source 离线”或“密钥已销毁”。

超过 `decryption_pending_timeout` 后，客户端 MUST 将用户可见投影标记为 `decryption_failed`，保留 metadata-only 占位、排序位置、引用关系和重试诊断，并向用户显示不可解密状态。若之后合法 key material 到达，客户端 MAY 重新解密并把状态从 `decryption_failed` 恢复为 verified content，但该 MAY 受 [`encryption-and-audit.md` §2.10](../crypto-media/encryption-and-audit.md) late key recovery 状态机约束：必须通过原始接收时刻 T0 的 membership / history / key scope 校验，UI 必须显示 late recovery timeline marker；audit profile 下必须先 emit `ak.audit.accessed` 并取得 RYW receipt 后才可显示明文。恢复审计记录必须保留，不得静默替换原 metadata-only 占位。
