---
title: Join Policy
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与范围

本文档定义 Realm 的 **Join Policy** 模型，覆盖 gate 组合、自动解析路径、申请-审核路径、加密语义、联邦传播、反滥用与 MIMI 映射。Realm 对象模型与 Space / hierarchy 由 `realm-and-space.md` 定义。

术语层级（normative，消歧）——本文反复出现的四个相近名词分属不同层级，MUST NOT 互换：

| 术语 | 层级 | 说明 |
| --- | --- | --- |
| **Join Policy** | 章节 / 策略域总称 | 本文定义的 gate 组合、解析顺序、加密语义与反滥用约束的统称；不是单一 wire `Event.kind`。 |
| `ak.realm.join_rule` | wire event / cell（active） | `default_join_rule` 入口模式策略事件，写入 `ak.component.realm.join_rule.v1` cell。 |
| `ak.realm.delivery_binding_policy` | wire event / cell（active） | 成员投递绑定策略事件，写入 `ak.component.realm.delivery_binding_policy.v1` cell（见 [`member-delivery-binding.md`](member-delivery-binding.md) §4）；约束成员 `delivery_binding.binding_source`，与 join gate 正交。 |
| `RealmJoinCandidate`（`realm-join-candidate.schema.json`） | Principal Server 转发提示 | invitee 客户端只提交给自己的 Principal Server；该对象描述后者可按 signed invite / 当前 joined-member delivery binding 转交到哪个成员 Principal Server，不产生 ingress authority（见 [`member-delivery-binding.md`](member-delivery-binding.md) §2）。 |

当前 v1 的 active 与 candidate surface 分层如下，base v1 实现只需要实现 active surface；application / review workflow 只在实现声明 `ak.profile.candidate.join_policy.v1` 时成为该实现的自愿承诺。

| Surface | v1 状态 | Wire 形态 | 实现要求 |
| --- | --- | --- | --- |
| `ak.realm.join_rule` | active | 标准 `Event.kind` / reducer cell | base v1 按 registry 和 reducer 规则实现 |
| `ak.realm.policy_bundle` 中的 join policy facet | active | 标准 policy component payload | base v1 可表达 gate、delivery binding policy 与自动解析要求 |
| `ak.member.state{membership=join}` 自动 gate | active | 标准 membership event + `gate_proofs[]` / delivery binding payload | base v1 必须 fail closed 校验 capability、gate proof 与 delivery binding |
| `ak.invite.*` + `refs[role="join_authorised_by"]` | active | 标准 invite / member refs | base v1 支持 invite 或 join-authorized grant 时必须校验引用仍有效 |
| `realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel` | candidate | 裸名 design-time concept；不得作为 `Event.kind` | 仅 `ak.profile.candidate.join_policy.v1` 实现可用 profile-private signed receipt 或私有 Event kind 承载 |

独立 join-policy Event.kind / schema 仍未进入 active registry。任何未声明 `ak.profile.candidate.join_policy.v1` 的实现 MUST 把 application / review workflow 当作未知高风险 surface，返回 `unsupported_feature`、`unsupported_event_kind`、`capability_denied` 或等价 fail-closed 结果；MUST NOT 把未注册裸名 kind 写入 shared Realm history。

**base v1 knock 不得退化为明文 spam 通道（normative）**：申请材料对外不可见（§2 设计原则 2）与 reviewer-only 加密承载（§8）都属于 candidate surface（`ak.profile.candidate.join_policy.v1`）能力；**未声明该 profile 的 base v1 实现没有任何受保护的申请正文承载层**。为避免 base v1 下 `default_join_rule=knock` 退化为 Matrix `m.room.member{knock}.reason` 那样的默认可见明文 spam 通道，base v1（未声明 candidate profile）下的 `ak.member.state{membership="knock"}` Control Move **MUST NOT 携带任何申请正文 / 自由文本 / answers / 3PID / 附件**——该 Control Move 公开，正文一旦携带即对 Realm 可见侧成员暴露并成为 spam 注入面。reducer 在 base v1 收到携带正文字段的 knock Control Move MUST 拒绝（`schema_violation` 或 `unsupported_feature`）。需要结构化申请材料时，实现 MUST 先声明 `ak.profile.candidate.join_policy.v1` 并通过 §8 的 reviewer-only encryption envelope / profile-private 承载提交正文，而非塞进公开 knock。这一禁止与 §8.2 末尾"申请正文 MUST NOT 进入 `ak.member.state{knock}` Control Move"在 base v1 层同口径，构成两侧闭合。

`default_join_rule` 枚举（[`../models/realm-and-space.md` §2.3](../models/realm-and-space.md)）只表达粗粒度的入口模式：`public` 直接进、`invite` 必须有人邀、`knock` 可申请、`restricted` / `knock_restricted` 有附加条件、`closed` 不收新人。但是 `restricted` 的"条件"是什么、`knock` 申请里能否带结构化材料、人工审批的决策是否上链审计、CAPTCHA / proof-of-work 等运行时挑战如何接入——这些都需要本文件统一定义。

本文定义的 **Join Policy** 与 `default_join_rule` 正交又互补：

- `default_join_rule` 决定**入口模式**（`public` / `invite` / `knock` / `restricted` / `knock_restricted` / `closed`）。
- Join Policy 决定**入口模式选定后，到 `membership=join` 必须穿越的 gate 集合**（凭证、问卷、挑战、人工审批等）的组合、解析顺序、加密语义和反滥用约束。
- Join Policy 的 gate 分三条正交轴（§4）：**A 硬准入门 `principal_admission`** 与 **B deny-only gate `cooldown`** 与 `default_join_rule` 完全正交，在所有取值（含 `public` / `invite` / `closed`）下无条件评估；只有 **C 轴 applicant 可选解析门**的参与集合由 `default_join_rule` 决定。`public` 与 `closed` 下 C 轴为空，但 A / B 轴照常生效——MUST NOT 据此认为 Join Policy 整体不生效。

## 2. 设计原则

1. **Gate 是组合的，不是命名的。** Realm 通过 `gates[]` + `combinator` 表达任意 AND/OR 组合；`knock_restricted` 等组合 enum 的语义由 `combinator` 直接表达，避免每加一类 gate 就要再造 enum。
2. **申请材料对外不可见。** Matrix `m.room.member{knock}` 的 free-text `reason` 因默认可见已成为 spam 通道。实现声明 `ak.profile.candidate.join_policy.v1` 并启用 application / review workflow 时，申请正文 MUST 仅对持有目标 Realm 精确 `ak.realm.admin` capability 的 reviewer 可见：E2EE Realm 中通过 reviewer-only encryption envelope；非 E2EE Realm 中由 Principal Server sync surface 强制访问控制并审计读取（`ak.audit.accessed`）。
3. **审核决策必须有稳定审计材料。** 实现声明 `ak.profile.candidate.join_policy.v1` 时，所有审核接受 / 拒绝 MUST 是签名且被 accepted Seal 覆盖的 Control Move、profile-private Event 或 signed receipt，记录 reviewer DID、review reason、引用证据 hash。事后审计与申诉（参见 [`./content-moderation.md` §5.5](./content-moderation.md) 申诉流程与 [`./content-moderation.md` §10](./content-moderation.md) 审计要求）依赖该 trail。
4. **审核必须密码学绑定到 join。** 借鉴 Matrix `join_authorised_via_users_server` 的担保模式：candidate profile 下随后的 `ak.invite.create` MUST 通过 `refs[role="join_authorised_by"]` 引用对应 signed review accept receipt digest；若实现 profile 已注册私有 review Event kind，MAY 引用该 Event id。reducer 校验该 ref 在写入时仍指向有效 capability 持有者。
5. **自动解析路径不强制走人工。** 当所有 gate 都可自动解析（claim presentation 验证、challenge proof 验证），applicant 可直接提交 `ak.member.state{membership=join}` Control Move，由 reducer 内联校验，无需 application / review Control Move。这条路径替代既有 `restricted` 入口模式的实质语义。
6. **Capability 仍是 allow 唯一来源。** Join Policy gate 通过即"可以提议加入"，但 reducer 仍按 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 校验 join Control Move 的 capability。Policy Server `obligations[]`（§12）只能在 capability 之上叠加额外要求（如 challenge），不能凭空创造权限。

## 3. Cell Family 与 State Event

```text
event kind  := ak.realm.policy_bundle
cell_id     := ak:cell:ak.component.realm.policy_bundle.v1:null
lattice     := cas_register
bottom      := reject
payload path:= join_policy
value shape := JoinPolicy（见下；机器真源
               [`event-payload.schema.json#/$defs/join_policy_component`](../../artifacts/schemas/event-payload.schema.json)）
