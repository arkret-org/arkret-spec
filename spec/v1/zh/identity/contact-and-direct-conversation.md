---
title: Contact & Direct Conversation Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-08-11
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
`ak.consent.*` 只服务不以 Contact 为授权依据的路径，**MUST NOT** 为 Contact 或 Personal DM 补授权。

Contact wire 中的 `peer` **MUST** 是 closed discriminated XOR：human、Agent 与其它已登记
principal kind 分支分别携带该分支的完整 stable subject/binding 字段；裸 `peer_id`、未知 kind、分支字段混用
或仅靠显示 handle 推断主体均 **MUST** fail closed。Contact Event 的 signer **MUST** 是 holder-authorized
long-term signer，且只能是 active human device、active Agent runtime，或 controller 依据 accepted narrow
delegation 代表其 owned Agent 签名。session DPoP key、Station key 与 relay key 不得签 Contact Event。

每个 issuer 独立维护 `(contact_round_id, issuer_id, peer)` lineage。不存在跨双方共享 pair CAS、两阶段互签
assignment 或服务端代签。request 发生在 receipt/round 之前，只签完整 peer XOR、directional full-set scope与
private introduction evidence digest；reject只终止其 exact admission slot，不建立 round 或 lineage。只有 post-round
lineage facts携 `contact_round_id` / version：normal accepted genesis固定`version=1`且无predecessor；scope update/tombstone固定
`version=current+1`且`predecessor_event_ref`逐字等于current head。glare的request heads只能由后续source-signed
lineage/current proof绑定，不得回写旧Event。fork、跳版、同version不同bytes、未知predecessor或signer不匹配
全部quarantine/fail closed。

### 1.1 陌生人首次接触的 new-source quota（normative）

Contact request 与 invite delivery、`ak.self.consent.command.request.v1` 一样，是**陌生人向 holder
发起的首次接触**，因此同样是"换一个 principal 就能重新骚扰"的放大面。这三条面 **MUST** 汇聚到
[`consent-model.md` §6.1.1.3](./consent-model.md) 定义的**同一个 holder admission chokepoint**，共用
§6.1.1.1 的 quota carrier 与 effective 值、§6.1.1.2 的 identity key
`(holder 完整 AccountId, source_peer_principal_id)`、以及 §6.1.1.4 的 seen-source ledger 与线性化要求。
Contact 首次接触照常计费；被计费的是**发起方 principal 首次向该 holder 接触**这件事，与该请求最终落在
哪个 carrier 无关。

但 **Contact 的 carrier 不是 holder quarantine**：Contact 的待审状态是本文 §3 的 directional
`pending_incoming` head，由 Contact 状态机独占。因此：

- Contact request 通过 chokepoint 时，写入的是 `pending_incoming`，**MUST NOT** 在 holder quarantine 中
  产生 entry——那会给同一事实造出第二个平行待审 carrier；
- Contact request 命中 quota 上限时，被静默丢弃的对象是 **`pending_incoming` row 的建立**，不是
  quarantine entry。丢弃 **MUST** 对 requester 不可区分：与 `pending` 建立成功、holder 不存在、
  holder policy deny 返回逐字节相同的响应并落在同一 timing bucket，理由与
  [`consent-model.md` §6.1.1](./consent-model.md) 的五元等价类完全相同；
- Contact 的重复判定由本文 §3 的 directional current head 决定：同一 issuer 对同一 peer 已有未终态的
  request 或 lineage head 时即为重复，重复不进入 quota 评估、零新计费。本节不新增第二个去重键；
  §1 的 `(contact_round_id, issuer_id, peer)` lineage 仍是唯一真源。

Contact 路径**仍然不读写 Consent**（本节开头条与
[`../sync/service-http-binding.md`](../sync/service-http-binding.md) 的 `POST /_arkret/self/contacts/request`
行）。共用 chokepoint 只共享反滥用计数，不引入任何 consent 授权语义。

## 2. Contact 写链、回执与 Contact round

request、respond、reject、scope replacement 与 tombstone 共享唯一写链：

```text
prepare private durable reservation
→ holder-authorized signer 签 closed Event，并在必要时附外部 authority Control Proposal Ack
→ commit 在 holder PCR 本地原子 acceptance
→ source-signed acceptance receipt + durable receipted outbox
→ peer carrier 投递原始 signed fact 与对应 receipt
→ peer 保存 verified mirror、checkpoint/current lease 与 transport receipt
```

prepare **MUST** 保存 operation/idempotency/canonical request digest、预分配 Event ID、完整 peer XOR、方向化
full-set scope、expiry 与该分支已有的 round/version/predecessor，并返回 branch-typed
`{unsigned_event_bytes,event_digest}` canonical draft；request/reject不得伪造未来 round 字段。typed digest 携带 suite，
Event ID 与 kind 分别由 digest 和 canonical bytes 唯一派生，不得作为平行 wire source。draft
不含holder proof，客户端只可追加该proof。客户端在签名前 MUST 解码 exact unsigned bytes，并按 operation 分别要求
`ak.contact.requested`、`ak.contact.accepted`、`ak.contact.rejected`、`ak.contact.scope.update` 或
`ak.contact.tombstone`；响应上下文与 decoded kind 不符必须 fail closed，不能依赖或接受第二份 `event_draft.kind`。
commit移除proof后必须与 reserved unsigned bytes 和 digest
逐字一致，并对最终 Event 执行普通 content-bound ID/kind 校验；任何其它变化返回conflict，不存在接受caller自造Event shape的分支。五类 Contact Event 均为
Control Move；commit body 可携带`control_proposal_ack`，其结构和验证规则与
`EventInitialSubmission.control_proposal_ack`完全相同。当接收 Station 不能代表当前 authority set
产生完整 quorum 时，caller **MUST** 携带该字段；服务端能产生时该字段 **MAY** 省略。该证据只是
Event 外的 publication evidence，不进入 reserved Event bytes 或 Event digest。同一
operation/idempotency/phase + 相同完整bytes回放该phase首次outcome；prepare与commit必须使用同一
operation/idempotency，但两phase的canonical bytes与幂等记录彼此独立。响应丢失、重启或outbox redelivery
不得产生第二Event、第二receipt或第二lineage head。

对 human self-principal PCR，commit 的 exact Event 已由 current active accepted device 以 canonical
`{holder}#{device_id}` method 签名；该 device method 同时是 current `single_signer(holder actor_id)` authority，因此这是
authority-authored Move，不得再要求一份独立 Control Proposal Ack，也不得因 Station 不持有
holder 私钥而返回 `quorum_unreachable`。commit 仍须把 Event 写入 pending Control index；只有后继
device-signed accepted Seal 覆盖该 digest 后 Contact effect 才 materialize。Agent delegation、
organization governance、ordinary Realm 与 recovery/re-anchor 不使用此例外。

request prepare 是 holder-local authoring：它 **MUST** 从 holder PCR 的 current actor frontier 与 accepted Seal
frontier 固定 `actor_seq`、`prev_refs` 与 `seal_basis`；任一 frontier 暂不可得时返回可重试的
`frontier_unavailable` 且零写入。target principal 的解析与投递属于 commit 后的 durable receipted outbox / peer
carrier；因此 target 当前离线或不可解析 **MUST NOT** 把本地 prepare 改写成 `not_found`，也不得伪造已投递状态。

holder source service **MUST** 以本地 `(holder, peer)` admission slot CAS 串行 request/respond/reject，并保证
任一 request ref 最多被 normal、glare 或 reject 之一消费。每条 accepted request 独立取得 source-signed
`request_acceptance_receipt`，至少绑定 holder、完整 peer、slot version/predecessor、完整 request Event ref、
source checkpoint、accepted-at 与 issuer；receipt 不得反向承诺尚未存在的 future round。
`request_acceptance_receipt_digest` 是 exact closed signed receipt 的 RFC 8785/JCS UTF-8 bytes 的 SHA-256。

永久 `contact_round_id` 只从以下 stable semantics 计算。`contact_round` 是该轮次的短名，也是下列 immutable closed 建轮核心；后续 directional scope replacement / tombstone 只推进该 ID 下的 lineages，不改写此对象。计算固定为
`H("ak.contact.round.v1", contact_round)`，即
`"sha256:" + lowerhex(SHA256(UTF8("ak.contact.round.v1\n") || RFC8785_JCS(contact_round)))`。
domain label 不是 `contact_round` 的 wire 字段，实现不得把它插入 object 后改算 `SHA256(JCS(object))`：

```text
normal = {kind:"normal", sorted_pair_member_ids,
          request_event_ref, request_acceptance_receipt_digest}
glare  = {kind:"glare", sorted_pair_member_ids,
          requests:[{request_event_ref,request_acceptance_receipt_digest}, ...]}
```

排序对象与比较键固定如下，构造方与验证方 **MUST** 使用相同规则：

- `sorted_pair_member_ids` 恰含两个不同的完整 `ActorId`，各自序列化为 RFC 8785 JCS UTF-8 bytes，按 unsigned-byte lexicographic order **严格升序**排列。
- glare 的 `requests` 恰含两个条目；唯一排序键为每项 `request_event_ref` 的完整、已通过 typed EventId 校验的 wire 字符串的 UTF-8 bytes。逐字节按无符号值比较，第一个不同字节较小者在前；若一串是另一串的完整前缀，较短者在前。**MUST NOT** 解码 digest 后比较，不得大小写折叠、使用 locale 排序，或比较整个 request 对象的 JCS bytes。
- 两个 `request_event_ref` **MUST** 不同且严格升序；相同 ref 无论收据摘要相同还是不同都必须拒绝。`request_acceptance_receipt_digest` 仅绑定该条目的 exact receipt，**不参与排序，也不是平局决胜键**。收据仍须逐项匹配原请求、签名作者与 exact reverse pair。
- 本地构造 glare core 时可以将两条独立取得的 request refs 按上述规则排序；验证收到的 `contact_round` 时必须先检查其现有数组顺序，乱序或重复一律拒绝。**MUST NOT** 对收到的 round 排序、去重或替换条目后再验证其 ID、证据或 founder。RFC 8785 对对象键的规范化不改变数组顺序。

normal responder 必须在本地
CAS 点证明自己没有 outgoing request，并签 `normal_response_acceptance_receipt`；该 receipt 绑定 exact request
receipt、derived normal round 与 CAS/completeness proof。reject 必须同样取得 source-signed
`reject_acceptance_receipt`，绑定 exact request receipt、slot predecessor、reject Event 与 terminal
outcome，并具有 durable exact replay/conflict 语义。

normal 与 glare 的逐字节 known-answer vectors 见
[`contact-round-kat.json`](../../artifacts/fixtures/contact-round-kat.json)；实现必须同时核对 canonical round bytes
与最终 `contact_round_id`，仅比较 object 语义或自行选择 domain 承载形态不算通过。

normal responder 的 `outgoing_slot_absence_digest` 只允许使用以下 closed transcript，计算固定为
`H("ak.contact.no_outgoing_slot.v1", outgoing_slot_absence_transcript)`：

```text
outgoing_slot_absence_transcript = {
  sorted_pair_member_ids: [p0, p1],
  request_slot_owner: responder_actor_id,
  contact_round_id: derived_normal_contact_round_id,
  slot_predecessor: previous_slot_digest_or_null,
  cas_sequence: accepted_local_slot_sequence,
  cas_frontier: [event_ref, ...],
  observed_at: canonical_timestamp,
  outgoing_request_state: "absent"
}
```

