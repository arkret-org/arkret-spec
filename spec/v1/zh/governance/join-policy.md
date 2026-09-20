---
title: Join Policy
status: candidate
normative: true
stability: v1
updated: 2026-08-29
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释。

## 1. 范围

Join Policy 定义加入 Realm 前由当前治理 Station在 commit admission 时自动验证的 gate。它不是独立 Event kind；权威值是 current committed `ak.realm.policy_bundle` payload 的 `join_policy` 组件。

当前 v1 不定义独立的 join application、review 或 cancel 工作流，也不定义这些概念的 HTTP 包装接口、私有 receipt 或审核队列。`ak.member.state{membership="knock"}` 仅表达无正文的加入意向；结构化申请正文、问卷、人工审核和审核者私有投递均不属于当前协议。

## 2. 与入口规则的关系

`ak.realm.join_rule` 决定入口模式；Join Policy 只增加自动、可重放验证的约束：

| `join_rule` | 入口语义 | Join Policy |
| --- | --- | --- |
| `public` | 可直接提出 join | 仍必须通过所有 hard/deny gate |
| `invite` | 必须有有效 invite | invite 之外仍评估 hard/deny gate |
| `knock` | 可先提交无正文 knock | knock 不产生加入授权；后续 join 仍需有效授权并通过 gate |
| `restricted` | 必须携带满足 policy 的自动证明 | 评估 applicant 可选自动 gate |
| `knock_restricted` | 无正文 knock + 自动证明 | 不存在额外人工审核支线 |
| `closed` | 不接受新的普通 join | hard/deny gate 仍不得被绕过 |

`principal_admission` 与 `cooldown` 对所有入口模式生效。切换 `join_rule` 不得绕过 DID allow/deny 约束或离开冷却期。

`join_rule` 与 `join_policy` 的一致性由 reducer 强制：`join_rule` 为 `restricted` 或 `knock_restricted` 时，`join_policy` MUST 含至少一个自动 gate（`claim_required` / `challenge_response` / `parent_membership`），且 `combinator` 不得使评估结果与声明的入口模式矛盾：只含 `principal_admission` / `cooldown` 硬门时，按 §4 规则 2-3 的求值顺序 `restricted` 的可通过集合与 `public` 完全相同，`knock_restricted` 则退化为 `restricted`。`restricted` 未配任何自动 gate、或 `knock_restricted` 的 gate 组合实际退化为 `restricted` 时，写入 `ak.realm.join_rule` / `ak.realm.policy_bundle` 的 reducer MUST 以 `failed_precondition`、`reason_code=join_rule_policy_mismatch` 拒绝，不接受互相矛盾的入口声明。

首次跨站引导只授权本次 intent 必需且 policy 允许披露的认证事实。申请人的 Station先验证 nonce-bound `RealmAuthorityBundle`，再把 exact signed Event提交给当前治理 Station；Realm join/knock 不授予 private Circle、Sidecar、其它成员身份、普通消息、附件或 MLS secrets 的额外读取权。成功后 bootstrap 只返回签名 typed snapshot 和获准 stream tails，不默认拉全历史。

## 3. 数据模型

机器真源是 [`event-payload.schema.json#/$defs/join_policy_component`](../../artifacts/schemas/event-payload.schema.json)。最小形态：

```json fragment
{
  "gates": [
    {
      "gate_id": "employee-credential",
      "kind": "claim_required",
      "auto_resolve": true,
      "required_claims": ["employee"]
    }
  ],
  "combinator": "all"
}
```
| 字段 | 必填 | 约束 |
| --- | --- | --- |
| `gates` | yes | 1..16；`gate_id` 在数组内 MUST 唯一 |
| `combinator` | yes | `all` 或 `any` |
| `directory_hint` | no | 仅可公开摘要和支持的 challenge 类型，不得含凭证值或主体信息 |

每个 gate 至少包含稳定的 `gate_id` 与 `kind`。未知 kind、未知标准字段组合或重复 `gate_id` MUST 以 `schema_violation` fail closed；重复 id 的 reason code 为 `join_policy_duplicate_gate_id`。

