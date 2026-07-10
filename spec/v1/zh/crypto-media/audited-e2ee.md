---
title: Audited End-to-End Encryption (Profile)
status: candidate
normative: true
stability: v1
updated: 2026-07-02
sidebar:
  label: Audited E2EE
---

> **状态：可选 hardening profile**。本文档定义 Arkret v1 中面向政府 / 企业合规的 **Audit Applet Binding + sealed release session** 审计模型。v1 core 互操作 **不要求** 实现本 profile；只有 Realm 或 Circle 显式存在 active `ak.audit.applet_binding` 时才启用。基础 MLS / E2EE 架构见 [`encryption-and-audit.md`](./encryption-and-audit.md)。
>
> 本 profile 不定义常驻审计成员。审计 applet **不是** MLS 成员，**不是**实时 sync 订阅者，**不会**因为被绑定就持续收到所有聊天信息或历史密钥。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与边界

Arkret 的合规审计目标是：在不削弱默认 E2EE 的前提下，为明确声明的 Realm / Circle 提供可见、可追责、按窗口打开的历史审计流程。

本 profile 的核心约束是：

- **没有 active binding 就没有协议级审计 release**。任何 `ak.audit.release` 若无法引用 active `ak.audit.applet_binding`，receiver / reducer MUST 拒绝。
- **审计 applet 只在控制面存在**。它可以登记审计能力、发起 session、接收被批准 release 的材料；不得作为 MLS group 成员加入 Realm / Circle，也不得获得实时消息 fanout。
- **审计资格在加密时固定**。某条消息 / 某个 epoch 是否可被合规审计，取决于它被加密时已经被 MLS commit 覆盖的 active Audit Applet Binding 和当时的 release window policy；后续新增 applet、扩大窗口或改变 policy MUST NOT 让既有消息变成可审计。
- **Audit Applet Binding 不得追溯生效**。Binding accepted 之前、或 binding accepted 之后但尚未被新的 `ak.mls.commit` 覆盖之前的消息 / epoch / event，MUST 永久保持不可被该 binding 审计 release。
- **审计只面向历史窗口**。Release MUST 绑定 `sealed_epoch_range`、`target_refs` 或二者之一；不得表达“从现在开始持续可读”。
- **当前 active epoch 不得 release**。若请求覆盖当前 epoch，授权方 MUST 先通过 `ak.mls.commit` 推进 epoch，把可审计窗口封口；`ak.audit.release.sealed_by_commit_ref` MUST 引用该 commit。
- **成员透明**。绑定、session request、授权、通知、release manifest 和 close 都是 durable audit trail。对 Circle-scoped release，通知和可见元数据 MUST 限于该 Circle 的成员 / 管理员，不得泄露给无权知道该 Circle 存在或内容的人。
- **治理举报不走本 profile**。普通用户举报垃圾信息 / 恶意信息是 Realm / Circle 治理流程，直接路由给对应管理员 / moderator，见 [`../governance/content-moderation.md`](../governance/content-moderation.md)。举报不得要求审计 applet、历史 key release 或外部 verifier。

## 2. Profile 与保证类别

为保持 v1 profile 命名稳定，本 profile 沿用两个已登记的 profile id，但其语义仅指 **release path 的保证类别**，不再表示常驻审计成员：

| Profile | `audit_assurance_class` | 含义 |
| --- | --- | --- |
| `ak.profile.attested_audit.e2ee.v1` | `attested_hardware` | Release service / applet output MUST 由 TEE / HSM / 等价硬件约束：未见 accepted `ak.audit.release` 与有效 RYW receipt 时，不得输出 wrapped key material 或明文 evidence。Remote attestation evidence 使用 [`attestation-evidence.schema.json`](../../artifacts/schemas/attestation-evidence.schema.json)。 |
| `ak.profile.disclosed_audit.e2ee.v1` | `disclosed_policy` | 不要求硬件强制。部署公开声明审计 applet、审批和通知流程，但协议不能阻止恶意持有者私下复制其已经可见的明文。 |

