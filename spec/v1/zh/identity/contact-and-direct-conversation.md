---
title: Contact & Direct Conversation Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - consent-model.md
  - ../discovery/discovery-directory.md
  - ../models/realm-and-space.md
  - ../models/strand-and-message.md
  - ../models/relation.md
  - ../sync/service-http-binding.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本文定义 Arkret v1 中 principal 与另一个 principal 建立 1:1 私聊的协议级生命周期。它不是 UI 联系人列表说明，也不是对 consent、Realm 或 Strand 的别名重述，而是把联系人关系、managed Agent controller binding、action consent gate、direct conversation binding 与消息载体明确分层。

## 1. 真相源分层

同一对用户之间至少存在五个相邻但互不替代的事实源：

| 层 | 标识 | 作用域 | 真源问题 | 不得替代 |
| --- | --- | --- | --- | --- |
| L1 holder-private 备注 | `ak.contacts.actor.<did>` account-data | holder 本地私有 | "我本地怎么备注、置顶、过滤这个 DID" | 不表示对方接受 |
| L2 协作图关系 | `ak.relation.*` | Realm 内 | "这个 Realm 里的 Strand / Message / Actor / Object 如何相连" | 不表示跨 Realm 社交关系 |
| L3 联系人关系 | `ak.contact.*` fact / operation | principal 级、跨 Realm | "双方请求、接受、拒绝、终止联系人关系到了哪一步" | 不表示 action 授权本身 |
| L4 action gate | `ak.consent.*` | holder Principal Control Realm | "peer 是否可发起 direct_message / invite / call / presence" | 不表示 pending / rejected / tombstoned |
| L5 会话载体 | direct conversation binding + DM Realm + 主 Strand | Realm / Strand | "这对 actor 的 1:1 消息写到哪里" | 不表示双方仍是联系人 |

`ak.contact.*` 作为 operation id 与 event kind 使用单数 `contact`。既有 account-data key 保持复数 `ak.contacts.*`，只表达 holder-private 备注、标签、置顶和本地过滤。实现文档和 catalog description MUST 明确区分二者，不得把 account-data contact note 称为 contact relation truth source。

Consent 的有效状态只有 `active` / `no-consent`；`revoke` 是操作，不是关系状态。联系人关系的 pending / accepted / rejected / tombstoned MUST 来自 contact fact projection，而不是从 consent cell、共享 DM Realm 或服务私有 `contacts` 表反推。

## 2. Contact Fact Log

联系人关系的真源是 principal-scoped contact fact log。holder 自己签发的 contact facts 默认写入 holder 的 Principal Control Realm（PCR）。普通 Collaboration Realm 不承载 contact relation truth。

对端签发的 request / accept / reject / tombstone facts 以原签名 envelope 参与本 holder 的 contact projection。实现 MAY 在本 holder 的 PCR 中保存为 receipt / mirror 以便多设备同步和离线验证，但 receiver MUST NOT 重新签发成自己的本地 fact。

| event kind | issuer | 主要字段 | 语义 |
| --- | --- | --- | --- |
| `ak.contact.requested` | requester | `request_id`, `target`, `requested_scopes[]`, `requester_consent_refs[]` | 发出请求；requester 侧形成 `pending_outgoing`，target 收到后形成 `pending_incoming`；`requested_scopes[]` 非空时 `requester_consent_refs[]` 必填 |
| `ak.contact.accepted` | request target | `request_id`, `requester`, `granted_scopes[]`, `consent_grant_refs[]` | 接受请求；MUST 引用原 request；MUST 写 target 控制的 consent grants |
| `ak.contact.rejected` | request target | `request_id`, `requester` | 拒绝请求；MUST NOT 隐式写 consent grant |
| `ak.contact.tombstoned` | 任一参与方 holder | `peer`, `revoke_scopes[]`, `consent_revoke_refs[]` | holder 终止自己这一侧的联系人关系；也可由 requester 用于撤回仍处 pending 的 request；默认 revoke holder 给 peer 的 contact-managed consent |

Issuer 约束是硬边界：

- requester 可以声明"我请求联系 target"，也可以预先给 target 写 requester 侧 consent grant。
- target 才能声明"我接受或拒绝 requester"。requester MUST NOT 替 target 写 accepted / rejected，也 MUST NOT 替 target 写 consent。
- 任一 holder 都可以 tombstone 自己与 peer 的关系视图。tombstone 不会修改 peer 的 contact fact log；peer 只能在收到 tombstone fact 后把关系投影降级。若 requester 在 `pending_outgoing` 阶段发布 tombstone，target 收到后 MUST 将对应 `pending_incoming` 降级为 non-active（`tombstoned` 或等价 withdrawn projection），且后续对该 `request_id` 的 accept MUST `failed_precondition`。