### 3.1 Gate 类型

| `kind` | 必要材料 | 语义 |
| --- | --- | --- |
| `claim_required` | `required_claims[]`、`trusted_issuer_ids[]` | 验证调用方提交的 claim presentation（§4 的 `join_gate_proof{kind="claim_required"}`）：`issuer_id` MUST 落在 `trusted_issuer_ids[]`，`claims[]` MUST 覆盖 `required_claims[]`；claim 畸形、issuer 不在边界内、签名不可验证或缺少 proof 项时拒绝，授权审计 reason 为 `claim_invalid`。issuer 边界与 [`../authz/capabilities.md`](../authz/capabilities.md) `required_claims[].trusted_issuer_ids` 同名同义 |
| `challenge_response` | `provider_did`、`challenge_kinds[]`、`max_proof_age` | 验证 CAPTCHA、PoW、attested-human 或 OIDC challenge 的签名结果 |
| `parent_membership` | `membership_source_realm_ids[]`、`require_min_membership="join"` | 仅当全部 source 与 target Realm 由同一 current governing Station 治理、且全部依赖可验证时，验证调用方在至少一个声明来源 Realm 的 authoritative current `member_state` 为 accepted `join`；待处理 Invite 与 `knock` 均不满足该 gate |
| `principal_admission` | DID method、principal allowlist 或 denylist selector 至少一个 | 在其它 gate 前执行的硬准入门；deny 优先 |
| `cooldown` | `min_interval_since_leave` | 最近一次由成员本人签署的主动 leave 未过窗口时拒绝 |

gate item 与 `join_policy` component 都是 closed object；每个 kind 只能携上表列出的专属材料与通用
`gate_id/kind/auto_resolve`，`auto_resolve` 出现时只能为 `true`。扩展字段、把某 kind 的材料放进另一 kind、或缺任一
required material 都必须 schema reject，不能由 reducer 猜默认值。

`parent_membership` 的每个 `membership_source_realm_ids[]` 都必须对应目标 Realm 内 current active 的
`(source_realm_id, link_kind="join_gate_from")` `realm_link` row。写入包含该 gate 的 join policy 时，当前 governing
Station MUST 验证这些 link 均 active，且每个 source Realm 与 target Realm 的已验证 current authority tenure
`service_id` 逐字相同；每个 Realm 自己的 `governance_generation` 必须为 current，但不同 Realm 的 generation 数值
**不得互相比较**，也不得改用 capability `authority_generation`。任一 source 缺 link、由另一 Station 治理、current
authority/handoff state 不可确认，policy Event MUST fail closed 且零写入。已接受 policy 不因随后 handoff 被隐式改写；
每次 join admission 都必须重新执行相同检查。

`principal_admission` 的 identity predicate 只允许以下 closed 字段：
`allowed_account_ids/denied_account_ids: AccountId[]`、
`allowed_actor_ids/denied_actor_ids: ActorId[]`、
`allowed_principal_ids/denied_principal_ids: DidCoreId[]` 与正交的
`allowed_did_methods[]`。至少一个字段必须出现。
predicate 适用角色由同一 admission basis 中已接受的 subject classification 决定，不能由 list 命中反推：

- `*_account_ids` 只对 `subject_class=human` 的 exact AccountId 求值；
- `*_actor_ids` 只对 `subject_class=agent|service` 的 exact ActorId 求值；Agent 即使 ActorId 使用 account 分支也仍只走
  actor predicate，不能同时走 account predicate；
- `*_principal_ids` 对所有 subject class 求值，但只用于 policy 明确声明“同一密码学主体跨账号”的场景，比较
  Actor 的 principal 分量；它不能补全 Station，也不能把两个 Account/Actor 合并为同一成员；
- `allowed_did_methods` 对该 Actor principal 的 evidence-time 已接受 DID method 求值，current resolver 或 transport DID
  不能替代。

