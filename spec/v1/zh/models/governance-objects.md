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

Realm-scoped Morph kind 收紧声明 `morph_kind_profiles` 与 `schema_refs` 同载：由 `ak.realm.schema` state event 的 closed `realm_schema_payload.value` 写入 `realm_schema` typed current result（机器真源为 [`event-payload.schema.json#/$defs/realm_schema_payload`](../../artifacts/schemas/event-payload.schema.json)，writable_by 见 [`../../artifacts/registry/morph-kind-decision-table.json`](../../artifacts/registry/morph-kind-decision-table.json) order=2）。声明形态为 `map<morph_kind, profile>`，每个 profile 至多包含四个收紧维度（与 decision table notes 一致，全部可选、只能收紧不得放宽 [morph.md §4](./morph.md) 顺序 1 的声明）：`allowed_facets[]`（可暴露 facet 子集）、`writable_fields[]`（可写字段子集）、`required_schema_refs[]`（必需 schema refs）、`required_capability_actions[]`（必需 capability action）。未知 profile 字段由 schema 直接拒绝；未声明某 `morph_kind` 时按空收紧处理（纯顺序 1，不得自动放宽）；放宽尝试在 Realm accept 时 MUST 以顶层 code=`morph_profile_widens_schema_ref` 拒绝（422），不得降级为通用 `schema_violation`。

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
| `history_access` | 历史可见性 |
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
| `policy_kind` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_access, plaintext_visibility, media, applet, agent)` |  | 策略类型。 |
| `rules` | yes | non-empty `array<PolicyRule>` | `minItems=1`；每条规则必须有 `rule_id`、`kind`、`effect`；规则顶层 closed，profile 扩展必须使用 `kind=extension` + `schema_ref` / `profile_ref` + `params`。纯默认策略也必须显式写一条覆盖目标 scope 的规则，不接受空数组。 | 策略规则。 |
| `default_effect` | yes | `enum(allow, deny, quarantine, require_review)` |  | 默认效果。 |
| `priority` | no | `integer` | 数值大者优先；缺省视为 `0`。同 `priority` 冲突的确定性裁决见下方说明。 | 策略优先级。 |
| `not_before` | no | `timestamp` |  | 生效时间。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `created_by` | yes | `ActorId` | 必须有 policy/admin capability。 | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` | 必须有 policy/admin capability。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

`PolicyRule` 的完整 closed schema（`rule_id` / `kind` / `effect` 必填，`kind` enum、各 kind 的条件字段、`kind=extension` 的 `schema_ref` / `profile_ref` / `params`）由 [`policy.schema.json`](../../artifacts/schemas/policy.schema.json) 的 `policy_rule` `$def` 权威定义；本节字段表不重复展开 rule 内部结构。

`ak.policy.set` 的 payload 只允许 required `{policy_id,value}`。`value.schema` 直接由
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

### 3.4 Policy Action 审批配置

`ak.policy.action` 在 v1 只有一个 family，写入 typed current result `policy_action`。payload 必须携带 required
`value`，并在 `policy_id` / `action_id` 中恰好携带一个作为 subject；`value` 必须是 closed
`{action,approval_required,approval_quorum,policy_scope}`，其中 `action` 是完整 `ak.*` action token、
`approval_quorum >= 1`、`policy_scope` 是完整 typed resource/DID ref。v1 不按 subject id 分派 action body，
也不允许 `state` / `reason`、平铺 action 字段或未知 value 字段；违者 `schema_violation`。机器真源为
[`policy_action_state_payload`](../../artifacts/schemas/event-payload.schema.json)。

