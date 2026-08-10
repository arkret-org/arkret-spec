---
title: Realm & Space
status: candidate
normative: true
stability: v1
updated: 2026-07-13
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
- Policy Server
- event frontier / Seal pipeline

`Realm` 的语义接近“保护域”或“治理域”，不是“项目文件夹”。一个组织通常会拥有多个 Realm：公开项目、普通内部项目、机密项目、HR 项目、法务项目可以位于同一 Organization / Space tree 下，但落到不同 Realm。

`security_class=high_assurance` 是 Realm 的可选标签，进一步收紧 federation policy 与默认审计 / E2EE 选项。

### 2.2 Realm 与 MLS group

Realm 与 MLS group 不是同义词：

- 非 E2EE Realm 可以没有 MLS group。
- E2EE Realm 通常拥有一个 primary MLS group。
- Realm 还包含 policy、membership、history、sync frontier、federation、retention 和 capability 等语义；MLS group 只承载加密成员、epoch 和密钥演进。
- 实现把 Realm 内的子事件 / 子消息边界形式化为一等对象 [Circle](./circle.md)（`ak:circle:`）：独立 membership、独立 history visibility、独立投递 / 查询 / projection 裁剪，且 `Circle.members ⊆ Realm.members`；当父 Realm 或 policy 要求 E2EE 时，Circle 还必须拥有独立 MLS group。federation identity / Policy Server / capability registry 仍在父 Realm。

规范性规则：

- `encryption_profile` 是 Realm 的 create-locked 基线。
- 同一 Realm 内不允许把普通 Strand 任意混合成"有的 E2EE、有的非 E2EE"的保密等级拼盘；加密覆盖范围由 Realm `content_encryption_floor` 与 `metadata_encryption_floor` 声明（二者均为 Realm 对象顶层的 policy 字段，权威定义见 §2.3 字段表），Circle 不得放宽父 Realm floor（详见 [`circle.md` §7](./circle.md)）。
- Realm policy component `agent_participation` 声明 native personal agent 的治理 ceiling，shape 固定为 closed required 五位 `{native_agent:{reply_message,reaction_add,reaction_remove,accept_third_party_mention,act_on_behalf}}`，由 `ak.realm.admin` 经 `ak.realm.policy_bundle` 写入。target-local deployment safety、Realm、Circle、Strand 构成逐位 AND 收紧链；component 存在时不得缺位，inner true 必须蕴含 parent true，unknown/stale/fork 全 deny。实际动作还必须与 Account Authority 当前 controller selection 求交，并独立通过 capability、session、membership 与 lifecycle；policy 本身不授予 action。native Agent 与 Applet/Ghost 策略分离。详见 [`common-fields.md` §4.4](./common-fields.md#44-agent_participation-wire-形态normative)。
- Realm policy component `account_deactivation` 声明：当某 principal 进入 account `deactivated` 时，其在本 Realm 的 membership 如何处置。其子字段 `account_deactivation.member_action` 是封闭枚举（`leave_self_initiated`（默认）/ `retain_membership` / `leave_all`），同样由持有 `ak.realm.admin` 的 principal 经 `ak.realm.policy_bundle` 写入，未识别取值按未知 policy 字段 fail closed。**该字段的封闭枚举与处置语义的单一权威源是 [`../identity/account-lifecycle.md` §7.1](../identity/account-lifecycle.md)**；本处仅登记它属于 Realm policy component（经 `ak.realm.policy_bundle` 承载、随 `policy_revision` 推进），不重复定义取值。
- 若某个 Strand / artifact 需要 Realm 内的子事件 / 子消息边界（子集成员、独立 history、投递 / 查询裁剪，必要时独立 MLS group），创建一个 [Circle](./circle.md) 并把对象的 `scope_circle_id` 指向该 Circle。仅当跨 federation/policy/capability registry 边界时才升级到另一个独立 Realm，并通过 `ak.realm.link` 显式引用连接。
- `history_visibility` 的五个值只定义历史读取资格；是否能发现 Realm、能否加入、是否能解密旧 E2EE epoch、以及服务是否可接收明文，分别由 discoverability、join rule、history sharing policy / key share、`plaintext_visible_services` 决定。完整语义见 [`../governance/history-visibility.md`](../governance/history-visibility.md)。

Realm policy component `availability_policy` 声明 Control Move、snapshot 与 backfill bytes 的签名持有者门槛；`audit_policy` 声明 range-completeness / transparency witness 白名单、最小 attestation 份数与独立性。二者均经 `ak.realm.policy_bundle` 写入并进入 `policy_root`，结构以登记的 `realm_policy_bundle_payload` 为机器真源；实现不得用未登记的 profile-local 隐式集合替代。

**bundle 组件集合边界（normative）**：`ak.realm.policy_bundle` 是**闭合对象**（[`event-payload.schema.json#/$defs/realm_policy_bundle_payload`](../../artifacts/schemas/event-payload.schema.json)，`additionalProperties: false`），承载且仅承载**没有独立 facet event kind** 的 Realm policy 组件：`policy_revision`、`content_scheme`、`content_encryption_floor`、`metadata_encryption_floor`、`federation_policy`、`aad_visibility`、`durability_policy`、`mls_send_pause`、`relaxed_window_max_ms`、`media_service_decrypts`、`join_policy`、`agent_participation`、`account_deactivation`、`availability_policy`、`audit_policy`、`preauth`、`allowed_third_party_invite_verification_service_ids`。已经拥有自己 event kind 与 cell 的组件（`ak.realm.join_rule` / `ak.realm.history_visibility` / `ak.realm.discovery` / `ak.realm.read_receipt_policy` / `ak.realm.asset_privacy_policy` / `ak.realm.delivery_binding_policy` / `ak.realm.moderation_policy` / `ak.realm.media_service` / `ak.realm.plaintext_visible_services` / `ak.realm.disappearing_policy` / ...）MUST 走各自的 facet event，MUST NOT 在 bundle payload 内回显或再声明一次 "active set"。全部 policy cell 继续进入普通 policy state/frontier；MLS `security_frontier_digest` 只按 [`../crypto-media/encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md) 的机器 registry 投影真正改变 key access 的字段，不能用 `ak.component.realm.*policy*` 通配过滤。未登记字段在 wire 解析阶段即 `schema_violation`。

`federation_policy` 与 `allowed_third_party_invite_verification_service_ids` 都由 policy bundle 唯一承载。前者是 whole-value federation posture；`security_class=high_assurance` 时每个 bundle revision MUST 显式携带 `closed` / `restricted` / `quarantine` 之一，`open` 或省略都必须拒绝。后者是第三方邀请验证服务信任根的全量替换集合：每个 bundle revision 都声明当前完整集合，而不是增量 add/remove；省略与空数组都表示拒绝所有第三方验证服务。删除某个 DID 只需在更高 `policy_revision` 的集合中省略它，不存在独立 tombstone。组件随整个 bundle 写入 `ak.component.realm.policy_bundle.v1`，因此已机械进入 `policy_root`，不得另造第二个 leaf 或 active-set 摘要。授权 action 仍是 `ak.realm.policy_bundle`；`ak.invite.claim` 必须从其 CBA basis 上当前 accepted bundle cell 读取该集合，并按 Realm `revocation_freshness_window_ms` fail closed 地复校验。

### 2.3 Schema id 与字段

Schema id: `ak.schema.realm.v1`

> Materialized Realm 上以 **reducer 派生** 标注的字段（`policy_id` / `default_discoverability` / `default_join_rule` / `history_visibility` / `content_scheme` / `federation_policy` 等）只是当前态快照。写入路径必须使用对应 per-facet state event（`ak.realm.policy` / `ak.realm.join_rule` / `ak.realm.history_visibility` / `ak.realm.discovery` / `ak.realm.policy_bundle` / ...），不得直接 PATCH Realm 对象更新这些字段。`trust_domain` 与 `encryption_profile` 在 create event 时锁定，后续不可变。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:realm` | 以 `ak:realm:` 开头。 | Realm ID。 |
| `schema` | yes | `ak.schema.realm.v1` | 固定。 | 对象 schema。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称；产品 UI MAY 隐藏或弱化它。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `security_class` | no | `enum(standard, high_assurance)` | 默认 `standard`。`high_assurance` MUST 满足 `federation_policy ∈ {closed, restricted, quarantine}`。 | 安全等级标签。 |
| `trust_domain` | yes | `id:trust_domain` | create-locked；必须匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context。 | 跨 deployment replay boundary。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal；仅是 create/update 中的声明或投影，已验证归属必须有 active `ak.realm.organization`。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 `ak.schema.realm.v1`。 | 启用 schema / profile。 |
| `relation_profiles` | no | `array<RelationProfile>` | 同一 `(relation_kind, from_kind, to_kind, scope)` 至多一个 active profile。 | Relation 基数、去重和冲突规则。 |
| `policy_id` | no | `id:policy` | reducer 派生。 | 当前 Realm access policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | reducer 派生。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | reducer 派生。 | 默认加入规则。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | reducer 派生。`world_readable` / `shared` / `invited` 在 MLS-backed Realm 上要求 effective `content_scheme=mls_exporter_aead_v1`；`mls_rfc9420` 只能与 `joined` / `restricted` 同用。 | 历史可见性。 |
| `reducer_profile` | yes | `ak.reducer.*.vN` | genesis 写入 singleton control cell；只允许 `ak.realm.upgrade` 修改。 | 当前 Realm 共识 reducer。 |
| `preview_policy_id` | no | `id:policy` | reducer 派生或投影字段；canonical 写入路径为 `ak.realm.preview_policy`。 | 加入前 / token-scoped preview 的 policy 引用或摘要。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420, external)` | create-locked 的**能力轴**：只声明加密**机制**(有没有 MLS group)，不声明哪些 Arkret 字段进入密文，也不是"内容是否加密"的开关。`none` 是 bridge / 公开广播等"结构上永不 E2EE"scope 的诚实 opt-out；将来可能加密的协作 Realm SHOULD 以 `mls_rfc9420` + `content_encryption_floor=allow_plaintext` 创建，以便后期原地启用加密。完整语义见 [`circle.md` §7](./circle.md)。 | 加密机制声明。 |
| `content_scheme` | no | `enum(mls_rfc9420, mls_exporter_aead_v1)` | reducer 派生（Realm policy 字段，经 `ak.realm.policy_bundle` 写入并纳入 MLS `security_frontier_digest`）。仅当 `encryption_profile=mls_rfc9420` 时适用；缺省为 `mls_rfc9420`。`mls_rfc9420` 使用 MLS PrivateMessage，join 前历史不可被后加入者解密，故只能配 `history_visibility=joined` / `restricted`；`mls_exporter_aead_v1` 使用 per-epoch `history_secret`，可在 history sharing policy 授权下经 `ak.realm_key.share` 交付，但不自动打开 pre-join delivery。切换只对后续 epoch 生效，完整语义见 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.10。 | MLS-backed content envelope scheme。 |
| `content_encryption_floor` | no | `enum(allow_plaintext, e2ee_required)` | reducer 派生（Realm policy 字段，经 Realm policy facet event 写入，非直接 PATCH）。这是 Realm 真正的"内容加密开关"：`e2ee_required` 时 Strand / Message / Morph / Blob content 的 `effective_scope` MUST 为 MLS-backed，plaintext content reducer MUST `failed_precondition`（reason=`content_encryption_floor_violation`）。缺省 `allow_plaintext`。**单向 ratchet**：一旦 effective 值达到 `e2ee_required`，后续降回 `allow_plaintext` 的写入 MUST `failed_precondition`（reason=`content_encryption_floor_downgrade`）。完整语义见 [`circle.md` §7](./circle.md)。 | Realm 级 content 加密下限。 |
| `metadata_encryption_floor` | no | `enum(allow_plaintext, e2ee_required)` | reducer 派生（Realm policy 字段，经 Realm policy facet event 写入，非直接 PATCH），与 `content_encryption_floor` 对称。比较序 `allow_plaintext < e2ee_required`；effective 值取父 Realm / Circle / 对象 profile 的最大值，低于 effective 的写入 MUST `failed_precondition`（reason=`metadata_encryption_floor_violation`），MUST NOT 被 Circle 或对象 profile 放宽。**单向 ratchet**：一旦 effective 值达到 `e2ee_required`，后续降回 `allow_plaintext` 的写入 MUST `failed_precondition`（reason=`metadata_encryption_floor_downgrade`）。缺省：`mls_rfc9420` 或 `content_encryption_floor=e2ee_required` 的 Realm 为 `e2ee_required`，否则 `allow_plaintext`。完整语义见 [`circle.md` §7](./circle.md)。 | Realm 级 metadata 加密下限。 |
| `durability_policy` | no | `object` | reducer 派生（Realm policy 字段，经 `ak.realm.policy_bundle` 写入，非直接 PATCH）。仅当 `content_scheme=mls_exporter_aead_v1` 时 `mode != none` 才有效（见 §2.3.1）。 | Realm 恢复密钥（RRK）持久化策略。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | reducer 派生。 | 联邦策略。 |
| `sync_endpoints` | no | `array<ServiceBinding>` | Realm-level shared notary / Sync Service / mirror / federation 服务绑定；不是成员级 delivery binding。详见 [`../sync/federation.md`](../sync/federation.md)。 | Realm 委托同步与联邦入口。 |
| `notary_profile` | yes | `enum(single_did, threshold, open_set, mixed)` | create-locked。 | Seal finality profile。 |
| `digest_algorithm` | no | `enum(digest-suite-registry active ids；v1: sha256, blake3)` | create 时锁定，唯一例外是 `ak.realm.digest_suite_transition`（默认 `sha256`）。 | Digest suite（canonicalization × hash 注册元组，见 [`encoding.md` §3.1–§3.3](../conformance/encoding.md)）：裸 id = canonical JSON 归一化，点分 id（如 reserved 的 `cbor.sha256`）= 备用归一化编码 suite。Realm 内单一 suite 排他；切换走控制面 suite transition Seal（[`event-auth-state-resolution.md` §9.3.2](../authz/event-auth-state-resolution.md)）。 |
| `notary` | yes | `object` | Genesis notary control cell 初值；其 `kind` MUST 与 `notary_profile` 同源并满足对应 profile 的条件必填子字段。discriminator `kind` 的取值与 `notary_profile` 枚举同源：`single_did` / `threshold` / `open_set` / `mixed`；create wire schema 以 `realm-genesis.schema.json` 为准。 | 当前 Seal 签发规则。 |
| `capability_action_registry_digest` | yes | `string` | create-locked。`sha256:<64 hex>`，绑定 receiver 可取得且 JCS 重算一致的完整 `capability-action-registry.json` snapshot。reducer 原样复制进 authority-root cell（§2.5 步骤 6），MUST NOT 用本机 embedded registry 推断；后续变更只能走 root-control basis update。 | Realm authority root 的 capability registry basis。 |
| `availability_policy` | no | `object` | reducer 派生，经 `ak.realm.policy_bundle` 写入；缺省为 1 个 notary holder，仅约束 Seal include。 | bytes availability receipt 门槛。 |
| `audit_policy` | no | `object` | reducer 派生，经 `ak.realm.policy_bundle` 写入；缺省时不得采信 range-completeness / transparency witness attestation。 | completeness / transparency witness policy。 |
| `revocation_freshness_window_ms` | no | `integer` | 默认 24h；用于 DataEvent `seal_ref` 和 Control Move `seal_basis` 的撤销新鲜度判定。高风险写入 MAY 按 [`capabilities.md` §18.2](../authz/capabilities.md) 要求更短窗口。 | CBA 授权基准 freshness 上限。 |
| `recovery_witness_freshness_window_ms` | no | `integer` | 默认 24h，最大 7d；按签名覆盖的 `Seal.sealed_at` DAG 时间差计算。 | conflict-recovery witness freshness 上限。 |
| `max_authority_lifetime_ms` | no | `integer` | 默认 24h；用于 [`capabilities.md` §10.1](../authz/capabilities.md) 无限期 parent grant 首次转授时冻结 `authority_expiry_seal`。effective 值取 Realm 字段与任何 grant / policy / deployment / profile 更短窗口的最小值。 | 委托防滚动续期窗口。 |
| `bottom_escalation_after_ms` | no | `integer` | cell `⊥` 持续超过该窗口后，reducer / Projection SHOULD 标记 `escalated_at` 并触发带外告警；详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。 | bottom 诊断升级窗口。 |
| `cell_lattices` | no | `array<CellLattice>` | `CellLattice` 结构（cell family / lattice / bottom 等）定义见 [`../authz/event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md)。 | Realm-specific 扩展 cell family。 |
| `retention_policy_id` | no | `id:policy` | Realm 级 retention 的**唯一**协议承载：指向 `policy_kind="retention"` 的 Policy 对象（经 `ak.policy.set` 写入）。retention TTL 规则使用 `kind="temporal"` 且 `params.retention_ttl_seconds`（非负整数秒）。内联 `retention_policy`（payload 顶层 / `payload.object` / patch）从来不是登记承载，已在 `forbidden-wire-fields.json` hard reject；部署管理面的 retention 配置是本地运维工具，不进 Event 历史。产品级 disappearing TTL 走 `ak.realm.disappearing_policy`，与本字段正交。 | 保留策略。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_by` | yes | `did_core_id` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did_core_id` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

