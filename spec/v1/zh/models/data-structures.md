---
title: Data Structures
---

## 1. 目标

本文定义 Contrix 核心数据结构的字段级规范，包括字段名、是否必填、类型、取值约束和语义说明。

本文不替代具体业务章节。若某个字段在业务章节中有更严格规则，以更具体章节为准；若业务章节只给出示例，则以本文字段定义作为基础 schema contract。

## 2. 类型记法

| 记法 | 含义 |
| --- | --- |
| `string` | JSON string。 |
| `boolean` | JSON boolean。 |
| `integer` | JSON integer，不能是 float。 |
| `number` | JSON number，必须满足 `encoding.md` 的 number profile。 |
| `object` | JSON object，字段名必须 snake_case。 |
| `array<T>` | JSON array，元素类型为 `T`。 |
| `map<T>` | JSON object，value 类型为 `T`。 |
| `enum(...)` | 枚举字符串。 |
| `timestamp` | RFC 3339 UTC string，必须以 `Z` 结尾。 |
| `did` | DID URI string。 |
| `id:<kind>` | `cx:<kind>:<ulid>` typed ID，或该 kind 在 `id-kind-registry.json` 声明的特殊 wire form。 |
| `hash` | `sha256:<lowercase_hex_digest>`。 |
| `cursor` | `cx:cursor:<base64url>` opaque string。 |

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `cx:device:<ulid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `cx:<kind>:<ulid>` 格式。这些标识符的编码规则由各自所在章节定义。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- 实现 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `cx:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `cx:device:<ulid>`，不得写成局部别名如 `dev_a` 或 `a`。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | typed ID 前缀决定对象种类（`cx:flow:` 即 flow 对象，依此类推）。 | 对象稳定 ID；前缀就是 type，不再单独写 `type` 字段。 |
| `space_id` | conditional | `id:space` | Space 外对象可省略。 | 所属 Space。 |
| `schema` | yes | `string` | SHOULD 是 `cx.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `created_by` | conditional | `did` | 系统派生对象可由 `derived_from` 替代。 | 创建主体（创建该对象的 Event 的 `actor_id`）。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST 不早于 `created_at`。 | 最近更新时间。 |
| `deleted_at` | no | `timestamp` | durable tombstone 可用。 | 逻辑删除时间。 |
| `state_changed_at` | conditional | `timestamp` | 所有具有 `state` 字段的对象（Flow / Place / Message / Morph / Relation）当 `state != active` 时 MUST 写入；reducer 派生为对应 state-transition Event 的 `created_at`。MUST 不早于 `created_at`，MUST ≤ `updated_at`（当后者存在时）。 | 最近一次 state 转换时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `fields` | no | `object` | 字段 schema 由对象类型自身的 `schema_refs` 决定。 | 扩展字段；v1 唯一标准扩展容器。 |

对象种类由 `id` 的 typed prefix（`cx:flow:` / `cx:space:` / ...）唯一决定；扩展字段统一走 `fields`，由对象 `schema_refs` 约束。Event Envelope 不是 Materialized Object，事件类型由顶层 `kind` 表达。

### 3.1 主体引用字段交叉对照

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Marker、Notification | 直接执行该 Event / 拥有该私有状态的 actor DID（`actor_type` 决定它是 user / agent / service 等）。 |
| `principal_id` | Actor Profile | Profile 对应的 principal DID；权限根。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。 |
| `issuer` | Capability Grant、Identity Receipt | 签发授权或 receipt 的 DID；必须持有签发权限。 |
| `subject` | Capability Grant | 被授权 DID 或 selector condition。 |
| `inviter` / `invitee` | Invite | 邀请方 DID / 被邀请 DID。 |
| `created_by_principal` | Space | Space create event 的授权 principal（与该事件 `actor_id` 一致）。 |

这些不是同一字段的别名，每条都有独立语义角色；该表用于读 spec 时快速建立对应关系。

### 3.2 State 枚举对齐表

各对象的 `state` 字段值不完全相同（部分名字承载了已稳定的 `cx.*.tombstone` event 命名约定），但在 reducer / projection 语义层等价于以下规范状态机：

| 规范状态 | 语义 | Flow | Place | Message | Morph | Relation | Space |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | 当前可用 | `active` | `active` | `active` | `active` | `active` | `active` |
| `archived` | 软隐藏，UI 默认不展示，可撤销 | `archived` | `archived` | — | `archived` | — | `archived` |
| `redacted` | 内容已根据 redaction policy 清除，envelope 与审计元数据保留 | `redacted` | — | `redacted` | `redacted` | `tombstone`（合并 deleted+redacted） | — |
| `deleted` | 不可逆删除：content / encrypted_payload 清空，仅保留 envelope 用于审计 | `deleted` | `tombstoned` | `deleted` | `deleted` | `tombstone` | `tombstoned` |

约定：
- 写入路径 MUST 来自对应 reducer-input event（`cx.<kind>.archive` / `cx.<kind>.tombstone` / `cx.<kind>.redact` 或等价命名）；不得直接 PATCH 对象顶层 state。
- `state != active` 时 MUST 写入 `state_changed_at`（见 §3 公共字段）。
- "Place 没有 redacted"：Place 不承载用户 content（仅承载结构容器元数据），无需独立 redaction 状态；title / summary 的内容清理通过 `cx.place.tombstone` 或 `cx.redaction` 一并完成。
- "Message / Relation 没有 archived"：Message timeline 是有时序流，Relation 是边——两者都不需要"软隐藏可撤销"语义；要隐藏 Message 用 redaction，要解除 Relation 用删除即可。
- "Relation 用 `tombstone` 单一终态"：删除与 redaction 在边语义上不可区分（边只有"存在"或"不存在"），故合并为单一 `tombstone`；具体 reason 在对应 `cx.relation.delete` / `cx.redaction` event 中保留。
- Reducer 与 projection MUST 把 `tombstoned` / `tombstone` / `deleted` 视为语义等价的"不可逆删除"状态；UI 展示策略（隐藏 vs 显示 tombstone 占位符）由 client 根据对象类型决定。

## 4. Space

Schema id: `cx.schema.space.v1`

> Materialized Space 上以 **reducer 派生** 标注的字段（`policy_ref` / `default_discoverability` / `default_join_rule` / `history_visibility` / `federation_policy` 等）只是当前态快照。**写入路径** 必须使用对应 per-facet state event（`cx.space.policy` / `cx.space.join_rule` / `cx.space.history_visibility` / `cx.space.discovery` / `cx.space.policy_components` / ...），不得直接 PATCH Space 对象更新这些字段。`encryption_profile` 在 create event 时锁定，后续不可变。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `cx:space:` 开头。 | Space ID。 |
| `schema` | yes | `cx.schema.space.v1` | 固定为 Space schema id。 | 对象 schema。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `security_class` | no | `enum(standard, high_assurance)` | 默认 `standard`。`high_assurance` MUST 满足 `federation_policy ∈ {closed, restricted, quarantine}`，并 SHOULD 使用更严的 resolver / E2EE / 审计默认值。schema enforce 见 `space.schema.json`。 | 安全等级标签。 |
| `created_by_principal` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 registry 中的对象 schema，例如 `cx.schema.space.v1`，或实现 profile。 | 启用 schema。 |
| `relation_profiles` | no | `array<RelationProfile>` | 可由 Space schema/profile 等价声明；同一 `(relation_kind, from_type, to_type, scope)` 至多一个 active profile。 | Relation 基数、去重和冲突规则。 |
| `policy_ref` | no | `id:policy` | **reducer 派生**，由 `cx.space.policy` 维护；若 create event 未声明则为空。 | 派生：当前 Space access policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | **reducer 派生**，由 `cx.space.discovery` 维护；create event 提供初值。详见 `discovery-directory.md`。 | 派生：默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | **reducer 派生**，由 `cx.space.join_rule` 维护；create event 提供初值。`invite` 表示只允许邀请加入；canonical state MUST 使用本枚举值。 | 派生：默认加入规则。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | **reducer 派生**，由 `cx.space.history_visibility` 维护；create event 提供初值。各取值 canonical 语义见 `authz/event-auth-state-resolution.md` §6。 | 派生：历史可见性。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420, external)` | create event 锁定；后续不得通过 Space update 改变。E2EE Space SHOULD 使用 `mls_rfc9420`。 | 加密配置（create-locked）。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | **reducer 派生**，由 `cx.space.policy_components` 中相关组件维护。sovereign 默认 SHOULD `closed`。`security_class=high_assurance` MUST 使用 `closed`、`restricted` 或 `quarantine`，禁止 `open`；schema enforce 见 `space.schema.json`。 | 派生：联邦策略。 |
| `anchor_profile` | no | `enum(single_did, threshold, open_set, mixed)` | **create-locked**。省略时 sovereign / closed deployment SHOULD 使用 `single_did`，开放联邦 SHOULD 使用 `open_set`。详见 `authz/event-auth-state-resolution.md`。 | Anchor finality profile。 |
| `hash_profile` | no | `enum(sha256, sha512, sha3_256, blake3)` | **create-locked**。Space 内 Anchor / Move id、state_root、Merkle leaf 等核心承诺字段使用的 hash 算法。默认 `sha256`。切换需要走 hash transition Anchor，详见 `authz/event-auth-state-resolution.md` §4.2.5。各算法 wire 形态见 `conformance/encoding.md` §3。 | Hash 算法 profile。 |
| `anchorer` | conditional | `object` | Genesis anchorer cell 的初值；`anchor_profile` 存在时 SHOULD 指定。支持 `single_did`、`threshold`、`open_set`、`mixed`。 | 派生：当前 Anchor 授权规则。 |
| `max_anchor_staleness_ms` | no | `integer` | Move `anchor_ref` 的 freshness 窗口。离线超过窗口的客户端必须 rebase 并重新签名。默认 24h。 | Move freshness。 |
| `cell_lattices` | no | `array<CellLattice>` | Space-specific 扩展 cell family 的 lattice 声明；核心 cell family 由 registry 声明。 | Lattice 扩展。 |
| `co_write_policy` | no | `array<array<component>>` | 限制哪些 cell family 可以在同一 Move 中共同写入，避免跨域原子写滥用。 | Move 原子写约束。 |
| `retention_policy_ref` | no | `id:policy` | 可引用 retention policy。 | 保留策略。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

