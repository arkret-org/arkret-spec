---
title: Standard Event and Object Schema Registry
sidebar:
  label: Schema Registry
---

## 1. 目标与真源

> **本文是 generated documentation view,不是 schema/event 真源。**
> 下方的 schema id 表与 event kind 表由 `artifacts/registry/*.json` 渲染得到;两者不一致时 **JSON registry 为准**。"本文定义"的措辞仅指文档级别的展示视图。
> 修改流程:`contract-catalog.json` → `tools/artifact_pipeline.py generate` → 各 `*-registry.json` 与本文表格一并刷新;不得只手工编辑本文表格。

字段级结构定义见 `../models/common-fields.md` 及各对象专属文件（`space-and-place.md` / `flow-and-message.md` / `morph.md` / `relation.md` / `actor.md` / `governance-objects.md` / `private-objects.md` / `event-and-patch.md`）。

机器可读真源(authoritative,本文表格只是其投影):

- `artifacts/registry/contract-catalog.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/operation-registry.json`
- `artifacts/registry/error-code-registry.json`

其中 `error-code-registry.json` 是标准 service error code 与批处理逐项 `reason_code` 的 canonical registry；本文后续 event/schema 表只提供文档视图，不重复维护错误码全集。

## 2. Standard Object Schema

| schema id | kind |
| --- | --- |
| `cx.schema.space.v1` | Space |
| `cx.schema.actor_profile.v1` | Actor Profile |
| `cx.schema.flow.v1` | Flow |
| `cx.schema.message.v1` | Message |
| `cx.schema.morph.v1` | Morph |
| `cx.schema.relation.v1` | Relation |
| `cx.schema.view.v1` | View |
| `cx.schema.policy.v1` | Policy |
| `cx.schema.invite.v1` | Invite |
| `cx.schema.read_marker.v1` | Read Marker |
| `cx.schema.notification.v1` | Notification |
| `cx.schema.capability.v1` | Capability Grant |
| `cx.schema.event.v1` | Event Envelope |
| `cx.schema.event_payload.v1` | Standard Event Payload Classes |
| `cx.schema.event_batch_receipt.v1` | Event Batch Receipt |
| `cx.schema.cursor.v1` | Cursor |
| `cx.schema.snapshot.v1` | Snapshot Manifest |
| `cx.schema.grant_constraint.v1` | Grant Constraint |
| `cx.schema.resource_selector.v1` | Resource Selector |
| `cx.schema.did_key_log_entry.v1` | DID Key Log Entry |
| `cx.schema.did_continuity_proof.v1` | DID Continuity Proof |
| `cx.schema.identity_receipt.v1` | Identity Receipt |
| `cx.schema.identity_link.v1` | Minimal-metadata E2EE identity link |
| `cx.schema.handle_claim.v1` | Handle Claim |
| `cx.schema.media_metadata.v1` | Media Metadata |
| `cx.schema.read_receipt.v1` | Read Receipt |
| `cx.schema.blob.v1` | Blob Metadata |
| `cx.schema.encrypted_payload.v1` | MLS Encrypted Payload Envelope |
| `cx.schema.key_backup.v1` | Encrypted Key Backup |
| `cx.schema.client_sync_response.v1` | Client Sync Response |
| `cx.schema.device_message.v1` | To-device Message Envelope |
| `cx.schema.mimi_interop.v1` | MIMI Provider Directory / Room Binding / Mapping Receipt |
| `cx.schema.moderation_report.v1` | Moderation Report |
| `cx.schema.moderation_queue_item.v1` | Moderation Queue Item |
| `cx.schema.agent_authority.v1` | Agent Authority Panel |

## 3. Event Type 设计约束

### 3.1 命名规则

- 标准事件必须使用命名空间：`cx.<domain>[.<subdomain>].<verb>`。
- 所有标准事件必须是 `cx.` 前缀。
- 裸名事件（例如 `space.create`）不是标准事件。
- 自由字符串事件（如 `custom.*`）不能直接登记标准事件，需要通过自定义 schema + capability / state filter 映射。