```

Join policy **没有**独立 Event kind，也**没有**独立 cell family：它是 `ak.realm.policy_bundle` payload 的 `join_policy` 组件，随整个 bundle 一起写入 per-Realm 单例 `ak.component.realm.policy_bundle.v1` cell，因此也随 `policy_revision` 单调推进、被同一 cas_register 语义整体替换（每次 revision 重述完整启用组件集）。这与 [`member-delivery-binding.md`](member-delivery-binding.md) §4 的 `ak.component.realm.delivery_binding_policy.v1` 形成对照：后者有自己的 facet event 与独立 cell，前者没有。两个 cell 的 `cell_subject` 都为 `null`，都由 Event envelope `realm_id` 定位。null subject 的 canonical wire 形态（字面 ASCII `null`）及"不得把 `realm_id`、Realm 角色分类或任何 payload 派生值编码进 subject 段"的禁令是全协议规则，canonical 定义在 [`../conformance/encoding.md` §4](../conformance/encoding.md)；本节不再重复承载该规则。

写入 cell 的候选概念在正式登记前记为 `realm.join_policy`（裸名仅是 design-time concept/action，不是 v1 wire `Event.kind`，也 MUST NOT 作为 Event envelope 的 `kind` 上链或同步），需要 `ak.policy.manage` capability（与 `ak.realm.policy_server` / `ak.realm.policy_bundle` 同等级）。`ak.realm.create` 时 SHOULD 通过 `ak.realm.policy_bundle` 一并提供 join policy 初值；bundle 内省略 `join_policy` 组件即表示未声明 join policy，行为退化为"`default_join_rule` 单独决定"。

JoinPolicy 候选 schema 名：`realm.join_policy.v1`。

**`candidate_kind` 信封字段（normative）**：§3 与 §14 示例顶层出现的 `candidate_kind`（如 `"candidate_kind": "realm.join_policy"`）是 **candidate surface 专用的 profile-private 信封字段**，用于在实现自有承载（signed receipt / profile-private Event kind）中标注该 payload 对应哪个 candidate concept。它**不是** Event envelope 的 `kind`（[`../models/event-and-patch.md`](../models/event-and-patch.md)），在 [`../models/common-fields.md`](../models/common-fields.md) / [`../overview/glossary.md`](../overview/glossary.md) 中无登记，也 MUST NOT 作为 `Event.kind` 上链或进入 shared Realm wire / federation。`candidate_kind` 取裸名 candidate concept（`realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel`），仅在声明 `ak.profile.candidate.join_policy.v1` 的实现内部、其 profile-private 承载层有效。§7.2 / §7.3 在 prose 中直接用裸名引用同一组 candidate concept，二者指向一致；区别仅是 §3 / §14 给出带 `candidate_kind` 包装的具体 payload 示例形态。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `gates` | yes | `array<Gate>` | 1..16 项；空数组 MUST schema_violation。 | 必须穿越的 gate 列表。 |
| `combinator` | yes | `enum(all, any)` | 无默认值；producer MUST 显式写入。 | gate 之间的组合语义。 |
| `review_capability` | conditional | `const ak.realm.admin` | 任一 gate `kind ∈ {manual_review, application_form}` 时必填；wire payload MUST 显式写入。 | current-v1 复用既有 exact-Realm admin grant，不登记 candidate 专用 action，也不从 profile claim 推导 issuer authority；与 §7.3 `reviewer_capability_proof`（引用授予该 action 的 **grant id** + frontier digest）是两个不同概念。[^review-capability-alias] |
| `reviewer_quorum` | no | `enum(any, majority, all) \| object` | 默认 `any`。`object` 形式 `{ threshold: int, reviewers: did[] }` 表达 N-of-M。 | 审核法定人数。 |
| `application_ttl` | no | `duration` | 默认 `PT168H`，最小 `PT1H`，最大 `P1Y`。 | 申请未决超时即失效。 |
| `cooldown_after_reject` | no | `duration` | 默认 `PT72H`。 | 拒绝后同一 actor 重新申请的最短间隔。 |
| `max_open_applications_per_actor` | no | `integer` | 默认 `1`，最大 `5`。 | 同一 actor 在本 Realm 同时未决申请上限。 |
| `applicant_visibility` | no | `enum(reviewer_only, members_after_join, public)` | 默认 `reviewer_only`。 | 申请正文谁可见；`members_after_join` 表示 join 成功后开放给 Realm 成员（用于自我介绍场景）。 |
| `directory_hint` | no | `object` | 见 §3.2。 | Discovery Directory 公开投影所需 hint。 |

[^review-capability-alias]: 该字段语义是 *被授权 reviewer 所持的 capability action token*，不是 grant id 引用；wire 字段名固定为 `review_capability`。

**`reviewer_quorum` 解析规则（normative）**：

- object 形式 `{ threshold, reviewers }`（N-of-M）写入时，reducer MUST 校验 `threshold <= |unique reviewers|`（`reviewers[]` 按 DID 去重后的元素数；[`event-payload.schema.json#/$defs/join_policy_component`](../../artifacts/schemas/event-payload.schema.json) 已对 `reviewers` 声明 `uniqueItems: true`）。不满足时 MUST 以 `schema_violation` 拒绝该 policy 写入。
- `majority` / `all` 的分母（reviewer 总数）与单个 reviewer 的资格（是否持有 `review_capability`）MUST 按**各 review accept Event 的 CBA basis** 取值（与 §5 "Gate predicate 评估时点"同一模型）。某条 accept 按其 basis 计入后，该 reviewer 在后续 Seal 失去 capability **不**追溯使既有 accept 失效；它只影响该 reviewer 此后新的 review 决策与新 envelope 投递（§8.2）。
- **quorum 数学上不可达（normative）**：当 `reviewer_quorum` 为 object 形式 `{ threshold, reviewers }` 且在当前评估 frontier 下仍持有 `review_capability` 的 `reviewers[]` 元素数已 `< threshold`（如 reviewer 被撤销 capability 或离开 Realm，使剩余合格 reviewer 不足以达成 threshold），该 application 进入**不可达**状态。reducer / review 服务 MUST NOT 让 applicant 无声挂起至 `application_ttl`：检测到不可达时 MUST 把该 application 转为终态 reject，写入 §7.3 受控枚举 `reason_code="quorum_unreachable"`（见 [`../../artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)），并 SHOULD 通过 §11 / Realm policy 触发 join policy 重评（如降低 threshold 或补充 reviewer）。`majority` / `all` 形式因分母随合格 reviewer 集合动态收缩，不构成此意义上的不可达。

### 3.1 Gate 类型

每个 Gate 是 typed flat object，复用 [`../authz/constraint-schema.md` §2.1](../authz/constraint-schema.md) 的扁平结构传统：

```json
{
  "gate_id": "string",
  "kind": "claim_required",
  "auto_resolve": true
}
```

字段语义：

- `gate_id`：稳定 id，用于审计与 application 中的 proof 关联。**`gate_id` MUST 在 `gates[]` 中唯一**——重复值 MUST 触发 `schema_violation`（`reason_code=join_policy_duplicate_gate_id`，见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）。enforcement 由三层组成：(a) [`event-payload.schema.json#/$defs/join_policy_component`](../../artifacts/schemas/event-payload.schema.json) 在 `gates` 数组上声明 `uniqueItems: true`，捕获**整对象重复**的 gate；(b) JSON Schema 2020-12 无法以纯 schema 表达"按字段属性去重"，因此 [`check_join_policy_gate_id_uniqueness`](../../../../tools/artifact_lint/prose.py) 在 fixture 与 Markdown JSON 示例中机械拒绝**按 `gate_id` 去重**的违例；(c) reducer 在 wire 上再做一次 `gate_id` 唯一性校验并以上述 reason_code 拒绝。三层共同构成机器可执行的闭环。
- `kind`：取 `claim_required` / `application_form` / `challenge_response` / `manual_review` / `parent_membership` / `principal_admission` / `cooldown` 之一
- `auto_resolve`：该 gate 能否仅靠 applicant 提交的材料解析；`manual_review` / `application_form` 必为 `false`
- 其余字段按 `kind` 决定（见下表）

| `kind` | 必带字段 | 语义 | `auto_resolve` |
| --- | --- | --- | --- |
| `claim_required` | `required_claims[]`（见 [`../authz/constraint-schema.md` §10](../authz/constraint-schema.md)） | applicant MUST 提交满足声明集合的 VC / claim presentation。 | `true` |
| `parent_membership` | `membership_source_realm_ids: id:realm[]`、`require_min_membership: enum(invite, join)` | applicant MUST 已是任一 source Realm 的指定成员；该字段只是 membership gate 的验证来源，不表达 Realm 树形父子关系。reducer 在 join Control Move 校验时必须能够独立验证（snapshot 或 backfill）。等价于 Matrix MSC3083 `m.room_membership` 条件。 | `true` |
| `principal_admission` | 至少一个 selector 字段：`allowed_did_methods[]`、`allowed_principal_ids[]`、`denied_principal_ids[]` | applicant 的 principal DID 自身 MUST 满足 Realm 声明的硬准入条件。典型用途是只允许特定 DID method 或显式 allowlist 中的 principal 加入。 | `true` |
| `challenge_response` | `provider_did: did`、`challenge_kinds: enum(captcha, pow, attested_human, idp_oidc)[]`、`max_proof_age: duration` | applicant MUST 完成 provider 颁发的挑战并提交 signed proof。详见 §12。 | `true` |
| `application_form` | `questions[]`（见 §3.3） | applicant MUST 在 `member.application` 中提交对应 answer；reviewer 人工评估。 | `false` |
| `manual_review` | （无额外字段） | reviewer 必须显式签署 accept；不要求结构化问卷。 | `false` |
| `cooldown` | `min_interval_since_leave: duration` | applicant 上次**主动离开**后未达冷却期 MUST 拒绝。主动离开仅指由该 member 自己 author、满足 `Event.actor_id == payload.actor_id`、并把已 join membership 转为 `leave` 的 accepted `ak.member.state`；review reject、application cancel、`application_ttl` 到期或 ban 导致的 `leave` projection 不计入本 gate。仅作为 deny gate（与 `combinator` 无关，单独评估；亦不计入 §5 "applicant 拟使用的 gate 子集"的 `auto_resolve` 全称校验，见 §5）。此 gate 的语义是 **leave-cooldown**，prose / SDK 推荐用 `leave_cooldown` 称呼以区别于 §3 顶层字段 `cooldown_after_reject`（后者按上次 **review reject** 计时，作用于 `member.application` 重提，二者计时锚点、作用对象完全不同）。 | `true` |

未注册 `kind` MUST schema_violation；未注册的 `(kind, subfield)` 组合按 lattice `bottom=reject` 处理。

#### `principal_admission`

`principal_admission` 是自动解析 gate，用于约束提交 `ak.member.state{membership="join"}` 的 `actor_id` / `payload.actor_id` 所指稳定 principal `did_core_id`。它只判断该 principal identity，不替代 capability、invite、review、claim presentation、DID Document 解析、service delegation 或 [`member-delivery-binding.md`](./member-delivery-binding.md) 的投递绑定校验；需要解析或验证控制权时，裸 DID 与 DID URL 作为独立证据输入处理。

字段：

- `allowed_did_methods[]`：允许的 DID method 列表，元素使用完整 `did:<method>` 标签（例如 `did:webvh`、`did:web`、`did:key`）。空或缺省表示不按 method 限制。
- `allowed_principal_ids[]`：可选精确 allowlist。非空时 applicant DID MUST 等于其中一个值。
- `denied_principal_ids[]`：可选精确 denylist。denylist 优先级最高；命中时 MUST 拒绝，即使也命中 allowlist。

`principal_admission` 至少 MUST 声明一个 selector 字段（上述三个数组之一非空，或实现 profile 明确声明的等价 selector），否则 reducer MUST 以 `schema_violation` 拒绝 policy 写入。多个 selector 字段按 AND 组合，denylist 先于 allowlist 评估。

`principal_admission` 是 hard pre-admission gate：只要 Join Policy 中出现该 gate，reducer MUST 在普通 `combinator` 解析、application form 或 manual review 之前先评估它；任一 `principal_admission` gate 失败时，当前 join / knock / application MUST fail closed，applicant 不得通过其它 gate 或人工审核路径绕过 principal 准入约束。

**本 gate 与 `default_join_rule` 完全正交（normative）**：它在 `public` / `invite` / `knock` / `restricted` / `knock_restricted` / `closed` 六种取值下一律评估，**invite 路径同样适用**——`ak.invite.create` 与 `ak.invite.accept` 在写 `ak.component.member.state.v1` 之前 MUST 先过本 gate（§4）。任何"某些 join rule 下 Join Policy 不生效"的实现都会让 DID method allowlist 与 principal denylist 可被切换 join rule 绕过。

加入失败对外 MUST 使用通用 `gate_check_failed`，不得向 external applicant 区分"method 不允许"、"DID 不在 allowlist"、"DID 在 denylist"等细节；细节 MAY 写入 reviewer / admin 可见审计日志。

**细分原因对 applicant 永不可见是预期，非缝隙（normative，消歧）**：`principal_admission` 是 hard pre-admission gate，在普通 `combinator` 解析、application form、manual review 之前评估，也即在 applicant 提交 stage 1 `ak.member.state{knock}` 进入 §7.3 半信任申请-审核态**之前**就已对其 fail closed。因此被 `principal_admission` 拒绝者**永远到达不了** §7.3 半信任态，§7.3「knock 之后才解锁面向本人的细粒度 review reason」对其不适用——其拒绝细分原因（method / allowlist / denylist 命中）对 applicant **永不可见**（仅 reviewer / admin audit 可见）。这是刻意设计：principal 准入是比半信任申请更靠前的硬门，不向未通过硬门的探测者透露准入名单结构，与 §5「外部 applicant 失败不可枚举」一致，并非 §7.3 半信任披露规则的缝隙或遗漏。

示例：

```json
{
  "gates": [
    {
      "gate_id": "principal-users-acme",
      "kind": "principal_admission",
      "auto_resolve": true,
      "allowed_did_methods": ["did:webvh"],
      "allowed_principal_ids": [
        "did:webvh:z2dmjYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x:users.acme.example:bob"
      ]
    }
  ],
  "combinator": "all"
}
```

### 3.2 `directory_hint`

为帮助 Discovery Directory（[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)）告知 applicant "进入这个 Realm 大概要做什么"，Realm MAY 声明 directory hint。该 hint 是公开投影，**MUST NOT** 包含敏感问卷正文：

```json
{
  "directory_hint": {
    "summary": "Members must hold an Acme employee VC and complete a brief intro form.",
    "expected_review_time": "PT24H",
    "human_review_required": true,
    "challenge_kinds_displayed": ["captcha"]
  }
}
```

`questions[]` 正文 MUST NOT 出现在 hint 中；公开 question prompt 是 opt-in（每个 question 独立 `disclosed_in_directory: bool`）。

`directory_hint` 是封闭对象：`summary` 为 1..512 chars；`expected_review_time` 为 ISO 8601 duration；`human_review_required` 为 boolean；`challenge_kinds_displayed[]` 最多 16 项且仅取 `captcha` / `pow` / `attested_human` / `idp_oidc`。未知字段或未知 challenge kind MUST `schema_violation`。

### 3.3 `application_form.questions[]`

```json
{
  "questions": [
    {
      "question_id": "q1",
      "prompt_canonical": "Why do you want to join?",
      "prompt_locales": {"en": "Why do you want to join?", "zh": "为什么想加入？"},
      "answer_kind": "text | single_choice | multi_choice | boolean",
      "required": true,
      "min_chars": 20,
      "max_chars": 500,
      "choices": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
      "auto_reject_if_choice_in": ["no"],
      "disclosed_in_directory": false
    }
  ]
}
```

`auto_reject_if_choice_in` 让 reducer / 审核服务对明显错误答案直接生成 `decision=reject`，不进入人工队列。

Question 是封闭对象，必填 `question_id`、`prompt_canonical`、`answer_kind`、`required`；`answer_kind` 封闭为 `text` / `single_choice` / `multi_choice` / `boolean`。`question_id` 在同一 gate 内 MUST 唯一；`choices[]` 仅用于 choice kind，choice `id` 在同一 question 内 MUST 唯一；`auto_reject_if_choice_in[]` 的每一项 MUST 引用同一 question 的 choice id。`min_chars <= max_chars`，且二者仅用于 `text`。违反字段组合、引用或唯一性约束 MUST `schema_violation`。

单个 `application_form` gate 的 `questions[]` MUST ≤ 64 项（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)）；超过时 MUST `schema_violation`。