同一 gate 内先对全部 applicable deny predicate 求并集，任一命中立即拒绝；随后对每个**出现的** applicable allow
predicate 求交集，必须逐个命中。省略 allowed 字段表示该维度不约束；显式空 allowed array 表示该适用角色无成员可
通过。省略或显式空 denied array均不拒绝任何成员。inapplicable role-specific predicate 不参与该 applicant 的交并运算，
但 principal-core 与 DID-method predicate始终 applicable。多个 `principal_admission` gate 与 `cooldown` gate固定全部
AND，任一失败即拒绝，不受 component `combinator` 影响；其它 gate 才按 `all/any` 组合。deny 优先级跨 gate 也不被
任一 allow 命中覆盖。上述规则使 Account 与包含 account 分支的 Actor 不成为两套含混等价 allowlist。

所有 gate 均必须可由当前治理 Station根据签名 Event、当前 committed typed state和显式证明确定性求值。依赖服务端私有审核记录、自由文本判断或未登记外部状态的 gate 不得写入当前 v1 policy。

### 3.2 `directory_hint`

`directory_hint` 是公开发现提示，不是授权证据。它 MAY 包含 `summary` 与 `challenge_kinds_displayed[]`；接收方不得从 hint 推导 policy，也不得因 hint 缺失而放宽 gate。

## 4. 评估规则

1. 当前治理 Station先验证 Event envelope、producer proof、capability、目标 Realm及本次 Event 的目标 stream；Event 不携带 authority-commit basis、RealmCommit basis或 predecessor。
2. 先评估全部 `principal_admission` 和 `cooldown` gate；任一失败即拒绝。
3. 再按 `combinator` 评估其余自动 gate。`all` 要求全部成功；`any` 要求至少一个成功。
4. `gate_proofs[]` 的唯一合法项形态是封闭的 [`event-payload.schema.json#/$defs/join_gate_proof`](../../artifacts/schemas/event-payload.schema.json)。每一项以 wire 成员携带绑定元组 `gate_id`、`realm_id`、`applicant_actor_id`、`policy_digest`、`created_at`，并由 `proofs[]`（context `ak.join_gate_proof.v1`，`payload_digest` = 去掉 `proofs` 后本对象的 canonical JSON sha256，登记于 `proof-context-registry.json`）覆盖；reducer MUST 先按字段比较再验签：`realm_id` ≠ 目标 Realm、`applicant_actor_id` ≠ `member_id`、`policy_digest` ≠ 当前 accepted `join_policy` component 的 canonical JSON sha256、`gate_id` 不在 policy 中或 `kind` 与该 gate 的 `kind` 不一致，都是绑定失败。只有 `challenge_response` 与 `claim_required` 两种 gate 接受 proof 项；`principal_admission` / `cooldown` 从目标 Realm 已接受状态重放；`parent_membership` 只能按下条规则读取同一 Station 持有的 source authoritative current state，三者都不读 caller proof。签名 key 的解析路径固定：`challenge_response` 的 `proofs[].verification_method` MUST 经已登记 DID method adapter 解析为 gate `provider_did` 控制的 key；`claim_required` MUST 解析为 `issuer_id` 控制的 key，且 `issuer_id` ∈ `trusted_issuer_ids[]`。freshness 只以该 Event 已签名的 `created_at` 为准，MUST NOT 使用 receiver 本地时钟：`proof.created_at + max_proof_age < event.created_at` 为 `challenge_expired`，`proof.created_at > event.created_at` 或任一绑定 / 签名 / key 解析失败为 `challenge_proof_invalid`；`challenge_failed`（challenge 答案本身核验失败，或 `challenge_response` gate 没有对应 proof 项）与二者互斥，不得混用。policy 含自动 gate 而 Event 未携带对应 proof 项时，结果与 gate 失败相同（对非成员统一 `gate_check_failed`）。同一 `gate_id` 出现两次是 `schema_violation`。
5. 对 `parent_membership`，governing Station MUST 在接受目标 join 的同一事务中按 RealmId canonical bytes 排序锁定
   source 与 target 的 current authority-tenure/handoff rows、target policy／active `join_gate_from` rows，以及每个 source
   Realm 中 applicant 的 authoritative current `member_state` lookup。全部 source 的 link、authority 和 authoritative lookup
   都必须可验证；其后只要至少一个 source 的 exact current value 为 accepted `membership="join"` 即满足 gate，leave、ban、
   knock、authoritative absence 或 terminal value 均不命中。若 source/target current tenure 的 `service_id` 不相同、任一
   Realm 正在 handoff、dependency 无法形成同一内部事务 cut 或 authoritative lookup 不可用，MUST 使用统一
   `gate_check_failed` fail closed，且不得写入 Event、RealmCommit 或 target `member_state`。同一 Station 的分库部署若不能
   提供该原子事务，也必须拒绝，不能用 saga 补偿。cache、replica、Directory、历史 Event 与 caller assertion 都不能替代
   该读取。handoff 完成后只有重新满足同 Station 条件并读取新 tenure 下的 current rows 才能通过；未来跨 Station gate
   必须作为带 authenticated membership assertion、peer operation、freshness 与 handoff 合同的新 profile 注册。
