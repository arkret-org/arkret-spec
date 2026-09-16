---
title: Standard Event and Object Schema Registry
status: candidate
normative: true
stability: v1
updated: 2026-07-30
sidebar:
  label: Schema Registry
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与真源

> **本文是 documentation view，不是 schema/event 真源。**
> 下方 §2 schema id 表与 §4 event kind 表是**人工维护的阅读节选**，并非穷尽清单；两者与机器 registry 不一致时一律 **以 JSON registry 为准**。"本文定义"的措辞仅指文档级别的展示视图。穷尽且 canonical 的清单是 `artifacts/registry/*.json`（站点经 MDX 组件 `<EventKindTable/>` / `<SchemaViewer/>` 等直接渲染这些 JSON）。
> 修改流程:`contract-registry.json` → `tools/artifact_pipeline.py generate` → 刷新各 `*-registry.json`。pipeline 不改写本文 md 表；新增 / 改名概念时如需在本节节选表体现，MUST 手工同步对应行，但本节表的滞后**不**改变「JSON registry 为唯一真源」这一结论。

字段级结构定义见 `../models/common-fields.md` 及各对象专属文件（`realm-and-space.md` / `strand-and-message.md` / `morph.md` / `relation.md` / `actor.md` / `governance-objects.md` / `private-objects.md` / `event-and-patch.md`）。

机器可读真源(authoritative，本文表格只是其投影):

- `artifacts/registry/contract-registry.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/track-name-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/operation-registry.json`
- `artifacts/registry/error-code-registry.json`

其中 `error-code-registry.json` 是标准 service error code 与批处理逐项 `reason_code` 的 canonical registry；本文后续 event/schema 表只提供文档视图，不重复维护错误码全集。

`track-name-registry.json` 是 `contract-registry.json#track_name_registry.track_names`
生成的唯一 TrackName 视图。`Strand.tracks`、track-scoped constraint、正文与 conformance
vector MUST 使用同一 active 集合；owner 的 `schema_ref` / `profile_id` 必须可解析，未登记名称
一律 fail closed。

各 registry（schema / event kind / typed ID / operation / profile）的**当前 registered 计数及其 CI 门禁**（由 `tools/artifact_lint` 的 `check_release_readiness_counts` 对照 Canonical registry 自动校验）集中登记在 [`overview/release-readiness.md` §2](../overview/release-readiness.md) 的计数表；本文不重复维护计数，引用时以该表与各 Canonical JSON registry 为权威来源。

### 1.1 schema id ↔ 文件名映射例外（normative）

下游 SDK / IDE 插件不得用 "schema id 去掉前缀 + 换分隔符" 这种机械推导拿文件名；MUST 从 `schema-registry.json` 读取每条 `{schema_id, file, 可选 fragment}` 三元组。**effective schema reference = `file` + 可选 `fragment` 的逐字拼接**：`fragment` 自身已带前导 `#`，消费者不得再插入分隔符。例如 `file="schemas/agent-operations.schema.json"` 与 `fragment="#/$defs/agent_pairing_bootstrap"` 的结果精确为 `schemas/agent-operations.schema.json#/$defs/agent_pairing_bootstrap`。`fragment` 是 RFC 6901 JSON Pointer 的 URI-fragment 表示；消费者 MUST 解析其指向的子 schema，MUST NOT 把该 `schema_id` 绑定到 `file` 的顶层文档。`fragment` 省略时 effective reference 即 `file` 顶层文档。两个 `schema_id` 映射同一 `file` 时 MUST 靠 `fragment` 区分（或其一省略 `fragment` 表示整包）；忽略 `fragment`、对带 fragment 的行加载顶层文档的实现**不合规**。`fragment` 不可解析、或共用同一 `file` 的多行都省略 `fragment`（整包映射歧义）时，消费者 MUST fail closed，不得静默择一。该规则的机读声明见 `schema-registry.json` 的 `registry_rules`。当前 v1 已知的不能机械推导的对应关系：