产品语义（个人 / 项目 / 组织 / enclave 等）使用 `Space.fields` / `schema_refs` / `labels` 表达；安全等级使用 `security_class` 字段（`standard` / `high_assurance`，后者强制 `federation_policy != open`）。

每个 `cx:space:` ID 都直接是 security/sync/auth/E2EE 边界。授权、membership、history visibility、E2EE、federation、retention、plaintext-visible service 和 policy server 解析全部以该 Space 为根，无需运行时 dispatch。结构性容器（看板、列、泳道、calendar bucket 等）使用独立的 `cx:place:` 对象表达，不再复用 `cx:space:` 类型；详见 §4a。

## 4a. Place

Schema id: `cx.schema.place.v1`

Place 是 Space 内部的**结构性分组对象**——看板、列、泳道、calendar bucket、document outline group 等都是 Place。Place **永远不是**安全边界：它没有自己的 membership、policy、history visibility、E2EE group 或 federation policy；授权解析透明回退到所属 Space。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:place` | 以 `cx:place:` 开头。 | Place ID。 |
| `schema` | yes | `cx.schema.place.v1` | 固定。 | 对象 schema。 |
| `space_id` | yes | `id:space` | MUST 指向 `cx:space:`，**MUST NOT** 指向另一个 `cx:place:`。 | 所属 Space（安全边界）。 |
| `parent_ref` | no | `id:place` 或 `id:space` | 在结构层级中的父；可以是 `cx:place:`（如列的父是看板）或同 `space_id` 的 `cx:space:`（Place 在 Space 根）。省略表示 Space 根。 | 结构层级父。 |
| `kind` | yes | `string` | v1 标准 kind 包括 `board`、`list`。Profile 可注册新 kind（如 `swimlane`、`calendar_bucket`、`page_group`），未注册 kind MUST `schema_violation`。 | Place 类型。 |
| `title` | yes | `string` | 1..256 chars。 | 显示名。 |
| `summary` | no | `string` | <= 2048 chars。 | 简短说明。 |
| `rank` | no | `string` | 见 `encoding.md` §9。 | 在 parent 内的位置。 |
| `schema_refs` | no | `array<string>` | 可选 schema/profile 引用，进一步约束本 Place 容纳的 Flow 类型 / fields。 | Place schema 扩展。 |
| `fields` | no | `object` | kind-specific 字段：例如 `kind=list` 的 `wip_limit`，`kind=board` 的默认 view ref。 | 扩展字段。 |
| `labels` | no | `array<string>` |  | 用户/系统标签。 |
| `avatar_blob_ref` | no | `id:blob` |  | Place 图标。 |
| `state` | no | `enum(active, archived, tombstoned)` | 默认 `active`。`archived` 由 `cx.place.archive` reducer 设置（可逆 UI 隐藏）；`tombstoned` 由 `cx.place.tombstone` reducer 设置（不可逆，引用尚存的 active Flow 时 MUST schema_violation）。 | Place 生命周期状态。 |
| `state_changed_at` | no | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

### 4a.1 Place 行为

- **授权**：Place 自身不持有 capability、membership 或 policy。任何对 Place 的写入（`cx.place.create` / `cx.place.update` / `cx.place.archive` / `cx.place.tombstone` / `cx.place.parent`）的授权检查 MUST 落到所属 `space_id` 的 Space membership + capability。Place 上 `cx.flow.move` 类操作的授权检查仍由 Space 决定。
- **同步与联邦**：Place 跟随所属 Space 同步；它**不**形成独立 federation transaction 单位。Place 的 Move 与 Anchor 共享 Space 的 anchor pipeline。
- **加密**：Place **永远没有**自己的 MLS group。E2EE Space 中 Place 元数据（title、rank 等）按 Space 的 encryption_profile 处理。
- **生命周期**：archive Place = UI 隐藏；tombstone Place = 不可逆删除（但 Space 与已被关联 Flow 都仍存在）。这与 archive/tombstone Space（影响成员、E2EE、history）的语义截然不同——Place lifecycle 仅影响 UI 分组。
- **嵌套**：Place 之间可以嵌套（看板里的列），通过 `parent_ref` 表达；`cx.place.parent` event 是该字段的 reducer-input。Place 之间嵌套不得跨 Space——`parent_ref` 引用的 Place 必须 `space_id` 相同。
- **位置**：Flow 在 Place 中的位置由 active `contains` Relation + Flow position event（`cx.flow.move` / `cx.flow.reorder`）维护，不由 Flow canonical object 自带 `place_id` 表达。`cx.flow.move` payload 使用 `target_place_id` 字段。

### 4a.2 Lifecycle 与 Cascade 规则

**Archive Place**：

- 由 `cx.place.archive` 把 `state` 设为 `archived` 并写入 `state_changed_at`；该 Place 在默认 view 中被隐藏。
- Archive **不**自动级联到内部 Flow 或 child Place。具体级联策略由 Place schema/profile 声明，缺省策略：
  - 内部 Flow 的 `contains` Relation 保留（Flow 仍在该 Place，但不可见）；用户在 unarchive 后看到的位置一致。
  - Child Place（List 在 Board 内）保留，跟随 parent 一起被默认 view 隐藏。
  - 客户端 SHOULD 在 archive 前提示用户 "X 个 Flow / Place 将一起隐藏"；reducer 不强制 relocate。

**Tombstone Place**：

- 由 `cx.place.tombstone` 把 `state` 设为 `tombstoned` 并写入 `state_changed_at`；不可逆。
- Reducer 在接受 `cx.place.tombstone` 前 **MUST** 校验：
  - 不存在指向该 Place 的 active `contains` Relation（即所有 Flow 已被 relocate 或它们也在被同批次 tombstone）。
  - 不存在 `parent_ref = <this_place>` 且未 tombstone 的 child Place。
  - 校验失败时返回 `failed_precondition` (`reason="place_has_live_dependents"`)，附带未清空的依赖列表。
- Tombstone 一个引用了**已 tombstone Place** 的 child（即 `parent_ref` 指向 dangling Place）：reducer SHOULD 接受（这是依赖清理路径），但 MUST 同时把该 child 标记为 `parent_ref_dangling=true` 投影 hint，让 UI 显示孤立状态。
- Tombstone 后 Place 元数据本身保留（用于 audit），但 `title` / `summary` 等用户内容 SHOULD 通过 redaction Move 清理。

### 4a.3 `cx.place.parent` cas-register basis

`cx.place.parent` 写入 cell `cx:cell:cx.component.place.parent.v1:<place_id>`（`cas-register, bottom=reject`）。Move 的 precondition `head_eq` 表达期望的 pre-state：

- **首次 set**（Place 刚 create，尚无 parent 记录）：precondition 使用 `head_eq null`。Reducer 在 cell pre-state 为初始（无任何 add/set）时只接受 `head_eq null` 的 Move；任何带具体 value 的 `head_eq` 在初始 cell 上 `failed_precondition`。
- **从 A 改为 B**：precondition 使用 `head_eq <A_place_id>`，effect 是 `set <B_place_id>`。
- **并发 reparent**：两个 Move 都用 `head_eq <A>` 但 set 不同 target，Anchor batch 内被识别为 sibling → cas-register 返回 `⊥`（kind=conflict）；依赖该 cell 的后续 Move fail_bottom，必须走 §8 conflict-recovery（带 state_witness + inclusion_proof）。
- **不允许 self-loop**：`cx.place.parent.set value == this_place_id` MUST schema_violation。
- **不允许跨 Space**：effect value MUST `space_id` 与 cell subject Place 的 `space_id` 相同；reducer 校验失败 `failed_precondition`。

Conformance fixture `move-anchor-lattice-fixture.json` SHOULD 覆盖三种场景：first-set、change-from-A-to-B、并发 reparent。

### 4a.4 `cx.flow.move` / `cx.flow.reorder` cas-register basis

为与 §4a.3 的 lattice 模型对称，Flow 在 Board 内的位置由 cas-register cell 而**不是** reducer-side dedup tuple 决定。一个 Flow 在某个 Board 内的 active 位置占用一个 cell：

```text
cell_id     := cx:cell:cx.component.flow.position.v1:<board_place_id>:<flow_id>
lattice     := cas-register
bottom      := reject
value shape := { "list_place_id": id:place, "rank": string } | null
```

写入语义：

- `cx.flow.move` 的 effect 是 `set { list_place_id, rank }`，precondition `head_eq` 表达 Move 提交者期望的 pre-state（即 §9.1 中 `expected_position`）：
  - **首次进入 Board**：`head_eq null`，effect `set { <target_list>, <rank> }`；
  - **跨 List 移动**：`head_eq { <from_list>, <from_rank> }`，effect `set { <target_list>, <new_rank> }`；
  - **从 Board 移除**：`head_eq { <from_list>, <from_rank> }`，effect `set null`（reducer 同步删除对应 `contains` Relation）。
- `cx.flow.reorder` 写同一 cell，但要求 effect 的 `list_place_id` 与 pre-state 的 `list_place_id` 相同；改 list 必须走 `cx.flow.move`，reducer 在写入 cell 前静态拒绝试图通过 reorder 改 list 的 effect。
- **并发 move/reorder**：两个 Move 都用同一 `head_eq` 但 set 不同 value，cas-register 返回 `⊥`（kind=conflict）；依赖该 cell 的后续 Move fail_bottom，必须走 §8 conflict-recovery。这取代了早期"reducer 关闭旧 position edge + tuple dedup"的分流：tuple dedup 仍是 projection 不变量，但**真相由 cell 决定**，并发竞态收敛到正式的 cas-register 冲突而非"先到先赢的接收顺序"。
- **跨 Board**：每个 `(board_place_id, flow_id)` 对应独立 cell；Flow 同时出现在不同 Board 是合法的（看板视图各自独立），所以 reducer **不**跨 Board 执行 cell join；仅在同一 Board 内强制单 active list。
- **`contains` Relation 是派生投影**：`list_place_id --contains--> flow_id` Relation 由 cell value 派生；客户端不得通过 `cx.relation.create/delete` 直接编辑该 Relation 来移动 Flow，必须使用 `cx.flow.move`。reducer 收到对该派生 Relation 的直接写入 MUST `schema_violation`。
- **Self-loop / 跨 Space**：effect value 的 `list_place_id` MUST 与 cell subject 的 `board_place_id` 共享同一 Space；不一致即 `failed_precondition`。

Conformance fixture `move-anchor-lattice-fixture.json` SHOULD 覆盖：first-move-into-board、cross-list-move、in-list-reorder、并发 move-to-different-list（产生 ⊥）、cross-board-independent-cells。

### 4a.5 与 cx:flow:、cx:space: 的关系

```text
cx:space:01...  ← security boundary
├─ cx:place:01...  kind=board     ← 看板（Place）
│  ├─ cx:place:01...  kind=list   ← 列（Place）
│  │  └─ contains → cx:flow:01...  ← Flow 通过 Relation/position event 入列
│  └─ cx:place:01...  kind=list
└─ cx:place:01...  kind=calendar_bucket  ← 未来扩展
```

每条 typed ID 一眼即知其角色：

- `cx:space:` → 安全边界，永远是授权/E2EE/federation 决策终点。
- `cx:place:` → 结构容器，永远透明回退到 `space_id`。
- `cx:flow:` → 协作主对象，永远在某 `space_id` 内；位置由 Place + position relation 决定。

## 5. Actor Profile

Schema id: `cx.schema.actor_profile.v1`

Actor Profile 是 Actor 在协作图中的展示镜像，不是权限主键。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:actor_profile` | Actor Profile 是标准对象。 | Profile 对象 ID。 |
| `space_id` | no | `id:space` | 全局 profile 可省略。 | 所属 Space。 |
| `principal_id` | yes | `did` | 权限仍以 DID/capability 为准。 | Principal DID。 |
| `actor_type` | yes | `enum(user, org, team, agent, service, device, integration)` |  | Actor 类型。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, suspended, deactivated, deleted)` | 账户生命周期见 `account-lifecycle.md`。 | 状态。 |
| `accountable_to` | no | `array<did>` | agent/托管账号 SHOULD 设置。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

`principal_id` 是授权、签名和审计归属的根；`actor_type` 只是该 DID 在协作图中的展示和策略分类。`actor_type="device"` 表示该 DID 被作为设备级或 pairwise device principal 直接行动；若设备只是某个用户/组织 principal 的授权设备，则 Event 仍以用户/组织 DID 作为 `actor_id`，设备身份通过 proof `verification_method`、`device_id`、`cx.device.authorized` 或 session grant 表达。`team`、`agent`、`service` 和 `integration` MAY 使用独立 DID，也 MAY 由 `accountable_to` 指向控制/责任 principal；它们不会因为 `accountable_to` 自动继承权限。

## 6. Standard Objects

Space、Place、Flow、Message 是标准对象。Place（`kind=board` / `kind=list` / 其他 profile 注册形态）表达 Space 内部的结构容器；Flow 通过 track primary 解析规则表达协作主对象的默认入口。

### 6.1 Flow

Schema id: `cx.schema.flow.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:flow` | 以 `cx:flow:` 开头。 | Flow ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `title` | yes | `string` | 1..512 chars。 | 标题。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 一句话/一段话简介。 |
| `body` | no | `ContentBlock` | 见 `content-types.md`。 | 富文本正文。 |
| `encrypted_payload` | conditional | `EncryptedPayload` | 与 `body` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹 Flow synthesis 正文或附件内容。 |
| `tracks` | yes | `array<FlowTrack>` | 至少 1 项；`name` 在同一 Flow 内唯一；至多 1 项 `is_primary=true`。 | 轨道定义、默认入口与轨道访问继承。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

`tracks` 是 active track 定义数组。标准 track name 为 `synthesis` 与 `discussion`，profile MAY 声明更多 track name。`synthesis` 承载标题、摘要、正文、结构化字段和状态等正式表达。`discussion` 在启用时承载讨论能力，例如 `profile`、timeline profile 与 track-local fields。

**Track 是纯展示 / 时间线分段标识，不携带独立的 membership / 权限 / history visibility / E2EE**。Track 的访问语义完全继承自所属 Space（或 `discussion_space_ref` 指向的 child Space，见下文）。早期 v1 草案曾允许 `tracks[].access` 子对象表达 `track_scoped` 的 hybrid 模型，该机制已被移除——任何需要独立访问域的 discussion 必须升级为 child Space。`assigned_to`、watchers 或其他业务关系不会自动成为 discussion 成员，除非 Space policy 明确把它们映射为授权条件。

`FlowTrack` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | yes | `string` | `^[a-z][a-z0-9_]{0,63}$`；同一 Flow 内唯一。 | Track 稳定名。 |
| `is_primary` | no | `boolean` | 同一 Flow 至多一个 track 为 true；省略或 false 均表示无显式 primary。 | 是否为显式默认入口。 |
| `profile` | no | `string` | 由 Space schema/profile 定义；标准 discussion profile 可用 `discussion`、`announcement`、`support`、`activity`、`review`、`external`。 | track 交互 profile（pure UI hint）。 |
| `template` | no | `string` | track profile 可声明结构模板。 | 模板引用。 |
| `fields` | no | `object` |  | track-local 扩展字段（pure UI hint，不影响访问）。 |

#### 6.1.1 Discussion 独立 Space（替代 track_scoped）

需要让 discussion 拥有独立 membership、history visibility 或 MLS group 时，**不再**通过 track hybrid 表达，而是创建一个 child Space 并通过 Flow.discussion_space_ref 引用：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `discussion_space_ref` | no | `id:space` | 必须是同 organization / federation 范围内的 Space。 | 该 Flow 的 discussion 时间线、成员、E2EE group 由该子 Space 承载。 |

规则：

- 未设置 `discussion_space_ref` 时，discussion 时间线事件直接写在 Flow 所属 Space，访问规则完全等于父 Space。
- 设置 `discussion_space_ref` 时，所有 discussion-side `cx.message.*` / `cx.reaction.*` / track membership 写入 MUST 使用该 child Space 的 `space_id`；Flow synthesis 和 discussion 是两个独立 reducer 视图，不共享 cell。
- 同一 Flow MUST NOT 同时存在 track hybrid（不存在）+ child Space 引用——hybrid 已废弃，只有 child Space 一种方式。
- Flow 的 parent Space 与 `discussion_space_ref` Space 之间的关系建议用 `cx.space.parent` / `cx.space.child` 或独立的 governance 关系表达；reducer 不强制 hierarchy，授权仍按各自 Space policy 独立判断。

Primary track 解析规则：

1. 若恰好一个 track 设置 `is_primary=true`，它是 primary。
2. 若没有显式 primary 且存在 `name="synthesis"`，`synthesis` 是 primary。
3. 若没有显式 primary 且只有一个 track，该唯一 track 是 primary。
4. 若没有显式 primary，且 profile 声明了可验证默认 track，使用该默认 track。
5. 仍无法唯一确定时，Reducer MUST fail closed，要求写入 `cx.flow.track.set_primary` 或等价修复事件。

### 6.2 Place（看板 / 列 / 泳道 / Calendar Bucket / …）

Place 详细定义见 §4a。这里仅提示与 Flow 的关系：

- 看板 = `cx:place: kind=board`；列 = `cx:place: kind=list`；其他结构容器（`swimlane`、`calendar_bucket`、`page_group` 等）由 profile 注册。
- Place 通过 `space_id` 绑定到所属 Space（安全边界），通过 `parent_ref` 表达 board → list 嵌套。
- Place **不**继承或叠加 Space 的安全语义字段——它没有自己的 `history_visibility` / `encryption_profile` / `federation_policy` / `default_join_rule`；这些字段一律由所属 Space 提供。
- `cx.place.parent` 是 Place 父子关系的 reducer-input event（`cas-register, bottom=reject`），保证一个 Place 至多一个 active parent。
- List 内 Flow 排序、WIP enforcement、card 位置通过 Relation 与 `cx.flow.move` / `cx.flow.reorder` 事件表达；Place 本身不得被当作 Message timeline、成员房间或权限主键。
- `cx.flow.move` payload 字段 `target_place_id` 指向目标 List Place；不再使用 `target_list_id`。

### 6.4 Message

Schema id: `cx.schema.message.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:message` | 以 `cx:message:` 开头。 | Message ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `flow_id` | yes | `id:flow` |  | 所属 Flow。 |
| `track` | yes | `string` | 必须匹配 `^[a-z][a-z0-9_]{0,63}$`，并且必须是目标 Flow 当前 active 的 track name。v1 reducer 默认只识别 `discussion`；profile 可声明额外 track name 承载 Message timeline，但 v1 wire 互操作 SHOULD 使用 `discussion`。 | 所属 Flow 轨道。 |
| `content` | conditional | `object` | 富文本/blocks 见 `content-types.md`；`state=active` 且未加密时必填。 | 消息正文。 |
| `encrypted_payload` | conditional | `EncryptedPayload` | 与 `content` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹消息正文与附件内容。 |
| `state` | yes | `enum(active, redacted, deleted)` | 默认 `active`。`redacted` 由 `cx.message.redact` reducer 设置（content 被替换为 redaction tombstone 但消息槽保留）；`deleted` 表示消息整体被治理或 retention 清除（content / encrypted_payload MUST 被清空，仅保留 envelope 元数据用于审计）。**与 Flow.state / Place.state 在顶层 schema 上对齐**，不再用 `fields.visible_state` 表达可见性。 | 消息生命周期状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `revision_root` | no | `id:message` | 第一条 revision MUST 等于 `id`；后续 revision 引用 chain 起点。同一 `revision_root` 下的 revision 形成有序 chain，由 `cx.message.revise` reducer 维护。 | revision chain 起点（顶层 schema-validated）。 |
| `edited_at` | no | `timestamp` | revision chain 中 latest revise event 的 `created_at`；首次 create 后未编辑时缺省。MUST 不早于 `created_at`。 | 最近一次编辑时间。 |
| `redaction_ref` | conditional | `id:event` | `state=redacted` 时必填，指向触发 redaction 的 `cx.message.redact` event；其他 state MUST 缺省。 | redaction event 引用。 |
| `fields` | no | `object` | 客户端 metadata、reaction summary 等扩展字段；不再承载 revision / visibility 状态。 | 扩展字段。 |
| `created_by` | yes | `did` |  | 发送者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

> **schema 迁移说明**：早期草案把 `revision_root` / `visible_state` 藏在 `fields` 黑盒中，缺乏 schema 验证、易被实现各自命名。v1 把这些字段提升到顶层；同时用 `state` 顶层枚举替代 `fields.visible_state`、用 `redacted: true` 单一 boolean。`fields.revision_root` / `fields.visible_state` / `fields.redacted` 在 v1 wire 上 MUST 被拒绝（`schema_violation`），不接受双源并存。

## 7. Morph and Facets

Schema id: `cx.schema.morph.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:morph` | 以 `cx:morph:` 开头。 | Morph ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `morph_type` | yes | `string` | 标准值见业务 profile，扩展不得使用未注册 `cx.` 前缀。 | 开放类型。 |
| `facets` | no | `map<FacetConfig>` | 未知 facet 必须由 Space schema / Morph profile 声明。 | Morph 暴露哪些已声明能力 hint。 |
| `title` | no | `string` | SHOULD <= 512 chars。 | 标题。 |
| `summary` | no | `string` |  | 摘要。 |
| `content` | no | `object` | 富文本/blocks 见 `content-types.md`。 | 正文内容。 |
| `encrypted_payload` | no | `EncryptedPayload` | 与 `content` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹 Morph 正文内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 自身属性。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

标准 `facets` 名称作为 schema/profile 声明后的 hint / 查询标签使用：

| Facet | 说明 | 典型字段/关系 |
| --- | --- | --- |
| `container` | 提示对象可按显式 relation/profile 作为容器投影。 | `child_object_types`, `relation_kinds`, `ordering`, `exclusive_scope`。 |
| `replyable` | 提示对象可按声明的 reply relation 被回复，形成 thread/discussion。 | `reply_object_types`, `reply_relation_kind`, `time_field`, `redaction_policy`。 |
| `schedulable` | 提示对象有声明的时间窗口，可进入 calendar/gantt 投影。 | `start_field`, `end_field`, `timezone_field`, `dependency_relation_kinds`。 |
| `assignable` | 提示对象有声明的分配字段或关系。 | `assignee_relation_kind` 或 `assignee_field`。 |
| `stateful` | 提示对象有显式 profile 定义的受控状态机。 | `state_field`, `states`, `transition_policy`。 |
| `rankable` | 提示对象有声明的稳定手动排序 rank。 | `rank_field`, `rank_profile`, `collision_policy`。 |
| `reviewable` | 提示对象有声明的审核/审阅状态。 | `review_state_field`, `reviewer_relation_kind`, `priority_field`。 |
| `notifiable` | 提示对象可按声明的 notification profile 派生 notification/inbox/read state。 | `notification_types`, `read_state_policy`。 |
| `documentable` | 提示对象可按声明的 document profile 作为文档或 section root。 | `section_relation_kind`, `section_order_field`, `body_field`。 |
| `renderable` | 提示对象声明允许的默认展示面。 | `renderers`, `title_field`, `summary_field`, `media_field`。 |

`query.facets`、`collection.item_facets` 和 `graph.node_facets` 的数组语义为 AND：候选对象 MUST 同时具备列出的全部 facet。`container.child_facets` 与 `replyable.reply_facets` 使用 `{all?, any?, none?}` 选择器。

Facet 配置 MUST NOT 成为授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作的唯一规范来源。这些语义必须由 Space schema / Morph profile / event registry / capability action 明确定义。

## 8. Relation

Schema id: `cx.schema.relation.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:relation` | 以 `cx:relation:` 开头。 | Relation ID。 |
| `space_id` | yes | `id:space` | Relation 所在 Space。 | 所属 Space。 |
| `relation_kind` | yes | `string` | 标准值见下方。 | 关系语义。 |
| `from_ref` | yes | `string` | MUST 是 `cx:<kind>:...` 或 DID。 | 起点对象/Actor/Space 引用。 |
| `to_ref` | yes | `string` | MUST 是 `cx:<kind>:...` 或 DID。 | 终点对象/Actor/Space 引用。 |
| `rank` | no | `string` | 见 `encoding.md` §9。**与 Place.rank 顶层字段对齐**——v1 把 rank 提升到顶层，`fields.rank` 在 wire 上 MUST 被拒绝（`schema_violation`），不接受双源并存。 | 有序关系（如 `contains list -> flow`）的稳定 rank。 |
| `fields` | no | `object` | 可放 role、edge metadata；MUST NOT 包含 `rank`（已提升到顶层）。 | 关系属性。 |
| `state` | no | `enum(active, tombstone)` | `tombstone` 同时覆盖删除与 redaction；原因保存在对应 `cx.relation.delete` / `cx.redaction` event 上，不再写入物化对象。 | 关系状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

标准 `relation_kind`：

```text
contains, belongs_to, replies_to, depends_on, blocks, mentions,
assigned_to, references, derived_from, attached_to, has_default_view,
summarized_from, promoted_from_discussion
```

> **Reserved for extension profiles**：早期草案曾把 `produced` / `used` / `triggered_by` / `has_log` 列为标准 kind，但 v1 没有任何 schema/profile/fixture 定义其 from/to 类型、基数或 capability action，无法支撑互操作。这些名字在 v1 wire 上视为**未注册的 relation_kind**——实现遇到时 SHOULD 保留为不透明边并在 projection 层标记 `unknown_relation_kind`，**MUST NOT** 据此自动推断容器、依赖或可见性语义。它们保留为未来 agent workflow extension profile 的候选名，profile 注册前 producer 不应使用。

标准 Relation 基数表：

| `relation_kind` | 默认基数 | 作用域与去重规则 |
| --- | --- | --- |
| `contains`：`Place(kind=board) -> Place(kind=list)` | `one_to_many` | 一个 Board 可包含多个 List；同一 List 在同一 Space 内 MUST 至多有一个 active Board parent（由 `cx.place.parent` cas-register 保证）。 |
| `contains`：`Place(kind=list) -> Flow` | `one_to_many` with board-exclusive target | 一个 List 可包含多个 Flow；同一 Flow 在同一个 Board 内 MUST 至多处于一个 active List。去重/互斥 key 为 `(board_place_id, flow_id)`，与 `object-model-core.md` 的位置唯一性一致。 |
| `contains`：其他对象组合 | `many_to_many` unless profiled | 默认只按完整 tuple 去重；若对象被当作容器使用，Space schema/profile MUST 声明更严格基数。 |
| `belongs_to` | `many_to_one` | 作为 `contains` 的显式 parent 关系时，同一 `from_ref` 在同一作用域内至多有一个 active `to_ref`。优先使用 canonical `contains` 表达容器包含。 |
| `replies_to` | `many_to_one` | 一个 Message 或 reply object SHOULD 只有一个 direct parent；额外链接用 `references` 或 `mentions`。 |
| `depends_on`, `blocks` | `many_to_many` | 按 `(space_id, relation_kind, from_ref, to_ref)` 去重；循环检测由 workflow/profile 规则决定。 |
| `mentions`, `references`, `derived_from`, `attached_to`, `summarized_from`, `promoted_from_discussion` | `many_to_many` | 按完整 tuple 去重；多条语义不同的边必须用 `fields.role`、不同 `relation_kind` 或 profile 声明的 multi-edge key 区分。 |
| `assigned_to` | `many_to_many` | 一个 Flow MAY 同时分配给多个 Actor；同一 Actor 只保留一条 active assignment edge。需要单负责人语义时，Space schema/profile MUST 声明 `max_to_per_from=1` 或单独的 owner relation。 |
| `has_default_view` | `many_to_one` | 同一 `from_ref` 在同一 Space 内至多有一个 active default View；设置新默认 View MUST 关闭旧 active edge。 |

未声明为 multi-edge 的 Relation MUST 由 reducer 按 `(space_id, relation_kind, from_ref, to_ref)` 去重。Events API MAY 拒绝同一 frontier 下显然重复的写入，但不能作为唯一去重机制；两个离线设备并发创建同一关系时，reducer 必须确定性选择一个 active winner，并把 loser 记录为 conflict 或 tombstone。

**跨 Space 强约束（reducer 必检）**：

- `contains` 与 `belongs_to` MUST NOT 跨 Space——reducer MUST 解析 `from_ref` / `to_ref` 指向的对象（Place / Flow / Message / Morph 等），确认其 `space_id` 与 Relation 自身 `space_id` 一致；任一不一致 MUST `failed_precondition`（`reason="cross_space_structural_relation"`）。`object-model-core.md §2.4.1` 给出的两端 enforce 责任表是这条规则的语义来源。
- 弱语义 `references` / `mentions` / `derived_from` / `summarized_from` / `depends_on` / `blocks` / `assigned_to` / `has_default_view` / `replies_to` 等 MAY 跨 Space，需走 §2.4.1 的"两次独立 capability check"路径，并按目标 Space policy 在 projection 层降级为 `lazy_link` / `locked` / `accessible` 状态。
- JSON Schema 层面无法在不引入冗余字段的前提下完整表达该约束（需要解析 typed reference 后再比 Space），因此 [`relation.schema.json`](../../artifacts/schemas/relation.schema.json) 的 `relation_kind` description 把该约束标记为 reducer-enforced；schema validation 通过仅代表线路形态合法，不代表 cross-Space 约束已通过。

Relation conflict 的默认处理为：候选先通过格式、签名、授权、时钟窗口和 causal dependency 检查；严格因果后继 supersede 前驱；互不可达候选不得靠 HLC、actor id、本地接收顺序、数据库 ID 或服务端插入顺序自动选边。若 relation profile 能用业务 lattice 合并则合并；否则输出 conflict bottom / diagnostic。`on_conflict="close_previous"` 只适用于因果上明确晚于旧 edge 的事件；并发互斥 edge 不得靠接收顺序关闭。`on_conflict="reject"` 表示 reducer 输出无 active 新 edge，并要求客户端重新基于最新 Anchor frontier 提交修复 Move。`require_review` MUST 输出可投影的 conflict 诊断，不得让两个互斥 active edge 同时进入 canonical projection。

Space schema、Space profile 或 `relation_profiles` MAY 对标准默认值收紧，但不得放宽会破坏互操作 projection 的标准互斥规则（例如同一 Board 内 Flow 只能处于一个 List）。`RelationProfile` 最小结构：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `relation_kind` | yes | `string` | 被声明的 relation kind。 |
| `from_type` | no | `string` | 起点类型约束，例如 `space`、`place:board`、`place:list`、`flow`、`message`、`morph:*` 或 `did`。 |
| `to_type` | no | `string` | 终点类型约束。 |
| `scope` | no | `enum(space, place, board, global)` | 基数和去重作用域；默认 `space`。`place` 表示在某 Place 内、`board` 是 `kind=board` Place 的简写。 |
| `cardinality` | yes | `enum(one_to_one, one_to_many, many_to_one, many_to_many)` | `one_to_many` 表示同一 `from_ref` 可有多个 `to_ref`，但同一 `to_ref` 在 scope 内最多一个 active `from_ref`。 |
| `dedupe_key` | no | `array<string>` | 默认完整 tuple；可声明如 `["board_place_id", "to_ref"]`。 |
| `max_to_per_from` | no | `integer` | 每个 `from_ref` 的 active `to_ref` 上限。 |
| `max_from_per_to` | no | `integer` | 每个 `to_ref` 的 active `from_ref` 上限。 |
| `multi_edge` | no | `boolean` | 只有 true 时允许同一 tuple 多条 active edge。 |
| `rank_field` | no | `string` | 有序关系的 rank 字段，默认 `rank`（顶层）。仅当 profile 把 rank 显式放在另一字段时声明；MUST NOT 指向 `fields.rank`，该路径已废弃。 |
| `on_conflict` | no | `enum(reject, close_previous, deterministic_winner, require_review)` | 并发冲突处理；默认 `deterministic_winner`。 |

```json
{
  "relation_kind": "assigned_to",
  "from_type": "flow",
  "to_type": "did",
  "scope": "space",
  "cardinality": "many_to_one",
  "max_to_per_from": 1,
  "on_conflict": "reject"
}
```

声明为 multi-edge 的 relation profile MUST 显式定义去重 key、排序字段和 conflict 处理。

## 9. Event Envelope（兼容层） 

Schema id: `cx.schema.event.v1`

Event Envelope 是 kind-routed payload 兼容层。v1 的协议状态收敛以 Move / Anchor / Lattice 为准；Event kind 可以作为 Move effect kind 与现有 Events API payload router 的稳定命名。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` | 事件稳定 typed ID。事件 canonical digest / proof hash 见 `conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | 标准 effect kind SHOULD 使用 `cx.` 前缀。Registry 可声明 `cell_family`、`cell_subject`、`lattice` 和 `bottom`，供 Move effect / 兼容 reducer 使用。 | 事件 kind。 |
| `space_id` | yes | `id:space` | Space create 可在 payload 中建立。 | 所属 Space。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链。 | 发送 Actor。 |
| `actor_seq` | yes | `integer` | 同一 actor 因果路径上严格递增；并发 sibling fork 可出现相同高度。 | Actor 链高度 / 防回退索引。 |
| `created_at` | yes | `timestamp` | 不能单独决定因果。 | 创建时间。 |
| `hlc` | yes | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。 | HLC。 |
| `prev_refs` | yes | `array<id:event>` | 可为空。 | Actor event chain 前序。 |
| `auth_refs` | yes | `array<id:event>` | create event 可为空；必须引用授权状态事件，不能直接引用 grant / policy object ID。 | 授权依赖。 |
| `requirements` | no | `object` | `requirements.{schema[], reducer, features[], critical_extensions[]}` 全部进入 canonical bytes 与 event digest；接收方 MUST fail closed 对未知 critical 项。`critical_extensions[]` 每项必须有 `id`、`scope`、`fail_closed=true`。 | 事件依赖声明（schema profile / reducer profile / feature / critical extension）。 |
| `redacts` | no | `id:event` 或 `hash` | 仅 redaction event 使用。 | 被撤回事件。 |
| `payload` | yes | `object` | 由 event kind schema 定义。 | 事件负载。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。 | 本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof。 | 签名证明。 |

Event Envelope 的顶层 `kind` 是唯一 payload discriminator。State convergence 不再从 envelope 推导 state slot；Move effect 必须显式给出 cell id 与 lattice op。`payload.type` 不得重复写入 `cx.*` Event kind。Payload 引用被创建对象时通过 `payload.object.id` 或 `payload.target_ref` 等 typed-id 字段表达，前缀（`cx:flow:` 等）即对象种类，不写单独的 `payload.object.type`。`actor_id` 是签署并提交该 Event 的 DID；物化对象的 `created_by` / `updated_by` 是 reducer 输出字段，通常来自对应 create/update Event 的 `actor_id`，但不得替代 Event proof、capability 或 Move refs 校验。启用 minimal-metadata E2EE profile 时，`actor_id` MAY 是 Space / Flow track scoped pairwise DID；真实 principal DID 的映射必须通过加密的 `cx.identity_link`、claim disclosure 或 policy 声明验证，不得把非 DID pseudonym 写入 `actor_id`。

Create 类 Event 的 `payload.object` MAY 使用完整对象 schema 做 wire validation，但接收方在进入 accepted set 前还必须执行跨字段语义校验：`cx.space.create.payload.object.created_by_principal` MUST 等于顶层 `actor_id`，`cx.flow.create` / `cx.morph.create` / `cx.profile.create` 中的 `payload.object.created_by` 或 `principal_id` MUST 等于顶层 `actor_id` 或被该 profile 明确授权的 controller，且 `payload.object.created_at` MUST 等于顶层 `created_at`。校验失败 MUST `schema_violation` 或 `capability_denied`，不得把 payload 中的创建者字段当作 proof、capability 或审计归属的替代来源。

`actor_seq` fork 约束：

- Producer SHOULD 为同一 `actor_id` 维护单调本地链，避免主动产生同高 sibling fork。
- 同一 `actor_id` 的非 genesis event MUST 在 `prev_refs` 中引用至少一个该 actor 的 accepted predecessor；该 predecessor 的最大 `actor_seq` 必须是当前 `actor_seq - 1`，除非 profile 明确声明恢复/导入场景。
- 相同 `(actor_id, actor_seq)` 的多个 event 是 sibling fork。它们没有隐含先后顺序；展示排序可使用 HLC，但协议状态生效必须使用 Move preconditions、Anchor frontier 与 Lattice join。
- 实现 MUST 对同一 `(actor_id, actor_seq, prev_frontier_hash)` 接受的 sibling 数量设置上限；v1 public profile 的上限为 16，超过后 MUST quarantine 或要求 actor chain repair。
- 被判定为 rejected 的 fork 不推进 actor accepted frontier，也不得作为后续 accepted event 的 predecessor。

`requirements.features[]` 与 `requirements.critical_extensions[].id` 必须使用可发现的 feature/profile 标识，并通过 service describe、profile registry 或 Space schema/policy 指向可验证定义。接收方不支持 critical feature 时 MUST fail closed；不得把未知 critical 语义当作普通未知字段保留后继续 accepted。

## 10. Proof

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `enum(detached_jws)` | 初版必须支持。 | 证明类型。 |
| `alg` | yes | `string` | 初版默认 `EdDSA`。 | 签名算法。 |
| `verification_method` | yes | `string` | DID URL。 | 公钥/设备方法。 |
| `payload_hash` | yes | `hash` | 必须绑定 canonical payload。 | 被签名 payload hash。 |
| `created_at` | yes | `timestamp` |  | 签名时间。 |
| `domain` | no | `string` | 跨服务 SHOULD 设置。 | 域绑定。 |
| `audience` | no | `string` 或 `array<string>` | 跨域/服务调用 SHOULD 设置。 | 受众绑定。 |
| `jws` | yes | `string` | detached JWS。 | 签名值。 |

## 11. View

Schema id: `cx.schema.view.v1`

View 是投影定义对象。它的 canonical state 只覆盖“如何看”：query、kind、renderer、typed config、visible fields、layout 和共享配置。它不得作为被投影对象的状态、位置、关系、权限或消息历史的唯一来源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:view` |  | View ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `kind` | yes | `enum(collection, timeline, graph, document, composite)` |  | 核心投影原语。 |
| `renderer` | no | `enum(board, card, row, table, calendar, gantt, timeline, thread, chat, forum, graph, tree, document, dashboard, custom)` | 不参与真相归约。 | 展示面提示；交互能力仍由对象类型、显式 schema/profile、capability 与 typed config 决定。 |
| `title` | no | `string` |  | View 名称。 |
| `query` | yes | `Query` | 见 `query-schema.md`。 | 数据查询。 |
| `visible_fields` | no | `array<string>` | dot path。 | 展示字段。 |
| `layout` | no | `object` | UI hint，不是权限。 | 布局配置。 |
| `collection` | conditional | `CollectionConfig` | `kind="collection"` 时 MUST 设置。 | 集合投影配置；看板、表格、日历、甘特、队列、矩阵都由该配置表达。 |
| `timeline` | conditional | `TimelineConfig` | `kind="timeline"` 时 MUST 设置。 | 时间线配置。 |
| `conversation` | conditional | `ConversationConfig` | 会话/讨论类 renderer SHOULD 设置，或 query 必须提供 anchor/relation。 | 会话配置。 |
| `graph` | conditional | `GraphConfig` | `kind="graph"` 时 MUST 设置。 | 图/树遍历配置。 |
| `document` | conditional | `DocumentConfig` | `kind="document"` 时 MUST 设置。 | 文档 section 配置。 |
| `dashboard` | conditional | `DashboardConfig` | `kind="composite"` 时 MUST 设置。 | 仪表盘 widget 配置。 |
| `sort` | no | `array<SortSpec>` | 与 query sort 等价或补充。 | 排序。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

