---
title: Join Policy
---

## 1. 目标与范围

本文档定义 Realm 的 **Join Policy** 模型，覆盖 gate 组合、自动解析路径、申请-审核路径、加密语义、联邦传播、反滥用与 MIMI 映射。原本作为 `realm-and-space.md §3` 的子节存在；v1 拆出独立文件以便 governance / membership 相关讨论集中维护。`realm-and-space.md` 现在只承担 Realm 对象模型与 Space / hierarchy 部分。

当前 v1 的 active 与 candidate surface 分层如下，base v1 实现只需要实现 active surface；application / review workflow 只在实现声明 `cx.profile.candidate.join_policy.v1` 时成为该实现的自愿承诺。

| Surface | v1 状态 | Wire 形态 | 实现要求 |
| --- | --- | --- | --- |
| `cx.realm.join_rule` | active | 标准 `Event.kind` / reducer cell | base v1 按 registry 和 reducer 规则实现 |
| `cx.realm.policy_components` 中的 join policy facet | active | 标准 policy component payload | base v1 可表达 gate、delivery binding policy 与自动解析要求 |
| `cx.member.state{membership=join}` 自动 gate | active | 标准 membership event + `gate_proofs[]` / delivery binding payload | base v1 必须 fail closed 校验 capability、gate proof 与 delivery binding |
| `cx.invite.*` + `refs[role="join_authorised_by"]` | active | 标准 invite / member refs | base v1 支持 invite 或 join-authorized grant 时必须校验引用仍有效 |
| `realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel` | candidate | 裸名 design-time concept；不得作为 `Event.kind` | 仅 `cx.profile.candidate.join_policy.v1` 实现可用 profile-private signed receipt 或私有 Event kind 承载 |

独立 join-policy Event.kind / schema 仍未进入 active registry。任何未声明 `cx.profile.candidate.join_policy.v1` 的实现 MUST 把 application / review workflow 当作未知高风险 surface，返回 `unsupported_feature`、`unsupported_event_kind`、`capability_denied` 或等价 fail-closed 结果；不得把未注册裸名 kind 写入 shared Realm history。

`default_join_rule` 枚举（[`../models/realm-and-space.md` §2.3](../models/realm-and-space.md)）只表达粗粒度的入口模式：`public` 直接进、`invite` 必须有人邀、`knock` 可申请、`restricted` / `knock_restricted` 有附加条件、`closed` 不收新人。但是 `restricted` 的"条件"是什么、`knock` 申请里能否带结构化材料、人工审批的决策是否上链审计、CAPTCHA / proof-of-work 等运行时挑战如何接入——这些都需要本文件统一定义。

本文定义的 **Join Policy** 与 `default_join_rule` 正交又互补：

- `default_join_rule` 决定**入口模式**（`public` / `invite` / `knock` / `restricted` / `knock_restricted` / `closed`）。
- Join Policy 决定**入口模式选定后，到 `membership=join` 必须穿越的 gate 集合**（凭证、问卷、挑战、人工审批等）的组合、解析顺序、加密语义和反滥用约束。
- `default_join_rule=public` 与 `default_join_rule=closed` 不消耗 Join Policy（前者无 gate，后者无入口）；其余四个枚举值的精确语义由 §4 与 Join Policy 交叉决定。

## 2. 设计原则

1. **Gate 是组合的，不是命名的。** 不再以新 enum 区分"附加条件类型"。Realm 通过 `gates[]` + `combinator` 表达任意 AND/OR 组合；`knock_restricted` 等组合 enum 的语义由 `combinator` 直接表达，避免每加一类 gate 就要再造 enum。
2. **申请材料对外不可见。** Matrix `m.room.member{knock}` 的 free-text `reason` 因默认可见已成为 spam 通道。实现声明 `cx.profile.candidate.join_policy.v1` 并启用 application / review workflow 时，申请正文 MUST 仅对 `cx.realm.join.review` capability 持有方可见：E2EE Realm 中通过 reviewer-only encryption envelope；非 E2EE Realm 中由 Sync Service 强制访问控制并审计读取（`cx.audit.accessed`）。
3. **审核决策必须有稳定审计材料。** 实现声明 `cx.profile.candidate.join_policy.v1` 时，所有审核接受 / 拒绝 MUST 是签名的 anchored Move、profile-private Event 或 signed receipt，记录 reviewer DID、review reason、引用证据 hash。事后审计与申诉（参见 [`./content-moderation.md` §6](./content-moderation.md)）依赖该 trail。
4. **审核必须密码学绑定到 join。** 借鉴 Matrix `join_authorised_via_users_server` 的担保模式：candidate profile 下随后的 `cx.invite.create` MUST 通过 `refs[role="join_authorised_by"]` 引用对应 signed review accept receipt hash；若实现 profile 已注册私有 review Event kind，MAY 引用该 Event id。reducer 校验该 ref 在写入时仍指向有效 capability 持有者。
5. **自动解析路径不强制走人工。** 当所有 gate 都可自动解析（claim presentation 验证、challenge proof 验证），applicant 可直接提交 `cx.member.state{membership=join}`，由 reducer 内联校验，无需 application / review Move。这条路径替代既有 `restricted` 入口模式的实质语义。
6. **Capability 仍是 allow 唯一来源。** Join Policy gate 通过即"可以提议加入"，但 reducer 仍按 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 校验 join Move 的 capability。Policy Server `obligations[]`（§11）只能在 capability 之上叠加额外要求（如 challenge），不能凭空创造权限。

