---
title: Join Policy
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与范围

本文档定义 Realm 的 **Join Policy** 模型，覆盖 gate 组合、自动解析路径、申请-审核路径、加密语义、联邦传播、反滥用与 MIMI 映射。Realm 对象模型与 Space / hierarchy 由 `realm-and-space.md` 定义。

术语层级（normative，消歧）——本文反复出现的四个相近名词分属不同层级，MUST NOT 互换：

| 术语 | 层级 | 说明 |
| --- | --- | --- |
| **Join Policy** | 章节 / 策略域总称 | 本文定义的 gate 组合、解析顺序、加密语义与反滥用约束的统称；不是单一 wire `Event.kind`。 |
| `ck.realm.join_rule` | wire event / cell（active） | `default_join_rule` 入口模式策略事件，写入 `ck.component.realm.join_rule.v1` cell。 |
| `ck.realm.delivery_binding_policy` | wire event / cell（active） | 成员投递绑定策略事件，写入 `ck.component.realm.delivery_binding_policy.v1` cell（见 [`member-delivery-binding.md`](member-delivery-binding.md) §4）；约束成员 `delivery_binding.binding_source`，与 join gate 正交。 |
| `RealmJoinCandidate`（`realm-join-candidate.schema.json`） | 候选请求 / 评估对象 | 描述本次 join / invite-accept / knock material 可提交到哪些 Realm ingress service；方向与 `delivery_binding` 相反（见 [`member-delivery-binding.md`](member-delivery-binding.md) §2 末尾注意段）。 |

当前 v1 的 active 与 candidate surface 分层如下，base v1 实现只需要实现 active surface；application / review workflow 只在实现声明 `ck.profile.candidate.join_policy.v1` 时成为该实现的自愿承诺。

| Surface | v1 状态 | Wire 形态 | 实现要求 |
| --- | --- | --- | --- |
| `ck.realm.join_rule` | active | 标准 `Event.kind` / reducer cell | base v1 按 registry 和 reducer 规则实现 |
| `ck.realm.policy_components` 中的 join policy facet | active | 标准 policy component payload | base v1 可表达 gate、delivery binding policy 与自动解析要求 |
| `ck.member.state{membership=join}` 自动 gate | active | 标准 membership event + `gate_proofs[]` / delivery binding payload | base v1 必须 fail closed 校验 capability、gate proof 与 delivery binding |
| `ck.invite.*` + `refs[role="join_authorised_by"]` | active | 标准 invite / member refs | base v1 支持 invite 或 join-authorized grant 时必须校验引用仍有效 |
| `realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel` | candidate | 裸名 design-time concept；不得作为 `Event.kind` | 仅 `ck.profile.candidate.join_policy.v1` 实现可用 profile-private signed receipt 或私有 Event kind 承载 |

独立 join-policy Event.kind / schema 仍未进入 active registry。任何未声明 `ck.profile.candidate.join_policy.v1` 的实现 MUST 把 application / review workflow 当作未知高风险 surface，返回 `unsupported_feature`、`unsupported_event_kind`、`capability_denied` 或等价 fail-closed 结果；MUST NOT 把未注册裸名 kind 写入 shared Realm history。

`default_join_rule` 枚举（[`../models/realm-and-space.md` §2.3](../models/realm-and-space.md)）只表达粗粒度的入口模式：`public` 直接进、`invite` 必须有人邀、`knock` 可申请、`restricted` / `knock_restricted` 有附加条件、`closed` 不收新人。但是 `restricted` 的"条件"是什么、`knock` 申请里能否带结构化材料、人工审批的决策是否上链审计、CAPTCHA / proof-of-work 等运行时挑战如何接入——这些都需要本文件统一定义。

本文定义的 **Join Policy** 与 `default_join_rule` 正交又互补：

- `default_join_rule` 决定**入口模式**（`public` / `invite` / `knock` / `restricted` / `knock_restricted` / `closed`）。
- Join Policy 决定**入口模式选定后，到 `membership=join` 必须穿越的 gate 集合**（凭证、问卷、挑战、人工审批等）的组合、解析顺序、加密语义和反滥用约束。
- `default_join_rule=public` 与 `default_join_rule=closed` 不消耗 Join Policy（前者无 gate，后者无入口）；其余四个枚举值的精确语义由 §4 与 Join Policy 交叉决定。

## 2. 设计原则

1. **Gate 是组合的，不是命名的。** Realm 通过 `gates[]` + `combinator` 表达任意 AND/OR 组合；`knock_restricted` 等组合 enum 的语义由 `combinator` 直接表达，避免每加一类 gate 就要再造 enum。
2. **申请材料对外不可见。** Matrix `m.room.member{knock}` 的 free-text `reason` 因默认可见已成为 spam 通道。实现声明 `ck.profile.candidate.join_policy.v1` 并启用 application / review workflow 时，申请正文 MUST 仅对 `ck.realm.join.review` capability 持有方可见：E2EE Realm 中通过 reviewer-only encryption envelope；非 E2EE Realm 中由 Sync Service 强制访问控制并审计读取（`ck.audit.accessed`）。
3. **审核决策必须有稳定审计材料。** 实现声明 `ck.profile.candidate.join_policy.v1` 时，所有审核接受 / 拒绝 MUST 是签名且被 accepted Seal 覆盖的 Control Move、profile-private Event 或 signed receipt，记录 reviewer DID、review reason、引用证据 hash。事后审计与申诉（参见 [`./content-moderation.md` §5.5](./content-moderation.md) 申诉流程与 [`./content-moderation.md` §10](./content-moderation.md) 审计要求）依赖该 trail。
4. **审核必须密码学绑定到 join。** 借鉴 Matrix `join_authorised_via_users_server` 的担保模式：candidate profile 下随后的 `ck.invite.create` MUST 通过 `refs[role="join_authorised_by"]` 引用对应 signed review accept receipt digest；若实现 profile 已注册私有 review Event kind，MAY 引用该 Event id。reducer 校验该 ref 在写入时仍指向有效 capability 持有者。
5. **自动解析路径不强制走人工。** 当所有 gate 都可自动解析（claim presentation 验证、challenge proof 验证），applicant 可直接提交 `ck.member.state{membership=join}` Control Move，由 reducer 内联校验，无需 application / review Control Move。这条路径替代既有 `restricted` 入口模式的实质语义。
6. **Capability 仍是 allow 唯一来源。** Join Policy gate 通过即"可以提议加入"，但 reducer 仍按 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 校验 join Control Move 的 capability。Policy Server `obligations[]`（§12）只能在 capability 之上叠加额外要求（如 challenge），不能凭空创造权限。