#### 2.3.A 字段 carrier inventory（normative）

`ak.schema.realm.v1` 是 effective query projection，不是 `ak.realm.create` 的 payload schema。每个字段必须从下列唯一 carrier 构造，禁止 create/profile/policy 重复声明：

| 字段组 | 唯一 canonical carrier |
| --- | --- |
| `trust_domain`、`schema_refs`、初始 `reducer_profile`、`digest_algorithm`、`security_class`、`encryption_profile`、`notary_profile`、`notary`、`capability_action_registry_digest` | `ak.realm.create` 的 closed `ak.schema.realm_genesis.v1` object；仅这些 identity/security roots 进入 Realm ID preimage。 |
| `title`、`summary`、`avatar_blob_ref` | `ak.realm.profile` → `ak.component.realm.profile.v1`。 |
| `default_discoverability` | `ak.realm.discovery`。 |
| `default_join_rule` | `ak.realm.join_rule`。 |
| `history_visibility` | `ak.realm.history_visibility`。 |
| history key sharing | `ak.realm.history_sharing_policy`。 |
| bundle 组件集合（本节 §2.2，含 `federation_policy`、`sync_endpoints`、freshness / proposal / compaction / authority-lifetime / bottom-escalation 时窗与 `cell_lattices`） | `ak.realm.policy_bundle`。整个 bundle 每次按 `policy_revision` 完整重述；这些字段不得回落到 create 或 generic patch。 |
| alias | `ak.realm.alias`。 |
| plaintext-visible services | `ak.realm.plaintext_visible_services`。 |
| delivery binding policy | `ak.realm.delivery_binding_policy`。 |
| verified organization relationship | `ak.realm.organization`。 |
| lifecycle、其它已有专用 facet | 对应 registered event/cell。 |
| `id`、`created_by`、`created_at`、`updated_by`、`updated_at` 与其它 query-only 字段 | 分别由 Realm identity、signed envelope 与 reducer history 派生，不由 producer 在 Realm object 中重复写入。 |

monolithic `ak.realm.update` 与 `ak.component.realm.metadata.v1` 已删除。实现不得保留双写、双读或把完整旧 Realm create object 缓存为第二真相源。

`owning_organizations`、`fields`、`relation_profiles`、`policy_id`、`preview_policy_id`、`default_strand_id` 与 `retention_policy_id` 不构成遗漏的自由写入面：它们分别由已接受的 `ak.realm.organization` 关系、registered extension/relation projection、`ak.policy.set`、`ak.realm.preview_policy`、`ak.realm.set_default_strand` 与 retention Policy 投影。producer MUST NOT 在 profile 或 policy bundle 中重复声明这些 query 字段。

跨字段约束（normative）：`encryption_profile=mls_rfc9420` 的 Realm 若 effective `history_visibility ∈ {world_readable, shared, invited}`，effective `content_scheme` MUST 为 `mls_exporter_aead_v1`。若 effective `content_scheme=mls_rfc9420`（含缺省），effective `history_visibility` MUST 为 `joined` 或 `restricted`。任何 create/bootstrap 或 facet update 造成非法组合时，reducer MUST `failed_precondition`，reason=`history_visibility_requires_history_capable_scheme`。

### 2.3.0 Realm 组织归属与治理同意（normative）

`owning_organizations` 是 Realm metadata 中的声明 / 投影字段，不单独产生"官方 Realm"、"组织治理 Realm"或"组织控制 Realm"语义。客户端、Directory、搜索索引和管理 UI MUST NOT 仅凭该数组展示 verified badge、组织官方背书、组织治理归属或组织控制权。

已验证的组织关系 MUST 由 active `ak.realm.organization` 表示。该事件有两层独立授权：

1. **Realm-side acceptance**：事件必须作为目标 Realm 的 durable reducer-input event 被接受；写入者必须满足 `ak.realm.admin`，或处于 §2.5 允许的 create bootstrap 同批初始配置路径。这表示 Realm 当前治理面接受该组织关系声明。
2. **Organization-side consent**：`payload.authorization` 必须验证到 `payload.organization_id` 的 DID control state、threshold governance proof，或该组织 DID Document / governance profile 显式委派的 Account Authority / `ArkretGovernanceService`。委派 purpose MUST 覆盖 `ak.realm.organization`、`payload.relationship` 和 `payload.control_scopes`；事件时间必须落在 delegation 有效期内，且未被撤销。

