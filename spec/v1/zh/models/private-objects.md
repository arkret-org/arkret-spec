---
title: Private & Derived Objects
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Arkret 协作图中的**派生 / actor-private 对象**：

- **Read Cursor**：actor 私有的已读位置状态。
- **Notification**：从 Event / Strand / Message / Relation 派生的 inbox projection。

这些对象**不是 canonical truth**——它们由 client / SDK 从 Event 集合本地计算；schema 仅用于 wire 表示。它们不进入协作图归约，不向其他 actor 广播持久化共享对象。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Read Cursor

### 2.1 概念

`read_cursor` 是 actor-private 状态。它 SHOULD 存在于私有 account data 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

完整 read receipt / read cursor 同步规则、`ak.receipt.read` 的 disclosure 选项和高频更新策略见 [`../discovery/read-receipts.md`](../discovery/read-receipts.md)。

### 2.2 Schema 与字段

Schema id: `ak.schema.read_cursor.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:read_cursor` | `ak:read_cursor:<uuidv7>`。 | 私有状态 ID。 |
| `schema` | yes | `ak.schema.read_cursor.v1` |  | Schema ID。 |
| `actor_id` | yes | `did` | 只对该 actor 生效。 | 读取主体。 |
| `device_id` | yes | `id:device` | `ak:device:<uuidv7>`。多设备收敛 tiebreaker。 | 来源设备。 |
| `realm_id` | yes | `id:realm` |  | Realm。 |
| `read_scope` | yes | `object` | `{kind, container_ref?, track_name?}`。`kind ∈ enum(realm, circle, space, strand, thread)`。`container_ref` 必填规则：`kind=realm` 时 MUST 省略（范围即本对象 `realm_id`）；`kind=circle` 时 MUST 是 `id:circle`；`kind=space` 时 MUST 是 `id:space`；`kind=strand` 时 MUST 是 `id:strand`；`kind=thread` 时 MUST 是 Thread 根消息的 `id:message`（Thread 是 root message 回复子时间线的投影选择器，不是一等协议对象，已读隔离语义见 [`../discovery/read-receipts.md` §5](../discovery/read-receipts.md)）。`track_name` 仅在 `kind=strand` 时 MAY 出现（限定到该 Strand 的某个 track 时间线，省略表示整个 Strand）；其余 kind MUST 省略 `track_name`。Read Receipt 的 `read_scope` 使用 `object_ref`，与本字段共享同一 discriminator 族，但**两者的 `kind` 取值集合并不相交一致**：Read Cursor 支持 `realm` / `circle` / `space` / `strand` / `thread`，Read Receipt 另支持 `view` / `message` / `morph` 但**不**支持 `circle` / `space`。因此 SDK / 实现 **MUST** 按各自 schema 分别校验 `read_scope.kind`，**MUST NOT** 共用单一 enum 类型（共用会让 `circle` 误用于 Receipt、或 `message` 误用于 Cursor 等错配静默通过）；以各自 schema 为字段形状权威。跨对象 kind 可引用类别的机读真相源是 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `referenceability`：本字段使用 `read_cursor_scope_kind`、`read_cursor_scope_ref` 与 `read_cursor_thread_root` 类别。 | 已读范围。 |
| `position` | yes | `object` | `{event_id, hlc}`。 | 已读位置。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

### 2.3 行为规则

- Read marker MUST NOT 作为持久化共享对象写入 Event 链；它属于 ephemeral / actor-private 范畴（详见 [strand-and-message.md §9.6](./strand-and-message.md)）。
- 多设备并发更新同一 `(actor_id, realm_id, read_scope)` 时，接收方取 HLC 更大者收敛;HLC 相等时按 `device_id` 作 actor 域内确定性 tiebreaker(见 [`../discovery/read-receipts.md` §6.6](../discovery/read-receipts.md))。
- Strand 时间线与父 Realm 在 read receipt policy 上需要分离时，整个 Strand 通过 `Strand.scope_circle_id` 落在一个 [Circle](./circle.md)（参见 [strand-and-message.md §5](./strand-and-message.md)）；effective policy 由 Circle 自身策略与父 Realm `ak.realm.read_receipt_policy` 取更严格者。Track 级别 override 不在 v1 范围内。