## 3. Cell Family 与 State Event

```text
cell_id     := ck:cell:realm.join_policy.v1:<realm_id>
lattice     := cas_register
bottom      := reject
value shape := JoinPolicy（见下）
```

本 cell 的 `cell_subject` 取 `<realm_id>`（每 Realm 一个单例），与 [`member-delivery-binding.md`](member-delivery-binding.md) §4 的 `ck.component.realm.delivery_binding_policy.v1` 使用 `cell_subject=null` 的写法在语义上等价——二者都表达"per-Realm 单例 policy"，差异仅是历史保留的 subject 编码约定：join_policy cell 把 `realm_id` 编入 `cell_subject`，delivery_binding_policy cell 把 Realm 归属隐含在 cell family 并以 `null` subject 标记单例。实现 MUST NOT 据此推断二者作用域不同。

写入 cell 的候选概念在正式登记前记为 `realm.join_policy`（裸名仅是 design-time concept/action，不是 v1 wire `Event.kind`，也 MUST NOT 作为 Event envelope 的 `kind` 上链或同步），需要 `ck.policy.manage` capability（与 `ck.realm.policy_server` / `ck.realm.policy_components` 同等级）。`ck.realm.create` 时 SHOULD 通过 `ck.realm.policy_components` 一并提供 join policy 初值；省略时 cell 维持 `null`，行为退化为"`default_join_rule` 单独决定"。

JoinPolicy 候选 schema 名：`realm.join_policy.v1`。

**`candidate_kind` 信封字段（normative）**：§3 与 §14 示例顶层出现的 `candidate_kind`（如 `"candidate_kind": "realm.join_policy"`）是 **candidate surface 专用的 profile-private 信封字段**，用于在实现自有承载（signed receipt / profile-private Event kind）中标注该 payload 对应哪个 candidate concept。它**不是** Event envelope 的 `kind`（[`../models/event-and-patch.md`](../models/event-and-patch.md)），在 [`../models/common-fields.md`](../models/common-fields.md) / [`../overview/glossary.md`](../overview/glossary.md) 中无登记，也 MUST NOT 作为 `Event.kind` 上链或进入 shared Realm wire / federation。`candidate_kind` 取裸名 candidate concept（`realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel`），仅在声明 `ck.profile.candidate.join_policy.v1` 的实现内部、其 profile-private 承载层有效。§7.2 / §7.3 在 prose 中直接用裸名引用同一组 candidate concept，二者指向一致；区别仅是 §3 / §14 给出带 `candidate_kind` 包装的具体 payload 示例形态。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `gates` | yes | `array<Gate>` | 1..16 项；空数组 MUST schema_violation。 | 必须穿越的 gate 列表。 |
| `combinator` | yes | `enum(all, any)` | 无默认值；producer MUST 显式写入。 | gate 之间的组合语义。 |
| `review_capability` | conditional | `string` | 任一 gate `kind ∈ {manual_review, application_form}` 时必填；wire payload MUST 显式写入。 | 审核所需 capability，取 **capability action token** 形态（如 `ck.realm.join.review`），不是 grant id 引用；与 §7.3 `reviewer_capability_proof`（引用授予该 action 的 **grant id** + frontier digest）是两个不同概念。[^review-capability-alias] |

[^review-capability-alias]: 该字段语义是 *被授权 reviewer 所持的 capability action token*，不是 grant id 引用。v1 wire 字段名为 `review_capability`，不会改变。（未来版本对该字段的 prose alias 规划属 roadmap 范畴，不在 v1 normative 范围内。）
| `reviewer_quorum` | no | `enum(any, majority, all) \| object` | 默认 `any`。`object` 形式 `{ threshold: int, reviewers: did[] }` 表达 N-of-M。 | 审核法定人数。 |
| `application_ttl` | no | `duration` | 默认 `PT168H`，最小 `PT1H`，最大 `P1Y`。 | 申请未决超时即失效。 |
| `cooldown_after_reject` | no | `duration` | 默认 `PT72H`。 | 拒绝后同一 actor 重新申请的最短间隔。 |
| `max_open_applications_per_actor` | no | `integer` | 默认 `1`，最大 `5`。 | 同一 actor 在本 Realm 同时未决申请上限。 |
| `applicant_visibility` | no | `enum(reviewer_only, members_after_join, public)` | 默认 `reviewer_only`。 | 申请正文谁可见；`members_after_join` 表示 join 成功后开放给 Realm 成员（用于自我介绍场景）。 |
| `directory_hint` | no | `object` | 见 §3.2。 | Discovery Directory 公开投影所需 hint。 |

**`reviewer_quorum` 解析规则（normative）**：

- object 形式 `{ threshold, reviewers }`（N-of-M）写入时，reducer MUST 校验 `threshold <= |unique reviewers|`（`reviewers[]` 按 DID 去重后的元素数；[`event-payload.schema.json#/$defs/join_policy_payload`](../../artifacts/schemas/event-payload.schema.json) 已对 `reviewers` 声明 `uniqueItems: true`）。不满足时 MUST 以 `schema_violation` 拒绝该 policy 写入。
- `majority` / `all` 的分母（reviewer 总数）与单个 reviewer 的资格（是否持有 `review_capability`）MUST 按**各 review accept Event 的 CBA basis** 取值（与 §5 "Gate predicate 评估时点"同一模型）。某条 accept 按其 basis 计入后，该 reviewer 在后续 Seal 失去 capability **不**追溯使既有 accept 失效；它只影响该 reviewer 此后新的 review 决策与新 envelope 投递（§8.2）。

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