**这是审批配置，不是执行回执，也不是审批授权（normative）**：该 value 只声明「某 action 需不需要审批、需要几票、
在哪个 scope 内」。一条被接受的 `ak.policy.action` Event **MUST NOT** 被读成已经满足了某次审批，也 **MUST NOT**
被读成授予了执行该 `action` 的权限——[§3.3](#33-policy-与-capability-决策) 的「policy 不能授予权限」对本节同样成立，
执行授权仍只来自 capability grant。实际的审批发生与否由该 action 自己的 Event 链承担。

**投影与 selector（normative）**：`policy_action` 是 whole-value set family——`value` 整体替换上一版本，
没有成员级 patch；当前值由同一流内的接受位置确定，[`../sync/current-results.md`](../sync/current-results.md)
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
[`../authz/constraint-schema.md` §9.3](../authz/constraint-schema.md) 的 **approval signature**，
**MUST NOT** 另造第二种审批证据类型。一份 approval signature 对本层的 quorum 计一票，
当且仅当它同时满足：

- 按 §9.3 的全部字段绑定与 replay 规则有效（canonical signing input 完整、`approved_at` 在该节规定的
  freshness 边界内、`(approver_did, nonce)` 未复用、签名由 `approver_did` 在 `approved_at` 时刻
  未被撤销的 verification method 签发）；
- `request_canonical_digest` 等于**本次**请求 body 的 JCS SHA-256 摘要，`action` 等于 `A`，
  `realm_id` 等于 `R`；
- 其 `grant_id` 是本次操作的某个**满足的依赖 grant**（§15.4 第 2 步的定义）。§9.3 的字段集要求
  `grant_id` 与 `proposal_id` 恰有其一，本层不为此增设第三种取值：走 grant 路径即绑 `grant_id`，
  走提案路径即绑 `proposal_id`；
- `approver_did` **不是**本次操作的发起者。自签名 MUST NOT 计票，否则 `approval_quorum=1` 等于没有要求；
- `approver_did` 自身持有一份对 `(A, T)` 有效的 capability grant。`policy_action.value` 不携带
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
准入返回既有的 `error.code=claim_required`，`error.details.reason_code=approval_required`；
v1 **不**为本层新造错误码或 reason code。该判定属 `require_review` 类而非 `deny` 类：
补齐证据后重试是规范给出的路径，实现 MUST NOT 把它记成对该 actor 的永久拒绝，
也 MUST NOT 降级成 `quarantine`。

`error.details` MUST 携带足以让调用方行动的信息：本次的 action token 与
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
| `issuer_authority_refs` | yes | `array<object>` | MUST 非空。Realm root controller 签发时携带 `kind=realm_root` 的 authority-root typed current result / epoch / generation；再授权时携带 `kind=grant` 的 `ak:grant:` 父授权，不得指向 `ak:capability:`。 | 签发所依据的完整授权根或父授权边。 |
| `authority_depth` | no | `integer` | **Reducer-derived**，见 [`../authz/capabilities.md` §10](../authz/capabilities.md)；`realm_root` ref 深度为 0，root controller 直发为 1。 | 距授权根的绝对跳数。 |
| `authority_root_refs` | no | `array<object>` | **Reducer-derived**，同上；非单值，多亲与跨 Realm 派生可追溯到不同 root。 | 该授权可追溯到的全部授权根。 |

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
| `inviter_account_id` | yes | `AccountId` | 必须持有 invite capability。 | 邀请者。 |
| `invitee_account_id` | no | `AccountId` | 3PID 邀请可为空。 | 被邀请 exact AccountId。 |
| `introduction_evidence_digest` | conditional | hash | 直接账号邀请中若出现 `invitee_account_id` 且不是 `third_party_invite` 分支，则 MUST 出现；不得包含 raw locator token。 | 私有 `introduction_evidence` 的审计摘要。 |
| `third_party_invite` | no | `object` | 见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md)。 | 邮箱/手机号等外部标识证明。 |
| `capability_grant_refs` | no | `array<id:grant>` | 接受后才生效；每项 MUST 以 `ak:grant:` 开头，不得指向 `ak:capability:`。 | 关联授权。 |
| `state` | yes | `enum(pending, accepted, rejected, revoked, expired, claimed, send_failed, revoked_by_capability_loss, revoked_by_inviter_left, invalidated_by_rate_limit)` | Invite 的流程对象状态。按 [`common-fields.md` §5](./common-fields.md) 的所有权判据，该轴由 Arkret Event 封闭推进，故用 `state` 而非 `status`；它不是通用对象的 §5.1 lifecycle 轴，不参与 archive / restore / tombstone 模板。 | 邀请状态。 |
| `expires_at` | yes | `timestamp` | 默认不超过 7 天；高安全 Realm SHOULD be no greater than 24 小时。 | 过期时间。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` | 最近一次 invite state update 的 actor。 | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

> `inviter_account_id` / `invitee_account_id` 以既定 governance 角色名词为 stem，AccountId 字段使用 `_account_id` 表示后缀；角色名词总索引见 [`common-fields.md` §4.3](./common-fields.md#43-角色名词登记索引)。member 引用形态另用 `inviter_member_ref` / `invitee_member_ref`（见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)）。

### 5.3 行为规则

- Invite MUST 携带 `expires_at`。默认有效期 SHOULD be no greater than 7 天，高安全 Realm SHOULD be no greater than 24 小时；过期 invite 不得被 claim、accept 或用于派生新的 capability。
- **直接账号邀请的 live 去重由 slot typed current result 承载（normative）**：同一 Realm 内，每个 `invitee_account_id` 至多有一个 live 直接 invite。该唯一性的唯一真相源是 typed current result family
  `invite_live_target`——`commit-ordered projection`、`execution="security"`（未写入初始态恒为 `null`，见 [`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)），`result_selector` 是单分量 composite `[canonical_json(payload.invitee_account_id)]`。**subject 不含 `realm_id`**：typed current result 本来就由 Event envelope 的 `realm_id` 定位，把它写进 subject 段被 [`../conformance/encoding.md` §4](../conformance/encoding.md) 明禁。slot 的 value 是 `{create_event_id}` 或 `null`，**只承载占位者身份**（占用它的那条 `ak.invite.create` 的 `envelope.event_id`，逐字 `ak:event:` 形态）；invite 的流程状态唯一由 `invite_lifecycle` 承载，MUST NOT 在 slot 内复制一份会漂移的副本——理由与本节删除 `join_rule_snapshot` 时给出的完全相同。**「格子被占用」本身即等价于「存在 live 直接 invite」**，不需要第二条状态轴。
  - 直接邀请的 live 集合是 `{pending, send_failed}`。`claimed` **不属于**该集合：它只用于 3PID 流程（见本节 state 转换条），直接 DID invite 永远到不了 `claimed`。
  - `ak.invite.create` MUST 在同一个 Event 内原子写三条 typed current result：`invite_lifecycle`（`(initial) -> pending`）、`invite_directed_invitee`（create-locked 写入 `{invitee_account_id}`，是本 slot 的反向索引，见下方释放写两条）与该 slot（`set {create_event_id}`）。`invite_id` 是稳定领域身份；治理 Station 在提交位置验证该 ID 尚未存在。后续每一条 state-changing Event MUST 在 payload 里声明它读到的前态 `previous_state`（与 `agent_deactivate_payload.previous_status` 同一惯用法），reducer 在接纳事务内拿它与冻结前态比较，因此一条按 `pending` 编写的 Event 不能落在已变成 `claimed` 的 invite 上；`previous_state` 是**声明的前态**，不是生产者侧的顺序或因果依据。
  - 两条并发 create 争用同一 `commit-ordered projection` 槽位。命令按唯一安全日志顺序执行，reducer 在提交位置读该槽位的冻结前态；至多一个占槽成功，另一个得到持久拒绝结果。数据库唯一索引只是实现保护，不能替代协议状态。
  - **重复 create 的唯一结果是无效重复**：命中已占用的 slot 时，reducer MUST 以 `failed_precondition` + `reason_code="invite_live_target_occupied"` 原子拒绝。该 Event **不被接受**、不进 canonical history、不产生任何 typed current result write、投影或通知。closed `error.details` 是 [`service-operation-dtos.schema.json#/$defs/InviteLiveTargetOccupiedProblem`](../../artifacts/schemas/service-operation-dtos.schema.json)，即 `{reason_code, invite_id, create_event_id}`；提交者必须先持有 invite capability 才会走到这一步，回显占用者不构成额外披露。MUST NOT 把它旁路成 `cas_conflict`（[`../sync/service-http-binding.md` §3.1.4](../sync/service-http-binding.md) 明禁把 state-changing Event 的 precondition 失败改写为 `cas_conflict`）。**不存在「语义幂等重投」分支**：`invite_id` 是 `retype(create_event.event_id)`，第二条 Event 天然算不出第一条的 id；`idempotent_replay="same_event_identity_replay_noop"` 只覆盖同一 Event 的重投；把它当成幂等成功会让一条已进 history 的 Event 携带零 registered write，与「每个 kind MUST 派生恰好一条匹配 write」直接冲突。
  - **客户端语义（normative）**：收到 `invite_live_target_occupied` 后，客户端 MUST NOT 直接换一个新 `event_id` 重发同一条 create（那只会再撞一次同一个格子），而 MUST 先按 `details.create_event_id` 读取占用者的 lifecycle 状态再分支。占用者只可能是 `pending` 或 `send_failed`——`claimed` 只属于 3PID 流程，而 3PID invite 不占本 slot：`pending` 时对既有 invite 重投 private delivery（稳定 idempotency key 是既有的 `invite_id`，不是本次被拒 Event 的 id）；`send_failed` 时先提交 `ak.invite.revoke(target_state="revoked")` 释放格子，再 create 一条新 invite——`send_failed -> pending` 不合法，重发是一条新 invite 而不是旧 typed current result 复活。
  - **liveness 只看 typed current result，不看墙钟（normative）**：slot 被占用即 live，直到一条已登记的 Event 释放它。`expires_at` 到达**不会**自动释放格子，它只是授权 writer 提交 `ak.invite.revoke(target_state="expired")` 的理由。receiver MUST NOT 用本地时间比较合成「该 invite 已不再 live」。
  - 3PID invite 不占用该 slot（`ak.invite.third_party` 不写它）。已 `claimed` 的 3PID invite 是否阻塞对同一 AccountId 的后续直接邀请，属 [`../sync/third-party-invites.md`](../sync/third-party-invites.md) 的职责，v1 不在本 slot 内表达。3PID invite 的去重与 claim 规则仍由该文件定义。
