---
title: Governance Objects
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Arkret 协作图中的**治理对象**：

- **Schema**：标准对象 / Morph kind / facet / event 的结构与约束。
- **Policy**（`ak:policy:`）：access / encryption / retention / federation / moderation 等运行时策略。
- **Capability Grant**（`ak:grant:`）：授权委派。
- **Invite**（`ak:invite:`）：Realm 加入引导。

这些对象都不直接承载协作内容，但决定了协作内容的合法范围、可见性和权限路径。完整 capability 模型、Policy Server 决策、seal finality profile 等运行时语义在 `authz/`、`governance/` 和 `security/` 章节展开；本文聚焦对象级 schema、字段和生命周期。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Schema

### 2.1 概念

Schema 约束：

- 标准对象类型
- Morph kind 和 facets
- `fields`
- relation type
- allowed actions
- default views
- validation rules

Schema 在 wire 上以 schema id（如 `ak.schema.strand.v1`、`ak.schema.message.v1`）引用。Schema 文件本身在 [`artifacts/schemas/`](../../artifacts/schemas/) 维护，schema registry 在 [`../conformance/schema-registry.md`](../conformance/schema-registry.md) 与 `artifacts/registry/schema-registry.json`。

### 2.2 Schema Evolution

Schema evolution MUST be additive by default。通用 evolution 约束（新字段优先 optional、既有字段不得静默改变语义、reducer 与客户端 MUST 保留 schema 允许的未识别字段、UI 遇未知 Morph kind SHOULD 降级、标准对象不得阻止自定义 Morph kind 等）以 [morph.md §6](./morph.md) 为单一权威源，本节不重复列举，避免漂移。

完整迁移与兼容声明规则另见 [morph.md §6](./morph.md) 与 [`../conformance/conformance-profiles.md`](../conformance/conformance-profiles.md)。

### 2.3 Schema 在 Realm 中的应用

Realm 通过 `schema_refs` 字段引用启用的 schema 集合。

Schema 引用的写入路径：

- Realm create：通过 `ak.realm.create.payload.object.schema_refs` 设置初值。
- Realm update：通过 `ak.realm.schema` state event 更新引用集合。
- Morph：通过 `morph.schema_refs[]` 引用具体类型 schema（详见 [morph.md §4](./morph.md) 顺序 1）。

Realm-scoped Morph kind 收紧声明 `morph_kind_profiles` 与 `schema_refs` 同载：由 `ak.realm.schema` state event 写入 `ak.component.realm.schema.v1` cell（writable_by 见 [`../../artifacts/registry/morph-kind-decision-table.json`](../../artifacts/registry/morph-kind-decision-table.json) order=2）。声明形态为 `map<morph_kind, profile>`，每个 profile 至多包含四个收紧维度（与 decision table notes 一致，全部可选、只能收紧不得放宽 [morph.md §4](./morph.md) 顺序 1 的声明）：`allowed_facets[]`（可暴露 facet 子集）、`writable_fields[]`（可写字段子集）、`required_schema_refs[]`（必需 schema refs）、`required_capability_actions[]`（必需 capability action）。未声明某 `morph_kind` 时按空收紧处理（纯顺序 1，不得自动放宽）；放宽尝试在 Realm accept 时 MUST `schema_violation` reason=`morph_profile_widens_schema_ref`。

## 3. Policy

### 3.1 概念

Policy 是 reducer 和服务节点判断请求是否可接受的输入。每个 Policy 对象的分类由 §3.2 `policy_kind` 字段表达；下表把 `policy_kind` enum 的每个取值与它所约束的维度对齐，概念列表与 enum 取值一一对应：

| `policy_kind` | 约束维度 |
| --- | --- |
| `access` | capability requirement、object type / facet requirement 等访问准入条件 |
| `encryption` | encryption profile / metadata 加密下限 |
| `retention` | 保留与擦除 |
| `federation` | 联邦准入与传播 |
| `moderation` | 举报 / 审核 / franking 流程 |
| `discoverability` | Realm / 对象可发现性 |
| `join` | 加入规则 |
| `history_visibility` | 历史可见性 |
| `plaintext_visibility` | plaintext-visible service 披露范围 |
| `media` | 媒体 / Blob 准入与处理 |
| `applet` | Applet 集成约束 |
| `agent` | Agent 运行约束 |