## 3. Cell Family 与 State Event

```text
cell_id     := cx:cell:realm.join_policy.v1:<realm_id>
lattice     := cas_register
bottom      := reject
value shape := JoinPolicy（见下）
```

写入 cell 的候选概念在正式登记前记为 `realm.join_policy`（裸名仅是 design-time concept/action，不是 v1 wire `Event.kind`，也不得作为 Event envelope 的 `kind` 上链或同步），需要 `cx.policy.manage` capability（与 `cx.realm.policy_server` / `cx.realm.policy_components` 同等级）。`cx.realm.create` 时 SHOULD 通过 `cx.realm.policy_components` 一并提供 join policy 初值；省略时 cell 维持 `null`，行为退化为"`default_join_rule` 单独决定"。

JoinPolicy 候选 schema 名：`realm.join_policy.v1`。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `gates` | yes | `array<Gate>` | 1..16 项；空数组 MUST schema_violation。 | 必须穿越的 gate 列表。 |
| `combinator` | yes | `enum(all, any)` | 默认 `all`。 | gate 之间的组合语义。 |
| `review_capability` | conditional | `string` | 任一 gate `kind ∈ {manual_review, application_form}` 时必填；缺省 `cx.realm.join.review`。 | 审核所需 capability。 |
| `reviewer_quorum` | no | `enum(any, majority, all) \| object` | 默认 `any`。`object` 形式 `{ threshold: int, of: did[] }` 表达 N-of-M。 | 审核法定人数。 |
| `application_ttl` | no | `duration` | 默认 `168h`，最小 `1h`，最大 `8760h`（1y）。 | 申请未决超时即失效。 |
| `cooldown_after_reject` | no | `duration` | 默认 `72h`。 | 拒绝后同一 actor 重新申请的最短间隔。 |
| `max_open_applications_per_actor` | no | `integer` | 默认 `1`，最大 `5`。 | 同一 actor 在本 Realm 同时未决申请上限。 |
| `applicant_visibility` | no | `enum(reviewer_only, members_after_join, public)` | 默认 `reviewer_only`。 | 申请正文谁可见；`members_after_join` 表示 join 成功后开放给 Realm 成员（用于自我介绍场景）。 |
| `directory_hint` | no | `object` | 见 §3.2。 | Discovery Directory 公开投影所需 hint。 |

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
- `kind`：取 `claim_required` / `application_form` / `challenge_response` / `manual_review` / `parent_membership` / `cooldown` 之一
- `auto_resolve`：该 gate 能否仅靠 applicant 提交的材料解析；`manual_review` / `application_form` 必为 `false`
- 其余字段按 `kind` 决定（见下表）

| `kind` | 必带字段 | 语义 | `auto_resolve` |
| --- | --- | --- | --- |
| `claim_required` | `requires_claims[]`（见 [`../authz/constraint-schema.md` §10](../authz/constraint-schema.md)） | applicant MUST 提交满足声明集合的 VC / claim presentation。 | `true` |
| `parent_membership` | `membership_source_realm_refs: id:realm[]`、`require_min_membership: enum(invite, join)` | applicant MUST 已是任一 source Realm 的指定成员；该字段只是 membership gate 的验证来源，不表达 Realm 树形父子关系。reducer 在 join Move 校验时必须能够独立验证（snapshot 或 backfill）。等价于 Matrix MSC3083 `m.room_membership` 条件。 | `true` |
| `challenge_response` | `provider_did: did`、`challenge_kinds: enum(captcha, pow, attested_human, idp_oidc)[]`、`max_proof_age: duration` | applicant MUST 完成 provider 颁发的挑战并提交 signed proof。详见 §11。 | `true` |
| `application_form` | `questions[]`（见 §3.3） | applicant MUST 在 `member.application` 中提交对应 answer；reviewer 人工评估。 | `false` |
| `manual_review` | （无额外字段） | reviewer 必须显式签署 accept；不要求结构化问卷。 | `false` |
| `cooldown` | `min_interval_since_leave: duration` | applicant 上次 `cx.member.state{membership=leave}` 后未达冷却期 MUST 拒绝。仅作为 deny gate（与 `combinator` 无关，单独评估）。 | `true` |

未注册 `kind` MUST schema_violation；未注册的 `(kind, subfield)` 组合按 lattice `bottom=reject` 处理。

### 3.2 `directory_hint`

为帮助 Discovery Directory（[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)）告知 applicant "进入这个 Realm 大概要做什么"，Realm MAY 声明 directory hint。该 hint 是公开投影，**不得**包含敏感问卷正文：

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

## 4. 与 `default_join_rule` 的交叉表

| `default_join_rule` | Join Policy 是否生效 | 等价 gate 组合 |
| --- | --- | --- |
| `public` | 不生效 | applicant 提交 `cx.member.state{join}` 即被接受。 |
| `invite` | 不生效 | 必须有 `cx.invite.create`；Join Policy 不可绕过 invite。 |
| `restricted` | 生效（自动解析路径） | `gates[*].auto_resolve == true` MUST 全为 true；含 `manual_review` 或 `application_form` MUST schema_violation。 |
| `knock` | 生效（任一路径） | gate 集合可包含人工审核；申请-审核路径必走。 |
| `knock_restricted` | 生效（OR 合成） | `combinator` SHOULD 为 `any`；典型组合：`[claim_required(auto), application_form(manual)]`，凭证持有者直接进，否则走问卷申请。 |
| `closed` | 不生效 | reducer 拒绝任何 join / knock / application Move。 |