- `gate_id`：稳定 id，用于审计与 application 中的 proof 关联。**`gate_id` MUST 在 `gates[]` 中唯一**——重复值 MUST 触发 `schema_violation`（`reason_code=join_policy_duplicate_gate_id`，见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）。enforcement 由三层组成：(a) [`event-payload.schema.json#/$defs/join_policy_payload`](../../artifacts/schemas/event-payload.schema.json) 在 `gates` 数组上声明 `uniqueItems: true`，捕获**整对象重复**的 gate；(b) JSON Schema 2020-12 无法以纯 schema 表达"按字段属性去重"，因此 [`tools/lint_artifacts.py` `check_join_policy_gate_id_uniqueness`](../../../../tools/lint_artifacts.py) 在 fixture 与 Markdown JSON 示例中机械拒绝**按 `gate_id` 去重**的违例；(c) reducer 在 wire 上再做一次 `gate_id` 唯一性校验并以上述 reason_code 拒绝。三层共同构成机器可执行的闭环。
- `kind`：取 `claim_required` / `application_form` / `challenge_response` / `manual_review` / `parent_membership` / `principal_admission` / `cooldown` 之一
- `auto_resolve`：该 gate 能否仅靠 applicant 提交的材料解析；`manual_review` / `application_form` 必为 `false`
- 其余字段按 `kind` 决定（见下表）

| `kind` | 必带字段 | 语义 | `auto_resolve` |
| --- | --- | --- | --- |
| `claim_required` | `requires_claims[]`（见 [`../authz/constraint-schema.md` §10](../authz/constraint-schema.md)） | applicant MUST 提交满足声明集合的 VC / claim presentation。 | `true` |
| `parent_membership` | `membership_source_realm_ids: id:realm[]`、`require_min_membership: enum(invite, join)` | applicant MUST 已是任一 source Realm 的指定成员；该字段只是 membership gate 的验证来源，不表达 Realm 树形父子关系。reducer 在 join Control Move 校验时必须能够独立验证（snapshot 或 backfill）。等价于 Matrix MSC3083 `m.room_membership` 条件。 | `true` |
| `principal_admission` | 至少一个 selector 字段：`allowed_did_methods[]`、`allowed_principal_dids[]`、`denied_principal_dids[]` | applicant 的 principal DID 自身 MUST 满足 Realm 声明的硬准入条件。典型用途是只允许特定 DID method 或显式 allowlist 中的 principal 加入。 | `true` |
| `challenge_response` | `provider_did: did`、`challenge_kinds: enum(captcha, pow, attested_human, idp_oidc)[]`、`max_proof_age: duration` | applicant MUST 完成 provider 颁发的挑战并提交 signed proof。详见 §12。 | `true` |
| `application_form` | `questions[]`（见 §3.3） | applicant MUST 在 `member.application` 中提交对应 answer；reviewer 人工评估。 | `false` |
| `manual_review` | （无额外字段） | reviewer 必须显式签署 accept；不要求结构化问卷。 | `false` |
| `cooldown` | `min_interval_since_leave: duration` | applicant 上次 `ck.member.state{membership=leave}` 后未达冷却期 MUST 拒绝。仅作为 deny gate（与 `combinator` 无关，单独评估；亦不计入 §5 "applicant 拟使用的 gate 子集"的 `auto_resolve` 全称校验，见 §5）。此 gate 的语义是 **leave-cooldown**（按上次主动 leave 计时），prose / SDK 推荐用 `leave_cooldown` 称呼以区别于 §3 顶层字段 `cooldown_after_reject`（后者按上次 **review reject** 计时，作用于 `member.application` 重提，二者计时锚点、作用对象完全不同）。 | `true` |

未注册 `kind` MUST schema_violation；未注册的 `(kind, subfield)` 组合按 lattice `bottom=reject` 处理。

#### `principal_admission`

`principal_admission` 是自动解析 gate，用于约束提交 `ck.member.state{membership="join"}` 的 `actor_id` / `payload.actor_id` 所指 principal DID。它只判断 principal DID 本身，不替代 capability、invite、review、claim presentation、DID Document 解析、service delegation 或 [`member-delivery-binding.md`](./member-delivery-binding.md) 的投递绑定校验。

字段：

- `allowed_did_methods[]`：允许的 DID method 列表，元素使用完整 `did:<method>` 标签（例如 `did:webvh`、`did:web`、`did:key`）。空或缺省表示不按 method 限制。
- `allowed_principal_dids[]`：可选精确 allowlist。非空时 applicant DID MUST 等于其中一个值。
- `denied_principal_dids[]`：可选精确 denylist。denylist 优先级最高；命中时 MUST 拒绝，即使也命中 allowlist。

`principal_admission` 至少 MUST 声明一个 selector 字段（上述三个数组之一非空，或实现 profile 明确声明的等价 selector），否则 reducer MUST 以 `schema_violation` 拒绝 policy 写入。多个 selector 字段按 AND 组合，denylist 先于 allowlist 评估。

`principal_admission` 是 hard pre-admission gate：只要 Join Policy 中出现该 gate，reducer MUST 在普通 `combinator` 解析、application form 或 manual review 之前先评估它；任一 `principal_admission` gate 失败时，当前 join / knock / application MUST fail closed，applicant 不得通过其它 gate 或人工审核路径绕过 principal 准入约束。

加入失败对外 MUST 使用通用 `gate_check_failed`，不得向 external applicant 区分"method 不允许"、"DID 不在 allowlist"、"DID 在 denylist"等细节；细节 MAY 写入 reviewer / admin 可见审计日志。

示例：

```json
{
  "gates": [
    {
      "gate_id": "principal-users-acme",
      "kind": "principal_admission",
      "auto_resolve": true,
      "allowed_did_methods": ["did:webvh"],
      "allowed_principal_dids": [
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
    "requires_human_review": true,
    "challenge_kinds_displayed": ["captcha"]
  }
}
```

`questions[]` 正文 MUST NOT 出现在 hint 中；公开 question prompt 是 opt-in（每个 question 独立 `disclosed_in_directory: bool`）。

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