quota（速率 / 资源上限）不作为独立 `policy_kind`，而是通过相关 policy（典型 `access` / `media`）的 `rules[]` 内 `quota` 约束表达。Policy 决策与 capability 决策的关系见 §3.3。

### 3.2 Schema 与字段

Schema id: `ak.schema.policy.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:policy` |  | Policy ID。 |
| `schema` | yes | `ak.schema.policy.v1` |  | Schema ID。 |
| `realm_id` | no | `id:realm` | 组织级 policy 可省略。 | 适用 Realm。 |
| `policy_kind` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_visibility, plaintext_visibility, media, applet, agent)` |  | 策略类型。 |
| `rules` | yes | non-empty `array<PolicyRule>` | `minItems=1`；每条规则必须有 `rule_id`、`kind`、`effect`；规则顶层 closed，profile 扩展必须使用 `kind=extension` + `schema_ref` / `profile_ref` + `params`。纯默认策略也必须显式写一条覆盖目标 scope 的规则，不接受空数组。 | 策略规则。 |
| `default_effect` | yes | `enum(allow, deny, quarantine, require_review)` |  | 默认效果。 |
| `priority` | no | `integer` | 数值大者优先；缺省视为 `0`。同 `priority` 冲突的确定性裁决见下方说明。 | 策略优先级。 |
| `not_before` | no | `timestamp` |  | 生效时间。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `created_by` | yes | `did` | 必须有 policy/admin capability。 | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` | 必须有 policy/admin capability。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

`PolicyRule` 的完整 closed schema（`rule_id` / `kind` / `effect` 必填，`kind` enum、各 kind 的条件字段、`kind=extension` 的 `schema_ref` / `profile_ref` / `params`）由 [`policy.schema.json`](../../artifacts/schemas/policy.schema.json) 的 `policy_rule` `$def` 权威定义；本节字段表不重复展开 rule 内部结构。

**`rules[]` 求值与同 `priority` 冲突的确定性裁决（normative）**：reducer / Policy Server 求值 `rules[]` 时 MUST 按 `priority` 降序（数值大者先）评估；命中规则的 `effect` 即裁决结果，未命中任何规则时取 `default_effect`。当两条或多条规则同时命中目标、`priority` 相等、但 `effect` 不一致时，MUST 按以下确定性顺序裁决，**MUST NOT** 依赖 `rules[]` 数组顺序或本地求值顺序（否则跨实现结果分歧）：

1. **deny-overrides**：命中的同 `priority` 规则中只要有一条 `effect=deny`，结果 MUST 为 `deny`；
2. 否则若有 `effect=quarantine`，结果 MUST 为 `quarantine`；
3. 否则若有 `effect=require_review`，结果 MUST 为 `require_review`；
4. 否则（全部为 `allow`）结果为 `allow`。

即同 `priority` 命中规则的 `effect` 按 `deny ≻ quarantine ≻ require_review ≻ allow` 的固定优先序合并，取最严结果。该裁决与 [`../authz/capabilities.md` §20](../authz/capabilities.md)「约束按最严格规则相交」的整体取严姿态一致。

### 3.3 Policy Server 与决策

Policy Server 风险判断与签名决策见 [`../authz/policy-server.md`](../authz/policy-server.md)；moderation policy（举报、franking、审核流程）见 [`../governance/content-moderation.md`](../governance/content-moderation.md)。Policy 决策与 capability 决策的关系：capability 决定基础动作权限，policy 可以 deny / quarantine / require review，但**不能授予权限**。

## 4. Capability Grant

### 4.1 概念

Capability Grant 是显式授权委派对象。它表达"谁（subject）可以在哪些资源（resources）上执行哪些动作（actions），在什么约束（constraints）下"。

Grant 体系总览、derivation chain、revocation 传播见 [`../authz/capabilities.md`](../authz/capabilities.md) 与 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §8。

### 4.2 Schema 与字段