`ak.realm.organization` 的 reducer cell subject 是 `(payload.organization_id, payload.relationship)`；`payload.status="active"` 表示该组织关系当前生效，`payload.status="revoked"` 表示同一组织关系已撤销。`statement_id` 只用于审计和替换 / 撤销链路，不是 cell subject。Directory 或客户端显示"官方 / 组织治理 / sponsor / directory certified"状态时，MUST 同时检查该 cell 的 latest accepted value 为 `active`、已到 `not_before`（若存在）、未超过 `expires_at`（若存在）、`control_scopes` 覆盖所展示的语义，并按时点解析组织 DID / delegation。

不同控制语义不能由组织归属自动推导：

- `relationship="owner"` 或 `control_scopes` 包含 `official_badge` 只表示组织背书该 Realm 的身份归属；不自动授予组织管理员 capability。
- 组织能否管理成员、policy、retention、moderation 或明文可见服务，仍由 `ak.realm.admin` capability、Realm policy facet、service binding 或对应控制事件决定。
- 组织作为 notary、notary controller、RRK 接收方或 delivery binding authority，必须分别由 `notary` / notary control move、`durability_policy`、`ak.realm.delivery_binding_policy` 等字段和事件明确表示；不得从 `owning_organizations` 或 `ak.realm.organization` 自动继承。
- Realm admin 单方面把某个组织 DID 写入 `owning_organizations`，如果没有对应 active `ak.realm.organization` 组织侧证明，接收方 MUST 把它视为未验证声明。

被授权读取 Realm 的客户端通过 self-surface 操作 `ak.self.realm_organization.read.list`（`GET /_arkret/self/realms/{realm_id}/organizations`，response schema `schemas/realm-organization-operations.schema.json#/$defs/realm_organization_relationship_list`）取回该 Realm 的 `ak.realm.organization` 关系投影（active / revoked / expired，latest-per-`(organization_id, relationship)`，由 reducer 派生 `lifecycle_phase`）以及无验证语句的 `declared_organization_hints`。客户端 MUST 仅在 `lifecycle_phase=verified_active` 时显示官方 / 治理 / 背书状态，并 MUST 把 `declared_organization_hints` 渲染为未验证声明。public discovery 路径（Directory Service 的 `ak.find.directory.read.resolve_realm` / `resolve_organization`）受 anti-enumeration 约束，不替代成员 / admin 侧的本操作。

### 2.3.1 `durability_policy`（Realm 恢复密钥 / RRK，normative）

`durability_policy` 声明在该 Realm 全体成员设备失效或全员离职后，谁能解开 Realm 历史。它是机密性轴的**持久性**策略，与 `notary`（finality 轴：谁签 Seal）、`notary.recovery_*`（主 notary 失效后谁接管盖章）正交，二者 MUST NOT 互相替代。

恢复方（Realm Recovery Key, RRK）是一组**离线 HPKE 接收方公钥**，**不是 MLS 成员**、不进 ratchet 树、不接收实时 fanout，只在恢复时取出。封存机制（每 epoch eager 把 `history_secret` 封给恢复方）见 [`../crypto-media/encryption-and-audit.md` §2.10.8](../crypto-media/encryption-and-audit.md)。

| 子字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | yes | `enum(none, org_recovery_key, threshold)` | 默认 `none`。 | `none`=无组织恢复路径（丢光即永久丢失）；`org_recovery_key`=单把 org-RRK；`threshold`=k-of-n。 |
| `recovery_recipients` | conditional | `array<RecoveryRecipient>` | `mode != none` 时 MUST 非空且 `uniqueItems`。 | 恢复方列表。 |
| `threshold` | conditional | `object{k:int, n:int}` | `mode=threshold` 时必填，`1 <= k <= n == len(recovery_recipients)`。 | 门限参数。 |

`RecoveryRecipient`：

| 子字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `recipient_id` | yes | `string` | Realm 内唯一。 | 接收方稳定标识。 |
| `principal_id` | yes | `did_core_id` | `org_recovery_key` / `threshold` 模式下 SHOULD 对应 Organization Principal；个人 Realm MAY 为个人 principal。验证时由完整 DID/DID URL 经 adapter 投影并比对该值。 | 持有 RRK 私钥的主体。 |
| `verification_method` | yes | `string` | MUST 指向 `principal_id` DID Document 中被 active `ArkretRealmHistoryRecoveryKey` service entry 指定的活跃 verification method（见 [`../identity/identity-did.md` §8.3](../identity/identity-did.md)）。 | RRK HPKE 公钥引用。 |
| `controller_organization` | no | `did` | 存在时 receiver MAY 据此核验组织归属。 | 控制该恢复方的组织。 |

规则（normative）：

- **粒度 = 组织组合，不在 Realm 上加旋钮**：爆炸半径 = 某 org 拥有的 Realm 集合；要更细隔离就把敏感 Realm 的 `owning_organizations` 指向更细的 org（例如独立的 HR org），而不是给 Realm 加 RRK 粒度机制。父组织保留访问 = 把父 org 的 RRK 也列入 `recovery_recipients`（显式、成员可见，无暗继承）。
- **域隔离**：`verification_method` 指向的 RRK MUST 是 history-recovery 域专用 key，独立于 `principal_id` 由 [`../identity/key-management.md` §3.3](../identity/key-management.md) `backup_hpke_ikm` 派生的 backup-HPKE key（wire 名 `recovery_public_key`）；攻破"能解 Realm 历史"MUST NOT 等于"能改组织身份"。
- **成员可见**：`mode != none` 时客户端 MUST 按 [`../crypto-media/encryption-and-audit.md` §2.10.8](../crypto-media/encryption-and-audit.md) 披露义务向成员展示恢复方可验证身份与 mode。
- **写入路径**：`durability_policy` 经 `ak.realm.policy_bundle` 写入（不新增 event kind），随 `policy_revision` 单调推进；变更 MUST 由后续 `ak.mls.commit` 覆盖 frontier 后对新 epoch 的封存义务生效。
- **scheme 约束**：`mode != none` 仅在 `content_scheme=mls_exporter_aead_v1` 时有效；在 `mls_rfc9420` Realm 上声明 `mode != none` MUST `failed_precondition`（reason=`durability_scheme_incompatible`），因为后者无可交付 `history_secret`。

### 2.4 最小示例