两者不是强弱不同的同一保证，而是不同 family。实现和 UI MUST 明确区分：`attested_hardware` 是受控输出保证；`disclosed_policy` 是流程性披露，不是密码学阻断。

## 3. Audit Applet Binding

`ak.audit.applet_binding` 是审计 applet 在某个 Realm / Circle 中具有协议级审计资格的唯一入口。Binding 是 durable reducer-input Event，payload 至少包含：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `binding_id` | yes | `ak:audit_binding:<uuid>`，binding 的稳定 ID。 |
| `realm_id` | yes | 父 Realm。 |
| `effective_scope` | yes | `{kind:"realm", realm_id}` 或 `{kind:"circle", realm_id, circle_id}`。Realm-scope binding 只覆盖 Realm-default history；Circle history MUST 有 Circle-scoped binding。 |
| `applet_id` / `service_did` | yes | 审计 applet 与承载服务身份。 |
| `status` | yes | `active` / `suspended` / `revoked`。只有 `active` 可授权新 session。 |
| `purpose_classes` | yes | 允许的审计目的，例如 `legal_compliance`、`regulatory_audit`、`incident_investigation`。 |
| `allowed_release_modes` | yes | 允许的 release mode；默认 SHOULD 仅含 `targeted_evidence_release`。 |
| `audit_assurance_class` | yes | `attested_hardware` 或 `disclosed_policy`。 |
| `notice_policy` | yes | session notice 的 audience、delay、是否要求成员通知或公告。 |
| `activation_frontier_digest` | yes | Binding 公告 / policy revision 被 accepted Seal 覆盖时的控制面 coverage digest。该 coverage point 是审计资格的下界。 |
| `first_auditable_epoch` | yes | 第一个可以被该 binding 审计的 MLS epoch；MUST 是覆盖 `activation_frontier_digest` 的 `ak.mls.commit` 之后的 epoch。 |
| `release_window_policy` | yes | 最大审计窗口和 release 限制。`retroactive_release` MUST 固定为 `forbidden`；可选 `max_lookback_ms` / `max_epoch_span` 只能收窄未来 release。 |
| `policy_version_digest` | yes | Realm-bound policy hash，覆盖 binding、scope、purpose、notice、approver 与 release-mode policy。 |
| `not_before` / `expires_at` | no | Binding 有效窗口。 |

### 3.1 Activation Frontier 与不可追溯性

Binding 生效必须经过两个步骤：

1. `ak.audit.applet_binding` 进入对应 Realm / Circle 的 durable history，并对该 scope 的当前成员可见；
2. 一个新的 `ak.mls.commit` 覆盖包含该 binding 的 governance / policy frontier，推进到 `first_auditable_epoch`。

在这两个条件同时满足之前，客户端 MUST 把 E2EE application message 发送视为 `epoch_update_required` / `encryption_transition_pending`。`first_auditable_epoch` 之前的消息、epoch 和 event，即使随后变成历史窗口，也 MUST NOT 被 `ak.audit.session.request`、`ak.audit.session.authorize` 或 `ak.audit.release` 覆盖。Reducer 发现 request / authorize / release 试图覆盖该边界之前的材料时，MUST 以 `audit_release_retroactive_scope_forbidden` 拒绝。

Binding 或 policy 的后续变更遵守同一规则：

- 管理员 MAY 收窄 release window、暂停 / revoke binding、删除 release mode 或降低最大回看范围；收窄可以从新的 accepted policy frontier 起生效。
- 管理员 MAY 扩大未来窗口（例如从 30 天改为 90 天），但扩大只适用于被该变更后的 `ak.mls.commit` 覆盖并在之后加密的消息；已经加密的消息继续使用其加密时的 eligibility snapshot。
- 任何改变 `effective_scope`、`release_window_policy`、`allowed_release_modes`、`notice_policy`、`purpose_classes` 或 `audit_assurance_class` 的事件 MUST 对受影响 scope 的成员可见，并 MUST 触发新的 MLS epoch 覆盖；在覆盖前不得发送新的 application messages。

