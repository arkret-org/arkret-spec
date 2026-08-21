---
title: Encryption and Auditability
status: candidate
normative: true
stability: v1
updated: 2026-07-29
sidebar:
  label: Encryption & Audit
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

去中心化协作协议面临着复杂的隐私与合规矛盾：一方面，商业数据和私密频道必须提供不可被 Principal Server sync surface 或未授权受托服务窃听的端到端加密 (E2EE)；另一方面，在特定组织边界内，数据流又需要受到法律或合规层面的安全审查。

本规范定义了 Arkret 官方推荐的加密标准，旨在实现：
- 基于 **MLS (RFC 9420)** 的高效大规模协作加密
- 强前向安全 (Forward Secrecy) 与后向安全 (Post-Compromise Security)——此为默认 `mls_rfc9420` 内容 scheme 的属性；启用 §2.10 `mls_exporter_aead_v1` 且保留 per-epoch `history_secret` 的 Realm，其 FS / PCS 在被保留 epoch 上按 §2.10.5 退化为限定形态（per-epoch FS、PCS 仅对未被保留的 epoch 成立）
- **可审查加密 (Auditable E2EE)**，在 TEE / HSM / 等价受控执行 profile 下把合规解密绑定到可验证审计记录；在 software-only profile 下提供透明审计流程，但不声称具备同等密码学强制力。

## 2. 基础加密架构：MLS 与 Arkret 的融合

Arkret 采用 [RFC 9420 - Message Layer Security (MLS)](https://datatracker.ietf.org/doc/html/rfc9420) 作为官方的群组加密标准。
不推荐使用传统的 Double Ratchet（双棘轮），因为在包含数十到数百名成员的 discussion track 或大型协作 Realm 中，双棘轮会导致巨大的性能开销与并发处理难题。

### 2.1 KeyPackage 与服务发现
在参与 MLS 加密前，用户必须公布自己的 `KeyPackage`。
- **发布位置**：Actor 通过 signed Event 发布自己的 `KeyPackage`，或者在其 DID Document 的 `service` 中指定独立的 `MLS Delivery Service` 节点入口。
- **生命周期验证**：其他客户端在拉取 `KeyPackage` 时，MUST 独立验证 claim response 携带的
  portable authorization evidence。DID method history 只验证 identity root；普通设备签名 key
  只来自 registration-anchor PCR genesis、完整 control history、accepted Seal 与 current device projection，
  **MUST NOT** 回退到 DID Document verification method。Native Agent 则验证 current-admission
  `AgentSignerEvidence`，两分支不得互相 fallback，也不得以 Principal Server 裸投影替代。

### 2.2 握手与组成员管理 (Welcome, Commit)
MLS 维护了一颗成员密钥树 (Ratchet Tree)。在 Arkret 中，群组的密钥状态变动不依赖于独立的中心化分发服务器，而是映射到原生的 `Realm` 与 Event 模型中：

```mermaid
sequenceDiagram
    participant Alice
    participant Principal Server sync surface (Realm Events)
    participant BobClient as Bob Client

    Alice->>Principal Server sync surface: POST /_arkret/self/keys/query
    Principal Server sync surface-->>Alice: Bob's signed KeyPackage / device keys

    note over Alice: Computes GroupContext & Tree

    Alice->>Principal Server sync surface: Submit `ak.mls.commit` (Group state update)
    Principal Server sync surface-->>Alice: Commit accepted / duplicate
    Alice->>Principal Server sync surface: Submit exact bound `ak.mls.welcome` (Encrypted for Bob)

    Principal Server sync surface->>BobClient: Push Notification & Sync

    BobClient->>Principal Server sync surface: Fetch `ak.mls.welcome`
    note over BobClient: Decrypts Welcome using InitKey
    note over BobClient: Derives Group Epoch Secret
```

- **`ak.mls.commit`**：当拥有权限的 Admin 邀请新成员加入或移除成员时，客户端计算 MLS 的 `Commit` 消息。该 `Commit` 必须作为 `ak.mls.commit` 类型的 Event 提交至 Realm Event history。它作为不可篡改的账本，确保全网节点对群组密钥状态树的演进达成一致。
- **`Welcome` 分发**：新成员会收到由 Admin 构造的 `Welcome` 消息。Welcome MUST 通过 durable `ak.mls.welcome` Event、durable encrypted pointer 或等价可 backfill 记录交付，直到被消费、撤销或过期。Principal Server sync surface 的 Signal Extension 只能作为通知和加速通道，不得是唯一交付路径；否则离线设备、跨域 backfill 和恢复流程无法验证加入历史。
- **投递不得降维**：Delivery / Principal Server sync surface 把 accepted `ak.mls.welcome` 投影为 to-device message 时，MUST 原样保留其规范 payload，至少包括 `mls_group_id`、`epoch`、`recipient_principal_id`、`recipient_device_id`、`claim_ref`、`claim_envelope`、`governance_binding`、`commit_ref` 与 ciphertext / durable ciphertext pointer。服务端不得只转发 MLS ciphertext 或重新构造一个缺少 claim / governance 字段的缩减信封；接收端必须能在解密和入组前独立复算 Welcome digest、验证邀请方签名，并将同一个 `governance_binding` 与 MLS GroupContext extension 及 Seal 证明逐字段比较。

**发送方 admission saga（normative）**：一次 Add admission 的 Commit、面向全部目标设备的 Welcome、以及 Commit 后本地 MLS group state 是同一不可拆分的恢复单元。发送客户端在完成必要的 KeyPackage claim、构造出该 admission 后，MUST 在首次 Commit / Welcome 网络写入前，把以下材料原子写入 crash-recoverable outbound state：精确签名后的 `ak.mls.commit` Event、每条精确签名后的 `ak.mls.welcome` Event，以及仅在投递完成后安装的 post-Commit group state。网络时序 MUST 是 Commit accepted / duplicate 后才投递与其 `commit_ref` 绑定的 Welcome；不得先投递 Welcome，也不得在 Commit 未被接受时安装 post-Commit group state。

Commit 一旦 accepted / duplicate，发送方 MUST 持续重试**同一 event id、同一签名 bytes、同一 ciphertext** 的每条 Welcome，直到该 Welcome accepted / duplicate，或新的 accepted membership/repair Commit 已明确移除该接收方并使旧 Welcome 失效。单纯达到本地 TTL / policy expiry 不足以把已接受 Commit 对应的 Welcome 标为完成；实现必须同时进入明确的 repair/removal 流程。进程退出、页面关闭、网络错误和普通 deterministic service error 均不得让实现丢弃该 durable item、重新 claim KeyPackage、用新随机数重签 Welcome，或回退到旧 epoch 继续发送。无法自动恢复的响应 MUST 进入可诊断的 quarantined / repair-required 状态并保留原材料；修复路径 MAY 产生新的授权 Commit，但不得静默把已接受 Commit 对应的 Welcome 标为完成。只有全部 Welcome 完成 durable 提交后，发送方才能安装该 admission 的 staged post-Commit group state；若旧 Welcome 已被 accepted repair 取代，则 MUST 丢弃旧 staged state 并安装经验证的 repair 后 current state。两条路径都必须在收敛后才能解除本地 admission transition；这不改变接收方对 Welcome、governance binding 和 Seal proof 的独立校验义务。

**Welcome 大小侧信道（acknowledged side channel）**：MLS Welcome / GroupInfo 的 ciphertext 长度会与 leaf 数量、ratchet tree 形态、path secret 数量和近期 churn 有相关性。Arkret v1 不声称第三方观察者无法从 Welcome 大小推断粗粒度成员变化。高隐私 Realm SHOULD 声明 `ak.profile.traffic_metadata_hardened.v1`；声明后 Welcome / GroupInfo blob MUST 使用该 profile 声明的 padding bucket（默认 4KiB / 16KiB / 64KiB）并批量投递 welcome pointer。实现不得在 minimal-metadata 或 high-confidentiality 文案中承诺“成员变化不可由消息大小观察”，除非已声明并通过该 profile 的 padding 策略测试。

#### 2.2.1 MLS Group Admin 推导

MLS group admin 不是“第一个发 Welcome 的客户端”或“track 的第一个成员”。Arkret v1 按当前 accepted auth state 确定管理集合：

- Realm-scoped MLS group 的默认 admin set 来自 `ak.realm.create.payload.object.initial_creators` / `created_by`，以及当前有效的 `ak.realm.admin`、`ak.mls.commit`、`ak.mls.welcome` 或 Realm policy 声明的等价 E2EE admin capability。
- Realm 内的 [Circle](../models/circle.md)（`Strand.scope_circle_id` 指向的子事件边界）只有在 `encryption_profile=mls_rfc9420` 时才拥有 Circle MLS group；其 MLS group admin set 由该 Circle 的 `ak.circle.create` / `ak.circle.member.state` / `ak.mls.commit` / `ak.mls.welcome` 等事件按 Circle 自身的 capability 与 membership 体系收敛，与 Realm-default MLS group admin set 独立；Circle key MUST NOT 从 Realm-default key 派生。
- Admin capability 可以通过普通 capability grant / revoke Control Move 转移或收回；转移生效点由 Seal finality、Lattice value 和 revoke freshness 决定，不由 MLS leaf index、设备在线状态或本地 UI 角色决定。

发送 `ak.mls.proposal`、`ak.mls.commit` 或 `ak.mls.welcome` 的 actor 必须在其事件自己的 causal auth state 下属于上述 admin set，或满足该 event kind 允许的普通成员 update / self-update 规则。

### 2.3 载荷加密与 closed pre-encryption header

是否存在 MLS group 只由 effective scope 的 `encryption_profile` 决定；`content_scheme` 在该 group Genesis
中显式固定为 `mls_rfc9420|mls_exporter_aead_v1`。每个 MLS-backed Realm/Circle 使用独立 group。未选择 MLS 的
scope 不得产生 MLS envelope 或占位 group。

两种 scheme 都使用
[`encrypted-envelope.schema.json`](../../artifacts/schemas/encrypted-envelope.schema.json) 的最小 closed wire：

```text
EncryptedEnvelope = {version, content_type, encryption_context, ciphertext}
encryption_context = {epoch, group_state_ref, routing_context?}           // standard
                   | {epoch, group_state_ref, counter, routing_context?}  // exporter
```

双方在加密/解密时从已冻结 outer Event、exact winning group state 与该最小 context 唯一重构 AAD 对象：

```text
pre_encryption_header = {
  purpose: "arkret_event_content",
  envelope_version: EncryptedEnvelope.version,
  content_type: EncryptedEnvelope.content_type,
  scheme: content_scheme(exact group_state_ref),
  effective_scope: effective_scope_from_outer_signed_event,
  event_kind: outer_signed_event.kind,
  mls_group_id: derive(effective_scope),
  epoch: encryption_context.epoch,
  group_state_ref: encryption_context.group_state_ref,
  sender_domain: derive_from_frozen_producer_verification_method_and_verified_leaf,
  counter: encryption_context.counter, // exporter only
  routing_context: derived_routing_context
}
derived_routing_context = {kind:"none"}
                        | {kind:"reaction", target_ref, routing_window, routing_tag}
```

Wire 不复制 purpose、scheme、effective scope、Event kind 或 group id。Counter absence 是 standard 的结构分支，required
counter 是 exporter 的结构分支；receiver MUST 与 exact `group_state_ref` 冻结的 content scheme 交叉校验。重构 header 的
`effective_scope/event_kind/sender_domain/group/epoch/group_state_ref` MUST 与外层已签 Event 和 exact
historical active leaf 逐字节相符；unknown kind、额外字段、inner/outer routing 不一致或陈旧 current history frontier
均拒绝。当前 EventId、由当前 ciphertext/payload 派生的任何 digest、算法名、purpose/profile 的顶层重复副本均不得进入
AAD 或 envelope。构造顺序固定为“冻结 header → seal ciphertext → 组装 Event → 计算 EventId → 外层 proof”。

只有 registry 标记为 reaction 的外层 Event kind 才 MUST 在 wire 携带
`routing_context={target_ref,routing_tag}`；其它 kind MUST 省略。`kind="reaction"` 与
`routing_window=floor(unix_ms(event.created_at)/3_600_000)` 从外层已签 Event 派生并只进入
`derived_routing_context`，不得在 wire 重复。

Exporter scheme 的内容派生、counter 和 replay 见 §2.10。Standard MLS 把同一 header canonical bytes 作为 MLS
authenticated data，并额外执行 history-access 文档中的 endpoint-admission floor。外置 content-addressed blob 可保留
检索 digest；inline encrypted Event 不得携重复 `aad_digest/payload_digest/key_ref.algorithm/aead_profile`。

解密前 MUST 验 Event schema/proof、exact historical group state、unique active leaf、current history frontier 与
header 外层绑定；解密后 MUST 验 plaintext schema 与 inner/outer routing。错误不得进入 verified timeline。Redaction、
retention 或 erasure 可停止投影，但不能使已交付的 secret 失效。
### 2.4 Sync 与 MLS Epoch

Client Sync 中的事件顺序不保证密钥材料已经同步完成。加密事件和 MLS epoch state MUST 作为相关但可独立到达的 stream 处理：

- encrypted event 可以先进入 raw event cache 和 timeline position。
- `ak.mls.*` state event / MLS Commit 决定客户端是否拥有对应 epoch 的解密状态。
- 客户端缺少 epoch 时 MUST 标记 `decryption_pending`，不得静默丢弃或重排事件。
- standard MLS 只允许 endpoint 从自身 initial Add/Welcome admission 起顺序应用 winning Commit，不得为历史 backfill 获取
  foreign active MLS state。Exporter scope 的 late receiver 缺历史正文时，按每个 epoch 的 T0 `history_access` ceiling 与
  chunk 首次耐久入队时的 T1 current gate 使用 private history-key manifest/chunk；不得把 snapshot、leaf signer、ratchet、
  proposal 或 sender counter 当作恢复材料。
- 被移除成员不得获取移除后 epoch 的 group secret；客户端必须 fail closed。
- `history_access` 只授予历史范围资格，不自动授予旧 epoch key。Exporter 交付必须执行
  [`../governance/history-visibility.md`](../governance/history-visibility.md) §4 的 receipt-bound direct Seal traversal，重放 winning transition、current 单向收紧 history_access 与 current incarnation/join floor，并执行首次入队 T1 gate；v1 不存在
  第二套 key-sharing policy 或公开 share/withheld Event。

服务端和 Principal Server sync surface 不需要解密正文，但必须保留明文 routing metadata、epoch reference、hash 和 causal refs，以便客户端后续补齐密钥后重试解密。

#### 2.4.1 Membership 与 Epoch 不一致窗口

Membership state 与 MLS epoch 推进是异步事件，但可见性规则必须确定：

  **明文发送豁免（normative）**：send-pause 只约束需要 MLS-backed 密文的发送。当某 scope 的 effective `content_encryption_floor=allow_plaintext` 且该消息以明文发送时，不受 MLS epoch / `security_frontier_digest` gating——明文消息的 ban / revoke 由 membership cell 即时生效，不依赖 epoch 推进。这使 “`encryption_profile=mls_rfc9420` + `allow_plaintext`” 的可升级默认形态在明文期间无需为每次成员变更推进 MLS epoch；一旦 effective floor 抬到 `e2ee_required`（或该消息以密文发送），完整 §2.5 governance-binding send-pause 立即恢复，首条密文发送 MUST 等待覆盖当前 membership frontier 的 epoch。`encryption_profile=none` 的 scope 不拥有 MLS group，本规则不适用。

  **`mls_send_pause="advisory"` 降级规则**：把上述 MUST 暂停降级为 SHOULD 的能力**仅在显式 degraded profile** `ak.profile.e2ee_relaxed.v1` 下允许声明，不得在默认 `ak.profile.mls_governance_binding.full.v1` profile 或任何声称 “完整 MLS Governance Binding” 的部署中使用。该字段在符合资格的部署中也 MUST：

  - 出现在 `ak.realm.policy_bundle` 的明文 audit log 中(声明本身被记录，便于审计)
  - 部署 profile 在 conformance 声明中**显式列出** `ak.profile.e2ee_relaxed.v1`，否则降级声明 MUST 被 reducer 拒绝（`unsupported_profile` reason）
  - 客户端 UI 在该 Realm 中 MUST 展示明确的"该 Realm 使用降级 E2EE,踢/ban 非密码学即时生效"banner-level 警示(详见 §2.4.2 / `ak.profile.e2ee_relaxed.v1` 规范)
  - 接收端在解密 advisory 模式下旧 epoch 消息时 MUST 检查 receive_at vs membership_change_at 时间窗，超过部署声明 `relaxed_window_max_ms` 时拒绝解密结果进入 verified timeline
  - **`relaxed_window_max_ms` 默认值 = 30,000 ms（30 秒），硬上限 = 300,000 ms（5 分钟）**：两者语义不同，不得混淆。**默认值**是部署未在 `ak.realm.policy_bundle` 显式声明 `relaxed_window_max_ms` 时 reducer / 接收端 MUST 采用的值，固定为 30,000 ms（与 §2.4.2 profile 行为表"被踢者继续解密窗口默认 30s"及 `max_mls_commit_delay_ms` 默认 30,000 ms 对齐，使"踢出后被踢者继续可读窗口"与"正常 commit roundtrip 上限"在默认配置下同量级）。**硬上限**是部署即使显式声明也不得超过的天花板 300,000 ms：部署不得通过 `ak.realm.policy_bundle` 把 `relaxed_window_max_ms` 写为大于硬上限的值；reducer MUST 用 `relaxed_window_exceeds_ceiling` 拒绝。接收端 MUST 独立 enforce 硬上限——不得静默 clamp 到 300000，否则部署声明的窗口与 receiver 接受的窗口会跨实现分裂。部署 MAY 在 `(0, 300000]` 区间内显式覆盖默认 30000；缺省即 30000。Negative vector `ak.vector.e2ee_relaxed.window_exceeds_ceiling.v1` 同时覆盖 policy write 超限与 receiver 接受超限 decrypt 两条路径。
  - **合规 profile 互斥**：声明 `ak.profile.attested_audit.e2ee.v1` / `ak.profile.disclosed_audit.e2ee.v1` 或存在 active Audit Applet Binding 的部署 MUST NOT 同时启用 `ak.profile.e2ee_relaxed.v1`；reducer MUST 用 `e2ee_relaxed_disallowed_in_compliance_profile` 拒绝。合规 / 监管 profile 的核心承诺是"踢出即时密码学生效"，relaxed 窗口与之矛盾。
  - **Federation guard**：`ak.profile.e2ee_relaxed.v1` MUST NOT 与 `federation_policy="open"` 或 `"quarantine"` 同时启用；reducer MUST 用 `e2ee_relaxed_federation_policy_unsupported` 拒绝。`federation_policy="restricted"` 只允许在 Realm policy 同时声明 `relaxed_fanout_deadline_ms <= relaxed_window_max_ms`、`max_federation_delivery_delay_ms <= relaxed_window_max_ms` 且 federation peers 在 `ak.server.read.describe.limits` 中公开不超过该 deadline 的 fanout SLA 时启用；否则 MUST fail closed。`federation_policy="closed"` 不需要额外 federation guard。describe SLA 校验仅是准入门槛（声明时校验 peer 公开的 fanout deadline 是否满足约束），实际 enforcement 仍由接收端 `relaxed_window_max_ms` 时间窗兜底（运行时校验 receive_at vs membership_change_at，超窗即拒绝 decrypt 进入 verified timeline）；二者缺一不可，不得理解为"声明合规即放行"。

  **降级声明义务（normative）**：`ak.profile.e2ee_relaxed.v1` 不是本地优化开关，而是可审计的协议降级声明。有效声明必须同时满足：Realm `schema_refs` 明文记录 `ak.profile.e2ee_relaxed.v1`（经 `ak.realm.create` 或 `ak.realm.schema` 写入），且 `ak.realm.policy_bundle` 明文记录 `mls_send_pause="advisory"`——profile id 与 `mls_send_pause` 分属两个承载，bundle 闭合 payload 内没有 profile 字段；服务端 `ServiceDescribe.supported_profiles` / `supported_features` 声明 `ak.profile.e2ee_relaxed.v1` / `ak.feature.e2ee_relaxed.v1`；该 Realm 后续每个 MLS `governance_binding.binding_profile` 写为 `ak.profile.e2ee_relaxed.v1` 并携带匹配的 `reducer_profile`；sync metadata、snapshot、backup/export 与 interop mapping receipt 必须保留 `e2ee_relaxed=true` 和 `relaxed_window_max_ms`。任一条件缺失、互相矛盾、或仅通过部署私有配置 / UI 标签 / 省略 GroupContext extension 表达降级，接收方 MUST 按未声明降级 fail closed：拒绝 Realm 写入、quarantine 相关 MLS artifact，或拒绝 old-epoch decrypt 进入 verified timeline。

  **联邦互操作下界（normative）**：跨 deployment 的 MLS-backed Realm 以 `ak.profile.mls_governance_binding.full.v1` 为 E2EE 互操作下界。`ak.profile.e2ee_relaxed.v1` 是低于该下界的显式降级，只能在 `federation_policy="closed"` 或满足上方 restricted federation guard 的 `restricted` Realm 中出现；open / quarantine federation MUST reject。联邦 peer 未在 describe 中声明所需 profile/feature、未公开满足窗口的 fanout SLA、或 MLS commit / DataEvent 的 `binding_profile`、`reducer_profile`、`security_frontier_digest` 无法验证时，接收方 MUST reject 或 quarantine，不得把该 peer 的 push 用于推进本地 Realm frontier。

  声明 advisory 但未声明 `ak.profile.e2ee_relaxed.v1` profile 的 Realm create / policy update event MUST 被 reducer 拒绝。详见 §2.4.2 与 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json)。
