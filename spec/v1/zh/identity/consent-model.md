---
title: Holder-Private Consent Model
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 的访问授权由 **capability + invite** 两条路径承担。但二者都不能完整表达一类语义：

> "我同意 / 不同意来自 X 的联系请求。"

这是 **持有人私有 (holder-private) 决策**，独立于：

- 任何 Realm 的 membership（成员关系）
- 任何 capability grant（能力授权）
- 任何 invite token（邀请凭证）

它是invite及其它**不以 Contact 为授权依据**的动作路径的holder-private前置gate。Contact request/response、Contact-based create/send与Personal DM明确不读取本模型；它们只读取双方holder-signed directional Contact heads（见[`contact-and-direct-conversation.md`](./contact-and-direct-conversation.md)）。

本规范定义 Arkret 的 consent state，与 capability / invite 正交。模型借鉴自 [`draft-ietf-mimi-protocol-06`](https://datatracker.ietf.org/doc/html/draft-ietf-mimi-protocol-06) 的 consent 概念，并完整落在 Arkret 的 CBS / Lattice 模型之上：consent 是 holder 控制的 Realm 内某个 consent cell（sequenced_state，值为活跃 tagged set）的当前确认值，由签名 Control Move 维护并在被 accepted Seal 覆盖后生效。

## 2. 设计原则

### 2.1 Consent 是 holder 私有状态

Consent grant / revoke 表达的是 **holder 自己的决定**。它写入 holder 的 Principal Control Realm（或等价的 actor-private 流），不暴露给任何 Collaboration Realm。Realm 角色分类见 [`models/realm-and-space.md` §2.8](../models/realm-and-space.md)。

> **术语**：principal control Realm 是 holder 个人控制下的 Realm（profile = `ak.profile.principal_control_realm.v1`，purpose = `principal_control`），用于承载 consent、device authorization、session grant、push registration 等 holder 私有状态。Realm 的创建、字段、生命周期与 device-key 引导见 [`identity/key-management.md` §4.1](./key-management.md)（bootstrap 见 §5.0）；下文凡是出现"holder principal control Realm"或"等价 actor-private 流"，含义均以此为准。

- 写入方：Event actor 与认证 holder MUST 是 holder Principal Control Realm 当前 authority-root controller，且 `authorization_ref` MUST 绑定该 authority root。`ak.consent.grant` / `ak.consent.revoke` 是 `root_control_only` action，不支持独立 managed-behalf 执行，也不存在可授予 controller / agent 的 `consent_write` 委派。
- 可见方：默认仅 holder；MAY 通过 holder 主动 disclose 给 peer 作为"green light"信号。
- 不进入 Collaboration Realm：consent 状态不暴露 holder 的隐私偏好给 Realm 内的其他成员。

### 2.2 Consent 不授予 Realm 权限，也不是联系人关系真源

Consent 表达"我允许某个 peer 发起某类不以 Contact 为授权依据的动作"，但加入 Realm、写入 Realm、解密 E2EE 内容仍需独立的 capability + membership。Consent 可作为 invite、非 Contact call/presence 等流程的上游 action gate；Contact-based create/send 与 Personal DM 完全不读取它。

仅当正式登记的**持久 ordinary action** 求值器实际需要某个 active Consent grant 时，才展开 [CBS §5](../authz/cbs-profiles.md#5-授权关闭与有限期) 的 `consent_grant` 历史依赖；其 A/G 是确切 ConsentGrant Event，revoke 只关闭 observed tag 对应实例。invite、call/presence 的仅 live 私有前置检查仍是 live 检查，不自动把全部普通历史变为 Consent-dependent；尤其 Contact/Personal DM 始终没有该依赖。结构 action 上界不是新增 Consent 要求。

联系人关系的 pending / accepted / rejected / tombstoned 状态不属于 consent cell。它们的真源是 [`contact-and-direct-conversation.md`](./contact-and-direct-conversation.md) 定义的 principal-scoped contact fact log。Consent 的有效状态只有 `active` / `no-consent`；`revoke` 是撤销操作，不是联系人关系状态。

### 2.3 Consent 与 capability 正交

| 维度 | Consent | Capability |
| --- | --- | --- |
| 关系 | holder ↔ peer pair | actor ↔ resource action |
| 持有方 | holder（被联系方） | actor（执行动作方） |
| 写入位置 | holder principal control Realm | 目标 Realm |
| 用途 | invite / 不以 Contact 为授权依据的动作前置 gate | 执行动作 (read/write/admin/...) 时的权限判断 |
| 撤销 | `ak.consent.revoke` | `ak.capability.revoke` |

二者可独立存在：peer 持有"对 Alice 的 invite capability"，但 Alice 没 consent → invite 路径仍被 gate；Alice consent 给了 Bob，但 Bob 没 capability → invite 不能执行。

## 3. Consent Cell 与 Control Move 形态

### 3.1 Consent Cell

Consent state 写入 holder 控制的 Realm（默认是 holder 的 principal control Realm）内一个 sequenced_state 安全集合 Cell：

```text
cell_id  = state-slot:ak.component.consent.grant.v1:<consent_id>
state_model = sequenced_state
value_shape = set
```

- `consent_id` 是 consent 槽的 subject。同一 holder 对同一 peer 的不同 consent_scope 用不同 consent_id；同 consent_id 上所有 add / remove tag op 收敛于同一 cell。
- effective consent 来自唯一确认序列中的活跃 tagged set。grant/revoke 检查实际相关 revision，竞争命令可以被拒绝，不能无序 join 成权限。
- **缺省判定（normative，唯一默认）**：一个`(consent_id,peer,consent_scope)`没有active grant dot时，effective consent=`no-consent`，invite/非Contact action gate不得放行（按§6.1 profile拒绝或进入holder quarantine）。该默认不得扩展到Contact/Personal DM，因为那些路径根本不以Consent为authority。

### 3.2 `ak.consent.grant` Control Move

**精确撤销身份（normative）**：observed_dot_ids 固定要移除的授权实例，不能用业务值或接收时刻推测。签名 basis 的 Cell revision 必须在确认执行位置仍匹配；并发变化导致拒绝后，调用方取得新状态再明确签署所需撤销。不能以此保证一次部分撤销删除所有未来 grant。

```text
ControlMove(ak.consent.grant) {
  event_id      = ak:event:AfumWbbDTAdHm6EJcwrgFczGIei511I72WryaaMIPtpV
  kind          = ak.consent.grant
  realm_id      = holder principal control Realm
  scope_ref     = {kind: "realm", realm_id: <holder PCR>}
  actor_id      = holder DID
  payload       = {
    consent_id: <consent_id>,
    peer: {kind: "actor", actor_id: {kind: "account", account_id: {
      principal_id: "ak:did_core:webvh:z4Uy7eEwDuHWSxMT2dHWEWPip",
      station_id: "ak:did_core:web:peer.example"}}},
    consent_scope: "invite",
    not_before: "2026-05-07T00:00:00Z",
    expires_at: "2026-12-31T00:00:00Z",
    evidence_ref: "ak:event:AbrLG_RrXje1gI-BHa-0mIIb4PC0jTvW-mBnXJu6WTgT",
    reason: "Bob completed verified contact discovery"
  }
  preconditions = []
  refs          = [(id="ak:grant:AYATq7mU7m9Q7AWf6OW2_Qo-yToeIo7cGEVJ7O4dyc0f", role="authorized_by")]
  seal_basis    = <holder principal control Realm 的当前 Seal basis>
}

receiver 按 registry 从 `kind + payload` 唯一投影一条 安全集合 add：目标 cell
为 `ak.component.consent.grant.v1:<consent_id>`，dot 为
`"ak:event:<enclosing event_id>:<write_index>"`（dot 的规范定义见 [`../models/event-and-patch.md`](../models/event-and-patch.md) §2.4.2），value 为 payload 的规范化 consent
entry。该投影不是 Event wire 字段。
```

字段语义：

- `intent.consent_id`：consent cell subject。同一 holder 对同一 peer 的不同 consent_scope 用不同 consent_id。
- `intent.peer`：闭合 `consent_peer`，两个分支的语义互斥且**跨 kind 永不匹配**（见 §6.1 查询步骤 1）。
  - `{kind:"actor",actor_id:ActorId}`：ordinary account、Agent、**为每段关系另铸 principal 的 pseudonymous Account**、以及 MIMI exact correlation 一律走这一支，完整保留 Account Station 与 actor role。不得把同 core 异 Station / 异角色 Actor 当作同一 peer。
  - `{kind:"pairwise_principal",realm_id:RealmId,principal_id:DidCoreId}`：**唯一表示 minimal-metadata Realm 的 Realm-local ephemeral pairwise actor**（[`identity-did.md` §3.1](./identity-did.md) 的 `ak.profile.ephemeral_pairwise_principal.v1`；该 actor 不建账号 / PCR / 设备目录，authority 完全来自 `realm_id` 所指 Realm 中一条 active LeafNode，见 [`../crypto-media/encryption-and-audit.md` §2.7](../crypto-media/encryption-and-audit.md)）。因为这种 actor **脱离该 Realm 就不存在**，`realm_id` 是必填载体；consent Event 位于 holder PCR，其 envelope `realm_id` 是 holder 自己的 PCR，**不能**充当该绑定。`principal_id` MUST 是 `ak:did_core:key:` 形态。不得把普通账号的 principal core 填入本分支。
  - **不携带 `pairwise_verification_method`**：`did:key` 的 method URL 与 `ak:did_core:key:` 投影一一对应，另设字段即平行 principal 镜像；consent peer 是匹配键，不承担签名验证。
  - **不携带 binding Event ref / binding digest / epoch / leaf selector。** 三条理由任一独立成立：v1 没有「accepted pairwise binding Event」这个对象，binding 就是该 Realm 内的 MLS LeafNode，要求 ref 等于发明一个新 Event 类型；LeafNode 每次 commit 都会变，把 epoch / leaf 冻进 holder PCR 的 grant Event 下一个 commit 即陈旧，而跨 epoch 稳定的身份恰好就是 `did:key` 投影的 `principal_id`（rebinding = 换 key = 换 actor = 换 peer，本来就该是一条新 consent entry）；holder PCR 对 Collaboration Realm history 没有也不应有可验证视图，要求写入时证明外部 Realm 的当前态，是把浮动远端状态钉进 frozen Seal basis。
  - **「只有已接受 binding」的强制点在匹配时点，不在写入时点（normative）**：Event admission 只验证闭合形态、`realm_id` 合法、`principal_id` 形态、以及 peer principal ≠ holder principal，**不**查询任何外部 Realm。holder 若填了未接受、跨 Realm 或凭空生成的值，该 entry 在 §6.1 匹配时永远命中不了，等价 no-consent，fail closed；伪造只能自伤，不产生任何越权。holder 离开该 Realm 后不再有该 Realm 的 view，pairwise entry 自然永不匹配，规范不需要额外的可见性或删除规则。
- `intent.consent_scope`：详见 §4。
- `not_before` / `expires_at`：时间窗口（可选）。窗口外 consent 不生效，相当于 implicit revoke（不需要单独的 revoke Control Move）。
- `evidence_ref`：可选审计链——指向引发此 consent 的 claim disclosure / presentation response / invite proof Event。
- `reason`：人类可读理由（仅审计，不参与授权）。

Payload-only schema 示例：

```json schema=schemas/event-payload.schema.json#/$defs/consent_grant_payload
{
  "consent_id": "ak:consent:019640ed-6000-7000-8000-000000000001",
  "peer": {
    "kind": "actor",
    "actor_id": {
      "kind": "account",
      "account_id": {
        "principal_id": "ak:did_core:webvh:z4Uy7eEwDuHWSxMT2dHWEWPip",
        "station_id": "ak:did_core:web:peer.example"
      }
    }
  },
  "consent_scope": "invite",
  "not_before": "2026-05-07T00:00:00.000Z",
  "expires_at": "2026-12-31T00:00:00.000Z",
  "evidence_ref": "ak:event:AbrLG_RrXje1gI-BHa-0mIIb4PC0jTvW-mBnXJu6WTgT",
  "reason": "Bob completed verified contact discovery"
}
```

Event `actor_id` 与认证 holder MUST 是 holder Principal Control Realm 当前 authority-root controller，且 `authorization_ref` MUST 绑定当前 authority-root 授权。`ak.consent.grant` / `ak.consent.revoke` 是 `root_control_only` action，不支持由不同主体独立 managed-behalf 执行，也不可作为 `consent_write` capability 授予 controller / agent；通用 PCR write、co-owner grant、agent 自动化权限、payload approval evidence 或 `ak.self.events.command.submit.v1` 均不得替代 authority-root authorization。普通 Event admission MUST 验证上述约束，缺失或由其他 actor 提交时 MUST 以 `unauthorized` reject。

`dot` 由 `ak:event:<enclosing event_id>:<write_index>` 派生，全局唯一。Projection 层按 `intent` 把同一 (consent_id, peer, consent_scope) 下当前 active 的多个 dot 折叠成一条 effective consent。同一 holder 对同一 intent 重复 grant 会产生不同 dot，安全集合将顺序确认的 grant 保留为不同 add——effective consent 仍然 active；revoke 时需要枚举该 intent 当前所有 active dot 才能完整撤销（见 §3.3）。

### 3.3 `ak.consent.revoke` Control Move

```text
ControlMove(ak.consent.revoke) {
  event_id      = ak:event:AdOBf6fvL9Q7FrkkRwDrquZ52Nky2-aShGC7r3Pl6WsP
  kind          = ak.consent.revoke
  realm_id      = holder principal control Realm
  scope_ref     = {kind: "realm", realm_id: <holder PCR>}
  actor_id      = holder DID
  payload       = {
    consent_id: <consent_id>,
    observed_dot_ids: ["ak:event:AfumWbbDTAdHm6EJcwrgFczGIei511I72WryaaMIPtpV:0"],
    revoked_at: "2026-06-15T10:00:00Z",
    reason: "Bob harassment incident #4711"
  }
  preconditions = [
    (state-slot:ak.component.consent.grant.v1:<consent_id>,
     {op: "contains_dots",
      dots: ["ak:event:AfumWbbDTAdHm6EJcwrgFczGIei511I72WryaaMIPtpV:0"]})
  ]
  refs          = [(id="ak:grant:AYATq7mU7m9Q7AWf6OW2_Qo-yToeIo7cGEVJ7O4dyc0f", role="authorized_by")]
  seal_basis    = <holder principal control Realm 的当前 Seal basis>
}

receiver 按 registry 从 `kind + payload` 唯一投影同一 consent cell 上的
安全集合 remove；其 `observed_dot_ids` 必须逐字取自 payload。该投影不是 Event
wire 字段。
```

`observed_dot_ids` MUST 列出 revoke 想要撤销的具体 add dot；它们 MUST 在该 Control Move 的 `seal_basis` view 下解析为合法 add op。precondition `contains_dots` 让 reducer 在 dots 已被先行 revoke 时拒绝 no-op 重放，避免审计日志中出现无意义记录；多 issuer 基于同一 revision 撤销时至多一个成功；相同 Event exact replay 返回原结果，另一 stale Event 拒绝。`observed_dot_ids` 之外的 dot 不受影响——这是登记的精确移除行为。

Payload-only schema 示例：

```json schema=schemas/event-payload.schema.json#/$defs/consent_revoke_payload
{
  "consent_id": "ak:consent:019640ed-6000-7000-8000-000000000001",
  "revoked_at": "2026-06-15T10:00:00.000Z",
  "reason": "Bob harassment incident #4711"
}
```

Reducer projection 的 `observed_dot_ids[]` MUST 逐字等于 payload 的 `observed_dot_ids[]`；缺失、额外、重复或排序后集合不等都 MUST `schema_violation` / `reducer_projection_failed` 拒绝。这样 schema validation、审计 projection 与 lattice reducer 看到的是同一个撤销集合。

**Regrant**：撤销后 holder 可以再次发出 `ak.consent.grant` Event；新 Event 产生新的 `dot`（来自不同 `event_id`），不在任何先前 `observed_dot_ids` 中，effective consent 重新 active。Regrant 是 normative 支持的行为。

**完整撤销 vs 部分撤销**：撤销整个 (consent_id, peer, consent_scope) intent 需要 client 在构造 revoke Control Move 前先查询当前 cell 的 已确认安全集合，列出该 intent 下所有 active dot。Missing 一些 dot 是合法操作，但只构成部分撤销，剩余 dot 仍然 active——admin / UI MUST 把这种状态明确提示为 "partial revoke"。

撤销在该revoke Control Move被accepted Seal覆盖后立即生效；此前凭Consent发出的invite或其它非Contact action不追溯失效。Contact事实不读取本cell。

## 4. Scope 枚举

| Scope | 语义 |
| --- | --- |
| `invite` | peer 可发送 Realm / Strand invite |
| `voice_call` | peer 可发起 WebRTC 语音通话 |
| `video_call` | peer 可发起 WebRTC 视频通话 |
| `presence` | peer 可观察 holder presence |
| `any` | 全部 scope（覆盖所有上述类型）|

`consent_scope=any` 是宽授权 dot：在查询任一具体 scope 时，它与该具体 scope 的 active dot 都可独立满足 gate；它**不等价于**在 lattice 中隐式生成全部具体 scope dot。撤销永远只移除 `observed_dot_ids[]` 显式列出的 dot；要完全撤销同一 `(consent_id, peer)` 的全部授权，客户端必须按 §4.1.1 枚举全部 active dot。

`consent_scope=invite`(或 `any`)的 active grant dot 可作为 Realm 邀请的高信任引入证据:邀请者出示该 grant 的 `consent_grant_ref`,接收方按 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) §2 的 `consent_grant` evidence 校验。撤销该 dot 后,§4.1.2 的 invite gate cache 失效，后续以该 dot 为证据的 invite delivery MUST 在接收方降级为低信任 `explicit_address`。这条不改变 consent lattice 语义，只说明 grant dot 的对外引用用途。

### 4.1 Scope 撤销级联 与 缓存失效（normative）

`ak.consent.revoke` 的 scope 语义与缓存失效规则：

#### 4.1.1 Scope 级联

- **按 `consent_id` 全量撤销**（推荐路径）：revoke Control Move 的 `observed_dot_ids` 列出 cell 当前 `(consent_id, peer, *)` 下所有 active dot，无论原 grant 的 scope 是 `any` 还是具体 consent_scope。这是显式"完全 revoke 该 consent_id"操作。
- **按 scope 部分撤销**：revoke Control Move 仅列出某具体 consent_scope 对应的 active dot。剩余 consent_scope 的 dot 保持 active。
- **`consent_scope="any"` 与具体 consent_scope 互斥语义**：
  - 撤销一条 `consent_scope=any` 的 grant dot MUST 显式枚举该 `(consent_id, peer)` 下当前 active 的 **所有** consent_scope dot（含具体 consent_scope 的 grant dot）。即 `any` revoke 的 cascade 由 payload 中完整的 `observed_dot_ids[]` 表达；reducer MUST NOT 基于一个 `consent_scope=any` dot 隐式推断并移除未枚举的其他 dot。若 active dot 未被枚举，effective consent 只构成部分撤销，admin / UI MUST 标 `partial_revoke`。
  - 反向不成立：撤销一条 `consent_scope=invite` 的具体 consent_scope dot 仅清空 `invite`，不影响同 `(consent_id, peer)` 下 `consent_scope=any` 的 dot——因为 `any` 是 holder 显式更宽授权，需要 holder 再单独撤销 `any` 才算 cascade。
  - 这条非对称规则 MUST 在 admin / UI 中明示，避免用户误以为"撤销 invite 就等于全撤销"。
- **conformance vector** `ak.vector.consent.scope_cascade.v1` 覆盖 (a) `any` revoke cascade 到具体 consent_scope；(b) 具体 consent_scope revoke 不影响 `any`；(c) 部分 scope revoke 留下其他 scope active；(d) 完整 revoke 必须列出当前 cell 全部 active dot 否则只构成部分 revoke。

#### 4.1.1.1 UI / admin 展示要求

发起 revoke 前，客户端 / admin MUST 展示将被写入 `observed_dot_ids[]` 的实际 dot 清单及其 consent_scope 分组，并明确标注本次操作是 full revoke 还是 partial revoke。若用户选择“撤销 invite”但同一 `(consent_id, peer)` 下仍存在 `consent_scope=any` 或其它具体 consent_scope 的 active dot，UI MUST 在确认前提示这些 dot 将继续授权对应能力；不得用一个泛化按钮文案暗示未枚举的 scope 会被隐式撤销。

#### 4.1.2 缓存失效（normative MUST）

consent revoke 被 accepted Seal 覆盖后，下列下游缓存 MUST eager invalidate（同一事务边界内）：

| 缓存 | 失效粒度 | 触发动作 |
| --- | --- | --- |
| Private contact discovery PSI 结果 / invite handoff cache | 按 `(holder_account_id, JCS(peer))` 失效，下次查询走完整 consent 重判 | 不返回 stale PSI match 或 invite handoff，防止 peer 看到已撤销的"可联系"指示。 |
| MIMI consent check cache（interop 模块） | 按 `(holder_account_id, JCS(peer.actor_id), scope)` 失效；`any` revoke 失效全部 scope | interop bridge 下次跨协议解析 MUST 重新校验；MIMI reporter authority 的 exact ActorId 必须逐字等于 `peer.actor_id`，同 core 异 Station或异角色不命中。 |
| Push / contact discovery 缓存（含 PSI 结果） | 按 `(holder_account_id, JCS(peer))` 失效；PSI 索引 MUST 在下次轮转时排除 revoked peer | 即使 cache TTL 未到，revoke 后下一次 contact sync MUST 反映新状态。 |
| Invite admission gate cache（§6.1 invite 前置 gate） | 按 `(holder_account_id, JCS(peer), scope)` 失效 | 即便已缓存"该 peer 有 active consent"，revoke 后下一次 invite MUST 在提交目标 Realm Control Move 前重判；旧 cache MUST NOT 让 facade / invite service 放行。 |
| In-flight invite 与 DM Realm | **不**追溯 — 已发出的 invite / 已创建的 DM Realm 不自动撤销（与 §3.3 撤销 Seal 覆盖前不追溯的规则一致）；如需撤销，单独发 `ak.invite.revoke` / member remove。 | 不自动级联撤销已生效邀请或 DM Realm。 |

`consent_scope="any"` 被撤销后 cascade 失效规则：上面 5 类缓存中所有 consent_scope 的 entry 必须一起失效，包括 `invite`、`voice_call`、`video_call`、`presence`。不允许实现把 `any` revoke 只清单一 scope。

`ak.vector.consent.cache_invalidation.v1` 覆盖 (a) revoke 后 private contact discovery / invite handoff 立即不返回该 peer；(b) revoke 后下一次 invite 在目标 Realm Control Move 提交前被 admission gate 拒绝（capability gate 重判）；(c) `any` revoke cascade 失效所有 consent_scope cache；(d) revoke 后 PSI 索引在下一次轮转时排除该 peer。

## 5. Cell Join 与 Effective Consent

Consent cell 是 sequenced_state 安全状态，值为 dot-based observed-remove 集合（详见 [`event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)）。Effective consent 由当前 confirmed Seal state 中按确认顺序逐项应用集合增删所得状态派生：

- `active_dots(cell) = { (entry.tag_id, entry.value) | entry ∈ cell.state.value }`
- `effective_grants(cell) = group active_dots(cell) by value.intent` —— projection 把同 intent 的多 active dot 折叠成一条 effective consent。
- 一个`(consent_id,peer,concrete_scope)`的grant当前生效（即invite/非Contact action gate放行）当且仅当：
  - `active_dots(cell)` 中存在 ≥1 条 `value.intent == (consent_id, peer, concrete_scope)` **或** `value.intent == (consent_id, peer, "any")` 的 dot；
  - 当前时间 ∈ `[not_before, expires_at]`（窗口字段缺省视为 `(-∞, +∞)`）。
- 不同 consent ID 是独立 cell；查询 `(holder_account_id,JCS(peer),scope)` 时只有 invite / 非 Contact action service 遍历 holder cells 匹配，完整 identity tuple 任一分量不同都不命中。
- grant 与 revoke 在 Realm 安全序列中执行，每条命令验证实际相关 revision；先前状态变化使旧命令拒绝。审计保留成功与拒绝 outcome，invite gate 只使用当前已确认活跃集合，不合并竞争权限。

物化 `Consent` 对象由 holder client / admin 从该 cell 当前 join 值生成；它不是协议授权根，而是 UX / 审计辅助视图。Consent 没有 canonical-object schema：cell 的写入 payload 由 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的 `ak.consent.grant` / `ak.consent.revoke` 绑定，投影形态由 [`consent-operations.schema.json#/$defs/consent_cell_view`](../../artifacts/schemas/consent-operations.schema.json) 固定；本文只定义语义。

## 6. 与 Invite / Contact 流程的整合

### 6.1 Invite 前置 gate

Peer 发送 invite Control Move 时，consent gate 在 **holder 的 Station** 于 invite delivery admission（[`../sync/invite-addressing.md` §7](../sync/invite-addressing.md) 第 8 步；同 Station 本地分支从第 4 步起执行同一套验证）查询 holder 的 consent cell。**Contact delivery 不在本 gate 内**：Contact request / response、Contact-based create/send 与 Personal DM 按 [`contact-and-direct-conversation.md` §1](./contact-and-direct-conversation.md) 与 [`../sync/service-http-binding.md`](../sync/service-http-binding.md) 的 `POST /_arkret/self/contacts/request` 行**不读写 Consent**，只读双方 holder-signed directional Contact heads；它们仍受 §6.1.1 的 new-source quota 计费，但那是反滥用面，不是 consent gate（见 §6.1.1.3）。Consent cell 位于 holder PCR，而目标 invite Move 位于目标 Realm；因此该检查是**跨 Realm operation admission gate**，不是 CBS `preconditions[]`。CBS precondition 只能引用并求值同一目标 Realm 的 cell；producer、facade 与 reducer MUST NOT 把 holder PCR cell id、跨 Realm state root 或 consent query result 塞进目标 Move 的 `preconditions[]`，目标 Realm reducer也不得读取 holder PCR 当前态作为本 Realm reducer 输入。邀请方 Station / facade 在提交目标 Realm Control Move 前 MAY 预检 consent，但只能基于同一受信服务边界内已验证的 holder PCR view，或 holder 主动披露的 §2.1 / §6.2.2 audience-bound green-light；跨 Station 时 MUST NOT 读取 holder consent cell（§6.1.2），且「没有 active grant」MUST NOT 被转换为 inviter 客户端可见的 `failed_precondition` 或任何可区分错误——self dispatch 面的 `failed_precondition` 子理由封闭为 `invite_event_unaccepted` / `invite_event_actor_mismatch` 两条（[`../sync/invite-addressing.md` §7](../sync/invite-addressing.md)）。查询强度按 holder 选择的 **consent profile** 分两档。profile 的唯一 carrier 是 subject 私有 `ak.schema.invite_receive_policy.v1` 的 `consent_profile` 字段（`default | require_explicit_consent`，省略即 `default`，见 [`../sync/invite-addressing.md` §5](../sync/invite-addressing.md)）：它不经 `ServiceDescribe` 广告，MUST NOT 被 requester 或 peer Station 观察；与 Realm 级 `preauth.consent_required` 是两个独立维度，后者只强制本 gate 对该 Realm 全部 invite 执行，不选择也不覆盖 holder 的 profile。（与 §4.1.2 invite gate cache 的 revoke 后 MUST 重判咬合：被 eager invalidate 的 cache 在下一次 invite 时，`require_explicit_consent` profile 下 MUST 走完整重判，旧 cache MUST NOT 让 holder Station 放行）：

- **`require_explicit_consent` profile**：holder Station **MUST** 查询 holder consent cell；只有已验证的 `consent_grant` introduction evidence（exact holder 给 inviter 的 active `invite` / `any` grant dot）可以通知 holder，其余一律按 §6.1 step 2 静默丢弃（consent gate 强制，但属于 operation admission，不是 Event/CBS precondition）。
- **default profile**：holder Station **SHOULD** 查询；无 active grant 时 MAY 进入 holder quarantine inbox（见 §6.1 step 2 与下述 quarantine inbox 定义）,而非直接拒绝或放行。

查询步骤：

1. 调用 holder 的 principal control Realm（或受托 contact discovery service）查询所有候选 consent cell（subject 由 holder consent 命名约定决定），跑 已确认安全集合 后筛选 `value.intent` 匹配 `(peer=requester, scope="invite" OR consent_scope="any")` 当前 active 的 dot 集合。
   **`peer=requester` 是分类型精确匹配，跨 kind 永不匹配（normative）**：
   - 已认证对端是普通 Account / Agent / pseudonymous Account / service Actor 时，**只**与 `{kind:"actor"}` entry 按**完整 ActorId**（含 Station 与 role）比较，MUST NOT 降维到 principal core；
   - 已认证对端是 Realm-local ephemeral pairwise actor 时，**只**与 `{kind:"pairwise_principal"}` entry 按 `(realm_id, principal_id)` 比较，且该 actor MUST 是 `realm_id` 所指 Realm **当前** active LeafNode 所投影的 actor；
   - 两类 entry 之间 MUST NOT 互相命中。把 peer 折叠成裸 `DidCoreId` 再比较（无论哪一侧）MUST 视为不合规：它同时制造「异 Station / 异角色 Actor 被当作同一 peer」与「pairwise 值冒充普通 Account」两条越权路径。
   **隔离键（normative）**：pairwise peer 按 `(realm_id, principal_id)` 隔离，**不聚合**。同一 `principal_id` 出现在不同 Realm 时是不同 peer；这与 [`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md) 中「客户端把已绑定另一 Realm 的同一 pairwise key / ActorId 用于本 Realm：本地拒绝」一致，consent cell MUST NOT 替这种违规兜底聚合。§8.1 的 holder-side 聚合 revoke 仍只是本地组织能力，不进入 wire 语义。
2. 若没有匹配的活跃 grant：
   - **`require_explicit_consent` profile**：holder Station MUST 静默丢弃该 delivery——不写 quarantine cell、不计 §6.1.1 新来源 ledger、不写任何 holder-private cell、不通知；对 requester 返回与 §6.1.1 五元等价类**逐字节相同**的 opaque `status="deferred"` 且不携带 `disclosed_outcome`，无论 evidence 信任档与 `invite_receive_policy.disclosure` / `disclosure_max` 取值（该情形是等价类中「holder policy deny」成员，profile 本身不可观察）。MUST NOT 返回 `failed_precondition` 或任何可区分错误码，也不得创建一个随后等待目标 reducer 读取 holder PCR 的 pending Move。Peer 只能在 holder 主动授权（holder 自行构造 §3.2 grant，或经 `ak.private_contact_discovery.v1` 等 holder 主导机制）后重试。
   - **default profile**：invite MAY 进入 holder 的 quarantine inbox（"陌生人邀请"），由 holder 在 UI 上 review 后构造 grant Control Move 或丢弃。
3. 若有匹配活跃 grant 且当前时间在 `[not_before, expires_at]`：facade / invite service 才可提交目标 Realm invite Control Move；该 Move 随后只按目标 Realm 自身的 schema、capability、CBS basis 与 Seal 规则 accepted。

跨服务查询结果 MUST 由 holder PCR 的权威服务签名，或由 facade 在同一受信服务边界内直接从已验证 holder PCR view 求值；结果至少绑定 holder、requester、concrete scope、holder PCR frontier / Seal ref 与有效期。它是短期 admission evidence，不进入目标 Event canonical bytes，也不成为目标 Realm state root 的叶子。`ak.realm.policy_bundle` 的 `preauth.consent_required=true` 对该 Realm 的所有 invite 强制执行上述 admission gate；它 MUST NOT 被解释为允许跨 Realm CBS precondition，也不选择或覆盖 holder 的 `consent_profile`。

#### 6.1.1 Quarantine inbox（default profile no-consent invite 暂存）

§3.1 缺省判定与 §6.1 step 2 提到的 **quarantine inbox** 是 default profile 下"无 active consent 的 invite"既不直接拒绝、也不直接放行的暂存区，其最小定义如下：

- **承载位置**：quarantine inbox 不是独立对象类型，而是 holder 的 Station CAS account-data cell（key `ak.account.holder_quarantine`，plaintext value 符合 `ak.schema.holder_quarantine.v1`，机读真源 [`holder-quarantine.schema.json`](../../artifacts/schemas/holder-quarantine.schema.json)）。权威 register 通过 account subscribe 顶层 `account_data.station_cas` 的 complete baseline 与 cursor-covered upsert/remove 持续投影；`ak.self.account_data.read.list.v1` / `.resource.get.v1` 是诊断与定点恢复面，`to_device.messages[]` 中的 `ak.account_data.update` 只是低延迟加速。该 CAS-only cell **不会**出现在 `delta.account_data.events[]`，也不得被合成为 authorless 或 service-authored `ak.account_data.set` Event。每条暂存项记录待 review 的引用，**MUST NOT** 物化为已接受的 membership 或 DM Realm——它只是"待人工决策"的指针，不构成任何授权。`quarantine_entries[]` 的成员资格本身固定表达 pending-review；entry 不携 `status="pending_review"`，离开该状态即从数组删除。
- **两个封闭分支（normative）**：entry 携带封闭判别器 `surface_kind ∈ {invite_delivery, consent_request}`，未登记取值 fail closed。公共字段为 `entry_digest` / `account_id` / `source_peer_principal_id` / `source_id` / `surface_kind` / `consent_scope` / `received_at` / `expires_at`；分支私有字段各自闭合：
  - `invite_delivery`：MUST 携带 `introduction_kind` / `effective_kind` / `trust_tier` / `invite_event_id` / `request_digest` / `idempotency_key_digest`，且 `consent_scope` 固定为 `invite`。该分支的约束与判别器引入之前逐字相同，不因此放松任何一项。
  - `consent_request`：**不携带任何 Event ref**——§6.1.2 的请求根本不产生 Event。上述六个字段在该分支 **MUST NOT** 出现：consent request 没有 introduction evidence，填任何值都是伪造；而 `ak.self.consent.command.request.v1` 是 `idempotency_mechanism="none"` / `retry_safe=false` / `durable_effect.kind=none`，body 只有 `holder_account_id` 与 `consent_scope`（闭合），两个 digest 在该分支**无源可取**。`consent_scope` 取 §4 枚举**去掉 `invite`**：scope 为 invite 的请求本来就该走 invite delivery。
  - **不为 `consent_request` 新增第三个 digest**。它的去重键是 holder 本地的 **live-entry 唯一性**：`(account_id, source_peer_principal_id, consent_scope)` 上同时至多一条非终态 entry。live 期间的重复请求是 no-op、不计 §6.1.1 quota；entry 终结（holder 接受 / 丢弃 / `expires_at` 到达）之后的同 tuple 请求是一条新 entry。wire 上不存在任何能区分"合法重复"与"replay"的信息（body 无 nonce、无时间戳），因此只能用 live 唯一性定义去重，不得用一个凭空构造的 digest 假装有。
- **Contact delivery 不是本 cell 的分支（normative）**：Contact 有自己的正文真源与自己的待审状态——`pending_incoming` 本身就是"有人等我回应"的 holder 待审面，由 Contact 状态机独占。给本 cell 加一个 Contact 分支等于给 Contact 造第二个平行待审 carrier，会与该状态机争夺同一事实。因此 `POST /_arkret/self/contacts/request` 形成 `pending_outgoing` / `pending_incoming` 而 holder quarantine 无 entry 是**正确行为**，不是缺陷。Contact 侧仍受同一条 new-source quota 计费，落点见 [`contact-and-direct-conversation.md` §1.1](./contact-and-direct-conversation.md)。
- **生命周期与 TTL**：暂存项停留在 `pending_review` 直到 holder 在 UI review;实现 SHOULD 为暂存项设置 deployment-policy 声明的 TTL（缺省建议 30 天）,超时后 MUST 按"丢弃"处理（等价 holder 未授权，不得自动转 grant）。
- **review 后转换**：holder review 后只有两种终态——(a) **接受** → holder 构造 §3.2 `ak.consent.grant` Control Move 写入 consent cell（此后该 peer 走正常 active-grant 路径）;(b) **丢弃** → 删除暂存项，不产生任何 consent dot；TTL 超时等价于丢弃。review 动作本身不绕过 consent cell:授权始终经 grant Control Move 落入 consent cell,quarantine inbox 永远不是授权根。**接受后是否还有"原对象"要处理，按 `surface_kind` 分叉（normative）**：`invite_delivery` 分支 holder **MAY** 另行接受原 invite（grant 不等于入群）；`consent_request` 分支**到此为止**——它没有任何待接受的原对象，requester 需自己在拿到 active grant 后走正常路径重试。这一条必须明写，否则实现会去猜有没有一个隐藏的待接受对象。
- **profile 边界**：quarantine inbox 仅在 default profile 生效；`require_explicit_consent` profile 下无 active grant 的 invite 按 §6.1 step 2 在 holder Station 静默丢弃，不进入 quarantine inbox、不计本节新来源 quota，requester 仍只观察到本节等价类的同一 opaque `deferred`。
- **不向 requester 暴露可联系信号（normative）**：invite 进入 quarantine inbox 暂存(§3.1 缺省判定的"非拒绝、非放行")**MUST NOT** 被对 requester 暴露为送达 / 可联系信号。quarantine 期间(暂存项处于 `pending_review`,以及超时丢弃后)服务端与客户端 **MUST NOT** 向 requester 返回任何 deliver / seen / read receipt / presence / typing / "已送达" / "可联系" 等指示，亦不得通过响应码、时序或副作用让 requester 区分下列五种情形。

  **不可区分等价类（normative，封闭列举）**：`{已进入 quarantine inbox（`pending_review`）, 本节反滥用限速导致的静默丢弃, TTL 超时丢弃, holder 不存在, holder policy deny}` 五种情形 MUST 返回**逐字节相同**的响应体与状态码，并落在同一 timing bucket。任何一项与其余四项可区分，都等价于回答了"holder 是否对该 requester 持有 active invite grant"。

  **wire 落点（normative）**：在 peer invite delivery 与 contact delivery 面上，该等价类的 wire 形态固定为 `status="deferred"` 且**不携带** `disclosed_outcome`；`disclosed_outcome` 的枚举因此封闭为 `delivered | blocked`，`quarantined` 不是可回送值。详见 [`../sync/invite-addressing.md` §5.1](../sync/invite-addressing.md)。高信任 introduction evidence（`locator_ref` / `consent_grant` / `shared_realm`）**不构成**放宽理由：它只说明 requester 已知 holder 存在，而这里泄露的是 consent 状态而非 existence。

  requester 只有在 holder 显式 review 接受并构造 grant Control Move(本节 review 后转换 (a))后，才 MAY 从正常 active-grant 路径观察到可联系状态。否则 quarantine 暂存本身会成为"holder 真实存在且 inbox 可达"的可联系侧信道，违背 consent gate 的"非授权即不可联系"语义。
- **反滥用限速（normative）**：为闭合"换一个 principal 即重新入列"的骚扰放大面，服务端对**新来源**（此前未见过的 peer，identity key 由 §6.1.1.2 唯一定义）向同一 holder 的首次接触 MUST 施加 per-holder 速率与总量上限。**范围是 §6.1.1.3 chokepoint 上的三条 first-contact 面**——invite delivery、contact delivery 与 §6.1.2 consent request——**不是"写入 quarantine inbox 的项"**：contact 首次接触照常计费却从不产生 quarantine entry（[`contact-and-direct-conversation.md` §1.1](./contact-and-direct-conversation.md)），按 carrier 划范围会把它整条漏掉。承载、identity key、算法、ledger 与原子性由 §6.1.1.1–§6.1.1.4 唯一定义；超过上限的新来源接触 MUST 被静默丢弃——**被丢弃的是本面的 carrier 写入**（invite delivery 与 consent request 是 quarantine entry，contact delivery 是 `pending_incoming` row 的建立，见 §6.1.1.3），且不向 requester 暴露任何送达 / 可联系信号（遵守上一条不可区分要求）。该限速仅针对"陌生人首次接触"；已被 holder grant 过、走正常 active-grant 路径的 peer 结构上不进入本节的陌生人首次接触路径，因而不受此限。

##### 6.1.1.1 Quota carrier 与 effective 值（normative）

- **deployment 侧**：阈值只由 [`../sync/invite-addressing.md` §5.2](../sync/invite-addressing.md) 的
  `receive_policy_constraints.new_source_quota` 声明（closed object，字段与缺省见该节表）。它经既有
  `$ref` 自动进入 `ServiceDescribe`，广告边界与 PSI quota 广告同构。部署**省略该对象或其中任一字段
  ≠ 关闭 quota**：本节是 MUST，省略即取 spec 缺省值；"关闭"不可表达。服务端 MUST NOT 用通用 endpoint
  限速、Directory PSI device quota 或私有配置替代该 carrier。
- **holder 侧**：subject 私有 `ak.schema.invite_receive_policy.v1` 的 optional closed
  `new_source_quota` 携带 `new_sources_per_window` / `new_sources_per_retention`（integer ≥ 0）。
- **effective 值**：`E_w = min(subject.new_sources_per_window ?? default_new_sources_per_window,
  max_new_sources_per_window)`；`E_r = min(subject.new_sources_per_retention ??
  default_new_sources_per_retention, max_new_sources_per_retention)`。subject 值 `0` 合法，表示 holder
  锁死新来源、全部静默丢弃。放宽边界唯一由部署 `max_*` 给出：这既是"holder MAY 在 UI 显式放宽"的
  上界，也保持 `receive_policy_constraints` 既有"约束只能让 subject 更不可达"的合同。
- **MUST 不变式**（validator 强制，schema 无法表达跨字段比较）：`max_new_sources_per_window ≥
  default_new_sources_per_window`；`max_new_sources_per_retention ≥
  default_new_sources_per_retention`；`retention_seconds ≥ window_seconds`；部署侧全部字段 ≥ 1。
  违反 MUST 以 `schema_violation` 拒绝该 constraints 对象，不得取部分字段继续求值。
  SHOULD：`*_per_retention ≥ *_per_window`。
- **`applies_to` MUST NOT 筛选该对象（normative）**：`receive_policy_constraints.applies_to` 只筛选同一
  constraints 对象里的 introduction-evidence 与分级披露类成员。`new_source_quota` 是 §6.1.1.3 holder
  admission chokepoint 的阈值，三条面共用同一份 ledger 与同一组阈值，因此无论 `applies_to` 取何值
  （含只写 `["invite_delivery"]`、只写 `["contact_request"]`，或整个省略），本对象都对三条面**无条件生效**。
  把它按面筛选会让同一份 ledger 出现两组阈值，与本节 §6.1.1.3 直接矛盾。`applies_to` 的封闭枚举也因此
  **不**为 consent request 面新增取值：该面按 §6.1.2 不携带 `introduction_kind` / `effective_kind` /
  `trust_tier`，也不参与 [`../sync/invite-addressing.md` §5.1](../sync/invite-addressing.md) 的分级披露，
  其余成员在该面上没有可筛选的对象。

##### 6.1.1.2 "新来源"的 identity key（normative）

新来源的 identity key 是 `(holder 完整 AccountId, source_peer_principal_id)`。
`source_peer_principal_id` 在 invite 路径取已验证 invite Event 的完整 inviter ActorId 的 principal
分量，在 §6.1.2 路径取认证上下文的 peer principal。**对端是 Realm-local ephemeral pairwise actor 时，
该 identity key 的 peer 分量 MUST 是 `(realm_id, principal_id)`**，与 §6.1 查询步骤 1 的隔离键一致；
只取 `principal_id` 会把两个 Realm 的不同 peer 并进同一条 quota 账，取完整 ActorId 又会引入该 actor
身份键里本不存在的 Station 维度。quarantine entry 的 `source_id` 是已认证
transport source service DID（见 [`../sync/invite-addressing.md` §5](../sync/invite-addressing.md)），
它 **MUST NOT** 参与 quota identity：按 Station 计费会一站连坐，也可被换站绕过。holder 维度使用完整
AccountId，同 principal core 异 Station 是不同 holder。

##### 6.1.1.3 判定算法（normative）

quota 判定发生在 **holder admission 唯一 chokepoint**——三条陌生人首次接触面（invite delivery、
contact delivery 与 §6.1.2 consent request）全部汇聚于此，在任何 holder-visible 待审状态写入**之前**
恰好执行一次。三条面共用同一份 ledger 与同一组阈值；**超限时被丢弃的对象各不相同**：invite delivery 与
consent request 丢弃的是 holder quarantine entry 的写入，contact delivery 丢弃的是 Contact
`pending_incoming` row 的建立（见 [`contact-and-direct-conversation.md` §1.1](./contact-and-direct-conversation.md)）。
只有前两条会产生 quarantine entry；contact 永远不产生（理由见 §6.1.1 的 carrier 分支条）。判定步骤：

1. **prune**：忽略并删除 ledger 中 `first_admitted_at ≤ now − retention_seconds` 的条目。
2. **seen**：source 在 prune 后 ledger 中存在 → 非新来源，直接进入本面的 carrier 写入（invite delivery 与
   consent request 是 quarantine cell 写，contact delivery 是 `pending_incoming` head 写）；MUST NOT 写 ledger，也
   MUST NOT 刷新其 `first_admitted_at`（刷新会让活跃骚扰源永久保鲜）。
3. **new**：令 `rate = |{first_admitted_at > now − window_seconds}|`、`total = |ledger|`。
   `rate ≥ E_w` **或** `total ≥ E_r` → 静默丢弃：零 ledger 写、零 carrier 写，对外与本节不可区分等价类
   同一 opaque `deferred`。两者均未超时 MUST 原子 append `(source, now)` 后进入本面的 carrier 写入。
4. 被丢弃的 source **MUST NOT** 记入 ledger：既防"上一窗口被拒 → 下一窗口洗白为 seen"的绕过，也使
   攻击者无法用海量被拒 DID 撑大 ledger。

"总量上限"是 **retention 窗内 distinct 新来源上限**，不是终身计数，也不是 pending 条数（后者已由
quarantine cell 的 200 条上限覆盖）。两个窗口都是**滑动窗**，直接由 ledger 时间戳计数，不需要固定窗
轮转状态。与 [`../discovery/discovery-directory.md` §6.4](../discovery/discovery-directory.md) PSI quota
的同构点是"准入原子执行一次、replay 不重复计数"；刻意偏离点是**不缓存 drop outcome、不返回 429 /
`Retry-After`**——PSI 的 outcome 对外可区分才需要缓存，本面对外恒为同一 opaque `deferred`，重评估无
侧信道，缓存只会新增状态。

##### 6.1.1.4 Seen-source ledger 与原子性（normative）

- ledger 是 Station **内部 durable 反滥用状态**：无 wire carrier，不是 account-data cell，任何 wire
  surface（含 holder 面）MUST NOT 可读。holder 的可观察面仍只有 quarantine cell 本身。
- 行内容是 `(holder AccountId, source_peer_principal_id, first_admitted_at)`。holder 列明文建索引；
  source 列 SHOULD 只存 server-private key 的 keyed digest（成员判定只需相等性），降低落库暴露面。
- `retention_seconds` 同时是 ledger 保留期与长窗计数窗。超龄条目在判定时 MUST 立即失效（步骤 1），
  物理删除 MUST 在该 holder 下次 admission 评估或周期清理时完成。prune 后
  `|ledger| ≤ max_new_sources_per_retention`，存储有部署上界。
- holder 账号擦除 MUST 连带删除其整个 ledger。consent revoke 与 `denied_source_ids` /
  `trusted_source_ids` 名单变更 MUST NOT 触碰 ledger：准入反滥用状态与 consent 状态分离。
- audit MAY 记录聚合丢弃计数，SHOULD NOT 持久化被丢弃 source 的可识别 DID。
- prune + membership + 双计数 + append 与准入判定 MUST 按 holder **线性化**。并发新来源首次接触在任何
  交错下 MUST NOT 超额准入；同一 source 的两条并发首次接触恰好计费一次（第二条按 seen 放行）。
- quota 判定 MUST NOT 在 cell 写的 CAS 重试循环内重复执行。重试耗尽的内部静默放弃**不退费**。
- replay 去重**按 `surface_kind` 分叉（normative）**：`invite_delivery` 命中既有 entry 的
  `request_digest` / `idempotency_key_digest` 时判为重复投递；`consent_request` 没有这两个 digest，
  改判 `(account_id, source_peer_principal_id, consent_scope)` 上是否已有 live entry（§6.1.1 carrier
  分支条）。两种形态的后果相同：重复不进入 quota 评估、零新计费、对外仍是同一 opaque outcome。
  contact delivery 的重复判定由 Contact 状态机自身的 directional head 决定，同样零新计费。
  被丢弃请求的重放按当前窗口重新评估。

##### 6.1.1.5 Quarantine cell 写语义（normative）

`ak.account.holder_quarantine` cell 的写语义与 notify 分支的 `ak.account.invite_delivery`
（[`../sync/invite-addressing.md` §7](../sync/invite-addressing.md)）同构：该 cell 是
[`../models/account-data.md` §5](../models/account-data.md) 的 server-versioned CAS whole-value
register。每次写入 MUST 先清除 `expires_at ≤ now` 的过期 entry，再按 `entry_digest` 去重，随后 append
新 entry；结果超过 200 条上限时 MUST 从 `received_at` 最旧的 entry 起逐出。CAS 冲突时写入方 MUST 重读
当前值、按本节规则重新合并后重试，重试 MUST 有界（至多 3 次），并保持 oldest-first 顺序与
`updated_at` 单调。重试耗尽 MUST 以内部失败放弃本次写入并 audit，MUST NOT 以 stale revision 强行覆盖；
对外仍返回同一 opaque `deferred`。两个 `surface_kind` 分支共用这一套写语义：`entry_digest` 去重、200 条上限、
oldest-first 逐出、`updated_at` 单调、有界 CAS 重试均不分支。

#### 6.1.2 `ak.self.consent.command.request.v1`（normative）

该 self-surface operation 只把 authenticated actor 的请求提交给上述 quarantine/anti-abuse pipeline；它**不**创建 consent grant dot、pending consent state 或 contact fact。peer 的完整 ActorId 只取认证上下文，不由 request body 携带；body 的 `holder_account_id` 是跨 Station target，必须按完整 AccountId 参与路由、限速与 anti-enumeration key。

服务端对 holder 不存在、holder policy deny、per-holder 限速、静默丢弃与成功进入 quarantine MUST 返回完全相同的 `consent_request_outcome {accepted_for_processing:true}`，并 SHOULD 做统一时序填充。响应 MUST NOT 包含 cell id、state、dots、expiry、request timestamp、account-existence flag 或可关联 queue id。**该 operation 不是空壳（normative）**：请求通过 §6.1.1 chokepoint 后 MUST 写入 holder quarantine 的一条 `surface_kind="consent_request"` entry，其 `consent_scope` 取 body 的值（§4 枚举去掉 `invite`），`source_peer_principal_id` 取认证上下文的 peer principal，且 **MUST NOT** 携带 `introduction_kind` / `effective_kind` / `trust_tier` / `invite_event_id` / `request_digest` / `idempotency_key_digest`。去重按 §6.1.1 的 live-entry 唯一性：`(account_id, source_peer_principal_id, consent_scope)` 上已有非终态 entry 时本次请求是 no-op、不计 quota，对外仍是同一 opaque outcome。**request body 的 `consent_scope` 取 §4 枚举去掉 `invite`**（[`consent-operations.schema.json#/$defs/consent_request_request_body`](../../artifacts/schemas/consent-operations.schema.json)）：invite scope 的请求在本 operation 上没有 carrier——它只能变成一条 `surface_kind="consent_request"` 的 entry，而该分支按定义不接受 `invite`。在请求边界就以 `schema_violation` 拒绝，服务端因而不需要为一个存不下的 scope 发明行为；真正的 invite 走 invite delivery 面。写入 quarantine 时必须执行 §6.1.1 的总量/速率上限；`require_explicit_consent` profile 下请求被静默丢弃、不写 entry、不计 ledger，仍返回相同 opaque outcome。

完整 consent cell 查询 `ak.self.consent.read.list.v1` / `.resource.get` 仅允许 holder 或 holder 明确授权的 controller 调用。Peer MUST NOT 读取 consent cell、grant/revoked dots、expiry 或 request history；peer 若获 holder 主动披露，只能消费 §2.1/§6.2.2 定义的 audience-bound 短期 opaque green-light。

**UX 提示（normative for client implementations）**: 撤销 consent 后，客户端 UI MUST 明确披露两点语义：已发出的 invite 不会因 consent revoke 自动失效；如需撤销已发出的 invite，必须单独执行 `ak.invite.revoke`。该提示是非追溯语义的 UX 配套，服务端不强制（consent revoke 不会自动 cascade 到 invite）。

### 6.2 非 Contact action gate 与 Contact 排除边界

对不以 Contact 为授权依据发起的WebRTC call、presence subscription或未来显式注册的一次性动作，发起方可preflight目标Consent，但接收侧仍须在fanout/响铃/presence/media token前重验holder-private current consent。缺active consent时fail closed/quarantine。该规则不授权创建或发送Contact-based DM。

WebRTC `ak.call.signal{signal_kind=invite}` 在服务端投递与目标客户端展示前都 MUST 校验 `voice_call` / `video_call` consent；无 consent 的 invite MUST 被丢弃或进入 profile 声明的 quarantine，且不得产生 VoIP push / ringing UI。Presence subscription / fanout 由 Station sync surface 在每次订阅建立和每次 fanout 前校验 holder 对 observer 的 `presence` consent；无 consent 时不得泄露在线、离线、last active bucket 或订阅是否存在。

`ak.self.direct_conversation.read.resolve.v1`与§5.4的DM founding admission均不得查询Consent。普通分支只验证双方current directional Contact heads与source freshness；owned-Agent分支验证immutable controller/provision/runtime binding。无权主体统一opaque unavailable。其它基于Consent的一次性通信若未来需要，必须另行注册operation/profile，不得复用resolver或伪造Contact。

`ak.private_contact_discovery.v1` 返回 PSI set-membership 命中位图时，MAY 附带 holder 当前 consent state hash 或最小 invite/consent handoff stub（不暴露具体 consent 内容，只声明 grant/revoke 状态与下一步引导），让发起方在尝试联系前判断是否需要先请求 consent。该响应 MUST NOT 包含 contact request handoff token、reachability proof、handle verified claim、组织成员资格、Realm membership 或读取权限。

#### 6.2.1 PSI 命中位时序侧信道（normative）

contact discovery / PSI 端点 MUST 按 `(requester, holder)` 维度限速，防止请求方通过高频探测观测 holder 命中 bit 的翻转时刻（grant/revoke 时点）形成时序侧信道。命中位图 MUST 引入粗粒度时间 bucket（类似 presence `last_active_at` 的 bucket 化），使命中状态变化只在 bucket 边界对外可见，而非实时反映 holder 决策的精确时刻。此外，PSI 探测 MUST 纳入 holder 可审计的访问记录，使 holder 可事后发现针对自己的反复探测。

#### 6.2.2 Consent state hash 侧信道（normative，MUST 加盐或改 opaque token）

裸 consent state hash（例如对 `(consent_id, peer, scope, granted/revoked)` 直接 SHA-256）是低熵、跨 requester 稳定的值——任意请求方可离线枚举有限的 consent 取值组合反查 holder 的真实 consent 状态，或跨多次/多 requester 比对 hash 是否相同来关联 holder 对不同 peer 的决策。因此当响应携带 consent state hash 时，该 hash MUST 满足以下之一，否则 MUST NOT 暴露：

- **加盐**：hash 输入 MUST 混入 per-requester salt 或 per-session salt（例如 `HMAC(key = per_session_salt, data = canonical_consent_state)`，salt 至少 128-bit 随机、每个 requester / session 不同且不可由请求方预测），使同一 consent 状态对不同 requester / session 产生不同、不可反查、不可跨 requester 关联的值；裸的、跨 requester 稳定的 consent state hash MUST NOT 出现在 wire 上。
- **或改为 holder-authorized opaque token**：用一个由 holder（或受托 contact discovery service）签发的、不透明、短期、单 audience 的 token 代替 hash，token 本身不泄露 consent 内容，只在该 requester 的下一步引导中被当作 grant/revoke 状态指示；token MUST 绑定 audience 与过期时间。

实现 MUST NOT 把同一裸 hash 复用于多个 requester；conformance 检查 MUST 覆盖"同一 consent 状态对两个不同 requester / session 产生不同 hash/token"。

## 7. MIMI Interop

MIMI 协议有 `request_consent` / `update_consent` 操作（`ak.open.mimi.command.request_consent.v1` / `ak.open.mimi.command.update_consent.v1`），见 [`extensions/mimi-interop.md`](../extensions/mimi-interop.md) §10。Facade 映射规则：

- 接收 MIMI consent update：facade MUST 先验证私有 request correlation 声明的 holder、Event actor 与认证主体均是该 holder Principal Control Realm 当前 authority-root controller，且 `authorization_ref` 绑定该 authority root；不同主体的 managed-behalf 执行不受支持。facade MUST 把调用方携带的 exact `ak.consent.grant` / `ak.consent.revoke` `EventInitialSubmission` 原样送入普通 Event admission，不得构造、代签或重建该 Control Move。只有 accepted Event 才能写入 holder principal control Realm 的 consent cell。
- 发送 Arkret consent state 到 MIMI：facade MUST 把当前 consent cell 已确认安全集合 值翻译为 MIMI consent message，并保留 consent_id 作为 inter-protocol correlation。
- consent state 不暴露具体 evidence_ref / reason 跨 provider；只暴露最小 `(peer, scope, granted/revoked)` 三元组。

## 8. 隐私与审计

- consent state 是 holder 私有；服务端 MUST NOT 把它暴露给非 holder actor 或非授权 service。
- consent grant / revoke 的 backfill 受 holder principal control Realm 的 history visibility 与 access policy 约束。
- audit projection MAY 记录 consent state 变化（用于合规审查），但 audit access 必须经 holder 授权或 legal hold 边界。
- pseudonymous account 场景下（对端为每段关系另铸一个 principal 并以之开设 Account），consent 绑定的是那个 pseudonymous Account 的完整 ActorId 而非其真实主体，holder 与 reducer 都无从判定两个 pseudonym 是否同一主体——这正是该形态的隐私目标。**该形态走 `{kind:"actor"}` 分支**；`{kind:"pairwise_principal"}` 分支只表示 §3.2 定义的 Realm-local ephemeral pairwise actor，本条 MUST NOT 被读成对该分支的松绑。

### 8.1 Pseudonym consent 的反骚扰局限与聚合 revoke（normative for client UI）

consent 的去重 / 撤销键含 `intent.peer`（见 §3.2 的两个封闭分支）。这带来一个协议层局限：**骚扰者每换一个新 principal 另铸一个 pseudonymous Account 发起联系，就构成一个全新的 `(consent_id, peer)` 入口**——holder 此前对旧 pseudonym 的 `ak.consent.revoke` 不会覆盖新 pseudonym，default profile 下该新 peer 仍可经 §6.1.1 quarantine inbox 暂存，重新出现在 holder 的待 review 列表中。本节讨论的对象是 `{kind:"actor"}` 分支下的 pseudonymous Account，不是 §3.2 的 Realm-local ephemeral pairwise actor（后者脱离其 Realm 不存在，也不能用来向 holder PCR 发起跨 Realm 骚扰）。（本节的 pairwise 反骚扰分析以"quarantine 对 requester 完全不可区分"为前提；该前提由 §6.1.1 的五元等价类与 [`../sync/invite-addressing.md` §5.1](../sync/invite-addressing.md) 的 `deferred` 映射**共同**保证，不是隐含假设。任一侧回送 `quarantined` 都会让本节结论失效。）协议层无法在 wire 上判定两个 pseudonymous Account 是否指向同一真实主体（这正是 pseudonym 的隐私目标），因此**不能**在 consent cell 语义中强制把多个 pseudonym 折叠到同一撤销键。

为收敛该局限，对反骚扰能力作如下要求：

- **聚合 revoke（SHOULD）**：当 holder 客户端能够在本地把多个 pseudonymous Account link 到同一真实主体（例如 holder 本地维护的 contact↔pseudonym 映射，或 holder 显式标注"这些都是同一人"）时，反骚扰 / block UI **SHOULD** 提供"聚合 revoke"：一次操作对该主体名下 holder 已知的全部 `(consent_id, peer)` 入口分别构造 `ak.consent.revoke`，并对后续来自这些已知 pseudonym 的 quarantine 暂存项默认丢弃，而非逐个 peer 手动撤销。该 link 只是 holder-side 本地组织能力，不构成跨 `did_core_id` 身份等价，不进入 consent cell 的 wire 语义，也不要求 holder 向任何 peer 或服务端披露 pseudonym 关联。
- **协议局限披露（SHOULD）**：UI **SHOULD** 向 holder 明示：单条 consent revoke 只对一个 peer 生效；对方更换 principal / 另铸 pseudonymous Account 后可能重新进入 quarantine inbox，聚合 revoke 仅覆盖 holder 客户端**当前已能 link** 的 pseudonym，无法阻止 holder 尚未识别为同一主体的全新 pseudonym。
- **profile 边界**：`require_explicit_consent` profile 下该反骚扰面更小——无 active grant 的 invite（无论换不换 pseudonym）一律按 §6.1 step 2 在 holder Station 静默丢弃（opaque `deferred`）、不进入 quarantine inbox，骚扰者换 pseudonym 也得不到 holder 侧的待 review 入口或任何可联系信号（§6.1.1 不向 requester 暴露可联系信号）。该 profile 因此把 pseudonym 切换骚扰面收敛为"必须先获得 holder 显式 grant 才能产生任何 holder-visible 入口"。

## 9. 与未来 Capability Constraint 的关系

扩展profile MAY引入`consent_required` capability constraint，使非Contact action在Control Move验证时检查holder consent。本cell是其查询源；Contact/Personal DM不得使用该constraint替代directional Contact authority。

请求的 consent_scope MUST 显式携带且无默认值。Personal DM 不查询 Consent，不从缺失 scope 推断 direct_message；MIMI、Contact cascade 与 quota 使用同一保留枚举。
