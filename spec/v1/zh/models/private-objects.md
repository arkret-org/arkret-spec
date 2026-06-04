---
title: Private & Derived Objects
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Cokret 协作图中的**派生 / actor-private 对象**：

- **Read Cursor**：actor 私有的已读位置状态。
- **Notification**：从 Event / Flow / Message / Relation 派生的 inbox projection。

这些对象**不是 canonical truth**——它们由 client / SDK 从 Event 集合本地计算；schema 仅用于 wire 表示。它们不进入协作图归约，不向其他 actor 广播持久化共享对象。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Read Cursor

### 2.1 概念

`read_cursor` 是 actor-private 状态。它 SHOULD 存在于私有 account data 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

完整 read receipt / read cursor 同步规则、`ck.receipt.read` 的 disclosure 选项和高频更新策略见 [`../discovery/read-receipts.md`](../discovery/read-receipts.md)。

### 2.2 Schema 与字段

Schema id: `ck.schema.read_cursor.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:read_cursor` | `ck:read_cursor:<uuidv7>`。 | 私有状态 ID。 |
| `schema` | yes | `ck.schema.read_cursor.v1` |  | Schema ID。 |
| `actor_id` | yes | `did` | 只对该 actor 生效。 | 读取主体。 |
| `realm_id` | yes | `id:realm` |  | Realm。 |
| `read_scope` | yes | `object` | `{kind, ref?, track_name?}`。`kind ∈ enum(realm, circle, space, flow)`。ref 必填规则：`kind=realm` 时 `ref` MUST 省略（范围即本对象 `realm_id`）；`kind=circle` 时 `ref` MUST 是 `id:circle`；`kind=space` 时 `ref` MUST 是 `id:space`；`kind=flow` 时 `ref` MUST 是 `id:flow`。`track_name` 仅在 `kind=flow` 时 MAY 出现（限定到该 Flow 的某个 track 时间线，省略表示整个 Flow）；其余 kind MUST 省略 `track_name`。 | 已读范围。 |
| `position` | yes | `object` | `{event_id, hlc}`。 | 已读位置。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

### 2.3 行为规则

- Read marker MUST NOT 作为持久化共享对象写入 Event 链；它属于 ephemeral / actor-private 范畴（详见 [flow-and-message.md §9.6](./flow-and-message.md)）。
- Flow 时间线与父 Realm 在 read receipt policy 上需要分离时，整个 Flow 通过 `Flow.scope_circle_id` 落在一个 [Circle](./circle.md)（参见 [flow-and-message.md §5](./flow-and-message.md)）；effective policy 由 Circle 自身策略与父 Realm `ck.realm.read_receipt_policy` 取更严格者。Track 级别 override 不在 v1 范围内。

## 3. Notification

### 3.1 概念

`notification` SHOULD 是从 Event / Flow / Message / Relation 派生的 inbox projection，**不是 canonical truth**。它面向单个 actor 的 inbox / push pipeline，不参与协作图归约。

完整推送规则、push gateway、E2EE 脱敏推送策略见 [`../discovery/push-notifications.md`](../discovery/push-notifications.md)。

### 3.2 Schema 与字段

Schema id: `ck.schema.notification.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:notification` | `ck:notification:<uuidv7>`。 | 通知 ID。 |
| `schema` | yes | `ck.schema.notification.v1` |  | Schema ID。 |
| `actor_id` | yes | `did` | 接收者。 | 通知主体。 |
| `realm_id` | no | `id:realm` |  | 来源 Realm。 |
| `source_event_id` | yes | `id:event` |  | 来源事件。 |
| `notification_type` | yes | `enum(mention, reply, assignment, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` | Notification projection-state 例外；表示 inbox/read 状态，不表示 canonical object 物理 lifecycle。 | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 行为规则

- Notification 是派生 projection；客户端 / 服务端 SHOULD 从 source event + actor preferences 计算，不要把它当作独立真相源持久化为 durable canonical event。
- E2EE Realm 中 `preview` 必须由发送者客户端脱敏后置入推送 envelope；服务端不得用明文重新生成 preview。
- `notification_type=applet` / `agent` / `policy` / `moderation` 等扩展类型的语义见 [`../extensions/applet-integration.md`](../extensions/applet-integration.md)、[`../extensions/agent-protocol-interop.md`](../extensions/agent-protocol-interop.md)、[`../authz/policy-server.md`](../authz/policy-server.md) 与 [`../governance/content-moderation.md`](../governance/content-moderation.md)。

### 3.4 Mention notification 派生

`notification_type=mention` 覆盖普通 direct mention 与 audience mention（例如 `@all` / `@here`）。派生器 MUST 遵守 [`flow-and-message.md` §9.4](./flow-and-message.md)：