`p0/p1` 是 exact pair 的完整 `ActorId` 按 unsigned RFC 8785 JCS bytes 严格升序排列；
`request_slot_owner` 必须恰为其中的 responder，不能是裸 principal 或签名 Station。`contact_round_id` 必须由同一
normal request receipt 和 pair 按本节公式重算。`slot_predecessor` 字段永远存在：genesis slot 使用 JSON `null`，
否则使用刚被 CAS 消费的 exact predecessor digest，禁止省略、空字符串或零摘要。`cas_sequence` 从 1 开始；
`cas_frontier` 非空、无重复并按 EventId unsigned UTF-8 bytes 严格升序，且精确表示该 CAS 观察点，不得替换为数据库
行号、map iteration、当前全局 frontier 或后来的 frontier。`observed_at` 必须逐字等于 receipt 的 `accepted_at`；
`outgoing_request_state` 唯一合法值是字符串 `"absent"`，不存在 null、false、空对象或省略编码。字段名、字段集合和
JCS bytes 必须精确匹配；旧 frontier、pair/round 对调、任何字段遗漏或非 canonical JSON 都必须拒绝。上述正反
known-answer vectors 与 round vectors 同在 `contact-round-kat.json`。

glare admission 不仅需要两张 exact request receipts，还 **MUST** 携 source-signed causal frontier/completeness
evidence，证明两 request 在任一方消费 request ref 前因果并发。仅收到两张 receipt、到达顺序或 wall clock
不足以建立 glare。证据足够时双方机械派生同一 round，禁止 respond/reject且不合成 `ak.contact.accepted`
Event；若双方 current directional full-set scope允许，则直接投影 effective/UI accepted。normal accepted 后晚到的
reverse request 必须由 slot CAS 拒绝，不得改判 glare。

`ContactRoundEvidenceBundle` 是唯一无签名 deterministic bundle，只容纳 derived `contact_round_id`、exact request
acceptance receipts、normal response receipt（normal 分支）、双方 glare concurrency attestations（glare 分支）
以及可刷新的 current checkpoint/completeness/frontier proofs。normal 分支必须有 response receipt且禁止 glare
attestation；glare 分支必须有双方各一张 attestation且禁止 response receipt。两种final bundle都必须有pair双方各一张
current proof；少于两张只能形成非授权的partial/tentative query view，不能冒充portable round evidence。刷新 current proof 不改变 `contact_round_id`。unknown/stale/incomplete evidence 只能产生 tentative；tentative
不能授权 successor、Contact create/send 或 DM authority。

所有 service-signed Contact proof/receipt 的 `issuer_id` 都是 `DidCoreId` Station service authority，并使用
`issued_at`/`accepted_at`/`observed_at` 对应 evidence time 已接受且历史完整的 source service key 验签；它从不表示
pair member。`contact_current_proof` 另签 required `peer: contact_peer`，补全
`(contact_round_id, issuer_id, peer)` lineage key；方向 subject 是 exact pair 中不等于 `peer` 的唯一成员。
bundle 的两张 proof 必须覆盖 `p0 -> p1` 与 `p1 -> p0` 两个相反方向，不能按 issuer 集合或 head author 去重。
非 terminal proof 的 exact head Event author 必须等于方向 subject 且 payload peer 必须等于 signed `peer`；terminal
proof 即使共同指向同一 tombstone head，仍按 signed peer 覆盖两个方向。重复方向、对调 peer、pair 外 peer、同一方向
两个时点快照或错误 service signer全部拒绝。

`glare_concurrency_attestation` 同理签 `subject_id: ActorId`、`peer_id: ActorId` 与
`issuer_id: DidCoreId`。两张 attestation 必须分别是 `p0 -> p1` 与 `p1 -> p0`，issuer 必须是 subject 在
`observed_at` 已接受的 Station service authority；同 core 异 Station与同 Station双账号均按完整 ActorId 独立判定，
不得保留裸 core 兼容分支。

`ak.peer.contacts.command.submit.v1` 是唯一 peer carrier，其 closed XOR 分支分别机器限定原始 signed Event kind为
`ak.contact.requested|accepted|rejected|scope.update|tombstone`并携该分支exact acceptance receipt与允许的
current proof。request分支还必须携closed typed private `introduction_evidence`，其registered digest算法结果必须
逐字等于signed request payload的`introduction_evidence_digest`；该digest固定为
`H("ak.contact.introduction-evidence.v1", exact_introduction_evidence)`。本文的 domain-separated digest 统一定义为：

```text
H(label, x) = "sha256:" + lowerhex(SHA256(UTF8(label + "\n") || RFC8785_JCS(x)))
```

若某字段定义显式指定 decoded ciphertext bytes，则改为 `SHA256(UTF8(label + "\n") || decoded_bytes)` 且不做 JCS。
receipt 中的完整 Event ref、lineage 中的 Event ref 与 current proof head 都必须与同一内层 Event 及分支逐字交叉匹配。所有完整 Event ref 的 digest 都按
[`../conformance/encoding.md` §4.0](../conformance/encoding.md) 从 suite-tagged full-digest EventId 解码，wire **MUST NOT** 再携同源 digest 镜像；验证方仍必须从内层 Event canonical preimage 重算 digest 并与 EventId 比较。carrier只承载
`ak.contact.*`，不得承载 `ak.direct_conversation.bound` 或 Realm Event；Direct Conversation binding 只能走
§5–§7 的 founding admission 与 bootstrap authority。carrier 必须使用 peer Message Signature，并逐字保留内层 bytes；relay
不得重签、改写、拆批或把 tentative 提升为 accepted。其 response 是独立 closed union
`accepted | duplicate | deferred`。五类 signed Event 分支返回逐字匹配该 Event 的 mirror receipt；`glare_finalize`
与 `proof_refresh` 没有 signed Event，必须返回各自 request-kind 绑定的 signed control receipt，绝不能伪造或借用
某个 Event mirror receipt。所有成功响应还必须带 closed `result_kind`，并将实际返回的 attestation/current proof纳入
control receipt的 `result_digest`；它不得复用 self contact
prepare/commit 的 `ContactOperationOutcome`，也不得把 holder-private receive state编码进状态值。
其中 request/response 分支允许携该分支 current proof；缺 proof 时只能保持 tentative，不能授权 projection；
scope/tombstone 分支必须携 current proof；reject 分支没有 round current proof。`glare_finalize` 分支携 exact 两张
request receipts、发送方从对端收到的一张 remote mirror receipt、derived glare Contact round 和发送方 attestation；接收方用
自己本地持有的counterpart mirror receipt补齐交叉验证，只在全部匹配且本地
slot仍未消费时返回自己的 attestation，并在双方 attestation齐备后才可同时返回 current proof。用于该分支的
remote mirror receipt只能是`accepted|duplicate`，`deferred`从不构成authority。无签名 bundle本身永远
不是 authority。`proof_refresh` 必须使用 fresh idempotency key，携目标先前签发的 mirror receipt锁定同一 immutable
inner fact；该prior mirror receipt也只能是`accepted|duplicate`。receiver只可用更鲜且逐字段匹配的
source-signed proof替换旧 proof，不能修改 fact/receipt/round；成功响应必须返回匹配的current proof。
任何不匹配当前 closed XOR 的请求
都必须 schema reject；实现不得协商第二种 carrier，也不得以缺少必需 branch receipt 或 proof 的自定义结构进入
projection。

每个 peer carrier 的 `contact_address` 只有一个身份字段 `recipient: contact_peer`。human 分支携完整
`account_id`；agent 分支携完整 `actor_id + controller_account_id`，不开放 service participant 分支。delivery Station
只从 human `account_id.station_id` 或 agent `controller_account_id.station_id` 唯一派生，并必须与 authenticated
destination service、signed Event author/target 的 exact participant 交叉一致。`subject_id`、`recipient_id`、
`recipient_kind` 及任何裸 host/subject sidecar 都是 forbidden wire。`service_resolution` 与可选
`route_assistance` 只提供该派生 Station 的私有首跳 transport material，不进入 durable Event、projection、member cell
或长期 authority；替换路由材料不能改变 participant identity。

## 3. Directional scope、current head 与终态

Contact scope 只表达 issuer holder 授予 peer 的方向，唯一字段为 `granted_to_peer_scopes[]`。scope update 的
唯一 fact 是 `ak.contact.scope.update`，唯一 self operation 是
`ak.self.contact.command.scope_update.v1{phase=prepare|commit}`。payload closed 绑定完整 peer XOR、round、version、
predecessor 与完整 scope 集合；扩大和收窄都必须由 holder 显式签名。tombstone 只终止 Contact，不承担 scope
update。

scope full-set replacement 为空仅把非 terminal round 投影为 `suspended`；同一 lineage 后续显式 widen 可恢复。
proposal 阶段 reject 与 accepted round 上 tombstone 是 terminal；terminal 后 constituent request refs、round 与
lineage 永不复活，recontact 必须创建全新 request receipt(s)与新 round。

source service 必须对每个 issuer lineage 签 monotonic head checkpoint/current lease，逐字绑定 current head、
accepted frontier、`complete_through` 与 `fresh_until`。peer mirror 保留 source signed fact、lease/checkpoint 与
transport receipt；收到更高 incoming signed head时 target service 立即撤销旧 mirror，不等待轮询。stale/unknown
current proof仅阻止 Contact-based create/send：existing binding resolver仍返回原坐标，并在 `found.send_blockers[]`
报告 `contact_scope_stale`。proof stale 绝不把 accepted round 回滚为 pending，也不得隐藏 participant 坐标。

`ak.self.contact.read.list.v1` 的 `contact_list_row` **MUST** 用封闭子对象 `next_prepare_input` 承载下一次写入的输入。其
`contact_round_id`、`version`、`predecessor_event_ref` 三个字段与 `ak.self.contact.command.scope_update.v1` /
`ak.self.contact.command.tombstone.v1` 的 prepare 分支逐字同名，客户端 **MUST** 原样抄入，**MUST NOT** 改名映射、重算或
另行推导。容器名承担时态消歧：其中的 `version` 是**下一条 Event 要携带的**版本号，即 current head version + 1，故最小值
为 2；`predecessor_event_ref` 是**当前 lineage head 的 Event ID**，即下一条 Event 的前驱，而不是当前 head 自己的前驱。
同一 row 的 `request_event_ref` / `response_event_ref` / `tombstone_event_ref` 只是投影摘要，**MUST NOT** 被当作权威
链头拼装 successor。

该子对象只在能 author 后继时出现，省略本身就是“现在不可 author”的表达，**MUST NOT** 为此另造 error code 或扩充
`contact_state`。按 `contact_state` 逐值判定：`accepted` **MUST** 携带；`pending_outgoing`、`pending_incoming`、
`rejected`、`expired`、`tombstoned` **MUST NOT** 携带——前两者尚未建立 round 与 lineage，后三者是 terminal 且 round 与
lineage 永不复活。glare 机械派生的 round 直接投影为 accepted 时同样 **MUST** 携带，此时 `predecessor_event_ref` 是该
issuer 自己的 request head。若该 issuer-local lineage 尚无任何带版本号的 accepted successor，则这个 request head 是
bootstrap predecessor，`next_prepare_input.version` **MUST** 为 2；验证方 **MUST** 把“逐字等于该 issuer 自己的 request
Event ID 的 predecessor + version 2”作为 glare founding edge 的唯一合法首个 successor，**MUST NOT** 因 request payload
没有 lineage `version` 字段而拒绝，也 **MUST NOT** 合成一条 version 1 的 `ak.contact.accepted` Event。首个 successor 之后
恢复普通规则：`version = current head version + 1` 且 predecessor 逐字等于 current head Event ID。
scope 全集替换为空只把非 terminal round 投影为 `suspended`，其 `contact_state` 仍是
`accepted`，因此仍 **MUST** 携带该子对象，否则后续显式 widen 无从 author。