## 3. Notification

### 3.1 概念

`notification` SHOULD 是从 Event / Strand / Message / Relation 派生的 inbox projection，**不是 canonical truth**。它面向单个 actor 的 inbox / push pipeline，不参与协作图归约。

**inbox `state` 的跨设备真源（normative）**：`notification` 对象本身不被持久化为共享 canonical event，但其可变 inbox `state`（`unread` / `read` / `dismissed` / `archived`）的跨设备收敛真源是 **actor-private account data**：`read` 由 read cursor（[`../discovery/read-receipts.md`](../discovery/read-receipts.md)）派生；`dismissed` / `archived` 由 actor-private account-data key 承载（key 规则见 [`../discovery/client-preferences.md`](../discovery/client-preferences.md)），并按 account-data 的 LWW（HLC + tie-break）跨设备收敛。客户端 MUST 从该真源重算 inbox `state`，MUST NOT 把某设备本地的 `dismissed` / `archived` 当作不可同步的纯本地状态而在其它设备丢失。

完整推送规则、push gateway、E2EE 脱敏推送策略见 [`../discovery/push-notifications.md`](../discovery/push-notifications.md)。

### 3.2 Schema 与字段

Schema id: `ak.schema.notification.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:notification` | `ak:notification:<uuidv7>`。 | 通知 ID。 |
| `schema` | yes | `ak.schema.notification.v1` |  | Schema ID。 |
| `actor_id` | yes | `did` | 接收者。 | 通知主体。 |
| `realm_id` | no | `id:realm` |  | 来源 Realm。 |
| `source_event_id` | conditional | `id:event` | 与 `source_account_artifact` 恰好一个出现。 | durable Realm Event 来源。 |
| `source_account_artifact` | conditional | `{kind, id}` | 与 `source_event_id` 恰好一个出现；v1 闭合分支仅 `{kind="agent_runtime_approval", id=<approval_request_id>}`。 | 非 Event 的 account-private 短期 artifact 来源。不得伪造 Event id。 |
| `source_ref` | no | `id:(message\|strand\|morph\|relation\|view\|blob)` | 只允许在 `source_event_id` 分支出现。取值形如 `ak:(message\|strand\|morph\|relation\|view\|blob):…`，union 枚举即此 6 类。render-only hint;reducer MUST 以 `source_event_id` 为权威。**子集差异（informative）**：本字段允许的 kind 子集与 Relation 端点（[`relation.md` §1](./relation.md)，端点另允许 `realm` / `space` / `actor_profile` / `event` / DID）、Read Cursor `read_scope`（§2.2，scope 限 `realm` / `circle` / `space` / `strand` / `thread`）各自不同；差异由各自语义决定（Notification 渲染目标 = 可被通知指向的内容对象；Relation 端点 = 可连边的图节点；Read Cursor scope = 可定位已读位置的时间线容器）。三处实现 MUST 按各自 schema 校验字段形状，同时以 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `referenceability` 作为 kind 子集的机读真相源；本字段对应 `notification_source` 类别。 | 可选 canonical 对象引用，供客户端直接渲染通知目标。 |
| `strand_id` | no | `id:strand` |  | 可选 Strand 上下文，用于路由通知。 |
| `track_name` | no | `string` | `^[a-z][a-z0-9_]{0,63}$`。 | 可选，来源 Strand 上的 track key。 |
| `notification_kind` | yes | `enum(message, mention, reply, assignment, schedule, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` | Notification projection-state 例外；表示 inbox/read 状态，不表示 canonical object 物理 lifecycle。 | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 3.3 行为规则

