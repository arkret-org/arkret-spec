---
title: Signal Extension
status: candidate
normative: true
stability: v1
updated: 2026-09-25
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
  realm_id, scope_ref, sender_actor_id, sender_device_id?, commit_ref,
  signal_class, sent_at, expires_at, encrypted_payload, proof
}
```

Signal 始终是短 TTL encrypted-only transport，不是 Event 或 durable object。Sender proof 使用
`ak.signal_proof.v1` 并覆盖移除 proof 后的完整 envelope digest；transcript 成员 `created_at` 由外层 `sent_at` 注入
（proof-context registry 该行的 `binding_field_sources`），proof 本身不携带第二个时间戳。sender 是 closed XOR：ordinary
account-device MUST 携带 `sender_device_id: DeviceId`；Agent MUST 省略该字段，且 `null`/空值非法。
字段存在性只选择候选分支，不能证明 actor 是 Agent；source 与 recipient 自己的 Station MUST 从 accepted principal
classification 和 current authority 独立确认。
MUST NOT 冒入 Agent 分支。两分支均不得合成 DeviceId、借用 controller device 或 ordinary
directory；不具备匹配 carrier/authority 的 endpoint/scope MUST NOT 广告 Signal 可用。本节不新增
endpoint、profile、版本或 runtime-epoch 字段。

`sender_actor_id` 是完整 `ActorId`。`verification_method` 的 bare DID 经已登记 adapter 投影后 MUST
等于其 signing principal 分量（account 分支的 `account_id.principal_id`）。ordinary 分支的 fragment
MUST 等于 `sender_device_id`；Agent 分支的完整 method MUST 逐字等于 current accepted
`ak.agent.key.authorize` signing-key binding。DID 投影不能证明 Station 分量、Agent classification 或
authorization；source 与 recipient 必须独立绑定完整 ActorId 与 endpoint authority，不得用入口
Station、session audience 或裸 principal 补造另一账号。完整 ActorId 和实际存在的 sender endpoint
字段同时进入 proof 与 AAD。destination 的 peer transport admission 不解析远端 authority、不验
producer signature；recipient 的端到端验证义务见 §3，治理准入由其自己的 Station 执行。

Signal 的 raw key 必须 per verified sender 派生；所有 MLS scope 都使用当前 epoch、不可交付的 `ak.signal-root-v1` exporter root。两者都以 exact active Leaf BasicCredential identity 作为
`ak.signal-v1` context。Nonce 使用该 `(group,epoch,sender)` 域的 durable full-width counter：

```text
K_signal = ExpandWithLabel(signal_root[N], "ak.signal-v1", sender_domain, AEAD.Nk)
nonce = I2OSP(counter, AEAD.Nn)
```

Signal encrypted payload 的 closed pre-encryption header 必须绑定 scope/sender/authority commit/class/time/scheme/group/epoch/state/
counter；AAD 是该 header 的 JCS bytes。header 是下列对象，全部成员在 authority commit 前冻结，并只从 envelope 顶层、
`encrypted_payload` 的已登记成员与已验证 group state 投影（`sender_device_id` 仅在实际存在时进入，缺席即整体省略该 key）：

```text
signal_aad_header = {
  realm_id, scope_ref, sender_actor_id, sender_device_id?, commit_ref, signal_class, sent_at, expires_at,
  scheme: encrypted_payload.scheme, key_ref: encrypted_payload.key_ref, purpose: encrypted_payload.purpose,
  aead_profile: encrypted_payload.aead_profile, epoch: encrypted_payload.epoch, nonce: encrypted_payload.nonce
}
AAD = RFC8785_JCS(signal_aad_header)
```

`nonce` 以 wire 上的 base64url 字符串逐字进入，`counter` 由 `nonce = I2OSP(counter, AEAD.Nn)` 反推。AAD 由 header
投影重算，不上 wire：`encrypted_payload` MUST NOT 携带 `aad_digest` 或 `key_ref.algorithm`——前者只是无密钥的本地重算值，
后者由 `aead_profile` 与 `key_ref.group_state_ref` 所指 group state 唯一决定，两者都是
[`encoding.md` §10](../conformance/encoding.md) 禁止的同 carrier 镜像。recipient 按本节重建 AAD 并在 AEAD open 时验证；
Station 只核对 header 的 basis 成员，不比对任何 AAD 摘要。
Counter 回退/复用 fail closed，不得 prefix 或 random fallback。Signal root 只能由接收端当前本地 MLS state 导出，不得通过任何网络响应交付；Signal digest 也不得注册为持久 ID。

### 1.1 Plaintext payload profile 通用最小集（normative）

每个标准 plaintext payload profile 都 MUST 在独立 closed schema（`additionalProperties:
false`）中登记，并且 MUST 至少携带下面两个通用字段——它们不是各 profile 的可选装饰，而是
Signal rail 的路由与去重前提：

| 字段 | 约束 |
| --- | --- |
| `kind` | `const`，取该 profile 的 payload kind（如 `ak.receipt.read`）。它是解密后的唯一 payload 判别式；外层不得出现同义 selector。 |
| `payload_sequence` | 非负 `u64`，按 verified sender endpoint 与 canonical scope（ordinary=`(sender_actor_id,sender_device_id,scope)`；Agent=`(sender_actor_id,agent_signing_public_key_digest,scope)`）**严格单调递增但不要求连续**；§2 receiver high-water 的候选值。profile 自己的产品序列与它相互独立。 |

Realm scope、sender endpoint 与发送时间由外层已签名 envelope 和 verified authority 承载，
plaintext MUST NOT 重复 `realm_id`、`sender_device_id`、Agent key digest 与 `sent_at`（或等价的
`created_at`）；需要它们时接收方从 envelope 和已验证 authority 取值。profile 需要在密文内表达读者 / 发布者身份时使用 `actor_id`，接收方 MUST 校验
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

recipient 客户端 MUST 先按 §3 的客户端角色执行端到端校验并解密，再按 `kind` 选中对应 closed schema 校验；
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
- receiver 在 current authority、proof/AAD/AEAD/plaintext schema 全部通过后，按上述两分支的
  verified endpoint domain 维护 `payload_sequence` high-water；新值 MUST 严格大于旧值，但任意正向 gap
  （例如 `7 -> 1024`）MUST 接受。`N+1` 先到后，迟到的 `N` 是
  `signal_payload_sequence_stale`，不是“缺少 catch-up”。
- exact same envelope digest 的重投是 `signal_exact_envelope_replay`；使用新 nonce/ciphertext
  形成的新 envelope 若 sequence 未推进则是上一项 stale。两条诊断 MUST NOT 混同。
- sequence 位于密文内，server 只按完整 `envelope_digest` 做短期 replay suppression，不解密、
  不读取 high-water，也不把 digest 升级成业务 ID。

sender MUST 使用 durable per-verified-endpoint/scope `u64` allocator。ordinary 域不变；Agent 域使用
完整 ActorId、SDK 对 current binding 32-byte raw Ed25519 key 计算的唯一
`agent_signing_public_key_digest` 与 canonical scope。允许先原子
预留 block；durable `next_unreserved` MUST 在返回 block 首值前提交。crash、reservation 尾部、
加密失败、admission 失败或 submit 结果不确定均可永久 burn sequence 并形成 gap，MUST NOT
回退或复用。多进程 / 多 tab MUST 共享原子 store/CAS 或单写 owner；process-local counter 不合规。
UUIDv7、wall clock、`sent_at`、随机 salt 或 AEAD nonce counter 均不得替代该公共 sequence。

Agent 正式首次配对、runtime replacement 和丢失 allocator 后的恢复配对 MUST 使用新签名 key；
replacement admission MUST 至少拒绝与被替换 runtime 相同的 raw key。同 key re-authorization、session
refresh、pause/resume、MLS epoch 更新、普通重启和保留 allocator 的部署迁移都不创建新 sequence
domain。仅持私钥但无法证明 allocator 未回退时 MUST 停止发送并走 new-key replacement，不得猜测、
读取某个 recipient high-water、改 method 后清零或 wrap `u64`。新 authorization accepted 且目标
scope 的新 MLS transition 就绪后，新 key domain MAY 从 0 开始；旧 key 随 current authorization
失效，即使给出更大 sequence 也必须在推进 high-water 前拒绝。多个不同 raw key 的 authorization
并发存活时不得选“较新”key，Signal fail closed 直到 controller 收敛。

sequence domain 与 AEAD nonce domain 独立：新 signing key 或 sequence 清零不允许在旧
`(group,epoch,sender_domain)` 下重用 nonce；必须完成 accepted MLS transition 并按实际新加密域持久预留。

上述 `sender_actor_id` 使用完整 ActorId 的 JCS 值。持久 namespace 已按完整 AccountId 隔离的
account sender MAY 在该 namespace 内仅存 device/scope 子键，但 MUST 校验 namespace 与待发送
ActorId 一致。同 principal/device 在不同 Station 下的账号具有独立序列域；设备标识碰撞或复用
不得使一个已验证账号压制另一个账号的合法序列。

部署 MAY 收紧 TTL/byte/rate 上限，但能力广告必须给出实际值。

## 3. Admission 与能力广告

Signal 把来源授权、联邦准入与端到端身份分成三层，MUST NOT 因函数复用而把三个角色的
验证责任混成一个“所有 verifier 都查询 current device directory”的要求：

四个 Station 时间边界的 Realm governance 真相源始终是目标 Realm 的唯一 current governance Station。它独占 membership、capability 与 RealmCommit 的可写接纳状态；source local ingress、source 出站重检、destination peer ingress 与 recipient 投递只读已验证的 authority-committed projection，再分别执行本地 device、transport、TTL 与投递新鲜度检查。缓存只在能够证明其覆盖当前已知治理 head 且未越过该阶段要求的 freshness 边界时可复用；排队后的出站与每帧投递必须重新观察撤销/过期。projection 不可验证、已知 stale 或读取超时只可在原 Signal TTL 内有界 pending，随后丢弃；不得猜测通过、维护第二份可写 membership/capability ledger、签发 Commit 或声称第二次 accepted。对应机读阶段见 `contract-registry.json#operation_registry/direct_conversation_signal_admission_mappings`，向量 `ak.vector.direct_conversation.signal_admission.v1` 锁定四个只读 gate 与密文产品动作的分层。