reducer 在 `cx.realm.join_rule` 与 join-policy cell 任一变更时 MUST 重新评估上述一致性约束；不一致 MUST `failed_precondition` 拒绝写入，并附带 `reason="join_rule_policy_mismatch"`。

## 5. 自动解析路径

适用条件：`default_join_rule ∈ {public, restricted, knock_restricted}` 且 applicant 拟使用的 gate 子集全部 `auto_resolve=true`。

applicant 直接提交：

```json
{
  "kind": "cx.member.state",
  "payload": {
    "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
    "actor_id": "did:webvh:bob",
    "membership": "join",
    "delivery_status": "routable",
    "delivery_binding": {
      "recipient_service_did": "did:web:principal.org-a.example",
      "recipient_service_type": "principal_server",
      "binding_scope": "realm",
      "binding_source": "explicit",
      "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
      "service_acceptance_ref": "cx:event:0196419b-0000-7000-8000-000000000001"
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

reducer MUST NOT 在自动解析路径上隐式生成 application / review Move——此路径绕过申请-审核状态机。

**外部 applicant 失败不可枚举（normative）**：对尚未 join 的外部 applicant，wire 响应 MUST 统一为 `failed_precondition` + `reason_code=gate_check_failed`（或 invite / directory surface 已定义的统一不可枚举错误），不得区分“claim 从未签发”、“claim 已撤销”、“issuer 暂时不可达”、“parent membership 不满足”或“challenge proof 失效”。Reducer / audit log MAY 记录内部 diagnostic reason、gate_id 与 issuer 状态，但这些字段不得出现在 applicant 可见响应、directory hint 或 push/notification payload 中。Reviewer-only application workflow 可以在加密 reviewer envelope 内展示更细原因。

**Gate predicate 评估时点（normative）**：所有 gate predicate（包括 claim issuer revocation、challenge provider signature、`cooldown`、parent membership、capability presence 检查）MUST 仅对该 join Move 的 `anchor_ref` 指向的 **Anchor pre-state** 求值，与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.3 `apply_anchor(A)` 的 `pre_state` 模型完全一致。同一 Anchor batch 内并发的 `cx.capability.revoke` / policy 变更 / `cx.realm.join_rule` 更新对**本批次**的 join Move **不**生效；它们仅从下一 Anchor 起影响 gate 评估。这意味着：

- 同批中"先撤销 review capability，后 join"的攻击模式不会让 join 通过 review-gated 路径——gate 仍按 pre-state 看到完整 capability。
- 反之，同批中"先发 grant，后用 grant 满足 gate" 也不会被 reducer 当作满足——授权与 Move 的可见性以 Anchor 边界为单位。
- 与本规范 §3.1 中 `combinator` 的"deny gate（如 cooldown）独立评估"规则共存：cooldown 等 pre-evaluation deny gate 同样基于 pre-state 触发，且不参与 combinator。

### 5.1 成员投递绑定

`cx.member.state{membership="join"}` 表达的是某个 DID 在该 Realm 中成为成员；它**不等价于**"按该 DID 的全局 home Principal Server 投递"。Realm-scoped events / account aggregate / to-device / push / key-package 的实际投递目标由该成员的 **effective delivery binding** 决定。本 §5.1 是 v1 normative。

#### 5.1.1 接受准则（normative）

任一 `cx.member.state{membership="join"}` Move 被 reducer 接受前 MUST 满足：

1. `payload.delivery_status ∈ {routable, unroutable}` 显式声明。
2. `delivery_status="routable"` 时 `payload.delivery_binding` 必填，且其 `binding_source` 在 Realm `cx.component.realm.delivery_binding_policy.v1`（§5.1.3）的 `allow_binding_sources` 集合内。
3. `delivery_status="unroutable"` 仅当 Realm policy 显式允许（`allow_unroutable_membership=true`），且该成员的客户端理解"该 Realm 仅向本地可见、不接收服务端推送 / 同步 / to-device / push / key-package 投递"。
4. `delivery_binding.recipient_service_did` 出现在 Realm policy 的 `allowed_recipient_services`（若声明），否则 MUST 被 `required_endorsers` 中至少一个治理 DID 通过 `service_acceptance_ref` 引用的 acceptance Event 背书。
5. `delivery_binding` 的 `binding_source`-conditional required 字段满足 [`event-payload.schema.json#/$defs/member_delivery_binding`](../../artifacts/schemas/event-payload.schema.json)（例如 `did_document_default` MUST 含 `did_document_digest`；`explicit` / `invite` / `organization_policy` MUST 含 `service_acceptance_ref`；policy-driven source MUST 含 `policy_ref`）。
6. `delivery_binding.delivery_modes` 是该 binding 的**显式**模式集合；空集合或缺失等价于 schema violation。普通"全功能"成员 SHOULD 列出 `["events", "sync", "to_device", "push", "key_packages"]`。

reducer 校验上述任一条失败 MUST 拒绝该 Move 并返回 `delivery_binding_invalid`，**不得**降级为部分接受。

#### 5.1.2 `binding_source` 与责任方