- Notification 是派生 projection；客户端 / 服务端 SHOULD 从 source event + actor preferences 计算，不要把它当作独立真相源持久化为 durable canonical event。
- 每条 Notification 必须恰好选择 `source_event_id` 或 `source_account_artifact`；Agent runtime approval 使用后者、`notification_kind="agent"`，且不得携带 `realm_id`、`source_ref`、`strand_id` 或 `track_name`。`source_account_artifact.id` 是 profile-local 短期 id，不是 durable protocol object ref；Notification 终止后 durable 真相只有 accepted `ak.agent.key.authorize` / lifecycle state。
- E2EE Realm 中 `preview` 必须由发送者客户端脱敏后置入推送 envelope；服务端不得用明文重新生成 preview。
- `notification_kind=message` 表示普通 `ak.message.create` 在接收者 effective watch / push rule 允许普通消息提醒时产生的 inbox / push 提醒；默认 `mentions_only` 不得为非定向普通消息产生该类型。当同一 source event 对同一 actor 同时命中 `mention`、`reply`、`assignment` 等更具体原因时，dispatcher MUST NOT 额外产生重复的 `message` notification。
- `notification_kind=assignment` 表示当前 actor 被新增为某 Strand 的 `assigned_to` target；它不是普通 message 的别名。
- `notification_kind=schedule` 表示该 actor 需要知晓的 Strand due date 或 Calendar schedule 变更；它覆盖 `metadata.fields.due_at` 与 [`calendar-event.md`](./calendar-event.md) §2 schedule fields。
- `notification_kind=applet` / `agent` / `policy` / `moderation` 等扩展类型分别沿用对应 Applet、native agent、policy 与 moderation 业务对象的可见性边界；参见 [`../extensions/applet-integration.md`](../extensions/applet-integration.md)、[`../authz/policy-server.md`](../authz/policy-server.md) 与 [`../governance/content-moderation.md`](../governance/content-moderation.md)。

### 3.4 Mention notification 派生

`notification_kind=mention` 覆盖普通 direct mention 与 audience mention（例如 `@all` / `@here`）。派生器 MUST 遵守 [`strand-and-message.md` §9.4](./strand-and-message.md)：

- Direct mention 以结构化节点的 `subject_id` 为目标；audience mention 先按 source event causal frontier、Message effective scope、Realm / Circle policy 与可见性规则展开 receiver set。`strand_watchers` / `strand_engaged` audience 的 watcher 命中由完整 effective watch level 计算，但只作为 receiver-side fanout 条件。
- 对同一 `(actor_id, source_event_id, notification_kind)` MUST 去重。一个 Message 中重复 direct mention、direct mention 与 audience mention 同时命中、或 watch / reply / assignment 叠加命中，都不得在同一 push delivery window 内产生多次 wakeup。
- `actor_id` MUST 是接收 notification 的 actor，而不是发送者。默认发送者自 mention 不产生 notification，除非该 actor 的私有 push rule 显式 opt-in。
- 派生器 MUST 在生成 notification 前应用 access check、history visibility、`level=muted`、blocklist、DND 与 push rule 覆盖；无访问权或被静音时不得留下可查询的 notification stub。
- 派生器、delivery response、inbox projection 与 push payload MUST NOT 暴露 audience 展开结果、recipient count、watcher 列表、watch level 或命中原因；sender 不得区分某 receiver 是因历史参与、watch 还是 direct mention 命中。
- `preview` 在 E2EE / redaction / history-limited 场景下 MUST 为空或使用已授权的脱敏摘要；不得因为 notification projection 需要展示而扩大源 Message 的明文可见性。

### 3.5 Assignment notification 派生

当一个 accepted `ak.relation.create` 满足下列条件时，notification dispatcher MUST 为被分配 actor 派生 `notification_kind=assignment`：

- `relation_kind="assigned_to"`。
- `from_ref` 是 active Strand id，`to_ref` 是 actor DID。
- Relation create 不是现有 active `(realm_id, relation_kind, from_ref, to_ref)` assignment tuple 的 no-op 重放；同一 `(actor_id, source_event_id, notification_kind=assignment)` 最多生成一个 notification。
- 接收 actor 对该 Strand 的 effective Realm / Circle scope 有读取权，且未被 `level=muted`、blocklist、DND 或 push rule 覆盖抑制。

