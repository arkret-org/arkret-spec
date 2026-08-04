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
assignment 或服务端代签。request 发生在 receipt/basis 之前，只签完整 peer XOR、directional full-set scope与
private introduction evidence digest；reject只终止其 exact admission slot，不建立 basis或lineage。只有 post-basis
lineage facts携basis/version：normal accepted genesis固定`version=1`且无predecessor；scope update/tombstone固定
`version=current+1`且`predecessor_event_ref`逐字等于current head。glare的request heads只能由后续source-signed
lineage/current proof绑定，不得回写旧Event。fork、跳版、同version不同bytes、未知predecessor或signer不匹配
全部quarantine/fail closed。

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

prepare **MUST** 保存 operation/idempotency/canonical request digest、预分配 Event ID、完整 peer XOR、方向化
full-set scope、expiry 与该分支已有的 basis/version/predecessor，并返回branch-typed
`{event_id,kind,unsigned_event_bytes,event_digest}` canonical draft；request/reject不得伪造未来basis字段。draft
不含holder proof，客户端只可追加该proof。commit移除proof后必须与reserved unsigned bytes、ID、kind与digest
逐字一致，任何其它变化返回conflict；不存在接受caller自造Event shape的分支。同一
operation/idempotency/phase + 相同完整bytes回放该phase首次outcome；prepare与commit必须使用同一
operation/idempotency，但两phase的canonical bytes与幂等记录彼此独立。响应丢失、重启或outbox redelivery
不得产生第二Event、第二receipt或第二lineage head。

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
`reject_acceptance_receipt`，绑定 exact request receipt、slot predecessor、reject Event 与 terminal
outcome，并具有 durable exact replay/conflict 语义。

glare admission 不仅需要两张 exact request receipts，还 **MUST** 携 source-signed causal frontier/completeness
evidence，证明两 request 在任一方消费 request ref 前因果并发。仅收到两张 receipt、到达顺序或 wall clock
不足以建立 glare。证据足够时双方机械派生同一 basis，禁止 respond/reject且不合成 `ak.contact.accepted`
Event；若双方 current directional full-set scope允许，则直接投影 effective/UI accepted。normal accepted 后晚到的
reverse request 必须由 slot CAS 拒绝，不得改判 glare。

`ContactBasisEvidenceBundle` 是唯一无签名 deterministic bundle，只容纳 derived basis ID、exact request
acceptance receipts、normal response receipt（normal 分支）、双方 glare concurrency attestations（glare 分支）
以及可刷新的 current checkpoint/completeness/frontier proofs。normal 分支必须有 response receipt且禁止 glare
attestation；glare 分支必须有双方各一张 attestation且禁止 response receipt。两种final bundle都必须有pair双方各一张
current proof；少于两张只能形成非授权的partial/tentative query view，不能冒充portable basis evidence。刷新 current proof 不改变 `basis_id`。unknown/stale/incomplete evidence 只能产生 tentative；tentative
不能授权 successor、Contact create/send 或 DM authority。

