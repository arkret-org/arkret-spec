---
title: Actor & Actor Profile
---

## 1. 目标

Actor 是 Contrix 协作图中"能执行动作的主体"。Actor identity 的根由 DID 定义；为了让 Actor 能在协作图中被 mention、被 assign、被展示，它 MAY 拥有对应的 `actor_profile` 标准对象。

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
| `space_id` | no | `id:space` | 全局 profile 可省略。 | 所属 Space。 |
| `principal_id` | yes | `did` | 权限仍以 DID/capability 为准。 | Principal DID。 |
| `actor_kind` | yes | `enum(user, org, team, agent, service, device, integration)` |  | Actor 类型。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, suspended, deactivated, deleted)` | 账户生命周期独有的状态集，不复用 [`common-fields.md` §5](./common-fields.md) 的对象通用状态机；具体语义、转移与允许的写入主体见 [`../identity/account-lifecycle.md` §3](../identity/account-lifecycle.md)。 | 状态。 |
| `accountable_to` | no | `array<did>` | agent/托管账号 SHOULD 设置。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 `principal_id` 与 `actor_kind` 的语义

`principal_id` 是授权、签名和审计归属的根；`actor_kind` 只是该 DID 在协作图中的展示和策略分类。

- `actor_kind="device"`：表示该 DID 被作为设备级或 pairwise device principal 直接行动；若设备只是某个用户/组织 principal 的授权设备，则 Event 仍以用户/组织 DID 作为 `actor_id`，设备身份通过 proof `verification_method`、`device_id`、`cx.device.authorized` 或 session grant 表达。
- `team`、`agent`、`service` 和 `integration` MAY 使用独立 DID，也 MAY 由 `accountable_to` 指向控制/责任 principal；它们不会因为 `accountable_to` 自动继承权限。

## 4. 跨链路引用对照

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Marker、Notification | 直接执行该 Event / 拥有该私有状态的 actor DID。 |
| `principal_id` | Actor Profile | Profile 对应的 principal DID；权限根。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。 |
| `accountable_to` | Actor Profile | Agent / 托管账号的责任主体；不传染 capability。 |

完整跨字段对照见 [common-fields.md §4](./common-fields.md)。

## 5. Actor 与协作图

Actor 在协作图中通过：

- **Capability Grant**（[`governance-objects.md`](./governance-objects.md)）：表达"谁能做什么"。
- **Relation `assigned_to` / `mentions`**：表达"谁参与 / 被 cue"。
- **Membership state event**（`cx.member.state`）：表达"谁在 Space"，详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- **Identity claim / handle**：表达"对外可发现身份"，详见 [`../identity/identity-handles.md`](../identity/identity-handles.md)。

`actor_profile` 只是上述结构在 UI 层的展示镜像。

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- DID / identity：[`../identity/identity-did.md`](../identity/identity-did.md)。
- Handles / claim：[`../identity/identity-handles.md`](../identity/identity-handles.md)。
- 账户 lifecycle：[`../identity/account-lifecycle.md`](../identity/account-lifecycle.md)。
- Capability：[`../authz/capabilities.md`](../authz/capabilities.md)。
- Actor Profile schema：`artifacts/schemas/actor-profile.schema.json`。