| `binding_source` | 谁负责填 | 何时使用 | 补充必填 |
| --- | --- | --- | --- |
| `explicit` | 邀请方 / 管理员客户端 | 用户显式选择目标服务 | `service_acceptance_ref` |
| `did_document_default` | 客户端 DID resolver | Realm policy 允许 fallback，未匹配其它来源 | `did_document_digest` |
| `invite` | 邀请方 builder | 邀请 token 已携带 binding | `service_acceptance_ref` |
| `join_policy` | reducer 由 Join Policy 推导 | Join Policy 的 gate / role 决定目标服务 | `policy_ref` |
| `organization_policy` | 组织治理目录 | invitee 是 Org 员工，组织 policy 指定目标 | `service_acceptance_ref` + `policy_ref` |
| `realm_policy` | Realm policy 默认值 | Realm 声明 default recipient | `policy_ref` |

所有六类来源都要求 `resolved_at`；任何 `binding_source` 进入 canonical Event 时，**结果 MUST 已在客户端 / 提交服务侧解析完成**，不得留"运行时再 resolve"的隐含状态。

##### 5.1.2.1 Handle 作为成员添加输入

客户端 MAY 允许邀请方输入 `@alice:acme.example`、`alice@acme.example`、`contrix://acme.example/users/alice` 或 `acct:alice@acme.example` 来添加成员。该字符串只是 builder 输入，不是 membership 主键。

构造 `cx.member.state{membership="join"}` 前，客户端 / 提交服务 MUST：

1. 按 [`identity/identity-handles.md` §3.1](../identity/identity-handles.md) 规范化为 canonical `handle_uri`（主形态为 `contrix://<domain>/users/<localpart>`）。
2. 调用 `cx.directory.resolve_handle` 或等价 Principal Server / Organization Directory 解析，带上 `intent="member_add"`、目标 `realm_id`、`requester` 和 challenge。
3. 验证响应中的 handle claim / presentation 绑定 `handle_uri`、`subject` DID、`member_delivery_binding.recipient_service_did`、issuer、`expires_at`、撤销状态，以及 `audience`：claim `audience` MUST 等于目标 `realm_id` 或邀请方 service DID 之一；不一致 MUST 视作未授权 claim。
4. 生成 member Move 时使用 `payload.actor_id = subject`；不得把 handle 字符串写作 actor、grant subject 或 cell subject。
5. 若解析结果携带 `member_delivery_binding`，将其物化为 `payload.delivery_binding`，并按 Realm `cx.realm.delivery_binding_policy` 选择 `binding_source`：
   - 若 invite token / signed candidate 内嵌 binding，优先使用 `invite`，并携带 `service_acceptance_ref`；
   - 其次使用 Realm join policy 推导的 `join_policy`，并携带 `policy_ref`；
   - 组织目录 / 员工名录背书的地址使用 `organization_policy`，并携带 `service_acceptance_ref` + `policy_ref`；
   - Realm / linked Realm policy 继承使用 `realm_policy`，并携带 `policy_ref`；
   - 用户 / 管理员显式选择服务时使用 `explicit`，并携带 `service_acceptance_ref`；
   - 最后才考虑 `did_document_default`，且仅当 Realm `delivery_binding_policy.allow_did_document_default=true` 并已在 join 时物化 DID document hash。
   - `member_delivery_binding.binding_source` 不得是 `did_document_default`；handle resolution 与 DID Document fallback 是两条独立的物化路径。
6. 若解析结果没有 `member_delivery_binding.recipient_service_did`，该 handle 只能证明 actor DID；除非 Realm policy 允许 `did_document_default` fallback 并在 join 时完成物化，否则 reducer MUST 拒绝 handle-based join。

Reducer MUST 在 gate proof 通过前先校验 applicant 是否具备提交 `cx.member.state{join}` 的 capability 或等价 invite / join-authorized grant；gate 只能增加限制，不能创造权限。最终 `binding_source` 不在 `allow_binding_sources` 中、或优先级决策得到的 binding 与 policy allowlist 冲突时，reducer MUST 返回 `delivery_binding_policy_mismatch`，不得降级到下一个来源。

Realm history SHOULD NOT 写入受限组织 handle 明文。需要审计时，Move 可引用 handle claim / service acceptance Event 的 `event_id`，或在私有 review / invite 流程中保存最小披露记录；公开成员状态只需要 DID 与 `delivery_binding`。

#### 5.1.3 Policy 事件：`cx.realm.delivery_binding_policy`

Realm 通过独立的 `cx.realm.delivery_binding_policy` event 声明对成员投递绑定的强约束。该事件写入 `cx.component.realm.delivery_binding_policy.v1` cell（cas_register, cell_subject=null, bottom=reject），与 `cx.realm.join_rule` / `cx.realm.history_visibility` 等其它 realm policy 事件并列。Realm 在 `cx.realm.policy_components` 中将该 component 列入 active set 后，reducer 强制其约束。

```json
{
  "kind": "cx.realm.delivery_binding_policy",
  "payload": {
    "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
    "allow_binding_sources": [
      "explicit",
      "invite",
      "organization_policy"
    ],
    "allow_did_document_default": false,
    "allowed_recipient_services": [
      "did:web:principal.acme.example"
    ],
    "required_endorsers": [
      "did:web:acme.example"
    ],
    "allow_unroutable_membership": false,
    "rebind_authorization": "member_and_admin",
    "expires_after_seconds": 7776000
  }
}
```

字段语义：