Schema id: `ak.schema.capability.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:grant` | `ak:grant:<uuidv7>`；不得使用 `ak:capability:`，后者只表示抽象 capability definition 引用。 | Grant ID。 |
| `schema` | yes | `ak.schema.capability.v1` |  | Schema ID。 |
| `realm_id` | no | `id:realm` | 全局 grant 可省略但 SHOULD 避免。 | 作用域。 |
| `issuer` | yes | `did` | 必须持有授予权限。 | 授权方。 |
| `subject` | yes | `did` 或 `object` | 可为 DID 或 condition selector；condition selector 的结构与 `required_claims` 等求值语义见 [`../authz/constraint-schema.md`](../authz/constraint-schema.md)（claim/attestation 条件）与 [`../authz/capabilities.md` §2.4 / §7](../authz/capabilities.md)（DID 主体 + Claim 条件模型）。matching 失败 fail-closed（deny）。 | 被授权主体。 |
| `actions` | yes | `array<string>` | 例如 `ak.strand.update`、`ak.message.create`；逐字命中、不接受 wildcard，见 [`../authz/capabilities.md` §5](../authz/capabilities.md)。 | 允许动作。 |
| `resources` | yes | `array<object>` | 资源 selector array，其 kind 词表、canonical JSON 结构、匹配算法与求值时机由 [`../authz/resource-selector-grammar.md`](../authz/resource-selector-grammar.md) 与 [`resource-selector.schema.json`](../../artifacts/schemas/resource-selector.schema.json) 权威定义；多个 `resources[]` 默认 OR。匹配失败 fail-closed（不命中即不授权）。 | 资源范围。 |
| `constraints` | no | `array<object>` | 见 [`../authz/constraint-schema.md`](../authz/constraint-schema.md) §20.3 grant 示例。委托控制 MUST 通过 `constraint_kind=authority_control` 的 `max_authority_depth` 表达；缺省（无 authority_control 约束）等价于 `max_authority_depth=0`，即不可转授。 | 约束条件。 |
| `issuer_authority_refs` | no | `id:grant` | derived grant 必填；MUST 以 `ak:grant:` 开头，不得指向 `ak:capability:`。 | 父授权。 |
| `capability_action_registry_digest` | conditional | `sha256:<64hex>` | `actions[]` 含 aggregate admin action 时必填；proof 覆盖，按 [`capabilities.md` §3/§5.0.1](../authz/capabilities.md) 固定签发时 registry snapshot。 | 防 registry 演进造成历史 grant 权限蠕变。 |
| `issued_at` | no | `timestamp` | 承载 Grant 的"创建时间"语义，取代通用 `created_at`（见 [`common-fields.md` §3.2](./common-fields.md)）；retention / audit / 排序查询 MUST 用 `issued_at` / `expires_at` / `revoked_at`，不回退到通用 `created_at`。缺省时该 Grant 无创建时间真源，签发方 SHOULD 始终提供。 | 签发时间。 |
| `not_before` | no | `timestamp` |  | 生效时间。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `updated_by` | no | `did` | grant lifecycle update 的 actor；普通 grant body 仍不可变。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | grant lifecycle update 的时间；普通 grant body 仍不可变。 | 最近更新时间。 |
| `revoked_by` | no | `did` | 撤销后设置。 | 撤销者。 |
| `revoked_at` | no | `timestamp` |  | 撤销时间。 |
| `proofs` | yes | `array<Proof>` |  | 授权签名。 |

### 4.3 Capability 派生与 Realm 层级继承

