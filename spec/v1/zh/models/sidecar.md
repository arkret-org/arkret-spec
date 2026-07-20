---
title: Agent Sidecar
status: candidate
normative: true
stability: v1
updated: 2026-07-20
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与对象边界

**Agent Sidecar**（`ak:sidecar:`）是绑定到一个 `(realm_id, controller_id)` 的个人 AI 私有工作区。它是一等协议对象，不是 Circle profile、普通 Circle、Direct Conversation、Strand Track 或某个 Agent 的 1:1 会话。

Sidecar 与 Circle 的职责不同：

| 对象 | 身份与生命周期 | 访问集合 | 用户创建/管理 |
| --- | --- | --- | --- |
| Realm | federation / identity / policy boundary | Realm membership | 按 Realm 治理 |
| Circle | Realm 内显式协作圈与 scoped event boundary | 可管理的 `Circle.members ⊆ Realm.members` | 需要 Circle 创建/成员管理能力 |
| Sidecar | controller 的个人 AI 工作区 | controller + 派生的 eligible owned Agents | controller 自助幂等 ensure；无成员管理 |

每个 `(realm_id, controller_id)` MUST 至多存在一个 non-tombstoned Sidecar。Sidecar 可拥有多个 private Strand；这些 Strand 按 normalized source context 复用。

## 2. Sidecar 对象

Schema id：`ak.schema.agent_sidecar.v1`。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:sidecar` | `ak:sidecar:<uuid>`（UUIDv7） | Sidecar ID。 |
| `schema` | yes | `ak.schema.agent_sidecar.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | create-locked。 | Sidecar 所属 Realm。 |
| `controller_id` | yes | `did` | create-locked；MUST 是父 Realm active member。 | 唯一 controller。 |
| `backing_circle_id` | yes | `id:circle` | reducer-derived；create-locked；raw ensure caller MUST NOT 提供；`ak.sidecar.create` 的 service-built canonical payload MUST 物化。 | 系统管理的私有 event/MLS scope；不是产品 Circle。 |
| `encryption_profile` | yes | `mls_rfc9420` | 固定；create-locked。 | Sidecar 始终 E2EE，不允许 plaintext fallback。 |
| `state` | yes | `enum(active, suspended, tombstoned)` | reducer-derived。 | Sidecar 生命周期。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近状态变化。 |
| `created_at` | yes | `timestamp` | reducer-derived。 | 创建时间。 |
| `updated_at` | no | `timestamp` | reducer-derived。 | 最近投影更新时间。 |

Sidecar 不包含 `title`、`summary`、`display`、`directory_visibility`、`join_rule`、`history_visibility`、caller-provided members 或管理员角色。客户端使用本地化的 “Private Sidecar / 私人 AI 工作区”身份与来源 context 标题，不得把 backing Circle 的派生 metadata 当作 Sidecar 标题。

## 3. 创建与生命周期

### 3.1 Ensure

`ak.self.agent.sidecar.command.ensure` MAY 作为 self-scoped default capability 授予任一 active Realm member，但只能确保 `controller_id == authenticated principal` 的 Sidecar。

ensure MUST：

1. 以 `(context_ref.realm_id, controller_id)` 作为 Sidecar singleton key。
2. 并发请求幂等收敛到同一 `sidecar_id`。
3. 在首次需要时按同一原子 batch 建立系统管理的 backing Circle、初始 access、`ak.sidecar.create`、private Strand 与 `agent_sidecar_of` Relation；`ak.sidecar.create` 必须位于 backing Circle 建立之后并以它作为 effective scope。任一步失败，整个 batch 不可见且不得留下可枚举的部分对象。
4. 以 `(sidecar_id, normalized_context_ref)` 作为 private Strand reuse key。
5. 只接受由服务端派生的 backing Circle shape；caller 不得提供 Circle title、display、join rule、membership、encryption profile 或 ID。
6. 返回 Sidecar、private Strand、private Relation 与 access/readiness 投影；不得把 backing Circle 暴露成普通 Circle 资源。

普通 `ak.circle.create`、Circle REST create、Circle member-management capability 或 Circle picker MUST NOT 创建、更新、枚举或改变 Sidecar backing Circle。

`ak.sidecar.create` 不能通过通用 event submit 独立构造。Admission MUST 证明它属于本节 ensure 的原子 aggregate，`controller_id` 等于 authenticated principal，`backing_circle_id` 与同 batch 中 reducer 派生的 Circle bit-identical，且 singleton/reuse key 尚未被另一个 non-tombstoned Sidecar 占用；否则 MUST fail closed。该 Event 的 `effective_scope` MUST 为 `{kind:"circle", realm_id, circle_id=backing_circle_id}`，不得进入 Realm-default shared delivery 或明文 Seal leaf。