| schema id | canonical effective reference | 说明 |
| --- | --- | --- |
| `ak.schema.event.v1` | `schemas/event-envelope.schema.json` | schema id 用 `event` 保持协议对象名，文件名用 `event-envelope` 对齐 wire envelope 术语；不得机械推导为 `event.schema.json`。 |
| `ak.schema.capability.v1` | `schemas/capability-grant.schema.json` | id 简化为 `capability`，文件保留 `capability-grant` 以区别于其他 capability 相关 schema（grant-constraint、resource-selector 等）。 |
| `ak.schema.morph.customer_risk.v1` | `schemas/morph-customer-risk.schema.json` | id 用 dot 分段（`morph.customer_risk`），文件用 dash（`morph-customer-risk`）；对应规则是 "schema id 里的每段都换成 dash"。其它 dotted-id schema 适用同一规则。 |
| `ak.schema.agent_pairing_bootstrap.v1` | `schemas/agent-operations.schema.json#/$defs/agent_pairing_bootstrap` | 与 `ak.schema.agent_operations.v1` 共用文件，但必须解析 `fragment` 指向的bootstrap 子 schema（含 runtime_identity），不得加载顶层 DTO `oneOf` bundle。 |

新增 schema 时如果出现不能机械推导的命名，必须把对应关系登记到 `contract-registry.json` 的 `schemas[]` 条目，并在此表格补充一行；不得只改文件名。

### 1.1.1 error code 命名空间例外（normative）

`error-code-registry.json` 中的 `code` / `reason_code` 值有意使用裸名（例如 `json_invalid`、`policy_violation`、`failed_precondition`），不加 `ak.` 前缀。错误码只在 service response、batch item 诊断和 reducer reason 上下文中解释，不与 event kind、operation id、schema id 或 capability action 共用命名空间。跨规范聚合错误时，调用方 SHOULD 用 registry 文件或 protocol 名称作为外层 namespace，而不是把 `ak.` 前缀补进 wire code。

新增标准错误码必须继续登记在 `error-code-registry.json`，不得因为本例外而在其它 registry 里注册裸名 action / event / operation。

**`codes` vs `reason_codes` 与双注册模型（normative）**：`error-code-registry.json` 有两个并列数组，语义不同:

- **`codes`**:可作为**顶层 service error** 返回的码，携带 `http_status` 与 `scope`（`both` / `service_call` / `delivery` / `endpoint`）。
- **`reason_codes`**:per-item / per-decision 的**子原因**（batch item 诊断、reducer reason、auth/policy decision reason），不携带 `http_status`，由 `applies_to` 声明适用上下文。

一个 token 同时扮演两种角色时（既能作顶层服务错误返回、又能作某条目的子原因），**MUST 在两个数组中各登记一次（双注册）**，两处描述 SHOULD 一致并互相点明"dual-registered"。双注册是有意设计、不是漂移；新增码若兼具两种角色，MUST 保持两侧同步。算法-agility fail-closed 四项 `unsupported_digest_algorithm` / `unsupported_signature_alg` / `unsupported_hpke_suite` / `unsupported_ciphersuite` 即按此模型对称双注册（`codes` 均 `http_status=422` / `scope=both`，且各自在 `reason_codes` 有对应 per-item 条目），确保 digest / signature / HPKE / MLS ciphersuite 四类未识别 selector 的处置在 registry 中口径一致。

### 1.2 `ak.*` 命名空间的机读登记边界（normative）

并非所有 `ak.*` 标识符都要求进入机读 registry。下列命名空间类别**豁免机读登记**，其权威定义由各自的定义文档承载；豁免类别之外、被正文当作真实 wire 标识符使用的 `ak.*` id 仍 MUST 有机读归属（registry、schema const 或 profile 矩阵），缺失即为漂移缺陷：