`ak.peer.contacts.command.submit` 是唯一 peer carrier，其 closed XOR 分支分别机器限定原始 signed Event kind为
`ak.contact.requested|accepted|rejected|scope.update|tombstoned`并携该分支exact acceptance receipt与允许的
current proof。request分支还必须携closed typed private `introduction_evidence`，其registered digest算法结果必须
逐字等于signed request payload的`introduction_evidence_digest`；该digest固定为
`H("ak.contact.introduction-evidence.v1", exact_introduction_evidence)`，其中H使用§7的统一定义。receipt中的Event ref/digest、lineage中的
event ref与current proof head都必须与同一内层Event及分支逐字交叉匹配。carrier只承载
`ak.contact.*`，不得承载 `ak.direct_conversation.bound` 或 Realm Event；Direct Conversation binding 只能走
§6–§8 的 materialization admission。carrier 必须使用 peer Message Signature，并逐字保留内层 bytes；relay
不得重签、改写、拆批或把 tentative 提升为 accepted。其 response 是独立 closed union
`accepted | duplicate | deferred`。五类 signed Event 分支返回逐字匹配该 Event 的 mirror receipt；`glare_finalize`
与 `proof_refresh` 没有 signed Event，必须返回各自 request-kind 绑定的 signed control receipt，绝不能伪造或借用
某个 Event mirror receipt。所有成功响应还必须带 closed `result_kind`，并将实际返回的 attestation/current proof纳入
control receipt的 `result_digest`；它不得复用 self contact
prepare/commit 的 `ContactOperationOutcome`，也不得把 holder-private receive state编码进状态值。
其中 request/response 分支允许携该分支 current proof；缺 proof 时只能保持 tentative，不能授权 projection；
scope/tombstone 分支必须携 current proof；reject 分支没有 basis current proof。`glare_finalize` 分支携 exact 两张
request receipts、发送方从对端收到的一张 remote mirror receipt、derived glare basis和发送方 attestation；接收方用
自己本地持有的counterpart mirror receipt补齐交叉验证，只在全部匹配且本地
slot仍未消费时返回自己的 attestation，并在双方 attestation齐备后才可同时返回 current proof。用于该分支的
remote mirror receipt只能是`accepted|duplicate`，`deferred`从不构成authority。无签名 bundle本身永远
不是 authority。`proof_refresh` 必须使用 fresh idempotency key，携目标先前签发的 mirror receipt锁定同一 immutable
inner fact；该prior mirror receipt也只能是`accepted|duplicate`。receiver只可用更鲜且逐字段匹配的
source-signed proof替换旧 proof，不能修改 fact/receipt/basis；成功响应必须返回匹配的current proof。
任何不匹配当前 closed XOR 的请求
都必须 schema reject；实现不得协商第二种 carrier，也不得以缺少必需 branch receipt 或 proof 的自定义结构进入
projection。

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
| `ak.self.contact.command.respond` | 只执行 normal accept；要求 responder slot 无 outgoing，不接受 reject action |
| `ak.self.contact.command.reject` | 独立 proposal terminal reject与 rejection receipt；不得复用 respond body |
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

permanent cancel accepted后，resolver对有权的原requester及existing participant唯一返回closed
`{status:"tombstoned",operation_id,attempt_sequence,coordinates}`；`coordinates`仍是首次genesis固定的immutable
pair/Realm/main Strand/binding坐标，只供审计与确定性发现，不恢复create/send authority。相同请求永远exact replay
该terminal outcome；任何`create=true`、attempt advance、claim、repair或新operation都不得使该slot复活。无权主体
仍得到与不存在相同的opaque failure。

`create=false`只需 peer。`create=true` 是唯一两阶段授权入口：`prepare_authorization`携 caller-generated
`operation_id`与`idempotency_key`，domain authority在 permanent pair slot上执行single-write CAS并返回
`reservation_handle`、domain-root-signed exact registry statement和固定authorization core；caller只签该core。
`commit_authorization`必须原样带回handle、statement/core组成的`operation_control_authorization`与requester签名，
不得修改registry/pair/host/replica/quorum坐标。同 operation/key/phase/canonical bytes回放原outcome；同 identity
配不同bytes conflict。同 pair并发prepare由permanent pair slot CAS只接受第一份，后续永远返回同一registry。
已有 operation暂不可用时返回相同 operation ID，禁止生成第二份 draft或跨endpoint server next-action。

v1 只允许双方 locator位于同一 trust domain；不同 trust domain在 reservation前 opaque reject。完整
`operation_control_domain_policy_statement`携trust-domain ID、policy version、受信domain root及verification method、
eligible replicas/hosts、N/f/q、epoch policy与时窗，由配置的trust-domain root对exact closed statement签名。
`pair_slot_id=H("ak.direct-conversation.pair-slot.v1",{trust_domain_id,pair_key})`不含policy version或可变registry选择，
且`pair_registry_id=pair_slot_id`。replicas机械取policy canonical排序后的前N项，initial host取eligible hosts第一项，
origin coordinator固定为`replicas[0]`。pair registry statement同时是slot_version=1的永久CAS receipt；requester不能
缩小replicas/quorum、换host、重签第二core或引入pair generation。

