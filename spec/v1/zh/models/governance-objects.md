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

这些对象都不直接承载协作内容，但决定了协作内容的合法范围、可见性和权限路径。完整 capability 模型、policy 求值、authority commit finality profile 等运行时语义在 `authz/`、`governance/` 和 `security/` 章节展开；本文聚焦对象级 schema、字段和生命周期。

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

`ak.schema.define` 的 payload MUST 严格匹配
[`schema_define_state_payload`](../../artifacts/schemas/event-payload.schema.json)：只允许 required
`value`，不得携带旧 `schema_id` 回声或通用 wrapper 的 `state` / `reason`。`value` MUST 是声明
`$schema="https://json-schema.org/draft/2020-12/schema"` 与 `$id` 的 JSON Schema 2020-12 文档；receiver
MUST 执行 [`payload-validator-profile-registry.json`](../../artifacts/registry/payload-validator-profile-registry.json)
的 `ak.validator.json_schema_2020_12_definition.v1`。合法但此前未登记的 `value.$id` 正是 define 的
selector 与输入，不按 unknown family 拒绝；meta-schema validation 失败、dialect 错误、缺少/非法 `$id`
或 wrapper 未知字段统一以 `schema_violation` 拒绝。

v1 schema id 是 create-once 的不可变定义，不存在 `ak.schema.update` Event。首次合法 `ak.schema.define` 占用
`value.$id`；相同 canonical Event 的重放按普通 Event 幂等规则处理，对已占用 `$id` 提交不同 bytes 必须
`schema_violation` 且零覆盖。任何演进都使用新的 versioned `$id` / `schema_id`（例如 `.v2`），并由引用方显式切换
`schema_refs`。因此 v1 不定义 predecessor 字段、并行 schema 图、原地 breaking update 或第二套 schema CAS 生命周期。

### 2.2 Schema Evolution

Schema evolution MUST be additive by default，且通过新的 versioned schema id 表达，不修改既有定义。通用 evolution 约束（新字段优先 optional、既有字段不得静默改变语义、reducer 与客户端 MUST 保留 schema 允许的未识别字段、UI 遇未知 Morph kind SHOULD 降级、标准对象不得阻止自定义 Morph kind 等）以 [morph.md §6](./morph.md) 为单一权威源，本节不重复列举，避免漂移。

完整迁移与兼容声明规则另见 [morph.md §6](./morph.md) 与 [`../conformance/conformance-profiles.md`](../conformance/conformance-profiles.md)。

### 2.3 Schema 在 Realm 中的应用

Realm 通过 `schema_refs` 字段引用启用的 schema 集合。

Schema 引用的写入路径：

- Realm create：通过 `ak.realm.create.payload.object.schema_refs` 设置初值。
- Realm update：通过 `ak.realm.schema` state event 更新引用集合。
- Morph：通过 `morph.schema_refs[]` 引用具体类型 schema（详见 [morph.md §4](./morph.md) 顺序 1）。

Realm-scoped Morph kind 收紧声明 `morph_kind_profiles` 与 `schema_refs` 同载：由 `ak.realm.schema` state event 的 closed `realm_schema_payload.value` 写入 `realm_schema` current state（机器真源为 [`event-payload.schema.json#/$defs/realm_schema_payload`](../../artifacts/schemas/event-payload.schema.json)，writable_by 见 [`../../artifacts/registry/morph-kind-decision-table.json`](../../artifacts/registry/morph-kind-decision-table.json) order=2）。声明形态为 `map<morph_kind, profile>`，每个 profile 至多包含四个收紧维度（与 decision table notes 一致，全部可选、只能收紧不得放宽 [morph.md §4](./morph.md) 顺序 1 的声明）：`allowed_facets[]`（可暴露 facet 子集）、`writable_fields[]`（可写字段子集）、`required_schema_refs[]`（必需 schema refs）、`required_capability_actions[]`（必需 capability action）。未知 profile 字段由 schema 直接拒绝；未声明某 `morph_kind` 时按空收紧处理（纯顺序 1，不得自动放宽）；放宽尝试在 Realm accept 时 MUST 以顶层 code=`morph_profile_widens_schema_ref` 拒绝（422），不得降级为通用 `schema_violation`。

## 3. Policy

### 3.1 概念

Policy 是 reducer 和服务节点判断请求是否可接受的输入。每个 Policy 对象的分类由 §3.2 `policy_kind` 字段表达；下表把 `policy_kind` enum 的每个取值与它所约束的维度对齐，概念列表与 enum 取值一一对应：