### 3.2 wire scope 语义

完整 event kind 集合以 `artifacts/registry/event-kind-registry.json` 为准。`wire_scope` 语义如下：

- `durable_event`：进入共享 Event Envelope 历史，参与 reducer。
- `actor_private_event`：进入加密 account data 或 actor-private stream。
- `ephemeral_event`：仅经短暂同步通道，不参与 actor_seq / prev_refs / state hash / reducer frontier。

实现不得仅靠本文件定义；必须加载机器 registry 或等价生成产物。

## 4. Event kind 注册表（文档视图）

### 4.1 Space 与 Flow

| event type | payload |
| --- | --- |
| `cx.space.create` | Space create |
| `cx.space.update` | Space patch |
| `cx.space.upgrade` | Space version upgrade |
| `cx.space.organization` | Space official sponsor statement |
| `cx.space.child` | Child space link |
| `cx.space.parent` | Parent space link |
| `cx.space.inheritance_policy` | Per-parent policy inheritance declaration (subject=`payload.parent_space_id`) |
| `cx.space.join_rule` | Join rule state |
| `cx.space.history_visibility` | History visibility state |
| `cx.space.discovery` | Discoverability state |
| `cx.space.policy` | Space policy state |
| `cx.space.read_receipt_policy` | Space read receipt disclosure policy state |
| `cx.space.tombstone` | Terminal Space tombstone or replacement marker |
| `cx.space.archive` | Reversible archive state |
| `cx.space.freeze` | Temporary freeze state |
| `cx.space.destroy` | Terminal decommission marker |
| `cx.member.state` | Membership state |

> `space.join_policy` / `member.application` / `member.application.review` / `member.application.cancel` 是 candidate workflow concept/action 名称，不是 v1 wire `Event.kind`，见 [`../governance/join-policy.md`](../governance/join-policy.md)。未列入本 active registry，正式登记前不得使用 `cx.*` 前缀，也不得作为 Event envelope 的 `kind`。
| `cx.flow.create` | Flow create |
| `cx.flow.update` | Flow patch |
| `cx.flow.archive` | Flow archive |
| `cx.flow.restore` | Flow restore |
| `cx.flow.move` | Flow move between Lists |
| `cx.flow.reorder` | Flow reorder within List |
| `cx.flow.tracks.update` | Flow tracks map patch（`cx.patch.v1` payload；详见 [`../models/flow-and-message.md` §4.8](../models/flow-and-message.md)） |
| `cx.flow.watch.set` | Set / clear per-(flow, actor) watch subscription (writes cas-register cell `cx.component.flow.watch.v1`; derives `watches` Relation) |
| `cx.place.create` | Place create (board / list / swimlane / calendar bucket / ...) |
| `cx.place.update` | Place metadata patch |
| `cx.place.parent` | Place parent declaration (cas-register cell) |
| `cx.place.archive` | Place archive (reversible UI hide) |
| `cx.place.restore` | Place restore (archived -> active; only valid when current state == archived) |
| `cx.place.tombstone` | Place tombstone (irreversible; contained Flows MUST be relocated first) |

### 4.2 消息与关系

| event type | payload |
| --- | --- |
| `cx.morph.create` | Morph create |
| `cx.morph.update` | Morph patch |
| `cx.morph.archive` | Morph archive |
| `cx.morph.restore` | Morph restore |
| `cx.container.move_item` | Facet container item move |
| `cx.container.rebalance` | Facet container rank rebalance |
| `cx.message.create` | Message create |
| `cx.message.revise` | Message edit patch |
| `cx.message.redact` | Message-scoped redaction |
| `cx.relation.create` | Relation create |
| `cx.relation.update` | Relation patch |
| `cx.relation.delete` | Relation tombstone |
| `cx.reaction.add` | Reaction add |
| `cx.reaction.remove` | Reaction remove |
| `cx.read.marker` | Read marker event |
| `cx.receipt.read` | Read receipt event |