| 角色 | 必须独立验证的材料与边界 |
| --- | --- |
| sender / source Station local ingress | exact AccountId 的 current accepted device authorization、设备签名 key 和 producer signature；Realm/scope、可验证 RealmCommit、current membership、class action、TTL 与外层 MLS/AAD basis。账号 session 不替代设备授权。 |
| destination Station peer ingress | 已认证 source service 对 request body 的 HTTP 签名、source 与完整 sender ActorId 的 routing projection、closed schema、proof transcript 结构/digest、Realm/scope/RealmCommit/current membership/class action/TTL 与外层 MLS/AAD basis。不得把远端设备信任或 producer 验签作为 relay 前置。 |
| recipient 自己 Station 的 authenticated self 投递 | 发出每个 exact envelope 前完成 current signer/device/Agent、撤销、fence、expiry、成员与 action gate，输出绑定收件账号及连接代际的 delivery_authority；不可用则不投递。 |
| recipient 客户端 | 核对本连接 exact delivery_authority、producer signature、exact scope/group/epoch/winning state、active leaf 的完整 ActorId/device/key/authorization transition binding、AAD、AEAD、plaintext schema 与 replay/high-water；全部通过后才能展示或产生业务副作用。 |

两类 Station 的外层治理检查包括 `scope_ref.realm_id == realm_id`、sender actor 在 signed RealmCommit 的 Realm /
scope basis 下具备发送资格且当前仍有 membership、`signal_class=moderation` 的对应 action，以及
已登记加密 scheme/ciphersuite、current epoch/winning state ref 和 §2 TTL；AAD 不上 wire，由 recipient 按 §1 的 header
投影重算，Station 只核对这些 basis 成员。Station 利用已有 accepted
scope、MLS genesis/winning Commit 与 governance projection 核对外层 basis；未知、不匹配或已知
stale 的 basis 不能靠猜测补全。该检查不要求 Station 取得 MLS secret、维护 RFC 9420 public tree
或 leaf-directory tracker；recipient 仍 MUST 用自己的 verified MLS state 独立完成完整绑定。
短 TTL 和允许乱序不授予旧 epoch 或另一 fork 的接收宽限。

