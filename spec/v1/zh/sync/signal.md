---
title: Signal Extension
status: candidate
normative: true
stability: v1
updated: 2026-08-08
---

# Signal Extension

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Signal 是可选 Extension，不是 durable Event 或 core to-device 的别名。它只有一个
encrypted envelope、一条 send/subscribe live rail 与一个可选单跳 peer relay。
标准 plaintext payload profile 必须在独立 closed schema 中登记（封闭登记表与通用最小集见
§1.1）；profile schema 只在接收端
解密后应用，不得把其中的 `kind`、产品 target 或 sequence 提升到外层 routing metadata。

## 1. Envelope

```text
SignalEnvelope {
  realm_id, scope_ref, sender_actor_id, sender_device_id, seal_ref,
  signal_class, sent_at, expires_at, encrypted_payload, proof
}
```

Signal 始终是短 TTL encrypted-only transport，不是 Event、history response 或 durable object。Sender proof 使用
`ak.signal-proof-v1` 并覆盖移除 proof 后的完整 envelope digest。普通/Agent/minimal sender 的 identity 与 current
authorization 按各自 profile 验证。

Signal 的 raw key 必须 per verified sender 派生；exporter scope 可用本 epoch history secret，standard MLS 使用
同 epoch、不可交付的 `ak.signal-root-v1` exporter root。两者都以 exact active Leaf BasicCredential identity 作为
`ak.signal-v1` context。Nonce 使用该 `(group,epoch,sender)` 域的 durable full-width counter：

```text
K_signal = ExpandWithLabel(signal_root[N], "ak.signal-v1", sender_domain, AEAD.Nk)
nonce = I2OSP(counter, AEAD.Nn)
```

Signal encrypted payload 的 closed pre-encryption header 必须绑定 scope/sender/seal/class/time/scheme/group/epoch/state/
counter；AAD 是该 header 的 JCS bytes。Counter 回退/复用 fail closed，不得 prefix 或 random fallback。Signal 不得借
history mailbox 交付 standard signal root，也不得把 Signal digest 注册为持久 ID。

### 1.1 Plaintext payload profile 通用最小集（normative）

每个标准 plaintext payload profile 都 MUST 在独立 closed schema（`additionalProperties:
false`）中登记，并且 MUST 至少携带下面两个通用字段——它们不是各 profile 的可选装饰，而是
Signal rail 的路由与去重前提：

| 字段 | 约束 |
| --- | --- |
| `kind` | `const`，取该 profile 的 payload kind（如 `ak.receipt.read`）。它是解密后的唯一 payload 判别式；外层不得出现同义 selector。 |
| `payload_sequence` | 非负 `u64`，按 `(sender_device_id, canonical scope_ref)` **严格单调递增但不要求连续**；§2 receiver high-water 的候选值。profile 自己的产品序列（call 的 `seq`、message stream 的 `seq`）与它相互独立，不得互相替代。 |

Realm scope、sender device 与发送时间由外层已签名 envelope 承载，plaintext MUST NOT 重复
`realm_id`、`sender_device_id` 与 `sent_at`（或等价的 `created_at`）；需要它们时接收方直接从
envelope 取值。profile 需要在密文内表达读者 / 发布者身份时使用 `actor_id`，接收方 MUST 校验
它逐字等于外层 `sender_actor_id`（`ak.receipt.read` 与 `ak.presence` 属此类）。plaintext TTL
字段（`ttl_ms`）只能收紧、不得放宽外层 `expires_at`。

v1 已登记的 plaintext payload profile 是封闭集合：

| payload `kind` | schema id | 定义正文 |
| --- | --- | --- |
| `ak.presence` | `ak.schema.signal_presence.v1` | [`../discovery/profiles-presence.md` §3.3](../discovery/profiles-presence.md) |
| `ak.typing` | `ak.schema.signal_typing.v1` | [`../discovery/profiles-presence.md` §3.5](../discovery/profiles-presence.md) |
| `ak.receipt.read` | `ak.schema.read_receipt.v1` | [`../discovery/read-receipts.md` §2.1](../discovery/read-receipts.md) |
| `ak.call.signal` | `ak.schema.call_signal_plaintext.v1` | [`../crypto-media/webrtc-signaling.md` §5](../crypto-media/webrtc-signaling.md) |
| `ak.message.stream` | `ak.schema.signal_message_stream.v1` | §7 |

