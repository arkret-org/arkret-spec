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
  "kind": "ak.sidecar.desired_access.v1",
  "sidecar_id": "ak:sidecar:...",
  "realm_id": "ak:realm:...",
  "controller_id": "did:...",
  "principal_ids": ["did:..."]
}
```

`principal_ids` MUST 等于完整 `desired_sidecar_access(S)`（包含 controller），按 DID UTF-8 byte lexicographic 升序排列且去重；digest 为 `sha256:<lowercase-hex(SHA-256(JCS bytes))>`。任何实现不得使用 UI 顺序、Circle member 顺序、设备 id、display name、到达时间或本地数据库 id 参与该 digest。

`mls_context.control_frontier` 是服务端当前用于物化 Sidecar 与 backing membership 的 accepted control refs：MUST 包含 effective `ak.sidecar.create` ref、controller backing join ref，以及每个 desired Agent 当前 backing join ref；按 ref UTF-8 byte lexicographic 升序排列且去重。Admission 还 MUST 以当前 accepted eligibility/control state 重新计算 desired set；control frontier 与 digest 都匹配也不能绕过 freshness、revocation 或 policy 检查。

- 新 Agent 进入 desired access 后，在 backing Circle membership、Add Commit accepted、匹配的 `ak.mls.welcome` accepted、目标设备成功 consume 同一 KeyPackage claim 全部完成前不得接收 Sidecar payload。一个 Agent principal 至少有一个仍 active/authorized、未被 remove 的设备满足上述证据时进入 `effective_agent_ids`；其它设备不会因 principal 已 effective 自动获得密钥。
- controller 当前调用设备只在它是 accepted genesis 的 `creator_device_id`，或已完成同样的 Welcome/consume 证据时视为 device-ready。`access_readiness=ready` 要求当前 controller 设备 ready，且每个 `desired_agent_ids` principal 都已 effective；因此同一 Sidecar 在 controller 的不同设备上 MAY 暂时呈现不同 readiness，但 `desired_agent_ids`/`effective_agent_ids` 必须一致。
- Agent 离开 desired access 时，服务端 MUST 在同一 control-state apply 中立即停止寻址/投递、移除 backing membership 并产生 durable pending MLS removal obligation。持有该 backing Circle 当前 MLS snapshot 的 controller 设备或 policy-authorized key service MUST 通过普通 `ak.mls.proposal` + `ak.mls.commit` 完成 remove/rotate；普通 Principal Server 不得伪造 Commit。没有 eligible committer 时发送保持 fail closed，obligation 保留并允许 §5.3 takeover。
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
- admitted device row：accepted Add Commit、引用该 Commit 的 accepted `ak.mls.welcome`、与 Welcome 相同的 `(group, recipient principal, recipient device, keypackage_ref)`，以及目标设备 authenticated consume 成功；
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

controller-private projection 分成两个加密 account-data plaintext schema：

- `ak.schema.agent_sidecar_view_state.v1` 使用 key `ak.agent.sidecar_view_state.v1:<controller_id>:<target_realm_id>:<target_strand_id>`，按 context 保存 `display_mode`、pin/折叠状态与跨设备 HLC。`display_mode` 只有 `context_merged` 与 `sidecar_only`；首次激活默认 `context_merged`。
- `ak.schema.agent_sidecar_exchange_projection.v1` 使用 key `ak.agent.sidecar_projection.v1:<controller_id>:<target_realm_id>:<target_strand_id>:<exchange_id>`，每个 source-routed exchange 独立一条记录。它保存强类型 `origin=source_track_routed`、Track sub-key、anchor、HLC、stable order key、addressed/participating Agents、private request Event、显式 user-facing response Events 与状态。每 exchange 独立记录使 account stream 可增量 fold，客户端 MUST NOT 在每次更新时解密、重写或重放该 context 的完整 echo 历史。

上述 key 中的 controller/Realm/Strand/exchange components MUST 与解密后的 schema 字段 bit-identical；owner、key binding、schema 与 AEAD AAD 任一不匹配 MUST fail closed。两类 projection 只可从 actor-private account stream 返回给 controller 及明确获得该 account-data scope 的 Agent runtime。它们不得修改目标 Strand `tracks`、metadata、Relation、watch、unread、search、notification 或 shared history state。

### 7.1 显示模式与多 Track projection

`display_mode` 是 Strand-level private view state，切换 Track 后保持生效：

- `context_merged`：显示当前 Track 的来源 shared projection 与 Sidecar private projection。Timeline Track 使用 `(causal position, HLC, event id)` 的确定性增量 interleave；若 schema/profile 没有注册 merge adapter，文档/状态 Track MUST 渲染只读 shared base + private overlay，不得猜测性字段合并。
- `sidecar_only`：只显示当前 private Track projection；private Track 缺失时显示 private empty state，不得回退 shared 内容。

两种模式下，只要 Sidecar active，全部 Track write target 都固定为 private Strand 的对应 Track，shared projection 只读。切换 mode 不得创建/迁移 Event，不得改变 access、MLS scope、read/unread、watch、notification、search 或来源 Strand state。退出 Sidecar 后，客户端恢复该 Track 原 shared scroll/editor/draft；private draft 不得进入 shared editor。

所有 merged content 必须持续显示 shared/private provenance 与当前 editor destination。若同一 private request Event 已由 `ak.agent.sidecar_projection.v1` 作为来源 echo 合并进当前 timeline，private Track fold MUST 按 Event id 去重，只显示一次，不得依赖本地数组下标或 DOM identity。

### 7.2 Routed exchange 与 timeline anchor

`source_track_routed` 表示 controller 在 shared Track 提交前由客户端拦截的 owned-Agent selector 请求。该请求 MUST 只在 Sidecar private Track 创建真实加密 Event，随后以相同 `exchange_id` 幂等写入 exchange projection；来源 shared Track MUST NOT 创建 Message/Event。`sidecar_native` 表示 Sidecar active 时直接写入 private Track 的 Event，只存在于 private Strand，MUST NOT 创建 source echo projection。

exchange projection 的 `source_frontier_anchor` 是发送时 controller 已看到的最新 shared Event，可在没有已见 Event 时省略；`source_hlc` 与 `client_order_key` 始终必填。同一 anchor 后的 echoes 按 `(source_hlc, exchange_id)` 字节序稳定排序。anchor 尚未同步时 projection 暂存；anchor 到达后归位。anchor 被 retention 删除时，在对应日期的 actor-private 区域显示并标注来源位置不可用。客户端本地数组下标、接收时间与数据库自增 id 不得参与跨设备排序。

echo 只渲染 controller 的 private request Event、明确列入 `user_facing_response_event_ids` 的本 exchange 用户可见回复，以及失败/重试状态。Agent-to-Agent 内部消息、chain-of-thought、scratchpad、tool raw output、draft history、其它 exchange 与任何 private locator 均不得回显。每个 echo 持续显示 controller-only Private Sidecar 可见性标识，不能只在 hover 时披露。

private Event 成功但 projection 写入失败时，客户端/服务端用同一 `exchange_id` 从已接受的 private request Event 重建 projection，不得再次投递 Agent 请求。projection 成功但响应丢失时，同一 key 幂等返回。account stream 重连只增量 fold 变更记录；不得要求来源 Realm 重放 private Event。

### 7.3 显式 Publish 与存在性隐私

Sidecar 发布到共享 Strand 必须由 controller 显式确认，只创建符合目标 scope 的正常 shared event。shared event、日志、URL、push preview 与公开 telemetry MUST NOT 携带 `sidecar_id`、`backing_circle_id`、private Strand/Relation id、private messages、scratchpad 或 draft history；只可携带规范允许的 opaque digest。

未授权 caller 对 Sidecar 的 list/get/search、backing Circle existence、private Strand/Relation existence MUST 收到与不存在资源相同的固定错误 envelope、字段集合与 timing bucket。

## 8. UI 安全不变量

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