- 接受 invite 后，相关 capability grant 才进入有效集合。
- **准入基准是 create Event 自身的治理 basis（normative）**：Invite **MUST NOT** 物化 join rule / join-policy 的
  副本。`ak.invite.create` 是这次治理决定的发生点，它的 authority-commit basis 已唯一确定创建时刻的
  `default_join_rule` 与 join-policy facet；Invite id 是 `retype(create_event.event_id)`
  （[`common-fields.md` §6.0](./common-fields.md)），因此由 Invite id 反查该 Event 并从其 basis 重放规则是
  规范定义的 canonical projection，不是实现私有扫描。reducer **MUST** 在准入 `ak.invite.create` 时按该
  basis 判定；claim / accept 阶段 **MUST NOT** 拿"当前"policy 或某份物化副本重判一次——两者都会引入邀请后
  规则混淆，而副本还会额外漂移。Invite 对象 MUST NOT 携带 join rule snapshot 或私有 locator。
- **private delivery material MUST NOT 物化到 Invite（normative）**：`invite_token`、
  `introduction_evidence`、receive-policy 状态与任何 transport material **MUST NOT** 出现在 Invite 对象上。
  Invite 上唯一合法的私有投递痕迹是 `introduction_evidence_digest`（摘要，不含 raw locator token）；
  不得保存 endpoint、resolution 或 route mirror。
