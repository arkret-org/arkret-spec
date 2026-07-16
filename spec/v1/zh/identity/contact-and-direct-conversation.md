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

本文定义 Arkret v1 中"加联系人 -> 找他聊天"的协议级生命周期。它不是 UI 联系人列表说明，也不是对 consent、Realm 或 Strand 的别名重述，而是把联系人关系、action consent gate、direct conversation binding 与消息载体明确分层。

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
| `ak.self.contact.command.tombstone` | `POST /_arkret/self/contacts/tombstone` | `ContactTombstoneRequestBody` / `ContactTombstone` | 写 holder 侧 tombstone；默认 revoke holder 给 peer 的 contact-managed consent；request body 含可选 `block_peer`(默认 false),为 true 时额外把 peer DID 写入 holder `invite_receive_policy.blocked_subjects`(硬拉黑) |

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

列表 MAY 包含 `direct_conversation` 摘要，但该字段只能来自 direct conversation binding，不得反向决定 contact state。

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
- recipient 的 `invite_receive_policy.blocked_subjects` 命中 issuer 时，MUST fail closed（drop + opaque），与 invite 投递的隐私侧信道防护一致。
- **首次接触附言不绕过 consent gate（normative）**：`ak.contact.requested` 携带的 `message`（1..2000 自由文本，透传到 `contact_requested_payload.message`）在 target **accept 之前**是来自陌生 requester 的未经同意文本，不得直接落入 target 的可见 contact projection 充当骚扰 / 钓鱼 / 未授权信息投递通道。当 requester **不**在 target 的既有 contact 或 consent 白名单内（首次接触）时，recipient MUST 把该 `message` 与 invite 的 quarantine inbox 对齐处理：在 `pending_incoming` 行中 **MUST** 收窄 / stub 化（如仅显示"有附言，accept 后可见"而不得直接渲染 2000 字正文），或把附言暂存于 quarantine 区，待 target 显式 accept / 放行后再呈现。`invite_receive_policy.blocked_subjects` 命中只在已知拉黑时 fail-closed；本约束补齐首次接触（尚无 block 记录）时的默认防护，使加好友附言不绕过 [`consent-model.md` §6.1](./consent-model.md) 的 quarantine gate。已在白名单 / 已 accepted contact 的 requester 的 `message` 不受此收窄约束。

因 v1 principal DID（如 `did:web` / `did:webvh`）不强制内嵌 home Principal Server，requester 发起跨端 `ak.self.contact.command.request` 时 MUST 携带 target 的 `recipient_service_id`（与 invite 寻址同构），issuer 侧 PS 据此投递；同 PS 的 request 不需要该字段，本地直接投影。

## 5. Private Contact Discovery 边界

`ak.find.directory.query.private_contact_discovery` 只回答"哪些本地 connection identifier 在 provider 的可联系集合里"，以及 v1 core 已允许的最小 invite / consent handoff stub。

v1 规范采用窄读：private contact discovery 响应 MAY 在 PSI set-membership 命中结果旁附带最小 invite / consent handoff stub，但该 stub 只能声明 consent state hash、grant / revoke 状态或下一步引导。它 MUST NOT 携带 reachability proof、完整 profile、成员资格、Realm membership、读取权限、关系图谱，或可直接创建 contact relation 的 token。

该 handoff stub 携带 consent state hash 时,**MUST** 满足 [`consent-model.md` §6.2.1](./consent-model.md)（PSI 命中位时序侧信道）与 [`§6.2.2`](./consent-model.md)（Consent state hash 侧信道）的侧信道防护 normative 约束:consent state hash MUST 加 per-requester / per-session salt（或改为 holder-authorized opaque token）,MUST NOT 输出裸的、跨 requester 稳定的 hash（§6.2.2）;PSI 命中位 MUST 经粗粒度时间 bucket 化并按 `(requester, holder)` 维度限速，防止时序侧信道（§6.2.1）。实现 MUST NOT 在本 stub 中输出未加盐的 consent state hash。

本规范不新增、也不依赖 contact request handoff token。若未来需要 discovery 直接返回可发起 `ak.self.contact.command.request` 的 token / credential，必须另行注册 profile 与 response schema。在那之前，用户选择联系某个 PSI 命中后，客户端才向目标 principal 披露自己的 DID / pairwise DID 并调用 `ak.self.contact.command.request`。

## 6. Direct Conversation Resolver