因此，成员在某一天看到 Realm / Circle 没有 active Audit Applet Binding 时，该状态下发送的 E2EE 消息获得永久的协议级承诺：未来新增审计 applet 不得追溯审计这些消息。需要处理 binding 之前材料的政府 / 企业流程必须走协议外的 legal hold / export / enterprise archive 机制，不能用本 profile 的 `ak.audit.release` 表达。

### 3.2 成员可见提示

客户端在加入或打开存在 active binding 的 Realm / Circle 前 MUST 显示对应 scope 的提示。文案可本地化，但必须保留以下语义：

- `attested_hardware`：该 Realm / Circle 绑定了审计 applet；审计只能在公告 / 留痕的 session 中访问 `first_auditable_epoch` 之后、已封口的历史窗口；受控硬件会阻止未留痕 release；新的消息不会自动对审计方可见。
- `disclosed_policy`：该 Realm / Circle 绑定了流程性审计 applet；审计应通过公告 / 留痕 session 访问 `first_auditable_epoch` 之后、已封口的历史窗口；但协议层不能阻止已持有明文的成员或服务绕过流程私下复制。

客户端 MUST NOT 把“存在 audit binding”展示成“审计方正在实时旁听”。绑定只表示后续可能发起审计 session。

## 4. Release Session 生命周期

审计 applet 获取历史材料必须走阶段性 session。标准事件链为：

1. `ak.audit.session.request`
2. `ak.audit.session.authorize`
3. `ak.audit.session.notice`
4. `ak.audit.release`
5. `ak.audit.session.close`

### 4.1 Request

`ak.audit.session.request` 由审计 applet 或受授权合规服务发起，MUST 引用 active `binding_id`，并声明：

- `session_id`
- `realm_id`
- `effective_scope`
- `requested_by`
- `purpose_class` / `legal_basis_ref`
- `requested_epoch_range` 或 `target_refs`
- `requested_release_mode`
- `occurred_at`
- `request_digest`

Receiver MUST 校验 request 的 scope、purpose 和 release mode 均被 binding 允许，并且请求范围不早于 binding 的 `first_auditable_epoch` / `activation_frontier_digest`。Target-based request MUST 能证明每个 `target_ref` 在加密时的 eligibility snapshot 允许该 binding 和 release mode；不能证明时按不可审计处理。

### 4.2 Authorize

`ak.audit.session.authorize` 由 Realm / Circle policy 指定的 approver 签发。Approver MUST 独立持有对应 scope 的高风险 audit authorization capability；Realm admin 权限不得自动覆盖 Circle-scoped audit session，除非该 grant 显式包含目标 Circle。

Authorize payload MUST 引用 `session_id`、`binding_id`、`approver_actor_id`、批准的 epoch / target 范围、release mode、notice policy、expiry、`approved_recipient_audit_actor_id` 与 `approved_recipient_public_key_ref`。`approved_recipient_public_key_ref` MUST 解析为 `approved_recipient_audit_actor_id` 当前 DID 文档或该 actor 已 accepted device/key registry 中授权用于 audit release 的 verification method；若该 key 由专用 audit key registry / hardware attestation key 承载，authorize payload MUST 同时绑定对应 registry / attestation evidence digest。批准范围不得超过 request、binding、release window policy 与每个目标加密时 eligibility snapshot 的交集。