- `ak.invite.cancel` 使用 `invite_cancel_payload`（`invite_id`、与持久化目标逐字节相等的 `invitee_account_id`、`target_state`、可选 `reason`）引用**普通定向 DID invite**。若 actor 是该 invite 的 `invitee_account_id`，它表示被邀请者拒绝，reducer MUST 将 live direct invite 从 `pending`/`claimed` 推进到 `rejected`；若 actor 是 `inviter_account_id` 或持有 `ak.invite.cancel` / Realm 管理权限的 actor，它表示取消尚未接受的普通定向 invite，reducer MUST 推进到 `revoked`。reducer 在应用任何投影前 MUST 从 Invite typed current result 前态确认 `invitee_account_id` 存在；目标为第三方/token invite 或前态没有 `invitee_account_id` 时 MUST 原子拒绝 `failed_precondition`（`reason_code="invite_kind_requires_revoke"`），不得仅凭请求伪造的 `invitee_account_id` 进入低风险 cancel 路径。`ak.invite.revoke` 保留给第三方/token invite、高风险撤销路径，以及**除 `accepted` / `rejected` 以外的全部终态推进**，使用独立的 `invite_revoke_payload` 引用目标 invite 并清除可认领 token material。它承载的具体终态由该 Event 的 registered FSM projection `to` 决定，取值范围就是 `invite_revoke_payload.target_state` 的 enum（`{revoked, expired, send_failed, revoked_by_capability_loss, revoked_by_inviter_left, invalidated_by_rate_limit}`；`send_failed` 是唯一的非终态取值，见下一条），并 MUST 携带与之对应的稳定 `reason_code`（该 payload 的登记成员；见本节终态集合与下方 registered write set 表）。把这些终态集中到一个已注册 kind 上，是为了让每条终态转换都有**可签名、可被 RealmCommit 覆盖**的载体：本地计时器与反滥用策略本身不是共享真相源，它们只能促使授权 writer 提交这条 Event；receiver 不得按本地墙钟合成 lifecycle 或 member write。
- Invite state 转换的真源分两层。**边集本身**由 [`contract-registry.json`](../../artifacts/registry/contract-registry.json) 的 `event_kind_registry.transition_contracts.invite_lifecycle` 单独承载：十个状态、`initial_state="pending"`、七个终态与二十一条允许边，并由 `check_fsm_state_reachability` 证明每条边都有登记的写、每个状态都可达、终态没有出边。本节 **MUST NOT** 再抄一份边集——两处各存一份必然漂移。3PID 邀请（邮箱、手机号等）的认领、失败和异常清理流程见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md) §6.1。本节只定义转换表无法承载的**触发条件与语义**：
  - 各终态边的触发条件：`-> accepted` 是 invitee 提交 `ak.invite.accept` 且 capability / delivery target 校验通过；`-> rejected` 是 invitee 显式拒绝；`-> expired` 是 `expires_at` 到达；`-> revoked` 是 inviter 或持有撤销 capability 的 actor 撤销；`-> revoked_by_capability_loss` 是 inviter 失去 invite capability；`-> revoked_by_inviter_left` 是 inviter 不再是可邀请成员；`-> invalidated_by_rate_limit` 是反滥用策略命中。从 `claimed` 或 `send_failed` 出发的同名边沿用同一触发条件与 `reason_code` 约定。
  - `send_failed` 只由投递服务在无法送达私有 invite delivery target 时写入，携带 delivery 诊断 `reason_code`（如 `delivery_target_unreachable`）。它唯一的入边是 `pending -> send_failed`，且该约束已在 wire 层封闭：`invite_revoke_payload` 的 `if/then` 在 `target_state` 取 `send_failed` 时把 `previous_state` 钉死在 `pending` 上，因此 `claimed -> send_failed` 与 `send_failed -> send_failed` 根本不可表达。`ak.invite.create` MUST NOT 直接落 `send_failed`：invite 的 initial state 恒为 `pending`（3PID 流程随后经 `claimed`），投递失败只能在 `pending` 之后由投递服务标注，故 reducer MUST 拒绝 create payload 携带 `state=send_failed`。
  - `send_failed` 不是终态，但只有清理方向的出边。`send_failed -> pending` **MUST NOT** 存在——重发是一条新 invite（新 `invite_id`、新 token、新 commitment），不是旧 typed current result 复活，见 [`../sync/third-party-invites.md` §6.1](../sync/third-party-invites.md)。`send_failed -> accepted` / `-> rejected` / `-> claimed` 同样不在边集内：私有 invite 尚未送达，被邀请方无从 accept/reject，而 `claimed` 只属于 3PID 流程。
  - `claimed` 仅用于 3PID 流程，且不是终态：被认领（subject 已绑定，见 [`third-party-invites.md`](../sync/third-party-invites.md) §6.1）后 invite 沿用与 `pending` 相同的生命周期规则，`expires_at` 对 claimed invite 持续生效，认领后迟迟不 accept 的 invite 照常过期；`claimed -> claimed` 不合法（token 已原子用尽）。
  - 每条进入非 `pending` 状态的 Event MUST 携带稳定 `reason_code`，并引用触发该转换的 event、`realm_policy` revision 或投递诊断。
