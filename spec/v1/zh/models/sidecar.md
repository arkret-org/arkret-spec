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

用户从 Contacts/Direct Messages 产品面点击自己的 Native Personal Agent 时，客户端 MUST 使用 [`ak.self.direct_conversation.command.resolve`](../identity/contact-and-direct-conversation.md#6-direct-conversation-resolver) 建立或复用 `{controller, agent}` 的独立双成员 Direct Conversation Realm。该入口不得调用 Sidecar ensure、不得要求当前 Realm/Strand context，也不得把 backing Circle 暴露成私聊会话。Sidecar 仅用于既有 Realm/Strand 内的 context-routed 私有协作。

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
3. 在首次需要时按同一原子 batch 建立系统管理的 backing Circle、初始 backing membership、`ak.sidecar.create`、private Strand 与 `agent_sidecar_of` Relation；`ak.sidecar.create` 必须位于 backing Circle 建立之后并以它作为 effective scope。任一步失败，整个 batch 不可见且不得留下可枚举的部分对象。真实 MLS genesis 不属于该服务端 aggregate；它按 §5.1 由 controller 设备在本地持久化 provisional OpenMLS state 后通过标准 Event admission 提交。在 genesis accepted 之前 aggregate 保持 `key_material_pending` 且不可发送。
4. 以 `(sidecar_id, normalized_context_ref)` 作为 private Strand reuse key；`normalized_context_ref` 只包含 Realm 与 Strand（或 profile 明确允许的 Relation）级身份，MUST NOT 包含 `track_name`、Message id、timeline anchor 或当前 UI route。
5. 只接受由服务端派生的 backing Circle shape；caller 不得提供 Circle title、display、join rule、membership、encryption profile 或 ID。
6. 返回 Sidecar、private Strand、private Relation 与 access/readiness 投影；不得把 backing Circle 暴露成普通 Circle 资源。

普通 `ak.circle.create`、Circle REST create、Circle member-management capability 或 Circle picker MUST NOT 创建、更新、枚举或改变 Sidecar backing Circle。

`ak.sidecar.create` 不能通过通用 event submit 独立构造。Admission MUST 证明它属于本节 ensure 的原子 aggregate，`controller_id` 等于 authenticated principal，`backing_circle_id` 与同 batch 中 reducer 派生的 Circle bit-identical，且 singleton/reuse key 尚未被另一个 non-tombstoned Sidecar 占用；否则 MUST fail closed。该 Event 的 `effective_scope` MUST 为 `{kind:"circle", realm_id, circle_id=backing_circle_id}`，不得进入 Realm-default shared delivery 或明文 Seal leaf。

### 3.2 专用读取

Sidecar 的 canonical read surface 是 `ak.self.agent.sidecar.resource.get` 与 `ak.self.agent.sidecar.query.list`。两者只返回 authenticated controller 自己的 Sidecar，以及分离的 desired/effective Agent access、readiness、pending reconciliation 与 `mls_context`。普通 Circle get/list、Realm directory、scope picker 或通用 event query MUST NOT 代替该 surface。

get 对 nonexistent、foreign-controller 与 unauthorized `sidecar_id` MUST 返回相同 `not_found` envelope 与 timing bucket。list 不返回其他 controller 的 locked stub、计数空洞或 backing Circle。Sidecar view MAY 包含 `backing_circle_id` 供专用 MLS/scope 处理，但客户端不得把它注册为普通 Circle route 或用户可管理资源。

### 3.3 生命周期

- controller 仍为 Realm active member且 Sidecar policy gate 允许时，Sidecar 为 `active`。
- controller 暂时失去 Realm access、account 被临时冻结或密钥恢复尚未 ready 时，Sidecar MUST 转为 `suspended` 并阻止新写入；恢复条件满足后 MAY 回到 `active`。
- controller 永久离开 Realm、account 被不可逆删除或显式执行合规删除时，Sidecar MUST `tombstoned`；该状态不可逆，并级联停止 private Strand 写入、移除 backing Circle access、完成 MLS remove/rotate 与 retention/tombstone policy。
- 用户不得通过普通 Circle archive/restore/tombstone 操作间接改变 Sidecar 生命周期。

**合法 / 非法迁移（normative）**：`state` 由下表封闭定义，全部由派生条件触发，无 actor-authored 迁移入口；表外任何迁移非法，reducer MUST NOT 物化。

| 源 state | 目标 state | 触发派生条件 |
| --- | --- | --- |
| `active` | `suspended` | controller 暂时失去 Realm access / account 临时冻结 / 密钥恢复未 ready |
| `active` | `tombstoned` | controller 永久离开 Realm / account 不可逆删除 / 显式合规删除 |
| `suspended` | `active` | 上述暂时性条件全部解除（controller 重获 Realm active membership 且 policy gate 允许） |
| `suspended` | `tombstoned` | 暂停期间发生上一行的任一永久性条件 |
| `tombstoned` | —（终态） | 不可逆；无出边 |

`active` 与 `suspended` 是非终态，`tombstoned` 是唯一终态。`active -> active` / `suspended -> suspended` 的同态派生不是迁移，reducer MUST NOT 因此更新 `state_changed_at`。因 `state` 是 reducer-derived projection（无 actor-authored state event 可拒绝），"非法迁移拒绝"体现为 reducer MUST NOT 物化任何不在上表的 (源, 目标) 对，而非返回错误码。

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

`desired_access_digest` 的 byte-exact transcript 为 RFC 8785 JCS canonical JSON：

```json
{
  "domain": "ak.sidecar.desired_access.v1",
  "sidecar_id": "ak:sidecar:...",
  "realm_id": "ak:realm:...",
  "controller_id": "did:...",
  "principal_ids": ["did:..."]
}
```

`principal_ids` MUST 等于完整 `desired_sidecar_access(S)`（包含 controller），按 DID UTF-8 byte lexicographic 升序排列且去重；digest 为 `sha256:<lowercase-hex(SHA-256(JCS bytes))>`。任何实现不得使用 UI 顺序、Circle member 顺序、设备 id、display name、到达时间或本地数据库 id 参与该 digest。

`mls_context.control_frontier` 是服务端当前用于物化 Sidecar 与**已落地** backing membership 的 accepted control refs：MUST 包含 effective `ak.sidecar.create` ref、controller backing join ref，以及每个已经完成 backing membership reconciliation 的 desired Agent 当前 backing join ref；尚未落地的 desired Agent 不得伪造 join ref，view 同时以 `backing_scope_membership` pending 明示缺口。按 ref UTF-8 byte lexicographic 升序排列且去重。Sidecar MLS Event admission 还 MUST 要求 backing members 已与 `{controller} ∪ desired agents` 精确相等，并以当前 accepted eligibility/control state 重新计算 desired set；control frontier 与 digest 都匹配也不能绕过 membership reconciliation、freshness、revocation 或 policy 检查。

- 新 Agent 进入 desired access 后，在 backing Circle membership、Add Commit accepted、匹配的 `ak.mls.welcome` accepted、目标设备成功 consume 同一 KeyPackage claim 全部完成前不得接收 Sidecar payload。一个 Agent principal 至少有一个仍 active/authorized、未被 remove 的设备满足上述证据时进入 `effective_agent_ids`；其它设备不会因 principal 已 effective 自动获得密钥。
- controller 当前调用设备只在它是 accepted genesis 的 `creator_device_id`，或已完成同样的 Welcome/consume 证据时视为 device-ready。`access_readiness=ready` 要求当前 controller 设备 ready，且每个 `desired_agent_ids` principal 都已 effective；因此同一 Sidecar 在 controller 的不同设备上 MAY 暂时呈现不同 readiness，但 `desired_agent_ids`/`effective_agent_ids` 必须一致。
- Agent 离开 desired access 时，服务端 MUST 在同一 control-state apply 中立即停止寻址/投递、移除 backing membership 并产生 durable pending MLS removal obligation。持有该 backing Circle 当前 MLS snapshot 的 controller 设备或 policy-authorized key service MUST 通过普通 `ak.mls.proposal` + `ak.mls.commit` 完成 remove/rotate；普通 Principal Server 不得伪造 Commit。没有 eligible committer 时发送保持 fail closed，obligation 保留并允许 §5.3 takeover。

  专用 Sidecar view MUST 为每个尚未完成的 obligation 返回 `stage="mls_remove"` 的 `pending_access_reconciliations` item；该 item 的 `agent_id` 是已移除的 Agent，且 `membership_frontier` 是触发该 obligation 的 accepted membership/control refs，按 UTF-8 byte lexicographic 升序排列且去重。`membership_frontier` 对 `mls_remove` 必填且非空，对其它 stage 必须省略。这样 controller/key service 无需也不得通过普通 Circle surface 枚举 backing Circle，即可构造带当前 `sidecar_binding` 的 Remove Proposal/Commit。Commit accepted 后服务端清除对应 obligation；客户端仅在 accepted 后持久化 post-commit snapshot。
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

### 5.1 Client-authored bootstrap 与崩溃恢复

Sidecar MLS bootstrap 复用标准 `ak.mls.genesis` Event 与 `POST /_arkret/self/events`，不注册可绕过普通 Event proof/Seal/CAS 的私有 bootstrap endpoint：

1. controller 读取专用 Sidecar view 的 `sidecar.backing_circle_id` 与 `mls_context.{desired_access_digest,control_frontier}`。
2. controller 当前设备在本地创建真实 OpenMLS group，构造 Circle effective-scope genesis，并把完整 §5.2 `sidecar_binding` 写入 governance binding/GroupContext extension。
3. 提交前客户端 MUST 将 `(sidecar_id, genesis_event_id, mls_group_id, provisional_snapshot)` 持久化到设备保护存储。Event accepted 后把 provisional snapshot 标记 active；确定 rejected/loser 后销毁该 snapshot。
4. 服务端按 `(effective_scope, mls_group_id)` genesis CAS、Sidecar singleton、当前 desired digest/frontier 与 authenticated controller/device proof 一并校验。成功后 `mls_context.mls_group_id`、`epoch=0`、`genesis_event_ref` 可见，且该 creator device ready。
5. 崩溃恢复 MUST 重放 exact same Event id/bytes 或读取 Sidecar view 判断它是否 accepted，不得另造 Event。多 controller 设备并发 genesis 时只有 canonical accepted winner 可激活；loser 必须销毁 provisional snapshot，并通过 winner group 的 KeyPackage/Welcome 正常加入。

服务端、Account Authority 与普通同步服务 MUST NOT 生成、暂存或备份明文 MLS private state。客户端若选择跨设备恢复，必须使用既有 controller-owned encrypted key-backup 机制，不得把 snapshot 放入 Sidecar view 或普通 Event payload。

### 5.2 Sidecar MLS binding

`mls_governance_binding.sidecar_binding` 是 closed object，仅在 effective scope 对应一个 Sidecar backing Circle 时必填，在普通 Realm/Circle MLS group 中 MUST 省略：

```json
{
  "sidecar_id": "ak:sidecar:...",
  "desired_access_digest": "sha256:...",
  "control_frontier": ["ak:event-or-operation-ref:..."]
}
```

字段顺序不参与 JSON 语义，但 deterministic CBOR 必须按 RFC 8949 deterministic map-key ordering；SDK 是唯一编码实现。Genesis、每次 Sidecar Add/Remove/self-update Commit及对应 Welcome MUST 携带同一个由其 base control view 计算的 binding。Sidecar application DataEvent 不重复携带完整 binding；它必须引用已由当前 GroupContext binding 约束的 group/epoch，并按 [`encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md#25-mls-governance-binding) 通过 `seal_ref`/`covered_seals_cell` gate。服务端在 admission 时必须重新计算 current Sidecar/binding；`sidecar_id`、backing Circle、desired digest、frontier、Realm、group 或 epoch 任一不匹配都 fail closed。历史 Event 保留其创建时 binding，不因后续 desired set 变化重写。

### 5.3 Effective roster 证据

服务端从已有标准事实机械派生 device roster，不新增由服务端代签的 join Event：

- genesis creator row：accepted Sidecar-bound `ak.mls.genesis` 的 `(creator_principal_id, creator_device_id, epoch=0, genesis_event_ref)`；
- admitted device row：accepted Add Commit、引用该 Commit 的 accepted `ak.mls.welcome`、与 Welcome 相同的 `(group, recipient principal, recipient device, keypackage_ref)`，以及目标设备 authenticated consume 成功；该 Welcome 的 Sidecar control frontier MUST 包含该 principal 当前 backing join ref。后续加入其它 Agent 不会废止该设备证据，但 principal 被移除后重新加入会产生新 join ref，旧 Welcome 因而不能复用；当前 group epoch 的 governance binding 仍 MUST 与当前完整 Sidecar binding 精确一致；
- removed row：effective Remove Commit 引用匹配 target principal/device 的 remove proposal 后，自 `next_epoch` 起不再 effective；backing membership/desired access 先行移除时投递已立即停止，不等待 Commit。

Welcome durable projection MUST 保留 `epoch`、`commit_ref`、KeyPackage ref 与完整 Sidecar binding identity；KeyPackage consume MUST 只接受与调用 session device、claimed group 和 matching accepted Welcome 一致的 claim。仅 delivered、仅 claimed、仅 Circle member、仅存在旧 Welcome、或没有 target-device consume 都不能产生 effective row。

## 6. Private Strand 与 context

Sidecar private Strand MUST：

- `scope_circle_id = Sidecar.backing_circle_id`。
- 由 `(sidecar_id, normalized_context_ref)` 唯一复用，不以标题或 Agent id 作为 identity。
- 不出现在 Realm-wide navigation、普通 Circle navigation、Board、list、public search、public Relation expansion 或目标 Strand projection。
- 可在 encrypted metadata 中保存来源标题 snapshot，但 reuse、安全与授权只依赖 canonical context ref/digest。

`addressed_agent_ids` 是 exchange/message 级寻址集合，MUST 是当前 desired/effective access 中 eligible Agent 的子集；它不是 membership，也不改变 Sidecar access。

同一个来源 Strand 的全部 Track 共享一条 Sidecar private Strand。`track_name` 只选择主 Strand与 private Strand 各自的 Track projection/write target，MUST NOT 进入 private Strand reuse key。来源 Message id 只可作为 routed exchange 的 actor-private timeline anchor，MUST NOT 产生另一条 private Strand。客户端不得以当前 URL、组件树、标题或激活的 Track 反推 context identity。

Sidecar private Strand 是完整 Strand，可拥有来源 Strand 对应的 `synthesis`、`discussion` 与 profile-defined future Tracks。Track 可在首次 private write 时惰性建立；未建立的 private Track 表示 private empty state，客户端 MUST NOT 因缺少 private Track 而回退显示或写入来源 shared Track。

`agent_sidecar_of` 是 weak-semantic、non-structural、non-cascading private Relation。其 effective scope 使用 backing Circle；目标公共对象不得保存反向 relation 或可枚举 Sidecar locator。

## 7. Controller-private projection、寄宿显示与回显

Sidecar 没有独立用户可见页面、route、drawer workspace、导航项或 private Strand deep link。客户端必须在 `normalized_context_ref` 对应的主 Strand shell 内显示 Sidecar，始终保留来源 Strand的 title、breadcrumb 与 Track tabs，并在 Strand header 与 Track tabs 之间持续显示 private-context bar、E2EE/仅本人可见状态、当前 write target 与退出入口。Sidecar 不得表现为第四个 Track Tab 或普通 Circle。

controller-private 状态只有 `ak.schema.agent_sidecar_view_state.v1` 属于 encrypted Account Data：它使用 key `ak.agent.sidecar_view_state.v1:<controller_id>:<target_realm_id>:<target_strand_id>`，按 context 保存 `display_mode`、pin/折叠状态与跨设备 HLC。`display_mode` 只有 `context_merged` 与 `sidecar_only`；首次激活默认 `context_merged`。key 中的 controller/Realm/Strand components MUST 与解密后的 schema 字段 bit-identical；owner、key binding、schema 与 AEAD AAD 任一不匹配 MUST fail closed。

`ak.schema.agent_sidecar_exchange_projection.v1` **不是 Account Data 或 wire object**，只是 controller 设备本地可删除的 Event-fold cache/SDK DTO。Exchange 的 request、response、coordinator 与 terminal state 全部以 §7.2 的 Sidecar private Strand Event 为真相源；设备不得上传、跨设备合并或通过 account stream 分发 exchange projection。Agent runtime 既不接收 projection，也不接触 controller account secret。view state 与本地 exchange cache 均不得修改目标 Strand `tracks`、metadata、Relation、watch、unread、search、notification 或 shared history state。

### 7.1 显示模式与多 Track projection

`display_mode` 是 Strand-level private view state，切换 Track 后保持生效：

- `context_merged`：显示当前 Track 的来源 shared projection 与 Sidecar private projection。Timeline Track 使用 `(causal position, HLC, event id)` 的确定性增量 interleave；若 schema/profile 没有注册 merge adapter，文档/状态 Track MUST 渲染只读 shared base + private overlay，不得猜测性字段合并。
- `sidecar_only`：只显示当前 private Track projection；private Track 缺失时显示 private empty state，不得回退 shared 内容。

两种模式下，只要 Sidecar active，全部 Track write target 都固定为 private Strand 的对应 Track，shared projection 只读。切换 mode 不得创建/迁移 Event，不得改变 access、MLS scope、read/unread、watch、notification、search 或来源 Strand state。退出 Sidecar 后，客户端恢复该 Track 原 shared scroll/editor/draft；private draft 不得进入 shared editor。

所有 merged content 必须持续显示 shared/private provenance 与当前 editor destination。若同一 private request Event 已由本地 exchange fold 作为来源 echo 合并进当前 timeline，private Track fold MUST 按 Event id 去重，只显示一次，不得依赖本地数组下标或 DOM identity。

### 7.2 Routed exchange 与 timeline anchor

`source_track_routed` 表示 controller 在 shared Track 提交前由客户端拦截的 owned-Agent selector 请求。该请求 MUST 只在 Sidecar private Track 创建真实加密 Event，其 encrypted metadata plaintext MUST 携带 §7.2.1 定义的 `role=request` exchange binding；来源 shared Track MUST NOT 创建 Message/Event。`sidecar_native` 表示 Sidecar active 时直接写入 private Track 的 Event，只存在于 private Strand，MUST NOT 携带 exchange binding，也不进入 source echo fold。

request binding 的 `source_frontier_anchor` 是发送时 controller 已看到的最新 shared Event，可在没有已见 Event 时省略；`source_hlc` 与 `client_order_key` 始终必填。同一 anchor 后的 echoes 按 `(source_hlc, exchange_id)` 字节序稳定排序。anchor 尚未同步时本地 fold 暂存；anchor 到达后归位。anchor 被 retention 删除时，在对应日期的 actor-private 区域显示并标注来源位置不可用。客户端本地数组下标、接收时间与数据库自增 id 不得参与跨设备排序。

echo 只渲染 controller 的 private request Event、明确列入 `user_facing_response_event_ids` 的本 exchange 用户可见回复，以及失败/重试状态。`user_facing_response_event_ids` 的唯一合法追加路径是 §7.2.2 的 controller 设备验证；实现 MUST NOT 由 `reply_to`、Event 到达顺序、actor kind、content kind、正文前缀、工具运行状态或"exchange 后第一条/最后一条 Agent Message"推断回显资格。Agent-to-Agent 内部消息、chain-of-thought、scratchpad、tool raw output、draft history、其它 exchange 与任何 private locator 均不得回显。每个 echo 持续显示 controller-only Private Sidecar 可见性标识，不能只在 hover 时披露。

本地 cache 写入失败或丢失不影响 exchange。controller 设备从已接受的 private request Event 与后续 exchange Events 重建，不得再次投递 Agent 请求；服务端不参与 fold，也不解密任何 Sidecar 明文。

### 7.2.1 Exchange binding（producer 语义）

`ak.schema.agent_sidecar_event_exchange_binding.v1`（[`agent-sidecar-event-exchange-binding.schema.json`](../../artifacts/schemas/agent-sidecar-event-exchange-binding.schema.json)）是把一条 Sidecar Event 绑定到一个 source-routed exchange 的唯一 closed 机制。它只能出现在 effective scope 为该 Sidecar backing Circle 的 Message Event 的 `encrypted_metadata` plaintext（`message_metadata.sidecar_exchange_binding`）中：

- 明文 `metadata` 携带该 key、或任何 shared Realm/Circle Event payload 在 wire 上携带该 key/schema id/`exchange_id`，MUST 以 `schema_violation` 拒绝（见 [`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。
- 从非 Sidecar scope 解密得到的 binding，客户端 MUST 视为 non-echo 并不得渲染其存在。

producer 义务按角色闭合；所有 exchange Event MUST 携带顶层 `hlc`。binding 内对 request 的引用一律使用 accepted **Event id**（`request_event_id`），Message id 不是合法引用形式：

1. **Controller（`role=request`）**：提交 routed request Event 时写入 `exchange_id` 与完整 `request_context`（`source_track_ref`、`source_hlc`、`client_order_key`、`addressed_agent_ids`、`completion_policy=coordinator`、可选 `coordinator_agent_id`/`source_frontier_anchor`）。当 addressed 集合只有一个 Agent 时，`coordinator_agent_id` MAY 省略并隐含为该 Agent；集合大于一个时该字段必填。无论是否省略，coordinator MUST 属于 `addressed_agent_ids`。`request` binding MUST NOT 携带 `request_event_id`。
2. **Agent runtime（`role=user_facing_response`）**：真正面向用户的响应 Event MUST 携带同一 `exchange_id`、`request_event_id=` accepted request Event id，并在顶层 `refs[role=after]` 引用该 request。`completes_exchange=true` 只是 coordinator 的完成请求，不直接改变终态；此时还 MUST 携带 `coordinator_assignment_event_id`（初始 assignment 使用 request Event id，重分配后使用对应 control Event id）。
3. **Agent runtime（`role=internal`）**：由该 exchange 触发的 Agent-to-Agent 协作、tool 输出等内部 Event MUST 显式携带 `role=internal` 与同一 `exchange_id`/`request_event_id`，并在顶层 `refs[role=after]` 引用 request。省略 binding 的 Event 按下段规则安全地视为 non-echo；schema 无法证明一个本应属于 exchange 的 producer Event 是否漏标，SDK typed builder 与 conformance runner MUST 捕获该 producer 缺陷。
4. 与任何 exchange 无关的 Event（含全部 `sidecar_native` 写入）MUST NOT 携带 binding。

未携带 binding、schema 不匹配、role 未知或字段校验失败的 Event 一律 fail closed 为 non-echo；这是缺省结果，不是错误状态。Agent runtime 从收到的 request Event binding 获得 exchange identity，MUST NOT 从 projection、`reply_to`、消息正文或到达顺序推断。

`role=request` binding 有消费侧验证：仅当携带它的 Event actor 是该 Sidecar controller、effective scope 是 backing Circle、`strand_id` 是该 context private Strand、coordinator 规则成立且 request Event 已 accepted 时有效。非 controller actor 携带的 request binding 整体无效。

`exchange_id` 的幂等域是 `(controller_id, private_strand_id, exchange_id)`。同一域出现多个不同的有效 request Event 时，canonical request 是 controller accepted actor chain 中 `actor_seq` 最小的 surviving Event；同 sequence sibling 先按 §7.2.3 相同的 `event_digest` bytewise-max 规则决胜。更高 sequence 的同 id request 是 retry duplicate，即使正文或 `request_context` 不同也不得执行或进入 fold；实现 MAY 记录 controller-local equivocation 诊断。Agent runtime MUST 持久化 `exchange_id → canonical request_event_id`，同一 `exchange_id` 再出现不同 request Event id 时 fail closed，不能因 tuple 不同而执行第二次。

### 7.2.2 Runtime 消费门与 controller response 验证

Agent runtime 执行 request 前 MUST 同时验证：§7.2.1 的 request binding 有效且 Event 是该 `exchange_id` 的 canonical request；runtime 自身 principal 位于 `request_context.addressed_agent_ids`；自身当前为 active、eligible、effective-access 且目标设备 MLS-ready；本地尚未消费该 `exchange_id`；持久映射不存在不同 request Event id；exchange 未被 §7.2.3 的有效 terminal control 关闭。任一失败都把 request 当作不存在，不执行、不报 shared 错误。非 addressed backing-Circle 成员即使能解密也 MUST fail closed；它只能经 addressed Agent 显式 A2A 委托参与 internal 协作。

controller 客户端解密候选 Agent Event 后，MUST 全部通过下列检查才可把其 Event id 纳入本地 fold 的 `user_facing_response_event_ids`：

1. Event 的 effective scope 是该 Sidecar backing Circle，且 Event 的 `strand_id` == projection 的 `private_strand_id`（backing Circle 可承载多个 context 的 private Strand，缺少 Strand 绑定会造成跨 context 回显串扰）；
2. binding 通过 `ak.schema.agent_sidecar_event_exchange_binding.v1` closed 校验；
3. `binding.exchange_id` 与 projection 的 `exchange_id` 逐字一致；
4. `binding.request_event_id` == projection 的 `private_request_event_id`；
5. Event actor 是该 exchange `addressed_agent_ids` 中的 Agent principal（echo 资格只授予 addressed Agent；MUST NOT 是 controller 本人）；
6. `binding.role == user_facing_response`；
7. 顶层 `refs[role=after]` 包含 `binding.request_event_id`，且该 Event id 尚未在 fold 中出现（重复到达幂等）。

`user_facing_response_event_ids` 按 `(response Event HLC, Event id)` 字节序升序；Event HLC 只用于显示排序，不参与授权或 causal dominance。

`participating_agent_ids` 是 controller 设备的记账集合，不授予 echo 资格：非 controller 的 Event actor 通过检查 1–4 且 `role ∈ {internal, user_facing_response}` 时（即检查 5/6/7 之外全部通过），controller 设备把该 actor 并入集合（集合并集、幂等），用于呈现 working/参与状态。非 addressed Agent 的 `user_facing_response` 即使 binding 完全正确也保持 non-echo——多 Agent 协作的用户可见结论 MUST 由 addressed Agent 以自己的 `user_facing_response` Event 交付。

任何一条不满足 → non-echo：不纳入 fold、不推进状态、不向 shared surface 报错；客户端 MAY 记录 controller-local 诊断。若 response 携带 `completes_exchange=true`，仅当 actor 等于该 `coordinator_assignment_event_id` 建立的有效 coordinator 时，controller 设备才可自动 author §7.2.3 的 `action=close` control Event，并把该 response 纳入 control 的 `response_event_ids`；非 coordinator 的 completion 请求被忽略，但通过上述检查的正文仍可回显。

### 7.2.3 Durable control Event 与终态冲突

`ak.agent.sidecar.exchange.control` 是独立的 durable private-Strand Event。外层 payload 只有 `strand_id` 与 MLS `encrypted_payload`；解密明文 MUST 通过 `ak.schema.agent_sidecar_exchange_control.v1`（[`agent-sidecar-exchange-control.schema.json`](../../artifacts/schemas/agent-sidecar-exchange-control.schema.json)）。服务端 admission 与 consumer 都 MUST 验证 effective scope 是对应 backing Circle、`strand_id` 匹配、actor 是 Sidecar controller；Agent-authored control 一律无效。consumer 还 MUST 验证明文 `request_event_id` 是同一 `exchange_id` 的 canonical request。外层 `refs` MUST 为明文 `basis_event_ids` 的每一项携带 `role=after`，canonical request Event 必须被该 causal frontier 覆盖；`response_event_ids` 必须恰好是该 basis 覆盖且通过 §7.2.2 的 user-facing response 集合，并按 `(HLC, Event id)` 排序。

同一 exchange 的 control 只按 controller 的 accepted actor chain 排序：先按 `actor_seq` 升序；同一 sequence 出现合法 sibling 时，只有 `event_digest` bytewise 最大者进入 control fold，其余保留为可审计 conflict loser。数据库到达顺序、Sync 返回顺序、HLC 与本地时间不得决胜。按该顺序处理：

- `reassign_coordinator` 仅在非终态有效；`expected_coordinator_agent_id` 必须等于当前 coordinator，`coordinator_agent_id` 必须与 expected 值不同、属于 request 的 `addressed_agent_ids` 且 authoring 时 eligible。成功后该 control Event id 成为新的 `coordinator_assignment_event_id`。
- `close`、`cancel`、`fail` 都是 terminal action。第一条有效 terminal control 吸收终态；其后的全部 control（含 reassign）忽略，不得改变 projection。
- terminal action 的 `response_event_ids` 非空时统一落 `complete`。这明确覆盖 `cancel + response`、`fail + response`：已交付的响应不是失败。
- `response_event_ids=[]` 时：`close` 落 `failed/controller_closed_empty`；`cancel` 落 `failed/controller_cancelled`；`fail` 落 `failed/<failure_code>`。因此 complete 始终至少一个 response，failed 始终没有 response。

Agent pause/deactivate、MLS removal、超时、Event 缺席都不会隐式改变 exchange。非 coordinator Agent 失效不影响终态；coordinator 失效后 exchange 保持非终态，直到 controller 写入 reassign、cancel 或 fail control。controller 自动化 MAY 因已验证 lifecycle 事实 author `fail/failure_code=agent_deactivated`，但该 control Event 本身才是可重放真相。

### 7.2.4 确定性 fold、本地 cache 与恢复

fold 输入只包含有效 controller request Event、通过 §7.2.2 的 Agent binding Events，以及按 §7.2.3 决胜后的有效 control Events。没有 terminal control 时，纳入当前已验证 history 中的全部上述 exchange Events；存在 terminal control 时，只纳入该 terminal 的 `basis_event_ids` causal closure 覆盖的 Agent binding Events，以及 control fold 中截至该 terminal（含本 Event）的有效前缀。与 terminal 并发但未被其 basis 覆盖、或因果上晚于 terminal 的 Agent/control Events 一律保留为私有审计历史但不进入 exchange projection。status 是纯函数：

- 仅有已接受的 request，或存在 internal/其它合法 Agent binding 但无 response：`delivered`；
- 存在 response、但无 terminal control：`responding`；
- terminal control 按 §7.2.3 映射为 `complete` 或 `failed`。

`AgentSidecarExchangeProjection` 只可写入 controller 设备本地缓存。其 write-once 字段来自 request binding/accepted Event scope；coordinator 字段来自 request 与有效 reassign；response/terminal 字段来自上述 fold。`folded_frontier.event_ids` 是所有参与 fold Event 的**最大 causal head 集合**，按 Event id UTF-8 字节序排序；它不是“最后一个 Event”。`event_set_digest = sha256(canonical_json(<全部参与 fold Event id 的排序去重数组>))`；`max_hlc` 是参与 Event HLC 的最大值，只用于显示与缓存诊断，不证明因果覆盖。

设备只有在本地已验证 Event frontier 与 cache frontier 相等，或本地 frontier causally dominates cache 的全部 heads 时，才可使用/增量推进 cache；两者不可比较时 MUST 补齐缺失 Event 并从联合 history 重新 fold，禁止用 HLC/LWW 选择赢家。cache 永远不得覆盖或回退当前内存中的已验证 fold/UI；不满足校验时立即丢弃。由于 cache 不上传、不进入 account stream，不存在密文合并、远端 stale writer 或 Account Data CAS 问题。

controller 离线时 response/control 留在 private history。新设备或 cache 丢失时扫描对应 private Strand 中 controller-authored request binding，验证后重放相关 Agent/control Events；不得再次投递请求。给定相同 accepted Event 集，所有 conforming 设备 MUST 得到 bit-identical projection、frontier digest、response 顺序与 terminal outcome。

request Event 提交被拒时没有 durable exchange；失败呈现属于 client-local pending-submission state，同一 intent 重试使用相同 `exchange_id`。实现 MUST NOT 由时间流逝、Event 缺席、内容或本地任务状态推断 `failed`/`complete`。

### 7.2.5 信任边界

binding 把“Agent 声明 user-facing/internal”与“controller 写入控制事实”分离。验证保证绑定、归属、scope、coordinator 与幂等，不保证内容语义适合用户；被攻陷的 addressed Agent 最多造成 controller-private 回显污染，不能突破既有 Sidecar MLS 可见性。服务端不解密 Message binding、control plaintext 或本地 projection；controller account secret 不共享给 Agent principal。

### 7.3 显式 Publish 与存在性隐私

Sidecar 发布到共享 Strand 必须由 controller 显式确认，只创建符合目标 scope 的正常 shared event。shared event、日志、URL、push preview 与公开 telemetry MUST NOT 携带 `sidecar_id`、`backing_circle_id`、private Strand/Relation id、private messages、scratchpad 或 draft history；只可携带规范允许的 opaque digest。

未授权 caller 对 Sidecar 的 list/get/search、backing Circle existence、private Strand/Relation existence MUST 收到与不存在资源相同的固定错误 envelope、字段集合与 timing bucket。

## 8. UI 安全不变量

本节是 **client-presentation safety conformance**，只约束向人类呈现 Sidecar 激活、写入、访问状态或导航入口的客户端 surface；不向人类呈现 UI 的 headless SDK、service worker 与 agent runtime 不承担控件/布局义务，但向上层 UI 暴露 Sidecar projection 时 MUST 原样提供 private/shared provenance、effective access、MLS readiness 与 write target，使实际呈现方能够履行下列不变量。具体控件布局与文案可由实现选择，不得改变每条可测试安全结果。

1. Sidecar MUST 使用主 Strand 寄宿 surface，不得进入 Circle 目录、Circle 创建器、Circle 成员管理、独立页面/route/drawer/navigation 或 Strand Track tabs。
2. 从 shared surface 激活 Sidecar 时，客户端 MUST 留在同一主 Strand shell，明确显示进入“仅 controller 与其 AI Agents 可访问”的个人私有 scope，并提供退出 Sidecar 的入口。
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