对 Direct Conversation，Station 外层只看 closed `SignalEnvelope` 中的 `signal_class`、Realm/scope、sender、Commit、时间与 MLS basis，以及已验证的当前 participant 投影。三项密文产品动作 `ak.call.signal.send`、`ak.receipt.broadcast`、`ak.typing.broadcast` 不映射到 Event submit，也不从 ciphertext 推断为 Station 可见的 kind-specific capability。self send 的外层 participant/class 拒绝统一用 non-enumerating Problem Details `signal_class_denied`，不暴露失败的 participant 输入；peer ingress 对单项失败 opaque drop，recipient delivery 不发 data frame，均无 Event/RealmCommit 写入。recipient 解密并验证后按 plaintext profile 对 exact kind 与 target 执行产品策略；失败不得展示或产生业务副作用，也不能回填一个服务端 reason。`signal_class=setup|moderation|session` 是外层唯一 class discriminator，不能据此推断密文里是 typing、receipt 还是 call。

客户端只消费自己 Account Station 的已认证 Signal stream。Station 在 self ingress / peer ingress 及投递时读取同一个 current governance Station 已签发事实的验证投影，并执行各自时间边界的只读 fresh gate；客户端 MUST NOT 为每个 Signal 下载或重放 membership、capability、RealmCommit checkpoint，也不得以本地尚未取得完整治理历史阻塞解密。客户端仍核对订阅来源、Realm/scope、可信当前签名 key 与本地 MLS 的 exact leaf/group/epoch/state binding，验证 producer signature、AAD/AEAD、TTL、plaintext schema 与 replay。服务器治理结果不替代这些端到端检查。