**引用键与总量预算（normative）**：`question_id` 只在同一 gate 内唯一，因此一条 answer 的引用键 MUST 是
**`(gate_id, question_id)` 二元组**——一个 policy 可以有多个 `application_form` gate，裸 `question_id`
在两个 gate 都声明同名 slug 时无法唯一指向其中一条。[`join-policy-operations.schema.json#/$defs/answer`](../../artifacts/schemas/join-policy-operations.schema.json)
的两个成员都 `$ref` 到定义端同一组 slug 类型
（[`event-payload.schema.json#/$defs/join_policy_gate_id`](../../artifacts/schemas/event-payload.schema.json) 与
`#/$defs/join_policy_question_id`），因此 answer **不可能**拼出 policy 永远无法定义的引用；
SDK 也只实现这一组共享强类型，不得在引用端另建更宽的字符串类型。

词法合法不等于存在：reducer MUST 把每个 `(gate_id, question_id)` 对照 `policy_version_digest`
钉住的那一版 policy 解析，未定义的对、指向非 `application_form` gate 的 `gate_id`、以及重复的同一对
分别以 `join_policy_unknown_answer_reference` 与 `join_policy_duplicate_answer_reference` 拒绝
（见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）。

单个 policy 中**所有** `application_form` gate 的 `questions[]` 总数 MUST ≤ 一条 application 的
`answers[]` 上限（同一个机器常量，当前 64）；超过时 MUST `schema_violation`
（`reason_code=join_policy_question_budget_exceeded`）。缺这条总量预算时，`combinator=all`
会允许一个**没有任何合法 application 能满足**的 policy（16 个 gate × 64 questions 远超 64 条 answers），
而申请人只能在提交时才发现。enforcement 与 §3.1 的 `gate_id` 唯一性同构三层：schema 分别约束两侧上限、
[`check_join_policy_question_budget`](../../../../tools/artifact_lint/prose.py) 机械拒绝 artifact 与
Markdown 示例中的越预算 policy、reducer 在 wire 上以上述 reason_code 拒绝。

## 4. 与 `default_join_rule` 的交叉表

Join Policy 的 gate 分三条**正交轴**，`default_join_rule` 只影响其中一条。"Join Policy 在某些 join rule 下整体不生效"是错误概括，MUST NOT 按该概括实现。

| 轴 | 成员 gate | 与 `default_join_rule` 的关系 |
| --- | --- | --- |
| **A. 硬准入门** | `principal_admission` | **完全正交**：`public` / `invite` / `knock` / `restricted` / `knock_restricted` / `closed` 全部无条件评估，且先于一切其它判定（§3.1）。invite 路径同样适用。 |
| **B. deny-only gate** | `cooldown` | **完全正交**：无条件独立评估，命中即拒，无视 `combinator`（§5）。 |
| **C. applicant 可选解析门** | `claim_required` / `parent_membership` / `challenge_response` / `application_form` / `manual_review` | 由 `combinator` 组合，其**参与集合**随 `default_join_rule` 变化，见下表。 |

C 轴与 `default_join_rule` 的交叉：