`request_id` SHOULD 使用 `ak.contact.requested` 的 `event_id`。实现 MAY 用 `(holder, peer, outstanding_request)` 做幂等去重，但不得把重复 request 折叠成 consent grant。去重折叠多条等价 request 时，投影行与后续 respond MUST 以**最早未终结**的 `ak.contact.requested` 的 `event_id` 为 canonical `request_id`；对任一重复 request 的 accept / reject MUST 视为作用于该 canonical `request_id`，两端不得各自选边。

**交叉请求（glare，normative）**：若 A 与 B 的 pending request 尚未终结，而任一方收到对方反向的 `ak.contact.requested`，两条 fact 均保留用于审计，但 effective contact row MUST 折叠为对按 canonical event ordering 较小的 request 的 `accepted`；较大 request 不得再独立 accept / reject。双方 operation layer MUST 以一个原子动作写该 canonical request 的 `ak.contact.accepted` 与所需 consent grants。相同 `(issuer, grantee, scope)` 的 contact-managed consent grants 按 active OR-set dot 合并为一个 effective scope，不得因两条交叉 request 在 UI 或授权判定中重复计数。若原子写入任一必需 consent grant 失败，整个折叠 MUST fail closed。

## 3. Contact 与 Consent

Contact 负责关系状态：`pending_outgoing` / `pending_incoming` / `accepted` / `rejected` / `tombstoned`。Consent 负责 action gate：`direct_message` / `invite` / `voice_call` / `video_call` / `presence` 是否允许。

`ak.self.contact.command.request` 默认请求 `requested_scopes=["direct_message"]`。若 request 请求某个 scope，requester MUST 在自己的 PCR 同步写一条给 target 的 `ak.consent.grant`，并在 `requester_consent_refs[]` 中引用它。若该 grant 写入失败，request MUST fail closed，或移除该 scope 后重新签名。该 requester-side grant 在 contact accepted 前只表示 requester 允许 target 发起对应动作；`ak.self.direct_conversation.command.resolve` 仍 MUST 检查 accepted contact，不得只凭 consent grant 创建联系人 DM。

该 requester-side grant 的生命周期 MUST 与 request 绑定，不得在 request 终结后长期残留为开放的反向 consent gate：当 requester 看到该 request 对应的 `ak.contact.rejected`、`ak.contact.tombstoned`，或 request 在 `contact_request_pending_ttl`（部署可配，默认 SHOULD ≤ 14 天）内仍处 `pending_outgoing` 而超时（无论先到者），requester 的 PCR MUST 自动对 `requester_consent_refs[]` 引用的 active grant dots 发 `ak.consent.revoke`。这些 dots 同时是 contact-managed consent，故也纳入 §3 / `ak.self.contact.command.tombstone` 的级联枚举范围；若 requester 无法枚举完整 dots，MUST 按 partial / fail-closed 处理并标记，不得报告完整撤销。该自动 revoke 不依赖 target 配合，目的是关闭"已死 request 留下长期开放的 requester→target 反向 consent gate"的暴露面。

**`contact_request_pending_ttl` 计时锚与权威侧（normative）**：过期计时锚 MUST 是 canonical `ak.contact.requested` fact 的 `created_at`，去重折叠时取 §2 选定的最早未终结 canonical request。`contact_request_pending_ttl` 是 holder 本侧投影 / operation policy：requester 侧用本侧 TTL 决定何时自动 revoke `requester_consent_refs[]`；target 侧用本侧 TTL 决定 `ak.self.contact.command.respond` 是否仍可接受该 `request_id`。任一侧观察到对方已 tombstone / reject / revoke 使 consent gate 不再满足时，resolver 与 direct conversation gate MUST fail closed；迟到的 accept fact MAY 作为审计事实保存，但不得让本 holder 的 effective contact row 越过已失效的 contact-managed consent gate。

`ak.self.contact.command.respond(action="accept")` MUST：

1. 验证 request 存在、target 是当前 holder、request 未被 target 已拒绝 / 接受 / 终止。
2. 写 `ak.contact.accepted` fact。
3. 对每个 `granted_scopes[]` 写 target 控制的 `ak.consent.grant`，并把 event refs 写入 `consent_grant_refs[]`。

