---
title: Actor & Actor Profile
status: candidate
normative: true
stability: v1
updated: 2026-07-02
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
- `org`
- `team`
- `agent`
- `service`
- `integration`

`actor_kind` 不包含 `device`：设备不是 actor 主体，没有自己的 DID。设备永远从属于某个 user/org principal，通过 `ak.device.authorize` 由该 principal 授权登记；设备的稳定标识是 `device_id`（`ak:device:<uuid>` typed ID），设备密钥是该 principal DID 下的 verification method。详见 [`../crypto-media/device-lifecycle.md` §4](../crypto-media/device-lifecycle.md)。

Actor MAY 有对应的 `actor_profile` 对象，便于在协作图中被 mention、assign 或展示。

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
| `principal_id` | yes | `did` | 权限仍以 DID/capability 为准。 | Principal DID。 |
| `actor_kind` | yes | `enum(user, org, team, agent, service, integration)` | 不含 `device`：设备非 actor 主体，见 §2 与 device-lifecycle §4。 | Actor 类型。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `agent_slug` | no | `string` | 仅 native personal agent 可用；pattern 以 `actor-profile.schema.json` 为准。若出现，MUST 可由当前有效 `ak.schema.agent_selector_claim.v1` 证明；冲突时 selector 解析 fail closed。 | controller-scoped agent mention selector 的投影 hint；不是 handle、权限主体或目录发现键。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, soft_logged_out, locked, suspended, deactivated, erasure_pending)` | 账户生命周期 status 的 public projection，不复用 [`common-fields.md` §5](./common-fields.md) 的对象通用 state；具体语义、转移与允许的写入主体见 [`../identity/account-lifecycle.md` §3](../identity/account-lifecycle.md)。 | 状态。 |
| `accountable_principal_ids` | no | `array<did>` | agent/托管账号 SHOULD 设置；每个 DID 必须由对应 `ak.identity.accountability_grant` 背书，详见 §3.3.1。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新主体。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 `principal_id` 与 `actor_kind` 的语义

`principal_id` 是授权、签名和审计归属的根；`actor_kind` 只是该 DID 在协作图中的展示和策略分类。

- **设备不是 actor 主体（normative）**：`actor_kind` 不含 `device`，设备没有自己的 DID。设备的一切协作-图行动 MUST 以所属 user/org principal DID 作为 `actor_id`；设备身份通过 proof `verification_method`、`device_id`（`ak:device:<uuid>`）、`ak.device.authorize` 或 session grant 表达。需要 pairwise 匿名行动时，MUST 创建临时 pairwise **principal**（`did:key`，`actor_kind` 取 `user`/`agent` 等真实主体类型），而不是把设备当作独立主体；该临时 principal 仍需经正常 actor 登记，其设备同样通过 `ak.device.authorize` 从属于它。
- `team`、`agent`、`service` 和 `integration` MAY 使用独立 DID，也 MAY 由 `accountable_principal_ids` 指向控制/责任 principal；它们不会因为 `accountable_principal_ids` 自动继承权限。
- `actor_kind` 的 wire enum 不包含 `agent_native`、`agent_ghost` 或 `ghost`。Native personal agent 使用 `actor_kind="agent"`，并由 `ak.profile.personal_agent_provisioning.v1` provisioning state 区分；Applet-managed Ghost Actor 使用现有 enum 中最贴合其主体类型的值（外部人类/账号镜像 SHOULD 使用 `integration`，Applet 托管 AI/automation MAY 使用 `agent`）。Realm policy 必须能通过 Applet provenance、`accountable_principal_ids`、profile 与 capability 分别控制 native personal agent 与 Applet / Ghost Actor，不得合并为单一 "automation allowed" 开关：
  - **Native personal agent**:由 controller 通过 `ak.self.agent.command.provision` 直接创建的一等 Arkret actor principal,拥有独立 DID document、`ak.identity.accountability_grant` 指向 controller、`ak.agent.key.authorize` 绑定的运行时 key。可被 mention / grant / revoke / pause / deactivate。
  - **Ghost Actor**([`../extensions/applet-integration.md`](../extensions/applet-integration.md)):Applet 管辖 namespace 下的外部 / 集成 actor 镜像或 Applet 托管 automation。`actor_id` / Actor Profile `principal_id` MUST 是无 fragment 的 DID；DID URL fragment 只用于 `verification_method`。其 `accountable_principal_ids` 指向 Applet controller / 外部系统；生命周期由 Applet registration 管理。
- **Agent 三轴正交（normative）**:Native Personal Agent 的可用性由三条互不替代的轴共同决定——controller lifecycle 意图(`active | paused | deactivated`,仅 controller 写入)、派生 runtime key 就绪度 `runtime_state`(`pending_runtime_key | ready | replacing | pairing_expired`,由 key/pairing 事实派生，见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))、以及 admission 时点的 MLS KeyPackage 池可领取性。lifecycle `active` 不能替代 runtime 就绪,`runtime_state=ready` 不能替代 MLS readiness;encrypted Realm membership admission MUST 继续要求可领取 KeyPackage,任何一轴都不得被另一轴的检查省略。
- **Realm membership 从属性（normative）**：Native Personal Agent 的 Realm membership 是独立的 `ak.member.state`，但其有效性从属于 controller 在同一 Realm 的 active `join`。controller 已是 active member 时，MAY 直接把自己控制且 lifecycle 为 `active` 的 Native Personal Agent 从 `leave` 转为 `join`；该动作是 controller 对受控 principal 的显式授权，不是发给 agent runtime 的邀请，因此 MUST NOT 创建 pending invite、MUST NOT 要求 agent opt-in，也 MUST NOT 走 `ak.invite.accept`。Reducer MUST 校验 active provisioning state、`ak.identity.accountability_grant`、Realm native-agent policy、join policy 与 E2EE/MLS admission；仅凭 `accountable_principal_ids` 字面声明不得放行。普通成员不得用此路径加入其他 controller 的 agent 或任意第三方 principal。
- **无主残留禁止（normative）**：Native Personal Agent MUST NOT 在 controller 已不再是同一 Realm active member 时继续保持 `join`。controller 的 membership 从 `join` 转为 `leave` 或 `ban` 时，reducer / service MUST 在同一接受事务或可验证的强制 cascade 中，把该 controller 在此 Realm 中仍为 `join` 的所有 Native Personal Agents 转为 `leave`，reason=`controller_membership_ended`，并触发对应 Circle、delivery 与 MLS Remove cascade。该 cascade 不自动恢复；controller 后续重新加入时必须重新显式添加 agent。
- `agent_slug` 只为 native personal agent 的 **controller-scoped mention selector** 服务。它与 controller handle 组合成输入 token `@<controller-handle>/<agent_slug>`，发送前必须解析为 agent `principal_id`。权威绑定来自 `ak.schema.agent_selector_claim.v1`，而不是 DID path 或 Actor Profile 字面值；Actor Profile 上的 `agent_slug` 只是 list/get、roster、mention picker 可用的投影 hint。`agent_slug` 本身 MUST NOT 进入 grant subject、actor attribution、membership key、delivery decision、公开 Directory search/list key 或 audit attribution。Reducer / profile projection 在同一 verified controller principal 下发现多个 active native personal agents 使用同一有效 selector claim 时，MUST 把该 selector 解析为 ambiguous 并 fail closed；实现 MAY 拒绝造成冲突的 `ak.profile.create` / `ak.profile.update` 或 selector claim。`agent_slug` 变化只影响未来输入解析，历史 mention 仍按已持久化的 `subject_id` 指向原 agent。
- Event Envelope 在 reducer 接受时 stamp `actor_kind` projection(见 [`event-and-patch.md`](./event-and-patch.md) §2.2),让审计 / 取证 / offline reader 不必反向解析 Actor Profile 即可分类 event。该字段是 reducer-managed immutable,actor 提交侧 MUST NOT 携带。

### 3.3.1 `accountable_principal_ids` 的可验证性（normative）

`accountable_principal_ids` 是社工攻击面: actor 可以单方填入 `accountable_principal_ids: ["did:webvh:z6shM8wDREPSST7ZtxGkuFsk6:famous-org.example"]`,让其他客户端 / Directory UI 显示 "由 famous-org 担保" 的暗示信任，即便 famous-org 从未批准过。这对接收方做出"是否互动 / 是否接受邀请"的判断有真实影响。

因此 reducer **MUST** 校验:

1. 写入 / 更新 `Actor Profile.accountable_principal_ids[]` 的 Event 提交时,reducer MUST 解析数组中**每个** DID,并检查是否存在已 sealed 的 `ak.identity.accountability_grant` event,其 `issuer = <该 DID>`、`subject = profile.principal_id`、`grant_status = "active"`、`not_before <= now`,且若声明了 `expires_at` 则 `now <= expires_at`。
2. 不存在对应 grant 的 DID 条目 MUST 被 reducer 从 accountable_principal_ids 中剔除(或整个 Event 以 `failed_precondition` reason=`accountability_grant_missing` 拒绝；部署 policy 可选其一，默认推荐"剔除 + audit log",见下方)。
3. accountability grant 被签发方 revoke 后,reducer **SHOULD** 在 freshness 窗口(默认 ≤ 1 小时)内把对应 actor profile 的 `accountable_principal_ids[]` 中该条目降级为 `unverified`(projection 层标记),并在下次 actor profile update 时移除。

**Profile-visible 选择**：deployment 若需要让选择 wire-visible，可声明 `ak.profile.accountable_principals.strict_reject.v1` profile（整 Realm 走 reject 路径，而非默认"strip + audit log"）；该 profile 在 [`../conformance/conformance-profiles.md` §17](../conformance/conformance-profiles.md) 与 `artifacts/profiles/conformance-profiles.json` 注册。

`ak.identity.accountability_grant` 字段:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `issuer` | did | 签发 accountability 担保的主体(`accountable_principal_ids[]` 中被声明的 DID) |
| `subject` | did | 被担保的 actor principal(actor profile 的 `principal_id`) |
| `accountability_scope` | string \| array | 非空、无重复、无顺序语义的闭合集合（`employment` / `contracted_service` / `agent_operator`）；string 是 singleton set 的 wire 写法；仅供 UI 与 governance 展示，不参与授权 |
| `not_before` | timestamp | 担保起始时间 |
| `expires_at` | timestamp（可选） | 担保到期；过期后视作 unverified。缺省表示不设时间过期，由 `grant_status` 撤销与 controller lifecycle 级联治理;native personal agent 的 controller 自担保 SHOULD 缺省不声明 `expires_at`,避免静默失效悬崖（见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md)） |
| `grant_status` | enum(active, revoked) | issuer 主动 revoke 改为 `revoked` |
| `proof` | object | 由 `issuer` 的 active authentication key 签发 |

完整机读形态由 [`accountability-grant.schema.json`](../../artifacts/schemas/accountability-grant.schema.json) 权威定义；payload 的 `schema` MUST 为 `ak.schema.accountability_grant.v1`。`proof.payload_digest` MUST 覆盖 `utf8("ak.accountability-grant-v1\n") || canonical_json(payload with proof omitted)`，且 verification method controller MUST 等于 `issuer`。

`accountability_scope` 的 array 顺序不表达优先级、时间或授权强度；receiver MUST 接受合法 singleton array 与任意合法排列，且只在 cell subject 派生、领域相等比较和 projection 聚合时按 [`encoding.md` §9.5.1](../conformance/encoding.md) 的 canonical string-set 规则规范化，不得重写已签名 payload bytes。Canonical authoring API 对新 Event MUST 将单元素集合输出为 string，多元素集合按原始 UTF-8 bytes 升序输出为 array。

Accountability 状态按 `(issuer, subject, normalized exact scope set)` 独立定址。同一 exact set 的 `active` 与 `revoked` 必须写入同一 cell；revoke 必须携带与被撤销 grant 完全相同的集合，子集 revoke 不表示从超集中做差集。若只需保留原集合的一部分，issuer 必须先 revoke 原 exact set，再签发目标 exact set。多个 exact-set cell 可同时 active；projection 展示的 active scopes 是这些 cell 的集合并集，撤销其中一个不得影响其它 cell。只要至少一个未过期的 active exact-set cell 存在，该 issuer/subject accountability 关系仍可验证。

**UI / projection 责任**:

- 客户端 UI **MUST** 把 `accountable_principal_ids[]` 中已校验通过的 DID 与 unverified(grant 缺失 / 过期 / revoked)的 DID 以可感知、可测试的 presentation invariant 区分；具体文案、图形、隐藏策略或控件形式属于实现自由，但 verified 与 unverified 两种状态不得在同一上下文中呈现为等价信任暗示。
- 客户端 UI **MUST NOT** 仅根据 actor profile 字面值显示信任暗示。
- Directory / Search 投影把 `accountable_principal_ids` 作为过滤条件时 MUST 只对 verified 条目生效。

**Why**: 没有这层校验时,actor 可以伪造任意大型组织或知名实体作为"担保人",借此社工诱导对端；有了 grant-based 校验，虚假声明会被 reducer 剔除,UI 不会显示信任暗示。

## 4. 跨链路引用对照

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Cursor、Notification | 直接执行该 Event / 拥有该私有状态的 actor DID。 |
| `principal_id` | Actor Profile | Profile 对应的 principal DID；权限根。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。 |
| `accountable_principal_ids` | Actor Profile | Agent / 托管账号的责任主体；不传染 capability。 |

完整跨字段对照见 [common-fields.md §4](./common-fields.md)。

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
