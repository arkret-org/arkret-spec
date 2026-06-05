---
title: Standard Event and Object Schema Registry
status: candidate
normative: true
stability: v1
updated: 2026-05-25
sidebar:
  label: Schema Registry
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与真源

> **本文是 documentation view,不是 schema/event 真源。**
> 下方 §2 schema id 表与 §4 event kind 表是**人工维护的阅读节选**，并非穷尽清单；两者与机器 registry 不一致时一律 **以 JSON registry 为准**。"本文定义"的措辞仅指文档级别的展示视图。穷尽且 canonical 的清单是 `artifacts/registry/*.json`（站点经 MDX 组件 `<EventKindTable/>` / `<SchemaViewer/>` 等直接渲染这些 JSON）。
> 修改流程:`contract-catalog.json` → `tools/artifact_pipeline.py generate` → 刷新各 `*-registry.json`（pipeline **不再**改写本文 md 表）。新增 / 改名概念时如需在本节节选表体现，MUST 手工同步对应行；但本节表的滞后**不**改变「JSON registry 为唯一真源」这一结论。

字段级结构定义见 `../models/common-fields.md` 及各对象专属文件（`realm-and-space.md` / `flow-and-message.md` / `morph.md` / `relation.md` / `actor.md` / `governance-objects.md` / `private-objects.md` / `event-and-patch.md`）。

机器可读真源(authoritative,本文表格只是其投影):

- `artifacts/registry/contract-catalog.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/operation-registry.json`
- `artifacts/registry/error-code-registry.json`

其中 `error-code-registry.json` 是标准 service error code 与批处理逐项 `reason_code` 的 canonical registry；本文后续 event/schema 表只提供文档视图，不重复维护错误码全集。

### 1.1 schema id ↔ 文件名映射例外（normative）

下游 SDK / IDE 插件不得用 "schema id 去掉前缀 + 换分隔符" 这种机械推导拿文件名；MUST 从 `schema-registry.json` 读取每条 `{schema_id, file}` 对。当前 v1 已知的不能机械推导的对应关系：

| schema id | canonical 文件 | 说明 |
| --- | --- | --- |
| `ck.schema.event.v1` | `schemas/event-envelope.schema.json` | schema id 用 `event` 保持协议对象名，文件名用 `event-envelope` 对齐 wire envelope 术语；不得机械推导为 `event.schema.json`。 |
| `ck.schema.capability.v1` | `schemas/capability-grant.schema.json` | id 简化为 `capability`，文件保留 `capability-grant` 以区别于其他 capability 相关 schema（grant-constraint、resource-selector 等）。 |
| `ck.schema.morph.customer_risk.v1` | `schemas/morph-customer-risk.schema.json` | id 用 dot 分段（`morph.customer_risk`），文件用 dash（`morph-customer-risk`）；对应规则是 "schema id 里的每段都换成 dash"。其它 dotted-id schema 适用同一规则。 |

新增 schema 时如果出现不能机械推导的命名，必须把对应关系登记到 `contract-catalog.json` 的 `schemas[]` 条目，并在此表格补充一行；不得只改文件名。

### 1.1.1 error code 命名空间例外（normative）

`error-code-registry.json` 中的 `code` / `reason_code` 值有意使用裸名（例如 `bad_json`、`policy_violation`、`failed_precondition`），不加 `ck.` 前缀。错误码只在 service response、batch item 诊断和 reducer reason 上下文中解释，不与 event kind、operation id、schema id 或 capability action 共用命名空间。跨规范聚合错误时，调用方 SHOULD 用 registry 文件或 protocol 名称作为外层 namespace，而不是把 `ck.` 前缀补进 wire code。

新增标准错误码必须继续登记在 `error-code-registry.json`，不得因为本例外而在其它 registry 里注册裸名 action / event / operation。

### 1.2 有意保留的旧命名（intentionally retained legacy wire names）

以下名称在 Realm/Space 反转或其它命名收敛之后**语义已迁移**到新模型，但**字符串本身保留**以保持 wire 兼容。`renames.json` 与 `forbidden-wire-fields.json` 等漂移防护机制不针对它们，授权 / 解析逻辑必须按更新后的语义处理：