若某个 UI 操作改变 Flow 所属 List、Flow rank、List rank、Flow discussion Message、Relation 或对象字段，必须使用对应对象 Event；只有改变共享 filter、sort、grouping、visible fields、renderer 或 layout 时才修改 View。个人偏好、临时排序、列宽、折叠状态和本地 pin MUST 使用 actor-private account data 或等价私有 Event。

`CollectionConfig` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_object_types` | conditional | `array<string>` | 可由 `item_facets` 替代；至少 1 项。 | 按对象类型过滤可投影为 item/card/row/message 的对象。 |
| `item_facets` | conditional | `array<FacetName>` | 可替代 `item_object_types`；至少 1 项。 | 按声明 hint 选择 item，例如 `rankable`、`reviewable`、`replyable`。 |
| `item_render` | yes | `enum(card, row, tile, compact, badge, message)` | 看板式展示 SHOULD 为 `card`。 | 默认展示面。 |
| `item_order_by` | yes | `array<SortSpec>` | 至少 1 项。 | item 稳定排序；拖拽类 collection SHOULD 使用 rank。 |
| `display_fields` | no | `array<DisplayColumn>` | dot path。 | 展示字段与格式。 |
| `grouping` | yes | `CollectionGrouping` |  | 分组/列/时间桶/矩阵配置。 |
| `selection_policy` | no | `enum(none, single, multiple)` | 默认 `multiple`。 | UI 选择策略。 |
| `count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 集合级计数策略。 |
| `page_size` | no | `integer` | 1..1000。 | 默认分页大小。 |