| 字段 | 类型 | 默认 | 语义 |
| --- | --- | --- | --- |
| `allow_binding_sources` | `enum[]` | `["did_document_default"]` for 个人 / 公开 Realm；组织 Realm 必须显式收窄 | 允许出现在被接受 binding 中的 `binding_source` 子集。 |
| `allow_did_document_default` | `boolean` | `false` | 是否允许 binding_source=did_document_default。组织 / 合规 Realm MUST 设为 `false`。 |
| `allowed_recipient_services` | `did[]` | `[]`（不限） | 允许出现在 `recipient_service_did` 的封闭集合。空数组等价于"不限"。 |
| `required_endorsers` | `did[]` | `[]` | 当 `allowed_recipient_services` 非空时，`recipient_service_did` 的 `service_acceptance_ref` MUST 由其中一个治理 DID 背书；否则空数组表示无强制背书要求。 |
| `allow_unroutable_membership` | `boolean` | `false` | 是否允许 `delivery_status="unroutable"` 成员。 |
| `rebind_authorization` | `enum(member, member_and_admin, admin_only, service_only, any)` | `member_and_admin` | rebind Move 的合法签名 / 背书集合（见 §5.1.5）。 |
| `expires_after_seconds` | `int?` | unset = 不过期 | 该 Realm 中所有 binding 的最大有效期；reducer MUST 在物化时把 `delivery_binding.expires_at = resolved_at + expires_after_seconds`，除非 binding 显式声明更短的 `expires_at`。 |

`cx.component.realm.delivery_binding_policy.v1` 是 cas_register cell（`cell_subject=null`，每 Realm 一个）。变更走 [`models/realm-and-space.md`](../models/realm-and-space.md) 的 `cx.realm.policy_components` 通用路径。

#### 5.1.4 路由不可降级（normative）

`delivery_binding` 一旦进入 accepted member cell，**任何 sender** 在向该 Realm 投递面向该成员的事件 / sync delta / to-device 消息 / push 唤醒 / MLS KeyPackage 请求时：

- MUST 解析当前 effective `delivery_binding.recipient_service_did` 作为唯一投递目标。
- MUST NOT 退路到该 actor 的 DID Document `ContrixPrincipalServer` service entry，即便 DID Document 当前可解析、`recipient_service_did` 临时不可达、binding 已 `expires_at` 过期或被撤销。失败时 MUST 进入 quarantine + retry（默认重试上限见 [`sync/federation.md` §4.1](../sync/federation.md)），并在第二次失败后向 sender 上游暴露 `delivery_binding_unresolvable` 诊断。
- MUST NOT 把"recipient_service_did 在本地登记了该 DID 的内部账号 / OIDC subject / 员工目录条目"视为投递授权——所有授权 MUST 通过 binding 的 `service_acceptance_ref` / `policy_ref` 显式建立。

`expires_at` 到期：sender MUST 停止向该 binding 投递、quarantine pending events，并提示该成员客户端通过 §5.1.5 rebind 流程提交新 binding。**未提供 fallback path**——这是设计约束。

#### 5.1.5 Rebind 过渡（normative）

成员保持 `membership="join"` 但迁移 `recipient_service_did`（个人 PS → 组织 PS、组织换集群、灾备切换等）通过同一 `cx.member.state{membership="join"}` 的同状态 self-transition 完成：

1. **签名 / 背书**：rebind Move 的可签名主体由 `rebind_authorization` 决定：
   - `member`：仅成员 DID 自签即可。
   - `member_and_admin`：成员 DID 自签 + Realm `cx.realm.admin` capability 持有者背书（双签）。
   - `admin_only`：仅 Realm admin 可发起（用于离职 / 强制迁移）。
   - `service_only`：仅当前 / 目标 recipient service DID 可发起（用于服务运维迁移）。
   - `any`：上述任一即可。
2. **Precondition**：Move 的 `prev_refs` MUST 引用前一 accepted member cell 的 head；reducer 用 cas_register 校验前态。
3. **Handover frontier `F`**：该 Move 被接受时的 accepted causal frontier 是 rebind 切换点。
   - causal 上 `prec(F)`（不含 F）的 Realm events MUST 仍投递到旧 `recipient_service_did`。
   - causal 上 `succ(F)`（含 F）的 Realm events MUST 投递到新 `recipient_service_did`。
   - 这一切分对所有 sender 是确定性的——只要 sender 的本地 `service_binding_ref.delivery_binding_frontier ≥ F` 就 MUST 切换；frontier 落后的 sender 仍按旧 binding 投递（接收方负责回执并通知 sender 升级）。
4. **Grace period**：旧 `recipient_service_did` MUST 在 `handover_grace_seconds`（默认 86400）内继续接受迟到的 `prec(F)` event；超过 grace 后旧服务 MUST reject 并返回 `delivery_binding_handed_over` + `new_recipient_service_did`。
5. **In-flight 事件**：grace 内 sender 收到的"旧目标 reject"事件 MUST 按新 binding 重新投递；不得回退到 DID Document。
6. 旧服务在 grace 结束后 MUST NOT 保留可逆映射到该 Realm membership 的 sync state / to-device queue / push registration。新服务从 handover frontier 起重建。

未满足 rebind 授权或 precondition 的 Move **MUST fail closed**；服务不得仅因 DID Document 更新、本地 service account 切换、SSO subject 变更或员工目录调整自动迁移既有 Realm membership 的投递路径。

#### 5.1.6 单 binding 约束 + 多设备策略

