---
title: Contact & Direct Conversation Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-06-04
see_also:
  - consent-model.md
  - ../discovery/discovery-directory.md
  - ../models/realm-and-space.md
  - ../models/flow-and-message.md
  - ../models/relation.md
  - ../sync/service-http-binding.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本文定义 Cokret v1 中"加联系人 -> 找他聊天"的协议级生命周期。它不是 UI 联系人列表说明，也不是对 consent、Realm 或 Flow 的别名重述，而是把联系人关系、action consent gate、direct conversation binding 与消息载体明确分层。

## 1. 真相源分层

同一对用户之间至少存在五个相邻但互不替代的事实源：

| 层 | 标识 | 作用域 | 真源问题 | 不得替代 |
| --- | --- | --- | --- | --- |
| L1 holder-private 备注 | `ck.contacts.actor.<did>` account-data | holder 本地私有 | "我本地怎么备注、置顶、过滤这个 DID" | 不表示对方接受 |
| L2 协作图关系 | `ck.relation.*` | Realm 内 | "这个 Realm 里的 Flow / Message / Actor / Object 如何相连" | 不表示跨 Realm 社交关系 |
| L3 联系人关系 | `ck.contact.*` fact / operation | principal 级、跨 Realm | "双方请求、接受、拒绝、终止联系人关系到了哪一步" | 不表示 action 授权本身 |
| L4 action gate | `ck.consent.*` | holder Principal Control Realm | "peer 是否可发起 direct_message / invite / call / presence" | 不表示 pending / rejected / tombstoned |
| L5 会话载体 | direct conversation binding + DM Realm + 主 Flow | Realm / Flow | "这对 actor 的 1:1 消息写到哪里" | 不表示双方仍是联系人 |

`ck.contact.*` 作为 operation id 与 event kind 使用单数 `contact`。既有 account-data key 保持复数 `ck.contacts.*`，只表达 holder-private 备注、标签、置顶和本地过滤。实现文档和 catalog description MUST 明确区分二者，不得把 account-data contact note 称为 contact relation truth source。

Consent 的有效状态只有 `active` / `no-consent`；`revoke` 是操作，不是关系状态。联系人关系的 pending / accepted / rejected / tombstoned MUST 来自 contact fact projection，而不是从 consent cell、共享 DM Realm 或服务私有 `contacts` 表反推。

## 2. Contact Fact Log

联系人关系的真源是 principal-scoped contact fact log。holder 自己签发的 contact facts 默认写入 holder 的 Principal Control Realm（PCR）。普通 Collaboration Realm 不承载 contact relation truth。

对端签发的 request / accept / reject / tombstone facts 以原签名 envelope 参与本 holder 的 contact projection。实现 MAY 在本 holder 的 PCR 中保存为 receipt / mirror 以便多设备同步和离线验证，但 receiver MUST NOT 重新签发成自己的本地 fact。

| event kind | issuer | 主要字段 | 语义 |
| --- | --- | --- | --- |
| `ck.contact.requested` | requester | `request_id`, `target`, `requested_scopes[]`, `requester_consent_refs[]` | 发出请求；requester 侧形成 `pending_outgoing`，target 收到后形成 `pending_incoming`；`requested_scopes[]` 非空时 `requester_consent_refs[]` 必填 |
| `ck.contact.accepted` | request target | `request_id`, `requester`, `granted_scopes[]`, `consent_grant_refs[]` | 接受请求；MUST 引用原 request；MUST 写 target 控制的 consent grants |
| `ck.contact.rejected` | request target | `request_id`, `requester` | 拒绝请求；MUST NOT 隐式写 consent grant |
| `ck.contact.tombstoned` | 任一参与方 holder | `peer`, `revoke_scopes[]`, `consent_revoke_refs[]` | holder 终止自己这一侧的联系人关系；默认 revoke holder 给 peer 的 contact-managed consent |

Issuer 约束是硬边界：

- requester 可以声明"我请求联系 target"，也可以预先给 target 写 requester 侧 consent grant。
- target 才能声明"我接受或拒绝 requester"。requester MUST NOT 替 target 写 accepted / rejected，也 MUST NOT 替 target 写 consent。
- 任一 holder 都可以 tombstone 自己与 peer 的关系视图。tombstone 不会修改 peer 的 contact fact log；peer 只能在收到 tombstone fact 后把关系投影降级。