- Realm / reducer profile MUST 声明 `max_mls_commit_delay_ms`，**默认 30,000 ms**；profile MAY 覆盖（交互式 profile SHOULD be no greater than 30,000 ms，高延迟 / 批量 profile MAY 声明更大值）。客户端在 commit 滞后超过该 effective 值后 MUST 将该 scope 降级为 read-only / send blocked，服务端 SHOULD 返回 `epoch_update_required` 或 `temporarily_unavailable`。
- 网络分区期间可以继续 backfill 旧 epoch 历史，但不得把旧 epoch 下的新消息展示为已满足最新 membership policy 的消息。

该窗口规则不改变 MLS Proposal / Commit 两阶段语义；它只定义 Arkret 在 state 已变化但 epoch 尚未收敛时的 UI、发送和解密处理。

### 2.4.2 `ak.profile.e2ee_relaxed.v1`(降级 profile)

**目的**:某些低延迟交互场景(实时音视频会议、协同光标 / 多人编辑、游戏内聊天等)不能容忍 MLS commit 完成才允许发新消息的等待开销(典型延迟 200ms-数秒)。`ak.profile.e2ee_relaxed.v1` 是为这些场景保留的**显式降级 profile**:允许 `mls_send_pause="advisory"`,代价是放弃"踢人/ban 后被踢者立即不能解密新消息"的密码学硬承诺。

**适用判断**:
- Allowed: 实时交互延迟要求 < 1s 且业务可接受"踢出后窗口内被踢者仍可读 1-2 条消息"的场景。
- Forbidden: 普通群聊 / 协作文档 / 项目讨论(踢人语义需要密码学强保证)不适用，继续用默认 `ak.profile.mls_governance_binding.full.v1`。
- Forbidden: 合规 / 法律 / 监管要求"立即生效"撤销时强制不适用，部署 MUST 拒绝。

**Profile 行为差异**:

| 维度 | 默认 (`mls_governance_binding.full.v1`) | 降级 (`e2ee_relaxed.v1`) |
| --- | --- | --- |
| `mls_send_pause` 默认 | MUST 暂停直到 security frontier 被当前 Commit 覆盖 | 允许声明 `"advisory"`,降为 SHOULD |
| `security_frontier_digest` 匹配 | reducer/客户端 MUST enforce | 仍然写入并验证，但 send-side 可按声明窗口延迟阻塞 |
| 被踢者继续解密窗口 | ≤ MLS commit roundtrip(密码学保证) | ≤ `relaxed_window_max_ms`(默认 30s,部署声明) |
| 接收端 verified timeline 检查 | epoch 不匹配 → 拒绝 | epoch 不匹配且超出 `relaxed_window_max_ms` → 拒绝 |
| UI 警示 | 无 | **MUST 显示 banner-level 警示**，并明确披露：该 Realm 使用降级 E2EE；踢出 / ban 不具备密码学即时生效保证；旧成员可能在声明窗口内继续解密最近消息。 |
| Server describe `supported_features` | `ak.feature.mls_governance_binding.full.v1` | `ak.feature.e2ee_relaxed.v1`(互斥;**MUST NOT** 同时声明 full + relaxed) |
| 在合规 / 监管语境下 | 满足"成员踢出即时生效" | 不满足,SHOULD 走非 E2EE 或专用 enclave 通道 |

