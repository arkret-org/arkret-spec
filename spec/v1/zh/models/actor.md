---
title: Actor & Actor Profile
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Actor 是 Cokret 协作图中"能执行动作的主体"。Actor identity 的根由 DID 定义；为了让 Actor 能在协作图中被 mention、被 assign、被展示，它 MAY 拥有对应的 `actor_profile` 标准对象。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。Actor 与 Capability、Identity 体系的交互见 [`../identity/identity-did.md`](../identity/identity-did.md) 与 [`../authz/capabilities.md`](../authz/capabilities.md)。

## 2. Actor 概览

协议中的 actor identity 根由 DID 定义。

Actor 类型（`actor_kind`）：

- `user`
- `org`
- `team`
- `agent`
- `service`
- `device`
- `integration`

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

Schema id: `cx.schema.actor_profile.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:actor_profile` | Actor Profile 是标准对象。 | Profile 对象 ID。 |
| `realm_id` | no | `id:realm` | 全局 profile 可省略。 | 所属 Realm。 |
| `principal_id` | yes | `did` | 权限仍以 DID/capability 为准。 | Principal DID。 |
| `actor_kind` | yes | `enum(user, org, team, agent, service, device, integration)` |  | Actor 类型。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, soft_logged_out, locked, suspended, deactivated, erasure_pending)` | 账户生命周期 status 的 public projection，不复用 [`common-fields.md` §5](./common-fields.md) 的对象通用 state；具体语义、转移与允许的写入主体见 [`../identity/account-lifecycle.md` §3](../identity/account-lifecycle.md)。 | 状态。 |
| `accountable_principal_ids` | no | `array<did>` | agent/托管账号 SHOULD 设置；每个 DID 必须由对应 `cx.identity.accountability_grant` 背书，详见 §3.3.1。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 `principal_id` 与 `actor_kind` 的语义

`principal_id` 是授权、签名和审计归属的根；`actor_kind` 只是该 DID 在协作图中的展示和策略分类。

- `actor_kind="device"`：表示该 DID 被作为设备级或 pairwise device principal 直接行动；若设备只是某个用户/组织 principal 的授权设备，则 Event 仍以用户/组织 DID 作为 `actor_id`，设备身份通过 proof `verification_method`、`device_id`、`cx.device.authorize` 或 session grant 表达。
- `team`、`agent`、`service` 和 `integration` MAY 使用独立 DID，也 MAY 由 `accountable_principal_ids` 指向控制/责任 principal；它们不会因为 `accountable_principal_ids` 自动继承权限。
- `actor_kind` 的 wire enum 不包含 `agent_native`、`agent_ghost` 或 `ghost`。Native personal agent 使用 `actor_kind="agent"`，并由 CXP-0008 provisioning state 区分；Applet-managed Ghost Actor 使用现有 enum 中最贴合其主体类型的值（外部人类/账号镜像 SHOULD 使用 `integration`，Applet 托管 AI/automation MAY 使用 `agent`）。Realm policy 必须能通过 Applet provenance、`accountable_principal_ids` / `accountability`、profile 与 capability 分别控制 native personal agent 与 Applet / Ghost Actor，不得合并为单一 "automation allowed" 开关：
  - **Native personal agent**(CXP-0008):由 controller 通过 `cx.agent.provision` 直接创建的一等 Cokret actor principal,拥有独立 DID document、`cx.identity.accountability_grant` 指向 controller、`cx.agent.key.authorize` 绑定的运行时 key。可被 mention / grant / revoke / pause / deactivate。
  - **Ghost Actor**([`../extensions/applet-integration.md`](../extensions/applet-integration.md)):Applet 管辖 namespace 下的外部 / 集成 actor 镜像或 Applet 托管 automation。`actor_id` / Actor Profile `principal_id` MUST 是无 fragment 的 DID；DID URL fragment 只用于 `verification_method`。其 `accountable_principal_ids` / `accountability` 指向 Applet controller / 外部系统；生命周期由 Applet registration 管理。
- Event Envelope 在 reducer 接受时 stamp `actor_kind` projection(见 [`event-and-patch.md`](./event-and-patch.md) §2.2),让审计 / 取证 / offline reader 不必反向解析 Actor Profile 即可分类 event。该字段是 reducer-managed immutable,actor 提交侧 MUST NOT 携带。

### 3.3.1 `accountable_principal_ids` 的可验证性（normative）

`accountable_principal_ids` 是社工攻击面: actor 可以单方填入 `accountable_principal_ids: ["did:web:famous-org.example"]`,让其他客户端 / Directory UI 显示 "由 famous-org 担保" 的暗示信任，即便 famous-org 从未批准过。这对接收方做出"是否互动 / 是否接受邀请"的判断有真实影响。

因此 reducer **MUST** 校验:

1. 写入 / 更新 `Actor Profile.accountable_principal_ids[]` 的 Event 提交时,reducer MUST 解析数组中**每个** DID,并检查是否存在已 anchored 的 `cx.identity.accountability_grant` event,其 `issuer = <该 DID>`、`subject = profile.principal_id`、`grant_status = "active"`、`not_before <= now <= expires_at`。
2. 不存在对应 grant 的 DID 条目 MUST 被 reducer 从 accountable_principal_ids 中剔除(或整个 Event 以 `failed_precondition` reason=`accountability_grant_missing` 拒绝；部署 policy 可选其一，默认推荐"剔除 + audit log",见下方)。
3. accountability grant 被签发方 revoke 后,reducer **SHOULD** 在 freshness 窗口(默认 ≤ 1 小时)内把对应 actor profile 的 `accountable_principal_ids[]` 中该条目降级为 `unverified`(projection 层标记),并在下次 actor profile update 时移除。

**Profile-visible 选择**：deployment 若需要让选择 wire-visible，可声明 `cx.profile.accountable_principals.strict_reject.v1` profile（整 Realm 走 reject 路径，而非默认"strip + audit log"）；该 profile 在 [`../conformance/conformance-profiles.md` §17](../conformance/conformance-profiles.md) 与 `artifacts/profiles/conformance-profiles.json` 注册。

`cx.identity.accountability_grant` 字段:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `issuer` | did | 签发 accountability 担保的主体(`accountable_principal_ids[]` 中被声明的 DID) |
| `subject` | did | 被担保的 actor principal(actor profile 的 `principal_id`) |
| `scope` | string \| array | 担保范围(例如 `"employment"` / `"contracted_service"` / `"agent_operator"`);仅供 UI 与 governance 展示，不参与授权 |
| `not_before` | timestamp | 担保起始时间 |
| `expires_at` | timestamp | 担保到期；过期后视作 unverified |
| `grant_status` | enum(active, revoked) | issuer 主动 revoke 改为 `revoked` |
| `proof` | object | 由 `issuer` 的 active authentication key 签发 |

**UI / projection 责任**:

- 客户端 UI **MUST** 把 `accountable_principal_ids[]` 中已校验通过的 DID 与 unverified(grant 缺失 / 过期 / revoked)的 DID 在视觉上严格区分(例如 verified 显示 "由 X 担保" 加 verified 图标,unverified 显示 "声明可问责到 X(未验证)" 加 warning 图标或完全隐藏)。
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
- **Membership state event**（`cx.member.state`）：表达"谁在 Realm"，详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- **Identity claim / handle**：表达"对外可发现身份"，详见 [`../identity/identity-handles.md`](../identity/identity-handles.md)。

`actor_profile` 只是上述结构在 UI 层的展示镜像。

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- DID / identity：[`../identity/identity-did.md`](../identity/identity-did.md)。
- Handles / claim：[`../identity/identity-handles.md`](../identity/identity-handles.md)。
- 账户 lifecycle：[`../identity/account-lifecycle.md`](../identity/account-lifecycle.md)。
- Capability：[`../authz/capabilities.md`](../authz/capabilities.md)。
- Actor Profile schema：`artifacts/schemas/actor-profile.schema.json`。