| `default_join_rule` | C 轴参与集合 | 说明（A / B 轴始终评估） |
| --- | --- | --- |
| `public` | 空 | 无 applicant 可选解析门；applicant 自助 join 按 §5 自动解析路径处理（A/B 轴仍是该路径的一部分，`principal_admission` 不满足或 `cooldown` 命中 MUST 拒绝）。 |
| `invite` | 空 | 入口授权由 invite 承担：必须有 `ak.invite.create`，C 轴不可绕过 invite；**invite 亦不得绕过 A / B 轴**——见下方"invite 路径的 A/B 轴义务"。 |
| `knock` | 全部（任一路径） | gate 集合可包含人工审核；申请-审核路径必走。 |
| `restricted` | 全部 auto-resolve gate | non-deny gate 的 `auto_resolve == true` MUST 全为 true；含 `manual_review` 或 `application_form` MUST `schema_violation`。 |
| `knock_restricted` | 全部（OR 合成） | `combinator` SHOULD 为 `any`；典型组合：`[claim_required(auto), application_form(manual)]`，凭证持有者直接进，否则走问卷申请。 |
| `closed` | 空 | 只关闭 **applicant-initiated 入口**，见下方"`closed` 的封闭豁免列表"。 |

**invite 路径的 A / B 轴义务（normative）**：`ak.invite.create` 与 `ak.invite.accept` 在写 `ak.component.member.state.v1` 之前 MUST 评估 A 轴 `principal_admission` 与 B 轴 `cooldown`；命中 `denied_principal_ids`、不满足 `allowed_did_methods` / `allowed_principal_ids`，或处于 cooldown 期时 MUST fail closed，对外统一 `gate_check_failed`（§5 的不可枚举要求）。否则把 `default_join_rule` 从 `knock` 改成看似**更紧**的 `invite`，反而会关闭 DID method allowlist 与 principal denylist——那是准入面的净放宽，不是收紧。

**`closed` 的封闭豁免列表（normative）**：`closed` MUST 拒绝 applicant 自助提交的 `ak.member.state{join}` / `{knock}` 与 candidate application。它 MUST NOT 拒绝下列 authorized-writer 路径（本列表封闭，不得由实现自行扩展或收窄）：

1. `ak.realm.admin` 持有者按 [`../models/common-fields.md` §4.5](../models/common-fields.md) 写入的 `leave -> join` / `invite -> join`；
2. [`../models/realm-and-space.md` §2.7](../models/realm-and-space.md) 的 Native Personal Agent controller carve-out；
3. Realm bootstrap batch 内由 creator 写入的初始成员（1:1 Direct Conversation Realm 的 peer join 即此项，见 [`../identity/contact-and-direct-conversation.md` §6/§7](../identity/contact-and-direct-conversation.md)）。

这三项仍然要过 A / B 轴。`closed` 约束的是**入口模式**（谁可以自助发起加入），不是一条授权规则——把它扩大成"禁止一切 membership join 写入"会同时封死管理员加人、controller 拉入自己的 Agent，以及 1:1 私聊的 peer bootstrap。

reducer 在 `ak.realm.join_rule` 与 join-policy cell 任一变更时 MUST 重新评估上述一致性约束；不一致 MUST `failed_precondition` 拒绝写入，并附带 `reason="join_rule_policy_mismatch"`。