| `policy_kind` | 约束维度 |
| --- | --- |
| `access` | capability requirement、object type / facet requirement 等访问准入条件 |
| `encryption` | 已登记的加密准入约束；不提供另一套激活模式、父 Realm floor 或密钥继承 |
| `retention` | 保留与擦除 |
| `federation` | 联邦准入与传播 |
| `moderation` | 举报 / 审核 / franking 流程 |
| `discoverability` | Realm / 对象可发现性 |
| `join` | 加入规则 |
| `history_access` | 历史可见性 |
| `plaintext_visibility` | plaintext-visible service 披露范围 |
| `media` | 媒体 / Blob 准入与处理 |
| `applet` | Applet 集成约束 |
| `agent` | Agent 运行约束 |

quota（速率 / 资源上限）不作为独立 `policy_kind`，而是通过相关 policy（典型 `access` / `media`）的 `rules[]` 内 `quota` 约束表达。Policy 决策与 capability 决策的关系见 §3.3。

`policy_kind` 分类本身不登记新的 scope selector、加密激活或 retention / legal hold 控制载体。
各对象的独立配置、继承与约束，以及现行 v1 保留／hold／明文服务的既有义务和明确未定义的通用能力见
[`scope-settings.md`](../governance/scope-settings.md)。

### 3.2 Schema 与字段

Schema id: `ak.schema.policy.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:policy` |  | Policy ID。 |
| `schema` | yes | `ak.schema.policy.v1` |  | Schema ID。 |
| `realm_id` | no | `id:realm` | 组织级 policy 可省略。 | 适用 Realm。 |
| `policy_kind` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_access, plaintext_visibility, media, applet, agent)` |  | 策略类型。 |
| `rules` | yes | non-empty `array<PolicyRule>` | `minItems=1`；每条规则必须有 `rule_id`、`kind`、`effect`；规则顶层 closed，profile 扩展必须使用 `kind=extension` + `schema_ref` / `profile_ref` + `params`。纯默认策略也必须显式写一条覆盖目标 scope 的规则，不接受空数组。 | 策略规则。 |
| `default_effect` | yes | `enum(allow, deny, quarantine, require_review)` |  | 默认效果。 |
| `default_review_requirement` | conditional | `object` | 管理Policy默认require_review时必填的完整批准人、threshold与期限。 | 不生成grant。 |
| `default_operations` | conditional | non-empty `array<enum(join, publish, create_bot, map_ghost)>` | require_review 管理默认适用的 join/publish/create_bot/map_ghost 子集；同时必填审批要求。 | 未选操作默认 deny。 |
| `priority` | no | `integer` | 数值大者优先；缺省视为 `0`。同 `priority` 冲突的确定性裁决见下方说明。 | 策略优先级。 |
| `not_before` | no | `timestamp` |  | 生效时间。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `created_by` | yes | `ActorId` | 必须有 policy/admin capability。 | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` | 必须有 policy/admin capability。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

`PolicyRule` 的完整 closed schema（`rule_id` / `kind` / `effect` 必填，`kind` enum、各 kind 的条件字段、`kind=extension` 的 `schema_ref` / `profile_ref` / `params`）由 [`policy.schema.json`](../../artifacts/schemas/policy.schema.json) 的 `policy_rule` `$def` 权威定义；本节字段表不重复展开 rule 内部结构。

`ak.policy.set` 的 payload 通常只允许 required `{policy_id,value}`；唯一例外是 generic
`policy_kind=agent`，其 payload 必须为 `{policy_id,expected_revision,value}`，required nullable
`expected_revision` 的精确 CAS 与首次写证据按 [自有 Agent 授权 §3](../authz/owned-agent-authority.md)。
其它 kind/family 禁止该字段，Event 顶层仍禁止 revision。`value.schema` 直接由
[`policy_set_state_payload`](../../artifacts/schemas/event-payload.schema.json) 的 `oneOf` 选择：
`ak.schema.policy.v1` 使用 [`policy.schema.json`](../../artifacts/schemas/policy.schema.json) root，
`ak.schema.recovery_policy.v1` 使用 [`recovery-policy.schema.json`](../../artifacts/schemas/recovery-policy.schema.json)
root；v1 没有第三个 policy family，也不通过随机 `policy_id` 查询外部分派。unknown `value.schema`、body
与所选 family 不匹配或 value 未知字段均 `schema_violation`。semantic admission 还 MUST 要求外层
`policy_id` 与 generic Policy 的 `value.id`、或 RecoveryPolicy 的 `value.policy_id` 逐字相等。`state` /
`reason` 不是该 Event 的 wire 字段。