| 豁免类别 | 例子 | 权威定义位置 |
| --- | --- | --- |
| 算法 / 编码 profile id | `ak.rank.lexofractional.v1`、`ak.reducer.core.v1` | 定义文档（encoding.md §9、realm-state-snapshot-schema.md）；它们不是 conformance profile，不进 conformance-profiles.json |
| client-local scheme id（不进 wire 互操作面） | `ak.secret_storage.v1`、secret storage 的 `ak.mls.v1` | device-lifecycle.md / key-management.md |
| 信封 scheme 常量 | `ak.blob.presign.v1` | media-and-blob.md §5.4.2（与已进 schema const 的 scheme 并存是允许的；进 schema const 后以 schema 为准）。**例外**：HPKE 封装 suite id（`ak.hpke_*`）已进 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json)，按 registered 算法 agility suite 处理（与 signature / digest / mls-ciphersuite registry 并列），**不属**本豁免类别。 |
| hash / transcript 域分隔标签 | `ak.agent_sidecar_circle.v1`、`ak.invite.claim.binding_proof.v1`、`ak.invite.claim.subject_proof.v1` | 使用处定义文档（MLS exporter label 除外——它有专属 exporter-label-registry） |
| feature id（`supported_features` / `supported_features` 值） | `ak.feature.identity.webvh_native_log.v1` | service-surface.md 与对应能力文档；feature id 是 describe 协商值 |
| DID Document / 外部生态 profile 值 | `ak.organization.governance.v1` | identity-did.md 示例上下文 |
| E2EE MLS content type | `application/vnd.arkret.identity-link+json` | 定义文档（history-visibility.md）；其 plaintext schema（`ak.schema.identity_link.v1`）仍 MUST 注册，content type 本身不进 durable event registry |
| Signal plaintext payload kind | `ak.presence`、`ak.typing`、`ak.receipt.read`、`ak.call.signal`、`ak.message.stream` | [`../sync/signal.md` §1.1](../sync/signal.md) 的封闭登记表；每个 kind 的 closed plaintext schema 仍 MUST 注册（`ak.schema.signal_presence.v1` / `ak.schema.signal_typing.v1` / `ak.schema.read_receipt.v1` / `ak.schema.call_signal_plaintext.v1` / `ak.schema.signal_message_stream.v1`），kind 本身位于 ciphertext、不进 event-kind registry，也不分配 `wire_scope` |
| 标准 account-data tag 词表 | `ak.favorite` | client-preferences.md §3.1（标准 tag 词表；tag 是加密 account data 内的私有分组标签，不进 wire registry） |

### 1.3 Interop 命名空间例外

以下名称来自外部互通协议的固有术语，不属于 Arkret core 模型命名。`forbidden-wire-fields.json` 与 registry lint 只允许它们出现在登记的 interop 模块上下文中，授权 / 解析逻辑不得把这些术语提升为 core model 概念：

| 名称 | 当前语义 | 允许理由 | 防护参考 |
| --- | --- | --- | --- |
| operation id `ak.open.mimi.command.update_room.v1` | MIMI interop 命名空间内的标准操作；`room_update` 中的 `room` 术语与上游 MIMI 规范对齐 | 仅在 MIMI interop module 内部使用，不污染 core | `forbidden-model-terms.json` 把 `Room` 列为 `interop_module` allowed context |
| `Room visibility` | 外部 Matrix/MIMI 互通文档中引用的上游术语；Arkret core 必须拆成 discoverability / join rule / history visibility 三轴 | 仅允许在 interop module 中说明外部语义映射，不得作为 Arkret core 字段或 policy 名 | `forbidden-model-terms.json` 把 `Room visibility` 列为 `interop_module` allowed context |

新增 interop 命名空间例外必须在此表登记并在对应 schema / registry 内联说明允许理由；不得仅靠口头约定。下游漂移扫描器 SHOULD 把此表作为 interop-only allowlist。

## 2. Standard Object Schema

