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
→ holder-authorized signer 签 closed Event，并在必要时附外部 authority Control Proposal Ack
→ commit 在 holder PCR 本地原子 acceptance
→ source-signed acceptance receipt + durable receipted outbox
→ peer carrier 投递原始 signed fact 与对应 receipt
→ peer 保存 verified mirror、checkpoint/current lease 与 transport receipt
```

prepare **MUST** 保存 operation/idempotency/canonical request digest、预分配 Event ID、完整 peer XOR、方向化
full-set scope、expiry 与该分支已有的 basis/version/predecessor，并返回branch-typed
`{event_id,kind,unsigned_event_bytes,event_digest}` canonical draft；request/reject不得伪造未来basis字段。draft
不含holder proof，客户端只可追加该proof。commit移除proof后必须与reserved unsigned bytes、ID、kind与digest
逐字一致，任何其它变化返回conflict；不存在接受caller自造Event shape的分支。五类 Contact Event 均为
Control Move；commit body 可携带`control_proposal_ack`，其结构和验证规则与
`EventInitialSubmission.control_proposal_ack`完全相同。当接收 Principal Server 不能代表当前 authority set
产生完整 quorum 时，caller **MUST** 携带该字段；服务端能产生时该字段 **MAY** 省略。该证据只是
Event 外的 publication evidence，不进入 reserved Event bytes 或 Event digest。同一
operation/idempotency/phase + 相同完整bytes回放该phase首次outcome；prepare与commit必须使用同一
operation/idempotency，但两phase的canonical bytes与幂等记录彼此独立。响应丢失、重启或outbox redelivery
不得产生第二Event、第二receipt或第二lineage head。

对 human self-principal PCR，commit 的 exact Event 已由 current active accepted device 以 canonical
`{holder}#{device_id}` method 签名；该 device 同时是 current `single_did(holder)` authority，因此这是
authority-authored Move，不得再要求一份独立 Control Proposal Ack，也不得因 Principal Server 不持有
holder 私钥而返回 `quorum_unreachable`。commit 仍须把 Event 写入 pending Control index；只有后继
device-signed accepted Seal 覆盖该 digest 后 Contact effect 才 materialize。managed Agent delegation、
organization governance、ordinary Realm 与 recovery/re-anchor 不使用此例外。

request prepare 是 holder-local authoring：它 **MUST** 从 holder PCR 的 current actor frontier 与 accepted Seal
frontier 固定 `actor_seq`、`prev_refs` 与 `seal_basis`；任一 frontier 暂不可得时返回可重试的
`frontier_unavailable` 且零写入。target principal 的解析与投递属于 commit 后的 durable receipted outbox / peer
carrier；因此 target 当前离线或不可解析 **MUST NOT** 把本地 prepare 改写成 `not_found`，也不得伪造已投递状态。

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
`H("ak.contact.introduction-evidence.v1", exact_introduction_evidence)`。本文的 domain-separated digest 统一定义为：

```text
H(label, x) = "sha256:" + lowerhex(SHA256(UTF8(label + "\n") || RFC8785_JCS(x)))
```

若某字段定义显式指定 decoded ciphertext bytes，则改为 `SHA256(UTF8(label + "\n") || decoded_bytes)` 且不做 JCS。
receipt中的Event ref/digest、lineage中的
event ref与current proof head都必须与同一内层Event及分支逐字交叉匹配。carrier只承载
`ak.contact.*`，不得承载 `ak.direct_conversation.bound` 或 Realm Event；Direct Conversation binding 只能走
§5–§7 的 founding admission 与 bootstrap authority。carrier 必须使用 peer Message Signature，并逐字保留内层 bytes；relay
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

`ak.self.contact.read.list` 的 `contact_list_row` **MUST** 用封闭子对象 `next_prepare_input` 承载下一次写入的输入。其
`basis_id`、`version`、`predecessor_event_ref` 三个字段与 `ak.self.contact.command.scope_update` /
`ak.self.contact.command.tombstone` 的 prepare 分支逐字同名，客户端 **MUST** 原样抄入，**MUST NOT** 改名映射、重算或
另行推导。容器名承担时态消歧：其中的 `version` 是**下一条 Event 要携带的**版本号，即 current head version + 1，故最小值
为 2；`predecessor_event_ref` 是**当前 lineage head 的 Event ID**，即下一条 Event 的前驱，而不是当前 head 自己的前驱。
同一 row 的 `request_event_ref` / `response_event_ref` / `tombstone_event_ref` 只是投影摘要，**MUST NOT** 被当作权威
链头拼装 successor。

该子对象只在能 author 后继时出现，省略本身就是“现在不可 author”的表达，**MUST NOT** 为此另造 error code 或扩充
`contact_state`。按 `contact_state` 逐值判定：`accepted` **MUST** 携带；`pending_outgoing`、`pending_incoming`、
`rejected`、`expired`、`tombstoned` **MUST NOT** 携带——前两者尚未建立 basis 与 lineage，后三者是 terminal 且 basis 与
lineage 永不复活。glare 机械派生的 basis 直接投影为 accepted 时同样 **MUST** 携带，此时 `predecessor_event_ref` 是该
issuer 自己的 request head。scope 全集替换为空只把非 terminal basis 投影为 `suspended`，其 `contact_state` 仍是
`accepted`，因此仍 **MUST** 携带该子对象，否则后续显式 widen 无从 author。

游标可能陈旧。服务端 prepare 侧已有 `contact_lineage_conflict`（409）与 `contact_scope_stale`（409），持陈旧游标的
prepare 只会被拒且零写入；被拒后客户端 **MUST** 重读 `ak.self.contact.read.list` 并以新值重试，**MUST NOT** 猜测
lineage，也 **MUST NOT** 以同一组值重试。本条的规范执行向量是 `ak.vector.contact.next_prepare_input.v1`。

同一 row 还 **MUST** 用 `request_receipt` 承载**回应一条 incoming 提案**所需的 prepare 输入。它是完整签名的
`request_acceptance_receipt` 对象，**MUST NOT** 收窄为引用，也 **MUST NOT** 改变 respond / reject 的 prepare 契约；
字段名与 `ak.self.contact.command.respond` / `ak.self.contact.command.reject` 的 prepare 分支逐字同名，客户端
**MUST** 原样抄入，**MUST NOT** 改名、重建或从 `request_event_ref` 拼装。与 `next_prepare_input` 的关键差异在于**签发者**：
该 receipt 由**对端的** source service 签发，不是 holder 自己的服务器签的。正因如此，把对象本身交给 holder 客户端
具有真实的跨服务器验证价值——客户端 **MUST** 自行验证 issuer 签名、`accepted_at` 时点的 issuer service key，以及
receipt 对 exact request Event ref/digest 的绑定，而不是无条件相信自己服务器的转述。

按 `contact_state` 逐值判定：只有 `pending_incoming` **MUST** 携带；`pending_outgoing`、`accepted`、`rejected`、
`expired`、`tombstoned` **MUST NOT** 携带——`pending_outgoing` 是 holder 自己发起、尚未有结果的提案，没有待回应的
incoming request，其余四者的 admission slot 已被消费或 basis 已终态。glare 因此**结构上不会**出现携带 receipt 的 row：
holder 自己那条尚未被消费的 outgoing request 使该 row 在 glare 证据齐备前保持 `pending_outgoing`，证据齐备后机械派生的
basis 直接投影为 `accepted`，两段都不是 `pending_incoming`——这与 §2 “glare 禁止 respond/reject” 完全一致。实现
**MUST NOT** 因为收到对端并发 request 就把 `pending_outgoing` 改判为 `pending_incoming`，那会诱导客户端去 author 一条
必被拒的 respond。

省略本身就是“现在不可 author respond / reject”的表达，**MUST NOT** 为此另造 error code，也 **MUST NOT** 扩充
`contact_state`。slot 已被 normal、glare 或 reject 之一消费后，携旧 receipt 的 prepare **MUST** 零写入拒绝；客户端
**MUST** 重读 `ak.self.contact.read.list`，**MUST NOT** 缓存、猜测或重放已消费的 receipt。本条的规范执行向量是
`ak.vector.contact.pending_incoming_request_receipt.v1`。

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
| `ak.self.contact.read.list` | 从 verified basis与双方 directional current heads投影；accepted row 另携 §3 的 `next_prepare_input` 游标，`pending_incoming` row 另携 §3 的 `request_receipt` |
| `ak.peer.contacts.command.submit` | closed XOR peer carrier；原 bytes + exact receipt/current proof |
| `ak.self.direct_conversation.read.resolve` | §9.1 的唯一 DM 查询入口；closed outcome，不携 create phase 分支 |
| `ak.self.events.command.submit` | 其 `direct_conversation_founding` branch 是 §5.5 的唯一 DM founding 提交入口 |
| `ak.peer.events.command.submit` | 其 `direct_conversation_founding` branch 是 §5.6 的唯一 DM founding 联邦入口 |