| 保留名（wire） | 当前语义 | 保留理由 | 防护参考 |
| --- | --- | --- | --- |
| event kind `ck.profile.space_override` | Realm-scoped Actor Profile override（`payload.target_realm_id` 是目标 Realm，不指向 `ck:space:` 容器，也不创建任何 Space 级访问边界） | 该 event 在反转前已经发布到 wire 并被多个客户端消费；强行重命名会破坏现存事件审计链与历史 query。新对象类型用 `ck.profile.realm_override` 命名。 | `event-payload.schema.json` `$defs/profile_realm_override_payload`；`contract-catalog.json` 中 payload description 显式说明语义；`zh/discovery/profiles-presence.md §3` 散文兼容声明 |
| HTTP path segment `/_cokret/open/mimi/rooms/...` → `/_cokret/open/mimi/flows/...` | （已重命名，仅作对照说明）当前 wire 是 `/_cokret/open/mimi/flows/{flow_id}/...`；旧路径已 hard reject。 | 不再保留 | 见 `renames.json` `/_cokret/open/mimi/rooms/{flow_id}/...` |
| operation id `ck.mimi.room_update` / `ck.mimi.notify` / `ck.mimi.submit_message` / `ck.mimi.group_info` | MIMI interop 命名空间内的标准操作；`room` 出现是为了与上游 MIMI 规范对齐 | MIMI interop 模块对外语义就是 "MIMI room"；仅在 interop module 内部使用，不污染 core | `forbidden-model-terms.json` 把 `Room` 列为 `interop_module` allowed context |

新增"有意保留的旧命名"必须在此表登记并在对应 schema / registry 内联说明保留理由；不得仅靠口头约定。下游漂移扫描器 SHOULD 把此表作为 allowlist。

## 2. Standard Object Schema

