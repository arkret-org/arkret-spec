---
title: 有界离线发布、AuthorizationLease 与 IngressReceipt
status: candidate
normative: true
stability: v1
updated: 2026-07-28
---

# 有界离线发布、AuthorizationLease 与 IngressReceipt

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Arkret v1 不承诺无限期离线写在任意未来都可首次发布。撤销边界由 basis-bound lease 与签名
ingress receipt 给出；Event `created_at` 和 verifier 本地首次见到时间均无此权限。

## 1. AuthorizationLease

```text
AuthorizationLease {
  authorization_lease_id,
  basis_ref,
  actor_id,
  device_id,
  scope_ref,
  action,
  authorization_rule_id,
  risk_tier,
  issued_at,
  expires_at,
  authority_set_ref,
  authority_set_policy,
  proofs
}
```

`lease_digest = sha256(canonical_json(lease_without_proofs))`。每个 issuer proof 必须签
`canonical_json({context:"ak.authorization-lease-proof-v1", payload_digest:lease_digest,
authority_set_ref, verification_method, created_at, domain?, audience?})`；proof `created_at` 必须逐字
等于 lease `issued_at`。proof 条数与唯一 issuer 数必须满足 basis 中已接受的 authority-set policy，
数组长度本身不等于 quorum。

`basis_ref` 在 `single_did` / `threshold` / `mixed` 下是单个 accepted Seal ref；在
`open_set` 下必须是包含 `leaves[]`、`control_event_set_root` 与 `state_root` 的完整
`seal_basis`，不能用任一单 leaf 冒充 joined view。lease 只能收窄该 basis 中已存在的
authorization。verifier MUST 从 accepted CBA basis
验证 issuer/delegation、actor/device、scope、action、risk 与有效期；lease 不能创建 capability，
不能把 medium/high action 降为 low，也不能跨 scope 使用。

`authority_set_ref` 是 CBA 各 authority/quorum 场景共用的闭合对象
`{authority_set_id, authority_set_digest}`。`authority_set_id` 必须是登记的
`ak.authority_set.*.v1` policy symbol；`authority_set_digest` 必须等于该 policy 在 `basis_ref`
控制面视图中的 canonical digest。verifier MUST 同时校验 id、digest、quorum、delegation 与
revocation authority，不得只按可变 registry 名称解析当前值。

`authority_set_policy` 是
[`ak.schema.authority_set_policy.v1`](../../artifacts/schemas/authority-set-policy.schema.json)
的完整 concrete policy bytes。它不是可选提示：

1. `authority_set_policy.authority_set_id` MUST 等于
   `authority_set_ref.authority_set_id`；
2. `SHA-256(JCS(authority_set_policy))` MUST 等于
   `authority_set_ref.authority_set_digest`；
3. policy 的 kind、source kind与ordered `authorization_rules[]` MUST 命中
   [`authority-set-policy-registry.json`](../../artifacts/registry/authority-set-policy-registry.json)
   中同 id 的 template；
4. verifier MUST 使用 `basis_ref` 与 `CbaProofBundle` 重放 accepted control state，重新派生
   source ref/digest/generation、每个rule的issuer methods、scope、actions 与 threshold。

`authorization_rules[]` 是替代分支，不是一个可合并的全局issuer set。每个rule独立固定
`rule_id + issuer_role + allowed_actions + issuers + threshold`；lease必须携带
`authorization_rule_id`，verifier按该id精确选择唯一rule，再确认该rule覆盖lease的`action`
并独立满足其quorum。不同rule可以覆盖同一action；verifier不得按action、issuer交集或
threshold猜测分支，也不得把不同recovery proof family的issuer拼成一个较弱门限。
缺失或未知`authorization_rule_id`、所选rule不允许`action`、proof issuer不属于所选rule、
或把多个rule的proof合并凑threshold，均必须fail closed为`authorization_denied`。同一policy
中至少两个rule覆盖同一action时，分别显式选择各rule的lease都合法，前提是各自独立满足
所选rule的全部验证条件。

