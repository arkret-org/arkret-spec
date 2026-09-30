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

Actor Profile 可声明以下展示分类（`actor_kind`）：

- `user`
- `organization`
- `team`
- `agent`
- `bot`
- `service`
- `integration`

`actor_kind` 不包含 `device`：设备不是 actor 主体，没有自己的 DID。设备永远从属于某个 user/organization principal，通过 `ak.device.authorize` 由该 principal 授权登记；设备的稳定标识是 `device_id`（`ak:device:<uuid>` typed ID），设备密钥是该 principal DID 下的 verification method。`actor_kind` 只存在于 Actor Profile / read projection，不进入 Event Envelope，也不授予 capability、决定签名归属或替代 provisioning / registration / installation / accountability。详见 [`../crypto-media/device-lifecycle.md` §4](../crypto-media/device-lifecycle.md)。

Actor MAY 有对应的 `actor_profile` 对象，便于在协作图中被 mention、assign 或展示。

所有 Station 承载 Actor 的完整身份统一为 `ActorId.account{account_id:{principal_id,station_id}}`，
包括 user、Agent、Ghost、organization/team 账号与 integration。服务以自身身份直接行动时使用
`ActorId.service{service_id}`。Profile `actor_kind` 是非权威展示分类；controller、provisioning、registration、
credential 与 lifecycle 才是各自独立验证的安全事实。任何一项都不得成为同一 principal/station pair 的另一身份分支，也不得仅因 account 分支或 Profile 分类授予权限。

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
| `actor_kind` | yes | `enum(user, organization, team, agent, bot, service, integration)` | 不含 `device`：设备非 actor 主体，见 §2 与 device-lifecycle §4。仅用于 Profile 展示、发现与 compose-time 分类；不得作为 Event 授权、签名归属或审计问责的权威来源。 | Actor Profile 分类。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `agent_slug` | no | `string` | 仅 Agent 可用；pattern 以 `actor-profile.schema.json` 为准。若出现，MUST 可由当前 `agent_selector_claim` typed current 对已知完整 AccountId 校验；冲突时该 label 不得显示为 verified。 | controller-scoped picker label 投影 hint；不是 handle、权限主体或目录发现键。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, soft_logged_out, locked, suspended, deactivated, erasure_pending)` | 账户生命周期 status 的 public projection，不复用 [`common-fields.md` §5](./common-fields.md) 的对象通用 state；具体语义、转移与允许的写入主体见 [`../identity/account-lifecycle.md` §3](../identity/account-lifecycle.md)。 | 状态。 |
| `accountable_principal_ids` | no | `array<did>` | Agent、Bot 与托管 integration SHOULD 设置；每个 DID 必须由对应 `ak.identity.accountability_grant` 背书，详见 §3.3.1。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新主体。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 `principal_id` 与 `actor_kind` 的语义

`principal_id` 是授权、签名和审计归属的稳定 `did_core_id`；`actor_kind` 只是该 Profile 在协作图中的展示、发现和 compose-time 分类。Profile 值与已验证 provisioning / registration / installation / ActorId 分支或 accountability 冲突时，安全判断 MUST 使用后者并 fail closed；不得以 Profile 扩权或改写历史 Event 归属。

- **设备不是 actor 主体（normative）**：`actor_kind` 不含 `device`，设备没有自己的 DID。设备的一切普通协作-图行动 MUST 以所属账号的完整 account `ActorId`（包含 `principal_id` 与 `station_id`）作为 `actor_id`；设备身份通过 proof `verification_method`、`device_id`（`ak:device:<uuid>`）、`ak.device.authorize` 或 session grant 表达。v1 没有例外：不存在把 `did:key` 投影成 Realm actor principal 的分支，也不存在只用 `(realm_id, principal_id)` 匹配 actor 的持有方。
- `team`、`agent`、`bot`、`service` 和 `integration` MAY 使用独立 DID，也 MAY 由 `accountable_principal_ids` 指向控制/责任 principal；它们不会因为 `accountable_principal_ids` 自动继承权限。
- **Actor 分类边界（normative）**：`Agent` 是唯一的 Agent 概念；其 Actor Profile 使用 `actor_kind="agent"`，但 Agent 身份 MUST 由 controller 发起的 `ak.self.agent.command.provision.v1`、独立 DID document、指向 controller 的 `ak.identity.accountability_grant` 与 `ak.agent.key.authorize` runtime key 共同证明。协议不存在“普通设备 Agent”“托管 Agent”或 Agent 的 native/ghost 子类。Applet 创建或托管的自动化 Actor Profile 使用 `actor_kind="bot"`，不得使用 `agent`，但其安全身份来自 Applet registration/install/provisioning。Device 只是 principal endpoint，既不是 Actor 也不是 Agent。Ghost Actor 是外部主体镜像的 provenance，不是 `actor_kind`；外部账号/集成镜像 Profile 使用 `integration`，外部 Bot 镜像 Profile 使用 `bot`，不得使用 `agent`。Applet 自身直接行动时由 `ActorId.service` 与 registration 证明，Profile 可分类为 `service`。Realm policy MUST 分别控制 Agent、Bot 与 Applet/Ghost provenance，不得把 Profile 字面值当作单一 "automation allowed" 授权开关：
  - **Agent**：可被 mention / grant / revoke / pause / deactivate；只走 Agent provisioning、pairing、runtime key、Sidecar 与 exact controller membership binding。未登记的 cascade 提交不得被当作可调用能力。
  - **Bot**：Applet 管辖的自动化 principal；其 lifecycle 与授权根来自 Applet registration/install/provisioning，MUST NOT 进入 Agent provisioning、pairing、Sidecar 或 controller membership cascade。
  - **Ghost Actor**（[`../extensions/applet-integration.md`](../extensions/applet-integration.md)）：Applet 管辖 namespace 下的外部主体镜像。`actor_id` MUST 是该 Ghost 的完整 account `ActorId`；Actor Profile `principal_id` MUST 是无 fragment 的 `did_core_id`，不得用它替代完整账号身份；DID 仅进入已验证 resolution commitment，DID URL fragment 只用于 `verification_method`。其初始 `accountable_principal_ids` 恰为签署同 provisioning aggregate accountability grant 的 `[service_id]`；controller 只有另行签发 active grant 才可加入。每个 Ghost 有独立 `AccountId` 与 purpose=`applet_managed_control` PCR，rotation 走普通 resolution update；active registration/install grant/revoke fence 控制新写入，历史与 resolution audit 不因撤销而删除。
- **Agent 三轴正交（normative）**：Agent 通用 list/get 恰好暴露 lifecycle、readiness、presence。lifecycle (`active|paused|deactivated`) 只表达 controller intent；generic readiness (`ready|not_ready`) 的 closed blockers 只从主体级 durable runtime key 与 open pairing 派生，即 `runtime_key_missing|pairing_open`，不得复制 backup、session、KeyPackage、target grant/membership/reply/MLS facts；presence (`online|offline|unknown` + expiry/refresh) 只表达短时可达性。target-specific 事实只进入对应 operation 或 SDK local plan。pairing poll 的 `runtime_state` 只是 handle-local 诊断，不得进入 generic view/key_state 或成为第四轴。
- **Realm membership 从属性（normative）**：Agent 的 canonical Realm membership 是独立、caller-signed 的 `ak.member.state`；它的 effective membership 还必须与 controller 当前状态做确定性 AND。Agent 的 `join` payload MUST 携 `agent_controller_binding`，逐字绑定 controller 的 exact `AccountId` 与当前 accepted controller `join` Event ID（该 Event ID 就是 membership generation ref）。在 controller/Agent 私聊完整原子 founding unit 内，允许按 [私聊 §6.1](../identity/contact-and-direct-conversation.md) 显式引用同批前序 controller join，整批 accepted 才生效；字段不得省略或由 receiver 推导。只有 `agent_member_result == join`、controller 当前 typed current result 仍由该 exact join Event 建立且为 `join`、Agent lifecycle 为 `active`、provision/accountability 绑定仍有效时，Agent 才是 effective member。controller 后续 rejoin 产生新的 join Event ID，旧 Agent join 永远不能自动复活。
- controller 已是 active member 时，MAY 直接把自己控制且 lifecycle 为 `active` 的 Agent 从 `leave` 转为 `join`；该动作是 controller 对受控 principal 的显式授权，不是发给 Agent Runtime 的邀请，因此 MUST NOT 创建 pending invite、MUST NOT 要求 Agent opt-in，也 MUST NOT 走 `ak.invite.accept`。Reducer MUST 校验 active provisioning state、`ak.identity.accountability_grant`、Realm Agent policy、join policy 与 E2EE/MLS admission；仅凭 `accountable_principal_ids` 字面声明不得放行。普通成员不得用此路径加入其他 controller 的 Agent 或任意第三方 principal。
- **无主残留禁止（normative）**：controller 的 membership 不再是 binding 所指的 active `join` 时，受控 Agent 从同一 accepted basis 起立即 effective-invalid，不得 author Event、取得 capability、接收新 delivery、领取 KeyPackage 或继续作为 MLS active member；该安全门不等待 cleanup Event，也不依赖缓存。canonical Agent member typed current result 只由显式签名 Event 改写，reducer、Station、数据库 trigger 均不得合成 Agent leave。
- **显式 cascade 的 v1 边界（normative）**：`AgentMembershipCascadeSubmission` 与 exact-set cleanup record 是已登记的 typed 模型，但正式 `self_submit_request`／`self_submit_outcome` closed union 尚无对应分支。v1 不存在可调用的 cascade ingress；receiver MUST 对声称携带 `unit_kind="agent_membership_cascade"` 的提交失败关闭，不得把普通 Event body 当成原子 batch、合成 Agent leave，或返回 `terminal_applied_cleanup_pending`／`cleanup_completed` 的假 outcome。controller exact join generation 失效时，上一段的 effective-invalid 门立即生效；canonical Agent member typed current result 仍须由真实已签 Event 才能改变。typed 模型中 self leave exact set、第三方 terminal cleanup intent、原 initiator 签名及幂等/超时规则只限定将来若有正式载体时的验证语义，不构成 v1 操作可用性承诺。
- `membership_cause` 是 closed lifecycle cause，仅作审计分类，不授予 authority；它不能替代 terminal Event、exact controller binding、实际 signer 与正式 aggregate admission。自由文本 `reason` 最长 256 个 Unicode scalar values，不得作为 cascade 成立的证据。
- `agent_slug` 是 Agent 的 **controller-scoped picker label**，仅在客户端已从授权来源取得目标完整 `subject_account_id` 后用于展示和逐字节绑定校验。当前 `agent_selector_claim` typed current 可证明该 label 绑定该已知目标；DID path、Actor Profile 字面值、roster 中的裸 slug 均不能反向构造 AccountId。v1 不支持把 controller handle 与 slug 组合成自由文本 `@<controller-handle>/<agent_slug>` 自动寻址；跨 Station 没有完整候选集/absence proof，单一 Station 的 current 行不能证明 principal 级唯一。`agent_slug` MUST NOT 进入 grant subject、actor attribution、membership key、delivery decision、公开 Directory search/list key 或 audit attribution。多个当前可见 selector 值冲突时该 label 不得显示为 verified，且不得据此改选目标；实现 MAY 拒绝造成冲突的 `ak.profile.create` / `ak.profile.update` 或 `ak.agent.provision`。slug 变化不改写历史 mention 的已持久化 `subject_account_id`。

- **唯一写入方（normative）**：`agent_selector_claim` 这个 typed current result family 只由 `ak.agent.provision`
  的 selector 投影写入；协议不定义独立的 selector claim Event，也不定义可携带的签名 selector claim。
  namespace 是 principal 级 `(controller principal, agent_slug)`，**不加 Station**；被选中的目标是一个完整 AccountId。
  - provision 投影**没有**内层 selector proof，也 MUST NOT 为此新增一套签名或再复制一遍 agent principal。
    它的目标只能从已签名的 `payload.agent_id`、该 provision Event 的 exact controller account / Station
    与既有同 Station admission 规则派生，并在 Agent genesis / binding 完成后与
    `genesis.actor_id.account_id` 精确核对。**这不是取调用方当次的 Station。**
    provision 未完成（Agent PCR genesis 未 accepted）之前，该 Agent MUST NOT 被当作 active 可解析目标。
  - 服务端 MUST NOT 补签任何 selector claim，也 MUST NOT 公开 private provision 材料来填满任何响应。
  - 同一 controller 以同一 slug 再次 provision 时，新值整体置换旧绑定。Agent deactivate / revoke 不删除该行，
    由下方「已知目标 label 校验」的 lifecycle 检查使 label 不可验证。

- **canonical value（normative）**：该 family 的 canonical 业务值固定为
  `{subject_account_id, visibility, audience?}`。`subject_account_id` 恒为完整 AccountId；
  `audience` 缺席表示 public 情形，MUST NOT 写 JSON `null`。
  值里**没有** `claim_scope`——开放对象不能承载 MUST 级授权判定所依赖的状态而仍让所有 verifier
  判定一致，理由与 [`../identity/identity-handles.md` §3.2](../identity/identity-handles.md) 对 `HandleClaimCore`
  的既有裁决同一条；disclosure 边界只有 `visibility` 与 `audience`，`intent` 是请求参数而不是值成员。
  `issuer_id`、`vouching_id`、`source_refs`、`created_at`、`verified_at`、`expires_at` 与 `proofs`
  同样不进入值：来源身份已由 head Event 及其接纳证明承载，provision 绑定不按时钟过期。
  值也不重复自己的 subject——与 `identity_accountability` 不同，本 family 没有「把值当便携记录逐字段读」的读者。
- **provision 侧 AccountId 的唯一登记派生（normative）**：provision 的 selector 投影里，
  `subject_account_id` 由已登记派生 `agent_account_id_from_provision` 产出：
  principal 分量取已签名的 `payload.agent_id`，station 分量取**本 Event 自己的**
  `envelope.actor_id`（即 controller 账号）的 station 分量。它是 derivation 而不是字段拷贝，
  因为 `value_projection` 的成员来源里 `select` 只能取**一条**字段路径，
  没有任何拼法能把 payload 的 principal 与 envelope 的 station 合起来；
  而该值在 wire 上完全确定，所有 verifier 得到同一串字节。这条派生也是
  [`strand-and-message.md` §9.4.1](./strand-and-message.md) 那串客户端禁令的服务端对偶：
  不取本机 authoring Station、不取 controller handle 的 Station、不取 DID 默认 Station、
  不取当前解析 facade 的 Station——改为这一条唯一规则。
- **已知目标 label 校验（normative）**：先从获授权的 roster/picker 得到完整 Agent `subject_account_id`，再 MAY 读取当前可见且已确认的 selector 值并要求目标逐字节相等，同时检查 Agent lifecycle、accountability 与 visibility。冲突或缺确认材料只使 label 不可验证，不得把它们变成另一个目标；已知完整 AccountId 的普通 mention 仍按其独立成员/可读权与 Agent gate 判定。selector 不替代成员、grant 或审计责任身份。

- Event Envelope 不携带主体分类 stamp。审计 / 取证 / offline reader 必须分别保留签名覆盖的 `actor_id` 与可选 `executed_by`，并解析准入时点的 provisioning / registration / installation / accountability / identity 证据；Actor Profile `actor_kind` 只能作为展示分类，不能决定问责主体、executor 或权限。

### 3.3.1 `accountable_principal_ids` 的可验证性（normative）

`accountable_principal_ids` 是社工攻击面: actor 可以单方填入 `accountable_principal_ids: ["did:webvh:z6shM8wDREPSST7ZtxGkuFsk6:famous-org.example"]`,让其他客户端 / Directory UI 显示 "由 famous-org 担保" 的暗示信任，即便 famous-org 从未批准过。这对接收方做出"是否互动 / 是否接受邀请"的判断有真实影响。

因此 reducer **MUST** 校验:

**Applet service issuer 的封闭例外（normative）**：普通 issuer 使用下文 PCR / active device 合同。只有 [applet-integration.md §4b / §9.1](../extensions/applet-integration.md) 的 install Bot / provision Ghost closed creation aggregate 可以由 `ActorId.service` 的 Applet service 签发 accountability Event：issuer MUST 等于 exact registration `service_id`，subject MUST 等于同单元 provision 的 managed principal；Event 位于该 provision 所属的目标 Collaboration Realm，而非不存在的 service PCR。payload 内层 proof 与 `producer_proof` MUST 使用同一个由该 exact registration epoch evidence 验证的 service verification method 与 key，不使用 principal device fragment。profile 在同一原子单元内读取这条暂待提交记录，并以同事务最终 accepted 状态校验；后续 profile 只可通过 accepted managed provision anchors 唯一选定该 Realm、exact install 与 service endorsement。不得全 Realm 搜索、任取同 service 的 grant，或把 namespace / profile 字面值作为 exception 证据。exact install 不再 active 时，该 service endorsement 对后续 profile admission / verified 展示立即失效；没有可验证 anchors 时返回 `accountability_grant_missing`。此例外不开放 standalone service accountability ingress，不改变 ordinary issuer 与 Agent controller 的 PCR 查找规则，也不授予 action 权限。

1. 写入 / 更新 `Actor Profile.accountable_principal_ids[]` 的 Event 提交时，reducer MUST 对数组中**每个** DID 检查是否存在已 committed 的问责记录，其 `issuer_id = <该 DID>`、`subject_id = profile.principal_id`、`grant_status = "active"`、`not_before <= now`，且若声明了 `expires_at` 则 `now <= expires_at`。**该记录有两个已登记来源，MUST 同时接受**（见下面的「问责记录只有一条，来源有两个」）：独立的 `ak.identity.accountability_grant`，以及 `ak.agent.provision` 的原子问责投影。MUST NOT 只搜索通用 kind。判定时刻 `now` 是接纳该 profile Event 的 RealmCommit 的 `committed_at`（治理 Station 在分配该 Commit 的同一接纳事务内读取问责记录，并锁住所依赖的记录行，使并发撤销排在该 Commit 之前或之后）；Event 的 `created_at` 不参与该判定，因此预签的 profile Event 不能在问责撤销后借旧时间被接纳。问责记录除上述 Applet closed creation exception 外只在 **issuer 的 Principal Control Realm** 中查找（两个来源都只写入那里，见下文）；issuer 的 PCR 不由接纳该 profile 的同一治理 Station 治理时，该 Station 读不到记录，结果即 `accountability_grant_missing`。同一 `(issuer, subject)` 的多个 exact-set 记录中任一满足条件即可。
2. 任一 DID 条目不存在对应 active grant 时，reducer MUST 以 `failed_precondition`
   reason=`accountability_grant_missing` 拒绝整个 `ak.profile.create` / `ak.profile.update`
   Event，且不得写入或裁剪后写入 Actor Profile typed current result。该判定只依赖签名 payload 与冻结的
   control-plane basis，所有 verifier 必须得到相同结果。
3. accountability grant 被签发方 revoke 后,reducer **SHOULD** 在 freshness 窗口(默认 ≤ 1 小时)内把对应 actor profile 的 `accountable_principal_ids[]` 中该条目降级为 `unverified`(projection 层标记),并在下次 actor profile update 时移除。

**问责记录只有一条，来源有两个（normative）**：
`identity_accountability` 承载的是**同一条**问责记录，
它有两个已登记写入方——独立的 `ak.identity.accountability_grant`，
以及 `ak.agent.provision` 在 controller PCR 内的原子问责投影
（[`../identity/key-management.md` §3.6](../identity/key-management.md)：
provision 原子投影问责事实，**后续独立变更仍使用通用 accountability Event**）。

- **typed current result 身份**是 `(Realm, issuer principal, subject principal, 归一化 exact scope set)`。
  两侧第三个 subject 分量 MUST 都是
  `string_set_digest(payload.accountability_scope, ak.accountability_scope_set.v1)`：
  裸 string 按 singleton set 解释，数组按既有 UTF-8 string-set 规则归一化。
  provision 的 scope 是固定 const，仍走同一归一化，二者因此落在同一个 typed current result。
  该函数先拒绝空集与重复项，再按原始 UTF-8 字节升序得到 `normalized_scopes`，构造唯一闭合 transcript
  `{"scopes": normalized_scopes}`；摘要输入固定为
  `UTF8("ak.accountability_scope_set.v1\n") || RFC8785_JCS({"scopes": normalized_scopes})`，
  输出固定为 `"sha256:" + lowercase_hex(SHA256(input))`。domain 不是 transcript 成员，构造方与验证方
  MUST NOT 直接摘要裸数组、保留来线数组顺序，或把输出改写为 Base64URL。逐字节向量见
  [`canonical-json-digest-kat-fixture.json`](../../artifacts/fixtures/canonical-json-digest-kat-fixture.json)。
- **普通 issuer 的记录只存在于 issuer 的 PCR；Applet service closed aggregate 使用上述明确例外。** 普通 `ak.identity.accountability_grant` 的 `envelope.realm_id` MUST 是 issuer 的
  Principal Control Realm，`envelope.actor_id` MUST 是 issuer 本人（`admission=self_authored_proof`）；
  provision 的原子投影写入 controller（即 issuer）的 PCR。因此修改 provision 问责的通用 grant 落在原 controller
  PCR 的同一个 typed current result。完整 AccountId 的授权、Station 绑定与
  issuer 签名检查仍各自独立执行；MUST NOT 用 principal 相同推导 Account 等价。
- **canonical 业务值**固定为
  `{issuer_id, subject_id, accountability_scope（归一化排序数组）, not_before, expires_at?, grant_status}`。
  provision 映射 `controller_principal_id` / `agent_id`，通用 grant 映射 `issuer_id` / `subject_id`。
  两侧 MUST 使用显式登记的 `value_projection` 产出该形状，
  MUST NOT 在普通 `result_projection.value.field` 路径里暗加改名或裁剪。
- **provision 派生值**：`not_before = envelope.created_at`，且 admission MUST 校验
  `payload.created_at == envelope.created_at`，避免两个签名时间产生歧义；
  `expires_at` **省略**（含义是不设时间到期，MUST NOT 写 JSON `null`，
  MUST NOT 采用服务器接收时间）；`grant_status = "active"`。
  时间条件成立不代表尚未 accepted 的 provision 可以提前生效。
- **`source_event_ref` 与内层 `proof` MUST NOT 进入业务值。**来源身份已由该 typed current result 的 head Event
  及其 accepted 证明承载；把 `event_id` 放进值会让语义完全相同的两个背书因来源不同变成异值，
  而无需把来源身份复制进业务值。读取与快照 MUST 保留 head 到源 Event 的
  可验证关联，MUST NOT 丢掉证据或任选一个来源。
- 普通 issuer 的通用 grant 仍验证内层 issuer proof 与 Event proof。内层 `proof` 的 verification method MUST 与该 Event 的
  producer proof 是同一个 `<issuer DID>#ak:device:<device_id>` 设备方法，且该设备在接纳事务读取的 issuer PCR
  同一 cut 上为 `active`；即 issuer 的「active authentication key」就是签发该 Event 的当前设备 key，按 Event
  producer proof 的同一路径验证，不在线解析 DID，DID Document 的其它 authentication 方法不是 v1 问责 proof key。
  provision 只验证其已登记的 controller Event proof，
  MUST NOT 伪造 detached accountability proof，也 MUST NOT 把 provision 冒充独立 grant Event。

