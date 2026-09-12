---
title: 有界离线发布、AuthorizationLease 与 IngressReceipt
status: candidate
normative: true
stability: v1
updated: 2026-07-30
---

# 有界离线发布、AuthorizationLease 与 IngressReceipt

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

普通 Event 使用已验证缓存授权即可离线创作、直接提交到任意合资格接收站并传播。MUST NOT 因网络断连、原站离线或长期未推进 Seal 要求 AuthorizationLease。AuthorizationLease 只用于调用者显式选择的有限期延迟执行约束，不能替代权限或绕过后来已确认的撤销关闭集合。IngressReceipt 记录签收，不授予历史有效性或安全最终性。

安全命令的 `publication_mode=online` 禁止 lease；显式 `delayed` 必须提供匹配 lease。无效的已提供 lease 必须拒绝，不能忽略后回退。Ack 表示持久处理义务，不代替安全确认。

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
`canonical_json({context:"ak.authorization_lease_proof.v1", payload_digest:lease_digest,
authority_set_ref, verification_method, created_at, domain?, audience?})`；proof `created_at` 必须逐字
等于 lease `issued_at`。proof 条数与唯一 issuer 数必须满足 basis 中已接受的 authority-set policy，
数组长度本身不等于 quorum。

`basis_ref` 绑定已确认安全状态：单 Realm 为一个 Seal；多 Realm 使用每域恰一个 head 的 canonical `leaves[]`。同域多 leaf 无效。issuer/verifier 独立验证配置、确认前缀和 authority-set policy；lease 只能收窄已有 actor/device、scope、action、risk 与有效期，不创造新的 capability。

三个已注册的 closed genesis family（ordinary Realm founding unit、self-principal PCR
bootstrap unit 与 accepted controller delegation 精确绑定的 Agent PCR create）
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

`authority_set_ref` 是 CBS 各 authority/quorum 场景共用的闭合对象
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
4. verifier MUST 使用 `basis_ref` 与 `CbsProofBundle` 重放 accepted control state，重新派生
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
与同一 安全撤销 authority set 相交并满足 `2k > n`。

### 1.1 RecoveryTransaction 的 authority ownership

PCR-policy device recovery 不需要另一个账号服务签 replacement authorize，也不为该动作签发 DID-derived device authority lease。RecoveryTransaction 直接提交 policy-authorized re-anchor + replacement-device-signed authorize 原子 unit，不发布 DID operation；内容 authority 来自 recovery session/policy、满足策略的 proof 与 candidate device possession。Coordinator/service authentication 只控制 transport、rate-limit 和幂等 correlation。

若 recovery policy 需要离线 quorum，`ak.authority_set.recovery_identity_reanchor.v1` 可以为 policy proof/publication intent签发有界 lease；该 lease不得单独签 `ak.device.authorize`，也不得把账号服务变成 device authority。接受 unit 后 receipt 和 generation fence 是 durable outcome。

## 2. IngressReceipt

```text
IngressReceipt {
  receipt_id,
  event_digest,
  qualified_ingress_did,
  received_at,
  ingress_frontier,
  proofs
}
```

`receipt_digest = sha256(canonical_json(receipt_without_proofs))`。每个 ingress proof 必须签
`canonical_json({context:"ak.ingress_receipt_proof.v1", payload_digest:receipt_digest,
authority_set_ref, verification_method, created_at, domain?, audience?})`；proof `created_at` 必须逐字
等于 `received_at`。`authority_set_ref` 不在 receipt body；它必须逐字取自同一 submission 携带的 exact companion
`AuthorizationLease.authority_set_ref`，并由 proof-context transcript 作为 body 外 binding source 固定。
`qualified_ingress_did` 是签收时 ingress service 的 version-qualified DID；每个 proof 的 verification method
必须由该 DID 控制，stable service id 在验证时由它投影，不再作为 receipt 镜像字段。`proofs[]` 必须按
verification method 严格排序、不得重复，并满足 companion lease 所绑定 authority-set policy 中选定规则的
issuer 集合与 threshold；单 proof 只在 threshold 为 1 时成立。

receipt 的签名时间必须落在 companion lease 窗口内，并绑定 exact Event digest 与完整 causal frontier。它证明 policy issuer 声称的签收事实，不证明全球先于撤销，也不能单独作为有限期消息的真实存在时间证明；稳定历史的期限内存在保证使用 [安全域确认 §5](./cbs-profiles.md) 的有界时钟 anchor。

