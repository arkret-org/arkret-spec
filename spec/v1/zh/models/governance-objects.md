---
title: Governance Objects
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Cokret 协作图中的**治理对象**：

- **Schema**：标准对象 / Morph type / facet / event 的结构与约束。
- **Policy**（`ck:policy:`）：access / encryption / retention / federation / moderation 等运行时策略。
- **Capability Grant**（`ck:grant:`）：授权委派。
- **Invite**（`ck:invite:`）：Realm 加入引导。

这些对象都不直接承载协作内容，但决定了协作内容的合法范围、可见性和权限路径。完整 capability 模型、Policy Server 决策、anchor finality profile 等运行时语义在 `authz/`、`governance/` 和 `security/` 章节展开；本文聚焦对象级 schema、字段和生命周期。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Schema

### 2.1 概念

Schema 约束：

- 标准对象类型
- Morph type 和 facets
- `fields`
- relation type
- allowed actions
- default views
- validation rules

Schema 在 wire 上以 schema id（如 `ck.schema.flow.v1`、`ck.schema.message.v1`）引用。Schema 文件本身在 [`artifacts/schemas/`](../../artifacts/schemas/) 维护，schema registry 在 [`../conformance/schema-registry.md`](../conformance/schema-registry.md) 与 `artifacts/registry/schema-registry.json`。

### 2.2 Schema Evolution

Schema evolution MUST be additive by default。通用 evolution 约束（新字段优先 optional、既有字段不得静默改变语义、reducer 与客户端 MUST 保留未知字段、UI 遇未知 Morph type SHOULD 降级、标准对象不得阻止自定义 Morph type 等）以 [morph.md §6](./morph.md) 为单一权威源，本节不重复列举，避免漂移。

完整迁移与兼容声明规则另见 [morph.md §6](./morph.md) 与 [`../conformance/conformance-profiles.md`](../conformance/conformance-profiles.md)。

### 2.3 Schema 在 Realm 中的应用

Realm 通过 `schema_refs` 字段引用启用的 schema 集合。

Schema 引用的写入路径：

- Realm create：通过 `ck.realm.create.payload.object.schema_refs` 设置初值。
- Realm update：通过 `ck.realm.schema` state event 更新引用集合。
- Morph：通过 `morph.schema_refs[]` 引用具体类型 schema（详见 [morph.md §4](./morph.md) 顺序 1）。

## 3. Policy

### 3.1 概念

Policy 是 reducer 和服务节点判断请求是否可接受的输入。每个 Policy 对象的分类由 §3.2 `policy_type` 字段表达；下表把 `policy_type` enum 的每个取值与它所约束的维度对齐，概念列表与 enum 取值一一对应：

| `policy_type` | 约束维度 |
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

quota（速率 / 资源上限）不作为独立 `policy_type`，而是通过相关 policy（典型 `access` / `media`）的 `rules[]` 内 `quota` 约束表达。Policy 决策与 capability 决策的关系见 §3.3。

### 3.2 Schema 与字段

Schema id: `ck.schema.policy.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:policy` |  | Policy ID。 |
| `schema` | yes | `ck.schema.policy.v1` |  | Schema ID。 |
| `realm_id` | no | `id:realm` | 组织级 policy 可省略。 | 适用 Realm。 |
| `policy_type` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_visibility, plaintext_visibility, media, applet, agent)` |  | 策略类型。 |
| `rules` | yes | `array<PolicyRule>` | 每条规则必须有 `rule_id`、`kind`、`effect`；规则顶层 closed，profile 扩展必须使用 `kind=extension` + `schema_ref` / `profile_ref` + `params`。 | 策略规则。 |
| `default_effect` | yes | `enum(allow, deny, quarantine, require_review)` |  | 默认效果。 |
| `priority` | no | `integer` | 数值大者优先。 | 策略优先级。 |
| `not_before` | no | `timestamp` |  | 生效时间。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `created_by` | yes | `did` | 必须有 policy/admin capability。 | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` | 必须有 policy/admin capability。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

### 3.3 Policy Server 与决策

Policy Server 风险判断与签名决策见 [`../authz/policy-server.md`](../authz/policy-server.md)；moderation policy（举报、franking、审核流程）见 [`../governance/content-moderation.md`](../governance/content-moderation.md)。Policy 决策与 capability 决策的关系：capability 决定基础动作权限，policy 可以 deny / quarantine / require review，但**不能授予权限**。

## 4. Capability Grant

### 4.1 概念

Capability Grant 是显式授权委派对象。它表达"谁（subject）可以在哪些资源（resources）上执行哪些动作（actions），在什么约束（constraints）下"。

Grant 体系总览、derivation chain、revocation 传播见 [`../authz/capabilities.md`](../authz/capabilities.md) 与 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §8。

### 4.2 Schema 与字段