**存量 in-flight 申请处置（normative）**：当 `default_join_rule` 收紧为 `closed` 或 `invite`（即新入口模式不再接受 knock / application 路径）时，此前已处于 `knock` / `awaiting_review` / `changes_requested` 的存量未决申请 MUST NOT 因 join_rule 变更被静默保留为可继续审核状态。reducer 在 join_rule 收紧生效的 Seal basis 起 MUST：(a) 对收紧前已写入的未决申请，停止接受针对它们的新 `member.application.review{accept}` 与后续 `ak.invite.create`（除非该 invite 走收紧后仍合法的 `invite` 路径独立签发）；(b) 把这些未决申请转为终态 leave，写入 `reason_code="join_rule_tightened"`（见 [`../../artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)），不计 cooldown。已经 `accepted` 且对应 `ak.invite.create` 已落入 frontier 的申请不受影响（其 join 已由 invite 授权承载）。收紧为 `restricted` / `knock_restricted` 等仍保留 application 路径的模式时，存量未决申请按新 policy 的一致性约束在下次 review / 自动解析时重评，不强制转 leave。

## 5. 自动解析路径

适用条件：`default_join_rule ∈ {public, restricted, knock_restricted}` 且 applicant 拟使用的 gate 子集全部 `auto_resolve=true`。`public` 下 C 轴集合可为空，此时"拟使用子集"为空集、全称条件平凡成立，但 **A 轴 `principal_admission` 与 B 轴 `cooldown` 仍 MUST 评估**（§4）——`public` Realm 上的自助 join 不是无条件放行。

**deny-only gate 不计入"拟使用子集"（normative）**：`cooldown` 这类 deny-only gate（§3.1）始终独立、强制评估，applicant 无法选择"使用 / 不使用"，因此**不计入**上述"applicant 拟使用的 gate 子集"的 `auto_resolve` 全称校验；它们虽标注 `auto_resolve=true`，但其角色是 pre-evaluation deny，不是 applicant 可选的解析门。相应地，§4 中 `restricted` 生效时"`gates[*].auto_resolve == true` 全为 true"与"含 `manual_review` / `application_form` MUST schema_violation"的 schema 校验只针对 **non-deny gate**——deny-only gate 始终独立评估，既不破坏 restricted 的全称约束，也不被计入 applicant 子集。

applicant 直接提交：

```json
{
  "kind": "ak.member.state",
  "payload": {
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "actor_id": "ak:did_core:webvh:z2dmjYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x",
    "membership": "join",
    "delivery_status": "routable",
    "delivery_binding": {
      "recipient_service_id": "ak:did_core:webvh:zumXV7yCE8UjvfwVEcio4oN3f",
      "service_resolution": {
        "current_record_url": "https://principal.org-a.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3AzumXV7yCE8UjvfwVEcio4oN3f/resolution"
      },
      "recipient_service_kind": "principal_server",
      "binding_scope": "realm",
      "binding_source": "explicit",
      "delivery_modes": ["events", "sync", "to_device", "push", "keypackages"],
      "service_acceptance_ref": "ak:event:AQwfxZZieb7Udz28u8Z_wXvR3hFpZzHl4sWKOICaiKC6"
    },
    "gate_proofs": [
      {
        "gate_id": "g-org-vc",
        "claim_presentation": "jws-vc:eyJhbGciOiJFZDI1NTE5In0..."
      },
      {
        "gate_id": "g-captcha",
        "challenge_proof": {
          "challenge_id": "chg_01HXY9PM0AB6Y7VN2C7M4WG5KQ",
          "issued_by": "ak:did_core:webvh:zaeuR1WGwz5pkZueKCmyqGFqu",
          "proof": "base64url:..."
        }
      }
    ]
  }
}
```

reducer MUST：

1. 加载当前 join-policy cell value；
2. 按 `combinator` 选取需满足的 gate 子集；
3. 对每个引用的 gate 调用对应 verifier（claim issuer revocation check、challenge provider signature check、parent membership snapshot 查询）；
4. `cooldown` gate 独立评估，命中即拒绝（无视 `combinator`）；
5. 全部通过则接受 `membership=join`；任一失败 `failed_precondition`。**wire 响应统一 `reason_code=gate_check_failed`**（下方"外部 applicant 失败不可枚举"）；具体是哪个 gate fail 与原因只写入 reducer / audit log，MUST NOT 出现在 applicant 可见响应中。

reducer MUST NOT 在自动解析路径上隐式生成 application / review Control Move——此路径绕过申请-审核状态机。

**外部 applicant 失败不可枚举（normative）**：对尚未 join 的外部 applicant，wire 响应 MUST 统一为 `failed_precondition` + `reason_code=gate_check_failed`（或 invite / directory surface 已定义的统一不可枚举错误），不得区分“claim 从未签发”、“claim 已撤销”、“issuer 暂时不可达”、“parent membership 不满足”或“challenge proof 失效”。Reducer / audit log MAY 记录内部 diagnostic reason、gate_id 与 issuer 状态，但这些字段不得出现在 applicant 可见响应、directory hint 或 push/notification payload 中。Reviewer-only application workflow 可以在加密 reviewer envelope 内展示更细原因。

**Gate predicate 评估时点（normative）**：所有 gate predicate（包括 claim issuer revocation、challenge provider signature、`cooldown`、parent membership、capability presence 检查）MUST 仅对该 join Control Move 的 `seal_basis` 指向的控制面 view 求值，与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 的 CBA basis 模型一致。同一 ordered submit batch 内并发的 `ak.capability.revoke` / policy 变更 / `ak.realm.join_rule` 更新对**本批次**的 join Control Move **不**生效；它们仅从后续 Seal 起影响 gate 评估。这意味着：

- 同批中"先撤销 review capability，后 join"的攻击模式不会让 join 通过 review-gated 路径——gate 仍按 pre-state 看到完整 capability。
- 反之，同批中"先发 grant，后用 grant 满足 gate" 也不会被 reducer 当作满足——授权与 Control Move 的可见性以 CBA basis 为单位。
- 与本规范 §3.1 中 `combinator` 的"deny gate（如 cooldown）独立评估"规则共存：cooldown 等 pre-evaluation deny gate 同样基于 CBA basis 触发，且不参与 combinator。

## 6. 成员投递绑定

> 成员投递绑定（effective delivery binding）的接受准则、`binding_source` 与责任方、`ak.realm.delivery_binding_policy` policy 事件、路由不可降级、rebind 过渡、单 binding + 多设备策略与关联性 / 隐私边界，已拆分为独立文件 [`member-delivery-binding.md`](member-delivery-binding.md)。
>
> delivery binding 与 join gate **正交**：join gate（本文）决定“能否加入”，delivery binding 决定“加入后 events / sync / to-device / push / key-package 投递到哪个 Principal Server”。两者方向、生命周期、授权来源均不同，MUST NOT 互相推导。

## 7. 申请-审核路径

适用条件：`default_join_rule ∈ {knock, knock_restricted}` 且至少一个 gate `auto_resolve=false`。

### 7.1 阶段

| 阶段 | Control Move | 写入方 |
| --- | --- | --- |
| 1. 敲门 | `ak.member.state{membership=knock}` | applicant |
| 2. 提交申请 | `member.application` | applicant |
| 3. 审核决策 | `member.application.review` | reviewer（持 `review_capability`） |
| 4. 签发定向邀请 | `ak.invite.create`（注册 projection：`ak.component.invite.lifecycle.v1` → `pending` **且** `ak.component.member.state.v1:<invitee>` `knock -> invite`） | reviewer（持目标 Realm 精确 `ak.realm.admin`） |
| 5. 接受邀请 | `ak.invite.accept`（注册 projection：`invite.lifecycle` → `accepted` **且** `member.state` `invite -> join`） | applicant（invitee 本人） |

stage 4 / 5 的两条 Event **各自**在同一 Control Move 内同时推进 invite 流程轴与 membership cell，不是"invite 对象变了、成员态由 reducer 顺带跟进"。invite 被 reject / revoke / 过期时的 `invite -> leave` 原子回写见 [`../models/governance-objects.md` §5.3](../models/governance-objects.md)。

stage 1 是公开 Control Move，stage 2 是 profile-private receipt，二者不得伪装成同一 Event batch。client MUST 先取得已接受 stage 1 的 `event_id`，再把它作为 `knock_ref` 提交 stage 2；server 在写入 private record 的同一事务内 MUST 重新确认该 knock 仍有效。

### 7.1.1 Candidate profile 的唯一承载（normative）

声明 `ak.profile.candidate.join_policy.v1` 的实现 MUST 实现下表 profile-private operation；这些 operation 是该 candidate profile 的唯一可互操作承载，不得再把 `application` / `application_review` / `application_cancel` 扩展字段塞入闭合的 `ak.member.state` payload，也不得把裸名 candidate concept 当作 Event envelope `kind`：

| operation id | HTTP binding | caller / 可见性 | 用途 |
| --- | --- | --- | --- |
| `ak.self.realm.join_application.command.submit.v1` | `POST /_arkret/self/realms/{realm_id}/join-applications` | applicant | 提交或修订 applicant-signed application receipt 与独立 private body。`Idempotency-Key` 必填。 |
| `ak.self.realm.join_application.command.review.v1` | `POST /_arkret/self/realms/{realm_id}/join-applications/{application_ref}/reviews` | 当前持有 `review_capability` 的 reviewer | 提交 reviewer-signed review receipt。`Idempotency-Key` 必填。 |
| `ak.self.realm.join_application.command.cancel.v1` | `POST /_arkret/self/realms/{realm_id}/join-applications/{application_ref}/cancel` | 原 applicant | 提交 applicant-signed cancel receipt。`Idempotency-Key` 必填。 |
| `ak.self.realm.join_application.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/join-applications` | Realm member / applicant；正文仍按下文授权裁剪 | 分页列出最小化 metadata；reviewer 与对应 applicant 可见 private body，其他 Realm member 只见 `{application_pending:true}`。 |
| `ak.self.realm.join_application.resource.get.v1` | `GET /_arkret/self/realms/{realm_id}/join-applications/{application_ref}` | reviewer 或对应 applicant | 读取一条申请；每次成功读取 private body MUST 产生 `ak.audit.accessed`。 |
| `ak.self.realm.join_application.audit.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/join-applications/{application_ref}/audit` | reviewer、对应 applicant 或持有 Realm audit capability 的主体 | 读取 submit/read/review/cancel/invite-consume 审计轨迹；不得返回其它申请正文。 |

所有 `{realm_id}` / `{application_ref}` path 参数 MUST 与 body receipt 内对应字段逐字一致。`application_ref` 是 `application_receipt_digest`（`sha256:<lowercase hex>`），path 中按普通 URL segment percent-encode。write operation 的 `Idempotency-Key` 与完整 canonical request digest 绑定：相同 key + 相同 body 返回原结果；相同 key + 不同 body MUST `duplicate_conflict`，不得覆盖首个 receipt / private body。

这组 operation 只在部署的 `ak.server.read.describe.v1` 与 `ak.self.account.read.describe.v1` 同时声明：

- `supported_profiles` 含 `ak.profile.candidate.join_policy.v1`；
- `supported_operation_bundles` 含上表全部 operation 的精确 carrier/schema 行；
- feature set 含 `candidate_join_policy_reviewer` 与 `candidate_member_application_intake`；
- `profile_bindings["ak.profile.candidate.join_policy.v1"].carrier` 恰为 `"profile_private_http_receipt_v1"`。

否则 client / conformance runner MUST 视为未启用并跳过 candidate 流程；server MUST 以 `unsupported_feature` / 501 fail closed，不得只暴露部分 write/read surface。HTTP request / response 的闭合 DTO 以 `ak.schema.join_policy_operations.v1`（`join-policy-operations.schema.json`）为准。

**receipt digest 与签名 transcript（normative）**：

1. application / review / cancel receipt 分别计算 `sha256:JCS(receipt without {application_receipt_digest|review_receipt_digest|cancel_receipt_digest, proof})`；wire 中必须回填该小写十六进制 digest。receiver MUST 重算并 constant-time 比较。
2. `proof` 必须是 `kind="detached_jws"`，`verification_method` 必须解析为对应 `applicant_actor_id` / exact `(reviewer_actor_id, reviewer_principal_server_id)` / `cancelled_by` 在提交 basis 上的 active device/actor key；review receipt 引用 grant 的 `(subject, subject_principal_server_id)`、receipt reviewer pair 与验签 key controller 投影 MUST 逐字相等；仅有 bearer session 或三者任一不等 MUST 拒绝。
3. application proof 签名 JCS `{context:"ak.join_application_receipt_proof.v1",receipt_digest,realm_id,actor_id,verification_method,created_at}`；其中 `actor_id=applicant_actor_id`、`created_at=submitted_at`。
4. review proof 签名 JCS `{context:"ak.join_application_review_receipt_proof.v1",receipt_digest,realm_id,application_ref,application_revision_digest,actor_id,principal_server_id,verification_method,created_at}`；其中 `actor_id=reviewer_actor_id`、`principal_server_id=reviewer_principal_server_id`、`created_at=reviewed_at`。
5. review capability 资格与 proof 验签按 exact reviewer authority pair 校验，但 quorum 按 `reviewer_actor_id` 去重，同一 DID 在同一 quorum 中最多计一票。若同一 DID 有多张 accepted receipt，canonical tie-break 键固定为每张 receipt 的 `review_receipt_digest`：先按 `encoding.md` §4.2 校验 digest suite，再比较解码后的 digest octets，bytewise 最大者胜出；仅 octets 完全相同而 suite 不同时才以 canonical suite id 的 unsigned UTF-8 bytewise 顺序作第二键。不得以 `reviewed_at`、arrival order、Principal Server 或 wire digest 字符串替代该键；结果必须与到达顺序无关。协议不提供按 authority pair 重复计票的可选形态。
6. cancel proof 签名 JCS `{context:"ak.join_application_cancel_receipt_proof.v1",receipt_digest,realm_id,application_ref,actor_id,verification_method,created_at}`；其中 `actor_id=cancelled_by`、`created_at=cancelled_at`。
7. request 中的 private body 不进入共享 receipt；receipt 的 `private_body_digest` MUST 等于该 body 的 `sha256:JCS(private_body)`。`application_revision_digest` 仍按 §7.3 的固定 `{answers,gate_proofs,policy_version_digest}` 前像计算：`server_protected` 模式由 server 重算；`reviewer_envelope` 模式由 client 在加密前计算并由 reviewer 解密后复核，server 只验证 receipt / ciphertext body digest 与 recipient capability binding。

receipt 与 private body MUST 在同一 durable transaction 中写入；任一 schema、签名、policy、knock、cooldown、TTL、capability、recipient 或幂等校验失败时均不得留下半条记录。application/review/cancel receipt 属于 profile-private durable record，可以跨重启读取与审计，但 MUST NOT 出现在普通 Realm event query、sync timeline、federation event push/pull 或 Seal `control_event_set_root` 中。

### 7.2 `member.application`

候选申请概念；schema 名 `member.application.v1`。正式进入 v1 registry 前，`member.application` 不得作为 Event envelope 的 `kind` 使用，也不得使用 `ak.*` 标准前缀伪装成 active contract；生产实现若启用本 workflow，必须在自有 profile 中声明唯一承载方式，并输出可引用的 signed application receipt（`application_receipt_digest`），供后续 review / invite / audit 引用。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `realm_id` | yes | `id:realm` | 申请目标 Realm。 |
| `applicant_actor_id` | yes | `did_core_id` | 等于 envelope `actor_id`。 |
| `knock_ref` | yes | `event_ref` | 引用 stage 1 的 `ak.member.state{knock}` event id。 |
| `policy_version_digest` | yes | `digest` | 提交时 `realm.join_policy` cell value 的 canonical digest；reducer 校验 reviewer 决策时是否仍是同一 policy。 |
| `private_body_digest` | yes | `digest` | 对本次 profile-private body 的 `sha256:JCS`；receipt 只绑定 digest，不复制正文。 |
| `application_revision_digest` | yes | `digest` | 按 §7.3 固定前像计算，review 必须绑定同一 revision。 |
| `answers` | conditional | `array<Answer>` | 位于 `private_body{mode="server_protected"}`；任一 `application_form` gate 存在时必填，覆盖每个这样的 gate 所有 `required=true` 的 `(gate_id, question_id)` 对。 |
| `gate_proofs` | conditional | `array<GateProof>` | 位于 `private_body{mode="server_protected"}`；任一可自动解析 gate 存在时按需提供（与自动解析路径同形）。 |
| `applicant_note` | no | `string` | 位于 private body，1..2000 chars 自由文本备注。 |
| `encryption_envelope` | conditional | `object` | 位于 `private_body{mode="reviewer_envelope"}`；E2EE Realm 必填，见 §8。 |

`Answer` 形态：`{gate_id, question_id, value: string|string[]|boolean}`；引用键是 §3.3 的 `(gate_id, question_id)` 二元组，reducer 做存在性 / 唯一性 / shape 校验，语义评估留给 reviewer。`answers[]` MUST ≤ 64 项（与 §3.3 的 policy 级 `questions[]` 总量预算是同一个机器常量）、`gate_proofs[]` MUST ≤ 16 项（与 §3 `gates` 1..16 上限对齐）；超过时 MUST `schema_violation`（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)）。非 E2EE Realm 使用 `server_protected` private record；E2EE Realm 使用 reviewer envelope。两种 body 都只经 §7.1.1 私有 operation 传输，不进入 `ak.member.state`。

### 7.3 `member.application.review`

签名 review workflow record，需要 `review_capability`。在正式注册为 v1 active Event kind 前，它不是 base profile 的 durable `Event.kind`；实现必须把 review 结果承载为自有 profile 声明的 signed review receipt（`review_receipt_digest`），或承载在该 profile 自己注册的私有 Event kind 中。任何 `ak.invite.create` 对 review 的引用 MUST 指向稳定 receipt digest 或该私有 Event id，不得引用未注册的裸名 kind。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `realm_id` | yes | `id:realm` |  |
| `application_ref` | yes | `receipt_digest` 或 profile-private `event_ref` | 指向 §7.2 的 signed application receipt；若实现 profile 已注册私有 application Event kind，MAY 指向该私有 Event id。不得引用未注册的裸名 `member.application`。 |
| `decision` | yes | `enum(accept, reject, request_changes)` | review **结果**由本字段承载（accept / reject / request_changes），等价于本文件族 §5.5 appeal 的 `decision` 角色。`request_changes` 允许 applicant 修订 answer 后重提，不计入 cooldown。 |
| `reason_code` | conditional | `string` | 稳定**拒绝 / 变更细分原因码**：`incomplete_answers` / `policy_violation` / `claim_invalid` / `challenge_failed` / `duplicate` / `ttl_expired`（reducer 自动超时拒绝，见 §12）/ `quorum_unreachable`（§3 N-of-M reviewer quorum 已不可达）/ `other`。`decision ∈ {reject, request_changes}` 时必填；`decision=accept` 时省略或取保留值 `ok`（`ok` 不承载独立语义，成功结果由 `decision=accept` 表达）。本字段遵循 [`../models/common-fields.md` §2](../models/common-fields.md)（受控枚举用 `_code` 后缀），仅承载拒绝 / 变更细分，不兼表成功裁决。 |
| `reason_text` | no | `string` | 1..1000 chars 自由文本，对 applicant 可见。 |
| `evidence_refs` | no | `event_ref[]` / `hash[]` | 评审依据的其它 event 或 signed receipt（如 `ak.audit.*` 风险记录）。 |
| `reviewer_capability_proof` | yes | `object` | 引用授予 reviewer `review_capability`（§3 中那个 capability **action token**）的 **grant id** 与当时 frontier digest；reducer 必须在写入时再校验一次。注意：本字段承载 grant id 引用，`review_capability` 承载 action token，二者勿混用。 |

`reviewer_quorum != "any"` 时，reducer 需收集 N 个独立 reviewer 的 accept 才认为申请进入 `accepted` 状态；任一 reject 即终止。quorum 判定 MUST 遵循 §3 的 `reviewer_quorum` 解析规则：`majority` / `all` 的分母与 reviewer 资格按各 accept Event 的 CBA basis 取值；accept 计入后 reviewer 失去 capability 不追溯使该 accept 失效。

`request_changes` 与 quorum 的聚合规则（normative）：

1. 任一在当前 application revision 上有效的 `request_changes` 立即把 application 投影置为 `changes_requested`，并暂停该 revision 的 quorum 计数；同批存在 `reject` 时 `reject` 优先并进入终态。
2. Application 的每个提交/修订 MUST 计算 `application_revision_digest = sha256(JCS({answers, gate_proofs, policy_version_digest}))`。对象恰含这三个键；条件字段未提供时，`answers` 或 `gate_proofs` 仍以空数组进入前像，禁止省略键或写 `null`。每条 review receipt MUST 签名绑定该 digest；缺失或不等的 accept/request_changes/reject 不得作用于当前 revision。
3. Applicant 提交修订后，旧 digest 上全部 accept 与 request_changes 保留审计事实但 MUST NOT 计入新 revision 的 threshold。新 revision 的 accept 从零重新累计；实现 MUST NOT 复用 reviewer 对旧正文的同意。
4. 同一 reviewer 对同一 revision 的多个决定按其因果后继取最新；并发不同决定为冲突，不计入 quorum，直到 reviewer 在新 basis 上显式收敛。不同 reviewer 的 accept 按集合并集计数。

**review reason_code / reason_text 可见性（normative）**：§7.3 的细粒度 `reason_code` 与 `reason_text` 只在 applicant **已提交 stage 1 `ak.member.state{knock}`**（即进入半信任的申请-审核状态机）后，才 MAY 对该 applicant 自身可见。这与 §5 自动解析路径"外部 applicant 失败不可枚举"不冲突：尚未 knock 的外部探测者仍只能看到统一不可枚举错误，细粒度 review 原因 MUST NOT 出现在 directory hint、discovery surface、push / notification payload 或任何未经 knock 的 caller 可见响应中。换言之，半信任边界由"是否已 knock"划定——knock 之前等同自动路径的不可枚举约束，knock 之后才解锁面向本人的 review reason。

### 7.4 `member.application.cancel`

applicant 可主动撤回；写入独立 `member.application.cancel` record，携带 `application_ref`、`cancelled_by`、`cancelled_at` 和可选 `reason_text`，不写入 §7.3 的 `decision` 字段，也不计 cooldown。

### 7.5 接受后的 invite

application 进入 `accepted` 状态后：

1. 任一 reviewer 提交 `ak.invite.create`，`refs[role="join_authorised_by"]` MUST 引用对应 `member.application.review{accept}` 的 signed review receipt digest；若实现 profile 已注册私有 review Event kind，MAY 引用该 Event id。`reviewer_quorum` 为 object 形式（N-of-M）时，`refs[role="join_authorised_by"]` MUST 引用**满足 `threshold` 的全部** review accept receipt digest（每条计入 quorum 的 accept 各一条 ref），使 reducer 与审计方可独立复核 quorum 在引用的 accept 集合上成立；
2. applicant 提交 `ak.invite.accept`；
3. reducer 在写入 `ak.invite.create` 时再次校验：被引用的 review accept 仍指向尚未消费的 application（防止同一 accept 被复用）、application 未过 `application_ttl`、未被后续 `reject` / `cancel` 覆盖；且每条被引用的 review accept 在**其自身 CBA basis**（该 accept receipt 的 seal_basis）下由当时持有 `review_capability` 的 reviewer 签发。

**已计入 quorum 的 accept 不追溯失效（normative，竞态衔接）**：reviewer 在签发某条 accept 之后失去 `review_capability`（被撤销 / 离开 Realm），**不**追溯使该条已计入 quorum 的 accept 失效——其有效性锚定在该 accept 自身的 CBA basis（与 §3 "accept 不追溯失效" 一致）。§3 的 quorum **不可达**检测只在 threshold **尚未达成**时，看当前仍合格 reviewer 是否 `< threshold`；一旦 N-of-M 的 threshold 已被合法 accept 集合达成，后续个别 reviewer 失权不回退该 quorum，也不阻塞本节 invite 写入。因此 §7.5(3) 不再要求"全部被引用 reviewer 在写入当前 frontier 仍持有 capability"，只要求每条 accept 在其各自 basis 上成立。

校验失败 `failed_precondition`，`reason_code="join_authorisation_invalid"`。

## 8. 加密与隐私

### 8.1 非 E2EE Realm

`member.application` 的共享 durable wire payload 即使在非 E2EE Realm 中也只能包含最小化 metadata（application id、applicant DID、policy digest、receipt digest、状态与时间戳）。申请正文、answers、自由文本、3PID、附件和 reviewer-only 诊断 MUST 放入 reviewer encryption envelope 或实现 profile 声明的受保护 private record；不得仅依赖 projection 隐藏来保护隐私。Principal Server sync surface / Principal Server MUST：

- 仅向 reviewer set（`review_capability` 持有方）与 applicant 自身投影 application 正文；
- 对其它 Realm 成员投影占位（`{application_pending: true}`）；
- 对每次 reviewer 读取写一条 `ak.audit.accessed`（payload 包含 `application_receipt_digest` 或 profile-private application Event id 与读取者 DID）。

`applicant_visibility=members_after_join` 仅在 application 进入 `accepted` 且对应 `ak.invite.accept` 已落入 frontier 后，才允许向 Realm 成员投影正文。

### 8.2 E2EE Realm（`encryption_profile=mls_rfc9420`）

Realm 主 MLS group 不包含尚未 join 的 applicant，因此申请正文不能直接走 Realm MLS group。MUST 使用以下机制之一：

1. **Reviewer Sub-Group MLS**：Realm 维护一个独立 MLS group `ak:mls:reviewer_subgroup:<realm_id>:reviewers`，成员是当前所有 `review_capability` 持有方。applicant 通过 reviewer set 中任一成员公布的 KeyPackage 出 group commit + welcome，将 application 正文作为该 sub-group 的 application message 投递。reducer 通过 `ak.mls.commit.governance_binding` 验证 sub-group roster 与 capability 一致。

   **新加入 reviewer 的加入前 epoch 解密约束（normative，与 applicant 单向约束对称）**：新加入 reviewer sub-group 的 reviewer 与上方 applicant 单向约束对称——新 reviewer MUST NOT 获得加入其 commit 之前 epoch 的 application 解密能力。MLS forward secrecy 保证每次 reviewer roster 变更推进 epoch 后，新成员仅能解密自其加入 epoch 起的 sub-group 消息，不能解密加入前已投递的历史 application 正文。实现 SHOULD 让每条 application 投递（applicant add+remove）与每次 reviewer roster 变更各推进一次 epoch，使"哪些 reviewer 能看到哪条 application"按 epoch 边界确定。需要让新 reviewer 复核加入前的 pending application 时，MUST 由已持有该 application 明文的现任 reviewer 经显式、受审计的 re-share（如 §8.2(2) Envelope Encryption 重新封装给新 reviewer device）完成，不得依赖 sub-group 历史 key 自动回授；这是对称残留的显式声明，而非隐式放宽。

   **applicant 单向投递约束（normative）**：applicant 未 join Realm、不应成为 reviewer sub-group 的持久成员，也 MUST NOT 因投递申请而获得读取该 sub-group 后续 epoch（其他 applicant 申请、reviewer 间通信）的能力。因此：
   - applicant 加入 reviewer sub-group 的 commit 与将其移出的 commit MUST 在**同一或紧邻的 commit**内完成——投递正文后 applicant MUST 立刻被 remove，sub-group MUST 推进到不含该 applicant 的新 epoch；reducer / sub-group 维护方 MUST NOT 让 applicant 停留在 roster 中跨越多个 epoch。
   - MLS forward secrecy MUST 保证 applicant 仅能解密自己投递的那条 application message 所在 epoch 的密钥材料，不能解密其加入之前或被移出之后的任何 sub-group epoch。
   - 若实现无法保证上述单向移出（例如批处理无法在同一 ordered submit batch 或同一 Control Move 中完成 add+remove），SHOULD 改用 §8.2(2) Envelope Encryption 路径——后者天然单向，applicant 只持有面向 reviewer 的封装能力、无任何 sub-group 解密能力。
2. **Envelope Encryption to Reviewer Devices**：当 reviewer 数小于阈值（默认 `<=5`）或 sub-group 维护成本不可接受时，applicant 可使用 `encryption_envelope` 字段，对 reviewer set 中每个 reviewer 的每台有效 device 的专用 `hpke_key`（device record 公布的 X25519 HPKE 接收公钥，见 [`../crypto-media/device-lifecycle.md` §4](../crypto-media/device-lifecycle.md)）逐一封装 content key：

   - **接收公钥（normative）**：envelope 接收键 MUST 是目标 device 当前 device record 中的 `hpke_key`。**MUST NOT 以 MLS KeyPackage init key（`ak.mls.keypackage`）作为 envelope 接收键**——KeyPackage init key 是一次性 MLS join 材料，挪作通用 HPKE 接收键会破坏其一次性使用语义并构成跨协议密钥复用。
   - **scheme（normative）**：`scheme` MUST 为 [`../../artifacts/registry/hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active suite id（v1 default-MUST `ak.hpke_x25519_aead_chacha20poly1305.v1`，用法与 [`../crypto-media/device-lifecycle.md` §10.7](../crypto-media/device-lifecycle.md) 的 `ak.secret.send` 一致）；未登记 / 非 active suite MUST fail closed（`unsupported_hpke_suite`）。
   - **HPKE `info` 域分隔与 AAD 绑定（normative）**：每个 recipient 的 HPKE 封装 MUST 使用 `info = "ak.realm.member_application.envelope.v1" || 0x00 || <realm_id> || 0x00 || <application_ref>`（三段以单字节 `0x00` 连接；`application_ref` 取 §7.2 的 `application_receipt_digest`，封装时刻 receipt 尚未生成的实现 MUST 改用 stage 1 `knock_ref` event id，并在 profile 中固定所选形态）。HPKE AAD MUST 是对 `{realm_id, applicant_actor_id, application_ref, device_id}`（`device_id` 为该 recipient 的目标 device）的 canonical JSON（RFC 8785 JCS）。`info` 域分隔与 AAD 共同把密文绑定到目标 Realm、本次申请与接收设备，防止 envelope 被搬运到其它 Realm / application / device 重放或解封。
   - **recipients 上限**：`encryption_envelope.recipients[]` ≤ 64（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)）；超过时 MUST `schema_violation`。

