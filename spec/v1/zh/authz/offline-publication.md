---
title: 有界离线发布、AuthorizationLease 与 IngressReceipt
status: candidate
normative: true
stability: v1
updated: 2026-07-30
---

# 有界离线发布、AuthorizationLease 与 IngressReceipt

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Arkret v1 的普通在线 Event 不需要预先申请 AuthorizationLease：接收服务在一个 transaction 内按最新 accepted state 完成 admission 与持久化。只有调用方明确请求延迟/离线发布窗口时才使用 basis-bound lease；IngressReceipt 仍是可选 seen/availability evidence，不是 Event 有效性或最终性证明。Event `created_at` 和 verifier 本地首次见到时间均不能创造离线发布权限。

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

`basis_ref` 在普通 `single_did` / `threshold` / `mixed` 发布下是单个 accepted Seal ref；在
`open_set` 下必须是只含 canonical sorted `leaves[]` 的完整 `seal_basis`，不能用任一单 leaf 冒充 joined view。issuer 与 verifier 均须解析这些 Seal 并重算 union covered set、joined state 与 roots。lease 只能收窄该 basis 中已存在的
authorization。verifier MUST 从 accepted CBA basis
验证 issuer/delegation、actor/device、scope、action、risk 与有效期；lease 不能创建 capability，
不能把 medium/high action 降为 low，也不能跨 scope 使用。

三个已注册的 closed genesis family（ordinary Realm founding unit、self-principal PCR
bootstrap unit 与 accepted controller delegation 精确绑定的 managed Agent PCR create）
没有先验 Seal。ordinary Realm founding unit 的 wire 必需项是 bootstrap registry 的完整有序闭包。
其中 create 只投影 genesis intent、create 审计日志、founding notary、reducer profile 与 founding authority root
cell（`ak.component.realm.authority_root.v1`）五项；profile、policy 与 creator membership 都由独立签名 facet 承担
（[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)），
unit 内除 create 外只可含该节 registry 登记的 required/conditional/optional slots，且**不含**任何 founding
`ak.capability.grant`。仅对这些完整 unit，`basis_ref` MAY 是
`{anchor_unit:{realm_id,event_digests[],unit_digest}}`，其中 event digest 按 unit 必需顺序排列，
`unit_digest = sha256(canonical_json({realm_id,event_digests}))`。issuer MUST 在签发前验证完整
closed unit、root/founding authority proof、creator/session/device、notary declaration、actor
chain 与目标 Realm 不存在；提交时 unit、顺序、数量或任一 digest 不同都 MUST 零写入拒绝。
该例外不得用于普通未接受 Event，也不得把 prospective/fabricated Seal 当作 accepted basis。

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

Root-anchored device recovery 不需要另一个账号服务签 replacement authorize，也不为该动作签发 DID-derived device authority lease。RecoveryTransaction 先发布 method-native DID entry，再提交 root-signed re-anchor + replacement-device-signed authorize 原子 unit；内容 authority来自 DID root history、recovery session/policy 与 candidate device possession。Coordinator/service authentication只控制 transport、rate-limit和幂等 correlation。

若 recovery policy 需要离线 quorum，`ak.authority_set.recovery_identity_reanchor.v1` 可以为 policy proof/publication intent签发有界 lease；该 lease不得单独签 `ak.device.authorize`，也不得把账号服务变成 device authority。接受 unit 后 receipt 和 generation fence 是 durable outcome。

## 2. IngressReceipt