接收方 MUST 先按外层 §3 admission 校验并解密，再按 `kind` 选中对应 closed schema 校验；
未登记的 `kind`、未通过对应 closed schema 的 plaintext MUST 以 `schema_violation` 丢弃，
MUST NOT 按字段名手工解析。新增 profile 只能新增登记行，不得新增 endpoint、
`SignalStreamFrame` kind 或 server-visible selector（§4.1）。

## 2. 时间与资源上限

对应可执行向量为 `ak.vector.signal.sequence_high_water.v1`。

- `expires_at` 必须晚于 `sent_at`，差值硬上限 120 seconds；
- `setup` 最大 120 seconds，`moderation` 最大 60 seconds，`session` 最大 30 seconds；
- canonical envelope ≤ 64 KiB（65,536 bytes），AEAD plaintext ≤ 46 KiB（47,104 bytes）。AEAD tag 计入
  `ciphertext`（v1 全部 active ciphersuite 的 tag 均为 16 字节），因此 `ciphertext` 的 unpadded base64url
  最大长度为 62,827 characters，与 envelope 上限之间留 2,709 bytes 承载其余 envelope 字段。
  **两个上限必须自洽**：plaintext 上限 MUST 使 base64url 后的 `ciphertext` 加其余字段仍不超过 envelope
  上限；把 plaintext 定成 48 KiB 会让单个 `ciphertext` 字符串（65,558 characters）就超过 envelope 上限，
  使该组合永远不可满足；
- relay 每次只允许一个 destination peer hop，不得形成 signal mesh 转发链；
- receiver 在 proof/AAD/AEAD/plaintext schema 全部通过后，按 `(sender_device_id, canonical
  scope_ref)` 维护 `payload_sequence` high-water；新值 MUST 严格大于旧值，但任意正向 gap
  （例如 `7 -> 1024`）MUST 接受。`N+1` 先到后，迟到的 `N` 是
  `signal_payload_sequence_stale`，不是“缺少 catch-up”。
- exact same envelope digest 的重投是 `signal_exact_envelope_replay`；使用新 nonce/ciphertext
  形成的新 envelope 若 sequence 未推进则是上一项 stale。两条诊断 MUST NOT 混同。
- sequence 位于密文内，server 只按完整 `envelope_digest` 做短期 replay suppression，不解密、
  不读取 high-water，也不把 digest 升级成业务 ID。

sender MUST 使用 durable per-`(sender_device_id, canonical scope_ref)` `u64` allocator。允许先原子
预留 block；durable `next_unreserved` MUST 在返回 block 首值前提交。crash、reservation 尾部、
加密失败、admission 失败或 submit 结果不确定均可永久 burn sequence 并形成 gap，MUST NOT
回退或复用。多进程 / 多 tab MUST 共享原子 store/CAS 或单写 owner；process-local counter 不合规。
UUIDv7、wall clock、`sent_at`、随机 salt 或 AEAD nonce counter 均不得替代该公共 sequence。

部署 MAY 收紧 TTL/byte/rate 上限，但能力广告必须给出实际值。

## 3. Admission 与能力广告

sender、ingress、relay 和 receiver 都 MUST 验证：

1. `scope_ref.realm_id == realm_id`；
2. `seal_ref` 可验证，且 sender **actor** 在该 Realm / scope basis 下有实时发送资格
   （Realm / scope 授权域）；
3. sender **device** 的签名方法按 §1 的设备授权域规则在 verifier 的 current accepted
   device directory 下解析并通过 A / B 模型信任链校验；
4. `signal_class=moderation` 还具有对应 moderation action；
5. E2EE profile、epoch/AAD binding、proof 与 TTL 有效。`expires_at` 已过期的 envelope 在
   **任何**入口（含 local `POST /_arkret/self/signal`）MUST 被拒绝为 `param_invalid`，
   不得接受后静默丢弃。

不存在 plaintext branch。任何 MLS-backed scope 的 plaintext signal / 未加密 ephemeral 输入
MUST 以 `signal_plaintext_forbidden` fail closed。

conformance（`ak.vector.signal.device_authorization_domain.v1`）至少覆盖：

1. 设备在 current directory 为 active、授权晚于 `seal_ref`：设备授权检查通过；
2. 设备在 `seal_ref` 时曾 active、当前已 revoked / fenced / conflicted：拒绝；
3. fragment 看似为 device id，但 `verification_method` 的 bare full DID 经 adapter 投影不等于
   `sender_actor_id`，或 fragment 不等于 `sender_device_id`：拒绝；
