---
title: Relation
status: candidate
normative: true
stability: v1
updated: 2026-09-10
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

**`ak.relation.tombstone` payload（normative）**：该 Event 的 payload 由 [`event-payload.schema.json#/$defs/relation_tombstone_payload`](../../artifacts/schemas/event-payload.schema.json) 定义，唯一目标字段是必填的 `relation_id: id:relation`；可选 `reason` 是保留在 Event 上的人类可读原因。`target_ref`、`patch`、`expected_state_digest` 以及其它 `ak.relation.update` 字段在 tombstone payload 上 MUST 以 `schema_violation` 拒绝，不允许两个目标别名形成双源。Reducer MUST 验证 `relation_id` 指向本 Event `realm_id` 内当前为 `active` 的 Relation；目标不存在、属于其它 Realm 或已经 `tombstoned` 时 MUST `failed_precondition`。接受后只执行 `active → tombstoned`，并把物化 `state_changed_at` 设为该 Event 的 `created_at`；`reason` 不复制到 Relation 对象。

**`ak.relation.update` 目标（normative）**：更新 payload 同样只使用必填 `relation_id: id:relation` 定位被 patch 的 Relation；`target_ref` 不是 v1 别名，出现时 MUST `schema_violation`。registry 的 `relation` typed current result subject 逐字取 `payload.relation_id`，正文、schema 与 reducer 不得分别选择两个目标字段。

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

Relation MUST 由 reducer 按 `(realm_id, relation_kind, from_ref, to_ref)` 去重。Events API MAY 拒绝同一 checkpoint 下显然重复的写入，但不能作为唯一去重机制；两个离线设备并发创建同一关系时，reducer MUST 按 §6 的 `require_review` 暴露完整 heads，在显式 resolution 前不得选择 active winner。显式 resolution 的唯一载体是 §6.2 的 `ak.relation.resolve`；单条 `ak.relation.update` / `ak.relation.tombstone` MUST NOT 被用来消灭同组的其它候选。

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

v1 不提供 Realm 级关系数量限制配置或注册机制。标准关系按 §3.2 的规则处理；Realm schema、profile 与 UI hint MUST NOT 改写标准关系的基数、去重键或并发冲突处理规则。

`assigned_to` 仅记录 Strand 与完整 ActorId 之间的分配事实。一个 Strand MAY 同时分配给多个 Actor；不同 Actor 的分配记录不构成互斥冲突。创建、修改或删除分配记录 MUST NOT 派生 membership、角色、capability 或访问权限变更。应用的单负责人交互属于应用层规则，不构成协议 reducer 的接受或拒绝条件。

## 6. 冲突处理

### 6.1 候选、诊断与唯一主冲突域

本节的历史准入、候选完整性与因果归约由服务器验证；普通客户端按
[`server-trusted-results.md`](../sync/server-trusted-results.md) 消费自己 Station 在认证请求下提供的
结果，核对账号、Realm/scope、目标、basis 与待签意图，不为认证该结果重放治理历史或执行完整性挑战。
服务器仍须验证外部输入，projection diagnostic 本身不能替代接纳证据或授权。

Relation conflict 的处理为：候选先通过格式、签名、授权与时钟窗口检查。一个候选只被**同一 Relation 上、该 stream 更后位置被接受的 `ak.relation.update` / `ak.relation.tombstone`** 取代；除此之外的两个候选同时是活跃 head，按 `require_review` 处理。实现 MUST NOT 用 HLC、`created_at`、actor id、本地接收顺序、数据库 ID 或服务端插入顺序在互斥候选之间自动选边。不同 Actor 的 `assigned_to` 记录不是互斥候选。

- `require_review` MUST 输出包含全部 heads 的 conflict 诊断，不得让两个互斥 active edge 同时进入 canonical projection。后续 resolution Event MUST 在 §6.3 的冻结 baseline 中覆盖它要解决的完整 current head set；漏掉任一 current head 时仍保持 `require_review`。