| schema id | kind |
| --- | --- |
| `ck.schema.realm.v1` | Realm |
| `ck.schema.space.v1` | Space |
| `ck.schema.actor_profile.v1` | Actor Profile |
| `ck.schema.circle.v1` | Circle (intra-Realm scoped event/message boundary; see [`../models/circle.md`](../models/circle.md)) |
| `ck.schema.flow.v1` | Flow |
| `ck.schema.message.v1` | Message |
| `ck.schema.morph.v1` | Morph |
| `ck.schema.relation.v1` | Relation |
| `ck.schema.view.v1` | View |
| `ck.schema.policy.v1` | Policy |
| `ck.schema.invite.v1` | Invite |
| `ck.schema.read_cursor.v1` | Read Cursor |
| `ck.schema.notification.v1` | Notification |
| `ck.schema.capability.v1` | Capability Grant |
| `ck.schema.event.v1` | Event Envelope |
| `ck.schema.event_payload.v1` | Standard Event Payload Classes |
| `ck.schema.event_batch_receipt.v1` | Event Batch Receipt |
| `ck.schema.cursor.v1` | Cursor |
| `ck.schema.snapshot.v1` | Snapshot Manifest |
| `ck.schema.grant_constraint.v1` | Grant Constraint |
| `ck.schema.resource_selector.v1` | Resource Selector |
| `ck.schema.did_key_log_entry.v1` | DID Key Log Entry |
| `ck.schema.did_continuity_proof.v1` | DID Continuity Proof |
| `ck.schema.identity_receipt.v1` | Identity Receipt |
| `ck.schema.identity_link.v1` | Minimal-metadata E2EE identity link |
| `ck.schema.handle_claim.v1` | Handle Claim |
| `ck.schema.realm_join_candidate.v1` | Realm join candidate routing hint |
| `ck.schema.media_metadata.v1` | Media Metadata |
| `ck.schema.read_receipt.v1` | Read Receipt |
| `ck.schema.blob.v1` | Blob Metadata |
| `ck.schema.encrypted_envelope.v1` | MLS Encrypted Payload Envelope |
| `ck.schema.key_backup.v1` | Encrypted Key Backup |
| `ck.schema.recovery_policy.v1` | Principal Recovery Policy |
| `ck.schema.recovery_session.v1` | Device Recovery Session |
| `ck.schema.recovery_receipt.v1` | Recovery Receipt |
| `ck.schema.account_subscribe_frame.v1` | Account Subscribe Frame |
| `ck.schema.device_message.v1` | To-device Message Envelope |
| `ck.schema.mimi_interop.v1` | MIMI Provider Directory / MIMI Room Binding (interop; see [`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)) / Mapping Receipt |
| `ck.schema.moderation_report.v1` | Moderation Report |
| `ck.schema.moderation_queue_item.v1` | Moderation Queue Item |

## 3. Event Type 设计约束

### 3.1 命名规则

- 标准事件必须使用命名空间：`ck.<domain>[.<subdomain>].<verb>`。
- 所有标准事件必须是 `ck.` 前缀。
- 裸名事件（例如 `realm.create`）不是标准事件。
- 自由字符串事件（如 `custom.*`）不能直接登记标准事件，需要通过自定义 schema + capability / state filter 映射。

### 3.2 wire scope 语义

完整 event kind 集合以 `artifacts/registry/event-kind-registry.json` 为准。`wire_scope` 语义如下：

- `durable_event`：进入共享 Event Envelope 历史，参与 reducer。
- `actor_private_event`：进入加密 account data 或 actor-private stream。
- `ephemeral_event`：仅经短暂同步通道，不参与 actor_seq / prev_refs / state hash / reducer frontier。

实现不得仅靠本文件定义；必须加载机器 registry 或等价生成产物。

## 4. Event kind 注册表（文档视图）

### 4.1 Realm 与 Flow

| event type | payload |
| --- | --- |
| `ck.realm.create` | Realm create |
| `ck.realm.update` | Realm patch |
| `ck.realm.upgrade` | Realm version upgrade |
| `ck.realm.organization` | Realm official sponsor statement |
| `ck.realm.link` | Typed Realm link graph edge |
| `ck.realm.inheritance_policy` | Policy inheritance declaration from a source Realm (subject=`payload.source_realm_id`) |
| `ck.realm.join_rule` | Join rule state |
| `ck.realm.history_visibility` | History visibility state |
| `ck.realm.history_sharing_policy` | E2EE history key share policy |
| `ck.realm.discovery` | Discoverability state |
| `ck.realm.preview_policy` | Preview / peek policy state |
| `ck.realm.policy` | Realm policy state |
| `ck.realm.read_receipt_policy` | Realm read receipt disclosure policy state |
| `ck.realm.tombstone` | Terminal Realm tombstone or replacement marker |
| `ck.realm.archive` | Reversible archive state |
| `ck.realm.freeze` | Temporary freeze state |
| `ck.realm.destroy` | Terminal decommission marker |
| `ck.member.state` | Membership state |

> `realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel` 是 candidate workflow concept/action 名称，不是 v1 wire `Event.kind`，见 [`../governance/join-policy.md`](../governance/join-policy.md)。未列入本 active registry，正式登记前不得使用 `ck.*` 前缀，也不得作为 Event envelope 的 `kind`。
| `ck.flow.create` | Flow create |
| `ck.flow.update` | Flow patch |
| `ck.flow.archive` | Flow archive |
| `ck.flow.restore` | Flow restore |
| `ck.flow.move` | Flow move between Lists |
| `ck.flow.reorder` | Flow reorder within List |
| `ck.flow.tracks.update` | Flow tracks map patch（`ck.patch.v1` payload；详见 [`../models/flow-and-message.md` §4.8](../models/flow-and-message.md)） |
| `ck.flow.watch.set` | Set / clear per-(flow, actor) watch subscription (writes cas_register cell `ck.component.flow.watch.v1`; derives `watches` Relation) |
| `ck.space.create` | Space create (board / list / swimlane / calendar bucket / ...) |
| `ck.space.update` | Space metadata patch |
| `ck.space.parent` | Space parent declaration (cas_register cell) |
| `ck.space.archive` | Space archive (reversible UI hide) |
| `ck.space.restore` | Space restore (archived -> active; only valid when current state == archived) |
| `ck.space.tombstone` | Space tombstone (irreversible; contained Flows MUST be relocated first) |

### 4.2 消息与关系

| event type | payload |
| --- | --- |
| `ck.morph.create` | Morph create |
| `ck.morph.update` | Morph patch |
| `ck.morph.archive` | Morph archive |
| `ck.morph.restore` | Morph restore |
| `ck.container.move_item` | Facet container item move |
| `ck.container.rebalance` | Facet container rank rebalance |
| `ck.message.create` | Message create |
| `ck.message.revise` | Message edit patch |
| `ck.message.redact` | Message-scoped redaction |
| `ck.relation.create` | Relation create |
| `ck.relation.update` | Relation patch |
| `ck.relation.tombstone` | Relation tombstone |
| `ck.reaction.add` | Reaction add |
| `ck.reaction.remove` | Reaction remove |
| `ck.read_cursor.advance` | Read cursor advance event |
| `ck.receipt.read` | Read receipt event |

### 4.3 授权与治理

| event type | payload |
| --- | --- |
| `ck.capability.grant` | Grant |
| `ck.capability.delegate` | Delegate grant |
| `ck.capability.revoke` | Revocation |
| `ck.capability.derived` | Derived capability state |
| `ck.account.status` | Signed account lifecycle status |
| `ck.profile.create` | Actor profile create |
| `ck.profile.update` | Actor profile patch |
| `ck.profile.space_override` | Realm-scoped profile override |
| `ck.audit.accessed` | Auditable access |
| `ck.moderation.report` | Moderation report |
| `ck.key.verification.request` | Device key verification request |
| `ck.key.verification.ready` | Device key verification ready |
| `ck.key.verification.start` | Device key verification start |
| `ck.key.verification.accept` | Device key verification accept |
| `ck.key.verification.key` | Device key verification ephemeral key |
| `ck.key.verification.mac` | Device key verification MAC |
| `ck.key.verification.done` | Device key verification completion |
| `ck.key.verification.cancel` | Device key verification cancellation |
| `ck.session.grant` | Session grant |
| `ck.device.authorize` | Device authorization |
| `ck.device.revoke` | Device revocation |
| `ck.device.list_update` | Device list update |
| `ck.call.signal` | WebRTC signal message |

### 4.4 加密、协作与扩展

| event type | payload |
| --- | --- |
| `ck.mls.proposal` | MLS proposal |
| `ck.mls.genesis` | MLS group genesis |
| `ck.mls.commit` | MLS commit |
| `ck.mls.commit_failed` | MLS commit or Welcome processing failure diagnostic |
| `ck.mls.welcome` | MLS welcome ref |
| `ck.mls.keypackage` | MLS KeyPackage publication |
| `ck.realm_key.share` | Realm key share |
| `ck.realm_key.withheld` | Realm key withheld notice |
| `ck.realm_key.share_audit` | Auditable history key share marker |
| `ck.agent.endpoint` | Agent protocol endpoint declaration |
| `ck.agent.protocol_session.start` | Agent protocol session start |
| `ck.agent.protocol_session.status` | Agent protocol session status |
| `ck.agent.protocol_session.result` | Agent protocol session result |
| `ck.applet.bridge_error` | Bridge failure |
| `ck.applet.registration` | Applet registration |
| `ck.applet.protocol_session.start` | Applet / agent protocol session start |
| `ck.applet.protocol_session.status` | Protocol session status |
| `ck.mimi.room_binding` | MIMI room binding state |
| `ck.redaction` | Generic redaction envelope |

## 5. Extension 约定

自定义 schema id SHOULD 使用反向域名前缀：

```text
com.example.schema.foo.v1
```

自定义 event type MUST NOT 使用 `ck.` 前缀，除非被正式纳入标准注册表。

## 6. 演进约束

Schema evolution MUST：

- 保留未知字段
- 不修改既有字段语义
- 可选字段应先于必填字段添加
- reducer 行为变化需提供变更说明
- 若变更授权、可见性、排序或收敛语义，需声明新 schema 或 reducer profile

未知 non-critical 字段出现在 canonical Event / Operation / Event Batch Receipt / Snapshot / Grant / encrypted envelope 中时，接收方 MUST 保留这些字段用于存储、转发、backfill、hash 与签名校验的 canonical bytes；reducer 可忽略语义，但不得剔除。

未知 critical feature MUST fail closed。Event Envelope 的 `requirements` 对象（含 `schema[]` / `reducer` / `features[]` / `critical_extensions[]`）是 v1 固定的扩展声明位置，全部进入 canonical bytes 并参与 `event_digest`。`requirements.critical_extensions[]` 每项必须包含 `id`、`extension_scope` 和 `fail_closed=true`；entry 顶层不得携带未声明字段，扩展参数必须放入 `parameters`，大对象必须用 `material_digest` 绑定。

OpenAPI DTO MAY 使用 `additionalProperties: false`。但这不覆盖 canonical object 的字段保留规则。若 DTO 内嵌 canonical protocol object，内嵌对象 MUST 按 registry schema 解析，并按本节规则保留未知字段。