- Direct mention 以结构化节点的 `subject_id` 为目标；audience mention 先按 source event causal frontier、Message effective scope、Realm / Circle policy 与可见性规则展开 receiver set。`flow_watchers` / `flow_engaged` audience 的 watcher 命中由完整 effective watch level 计算，但只作为 receiver-side fanout 条件。
- 对同一 `(actor_id, source_event_id, notification_type)` MUST 去重。一个 Message 中重复 direct mention、direct mention 与 audience mention 同时命中、或 watch / reply / assignment 叠加命中，都不得在同一 push delivery window 内产生多次 wakeup。
- `actor_id` MUST 是接收 notification 的 actor，而不是发送者。默认发送者自 mention 不产生 notification，除非该 actor 的私有 push rule 显式 opt-in。
- 派生器 MUST 在生成 notification 前应用 access check、history visibility、`level=muted`、blocklist、DND 与 push rule 覆盖；无访问权或被静音时不得留下可查询的 notification stub。
- 派生器、delivery response、inbox projection 与 push payload MUST NOT 暴露 audience 展开结果、recipient count、watcher 列表、watch level 或命中原因；sender 不得区分某 receiver 是因历史参与、watch 还是 direct mention 命中。
- `preview` 在 E2EE / redaction / history-limited 场景下 MUST 为空或使用已授权的脱敏摘要；不得因为 notification projection 需要展示而扩大源 Message 的明文可见性。

## 4. 与 Account Data 的关系

Read marker 与个人通知偏好、saved view personalization、列宽 / 折叠等本地状态都属于 **actor-private account data** 类别。完整 account data 模型、私有标签、个人 blocklist 见 [`../discovery/client-preferences.md`](../discovery/client-preferences.md)。

### 4.1 Agent draft 与 sidecar projection account data

两类 controller-owned encrypted account data 类型在 `ck.agent.*` 命名空间下:

- **`ck.agent.draft.v1`**:agent 通过 `ck.agent.draft.propose` / `ck.agent.action_request`(actor_private_event)提议候选内容,Principal Server 通过 capability / policy / accountability / risk check 后,materialize 为 controller-owned `ck.agent.draft.v1` account-data。Key pattern 建议 `ck.agent.draft.v1:<agent_principal_id>:<draft_id>`,声明 `encrypted_at_rest=true`、tombstone 与 retention 规则。Draft MUST NOT 作为 `ck.message.create` / `ck.flow.create` 或任何 `wire_scope=durable_event` 进入目标 Realm 共享历史。Draft 引用目标 `realm_id` / `flow_id` / `message_id` 不授予目标 Realm 成员读取 draft 内容的权利。
- **`ck.agent.sidecar_projection.v1`**:controller-private UI projection,跨设备同步 "My AI" tab 顺序、pin / 折叠状态、addressed agents list 等。Key pattern `ck.agent.sidecar_projection.v1:<controller_principal_id>:<target_realm_id>:<target_flow_id>`。它**不**修改目标 Flow `tracks` map,不写入 target metadata / target-side Relation / watch cell / unread cell / search index / notification state。

二者 key 前缀不同、key 第二段语义不同(controller vs agent),不会在 `ck.agent.*` 命名空间下冲突。注册时 MUST 在 `account-data-type-registry.json` 显式声明 key pattern 与 owner principal,reducer 据此做归属校验。

### 4.2 隐私边界(normative)

针对上述 agent-attributed private state:

- 存储 MUST 使用 `wire_scope=actor_private_event` 通道(encrypted account data 或 actor-private stream);不得进入 shared Realm Move / Anchor history。
- 目标 Realm 的 `ck.events.subscribe` / `ck.events.query` / shared reducer / Realm search index / notification fanout / push preview MUST NOT 返回 draft 或 sidecar projection 内容。
- `ck.account.subscribe` 只能把 controller-owned approval draft / sidecar projection 返回给 controller principal 的授权 session,以及 scope 明确包含该 account-data 访问权的 agent runtime。
- 若服务端存储明文，该 deployment MUST 把"明文可见服务"写入 profile / policy 并向 controller 披露；默认语义 SHOULD 是服务端只保存 encrypted account data。
- Draft 发布到目标 Flow 时,shared event MAY 通过 `refs[].role="draft_source"` 携带 opaque digest,但明文 draft id、private metadata、scratchpad、private prompt 或历史版本 MUST NOT 泄露到共享历史。
- Sidecar 发布到目标 Flow 时,MUST NOT 泄露 sidecar `private_flow_id`、`private_circle_id`、private messages、scratchpad 或 draft history。

## 5. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Read receipts：[`../discovery/read-receipts.md`](../discovery/read-receipts.md)。
- Push notifications：[`../discovery/push-notifications.md`](../discovery/push-notifications.md)。
- Account data / 个人偏好：[`../discovery/client-preferences.md`](../discovery/client-preferences.md)。
- Profiles / presence：[`../discovery/profiles-presence.md`](../discovery/profiles-presence.md)。