`CollectionGrouping` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | yes | `enum(none, field, relation_container, time_bucket, matrix)` |  | 分组模型。 |
| `field` | conditional | `string` | `mode="field"` 时必填。 | 字段分组路径。 |
| `lanes` | conditional | `array<object>` | `mode="field"` 时必填。 | 字段值列/泳道定义。 |
| `board_place_id` | conditional | `id:place` | `mode="relation_container"` 时必填，指向一个 `cx:place: kind=board`。 | Board Place。（旧名 `board_id` 已替换为 `board_place_id` 以避免与 Space ID 误读）|
| `container_relation_kind` | no | `string` | 默认 `contains`。 | root 到 collection/container 的关系。 |
| `item_relation_kind` | conditional | `string` | `mode="relation_container"` 时必填；不得隐式推断。 | container 到 item 的关系。 |
| `start_field` | conditional | `string` | `mode="time_bucket"` 时必填。 | 时间窗口起点字段。 |
| `end_field` | no | `string` |  | 时间窗口终点字段。 |
| `rows_by` / `columns_by` | conditional | `string` | `mode="matrix"` 时必填。 | 矩阵双轴字段。 |
| `hidden_count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 分组计数授权策略。 |
| `wip_limit_enforcement` | no | `enum(warn, reject, require_review)` | 默认 `warn`。 | 分组 WIP enforcement；只影响 reducer / review policy，不由 renderer 决定。 |

## 12. Policy

Schema id: `cx.schema.policy.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:policy` |  | Policy ID。 |
| `space_id` | no | `id:space` | 组织级 policy 可省略。 | 适用 Space。 |
| `policy_type` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_visibility, plaintext_visibility, media, applet, agent)` |  | 策略类型。 |
| `rules` | yes | `array<object>` | 每条规则必须有 `effect`。 | 策略规则。 |
| `default_effect` | yes | `enum(allow, deny, quarantine, require_review)` |  | 默认效果。 |
| `priority` | no | `integer` | 数值大者优先。 | 策略优先级。 |
| `valid_from` | no | `timestamp` |  | 生效时间。 |
| `valid_until` | no | `timestamp` |  | 过期时间。 |
| `created_by` | yes | `did` | 必须有 policy/admin capability。 | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

