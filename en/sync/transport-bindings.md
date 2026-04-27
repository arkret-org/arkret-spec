# Transport Bindings

## 1. Scope

Contrix protocol is not bound to REST as the only implementation profile.
The protocol core defines semantic operations, identity/authorization model, policy semantics, and state semantics.

HTTP/JSON is the default interoperability profile; implementations MAY use gRPC, WebSocket, SSE, GraphQL, message queue, or libp2p as long as operation semantics, signing, authorization, idempotency, pagination, streaming, and error behavior are preserved.

## 2. Layers

| Layer | Protocol Core | Example |
| --- | --- | --- |
| Semantic operation | Yes | `submit_commit`, `sync`, `query`, `backfill`, `authz_check`, `applet_transaction` |
| Message envelope | Yes | request id, actor, device, capability refs, idempotency key, cursor, error code |
| Canonical encoding | Yes | canonical JSON, hash/signature profile, optional CBOR profile |
| Transport binding | No (unless explicitly declared) | HTTP/REST, gRPC, WebSocket, SSE, GraphQL, libp2p |
| SDK / product API | No | JavaScript SDK, CLI, native bridge |

`/api/v1/...` paths are default HTTP examples and not the only legal interface shape.

## 3. Binding Requirements

Any binding MUST support:

- service feature discovery with supported transports and supported operations
- carrying authentication and service context (actor, capability refs, Space, action, device)
- idempotent writes
- opaque cursors for listing/history
- stream envelopes for subscription and backfill
- stable error envelope (`code`, `message`, `retry` hints, `details`)
- flow control and throttling signals (`retry-after`, quota, frame/body limits)

## 4. Canonical Operation Names

Bindings SHOULD map to canonical operation names such as:

- `identity.resolve`, `identity.get_log`
- `repo.submit_commit`, `repo.get_ops`
- `sync.subscribe`, `sync.backfill`, `sync.run`
- `index.query`, `index.space_hierarchy`
- `blob.upload`, `blob.get`
- `authz.check`, `policy.check`
- `applet.transaction`
- `device.send_message`
- `agent.protocol_session.start`, `agent.protocol_session.status`

## 5. Non-HTTP Notes

- gRPC: preserve canonical operations, keep metadata for request identity and idempotency.
- WebSocket/SSE: each frame carries operation and envelope and must remain independently verifiable.
- Message queue: message body MUST include signed envelope; topic offset alone is not a canonical cursor.
- libp2p / P2P: peer identity must bind to service or device DID; backfill and snapshot still use signed/verified canonical cursor forms.

HTTP remains default, and transport selection is negotiated by feature discovery.