游标可能陈旧。服务端 prepare 侧已有 `contact_lineage_conflict`（409）与 `contact_scope_stale`（409），持陈旧游标的
prepare 只会被拒且零写入；被拒后客户端 **MUST** 重读 `ak.self.contact.read.list.v1` 并以新值重试，**MUST NOT** 猜测
lineage，也 **MUST NOT** 以同一组值重试。本条的规范执行向量是 `ak.vector.contact.next_prepare_input.v1`。

`pending_incoming` row **MUST** 携带 `request_event_ref`；`request_message` 的存在性及内容 **MUST** 与该 exact 已验证 request Event 的 `message` 一致。其它状态 **MUST NOT** 携带 `request_message`。列表是自己 Station 在已认证 holder 会话下提供的结果，客户端不取得原始 request Event 或远端 receipt 重新验证。

respond/reject prepare **MUST** 提交列表的 `peer` 与 `request_event_ref`。peer 使用完整 ActorId 的 Account/service 坐标，远端服务解析由 Station 持有与验证，不经列表交给客户端。Station 以已认证 holder 和 exact peer 查询私有 durable Contact 记录，确认引用对应当前可回应的 incoming proposal，再从记录加载已验证 receipt；字段不是 bearer 权限。客户端签署前 **MUST** 核对 draft 的 actor、peer、request Event 引用、动作与所选 scopes。服务端 commit **MUST** 在同一事务中复核 reservation 和当前 slot；陈旧引用、错 holder、错 peer、glare 或终态请求零写入拒绝，客户端重读列表，不猜测或重放已消费输入。

glare 在证据齐备前保持 `pending_outgoing`，齐备后直接投影 `accepted`，两者都不可 respond/reject。实现 **MUST NOT** 因收到并发 request 将已有 outgoing proposal 改判 `pending_incoming`，也不为不可回应另造 `contact_state`。

**Contact verified mirror（normative）**：接收服务器 **MUST** 在 ingest 时验证 canonical Event ID/digest、producer proof、origin Station admission、receipt 签名、`accepted_at` 时点 issuer service key，以及 exact Event/actor/peer/target holder 绑定，随后将 exact signed Event bytes、receipt 和 verified 记录 CAS 耐久提交。未完成任一项的材料不能进入可回应列表。

mirror 是 principal-private 存储，**MUST NOT** 进入接收方 canonical Realm Event store 或推进 reducer、Seal、CBS frontier、`state_root`；仅供服务器 prepare、联邦和审计使用。self/peer Event resolve **MUST NOT** 以 Contact mirror 或 receipt 赋予 requester PCR 读取权限。移出 `pending_incoming` 后列表不再返回申请附言；私有材料可按 retention 保留。

本条规范向量为 `ak.vector.contact.pending_incoming_prepare.v1`。客户端与服务器职责见 [账号服务器信任与结果消费](../sync/server-trusted-results.md)。

不存在、policy deny、过期、未授权与 quarantined 对无权主体必须使用相同 opaque failure。

## 4. Contact operation surface

所有非 public `ak.self.*` operation 的同一个 OpenAPI security object **MUST** 同时要求 bearer 与 DPoP；HTTP
Message Signature只能额外叠加，不能替代其中任一项。实现 **MUST** 登记并实现下列 closed operation：

| operation | 语义 |
| --- | --- |
| `ak.self.contact.command.request.v1` | prepare/commit 原始 signed request与 request acceptance receipt |
| `ak.self.contact.command.respond.v1` | 只执行 normal accept；要求 responder slot 无 outgoing，不接受 reject action |
| `ak.self.contact.command.reject.v1` | 独立 proposal terminal reject与 rejection receipt；不得复用 respond body |
| `ak.self.contact.command.scope_update.v1` | issuer-local full-set replacement |
| `ak.self.contact.command.tombstone.v1` | accepted round terminal，已接受的 predecessor refs 永久消费 |
| `ak.self.contact.read.list.v1` | 从 verified Contact round evidence 与双方 directional current heads 投影；accepted row 另携 §3 的 `next_prepare_input` 游标，`pending_incoming` row 携带 §3 的 exact request 引用及申请附言；显式 `include_continuity=true` 才导出完整 continuity evidence |
| `ak.peer.contacts.command.submit.v1` | closed XOR peer carrier；原 bytes + exact receipt/current proof |
| `ak.self.direct_conversation.read.resolve.v1` | §9.1 的唯一 DM 查询入口；closed outcome，不携 create phase 分支 |
| `ak.self.events.command.submit.v1` | 其 `direct_conversation_founding` branch 是 §5.5 的唯一 DM founding 提交入口 |
| `ak.peer.events.command.submit.v1` | 其 `direct_conversation_founding` branch 是 §5.6 的唯一 DM founding 联邦入口 |

创建由 §5 的 `ak.realm.create` founding admission 承担，查询由上表的
`ak.self.direct_conversation.read.resolve.v1` 承担，二者 **MUST NOT** 合并为一个带 `create=true` 的 operation。

所有 transport binding **MUST** 逐字段等值，不能自行增加 `accepted`、兼容 consent shape、unsigned service row
或第二轮 assignment。

**首次接触 message 的封闭约束（normative）**：`ak.contact.requested` 的 `message` 是未获同意文本，本条约束的是
**投递面**，不是 exact target holder 的可见性。接受前它 **MUST NOT** 进入任何 Strand、message timeline、未读
计数、消息搜索索引或推送正文；跨服务器投递与一切 non-Contact projection **MUST** 以 stub 替换。它 **只**能经
`ak.self.contact.read.list.v1` 的 `pending_incoming.request_message` 向 **exact target holder** 呈现完整内容。附言与 `request_event_ref` 必须来自同一已验证 Event；服务器不得用其它内容替换。

stub 不是加密措施：`message` 是 digest-covered 明文，requester Station 持有它。Contact 建立前没有共享密钥，v1 不将该字段改为密文。客户端信任自己 Station 的申请投影，并核对回应草稿绑定其所见申请。

## 5. Direct Conversation founder 派生与创建授权

### 5.1 pair identity

同 trust domain 下两个 exact `ActorId` 先分别序列化为 RFC 8785 JCS，再按 unsigned JCS bytes 排序为 `[p0, p1]`。`pair_key` **MUST** 在任何 Realm 存在前即可计算，因此固定使用 SHA-256 与 RFC 8785 JCS，**MUST NOT** 读取任何 Realm 自报的 digest suite：

```text
pair_key = sha256(UTF8("ak.direct-conversation.pair-key.v1\n") ||
                  JCS({"trust_domain_id": <id>, "participants": [p0, p1]}))
```

