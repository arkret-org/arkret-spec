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

Join Policy 定义加入 Realm 前可由 reducer 自动验证的 gate。它不是独立 Event kind，也没有独立 cell：权威值是 `ak.realm.policy_bundle` payload 的 `join_policy` 组件，随 `ak.component.realm.policy_bundle.v1` 的 `cas_register` 一起收敛。

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

## 3. 数据模型

机器真源是 [`event-payload.schema.json#/$defs/join_policy_component`](../../artifacts/schemas/event-payload.schema.json)。最小形态：

```json
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
| `claim_required` | `required_claims[]` | 验证调用方提交的 VC / claim presentation |
| `challenge_response` | `provider_did`、`challenge_kinds[]`、`max_proof_age` | 验证 CAPTCHA、PoW、attested-human 或 OIDC challenge 的签名结果 |
| `parent_membership` | `membership_source_realm_ids[]`、`require_min_membership` | 验证调用方已在声明的来源 Realm 具有最低成员状态 |
| `principal_admission` | DID method、principal allowlist 或 denylist selector 至少一个 | 在其它 gate 前执行的硬准入门；deny 优先 |
| `cooldown` | `min_interval_since_leave` | 最近一次由成员本人签署的主动 leave 未过窗口时拒绝 |

所有 gate 均必须可由 reducer 根据签名 Event、已接受状态和显式证明确定性重放。依赖服务端私有审核记录、自由文本判断或未登记外部状态的 gate 不得写入当前 v1 policy。

### 3.2 `directory_hint`

`directory_hint` 是公开发现提示，不是授权证据。它 MAY 包含 `summary` 与 `challenge_kinds_displayed[]`；接收方不得从 hint 推导 policy，也不得因 hint 缺失而放宽 gate。

## 4. 评估规则

1. reducer 先验证 Event envelope、producer proof、CBA basis、capability 与目标 Realm。
2. 先评估全部 `principal_admission` 和 `cooldown` gate；任一失败即拒绝。
3. 再按 `combinator` 评估其余自动 gate。`all` 要求全部成功；`any` 要求至少一个成功。
4. 每个 `gate_proofs[]` 项 MUST 绑定 `gate_id`、目标 Realm、applicant、policy frontier/digest 和 proof 创建时间；跨 Realm、跨主体、跨 policy revision 重放 MUST 失败。
5. gate 成功仅说明 admission 条件满足，不创建 capability、invite 或 membership。最终 `membership=join` 仍按普通 Event admission 和成员状态机处理。

对尚未成为成员的调用方，gate 失败 MUST 使用统一的 `gate_check_failed` 或等价不可枚举结果；不得暴露 allowlist 命中、Realm 存在性、凭证差异或成员状态。详细原因只可写入授权审计。

## 5. Knock 与隐私

`ak.member.state{membership="knock"}` 是公开 Control Move，MUST NOT 携带申请正文、自由文本、answers、3PID、附件或审核材料。收到这些字段时 receiver MUST 拒绝，而不是存入 shared Realm history。

当前协议没有 knock 对应的标准申请读取面。产品若需要人工申请流程，应作为未来独立治理扩展重新设计完整的身份、加密、审计、保留期和 SDK 契约；不得恢复已删除的局部 HTTP wrapper。

## 6. 联邦与路由

跨域 join Event 只通过普通 Event 提交/转发面传输。`RealmJoinCandidate` 仅是 invitee Principal Server 可使用的有界转发提示，不产生 ingress authority；客户端不得直连候选服务绕过自己的 Principal Server。

接收方 MUST 独立验证 Realm、Event producer、origin Principal Server admission proof、candidate provenance、Join Policy、invite/capability 与 CBA basis。Directory/search projection、裸 URL、部署已知 peer 或 mirror 不得成为额外授权来源。

## 7. 规范性引用

- Realm 与 policy bundle：[`../models/realm-and-space.md`](../models/realm-and-space.md)
- Event admission：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)
- Member delivery binding：[`./member-delivery-binding.md`](./member-delivery-binding.md)
- Federation：[`../sync/federation.md`](../sync/federation.md)
- 机器 schema：[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json)