因此 inline policy 只提供可移植的 canonical bytes，不是自报 authority。registry template
也只固定投影算法和值域，不能替代 basis 中的 accepted source。candidate、未 Seal 或晚于
`basis_ref` 的控制对象不得给该 lease 创造 authority。

协议最大 TTL：

| risk tier | `expires_at - issued_at` 最大值 |
| --- | ---: |
| `low` | 24 hours |
| `medium` | 8 hours |
| `high` | 1 hour |

未知 action 按 `high`。Realm policy MAY 收紧但不得放宽。高风险 lease 的 issuer quorum MUST
与同一 `security_barrier` revoke authority set 相交并满足 `2k > n`。

### 1.1 RecoveryTransaction 的 authority ownership

fresh-device recovery 不存在“replacement device因为通过 recovery proof即可自行签 lease”的
规则。服务端创建 recovery session时必须从 accepted basis snapshot一个 closed
`publication_authority_context`并把其digest纳入 recovery proof transcript：

- A模型使用`ak.authority_set.recovery_cross_signing.v1`，只有当前snapshot generation的SSK
  可为固定`ak.device.authorize`和
  `ak.device.list_update`签发lease；
- B模型local re-anchor使用`ak.authority_set.recovery_identity_reanchor.v1`，每个allowed proof
  family的issuer集合与threshold从session创建时accepted sealed recovery policy完整投影；满足
  其中一个完整authorization rule的recovery
  authority才可为固定`ak.device.reanchor`签发lease；
- B模型Account Authority lease使用`ak.authority_set.recovery_account_authority.v1`。该
  authority必须已经由pre-fence accepted DID document委托，并在
  `authorize_recovery_device`首次durable outcome中同时签发lease。

每份lease的basis、actor、replacement device、scope、action、risk与authority-set都必须逐字
等于session context或transaction-bound publication intent。SSK、root/recovery method或Account
Authority只有在accepted basis明确把它列为相应high-risk issuer时才有效；角色名称本身不产生
authority。协议不登记一个允许客户端请求任意action lease的通用endpoint。

每个 accepted recovery policy version 必须携带 immutable `acceptance_basis`。该 basis 引用已把
承载该 policy 的 Principal Control Realm `ak.policy.set` Event纳入control state的accepted
Seal/SealBasis；policy publish request必须是该Event的完整`EventInitialSubmission`。Event
actor/scope、payload principal、lease与accepted Seal必须一致。command只有在该basis
materialize后才能返回成功或推进active policy；此前对同一Event id返回retry-safe
`frontier_unavailable`，不得生成第二policy Event。B 模型 session 的
`publication_authority_context.basis_ref` 必须逐字等于该 `acceptance_basis`，不得借用 live
device-generation frontier、`accepted_at` 或 inline policy bytes。authority policy 的
`source_ref=policy_id`、`source_digest=SHA-256(JCS(RecoveryPolicy))`、
`generation_ref=policy_version(decimal)`。所谓“零 Seal frontier”只允许
device-generation/re-anchor frontier 为空，不表示 recovery policy 可以没有自己的 acceptance
basis。

B 模型 policy 的 `publication_authorization_rules[]` 必须由 policy
`auth_data.signed_fields`覆盖，并与`allowed_proof_kinds[]`一一对应。它是确定性投影输入而不是
自报 authority：session creator必须在policy `acceptance_basis`重算每个exact DidUrl。规则固定
只允许`ak.device.reanchor`；principal-signing使用accepted policy authority method；
recovery-unlock使用active `recovery_keys[].verification_method`且threshold=1；device-quorum把
每个member在basis中解析为唯一current device method并使用`device_quorum.k`；trusted service
使用entry中与`service_id`同controller DID的`authorization_verification_method`且threshold=1。
threshold-recovery完成Shamir重构后使用policy中的recovery signing key、signature
threshold=1；`threshold.k`是secret reconstruction门限，绝不能复制成PayloadProof签名quorum。
proof verified后，prepared plan与lease的`authorization_rule_id`必须逐字等于已验证proof
family对应的`publication_authorization_rules[].rule_id`；不得在其它同action rule间切换。