统一形状只消除**结构性伪差异**。不同 `not_before`、`expires_at` 或 `grant_status`
仍是真实不同的决定，按 `commit-ordered projection` 的确认顺序和实际前置条件处理。

`ak.identity.accountability_grant` 字段:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `issuer` | did | 签发 accountability 担保的主体(`accountable_principal_ids[]` 中被声明的 DID) |
| `subject` | did | 被担保的 actor principal(actor profile 的 `principal_id`) |
| `accountability_scope` | string \| array | 非空、无重复、无顺序语义的闭合集合（`employment` / `contracted_service` / `agent_operator`）；string 是 singleton set 的 wire 写法；仅供 UI 与 governance 展示，不参与授权 |
| `not_before` | timestamp | 担保起始时间 |
| `expires_at` | timestamp（可选） | 担保到期；过期后视作 unverified。缺省表示不设时间过期，由 `grant_status` 撤销与 controller lifecycle 级联治理;Agent 的 controller 自担保 SHOULD 缺省不声明 `expires_at`,避免静默失效悬崖（见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md)） |
| `grant_status` | enum(active, revoked) | issuer 主动 revoke 改为 `revoked` |
| `proof` | object | 普通 issuer 由 PCR 同 cut active 设备 key 签发；Applet closed creation 使用 exact registration epoch service key；均与 producer proof 同一 verification method |

