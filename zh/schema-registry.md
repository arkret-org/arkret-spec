# Standard Event and Object Schema Registry Draft

## 1. 目标

本文定义初版标准 schema registry。正式 JSON Schema 文件后续可从本注册表生成。

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

## 3. Event Type

| event type | payload |
| --- | --- |
| `space.create` | Space create |
| `space.update` | Space patch |
| `entity.create` | Entity create |
| `entity.update` | Entity patch |
| `entity.redact` | Redaction |
| `relation.create` | Relation create |
| `relation.delete` | Relation tombstone |
| `message.create` | Message create |
| `message.edit` | Message replacement |
| `reaction.create` | Reaction |
| `reaction.delete` | Reaction removal |
| `capability.grant` | Grant |
| `capability.revoke` | Revocation |
| `membership.invite` | Invite |
| `membership.join` | Join |
| `membership.leave` | Leave |
| `membership.ban` | Ban |
| `mls.proposal` | MLS proposal |
| `mls.commit` | MLS commit |
| `mls.welcome` | MLS welcome ref |
| `audit.accessed` | Auditable access |
| `device.authorized` | Device authorization |
| `device.revoked` | Device revocation |
| `applet.bridge_error` | Bridge failure |

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