同一 `(realm_id, actor_id)` 在任一时刻**有且仅有**一个 active `membership="join"` cell；该 cell 持有唯一 effective `delivery_binding`。**不允许**同一 DID 通过两个不同 `recipient_service_did` 同时持有两条 join membership——这种诉求应通过下列正确机制表达：

- **同一 binding 下多设备**：member 的多台设备各自向 `recipient_service_did` 上传 KeyPackage、注册 push、维护 to-device 队列。同一 binding 下的设备共享 sync state。
- **Realm-level mirror / shared sync**：Realm 自身需要多服务承载（HA / 灾备 / 跨区域）时，使用 Realm metadata 的 [`sync_endpoints`](../sync/federation.md) 表达 Realm-level service binding，与 member-level `delivery_binding` 正交。
- **同一物理用户的多个上下文** (e.g. Alice 既参与 personal Realm P 也参与 work Realm S)：每个 Realm 各自有独立 membership 与独立 binding；同一 DID 在 P 中 `recipient_service_did = personal PS`，在 S 中 `recipient_service_did = org PS`。这就是 §5.1 整套机制要解决的核心场景。

#### 5.1.7 关联性与隐私边界

`delivery_binding` 解决的是**投递路由 / 设备隔离 / push 隔离 / 合规审计边界**，**不解决跨上下文 unlinkability**：外部观察者仍能看到同一 `actor_id` 在不同 Realm 的 membership。需要 unlinkability 的部署应使用 pairwise / private DID（[`../identity/identity-did.md` §3](../identity/identity-did.md)），与 `delivery_binding` 正交。

## 6. 申请-审核路径

适用条件：`default_join_rule ∈ {knock, knock_restricted}` 且至少一个 gate `auto_resolve=false`。

### 6.1 阶段

| 阶段 | Move | 写入方 |
| --- | --- | --- |
| 1. 敲门 | `cx.member.state{membership=knock}` | applicant |
| 2. 提交申请 | `member.application` | applicant |
| 3. 审核决策 | `member.application.review` | reviewer（持 `review_capability`） |
| 4. 接受邀请（隐式） | `cx.invite.create` + `cx.invite.accept` | reviewer 与 applicant |

reducer MUST 接受 stage 1 与 stage 2 在同一 batch 内提交；client SHOULD 把它们打包到同一 Anchor request 以减少 round trip。

### 6.2 `member.application`

候选申请概念；schema 名 `member.application.v1`。正式进入 v1 registry 前，`member.application` 不得作为 Event envelope 的 `kind` 使用，也不得使用 `cx.*` 标准前缀伪装成 active contract；生产实现若启用本 workflow，必须在自有 profile 中声明唯一承载方式，并输出可引用的 signed application receipt（`application_receipt_hash`），供后续 review / invite / audit 引用。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `realm_id` | yes | `id:realm` | 申请目标 Realm。 |
| `applicant_did` | yes | `did` | 等于 envelope `actor`。 |
| `knock_ref` | yes | `event_ref` | 引用 stage 1 的 `cx.member.state{knock}` event id。 |
| `policy_version` | yes | `sha256` | 提交时 `realm.join_policy` cell value 的 canonical hash；reducer 校验 reviewer 决策时是否仍是同一 policy。 |
| `answers` | conditional | `array<Answer>` | 任一 `application_form` gate 存在时必填，覆盖该 gate 所有 `required=true` 的 question_id。 |
| `gate_proofs` | conditional | `array<GateProof>` | 任一可自动解析 gate 存在时按需提供（与自动解析路径同形）。 |
| `applicant_note` | no | `string` | 1..2000 chars 自由文本备注。 |
| `encryption_envelope` | conditional | `object` | E2EE Realm 必填；见 §7。 |

`Answer` 形态：`{question_id, value: string|string[]|boolean}`；reducer 仅做存在性 / shape 校验，语义评估留给 reviewer。

### 6.3 `member.application.review`

签名 review workflow record，需要 `review_capability`。在正式注册为 v1 active Event kind 前，它不是 base profile 的 durable `Event.kind`；实现必须把 review 结果承载为自有 profile 声明的 signed review receipt（`review_receipt_hash`），或承载在该 profile 自己注册的私有 Event kind 中。任何 `cx.invite.create` 对 review 的引用 MUST 指向稳定 receipt hash 或该私有 Event id，不得引用未注册的裸名 kind。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `realm_id` | yes | `id:realm` |  |
| `application_ref` | yes | `receipt_hash` 或 profile-private `event_ref` | 指向 §6.2 的 signed application receipt；若实现 profile 已注册私有 application Event kind，MAY 指向该私有 Event id。不得引用未注册的裸名 `member.application`。 |
| `decision` | yes | `enum(accept, reject, request_changes)` | `request_changes` 允许 applicant 修订 answer 后重提，不计入 cooldown。 |
| `reason_code` | yes | `string` | 稳定原因码：`ok` / `incomplete_answers` / `policy_violation` / `claim_invalid` / `challenge_failed` / `duplicate` / `other`。 |
| `reason_text` | no | `string` | 1..1000 chars 自由文本，对 applicant 可见。 |
| `evidence_refs` | no | `event_ref[]` / `hash[]` | 评审依据的其它 event 或 signed receipt（如 `cx.audit.*` 风险记录）。 |
| `reviewer_capability_proof` | yes | `object` | 引用授予 reviewer `review_capability` 的 grant id 与当时 frontier hash；reducer 必须在写入时再校验一次。 |

