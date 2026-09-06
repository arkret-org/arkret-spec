---
title: Actor & Actor Profile
status: candidate
normative: true
stability: v1
updated: 2026-07-30
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Actor 是 Arkret 协作图中"能执行动作的主体"。Actor identity 的根由 DID 定义；为了让 Actor 能在协作图中被 mention、被 assign、被展示，它 MAY 拥有对应的 `actor_profile` 标准对象。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。Actor 与 Capability、Identity 体系的交互见 [`../identity/identity-did.md`](../identity/identity-did.md) 与 [`../authz/capabilities.md`](../authz/capabilities.md)。

## 2. Actor 概览

协议中的 actor identity 根由 DID 定义。

Actor 类型（`actor_kind`）：

- `user`
- `organization`
- `team`
- `agent`
- `bot`
- `service`
- `integration`

`actor_kind` 不包含 `device`：设备不是 actor 主体，没有自己的 DID。设备永远从属于某个 user/organization principal，通过 `ak.device.authorize` 由该 principal 授权登记；设备的稳定标识是 `device_id`（`ak:device:<uuid>` typed ID），设备密钥是该 principal DID 下的 verification method。详见 [`../crypto-media/device-lifecycle.md` §4](../crypto-media/device-lifecycle.md)。

Actor MAY 有对应的 `actor_profile` 对象，便于在协作图中被 mention、assign 或展示。

所有 Station 承载 Actor 的完整身份统一为 `ActorId.account{account_id:{principal_id,station_id}}`，
包括 user、Agent、Ghost、organization/team 账号与 integration。服务以自身身份直接行动时使用
`ActorId.service{service_id}`。`actor_kind`、controller、provisioning、credential 与 lifecycle 是独立的
已验证事实，不得成为同一 principal/station pair 的另一身份分支，也不得仅因 account 分支授予权限。

Accountable actor MUST 记录责任关系，但 accountability 不等于 capability。

## 3. Actor Profile

### 3.1 概念

Actor Profile 是 Actor 在协作图中的展示镜像，不是权限主键。它用于：

- mention
- assignment
- display
- team membership view

Actor Profile 不替代 DID，也不成为权限主键。

### 3.2 Schema 与字段