**`rules[]` 求值与同 `priority` 冲突的确定性裁决（normative）**：reducer 求值 `rules[]` 时 MUST 按 `priority` 降序（数值大者先）评估；命中规则的 `effect` 即裁决结果，未命中任何规则时取 `default_effect`。当两条或多条规则同时命中目标、`priority` 相等、但 `effect` 不一致时，MUST 按以下确定性顺序裁决，**MUST NOT** 依赖 `rules[]` 数组顺序或本地求值顺序（否则跨实现结果分歧）：

1. **deny-overrides**：命中的同 `priority` 规则中只要有一条 `effect=deny`，结果 MUST 为 `deny`；
2. 否则若有 `effect=quarantine`，结果 MUST 为 `quarantine`；
3. 否则若有 `effect=require_review`，结果 MUST 为 `require_review`；
4. 否则（全部为 `allow`）结果为 `allow`。

即同 `priority` 命中规则的 `effect` 按 `deny ≻ quarantine ≻ require_review ≻ allow` 的固定优先序合并，取最严结果。该裁决与 [`../authz/capabilities.md` §20](../authz/capabilities.md)「约束按最严格规则相交」的整体取严姿态一致。

### 3.3 Policy 与 capability 决策

Moderation policy（举报、franking、审核流程）见 [`../governance/content-moderation.md`](../governance/content-moderation.md)。Policy 决策与 capability 决策的关系：capability 决定基础动作权限，policy 可以 deny / quarantine / require review，但**不能授予权限**。

`policy_kind=agent` 的 closed `kind=agent` rule 使用 `agent_target`（all／完整 controller／完整 Agent）和 `agent_operations`（join／authorize／execute／read／deliver），字段、主体匹配、默认自助与跨层取严按 [owned-agent-authority.md](../authz/owned-agent-authority.md)。管理 gate 未设置时不要求普通成员找管理员逐次批准；禁止新增不自动停止已有 Agent，行动禁令持续覆盖指定主人的当前及未来 Agents。用户 grant、selection 或更窄 scope allow 不能覆盖有效禁令；主人直接收权仍允许。

### 3.4 Policy Action 审批配置

`ak.policy.action` 在 v1 只有一个 family，写入 current state `policy_action`。payload 必须携带 required
`value`，并在 `policy_id` / `action_id` 中恰好携带一个作为 subject；`value` 必须是 closed
`{action,approval_required,approval_quorum,policy_scope}`，其中 `action` 是完整 `ak.*` action token、
`approval_quorum >= 1`、`policy_scope` 是完整 typed resource/DID ref。v1 不按 subject id 分派 action body，
也不允许 `state` / `reason`、平铺 action 字段或未知 value 字段；违者 `schema_violation`。机器真源为
[`policy_action_state_payload`](../../artifacts/schemas/event-payload.schema.json)。

`approval_required=true` 还有一项写入时前置条件：`value.action` 必须由
[`capability-action-registry.json#approval_requirement_eligibility`](../../artifacts/registry/capability-action-registry.json)
解析为 `event_submission_carrier` 或带真实 carrier 引用的 `registered_operation_carrier`。解析为
`ineligible_no_registered_carrier` 时 reducer MUST 拒绝为 `schema_violation`
（reason=`approval_carrier_unregistered`），且不得写 `policy_action` current state。未登记 exact operation carrier
例外的 `event_mapping_kind=non_event_surface` action 禁止被本配置要求审批；`approval_required=false` 只撤回本层要求，
不需要 carrier。实现 MUST NOT 以 risk tier、action 名称或未登记的 action→operation 猜测替代 registry 判定。