Realm link graph 中的 derived capability grant 通过 `ak.capability.derived` event 表达，必须满足 source grant、target Realm 的 `ak.realm.inheritance_policy`、`max_depth` 等约束，并在 source grant 被 revoke 时按因果传播失效。完整规则见 [`realm-links.md` §6](./realm-links.md) 与 [`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)。

## 5. Invite

### 5.1 概念

Invite 是加入引导对象，**不等于 capability grant**。接受 invite 后，相关 capability grant 才进入有效集合。

### 5.2 Schema 与字段

Schema id: `ak.schema.invite.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:invite` |  | Invite ID。 |
| `schema` | yes | `ak.schema.invite.v1` |  | Schema ID。 |
| `realm_id` | yes | `id:realm` |  | 目标 Realm。 |
| `inviter` | yes | `did` | 必须持有 invite capability。 | 邀请者。 |
| `invitee` | no | `did` | 3PID 邀请可为空。 | 被邀请 DID。 |
| `invite_delivery_target` | conditional | object | 直接 DID 邀请中若出现 `invitee` 且不是 `third_party_id` 分支，则 MUST 出现；见 [`../sync/invite-addressing.md`](../sync/invite-addressing.md)。 | 私有 invite delivery 的公开目标服务。 |
| `introduction_evidence_digest` | conditional | hash | 直接 DID 邀请中若出现 `invitee` 且不是 `third_party_id` 分支，则 MUST 出现；不得包含 raw locator token。 | 私有 `introduction_evidence` 的审计摘要。 |
| `third_party_id` | no | `object` | 见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md)。 | 邮箱/手机号等外部标识证明。 |
| `join_rule_snapshot` | yes | `object` | 防止邀请后规则混淆。 | 邀请时 join rule。 |
| `capability_grant_refs` | no | `array<id:grant>` | 接受后才生效；每项 MUST 以 `ak:grant:` 开头，不得指向 `ak:capability:`。 | 关联授权。 |
| `expires_at` | yes | `timestamp` | 默认不超过 7 天；高安全 Realm SHOULD be no greater than 24 小时。 | 过期时间。 |
| `state` | yes | `enum(pending, accepted, rejected, revoked, expired, claimed, send_failed, revoked_by_capability_loss, revoked_by_inviter_left, invalidated_by_rate_limit)` | Invite 的流程对象状态；命名例外：Invite 的 `state` 承载流程状态轴，与通用对象的物理 lifecycle 轴不同，不表示通用对象物理 lifecycle。 | 邀请状态。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` | 最近一次 invite state update 的 actor。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

> `inviter` / `invitee` 是既定 governance 角色名词；角色名词总索引见 [`common-fields.md` §4.3](./common-fields.md#43-角色名词登记索引)。member 引用形态另用 `inviter_member_ref` / `invitee_member_ref`（见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)）。

### 5.3 行为规则

- Invite MUST 携带 `expires_at`。默认有效期 SHOULD be no greater than 7 天，高安全 Realm SHOULD be no greater than 24 小时；过期 invite 不得被 claim、accept 或用于派生新的 capability。
- 直接 DID 邀请在同一 Realm 内 MUST 以 `(realm_id, invitee)` 作为 live invite 去重键：当已有 `pending`、`claimed` 或 `send_failed` 的直接 DID invite 指向同一 `invitee` 时，后续 `ak.invite.create` 不得创建第二个 live Invite cell；reducer MUST 将其视为对既有 live invite 的幂等重投/无效重复，直到既有 invite 进入终态或过期清理。3PID invite 的去重与 claim 规则仍由 [`../sync/third-party-invites.md`](../sync/third-party-invites.md) 定义。
- 接受 invite 后，相关 capability grant 才进入有效集合。
- `ak.invite.cancel` 使用 `invite_payload` 的引用形态（`invite_id`、与持久化目标逐字节相等的 `invitee`、可选 `reason`）引用**普通定向 DID invite**。若 actor 是该 invite 的 `invitee`，它表示被邀请者拒绝，reducer MUST 将 live direct invite 从 `pending`/`claimed` 推进到 `rejected`；若 actor 是 `inviter` 或持有 `ak.invite.cancel` / Realm 管理权限的 actor，它表示取消尚未接受的普通定向 invite，reducer MUST 推进到 `revoked`。reducer 在应用任何投影前 MUST 从 Invite cell 前态确认 `invitee` 存在；目标为第三方/token invite 或前态没有 `invitee` 时 MUST 原子拒绝 `failed_precondition`（`reason_code="invite_kind_requires_revoke"`），不得仅凭请求伪造的 `invitee` 进入低风险 cancel 路径。`ak.invite.revoke` 保留给第三方/token invite、高风险撤销路径，以及**除 `accepted` / `rejected` 以外的全部终态推进**，使用同一 payload 形态引用目标 invite 并清除可认领 token material。它承载的具体终态由该 Move 的 registered FSM projection `to` 决定，取值范围是 `{revoked, expired, revoked_by_capability_loss, revoked_by_inviter_left, invalidated_by_rate_limit}`，并 MUST 携带与之对应的稳定 `reason_code`（见本节终态集合与下方 member cell 原子绑定表）。把这些终态集中到一个已注册 kind 上，是为了让每条终态转换都有**可签名、可被 Seal 覆盖**的载体：本地计时器与反滥用策略本身不是共享真相源，它们只能促使授权 writer 提交这条 Move（与 [`realm-and-space.md` §2.7](realm-and-space.md) 的"超时清理必须由 authorized writer 提交显式 `leave`"同源）。
- Invite state 转换的真源分两层：直接 DID 邀请由本节定义；3PID 邀请（邮箱、手机号等）的认领、失败和异常清理流程见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md) §6.1。直接 DID 邀请的合法转换为 `pending -> accepted`（invitee 提交 `ak.invite.accept` 且 capability / delivery target 校验通过）、`pending -> rejected`（invitee 显式拒绝）、`pending -> expired`（`expires_at` 到达）、`pending -> revoked`（inviter 或持有撤销 capability 的 actor 撤销）、`pending -> revoked_by_capability_loss`（inviter 失去 invite capability）、`pending -> revoked_by_inviter_left`（inviter 不再是可邀请成员）、`pending -> invalidated_by_rate_limit`（反滥用策略命中）。`send_failed` 仅由投递服务在无法送达私有 invite delivery target 时写入。**入边（normative）**：`send_failed` 唯一合法入边为 `pending -> send_failed`（投递服务在对一个已 `pending` 的私有 direct invite 投递失败时写入，携带 delivery 诊断 `reason_code`，如 `delivery_target_unreachable`）；reducer MUST 拒绝从 `claimed` / 任一终态 / `send_failed` 自身进入 `send_failed`（`failed_precondition`）。`ak.invite.create` MUST NOT 直接落 `send_failed`：invite 的 initial-state 恒为 `pending`（3PID 流程经 `claimed`），投递失败只能在 `pending` 之后由投递服务标注，故 reducer MUST 拒绝 create payload 携带 `state=send_failed`。**`send_failed` 不是终态**：投递失败后 invite 仍可被重投或正常清理，合法出边为 `send_failed -> pending`（投递服务重试投递成功，回到等待 claim/accept）、`send_failed -> expired`（`expires_at` 到达）、`send_failed -> revoked`、`send_failed -> revoked_by_capability_loss`、`send_failed -> revoked_by_inviter_left`、`send_failed -> invalidated_by_rate_limit`，各转换沿用 `pending` 出发的同名转换的触发条件与 `reason_code` 约定；`send_failed -> accepted` / `send_failed -> rejected` / `send_failed -> claimed` 不合法（私有 invite 尚未送达，被邀请方无从 accept/reject，且 `claimed` 仅用于 3PID 流程）。`claimed` 仅用于 3PID 流程。**`claimed` 不是终态**：3PID 邀请被认领（subject 已绑定，见 [`third-party-invites.md`](../sync/third-party-invites.md) §6.1）后，invite 沿用与 `pending` 相同的生命周期规则——合法出边为 `claimed -> accepted`（被认领 subject 提交 `ak.invite.accept`）、`claimed -> rejected`、`claimed -> expired`（`expires_at` 对 claimed invite 持续生效；认领后迟迟不 accept 的 invite 照常过期）、`claimed -> revoked`、`claimed -> revoked_by_capability_loss`、`claimed -> revoked_by_inviter_left`、`claimed -> invalidated_by_rate_limit`，各转换沿用 `pending` 出发的同名转换的触发条件与 `reason_code` 约定；`claimed -> claimed` 与 `claimed -> send_failed` 不合法（token 已原子用尽、投递阶段已结束）。每个非 `pending` 状态的写入事件 MUST 携带稳定 `reason_code`，并引用触发该转换的 event、policy frontier 或投递诊断。
- **终态集合（normative）**：`accepted`、`rejected`、`revoked`、`revoked_by_capability_loss`、`revoked_by_inviter_left`、`expired`、`invalidated_by_rate_limit` 为**终态**（无合法出边，reducer MUST 拒绝任何后续 state 转换并以 `failed_precondition` 拒绝，`reason_code="invite_already_terminal"`）。`pending`、`claimed`、`send_failed` 为**非终态**（出边见上）。该终态集合是 Invite 流程轴的权威声明；实现 MUST NOT 从某状态"恰好无出边"反推终态属性，而 MUST 依据本声明。
- **Invite 终态与 `ak.component.member.state.v1` 的原子绑定（normative）**：定向 DID 邀请的 invite 流程轴与被邀请者的 Realm member cell 是同一次治理决定的两个面，MUST 由同一 Control Move reducer transaction 原子推进，不得只关一半：

  | invite.lifecycle 转换 | 承载 wire event kind | 同 Move 内的 `ak.component.member.state.v1:<invitee>` registered projection |
  | --- | --- | --- |
  | `(initial) -> pending` | `ak.invite.create`（定向分支） | `leave -> invite` |
  | `pending`/`claimed` `-> accepted` | `ak.invite.accept` | `invite -> join` |
  | `-> rejected`（invitee 拒绝） | `ak.invite.cancel` | `invite -> leave` |
  | `-> revoked`（inviter / 管理方撤销） | 普通定向 DID invite 用 `ak.invite.cancel`；第三方/token 与其它高风险路径用 `ak.invite.revoke` | `invite -> leave`（存在已绑定 `invitee` 时） |
  | `-> expired` / `-> revoked_by_capability_loss` / `-> revoked_by_inviter_left` / `-> invalidated_by_rate_limit` | `ak.invite.revoke`（携带对应 `reason_code`） | `invite -> leave` |

  两条 cell 的写入在 canonical [`contract-registry.json`](../../artifacts/registry/contract-registry.json) 中登记为 `ak.invite.create` / `ak.invite.cancel` / `ak.invite.revoke` 的第二条**条件性** `cell_writes[]`（条件语法见 [`event-and-patch.md` §2.4.2](event-and-patch.md)）：条件是 invitee 字段存在，即定向 DID 邀请分支。

  - **定向邀请的终态 Move MUST 携带 invitee**：`ak.invite.cancel` / `ak.invite.revoke` 指向一条定向 DID invite 时，payload MUST 携带 `invitee`，其值 MUST 与目标 invite cell 记录的 `invitee` 逐字节相等；缺失或不等 MUST `failed_precondition`（`reason_code="reducer_projection_failed"`），MUST NOT 只推进 invite 流程轴而留下停在 `invite` 的 member cell。这与 [`realm-and-space.md` §2.7](realm-and-space.md) "超时清理必须由 authorized writer 提交显式 `leave`" 一致：写 `leave` 的 authorized writer 就是提交该终态 Event 的 actor，不是本地计时器。
  - **3PID 分支 MUST NOT 写 member cell**：`ak.invite.third_party` 创建的占位符邀请在 claim 前没有 `invitee`，其 `ak.invite.create` / `ak.invite.revoke` 条件不命中，reducer MUST NOT 投影 `member.state` write（尝试额外写入同样以 `reducer_projection_failed` 拒绝整个 Event）。3PID 主体的 `leave -> invite` 由 claim 之后针对 `subject_id` 签发的标准定向 `ak.invite.create` 建立，见 [`../sync/third-party-invites.md` §4.3](../sync/third-party-invites.md) step 7。

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Capability 详细模型：[`../authz/capabilities.md`](../authz/capabilities.md)。
- Constraint schema：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)。
- Policy Server 决策：[`../authz/policy-server.md`](../authz/policy-server.md)。
- Moderation policy：[`../governance/content-moderation.md`](../governance/content-moderation.md)。
- Realm-Realm 继承：[`realm-links.md`](./realm-links.md)。
- Schema registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- 3PID 邀请：[`../sync/third-party-invites.md`](../sync/third-party-invites.md)。
- Schemas：`artifacts/schemas/policy.schema.json`、`artifacts/schemas/capability-grant.schema.json`、`artifacts/schemas/invite.schema.json`。