`ak.self.direct_conversation.command.resolve` 的 untagged 多 phase create 入口 **MUST** 删除：创建由 §5 的
`ak.realm.create` founding admission 承担，查询由上表的 `query.resolve` 承担，二者 **MUST NOT** 合并为一个
带 `create=true` 的 operation。

所有 transport binding **MUST** 逐字段等值，不能自行增加 `accepted`、兼容 consent shape、unsigned service row
或第二轮 assignment。首次接触 message 属于未获同意文本，接受前必须 quarantine/stub，不得把 Contact request
变成正文投递通道。

## 5. Direct Conversation founder 派生与创建授权

### 5.1 pair identity

同 trust domain 下两个 stable subject DID 按 unsigned UTF-8 bytes 排序为 `[p0, p1]`。`pair_key` **MUST** 在任何 Realm 存在前即可计算，因此固定使用 SHA-256 与 RFC 8785 JCS，**MUST NOT** 读取任何 Realm 自报的 digest suite：

```text
pair_key = sha256(UTF8("ak.direct-conversation.pair-key.v1\n") ||
                  JCS({"trust_domain_id": <id>, "participants": [p0, p1]}))
```

handle、display name、设备 ID、Principal Server endpoint、Realm ID、Strand ID 与 Contact Event ID **MUST NOT** 进入前像。双方 **MUST** 从 Event 中的 exact participants 与 trust domain 重算 `pair_key`，**MUST NOT** 采信 caller 自报值。实现 **MUST** 执行 [`ak.vector.direct_conversation.pair_key.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT；无 domain separator 或把 `trust_domain_id` 改名为 `trust_domain` 的旧前像均不是 v1 `pair_key`。

### 5.2 founder 派生（normative）

同一 pair 的 Direct Conversation Realm **MUST** 由且仅由从该 pair 的 **founder basis** 确定性派生出的 `founder` 创建。派生只读 §2 已定义的 basis core，不引入新字段：

```text
founder(basis) =
    normal 分支 -> sorted_pair_members 中不等于 request_event_ref 之 issuer 的那一方（即 responder）
    glare  分支 -> requests[0].request_event_ref 之 issuer
```

**normal 分支取 responder 而非 requester 是 normative 选择**：basis 由 responder 的 `normal_response_acceptance_receipt` 点亮，该 receipt 证明 responder 在 basis 成立时在线且刚完成签名；requester 可能在数日前发出请求后即长期离线。base v1 不定义 fallback（§5.7），因此把 founder 定为可能不在场的一方会使该 pair 永久无法创建。

glare 分支不存在 responder，`requests[0]` 依 §2 已登记的 canonical ordering 取得，**MUST NOT** 另立排序规则。

`sorted_pair_members` 不恰为二、request issuer 不属于该 pair、glare requests 未按登记顺序或两个 issuer 不构成该 pair 时，founder 派生 **MUST** 失败并整组拒绝，**MUST NOT** 以补集或本地偏好猜测。

### 5.3 founder basis 与 recontact continuity

founder **MUST** 从该 pair 的**根 founder basis** 派生，而非从 current basis。tombstone 后 recontact 产生的新 basis **MUST** 在其 request/receipt 中承诺 `previous_terminal_basis_id`；receiver **MUST** 沿该链求出唯一根 basis，并从根 basis 派生 founder。

该指针的 wire 规则是封闭的：根 request Event 与根 acceptance receipt 都 **MUST** 省略 `previous_terminal_basis_id`；recontact 的 request Event、source request acceptance receipt、以及 normal response acceptance receipt **MUST** 都携带同一个“紧邻上一轮 terminal basis”的 `basis_id`。glare 分支的两个 request Event 与两张 source acceptance receipt 也 **MUST** 携带相同指针。`slot_predecessor` 只表示签发服务内部 request-slot 的 CAS 前驱，**不是**跨轮 continuity 指针，二者不得互相替代。

`basis_continuity_chain` 按 current → immediate predecessor → root 排列，最多 64 段，不得重复或成环。每一段 predecessor bundle 的两张 `contact_current_proof` 都 **MUST** 令 `terminal=true`，共同证明该 basis 已 tombstone；当前 active basis 的 proof 则 **MUST** 为 `terminal=false`。每条边必须逐字节满足“后继 core/receipt 的 `previous_terminal_basis_id` 等于下一段 bundle 的 `basis_id`”；最后一段必须且只能是省略该指针的 root。proof 对完整 closed object 签名，因此 `terminal` 也在签名 transcript 内。断链、多根、跳段、非 terminal predecessor、两个方向 proof 不一致或超过上限均整体拒绝。

断链、多根、成环、跳过非 terminal basis、或两个 directional proof 导出不同根，**MUST** 拒绝创建与回放。current recontact 的 responder 即使与根 basis 的 responder 不同，也 **MUST NOT** 取得创建权。Realm 一经 accepted，founder 身份只保留为 founding 审计与 §7.2 bootstrap authority 的 actor 约束；日常 authority、repair 与 recontact **MUST NOT** 再读取它。

### 5.4 create 判别与授权

`ak.realm.create` 的 conditional admission **MUST** 登记两个结构互斥的 Direct Conversation variant，判别器为 critical ref role：

| ref role | admission variant | 适用分支 |
| --- | --- | --- |
| `direct_conversation_basis` | `direct_conversation_genesis` | human↔human、Agent↔第三方 |
| `direct_conversation_agent_provision` | `direct_conversation_agent_genesis` | controller↔自己的 owned Agent |

两个 role **MUST** exact XOR。managed-Agent PCR genesis 不再使用任何 ref role 判别：它按 `payload.object.purpose="managed_agent_control"` 选择 `delegated_pcr_genesis`，并以准入反查 accepted `ak.agent.provision` 的前向声明取代旧 ref（见 [`./key-management.md` §3.6.3](./key-management.md)），因此这里的两个 DM role **MUST NOT** 与之混用。DM variants、PCR variants 与 ordinary Realm 的 `when` 条件 **MUST** 结构互斥；零命中或多命中 **MUST** `schema_violation`，**MUST NOT** 按 registry 顺序取第一条。

`direct_conversation_genesis` **MUST** 逐项验证，任一不符整组零写入：

1. 该 ref 指向完整 portable Contact basis evidence bundle 及至根 founder basis 的 continuity chain，`basis_id`、normal/glare core、request/response receipts 或 glare attestations、terminal links 与双方 proofs 均可验证；
2. 按 §5.2/§5.3 求出 `founder`；
3. `created_by == actor_id == founder`（追加约束，**不**放松既有 `created_by == actor_id`）；
4. payload 的 `pair_key` 等于从 basis 的 `sorted_pair_members` 与 trust domain 重算之值；
5. Realm profile 为 `ak.profile.direct_conversation_realm.v1`，`collaboration_role="direct_conversation"`，effective participants 恰为该 pair；
6. §6.2 的固定 baseline 投影全部命中；
7. 该 `realm_id` 无对象身份冲突。

**accepted-at 与 current gate MUST 分开求值**：source self admission 在 slot commit 线性化点要求两条 directional current heads 共同引用该 current basis、授予 `direct_message` 且 fresh；peer replay 只验证这些 proof 在 source receipt 的 `accepted_at` 时有效并被 receipt digest 绑定。因此即使 Event 到达时 Contact 已撤回，peer 仍 **MUST** 接受该历史 Realm identity，并以 current gate 投影 `suspended`；否则 Event 有效性会依赖投递顺序。

`direct_conversation_agent_genesis` 改验 participants 恰为该 controller/Agent、profile 为 DM 而非 PCR、`ak.agent.provision` 已 accepted 且 controller binding current，并令 `founder = controller`。Agent 与第三方之间的 DM 仍 **MUST** 使用该 pair 的 current Contact basis，**MUST NOT** 以 provision 绕过第三方 consent。

### 5.5 caller-authored founding unit、source 唯一 slot 与 acceptance receipt

三条 Event 的 ID 都是各自 canonical Event preimage 的完整 digest（[`../conformance/encoding.md` §4.0](../conformance/encoding.md)），`realm_id` 与 `main_strand_id` 又分别是第一条与第三条 Event ID 的重类型（[`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)、[`../models/common-fields.md` §6.0](../models/common-fields.md)）。因此在 canonical preimage 完成之前**没有任何主体能"分配"这两个 ID**：服务端预分配、reserved/materializing draft、coordinator 选举与 caller 自选 ID 全部 **MUST NOT** 出现在本流程。founding **MUST** 采用 caller-authored first-valid unit：

1. founder caller author `ak.realm.create`（envelope 省略 `realm_id`、`scope_ref` 为 `{"kind":"realm_genesis"}`，payload 省略 object id），完成 canonical preimage 后派生其 Event ID，并重类型得到 `realm_id`；
2. 以该 `realm_id` author 另一 participant 的 `ak.member.state{join}`；
3. author `ak.strand.create`（payload 不携 `strand_id`），由其 Event ID 重类型得到 `main_strand_id`；
4. 三条全部由 founder 签名，按该 wire 顺序构成 exact ordered unit 一次提交；不存在 server-created draft、reserved Event ID 或第二次 authoring 机会；
5. 网络结果不明时 caller **MUST** 重放逐字节相同的 signed bytes，**MUST NOT** 重新 author 另一组 Event。