`granted_scopes[]` MUST 是 `requested_scopes[]` 的子集，除非 response UI 明确执行"扩展授权"并把扩展 scope 写入 accepted fact 的审计字段。默认 accept 不得静默扩大 requester 请求范围。

`ak.self.contact.command.respond(action="reject")` MUST 只写 `ak.contact.rejected`，不得隐式写 consent。

Contact-managed consent dots 指通过该 contact request / accepted fact 的 `requester_consent_refs[]` 或 `consent_grant_refs[]` 引入、或后续明确绑定到该 contact relation 的 active grant dots，即 [`consent-model.md`](./consent-model.md) §5 的 `active_dots(cell)` 中对应 intent 的 add dots。

`ak.self.contact.command.tombstone` MUST 写 `ak.contact.tombstoned`。`revoke_scopes[]` 缺省为 holder 给 peer 的全部 contact-managed active scopes；operation MUST 枚举并 revoke 这些 active grant dots，并把 revoke refs 写入 tombstone fact。若实现无法枚举完整 dots，必须返回 partial / fail-closed 结果，不得报告完整 tombstone。实现不得默认撤销 holder 给同一 peer 的非 contact-managed consent（例如独立组织 invite 授权），除非 UI / admin 明确选择 full peer revoke 并在 tombstone fact 中审计。

Consent revoke 与 contact tombstone 仍是两条显式事实：单独 revoke consent 只会减少 `effective_scopes`，不得自动删除 accepted contact；tombstone 也不得伪造不存在的 revoke event。

`ak.self.contact.command.tombstone` MAY 作用于 pending request：requester 对 `pending_outgoing` tombstone 表示撤回；target 对 `pending_incoming` tombstone 表示本地丢弃/拒收该 request 且不写 `ak.contact.rejected`。任一 pending tombstone 后，同一 `request_id` 的后续 accept/respond MUST 返回 `failed_precondition`（reason=`contact_request_not_pending` 或更具体的 `contact_request_expired`）。

## 4. Contact Operation Surface

全部 contact operation 要求 `user_session`，落在 `/_arkret/self/...` trust surface。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ak.self.contact.command.request` | `POST /_arkret/self/contacts/request` | `ContactRequestRequestBody` / `ContactRequestOutcome` | 写 requester 侧 request fact，并投递签名请求给 target；request body MAY 含可选 `message`(1..2000,NFC,wire bound 登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)),透传到 `ak.contact.requested` 的 `message` 字段作为加好友附言；target 在对端 PS 时 MUST 携带可选 `recipient_service_id`(见 §4.1)以驱动跨端投递；首次接触 MAY 携带 `introduction_evidence`（例如 `locator_ref`、`handle_claim` 或 `explicit_address`），issuer 侧 PS 若无法构造合规 evidence MUST 按 `explicit_address` 低信任处理 |
| `ak.self.contact.command.respond` | `POST /_arkret/self/contacts/respond` | `ContactRespondRequestBody` / `ContactRespondOutcome` | 由 target 接受 / 拒绝 request；accept 同步写 target consent grants |
| `ak.self.contact.query.list` | `GET /_arkret/self/contacts` | `ContactList` | 从 contact facts 投影，并附带 consent-derived scopes；human contact 的 `agents[]` 仅投影当前 viewer 具有 accepted `direct_message` contact / consent、且 lifecycle active 的 accountable native personal agents |
| `ak.self.contact.command.tombstone` | `POST /_arkret/self/contacts/tombstone` | `ContactTombstoneRequestBody` / `ContactTombstone` | 写 holder 侧 tombstone；默认 revoke holder 给 peer 的 contact-managed consent；request body 含可选 `block_peer`(默认 false),为 true 时额外把 peer DID 写入 holder `invite_receive_policy.denied_subjects`(硬拉黑) |

`ContactListRow` MUST 至少区分：

- `pending_outgoing`：本 holder 发出 request，尚未看到 target accept / reject。
- `pending_incoming`：本 holder 收到 request，尚未 respond。
- `accepted`：已看到合法 `ak.contact.accepted`，且本 holder 未 tombstone。
- `rejected`：已看到合法 `ak.contact.rejected`。
- `expired`：request 自 canonical `ak.contact.requested.created_at` 起超过本 holder `contact_request_pending_ttl` 后的派生投影态；过期不是新的 contact fact，但对该 `request_id` 的 accept/respond MUST fail closed。
- `tombstoned`：本 holder 已 tombstone，或已看到 peer tombstone 且投影选择暴露该状态。

request 到达 `rejected`、`expired` 或 `tombstoned` 后，后续重新发起 contact request 不复用旧 `request_id`；除非 Realm / holder policy 另有 cooldown 或 block_peer 限制，协议本身不禁止重新 request。

`ContactListRow` 的 scope 投影 MUST 是方向化的，至少区分 `granted_by_me[]`（我允许 peer 发起的 scopes）、`granted_to_me[]`（peer 允许我发起的 scopes）与 `bidirectional_scopes[]`。若响应使用简写字段 `effective_scopes[]`，它 MUST 等价于 `bidirectional_scopes[]`，不得把单向 consent 显示成双方都可用。

看到 peer 的合法 `ak.contact.tombstoned` 后，本 holder 的 projection SHOULD 立即把该 row 从 `accepted` 降级为 `tombstoned` 或等价 non-active state，避免列表长期显示 accepted 但 direct-message gate 已关闭。peer tombstone 尚未同步到本 holder 前，列表与 gate 可能短暂不一致；resolver 仍以最新可验证 contact projection + consent gate fail closed。

列表 MAY 包含 `direct_conversation` 摘要，但该字段只能来自已 materialize 的 immutable binding，不得反向决定 contact state。摘要固定携带同一 `realm_id`、`main_strand_id`、`binding_event_ref`，其 state 只有 `found | suspended`；创建进度只存在于 resolver outcome / durable operation，摘要不得出现 `creation_required`、`temporarily_unavailable` 或任何 retirement/candidate 状态。

### 4.1 跨 Principal Server 投递

§2 要求「对端签发的 request / accept / reject / tombstone facts 以原签名 envelope 参与本 holder 的 contact projection」。当 issuer 与 target holder 不在同一 Principal Server 时，该交换必须经由专门的 peer 投递面完成；本地 `ak.self.contact.*` operation 本身只写 issuer 侧 fact，不跨端。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ak.peer.contacts.command.submit` | `POST /_arkret/peer/contacts` | `PeerContactDeliveryRequest` / `PeerContactDeliveryOutcome` | issuer 侧 PS 把签名的 `ak.contact.requested` / `accepted` / `rejected` / `tombstoned` envelope 投递到 target holder 的 PS |

