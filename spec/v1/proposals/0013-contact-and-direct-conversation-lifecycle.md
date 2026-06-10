---
ckp: CKP-0013
title: Contact & Direct Conversation Lifecycle — 把"加联系人 → 找他聊天"端到端定义在 contact fact / consent gate / direct conversation binding / Flow 之上
normative: false
stability: v1
updated: 2026-06-04
status: accepted
created: 2026-06-04
authors:
  - chris@acroidea.com
depends_on: []
merged_to:
  - spec/v1/zh/identity/contact-and-direct-conversation.md
  - spec/v1/zh/identity/consent-model.md
  - spec/v1/zh/discovery/discovery-directory.md
  - spec/v1/zh/models/realm-and-space.md
  - spec/v1/zh/models/flow-and-message.md
  - spec/v1/zh/sync/service-http-binding.md
  - spec/v1/artifacts/registry/contract-catalog.json
  - spec/v1/artifacts/schemas/contact-operations.schema.json
---

> **Status: accepted, merged into v1 normative spec on 2026-06-04.**
>
> Normative entry point: [`spec/v1/zh/identity/contact-and-direct-conversation.md`](../zh/identity/contact-and-direct-conversation.md)。Operation / Event.kind 注册见 [`contract-catalog.json`](../artifacts/registry/contract-catalog.json)，HTTP/OpenAPI、operation schema 与 error mapping 已同步。本文件保留为历史设计 rationale；联系人和 direct conversation 的后续变更 MUST 落到 normative 文件与 artifacts，不在此处。
>
> 从 **[CKP-0012](./0012-account-and-contact-self-operations.md)** 分拆而来:0012 处理无歧义的 account self-service;联系人因横跨 consent / discovery / realm / flow 多个 normative spec,单列于此。

## 1. Summary

本提案定义"**加联系人 → 找他聊天**"的协议级生命周期,并把相关状态拆成四个互不替代的事实源:

1. **Contact fact log** 是"双方是不是联系人 / 请求是否 pending / 是否被拒绝或终止"的真源。它是 principal-scoped、跨 Realm 的 signed fact,不归属普通 Collaboration Realm,也不是 `ck.relation.*`。
2. **Consent cell** 是"某个 peer 是否被 holder 允许发起 invite / direct_message / call / presence"的 gate。它不保存 pending/rejected/tombstoned,因此不能作为联系人关系真源。
3. **Direct conversation binding + DM Realm** 是"这对联系人当前聊天入口在哪里"的真源。它不决定双方是不是联系人。
4. **DM 主 Flow** 是消息时间线载体。Cokret 没有独立"消息表";聊天仍然是 Flow 的 `discussion` track 上的 `ck.message.create`。

关键收敛:

- `ck.self.contact.request` **不能**编译成目标 holder 的 `ck.consent.grant`:requester 无权替 target 写 consent。request 只能写 requester 自己的 contact request fact,并把签名请求投递给 target。
- `ck.self.contact.respond(action="accept")` 由 target 执行。accept 写 target 的 contact accepted fact,并显式写 target 控制的 consent grant。这样 contact relation 与 consent gate 都有合法 issuer。
- `ck.self.contact.list` 从 contact fact log 投影关系状态,并另外附带由 consent cell 派生的 `effective_scopes`。列表不得把"有 DM Realm"或"有 consent grant"误判成 accepted contact。
- Direct conversation 创建使用 `encryption_profile="mls_rfc9420"` 的普通 Realm 加 MLS,不得把 `mls_dm` 当作 Realm `encryption_profile` 的新枚举值。`mls_dm` 只能作为 profile/用途标签在后续 normative binding 中定义。
- 本提案不修改 Flow `stage` 的 v1 必填不变量。DM 主 Flow 在当前 v1 下仍必须携带 `stage`。UI 可隐藏该 stage,但 wire/reducer 不开 profile-gated 例外;若要让 conversation Flow 省略 stage,应另起 Flow schema 提案。

## 2. Motivation

### 2.1 现状是碎片,不是空白

"加联系人之后找他聊天"今天能跑,但它分散在多份 normative spec 与实现私有 API 中:

1. Bob 发现 Alice 可达 → `ck.find.directory.private_contact_discovery`。
2. Bob 想联系 Alice → 需要给 Alice 发送一个可审计的 contact request。
3. Alice 接受 → Alice 写 contact accepted fact,并写 `consent_scope=direct_message` grant 给 Bob。
4. Bob 发起私聊 → resolver 查找或创建这对 actor 的 direct conversation binding / DM Realm / 主 Flow。
5. 聊天 → `ck.message.create` 写入 DM 主 Flow 的 `discussion` track。

问题在于第 2-4 步以前没有 canonical 编排。"Bob 和 Alice 是不是联系人"现在可能被实现从 consent cell、共享 DM Realm 或 soland 私有 `contacts` 表推断出来。三个来源互相覆盖会导致通用客户端无法可靠列出联系人,也无法解释 pending / rejected / removed 这类关系状态。

### 2.2 不能把 contact 压进既有相近概念

协议已有 `ck.contacts.*` account-data 与 `ck.relation.*`。它们都不能表达本提案的 L3 联系人关系:

- `ck.contacts.actor.<did>` 是 holder-private 备注/tag/pin,单边且不通知对方。
- `ck.relation.*` 是 Realm 内协作图边,`realm_id` 必填,无 pending/accepted 双边握手。
- `ck.consent.*` 是 holder-controlled action gate,只有 active / no-consent 两个有效态(revoke 是操作),无关系请求状态机。

## 3. Specification

### 3.1 分层模型与边界

| 层 | 标识 | 作用域 | 真源问题 | 不得替代 |
| --- | --- | --- | --- | --- |
| L1 holder-private 备注 | `ck.contacts.actor.<did>` account-data | holder 本地私有 | "我本地怎么备注/置顶/过滤这个 DID" | 不表示对方接受 |
| L2 协作图关系 | `ck.relation.*` | Realm 内 | "这个 Realm 里的 Flow/Message/Actor/Object 如何相连" | 不表示跨 Realm 社交关系 |
| **L3 联系人关系** | `ck.contact.*` fact / operation | principal 级、跨 Realm | "双方请求、接受、拒绝、终止联系人关系到了哪一步" | 不表示 action 授权本身 |
| L4 action gate | `ck.consent.*` | holder principal control Realm | "peer 是否可发起 direct_message/invite/call/presence" | 不表示 pending/rejected/tombstoned |
| L5 会话载体 | direct conversation binding + DM Realm + 主 Flow | Realm / Flow | "这对 actor 的 1:1 消息写到哪里" | 不表示双方仍是联系人 |

`ck.contact.*` 作为 operation id 使用单数 `contact`,而 account-data key 保持既有复数 `ck.contacts.*`。catalog `description` MUST 明确写出二者差异;实现文档不得把 account-data contact note 称为 contact relation truth source。

### 3.2 Contact fact log:关系真源

联系人关系的真源是 principal-scoped contact fact log。holder 自己签发的 contact facts 默认写入 holder 的 principal control Realm;普通 Collaboration Realm 不承载 contact relation truth。对端签发的 facts(request / accept / reject / tombstone)以原签名 envelope 参与本 holder 的 contact projection,MAY 在本 holder 的 principal control Realm 中保存为 receipt/mirror,但 receiver MUST NOT 重新签发成自己的本地 fact。规范合入时需要注册 closed fact/event payload,并把这些 fact kind 加入 `ck.profile.principal_control_realm.v1` allowlist;否则现行 PCR 会按 `principal_control_event_kind_forbidden` 拒绝。

| fact kind | issuer | 主要字段 | 语义 |
| --- | --- | --- | --- |
| `ck.contact.requested` | requester | `request_id`, `target`, `requested_scopes[]`, `requester_consent_refs[]` | 发出请求;在 requester 侧形成 `pending_outgoing`,投递到 target 后形成 `pending_incoming`;`requested_scopes[]` 非空时 `requester_consent_refs[]` 必填 |
| `ck.contact.accepted` | request target | `request_id`, `requester`, `granted_scopes[]`, `consent_grant_refs[]` | 接受请求;必须引用原 request;写 target 控制的 consent grant |
| `ck.contact.rejected` | request target | `request_id`, `requester` | 拒绝请求;不写 consent grant |
| `ck.contact.tombstoned` | 任一参与方 holder | `peer`, `revoke_scopes[]`, `consent_revoke_refs[]?` | holder 终止自己这一侧的联系人关系;通常同时撤销 holder 给 peer 的 consent |