| schema id | kind |
| --- | --- |
| `ak.schema.realm.v1` | Realm |
| `ak.schema.space.v1` | Space |
| `ak.schema.actor_profile.v1` | Actor Profile |
| `ak.schema.agent_selector_claim.v1` | Controller-scoped Agent selector claim |
| `ak.schema.circle.v1` | Circle (intra-Realm scoped event/message boundary; see [`../models/circle.md`](../models/circle.md)) |
| `ak.schema.agent_sidecar.v1` | Agent Sidecar (controller-owned private AI workspace; see [`../models/sidecar.md`](../models/sidecar.md)) |
| `ak.schema.agent_sidecar_view_state.v1` | Controller-private encrypted per-context Sidecar display/view state (see [`../models/sidecar.md` §7](../models/sidecar.md)) |
| `ak.schema.agent_sidecar_exchange_projection.v1` | Controller-device-local source-routed exchange Event-fold cache/SDK DTO；非 Account Data / wire truth（见 [`../models/sidecar.md` §7](../models/sidecar.md)） |
| `ak.schema.agent_sidecar_event_exchange_binding.v1` | Sidecar-scoped Message encrypted metadata 内的 closed exchange producer binding（见 [`../models/sidecar.md` §8](../models/sidecar.md)） |
| `ak.schema.agent_sidecar_exchange_control.v1` | `ak.agent.sidecar.exchange.control` 的加密明文；coordinator 重分配与终态的 durable truth（见 [`../models/sidecar.md` §8](../models/sidecar.md)） |
| `ak.schema.strand.v1` | Strand |
| `ak.schema.message.v1` | Message |
| `ak.schema.content_block_poll.v1` | Poll Content Block |
| `ak.schema.morph.v1` | Morph |
| `ak.schema.relation.v1` | Relation |
| `ak.schema.view.v1` | View |
| `ak.schema.policy.v1` | Policy |
| `ak.schema.invite.v1` | Invite |
| `ak.schema.read_cursor.v1` | Read Cursor |
| `ak.schema.notification.v1` | Notification |
| `ak.schema.capability.v1` | Capability Grant |
| `ak.schema.event.v1` | Event Envelope |
| `ak.schema.event_payload.v1` | Standard Event Payload Classes |
| `ak.schema.event_batch_receipt.v1` | Event Batch Receipt |
| `ak.schema.cursor.v1` | Cursor |
| `ak.schema.realm_state_snapshot.v1` | Snapshot Manifest |
| `ak.schema.realm_state_snapshot.v1` | Authority-signed typed current snapshot、per-stream heads、history floors 与 chunk digests |
| `ak.schema.grant_constraint.v1` | Grant Constraint |
| `ak.schema.resource_selector.v1` | Resource Selector |
| `ak.schema.identity_resolution.v1` | did_core_id/did resolution、PCR evidence 与 AuthenticatedServiceResolution |
| `ak.schema.identity_receipt.v1` | Identity Receipt |
| `ak.schema.identity_link.v1` | Minimal-metadata E2EE identity link |
| `ak.schema.handle_claim.v1` | Handle Claim |
| `ak.schema.realm_join_candidate.v1` | Realm join candidate routing hint |
| `ak.schema.media_metadata.v1` | Media Metadata |
| `ak.schema.read_receipt.v1` | Read Receipt Signal plaintext（`ak.receipt.read`；见 [`../sync/signal.md` §1.1](../sync/signal.md)） |
| `ak.schema.blob.v1` | Blob Metadata |
| `ak.schema.encrypted_envelope.v1` | MLS Encrypted Payload Envelope |
| `ak.schema.account_data_encrypted_value.v1` | Principal-private Account Data AEAD envelope |
| `ak.schema.key_backup.v1` | Encrypted Key Backup |
| `ak.schema.recovery_policy.v1` | Principal Recovery Policy |
| `ak.schema.recovery_session.v1` | Device Recovery Session |
| `ak.schema.recovery_receipt.v1` | Recovery Receipt |
| `ak.schema.account_subscribe_frame.v1` | Account Subscribe Frame |
| `ak.schema.device_message.v1` | To-device Message Envelope |
| `ak.schema.applet_registration_epoch_transcript.v1` | Closed Applet registration epoch security transcript |
| `ak.schema.mimi_interop.v1` | MIMI Provider Directory / MIMI Room Binding (interop; see [`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)) / Mapping Receipt |
| `ak.schema.moderation_report.v1` | Moderation Report |
| `ak.schema.moderation_queue_item.v1` | Moderation Queue Item |

## 3. Event Type 设计约束

### 3.1 命名规则

- 标准事件必须使用命名空间：`ak.<domain>[.<subdomain>].<verb>`。
- 所有标准事件必须是 `ak.` 前缀。
- 裸名事件（例如 `realm.create`）不是标准事件。
- 自由字符串事件（如 `custom.*`）不能直接登记标准事件，需要通过自定义 schema + capability / state filter 映射。

### 3.2 wire scope 语义

完整 event kind 集合以 `artifacts/registry/event-kind-registry.json` 为准。`wire_scope` 语义如下：

- `durable_event`：进入共享 Event Envelope 历史，参与 reducer。
- `actor_private_event`：进入加密 account data 或 actor-private stream。

SignalEnvelope 与 DeviceMessageEnvelope 不属于 Event kind registry，因此不分配 `wire_scope`。
Signal plaintext payload kind（`ak.presence` / `ak.typing` / `ak.receipt.read` / `ak.call.signal` /
`ak.message.stream`）因此**不出现在** §4 的 event kind 文档视图中；其封闭登记表见
[`../sync/signal.md` §1.1](../sync/signal.md)，豁免依据见 §1.2。

实现不得仅靠本文件定义；必须加载机器 registry 或等价生成产物。

## 4. Event kind 注册表（文档视图）

### 4.1 Realm 与 Strand

| event type | payload |
| --- | --- |
| `ak.realm.create` | Realm create |
| `ak.realm.profile` | Realm profile facet |
| `ak.realm.alias` | Realm alias declaration or durable value tombstone（alias 的唯一 wire 承载） |
| `ak.realm.upgrade` | Realm reducer profile upgrade |
| `ak.realm.organization` | Organization-authorized Realm relationship statement or revocation |
| `ak.realm.link` | Typed Realm link graph edge |
| `ak.realm.inheritance_policy` | Policy inheritance declaration from a source Realm (subject=`payload.source_realm_id`) |
| `ak.realm.join_rule` | Join rule state |
| `ak.realm.history_access` | History visibility state |
| `ak.realm.discovery` | Discoverability state |
| `ak.realm.preview_policy` | Preview / peek policy state |
| `ak.realm.policy` | Closed reference to one independently defined Policy object (`payload.value.policy_id`); inline Realm facets use `ak.realm.policy_bundle` or their dedicated Event kinds |
| `ak.realm.read_receipt_policy` | Realm read receipt disclosure policy state |
| `ak.realm.tombstone` | Terminal Realm tombstone or replacement marker |
| `ak.realm.archive` | Reversible archive state |
| `ak.realm.freeze` | Temporary freeze state |
| `ak.realm.destroy` | Terminal decommission marker |
| `ak.member.state` | Membership state |
| `ak.strand.create` | Strand create |
| `ak.strand.update` | Strand patch |
| `ak.strand.archive` | Strand archive |
| `ak.strand.restore` | Strand restore |
| `ak.strand.move` | Strand move between Lists |
| `ak.strand.reorder` | Strand reorder within List |
| `ak.strand.tracks.update` | Strand tracks map patch（`ak.schema.patch.v1` payload；详见 [`../models/strand-and-message.md` §4.8](../models/strand-and-message.md)） |
| `ak.strand.watch.set` | Set / clear per-(strand, actor) watch subscription；authority按 commit顺序更新 typed current并派生 `watches` Relation |
| `ak.space.create` | Space create (board / list / swimlane / calendar bucket / ...) |
| `ak.space.update` | Space metadata patch |
| `ak.space.parent` | Space parent declaration；authority按 commit顺序执行 cycle/depth gate |
| `ak.space.archive` | Space archive (reversible UI hide) |
| `ak.space.restore` | Space restore (archived -> active; only valid when current state == archived) |
| `ak.space.tombstone` | Space tombstone (irreversible; contained Strands MUST be relocated first) |

### 4.2 消息与关系

| event type | payload |
| --- | --- |
| `ak.morph.create` | Morph create |
| `ak.morph.update` | Morph patch |
| `ak.morph.archive` | Morph archive |
| `ak.morph.restore` | Morph restore |
| `ak.container.move_item` | Profile-declared container item move |
| `ak.container.rebalance` | Profile-declared container rank rebalance |
| `ak.message.create` | Message create |
| `ak.message.revise` | Message edit patch |
| `ak.message.redact` | Message-scoped redaction |
| `ak.relation.create` | Relation create |
| `ak.relation.update` | Relation patch |
| `ak.relation.tombstone` | Relation tombstone |
| `ak.reaction.add` | Reaction add |
| `ak.reaction.remove` | Reaction remove |
| `ak.read_cursor.advance` | Read cursor advance event |

### 4.3 授权与治理

| event type | payload |
| --- | --- |
| `ak.capability.grant` | Grant |
| `ak.capability.revoke` | Revocation |
| `ak.capability.derived` | Derived capability state |
| `ak.profile.create` | Actor profile create |
| `ak.profile.update` | Actor profile patch |
| `ak.profile.realm_override` | Realm-scoped profile override |
| `ak.audit.accessed` | Auditable access |
| `ak.self.moderation.report` | Moderation report |
| `ak.session.grant` | Session grant |
| `ak.device.authorize` | Device authorization |
| `ak.device.revoke` | Device revocation |
| `ak.device.list_update` | Device list update |

### 4.4 加密、协作与扩展

## 5. Extension 约定

自定义 schema id SHOULD 使用反向域名前缀：

```text
com.example.schema.foo.v1
```

自定义 event type MUST NOT 使用 `ak.` 前缀，除非被正式纳入标准注册表。

## 6. 演进约束

Schema evolution MUST：

- 保留 schema 显式声明扩展位中的未识别字段（规则见下），不得静默剔除
- 不修改既有字段语义
- 可选字段应先于必填字段添加
- reducer 行为变化需提供变更说明
- 若变更授权、可见性、排序或收敛语义，需声明新 schema 或 reducer profile

v1 canonical object（Event Envelope / RealmCommit / Operation / Snapshot / Grant / encrypted envelope）的 schema 是封闭的（`additionalProperties: false`）：schema 未声明的未知字段 MUST 被 schema validation 以 `schema_violation` 拒绝，**不存在**“接受并保留任意未知字段”的隐式路径。Event kind-bound payload 不允许 `{}` 空 schema：有限 family 必须由 payload schema直接以 `$ref` / `oneOf` 闭合。扩展只能使用该具体 payload显式声明的 `x_*`/extension member或新的 versioned kind/schema；Event顶层不再提供通用 `requirements` 或 `unsigned` 逃生口。`ak.schema.define.value` 的 wrapper仍 closed且 `value`必填，schema identity唯一取自 `value.$id`。receiver MUST执行 [`payload-validator-profile-registry.json`](../../artifacts/registry/payload-validator-profile-registry.json) 的定义校验 profile。对 schema允许但实现未识别的显式扩展内容，接收方必须在 canonical bytes、存储、转发和签名校验中原样保留。

未知 critical feature MUST fail closed。能力协商只来自 ServiceDescribe、Realm current policy、kind/schema registry 及具体 typed payload 声明。

OpenAPI DTO MAY 使用 `additionalProperties: false`。若 DTO 内嵌 canonical protocol object，内嵌对象 MUST 按 registry schema 解析，并按本节规则处理：未声明字段拒绝，显式扩展位内容保留。

### 6.1 注册表条目演进兼容级别（normative）

上文覆盖字段级演进；本节回答**值集级**演进：event kind、error code、闭集枚举等新增合法值时的兼容级别，以及已发布实现的处置义务。判定的第一步是区分值集的权威承载形态（与 §1.2 的机读归属规则同源）；同一 token 不得同时以两种承载形态声明。

**a. 开放注册集（open registry set）**——以独立 registry JSON 承载的字符串值集合：event kind（`event-kind-registry.json`）、error `code` / `reason_code`（`error-code-registry.json`）、relation kind（`relation-kind-registry.json`）、capability action、typed id kind（`id-kind-registry.json`——typed ID 前缀为 wire 字符串值集，新增 kind 向后兼容，与同源 generated 的 event kind / capability action 同类）、feature id 等。

- 新增条目是**向后兼容演进**（minor）：只体现在 registry 的 `version` / `generated_at` 推进，不要求新 schema 版本，也不要求 schema profile bump。
- registry / profile 的规范内容发生任何变化时，顶层 `version` MUST 推进；若该 artifact 携带 `generated_at`，该时间戳也 MUST 推进且日期必须与 date-shaped `version` 一致。`tools/check_artifact_versions.py` 的内容摘要排除这两个元数据字段，并把其余内容绑定到受版本控制的 reference manifest；内容变化但元数据未推进、或 metadata/content reference 漂移，均 MUST 使 release gate 失败。
- 已发布实现遇到不在其本地 registry 快照中的值时，MUST 按**未知值保留**处理：不得因此让整个对象 / 信封反序列化失败。反序列化层保留之后的语义处置按各消费面既有规则执行——未知值保留**不等于**语义接受：写入权威接收方对未声明支持的标准 event kind 仍按 [conformance-profiles.md §2.1](./conformance-profiles.md) 返回 `unsupported_feature` / `unsupported_event_kind` / `schema_violation` 或 quarantine；未注册 relation kind 按 relation-kind-registry `registry_rules` 保留为 opaque edge 且不得推断语义；fail-closed 门（未知 critical feature、授权判定）照常适用。
- 生成代码 SHOULD 为开放注册集值提供 non-exhaustive / `Unknown(String)` 兜底变体，MUST NOT 用封闭 enum 让未知值导致整体反序列化失败。

**b. schema 内闭集枚举（closed enum）**——由 JSON Schema `enum` 关键词在 canonical schema 中承载的封闭值集：如 Actor Profile 的 `actor_kind`（`user` / `organization` / `team` / `agent` / `bot` / `service` / `integration`）、cursor 的 `purpose`（`stream` / `barrier`）。

- 已发布 stable schema 向闭集枚举新增值 MUST 伴随对应 schema 版本 bump，并经 §6 的变更说明流程反映到 `conformance-profiles.json#profile_requirements` 的 `required_schemas`。尚未发布的 current-v1 candidate 在冻结前发现分类错误时 MUST 直接修正 current-v1 canonical schema、fixtures、SDK 与全部 consumer，不得为未发布错误保留 compatibility alias 或另造 v2。
- 已发布旧实现对新值按 `schema_violation` 硬拒是**合规行为**，不是互操作缺陷；发起方在对端未声明新 schema 版本前 MUST NOT 发送新值（能力交集原则）。
- 生成代码 MAY 用封闭 enum 类型（无 Unknown 兜底）表达闭集值；闭集枚举值导致的反序列化失败不违反 a 条的"未知值保留"义务——该义务只适用于开放注册集。

**b.1 registry-backed schema selector（算法 agility 的唯一分类）**——signature、digest、HPKE 与 MLS ciphersuite registry 是算法 token 与参数元组的唯一机器词表，但具体 canonical object schema 中的 selector 仍是**按 schema 版本冻结的闭集**，不属于 a 类开放注册集。"enum 由 active rows 生成"只允许发生在创建或 bump 该 canonical schema 版本时；registry release 不得原地扩写已发布 schema 的 enum。

- reserved 算法行翻为 active 前，MUST 先发布包含该值的新 schema 版本、更新 profile `required_schemas` / capability negotiation，并满足 registry 的全部 activation requirements；旧 schema 的 enum 与签名字节保持不变。
- producer 只有在对端声明新 schema 版本与相应算法 profile 后才可发送新 selector。旧 schema receiver 拒绝该新值是合规的版本协商结果。
- 已选定 schema 版本后，selector 不在该版本 enum 内时，receiver MUST fail closed。对已知算法 selector 字段，错误映射优先使用对应稳定码 `unsupported_digest_algorithm` / `unsupported_signature_alg` / `unsupported_hpke_suite` / `unsupported_ciphersuite`；对象其它闭集 enum 违例仍使用 `schema_violation`。预解析器 MAY 保留原始字符串用于形成该错误，但不得把 Unknown 变体交给 reducer 或密码学库执行。
- SDK/codegen 对这些 selector MUST 生成 per-schema-version 的封闭类型；可在 transport diagnostic 层提供 `Unknown(String)` 以承载稳定错误，但该值不得构造为已通过 schema 验证的 canonical object。registry consumer 不得把"registry 中 active"误解为"所有旧 schema 自动接受"。

**c. `status` 字段纪律**——`schema-registry.json` 的 schema 条目只允许 `active`；未知或非 active 状态一律 fail closed，不存在为了旧数据解析而保留的 schema 行。省略 `status` 的 source row按 `active` 解释；新增或修改 schema 行 MUST 显式写出 `status`。其它 registry 若定义 `profile_extension` 等状态，只在其自身 closed contract 内有效，不得套用到 schema registry。

- 新增条目 MUST 以 `active`（或 `profile_extension`）登记进 canonical 真源（generated registry 一律经 `contract-registry.json` → pipeline 再生成，见 §1）。
- schema registry 只包含 current-v1 的 active canonical 条目；解析必须精确命中登记的 schema id 与 shape。
  历史快照不属于当前 schema registry 的输入，消费者 MUST 只接受当前 registry 声明的 shape。

### 6.2 禁字段的机读上下文（normative）

`forbidden-wire-fields.json` 的 `context_definitions`、`context_matching` 与每条 entry 的
`match` 是唯一匹配合同。context 选择先于禁字段匹配：以调用面的已知文档类别、owning schema
引用和实例 JSON Pointer 域选中规则，再按登记的 match_scope 执行；不得在实现中维护另一份
context 名称到 Event kind 的手写映射。Event payload 的 owning schema 只从 event-kind registry
的 `payload_schema_ref` 取得。嵌套 typed instance 由 owning schema 确认，不能因为一个对象碰巧
含 `kind`、`schema` 或 `track_name` 就猜其类型。

root 字段路径只相对于该实例根；descendants 才允许在子对象重复匹配。`match` 明确区分字段、
路径、patch 路径和标量值；entry id 是审计标识，不是供 consumer 猜测的 DSL。未定义 context、
不可解析 schema 引用、未知 matcher 均使 artifact 门禁失败。引用类 allowed_contexts 不能豁免
任何真实提交的 wire 数据。

`patch` scope 显式将 owning create context 的字段／路径规则应用于该更新实例的 canonical patch
映射，包括 direct value、显式 set/add 与祖先替换中的剩余路径；不是按字段名猜测 create 类型。

`track_name/message` 只禁止物化 Message 对象复制 track；`ak.message.create` payload 的
`track_name` 仍是必填签名事实。Message 中不相关嵌套用户字段不得被根字段规则误拒。对象整体
替换和 patch set 的嵌套值仍按其 owning create context 检查，不能通过替换祖先逃过禁字段。
