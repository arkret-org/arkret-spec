# Applet Schema

Defines Applet registration, namespace patterns, transaction endpoint, query actor, query space, protocol metadata, and bridge error event.

Core endpoint:

```text
PUT /api/v1/applet/transactions/{txn_id}
```

Transactions are idempotent. Applets must validate source service DID, HTTP message signature, and event signatures.

Request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `txn_id` | path | `id` | required | Idempotent transaction id; path value MUST match body `txn_id`. |
| `source_service_did` | body | `did` | required | Source service DID. |
| `events` | body | `object[]` | required | Event array pushed to the Applet. |
| `ephemeral` | body | `object[]` | optional | Non-persistent ephemeral event array. |

Response fields: `ok: boolean` required; `rejected: object[]` optional; `retry_after_ms: int` optional.

Related lookup endpoints:

| Endpoint | Request fields | Response fields | Constraints |
| --- | --- | --- | --- |
| `GET /api/v1/applet/actors/{actor_id}` | `path.actor_id: did` required | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | Actor id must match the Applet namespace. |
| `GET /api/v1/applet/spaces/{space_id_or_alias}` | `path.space_id_or_alias: string` required | `exists: boolean`; `space_id: id?`; `title: string?`; `external_ref: object?` | Must match portal namespace or authorized query. |
| `GET /api/v1/applet/protocols/{protocol}` | `path.protocol: string` required | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | Instance list may require authorization. |