source 和 recipient 的设备授权使用 **current** 状态，`commit_ref` 只选择 Realm/scope 授权域，
不选择设备授权历史。source 使用自己托管的 exact AccountId 的 accepted device projection。
source 每次准入与出站 fresh 检查 MUST 同时满足原 accepted 设备授权的 `now >= not_before`，
以及非空 `expires_at` 的 `now < expires_at`；缓存 `active` 标记和 Signal TTL 不延长该有效期。
跨账号投递由 recipient 自己的 Station 使用 [`device-lifecycle.md` §8.2/§8.3](../crypto-media/device-lifecycle.md)
的 origin Station 已签 `device_projection_attestation` 完成公共授权验证。cold foreign human sender 由该 Station
按 [`device-lifecycle.md` §8.2.1](../crypto-media/device-lifecycle.md) 经既有 `ak.peer.keys.read.lookup.v1` 取材，
使用既有 `purpose=e2ee_message_encryption`（Signal 是 E2EE 消息场景，不另设 purpose），每批最多 16 个 exact AccountId；不得转发用户 SessionGrant、请求私有 device gate、用 KeyPackage claim 代替
current projection，或透传未验证证据。

每次发出 authenticated self data frame 前，Station MUST 对 exact sender Actor/method、目标 Realm/scope、
exact recipient Account 和当前连接会话执行完整 current gate；排队期间撤销、过期、fence、成员或 action
变化必须被本次 gate 观察。该决定与 frame 内完整 envelope 和 delivery_authority 一起输出，不产生可重用
租约。来源、peer ingress、普通 relay 成功与先前 data frame 均不能代替这项求值；未知或超时不得发帧。
可有界合并尚在途的相同求值，但完成结果不能供未来帧或重连复用；本合同不承诺免除服务器远端查询。

