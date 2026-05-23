---
title: Relation
---

## 1. 目标

`relation`（`cx:relation:`）是 Contrix 协作图的**一等关系对象**。跨对象语义 MUST 使用 Relation 表达，而不是藏在对象字段里。

Relation 连接的是对象引用：标准字段使用 `from_ref` / `to_ref`，其值可以指向 `flow`、`message`、`morph`、`actor`、`space`、`realm` 或 `blob`。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Schema 与字段

Schema id: `cx.schema.relation.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:relation` | 以 `cx:relation:` 开头。 | Relation ID。 |
| `realm_id` | yes | `id:realm` | Relation 所在 Realm。 | 所属 Realm。 |
| `relation_kind` | yes | `string` | 标准值见 §3。 | 关系语义。 |
| `from_ref` | yes | `string` | MUST 是 `cx:<kind>:...` 或 DID。 | 起点对象/Actor/Realm 引用。 |
| `to_ref` | yes | `string` | MUST 是 `cx:<kind>:...` 或 DID。 | 终点对象/Actor/Realm 引用。 |
| `rank` | no | `string` | 见 `encoding.md` §9。**与 Space.rank 顶层字段对齐**——v1 把 rank 提升到顶层，`fields.rank` 在 wire 上 MUST 被拒绝（`schema_violation`），不接受双源并存。 | 有序关系（如 `contains list -> flow`）的稳定 rank。 |
| `fields` | no | `object` | 可放 role、edge metadata；MUST NOT 包含 `rank`（已提升到顶层）。 | 关系属性。 |
| `state` | no | `enum(active, tombstone)` | `tombstone` 同时覆盖删除与 redaction；原因保存在对应 `cx.relation.delete` / `cx.redaction` event 上，不再写入物化对象。 | 关系状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

Canonical 方向由 `from_ref -> to_ref` 定义。反向语义 SHOULD 由查询层或 schema 派生。

最小示例：