```json schema=schemas/realm.schema.json
{
  "id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "schema": "ak.schema.realm.v1",
  "title": "Launch Plan Confidential Realm",
  "trust_domain": "ak:trust_domain:did.webvh.acme.example",
  "schema_refs": ["ak.schema.realm.v1"],
  "default_discoverability": "invite_only",
  "default_join_rule": "invite",
  "history_visibility": "joined",
  "reducer_profile": "ak.reducer.core.v1",
  "encryption_profile": "mls_rfc9420",
  "notary_profile": "single_did",
  "notary": {
    "kind": "single_did",
    "actor_id": "ak:did_core:webvh:zAKD7rB7Tn8G84VgUBAjn8p2h",
    "recovery_members": ["ak:did_core:webvh:z8wtK7VwY3xTRFNPwZixinUFx"],
    "controller_organization": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
    "recovery_controller_organizations": ["ak:did_core:webvh:zGnKWC3QoYaXLNsfmH6VfPke4"]
  },
  "capability_action_registry_digest": "sha256:9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a",
  "created_by": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
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

每一个 Realm——Collaboration、Direct Conversation、human PCR 与 managed Agent PCR——的 closed genesis object MUST 使用 `schema="ak.schema.realm_genesis.v1"`，并携带：`purpose`、`genesis_salt`、`trust_domain`、`schema_refs`、`reducer_profile`、`digest_algorithm`、`security_class`、`encryption_profile`、`notary_profile`、`notary`、`capability_action_registry_digest`。其中：

```text
genesis_salt = base64url_no_pad(CSPRNG(32 octets))
```

canonical wire 恰为 43 chars，禁止 padding、非 URL-safe alphabet、31/33 bytes、时间/HLC/UUID/计数器或可预测 PRNG。每个新 create intent 只生成一次并先与 intent 持久化；prepare、签名、HTTP retry、receipt 查询与 crash recovery 必须复用同一 salt 以及首次持久化的 exact signed unit。salt 不是 replay nonce、授权、新鲜度、排序或 winner 输入。**PCR 与 managed Agent PCR 同样 MUST 携带 `genesis_salt`**：收敛为 event-derived 后它们不再是例外分支。salt 在此的作用是 (i) 消除例外、(ii) 使 PCR 地址不可由 DID 预先推算、(iii) 强制 durable intent 纪律——崩溃后重建 create 会得到不同 `event_id`，复用同一 salt 与首次持久化的 exact signed unit 才能避免产生第二个 PCR；该纪律与账号维度唯一约束互为正反面。

**为什么必须省略而不是"携带并校验相等"（normative rationale）**：`event_digest` 的 preimage 只排除 `proofs` / `unsigned` / `actor_kind` / `event_id`（[`../conformance/encoding.md` §6](../conformance/encoding.md)），`realm_id` 与 `scope_ref` **仍在 preimage 内**。而 §4.0 的 `event_id` 由该 digest 决定，`realm_id` 又要等于 `retype(event_id)`——于是 `realm_id` 成为 digest 的函数，却又是 digest 的输入，**定义即循环，没有不动点可解**。唯一出路是把它移出 preimage，即从 envelope 省略；`scope_ref` 同理，故 genesis 使用不含 `realm_id` 的 `realm_genesis` 形态。这与 Matrix room v12 把 `room_id` 从 create event 移除的理由完全相同。

Realm 之外的 create-once 对象没有这个问题：它们的 ID 只出现在 payload，且按 [`common-fields.md` §6.0](./common-fields.md) 一律省略。

**Principal Control Realm 与 managed Agent PCR 适用本节通则（normative）**：
**全部 Realm——含 human PCR 与 managed Agent PCR——一律按 §2.5.0 从各自 genesis Event 派生
`realm_id`**，使用同一个 33-octet / 44-character Realm token wire form，不使用 UUID。

理由：PCR 的作用域是「某个 DID 在**当前 Principal Server** 上的账号」，同一 DID 在不同 Principal
Server 上是完全独立、不可迁移的 PCR。因此 `realm_id` MUST NOT 只由 principal DID 决定：那样会让这些互不
相关的 PCR 算出**同一个 `realm_id`**，使该 id 无法标识"哪一个 PCR"——而 PCR 的 realm id、genesis receipt 与 Seal
都会作为设备授权权威证据进入联邦（见 [`../sync/federation.md`](../sync/federation.md) 与
`federated-device-signing-key-evidence.schema.json`），碰撞会让远端 verifier 无法区分两个 PS 上的设备目录。
event-derived 天然按创建事件区分，同时使 `realm_id` 承诺 create Event 的完整内容。

**「一个账号至多一个 PCR」不再由 id 碰撞保证**：event-derived 下两次 genesis 产生两个不同 `realm_id`，
`realm_already_exists` 不再拦截重复。Principal Server MUST 在**账号维度**（其本地 accounts 记录）强制
该唯一性，并在冲突时零写入拒绝；实现 MUST NOT 依赖 id 相等来发现并发 genesis。

`realm_token[0]` 按 nibble 拆分：**高 4 位永久保留并 MUST 为 `0x0`**，低 4 位是 `digest_suite`。
v1 Realm 算法固定为 `digest_suite=0x1`（SHA-256），因此 v1 唯一合法 header 是 `0x01`。
该 nibble 不承载派生类别信息，语义与 Event ID 的 reserved nibble 完全一致。任何非零高 nibble MUST NOT 产出，收到 MUST 以 `realm_id_not_event_derived`
拒绝。低 nibble `0x0` 与 `0x2..0xF` 非法/保留；普通 Event 支持其它低-nibble suite 不代表 Realm 自动支持。

PCR 的**身份锚**与其 `realm_id` 是两件事：realm id 按上述通则由 genesis Event 派生，而该 PCR 属于哪个 principal 由 create 携带的唯一 critical root anchor ref 决定（见 [`../identity/key-management.md` §5.0.1](../identity/key-management.md)）。远端 verifier 需要判定"某 Seal 是否属于该 principal 的 PCR"时，MUST 以已签名的 `pcr_genesis_unit` receipt 中承诺的 `realm_id` 为准，MUST NOT 从 principal DID 自行重算。

因此 `ak:realm:` 始终只有一种物理形态：`ak:realm:<44-char-token>`，解码后恰为 33 octets。所有 Realm（含 human PCR 与 managed Agent PCR）都重类型其 create Event 的 token（header `0x0S`）。它不是 producer 自选。

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
3. 对**所有** `purpose` 校验 `retype(event_id) == realm_id`，且 `genesis_salt` 为 canonical Base64URL-no-pad 的 32 octets；`purpose="principal_control"` 走 `did_root_anchor` 分支时另需校验 create 携带的唯一 critical `did_inception` root anchor ref，走 organization-governed `delegated_pcr_genesis` 分支时改验 `executed_by` / `authorization_ref` 的 governance delegation（该分支 MUST 不含 `did_inception`，两分支因此结构互斥）；`purpose="managed_agent_control"` 时 create **不携带任何 anchor ref**，改为反查 controller PCR 中是否已存在 accepted 的 `ak.agent.provision` 声明了 `retype(本 create 的 event_id)`，无匹配 MUST 零写入拒绝（见 [`../identity/key-management.md` §3.6.3](../identity/key-management.md)）；
4. 取得并验证完整 ordered genesis unit 与其 genesis Seal/state commitment；identity 或 genesis closure 任一未完成前 MUST NOT 接受该 Realm 的后续 Event、Seal 或 effective Realm projection；
5. 把该 genesis 与完整初始 facet commitment 持久化为该 `realm_id` 的永久本地绑定；
6. 此后出现的任何不同 genesis MUST 拒绝，MUST NOT 因为它先到、更新、或来自"更权威"的 peer 而覆盖。

上面第 3 条大体已被现有机制隐含——Control Move 要 `seal_basis`、DataEvent 要 `seal_ref`，Seal 链最终 root 在 genesis Seal——但仍 MUST 显式执行，否则实现会在 backfill 乱序时先落一半状态。

**这条使 `realm_id` 自证。**一个恶意 join candidate 服务自造的"Realm S"时，其 genesis 内容不同 → `event_id` 不同 → `retype(event_id) ≠ S` → 首次接触即被拒。因此 invite、`join_candidates[]` 与 Directory 响应 **MUST NOT** 被要求携带 genesis digest 或 authority-root 值：自证不需要外部背书，也不引入对邀请者或 Directory 的新信任。拒绝时的对外语义复用 [`../sync/federation.md` §5.0](../sync/federation.md) 规则 4 的统一最小披露失败族。

> **边界：identity 自证，naming 不自证。**攻击者仍可创建一个 `realm_id` 完全合法自证的 Realm，再去抢注一个像样的 alias。alias 抢注与目录投毒是独立问题，本节不解决，也 MUST NOT 被表述为已解决。

除非底层 256-bit digest 发生完整 hash collision，两条不同 digest preimage 的 create 必然有不同
`event_id`、因而是两个不同的 Realm。"同一 Realm id 的第二条 create"要么是携带 ID 与重算 digest
不符的伪造输入（必须在 lookup 前以 `event_id_digest_mismatch` 拒绝），要么是约 `2^128` 通用复杂度的
完整 collision evidence（必须整组 quarantine）。下文步骤 3 的 `realm_already_exists` 因此是防御性
剩余分支，不是常规路径，也不得退化为 first-create-wins。

#### 2.5.1 Bootstrap 步骤

`ak.realm.create` 是 Realm 生命周期的 genesis event，只建立 Realm identity/security core、create log、notary、reducer profile 与终身稳定的 authority root。显示内容、policy 与 membership 都由同一原子 bootstrap unit 中各自的 registered facet Event 建立。

**Human Principal Control Realm 分支（normative）**：当 create 满足 `purpose="principal_control"`、PCR profile、`actor_id=principal DID` 与唯一 critical `did_inception` root anchor 时，root-signed genesis 必须携带 `FoundingDeviceDescriptor`，第二条固定为 founding-device-signed `ak.device.authorize`。两条通过 `ak.peer.principal_genesis.command.submit` 原子接受，均免 `seal_basis`；descriptor 与 authorize payload 必须逐字段/digest 相等。Managed Agent PCR 的 controller-authorized 分支 MUST 使用 `purpose="managed_agent_control"`，且不使用 human `pcr_genesis_unit` 或 `FoundingDeviceDescriptor`。

以下五项是 `ak.realm.create` 的完整 registered writes。任何实现不得由 create 顺带写 profile、member 或 Agent lifecycle 状态。

`ak.realm.create` 的 registered writes MUST 由该 Event 的 canonical reducer contract 原子承担。全部 writes 在 [`contract-registry.json`](../../artifacts/registry/contract-registry.json) 的 `ak.realm.create.cell_writes[]` 中登记；wire 不重复携带：

1. **写入 `ak.component.realm.genesis.v1` singleton**：值为 closed `ak.schema.realm_genesis.v1` object；该 cell 是 create-locked identity/security core 的唯一权威。
2. **写入 `ak.component.realm.create.v1` ordered log**：记录 accepted create 用于审计/backfill；同一 Realm 的不同 create 以 `realm_already_exists` 或 collision quarantine 拒绝，不由 lattice 选择 winner。
3. **写入 `ak.component.notary.v1` singleton**：初值为 `payload.object.notary`；后继只能由 `ak.realm.notary` 承担。

4. **写入 `ak.component.realm.reducer_profile.v1` singleton**：初值为 `payload.object.reducer_profile`；必须是本地支持的 active registry row，否则整个 unit 返回 `profile_unsupported`。后继只能由 `ak.realm.upgrade` 承担。

5. **写入 `ak.component.realm.authority_root.v1` cell**（`cas_register`，`bottom=reject`，`cell_subject=null`），值由注册 `value_projection` 从 signed envelope 与 create payload 确定性派生：

   ```text
   {
     "controller_id": "<envelope.actor_id>",
     "controller_epoch": 0,
     "authority_generation": 0,
     "capability_action_registry_digest": "<payload.object.capability_action_registry_digest>"
   }
   ```

   `(realm_id, cell_ref)` 是该 Realm **终身稳定的 authority root identity**；`controller_id` 只是当前控制者，`controller_epoch` 只随 root controller 轮换递增，`authority_generation` 只随整代授权重置递增。`capability_action_registry_digest` MUST 由创建者写入并签进 `ak.realm.create` payload；receiver MUST 取得对应 `capability-action-registry.json` snapshot、按 RFC 8785 JCS 重算 digest 一致后**原样复制**进该 cell，MUST NOT 用本机当前 embedded registry 推断——否则跨版本回放会对同一签名 Event 得到不同 genesis `state_root`。已发布实现写入过的旧 snapshot MUST 按 [`capabilities.md` §3.2](../authz/capabilities.md#32-首发-grant-的-issuer-自身权限上界normative) 的 append-only 归档规则保留；current registry 升级不得使既有 Realm 的 digest 失去可解析性。snapshot 不可得或重算不一致时，整个 bootstrap unit MUST 原子拒绝（`failed_precondition`，`reason="capability_registry_basis_unavailable"`）。author 不得自行提供 `controller_id` / `controller_epoch` / `authority_generation`，也不得携带该四字段之外的成员；出现额外 author-supplied 字段时 MUST 原子拒绝（`failed_precondition`，`reason="realm_authority_root_conflict"`）。

以上五条是 create 的完整 projection。profile 与其它初始 state 由后续 slots 的 registered writes 产生，完整 unit 的所有 writes 一起进入 genesis Seal/state commitment。任一 required write 失败，整个 unit MUST 原子回滚；authority-root 缺失时返回 `realm_authority_root_missing`。

**root authority 的语义边界（normative）**：authority-root cell 的 current controller 在给定 Seal basis 下凭该 cell 的 inclusion proof 获得 effective `ak.realm.owner` 与封闭的 root-control authority。它是显式、sealed、registry-basis-bound 的协议状态，**不是** `realm_state.owner`、membership 或 `created_by` 身份旁路：

- 授权判定 MUST 使用该 cell 在同一 Seal basis 下的 registered inclusion proof，并逐项校验 registry digest、`controller_id`、`controller_epoch` 与 `authority_generation`。任何以 `created_by`、membership 或 projection mirror 回退的实现都重新引入了隐式提权洞。
- 服务实现若维护 `realm_state.owner` 一类投影镜像，它只能是该 cell 的可丢弃 projection mirror，MUST NOT 参与授权判定。
- 该 authority 的 resource 固定为本 Realm 的 `realm_wide`，MUST NOT 为其它 Realm 提供普通 issuer upper bound；跨 Realm 派生只能走已注册的 `ak.capability.derived` 规则（[`realm-links.md` §6](./realm-links.md)）。
- 普通 `ak.realm.owner` grant 只表示**可撤销的 co-owner**：持有人具有 owner 的 operational / grant authority，但不控制 authority-root cell，因而不能 author root-control Event。`ak.realm.owner` 逐字存在于 owner 的 `grant_authority_actions`，所以 root controller 与 co-owner **都可以**把 `ak.realm.owner` 继续授予他人——这是期望行为，不是漏洞；它不改变"root-control 平面唯一且不可经普通 grant 获得"。

**genesis batch 内的 staged root proof（normative）**：同一 ordered submit batch 中位于 create 之后的 Event MAY 使用 staged authority-root proof，其绑定的 create Event MUST 是同批 slot 0，且 `controller_id` MUST 等于 signed envelope `actor_id`。该 proof 只在此原子 unit 内有效；batch 外一律要求 accepted Seal 下的 root-cell inclusion proof。

Realm bootstrap event set 以 create 开始。创建时没有 accepted Seal，因此下列两个**互斥封闭分支**内的 Event MAY 免 `seal_basis`（与 [`event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md#5-control-move) 使用同一句，两处 MUST 保持逐条一致）：