```json
{
  "encryption_envelope": {
    "scheme": "ak.hpke_x25519_aead_chacha20poly1305.v1",
    "info": "ak.realm.member_application.envelope.v1 || 0x00 || ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5 || 0x00 || sha256:...",
    "ciphertext": "base64url:...",
    "recipients": [
      {"reviewer_actor_id": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH", "device_id": "ak:device:...", "recipient_hpke_kid": "did:webvh:...#ak_device_01HV_hpke", "enc": "base64url:...", "wrapped_key": "base64url:..."},
      {"reviewer_actor_id": "ak:did_core:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn", "device_id": "ak:device:...", "recipient_hpke_kid": "did:webvh:...#ak_device_01HW_hpke", "enc": "base64url:...", "wrapped_key": "base64url:..."}
    ]
  }
}
```

（示例中 `info` 为说明性展开，wire 上由收发两端按上文规则确定性重建，不要求随密文携带；`enc` 是每个 recipient 的 HPKE（RFC 9180）KEM 封装输出。）

reviewer 加 / 退职导致 envelope 失效时，应用层 SHOULD 提示 applicant 重提。

**Envelope recipient capability 绑定（normative）**：`encryption_envelope.recipients[]` 中列出的每个 reviewer device，applicant / 提交服务在构造 envelope 时 MUST 校验其对应 reviewer DID 在该 Event 的 CBA basis 下仍持有有效 `review_capability`，且该 device 仍是该 reviewer 当前有效 device；MUST NOT 向已撤销 capability 或已退役 device 封装 `wrapped_key`。reducer / 投递服务在投递**新** envelope 时 MUST 对每个 recipient device 重新校验上述两项（reviewer DID 仍持有有效 `review_capability`、device 仍有效未退役），任一不满足 MUST 拒绝向该 device 投递，reason `reviewer_capability_revoked`。注意这是 best-effort 前向控制：**reviewer 退职前已经解密的历史 application 正文无法被协议回收**——一旦某 device 在持有有效 capability 期间收到并解出 `wrapped_key`，撤销 capability 只能阻止后续新 envelope 投递，不能撤销既有明文副本。需要严格前向保密的部署 SHOULD 改用 §8.2(1) Reviewer Sub-Group MLS 并在 reviewer 退职时 rotate epoch。