## 13. Capability Grant

Schema id: `cx.schema.capability.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:grant` |  | Grant ID。 |
| `space_id` | no | `id:space` | 全局 grant 可省略但 SHOULD 避免。 | 作用域。 |
| `issuer` | yes | `did` | 必须持有授予权限。 | 授权方。 |
| `subject` | yes | `did` 或 `object` | 可为 DID 或 condition selector。 | 被授权主体。 |
| `actions` | yes | `array<string>` | 例如 `cx.flow.update`、`cx.message.create`。 | 允许动作。 |
| `resources` | yes | `array<object>` | 资源 selector。 | 资源范围。 |
| `constraints` | no | `array<object>` | 见 [`authz/constraint-schema.md`](../authz/constraint-schema.md) §20.3 grant 示例。委托控制 MUST 通过 `constraint_type=delegation_control` 的 `max_delegation_depth` 表达；缺省（无 delegation_control 约束）等价于 `max_delegation_depth=0`，即不可转授。 | 约束条件。 |
| `parent_grant_id` | no | `id:grant` | derived grant 必填。 | 父授权。 |
| `valid_from` | no | `timestamp` |  | 生效时间。 |
| `valid_until` | no | `timestamp` |  | 过期时间。 |
| `revoked_by` | no | `did` | 撤销后设置。 | 撤销者。 |
| `revoked_at` | no | `timestamp` |  | 撤销时间。 |
| `proofs` | yes | `array<Proof>` |  | 授权签名。 |