- 普通 Collaboration 分支：`ak.realm.create`；同批同 actor 的 initial facets，顺序唯一由 `contract-registry.json.realm_bootstrap_registry.ordinary_collaboration` 登记：required `profile → policy_bundle → join_rule → history_visibility`，条件 `history_sharing_policy`，required `discovery`，可选 `alias`，条件 `plaintext_visible_services`，required `delivery_binding_policy`，最后 required creator `member.state{join}`。不得在实现中维护第二套顺序常量；
- 1:1 Direct Conversation 分支：恰好 `ak.realm.create → peer ak.member.state{join} → main ak.strand.create` 三条，不得携普通 Collaboration facet。固定 profile、policy、join、history 与 discovery baseline 由 [`../identity/contact-and-direct-conversation.md` §6.2](../identity/contact-and-direct-conversation.md) 的 registered reducer contract 机械投影。`ak.strand.create` 平时是携 `seal_ref + auth_context` 的 DataEvent；但该 exact unit 的 Genesis Seal 同时覆盖三条，Strand 无法引用尚不存在的 Seal，因此在且仅在该 unit 内免 basis。

不在该列表内的 Control Move 一律要求 `seal_basis`。Human PCR 只允许上文 root create + founding authorize 两项 shape；不得把普通 Realm follow-up 白名单混入 PCR genesis。批次结束后所有普通 Control Move 按 [`event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md#5-control-move) 携带 basis。

Authz 含义：

- 同批 facet 在 creator member slot 生效前依赖 staged authority-root proof，而不是 create 隐式 membership。批次外的授权不得回退到 envelope actor、create author 或服务本地 owner mirror。
- `ak.realm.policy_bundle` payload MUST 携带单调递增的 `policy_revision`。初始 revision 为 `1`；后续更新必须满足 `new.policy_revision == previous.policy_revision + 1`，否则 reducer MUST `failed_precondition`，reason=`policy_revision_rollback` 或 `policy_revision_gap`。任何用于缓存、Policy Server decision 或 identity_link 的 `policy_frontier_digest` MUST 覆盖 `policy_revision`，不得只 hash policy 字段值集合；MLS security frontier 则只投影 key-access 字段，MUST NOT 因无关 revision 前进而变化。
- **加密 floor 单向 ratchet（normative）**：Realm 的 effective `content_encryption_floor` 与 effective `metadata_encryption_floor` MUST 随时间单调非降。`ak.realm.policy_bundle` 若把 `content_encryption_floor` 从 `e2ee_required` 降回 `allow_plaintext`，reducer MUST `failed_precondition`，reason=`content_encryption_floor_downgrade`；若把 `metadata_encryption_floor` 降到更低等级（比较序 `allow_plaintext < e2ee_required`），reducer MUST `failed_precondition`，reason=`metadata_encryption_floor_downgrade`。收紧（抬高 floor）永远允许，只有降低被拒。该 ratchet 使"加密一旦开启不可撤销"成为治理层硬约束，并消除静默 downgrade 攻击面；Circle 级同一规则与 effective floor 计算见 [`circle.md` §7](./circle.md)。
- 同一 submit 批次内 reducer MUST 按 wire 顺序处理。普通 Realm：create 第一，其后是白名单内的 follow-up；human PCR：root-anchored create 第一、founding-device-signed authorize 第二且 unit 到此结束。顺序或形态不符以 `pcr_genesis_unit_invalid` 原子拒绝。
- byte-identical unit retry 返回原 accepted identity/receipt，不产生第二个 Realm 或副作用；不同 canonical bytes 声称同一 Realm id 时 MUST `realm_already_exists` 或 collision quarantine。

Server 端实现合规要点：

- server 必须先在隔离 staged state 上按 wire order 验证完整 unit，再以一个 storage transaction 提交 canonical Events、全部 registered cells、receipt/ack 与 federation outbox；任何失败后上述可观察状态均为零。
- effective Realm query 必须组合 genesis/profile/discovery/join/history/policy/alias/lifecycle cells；不得从 create payload 原样复制旧完整 Realm，也不得读取已删除 metadata cell。
- 不允许通过 spec 之外的 REST 端点（如 `POST /spaces` 之类的私造 lifecycle 命令面）来兜底 bootstrap。此类端点违反 [`sync/service-http-binding.md` §2.1](../sync/service-http-binding.md#21-rest-api-命名空间组织) 的"实现不得用未声明路径绕过 canonical operation"规则，且会让事件流上的 read-only consumer 看不到完整的 source-of-truth 事件。

**Backfill / federation peer 一致性（normative）**：peer 可先取得 create bytes，但在完整 bootstrap closure 与 genesis state commitment 验证前必须保持 unresolved，不得接受后续 Realm Event、Seal 或发布 effective projection。creator membership 来自 unit 最后独立 `ak.member.state{join}` slot；缺失不得本地补造。

### 2.6 Realm 终态 (`ak.realm.tombstone` / `ak.realm.destroy`)

Realm 有两个终态 event，语义不同：

| Event | 语义 | 是否可恢复 | successor |
| --- | --- | --- | --- |
| `ak.realm.tombstone` | "本 Realm 不再活跃" — 转移到 successor Realm（产品改版、组织重组等）。 | no，但 successor 接续历史可达 | 必填 `successor_realm_id` |
| `ak.realm.destroy` | "本 Realm 永久退役" — 终极去活。无 successor，等同于"该 Realm 在该 deployment 内永久关闭"。 | no | MUST NOT 设 successor |

`ak.realm.tombstone` 写入 `ak.component.realm.tombstone.v1`，`ak.realm.destroy` 写入 `ak.component.realm.destroy.v1`；二者均为 cas_register（bottom=reject），各自不可重复写入。capability：`ak.realm.tombstone` / `ak.realm.destroy`（action 定义见 [`../authz/capabilities.md` §5.1](../authz/capabilities.md)，high-risk 约束见 [`capabilities.md` §8](../authz/capabilities.md)）。

#### 2.6.0 Realm 可逆 lifecycle facet（`ak.realm.archive` / `ak.realm.freeze`）

除上述两个终态外，Realm 还有两个**可逆** lifecycle facet，与终态正交，且对应 [`common-fields.md` §5](./common-fields.md) 状态对齐表 Realm 行支持的 `archived`：

| Event | 语义 | lifecycle_modality | cell family |
| --- | --- | --- | --- |
| `ak.realm.archive` | 把 Realm 设为 `archived`（软隐藏，UI 默认不展示，可撤销）。 | reversible | `ak.component.realm.archive.v1` |
| `ak.realm.freeze` | 把 Realm 冻结为只读（暂停普通写入，可撤销）。 | reversible | `ak.component.realm.freeze.v1` |

二者均为 cas_register（bottom=reject）durable event，承载一个 **reversible boolean** facet：**同一个 `ak.realm.archive` 写 `true` 进入 `archived`、写 `false` 复原**，**不走独立 `ak.realm.restore` event**；`ak.realm.freeze` 同理用单一 reversible boolean facet 在 frozen / 非 frozen 之间切换。这区别于 [`common-fields.md` §5.2](./common-fields.md) 模板中 `ak.<kind>.archive` + `ak.<kind>.restore` 成对的形态——Realm 的可逆性由 facet boolean 表达，registry `lifecycle_modality=reversible` 是真源。capability：`ak.realm.archive` / `ak.realm.freeze`（action 见 [`../authz/capabilities.md`](../authz/capabilities.md)）。

被 `archived` 或 `frozen` facet 关闭普通写入的 Realm 收到非豁免普通写入时，reducer / 服务端 MUST 返回 `realm_frozen`（HTTP 403）。豁免集合是封闭集合，仅包括：(a) `ak.realm.archive` / `ak.realm.freeze` facet 自身的后继写（包括写 `false` 解锁）；(b) `ak.realm.tombstone` / `ak.realm.destroy` 终态升级；(c) `ak.audit.*` 与 `ak.audit.erasure_receipt`；(d) 撤权或主动退出写入：`ak.member.state{membership="leave"}`、`ak.capability.revoke`、delegation revoke、device / key revoke，以及这些动作必需的审计回执。豁免动作仍 MUST 通过其普通 capability、CAS basis、签名和 schema 校验；冻结/归档不授予额外权限。`ak.realm.policy_bundle`、新增成员、授权扩张和其它控制面写入不在豁免集合内。Circle 与其它子对象 MUST 直接回指本枚举，不得自行扩张豁免面。

#### 2.6.0.1 产品态"解散 Realm"映射（normative）

产品层若给 Realm owner / admin 提供"不转让、直接解散 / 关闭这个 Realm"的选择，wire 层 MUST 映射为 `ak.realm.destroy`，而不是 `ak.realm.tombstone`：

- `ak.realm.tombstone` 只用于**有 successor Realm 的迁移 / 接续**。它 MUST 携带 `successor_realm_id`，表示旧 Realm 不再活跃但由 successor 接续历史可达性。没有 successor 时，客户端 / server MUST NOT 用 tombstone 表达"解散"。
- `ak.realm.destroy` 用于**无 successor 的永久关闭**。accepted 后 Realm 仍可作为终态记录、审计对象和按 retention / history visibility 可读取的历史存在，但普通成员写入、消息发送、Circle / Strand / Relation 新写入等 MUST fail closed（`realm_terminal_state`）。这正是"Realm 还在，但所有成员不能继续发言 / 协作"的不可逆产品语义。
- `ak.realm.freeze` 用于**可逆只读冻结**（incident hold、管理员临时锁场、等待治理决策等）。如果产品文案承诺"解散 / 永久关闭"，不得只写 `freeze=true`；如果产品文案承诺"临时只读 / 可恢复"，不得写 `destroy`。
- `ak.realm.archive` 用于软隐藏 / 默认列表移出，不是 ownership transfer、迁移或解散的替代品。

实现的 UI 可以把上述 wire event 命名为"解散 Realm"、"关闭 Realm"或"冻结 Realm"，但审计、capability、federation 与 reducer MUST 以本节的 event 语义为准。ownership transfer 是成员 / capability 治理动作，不改变 Realm lifecycle；当 owner/admin 不愿 transfer 时，应在 `freeze`（可逆只读）与 `destroy`（无 successor 永久关闭）之间选择，而不是滥用 `tombstone`。

#### 2.6.1 `ak.realm.tombstone` / `ak.realm.destroy` 终态规则（normative）

任一终态 Event accepted 进入 frontier 之后：

1. **拒绝后续普通写入**：reducer MUST reject 所有非 `ak.audit.*` / 非 `ak.audit.erasure_receipt` event；后续 `ak.self.events.command.submit` 返回 `realm_terminal_state`（错误码归类于 `realm_lifecycle` 错误域，避免与 `ak.realm.lifecycle.*` capability action 命名混用）。
2. **Snapshot / Backfill / GC**：
   - Snapshot service MAY 发布最后一份 final snapshot（`ak.snapshot.*` event）；之后 snapshot 不再更新。
   - Backfill MAY 继续提供历史 event 给已授权 reader，受 history visibility policy 控制；新读权 MUST NOT 再被授予。
   - GC：tombstone 本身只关闭旧 Realm，不触发额外物理删除；destroy 可令 blob bytes、projection 缓存、to-device 队列、push route 按部署 retention policy 物理删除。canonical event log 仍按 retention/legal hold 保留。
3. **Successor / Tombstone 区分**：`ak.realm.tombstone` MUST 携带不同于自身的 `successor_realm_id`；`ak.realm.destroy` MUST NOT 携带该字段。Projection 对二者统一暴露 `realm_terminal_state`，并用 `terminal_kind=tombstone|destroy`（或逐字节等价的封闭枚举）区分迁移与永久退役。
4. **Erasure Receipt 与 Legal Hold**：destroy 不自动触发 erasure。若部署进入 erasure 阶段，发布 `ak.audit.erasure_receipt`（schema `ak.schema.erasure_receipt.v1`），可能 `outcome=blocked_by_legal_hold`。Legal hold 优先于 destroy 的 GC 路径。
5. **Federation Fanout**：终态 Event MUST 沿 federation 推送到所有曾持有该 Realm 状态的 peer Principal Server；peer 收到后 MUST 在 30 天内本地标记 `realm_terminal_state`、记录相同 `terminal_kind`，并停止接受该 Realm 的新 `ak.peer.events.command.submit`（包括 backfill 写入）。
6. **Child Space / Strand cascade**：终态 accepted 后，home Realm 内所有 non-terminal Space、Strand placement 与 structural `contains` projection MUST NOT 作为 live navigation surface 暴露。实现 MUST 在同一事务或后续 bounded cleanup job 中把这些对象标记为只读 locked projection（destroy 可用 `realm_destroyed_orphan`，tombstone 可用 `realm_tombstoned_orphan`）或自动 tombstone/archive；不得继续允许 `ak.strand.move`、`ak.space.parent`、`ak.space.update` 等普通写入复活它们。跨 Realm `parent_space_id` 指向终态 Realm 的 Space 时，引用方 MUST 在发现终态 frontier 后将该 edge 降级为 locked/lazy link，并在 30 days 的 `terminal_parent_repair_window` 内 reparent、archive 或 tombstone；不得传播终态 Realm 的 membership、capability、history 或 E2EE key material。
7. **Circle scope cascade**：父 Realm tombstone 或 destroy 后，其内所有 [Circle](./circle.md) 的 **effective lifecycle** 立即进入 `realm_terminal`，但 Circle canonical lifecycle cell 不被隐式改写，也不合成 `ak.circle.tombstone`。该派生状态以父 Realm terminal Event 及其 Seal 为唯一依据，优先于 Circle 自身 `active` / `archived` projection。任何指向这些 Circle 的写入 MUST fail closed（`failed_precondition`, `reason_code=realm_terminal_state`）；projection MAY 显示 `scope_unavailable`，但 `scope_circle_id` 不会被自动 rewrite。详见 [`circle.md` §9.2](./circle.md)。

#### 2.6.2 跨 Principal Server Erasure Receipt Fanout（normative）

当部署对一个 Realm（或一个 principal）执行 hard erasure 时，**issuing** Principal Server MUST：

- 发布一条 `ak.audit.erasure_receipt`（durable_event）；
- 把 receipt、`receipt_digest` 与 exact retained stub 封装成 `erasure_receipt_package`，通过 `ak.peer.erasure_receipt.command.submit`（`POST /_arkret/peer/erasure-receipts`）投递给所有曾接收过该 scope 内容的 peer Principal Server；
- 为每个 destination 写入有上限的 durable outbox，并只在收到 receiver 签名的 `accepted` 或 `duplicate` acknowledgement 后关闭；网络不明时使用相同 Idempotency-Key 与逐字节相同 body 重试；
- 通过 `ak.peer.erasure_receipt.resource.get`（`GET /_arkret/peer/erasure-receipts/{receipt_id}`）向 issuer、receiver 或显式授权 auditor 返回 exact package；未知、隐藏与未授权统一 `not_found`，不得提供可枚举列表。

**receiving** peer 处理 receipt 时 MUST：

- 在任何删除或 durable acknowledgement 之前，验证 service-to-service transport，要求 `Source-Service-ID == receipt.issuer`，并验证 receipt schema、签名链、issued-at authority、`receipt_digest`、retained-stub digest 与 scope/subject/terminal binding；
- 如果 peer 本地存有该 erasure scope 内的 blob / projection / cache，按 receipt `scope.storage_boundary` 走本地删除流程，并发布自己的 `ak.audit.erasure_receipt` 反馈实际结果；
- 失败（legal hold、retention 冲突、blob 已被备份到不可达存储）MUST 在 peer 自己的 receipt `outcome` 字段写 `partially_completed` 或 `blocked_by_legal_hold`，不得假装成功；
- 任何 peer 未在 `erasure_propagation_window_ms`（默认 7 天）内回执，issuing server MUST 在该 erasure receipt 的 `fanout_status` 字段标 `incomplete`（并在 `peer_receipts[]` 对应 peer 条目记 `status=timed_out`），把 incomplete 状态暴露给 audit/UI；不得静默吞没。`fanout_status` 与 per-peer `peer_receipts` 子结构定义见 `ak.schema.erasure_receipt.v1`（schema `artifacts/schemas/erasure-receipt.schema.json`）。

提交操作的幂等域固定为 `(source service, destination service, Idempotency-Key)`：同 key / 同 canonical body 必须返回首次生成的 byte-identical acknowledgement 与原 `accepted_at`；同 key / 不同 body 返回 `duplicate_conflict` 且零写入。receiver acknowledgement 的 proof 对去掉 proof 的完整 closed object 使用 `H("ak.erasure-receipt-acceptance.v1", object)`，因此发送方可以离线验证谁在何时接受了哪一个 receipt digest。

**Hash chain linkage 保留**：hard erasure 仍保留 event graph verification stub（`retained_stub_digest` 字段），供后续 verifier 校验 Event ID 的结构、Event ID 与冗余 digest 的一致性、receipt/stub binding，并连接外部仍存在的 proof、Seal 与授权证据。它只保留已记录的 identity/linkage evidence；原 canonical Event bytes 已擦除后，stub 不能独立重算或证明这些 bytes 的 hash preimage。`retained_stub_digest` 的输入是 `canonical_json(retained_stub)`；`retained_stub` 使用 `ak.schema.erasure_verification_stub.v1` 结构，至少绑定 subject、scope、receipt_id、completed_at，并在适用时包含 event digest / proof `event_digest`、seal inclusion、redaction authorization ref 与 legal-hold ref。Stub MUST NOT 保留已擦除 plaintext 或未加盐低熵 plaintext digest；若 receipt 不内联 `retained_stub`，签发服务必须在 erasure receipt endpoint 暴露同一 canonical stub。projection / UI MUST 显示 `[erased]` 占位而不是模糊化。

### 2.7 Realm Membership FSM（normative）

`ak.member.state` 写入 `ak.component.member.state.v1:<actor_id>`，lattice 为 `fsm`、`bottom=reject`。Realm 使用 [`common-fields.md` §4.5](./common-fields.md#45-参数化-membership-fsmnormative) 的共享 membership FSM，实例参数为 `scope_kind=realm`、`delivery_binding_rebind=true`；writer/guard 以该表 Realm 列为准。`ak.realm.create` bootstrap 例外见 §2.5：它直接把 `created_by` 的 member cell 初始化为 `join`。`join -> join` 仅用于成员保持加入状态时迁移 delivery binding / membership metadata，不得借此改变 join gate 结果。

`invite` 与 base v1 bare `knock` 的过期只影响 operation eligibility，不会由本地计时器自动改写共享 member cell。超时清理必须由上表列出的 authorized writer 提交显式 `leave`；receiver MUST NOT 根据本地墙钟合成 reducer-derived member event。Join Policy `member.application` 的 `application_ttl` 是独立 candidate workflow，不得反向解释为 bare knock TTL。

共享表未列出的 transition MUST `failed_precondition`，reason=`invalid_membership_transition` 或更具体的 join / delivery-binding reason。`join -> invite`、`ban -> join`、`invite -> knock`、`leave -> leave` 等均非法；需要重试时 producer 必须基于当前 state 重新提交合法 transition。父 Realm `join -> leave/ban` 的 cascade 对 Circle membership 的影响见 [`circle.md` §9.1](./circle.md)。

上表 `leave -> join` 另有一个封闭的 Native Personal Agent controller carve-out：当 writer 是 target agent 的已验证 controller、writer 自身在目标 Realm 为 active `join`、target agent lifecycle 为 `active`，且 accountability / Realm native-agent policy / Join Policy / MLS admission 全部通过时，controller MAY 直接写入 target agent 的 `join`。该写入不产生 invite，也不需要 agent runtime 接受。该 carve-out 不授予 writer 通用 `ak.realm.admin`，不得用于其他 principal。反向约束同样是强制的：controller 从 `join` 转为 `leave` / `ban` 时，其在该 Realm 内仍为 `join` 的 Native Personal Agents MUST 级联为 `leave`（reason=`controller_membership_ended`）；已为 `ban` 的 agent 保持 `ban`，不得被 cascade 降级。

### 2.8 Realm 角色分类（normative）

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
  - human / organization PCR create genesis `purpose = "principal_control"`；managed Agent PCR create genesis `purpose = "managed_agent_control"`
  - `schema_refs` 包含 `ak.profile.principal_control_realm.v1`
  - `encryption_profile = "mls_rfc9420"`；PCR 在 v1 中不允许 `none` 或 `external`，schema / reducer MUST fail closed。
  - effective `content_encryption_floor = "e2ee_required"` 且 `metadata_encryption_floor = "e2ee_required"`。v1 不存在"明文地板的 PCR"：两条 floor 由 PCR profile baseline 固定，不是 genesis object 的 producer 字段。
  - `created_by` 从 create envelope `actor_id` 派生；genesis `notary` 指向 principal DID，`notary_profile = "single_did"`。
  - genesis `security_class = "high_assurance"`；effective `federation_policy ∈ {closed, restricted, quarantine}` 来自 profile/policy projection。
  - effective `history_visibility = "restricted"`。新授权的同 principal 设备获取 join 前控制历史的 canonical 路径是 durable device-list / normalized principal view baseline 加 policy 受控的 MLS history key share，而非"在当前 epoch 加入"；PCR 不使用 `joined`（`joined` 会让新设备读不到其授权之前的 device / recovery 控制历史）。
- 事件类型由 `ak.profile.principal_control_realm.v1` 的 allowlist 约束：只接受 device / session / KeyPackage / recovery / profile / consent / contact fact / direct conversation binding 等身份基础设施 event；普通 Message / Strand / Space / Morph / Relation / View / Call 协作 event MUST `principal_control_event_kind_forbidden`。
- Native Personal Agent 作为独立 principal 使用自己的 PCR，不得复用 controller PCR id。Agent DID 与 PCR id 的绑定、controller delegation、`actor_id` / `executed_by` authoring 和 agent/controller 控制事实落点以 [`identity/key-management.md` §4.1](../identity/key-management.md) 为权威；realm id 本身按 §2.5.0 通则从 genesis Event 派生，**实现私有的 deterministic id 派生不是验证证据**。Profile allowlist 虽包含 Agent PCR 与 controller PCR 两组 agent-control kind，reducer 必须按 `agent_control_event_placement` 再做落点约束，不能把 allowlist 并集解释成跨 principal 通用写权限。
- 跨 principal 写入（另一个 principal 的 device / session 状态）MUST `unauthorized` reject。
- "私有"语义由 **用途 + event-kind allowlist** 锁定，不是 access control。PCR 在结构上允许 multi-member（该 principal 的所有设备 / agent）。
- **history sharing policy 由 profile 固定，PCR 不声明也不发出（normative）**：PCR 必须 `history_visibility="restricted"`，而 [`../governance/history-visibility.md` §3](../governance/history-visibility.md) 要求 effective `restricted` 必须有一份已接受的 `ak.realm.history_sharing_policy`。但 PCR **无法**发出该 Event——`ak.realm.history_sharing_policy` 不在 profile 的 `realm_event_kind_policy.allowed_event_kinds` 内（`allowlist_only: true`），PCR genesis 是 create + `ak.device.authorize` 的封闭两条 unit（managed Agent PCR genesis 只有一条 create），bootstrap 后的 `recovery_material_pending` gate 又只允许它自己那个封闭写入集合（[`../identity/key-management.md` §5.0.4](../identity/key-management.md)）。因此 effective 值由 profile 提供：`ak.profile.principal_control_realm.v1` 的 `history_sharing_policy_fixed_baseline.value` 是该 PCR 的 effective `ak.realm.history_sharing_policy`，key source 与 reducer MUST 按该字面值求值。对应地：
  - Realm genesis/profile object **MUST NOT** 声明 `history_sharing_policy`（两者 schema 闭合且无此属性，[`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json) 已登记 hard reject）；
  - 向 PCR 提交 `ak.realm.history_sharing_policy` MUST `principal_control_event_kind_forbidden`；
  - baseline 的 `restricted_rules[].range="all_visible_at_t0"` 只是 policy 上界，实际释放区间仍 MUST 按 [`../identity/key-management.md` §5.0.1](../identity/key-management.md) 的 "PCR history key share 释放授权" 收敛到接收设备 accepted `ak.device.authorize` 的 frontier；授权之前的控制历史由 durable device-list / normalized principal view baseline 提供，而不是更早的 epoch key；
  - baseline 不含 `archive_node` / `recovery_service` key source：PCR 是 `high_assurance` 且非 open federation，其历史密钥 MUST NOT 经第三方 archive / recovery 服务恢复；managed Agent PCR 的连续性走 controller 持有的 `mls_history` backup（属 `key_backup` 来源）。
  - 本条的规范执行向量是 `ak.vector.history_sharing.principal_control_profile_baseline.v1`。
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