`founding_unit_digest` 是该 unit 的唯一稳定标识，按 §2 的 `H` 定义为：

```text
founding_unit_digest = H("ak.direct-conversation.founding-unit.v1",
                         {"event_ids": [realm_create_event_id,
                                        peer_member_join_event_id,
                                        strand_create_event_id]})
```

三个 Event ID **MUST** 按 §6.1 的 wire 顺序列出，**MUST NOT** 排序、去重或替换为 digest。该值不进入任一 unit Event 的 preimage，因此不存在自指；receipt 与 `ak.direct_conversation.bound` 只引用它。实现 **MUST** 执行 [`ak.vector.direct_conversation.founding_unit.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT。

founder 的 current Principal Server **MUST** 以本地唯一约束保证同一 `(founder_id, trust_domain_id, pair_key)` 至多一组 founding unit 被 accepted。self admission **MUST** 在同一事务内完成：确认该 pair 尚无 accepted DM Realm、CAS 占用 slot、按 §5.4 与 §6 完整验证三条 Event、basis 与派生坐标、零项或三项原子接受、签发 `DirectConversationFoundingAcceptanceReceipt`、写入 peer-delivery outbox。acceptance **只固定 caller 已派生的坐标**，**MUST NOT** 分配、替换或重新协商任一 ID；receipt 是该事务的输出，**MUST NOT** 循环要求 caller 预先携带。

receipt **MUST** 绑定 `pair_key`、`founder_id`、`realm_id`、`main_strand_id`、`founding_unit_digest`、分支化 authorization core（human 为 current/根 basis 与 evidence digest；controller↔Agent 为 provision ref/digest 与 controller binding digest）、`slot_committed`、issuer service ID 与其 accepted-at service binding digest、`accepted_at` 与 proof。它 **MUST NOT** 创建 Realm、授权 Message 或充当全局 slot；它只让 peer verifier 确认 founder 当时的 current service 已原子接受该 unit 并关闭本地唯一 slot。

`issuer_service_binding_digest` 的唯一输入是 [`principal-service-binding.schema.json`](../../artifacts/schemas/principal-service-binding.schema.json) 中 `accepted_at_service_binding` 去掉 `binding_digest`、`service_acceptance_proof` 与 `principal_authorization_proof` 后的完整 closed object，按 `H("ak.principal-service-binding.v1", object)` 计算。该 snapshot 必须把 `principal_id=founder_id`、`service_id=issuer_service_id`、`accepted_at` 不晚于且在 `receipt.accepted_at` 仍有效、service DID verification method、endpoint origins、DID document digest 与 current authority evidence固定；两张 proof 分别证明 service 接受承载关系和 principal 授权该 service，任何只查询“现在是谁的服务器”的结果都不能替代 accepted-at snapshot。

`proof` 的签名 transcript 是唯一封闭前像，按 §2 的 `H` 固定为：

```text
founding_receipt_transcript = H("ak.direct-conversation.founding-receipt.v1",
                                receipt 去掉 proof 后的完整 closed object)
```

`proof.verification_method` **MUST** 解析为 `issuer_service_id` 在 `accepted_at` 时的 current service key，
`proof.created_at` **MUST** 等于 `accepted_at`。receiver **MUST** 从 receipt 自身字段重算该 transcript 再验签，
**MUST NOT** 采信任何随 receipt 传来的预算 digest；这使 byte-identical retry 与两个独立实现必然得到同一
transcript 与同一签名输入。

carrier 是 `ak.self.events.command.submit` request union 中显式登记的 discriminated branch
`DirectConversationFoundingUnitSubmission`（discriminator `unit_kind="direct_conversation_founding"`）：它精确要求恰好三条按 §6.1 顺序排列的 `EventInitialSubmission`、分支化 founder basis evidence、founder 已签名的 `source_service_binding` 与 `idempotency_key`，并在 response union `EventsSubmitResponseBody` 中返回 `DirectConversationFoundingAcceptanceOutcome`。binding 的 `principal_id` 必须等于 founder、`service_id` 必须等于接收服务，服务端在 slot transaction 固定并验证 `accepted_at` 后只把其已验证 `binding_digest` 写入 receipt，**MUST NOT** 代替 founder 产生 `principal_authorization_proof`。实现 **MUST NOT** 新增私有 endpoint、复用普通 batch 分支，也 **MUST NOT** 用本地 DTO 猜测该合同；`ak.self.direct_conversation.read.resolve` 继续 query-only，**MUST NOT** 承载 create。

幂等与 crash/restart 语义 **MUST** 如下封闭：

- 同 `idempotency_key` 且同 `founding_unit_digest` 的 exact retry 返回 byte-identical receipt 与相同 `event_ids`，且 **MUST NOT** 推进 `accepted_at`；
- 同 `idempotency_key` 但不同 `founding_unit_digest` 返回 `duplicate_conflict` 且零写入；
- 本地 slot 已被同 pair 的另一组 unit 关闭时返回 `conflict` 与 `direct_conversation_slot_already_committed` 且零写入，caller **MUST** 改用 §9.1 resolver 取回既有坐标；服务 **MUST NOT** 接受第二组 unit，也 **MUST NOT** 把它降级为 partial 或 quarantine；
- 客户端已派生 ID、unit 已提交、三 Event 已落库、receipt 已签发、outbox 已入队与响应丢失这些崩溃点，重放同一 signed bytes **MUST** 收敛到同一 receipt、同一坐标与同一 outbox 条目，**MUST NOT** 产生第二组 Event、第二张 receipt 或第二个 slot。

相同 pair/founder 但不同 unit 的第二张 receipt 是 §5.7 冲突证据。

### 5.6 联邦例外

Realm 尚不存在时无法取得普通 `federation_peer` authority，因此 [`../sync/federation.md`](../sync/federation.md) **MUST** 登记一条封闭的 DM founding exception：允许 founder 的 current Principal Server 向另一 participant 的 current Principal Server 投递该 pair 的 founding atomic unit、source acceptance receipt 与验证所需的 bounded dependencies。

接收方每次 **MUST** fresh 验证：transport source 当前确实承载 founder（receipt 由迁移前旧 service 签发时还须携完整 accepted-at binding 与 cutover/fence 连续性证明）、destination 承载本地 participant、body 只含该 unit/receipt/dependencies、且 create 通过 §5.4 全部校验。Contact basis 镜像尚未到达时 **MUST** 返回 `dependency_missing` 并重试，**MUST NOT** 放行，也 **MUST NOT** 永久拒绝。

该连续性证明使用 `principal_service_binding_continuity`：先验证 accepted-at snapshot digest 等于 receipt，再按 `sequence` 从 1 严格递增验证至多 16 个 `principal_service_cutover`。每次 cutover 都必须把上一服务、下一服务、上一 binding digest、新 binding、effective time 与 fence digest 一并签入 `ak.principal-service-cutover.v1` transcript，并同时具有 principal、旧服务、新服务三方 proof；下一段的 previous digest/服务必须等于上一段输出，最后 service 必须逐字节等于认证的 `Source-Service-ID`。缺段、分叉、倒序、重复、无旧服务 fence 或超过上限均 fail closed；若 transport source 仍等于 receipt issuer，则 `cutovers` 必须为空。

该例外的 carrier **MUST** 是 `ak.peer.events.command.submit` request union 中显式登记的 discriminated
branch `DirectConversationFoundingFederationSubmission`（discriminator
`unit_kind="direct_conversation_founding"`），承载恰好三条按 §6.1 顺序排列的 `EventFederationSubmission`、
source `DirectConversationFoundingAcceptanceReceipt`、`source_service_continuity` 与 bounded dependencies；实现 **MUST NOT** 新增私有 peer
endpoint，也 **MUST NOT** 用普通 Realm batch 分支夹带该 unit。该 branch 是 registered atomic unit：dependency
不足时 **MUST** 用 top-level HTTP 409 `dependency_missing` 与 `EventsDependencyMissingProblem` 并零写入，
**MUST NOT** 退化为 per-item partial，也 **MUST NOT** 只接受其中一或两条。

Realm 在对端 accepted 后立即回落普通 federation 规则。因 §5.4 第 3 条已钉死作者，该例外不需要方向性约束。

### 5.7 无 fallback 与 pair materialization conflict

base v1 **MUST NOT** 定义 timeout fallback、takeover lease 或 `founder_fallback_window`。仅凭"本地与对端当前都没看到 Realm"不能证明 founder 没有 accepted 但尚未送达的 Realm；旧 founder 创建权未被全局可验证且不可逆的 fence 关闭前，non-founder 创建可能与迟到的 founder 创建同时合法。因此 timeout、HLC、到达顺序、Realm token 的词法大小与一次 negative query **MUST NOT** 改变 founder authority。

若仍观察到同 pair 第二个 **accepted** Realm：

1. 先判定是否只是非 founder、旧 basis 或旧 service 产生的无效 bytes；无效对象 **MUST NOT** 进入 discovery、binding 或 Message authority，也 **MUST NOT** 被称为 candidate；
2. 若两条都携看似合法的 founder admission 与 source receipt，则受信 service 的 slot、cutover fence 或签名发生 equivocation。pair **MUST** 进入 `direct_conversation_pair_materialization_conflict`，冻结两边新的 Message/membership/policy/MLS/binding；
3. **MUST** 保留两组 founding unit、receipts、service-binding/cutover proofs 与本地 slot 证据；**MUST NOT** 自动取 min、tombstone 任一 Realm、搬移历史或让 UI 选择一边继续；
4. 只有另行登记、能证明唯一 canonical founding unit 且不复活已终结历史的 recovery 协议可以解除。本规范不提供该协议。

## 6. Founding unit 与固定 baseline

### 6.1 三 Event atomic unit

founder **MUST** 一次提交恰好三条 Event：

```text
1. ak.realm.create        携 §5.4 的 critical ref；creator membership 由既有 reducer 派生
2. ak.member.state{join}  subject 为另一 participant 的显式 canonical membership
3. ak.strand.create       main Strand，scope_circle_id=null，primary discussion track
```

三条注册为 `ak.profile.direct_conversation_realm.v1` 的 closed atomic founding unit：按 wire 顺序验证，同一事务零项或三项接受。create-alone、缺 peer join、缺 Strand、乱序、不同 actor/pair/profile/Realm 或出现第四条 Event **MUST** 拒绝整组。三条 **MUST** 由 founder author，并使用同一分支 context（`direct_conversation_basis` 或 `direct_conversation_agent_provision`，exact XOR），叠加同批 staged authority-root proof。

该顺序同时是 §5.5 的派生顺序，不是可选排版：第 2、3 条的 `envelope.realm_id` **MUST** 逐字等于
`retype(第 1 条 event_id, "realm")`，`main_strand_id` **MUST** 逐字等于 `retype(第 3 条 event_id, "strand")`，
第 2 条的 `prev_refs` **MUST** 引用第 1 条、第 3 条 **MUST** 引用第 2 条。验证方 **MUST** 从 unit 自身 bytes
重算这两个坐标，**MUST NOT** 采信请求中另行携带的坐标字段，也 **MUST NOT** 接受任何声称先分配后签名的
提交形态。本段任一条件不成立 **MUST** 以 `direct_conversation_founding_unit_invalid` 整组零写入拒绝。

三条的 CBA basis 形态是封闭的：`ak.realm.create` 用 genesis bootstrap shape；`ak.member.state{join}` 与
`ak.strand.create` 在**且仅在**该 exact unit 内使用 bootstrap no-basis shape（既不携 `seal_basis`，也不携
`seal_ref`/`auth_context`），并叠加同批 staged authority-root proof。两者的免 basis 落点分别登记在
[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md) 与
[`../authz/event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md) 的封闭列表。
`ak.strand.create` 平时是携 `seal_ref + auth_context` 的 DataEvent，batch admission **MUST** 在本 unit 之外
拒绝它的 no-basis 形态。

