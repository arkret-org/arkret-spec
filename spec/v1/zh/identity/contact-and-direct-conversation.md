---
title: Contact & Direct Conversation Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-08-03
see_also:
  - consent-model.md
  - ../crypto-media/device-lifecycle.md
  - ../models/realm-and-space.md
  - ../models/strand-and-message.md
  - ../sync/api-conventions.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按
[`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本文定义 principal-scoped Contact 事实、1:1 Direct Conversation 的稳定身份与故障恢复。本文是这些语义的
唯一正文真源；测试矩阵或执行报告只能引用本文，不得建立另一套 authority、wire 或状态机。

## 1. Contact 真相源与主体身份

Contact 与 holder-private 备注、Realm 内 `ak.relation.*`、非 Contact Consent、Direct Conversation binding
互不替代。Contact-based create/send **MUST** 只读取双方各自签发的 directional Contact lineage；
`ak.consent.*` 只服务非 Contact basis，**MUST NOT** 为 Contact 或 Personal DM 补授权。

Contact wire 中的 `peer` **MUST** 是 closed discriminated XOR：human、Native Personal Agent 与其它已登记
principal kind 分支分别携带该分支的完整 stable subject/binding 字段；裸 `peer_id`、未知 kind、分支字段混用
或仅靠显示 handle 推断主体均 **MUST** fail closed。Contact Event 的 signer **MUST** 是 holder-authorized
long-term signer，且只能是 active human device、active Agent runtime，或 controller 依据 accepted narrow
delegation 代表其 owned Agent 签名。session DPoP key、Principal Server key 与 relay key 不得签 Contact Event。

每个 issuer 独立维护 `(basis_id, issuer_id, peer)` lineage。不存在跨双方共享 pair CAS、两阶段互签
assignment 或服务端代签。每条 lineage 的 genesis 固定为 `version=1` 且 predecessor 缺省；successor 固定为
`version=current+1` 且 `predecessor_event_ref` 逐字等于 current head。每条事实都签入完整 peer XOR、
`basis_id`、version、predecessor 形状与 directional full-set scope。fork、跳版、同 version 不同 bytes、未知
predecessor 或 signer 不匹配全部 quarantine/fail closed。

## 2. Contact 写链、回执与 basis

request、respond、reject、scope replacement 与 tombstone 共享唯一写链：

```text
prepare private durable reservation
→ holder-authorized signer 签 closed EventInitialSubmission batch
→ commit 在 holder PCR 本地原子 acceptance
→ source-signed acceptance receipt + durable receipted outbox
→ peer carrier 投递原始 signed fact 与对应 receipt
→ peer 保存 verified mirror、checkpoint/current lease 与 transport receipt
```

prepare **MUST** 保存 operation/idempotency/canonical request digest、预分配 Event IDs、完整 peer XOR、方向化
full-set scope、expiry 与 branch-specific basis/version/predecessor；不得写 canonical Contact state。commit
**MUST** byte-identical 匹配 reservation。相同 identity + 相同完整 bytes 回放首次 outcome，任何 bytes/proof
变化返回 conflict。响应丢失、重启或 outbox redelivery 不得产生第二 Event、第二 receipt 或第二 lineage head。

holder source service **MUST** 以本地 `(holder, peer)` admission slot CAS 串行 request/respond/reject，并保证
任一 request ref 最多被 normal、glare 或 reject 之一消费。每条 accepted request 独立取得 source-signed
`request_acceptance_receipt`，至少绑定 holder、完整 peer、slot version/predecessor、request Event ref/digest、
source checkpoint、accepted-at 与 issuer；receipt 不得反向承诺尚未存在的 future basis。
`request_acceptance_receipt_digest` 是 exact closed signed receipt 的 RFC 8785/JCS UTF-8 bytes 的 SHA-256。

永久 `basis_id` 只从以下 stable semantics 计算：

```text
normal = {kind:"normal", sorted_pair_members,
          request_event_ref, request_acceptance_receipt_digest}
glare  = {kind:"glare", sorted_pair_members,
          requests:[{request_event_ref,request_acceptance_receipt_digest}, ...]}
```

pair members 与 glare requests 都按已登记的 UTF-8 unsigned-byte ordering 排序。normal responder 必须在本地
CAS 点证明自己没有 outgoing request，并签 `normal_response_acceptance_receipt`；该 receipt 绑定 exact request
receipt、derived normal basis 与 CAS/completeness proof。reject 必须同样取得 source-signed
`request_rejection_acceptance_receipt`，绑定 exact request receipt、slot predecessor、reject Event 与 terminal
outcome，并具有 durable exact replay/conflict 语义。

glare admission 不仅需要两张 exact request receipts，还 **MUST** 携 source-signed causal frontier/completeness
evidence，证明两 request 在任一方消费 request ref 前因果并发。仅收到两张 receipt、到达顺序或 wall clock
不足以建立 glare。证据足够时双方机械派生同一 basis，禁止 respond/reject且不合成 `ak.contact.accepted`
Event；若双方 current directional full-set scope允许，则直接投影 effective/UI accepted。normal accepted 后晚到的
reverse request 必须由 slot CAS 拒绝，不得改判 glare。

`ContactBasisEvidenceBundle` 是唯一无签名 deterministic bundle，只容纳 derived basis ID、exact acceptance
receipts、normal response receipt或reject receipt，以及可刷新的 causal/checkpoint/completeness/frontier
evidence。刷新 current proof 不改变 `basis_id`。unknown/stale/incomplete evidence 只能产生 tentative；tentative
不能授权 successor、Contact create/send 或 DM authority。

`ak.peer.contacts.command.submit` 是唯一 peer carrier，其 closed XOR 分支分别携原始 signed request/response/
reject/scope/tombstone Event、该分支 exact acceptance receipt与可刷新的 current proof。carrier 必须使用 peer
Message Signature，并逐字保留内层 bytes；relay 不得重签、改写、拆批或把 tentative 提升为 accepted。

## 3. Directional scope、current head 与终态

Contact scope 只表达 issuer holder 授予 peer 的方向，唯一字段为 `granted_to_peer_scopes[]`。scope update 的
唯一 fact 是 `ak.contact.scope.update`，唯一 self operation 是
`ak.self.contact.command.scope_update{phase=prepare|commit}`。payload closed 绑定完整 peer XOR、basis、version、
predecessor 与完整 scope 集合；扩大和收窄都必须由 holder 显式签名。tombstone 只终止 Contact，不承担 scope
update。

scope full-set replacement 为空仅把非 terminal basis 投影为 `suspended`；同一 lineage 后续显式 widen 可恢复。
proposal 阶段 reject 与 accepted basis 上 tombstone 是 terminal；terminal 后 constituent request refs、basis 与
lineage 永不复活，recontact 必须创建全新 request receipt(s)与新 basis。

source service 必须对每个 issuer lineage 签 monotonic head checkpoint/current lease，逐字绑定 current head、
accepted frontier、`complete_through` 与 `fresh_until`。peer mirror 保留 source signed fact、lease/checkpoint 与
transport receipt；收到更高 incoming signed head时 target service 立即撤销旧 mirror，不等待轮询。stale/unknown
current proof仅阻止 Contact-based create/send：existing binding resolver仍返回原坐标，并在 `found.send_blockers[]`
报告 `contact_scope_stale`。proof stale 绝不把 accepted basis回滚为 pending，也不得隐藏 participant 坐标。

不存在、policy deny、过期、未授权与 quarantined 对无权主体必须使用相同 opaque failure。

## 4. Contact operation surface

所有非 public `ak.self.*` operation 的同一个 OpenAPI security object **MUST** 同时要求 bearer 与 DPoP；HTTP
Message Signature只能额外叠加，不能替代其中任一项。实现 **MUST** 登记并实现下列 closed operation：

| operation | 语义 |
| --- | --- |
| `ak.self.contact.command.request` | prepare/commit 原始 signed request与 request acceptance receipt |
| `ak.self.contact.command.respond` | normal accept；要求 responder slot 无 outgoing |
| `ak.self.contact.command.reject` | proposal terminal reject与 rejection receipt |
| `ak.self.contact.command.scope_update` | issuer-local full-set replacement |
| `ak.self.contact.command.tombstone` | accepted basis terminal，旧 refs永久消费 |
| `ak.self.contact.query.list` | 从 verified basis与双方 directional current heads投影 |
| `ak.peer.contacts.command.submit` | closed XOR peer carrier；原 bytes + exact receipt/current proof |

所有 transport binding **MUST** 逐字段等值，不能自行增加 `accepted`、兼容 consent shape、unsigned service row
或第二轮 assignment。首次接触 message 属于未获同意文本，接受前必须 quarantine/stub，不得把 Contact request
变成正文投递通道。

## 5. Direct Conversation resolver

`ak.self.direct_conversation.command.resolve` 是 unordered stable subject pair 到唯一 DM binding 的入口。
Resolver 必须分开三个 gate：

1. binding discovery：existing participant或精确 owned-Agent controller可见固定 pair/Realm/Strand/binding；
2. pre-binding operation discovery：仅原 authenticated requester可按 operation ID读取自己的 reservation/journal；
3. creation admission：仅 `create=true` 且无 binding时校验 exact pair、双方 current directional Contact heads与
   source leases、account/Agent/controller lifecycle、policy、operation-control、membership/MLS/KP facts。

discovery 不授予 create/send。existing binding不因 offline、session、presence、KP empty、grant/policy freshness、
MLS reconcile或 personal blocklist而隐藏。canonical participant membership缺失，或任一 current Contact
directional head已撤回 exact pair，返回 `suspended` 与原坐标。其余运行时问题返回 `found`、原坐标与 closed
`send_blockers[]`。personal blocklist是 holder-private blocker，只能对 owner显示 `personal_blocked`，不得伪造
shared suspension。

`create=false`只需 peer。`create=true` request 必须在 body 中携 caller-generated `operation_id`、
`idempotency_key`与同一 requester-signed `operation_control_authorization`。同 operation/key/canonical bytes回放原
outcome；同 operation或 key配不同 bytes conflict。同 pair并发 operation由 permanent pair slot CAS只接受一个。
已有 operation暂不可用时返回相同 operation ID，禁止生成新 draft或 server next-action。

v1 只允许双方 locator位于同一 trust domain；不同 trust domain在 reservation前 opaque reject。domain-root-signed
closed pair policy机械产生 stable `pair_registry_id`、pair key、origin coordinator、immutable replica set与 epoch
policy，并在 reservation pin policy digest。requester不能缩小 replicas/quorum，也不能引入 pair generation。

## 6. Permanent pair slot 与 materialization journal

同一 pair 永久只有一个 stable `operation_id`和单调递增的 certified `attempt_sequence`，初始为 1。首个
q-certified genesis固定 Realm、main Strand与未来 binding坐标。一旦发生 claim、accepted Event或任一 external
effect，slot不得删除或重分配，只能沿
`materializing → cleanup → cleanup_complete_retryable`前进；permanent cancel也保留 tombstoned slot与坐标。

每个 attempt 使用独立 `(operation_id, attempt_sequence)` journal，并最终绑定 fresh target authorization、
KP claim、membership Event/version、MLS generation及所有 effects。新 attempt只能由同 operation-control log 的
q-certified `attempt_advance` successor打开；其 predecessor必须是 current attempt 的
`cleanup_complete_retryable`。除 operation/host/predecessor cleanup proof等结构字段外，advance只绑定 fresh
target authorization、未 claimed KP ref与 `claim_request_digest`，禁止预先绑定 accepted claim/receipt、
membership draft/version或 MLS generation。advance q-COMMIT后，第一 external effect才执行 claim CAS并记录
receipt，后续 journal successor再绑定 membership/MLS。

唯一 materialization 顺序是：

```text
participant-authorized reservation + compensation authority
→ KP claim CAS
→ durable journal genesis + eligible committer exact commitment
→ atomic [Realm create Event, peer member join Event]
→ append accepted frontier
→ main Strand create Event
→ MLS genesis + Add Commit + Welcome
→ recipient durable MLS state
→ consume original claim
→ Direct Conversation binding accepted
→ found
```

draft是 closed object且恰有 Realm create、peer join、main Strand create、binding四个 Event slots；只有前两个是
atomic founding unit。跨 Principal Server claim receipt必填，本地同服分支明确缺省。服务不得添加第五 Event、
代签、合成或复制 Event。binding只在 recipient durable且 claim consumed之后创建一次。失败 attempt补偿完成后
复用已 accepted Realm/Strand坐标，但使用 fresh authorization、未 claimed KP、较高 membership version与新 MLS
generation；成功前不得报告 existing binding。

## 7. Operation-control PBFT、DA 与 host fence

本节唯一authority/profile ID是`ak.profile.direct_conversation_operation_control.v1`；transfer、ordinary effect、
attempt advance与read certificate都复用它，不得登记第二套handoff/manifest authority。

pair registry 的 replica set在整个 registry生命周期 immutable；v1不定义 joint migration。固定
`N=3f+1`、`q=2f+1`。genesis key是 `(pair_registry_id,pair_key,predecessor=⊥)`，每个 instance使用单调 view、
deterministic proposer、PRE-PREPARE/PREPARE/COMMIT、prepared lock与 VIEW-CHANGE/NEW-VIEW。NEW-VIEW包含
exact q份 VIEW-CHANGE；存在 prepared时选择其中最高 prepared value。若 q份都无 prepared，当前 view proposer
在 NEW-VIEW中提出恰一个 fresh合法完整 value；validator只验证该 value与 bundle，不扫描外部候选。空/非法
proposal只触发下一 view。q-COMMIT前无 canonical effect，q-COMMIT后同一 effect不可 cancel。

业务值与每轮投票信封必须完全分离。无 view、无 certificate 的 closed `EffectValueCore` 只绑定
`pair_registry_id,pair_key,operation_id,attempt_sequence,effect_id,effect_digest,destination,
expected_host_epoch,predecessor_head_digest,journal_root`；`value_digest`是 exact core 的 RFC 8785/JCS UTF-8
bytes 的 SHA-256，换 view不得改变它。qDA certificate使用无自引用 closed shape，逐字绑定 value digest、journal
root、registry/operation/attempt/effect/destination/epoch、distinct signer identities、阈值与 canonical排序；
其 digest从不含自身 digest的 exact certificate core计算。

每个 per-view phase envelope分别以 domain-separated transcript绑定 registry、view、phase、value digest、qDA
certificate digest与该 phase的 predecessor/lock facts；签名禁止跨 phase/view/registry/context复用。q份 PREPARE
形成 prepared certificate，q份 COMMIT形成唯一 point-of-no-return。closed
`ExecutionBundle={exact_effect_value_core,exact_qda_certificate,per_view_certificates,
authenticated_encrypted_journal_bytes}`只是传输载体，不创造第二个 PONR。receiver从 immutable registry解析
distinct signers，重算 value/certificate/journal root与 canonical ancestor；缺 bundle只允许补传同 effect ID。

每次 current-head read都需要 fresh q-certified read certificate；它只证明读取，不授权 effect。无 fresh proof或
不完整 authenticated journal时保持 pending/fail closed。transfer是同 PBFT profile上的 effect successor，绑定
`transfer_id,from,to,manifest_root`并令 accepted host epoch加一；initial host head不得携 `transfer_id`。claim、
recipient delivery、Event admission与binding receipt都携 operation、host epoch、`effect_head_ref`及对应 q-COMMIT
proof/bundle。receiver接受 canonical ancestor effect，不因 later transfer/cancel拒绝已 q-committed effect。

同 attempt已有 claim时不得领取第二 claim。transfer只可按 certified fence将原 claim绑定到新 host/epoch并签新
receipt；attempt失败先把原 claim推进到 terminal revoke，再由下一 certified attempt使用 fresh未 claimed KP。
binding found后 operation-control authority永久退出，后续 hosting/failover使用普通 Realm governance。

## 8. Stable identity、repair 与 participant authority

pair key从同 trust domain下两 stable subject DID按 UTF-8 unsigned-byte排序后对 closed JCS对象计算 SHA-256。
handle、display name、request、service、Realm或Strand都不得进入前像。同 pair只有一个 immutable binding、Realm
与main Strand；leave、block、tombstone、terminal、erase或恢复均不得创建 successor。

exact-pair repair唯一 carrier是标准 `ak.member.state{join}` `EventInitialSubmission`与
`ak.profile.direct_conversation_repair.v1`。profile锁定既有 pair/Realm/main Strand和二人 mask。human只能
self-rejoin；owned Agent使用 `actor_id=agent_id, executed_by=controller_id`及 immutable controller authorization。
不得加入第三 participant或取得 grant/policy/admin/Strand/binding变更权。repair accepted后重新 MLS reconcile；
旧 MLS private state不可恢复时可在同 Realm/Strand创建单调新 generation，但不得读取加入前无权解密的历史。

日常写 authority唯一来自 `ak.authority.direct_conversation_participant.v1`与 current accepted binding、exact
membership、directional Contact heads、active MLS generation及 action-specific Agent gate的交集。技术 root、
created_by、membership本身或普通 grant均不能替代该 evaluator。root mask只允许 current materialization的精确
founding/repair effects；found后不得恢复 owner/admin authority。

## 9. SDK 本地事实 DAG 与 endpoint 边界

服务端不得注册全局 ActivationPlan、跨 endpoint next-action或 workflow/conversation identity。每个 endpoint只
返回自己的 closed local outcome、local blocker/reason、operation/ref、exact-retry/conflict与本 endpoint expiry。

SDK planner按四类 typed facts组合并行 `ready_actions[]`：canonical public（Event/Seal/binding）、authenticated
service durable（reservation、PBFT log/journal、receipts/epoch）、controller-private durable（allocation、
requested-scope disclosure、canonical authoring bytes）与 local ephemeral（session/presence/timer）。每项携 source
ref、frontier/epoch、freshness/expiry与privacy label。客户端 bytes仅负责 authoring/exact retry；服务恢复必须依赖
signed reservation、replicated journal与receipts，digest不能重建私有 bytes。unknown/stale只阻断相关 action，
不得隐藏 existing DM坐标。

## 10. 规范性回归边界

Conformance 必须覆盖 response loss、restart、duplicate、reorder、reject replay、glare causal completeness、
tombstone/recontact、scope narrow/widen、partition、PBFT view change、qDA/qCOMMIT、host transfer、second claim/
second Realm拒绝、compensation与new MLS generation隔离。旧 consent-managed Contact、synthetic glare accepted
Event、跨双方 CAS、server next-action、successor Realm/Strand或 view-dependent effect digest必须由负例拒绝。