- "Internal / External" 的判定轴是 **是否含跨信任域成员**，不是 hosting 在哪台 server 上：一个 Realm 由组织自己的 Principal Server 托管，但邀请了外部 Organization DID 的成员——它就是 External Collaboration Realm。
- Sovereign deployment 对 External Collaboration Realm 加的那一组 policy 来自 `ak.profile.sovereign_deployment.v1`，是 **部署 profile** 决定的 policy 配置，不是另一种 Realm 类型。
- PCR 永远是 Internal 的，不存在 "External PCR"：principal DID 与其 control Realm 1:1 绑定，跨域 PCR 在结构上不存在。
- `security_class=high_assurance` 是横切标签，可叠加在 Internal / External Collaboration Realm 与 PCR 上，不属于本分类的一层节点。
- 这套分类是 **prose / glossary 层** 的角色术语，便于跨章节统一指代；底层 schema、reducer、Seal pipeline、Move 处理对三类一视同仁。

#### 2.8.4 Direct Conversation Realm（1:1 DM）

Direct Conversation Realm 是 Collaboration Realm 的受约束形态，不是新的 Realm 类型。完整生命周期见 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md)。

Direct Conversation Realm MUST：

- 使用 `encryption_profile="mls_rfc9420"`；`mls_dm` 不得作为 Realm `encryption_profile` 枚举值出现。
- `content_encryption_floor="e2ee_required"` 且 `metadata_encryption_floor="e2ee_required"`。
- `schema_refs` 同时包含 `ak.schema.realm.v1` 与 `ak.profile.direct_conversation_realm.v1`，并设置 `fields.collaboration_role="direct_conversation"`；两者受 schema 双向 guard 约束。不得复用 `fields.purpose="direct_message"`，因为 `fields.purpose` 已用于 Principal Control Realm。
- `found` 且可发送时 active member count 等于 2；任一 participant 离开、被移除或其它 gate 失败时，同一稳定 DM 投影为 `suspended`，恢复时仍使用原 Realm。向 DM Realm 加第三人 MUST 被拒绝。升级多人聊天必须创建新的普通 Realm / Strand，再用 Relation 或 Message 引用旧 DM 内容。
- `default_join_rule` 为 `closed` 或等价 fail-closed policy。**这里必须区分两件事（normative）**：（a）**bootstrap peer join**——Realm bootstrap batch 内由 creator 写入的第二个成员（pair 的另一方）是 DM Realm 成立的必要步骤，MUST 被接受；它走 authorized-writer 分支（creator 在同批 genesis unit 内使用 staged authority-root proof 取得的 effective `ak.realm.owner`，见 [§2.5](#25-akrealmcreate-reducer-bootstrapnormative)），属于 [`../governance/join-policy.md` §4](../governance/join-policy.md) `closed` 行的封闭豁免列表第 3 项。（b）**向已 active 的 DM Realm 加第三人**——任何第三方 invite / member_add MUST 被拒绝。实现 MUST NOT 把（a）当成（b）拒掉，否则 1:1 私聊永远只有 1 个成员，违反“active member count 等于 2”。
- `ak.space.*` Event MUST 以 `direct_conversation_space_forbidden` 拒绝；额外普通 Strand MAY 存在，但不改变 binding 指定的默认 main Strand。
- 通过一次性 principal-scoped `ak.direct_conversation.bound` fact 绑定 unordered participant pair、`realm_id` 与 `main_strand_id`。同一 `(trust_domain,pair_key)` 只有一组永久坐标，且由 founder 一次 author 的三 Event atomic unit 自身派生（见 [`../identity/contact-and-direct-conversation.md` §5.5](../identity/contact-and-direct-conversation.md)）；不存在服务端预分配 ID、reserved/materializing draft、第二候选或 winner tie-break。
- DM Realm 继续只有一个技术 authority-root controller，但 root 的 operational owner aggregate MUST 与 `ak.profile.direct_conversation_realm.v1` 的 phase mask 求交。founding 之外的普通消息、成员、policy、grant 与 terminal 写不得借 owner 绕过；双方日常写统一从 `ak.authority.direct_conversation_participant.v1` 求值。
- participant authority 只在 immutable binding、恰好两个 stable participant、actor active membership、conversation 未 suspended、Realm/Strand/MLS cross-binding、非终态 scope 与 action-specific gate 同时成立时生效。membership、`created_by`、role/projection mirror 与相同 `pair_key` 都不是其替代来源；authority reset 不使 baseline 失效。
- 基数是同一 trust domain/pair 的 `0..1` stable binding，且一旦 accepted，该 pair 永久复用同一个 Realm 与 main Strand。suspended、rejoin、rekey、恢复或 erasure 都不创建 successor；结果不明的创建只能由 founder 重放逐字节相同的 signed unit，不得重新 author 另一组 Event。

任一参与方主动离开或被移出 DM Realm 后，同一 immutable binding 立即投影为 `suspended`，双方 participant authority 失效，不需要也不得写 retirement fact。后续 `ak.self.direct_conversation.read.resolve` MUST 返回同一 `pair_key`、Realm 与 main Strand；只有恢复所需 authorization basis 后，才可在同一 Realm 执行标准 rejoin/rekey 并恢复为 `found`。resolve 是查询入口，MUST NOT 承载 `create` phase；DM Realm 的唯一创建入口是 [`../identity/contact-and-direct-conversation.md` §5.4](../identity/contact-and-direct-conversation.md) 的 founder-only founding admission。实现不得创建 successor、predecessor-linked binding、竞争 Realm 或历史 segment；旧 epoch/history key 仍逐次按 event-time visibility 与 history-sharing policy裁决。

## 3. Space

### 3.1 概念

Space 是用户和产品层可见的结构容器。它可以表达：

- organization 下的 workspace / project / folder / section
- board / list / swimlane / calendar bucket
- document outline group / page group
- 任意 profile 注册的结构节点

Space **不**拥有自己的 membership、policy、history visibility、E2EE group 或 federation policy。它通过 `realm_id` 和可选 `default_realm_id` 解析到 Realm：

- `realm_id`：该 Space 对象自身 metadata 的 home Realm。创建、更新、archive、tombstone 该 Space 的事件写入这个 Realm。
- `default_realm_id`：该 Space 下新建资源默认落入的 Realm。省略时直接取自身 `realm_id`；协议不递归继承 ancestor 默认值。

这允许 UI 上的同一个 Space tree 跨越多个 Realm。例如 `/Acme/Projects` 下面的普通项目、机密项目和 HR 项目可以是兄弟 Space，但各自 `default_realm_id` 不同。

### 3.2 Schema id 与字段

Schema id: `ak.schema.space.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `ak:space:` 开头。 | Space ID。 |
| `schema` | yes | `ak.schema.space.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | MUST 指向 `ak:realm:`。 | Space metadata 的 home Realm。 |
| `default_realm_id` | no | `id:realm` | MUST 指向 `ak:realm:`。 | 子资源默认 Realm；省略时直接取本 Space `realm_id`。 |
| `scope_circle_id` | no | `id:circle` | MUST 指向 Space metadata home Realm 的 Circle。 | Space 自身 metadata 与 structural relation facts 的 effective scope；省略表示 Realm-default。 |
| `child_scope_policy` | no | `object` | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id`。 | 子资源 placement 的 reducer-enforced 约束。 |
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
| `created_by` | yes | `did_core_id` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did_core_id` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

Space 是 v1 标准协作容器中唯一把顶层 `kind` 用作产品 / 容器子类型的对象：`board`、`list`、`folder` 等都在 Space.kind 表达。Realm 不按 kind 分裂安全边界；Strand 的业务分类也不放顶层 kind，必须通过 schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 表达。View.kind 是投影响应族，不表示协作容器类型。

### 3.3 行为规则

- **授权**：任何对 Space 的写入（`ak.space.create` / `ak.space.update` / `ak.space.archive` / `ak.space.restore` / `ak.space.tombstone` / `ak.space.parent`）都在 `realm_id` 指向的 home Realm 内授权。
- **同步与联邦**：Space metadata 跟随 home Realm 同步。跨 Realm parent 只是可验证引用，不把 child metadata 合并到 source Realm 的 event frontier。
- **加密 / scope**：Space 没有自己的 membership、Policy Server 或 MLS group。Space metadata 默认取决于 home Realm 的 scope、`encryption_profile` 与 metadata profile；若 `scope_circle_id` 指向 Circle，则 Space metadata 与对应 structural relation facts 落在该 Circle 的 existing scope，并继承该 Circle 的投递 / 查询裁剪与 encryption profile。
- **导航**：Space hierarchy 是产品结构树 / DAG。遍历每个 Space 节点时 MUST 独立校验该节点 home Realm 的可见性。
- **默认资源边界**：创建 Strand / Morph / View / Blob 引用等资源时，客户端 MUST 显式写入 `realm_id` 与需要的 `scope_circle_id`；`default_realm_id` 只提供 Realm 初值。若 Space tree 的 home Realm 与默认子资源 Realm 不同，不能用 home Realm 的 Circle 作为子资源 scope。
- **子边界升级**：若 Space subtree 或单个 Strand 只需要 Realm 内的子事件 / 子消息边界，创建 Circle，并让子资源显式写入 `scope_circle_id`，必要时用 `child_scope_policy` 强制指向该 Circle；若还需要密码学隔离，则该 Circle 必须 MLS-backed。只有需要独立 federation / Policy Server / capability registry 时才创建新的 Realm。

**两字段速查表（normative）**：Space 上两个 scope 相关字段语义不同，分别由 reducer 强制：

| 字段 | 语义 | 谁强制 |
| --- | --- | --- |
| `Space.scope_circle_id` | 本 Space 自身的 effective scope | reducer（写本 Space 时校验） |
| `Space.child_scope_policy.require_scope_circle_id` | 子资源 scope 的 reducer-enforced 约束 | reducer（写子资源时校验） |

这两个字段不是冗余：自身 scope ≠ 子资源约束，实现 MUST 分别消费。

### 3.4 Lifecycle 与 Cascade 规则

Space lifecycle 只影响结构容器，不影响 Realm membership、E2EE group 或 history visibility。

- `ak.space.archive`：把 Space 设为 `archived`，默认 UI 隐藏；不自动 archive child Space 或内部 Strand。
- `ak.space.restore`：仅允许 `archived -> active`；不级联 restore。
- `ak.space.tombstone`：不可逆；在存在 live child Space 或 live `contains` placement 时 MUST `failed_precondition`。

错误码 MUST 使用 `space_not_active`、`space_not_archived`、`space_has_live_dependents`、`space_already_terminal`。

### 3.5 `ak.space.parent` cas_register basis

`ak.space.parent` 写入 cell：

```text
cell_id := ak:cell:ak.component.space.parent.v1:<space_id>
lattice := cas_register
bottom  := reject
value   := id:space | null
```

**Plane 裁决（normative，CBA）**：与 §3.6 `ak.component.strand.position.v1` 同型，`ak.space.parent` 的默认裁决是 **`plane := control`（`sealed=true`，升控制面）**——这保留下表 `cas_register` / `bottom=reject` / `head_eq` CAS basis 的全部语义不变。因此 `ak.space.parent` 是 **Control Move**（携带 `seal_basis`，**不**携带 `seal_ref`，由 Seal 裁决），而非 data-plane DataEvent：按 [`event-and-patch.md` §2.2](./event-and-patch.md) DataEvent MUST NOT 携带 preconditions，且 [`event-auth-state-resolution.md` §9.1](../authz/event-auth-state-resolution.md) 中 `cas_register` 在 data plane 默认不可用、`bottom=reject` 是控制面 / sealed 语义，带 `head_eq` CAS + `bottom=reject` 的 `ak.space.parent` 结构上只能是 Control Move。Realm schema MAY 按 §9.4 三选一改声明为 data-plane `mv_register`（并发 reparent 暴露多 heads、任意写权限者一笔收敛、无协议 `⊥`）或 per-object sequencer；改声明后 `head_eq` 退化为诊断字段。`event-kind-registry.json` 中 `ak.space.parent` 行的 plane/sealed 语义以本节为准。

规则：

- 首次 set 使用 `head_eq null`。
- reparent 使用 `head_eq <expected_parent_space_id>`；该名称与 `ak.space.parent` payload 字段一致。
- 并发 reparent 返回 `⊥`，后续 Move fail closed，必须走 conflict recovery。
- `parent_space_id == this_space_id` MUST `schema_violation`。
- Reducer 在接受 `ak.space.parent` 前 MUST 以候选新 parent 链执行确定性 acyclic 检测；若 `space_id` 再次出现在 ancestor 集合中，MUST 以 `failed_precondition`、`reason_code=space_parent_cycle` 拒绝。跨 Realm parent 同样参与检测；任何 ancestor 不可读取或缺少可验证 parent proof 时 MUST 以 `failed_precondition`、`reason_code=space_parent_unreadable` fail closed，不得假设无环。
- `parent_space_id=null` 表示移动到 root。不可读 parent 的 projection MAY 返回 `{parent_space_id_hidden:true}`，但 MUST NOT 伪造 root。
- parent Space MAY 位于不同 Realm；这只影响导航，不传播 membership、capability、history、E2EE key 或 retention policy。

### 3.6 Strand 位置

Strand 在 board/list 类 Space 中的位置仍由 cas_register cell 维护：

```text
cell_id     := ak:cell:ak.component.strand.position.v1:<board_space_id>:<strand_id>
lattice     := cas_register
bottom      := reject
plane       := control（默认 sealed=true）
value shape := { "list_space_id": id:space, "rank": string } | null
```

**Plane 裁决（normative，CBA）**：`ak.component.strand.position.v1` 是非治理强一致对象，按 [`event-auth-state-resolution.md` §9.4](../authz/event-auth-state-resolution.md) 三选一。**默认裁决是选项 2（`sealed=true` 升控制面）**——这保留上表 cas_register / bottom=reject / `expected_position` CAS basis 的全部既有语义不变，`ak.strand.move` / `ak.strand.reorder` 因此是 Control Move（携带 `seal_basis`，由 Seal 裁决）。Realm schema MAY 改声明为选项 1（data plane `mv_register` + user-pick：并发拖动暴露多 heads，任何有写权限者一笔写收敛、无协议 `⊥`）或选项 3（per-object sequencer）；改声明后 `expected_position` 退化为诊断字段。看板拖动延迟敏感、且 Realm 接受多值短暂并存的部署 SHOULD 评估选项 1。

`ak.strand.move` payload 是 closed object（未知字段 MUST `schema_violation`）：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `board_space_id` | yes | `id:space`（Board） | position edge 的所属 Board；与 `strand_id` 共同构成去重 key。 |
| `strand_id` | yes | `id:strand` | 被移动的 Strand。 |
| `from_space_id` | no | `id:space`（List） | 源 List；省略时 reducer 从当前 active edge 推导。 |
| `target_space_id` | yes | `id:space`（List） | 移动后的目标 List；payload 不得另带 `list_space_id`。 |
| `rank` | yes | `string` | 目标 List 内 canonical rank。 |
| `expected_position` | no | `object{space_id?: id:space, rank?: string, relation_id?: id:relation}` | 可选 CAS 诊断前像；字段集封闭。 |

默认规则：workflow placement MUST resolve to the same effective Realm as the Strand unless a profile explicitly declares a cross-Realm reference relation. 跨 Realm 展示可以通过 Relation / View 聚合完成，但不得把目标 Realm 的读权隐式带入源 Realm。

### 3.7 示例

Project Space：

```json schema=schemas/space.schema.json
{
  "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
  "schema": "ak.schema.space.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "default_realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "kind": "project",
  "title": "Website Redesign",
  "created_by": "ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw",
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

Confidential sibling Space：

```json schema=schemas/space.schema.json
{
  "id": "ak:space:AScD0xd0vWSGWhC2n9BZHco7N_jYnNgmEIifpAo_uxUJ",
  "schema": "ak.schema.space.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "default_realm_id": "ak:realm:AZUa8SJ6PUaPKeLjKKRW64JmDpKE7X-1KZHajF0_it8p",
  "parent_space_id": "ak:space:AUwbeCUMZI_GuEADljowhvFwzl6wIkaSiCDhu2oaOqTg",
  "kind": "project",
  "title": "Pricing Strategy",
  "created_by": "ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw",
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
- CBA / Lattice：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- `ak.strand.move` / cas_register sync 编译：[`../sync/operations-sync.md`](../sync/operations-sync.md)。
- Realm genesis/profile/effective projection 与 Space schema：`artifacts/schemas/realm-genesis.schema.json`、`artifacts/schemas/realm-profile.schema.json`、`artifacts/schemas/realm.schema.json`、`artifacts/schemas/space.schema.json`。