`request_id` SHOULD 使用 `ck.contact.requested` 的 `event_id`。实现 MAY 用 `(holder, peer, outstanding_request)` 做幂等去重，但不得把重复 request 折叠成 consent grant。

## 3. Contact 与 Consent

Contact 负责关系状态：`pending_outgoing` / `pending_incoming` / `accepted` / `rejected` / `tombstoned`。Consent 负责 action gate：`direct_message` / `invite` / `voice_call` / `video_call` / `presence` 是否允许。

`ck.self.contact.request` 默认请求 `requested_scopes=["direct_message"]`。若 request 请求某个 scope，requester MUST 在自己的 PCR 同步写一条给 target 的 `ck.consent.grant`，并在 `requester_consent_refs[]` 中引用它。若该 grant 写入失败，request MUST fail closed，或移除该 scope 后重新签名。该 requester-side grant 在 contact accepted 前只表示 requester 允许 target 发起对应动作；`ck.self.direct_conversation.resolve` 仍 MUST 检查 accepted contact，不得只凭 consent grant 创建联系人 DM。

该 requester-side grant 的生命周期 MUST 与 request 绑定，不得在 request 终结后长期残留为开放的反向 consent gate：当 requester 看到该 request 对应的 `ck.contact.rejected`，或 request 在 `contact_request_pending_ttl`（部署可配，默认 SHOULD ≤ 14 天）内仍处 `pending_outgoing` 而超时（无论先到者），requester 的 PCR MUST 自动对 `requester_consent_refs[]` 引用的 active grant dots 发 `ck.consent.revoke`。这些 dots 同时是 contact-managed consent，故也纳入 §3 / `ck.self.contact.tombstone` 的级联枚举范围；若 requester 无法枚举完整 dots，MUST 按 partial / fail-closed 处理并标记，不得报告完整撤销。该自动 revoke 不依赖 target 配合，目的是关闭"已死 request 留下长期开放的 requester→target 反向 consent gate"的暴露面。

`ck.self.contact.respond(action="accept")` MUST：

1. 验证 request 存在、target 是当前 holder、request 未被 target 已拒绝 / 接受 / 终止。
2. 写 `ck.contact.accepted` fact。
3. 对每个 `granted_scopes[]` 写 target 控制的 `ck.consent.grant`，并把 event refs 写入 `consent_grant_refs[]`。

`granted_scopes[]` MUST 是 `requested_scopes[]` 的子集，除非 response UI 明确执行"扩展授权"并把扩展 scope 写入 accepted fact 的审计字段。默认 accept 不得静默扩大 requester 请求范围。

`ck.self.contact.respond(action="reject")` MUST 只写 `ck.contact.rejected`，不得隐式写 consent。

Contact-managed consent dots 指通过该 contact request / accepted fact 的 `requester_consent_refs[]` 或 `consent_grant_refs[]` 引入、或后续明确绑定到该 contact relation 的 active grant dots，即 [`consent-model.md`](./consent-model.md) §5 的 `active_dots(cell)` 中对应 intent 的 add dots。

`ck.self.contact.tombstone` MUST 写 `ck.contact.tombstoned`。`revoke_scopes[]` 缺省为 holder 给 peer 的全部 contact-managed active scopes；operation MUST 枚举并 revoke 这些 active grant dots，并把 revoke refs 写入 tombstone fact。若实现无法枚举完整 dots，必须返回 partial / fail-closed 结果，不得报告完整 tombstone。实现不得默认撤销 holder 给同一 peer 的非 contact-managed consent（例如独立组织 invite 授权），除非 UI / admin 明确选择 full peer revoke 并在 tombstone fact 中审计。

Consent revoke 与 contact tombstone 仍是两条显式事实：单独 revoke consent 只会减少 `effective_scopes`，不得自动删除 accepted contact；tombstone 也不得伪造不存在的 revoke event。

## 4. Contact Operation Surface

