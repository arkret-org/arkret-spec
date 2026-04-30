# Schema Registry

Initial object schemas:

- `cx.schema.space.v1`
- `cx.schema.actor_profile.v1`
- `cx.schema.entity.v1`
- `cx.schema.relation.v1`
- `cx.schema.view.v1`
- `cx.schema.policy.v1`
- `cx.schema.invite.v1`
- `cx.schema.read_marker.v1`
- `cx.schema.notification.v1`
- `cx.schema.capability.v1`
- `cx.schema.event.v1`
- `cx.schema.commit.v1`
- `cx.schema.operation.v1`
- `cx.schema.blob.v1`
- `cx.schema.encrypted_payload.v1`
- `cx.schema.client_sync_response.v1`
- `cx.schema.mimi_interop.v1`

## Event Types

### Naming Rule

- Standard event types MUST use `cx.` namespace with the shape `cx.<domain>.<verb>`.
- Unprefixed event names such as `space.create` are not standard event types and MUST NOT appear in interoperable event streams.
- Arbitrary free-form `custom.*` event names are not directly registrable. Custom behavior MUST be mapped through custom schema + capability guard.

| event type | meaning |
| --- | --- |
| `cx.space.create` | Space create |
| `cx.space.update` | Space patch |
| `cx.space.upgrade` | Space version upgrade |
| `cx.space.organization` | Space official/sponsorship declaration |
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
| `cx.container.move_item` | Facet container item move |
| `cx.container.rebalance` | Facet container rank rebalance |
| `cx.field_position.move` | Facet field-position move |
| `cx.field_position.reorder` | Facet field-position reorder |
| `cx.message.create` | Message create |
| `cx.message.revise` | Message edit patch (canonical edit operation) |
| `cx.message.redact` | Message redaction |
| `cx.reaction.add` | Reaction add |
| `cx.reaction.remove` | Reaction remove |
| `cx.capability.grant` | Grant |
| `cx.capability.delegate` | Delegate grant |
| `cx.capability.revoke` | Revocation |
| `cx.task.create` | Task create |
| `cx.task.update` | Task patch |
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
| `cx.read.marker` | Read marker event |
| `cx.receipt.read` | Read receipt event |
| `cx.applet.bridge_error` | Bridge failure |
| `cx.applet.registration` | Applet registration |
| `cx.applet.protocol_session.start` | Applet/agent protocol session start |
| `cx.applet.protocol_session.status` | Session status |
| `cx.mimi.room_binding` | MIMI room binding state |
| `cx.call.signal` | WebRTC signal message |
| `cx.redaction` | Generic redaction envelope |