## 2. IngressReceipt

```text
IngressReceipt {
  receipt_id,
  event_digest,
  authorization_lease_id,
  received_at,
  service_id,
  authority_set_ref,
  proofs
}
```

`receipt_digest = sha256(canonical_json(receipt_without_proofs))`。每个 ingress proof 必须签
`canonical_json({context:"ak.ingress-receipt-proof-v1", payload_digest:receipt_digest,
authority_set_ref, verification_method, created_at, domain?, audience?})`；proof `created_at` 必须逐字
等于 `received_at`。同一 verification method 的重复 proof 只计一次。

Event 必须在 lease `expires_at` 之前被 policy 接受的 ingress 签收。`received_at` 必须由 issuer
产生、进入签名，且满足 `issued_at <= received_at <= expires_at`。lease 到期后首次出现且没有
合格 receipt 的 Event 永久拒绝；已有合格 receipt 的相同 event digest 可在之后缓存、重传和
federation。

receipt 证明“该 digest 在期限内到达一个被 policy 接受的 ingress”，不证明 Event 已通过
reducer、已进入数据 projection、已被 peer 看见或已获 Seal finality。

### 2.1 提交与重传封装

lease、receipt 与 `CbaProofBundle` 都不是 Event 字段，也不进入 Event digest。首次提交使用：

```text
EventInitialSubmission {
  event,
  authorization_lease,
  cba_proof_bundles?
}
```

ingress 在验证 lease、Event proof、scope 与 CBA basis 后，必须把签发的 receipt 持久化并通过
`EventsSubmitOutcome.ingress_receipts[]` 返回。相同 Event canonical bytes 的幂等重试必须返回
原 receipt，不得用新的 `received_at` 重签，从而延长已经固定的撤销窗口。

peer federation 使用：

```text
EventFederationSubmission {
  event,
  authorization_lease,
  ingress_receipts[]
}
```

至少携带一个 receipt；receiver 再按目标 Realm 的 issuer/threshold/transparency policy 判断证据
是否充分。request 级 `cba_proof_bundles[]` 只负责补齐 basis closure。任何服务都不得把这些
传输证据复制进 Event，或因本地较晚首次见到而改写 `received_at`。

## 3. Profile 与审查风险

| profile/保障 | issuer 要求 |
| --- | --- |
| `single_did` 基础 | 当前 authority 或 basis 中明确委托的 admission signer；允许单 ingress，但必须广告 `single_ingress_censorship_risk=true`。 |
| `threshold` / `mixed` | Realm policy 指定 admission quorum。 |
| `open_set` low/medium | basis-bound issuer policy；joined view 补齐后重验。 |
| 任意 profile high | 与 barrier revoke authority 相交的 quorum。 |

Realm policy MUST 至少能声明多个 issuer、receipt threshold、delegation、transparency、
failover 与 health endpoint。高保障 profile MUST 使用多 issuer threshold，或一个 issuer 加
append-only transparency inclusion proof；不得只依赖无审计的单 ingress。

## 4. 撤销窗口

最坏撤销窗口是：

```text
max_remaining_lease_ttl
+ ingress/transparency propagation bound
+ verifier dependency fetch bound
```

其中 propagation bound 硬上限 5 minutes，dependency fetch 连续 8 轮且总 wall-clock budget
硬上限 10 minutes。实现可以更快 fail closed，但不得宣传撤销窗口“等于 lease TTL”。

Event `created_at` 早于 revoke 不足以接受；后填、回拨或重放 `created_at` 不能替代 receipt。

## 5. 最小正反例

正例：medium lease 在第 7 小时签收 Event；第 9 小时 peer 首次收到 Event 与有效 receipt，
验证 basis 和签名后可继续处理。

反例：Event 声称第 1 小时创建，但直到 lease 到期后才首次出现且无 receipt，永久拒绝。

反例：open-set high-risk lease 的 issuer 与 revoke barrier authority 不相交。即使签名有效，
也没有确定撤销上界，必须拒绝该 lease。
