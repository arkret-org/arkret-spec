---
title: Station Federation and Authority Replication
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - authority-commit-log.md
  - service-http-binding.md
---

# Station 联邦与权威复制

规范关键字按[规范语言](../conformance/normative-language.md)解释。

Arkret v1 的每条 Realm、Circle 或 Sidecar stream 由其 current governance Station 唯一接纳 Event，并通过连续 RealmCommit
chain 提供完整性与顺序。每个 Realm 在某一 authority generation 只有一个 current governance Station。

**章节编号是稳定引用身份（normative）**：本页的编号小节都是正文，各自承载自己的完整义务。
编号是供其它领域页稳定引用的身份，不表达阅读顺序，MUST NOT 被理解为「只保留号、内容在别处」的占位别名。
引用本页某节即引用该节正文。

## 1. 信任边界

Peer request 使用 service-to-service authentication，绑定 source/destination service DID、operation、body digest、
created/expires 和 nonce。Transport authentication 只证明请求来源；Event producer proof、RealmCommit proof、authority
handoff proof 必须分别验证。

## 2. 设计原则

成员的 Account Station 可耐久排队 exact producer-signed Event，然后转发给已验证的 current governance Station。
转发方不得修改 Event、补签、先行 accepted 或向其它成员 fanout。只有 authority 签发的 RealmCommit
才能产生共享 finality。

## 3. 复制

复制单元是一条具体 Realm、Circle 或 Sidecar stream 中连续的 `(RealmCommit, Event)` 序列。调用方对
每条 stream 单独授权和分页，必须验证：

1. authority generation 与已验证的 genesis/handoff chain 一致；
2. position 从请求起点严格递增；
3. `previous_commit_ref` 只引用同 stream 的直接前驱；
4. Commit/Event ID 、治理签名和 producer proof 均有效；
5. response 不携带调用方不可见的其它 stream head。

消费 Station 可以投影和缓存 current state，但不能用本地重放产生另一种 accepted 判决。

旧 `peer/events/frontier` 与 `peer/seals/frontier` 两条路径不属于 v1 peer 读取面，
`/.well-known/arkret` MUST NOT 广告 `peer_events_frontier` 假能力。peer MUST NOT 把 SealBasis、
actor Event aggregate 或跨 stream 的聚合位置当作 RealmCommit head、复制权、visibility 或 readable floor。
补缺和恢复使用已登记的 `ak.peer.committed_event.read.scan.v1`，对每条获准 stream 分别验证
`stream_ref`、`stream_position`、Commit 链与可读边界；本文所说的 frontier probe 不定义旧聚合 API。

旧 `QUERY peer/events`、`QUERY peer/events/resolve` 与
`QUERY peer/events/sibling-positions` 也不属于 v1 peer 读取面。peer MUST NOT 通过跨 Realm／actor
query、仅凭 Event ID／digest 的 resolve，或 `actor_seq` sibling oracle 代替逐流复制和精确依赖验证。
Directory 首次 ingest 所需的依赖 MUST 以同一条获准 stream 中的 exact
`(event_id, commit_id, stream_ref, stream_position)` 及相符的 RealmCommit + Event 验证；
本规则不撤销已登记的 `ak.peer.events.command.submit.v1` 的 `POST peer/events`，也不放宽
其接纳、来源证明或可见性门禁。

### 3.2 服务签名验证

服务签名先于任何内层对象处理，但不替代 Event/Commit proof。

### 3.4 Peer policy

Peer allow/deny 只控制转发与复制入口，不能授予 governance authority。

## 4. 完整性与故障

消费方可以证明自己获准的某条 stream 从已知 head 到新 head 连续，但不能证明 authority 在接纳前
没有审查或扣留 Event。同一 `(realm, stream, generation, position)` 出现两个不同且有效的 authority
signature 是 equivocation evidence；消费方必须冻结该 stream 并进入人工审计，base v1 不自动选择 winner。

Authority 离线时可继续读已缓存字节，但整个 Realm 不能生成新 committed Event。

### 4.1 Event forwarding

Event forwarding 始终保留 exact producer bytes，并只将 current authority 的 Commit 视为 accepted。

**跨站 human 设备 producer（normative）**：transport 认证不证明 producer 设备授权，治理 Station 也没有 producer
account Station 的 PCR。因此 producer 是 human Account 设备且其 `account_id.station_id` 不是治理 Station 时，
`ak.peer.events.command.submit.v1` 的 `authority_forward` MUST 携带 `producer_device_evidence`，其它 producer
MUST NOT 携带；同站接纳读取本地 PCR，不携带证据。forwarding Station 在每次转发尝试前从自己 live gate 的同一
耐久 cut 现签完整 `account_device_signer_evidence`，先持久化对象与 ref 再发送，不复用缓存；设备已不可用时不转发。
治理 Station 在任何写入前核对已认证 `Source-Service-ID` 等于 `attestation.account_id.station_id`、对象自带
Service 历史在 `attested_at` 的 assertion method 与签名、attestation `expires_at`、原 `authorization_window`
同时覆盖 Event `created_at` 与当前时刻、`device_status=active`，以及 producer／proof fragment／签名 key 的逐字
绑定；任一失败零写入。exact 重复的 Event 先返回原 outcome 再检查证据时效；完整 evidence 与 ref 在接纳事务内
持久化，仅供审计，历史 replay 以 `RealmCommit` 与治理权威链为准。完整规则与错误码见
[`../crypto-media/device-lifecycle.md` §8.2.2](../crypto-media/device-lifecycle.md)，正负例由
[`ak.vector.federation.authority_forward_producer_device_evidence.v1`](../../artifacts/registry/vector-registry.json) 固定。