**这是审批配置，不是执行回执，也不是审批授权（normative）**：该 value 只声明「某 action 需不需要审批、需要几票、
在哪个 scope 内」。一条被接受的 `ak.policy.action` Event **MUST NOT** 被读成已经满足了某次审批，也 **MUST NOT**
被读成授予了执行该 `action` 的权限——[§3.3](#33-policy-与-capability-决策) 的「policy 不能授予权限」对本节同样成立，
执行授权仍只来自 capability grant。实际的审批发生与否由该 action 自己的 Event 链承担。

**投影与 selector（normative）**：`policy_action` 是 whole-value set family——`value` 整体替换上一版本，
没有成员级 patch；当前值由同一流内的接受位置确定，[`../sync/current-state.md`](../sync/current-state.md)
的通则适用，无需额外 `expected_revision`。payload 顶层的 `policy_id` / `action_id` closed XOR 是**两个命名空间，
不是一个可合并的 subject**，因此 selector MUST 带标签地分成两支，且两支的 composite key 逐项封闭：

| 分支 | 判据 | composite key | 主体 |
| --- | --- | --- | --- |
| `policy_ref` | payload 带 `policy_id` | `(policy_id, value.action)` | 挂在某份 Policy 文档下的 action 审批配置 |
| `realm_action` | payload 不带 `policy_id` | `(action_id)` | Realm 内独立的 action 审批配置 |

`policy_ref` 支 MUST 把 `value.action` 计入 key：一份 Policy 文档可以为多个 action 各配置一次，只按 `policy_id`
归集会让改一个 action 静默覆盖同文档的其余配置。该支的 `policy_id` MUST 解析到**本 Realm 内**的一份 Policy 文档。

`realm_action` 支的 `action_id` 是**本 Realm 内的配置名**：它不是 capability token，不是全局对象 ID，也不是某份
Policy 文档内部的 rule 或 action 标识，MUST NOT 按这三者中的任何一种解读或解析。首条被接受的写入把
`(value.action, value.policy_scope)` 绑定到该 `action_id`；此后同一 `action_id` 的写入是对该配置的更新，
**MUST NOT** 把这个名字改挂到另一个 `action` 或另一个 scope 上，否则历史引用会在不改名的情况下改指。

两支都 MUST 用标签区分，**MUST NOT** 用无标签的 coalesce 把两个命名空间并成一个 key 空间，也 MUST NOT 用显示
名称或文档内局部符号（如 `PolicyRule.rule_id`）充当 subject。`value.policy_scope` MUST 解析到本 Realm 内一个
**精确的**已授权 scope：非空字符串检查不是这项校验，合法的子 scope 也 MUST NOT 被放宽成 RealmId。

### 3.5 审批配置的消费合同（normative）

[§3.4](#34-policy-action-审批配置) 只定义了这份配置怎么写进来。本节定义它怎么被读——
一份没有读者的配置对系统行为没有可观察后果，任何实现只能自己发明一套仲裁规则，
然后在跨实现处分歧。本节是 `policy_action` 在 v1 的**唯一**消费点。

本节的层次定位：`policy_action` 是叠加在 capability 判定**之上**的收紧层。
它对应 [`../authz/capabilities.md` §18](../authz/capabilities.md) 判定链路第 11 步
「若需要 approval，校验 approval 证据」里「是否需要」的第二个来源——第一个来源是 grant 上的
approval constraint。它 MUST 在跨 grant 合并
（[`../authz/constraint-schema.md` §15.4](../authz/constraint-schema.md)
的 `evaluate_constraints_across_grants`）判定为 ALLOWED **之后**求值：
配置不能把一次本来 DENIED 的操作变成可执行，这是 [§3.3](#33-policy-与-capability-决策)
「policy 不能授予权限」在本节的直接后果。

**命中条件**：设待准入操作的 capability action token 为 `A`、目标资源为 `T`、所在 Realm 为 `R`。
一条 `policy_action` 的**当前值** `C` 命中该操作，当且仅当以下全部成立：

1. `C.value.action` 与 `A` **逐字相等**。MUST NOT 用前缀、通配或
   [`../authz/capabilities.md` §5.0.1](../authz/capabilities.md) 的聚合 admin 覆盖集展开来扩大命中：
   为 `ak.realm.admin` 配置的审批只作用于 action token 恰为 `ak.realm.admin` 的操作，
   MUST NOT 自动施加到它覆盖集内的具体动作上，反向也一样。
2. `T` 落在 `C.value.policy_scope` 所指的 scope 内，按该 scope 自身的包含语义判定。
3. 分支 `policy_ref` 另需其 `policy_id` 指向的 Policy 文档在本次准入时刻对该操作**有效**：
   在 `R` 内可解析，且落在该文档的 `not_before` / `expires_at` 窗口内。挂在已过期或已不可解析的
   Policy 文档下的配置 MUST NOT 命中。分支 `realm_action` 没有这一项，它在 `R` 内直接生效。
4. 当 `C.value.approval_required=true` 时，`A` 的 approval eligibility 必须仍能在 capability action registry
   解析到登记 carrier；若 registry 与已存历史配置发生不可能的本地漂移，准入 MUST fail closed，且不得把
   该配置视为不存在。正常写入路径已在 §3.4 阻止无 carrier 配置进入历史。

只有每个 `(分支, composite key)` 的**当前值**参与求值；被替换的历史版本 MUST NOT 参与。

**多条配置同时命中的裁决**：MUST 确定，且 MUST NOT 依赖读取顺序、写入顺序或分支顺序。
设命中集合为 `H`，有效要求按下式合并：

- `effective_approval_required` = `H` 中各 `value.approval_required` 的**逻辑或**；
- `effective_approval_quorum` = `H` 中 `approval_required=true` 的那些配置的
  `value.approval_quorum` 的**最大值**（当 `effective_approval_required=false` 时无定义，也不使用）。

或与最大值都满足交换律与结合律，因此任意读取顺序得到同一结果；这与
[§3.2](#32-schema-与字段) 同 `priority` 的 deny-overrides 和
[`../authz/capabilities.md` §20](../authz/capabilities.md)「约束按最严格规则相交」是同一种取严姿态。
两支之间 **MUST NOT** 存在任何优先级：`policy_ref` 支的配置 MUST NOT 覆盖 `realm_action` 支的要求，
反向同样禁止；「后写覆盖先写」「更具体的 scope 覆盖更宽的 scope」都 MUST NOT 被用作跨配置的裁决规则。

**满足证据**：本层复用
[`../authz/constraint-schema.md` §9.2](../authz/constraint-schema.md) 的 **approval signature**，
**MUST NOT** 另造第二种审批证据类型。一份 approval signature 对本层的 quorum 计一票，
当且仅当它同时满足：

- 按 §9.2 的全部字段绑定与 replay 规则有效（`signing_bytes` 逐字节重算通过、`approved_at` 在该节规定的
  freshness 边界内、`(approver_did, nonce)` 未复用、签名由 `approver_did` 在 `approved_at` 时刻
  未被撤销的 verification method 签发）；
- `request_canonical_digest` 等于**本次**请求 body 的 JCS SHA-256 摘要，`action` 等于 `A`，
  `realm_id` 等于 `R`；
- 其 `approval_context` 是 §9.2.2 的两支之一：`context_kind="grant"` 时 `grant_id` MUST 是本次操作的
  某个**满足的依赖 grant**（§15.4 第 2 步的定义）；`context_kind="realm_governance"` 时不携带任何
  grant / policy 标识，表示本层对 `(action token, scope)` 的独立审批要求。本层 MUST 接受这两支——
  治理层的要求可以作用于不靠单份 grant 接纳的动作，实现 MUST NOT 为了满足 schema 伪造 `grant_id`；
  反向，一份 `realm_governance` 支证据 MUST NOT 被当成对某份特定 grant 的批准。
- `approver_did` **不是**本次操作的发起者。自签名 MUST NOT 计票，否则 `approval_quorum=1` 等于没有要求；
- `approver_did` 自身持有一份对 `(A, T)` 有效的 capability grant；仅登记的两项 Applet 创建动作按
  [constraint-schema §9.1](../authz/constraint-schema.md) 的 `approver_capability_action` override，
  改验对实际 scope 的显式 `ak.realm.admin` grant，不以 root/owner 身份替代。签名 action 与被批准的
  `(A, T)` 不变。`policy_action.value` 不携带
  `approval_actor_ids`，所以有资格投票的集合由这一条定义，MUST NOT 放宽成「任意 Realm 成员」——
  否则任何人都能凑齐 quorum。

**一票 = 一个互不相同的 `approver_did`**。同一 actor 的多份签名（无论 nonce 是否不同）计一票。
当计入本层的不同 `approver_did` 数量 `>= effective_approval_quorum` 时，本层的要求被满足。

因为每份签名绑定的是**本次**请求 body 的摘要，一次批准 MUST NOT 被复用到之后的任何操作，
即便 action token 与目标完全相同；实现 MUST NOT 把满足过一次的 quorum 记成对该 `(action, scope)`
的长期授权。`policy_action.value` 不携带 `timeout`，本层也 MUST NOT 自造一个：签名的时效边界
只由 §9.3 的 `approved_at` 规则给出，而跨请求的累积本就不成立——换一次请求就换一个
`request_canonical_digest`。

**未满足时的拒绝形态**：`effective_approval_required=true` 而计票不足时，该操作 MUST NOT 被接受。
准入返回既有的 RFC 9457 Problem（`type=https://arkret.org/problems/claim_required`），顶层扩展成员 `reason_code=approval_required`；
v1 **不**为本层新造错误码或 reason code。该判定属 `require_review` 类而非 `deny` 类：
补齐证据后重试是规范给出的路径，实现 MUST NOT 把它记成对该 actor 的永久拒绝，
也 MUST NOT 降级成 `quarantine`。

Problem 顶层扩展成员 MUST 携带足以让调用方行动的信息：本次的 action token 与
`effective_approval_quorum`，以及已计入的票数。它 **MUST NOT** 枚举命中了哪些配置的 subject
（`policy_id` / `action_id`），否则一个没有 Policy 读权限的调用方会从错误信封里推断出
Realm 内 Policy 对象的存在与命名。

**没有命中配置时的默认**：`H` 为空时本层**不施加任何审批要求**，MUST NOT fail closed。
本层只能收紧、不能授予（[§3.3](#33-policy-与-capability-决策)），
一个只能收紧的层，其「无配置」的语义就是它的单位元；若在此 fail closed，
则每个未被配置过的 action 都不可执行。这一条是显式默认，不是隐式约定。

与之**互补**的是求值失败：某条配置命中了，但它的 `policy_scope` 或 `policy_id` 在本次准入时刻
无法解析，则本次判定 MUST fail closed（按未满足审批拒绝），**MUST NOT** 把不可解析的配置
当成不存在而放行。「无配置」与「配置读不出来」是两件事。

**与 grant constraint 上同名字段的关系（normative）**：`policy_action.value.approval_required` 与
capability grant constraint 的 `approval_required`
（[`../authz/capabilities.md` §6](../authz/capabilities.md)、
[`../authz/constraint-schema.md` §9](../authz/constraint-schema.md)）是**两个独立开关**，
不是同一个开关的两处写法，也不存在冗余关系。两者的判定层次不同：前者挂在
`(action token, scope)` 上、由 Realm 治理面配置、对所有持 grant 的 actor 一律生效；
后者挂在**一份具体 grant** 上、随该 grant 的签发与撤销进出。

两层 MUST 按取严相交：任一层要求审批，该操作就需要审批；两层都要求时，两层的要求
MUST **各自**被满足——grant constraint 侧按 §9 的 `approval_actor_ids` / `approval_threshold`
判定，本层按上文的 quorum 判定；不取最大值，也不用一层的满足替代另一层。
一份 approval signature 若同时满足两层的资格条件，MAY 同时计入两层。

任一层的 `approval_required=false` 的含义是「**本层**不施加要求」，
**MUST NOT** 被读成「该操作不需要审批」：它 MUST NOT 取消另一层的要求。
一个 grant constraint 写 `approval_required=false` 不能绕过 Realm 的 `policy_action` 配置，
反向也一样。

## 4. Capability Grant

### 4.1 概念

Capability Grant 是显式授权委派对象。它表达"谁（subject）可以在哪些资源（resources）上执行哪些动作（actions），在什么约束（constraints）下"。

Grant 体系总览、derivation chain、revocation 传播见 [`../authz/capabilities.md`](../authz/capabilities.md) 与 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §8。

### 4.2 Schema 与字段

Schema id: `ak.schema.capability.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:grant` | `ak:grant:<44-char-suite-tagged-full-digest-token>`；不得使用 `ak:capability:`，后者只表示抽象 capability definition 引用。 | Grant ID；由承载 Event 的 `event_id` 重类型派生，create payload 不得自带。 |
| `schema` | yes | `ak.schema.capability.v1` |  | Schema ID。 |
| `realm_id` | no | `id:realm` | 全局 grant 可省略但 SHOULD 避免。 | 作用域。 |
| `issuer_id` | yes | `ActorId` | 必须持有授予权限；承载 Event 的 `actor_id` MUST 与本字段逐字段相等。账号与托管 principal 的 server 归属已封闭在 ActorId 内，不得另设 station sidecar（见 [`../authz/capabilities.md` §3.0.1](../authz/capabilities.md)）。 | 授权方。 |
| `subject` | yes | `ActorId` 或 condition selector | 可为完整 ActorId 或 condition selector；condition selector 的结构与 `required_claims` 等求值语义见 [`../authz/constraint-schema.md`](../authz/constraint-schema.md)（claim/attestation 条件）与 [`../authz/capabilities.md` §2.4 / §7](../authz/capabilities.md)（主体 + Claim 条件模型）。matching 失败 fail-closed（deny）。 | 被授权主体。 |
| `actions` | yes | `array<string>` | 例如 `ak.strand.update`、`ak.message.create`；逐字命中、不接受 wildcard，见 [`../authz/capabilities.md` §5](../authz/capabilities.md)。 | 允许动作。 |
| `resources` | yes | `array<object>` | 资源 selector array，其 kind 词表、canonical JSON 结构、匹配算法与求值时机由 [`../authz/resource-selector-grammar.md`](../authz/resource-selector-grammar.md) 与 [`resource-selector.schema.json`](../../artifacts/schemas/resource-selector.schema.json) 权威定义；多个 `resources[]` 默认 OR。匹配失败 fail-closed（不命中即不授权）。 | 资源范围。 |
| `constraints` | no | `array<object>` | 见 [`../authz/constraint-schema.md`](../authz/constraint-schema.md) §20.3 grant 示例。生效与过期窗口 MUST 通过 `constraint_kind=temporal` 的 `not_before` / `expires_at` 表达，本对象没有同名顶层字段。委托控制 MUST 通过 `constraint_kind=authority_control` 的 `max_authority_depth` 表达；缺省（无 authority_control 约束）等价于 `max_authority_depth=0`，即不可转授。 | 约束条件。 |
| `issued_at` | yes | `timestamp` | 承载 Grant 的“创建时间”语义，取代通用 `created_at`（见 [`common-fields.md` §3.2](./common-fields.md)）；retention / audit / 排序查询 MUST 用 `issued_at`、`revoked_at` 与 temporal 约束的过期时间，不回退到通用 `created_at`。 | 签发时间。 |
| `status` | yes | `enum` | `active` / `revoked` / `relinquished`。**Reducer-derived**：由封闭派生 `capability_status` 物化，producer 自填 MUST 拒绝。终态不可复活，压缩后仍 MUST 保留（见 [`../authz/capabilities.md` §12.1](../authz/capabilities.md)）。 | 授权生命周期状态。 |
| `updated_by` | no | `ActorId` | 非撤销类 grant lifecycle update 的 actor，`ak.capability.relinquish` 写入；普通 grant body 仍不可变。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 同上，取该 Event envelope 的 `created_at`。 | 最近更新时间。 |
| `revoked_by` | no | `ActorId` | `ak.capability.revoke` 写入，取该 Event envelope 的 `actor_id`。 | 撤销者。 |
| `revoked_at` | no | `timestamp` | 同上，取该 Event envelope 的 `created_at`。 | 撤销时间。 |
| `issuer_authority_refs` | yes | `array<object>` | MUST 非空。Realm root controller 签发时携带 `kind=realm_root` 的 authority-root current state / epoch / generation；再授权时携带 `kind=grant` 的 `ak:grant:` 父授权，不得指向 `ak:capability:`。 | 签发所依据的完整授权根或父授权边。 |
| `authority_depth` | no | `integer` | **Reducer-derived**，见 [`../authz/capabilities.md` §10](../authz/capabilities.md)；`realm_root` ref 深度为 0，root controller 直发为 1。 | 距授权根的绝对跳数。 |
| `authority_root_refs` | no | `array<object>` | **Reducer-derived**，同上；非单值，多亲与跨 Realm 派生可追溯到不同 root。 | 该授权可追溯到的全部授权根。 |

### 4.3 Capability 派生与 Realm 层级继承

Realm link graph 不传播 capability 或 policy。另一 Realm 的 controller／获授权 issuer 必须签发新的本地 grant；source
Realm grant、policy 或 revoke 不构成目标 Realm reducer 输入。完整边界见 [`realm-links.md` §6](./realm-links.md)。

## 5. Invite

Invite 是针对一个完整 AccountId 的定向邀请。它不携带可转发的入组秘密；用户自行分享的 Realm 邀请链接是独立对象，见 [Realm 邀请链接](../sync/realm-invite-links.md)。

### 5.1 身份与字段

`id` MUST 从唯一已接纳 `ak.invite.create` Event 的 token 派生为 InviteId，不得由调用者生成。`realm_id` 是该 Event 的 Realm；`schema` 为 `ak.schema.invite.v1`。

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `id` | yes | InviteId | 创建 Event 派生的不可变身份。 |
| `schema` | yes | schema id | 当前 v1 Invite 合同。 |
| `realm_id` | yes | RealmId | 邀请的 Realm。 |
| `inviter_account_id` | yes | AccountId | 创建者的完整账号。 |
| `invitee_account_id` | yes | AccountId | 不可变的唯一被邀请账号，含 principal_id 与 station_id。 |
| `introduction_evidence_digest` | yes | hash | 私有引介材料的摘要；raw locator token 不进入共享历史。 |
| `capability_grant_refs` | no | GrantId[] | 另行已授权的 grant 引用；邀请本身不授予管理能力。 |
| `state` | yes | enum | pending、accepted、rejected、revoked、expired。 |
| `expires_at` | yes | timestamp | 硬有效期，canonical UTC。 |
| `created_at` | yes | timestamp | 创建原件时间。 |
| `updated_by` | no | ActorId | 最近一次状态更新的 producer。 |
| `updated_at` | no | timestamp | 最近一次状态更新时间。 |

精确字段顺序、可空性和扩展边界以 `invite.schema.json` 为准。MUST NOT 嵌入 join-rule 快照、投递凭据或另一条目标绑定；准入读取当前 Realm 治理权威及创建原件的已接纳依据。

### 5.2 创建与投递

`ak.invite.create` 的 producer 必须在当前 Realm cut 上具有该操作的邀请权限。其 payload 只包含 invitee_account_id、introduction_evidence_digest、expires_at 及合法 `x_*` 扩展，不包含 invite_id。创建原件与其 RealmCommit 是邀请的权威来源。

私有投递独立按 [邀请寻址](../sync/invite-addressing.md)工作；失败、重试、路由变更或邮件投递都不是邀请生命周期状态，也不产生额外共享成员写入。个人 PrincipalLocator 只提供引介，不替代 Realm 邀请权限。

### 5.3 生命周期与原子性

唯一非终态是 pending；四个终态为 accepted、rejected、revoked、expired。允许边仅为 pending 到上述四种终态。后续任何状态变更 MUST 以 `invite_already_terminal` 拒绝；精确已接纳 Event 的重试只返回原结果，不重复写入。

- `ak.invite.accept`：仅被邀请完整账号本人接受，payload.invitee_account_id MUST 等于 envelope.actor_id 的 account 分量，并等于 stored target。接受时必须尚未过期、成员前态为 leave，ban 不可绕过。普通 Realm、当前 join-policy、主体资格及 MLS 等独立边界继续适用。Applet-managed Bot／Ghost 按现有 Applet 规则验证精确执行者及目标，不扩大账号授权。
- `ak.invite.cancel`：target_state 为 rejected 时只有被邀请人可拒绝；target_state 为 revoked 时由当前仍有相应资格的创建者或有权管理者撤销。invitee_account_id 与 previous_state 均必填。
- `ak.invite.revoke`：由当前具备该操作权限的 producer 执行，target_state 只为 revoked／expired。invitee_account_id 与 previous_state 均必填。
- `previous_state` 必须为 pending，接纳时与锁定的 lifecycle 精确比较。过期的准入拒绝不能凭空生成 expired Event；状态推进仍需要合法原签 Event 与 RealmCommit。

三个 typed-current family 在同一个 Realm 事务内工作：

1. `invite_lifecycle` 以 InviteId 为键；创建写 pending，终态事件只推进上述合法边。
2. `invite_directed_invitee` 以 InviteId 为键；只由创建 Event 写一次不可变目标。所有后续变更都必须将 signed target 与该记录逐字比较；缺失或不匹配不得释放任何 slot。
3. `invite_live_target` 以 canonical_json(完整 invitee_account_id) 为键，只保存占位的 `{create_event_id}` 或 JSON null。同一 Realm 的一个完整账号最多持有一个 pending Invite；同 principal 异 Station 是不同 slot。

创建必须在空槽上占位；占位冲突 MUST 原子拒绝为 failed_precondition、reason_code=invite_live_target_occupied，不得改写为 cas_conflict 或把第二次 create 当作精确重试。slot 的占用本身表示 live 状态，不增加第二状态轴。

接受／拒绝／撤销／到期的终态事务必须确认 slot 仍指向本邀请的创建 Event，然后显式 set null。释放后保留该 current head；它是可复用寄存器，不是 singleton-once-set，下一次合法 create 可以重新占位。旧邀请永远不能释放后继邀请的 slot。

slot 保存逐字 `ak:event:` create_event_id；InviteId 与 EventId 虽共享 token，前缀不同，wire 上不可互换。不能把 create_event_id 当 expected_revision；shared-face CAS 的 expected_revision 始终为 `{commit_id, stream_position}`。签名 payload 的 invitee_account_id 是 slot subject 的唯一可派生来源；不能在 projection 中裁剪 ActorId 或隐式改名。

接受还必须在相同事务中完成成员 leave→join；其它终态只改邀请并释放 slot，MUST NOT 合成成员 leave。Event、RealmCommit、全部登记 current 写和必要 outbox 要么一起成功，要么零写入。任何登记外成员写 MUST 以 reducer_projection_failed 原子拒绝。权限、额度或状态检查不得依赖 reducer 缓存或复制表作为权威。

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Capability 详细模型：[`../authz/capabilities.md`](../authz/capabilities.md)。
- Constraint schema：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)。
- Moderation policy：[`../governance/content-moderation.md`](../governance/content-moderation.md)。
- Realm-Realm 继承：[`realm-links.md`](./realm-links.md)。
- Schema registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Realm 邀请链接：[`../sync/realm-invite-links.md`](../sync/realm-invite-links.md)。
- Schemas：`artifacts/schemas/policy.schema.json`、`artifacts/schemas/capability-grant.schema.json`、`artifacts/schemas/invite.schema.json`。