客户端 MUST 只消费自己 Station 的当前认证 subscribe 连接中的 `{kind:"signal", envelope, delivery_authority}`。
delivery_authority.recipient_account_id MUST 等于该连接的完整 AccountId；key.actor/method MUST 与 envelope
sender/proof 逐字相等，并以 exact key 和 authorization_ref 核对本地已验证 MLS leaf transition。
连接关闭、账号/session/安装代际改变后，原连接尚在本地队列的帧 MUST 丢弃；已知撤销优先于已收到的成功
结果。客户端 MUST NOT 为该帧另发 signer self RPC，也不得持久缓存 delivery_authority 作为未来授权。
仍逐帧核对 producer signature、完整 Actor、实际 MLS leaf/group/epoch、AAD/AEAD、TTL、plaintext schema
与 replay；稳定 public-key bytes 缓存不能替代同 key 的不同授权实例。

没有有效可信材料时只可在 Signal TTL 内有界等待；未验证不得展示、更新 high-water 或执行业务，过期即丢弃。

foreign evidence authority 必须在签发前同时验证 authenticated requester Station、requester exact
recipient 与 target 在指定 Realm 的 current effective joined membership，以及
target Actor 的 routing Station 等于自身。ordinary fresh gate 同时检查 exact generation、active
authorization/time/status；Agent fresh gate严格 fold 全部 current authorize dots，并把 controller
account active 与 controller exact Realm membership generation 作为两个独立 AND gate。unknown、
wrong Station、无权、不可见、撤销、冲突、过期或 membership ending 均只产生同形空 evidence，
不得借状态码、failure reason、长度或明显时序差异形成枚举 oracle。

recipient MUST 要求 directory 的 exact device key 与 current authorization Event 同时匹配
active leaf 的 accepted transition binding。已知 revoked、expired、revocation-pending、fenced
或非 current generation 的设备，即使 leaf 尚未 Remove，也 MUST 被 source 与 recipient
拒绝。TTL 不延长授权有效期；同 epoch secret 的其他持有者可以派生公开 sender domain 的 key，
因此 AEAD 成功、leaf 存在、source service 签名均不能代替 producer signature 和设备信任。

local `POST /_arkret/self/signal` 收到 `expires_at` 已过期的 envelope MUST 以 `param_invalid`
拒绝；peer request 内过期 item 按 §4.3 静默丢弃，recipient 也必须丢弃。不能把 local ingress
的明确错误移植为 peer per-item 结果，也不能把 peer 的 opaque 成功当作设备已认证。

不存在 plaintext branch。任何 MLS-backed scope 的 plaintext signal / 未加密 ephemeral 输入
MUST 以 `signal_plaintext_forbidden` fail closed。

conformance（`ak.vector.signal.device_authorization_domain.v1`）至少覆盖：

1. 设备在 current directory 为 active、授权晚于 `commit_ref`：source 与 recipient self 投递的设备授权检查通过，仍须独立通过 MLS 与 scope 检查；
2. 设备在 `commit_ref` 时曾 active、当前已 revoked / fenced：source/recipient 拒绝，包括 leaf 尚未 Remove；
3. fragment 看似为 device id，但 `verification_method` 的 bare DID 经 adapter 投影不等于
   `sender_actor_id` 的 signing principal 分量，或 fragment 不等于 `sender_device_id`，或
   current directory 信任锚属于同 principal 的另一 Station：source/recipient 拒绝；
4. current directory key 或 Tier-2 / service-attested 信任锚缺失：source/recipient fail closed；destination 没有远端目录但 transport checks 均通过时仍可 relay；
5. 设备 current active 但 sender 在 Realm `commit_ref` 下无 scope 发送资格或缺
   `signal_class` action：拒绝；
6. 恶意 source 以有效 peer 签名提交结构正确但 producer signature 伪造的 envelope：destination
   可转交，recipient MUST 验签拒绝，即使密文能解开；proof digest/transcript 或 sender routing 不匹配则在 destination 丢弃；
