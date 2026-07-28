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
派生的 AEAD key，并把上述不可变 server-visible header 的 canonical digest 绑定进 AAD。
其中：

```text
aad_digest = H(canonical_json({
  realm_id, scope_ref, sender_actor_id, sender_device_id, seal_ref,
  signal_class, sent_at, expires_at,
  scheme: encrypted_payload.scheme,
  epoch: encrypted_payload.epoch,
  nonce: encrypted_payload.nonce
}))
```

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
- canonical envelope ≤ 64 KiB，AEAD plaintext ≤ 48 KiB；ChaCha20-Poly1305 tag 计入
  `ciphertext`，其 unpadded base64url 最大长度为 65,558 characters；
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

## 4. Rail

`send` 接受一个 `SignalEnvelope`；`subscribe` 在既有 authenticated live connection 上输出
同一 envelope 和 transport control frames。新增 payload type 不得新增 endpoint、stream
frame kind 或 server-visible selector。

peer relay 是显式 profile。source peer 验证 envelope 后只向目标 Realm 已登记的下一个 peer
转发一次；destination 重新执行全部验证。relay receipt 不是 durable acceptance、Seal 或
delivery guarantee。

## 5. 与 to-device 的硬边界

`ak.key.verification.*`、`ak.secret.request/send`、`ak.realm_key.request` 以及直接参与设备验证、
密钥分发、历史恢复的消息使用 `DeviceMessageEnvelope` 和可靠队列。它们不得进入 broadcast
Signal，也不得使用 signal TTL/单跳 fanout 语义。

## 6. 最小正反例

正例：typing payload 和 `strand_id` 加密，外层只暴露 Circle `scope_ref` 与 `session`。

反例：外层携带 `signal_kind=typing` 或 `call_id`，即使内容仍加密也违反元数据最小化。

反例：服务端因 operation 存在而对所有 Realm 全局广告 Signal，却不能验证某 Circle 的 MLS
basis。该广告不合规，必须按 scope 撤下。