普通消息持久资格统一按原授权和全部适用关闭集合求值。已知撤销禁止新 live 效果；未知撤销允许传播窗口；缺被引用依赖 pending；关闭集合明确排除则 quarantine。producer/receipt 时间和本站首次到达顺序均不能代替该集合判断。

### 2.0 Publication authority carrier lanes（normative）

每条共享 Event 只有一个 producer proof，并引用精确 signer evidence。普通数据的 `auth_context.authority_refs` 是可携带授权依据，安全命令的 `seal_basis` 是执行前态。请求认证与 Event authority 分开：

1. 普通单条提交可使用 `ProofAuthenticatedPublication` 的 body proof，无 SessionGrant、handoff 或原站回调。
2. 使用会话的请求执行其精确 audience/holder/scope 约束；会话不得改写 Event author，也不代替 Event 授权。
3. peer federation 认证发送服务的传输权限，接收站仍独立验 Event；来源服务不必是原账号 Station。

显式有限期 delayed lease 是附加收窄约束，不是另一套作者身份。已提供但无效的任一凭据必须拒绝，不能启发式 fallback。Agent 同样验证 runtime key、controller 委托和可携带闭包，不冒充 human device。

### 2.1 提交与重传封装

lease、receipt 与 `CbsProofBundle` 都不是 Event 字段，也不进入 Event digest。普通在线首次提交以 `event` 为主载体；MLS Genesis/Commit 还必须携带下述公开叶输入，其 authority 来自 §2.0 的 typed request context；显式延迟/离线模式才附加 lease。`EventInitialSubmission` 没有也不得新增 publication authority evidence 字段：

```text
EventInitialSubmission {
  event,
  mls_frontier_leaves?, // MLS Genesis/Commit 必填，其它 kind 禁止
  authorization_lease?,
  cbs_proof_bundles?,
  control_proposal_ack?,
  membership_compensation_evidence?
}
```

ingress 直接验证 Event proof、scope 与所引用的已确认授权闭包；携带 lease 时还必须验证 lease。若签发 receipt，则必须把它持久化并通过
`EventsSubmitOutcome.ingress_receipts[]` 返回。相同 Event canonical bytes 的幂等重试必须返回
原 receipt 与首次签发时的 exact companion lease，不得用新的 `received_at` 重签，从而延长已经固定的撤销窗口。
receipt/lease 的机械配对条件恰为：同一 submission 只有这一份 companion lease、receipt `event_digest` 等于该
submission Event canonical content digest、`project(receipt.qualified_ingress_did)` 成功且 proof method 由该 DID
控制，并且 receipt proof binding 的 body 外 `authority_set_ref` 等于 lease 同名字段。相同 Event bytes 若改携另一份 lease，MUST
`duplicate_conflict`，不得返回旧 receipt、静默重新配对或重签。

peer federation 使用：

```text
EventFederationSubmission {
  event,
  mls_frontier_leaves?, // 与初次接受的公开叶输入完全相同
  authorization_lease?,
  ingress_receipts[], // online 必须为空；delayed/offline 必须非空
  control_proposal_ack?,
  ackless_self_principal_admission_evidence?,
  membership_compensation_evidence?
}
```