7. source 入队后发生撤销、退群、action 收紧或过期：出站 fresh admission 拒绝，不发送旧 item；
8. Agent current authority、active unique leaf 与 method/key/authorization binding 全部匹配时可用 Agent sender 分支；ordinary 省略 device、Agent 携 device/controller device、paused/deactivated、key revoke/supersede/expire/conflict、controller membership generation ended、旧 leaf 或 pairwise 冒入均拒绝。
9. cold foreign ordinary 与 Agent sender 均从空 cache 经真实 self 投递 gate→peer query 成功；预注入同一对象、
   重放另一 challenge/Signal/recipient/verifier 的 response、同 core 不同 Station、旧 generation、
   expired attestation、已知 revoke 或 membership ending 均拒绝，且未认证 plaintext sequence 不推进 high-water。

Service Describe 的服务级 operation 广告仅表示 transport surface 存在，不表示每个 scope
可用。实现只有在同时提供 scope-aware profile/limit descriptor，并能在目标 scope 验证
encrypted signal 时，才能为该 scope 广告 Signal；否则必须撤下 scope capability。

## 4. Rail 与 peer relay

### 4.1 Local send / subscribe

`send` 接受一个 `SignalEnvelope`。canonical HTTP binding 的 `subscribe` 使用独立
`GET /_arkret/self/signal/subscribe` NDJSON response，并输出
[`SignalStreamFrame`](../../artifacts/schemas/signal-stream-frame.schema.json)：data frame
固定为 `{kind:"signal", envelope, delivery_authority}`，control frame 只允许 `heartbeat`、`drain` 与
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
operation: ak.peer.signal.command.relay.v1
POST /_arkret/peer/signal
request:  ak.schema.signal_relay.v1
response: empty
```

request 是闭合对象：

```json fragment
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
| HTTP Message Signature 签名寿命 | `ak.http_signature.freshness.v1`（与其余场景同一份） |

这些上限合取生效；128 个接近单 envelope 上限的 item 不承诺能装入一个 request。source
加入下一项将使 count 或 canonical bytes 任一超限时 MUST 在 signal 边界拆批。destination
对 count/schema 超限拒绝整个 request，不得 partial accept；byte overflow 固定
`payload_too_large`。

本 operation 的签名场景是 [`service-http-binding.md` §8](./service-http-binding.md) 的
`ak.http_signature.scenario.signal_relay.v1`。适用的必需覆盖项：

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.signal_relay.v1 -->
- `@method`、`@target-uri`、`@authority`
- `arkret-operation`
- `content-digest`（relay request 总是带 body）
- `source-service-id`、`destination-service-id`
- `source-trust-domain`、`destination-trust-domain`
- `destination-service-endpoint-digest`（条件项：经 shared ingress 抵达 destination 时必需）
<!-- END ak-http-signature-covered-set -->

本 operation 的时效窗口是共享的 `ak.http_signature.freshness.v1`，与其余签名场景同一份；
数值只在合同里编辑，本页不复制。relay 曾有一条更短的寿命上限，因为没有记录过依据、
也不承担业务新鲜度职责而取消：实时面的旧包边界由 §2 的 `sent_at` / `expires_at`（差值硬上限）、
§3 两道 ingress 的 Realm／scope／RealmCommit／current membership／class action／TTL 判据，
以及 recipient 自己的 replay 与 high-water 检查共同执行，transport 签名寿命替代不了它们，
本次取消也不放宽其中任何一条。
clock skew、endpoint、canonical body 与最小披露规则与 §8.3 相同。

### 4.3 Source 与 destination admission

source 对每个 envelope MUST 先完成与 local `send` 相同的 §3 source admission，包括 exact
AccountId 的 current device authorization 与 producer signature，再按当前 accepted joined-member ActorId 的封闭路由投影
计算 destination service 集。source 只向至少托管一个 scope 内 active member
的 service 发一份 request；request 不携带 member、principal、device 或精确产品 target 列表。
一个 Realm 的多个 destination 由 source 分别直发，不能串成 relay chain。若 envelope 经短期排队，
source MUST 在实际出站前重新验证 current device authorization、producer proof、current
membership/scope/class action、TTL 与 MLS basis，并重算 destination 集；不得只复用 local ingress
时的成功结果，或把已经失效的 item 交给 destination/recipient 才过滤。

destination 在任何 local fanout 前 MUST：