Genesis Seal **MUST** 覆盖三条 Event、普通 Realm create 的全部 required founding writes 与 §6.2 的固定投影；**MUST NOT** 先 Seal create 再补 peer join 与 Strand。这也是 `ak.strand.create` 必须免 basis 的原因：它被同一张 Seal 覆盖，无法引用那张尚不存在的 Seal。

### 6.2 固定 baseline 投影

本 profile **MUST NOT** 让 producer 选择"是否追加 policy Event"。`direct_conversation_genesis` contract **MUST** 从 create 与 basis 机械投影下列 create-locked baseline：

- `join_rule=closed`，不可公开发现或枚举；
- `content_scheme=mls_exporter_aead_v1`；
- `content_encryption_floor=e2ee_required` 且 `metadata_encryption_floor=e2ee_required`；
- `history_visibility=joined` 与 exact-peer-only history sharing。

同批 facet Event 重复或覆盖这些值 **MUST** 拒绝；后续普通 policy Move 试图改变固定 baseline 亦 **MUST** 拒绝。

上列最后一项的 "exact-peer-only history sharing" 不是散文修饰，它的唯一字面值是 `ak.profile.direct_conversation_realm.v1` 的 `history_sharing_policy_fixed_baseline.value`：DC 与 PCR 是 v1 仅有的两个 profile-fixed baseline 例外（见 [`../governance/history-visibility.md` §3](../governance/history-visibility.md)）。DC 结构上永远发不出 `ak.realm.history_sharing_policy`——§6.1 的 founding unit 恰三条、第四条 **MUST** 以 `direct_conversation_founding_unit_invalid` 整组拒绝，`ak.authority.direct_conversation_bootstrap_participant.v1` 与 `ak.authority.direct_conversation_participant.v1` 的 `action_allowlist` 都没有能 author policy Event 的 action，§8.3 又禁止 `found` 后恢复 owner / admin authority——因此该字面值**就是**该 Realm 的 effective `ak.realm.history_sharing_policy`。key source 与 reducer **MUST** 按它执行 history-visibility §6 的 key-share 判定，**MUST NOT** 因"没有 accepted policy Event"报 `history_sharing_policy_missing`。其中 `allowed_receiver_states=["active_member"]` 承载 exact-peer-only 语义（profile 锁死 exact-two participants），`allowed_key_sources` 排除 `archive_node` / `recovery_service` 以维持两人独占，`post_removal_recovery="deny"` 对齐 §8.2。

**两个 "pre-join" 指不同的东西，实现 MUST NOT 混淆**：baseline 里 `pre_join_history` 的 pre-join 指**成为 Realm 成员之前**；DC 中 peer 的 `join_frontier` 就是 Realm Genesis，Realm 内不存在 `T0` 更早的 Event，故该字段结构性不会被触发，取 `deny` 只是如实陈述本 profile 从不释放加入前历史。而本节此处的 pre-join 只表示 peer 尚未成为 MLS leaf——§6.1 已使其自 Realm Genesis 起 joined——那段 generation-0 历史 **MUST** 共享，实现 **MUST NOT** 因 `pre_join_history="deny"` 拒发 §7.2 的 generation-0 provisional history key share。本条的规范执行向量是 `ak.vector.history_sharing.direct_conversation_profile_baseline.v1`。

notary value 与 CBA profile **MUST** 从 trust domain 已 accepted 的 DM deployment policy 与 founder current service binding 确定性派生，caller **MUST NOT** 自选。单侧创建只保证不依赖 peer 设备与 peer Principal Server；若所选普通 notary profile 本身需要其它不可达 signer，创建仍按普通 CBA 规则 pending。

## 7. 首次物化：bootstrap authority 与 active MLS generation

### 7.1 三种离线必须分开

1. **对方已在 current group、仅设备离线**：MLS 原生异步，用 current epoch 加密提交，对方上线后追 epoch 解密。**MUST NOT** 因对方设备离线而拒绝发送。
2. **对方尚未入组**：founder **MAY** 建立只含自身 leaf 的 provisional exporter epoch 并产生密文 Message；对方入组后经 `ak.realm_key.share` 取得旧 epoch `history_secret` 解开 `decryption_pending` 历史。
3. **连 exporter epoch 也无法建立**（Realm 尚不存在）：内容 **MUST** 只进入本地 pending tier，**MUST NOT** 成为任何 Realm 的 shared accepted Message，且 **MUST NOT** 以明文上传、日志或备份形式离开设备保护边界。

任何网络、KeyPackage 或 basis 失败 **MUST NOT** 触发自动明文降级。

### 7.2 bootstrap participant authority

binding 尚不存在时普通 DM participant authority 未激活，因此 **MUST NOT** 以 founder、`created_by` 或技术 root owner 身份暗中放行 Message。本规范登记封闭 authority source `ak.authority.direct_conversation_bootstrap_participant.v1`，只含两个由 verifier 从 accepted facts 重算、producer 不可自选的互斥 phase：

1. `provisional_history_send`：三 Event unit 与 Genesis Seal 已 accepted、active-generation cell 尚未越过 generation 0、对应分支的 current authorization 与 device/account/Agent gates 通过时，**仅对 founder 生效**。允许 sender-only `ak.mls.genesis`、generation-0 activation、founder 自身 leaf 管理、引用 active generation 0 的 exporter Message、exact peer KeyPackage claim/Add/Welcome 准备及必要 history share；**MUST NOT** 放行 policy、grant、第三 participant、其它 Strand 或普通 membership 写。
2. `exact_pair_founding_completion`：accepted selected group state 已含 exact pair authorized leaves、peer current service 已 durable 接受 Welcome、current authorization 与 device gates 通过、且 binding 尚无合法 endorsement 时生效。只允许从 generation 0 激活 generation 1、提交 `ak.direct_conversation.bound` endorsement 及完成对应 history share；**MUST NOT** 继续创建 sender-only group 或扩大成员。

   该 phase 内两类动作的 author 约束不同：generation-1 activation **MUST** 由 joiner author（§7.3）；binding endorsement 对任一 exact participant 开放（§8.3）。实现 **MUST NOT** 把两者合并为同一条"任一 participant"授权。