**强制约束**:

- Realm 在 `ak.realm.policy_bundle` 中声明 `mls_send_pause="advisory"` 时,**MUST** 在 Realm `schema_refs` 中同时声明 `ak.profile.e2ee_relaxed.v1` profile 适配。reducer 检测到 advisory 但 Realm `schema_refs` 不含 `ak.profile.e2ee_relaxed.v1` → MUST reject(`unsupported_profile`,详细 reason `mls_send_pause_advisory_requires_e2ee_relaxed_profile`)
- 声明本 profile 的 Realm **MUST NOT** 同时声明 `ak.profile.mls_governance_binding.full.v1`(互斥)。reducer 检测同时声明 → MUST reject(`conflicting_e2ee_profiles`)
- 声明本 profile 的 Realm 后续 MLS commit **MUST** 在 `governance_binding.binding_profile` 中写入 `ak.profile.e2ee_relaxed.v1`，并在 `governance_binding.reducer_profile` 中写入当前协商 reducer profile。缺字段、写成 full profile、写成未知 profile、或与 Realm policy / ServiceDescribe 声明不一致时，接收方 MUST reject / quarantine 该 commit，并不得把对应 epoch 用于 verified timeline。
- 声明本 profile 的 Realm 若同时声明 federation，MUST 满足 §2.4.1 的 Federation guard。open / quarantine federation 直接拒绝；restricted federation 必须证明 fanout deadline 不超过 relaxed window。
- 客户端实现 **MUST**:
  - 在该 Realm 的对话 UI 上展示 banner-level 警示(不可被用户永久 dismiss,可临时折叠)
  - 在用户邀请新成员时弹窗提示"该 Realm 使用降级 E2EE",让用户知情决策
  - 在 sync metadata 中标记该 Realm 为 `e2ee_relaxed=true`,导出 / 备份 / 跨设备时保留该标记
- 服务端 `ak.server.read.describe.supported_features` **MUST** 列出 `ak.feature.e2ee_relaxed.v1` 才能接受该 profile 的 Realm 写入

**禁止扩展**:本 profile 不允许进一步降级到"不验证 `security_frontier_digest`" / "允许跨 epoch 解密无窗口限制"。降级到此为止；更宽松场景应当退回到**非 E2EE** Realm(`encryption_profile="none"`)而不是继续放宽 E2EE 承诺。

### 2.5 MLS Security Frontier Binding

Arkret v1 把 MLS epoch 只绑定到会改变当前或历史密钥取得者的 accepted control state。普通 Event admission 的 seal_ref 与 MLS security frontier 是正交证明：seal_ref 选择该 Event 的 CBA 授权视图；security_frontier_digest 证明当前 MLS epoch 已覆盖最新 key-access state。任何 Seal 都不得因为被消息引用而要求 MLS Commit 反向覆盖自身。

每个 MLS scope 投影唯一 current state：

- mls_group_id；
- epoch；
- security_frontier_digest；
- commit_ref（genesis 时为 genesis Event ref）。

security_frontier_digest 的输入由 [`mls-security-frontier-registry.json`](../../artifacts/registry/mls-security-frontier-registry.json) 闭合登记，并从 accepted Seal state 与 RFC 9420 current/pending leaf set 确定性重建：

1. Realm / Circle membership join、leave、remove、ban，以及实际使当前 MLS leaf 无效的 participant terminal；
2. 当前或 pending MLS leaf 实际引用的 participant device / Agent runtime key authorize、revoke、replacement；
3. MLS group membership；
4. 改变谁能取得当前或历史密钥的 encryption floor、content encryption scheme、history visibility / sharing policy。

与当前或 pending leaf 无关的 device/Agent key、普通 capability、message/Strand metadata、moderation、display metadata、media/routing endpoint 和 contact/consent-only state MUST 排除。block、Contact或Consent只在各自被当前操作正式登记为authority gate的路径上立即禁止新 application message、call signal或Welcome；Personal DM只读取双方directional Contact heads，Consent变化对其无效。除非accepted effect同时remove leaf，否则这些变化不单独触发rekey。

producer 不提交任意 Event/Seal ref 清单来定义 frontier。所有实现必须从相同 accepted state 得到逐字节相同的 canonical digest；未知 cell family 或无法闭合依赖时 fail closed。
#### 2.5.1 Security binding payload

ak.mls.genesis、ak.mls.commit、需要绑定当前 epoch 的 ak.mls.welcome 与 MLS proposal 使用同一 mls_governance_binding closed object。必需字段是：

| 字段 | 约束 |
| --- | --- |
| binding_version | 固定 1 |
| encoding_profile | 固定 cbor-deterministic-rfc8949-v1 |
| realm_id / effective_scope / circle_id? / sidecar_id? | 精确标识 Realm-default、Circle 或 native Sidecar MLS scope |
| mls_group_id | 目标 group |
| previous_epoch / next_epoch | genesis 为 0/0；Commit 必须 next=previous+1 |
| security_frontier_digest | 按 §2.5 的闭合集合重算 |
| binding_profile / reducer_profile | 显式解释 profile；缺失或不支持 fail closed |
| sidecar_binding? | 只在 `effective_scope.kind="sidecar"` 中出现，绑定 exact Realm-scoped desired participant authority |

membership_frontier、covered_seal_refs、policy_root、capability_root 与 discussion_metadata_digest 不再是 wire 字段。它们把同一 accepted state 重复拆成多个 producer-supplied commitments，并导致无关治理变化阻断消息；receiver 改为从 Seal state 直接重算唯一 security_frontier_digest。

每个 ak.mls.commit MUST 同时携带 mls_group_id、base_epoch、next_epoch、完整 commit_bytes_b64、commit_digest 与 governance_binding。receiver 先校验 digest，再按 RFC 9420 应用完整 Commit bytes，并核对 epoch、group 与 security frontier。只提供 digest 或 object ref 不合规。

Principal Server 对 `ak.mls.commit` 的 admission 边界是 schema、Event proof/capability、canonical effective scope/group identity、`commit_bytes_b64` 的 `commit_digest`、`base_epoch -> next_epoch` CAS 与 governance-binding shape。服务端不是 member MLS frontier authority，MUST NOT 因自己没有 member leaf/private tree state 而返回 `frontier_unavailable` 或固定 503，也无需建设第二套 server-side public-tree tracker。`security_frontier_digest` 的语义重算与 RFC 9420 Commit 应用属于持有相应 group state 的 member receiver；receiver 即使看到 accepted Event 也 MUST 独立执行，错误 Commit 不得进入 verified MLS state。

ak.mls.welcome MUST 携带 commit_ref，并与同一 Commit、recipient 和 claimed KeyPackage 逐字段闭合。Delivery/Principal Server sync surface 必须原样保留完整 payload；不得转发缺 claim、commit_ref、binding 或 ciphertext 的缩减 envelope。
#### 2.5.2 Send gate 与 self-heal

E2EE DataEvent 必须声明 mls_group_id、epoch 与 security_frontier_digest，并携带普通 Event admission 所需的 seal_ref。receiver 接受 application message 当且仅当：

1. Event 的 seal_ref / CBA admission 独立通过；
2. group 与 scope 匹配；
3. epoch 等于 winning MLS epoch；
4. message 的 security_frontier_digest 等于 receiver 在该 Event basis 可验证的最新 key-access frontier；
5. winning genesis/Commit Event 已 accepted，且其完整 RFC 9420 transcript 绑定同一 digest。

若存在尚未被 winning Commit 覆盖的 key-affecting fact，scope 进入 epoch_update_required，所有新加密 application message、call signal 和 Welcome暂停；返回 mls_governance_binding_stale。无关 capability、metadata、moderation、routing 或 consent-only state 前进时 MUST NOT 产生该错误。

任一 active member 客户端观察到 epoch_update_required 后 MUST 发起 self-heal Commit；并发 proposal/Commit 按现行 MLS winner/CAS 规则收敛。消息数、epoch 存活时长与 routing-token scope 的自保推进上限保持不变。明文 scope 不受 MLS epoch gate，但仍受即时 membership/authorization admission。
#### 2.5.3 GroupContext extension 与 proof materialization

MLS GroupContext extension type 0xF1C0 继续把确定性 CBOR 编码的完整 mls_governance_binding 纳入 confirmed_transcript_hash。canonical map 只包含 §2.5.1 的字段；禁止 indefinite-length CBOR、非最短整数、重复/乱序 map key、未知字段或 JSON/CBOR 混用。

轻客户端可以请求 MLS governance proof operation 的唯一近端 profile `group_security_frontier`。Query 逐字节绑定本地已完整验证并持久 pin 的 canonical `proof_base_basis.leaves[]` Seal 反链、exact canonical `proof_target_basis.leaves[]` 反链、从本机 current/pending RFC 9420 group state 取得的 every-and-only `local_mls_leaves[]`、profile-specific `frontier_purpose` 及其 closed 字段和 caller-selected `byte_limit`。`local_mls_leaves[]` 只含公开 `leaf_index/principal_id/credential_ref`，必须按 `leaf_index` 严格递增排列，不得携私有 tree secret；服务必须拒绝重复 index/credential，并把整组 leaf 与重放出的治理状态交叉验证，client 收到结果后仍必须与自己的同一 group state 再次逐项比较。本地 pin 不是裸 Seal ID 集合；它 MUST 在同一 crash-safe checkpoint 中保存该完整 basis 已验证的 predecessor joined notary state，以及继续按普通 `apply_seal` 重放所需的 accepted Event、历史 signer evidence 和 registry snapshot 坐标。仅保存 `SealBasis` 而丢失其验证 checkpoint 的实现 MUST 退回 T1/T2 重新建立更早的可信 base，或 fail closed，不得查询 current DID/notary 补造历史状态。Successor query 的 `base_group_state_ref` 必须逐字等于 `previous_epoch` 已 accepted 的 winning Genesis/Commit Event；它绝不指向正在 author 的新 transition。Genesis query 固定为 `(previous_epoch,next_epoch)=(0,0)`，此时尚无 prior MLS group-state Event，必须省略 `base_group_state_ref`，不得用占位 EventId 制造 governance binding 与待 author EventId 的循环。Target MUST 支配 base：每个 base leaf 要么仍是 target leaf，要么是某个 target leaf 的 ancestor；`base == target` 是合法的零过渡查询。已证明并发或不可达时返回 `mls_governance_anchor_unreachable`；因必需 Seal/Event/witness 缺失而无法判定时返回 `frontier_unavailable`，不得用服务自选单 head、common descendant 或其它 base/target 代替。

响应只携 `query_digest`、registry-closed singleton/prefix projection、sparse frontier provenance 所需的 content-addressed Event/Seal descriptor、closed sparse Merkle path 及左右 boundary/nonmembership witness；不重复可能很大的 `local_mls_leaves[]`，调用方必须保留 exact request 并重算 `query_digest`。`event_descriptors[]` 不是 base→target 区间全部 `Seal.delta[]` 的重复目录。完整 signed Seal 由标准 typed resolve surface 取得，每个 Seal 已签入的 `delta[]` digest 是普通 accepted Event resolve 的唯一 exact selector；verifier 必须另外取得并 every-and-only 核对区间内全部 delta Event，再执行 §2.5.3 的 checkpoint 重放。完整对象不嵌入 proof 响应，也不返回全 control state。`frontier_projection.branches[]` 必须按 `target_seal_ref` canonical 排序，并 every-and-only 覆盖完整 `proof_target_basis.leaves[]`。每个 branch 独立绑定该 target Seal 自己签署的 `state_root`，branch 内所有 membership/range/boundary witness 只能使用该 Seal 与该 root；协议不得把 multi-leaf joined view 的未签名 root 冒充成某个 Seal 的 signed root。verifier 完整验证每个 branch 后，必须用 base checkpoint、全部 accepted Seal/Event 与 generated lattice registry 对完整 target antichain 做 join；同一 cell 跨 branch 的 CAS/FSM conflict、`Bottom`、recovery reset 与 missing 语义都由普通 reducer 产生，禁止对 branch value 做临时 JSON merge。然后 verifier 与本地 RFC 9420 current/pending leaf set 一起重算唯一 `security_frontier_digest`；服务不得替客户端选择 MLS leaf set、basis leaves、单一 branch 或 continuation。`base == target` 仍须对 exact request 的同一完整 leaf 集求值。这个近端响应不存在 epoch-range 分块：完整响应超过 caller budget 或 v1 1 MiB 上限时返回 `mls_governance_proof_bounds_exceeded`；调用方只能提供更接近且已独立验证的 base，或 fail closed，不得拆 cell、截断或接受 partial frontier。批量/旧历史通过 request receipt 冻结的 direct accepted-Seal traversal retention，并经标准 Event/Seal/governance-dependency resolve 取得完整重放材料；它不是第二个 stateless profile。