联系人 accepted 后，客户端不应手工拼 Realm / Strand。`ak.self.direct_conversation.command.resolve` 是 pair 到 canonical 1:1 DM 入口的幂等 resolver。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ak.self.direct_conversation.command.resolve` | `POST /_arkret/self/direct-conversations/resolve` | `DirectConversationResolveRequestBody` / `DirectConversationResolveOutcome` | 解析或创建这对 actor 的 canonical 1:1 DM 入口 |

Resolver MUST：

1. 验证 requester 与 peer 的 contact projection 为 `accepted`，且 requester 未 tombstone 该 contact。若没有 accepted contact，对 requester 统一返回 `failed_precondition` / `direct_conversation_unavailable`。本 resolver 是"联系人私聊入口"；只想基于 consent 发起非联系人 DM 的 profile 必须另行注册 operation。
2. 验证目标 holder 对 requester 有 active `consent_scope=direct_message` 或 `any`。若没有，对 requester 同样返回 `failed_precondition` / `direct_conversation_unavailable`。服务端 MAY 在 holder-private 审计中区分 contact/consent 原因，但响应状态、body 与时序 MUST 不可区分。
3. 查询 direct conversation binding。若已有 active canonical binding，返回其 `realm_id` 与 `main_strand_id`。
4. 若 `create=false` 且不存在 binding，返回 `not_found`。
5. 若 `create=true`，走既有 KeyPackage claim、Realm create / member add、MLS group create、Strand create，然后写 direct conversation binding fact。该编排的失败路径 MUST 返回如下终态错误，且 MUST NOT 把半成品 Realm 作为 canonical binding 返回：
   - **对端 principal 不可解析**（peer DID 无法解析到有效 principal / control state）：返回 `failed_precondition` / `peer_unresolvable`，不发起 KeyPackage claim 或 Realm create。
   - **对端无可用 KeyPackage**（KeyPackage claim 全部失败，对端无 active KeyPackage 或全部过期 / 撤销）：返回 `failed_precondition` / `keypackage_unknown`（与 §9 KeyPackage claim 路径的反枚举错误口径一致，不泄露对端设备存在性 / 数量）。
   - **create 编排中途失败**（Realm / membership / MLS group / Strand 任一步已创建但后续步骤或 binding fact 未写成）：返回 `temporarily_unavailable`（可重试）；已创建的 Realm 按下文 orphan / non-canonical 规则处理，MUST NOT 作为默认聊天入口返回。重试 MAY 在 participants / membership / main Strand / contact refs 完全匹配后补写 binding，否则创建新候选并由 deterministic canonical selection 收敛。

Resolver create 是多步编排，不是单个 reducer 原子操作。若 Realm / membership / Strand 已创建但 binding fact 未写成，该 Realm 只能作为 orphan / non-canonical 候选存在；重试 MAY 在验证其 participants、membership、main Strand、contact refs 与请求 pair 完全匹配后补写 binding，否则必须创建新的候选并让 deterministic canonical selection 收敛。没有 binding 的 orphan Realm 不得作为默认聊天入口返回。

Direct conversation binding 是 pair 到 `(realm_id, main_strand_id)` 的 principal-scoped signed fact / projection，不是 server 私有表。`ak.direct_conversation.bound` 的 issuer MUST 是参与 pair 的一方，字段至少包含 `participants_unordered[]`, `realm_id`, `main_strand_id`, `contact_refs[]`, `member_event_refs[]`, `main_strand_create_ref` 与 `created_at`。

Binding facts 与 contact facts 一样需要在双方之间交换 / 镜像并以原签名 envelope 参与 projection；否则 Alice 与 Bob 可能各自只看到自己的 binding fact，无法用同一 tie-break 算出相同 canonical Realm。Binding 只有在引用的 DM Realm、双方 active membership、DM main Strand 与 accepted contact refs 都可验证时才可成为 canonical。

并发创建同一 pair 时，实现 MUST 按 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的统一 canonical 全序选择 canonical binding：先删除不可验证的候选，再删除因果上被同一 pair 的后继 binding 明确取代的候选；剩余候选若互不可达，取承载 binding fact 的 Event `event_digest` 按 unsigned-byte lexicographic order 最大者。不得使用 `event_id`、接收时间、墙钟或本地数据库顺序作 tie-break。loser 标为 duplicate / non-canonical；`ak.self.direct_conversation.command.resolve` 不得随机返回两个不同 Realm。

## 7. DM Realm Well-Known 形态

1:1 DM Realm 是普通 Realm 的受约束形态，不是新的 Realm 类型。

DM Realm MUST：

- 使用 `encryption_profile="mls_rfc9420"`。不得把 `mls_dm` 注册为 Realm `encryption_profile` 新枚举。
- 声明已注册的 direct conversation profile，并在 Realm `fields` 中使用已注册的 direct-conversation discriminator。不得使用 `fields.purpose="direct_message"`，因为 `fields.purpose` 已被 Principal Control Realm 语义占用。
- active member count 等于 2（wire bound，登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)）。不得向 active DM Realm 加第三人；升级多人聊天必须创建新的普通 Realm / Strand，再用 Relation 或 Message 引用旧 DM 内容。
- `default_join_rule` 为 `closed` 或等价 fail-closed policy；第三方 invite / member_add MUST 被拒绝。
- 对同一 unordered participant pair 至多保留一个 active canonical DM Realm。

Pair key canonical encoding 是 direct conversation 的关键 normative 依赖，唯一算法如下：

1. 对双方输入分别完成 DID method 的 canonical string normalization，并验证其代表当前 contact fact 中的稳定 subject DID。若交互使用 pairwise DID，producer MUST 先用已验证、由双方 contact fact 绑定的映射还原到稳定 subject DID；无法还原时 MUST `failed_precondition` / `direct_conversation_unavailable`，不得用 pairwise DID 临时生成另一个 pair key。
2. 把两个稳定 subject DID 的 UTF-8 bytes 按 unsigned-byte lexicographic order 升序排列为 `participants`；两值相同 MUST `schema_violation`。
3. 构造恰含两个键的对象 `{"participants":[p0,p1],"trust_domain":realm_trust_domain}`。`realm_trust_domain` MUST 等于目标 DM Realm create-locked 的 `trust_domain`，不得使用 handle domain、服务 hostname 或请求来源字符串替代。
4. `pair_key = "sha256:" || lowercase_hex(SHA-256(JCS(object)))`。JCS 与 UTF-8 规则见 [`../conformance/encoding.md` §2](../conformance/encoding.md)。

`participants_unordered[]` 在线上仍承载上述两个稳定 subject DID；其集合、排序后结果与 `pair_key` 前像 MUST 完全一致。receiver MUST 重算并逐字比较 `pair_key`，不一致时以 `schema_violation` 拒绝。handle 字符串、显示名、contact request id、Realm id 与 Strand id 均不得进入前像。

字节级 KAT 与反序输入规则由 `ak.vector.direct_conversation.pair_key.v1` 固定。

DM Realm MAY 为 push / server-side rule 暴露最小 `is_direct_message` projection。该 projection 可由 direct conversation profile + active member count 派生，不得要求 server 解密用户内容。

非 canonical duplicate Realm MAY 保留历史可读性，但不得作为默认聊天入口。

### 7.1 成员退出

任一参与方主动离开 / 被移出 DM Realm 后，该 Realm 立即失去 active canonical DM 资格。direct conversation binding MUST 标为 retired / non-canonical，后续 `ak.self.direct_conversation.command.resolve(create=true)` MUST 创建新的 DM Realm、main Strand 与 binding。

Resolver MUST NOT 为了"继续同一个私聊"把退出方重新加入旧 DM Realm。退出是明确的会话边界与密钥 / 历史边界；复用旧 Realm 会混淆退出后的 MLS epoch、history eligibility 与用户意图。

旧 DM Realm MAY 继续作为历史归档存在，其可读性按离开时的 Realm history visibility、retention、redaction 与本地备份策略决定。它不得接收新的默认聊天消息。

## 8. DM 主 Strand Well-Known 形态

消息必须挂在 Strand 的 `discussion` track 上，所以 direct conversation binding 必须同时绑定 `main_strand_id`。

DM 主 Strand MUST：

- 位于 DM Realm 内。
- `scope_circle_id=null`，继承 DM Realm 的 Realm-default MLS group。DM 主 Strand MUST NOT 再套 Circle；双人 Realm 的 Circle 子集切不出更窄隐私边界。
- 声明 `tracks.discussion.is_primary=true`，且 discussion track active。
- `stage` MAY 省略；若携带，MUST 是当前 v1 Strand schema 的合法枚举值。推荐使用 `stage="in_progress"` 作为 wire 兼容值；direct conversation UI MUST NOT 把 DM 主 Strand 的 `stage` 当成待办进度展示，也 SHOULD 禁用普通 `ak.strand.stage.set` 控件。
- 通过 direct conversation binding 标识为该 Realm 的 main Strand。`discussion.is_primary=true` 只是 Strand 内默认入口，不能单独证明"这是 DM 主 Strand"。

同一 DM Realm 至多一个 active canonical main Strand。DM Realm 内 MAY 有其它普通 Strand，用于把某个话题升级成独立议题；默认聊天消息必须写入 binding 指向的 main Strand。