handle、display name、设备 ID、endpoint、Realm ID、Strand ID 与 Contact Event ID **MUST NOT** 进入前像。裸 `principal_id`、裸 DID 与 unresolved pairwise DID 也不是参与者身份；账号参与者必须使用内含 `station_id` 的完整 `AccountId` 分支。双方 **MUST** 从 Event 中的 exact participants 与 trust domain 重算 `pair_key`，**MUST NOT** 采信 caller 自报值。实现 **MUST** 执行 [`ak.vector.direct_conversation.pair_key.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT；无 domain separator 或把 `trust_domain_id` 改名为 `trust_domain` 的旧前像均不是 v1 `pair_key`。

### 5.2 founder 派生（normative）

同一 pair 的 Direct Conversation Realm **MUST** 由且仅由从该 pair 的 **root Contact round** 确定性派生出的 `founder` 创建。派生只读 §2 已定义的 `contact_round` core，不引入新字段：

```text
founder(contact_round) =
    normal 分支 -> sorted_pair_member_ids 中不等于 request_event_ref 之 author/requester 的那一方（即 responder）
    glare  分支 -> requests[0].request_event_ref 之 author/requester
```

**normal 分支取 responder 而非 requester 是 normative 选择**：Contact round 由 responder 的 `normal_response_acceptance_receipt` 点亮，该 receipt 证明 responder 在该 round 成立时在线且刚完成签名；requester 可能在数日前发出请求后即长期离线。base v1 不定义 fallback（§5.7），因此把 founder 定为可能不在场的一方会使该 pair 永久无法创建。

glare 分支不存在 responder；`requests[0]` 是 §2 按完整 `request_event_ref` wire 字符串的 UTF-8 unsigned bytes 严格升序排列后的第一项。founder 是该项引用的 signed request Event 的完整 author `ActorId`，不是 receipt 的 Station `issuer_id`，也不是 `sorted_pair_member_ids[0]`。到达顺序、墙钟时间、请求发起先后及收据摘要都不参与选择，**MUST NOT** 另立排序规则。

以上两条 Contact founder 规则用于 human↔human 和需要 Contact consent 的 Agent↔第三方分支。controller↔自己的 owned Agent 不走 Contact 邀请／接受／glare，按 §5.4 从已接受且 current 的 provision/controller binding 固定 `founder=controller`；Agent 配对只建立 runtime 授权，不创建聊天 Realm。

双方只有各自 outgoing request、尚未取得完整有效 round evidence 时均没有 DM 创建权。normal accept 的本地 slot CAS 必须证明不存在 outgoing request；glare 的双方 causal/completeness evidence 未齐时只可等待，不得按本地可见请求分别建立 normal round。网络超时不得授予另一方 fallback/takeover 创建权。完整证据确定同一 founder 后，才由其 current Station 按 §5.5 原子关闭唯一 founding slot；本地数据库锁本身不承担跨 Station 选择 founder 的职责。

`sorted_pair_member_ids` 不恰为二、request Event author/requester 不属于该 pair、glare requests 未按登记顺序或两个 requester 不构成该 pair 时，founder 派生 **MUST** 失败并整组拒绝，**MUST NOT** 以补集或本地偏好猜测。这里的 author/requester 是 signed Event 的完整 `ActorId`，不是 service-signed proof/receipt 的 `issuer_id`。

### 5.3 root Contact round 与 recontact continuity

founder **MUST** 从该 pair 的 **root Contact round** 派生，而非从 current round。tombstone 后 recontact 产生的新 round **MUST** 在其 request/receipt 中承诺 `previous_terminal_contact_round_id`；receiver **MUST** 沿该链求出唯一 root round，并从该 root round 派生 founder。

该指针的 wire 规则是封闭的：根 request Event 与根 acceptance receipt 都 **MUST** 省略 `previous_terminal_contact_round_id`；recontact 的 request Event、source request acceptance receipt、以及 normal response acceptance receipt **MUST** 都携带同一个“紧邻上一轮 terminal round”的 `contact_round_id`。glare 分支的两个 request Event 与两张 source acceptance receipt 也 **MUST** 携带相同指针。`slot_predecessor` 只表示签发服务内部 request-slot 的 CAS 前驱，**不是**跨轮 continuity 指针，二者不得互相替代。

`contact_round_continuity_chain` 按 current → immediate predecessor 向旧方向排列；64 是最近 mutually signed checkpoint 之后的**未压缩尾段**上限，不是一段关系终身最多 recontact 64 次。没有 checkpoint 时，尾段最后一项必须且只能是省略 predecessor 指针的 root。存在 checkpoint 时，尾段最后一条边必须精确终止于 `checkpoint.core.covered_through_contact_round_id`，不得再携已压缩 prefix。该字段是轮次标识而不是 bundle 内容摘要；被压缩 bundle 的内容摘要只进入 `prefix_accumulator_root`。每一段 predecessor bundle 的两张 `contact_current_proof` 都 **MUST** 令 `terminal=true`，共同证明该 round 已 tombstone；当前 active round 的 proof 则 **MUST** 为 `terminal=false`。每条边必须逐字节满足“后继 core/receipt 的 `previous_terminal_contact_round_id` 等于下一段 bundle 的 `contact_round_id`”。proof 对完整 closed object 签名，因此 `terminal` 也在签名 transcript 内。

prefix compaction 只使用 `bilateral_continuity_checkpoint` 这一通用机读合同，不定义 Contact 专用 accumulator：core 封闭承诺 canonical 排序的两个 `(principal_id, station_id)`、可移植 root basis、覆盖至哪个 terminal `contact_round_id`、域分离 prefix accumulator root、覆盖数量、单调 `sequence` 与前一 checkpoint digest；checkpoint digest 是 `H("ak.bilateral-continuity.checkpoint.v1", canonical core)`，两张签名也覆盖同一域分离 core bytes，且 `signatures` 必须恰好由两个 participant authority key 各签一次。实现需要 root basis 摘要时只能按 `SHA-256(JCS(root_basis))` 即时派生；该值不是 wire 字段，也不得持久化为另一份 continuity 状态。单边签名无效；同 sequence 不同 digest 是 fork，**MUST NOT** 按到达时间或 digest 大小选 winner；sequence 回退、previous digest 不连续、root/pair 改写或 accumulator 不符均为 `continuity_invalid`。上述边界与派生公式由 conformance vector `ak.vector.contact.bilateral_continuity_checkpoint.v1` 锁定。

checkpoint issuance 复用现有 Contact 机器面而不再建立一套三阶段提交协议。holder 对 `ak.self.contact.command.checkpoint.v1` 提交 peer 与 idempotency key；本地 Station 从已接受的 terminal history **机械选择**最老的连续 prefix，构造 core、以本地 participant authority 签名，并把单签 proposal 作为 `ak.peer.contacts.command.submit.v1` 的 `continuity_checkpoint` 闭合分支 durable 发送。接收方必须先重算 root、边界、accumulator、sequence、previous digest 与双方 authority pair，再验证 proposer service signature；随后在一次 CAS 中追加自身签名并提交完整 checkpoint，才可返回 `accepted`。发起方只在验证返回的完整 checkpoint 与原 proposal 逐字节同 core/digest、两张 service signature 都有效后提交。响应丢失时以相同 idempotency key 和相同 proposal 重试，接收方返回已持久的同一完整 checkpoint；**没有**另一个 countersign endpoint 或 commit endpoint，也不存在“已共签但尚未提交”的第三状态。同 sequence 异 digest 在任一侧永久记为 fork 并 fail closed。

self request prepare 不携带客户端自选的前驱坐标。普通在线 recontact 由 Station 从自身耐久状态选择同一 exact pair 的 immediate terminal predecessor、相同 lineage 的 committed checkpoint 与精确未压缩尾段；客户端不搬运服务器已有 evidence。`ak.self.contact.read.list.v1` 仅在显式 query `include_continuity=true` 时导出 `continuity_evidence`，默认省略；缺省或 `false` 不构造完整 export。显式导入复用 request prepare 的可选 `continuity_evidence`，服务器完整验证签名、exact pair、root 和 tail，并与本地 sequence/digest/root 比对，不能接受 rollback/fork；导入前驱来自已验证 tail 首项且必须匹配本地已知终态。较新 checkpoint 必须连接本地 checkpoint 的下一 sequence 和 previous digest，否则不得跳过未证明的中间关系。服务器将所选前驱写入 draft，commit 再核对当前 slot，不修改已签 Event。未提供导入对象时服务器使用本地材料，不能因此创建不声称 continuity 的新 lineage。pending proposal、单签与 projection 摘要不得导出。

每次 checkpoint 成功后双方 Station **MUST** 耐久保存当前 committed checkpoint 与尚需的 bounded tail，并使 holder 可显式导出；不要求永久保留已压缩 prefix。checkpoint、前一 checkpoint 或尾段暂时取不到时只返回固定 409 `continuity_evidence_unavailable`，取回/导入 exact evidence 后可重试；密码学、root、pair、rollback、fork 或断链错误返回固定 409 `continuity_invalid`，不得降级成“稍后重试”。两个 outward bucket 共享相同 RFC 9457 Problem Details 尺寸类、无 target-sensitive header，且不披露缺哪段、错哪方或内部 Contact 状态。无法取得双签 checkpoint 且尾段已满 64 时，该 exact pair 的 lineage MUST 暂停新增 recontact，返回 `continuity_evidence_unavailable`。相同 trust domain 与完整 ActorId pair MUST NOT 通过省略前驱、声明不连续、重置 slot 或另建 root 绕过此限制；已有唯一 founding slot 与 Direct Conversation 保持不变。恢复只能取回或显式导入该 lineage 的有效材料，或完成双签 checkpoint。至少一方经既有合法身份流程取得不同的完整 ActorId 后，用户 MAY 明确向新的 exact pair 发起普通首次联系；服务器和客户端 MUST NOT 自动更换身份。新 pair 的 root、pair_key 与 founding slot 按普通首次联系规则产生，不继承旧 history、audit identity、checkpoint、Direct Conversation、MLS state、历史授权或带外设备验证状态。此分支不新增 reset/continuity 开关。

断链、多根、成环、跳过非 terminal round、或两个 directional proof 导出不同根，**MUST** 拒绝创建与回放。current recontact 的 responder 即使与根 round 的 responder 不同，也 **MUST NOT** 取得创建权。Realm 一经 accepted，founder 身份只保留为 founding 审计与 §7.2 bootstrap authority 的 actor 约束；日常 authority、repair 与 recontact **MUST NOT** 再读取它。

### 5.4 create 判别与授权

`ak.realm.create` 的 conditional admission **MUST** 登记两个结构互斥的 Direct Conversation variant，判别器为 critical ref role：

| ref role | admission variant | 适用分支 |
| --- | --- | --- |
| `direct_conversation_contact_round` | `direct_conversation_genesis` | human↔human、Agent↔第三方 |
| `direct_conversation_agent_provision` | `direct_conversation_agent_genesis` | controller↔自己的 owned Agent |

两个 role **MUST** exact XOR。Agent PCR genesis 只按 `payload.object.purpose="agent_control"` 选择 `delegated_pcr_genesis`，并在准入时反查 accepted `ak.agent.provision` 的前向声明（见 [`./key-management.md` §3.6.3](./key-management.md)）；它没有 ref role 判别，因此这里的两个 DM role **MUST NOT** 与之混用。DM variants、PCR variants 与 ordinary Realm 的 `when` 条件 **MUST** 结构互斥；零命中或多命中 **MUST** `schema_violation`，**MUST NOT** 按 registry 顺序取第一条。

`direct_conversation_genesis` **MUST** 逐项验证，任一不符整组零写入：

1. 该 ref 指向完整 portable Contact round evidence bundle 及至 root Contact round 的 continuity chain，`contact_round_id`、normal/glare core、request/response receipts 或 glare attestations、terminal links 与双方 proofs 均可验证；
2. 按 §5.2/§5.3 求出 `founder`；
3. `created_by == actor_id == founder`（追加约束，**不**放松既有 `created_by == actor_id`）；
4. payload 的 `pair_key` 等于从 round 的 `sorted_pair_member_ids` 与 trust domain 重算之值；
5. Realm profile 为 `ak.profile.direct_conversation_realm.v1`，`collaboration_role="direct_conversation"`，effective participants 恰为该 pair；
6. §6.2 的固定 baseline 投影全部命中；
7. 该 `realm_id` 无对象身份冲突。

**accepted-at 与 current gate MUST 分开求值**：source self admission 在 slot commit 线性化点要求两条 directional current heads 共同引用该 current round、授予 `direct_message` 且 fresh；peer replay 只验证这些 proof 在 source receipt 的 `accepted_at` 时有效并被 receipt digest 绑定。因此即使 Event 到达时 Contact 已撤回，peer 仍 **MUST** 接受该历史 Realm identity，并以 current gate 投影 `suspended`；否则 Event 有效性会依赖投递顺序。

`direct_conversation_agent_genesis` 改验 participants 恰为该 controller/Agent、profile 为 DM 而非 PCR、`ak.agent.provision` 已 accepted 且 controller binding current，并令 `founder = controller`。Agent 与第三方之间的 DM 仍 **MUST** 使用该 pair 的 current Contact round，**MUST NOT** 以 provision 绕过第三方 consent。

controller-Agent founding material 的 `controller_binding_digest` MUST 为 accepted `ak.agent.provision` 的完整 typed payload 的 RFC 8785 JCS 字节的 SHA-256（`sha256:<lowercase hex>`）。该 payload 绑定 Agent、controller、PCR、delegation、accountability 与 scope；不得对本地数据库记录、完整 Event envelope 或运行时状态计算该值。resolver 与 admission MUST 使用同一共享 SDK 算法；admission MUST 从本地 accepted provision 重算并比较，不能信任 caller 回传的摘要。current controller binding 仍独立验证，不得用摘要相等代替。

### 5.5 caller-authored founding unit、source 唯一 slot 与 acceptance receipt

四条 Event 的 ID 都是各自 canonical Event preimage 的完整 digest（[`../conformance/encoding.md` §4.0](../conformance/encoding.md)），`realm_id` 与 `main_strand_id` 又分别是第一条与第四条 Event ID 的重类型（[`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)、[`../models/common-fields.md` §6.0](../models/common-fields.md)）。因此在 canonical preimage 完成之前**没有任何主体能"分配"这两个 ID**：服务端预分配、reserved/materializing draft、coordinator 选举与 caller 自选 ID 全部 **MUST NOT** 出现在本流程。founding **MUST** 采用 caller-authored first-valid unit：

1. founder caller author `ak.realm.create`（envelope 省略 `realm_id`、`scope_ref` 为 `{"kind":"realm_genesis"}`，payload 省略 object id），完成 canonical preimage 后派生其 Event ID，并重类型得到 `realm_id`；
2. 以该 `realm_id` author founder 自己的 `ak.member.state{join}`，携 member cell 的 `head_eq null` genesis precondition；
3. author 另一 participant 的 `ak.member.state{join}`；controller/Agent 分支显式携带绑定第 2 条的 `agent_controller_binding`；
4. author `ak.strand.create`（payload 不携 `strand_id`），由其 Event ID 重类型得到 `main_strand_id`；
5. 四条全部由 founder 签名，按该 wire 顺序构成 exact ordered unit 一次提交；不存在 server-created draft、reserved Event ID 或第二次 authoring 机会；
6. 网络结果不明时 caller **MUST** 重放逐字节相同的 signed bytes，**MUST NOT** 重新 author 另一组 Event。