Schema id: `ck.schema.capability.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:grant` | `ck:grant:<uuidv7>`；不得使用 `ck:capability:`，后者只表示抽象 capability definition 引用。 | Grant ID。 |
| `schema` | yes | `ck.schema.capability.v1` |  | Schema ID。 |
| `realm_id` | no | `id:realm` | 全局 grant 可省略但 SHOULD 避免。 | 作用域。 |
| `issuer` | yes | `did` | 必须持有授予权限。 | 授权方。 |
| `subject` | yes | `did` 或 `object` | 可为 DID 或 condition selector。 | 被授权主体。 |
| `actions` | yes | `array<string>` | 例如 `ck.flow.update`、`ck.message.create`。 | 允许动作。 |
| `resources` | yes | `array<object>` | 资源 selector。 | 资源范围。 |
| `constraints` | no | `array<object>` | 见 [`../authz/constraint-schema.md`](../authz/constraint-schema.md) §20.3 grant 示例。委托控制 MUST 通过 `constraint_type=delegation_control` 的 `max_delegation_depth` 表达；缺省（无 delegation_control 约束）等价于 `max_delegation_depth=0`，即不可转授。 | 约束条件。 |
| `parent_grant_id` | no | `id:grant` | derived grant 必填；MUST 以 `ck:grant:` 开头，不得指向 `ck:capability:`。 | 父授权。 |
| `issued_at` | no | `timestamp` | 承载 Grant 的"创建时间"语义，取代通用 `created_at`（见 [`common-fields.md` §3.2](./common-fields.md)）；retention / audit / 排序查询 MUST 用 `issued_at` / `expires_at` / `revoked_at`，不回退到通用 `created_at`。缺省时该 Grant 无创建时间真源，签发方 SHOULD 始终提供。 | 签发时间。 |
| `not_before` | no | `timestamp` |  | 生效时间。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `updated_by` | no | `did` | grant lifecycle update 的 actor；普通 grant body 仍不可变。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | grant lifecycle update 的时间；普通 grant body 仍不可变。 | 最近更新时间。 |
| `revoked_by` | no | `did` | 撤销后设置。 | 撤销者。 |
| `revoked_at` | no | `timestamp` |  | 撤销时间。 |
| `proofs` | yes | `array<Proof>` |  | 授权签名。 |

### 4.3 Capability 派生与 Realm 层级继承

Realm link graph 中的 derived capability grant 通过 `ck.capability.derived` event 表达，必须满足 source grant、target Realm 的 `ck.realm.inheritance_policy`、`max_depth` 等约束，并在 source grant 被 revoke 时按因果传播失效。完整规则见 [`realm-links.md` §6](./realm-links.md) 与 [`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)。

## 5. Invite

### 5.1 概念

Invite 是加入引导对象，**不等于 capability grant**。接受 invite 后，相关 capability grant 才进入有效集合。

### 5.2 Schema 与字段

Schema id: `ck.schema.invite.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:invite` |  | Invite ID。 |
| `schema` | yes | `ck.schema.invite.v1` |  | Schema ID。 |
| `realm_id` | yes | `id:realm` |  | 目标 Realm。 |
| `inviter` | yes | `did` | 必须持有 invite capability。 | 邀请者。 |
| `invitee` | no | `did` | 3PID 邀请可为空。 | 被邀请 DID。 |
| `invite_delivery_target` | conditional | object | 直接 DID 邀请中若出现 `invitee` 且不是 `third_party_id` 分支，则 MUST 出现；见 [`../sync/invite-addressing.md`](../sync/invite-addressing.md)。 | 私有 invite delivery 的公开目标服务。 |
| `introduction_evidence_digest` | conditional | hash | 直接 DID 邀请中若出现 `invitee` 且不是 `third_party_id` 分支，则 MUST 出现；不得包含 raw locator token。 | 私有 `introduction_evidence` 的审计摘要。 |
| `third_party_id` | no | `object` | 见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md)。 | 邮箱/手机号等外部标识证明。 |
| `join_rule_snapshot` | yes | `object` | 防止邀请后规则混淆。 | 邀请时 join rule。 |
| `capability_grant_refs` | no | `array<id:grant>` | 接受后才生效；每项 MUST 以 `ck:grant:` 开头，不得指向 `ck:capability:`。 | 关联授权。 |
| `expires_at` | yes | `timestamp` | 默认不超过 7 天；高安全 Realm SHOULD be no greater than 24 小时。 | 过期时间。 |
| `state` | yes | `enum(pending, accepted, rejected, revoked, expired, claimed, send_failed, revoked_by_capability_loss, revoked_by_inviter_left, invalidated_by_rate_limit)` | Invite 的流程对象状态；保留为 `state` 是 v1 兼容例外，不表示通用对象物理 lifecycle。 | 邀请状态。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` | 最近一次 invite state update 的 actor。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

> `inviter` / `invitee` 是既定 governance 角色名词；角色名词总索引见 [`common-fields.md` §4.3](./common-fields.md#43-角色名词登记索引)。member 引用形态另用 `inviter_member_ref` / `invitee_member_ref`（见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)）。

### 5.3 行为规则

- Invite MUST 携带 `expires_at`。默认有效期 SHOULD be no greater than 7 天，高安全 Realm SHOULD be no greater than 24 小时；过期 invite 不得被 claim、accept 或用于派生新的 capability。
- 接受 invite 后，相关 capability grant 才进入有效集合。
- Invite state 转换的真源分两层：直接 DID 邀请由本节定义；3PID 邀请（邮箱、手机号等）的认领、失败和异常清理流程见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md) §6.1。直接 DID 邀请的合法转换为 `pending -> accepted`（invitee 提交 `ck.invite.accept` 且 capability / delivery target 校验通过）、`pending -> rejected`（invitee 显式拒绝）、`pending -> expired`（`expires_at` 到达）、`pending -> revoked`（inviter 或持有撤销 capability 的 actor 撤销）、`pending -> revoked_by_capability_loss`（inviter 失去 invite capability）、`pending -> revoked_by_inviter_left`（inviter 不再是可邀请成员）、`pending -> invalidated_by_rate_limit`（反滥用策略命中）。`send_failed` 仅由投递服务在无法送达私有 invite delivery target 时写入；`claimed` 仅用于 3PID 流程。每个非 `pending` 状态的写入事件 MUST 携带稳定 `reason_code`，并引用触发该转换的 event、policy frontier 或投递诊断。

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