#### 4.1.1 Realm fanout 目标集合与持久 intent（normative）

首次接受本地 Actor 所签 Event 的 Station 是该 Event 实时 push 的唯一编排方；通过 peer 接收面收到该 Event 的 remote Station MUST 验证、持久化并服务其本地成员，但 MUST NOT 因该次 peer ingress 再创建第二轮实时 fanout。缺失副本通过 frontier probe、pull、backfill 或 snapshot 修复，不能靠接收方无界转广播。

对 Realm 共享 Event，发送方 MUST 从同一 accepted Realm view 取所有未撤销的 effective joined member ActorId，按 [`../models/common-fields.md`](../models/common-fields.md) §4.2 的封闭规则投影 routing service，排除本机并按 service `did_core_id` 去重。多个成员由同一 remote service 托管时只创建一份 Event transaction。bot、service、archive 或 search projection 若要持有 Realm Event，必须成为显式 joined ActorId，并受 membership、capability、E2EE 与 canonical payload／plaintext visibility 约束；已知 peer、allowlist、mirror、resolver 或部署拓扑都不自动取得内容。只有至少一个本机托管成员被授权取得该 Event 的**完整 canonical bytes** 时，其 remote Station 才进入 committed-replication target set。无权取得完整 Event 的成员不建立 canonical replica；授权读取面可返回 `CommittedEventView` 的 withheld 分支，但它不得进入 canonical Event store 或 reducer。E2EE ciphertext 的 canonical 持有权不自动授予 Station plaintext key 或本地 caller 明文读取权。

面向单个成员的 to-device、push、KeyPackage、邀请或其它 direct rail 只使用该成员 ActorId 投影出的 exact routing service，MUST NOT 扩张为 Realm fanout。发送方对目标集合中的每个 distinct service MUST 创建独立、持久的 outbox intent；本地 Event 的 accepted 状态、按 service DID 去重后的完整目标集合与全部 outbox intents MUST 在同一 durable transaction 中提交。任一写入失败时整个事务回滚。

目标暂时缺少 verified route **不得**拒绝已经通过 admission 的本地 Event，也不得返回 `service_unavailable` 来撤销本地 acceptance。该目标必须以 `pending_route` 状态原子写入；已有 verified route 但尚未收到 peer 成功响应的目标写为 `pending_delivery`。两种 pending 状态都必须跨重启恢复、按同一 idempotency key 重试，并在超过部署运维阈值后告警；只要冻结的接收 authority 仍有效，就不得因 TTL、尝试次数、dead-letter 上限、cache eviction 或进程重启静默终止义务。

每个 intent MUST 在**发送方本地 durable outbox metadata** 冻结 `target_service_id`，以及使它获得投递 authority 的非空 `fanout_authorization_basis` 集。每个 basis 是完整三元组 `(realm_id, member_id: ActorId, membership_event_ref)`，不是其中任意一个字段。每次真正发送前，发送方 MUST 在同一当前 accepted Realm view 中验证一个 basis 的全部条件同时成立：完整 ActorId 仍是 effective joined、其 effective membership Event ref 与冻结值逐字相等、`route(member_id)` 等于 intent 的冻结 target service，并且该 Event 的 scope、history、reference disclosure、canonical payload 与 plaintext policy 仍允许发送。只有至少一个完整 basis 通过全部条件，目标才仍有权接收；这是 tuple 内 AND、tuple 间 OR，MUST NOT 跨两个 basis 拼凑条件，也 MUST NOT 把恒定的 ActorId routing projection、可达 endpoint 或 service resolution 当成独立授权依据。全部 basis 失效时 intent MUST 原子进入 terminal `cancelled_authority_lost` 且绝不发送。

同一 service DID 的 endpoint/record 更新只刷新 transport route，MUST NOT 改变冻结 basis、target identity 或原幂等键。AccountId 的 Station 分量变化意味着另一完整 ActorId，不是旧 intent 的 route 更新；之后同一 principal 以新 AccountId、其它 ActorId 或新 membership Event 重新加入，只能影响新 intent，MUST NOT 复活或重定向旧 intent。多个 frozen members 共享同一 service 时，一个成员退出不影响其它仍完整有效的 basis。