```text
IngressReceipt {
  receipt_id,
  event_digest,
  authorization_lease_id,
  qualified_ingress_id,
  received_at,
  ingress_basis,
  ingress_frontier,
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

`received_at`只用于签收审计与lease deadline，不决定撤销因果。首次offline ingress必须携完整causal
ingress basis：lease basis、exact Event digest、qualified ingress ID与ingress frontier。receiver按已验证的
causal order执行四分判定：

1. 已知 revoke/ban frontier `≤ ingress_basis`：拒绝authoring；
2. `ingress_basis < revoke/ban frontier`：接受历史authoring，后继Control仍按正常Lattice/Seal投影并支配
   current delivery/display/effect；不得追溯把已接受Event的author改成未授权；
3. 依赖未知或frontier closure不完整：返回`dependency_pending`并backfill，不得把缺证据当终局；
4. 依赖补齐后可证明Event与revoke/ban并发：拒绝。

current session/lifecycle/policy gate只能控制当前交付、展示与新副作用，不能覆盖第二分支的历史authoring结论。
实现不得以`created_at`、`received_at`、本地到达顺序或wall clock替代causal proof。

### 2.0 Publication authority carrier lanes（normative）

普通 Event publication 只有三条互斥 authority lane；选择结果属于已验证 request context，绝不序列化为第四套 submission sidecar：

1. **online self**：唯一 carrier 是 sender-constrained verified session grant + typed introspection holder/device binding。request context 从 `subject + audience` 构造 exact `PrincipalAuthorityKey`，并携 `SessionGrantDeviceBinding {device_id, authorization_event_id, model_generation_ref}` selector；它必须与 producer-signed Event 的 `(actor_id/executed_by, principal_server_id, proof.verification_method)` 机械交集，再从本地 accepted PCR/device evidence 重放。`EventInitialSubmission` 不增加 publication-authority member。
2. **offline/delayed ingress**：唯一 carrier 是 `AuthorizationLease`，且服务在 lease 窗口内成功签收后产生 `IngressReceipt`。online request context 不能代替 lease，lease 也不能塞入 online authority context。
3. **peer federation**：peer authority 只来自 Event envelope 内已验证的 origin `principal_server_admission` proof。若 peer 转发最初 offline ingress 的 lease/receipt，它们只证明 origin 的历史签收窗口，不替代也不扩展 origin admission proof。

managed Agent online Event 复用 controller session 的同一 online context，并额外交集 Agent 当前 delegated runtime binding 与 portable signer evidence；不得伪造 human device authority。三条 lane 不得启发式 fallback，也不得从裸 Event core、当前 DID、最新 PCR 或全局 device row猜测 authority。

### 2.1 提交与重传封装

lease、receipt 与 `CbaProofBundle` 都不是 Event 字段，也不进入 Event digest。普通在线首次提交只要求 `event`，其 authority 来自 §2.0 的 typed request context；显式延迟/离线模式才附加 lease。`EventInitialSubmission` 没有也不得新增 publication authority evidence 字段：

```text
EventInitialSubmission {
  event,
  authorization_lease?,
  cba_proof_bundles?,
  control_proposal_ack?
}
```

ingress 直接验证 Event proof、scope 与当前 CBA basis；携带 lease 时还必须验证 lease。若签发 receipt，则必须把它持久化并通过
`EventsSubmitOutcome.ingress_receipts[]` 返回。相同 Event canonical bytes 的幂等重试必须返回
原 receipt，不得用新的 `received_at` 重签，从而延长已经固定的撤销窗口。

peer federation 使用：

```text
EventFederationSubmission {
  event,
  authorization_lease?,
  ingress_receipts[], // online 必须为空；delayed/offline 必须非空
  control_proposal_ack?
}
```

普通在线 federation 必须同时省略 lease 并携带空 `ingress_receipts[]`；来源明确声明该 Event 使用
延迟/离线窗口时，必须同时携带 lease 与至少一个绑定该 lease 的 receipt。receiver 再按目标 Realm
的 issuer/threshold/transparency policy 判断离线证据是否充分。request 级 `cba_proof_bundles[]`
只负责补齐 basis closure。任何服务都不得把这些
传输证据复制进 Event，或因本地较晚首次见到而改写 `received_at`。

`control_proposal_ack` 只允许 Control Move，且必须是
[`event-auth-state-resolution.md` §7.2](./event-auth-state-resolution.md) 的 canonical
authority receipt set；DataEvent携带该字段必须拒绝。它不属于通用CBA bundle，也不能由接收
Principal Server在不持有真实authority key时补签。

### 2.2 租约签发

只有显式延迟/离线流程的客户端通过 `ak.self.authorization_leases.command.issue`
（`POST /_arkret/self/authorization-leases`）提交且只能二选一：
`AuthorizationLeaseIssueRequestBody {events: Event[1..500]}` 或
`AuthorizationLeaseIssueRequestBody {intents: AuthorizationLeaseIssueIntent[1..500]}`。Event 必须已完成最终签名；服务端
MUST 对其执行与稍后正式提交相同的 actor/session、device generation、proof、registry、Realm
policy、CBA、capability、frontier 与 closed-unit admission，但不得写 Event、推进 frontier 或
承诺稍后一定接受。

`AuthorizationLeaseIssueIntent` 只用于 capability registry 中 `target_event_kinds=[]` 的
non-Event operation，固定 `scope_ref/action/authorization_rule_id/risk_tier/basis_ref`。
issuer MUST 独立确认 action/risk、当前 accepted basis、session actor/device、scope control
Realm 和当前 authority policy；intent 本身不是授权。`events` 与 `intents` 不得同时出现。

成功响应 `AuthorizationLeaseIssueOutcome {authorization_leases[]}` MUST 与 request target
逐项同序、同数量。普通 Event 的 lease 绑定其 `seal_ref` / `seal_basis`；genesis 绑定 §1 的完整
anchor unit。lease action 必须是其 `target_event_kinds` 覆盖 Event kind 且 actor 在该 basis
实际持有的 registered capability action；未知 action 按 high risk fail closed。

issuer 是完成上述 admission 的 authenticated Principal Server admission authority，不必同时是
Realm Seal notary。`authority_set_digest` 必须冻结 issuer service DID、Realm 与精确 basis；
receiver 还 MUST 验证该 service 在 basis/policy 中是合格 ingress 或 delegated admission signer。
proof audience 必须覆盖 issuer service DID。

相同 canonical request 与相同 `Idempotency-Key` 的 retry MUST 返回逐字节相同 lease 与 expiry；
同 key 不同 request 返回 `duplicate_conflict`。续租是用新`Idempotency-Key`重新执行同一
read-only admission并取得新lease id/issued_at/expires_at；它不得修改已签Event或延长旧lease。
客户端 MAY 在到期前续取，但 MUST 以
actor/device/scope/action/basis/authority-set digest 分区保存，且在 sign-out、account switch、
device revocation、generation change或authority-set digest变化时清除。AuthorizationLease是
离线可验证事实，协议不定义一个能追溯抹除已分发签名bytes的私有revoke endpoint；撤销必须通过
accepted CBA capability/device/authority policy变化与bounded TTL生效，client cache清除不能
替代receiver的basis/revocation验证。离线状态只能使用已持有且未过期的 lease，不得
把无法联机签发降级为裸 Event。

签发、ordered batch delivery、founding anchor、exact replay/refresh、stale basis、quorum失败与
cache清除由`ak.vector.authz.authorization_lease_issuance.v1`固定，至少两个独立runner必须对
相同request产生相同typed decision与lease canonical digest。

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
