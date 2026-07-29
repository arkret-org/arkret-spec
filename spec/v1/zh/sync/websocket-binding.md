---
title: WebSocket Binding Extension
status: candidate
normative: true
stability: v1-extension
updated: 2026-07-28
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按
[`normative-language.md`](../conformance/normative-language.md) 解释。

## 1. Profile 与边界

本扩展注册 profile `ak.profile.binding.websocket.v1` 与 binding kind `websocket`。它不是
Arkret v1 core mandatory transport；服务与客户端不支持本 profile 时继续使用 canonical
HTTP/JSON、NDJSON binding。

第一版只覆盖：

- `ak.self.account.stream.subscribe`
- `ak.self.events.stream.subscribe`
- `ak.self.signal.stream.subscribe`

它不覆盖 Event submit、Signal send、Blob、媒体、federation peer 或其它 command/resource/query
operation。普通写操作继续使用 canonical HTTPS binding。LiveKit/SFU 等媒体 WebSocket 不属于
本 profile，不得放进 `ServiceDescribe.supported_bindings` 的 Arkret `websocket` 条目。

一个 authenticated Principal Server session **SHOULD** 只建立一个 Arkret WebSocket；上述
operation 作为逻辑 channel 在该物理连接内多路复用。operation 的授权、cursor、filter、
dedupe、catch-up 与完成语义保持独立，不因共享连接而合并。

## 2. Discovery

服务只有在实现并通过本 profile conformance 时，才能广告：

```json
{
  "kind": "websocket",
  "base_url": "wss://server.example/_arkret/ws",
  "operations": [
    "ak.self.account.stream.subscribe",
    "ak.self.events.stream.subscribe",
    "ak.self.signal.stream.subscribe"
  ],
  "extension_profile_required": "ak.profile.binding.websocket.v1",
  "subprotocol": "arkret.v1",
  "authentication": "challenge_dpop_session_v1",
  "max_frame_bytes": 262144,
  "max_channels": 16
}
```

`base_url` **MUST** 使用 `wss`，不得含 bearer、session grant、DPoP proof、DID、device id、
cursor 或其它 secret/query credential。客户端 **MUST** 请求 WebSocket subprotocol
`arkret.v1`，服务端未选择该 subprotocol 时客户端 **MUST** 关闭连接。

客户端遇到未知 kind/profile、缺字段、非 `wss` URL、超出自身 limit 或声明了本 profile
未覆盖的 operation 时，**MUST** 忽略该条 binding 并回退 HTTP；不得猜测 endpoint。

## 3. Origin 与认证

服务端在 HTTP Upgrade 阶段 **MUST**：

1. 校验 TLS、Host 与配置的公开 service origin；
2. 对浏览器请求校验 `Origin` 精确属于服务允许的 Inkson origin 集合；
3. 拒绝 `Origin: null`，除非显式的非浏览器 deployment profile 定义替代认证；
4. 不从 URL query、cookie fallback 或 `Sec-WebSocket-Protocol` 接受长期 bearer。

Upgrade 成功不表示 authenticated。服务端首先发送：

```json
{
  "kind": "challenge",
  "connection_id": "opaque-random",
  "nonce": "base64url-random",
  "expires_at": "2026-07-28T12:00:30.000Z"
}
```

客户端必须在 5 秒内返回 `authenticate`：

```json
{
  "kind": "authenticate",
  "connection_id": "opaque-random",
  "session_grant": "opaque-session-grant",
  "dpop_proof": "compact-jws"
}
```

DPoP proof 的 target URI 是 discovery 中的 `base_url`，method token 固定为
`ARKRET-WEBSOCKET-AUTH`，并 **MUST** 绑定 `(connection_id, nonce, Origin,
session_grant_digest)`。服务端复用 canonical session grant 验证、device binding、撤销与
过期检查；proof 重放、connection id/nonce/origin 不匹配或超时均 fail closed。

认证成功后服务端发送 `welcome`，至少包含 `connection_id`、实际 limits 与 heartbeat
interval。认证完成前双方不得发送/接受 `open`、`data` 或业务 control frame。

Session 临近过期时服务端可发 `reauth_required` challenge。客户端用刷新后的 session grant
生成新的绑定 proof；reauth 失败时服务端关闭整个连接，客户端不得在旧授权下继续 channel。

## 4. Connection Frame

所有 frame 是一个完整 UTF-8 JSON object。禁止把一个 JSON object 跨多个 Arkret application
frame 分片；WebSocket 自身 fragmentation 可由实现处理，但必须在解析 JSON 前执行累计 byte
上限。

连接层 frame kind 是封闭集合：

- server → client：`challenge`、`welcome`、`opened`、`data`、`control`、`error`、
  `closed`、`ping`、`reauth_required`
- client → server：`authenticate`、`open`、`close`、`pong`

未知 kind、缺 required field、duplicate key、非 canonical operation id 或超过
`max_frame_bytes` 必须关闭连接，close code 使用 `1002`（protocol error）。业务 operation
错误使用 `error` frame，不依赖 WebSocket reason string 传递完整诊断。

每个业务 frame **MUST** 带 `channel_id`；该值是单连接内客户端生成的非空 opaque string，
不得跨连接承担幂等或身份语义。

## 5. Channel Open

客户端发送：

```json
{
  "kind": "open",
  "channel_id": "account-1",
  "operation_id": "ak.self.account.stream.subscribe",
  "parameters": {
    "after": "ak:cursor:opaque",
    "catchup": true
  }
}
```