全部 contact operation 要求 `user_session`，落在 `/_cokret/self/...` trust surface。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ck.self.contact.request` | `POST /_cokret/self/contacts/request` | `ContactRequestRequestBody` / `ContactRequestOutcome` | 写 requester 侧 request fact，并投递签名请求给 target；request body MAY 含可选 `message`(1..2000,NFC),透传到 `ck.contact.requested` 的 `message` 字段作为加好友附言；target 在对端 PS 时 MUST 携带可选 `recipient_service_did`(见 §4.1)以驱动跨端投递 |
| `ck.self.contact.respond` | `POST /_cokret/self/contacts/respond` | `ContactRespondRequestBody` / `ContactRespondOutcome` | 由 target 接受 / 拒绝 request；accept 同步写 target consent grants |
| `ck.self.contact.list` | `GET /_cokret/self/contacts` | `ContactList` | 从 contact facts 投影，并附带 consent-derived scopes |
| `ck.self.contact.tombstone` | `POST /_cokret/self/contacts/tombstone` | `ContactTombstoneRequestBody` / `ContactTombstone` | 写 holder 侧 tombstone；默认 revoke holder 给 peer 的 contact-managed consent；request body 含可选 `block_peer`(默认 false),为 true 时额外把 peer DID 写入 holder `invite_receive_policy.blocked_subjects`(硬拉黑) |

`ContactListRow` MUST 至少区分：

- `pending_outgoing`：本 holder 发出 request，尚未看到 target accept / reject。
- `pending_incoming`：本 holder 收到 request，尚未 respond。
- `accepted`：已看到合法 `ck.contact.accepted`，且本 holder 未 tombstone。
- `rejected`：已看到合法 `ck.contact.rejected`。
- `tombstoned`：本 holder 已 tombstone，或已看到 peer tombstone 且投影选择暴露该状态。

`ContactListRow` 的 scope 投影 MUST 是方向化的，至少区分 `granted_by_me[]`（我允许 peer 发起的 scopes）、`granted_to_me[]`（peer 允许我发起的 scopes）与 `bidirectional_scopes[]`。若响应使用简写字段 `effective_scopes[]`，它 MUST 等价于 `bidirectional_scopes[]`，不得把单向 consent 显示成双方都可用。

看到 peer 的合法 `ck.contact.tombstoned` 后，本 holder 的 projection SHOULD 立即把该 row 从 `accepted` 降级为 `tombstoned` 或等价 non-active state，避免列表长期显示 accepted 但 direct-message gate 已关闭。peer tombstone 尚未同步到本 holder 前，列表与 gate 可能短暂不一致；resolver 仍以最新可验证 contact projection + consent gate fail closed。

列表 MAY 包含 `direct_conversation` 摘要，但该字段只能来自 direct conversation binding，不得反向决定 contact state。

### 4.1 跨 Principal Server 投递

§2 要求「对端签发的 request / accept / reject / tombstone facts 以原签名 envelope 参与本 holder 的 contact projection」。当 issuer 与 target holder 不在同一 Principal Server 时，该交换必须经由专门的 peer 投递面完成；本地 `ck.self.contact.*` operation 本身只写 issuer 侧 fact，不跨端。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ck.peer.contacts.submit` | `POST /_cokret/peer/contacts` | `PeerContactDeliveryRequest` / `PeerContactDeliveryOutcome` | issuer 侧 PS 把签名的 `ck.contact.requested` / `accepted` / `rejected` / `tombstoned` envelope 投递到 target holder 的 PS |

该 peer 端点与 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) §5 的 `ck.peer.invites.submit` 同级、风格一致：要求 service-to-service 认证、`Destination-Service-DID` 等于 `contact_address.recipient_service_did`、RFC 9530 `Content-Digest` 与 RFC 9421 message signature。约束如下：

- `contact_event` MUST 是 issuer 原签名的 `ck.contact.*` EventEnvelope；recipient MUST 以原签名 envelope 参与 projection，MUST NOT 重新签发成自己的本地 fact（§2 硬边界）。
- `fact_kind` MUST 等于 `contact_event.kind`。
- `contact_address.subject_id` 是该 fact 在 recipient 侧的归属 holder：`ck.contact.requested` 投递到 request target；`ck.contact.accepted` / `rejected` 反向投递回原 requester；`ck.contact.tombstoned` 投递到被 tombstone 的 peer。
- recipient 把 fact 投影进 `subject_id` 的 contact projection（target 侧形成 `pending_incoming`；requester 侧 accept 形成 `accepted` 并带 `consent_grant_refs[]` / `invite_consent_grant_ref`；reject 形成 `rejected`；tombstone 把对应 row 降级）。
- recipient 的 `invite_receive_policy.blocked_subjects` 命中 issuer 时，MUST fail-closed（drop + opaque），与 invite 投递的隐私侧信道防护一致。