每条 Event **MUST** 使用该 source 的 registered `authorization_ref`/proof context 并携 action-specific critical refs；owned Agent 分支仍叠加 controller delegation。wire 承载是 `authorization_ref` 的封闭常量
`direct_conversation_bootstrap_authority_ref`（值为 `ak.authority.direct_conversation_bootstrap_participant.v1`），
**MUST** 恰好配一条 critical `refs[role=direct_conversation_founding_unit]` 指向该 unit 的 accepted
`ak.realm.create`；binding 尚不存在，因此该阶段 **MUST NOT** 使用 `direct_conversation_binding` ref role 或
`ak.authority.direct_conversation_participant.v1`。phase 由 verifier 从 accepted facts 重算，producer 不得在 wire
上声明。首个合法 binding endorsement accepted 后两 phase **MUST** 永久退出，后续动作只走
`ak.authority.direct_conversation_participant.v1`。

### 7.3 active MLS generation

DM Realm **MUST** 登记 singleton control cell `ak.component.direct_conversation.active_mls_generation.v1`（`cas_register`，`bottom=reject`，registry 声明 `initial_value=__unset__`），写入 kind 为 `ak.direct_conversation.mls_generation.activate`，contract concurrency class 为 `security_barrier`。activation **MUST NOT** 创建 group：producer 先用普通 `ak.mls.genesis`/Commit 建立候选 state 并原子保存本端私态，activation 再引用 accepted public state 与 durable facts。未被 cell 选中的 group **MUST NOT** 取得 Message send authority。