`parameters` 与 canonical HTTP operation 的 query/body 参数语义一致。服务端重新执行 session、
device、scope、Realm selector 与 capability authorization，不能因为连接已认证而跳过
operation authorization。

成功后返回 `opened`。同一连接的 `channel_id` 不得复用；重复 id 返回 channel-scoped
`error(code="conflict")`。超过 `max_channels` 返回 `rate_limited`，不得驱逐现有 channel。

客户端可以同时打开一个 account channel、零或多个 events channel和一个 signal channel；
部署可以把 events channel 数限制得更低，但必须在 advertised `max_channels` 和 operation
limit 内一致执行。

## 6. Data 与 Control 映射

`data` frame 形态：

```json
{
  "kind": "data",
  "channel_id": "account-1",
  "payload": {}
}
```

`payload` 必须逐 operation 使用 canonical frame schema：

| operation | payload |
| --- | --- |
| `ak.self.account.stream.subscribe` | `AccountSubscribeFrame` |
| `ak.self.events.stream.subscribe` | canonical `EventsSubscribeFrame` |
| `ak.self.signal.stream.subscribe` | `SignalStreamFrame` 中 `kind=signal` |

`control` 只承载对应 operation 已定义的 heartbeat/drain/dropped/resync/unauthorized 等 control
frame，payload 仍按该 operation schema 验证。连接层 `ping`/`pong` 只判断物理连接存活，
不得推进任何业务 cursor。

### 6.1 Durable stream

Account/events channel 保持 canonical cursor 语义：

- cursor-bearing payload 才能推进 durable resume point；
- client 只有在 frame 已通过 schema/authorization并完成所需本地 durable checkpoint 后，
  才能把 cursor 用于下一连接；
- 连接断开后客户端用最后 durable cursor 重新 `open`；
- `dropped`、`resync_required`、catch-up 与 filter digest 规则与 HTTP binding 相同。

共享物理连接不得让一个 channel 的 cursor、error、close 或 filter 影响其它 channel。

### 6.2 Signal stream

Signal channel 无 cursor、catch-up、ack 或 delivery receipt。断线期间 Signal 不补发；重连只
重新建立 live fanout。`SignalStreamFrame.kind=drain` 的 `reconnect_after_ms` 只限制相同
session/device Signal channel，不限制 account/events 或其它 HTTP operation。

## 7. Flow Control 与公平性

服务必须同时限制：

- connection 与 channel 的 pending item 数；
- connection 与 channel 的 pending bytes；
- frame bytes、每秒 frame/bytes、idle 与最大 lifetime；
- 单 session/device 的 connection 数。

调度 **MUST** 防止 Signal 洪峰饿死 account/to-device 或 events cursor 推进。实现应给予
account control/data 最高或独立保留配额；达到 Signal queue limit 时允许丢弃 Signal，并可发
channel-scoped `control(kind="drain")`，不得删除 durable account/events frame来腾空间。

慢消费者导致 durable channel 无法在 limit 内排空，应对该 channel发送 `error`/`closed`，
让客户端按 cursor恢复；只有 connection-level protocol/auth/resource failure才关闭整个连接。

## 8. Close、错误与回退

Channel `error` 使用 canonical Arkret error object，并带 `channel_id`。`closed` 表示该 channel
终止，不等于 cursor checkpoint或Signal delivery receipt。

服务部署 drain 时应先停止接受新 channel，发送 connection-level drain hint，并给现有 durable
channel有限 checkpoint时间。客户端收到连接关闭后：

1. 持久化已完成处理的 durable cursor；
2. 遵守 `reconnect_after_ms`；
3. 尝试重新连接；
4. WebSocket 不可用、代理阻断、profile不匹配或连续握手失败时回退 canonical HTTP。

客户端 **MUST NOT** 同时保留 WebSocket 与 HTTP 两套相同 account/events/signal consumer；
transport切换必须先终止旧 owner，再启动新 owner。Web多标签页环境还必须先满足单 writer/
single leader要求，WebSocket multiplex不能替代跨标签页协调。

## 9. WebTransport 非继承

本 profile 不定义 WebTransport。实现不得把相同 frame直接搬到WebTransport后广告
`ak.profile.binding.websocket.v1`。WebTransport profile必须单独定义HTTP/3版本、双向/
单向stream、datagram size与loss/ordering、0-RTT replay、Origin、认证、连接迁移和可靠
fallback；没有该 profile时不得在Arkret discovery中广告WebTransport。

## 10. Conformance

声明本 profile的实现必须覆盖：

- Origin缺失/错误、subprotocol不匹配、认证超时、nonce/proof重放；
- 三种operation并发open与duplicate/越权channel；
- account/events断线按durable cursor恢复，Signal断线不补发；
- 单channel schema/error/close不误伤其它channel；
- Signal洪峰下account/to-device保留配额；
- server drain、reauth、session撤销与HTTP fallback；
- 两标签页中只有single leader拥有物理连接和durable writer。

上述发现、认证、多路复用隔离、backpressure、reconnect/downgrade与HTTP fallback由
`ak.vector.binding.websocket.v1`固定。实现只有运行
`websocket-binding-fixture.json`并通过全部正负向case后，才可在
`ServiceDescribe.supported_bindings`广告本profile；未知/不完整descriptor永远回退mandatory
HTTP/JSON与bounded NDJSON。