Schema id: `ak.schema.actor_profile.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:actor_profile` | Actor Profile 是标准对象。 | Profile 对象 ID。 |
| `schema` | yes | `ak.schema.actor_profile.v1` | const。 | Schema ID。 |
| `realm_id` | no | `id:realm` | 全局 profile 可省略。 | 所属 Realm。 |
| `principal_id` | yes | `did_core_id` | 权限仍以经DID 证明的稳定主体与 capability 为准。 | Principal 的稳定业务身份。 |
| `actor_kind` | yes | `enum(user, organization, team, agent, bot, service, integration)` | 不含 `device`：设备非 actor 主体，见 §2 与 device-lifecycle §4。 | Actor 类型。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `agent_slug` | no | `string` | 仅 Agent 可用；pattern 以 `actor-profile.schema.json` 为准。若出现，MUST 可由当前有效 `ak.schema.agent_selector_claim.v1` 证明；冲突时 selector 解析 fail closed。 | controller-scoped agent mention selector 的投影 hint；不是 handle、权限主体或目录发现键。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, soft_logged_out, locked, suspended, deactivated, erasure_pending)` | 账户生命周期 status 的 public projection，不复用 [`common-fields.md` §5](./common-fields.md) 的对象通用 state；具体语义、转移与允许的写入主体见 [`../identity/account-lifecycle.md` §3](../identity/account-lifecycle.md)。 | 状态。 |
| `accountable_principal_ids` | no | `array<did>` | Agent、Bot 与托管 integration SHOULD 设置；每个 DID 必须由对应 `ak.identity.accountability_grant` 背书，详见 §3.3.1。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新主体。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 `principal_id` 与 `actor_kind` 的语义

`principal_id` 是授权、签名和审计归属的稳定 `did_core_id`；`actor_kind` 只是该主体在协作图中的展示和策略分类。

- **设备不是 actor 主体（normative）**：`actor_kind` 不含 `device`，设备没有自己的 DID。设备的一切普通协作-图行动 MUST 以所属账号的完整 account `ActorId`（包含 `principal_id` 与 `station_id`）作为 `actor_id`；设备身份通过 proof `verification_method`、`device_id`（`ak:device:<uuid>`）、`ak.device.authorize` 或 session grant 表达。唯一例外是声明 `ak.profile.mls.minimal_metadata_realm.v1` 的 Realm：发送方 MAY 使用显式 `ak.profile.ephemeral_pairwise_principal.v1` 的临时 pairwise **actor principal**（`did:key` 投影的 `did_core_id`，`actor_kind` 仍取 `user`/`agent` 等真实主体类型）。该 actor 不进入账号、PCR、Actor Profile 或设备目录；其作者 authority 仅来自 Event 所钉定 exact `(group_id, epoch, group_state_ref)` 中恰好一条 active LeafNode，且 credential identity 与 pairwise `did`、signature key 与 Event proof key 必须逐字一致。transport session 只承担访问与限流，不是作者授权，也不得被持久化为 identity link。该 pairwise actor 在 wire 上仍以完整 account `ActorId` 作者 Event，其 `actor_id` 的 `station_id` 分量是**当次的 hosting Station**；Realm 内状态（membership cell、MLS leaf 披露）仍按完整 `ActorId` 定址。只有 Realm **之外**的持有方把它当匹配键时才改用 `(realm_id, principal_id)`——v1 封闭列举为 consent peer 匹配与 KeyPackage claim 授权两处，判据见 [`../crypto-media/encryption-and-audit.md` §2.7](../crypto-media/encryption-and-audit.md)。该例外只对本 profile 成立，不放松普通 Account / Agent / service actor 的完整 ActorId 相等规则。
- `team`、`agent`、`bot`、`service` 和 `integration` MAY 使用独立 DID，也 MAY 由 `accountable_principal_ids` 指向控制/责任 principal；它们不会因为 `accountable_principal_ids` 自动继承权限。
- **Actor 分类边界（normative）**：`Agent` 是唯一的 Agent 概念；wire 上恰好使用 `actor_kind="agent"`，且 MUST 是 controller 通过 `ak.self.agent.command.provision.v1` 创建、拥有独立 DID document、指向 controller 的 `ak.identity.accountability_grant` 与 `ak.agent.key.authorize` runtime key 的一等 principal。协议不存在“普通设备 Agent”“托管 Agent”或 Agent 的 native/ghost 子类。Applet 创建或托管的自动化 Actor MUST 使用 `actor_kind="bot"`，不得使用 `agent`。Device 只是 principal endpoint，既不是 Actor 也不是 Agent。Ghost Actor 是外部主体镜像的 provenance，不是 `actor_kind`；外部账号/集成镜像使用 `integration`，外部 Bot 镜像使用 `bot`，不得使用 `agent`。Applet 自身直接行动时使用 `service`。Realm policy MUST 分别控制 Agent、Bot 与 Applet/Ghost provenance，不得合并为单一 "automation allowed" 开关：
  - **Agent**：可被 mention / grant / revoke / pause / deactivate；只走 Agent provisioning、pairing、runtime key、Sidecar 与 controller membership cascade。
  - **Bot**：Applet 管辖的自动化 principal；其 lifecycle 与授权根来自 Applet registration/install/provisioning，MUST NOT 进入 Agent provisioning、pairing、Sidecar 或 controller membership cascade。
  - **Ghost Actor**（[`../extensions/applet-integration.md`](../extensions/applet-integration.md)）：Applet 管辖 namespace 下的外部主体镜像。`actor_id` MUST 是该 Ghost 的完整 account `ActorId`；Actor Profile `principal_id` MUST 是无 fragment 的 `did_core_id`，不得用它替代完整账号身份；DID 仅进入已验证 resolution commitment，DID URL fragment 只用于 `verification_method`。其初始 `accountable_principal_ids` 恰为签署同 provisioning aggregate accountability grant 的 `[service_id]`；controller 只有另行签发 active grant 才可加入。每个 Ghost 有独立 `AccountId` 与 purpose=`applet_managed_control` PCR，rotation 走普通 resolution update；active registration/install grant/revoke fence 控制新写入，历史与 resolution audit 不因撤销而删除。
- **Agent 三轴正交（normative）**：Agent 通用 list/get 恰好暴露 lifecycle、readiness、presence。lifecycle (`active|paused|deactivated`) 只表达 controller intent；generic readiness (`ready|not_ready`) 的 closed blockers 只从主体级 durable runtime key 与 open pairing 派生，即 `runtime_key_missing|pairing_open`，不得复制 backup、session、KeyPackage、target grant/membership/reply/MLS facts；presence (`online|offline|unknown` + expiry/refresh) 只表达短时可达性。target-specific 事实只进入对应 operation 或 SDK local plan。pairing poll 的 `runtime_state` 只是 handle-local 诊断，不得进入 generic view/key_state 或成为第四轴。
- **Realm membership 从属性（normative）**：Agent 的 canonical Realm membership 是独立、caller-signed 的 `ak.member.state`；它的 effective membership 还必须与 controller 当前状态做确定性 AND。Agent 的 `join` payload MUST 携 `agent_controller_binding`，逐字绑定 controller 的 exact `AccountId` 与当前 accepted controller `join` Event ID（该 Event ID 就是 membership generation ref）。只有 `agent_member_cell == join`、controller 当前 cell 仍由该 exact join Event 建立且为 `join`、Agent lifecycle 为 `active`、provision/accountability 绑定仍有效时，Agent 才是 effective member。controller 后续 rejoin 产生新的 join Event ID，旧 Agent join 永远不能自动复活。
- controller 已是 active member 时，MAY 直接把自己控制且 lifecycle 为 `active` 的 Agent 从 `leave` 转为 `join`；该动作是 controller 对受控 principal 的显式授权，不是发给 Agent Runtime 的邀请，因此 MUST NOT 创建 pending invite、MUST NOT 要求 Agent opt-in，也 MUST NOT 走 `ak.invite.accept`。Reducer MUST 校验 active provisioning state、`ak.identity.accountability_grant`、Realm Agent policy、join policy 与 E2EE/MLS admission；仅凭 `accountable_principal_ids` 字面声明不得放行。普通成员不得用此路径加入其他 controller 的 Agent 或任意第三方 principal。
- **无主残留禁止（normative）**：controller 的 membership 不再是 binding 所指的 active `join` 时，受控 Agent 从同一 accepted basis 起立即 effective-invalid，不得 author Event、取得 capability、接收新 delivery、领取 KeyPackage 或继续作为 MLS active member；该安全门不等待 cleanup Event，也不依赖缓存。canonical Agent member cell 只由显式签名 Event 改写，reducer、Station、数据库 trigger 均不得合成 Agent leave。
- **显式 cascade（normative）**：controller terminal transition 的实际签名者必须为 terminal pre-state 中的全部 active controlled Agent 提交 `membership_cause="controller_membership_ended"` 的 leave Events；每条 Agent Event 的 `actor_id` 是 Agent，`executed_by` 是 terminal transition 的实际 initiator，并以 `agent_controller_binding.controller_terminal_event_ref` 绑定该 terminal Event。receiver 从 terminal pre-state 机械得到按 `agent_id` 排序的 exact set，禁止缺失、多余、重复、换 Realm、换 controller pair/generation、换 signer 或非 leave Event。
- self leave 使用 `unit_kind="agent_membership_cascade"`、`cascade_mode="atomic_self_leave"` 的完整原子 batch；任一 Event 或 exact-set 检查失败时 controller 与全部 Agent transition 一起回滚。第三方紧急 ban/remove 使用 `cascade_mode="emergency_terminal"` 先原子接受 terminal Event并建立 durable exact-set cleanup intent，权限立即失效；随后同一 initiator 用 `cascade_mode="emergency_cleanup"` 提交完整集合，全部验证后一次性落地 Agent transitions。同 intent exact replay 幂等，异内容拒绝。durable/wire record 不保存 pending/completed/overdue status；`completed_at` 与完整 `agent_transition_event_ids` 共同存在即 completed，否则 incomplete，incomplete record 在 `cleanup_due_at <= observation_time` 时才是 computed overdue view。超时只告警，不恢复权限，也不得由服务端代签。outcome 必须区分 `terminal_applied_cleanup_pending` 与 `cleanup_completed`。
- `membership_cause` 是 closed lifecycle cause，仅作审计分类，不授予 authority；安全 provenance 来自 terminal Event、exact controller binding、实际 signer、pre-state exact set 与原子提交。自由文本 `reason` 最长 256 个 Unicode scalar values，不得作为 cascade 成立的证据。
- `agent_slug` 只为 Agent 的 **controller-scoped mention selector** 服务。它与 controller handle 组合成输入 token `@<controller-handle>/<agent_slug>`，发送前必须解析为 Agent 的完整 `subject_account_id`。权威绑定来自 `ak.schema.agent_selector_claim.v1`，而不是 DID path 或 Actor Profile 字面值；Actor Profile 上的 `agent_slug` 只是 list/get、roster、mention picker 可用的投影 hint。`agent_slug` 本身 MUST NOT 进入 grant subject、actor attribution、membership key、delivery decision、公开 Directory search/list key 或 audit attribution。Reducer / profile projection 在同一 verified controller principal 下发现多个 active Agents 使用同一有效 selector claim 时，MUST 把该 selector 解析为 ambiguous 并 fail closed；实现 MAY 拒绝造成冲突的 `ak.profile.create` / `ak.profile.update` 或 selector claim。`agent_slug` 变化只影响未来输入解析，历史 mention 仍按已持久化的 `subject_account_id` 指向原 Agent。

- **两类 registered writer 必须产出同一个语义目标（normative）**：`ak.component.agent.selector_claim.v1`
  这个 cell family 有两个写入方——独立的 `ak.agent.selector_claim` 与 `ak.agent.provision` 的 selector 投影。
  cell namespace 两侧都保持 principal 级 `(controller principal, agent_slug)`，**不加 Station**；
  被选中的目标两侧都必须是同一个完整 AccountId。
  - 独立 claim 验它自己的 `ak.agent_selector_claim_proof.v1`：`subject_account_id` 是 binding field，
    换 Station 而复用原 proof MUST 验签失败。
  - provision 投影**没有**内层 selector proof，也 MUST NOT 为此新增一套签名或再复制一遍 agent principal。
    它的目标只能从已签名的 `payload.agent_id`、该 provision Event 的 exact controller account / Station
    与既有同 Station admission 规则派生，并在 Agent genesis / binding 完成后与
    `genesis.actor_id.account_id` 精确核对。**这不是取调用方当次的 Station。**
    provision 未完成（Agent PCR genesis 未 accepted）之前，该 Agent MUST NOT 被当作 active 可解析目标。
  - 无内层 proof 的投影 MUST NOT 被伪造成独立签名 claim。要求返回 `selector_claim.proofs` 的 portable
    响应，必须拿到真实 controller 或授权 issuer 签名的 claim；拿不到就不能广告 / 返回该成功面，
    服务端 MUST NOT 补签，也 MUST NOT 公开 private provision 材料来填满 DTO。

- **为什么该 cell 是 `mv_register` 而不是 `cas_register`（normative rationale）**：
  这个 family 承载的是一个 selector 的**占位声明**，占位语义通常会让人推断它应该是 CAS。
  规范选择 `mv_register` 是有意的，实现 MUST NOT 「顺手改成 CAS」：
  - **排他性不在 lattice 层，而在解析层。** 同一 verified controller principal 下出现多个有效 claim 时，
    上一条已经要求解析为 ambiguous 并 fail closed。这条领域规则提供的排他保证与 CAS 相同，
    却不会把 cell 本身推进不可写状态。
  - **`mv_register` 的因果取代给了 CAS 没有的活性。** 并发的两条 claim 在 MV 下是两个 heads，
    一条因果覆盖二者的后继 claim 会取代它们并自动收敛；同样的并发在 `cas_register` +
    `bottom=reject` 下会把 cell 打成 `⊥`，而按
    [`../authz/event-auth-state-resolution.md` §9.3.1.4](../authz/event-auth-state-resolution.md)
    该 family 的写入 precondition 读的正是它自己，`⊥` 之后没有主体能 author 普通写——
    一次 selector 竞争就会永久占死一个 slug。
  - **它不违反 §9.1 「`mv_register` 在 control plane 禁止作为授权根」。** `agent_slug` 已被上一条
    禁止进入 grant subject、actor attribution、membership key、delivery decision 与 audit attribution；
    它只参与 compose-time 的输入别名解析，解析结果还必须另行验证 Agent Actor Profile 与
    accountability grant。授权根仍是完整 AccountId 与既有 grant 链，不是这个 cell。
  - 因此本 family 的 `bottom=expose` 只表示读路径暴露多 heads，不构成 `⊥`（§9.1.1）。

- Event Envelope 在 reducer 接受时 stamp `actor_kind` projection(见 [`event-and-patch.md`](./event-and-patch.md) §2.2),让审计 / 取证 / offline reader 不必反向解析 Actor Profile 即可分类 event。该字段是 reducer-managed immutable,actor 提交侧 MUST NOT 携带。

### 3.3.1 `accountable_principal_ids` 的可验证性（normative）

`accountable_principal_ids` 是社工攻击面: actor 可以单方填入 `accountable_principal_ids: ["did:webvh:z6shM8wDREPSST7ZtxGkuFsk6:famous-org.example"]`,让其他客户端 / Directory UI 显示 "由 famous-org 担保" 的暗示信任，即便 famous-org 从未批准过。这对接收方做出"是否互动 / 是否接受邀请"的判断有真实影响。

因此 reducer **MUST** 校验:

1. 写入 / 更新 `Actor Profile.accountable_principal_ids[]` 的 Event 提交时，reducer MUST 对数组中**每个** DID 检查是否存在已 sealed 的问责记录，其 `issuer_id = <该 DID>`、`subject_id = profile.principal_id`、`grant_status = "active"`、`not_before <= now`，且若声明了 `expires_at` 则 `now <= expires_at`。**该记录有两个已登记来源，MUST 同时接受**（见下面的「问责记录只有一条，来源有两个」）：独立的 `ak.identity.accountability_grant`，以及 `ak.agent.provision` 的原子问责投影。MUST NOT 只搜索通用 kind。grant proof 使用 accepted auth-state / issuer key binding 验证；只有首次接受新 issuer / key、binding invalidation 或显式 freshness 触发时才解析 DID，不得在每次 profile replay 时在线解析。
2. 任一 DID 条目不存在对应 active grant 时，reducer MUST 以 `failed_precondition`
   reason=`accountability_grant_missing` 拒绝整个 `ak.profile.create` / `ak.profile.update`
   Event，且不得写入或裁剪后写入 Actor Profile cell。该判定只依赖签名 payload 与冻结的
   control-plane basis，所有 verifier 必须得到相同结果。
3. accountability grant 被签发方 revoke 后,reducer **SHOULD** 在 freshness 窗口(默认 ≤ 1 小时)内把对应 actor profile 的 `accountable_principal_ids[]` 中该条目降级为 `unverified`(projection 层标记),并在下次 actor profile update 时移除。

**问责记录只有一条，来源有两个（normative）**：
`ak.component.identity.accountability.v1` 承载的是**同一条**问责记录，
它有两个已登记写入方——独立的 `ak.identity.accountability_grant`，
以及 `ak.agent.provision` 在 controller PCR 内的原子问责投影
（[`../identity/key-management.md` §3.6](../identity/key-management.md)：
provision 原子投影问责事实，**后续独立变更仍使用通用 accountability Event**）。

- **cell 身份**是 `(Realm, issuer principal, subject principal, 归一化 exact scope set)`。
  两侧第三个 subject 分量 MUST 都是
  `string_set_digest(payload.accountability_scope, ak.accountability_scope_set.v1)`：
  裸 string 按 singleton set 解释，数组按既有 UTF-8 string-set 规则归一化。
  provision 的 scope 是固定 const，仍走同一归一化，二者因此落在同一个 cell。
- **修改 provision 问责的通用 grant MUST 写入原 controller PCR 的同一个 cell。**
  写入其它 Realm 是另一条记录，**不能**撤销原记录。完整 AccountId 的授权、Station 绑定与
  issuer 签名检查仍各自独立执行；MUST NOT 用 principal 相同推导 Account 等价。
- **canonical 业务值**固定为
  `{issuer_id, subject_id, accountability_scope（归一化排序数组）, not_before, expires_at?, grant_status}`。
  provision 映射 `controller_principal_id` / `agent_id`，通用 grant 映射 `issuer_id` / `subject_id`。
  两侧 MUST 使用显式登记的 `value_projection` 产出该形状，
  MUST NOT 在普通 `effect_projection.value.field` 路径里暗加改名或裁剪。
- **provision 派生值**：`not_before = envelope.created_at`，且 admission MUST 校验
  `payload.created_at == envelope.created_at`，避免两个签名时间产生歧义；
  `expires_at` **省略**（含义是不设时间到期，MUST NOT 写 JSON `null`，
  MUST NOT 采用服务器接收时间）；`grant_status = "active"`。
  时间条件成立不代表尚未 accepted 的 provision 可以提前生效。
- **`source_event_ref` 与内层 `proof` MUST NOT 进入业务值。**来源身份已由该 cell 的 head Event
  及其 accepted 证明承载；把 `event_id` 放进值会让语义完全相同的两个背书因来源不同变成异值，
  从而在同一个 `bottom=reject` cell 上制造假冲突。读取与快照 MUST 保留 head 到源 Event 的
  可验证关联，MUST NOT 丢掉证据或任选一个来源。
- 通用 grant 仍验证内层 issuer proof 与 Event proof；provision 只验证其已登记的 controller Event proof，
  MUST NOT 伪造 detached accountability proof，也 MUST NOT 把 provision 冒充独立 grant Event。

统一形状只消除**结构性伪差异**。不同 `not_before`、`expires_at` 或 `grant_status`
仍是真实不同的决定，按 `cas_register` 的正常规则处理。

`ak.identity.accountability_grant` 字段:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `issuer` | did | 签发 accountability 担保的主体(`accountable_principal_ids[]` 中被声明的 DID) |
| `subject` | did | 被担保的 actor principal(actor profile 的 `principal_id`) |
| `accountability_scope` | string \| array | 非空、无重复、无顺序语义的闭合集合（`employment` / `contracted_service` / `agent_operator`）；string 是 singleton set 的 wire 写法；仅供 UI 与 governance 展示，不参与授权 |
| `not_before` | timestamp | 担保起始时间 |
| `expires_at` | timestamp（可选） | 担保到期；过期后视作 unverified。缺省表示不设时间过期，由 `grant_status` 撤销与 controller lifecycle 级联治理;Agent 的 controller 自担保 SHOULD 缺省不声明 `expires_at`,避免静默失效悬崖（见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md)） |
| `grant_status` | enum(active, revoked) | issuer 主动 revoke 改为 `revoked` |
| `proof` | object | 由 `issuer` 的 active authentication key 签发 |

完整机读形态由 [`accountability-grant.schema.json`](../../artifacts/schemas/accountability-grant.schema.json) 权威定义；payload 的 `schema` MUST 为 `ak.schema.accountability_grant.v1`。`proof.payload_digest` MUST 覆盖 `utf8("ak.accountability-grant-v1\n") || canonical_json(payload with proof omitted)`，且 verification method controller MUST 等于 `issuer`。

`accountability_scope` 的 array 顺序不表达优先级、时间或授权强度；receiver MUST 接受合法 singleton array 与任意合法排列，且只在 cell subject 派生、领域相等比较和 projection 聚合时按 [`encoding.md` §9.5.1](../conformance/encoding.md) 的 canonical string-set 规则规范化，不得重写已签名 payload bytes。Canonical authoring API 对新 Event MUST 将单元素集合输出为 string，多元素集合按原始 UTF-8 bytes 升序输出为 array。

Accountability 状态按 `(issuer, subject, normalized exact scope set)` 独立定址。同一 exact set 的 `active` 与 `revoked` 必须写入同一 cell；revoke 必须携带与被撤销 grant 完全相同的集合，子集 revoke 不表示从超集中做差集。若只需保留原集合的一部分，issuer 必须先 revoke 原 exact set，再签发目标 exact set。多个 exact-set cell 可同时 active；projection 展示的 active scopes 是这些 cell 的集合并集，撤销其中一个不得影响其它 cell。只要至少一个未过期的 active exact-set cell 存在，该 issuer/subject accountability 关系仍可验证。

**UI / projection 责任**:

- 客户端 UI **MUST** 把 `accountable_principal_ids[]` 中已校验通过的 DID 与因既有 grant 后续过期 /
  revoked 而成为 unverified 的 DID 以可感知、可测试的 presentation invariant 区分；具体文案、
  图形、隐藏策略或控件形式属于实现自由，但 verified 与 unverified 两种状态不得在同一上下文中
  呈现为等价信任暗示。缺失 grant 的新声明不会进入 cell，不属于此展示分支。
- 客户端 UI **MUST NOT** 仅根据 actor profile 字面值显示信任暗示。
- Directory / Search 投影把 `accountable_principal_ids` 作为过滤条件时 MUST 只对 verified 条目生效。

**Why**: 没有这层校验时,actor 可以伪造任意大型组织或知名实体作为"担保人",借此社工诱导对端；
有了 grant-based 准入校验，虚假声明的整个 Event 会被确定性拒绝，不能进入 Actor Profile cell。

## 4. 跨链路引用对照

主体引用字段的完整跨字段对照与语义以 [common-fields.md §4](./common-fields.md) 为唯一规范来源。

## 5. Actor 与协作图

Actor 在协作图中通过：

- **Capability Grant**（[`governance-objects.md`](./governance-objects.md)）：表达"谁能做什么"。
- **Relation `assigned_to` / `mentions`**：表达"谁参与 / 被 cue"。
- **Membership state event**（`ak.member.state`）：表达"谁在 Realm"，详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- **Identity claim / handle**：表达"对外可发现身份"，详见 [`../identity/identity-handles.md`](../identity/identity-handles.md)。

`actor_profile` 只是上述结构在 UI 层的展示镜像。

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- DID / identity：[`../identity/identity-did.md`](../identity/identity-did.md)。
- Handles / claim：[`../identity/identity-handles.md`](../identity/identity-handles.md)。
- 账户 lifecycle：[`../identity/account-lifecycle.md`](../identity/account-lifecycle.md)。
- Capability：[`../authz/capabilities.md`](../authz/capabilities.md)。
- Actor Profile schema：`artifacts/schemas/actor-profile.schema.json`。
