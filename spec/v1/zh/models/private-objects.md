---
title: Private & Derived Objects
status: candidate
normative: true
stability: v1
updated: 2026-06-24
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Cokret 协作图中的**派生 / actor-private 对象**：

- **Read Cursor**：actor 私有的已读位置状态。
- **Notification**：从 Event / Strand / Message / Relation 派生的 inbox projection。

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
| `device_id` | yes | `id:device` | `ck:device:<uuidv7>`。多设备收敛 tiebreaker。 | 来源设备。 |
| `realm_id` | yes | `id:realm` |  | Realm。 |
| `read_scope` | yes | `object` | `{kind, ref?, track_name?}`。`kind ∈ enum(realm, circle, space, strand, thread)`。ref 必填规则：`kind=realm` 时 `ref` MUST 省略（范围即本对象 `realm_id`）；`kind=circle` 时 `ref` MUST 是 `id:circle`；`kind=space` 时 `ref` MUST 是 `id:space`；`kind=strand` 时 `ref` MUST 是 `id:strand`；`kind=thread` 时 `ref` MUST 是 Thread 根消息的 `id:message`（Thread 是 root message 回复子时间线的投影选择器，不是一等协议对象，已读隔离语义见 [`../discovery/read-receipts.md` §5](../discovery/read-receipts.md)）。`track_name` 仅在 `kind=strand` 时 MAY 出现（限定到该 Strand 的某个 track 时间线，省略表示整个 Strand）；其余 kind MUST 省略 `track_name`。Read Receipt 的 `read_scope` 与本字段共享同一 discriminator 族，但**两者的 `kind` 取值集合并不相交一致**：Read Cursor 支持 `realm` / `circle` / `space` / `strand` / `thread`，Read Receipt 另支持 `view` / `message` / `morph` 但**不**支持 `circle` / `space`。因此 SDK / 实现 **MUST** 按各自 schema 分别校验 `read_scope.kind`，**MUST NOT** 共用单一 enum 类型（共用会让 `circle` 误用于 Receipt、或 `message` 误用于 Cursor 等错配静默通过）；以各自 schema 为字段形状权威。跨对象 kind 可引用类别的机读真相源是 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `referenceability`：本字段使用 `read_cursor_scope_kind`、`read_cursor_scope_ref` 与 `read_cursor_thread_root` 类别。 | 已读范围。 |
| `position` | yes | `object` | `{event_id, hlc}`。 | 已读位置。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

### 2.3 行为规则

- Read marker MUST NOT 作为持久化共享对象写入 Event 链；它属于 ephemeral / actor-private 范畴（详见 [strand-and-message.md §9.6](./strand-and-message.md)）。
- 多设备并发更新同一 `(actor_id, realm_id, read_scope)` 时，接收方取 HLC 更大者收敛;HLC 相等时按 `device_id` 作 actor 域内确定性 tiebreaker(见 [`../discovery/read-receipts.md` §6.6](../discovery/read-receipts.md))。
- Strand 时间线与父 Realm 在 read receipt policy 上需要分离时，整个 Strand 通过 `Strand.scope_circle_id` 落在一个 [Circle](./circle.md)（参见 [strand-and-message.md §5](./strand-and-message.md)）；effective policy 由 Circle 自身策略与父 Realm `ck.realm.read_receipt_policy` 取更严格者。Track 级别 override 不在 v1 范围内。

## 3. Notification

### 3.1 概念