## 6. Permanent pair slot 与 materialization journal

同一 pair 永久只有一个 stable `operation_id`和单调递增的 certified `attempt_sequence`，初始为 1。首个
q-certified genesis固定 Realm、main Strand与未来 binding坐标。一旦发生 claim、accepted Event或任一 external
effect，slot不得删除或重分配。成功分支从 `materializing` 单调进入 `found`；失败分支才沿
`materializing → cleanup → cleanup_complete_retryable`前进。`cleanup_complete_retryable` 只能经 §6 所述
q-certified `attempt_advance` 打开下一 attempt并回到 `materializing`，不得直接变成 `found`。permanent cancel
进入唯一名称`status="tombstoned"`的terminal，但仍保留slot与已固定坐标；其后只允许上述terminal exact replay，
不得回到`creation_required`、`materializing`或`found`。

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

draft是 closed object且恰有 Realm create、peer join、main Strand create、MLS genesis、MLS Add Commit、MLS Welcome、binding七个 Event slots；它们按 founding unit（前两个，atomic）、main Strand、MLS epoch（genesis + Add Commit）、welcome admission、binding finalize 五步物化。跨 Principal Server claim receipt必填，本地同服分支明确缺省。服务不得添加第八个 Event、
代签、合成或复制 Event。binding只在 recipient durable且 claim consumed之后创建一次。失败 attempt补偿完成后
复用已 accepted Realm/Strand坐标，但使用 fresh authorization、未 claimed KP、较高 membership version与新 MLS
generation；成功前不得报告 existing binding。

跨Principal Server执行membership compensation时，发送方必须在`ak.peer.events.command.submit`对应
`EventFederationSubmission.membership_compensation_evidence`传递与self admission逐字相同的closed transport
evidence；该字段不进入Event canonical bytes/event digest。federation receiver不得丢弃、改名、重签、从digest重建
或降级为普通grant，而必须重验delegation digest/author signature、原join accepted proof、exact admission/cell/
incarnation/J1 provenance、leave/remove action XOR、executor service/proof key、terminal certificate与destination
single-use CAS。任何缺失或不匹配均零写入fail closed；同一evidence在self与peer路径必须得到同一admission结果。

## 7. Operation-control PBFT、DA 与 host fence

本节唯一authority/profile ID是`ak.profile.direct_conversation_operation_control.v1`；transfer、ordinary effect、
attempt advance与read certificate都复用它，不得登记第二套handoff/manifest authority。

pair registry 的 replica set在整个 registry生命周期 immutable；v1不定义 joint migration。domain-root-signed
`pair_registry_statement`逐字携上述完整policy statement、closed core、stable pair slot/registry ID、registry
digest、slot version与accepted time；domain root对除`signature`外的完整closed statement签名。它固定canonical
participant pair/pair key、origin coordinator、initial host DID/epoch 0、canonical replicas、`N=3f+1`、`q=2f+1`
与epoch policy；同pair slot的第二个不同core必须永久拒绝。每个instance显式使用前一certified head digest；replica one-vote slot固定为
`(registry_digest,pair_registry_id,pair_key,instance_predecessor_head_digest,view,phase,replica_id)`，不含
operation ID，因此同一pair/head上两个operation ID是冲突value而非两个独立genesis。proposer严格为
`replicas[view mod N]`。每个instance使用单调view、PRE-PREPARE/PREPARE/COMMIT、prepared lock与
VIEW-CHANGE/NEW-VIEW。NEW-VIEW包含
exact q份 VIEW-CHANGE；存在 prepared时选择其中最高 prepared value。若 q份都无 prepared，当前 view proposer
在 NEW-VIEW中提出恰一个 fresh合法完整 value；validator只验证该 value与 bundle，不扫描外部候选。空/非法
proposal只触发下一 view。q-COMMIT前无 canonical effect，q-COMMIT后同一 effect不可 cancel。

