# CKP-0014: Implementation-local HTTP surfaces found in coauth / yougen audit

> **Status: draft.** This proposal is an audit record, not an accepted protocol
> change. Until an item below is accepted into the normative operation catalog
> and OpenAPI artifacts, implementations MUST NOT mount it under `/_cokret`.
> Private deployment endpoints MUST use implementation namespaces such as
> `/_coauth/*`, `/_soland/*`, or `/_starid/*`.

## 1. Scope

The 2026-06 coauth / yougen audit found several implementation-local URLs that
were previously documented, mocked, or called as if they belonged to the Cokret
HTTP namespace. This proposal lists the concrete candidates that need a protocol
decision before any implementation can expose them as `/_cokret/*`.

## 2. Account authority and OIDC bridge candidates

These endpoints are useful for native-client sign-in, but they are not currently
registered Cokret operations:

- `GET /_cokret/gate/account/auth/bridge/describe`
- `POST /_cokret/gate/account/auth/oidc/browser-bridge/session`
- `GET /_cokret/gate/account/auth/oidc/exchange/describe`
- `POST /_cokret/gate/account/auth/oidc/exchange`
- `POST /_cokret/gate/account/session-grants/refresh`
- `POST /_cokret/gate/account/session-grants/introspect`

Open question: whether native sign-in should standardize these bridge endpoints,
or whether clients must use `/_cokret/describe.auth_metadata` plus standard OIDC
discovery and token endpoints without a Cokret bridge.

## 3. WebVH / StarID candidates

These paths are StarID / principal implementation details today. If Cokret wants
first-class HTTP bindings for did:webvh inception, update, verification, or
principal DID registration, define them explicitly:

- `POST /_cokret/root/webvh/dids`
- `POST /_cokret/root/webvh/dids/{did}/update`
- `POST /_cokret/root/webvh/dids/{did}/verify`
- `POST /_cokret/root/webvh/dids/{did}/deactivate`
- `POST /_cokret/root/identity/webvh/register`

Open question: whether these belong in the core identity service surface, an
optional WebVH profile, or only service-private namespaces such as `/_starid/*`
and `/_soland/*`.

## 4. Invite and MIMI ingest candidates

These were observed as soland-local ingest surfaces:

- `POST /_cokret/self/invites/intake`
- `POST /_cokret/peer/moves`

Open question: whether they should map to existing event submission /
federation transaction operations instead of receiving dedicated HTTP bindings.

## 5. Client self-service candidates from yougen

yougen still has product scaffold code for device management, recovery UI,
media signaling, Circle administration, and local projection helpers. These need
separate protocol decisions before they can be Cokret HTTP bindings:

- `GET /_cokret/self/devices`
- `POST /_cokret/self/devices/{device_id}/revoke`
- `POST /_cokret/self/devices/{device_id}/rename`
- `POST /_cokret/self/devices/pairing-challenge`
- `POST /_cokret/self/devices/authorize-pairing`
- `GET /_cokret/self/devices/trust`
- `POST /_cokret/self/devices/{device_id}/verify`
- `GET /_cokret/root/identity/recovery-policy`
- `GET /_cokret/self/recovery/policies`
- `GET /_cokret/self/recovery/receipts`
- `POST /_cokret/self/webrtc/sessions`
- `POST /_cokret/self/webrtc/sessions/{session_id}/signals`
- `POST /_cokret/self/calls/{session_id}/recording/start`
- `POST /_cokret/self/circles`
- `GET /_cokret/self/circles`
- `GET /_cokret/self/views/{view_id}/projection`
- `GET /_cokret/self/projection/documents/{morph_id}`
- `POST /_cokret/self/mls/rotate`
- `POST /_cokret/edge/push/preferences`
- `POST /_cokret/self/account-data/blocklist`
- `POST /_cokret/self/telemetry/error`

Open question: which items should be replaced by existing canonical operations
such as `/_cokret/self/events`, `/_cokret/self/account/subscribe`,
`/_cokret/gate/account/device-pair`, `/_cokret/self/rtc/ice-config`, or
`/_cokret/self/moderation/report`, and which deserve new optional profiles.

## 6. Required acceptance work

For any candidate accepted from this proposal:

1. Add a closed request / response schema.
2. Add the operation to the operation registry, contract catalog, OpenAPI, and
   operation-schema index.
3. Document auth, audience, replay protection, rate limits, and privacy
   semantics in `service-http-binding.md`.
4. Add conformance vectors before any implementation mounts the path under
   `/_cokret`.
