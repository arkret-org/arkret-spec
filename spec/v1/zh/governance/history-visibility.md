---
title: History Access and Recovery
status: candidate
normative: true
stability: v1
updated: 2026-08-20
see_also:
  - ../crypto-media/encryption-and-audit.md
  - ../crypto-media/device-lifecycle.md
  - ../sync/client-sync.md
  - ../sync/service-http-binding.md
---

## 0. 规范语言

本文中的规范关键字按 [`normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 唯一历史 policy

每个 Realm 和 Circle 都是独立的 effective scope，并在任一 accepted view 中 MUST 恰有一个 current 值：

```text
history_access = since_join | all_history_for_current_members
```

scope create 必须初始化该唯一治理 cell。它是单向安全 ratchet：唯一合法更新是
`all_history_for_current_members → since_join`；重复 `since_join` 可作为幂等 duplicate/no-op，任何
`since_join → all_history_for_current_members` 或其它写入都必须在 schema/reducer admission 永久拒绝。它是非公开 Event projection 的
唯一历史 range policy；对 `content_scheme=mls_exporter_aead_v1` 的 scope，它也是 history-secret delivery 的唯一 range policy。
Realm 和 Circle 互不继承；创建 UI 可复制父 Realm 当时值，accepted 后即为 Circle 自己的 cell。

`history_access` 不决定 discoverability、invite preview、public content、redaction 或 retention。
Public content 由显式 public schema/projection 授权；invite 只能发放有界 preview；需要密码学
隔离的 role/admin/restricted 正文 MUST 使用独立 MLS-backed Circle。已获得的 secret
不能被后续 policy、remove、redaction 或 retention 撤回。

## 2. 可选 MLS group 与 closed union

未选 MLS 的 Realm/Circle MUST NOT 生成 `mls_group_id`、epoch、leaf、snapshot、Welcome、counter、
history secret、history delivery、MLS backup 或 RHRK archive。每个 MLS-backed Realm/Circle 有完全独立
的 group、epoch、leaf、counter 和 history store，不得回退到父 Realm。

Circle 创建对象 MUST 满足：

| profile | `encryption_profile` | `content_scheme` | `mls_group_id` |
| --- | --- | --- | --- |
| plaintext | `none` | absent | absent |
| standard MLS | `mls_rfc9420` | `mls_rfc9420` | derived |
| exporter MLS | `mls_rfc9420` | `mls_exporter_aead_v1` | derived |

MLS-backed Realm 也 MUST 在 Genesis 显式提供并冻结 `content_scheme`；
`encryption_profile=none|external` 时该字段和 Arkret MLS group 均 absent。Actor 不得提交
`mls_group_id`；reducer 按下式派生：

```text
canonical_effective_scope_key_bytes(Realm(r))  = utf8(canonical RealmId r)
canonical_effective_scope_key_bytes(Circle(c)) = utf8(canonical CircleId c)
mls_group_id = base64url_no_pad(canonical_effective_scope_key_bytes(effective_scope))
```

`mls_rfc9420` scope MUST 固定 `history_access=since_join`，且不得进入 history request、backup 或
RHRK archive。仅 exporter scope 可进入这三条路径。Sidecar 保持现有 standard MLS profile，v1
不为 Sidecar 定义可交付 history secret。

## 3. Incarnation 与 endpoint floor

`join_activation(principal, scope)` 是当前 membership incarnation 从 non-active 转为 active 的 winning
membership Event 及 accepted activation Seal。MLS-backed scope 的 `ak.mls.proposal{proposal_type=add}` MUST
把完整 `target_actor_id: ActorId + target_authorization_incarnation` 逐字绑定到该 exact winning Realm incarnation；endpoint
identity只从完整 RFC 9420 Add/KeyPackage的 signed Leaf取得，不重复携 `target_device_id`。Circle Add 则同时绑定
parent-Realm 与 Circle incarnation。消费该 Add 的 winning Commit 的 `next_epoch` 是该 incarnation 唯一的
`join_epoch`。非 Add proposal 禁带该字段；实现不得按本地 `received_at`、`joined_at` 或当前最新 epoch 猜测。
v1 Genesis 只允许一个初始 principal leaf，即 Genesis Event 的 `actor_id`（creator）；creator device 由唯一 producer
proof 的 `verification_method` fragment 投影。完整 replay 同时证明该 creator 的 exact founding membership incarnation
与 winning Genesis Event 后，才得到 `join_epoch=0`。`mls_genesis_payload` 不携带
`initial_keypackage_refs` 或另一份 initial-member 清单；任何非 creator principal（包括创建时就计划加入的成员）都必须经后续
winning Add/Commit/Welcome 得到自己的 `join_epoch`，不得从 KeyPackage blob、ratchet tree 或实现私有元数据猜测 epoch 0。
已 active principal 的设备变化不改变 principal incarnation/join epoch；remove 后 rejoin 产生新值。

Standard MLS 对每个认证 endpoint 维护 `endpoint_admission`：从该 endpoint incarnation 的 initial
winning Add/Welcome activation 开始，以 Remove 结束。保持同一 BasicCredential identity 和
signature key 的 ordinary self-update MUST NOT 重置；Remove+Add、credential/signature-key replacement
或 reinstall 建立新 incarnation 并重置。Exporter response MUST NOT 套用 endpoint floor。

Minimal-metadata 的服务端授权主体是 Realm-local pairwise endpoint actor。每个
`(Realm, endpoint incarnation)` MUST 生成唯一 pairwise did:key `ActorId` 和 signing key；同一
Realm 不同 endpoint 不得复用，同一 endpoint 可在该 Realm 及其 Circles 中复用。Event actor、
Leaf BasicCredential identity、proof key、sender KDF/counter domain 和 request sender domain MUST
逐字节相同。服务端 MUST NOT 将其聚合为真实 principal/device。该 profile 不承诺 Realm
内 endpoint、request range 或 timing 不可关联。

Pairwise identity 的生命周期是 Realm-global endpoint incarnation。v1 不定义独立的 replacement operation、
old-to-new actor mapping 或跨 group 原子事务：旧 actor 的 Realm membership 被 winning leave/remove 终结时，其在该
Realm 及全部 Circle 中的 authorization 同时失效，Circle-local actor rotation MUST 拒绝。新 endpoint incarnation
必须生成新的 pairwise actor，并按普通 Realm join 取得成员资格；各 MLS group 只使用现有 Remove/Add 独立收敛。
Realm rejoin 或新 actor 的 Realm Add 不自动恢复任一 Circle 的旧 leaf，也不自动加入 Circle；仍需该 Circle 的显式
reactivation 和 winning Add。实现不得因某个 group 尚未完成 Remove 而继续授权旧 actor，也不得把多个 group 的
MLS transaction 包装成新的 Realm-level replacement transaction。

## 4. Current ratchet、join floor 与 T2

```text
allow_event(all_history_for_current_members, E, join) = true
allow_event(since_join, E, join) = T0(E) causally covers exact join
allow_epoch(all_history_for_current_members, N, join_epoch) = true
allow_epoch(since_join, N, join_epoch) = N >= join_epoch
```

```text
readable_by_scope(E, recipient) =
  allow_event(current_history_access, E, recipient.current_join_activation)
  AND recipient authorization subject is currently active
  AND scope is readable and not tombstoned

readable_standard_mls(E, endpoint) =
  readable_by_scope(E, endpoint.authorization_subject)
  AND T0(E) causally covers endpoint.current_endpoint_admission

deliverable(N, recipient) =
  allow_epoch(current_history_access, N, recipient.current_join_epoch)
  AND current membership/device/account/source/scope/safety/audit gates pass
```

上述 `allow_event` 只裁剪历史 Event/body 与旧 revision，不裁剪 active member 使用当前 Realm 所必需的
**current object/control projection baseline**。对每个当前 active membership，服务 MUST 以同一 accepted
frontier 提供：验证当前 read/write authorization 所需的 effective singleton/control closure、Realm 当前
`default_strand_id`，以及该指针所指向 non-tombstoned Strand 的最小当前投影。该投影 MAY 由已验证 snapshot
或 current-state proof 提供，即使建立它的 Event 位于 join frontier 之前；它 MUST NOT 因此泄露加入前 Message
timeline、旧治理 revision、旧 Strand metadata revision 或历史密钥。`default_strand_id=null` 仍必须作为明确
当前值表达，不能用“字段缺失”同时表示未知与未设置。

`ProjectionStrandRow.is_default` 对每个返回行都是 required current-derived boolean，且必须逐行满足
`is_default == (strand_id == Realm.default_strand_id)`。当默认指针非 null 时，Strand 列表的 current baseline
MUST 包含恰好一条 `is_default=true` 的对应 non-tombstoned 行；Realm pointer 与 Strand row 必须来自同一
frontier。服务不能以 `since_join` 为由同时隐藏两条默认入口发现路径。

由于 ratchet 永不放宽，current policy 本身就是历史最窄值，不需要 event/epoch ceiling、activation-policy witness 或 policy meet。
direct Seal replay 仍验证 winning MLS transition、epoch continuity、requester incarnation 与 join floor，但不在 activation Seal 采样
history policy。MLS Genesis 只校验 content scheme 与 initial policy 兼容，不复制或选择 `history_access`；后续 Commit 和 MLS security frontier
也不绑定该 cell。T1 使用 current ratchet 值与 current membership/device/account/source/scope gates。T2 是已交付、已备份或已由 RHRK 解出的
不可撤回能力；因此收紧只禁止未来读取/交付，不宣称回收既有能力。

Circle current gate 同时要求 Circle 和父 Realm membership active。父 Realm 成员失效后，
MLS-backed Circle 停止发送直到自身 Remove Commit 生效；plaintext Circle 立即按
`active Circle members ∩ active Realm members` 收紧 read/write，不生成伪 Commit。
该失效同时终结 current effective Circle membership incarnation。后来父 Realm rejoin 不得复活旧 Circle row 或旧 leaf；
重新进入必须由因果覆盖新 Realm join 的显式 Circle membership reactivation 建立新 incarnation，MLS-backed Circle 还必须
在自身独立 group 的 winning Commit 中 Add 该 endpoint。

## 5. Exporter secret 与 proof

```text
history_secret[N] = MLS-Exporter(
  "ak.history-v1",
  canonical_effective_scope_key_bytes(effective_scope),
  KDF.Nh
)
```

每个 epoch secret 独立；MUST NOT 互相派生。本机从已经完整验证并实际应用的 MLS epoch state 直接导出的 secret 标为
`local_authoritative`。通过 history response、RHRK archive 或任何其它外部 carrier 收到的 secret 永远只是 `candidate`；v1 不存在
远端 epoch promotion 或“首个成功候选”语义。AEAD 成功只建立 exact Event attribution，不能把 candidate
升级为该 epoch 的唯一真相，也不能淘汰其它 candidate。

`ak.self.seals.read.mls_governance_proof.v1` 的无状态 query 只保留近端 `group_security_frontier`：它投影 frontier registry 登记的
cell singleton/prefix ranges，并为每个 range 携连续 leaf indices、左右 boundary inclusion/nonmembership 或 state-edge witness；空 range
也必须有相邻边界证明，不能把省略当 Bottom。query 的 Seal 坐标都是 canonical `seal_basis.leaves[]` antichain：`proof_target_basis`
必须支配 `proof_base_basis`，即每个 base leaf 仍是 target leaf 或是某 target leaf 的 ancestor；open_set 不得缩成单一 head。

批量/旧 epoch 历史不得使用独立 stateless activation-range page、proof package 或第二套 witness wire。Request receipt 只冻结 closed
`HistoryGovernanceTraversalIntent`：profile、scope/group、caller 签名并已独立验证的完整 `trusted_history_base_basis`、独立
`trusted_current_basis` anti-rollback frontier、release service 当次 verified durable view 的完整 `target_basis`、canonical ranges、
incarnation 或 RHRK tuple、registry digests 与 retention。`traversal_intent_digest = SHA-256(UTF8("ak.history-governance-traversal-intent-v1")
||0x00||JCS(traversal_intent))`。服务不得替换 caller 的 base/current、缩成单一 head 或在 retry 中换 target。

v1 member history recovery 的 `trusted_history_base_basis` 必须是 caller 独立验证、T3 crash-safe durable pin 的完整 predecessor-free Realm
bootstrap cut；它不是服务自报的“全局唯一 Genesis Seal”，但不能使用缺少 pre-base provenance/joined-state 的 later checkpoint 冒充。
从每个 target leaf 反向沿 signed `predecessor_refs[]` 遍历，只能在 exact base leaf 终止；每个区间 Seal 的每个 direct predecessor 必须仍在
区间或恰为 base leaf，每个 base leaf 至少被一条 target 路径消费，且 target 必须支配 trusted current 的每个 leaf。隐藏 predecessor、无法从
base 到达的并发 branch、missing object 或 fork-quarantine 均 fail closed。

客户端/服务使用 SQLite 或等价 disk-backed work queue+visited set，从 target 反向发现完整 cut，再按拓扑 base→target 运行标准 `apply_seal`。
direct traversal 只消费 Seal 与其 `delta[]` 唯一发现的 Control Move；普通 Message/reaction 等 DataEvent 的 digest 不得进入 `delta[]`，也不因
某个 Seal 的 optional data observation root 出现它而取得控制面 finality。resolve 必须返回该 accepted Seal 在 acceptance 时实际 pin 的
exact canonical Control Move bytes，并同时提供 registered `apply_seal` 所需的 historical signer evidence、AvailabilityReceipt 及其它 CBS
依赖。每个 Seal 的 notary、predecessor、delta、control_event_set_root、completeness_root、state_root、frozen-predecessor admission、
Bottom/recovery 与 joined state 都按核心规则重算。

Seal 的 `notary_signature` 只使用其 predecessor joined governance state 中 `ak.component.notary.v1` cell 冻结的 signer descriptor 验证；
包含 `ak.realm.notary` rotation Move 的 Seal 仍用旧 descriptor，只有 accepted 后继才使用新 descriptor。Genesis Seal 仅从其完整 Realm
anchor unit 的 create notary descriptor 取得 founding key。verification method 虽可使用 DID URL 命名，verifier 也不得查询 current DID
document、当前同名 method 的 key bytes 或本地 latest notary row 来替换上述历史 descriptor。Control Move/Event proof 所需的历史 signer
evidence 同样按其 content-addressed acceptance pin 解析，不得由 current resolver 补造。

同一 `event_id` / `event_digest` 后来出现两个不同 digest-preimage canonical bytes 时，direct traversal 的“不得任选 variant”只禁止歧义
解析与追溯替换，不表示追溯撤销整个 Realm：若 resolve 对一个 selector 返回多份未经 acceptance pin 区分的 variant、返回的 bytes 不等于
该 Seal 当时 pin 的 bytes，或已丢失该 pin，当前 traversal MUST fail closed，且不得 first-row-wins。此前 accepted Seal 及其后继不得因此
回滚或重算；最初 receiver 必须按 [`event-auth-state-resolution.md` §6.3.2–§6.3.3](../authz/event-auth-state-resolution.md)
保留该 Seal 实际应用的 canonical bytes 与确定性 reducer 输出，拒绝 later-arriving variant 进入普通状态，并由显式按 canonical bytes 指认的
fork-resolution/recovery 归一。没有 acceptance-time bytes/output pin 的新 verifier 把该覆盖区间视为不可验证；它不能用任一当前可取得的 variant
重建旧 `state_root`。内存只需当前对象与有界队列 buffer；visited/work state 可 durable 恢复。

Replay 解释器只由 Realm 冻结的 profile id 选择；profile 的规范语义与 conformance vectors 随实现发布，不作为可寻址运行时工件进入 replay 输入。验签、Event identity 与转发均以收到并持久化的 canonical raw bytes 为准，typed view 只用于已知字段的语义解释，不得通过重序列化改变对象身份。实现不支持该 profile 时只对目标 Realm 返回 `unsupported_profile`，不得降级为权限错误或扩大到连接、账户和其他 Realm。

winning MLS transition、requester join/incarnation 和 scope 当前单向收紧的 history access 均由这次 replay 派生；同一 Move 被多个并发 Seal 覆盖不产生可选的
singular activation Seal。普通 Message/reaction 等 DataEvent 只携既有 accepted `seal_ref` authorization view，不携 `seal_basis`、不进入 Seal.delta、不推进 epoch。
T1 release 不进入 governance proof query；它由 chunk 首次耐久入队事务生成 `HistoryReleaseAttestation`。旧
`HistoryGovernanceEvidenceChain`、page/root/ownership/selection/activation/auth witness、`epoch_activation_range`、
`complete_control_state_v1` 与 proof result/snapshot carrier 均不存在。

## 6. Private history-key delivery

Public Event timeline MUST NOT 承载 history request/response/withholding。唯一 carrier 是 scope-private
durable request delivery 和 capability-addressed per-request response stream：

```text
ak.history_key.request
ak.history_key.request_receipt
ak.history_key.response_manifest
ak.history_key.response_chunk
```

wire object identity 只有 `ak:history_request:<uuidv7>` 与 `ak:history_response:<uuidv7>`，不得互换或用 EventId 代替。
每个 request 恰有一个服务内部 `(request_id, sequence)` response stream；该 stream 没有第二个 wire id。Request
是 immutable/idempotent；create 只能在 request、receipt、sealed capability 与 fanout bytes 已耐久保存后返回 accepted。
Request delivery 仅对 scope current active member endpoint 和与目标 archive 相交的 RHRK holder 窄分支可见。
Service 不选 source、不解密、不把 minimal actor 聚合到真实 route。

`request_id` 与 `response_id` 各自全局唯一。同一 `response_id` 在另一 request response stream 重用仍是
`duplicate_conflict`；`(request_id,sequence)` 只用于服务内部流顺序，绝不构成第二 identity namespace。

Release service 在首次接受非重复 request 时 MUST 从系统 CSPRNG 生成恰 32 bytes，编码为 canonical unpadded
base64url `response_capability_b64u`，并计算
`Digest(domain="ak.history-response-capability-commitment-v1", preimage=JCS({response_capability_b64u}))`。
服务 MUST 在任何 durable write 前以 commitment 唯一索引检查碰撞并透明重采样，只耐久保存
`response_capability_commitment` 与 sealed bytes，MUST NOT 保存 capability 明文。Capability 使用 request HPKE key
独立封装；exact create retry MUST 返回 byte-identical request、receipt 与 sealed capability bytes。

读取与确认只使用 `POST /_arkret/self/history-key-responses/read` 和
`POST /_arkret/self/history-key-responses/ack`，并呈递
`Authorization: Arkret-History-Capability <response_capability_b64u>`。Path、query 与 body 均不得携带 request locator；
服务从呈递值重算 commitment 并通过唯一索引定位 request/stream。缺失或错误 scheme、非 canonical shape、unknown、
expired、已 GC 与 unauthorized 均返回同一 `not_found` wire shape；合法 shape 的 miss 仍执行固定 digest、dummy row material
与 constant-time byte comparison。Capability、commitment 不得进入日志 key、trace 或 metrics label。

Request MUST 签入 `requester_author_profile`、与该 profile 逐字匹配的 closed
`requester_endpoint_authorization`、exact current `requester_authorization_incarnation`、requester 已完整验证并 durable pin 的
canonical `trusted_history_base_basis.leaves[]` 以及独立的 canonical `trusted_current_basis.leaves[]`。前者是历史 DAG 重放的显式首 trust
cut，并且必须是完整 predecessor-free Realm bootstrap cut；accepted traversal intent 的 base 必须与其逐字相等。后者是 scope Realm 的 current anti-rollback frontier，Account/PCR/Agent
T1 facts 不进入它，
open_set 也不得只签一条 leaf。Release service 只能接受一个完整 target basis 支配该 trusted basis 的 request；无法证明支配、bootstrap
base 不可验证或 target 存在并发未纳入 leaf 时，create 零写失败。`requester_authorization_incarnation`
是 closed scope union：Realm 为 exact `realm_membership_incarnation_ref`；Circle 同时携 exact parent-Realm 与 Circle membership
incarnation refs。Circle reactivation/Add 必须因果覆盖该 parent incarnation，join epoch 只取 Circle 独立 group 内的显式 Add
activation；禁止跨 Realm/Circle group epoch 取最大值。Request retry 必须保留原 trusted basis 及其本地 verification material，不能只保存裸 ID。
`ordinary_human` endpoint 分支签入 exact `requester_device_id`、accepted `requester_device_authorize_event_id`
与 PCR-local monotonic `requester_device_generation_ref`；`agent` 分支签入 exact Agent id、runtime verification
method 与 `requester_agent_key_authorize_event_id`；`minimal_metadata` 分支不得携 principal/device locator。Create 与每个
chunk 首次入队 T1 都重新解析同一签名 locator 并与 current Account/PCR/Agent authority 逐字比较，禁止从当前 session、proof
fragment 或服务私有“默认设备”替换。

Request create 返回成功前，release service 必须冻结并完整验证 request-expiring `HistoryGovernanceTraversalIntent`，在 receipt 的
`history_traversal_retention` 中保存 intent 与 registered digest。`intent.retention.expires_at == request.expires_at == receipt.expires_at == response stream expiry`
必须逐字相等，否则同事务零写失败。服务到 expiry 保留 exact target→base accepted Seal cut、每个 Seal.delta 命中的 canonical Control Move bytes
以及所有 registered `apply_seal` dependency；split-view 仍由既有 transparency/gossip 处理。object 丢失显式返回 `frontier_unavailable`
（reason=`history_traversal_anchor_unreachable`）并要求新 request，不得在旧 receipt 下换 base/current/target/range。

每个 Manifest descriptor 只列 `chunk_response_id,chunk_index,covered_epoch_range`。requester 凭 session/capability 及 exact
`request_receipt_digest`，通过标准 self Seal/Event/dependency resolve 携 closed `TraversalAccess` 读取该 receipt target 反向 cut 内的 Seal、其 delta
Control Move 及 registered replay dependencies。remote member source 只走普通 authenticated Realm/federation 治理可见性；request replica 只证明请求/receipt bytes、authorization 与 TTL，不承诺 cut 且不扩张治理可见性。仅 RHRK pending archive replica 可用 `pending_archive_replica_digest` 取得 peer retained-cut 窄访问。caller 不得自报 allowed ref 数组；服务从 retained intent/cut 机械判定。普通 timeline visibility 与
TraversalAccess 互斥，unknown/unauthorized/out-of-cut 同形。旧 evidence-page read operation 与 descriptor-access branch 均不存在。

Request create 时 requester authenticated AccountId 的 `station_id` 是该 request response stream 唯一 `release_id`。Request
receipt、sealed capability context 与 response stream 都冻结 exact AccountId、该 service DID、resolution refs 和 route digest；后续 retry 或路由变化
不得替换。固定 service DID 是该 request 的唯一 release authority；chunk 首次入队时仍必须确认 receipt 的 exact AccountId
未变。同一 DID 的 ServiceResolution successor 允许成为新 route；请求若改用另一 AccountId 或另一 service DID则
fail closed 并由 requester 创建新 request；已经 accepted 的小型 `HistoryKeyResponseSendReceipt`
仍由旧 idempotency ledger 保留并 byte-identical retry 到 expiry；recipient response stream 的完整 record 则在有效 high-water ack
事务中 GC。v1 不迁移 response stream/idempotency ledger。Release service 通过
`ak.peer.history_key_requests.command.replicate.v1` 把 byte-identical request+receipt 私有 fanout 到 closed destinations：current member
ActorId routing services，或其 archive tuple 与 requested ranges 相交的 exact RHRK holder service。Destination authorization/TTL/idempotency
受 S2S proof 覆盖；destination 只在本地 scope-private
request 投影，不生成 Event 或 DeviceMessage。Create 事务必须先 durable 写入 initial target set 与 fanout outbox；重启从 outbox 重放，
TTL 内 membership/service-binding 变化由 durable reconciliation 增加当前合法 target 并使失权 target 的 list gate 立即失效，不能因
create accepted 后的崩溃永久漏掉远端 source。

Source 仍调用自己 local PS 的 self send；local PS 先验 source current account/device、Agent、minimal membership 或 RHRK holder
authority，再签 `SourceRelayAttestation`，绑定 source-record digest、request/receipt、source current authority locator 和冻结的
destination release service，经 `ak.peer.history_key_responses.command.relay.v1` 私有投递。Destination 必须证明 relay service 等于
source 当前 delivery/authority binding，随后才执行 recipient/current scope T1 并签最终 attestation。该双服务 cut 不声称全局原子；
v1 依赖诚实 service、短 TTL 和 exact durable retry，恶意/延迟 peer 不在密码学保证内。Local source service 第一次验证 self send
时即以 `(response_id,source_record_digest)` 原子保存 byte-identical relay envelope/outbox；`relayed_at` 与 proof 不得在 retry 或重启时
重生成。最终首次 accepted 的小型 send receipt 耐久回填同一 row，client exact retry 返回原 bytes；transport 不另签 duplicate
variant，同 response_id 异 digest 为永久冲突。

Agent authority locator 逐字为
`{agent_id, verification_method, agent_key_authorize_event_id, active_lifecycle_event_id, control_basis, agent_signer_evidence_digest, observed_at, expires_at}`；
其中 `observed_at` 为 lease.issued_at、gate.issued_at、binding.issued_at、authorization.accepted_at 与 not_before 的最大值；`expires_at` 为 lease、gate、binding 与 authorization 已声明 expires_at 的最小值。该共同窗口必须非空，恢复或刷新不得扩大各来源独立期限。
其中 `control_basis` 是完整 accepted PCR Seal antichain，`agent_signer_evidence_digest = SHA-256(JCS(complete current AgentSignerEvidence))`。
不得退化为 singular control Seal、含糊的 control/evidence Event ref 或未定义 digest。RHRK source locator 内联完整
`RhrkHolderAuthorityObservation`，而不是裸 observation digest；该 object 分别绑定 `method_controller_principal_id`、`holder_service_id`、current signing method、accepted key evidence Event、
archive tuple digest、完整 holder trusted basis 与有效期。外层 `SourceRelayAttestation.service_proof` 已签完整 locator，所以 observation 不再嵌套第二份 proof。
接收端必须把 observation 与 source actor/service、外层 proof method/expiry 及 exact archive tuple 逐字交叉核对。
其中 immutable archive tuple 只通过 `method_controller_principal_id`、`holder_service_id` 与 `archive_authorization_tuple_digest` 逐字绑定；`current_holder_signing_ref`、
`accepted_key_evidence_ref` 和 `holder_trusted_basis` 证明 current holder authority，不得被错误要求等于 archive 创建时冻结的历史 signing/evidence coordinates。

Source 先分配全部 chunk response ids，再冻结 descriptors
`{chunk_response_id,chunk_index,covered_epoch_range}`。每个 chunk 恰覆盖一条连续 inclusive epoch range，且该 range 是 request 已授权 ranges 的
canonical subset；manifest 不枚举 proof bytes 或 `CbsProofBundle`，也不得用一个 descriptor 代表离散 range。
Manifest 不得承诺 chunk
ciphertext、enc、最终 size 或 release proof。每个 chunk 使用 request 中的同一 recipient public key 但独立 HPKE
encapsulation。唯一 info/AAD context 是下面的 canonical bytes；发送方必须把同一份 bytes 同时作为 RFC 9180
`SetupBaseS` 的 `info` 与单次 AEAD `Seal` 的 `aad`，接收方必须把同一份 bytes 同时作为 `SetupBaseR` 的
`info` 与 `Open` 的 `aad`。不得把空值、仅 purpose、额外 wrapper 或两次独立序列化的不同 bytes 分别传入：

```text
history_chunk_context = JCS({
  purpose: "history_secret_chunk",
  manifest_admission_digest,
  chunk_response_id,
  chunk_index,
  source_actor_id,
  source_sender_domain
})
```

request、receipt、manifest、effective scope、authorized ranges 与 expiry 已由 `manifest_admission_digest` 闭包承诺，不得重复进入
context。recipient public key 来自已签 request 而不是 transport route，仅用于 HPKE `SetupBaseS`，不是 context 成员。manifest descriptor 只绑定 `chunk_response_id,chunk_index,covered_epoch_range`；
不存在 selection digest、range key 或 page root。sealed chunk wire 仅携
`{kind,manifest_digest,manifest_admission_digest,chunk_index,enc,ciphertext}`，不得重复 range。Manifest 首次
admission 必须从 receipt target 按 predecessor_refs 反向取得完整 closed cut 和 registered dependencies，再从 base basis 按拓扑 `apply_seal`
重放到 target basis，执行 join/profile floor、scope current monotone history-access ratchet 与 winning transition 校验；任一失败时整个 manifest 零 record、
零 admission。成功事务耐久写 `HistoryManifestAdmission`，其 digest 绑定 manifest/request/receipt、exact `traversal_intent_digest`、
authorized ranges 和 T0 pass marker。Source 必须先取得该首次 accepted manifest receipt；在此之前提交 chunk 或提交错误
admission digest 必须 dependency reject 且零 pending、零 response record、零 attestation。
Receiver 必须先 durable 取得并验证 manifest。Receiver 安装前必须独立执行同一 target→base 遍历与 base→target replay，核对 winner、
join/incarnation、current monotone history-access ratchet 及 request/receipt/attestation 绑定。RHRK archive 使用 archive-lifetime traversal profile，不伪造 recipient。Source 不生成、
不签名也不携带 T1 authorization basis。Source proof 对 exact request/ranges/content 归因。`history_response_signing_input` 必须携带
`source_signer_evidence_ref`，其内嵌 digest 逐字绑定 closed source-signer evidence union 的同一份对象，且是该 digest 的唯一
wire 表示（[`../conformance/encoding.md` §4.0.1](../conformance/encoding.md)）：
ordinary human、Agent 与 organization-recovery holder 使用 `AuthenticatedSignerResolutionEvidence`，minimal-metadata 使用
`MinimalMetadataMlsLeafSignerEvidence`。Evidence 必须授权 `source_actor_id`、`source_proof.verification_method` 与
`source_proof.created_at`。

普通 human 设备使用封闭 `account_device` 分支：`signer_id` 等于 attestation 的 AccountId principal，
`verification_method` 必须是该 principal DID 加 exact device-id fragment；`source_actor_id` 必须等于完整 attested AccountId，
`source_sender_domain` 必须等于 exact device ID。该分支携 `device_projection_attestation` 与唯一
`attester_signer_evidence_ref`，后者必须指向该 AccountId 的 origin Station 的历史 Service evidence。
origin Station 在 `keys/query` 返回 `query_device_record.signer_evidence_ref` 前必须耐久保存这份内容寻址对象及 attester 闭包；
对象内 attestation 与 row 中的 attestation 逐字相等。Source 先取该 ref，再在 attestation 有效窗口内签名 response，
不得从 DID 文档猜设备公钥或把设备伪装成 `principal` 分支。接收方在 `source_proof.created_at` 验证完整闭包、
正有效期区间、active 状态、签名与 exact actor/device 绑定；后续过期不追溯作废已接受的历史证明。
首次入队 T1 仍验证 source 的 current exact device authorization/generation 与 membership；历史 attestation 不代替 current gate。
`account_device` 仅授权普通 human history-response proof，不扩张 Control Event、DID 文档或 notary 的签名权威。

Release service admission 必须完整验证 authenticated branch 及其递归 attester evidence closure；对于只有 receiver
持有 verified local MLS tree 的 minimal-metadata branch，release service 只验证 content address、closed shape、source relay binding 并原样 pin，
不得声称自己已验证本地 MLS tree 与加密 IdentityLink 的 authority。两种 branch 的 exact canonical bytes 均随 request retention 保留至 request expiry；
receiver 使用 `request_receipt` history traversal access 从标准
governance-dependency resolve surface 按 digest 分页取得。不得查询 current DID document 代替历史 evidence，也不得把最多 1 MiB 的
evidence bytes 重复内联到每个 manifest/chunk。
Agent 使用可复用 CurrentAdmission 材料，在 source proof 的签署时刻核对 lease/gate/key 时窗与当前授权。
`source_proof` 直接签完整 history response signing input，包括 evidence ref；不再计算另一份 Agent observation
request digest。实际 request、receiver、范围与 capability 仍由该消息自己的签名和请求合同绑定。
Ordinary human、Agent 与 organization-recovery holder source 使用 `AuthenticatedSignerResolutionEvidence`。
organization-recovery holder 使用 Principal root evidence；ordinary human 的设备签名必须使用上述 AccountDevice branch，
其 DID-document method 签名使用 Principal branch。Agent 的 root evidence 必须是 Agent branch；Service branch
只能作为递归 attester leaf，不得作为 source root。Minimal-metadata source 不得冒充
Principal，而必须使用 `MinimalMetadataMlsLeafSignerEvidence`。后者绑定 effective scope、canonical MLS group id、epoch、leaf index、
pairwise/source actor、verification method、独立 Ed25519 response-signing public key/digest、端到端加密取得的 IdentityLink canonical bytes/digest、
exact RFC MLS LeafNode canonical bytes/digest、winning group-state transition Event ref、
outer Event digest、MLS transition digest、完整 target Seal basis 与 authorization incarnation。Receiver 只有将这些坐标与独立验证并耐久保存的
winning MLS state、active LeafNode 与本地加密取得的 IdentityLink 逐字对齐后，才能使用该独立 Ed25519 response key 验证 source proof；MLS ciphersuite 的
LeafNode signature key 不得被冒充为 generic PayloadProof key，因此 MLDSA44 hybrid group 不会被暗中禁用。该 evidence 使用独立
`minimal_metadata_mls_leaf_signer_evidence` governance-dependency selector，canonical bytes 同样不得超过 1 MiB。
IdentityLink 的 closed shape 必须携带并由其既有 proof transcript 签入
`response_signing_verification_method,response_signing_public_key_b64u,response_signing_public_key_digest`；
`ak.schema.identity_link.v1` identity 固定 response signing algorithm 为 `Ed25519`，wire 不再回显 algorithm。
method controller 必须投影为 `pairwise_actor_id`，digest 必须等于 decoded 32-byte key 的 SHA-256。
Minimal-metadata evidence 中的三项 wire response-signing 坐标与 schema-injected Ed25519 algorithm 必须与接收端通过同一 MLS group 端到端加密取得并和 exact active LeafNode
绑定的 canonical IdentityLink 逐字相等；仅让
evidence 自己携带并 self-consistently hash 一把未被 IdentityLink 签入的 key 必须拒绝。
IdentityLink 通过 `content_type=application/vnd.arkret.identity-link+json` 的加密 MLS application message 或等价 MLS private extension
承载；解密后的 plaintext 必须恰好是 `ak.schema.identity_link.v1` 的 RFC 8785 canonical bytes。接收端只有在该消息的已验证 sender domain
逐字等于 `pairwise_actor_id`、其 `(realm_id,mls_group_id,mls_epoch,mls_leaf_index)` 与本机已验证 winning MLS state 的 exact active
BasicCredential LeafNode 对齐、`trust_domain` 等于当前连接的已验证 trust domain 后，才可把 IdentityLink canonical bytes、digest、exact
LeafNode TLS bytes、digest 与 winning transition ref 写入 E2EE secure cache。该接收步骤只证明 MLS delivery 与本地 tree 绑定；IdentityLink
自身的 Principal proof 必须在 history response 验证时由
`identity_link_signer_evidence_ref` 解析出的 exact
`AuthenticatedSignerResolutionEvidence::Principal` 及其递归 attester closure 验证，禁止把 evidence 内嵌 IdentityLink bytes 当作自证来源。
Source record 的唯一 digest 为：

```text
source_record_digest = H(
  UTF8("ak.history-source-record-v1") || 0x00 ||
  JCS({history_response_signing_input, source_proof})
)
```

其中 `history_response_signing_input.content.kind` 是 manifest/chunk 的唯一 discriminator；不存在重复的 outer kind。
Response wire 只携 `request_digest+request_receipt_digest`；source service 从已验证的本地 request replica/list 按 digest 取 receipt，
destination release service 从自己的 durable request ledger 取原 receipt。未知/mismatch 是 dependency reject 且零写，完整 receipt 不在
manifest/chunk wire 重复。Source-record digest 排除 service metadata、`sent_at`、release attestation 和 service proof。
服务在每个 chunk 首次耐久入队事务中取得 profile-dispatched current accepted authority views、执行 T1，并生成独立
`HistoryReleaseAttestation`；它绑定 source-record digest、request/receipt/scope、exact continuous range、recipient/source
identity/profile 以及 profile-closed typed authority view locator/digest vector，但不进入 source record/proof、HPKE context 或 manifest。
Release service 在该事务中通过各 authority 既有标准接口或本地 durable replica 机械验证 closed predicates；locator vector 只是
service-signed 决定收据和审计坐标，不是 receiver 可独立重放的 portable 多 authority proof。v1 显式信任 release service 诚实执行 T1；
恶意或 stale service 不在本 profile 的密码学保证内，不能用 Merkle 包装伪装成已解决。manifest 未完成上述 T0 admission 时
chunk 必须 dependency reject 且零写；只有 manifest、descriptor、完整 traversal closure、release attestation 与 service record 全部验证后才可安装。
Service proof 的 transcript 是移除 `service_proof` 后完整 closed response record 的 RFC 8785 JCS bytes；chunk record 中的
完整 release attestation（含 typed authority locator/digest vector）因此逐字节受 service proof 覆盖，attestation 不再有第二条独立签名或
不完整的外层摘要。每条 normal record 与 lost descriptor 都 MUST 携带
`release_service_signer_evidence_ref`；该坐标必须解析为
`AuthenticatedSignerResolutionEvidence::Service`，其 signer id 和 verification method 分别逐字等于 receipt 冻结的
`release_id` 与该条 `service_proof.verification_method`，并按 `service_proof.created_at` 验证完整 method history。
Release service 必须在首次写入 record/lost 的同一事务中把该 evidence 及其递归依赖按 request-receipt access 保留到 request expiry；
requester 通过 receipt-bound governance-dependency resolve 获取，不依赖 current DID document 或另建 resolution-chain surface。
Manifest record MUST 不含 release attestation。
Source MUST 先以 content-addressed staged blobs 保存 manifest、所有 sealed chunk bytes 和 ids，最后原子写 ready marker；
marker 出现前不得发送。Retry 重发相同 bytes。Accepted chunk 是 secret release 线性化点；source 的 exact retry 只返回首次
小型 `HistoryKeyResponseSendReceipt`，不以新 head 重验或重签；完整 record/attestation 只从 recipient response stream 读取。

Attempt identity 固定为 `(request_id,source_sender_domain,manifest response_id,manifest_digest)`。Attempt 的 source-local durable
status 是封闭四元集 `unfinished | completed | permanently_rejected | expired`。只有 manifest 命名的每个
chunk 都取得 durable send receipt 才是 `completed`；v1 不定义 abandon operation，未取得全部 receipt 且未被 §6.2 判为
`replace_manifest` 的 attempt 仅在 request expiry 进入 `expired`。Permanent chunk rejection 按 §6.2 把 attempt 转入
`permanently_rejected` 并要求 source 建新 manifest，不能把旧 attempt 偷换为完成，也不得对外呈现为已投递。
`completed|permanently_rejected|expired` 后才能 GC 对应
staged blobs/outbox，compact accepted receipt ledger 仍按下述期限保留。并发上限只计 `unfinished`：每 request/source-domain 4、
每 request 8；`permanently_rejected` 不再占用该预算——它已停止重发且没有 in-flight bytes，否则若干次 permanent rejection 就能把
同一 request 的合法 replacement 永久堵死。同一 request 在 expiry 前可顺序创建任意多个满足单体上限的 manifest，不存在
lifetime split/attempt 总次数。

Release service 必须在有效 high-water ack 前保留完整 byte-identical record 与 conditional attestation。Receiver 只有在对应
manifest descriptor 或 chunk 结果已 durable install/reject（或取得 signed lost descriptor）后才能 ack；未 durable 处理即 ack 是
client error。Ack 事务原子记录 disposition、GC 大 record/attestation 并释放 active 16 MiB quota，不再承诺 ack 后重读 response record。
Source exact retry 只依赖首次 enqueue 已冻结的小型 `HistoryKeyResponseSendReceipt` ledger；该 compact ledger 保留到 request expiry，
按 request 64 MiB、requester 256 MiB 与 service advertised finite floor 独立计费，不能由 ack 刷写绕过。Expiry 后才转为 30 天 light tombstone
`{response_id,source_record_digest,terminal_status,expired_at}`；tombstone 只拒绝冲突/过期 retry，不再承诺返回完整 record。

Receiver 对 list 的单一 sequence stream 逐项耐久记录 disposition。Normal record 允许
`installed|cryptographically_rejected|superseded_duplicate`；`service_record_lost` 只允许匹配同 sequence/response_id 与 signed
lost-descriptor digest 的 lost entry。`ack_token` 绑定每项 `{sequence,kind,response_id,entry_digest}` 和 high-water，不能把 lost
与 normal record 分页或确认到不同顺序。四者都释放 processing quota；manifest 的
`installed` 只安装 descriptor，chunk 的 `installed` 也只表示 candidate material 已耐久落入 history-only store。后续 AEAD 成功仅建立
exact Event→candidate digest binding，不得把 candidate 或整个 epoch 标成 verified/authoritative coverage。High-water ack 只能跨过已有 durable
disposition 的 sequence。尚未 durable ack 的 accepted record 不得默默驱逐；不可恢复损坏必须返回
`lost_records[{sequence,cursor,response_id,record_digest}]`，不得用裸 `lost=true` 解除 ack 死锁。资源常量以 scalability registry 为唯一机读真源。

### 6.1 E2EE client 自动收敛义务 (normative)

声明 `ak.profile.e2ee_client.v1` 且 `ak.feature.history_key_recovery.v1` 的客户端，对
`content_scheme=mls_exporter_aead_v1` 与 current effective
`history_access=all_history_for_current_members` 的 scope，在发现已接收的 encrypted Event 缺少 exporter epoch 时，
MUST 无人工操作地执行以下 crash-safe 收敛循环：

1. requester MUST 先持久化 recipient HPKE private key 与 pending create intent，再创建或恢复一个覆盖当前
   canonical missing ranges 的未过期 private request。同一 `(effective_scope, requester_actor_id,
   requester_authorization_incarnation, missing canonical ranges)` 在任意时刻只能有一个可用的 durable
   single-flight request；重启、超时、列表空页或短暂网络失败只能恢复该 intent/request，不得每轮创建新的
   `request_id` 或 HPKE key。新 request 必须使用作者当时最新 durable trusted bases；仅 basis 前进不会使已接受
   receipt 失效，因此不得单独引发 request churn。只有 missing range 扩展、request expiry、release-service
   rebind，或已冻结 traversal 确实无法解析/验证时，才能按现行 create 规则作者化新 request。
2. requester MUST 持续读取每个已接受 request 的 private response stream，按 §6 验证、安装并只在 durable
   disposition 后 ack。空页的唯一 canonical 形状是 `entries=[]`、`limited=false`，且省略
   `ack_token` 与 `cursor`；客户端 MUST NOT 持久钉住或 ACK 空页，MUST NOT 推进 high-water，并 MUST
   以有界退避从同一 `after=last_acked_cursor` 重新读取。非空页 MUST 携带 `ack_token`。
3. 同 profile 的 current authorized endpoint MUST 持续消费它可见的 scope-private request projection。当它持有与
   request 范围交集的 `local_authoritative` material 且 T0/T1 及所有 current authorization gate 通过时，
   MUST 构造最小已持有覆盖的 manifest/chunks，在 ready marker 前耐久 staging，并按 exact bytes 重试直到
   attempt `completed|permanently_rejected|expired`。存在 `unfinished` attempt 时不得为同一覆盖重签另一组 response id；既有 attempt
   completed 之后若本地又取得该 request 尚未覆盖的 requested epoch，必须创建新 manifest，不得因“已响应过”
   永久抑制新材料。send/relay 失败的 exact-retry / replacement / terminal 分支只按 §6.2 的封闭分类决定。
4. 本地诊断必须至少区分 `awaiting_authorized_source_response`、`response_verification_pending`、
   `decryption_unavailable_by_policy`、`decryption_unavailable_by_profile_floor` 与 request expiry。在没有受验证证据时，
   requester 不得声称某 source 离线或材料已销毁；等待 source、T1 dependency 或短暂传输失败都不是 policy
   terminal。只有 §6.2 `request_terminal` 行登记的 closed code，或 request expiry 本身，才能停止对该 request 的自动尝试。

这些义务只保证在“至少一个符合条件的 endpoint 在 request 有效期内持有 material、可见 request 且所有安全门禁成功”
时客户端会发起并持续尝试恢复；它不把 `all_history_for_current_members` 扩张为服务端明文托管、密钥永久存在或
绝对可用性承诺。

### 6.2 Source send/relay 拒绝的耐久处置分类 (normative)

Source 对 `ak.self.history_key_responses.command.send.v1` 与
`ak.peer.history_key_responses.command.relay.v1` 的每一次失败，MUST 只按已登记 code 机械选择下面三种
source-local durable 处置之一：顶层 code 取自 RFC 9457 Problem `type` 的 `{code}` 尾段（见
[`../sync/api-conventions.md` §5](../sync/api-conventions.md)），仅当该 code 需要细分时再读已登记
`reason_code`。Source MUST NOT 依据 HTTP status 类别、`title` / `detail` 文案或本地化字符串推断处置。

| 处置 | 含义 | source 耐久动作 |
| --- | --- | --- |
| `retry_same_attempt` | 拒绝不归因于已冻结的 exact bytes，同一 bytes 之后仍可能被接受 | attempt 保持 `unfinished`；按有界退避重发 exact staged bytes，直到取得 send receipt 或 request expiry。不新建 manifest，不新签 response id，不改写 attempt identity。 |
| `replace_manifest` | 服务已永久拒绝这组 exact bytes，重发同一 bytes 永远不会被接受 | attempt 转入 `permanently_rejected`（既不是 `completed` 也不是 `expired`）；停止对该 attempt 的重发；在 §6 并发上限内为同一 request 作者化覆盖相同 requested ranges 的新 manifest。 |
| `request_terminal` | 该 source 在**当前**已验证 authorization / policy 下对该 request 的任何 attempt 都不会被接受 | attempt 同样转入 `permanently_rejected` 并停止重发；MUST NOT 立即作者化替代 manifest，也 MUST NOT 用定时退避反复重试该判定；记录该 closed terminal code 作为本地诊断。只有当本 source 侧参与判定的输入实际前进（新的 accepted authorization incarnation / grant，或该 scope 的 current history-access 变化）时，§6.1 第 3 条的持续义务才重新允许作者化新 manifest。 |

分类是封闭的：该 operation 的可返回 code union 等于
[`operations-error-mapping.json`](../../artifacts/registry/operations-error-mapping.json) 的
`rules.universal_codes` 与本 operation `operation_specific[]` 之并，下面三行覆盖其全部成员。

- `retry_same_attempt`：`dependency_missing`、`frontier_unavailable`、`rate_limited`、`internal_error`、
  `service_unavailable`、`temporarily_unavailable`、`unauthenticated`、`auth_expired`、`soft_logged_out`、
  `did_proof_required`、`account_locked`、`account_suspended`、`operation_selector_required`。
- `replace_manifest`：`schema_violation`、`json_invalid`、`query_invalid`、`param_missing`、`param_invalid`、
  `too_large`、`limit_exceeded`、`signature_invalid`、`state_mismatch`、`conflict`、`duplicate_conflict`、
  `failed_precondition`（含 `reason_code=history_traversal_anchor_unreachable`）、`ttl_expired`
  （staged bytes 所携的 TTL / `expires_at` 窗口已过，同一 bytes 重发永远不会被接受）。
- `request_terminal`：`capability_denied`、`history_not_visible`、`account_deactivated`、`account_erased`、
  `not_implemented`、`unsupported_feature`、`unsupported_event_kind`、`unsupported_protocol_version`、
  `unsupported_operation_version`。

传输失败、超时、TLS 失败，以及任何没有可解析 closed Problem body 的应答，MUST 按 `retry_same_attempt`
处理。收到不在上述 union 中的 code 是对端协议违规；source MUST 同样按 `retry_same_attempt` 处理（fail-safe：
它不会产生 response-id / outbox churn，且仍被 request expiry 封顶），并 MUST 把该 code 记为本地诊断，
MUST NOT 据此猜测 replacement。

`permanently_rejected` 描述的是 **attempt** 的终局（这组 bytes 不会再被接受），不是对后续是否作者化
replacement 的授权：后者只由上表第三列区分。两种处置都 MUST NOT 把旧 attempt 记为 `completed`，也不得
对 requester 呈现为已投递；旧 attempt 的 compact `HistoryKeyResponseSendReceipt` ledger 仍按 §6 的
request-expiry 期限保留；进程重启后 source MUST 从耐久记录恢复同一处置分支，不得因重启把
`permanently_rejected` 退回 `unfinished` 重新 exact retry，也不得把 `retry_same_attempt` 升级成新 manifest。

## 7. History-only store 与终态

候选 secret bytes 全局按 material key `(effective_scope,mls_group_id,epoch,candidate_digest)` 去重；`candidate_digest` 是 exact secret bytes
的 SHA-256，origin 不参与 material identity。每个 resident material instance 在 bytes 首次落盘时取得不可变、单调递增的
`material_received_sequence`；同 bytes 从新 origin 到达只增加 origin attribution，不刷新 sequence。bytes 被驱逐后再次 refetch 才建立新
resident instance 并取得新 sequence。每 `(scope,group,epoch)` 最多 8 份 received material；槽位只计算 resident secret bytes。
本机从 verified MLS state 直接导出的 secret 是独立 `local_authoritative` 项，使用分离账本，不占 received 槽位，永不被驱逐或 received bytes 覆盖。Portable backup
只允许序列化源设备的 `local_authoritative`；在另一 endpoint restore 后，该 material 仍按 `portable_backup` origin 进入 received candidate
槽位而不继承源设备 authority。received candidate 只能留在 device-bound multi-candidate store，RHRK open 也不例外。

`CandidateOriginAttribution` 使用独立 key `(material_key,origin_domain,origin_ref)`，另存不可由 retrieval coordinate 替代的稳定
`origin_quota_domain`。三分支为：

- `response_sender`：quota domain=`{source_sender_domain}`，origin ref=`{response_id,source_record_digest}`；
- `rhrk_archive`：quota domain=`{method_controller_principal_id,holder_service_id,recovery_key_id,accepted_key_evidence_ref}`，其中 accepted
  evidence EventId 就是 rotation identity 且不存在独立 key version；origin ref=
  `{container_event_ref,archive_digest}`；
- `portable_backup`：quota domain=`{backup_series_id,producer_actor_id}`，origin ref=`{backup_origin_id}`。

`backup_origin_id` 必须为 `backup:<BackupId>`；无 canonical BackupId 时为 `backup:sha256:<hex of exact envelope bytes>`。
origin ref 只用于 refetch，换 response/archive/envelope 不得换 quota domain 或伪装 sender。每 material key 最多 4 条、每 exact
`(scope,group,epoch,origin_domain,origin_quota_domain)` 最多 64 条、每 `(scope,group,epoch)` 总计最多 256 条。
每行有效期固定为 `first_observed_at+2592000` 秒，由 reader / GC 计算而不持久化 `expires_at`；duplicate/refetch 不可刷新 `first_observed_at`。时间加法溢出 canonical timestamp 可表示范围时 MUST fail closed。先删过期项；仍超任一 cap 时仅保留 canonical tuple
`(first_observed_at,candidate_digest,origin_domain,JCS(origin_quota_domain),JCS(origin_ref))` 最小集合（固定同加 30 天不改变顺序）。origin ledger 不得复制 secret bytes 或改变 material sequence。

使用 candidate 前必须先验证外层 Event proof、scope/group/epoch、verified sender domain、重构 AAD、schema 与 replay gate。AEAD
成功/失败都只向独立 `EventCandidateBinding` 账本写
`(event_binding_key,candidate_digest,outcome)`；`event_binding_key=(scope,group,epoch,event_id,verified_sender_domain)`，其中 Event digest 从 suite-bearing `event_id` 解码，
`outcome=success|failure`。该 key 不含 origin，也不得从 binding 反推 origin。binding 只保存 digest、结果与 attribution，**不得 pin secret bytes**；
两者均不得 epoch-level promote、隔离或删除其它候选。
恶意作者的 fake secret 加 fake ciphertext 至多影响其自身签名 Event，不能锁死另一 sender。插入超配额时按两级确定性驱逐 received bytes：
先从无 success binding 的 material（unbound 与 failure-only）中选择，再从 success-bound material 中选择；每级均取
（`material_received_sequence` 升序，`candidate_digest` 按 UTF-8 升序）最小者。success/failure binding 只决定 tier，绝不 pin bytes。
驱逐只删除 secret bytes 与该 resident sequence，保留可供 refetch 的有界 origin attribution/Event binding tombstone；
只有 `local_authoritative` 永不成为 victim，且它不阻塞 received 槽位。

`EventCandidateBinding` 每 `(scope,group,epoch)` 最多 256 条，有效期固定为 `first_observed_at+2592000` 秒，由 reader / GC 计算且不可延长；时间加法溢出时 MUST fail closed。超限先删已过期项，
再按 `(first_observed_at,event_id,verified_sender_domain,candidate_digest,outcome)` 升序确定性裁剪。binding 到期或裁剪不得改写独立 ciphertext replay ledger、
`local_authoritative` 或 epoch authority。恢复 material 只进 decrypt store，不恢复 leaf signer、ratchet、proposal 或 counter。

终态 reason 只有 `decryption_unavailable_by_policy` 和 `decryption_unavailable_by_profile_floor`，
key 至少包含 `(effective_scope,epoch,authorization_incarnation,endpoint_incarnation,reason)`。T1 失权、
source 离线、proof/chunk 缺失是暂时状态，MUST NOT 进入终态。

## 8. Backup 与 organization recovery key

Human `mls_history` backup 每个 object 只属于一个 exporter effective scope，只保存：

```text
HistorySecretRange = { from_epoch, to_epoch, secrets_b64u }
```

解码长度 MUST 等于 `(to_epoch-from_epoch+1) * KDF.Nh`。Suite 从 exact winning transition/activation
proof 解析，wire 不自报。多 scope 拆为多 object，backup series 负责 anti-rollback 和替代。

每个 Realm authority 同一时点最多登记一把逻辑 organization recovery public key。该 key 不能塞入 Realm create：固定顺序是
Realm create → accepted create Seal → `ak.realm.organization_recovery_key.register`（含 holder acceptance，锚定 create Seal 或 holder
已 pin 的 prior evidence Seal）→ accepted key-evidence Seal → 之后才允许任何选择
`organization_recovery_key` durability 的 Realm/Circle MLS Genesis。Rotate 使用
`ak.realm.organization_recovery_key.rotate` 对唯一 active cell 做通用 whole-value CAS：签名 Event MUST 恰好携带一条
目标为 `ak:cell:ak.component.realm.organization_recovery_key.v1:null` 的 `head_eq`，其 value MUST 是 producer 在
`seal_basis` 下观察到的完整 current projected tuple；生产 projector 按
[`../authz/event-auth-state-resolution.md` §9.3.1](../authz/event-auth-state-resolution.md) 把该值复制到
lattice `op.from`。不得以 `expected_previous_key_evidence_ref`、Seal ref 或任何 RHRK 专用 fallback 代替 `head_eq`。
payload 中的 `expected_previous_key_evidence_ref` 与 `expected_previous_key_evidence_seal_ref` 只证明 prior tuple provenance：
前者必须等于 current projected tuple 的 provenance Event，后者必须是使该 Event 生效的 exact accepted Seal；新 holder
acceptance 的 trusted basis 必须因果覆盖该 Seal。CAS 与 provenance 任一不成立均 fail closed 且整个 Move 零写入。
同一 frozen predecessor 上的同批 sibling 必须由 Seal 排重；若互斥 sibling 分别进入不可达 accepted Seal branches，通用
`cas_register` join 产生 `⊥`，不得按到达顺序选 winner。旧 tuple 保留作历史验证。Circle 不登记独立 key。同一个 Realm key 只服务显式 opt-in scopes。每个
exporter Realm/Circle 独立选择 `none|organization_recovery_key`，不继承父 scope，不复制
holder/custody tuple。选择后，每个 winning Genesis/Commit Event MUST 在同一签名 Event 中携带
恰一份本 scope/epoch archive，否则 transition 拒绝。RHRK tuple 固定
`hpke_suite=ak.hpke_x25519_aead_chacha20poly1305.v1`，`frozen_public_key_b64u` 必须是 exact 32-byte X25519 raw key 的
43 字符 unpadded base64url。Admission 必须解析 current `key_agreement_ref` 并逐字匹配 raw key/controller，解析 current
`holder_signing_ref`，并要求 holder proof verification_method 逐字等于该 signing ref、该 method 的 controller 投影逐字等于 `method_controller_principal_id`；同时验证 `holder_service_id` 是本次 accepted holder service route/authority。二者是独立字段，不得互相推导或比较为同一 DidCoreId。
Archive 绑定 `effective_scope + derived
mls_group_id + epoch + mls_transition_digest + recovery_key_tuple + registered HPKE profile`，不绑定尚未产生的
container EventId。Rotation 只影响后续 transition，旧 archive 按历史 key id 可读，不自动
backfill/revoke。Custody 复制、HSM、Shamir 或 threshold 不上 Realm/Circle wire。

跨服务 holder 可达性只用私有 `ak.peer.organization_recovery_archives.command.replicate.v1`：source scope service 将 exact
archive、container Event ref、archive-lifetime `HistoryGovernanceTraversalRetention` 复制到 tuple 冻结的
`holder_service_id`。Archive tuple 保留声明 key provenance 的 `accepted_key_evidence_ref` EventId 与 holder acceptance 已 pin 的 prior
`holder_trusted_basis` 完整 Seal antichain；没有 singular activation Seal selector。每个 ArchiveListItem 的 traversal intent 只有一个 singleton
`requested_ranges=[{from_epoch:epoch,to_epoch:epoch}]`，base 逐字等于该 tuple 的 holder trusted basis，target basis 经完整 replay 证明
key-evidence Event 已成为 effective tuple 且 container Event 是该 epoch winning transition。不同 item 逻辑独立，服务可按 digest 物理复用
retained Event/Seal/dependency bytes。Holder service 由此投影 archive read/list；不创建 ArchiveId、proof package/result object 或 `ak:snapshot`，
也不存在 request 式临时 expiry/renewal 状态。
跨服务 replica 可先 durable 进入 `pending_traversal` 并以 exact replica digest 授权拉取 missing objects；只有完整 cut 与全部 registered dependencies
验证通过，才能在一个事务中转为 `accepted` 并分配 archive sequence。Source outbox 只重放同一 pending replica bytes/digest，
不得因部分下载或重启生成新对象。

Winning Genesis/Commit 被 accepted Seal 激活时，activation consumer 必须在同一个 durable checkpoint 事务中按
`(effective_scope,mls_group_id,epoch,container_event_ref,archive_tuple_digest)` upsert replication obligation 与 exact-byte
outbox。启动、重连和 projection checkpoint 恢复都必须扫描已激活 archive 并补建遗漏 obligation。Replica 首次生成后不得重新
HPKE、换 base/current/target 或改 intent；失败/receipt 丢失只重放原 bytes，exact duplicate 返回首次 accepted receipt。Archive、其
完整 Seal cut、Control Move bytes 与 registered replay dependencies 作为 Realm history recovery material 长期同寿命；旧 key rotation
不缩短寿命。v1 不定义 RHRK 远端 GC、renewal 或双方销毁协调 surface；部署在规范外本地销毁后不得再声称对应历史可恢复。

对选择 `organization_recovery_key` durability 的 scope，source 在删除本地 epoch history secret 前 **MUST**
同时完成以下 durable gate：holder 已首次接受 replica 或 exact duplicate 已返回首次 accepted receipt；随后通过
`ak.self.organization_recovery_archives.read.list.v1` barrier 逐字重读同一 archive、container Event ref 与
`HistoryGovernanceTraversalRetention`；本地 coverage ledger 已在一个原子事务中提交 exact
`(effective_scope,mls_group_id,epoch,container_event_ref,archive_tuple_digest)`、durable holder acceptance 与 exact
reread。任一条件缺失或重读 bytes 不一致时，本地 GC **MUST** 以 `failed_precondition` 拒绝；全部完成后 GC 只删除本地
history secret，不得删除或改写 holder archive。`ak.vector.history_key.organization_recovery_archive_durable_before_gc.v1`
是该 gate 的规范性 service-behavior 向量；它不规定服务端私有表形状。

effective epoch cell 明确分开：`transition_ref` 是 Genesis/Commit EventId，`transition_event_digest` 是 outer Event digest，
`mls_transition_digest` 才是 MLS transition 内容摘要。Conflict recovery 选择前两者；state leaf 同时绑定三者。Archive 的
`transition_digest` 必须逐字等于 `mls_transition_digest`。Commit 对解码后的 `payload.commit_bytes_b64` 原始字节计算 SHA-256；该摘要是 reducer 派生值，不作为 sibling 字段进入 wire payload。Genesis 使用
`SHA-256(UTF8("ak.mls-genesis-transition-v1") || 0x00 || JCS(closed mls_genesis_payload core after removing
organization_recovery_archive))`；outer EventId、Event proof 与 archive 本身均排除。Genesis/Commit 的
`governance_binding.content_scheme` 与 conditional `durability_policy` 机械决定 archive 必填/禁止，producer 不得漏 archive 后继续。

RHRK holder 唯一读取面是 recipient-bound、按 canonical bytes 分页的
`ak.self.organization_recovery_archives.read.list.v1`。Query 必须给 exact effective scope、`recovery_key_id`、
`key_agreement_ref`、`accepted_key_evidence_ref`、`holder_trusted_basis` 与可选单一 epoch range；每行直接返回匹配 archive、container Event ref、
archive-lifetime traversal retention。holder 从 target 反向取得完整 Seal cut 并拓扑重放；
不存在 `ArchiveId` 或第二个 archive-get surface。服务只返回历史 tuple 中
`holder_service_id` 与当前认证 holder service authority 逐字节相符，且 `holder_signing_ref` 的当前 method-controller 投影仍等于 `method_controller_principal_id` 的行；unknown scope、无匹配、tuple 失配、过期/无权 holder
均使用同形 `not_found`。Organization Recovery holder 是显式全历史高权限恢复主体：为独立验证 notary、state root 与 activation，它被授权
读取从 `holder_trusted_basis` 到 exact archive target 所必需的完整 Control Move 与 Seal closure；这可能披露 membership、policy 及其它 control
metadata。该披露不能用伪稀疏证明或 service attestation 代替。若部署不能接受，MUST NOT 启用 `organization_recovery_key` durability。
Traversal access 仍只允许 target→base cut 的 Seal、其 delta Control Move 与 registered dependencies：不得读取无关 DataEvent、执行 generic timeline scan、获得 membership 或 send 权。
Holder service 首次 durable accept replica 时分配严格单调
`archive_sequence`；list 按 `(archive_sequence,container_event_ref)` 升序，cursor 绑定 exact `holder_service_id`、`method_controller_principal_id`、完整 query digest
（含 Event provenance 与 Seal trusted anchor）及最后 ordering tuple。延迟到达的旧 epoch 只能取得更大 sequence，不会插入旧 cursor 前。

同一 holder 可复用 history request list 的窄授权分支，但必须显式给 scope，且只返回 requested range 与该 holder exact
historical key tuple 下至少一个 archive 相交的未过期 request；无交集 request 不得出现。读取 archive 本身不授予 membership。
holder 作为 response source 时，每个 chunk 只能覆盖同一个 byte-identical RHRK tuple，source proof 必须使用 current
holder signing authority；archive 历史 `holder_signing_ref` 只作 provenance。当前 holder lifecycle/signing authority 仍由首次入队
release attestation 复核，唯一 continuous released range 中的每个 epoch 都必须绑定实际 archive ref。

## 9. Conformance

Vectors MUST 覆盖 closed union、Realm/Circle 独立 group、ordinary human/Agent/minimal sender、join/rejoin、
endpoint replacement、history_access 单向收紧与禁止放宽、response-stream duplicate/reject/ack、多候选投毒、
RHRK rotation、traversal target 不支配 base/current、隐藏 predecessor、secret-chain 负例和 26,298 epoch/Nh=32 packed-size 算例。
至少两个独立 runner MUST 从原始输入重算 exporter、KDF、nonce、AAD、AEAD、HPKE、RHRK 和 routing tag，
并执行 negative mutations。