- **generation 0**：cell 仍 `__unset__`、predecessor 缺省、`phase=provisional_history_send`，group 恰含 founder 的 authorized current leaves 且不含 peer 或第三方；只有 §7.2 phase 1 可 author。
- **generation 1**：current 恰为 generation 0，`phase=exact_pair`，selected state 含双方 authorized current leaves 且无第三 participant，`predecessor_active_value_digest` 与 `head_eq` 逐字命中 generation-0 whole value。

  **generation-1 activation MUST 由 joiner（非 founder 的那个 participant）author。** 本规范不定义可移植的"对端已 durable 接受 Welcome"证物——[`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) 的 `peer_claim_receipt` 证明 claim 合法而非 Welcome 已 durable——因此只有 joiner 能真实断言"我的 current service 已 durable 收下该 Welcome 且我已持有 private state"。这与 `consume` 只能由 Welcome 接收方调用、peer surface 不提供代理是同一条原则。joiner 侧 self admission 从本地记录验证该前提；founder 侧只验证 `author == joiner` 这一结构约束。founder author 的 generation-1 activation **MUST** 以 `direct_conversation_activation_author_invalid` 拒绝，即使其它字段全部正确。该约束不引入新等待：generation 1 本就要求 joiner 处理完 Welcome 并持有私态。
- **generation ≥ 2**：binding 后的 repair，要求 `phase=exact_pair`、`generation = current + 1`、predecessor 逐字命中 current whole value，并走 ordinary participant authority；**MUST NOT** 重新进入 provisional phase。

跳代、回退、把未 active group 当 predecessor、`u64::MAX` 或省略 causal basis **MUST** 拒绝。同一 predecessor 下未 active 的候选 group 硬上限为 16，第 17 个以 `mls_generation_proposal_fanout_exceeded` 拒绝，**MUST NOT** quarantine 整个 pair。

该 code 登记在 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)，`http_status=409`、`scope=both`，self 与 peer 两条 Event 提交入口都 **MUST** 使用它。这是硬结构上限而非限速：实现 **MUST NOT** 改用 `rate_limited`（429），**MUST NOT** 通过 `retry_after_ms` 承诺重试窗口；只有既有候选之一被 cell 选中激活或过期，第 17 个才可能被接受。拒绝 **MUST** 零写入且只针对该候选：pair 的坐标、binding、成员集与 current active generation **MUST** 保持不变，resolver **MUST NOT** 因此转为 `suspended`。本条的规范执行向量是 `ak.vector.direct_conversation.mls_generation_candidate_fanout.v1`。

并发 activation **MUST** 逐字复用所选普通 Realm notary profile 的 `security_barrier` 规则；本规范 **MUST NOT** 为 Direct Conversation 新增专属 barrier 或 quorum，也 **MUST NOT** 宣称裸 CAS 自身能自动选出 loser。未获 finality 的 proposal 基于新 head 重建；若 signer equivocation 确实使两个不同值 accepted，cell 进入 `⊥` 并走既有 conflict recovery。

provisional Message **MUST** 引用 Event-time active generation 0；`found` 后的普通 Message **MUST** 引用 Event-time active exact-pair generation。未 active group 上的 Message **MUST** 拒绝。后来的合法 activation **MUST NOT** 追溯否定旧 Message。

### 7.4 exporter scheme 的既有代价

固定 `mls_exporter_aead_v1` 使 per-epoch `history_secret` 可保留、可重新封装，其 FS/PCS 按 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.10 退化为限定形态。该取舍 **MUST** 在 profile 中声明并对双方可查。需要更强前向保密的部署 **MUST** 另立 `mls_rfc9420` 变体 profile，并接受后加入设备无法读取历史。

founder **MUST** 在对方 `ak.realm_key.share` durable receipt 到达前保留相关 epoch `history_secret`，**MUST NOT** 按普通 epoch GC。确认丢失后，相关 Message **MUST** 以 `history_key_unavailable` 呈现为永久不可送达，**MUST NOT** 停留在含混的发送中状态。该值是 §9.1 的 client-local blocker，由持有该密钥状态的客户端自行判定；服务端 **MUST NOT** 在 wire 上返回它。

## 8. Stable identity、repair 与 participant authority

### 8.1 稳定坐标

同 pair 只有一个 immutable Realm 与 main Strand。leave、block、tombstone、scope 撤回、Agent pause、erasure 或恢复 **MUST NOT** 创建 successor Realm、Strand 或 binding。

canonical DM Realm **MUST** 拒绝 `ak.realm.destroy` 与任何 `ak.realm.tombstone`（`direct_conversation_terminal_forbidden`）。`ak.realm.archive` 与 `ak.realm.freeze` 是普通可逆 facet：具备合法 authority 与 CAS basis 时可设置，且 **MUST** 保留普通 unarchive/unfreeze 路径；它们只令 resolver 附带 send blocker，**MUST NOT** 产生 successor 或新坐标。

若错误实现或对象冲突仍使 canonical Realm 进入 terminal 或不可判定状态，pair **MUST** 按 §5.7 `suspended` 并等待显式 recovery；本地 slot **MUST NOT** 回到可创建状态。自动重开会再次允许第二个 Realm，正好破坏 founder-only 唯一性。

### 8.2 repair

exact-pair repair 的唯一 carrier 是标准 `ak.member.state{join}` `EventInitialSubmission` 与 `ak.profile.direct_conversation_repair.v1`。profile 锁定既有 pair/Realm/main Strand 与二人 mask。human 只能 self-rejoin；owned Agent 使用 `actor_id=agent_id, executed_by=controller_id` 及 immutable controller authorization。**MUST NOT** 加入第三 participant，也 **MUST NOT** 取得 grant/policy/admin/Strand/binding 变更权。

repair **MUST NOT** 读取 `created_by`、founder 身份或 bootstrap authority。current group 不可恢复时按 §7.3 创建 `generation = current + 1` replacement；回归方 **MUST NOT** 取得加入前无权解密的历史，历史访问仍按 event-time visibility 与 history-sharing policy 裁决。

任一 directional Contact 已撤回时，self-rejoin **MAY** 恢复成员位，但 KeyPackage claim、MLS Add 与发送 **MUST** 保持拒绝，resolver 返回 `suspended`；repair **MUST NOT** 恢复已撤回的同意。

repair 档的授权面是封闭的：`ak.authority.direct_conversation_repair.v1` 的 `action_allowlist` 恰为 `ak.member.rejoin.own` 一条，该 action 的 evaluator check 锁死 `leave -> join` 且要求 `actor` 等于 membership subject。因此在 repair source 下出示 `ak.member.leave.own` **MUST** 拒绝——日常自退归 `ak.authority.direct_conversation_participant.v1`，两档职责不重叠；代对方 join、以 repair 承载首次 join 或第三 participant、以及用 `ak.member.rejoin.own` 反向做 `join -> leave` 同样 **MUST** 拒绝。只测行为面（复用同一 Realm、投影新 generation、不下发旧 epoch key）而不断言 action 名与 authority source 的向量 **MUST NOT** 被当作该授权面的覆盖；本条的规范执行向量是 `ak.vector.capability.direct_conversation_repair_authority.v1`。

#### 8.2.1 replacement repair 的跨作者调度（normative）

`generation = current + 1` 的 replacement 需要**两个不同 actor** 各自签名：回归方 author
自己的 `ak.member.rejoin.own`，而 MLS Remove/re-add Commit 与 Welcome 只能由 **current peer
participant** author（回归方无法把自己加进 MLS group）；activation 又必须由持有私态的那一方
author（§7.3）。因此仅有 authority 是不够的——还需要一条把"该对端出手了"这一调度信号送达
对端的通道，且对端 **MAY 长时间离线**。

最终落入 recipient device queue 的 **carrier 是 `ak.member.repair.request`**，形态与
`ak.realm_key.request` 逐条对齐
（[`../crypto-media/device-lifecycle.md` §13.2](../crypto-media/device-lifecycle.md)）：它是
human recipient 分支中是 `DeviceMessageEnvelope` 上的可靠 to-device 触发消息；Native Agent recipient
分支把同一 closed content 投递到 accepted current Agent runtime endpoint。两者都走 destination durable
queue（服务端以
`ServiceDescribe.supported_features` 的 `ak.feature.member_repair.peer_relay.v1` 声明中继能力），
**MUST NOT** 使用 durable `EventEnvelope`，**MUST NOT** 进入 Realm history、reducer state 或
Seal 链，也 **MUST NOT** 走 Signal——Signal 是 ≤120s 的 live rail，离线对端收不到，且
[`../sync/signal.md` §5](../sync/signal.md) 已把密钥分发/历史恢复类消息划归 to-device。
content 见 [`device-message.schema.json`](../../artifacts/schemas/device-message.schema.json)
的 `member_repair_request_content`。

客户端 **MUST NOT** 用通用 `ak.self.device_messages.command.send` 自己列举 peer device。唯一发送入口是
`ak.self.direct_conversation.command.repair_dispatch`：请求只携稳定 `request_id`、exact content 与 requester
detached authorization，不携 recipient device id。source Principal Server 验证 authenticated session、
requester authority、accepted self-rejoin、双方 current directional Contact、immutable pair/Realm 与 observed
active-generation whole-value digest 后，按 current accepted peer service binding 定位 destination，并通过
`ak.peer.direct_conversation.command.repair_relay` 转交 exact request。relay body 由既有 RFC 9421 +
`Content-Digest` 服务身份通道覆盖；source service 必须追加 portable requester authority evidence，但它与外层
服务签名都只是 transport evidence，destination **MUST** 独立验证 requester 权威与下列 durable gates。

**它是非授权性的触发信号。** 对端 **MUST NOT** 因为收到请求就 author 任何东西，而是从
**签名事件日志**独立重验下列全部，任一不过即静默丢弃：

1. requester authorization 与 evidence 是封闭 XOR：human-device 分支的 `requester_device_id`、
   `verification_method`、`device_authorize_event_id` 必须逐字节匹配 portable device authorization evidence；
   Native Agent 分支的 `requester_agent_id`、`verification_method`、`agent_key_authorize_event_id` 必须逐字节
   匹配 current `AgentSignerEvidence`。两分支的 requester identity 都必须等于
   `requester_principal_id`、accepted rejoin Event 的 actor/subject 与 exact KeyPackage signer identity，且
   **MUST** 是本 pair 的另一 participant——不接受代他人请求，也不得引入第三 participant；
2. `rejoin_event_id` **MUST** 是已 accepted 的 `ak.member.rejoin.own` 且 subject 与
   `requester_principal_id` 一致——尚无已接受的 rejoin 就没有需要修的东西；
3. 双方 current directional Contact head **MUST** 仍有效：任一方向已撤回时 §8.2 要求
   KeyPackage claim、MLS Add 与发送保持拒绝，**MUST NOT** 因 repair 请求而放行；
4. `observed_active_generation_value_digest` **MUST** 逐字节等于对端读取的 current
   `ak.component.direct_conversation.active_mls_generation.v1` whole-value digest；该 digest 是
   `sha256(RFC8785_JCS(current accepted cell whole value))`，不是 activation Event id 的 hash。
   不相等表示 requester 观察陈旧，对端 **MUST** 丢弃且 **MUST NOT** author 第二个 replacement；
5. `requester_keypackage_ref` **MUST** 属于上述 current authorized device / Native Agent signer。
   peer author MLS Add 前调用 `ak.peer.keys.keypackages.command.claim` 时必须使用
   `claim_purpose=direct_conversation_repair`、`target_keypackage_ref=requester_keypackage_ref`；claim outcome
   的唯一 claim ref 必须与 request 逐字节相同。owner authority 只能原子 claim 该 exact、current、未消费、
   非 last-resort 的普通 KeyPackage；wrong principal/device/signer、陈旧、已消费、已撤销或 ref 不匹配全部
   通过同一 `claim_failed` 面 fail closed，不得退回按 device 任取一份（claim/consume 语义见
   [`../crypto-media/device-lifecycle.md` §9](../crypto-media/device-lifecycle.md)）。

repair dispatch 成功 outcome **只证明** destination service 已 durable 接受 relay 并完成一次原子
device snapshot enqueue；它不是业务 ack / receipt。业务应答仍只有 **durable Event 本身**——对端提交的
Commit/Welcome 与随后的 activation；请求方从 §9.1 resolver 的 `active_mls_generation_ref` 与
`active_mls_generation_value_digest` 配对推进观察到完成。这与 `ak.realm_key.request` 由 durable
`ak.realm_key.share` 应答同构。
规范 **MUST NOT** 为 repair 新增 ack/receipt Event 或 `SignalPayload` 变体：拒绝在业务协议上
不是事实，只是 generation 没有推进；请求方看到的仍是既有 resolver 状态。

**离线、重试与并发**全部复用既有语义，**MUST NOT** 另立机制：

- source Principal Server 以 `(requester_principal_id, request_id)` 在一个 durable transaction 内固化 self
  request digest、当时 current destination service binding、exact relay bytes 与 outbox 状态；exact replay
  返回同一 dispatch outcome / pending 状态，另一 digest `duplicate_conflict` 且不得更换 destination 或重新
  取证。network outcome 不确定时只能重发 exact same peer relay，不得生成新 request id 掩盖未知提交；
- destination Principal Server 在一个 durable transaction 内，以 `(Source-Service-ID, request_id)`
  固化 exact relay request digest，并从 accepted Direct Conversation binding 决定一个封闭 recipient target
  分支：human principal 分支快照 **peer 全部 current authorized devices**，为每个 target 分配并冻结不同的
  stable outer `message_id`，再将逐字节相同的 `member_repair_request_content` 原子入全部本地 per-device
  queues；Native Agent 分支必须从 accepted Agent key/session binding 解析唯一 current active runtime endpoint，
  冻结一个 stable `message_id` 并向该 endpoint 原子入队，且不得把 Agent 伪装成 `ak:device`。human snapshot
  digest 是 `H('ak.member-repair-target-snapshot-human-v1', device-id 排序的
  [{recipient_device_id,message_id}])`；Agent snapshot digest 是
  `H('ak.member-repair-target-snapshot-native-agent-v1',
  {recipient_agent_id,active_runtime_endpoint_ref,message_id})`。任一 target 写失败必须零入队。同
  source/request/digest exact replay 返回 byte-identical 原 outcome，另一 digest
  `duplicate_conflict` 且零写入；响应丢失或 worker 重启只能重放同一 snapshot / ids / bytes。批次之后
  新授权设备不追溯加入旧批次，recipient 上线后仍从 durable log 重验 current authorization 与上述全部 gate；
- 队列本身是可靠且 durable 的，对端上线后照常收取；`expires_at` 与 `message_id` 都是 destination
  transaction 生成并冻结的 transport envelope/runtime queue 字段，不属于 caller 提交的
  `member_repair_request_content`。外层 `expires_at` 到期后请求方 **MAY** 用新 repair `request_id` 重新
  dispatch，由 destination 生成新的 `message_id`；同一 `message_id` 配不同 canonical content **MUST** 以
  `duplicate_conflict`（`message_id_conflict`）拒绝；
- 请求方 **MUST NOT** 因为发过请求就等待或降级任何校验——它 **MAY** 在对端 push 式自发修复
  时直接观察到 generation 推进（等同于 §13.2 的 push 豁免）；
- 并发 winner 完全由 §7.3 决定：同 predecessor 下未 active 候选硬上限 16、第 17 个
  `mls_generation_proposal_fanout_exceeded`、`security_barrier` CAS 选出唯一 active，
  两个不同值都被 accepted 时按既有 `⊥` conflict recovery。**MUST NOT** 为 repair 新增
  barrier、quorum 或 winner 规则。

本条的规范执行向量是
[`ak.vector.direct_conversation.repair_dispatch.v1`](../../artifacts/registry/vector-registry.json)。

### 8.3 binding 与日常 authority

`ak.direct_conversation.bound` **MUST NOT** 承担阻止第二个 Realm 的职责——唯一性来自 §5.4 的 admission。它是 coordinates 与首次 exact-pair generation 的 participant 可见凭证，wire payload 绑定 `pair_key`、`participants_unordered[2]`、`realm_id`、`main_strand_id`、`founding_unit_digest`、分支化 `authorization_basis` 与 `initial_exact_pair_generation_ref`。`binding_digest` 是下述内容的 receiver-derived semantic digest，**不是 wire 字段**；producer **MUST NOT** 在 payload 中携带它，receiver 也 **MUST NOT** 从任何上游值采信它。

receiver 先必须验证 payload 的每个字段与 accepted founding unit、唯一 main Strand、该 pair 的 canonical authorization basis 及 generation-1 activation 一致，再构造以下唯一 closed object。`p0/p1` 是 `participants_unordered` 中两个 canonical stable subject DID 按 unsigned UTF-8 bytes 升序排列的结果；`e0/e1` 是 `authorization_basis.event_refs` 中两个 accepted Event ref 按同一顺序排列的结果。排序只用于此派生对象，**MUST NOT** 改写已签名 Event bytes。

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
  "initial_exact_pair_generation_ref": initial_exact_pair_generation_ref
}

binding_digest = H("ak.direct-conversation.binding-digest.v1", binding_object)
```

`H` 的精确定义见 §2：实际前像为 `UTF8("ak.direct-conversation.binding-digest.v1\n") || RFC8785_JCS(binding_object)`，结果为 `sha256:<lowercase-hex>`。`created_at`、Event envelope 的 author/proof 与 `binding_digest` 本身都不在 `binding_object` 中，因而不存在“先放入再排除”或自指前像。实现 **MUST** 执行 [`ak.vector.direct_conversation.binding_digest.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT，**MUST NOT** 使用无 domain 的 `SHA256(JCS(payload - created_at))`。

binding cell **MUST** 为 `or_set`，contract concurrency class 为 `merge_safe`。core OR-Set 元素身份仍是 [`../models/event-and-patch.md` §2.4.2](../models/event-and-patch.md) 定义的 Event dot，registry 仍精确投影 `tag={dot:true}, value=payload`；`(binding_digest, envelope.actor_id)` 是 Direct Conversation 领域视图的 **endorsement identity / 去重键**，不是 core OR-Set tag，也不是 wire 字段。同一 participant 对同一 digest 的多条 Event 在领域视图只计一个 endorsement；双方对相同 semantic payload 并发签名是两个兼容 add，**MUST NOT** 产生 `⊥`；不同 digest **MUST** 在 effect projection 前拒绝并触发 `suspended` 诊断。`found` 至少需要一份合法 endorsement；部署 **MAY** 登记要求双方 endorsement 的更高 profile，但 base **MUST NOT** 因两人同时 endorse 而失败。

binding **MUST NOT** 携带 `binding_state`、`supersedes_binding_ref`、永久 `mls_group_id` 或 consume receipt，也 **MUST NOT** 改变 membership、MLS、policy 或 Realm 坐标；若未来增加此类字段，**MUST** 拆为独立 `security_barrier` Move。

日常写 authority 唯一来自 `ak.authority.direct_conversation_participant.v1` 与 current accepted binding、exact-two membership、双方 current directional Contact heads、active exact-pair MLS generation 及 action-specific lifecycle gate 的交集。技术 root、`created_by`、founder 身份、本地 slot 与普通 grant **MUST NOT** 替代该 evaluator。root mask 只允许 current materialization 的精确 founding/repair effects；`found` 后 **MUST NOT** 恢复 owner/admin authority。

## 9. Resolver、隐私与 SDK 边界

### 9.1 resolver 状态

`ak.self.direct_conversation.read.resolve` 是唯一查询入口，其 outcome 为封闭判别联合：

| state | 条件 |
| --- | --- |
| `creation_required` | 无 accepted DM Realm，本方 `== founder`，且 current gate 允许创建；**MUST** 携带 §9.1.1 的 `next_founding_input` |
| `creation_blocked` | 无 accepted DM Realm 且本方 `== founder`，但 current Contact/account/Agent/profile/notary gate 确定性拒绝；**MUST NOT** author genesis Event 或派生 Realm token，也不得诱导重试 |
| `awaiting_founder` | 无 accepted DM Realm 且本方 `!= founder`；等待时长 **MUST NOT** 改变 create authority |
| `provisional` | 唯一 founding unit 已 accepted 但尚无合法 binding；只可执行 §7.2 的封闭 bootstrap 动作 |
| `found` | 至少一份合法 binding endorsement、唯一 active exact-pair generation 与普通 participant authority evaluator 均通过 |
| `suspended` | 已有 Realm 但 materialization/object conflict、terminal fault 或 membership/Contact/Agent/account/MLS/notary/lifecycle gate 阻止继续；blocker **MUST** 可机读 |
| `temporarily_unavailable` | 必需依赖不可验证，无法安全归类 |

求值优先级固定：依赖不足以验证 current basis 或 founder 时 `temporarily_unavailable`；无 Realm 时区分 `creation_blocked | creation_required | awaiting_founder`；有 Realm 后 identity/materialization/terminal/notary 冲突优先 `suspended`；否则无 binding 为 `provisional`；最后才在 binding、generation 与 daily gates 齐备时 `found`。`retry_after` 只是调度提示，**MUST NOT** 产生 fallback authority。

resolver 对已存在的 active-generation singleton cell **MUST** 同时返回
`active_mls_generation_ref` 与 `active_mls_generation_value_digest`，或同时省略二者；后者是
`sha256(RFC8785_JCS(current accepted cell whole value))`。`found` 必有该二元组；`provisional` /
`suspended` 在 cell 已存在时也必须携带，尤其 replacement repair 的 `suspended` 状态不得隐藏它。
客户端 **MUST NOT** 从 Event ref、最大 generation、局部 MLS snapshot 或坐标猜 whole-value digest。

existing 坐标 **MUST NOT** 因 offline、presence、session、KeyPackage 库存、grant/policy freshness 或 MLS reconcile 而被隐藏。

#### 9.1.1 `creation_required` 的 authoring material（normative）

`DirectConversationFoundingUnitSubmission` 必填 `founder_basis_evidence` 与
`source_service_binding`，二者都是**服务端自己持有**的对象（前者由 Contact 证据投影得到，
后者就是本服务签发并接受的 binding）。若 resolver 只回一个无 material 的
`creation_required`，则 founder 在协议层不可能构造该 unit——这正是
[`service-http-binding.md` §2.2.2](../sync/service-http-binding.md) 供给闭合律禁止的形态。
因此：

- `creation_required` **MUST** 携带 `next_founding_input`，其成员名与 submission 的对应成员
  **逐字节一致**（`founder_basis_evidence`、`source_service_binding`），caller 原样搬运，
  **MUST NOT** 引入任何改名映射；服务端 **MUST NOT** 在该容器里附带 Event bytes、坐标、
  `idempotency_key` 或 receipt——三条 Event 仍由 founder 自签，服务端**永不**代签。
- 服务端 **MUST** 按本 pair 选择唯一分支：peer Contact founding 用 `human` 分支（含完整
  bundle 与 root continuity chain），own-Agent founding 用 `controller_agent` 分支；
  **MUST NOT** 同时返回两个分支，也 **MUST NOT** 返回与 §5.4 验证口径不同的另一份证据。
- **无料时不得返回本状态**：服务端组装不出或验证不了该 material 时 **MUST** 返回
  `temporarily_unavailable`，**MUST NOT** 返回不带容器的 `creation_required`，也 **MUST NOT**
  为此新增错误码或状态值——求值优先级表里 `temporarily_unavailable` 本就覆盖"依赖不可验证"。
- **新鲜度**：该 material 是响应时刻的快照，**不是** authority。caller **MUST NOT** 跨
  Contact 状态变化复用它；material 在提交时已陈旧的，submission 侧按 §5.4/§6 既有校验拒绝
  （basis 不匹配、continuity 断链、binding 非 current），**MUST NOT** 因为它来自 resolver
  就放宽任何一条校验，服务端也 **MUST NOT** 把 caller 回传的 material 当作可信输入——
  它 **MUST** 以自己 current 的那份重新验证。
- **并发 founder 设备**：同一 founder 的多台设备 **MAY** 同时取得 `creation_required` 与
  相同 material；胜负仍只由 §5.5 的 `(founder_id, trust_domain_id, pair_key)` slot CAS 决定，
  失败方得到 `direct_conversation_slot_already_committed` 后 **MUST** 改走 resolver 取回既有
  坐标，**MUST NOT** 用自己那份 unit 重试。material 相同不构成"两份 unit 等价"。

联邦面（`ak.peer.events.command.submit` 的同形字段）由 source 服务器在 server-to-server
一跳上投影供给，**MUST NOT** 要求 founder 客户端亲手跨服务器搬运这些证据。

实现 **MUST** 执行 [`ak.vector.direct_conversation.founding_authoring_material.v1`](../../artifacts/registry/vector-registry.json)：
它断言容器存在性、成员名逐字一致、单一分支、无 Event bytes / 坐标 / receipt、无料时降为
`temporarily_unavailable`，以及提交侧对回传 material 的重新验证。

#### 9.1.2 accepted-at service binding 的建立与同服务续期（normative）

`AcceptedAtServiceBinding` 只能在 principal DID 已发布、PCR 已 accepted 且 principal session 已建立后，
通过 `ak.self.principal_service_binding.command.prepare` →
`ak.self.principal_service_binding.command.commit` 两步建立；它 **MUST NOT** 被塞进首次 registration，
因为其中的 DID `authority_evidence` 只有发布后才能由服务端验证，提前生成会形成未来值依赖。

- prepare 只接受 `request_id` 与可选 `expected_current_binding_digest`。省略表示 create-if-absent；
  携带表示 same-service renewal，且必须逐字节命中 current binding。服务端从 authenticated principal、
  current verified DID authority、自己的 service key / trust domain / HTTPS origins 与自己的时钟组装
  frozen core，caller **MUST NOT** 提交这些字段；
- 服务端生成 single-use `challenge_id`，把它逐字节写入 core 的
  `authorization_challenge`，令它进入 `binding_digest`；`accepted_at = not_before = issued_at`，
  所有时间固定为 UTC millisecond。prepare outcome 与 challenge state 必须 durable；同 request/body
  exact replay 返回同一未消费 outcome，同 request 不同 intent 为 `duplicate_conflict`；
- principal 对精确 transcript
  `H('ak.principal-service-binding-proof.v1', {binding_digest, accepted_at,
  proof_purpose:'principal_authorization', verification_method, audience:service_id})` 签名；
  `proof.created_at` 必须等于 `accepted_at`。commit 只携 request/challenge/digest/proof，服务端从
  durable prepare record 取 draft，重算 digest，并按 `accepted_at` 的已验证 DID authority 验证 method；
- commit 在一个事务中执行 current-binding CAS、写 immutable accepted binding、消费 challenge、
  生成同结构但 `proof_purpose='service_acceptance'` 的 service proof，并保存 byte-identical outcome。
  exact request replay返回原 outcome；同 challenge 配不同 request/digest/proof、过期、已被另一请求消费、
  current pointer 已变化全部零写入 fail closed；
- binding 是历史 accepted-at 证物，不做原地修改或删除。same-service renewal 以
  `predecessor_binding_digest` 前向连接；principal/account/PCR lifecycle 不满足时 current use 被 gate
  抑制，但历史 proof 仍可验证。跨服务迁移继续使用三方签名 `principal_service_cutover` continuity，
  **MUST NOT** 把本地 renewal 冒充 cutover 或用“撤销历史 binding”替代 writer fence。

resolver 只有在 current pointer 指向一份按上述流程完整验证的 binding 时，才可把它放入
`next_founding_input.source_service_binding`；缺失、过期、CAS 冲突或 authority freshness 不足均返回
`temporarily_unavailable`，不得现场代 principal 签名或从 service metadata 拼装一个 binding。

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

SDK planner 只组合 canonical public facts（Event/Seal/binding/active-generation cell）、authenticated service durable facts（source acceptance receipt、delivery outbox 状态）、controller-private durable facts 与 local ephemeral 状态；每项携 source ref、frontier/epoch、freshness/expiry 与 privacy label。客户端 bytes 只负责 authoring 与 exact retry。unknown 或 stale 只阻断相关 action，**MUST NOT** 隐藏 existing DM 坐标。

SDK **MUST NOT** 实现事后从多个 binding 中选择 canonical 的逻辑，也 **MUST NOT** 实现任何 fallback、takeover 或 minimum-token selector。

## 10. 规范性回归边界

founding 相关的机读入口是 [`ak.vector.direct_conversation.founding_unit.v1`](../../artifacts/registry/vector-registry.json)
与 [`ak.vector.direct_conversation.founding_admission.v1`](../../artifacts/registry/vector-registry.json)，
机读 fixture 见 [`direct-conversation-fixture.json`](../../artifacts/fixtures/direct-conversation-fixture.json)。

Conformance **MUST** 覆盖：

- founder 派生：normal 取 responder、glare 取 `requests[0]` issuer，两侧独立计算一致；把 normal 分支误算为 requester **MUST** 被两侧 admission 拒绝；
- 非 founder 提交 founding unit 在 self 与 peer 两条路径均拒绝；
- caller-authored 派生：`realm_id`、`main_strand_id` 与 `founding_unit_digest` 由两个独立实现从同一 unit bytes 重算得到逐字节相同结果；请求另行携带坐标、服务端预分配 ID、reserved/materializing draft 与 coordinator 选举形态 **MUST** 被拒绝；
- founder 多设备并发各自 author 出不同 unit 时，同一 Principal Server 的唯一 slot **MUST** 只接受先到的合法 unit，后到者返回 `slot_already_committed` 且零写入，两台设备随后从 resolver 得到同一组坐标；
- founder 与 peer 位于同一 Principal Server 与位于两台 Principal Server 两种部署下，self 路径与 §5.6 peer 路径 **MUST** 得到相同 unit digest、相同 receipt 语义与相同 admission verdict；
- 幂等与崩溃恢复：同 `idempotency_key` 同 unit 的 exact retry 返回 byte-identical receipt 且 `accepted_at` 不变，同 key 不同 unit 返回 `duplicate_conflict`；unit 提交、receipt 落库、outbox 入队与响应丢失各崩溃点重放同一 signed bytes 均恢复同一结果，且不产生第二组 Event；
- §5.6 branch 的 dependency 不足 **MUST** 是 top-level 409 `dependency_missing` 加零写入，**MUST NOT** 出现只接受一或两条 Event 的 partial；
- basis 形态：unit 内 `ak.member.state{join}` 与 `ak.strand.create` 的 no-basis shape 被接受；同一 no-basis `ak.strand.create` 出现在 founding unit 之外（普通 Realm、同 Realm 的后续 Strand 或单条提交）**MUST** 被 admission 拒绝，而 unit 内改携 `seal_ref`/`auth_context`/`seal_basis` 也 **MUST** 被拒绝；
- recontact continuity：多轮 tombstone/recontact 后仍重算出同一根 founder basis 与同一 founder；缺 `previous_terminal_basis_id`、成环、分叉或两 proof 导出不同根均拒绝；
- accepted-at 与 current gate 分离：source 在旧 current basis 有效时 accepted 的 unit 延迟到撤回后才到 peer，peer 仍接受历史 identity 并按 current gate 投影 `suspended`；
- 对方设备离线时 MLS 建立与发送成功；对方服务器不可达时 founder 仍可建 Realm、激活 generation 0 并发出真密文；
- generation-1 activation 由 founder author **MUST** 以 `direct_conversation_activation_author_invalid` 拒绝，由 joiner author 且前提齐备则接受；
- 跳代、回退、未 active group 作 predecessor、第 17 个候选 group 的既定错误；
- 无 fallback：non-founder 无论等待多久、伪造标记、回填时间或携 negative query 结果，create 均拒绝；
- pair materialization conflict：模拟受信 service 对同 pair 签出两份不同 unit/receipt 时两 Realm 全部冻结，**MUST NOT** 按 Realm token 词法顺序或到达时间选 winner，也 **MUST NOT** 发 tombstone；
- 同对象 token 不同 Genesis 继续走 `object_identity_conflict`，**MUST NOT** 与 pair materialization conflict 合并为一个 selector；
- 终态：`destroy` 与任意 `tombstone` 拒绝；合法 archive/freeze 及其反向操作沿普通路径生效且坐标不变；违规 terminal 后 slot 保持关闭且 resolver `suspended`；
- binding：逐字节 KAT 覆盖固定 domain、closed `binding_object`、participants / authorization refs 换序归一、`created_at` 与 Event author/proof 排除，任一语义字段改变必须产生不同 digest；双方并发同 semantic endorsement 得到两个 core OR-Set dot 且不 `⊥`；同 actor 重复在领域视图只计一个；不同 semantic digest 在 effect projection 前拒绝；current Contact/service refresh 不改 binding digest；
- owned Agent：controller↔own-Agent 只携 `direct_conversation_agent_provision` 时命中 DM variant；改用 `purpose="managed_agent_control"`（那是 PCR genesis 分支，见 [`./key-management.md` §3.6.3](./key-management.md)）、同时携两个 DM roles 或 DM/PCR variants 多命中均零写入拒绝；Agent↔第三方分别覆盖 founder=Agent 与 founder=other；
- 隐私：非 participant 对任意阶段的 pair 查询与不存在逐字相同。

synthetic glare accepted Event、跨双方 CAS、server next-action、successor Realm/Strand、timeout takeover、minimum-token 归一、server-allocated founding ID、reserved/materializing draft、min-service-DID coordinator 与 view-dependent effect digest **MUST** 由负例拒绝。