该 peer 端点与 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) §5 的 `ak.peer.invites.command.submit` 同级、风格一致：要求 service-to-service 认证、`Destination-Service-ID` 等于 `contact_address.recipient_service_id`、RFC 9530 `Content-Digest` 与 RFC 9421 message signature。约束如下：

- `contact_event` MUST 是 issuer 原签名的 `ak.contact.*` EventEnvelope；recipient MUST 以原签名 envelope 参与 projection，MUST NOT 重新签发成自己的本地 fact（§2 硬边界）。
- `fact_kind` MUST 等于 `contact_event.kind`。
- `contact_address.subject_id` 是该 fact 在 recipient 侧的归属 holder：`ak.contact.requested` 投递到 request target；`ak.contact.accepted` / `rejected` 反向投递回原 requester；`ak.contact.tombstoned` 投递到被 tombstone 的 peer。
- `ak.contact.requested` 的 `PeerContactDeliveryRequest` MUST 携带 `introduction_evidence`，其 kind 集合与 invite delivery 对齐：`locator_ref`、`consent_grant`、`shared_realm`、`handle_claim`、`same_principal_server`、`explicit_address`。`handle_claim` 只证明 target 显式披露了可解析 handle，不等于 target 同意该 requester 联系自己；`explicit_address` 只表示 requester 知道或猜测 `subject_id + recipient_service_id`。
- `ak.contact.requested.payload.introduction_evidence_digest` MAY 携带 `digest(canonical_json(private_contact_introduction_evidence))`，用于把 durable contact fact 与私有投递 evidence 审计关联；raw evidence 不得写入 contact fact log。若该 digest 存在，recipient MUST 与 `PeerContactDeliveryRequest.introduction_evidence` 核对；不匹配 MUST fail closed 或按 `explicit_address` 低信任处理。
- recipient MUST 对 `introduction_evidence` 执行与 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) §2 同构的校验。对 `consent_grant`，scope MUST 覆盖 `requested_scopes[]` 中的动作（或为 `any`）；对 `handle_claim`，MUST 校验 handle claim 绑定 `contact_address.subject_id`、issuer / Directory trust、domain allowlist、expiry、visibility / audience 和部署约束。若 handle claim 或 Directory 解析结果携带 `member_delivery_binding`，还 MUST 校验 `member_delivery_binding.recipient_service_id == contact_address.recipient_service_id`；缺少该绑定时，recipient 只能把 handle claim 作为 subject 可发现性 evidence，不能把它当作 service DID 授权。校验失败 MUST 降级按 `explicit_address` 处理。
- recipient MUST 使用 subject 私有 `invite_receive_policy` 与 Principal Server `receive_policy_constraints` 的交集作为首次接触接收策略，尽管 schema 名称保留 `invite_receive_policy`。`handle_claim_behavior` 控制通过 verified handle 发起的 contact request 是否 drop / quarantine / notify；`explicit_address_behavior` 控制 DID+server 直达请求。部署约束可以禁止 handle、禁止 explicit address、限制 handle domain / issuer / Directory DID / subject DID method，且只能收紧不能放宽。
- recipient 把 fact 投影进 `subject_id` 的 contact projection（target 侧形成 `pending_incoming`；requester 侧 accept 形成 `accepted` 并带 `consent_grant_refs[]` / `invite_consent_grant_ref`；reject 形成 `rejected`；tombstone 把对应 row 降级）。
- recipient 的 `invite_receive_policy.denied_subjects` 命中 issuer 时，MUST fail closed（drop + opaque），与 invite 投递的隐私侧信道防护一致。
- **首次接触附言不绕过 consent gate（normative）**：`ak.contact.requested` 携带的 `message`（1..2000 自由文本，透传到 `contact_requested_payload.message`）在 target **accept 之前**是来自陌生 requester 的未经同意文本，不得直接落入 target 的可见 contact projection 充当骚扰 / 钓鱼 / 未授权信息投递通道。当 requester **不**在 target 的既有 contact 或 consent 白名单内（首次接触）时，recipient MUST 把该 `message` 与 invite 的 quarantine inbox 对齐处理：在 `pending_incoming` 行中 **MUST** 收窄 / stub 化（如仅显示"有附言，accept 后可见"而不得直接渲染 2000 字正文），或把附言暂存于 quarantine 区，待 target 显式 accept / 放行后再呈现。`invite_receive_policy.denied_subjects` 命中只在已知拉黑时 fail-closed；本约束补齐首次接触（尚无 block 记录）时的默认防护，使加好友附言不绕过 [`consent-model.md` §6.1](./consent-model.md) 的 quarantine gate。已在白名单 / 已 accepted contact 的 requester 的 `message` 不受此收窄约束。