`notification` SHOULD 是从 Event / Strand / Message / Relation 派生的 inbox projection，**不是 canonical truth**。它面向单个 actor 的 inbox / push pipeline，不参与协作图归约。

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
| `source_ref` | no | `id:(message\|strand\|morph\|relation\|view\|blob)` | 取值形如 `ck:(message\|strand\|morph\|relation\|view\|blob):…`，union 枚举即此 6 类。render-only hint;reducer MUST 以 `source_event_id` 为权威。**子集差异（informative）**：本字段允许的 kind 子集与 Relation 端点（[`relation.md` §1](./relation.md)，端点另允许 `realm` / `space` / `actor_profile` / `event` / DID）、Read Cursor `read_scope`（§2.2，scope 限 `realm` / `circle` / `space` / `strand` / `thread`）各自不同；差异由各自语义决定（Notification 渲染目标 = 可被通知指向的内容对象；Relation 端点 = 可连边的图节点；Read Cursor scope = 可定位已读位置的时间线容器）。三处实现 MUST 按各自 schema 校验字段形状，同时以 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `referenceability` 作为 kind 子集的机读真相源；本字段对应 `notification_source` 类别。 | 可选 canonical 对象引用，供客户端直接渲染通知目标。 |
| `strand_id` | no | `id:strand` |  | 可选 Strand 上下文，用于路由通知。 |
| `track_name` | no | `string` | `^[a-z][a-z0-9_]{0,63}$`。 | 可选，来源 Strand 上的 track key。 |
| `notification_type` | yes | `enum(message, mention, reply, assignment, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` | Notification projection-state 例外；表示 inbox/read 状态，不表示 canonical object 物理 lifecycle。 | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 行为规则

- Notification 是派生 projection；客户端 / 服务端 SHOULD 从 source event + actor preferences 计算，不要把它当作独立真相源持久化为 durable canonical event。
- E2EE Realm 中 `preview` 必须由发送者客户端脱敏后置入推送 envelope；服务端不得用明文重新生成 preview。
- `notification_type=message` 表示普通 `ck.message.create` 在接收者 effective watch / push rule 允许普通消息提醒时产生的 inbox / push 提醒；默认 `mentions_only` 不得为非定向普通消息产生该类型。当同一 source event 对同一 actor 同时命中 `mention`、`reply`、`assignment` 等更具体原因时，dispatcher MUST NOT 额外产生重复的 `message` notification。
- `notification_type=applet` / `agent` / `policy` / `moderation` 等扩展类型的语义见 [`../extensions/applet-integration.md`](../extensions/applet-integration.md)、[`../extensions/agent-protocol-interop.md`](../extensions/agent-protocol-interop.md)、[`../authz/policy-server.md`](../authz/policy-server.md) 与 [`../governance/content-moderation.md`](../governance/content-moderation.md)。

### 3.4 Mention notification 派生

`notification_type=mention` 覆盖普通 direct mention 与 audience mention（例如 `@all` / `@here`）。派生器 MUST 遵守 [`strand-and-message.md` §9.4](./strand-and-message.md)：

- Direct mention 以结构化节点的 `subject_id` 为目标；audience mention 先按 source event causal frontier、Message effective scope、Realm / Circle policy 与可见性规则展开 receiver set。`strand_watchers` / `strand_engaged` audience 的 watcher 命中由完整 effective watch level 计算，但只作为 receiver-side fanout 条件。
- 对同一 `(actor_id, source_event_id, notification_type)` MUST 去重。一个 Message 中重复 direct mention、direct mention 与 audience mention 同时命中、或 watch / reply / assignment 叠加命中，都不得在同一 push delivery window 内产生多次 wakeup。
- `actor_id` MUST 是接收 notification 的 actor，而不是发送者。默认发送者自 mention 不产生 notification，除非该 actor 的私有 push rule 显式 opt-in。
- 派生器 MUST 在生成 notification 前应用 access check、history visibility、`level=muted`、blocklist、DND 与 push rule 覆盖；无访问权或被静音时不得留下可查询的 notification stub。
- 派生器、delivery response、inbox projection 与 push payload MUST NOT 暴露 audience 展开结果、recipient count、watcher 列表、watch level 或命中原因；sender 不得区分某 receiver 是因历史参与、watch 还是 direct mention 命中。
- `preview` 在 E2EE / redaction / history-limited 场景下 MUST 为空或使用已授权的脱敏摘要；不得因为 notification projection 需要展示而扩大源 Message 的明文可见性。

## 4. 与 Account Data 的关系

Read marker 与个人通知偏好、saved view personalization、列宽 / 折叠等本地状态都属于 **actor-private account data** 类别。完整 account data 模型、私有标签、个人 blocklist 见 [`../discovery/client-preferences.md`](../discovery/client-preferences.md)。

### 4.1 Agent draft、sidecar projection 与 participation account data

三类 controller-owned encrypted account data 类型在 `ck.agent.*` 命名空间下:

- **`ck.agent.draft.v1`**:agent 通过 `ck.agent.draft.propose` / `ck.agent.action_request`(actor_private_event)提议候选内容,Principal Server 通过 capability / policy / accountability / risk check 后,materialize 为 controller-owned `ck.agent.draft.v1` account-data。Key pattern 建议 `ck.agent.draft.v1:<agent_principal_id>:<draft_id>`,声明 `encrypted_at_rest=true`、tombstone 与 retention 规则。Draft MUST NOT 作为 `ck.message.create` / `ck.strand.create` 或任何 `wire_scope=durable_event` 进入目标 Realm 共享历史。Draft 引用目标 `realm_id` / `strand_id` / `message_id` 不授予目标 Realm 成员读取 draft 内容的权利。
- **`ck.agent.sidecar_projection.v1`**:controller-private UI projection,跨设备同步 "My AI" tab 顺序、pin / 折叠状态、addressed agents list 等。Key pattern `ck.agent.sidecar_projection.v1:<controller_principal_id>:<target_realm_id>:<target_strand_id>`。它**不**修改目标 Strand `tracks` map,不写入 target metadata / target-side Relation / watch cell / unread cell / search index / notification state。
- **`ck.agent.participation.v1`**:controller-owned 的逐 scope agent 参与选择 `{reply, accept_third_party_mention, act_on_behalf}`。Key pattern `ck.agent.participation.v1:<agent_principal_id>:<scope_key>`,`scope_key` 为 `realm:<realm_uuid>` / `circle:<realm_uuid>:<circle_uuid>` / `strand:<realm_uuid>:<strand_uuid>`,声明 `encrypted_at_rest=true`。它经 `ck.self.agent.participation.resource.replace` 物化(校验 `selection ⊆ effective_ceiling` 后写入);`reply` / `act_on_behalf` effective 为真时进一步物化为 `ck.capability.grant`,`accept_third_party_mention` 驱动 [`strand-and-message.md` §9.4.5](./strand-and-message.md) 的第三方 mention 投递 gate。它是 controller-private state,不进入目标 Realm 共享历史。

三者 key 前缀不同、key 第二段语义不同(`draft` / `participation` 为 agent_principal_id,`sidecar_projection` 为 controller_principal_id),不会在 `ck.agent.*` 命名空间下冲突。注册时 MUST 在 `account-data-type-registry.json` 显式声明 key pattern 与 owner principal,reducer 据此做归属校验。

### 4.2 隐私边界(normative)

针对上述 agent-attributed private state:

- 存储 MUST 使用 `wire_scope=actor_private_event` 通道(encrypted account data 或 actor-private stream);不得进入 shared Realm data-plane history 或 control-plane Seal history。
- 目标 Realm 的 `ck.self.events.stream.subscribe` / `ck.self.events.query.scan` / shared reducer / Realm search index / notification fanout / push preview MUST NOT 返回 draft 或 sidecar projection 内容。
- `ck.self.account.stream.subscribe` 只能把 controller-owned approval draft / sidecar projection 返回给 controller principal 的授权 session,以及 scope 明确包含该 account-data 访问权的 agent runtime。
- 若服务端存储明文，该 deployment MUST 把"明文可见服务"写入 profile / policy 并向 controller 披露；默认语义 SHOULD 是服务端只保存 encrypted account data。
- Draft 发布到目标 Strand 时,shared event MAY 通过 `refs[].role="draft_source"` 携带 opaque digest,但明文 draft id、private metadata、scratchpad、private prompt 或历史版本 MUST NOT 泄露到共享历史。
- Sidecar 发布到目标 Strand 时,MUST NOT 泄露 sidecar `private_strand_id`、`private_circle_id`、private messages、scratchpad 或 draft history。

## 5. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Read receipts：[`../discovery/read-receipts.md`](../discovery/read-receipts.md)。
- Push notifications：[`../discovery/push-notifications.md`](../discovery/push-notifications.md)。
- Account data / 个人偏好：[`../discovery/client-preferences.md`](../discovery/client-preferences.md)。
- Profiles / presence：[`../discovery/profiles-presence.md`](../discovery/profiles-presence.md)。