`founding_unit_digest` 是该 unit 的唯一稳定标识，按 §2 的 `H` 定义为：

```text
founding_unit_digest = H("ak.direct-conversation.founding-unit.v1",
                         {"event_ids": [realm_create_event_id,
                                        founder_member_join_event_id,
                                        peer_member_join_event_id,
                                        strand_create_event_id]})
```

四个 Event ID **MUST** 按 §6.1 的 wire 顺序列出，**MUST NOT** 排序、去重或替换为 digest。该值不进入任一 unit Event 的 preimage，因此不存在自指；receipt 与 `ak.direct_conversation.bound` 只引用它。实现 **MUST** 执行 [`ak.vector.direct_conversation.founding_unit.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT。

founder 的 current Station **MUST** 以本地唯一约束保证同一 `(founder_id, trust_domain_id, pair_key)` 至多一组 founding unit 被 accepted。self admission **MUST** 在同一事务内完成：确认该 pair 尚无 accepted DM Realm、CAS 占用 slot、按 §5.4 与 §6 完整验证四条 Event、round 与派生坐标、零项或四项原子接受、签发 `DirectConversationFoundingAcceptanceReceipt`、写入 peer-delivery outbox。acceptance **只固定 caller 已派生的坐标**，**MUST NOT** 分配、替换或重新协商任一 ID；receipt 是该事务的输出，**MUST NOT** 循环要求 caller 预先携带。

receipt **MUST** 绑定 `pair_key`、完整 `founder_id: ActorId`、`realm_id`、`main_strand_id`、`founding_unit_digest`、分支化 authorization core（human 为 current/root Contact round 与 evidence digest；controller↔Agent 为完整 provision Event ref 与 controller binding digest）、issuer service ID、`accepted_at` 与 proof。provision digest 必须从 suite-tagged full-digest `agent_provision_ref` 解码，wire **MUST NOT** 另带 `agent_provision_digest`。receipt 的存在本身即证明本地唯一 slot 与 founding unit 在同一事务内提交，不重复布尔回声。四条 accepted Event 的 exact author `ActorId` 与 admission proofs 是 founder authority 的唯一 carrier；不得再加 Event server sidecar。它 **MUST NOT** 创建 Realm、授权 Message 或充当全局 slot；它只让 peer verifier 确认 founder 当时的 current service 已原子接受该 unit 并关闭本地唯一 slot。


`proof` 的签名 transcript 是唯一封闭前像，按 §2 的 `H` 固定为：

```text
founding_receipt_transcript = H("ak.direct-conversation.founding-receipt.v1",
                                receipt 去掉 proof 后的完整 closed object)
```

`proof.verification_method` **MUST** 解析为 `issuer_id` 在 `accepted_at` 时的 current service key，
`proof.created_at` **MUST** 等于 `accepted_at`。receiver **MUST** 从 receipt 自身字段重算该 transcript 再验签，
**MUST NOT** 采信任何随 receipt 传来的预算 digest；这使 byte-identical retry 与两个独立实现必然得到同一
transcript 与同一签名输入。receipt 或 `ak.direct_conversation.bound` binding fact 的 issuer、`pair_key`、
authorization basis、Realm role、exact two-member set、main Strand、`founding_unit_digest` 或 founding MLS
引用任一无效时，verifier **MUST** 拒绝该 binding（reason `direct_conversation_binding_invalid`）。

carrier 是 `ak.self.events.command.submit.v1` request union 中显式登记的 discriminated branch
`DirectConversationFoundingUnitSubmission`（discriminator `unit_kind="direct_conversation_founding"`）：它精确要求恰好四条按 §6.1 顺序排列的 `EventInitialSubmission` 与 `idempotency_key`，不携带 `founding_authority_evidence`——founder 的 current Station 在同一 admission 事务内以自己 current 的 Contact round / Agent provision 证据校验该 unit（§9.1.1），并在 response union `SelfEventsSubmitOutcome` 中返回 `DirectConversationFoundingAcceptanceOutcome`。每条 Event 的实际 author `ActorId` 必须路由到接收服务，服务端只在完整本地准入后追加 admission proof。实现 **MUST NOT** 新增私有 endpoint、复用普通 batch 分支或让服务端代签 producer Event；`ak.self.direct_conversation.read.resolve.v1` 继续 query-only，**MUST NOT** 承载 create。

幂等与 crash/restart 语义 **MUST** 如下封闭：

- 同 `idempotency_key` 且同 `founding_unit_digest` 的 exact retry 返回 byte-identical receipt 与相同 `event_ids`，且 **MUST NOT** 推进 `accepted_at`；
- 同 `idempotency_key` 但不同 `founding_unit_digest` 返回 `duplicate_conflict` 且零写入；
- 本地 slot 已被同 pair 的另一组 unit 关闭时返回 `conflict` 与 `direct_conversation_slot_already_committed` 且零写入，caller **MUST** 改用 §9.1 resolver 取回既有坐标；服务 **MUST NOT** 接受第二组 unit，也 **MUST NOT** 把它降级为 partial 或 quarantine；
- 客户端已派生 ID、unit 已提交、四 Event 已落库、receipt 已签发、outbox 已入队与响应丢失这些崩溃点，重放同一 signed bytes **MUST** 收敛到同一 receipt、同一坐标与同一 outbox 条目，**MUST NOT** 产生第二组 Event、第二张 receipt 或第二个 slot。

相同 pair/founder 但不同 unit 的第二张 receipt 是 §5.7 冲突证据。

### 5.6 联邦例外

Realm 尚不存在时无法取得普通 member federation authority，因此 Direct Conversation founding exception 只允许 Contact round 中完整 founder `ActorId` 所路由的服务向 invitee 自己的 Station 投递该 atomic unit、source acceptance receipt 与 bounded founding-authority dependencies。接收方必须验证 transport source、四条 Event actual author 的 route、producer proof 与 origin admission proof 一致，并要求目标 pair 命中本地 Contact round；不得要求或比较 PCR id/genesis receipt。

该例外的 carrier **MUST** 是 `ak.peer.events.command.submit.v1` request union 中显式登记的 discriminated
branch `DirectConversationFoundingFederationSubmission`（discriminator
`unit_kind="direct_conversation_founding"`），承载恰好四条按 §6.1 顺序排列的 `EventFederationSubmission`、
source `DirectConversationFoundingAcceptanceReceipt` 与 bounded dependencies；实现 **MUST NOT** 新增私有 peer
endpoint，也 **MUST NOT** 用普通 Realm batch 分支夹带该 unit。该 branch 是 registered atomic unit：dependency
不足时 **MUST** 用 top-level HTTP 409 `dependency_missing` 与 `EventsDependencyMissingProblem` 并零写入，
**MUST NOT** 退化为 per-item partial，也 **MUST NOT** 只接受其中一或两条。

Realm 在对端 accepted 后立即回落普通 federation 规则。因 §5.4 第 3 条已钉死作者，该例外不需要方向性约束。

### 5.7 无 fallback 与 pair materialization conflict

base v1 **MUST NOT** 定义 timeout fallback、takeover lease 或 `founder_fallback_window`。仅凭"本地与对端当前都没看到 Realm"不能证明 founder 没有 accepted 但尚未送达的 Realm；旧 founder 创建权未被全局可验证且不可逆的 fence 关闭前，non-founder 创建可能与迟到的 founder 创建同时合法。因此 timeout、HLC、到达顺序、Realm token 的词法大小与一次 negative query **MUST NOT** 改变 founder authority。

base v1 同样 **MUST NOT** 定义 Direct Conversation 专用的 founder succession、root-committed
recovery authority、recovery generation 或 versioned successor pair coordinate。设备、恢复材料或
Station 暂时/永久不可用都不会把 founder authority 转移给另一 participant、第三方或双方事后
共同指定的 successor：

- 若既有账号、设备与 Station 恢复机制让**同一**
  `(principal_id, station_id)` 重新满足 current authority proof，原 founder 只是恢复了控制，
  仍可按原 slot 创建；这不是 succession，也不产生新的 DC 状态或 Event kind。
- 若该 exact authority pair 始终无法恢复，同一 stable participant pair 的 resolver 继续返回
  `awaiting_founder`。该状态对 non-founder 是协议终局：等待、重试、双方事后双签、第三方 attestation
  与 recovery capability 都不能推进 slot。由于“永久丢失”不可由一次网络观测证明，wire **MUST NOT**
  新增 `founder_unrecoverable` 或把本地放弃判断伪装成共识事实。
- v1 中新的 Direct Conversation 只能来自实际不同的 stable participant pair（或不同 trust domain），
  因而按 §5.1 自然得到不同 `pair_key`。实现 **MUST NOT** 给同一 pair 添加 salt/generation 来制造
  successor coordinate，也 **MUST NOT** 把新 pair 的 history、MLS state、keys、audit identity 或
  founding receipt 表述为旧 lineage 的继承。

Realm 已 accepted 后，founder 身份按 §5.3 不再参与日常 authority。后续 signer/device/material 丢失只走
§8.2 与通用 principal/device 恢复；它 **MUST NOT** 重新开启 founder succession。若未来定义跨
`principal_id` 或 `station_id` 的连续性，必须先登记通用 principal/service succession 合同，再由
所有 domain 统一消费；v1 不为 Direct Conversation 局部预埋该能力。

本节的规范执行向量是 `ak.vector.direct_conversation.founder_loss_terminality.v1`；runner 必须覆盖
exact authority 恢复、四类替代 authority 零写入拒绝，以及新 stable identity 导出不同 pair 且不继承
旧 lineage 三条路径。

若仍观察到同 pair 第二个 **accepted** Realm：

1. 先判定是否只是非 founder、旧 round 或旧 service 产生的无效 bytes；无效对象 **MUST NOT** 进入 discovery、binding 或 Message authority，也 **MUST NOT** 被称为 candidate；
2. 若两条都携看似合法的 founder admission 与 source receipt，则受信 service 的 slot、cutover fence 或签名发生 equivocation。pair **MUST** 进入 `direct_conversation_pair_materialization_conflict`，冻结两边新的 Message/membership/policy/MLS/binding；
3. **MUST** 保留两组 founding unit、receipts、service-binding/cutover proofs 与本地 slot 证据；**MUST NOT** 自动取 min、tombstone 任一 Realm、搬移历史或让 UI 选择一边继续；
4. 只有另行登记、能证明唯一 canonical founding unit 且不复活已终结历史的 recovery 协议可以解除。本规范不提供该协议。

## 6. Founding unit 与固定 baseline

### 6.1 四 Event atomic unit

founder **MUST** 一次提交恰好四条 Event：

```text
1. ak.realm.create        携 §5.4 的 critical ref；不承载 membership 边
2. ak.member.state{join}  subject 为 founder 自身；genesis write，head_eq null
3. ak.member.state{join}  subject 为另一 participant 的显式 canonical membership
4. ak.strand.create       main Strand，scope_circle_id=null，primary discussion track
```

四条注册为 `ak.profile.direct_conversation_realm.v1` 的 closed atomic founding unit：按 wire 顺序验证，同一事务零项或四项接受。create-alone、缺 peer join、缺 Strand、缺 founder join、乱序、不同 actor/pair/profile/Realm 或出现第五条 Event **MUST** 拒绝整组。四条 **MUST** 由 founder author，并使用同一分支 context（`direct_conversation_contact_round` 或 `direct_conversation_agent_provision`，exact XOR），叠加同批 staged authority-root proof。

该顺序同时是 §5.5 的派生顺序，不是可选排版：第 2、3、4 条的 `envelope.realm_id` **MUST** 逐字等于
`retype(第 1 条 event_id, "realm")`，`main_strand_id` **MUST** 逐字等于 `retype(第 4 条 event_id, "strand")`，
第 2 条的 `prev_refs` **MUST** 引用第 1 条、第 3 条 **MUST** 引用第 2 条、第 4 条 **MUST** 引用第 3 条。验证方 **MUST** 从 unit 自身 bytes
重算这两个坐标，**MUST NOT** 采信请求中另行携带的坐标字段，也 **MUST NOT** 接受任何声称先分配后签名的
提交形态。本段任一条件不成立 **MUST** 以 `direct_conversation_founding_unit_invalid` 整组零写入拒绝。

四条的 CBS basis 形态是封闭的：`ak.realm.create` 用 genesis bootstrap shape；两条 `ak.member.state{join}` 与
`ak.strand.create` 在**且仅在**该 exact unit 内使用 bootstrap no-basis shape（既不携 `seal_basis`，也不携
`seal_ref`/`auth_context`），并叠加同批 staged authority-root proof。两者的免 basis 落点分别登记在
[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md) 与
[`../authz/event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md) 的封闭列表。
`ak.strand.create` 平时是携 `seal_ref + auth_context` 的 DataEvent，batch admission **MUST** 在本 unit 之外
拒绝它的 no-basis 形态。