requester-signed `operation_control_authorization` 必须内嵌上述完整registry statement；`requester_signature`只签
exact `operation_control_authorization_core`，verification method必须由`requester_id`控制。该closed core逐字绑定
registry digest/pair/operation/requester/genesis head；genesis digest按registered transcript绑定registry、pair、
operation、initial host DID与epoch 0。首次Effect predecessor必须等于它，后续必须等于前一qCOMMIT effect head。
无法验证domain root、requester属于stable pair、replica排序/阈值、host或任一digest时不得开始qDA。

业务值与每轮投票信封必须完全分离。无view/certificate的closed `EffectValueCore`内嵌closed
`ordinary_external|attempt_advance|host_transfer` effect XOR，并绑定registry/pair/operation/attempt/effect、exact
authenticated plaintext `payload_digest`、
destination、expected/resulting host DID+epoch、predecessor与journal root。ordinary/attempt advance的host前后
必须逐字相等；transfer details的from/to必须逐字等于value的expected/resulting fence且`to_epoch=from_epoch+1`。
`effect_digest`哈希exact closed `{effect_kind,effect_details}`；`value_digest`哈希exact full core，换view不得改变。
ordinary external只允许`keypackage_claim`映射到`ak.peer.keys.keypackages.command.claim`和`event_admission`映射到
`ak.peer.events.command.submit`两类closed branch；target operation、request schema、request/authorization digest及
admitted Event kind allowlist必须逐字段匹配，不能把PBFT当成任意管理operation授权。attempt advance在旧attempt日志
提交：outer attempt_sequence=from_attempt、inner operation_id=outer operation_id、to_attempt=from_attempt+1；解密
journal必须给出exact cleanup terminal receipt与fresh peer claim request。host transfer的journal必须给出双方host签名
的exact manifest，manifest digest、from/to fence与outer value逐字匹配，且destination=to_host。closed encrypted
journal carrier通过AAD重复绑定effect/payload及全部实例/host坐标；authenticated decrypt后的registered payload必须匹配它们。

typed payload投影固定如下：`keypackage_claim.request_digest=H("ak.direct-conversation.external-request.v1",
exact peer_key_packages_claim_request_body)`，其`authorization_digest=H("ak.direct-conversation.external-authorization.v1",
request.requester_authorization)`；`event_admission.request_digest`同样哈希exact
`EventsSubmitFederationRequestBody`，`authorization_digest`哈希canonical排序的每条原Event proofs、authorization lease、
membership compensation evidence及request级CBA bundles的closed授权投影，`admitted_event_kinds`必须等于body实际Event
kind的canonical-sorted distinct集合。两分支destination必须是目标operation的authenticated destination service，
journal `plaintext_schema_ref`必须等于branch固定schema。attempt的cleanup/target/claim digests分别对journal中的exact
receipt、requester_authorization与peer claim request使用对应registered H；transfer
`manifest_digest=H("ak.direct-conversation.host-transfer-manifest.v1", exact manifest without its two signatures)`，双方
signature各自覆盖同一exact unsigned manifest。任一projection、digest、destination或schema不等都在qDA前拒绝。

