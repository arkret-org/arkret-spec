---
title: Realm & Space
---

## 1. 目标

本文定义 Contrix 协作图中的两个一等对象：

- **Realm**（`cx:realm:`）：security / sync / auth / E2EE / federation 的硬边界。
- **Space**（`cx:space:`）：用户可理解的结构容器与导航节点，可表达 organization 下的 workspace、project、folder、board、list、section、calendar bucket 等形态；Space 自身不是安全边界。

本轮模型把旧 `Space` 的硬边界职责移动到 `Realm`，把旧 `Place` 的结构容器职责升格为新的 `Space`。因此：

- `Realm` 不再承担产品导航树职责，也不应被建模为 parent/child hierarchy。
- `Space` 承担层级、排序、分类、项目组织和工作流容器职责。
- 强保密差异通过切分 Realm 表达；同一 Realm 内的 capability / Group 只承诺操作隔离，不承诺对已入组成员的强读隔离。

Realm 之间只允许显式 link graph（governance / discoverability / import-export / confidential-extension 等关系），详见 [`realm-links.md`](./realm-links.md)。Space 层级与跨 Realm 导航见 [`space-hierarchy.md`](./space-hierarchy.md)。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Realm

### 2.1 概念

每个 `cx:realm:` ID 都是一个 security / sync / auth / E2EE 边界。以下语义全部以 Realm 为根解析：

- membership
- capability grant / revoke 的授权上下文
- history visibility
- E2EE / MLS group governance
- federation policy
- retention / legal hold
- plaintext-visible service
- policy server
- event frontier / Anchor pipeline

`Realm` 的语义接近“保护域”或“治理域”，不是“项目文件夹”。一个组织通常会拥有多个 Realm：公开项目、普通内部项目、机密项目、HR 项目、法务项目可以位于同一 Organization / Space tree 下，但落到不同 Realm。

`security_class=high_assurance` 是 Realm 的可选标签，进一步收紧 federation policy 与默认审计 / E2EE 选项。

### 2.2 Realm 与 MLS group

Realm 与 MLS group 不是同义词：

- 非 E2EE Realm 可以没有 MLS group。
- E2EE Realm 通常拥有一个 primary MLS group。
- Realm 还包含 policy、membership、history、sync frontier、federation、retention 和 capability 等语义；MLS group 只承载加密成员、epoch 和密钥演进。
- 实现 MAY 在同一 Realm 中声明辅助 MLS group（例如 reviewer subgroup、audit subgroup、sealed application group），但这些辅助 group 不改变 Realm 作为主内容边界的事实。

规范性规则：

- `encryption_profile` 是 Realm 的 create-locked 基线。
- 同一 Realm 内不允许把普通 Flow 任意混合成“有的 E2EE、有的非 E2EE”的保密等级拼盘。
- 若某个 Flow / discussion / artifact 需要不同读隔离或不同密钥资格，必须升级到另一个 Realm，并通过 Space / Relation / `discussion_realm_ref` 等显式引用连接。

### 2.3 Schema id 与字段

Schema id: `cx.schema.realm.v1`

> Materialized Realm 上以 **reducer 派生** 标注的字段（`policy_ref` / `default_discoverability` / `default_join_rule` / `history_visibility` / `federation_policy` 等）只是当前态快照。写入路径必须使用对应 per-facet state event（`cx.realm.policy` / `cx.realm.join_rule` / `cx.realm.history_visibility` / `cx.realm.discovery` / `cx.realm.policy_components` / ...），不得直接 PATCH Realm 对象更新这些字段。`encryption_profile` 在 create event 时锁定，后续不可变。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:realm` | 以 `cx:realm:` 开头。 | Realm ID。 |
| `schema` | yes | `cx.schema.realm.v1` | 固定。 | 对象 schema。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称；产品 UI MAY 隐藏或弱化它。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `security_class` | no | `enum(standard, high_assurance)` | 默认 `standard`。`high_assurance` MUST 满足 `federation_policy ∈ {closed, restricted, quarantine}`。 | 安全等级标签。 |
| `created_by_principal` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 `cx.schema.realm.v1`。 | 启用 schema / profile。 |
| `relation_profiles` | no | `array<RelationProfile>` | 同一 `(relation_kind, from_type, to_type, scope)` 至多一个 active profile。 | Relation 基数、去重和冲突规则。 |
| `policy_ref` | no | `id:policy` | reducer 派生。 | 当前 Realm access policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | reducer 派生。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | reducer 派生。 | 默认加入规则。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | reducer 派生。 | 历史可见性。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420, external)` | create-locked。 | 加密配置。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | reducer 派生。 | 联邦策略。 |
| `anchor_profile` | no | `enum(single_did, threshold, open_set, mixed)` | create-locked。 | Anchor finality profile。 |
| `hash_profile` | no | `enum(sha256, sha512, sha3_256, blake3)` | create-locked，默认 `sha256`。 | Hash 算法 profile。 |
| `anchorer` | conditional | `object` | Genesis anchorer cell 初值。 | 当前 Anchor 授权规则。 |
| `max_anchor_staleness_ms` | no | `integer` | 默认 24h。 | Event freshness 窗口。 |
| `cell_lattices` | no | `array<CellLattice>` |  | Realm-specific 扩展 cell family。 |
| `co_write_policy` | no | `array<array<component>>` |  | Move 原子写约束。 |
| `retention_policy_ref` | no | `id:policy` |  | 保留策略。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 2.4 最小示例

