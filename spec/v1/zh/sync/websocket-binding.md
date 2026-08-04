---
title: WebSocket Binding Extension
status: candidate
normative: true
stability: v1
updated: 2026-07-29
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

`base_url` **MUST** 使用下面的 canonical `wss` URI 形态：

- scheme 固定为小写 `wss`；
- DNS host 使用小写 A-label，禁止 userinfo、尾随点、query 与 fragment；
- 默认端口 `443` 必须省略，非默认端口使用无前导零的十进制；
- path 必须是非空 absolute path，移除 dot segment；percent-encoding 使用大写十六进制，
  且 unreserved 字符不得 percent-encode；
- UTF-8 长度不得超过 2048 bytes。

该值不得含 bearer、session grant、proof、DID、device id、cursor 或其它 credential。客户端
**MUST** 请求 WebSocket subprotocol `arkret.v1`，服务端未选择该 subprotocol 时客户端
**MUST** 关闭连接。一个声明本 profile 的 descriptor 的 `operations` 必须恰好包含本文件
登记的三个 operation；部分列表不是本 profile。

客户端遇到未知 kind/profile、缺字段、非 `wss` URL、超出自身 limit 或声明了本 profile
未覆盖的 operation 时，**MUST** 忽略该条 binding 并回退 HTTP；不得猜测 endpoint。

## 3. Origin 与认证

服务端在 HTTP Upgrade 阶段 **MUST**：

1. 校验 TLS、Host 与配置的公开 service origin；
2. 要求且只接受一个语法合法的 `Origin`，按 RFC 6454 serialization 得到小写
   scheme/host、移除默认端口且不带 path 的 canonical origin，并精确属于允许集合；
3. 拒绝缺失、重复或值为 `null` 的 `Origin`；本 profile 不定义无 Origin 的 native 旁路；
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

### 3.1 `challenge_dpop_session_v1` proof（normative）

本认证 proof 使用 RFC 9449 DPoP proof JWT 的 JOSE、`ath`、`nonce` 与 holder-key 规则，
但它位于 Upgrade 后的 Arkret `authenticate` application frame，不是 HTTP `DPoP` header。
因此 `htm="ARKRET-WEBSOCKET-AUTH"` 与 `htu=wss://...` 是本 profile 独有的 application
context。通用 HTTP DPoP verifier **MUST NOT** 接受 `ws` / `wss` 或该 method token；只有显式
进入 `challenge_dpop_session_v1` validator 的调用才能接受它。实现不得把它改写成 Upgrade
请求的 `GET` / `https` proof，也不得全局放宽 HTTP DPoP URI validator。

compact JWS 的 protected header 必须精确符合
`ak.schema.websocket_dpop_protected_header.v1`：

```json
{"alg":"Ed25519","jwk":{"crv":"Ed25519","kty":"OKP","x":"<43-char-base64url>"},"typ":"dpop+jwt"}
```

payload 必须精确符合 `ak.schema.websocket_dpop_claims.v1`，字段为：

| claim | 固定规则 |
| --- | --- |
| `jti` | 16..128 个 base64url 字符，生成时至少 96 bit 随机熵。 |
| `htm` | 精确字符串 `ARKRET-WEBSOCKET-AUTH`。 |
| `htu` | discovery `base_url` 通过 §2 canonical URI 校验后的**原字符串**；禁止 `ws`、`http`、`https` 映射。 |
| `iat` | NumericDate integer；必须处于 challenge 的 5 秒认证窗口内。 |
| `ath` | `BASE64URL_NOPAD(SHA-256(ASCII(session_grant)))`，固定 43 字符，不带 `sha256:` 前缀。 |
| `nonce` | 当前 `challenge.nonce` 原字符串。 |

`authenticate.session_grant` 必须是 1..16384 bytes 的可见 ASCII opaque token；这使 `ASCII(...)`
输入唯一，服务不得先做 Unicode normalization、trim 或其它重编码。

protected header 与 payload 不接受额外 member、duplicate member、`kid`、`x5*` 或 private JWK
member。两段 JSON 使用 RFC 8785 JCS UTF-8 bytes；签名输入精确为
`BASE64URL_NOPAD(protected_bytes) || "." || BASE64URL_NOPAD(payload_bytes)`，签名算法为
Ed25519，第三段是 64-byte signature 的无 padding base64url。`websocket-binding-fixture.json`
给出可重算的完整 KAT；只复制 expected compact string 而不验签不算通过。

服务发送 challenge 前，必须在共享的一次性 challenge store 原子写入：

