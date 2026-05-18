---
title: Join Policy
---

## 1. 目标与范围

本文档定义 Space 的 **Join Policy** 模型，覆盖 gate 组合、自动解析路径、申请-审核路径、加密语义、联邦传播、反滥用与 MIMI 映射。原本作为 `space-and-place.md §3` 的子节存在；v1 拆出独立文件以便 governance / membership 相关讨论集中维护。`space-and-place.md` 现在只承担 Space 对象模型与 Place / hierarchy 部分。

当前 v1 core 的 active 机器 contract 仍以
`cx.space.join_rule`、`cx.space.policy_components`、capability 与 invite 状态机为准；
独立 join-policy Event.kind / schema 尚未进入 registry。实现若做实验，MUST 使用自有
extension namespace，并且不得在 describe/profile discovery 中把它声明为 active `cx.*`
标准 contract。

`default_join_rule` 枚举（[`../models/space-and-place.md` §2.2](../models/space-and-place.md)）只表达粗粒度的入口模式：`public` 直接进、`invite` 必须有人邀、`knock` 可申请、`restricted` / `knock_restricted` 有附加条件、`closed` 不收新人。但是 `restricted` 的"条件"是什么、`knock` 申请里能否带结构化材料、人工审批的决策是否上链审计、CAPTCHA / proof-of-work 等运行时挑战如何接入——这些都需要本文件统一定义。

本文定义的 **Join Policy** 与 `default_join_rule` 正交又互补：

- `default_join_rule` 决定**入口模式**（`public` / `invite` / `knock` / `restricted` / `knock_restricted` / `closed`）。
- Join Policy 决定**入口模式选定后，到 `membership=join` 必须穿越的 gate 集合**（凭证、问卷、挑战、人工审批等）的组合、解析顺序、加密语义和反滥用约束。
- `default_join_rule=public` 与 `default_join_rule=closed` 不消耗 Join Policy（前者无 gate，后者无入口）；其余四个枚举值的精确语义由 §4 与 Join Policy 交叉决定。

## 2. 设计原则

1. **Gate 是组合的，不是命名的。** 不再以新 enum 区分"附加条件类型"。Space 通过 `gates[]` + `combinator` 表达任意 AND/OR 组合；`knock_restricted` 等组合 enum 的语义由 `combinator` 直接表达，避免每加一类 gate 就要再造 enum。
2. **申请材料对外不可见。** Matrix `m.room.member{knock}` 的 free-text `reason` 因默认可见已成为 spam 通道。Contrix 申请正文 MUST 仅对 `cx.space.join.review` capability 持有方可见：E2EE Space 中通过 reviewer-only encryption envelope；非 E2EE Space 中由 Sync Service 强制访问控制并审计读取（`cx.audit.accessed`）。
3. **审核决策必须上链。** 所有审核接受 / 拒绝 MUST 是签名的 anchored Move，记录 reviewer DID、review reason、引用证据 hash。事后审计与申诉（参见 [`./content-moderation.md` §6](./content-moderation.md)）依赖该 trail。
4. **审核必须密码学绑定到 join。** 借鉴 Matrix `join_authorised_via_users_server` 的担保模式：随后的 `cx.invite.create` MUST 通过 `refs[role="join_authorised_by"]` 引用对应 review accept Move。reducer 校验该 ref 在写入时仍指向有效 capability 持有者。
5. **自动解析路径不强制走人工。** 当所有 gate 都可自动解析（claim presentation 验证、challenge proof 验证），applicant 可直接提交 `cx.member.state{membership=join}`，由 reducer 内联校验，无需 application / review Move。这条路径替代既有 `restricted` 入口模式的实质语义。
6. **Capability 仍是 allow 唯一来源。** Join Policy gate 通过即"可以提议加入"，但 reducer 仍按 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 校验 join Move 的 capability。Policy Server `obligations[]`（§11）只能在 capability 之上叠加额外要求（如 challenge），不能凭空创造权限。

## 3. Cell Family 与 State Event

```text
cell_id     := cx:cell:space.join_policy.v1:<space_id>
lattice     := cas-register
bottom      := reject
value shape := JoinPolicy（见下）
```

写入 cell 的候选事件在正式登记前记为 `space.join_policy`（无 `cx.` 标准前缀），需要 `cx.policy.manage` capability（与 `cx.space.policy_server` / `cx.space.policy_components` 同等级）。`cx.space.create` 时 SHOULD 通过 `cx.space.policy_components` 一并提供 join policy 初值；省略时 cell 维持 `null`，行为退化为"`default_join_rule` 单独决定"。