Authorization 只授予一个有界 release 窗口，不是一次性永久凭证。`ak.audit.release` 被 accepted 时，reducer MUST 重新校验对应 `ak.audit.applet_binding.status == "active"`，authorize payload 的 `expiry` 尚未到期，且 release 的 `recipient_audit_actor_id` / `recipient_public_key_ref` 与 authorize payload 中批准的 `approved_recipient_audit_actor_id` / `approved_recipient_public_key_ref` 逐字节一致；任一条件不满足，release MUST 被拒绝（binding 非 active 使用 `audit_release_binding_inactive`，authorize 过期使用 `auth_expired` 或更具体的 release expiry reason；recipient/key mismatch 使用 `audit_release_manifest_invalid`）。Attested release service 在输出 wrapped material 或明文 evidence 前 MUST 执行同一 guard，并且不得仅凭先前见过的 authorize 事件继续 release。

### 4.3 Notice

`ak.audit.session.notice` 是 release 前的成员通知 / 公告留痕。Notice MUST 进入对应 scope 的 durable history，并至少公开：

- 审计 applet / service DID；
- 审计目的类别；
- 被批准的历史窗口或 target 摘要；
- binding activation frontier、`first_auditable_epoch` 和 release window policy 摘要；
- release mode；
- approver；
- 预计 release 时间或立即 release 的政策依据。

对 Circle-scoped session，notice MUST 发送给该 Circle 的当前成员和 Circle 管理员；父 Realm 普通成员不得因此获得 Circle 私有元数据。

### 4.4 Release

`ak.audit.release` 是唯一允许输出审计材料的 release manifest。Payload MUST 包含：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `release_id` | yes | `ak:audit_release:<uuid>`。 |
| `session_id` | yes | 对应 session。 |
| `binding_id` | yes | 对应 active binding。 |
| `realm_id` / `effective_scope` | yes | release scope。 |
| `applet_id` / `service_did` | yes | 接收 release 的审计 applet / service。 |
| `release_mode` | yes | `targeted_evidence_release` 或 `sealed_epoch_key_release`。 |
| `sealed_epoch_range` | conditional | release 覆盖 epoch 时必填；不得包含当前 active epoch。 |
| `target_refs` | conditional | target-based release 时必填。 |
| `seal_ref` / `seal_digest` | yes | release 所依赖的 accepted history seal。 |
| `recipient_audit_actor_id` | yes | 接收材料的审计主体。 |
| `recipient_public_key_ref` | yes | release material 加密目标 key；MUST 等于 authorize payload 的 `approved_recipient_public_key_ref`，并解析为 `recipient_audit_actor_id` 授权的 audit release 接收 key。 |
| `approver_actor_id` | yes | 授权者。 |
| `notice_ref` | yes | 对应 `ak.audit.session.notice`。 |
| `purpose_class` / `legal_basis_ref` | yes | 目的与依据。 |
| `policy_version_digest` | yes | 与 binding / authorize frontier 一致的 policy hash。 |
| `eligibility_proof` | yes | 证明 release 范围未早于 binding activation frontier，且每个 target / epoch 在加密时允许该 release mode。 |
| `sealed_by_commit_ref` | conditional | 若 release 涉及 MLS epoch，MUST 引用把 active epoch 推进后的 `ak.mls.commit`。 |
| `wrapped_material_digest[]` | yes | 已输出材料的 digest 列表；不内联明文。 |

Release event MUST 先 accepted，并取得有效 `ak.audit.ryw_receipt` 后，attested release service 才能输出 wrapped material。输出前，release service MUST 重新解析并验证 `recipient_public_key_ref` 仍是 `recipient_audit_actor_id` 授权的 audit release 接收 key；不得把 material 加密给 release manifest 自带但未被 authorize 批准、或不属于该审计主体的 key。`disclosed_policy` 也 MUST 按同一顺序记录，但其保证是流程性。

