---
title: Relation
status: candidate
normative: true
stability: v1
updated: 2026-09-20
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

`relation`（`ak:relation:`）是 Arkret 协作图的**一等关系对象**。跨对象语义 MUST 使用 Relation 表达，而不是藏在对象字段里。

Relation 连接的是对象引用：标准字段使用 `from_ref` / `to_ref`，其值可以指向 `realm`、`space`、`actor_profile`、`strand`、`message`、`morph`、`relation`、`event`、`view`、`blob` 的 `ak:<kind>:` typed ID，或完整的结构化 ActorId。Actor 端点没有 actor typed-ID 对象——当端点是 Actor 时直接使用该 actor 的 ActorId object（包含 Station 归属），而不是裸 DID、Actor Profile ID 或把 ActorId JSON 编码成字符串（见 [`overview.md` §3.4](./overview.md) 与 [`common-fields.md` §4.1](./common-fields.md#41-did-适用边界)）。

> **端点 kind 子集与其它"可引用 kind 子集"字段的关系（informative）**：Relation 端点允许的 kind 集合与 Notification `source_ref`（[`private-objects.md` §3.2](./private-objects.md)）、Read Cursor `read_scope`（[`private-objects.md` §2.2](./private-objects.md)）各自不同；差异由各自语义决定（Relation 端点 = 可连边的图节点，故含 `realm` / `event` / ActorId；Notification = 可被通知指向的内容对象；Read Cursor = 可定位已读位置的时间线容器）。三处实现 MUST 按各自 schema 校验字段形状，同时以 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `referenceability` 作为 typed-id kind 子集的机读真相源；Relation 端点对应 `relation_endpoint` 类别。ActorId 端点不属于 typed-id kind，由 `common-ids.schema.json#/$defs/actor_id` 与 `common-fields.md` §4.1 约束。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

联系人关系不是 Relation。`ak.relation.*` 是 Realm-scoped 协作图边，`realm_id` 必填；跨 Realm 的联系人请求、接受、拒绝、tombstone 与 direct conversation binding 的真源是 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md) 定义的 principal-scoped facts。实现 MUST NOT 用 `relation_kind=contact` 或等价自定义 Relation 替代 `ak.contact.*`。

Realm 端点只允许普通内容引用。Realm 之间的治理、发现、继承、迁移、mirror 或 confidential-extension 边的唯一真源是 [`realm-links.md`](./realm-links.md)；实现 MUST NOT 用 `ak.relation` 表达这些边，也 MUST NOT 从 Realm 端点 Relation 派生 membership、capability、policy、history、E2EE 或 federation 语义。

## 2. Schema 与字段

