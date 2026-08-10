---
title: Relation
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

`relation`（`ak:relation:`）是 Arkret 协作图的**一等关系对象**。跨对象语义 MUST 使用 Relation 表达，而不是藏在对象字段里。

Relation 连接的是对象引用：标准字段使用 `from_ref` / `to_ref`，其值可以指向 `realm`、`space`、`actor_profile`、`strand`、`message`、`morph`、`relation`、`event`、`view`、`blob` 的 `ak:<kind>:` typed ID，或一个 DID。Actor 端点没有 actor typed-ID 对象——当端点是 Actor 时直接使用该 actor 的 DID（principal），而不是某个 actor typed-ID（见 [`overview.md` §3.4](./overview.md) 与 [`common-fields.md` §4.1](./common-fields.md#41-did-适用边界)）。

> **端点 kind 子集与其它"可引用 kind 子集"字段的关系（informative）**：Relation 端点允许的 kind 集合与 Notification `source_ref`（[`private-objects.md` §3.2](./private-objects.md)）、Read Cursor `read_scope`（[`private-objects.md` §2.2](./private-objects.md)）各自不同；差异由各自语义决定（Relation 端点 = 可连边的图节点，故含 `realm` / `event` / DID；Notification = 可被通知指向的内容对象；Read Cursor = 可定位已读位置的时间线容器）。三处实现 MUST 按各自 schema 校验字段形状，同时以 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `referenceability` 作为 typed-id kind 子集的机读真相源；Relation 端点对应 `relation_endpoint` 类别。Actor DID 端点不属于 typed-id kind，仍由 DID grammar 与 `common-fields.md` §4.1 约束。

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
| `scope_circle_id` | no | `id:circle` | submit payload 提供的 Realm 内 Circle scope；`confidential_discussion_of` 按 §3.1 MUST 指向 private Strand 的 Circle。Sidecar context mapping 使用原生 `ak.component.sidecar.context.v1`，不是 Relation。 | 该 Relation 事实的 Circle 作用域。 |
| `effective_scope` | no | `object` | 只读对象投影，MUST 等于创建 Event 的签名 `scope_ref`；actor 不在 relation content 内重复提交。create 时 receiver 从 `scope_circle_id` 与端点冻结前态复核，结构关系 MUST NOT 宽于参与端点中最窄的作用域。 | 派生的有效作用域。 |
| `relation_kind` | yes | `string` | 标准值见 §3。 | 关系语义。 |
| `from_ref` | yes | `string` | MUST 是 `ak:<kind>:...` 或 DID。 | 起点对象/Actor/Realm 引用。 |
| `to_ref` | yes | `string` | MUST 是 `ak:<kind>:...` 或 DID。 | 终点对象/Actor/Realm 引用。 |
| `rank` | no | `string` | 见 `encoding.md` §9。**与 Space.rank 顶层字段对齐**——v1 把 rank 提升到顶层，`fields.rank` 在 wire 上 MUST 被拒绝（`schema_violation`），不接受双源并存。 | 有序关系（如 `contains list -> strand`）的稳定 rank。 |
| `fields` | no | `object` | 可放 role、edge metadata；MUST NOT 包含 `rank`（已提升到顶层）。 | 关系属性。 |
| `state` | no | `enum(active, tombstoned)` | `tombstoned` 同时覆盖删除与 redaction；若操作提供原因，原因保存在对应 `ak.relation.tombstone` / `ak.redaction` event 上，物化对象只保留当前状态。 | 关系状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `core_id` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `core_id` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

**生命周期（normative）**：Relation 的 `state` 只取 `active` / `tombstoned` 两值，**没有 `archived` 态**——这是有意取舍，区别于含 `archived` 的 Circle / Morph 等对象（[`common-fields.md` §5.2](./common-fields.md) 模板）：Relation 是一等边，要么有效（`active`）要么作废（`tombstoned`，不可逆，由 `ak.relation.tombstone` / `ak.redaction` 写入），不存在"暂时收起、可恢复"的中间态。需要"软隐藏"某条关系时，由查询 / projection 层过滤，不引入额外 canonical 生命周期态。生命周期仅 `active → tombstoned` 单向迁移。

**`ak.relation.tombstone` payload（normative）**：该 Event 的 payload 由 [`event-payload.schema.json#/$defs/relation_tombstone_payload`](../../artifacts/schemas/event-payload.schema.json) 定义，唯一目标字段是必填的 `relation_id: id:relation`；可选 `reason` 是保留在 Event 上的人类可读原因。`target_ref`、`patch`、`expected_state_digest` 以及其它 `ak.relation.update` 字段在 tombstone payload 上 MUST 以 `schema_violation` 拒绝，不允许两个目标别名形成双源。Reducer MUST 验证 `relation_id` 指向本 Event `realm_id` 内当前为 `active` 的 Relation；目标不存在、属于其它 Realm 或已经 `tombstoned` 时 MUST `failed_precondition`。接受后只执行 `active → tombstoned`，并把物化 `state_changed_at` 设为该 Event 的 `created_at`；`reason` 不复制到 Relation 对象。

```text
{
  "relation_id": "ak:relation:AUifoAUG8AEOHYXp999WnI7WlLt19ByDoqYUsFwbw4A4",
  "reason": "relationship no longer applies"
}
```

Canonical 方向由 `from_ref -> to_ref` 定义。反向语义 SHOULD 由查询层或 schema 派生。

最小示例：

```json schema=schemas/relation.schema.json
{
  "id": "ak:relation:AUifoAUG8AEOHYXp999WnI7WlLt19ByDoqYUsFwbw4A4",
  "schema": "ak.schema.relation.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "relation_kind": "contains",
  "from_ref": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
  "to_ref": "ak:strand:AQdknt9AByYY2gb16KB093xeB4J8b02mTEd4Mt8z2rO-",
  "rank": "mV",
  "created_by": "ak:did_core:webvh:zHuXvTbhiRsj2KEPE64TLhzG4",
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

其中 `summarized_from` 与 `promoted_from_discussion` 是 active 标准 kind 中的 **profile-required typing** 子类：registry 将二者标记为 `weak_semantic=true`，且 from/to 类型 MUST 由 Realm schema 或 RelationProfile 显式声明；未声明时，它们只是不透明弱语义引用边，不提供开箱即用的摘要或讨论升级强语义。

> **未注册的 relation_kind 处理规则**：`produced` / `used` / `triggered_by` / `has_log` 这类名字在 v1 没有 schema / profile / fixture 定义 from/to 类型、基数或 capability action，因此在 v1 wire 上视为**未注册的 relation_kind**——实现遇到时 SHOULD 保留为不透明边并在 projection 层标记 `unknown_relation_kind`，**MUST NOT** 据此自动推断容器、依赖或可见性语义。扩展 profile 注册之前 producer 不应使用。

### 3.2 默认基数表

| `relation_kind` | 默认基数 | 作用域与去重规则 |
| --- | --- | --- |
| `contains`：`Space(kind=board) -> Space(kind=list)` | **派生投影**(derived projection only) | 一个 Board 可包含多个 List；同一 List 在同一 Realm 内 MUST 至多有一个 active Board parent。**Truth source 是 cas_register cell `ak:cell:ak.component.space.parent.v1:<list_space_id>`，写入路径是 `ak.space.parent` Move，不是 `ak.relation.create`**。直接 `ak.relation.create / update / delete relation_kind=contains` 在该 from→to 形状上 MUST `schema_violation`(详见 [realm-and-space.md §3.5](./realm-and-space.md#35-akspaceparent-cas_register-basis))。`contains` Relation 仍出现在标准 kinds 列表中是因为 projection / query / UI 仍按 Relation 视角读它，但**写入路径单一化**到 `ak.space.parent`。 |
| `contains`：`Space(kind=list) -> Strand` | **派生投影**(derived projection only) with board-exclusive target | 一个 List 可包含多个 Strand；同一 Strand 在同一个 Board 内 MUST 至多处于一个 active List。去重/互斥 key 为 `(board_space_id, strand_id)`，与 [realm-and-space.md §3.6](./realm-and-space.md#36-strand-位置) 的位置唯一性一致。**Truth source 是 cas_register cell `ak:cell:ak.component.strand.position.v1:<board_space_id>:<strand_id>`，写入路径是 `ak.strand.move` / `ak.strand.reorder` Move**，不是 `ak.relation.create`。直接 `ak.relation.create / update / delete relation_kind=contains` 在该 from→to 形状上 MUST `schema_violation`(与 `watches` derived Relation 同模式)。 |
| `contains`：其他对象组合(非 Space 容器场景，例如 `Strand -> Strand` subtask / checklist item) | `many_to_many` unless profiled | 默认只按完整 tuple 去重；若对象被当作容器使用，Realm schema/profile MUST 声明更严格基数、排序字段和 cascade 规则。这种非派生形态的 `contains` 由 `ak.relation.create` 直接写入，不得与 Board/List 的派生 `contains` 混用。 |
| `belongs_to` | `many_to_one` | 作为 `contains` 的显式 parent 关系时，同一 `from_ref` 在同一作用域内至多有一个 active `to_ref`。优先使用 canonical `contains` 表达容器包含。 |
| `replies_to` | `many_to_one` | 一个 Message 或 reply object SHOULD 只有一个 direct parent；额外链接用 `references` 或 `mentions`。 |
| `depends_on`, `blocks` | `many_to_many` | 按 `(realm_id, relation_kind, from_ref, to_ref)` 去重；循环检测由 workflow/profile 规则决定。 |
| `mentions`, `references`, `derived_from`, `attached_to`, `summarized_from`, `promoted_from_discussion` | `many_to_many` | 按完整 tuple 去重；多条语义不同的边必须用 `fields.role`、不同 `relation_kind` 或 profile 声明的 multi-edge key 区分。其中语义性较强的 `summarized_from`(摘要 → 来源)与 `promoted_from_discussion`(正式对象 → 来源 discussion)在 v1 不在本表硬编码 from_kind→to_kind 约束，其 from/to 类型 MUST 由 Realm schema / RelationProfile 显式声明(见 [§5](#5-relationprofile))；未声明 profile 时按通用弱语义引用边处理。 |
| `assigned_to` | `many_to_many` | Canonical 方向为 `Strand -> DID`（`from_ref=<strand_id>`, `to_ref=<actor DID>`）。默认 `many_to_many`，按完整 tuple `(realm_id, relation_kind, from_ref, to_ref)` 去重(同一 (Strand, Actor) 对至多一条 active edge，即同一 Actor 不重复分配)；一个 Strand MAY 同时分配给多个 Actor。**这是按完整 tuple 去重，不是 per-actor 单值约束。** 需要单负责人语义时，Realm schema/profile MUST 声明 `max_to_per_from=1` 或单独 owner relation——[§5](#5-relationprofile) 的 `many_to_one` 示例即此单负责人 profile 收紧示例，非默认基数。Strand object / `metadata.fields` 不得携带 `assignee` / `assignees` / `assigned_to` 字段作为替代真源；见 [strand-and-message.md §7.1](./strand-and-message.md#71-assignment--assignee-投影)。 |
| `watches`：`actor (did) -> strand` | **派生投影**（derived from cell, not directly writable） | 每个 `(from_ref, to_ref)` 至多一条 active edge；`from_ref` MUST 是 DID，`to_ref` MUST 指向 Strand（或 profile 声明的 watchable 对象）。**Truth source 是 cas_register cell `ak.component.strand.watch.v1`，写入路径是 `ak.strand.watch.set` durable event，不是 `ak.relation.create`**——直接 `ak.relation.create / update / delete relation_kind=watches` MUST `schema_violation`（与派生 `contains` Relation 的双源约束同模式，见 [`./realm-and-space.md` §3.6](./realm-and-space.md#36-strand-位置)）。写入 invariant：`payload.watcher_actor_id == envelope.actor_id`，除非 actor 持有 `ak.strand.watch.set.others` capability。级别枚举、投影脱敏、通知路由见 [strand-and-message.md §8](./strand-and-message.md)。 |
| `has_default_view` | `many_to_one` | 同一 `from_ref` 在同一 Realm 内至多有一个 active default View；设置新默认 View MUST 关闭旧 active edge。 |
| `confidential_discussion_of` | `many_to_one` | weak-semantic、non-structural、non-cascading。`from_ref` MUST 是 private Strand，`to_ref` MUST 是其 public seal Strand。该 relation fact MUST 提交在 `from_ref` 所在 Circle scope（即 payload `scope_circle_id` 指向 private Strand 的 Circle，使 `effective_scope = circle`），使 Circle 成员能从 private Strand 回到 public seal，而 non-member 不能从 public seal 侧枚举该边。**实现 MUST NOT 在目标公开 Strand 写 target-side reverse relation**。 |

未声明为 multi-edge 的 Relation MUST 由 reducer 按 `(realm_id, relation_kind, from_ref, to_ref)` 去重。Events API MAY 拒绝同一 frontier 下显然重复的写入，但不能作为唯一去重机制；两个离线设备并发创建同一关系时，若 relation profile 未声明其它 `on_conflict` 值，reducer MUST 按 §6 的 `deterministic_winner` 规则选择一个 active winner，并把 loser 记录为 conflict 或 tombstone。

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

**Raw Event API 边界（normative）**：源 Realm canonical Event Store Service MAY 保存完整 `from_ref` / `to_ref` 字段以维持签名、dedupe 与 reducer determinism，但 `ak.self.events.read.scan` / `ak.self.events.stream.subscribe` / backfill / federation fanout 不是无条件 byte dump。若目标 Realm policy 对当前 caller / peer 拒绝 reference disclosure，则这些读取 surface MUST 返回与 §4.5 `locked` projection 等价的 redacted event view（保留 event id、kind、realm_id、payload digest / redaction reason 等可验证 stub，隐藏 envelope payload 内的目标 `realm_id` / `to_ref` / preview 字段），或直接按目标 policy 返回不可区分的 `locked` stub；不得把 canonical bytes 直接 forward 给本地客户端。redacted / locked 形态的机器契约是 `service-operation-dtos.schema.json#/$defs/RedactedEventView` 与 `#/$defs/ReferenceLockedEventStub`；`EventsQueryOutcome.events[]`、`EventView.event` 与 federation/backfill 的等价响应项必须能验证为完整 Event Envelope、RedactedEventView 或 ReferenceLockedEventStub 三者之一。只有同时满足源 Realm `ak.event.read` 与目标 reference disclosure 的 caller 才可取得完整 canonical payload bytes。

#### 4.2.1 `ReferenceProjectionState`（normative）

跨 Realm Relation、View、Space hierarchy 或 Graph 查询在展示引用目标时 MUST 使用统一的 `ReferenceProjectionState`：

| 值 | 语义 | 可见字段 |
| --- | --- | --- |
| `accessible` | caller 已通过目标 Realm 的 discover/reference 与内容展开授权，可展示目标 policy 允许的 metadata / preview。 | 目标 policy 允许的最小 metadata；不得超出本次授权。 |
| `lazy_link` | caller 可能有后续展开路径，但当前查询深度、范围、profile 或缺失依赖要求截断为惰性链接。 | 不解引用占位、必要的 source-side relation id / digest；不得自动 backfill 目标 Realm。 |
| `locked` | 目标不存在、未发现、policy 拒绝或 caller 无权知道目标存在性；这些原因对 caller MUST 保持不可区分。 | 固定 locked stub；不得包含目标 `realm_id`、title、member_count、created_at、issuer set、preview 或任何可区分存在性的字段。 |

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
- 目标 Realm policy 拒绝引用时（例如 `discoverability=secret` + 不在 trusted issuer 列表），源 Realm 仍 MAY 接受 Relation 但**MUST**在 projection 层把它降级为 `ReferenceProjectionState.locked`，并不得泄露目标 Realm 的存在性细节。reducer 仍把 Relation 视为 `active` 写入 canonical event log；`locked` 只由 projection 在读取时对目标 Realm policy 做最新评估后派生而成。当目标 Realm 解除 policy 阻塞时，projection 在下一次重新评估时自动把同一 Relation 显示为 `accessible`（含具体目标 metadata），**无需**额外发布 "Relation unlock" 事件；同理 lock 与 unlock 之间不引入 reducer-level 状态机或新的 cell 类型。源 Realm SHOULD 缓存最近一次目标 policy 评估结果，以减少跨 Realm 探测；缓存 TTL 由目标 Realm `discoverability` policy 与 projection 实现 trade-off，但 MUST 在 policy 显式变更时即时失效。

> **projection 态的收敛语义（normative 澄清）**：`ReferenceProjectionState`（`accessible` / `lazy_link` / `locked`）是 **reader-local 派生视图**，由各 reader 在读取时对目标 Realm policy 做最新评估（含各自缓存 TTL）得出，因此**不要求跨 reader 收敛**：在 policy 变更的传播窗口或不同缓存 TTL 下，两个 reader 对同一 Relation 同时派生出 `accessible` 与 `locked` 是**有意取舍**，不构成收敛缺口。Relation 的 canonical state 始终为 `active`（写入 canonical event log 的唯一权威态），不随 projection 态变化；本节的「不跨 reader 收敛」仅限投影/展示层，不影响任何 canonical state、授权或 winner 选择。

**跨 Realm 强约束（reducer 必检）**：

- `contains` 与 `belongs_to` MUST NOT 跨 Realm——reducer MUST 解析 `from_ref` / `to_ref` 指向的对象（Space / Strand / Message / Morph 等），确认其 `realm_id` 与 Relation 自身 `realm_id` 一致；任一不一致 MUST `failed_precondition`（`reason="cross_realm_structural_relation"`）。实现、日志和审计解释时 MUST 按“结构 Relation 跨 Realm”理解，不得解释为“同 Realm 内跨 Space”。本节给出的两端 enforce 责任表是这条规则的语义来源。
- 弱语义 `references` / `mentions` / `derived_from` / `summarized_from` / `depends_on` / `blocks` / `assigned_to` / `has_default_view` / `replies_to` 等 MAY 跨 Realm，需走 §4.3 的"两次独立 capability check"路径，并按目标 Realm policy 在 projection 层降级为 `ReferenceProjectionState`。
- JSON Schema 层面无法在不引入冗余字段的前提下完整表达该约束（需要解析 typed reference 后再比 Realm），因此 [`relation.schema.json`](../../artifacts/schemas/relation.schema.json) 的 `relation_kind` description 把该约束标记为 reducer-enforced；schema validation 通过仅代表线路形态合法，不代表 cross-Realm 约束已通过。

### 4.5 反枚举（normative）

**存在性反枚举**：`ReferenceProjectionState.locked` 与"目标 Realm 不存在 / 未发现"对外 MUST 保持不可区分。projection 在两种情况下 MUST 返回**相同**的 wire 形态：相同 `status="locked"` 或等价字段、相同 metadata 集合、相同 error 字符串、相同 timing bucket。Timing 判定使用同一服务端测量点、同一请求类别和同一部署 profile 的分布式口径：实现 SHOULD 对每类至少采样 30 次，p95 差异 SHOULD ≤ 50ms；声明高安全 profile 时 MUST 使用 padding / jitter 使 p99 也落入该 bucket。网络传输时间不计入服务端本地口径，但 conformance runner MAY 在同一网络条件下做端到端抽样。MUST NOT 在 `locked` 响应中泄露目标 `realm_id`、`title`、`member_count`、`created_at`、issuer set 或任何能被探测者用于"目标存在 vs 不存在"区分的字段；客户端 UI MAY 显示通用 "reference not accessible" 而不是显示具体目标 ID。源 Realm reducer SHOULD 限制单一 actor 在固定窗口内创建跨 Realm `locked` Relation 的速率（默认 ≤ 20/min），防止枚举攻击。Conformance vector `ak.vector.relation.reference_projection_indistinguishable.v1` 固化该响应 shape、raw event/backfill masking 与 timing bucket。

读取实现 MUST 对 projection caller、raw event caller、backfill consumer 与 federation peer 使用同一 reference-disclosure 决策。对 peer 传输 canonical bytes 仅在 peer 本身被授权接收完整 payload 且承诺对其本地 caller 继续执行本节 masking 时允许；否则发送方 MUST 只传 redacted event view / locked stub。签名验证工具需要证明原始事件存在时，服务端 MAY 返回 `payload_digest`、inclusion proof 与 redaction reason，但不得返回被 target policy 禁止的 target ref 明文字段。RedactedEventView 与 ReferenceLockedEventStub 均为 projection / completeness evidence,`reducer_input` MUST 为 `false`；接收方 MUST NOT 把它们作为 reducer input、canonical event bytes、dedupe authority 或 proof.event_digest 重算材料。

## 5. RelationProfile

Realm schema、Realm profile 或 `relation_profiles` MAY 对标准默认值收紧，但不得放宽会破坏互操作 projection 的标准互斥规则（例如同一 Board 内 Strand 只能处于一个 List）。

`RelationProfile` 最小结构：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `relation_kind` | yes | `string` | 被声明的 relation kind。 |
| `from_kind` | no | `string` | 起点类型约束，例如 `realm`、`space:board`、`space:list`、`strand`、`message`、`morph:*` 或 `did`。 |
| `to_kind` | no | `string` | 终点类型约束。 |
| `relation_scope` | no | `enum(realm, space, board, global)` | 基数和去重作用域；默认 `realm`。`space` 表示在某 Space 内、`board` 是 `kind=board` Space 的简写。**scope 解析失败处置（normative）**：当 `relation_scope ∈ {space, board}` 但 reducer 无法解析参与端点所属的 board/space 用作去重 / 基数 key 的 `board_space_id`（端点不隶属任何 board/space，或所属 board/space 已 `tombstoned`），reducer MUST `failed_precondition`（`reason=relation_scope_unresolved`）——MUST NOT 静默降级为 `realm` scope 去重、MUST NOT 跳过基数约束。producer 需重试时应改用可解析的 scope 或显式 `realm` scope 重新提交。 |
| `cardinality` | yes | `enum(one_to_one, one_to_many, many_to_one, many_to_many)` | `one_to_many` 表示同一 `from_ref` 可有多个 `to_ref`，但同一 `to_ref` 在 scope 内最多一个 active `from_ref`。 |
| `dedupe_key` | no | `array<string>` | 默认完整 tuple；可声明如 `["board_space_id", "to_ref"]`。 |
| `max_to_per_from` | no | `integer` | 每个 `from_ref` 的 active `to_ref` 上限。 |
| `max_from_per_to` | no | `integer` | 每个 `to_ref` 的 active `from_ref` 上限。 |
| `multi_edge` | no | `boolean` | 只有 true 时允许同一 tuple 多条 active edge。 |
| `rank_field` | no | `string` | 有序关系的 rank 字段，默认 `rank`（顶层）。仅当 profile 把 rank 显式放在另一字段时声明；MUST NOT 指向 `fields.rank`，该路径在 v1 不合法。 |
| `on_conflict` | no | `enum(reject, close_previous, deterministic_winner, require_review)` | 并发冲突处理；默认 `deterministic_winner`。该默认规则按 canonical `event_digest` 字典序选择 winner。 |

```json
{
  "relation_kind": "assigned_to",
  "from_kind": "strand",
  "to_kind": "did",
  "relation_scope": "realm",
  "cardinality": "many_to_one",
  "max_to_per_from": 1,
  "on_conflict": "reject"
}
```

声明为 multi-edge 的 relation profile MUST 显式定义去重 key、排序字段和 conflict 处理。

**`cardinality` 与 `max_*` 一致性校验（normative）**：`cardinality`（必填）与 `max_to_per_from` / `max_from_per_to`（可选）可表达互相矛盾的基数。reducer 在 accept RelationProfile（Realm schema / `relation_profiles` 注册或更新）时 MUST 校验三者一致，矛盾 MUST `schema_violation`（`reason=relation_profile_cardinality_conflict`）。一致性判据（`max_*` 只能在 `cardinality` 的方向语义内**收紧**，不得放宽或抵触）：

- `cardinality=one_to_one`：每方向至多 1。声明 `max_to_per_from > 1` 或 `max_from_per_to > 1` MUST reject；`max_to_per_from=1` / `max_from_per_to=1` 允许（冗余但不矛盾）。
- `cardinality=one_to_many`（同一 `from_ref` 多个 `to_ref`、同一 `to_ref` 至多一个 `from_ref`）：`max_from_per_to` MUST NOT > 1；`max_to_per_from` MAY 为任意正整数（收紧 `to` 侧上限）。
- `cardinality=many_to_one`（对称于上）：`max_to_per_from` MUST NOT > 1；`max_from_per_to` MAY 为任意正整数。
- `cardinality=many_to_many`：`max_to_per_from` / `max_from_per_to` MAY 为任意正整数，仅收紧上限，不构成矛盾。

任一 `max_*` 取值 ≤ 0 MUST `schema_violation`。校验在 profile 注册时一次性完成，使后续 Relation 写入只需按已校验一致的 effective 基数判定，不在每次写入时重新比对 `cardinality` 与 `max_*`。

## 6. 冲突处理

Relation conflict 的默认处理为：候选先通过格式、签名、授权、时钟窗口和 causal dependency 检查；严格因果后继 supersede 前驱；互不可达候选不得靠 HLC、actor id、本地接收顺序、数据库 ID 或服务端插入顺序自动选边。若 relation profile 能用业务 lattice 合并则合并；否则按 `on_conflict` 处理。

- `on_conflict="close_previous"` 只适用于因果上明确晚于旧 edge 的事件；并发互斥 edge 不得靠接收顺序关闭。
- `on_conflict="reject"` 表示 reducer 输出无 active 新 edge，并要求客户端重新基于最新 CBA query basis 提交修复 Event 或 Control Move。
- `on_conflict="deterministic_winner"` 表示 reducer 对互不可达候选按 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的统一 canonical tie-break(`event_digest` bytewise **最大值**)选出唯一 active winner；其它候选必须记录为 conflict loser 或 tombstone，并保留其 `event_id` / `event_digest` 以便审计和显式修复。`event_digest` 是签名覆盖的 canonical Event digest，不得由 HLC、actor id、`event_id` 或接收顺序替代。
- `require_review` MUST 输出可投影的 conflict 诊断，不得让两个互斥 active edge 同时进入 canonical projection。

**conflict loser 集合上限（normative）**：同一去重 key 下并发候选（winner + losers）的总数 MUST 受上限约束，复用 sibling fork 上限——v1 无条件上限为 **16**（与 [`event-and-patch.md` §2.6](./event-and-patch.md) 的 `(actor_id, actor_seq, prev_frontier_digest)` sibling 上限同值同范式；数值真相源见 [`scalability-constraints.md` §2](../conformance/scalability-constraints.md)）。当同一去重 key 的并发候选数超过 16 时，reducer MUST 对该去重 key 的整组候选 `failed_precondition`（`reason=relation_conflict_fanout_exceeded`），MUST NOT 无界保留 loser 记录；归一只能由后续基于最新 CBA query basis 的修复 Event / Control Move 产生。`deterministic_winner` 在 ≤16 候选内按 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的统一 tie-break(`event_digest` bytewise 最大值)选 active winner，其余 loser 记录 MUST 保留 `event_id` / `event_digest` 用于审计与显式修复。

**与 over-fork sibling 上限的分层关系（normative 澄清）**：本 relation fanout 上限（按去重 key `(realm_id, relation_kind, from_ref, to_ref)` 计数）与 [`event-and-patch.md` §2.6](./event-and-patch.md) 的 actor_seq sibling 上限（按 `(actor_id, actor_seq, prev_frontier_digest)` 计数）是**两层正交的限流**，作用于不同分桶。二者都 MUST 作为**收敛后候选集的纯函数**求值——即对给定的已收敛候选集，触发与否只取决于集合本身，**不依赖到达顺序、分桶处理先后或本地接收时序**；因此任意观察到相同候选集的 receiver 计算出相同的 quarantine / reject 子集，两层限流的触发先后不产生跨 receiver 分歧。pre-convergence(尚未收齐全部并发候选)的瞬态拒绝是 fail-closed 安全的，补齐缺失候选后重判收敛到同一结果。

`require_review` 与 loser 记录输出的 conflict 诊断对象使用 [`relation.schema.json`](../../artifacts/schemas/relation.schema.json) 的 `$defs/relation_conflict_diagnostic`（每条 loser 至少含 `event_id`、`event_digest`、`dedupe_key` 投影、`reason`）；conflict 诊断是 projection-only evidence，`reducer_input` MUST 为 `false`，MUST NOT 被当作 canonical event bytes 或 dedupe authority。

## 7. 常见关系（按对象）

- **Strand**：见 [strand-and-message.md §7](./strand-and-message.md)。
- **Space**（Board / List）：见 [realm-and-space.md §3.5](./realm-and-space.md#35-akspaceparent-cas_register-basis) 与 [§3.6](./realm-and-space.md#36-strand-位置)。
- **Message**：见 [strand-and-message.md §9.7](./strand-and-message.md)。
- **Morph**：业务自定义关系，由 Realm schema / Morph profile 声明。

## 8. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Space 位置语义：[realm-and-space.md §3.6](./realm-and-space.md#36-strand-位置)。
- CBA / Lattice：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Relation schema：`artifacts/schemas/relation.schema.json`。
