---
title: Realm & Space
status: candidate
normative: true
stability: v1
updated: 2026-09-15
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 协作图中的两个一等对象：

- **Realm**（`ak:realm:`）：security / sync / auth / E2EE / federation 的硬边界。
- **Space**（`ak:space:`）：用户可理解的结构容器与导航节点，可表达 organization 下的 workspace、project、folder、board、list、section、calendar bucket 等形态；Space 自身不是安全边界。

两类对象的边界职责严格分离：

- `Realm` 承担 security / sync / auth / E2EE / federation 边界；**不**承担产品导航树职责，也不应被建模为 parent/child hierarchy。
- `Space` 承担层级、排序、分类、项目组织和工作流容器职责；自身不是安全边界。
- 强保密差异通过切分 Realm 表达；同一 Realm 内的 capability / Group 只承诺操作隔离，不承诺对已入组成员的强读隔离。

Realm 之间只允许显式 link graph（governance / discoverability / import-export / confidential-extension 等关系），详见 [`realm-links.md`](./realm-links.md)。Space 层级与跨 Realm 导航见 [`space-hierarchy.md`](./space-hierarchy.md)。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Realm

### 2.1 概念

每个 `ak:realm:` ID 都是一个 security / sync / auth / E2EE 边界。以下语义全部以 Realm 为根解析：

- membership
- capability grant / revoke 的授权上下文
- history visibility
- E2EE / MLS group governance
- federation policy
- retention / legal hold
- plaintext-visible service
- event checkpoint / RealmCommit pipeline

`Realm` 的语义接近“保护域”或“治理域”，不是“项目文件夹”。一个组织通常会拥有多个 Realm：公开项目、普通内部项目、机密项目、HR 项目、法务项目可以由同一组织入口的 View 展示，但每棵 canonical Space tree MUST 位于同一个 Realm。

`security_class=high_assurance` 是 Realm 的可选标签，进一步收紧 federation policy 与默认审计 / E2EE 选项。

### 2.2 Realm 与 MLS group

Realm 创建时没有加密 profile、content scheme 或 encryption floor。每个 scope 初始为 plaintext；首个
accepted `ak.mls.genesis` 将该 scope 不可逆地激活为 standard RFC 9420。

**canonical effective scope key bytes（normative）**：`effective_scope` 是 `realm` / `circle` / `sidecar`
三分支封闭 `oneOf`，它的 canonical key bytes 固定为

```text
realm:    UTF8(realm_id)
circle:   UTF8(circle_id)
sidecar:  UTF8(realm_id) || 0x1F || UTF8(sidecar_id)
```