proof outcome MUST NOT 重复 MLS leaves，也不得携带 GroupInfo 或 ratchet tree bytes；它只携 exact `query_digest`。公开 epoch-0
GroupInfo/ratchet tree 的获取只走 §5.1.1 的 group-state-material 合同；current/pending leaf set 仍由 verifier 的
RFC 9420 state 持有。两条材料路径不得合并为服务端选择 leaf set 的私有 proof DTO。

向量 `ak.vector.mls.security_frontier_key_access_only.v1` 只断言“普通 Seal/`seal_ref` 不进入
security frontier，active leaf revoke 必须进入”；v1 没有 covered-seals accumulator。

验证顺序是：确认 query 的完整 `proof_base_basis` 及其 predecessor joined verification checkpoint 已由本地 trust store 验证并原子 pin（§2.5.4）→确认响应逐字节重复 exact base/target antichains、purpose 及 closed 字段→校验 target 支配 base（包括合法的 `base == target`）→按 canonical 公式校验 `page_digest`→取得 base→target 区间内每个 Seal 的完整 predecessor closure、全部 `delta[]` accepted Event 与 registered dependency，并从 base checkpoint 拓扑重放；每个 Seal 必须按其 predecessor joined notary descriptor 验签，notary 轮换 Move 必须先由旧 descriptor 授权，禁止用 target/current notary 或 current DID key 验历史 Seal→验证响应 Event/Seal descriptor、effective-state membership、closed Merkle path、prefix boundaries 与 nonmembership→按 registry closed frontier 重算 key-access cells→重算 `security_frontier_digest`→比较 GroupContext extension 与 Event payload→把 target joined verification checkpoint、完整 target basis 和 proof cache 作为一次 crash-safe T3 写入→应用 Commit bytes。任一步缺失、歧义或不一致都 fail closed。响应出现不同 base/target 或将 open-set 反链缩成单 leaf MUST 拒绝，MUST NOT 验证通过后「顺便信任」。cache key 至少包含完整 query digest 与 `page_digest`；不存在 result-set/cursor。

#### 2.5.4 SealBasis 信任来源（normative）

§2.5.3 的验证以完整 canonical `trusted_basis.leaves[]` 反链为根：它只证明「从该已信任 cut 出发的 Seal DAG 投影自洽」，**不证明 basis leaves 本身**。
basis 信任从哪来因此是全部安全性所在，本节封闭定义，适用于所有请求 governance proof 的客户端。

**服务端的报告不产生信任。** 客户端 MUST NOT 仅因下列任一原因把某个 Seal 写入本地 trust store：

- 它出现在 `ak.self.seals.read.frontier` 的 `RealmSealFrontierView` 或任何 Seal frontier 查询结果里；
- 它是 proof response 重复的 `proof_base_basis` 或 `proof_target_basis` leaf；
- 它在 `mls_governance_anchor_unreachable` 等错误的 detail 里被建议为替代 basis。

服务端 MAY 提供**候选**；只有候选通过下面 T1/T2/T3 之一的本地校验后才能采信。这条区分是本节的
全部要点：「服务端建议、客户端用自己独立已知的事实校验」合法，「服务端断言、客户端接受」不合法。
在内容绑定 ID（[`../conformance/encoding.md` §4.0](../conformance/encoding.md)）之前客户端没有可用来
校验的独立事实，只能靠枚举信任来源；现在有了，本节因此以自证判定取代枚举。

