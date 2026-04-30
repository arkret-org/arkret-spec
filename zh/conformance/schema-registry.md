# Standard Event and Object Schema Registry

## 1. 目标

本文定义 Contrix v1 标准 schema registry。字段级结构定义见 `data-structures.md`；机器可验证 JSON Schema 文件 SHOULD 从 `data-structures.md` 与本注册表共同生成。

## 2. Object Schema

| schema id | kind |
| --- | --- |
| `cx.schema.space.v1` | Space |
| `cx.schema.actor_profile.v1` | Actor Profile |
| `cx.schema.entity.v1` | Entity |
| `cx.schema.relation.v1` | Relation |
| `cx.schema.view.v1` | View |
| `cx.schema.policy.v1` | Policy |
| `cx.schema.invite.v1` | Invite |
| `cx.schema.read_marker.v1` | Read Marker |
| `cx.schema.notification.v1` | Notification |
| `cx.schema.capability.v1` | Capability Grant |
| `cx.schema.event.v1` | Event Envelope |
| `cx.schema.commit.v1` | Repo Commit |
| `cx.schema.operation.v1` | Operation |
| `cx.schema.blob.v1` | Blob Metadata |
| `cx.schema.encrypted_payload.v1` | MLS Encrypted Payload Envelope |
| `cx.schema.client_sync_response.v1` | Client Sync Response |
| `cx.schema.mimi_interop.v1` | MIMI Provider Directory / Room Binding / Mapping Receipt |

## 3. Event Type

### 3.1 命名规则

- 标准 event type 应使用 namespace：`cx.<domain>.<verb>`。
- 所有标准事件必须使用 `cx.` 前缀。
- 旧草案中的裸名（如 `space.create`）视为历史兼容语法，不再用于新增互操作定义。
- 语义上不安全的自由字符串事件（如 `custom.*`）不直接进入注册表，必须通过自定义 schema + state filter+capability 约束映射到 `cx.custom.*` 空间。

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
| `cx.space.archive` | Enter archive mode |
| `cx.space.freeze` | Enter temporary freeze |
| `cx.space.destroy` | Destroy / reclaim marker |
| `cx.member.state` | Membership state |
| `cx.entity.create` | Entity create |
| `cx.entity.update` | Entity patch |
| `cx.entity.delete` | Entity delete |
| `cx.entity.restore` | Entity restore |
| `cx.entity.redact` | Entity redaction |
| `cx.relation.create` | Relation create |
| `cx.relation.update` | Relation patch |
| `cx.relation.delete` | Relation tombstone |
| `cx.relation.move` | Compatibility alias for `cx.container.move_item` |
| `cx.relation.rebalance` | Compatibility alias for `cx.container.rebalance` |
| `cx.container.move_item` | Facet container item move |
| `cx.container.rebalance` | Facet container rank rebalance |
| `cx.field_position.move` | Facet field-position move |
| `cx.field_position.reorder` | Facet field-position reorder |
| `cx.message.create` | Message create |
| `cx.message.revise` | Message edit patch（规范编辑操作，优先定义） |
| `cx.message.redact` | Message redaction |
| `cx.reaction.add` | Reaction add |
| `cx.reaction.remove` | Reaction remove |
| `cx.capability.grant` | Grant |
| `cx.capability.delegate` | Delegate grant |
| `cx.capability.revoke` | Revocation |
| `cx.task.create` | Task create |
| `cx.task.update` | Task patch |
| `cx.task.move` | Task move compatibility alias for `cx.field_position.move` |
| `cx.task.reorder` | Task rank-only reorder compatibility alias for `cx.field_position.reorder` |
| `cx.view.create` | View create |
| `cx.view.update` | View update |
| `cx.view.reconcile` | View schema/definition sync |
| `cx.mls.proposal` | MLS proposal |
| `cx.mls.commit` | MLS commit |
| `cx.mls.welcome` | MLS welcome ref |
| `cx.audit.accessed` | Auditable access |
| `cx.device.authorized` | Device authorization |
| `cx.device.revoked` | Device revocation |
| `cx.session.grant` | Session grant |
| `cx.read.marker` | Read marker event (legacy/private) |
| `cx.receipt.read` | Read receipt event |
| `cx.applet.bridge_error` | Bridge failure |
| `cx.applet.registration` | Applet registration |
| `cx.applet.protocol_session.start` | Applet / agent protocol session start |
| `cx.applet.protocol_session.status` | Session status |
| `cx.mimi.room_binding` | MIMI room binding state |
| `cx.call.signal` | WebRTC signal message |
| `cx.redaction` | Generic redaction envelope |

### 3.2 兼容别名（建议弃用）

下列历史别名在迁移期可被接受，但新协议与 conformance profile MUST 优先校验 `cx.*` 形式：

- `space.create`
- `session.grant`
- `entity.create`
- `message.edit`（兼容别名，映射到 `cx.message.revise`）
- `message.react`（兼容别名，映射到 `cx.reaction.add`）
- `message.unreact`（兼容别名，映射到 `cx.reaction.remove`）
- `relation.delete`
- `capability.revoke`
- `membership.invite|join|leave|ban`

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