Genesis Seal **MUST** 覆盖四条 Event、普通 Realm create 的全部 required founding writes 与 §6.2 的固定投影；**MUST NOT** 先 Seal create 再补任一 member join 与 Strand。这也是 `ak.strand.create` 必须免 basis 的原因：它被同一张 Seal 覆盖，无法引用那张尚不存在的 Seal。

controller/Agent 分支的第 3 条 Agent join **MUST** 显式携带 `agent_controller_binding`，其 controller AccountId 必须逐字等于 founder，generation ref 必须逐字等于第 2 条 controller join Event ID，且不得携 terminal ref。仅此完整原子 unit 的 admission 可使用同批前序 staged controller join；不得要求第 2 条预先独立 accepted，也不得在整批 accepted 前授予成员资格。receiver **MUST NOT** 推导、补写或替换缺失的 binding。普通 Agent join 仍引用已经 accepted 的 controller join。后续 controller rejoin 不得更新旧绑定或复活旧 Agent join。

### 6.2 固定 baseline 投影

本 profile **MUST NOT** 让 producer 选择"是否追加 policy Event"。`direct_conversation_genesis` contract **MUST** 从 create 与 round 机械投影下列 create-locked baseline：

- `join_rule=closed`，不可公开发现或枚举；
- `content_scheme=mls_exporter_aead_v1`；
- `content_encryption_floor=e2ee_required` 且 `metadata_encryption_floor=e2ee_required`；
- initial current `history_access=since_join`；exact-two active participants 是独立 membership/profile 约束。

同批 facet Event 重复或覆盖 create-locked encryption 值 **MUST** 拒绝。DC 的 `history_access` 由 create 条件写原子初始化并永久固定为 `since_join`；任何 update 或 `all_history_for_current_members` materialized state 都必须拒绝。

DC 不存在第二套 profile-fixed history sharing 对象。Exact-peer-only 来自 immutable exact-two participant binding 与 current
membership gate，不来自 key-source allowlist。DC 的 `history_access` 永久为 `since_join` 且不存在 update/widen 分支。Exporter DC 的历史 secret delivery 只按 receipt-bound direct Seal replay 得到的 winning transition、recipient current incarnation/join floor 与首次入队 T1 gate 执行；provisional epoch 是否可交付也由这些事实机械决定，
不得再引入 `pre_join_history` 或公开 provisional key-share 特例。

notary value 与 CBS profile **MUST** 从 trust domain 已 accepted 的 DM deployment policy 与 founder current service binding 确定性派生，caller **MUST NOT** 自选。单侧创建只保证不依赖 peer 设备与 peer Station；若所选普通 notary profile 本身需要其它不可达 signer，创建仍按普通 CBS 规则 pending。

## 7. 首次物化：bootstrap authority 与唯一 MLS group

### 7.1 三种离线必须分开

任何网络、KeyPackage 或 round 失败 **MUST NOT** 触发自动明文降级。

### 7.2 bootstrap participant authority

binding 尚不存在时普通 DM participant authority 未激活，因此 **MUST NOT** 以 founder、`created_by` 或技术 root owner 身份暗中放行 Message。本规范登记封闭 authority source `ak.authority.direct_conversation_bootstrap_participant.v1`，只含两个由 verifier 从 accepted facts 重算、producer 不可自选的互斥 phase：

1. `provisional_history_send`：founding unit 与唯一 scope-derived group Genesis Seal 已 accepted、对应 current authorization 与 endpoint gates 通过时，仅 founder 可管理自身 leaf、发送 provisional exporter Message、claim exact peer KeyPackage 并 author 同组 Add/Welcome；不得放行 policy、grant、第三 participant、其它 Strand 或普通 membership 写。
2. `exact_pair_founding_completion`：该同一 group 的 accepted winning state 已含 exact pair authorized leaves、joiner 已 durable 接受 Welcome、current gates 通过且 binding 尚无合法 endorsement 时，只允许提交 `ak.direct_conversation.bound` endorsement；不得创建第二组、重建 Genesis 或扩大成员。

每条 Event **MUST** 使用该 source 的 registered `authorization_ref`/proof context 并携 action-specific critical refs；owned Agent 分支仍叠加 controller delegation。wire 承载是 `authorization_ref` 的封闭常量
`direct_conversation_bootstrap_authority_ref`（值为 `ak.authority.direct_conversation_bootstrap_participant.v1`），
**MUST** 恰好配一条 critical `refs[role=direct_conversation_founding_unit]` 指向该 unit 的 accepted
`ak.realm.create`；binding 尚不存在，因此该阶段 **MUST NOT** 使用 `direct_conversation_binding` ref role 或
`ak.authority.direct_conversation_participant.v1`。phase 由 verifier 从 accepted facts 重算，producer 不得在 wire
上声明。首个合法 binding endorsement accepted 后两 phase **MUST** 永久退出，后续业务动作只走
`ak.authority.direct_conversation_participant.v1`。

该退出规则不把 §8.3 的等价背书变成冲突：针对已成立的同一 `binding_digest`，验证方仍 **MUST**
按原 founding completion 证据检查并接纳兼容 endorsement，包括并发提交的后到者与同 participant 的重复背书。
这只是既有 binding 的证明累积，不重新激活 bootstrap phase，也不赋予 Message、MLS 写或新 binding 的权限；
任一语义字段改变的 endorsement **MUST** 在 effect projection 前拒绝。背书继续携原 registered bootstrap
source 与 exact founding-unit ref，不得为重复背书发明新的 authority source 或兼容 wire 分支。

### 7.3 唯一 group 与 repair

DM Realm 与所有其它 MLS-backed effective scope 使用同一规则：
`mls_group_id = derive(canonical_effective_scope_key(scope))`，每个 scope 恰有一个 immutable group 与从零开始且永不重置的 epoch lineage。
首次 `ak.mls.genesis` 是 create-once；不存在第二个 group、候选 group、epoch reset 或额外 group selector。

Founding、peer Add 和以后 repair 都只通过该 group 的 ordinary winning Commit 推进。只要至少一个 current authorized live member
持有 private state，它可 author Remove/re-add Commit 和 Welcome；所有 reducer、CBS 与 security-frontier 规则与普通 MLS Commit 相同，
不得为 DC 新增 winner、barrier 或 quorum。Message 必须引用 event-time exact winning group state，后续 Commit 不追溯否定旧 Message。

若所有成员均丢失该 group 的 private state，则旧 encrypted DC scope 永久终结：不得用同一 derived group id 重放 Genesis、把 epoch
归零或激活第二组。同一 stable participant pair 与同一 trust domain 下也不得创建 successor DC Realm；resolver 保持 `suspended`，服务端只能返回已登记且可由当前状态证明的 `state_mismatch`，不得把设备私态丢失猜测成新的 wire 共识状态。只有实际不同的 stable participant pair 或不同 trust domain 才会按 §5.1 自然得到不同 `pair_key`
并进入新的普通建联流程；该新会话不是旧 lineage 的恢复，旧 Realm 的历史、backup、proof 与 epoch namespace 不与其合并。

### 7.4 exporter scheme 的既有代价

固定 `mls_exporter_aead_v1` 使 per-epoch `history_secret` 可保留、可重新封装，其 FS/PCS 按 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.10 退化为限定形态。该取舍 **MUST** 在 profile 中声明并对双方可查。需要更强前向保密的部署 **MUST** 另立 `mls_rfc9420` 变体 profile，并接受后加入设备无法读取历史。

## 8. Stable identity、repair 与 participant authority

### 8.1 稳定坐标

同 pair 只有一个 immutable Realm 与 main Strand。leave、block、tombstone、scope 撤回、Agent pause、erasure 或恢复 **MUST NOT** 创建 successor Realm、Strand 或 binding。

canonical DM Realm **MUST** 拒绝 `ak.realm.destroy` 与任何 `ak.realm.tombstone`（`direct_conversation_terminal_forbidden`）。`ak.realm.archive` 与 `ak.realm.freeze` 是普通可逆 facet：具备合法 authority 与 CAS basis 时可设置，且 **MUST** 保留普通 unarchive/unfreeze 路径；它们只令 resolver 附带 send blocker，**MUST NOT** 产生 successor 或新坐标。

若错误实现或对象冲突仍使 canonical Realm 进入 terminal 或不可判定状态，pair **MUST** 按 §5.7 `suspended` 并等待显式 recovery；本地 slot **MUST NOT** 回到可创建状态。自动重开会再次允许第二个 Realm，正好破坏 founder-only 唯一性。

### 8.2 rejoin 后的 MLS 收敛

标准 `ak.member.state{join}` / `ak.member.rejoin.own` 被 accepted 后本身就是 durable 收敛触发事实，不存在第二条 repair 消息、dispatch 或 relay。profile 只允许主体恢复既有 pair/Realm/main Strand 的二人 membership；human 只能 self-rejoin，owned Agent 仍使用 `actor_id=agent_id, executed_by=controller_account_id` 与 immutable controller authorization。它不得加入第三 participant，也不得取得 grant、policy、admin、Strand 或 binding 变更权。

只要至少一名 current authorized member 仍持有该唯一 group 的 private state，其普通同步器观察 accepted membership 变化后，按既有 KeyPackage claim 合同取得回归方 exact package，并在同一 group author 普通 Remove/Add Commit 与 Welcome。该流程完整复用普通 Commit winner、security frontier、claim consumption 与 Welcome admission；DC 不定义专用 carrier、operation、queue、feature、barrier、quorum 或幂等账本。

任一 directional Contact 已撤回时，membership Event 可以被保存，但 KeyPackage claim、MLS Add 与发送必须保持拒绝，resolver 返回 `suspended`。若没有成员保有 private state，则按 §7.3 终结旧 encrypted DC scope；同一 pair / trust domain 没有 successor Realm。

### 8.3 binding 与日常 authority