派生 notification 的 `actor_id` MUST 是 `to_ref`，`realm_id` MUST 是 Relation 所属 Realm，`source_event_id` MUST 是产生该 Relation create 的 Event id，`source_ref` SHOULD 是新增的 Relation id，`strand_id` MUST 是 `from_ref`。若 source Event 无独立 Event id，服务端 MAY 使用承载该 Event 的 operation id 作为本地 `source_event_id` 投影键，但跨服务 wire 输出仍 SHOULD 使用 canonical Event id。

解除 assignment（Relation tombstone）默认不产生 `assignment` notification；需要审计或流程提示的产品 MAY 在本地 UI 活动流展示，但不得把 tombstone 当作新的 assignment。发送者自分配默认不通知自己，除非 receiver 私有 push rule 显式 opt-in。

Assignment 只影响通知订阅与 inbox 派生，不扩大 Strand 访问权；无访问权时 dispatcher MUST 不留下可查询 notification stub，也不得通过 push 发送 wakeup。

### 3.6 Schedule notification 派生

core notification 只把 accepted `ak.strand.update` 对 `metadata.fields.due_at` 的改变视为 schedule-relevant change。扩展 profile 的额外 schedule 字段由该 profile 自己登记；core 实现不得因本节而被迫识别 calendar 字段。

Schedule notification 的 receiver set 是下列集合的并集，并在生成前按 access check、history visibility、`level=muted`、blocklist、DND 与 push rule 覆盖过滤：

- 该 Strand 当前 active `assigned_to` Relation 的 `to_ref` actors。
- 对该 Strand 显式选择 `watch=all` 的 watchers。

默认 `mentions_only` / 隐含 `participating` 不因普通 schedule field 变更自动通知；但 actor 同时处于上述 receiver set（例如 assignee）时，dispatcher SHOULD 将 push-rule EventContext 标记为 target-directed，以避免被普通消息规则错误过滤。发送者默认不通知自己，除非私有 push rule 显式 opt-in。

派生 notification 的 `notification_kind` MUST 是 `schedule`，`source_event_id` MUST 是该 `ak.strand.update` 的 Event id，`source_ref` SHOULD 是被更新的 Strand id，`strand_id` MUST 是被更新的 Strand id。对同一 `(actor_id, source_event_id, notification_kind=schedule)` MUST 去重；一次 patch 同时改 due date 和 calendar fields 也只生成一条 schedule notification。

E2EE / plaintext policy 不允许服务端读取 schedule fields 时，服务端不得为了通知而解密或扩展明文可见性；实现 MAY 发送不含 preview 的 blind wakeup，或让客户端在本地解密后根据同一规则完成 inbox 派生。

## 4. 与 Account Data 的关系

Read marker 与个人通知偏好、saved view personalization、列宽 / 折叠等本地状态都属于 **actor-private account data** 类别。完整 account data 模型、私有标签、个人 blocklist 见 [`../discovery/client-preferences.md`](../discovery/client-preferences.md)。

### 4.1 Agent draft、Sidecar view 与 participation account data

三类 controller-owned encrypted account data 类型在 `ak.agent.*` 命名空间下:

- **`ak.agent.draft.v1`**:agent 通过 `ak.agent.draft.propose` / `ak.agent.action_request`(actor_private_event)提议候选内容,Principal Server 通过 capability / policy / accountability / risk check 后,materialize 为 controller-owned `ak.agent.draft.v1` account-data。Key pattern 建议 `ak.agent.draft.v1:<agent_id>:<draft_id>`,声明 `encrypted_at_rest=true`、tombstone 与 retention 规则。Draft MUST NOT 作为 `ak.message.create` / `ak.strand.create` 或任何 `wire_scope=durable_event` 进入目标 Realm 共享历史。Draft 引用目标 `realm_id` / `strand_id` / `message_id` 不授予目标 Realm 成员读取 draft 内容的权利。
- **`ak.agent.sidecar_view_state.v1`**：controller-private context view state，使用 `ak.schema.agent_sidecar_view_state.v1` plaintext。Key pattern `ak.agent.sidecar_view_state.v1:<controller_id>:<target_realm_id>:<target_strand_id>`；保存 Sidecar 寄宿显示的 `display_mode=context_merged|sidecar_only`、pin/折叠与跨设备 HLC。它引用 `sidecar_id`，但不得把 backing Circle 当作产品身份。
- **`ak.agent.participation.v1`**:controller-owned 的逐 scope agent 参与选择 `{reply, accept_third_party_mention, act_on_behalf}`。Key pattern `ak.agent.participation.v1:<agent_id>:<scope_key>`,`scope_key` 为 `realm:<realm_uuid>` / `circle:<realm_uuid>:<circle_uuid>` / `strand:<realm_uuid>:<strand_uuid>`,声明 `encrypted_at_rest=true`。它经 `ak.self.agent.participation.resource.replace` 物化；服务端先把 Agent 创建时 immutable `requested_scope` 派生的全局 ceiling 与 deployment/Realm/Circle/Strand governance ceiling 做 AND，再校验 `selection ⊆ effective_ceiling`。治理 policy 不得补回 provision 时未允许的位。`reply` / `act_on_behalf` effective 为真时进一步物化为 `ak.capability.grant`,`accept_third_party_mention` 驱动 [`strand-and-message.md` §9.4.5](./strand-and-message.md) 的第三方 mention 投递 gate。它是 controller-private state,不进入目标 Realm 共享历史。

上述类型 key 前缀不同、key 第二段语义不同（`draft` / `participation` 为 agent_id，Sidecar view 为 controller_id），不会在 `ak.agent.*` 命名空间下冲突。注册时 MUST 在 `account-data-key-registry.json` 显式声明 key pattern、plaintext schema 与 owner principal，reducer/client 据此做归属、key/content binding 与 closed-schema 校验。

`ak.schema.agent_sidecar_exchange_projection.v1` 不属于本节 Account Data：它只是 controller 设备从 Sidecar private Event history 生成的本地可删除 cache/SDK DTO，不注册 account-data key，不进入 account stream，也不跨设备合并。真相源与恢复规则见 [`sidecar.md`](./sidecar.md) §7.2。

### 4.2 隐私边界(normative)

针对上述 agent-attributed private state:

- 存储 MUST 使用 `wire_scope=actor_private_event` 通道(encrypted account data 或 actor-private stream);不得进入 shared Realm data-plane history 或 control-plane Seal history。
- 目标 Realm 的 `ak.self.events.stream.subscribe` / `ak.self.events.query.scan` / shared reducer / Realm search index / notification fanout / push preview MUST NOT 返回 draft、Sidecar view state 或本地 exchange cache 内容。
- `ak.self.account.stream.subscribe` 只能把 controller-owned approval draft / Sidecar view state 返回给 controller principal 的授权 session。Agent runtime MUST NOT 接收上述 controller-owned encrypted account data：其 value 以 controller account secret 派生密钥加密（[`account-data.md`](./account-data.md) §3），不同 principal 的 account secret 强制隔离，不存在也不得新增向 Agent runtime 分发该 secret 的机制。Agent runtime 所需的 Sidecar exchange identity 经 [`sidecar.md`](./sidecar.md) §7.2.1 的加密 exchange binding 在 Event 内传递。
- 若服务端存储明文，该 deployment MUST 把"明文可见服务"写入 profile / policy 并向 controller 披露；默认语义 SHOULD 是服务端只保存 encrypted account data。
- Draft 发布到目标 Strand 时,shared event MAY 通过 `refs[].role="draft_source"` 携带 opaque digest,但明文 draft id、private metadata、scratchpad、private prompt 或历史版本 MUST NOT 泄露到共享历史。
- Sidecar 发布到目标 Strand 时，MUST NOT 泄露 `sidecar_id`、`backing_circle_id`、`private_strand_id`、private Relation id、private messages、scratchpad 或 draft history。

## 5. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Read receipts：[`../discovery/read-receipts.md`](../discovery/read-receipts.md)。
- Push notifications：[`../discovery/push-notifications.md`](../discovery/push-notifications.md)。
- Account data / 个人偏好：[`../discovery/client-preferences.md`](../discovery/client-preferences.md)。
- Profiles / presence：[`../discovery/profiles-presence.md`](../discovery/profiles-presence.md)。