### 4.3 授权与治理

| event type | payload |
| --- | --- |
| `cx.capability.grant` | Grant |
| `cx.capability.delegate` | Delegate grant |
| `cx.capability.revoke` | Revocation |
| `cx.capability.derived` | Derived capability state |
| `cx.account.status` | Signed account lifecycle status |
| `cx.profile.create` | Actor profile create |
| `cx.profile.update` | Actor profile patch |
| `cx.profile.space_override` | Space-scoped profile override |
| `cx.audit.accessed` | Auditable access |
| `cx.moderation.report` | Moderation report |
| `cx.key.verification.request` | Device key verification request |
| `cx.key.verification.ready` | Device key verification ready |
| `cx.key.verification.start` | Device key verification start |
| `cx.key.verification.accept` | Device key verification accept |
| `cx.key.verification.key` | Device key verification ephemeral key |
| `cx.key.verification.mac` | Device key verification MAC |
| `cx.key.verification.done` | Device key verification completion |
| `cx.key.verification.cancel` | Device key verification cancellation |
| `cx.session.grant` | Session grant |
| `cx.device.authorized` | Device authorization |
| `cx.device.revoked` | Device revocation |
| `cx.device.list_update` | Device list update |
| `cx.call.signal` | WebRTC signal message |

### 4.4 加密、协作与扩展

| event type | payload |
| --- | --- |
| `cx.mls.proposal` | MLS proposal |
| `cx.mls.genesis` | MLS group genesis |
| `cx.mls.commit` | MLS commit |
| `cx.mls.commit_failed` | MLS commit or Welcome processing failure diagnostic |
| `cx.mls.welcome` | MLS welcome ref |
| `cx.mls.keypackage` | MLS KeyPackage publication |
| `cx.space_key.share` | Space key share |
| `cx.space_key.withheld` | Space key withheld notice |
| `cx.space_key.share_audit` | Auditable history key share marker |
| `cx.agent.endpoint` | Agent protocol endpoint declaration |
| `cx.agent.protocol_session.start` | Agent protocol session start |
| `cx.agent.protocol_session.status` | Agent protocol session status |
| `cx.applet.bridge_error` | Bridge failure |
| `cx.applet.registration` | Applet registration |
| `cx.applet.protocol_session.start` | Applet / agent protocol session start |
| `cx.applet.protocol_session.status` | Protocol session status |
| `cx.mimi.room_binding` | MIMI room binding state |
| `cx.redaction` | Generic redaction envelope |

## 5. Extension 约定

自定义 schema id SHOULD 使用反向域名前缀：

```text
com.example.schema.foo.v1
```

自定义 event type MUST NOT 使用 `cx.` 前缀，除非被正式纳入标准注册表。

## 6. 演进约束

Schema evolution MUST：

- 保留未知字段
- 不修改既有字段语义
- 可选字段应先于必填字段添加
- reducer 行为变化需提供变更说明
- 若变更授权、可见性、排序或收敛语义，需声明新 schema 或 reducer profile

未知 non-critical 字段出现在 canonical Event / Operation / Event Batch Receipt / Snapshot / Grant / encrypted envelope 中时，接收方 MUST 保留这些字段用于存储、转发、backfill、hash 与签名校验的 canonical bytes；reducer 可忽略语义，但不得剔除。

未知 critical feature MUST fail closed。Event Envelope 的 `requirements` 对象（含 `schema[]` / `reducer` / `features[]` / `critical_extensions[]`）是 v1 固定的扩展声明位置，全部进入 canonical bytes 并参与 `payload_hash`。`requirements.critical_extensions[]` 每项必须包含 `id`、`scope` 和 `fail_closed=true`。

OpenAPI DTO MAY 使用 `additionalProperties: false`。但这不覆盖 canonical object 的字段保留规则。若 DTO 内嵌 canonical protocol object，内嵌对象 MUST 按 registry schema 解析，并按本节规则保留未知字段。
