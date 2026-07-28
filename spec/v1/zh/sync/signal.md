---
title: Signal Extension
status: candidate
normative: true
stability: v1
updated: 2026-07-28
---

# Signal Extension

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Signal 是可选 Extension，不是 durable Event 或 core to-device 的别名。它只有一个
encrypted envelope、一条 send/subscribe live rail 与一个可选单跳 peer relay。

## 1. Envelope

```text
SignalEnvelope {
  realm_id,
  scope_ref,
  sender_actor_id,
  sender_device_id,
  seal_ref,
  signal_class,
  sent_at,
  expires_at,
  encrypted_payload,
  proof
}
```

`scope_ref`、sender、Seal basis、时间、`signal_class` 与 ciphertext metadata 进入
`envelope_digest`；device proof 使用
`canonical_json({context:"ak.signal-proof-v1", envelope_digest, sender_actor_id,
sender_device_id, verification_method, created_at, domain?, audience?})`，其中 proof
`created_at` 必须逐字等于外层 `sent_at`。`encrypted_payload` 必须使用 scope 当前 MLS exporter
以 label `ak.signal-v1`（[`exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)）
派生的 AEAD key，并把上述不可变 server-visible header 的 canonical digest 绑定进 AAD。其中：

```text
aad_digest = H(canonical_json({
  realm_id, scope_ref, sender_actor_id, sender_device_id, seal_ref,
  signal_class, sent_at, expires_at,
  scheme: encrypted_payload.scheme,
  key_ref: encrypted_payload.key_ref,
  purpose: encrypted_payload.purpose,
  aead_profile: encrypted_payload.aead_profile,
  epoch: encrypted_payload.epoch,
  nonce: encrypted_payload.nonce
}))
```

`key_ref`、`purpose` 与 `aead_profile` 是 [`../conformance/encoding.md` §10.1](../conformance/encoding.md)
对每个 AEAD-bearing envelope 的最低 AAD 绑定要求，同时也是 canonical nonce 派生 context
`{key_ref, epoch, device_id, purpose, aead_profile}` 的分量——缺其一接收方就无法重算
`sender_nonce_prefix`。

**算法由 `aead_profile` 承载，不由 `scheme` 承载（normative）**：`scheme` 固定为
`ak.signal_exporter_aead.v1`，只标识构造方式；`aead_profile` MUST 是
[`mls-ciphersuite-registry.json`](../../artifacts/registry/mls-ciphersuite-registry.json)
某个 `status=active` 行的 `canonical_id`，且 MUST 等于 `key_ref.group_state_ref` 所指 MLS group
**实际协商**的 ciphersuite。reserved suite、未登记 suite 或与该 group 实际 ciphersuite 不符者
MUST fail closed（同 `encoding.md` §10.1 对全部 MLS-exporter 派生 domain 的统一规则）。
因此后续激活新 ciphersuite 时 Signal **无需任何 wire 变更**即可获得该算法；把算法名写进
`scheme` 会使每次激活都变成一次 wire-breaking 变更，v1 不采用该形态。

`aad_digest` 不包含自身、ciphertext 或 proof。`envelope_digest` 则覆盖移除 `proof` 后的完整
SignalEnvelope，因此同时承诺 ciphertext 与 `aad_digest`。`verification_method` 必须在
`seal_ref` 下解析为 `sender_actor_id` 为 `sender_device_id` 授权的 active device signing
method；不得用 verification-method fragment 与 device id 的字符串相等代替该授权验证。

`signal_class` 是服务端可见的唯一产品分类：

| 值 | 服务端用途 |
| --- | --- |
| `setup` | 唤醒、VoIP push、建立实时会话。 |
| `moderation` | 额外执行 moderation action gate。 |
| `session` | 普通 presence/typing/receipt/candidate/session 信号。 |

精确 payload type、Strand/Message/Call/receipt target、sequence 与内容都在 ciphertext 内。
服务端不得要求或推断更细 `signal_kind`。

## 2. 时间与资源上限

- `expires_at` 必须晚于 `sent_at`，差值硬上限 120 seconds；
- `setup` 最大 120 seconds，`moderation` 最大 60 seconds，`session` 最大 30 seconds；
- canonical envelope ≤ 64 KiB，AEAD plaintext ≤ 48 KiB；AEAD tag 计入 `ciphertext`，
  其 unpadded base64url 最大长度为 65,558 characters（按 16 字节 tag 计，v1 全部 active
  ciphersuite 的 AEAD tag 均为 16 字节）；
- relay 每次只允许一个 destination peer hop，不得形成 signal mesh 转发链；
- receiver 按 `(sender_device_id, scope_ref, payload_sequence)` 去重；sequence 位于密文内，
  server 只按完整 envelope digest 做短期 replay suppression。

部署 MAY 收紧 TTL/byte/rate 上限，但能力广告必须给出实际值。

## 3. Admission 与能力广告

sender、ingress、relay 和 receiver 都 MUST 验证：

1. `scope_ref.realm_id == realm_id`；
2. `seal_ref` 可验证，且 sender device 在该 basis 对 scope 有实时发送资格；
3. `signal_class=moderation` 还具有对应 moderation action；
4. E2EE profile、epoch/AAD binding、proof 与 TTL 有效。

不存在 plaintext branch。任何 MLS-backed scope 的 plaintext signal/legacy ephemeral 输入
MUST 以 `signal_plaintext_forbidden` fail closed。

Service Describe 的服务级 operation 广告仅表示 transport surface 存在，不表示每个 scope
可用。实现只有在同时提供 scope-aware profile/limit descriptor，并能在目标 scope 验证
encrypted signal 时，才能为该 scope 广告 Signal；否则必须撤下 scope capability。

## 4. Rail 与 peer relay

### 4.1 Local send / subscribe

`send` 接受一个 `SignalEnvelope`。canonical HTTP binding 的 `subscribe` 使用独立
`GET /_arkret/self/signal/subscribe` NDJSON response，并输出
[`SignalStreamFrame`](../../artifacts/schemas/signal-stream-frame.schema.json)：data frame
固定为 `{kind:"signal", envelope}`，control frame 只允许 `heartbeat`、`drain` 与
`unauthorized`。Signal stream 没有 cursor、catch-up、ack 或 durable delivery receipt；
control frame 不得推进任何 account/events position。

“既有 authenticated live connection”指 binding 可以复用同一 authenticated transport
session，而不是允许把 Signal 放进其它 operation 的 payload。启用
[`ak.profile.binding.websocket.v1`](./websocket-binding.md) 时，Signal subscribe 可以与
account/events channel 复用一个物理 WebSocket；三者仍是独立 canonical operation、独立
authorization 与独立 frame schema。HTTP fallback 下它们是独立 response。

新增 Signal plaintext payload type 不得新增 endpoint、`SignalStreamFrame` kind 或
server-visible selector；精确 signal kind 和 product target 始终位于 ciphertext。

### 4.2 单跳 peer operation

实现只有声明 `ak.profile.signal_peer_relay.v1` 时才能广告：

```text
operation: ak.peer.signal.command.relay
POST /_arkret/peer/signal
request:  ak.schema.signal_relay.v1
response: ak.schema.signal_relay.v1#/$defs/signal_relay_outcome
```

request 是闭合对象：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "signals": [
    {}
  ]
}
```

固定上限：

| 维度 | 上限 |
| --- | ---: |
| `signals[]` | 128 |
| canonical request body | 1 MiB（1,048,576 bytes） |
| 单个 `SignalEnvelope` | §2 的 64 KiB |
| HTTP Message Signature `expires-created` | 5 seconds |

这些上限合取生效；128 个接近单 envelope 上限的 item 不承诺能装入一个 request。source
加入下一项将使 count 或 canonical bytes 任一超限时 MUST 在 signal 边界拆批。destination
对 count/schema 超限拒绝整个 request，不得 partial accept；byte overflow 固定
`payload_too_large`。

本 operation 复用 [`federation.md` §3.2](./federation.md) 的 service-to-service HTTP Message
Signature profile。带 body 的 request MUST 携带并签名覆盖 `Content-Digest` 与
`Request-Canonical-Digest`，并覆盖 `@method`、`@target-uri`、`@authority`、
`Source-Service-ID`、`Destination-Service-ID`、两个 trust domain，以及 shared ingress
时的 `Destination-Service-Endpoint-Digest`。本 operation 把通用签名窗口进一步收紧为
`expires-created ≤ 5 seconds`；其它 clock-skew、endpoint、canonical body 与最小披露规则不变。

### 4.3 Source 与 destination admission

source 对每个 envelope MUST 先完成与 local `send` 相同的 schema、device proof、signed
`scope_ref`、`seal_ref`、`signal_class`、TTL 与 MLS/AAD admission，再按当前 accepted member
delivery binding 计算 destination service 集。source 只向至少托管一个 scope 内 active member
的 service 发一份 request；request 不携带 member、principal、device 或精确产品 target 列表。
一个 Realm 的多个 destination 由 source 分别直发，不能串成 relay chain。

destination 在任何 local fanout 前 MUST：

1. 验证 peer HTTP Message Signature、source/destination service DID、trust domain、endpoint、
   canonical body digest 与 5 秒窗口；
2. 要求所有 `signals[].realm_id == request.realm_id` 且
   `signals[].scope_ref.realm_id == request.realm_id`；
3. 验证 `Source-Service-ID` 是每个 sender actor/device 在当前 accepted member delivery
   binding 下的直接托管 service；不成立的 item 进入下述静默丢弃路径。这同时阻止
   destination 把收到的 signal 再转发第三 peer；
4. 重新验证完整 `SignalEnvelope` schema、producer device proof、`seal_ref`、sender 在
   signed scope/basis 的资格、三值 `signal_class` action gate、TTL、epoch/AAD binding；
5. 只按外层 `scope_ref` 计算本地 eligible devices，并执行 membership、Circle visibility、
   blocklist 与本地 rate/backpressure policy；
6. 把原 envelope 原样交给本地 live rail；精确 payload type、Strand/Message/Call/receipt
   target 与 sequence 只由 recipient 解密后校验。

source 与 destination MUST NOT 改写 `sent_at` / `expires_at`、ciphertext、AAD、routing header
或 producer proof，MUST NOT 重签 producer envelope，MUST NOT 解密后重加密。HTTP JSON 的
空白/成员顺序无需保留，但重新 canonicalize 后的完整 envelope digest identity MUST 不变。

schema-valid request 内的单个 signal 因 Realm/scope/sender 未知、producer proof 或 current
member delivery binding 不成立、过期、重复、sender 已离开、`signal_class` action gate
不通过、scope 不可见、本地无 eligible recipient 或本地 rail/policy 不接管而失败时，
destination 静默丢弃并 MAY 写 audit-only reason；不得向 source 返回 per-item 结果。只有外层
peer HTTP Message Signature / trust-domain / destination-endpoint 认证失败、跨 Realm batch 或
request schema/count/byte 超限才是 request-level reject，并复用 federation 的统一最小披露
错误/timing bucket。

### 4.4 Opaque outcome、重复与不确定结果

成功 response 固定为：

```json
{"accepted":true}
```

`accepted=true` 只表示已认证、结构合法的 peer request 被接管处理，不表示 Realm/scope/sender/
recipient/binding 存在，也不表示任何设备收到 signal。响应 MUST NOT 含 accepted/rejected count、
per-item outcome、recipient count、supported kind、envelope digest 或远端拓扑。无 local
eligible recipient 与存在 recipient 必须得到逐字相同 response。

operation registry 固定：

```text
idempotency_mechanism = none
retry_safe = false
uncertain_outcome.strategy = drop_unconfirmed
```

request MUST NOT 携带 `Idempotency-Key`。response 丢失、timeout 或连接中断后 source MUST NOT
自动重放 request；Signal 的恢复依靠下一个自足 frame或产品级 timeout/renegotiation。destination
可用完整 envelope digest 做有界短期 replay suppression；recipient 解密后仍按
`(sender_device_id, scope_ref, payload_sequence)` 去重。任何 dedupe 命中都不得绕过 peer
签名窗口与 producer proof 验证。

### 4.5 顺序、资源隔离与能力发现

peer relay 与 local/live rail 都允许丢失、重复和乱序，不保证 array、batch、source、destination
或 rail 之间的顺序。consumer MUST 在任意到达顺序下保持正确；依赖跨 signal 顺序才能正确的
payload 不得使用本 rail。

source/destination MUST 为 Signal relay 使用与 durable federation control/data 分离的有界
concurrency、pending-count、pending-bytes 与 per-peer/Realm byte-rate budget；typing/candidate
burst 不得饿死 Event、Seal、membership、MLS 或 dependency fetch。部署可在 128/1 MiB 固定
interop ceiling 内进一步用 rate limit/backpressure 拒绝当前负载，但不得把私有限值广告成新的
wire profile。

能力发现只使用：

- `supported_profiles` 包含 `ak.profile.signal_peer_relay.v1`；
- `supported_operations` 包含 `ak.peer.signal.command.relay`；
- operation registry 的固定 count/body/retry contract。

不得广告 `supported_signal_kinds` 或 per-member relay support；精确 payload kind 位于 ciphertext。
不支持 relay 时 local Signal 与 durable federation 仍可用，presence/typing 静默降级，call 可在
service-level profile preflight 后报告 peer relay unavailable，但不得暴露具体 remote member。

## 5. 与 to-device 的硬边界

`ak.key.verification.*`、`ak.secret.request/send`、`ak.realm_key.request` 以及直接参与设备验证、
密钥分发、历史恢复的消息使用 `DeviceMessageEnvelope` 和可靠队列。它们不得进入 broadcast
Signal，也不得使用 signal TTL/单跳 fanout 语义。

## 6. 最小正反例

正例：typing payload 和 `strand_id` 加密，外层只暴露 Circle `scope_ref` 与 `session`。

反例：外层携带 `signal_kind=typing` 或 `call_id`，即使内容仍加密也违反元数据最小化。

反例：服务端因 operation 存在而对所有 Realm 全局广告 Signal，却不能验证某 Circle 的 MLS
basis。该广告不合规，必须按 scope 撤下。