因 v1 principal DID（如 `did:web` / `did:webvh`）不强制内嵌 home Principal Server，requester 发起跨端 `ak.self.contact.command.request` 时 MUST 携带 target 的 `recipient_service_id`（与 invite 寻址同构），issuer 侧 PS 据此投递；同 PS 的 request 不需要该字段，本地直接投影。

## 5. Private Contact Discovery 边界

`ak.find.directory.query.private_contact_discovery` 只回答"哪些本地 connection identifier 在 provider 的可联系集合里"，以及 v1 core 已允许的最小 invite / consent handoff stub。

v1 规范采用窄读：private contact discovery 响应 MAY 在 PSI set-membership 命中结果旁附带最小 invite / consent handoff stub，但该 stub 只能声明 consent state hash、grant / revoke 状态或下一步引导。它 MUST NOT 携带 reachability proof、完整 profile、成员资格、Realm membership、读取权限、关系图谱，或可直接创建 contact relation 的 token。

该 handoff stub 携带 consent state hash 时,**MUST** 满足 [`consent-model.md` §6.2.1](./consent-model.md)（PSI 命中位时序侧信道）与 [`§6.2.2`](./consent-model.md)（Consent state hash 侧信道）的侧信道防护 normative 约束:consent state hash MUST 加 per-requester / per-session salt（或改为 holder-authorized opaque token）,MUST NOT 输出裸的、跨 requester 稳定的 hash（§6.2.2）;PSI 命中位 MUST 经粗粒度时间 bucket 化并按 `(requester, holder)` 维度限速，防止时序侧信道（§6.2.1）。实现 MUST NOT 在本 stub 中输出未加盐的 consent state hash。

本规范不新增、也不依赖 contact request handoff token。若未来需要 discovery 直接返回可发起 `ak.self.contact.command.request` 的 token / credential，必须另行注册 profile 与 response schema。在那之前，用户选择联系某个 PSI 命中后，客户端才向目标 principal 披露自己的 DID / pairwise DID 并调用 `ak.self.contact.command.request`。

## 6. Direct Conversation Resolver

