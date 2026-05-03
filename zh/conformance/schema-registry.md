# Standard Event and Object Schema Registry

## 1. 目标

本文定义 Contrix v1 标准 schema registry 与 event kind registry 的文档视图。字段级结构定义见 `data-structures.md`。

机器可读 source of truth：

- Canonical contract catalog：`artifacts/registry/contract-catalog.json`
- Object / DTO schema：`artifacts/registry/schema-registry.json`（generated view）
- Protocol typed ID kind：`artifacts/registry/id-kind-registry.json`（generated view）
- Standard Event kind：`artifacts/registry/event-kind-registry.json`（generated view，含 `wire_scope` 与 `reducer_input` 语义分类）
- Service operation id：`artifacts/registry/operation-registry.json`（generated view）

## 2. Object Schema

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
| `cx.schema.operation.v1` | Operation |
| `cx.schema.cursor.v1` | Cursor |
| `cx.schema.snapshot.v1` | Snapshot Manifest |
| `cx.schema.grant_constraint.v1` | Grant Constraint |
| `cx.schema.resource_selector.v1` | Resource Selector |
| `cx.schema.did_key_log_entry.v1` | DID Key Log Entry |
| `cx.schema.identity_receipt.v1` | Identity Receipt |
| `cx.schema.handle_claim.v1` | Handle Claim |
| `cx.schema.media_metadata.v1` | Media Metadata |
| `cx.schema.read_receipt.v1` | Read Receipt |
| `cx.schema.blob.v1` | Blob Metadata |
| `cx.schema.encrypted_payload.v1` | MLS Encrypted Payload Envelope |
| `cx.schema.client_sync_response.v1` | Client Sync Response |
| `cx.schema.mimi_interop.v1` | MIMI Provider Directory / Room Binding / Mapping Receipt |
| `cx.schema.moderation_report.v1` | Moderation Report |
| `cx.schema.moderation_queue_item.v1` | Moderation Queue Item |
| `cx.schema.agent_authority.v1` | Agent Authority Panel |

## 3. Event Type

### 3.1 命名规则

- 标准 event type 应使用 namespace：`cx.<domain>[.<subdomain>].<verb>`；少数根级标准事件（例如 `cx.redaction`）必须显式出现在 event kind registry 中。
- 所有标准事件必须使用 `cx.` 前缀。
- 裸名事件（如 `space.create`）不是标准事件类型，MUST NOT 出现在互操作事件流中。
- 语义上不安全的自由字符串事件（如 `custom.*`）不直接进入注册表，必须通过自定义 schema + state filter+capability 约束映射到 `cx.custom.*` 空间。

完整标准事件集合以 `artifacts/registry/event-kind-registry.json` 为准。registry 中的 `wire_scope` 是规范语义：`durable_event` 可以进入共享 Event Envelope 历史并作为 reducer 输入；`actor_private_event` 只能进入加密 account data 或 actor-private stream；`ephemeral_event` 只能走短暂同步通道；`deprecated_alias` 只能用于迁移读取。实现不得只解析本 Markdown 表，而必须加载机器 registry 或等价生成物。

下表是主要已注册 kind 的文档视图，不替代机器 registry，也不改变 registry 的 `wire_scope`。