**conflict head 集合上限（normative）**：分组单位始终是下文「唯一主冲突域」（`tuple` 形态即完整去重 key，`from` 形态是包含它的更大互斥组）；同一主冲突域下并发候选总数上限为 **16**，数值真相源见 [`scalability-constraints.md` §2](../conformance/scalability-constraints.md)。当同一去重 key 的并发候选数超过 16 时，reducer MUST 对该去重 key 的整组候选 `failed_precondition`（`reason=relation_conflict_fanout_exceeded`）；归一只能由后续读取最新已提交候选材料、覆盖完整 current head set 的修复 Event 产生。上限以内全部 heads 都保留，不存在 winner/loser 分类。

**唯一主冲突域（normative）**：`relation-kind-registry.json` 的每个可直接写 shape 登记
`primary_conflict_domain`。`tuple` 使用完整 `(realm_id, relation_kind, from_ref, to_ref)`；
`from` 使用 `(realm_id, relation_kind, from_ref)`，其完整 tuple 重复已经包含在同组中，MUST NOT 再生成
可独立裁决的 tuple 子组。`truth_source` 仅通过原来源 typed current result 处理。不同 Actor 的 `assigned_to` 仍属不同 tuple。

**超限证据保留（normative）**：第 17 条及之后已通过基础准入的候选 MUST 与前 16 条一样保留，
整组不产生 active edge，普通诊断／查询返回 `failed_precondition`（`relation_conflict_fanout_exceeded`）。
该错误不得被实现为只丢弃新到的候选、保留先到 16 条的截断，也不得删除已保留的 Event／来源证据。
完整候选的读取与修复证据不受普通诊断 16 条输出上限约束，仍受各自证据合同的资源与授权约束。
Circle 只参与读取和操作授权，不属于冲突 key；不同 Circle 下同一 Realm 的同 key 事实仍参与同一组冲突。

**判定基准（normative 澄清）**：relation fanout 上限按去重 key `(realm_id, relation_kind, from_ref, to_ref)` 计数，并在当前 authority-committed state 上求值。触发与否只取决于该提交位置的候选集合，不依赖网络到达顺序、本地接收时序或其它 stream 的状态。

`require_review` 输出的 conflict 诊断对象使用 [`relation.schema.json`](../../artifacts/schemas/relation.schema.json) 的 `$defs/relation_conflict_diagnostic`，并列出完整 head set；每个 candidate 只携 suite-bearing `event_id`，稳定排序与 digest 比较均从 ID 解码，不再携同源 `event_digest`。conflict 诊断是 projection-only evidence，`reducer_input` MUST 为 `false`，MUST NOT 被当作 canonical event bytes、winner 或 dedupe authority。诊断的 `conflict_domain` 是 `$defs/relation_conflict_domain` 强类型值，不是调用方自选的字符串桶；producer MUST NOT 用任意 dedupe key 绕过 registry 登记的互斥形状。

**16 是诊断上限，不是"冲突最多 16 个"（normative 澄清）**：`relation_conflict_diagnostic.heads` 的 `maxItems=16` 只界定**一次普通诊断输出**能展示的候选条数。它 MUST NOT 被读成"同一主冲突域最多存在 16 个候选"，也 MUST NOT 被用来在第 17 个候选之后截断、丢弃或拒绝 author 的 resolution：超限时整组候选按上文全部保留，修复走 §6.2 的唯一 carrier，其 `baseline.member_count` **没有** 16 的上限。任何以 16 为由拒绝提供完整候选材料、或拒绝受理覆盖 17 个及以上候选的 resolution 的实现都是不合规实现。

### 6.2 `ak.relation.resolve`：唯一 resolution carrier

显式 resolution 的唯一已登记载体是 committed state-changing Event `ak.relation.resolve`（payload [`event-payload.schema.json#/$defs/relation_resolve_payload`](../../artifacts/schemas/event-payload.schema.json)）。它按**完整冲突组**原子地保留一个仍然有效的候选 head，或把本次覆盖的候选全部作废。实现 MUST NOT 另造第二种 Relation resolution Event、私有管理端点或部署本地清理命令。