ak.self.direct_conversation.command.resolve 是一对 stable subject DID 到唯一 1:1 会话的幂等入口。联系人侧栏中的 owned Native Personal Agent 也走该入口；它不依赖当前 Collaboration Realm / Strand，不得调用 Sidecar ensure。

collaboration_role="direct_conversation" 的 Realm MUST 从普通 Collaboration Realm discovery/navigation projection 排除。该约束定义协议 discovery surface，不规定按钮、侧栏或窗口布局。DM Realm 可以参与同步与恢复，但只能经本节专用 resolver 进入。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| ak.self.direct_conversation.command.resolve | POST /_arkret/self/direct-conversations/resolve | DirectConversationResolveRequestBody / DirectConversationResolveOutcome | 解析或创建 pair 的唯一稳定 DM Realm 与 main Strand |

Resolver MUST 先建立恰好一种 authorization basis：

1. accepted_contact：双方 contact projection 为 accepted，requester 未 tombstone，peer 对 requester 的 direct_message 或 any consent 当前有效；
2. managed_agent_controller：peer 是 requester 控制的 Native Personal Agent，immutable controller binding 匹配 requester，lifecycle 为 active，且 runtime key 已授权。

basis 不成立，或 create=false 且不存在 binding 时，MUST 使用现行反枚举错误 direct_conversation_unavailable；响应状态、body 和时序不得泄露 peer 存在性、contact、consent、Agent、设备或 KeyPackage 库存。它们不是成功 outcome state。

Resolver 成功 outcome 只有四种：

| state | 含义 |
| --- | --- |
| found | stable binding 已存在；始终返回同一 pair_key、realm_id、main_strand_id 与 binding_event_ref |
| creation_required | 首次创建尚未完成；返回 durable operation 与一个 typed next_action |
| suspended | binding 已存在，但当前 admission basis 禁止新写；仍返回同一坐标且不得携带可区分原因 |
| temporarily_unavailable | locator、coordinator、依赖或同坐标恢复暂不可用；有 operation 时必须返回同一 operation_id |

found 与 presence、Agent reply readiness、KeyPackage 库存正交。已有 binding 的查询 MUST NOT 发起 KeyPackage claim，也不得因 Agent offline、participation grant 缺失或 active MLS state 暂不可用而创建第二个 Realm。客户端可以打开会话并单独显示 reply blocker。

### 6.1 稳定 identity 与确定性 coordinator

同一 trust_domain 内，同一 unordered stable participant pair 在整个生命周期中只有一个 pair_key、一个 DM Realm、一个 main Strand 和一个 immutable binding。pair_key 是唯一 logical identity，不新增 conversation_id。

首次创建的 coordinator 是双方同一组 accepted participant locator refs 与 trust-domain service binding 所解析 Principal Server DID 的 unsigned-byte lexicographic 最小值。两端的 evidence 必须完整、可比较且一致；否则返回 temporarily_unavailable。禁止 fallback 到另一 coordinator。binding accepted 后不再重跑 coordinator 选择；后续服务迁移按既有 Realm hosting / delivery 与 state-transfer 规则处理。

coordinator 以 pair_key 建立唯一 durable operation。operation state 只有 reserved、materializing、found：

- reserved 尚未产生 KeyPackage claim、accepted founding Event 或任何外部 durable effect；只有该状态可以带 expires_at 并在到期后 GC。
- coordinator MUST 在发出 KeyPackage claim或接受任一 founding Event前，原子持久化 materializing，并锁定 operation_id、realm_id 和 main_strand_id。
- materializing 与 found 永不因超时、重启、响应丢失、locator 变化或 coordinator 故障重新分配坐标；所有重试只能恢复相同 operation_id 和相同 IDs。
- coordinator 永久不可用时，只能通过可验证的 service / Realm state transfer 恢复同一 operation；恢复机制不可用时保持 temporarily_unavailable，不得创建竞争 Realm。

进入 materializing 后，客户端与服务 MUST 重放 byte-identical 已签名 Event、MLS Commit、Welcome 和 snapshot。不能保证上述 durable ordering 的实现不符合本 profile。

### 6.2 创建编排

coordinator 只预留坐标并维护 operation；participant 设备仍使用真实 KeyPackage 并签署 Realm bootstrap、MLS artifact 与 immutable binding，服务不得代签或伪造 reducer state。

同 Principal Server 可直接进入 direct_conversation_materialization。跨 Principal Server 的顺序固定为 remote_keypackage_claim → direct_conversation_materialization → found。每个 creation_required outcome 只携带一个 next_action：