4. current directory key 或 Tier-2 / service-attested 信任锚缺失：拒绝；
5. 设备 current active 但 sender 在 Realm `seal_ref` 下无 scope 发送资格或缺
   `signal_class` action：拒绝。

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
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
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
Signature profile。带 body 的 request MUST 携带并签名覆盖 `Content-Digest`，并覆盖
`@method`、`@target-uri`、`@authority`、
`Source-Service-ID`、`Destination-Service-ID`、两个 trust domain，以及 shared ingress
时的 `Destination-Service-Endpoint-Digest`。本 operation 把通用签名窗口进一步收紧为
`expires-created ≤ 5 seconds`；其它 clock-skew、endpoint、canonical body 与最小披露规则不变。

### 4.3 Source 与 destination admission

source 对每个 envelope MUST 先完成与 local `send` 相同的 schema、device proof（§1 设备
授权域：current accepted directory）、signed `scope_ref`、`seal_ref`（Realm / scope 授权域）、
`signal_class`、TTL 与 MLS/AAD admission，再按当前 accepted member
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
4. 重新验证完整 `SignalEnvelope` schema、producer device proof（每一跳都按**自己的**
   current accepted device directory 重新执行 §1 设备授权域校验；signed `scope/basis` 只是
   Realm 授权 basis，不得误读为设备授权 basis）、`seal_ref`、sender 在
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

`ak.key.verification.*`、`ak.secret.request/send`、`ak.history_key.request` 以及直接参与设备验证、
密钥分发、历史恢复的消息使用 `DeviceMessageEnvelope` 和可靠队列。它们不得进入 broadcast
Signal，也不得使用 signal TTL/单跳 fanout 语义。

## 6. 最小正反例

正例：typing payload 和 `strand_id` 加密，外层只暴露 Circle `scope_ref` 与 `session`。

反例：外层携带 `signal_kind=typing` 或 `call_id`，即使内容仍加密也违反元数据最小化。

反例：服务端因 operation 存在而对所有 Realm 全局广告 Signal，却不能验证某 Circle 的 MLS
basis。该广告不合规，必须按 scope 撤下。

## 7. Message 正文流式预览 payload profile

`ak.profile.signal_message_stream.v1` 定义 Signal plaintext payload kind
`ak.message.stream`。其 schema 是
[`signal-message-stream.schema.json`](../../artifacts/schemas/signal-message-stream.schema.json)。
它只提供尚未成为 durable Message 的、发送者设备认证过的正文预览；它不是 Content Block、
Event 分片、Blob upload progress、revision 或最终提交。外层 MUST 是 §1 的
`SignalEnvelope`，`signal_class` MUST 为 `session`，不得新增 plaintext envelope、endpoint、
stream frame kind、cursor 或 replay rail。

### 7.1 身份、作用域与授权

producer 在首帧前 MUST：

1. 预生成最终 `ak.message.create` 的 `event_id`；
2. 把该 EventId 的完整 33-octet token 重类型为 `ak:message:<44-char-event-token>`，作为每帧 `message_id`；
3. 持久化 `{event_id, attempt, stream_id}`；`message_id` 只能从 `event_id` 派生，不是第二份
   producer-chosen identity。

`stream_id` 为每个 attempt 新生成的 `ak:message_stream:<uuidv7>`。producer 丢失上述状态时
MUST 生成新的 Event/Message identity，不得猜测或复用旧 identity。

解密后的 `strand_id` MUST 在 Signal 外层签名 `scope_ref` 指定的 Realm/Circle security scope
内，`track_name` 固定为 `discussion`。sender MUST 同时持有 `ak.message.stream.send` 和目标
Message create 所需授权；因为精确 kind 与 target 按 §1 强制加密，service 只能执行外层实时
发送资格与 scope gate，recipient MUST 在展示前按 `seal_ref` basis 重验这两个产品级 action。
授权、scope、schema 或 AEAD 任一项不可验证时 MUST fail closed 且不得显示正文。

### 7.2 帧与资源常数

每个 decrypted payload 都携带通用 `payload_sequence`，供 §2 的 sender-device/scope replay
处理；它与每条 stream 自己从 0 严格递增的 `seq` 相互独立。`frame_kind` 是 closed 三值：

- `keyframe`：携带截至当前的完整 `text`、固定 `format=plain|markdown` 与 `truncated`；
- `delta`：只携带非空 `text_append`，并要求 `base_seq` 等于 producer 上一正文帧的 `seq`；
- `abort`：只携带低敏 `reason_code=generation_cancelled|generation_failed|superseded`。