1. 验证 peer HTTP Message Signature、source/destination service DID、trust domain、endpoint、
   canonical body digest，以及 [`service-http-binding.md` §8.3](./service-http-binding.md) 中
   `ak.http_signature.freshness.v1` 的时效窗口；
2. 要求所有 `signals[].realm_id == request.realm_id` 且
   `signals[].scope_ref.realm_id == request.realm_id`；
3. 验证 `Source-Service-ID` 等于每个 sender ActorId 的 routing-service projection；不成立的 item
   进入下述静默丢弃路径。这同时阻止
   destination 把收到的 signal 再转发第三 peer；
4. 验证完整 `SignalEnvelope` closed schema、proof method 的 §1 identity projection、
   重算移除 proof 的 envelope digest、以外层 `sent_at` 注入 `created_at` 重建的 closed detached-JWS
   transcript 与 header 结构，再验证 `commit_ref`、sender 在 signed scope/basis 的资格与
   current membership、三值 `signal_class` action gate、TTL、外层 accepted epoch/state/ciphersuite basis。
   这些是结构、完整性和 transport admission 检查，**不是** producer signature 的密码学验证。
   destination MUST NOT 查询远端 current device directory、重放远端 PCR 或维护 MLS public-tree /
   leaf tracker 来决定 relay；也不得借用本地同 principal/device、另一 Station 的账号目录验签；
5. 只按外层 `scope_ref` 计算本地 eligible devices，并执行 membership、Circle visibility、
   blocklist 与本地 rate/backpressure policy；
6. 把原 envelope 原样交给 recipient self 投递 gate；该 gate 与 peer ingress 是独立阶段，未通过不得输出 live data frame。精确 payload type、Strand/Message/Call/receipt
   target 与 sequence 只由 recipient 解密后校验。

source 与 destination MUST NOT 改写 `sent_at` / `expires_at`、ciphertext、`nonce` 等 AAD 输入、routing header
或 producer proof，MUST NOT 重签 producer envelope，MUST NOT 解密后重加密。HTTP JSON 的
空白/成员顺序无需保留，但重新 canonicalize 后的完整 envelope digest identity MUST 不变。

schema-valid request 内的单个 signal 因 Realm/scope/sender 未知、proof transcript/digest 或 current
joined-member ActorId routing projection 不成立、过期、重复、sender 已离开、`signal_class` action gate
不通过、scope 不可见、本地无 eligible recipient 或本地 rail/policy 不接管而失败时，
destination 静默丢弃并 MAY 写 audit-only reason；不得向 source 返回 per-item 结果。只有外层
peer HTTP Message Signature / trust-domain / destination-endpoint 认证失败、跨 Realm batch 或
request schema/count/byte 超限才是 request-level reject，并复用 federation 的统一最小披露
错误/timing bucket。closed schema 中 proof 缺字段、字段类型/shape 非法属于 request schema 失败；
结构正确但 proof digest、transcript 或 source/sender binding 不匹配属于 item failure。
结构正确的无效 producer signature 不属于 destination 的判定项，MUST 留给独立 recipient
认证拒绝；有效 source HTTP 签名不把该 producer signature 变为可信。

### 4.4 Opaque outcome、重复与不确定结果

成功使用 HTTP 204 empty response；operation registry 必须登记 `success_shape_kind=empty_response`，不得
返回 `{}` 或 `accepted=true`。2xx 只表示已认证、结构合法的 peer request 被接管处理，不表示
Realm/scope/sender/recipient/binding 存在，也不表示任何设备收到 signal。响应 MUST NOT 含 accepted/rejected count、
per-item outcome、recipient count、supported kind、envelope digest 或远端拓扑。无 local
eligible recipient 与存在 recipient 必须得到相同 HTTP status 与空响应体。

operation registry 固定：

```text
idempotency_mechanism = none
retry_safe = false
uncertain_outcome.strategy = drop_unconfirmed
```