所有摘要统一使用`H(label,x)="sha256:"+lowerhex(SHA256(UTF8(label+"\n") || RFC8785_JCS(x)))`；若字段定义
指定decoded ciphertext bytes，则改为`SHA256(UTF8(label+"\n")||decoded_bytes)`且不做JCS。registry、authorization、
value/effect、PRE-PREPARE、message、read request与bundle wire digest分别对各自closed unsigned/full对象取H；
除另有明确字段名的签名外，signature transcript一律是其对象去掉signature字段后的closed core；pair registry
root签名覆盖statement除signature外全部字段，requester_signature只覆盖authorization core。qDA/prepared/qCOMMIT certificate digest只对
不含自身digest及receipts/pre_prepare/prepares/commits witness的semantic core取H，因此不同合法exact-q signer
subset共享同一semantic digest；完整witness arrays仍必须逐签名、membership、distinct与canonical排序验证。

每个 per-view phase envelope是严格 closed XOR，并分别以 domain-separated transcript绑定 registry、view、phase、
value digest、qDA certificate digest与该 phase的 predecessor/lock facts：PRE-PREPARE不得携后续 phase 字段，
PREPARE必须绑定 `pre_prepare_digest=H("ak.direct-conversation.pre-prepare.v1", exact signed PRE-PREPARE envelope)`
（包含PRE-PREPARE自身signature），COMMIT必须绑定 exact prepared certificate digest。签名禁止跨
phase/view/registry/context复用。`prepared_certificate`逐字包含 exact PRE-PREPARE 与 q份同 view、同 value、
同 PRE-PREPARE digest 的 PREPARE envelopes；q份同 view、同 value、同 prepared certificate digest 的 COMMIT
envelopes形成唯一
point-of-no-return；certificate verifier必须重验 `N=3f+1`、`q=2f+1`、replica membership、distinct signer与
envelope逐字段一致，不能只信其声明的 `n/f/quorum`。

`authenticated_encrypted_journal`固定使用registered RFC9180 base-mode HPKE suite，`info`为domain UTF-8，AAD为exact
`aad_core`的JCS bytes；nonce由HPKE key schedule按single-shot seq=0内部派生，wire不得携nonce。`journal_root`按
`H("ak.direct-conversation.journal-envelope.v1", exact closed journal envelope)`计算，因而同时承诺scheme、recipient、
key ref、enc、plaintext schema、AAD和ciphertext；AAD故意不含journal/value digest或ciphertext，避免自摘要环。
qCOMMIT中的`effect_head_digest`按closed JCS transcript
`{registry_digest,pair_registry_id,pair_key,operation_id,attempt_sequence,view,
predecessor_head_digest,value_digest,qda_certificate_digest}`计算，qCOMMIT certificate或其digest不进入该transcript，
因此没有自摘要环。

`per_view_certificates[]` 是 `per_view_certificate` closed union的有序数组；每个元素恰为
`prepared_certificate | view_change_certificate | new_view_certificate`之一；首个 prepared certificate 内含 exact
PRE-PREPARE，合起来形成从该 instance genesis 到
最终 q-COMMIT view 的canonical ancestor chain。发生 view change时，先由每个replica产生closed
`view_change_message`，再由exact q份、目标view一致且signer distinct的messages形成`view_change_certificate`，
最后由新proposer签closed `new_view_certificate`。view 0的proposal禁止携new-view certificate；view>0必须携且其
内嵌PRE-PREPARE必须与proposal外层PRE-PREPARE逐字相同。每个`view_change_message`使用`prepared_state=none|prepared`
closed XOR；prepared分支逐字携本replica的最高`prepared_certificate`，none分支不得携伪造的prepared字段。
`new_view_certificate`逐字包含exact `view_change_certificate`和proposer的PRE-PREPARE proposal，并选择集合中最高
view的prepared value；只有q份全部为none时才能提出一个fresh合法完整value。数组按view及该view内
prepared→view-change→new-view的因果顺序排列，不能跳过影响最终选择的证据，COMMIT只能引用链尾view。

closed `ExecutionBundle={registry_authorization,value_core,qda_certificate,per_view_certificates,qcommit_certificate,
authenticated_encrypted_journal}` 逐字携带domain-root-signed registry、上述chain与最终q-COMMIT certificate，
只是传输载体，不创造第二个 PONR。receiver从 immutable registry解析 distinct signers，重算 value/qDA/每轮
certificate/journal root与 canonical ancestor；`per_view_certificates`缺失、断链或与 q-COMMIT view/value不一致
均 fail closed。缺 bundle只允许补传同 effect ID。