JoinPolicy 候选 schema 名：`space.join_policy.v1`。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `gates` | yes | `array<Gate>` | 1..16 项；空数组 MUST schema_violation。 | 必须穿越的 gate 列表。 |
| `combinator` | yes | `enum(all, any)` | 默认 `all`。 | gate 之间的组合语义。 |
| `review_capability` | conditional | `string` | 任一 gate `kind ∈ {manual_review, application_form}` 时必填；缺省 `cx.space.join.review`。 | 审核所需 capability。 |
| `reviewer_quorum` | no | `enum(any, majority, all) | object` | 默认 `any`。`object` 形式 `{ threshold: int, of: did[] }` 表达 N-of-M。 | 审核法定人数。 |
| `application_ttl` | no | `duration` | 默认 `168h`，最小 `1h`，最大 `8760h`（1y）。 | 申请未决超时即失效。 |
| `cooldown_after_reject` | no | `duration` | 默认 `72h`。 | 拒绝后同一 actor 重新申请的最短间隔。 |
| `max_open_applications_per_actor` | no | `integer` | 默认 `1`，最大 `5`。 | 同一 actor 在本 Space 同时未决申请上限。 |
| `applicant_visibility` | no | `enum(reviewer_only, members_after_join, public)` | 默认 `reviewer_only`。 | 申请正文谁可见；`members_after_join` 表示 join 成功后开放给 Space 成员（用于自我介绍场景）。 |
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

- `gate_id`：稳定 id，用于审计与 application 中的 proof 关联
- `kind`：取 `claim_required` / `application_form` / `challenge_response` / `manual_review` / `parent_membership` / `cooldown` 之一
- `auto_resolve`：该 gate 能否仅靠 applicant 提交的材料解析；`manual_review` / `application_form` 必为 `false`
- 其余字段按 `kind` 决定（见下表）

| `kind` | 必带字段 | 语义 | `auto_resolve` |
| --- | --- | --- | --- |
| `claim_required` | `requires_claims[]`（见 [`../authz/constraint-schema.md` §10](../authz/constraint-schema.md)） | applicant MUST 提交满足声明集合的 VC / claim presentation。 | `true` |
| `parent_membership` | `parent_space_refs: id:space[]`、`require_min_membership: enum(invite, join)` | applicant MUST 已是任一 parent space 的指定成员。reducer 在 join Move 校验时必须能够独立验证（snapshot 或 backfill）。等价于 Matrix MSC3083 `m.room_membership` 条件。 | `true` |
| `challenge_response` | `provider_did: did`、`challenge_kinds: enum(captcha, pow, attested_human, idp_oidc)[]`、`max_proof_age: duration` | applicant MUST 完成 provider 颁发的挑战并提交 signed proof。详见 §11。 | `true` |
| `application_form` | `questions[]`（见 §3.3） | applicant MUST 在 `member.application` 中提交对应 answer；reviewer 人工评估。 | `false` |
| `manual_review` | （无额外字段） | reviewer 必须显式签署 accept；不要求结构化问卷。 | `false` |
| `cooldown` | `min_interval_since_leave: duration` | applicant 上次 `cx.member.state{membership=leave}` 后未达冷却期 MUST 拒绝。仅作为 deny gate（与 `combinator` 无关，单独评估）。 | `true` |

未注册 `kind` MUST schema_violation；未注册的 `(kind, subfield)` 组合按 lattice `bottom=reject` 处理。

### 3.2 `directory_hint`

为帮助 Discovery Directory（[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)）告知 applicant "进入这个 Space 大概要做什么"，Space MAY 声明 directory hint。该 hint 是公开投影，**不得**包含敏感问卷正文：

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

reducer 在 `cx.space.join_rule` 与 join-policy cell 任一变更时 MUST 重新评估上述一致性约束；不一致 MUST `failed_precondition` 拒绝写入，并附带 `reason="join_rule_policy_mismatch"`。

## 5. 自动解析路径

适用条件：`default_join_rule ∈ {public, restricted, knock_restricted}` 且 applicant 拟使用的 gate 子集全部 `auto_resolve=true`。

applicant 直接提交：