Schema id: `ak.schema.relation.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:relation` | 以 `ak:relation:` 开头。 | Relation ID。 |
| `schema` | yes | `ak.schema.relation.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | Relation 所在 Realm。 | 所属 Realm。 |
| `scope_circle_id` | no | `id:circle` | 通用 scope 派生与校验以 [`circle.md` §6](./circle.md) 为唯一权威；`confidential_discussion_of` 按 §3.1 MUST 指向 private Strand 的 Circle。Sidecar context mapping 使用原生 `sidecar_context`，不是 Relation。 | 该 Relation 事实的 Circle 作用域。 |
| `effective_scope` | no | `object` | 通用只读 projection 规则以 [`circle.md` §6](./circle.md) 为唯一权威；结构关系 MUST NOT 宽于参与端点中最窄的作用域。 | 派生的有效作用域。 |
| `relation_kind` | yes | `string` | 标准值见 §3。 | 关系语义。 |
| `from_ref` | yes | `RelationEndpoint` | MUST 是合法 typed object-reference string 或完整 ActorId object。 | 起点对象/Actor/Realm 引用。 |
| `to_ref` | yes | `RelationEndpoint` | MUST 是合法 typed object-reference string 或完整 ActorId object。 | 终点对象/Actor/Realm 引用。 |
| `rank` | no | `string` | 见 [`../conformance/encoding.md` §9.1](../conformance/encoding.md) 的 `ak.rank.lexofractional.v1` 语法。**与 Space.rank 顶层字段对齐**——v1 把 rank 提升到顶层，`fields.rank` 在 wire 上 MUST 被拒绝（`schema_violation`），不接受双源并存。 | 有序关系（如 `contains list -> strand`）的稳定 rank。 |
| `fields` | no | `object` | 可放 role、edge metadata；MUST NOT 包含 `rank`（已提升到顶层）。 | 关系属性。 |
| `state` | no | `enum(active, tombstoned)` | `tombstoned` 同时覆盖删除与 redaction；若操作提供原因，原因保存在对应 `ak.relation.tombstone` / `ak.redaction` event 上，物化对象只保留当前状态。 | 关系状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `ActorId` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

**生命周期（normative）**：Relation 的 `state` 只取 `active` / `tombstoned` 两值，**没有 `archived` 态**——这是有意取舍，区别于含 `archived` 的 Circle / Morph 等对象（[`common-fields.md` §5.2](./common-fields.md) 模板）：Relation 是一等边，要么有效（`active`）要么作废（`tombstoned`，不可逆，由 `ak.relation.tombstone` / `ak.redaction` 写入），不存在"暂时收起、可恢复"的中间态。需要"软隐藏"某条关系时，由查询 / projection 层过滤，不引入额外 canonical 生命周期态。生命周期仅 `active → tombstoned` 单向迁移。

**Relation 写入 payload（normative）**：`ak.relation.create`、`ak.relation.update` 与 `ak.relation.tombstone` 都携必填 `primary_conflict_domain`，它是 `relation` typed current result 的唯一 subject（Realm 取自 Event envelope）。Reducer MUST 按 `relation-kind-registry.json` 复算并验证该 domain：`tuple` 精确绑定 `(relation_kind, from_ref, to_ref)`，`from` 精确绑定 `(relation_kind, from_ref)`；Circle 不进入 key，派生 `truth_source` shape 不能直接写 Relation。调用方自报的 domain 与 payload／当前 Relation 不一致时 MUST `schema_violation` 且零写入。

`create.relation` MUST 是 closed `relation_definition`，且只可包含 `scope_circle_id`、`relation_kind`、`from_ref`、`to_ref`、`rank`、`fields`；其中后三个 identity 字段必填，`scope_circle_id`、`rank`、`fields` 可选。create-time rank 的唯一签名路径和唯一投影 consumer 是 `payload.relation.rank`；`payload.rank` 不存在并 MUST 以 `schema_violation` 拒绝。完整物化 Relation 的 `schema`、`realm_id`、`id`、`effective_scope`、`state`、`state_changed_at`、`created_by`、`created_at`、`updated_by`、`updated_at` 均由 Reducer 派生或维护，不得作为 authoring input 回流。

`create.expected_revision` 是 `CurrentRevision | null`：domain 从未写入时必须为 `null`；当前值为 `tombstoned` 时可携其 exact revision 创建一个新的 event-derived RelationId；当前值仍为 `active` 时即使 revision 匹配也 MUST `failed_precondition`。`update` 与 `tombstone` 同时携 `relation_id` 和 exact `expected_revision`，Reducer MUST 验证 domain 当前值的 `id` 与 `relation_id` 相同且为 `active`。stale revision、错误 id、目标不存在／跨 Realm／已 tombstone 都 MUST `failed_precondition` 且零写入；exact replay 返回原 RealmCommit。

`relation_kind`、`from_ref`、`to_ref` 共同决定主冲突域，create 后 MUST 锁定；`ak.relation.update` 只可 patch `scope_circle_id`、`rank`、`fields`，触及身份三字段或 `effective_scope` MUST `schema_violation`。改变 kind／端点不是 update 或 move：调用方先以旧 domain 的 exact revision tombstone，再以新 domain 的 current revision（从未写入则 `null`）create 新 RelationId。这是两个独立、可重试、用户可见的操作；协议不提供跨 domain 双 CAS、隐式搬迁或原子 move。

`ak.relation.tombstone` 的可选 `reason` 只保留在 Event 上；接受后执行 `active → tombstoned`。
物化 `state_changed_at` 与 `updated_at` 必须在同一原子写入内分别由
[`common-fields.md` §3.3](./common-fields.md)
的 `object_state_transition_time` 与 `object_update_time` 产出，二者均为
`max(Event.created_at, accepting RealmCommit.committed_at)`；Relation 不定义第二套局部时间公式。
不把 reason 复制到 Relation 对象。`target_ref`、`expected_state_digest` 及 update-style `patch`
都不是 tombstone 字段。

```text
{
  "relation_id": "ak:relation:AUifoAUG8AEOHYXp999WnI7WlLt19ByDoqYUsFwbw4A4",
  "reason": "relationship no longer applies"
}
```

Canonical 方向由 `from_ref -> to_ref` 定义。反向语义 SHOULD 由查询层或 schema 派生。

**Actor 端点与去重（normative）**：`assigned_to` 的目标与 `watches` 的来源是完整协作 ActorId，而不是全局密码学 principal。两个 account Actor 即使 `principal_id` 相同，只要 `station_id` 不同，就是不同端点；授权、去重、基数、查询过滤、通知匹配与 tombstone 目标 MUST 保持该区别。端点相等按解析后的类型和值判断；需要持久化 tuple key 时 MUST 对完整结构采用 canonical JSON，不得只取 signing principal，也不得把 JSON 文本重新写入 endpoint string。既有对象引用仍是 typed ID string。`RelationQuery.source_ref` / `target_ref` 使用同一个 `RelationEndpoint` union。

最小示例：

```json schema=schemas/relation.schema.json
{
  "id": "ak:relation:AUifoAUG8AEOHYXp999WnI7WlLt19ByDoqYUsFwbw4A4",
  "schema": "ak.schema.relation.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "relation_kind": "contains",
  "from_ref": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
  "to_ref": "ak:strand:AQdknt9AByYY2gb16KB093xeB4J8b02mTEd4Mt8z2rO-",
  "rank": "U",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:zHuXvTbhiRsj2KEPE64TLhzG4","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

## 3. 标准 `relation_kind` 与基数

### 3.1 标准 kind

标准 `relation_kind` 词汇表的机器可读 source of truth 是 [`relation-kind-registry.json`](../../artifacts/registry/relation-kind-registry.json)（kind 清单、默认基数类别、truth-source 类别、可写性）；本节与 §3.2 表是其规范阅读视图，详细去重键、作用域与冲突语义以本文为权威。v1 active 集合：

对 `truth_source_class="shape_dependent"` 的 kind，SDK / producer MUST 先按 `(canonical_id, from object type/kind, to object type/kind)` 选择 registry 中最具体的 shape，再读取 `writability` 与 `write_path`；只有无具体 shape 匹配时才使用 `* -> *` fallback。这样 `contains` 的派生 placement 与直接 Relation 构造可在 builder 阶段机械区分，不能先构造 `ak.relation.create` 再依赖服务端运行时猜测。

```text
contains, belongs_to, replies_to, depends_on, blocks, mentions,
assigned_to, references, derived_from, attached_to, has_default_view,
summarized_from, promoted_from_discussion, watches,
confidential_discussion_of
```

其中 `summarized_from` 与 `promoted_from_discussion` 是弱语义引用边：registry 将二者标记为 `weak_semantic=true`，端点遵循通用 RelationEndpoint 约束；不提供开箱即用的摘要或讨论升级强语义。

> **未注册的 relation_kind 处理规则**：`produced` / `used` / `triggered_by` / `has_log` 这类名字在 v1 没有 schema / profile / fixture 定义 from/to 类型、基数或 capability action，因此在 v1 wire 上视为**未注册的 relation_kind**——实现遇到时 SHOULD 保留为不透明边并在 projection 层标记 `unknown_relation_kind`，**MUST NOT** 据此自动推断容器、依赖或可见性语义。扩展 profile 注册之前 producer 不应使用。

### 3.2 默认基数表

| `relation_kind` | 默认基数 | 作用域与去重规则 |
| --- | --- | --- |
| `contains`：`Space(kind=board) -> Space(kind=list)` | **派生投影**(derived projection only) | 一个 Board 可包含多个 List；同一 List 的 parent `current-value projection` 的当前值就是该 stream 上最后一个被接受的 `ak.space.parent` 写入，只有该当前值且未形成跨 typed current result 环时才投影 active Board parent；环属于领域 `unresolved`，不得反向改写该当前值。**Truth source 是 typed current result `space_parent:<list_space_id>`；`ak.space.create` 的 canonical `object.parent_space_id` 是该 typed current result 的 genesis 写入，后续唯一写入路径是 `ak.space.parent` Event，不是 `ak.relation.create`**。直接 `ak.relation.create / update / delete relation_kind=contains` 在该 from→to 形状上 MUST `schema_violation`（reason=`relation_kind_contains_derived`；详见 [realm-and-space.md §3.5](./realm-and-space.md)）。`contains` Relation 仍出现在标准 kinds 列表中是因为 projection / query / UI 仍按 Relation 视角读它，但**写入路径单一化**到 create genesis 或后续 `ak.space.parent`。 |
| `contains`：`Space(kind=list) -> Strand` | **派生投影**(derived projection only) with board-exclusive target | 一个 List 可包含多个 Strand；同一 Strand 在同一个 Board 的 position typed current result 的当前值由该 stream 上最后一个被接受的位置写入给出，且只向该当前值指向的 active List 投影。去重/互斥 key 为 `(board_space_id, strand_id)`，与 [realm-and-space.md §3.6](./realm-and-space.md#36-strand-位置) 的位置唯一性一致。**Truth source 是 current-value projection typed current result `strand_position:<board_space_id>:<strand_id>`，写入路径是 `ak.strand.move` / `ak.strand.reorder` Event**，不是 `ak.relation.create`。直接 `ak.relation.create / update / delete relation_kind=contains` 在该 from→to 形状上 MUST `schema_violation`（reason=`relation_kind_contains_derived`，与 `watches` derived Relation 同模式）。 |
| `contains`：其他对象组合(非 Space 容器场景，例如 `Strand -> Strand` subtask / checklist item) | `many_to_many` | 按完整 tuple 去重；普通包含记录不自动引入额外数量限制或级联规则。这种非派生形态的 `contains` 由 `ak.relation.create` 直接写入，不得与 Board/List 的派生 `contains` 混用。 |
| `belongs_to` | `many_to_one` | 作为 `contains` 的显式 parent 关系时，同一 `from_ref` 在同一作用域内至多有一个 active `to_ref`。优先使用 canonical `contains` 表达容器包含。 |
| `replies_to` | `many_to_one` | 一个 Message 或 reply object SHOULD 只有一个 direct parent；额外链接用 `references` 或 `mentions`。 |
| `depends_on`, `blocks` | `many_to_many` | 按 `(realm_id, relation_kind, from_ref, to_ref)` 去重；循环检测由 workflow/profile 规则决定。 |
| `mentions`, `references`, `derived_from`, `attached_to`, `summarized_from`, `promoted_from_discussion` | `many_to_many` | 按完整 tuple 去重；关系属性写在 `fields` 中，不改变去重键。`summarized_from` 与 `promoted_from_discussion` 按通用弱语义引用边处理。 |
| `assigned_to` | `many_to_many` | Canonical 方向为 `Strand -> ActorId`（`from_ref=<strand_id>`, `to_ref=<ActorId object>`）。默认 `many_to_many`，按完整 tuple `(realm_id, relation_kind, from_ref, to_ref)` 去重(同一 (Strand, Actor) 对至多一条 active edge，即同一 Actor 不重复分配)；一个 Strand MAY 同时分配给多个 Actor。**这是按完整 tuple 去重，不是 per-actor 单值约束。** 分配仅为关系记录，不改变成员身份、角色或访问权限；应用层单负责人规则见 §5。Strand object / `metadata.fields` 不得携带 `assignee` / `assignees` / `assigned_to` 字段作为替代真源；见 [strand-and-message.md §7.1](./strand-and-message.md#71-assignment--assignee-投影)。 |
| `watches`：`ActorId -> strand` | **派生投影**（derived from typed current result, not directly writable） | 每个 `(from_ref, to_ref)` 至多一条 active edge；`from_ref` MUST 是完整 ActorId object，`to_ref` MUST 指向 Strand（或 profile 声明的 watchable 对象）。**Truth source 是 current-value projection typed current result `strand_watch`，写入路径是 `ak.strand.watch.set` durable event，不是 `ak.relation.create`**——直接 `ak.relation.create / update / delete relation_kind=watches` MUST `schema_violation`（reason=`relation_kind_watches_derived`；与派生 `contains` Relation 的双源约束同模式，见 [`./realm-and-space.md` §3.6](./realm-and-space.md#36-strand-位置)）。写入 invariant：`payload.watcher_actor_id == envelope.actor_id`，除非 actor 持有 `ak.strand.watch.set.others` capability。级别枚举、投影脱敏、通知路由见 [strand-and-message.md §8](./strand-and-message.md)。 |
| `has_default_view` | `many_to_one` | 同一 `from_ref` 在同一 Realm 内至多有一个 active default View；设置新默认 View MUST 关闭旧 active edge。 |
| `confidential_discussion_of` | `many_to_one` | weak-semantic、non-structural、non-cascading。`from_ref` MUST 是 private Strand，`to_ref` MUST 是其 public authority commit Strand。该 relation fact MUST 提交在 `from_ref` 所在 Circle scope（即 payload `scope_circle_id` 指向 private Strand 的 Circle，使 `effective_scope = circle`），使 Circle 成员能从 private Strand 回到 public authority commit，而 non-member 不能从 public authority commit 侧枚举该边。**实现 MUST NOT 在目标公开 Strand 写 target-side reverse relation**。 |

Relation MUST 按 §6 以 `(realm_id, primary_conflict_domain)` 的单一 typed current result 去重。两个离线设备基于同一 revision 并发写入时，治理 Station 的原子 CAS 至多接受一个；另一个 stale Event 零写入拒绝，不产生 RealmCommit，也不进入共享 current state。

## 4. 跨 Realm 引用

### 4.1 总则

Relation 的 `realm_id` 表示关系事实所在的源 Realm；`from_ref` / `to_ref` MAY 指向其他 Realm 的对象、Actor 或 Realm。跨 Realm 引用只发布引用事实，不复制被引用对象内容，也不授予读取、写入、管理或同步被引用 Realm 历史的权限。

创建跨 Realm Relation 时，actor MUST 同时满足：

- 对 Relation 所在源 Realm 的写入能力。
- 对被引用目标的 discover/reference 能力，或目标 Realm policy 允许的等价引用能力。

### 4.2 读取与同步规则

- 引用 ID、目标类型和目标 `realm_id`（若已知）可以作为源 Realm 的 Relation metadata 同步。
- 被引用对象的标题、字段、消息、附件、成员、计数、preview 和历史只按目标 Realm 的 policy、history visibility、E2EE epoch 与 redaction policy 展开。
- 公共 Realm 引用私有 Realm 对象时，默认只能展示 opaque ref 或 Lazy Link；除非目标 Realm policy 明确允许 preview，不得泄露目标内容、成员、计数或存在性细节。
- Sync / projection 层不得因为源 Realm 可见就自动 backfill 目标 Realm；跨 Realm 展开必须重新执行目标 Realm 授权，并在响应 metadata 中标记 `ReferenceProjectionState`（见 §4.2.1），或使用能无损映射到该枚举的等价字段。

**Raw Event API 边界（normative）**：源 Realm canonical Event Store Service MAY 保存完整 `from_ref` / `to_ref` 字段以维持签名、dedupe 与 reducer determinism，但 `ak.self.committed_event.read.scan.v1` / `ak.self.committed_event.stream.subscribe.v1` / backfill / federation fanout 不是无条件 byte dump。只有同时满足源 Realm `ak.event.read` 与目标 reference disclosure 的 caller 才可取得完整 canonical payload bytes。否则授权读取面 MUST 使用 `CommittedEventView` 的 withheld 分支 `{commit,event_disclosure:{status:"withheld"}}`，不得构造 redacted Event 或 locked stub，也不得把 canonical bytes 直接 forward 给本地客户端。withheld 分支不是 reducer input，且不创建新资源、签名或存储对象。

#### 4.2.1 `ReferenceProjectionState`（normative）

跨 Realm Relation、View、Space hierarchy 或 Graph 查询在展示引用目标时 MUST 使用统一的 `ReferenceProjectionState`：

| 值 | 语义 | 可见字段 |
| --- | --- | --- |
| `accessible` | caller 已通过目标 Realm 的 discover/reference 与内容展开授权，可展示目标 policy 允许的 metadata / preview。 | 目标 policy 允许的最小 metadata；不得超出本次授权。 |
| `lazy_link` | caller 可能有后续展开路径，但当前查询深度、范围、profile 或缺失依赖要求截断为惰性链接。 | 不解引用占位、必要的 source-side relation id / digest；不得自动 backfill 目标 Realm。 |
| `locked` | 目标不存在、未发现、policy 拒绝或 caller 无权知道目标存在性；这些原因对 caller MUST 保持不可区分。 | 固定 locked stub；不得包含目标 `realm_id`、title、member_ids、created_at、issuer set、preview 或任何可区分存在性的字段。 |

响应实现 MAY 使用 `reference_projection.status`、`edge_status` 或等价字段名，但值 MUST 能无损映射到上述三值。`locked` 是 projection-only 派生状态，不写入 canonical Relation 对象，也不得与 account lifecycle 的 `locked` 混用。

### 4.3 授权拆分（两端 enforce 责任）

| 授权检查类型 | 在哪一边 enforce | 原因 |
| --- | --- | --- |
| Relation **创建**（`ak.relation.create`、`ak.relation.update`、`ak.relation.tombstone`） | **源 Realm**（Relation `realm_id`） | Relation 是源 Realm 的 reducer-input；reducer 在源 Realm 验证 actor 在源 Realm 的 capability 是否覆盖 `ak.relation.*`。 |
| 引用目标的 **discover / reference 能力** | **目标 Realm**（`from_ref` 或 `to_ref` 指向的 Realm） | 目标 Realm policy 决定是否允许该 Relation 引用自身；典型 capability `ak.object.read_metadata` 或 `ak.realm.discover`。源 Realm reducer 在 accept Relation 前 SHOULD 验证目标 Realm 的 reference 许可（通过 cached attestation / capability grant ref 等）；缺失证据时 Relation 仍可写入源 Realm，但 projection 层在展开时 MUST 重新校验目标授权，校验失败的 Relation 显示为 `locked`。 |
| 目标对象**内容展开**（标题、字段、preview） | **目标 Realm**（read 时） | 每次展开都用 reader 在目标 Realm 的 capability 重新校验；源 Realm 的可见性不传染到目标。 |
| **位置 / structural 关系**（如 `contains` 跨 Realm） | **源 Realm + 强制源 == 目标** | `contains` 这类强结构关系在 v1 **MUST NOT 跨 Realm**——结构容器（Space）必须与所属 Strand 同 Realm。跨 Realm 的引用只能用 `references`、`mentions`、`derived_from`、`summarized_from` 等弱语义关系。 |

### 4.4 Reducer 强制约束

实现 MUST：

- 在源 Realm 接收 Relation 时验证 `from_ref` / `to_ref` 的 typed prefix 与目标 Realm 一致性（`realm_id` 字段或 typed ref 解析）。
- 不得把"源 Realm 写权限"误当成"目标 Realm 引用权限"——两者是**两次独立 capability check**。
- 目标 Realm policy 拒绝引用时（例如 `discoverability=secret` + 不在 trusted issuer 列表），源 Realm 仍 MAY 接受 Relation 但**MUST**在 projection 层把它降级为 `ReferenceProjectionState.locked`，并不得泄露目标 Realm 的存在性细节。reducer 仍把 Relation 视为 `active` 写入 canonical event log；`locked` 只由 projection 在读取时对目标 Realm policy 做最新评估后派生而成。当目标 Realm 解除 policy 阻塞时，projection 在下一次重新评估时自动把同一 Relation 显示为 `accessible`（含具体目标 metadata），**无需**额外发布 "Relation unlock" 事件；同理 lock 与 unlock 之间不引入 reducer-level 状态机或新的 typed current result 类型。源 Realm SHOULD 缓存最近一次目标 policy 评估结果，以减少跨 Realm 探测；缓存 TTL 由目标 Realm `discoverability` policy 与 projection 实现 trade-off，但 MUST 在 policy 显式变更时即时失效。

> **projection 态的收敛语义（normative 澄清）**：`ReferenceProjectionState`（`accessible` / `lazy_link` / `locked`）是 **reader-local 派生视图**，由各 reader 在读取时对目标 Realm policy 做最新评估（含各自缓存 TTL）得出，因此**不要求跨 reader 收敛**：在 policy 变更的传播窗口或不同缓存 TTL 下，两个 reader 对同一 Relation 同时派生出 `accessible` 与 `locked` 是**有意取舍**，不构成收敛缺口。Relation 的 canonical state 始终为 `active`（写入 canonical event log 的唯一权威态），不随 projection 态变化；本节的「不跨 reader 收敛」仅限投影/展示层，不影响任何 canonical state、授权或 winner 选择。

**跨 Realm 强约束（reducer 必检）**：

- `contains` 与 `belongs_to` MUST NOT 跨 Realm——reducer MUST 解析 `from_ref` / `to_ref` 指向的对象（Space / Strand / Message / Morph 等），确认其 `realm_id` 与 Relation 自身 `realm_id` 一致；任一不一致 MUST `failed_precondition`（`reason="cross_realm_structural_relation"`）。实现、日志和审计解释时 MUST 按“结构 Relation 跨 Realm”理解，不得解释为“同 Realm 内跨 Space”。本节给出的两端 enforce 责任表是这条规则的语义来源。
- 弱语义 `references` / `mentions` / `derived_from` / `summarized_from` / `depends_on` / `blocks` / `assigned_to` / `has_default_view` / `replies_to` 等 MAY 跨 Realm，需走 §4.3 的"两次独立 capability check"路径，并按目标 Realm policy 在 projection 层降级为 `ReferenceProjectionState`。
- JSON Schema 层面无法在不引入冗余字段的前提下完整表达该约束（需要解析 typed reference 后再比 Realm），因此 [`relation.schema.json`](../../artifacts/schemas/relation.schema.json) 的 `relation_kind` description 把该约束标记为 reducer-enforced；schema validation 通过仅代表线路形态合法，不代表 cross-Realm 约束已通过。

### 4.5 反枚举（normative）

**存在性反枚举**：`ReferenceProjectionState.locked` 与"目标 Realm 不存在 / 未发现"对外 MUST 保持不可区分。projection 在两种情况下 MUST 返回**相同**的 wire 形态：相同 `status="locked"` 或等价字段、相同 metadata 集合、相同 error 字符串、相同 timing bucket。Timing 判定使用同一服务端测量点、同一请求类别和同一部署 profile 的分布式口径：实现 SHOULD 对每类至少采样 30 次，p95 差异 SHOULD ≤ 50ms；声明高安全 profile 时 MUST 使用 padding / jitter 使 p99 也落入该 bucket。网络传输时间不计入服务端本地口径，但 conformance runner MAY 在同一网络条件下做端到端抽样。MUST NOT 在 `locked` 响应中泄露目标 `realm_id`、`title`、`member_ids`、`created_at`、issuer set 或任何能被探测者用于"目标存在 vs 不存在"区分的字段；客户端 UI MAY 显示通用 "reference not accessible" 而不是显示具体目标 ID。源 Realm reducer SHOULD 限制单一 actor 在固定窗口内创建跨 Realm `locked` Relation 的速率（默认 ≤ 20/min），防止枚举攻击。Conformance vector `ak.vector.relation.reference_projection_indistinguishable.v1` 固化该响应 shape、raw event/backfill masking 与 timing bucket。

读取实现 MUST 对 projection caller、raw event caller、backfill consumer 与 federation peer 使用同一 reference-disclosure 决策。`committed_replication` 只允许 peer 本身被授权接收完整 payload 时传输 canonical bytes；否则该 peer 不进入 canonical replication target set，发送方只能通过已登记 read／sync surface 返回 `CommittedEventView` withheld 分支，MUST NOT 把该分支塞入 committed-replication request。获准持有 canonical bytes 的 Station 仍必须对其本地 caller 执行本节 disclosure 判定。接收方 MUST NOT 把 withheld 分支作为 reducer input、canonical event bytes、dedupe authority 或 proof.event_digest 重算材料。

## 5. 关系记录与应用规则边界

v1 不提供 Realm 级关系数量限制配置或注册机制。标准关系按 §3.2 与 §6 的规则处理；Realm schema、profile 与 UI hint MUST NOT 改写标准关系的基数、主冲突域或 CAS 规则。

`assigned_to` 仅记录 Strand 与完整 ActorId 之间的分配事实。一个 Strand MAY 同时分配给多个 Actor；不同 Actor 的分配记录不构成互斥冲突。创建、修改或删除分配记录 MUST NOT 派生 membership、角色、capability 或访问权限变更。应用的单负责人交互属于应用层规则，不构成协议 reducer 的接受或拒绝条件。

## 6. 主冲突域 CAS

### 6.1 唯一 subject

`relation-kind-registry.json` 的每个可直接写 shape MUST 登记且只登记一个 `primary_conflict_domain`：

- `tuple`：`(realm_id, relation_kind, from_ref, to_ref)`；
- `from`：`(realm_id, relation_kind, from_ref)`；
- `truth_source`：没有可直接写 Relation，继续只读其原 typed current result。

Realm 来自已验证 Event envelope；Circle 只参与 scope 与授权，不进入 subject。不同 Actor 的 `assigned_to` 因完整 ActorId 不同而属于不同 tuple。payload 的 `primary_conflict_domain` 是封闭、签名的 selector，不是调用方可任选的 bucket；Reducer MUST 从 create definition 或 domain 当前值复算并逐字段相等验证。

每个 `(realm_id, primary_conflict_domain)` 只有一个 `relation` typed current result，value 是完整 Relation 对象并保留 event-derived RelationId。不存在第二组裁决 family，也不存在候选 heads、16 条诊断上限、17-head recovery、分页修复材料或显式组裁决操作。

### 6.2 Create / update / tombstone

三种写入都在治理 Station 的同一 authority-commit transaction 内先比较 payload 的 `expected_revision`，再原子写入 domain 当前值：

- **create**：domain 从未写入时要求 `expected_revision = null`；若当前值已 tombstoned，要求携其 exact revision，成功后以本 create Event 派生新的 RelationId。当前值为 active 时不得用 create 覆盖；
- **update**：要求 non-null exact revision，且 `relation_id` 等于当前 value 的 id、state 为 active；只允许修改 `scope_circle_id`、`rank`、`fields`；
- **tombstone**：要求 non-null exact revision，且 `relation_id` 等于当前 value 的 id、state 为 active；成功后保留同一 RelationId 与历史，把 state 单向置为 tombstoned。

revision 不匹配、current id 不匹配、非法 lifecycle 或 active domain 上再次 create 都 MUST 以 `failed_precondition` 零写入拒绝。只有成功写入才取得 RealmCommit；字节完全相同的 Event exact replay 返回原 Commit，不再次推进 revision。失败 intent 可由客户端或部署本地拒绝审计保留，但不得伪装成 committed Relation、共享候选或 RealmCommit。

### 6.3 身份字段锁定与跨 domain 改动

`relation_kind`、`from_ref`、`to_ref` 是 primary domain 身份，create 后锁定。改变任一字段必须是两个显式操作：先对旧 domain tombstone，再对新 domain create；两步分别携各自 current revision、分别授权、分别产生可见结果。协议故意不提供跨 domain 双 CAS、隐式搬迁或原子 move；第一步成功而第二步失败是这两次用户操作的正常中间态，调用方重读新 domain 后重签第二步。

这一限制是 D1 简化的逆向门禁：若允许普通 update 改 domain，就必须同时删除旧 subject、写入新 subject并冻结两个前态，一条 `expected_revision` 无法闭合该事务，最终会重新引入被删除的多对象裁决机。实现 MUST NOT 用私有数据库锁、header 或未登记 payload 字段补出该语义。

### 6.4 历史、私密 scope 与 derived edge 保留边界

D1 只删除冗余冲突修复面，不删除 Relation 领域本身：

- 所有已接受 create/update/tombstone Event、RealmCommit、RelationId 与 tombstoned value 继续按既有 history/redaction policy 保留；
- `confidential_discussion_of` 及其它 Circle-scoped Relation 仍按 §3.2 / §4 执行最小披露，subject 不含 Circle 不代表扩大可见性；
- 派生 `contains` / `watches` 继续由其原 typed current result 投影，仍不得通过 Relation Event 直接写入；
- scope/capability、endpoint existence、cross-Realm reference disclosure 与不可逆 tombstone 规则不变。

并发 conformance 由 `ak.vector.relation.primary_domain_cas.v1` 固化：相同 revision 的 create/update/tombstone 竞争至多一个成功；相反提交顺序都只按 governance Station 接纳顺序决定；stale retry 零写入；exact replay 返回原 Commit；tombstone 后携其 revision 可创建新 RelationId；derived edge 直接写入继续拒绝。

## 7. 常见关系（按对象）

- **Strand**：见 [strand-and-message.md §7](./strand-and-message.md)。
- **Space**（Board / List）：见 [realm-and-space.md §3.5](./realm-and-space.md) 与 [§3.6](./realm-and-space.md#36-strand-位置)。
- **Message**：见 [strand-and-message.md §9.7](./strand-and-message.md)。
- **Morph**：业务自定义关系，由 Realm schema / Morph profile 声明。

## 8. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Space 位置语义：[realm-and-space.md §3.6](./realm-and-space.md#36-strand-位置)。
- authority-commit projection：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Relation schema：`artifacts/schemas/relation.schema.json`。
- Relation 写入 payload：`artifacts/schemas/event-payload.schema.json#/$defs/relation_{create,update,tombstone}_payload`。
- Relation 主冲突域：`artifacts/schemas/relation.schema.json#/$defs/relation_primary_conflict_domain`。
- 服务器已验证结果的客户端消费边界：[`../sync/server-trusted-results.md`](../sync/server-trusted-results.md)。
