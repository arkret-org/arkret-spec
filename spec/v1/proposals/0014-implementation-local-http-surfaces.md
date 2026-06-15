---
ckp: CKP-0014
title: Implementation-local HTTP surfaces found in coauth / yougen audit
normative: false
stability: v1
updated: 2026-06-11
status: draft
created: 2026-06-06
authors:
  - chris@acroidea.com
depends_on: []
---

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

Resolved (now registered Cokret operations): `POST /_cokret/gate/account/session-grants/refresh`
(`ck.gate.account.command.refresh_session_grant`) and
`POST /_cokret/gate/account/session-grants/introspect`
(`ck.gate.account.command.introspect_session_grant`) have been promoted out of
the candidate list and into the operation registry / OpenAPI / service-http-binding.

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

### 5.1 Resolved: Circle administration (now normative)

Circle administration was originally listed above as a candidate
(`POST /_cokret/self/circles`, `GET /_cokret/self/circles`). It has since been
accepted and is **normative** as of the Circle work (see CKP-0007). The full
self-service Circle surface is registered in the canonical operation registry
(`ck.self.circle.*`), the contract catalog, the OpenAPI artifact, and the HTTP
binding (`zh/sync/service-http-binding.md`). Implementations expose it under
`/_cokret/self/circles*`:

- `POST /_cokret/self/circles` → `ck.self.circle.create`
- `GET /_cokret/self/circles` → `ck.self.circle.list`
- `GET /_cokret/self/circles/{circle_id}` → `ck.self.circle.get`
- `POST /_cokret/self/circles/{circle_id}/members` → `ck.self.circle.member.add`
- `DELETE /_cokret/self/circles/{circle_id}/members/{actor_id}` →
  `ck.self.circle.member.remove`
- `POST /_cokret/self/circles/{circle_id}/scope-rotate` →
  `ck.self.circle.scope_rotate`
- `POST /_cokret/self/circles/{circle_id}/archive` → `ck.self.circle.archive`
- `POST /_cokret/self/circles/{circle_id}/tombstone` →
  `ck.self.circle.tombstone`

The remaining bullets in §5 (devices, recovery read/receipts, WebRTC / call
recording, view / document projection, MLS rotate, push preferences,
account-data blocklist, telemetry) stay draft and are deferred to later waves;
none of them is registered as a `ck.self.*` operation yet. In particular the
canonical account-data surface is the verbatim, opaque
`ck.self.account_data.*` family at `/_cokret/self/account_data/{data_type}`,
which is **not** the same as the yougen `POST /_cokret/self/account-data/blocklist`
helper listed above.

## 6. Admin / operations surface adjudication (2026-06 sodmin audit)

The 2026-06 sodmin audit found ~40+ admin endpoints called under `/_soland/admin/*`
that neither soland mounts nor any planning registry lists (actors write ops,
moderation report resolve, federation peers / allow-rules CRUD, authz
capabilities CRUD, handles admin, directory approval, media statistics,
policies CRUD, realm policy / links / member-routability / covered-frontier /
handovers, notary signing-key GET, spaces hierarchy), plus an ops panel set
(`server/info`, `server/stats`, `server/trust-domain`, `server/relaxed-window`,
`audit/attestation-evidence`).

**Adjudication (resolves SPEC-SOD-001 / SPEC-SOD-002):**

1. None of these endpoints are protocol candidates. Administrative and
   operations consoles are deployment products; the Cokret protocol surface
   (`/_cokret/*`) intentionally does not define an admin plane. They will not
   be added to the canonical operation registry, and this CKP does not reserve
   `/_cokret` paths for them.
2. Whether an implementation (soland) mounts any of them under its vendor
   namespace (`/_soland/admin/*`) is product planning owned by that
   implementation's repository, not by this spec.
3. Admin clients (sodmin) MUST NOT hardcode assumptions that a vendor admin
   endpoint exists: they MUST feature-gate UI on the server's advertised
   extension operations (`*.describe` / `supported_operations`) or degrade
   gracefully on 404 (`format_optional_endpoint_error`-style tolerance).
   Hardcoded vendor paths that the server never advertised are a client
   defect, not a spec gap.

**Related adjudications from the same audit:**

- *Agent provision wire body (SPEC-SOD-003)*: the protocol-plane body for
  `POST /_cokret/self/agents` is already canonical
  (`agent-operations.schema.json#/$defs/agent_provision_request_body`:
  `display_name` / `requested_scope` / `accountability` / `pairing_ttl_ms`).
  Implementations carrying a private body shape (`controller_did` +
  `agent_key_proof`) are in drift and must converge on the registered schema;
  no spec change is needed.
- *Recovery policy/receipt write operations (SPEC-SOD-005)*: the protocol
  plane defines read paths (`GET /_cokret/root/identity/recovery-policy`,
  `GET /_cokret/root/identity/receipts`) and the recovery-session strand.
  Write/configure operations (`POST recovery-policy`, `POST recovery-receipt`)
  stay implementation-local (`/_soland/root/identity/*`, registered as
  `org.cokret.soland.*` extension operations) for v1. Promoting them into
  `/_cokret` requires a dedicated CKP with closed schemas per §7.
- *Notary value wire shape (SPEC-SOD-004)*: adjudicated in normative prose —
  `zh/authz/event-auth-state-resolution.md` §4.4 now pins the `type`-tagged
  object from `realm.schema.json` as the only legal wire shape and forbids the
  `kind` / `kind_raw` / `shape` / `k` / `n` / flattened-alias spellings.
  SDK (`cokret_core::notary::NotaryValue`, `kind`-tagged) and
  soland/sodmin (flattened + alias tolerance) must both migrate.

## 7. Required acceptance work

For any candidate accepted from this proposal:

1. Add a closed request / response schema.
2. Add the operation to the operation registry, contract catalog, OpenAPI, and
   operation-schema index.
3. Document auth, audience, replay protection, rate limits, and privacy
   semantics in `service-http-binding.md`.
4. Add conformance vectors before any implementation mounts the path under
   `/_cokret`.