Receiver / reducer MUST 拒绝任何缺失 `eligibility_proof`、`eligibility_proof` 与 binding policy 不一致、`sealed_epoch_range.first_epoch < first_auditable_epoch`，或 target 在其 encryption-time eligibility snapshot 中未包含该 binding / release mode 的 release。Release 被 accepted 时还 MUST 重新校验 binding 仍为 `active`、authorize 未过 expiry、authorize 批准的 recipient actor/key 与 release manifest 一致、`recipient_public_key_ref` 解析到 `recipient_audit_actor_id` 授权 key、notice 已按 scope 留痕且 session 未 close。该拒绝使用 `audit_release_retroactive_scope_forbidden`、`audit_release_manifest_invalid`、`audit_release_binding_inactive` 或 `auth_expired`，取决于错误是越过不可追溯边界、manifest 自身不一致、binding 已暂停 / revoked，还是授权窗口已过期。

### 4.5 Close

`ak.audit.session.close` 关闭 session，记录 `occurred_at`、`closer_actor_id`、`close_reason`、最终 `release_refs[]` 和任何未完成原因。Session close 后不得追加新的 `ak.audit.release`；需要更多材料必须发起新 session。

## 5. Release Mode

### 5.1 `targeted_evidence_release`（默认）

默认 release mode 是目标证据 release：只针对 `target_refs[]` 输出最小 evidence package。Evidence package SHOULD 由当前持有明文的成员设备、授权保管服务或符合 Realm policy 的受控服务加密给 `recipient_public_key_ref`。该模式不 release MLS epoch secret，也不让审计 applet 获得后续消息能力。

`targeted_evidence_release` 的 evidence package MAY 包含被请求消息的明文、附件 digest、原始 encrypted envelope、franking proof、reporter / custodian 签名和必要上下文；MUST NOT 包含无关消息、超出授权范围的历史 key，或未被 `target_refs[]` 与 `eligibility_proof` 同时覆盖的同 epoch 明文。每个明文 item MUST 对应一个通过 §4.4 eligibility proof 的 `target_ref`，并满足该 target 的 encryption-time eligibility snapshot、`first_auditable_epoch` 与 release window。成员或 custodian 能解密某个 epoch 的更多明文，不等于可以把整 epoch 明文打包进 targeted evidence；超出 target 交集的明文 MUST 被拒绝并记录为 `audit_release_manifest_invalid` 或 `audit_release_retroactive_scope_forbidden`。

### 5.2 `sealed_epoch_key_release`（高风险）

`sealed_epoch_key_release` 只适用于明确合规需求。Binding 的 `allowed_release_modes` 未列出该值时，任何此类 request / authorize / release MUST 拒绝。

该模式只能 release 已封口 epoch 的 wrapped material；不得 release 当前 active epoch，也不得为未来 epoch 建立持续访问。若授权窗口覆盖当前 epoch，必须先接受一个新的 `ak.mls.commit`，随后 `sealed_by_commit_ref` 引用该 commit。

实现和 UI MUST 把该模式标为高风险合规 release，不得把它用于普通用户举报、moderation queue 或 Circle 日常治理。

**与 `mls-exporter-aead-v1` per-epoch `history_secret` 的交叉约束（normative）**：在采用 [`encryption-and-audit.md` §2.10](./encryption-and-audit.md) `mls-exporter-aead-v1` 内容 scheme 的 Realm 上，`sealed_epoch_key_release` 释放的 sealed-epoch material 与该 epoch 的 `history_secret[N]` 是**同一把根**（`sealed_epoch_key_release` 释放的即是对该 epoch 内容解密所需的 epoch root）。两条治理门（§2.10 的历史共享门 与本 profile 的 audit binding release 门）因此 MUST 交叉约束，不得各自独立放行而互相绕过：