```json schema=schemas/relation.schema.json
{
  "id": "cx:relation:01964180-0000-7000-8000-000000000000",
  "schema": "cx.schema.relation.v1",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "relation_kind": "contains",
  "from_ref": "cx:space:019640b6-8000-7000-8000-000000000000",
  "to_ref": "cx:flow:019640c6-8000-7000-8000-000000000000",
  "rank": "mV",
  "created_by": "did:web:bob.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 3. 标准 `relation_kind` 与基数

### 3.1 标准 kind

```text
contains, belongs_to, replies_to, depends_on, blocks, mentions,
assigned_to, references, derived_from, attached_to, has_default_view,
summarized_from, promoted_from_discussion, watches
```

> **未注册的 relation_kind 处理规则**：`produced` / `used` / `triggered_by` / `has_log` 这类名字在 v1 没有 schema / profile / fixture 定义 from/to 类型、基数或 capability action，因此在 v1 wire 上视为**未注册的 relation_kind**——实现遇到时 SHOULD 保留为不透明边并在 projection 层标记 `unknown_relation_kind`，**MUST NOT** 据此自动推断容器、依赖或可见性语义。扩展 profile 注册之前 producer 不应使用。

### 3.2 默认基数表

| `relation_kind` | 默认基数 | 作用域与去重规则 |
| --- | --- | --- |
| `contains`：`Space(kind=board) -> Space(kind=list)` | **派生投影**(derived projection only) | 一个 Board 可包含多个 List;同一 List 在同一 Realm 内 MUST 至多有一个 active Board parent。**Truth source 是 cas-register cell `cx:cell:cx.component.space.parent.v1:<list_space_id>`,写入路径是 `cx.space.parent` Move,不是 `cx.relation.create`**。直接 `cx.relation.create / update / delete relation_kind=contains` 在该 from→to 形状上 MUST `schema_violation`(详见 [realm-and-space.md §3.5](./realm-and-space.md#35-cxspaceparent-cas-register-basis))。`contains` Relation 仍出现在标准 kinds 列表中是因为 projection / query / UI 仍按 Relation 视角读它,但**写入路径单一化**到 `cx.space.parent`。 |
| `contains`：`Space(kind=list) -> Flow` | **派生投影**(derived projection only) with board-exclusive target | 一个 List 可包含多个 Flow;同一 Flow 在同一个 Board 内 MUST 至多处于一个 active List。去重/互斥 key 为 `(board_space_id, flow_id)`,与 [realm-and-space.md §3.6](./realm-and-space.md#36-flow-位置) 的位置唯一性一致。**Truth source 是 cas-register cell `cx:cell:cx.component.flow.position.v1:<board_space_id>:<flow_id>`,写入路径是 `cx.flow.move` / `cx.flow.reorder` Move**,不是 `cx.relation.create`。直接 `cx.relation.create / update / delete relation_kind=contains` 在该 from→to 形状上 MUST `schema_violation`(与 `watches` derived Relation 同模式)。 |
| `contains`：其他对象组合(非 Space 容器场景) | `many_to_many` unless profiled | 默认只按完整 tuple 去重;若对象被当作容器使用,Realm schema/profile MUST 声明更严格基数。这种非派生形态的 `contains` 由 `cx.relation.create` 直接写入。 |
| `belongs_to` | `many_to_one` | 作为 `contains` 的显式 parent 关系时，同一 `from_ref` 在同一作用域内至多有一个 active `to_ref`。优先使用 canonical `contains` 表达容器包含。 |
| `replies_to` | `many_to_one` | 一个 Message 或 reply object SHOULD 只有一个 direct parent；额外链接用 `references` 或 `mentions`。 |
| `depends_on`, `blocks` | `many_to_many` | 按 `(realm_id, relation_kind, from_ref, to_ref)` 去重；循环检测由 workflow/profile 规则决定。 |
| `mentions`, `references`, `derived_from`, `attached_to`, `summarized_from`, `promoted_from_discussion` | `many_to_many` | 按完整 tuple 去重；多条语义不同的边必须用 `fields.role`、不同 `relation_kind` 或 profile 声明的 multi-edge key 区分。 |
| `assigned_to` | `many_to_many` | 一个 Flow MAY 同时分配给多个 Actor；同一 Actor 只保留一条 active assignment edge。需要单负责人语义时，Realm schema/profile MUST 声明 `max_to_per_from=1` 或单独的 owner relation。 |
| `watches`：`actor (did) -> flow` | **派生投影**（derived from cell, not directly writable） | 每个 `(from_ref, to_ref)` 至多一条 active edge；`from_ref` MUST 是 DID，`to_ref` MUST 指向 Flow（或 profile 声明的 watchable 对象）。**Truth source 是 cas-register cell `cx.component.flow.watch.v1`，写入路径是 `cx.flow.watch.set` durable event，不是 `cx.relation.create`**——直接 `cx.relation.create / update / delete relation_kind=watches` MUST `schema_violation`（与派生 `contains` Relation 的双源约束同模式，见 [`./realm-and-space.md` §3.6](./realm-and-space.md#36-flow-位置)）。写入 invariant：`payload.actor_did == envelope.actor_id`，除非 actor 持有 `cx.flow.watch.manage_others` capability。级别枚举、投影脱敏、通知路由见 [flow-and-message.md §8](./flow-and-message.md)。 |
| `has_default_view` | `many_to_one` | 同一 `from_ref` 在同一 Realm 内至多有一个 active default View；设置新默认 View MUST 关闭旧 active edge。 |

未声明为 multi-edge 的 Relation MUST 由 reducer 按 `(realm_id, relation_kind, from_ref, to_ref)` 去重。Events API MAY 拒绝同一 frontier 下显然重复的写入，但不能作为唯一去重机制；两个离线设备并发创建同一关系时，reducer 必须确定性选择一个 active winner，并把 loser 记录为 conflict 或 tombstone。

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
- Sync / projection 层不得因为源 Realm 可见就自动 backfill 目标 Realm；跨 Realm 展开必须重新执行目标 Realm 授权，并在响应 metadata 中标记 `lazy_link`、`locked`、`accessible` 或等价可见性状态。

### 4.3 授权拆分（两端 enforce 责任）

| 授权检查类型 | 在哪一边 enforce | 原因 |
| --- | --- | --- |
| Relation **创建**（`cx.relation.create`、`cx.relation.update`、`cx.relation.delete`） | **源 Realm**（Relation `realm_id`） | Relation 是源 Realm 的 reducer-input；reducer 在源 Realm 验证 actor 在源 Realm 的 capability 是否覆盖 `cx.relation.*`。 |
| 引用目标的 **discover / reference 能力** | **目标 Realm**（`from_ref` 或 `to_ref` 指向的 Realm） | 目标 Realm policy 决定是否允许该 Relation 引用自身；典型 capability `cx.object.read_metadata` 或 `cx.realm.discover`。源 Realm reducer 在 accept Relation 前 SHOULD 验证目标 Realm 的 reference 许可（通过 cached attestation / capability grant ref 等）；缺失证据时 Relation 仍可写入源 Realm，但 projection 层在展开时 MUST 重新校验目标授权，校验失败的 Relation 显示为 `locked`。 |
| 目标对象**内容展开**（标题、字段、preview） | **目标 Realm**（read 时） | 每次展开都用 reader 在目标 Realm 的 capability 重新校验；源 Realm 的可见性不传染到目标。 |
| **位置 / structural 关系**（如 `contains` 跨 Realm） | **源 Realm + 强制源 == 目标** | `contains` 这类强结构关系在 v1 **MUST NOT 跨 Realm**——结构容器（Space）必须与所属 Flow 同 Realm。跨 Realm 的引用只能用 `references`、`mentions`、`derived_from`、`summarized_from` 等弱语义关系。 |

### 4.4 Reducer 强制约束

实现 MUST：

- 在源 Realm 接收 Relation 时验证 `from_ref` / `to_ref` 的 typed prefix 与目标 Realm 一致性（`realm_id` 字段或 typed ref 解析）。
- 不得把"源 Realm 写权限"误当成"目标 Realm 引用权限"——两者是**两次独立 capability check**。
- 目标 Realm policy 拒绝引用时（例如 `discoverability=secret` + 不在 trusted issuer 列表），源 Realm 仍 MAY 接受 Relation 但**MUST**在 projection 层把它降级为 `locked`，并不得泄露目标 Realm 的存在性细节。

**跨 Realm 强约束（reducer 必检）**：

- `contains` 与 `belongs_to` MUST NOT 跨 Realm——reducer MUST 解析 `from_ref` / `to_ref` 指向的对象（Space / Flow / Message / Morph 等），确认其 `realm_id` 与 Relation 自身 `realm_id` 一致；任一不一致 MUST `failed_precondition`（`reason="cross_space_structural_relation"`）。本节给出的两端 enforce 责任表是这条规则的语义来源。
- 弱语义 `references` / `mentions` / `derived_from` / `summarized_from` / `depends_on` / `blocks` / `assigned_to` / `has_default_view` / `replies_to` 等 MAY 跨 Realm，需走 §4.3 的"两次独立 capability check"路径，并按目标 Realm policy 在 projection 层降级为 `lazy_link` / `locked` / `accessible` 状态。
- JSON Schema 层面无法在不引入冗余字段的前提下完整表达该约束（需要解析 typed reference 后再比 Realm），因此 [`relation.schema.json`](../../artifacts/schemas/relation.schema.json) 的 `relation_kind` description 把该约束标记为 reducer-enforced；schema validation 通过仅代表线路形态合法，不代表 cross-Realm 约束已通过。

### 4.5 反枚举（normative）

**存在性反枚举**：`locked` 降级状态与"目标 Realm 不存在 / 未发现"对外 MUST 不可区分。projection 在两种情况下 MUST 返回**相同**的 wire 形态：相同 `status="locked"` 字段、相同 metadata 集合、相同 timing 类（差距 ≤ 50ms）、相同 error 字符串。MUST NOT 在 `locked` 响应中泄露目标 `realm_id`、`title`、`member_count`、`created_at`、issuer set 或任何能被探测者用于"目标存在 vs 不存在"区分的字段；客户端 UI MAY 显示通用 "reference not accessible" 而不是显示具体目标 ID。源 Realm reducer SHOULD 限制单一 actor 在固定窗口内创建跨 Realm `locked` Relation 的速率（默认 ≤ 20/min），防止枚举攻击。

## 5. RelationProfile

Realm schema、Realm profile 或 `relation_profiles` MAY 对标准默认值收紧，但不得放宽会破坏互操作 projection 的标准互斥规则（例如同一 Board 内 Flow 只能处于一个 List）。

`RelationProfile` 最小结构：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `relation_kind` | yes | `string` | 被声明的 relation kind。 |
| `from_type` | no | `string` | 起点类型约束，例如 `realm`、`space:board`、`space:list`、`flow`、`message`、`morph:*` 或 `did`。 |
| `to_type` | no | `string` | 终点类型约束。 |
| `scope` | no | `enum(realm, space, board, global)` | 基数和去重作用域；默认 `realm`。`space` 表示在某 Space 内、`board` 是 `kind=board` Space 的简写。 |
| `cardinality` | yes | `enum(one_to_one, one_to_many, many_to_one, many_to_many)` | `one_to_many` 表示同一 `from_ref` 可有多个 `to_ref`，但同一 `to_ref` 在 scope 内最多一个 active `from_ref`。 |
| `dedupe_key` | no | `array<string>` | 默认完整 tuple；可声明如 `["board_space_id", "to_ref"]`。 |
| `max_to_per_from` | no | `integer` | 每个 `from_ref` 的 active `to_ref` 上限。 |
| `max_from_per_to` | no | `integer` | 每个 `to_ref` 的 active `from_ref` 上限。 |
| `multi_edge` | no | `boolean` | 只有 true 时允许同一 tuple 多条 active edge。 |
| `rank_field` | no | `string` | 有序关系的 rank 字段，默认 `rank`（顶层）。仅当 profile 把 rank 显式放在另一字段时声明；MUST NOT 指向 `fields.rank`，该路径在 v1 不合法。 |
| `on_conflict` | no | `enum(reject, close_previous, deterministic_winner, require_review)` | 并发冲突处理；默认 `deterministic_winner`。 |

```json
{
  "relation_kind": "assigned_to",
  "from_type": "flow",
  "to_type": "did",
  "scope": "realm",
  "cardinality": "many_to_one",
  "max_to_per_from": 1,
  "on_conflict": "reject"
}
```

声明为 multi-edge 的 relation profile MUST 显式定义去重 key、排序字段和 conflict 处理。

## 6. 冲突处理

Relation conflict 的默认处理为：候选先通过格式、签名、授权、时钟窗口和 causal dependency 检查；严格因果后继 supersede 前驱；互不可达候选不得靠 HLC、actor id、本地接收顺序、数据库 ID 或服务端插入顺序自动选边。若 relation profile 能用业务 lattice 合并则合并；否则输出 conflict bottom / diagnostic。

- `on_conflict="close_previous"` 只适用于因果上明确晚于旧 edge 的事件；并发互斥 edge 不得靠接收顺序关闭。
- `on_conflict="reject"` 表示 reducer 输出无 active 新 edge，并要求客户端重新基于最新 Anchor frontier 提交修复 Move。
- `require_review` MUST 输出可投影的 conflict 诊断，不得让两个互斥 active edge 同时进入 canonical projection。

## 7. 常见关系（按对象）

- **Flow**：见 [flow-and-message.md §7](./flow-and-message.md)。
- **Space**（Board / List）：见 [realm-and-space.md §3.5](./realm-and-space.md#35-cxspaceparent-cas-register-basis) 与 [§3.6](./realm-and-space.md#36-flow-位置)。
- **Message**：见 [flow-and-message.md §9.7](./flow-and-message.md)。
- **Morph**：业务自定义关系，由 Realm schema / Morph profile 声明。

## 8. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Space 位置语义：[realm-and-space.md §3.6](./realm-and-space.md#36-flow-位置)。
- Move / Anchor / Lattice：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Relation schema：`artifacts/schemas/relation.schema.json`。