申请正文 MUST NOT 进入 `ak.member.state{knock}` Control Move（该 Control Move 公开），所有自由文本仅出现在受加密保护的 `member.application.encryption_envelope` 中。Matrix `m.room.member{knock}.reason` 因默认对部分客户端可见而成为 spam 通道——Arkret 通过结构上禁止 knock Control Move 携带正文规避该缺陷。

## 9. Membership 状态机扩展

复用既有 `ak.member.state` 枚举（`invite / join / leave / knock / ban`），不引入新值。状态转换补充：

```text
        knock ──submit member.application──▶ knock (with application_ref projection)
            │
            ├─ review.accept ──▶ invite ──▶ join
            │      invite: ak.invite.create  projection = { invite.lifecycle -> pending,
            │                                            member.state:<invitee> knock -> invite }
            │      join:   ak.invite.accept  projection = { invite.lifecycle -> accepted,
            │                                            member.state:<invitee> invite -> join }
            ├─ review.request_changes ──▶ knock[changes_requested] (awaiting applicant revision; ttl continues)
            ├─ review.reject ──▶ leave  (with rejected_at + cooldown_until projection)
            ├─ application.cancel ──▶ leave
            └─ application_ttl 到期 ──▶ leave (reducer 自动转换，reason_code="ttl_expired")

        knock[changes_requested]
            │  (ttl 继续从原申请提交时间计时，不重置)
            ├─ applicant 修订重提 ──▶ knock[awaiting_review] (同一 application_ref)
            ├─ review.accept ──▶ invite ──▶ join
            ├─ review.reject ──▶ leave  (允许 reviewer 在 changes_requested 后直接 reject)
            ├─ application.cancel ──▶ leave
            └─ application_ttl 到期 ──▶ leave (reducer 自动转换，reason_code="ttl_expired")
```

`request_changes` 不关闭 application，也不创建 invite；它把 projection 保持在 `awaiting_review` / `changes_requested` 子状态，允许 applicant 在同一 `application_ref` 下提交修订 answer 或补充 `gate_proofs`。`application_ttl` 从原申请提交时间继续计时，除非 Realm policy 显式允许 reviewer 延长并写入新的 signed receipt；`request_changes` 不触发 `cooldown_after_reject`，也不消费 `max_open_applications_per_actor` 之外的新名额。

客户端 / 服务端 SHOULD 提供一个申请列表派生 View（View 机制见 [`../models/views.md`](../models/views.md)；该投影属于 Realm schema / 实现自定义 View，v1 不注册标准 view id），按以下分组：

- `pending`: 未决申请；
- `awaiting_review`: 已提交但 reviewer 未决；
- `accepted_pending_invite`: 审核通过但 `ak.invite.create` 尚未签发；
- `recently_decided`: 7 日内的 accept/reject 决策。

