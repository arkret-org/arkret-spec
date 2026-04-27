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

## 4. Canonical Operation IDs

Bindings SHOULD map to canonical `operation_id` values. Values use `cx.<namespace>.<lower_snake_case>`, for example:

- `cx.server.describe`
- `cx.identity.resolve`, `cx.identity.get_log`, `cx.identity.submit_did_op`
- `cx.repo.submit_commit`, `cx.repo.get_ops`
- `cx.sync.subscribe`, `cx.sync.backfill`, `cx.sync.client_sync`
- `cx.federation.transaction`, `cx.federation.push_ops`, `cx.federation.pull_ops`
- `cx.index.query`, `cx.index.space_hierarchy`
- `cx.directory.search`, `cx.directory.resolve`
- `cx.blob.upload`, `cx.blob.get`
- `cx.push.register_device`, `cx.push.notify`
- `cx.authz.check`, `cx.policy.check`
- `cx.moderation.report`
- `cx.applet.transaction`
- `cx.device_messages.put`
- `cx.keys.upload`, `cx.keys.query`, `cx.keys.claim`
- `cx.agent.protocol_session_start`, `cx.agent.protocol_session_status`

## 5. Non-HTTP Notes

- gRPC: preserve canonical operations, keep metadata for request identity and idempotency.
- WebSocket/SSE: each frame carries operation and envelope and must remain independently verifiable.
- Message queue: message body MUST include signed envelope; topic offset alone is not a canonical cursor.
- libp2p / P2P: peer identity must bind to service or device DID; backfill and snapshot still use signed/verified canonical cursor forms.

HTTP remains default, and transport selection is negotiated by feature discovery.