`seq=0` MUST 是 keyframe。format 在同一 stream 内不得改变；delta 只能追加有效 UTF-8，不支持
删除、替换或格式切换。正文允许 LF、CR、TAB，禁止其它 C0 控制字符和 DEL。

本 profile 的固定限制为：

| 维度 | v1 上限 |
| --- | ---: |
| 累积 plaintext preview | 16 KiB UTF-8 |
| 单 stream producer 发送率 | 5 frames/s |
| 单 device 并发发送 stream | 8 |
| 单 stream 生命周期 | 10 min |
| consumer stalled 标记 | 30 s |
| 单 device 同时展示 stream | 8 |

16 KiB 是 §2 的 46 KiB Signal plaintext / 64 KiB canonical envelope 总上限之内的 profile
子上限。conformance 必须覆盖 16,384 个 ASCII quote/backslash 的最坏 JSON 转义 keyframe；
合法最大 keyframe 仍须装入两层 Signal 上限，不得把超限帧静默截短。service 不得解密以执行
per-stream 限制；它只执行外层 envelope/rate/backpressure budget。producer 和 recipient 都
MUST 执行 plaintext、stream count、lifetime 与 frame-rate 边界。

### 7.3 Keyframe 调度

首帧之后，满足任一条件时 producer MUST 发 keyframe：

1. 当前 preview UTF-8 bytes 大于或等于
   `max(1, previous_keyframe_bytes * 2)`；
2. 距上一 keyframe 的单调时钟时间达到 15 seconds；
3. 即将达到 16 KiB profile 上限。

达到上限时 producer MUST 发 `truncated=true` 的自足 keyframe，停止发送 delta；在 final 或
abort 之前仍 MUST 每 15 seconds 以内重复同一正文的自足 keyframe。最终 Message 可继续增长，
并按普通 inline text 或 Blob-backed long text 规则提交。

### 7.4 attempt 与 consumer 状态机

receiver 对同一 `(sender_actor_id, sender_device_id, message_id)`：

1. 没有活动 preview，或收到更大 `attempt` 时，只有 `seq=0` keyframe 能激活/替换；更大
   attempt 的 delta/abort 在该 keyframe 前忽略，已见更大 attempt 后的较小 attempt 永远忽略；
2. 同一 attempt 只允许一个 `stream_id`；出现第二个 stream id 表示 producer 分叉，receiver
   MUST 冻结该 Message preview、记录安全诊断并等待 final，不得按到达时间选 winner；
3. keyframe 仅在 `seq > last_content_seq` 时直接替换 preview；`highest_observed_seq` 只用于
   诊断，不得阻止稍后到达但仍更新的 keyframe；
4. delta 仅在 `seq > last_content_seq && base_seq == last_content_seq` 时追加；否则忽略正文并
   等待 keyframe，不得清空已经认证的前缀；
5. 当前 attempt/stream 的 abort 终止该 attempt；未激活更大 attempt 的 abort 不影响当前
   preview；
6. 30 seconds 无有效帧则标记 stalled；10 minutes 后丢弃未完成 preview。

Signal rail 的丢失、重复、乱序、backpressure drop 和断线都是正常输入。consumer 不需要
reorder buffer；service MUST NOT 保存 stream `seq`、attempt、正文、final/abort 或恢复缓存。

### 7.5 最终 Message 绑定

receiver 只有在以下条件全部成立时才把 durable final 绑定并替换 preview：

1. Event kind 为 `ak.message.create`，其 schema、proof、authorization 与 reducer 全部通过；
2. payload 不携带 `message_id`，物化 `Message.id` 等于把 `Event.event_id` 的完整33-octet token
   重类型为 `ak:message:`，且与 preview `message_id` 相等；
3. final Event 不含 `executed_by`；preview 的 `sender_actor_id == Event.actor_id`，且
   `sender_device_id` 等于从 final proof 的已验证 `verification_method` 解析并授权的设备；
4. preview/final 的 Realm、由 `scope_ref` 确定的 security scope、Strand 与 discussion track
   全部相等。

final 正文可以与最后 preview 不同；receiver 直接以 final 为准，差异不是协议错误。preview
不增加 hash commitment，也不承诺一定出现 final。收到合格 final 后，receiver MUST 终止该
message 的全部 preview attempts。委托执行的 final 因 Signal 外层没有同时表达 principal of
record 与 executor provenance，MUST NOT 与本 profile 的 direct preview 绑定。
