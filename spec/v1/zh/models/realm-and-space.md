---
title: Realm & Space
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Cokret 协作图中的两个一等对象：

- **Realm**（`ck:realm:`）：security / sync / auth / E2EE / federation 的硬边界。
- **Space**（`ck:space:`）：用户可理解的结构容器与导航节点，可表达 organization 下的 workspace、project、folder、board、list、section、calendar bucket 等形态；Space 自身不是安全边界。

两类对象的边界职责严格分离：

- `Realm` 承担 security / sync / auth / E2EE / federation 边界；**不**承担产品导航树职责，也不应被建模为 parent/child hierarchy。
- `Space` 承担层级、排序、分类、项目组织和工作流容器职责；自身不是安全边界。
- 强保密差异通过切分 Realm 表达；同一 Realm 内的 capability / Group 只承诺操作隔离，不承诺对已入组成员的强读隔离。

Realm 之间只允许显式 link graph（governance / discoverability / import-export / confidential-extension 等关系），详见 [`realm-links.md`](./realm-links.md)。Space 层级与跨 Realm 导航见 [`space-hierarchy.md`](./space-hierarchy.md)。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Realm

### 2.1 概念

每个 `ck:realm:` ID 都是一个 security / sync / auth / E2EE 边界。以下语义全部以 Realm 为根解析：

- membership
- capability grant / revoke 的授权上下文
- history visibility
- E2EE / MLS group governance
- federation policy
- retention / legal hold
- plaintext-visible service
- Policy Server
- event frontier / Seal pipeline

`Realm` 的语义接近“保护域”或“治理域”，不是“项目文件夹”。一个组织通常会拥有多个 Realm：公开项目、普通内部项目、机密项目、HR 项目、法务项目可以位于同一 Organization / Space tree 下，但落到不同 Realm。

`security_class=high_assurance` 是 Realm 的可选标签，进一步收紧 federation policy 与默认审计 / E2EE 选项。

### 2.2 Realm 与 MLS group

Realm 与 MLS group 不是同义词：

- 非 E2EE Realm 可以没有 MLS group。
- E2EE Realm 通常拥有一个 primary MLS group。
- Realm 还包含 policy、membership、history、sync frontier、federation、retention 和 capability 等语义；MLS group 只承载加密成员、epoch 和密钥演进。
- 实现把 Realm 内的子事件 / 子消息边界形式化为一等对象 [Circle](./circle.md)（`ck:circle:`）：独立 membership、独立 history visibility、独立投递 / 查询 / projection 裁剪，且 `Circle.members ⊆ Realm.members`；当父 Realm 或 policy 要求 E2EE 时，Circle 还必须拥有独立 MLS group。federation identity / Policy Server / capability registry 仍在父 Realm。

规范性规则：

- `encryption_profile` 是 Realm 的 create-locked 基线。
- 同一 Realm 内不允许把普通 Flow 任意混合成"有的 E2EE、有的非 E2EE"的保密等级拼盘；加密覆盖范围由 Realm `content_encryption_floor` 与 `metadata_encryption_floor` 声明（二者均为 Realm 对象顶层的 policy 字段，权威定义见 §2.3 字段表），Circle 不得放宽父 Realm floor（详见 [`circle.md` §7](./circle.md)）。
- Realm policy component `agent_participation` 声明 native personal agent 在该 Realm 内被允许的参与上限（ceiling），结构为 `{ native_agent: { reply, accept_third_party_mention, act_on_behalf } }`，由持有 `ck.realm.admin` 的 principal 通过 `ck.realm.policy_components` 写入。它与 deployment、Circle、Flow 同名 ceiling 构成 `deployment ⊇ Realm ⊇ Circle ⊇ Flow` 的单调收紧链：内层每一位为真 MUST 蕴含外层对应位为真，reducer 拒绝放宽（`failed_precondition`，`reason="agent_participation_ceiling_widen"`），与 `content_encryption_floor` 的 tighten-only ratchet 同框架。未声明时继承父级 ceiling；deployment 顶层默认全 `false`（与 `ck.profile.sovereign_deployment.v1` 的 deny-default agent 一致）。controller 的逐 scope selection 受 effective ceiling 约束，effective = ceiling ∩ selection。详见 [`../authz/capabilities.md` §5.4](../authz/capabilities.md)。native agent 与 Applet / Ghost Actor 的参与策略 MUST 分别声明，不得合并为单一开关。
- 若某个 Flow / artifact 需要 Realm 内的子事件 / 子消息边界（子集成员、独立 history、投递 / 查询裁剪，必要时独立 MLS group），创建一个 [Circle](./circle.md) 并把对象的 `scope_circle_id` 指向该 Circle。仅当跨 federation/policy/capability registry 边界时才升级到另一个独立 Realm，并通过 `ck.realm.link` 显式引用连接。
- `history_visibility` 的五个值只定义历史读取资格；是否能发现 Realm、能否加入、是否能解密旧 E2EE epoch、以及服务是否可接收明文，分别由 discoverability、join rule、history sharing policy / key share、`plaintext_visible_services` 决定。完整语义见 [`../governance/history-visibility.md`](../governance/history-visibility.md)。

### 2.3 Schema id 与字段

Schema id: `ck.schema.realm.v1`