单个 `application_form` gate 的 `questions[]` MUST ≤ 64 项（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)）；超过时 MUST `schema_violation`。

## 4. 与 `default_join_rule` 的交叉表

| `default_join_rule` | Join Policy 是否生效 | 等价 gate 组合 |
| --- | --- | --- |
| `public` | 不生效 | applicant 提交 `ck.member.state{join}` 即被接受。 |
| `invite` | 不生效 | 必须有 `ck.invite.create`；Join Policy 不可绕过 invite。 |
| `knock` | 生效（任一路径） | gate 集合可包含人工审核；申请-审核路径必走。 |
| `restricted` | 生效（自动解析路径） | `gates[*].auto_resolve == true` MUST 全为 true；含 `manual_review` 或 `application_form` MUST schema_violation。 |
| `knock_restricted` | 生效（OR 合成） | `combinator` SHOULD 为 `any`；典型组合：`[claim_required(auto), application_form(manual)]`，凭证持有者直接进，否则走问卷申请。 |
| `closed` | 不生效 | reducer 拒绝任何 join / knock / application Control Move。 |

reducer 在 `ck.realm.join_rule` 与 join-policy cell 任一变更时 MUST 重新评估上述一致性约束；不一致 MUST `failed_precondition` 拒绝写入，并附带 `reason="join_rule_policy_mismatch"`。

## 5. 自动解析路径

适用条件：`default_join_rule ∈ {public, restricted, knock_restricted}` 且 applicant 拟使用的 gate 子集全部 `auto_resolve=true`。

**deny-only gate 不计入"拟使用子集"（normative）**：`cooldown` 这类 deny-only gate（§3.1）始终独立、强制评估，applicant 无法选择"使用 / 不使用"，因此**不计入**上述"applicant 拟使用的 gate 子集"的 `auto_resolve` 全称校验；它们虽标注 `auto_resolve=true`，但其角色是 pre-evaluation deny，不是 applicant 可选的解析门。相应地，§4 中 `restricted` 生效时"`gates[*].auto_resolve == true` 全为 true"与"含 `manual_review` / `application_form` MUST schema_violation"的 schema 校验只针对 **non-deny gate**——deny-only gate 始终独立评估，既不破坏 restricted 的全称约束，也不被计入 applicant 子集。

applicant 直接提交：