### 3.2 专用读取

Sidecar 的 canonical read surface 是 `ak.self.agent.sidecar.resource.get` 与 `ak.self.agent.sidecar.query.list`。两者只返回 authenticated controller 自己的 Sidecar，以及分离的 desired/effective Agent access、readiness 与 pending reconciliation。普通 Circle get/list、Realm directory、scope picker 或通用 event query MUST NOT 代替该 surface。

get 对 nonexistent、foreign-controller 与 unauthorized `sidecar_id` MUST 返回相同 `not_found` envelope 与 timing bucket。list 不返回其他 controller 的 locked stub、计数空洞或 backing Circle。Sidecar view MAY 包含 `backing_circle_id` 供专用 MLS/scope 处理，但客户端不得把它注册为普通 Circle route 或用户可管理资源。

### 3.3 生命周期

- controller 仍为 Realm active member且 Sidecar policy gate 允许时，Sidecar 为 `active`。
- controller 暂时失去 Realm access、account 被临时冻结或密钥恢复尚未 ready 时，Sidecar MUST 转为 `suspended` 并阻止新写入；恢复条件满足后 MAY 回到 `active`。
- controller 永久离开 Realm、account 被不可逆删除或显式执行合规删除时，Sidecar MUST `tombstoned`；该状态不可逆，并级联停止 private Strand 写入、移除 backing Circle access、完成 MLS remove/rotate 与 retention/tombstone policy。
- 用户不得通过普通 Circle archive/restore/tombstone 操作间接改变 Sidecar 生命周期。

`state` 是由已接受的 controller account/Realm membership/lifecycle frontier 派生的 canonical projection，不提供 actor-authored `ak.sidecar.update/archive/restore`。`state_changed_at` 使用触发派生转换的已接受 Event timestamp；同一 control frontier 在所有 conforming reducer 上 MUST 得到同一状态。Backing Circle lifecycle 是 Sidecar state cascade 的执行结果，不是反向决定 Sidecar state 的真相源。

## 4. 派生访问集合

Sidecar 没有可编辑 membership。其 desired access set 为：

```text
desired_sidecar_access(S) = { S.controller_id }
  ∪ { A | eligible_sidecar_agent(S.realm_id, S.controller_id, A) }
```

`eligible_sidecar_agent(realm, controller, agent)` MUST fail closed，仅当以下条件全部成立时为 true：

1. controller 是 Realm active member。
2. agent 是父 Realm active member且为 active Native Personal Agent，immutable ownership/provisioning state 指向 controller。
3. active `ak.identity.accountability_grant` 的 issuer、subject、validity 与 revocation freshness 均通过。
4. agent 未 paused/deactivated，pairing 未过期，active `ak.agent.key.authorize` 与 runtime proof 未 revoke。
5. Realm policy、capability constraints、Sidecar gate 与 controller approval 均允许。

其它 human actor、其他 controller 的 Agent、非 accountable Agent、Applet Ghost Actor 与外部 service principal MUST NOT 进入 desired 或 effective access。

### 4.1 Desired access 与 effective access

`desired_access` 是从已接受 control frontier 派生的规范集合；`effective_access` 是已经完成 backing Circle delivery binding 与当前 MLS epoch 加入/移除的操作集合。两者 MUST 分开投影。

- 新 Agent 进入 desired access 后，在 backing Circle membership、MLS Welcome/commit 与 device readiness 全部完成前不得接收 Sidecar payload。
- Agent 离开 desired access 时，服务端 MUST 立即停止寻址/投递，并主动生成 backing membership remove 与 MLS remove/rotate；不得等待被动 reconcile。
- reconciliation 期间新消息 MUST 阻塞或仅发给已经证明符合当前 desired/effective access 的安全交集；不得因旧 MLS key 仍存在而继续投递。
- `pending_access_reconciliations=[]` 本身不证明 controller 设备或 addressed Agent 已 MLS-ready。

新 Agent 完成 effective access 后默认只能读取加入后 epoch 的内容。实现 MUST NOT 转移过去 epoch group secrets。controller 显式批准历史 backfill 时，只能通过 application-level resend：controller 设备解密获准内容并在当前 epoch 重新加密；不得共享 MLS exporter secret、past commit secret 或等价历史密钥。

## 5. Backing Circle 是安全实现，不是领域身份

每个 Sidecar 拥有一个系统管理的 backing Circle，用于复用 Circle 已定义的 scoped delivery、query/projection 裁剪、sub-seal 与独立 MLS group。它满足：