`mls_frontier_leaves` 是 signed governance binding 已绑定的公开治理输入，不是 publication authority；其类型、边界、exact-basis 重算、原子持久化与 peer 独立验证遵循[服务器结果 §5.1](../sync/server-trusted-results.md#51-accepted-transition-的公开输入)。缺失或改换输入的 MLS submission MUST 拒绝。

普通在线 federation 必须同时省略 lease 并携带空 `ingress_receipts[]`；来源明确声明该 Event 使用
延迟/离线窗口时，必须同时携带 lease 与至少一个绑定该 lease 的 receipt。receiver 再按目标 Realm
的 issuer/threshold/transparency policy 判断离线证据是否充分。request 级 `cbs_proof_bundles[]`
只负责补齐 basis closure。任何服务都不得把这些
传输证据复制进 Event，或因本地较晚首次见到而改写 `received_at`。
transparency 存档、离线转发与 durable idempotency ledger 必须把 receipt 与其首次签发时的 exact companion lease
作为一个不可拆配对保存；只保存 receipt JSON 不构成可复验的 publication evidence。

`control_proposal_ack` 只允许 Control Move，且必须是
[`event-auth-state-resolution.md` §14](./event-auth-state-resolution.md) 的 canonical
authority receipt set；DataEvent携带该字段必须拒绝。它不属于通用CBS bundle，也不能由接收
Station在不持有真实authority key时补签。

### 2.2 租约签发

只有显式延迟/离线流程的客户端通过 `ak.self.authorization_leases.command.issue.v1`
（`POST /_arkret/self/authorization-leases`）提交且只能二选一：
`AuthorizationLeaseIssueRequestBody {submissions: EventInitialSubmission[1..500]}` 或
`AuthorizationLeaseIssueRequestBody {intents: AuthorizationLeaseIssueIntent[1..500]}`。每个 submission 的 Event 必须已完成最终签名，且 MUST 省略 authorization_lease（包括 null）；其余接纳输入按正式 EventInitialSubmission 的 kind presence 规则携带。MLS Genesis/Commit 的最终 mls_frontier_leaves 必须与之后发布完全相同，预检服务器在 Event 的 exact basis 重算并比对 signed security_frontier_digest；不得使用临时 query cache 补缺。服务端
MUST 对其执行与稍后正式提交相同的 actor/session、device generation、proof、registry、Realm
policy、CBS、capability、frontier 与 closed-unit admission，但不得写 Event、推进 frontier 或
承诺稍后一定接受。

`AuthorizationLeaseIssueIntent` 只用于 capability registry 中 `target_event_kinds=[]` 的
non-Event operation，固定 `scope_ref/action/authorization_rule_id/risk_tier/basis_ref`。
issuer MUST 独立确认 action/risk、当前 accepted basis、session actor/device、scope control
Realm 和当前 authority policy；intent 本身不是授权。`submissions` 与 `intents` 不得同时出现；裸 `events` 字段 MUST 拒绝，不保留平行载体。预检不得持久接纳 Event 或公开叶输入；成功只签发逐项绑定 Event 的租约，实际发布仍独立验证。

成功响应 `AuthorizationLeaseIssueOutcome {authorization_leases[]}` MUST 与 request target
逐项同序、同数量。普通 Event 的 lease 绑定其 `seal_ref` / `seal_basis`；genesis 绑定 §1 的完整
anchor unit。lease action 必须是其 `target_event_kinds` 覆盖 Event kind 且 actor 在该 basis
实际持有的 registered capability action；未知 action 按 high risk fail closed。

issuer 是完成上述 admission 的 authenticated Station admission authority，不必同时是
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
accepted CBS capability/device/authority policy变化与bounded TTL生效，client cache清除不能
替代receiver的basis/revocation验证。离线状态只能使用已持有且未过期的 lease，不得
把显式 delayed 请求中的签发失败改成另一种请求；未选择 delayed 的普通消息本来就不需要 lease。

签发、ordered batch delivery、founding anchor、exact replay/refresh、stale basis、quorum失败与
cache清除由`ak.vector.authz.authorization_lease_issuance.v1`固定，至少两个独立runner必须对
相同request产生相同typed decision与lease canonical digest。

## 3. Issuer 与证明边界

lease proof 必须满足 exact basis 派生的 `authority_set_policy` 和选定 `authorization_rule_id`，不能跨 rule 拼门限。issuer 授权门限与安全日志的 PBFT voter quorum 是不同合同，不能把“足够多服务签字”当成安全决定。

## 4. 撤销窗口

普通消息的撤销窗口等于真实证据传播延迟；永久分区中没有有限上界。接收站获知撤销后立即 gate，新旧消息的稳定历史按关闭 frontier 重算。lease TTL、查询 budget、heartbeat 或原站存储时间都不能宣称消除了这个窗口。

## 5. 最小正反例

正例：A 离线，B 使用已验证无到期 grant 和 signer evidence 接纳普通消息，不申请新 Seal 或 lease。

反例：B 已知成员撤销，仍把旧缓存当作新 live 发言许可；必须阻止。稍后导入的历史只在所有适用关闭集合包含它时参与投影。

反例：显式有限期数据只有 producer 自报早期时间和普通签收回执，却没有满足时钟见证合同的期限内 anchor；不得声称已证明期限内合法存在。
