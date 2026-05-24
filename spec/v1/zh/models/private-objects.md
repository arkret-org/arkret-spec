---
title: Private & Derived Objects
---

## 1. 目标

本文集中定义 Contrix 协作图中的**派生 / actor-private 对象**：

- **Read Cursor**：actor 私有的已读位置状态。
- **Notification**：从 Event / Flow / Message / Relation 派生的 inbox projection。

这些对象**不是 canonical truth**——它们由 client / SDK 从 Event 集合本地计算；schema 仅用于 wire 表示。它们不进入协作图归约，不向其他 actor 广播持久化共享对象。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Read Cursor

### 2.1 概念

`read_cursor` 是 actor-private 状态。它 SHOULD 存在于私有 account data 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

完整 read receipt / read cursor 同步规则、`cx.receipt.read` 的 disclosure 选项和高频更新策略见 [`../discovery/read-receipts.md`](../discovery/read-receipts.md)。

### 2.2 Schema 与字段

Schema id: `cx.schema.read_cursor.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:read_cursor` | `cx:read_cursor:<uuidv7>`。 | 私有状态 ID。 |
| `schema` | yes | `cx.schema.read_cursor.v1` |  | Schema ID。 |
| `actor_id` | yes | `did` | 只对该 actor 生效。 | 读取主体。 |
| `realm_id` | yes | `id:realm` |  | Realm。 |
| `scope` | yes | `object` | `{kind, ref?, track?}`；`kind=realm` 时 `ref` 省略，其余 kind 必填对应对象 ref。 | 已读范围。 |
| `position` | yes | `object` | `{event_id, hlc}`。 | 已读位置。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

### 2.3 行为规则

- Read marker MUST NOT 作为持久化共享对象写入 Event 链；它属于 ephemeral / actor-private 范畴（详见 [flow-and-message.md §9.6](./flow-and-message.md)）。
- Discussion 时间线与源 Realm 在 read receipt policy 上需要分离时，必须把 discussion 升级为独立 linked Realm（参见 `Flow.discussion_realm_ref`，[flow-and-message.md §5](./flow-and-message.md)），由 linked Realm 自己声明 `cx.realm.read_receipt_policy`；track 级别 override 不在 v1 范围内。

## 3. Notification

### 3.1 概念

`notification` SHOULD 是从 Event / Flow / Message / Relation 派生的 inbox projection，**不是 canonical truth**。它面向单个 actor 的 inbox / push pipeline，不参与协作图归约。

完整推送规则、push gateway、E2EE 脱敏推送策略见 [`../discovery/push-notifications.md`](../discovery/push-notifications.md)。

### 3.2 Schema 与字段

Schema id: `cx.schema.notification.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:notification` | `cx:notification:<uuidv7>`。 | 通知 ID。 |
| `schema` | yes | `cx.schema.notification.v1` |  | Schema ID。 |
| `actor_id` | yes | `did` | 接收者。 | 通知主体。 |
| `realm_id` | no | `id:realm` |  | 来源 Realm。 |
| `source_event_id` | yes | `id:event` |  | 来源事件。 |
| `notification_type` | yes | `enum(mention, reply, assignment, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` |  | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 行为规则

- Notification 是派生 projection；客户端 / 服务端 SHOULD 从 source event + actor preferences 计算，不要把它当作独立真相源持久化为 durable canonical event。
- E2EE Realm 中 `preview` 必须由发送者客户端脱敏后置入推送 envelope；服务端不得用明文重新生成 preview。
- `notification_type=applet` / `agent` / `policy` / `moderation` 等扩展类型的语义见 [`../extensions/applet-integration.md`](../extensions/applet-integration.md)、[`../extensions/agent-protocol-interop.md`](../extensions/agent-protocol-interop.md)、[`../authz/policy-server.md`](../authz/policy-server.md) 与 [`../governance/content-moderation.md`](../governance/content-moderation.md)。

## 4. 与 Account Data 的关系

Read marker 与个人通知偏好、saved view personalization、列宽 / 折叠等本地状态都属于 **actor-private account data** 类别。完整 account data 模型、私有标签、个人 blocklist 见 [`../discovery/client-preferences.md`](../discovery/client-preferences.md)。

## 5. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Read receipts：[`../discovery/read-receipts.md`](../discovery/read-receipts.md)。
- Push notifications：[`../discovery/push-notifications.md`](../discovery/push-notifications.md)。
- Account data / 个人偏好：[`../discovery/client-preferences.md`](../discovery/client-preferences.md)。
- Profiles / presence：[`../discovery/profiles-presence.md`](../discovery/profiles-presence.md)。