## 14. Invite

Schema id: `cx.schema.invite.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:invite` |  | Invite ID。 |
| `space_id` | yes | `id:space` |  | 目标 Space。 |
| `inviter` | yes | `did` | 必须持有 invite capability。 | 邀请者。 |
| `invitee` | no | `did` | 3PID 邀请可为空。 | 被邀请 DID。 |
| `third_party_id` | no | `object` | 见 `third-party-invites.md`。 | 邮箱/手机号等外部标识证明。 |
| `join_rule_snapshot` | yes | `object` | 防止邀请后规则混淆。 | 邀请时 join rule。 |
| `capability_grant_refs` | no | `array<id:grant>` | 接受后才生效。 | 关联授权。 |
| `expires_at` | yes | `timestamp` | 默认不超过 7 天；高安全 Space SHOULD 不超过 24 小时。 | 过期时间。 |
| `state` | yes | `enum(pending, accepted, rejected, revoked, expired)` |  | 邀请状态。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

## 15. Read Marker

Schema id: `cx.schema.read_marker.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `string` | SHOULD 派生自 actor + space/view。 | 私有状态 ID。 |
| `actor_id` | yes | `did` | 只对该 actor 生效。 | 读取主体。 |
| `space_id` | yes | `id:space` |  | Space。 |
| `scope` | yes | `enum(space, flow, discussion, thread, view, message, morph)` |  | 已读范围。 |
| `scope_id` | no | `string` | scope 不是 space 时必填。 | 范围对象。 |
| `event_id` | yes | `id:event` |  | 已读到的事件。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

## 16. Notification

Schema id: `cx.schema.notification.v1`

Notification 是派生 inbox projection，不是 canonical truth。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `string` | SHOULD content-addressed 或 stable derivation。 | 通知 ID。 |
| `actor_id` | yes | `did` | 接收者。 | 通知主体。 |
| `space_id` | no | `id:space` |  | 来源 Space。 |
| `source_event_id` | yes | `id:event` |  | 来源事件。 |
| `notification_type` | yes | `enum(mention, reply, assignment, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` |  | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 17. Event Batch Receipt

Schema id: `cx.schema.event_batch_receipt.v1`

Event Batch Receipt 是可选审计/同步加速对象，不是 canonical history，也不是 reducer input。缺少 receipt 不得导致格式、签名、授权和因果均有效的 Event 被拒绝，除非 deployment profile 额外要求 witness。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `receipt_id` | yes | `id:receipt` |  | Receipt ID。 |
| `issuer` | yes | `did` | 必须控制签名 key。 | 签发者，可以是 principal、Principal Server 或 witness。 |
| `scope` | yes | `object` | SHOULD 包含 `actor_id`、`space_id` 或查询范围 hash。 | receipt 覆盖范围。 |
| `frontier` | yes | `object` | SHOULD 包含 `actor_seq`、`event_id` / event hash、HLC 或 Space frontier。 | 签发时前沿。 |
| `events` | yes | `array<id:event \| hash>` | 数组顺序参与 hash。 | 被 receipt 覆盖的 Event Envelope 引用。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `proofs` | yes | `array<Proof>` |  | Receipt proof。 |

## 18. Field Patch (cx.patch.v1)

非 create 类更新建议使用 `cx.patch.v1` 做字段增量；客户端不得自行定义私有 dot-path 语义替代该标准。

`cx.patch.v1` 为 map 类型：

- `key`: patch path（字段路径）。
- `value`: patch 操作，支持两种表达：
  - 直接值：等价于 `{"$op":"set","value":...}`。
  - 对象：`{"$op":"set|unset|add|remove","value":...}`。

patch path 规则：

- path 由 `snake_case` 标识符或反引号转义字段名组成；
- 默认仅支持对象路径，不支持数字数组下标；
- 对 schema 声明了唯一 key 的具名集合数组，path MAY 使用确定性 selector 段：`tracks[name=discussion].profile`。selector 字段必须是该数组项 schema 中声明唯一的 stable key，selector 值按 canonical JSON string 解析；匹配 0 项时 `set`/`add` MUST reject，匹配多项表示对象已违反 schema，reducer MUST fail closed；
- `unset` 不允许带 `value`；
- `set`、`add`、`remove` 必须带 `value`。

客户端不能把数字数组下标写入 path；如需更新无 stable key 的列表元素，必须将对象重建为具名集合项、用 profile 注册的 move/update event，或使用明确的 API 约束字段表示更新目标。