- **终态由转换表承载（normative）**：`accepted`、`rejected`、`revoked`、`revoked_by_capability_loss`、`revoked_by_inviter_left`、`expired`、`invalidated_by_rate_limit` 是 `transition_contracts.invite_lifecycle.terminal_states` 的七项，`pending`、`claimed`、`send_failed` 是非终态。命中终态后，该 invite 上任何后续 state-changing Event MUST 以 `failed_precondition` + `reason_code="invite_already_terminal"` 拒绝，且 MUST NOT 派生任何投影。终态性只由 `terminal_states` 与 `allowed_transitions` 共同承载：实现 MUST NOT 从某状态"恰好无出边"反推终态属性，也 MUST NOT 以本行的复述为准——复述只为免于跳出正文，与 registry 不一致时以 registry 为准。
- **Invite lifecycle 与 Realm membership 是两个状态轴（normative）**：membership FSM 只有 `join` / `knock` / `leave` / `ban`，不存在 membership `invite` 状态。canonical registered write set 是：

  | invite_lifecycle 转换 | 承载 wire event kind | registered typed current result write |
  | --- | --- | --- |
  | `(initial) -> pending` | `ak.invite.create` / `ak.invite.third_party` | direct create 原子写 `invite_lifecycle`、`invite_directed_invitee`（`set {invitee_account_id}`）与 `invite_live_target`（占格，`set {create_event_id}`）；3PID create 只写 `invite_lifecycle` |
  | `pending -> claimed` | `ak.invite.claim` | 只写 `invite_lifecycle`；subject-bound membership proposal 不是 typed current result，3PID invite 不占 slot |
  | `pending` / `claimed -> accepted` | `ak.invite.accept` | 同一 state-changing Event 原子写 `invite_lifecycle -> accepted`、`canonical_json(envelope.actor_id)` 的 member `leave -> join`，以及（携带 `invitee_account_id` 时）`invite_live_target` 释放 |
  | `-> rejected` / direct `-> revoked` | `ak.invite.cancel` | 原子写 `invite_lifecycle` 与 `invite_live_target` 释放（该 payload 的 `invitee_account_id` 必填，故释放写无条件） |
  | `-> revoked` / `expired` / capability-loss / inviter-left / rate-limit terminal | `ak.invite.revoke` | 原子写 `invite_lifecycle`，并在携带 `invitee_account_id` 时释放 `invite_live_target` |
  | `pending -> send_failed` | `ak.invite.revoke` | 只写 `invite_lifecycle`；`send_failed` 仍在 live 集合内，MUST NOT 释放格子 |

  **slot 释放写的封闭形态（normative）**：释放写的 `result_projection` 恒为 `set null`，且**不携带任何 revision 前置条件**。`expected_revision` 在 v1 里是 shared-face typed current result 的 `{commit_id, stream_position}` CAS（见 [`../sync/current-results.md`](../sync/current-results.md)），拿 `create_event_id` 当它的值是范畴错误。「一个已被后续邀请重新占用的格子被旧 Event 释放」由两条已登记的前置条件封死，两者都不是 revision：**(a)** 释放写只挂在离开 live 状态的那条 lifecycle 边上，而这些边的落点全在 `terminal_states` 内，此后该 invite 上的任何 state-changing Event 都被 `invite_already_terminal` 拒绝，所以同一条 invite 不可能释放两次；**(b)** 一条 invite 只能释放**自己**的格子，因为同一 Event 必须满足 `invite_directed_invitee` 的 `stored_field_matches_payload` 前态要求（见下一条）。释放写是一次**有身份的真实写入**，不是把 typed current result 删回「从未写过」：它的 head 保留在状态承诺里（[`../authz/event-auth-state-resolution.md` §11](../authz/event-auth-state-resolution.md) 的 `commit-ordered projection` leaf 规则），因此「首次空格」与「释放后的空格」业务读取同为 `null`，但在协议状态里可区分。`invite_id` 与 `create_event_id` 是同一 33-octet token 的两种前缀写法（[`common-fields.md` §6.0](./common-fields.md)），但 slot value 逐字是 `ak:event:` 形态，两种写法在 wire 上永不可互换。之所以不让 slot 存 `invite_id`，是因为 registry 的 projection 词汇里**没有 retype 投影**：整值 `result_projection.value` 只能是 `field` 或 `envelope_field` 之一；`value_projection` 的成员来源封闭为 `literal` / `field` / `envelope_field` / `select` / `derivation` / `digest_of` / `normalized_string_set`，其中 `select` 只在已登记的分支之间挑一条 field path 且 `transform` 唯一取值是 `base64url_utf8`，`derivation` 是一个封闭的具名集合。七种来源没有一种能把同一个 token 从一种 typed id 前缀换成另一种，因此 `invite_id` 无法从签名 Event 直接派生。

  **释放写的可派生性与 3PID 隔离（normative）**：`invite_live_target` 的 subject 只能由 `payload.invitee_account_id` 派生——`envelope.actor_id` 是 ActorId，而 projection 语法明禁在投影内拼装、改名或裁剪字段，AccountId→ActorId 的转换不可表达。因此 `ak.invite.accept` 与 `ak.invite.revoke` 的 payload 各带一个 optional `invitee_account_id`，其释放写以 `condition:{field_present}` 登记；`ak.invite.cancel` 的该字段本来就必填，故释放写无条件。但 slot 以 account 为键，payload 省略该字段时**没有任何 subject 被求值**，因此这道检查不可能挂在 slot 上；它挂在反向索引 `invite_directed_invitee` 上——该 family 以 `invite_id` 为键，只由 direct `ak.invite.create` 写入一次（create-locked），`ak.invite.third_party` 从不写它，所以 3PID invite 的 stored invitee 是**缺失**而不是 `null`。三个释放 kind 都以 `pre_state_requirements` 把 payload 钉死在这条 stored 记录上：`ak.invite.accept` 无条件、`ak.invite.revoke` 按 5 个非 `send_failed` 的 `target_state` 逐值条件化，谓词均为 `stored_field_matches_payload`（stored 字段与 payload 字段**同时缺失，或同时存在且逐字节相等**），不匹配时 MUST `failed_precondition` + `reason_code="invite_directed_invitee_mismatch"`。revoke 侧之所以按 `target_state` 而不是按 payload 字段是否存在条件化：若按字段存在性条件化，省略该字段就会连要求一起省掉，「stored 存在、payload 缺失」这一方向反而放行；按 `target_state` 条件化则要求恒被求值，缺失只能匹配缺失。由此两个方向同时封死：3PID invite 不能靠 payload 里伪造的 `invitee_account_id` 释放别人的 direct slot（stored 缺失、payload 存在 → 拒绝），direct invite 也不能靠省略该字段把格子永久占住（stored 存在、payload 缺失 → 拒绝）。`target_state="send_failed"` 由 schema 的 `if/then` 直接禁止携带该字段，因此不派生释放写、也不触发上述前态要求。

  `ak.invite.accept` 的 `payload.invitee_account_id` **MUST** 同时等于 `envelope.actor_id` 的 account 分量：接受邀请的只能是被邀请人本人（本节 state 转换条）。该字段的用途只是让 slot subject 可从签名 Event 派生，MUST NOT 被当成「代他人接受」的入口；payload 与 actor 不一致时 MUST 以 `failed_precondition` 拒绝。

  **slot 是可复用寄存器，不是 singleton-once-set（normative）**：释放写把 value 显式 `set null`，因此下一条 `ak.invite.create` 的占格写会再次在空槽前态上成立。实现 MUST NOT 把 `null` 当作只读哨兵或「已终结」标记而拒绝写入。可复用与 singleton-once-set 的差别**只在于本 family 登记了释放写**；该区别 MUST 由登记的写集判断，不由任何哨兵值承载。

  `ak.invite.cancel` 的 `invitee_account_id` 同时是 direct-invite kind 与 exact target binding 的 admission requirement，不是 member projection 的输入。缺失 stored direct invitee 时 MUST `invite_kind_requires_revoke`；payload 不等于 stored `invitee_account_id` 时 MUST `invite_directed_invitee_mismatch`（该字段在 cancel payload 里必填，故没有缺失分支，登记的谓词是 `stored_field_equals_payload`）。`ak.invite.revoke` 不要求或写入 member state。cancel / revoke 之后 member typed current result 保持原值且不得合成一次 `leave` write。

  3PID create / revoke 同样只推进 invite lifecycle，不触碰 `invite_live_target`。claim 原子写 claimed lifecycle 与 subject-bound membership proposal，但 proposal 不是 member typed current result；后续只有 `ak.invite.accept` 才把已验证 subject 的 member 从 `leave` 推进到 `join`。任一 Event 产生登记外的 member write MUST 以 `reducer_projection_failed` 原子拒绝。

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Capability 详细模型：[`../authz/capabilities.md`](../authz/capabilities.md)。
- Constraint schema：[`../authz/constraint-schema.md`](../authz/constraint-schema.md)。
- Moderation policy：[`../governance/content-moderation.md`](../governance/content-moderation.md)。
- Realm-Realm 继承：[`realm-links.md`](./realm-links.md)。
- Schema registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- 3PID 邀请：[`../sync/third-party-invites.md`](../sync/third-party-invites.md)。
- Schemas：`artifacts/schemas/policy.schema.json`、`artifacts/schemas/capability-grant.schema.json`、`artifacts/schemas/invite.schema.json`。