`ak.direct_conversation.bound` **MUST NOT** 承担阻止第二个 Realm 的职责——唯一性来自 §5.4 的 admission。它是 coordinates 与首次 exact-pair group state 的 participant 可见凭证，wire payload 绑定 `pair_key`、`unordered_participant_ids[2]`、`realm_id`、`main_strand_id`、`founding_unit_digest`、分支化 `authorization_basis` 与 `initial_exact_pair_group_state_ref`。`binding_digest` 是下述内容的 receiver-derived semantic digest，**不是 wire 字段**。

receiver 先必须验证 payload 的每个字段与 accepted founding unit、唯一 main Strand、canonical authorization basis 及该 pair 唯一 group 的 exact-pair winning state 一致，再构造以下唯一 closed object。`p0/p1` 是 wire `unordered_participant_ids` 中两个 exact `ActorId` 按 unsigned RFC 8785 JCS bytes 升序排列的结果；派生对象的字段名固定为 `participants_unordered`，不是 wire 别名。`e0/e1` 是 `authorization_basis.event_refs` 中两个 accepted Event ref 按 unsigned UTF-8 bytes 排序的结果。排序只用于此派生对象，**MUST NOT** 改写已签名 Event bytes。

```text
binding_object = {
  "pair_key": pair_key,
  "participants_unordered": [p0, p1],
  "realm_id": realm_id,
  "main_strand_id": main_strand_id,
  "founding_unit_digest": founding_unit_digest,
  "authorization_basis": {
    "kind": authorization_basis.kind,
    "event_refs": [e0, e1]
  },
  "initial_exact_pair_group_state_ref": initial_exact_pair_group_state_ref
}

binding_digest = H("ak.direct-conversation.binding-digest.v1", binding_object)
```