`reviewer_quorum != "any"` 时，reducer 需收集 N 个独立 reviewer 的 accept 才认为申请进入 `accepted` 状态；任一 reject 即终止。

### 6.4 `member.application.cancel`

applicant 可主动撤回；写入 `decision=canceled`，不计 cooldown。

### 6.5 接受后的 invite

application 进入 `accepted` 状态后：

1. 任一 reviewer 提交 `cx.invite.create`，`refs[role="join_authorised_by"]` MUST 引用对应 `member.application.review{accept}` 的 signed review receipt hash；若实现 profile 已注册私有 review Event kind，MAY 引用该 Event id；
2. applicant 提交 `cx.invite.accept`；
3. reducer 在写入 `cx.invite.create` 时再次校验：被引用的 review accept 仍指向尚未消费的 application（防止同一 accept 被复用）、reviewer 在当前 frontier 仍持有 `review_capability`、application 未过 `application_ttl`、未被后续 `reject` / `cancel` 覆盖。

校验失败 `failed_precondition`，`reason_code="join_authorisation_invalid"`。

## 7. 加密与隐私

### 7.1 非 E2EE Realm

`member.application` 的共享 durable wire payload 即使在非 E2EE Realm 中也只能包含最小化 metadata（application id、applicant DID、policy hash、receipt hash、状态与时间戳）。申请正文、answers、自由文本、3PID、附件和 reviewer-only 诊断 MUST 放入 reviewer encryption envelope 或实现 profile 声明的受保护 private record；不得仅依赖 projection 隐藏来保护隐私。Sync Service / Principal Server MUST：

- 仅向 reviewer set（`review_capability` 持有方）与 applicant 自身投影 application 正文；
- 对其它 Realm 成员投影占位（`{application_pending: true}`）；
- 对每次 reviewer 读取写一条 `cx.audit.accessed`（payload 包含 application receipt hash 或 profile-private application Event id 与读取者 DID）。

`applicant_visibility=members_after_join` 仅在 application 进入 `accepted` 且对应 `cx.invite.accept` 已落入 frontier 后，才允许向 Realm 成员投影正文。

### 7.2 E2EE Realm（`encryption_profile=mls_rfc9420`）

Realm 主 MLS group 不包含尚未 join 的 applicant，因此申请正文不能直接走 Realm MLS group。MUST 使用以下机制之一：

1. **Reviewer Sub-Group MLS**：Realm 维护一个独立 MLS group `cx:mls:reviewer_subgroup:<realm_id>:reviewers`，成员是当前所有 `review_capability` 持有方。applicant 通过 reviewer set 中任一成员公布的 KeyPackage 出 group commit + welcome，将 application 正文作为该 sub-group 的 application message 投递。reducer 通过 `cx.mls.commit.governance_binding` 验证 sub-group roster 与 capability 一致。
2. **Envelope Encryption to Reviewer Devices**：当 reviewer 数小于阈值（默认 `<=5`）或 sub-group 维护成本不可接受时，applicant 可使用 `encryption_envelope` 字段对 reviewer 当前已 published `cx.mls.keypackage` 的接收方公钥逐一封装：

```json
{
  "encryption_envelope": {
    "scheme": "hpke-base-x25519-aes256gcm",
    "ciphertext": "base64url:...",
    "recipients": [
      {"reviewer_did": "did:webvh:alice", "device_id": "cx:device:...", "wrapped_key": "base64url:..."},
      {"reviewer_did": "did:webvh:carol", "device_id": "cx:device:...", "wrapped_key": "base64url:..."}
    ]
  }
}
```

reviewer 加 / 退职导致 envelope 失效时，应用层 SHOULD 提示 applicant 重提。

申请正文 MUST NOT 进入 `cx.member.state{knock}` Move（该 Move 公开），所有自由文本仅出现在受加密保护的 `member.application.encryption_envelope` 中。Matrix `m.room.member{knock}.reason` 因默认对部分客户端可见而成为 spam 通道——Contrix 通过结构上禁止 knock Move 携带正文规避该缺陷。

## 8. Membership 状态机扩展

复用既有 `cx.member.state` 枚举（`invite / join / leave / knock / ban`），不引入新值。状态转换补充：

```text
        knock ──submit member.application──▶ knock (with application_ref projection)
            │
            ├─ review.accept ──▶ invite (via cx.invite.create) ──▶ join (via cx.invite.accept)
            ├─ review.reject ──▶ leave  (with rejected_at + cooldown_until projection)
            ├─ application.cancel ──▶ leave
            └─ application_ttl 到期 ──▶ leave (reducer 自动转换，rejected_reason="ttl_expired")
```

派生 view `cx.view.realm.applications.v1`（[`../models/views.md`](../models/views.md)）SHOULD 提供：

- `pending`: 未决申请；
- `awaiting_review`: 已提交但 reviewer 未决；
- `accepted_pending_invite`: 审核通过但 `cx.invite.create` 尚未签发；
- `recently_decided`: 7 日内的 accept/reject 决策。

## 9. 联邦语义

跨域加入流程在 [`../sync/federation.md` §5.2](../sync/federation.md) 详述。本节仅说明 Join Policy 引入的不变量：