- remote_keypackage_claim 携带 immutable claim_authorization_draft。该 draft 必须绑定 operation_id、pair_key、预留 Realm/main Strand/initial MLS group、source/destination service、trust domain、nonce 与 requester。participant 对完整 transcript 签名后用同一 operation_id 重试；响应丢失必须查询同一 claim outcome。
- direct_conversation_materialization 携带 operation_state=materializing 的无过期 draft，固定同一 operation_id、pair_key、Realm/main Strand、initial MLS group、MLS Event IDs、真实 claim record、Realm create、peer join、main Strand 与 binding drafts。客户端必须先持久化可重试的 Commit bytes、Welcome 和 post-commit MLS snapshot。
- retry 表示同一 operation 暂时无法前进；不得重新 claim 或重新分配 ID。

Realm create 与 peer member join 构成普通 Realm 的 atomic bootstrap unit。main Strand、MLS genesis / Add Commit / Welcome 只可由 §7.3 founding mask 接受。最后在 participant PCR 提交 ak.direct_conversation.bound。binding 只有在所有引用均 accepted、同 pair/Realm/Strand 且 RFC 9420 transcript 闭合时才可进入 found。binding 先于依赖到达时保持 dependency-pending 并在依赖补齐后重验，不得永久误判为 schema_violation。

跨 Principal Server 使用 participant-authorized peer KeyPackage claim、ak.peer.events.command.submit 与 ak.peer.contacts.command.submit；receiver 保留 participant 原签名并独立验证 outer service signature、locator/service binding、claim ledger、Event proof、Seal basis 和 MLS transcript。外层服务认证不得替代 participant authority。

### 6.3 Immutable binding 与 active MLS generation

ak.direct_conversation.bound 是 pair 到稳定 realm_id 与 main_strand_id 的一次性 principal-scoped fact。字段为 pair_key、participants_unordered、realm_id、main_strand_id、authorization_basis、member_event_refs、main_strand_create_ref、首次 MLS genesis/Commit/Welcome refs 与 created_at。issuer MUST 是 pair participant。

binding 不携带 mls_group_id、binding_state、predecessor、supersedes 或 retirement cause。它只证明创建闭环；当前 MLS group、epoch 与 security frontier 由同 Realm 的 accepted MLS history 单独投影。同一时刻只能有一个 active MLS generation。

binding facts 与 contact facts一样跨双方镜像原签名 envelope。不存在 binding winner、duplicate/non-canonical candidate、historical segment 或 orphan winner 选择；任一已经产生外部 effect 的半成品都属于该 pair 唯一 materializing operation。

### 6.4 Suspend、恢复与删除

leave、remove、ban、block、contact tombstone、consent revoke、participant / Agent terminal 或其它 admission failure MUST 立即把现有 conversation 投影为 suspended 并禁止新 application message、call signal 与 Welcome；它们不销毁 binding，也不创建 successor Realm。

恢复 authorization basis 时，resolver 返回同一 pair_key、Realm 与 main Strand，并在需要时于同 Realm执行标准 rejoin/rekey。rejoin 只恢复新 frontier 之后的发送资格；MUST NOT 自动重发旧 epoch key、history secret、本地已删除内容或 leave/block 前的历史。历史 key-share 仍逐次满足 event-time visibility、history-sharing policy 和显式 authority。

“删除我的聊天”是 principal-private navigation/cache 行为，不改变 binding。双方授权或 retention policy 允许的全局内容/密钥 erasure 可以清空内容和旧 MLS state，但 MUST 保留 pair/Realm/main Strand identity；再次联系时在同一 Realm 建立新的 active MLS generation。

只有 participant principal 自身进入不可逆 terminal 状态且 retention/audit 条件满足时，conversation 才可永久不可用；即使如此也不得为同一 pair 创建 successor。

## 7. DM Realm Well-Known 形态

1:1 DM Realm 是普通 Realm 的受约束 profile，不是新的 Realm 类型。它 MUST：

- 使用 encryption_profile="mls_rfc9420"，且 content_encryption_floor 与 metadata_encryption_floor 均为 e2ee_required；
- 同时声明 ak.schema.realm.v1、ak.profile.direct_conversation_realm.v1、fields.collaboration_role="direct_conversation" 与对应 fail-closed critical extension；
- active member count 等于 2；bootstrap peer join 是 founding unit 的闭合例外，任何第三 participant、invite 或 member add 均拒绝；
- default_join_rule 为 closed，禁止所有 ak.space.* Event、普通 Realm destroy/tombstone、main Strand terminal 和面向第三主体的治理；
- 永久绑定同一 pair_key 与 main Strand；同一 pair 不存在第二个 DM Realm。