Issuer 约束是硬边界:

- requester 可以声明"我请求联系 target",也可以预先给 target 写 requester 侧 consent grant。
- target 才能声明"我接受/拒绝 requester"。requester 不能替 target 写 accepted/rejected,更不能替 target 写 consent。
- 任一 holder 都可以 tombstone 自己与 peer 的关系视图。tombstone 不会修改 peer 的 contact fact log;peer 只能在收到 tombstone fact 后把关系投影降级。

`request_id` SHOULD 使用 `ck.contact.requested` 的 event id。实现 MAY 用 `(holder, peer, outstanding_request)` 做幂等去重,但不得把重复 request 折叠成 consent grant。

### 3.3 Contact 与 consent 的关系

Contact 与 consent 是两层不同事实:

- Contact 负责关系状态:pending / accepted / rejected / tombstoned。
- Consent 负责 action gate:direct_message / invite / voice_call / video_call / presence 是否允许。

`ck.self.contact.request` 默认请求 `requested_scopes=["direct_message"]`。若 request 请求某个 scope,requester MUST 在自己的 principal control Realm 同步写一条给 target 的 consent grant,并在 `requester_consent_refs[]` 中引用它;若该 grant 写入失败,request MUST fail closed 或移除该 scope 后重新签名。这样 target 接受后,双方都具备发起同类动作的对称 consent,`effective_scopes` 不会出现"关系 accepted 但 requester 侧 gate 未开"的半状态。该 requester-side grant 在 contact accepted 前只表示 requester 允许 target 发起对应动作;`ck.self.direct_conversation.resolve` 仍 MUST 检查 accepted contact,不得只凭 consent grant 创建联系人 DM。

`ck.self.contact.respond(action="accept")` MUST:

1. 验证 request 存在、target 是当前 holder、request 未被 target 已拒绝/接受/终止。
2. 写 `ck.contact.accepted` fact。
3. 对每个 `granted_scopes[]` 写 target 控制的 `ck.consent.grant`,并把 event refs 写入 `consent_grant_refs[]`。

`granted_scopes[]` MUST 是 `requested_scopes[]` 的子集,除非 response UI 明确执行"扩展授权"并把扩展 scope 写入 accepted fact 的审计字段。默认 accept 不得静默扩大 requester 请求的范围。

`ck.self.contact.respond(action="reject")` MUST 只写 `ck.contact.rejected`,不得隐式写 consent。

Contact-managed consent dots 指通过该 contact request / accepted fact 的 `requester_consent_refs[]` 或 `consent_grant_refs[]` 引入、或后续明确绑定到该 contact relation 的 active grant dots(即 [`consent-model.md`](../zh/identity/consent-model.md) §5 的 `active_dots(cell)` 中对应 intent 的 add dots)。`ck.self.contact.tombstone` MUST 写 `ck.contact.tombstoned`。`revoke_scopes` 缺省为 holder 给 peer 的全部 contact-managed active scopes;operation MUST 枚举并 revoke 这些 active grant dots,并把 revoke refs 写入 tombstone fact。若实现无法枚举完整 dots,必须返回 partial/fail-closed 结果,不得报告完整 tombstone。实现不得默认撤销 holder 给同一 peer 的非 contact-managed consent(例如独立组织 invite 授权),除非 UI/admin 明确选择 full peer revoke 并在 tombstone fact 中审计。consent revoke 与 contact tombstone 仍是两条显式事实:单独 revoke consent 只会减少 `effective_scopes`,不得自动删除 accepted contact;tombstone 也不得伪造不存在的 revoke event。

### 3.4 Contact operation surface

