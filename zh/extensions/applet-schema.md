# Applet Schema and OpenAPI Draft

## 1. Applet Registration Schema

```json
{
  "type": "cx.applet.registration",
  "applet_id": "cx:applet:example",
  "service_did": "did:web:applet.example",
  "controller_did": "did:web:acme.example",
  "base_url": "https://applet.example/api/v1/applet",
  "bot_actor_id": "did:web:applet.example#bot",
  "protocols": ["slack"],
  "namespaces": {
    "actors": [],
    "spaces": [],
    "handles": []
  },
  "receive_events": true,
  "receive_ephemeral": false,
  "rate_limited": true,
  "requested_scopes": [],
  "proof": {}
}
```

## 2. Namespace Pattern

```json
{
  "exclusive": true,
  "pattern": "did:web:applet.example#ghost-*"
}
```

Pattern grammar:

- `*` matches a single suffix segment
- `**` matches multiple path-like segments
- literal `*` MUST be escaped as `\\*`

## 3. Transaction Endpoint

```text
PUT /api/v1/applet/transactions/{txn_id}
```

Request:

```json
{
  "txn_id": "cx:txn:...",
  "source_service_did": "did:web:relay.example",
  "events": [],
  "ephemeral": []
}
```

Response:

```json
{ "ok": true }
```

## 4. Query Actor

```text
GET /api/v1/applet/actors/{actor_id}
```

Response:

```json
{
  "exists": true,
  "actor_id": "did:web:applet.example#ghost-u123",
  "display_name": "Alice",
  "external_ref": {}
}
```

## 5. Query Space

```text
GET /api/v1/applet/spaces/{space_id_or_alias}
```

Response:

```json
{
  "exists": true,
  "space_id": "cx:space:portal:slack:T:C",
  "title": "#general",
  "external_ref": {}
}
```

## 6. Protocol Metadata

```text
GET /api/v1/applet/protocols/{protocol}
```

Response:

```json
{
  "protocol": "slack",
  "display_name": "Slack",
  "field_types": {},
  "instances": []
}
```

## 7. Bridge Error Event

```json
{
  "type": "cx.applet.bridge_error",
  "applet_id": "cx:applet:example",
  "external_ref": {},
  "error_code": "external_rate_limited",
  "message": "external network rejected the message",
  "retry_after_ms": 1000
}
```