```text
(connection_id, nonce) ->
  {canonical_origin, canonical_base_url, issued_at, expires_at, consumed=false}
```

`connection_id` 与 `nonce` 各至少含 128 bit 随机熵；`expires_at - issued_at` 不得超过 5 秒。
`connection_id` 和 Origin **不进入私有 JWT claim**：它们由该 server-side record 间接绑定。
服务验证 `authenticate.connection_id`、claim `nonce`、当前 socket 的 canonical Origin 与
claim `htu` 全部等于 record 后，才验证 grant active、audience、device binding、expiry、
scope、JWK thumbprint 等于 grant `cnf.jkt`，以及 `ath` 等于当前 frame 中
`session_grant` 的 hash。任一失败不得消费为成功或建立部分 session。

最终成功必须在同一原子步骤把 challenge 标为 consumed，并写 replay ledger key
`(cnf.jkt, jti, "ak.websocket-auth.v1")`。同 key、同 nonce 或同
`(connection_id, nonce)` 的第二次使用均失败；ledger 至少保留 300 秒，challenge record
至少保留到 `expires_at` 后 300 秒，以区分 replay 与 unknown。多实例部署必须使用共享一致
状态，不能用 process-local map。proof 重放、connection id/nonce/origin/htu/ath 不匹配或
认证超时均以 policy failure 关闭连接。

认证成功后服务端发送 `welcome`，至少包含 `connection_id`、实际 limits 与 heartbeat
interval。认证完成前双方不得发送/接受 `open`、`data` 或业务 control frame。

Session 临近过期时服务端可发 `reauth_required`；它建立一条新的上述 challenge record。
客户端用刷新后的 session grant 发送同一个 `authenticate` schema，proof 的 `nonce`、`ath`、
`iat`、`jti` 必须全部更新。旧 challenge、旧 proof 或旧 grant 的 `ath` 不得复用。reauth
成功前旧授权只可服务已 admission 的 channel，且不得超过原 grant expiry；失败或超时以
`1008` 关闭整个连接，客户端不得在旧授权下继续 channel。

## 4. Connection Frame

所有 frame 是一个完整 WebSocket text message，内容是一个 UTF-8 JSON object；binary
message 一律以 `1002` 拒绝。禁止一个 message 放多个 JSON value。WebSocket fragmentation
可由实现重组，但解析 JSON 前必须累计 bytes，并取 discovery、`welcome.max_frame_bytes` 与
1 MiB hard ceiling 的最小值；超限立即以 `1009` 关闭，不得先分配无界 buffer。

解析器必须在 schema validation 前拒绝 duplicate member；然后按方向使用
`ak.schema.websocket_server_frame.v1` 或 `ak.schema.websocket_client_frame.v1` 验证。全部
object 都是 `additionalProperties=false`；字符串、selector array、credential、pending
bytes/frames 与 reconnect delay 上限由 schema 固定。JSON Schema 的 `maxLength` 计 code
point，不替代上述 UTF-8 byte gate。

连接层 frame kind 是封闭集合：

- server → client：`challenge`、`welcome`、`opened`、`data`、`control`、`error`、
  `closed`、`ping`、`reauth_required`
- client → server：`authenticate`、`open`、`close`、`pong`

每种 kind 的 schema registry id 是
`ak.schema.websocket_<kind>_frame.v1`；全集使用 `ak.schema.websocket_frame.v1`。未知 kind、
错误方向、缺 required field、unknown field、duplicate member、非 canonical operation id
或连接状态违规使用 `1002`；只有 byte 超限使用 `1009`。业务 operation 错误使用 `error`
frame，不依赖 WebSocket reason string 传递完整诊断。

`data`、channel-scoped `control` / `error`、`close`、`closed`、`open` 与 `opened` 必须带
`channel_id`；connection-scoped `control` / `error` 禁止带该字段。该值是单连接内客户端生成
的 1..64 字符 opaque token；一旦用于 `open`，即使 channel 已失败或关闭也不得在同连接复用。
连接层 challenge/welcome/ping/pong/reauth frame 禁止 channel field。

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

`open` 是按 operation discriminator 闭合的 union：

- account：`parameters={after?,catchup?,filter?,wait_for?}`；`filter` 只有
  `realms/timeline_limit/lazy_load_members/include_redundant_members/event_kinds/not_event_kinds`；
- events：`parameters={realms?,actors?,after?,catchup?}`，`realms` / `actors` 至少一个出现；
- signal：`parameters={}`。