```json
{
  "kind": "cx.member.state",
  "payload": {
    "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
    "subject_did": "did:webvh:bob",
    "membership": "join",
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

候选 durable Event；schema 名 `member.application.v1`，正式进入 v1 registry 前不得使用 `cx.*` 标准前缀。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `space_id` | yes | `id:space` | 申请目标 Space。 |
| `applicant_did` | yes | `did` | 等于 envelope `actor`。 |
| `knock_ref` | yes | `event_ref` | 引用 stage 1 的 `cx.member.state{knock}` event id。 |
| `policy_version` | yes | `sha256` | 提交时 `space.join_policy` cell value 的 canonical hash；reducer 校验 reviewer 决策时是否仍是同一 policy。 |
| `answers` | conditional | `array<Answer>` | 任一 `application_form` gate 存在时必填，覆盖该 gate 所有 `required=true` 的 question_id。 |
| `gate_proofs` | conditional | `array<GateProof>` | 任一可自动解析 gate 存在时按需提供（与自动解析路径同形）。 |
| `applicant_note` | no | `string` | 1..2000 chars 自由文本备注。 |
| `encryption_envelope` | conditional | `object` | E2EE Space 必填；见 §7。 |

`Answer` 形态：`{question_id, value: string|string[]|boolean}`；reducer 仅做存在性 / shape 校验，语义评估留给 reviewer。

### 6.3 `member.application.review`

durable Event，需要 `review_capability`。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `space_id` | yes | `id:space` |  |
| `application_ref` | yes | `event_ref` | 指向 §6.2 的 application event。 |
| `decision` | yes | `enum(accept, reject, request_changes)` | `request_changes` 允许 applicant 修订 answer 后重提，不计入 cooldown。 |
| `reason_code` | yes | `string` | 稳定原因码：`ok` / `incomplete_answers` / `policy_violation` / `claim_invalid` / `challenge_failed` / `duplicate` / `other`。 |
| `reason_text` | no | `string` | 1..1000 chars 自由文本，对 applicant 可见。 |
| `evidence_refs` | no | `event_ref[]` | 评审依据的其它 event（如 `cx.audit.*` 风险记录）。 |
| `reviewer_capability_proof` | yes | `object` | 引用授予 reviewer `review_capability` 的 grant id 与当时 frontier hash；reducer 必须在写入时再校验一次。 |

`reviewer_quorum != "any"` 时，reducer 需收集 N 个独立 reviewer 的 accept 才认为申请进入 `accepted` 状态；任一 reject 即终止。

### 6.4 `member.application.cancel`

applicant 可主动撤回；写入 `decision=canceled`，不计 cooldown。

### 6.5 接受后的 invite

application 进入 `accepted` 状态后：

1. 任一 reviewer 提交 `cx.invite.create`，`refs[role="join_authorised_by"]` MUST 引用对应 `member.application.review{accept}` event；
2. applicant 提交 `cx.invite.accept`；
3. reducer 在写入 `cx.invite.create` 时再次校验：被引用的 review accept 仍指向尚未消费的 application（防止同一 accept 被复用）、reviewer 在当前 frontier 仍持有 `review_capability`、application 未过 `application_ttl`、未被后续 `reject` / `cancel` 覆盖。

校验失败 `failed_precondition`，`reason_code="join_authorisation_invalid"`。

## 7. 加密与隐私

### 7.1 非 E2EE Space

`member.application` payload 在 wire 上保持明文，但 Sync Service / Principal Server MUST：

- 仅向 reviewer set（`review_capability` 持有方）与 applicant 自身投影 application 正文；
- 对其它 Space 成员投影占位（`{application_pending: true}`）；
- 对每次 reviewer 读取写一条 `cx.audit.accessed`（payload 包含 application event id 与读取者 DID）。

`applicant_visibility=members_after_join` 仅在 application 进入 `accepted` 且对应 `cx.invite.accept` 已落入 frontier 后，才允许向 Space 成员投影正文。

### 7.2 E2EE Space（`encryption_profile=mls_rfc9420`）

Space 主 MLS group 不包含尚未 join 的 applicant，因此申请正文不能直接走 Space MLS group。MUST 使用以下机制之一：

1. **Reviewer Sub-Group MLS**：Space 维护一个独立 MLS group `cx:mls:reviewer_subgroup:<space_id>:reviewers`，成员是当前所有 `review_capability` 持有方。applicant 通过 reviewer set 中任一成员公布的 KeyPackage 出 group commit + welcome，将 application 正文作为该 sub-group 的 application message 投递。reducer 通过 `cx.mls.commit.governance_binding` 验证 sub-group roster 与 capability 一致。
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

派生 view `cx.view.space.applications.v1`（[`../models/views.md`](../models/views.md)）SHOULD 提供：

- `pending`: 未决申请；
- `awaiting_review`: 已提交但 reviewer 未决；
- `accepted_pending_invite`: 审核通过但 `cx.invite.create` 尚未签发；
- `recently_decided`: 7 日内的 accept/reject 决策。

## 9. 联邦语义

跨域加入流程在 [`../sync/federation.md` §5.2](../sync/federation.md) 详述。本节仅说明 Join Policy 引入的不变量：

- `member.application` 与 `member.application.review` 都是候选 durable Event，参与正常 federation push / pull；
- `policy_version` 字段使 reviewer 与 applicant 显式承认评估时所用的 policy 快照，避免 reviewer 在不同 policy frontier 下决策导致争议；
- E2EE 场景下 reviewer sub-group MLS commit 通过既有 `cx.mls.*` 联邦机制传播；envelope encryption 由 origin Principal Server 投递到目标 reviewer 的 device list（参见 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md)）。
- `parent_membership` gate 评估需要其它 Space 的成员 snapshot；origin reducer MAY 通过 [`../discovery/discovery-directory.md`](../discovery/discovery-directory.md) 的 verified snapshot 接口或直接 backfill；snapshot 不可达时 fail closed。

## 10. Policy Server 运行时挑战

Policy Server（[`../authz/policy-server.md`](../authz/policy-server.md)）声明 `applies_to` 包含 `join` 时，对每条 `cx.member.state{join}` / `member.application` Move 调用 `/contrix/v1/check`。除既有 `decision` 外，Join 场景新增 obligation 子规范：

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
        "action": "cx.member.application",
        "request_canonical_hash": "sha256:...",
        "device_id": "cx:device:01964137-0000-7000-8000-000000000000"
      }
    }
  ]
}
```