RealmId 与 CircleId 都是全局唯一的 typed ID，自带互不相同的 kind 前缀且定长
（`^ak:<kind>:[A-Za-z0-9_-]{44}$`），因此它们各自单独就已经确定了一个 scope，重复 `realm_id`
不增加任何区分度；Sidecar 分支保留 `realm_id` 前缀，是因为 Sidecar 的 scope key 早于本节就按
`RealmId || 0x1F || SidecarId` 定义，且 `0x1F` 不可能出现在两个分量内部。三条分支的字节串因 kind
前缀与长度互不重叠，该编码整体单射。实现 MUST NOT 改用 JCS、字段序或任何带长度前缀的变体，
MUST NOT 给 `circle` 分支补上 `realm_id`，也 MUST NOT 省略 `sidecar` 分支的 `realm_id`——三者都会
改变 `group_id`，并同时改变以同一字节串为 context 的 MLS-Exporter 派生（见
[`exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)）。

**MLS `group_id` 的唯一派生式（normative）**：RFC 9420 原生 `group_id` bytes 固定为

```text
group_id_bytes = SHA-256(
  UTF8("ak.mls.group_id.v1") || 0x00 || canonical_effective_scope_key_bytes(effective_scope)
)
```

Arkret JSON 中的 `mls_group_id` 是 `base64url_no_pad(group_id_bytes)`，v1 固定 43 个字符。digest 固定为
SHA-256，**不**跟随 Realm `digest_algorithm`——group identity 不为每个 Realm 增加 suite 分支。actor
MUST NOT 提交该值；reducer 与 SDK 只从 effective scope 派生并逐字节验证。

v1 **只有**这一个公式。实现 MUST NOT 同时接受早期的可逆编码
`base64url_no_pad(utf8(canonical_effective_scope_key(scope)))`，MUST NOT 按字符串长度、group epoch 或
接收方本地状态在两个公式之间猜测，也 MUST NOT 把已有 group 的 `group_id` 原地改写后继续沿用原
transcript：旧 group 只能整体重建。本派生**不**承诺隐藏同一 group 的流量关联，也不抵抗已知候选 scope ID
的字典验证；它只阻止被动观察者从 `group_id` 直接还原 effective scope ID。

三个分支的 byte-exact KAT 与旧公式拒收向量是
`ak.vector.mls.group_id_derivation_kat.v1` 与
`ak.vector.mls.group_id_reversible_formula_rejected.v1`，材料在
[`mls-group-id-derivation-fixture.json`](../../artifacts/fixtures/mls-group-id-derivation-fixture.json)。

Realm-default group 与每个 MLS-backed Circle group 完全独立。Realm policy 不提供 Circle group/secret/counter fallback。
`history_access` 是 Realm 自有的单向安全 ratchet：create 初始化为二态之一，之后仅允许
`all_history_for_current_members → since_join`，永久禁止放宽；MLS 激活要求 current 值为 `since_join`。
它只约束历史交付，不进入 MLS key-access revision。具体 T0/T1 与恢复规则见
[`history-visibility.md`](../governance/history-visibility.md)。

### 2.3 Schema id 与字段

Schema id: `ak.schema.realm.v1`

> Materialized Realm 上以 **reducer 派生** 标注的字段只是当前态快照。写入路径必须使用对应 per-facet state Event，不得直接 PATCH Realm 对象更新这些字段。`trust_domain` 在 create 时锁定；MLS 激活状态只由该 scope 的 accepted Genesis/Commit 链派生。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:realm` | 以 `ak:realm:` 开头。 | Realm ID。 |
| `schema` | yes | `ak.schema.realm.v1` | 固定。 | 对象 schema。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称；产品 UI MAY 隐藏或弱化它。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `security_class` | no | `enum(standard, high_assurance)` | 默认 `standard`。`high_assurance` MUST 满足 `federation_policy ∈ {closed, restricted, quarantine}`。 | 安全等级标签。 |
| `trust_domain` | yes | `id:trust_domain` | create-locked；必须匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context。 | 跨 deployment replay boundary。 |
| `owning_organization_ids` | no | `array<did_core_id>` | 每项是 Organization Principal 的稳定身份；仅是 create/update 中的声明或投影，已验证归属必须有 active `ak.realm.organization`。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 `ak.schema.realm.v1`；除 genesis 封闭 allowlist 内的结构角色 profile 外，只允许 `ak.schema.*.vN`。 | 启用 schema，并在 genesis 中承载封闭的结构角色判别式；不是通用 conformance / policy profile 激活面。 |
| `policy_id` | no | `id:policy` | reducer 派生。 | 当前 Realm access policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | reducer 派生。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | reducer 派生。 | 默认加入规则。 |
| `history_access` | yes | `enum(since_join, all_history_for_current_members)` | reducer 派生且在任一时点恰有一个 current 值；accepted MLS Genesis 要求 current 值为 `since_join`。 | scope-local 历史访问策略。 |
| `preview_policy_id` | no | `id:policy` | reducer 派生或投影字段；canonical 写入路径为 `ak.realm.preview_policy`。 | 加入前 / token-scoped preview 的 policy 引用或摘要。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | reducer 派生。 | 联邦策略。 |
| `digest_algorithm` | no | `enum(digest-suite-registry active ids；v1: sha256, blake3)` | create 时锁定，唯一例外是 `ak.realm.digest_suite_transition`（默认 `sha256`）。 | Digest suite（canonicalization × hash 注册元组，见 [`encoding.md` §3.1–§3.3](../conformance/encoding.md)）：裸 id = canonical JSON 归一化，点分 id（如 reserved 的 `cbor.sha256`）= 备用归一化编码 suite。Realm 内单一 suite 排他；切换走控制面 suite transition RealmCommit（[`event-auth-state-resolution.md` §13](../authz/event-auth-state-resolution.md)）。 |
| `governance_station_id` | yes | `did_core_id` | genesis 固定 generation 0；materialized Realm 由连续 handoff chain 派生当前值。 | 当前治理 Station；该 Station 为 Realm、每个 Circle、每个 Sidecar 的独立 stream 签发 RealmCommit。 |
| `availability_policy` | no | `object` | reducer 派生，经 `ak.realm.policy_bundle` 写入；缺省逐字为 `{min_holders:1,applies_to:["commit_include"],minimum_retention_ms:86400000}`。eligible holders 只从 predecessor confirmed membership 的 ActorId routing-service projection 去重派生。 | bytes availability receipt 门槛。 |
| `max_authority_lifetime_ms` | no | `integer` | 默认 24h；用于 [`capabilities.md` §10.1](../authz/capabilities.md) 无限期 parent grant 首次转授时冻结 `authority_expiry_commit`。effective 值取 Realm 字段与任何 grant / policy / deployment / profile 更短窗口的最小值。 | 委托防滚动续期窗口。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_by` | yes | `ActorId` | 必须是 create event 授权主体。 | 创建 Actor。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

#### 2.3.A 字段 carrier inventory（normative）

`ak.schema.realm.v1` 是 effective query projection，不是 `ak.realm.create` 的 payload schema。每个字段必须从下列唯一 carrier 构造，禁止 create/profile/policy 重复声明：

| 字段组 | 唯一 canonical carrier |
| --- | --- |
| `trust_domain`、`security_class`、`governance_station_id`、`initial_join_rule`、`initial_history_access`、`initial_discoverability` | `ak.realm.create` 的 closed `ak.schema.realm_genesis.v1` object；这些 generation-0 identity、authority 与初始策略坐标进入 Realm ID preimage。 |
| `title`、`summary`、`avatar_blob_ref` | `ak.realm.profile` → `realm_profile`。 |
| `default_discoverability` | `ak.realm.discovery`。 |
| `default_join_rule` | `ak.realm.join_rule`。 |
| `history_access` | `ak.realm.history_access`。 |
| non-public history range | 该 scope 唯一 current `ak.realm.history_access`；Event projection与授权历史分页共用它。 |
| bundle 组件集合（本节 §2.2，含 `federation_policy`、freshness / proposal / compaction / authority-lifetime 时窗） | `ak.realm.policy_bundle`。整个 bundle 每次按 `policy_revision` 完整重述；这些字段不得回落到 create 或 generic patch。 |
| alias | `ak.realm.alias`。 |
| plaintext-visible services | `ak.realm.plaintext_visible_services`。 |
| Station admission policy | 直接约束 member AccountId 中的 `station_id`；不复制成员级 route evidence。 |
| verified organization relationship | `ak.realm.organization`。 |
| lifecycle、其它已有专用 facet | 对应 registered event/typed current result。 |
| `id`、`created_by`、`created_at`、`updated_by`、`updated_at` 与其它 query-only 字段 | 分别由 Realm identity、signed envelope 与 reducer history 派生，不由 producer 在 Realm object 中重复写入。 |

Realm 结构角色 profile 只允许出现在 `ak.realm.create.payload.object.schema_refs` 的封闭三项 allowlist 中，并随 genesis create-lock。后续 `ak.realm.schema.payload.value.schema_refs` 只接受 `ak.schema.*.vN`；它不能新增、删除或替换结构角色 profile。两条写入路径的接受面有意不对称，receiver MUST NOT 用 profile 字符串的通用匹配、默认补齐或私有 active-profile 集合抹平该边界。

v1 不定义 monolithic `ak.realm.update` 或 `realm_metadata`。实现 MUST 拒绝这些形态，
所有实现只读写上述唯一 carrier，不得把完整 Realm create object 缓存为第二真相源。

`owning_organization_ids`、`fields`、`policy_id`、`preview_policy_id`、`default_strand_id` 与 `retention_policy_id` 不构成遗漏的自由写入面：它们分别由已接受的 `ak.realm.organization` 关系、registered extension projection、`ak.policy.set`、`ak.realm.preview_policy`、`ak.realm.set_default_strand` 与 retention Policy 投影。producer MUST NOT 在 profile 或 policy bundle 中重复声明这些 query 字段。

跨字段约束（normative）：`history_access` 只有 `since_join` 与 `all_history_for_current_members`。治理 Station 仅在 current `history_access=since_join` 时接纳该 scope 的首个 `ak.mls.genesis`；激活后任何放宽历史范围的更新均以 `failed_precondition` 拒绝。

### 2.3.0 Realm 组织归属与治理同意（normative）

`owning_organization_ids` 是 Realm metadata 中的声明 / 投影字段，不单独产生"官方 Realm"、"组织治理 Realm"或"组织控制 Realm"语义。客户端、Directory、搜索索引和管理 UI MUST NOT 仅凭该数组展示 verified badge、组织官方背书、组织治理归属或组织控制权。

已验证的组织关系 MUST 由 active `ak.realm.organization` 表示。该事件有两层独立授权：

1. **Realm-side acceptance**：事件必须作为目标 Realm 的 durable reducer-input event 被接受；写入者必须满足 `ak.realm.admin`，或处于 §2.5 允许的 create bootstrap 同批初始配置路径。这表示 Realm 当前治理面接受该组织关系声明。
2. **Organization-side consent**：`payload.authorization` 必须验证到 `payload.organization_id` 的 DID control state、threshold governance proof，或该组织 DID Document / governance profile 显式委派的 Account Authority / `ArkretGovernanceService`。委派 purpose MUST 覆盖 `ak.realm.organization`、`payload.relationship` 和 `payload.control_scopes`；事件时间必须落在 delegation 有效期内，且未被撤销。

`ak.realm.organization` 的 reducer typed current result subject 是 `(payload.organization_id, payload.relationship)`；`payload.status="active"` 表示该组织关系当前生效，`payload.status="revoked"` 表示同一组织关系已撤销。`statement_id` 只用于审计和替换 / 撤销链路，不是 typed current result subject。Directory 或客户端显示"官方 / 组织治理 / sponsor / directory certified"状态时，MUST 同时检查该 typed current result 的 latest accepted value 为 `active`、已到 `not_before`（若存在）、未超过 `expires_at`（若存在）、`control_scopes` 覆盖所展示的语义，并按时点解析组织 DID / delegation。

不同控制语义不能由组织归属自动推导：

- `relationship="owner"` 或 `control_scopes` 包含 `official_badge` 只表示组织背书该 Realm 的身份归属；不自动授予组织管理员 capability。
- 组织能否管理成员、policy、retention、moderation 或明文可见服务，仍由 `ak.realm.admin` capability、Realm policy facet、service binding 或对应控制事件决定。
- 组织能否控制治理 Station handoff，必须由 Realm authority、capability 与 `ak.realm.governance_station.change` 明确表示；不得从 `owning_organization_ids` 或 `ak.realm.organization` 自动继承。组织关系本身也不能替账号选择 Station。
- Realm admin 单方面把某个稳定 Organization principal id 写入 `owning_organization_ids`，如果没有对应 active `ak.realm.organization` 组织侧证明，接收方 MUST 把它视为未验证声明。

被授权读取 Realm 的客户端通过 self-surface 操作 `ak.self.realm_organization.read.list.v1`（`GET /_arkret/self/realms/{realm_id}/organizations`，response schema `schemas/realm-organization-operations.schema.json#/$defs/realm_organization_relationship_list`）取回该 Realm 的 `ak.realm.organization` 关系投影（active / revoked / expired，latest-per-`(organization_id, relationship)`，由 reducer 派生 `lifecycle_phase`）以及无验证语句的 `declared_organization_hint_ids`。客户端 MUST 仅在 `lifecycle_phase=verified_active` 时显示官方 / 治理 / 背书状态，并 MUST 把 `declared_organization_hint_ids` 渲染为未验证声明。public discovery 路径（Directory Service 的 `ak.find.directory.read.resolve_realm.v1` / `resolve_organization`）受 anti-enumeration 约束，不替代成员 / admin 侧的本操作。

### 2.4 最小示例

```json schema=schemas/realm.schema.json
{
  "id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "schema": "ak.schema.realm.v1",
  "title": "Launch Plan Confidential Realm",
  "trust_domain": "ak:trust_domain:did.webvh.acme.example",
  "schema_refs": [
    "ak.schema.realm.v1"
  ],
  "default_discoverability": "invite_only",
  "default_join_rule": "invite",
  "history_access": "since_join",
  "governance_station_id": "ak:did_core:webvh:zAKD7rB7Tn8G84VgUBAjn8p2h",
  "created_by": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
      "station_id": "ak:did_core:webvh:z6mkfixturestationexample"
    }
  },
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

### 2.5 `ak.realm.create` Reducer Bootstrap（normative）

#### 2.5.0 `realm_id` 由 genesis Event 派生且自证（normative）

Realm ID 不由创建者选取，而是由 genesis Event 自身派生。`ak.realm.create` MUST 满足：

```text
envelope.realm_id       MUST 省略
envelope.scope_ref      MUST 是 {"kind":"realm_genesis"}（不含 realm_id）
payload.object.id       MUST 省略

receiver 派生：realm_id = retype(event_id, "realm")
```

违反 MUST `schema_violation`，`reason_code=realm_id_not_event_derived`。

每一个 Realm——Collaboration、Direct Conversation、human PCR 与 Agent PCR——的 closed genesis object MUST 使用 `schema="ak.schema.realm_genesis.v1"`，并携带：`purpose`、`genesis_salt`、`trust_domain`、`security_class`、`governance_station_id`、`initial_join_rule`、`initial_history_access`、`initial_discoverability`。其中：

```text
genesis_salt = base64url_no_pad(CSPRNG(32 octets))
```

canonical wire 恰为 43 chars，禁止 padding、非 URL-safe alphabet、31/33 bytes、时间/HLC/UUID/计数器或可预测 PRNG。每个新 create intent 只生成一次并先与 intent 持久化；prepare、签名、HTTP retry、receipt 查询与 crash recovery 必须复用同一 salt 以及首次持久化的 exact signed unit。salt 不是 replay nonce、授权、新鲜度、排序或 winner 输入。**PCR 与 Agent PCR 同样 MUST 携带 `genesis_salt`**：收敛为 event-derived 后它们不再是例外分支。salt 在此的作用是 (i) 消除例外、(ii) 使 PCR 地址不可由 DID 预先推算、(iii) 强制 durable intent 纪律——崩溃后重建 create 会得到不同 `event_id`，复用同一 salt 与首次持久化的 exact signed unit 才能避免产生第二个 PCR；该纪律与账号维度唯一约束互为正反面。

**为什么必须省略而不是"携带并校验相等"（normative rationale）**：`event_digest` 的 preimage 只排除 `event_id` / `proofs` / `unsigned`（[`../conformance/encoding.md` §6](../conformance/encoding.md)），`realm_id` 与 `scope_ref` **仍在 preimage 内**。而 §4.0 的 `event_id` 由该 digest 决定，`realm_id` 又要等于 `retype(event_id)`——于是 `realm_id` 成为 digest 的函数，却又是 digest 的输入，**定义即循环，没有不动点可解**。唯一出路是把它移出 preimage，即从 envelope 省略；`scope_ref` 同理，故 genesis 使用不含 `realm_id` 的 `realm_genesis` 形态。这与 Matrix room v12 把 `room_id` 从 create event 移除的理由完全相同。

Realm 之外的 create-once 对象没有这个问题：它们的 ID 只出现在 payload，且按 [`common-fields.md` §6.0](./common-fields.md) 一律省略。

**Principal Control Realm 与 Agent PCR 适用本节通则（normative）**：
**全部 Realm——含 human PCR 与 Agent PCR——一律按 §2.5.0 从各自 genesis Event 派生
`realm_id`**，使用同一个 33-octet / 44-character Realm token wire form，不使用 UUID。

理由：PCR 的作用域是「某个 DID 在**当前 Station** 上的账号」，同一 DID 在不同 Principal
Server 上是完全独立、不可迁移的 PCR。因此 `realm_id` MUST NOT 只由 principal DID 决定：那样会让这些互不
相关的 PCR 算出**同一个 `realm_id`**，使该 id 无法标识“哪一个 PCR”。这些值只在同一账号 authority 内用于设备、恢复与审计状态重建，不进入普通联邦 Event 的外部 identity；event-derived 仍能避免本地状态与恢复记录碰撞。
event-derived 天然按创建事件区分，同时使 `realm_id` 承诺 create Event 的完整内容。

**「一个账号至多一个 PCR」不再由 id 碰撞保证**：event-derived 下两次 genesis 产生两个不同 `realm_id`，
`realm_already_exists` 不再拦截重复。Station MUST 在**账号维度**（其本地 accounts 记录）强制
该唯一性，并在冲突时零写入拒绝；实现 MUST NOT 依赖 id 相等来发现并发 genesis。

`realm_token[0]` 按 nibble 拆分：**高 4 位永久保留并 MUST 为 `0x0`**，低 4 位是 `digest_suite`。
v1 Realm 算法固定为 `digest_suite=0x1`（SHA-256），因此 v1 唯一合法 header 是 `0x01`。
该 nibble 不承载派生类别信息，语义与 Event ID 的 reserved nibble 完全一致。任何非零高 nibble MUST NOT 产出，收到 MUST 以 `realm_id_not_event_derived`
拒绝。低 nibble `0x0` 与 `0x2..0xF` 非法/保留；普通 Event 支持其它低-nibble suite 不代表 Realm 自动支持。

PCR 的**身份锚**与其 `realm_id` 是两件事：realm id 按上述通则由 genesis Event 派生，而该 PCR 属于哪个 principal 由 create 携带的唯一 critical root anchor ref 决定（见 [`../identity/key-management.md` §5.0.1](../identity/key-management.md)）。远端 verifier 需要判定"某 RealmCommit 是否属于该 principal 的 PCR"时，MUST 以已签名的 `pcr_genesis_unit` receipt 中承诺的 `realm_id` 为准，MUST NOT 从 principal DID 自行重算。

因此 `ak:realm:` 始终只有一种物理形态：`ak:realm:<44-char-token>`，解码后恰为 33 octets。所有 Realm（含 human PCR 与 Agent PCR）都重类型其 create Event 的 token（header `0x0S`）。它不是 producer 自选。

**Realm id 不编码 Realm 类别。** header 只说明 token 布局与 digest suite，收敛后已无可分配的类别空间；
Realm **是什么**由签名 create payload 的 `purpose` 表达。新增 `purpose` 取值不改变 id 形态，
实现 MUST NOT 从 `realm_id` 反推 `purpose`——判定类别的唯一权威是已验证的 genesis Event payload，
receiver 按上文首次接触校验义务取得它。实现 MUST NOT 逐调用点自选，不得接受 UUID Realm ID，也不得把 Realm token 存入原生 UUID / `BYTEA(16)`；推荐存储为完整 typed string 或 raw `BYTEA(33)`。

持久化实现 MAY 建立 `canonical_realms(pk, identity, wire_id, ...)` 一类本地 intern 表，并以
`realm_pk` 作为 Event、投影和 Realm 业务表的物理外键；这与 Event 的本地 `event_pk` 分层相同。
`pk` 仅服务数据库 join/index，永远不得序列化。`identity` 必须无损保存完整 33 octets并唯一约束，
`wire_id` 必须能 canonical round-trip；写入关联行时必须确认 `realm_pk` 与其 wire `realm_id` 相同，
不得因本地 `pk` 相同或不同改变协议身份、重放、冲突或首次接触判断。

固定 KAT 与负例由 `ak.vector.object_identity.event_derived_realm.v1` 承载。

**首次接触校验义务（normative）**：receiver 首次接触某个 `realm_id` 时 MUST：

1. 先定位该 Realm 的 `ak.realm.create` 并取得其完整 canonical bytes；
2. 对所有分支重算并校验 `event_id`；
3. 对**所有** `purpose` 校验 `retype(event_id) == realm_id`，且 `genesis_salt` 为 canonical Base64URL-no-pad 的 32 octets；`purpose="principal_control"` 走 `did_root_anchor` 分支时另需校验 create 携带的唯一 critical `did_inception` root anchor ref，走 organization-governed `delegated_pcr_genesis` 分支时改验 `executed_by` / `authorization_ref` 的 governance delegation（该分支 MUST 不含 `did_inception`，两分支因此结构互斥）；`purpose="agent_control"` 时 create **不携带任何 anchor ref**，改为反查 controller PCR 中是否已存在 accepted 的 `ak.agent.provision` 声明了 `retype(本 create 的 event_id)`，无匹配 MUST 零写入拒绝（见 [`../identity/key-management.md` §3.6.3](../identity/key-management.md)）；
4. 取得并验证完整 ordered genesis unit 与其 genesis RealmCommit/state commitment；identity 或 genesis closure 任一未完成前 MUST NOT 接受该 Realm 的后续 Event、RealmCommit 或 effective Realm projection；
5. 把该 genesis 与完整初始 facet commitment 持久化为该 `realm_id` 的永久本地绑定；
6. 此后出现的任何不同 genesis MUST 拒绝，MUST NOT 因为它先到、更新、或来自"更权威"的 peer 而覆盖。

上面第 3 条大体已被现有机制隐含——state-changing Event 的领域 payload 要 `expected_revision`、每条 Event 的授权由治理 Station 在接纳事务内解析，RealmCommit 链最终 root 在 genesis RealmCommit——但仍 MUST 显式执行，否则实现会在 backfill 乱序时先落一半状态。

**这条使 `realm_id` 自证。**一个恶意 join candidate 服务自造的"Realm S"时，其 genesis 内容不同 → `event_id` 不同 → `retype(event_id) ≠ S` → 首次接触即被拒。因此 invite、`join_candidates[]` 与 Directory 响应 **MUST NOT** 被要求携带 genesis digest 或 authority-root 值：自证不需要外部背书，也不引入对邀请者或 Directory 的新信任。拒绝时的对外语义复用 [`../sync/federation.md` §5.0](../sync/federation.md) 规则 4 的统一最小披露失败族。

> **边界：identity 自证，naming 不自证。**攻击者仍可创建一个 `realm_id` 完全合法自证的 Realm，再去抢注一个像样的 alias。alias 抢注与目录投毒是独立问题，本节不解决，也 MUST NOT 被表述为已解决。

除非底层 256-bit digest 发生完整 hash collision，两条不同 digest preimage 的 create 必然有不同
`event_id`、因而是两个不同的 Realm。"同一 Realm id 的第二条 create"要么是携带 ID 与重算 digest
不符的伪造输入（必须在 lookup 前以 `event_id_digest_mismatch` 拒绝），要么是约 `2^128` 通用复杂度的
完整 collision evidence（必须整组 quarantine）。下文步骤 3 的 `realm_already_exists` 因此是防御性
剩余分支，不是常规路径，也不得退化为 first-create-wins。

#### 2.5.1 Bootstrap 步骤

`ak.realm.create` 是 Realm 生命周期的 genesis Event，只建立 Realm identity/security core、generation-0 governance Station 与终身稳定的 authority root。显示内容、policy 与 membership 都由同一原子 bootstrap unit 中各自的 registered facet Event 建立。

**Human Principal Control Realm 分支（normative）**：当 create 满足 `purpose="principal_control"`、PCR profile、`actor_id=principal DID` 与唯一 critical `did_inception` root anchor 时，root-signed genesis 必须携带 `FoundingDeviceDescriptor`，第二条固定为 founding-device-signed `ak.device.authorize`。两条 proof 必须省略 `signer_resolution_evidence_ref`：root key 只从同一提交冻结的 registration DID/root-control evidence 解析，founding device key 只从 root-signed descriptor、authorize payload 与 unit-local candidate overlay 解析。两条通过 `ak.peer.principal_genesis.command.submit.v1` 原子接受，均免 `expected_revision`；descriptor 与 authorize payload 必须逐字段/digest 相等。任一 Event 脱离完整 unit/receipt closure 均不可接纳或复验，省略规则不得用于其它 create/authorize。Agent PCR 的 controller-authorized分支 MUST 使用 `purpose="agent_control"`，且不使用 human `pcr_genesis_unit` 或 `FoundingDeviceDescriptor`。

以下两项是所有 purpose 共有的无条件 registered writes；另有五条 registered condition row。任何实现不得由 create 顺带写 profile 或 member 状态；Agent lifecycle 与三个互斥 purpose 的 history-access 初始化仅限下述已登记条件写入。完整集合及条件以机读 registry 为准。

`ak.realm.create` 的 registered writes MUST 由该 Event 的 canonical reducer contract 原子承担。全部 writes 在 [`contract-registry.json`](../../artifacts/registry/contract-registry.json) 的 `ak.realm.create.result_writes[]` 中登记；wire 不重复携带：

1. **写入 `realm_genesis` singleton**：值为 closed `ak.schema.realm_genesis.v1` object；该 typed current result 是 create-locked identity/security core 的唯一权威。accepted create 本身由 genesis RealmCommit 记录，不再另投影一份 create 日志；同一 Realm 的不同 create 以 `realm_already_exists` 或 collision quarantine 拒绝，不由 projection 选择 winner。
2. **写入 `realm_authority_root` typed current result**（`result_selector=null`），值由注册 `value_projection` 从 signed envelope 与 create payload 确定性派生：

   ```text
   {
     "controller_actor_id": "<envelope.actor_id>",
     "controller_epoch": 0,
     "authority_generation": 0
   }
   ```

   该值是 [`typed-current-result.schema.json`](../../artifacts/schemas/typed-current-result.schema.json) 的封闭 `realm_authority_root_value`，由三个写入方的 `value_schema_ref` 以 JSON Pointer 指向；它**没有**自己的 `ak.schema.*` id，理由见 [`../sync/current-results.md` §1](../sync/current-results.md)。`(realm_id, result_selector)` 是该 Realm **终身稳定的 authority root identity**；`controller_actor_id` 是当前控制者，`controller_epoch` 只随 `ak.realm.owner.transfer` 递增，`authority_generation` 只随 `ak.realm.authority.reset` 递增；二者都由 registered reducer contract 从 `expected_state_digest` 锁定的冻结前态 `checked_add` 得出，author 无可选值。该 `authority_generation` 是**授权委派代次**，与 `RealmCommit` 的治理 Station 任期代次 `governance_generation` 是两个不同的计数器，MUST NOT 互相替代（见 [`authz/capabilities.md` §10](../authz/capabilities.md#10-issuer-authority)）。owner/admin coverage 由 v1 固定领域 reducer 解释，不进入该 typed current result。author 不得自行提供这些派生字段。

3. **条件写入 `identity_resolution` singleton**：仅当 `payload.object.initial_resolution` 存在时，投影其完整已登记 resolution commitment。
4. **条件写入 `agent_status` typed current result**：仅当 `payload.object.purpose == "agent_control"` 时，以完整 Agent account ActorId 的 `canonical_json(envelope.actor_id)` 作为唯一 composite 分量派生 subject，把该 Agent 从 `uninitialized` 推进到 `active`。后续 pause / resume / deactivate 必须复用同一 subject；Agent 与 controller 的 principal 分量分别由 `envelope.actor_id` / `executed_by` 派生，lifecycle payload 不携 `agent_id` 或任何 controller identity 镜像，且这四个 kind 的 `executed_by` 与配对 `authorization_ref` 由 event-kind admission 规则强制存在。
5. **条件写入 `realm_history_access` FSM typed current result**：仅当 `payload.object.purpose == "direct_conversation"` 时，原子执行 `null -> since_join`。
6. **条件写入同一 history-access FSM typed current result**：仅当 `payload.object.purpose == "principal_control"` 时，原子执行 `null -> since_join`。
7. **条件写入同一 history-access FSM typed current result**：仅当 `payload.object.purpose == "agent_control"` 时，原子执行 `null -> since_join`。

以上两条无条件写入加五条条件 row 构成 create 的完整 projection；第 5 至 7 条按唯一 `payload.object.purpose` 互斥命中。普通 Collaboration 的 history 初值仍来自显式 bootstrap facet；profile、member 与其它初始 state 由后续 slots 的 registered writes 产生，完整 unit 的所有 writes 在**同一个接纳事务**内一起落下；各条 Event 各自获得同一 Realm stream 上 position 连续的独立 RealmCommit（一条 RealmCommit 恰好接纳一条 Event，见 [`../identity/contact-and-direct-conversation.md` §6.1](../identity/contact-and-direct-conversation.md)），不存在一笔覆盖整个 unit 的 Commit。任一 required write 失败，整个 unit MUST 原子回滚；authority-root 缺失时返回 `realm_authority_root_missing`。

**result_writes[] 的覆盖度（normative）**：`result_writes[]` 是「某个 Event kind 写哪些 typed current result、顺序如何、条件是什么」的唯一机读合同，由 `tools/artifact_lint:result_write_contracts` 校验。**当前它只在部分 Event kind 上登记**（见 `contract-registry.json` 的 `event_kind_registry.registry_rules`，其中记录了确切的已覆盖 / 未覆盖计数）；其余 reducer-input kind 的 registered writes 目前只存在于正文。规范正文 **MUST NOT** 对尚未登记的 kind 引用其 `result_writes[]`——引用一个不存在的登记项，正是这个数组被引入来消除的缺陷。扩大覆盖面时同时收缩该注记，**MUST NOT** 把规则改写成看起来已经完整。

反方向的义务同样是规范性的，且强度相同：**已登记的 kind，它的 `result_writes[]` MUST 穷举该 kind 被接纳时在共享面上写的每一个 typed current result**。部分登记算违规——一个原子写四个家族的 kind 只登记其中一个，就是在「唯一机读合同」这份工件里把自己描述错了，而读者正是被告知要以它为准。因此这类 kind 的登记是**整体的**：四个家族要么在同一批一起落，要么一个都不落，`ak.agent.provision` 就是这条规则的判例（见 [`../identity/key-management.md` §3.6.3](../identity/key-management.md)）。

这条义务**按其本性无法门禁化**，必须由裁决与评审承担：lint 手上没有第二份「该 kind 到底写哪些家族」的清单可以与 `result_writes[]` 比对——`result_writes[]` 自己就是那份清单。`tools/artifact_lint:result_write_contracts` 只能校验已声明的行**自身**自洽（成员被 `value_schema_ref` 声明、whole-value set 写齐 required 成员），它对「少了一行」结构性无感。所以「pipeline 全绿」MUST NOT 被当作某个 kind 覆盖完整的证据。

**root authority 的语义边界（normative）**：authority-root typed current result 的 current controller 在给定 RealmCommit basis 下凭该 typed current result 的 inclusion proof 获得 effective `ak.realm.owner` 与封闭的 root-control authority。它是显式、committed、profile-bound 的协议状态，**不是** `realm_state.owner`、membership 或 `created_by` 身份旁路：

- 授权判定 MUST 使用该 typed current result 在同一 RealmCommit basis 下的 registered inclusion proof，并逐项校验 `controller_actor_id`、`controller_epoch` 与 `authority_generation`，再由该 Realm 的 fixed reducer semantics compiled rules 判定 owner coverage。任何以 `created_by`、membership、projection mirror 或运行时 registry digest 回退的实现都重新引入了隐式提权洞。
- 服务实现若维护 `realm_state.owner` 一类投影镜像，它只能是该 typed current result 的可丢弃 projection mirror，MUST NOT 参与授权判定。
- 该 authority 的 resource 固定为本 Realm 的 `realm_wide`，MUST NOT 为其它 Realm 提供普通 issuer upper bound；跨 Realm 派生只能走已注册的 `ak.capability.derived` 规则（[`realm-links.md` §6](./realm-links.md)）。
- 普通 `ak.realm.owner` grant 只表示**可撤销的 co-owner**：持有人具有 owner 的 operational / grant authority，但不控制 authority-root typed current result，因而不能 author root-control Event。`ak.realm.owner` 逐字存在于 owner 的 `grant_authority_actions`，所以 root controller 与 co-owner **都可以**把 `ak.realm.owner` 继续授予他人——这是期望行为，不是漏洞；它不改变"root-control 平面唯一且不可经普通 grant 获得"。
- current-v1 没有 authority-policy override / role-assignment singleton。owner/admin 的可配置差异由显式 capability grant、revoke、constraint 与既有 policy control typed results 表达；未知 typed current result、部署配置、`ServiceDescribe` 或 UI role 不得进入 owner 判定。`ak.realm.owner.target_event_kinds` 与 `grant_authority_actions` 只来自 fixed reducer semantics compiled bundle，并保持 direct-author 与 grant-issuer 两个集合分离。

**genesis batch 内的 staged root proof（normative）**：同一 ordered submit batch 中位于 create 之后的 Event MAY 使用 staged authority-root proof，其绑定的 create Event MUST 是同批 slot 0，且 `controller_actor_id` MUST 等于 signed envelope `actor_id`。该 proof 只在此原子 unit 内有效；batch 外一律要求 accepted RealmCommit 下的 root-typed current result inclusion proof。

Realm bootstrap event set 以 create 开始。创建时没有 accepted RealmCommit，因此下列两个**互斥封闭分支**内的 Event MAY 免 `expected_revision`（与 [`event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md#8-安全状态与-authority commit) 使用同一句，两处 MUST 保持逐条一致）：

- 普通 Collaboration 分支：`ak.realm.create`；同批同 actor 的 initial facets，顺序唯一由 `contract-registry.json.realm_bootstrap_registry.ordinary_collaboration` 登记：required `profile → policy_bundle → join_rule → history_access → discovery`，可选 `alias`，条件 `plaintext_visible_services`，最后 required creator `member.state{join}`。不得在实现中维护第二套顺序常量；
- 1:1 Direct Conversation 分支：恰好 `ak.realm.create → founder ak.member.state{join} → peer ak.member.state{join} → main ak.strand.create` 四条，不得携普通 Collaboration facet。固定 profile、policy、join、history 与 discovery baseline 由 [`../identity/contact-and-direct-conversation.md` §6.2](../identity/contact-and-direct-conversation.md) 的 registered reducer contract 机械投影；第 2 槽显式写 founder membership 并携 `expected_revision null`。`ak.strand.create` 平时由治理 Station 解析出既有授权实例后才被接纳；但该 exact unit 的四条 Event 在同一个接纳事务内各自获得连续的 RealmCommit，Strand 无法引用尚未签发的 RealmCommit，因此在且仅在该 unit 内免 basis。

不在该列表内的 state-changing Event 一律要求 `expected_revision`。Human PCR 只允许上文 root create + founding authorize 两项 shape；不得把普通 Realm follow-up 白名单混入 PCR genesis。批次结束后所有非锚点 state-changing Event 按 [`event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md#8-安全状态与-authority commit) 携带 basis。

Authz 含义：

- 同批 facet 在 creator member slot 生效前依赖 staged authority-root proof，而不是 create 隐式 membership。批次外的授权不得回退到 envelope actor、create author 或服务本地 owner mirror。
- `ak.realm.policy_bundle` payload MUST 携带单调递增的 `policy_revision`。初始 revision 为 `1`；后续更新必须满足 `new.policy_revision == previous.policy_revision + 1`，否则 reducer MUST 拒绝：回退用顶层 code=`policy_revision_rollback`，跳号用 code=`failed_precondition` 且 reason_code=`policy_revision_gap`。任何用于缓存或 identity_link 的 `policy_revision` MUST 覆盖 `policy_revision`，不得只 hash policy 字段值集合；MLS key-access revision 则只投影 key-access 字段，MUST NOT 因无关 revision 前进而变化。
- **加密激活不可逆（normative）**：scope 在其唯一 `ak.mls.genesis` 被接受之前是明文 scope；该 Genesis 的 accepted RealmCommit 把 scope 不可逆地激活为 standard RFC 9420。协议不提供任何把已激活 scope 退回明文的 Event、policy 字段或 reducer 路径；激活后到达的明文内容写入 MUST `failed_precondition`，reason=`mls_activation_required`。Realm 与 Circle 各自独立激活，Circle 侧规则见 [`circle.md` §7](./circle.md)。
- 同一 submit 批次内 reducer MUST 按 wire 顺序处理。普通 Realm：create 第一，其后是白名单内的 follow-up；human PCR：root-anchored create 第一、founding-device-signed authorize 第二且 unit 到此结束。顺序或形态不符以 `pcr_genesis_unit_invalid` 原子拒绝。
- byte-identical unit retry 返回原 accepted identity/receipt，不产生第二个 Realm 或副作用；不同 canonical bytes 声称同一 Realm id 时 MUST `realm_already_exists` 或 collision quarantine。

Server 端实现合规要点：

- server 必须先在隔离 staged state 上按 wire order 验证完整 unit，再以一个 storage transaction 提交 canonical Events、全部 registered typed results、receipt/ack 与 federation outbox；任何失败后上述可观察状态均为零。
- effective Realm query 必须组合 genesis/profile/discovery/join/history/policy/alias/lifecycle typed results；不得把 create payload 原样复制为完整 Realm，也不得读取 `realm_metadata` typed current result。
- 不允许通过 spec 之外的 REST 端点（如 `POST /spaces` 之类的私造 lifecycle 命令面）来兜底 bootstrap。此类端点违反 [`sync/service-http-binding.md` §2.1](../sync/service-http-binding.md#21-rest-api-命名空间组织) 的"实现不得用未声明路径绕过 canonical operation"规则，且会让事件流上的 read-only consumer 看不到完整的 source-of-truth 事件。

**Backfill / federation peer 一致性（normative）**：peer 可先取得 create bytes，但在完整 bootstrap closure 与 genesis state commitment 验证前必须保持 unresolved，不得接受后续 Realm Event、RealmCommit 或发布 effective projection。creator membership 来自 unit 最后独立 `ak.member.state{join}` slot；缺失不得本地补造。

### 2.6 Realm 终态 (`ak.realm.tombstone` / `ak.realm.destroy`)

Realm 有两个终态 event，语义不同：

| Event | 语义 | 是否可恢复 | successor |
| --- | --- | --- | --- |
| `ak.realm.tombstone` | "本 Realm 不再活跃" — 转移到 successor Realm（产品改版、组织重组等）。 | no，但 successor 接续历史可达 | 必填 `successor_realm_id` |
| `ak.realm.destroy` | 本 Realm 永久关闭。无 successor。 | no | MUST NOT 设 successor |

`ak.realm.tombstone` 写入 `realm_tombstone`，`ak.realm.destroy` 写入 `realm_destroy`；二者均为 commit-ordered projection，各自不可重复写入。capability：`ak.realm.tombstone` / `ak.realm.destroy`（action 定义见 [`../authz/capabilities.md` §5.1](../authz/capabilities.md)，high-risk 约束见 [`capabilities.md` §8](../authz/capabilities.md)）。

#### 2.6.0 Realm archive/restore 与 freeze/unfreeze

Realm 的 lifecycle 由 archive、tombstone、destroy 等已登记事实组合；freeze 是独立普通写入 gate。四个可逆操作都沿用原 commit-ordered projection：

| Event | typed current result family | effect | capability action |
| --- | --- | --- | --- |
| `ak.realm.archive` | `realm_archive` | 常量 true | `ak.realm.archive` |
| `ak.realm.restore` | `realm_archive` | 常量 false | `ak.realm.archive` |
| `ak.realm.freeze` | `realm_freeze` | 常量 true | `ak.realm.freeze` |
| `ak.realm.unfreeze` | `realm_freeze` | 常量 false | `ak.realm.freeze` |

payload 只接受已登记的可选 reason，不接受 archived/frozen boolean、effective_at 或 freeze_expires_at。Event kind 唯一决定 effect，重放和并发继续按同一 CAS contract。restore 只解除 archive，unfreeze 只解除 freeze；二者均不能解除 terminal/redaction、其它 gate 或 capability 限制。无论交付顺序如何，任一适用 gate 仍关闭就不得普通写入，缺安全确认材料 fail closed；不另存与这些 typed current result 竞争的 Realm 总状态。

被 archived 或 frozen 关闭的非豁免普通写入返回 `realm_frozen`（HTTP 403）。封闭豁免集合为：(a) archive/restore/freeze/unfreeze；(b) tombstone/destroy 终态升级；(c) `ak.audit.*` 与 `ak.audit.erasure_receipt`；(d) `ak.member.state{membership="leave"}`、capability/delegation/device/key revoke 及其必需审计。所有豁免仍验证普通 capability、CAS basis、签名与 schema。policy_bundle、新增成员和授权扩张不豁免；子对象直接复用此集合。终态按 §2.6.1 的更严格规则处理，不能凭恢复豁免绕过。

生命周期只由正式 Event/RealmCommit 接受推进。时钟推进不会清除冻结；解冻必须提交 unfreeze。计划执行由产品在实际执行时 author/sign/submit，不是已接受 Event 的延迟效力，也不改变既有 revocation fence 的时点。

#### 2.6.0.1 产品态"解散 Realm"映射（normative）

产品层若给 Realm owner / admin 提供"不转让、直接解散 / 关闭这个 Realm"的选择，wire 层 MUST 映射为 `ak.realm.destroy`，而不是 `ak.realm.tombstone`：

- `ak.realm.tombstone` 只用于**有 successor Realm 的迁移 / 接续**。它 MUST 携带 `successor_realm_id`，表示旧 Realm 不再活跃但由 successor 接续历史可达性。没有 successor 时，客户端 / server MUST NOT 用 tombstone 表达"解散"。
- `ak.realm.destroy` 用于**无 successor 的永久关闭**。accepted 后 Realm 仍可作为终态记录、审计对象和按 retention / history visibility 可读取的历史存在，但普通成员写入、消息发送、Circle / Strand / Relation 新写入等 MUST fail closed（`realm_terminal_state`）。这正是"Realm 还在，但所有成员不能继续发言 / 协作"的不可逆产品语义。
- `ak.realm.freeze` 用于**可逆只读冻结**（incident hold、管理员临时锁场、等待治理决策等）。如果产品文案承诺"解散 / 永久关闭"，不得只写 `freeze=true`；如果产品文案承诺"临时只读 / 可恢复"，不得写 `destroy`。
- `ak.realm.archive` 用于软隐藏 / 默认列表移出，不是 ownership transfer、迁移或解散的替代品。

实现的 UI 可以把上述 wire event 命名为"解散 Realm"、"关闭 Realm"或"冻结 Realm"，但审计、capability、federation 与 reducer MUST 以本节的 event 语义为准。ownership transfer 是成员 / capability 治理动作，不改变 Realm lifecycle；当 owner/admin 不愿 transfer 时，应在 `freeze`（可逆只读）与 `destroy`（无 successor 永久关闭）之间选择，而不是滥用 `tombstone`。

#### 2.6.1 `ak.realm.tombstone` / `ak.realm.destroy` 终态规则（normative）

任一终态 Event accepted 进入 checkpoint 之后：

1. **拒绝后续普通写入**：reducer MUST reject 所有非 `ak.audit.*` / 非 `ak.audit.erasure_receipt` event；后续 `ak.self.events.command.submit.v1` 返回 `realm_terminal_state`（错误码归类于 `realm_lifecycle` 错误域，避免与 `ak.realm.lifecycle.*` capability action 命名混用）。
2. **Snapshot / Backfill / GC**：
   - Snapshot service MAY 发布最后一份 final snapshot（`ak.realm_state_snapshot.*` event）；之后 snapshot 不再更新。
   - Backfill MAY 继续提供历史 event 给已授权 reader，受 history visibility policy 控制；新读权 MUST NOT 再被授予。
   - GC：tombstone 本身只关闭旧 Realm，不触发额外物理删除；destroy 可令 blob bytes、projection 缓存、to-device 队列、push route 按部署 retention policy 物理删除。canonical event log 仍按 retention/legal hold 保留。
3. **Successor / Tombstone 区分**：`ak.realm.tombstone` MUST 携带不同于自身的 `successor_realm_id`；`ak.realm.destroy` MUST NOT 携带该字段。Projection 对二者统一暴露 `realm_terminal_state`，并用 `terminal_kind=tombstone|destroy` 区分迁移与永久关闭。
4. **Erasure Receipt 与 Legal Hold**：destroy 不自动触发 erasure。若部署进入 erasure 阶段，发布 `ak.audit.erasure_receipt`（schema `ak.schema.erasure_receipt.v1`），可能 `outcome=blocked_by_legal_hold`。Legal hold 优先于 destroy 的 GC 路径。
5. **Federation Fanout**：终态 Event MUST 沿 federation 推送到所有曾持有该 Realm 状态的 peer Station；peer 获知有效确认后 MUST 立即持久化 live fence，标记 `realm_terminal_state` 和相同 `terminal_kind`；仍可接收历史证明与 backfill，按授权关闭规则判定历史资格，禁止借历史导入触发新 live 效果。
6. **Child Space / Strand cascade**：终态 accepted 后，home Realm 内所有 non-terminal Space、Strand placement 与 structural `contains` projection MUST NOT 作为 live navigation surface 暴露。实现 MUST 在同一事务或后续 bounded cleanup job 中把这些对象标记为只读 locked projection（destroy 可用 `realm_destroyed_orphan`，tombstone 可用 `realm_tombstoned_orphan`）或自动 tombstone/archive；不得继续允许 `ak.strand.move`、`ak.space.parent`、`ak.space.update` 等普通写入复活它们。跨 Realm parent 禁止；普通外部引用不得进入 canonical placement 或 Space 删除依赖集合。
7. **Circle scope cascade**：父 Realm tombstone 或 destroy 后，其内所有 [Circle](./circle.md) 的 **effective lifecycle** 立即进入 `realm_terminal`，但 Circle canonical lifecycle typed current result 不被隐式改写，也不合成 `ak.circle.tombstone`。该派生状态以父 Realm terminal Event 及其 RealmCommit 为唯一依据，优先于 Circle 自身 `active` / `archived` projection。任何指向这些 Circle 的写入 MUST fail closed（`failed_precondition`, `reason_code=realm_terminal_state`）；projection MAY 显示 `scope_unavailable`，但 `scope_circle_id` 不会被自动 rewrite。详见 [`circle.md` §9.2](./circle.md)。

#### 2.6.2 跨 Station Erasure Receipt Fanout（normative）

当部署对一个 Realm（或一个 principal）执行 hard erasure 时，**issuing** Station MUST：

- 发布一条 `ak.audit.erasure_receipt`（durable_event）；
- 把 receipt 与 exact retained stub 封装成 `erasure_receipt_package`，通过 `ak.peer.erasure_receipt.command.submit.v1`（`POST /_arkret/peer/erasure-receipts`）投递给所有曾接收过该 scope 内容的 peer Station；package 的 receipt MUST 省略其可选 `retained_stub`，stub 只在 package 顶层出现一次，digest 由 receiver 对 receipt 重算；
- 为每个 destination 写入有上限的 durable outbox，并只在收到 receiver 签名的 `accepted` 或 `duplicate` acknowledgement 后关闭；网络不明时使用相同 Idempotency-Key 与逐字节相同 body 重试；
- 通过 `ak.peer.erasure_receipt.resource.get.v1`（`GET /_arkret/peer/erasure-receipts/{receipt_id}`）向 issuer、receiver 或显式授权 auditor 返回 exact package；未知、隐藏与未授权统一 `not_found`，不得提供可枚举列表。

**receiving** peer 处理 receipt 时 MUST：

- 在任何删除或 durable acknowledgement 之前，验证 service-to-service transport，要求 `Source-Service-ID == receipt.issuer`，并验证 receipt schema、签名链、issued-at authority、`receipt_digest`、retained-stub digest 与 scope/subject/terminal binding；
- 如果 peer 本地存有该 erasure scope 内的 blob / projection / cache，按 receipt `scope.storage_boundary` 走本地删除流程，并发布自己的 `ak.audit.erasure_receipt` 反馈实际结果；
- 失败（legal hold、retention 冲突、blob 已被备份到不可达存储）MUST 在 peer 自己的 receipt `outcome` 字段写 `partially_completed` 或 `blocked_by_legal_hold`，不得假装成功；
- 任何 peer 未在 `erasure_propagation_window_ms`（默认 7 天）内回执，issuing server MUST 在该 erasure receipt 的 `fanout_status` 字段标 `incomplete`（并在 `peer_receipts[]` 对应 peer 条目记 `status=timed_out`），把 incomplete 状态暴露给 audit/UI；不得静默吞没。`fanout_status` 与 per-peer `peer_receipts` 子结构定义见 `ak.schema.erasure_receipt.v1`（schema `artifacts/schemas/erasure-receipt.schema.json`）。

提交操作的幂等域固定为 `(source service, destination service, Idempotency-Key)`：同 key / 同 canonical body 必须返回首次生成的 byte-identical acknowledgement 与原 `accepted_at`；同 key / 不同 body 返回 `duplicate_conflict` 且零写入。receiver acknowledgement 的 proof 对去掉 proof 的完整 closed object 使用 `H("ak.erasure-receipt-acceptance.v1", object)`，因此发送方可以离线验证谁在何时接受了哪一个 receipt digest。

**Hash chain linkage 保留**：hard erasure 仍保留 event graph verification stub（`retained_stub_digest` 字段），供后续 verifier 校验 Event ID 的结构、Event ID 与冗余 digest 的一致性、receipt/stub binding，并连接外部仍存在的 proof、RealmCommit 与授权证据。它只保留已记录的 identity/linkage evidence；原 canonical Event bytes 已擦除后，stub 不能独立重算或证明这些 bytes 的 hash preimage。`retained_stub_digest` 的输入是 `canonical_json(retained_stub)`；`retained_stub` 使用 `ak.schema.erasure_verification_stub.v1` 结构，至少绑定 subject、scope、receipt_id、completed_at，并在适用时包含 event digest / proof `event_digest`、authority commit inclusion、redaction authorization ref 与 legal-hold ref。Stub MUST NOT 保留已擦除 plaintext 或未加盐低熵 plaintext digest；若 receipt 不内联 `retained_stub`，签发服务必须在 erasure receipt endpoint 暴露同一 canonical stub。projection / UI MUST 显示 `[erased]` 占位而不是模糊化。

### 2.7 Realm Membership FSM（normative）

`ak.member.state` 以完整 `payload.member_id: ActorId` 写入 `member_state`，状态模型为 `commit-ordered projection`，领域 membership 转移在唯一确认顺序处检查；账号分支的相等性包含 AccountId 两个分量。Realm 使用 [`common-fields.md` §4.5](./common-fields.md#45-membership-fsmnormative) 的共享 materialized membership FSM。普通 Collaboration bootstrap 的创建者 membership 仅由 §2.5 原子 unit 最后一条独立 `ak.member.state{membership="join"}` 建立；该 slot 是对应 member typed current result 的 genesis write，MUST 携带 `expected_revision null` 并进入 genesis RealmCommit。`ak.realm.create` 自身 MUST NOT 隐式写入 membership，receiver 也不得在仅收到 create 时预置本地成员。完整 unit 接受后，服务端 MAY 从该显式 slot 建立可重建 read index。same-state transition 非法；endpoint 刷新不写 membership，更换 Station 则是 old Actor leave + new Actor 的定向 invite lifecycle create/accept，其中 accept 原子执行 member `leave -> join`。

Invite 过期只推进 `invite_lifecycle`，不写共享 member typed current result。base v1 bare `knock` 的过期只影响 operation eligibility，不会由本地计时器自动改写共享 member typed current result；其清理必须由上表列出的 authorized writer 提交显式 `leave`。receiver MUST NOT 根据本地墙钟合成 reducer-derived member event。

共享表未列出的 transition MUST `failed_precondition`，reason=`invalid_membership_transition` 或更具体的 join-policy reason。`ban -> join`、`join -> join`、`leave -> leave` 等均非法；需要重试时 producer 必须基于当前 state 重新提交合法 transition。父 Realm `join -> leave/ban` 的 cascade 对 Circle membership 的影响见 [`circle.md` §9.1](./circle.md)。

上表 `leave -> join` 另有一个封闭的 Agent controller carve-out：当 writer 是 target agent 的已验证 controller、writer 自身在目标 Realm 为 active `join`、target agent lifecycle 为 `active`，且 accountability / Realm agent policy / Join Policy / MLS admission 全部通过时，controller MAY 直接写入 target agent 的 `join`。该写入不产生 invite，也不需要 agent runtime 接受；payload 的 `agent_controller_binding` MUST 钉住 controller exact authority pair 与建立当前 `join` 的 Event ID。该 carve-out 不授予 writer 通用 `ak.realm.admin`，不得用于其他 principal。

controller terminal transition 不再隐式改写 Agent canonical member typed current result。effective Agent membership 从 accepted member/controller/provision facts确定性派生；controller 不再处于 binding 所指 generation 的 active `join` 时，Agent 在同一 control view 立即无效。canonical cleanup 只接受 [`actor.md` §3.3](./actor.md) 定义的签名 cascade unit：self leave 为 controller transition + exact Agent leave set 的原子 batch；第三方紧急 ban/remove 为 terminal Event + durable exact-set cleanup intent，后续 complete-set batch 一次性写入 Agent leave。已为 `ban` 的 Agent 保持 `ban`，不得被 cleanup 降级；controller rejoin 的新 Event ID 不复活旧 Agent binding。

### 2.8 Realm 角色分类（normative）

**Account 与 Realm 的生存边界（normative）**：所有 Realm 均遵守
[`common-fields.md` §4.2 的账号隔离铁律](./common-fields.md#42-主体引用字段)。PCR 绑定完整 AccountId，
原 Station 永久停止服务时不能由另一 Station 上同 principal 的 Account 接续。Collaboration Realm
的创建者或管理员账号失效，不会把其权力赋予同 principal 的另一账号；Realm 是否能继续推进
由其已接受治理状态及已定义恢复授权决定。RealmCommit signer、恢复签名者与管理员的 account 身份比较 MUST
包含 `station_id`，历史签名验证成功不构成账号替换或当前治理授权。

schema 层只有一个 `ak.schema.realm.v1`；按 **用途** 把 Realm 分成两大类，Collaboration 再按 **成员是否跨信任域** 分两类。所有 Realm 共享同一组生命周期 event（`ak.realm.create` / `ak.realm.tombstone` / `ak.realm.destroy`）与同一套 reducer 规则；下面的分类影响的是 marker 字段、policy 字段默认值与允许的 event kind 集合。

```
Realm（ak.schema.realm.v1，schema 层统一）
├── Collaboration Realm        ← 多方业务协作（Strand / Message / Space / Morph / Relation）
│   ├── Internal Collaboration Realm   ← 仅本信任域成员
│   └── External Collaboration Realm   ← 含跨信任域成员
└── Principal Control Realm    ← 单 principal 身份基础设施流（device / session / KeyPackage / profile / consent / contact fact / DM binding）
```

#### 2.8.1 Principal Control Realm（PCR）

- 与 principal DID **1:1 绑定**，由 `principal_control_realm_id` 标识，由 DID method 的 inception 证据钉死（参见 [`identity/key-management.md` §4.1 与 §5.0](../identity/key-management.md)）。
- Genesis discriminator 与 effective projection MUST：
  - human / organization PCR create genesis `purpose = "principal_control"`；Agent PCR create genesis `purpose = "agent_control"`；Applet-managed Bot / Ghost PCR create genesis `purpose = "applet_managed_control"`（见 [`../extensions/applet-integration.md` §3.3 / §9.1](../extensions/applet-integration.md)）。三者是该 discriminator 的完整取值集合，`realm.schema.json` 与 `realm-genesis.schema.json` 的 enum 与本表逐字相等
  - `schema_refs` 包含 `ak.profile.principal_control_realm.v1`
  - PCR MUST 在任何控制内容写入之前接受自己的 `ak.mls.genesis`；该 accepted RealmCommit 把 PCR scope 不可逆激活为 standard RFC 9420。v1 不存在"明文 PCR"：激活后的明文控制内容写入 MUST fail closed。
   - `created_by` 从 create envelope 的完整 `actor_id` 派生；`governance_station_id` 明确指定 generation-0 治理 Station。RealmCommit 必须由该 generation 的治理 Station service identity 签署，并通过 service DID 的 historical method evidence 验证。
  - genesis `security_class = "high_assurance"`；effective `federation_policy ∈ {closed, restricted, quarantine}` 来自 profile/policy projection。
  - effective `history_access = "since_join"`。新 endpoint 从自己的 initial Add/Welcome admission 起读取密文，durable device-list / normalized principal view 提供必要控制 baseline，解密只使用该 endpoint 本地持有的 MLS state。
- 事件类型由 `ak.profile.principal_control_realm.v1` 的 allowlist 约束：只接受 identity resolution / device / session / KeyPackage / recovery / profile / consent / contact fact / direct conversation binding 等身份基础设施 event；普通 Message / Strand / Space / Morph / Relation / View / Call 协作 event MUST `principal_control_event_kind_forbidden`。allowlist 是**闭合**的：正文要求写入 PCR 的每个 kind MUST 出现在其中，反之亦然；`ak.identity.resolution.update`（[`../identity/identity-did.md` §4.2](../identity/identity-did.md)）与 `ak.contact.scope.update`（[`../identity/contact-and-direct-conversation.md` §3](../identity/contact-and-direct-conversation.md)）同属该 allowlist。
- Agent 作为独立 principal 使用自己的 PCR，不得复用 controller PCR id。Agent DID 与 PCR id 的绑定、controller delegation、`actor_id` / `executed_by` authoring 和 agent/controller 控制事实落点以 [`identity/key-management.md` §4.1](../identity/key-management.md) 为权威；Agent lifecycle 的 `actor_id` 必须是 exact account variant，service variant、同 principal 异 Station 的替代或 payload principal mirror 不匹配均 fail closed。realm id 本身按 §2.5.0 通则从 genesis Event 派生，**实现私有的 deterministic id 派生不是验证证据**。Profile allowlist 虽包含 Agent PCR 与 controller PCR 两组 agent-control kind，reducer 必须按 `agent_control_event_placement` 再做落点约束，不能把 allowlist 并集解释成跨 principal 通用写权限。
- 跨 principal 写入（另一个 principal 的 device / session 状态）MUST `unauthorized` reject。
- "私有"语义由 **用途 + event-kind allowlist + 外露注册表** 共同锁定，不是 access control。PCR 在结构上允许 multi-member（该 principal 的所有设备 / agent）。
- **Availability holder 的 PCR 特例是 create-locked，不是隐式 membership**：human、Agent 与 Applet-managed PCR genesis 都明确不写 `member_state`，因此首个及后续 successor RealmCommit 的 eligible holder 只从 predecessor closure 中唯一 accepted create 的、已由原始 producer proof 与 historical signer evidence 完整验证的 `station_id` 派生。该 frozen service DID 是 PCR 对 §8 AvailabilityReceipt 的唯一 holder carrier；不得把 authority-root controller、RealmCommit signer、current account row 或 session 当成 holder，也不得为满足默认 quorum 给 PCR 合成 member state。
- **外露方向同样闭合（normative）**：`realm_event_kind_policy.allowed_event_kinds` 只锁"能写什么"。允许写入的 kind 中，有一部分必须离开该 Realm 才能让协议成立——远端做设备信任重放、RealmCommit 归属判定、Contact 验证闭环与 KeyPackage claim 都需要它们。**这些外露路径 MUST 逐条登记在 [`pcr-exposure-registry.json`](../../artifacts/registry/pcr-exposure-registry.json)**，其 `event_kinds[]` 集合 MUST 与本 allowlist 逐字相等。每条 `exposures[]` 声明 carrier 形态（`exact_event` / `derived_field` / `receipt` / `authority commit` / `did_service_entry`）、surface、`operation_id` 与方向、exact `schema_ref` 与 JSON Pointer、`authorization_policy_id`，以及适用时的 `anti_enumeration_policy_id`。`exposures[]` 为空即 **PCR-private**：该 kind MUST NOT 经任何 `ak.open.*` / `ak.peer.*` / 跨 principal `ak.self.*` 面或公开 DID Document entry 到达域外。conformance vector `ak.vector.identity.pcr_outward_exposure_registry.v1` 覆盖 registry 正反向闭合与各授权分支的反枚举等价性。
- **`public` 是显式策略值，不是缺省**：缺少 `authorization_policy_id` MUST NOT 被解释为公开。新增任何承载 PCR 派生字段的对外面而未在该注册表登记，release gate MUST 红；把某个 carrier 悄悄扩大到第二个仍标记 private 的 kind 同样 MUST 红。
- **PCR 历史读取（normative）**：PCR 固定 `history_access=since_join`。新 endpoint 从自己的有效 Add/Welcome 起读取密文；控制基线由 durable device-list / normalized principal view 提供。
- **PCR 不得有 alias（normative）**：`ak.realm.alias` 同样不在 allowlist 内，PCR 只能按 `realm_id` 寻址；给身份基础设施控制流挂一个人类可读、可猜测的短地址会把 principal 的控制 Realm 公开暴露。写入 MUST `principal_control_event_kind_forbidden`。

#### 2.8.2 Collaboration Realm

承载多方业务协作。除 PCR 之外的所有 Realm 都属于这一类。

- create genesis `purpose` MUST 为 `"collaboration"` 或 `"direct_conversation"`，不得省略或藏入通用 `fields` map。
- 不引用 `ak.profile.principal_control_realm.v1`。
- 按 `federation_policy` 与实际成员构成进一步分为 Internal / External 两种。

##### Internal Collaboration Realm

- `federation_policy ∈ {closed, restricted}`，且实际成员仅来自本部署 trust domain。
- 组织主网络上的普通项目 / 团队 / 文档 / 群聊 Realm 默认属于此类。
- 不需要外部组织 authority chain 或外部 principal 验证流程。

##### External Collaboration Realm

- 含至少一个跨信任域成员（external Organization DID、external principal、跨部署 service DID）。
- `federation_policy` 通常为 `restricted`（allowlist）或 `open`；`discoverability` / `join_rule` 与 `external_federation` 由 deployment policy 决定。
- 外部主体进入 MUST 经过组织 authority chain 或 verifiable credential 验证（详细规则见 [`sync/sovereign-deployment.md` §5–§6](../sync/sovereign-deployment.md)）。

启用 `ak.profile.sovereign_deployment.v1` 的部署对 External Collaboration Realm 施加额外的强制约束（allowlist federation、独立 enclave、E2EE、deny-default applet/agent 等），规则见 [`sync/sovereign-deployment.md` §4](../sync/sovereign-deployment.md)。非 sovereign 部署下 External Collaboration Realm 仍须遵守 federation_policy / E2EE / capability 等普通 Realm 规则，但不强制 sovereign profile 的全部约束。

#### 2.8.3 关系与正交轴

- "Internal / External" 的判定轴是 **是否含跨信任域成员**，不是 hosting 在哪台 server 上：一个 Realm 由组织自己的 Station 托管，但邀请了外部 Organization DID 的成员——它就是 External Collaboration Realm。
- Sovereign deployment 对 External Collaboration Realm 加的那一组 policy 来自 `ak.profile.sovereign_deployment.v1`，是 **部署 profile** 决定的 policy 配置，不是另一种 Realm 类型。
- PCR 永远是 Internal 的，不存在 "External PCR"：principal DID 与其 control Realm 1:1 绑定，跨域 PCR 在结构上不存在。
- `security_class=high_assurance` 是横切标签，可叠加在 Internal / External Collaboration Realm 与 PCR 上，不属于本分类的一层节点。
- 这套分类是 **prose / glossary 层** 的角色术语，便于跨章节统一指代；底层 schema、reducer、RealmCommit pipeline、Event 处理对三类一视同仁。

#### 2.8.4 Direct Conversation Realm（1:1 DM）

Direct Conversation Realm 是 Collaboration Realm 的受约束形态，不是新的 Realm 类型。完整生命周期见 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md)。

Direct Conversation Realm MUST：

- 在 founding unit 之后提交该 scope 唯一的 `ak.mls.genesis`；其 accepted RealmCommit 把 Realm scope 不可逆激活为 standard RFC 9420，之后不存在明文内容写入分支。
- `schema_refs` 同时包含 `ak.schema.realm.v1` 与 `ak.profile.direct_conversation_realm.v1`，并设置 `fields.collaboration_role="direct_conversation"`；两者受 schema 双向 guard 约束。不得复用 `fields.purpose="direct_message"`，因为 `fields.purpose` 已用于 Principal Control Realm。
- `found` 且可发送时 active member count 等于 2；任一 participant 离开、被移除或其它 gate 失败时，同一稳定 DM 投影为 `suspended`，恢复时仍使用原 Realm。向 DM Realm 加第三人 MUST 被拒绝。binding 或 membership 投影不能解析为恰好两个 distinct principal participant 时，新写入 MUST fail closed，reason 为 `direct_conversation_member_count_invalid`；既有稳定会话投影为 `suspended` 而不是被替换。升级多人聊天必须创建新的普通 Realm / Strand，再用 Relation 或 Message 引用旧 DM 内容。
- `default_join_rule` 为 `closed` 或等价 fail-closed policy。**这里必须区分两件事（normative）**：（a）**bootstrap peer join**——Realm bootstrap batch 内由 creator 写入的第二个成员（pair 的另一方）是 DM Realm 成立的必要步骤，MUST 被接受；它走 authorized-writer 分支（creator 在同批 genesis unit 内使用 staged authority-root proof 取得的 effective `ak.realm.owner`，见 [§2.5](#25-akrealmcreate-reducer-bootstrapnormative)），属于 [`../governance/join-policy.md` §4](../governance/join-policy.md) `closed` 行的封闭豁免列表第 3 项。（b）**向已 active 的 DM Realm 加第三人**——任何第三方 invite / member_add MUST 以 `direct_conversation_invite_forbidden` 被拒绝。实现 MUST NOT 把（a）当成（b）拒掉，否则 1:1 私聊永远只有 1 个成员，违反“active member count 等于 2”。
- `ak.space.*` Event MUST 以 `direct_conversation_space_forbidden` 拒绝；额外普通 Strand MAY 存在，但不改变 binding 指定的默认 main Strand。
- 通过一次性 principal-scoped `ak.direct_conversation.bound` fact 绑定 unordered participant pair、`realm_id` 与 `main_strand_id`。同一 `(trust_domain,pair_key)` 只有一组永久坐标，且由 founder 一次 author 的四 Event atomic unit 自身派生（见 [`../identity/contact-and-direct-conversation.md` §5.5](../identity/contact-and-direct-conversation.md)）；不存在服务端预分配 ID、reserved/materializing draft、第二候选或 winner tie-break。
- DM Realm 继续只有一个技术 authority-root controller，但 root 的 operational owner aggregate MUST 与 `ak.profile.direct_conversation_realm.v1` 的 phase mask 求交。founding 之外的普通消息、成员、policy、grant 与 terminal 写不得借 owner 绕过；双方日常写统一从 `ak.authority.direct_conversation_participant.v1` 求值。
- participant authority 只在 immutable binding、恰好两个 stable participant、actor active membership、conversation 未 suspended、Realm/Strand/MLS cross-binding、非终态 scope 与 action-specific gate 同时成立时生效。membership、`created_by`、role/projection mirror 与相同 `pair_key` 都不是其替代来源；authority reset 不使 baseline 失效。
- 基数是同一 trust domain/pair 的 `0..1` stable binding，且一旦 accepted，该 pair 永久复用同一个 Realm 与 main Strand。suspended、rejoin、rekey、恢复或 erasure 都不创建 successor；结果不明的创建只能由 founder 重放逐字节相同的 signed unit，不得重新 author 另一组 Event。

任一参与方主动离开或被移出 DM Realm 后，同一 immutable binding 立即投影为 `suspended`，双方 participant authority 失效，不需要也不得写 retirement fact。后续 `ak.self.direct_conversation.read.resolve.v1` MUST 返回同一 `pair_key`、Realm 与 main Strand；只有恢复所需 authorization basis 后，才可在同一 Realm 执行标准 rejoin/rekey 并恢复为 `found`。resolve 是查询入口，MUST NOT 承载 `create` phase；DM Realm 的唯一创建入口是 [`../identity/contact-and-direct-conversation.md` §5.4](../identity/contact-and-direct-conversation.md) 的 founder-only founding admission。实现不得创建 successor、predecessor-linked binding、竞争 Realm 或历史 segment；客户端只能解密其本地仍持有对应 MLS state/material 的密文。

## 3. Space

### 3.1 概念

Space 是用户和产品层可见的结构容器。它可以表达：

- organization 下的 workspace / project / folder / section
- board / list / swimlane / calendar bucket
- document outline group / page group
- 任意 profile 注册的结构节点

Space **不**拥有自己的 membership、policy、history visibility、E2EE group 或 federation policy。Space metadata 及 canonical parent / placement 结构子资源 MUST 使用同一个实际 `realm_id`。Circle、对象 scope 和 capability 仍独立验证。跨 Realm 内容仅通过显式 View / 普通引用聚合。

### 3.2 Schema id 与字段

Schema id: `ak.schema.space.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `ak:space:` 开头。 | Space ID。 |
| `schema` | yes | `ak.schema.space.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | MUST 指向 `ak:realm:`。 | Space metadata 的 home Realm。 |
| `scope_circle_id` | no | `id:circle` | MUST 指向 Space metadata home Realm 的 Circle。 | Space 自身 metadata 与 structural relation facts 的 effective scope；省略表示 Realm-default。 |
| `child_scope_policy` | no | `object` | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id`。 | 子资源 placement 的 reducer-enforced 约束。 |
| `parent_space_id` | no | `id:space` | MUST 指向同一实际 Realm 的 Space；不级联权限。 | 结构层级父。 |
| `kind` | yes | `string` | v1 标准 kind 包括 `space`、`project`、`folder`、`board`、`list`；profile 可注册新 kind。 | Space 类型。 |
| `rank` | no | `string` | 见 `encoding.md` §9。 | 在 parent 内的位置。MUST 出现在 Space 顶层，**不**得作为 `fields.rank` 嵌套字段（与 [`relation.md` §2](./relation.md) 对 Relation 的相同约束对齐；wire 上 `fields.rank` MUST 被拒绝为 `schema_violation`，详见 [`artifacts/registry/forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。 |
| `schema_refs` | no | `array<string>` | 可选 schema/profile 引用。 | 约束本 Space 容纳的资源类型 / fields。 |
| `title` | yes | `string` | 1..256 chars。 | 显示名。 |
| `summary` | no | `string` | <= 2048 chars。 | 简短说明。 |
| `labels` | no | `array<string>` |  | 用户/系统标签。 |
| `fields` | no | `object` | kind-specific 字段。 | 扩展字段。 |
| `avatar_blob_ref` | no | `id:blob` |  | Space 图标。 |
| `state` | no | `enum(active, archived, tombstoned)` | 默认 `active`。 | Space 生命周期状态。 |
| `state_changed_at` | no | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `ActorId` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `ActorId` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

Space 是 v1 标准协作容器中唯一把顶层 `kind` 用作产品 / 容器子类型的对象：`board`、`list`、`folder` 等都在 Space.kind 表达。Realm 不按 kind 分裂安全边界；Strand 的业务分类也不放顶层 kind，必须通过 schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 表达。View.kind 是投影响应族，不表示协作容器类型。

### 3.3 行为规则

- **授权**：任何对 Space 的写入（`ak.space.create` / `ak.space.update` / `ak.space.archive` / `ak.space.restore` / `ak.space.tombstone` / `ak.space.parent`）都在 `realm_id` 指向的 home Realm 内授权。
- **同步与联邦**：Space metadata 跟随 home Realm 同步。parent 与 child MUST 属于同一 authority-committed Realm state；Circle 裁剪不等于依赖不存在。
- **加密 / scope**：Space 没有自己的 membership 或 MLS group。Space metadata 默认落在 home Realm 的 scope，并跟随该 scope 当前的 MLS 激活状态；若 `scope_circle_id` 指向 Circle，则 Space metadata 与对应 structural relation facts 落在该 Circle 的 existing scope，并继承该 Circle 的投递 / 查询裁剪与该 Circle 自己的 MLS 激活状态。
- **导航**：Space hierarchy 是产品结构树 / DAG。遍历每个 Space 节点时 MUST 独立校验该节点 home Realm 的可见性。
- **默认资源边界**：创建 Strand / Morph / View / Blob 引用等资源时，客户端 MUST 显式写入 `realm_id` 与需要的 `scope_circle_id`；新资源 MUST 使用当前 Space 的 `realm_id`；scope MUST 在该 Realm 中独立授权。
- **子边界升级**：若 Space subtree 或单个 Strand 只需要 Realm 内的子事件 / 子消息边界，创建 Circle，并让子资源显式写入 `scope_circle_id`，必要时用 `child_scope_policy` 强制指向该 Circle；若还需要密码学隔离，则该 Circle 必须 MLS-backed。只有需要独立 federation 或 capability registry 时才创建新的 Realm。

Space 自身 `scope_circle_id` 与子资源 `child_scope_policy` 的区别及 reducer 责任以
[`circle.md` §6.3](./circle.md) 为唯一规范来源；二者不可互相替代。

### 3.4 Lifecycle 与 Cascade 规则

Space lifecycle 只影响结构容器，不影响 Realm membership、E2EE group 或 history visibility。

- `ak.space.archive`：把 Space 设为 `archived`，默认 UI 隐藏；不自动 archive child Space 或内部 Strand。
- `ak.space.restore`：仅允许 `archived -> active`；不级联 restore。
- `ak.space.tombstone`：不可逆；在它自己签名的 accepted RealmCommit basis 中存在 non-tombstoned child Space 或 non-redacted Strand 的有效 canonical `contains` placement 时 MUST `failed_precondition / space_has_live_dependents`。archived 子项仍是依赖；tombstoned child 的历史 parent typed current result 和 redacted Strand 的历史 position 不算活依赖。必须先显式移出或终结已观察到的子项，禁止隐式级联或清空 canonical typed results。
- 上述准入检查 MUST 使用指定 accepted RealmCommit basis 的完整 canonical parent / position / lifecycle 状态；可见列表、Circle 裁剪、缓存未命中、unresolved typed current result 均不能证明无依赖。缺少完整可验证状态时 MUST fail closed。
- v1 不为 Space lifecycle 与所有可能指向它的 parent/position typed current result 新建跨 typed current result 事务或全 Realm dependency-lock。普通 reparent/placement Event 可能在尚未知道目标 Space tombstone 时合法创作；两条 canonical Event/typed current result 历史事实都保留，但派生结构边只有在当前 confirmed lifecycle 非 `tombstoned` 时才有效。目标已 tombstoned 时，该 parent/position 不得形成 `contains`、不得把目标复活、不得被投影成 root，也不得授予导航或写入能力；客户端/服务端必须把它显示为待显式 reparent/move 的不可用结构引用。后续修复写使用原 parent/position typed current result 的唯一 current source。该规则由已确认安全状态与普通因果状态共同唯一决定，与接收顺序无关，也不新增 recovery Event。

错误码 MUST 使用 `space_not_active`、`space_not_archived`、`space_has_live_dependents`、`space_already_terminal`。

### 3.5 `ak.space.parent` 因果父边

`space_parent` 是已登记的 typed current result family（[`current-result-registry.json`](../../artifacts/registry/current-result-registry.json) 行，result schema 见 [`typed-current-result.schema.json#/$defs/space_parent_result`](../../artifacts/schemas/typed-current-result.schema.json)）。它以 SpaceId 为 subject，special form 渲染为 `space_parent:<space_id>`，使用普通 `current-value projection`。

值是**单成员对象** `{"parent_space_id": <SpaceId> | null}`，成员可空，**值本身永不是裸 null**。这一点是规范性的，有两条独立理由：一是「只有成员才能缺失」（与 `realm_set_default_strand` 同一论证）；二是本 family 自己的 compare-and-set 是**对已存字段的谓词**，裸 null 没有字段可比，`expected_parent_space_id` 就无法表达。成员取 null 表示 root，即没有结构父。

写入方由 `result_writes[]` 唯一给定，共两条 Event kind：

- `ak.space.create.result_writes[]` 用两条互斥条件写覆盖 genesis：签名 `object.parent_space_id` **存在**时取该字段，**缺席**时把成员显式写成 null。因此每个 Space 从它的第一条 Event 起就有该寄存器，后续写入不可能把「寄存器缺失」误读成 root。Space 对象用**字段缺席**表达无父，本 family 的 payload 用**显式 null** 表达，归一化只发生在这一处。
- `ak.space.parent.result_writes[]` 是唯一的后续写入路径，且**无条件**：`space_parent_payload.parent_space_id` 是必填且可空的，脱离到 root 是显式 null 而不是省略成员，所以一条写就覆盖全部情形。

metadata 投影排除 `parent_space_id`，所以真源是本 family 而不是 Space 对象；通用 metadata patch 禁止触及该路径，这条禁令在 [`reducer-managed-path-registry.json`](../../artifacts/registry/reducer-managed-path-registry.json) 里以 `owner_kind: result_family` / `owner: space_parent` 登记，指向的正是上面两条写。普通父边变更不需要新 RealmCommit。

`expected_parent_space_id` 是**必填的前态声明**，不是可选 CAS。它在 `space_parent_payload.required` 里，并登记为 `ak.space.parent.pre_state_requirements[]` 的一条 `stored_field_equals_payload` 谓词：reducer 在提交位置读该 Space 冻结前态的 `parent_space_id` 成员，与该字段逐字节比较，不等即 `failed_precondition / space_parent_mismatch` 且**零写入**。这与 `agent_deactivate_payload.previous_status`、`invite_*` 的 `previous_state` 是同一个惯用法：**每一条 state-changing Event 都在 payload 里声明它读到的前态**。因此本 kind 没有「不做并发保护」的分支，实现 MUST NOT 提供一个省略该字段的旁路——省略在 wire 上就是 `schema_violation`。

这里用两值相等谓词 `stored_field_equals_payload` 而不是三值的 `stored_field_matches_payload`：双方**永远都在**（payload 成员必填，寄存器由 genesis 写保证存在），所以「双方都缺失」不是一个可达状态，用三值谓词只会引入一条无法触发的分支。

写入在该基底内验证存在性、同 Realm、可读 scope、自指及无环；缺证明 pending，不以本地当前图替换基底。不可读 parent 对外返回既有 `space_parent_unreadable`，已验证跨 Realm 返回 `space_realm_mismatch`，成环返回既有 `space_parent_cycle`。

先取每个 Space 的当前 parent——该 stream 上最后一个被接受的 parent 写入，次序只由 `stream_position` 给出；再将有向环内的所有 current parent 边标记为领域 `unresolved`。该环诊断不得反向重选寄存器值，不得伪装 root，也不得产生有效 contains。后续有权写引用各自 current source 后可修复。指向不可见、终态或不兼容 scope 的目标不产生 live navigation，但保留原始因果事实。

parent 只是导航关系，不授予读取权，不修改 `scope_circle_id`、Realm、creator 或安全 policy。普通对象 archive/restore 的写权限来自独立安全授权；restore 不能要求对象先 active。terminal 仍不可逆，不能通过 reparent 复活。

### 3.6 Strand 位置

Strand 在 board/list 类 Space 中的位置由普通 typed current 当前值维护：

```text
result_id     := strand_position:<board_space_id>:<strand_id>
domain reducer := current-value projection
execution   := data
value shape := { "list_space_id": id:space, "rank": string } | null
```

该 family 的 registry `result_selector.kind` 固定为 `typed_pair`，两个有序分量依次为
`id:space(payload.board_space_id)` 与 `id:strand(payload.strand_id)`。因此上式是可逆的
canonical wire 编码，不适用 `tuple/composite` 的 SHA-256 subject；producer、reducer、Current
publisher 与 selector validator MUST 从同一 registry row 得到完全相同的 typed current result id。解析时必须同时
验证 Board 与 Strand 两个 typed-ID 分量，不能只截取末尾 Strand，也不能接受 hash subject。

`ak.strand.move` / `ak.strand.reorder` 的执行类别为普通数据。`expected_position` 是**可选的显式 compare-and-set 前置**：存在时 MUST 与该 position typed current result 的当前值逐字节相等，不等即 `failed_precondition` 且零写入；缺席时该次移动不做并发保护，MUST NOT 被实现补成隐式 CAS。该 position typed current result 的当前值就是**该 stream 上最后一个被接受的位置写入**，次序只由治理 Station 给出的 `stream_position` 决定；实现 MUST NOT 依据任何客户端可见的深度、HLC、`created_at` 或到达顺序另选 winner。多个并发位置写因此被 Station 串行化为该 stream 上的一串位置，不产生需要人工合并的第二个 UI “冲突列”；被 CAS 拒绝的写没有任何业务效果，客户端重读当前值后重新签发再试。WIP 容量在同一当前值上计算，不得按到达顺序撤销某一已接受的合法写来伪装硬容量保证。

`ak.strand.move` payload 是 closed object（未知字段 MUST `schema_violation`）：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `board_space_id` | yes | `id:space`（Board） | position edge 的所属 Board；与 `strand_id` 共同构成去重 key。 |
| `strand_id` | yes | `id:strand` | 被移动的 Strand。 |
| `from_space_id` | no | `id:space`（List） | 源 List；省略时 reducer 从该 position typed current result 的当前值推导。 |
| `target_space_id` | yes | `id:space`（List） | 移动后的目标 List；payload 不得另带 `list_space_id`。 |
| `rank` | yes | `string` | 目标 List 内 canonical rank。 |
| `expected_position` | no | `object{space_id?: id:space, rank?: string, relation_id?: id:relation}` | 可选 CAS 诊断前像；字段集封闭。 |

Strand / Morph / Space 的 create payload 均不定义 `initial_relations`。Strand 创建后若要首次放置到 Board/List，producer MUST 在 create receipt 确认 event-derived `strand_id` 后单独提交 `ak.strand.move`；首次 Event 的 position typed current result 前像是不存在 / `null`，payload 省略 `from_space_id` 与 `expected_position`，并与后续 Event 使用相同的独立授权、可选 CAS 前置与 WIP 后像判定。create 成功而 Event 失败时，已创建的未定位 Strand 仍是合法状态；修正后只重试 Event，不得重建或撤销 Strand。派生 `contains` 仍只由当前 position typed current result 投影，不得合成 canonical Relation Event。

Board、List 与 Strand 的实际 `realm_id` MUST 相同；创建、首次 move、后续 move 和 reorder 均无 profile 例外。已可验证的跨 Realm placement MUST `failed_precondition / space_realm_mismatch`；普通 move / reparent MUST NOT 修改 Realm。 跨 Realm 展示可以通过 Relation / View 聚合完成，但不得把目标 Realm 的读权隐式带入源 Realm。

Board 或目标 List 的 lifecycle 在写入签名 basis 下已是 `tombstoned` 时，首次 move、后续 move 与 reorder MUST 以既有 `failed_precondition / space_not_active` 拒绝。合流后得知目标已 tombstoned 时，按 §3.4 的 joined-view gate 保留 position typed current result 但不派生有效 placement/contains 边，直到显式 move；不得静默改到 root、清除 typed current result 或用到达顺序选择 tombstone 与 placement 的赢家。

### 3.7 示例

Project Space：

```json schema=schemas/space.schema.json
{
  "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
  "schema": "ak.schema.space.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "kind": "project",
  "title": "Website Redesign",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

Confidential sibling Space：

```json schema=schemas/space.schema.json
{
  "id": "ak:space:AScD0xd0vWSGWhC2n9BZHco7N_jYnNgmEIifpAo_uxUJ",
  "schema": "ak.schema.space.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "parent_space_id": "ak:space:AUwbeCUMZI_GuEADljowhvFwzl6wIkaSiCDhu2oaOqTg",
  "kind": "project",
  "title": "Pricing Strategy",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

## 4. Group 与 Capability 的位置

Group 不是资源容器，也不是安全边界。Group 是 principal / actor 的集合，可作为 capability grant subject、join policy 条件或组织角色投影。

规范性区分：

- Realm membership 决定能否接收 Realm event、参与 Realm MLS group、获得 Realm 历史资格。
- Capability 决定在 Realm 内能否执行动作，例如发消息、改 Strand、移动 Strand、管理 Space、邀请成员。
- Group 只是授权主体集合；把 Group 授予 capability 不等于把 Group 加入 Realm。若 Group 被授予 Realm membership，必须物化为每个成员的 Realm membership / MLS add 路径。

同一 Realm 中已经具备 MLS key 的成员，不能仅靠撤销 capability 来实现强读隔离。强读隔离必须切 Realm。

## 5. 通用对象 ID 规则

完整 ID 列表与 ID kind registry 见 [common-fields.md](./common-fields.md) §6。Realm / Space 相关：

- `ak:realm:<44-char-event-token>`
- `ak:space:<44-char-event-token>`

## 6. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Space hierarchy：[`space-hierarchy.md`](./space-hierarchy.md)。
- Realm links：[`realm-links.md`](./realm-links.md)。
- Strand / Message / track 语义：[strand-and-message.md](./strand-and-message.md)。
- Relation 基数与跨 Realm 规则：[relation.md](./relation.md)。
- authority-commit projection：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- `ak.strand.move` / current-value projection sync 编译：[`../sync/operations-sync.md`](../sync/operations-sync.md)。
- Realm genesis/profile/effective projection 与 Space schema：`artifacts/schemas/realm-genesis.schema.json`、`artifacts/schemas/realm-profile.schema.json`、`artifacts/schemas/realm.schema.json`、`artifacts/schemas/space.schema.json`。


### Space lifecycle 合同入口

`space` 的 lifecycle 以 contract registry 中对应 typed current result family 的 `transition_contracts` 与 Event `result_projection` 为转换真源；本节只定义对象组合规则，不复制转换表。archive 只从 active、restore 只从 archived 发起；非法源分别返回 `space_not_active` / `space_not_archived`；终态操作对已终态对象返回 `space_already_terminal`。新的 same-state 写入不当作幂等成功，已接受 Event 的 exact replay 仍沿通用幂等合同处理。普通 update 只允许 active，不能隐式恢复对象。对象 redaction/terminal 优先于可逆 archive，restore 不能恢复已清除内容。缺对象或依赖时按 common-fields §5.1 保留 pending/replay。