因 v1 principal DID（如 `did:web` / `did:webvh`）不强制内嵌 home Principal Server，requester 发起跨端 `ck.self.contact.request` 时 MUST 携带 target 的 `recipient_service_did`（与 invite 寻址同构），issuer 侧 PS 据此投递；同 PS 的 request 不需要该字段，本地直接投影。

## 5. Private Contact Discovery 边界

`ck.find.directory.private_contact_discovery` 只回答"哪些本地 connection identifier 在 provider 的可联系集合里"，以及 v1 core 已允许的最小 invite / consent handoff stub。

v1 规范采用窄读：private contact discovery 响应 MAY 在 PSI set-membership 命中结果旁附带最小 invite / consent handoff stub，但该 stub 只能声明 consent state hash、grant / revoke 状态或下一步引导。它 MUST NOT 携带 reachability proof、完整 profile、成员资格、Realm membership、读取权限、关系图谱，或可直接创建 contact relation 的 token。

该 handoff stub 携带 consent state hash 时,**MUST** 满足 [`consent-model.md` §6.2.1](./consent-model.md)（PSI 命中位时序侧信道）与 [`§6.2.2`](./consent-model.md)（Consent state hash 侧信道）的侧信道防护 normative 约束:consent state hash MUST 加 per-requester / per-session salt（或改为 holder-authorized opaque token）,MUST NOT 输出裸的、跨 requester 稳定的 hash（§6.2.2）;PSI 命中位 MUST 经粗粒度时间 bucket 化并按 `(requester, holder)` 维度限速，防止时序侧信道（§6.2.1）。实现 MUST NOT 在本 stub 中输出未加盐的 consent state hash。

本规范不新增、也不依赖 contact request handoff token。若未来需要 discovery 直接返回可发起 `ck.self.contact.request` 的 token / credential，必须另行注册 profile 与 response schema。在那之前，用户选择联系某个 PSI 命中后，客户端才向目标 principal 披露自己的 DID / pairwise DID 并调用 `ck.self.contact.request`。

## 6. Direct Conversation Resolver