- 与 Sidecar 同 Realm，`encryption_profile=mls_rfc9420`，content/metadata floor 均为 `e2ee_required`。
- `directory_visibility=members`、`join_rule=invite`、history visibility 不宽于 `restricted`。
- canonical shape 固定为：`profile_ref` 省略，`title="Agent Sidecar Scope"`，`summary` 省略，`display.color_token="slate"`，`display.symbol.glyph="lock"`，`display.short_name="SC-" + upper(base32(sha256(canonical("ak.sidecar.backing_circle.v1\n" + sidecar_id))))[:16]`。普通 Circle create/update MUST 拒绝 `SC-` 保留前缀；backing Circle 冲突只能以 generic `sidecar_create_denied` 暴露。
- title/display/short name 仅满足 Circle schema 与安全 scope 内部需要；不得进入普通 Circle UI、目录、搜索、Board、scope picker、公开 Relation expansion 或普通 Circle API response。
- access state只能由 §4 的派生规则 fan-out；Circle admin、自助 join、knock、invite 与手工 remove 对 backing Circle MUST fail closed。
- backing Circle 与 Sidecar 必须在同一原子 operation/batch 中建立绑定。无法证明绑定的 reserved/private Circle 不得被客户端猜测为 Sidecar，也不得被普通 Circle surface 显示。

MLS governance binding 继续使用 backing Circle 的 `{kind:"circle", realm_id, circle_id}` effective scope，并额外绑定 `sidecar_id`、Sidecar desired-access digest 与对应 control frontier。任何字段不匹配 MUST fail closed。Sidecar key MUST NOT 从 Realm-default MLS group 派生。

## 6. Private Strand 与 context

Sidecar private Strand MUST：

- `scope_circle_id = Sidecar.backing_circle_id`。
- 由 `(sidecar_id, normalized_context_ref)` 唯一复用，不以标题或 Agent id 作为 identity。
- 不出现在 Realm-wide navigation、普通 Circle navigation、Board、list、public search、public Relation expansion 或目标 Strand projection。
- 可在 encrypted metadata 中保存来源标题 snapshot，但 reuse、安全与授权只依赖 canonical context ref/digest。

`addressed_agent_ids` 是 exchange/message 级寻址集合，MUST 是当前 desired/effective access 中 eligible Agent 的子集；它不是 membership，也不改变 Sidecar access。

`agent_sidecar_of` 是 weak-semantic、non-structural、non-cascading private Relation。其 effective scope 使用 backing Circle；目标公共对象不得保存反向 relation 或可枚举 Sidecar locator。

## 7. Projection、发布与存在性隐私

controller-private `ak.agent.sidecar_projection.v1` 可保存 UI 顺序、context overlay、exchange origin、source anchor、addressed Agents、readiness 与私有回显。它不得修改目标 Strand tracks/metadata/Relation/watch/unread/search/notification state。

Sidecar 发布到共享 Strand 必须由 controller 显式确认，只创建符合目标 scope 的正常 shared event。shared event、日志、URL、push preview 与公开 telemetry MUST NOT 携带 `sidecar_id`、`backing_circle_id`、private Strand/Relation id、private messages、scratchpad 或 draft history；只可携带规范允许的 opaque digest。

未授权 caller 对 Sidecar 的 list/get/search、backing Circle existence、private Strand/Relation existence MUST 收到与不存在资源相同的固定错误 envelope、字段集合与 timing bucket。

## 8. UI 安全不变量

1. Sidecar MUST 使用专用产品 surface，不得进入 Circle 目录、Circle 创建器、Circle 成员管理或 Strand Track tabs。
2. 从 Realm 或 Circle shared surface 打开 Sidecar 时，客户端 MUST 明确显示进入“仅 controller 与其 AI Agents 可访问”的个人私有 scope，并提供返回来源 context 的入口。
3. Access 面板 MUST 展示 controller、desired Agents、effective access、Agent lifecycle 与 MLS readiness；不得提供邀请/移除 human 的控件。
4. Mention picker 只显示 active eligible owned Agents，并在提交前由服务端再次 fail-closed 校验。
5. `addressed`、`working`、`replied` 与完整 desired/effective access 必须使用不同文案，不得把一次呼叫伪装成固定 1:1 成员关系。
6. readiness 未满足时 composer MUST 阻塞，并显示 `access_reconciliation_pending`、`key_material_pending`、`epoch_update_required` 等准确原因。

## 9. 规范性引用

- Circle backing scope：[`circle.md`](./circle.md)。
- Strand / Message：[`strand-and-message.md`](./strand-and-message.md)。
- Private projection：[`private-objects.md`](./private-objects.md)。
- Agent identity / lifecycle：[`actor.md`](./actor.md)、[`../identity/key-management.md`](../identity/key-management.md)。
- Service binding：[`../sync/service-http-binding.md`](../sync/service-http-binding.md)。