> Materialized Realm 上以 **reducer 派生** 标注的字段（`policy_id` / `default_discoverability` / `default_join_rule` / `history_visibility` / `federation_policy` 等）只是当前态快照。写入路径必须使用对应 per-facet state event（`ck.realm.policy` / `ck.realm.join_rule` / `ck.realm.history_visibility` / `ck.realm.discovery` / `ck.realm.policy_components` / ...），不得直接 PATCH Realm 对象更新这些字段。`trust_domain` 与 `encryption_profile` 在 create event 时锁定，后续不可变。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:realm` | 以 `ck:realm:` 开头。 | Realm ID。 |
| `schema` | yes | `ck.schema.realm.v1` | 固定。 | 对象 schema。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称；产品 UI MAY 隐藏或弱化它。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `security_class` | no | `enum(standard, high_assurance)` | 默认 `standard`。`high_assurance` MUST 满足 `federation_policy ∈ {closed, restricted, quarantine}`。 | 安全等级标签。 |
| `trust_domain` | yes | `id:trust_domain` | create-locked；必须匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context。 | 跨 deployment replay boundary。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 `ck.schema.realm.v1`。 | 启用 schema / profile。 |
| `relation_profiles` | no | `array<RelationProfile>` | 同一 `(relation_kind, from_type, to_type, scope)` 至多一个 active profile。 | Relation 基数、去重和冲突规则。 |
| `policy_id` | no | `id:policy` | reducer 派生。 | 当前 Realm access policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | reducer 派生。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | reducer 派生。 | 默认加入规则。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | reducer 派生。 | 历史可见性。 |
| `preview_policy_id` | no | `id:policy` | reducer 派生或投影字段；canonical 写入路径为 `ck.realm.preview_policy`。 | 加入前 / token-scoped preview 的 policy 引用或摘要。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420, external)` | create-locked 的**能力轴**：只声明加密**机制**(有没有 MLS group)，不声明哪些 Cokret 字段进入密文，也不是"内容是否加密"的开关。`none` 是 bridge / 公开广播等"结构上永不 E2EE"scope 的诚实 opt-out；将来可能加密的协作 Realm SHOULD 以 `mls_rfc9420` + `content_encryption_floor=allow_plaintext` 创建，以便后期原地启用加密。完整语义见 [`circle.md` §7](./circle.md)。 | 加密机制声明。 |
| `content_encryption_floor` | no | `enum(allow_plaintext, e2ee_required)` | reducer 派生（Realm policy 字段，经 Realm policy facet event 写入，非直接 PATCH）。这是 Realm 真正的"内容加密开关"：`e2ee_required` 时 Flow / Message / Morph / Blob content 的 `effective_scope` MUST 为 MLS-backed，plaintext content reducer MUST `failed_precondition`（reason=`content_encryption_floor_violation`）。缺省 `allow_plaintext`。**单向 ratchet**：一旦 effective 值达到 `e2ee_required`，后续降回 `allow_plaintext` 的写入 MUST `failed_precondition`（reason=`content_encryption_floor_downgrade`）。完整语义见 [`circle.md` §7](./circle.md)。 | Realm 级 content 加密下限。 |
| `metadata_encryption_floor` | no | `enum(allow_plaintext, e2ee_required)` | reducer 派生（Realm policy 字段，经 Realm policy facet event 写入，非直接 PATCH），与 `content_encryption_floor` 对称。比较序 `allow_plaintext < e2ee_required`；effective 值取父 Realm / Circle / Space `child_scope_policy` / 对象 profile 的最大值，低于 effective 的写入 MUST `failed_precondition`（reason=`metadata_encryption_floor_violation`），MUST NOT 被 Circle / Space / 对象 profile 放宽。**单向 ratchet**：一旦 effective 值达到 `e2ee_required`，后续降回 `allow_plaintext` 的写入 MUST `failed_precondition`（reason=`metadata_encryption_floor_downgrade`）。缺省：`mls_rfc9420` 或 `content_encryption_floor=e2ee_required` 的 Realm 为 `e2ee_required`，否则 `allow_plaintext`。完整语义见 [`circle.md` §7](./circle.md)。 | Realm 级 metadata 加密下限。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | reducer 派生。 | 联邦策略。 |
| `sync_endpoints` | no | `array<ServiceBinding>` | Realm-level shared notary / Sync Service / mirror / federation 服务绑定；不是成员级 delivery binding。详见 [`../sync/federation.md`](../sync/federation.md)。 | Realm 委托同步与联邦入口。 |
| `notary_profile` | yes | `enum(single_did, threshold, open_set, mixed)` | create-locked。 | Seal finality profile。 |
| `digest_algorithm` | no | `enum(digest-suite-registry active ids；v1: sha256, blake3)` | create-locked，默认 `sha256`。 | Digest suite（canonicalization × hash 注册元组，见 [`encoding.md` §3.1–§3.3](../conformance/encoding.md)）：裸 id = canonical JSON 归一化，点分 id（如 reserved 的 `cbor.sha256`）= 备用归一化编码 suite。Realm 内单一 suite 排他；切换走控制面 suite transition Seal（[`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)）。 |
| `notary` | yes | `object` | Genesis notary control cell 初值；其 `type` MUST 与 `notary_profile` 同源并满足对应 profile 的条件必填子字段。其 discriminator 子字段为 `type`（取值与 `notary_profile` 枚举同源：`single_did` / `threshold` / `open_set` / `mixed`）。**这是协议内 discriminator 默认用 `kind` 约定的已登记例外**（schema `realm.schema.json` 锁定 `notary.type`），见 [`common-fields.md` §2](./common-fields.md)。 | 当前 Seal 签发规则。 |
| `revocation_freshness_window_ms` | no | `integer` | 默认 24h；用于 DataEvent `seal_ref` 和 Control Move `seal_basis` 的撤销新鲜度判定。高风险写入 MAY 按 [`capabilities.md` §18.2](../authz/capabilities.md) 要求更短窗口。 | CBA 授权基准 freshness 上限。 |
| `max_delegation_lifetime_ms` | no | `integer` | 默认 24h；用于 [`capabilities.md` §10.1](../authz/capabilities.md) 无限期 parent grant 首次转授时冻结 `delegation_expiry_seal`。effective 值取 Realm 字段与任何 grant / policy / deployment / profile 更短窗口的最小值。 | 委托防滚动续期窗口。 |
| `bottom_escalation_after_ms` | no | `integer` | cell `⊥` 持续超过该窗口后，reducer / Projection SHOULD 标记 `escalated_at` 并触发带外告警；详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。 | bottom 诊断升级窗口。 |
| `cell_lattices` | no | `array<CellLattice>` | `CellLattice` 结构（cell family / lattice / bottom 等）定义见 [`../authz/event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md)。 | Realm-specific 扩展 cell family。 |
| `co_write_policy` | no | `array<array<component>>` | `component`（cell component 标识）语义见 [`../authz/event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md)。 | Control Move 原子写约束。 |
| `retention_policy_id` | no | `id:policy` |  | 保留策略。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_by` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 2.4 最小示例

```json schema=schemas/realm.schema.json
{
  "id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "schema": "ck.schema.realm.v1",
  "title": "Launch Plan Confidential Realm",
  "trust_domain": "ck:trust_domain:did.webvh.acme.example",
  "schema_refs": ["ck.schema.realm.v1"],
  "default_discoverability": "invite_only",
  "default_join_rule": "invite",
  "history_visibility": "joined",
  "encryption_profile": "mls_rfc9420",
  "notary_profile": "single_did",
  "notary": {
    "type": "single_did",
    "did": "did:web:notary.acme.example",
    "recovery_members": ["did:web:recovery-notary.example"],
    "controller_organization": "did:web:acme.example",
    "recovery_controller_organizations": ["did:web:recovery-org.example"]
  },
  "created_by": "did:web:acme.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 2.5 `ck.realm.create` Reducer Bootstrap（normative）

`ck.realm.create` 是 Realm 生命周期的 genesis event，它同时承担"建 Realm metadata"和"为 `created_by` 引导首份成员资格"两项职责。reducer MUST 在 commit 该 event 时原子完成下述写入，且 MUST 在评估同一 submit 批次中由同一 actor 发起的任何后续 event 之前完成：

1. **物化 Realm metadata**：把 `payload.object` 写入 reducer 视图（schema 校验、`encryption_profile` / `security_class` / `notary_profile` / `digest_algorithm` 等 create-locked 字段固化）。
2. **写入 `ck.component.member.state.v1` cell**（`subject=created_by`，state=`join`，hlc 取自 create event）。这 **不要求** 发起者额外提交一条 `ck.member.state{join}` event，event 本身的 `created_by == actor_id` 已经是 spec 规定的成员资格凭证（[`common-fields.md` §3](common-fields.md)、[`event-and-patch.md` §2.5](event-and-patch.md#25-create-类-event-的跨字段语义校验)）。
3. **写入 `ck.component.realm.create.v1` cell**（cas_register，bottom=reject，duplicate create 拒绝为 `realm_already_exists`）。

Authz 含义：

- 任何 `ck.realm.create` 之后到达的 facet event（`ck.realm.join_rule` / `ck.realm.history_visibility` / `ck.realm.discovery` / `ck.realm.policy_components` / `ck.realm.plaintext_visible_services` / ...）由 `created_by` 提交时，reducer MUST 把 actor 视为已建成员，不得以"actor 不是 Realm 成员"为由 fail closed。
- `ck.realm.policy_components` payload MUST 携带单调递增的 `policy_revision`。初始 revision 为 `1`；后续更新必须满足 `new.policy_revision == previous.policy_revision + 1`，否则 reducer MUST `failed_precondition`，reason=`policy_revision_rollback` 或 `policy_revision_gap`。任何用于缓存、Policy Server decision、MLS governance binding 或 identity_link 的 `policy_frontier_digest` MUST 覆盖 `policy_revision`，不得只 hash policy 字段值集合。
- **加密 floor 单向 ratchet（normative）**：Realm 的 effective `content_encryption_floor` 与 effective `metadata_encryption_floor` MUST 随时间单调非降。`ck.realm.policy_components` 若把 `content_encryption_floor` 从 `e2ee_required` 降回 `allow_plaintext`，reducer MUST `failed_precondition`，reason=`content_encryption_floor_downgrade`；若把 `metadata_encryption_floor` 降到更低等级（比较序 `allow_plaintext < e2ee_required`），reducer MUST `failed_precondition`，reason=`metadata_encryption_floor_downgrade`。收紧（抬高 floor）永远允许，只有降低被拒。该 ratchet 使"加密一旦开启不可撤销"成为治理层硬约束，并消除静默 downgrade 攻击面；Circle 级同一规则与 effective floor 计算见 [`circle.md` §7](./circle.md)。
- 同一 submit 批次内的事件 reducer MUST 按 wire 顺序处理；create event 必须排在前面（client 不得把 facet event 排在 create 前面，否则 reducer MUST 返回 `out_of_order_bootstrap`）。
- 重新提交同一 Realm id 的 `ck.realm.create`（无论 `created_by` 是否相同）MUST `realm_already_exists` 拒绝；该规则与 create-locked 字段保护一致。

Server 端实现合规要点：

- 若 server 内部维护"显式成员索引"（如 in-memory `members` set）用于快速 authz 判断，MUST 在 `ck.realm.create` 的 commit 路径同步更新此索引，且必须在向 actor 返回 `ck.self.events.submit` 200 之前完成 — 否则后续 facet event 在同批次内会以 `capability_denied` 错误失败，把 spec-合规客户端逼到旁路。
- 不允许通过 spec 之外的 REST 端点（如 `POST /spaces` 之类的私造 lifecycle 命令面）来兜底 bootstrap。此类端点违反 [`sync/service-http-binding.md` §2.1](../sync/service-http-binding.md#21-rest-api-命名空间组织) 的"实现不得用未声明路径绕过 canonical operation"规则，且会让事件流上的 read-only consumer 看不到完整的 source-of-truth 事件。

**Backfill / federation peer 一致性（normative）**：Backfill / federation peer consumer MUST 把 cell snapshot（`ck.component.member.state.v1`）与 event 流并联回放，不得只回放 event 流——否则会看到 `ck.realm.create` 之后由 `created_by` 提交的 facet event 但找不到对应 `ck.member.state{join}` event（spec 不要求显式 emit），产生"无成员合法写入"的误读。

### 2.6 Realm 终态 (`ck.realm.tombstone` / `ck.realm.destroy`)

Realm 有两个终态 event，语义不同：

| Event | 语义 | 是否可恢复 | successor |
| --- | --- | --- | --- |
| `ck.realm.tombstone` | "本 Realm 不再活跃" — 转移到 successor Realm（产品改版、组织重组等）。 | no，但 successor 接续历史可达 | 必填 `successor_realm_id` |
| `ck.realm.destroy` | "本 Realm 永久退役" — 终极去活。无 successor，等同于"该 Realm 在该 deployment 内永久关闭"。 | no | MUST NOT 设 successor |

`ck.realm.tombstone` 写入 `ck.component.realm.tombstone.v1`，`ck.realm.destroy` 写入 `ck.component.realm.destroy.v1`；二者均为 cas_register（bottom=reject），各自不可重复写入。capability：`ck.realm.tombstone` / `ck.realm.destroy`（action 定义见 [`../authz/capabilities.md` §5.1](../authz/capabilities.md)，high-risk 约束见 [`capabilities.md` §8](../authz/capabilities.md)）。

#### 2.6.0 Realm 可逆 lifecycle facet（`ck.realm.archive` / `ck.realm.freeze`）

除上述两个终态外，Realm 还有两个**可逆** lifecycle facet，与终态正交，且对应 [`common-fields.md` §5](./common-fields.md) 状态对齐表 Realm 行支持的 `archived`：

| Event | 语义 | lifecycle_modality | cell family |
| --- | --- | --- | --- |
| `ck.realm.archive` | 把 Realm 设为 `archived`（软隐藏，UI 默认不展示，可撤销）。 | reversible | `ck.component.realm.archive.v1` |
| `ck.realm.freeze` | 把 Realm 冻结为只读（暂停普通写入，可撤销）。 | reversible | `ck.component.realm.freeze.v1` |

二者均为 cas_register（bottom=reject）durable event，承载一个 **reversible boolean** facet：**同一个 `ck.realm.archive` 写 `true` 进入 `archived`、写 `false` 复原**，**不走独立 `ck.realm.restore` event**；`ck.realm.freeze` 同理用单一 reversible boolean facet 在 frozen / 非 frozen 之间切换。这区别于 [`common-fields.md` §5.2](./common-fields.md) 模板中 `ck.<kind>.archive` + `ck.<kind>.restore` 成对的形态——Realm 的可逆性由 facet boolean 表达，registry `lifecycle_modality=reversible` 是真源。capability：`ck.realm.archive` / `ck.realm.freeze`（action 见 [`../authz/capabilities.md`](../authz/capabilities.md)）。

被 `archived` 或 `frozen` facet 关闭普通写入的 Realm 收到非豁免普通写入时，reducer / 服务端 MUST 返回 `realm_frozen`（HTTP 403）；审计类豁免仍按 §2.6.1 的终态规则和 error-code registry 处理。

#### 2.6.1 `ck.realm.destroy` 终态规则（normative）

`ck.realm.destroy` accepted 进入 frontier 之后：

1. **拒绝后续普通写入**：reducer MUST reject 所有非 `ck.audit.*` / 非 `ck.audit.erasure_receipt` event；后续 `ck.self.events.submit` 返回 `realm_terminal_state`（错误码归类于 `realm_lifecycle` 错误域，避免与 `ck.realm.lifecycle.*` capability action 命名混用）。
2. **Snapshot / Backfill / GC**：
   - Snapshot service MAY 发布最后一份 final snapshot（`ck.snapshot.*` event）；之后 snapshot 不再更新。
   - Backfill MAY 继续提供历史 event 给已授权 reader，受 history visibility policy 控制；新读权 MUST NOT 再被授予。
   - GC：blob bytes、projection 缓存、to-device 队列、push route 按部署 retention policy 物理删除。canonical event log 仍按 retention/legal hold 保留。
3. **Successor / Tombstone 区分**：`ck.realm.destroy` MUST NOT 携带 `successor_realm_id`；如果产品需要迁移到新 Realm，使用 `ck.realm.tombstone` 而不是 destroy。
4. **Erasure Receipt 与 Legal Hold**：destroy 不自动触发 erasure。若部署进入 erasure 阶段，发布 `ck.audit.erasure_receipt`（schema `ck.schema.erasure_receipt.v1`），可能 `outcome=blocked_by_legal_hold`。Legal hold 优先于 destroy 的 GC 路径。
5. **Federation Fanout**：destroy event MUST 沿 federation 推送到所有曾持有该 Realm 状态的 peer Principal Server；peer 收到后 MUST 在 30 天内本地标记 `realm_terminal_state` 并停止接受该 Realm 的新 `ck.peer.events.submit`（包括 backfill 写入）。
6. **Child Space / Flow cascade**：destroy accepted 后，home Realm 内所有 non-terminal Space、Flow placement 与 structural `contains` projection MUST NOT 作为 live navigation surface 暴露。实现 MUST 在同一事务或后续 bounded cleanup job 中把这些对象标记为 `realm_destroyed_orphan`（只读 locked projection）或自动 tombstone/archive；不得继续允许 `ck.flow.move`、`ck.space.parent`、`ck.space.update` 等普通写入复活它们。跨 Realm `parent_space_id` 指向已 destroyed Realm 的 Space 时，引用方 MUST 在发现 destroy frontier 后将该 edge 降级为 locked/lazy link，并在 policy 窗口内 reparent、archive 或 tombstone；不得传播 destroyed Realm 的 membership、capability、history 或 E2EE key material。
7. **Circle scope cascade**：Realm 内的 [Circle](./circle.md) 在父 Realm destroy 时一并 tombstone（Circle 不持有独立 federation identity，无法独立存活）。对象 `scope_circle_id` 指向已 tombstone Circle 时，写入 MUST fail closed（`failed_precondition`, `reason_code=scope_unavailable`）；projection MAY 显示同名 `scope_unavailable` 状态标记；`scope_circle_id` 不会被自动 rewrite。详见 [`circle.md` §9.2](./circle.md) lifecycle cascade 表。

#### 2.6.2 跨 Principal Server Erasure Receipt Fanout（normative）

当部署对一个 Realm（或一个 principal）执行 hard erasure 时，**issuing** Principal Server MUST：

- 发布一条 `ck.audit.erasure_receipt`（durable_event）；
- 在 federation push 中带上该 receipt 给所有曾接收过该 Realm 内容的 peer Principal Server；
- 在 server describe `erasure_receipts_endpoint` 暴露 receipt 列表，便于 verifier 查询。

**receiving** peer 处理 receipt 时 MUST：

- 验证 receipt 签名链与 schema；
- 如果 peer 本地存有该 erasure scope 内的 blob / projection / cache，按 receipt `scope.storage_boundary` 走本地删除流程，并发布自己的 `ck.audit.erasure_receipt` 反馈实际结果；
- 失败（legal hold、retention 冲突、blob 已被备份到不可达存储）MUST 在 peer 自己的 receipt `outcome` 字段写 `partially_completed` 或 `blocked_by_legal_hold`，不得假装成功；
- 任何 peer 未在 `erasure_propagation_window_ms`（默认 7 天）内回执，issuing server MUST 在该 erasure receipt 的 `fanout_status` 字段标 `incomplete`（并在 `peer_receipts[]` 对应 peer 条目记 `status=timed_out`），把 incomplete 状态暴露给 audit/UI；不得静默吞没。`fanout_status` 与 per-peer `peer_receipts` 子结构定义见 `ck.schema.erasure_receipt.v1`（schema `artifacts/schemas/erasure-receipt.schema.json`）。

**Hash chain 保护**：hard erasure 仍保留 event graph verification stub（`retained_stub_digest` 字段），允许后续 verifier 校验"该 event 曾合法存在但内容已擦除"，不破坏 hash chain。`retained_stub_digest` 的输入是 `canonical_json(retained_stub)`；`retained_stub` 使用 `ck.schema.erasure_verification_stub.v1` 结构，至少绑定 subject、scope、receipt_id、completed_at，并在适用时包含 event digest / proof `event_digest`、seal inclusion、redaction authorization ref 与 legal-hold ref。Stub MUST NOT 保留已擦除 plaintext 或未加盐低熵 plaintext digest；若 receipt 不内联 `retained_stub`，签发服务必须在 erasure receipt endpoint 暴露同一 canonical stub。projection / UI MUST 显示 `[erased]` 占位而不是模糊化。

### 2.7 Realm Membership FSM（normative）

`ck.member.state` 写入 `ck.component.member.state.v1:<actor_id>`，lattice 为 `fsm`、`bottom=reject`。Realm membership FSM 的 `initial_state` 为 `leave`；wire 枚举仅使用 `invite / join / knock / leave / ban`，不存在单独的 `none` wire 值。`ck.realm.create` bootstrap 例外见 §2.5：它直接把 `created_by` 的 member cell 初始化为 `join`。

| from | to | writer / capability | 语义 |
| --- | --- | --- | --- |
| `leave` | `invite` | `ck.member.invite` 或 `ck.realm.admin` | 发出邀请或重新邀请。 |
| `leave` | `knock` | target actor，且当前 join rule / Join Policy 允许 knock | 申请加入；申请正文不得放入 member state Move。 |
| `leave` | `join` | target actor 通过 public / restricted gate，或 `ck.realm.admin` | 直接加入或管理员加入。 |
| `invite` | `join` | target actor，或 `ck.realm.admin` | 接受邀请或管理员完成加入。 |
| `invite` | `leave` | target actor，inviter，或 `ck.realm.admin` | 拒绝 / 撤销邀请。 |
| `knock` | `invite` | reviewer / `ck.realm.join.review` 或 `ck.realm.admin` | 批准申请并转为邀请。 |
| `knock` | `join` | reviewer / `ck.realm.join.review` 或 `ck.realm.admin` | 直接批准加入。 |
| `knock` | `leave` | target actor，reviewer，或 `ck.realm.admin` | 撤回、拒绝或 TTL 到期。 |
| `join` | `join` | target actor 或 rebind-authorized service，且只更新 delivery binding / membership metadata | 成员保持加入状态的投递绑定迁移；不得借此改变 join gate 结果。 |
| `join` | `leave` | target actor 或 `ck.realm.admin` | 主动离开或管理员移除。 |
| `leave` / `invite` / `knock` / `join` | `ban` | `ck.realm.admin` | 封禁；同时触发投递、MLS remove 与 Circle cascade。 |
| `ban` | `leave` | `ck.realm.admin` | 解封为非成员。 |
| `ban` | `invite` | `ck.realm.admin` | 解封并重新邀请。 |

未列出的 transition MUST `failed_precondition`，reason=`invalid_membership_transition` 或更具体的 join / delivery-binding reason。`join -> invite`、`ban -> join`、`invite -> knock`、`leave -> leave` 等均非法；需要重试时 producer 必须基于当前 state 重新提交合法 transition。父 Realm `join -> leave/ban` 的 cascade 对 Circle membership 的影响见 [`circle.md` §9.1](./circle.md)。

### 2.8 Realm 角色分类（normative）

schema 层只有一个 `ck.schema.realm.v1`；按 **用途** 把 Realm 分成两大类，Collaboration 再按 **成员是否跨信任域** 分两类。所有 Realm 共享同一组生命周期 event（`ck.realm.create` / `ck.realm.tombstone` / `ck.realm.destroy`）与同一套 reducer 规则；下面的分类影响的是 marker 字段、policy 字段默认值与允许的 event kind 集合。

```
Realm（ck.schema.realm.v1，schema 层统一）
├── Collaboration Realm        ← 多方业务协作（Flow / Message / Space / Morph / Relation）
│   ├── Internal Collaboration Realm   ← 仅本信任域成员
│   └── External Collaboration Realm   ← 含跨信任域成员
└── Principal Control Realm    ← 单 principal 身份基础设施流（device / session / KeyPackage / profile / consent / contact fact / DM binding）
```

#### 2.8.1 Principal Control Realm（PCR）

- 与 principal DID **1:1 绑定**，由 `principal_control_realm_id` 标识，由 DID method 的 inception 证据钉死（参见 [`identity/key-management.md` §4.1 与 §5.0](../identity/key-management.md)）。
- Marker 字段 MUST：
  - `fields.purpose = "principal_control"`
  - `schema_refs` 包含 `ck.profile.principal_control_realm.v1`
  - `created_by = <principal DID>`，`notary = <principal DID>`，`notary_profile = "single_did"`
  - `security_class = "high_assurance"`，`federation_policy ∈ {closed, restricted, quarantine}`
- 事件类型由 `ck.profile.principal_control_realm.v1` 的 allowlist 约束：只接受 device / session / KeyPackage / recovery / profile / consent / contact fact / direct conversation binding 等身份基础设施 event；普通 Message / Flow / Space / Morph / Relation / View / Call 协作 event MUST `principal_control_event_kind_forbidden`。
- 跨 principal 写入（另一个 principal 的 device / session 状态）MUST `unauthorized` reject。
- "私有"语义由 **用途 + event-kind allowlist** 锁定，不是 access control。PCR 在结构上允许 multi-member（该 principal 的所有设备 / agent）。

#### 2.8.2 Collaboration Realm

承载多方业务协作。除 PCR 之外的所有 Realm 都属于这一类。

- `fields.purpose` 不为 `"principal_control"`；普通 Collaboration Realm SHOULD 省略 `fields.purpose`，不得写入 schema 未注册的 `"collaboration"` marker。
- 不引用 `ck.profile.principal_control_realm.v1`。
- 按 `federation_policy` 与实际成员构成进一步分为 Internal / External 两种。

##### Internal Collaboration Realm

- `federation_policy ∈ {closed, restricted}`，且实际成员仅来自本部署 trust domain。
- 组织主网络上的普通项目 / 团队 / 文档 / 群聊 Realm 默认属于此类。
- 不需要外部组织 authority chain 或外部 principal 验证流程。

##### External Collaboration Realm

- 含至少一个跨信任域成员（external Organization DID、external principal、跨部署 service DID）。
- `federation_policy` 通常为 `restricted`（allowlist）或 `open`；`discoverability` / `join_rule` 与 `external_federation` 由 deployment policy 决定。
- 外部主体进入 MUST 经过组织 authority chain 或 verifiable credential 验证（详细规则见 [`sync/sovereign-deployment.md` §5–§6](../sync/sovereign-deployment.md)）。

启用 `ck.profile.sovereign_deployment.v1` 的部署对 External Collaboration Realm 施加额外的强制约束（allowlist federation、独立 enclave、E2EE、deny-default applet/agent 等），规则见 [`sync/sovereign-deployment.md` §4](../sync/sovereign-deployment.md)。非 sovereign 部署下 External Collaboration Realm 仍须遵守 federation_policy / E2EE / capability 等普通 Realm 规则，但不强制 sovereign profile 的全部约束。

#### 2.7.3 关系与正交轴

- "Internal / External" 的判定轴是 **是否含跨信任域成员**，不是 hosting 在哪台 server 上：一个 Realm 由组织自己的 Principal Server 托管，但邀请了外部 Organization DID 的成员——它就是 External Collaboration Realm。
- Sovereign deployment 对 External Collaboration Realm 加的那一组 policy 来自 `ck.profile.sovereign_deployment.v1`，是 **部署 profile** 决定的 policy 配置，不是另一种 Realm 类型。
- PCR 永远是 Internal 的，不存在 "External PCR"：principal DID 与其 control Realm 1:1 绑定，跨域 PCR 在结构上不存在。
- `security_class=high_assurance` 是横切标签，可叠加在 Internal / External Collaboration Realm 与 PCR 上，不属于本分类的一层节点。
- 这套分类是 **prose / glossary 层** 的角色术语，便于跨章节统一指代；底层 schema、reducer、Seal pipeline、Move 处理对三类一视同仁。

#### 2.7.4 Direct Conversation Realm（1:1 DM）

Direct Conversation Realm 是 Collaboration Realm 的受约束形态，不是新的 Realm 类型。完整生命周期见 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md)。

Direct Conversation Realm MUST：

- 使用 `encryption_profile="mls_rfc9420"`；`mls_dm` 不得作为 Realm `encryption_profile` 枚举值出现。
- 声明已注册的 direct conversation profile，并使用已注册的 direct-conversation discriminator；不得复用 `fields.purpose="direct_message"`，因为 `fields.purpose` 已用于 Principal Control Realm。
- active member count 等于 2；向 active DM Realm 加第三人 MUST 被拒绝。升级多人聊天必须创建新的普通 Realm / Flow，再用 Relation 或 Message 引用旧 DM 内容。
- `default_join_rule` 为 `closed` 或等价 fail-closed policy；第三方 invite / member_add MUST 被拒绝。
- 通过 principal-scoped `ck.direct_conversation.bound` fact 绑定 unordered participant pair、`realm_id` 与 `main_flow_id`。同一 pair 至多一个 active canonical DM Realm；并发 duplicate 必须用 deterministic tie-break 收敛。

任一参与方主动离开或被移出 DM Realm 后，该 Realm 立即失去 active canonical DM 资格。Resolver MUST NOT 为了继续同一个私聊把退出方重新加入旧 Realm；后续 `ck.self.direct_conversation.resolve(create=true)` MUST 创建新的 DM Realm、main Flow 与 binding。旧 Realm MAY 作为历史归档存在，但不得接收新的默认聊天消息。

## 3. Space

### 3.1 概念

Space 是用户和产品层可见的结构容器。它可以表达：

- organization 下的 workspace / project / folder / section
- board / list / swimlane / calendar bucket
- document outline group / page group
- 任意 profile 注册的结构节点

Space **不**拥有自己的 membership、policy、history visibility、E2EE group 或 federation policy。它通过 `realm_id` 和可选 `default_realm_id` 解析到 Realm：

- `realm_id`：该 Space 对象自身 metadata 的 home Realm。创建、更新、archive、tombstone 该 Space 的事件写入这个 Realm。
- `default_realm_id`：该 Space 下新建资源默认落入的 Realm。省略时继承最近 ancestor Space 的 `default_realm_id`，再退回自身 `realm_id`。

这允许 UI 上的同一个 Space tree 跨越多个 Realm。例如 `/Acme/Projects` 下面的普通项目、机密项目和 HR 项目可以是兄弟 Space，但各自 `default_realm_id` 不同。

### 3.2 Schema id 与字段

Schema id: `ck.schema.space.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `ck:space:` 开头。 | Space ID。 |
| `schema` | yes | `ck.schema.space.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | MUST 指向 `ck:realm:`。 | Space metadata 的 home Realm。 |
| `default_realm_id` | no | `id:realm` | MUST 指向 `ck:realm:`。 | 子资源默认 Realm；省略时继承。 |
| `scope_circle_id` | no | `id:circle` | MUST 指向 Space metadata home Realm 的 Circle。 | Space 自身 metadata 与 structural relation facts 的 effective scope；省略表示 Realm-default。 |
| `default_scope_circle_id` | no | `id:circle` | MUST 指向该 Space 子资源 effective `default_realm_id` 所在 Realm 的 Circle。 | 在该 Space 下新建子资源的默认 Circle scope；hint，不强制。若 `default_realm_id` 继承，先解析 effective target Realm 再校验该 Circle。 |
| `child_scope_policy` | no | `object` | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id`。 | 子资源 placement / encryption floor 的 reducer-enforced 约束。 |
| `parent_space_id` | no | `id:space` | MAY 指向任意 Space；跨 Realm parent 仅表示导航，不级联权限。 | 结构层级父。 |
| `kind` | yes | `string` | v1 标准 kind 包括 `space`、`project`、`folder`、`board`、`list`；profile 可注册新 kind。 | Space 类型。 |
| `title` | yes | `string` | 1..256 chars。 | 显示名。 |
| `summary` | no | `string` | <= 2048 chars。 | 简短说明。 |
| `rank` | no | `string` | 见 `encoding.md` §9。 | 在 parent 内的位置。MUST 出现在 Space 顶层，**不**得作为 `fields.rank` 嵌套字段（与 [`relation.md` §2](./relation.md) 对 Relation 的相同约束对齐；wire 上 `fields.rank` MUST 被拒绝为 `schema_violation`，详见 [`artifacts/registry/forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。 |
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

Space 是 v1 标准协作容器中唯一把顶层 `kind` 用作产品 / 容器子类型的对象：`board`、`list`、`folder` 等都在 Space.kind 表达。Realm 不按 kind 分裂安全边界；Flow 的业务分类也不放顶层 kind，必须通过 schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 表达。View.kind 是投影响应族，不表示协作容器类型。

### 3.3 行为规则

- **授权**：任何对 Space 的写入（`ck.space.create` / `ck.space.update` / `ck.space.archive` / `ck.space.restore` / `ck.space.tombstone` / `ck.space.parent`）都在 `realm_id` 指向的 home Realm 内授权。
- **同步与联邦**：Space metadata 跟随 home Realm 同步。跨 Realm parent 只是可验证引用，不把 child metadata 合并到 source Realm 的 event frontier。
- **加密 / scope**：Space 没有自己的 membership、Policy Server 或 MLS group。Space metadata 默认取决于 home Realm 的 scope、`encryption_profile` 与 metadata profile；若 `scope_circle_id` 指向 Circle，则 Space metadata 与对应 structural relation facts 落在该 Circle 的 existing scope，并继承该 Circle 的投递 / 查询裁剪与 encryption profile。
- **导航**：Space hierarchy 是产品结构树 / DAG。遍历每个 Space 节点时 MUST 独立校验该节点 home Realm 的可见性。
- **默认资源边界**：创建 Flow / Morph / View / Blob 引用等资源时，客户端 MUST 显式写入 `realm_id`，并 MAY 从目标 Space 的 effective `default_realm_id` / `default_scope_circle_id` 推导初值。`default_scope_circle_id` 的 Circle MUST 属于该 effective `default_realm_id`；如果 Space tree 的 home Realm 与默认子资源 Realm 不同，不能用 home Realm 的 Circle 作为子资源默认 scope。
- **子边界升级**：若 Space subtree 或单个 Flow 只需要 Realm 内的子事件 / 子消息边界，创建 Circle 并把 `scope_circle_id` / `default_scope_circle_id` / `child_scope_policy` 指向该 Circle；若还需要密码学隔离，则该 Circle 必须 MLS-backed。只有需要独立 federation / Policy Server / capability registry 时才创建新的 Realm。

**三字段速查表（normative）**：Space 上三个 scope 相关字段语义不同，分别由不同主体强制：

| 字段 | 语义 | 谁强制 |
| --- | --- | --- |
| `Space.scope_circle_id` | 本 Space 自身的 effective scope | reducer（写本 Space 时校验） |
| `Space.default_scope_circle_id` | 在该 Space 内新建子资源时的 *客户端 hint* 默认 scope；Circle 属于 effective `default_realm_id` | 客户端 UI（reducer 不强制） |
| `Space.child_scope_policy.require_scope_circle_id` | 子资源 scope 的 reducer-enforced 约束 | reducer（写子资源时校验） |

三字段不是冗余：自身 scope ≠ 默认 hint ≠ 子资源约束，实现 MUST 分别消费。

### 3.4 Lifecycle 与 Cascade 规则

Space lifecycle 只影响结构容器，不影响 Realm membership、E2EE group 或 history visibility。

- `ck.space.archive`：把 Space 设为 `archived`，默认 UI 隐藏；不自动 archive child Space 或内部 Flow。
- `ck.space.restore`：仅允许 `archived -> active`；不级联 restore。
- `ck.space.tombstone`：不可逆；在存在 live child Space 或 live `contains` placement 时 MUST `failed_precondition`。

错误码 MUST 使用 `space_not_active`、`space_not_archived`、`space_has_live_dependents`、`space_already_terminal`。

### 3.5 `ck.space.parent` cas_register basis

`ck.space.parent` 写入 cell：

```text
cell_id := ck:cell:ck.component.space.parent.v1:<space_id>
lattice := cas_register
bottom  := reject
value   := id:space | null
```

规则：

- 首次 set 使用 `head_eq null`。
- reparent 使用 `head_eq <old_parent_space_id>`。
- 并发 reparent 返回 `⊥`，后续 Move fail closed，必须走 conflict recovery。
- `parent_space_id == this_space_id` MUST `schema_violation`。
- parent Space MAY 位于不同 Realm；这只影响导航，不传播 membership、capability、history、E2EE key 或 retention policy。

### 3.6 Flow 位置

Flow 在 board/list 类 Space 中的位置仍由 cas_register cell 维护：

```text
cell_id     := ck:cell:ck.component.flow.position.v1:<board_space_id>:<flow_id>
lattice     := cas_register
bottom      := reject
plane       := control（默认 sealed=true）
value shape := { "list_space_id": id:space, "rank": string } | null
```

**Plane 裁决（normative，CBA）**：`ck.component.flow.position.v1` 是非治理强一致对象，按 [`event-auth-state-resolution.md` §9.4](../authz/event-auth-state-resolution.md) 三选一。**默认裁决是选项 2（`sealed=true` 升控制面）**——这保留上表 cas_register / bottom=reject / `expected_position` CAS basis 的全部既有语义不变，`ck.flow.move` / `ck.flow.reorder` 因此是 Control Move（携带 `seal_basis`，由 Seal 裁决）。Realm schema MAY 改声明为选项 1（data plane `mv_register` + user-pick：并发拖动暴露多 heads，任何有写权限者一笔写收敛、无协议 `⊥`）或选项 3（per-object sequencer）；改声明后 `expected_position` 退化为诊断字段。看板拖动延迟敏感、且 Realm 接受多值短暂并存的部署 SHOULD 评估选项 1。

`ck.flow.move` payload 字段：

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
  "id": "ck:space:019640b6-8000-7000-8000-000000000000",
  "schema": "ck.schema.space.v1",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "default_realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "kind": "project",
  "title": "Website Redesign",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Confidential sibling Space：

```json schema=schemas/space.schema.json
{
  "id": "ck:space:019640c0-8000-7000-8000-000000000000",
  "schema": "ck.schema.space.v1",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "default_realm_id": "ck:realm:019641aa-0000-7000-8000-000000000000",
  "parent_space_id": "ck:space:019640a0-8000-7000-8000-000000000000",
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

- `ck:realm:<uuid>`
- `ck:space:<uuid>`

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Space hierarchy：[`space-hierarchy.md`](./space-hierarchy.md)。
- Realm links：[`realm-links.md`](./realm-links.md)。
- Flow / Message / track 语义：[flow-and-message.md](./flow-and-message.md)。
- Relation 基数与跨 Realm 规则：[relation.md](./relation.md)。
- CBA / Lattice：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- `ck.flow.move` / cas_register sync 编译：[`../sync/operations-sync.md`](../sync/operations-sync.md)。
- Realm / Space schema：`artifacts/schemas/realm.schema.json`、`artifacts/schemas/space.schema.json`。