`H` 的精确定义见 §2：实际前像为 `UTF8("ak.direct-conversation.binding-digest.v1\n") || RFC8785_JCS(binding_object)`，结果为 `sha256:<lowercase-hex>`。`created_at`、Event envelope 的 author/proof 与 `binding_digest` 本身都不在 `binding_object` 中，因而不存在“先放入再排除”或自指前像。实现 **MUST** 执行 [`ak.vector.direct_conversation.binding_digest.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT，**MUST NOT** 使用无 domain 的 `SHA256(JCS(payload - created_at))`。

binding cell **MUST** 为 `or_set`，contract concurrency class 为 `merge_safe`。core OR-Set 元素身份仍是 [`../models/event-and-patch.md` §2.4.2](../models/event-and-patch.md) 定义的 Event dot，registry 仍精确投影 `tag={dot:true}, value=payload`；`(binding_digest, envelope.actor_id)` 是 Direct Conversation 领域视图的 **endorsement identity / 去重键**，不是 core OR-Set tag，也不是 wire 字段。同一 participant 对同一 digest 的多条 Event 在领域视图只计一个 endorsement；双方对相同 semantic payload 并发签名是两个兼容 add，**MUST NOT** 产生 `⊥`；不同 digest **MUST** 在 effect projection 前拒绝并触发 `suspended` 诊断。`found` 至少需要一份合法 endorsement；部署 **MAY** 登记要求双方 endorsement 的更高 profile，但 base **MUST NOT** 因两人同时 endorse 而失败。

**发送证据与展示引用（normative）。** `ak.direct_conversation.bound` 是 `sealed=true` 的 Control Move；
仅存入 ingress 或出现在查询投影中不等于可授权。普通 participant Message 的唯一 critical
`direct_conversation_binding` ref **MUST** 指向其 `seal_ref` 覆盖的一份合法 endorsement，且该 endorsement
的 semantic `binding_digest` **MUST** 等于当前无冲突 binding。服务端在列表中选择的代表 Event ref
不是额外的 authority head：**MUST NOT** 要求 Message 逐字引用该代表，也 **MUST NOT** 因后来出现另一份
等价 endorsement 而否定先前已覆盖的引用。上述覆盖与 authority 条件由服务器 admission 验证。
客户端信任自己的 Station，使用 resolver `found.coordinates.binding_event_ref`（found MUST 提供一份
合法已接受 endorsement 的完整 EventId）、current `group_state_ref` 和精确
`control_proposal_decisions` 的 sealed 结果取得 authoring 坐标；只核对本地操作的 actor、Realm、intent
与 basis 绑定，不下载或重放历史 Event/Seal 闭包。base 客户端 **MUST NOT** 等待所有可见 endorsement
被覆盖，或要求两方各一份确认。缺少当前供料时只等待相关 exact 服务端结果，不改变坐标、
不重建 group、不放松 current Contact、membership、endpoint 或 lifecycle gate。该规则不取代 §7.2
尚未建立 binding 时的 provisional founder Message authority。

binding **MUST NOT** 携带 `binding_state`、`supersedes_binding_ref`、永久 `mls_group_id` 或 consume receipt，也 **MUST NOT** 改变 membership、MLS、policy 或 Realm 坐标；若未来增加此类字段，**MUST** 拆为独立 `security_barrier` Move。

日常写 authority 唯一来自 `ak.authority.direct_conversation_participant.v1` 与 current accepted binding、exact-two membership、双方 current directional Contact heads、唯一 group 的 exact-pair winning state 及 action-specific lifecycle gate 的交集。技术 root、`created_by`、founder 身份、本地 slot 与普通 grant **MUST NOT** 替代该 evaluator。root mask 只允许 current materialization 的精确 founding/repair effects；`found` 后 **MUST NOT** 恢复 owner/admin authority。

## 9. Resolver、隐私与 SDK 边界

### 9.1 resolver 状态

`ak.self.direct_conversation.read.resolve.v1` 是唯一查询入口，其 outcome 为封闭判别联合：

| state | 条件 |
| --- | --- |
| `creation_required` | 无 accepted DM Realm，本方 `== founder`，且 current gate 允许创建；**MUST** 携带 §9.1.1 的 `next_founding_input` |
| `creation_blocked` | 无 accepted DM Realm 且本方 `== founder`，但 current Contact/account/Agent/profile/notary gate 确定性拒绝；**MUST NOT** author genesis Event 或派生 Realm token，也不得诱导重试 |
| `awaiting_founder` | 无 accepted DM Realm 且本方 `!= founder`；等待时长 **MUST NOT** 改变 create authority；即使 exact founder authority 永久不可恢复，v1 也不把权限转给 successor，不另造“永久丢失”wire state |
| `provisional` | 唯一 founding unit 已 accepted 但尚无合法 binding；只可执行 §7.2 的封闭 bootstrap 动作 |
| `found` | 至少一份合法 binding endorsement、唯一 group 的 exact-pair winning state 与普通 participant authority evaluator 均通过 |
| `suspended` | 已有 Realm 但 materialization/object conflict、terminal fault 或 membership/Contact/Agent/account/MLS/notary/lifecycle gate 阻止继续；blocker **MUST** 可机读 |
| `temporarily_unavailable` | 必需依赖不可验证，无法安全归类 |

求值优先级固定：依赖不足以验证 current round 或 founder 时 `temporarily_unavailable`；无 Realm 时区分 `creation_blocked | creation_required | awaiting_founder`；有 Realm 后 identity/materialization/terminal/notary 冲突优先 `suspended`；否则无 binding 为 `provisional`；最后才在 binding、unique group state 与 daily gates 齐备时 `found`。`retry_after` 只是调度提示，**MUST NOT** 产生 fallback authority。

resolver 对已存在的 unique group winning state **MUST** 返回完整 `group_state_ref`，不存在 winning state 时省略。该 ref 是 winning Genesis/Commit 的完整 Event ID，suite 与全部 Event digest bytes 均从 ref 无损恢复，MUST NOT 再返回 sibling `group_state_digest`。
`found` 必有该 ref；`provisional`/`suspended` 在 winning state 已存在时也不得隐藏。客户端不得从最大 epoch、局部 MLS snapshot 或坐标猜 Event ID。

existing 坐标 **MUST NOT** 因 offline、presence、session、KeyPackage 库存、grant/policy freshness 或 MLS reconcile 而被隐藏。

#### 9.1.1 `creation_required` 的 authoring material（normative）

`DirectConversationFoundingUnitSubmission` 的 closed shape **不携带** `founding_authority_evidence`：founder 与验证方是同一台 current Station，§5.5 的 self admission 在同一事务内以服务端自己 current 的 Contact round（或 Agent provision）证据校验四条 Event；caller 回传的副本既不进入 `founding_unit_digest` 等任何幂等身份，也不可能成为可信输入，因此不存在于 wire 上。Event origin authority 已由四条 Event 的完整 actual-author `ActorId` 及服务端追加的 admission proofs 表达。

但 founder 仍需要领料才能构造该 unit：§6.1 四条 Event 的 §5.4 critical ref、round / continuity 坐标与 §6.2 派生 baseline 都取决于 pair 当前的 Contact round（或 Agent provision）证据。若 resolver 只回一个无 material 的
`creation_required`，则 founder 在协议层无法确定这些输入——这正是
[`service-http-binding.md` §2.2.2](../sync/service-http-binding.md) 供给闭合律禁止的形态。
因此：

- `creation_required` **MUST** 携带 `next_founding_input {founding_authority_evidence}`。它是 founder 构造
  四条 Event 的领料容器，**不是** submission 的回声：caller 从中读取 round、continuity chain 与 binding 坐标去
  author 与签署 Event，**MUST NOT** 把该对象再放回 submission；submission 的 closed shape 对同名成员直接
  `schema_violation`，服务端 **MUST NOT** 以任何私有载体重新收取它。服务端 **MUST NOT** 在该容器里附带
  Event bytes、坐标、`idempotency_key` 或 receipt——四条 Event 仍由 founder 自签，服务端**永不**代签。
- 服务端 **MUST** 按本 pair 选择唯一分支：peer Contact founding 用 `human` 分支（含完整
  bundle 与 root continuity chain），own-Agent founding 用 `controller_agent` 分支；
  **MUST NOT** 同时返回两个分支，也 **MUST NOT** 返回与 §5.4 验证口径不同的另一份证据。
- **无料时不得返回本状态**：服务端组装不出或验证不了该 material 时 **MUST** 返回
  `temporarily_unavailable`，**MUST NOT** 返回不带容器的 `creation_required`，也 **MUST NOT**
  为此新增错误码或状态值——求值优先级表里 `temporarily_unavailable` 本就覆盖"依赖不可验证"。
- **新鲜度**：该 material 是响应时刻的快照，**不是** authority。caller **MUST NOT** 跨
  Contact 状态变化复用它；material 在提交时已陈旧的，submission 侧按 §5.4/§6 既有校验拒绝
  （round 不匹配、continuity 断链、binding 非 current），**MUST NOT** 因为 Event 是依据 resolver
  供料 author 的就放宽任何一条校验。submission 不携带 evidence，服务端 **MUST** 以自己 current 的那份
  证据校验 unit，**MUST NOT** 依赖任何 caller 侧的证据副本。
- **并发 founder 设备**：同一 founder 的多台设备 **MAY** 同时取得 `creation_required` 与
  相同 material；胜负仍只由 §5.5 的 `(founder_id, trust_domain_id, pair_key)` slot CAS 决定，
  失败方得到 `direct_conversation_slot_already_committed` 后 **MUST** 改走 resolver 取回既有
  坐标，**MUST NOT** 用自己那份 unit 重试。material 相同不构成"两份 unit 等价"。

联邦面与 self 面不同：`ak.peer.events.command.submit.v1` 的 `DirectConversationFoundingFederationSubmission`
**MUST** 显式携带 `founding_authority_evidence`——接收方是另一台 Station，读不到 source 的 Contact round / Agent
provision 状态，该成员是跨信任域的真实载荷，由 source 服务器在 server-to-server 一跳上投影供给并由接收
Station 独立验证；**MUST NOT** 要求 founder 客户端亲手跨服务器搬运这些证据，接收方也 **MUST NOT** 把搬运副本
当作 authority。

实现 **MUST** 执行 [`ak.vector.direct_conversation.founding_authoring_material.v1`](../../artifacts/registry/vector-registry.json)：
它断言容器存在性、单一分支、无 Event bytes / 坐标 / receipt、无料时降为
`temporarily_unavailable`、self submission 的 closed shape 拒绝同名回声成员，以及联邦面对 source 投影
evidence 的显式携带与接收 Station 的独立重新验证。

#### 9.1.2 Origin authority 供给（normative）

Direct Conversation founding 不建立独立 principal↔service binding object。resolver 只返回可验证的 `founding_authority_evidence`；caller author 的每条 Event 已签入完整 `ActorId`，接收服务按该 ActorId 路由完成本地 pair/device admission 后追加 proof。任何缺少该 pair、proof 不匹配或服务非 Event origin 的情况返回 `temporarily_unavailable` 或 fail closed，不得现场代 principal 签名。


**send blocker 的权威边界（normative）。** wire 上的封闭枚举 `direct_conversation_send_blocker`（[`direct-conversation-operations.schema.json`](../../artifacts/schemas/direct-conversation-operations.schema.json)）**MUST** 只承载 server-verifiable blocker：服务端 **MUST** 能从它有权读取的 accepted authoritative state 证明该值，**MUST NOT** 猜测、解密或把客户端自报当作 authority。因此 `personal_blocked` 与 `history_key_unavailable` **MUST NOT** 出现在该枚举中——`ak.account.blocklist` 是 holder-private account data，经不可信服务同步时只以对 holder 设备加密的形式存在；某条历史 MLS secret 是否已安装是端侧私有密钥状态。任何让服务端权威判定这两者的做法都要么拆掉那条加密不变量，要么把未认证声明当成事实。服务端返回这两个值 **MUST** 直接构成 `schema_violation`，客户端 **MUST** 拒绝，**MUST NOT** 以"容忍未知 blocker 字符串"的方式接受。

这两个值改由封闭的 **client-local blocker 集合** 承载，登记在 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `ak.profile.direct_conversation_realm.v1#client_local_send_blockers`，其值恰为：

```text
client_local_send_blocker = "personal_blocked" | "history_key_unavailable"
```

该集合 **MUST NOT** 出现在任何 wire 面：不进入 resolver outcome、任何 operation 的 request/response、任何 Event payload，也不进入 peer carrier 或联邦面。客户端在本地把它与 wire 返回的 `found.send_blockers[]` 合并，再决定是否放行发送。本规范只定义该封闭集合的语义与取值；类型实现属于共享 SDK 层，各客户端 **MUST NOT** 各自另立一套值。

client-local blocker **MUST NOT** 令 resolver 返回 `suspended`，也 **MUST NOT** 改变任何 wire 状态：它只影响客户端本地是否放行发送。否则服务端状态会被本地状态污染，同一 pair 在两台设备上会得到不同的 resolver 结论。

`presence_offline` 与 `keypackage_empty` 保留在 wire（服务端确有可证事实），但 **MUST** 只对该 pair 的 existing exact-pair participant 返回；其它任何调用方 **MUST** 得到与"该 pair 不存在"逐字相同的 opaque failure，**MUST NOT** 借这两个值做非参与者枚举或探测。反过来，真实 participant 的 existing 坐标 **MUST NOT** 因为对端离线或 KeyPackage 库存为空而被隐藏。

**连带后果（normative 提示）。** 因为拉黑是单方面本地过滤，"我拉黑了对方，所以发不出去"这件事**只有客户端自己知道**：服务端不知道，对端也不知道，而且本就不该知道——让任一方知道就等于把 holder-private blocklist 泄漏出去。这正是拉黑应有的语义，但习惯"发送前先问服务器要状态"的实现会在这里踩空：resolver 会返回 `found` 且 `send_blockers[]` 为空，发送仍 **MUST** 被客户端本地拦下。实现 **MUST NOT** 为了让服务端"看见"拉黑而新增任何上报、同步或探测通道。本条的规范执行向量是 `ak.vector.direct_conversation.send_blocker_authority.v1`。

### 9.2 隐私

DM Realm、其成员、Strand、MLS 状态、本地 slot、founder 身份、pending 状态，以及"该 pair 正在创建私聊"这一事实本身，**MUST** 只对两个 participant 及合法 owned-Agent controller 可见。其它任何主体 **MUST** 得到与不存在逐字相同的 opaque failure；不存在、不可见、policy deny、authorization deny 与 quarantined **MUST** 共用同一失败形态。DM Realm **MUST NOT** 出现在 directory、discovery、search、alias 解析或成员枚举中。

### 9.3 SDK 与 endpoint 边界

服务端 **MUST NOT** 注册全局 ActivationPlan、跨 endpoint next-action 或 workflow/conversation identity。每个 endpoint 只返回自己的 closed local outcome、blocker/reason、operation ref、exact-retry/conflict 与本 endpoint expiry。

SDK planner 只组合 canonical public facts（Event/Seal/binding/unique group state）、authenticated service durable facts（source acceptance receipt、delivery outbox 状态）、controller-private durable facts 与 local ephemeral 状态；每项携 source ref、frontier/epoch、freshness/expiry 与 privacy label。客户端 bytes 只负责 authoring 与 exact retry。unknown 或 stale 只阻断相关 action，**MUST NOT** 隐藏 existing DM 坐标。

SDK **MUST NOT** 实现事后从多个 binding 中选择 canonical 的逻辑，也 **MUST NOT** 实现任何 fallback、takeover 或 minimum-token selector。

## 10. 规范性回归边界

founding 相关的机读入口是 [`ak.vector.direct_conversation.founding_unit.v1`](../../artifacts/registry/vector-registry.json)
与 [`ak.vector.direct_conversation.founding_admission.v1`](../../artifacts/registry/vector-registry.json)，
机读 fixture 见 [`direct-conversation-fixture.json`](../../artifacts/fixtures/direct-conversation-fixture.json)。

Conformance **MUST** 覆盖：

- founder 派生：normal 取根轮次 responder、glare 取 §2 严格排序后 `requests[0].request_event_ref` 的 signed Event author `ActorId`，两侧独立计算一致；把 normal 分支误算为 requester、把 Station receipt issuer 当作 founder、乱序或重复 request refs（即使摘要不同）**MUST** 被两侧 admission 拒绝；反向 receipt 到达顺序、摘要排序与解码后 digest 排序不得改变 founder；
- 非 founder 提交 founding unit 在 self 与 peer 两条路径均拒绝；
- caller-authored 派生：`realm_id`、`main_strand_id` 与 `founding_unit_digest` 由两个独立实现从同一 unit bytes 重算得到逐字节相同结果；请求另行携带坐标、服务端预分配 ID、reserved/materializing draft 与 coordinator 选举形态 **MUST** 被拒绝；
- founder 多设备并发各自 author 出不同 unit 时，同一 Station 的唯一 slot **MUST** 只接受先到的合法 unit，后到者返回 `slot_already_committed` 且零写入，两台设备随后从 resolver 得到同一组坐标；
- founder 与 peer 位于同一 Station 与位于两台 Station 两种部署下，self 路径与 §5.6 peer 路径 **MUST** 得到相同 unit digest、相同 receipt 语义与相同 admission decision；
- 幂等与崩溃恢复：同 `idempotency_key` 同 unit 的 exact retry 返回 byte-identical receipt 且 `accepted_at` 不变，同 key 不同 unit 返回 `duplicate_conflict`；unit 提交、receipt 落库、outbox 入队与响应丢失各崩溃点重放同一 signed bytes 均恢复同一结果，且不产生第二组 Event；
- §5.6 branch 的 dependency 不足 **MUST** 是 top-level 409 `dependency_missing` 加零写入，**MUST NOT** 出现只接受一或两条 Event 的 partial；
- basis 形态：unit 内 `ak.member.state{join}` 与 `ak.strand.create` 的 no-basis shape 被接受；同一 no-basis `ak.strand.create` 出现在 founding unit 之外（普通 Realm、同 Realm 的后续 Strand 或单条提交）**MUST** 被 admission 拒绝，而 unit 内改携 `seal_ref`/`auth_context`/`seal_basis` 也 **MUST** 被拒绝；
- recontact continuity：多轮 tombstone/recontact 后仍重算出同一 root Contact round 与同一 founder；缺 `previous_terminal_contact_round_id`、成环、分叉或两 proof 导出不同根均拒绝；
- accepted-at 与 current gate 分离：source 在旧 current round 有效时 accepted 的 unit 延迟到撤回后才到 peer，peer 仍接受历史 identity 并按 current gate 投影 `suspended`；
- 对方设备离线时 MLS 建立与发送成功；对方服务器不可达时 founder 仍可建 Realm、建立唯一 group 并发出真密文；
- 同一 scope 的第二个 Genesis、第二 group 或 epoch reset 必须拒绝；
- 跳代、回退、未 active group 作 predecessor、第 17 个候选 group 的既定错误；
- 无 fallback：non-founder 无论等待多久、伪造标记、回填时间或携 negative query 结果，create 均拒绝；
- pair materialization conflict：模拟受信 service 对同 pair 签出两份不同 unit/receipt 时两 Realm 全部冻结，**MUST NOT** 按 Realm token 词法顺序或到达时间选 winner，也 **MUST NOT** 发 tombstone；
- 同对象 token 不同 Genesis 继续走 `object_identity_conflict`，**MUST NOT** 与 pair materialization conflict 合并为一个 selector；
- 终态：`destroy` 与任意 `tombstone` 拒绝；合法 archive/freeze 及其反向操作沿普通路径生效且坐标不变；违规 terminal 后 slot 保持关闭且 resolver `suspended`；
- binding：逐字节 KAT 覆盖固定 domain、closed `binding_object`、participants / authorization refs 换序归一、`created_at` 与 Event author/proof 排除，任一语义字段改变必须产生不同 digest；双方并发同 semantic endorsement 得到两个 core OR-Set dot 且不 `⊥`；同 actor 重复在领域视图只计一个；不同 semantic digest 在 effect projection 前拒绝；current Contact/service refresh 不改 binding digest；
- owned Agent：controller↔own-Agent 只携 `direct_conversation_agent_provision` 时命中 DM variant；改用 `purpose="agent_control"`（那是 PCR genesis 分支，见 [`./key-management.md` §3.6.3](./key-management.md)）、同时携两个 DM roles 或 DM/PCR variants 多命中均零写入拒绝；Agent↔第三方分别覆盖 founder=Agent 与 founder=other；
- 隐私：非 participant 对任意阶段的 pair 查询与不存在逐字相同。

synthetic glare accepted Event、跨双方 CAS、server next-action、successor Realm/Strand、timeout takeover、minimum-token 归一、server-allocated founding ID、reserved/materializing draft、min-service-DID coordinator 与 view-dependent effect digest **MUST** 由负例拒绝。