Pair key 唯一算法：

1. 把双方 canonical stable subject DID 的 UTF-8 bytes 按 unsigned-byte lexicographic order 排序为 participants；pairwise DID 必须先由 accepted contact 映射回 stable DID。
2. 构造恰含两个键的对象 {"participants":[p0,p1],"trust_domain":realm_trust_domain}。
3. pair_key = "sha256:" + lowercase_hex(SHA-256(JCS(object)))。
4. receiver MUST 重算；handle、display name、contact request、Realm、Strand 和 service DID 均不得进入前像。

### 7.1 Participant authority

DM 日常对等写权限唯一来自 ak.authority.direct_conversation_participant.v1，不来自 membership、created_by、role、技术 root 或普通 grant。

participant Event MUST 选择该 evaluator，并携带恰好一条 critical direct_conversation_binding ref。executed_by Agent 仍以自己的 grant/delegation 作为独立 AND gate；两者互不替代。

每次求值 MUST 在 Event 的 CBA basis 同时确认：

1. accepted immutable binding 恰含两个 participant，且 pair、Realm、main Strand 引用闭合；
2. actor 是 participant，当前 membership 为 join，conversation 不是 suspended；
3. 目标 Strand 是 main Strand或同 Realm、继承当前 active MLS generation 的普通 non-Circle discussion Strand；
4. 当前 active MLS generation、authorization basis 与所有依赖完整、可达、无 fork 且足够新；
5. action 命中 closed allowlist，resource 不越出该 Realm，并满足 own-message、self-leave、same-participant device Welcome 与 Agent-specific gate。

baseline 只包含双方 message create、own revise/redact、reaction、receipt/typing/call signal、call join/screen share、MLS proposal/commit、本人 device Welcome、自身 leave和创建普通 discussion Strand。它不包含 owner/admin、转授、对方 member/message 治理、invite、policy、moderation、record/transcribe、terminal action或第三方 MLS member。

creator 与 peer 使用同一 evaluator。证据 missing、forked、stale 或交叉不匹配时 dependency-pending 或 direct_conversation_participant_authority_denied，禁止回退 service-private allow row。

### 7.2 Root owner profile mask

DM authority root 是 founding / repair 技术 root，不是群主。profile mask 在 owner aggregate 后、最终 allow 前求交：

- founding 只允许同一 materializing operation 精确预留的 peer join、main Strand、MLS genesis / epoch-0 Commit / Welcome 与 binding；
- found 或 suspended 后，普通 owner operational coverage 全部 masked；双方消息都必须走 participant authority；
- 只保留同坐标 repair、不会改变 participant baseline 的 authority reset / transfer，以及 participant 均 terminal 且 retention/audit 满足后的内容 cleanup；
- repair/reset/transfer 不得改变 pair_key、Realm/main Strand，也不得授权第三 participant、owner/admin grant、对方治理或普通 policy 写；
- cleanup 不得删除 immutable binding identity或制造 successor。

违反 mask 返回 direct_conversation_root_mask_violation。root transfer 不改变 participant baseline。

## 8. DM 主 Strand Well-Known 形态

本章的机器回归合同由 `ak.vector.direct_conversation.stable_allocation.v1`、
`ak.vector.direct_conversation.suspend_rejoin.v1`、`ak.vector.direct_conversation.pair_key.v1`、
`ak.vector.direct_conversation.realm_shape.v1` 与
`ak.vector.capability.direct_conversation_participant_authority.v1` 固定；实现不得以旧 segment/
retirement/candidate winner 向量替代。

DM 主 Strand MUST 位于 stable DM Realm，scope_circle_id=null，继承当前 Realm-default active MLS generation，并声明 tracks.discussion.is_primary=true 且 discussion track active。discussion.is_primary 不能单独证明 main Strand；唯一 immutable binding 才是真源。

用户与其 owned Native Personal Agent 的私聊同样使用 participants={controller, agent} 的稳定双成员 DM Realm；它与当前 Collaboration Realm/Strand 无关，Sidecar 不是联系人入口。

stage 可省略；携带时必须是 v1 Strand 合法值。产品不得把它解释为 DM 任务进度。Realm 可以有额外 ordinary discussion Strand，但默认消息写入 binding 指向的 main Strand。