- `member.application` 与 `member.application.review` 都是候选 durable workflow 概念；正式登记前不得作为 v1 base profile 的 durable Event.kind 参与 federation push / pull；
- `policy_version` 字段使 reviewer 与 applicant 显式承认评估时所用的 policy 快照，避免 reviewer 在不同 policy frontier 下决策导致争议；
- E2EE 场景下 reviewer sub-group MLS commit 通过既有 `cx.mls.*` 联邦机制传播；envelope encryption 由 origin Principal Server 投递到目标 reviewer 的 device list（参见 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md)）。
- `parent_membership` gate 评估需要其它 Realm 的成员 snapshot；origin reducer MAY 通过 [`../discovery/discovery-directory.md`](../discovery/discovery-directory.md) 的 verified snapshot 接口或直接 backfill；snapshot 不可达时 fail closed。

## 10. Policy Server 运行时挑战

Policy Server（[`../authz/policy-server.md`](../authz/policy-server.md)）声明 `applies_to` 包含 `join` 时，对每条 `cx.member.state{join}` Move 以及 `member.application` signed receipt / private record 调用 OpenAPI canonical path `/policy/check`。除既有 `decision` 外，Join 场景新增 obligation 子规范：

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
        "actor": "did:webvh:applicant.example",
        "action": "member.application",
        "request_canonical_digest": "sha256:...",
        "device_id": "cx:device:01964137-0000-7000-8000-000000000000"
      }
    }
  ]
}
```

applicant 完成挑战后，重新提交 join / application Move，在 `gate_proofs[]` 中追加 `{gate_id: "runtime:<challenge_id>", challenge_proof: {...}}`。`challenge_proof.challenge_id` 是 runtime challenge 的唯一匹配键；历史占位 `gate_id="_runtime"` 只能作为 UI/display 兼容标签，MUST NOT 参与 verifier 选择。Policy Server 重新校验后返回 `decision=allow`。`must_satisfy_before_resubmit=true` 时 reducer MUST 拒绝缺失对应 `challenge_id` proof 的重提。

`bound_to.request_canonical_digest` 按 [`policy-server.md` §4.1](../authz/policy-server.md) 的 proof-stripped transcript 计算：它绑定首次被 challenge 的原始 join / application 请求，而不是包含 `challenge_proof` 自身的最终重提 Move。重提 Move 除追加 runtime challenge proof 外不得改变原始请求语义；任何字段变更都必须重新走 `/policy/check` 并获取新的 challenge。

`obligations[].type` 注册值（`rate_limit` / `challenge` / `review_hold` / `drop_attachment`）维护在 [`../authz/policy-server.md` §4](../authz/policy-server.md) 表中；本规范是 `challenge` 类型在 join 路径上的 normative wire schema，其它路径（如 `cx.message.create`）若使用 `challenge` 必须遵循同一 envelope。

## 11. 反滥用约束

| 控制项 | 默认 | 强制要求 |
| --- | --- | --- |
| `application_ttl` | 168h | reducer 到期自动转 `rejected_reason="ttl_expired"`；不计 cooldown。 |
| `cooldown_after_reject` | 72h | reject 后 reducer MUST 拒绝同 actor 在窗口内的新 `member.application`。`request_changes` 不触发 cooldown。 |
| `max_open_applications_per_actor` | 1 | reducer 校验 actor 当前 pending 数；超出 `failed_precondition`。 |
| Quota constraint | 由 Realm `cx.realm.policy_components` 声明 | 推荐对 `cx.member.state{knock}` 配置 `quota.subtype=rate`（如 `max_operations=5/day`），通过既有 [`../authz/constraint-schema.md` §7](../authz/constraint-schema.md) 表达。 |
| Policy Server `challenge` | 高风险 Realm 推荐 | Sync Service 面对突发 knock 流量时 SHOULD 通过 Policy Server 注入 challenge obligation。 |

## 12. 与 MIMI 的映射

[`../extensions/mimi-interop.md` §9.1](../extensions/mimi-interop.md) `participation` 中 `join_policy` 子字段 SHOULD 由 facade 在 Contrix `realm.join_policy` component 与 MIMI room policy 之间双向归约；MIMI 侧暂未规范的 gate 类型作为 Contrix 专属 component 标记 `application/vnd.contrix.component+json`。MIMI facade 接收外部 join 请求时 SHOULD 至少强制执行 `claim_required` 与 `parent_membership` gate；`application_form` / `manual_review` / `challenge_response` 在 MIMI 客户端不支持 inline 表达时，facade SHOULD 拒绝跨域请求并指引 applicant 通过 Contrix 原生客户端完成。

## 13. 完整示例

公开知识社群，凭证持有者直通、否则走 5 道问卷 + CAPTCHA：

```json
{
  "candidate_kind": "realm.join_policy",
  "payload": {
    "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
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
      "review_capability": "cx.realm.join.review",
      "reviewer_quorum": "any",
      "application_ttl": "168h",
      "cooldown_after_reject": "168h",
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

对应 `cx.realm.join_rule.value="knock_restricted"`：凭 VC 自动通过的走自动解析路径，其余走申请-审核路径。

## 14. 规范性引用

- Realm 对象模型：[`../models/realm-and-space.md`](../models/realm-and-space.md)
- Capability 与 `cx.realm.join.review` 等 action：[`../authz/capabilities.md`](../authz/capabilities.md)
- Policy Server 与 obligation：[`../authz/policy-server.md`](../authz/policy-server.md)
- Claim 与 constraint：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)
- Federation 跨域加入：[`../sync/federation.md` §5.2](../sync/federation.md)
- Discovery Directory：[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)
- Audit trail / 申诉：[`./content-moderation.md` §6](./content-moderation.md)
- MIMI 互操作：[`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)