全部 operation 要求 `user_session`,落 `/_cokret/self/...`。

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ck.self.contact.request` | `POST /_cokret/self/contacts/request` | `{ target: did, requested_scopes?: consent_scope[], idempotency_key?: string }` | 写 requester 侧 request fact,并投递签名请求给 target |
| `ck.self.contact.respond` | `POST /_cokret/self/contacts/respond` | `{ request_id, requester: did, action: "accept"\|"reject", granted_scopes?: consent_scope[] }` | 由 target 接受/拒绝 request;accept 同步写 target consent grants |
| `ck.self.contact.list` | `GET /_cokret/self/contacts` | `ContactList` | 从 contact facts 投影,并附带 consent-derived `effective_scopes` |
| `ck.self.contact.tombstone` | `POST /_cokret/self/contacts/tombstone` | `{ contact: did, revoke_scopes?: consent_scope[] }` | 写 holder 侧 tombstone;默认 revoke holder 给 peer 的全部 contact-managed consent |

`ContactListRow` MUST 至少区分:

- `pending_outgoing`:本 holder 发出 request,尚未看到 target accept/reject。
- `pending_incoming`:本 holder 收到 request,尚未 respond。
- `accepted`:已看到合法 `ck.contact.accepted`,且本 holder 未 tombstone。
- `rejected`:已看到合法 `ck.contact.rejected`。
- `tombstoned`:本 holder 已 tombstone,或已看到 peer tombstone 且投影选择暴露该状态。

`ContactListRow` 的 scope 投影 MUST 是方向化的,至少区分 `granted_by_me[]`(我允许 peer 发起的 scopes)、`granted_to_me[]`(peer 允许我发起的 scopes)与 `bidirectional_scopes[]`。若响应使用简写字段 `effective_scopes[]`,它 MUST 等价于 `bidirectional_scopes[]`,不得把单向 consent 显示成双方都可用。

看到 peer 的合法 `ck.contact.tombstoned` 后,本 holder 的 projection SHOULD 立即把该 row 从 `accepted` 降级为 `tombstoned` 或等价的 non-active state,避免列表长期显示 accepted 但 direct-message gate 已关闭。peer tombstone 尚未同步到本 holder 前,列表与 gate 可能短暂不一致;resolver 仍以最新可验证 contact projection + consent gate fail closed。

列表 MAY 包含 `direct_conversation` 摘要,但该字段只能来自 direct conversation binding,不得反向决定 contact state。

### 3.5 Private contact discovery 只负责发现入口

`ck.find.directory.private_contact_discovery` 只回答"哪些本地 connection identifier 在 provider 的可联系集合里",以及现行 v1 core 已允许的最小 invite/consent handoff stub。这里需要收敛一处既有 normative 文本裂缝:[`discovery-directory.md`](../zh/discovery/discovery-directory.md) §6.2 把 `ck.private_contact_discovery.v1` 写成严格 PSI 位图;但 [`service-surface.md`](../zh/sync/service-surface.md) §8.6 写明响应包含 PSI set-membership 命中位图与最小 invite/consent handoff stub,[`consent-model.md`](../zh/identity/consent-model.md) §6.2 也允许返回 consent state hash 或 invite handoff stub。

CKP-0013 采用窄读:既有 invite/consent handoff stub MAY 继续存在,但它只能声明 grant/revoke 状态与下一步引导,不得携带 reachability proof、完整 profile、成员资格、Realm membership、读取权限或可直接创建 contact relation 的 token。本提案不新增、也不依赖 **contact request handoff token**。若未来需要 discovery 直接返回可发起 `ck.self.contact.request` 的 token/credential,必须另行注册 profile 与 response schema。在那之前,用户选择联系某个 PSI 命中后,客户端才向目标 principal 披露自己的 DID/pairwise DID 并调用 `ck.self.contact.request`。

### 3.6 Direct conversation resolver

联系人 accepted 后,"找他聊天"不应由客户端手拼 Realm/Flow。协议需要一个 idempotent resolver:

| operation | HTTP | Body / Response | 说明 |
| --- | --- | --- | --- |
| `ck.self.direct_conversation.resolve` | `POST /_cokret/self/direct-conversations/resolve` | `{ peer: did, create?: boolean }` → `{ realm_id?, main_flow_id?, state, created?: boolean }` | 解析或创建这对 actor 的 canonical 1:1 DM 入口 |

Resolver MUST:

1. 验证 requester 与 peer 的 contact projection 为 `accepted`,且 requester 未 tombstone 该 contact。若没有 accepted contact,返回 `failed_precondition` / `contact_not_accepted`。本 resolver 是"联系人私聊入口";只想基于 consent 发起非联系人 DM 的 profile 必须另行注册 operation,不得复用此 resolver。
2. 验证目标 holder 对 requester 有 active `consent_scope=direct_message` 或 `any`。若没有,返回 `failed_precondition` / `contact_consent_missing`。
3. 查询 direct conversation binding。若已有 active canonical binding,返回其 `realm_id` + `main_flow_id`。
4. 若 `create=false` 且不存在 binding,返回 `not_found`。
5. 若 `create=true`,走既有 KeyPackage claim、Realm create/member add、MLS group create、Flow create,然后写 direct conversation binding fact。

Resolver create 是多步编排,不是单个 reducer 原子操作。若 Realm / membership / Flow 已创建但 binding fact 未写成,该 Realm 只能作为 orphan / non-canonical 候选存在;重试 MAY 在验证其 participants、membership、main Flow、contact refs 与请求 pair 完全匹配后补写 binding,否则必须创建新的候选并让 deterministic canonical selection 收敛。没有 binding 的 orphan Realm 不得作为默认聊天入口返回。

Direct conversation binding 是 pair → `(realm_id, main_flow_id)` 的 principal-scoped signed fact/projection,不是 server 私有表。规范合入时应注册 `ck.direct_conversation.bound` fact,issuer MUST 是参与 pair 的一方,字段至少包含 `participants_unordered`, `realm_id`, `main_flow_id`, `contact_refs[]`, `member_event_refs[]`, `main_flow_create_ref` 与 `created_at`。Binding facts 与 contact facts 一样需要在双方之间交换/镜像并以原签名 envelope 参与 projection;否则 Alice 与 Bob 可能各自只看到自己的 binding fact,无法用同一 tie-break 算出相同 canonical Realm。Binding 只有在引用的 DM Realm、双方 active membership、DM main Flow 与 accepted contact refs 都可验证时才可成为 canonical。并发创建同一 pair 时,实现 MUST 以 deterministic tie-break 选择 canonical binding(例如 first accepted binding by causal order/event id),并把 loser 标为 duplicate/non-canonical;`ck.self.direct_conversation.resolve` 不得随机返回两个不同 Realm。

### 3.7 DM Realm well-known 形态

1:1 DM Realm 是普通 Realm 的受约束形态,不是新的 Realm 类型。

MUST:

- `encryption_profile="mls_rfc9420"`。不得把 `mls_dm` 注册为 Realm `encryption_profile` 新枚举。
- Realm schema/profile 明确声明 direct conversation profile,例如 `schema_refs` 包含后续注册的 `ck.profile.direct_conversation.v1`,并在 Realm `fields` 中使用已注册的 direct-conversation discriminator。不得使用 `fields.purpose="direct_message"`,因为 `fields.purpose` 已被 principal control Realm 语义占用。
- active member count 必须等于 2。不得向 active DM Realm 加第三人;升级多人聊天必须创建新的普通 Realm/Flow,再用 Relation 或 Message 引用旧 DM 内容。
- `default_join_rule` MUST 是 `closed` 或等价 fail-closed policy;第三方 invite/member_add 必须被拒绝。
- 同一 unordered participant pair 至多一个 active canonical DM Realm。pair key 的精确 canonical encoding 是 normative 合入的 blocking dependency;它必须基于稳定 subject/pairwise DID 与 trust domain,并避免把 handle 字符串作为权威输入。pairwise DID 场景下,编码必须能把 pairwise DID 映射回可验证的稳定 subject,或显式声明不能跨 pairwise identity 合并;否则同一用户会被拆成多个 canonical pair。

MAY:

- 为 push/server-side rule 暴露最小 `is_direct_message` projection。该 projection 可由 direct conversation profile + active member count 派生,不得要求 server 解密用户内容。
- 保留非 canonical duplicate Realm 的历史可读性,但它不得作为默认聊天入口。

成员退出语义:

- 任一参与方主动离开 / 被移出 DM Realm 后,该 Realm 立即失去 active canonical DM 资格。direct conversation binding MUST 标为 retired / non-canonical,后续 `ck.self.direct_conversation.resolve(create=true)` MUST 创建新的 DM Realm、main Flow 与 binding。
- Resolver MUST NOT 为了"继续同一个私聊"把退出方重新加入旧 DM Realm。退出是明确的会话边界与密钥/历史边界;复用旧 Realm 会混淆退出后的 MLS epoch、history eligibility 与用户意图。
- 旧 DM Realm MAY 继续作为历史归档存在,其可读性按离开时的 Realm history visibility、retention、redaction 与本地备份策略决定。它不得接收新的默认聊天消息。

### 3.8 DM 主 Flow well-known 形态

消息必须挂在 Flow 的 `discussion` track 上,所以 direct conversation binding 必须同时绑定 `main_flow_id`。

DM 主 Flow MUST:

- 位于 DM Realm 内。
- `scope_circle_id=null`,继承 DM Realm 的 Realm-default MLS group。DM 主 Flow MUST NOT 再套 Circle;双人 Realm 的 Circle 子集切不出更窄隐私边界。
- 声明 `tracks.discussion.is_primary=true`,且 discussion track active。
- 在当前 v1 Flow schema 下携带合法 `stage`。推荐使用 `stage="in_progress"` 作为 wire 兼容值;direct conversation UI MUST NOT 把该 stage 当成待办进度展示,也 SHOULD 禁用普通 `ck.flow.stage.set` 控件。
- 通过 direct conversation binding 标识为该 Realm 的 main Flow。`discussion.is_primary=true` 只是 Flow 内默认入口,不能单独证明"这是 DM 主 Flow"。

同一 DM Realm 至多一个 active canonical main Flow。DM Realm 内 MAY 有其它普通 Flow,用于把某个话题升级成独立议题;默认聊天消息必须写入 binding 指向的 main Flow。

## 4. Interactions with normative spec

- `zh/identity/consent-model.md`:保留 consent 作为 action gate;补充 contact accept/tombstone 如何显式 grant/revoke consent,并强调 consent 不是 contact state truth source。
- `zh/discovery/discovery-directory.md` / `zh/sync/service-surface.md` / `zh/identity/consent-model.md`:收敛 private contact discovery 响应形态的现有措辞冲突。CKP-0013 取"PSI 位图 + 最小 invite/consent handoff stub"的窄读,但不引入 contact request handoff token;`discovery-directory.md` §6.2 需要改为不否认既有 stub。
- `zh/models/realm-and-space.md`:新增 direct conversation Realm profile、member_count=2、join closed、pair canonical binding 与 duplicate 处理;同时更新 principal control Realm allowlist,允许 contact facts / direct conversation binding facts 作为身份基础设施事件。
- `zh/models/flow-and-message.md`:新增 DM main Flow binding 约定;本提案不修改 `stage` 必填规则。
- `zh/models/relation.md` / `account-data-type-registry.json`:补充 L1/L2/L3 边界,防止把 contact relation 写入 `ck.relation.*` 或 holder-private account-data。
- `zh/crypto-media/encryption-and-audit.md` / `identity-handles.md`:明确 DM 使用 `mls_rfc9420` Realm-default MLS;`mls_dm` 只能是 profile/用途标签,不是 Realm encryption enum。
- artifacts:注册 contact fact payload、direct conversation binding payload、operation schemas、OpenAPI、`operations-error-mapping.json`、conformance vectors。

## 5. Rationale & alternatives

- **否决:contact 纯由 consent projection 得出。** consent 无 pending/rejected/tombstoned,且 requester 不能替 target 写 consent grant。把 request 编译成 target consent 在 issuer 模型上不合法。
- **否决:contact 纯产品面,维持 `/_soland/self/contacts/*`。** 通用客户端无法跨实现列出联系人,也无法解释 accepted contact 与 DM/call/presence gate 的关系。
- **否决:contact 作为 `ck.relation.* relation_kind=contact`。** Relation 是 Realm-scoped 协作图边;contact 是 principal-scoped 双边社交关系。
- **否决:用 DM Realm 存在性反推联系人。** 聊天历史可能保留、重复 Realm 可能存在、contact tombstone 不追溯删除历史;因此 DM Realm 只能说明有过或可用的会话载体。
- **否决:本提案顺手让 conversation Flow 省略 `stage`。** 这会触动 Flow schema required 字段、reducer、artifact 与 conformance。联系人生命周期不应夹带 Flow 基础模型变更。

## 6. Resolved decisions

- **Q1 source of truth:** contact 关系真源是 principal-scoped contact fact log;consent 只做 action gate。
- **Q2 signed log:** contact request/accept/reject/tombstone 与 direct conversation binding 都必须可被多设备/对端验证,不能只存在 server 私有 projection。
- **Q3 DM well-known 形态:** DM Realm 与 DM 主 Flow 都要钉死,分别落在 `realm-and-space.md` 与 `flow-and-message.md`;pair → realm/main_flow 的 binding 是 resolver 真源。
- **Q4 命名:** operation 继续使用 `ck.contact.*` 单数;account-data 继续使用 `ck.contacts.*` 复数。通过 catalog description 与 spec 边界消歧,不重命名既有 account-data。

## 7. Migration plan

1. 在 normative spec 中先合入 contact fact model 与 consent 边界,注册 fact/event payload 与错误码。
2. 收敛 `discovery-directory.md` / `service-surface.md` / `consent-model.md` 关于 private contact discovery response 的措辞:保留最小 invite/consent handoff stub,但明确不含 contact request token。
3. 增补 direct conversation binding、DM Realm profile、DM main Flow binding,并注册 pair key canonical encoding。
4. 注册 `ck.contact.*` 与 `ck.self.direct_conversation.resolve` operation,同步 OpenAPI、operation registry、error mapping。
5. soland 将 `/_soland/self/contacts/*` 迁移到 `/_cokret/self/contacts/*`,内部 contacts 表降级为 projection/cache,不得再作为真源。
6. yougen 从硬编码 `_soland` endpoint 迁移到 catalog operation;联系人列表展示 `state`、方向化 consent scopes 与 direct conversation 入口三层。
7. cotest 增加 conformance:
   - requester 不能替 target 写 contact accepted 或 consent grant;
   - pending/rejected/tombstoned 不得从 consent active/no-consent 伪造;
   - principal control Realm allowlist 接受 contact facts / direct conversation binding facts,但普通 Collaboration Realm 不承载 contact relation truth;
   - `ContactListRow.effective_scopes[]` 等价于 `bidirectional_scopes[]`,不得把单向 consent 显示成双向可用;
   - consent revoke 不自动 tombstone contact;
   - contact tombstone 只默认 revoke contact-managed active grant dots,不误删同 peer 的独立 consent;
   - contact tombstone 不隐式删除既有 DM Realm/历史;
   - private contact discovery 可以返回最小 invite/consent handoff stub,但不得返回 contact request token、reachability proof、完整 profile、成员资格或关系图谱;
   - `ck.self.direct_conversation.resolve` 在只有 consent、没有 accepted contact 时必须 `contact_not_accepted`;
   - resolver create 部分失败产生的 orphan Realm 不得作为默认聊天入口,重试只能在完整验证后补 binding;
   - 双方交换/镜像 binding facts 后必须对同一 pair 选出同一个 canonical binding;
   - pairwise DID 场景的 pair key canonical encoding 不得把同一 subject 拆成多个 canonical pair,除非 profile 明确声明不能跨 pairwise identity 合并;
   - 任一参与方退出 active DM Realm 后,旧 Realm 不得被 resolver 复用,下一次 create 必须产生新的 DM Realm/main Flow/binding;
   - `ck.self.direct_conversation.resolve` 幂等,并发 duplicate deterministic 收敛;
   - DM Realm 使用 `encryption_profile="mls_rfc9420"`,出现 `mls_dm` enum 必须 schema fail;
   - DM main Flow 必须有 binding,不能只靠 `discussion.is_primary` 推断。

## 8. References

- 姊妹提案:[CKP-0012 Account Self-Service Operations](./0012-account-and-contact-self-operations.md)(分拆来源)。
- `zh/identity/consent-model.md`、`zh/discovery/discovery-directory.md`、`zh/models/relation.md`、`zh/models/realm-and-space.md`、`zh/models/flow-and-message.md`。
- 下游:[`yougen/src/api/account.rs`](../../../../yougen/src/api/account.rs)(`_soland/self/contacts/*` 硬编码现状)。