- **为什么是 state-changing Event**：该操作为跨对象的一组互斥候选选出单一有效结果，[`../authz/event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md) 禁止用普通数据面写入承担这种单赢家裁决；tombstone 与组裁决都按各自注册普通数据合同执行，不改变安全许可。
- **只写组裁决数据状态**：本普通 Event 只写注册的 `current-value projection` typed current result family `relation_conflict_resolution`，`result_selector` 完全由 `payload.conflict_domain` 决定（Realm 取自 envelope）。Relation 内容仍由 `ak.relation.create` / `ak.relation.update` 的数据面 typed current result 提供，active edge 投影联合读取二者。本 Event 不得写安全许可 typed current result，也 MUST NOT 逐条覆盖历史 Event。
- **封闭结果**：`payload.outcome` 只有两支。`retain_candidate` 的 `retained_event_id` MUST 是本 Event 自身 baseline 内的成员，保留的 Relation 采用该 head 对应的确定状态与**原 RelationId**；本合同不接受任意 `resolved_value`、新端点或混拼字段，后续内容编辑仍走 `ak.relation.update`。`void_all` 只使**本次明确覆盖**的候选不再产生 active edge，保留其事实与裁决供审计；它不复活已 tombstone / redaction 的对象、不改变任何 capability，也不禁止将来在同一域下合法创建新的 Relation。
- **目标形状**：`conflict_domain.domain_kind` MUST 与 [`relation-kind-registry.json`](../../artifacts/registry/relation-kind-registry.json) 中匹配 shape 登记的 `primary_conflict_domain` 一致（`tuple` 携 `to_ref`，`from` MUST NOT 携 `to_ref`）。`truth_source` shape（派生 `contains`、`watches` 等）没有可直接写的 Relation，因此没有可裁决的域，MUST 以 `schema_violation`（`relation_kind_contains_derived` / `relation_kind_watches_derived`）拒绝；这些边只能由其原来源 typed current result 的正式操作处理，MUST NOT 借本 Event 增加第二真相源。不同 Actor 的 `assigned_to` 属于不同 tuple，本来就不是互斥候选。

**授权与最小披露（normative）**：本 Event 由已登记 capability action `ak.relation.resolve` 授权。Reducer MUST 按签名授权上下文与 §6.3 的完整候选 baseline 验证该授权覆盖**整组受影响关系及其作用域**；只持有其中一条 Relation 的 `ak.relation.update` / `ak.relation.tombstone` 权限 MUST NOT 被当作裁决其它候选的依据。完整名单的读取仍受 Realm / Circle 与目标引用披露规则约束：调用方看不到完整组时 MUST NOT 伪造完整名单，Station MUST 以 `failed_precondition`（`relation_conflict_group_not_visible`）拒绝，MUST NOT 返回删减后的名单、MUST NOT 把 Circle 纳入冲突 key 以隐藏本应参与的候选，也 MUST NOT 为凑齐名单扩大调用方 scope 或向无权调用方泄露隐藏关系。

### 6.3 冻结基线与修复材料（normative）

**控制面授权基线与数据面候选完整性是两件事。** 治理 Station 在接纳时解析的 current authorization 冻结的是授权依据，它 MUST NOT 被当作"全部 Relation Event 已被观察"的证明；逐 Event inclusion proof、`ak.relation.update` 的 `expected_state_digest` 与 projection diagnostic 同样都不是完整组证明。因此 `payload.baseline` 是独立登记的**数据面完整集合承诺**：

- 成员是该域在本基线下的**全部活跃候选 head**：每个未 tombstone 的目标 Relation 的每个活跃 head EventId。`create` 贡献它自己的 EventId；`update` 按其 `expected_revision` 取代同一 Relation 的被覆盖版本，其**新 EventId MUST 进入候选集**，MUST NOT 永远用 create EventId 代替；`tombstone` 按自身 committed lifecycle 合同结束目标 Relation，该 Relation 退出候选集，但它 MUST NOT 被解释为已对其它分支作出整体裁决。内容版本、生命周期与组裁决三者的已验证贡献分别参与派生，MUST NOT 被压成一个按通用可达性消边的集合。
- 成员的 canonical 顺序是完整 `ak:event:` token 的 **bytewise UTF-8 升序**，去重后唯一。顺序只用于 canonical 编码与分页，MUST NOT 提供胜者。
- 每 256 个成员构成一页，最后一页可以不足 256；256 是 v1 固定的材料分页上限（单页工作量约束）。
- 页按 hash 链承诺，`H` 为该 Realm 当前声明的 digest algorithm，结果保留算法前缀：

```text
page_digest(i) = H( UTF8("ak-relation-conflict-page-v1\u0000") || JCS({
  "conflict_domain": <payload.conflict_domain>,
  "member_event_ids": [<第 i 页的成员，canonical 升序>],
  "page_index": i,
  "prev_page_digest": <page_digest(i-1)；i = 0 时为 null>,
  "realm_id": <Realm>
}) )

members_digest = H( UTF8("ak-relation-conflict-members-v1\u0000") || JCS({
  "conflict_domain": <payload.conflict_domain>,
  "last_page_digest": <最后一页的 page_digest>,
  "member_count": <N>,
  "realm_id": <Realm>
}) )
```

该承诺同时绑定**目标、基线、成员数、规范排序与全部成员**。只给一个 root、只给 count、或只给 17 条 inclusion proof MUST NOT 被接受为"没有遗漏"的证明。

- `member_count ≤ 64` 时 `baseline.member_event_ids` MUST 内联完整名单，小组自洽；`member_count ≥ 65` 时该字段 MUST 缺席，Event 只携 `members_digest`，MUST NOT 把大集合改写成无界 Event JSON。两种形态的承诺算法完全相同。
- 完整材料通过已登记读取面 `ak.self.relation_conflicts.read.candidates.v1`（[`../sync/service-http-binding.md`](../sync/service-http-binding.md)）分页取得。**页不独立生效**：读取方 MUST 按 `page_index` 升序走完全部页、逐页复算 `page_digest` 链，并在链末值等于 `members_digest` 之后才把整份材料视为已验证，然后才原子应用唯一 Event。缺页、乱序、重复 `page_index`、`prev_page_digest` 与前一页不符、非末页不足 256 条，或读取过程中该组发生变化，MUST 以 `failed_precondition`（`relation_conflict_material_page_gap`）失败，读取方 MUST 丢弃已收到的部分材料并从 `page_index=0` 重新开始；恢复进度只由 `next_cursor` 与已验证链状态表达，MUST NOT 由客户端自行拼接。
- **材料可用性**：Station MUST 为处于 `require_review` 或 `relation_conflict_fanout_exceeded` 的域保留完整候选材料。无法完整提供时 MUST 以 `failed_precondition`（`relation_conflict_material_unavailable`）fail closed，MUST NOT 返回截断名单、重算子集或无法逐成员兑现的 `members_digest`。
- **总工作量约束**：一个主冲突域进入 `relation_conflict_fanout_exceeded` 之后，在写入方自己的签名 basis 下该域再新增 `ak.relation.create` MUST 以 `failed_precondition`（`relation_conflict_fanout_exceeded`）拒绝。这条与"保留第 17 条及之后的候选"不冲突：全部已保留候选一律保留、一律不产生 active edge，被拒绝的只是**在已知拥堵域上继续新增**的写入，从而使修复材料被已收敛集合界定。该判定同样是收敛后候选集的纯函数，pre-convergence 的瞬态接受在补齐候选后按同一规则重判。

### 6.4 准入、基线覆盖与重放（normative）

Receiver MUST 在本 Event 被接纳位置**之前**的该 stream 已提交前缀上，从自己已接纳的 Relation 历史独立重建该域的完整活跃候选集合，按 §6.3 复算承诺，并要求与 `payload.baseline.member_count`、`members_digest` 逐字节相等；`member_event_ids` 存在时还要求与重建集合逐 EventId、逐顺序相等。缺项、多带已被取代的旧 head、重复项、混入其它域的成员，或 `retain_candidate` 指向名单外的 EventId，MUST 以 `failed_precondition`（`relation_conflict_baseline_stale`）拒绝**整条 Event 且零 typed current result 写入**。提交前若发现当前可验证组已变化，author MUST 重新 query、重新签发；MUST NOT 先应用再补验，也 MUST NOT 用 receiver 当前数据库快照替代签名基线。

所谓 current 是**这份可验证基线下的 current**：本合同 MUST NOT 被解释为声称知道整个网络尚未送达的事件。已验证的历史裁决只对其冻结覆盖集产生效果；后来发现的、未被覆盖的并发分支改变当前投影并重新触发 `require_review`，MUST NOT 重写旧裁决的历史含义；已被覆盖的旧分支重复到达 MUST NOT 复活它。重放、增量处理与分片合并在相同已提交前缀下 MUST 得到相同领域候选集合、相同当前 resolution 与相同结果。

同一 canonical Event 的 exact replay 按 EventId 幂等：它已生效后重传 MUST NOT 因为它自己的效果改变了当前 heads 就被判成一次新的 stale 提交，也 MUST NOT 报 `relation_conflict_baseline_stale`。新的 EventId 则必须按本节重新验证。

### 6.5 并发裁决与再解决（normative）

组裁决数据状态登记为 `current-value projection` typed current result，当前值规则见
[`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)：