```json
{
  "kind": "ck.member.state",
  "payload": {
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "actor_id": "did:webvh:z2dmjYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x:users.example:bob",
    "membership": "join",
    "delivery_status": "routable",
    "delivery_binding": {
      "recipient_service_did": "did:web:principal.org-a.example",
      "recipient_service_type": "principal_server",
      "binding_scope": "realm",
      "binding_source": "explicit",
      "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
      "service_acceptance_ref": "ck:event:0196419b-0000-7000-8000-000000000001"
    },
    "gate_proofs": [
      {
        "gate_id": "g-org-vc",
        "claim_presentation": "jws-vc:eyJhbGciOiJFZERTQSJ9..."
      },
      {
        "gate_id": "g-captcha",
        "challenge_proof": {
          "challenge_id": "chg_01HXY9PM0AB6Y7VN2C7M4WG5KQ",
          "issued_by": "did:web:captcha.example",
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
5. 全部通过则接受 `membership=join`；任一失败 `failed_precondition`，附带 `reason_code` 指明哪个 gate fail 与原因。

reducer MUST NOT 在自动解析路径上隐式生成 application / review Control Move——此路径绕过申请-审核状态机。

**外部 applicant 失败不可枚举（normative）**：对尚未 join 的外部 applicant，wire 响应 MUST 统一为 `failed_precondition` + `reason_code=gate_check_failed`（或 invite / directory surface 已定义的统一不可枚举错误），不得区分“claim 从未签发”、“claim 已撤销”、“issuer 暂时不可达”、“parent membership 不满足”或“challenge proof 失效”。Reducer / audit log MAY 记录内部 diagnostic reason、gate_id 与 issuer 状态，但这些字段不得出现在 applicant 可见响应、directory hint 或 push/notification payload 中。Reviewer-only application workflow 可以在加密 reviewer envelope 内展示更细原因。

**Gate predicate 评估时点（normative）**：所有 gate predicate（包括 claim issuer revocation、challenge provider signature、`cooldown`、parent membership、capability presence 检查）MUST 仅对该 join Control Move 的 `seal_basis` 指向的控制面 view 求值，与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 的 CBA basis 模型一致。同一 ordered submit batch 内并发的 `ck.capability.revoke` / policy 变更 / `ck.realm.join_rule` 更新对**本批次**的 join Control Move **不**生效；它们仅从后续 Seal 起影响 gate 评估。这意味着：

- 同批中"先撤销 review capability，后 join"的攻击模式不会让 join 通过 review-gated 路径——gate 仍按 pre-state 看到完整 capability。
- 反之，同批中"先发 grant，后用 grant 满足 gate" 也不会被 reducer 当作满足——授权与 Control Move 的可见性以 CBA basis 为单位。
- 与本规范 §3.1 中 `combinator` 的"deny gate（如 cooldown）独立评估"规则共存：cooldown 等 pre-evaluation deny gate 同样基于 CBA basis 触发，且不参与 combinator。

## 6. 成员投递绑定

> 成员投递绑定（effective delivery binding）的接受准则、`binding_source` 与责任方、`ck.realm.delivery_binding_policy` policy 事件、路由不可降级、rebind 过渡、单 binding + 多设备策略与关联性 / 隐私边界，已拆分为独立文件 [`member-delivery-binding.md`](member-delivery-binding.md)。
>
> delivery binding 与 join gate **正交**：join gate（本文）决定“能否加入”，delivery binding 决定“加入后 events / sync / to-device / push / key-package 投递到哪个 Principal Server”。两者方向、生命周期、授权来源均不同，MUST NOT 互相推导。

## 7. 申请-审核路径

适用条件：`default_join_rule ∈ {knock, knock_restricted}` 且至少一个 gate `auto_resolve=false`。

### 7.1 阶段

| 阶段 | Control Move | 写入方 |
| --- | --- | --- |
| 1. 敲门 | `ck.member.state{membership=knock}` | applicant |
| 2. 提交申请 | `member.application` | applicant |
| 3. 审核决策 | `member.application.review` | reviewer（持 `review_capability`） |
| 4. 接受邀请（隐式） | `ck.invite.create` + `ck.invite.accept` | reviewer 与 applicant |

reducer MUST 接受 stage 1 与 stage 2 在同一 batch 内提交；client SHOULD 把它们打包到同一 Seal request 以减少 round trip。

### 7.2 `member.application`

候选申请概念；schema 名 `member.application.v1`。正式进入 v1 registry 前，`member.application` 不得作为 Event envelope 的 `kind` 使用，也不得使用 `ck.*` 标准前缀伪装成 active contract；生产实现若启用本 workflow，必须在自有 profile 中声明唯一承载方式，并输出可引用的 signed application receipt（`application_receipt_digest`），供后续 review / invite / audit 引用。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `realm_id` | yes | `id:realm` | 申请目标 Realm。 |
| `applicant_did` | yes | `did` | 等于 envelope `actor_id`。 |
| `knock_ref` | yes | `event_ref` | 引用 stage 1 的 `ck.member.state{knock}` event id。 |
| `policy_version_digest` | yes | `hash` | 提交时 `realm.join_policy` cell value 的 canonical digest；reducer 校验 reviewer 决策时是否仍是同一 policy。 |
| `answers` | conditional | `array<Answer>` | 任一 `application_form` gate 存在时必填，覆盖该 gate 所有 `required=true` 的 question_id。 |
| `gate_proofs` | conditional | `array<GateProof>` | 任一可自动解析 gate 存在时按需提供（与自动解析路径同形）。 |
| `applicant_note` | no | `string` | 1..2000 chars 自由文本备注。 |
| `encryption_envelope` | conditional | `object` | E2EE Realm 必填；见 §8。 |

`Answer` 形态：`{question_id, value: string|string[]|boolean}`；reducer 仅做存在性 / shape 校验，语义评估留给 reviewer。`answers[]` MUST ≤ 64 项（与 §3.3 `questions[]` 上限对齐）、`gate_proofs[]` MUST ≤ 16 项（与 §3 `gates` 1..16 上限对齐）；超过时 MUST `schema_violation`（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)）。

### 7.3 `member.application.review`

签名 review workflow record，需要 `review_capability`。在正式注册为 v1 active Event kind 前，它不是 base profile 的 durable `Event.kind`；实现必须把 review 结果承载为自有 profile 声明的 signed review receipt（`review_receipt_digest`），或承载在该 profile 自己注册的私有 Event kind 中。任何 `ck.invite.create` 对 review 的引用 MUST 指向稳定 receipt digest 或该私有 Event id，不得引用未注册的裸名 kind。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `realm_id` | yes | `id:realm` |  |
| `application_ref` | yes | `receipt_digest` 或 profile-private `event_ref` | 指向 §7.2 的 signed application receipt；若实现 profile 已注册私有 application Event kind，MAY 指向该私有 Event id。不得引用未注册的裸名 `member.application`。 |
| `decision` | yes | `enum(accept, reject, request_changes)` | review **结果**由本字段承载（accept / reject / request_changes），等价于本文件族 §5.5 appeal 的 `verdict` 角色。`request_changes` 允许 applicant 修订 answer 后重提，不计入 cooldown。 |
| `reason_code` | conditional | `string` | 稳定**拒绝 / 变更细分原因码**：`incomplete_answers` / `policy_violation` / `claim_invalid` / `challenge_failed` / `duplicate` / `ttl_expired`（reducer 自动超时拒绝，见 §12）/ `other`。`decision ∈ {reject, request_changes}` 时必填；`decision=accept` 时省略或取保留值 `ok`（`ok` 不承载独立语义，成功结果由 `decision=accept` 表达）。本字段遵循 [`../models/common-fields.md` §2](../models/common-fields.md)（受控枚举用 `_code` 后缀），仅承载拒绝 / 变更细分，不兼表成功裁决。 |
| `reason_text` | no | `string` | 1..1000 chars 自由文本，对 applicant 可见。 |
| `evidence_refs` | no | `event_ref[]` / `hash[]` | 评审依据的其它 event 或 signed receipt（如 `ck.audit.*` 风险记录）。 |
| `reviewer_capability_proof` | yes | `object` | 引用授予 reviewer `review_capability`（§3 中那个 capability **action token**）的 **grant id** 与当时 frontier digest；reducer 必须在写入时再校验一次。注意：本字段承载 grant id 引用，`review_capability` 承载 action token，二者勿混用。 |

`reviewer_quorum != "any"` 时，reducer 需收集 N 个独立 reviewer 的 accept 才认为申请进入 `accepted` 状态；任一 reject 即终止。quorum 判定 MUST 遵循 §3 的 `reviewer_quorum` 解析规则：`majority` / `all` 的分母与 reviewer 资格按各 accept Event 的 CBA basis 取值；accept 计入后 reviewer 失去 capability 不追溯使该 accept 失效。

**review reason_code / reason_text 可见性（normative）**：§7.3 的细粒度 `reason_code` 与 `reason_text` 只在 applicant **已提交 stage 1 `ck.member.state{knock}`**（即进入半信任的申请-审核状态机）后，才 MAY 对该 applicant 自身可见。这与 §5 自动解析路径"外部 applicant 失败不可枚举"不冲突：尚未 knock 的外部探测者仍只能看到统一不可枚举错误，细粒度 review 原因 MUST NOT 出现在 directory hint、discovery surface、push / notification payload 或任何未经 knock 的 caller 可见响应中。换言之，半信任边界由"是否已 knock"划定——knock 之前等同自动路径的不可枚举约束，knock 之后才解锁面向本人的 review reason。

### 7.4 `member.application.cancel`

applicant 可主动撤回；写入独立 `member.application.cancel` record，携带 `application_ref`、`cancelled_by`、`cancelled_at` 和可选 `reason_text`，不写入 §7.3 的 `decision` 字段，也不计 cooldown。

### 7.5 接受后的 invite

application 进入 `accepted` 状态后：

1. 任一 reviewer 提交 `ck.invite.create`，`refs[role="join_authorised_by"]` MUST 引用对应 `member.application.review{accept}` 的 signed review receipt digest；若实现 profile 已注册私有 review Event kind，MAY 引用该 Event id。`reviewer_quorum` 为 object 形式（N-of-M）时，`refs[role="join_authorised_by"]` MUST 引用**满足 `threshold` 的全部** review accept receipt digest（每条计入 quorum 的 accept 各一条 ref），使 reducer 与审计方可独立复核 quorum 在引用的 accept 集合上成立；
2. applicant 提交 `ck.invite.accept`；
3. reducer 在写入 `ck.invite.create` 时再次校验：被引用的 review accept 仍指向尚未消费的 application（防止同一 accept 被复用）、reviewer 在当前 frontier 仍持有 `review_capability`、application 未过 `application_ttl`、未被后续 `reject` / `cancel` 覆盖。

校验失败 `failed_precondition`，`reason_code="join_authorisation_invalid"`。

## 8. 加密与隐私

### 8.1 非 E2EE Realm

`member.application` 的共享 durable wire payload 即使在非 E2EE Realm 中也只能包含最小化 metadata（application id、applicant DID、policy digest、receipt digest、状态与时间戳）。申请正文、answers、自由文本、3PID、附件和 reviewer-only 诊断 MUST 放入 reviewer encryption envelope 或实现 profile 声明的受保护 private record；不得仅依赖 projection 隐藏来保护隐私。Sync Service / Principal Server MUST：

- 仅向 reviewer set（`review_capability` 持有方）与 applicant 自身投影 application 正文；
- 对其它 Realm 成员投影占位（`{application_pending: true}`）；
- 对每次 reviewer 读取写一条 `ck.audit.accessed`（payload 包含 `application_receipt_digest` 或 profile-private application Event id 与读取者 DID）。

`applicant_visibility=members_after_join` 仅在 application 进入 `accepted` 且对应 `ck.invite.accept` 已落入 frontier 后，才允许向 Realm 成员投影正文。

### 8.2 E2EE Realm（`encryption_profile=mls_rfc9420`）

Realm 主 MLS group 不包含尚未 join 的 applicant，因此申请正文不能直接走 Realm MLS group。MUST 使用以下机制之一：

1. **Reviewer Sub-Group MLS**：Realm 维护一个独立 MLS group `ck:mls:reviewer_subgroup:<realm_id>:reviewers`，成员是当前所有 `review_capability` 持有方。applicant 通过 reviewer set 中任一成员公布的 KeyPackage 出 group commit + welcome，将 application 正文作为该 sub-group 的 application message 投递。reducer 通过 `ck.mls.commit.governance_binding` 验证 sub-group roster 与 capability 一致。

   **applicant 单向投递约束（normative）**：applicant 未 join Realm、不应成为 reviewer sub-group 的持久成员，也 MUST NOT 因投递申请而获得读取该 sub-group 后续 epoch（其他 applicant 申请、reviewer 间通信）的能力。因此：
   - applicant 加入 reviewer sub-group 的 commit 与将其移出的 commit MUST 在**同一或紧邻的 commit**内完成——投递正文后 applicant MUST 立刻被 remove，sub-group MUST 推进到不含该 applicant 的新 epoch；reducer / sub-group 维护方 MUST NOT 让 applicant 停留在 roster 中跨越多个 epoch。
   - MLS forward secrecy MUST 保证 applicant 仅能解密自己投递的那条 application message 所在 epoch 的密钥材料，不能解密其加入之前或被移出之后的任何 sub-group epoch。
   - 若实现无法保证上述单向移出（例如批处理无法在同一 ordered submit batch 或同一 Control Move 中完成 add+remove），SHOULD 改用 §8.2(2) Envelope Encryption 路径——后者天然单向，applicant 只持有面向 reviewer 的封装能力、无任何 sub-group 解密能力。
2. **Envelope Encryption to Reviewer Devices**：当 reviewer 数小于阈值（默认 `<=5`）或 sub-group 维护成本不可接受时，applicant 可使用 `encryption_envelope` 字段，对 reviewer set 中每个 reviewer 的每台有效 device 的专用 `hpke_key`（device record 公布的 X25519 HPKE 接收公钥，见 [`../crypto-media/device-lifecycle.md` §4](../crypto-media/device-lifecycle.md)）逐一封装 content key：

   - **接收公钥（normative）**：envelope 接收键 MUST 是目标 device 当前 device record 中的 `hpke_key`。**MUST NOT 以 MLS KeyPackage init key（`ck.mls.keypackage`）作为 envelope 接收键**——KeyPackage init key 是一次性 MLS join 材料，挪作通用 HPKE 接收键会破坏其一次性使用语义并构成跨协议密钥复用。
   - **scheme（normative）**：`scheme` MUST 为已注册的 `ck.hpke_x25519_aead_xchacha20poly1305.v1`（用法与 [`../crypto-media/device-lifecycle.md` §10.7](../crypto-media/device-lifecycle.md) 的 `ck.secret.send` 一致）。
   - **HPKE `info` 域分隔与 AAD 绑定（normative）**：每个 recipient 的 HPKE 封装 MUST 使用 `info = "ck.realm.member_application.envelope.v1" || 0x00 || <realm_id> || 0x00 || <application_ref>`（三段以单字节 `0x00` 连接；`application_ref` 取 §7.2 的 `application_receipt_digest`，封装时刻 receipt 尚未生成的实现 MUST 改用 stage 1 `knock_ref` event id，并在 profile 中固定所选形态）。HPKE AAD MUST 是对 `{realm_id, applicant_did, application_ref, device_id}`（`device_id` 为该 recipient 的目标 device）的 canonical JSON（RFC 8785 JCS）。`info` 域分隔与 AAD 共同把密文绑定到目标 Realm、本次申请与接收设备，防止 envelope 被搬运到其它 Realm / application / device 重放或解封。
   - **recipients 上限**：`encryption_envelope.recipients[]` ≤ 64（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)）；超过时 MUST `schema_violation`。

```json
{
  "encryption_envelope": {
    "scheme": "ck.hpke_x25519_aead_xchacha20poly1305.v1",
    "info": "ck.realm.member_application.envelope.v1 || 0x00 || ck:realm:0196419b-0000-7000-8000-000000000000 || 0x00 || sha256:...",
    "ciphertext": "base64url:...",
    "recipients": [
      {"reviewer_did": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:users.example:alice", "device_id": "ck:device:...", "recipient_hpke_kid": "did:webvh:...#ck_device_01HV_hpke", "enc": "base64url:...", "wrapped_key": "base64url:..."},
      {"reviewer_did": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:carol", "device_id": "ck:device:...", "recipient_hpke_kid": "did:webvh:...#ck_device_01HW_hpke", "enc": "base64url:...", "wrapped_key": "base64url:..."}
    ]
  }
}
```

（示例中 `info` 为说明性展开，wire 上由收发两端按上文规则确定性重建，不要求随密文携带；`enc` 是每个 recipient 的 HPKE（RFC 9180）KEM 封装输出。）

reviewer 加 / 退职导致 envelope 失效时，应用层 SHOULD 提示 applicant 重提。

**Envelope recipient capability 绑定（normative）**：`encryption_envelope.recipients[]` 中列出的每个 reviewer device，applicant / 提交服务在构造 envelope 时 MUST 校验其对应 reviewer DID 在该 Event 的 CBA basis 下仍持有有效 `review_capability`，且该 device 仍是该 reviewer 当前有效 device；MUST NOT 向已撤销 capability 或已退役 device 封装 `wrapped_key`。reducer / 投递服务在投递**新** envelope 时 MUST 对每个 recipient device 重新校验上述两项（reviewer DID 仍持有有效 `review_capability`、device 仍有效未退役），任一不满足 MUST 拒绝向该 device 投递，reason `reviewer_capability_revoked`。注意这是 best-effort 前向控制：**reviewer 退职前已经解密的历史 application 正文无法被协议回收**——一旦某 device 在持有有效 capability 期间收到并解出 `wrapped_key`，撤销 capability 只能阻止后续新 envelope 投递，不能撤销既有明文副本。需要严格前向保密的部署 SHOULD 改用 §8.2(1) Reviewer Sub-Group MLS 并在 reviewer 退职时 rotate epoch。

申请正文 MUST NOT 进入 `ck.member.state{knock}` Control Move（该 Control Move 公开），所有自由文本仅出现在受加密保护的 `member.application.encryption_envelope` 中。Matrix `m.room.member{knock}.reason` 因默认对部分客户端可见而成为 spam 通道——Cokret 通过结构上禁止 knock Control Move 携带正文规避该缺陷。

## 9. Membership 状态机扩展

复用既有 `ck.member.state` 枚举（`invite / join / leave / knock / ban`），不引入新值。状态转换补充：

```text
        knock ──submit member.application──▶ knock (with application_ref projection)
            │
            ├─ review.accept ──▶ invite (via ck.invite.create) ──▶ join (via ck.invite.accept)
            ├─ review.request_changes ──▶ knock (awaiting applicant revision; ttl continues)
            ├─ review.reject ──▶ leave  (with rejected_at + cooldown_until projection)
            ├─ application.cancel ──▶ leave
            └─ application_ttl 到期 ──▶ leave (reducer 自动转换，reason_code="ttl_expired")
```

`request_changes` 不关闭 application，也不创建 invite；它把 projection 保持在 `awaiting_review` / `changes_requested` 子状态，允许 applicant 在同一 `application_ref` 下提交修订 answer 或补充 `gate_proofs`。`application_ttl` 从原申请提交时间继续计时，除非 Realm policy 显式允许 reviewer 延长并写入新的 signed receipt；`request_changes` 不触发 `cooldown_after_reject`，也不消费 `max_open_applications_per_actor` 之外的新名额。

客户端 / 服务端 SHOULD 提供一个申请列表派生 View（View 机制见 [`../models/views.md`](../models/views.md)；该投影属于 Realm schema / 实现自定义 View，v1 不注册标准 view id），按以下分组：

- `pending`: 未决申请；
- `awaiting_review`: 已提交但 reviewer 未决；
- `accepted_pending_invite`: 审核通过但 `ck.invite.create` 尚未签发；
- `recently_decided`: 7 日内的 accept/reject 决策。

## 10. 联邦语义

跨域加入流程在 [`../sync/federation.md` §5.2](../sync/federation.md) 详述。本节仅说明 Join Policy 引入的不变量：

- `member.application` 与 `member.application.review` 都是候选 durable workflow 概念；正式登记前不得作为 v1 base profile 的 durable Event.kind 参与 federation push / pull；
- `policy_version_digest` 字段使 reviewer 与 applicant 显式承认评估时所用的 policy 快照，避免 reviewer 在不同 policy frontier 下决策导致争议；
- E2EE 场景下 reviewer sub-group MLS commit 通过既有 `ck.mls.*` 联邦机制传播；envelope encryption 由 origin Principal Server 投递到目标 reviewer 的 device list（参见 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md)）。
- `parent_membership` gate 评估需要其它 Realm 的成员 snapshot；origin reducer MAY 通过 [`../discovery/discovery-directory.md`](../discovery/discovery-directory.md) 的 verified snapshot 接口或直接 backfill；snapshot 不可达时 fail closed。

## 11. Policy Server 运行时挑战

Policy Server（[`../authz/policy-server.md`](../authz/policy-server.md)）声明 `applies_to` 包含 `join` 时，对每条 `ck.member.state{join}` Control Move 以及 `member.application` signed receipt / private record 调用 `ck.self.policy.check` operation（默认 HTTP binding 为 `POST /_cokret/self/policy/check`）。除既有 `decision` 外，Join 场景新增 obligation 子规范：

```json
{
  "obligations": [
    {
      "type": "challenge",
      "challenge_id": "chg_01HXY9PM0AB6Y7VN2C7M4WG5KQ",
      "kinds": ["captcha", "pow"],
      "issuer": "did:web:captcha.example",
      "endpoint": "https://captcha.example/challenge/01HXY9PM0AB6Y7VN2C7M4WG5KQ",
      "max_proof_age": "PT5M",
      "must_satisfy_before_resubmit": true,
      "bound_to": {
        "actor_id": "did:webvh:z2dmjYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x:users.example:applicant",
        "action": "member.application",
        "request_canonical_digest": "sha256:...",
        "device_id": "ck:device:01964137-0000-7000-8000-000000000000"
      }
    }
  ]
}
```

applicant 完成挑战后，重新提交 join / application Control Move，在 `gate_proofs[]` 中追加 `{gate_id: "runtime:<challenge_id>", challenge_proof: {...}}`。`challenge_proof.challenge_id` 是 runtime challenge 的唯一匹配键；verifier MUST 仅按该键选择 challenge proof。Policy Server 重新校验后返回 `decision=allow`。`must_satisfy_before_resubmit=true` 时 reducer MUST 拒绝缺失对应 `challenge_id` proof 的重提。

`bound_to.request_canonical_digest` 按 [`policy-server.md` §4.1](../authz/policy-server.md) 的 proof-stripped transcript 计算：它绑定首次被 challenge 的原始 join / application 请求，而不是包含 `challenge_proof` 自身的最终重提 Control Move。重提 Control Move 除追加 runtime challenge proof 外不得改变原始请求语义；任何字段变更都必须重新走 `ck.self.policy.check` 并获取新的 challenge。

`obligations[].type` 注册值（`rate_limit` / `challenge` / `review_hold` / `drop_attachment`）维护在 [`../authz/policy-server.md` §4](../authz/policy-server.md) 表中；本规范是 `challenge` 类型在 join 路径上的 normative wire schema，其它路径（如 `ck.message.create`）若使用 `challenge` 必须遵循同一 envelope。

## 12. 反滥用约束

| 控制项 | 默认 | 强制要求 |
| --- | --- | --- |
| `application_ttl` | PT168H | reducer 到期自动转 `reason_code="ttl_expired"`（统一走 §7.3 受控枚举命名约定，`ttl_expired` 见 [`../../artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；不计 cooldown。 |
| `cooldown_after_reject` | PT72H | reject 后 reducer MUST 拒绝同 actor 在窗口内的新 `member.application`。`request_changes` 不触发 cooldown。 |
| `max_open_applications_per_actor` | 1 | reducer 校验 actor 当前 pending 数；超出 `failed_precondition`。 |
| Quota constraint | 由 Realm `ck.realm.policy_components` 声明 | 推荐对 `ck.member.state{knock}` 配置 `quota.subtype=rate`（如 `max_operations=5/day`），通过既有 [`../authz/constraint-schema.md` §7](../authz/constraint-schema.md) 表达。 |
| Policy Server `challenge` | 高风险 Realm 推荐 | Sync Service 面对突发 knock 流量时 SHOULD 通过 Policy Server 注入 challenge obligation。 |

## 13. 与 MIMI 的映射

[`../extensions/mimi-interop.md` §9.1](../extensions/mimi-interop.md) `participation` 中 `join_policy` 子字段 SHOULD 由 facade 在 Cokret `realm.join_policy` component 与 MIMI room policy 之间双向归约；MIMI 侧暂未规范的 gate 类型作为 Cokret 专属 component 标记 `application/vnd.cokret.component+json`。MIMI facade 接收外部 join 请求时 SHOULD 至少强制执行 `claim_required` 与 `parent_membership` gate；`application_form` / `manual_review` / `challenge_response` 在 MIMI 客户端不支持 inline 表达时，facade SHOULD 拒绝跨域请求并指引 applicant 通过 Cokret 原生客户端完成。

## 14. 完整示例

公开知识社群，凭证持有者直通、否则走 5 道问卷 + CAPTCHA：

```json
{
  "candidate_kind": "realm.join_policy",
  "payload": {
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "value": {
      "combinator": "any",
      "gates": [
        {
          "gate_id": "g-vc",
          "kind": "claim_required",
          "auto_resolve": true,
          "requires_claims": [
            {"claim_type": "membership", "issuer": "did:web:openresearch.org", "status": "active"}
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
          "provider_did": "did:web:captcha.example",
          "challenge_kinds": ["captcha"],
          "max_proof_age": "PT5M"
        }
      ],
      "review_capability": "ck.realm.join.review",
      "reviewer_quorum": "any",
      "application_ttl": "PT168H",
      "cooldown_after_reject": "PT168H",
      "max_open_applications_per_actor": 1,
      "applicant_visibility": "reviewer_only",
      "directory_hint": {
        "summary": "Members hold an OpenResearch credential, OR complete a brief application + CAPTCHA.",
        "expected_review_time": "PT24H",
        "requires_human_review": true,
        "challenge_kinds_displayed": ["captcha"]
      }
    }
  }
}
```

对应 `ck.realm.join_rule.value="knock_restricted"`：凭 VC 自动通过的走自动解析路径，其余走申请-审核路径。

> 注：本示例 `cooldown_after_reject` 显式收紧为 `PT168H`（7 天），高于 §3 字段表默认 `PT72H`；此处恰与 `application_ttl` 取同值仅为示例简洁，二者计时锚点与作用对象不同（`application_ttl` 按申请未决超时，`cooldown_after_reject` 按上次 review reject 计时），并非要求二者相等。生产部署应按需独立取值或回落默认 `PT72H`。

## 15. 规范性引用

- Realm 对象模型：[`../models/realm-and-space.md`](../models/realm-and-space.md)
- Capability 与 `ck.realm.join.review` 等 action：[`../authz/capabilities.md`](../authz/capabilities.md)
- Policy Server 与 obligation：[`../authz/policy-server.md`](../authz/policy-server.md)
- Claim 与 constraint：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)
- Federation 跨域加入：[`../sync/federation.md` §5.2](../sync/federation.md)
- Discovery Directory：[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)
- Audit trail / 申诉：[`./content-moderation.md` §5.5](./content-moderation.md)（申诉流程）、[`./content-moderation.md` §10](./content-moderation.md)（审计要求）
- MIMI 互操作：[`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)