durable outbox 必须使用 `ak.peer.events.command.submit.v1` 的 `committed_replication` 分支。每项只携完整 source
`EventAdmissionSubmission` 与 source-signed `RealmCommit`；`fanout_authorization_basis` 是发送方投递义务状态，
**不得进入 peer body**。接收方只从 authenticated source/destination、source Event／Commit、已验证 committed
membership history 与 typed current projection重新验证 commit/event/ref、source authority generation、连续性、
本机托管成员资格与 history/reference/plaintext visibility；sender claim 不能成为授权事实。所需 membership、
authority chain、predecessor 或 history floor 缺失时 MUST `dependency_missing` 并零写该项。唯一 bootstrap 例外是
本项本身就是本机托管成员的有效 join Event：接收方可在验证 source Commit 与前缀后做无副作用 reducer 预演，
并将 Event、Commit 与派生 membership 原子持久化；需要多 Event 的 bootstrap 仍使用 registered atomic unit。
接收方只保存 exact source bytes，**不得**重做首次 admission、重签 `RealmCommit` 或创建第二轮 fanout。

同一 request 的 `replications[]` 内 source coordinates 必须唯一；同一 stream 的项按 `stream_position` 严格升序，
receiver 按数组顺序验证。重复 coordinates 或同 stream 乱序在处理任何项前拒绝整个 request；不同 stream 的
连续性与失败互不回滚。只有经过 transport 认证、schema 校验和本轮授权求值后，对应数组位置在同序
`replication_outcomes[]` 中得到 `status="stored"|"duplicate"`，source 才能把该 Event / destination intent 置为 terminal
`delivered`。`rejected` 保持 pending 或按 reason 的确定性策略终止；HTTP 2xx、顶层 branch、写入 socket、
`sent_at`、attempt count、batch receipt 都不是逐项 delivery evidence。此处没有顶层
`accepted[]`／`duplicate[]`，也不得把 replica persistence 称为新的 accepted finality。`pending_route`、
`pending_delivery`、`delivered`、`cancelled_authority_lost` 是 Realm Event fanout 的封闭 target 状态；其中前两者
计入 pending，后两者不再欠投递。本地 canonical acceptance 不表示所有 remote target 已交付；source 当前没有
未结 fanout intent 也不表示 destination 当前仍持有 Event 或 Realm 历史完整。

`replication_outcomes[]` 与输入等长、同序，数组位置已经唯一关联输入项；每行只携
`status`，拒绝时再携 `reason_code`。`index`、`committed_ref`、destination 或其它 request echo 都不增加验证或
幂等能力，MUST NOT 出现。结果不确定时重放逐字节相同的完整 body；不得删除已 stored 项构造 partial retry。

target 状态的读取面 MUST 不泄露成员拓扑：未知 Event 与不可见 Event 使用同一 `not_found`，且只有调用者按当前 Realm membership / history / plaintext visibility 规则可读取产生该 target 的 joined-member ActorId routing projection 时，对应 row 才可携带 service 身份。

### 4.5 Stream replication

复制请求一次只覆盖一条获准 stream。

#### 4.5.1 查询抗枚举

未知、未授权、隐藏 stream 和超出 retention 的起点使用统一最小披露失败。

#### 4.5.3 有界分页

每页同时受 item count 和 canonical byte 上限约束，cursor 绑定 exact stream 与 caller。

## 5. Authority discovery 与 handoff

Invite、Directory、DID route 和缓存 endpoint 只提供 locator candidate。治理身份由 Realm genesis 和连续的 old→new
双签 handoff chain 证明。

计划 handoff 前，new Station 必须导入 typed snapshot、所有 stream heads/tails、idempotency index、outbox 和公开
MLS state。Handoff transition 绑定私有 full-stream-head manifest digest，但公开 bundle 只暴露 Realm stream head。
旧方在 cut 后永久拒写，新方从每条 stream 的各自直接后继位置开始。

没有完成 handoff 且旧方永久丢失时，同一 Realm 不允许自动选主或备份 takeover；只能保持可验证只读，
或创建新 successor Realm。

### 5.0 Authority locator

Locator 是候选网络位置，不是 authority proof。

### 5.3 Authority bundle

Bundle 从 genesis 起返回连续 generation chain 和 current Station。

#### 5.3.1 有界加入引导（normative）

Invite 和 Directory 只携带 locator candidate；客户端必须自行请求并验证 nonce-bound bundle。

## 6. 隐私

Circle 和 Sidecar 使用独立 stream，Realm 成员身份不自动授权这些 stream。复制 API 不返回隐藏
stream 的存在、head、position 或 timing 差异。治理 Station 仍可见全部 scope metadata；这是单 authority 模型的明确信任代价。

### 6.3 DID route privacy

DID route 更新不得泄露隐藏 stream inventory，也不得取代已签 handoff。

## 8. 失败归一化

### 8.5 Failure normalization

错误响应必须避免区分 hidden/nonexistent/unauthorized Realm、Circle 或 Sidecar。