**T1 —— event-derived Realm 的 genesis 自证。** 客户端已知 `realm_id`，据此派生
`create_event_id = retype(realm_id, "event")`（[`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)、
[`../models/common-fields.md` §6.0](../models/common-fields.md)），取回该 `ak.realm.create` Event `C`
并按 §4.0 重算其 content-bound `event_id`，MUST 与派生值逐字相等。候选 Seal `S` **MUST** 同时满足
才可被接纳为该 Realm 的初始 singleton trusted basis：

1. `S.realm_id` 等于 `realm_id`；
2. `S.predecessor_refs` 为空（genesis）；
3. `S.delta[]` 含 `C` 的 `event_digest`；
4. `S.notary_signature` 按 [`../authz/event-auth-state-resolution.md` §6.3](../authz/event-auth-state-resolution.md)
   的 genesis 例外，用 `C.payload.object.notary` 求值的 notary authority 验签通过。

任一条不成立 MUST 拒绝且 MUST NOT pin。`C` 的内容绑定 ID 与 `realm_id` 同源，因此本判定不依赖
任何一方对「哪个 Seal 是 genesis」的断言：客户端拿 `realm_id` 就能独立认出 `C`。

**T2 —— PCR 的 identity-root 锚。** Principal Control Realm 的 `realm_id` 由 principal DID 派生而
不由 genesis Event 派生（§2.5.0 例外），T1 的 create 派生不适用。PCR 的候选 genesis Seal MUST 覆盖
该 principal 唯一 critical `did_inception` root anchor unit
（[`../identity/key-management.md` §5.0.1](../identity/key-management.md)）；客户端 MUST 用该 principal
的 DID 与已验证 inception 校验该 anchor Event，再按同一 genesis notary 规则验签。

**T3 —— 已验证后继 cut（pin 前移）。** 客户端已信任完整 basis `A` 及其 joined verification checkpoint 后，任何从该 checkpoint 按完整 Seal DAG closure 与全部 registered dependency 重放、并支配 `A` 的 canonical successor antichain `B`（可含 compaction Seal）MAY 取代 `A` 成为新 pin。`B` 的 basis、joined notary/reducer state、重放依赖坐标与 proof cache 必须在同一个 crash-safe local transaction 中持久化；只写 basis、先写 basis 后写 checkpoint 或从服务响应拼装未验证 checkpoint 均不构成 T3。这是唯一合法的 basis 前移路径；open-set 必须整体前移，不能只选一个 leaf。Base/target 已证明并发或不可达时客户端 MAY 改用自己 trust store 里更旧的完整 basis 重试，或改向另一授权 proof service 请求，MUST NOT 因服务端建议替换 basis。

**三条覆盖全部首次场景**：Realm 创建者、被邀请者、同一 principal 的新设备、以及本地状态丢失后从
key backup 恢复的设备，都只需要知道 `realm_id`（PCR 则是 principal DID）——它们各自的认证路径本来
就提供这一项。因此 `ak.mls.welcome`、key backup 与设备配对包 **MUST NOT** 为携带 trusted basis 而新增
字段：那会制造第二个信任源，且都弱于 T1/T2 的自证。

取回 `C` 走 `ak.self.events.read.resolve`；候选 `S` 从 `ak.self.seals.read.frontier` 返回的完整候选
antichain 出发，经 `ak.self.seals.read.resolve` 按 `predecessor_refs[]` 反向遍历到 predecessor-free Seal。
客户端必须在有界 batch 中逐字验证 resolved Seal ID 与 predecessor edge，不得让服务直接返回一个未连接的
“covering/first activation Seal”。这些响应同样不产生信任——它们只是候选来源，判定仍在 T1/T2。

本节的 conformance 入口是 `ak.vector.mls.governance_proof.verifier.v1`：其 mutation matrix MUST 覆盖
「以服务端 observed head 缩减或替代本地 trusted basis」「候选 genesis 不覆盖派生出的 create Event」「候选 genesis 的 notary
不是 create payload 指定的 notary」三条负例，且都 MUST 在写入 trust store 前失败。
### 2.6 KeyPackage Claim 生命周期

Native Agent 的 claimed-endpoint trust binding 由 conformance vector `ak.vector.agent.mls_keypackage_authorization.v1` 固化。

KeyPackage 不应被建模为可无限次公开拉取的静态材料。E2EE 实现 MUST 将 MLS KeyPackage 作为可声明、可领取、可消费、可撤销的单次使用材料。

> **Arkret 扩展说明**：RFC 9420 Section 10.1 将 KeyPackage 定义为全局单次使用材料（一个 KeyPackage 对应一次 Welcome）。Arkret 的 claim 模型在此基础上增加了 `intended_realm_id` 绑定和 Realm-scoped claim，要求 MLS Delivery Service 跟踪 Realm affinity。这是 Arkret 的有意扩展，理由是：(a) 去中心化环境中没有中心化 Delivery Service 来全局追踪 KeyPackage 消费状态；(b) Realm-scoped claim 使客户端可以控制自己被邀请进入哪些 Realm，而非被动接受任何 Welcome；(c) claim 绑定使审计链可追溯某个 KeyPackage 被哪个 Realm 消费。实现若使用标准 MLS 库（不支持 Realm-scoped claim），MUST 至少在 Arkret 协议层维护 claim 映射表，并在 Welcome 发送/接收时执行 claim 验证。

KeyPackage lifecycle：

```text
published -> claimed -> consumed
          -> revoked
          -> retired
```

推荐记录：

```json
{
  "kind": "ak.mls.keypackage",
  "keypackage_id": "ak:mls:kp:01JS...",
  "principal_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "keypackage_ref": "sha256:...",
  "keypackage_digest": "sha256:canonical_keypackage_bytes",
  "cipher_suites": ["MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519"],
  "capabilities": ["mimi.content.v1", "ak.content.v1"],
  "state": "published",
  "created_at": "2026-04-30T00:00:00Z",
  "expires_at": "2026-05-07T00:00:00Z",
  "device_signature": "base64url..."
}
```

**MLS ciphersuite registered set（normative）**：`cipher_suites[]` 与 server describe 暴露的 MLS ciphersuite 合法值的机器可读 source of truth 是 [`mls-ciphersuite-registry.json`](../../artifacts/registry/mls-ciphersuite-registry.json)（与 hash 的 digest-suite registry、签名的 signature-alg registry、非-MLS 应用层封装的 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 形成四大算法 agility 面的对称纪律）。v1 active 集合仅 `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519`（default-MUST，RFC 9420 mandatory-to-implement suite）；软件友好的 RFC 9420 `0x0003` ChaCha20-Poly1305 suite 已作为 reserved row 占位，在 KAT、协商负例与新 contract release 完成前不得上 wire。KeyPackage claim / group 协商遇到未登记或 reserved suite MUST fail closed，即使底层 MLS 库支持。

Claim 请求 MUST 绑定：

- requester principal / service DID 和 device proof。
- intended `realm_id` 或 `mls_group_id`。
- required capabilities / content profiles / cipher suites。
- 是否允许 minimal-metadata pseudonymous credential。
- claim nonce、过期时间和目标 Welcome 路由服务。

Claim 成功后：

- KeyPackage 进入 `claimed`，并绑定 claim/requester/intended Realm、capability/digest、expiry 与 claimed endpoint 的 accepted authorization ref。普通 device 必须且只能使用 `device_authorize_event_id`；Native Agent runtime 必须且只能使用 `agent_key_authorize_event_id`。
- 同一 KeyPackage 不得被第二个 Realm/group、requester 或 Welcome 重复使用。
- Welcome `claim_ref` 携带 `{claim_id,keypackage_ref,keypackage_digest,capabilities_digest}` 加上述二选一 authorization ref，并进入 governance/AAD transcript。origin Principal Server 在 claim admission 前验证 account-local current generation、未撤销状态与 MLS LeafNode/signature key；对端验证 target service 的签名 claim，不接收 PCR history sidecar。
- 若 device 在 claim 与 Welcome 之间 revoke、re-anchor fenced 或其 authorization 被替换，未消费 claim 失效；发送方必须以 current `device_authorize_event_id` 新建 claim。Agent authorization revoke/supersede/expiry 同理。
- 返回 KeyPackage 时必须附 target Principal Server 的 endpoint signature，并由 `claims_digest` 与 target service receipt 覆盖 exact claim bytes。claim 不携 device/PCR/Agent signer history sidecar；服务签名提供对本地 admission 决定的可验证归责。device 与 Native Agent authorization refs 仍是 closed XOR，不能互相 fallback。

#### 2.6.1 Welcome `claim_envelope` 签名（normative）

KeyPackage 发布时 Realm 尚未确定，因此 per-Welcome `claim_envelope` 必须由 requester 当前 accepted signer 签署并至少绑定：`keypackage_ref`、`keypackage_digest`、`intended_realm_id`、`claim_id`、`requester_actor_id`、`nonce`、`welcome_digest`、`created_at`，以及精确二选一的 `requester_device_id + device_authorize_event_id` 或 `agent_key_authorize_event_id`。

普通 device signature 必须按 PCR authorization chain 解析到 current generation 的 accepted `device_public_key`；Native Agent 必须解析其 current active `ak.agent.key.authorize`。接收端还必须验证 intended Realm 与 Welcome group 一致、claim nonce/digests 一致、authorization ref 在消费时仍 current，以及 `welcome_digest` 等于 canonical Welcome bytes。任何失败都拒绝 Welcome，reason=`keypackage_welcome_envelope_mismatch`。Delivery Service key、目标 KeyPackage 自身的 publish signature或裸服务断言都不能替代 requester signature。

#### 2.6.2 Last-Resort KeyPackage（可选语义）

§2.6 的默认模型把 KeyPackage 建模为严格单次使用材料：`published -> claimed -> consumed`，"同一 KeyPackage 不得被第二个 Realm / MLS group、第二个 requester 或第二次 Welcome 重复使用"。该纪律带来两个运营缺口：(a) 长期离线设备的预发布 KeyPackage 池耗尽后，该设备**完全不可被邀请 / 加群**，直到下次上线补池；(b) 对端可在 claim 限速预算内逐步 claim 直至抽干池子，制造**定向 DoS**——使目标设备对外不可邀请。

RFC 9420 Section 10 明确承认 last-resort KeyPackage 模式（生产 MLS 部署如 Wire 已采用）。Arkret 采纳该模式为**可选能力**：实现 MAY 在 KeyPackage 池耗尽时提供一个标记 `last_resort=true` 的可复用 KeyPackage 作为回退。该能力**不改变默认 fail-closed 路径**——不支持的实现继续在池空时 claim 失败（见下文协商规则）。

**前向保密折衷声明（normative）**：last-resort KeyPackage 可被多次消费意味着同一 init/encryption key 被复用于多个 Welcome，**削弱了 Welcome 阶段的前向保密**——在该 KeyPackage 被轮换前，任一被攻破的 last-resort 私钥可解出此前用它封装的全部 Welcome（及其携带的 group secrets 初始注入）。影响范围是经该包加入的每个 group 在对应加入 epoch 及其后续 ratchet 之前可由 Welcome 取得的 application secret / history material；不追溯解密加入前的旧 epoch，但会暴露该加入路径本应由一次性 KeyPackage 隔离的初始历史材料。该折衷是 last-resort 模式的固有代价。实现 MUST 通过下文的强制轮换把弱化限制在一个**有界窗口**内，并 MUST 向启用该能力的部署 / 用户明示此窗口内 Welcome 前向保密被弱化。组建立后的常规消息 ratchet 前向保密不受影响（仅初始 Welcome 注入受影响）。

**状态与多次使用（normative）**：

- last-resort KeyPackage 在发布时 MUST 标记 `last_resort=true`，并 MUST NOT 进入单次 `claimed` / `consumed` 状态。每次领取由独立 `keypackage_claim_record` 表达，KeyPackage 本身保持 `published`，直到轮换、过期或显式吊销时转入 `revoked`；account deactivation 可按 [`device-lifecycle.md` §9.1](./device-lifecycle.md) 转入 `retired`。
- `last_resort` 是 Arkret 应用层标记，MUST 包含在 KeyPackage 发布条目的 `device_signature` 签名输入中；接收方 MUST 验证该签名，不得从未签名元数据推断或改写此标记。v1 不为尚未进入 IANA MLS 注册表的应用组件分配私有 wire codepoint。
- 池中存在普通（单次）KeyPackage 时，claim 响应 MUST 优先返回普通包；仅当普通包池为空时，claim 响应 MAY 返回 last-resort 包。
- claim 响应返回 last-resort 包时 MUST 在对应 `keypackage_claim_record` 中置 `last_resort=true`，使 requester 与 holder 都能识别本次 join 走的是 last-resort 路径。
- last-resort 包**不走** §2.6 的单次 `consume` 路径：服务端 MUST NOT 因一次 Welcome 消费而把它转入 `consumed` 或从池中移除。`ak.keys.keypackages.consume` 对 last-resort `keypackage_ref` 的调用 MUST 被服务端识别为幂等（返回成功但不改变 `published` 状态），不得返回 `keypackage_already_consumed`。
- §2.6 / §2.6.1 的其余校验（`keypackage_digest` / `capabilities_digest` / current authorization ref 匹配、`claim_envelope` 签名、Realm 反向 resolve）对 last-resort 包**仍然全部适用**；放宽的只有"单次性"。

**消费审计（normative）**：每次 last-resort 包被 claim / 用于 Welcome，MUST 进入 §2.6 既有审计链。实现 MUST 为每次消费追加一条独立 `keypackage_claim_record` 审计记录，至少携带 `keypackage_ref`、`keypackage_digest`、`claim_id`、`last_resort=true`、消费的 `intended_realm_id`（见下文 Realm affinity）与时间戳。该记录不是第二条 `ak.mls.keypackage` 状态 Event，也不得触发 KeyPackage FSM transition；KeyPackage 本身保持 `published`。审计链 MUST 保留每次消费的独立记录（append-only，不得覆盖前次），使审计员能枚举"该 last-resort 包被哪些 Realm / requester 在哪些时点使用"。

**强制轮换时点（normative）**：

- last-resort 包的持有 device 下次上线时 MUST 轮换该 last-resort 包：发布新的 last-resort KeyPackage（新 init/encryption key），并把旧包转入 `revoked`、记录 `revocation_reason="keypackage_rotated"`，使旧包不再被分发给新 claim。`keypackage_rotated` 不是 KeyPackage 状态。
- 持有者上线后 MUST 对**所有经该 last-resort 包加入的 group**触发一次 MLS update（self-update Commit，引入新 leaf key 材料），以推进这些 group 的 epoch、把前向保密恢复到正常 ratchet 水平，从而**闭合**上文所述的弱化窗口。
- 实现 SHOULD 在 holder 本地持久化"经哪个 last-resort 包加入了哪些 group"的映射，以便上线后精确触发上述 update；无法精确定位时 MUST 对该 device 当前所有 last-resort-joined group 保守触发 update。
- 轮换与 update 完成前，弱化窗口持续存在；实现 SHOULD 尽量缩短 device 的离线-上线间隔以限制窗口长度。device 上线时间不可由协议强制，故"上线触发轮换"无法单独给出 normative 上界；为防止设备长期离线把弱化窗口拉到任意长，对 last-resort 包**自身的 `expires_at`** 施加独立于上线轮换的硬上限：
  - 非 `personal_node` profile 的部署，last-resort KeyPackage 发布时 MUST 设置 `expires_at`，且其有效期（`expires_at - created_at`）MUST NOT 超过 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) §6 登记的 "KeyPackage 有效期" 默认上限（30 days）；profile 对 last-resort 包 MUST NOT 声明长于该上限的有效期（普通 KeyPackage 的"更长有效期由 profile 声明"豁免不适用于 last-resort 包）。服务端 MUST NOT 把已过 `expires_at` 的 last-resort 包返回给新 claim（MUST 转 `revoked`，`revocation_reason="keypackage_expired"`），从而把"未上线轮换"情形下的弱化窗口硬封顶在该生命周期内。
  - `personal_node` profile MAY 放宽该上限（个人设备长期离线场景），但 MUST 向用户披露弱化窗口随之延长。
- 高保证部署 MUST 禁止 last-resort 回退：`ak.profile.high_security_organization.v1` / `ak.profile.sovereign_deployment.v1` 下的 Realm MUST 通过 profile 禁止 last-resort join（即不声明 `ak.feature.mls_last_resort_keypackage.v1` 或在 Realm profile 中 opt-out），此时该 Realm 的邀请 MUST 走单次包或 fail closed，不接受任何 `last_resort=true` 的包。

**Realm affinity 处理（normative）**：§2.6 的 `intended_realm_id` 是 Realm-scoped claim——普通 KeyPackage 的 claim 绑定单一 `intended_realm_id`。last-resort 包天然要跨多个 Realm 复用，与该绑定存在张力。Arkret 选择**按 Realm 维度的 last-resort 池**而非全局 affinity 豁免：

- 实现 MUST NOT 用单个全局 last-resort 包跨任意 Realm 复用（即不豁免 Realm affinity）；而是 MUST 为每个需要 last-resort 回退的 Realm 维护**Realm-scoped 的 last-resort 池条目**：每个 last-resort `keypackage_claim_record` 仍绑定确定的 `intended_realm_id`，其多次复用**限定在同一 `intended_realm_id` 内**。
- 因此 last-resort 包的"多次使用"语义是**Realm 内多次**（同一 Realm 的多个 Welcome / 邀请可复用同一 last-resort 包），而非跨 Realm。跨 Realm 的 last-resort 回退 MUST 由各 Realm 各自的 last-resort 池条目分别满足。
- 该选择保留了 §2.6 的核心审计与隔离性质：每次消费的 `intended_realm_id` 确定、claim-Realm 一致性仍可校验、`claim_envelope` 的 Realm 反向 resolve 校验不被绕过；代价是 holder 需为每个活跃 Realm 各发布一个 last-resort 包（或在上线时按需补足）。
- holder 离线期间若一个尚无 last-resort 条目的 Realm 需要邀请该 device，则该 Realm 的 claim 在不支持普通包回退时 MUST fail closed（与默认池空行为一致），不得退化为跨 Realm 复用其它 Realm 的 last-resort 包。

**可选协商（normative）**：last-resort 是可选能力，复用 server describe `supported_features`（§2.4.2 同款 `ak.feature.*` 机制）与 Realm profile 的既有协商面，不引入新协商通道：

- 提供 last-resort 回退的服务端 MUST 在 `ak.server.read.describe.supported_features` 中声明 `ak.feature.mls_last_resort_keypackage.v1`；未声明该 feature 的服务端 MUST 继续 fail-closed（池空 claim 失败），claim 响应 MUST NOT 返回 `last_resort=true` 的包。
- device 发布 last-resort 包前 SHOULD 校验目标服务端声明了该 feature；requester 收到 `last_resort=true` claim 记录时，若其本地 profile 不接受 last-resort 路径（例如高保证 Realm 要求严格单次性），MUST NOT 用该包发 Welcome，并 SHOULD 视为池空（按默认 fail-closed 处理）。
- 是否在某 Realm 允许 last-resort join 由 Realm policy / profile 决定：要求严格前向保密的 Realm MAY 通过 profile 禁止 last-resort join；`ak.profile.high_security_organization.v1` / `ak.profile.sovereign_deployment.v1` MUST 禁止。此时即便服务端支持该 feature，该 Realm 的邀请 MUST 走单次包或 fail closed。
- 这是加性 feature：不声明 feature、不发布 last-resort 包的部署，其 claim / consume / Welcome 行为保持默认 fail-closed 路径不变。

### 2.7 Minimal-Metadata E2EE Realm

Minimal-metadata 的 author/authorization subject 是 Realm-local pairwise endpoint actor。每个
`(Realm, endpoint incarnation)` MUST 使用唯一 canonical `ak:did_core:key:<canonical-multibase-id>` ActorId 与 signature key；同一 Realm 的不同 endpoint
不得复用，同一 endpoint MAY 在该 Realm-default group 与该 Realm 的 Circles 中复用。它在 Event actor、exact active
Leaf BasicCredential identity、Event `actor_id`、content KDF/counter sender domain 与 history request sender
domain 中必须是该 canonical did_core_id 的同一组 UTF-8 bytes。proof `verification_method` 是完整 did:key DID URL；其 controller/base 必须经 registered adapter 投影到该 did_core_id，且其 key 必须等于 exact leaf signature key。

服务端只按 pairwise actor 执行 membership/current gate/join floor/remove/rejoin，不得查询目录或 transport session
推断真实 principal/device 聚合。持有 encrypted `identity_link` 的成员可在本地聚合并批量移除已知 actors；协议不声称
服务端能证明已发现某真实 principal 的全部 endpoint。该 profile 隐藏真实 principal、global DeviceId 和跨 Realm
关联，但不隐藏同一 Realm/Circle 中 actor、request range 或 timing 的可关联性。

Ordinary human 的 credential identity 必须逐字等于 canonical DeviceId UTF-8；Native Agent 必须逐字等于 canonical
Agent ActorId UTF-8。三种 profile 的 receiver 都只从 Event 钉住的 exact historical active leaf 取 sender domain；
零匹配、多匹配、credential/signing-key mismatch 或 directory fallback 均拒绝。


### 2.8 AAD 与 current frontier 的唯一性

v1 不再提供可选 AAD-visibility policy。加密内容只使用 §2.3 的 closed pre-encryption header；EventId 可见性、
discoverability、push 与 preview 由各自 projection 决定，不能改变 AEAD transcript。MLS-backed application Event
引用的 `group_state_ref` 必须覆盖 current effective history frontier；producer、服务端 admission 与 receiver 三方
都必须重算。policy 已改变而 winning Commit 尚未覆盖时，只允许治理 transition，不允许 application send。


### 2.9 Reaction routing window

```text
routing_window = floor(unix_ms(event.created_at) / 3_600_000)

routing_root[N] =
  exporter scheme: history_secret[N]
  standard scheme: MLS-Exporter(
    "ak.reaction-routing-root-v1",
    canonical_effective_scope_key_bytes(effective_scope),
    KDF.Nh
  )

K_reaction_routing = ExpandWithLabel(
  routing_root[N],
  "ak.reaction-routing-v1",
  JCS({effective_scope,target_ref,routing_window}),
  32
)
routing_tag = HMAC-SHA256(K_reaction_routing, utf8(canonical_emoji))
```

一小时是 v1 固定常量，取 Event 自身必填、已签且加密前冻结的 `created_at`；receiver 按 Event 自身 window 验证任意
历史 tag，不使用“当前/上一窗”限制。`target_ref` 是已存在的 canonical EventId。Exporter late receiver 可从获准
history secret 验证；standard MLS routing root 不交付给后加入者。Tag 不对持有 epoch root 的成员隐藏 emoji，也不是
跨 window reaction identity。Plaintext reaction 使用公开语义，不需要 opaque tag。

v1 不定义 mention routing KDF、plaintext recipient token 或专用 routing wire；mention 保持在 ciphertext 中，
push 只发通用 blind wakeup。Routing window 不驱动 MLS Commit 或 epoch。

### 2.10 Exporter AEAD 内容与历史恢复

仅 `content_scheme=mls_exporter_aead_v1` 的 Realm/Circle 可导出和交付：

```text
history_secret[N] = MLS-Exporter(
  "ak.history-v1",
  canonical_effective_scope_key_bytes(effective_scope),
  KDF.Nh
)

K_content[N,sender] = ExpandWithLabel(
  history_secret[N],
  "ak.content-v1",
  exact_active_leaf_basic_credential_identity,
  AEAD.Nk
)

nonce = I2OSP(durable_sender_counter, AEAD.Nn)

content_aad = JCS(reconstruct_pre_encryption_header(outer_signed_event, exact_group_state, encryption_context))
```

`sender_domain` 不上 wire，只取 producer 在 seal 前冻结的最终 producer proof verification method / signer，并与 exact active
Leaf BasicCredential identity 交叉验证：ordinary 从 verification-method fragment 投影 canonical DeviceId；Native Agent 与 minimal
从 verified signer/actor 投影 canonical ActorId。principal_server_admission proof 不参与。Producer proof 自身后生成且不进入 EventId
preimage；若最终 proof method 与冻结值不同，admission 必须先拒绝，receiver 重构 AAD 也必然 open 失败。Producer 以原子 CAS 在
`(mls_group_id,epoch,sender_domain)` 域耐久预留 counter；崩溃可留下 gap，但不得复用、回退或 random fallback。
counter 耗尽或状态无法证明时必须先推进 epoch。Nonce 不上 wire；counter 只出现于 exporter `encryption_context`，nonce 由其机械派生。
Standard MLS 分支把同一 `content_aad` 作为 RFC 9420 authenticated_data，不使用 Arkret counter、K_content 或 exporter nonce；
exporter 分支才使用 per-sender K_content 与 `I2OSP(counter,AEAD.Nn)`。

本机从 verified MLS state 直接导出的 secret 是 `local_authoritative`。history response、RRK open 与其它 received secret 永远只是
candidate；v1 不定义远端 epoch promotion。Receiver 先验证外层 proof、scope/group/epoch、sender domain、AAD、schema 与
replay，再逐 candidate 尝试。AEAD 成功只把 exact `(EventId,event_digest,sender_domain)` 耐久绑定到该 candidate digest，失败也只记录
该 Event attribution；binding 只保存 digest/attribution、不得 pin secret bytes，也不得因此立即淘汰或升级 epoch 候选。后续配额驱逐
可以只删除 candidate bytes 并保留有界 attribution/tombstone 以供 refetch。恶意作者的 fake secret/fake ciphertext 只影响其自身签名 Event。配额、digest
去重、确定性 eviction 与 backup 限制见 history-visibility §7。

Receiver 先按 EventId 折叠完全相同 Event，再执行 durable replay gate：
`(mls_group_id,epoch,sender_domain,counter) -> exact EventId/ciphertext digest`。同 tuple 的不同 Event/digest
即使 AEAD 可开也拒绝。ordinary DeviceId 历史上不得重分配给另一 endpoint/principal。

`history_secret[N]` 是 epoch 最小授权单元，不能执行 per-Event audience；各 epoch secret 必须独立，禁止正向或反向
互推。交付授权、per-request response stream、proof、backup、RRK 与 multi-candidate store 的唯一合同见
[`history-visibility.md`](../governance/history-visibility.md)。Standard `mls_rfc9420` 没有可交付 secret，固定
`history_access=since_join`。


### 2.11 Ordinary Native Agent Event 的 authorization + MLS 双绑定（normative）

本节只适用于未启用 minimal-metadata profile 的 ordinary MLS encrypted Event。Receiver 在 `event-and-patch.md` signer dispatch 已唯一确定 Native Agent regime 后，MUST：

1. 从 encrypted envelope 读取精确 `(group_id, epoch, group_state_ref)`，并证明 ref 是该 epoch accepted/winning state；不得用 current epoch 或同 epoch另一 fork补偿。
2. 只接受`verification_mode=historical_event`的`ak.schema.agent_signer_evidence.v1`：验证destination-signed Event admission receipt、Agent authority snapshot、key与Agent lifecycle witness、controller Account Authority gate，以及这些basis在receipt `accepted_at`的有效性；不得以current snapshot重建历史。按profile验证可选transparency proof。
3. 要求 proof method byte-identical 等于 binding method，并用 binding raw key验证 detached JWS；proof transcript actor仍是Event `actor_id`，signer principal是 `executed_by ?? actor_id`。
4. 在该historical group state的active leaves中找到恰好一个BasicCredential identity等于signer Agent DID。缺失、removed、non-basic或duplicate均拒绝。
5. 要求该leaf `signature_key`与binding raw key逐字节相等。
6. 要求leaf admission lineage中的KeyPackage/Welcome binding引用同一 `agent_key_authorize_event_id`。lineage缺失或不同均拒绝。

MLS leaf在ordinary Realm是membership/key cross-binding，不是authorization root；不得仅凭leaf把内容提升为Verified。反之，Agent evidence也不能替代encrypted Event的historical MLS leaf。任一确定性mismatch返回 `agent_signing_key_mismatch` 或 `agent_mls_leaf_binding_mismatch`；证据缺失/过期返回pending/stale。minimal-metadata Realm继续只走§2.10.3且禁止查询本evidence。

## 3. 受审计的端到端加密 (Audited E2EE) — 可选 hardening profile

> **完整规范见 [`audited-e2ee.md`](./audited-e2ee.md)**。本节只提供概览；详细 schema、
> Audit Applet Binding、release session、RYW receipt 流程、disclosed/attested 区分、forbidden marketing terms
> 全部由独立的 audited-e2ee profile 文档承载。

Arkret 提供 **"透明留痕审计 (Transparent Audit Trail)"** 机制。审计 applet 是控制面绑定，不是 MLS 成员，也不接收实时 sync fanout；需要访问历史材料时，必须走 active `ak.audit.applet_binding`、`ak.audit.session.request`、`ak.audit.session.authorize`、`ak.audit.session.notice`、`ak.audit.release` 和 `ak.audit.session.close`。Audit Applet Binding 不得追溯生效：消息是否可被审计在加密时由当时已被 MLS commit 覆盖的 binding / release window policy 固定，后续新增 applet 或扩大窗口不得覆盖既有消息。

该机制划分为两类正交保证 hardening profile：

- **`ak.profile.attested_audit.e2ee.v1`**（`audit_assurance_class="attested_hardware"`）：通过
  TEE / HSM / 等价硬件隔离把 release service 输出**密码学绑定**到 accepted `ak.audit.release` 与 RYW receipt。
- **`ak.profile.disclosed_audit.e2ee.v1`**（`audit_assurance_class="disclosed_policy"`）：仅在
  Realm / Circle policy 中**公开声明**审计 applet、审批和通知流程，**不提供密码学/硬件强制**。

两者**不是强弱不同的同一保证**，而是不同 family 的保证。任何把两者混称为 "Auditable E2EE"
或暗示二者等价的措辞都不符合本规范——禁止措辞清单与 join warning canonical 文案见
[`audited-e2ee.md` §7 与 §3.3](./audited-e2ee.md)。

v1 core 互操作 **不要求** 实现这两个 profile；只有在 Realm / Circle 显式存在 active Audit Applet Binding 且对应 activation frontier 已被 MLS commit 覆盖后才启用。需要审计 / 合规能力的部署可以按所在 audit profile 声明 RYW receipt、release service attestation、阶段性通知和 sealed historical release。普通 E2EE Realm 不进入该 profile 时，不得产生 `ak.audit.applet_binding`、`ak.audit.session.*` 或 `ak.audit.release`；进入 profile 前已经加密的消息也不得被后续 binding 追溯 release。

下面继续描述与 audit profile 正交的核心 E2EE 机制。

## 4. 受控账号的通信穿透 (Master-Agent Control)

协议严格区分“场地方合规审查 (Realm Audit)”与“参与方主控权穿透 (Master-Agent Control)”。

当一个受控账户（如 AI Agent，拥有自己独立的 DID）加入了一个私密加密群组，其控制者（Controller / Master）可以通过显式设备、授权转发或受控日志获得该 Agent 的通信副本。这属于**终端节点数据与密钥管理范畴**，不等同于场地方合规审查；只要访问范围已经在 capability grant、设备绑定或 owner-private policy 中声明，就不属于合规审计 release 流程（不触发 §3 的 `ak.audit.applet_binding` / `ak.audit.session.*` / `ak.audit.release`）。

协议支持以下两种原生方式实现 Controller 对 Agent 的通信穿透。默认实现 SHOULD 使用方案 A；方案 B 只在部署和产品策略明确时启用。

### 4.1 方案 A：独立 Agent 密钥与显式控制通道 (Independent Agent Key) —— 默认

Agent SHOULD 拥有独立 DID、独立 device key 和独立 MLS KeyPackage。Controller 通过 capability delegation、device / session grant、approval policy 和可撤销的 owner-private control channel 管理该 Agent。

- **机制**：Agent 自己生成和持有签名密钥、设备密钥与 MLS KeyPackage；Controller 通过显式 grant、controller approval、kill switch、审计事件和可选的 owner-private 1 对 1 E2EE Realm 接收必要副本或摘要。
- **效果**：Agent compromise 的影响边界限制在 Agent 自身 DID、device、session、grant 和可见 Realm 内。Controller 根种子、恢复密钥和其他身份材料不会因为 Agent 运行环境泄露而被扩散。

规则：

- Agent 私钥、Controller 主体私钥、Controller recovery key 和 Controller backup key MUST 是不同密钥域。
- Controller 拥有权限不自动使 Agent 拥有权限；Agent 写入、加入 Realm / Strand discussion track、读取 owner-private 知识源、读取 owner presence 或启动外部 protocol session 仍必须命中 Agent 自己的 grant / approval / policy。
- Controller 的管理面 MUST 能解释 Agent 的 Controller、responsible actor、effective grant、presence policy、knowledge source、join policy 和 expiry。
- 撤销 Controller 对 Agent 的控制通道时，必须使相关 session grant、owner-private 知识源 grant、presence trigger 和 tool / protocol session grant 失效。

### 4.2 方案 B：多设备绑定 (Multi-Device KeyPackage)
- **机制**：Agent 作为一个独立的物理/逻辑实体，生成自己的 `KeyPackage`，但在身份层面上挂靠在 Master 的 DID 下，作为 Master 的另一台“设备”。
- **效果**：在 MLS 树中，发送者对同一个主体的多个叶子节点加密。Master 手机与 Agent 服务器同时收到密文副本并各自解密。

方案 B 会把 Agent 与 Controller 的主体边界收紧，适合“同一 principal 的托管设备”而不是“独立 Agent DID”。若产品向用户展示 Agent 是独立 Actor，或 Realm policy 要求 automated actor 可审计，MUST 使用方案 A，不得把 Agent 静默伪装成 Controller 的普通设备。

### 4.3 HD 派生的限制

使用 Controller 根种子或主恢复种子派生 Agent 初始私钥不是 v1 默认 profile。实现 MAY 在完全本地、单用户、可导出性受控且 UI 明确告知风险的 profile 中使用 HD 派生，但必须满足：

- 派生路径、purpose、Agent DID、device id、audience 和 expiry 必须固定并可审计。
- Agent 子密钥泄露不得允许攻击者推导 Controller 根种子、Controller DID 控制密钥、recovery key 或其他 Agent 子密钥。
- HD 派生密钥不得用于 Controller 的 DID recovery、Realm admin grant 签发或组织治理动作。
- 该 profile 必须声明为可选高风险能力；互操作对端不得假设所有 Agent DID 都由 Controller 根种子派生。

## 5. 组员变动与高可用容错 (Proposal & Commit)

在去中心化网络中，管理员踢人（或邀请人）是一个典型的容易因网络抖动而“在部分完成后导致 epoch advancement 卡死（key tree 锁定）”的操作。为避免单点故障导致群组密钥树锁定，Arkret 严格继承了 MLS (RFC 9420) 的 **“提案与提交分离 (Proposal & Commit)”** 架构。

### 5.1 MLS Group Genesis

`ak.mls.genesis` 创建 Arkret 绑定的 MLS group 初始状态。它不是普通 Commit，也不消费 Proposal；它声明 epoch 0 的 group identity、初始 ratchet tree / GroupInfo proof 和被 MLS GroupContext extension 覆盖的 Arkret application state。

**Canonical effective scope/group identity（normative）**：对可执行 MLS scope 定义
`canonical_effective_scope_key_bytes`：Realm 为 `utf8(canonical realm_id)`；Circle 为
`utf8(canonical circle_id)`；Sidecar 为
`utf8(canonical realm_id) || 0x1f || utf8(canonical sidecar_id)`。三类 typed id 的 lexical space 均不含
`0x1f`。`mls_group_id` MUST 等于
`base64url_no_pad(canonical_effective_scope_key_bytes(effective_scope))`；`RealmGenesis` 或其它 scope 不可执行。
producer、Principal Server 与 receiver MUST 复算比较。普通 Realm/Circle/Sidecar scope 不定义第二 active group、
隐式 replacement 或 activate Event；同 scope 的不同 group id 在 schema 后的 semantic admission 阶段直接拒绝。

`ak.mls.genesis.payload` MUST 至少包含：

- `mls_group_id`
- `effective_scope`：tagged scope —— `{kind:"realm", realm_id}` 表示 Realm-default MLS group；`{kind:"circle", realm_id, circle_id}` 表示 MLS-backed [Circle](../models/circle.md)；`{kind:"sidecar", realm_id, sidecar_id}` 表示 native Sidecar MLS group。MUST NOT 从 `strand_id`、track 或隐藏 Circle 推断 genesis scope。
- `epoch`：MUST 为 `0`。
- `creator_principal_id`
- `creator_device_id`
- `cipher_suite`
- `group_info_ref` 与 `group_info_digest`
- `ratchet_tree_ref` 与 `ratchet_tree_digest`
- `governance_binding`
- `created_at`

Genesis 接受规则：

1. 创建者必须在 `governance_binding.security_frontier_digest` 所覆盖的 accepted key-access state下有创建该 MLS group 的权限；通常需要 `ak.mls.genesis` 或包含该动作的管理 grant。
2. `governance_binding.next_epoch` MUST 为 `0`；若包含 `previous_epoch`，也 MUST 为 `0`。
3. 同一 effective scope（其 `mls_group_id` 已由上式唯一派生）的 genesis/epoch/key-schedule cell 使用 `cas_register + bottom=reject`。并发重复 genesis 会使该 cell 返回 `⊥`，后续 MLS Commit Control Move 必须 fail closed，直到 recovery Control Move 修复；不同 group id 不能创建另一个 cell。
4. Genesis 后即可发送 epoch 0 application message。第一次成员变动或 group context extension 更新必须使用 `ak.mls.commit` Control Move，其 `base_epoch=0`、`base_epoch_ref` 指向 effective `ak.mls.genesis`、`next_epoch=1`。
5. 新加入成员的 `ak.mls.welcome` MUST 引用 effective genesis 或后续 effective commit 派生出的 epoch state；客户端不得从未被 accepted Seal 覆盖的 welcome / ratchet tree 本地推断 group authority。

#### 5.1.1 Epoch-0 public group-state material

`group_info_ref` 与 `ratchet_tree_ref` MUST 分别是 `ak:blob:sha256:...` content-addressed ref（省略号位置是
64 个 lowercase hex）；ref 内嵌 digest MUST 分别与同 Event 的
`group_info_digest`、`ratchet_tree_digest` 逐字对应。producer MUST 在提交 genesis 前把精确 RFC 9420
GroupInfo bytes 与 `ratchet_tree` extension bytes 放入可由承载该 Realm 的服务解析的 durable object store，
并对**原始 bytes**计算 SHA-256。ref 只提供检索坐标，不替代 digest 校验；只有 digest、只有 ref、随机 UUID
object ref、解析后的 leaf DTO 或本地路径都不合规。

需要读取 epoch-0 public tree 的 federation peer 或显式部署的独立公开 MLS group tracker MUST 使用注册操作
`ak.peer.mls.read.group_state_material`（`POST /_arkret/peer/mls/group-state-material`）或逐字段等价的同进程
typed binding。request 必须逐字携带 accepted genesis 的 Realm/scope/group/epoch/Event id 和两组 ref/digest；
响应必须回显同一 binding，并以未填充 base64url 返回两份原始 bytes。provider 在响应前 MUST：

1. resolve `group_state_event_id` 为当前 Realm 可验证、accepted 且未 quarantine 的 `ak.mls.genesis`；
2. 逐字段比较 Event 中的 scope/group/epoch/ref/digest，不允许 caller 用一个 Event 的授权取另一个对象；
3. 从 ref 取两份 bytes，对 raw bytes 重算 SHA-256，同时比较显式 digest 与 ref 内嵌 digest；
4. 按 RFC 9420 验证 GroupInfo、GroupContext、cipher suite、group id、epoch 与 ratchet tree 一致，并确认
   `governance_binding` 是该 Event transcript-authenticated binding；
5. 对不可见、不存在、未 accepted、缺对象、digest mismatch、tree/GroupInfo 不一致或超限一律 fail closed，
   不返回部分材料。

此操作只披露 RFC 9420 public group state，不披露 private tree、path secret、epoch secret 或 application key。
HTTP caller MUST 使用 §3 的 service-to-service authentication，并且是该 Realm 当前授权的 federation peer 或
被 Realm policy 显式授权读取 MLS public group state 的服务；同进程 tracker 也必须执行完全相同的 Event acceptance、visibility、digest 与 RFC 9420
校验。consumer 只能从验证后的 ratchet tree 的实际 occupied leaves 恢复 RFC leaf index；不得枚举 KeyPackage
记录猜测 tree position、不得按到达顺序编号，也不得从 governance proof bundle 获取 leaves。

### 5.2 意图与生效的分离
组员的增删改是两阶段流程：
1. **意图上链 (Proposal)**：成员发出 `ak.mls.proposal`（例如移除某成员的意图）。这只是一条明文路由加上密码学签名的操作意图。此阶段 group epoch 尚未推进，先前密钥仍有效，被提议移除的成员仍在 group 内。
2. **正式生效 (Commit)**：MUST 有成员针对上述 Proposal 构造并广播 `ak.mls.commit`。一旦 Commit 被 accepted Seal 覆盖，epoch 推进，ratchet tree 据此更新，新 group secret 仅分发给剩余成员（不含被移除成员）；自该 epoch 起，被移除成员无法解密后续 application message。

### 5.3 Committer 失联与 Commit 接管 (Takeover)
单一 committer 失联 MUST NOT 永久锁定 epoch 推进：任一持有相应 commit 权限的成员 MAY 在 observe 到 pending `ak.mls.proposal` 后构造并广播 `ak.mls.commit` 接管该 proposal；commit 被 accepted Seal 覆盖后，被移除成员 MUST 失去后续 epoch 的解密能力。

- **挂起态的可用性**：在对应 Commit 被 accepted Seal 覆盖前，scope 保持当前 epoch 与 group secret；尚未被移除的成员 MAY 继续使用当前 epoch 密钥收发 application message。
- **Churn 合并**：committer SHOULD 在不超过 `max_mls_commit_delay_ms` 的前提下，把同一 `(scope, mls_group_id, base_epoch)` 上已可见且仍满足授权 / membership / policy freshness 的 pending membership proposals 合并进单个 Commit；实现不得为每个 join/leave 机械地产生独立 Commit。高隐私或大群 profile MAY 声明更严格的 epoch 推进速率上限，但 ban / revoke / device revoke 不得因此超过 §2.4.1 的发送暂停窗口。
- **Commit 接管 (Takeover)**：任一持有相应 commit 权限的成员在 observe 到未消费的 Proposal 后，MAY 构造消费该 proposal 的 `ak.mls.commit` 并广播。该 commit 被 accepted Seal 覆盖后，epoch 推进，被移除成员自该 epoch 起 MUST 无法解密后续 application message。

#### 5.3.1 Direct Conversation participant MLS authority

在 `ak.profile.direct_conversation_realm.v1` 中，canonical pair 双方通过
`ak.authority.direct_conversation_participant.v1` 对等取得 `ak.mls.proposal` 与 `ak.mls.commit`，所以
epoch 活性不得依赖 creator/root controller 在线。求值仍必须逐字段验证唯一 immutable binding 的
`realm_id`、`main_strand_id`、`mls_group_id`、双方 active membership 与当前 MLS governance binding；仅有
membership、相同 group id 或 root owner 均不足。

同一 stable participant 增加其 active authorized device 时只可使用 profile action
`ak.mls.welcome.own_device`：Welcome recipient device 必须在该 participant 的当前 device authorization 中，
KeyPackage/claim/nonce/commit/MLS group 必须与 active binding 和当前 epoch 精确匹配。该 action不得加入第三
principal、对方的 device 或未知 device；这些情况也不能回退到宽 `ak.mls.welcome`。Native Personal Agent
participant 还必须同时满足 immutable provision、runtime key、独立 capability 及当前 participation
selection/policy gate。

participant leave/ban、Realm terminal 或 immutable main Strand terminal accepted 时，当前 participant
MLS authoring authority 立即停止，同一 binding 投影为 `suspended`，不等待 retirement fact。恢复不得创建
新 Realm/main Strand、successor/predecessor binding 或历史 segment；resolver 返回同一 `pair_key` 与永久坐标，
并只在同一 scope-derived group 内用普通 Commit/rejoin 单调推进 epoch，绝不创建第二 group 或重置 epoch。若
所有成员都丢失该 group 的私有状态，旧 Direct Conversation Realm 终结；继续会话必须创建新的 DC Realm/new realm_id。
旧 epoch 的历史解密仍逐次按 receipt-bound direct Seal replay、current 单向收紧 history_access、incarnation/join floor、首次入队 current gate 与本地 key availability 判定，
恢复不得自动补发旧 epoch key。

### 5.4 并发 Commit
如果 A 和 B 同时发起不同的 Commit，或者 A 发送缓慢导致与 B 的接力 Commit 在网络中发生竞态碰撞：
- 节点 MUST 以 accepted Seal view 下的 `mls_epoch_cell` / `key_schedule_cell` Lattice 结果为准。互不可达候选不会按时间或 actor 自动选 winner。
- 若并发 Commit Control Move 都满足各自 precondition 但写入同一 `cas_register` epoch cell 的不同值，该 cell 返回 `⊥`；后续 E2EE DataEvent fail closed，直到 recovery Control Move 或后续有效 Commit 修复。
- 只有 effective Commit Control Move 能成为合法的下一个 Epoch。未被 accepted Seal 覆盖或导致 bottom 的 Commit 客户端 MUST 丢弃本地 epoch 变更并拉取当前 Seal view。

MLS Commit 的输入和输出必须在 Event payload 中可验证表达：

- `mls_group_id`：目标 MLS group。
- `base_epoch`：Commit 构造时读取的当前 epoch。
- `base_epoch_ref`：本地认为当前 effective 的 `ak.mls.commit` Control Move 或 `ak.mls.genesis` Control Move / genesis group state ref；epoch 由 effective commit 机械派生，协议不定义独立的 `ak.mls.epoch` seal event。
- `proposal_refs`：被该 Commit 消费的 `ak.mls.proposal` events；即使只有一个 proposal，也 MUST 使用长度为 1 的数组，生产者不得使用单数 `proposal_ref`。
- Add proposal 必须携 `target_authorization_incarnation`，逐字绑定要加入的 exact current Realm 或 Realm+Circle membership incarnation；非 Add proposal 禁带。消费该 Add 的 winning Commit 的 `next_epoch` 是该 incarnation 的唯一 `join_epoch`，不得用 wall clock 或服务本地接收顺序派生。
- `commit_bytes_b64`：未填充 base64url 编码的完整 RFC 9420 MLS Commit 消息，MUST 内联携带，使离线成员仅依赖 durable Event history 即可按序追上 epoch；只携带摘要不能满足 §6 的离线恢复义务。
- `commit_digest`：`commit_bytes_b64` 解码后字节的 SHA-256 摘要；接收方 MUST 在处理 Commit 前校验。
- `commit_message_ref`：可选的 content-addressed blob 引用，只用于归档、去重或传输优化；不得替代 `commit_bytes_b64`，也不得成为应用 winning Commit 的额外可用性依赖。
- `next_epoch`：必须等于 `base_epoch + 1`。
- `governance_binding`：见第 2.5 节。

同一 `(effective_scope, derived_group_id, base_epoch)` 上多个 effective `ak.mls.commit` 候选如果无法由 Lattice 合并，会产生 `⊥`，而不是并存的多个有效 epoch。客户端发现自己提交的 commit 未成为 effective state 后，必须以当前 Seal view 为 base 重新生成 Commit；原失败 commit 中未被消费且仍满足授权、membership、policy 和 freshness 的 proposal MAY 重新发布为 proposal，或被后续 Commit 重新引用，但不得自动视为已生效。

每个 group 的当前 epoch 由 effective `ak.mls.commit` Control Move 的 `next_epoch` 字段直接表达；projection seal 是 Lattice / snapshot 派生视图，不进入 wire history。

当网络分区导致节点短期看见不同 Seal leaf 时，客户端 MUST 把依赖未知或竞争 epoch 的加密事件标记为 `decryption_pending` / `state_mismatch`，直到 Seal view、backfill 或 snapshot-assisted verification 收敛。服务端不得通过本地接收顺序指定 MLS epoch；可选 designated committer / key service 只能由 Realm policy 授权为普通 actor 或 service capability，不能替代 CBA/Lattice 验证。

### 5.5 Commit / Welcome 处理失败报告

客户端本地处理 winning `ak.mls.commit`、`ak.mls.welcome` 或其 `governance_binding` 失败时，MAY 发布 `ak.mls.commit_failed` 诊断事件。该事件用于让管理员、key service 或发送方重新发 Welcome、重新提交 Commit 或调查 state mismatch；它不回滚 accepted commit，也不推进 epoch。

`ak.mls.commit_failed.payload` MUST 至少包含：

- `mls_group_id`
- `commit_ref`
- `epoch`
- `failure_stage`，例如 `welcome_decrypt`、`transcript_verify`、`governance_binding`、`group_state_update`、`keypackage_claim`、`security_frontier_mismatch`、`unsupported_cipher_suite`、`storage_failure`
- `reporter_device_id`
- `failed_at`

规则：

- 事件的 `actor_id` MUST 是报告失败的 principal 或其授权设备 / service actor；`reporter_device_id` 必须能从 principal control state 验证。
- `payload` MUST NOT 包含 MLS secret、明文、Welcome 明文、私钥、passphrase、完整 ratchet tree 或可用于离线攻击的调试 dump。
- `refs[]` SHOULD 包含失败的 `commit_ref`（`role="parent_event"` 或 `role="attestation"`）、相关 `ak.mls.welcome` 引用、当前 membership / policy frontier 或可验证 snapshot reference（`role="state_witness"`）。
- 收到该事件的客户端 MAY 将相关消息保持 `decryption_pending`，并提示重新同步；服务端或管理员 MAY 重发 Welcome 或提交修复 Commit Control Move，但必须重新走普通授权、Control Move precondition 和 Seal finalization。

### 5.6 Epoch 自保推进

Epoch 推进只由 MLS forward secrecy、message-count、membership/security-frontier 变化或部署固定运维上限触发。
Routing metadata 不得要求每小时 Commit。Exporter transition 在 accepted Event/Seal 后 MUST 先原子耐久保存 post-state、
该 epoch 的独立 history secret、group-state ref、counter marker，以及启用时同 Event 内的单一 RRK archive，才允许
下一 Commit 或 application send。Standard MLS 只保存 RFC 9420 active state，不生成 history secret/archive。


## 6. 离线支持与消息延迟到达
- 凭借 MLS 的 Ratchet Tree，即使某成员长时间离线，只要他没有被驱逐出群组，他上线后依然能通过同步全量的 `ak.mls.commit` 操作中强制内联的 `commit_bytes_b64` 按 accepted Seal 顺序跟上 Epoch 的演进，并解密积压在 Principal Server sync surface 中的加密事件。实现不得假设发送者仍在线，也不得把可选 `commit_message_ref` 对应 blob 的可用性作为恢复前提。
- 对于极端网络分区情况，客户端 SHOULD 保存尚未完全确认的前驱 Epoch 密钥状态，直到所有相关的历史 `encrypted_payload` 都已被成功拉取与解密。
- 这种前驱 Epoch 保留是有界的恢复缓存，不是为后加入成员历史共享而无限期保存先前 secret。客户端 MUST 对本地先前 epoch key 使用设备保护存储或明确授权的 key backup，并在 retention / legal hold / erasure policy 不再要求保留时销毁。

## 7. v1 集成要求

- KeyPackage 在 DID Document 或 Device / Key Server 中的映射 MUST 绑定 principal DID、device id、KeyPackage hash、supported cipher suites、created_at、expires_at、revocation status 和 device signature。客户端必须通过 DID 控制链和 device trust chain 验证后才能加密。
- 当 Audit Applet Binding 声明 `audit_assurance_class = "attested_hardware"`（profile = `ak.profile.attested_audit.e2ee.v1`）时，release service remote attestation MUST 绑定 measurement、service DID、`audit_service_actor_id`、policy version、audit purpose、operator DID、created_at 和 expiry。Attestation 只能证明受控输出路径和代码身份，不能绕过 `ak.audit.release`、notice 与 RYW receipt 要求。`ak.profile.disclosed_audit.e2ee.v1` 不得伪造或暗示存在 TEE attestation；client UI 必须按 [`audited-e2ee.md`](./audited-e2ee.md) 的两类提示区分展示，不得合并、省略关键限定词。
- Signal / Double Ratchet 私信互操作只能作为 profile-specific interop profile。该 profile 必须声明会话 identity binding、device verification、forward secrecy profile、history visibility 差异和互通边界；不得在 MLS Realm 内静默降级。

> **PQ 覆盖边界（informative，防误读）**：v1 的后量子覆盖分为三层：签名层（`ML-DSA-65`，[`../conformance/encoding.md` §6.1](../conformance/encoding.md)）与传输层（TLS `X25519MLKEM768`，[`../sync/federation.md` §3.2](../sync/federation.md)）已有 PQ 选项；应用层内容机密性由 MLS ciphersuite registry 与非-MLS HPKE suite registry 分别控制。读者 MUST NOT 把传输层 TLS PQ 误读为已覆盖 E2EE 正文：Harvest-Now-Decrypt-Later 攻击者收割的是落盘 / 转发的 E2EE 密文，其机密性取决于 MLS / HPKE 的 KEM 而非 TLS（TLS 只保护单次传输跳）。
>
> **非-MLS HPKE hybrid gate（informative）**：静态密文备份、to-device sealed material、member-application reviewer envelope 与 file-transfer key envelope 的 KEM agility 由 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 承载。该 registry 已登记 `ak.hpke_xwing_aead_chacha20poly1305.v1`（status=`reserved`，gate `ak.profile.kem.hybrid_xwing.v1`），用于 X-Wing（X25519+ML-KEM-768）hybrid KEM。reserved row 钉定 wire id、profile gate 与 activation requirements；在 row 翻为 active 且 conformance vectors 发布前，receiver 收到该 suite id MUST fail closed（`unsupported_hpke_suite`），不得自行组合 KEM/KDF/AEAD。
>
> **MLS 内容 KEM 边界（normative scoping）**：v1 core MLS active set 仍是 `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519`；本文件不定义 PQ-MLS negotiation 或 hybrid KeyPackage ciphersuite。MLS group KEM 的新增 suite 只能通过 `mls-ciphersuite-registry.json` 的 active row 与显式 profile gate 加法引入；未登记或 reserved 状态的 MLS suite MUST fail closed。与 HPKE registry 的 PQ 预注册纪律对齐，该 registry 已按 MLS WG `draft-ietf-mls-pq-ciphersuites-06` 登记 `MLS_128_MLKEM768X25519_AES128GCM_SHA256_Ed25519`（status=`reserved`，gate `ak.profile.kem.hybrid_xwing.v1`），并固定 KEM `0x647A`、KDF `0x0001`（HKDF-SHA256）、AEAD `0x0001`、SHA256 与 Ed25519 的 suite mapping。MLS 的 ratchet tree、key schedule 与 secret tree 使用两段式 Extract/Expand，而 `draft-ietf-hpke-pq` 未为 SHAKE 这类 single-stage KDF 定义这两个函数，因此 MLS KDF MUST 使用 HKDF 系列，MUST NOT 使用 HPKE PQ 的 SHAKE256 KDF `0x0011`。`draft-ietf-hpke-pq-05` / CFRG concrete-hybrid-kems 是 KEM 的主标准化路径；X-Wing individual draft 只作为同构造的补充参考。reserved row 在取得 IANA MLS code point、逐字节 conformance vectors 且全部 activation requirements 完成前不得出现在 wire 上，不改变本节 fail-closed 语义。
>
> **MLS 认证面 PQ 路线（normative scoping）**：上述 Ed25519 suite 只提供 post-quantum confidentiality，不提供 post-quantum authentication；实现 MUST NOT 宣称 full-PQ MLS。认证面不自行把 Arkret detached-JWS hybrid proof 拼进 MLS credential / LeafNode / KeyPackage。v1 registry 另以 `MLS_128_MLKEM768X25519_CHACHA20POLY1305_SHA384_MLDSA44` reserved row 跟踪 `draft-ietf-mls-pq-ciphersuites-06` 的 PQ/T hybrid KEM + ML-DSA-44 标准路线（KEM `0x647A`、KDF `0x0002`（HKDF-SHA384）、AEAD `0x0003`、SHA384 transcript hash），gate 为 `ak.profile.mls_ciphersuite.pq_auth.v1`。该 row 在 IANA code point、MLS credential / LeafNode / KeyPackage 签名逐字节向量、mixed-member unsupported-suite fail-closed 与新 negotiated contract release 全部就绪前不得激活或出现在 wire 上。后量子认证的优先级低于静态密文与 MLS KEM 的 HNDL 缓解，但它是显式跟踪的后续阶段，不得被误读为已由 `ak.profile.signature.pqc.v1` 自动覆盖。