- `ak.realm_key.share` 经 [`encryption-and-audit.md` §2.10.4](./encryption-and-audit.md) 向接收主体交付 `history_secret` 时，其接收主体资格（key-share-source / recipient eligibility，见 [`device-lifecycle.md` §13](./device-lifecycle.md)）MUST 与 audit binding 的 release 限制**不冲突**——历史共享路径 MUST NOT 被用作绕过 audit binding `allowed_release_modes` / release window / `first_auditable_epoch` 限制、把本应经 audit session 才可释放的 epoch root 私下交付给审计相关主体的旁路。
- 反向地，audit `sealed_epoch_key_release` 释放 `history_secret`（或其等价 sealed-epoch material）时 MUST 仍满足 [`encryption-and-audit.md` §2.10.5](./encryption-and-audit.md) 的 retention 边界（该 epoch root 已按 retention policy 删除时不存在可释放 material，release MUST 失败而非要求成员重新派生）与本 profile 的 `first_auditable_epoch` 边界（§4：`sealed_epoch_range.first_epoch < first_auditable_epoch` MUST 拒绝 `audit_release_retroactive_scope_forbidden`）。即"该 epoch 的 `history_secret` 仍被保留"不等于"该 epoch 对审计可释放"——两个条件 MUST 同时成立，缺一即拒绝。

## 6. RYW Receipt 与 Attestation

`ak.audit.ryw_receipt` 是 read-your-writes receipt object / durable event，用于证明某个 `ak.audit.release` 或需要先留痕的 `ak.audit.accessed` 已进入 accepted history。Receipt schema 见 [`audit-ryw-receipt.schema.json`](../../artifacts/schemas/audit-ryw-receipt.schema.json)。

规则：

- `attested_hardware` release MUST 等待 `witness_attestation.kind="federation_witness_attested"` 的 receipt；至少两个独立 witness，且 witness 不得由 release service、audit actor 或 Realm operator 自己控制。每个 receipt MUST 携带 `realm_operator_organization`，verifier MUST 由 Realm service / operator 的 DID 控制链独立验证该值；任一 witness 的 `controlling_organization` 与其相同或同属一个最终控制组织时，receipt MUST `audit_receipt_invalidated` fail closed。
- `disclosed_policy` MAY 使用 `single_source` receipt，但 issuer 仍不得是 release service / audit actor 本身。
- Receipt 的 `audit_policy_version_digest` MUST 覆盖 `{realm_id, trust_domain, audit_binding, release_policy, release_window_policy, activation_frontier_digest, first_auditable_epoch}`，并与 `ak.audit.release.eligibility_proof` 一致；policy hash MUST 按本节定义计算，不得引入其他 hash 语义。
- Remote attestation evidence 绑定的是 release service / applet controlled output path，不是 MLS group membership。Evidence MUST 绑定 `realm_id`、`service_did`、`audit_service_actor_id`、measurement、purpose、policy digest、validity 和 operator DID。

## 7. 非保证项

本 profile 明确不保证：

- 审计 applet 能看到所有消息；
- 审计结果完整覆盖某个时间段内的全部事实；
- 已经由成员、服务或审计方复制出去的明文会被删除；
- 所有成员设备会删除历史 key；
- 移除或 revoke binding 会事后撤销过去已经 release 出去的材料；
- 审计 applet 可以实时监听后续消息。

任何 UI、采购材料、合规说明或营销文案 MUST NOT 声称上述性质。

## 8. 与 Realm/Circle 治理的关系

Realm / Circle 内部治理依赖管理员和 moderator。用户发现垃圾信息、恶意内容或违规行为时，使用 `ak.self.moderation.command.report` 将举报送达对应 scope 的管理员 / moderator。E2EE 中的举报证据由 reporter 提交加密 evidence package 和可选 `franking_proof`；moderator 不因举报获得 epoch key、历史 key 或审计 applet release 权限。

合规审计和群治理是两套流程：

- 治理举报：由成员触发，路由给 Realm / Circle 管理员，目标是 moderation decision。
- 合规审计：由绑定的 audit applet 触发，必须有 active binding、session、notice、release manifest 和 RYW receipt，目标是历史窗口 release。

实现 MUST NOT 把普通举报自动升级为 `ak.audit.session.request`，也 MUST NOT 以 moderation 权限绕过本 profile 的 binding / notice / sealed release 要求。