完整机读形态由 [`accountability-grant.schema.json`](../../artifacts/schemas/accountability-grant.schema.json) 权威定义；payload 的 `schema` MUST 为 `ak.schema.accountability_grant.v1`。`proof.payload_digest` MUST 覆盖 `utf8("ak.accountability-grant-v1\n") || canonical_json(payload with proof omitted)`，且 verification method controller MUST 等于 `issuer`。

`accountability_scope` 的 array 顺序不表达优先级、时间或授权强度；receiver MUST 接受合法 singleton array 与任意合法排列，且只在 typed current result subject 派生、领域相等比较和 projection 聚合时按 [`encoding.md` §9.5.1](../conformance/encoding.md) 的 canonical string-set 规则规范化，不得重写已签名 payload bytes。Canonical authoring API 对新 Event MUST 将单元素集合输出为 string，多元素集合按原始 UTF-8 bytes 升序输出为 array。

Accountability 状态按 `(issuer, subject, normalized exact scope set)` 独立定址。同一 exact set 的 `active` 与 `revoked` 必须写入同一 typed current result；revoke 必须携带与被撤销 grant 完全相同的集合，子集 revoke 不表示从超集中做差集。若只需保留原集合的一部分，issuer 必须先 revoke 原 exact set，再签发目标 exact set。多个 exact-set typed current result 可同时 active；projection 展示的 active scopes 是这些 typed current result 的集合并集，撤销其中一个不得影响其它 typed current result。只要至少一个未过期的 active exact-set typed current result 存在，该 issuer/subject accountability 关系仍可验证。

**UI / projection 责任**:

- 客户端 UI **MUST** 把 `accountable_principal_ids[]` 中已校验通过的 DID 与因既有 grant 后续过期 /
  revoked 而成为 unverified 的 DID 以可感知、可测试的 presentation invariant 区分；具体文案、
  图形、隐藏策略或控件形式属于实现自由，但 verified 与 unverified 两种状态不得在同一上下文中
  呈现为等价信任暗示。缺失 grant 的新声明不会进入 typed current result，不属于此展示分支。
- 客户端 UI **MUST NOT** 仅根据 actor profile 字面值显示信任暗示。
- Directory / Search 投影把 `accountable_principal_ids` 作为过滤条件时 MUST 只对 verified 条目生效。

**Why**: 没有这层校验时,actor 可以伪造任意大型组织或知名实体作为"担保人",借此社工诱导对端；
有了 grant-based 准入校验，虚假声明的整个 Event 会被确定性拒绝，不能进入 Actor Profile typed current result。

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