```json
{
  "id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "schema": "cx.schema.realm.v1",
  "title": "Launch Plan Confidential Realm",
  "created_by_principal": "did:web:acme.example",
  "schema_refs": ["cx.schema.realm.v1"],
  "default_discoverability": "invite_only",
  "default_join_rule": "invite",
  "history_visibility": "joined",
  "encryption_profile": "mls_rfc9420",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 3. Space

### 3.1 概念

Space 是用户和产品层可见的结构容器。它可以表达：

- organization 下的 workspace / project / folder / section
- board / list / swimlane / calendar bucket
- document outline group / page group
- 任意 profile 注册的结构节点

Space **不**拥有自己的 membership、policy、history visibility、E2EE group 或 federation policy。它通过 `realm_id` 和可选 `default_realm_ref` 解析到 Realm：

- `realm_id`：该 Space 对象自身 metadata 的 home Realm。创建、更新、archive、tombstone 该 Space 的事件写入这个 Realm。
- `default_realm_ref`：该 Space 下新建资源默认落入的 Realm。省略时继承最近 ancestor Space 的 `default_realm_ref`，再退回自身 `realm_id`。

这允许 UI 上的同一个 Space tree 跨越多个 Realm。例如 `/Acme/Projects` 下面的普通项目、机密项目和 HR 项目可以是兄弟 Space，但各自 `default_realm_ref` 不同。

### 3.2 Schema id 与字段

Schema id: `cx.schema.space.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `cx:space:` 开头。 | Space ID。 |
| `schema` | yes | `cx.schema.space.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | MUST 指向 `cx:realm:`。 | Space metadata 的 home Realm。 |
| `default_realm_ref` | no | `id:realm` | MUST 指向 `cx:realm:`。 | 子资源默认 Realm；省略时继承。 |
| `parent_ref` | no | `id:space` | MAY 指向任意 Space；跨 Realm parent 仅表示导航，不级联权限。 | 结构层级父。 |
| `kind` | yes | `string` | v1 标准 kind 包括 `space`、`project`、`folder`、`board`、`list`；profile 可注册新 kind。 | Space 类型。 |
| `title` | yes | `string` | 1..256 chars。 | 显示名。 |
| `summary` | no | `string` | <= 2048 chars。 | 简短说明。 |
| `rank` | no | `string` | 见 `encoding.md` §9。 | 在 parent 内的位置。 |
| `schema_refs` | no | `array<string>` | 可选 schema/profile 引用。 | 约束本 Space 容纳的资源类型 / fields。 |
| `fields` | no | `object` | kind-specific 字段。 | 扩展字段。 |
| `labels` | no | `array<string>` |  | 用户/系统标签。 |
| `avatar_blob_ref` | no | `id:blob` |  | Space 图标。 |
| `state` | no | `enum(active, archived, tombstoned)` | 默认 `active`。 | Space 生命周期状态。 |
| `state_changed_at` | no | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

### 3.3 行为规则

- **授权**：任何对 Space 的写入（`cx.space.create` / `cx.space.update` / `cx.space.archive` / `cx.space.restore` / `cx.space.tombstone` / `cx.space.parent`）都在 `realm_id` 指向的 home Realm 内授权。
- **同步与联邦**：Space metadata 跟随 home Realm 同步。跨 Realm parent 只是可验证引用，不把 child metadata 合并到 source Realm 的 event frontier。
- **加密**：Space 没有自己的 MLS group。Space metadata 是否 E2EE 取决于 home Realm 的 `encryption_profile` 与 metadata profile。
- **导航**：Space hierarchy 是产品结构树 / DAG。遍历每个 Space 节点时 MUST 独立校验该节点 home Realm 的可见性。
- **默认资源边界**：创建 Flow / Morph / View / Blob 引用等资源时，客户端 MUST 显式写入 `realm_id`，并 MAY 从目标 Space 的 effective `default_realm_ref` 推导初值。
- **强保密升级**：若 Space subtree 或单个 Flow 需要不同读隔离，创建新的 Realm 并把对应 Space 的 `default_realm_ref` 或资源的 `realm_id` 指向该 Realm；不要在同一 Realm 内伪造 per-Flow E2EE 等级。

### 3.4 Lifecycle 与 Cascade 规则

Space lifecycle 只影响结构容器，不影响 Realm membership、E2EE group 或 history visibility。

- `cx.space.archive`：把 Space 设为 `archived`，默认 UI 隐藏；不自动 archive child Space 或内部 Flow。
- `cx.space.restore`：仅允许 `archived -> active`；不级联 restore。
- `cx.space.tombstone`：不可逆；在存在 live child Space 或 live `contains` placement 时 MUST `failed_precondition`。

错误码沿用旧 Place lifecycle 语义，但新实现 SHOULD 使用 `space_not_active`、`space_not_archived`、`space_has_live_dependents`、`space_already_terminal`。兼容层 MAY 把旧 `place_*` reason code 映射到新名称。

### 3.5 `cx.space.parent` cas-register basis

`cx.space.parent` 写入 cell：

```text
cell_id := cx:cell:cx.component.space.parent.v1:<space_id>
lattice := cas-register
bottom  := reject
value   := id:space | null
```

规则：

- 首次 set 使用 `head_eq null`。
- reparent 使用 `head_eq <old_parent_space_id>`。
- 并发 reparent 返回 `⊥`，后续 Move fail closed，必须走 conflict recovery。
- `parent_ref == this_space_id` MUST `schema_violation`。
- parent Space MAY 位于不同 Realm；这只影响导航，不传播 membership、capability、history、E2EE key 或 retention policy。

### 3.6 Flow 位置

Flow 在 board/list 类 Space 中的位置仍由 cas-register cell 维护：

```text
cell_id     := cx:cell:cx.component.flow.position.v1:<board_space_id>:<flow_id>
lattice     := cas-register
bottom      := reject
value shape := { "list_space_id": id:space, "rank": string } | null
```

`cx.flow.move` payload 字段：

- `flow_id`
- `board_space_id`
- `target_space_id`
- `rank`
- `expected_position`

默认规则：workflow placement MUST resolve to the same effective Realm as the Flow unless a profile explicitly declares a cross-Realm reference relation. 跨 Realm 展示可以通过 Relation / View 聚合完成，但不得把目标 Realm 的读权隐式带入源 Realm。

### 3.7 示例

Project Space：

```json
{
  "id": "cx:space:019640b6-8000-7000-8000-000000000000",
  "schema": "cx.schema.space.v1",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "default_realm_ref": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "kind": "project",
  "title": "Website Redesign",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Confidential sibling Space：

```json
{
  "id": "cx:space:019640c0-8000-7000-8000-000000000000",
  "schema": "cx.schema.space.v1",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "default_realm_ref": "cx:realm:019641aa-0000-7000-8000-000000000000",
  "parent_ref": "cx:space:019640a0-8000-7000-8000-000000000000",
  "kind": "project",
  "title": "Pricing Strategy",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 4. Group 与 Capability 的位置

Group 不是资源容器，也不是安全边界。Group 是 principal / actor 的集合，可作为 capability grant subject、join policy 条件或组织角色投影。

规范性区分：

- Realm membership 决定能否接收 Realm event、参与 Realm MLS group、获得 Realm 历史资格。
- Capability 决定在 Realm 内能否执行动作，例如发消息、改 Flow、移动 Flow、管理 Space、邀请成员。
- Group 只是授权主体集合；把 Group 授予 capability 不等于把 Group 加入 Realm。若 Group 被授予 Realm membership，必须物化为每个成员的 Realm membership / MLS add 路径。

同一 Realm 中已经具备 MLS key 的成员，不能仅靠撤销 capability 来实现强读隔离。强读隔离必须切 Realm。

## 5. 通用对象 ID 规则

完整 ID 列表与 ID kind registry 见 [common-fields.md](./common-fields.md) §6。Realm / Space 相关：

- `cx:realm:<uuid>`
- `cx:space:<uuid>`

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Space hierarchy：[`space-hierarchy.md`](./space-hierarchy.md)。
- Realm links：[`realm-links.md`](./realm-links.md)。
- Flow / Message / track 语义：[flow-and-message.md](./flow-and-message.md)。
- Relation 基数与跨 Realm 规则：[relation.md](./relation.md)。
- Move / Anchor / Lattice：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- `cx.flow.move` / cas-register sync 编译：[`../sync/operations-sync.md`](../sync/operations-sync.md)。
- Realm / Space schema：`artifacts/schemas/realm.schema.json`、`artifacts/schemas/space.schema.json`。