## 10. 联邦语义

跨域加入流程在 [`../sync/federation.md` §5.2](../sync/federation.md) 详述。本节仅说明 Join Policy 引入的不变量：

- `member.application` 与 `member.application.review` 都是候选 durable workflow 概念；正式登记前不得作为 v1 base profile 的 durable Event.kind 参与 federation push / pull；
- `policy_version_digest` 字段使 reviewer 与 applicant 显式承认评估时所用的 policy 快照，避免 reviewer 在不同 policy frontier 下决策导致争议；
- E2EE 场景下 reviewer sub-group MLS commit 通过既有 `ak.mls.*` 联邦机制传播；envelope encryption 由 origin Principal Server 投递到目标 reviewer 的 device list（参见 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md)）。
- `parent_membership` gate 评估需要其它 Realm 的成员 snapshot；origin reducer MAY 通过 [`../discovery/discovery-directory.md`](../discovery/discovery-directory.md) 的 verified snapshot 接口或直接 backfill；snapshot 不可达时 fail closed。

## 11. Policy Server 运行时挑战

Policy Server（[`../authz/policy-server.md`](../authz/policy-server.md)）声明 `applies_to` 包含 `join` 时，对每条 `ak.member.state{join}` Control Move 以及 `member.application` signed receipt / private record 调用 `ak.self.policy.read.check.v1` operation（默认 HTTP binding 为 `POST /_arkret/self/policy/check`）。除既有 `decision` 外，Join 场景新增 obligation 子规范：

```json
{
  "obligations": [
    {
      "type": "challenge",
      "challenge_id": "chg_01HXY9PM0AB6Y7VN2C7M4WG5KQ",
      "kinds": ["captcha", "pow"],
      "issuer": "did:webvh:zaeuR1WGwz5pkZueKCmyqGFqu:captcha.example",
      "endpoint": "https://captcha.example/challenge/01HXY9PM0AB6Y7VN2C7M4WG5KQ",
      "max_proof_age": "PT5M",
      "must_satisfy_before_resubmit": true,
      "bound_to": {
        "actor_id": "ak:did_core:webvh:z2dmjYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x",
        "action": "member.application",
        "request_canonical_digest": "sha256:...",
        "device_id": "ak:device:01964137-0000-7000-8000-000000000000"
      }
    }
  ]
}
```

applicant 完成挑战后，重新提交 join / application Control Move，在 `gate_proofs[]` 中追加 `{gate_id: "runtime:<challenge_id>", challenge_proof: {...}}`。`challenge_proof.challenge_id` 是 runtime challenge 的唯一匹配键；verifier MUST 仅按该键选择 challenge proof。Policy Server 重新校验后返回 `decision=allow`。`must_satisfy_before_resubmit=true` 时 reducer MUST 拒绝缺失对应 `challenge_id` proof 的重提。

`bound_to.request_canonical_digest` 按 [`policy-server.md` §4.1](../authz/policy-server.md) 的 proof-stripped transcript 计算：它绑定首次被 challenge 的原始 join / application 请求，而不是包含 `challenge_proof` 自身的最终重提 Control Move。重提 Control Move 除追加 runtime challenge proof 外不得改变原始请求语义；任何字段变更都必须重新走 `ak.self.policy.read.check.v1` 并获取新的 challenge。

**`max_proof_age` 过期后的重发流程（normative）**：applicant 拿到 challenge obligation 后未在 `max_proof_age` 内完成、或提交了一个 issued 时刻已超 `max_proof_age` 的 `challenge_proof` 时，reducer / Policy Server MUST 以 `failed_precondition` + `reason_code="challenge_expired"`（见 [`../../artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）拒绝该重提，MUST NOT 把过期 proof 当作满足 obligation。被拒后 applicant MUST 重新提交原始 join / application Control Move 走一次 `ak.self.policy.read.check.v1`，由 Policy Server 签发**新的** `challenge_id`（旧 `challenge_id` 不得复用满足新一轮 obligation）；applicant 对新 challenge 完成后按上文在 `gate_proofs[]` 追加对应新 `challenge_id` 的 proof。reducer MUST NOT 自动续期或自动重发 challenge——challenge 的签发权属 Policy Server，过期即作废、由 applicant 重新发起请求获取。

`obligations[].type` 注册值（`rate_limit` / `challenge` / `review_hold` / `drop_attachment`）维护在 [`../authz/policy-server.md` §4](../authz/policy-server.md) 表中；本规范是 `challenge` 类型在 join 路径上的 normative wire schema，其它路径（如 `ak.message.create`）若使用 `challenge` 必须遵循同一 envelope。

## 12. 反滥用约束

| 控制项 | 默认 | 强制要求 |
| --- | --- | --- |
| `application_ttl` | PT168H | reducer 到期自动转 `reason_code="ttl_expired"`（统一走 §7.3 受控枚举命名约定，`ttl_expired` 见 [`../../artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；不计 cooldown。 |
| `cooldown_after_reject` | PT72H | reject 后 reducer MUST 拒绝同 actor 在窗口内的新 `member.application`。`request_changes` 不触发 cooldown。 |
| `max_open_applications_per_actor` | 1 | reducer 校验 actor 当前 pending 数；超出 `failed_precondition`。 |
| Quota constraint | 由 Realm `ak.realm.policy_bundle` 声明 | 推荐对 `ak.member.state{knock}` 配置 `quota.constraint_subkind=rate`（如 `max_operations=5/day` + `constraint_scope`），通过既有 [`../authz/constraint-schema.md` §7](../authz/constraint-schema.md) 表达。 |
| Policy Server `challenge` | 高风险 Realm 推荐 | Principal Server sync surface 面对突发 knock 流量时 SHOULD 通过 Policy Server 注入 challenge obligation。 |

## 13. 与 MIMI 的映射

[`../extensions/mimi-interop.md` §9.1](../extensions/mimi-interop.md) `participation` 中 `join_policy` 子字段 SHOULD 由 facade 在 Arkret `realm.join_policy` component 与 MIMI room policy 之间双向归约；MIMI 侧暂未规范的 gate 类型作为 Arkret 专属 component 标记 `application/vnd.arkret.component+json`。MIMI facade 接收外部 join 请求时 SHOULD 至少强制执行 `claim_required` 与 `parent_membership` gate；`application_form` / `manual_review` / `challenge_response` 在 MIMI 客户端不支持 inline 表达时，facade SHOULD 拒绝跨域请求并指引 applicant 通过 Arkret 原生客户端完成。

## 14. 完整示例

公开知识社群，凭证持有者直通、否则走 5 道问卷 + CAPTCHA：

```json
{
  "candidate_kind": "realm.join_policy",
  "payload": {
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "value": {
      "combinator": "any",
      "gates": [
        {
          "gate_id": "g-vc",
          "kind": "claim_required",
          "auto_resolve": true,
          "required_claims": [
            {"claim_kind": "membership", "issuer": "did:webvh:zHqvNofxnbRjYqHgjiWCQ5jj6:openresearch.org", "status": "active"}
          ]
        },
        {
          "gate_id": "g-form",
          "kind": "application_form",
          "auto_resolve": false,
          "questions": [
            {"question_id": "q1", "answer_kind": "text", "required": true, "min_chars": 50, "max_chars": 500,
             "prompt_canonical": "Briefly describe your interest in this community."},
            {"question_id": "q2", "answer_kind": "single_choice", "required": true,
             "choices": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
             "auto_reject_if_choice_in": ["no"],
             "prompt_canonical": "Do you agree to follow the community code of conduct?"}
          ]
        },
        {
          "gate_id": "g-captcha",
          "kind": "challenge_response",
          "auto_resolve": true,
          "provider_did": "did:webvh:zaeuR1WGwz5pkZueKCmyqGFqu:captcha.example",
          "challenge_kinds": ["captcha"],
          "max_proof_age": "PT5M"
        }
      ],
      "review_capability": "ak.realm.admin",
      "reviewer_quorum": "any",
      "application_ttl": "PT168H",
      "cooldown_after_reject": "PT168H",
      "max_open_applications_per_actor": 1,
      "applicant_visibility": "reviewer_only",
      "directory_hint": {
        "summary": "Members hold an OpenResearch credential, OR complete a brief application + CAPTCHA.",
        "expected_review_time": "PT24H",
        "human_review_required": true,
        "challenge_kinds_displayed": ["captcha"]
      }
    }
  }
}
```

对应 `ak.realm.join_rule.value="knock_restricted"`：凭 VC 自动通过的走自动解析路径，其余走申请-审核路径。

> 注：本示例 `cooldown_after_reject` 显式收紧为 `PT168H`（7 天），高于 §3 字段表默认 `PT72H`；此处恰与 `application_ttl` 取同值仅为示例简洁，二者计时锚点与作用对象不同（`application_ttl` 按申请未决超时，`cooldown_after_reject` 按上次 review reject 计时），并非要求二者相等。生产部署应按需独立取值或回落默认 `PT72H`。

## 15. 规范性引用

- Realm 对象模型：[`../models/realm-and-space.md`](../models/realm-and-space.md)
- Capability 与 `ak.realm.admin`：[`../authz/capabilities.md`](../authz/capabilities.md)
- Policy Server 与 obligation：[`../authz/policy-server.md`](../authz/policy-server.md)
- Claim 与 constraint：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)
- Federation 跨域加入：[`../sync/federation.md` §5.2](../sync/federation.md)
- Discovery Directory：[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)
- Audit trail / 申诉：[`./content-moderation.md` §5.5](./content-moderation.md)（申诉流程）、[`./content-moderation.md` §10](./content-moderation.md)（审计要求）
- MIMI 互操作：[`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)