联系人 accepted 后，客户端不应手工拼 Realm / Flow。`ck.self.direct_conversation.resolve` 是 pair 到 canonical 1:1 DM 入口的幂等 resolver。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ck.self.direct_conversation.resolve` | `POST /_cokret/self/direct-conversations/resolve` | `DirectConversationResolveRequestBody` / `DirectConversationResolveOutcome` | 解析或创建这对 actor 的 canonical 1:1 DM 入口 |

Resolver MUST：

1. 验证 requester 与 peer 的 contact projection 为 `accepted`，且 requester 未 tombstone 该 contact。若没有 accepted contact，返回 `failed_precondition` / `contact_not_accepted`。本 resolver 是"联系人私聊入口"；只想基于 consent 发起非联系人 DM 的 profile 必须另行注册 operation。
2. 验证目标 holder 对 requester 有 active `consent_scope=direct_message` 或 `any`。若没有，返回 `failed_precondition` / `contact_consent_missing`。
3. 查询 direct conversation binding。若已有 active canonical binding，返回其 `realm_id` 与 `main_flow_id`。
4. 若 `create=false` 且不存在 binding，返回 `not_found`。
5. 若 `create=true`，走既有 KeyPackage claim、Realm create / member add、MLS group create、Flow create，然后写 direct conversation binding fact。

Resolver create 是多步编排，不是单个 reducer 原子操作。若 Realm / membership / Flow 已创建但 binding fact 未写成，该 Realm 只能作为 orphan / non-canonical 候选存在；重试 MAY 在验证其 participants、membership、main Flow、contact refs 与请求 pair 完全匹配后补写 binding，否则必须创建新的候选并让 deterministic canonical selection 收敛。没有 binding 的 orphan Realm 不得作为默认聊天入口返回。

Direct conversation binding 是 pair 到 `(realm_id, main_flow_id)` 的 principal-scoped signed fact / projection，不是 server 私有表。`ck.direct_conversation.bound` 的 issuer MUST 是参与 pair 的一方，字段至少包含 `participants_unordered[]`, `realm_id`, `main_flow_id`, `contact_refs[]`, `member_event_refs[]`, `main_flow_create_ref` 与 `created_at`。

Binding facts 与 contact facts 一样需要在双方之间交换 / 镜像并以原签名 envelope 参与 projection；否则 Alice 与 Bob 可能各自只看到自己的 binding fact，无法用同一 tie-break 算出相同 canonical Realm。Binding 只有在引用的 DM Realm、双方 active membership、DM main Flow 与 accepted contact refs 都可验证时才可成为 canonical。

并发创建同一 pair 时，实现 MUST 以 deterministic tie-break 选择 canonical binding（例如 first accepted binding by causal order / event id），并把 loser 标为 duplicate / non-canonical；`ck.self.direct_conversation.resolve` 不得随机返回两个不同 Realm。

## 7. DM Realm Well-Known 形态

1:1 DM Realm 是普通 Realm 的受约束形态，不是新的 Realm 类型。

DM Realm MUST：

- 使用 `encryption_profile="mls_rfc9420"`。不得把 `mls_dm` 注册为 Realm `encryption_profile` 新枚举。
- 声明已注册的 direct conversation profile，并在 Realm `fields` 中使用已注册的 direct-conversation discriminator。不得使用 `fields.purpose="direct_message"`，因为 `fields.purpose` 已被 Principal Control Realm 语义占用。
- active member count 等于 2。不得向 active DM Realm 加第三人；升级多人聊天必须创建新的普通 Realm / Flow，再用 Relation 或 Message 引用旧 DM 内容。
- `default_join_rule` 为 `closed` 或等价 fail-closed policy；第三方 invite / member_add MUST 被拒绝。
- 对同一 unordered participant pair 至多保留一个 active canonical DM Realm。

Pair key canonical encoding 是 direct conversation 的关键 normative 依赖。编码 MUST 基于稳定 subject / pairwise DID 与 trust domain，不得把 handle 字符串作为权威输入。pairwise DID 场景下，编码必须能把 pairwise DID 映射回可验证的稳定 subject，或显式声明不能跨 pairwise identity 合并；否则同一用户会被拆成多个 canonical pair。

DM Realm MAY 为 push / server-side rule 暴露最小 `is_direct_message` projection。该 projection 可由 direct conversation profile + active member count 派生，不得要求 server 解密用户内容。

非 canonical duplicate Realm MAY 保留历史可读性，但不得作为默认聊天入口。

### 7.1 成员退出

任一参与方主动离开 / 被移出 DM Realm 后，该 Realm 立即失去 active canonical DM 资格。direct conversation binding MUST 标为 retired / non-canonical，后续 `ck.self.direct_conversation.resolve(create=true)` MUST 创建新的 DM Realm、main Flow 与 binding。

Resolver MUST NOT 为了"继续同一个私聊"把退出方重新加入旧 DM Realm。退出是明确的会话边界与密钥 / 历史边界；复用旧 Realm 会混淆退出后的 MLS epoch、history eligibility 与用户意图。

旧 DM Realm MAY 继续作为历史归档存在，其可读性按离开时的 Realm history visibility、retention、redaction 与本地备份策略决定。它不得接收新的默认聊天消息。

## 8. DM 主 Flow Well-Known 形态

消息必须挂在 Flow 的 `discussion` track 上，所以 direct conversation binding 必须同时绑定 `main_flow_id`。

DM 主 Flow MUST：

- 位于 DM Realm 内。
- `scope_circle_id=null`，继承 DM Realm 的 Realm-default MLS group。DM 主 Flow MUST NOT 再套 Circle；双人 Realm 的 Circle 子集切不出更窄隐私边界。
- 声明 `tracks.discussion.is_primary=true`，且 discussion track active。
- `stage` MAY 省略；若携带，MUST 是当前 v1 Flow schema 的合法枚举值。推荐使用 `stage="in_progress"` 作为 wire 兼容值；direct conversation UI MUST NOT 把 DM 主 Flow 的 `stage` 当成待办进度展示，也 SHOULD 禁用普通 `ck.flow.stage.set` 控件。
- 通过 direct conversation binding 标识为该 Realm 的 main Flow。`discussion.is_primary=true` 只是 Flow 内默认入口，不能单独证明"这是 DM 主 Flow"。

同一 DM Realm 至多一个 active canonical main Flow。DM Realm 内 MAY 有其它普通 Flow，用于把某个话题升级成独立议题；默认聊天消息必须写入 binding 指向的 main Flow。
