---
title: Holder-Private Consent Model
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 的访问授权由 **capability + invite** 两条路径承担。但二者都不能完整表达一类语义：

> "我同意 / 不同意来自 X 的联系请求。"

这是 **持有人私有 (holder-private) 决策**，独立于：

- 任何 Realm 的 membership（成员关系）
- 任何 capability grant（能力授权）
- 任何 invite token（邀请凭证）

它是 invite / direct contact 路径上的**前置 gate**：在"是否给 Alice 发出 invite"之前，先看"Alice 是否同意接收来自 Bob 的 invite"。

本规范定义 Cokret 的 consent state，与 capability / invite 正交。模型借鉴自 [`draft-ietf-mimi-protocol-06`](https://datatracker.ietf.org/doc/html/draft-ietf-mimi-protocol-06) 的 consent 概念，并完整落在 Cokret 的 Move / Anchor / Lattice 三原语之上：consent 是 holder 控制的 Realm 内某个 consent cell（or_set lattice）的当前 join 值，由签名 Move 维护。

## 2. 设计原则

### 2.1 Consent 是 holder 私有状态

Consent grant / revoke 表达的是 **holder 自己的决定**。它写入 holder 的 Principal Control Realm（或等价的 actor-private 流），不暴露给任何 Collaboration Realm。Realm 角色分类见 [`models/realm-and-space.md` §2.7](../models/realm-and-space.md)。

> **术语**：principal control Realm 是 holder 个人控制下的 Realm（profile = `ck.profile.principal_control_realm.v1`，purpose = `principal_control`），用于承载 consent、device authorization、session grant、push registration 等 holder 私有状态。Realm 的创建、字段、生命周期与 device-key 引导见 [`identity/key-management.md` §4.1](./key-management.md)（bootstrap 见 §5.0）；下文凡是出现"holder principal control Realm"或"等价 actor-private 流"，含义均以此为准。

- 写入方：holder 自己（或 holder 显式授权的 controller / agent）。
- 可见方：默认仅 holder；MAY 通过 holder 主动 disclose 给 peer 作为"green light"信号。
- 不进入 Collaboration Realm：consent 状态不暴露 holder 的隐私偏好给 Realm 内的其他成员。

### 2.2 Consent 不授予 Realm 权限，也不是联系人关系真源

Consent 表达"我允许某个 peer 发起某类联系动作"，但加入 Realm、写入 Realm、解密 E2EE 内容仍需独立的 capability + membership。Consent 是 invite / direct-message / call / presence 流程上游的 action gate，不替代下游授权。

联系人关系的 pending / accepted / rejected / tombstoned 状态不属于 consent cell。它们的真源是 [`contact-and-direct-conversation.md`](./contact-and-direct-conversation.md) 定义的 principal-scoped contact fact log。Consent 的有效状态只有 `active` / `no-consent`；`revoke` 是撤销操作，不是联系人关系状态。

### 2.3 Consent 与 capability 正交

| 维度 | Consent | Capability |
| --- | --- | --- |
| 关系 | holder ↔ peer pair | actor ↔ resource action |
| 持有方 | holder（被联系方） | actor（执行动作方） |
| 写入位置 | holder principal control Realm | 目标 Realm |
| 用途 | invite / contact 前置 gate | 执行动作 (read/write/admin/...) 时的权限判断 |
| 撤销 | `ck.consent.revoke` | `ck.capability.revoke` |

二者可独立存在：peer 持有"对 Alice 的 invite capability"，但 Alice 没 consent → invite 路径仍被 gate；Alice consent 给了 Bob，但 Bob 没 capability → invite 不能执行。

## 3. Consent Cell 与 Move 形态

### 3.1 Consent Cell

Consent state 写入 holder 控制的 Realm（默认是 holder 的 principal control Realm）内一个 or_set lattice cell：

```text
cell_id  = ck:cell:ck.component.consent.grant.v1:<consent_id>
lattice  = or_set
bottom   = (registry-declared, inert for or_set)  // or_set join never produces ⊥
```

- `consent_id` 是 consent 槽的 subject。同一 holder 对同一 peer 的不同 consent_scope 用不同 consent_id；同 consent_id 上所有 add / remove tag op 收敛于同一 cell。
- or_set join 永不产生 ⊥，因此 `bottom` 字段只是 registry 声明的占位值（registry-declared），对 consent 行为 **inert**，不构成任何"reject"语义；effective consent 始终由 or_set join 决定，不读取 `bottom`。
- **缺省判定（normative，唯一默认）**：一个 `(consent_id, peer, consent_scope)` 没有任何 active grant dot（`active_dots` 为空，或全部 dot 已被 `observed_dots` 撤销，或当前时间不在 `[not_before, expires_at]` 窗口内）时，**effective consent = no-consent**，invite / contact gate MUST NOT 放行（按 §6.1 profile：`require_explicit_consent` profile 下 MUST `failed_precondition` 拒绝；default profile 下 MAY 进入 holder 的 quarantine inbox 暂存待 review，而非直接拒绝或放行）。"无 active dot ⇒ no-consent ⇒ gate 拒绝"是 consent 的唯一默认判定——默认无授权而非默认放行；这不是来自 cell `bottom`，而是来自 §5 effective consent 的存在性要求（至少一条 active dot 才放行）。

### 3.2 `ck.consent.grant` Move

**为什么暴露 dot 模型（normative rationale）**: observe-remove OR-Set 要求 revoker 在 wire 层能枚举将要撤销的具体 dot；否则两个并发 revoke 会因为没有 `observed_dots` 上下文产生分布式 race（一方撤旧 dot，另一方撤新 dot，UI 看似已撤销但 state 仍 active）。把 dot 暴露给客户端是正确性必需，不是冗余复杂度。

```text
Move(ck.consent.grant) {
  event_id     = ck:event:019640ed-7000-7000-8000-000000000001   // producer-assigned typed UUIDv7
  event_digest = sha256:<H(canonical bytes excluding proofs and unsigned)>   // content-addressed fingerprint
  issuer       = holder DID（或 holder DID Document 显式授权的 controller / agent）
  realm_id     = holder principal control Realm
  preconditions = []          // grant 不依赖 cell 既有状态
  effects   = [
    (ck:cell:ck.component.consent.grant.v1:<consent_id>,
     {type: "add",
      dot:  "ck:event:019640ed-7000-7000-8000-000000000001:0",   // = "<enclosing event_id>:<effect_index>"
      value: {
        intent: {                          // projection-level dedupe key
          consent_id: <consent_id>,
          peer:       "did:web:bob.example.com",
          consent_scope: "invite"
        },
        not_before:   "2026-05-07T00:00:00Z",
        expires_at:  "2026-12-31T00:00:00Z",
        evidence_ref: "ck:event:019640e0-0000-7000-8000-000000000002",
        reason:       "Bob completed verified contact discovery"
      }})
  ]
  refs       = [
    (id="ck:grant:0196411c-b000-7000-8000-000000000000",
     role="authorized_by")
  ]
  anchor_ref = <holder principal control Realm 的最新 Anchor>
}
```

字段语义：

- `intent.consent_id`：consent cell subject。同一 holder 对同一 peer 的不同 consent_scope 用不同 consent_id。
- `intent.peer`：counterparty DID 或 pairwise DID。
- `intent.consent_scope`：详见 §4。
- `not_before` / `expires_at`：时间窗口（可选）。窗口外 consent 不生效，相当于 implicit revoke（不需要单独的 revoke Move）。
- `evidence_ref`：可选审计链——指向引发此 consent 的 claim disclosure / presentation response / invite proof Move。
- `reason`：人类可读理由（仅审计，不参与授权）。

Payload-only schema 示例：

```json schema=schemas/event-payload.schema.json#/$defs/consent_grant_payload
{
  "consent_id": "consent-alice-bob-invite-001",
  "peer": "did:web:bob.example.com",
  "consent_scope": "invite",
  "not_before": "2026-05-07T00:00:00Z",
  "expires_at": "2026-12-31T00:00:00Z",
  "evidence_ref": "ck:event:019640e0-0000-7000-8000-000000000002",
  "reason": "Bob completed verified contact discovery"
}
```

Issuer MUST 是 holder 自己（或 holder DID Document 显式授权的 controller / agent）。其他 actor 提交的 grant Move 在 holder 的 principal control Realm MUST `unauthorized` reject。

`dot` 由 `<enclosing event_id>:<effect_index>` 派生，全局唯一，不再使用 deterministic tag。Projection 层按 `intent` 把同一 (consent_id, peer, consent_scope) 下当前 active 的多个 dot 折叠成一条 effective consent。同一 holder 对同一 intent 重复 grant 会产生不同 dot，or_set 视为多个独立 add——effective consent 仍然 active；revoke 时需要枚举该 intent 当前所有 active dot 才能完整撤销（见 §3.3）。

### 3.3 `ck.consent.revoke` Move

```text
Move(ck.consent.revoke) {
  event_id     = ck:event:0196414c-3000-7000-8000-000000000003   // producer-assigned typed UUIDv7
  event_digest = sha256:<H(canonical bytes excluding proofs and unsigned)>   // content-addressed fingerprint
  issuer       = holder DID
  realm_id  = holder principal control Realm
  preconditions = [
    (ck:cell:ck.component.consent.grant.v1:<consent_id>,
     {op: "contains_dots",
      dots: [
        "ck:event:019640ed-7000-7000-8000-000000000001:0"   // anchor_ref pre-state 下该 intent 全部 active dots
      ]})
  ]
  effects   = [
    (ck:cell:ck.component.consent.grant.v1:<consent_id>,
     {type: "remove",
      observed_dots: [
        "ck:event:019640ed-7000-7000-8000-000000000001:0"
      ],
      value: {
        revoked_at: "2026-06-15T10:00:00Z",
        reason:     "Bob harassment incident #4711"
      }})
  ]
  refs       = [(id="ck:grant:0196411c-b000-7000-8000-000000000000", role="authorized_by")]
  anchor_ref = <holder principal control Realm 的最新 Anchor>
}
```

`observed_dots` MUST 列出 revoke 想要撤销的具体 add dot；它们 MUST 在 `Move.anchor_ref` 对应 pre-state 下解析为合法 add op。precondition `contains_dots` 让 reducer 在 dots 已被先行 revoke 时拒绝 no-op 重放，避免审计日志中出现无意义记录；多 issuer 并发 revoke 同一 dot 收敛于 or_set 的去重语义。`observed_dots` 之外的 dot 不受影响——这是 OR-Set 的 normative 行为。

Payload-only schema 示例：

```json schema=schemas/event-payload.schema.json#/$defs/consent_revoke_payload
{
  "consent_id": "consent-alice-bob-invite-001",
  "observed_dots": [
    "ck:event:019640ed-7000-7000-8000-000000000001:0"
  ],
  "revoked_at": "2026-06-15T10:00:00Z",
  "reason": "Bob harassment incident #4711"
}
```

Payload `observed_dots[]` MUST 与 Move effect 中的 `observed_dots` 完全一致；缺失、额外、重复或排序后集合不等都 MUST `schema_violation` / `failed_precondition` 拒绝。这样 schema validation、审计 projection 与 lattice reducer 看到的是同一个撤销集合。

**Regrant**：撤销后 holder 可以再次发出 `ck.consent.grant` Event；新 Event 产生新的 `dot`（来自不同 `event_id`），不在任何先前 `observed_dots` 中，effective consent 重新 active。Regrant 是 normative 支持的行为。

**完整撤销 vs 部分撤销**：撤销整个 (consent_id, peer, consent_scope) intent 需要 client 在构造 revoke Move 前先查询当前 cell 的 or_set join，列出该 intent 下所有 active dot。Missing 一些 dot 是合法操作，但只构成部分撤销，剩余 dot 仍然 active——admin / UI MUST 把这种状态明确提示为 "partial revoke"。

撤销在该 revoke Move 进入 Anchor frontier 后立即生效——consent cell 的 or_set join 值不再含被 observed 的 grant dot。frontier 之前 peer 凭借 consent 发出的 invite / contact 不会被追溯失效（已经发出的 invite 由 invite revoke 单独处理）。

## 4. Scope 枚举

| Scope | 语义 |
| --- | --- |
| `invite` | peer 可发送 Realm / Flow invite |
| `direct_message` | peer 可发起 1:1 消息（DM Realm）|
| `voice_call` | peer 可发起 WebRTC 语音通话 |
| `video_call` | peer 可发起 WebRTC 视频通话 |
| `presence` | peer 可观察 holder presence |
| `any` | 全部 scope（覆盖所有上述类型）|

`consent_scope=any` 是便利值，等价于显式 grant 所有具体 consent_scope。撤销 `any` consent 同时撤销所有具体 consent_scope；撤销具体 consent_scope 不影响其他 scope。

### 4.1 Scope 撤销级联 与 缓存失效（normative）

`ck.consent.revoke` 的 scope 语义与缓存失效规则：

#### 4.1.1 Scope 级联

- **按 `consent_id` 全量撤销**（推荐路径）：revoke Move 的 `observed_dots` 列出 cell 当前 `(consent_id, peer, *)` 下所有 active dot，无论原 grant 的 scope 是 `any` 还是具体 consent_scope。这是显式"完全 revoke 该 consent_id"操作。
- **按 scope 部分撤销**：revoke Move 仅列出某具体 consent_scope 对应的 active dot。剩余 consent_scope 的 dot 保持 active。
- **`consent_scope="any"` 与具体 consent_scope 互斥语义**：
  - 撤销一条 `consent_scope=any` 的 grant dot MUST 显式枚举该 `(consent_id, peer)` 下当前 active 的 **所有** consent_scope dot（含具体 consent_scope 的 grant dot）。即 `any` revoke 的 cascade 由 payload / Move effect 中完整的 `observed_dots[]` 表达；reducer MUST NOT 基于一个 `consent_scope=any` dot 隐式推断并移除未枚举的其他 dot。若 active dot 未被枚举，effective consent 只构成部分撤销，admin / UI MUST 标 `partial_revoke`。
  - 反向不成立：撤销一条 `consent_scope=invite` 的具体 consent_scope dot 仅清空 `invite`，不影响同 `(consent_id, peer)` 下 `consent_scope=any` 的 dot——因为 `any` 是 holder 显式更宽授权，需要 holder 再单独撤销 `any` 才算 cascade。
  - 这条非对称规则 MUST 在 admin / UI 中明示，避免用户误以为"撤销 invite 就等于全撤销"。
- **conformance vector** `ck.vector.consent.scope_cascade.v1` 覆盖 (a) `any` revoke cascade 到具体 consent_scope；(b) 具体 consent_scope revoke 不影响 `any`；(c) 部分 scope revoke 留下其他 scope active；(d) 完整 revoke 必须列出当前 cell 全部 active dot 否则只构成部分 revoke。

#### 4.1.1.1 UI / admin 展示要求

发起 revoke 前，客户端 / admin MUST 展示将被写入 `observed_dots[]` 的实际 dot 清单及其 consent_scope 分组，并明确标注本次操作是 full revoke 还是 partial revoke。若用户选择“撤销 invite”但同一 `(consent_id, peer)` 下仍存在 `consent_scope=any` 或其它具体 consent_scope 的 active dot，UI MUST 在确认前提示这些 dot 将继续授权对应能力；不得用一个泛化按钮文案暗示未枚举的 scope 会被隐式撤销。

#### 4.1.2 缓存失效（normative MUST）

consent revoke 进入 Anchor frontier 后，下列下游缓存 MUST eager invalidate（同一事务边界内）：

| 缓存 | 失效粒度 | 触发动作 |
| --- | --- | --- |
| Private contact discovery PSI 结果 / invite handoff cache | 按 `(holder_did, peer_did)` 失效，下次查询走完整 consent 重判 | 不返回 stale PSI match 或 invite handoff，防止 peer 看到已撤销的"可联系"指示。 |
| MIMI consent check cache（interop 模块） | 按 `(holder_did, peer_did, scope)` 失效；`any` revoke 失效全部 scope | interop bridge 下次跨协议解析 MUST 重新校验。 |
| Push / contact discovery 缓存（含 PSI 结果） | 按 `(holder_did, peer_did)` 失效；PSI 索引 MUST 在下次轮转时排除 revoked peer | 即使 cache TTL 未到，revoke 后下一次 contact sync MUST 反映新状态。 |
| Invite gate cache（§6.1 invite 前置 gate） | 按 `(holder_did, peer_did, scope)` 失效 | 即便已缓存"该 peer 有 active consent"，revoke 后下一次 invite MUST 重判，旧 cache MUST NOT 让 invite Move 通过 precondition。 |
| In-flight invite 与 DM Realm | **不**追溯 — 已发出的 invite / 已创建的 DM Realm 不自动撤销（与 §3.3 frontier 之前规则一致）；如需撤销，单独发 `ck.invite.revoke` / member remove。 | 不自动级联撤销已生效邀请或 DM Realm。 |

`consent_scope="any"` 被撤销后 cascade 失效规则：上面 5 类缓存中所有 consent_scope 的 entry 必须一起失效，包括 `invite`、`direct_message`、`voice_call`、`video_call`、`presence`。不允许实现把 `any` revoke 只清单一 scope。

`ck.vector.consent.cache_invalidation.v1` 覆盖 (a) revoke 后 private contact discovery / invite handoff 立即不返回该 peer；(b) revoke 后下一次 invite Move 被 precondition 拒绝（capability gate 重判）；(c) `any` revoke cascade 失效所有 consent_scope cache；(d) revoke 后 PSI 索引在下一次轮转时排除该 peer。

## 5. Cell Join 与 Effective Consent

Consent cell 是 or_set lattice（dot-based observed-remove，详见 [`event-auth-state-resolution.md` §5.3.1](../authz/event-auth-state-resolution.md)）。Effective consent 由当前 Anchor view 下 cell 的 or_set join 派生：

- `active_dots(cell) = { (dot, value) ∈ or_set.adds | dot ∉ or_set.observed_dots }`
- `effective_grants(cell) = group active_dots(cell) by value.intent` —— projection 把同 intent 的多 active dot 折叠成一条 effective consent。
- 一个 (consent_id, peer, consent_scope) 的 grant 当前生效（即 invite / contact 路径上 gate 放行）当且仅当：
  - `active_dots(cell)` 中存在 ≥1 条 `value.intent == (consent_id, peer, consent_scope)` 的 dot；
  - 当前时间 ∈ `[not_before, expires_at]`（窗口字段缺省视为 `(-∞, +∞)`）。
- 不同 consent_id 是独立 cell；查询 `(holder, peer, consent_scope)` 时 invite / contact service 遍历该 holder 全部 consent cell 匹配。
- 同 Anchor 批内并发 grant 与 revoke 在 or_set join 后唯一确定（add dot 集合与 observed_dots 集合各自取并集，dot 之间没有先后），不产生 ⊥。审计 / admin 视图可暴露并发的 add / remove dot 序列以提示决策不连续，但 invite gate 仍按 `active_dots` 集合判定。

物化 `Consent` 对象由 holder client / admin 从该 cell 当前 join 值生成；它不是协议授权根，而是 UX / 审计辅助视图。Consent cell 的 schema 由本文与 [`identity-handles.md`](./identity-handles.md) 定义，未在 `models/` 提供 canonical-object schema。

## 6. 与 Invite / Contact 流程的整合

### 6.1 Invite 前置 gate

Peer 发送 invite Move 时，invite service / facade SHOULD 在 Move 接受 / 投递前查询 holder 的 consent cell：

1. 调用 holder 的 principal control Realm（或受托 contact discovery service）查询所有候选 consent cell（subject 由 holder consent 命名约定决定），跑 or_set join 后筛选 `value.intent` 匹配 `(peer=requester, scope="invite" OR consent_scope="any")` 当前 active 的 dot 集合。
2. 若没有匹配的活跃 grant：
   - **`require_explicit_consent` profile**：invite Move MUST `failed_precondition` reject（consent gate 可表达为 invite Move 的 precondition：`active_intent_exists((requester, "invite"|"any"))`，由 reducer 把它编译为对 cell `active_dots` 的过滤）。Peer SHOULD 通过 `ck.private_contact_discovery.v1` 等机制请求 holder 显式授权后重试。
   - **default profile**：invite MAY 进入 holder 的 quarantine inbox（"陌生人邀请"），由 holder 在 UI 上 review 后构造 grant Move 或丢弃。
3. 若有匹配活跃 grant 且当前时间在 `[not_before, expires_at]`：invite Move 正常 anchor。

policy MAY 声明 `ck.realm.policy_components` 中的 `preauth` component 包含 `require_consent: true`，对该 Realm 的所有 invite Move 强制以 consent cell precondition 表达。

**UX 提示（normative for client implementations）**: 撤销 consent 后，客户端 UI MUST 提示用户 "已发出的 invite 不会自动失效；如需撤销已发出 invite，请单独执行 `ck.invite.revoke`"。该提示是非追溯语义的 UX 配套，服务端不强制（consent revoke 不会自动 cascade 到 invite）。

### 6.2 Contact / DM 前置 gate

类似地，发起 1:1 message Realm、WebRTC call、presence subscription 时，发起方 SHOULD 验证目标的 consent state（consent_scope = `direct_message` / `voice_call` / `video_call` / `presence`）。

`ck.direct_conversation.resolve` 是联系人私聊入口；它 MUST 同时检查 accepted contact projection 与目标 holder 对 requester 的 active `direct_message` / `any` consent。只有 consent、没有 accepted contact 时，resolver MUST fail closed（`failed_precondition` / `contact_not_accepted`）；只有 accepted contact、没有可验证 consent 时，resolver MUST fail closed（`failed_precondition` / `contact_consent_missing`）。非联系人但基于 consent 发起的一次性 DM profile 若未来需要，必须另行注册 operation，不得复用该 resolver。

`ck.private_contact_discovery.v1` 返回 PSI set-membership 命中位图时，MAY 附带 holder 当前 consent state hash 或最小 invite/consent handoff stub（不暴露具体 consent 内容，只声明 grant/revoke 状态与下一步引导），让发起方在尝试联系前判断是否需要先请求 consent。该响应 MUST NOT 包含 contact request handoff token、reachability proof、handle verified claim、组织成员资格、Realm membership 或读取权限。

**PSI 命中位时序侧信道（normative）**：contact discovery / PSI 端点 MUST 按 `(requester, holder)` 维度限速，防止请求方通过高频探测观测 holder 命中 bit 的翻转时刻（grant/revoke 时点）形成时序侧信道。命中位图 MUST 引入粗粒度时间 bucket（类似 presence `last_active_at` 的 bucket 化），使命中状态变化只在 bucket 边界对外可见，而非实时反映 holder 决策的精确时刻。此外，PSI 探测 MUST 纳入 holder 可审计的访问记录，使 holder 可事后发现针对自己的反复探测。

**Consent state hash 侧信道（normative，MUST 加盐或改 opaque token）**：裸 consent state hash（例如对 `(consent_id, peer, scope, granted/revoked)` 直接 SHA-256）是低熵、跨 requester 稳定的值——任意请求方可离线枚举有限的 consent 取值组合反查 holder 的真实 consent 状态，或跨多次/多 requester 比对 hash 是否相同来关联 holder 对不同 peer 的决策。因此当响应携带 consent state hash 时，该 hash MUST 满足以下之一，否则 MUST NOT 暴露：

- **加盐**：hash 输入 MUST 混入 per-requester salt 或 per-session salt（例如 `HMAC(key = per_session_salt, data = canonical_consent_state)`，salt 至少 128-bit 随机、每个 requester / session 不同且不可由请求方预测），使同一 consent 状态对不同 requester / session 产生不同、不可反查、不可跨 requester 关联的值；裸的、跨 requester 稳定的 consent state hash MUST NOT 出现在 wire 上。
- **或改为 holder-authorized opaque token**：用一个由 holder（或受托 contact discovery service）签发的、不透明、短期、单 audience 的 token 代替 hash，token 本身不泄露 consent 内容，只在该 requester 的下一步引导中被当作 grant/revoke 状态指示；token MUST 绑定 audience 与过期时间。

实现 MUST NOT 把同一裸 hash 复用于多个 requester；conformance 检查 MUST 覆盖"同一 consent 状态对两个不同 requester / session 产生不同 hash/token"。

## 7. MIMI Interop

MIMI 协议有 `request_consent` / `update_consent` 操作（`ck.mimi.request_consent` / `ck.mimi.update_consent`），见 [`extensions/mimi-interop.md`](../extensions/mimi-interop.md) §10。Facade 映射规则：

- 接收 MIMI consent update：facade MUST 先验证 actor 是声明 holder 或受授权 controller，然后构造 grant 或 revoke Move 写入 holder principal control Realm 的 consent cell。
- 发送 Cokret consent state 到 MIMI：facade MUST 把当前 consent cell or_set join 值翻译为 MIMI consent message，并保留 consent_id 作为 inter-protocol correlation。
- consent state 不暴露具体 evidence_ref / reason 跨 provider；只暴露最小 `(peer, scope, granted/revoked)` 三元组。

## 8. 隐私与审计

- consent state 是 holder 私有；服务端 MUST NOT 把它暴露给非 holder actor 或非授权 service。
- consent grant / revoke 的 backfill 受 holder principal control Realm 的 history visibility 与 access policy 约束。
- audit projection MAY 记录 consent state 变化（用于合规审查），但 audit access 必须经 holder 授权或 legal hold 边界。
- pairwise DID / pseudonym 场景下，consent 可绑定 pairwise DID 而非真实 principal DID；reducer 不强制 consent.peer 必须是 principal DID。

## 9. 与未来 Capability Constraint 的关系

扩展 profile MAY 引入 capability constraint type `consent_required`，使某些 capability grant 在 Move 验证时 runtime check holder consent。本规范定义的 consent cell 是该 constraint 的查询源。在引入该 constraint 前，consent gate 由 invite / contact service 在投递前查询 cell join 值实现，不直接出现在 Move precondition 上。