这些字段与 canonical HTTP operation 的 query/header 语义一致；`wait_for` 对应
`X-Arkret-Wait-For`。任何别名、未知参数或超限 selector 在 frame schema 阶段拒绝。服务端
重新执行 session、device、scope、Realm selector 与 capability authorization，不能因为连接
已认证而跳过 operation authorization。

成功后返回 `opened`，其中 `operation_id` 必须与 pending `open` 精确相同。重复 id 返回
channel-scoped `error(code="conflict")`；该 id 仍永久占用。超过 `max_channels` 返回
`rate_limited`，不得驱逐现有 channel。

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

`data.payload` 只接受 account `delta`、events `event` 或 Signal `signal`；`control` 的
`frame_scope="channel"` 只承载对应 operation 已定义的 heartbeat/drain/dropped/resync/unauthorized/
frontier/catchup/epoch 等 control payload。接收方先由 channel state 取得 operation，再用该
operation 的 canonical payload schema 验证；仅仅匹配其它 operation 的 union branch仍必须
拒绝并关闭该 channel。connection-scoped `control` 只接受 closed drain payload
`{kind:"drain",reconnect_after_ms,deadline,reason?}`。连接层 `ping`/`pong` 只判断物理连接
存活，不得推进任何业务 cursor。

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

WebSocket `error.error` 使用本 binding 的 closed transport error body
`{code,message,retry_after_ms?}`，不是 HTTP `ErrorEnvelope`；`code` 必须是
`error-code-registry.json` 的 `codes[]` 中已登记的 code，未知 code fail closed。Channel-scoped `error`
另带 `channel_id`；connection-scoped `error` 禁止该字段。`closed` 表示该 channel 终止，
不等于 cursor checkpoint或Signal delivery receipt。

服务部署 drain 时应先停止接受新 channel，发送 connection-scoped drain control，并在
`deadline` 前给现有 durable channel有限 checkpoint时间。客户端收到连接关闭后：

1. 持久化已完成处理的 durable cursor；
2. 遵守 `reconnect_after_ms`；
3. 尝试重新连接；
4. WebSocket 不可用、代理阻断、profile不匹配或连续握手失败时回退 canonical HTTP。

客户端 **MUST NOT** 同时保留 WebSocket 与 HTTP 两套相同 account/events/signal consumer；
transport切换必须先终止旧 owner，再启动新 owner。Web多标签页环境还必须先满足单 writer/
single leader要求，WebSocket multiplex不能替代跨标签页协调。

### 8.1 WebSocket close code（normative）

实现只使用 RFC 6455 标准 code，不登记私有 `4xxx`：

| code | 使用条件 |
| --- | --- |
| `1000` | 双方正常结束物理连接；channel 正常结束只用 `closed` frame。 |
| `1001` | 已发送 drain 且到达 deadline，服务停止。 |
| `1002` | binary、JSON/UTF-8/duplicate/unknown/direction/schema/state/subprotocol 协议错误。 |
| `1008` | Origin、challenge、proof、grant、reauth 或 connection-level authorization 失败。 |
| `1009` | 重组后的 text message 超过有效 byte limit。 |
| `1011` | 服务内部错误，不能继续保证 connection state。 |
| `1012` | 服务重启；若此前发过 drain，客户端遵守其 `reconnect_after_ms`。 |

reason string 若出现必须是 UTF-8、最多 123 bytes、不得含 grant、proof、nonce、DID、cursor 或
完整诊断。`1002` / `1009` 表示当前 binding 不兼容，客户端终止所有 channel并立即切换 HTTP，
直到 descriptor 变化或用户显式重试；`1008` 只允许一次 fresh grant + fresh socket 重试，
再次失败切换 HTTP；`1001` / `1012` 遵守 drain 后重连，连续三次未到 `welcome` 则切换 HTTP；
代理失败、Upgrade 非 `101` 或 subprotocol 未选择均立即切换 HTTP。切换前必须确认旧物理连接
已关闭，禁止双 consumer。

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

fixture 的 runner suite 固定为 `ak.suite.binding.websocket.v1`，必须执行而不是只加载 JSON：
逐条验证 exact UTF-8 frame bytes、方向 schema、DPoP KAT/变异、challenge replay ledger、
三 channel trace、reauth、drain、close code 和 HTTP fallback。profile requirement 同时登记
该 vector、fixture、runner suite、全部 frame schema 与三个 canonical payload schema；缺少
任一 runner mapping 的实现不得声称通过。