applicant 完成挑战后，重新提交 join / application Move，在 `gate_proofs[]` 中追加 `{gate_id: "_runtime", challenge_proof: {...}}`（保留 `gate_id="_runtime"` 作为运行时挑战的占位）。Policy Server 重新校验后返回 `decision=allow`。`must_satisfy_before_resubmit=true` 时 reducer MUST 拒绝缺失对应 challenge_proof 的重提。

`obligations[].type` 注册值（`rate_limit` / `challenge` / `review_hold` / `drop_attachment`）维护在 [`../authz/policy-server.md` §4](../authz/policy-server.md) 表中；本规范是 `challenge` 类型在 join 路径上的 normative wire schema，其它路径（如 `cx.message.create`）若使用 `challenge` 必须遵循同一 envelope。

## 11. 反滥用约束

| 控制项 | 默认 | 强制要求 |
| --- | --- | --- |
| `application_ttl` | 168h | reducer 到期自动转 `rejected_reason="ttl_expired"`；不计 cooldown。 |
| `cooldown_after_reject` | 72h | reject 后 reducer MUST 拒绝同 actor 在窗口内的新 `member.application`。`request_changes` 不触发 cooldown。 |
| `max_open_applications_per_actor` | 1 | reducer 校验 actor 当前 pending 数；超出 `failed_precondition`。 |
| Quota constraint | 由 Space `cx.space.policy_components` 声明 | 推荐对 `cx.member.state{knock}` 配置 `quota.subtype=rate`（如 `max_operations=5/day`），通过既有 [`../authz/constraint-schema.md` §7](../authz/constraint-schema.md) 表达。 |
| Policy Server `challenge` | 高风险 Space 推荐 | Sync Service 面对突发 knock 流量时 SHOULD 通过 Policy Server 注入 challenge obligation。 |

## 12. 与 MIMI 的映射

[`../extensions/mimi-interop.md` §9.1](../extensions/mimi-interop.md) `participation` 中 `join_policy` 子字段 SHOULD 由 facade 在 Contrix `space.join_policy` component 与 MIMI room policy 之间双向归约；MIMI 侧暂未规范的 gate 类型作为 Contrix 专属 component 标记 `application/vnd.contrix.component+json`。MIMI facade 接收外部 join 请求时 SHOULD 至少强制执行 `claim_required` 与 `parent_membership` gate；`application_form` / `manual_review` / `challenge_response` 在 MIMI 客户端不支持 inline 表达时，facade SHOULD 拒绝跨域请求并指引 applicant 通过 Contrix 原生客户端完成。

## 13. 完整示例

公开知识社群，凭证持有者直通、否则走 5 道问卷 + CAPTCHA：

```json
{
  "kind": "space.join_policy",
  "payload": {
    "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
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
      "review_capability": "cx.space.join.review",
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

对应 `cx.space.join_rule.value="knock_restricted"`：凭 VC 自动通过的走自动解析路径，其余走申请-审核路径。

## 14. 规范性引用

- Space 对象模型：[`../models/space-and-place.md`](../models/space-and-place.md)
- Capability 与 `cx.space.join.review` 等 action：[`../authz/capabilities.md`](../authz/capabilities.md)
- Policy Server 与 obligation：[`../authz/policy-server.md`](../authz/policy-server.md)
- Claim 与 constraint：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)
- Federation 跨域加入：[`../sync/federation.md` §5.2](../sync/federation.md)
- Discovery Directory：[`../discovery/discovery-directory.md`](../discovery/discovery-directory.md)
- Audit trail / 申诉：[`./content-moderation.md` §6](./content-moderation.md)
- MIMI 互操作：[`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)
