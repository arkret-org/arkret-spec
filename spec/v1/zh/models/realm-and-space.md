---
title: Realm & Space
---

## 1. 目标

本文定义 Contrix 协作图中的两个一等对象：

- **Realm**（`cx:realm:`）：security / sync / auth / E2EE / federation 的硬边界。
- **Space**（`cx:space:`）：用户可理解的结构容器与导航节点，可表达 organization 下的 workspace、project、folder、board、list、section、calendar bucket 等形态；Space 自身不是安全边界。

两类对象的边界职责严格分离：

- `Realm` 承担 security / sync / auth / E2EE / federation 边界；**不**承担产品导航树职责，也不应被建模为 parent/child hierarchy。
- `Space` 承担层级、排序、分类、项目组织和工作流容器职责；自身不是安全边界。
- 强保密差异通过切分 Realm 表达；同一 Realm 内的 capability / Group 只承诺操作隔离，不承诺对已入组成员的强读隔离。

历史 / pre-inversion 名词与当前名词的对应（仅供迁移参考，不进入 normative 描述）见 `CHANGELOG.md` 与 [`registry/renames.json`](../../artifacts/registry/renames.json) / [`registry/forbidden-model-terms.json`](../../artifacts/registry/forbidden-model-terms.json)。

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

> Materialized Realm 上以 **reducer 派生** 标注的字段（`policy_ref` / `default_discoverability` / `default_join_rule` / `history_visibility` / `federation_policy` 等）只是当前态快照。写入路径必须使用对应 per-facet state event（`cx.realm.policy` / `cx.realm.join_rule` / `cx.realm.history_visibility` / `cx.realm.discovery` / `cx.realm.policy_components` / ...），不得直接 PATCH Realm 对象更新这些字段。`trust_domain` 与 `encryption_profile` 在 create event 时锁定，后续不可变。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:realm` | 以 `cx:realm:` 开头。 | Realm ID。 |
| `schema` | yes | `cx.schema.realm.v1` | 固定。 | 对象 schema。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称；产品 UI MAY 隐藏或弱化它。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `security_class` | no | `enum(standard, high_assurance)` | 默认 `standard`。`high_assurance` MUST 满足 `federation_policy ∈ {closed, restricted, quarantine}`。 | 安全等级标签。 |
| `created_by_principal` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `trust_domain` | yes | `id:trust_domain` | create-locked；必须匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context。 | 跨 deployment replay boundary。 |
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

```json schema=schemas/realm.schema.json
{
  "id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "schema": "cx.schema.realm.v1",
  "title": "Launch Plan Confidential Realm",
  "created_by_principal": "did:web:acme.example",
  "trust_domain": "cx:trust_domain:did.webvh.acme.example",
  "schema_refs": ["cx.schema.realm.v1"],
  "default_discoverability": "invite_only",
  "default_join_rule": "invite",
  "history_visibility": "joined",
  "encryption_profile": "mls_rfc9420",
  "anchor_profile": "single_did",
  "anchorer": {
    "type": "single_did",
    "did": "did:web:anchorer.acme.example",
    "recovery_members": ["did:web:recovery-anchorer.example"],
    "controller_organization": "did:web:acme.example",
    "recovery_controller_organizations": ["did:web:recovery-org.example"]
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 2.5 Realm 终态 (`cx.realm.tombstone` / `cx.realm.destroy`)

Realm 有两个终态 event，语义不同：

| Event | 语义 | 是否可恢复 | successor |
| --- | --- | --- | --- |
| `cx.realm.tombstone` | "本 Realm 不再活跃" — 转移到 successor Realm（产品改版、组织重组等）。 | ❌ 但 successor 接续历史可达 | 必填 `successor_realm_id` |
| `cx.realm.destroy` | "本 Realm 永久退役" — 终极去活。无 successor，等同于"该 Realm 在该 deployment 内永久关闭"。 | ❌ | MUST NOT 设 successor |

`cx.realm.tombstone` 写入 `cx.component.realm.tombstone.v1`，`cx.realm.destroy` 写入 `cx.component.realm.destroy.v1`；二者均为 cas-register（bottom=reject），各自不可重复写入。capability：`cx.realm.lifecycle.tombstone` / `cx.realm.lifecycle.destroy`（high risk，capabilities.md §10）。

### 2.6 `cx.realm.create` Reducer Bootstrap（normative）

`cx.realm.create` 是 Realm 生命周期的 genesis event，它同时承担"建 Realm metadata"和"为 `created_by_principal` 引导首份成员资格"两项职责。reducer MUST 在 commit 该 event 时原子完成下述写入，且 MUST 在评估同一 submit 批次中由同一 actor 发起的任何后续 event 之前完成：

1. **物化 Realm metadata**：把 `payload.object` 写入 reducer 视图（schema 校验、`encryption_profile` / `security_class` / `anchor_profile` / `hash_profile` 等 create-locked 字段固化）。
2. **写入 `cx.component.member.state.v1` cell**（`subject=created_by_principal`，state=`join`，hlc 取自 create event）。这 **不要求** 发起者额外提交一条 `cx.member.state{join}` event，event 本身的 `created_by_principal == actor_id` 已经是 spec 规定的成员资格凭证（[`common-fields.md` §3](common-fields.md)、[`event-and-patch.md` §2.5](event-and-patch.md#25-create-类-event-的跨字段语义校验)）。
3. **写入 `cx.component.realm.create.v1` cell**（cas-register，bottom=reject，duplicate create 拒绝为 `realm_already_exists`）。

Authz 含义：

- 任何 `cx.realm.create` 之后到达的 facet event（`cx.realm.join_rule` / `cx.realm.history_visibility` / `cx.realm.discovery` / `cx.realm.policy_components` / `cx.realm.plaintext_visible_services` / ...）由 `created_by_principal` 提交时，reducer MUST 把 actor 视为已建成员，不得以"actor 不是 Realm 成员"为由 fail closed。
- `cx.realm.policy_components` payload MUST 携带单调递增的 `policy_revision`。初始 revision 为 `1`；后续更新必须满足 `new.policy_revision == previous.policy_revision + 1`，否则 reducer MUST `failed_precondition`，reason=`policy_revision_rollback` 或 `policy_revision_gap`。任何用于缓存、Policy Server decision、MLS governance binding 或 identity_link 的 `policy_frontier_hash` MUST 覆盖 `policy_revision`，不得只 hash policy 字段值集合。
- 同一 submit 批次内的事件 reducer MUST 按 wire 顺序处理；create event 必须排在前面（client 不得把 facet event 排在 create 前面，否则 reducer MUST 返回 `out_of_order_bootstrap`）。
- 重新提交同一 Realm id 的 `cx.realm.create`（无论 `created_by_principal` 是否相同）MUST `realm_already_exists` 拒绝；该规则与 create-locked 字段保护一致。

Server 端实现合规要点：

- 若 server 内部维护"显式成员索引"（如 in-memory `members` set）用于快速 authz 判断，MUST 在 `cx.realm.create` 的 commit 路径同步更新此索引，且必须在向 actor 返回 `cx.events.submit` 200 之前完成 — 否则后续 facet event 在同批次内会以 `capability_denied` 错误失败，把 spec-合规客户端逼到旁路。
- 不允许通过 spec 之外的 REST 端点（如 `POST /api/v1/spaces` 之类的私造 lifecycle 命令面）来兜底 bootstrap。此类端点违反 [`sync/service-http-binding.md` §2.1](../sync/service-http-binding.md#21-rest-api-命名空间组织) 的"实现不得用未声明路径绕过 canonical operation"规则，且会让事件流上的 read-only consumer 看不到完整的 source-of-truth 事件。

#### 2.5.1 `cx.realm.destroy` 终态规则（normative）

`cx.realm.destroy` accepted 进入 frontier 之后：

1. **拒绝后续普通写入**：reducer MUST reject 所有非 `cx.audit.*` / 非 `cx.audit.erasure_receipt` event；后续 `cx.events.submit` 返回 `realm_terminal_state`（错误码沿用 `cx.realm.lifecycle` 域）。
2. **Snapshot / Backfill / GC**：
   - Snapshot service MAY 发布最后一份 final snapshot（`cx.snapshot.*` event）；之后 snapshot 不再更新。
   - Backfill MAY 继续提供历史 event 给已授权 reader，受 history visibility policy 控制；新读权 MUST NOT 再被授予。
   - GC：blob bytes、projection 缓存、to-device 队列、push route 按部署 retention policy 物理删除。canonical event log 仍按 retention/legal hold 保留。
3. **Successor / Tombstone 区分**：`cx.realm.destroy` MUST NOT 携带 `successor_realm_id`；如果产品需要迁移到新 Realm，使用 `cx.realm.tombstone` 而不是 destroy。
4. **Erasure Receipt 与 Legal Hold**：destroy 不自动触发 erasure。若部署进入 erasure 阶段，发布 `cx.audit.erasure_receipt`（schema `cx.schema.erasure_receipt.v1`），可能 `outcome=blocked_by_legal_hold`。Legal hold 优先于 destroy 的 GC 路径。
5. **Federation Fanout**：destroy event MUST 沿 federation 推送到所有曾持有该 Realm 状态的 peer Principal Server；peer 收到后 MUST 在 30 天内本地标记 `realm_terminal_state` 并停止接受该 Realm 的新 `cx.events.submit`（包括 backfill 写入）。
6. **Child Space / Flow cascade**：destroy accepted 后，home Realm 内所有 non-terminal Space、Flow placement 与 structural `contains` projection MUST 不再作为 live navigation surface 暴露。实现 MUST 在同一事务或后续 bounded cleanup job 中把这些对象标记为 `realm_destroyed_orphan`（只读 locked projection）或自动 tombstone/archive；不得继续允许 `cx.flow.move`、`cx.space.parent`、`cx.space.update` 等普通写入复活它们。跨 Realm `parent_ref` 指向已 destroyed Realm 的 Space 时，引用方 MUST 在发现 destroy frontier 后将该 edge 降级为 locked/lazy link，并在 policy 窗口内 reparent、archive 或 tombstone；不得传播 destroyed Realm 的 membership、capability、history 或 E2EE key material。
7. **Discussion Realm edge cascade**：`Flow.discussion_realm_ref` 是跨 Realm 可见性边，destroy 必须双向 fail closed。若 `discussion_realm_ref` 指向的 linked Realm 被 destroy，源 Flow 的 discussion track projection MUST 标记为 `realm_destroyed_orphan` / locked，不得继续接受 `cx.message.*` 写入该 discussion，也不得把 source Realm membership 映射成 linked Realm 访问。若 source Realm 被 destroy 而 linked discussion Realm 仍 live，linked Realm 中既有 discussion history MAY 按其自身 policy 被授权 reader 回放，但 MUST 与已 destroyed source Flow 解耦为 locked historical context；新的 discussion 写入、watch 派发和 reverse navigation MUST 停止，除非后续显式 reparent/migration event 在 linked Realm 内被授权接受。

#### 2.5.2 跨 Principal Server Erasure Receipt Fanout（normative）

当部署对一个 Realm（或一个 principal）执行 hard erasure 时，**issuing** Principal Server MUST：

- 发布一条 `cx.audit.erasure_receipt`（durable_event）；
- 在 federation push 中带上该 receipt 给所有曾接收过该 Realm 内容的 peer Principal Server；
- 在 server describe `erasure_receipts_endpoint` 暴露 receipt 列表，便于 verifier 查询。

**receiving** peer 处理 receipt 时 MUST：

- 验证 receipt 签名链与 schema；
- 如果 peer 本地存有该 erasure scope 内的 blob / projection / cache，按 receipt `scope.storage_boundary` 走本地删除流程，并发布自己的 `cx.audit.erasure_receipt` 反馈实际结果；
- 失败（legal hold、retention 冲突、blob 已被备份到不可达存储）MUST 在 peer 自己的 receipt `outcome` 字段写 `partially_completed` 或 `blocked_by_legal_hold`，不得假装成功；
- 任何 peer 未在 `erasure_propagation_window_ms`（默认 7 天）内回执，issuing server 在 `cx.audit.erasure_receipt.fanout_status` 上标 `incomplete`，并把 incomplete 状态暴露给 audit/UI；不得静默吞没。

**Hash chain 保护**：hard erasure 仍保留 event graph verification stub（`retained_stub_hash` 字段），允许后续 verifier 校验"该 event 曾合法存在但内容已擦除"，不破坏 hash chain。`retained_stub_hash` 的输入是 `canonical_json(retained_stub)`；`retained_stub` 使用 `cx.schema.erasure_verification_stub.v1` 结构，至少绑定 subject、scope、receipt_id、completed_at，并在适用时包含 event digest / proof payload_hash、anchor inclusion、redaction authorization ref 与 legal-hold ref。Stub MUST NOT 保留已擦除 plaintext 或未加盐低熵 plaintext digest；若 receipt 不内联 `retained_stub`，签发服务必须在 erasure receipt endpoint 暴露同一 canonical stub。projection / UI MUST 显示 `[erased]` 占位而不是模糊化。

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

错误码 MUST 使用 `space_not_active`、`space_not_archived`、`space_has_live_dependents`、`space_already_terminal`。pre-inversion 形态已在 [`removed-event-kinds.json`](../../artifacts/registry/removed-event-kinds.json) 中标 hard_reject，不存在兼容映射通道；下游迁移工具按 drift artifact 一次性翻译为新名称后再回放。

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

```json schema=schemas/space.schema.json
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

```json schema=schemas/space.schema.json
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