6. source leave／ban、link tombstone 或任一 Realm handoff 与目标 join 并发时，按上述统一锁序线性化：依赖变更先取得锁，
   join 零写入拒绝；join 先取得锁并提交，则本次 admission 有效。之后的 source change 不级联撤销已经加入目标 Realm 的
   membership，因为 Realm link 不传播 membership。
7. gate 成功仅说明 admission 条件满足，不创建 capability、invite 或 membership。最终 `membership=join` 只有在同一请求获得有效 `RealmCommit` 后才成为 accepted。

对尚未成为成员的调用方，gate 失败 MUST 使用统一的 `gate_check_failed` 或等价不可枚举结果；不得暴露 allowlist 命中、Realm 存在性、凭证差异或成员状态。proof gate 的详细授权审计 reason 集合包含 `claim_invalid`、`challenge_failed`、`challenge_proof_invalid` 与 `challenge_expired`；parent-membership 的缺 link／跨 Station／handoff／读取不可用与未 join 只可作为 Station-private audit stage，不新增 applicant 可见 wire reason。

## 5. Knock 与隐私

`ak.member.state{membership="knock"}` 是 producer-signed、authority-committed typed Event，MUST NOT 携带申请正文、自由文本、answers、3PID、附件或审核材料。收到这些字段时 receiver MUST 拒绝，而不是存入 shared Realm history。

当前协议没有 knock 对应的标准申请读取面。产品若需要人工申请流程，必须作为独立治理扩展定义完整的身份、加密、审计、保留期和 SDK 契约；未登记的局部 HTTP wrapper 不属于 v1。

## 6. 联邦与路由

跨域 join Event 只通过 Event submit/forward surface 传输。`RealmJoinCandidate` 仅是 invitee Station 用于取得 nonce-bound authority bundle 的不可信 locator，不携带 proof、Realm scope、逐 locator 时间或 authority assertion，也不产生 ingress authority；Directory、invite delivery 与 join intake MUST 直接引用同一个 closed core。客户端不得直连候选服务绕过自己的 Station。

申请人的 Station MUST 以 `join_target.realm_id` 作为本次请求唯一 Realm scope，验证 authority bundle，并核对 Realm、Event producer 与 locator 指向的 service identity；只有 Realm genesis、连续 handoff chain 与 caller nonce 绑定且尚未到期的 `current_assertion` 可以确定 current governance Station。locator 不另设 TTL/skew：Directory 使用 enclosing `as_of / stale`，invite 使用 enclosing `expires_at`。当前治理 Station MUST 在 commit 位置独立验证 producer signer、Join Policy、invite/capability 和 current membership/policy。Directory/search projection、裸 URL、部署已知 peer、邀请人 Station 或 mirror 不得成为额外授权来源。

## 7. 规范性引用

- Realm 与 policy bundle：[`../models/realm-and-space.md`](../models/realm-and-space.md)
- Event admission：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)
- AccountId / ActorId identity：[`../models/common-fields.md`](../models/common-fields.md) 与 [`../identity/account-lifecycle.md`](../identity/account-lifecycle.md)
- Federation：[`../sync/federation.md`](../sync/federation.md)
- 机器 schema：[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json)
