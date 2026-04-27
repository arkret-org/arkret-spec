# Applet Integration

Applet is Contrix's equivalent to Matrix Application Service, adapted to DID, capability, and Space-based architecture.

Applet supports:

- signed registration
- actor / space / handle namespaces
- transaction push
- query actor
- query space
- protocol metadata
- third-party user/location lookup
- ghost actors
- portal spaces
- delegated `via applet` operation

Namespaces do not grant write authority. Every write still needs signature, capability, and Space policy authorization.

## Applet API Field Index

| operation_id | Required fields | Optional fields | Response fields | Constraints |
| --- | --- | --- | --- | --- |
| `cx.applet.ping` | none | none | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | May be public, but must not leak private namespace data. |
| `cx.applet.describe` | none | none | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | Public mode returns only public capabilities. |
| `cx.applet.transaction` | `path.txn_id: id`; `source_service_did: did`; `events: object[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet MUST verify source service DID, HTTP signature, event signature, namespace, and capability. |
| `cx.applet.query_actor` | `path.actor_id: did` | none | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | Actor id must match the Applet actor namespace. |
| `cx.applet.query_space` | `path.space_id_or_alias: string` | none | `exists: boolean`; `space_id: id?`; `title: string?`; `external_ref: object?` | Must match portal namespace or authorized query. |
| `cx.applet.protocol_metadata` | `path.protocol: string` | none | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | Instance list may require authorization. |
| `cx.applet.third_party_users` | `query.protocol: string`; external id query fields | none | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | Query fields must be inside the registration namespace. |
| `cx.applet.third_party_locations` | `query.protocol: string`; external id query fields | none | `space_id: id?`; `exists: boolean`; `external_ref: object?` | Query fields must be inside the portal namespace. |