- 该域的当前裁决是**该 relation 所属 stream 上最后一个被接受的 `ak.relation.resolve` 所产出的 typed current
  结果**。次序只由治理 Station 在该 stream 上给出的 `stream_position` 决定，MUST NOT 由任何客户端可见的
  因果深度、HLC、接收顺序或结果内容决定。
- 并发提交靠 `expected_revision` compare-and-set 收敛：提交者带上它读到的 `CurrentRevision`，Station 在接纳
  位置比较该值，不匹配即以 `failed_precondition` 拒绝且零 typed current result 写入；客户端重读当前裁决与
  当前候选集合后重新签发再试。因此不存在两条同时生效的裁决，也不需要在多个合法裁决之间挑选胜者。
- 每条 resolution 仍必须独立覆盖完整、冻结的 Relation 领域候选集合；CAS 只决定谁写得进去，MUST NOT 放宽
  §6.3 的 baseline 完整性。
- 后续 `ak.relation.resolve` 以当前裁决的 `CurrentRevision` 为 `expected_revision`，接纳后自然取代它；
  payload MUST NOT 另设一份"被取代的历史裁决列表"形成第二真相源。
- 新发现且不在当前裁决冻结 baseline 中的 Relation 领域候选仍会重新触发 `require_review`；这是跨 typed
  current result 的领域完整性检查。

**17-head 恢复（normative）**：超过普通诊断上限的域按同一 carrier 修复。author 通过 `ak.self.relation_conflicts.read.candidates.v1` 取得 17 条（或更多）成员的完整材料，按 §6.3 复算 `members_digest`，内联名单（`member_count ≤ 64`）或仅携承诺（`≥ 65`），再提交一条 `ak.relation.resolve`。实现 MUST NOT 因为普通 fanout 上限先拒绝所有修复材料，也 MUST NOT 把 16 复制成修复证据的上限。

§6.2–§6.5 的保留／全部作废、基线承诺、缺项与异组成员拒绝、17-head 恢复、大集合分页链、exact replay，以及并发裁决被 `expected_revision` 串行化的结果由 `ak.vector.relation.conflict_resolution.v1` 固化。

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
- Relation conflict resolution payload：`artifacts/schemas/event-payload.schema.json#/$defs/relation_resolve_payload`。
- 修复材料读取面：`ak.self.relation_conflicts.read.candidates.v1`（[`../sync/service-http-binding.md`](../sync/service-http-binding.md)）。
- 服务器已验证结果的客户端消费边界：[`../sync/server-trusted-results.md`](../sync/server-trusted-results.md)。