跨服务传输只能使用以下四个registered peer operation，不得借`peer/contacts`、`peer/events`或未登记JSON转发：

1. `ak.peer.direct_conversation.operation_control.command.submit`只在immutable replicas间投递closed tagged
   registry/qDA/PBFT/view-change/read内部消息。source与recipient都必须属于exact registry，HTTP Message Signature
   与内层签名分别验证。相同one-vote slot的相同semantic vote可由不同carrier/witness重放；只有同slot不同
   value/lock digest才是equivocation，不能把不同合法q signer subset或bundle bytes误判冲突。`message_digest`
   是closed tagged message完整bytes的registered H；`queued`只有消息与typed missing dependency set均durable时合法。
2. `ak.peer.direct_conversation.operation_control.command.deliver`只把完整ExecutionBundle送到
   `EffectValueCore.destination`。destination逐项重验后按
   `(pair_registry_id,operation_id,attempt_sequence,effect_id)`永久CAS，但比较的是registered
   `effect_commitment_digest={registry,pair,operation,attempt,effect,value,effect_head}`。相同commitment的不同合法
   ExecutionBundle witness subset是duplicate并返回signed receipt；只有同identity不同commitment才永久
   `operation_control_equivocation`。`submitted_bundle_digest`只用于精确补取/审计，不是semantic CAS identity。
   `deferred`表示exact bundle已durable但本地依赖未齐，不表示effect执行成功。
3. `ak.peer.direct_conversation.operation_control.query.execution_bundle`只按exact effect/value/bundle coordinates，
   或fresh committed head给出的effect/value/effect-commitment/effect-head/qCOMMIT坐标补取
   bundle或查询同一destination receipt；禁止“返回当前bundle”式head oracle。仅immutable replica、certified
   destination或同operation requester可调用。
4. `ak.peer.direct_conversation.operation_control.query.read_certificate`为一个exact signed read request主动收集fresh
   q receipts；request必须绑定registry、requester/audience、pair/operation、minimum host epoch；可选
   `expected_host_service_id`出现时要求exact match，省略时允许fresh certificate发现transfer后的新host DID。且
   `expires_at-issued_at<=60s`，最大clock skew为5s。certificate内嵌exact signed request与恰`q=2f+1`个distinct、
   canonical排序、request digest和完整head逐字相同的receipt；observed time必须在request窗口，receipt expiry不得
   晚于request expiry，consumer观察时全部未过期且observation age<=60s。相同(requester,registry,request_id)
   相同core回放，不同core conflict；过期必须新request ID。达不到q必须quorum unavailable，不得选本地head。

每次 current-head read都需要上述 fresh q-certified read certificate；head是closed `genesis | committed` XOR，
必须携registry/pair与完整host DID+epoch，committed分支还携effect ID、effect commitment、predecessor/effect/value/
qDA/qCOMMIT digest，因此可机械构造`by_committed_head` exact bundle query。certificate只证明读取，不
授权 effect、transfer或attempt advance。无 fresh proof或
不完整 authenticated journal时保持 pending/fail closed。transfer是同 PBFT profile上的 effect successor，绑定
`transfer_id,from_host/from_epoch,to_host/to_epoch,manifest_digest`并令accepted host epoch严格加一；delivery receipt
的host DID+epoch必须等于value resulting fence；initial host head
不得携`transfer_id`。claim、recipient delivery、Event admission与binding receipt都携operation、host DID+epoch、`effect_head_ref`及对应q-COMMIT
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
second Realm拒绝、compensation与new MLS generation隔离。synthetic glare accepted Event、跨双方 CAS、server
next-action、successor Realm/Strand或 view-dependent effect digest必须由负例拒绝。