| event type | payload |
| --- | --- |
| `cx.space.create` | Space create |
| `cx.space.update` | Space patch |
| `cx.space.upgrade` | Space version upgrade |
| `cx.space.organization` | Space 官方/赞助声明 |
| `cx.space.child` | Child space link |
| `cx.space.parent` | Parent space link |
| `cx.space.inheritance_policy` | Policy inheritance declaration |
| `cx.space.join_rule` | Join rule state |
| `cx.space.history_visibility` | History visibility state |
| `cx.space.discovery` | Discoverability state |
| `cx.space.policy` | Space policy state |
| `cx.space.tombstone` | Terminal Space tombstone or replacement marker |
| `cx.space.archive` | Set reversible archive state |
| `cx.space.freeze` | Set reversible temporary freeze state |
| `cx.space.destroy` | Terminal Space decommission marker |
| `cx.member.state` | Membership state |
| `cx.flow.create` | Flow create |
| `cx.flow.update` | Flow patch |
| `cx.flow.archive` | Flow archive |
| `cx.flow.restore` | Flow restore |
| `cx.flow.convert` | Flow mode convert |
| `cx.flow.branch.enable` | Enable Flow branch |
| `cx.flow.branch.disable` | Disable Flow branch |
| `cx.flow.branch.update` | Flow branch patch |
| `cx.flow.branch.set_primary` | Set Flow primary branch |
| `cx.flow.branch.member` | Flow discussion branch membership state |
| `cx.flow.branch.history_visibility` | Flow discussion branch history visibility state |
| `cx.flow.branch.policy_components` | Flow discussion branch policy component state |
| `cx.flow.move` | Flow move between Lists |
| `cx.flow.reorder` | Flow reorder within List |
| `cx.morph.create` | Morph create |
| `cx.morph.update` | Morph patch |
| `cx.morph.archive` | Morph archive |
| `cx.morph.restore` | Morph restore |
| `cx.agent.endpoint` | Agent protocol endpoint declaration |
| `cx.agent.protocol_session.start` | Agent protocol session start |
| `cx.agent.protocol_session.status` | Agent protocol session status |
| `cx.agent.protocol_session.result` | Agent protocol session result |
| `cx.relation.create` | Relation create |
| `cx.relation.update` | Relation patch |
| `cx.relation.delete` | Relation tombstone |
| `cx.container.move_item` | Facet container item move |
| `cx.container.rebalance` | Facet container rank rebalance |
| `cx.message.create` | Message create |
| `cx.message.revise` | Message edit patch（规范编辑操作，优先定义） |
| `cx.message.redact` | Message-scoped redaction |
| `cx.reaction.add` | Reaction add |
| `cx.reaction.remove` | Reaction remove |
| `cx.capability.grant` | Grant |
| `cx.capability.delegate` | Delegate grant |
| `cx.capability.revoke` | Revocation |
| `cx.capability.derived` | Derived capability state |
| `cx.view.create` | View create |
| `cx.view.update` | View update |
| `cx.view.reconcile` | View schema/definition sync |
| `cx.mls.proposal` | MLS proposal |
| `cx.mls.commit` | MLS commit |
| `cx.mls.welcome` | MLS welcome ref |
| `cx.mls.keypackage` | MLS KeyPackage publication |
| `cx.mls.epoch` | MLS epoch checkpoint derived from winning commit |
| `cx.space_key.share` | Space key share |
| `cx.space_key.withheld` | Space key withheld notice |
| `cx.space_key.share_audit` | Auditable history key share marker |
| `cx.audit.accessed` | Auditable access |
| `cx.moderation.report` | Moderation report |
| `cx.device.authorized` | Device authorization |
| `cx.device.revoked` | Device revocation |
| `cx.device.list_update` | Device list update |
| `cx.key.verification.request` | Device key verification request |
| `cx.session.grant` | Session grant |
| `cx.account.status` | Signed account lifecycle status |
| `cx.read.marker` | Read marker event |
| `cx.receipt.read` | Read receipt event |
| `cx.applet.bridge_error` | Bridge failure |
| `cx.applet.registration` | Applet registration |
| `cx.applet.protocol_session.start` | Applet / agent protocol session start |
| `cx.applet.protocol_session.status` | Session status |
| `cx.mimi.room_binding` | MIMI room binding state |
| `cx.call.signal` | WebRTC signal message |
| `cx.redaction` | Generic redaction envelope |

## 4. Extension

自定义 schema id SHOULD 使用反向域名前缀：

```text
com.example.schema.foo.v1
```

自定义 event type MUST NOT 使用 `cx.` 前缀，除非被纳入标准注册表。

## 5. Compatibility

Schema evolution MUST:

- preserve unknown fields
- avoid changing field meaning
- add optional fields before required fields
- provide migration notes for reducer behavior
- 若字段改变授权、可见性、排序或收敛语义，必须声明新的 schema 或 reducer profile。

未知的 non-critical 字段出现在 canonical Event、Operation、Event Batch Receipt、Snapshot、Grant 或 encrypted envelope 中时，接收方 MUST 在存储、转发、backfill 和 hash/signature 校验所用 canonical bytes 中保留这些字段；不理解该字段的 reducer MUST 忽略它，而不是剔除、重排语义或当作失败。OpenAPI DTO / materialized view MAY 在派生响应中省略未知字段，但不得在验证、联邦转发或审计回放前从 canonical object 中剥离。

未知 critical feature MUST fail closed。Event Envelope 顶层的 `required_features`、`critical_extensions`、`schema_profile_refs` 与 `reducer_profile_ref` 是 v1 固定扩展声明位置，MUST 进入 canonical event bytes、event digest 和 proof `payload_hash`。`critical_extensions[]` 每项 MUST 至少包含 `id`、`scope` 和 `fail_closed=true`；`scope` 表示该语义影响 `event`、`content`、`proof`、`authz`、`reducer`、`projection` 或 `encryption` 哪一层。接收方若不支持该 critical 语义，MUST 返回 `unsupported_feature`、`schema_violation`、`soft_fail` 或 `quarantine`，不得静默接受并用旧语义解释。

OpenAPI request/response schema MAY 对服务 DTO 使用 `additionalProperties: false`。这不覆盖 canonical object 的字段保留规则。若 DTO 内嵌 canonical protocol object，内嵌对象 MUST 按 registry schema 解析，并按本节保留未知字段。