request MUST NOT 携带 `Idempotency-Key`。response 丢失、timeout 或连接中断后 source MUST NOT
自动重放 request；Signal 的恢复依靠下一个自足 frame或产品级 timeout/renegotiation。destination
可用完整 envelope digest 做有界短期 replay suppression；recipient 解密后仍按
verified sender endpoint domain 与 `payload_sequence` 去重。任何 dedupe 命中都不得绕过 peer
签名窗口与该角色的 §3 admission；source/recipient 不得借 dedupe 跳过 producer 验签，
destination 不得借 dedupe 跳过 peer authentication 和 proof transcript/digest 检查。

### 4.5 顺序、资源隔离与能力发现

peer relay 与 local/live rail 都允许丢失、重复和乱序，不保证 array、batch、source、destination
或 rail 之间的顺序。consumer MUST 在任意到达顺序下保持正确；依赖跨 signal 顺序才能正确的
payload 不得使用本 rail。

source/destination MUST 为 Signal relay 使用与 durable federation control/data 分离的有界
concurrency、pending-count、pending-bytes 与 per-peer/Realm byte-rate budget；typing/candidate
burst 不得饿死 Event、RealmCommit、membership、MLS 或 dependency fetch。部署可在 128/1 MiB 固定
interop ceiling 内进一步用 rate limit/backpressure 拒绝当前负载，但不得把私有限值广告成新的
wire profile。

能力发现只使用：

- `supported_profiles` 包含 `ak.profile.signal_peer_relay.v1`；
- `supported_operation_bundles` 包含 `ak.peer.signal.command.relay.v1` 的精确 carrier/schema 行；
- operation registry 的固定 count/body/retry contract。

不得广告 `supported_signal_kinds` 或 per-member relay support；精确 payload kind 位于 ciphertext。
不支持 relay 时 local Signal 与 durable federation 仍可用，presence/typing 静默降级，call 可在
service-level profile preflight 后报告 peer relay unavailable，但不得暴露具体 remote member。

## 5. 与 to-device 的硬边界

设备专属控制消息使用 `DeviceMessageEnvelope` 和可靠队列，不得进入 broadcast Signal，也不得使用 signal TTL/单跳 fanout 语义。新设备的密钥恢复与 MLS 加入分别遵循备份和 `MlsWelcomeDelivery` 合同；`ak.secret.request` / `ak.secret.send` 在 v1 不可接纳。

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
内；`ak.schema.signal_message_stream.v1` identity 固定 discussion family，plaintext frame 不携
`track_name`。sender MUST 同时持有 `ak.message.stream.send` 和目标
Message create 所需授权；因为精确 kind 与 target 按 §1 强制加密，service 只能执行外层实时
发送资格与 scope gate，recipient MUST 在展示前按 `commit_ref` basis 重验这两个产品级 action。
授权、scope、schema 或 AEAD 任一项不可验证时 MUST fail closed 且不得显示正文。

### 7.2 帧与资源常数

每个 decrypted payload 都携带通用 `payload_sequence`，供 §2 的完整 Actor/verified endpoint/scope replay
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
| 单 verified sender endpoint 并发发送 stream | 8 |
| 单 stream 生命周期 | 10 min |
| consumer stalled 标记 | 30 s |
| 单 verified sender endpoint 同时展示 stream | 8 |

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

receiver 对同一 `(sender_actor_id, verified sender endpoint domain, message_id)`：

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
3. final Event 不含 `executed_by`；preview 的 `sender_actor_id == Event.actor_id`。ordinary preview
   的 `sender_device_id` 等于 final proof 的已验证设备；Agent preview 与 final 的合法 signer evidence
   必须得到同一个 raw-key digest。same-key re-authorization 可改变 authorize Event ref，但两侧仍须
   分别通过 current/historical authority；正式换 key 不得继承旧 preview/attempt，必须使用新
   Event/Message identity；
4. preview/final 的 Realm、由 `scope_ref` 确定的 security scope、Strand 与 discussion track
   全部相等。

final 正文可以与最后 preview 不同；receiver 直接以 final 为准，差异不是协议错误。preview
不增加 hash commitment，也不承诺一定出现 final。收到合格 final 后，receiver MUST 终止该
message 的全部 preview attempts。委托执行的 final 因 Signal 外层没有同时表达 principal of
record 与 executor provenance，MUST NOT 与本 profile 的 direct preview 绑定。
