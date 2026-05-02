# Service HTTP/JSON Binding Draft

## 1. Goal

This document defines the default HTTP/JSON binding request and response shape used for service interoperability.

Contrix protocol is not hard-coupled to REST semantics. Other transport bindings MAY use gRPC, WebSocket, SSE, message queue, or libp2p as long as they preserve the same operation semantics, authentication/authorization rules, idempotency, pagination, streaming, errors, and flow-control behavior.

## 2. General Requirements

- Requests and responses use `Content-Type: application/json` by default.
- Write requests MUST support idempotency via idempotency key or content-id style deduplication.
- Authentication MAY use bearer token, HTTP Message Signature, DID proof, or a transport-native equivalent.
- Services MUST expose `describe` / feature discovery for supported paths, profiles, and limits.
- Error responses MUST use a stable error schema.
- Authentication material MUST be carried in headers, HTTP Message Signatures, mTLS, or signed proof bodies. Protected endpoints MUST NOT accept query-string authentication.
- Unknown paths, wrong methods, rate limits, temporary unavailability, and invisible resources MUST use the standard error semantics in `api-conventions.md`.

### 2.1 REST API Namespace Organization

The Contrix HTTP/JSON binding is organized by **service role and canonical operation**, not by fixed product buckets such as Client API, Server API, and Push API. Clients, Principal Servers, Repos, Directories, Applets, and Push Gateways may each expose their own service surface; service discovery declares which namespaces a node actually supports.

Default REST namespaces:

| Namespace | Primary callers | Semantics | Spec |
| --- | --- | --- | --- |
| `/server/*` | clients and services | service description, feature discovery, auth metadata | `service-surface.md`, `api-conventions.md` |
| `/identity/*` | clients, services, registries | DID document, key log, DID operation, receipt | `service-surface.md`, `identity-did.md` |
| `/repo/*` | clients, Principal Servers, read-only repo storage replicas | signed commit submit, operation/commit reads, repo incremental sync | `operations-sync.md`, `service-surface.md` |
| `/sync/*` | clients, Principal Servers | client aggregate sync, Space subscription, backfill, snapshot head | `client-sync.md`, `service-surface.md` |
| `/federation/*` | Principal Servers | cross-domain transaction, operation push/pull, member query, actor verification | `federation.md`, `federation-wire.md` |
| `/directory/*` | clients and services | authorized discovery and resolution of Spaces, Organizations, Actors, and handles | `discovery-directory.md` |
| `/blob/*` | clients and services | blob upload, HEAD, authenticated download | `media-and-blob.md` |
| `/push/*` | clients, Sync, Push Gateways | push device registration, unregister, blind wakeup delivery | `push-notifications.md` |
| `/device_messages/*`, `/keys/*` | E2EE clients, Principal Servers | to-device, one-time key, fallback key, device-list related operations | `device-crypto-verification.md` |
| `/authz/*`, `/contrix/v1/check` | clients, Repos, Sync, Policy Servers | capability pre-check and signed policy decisions | `capabilities.md`, `policy-server.md` |
| `/contrix/v1/ice-config` | call clients, Media Services | short-lived TURN/STUN/ICE credentials | `webrtc-signaling.md` |
| `/moderation/*` | clients and moderation services | reports, review queues, or extended moderation entry points | `moderation.md` |
| `/applet/*` | Contrix services calling Applets | applet ping / describe, transaction push, ghost actor / portal lookup | `applet-integration.md` |

From a client perspective, the common API set usually includes `/server`, `/identity`, `/repo`, `/sync`, `/directory`, `/blob`, `/push`, `/device_messages`, `/keys`, and `/authz`. The service-to-service set usually includes `/federation`, `/repo`, `/sync`, `/authz`, `/contrix/v1/check`, `/applet`, and `/push/notify`. Search, inbox, notifications, and View projection are client-local derived capabilities by default; network search interfaces must be declared by an extension profile.

Before adding a new top-level REST namespace, the spec MUST update `service-api-schema.md`, feature discovery, and the related conformance profile. Implementations MUST NOT use undeclared paths to bypass canonical operation, capability, idempotency, pagination, or error semantics.

### 2.2 Endpoint Contract Rules

Every REST endpoint definition must include at least:

- `operation_id` / canonical operation
- path parameters, query parameters, and request body field types
- successful response field types
- authentication mode: `public_metadata`, `user_session`, `device_proof`, `service_signature`, `policy_token`, `applet_signature`, etc.
- access restrictions: Space membership, history visibility, capability, service delegation, namespace, plaintext visibility, rate limit, and quota
- idempotency key: `Idempotency-Key`, path `{txn_id}`, `commit_id`, `operation_id`, or canonical request hash
- standard error envelope on failure

JSON examples are illustrative only and are not complete schemas. Normative endpoint definitions MUST use field tables that state field name, location, type, requiredness, meaning, and constraints.

Default rules:

- Except for endpoints explicitly marked as `public_metadata`, all endpoints MUST authenticate the caller.
- Authentication only identifies the caller; services MUST still enforce capability, Space policy, history visibility, service delegation, and revocation checks.
- Service-to-service calls MUST use HTTP Message Signature or equivalent service DID proof bound to method, target URI, content digest, origin service DID, and destination service DID.
- Service-to-service `origin` and `destination` MUST be service DIDs and must match DID Document service endpoints, target URL, Space policy / service delegation, and the signature transcript.
- Protected endpoints MUST NOT accept tokens, API keys, or signature material in query strings. Short-lived download URLs may only use derived, single-purpose, revocable, short-expiry tokens.
- Endpoints returning `not_found` MUST keep indistinguishable semantics for missing vs. existing-but-not-visible resources unless the caller has administrative visibility.
- Bulk reads MUST enforce a maximum `limit`, and pagination cursors must be opaque tokens.
- Routers MUST return `404 unrecognized_endpoint` for unknown paths under `/api/v1/*` and `/contrix/v1/*`, and `405 method_not_allowed` for unsupported methods on known paths, without entering business logic.

### 2.3 Endpoint Contract Registry

Type shorthand: `did` is a DID URI, `id` is a protocol object id, `cursor` / `token` is an opaque string, `signature` is `{kid, alg?, sig}`, and `proof` is a DID / HTTP message / detached JWS proof. `operations` is the wire name for operation arrays. Human-readable documents SHOULD spell out Operation.

| Endpoint | Request type | Auth / access restrictions | Success type |
| --- | --- | --- | --- |
| `GET /api/v1/server/describe` | query: none or `service_type?` | `public_metadata`; must not return private topology, secrets, or unauthorized internal endpoints. | `{service_did, service_type, protocol_version, supported_features[], supported_bindings[], supported_operations[], auth_metadata?, limits}` |
| `GET /api/v1/identity/describe` | query: none | `public_metadata`; rate-limitable. | `{service_did, registry_mode, supported_receipts[], protocol_version, profiles[]}` |
| `POST /api/v1/identity/resolve` | body `{did: did, include?: string[]}` | `public_metadata`; private DIDs MAY require `user_session` or presentation proof. | `{did_document, key_log_head?, seq?, receipts?, method_evidence?}` |
| `GET /api/v1/identity/document` | query `{did: did, version?: string}` | Same as `identity.resolve`. | `{did_document, head_event_hash?, seq?, receipts?}` |
| `GET /api/v1/identity/log` | query `{did: did, cursor?: cursor, limit?: int}` | Public DIDs may be public; private / pairwise DIDs MUST require holder-approved proof. | `{events[], next_cursor?, has_more}` |
| `POST /api/v1/identity/submit-did-operation` | body `{did: did, seq: int, prev_event_hash?: string, patch: object, proofs: proof[]}` | `device_proof` or recovery proof; MUST satisfy DID method / key-log authorization. | `{status, head_event_hash, seq, receipts?}` |
| `GET /api/v1/identity/receipts` | query `{did: did, head: string}` | Same DID visibility; witness receipts may expose only minimal evidence. | `{receipts[], threshold_met?: boolean}` |
| `GET /api/v1/repo/describe` | query `{repo_id?: did}` | `user_session` / `service_signature`; only for repos visible to the caller. | `{repo_did, head_commit, supported_signatures[], limits}` |
| `GET /api/v1/repo/commits` | query `{repo_id: did, cursor?: cursor, limit?: int}` | Repo owner, authorized replica, Space policy, or history visibility must allow access. | `{commits[], next_cursor?, has_more}` |
| `GET /api/v1/repo/commit` | query `{repo_id?: did, commit_id: id}` | Same repo-read access; invisible resources return `not_found`. | `{commit, operations?, proofs?}` |
| `POST /api/v1/repo/operations` | body `{repo_id?: did, operation_ids?: id[], event_ids?: id[], include_payload?: boolean}` | Same repo-read access; payload visibility follows Space policy / E2EE envelope rules. | `{operations[], missing[], unauthorized[]?}` |
| `POST /api/v1/repo/sync` | body `{repo_id: did, since?: cursor, limit?: int, filters?: object}` | Repo owner, authorized replica, or delegated service. | `{operations[], next_cursor?, has_more}` |
| `POST /api/v1/repo/submit-commit` | body `{repo_id: did, commit: object, expected_head?: string, idempotency_key?: string}` | Commit signature + capability; repo MUST verify actor DID, device/session, CAS, and Space policy. | `{status, commit_id, head_commit?, sync_token}` |
| `POST /api/v1/sync` | body `{since?: token, filter?: object, set_presence?: string, timeout_ms?: int}` | `user_session` bound to principal/device. | Client Sync response `{next_batch, spaces?, to_device?, account_data?, device_lists?}` |
| `GET /api/v1/sync/describe` | query none | `public_metadata` or `user_session`; private limits may require auth. | `{service_did, supported_sync_profiles[], limits, frontier?}` |
| `GET /api/v1/sync/subscribe` | query `{space_id: id, cursor?: cursor}` | Space read + service delegation; non-E2EE private content only to principal / plaintext-visible services. | event stream frames `{type, seq, cursor?, payload}` |
| `GET /api/v1/sync/backfill` | query `{space_id: id, cursor?: cursor, limit?: int}` | History visibility + membership frontier + E2EE epoch policy. | `{events[], prev_cursor?, next_cursor?, limited?}` |
| `GET /api/v1/sync/snapshot-head` | query `{space_id: id}` | Space read; snapshot manifest must be signed. | `{snapshot_ref, state_hash, frontier, signature}` |
| `PUT /api/v1/federation/transactions/{txn_id}` | path `{txn_id}` body `{origin: did, destination: did, service_binding_ref, operations[], receipts?, frontier?}` | `service_signature`; destination service DID, URL, Space policy, and service binding must match. | `{ok: true, accepted[], rejected[], next_retry_at?}` |
| `POST /api/v1/federation/push-operations` | body `{origin: did, destination: did, space_id: id, service_binding_ref, operations[]}` | `service_signature`; origin must be acceptable under Space federation policy; each operation is verified independently. | `{accepted[], rejected[], quarantine[]?}` |
| `GET /api/v1/federation/pull-operations` | query `{space_id: id, after_cursor?: cursor, limit?: int}` | `service_signature`; requester must have backfill rights and plaintext-visibility eligibility. | `{operations[], snapshot_bootstrap?, next_cursor?, has_more}` |
| `GET /api/v1/federation/space-members` | query `{space_id: id, cursor?: cursor, limit?: int}` | `service_signature`; only for participant Principal Servers or policy-allowed services. | `{members[], membership_frontier, next_cursor?}` |
| `POST /api/v1/federation/verify-actor` | body `{actor_id: did, challenge?: string, signed_payload_hash?: string, signature: signature, purpose: string, space_id?: id}` | `service_signature`; not a public DID oracle; requester must have a federation, join, event-source, or shared-Space purpose. | `{valid: boolean, actor_id, verified_key_id?, key_log_head?, did_document_ref?, expires_at?, warnings[]}` |
| `GET /api/v1/directory/describe` | query none | `public_metadata`; rate-limitable. | `{service_did, resource_types[], discovery_profiles[], restricted_query_proof?: boolean}` |
| `POST /api/v1/directory/search-spaces` | body `{query?: string, organization_did?: did, parent_space_id?: id, requester?: did, proofs?: proof[], cursor?: cursor, limit?: int}` | Discoverability + requester proof + policy filtering; hidden resources do not leak existence. | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-space` | body `{space_id?: id, alias?: string, invite_token?: string, signed_link?: string, requester?: did, proofs?: proof[]}` | Invite / restricted / secret Spaces use uniform `not_found` failure. | `{space_preview, stripped_state?, join_rule?, via_services?}` |
| `POST /api/v1/directory/search-organizations` | body `{query?: string, claims?: object, cursor?: cursor, limit?: int}` | Only public or authorized-discoverable organizations. | `{results[], next_cursor?}` |
| `POST /api/v1/directory/resolve-organization` | body `{organization_did?: did, handle?: string, proofs?: proof[]}` | Public organization DID resolution does not expose members or topology. | `{organization_preview, did_document_ref?, endorsements?}` |
| `POST /api/v1/directory/search-actors` | body `{query?: string, space_id?: id, organization_did?: did, cursor?: cursor, limit?: int}` | Must not reveal pairwise/private DID or undisclosed organization accounts. | `{results[], next_cursor?}` |
| `GET /api/v1/directory/search-users` | query `{q: string, space_id?: id, limit?: int}` | `user_session`; mention autocomplete constrained by shared Space / directory policy. | `{results[]}` |
| `POST /api/v1/directory/resolve-handle` | body `{handle: string, expected_did?: did, proof_challenge?: string}` | Follows handle bidirectional verification; private handle requires presentation. | `{did, handle, verified: boolean, claims?}` |
| `POST /api/v1/blob/upload` | body binary/multipart + metadata `{space_id?, sha256?, size, media_type?, filename?, purpose?}`; `Content-Type` optional | `user_session`; upload capability, quota, media policy; private blob is bound to Space / actor. | `{blob_ref, size, media_type?, sha256, upload_receipt?}` |
| `HEAD/GET /api/v1/blob/get` | query `{blob_ref: string}` headers `Authorization?`, `Range?`, `X-Contrix-Wait-For?` | Public blobs may be anonymous; private blobs verify actor/device/Space/purpose/expiry; query-string auth is not allowed. | bytes or headers `{Content-Length?, Digest?, Cache-Control, Content-Type?, Content-Disposition?, Content-Range?}` |
| `POST /api/v1/push/register-device` | body `{device_id: id, push_gateway: url, push_key: string, platform?: string, app_id?: string, display_name?: string}` | `user_session` for same principal/device; push key must be encrypted or minimally disclosed at rest. | `{ok: true, registration_id?, expires_at?}` |
| `POST /api/v1/push/unregister-device` | body `{device_id: id, push_key?: string, app_id?: string}` | `user_session` for same device/principal or device-revocation path. | `{ok: true}` |
| `POST /api/v1/push/notify` | body `{notification: {event_id?, space_id?, type, sender?, push_hint?, counts?, devices[]}}` | `service_signature` from authorized Sync or notification service; MUST be blind/minimized for E2EE. | `{rejected[]}` |
| `PUT /api/v1/device_messages/{txn_id}` | path `{txn_id}` body `{messages: {principal_id: {device_id: {type, content}}}}` | Sender `user_session` / device key; target must be authorized device; idempotent by `(sender, txn_id)`. | `{ok: true, delivered?, unknown_devices?}` |
| `GET /api/v1/device_messages` | query `{from?: token, limit?: int}` | `user_session` bound to current device; only this device queue. | `{events[], next_batch?, limited?}` |
| `POST /api/v1/keys/upload` | body `{device_id: id, one_time_keys?: object, fallback_keys?: object, device_signature: signature}` | Current device proof; key must link to self-signing / principal key. | `{one_time_key_counts, fallback_keys?}` |
| `POST /api/v1/keys/query` | body `{device_keys: {principal_id: string[]}, timeout_ms?: int}` | `user_session`; query scope may be relationship / Space limited. | `{device_keys, failures?}` |
| `POST /api/v1/keys/claim` | body `{one_time_keys: {principal_id: {device_id: algorithm}}}` | `user_session`; one-time key MUST be atomically consumed. | `{one_time_keys, failures?}` |
| `GET /api/v1/authz/effective-grants` | query `{space_id: id, subject: did, at?: string}` | Subject, Space admin, or authorized service; must not enumerate unrelated subjects. | `{grants[], state_hash?, evaluated_at}` |
| `GET /api/v1/authz/invites` | query `{space_id?: id, subject: did or string, cursor?: cursor}` | Subject or inviter/admin; secret invites are not enumerable. | `{invites[], next_cursor?}` |
| `POST /api/v1/authz/check` | body `{actor: did, action: string, resource: object, context?: object}` | Caller must be the relevant actor, Repo/Sync pre-check service, or policy-authorized service. | `{allowed: boolean, reason_code?, grants?, obligations?}` |
| `POST /contrix/v1/check` | body `{request_id, space_id?, request_canonical_hash, action, actor, source, event_preview?, auth_context?}` | `policy_token` / `service_signature`; accepts only minimally disclosed fields. | signed policy decision `{decision, reason_code, expires_at, obligations?, signature}` |
| `POST /api/v1/moderation/report` | body `{space_id: id, target_ref: id, reason: enum, description?: string, reporter: did, evidence_refs?: id[]}` | `user_session`; reporter must be able to see target; report visible only to moderators. | `{report_id, status, routed_to?}` |
| `GET /api/v1/applet/ping` | query none | `public_metadata` or `service_signature`; must not leak private namespace. | `{ok, applet_id, service_did, protocol_version}` |
| `GET /api/v1/applet/describe` | query none | `service_signature` SHOULD; public mode returns only public capabilities. | `{applet_id, service_did, protocols[], namespaces, limits, auth}` |
| `PUT /api/v1/applet/transactions/{txn_id}` | path `{txn_id}` body `{source_service_did, events[], ephemeral?}` | `service_signature`; Applet must verify every event signature, namespace, and capability. | `{ok: true, rejected?, retry_after_ms?}` |
| `GET /api/v1/applet/actors/{actor_id}` | path `{actor_id}` | `service_signature`; actor id must match Applet actor namespace. | `{exists, actor_id, display_name?, external_ref?}` or `not_found` |
| `GET /api/v1/applet/spaces/{space_id_or_alias}` | path `{space_id_or_alias}` | `service_signature`; must match portal namespace or authorized query. | `{exists, space_id?, title?, external_ref?}` |
| `GET /api/v1/applet/protocols/{protocol}` | path `{protocol}` | May be `public_metadata`; instance list may require auth. | `{protocol, display_name, icon_blob?, field_types, instances?}` |
| `GET /api/v1/applet/third_party/users` | query `{protocol, ...external_ids}` | `service_signature`; query fields must be inside registration namespace. | `{actor_id?, exists, external_ref?}` |
| `GET /api/v1/applet/third_party/locations` | query `{protocol, ...external_ids}` | `service_signature`; query fields must be inside portal namespace. | `{space_id?, exists, external_ref?}` |
| `POST /contrix/v1/ice-config` | body `{space_id: id, call_id: id, actor_id: did, device_id: id, mode: string}` | `user_session`; actor must have call/media capability, and Media Service must be delegated by Space policy. | `{ttl_seconds, ice_servers[], policy, signature}` |

`POST /api/v1/federation/verify-actor` is only a cache accelerator or diagnostic helper. Before accepting events, membership changes, or device bindings, the receiver MUST still independently verify the DID Document, key log, signature transcript, capability, and Space policy; a peer's "valid" answer is not final authorization.

### 2.4 Field-Level Schema Index

This section is the field-level schema index for REST endpoints. Field syntax is `name: type - meaning`. Fields in "Required fields" are required; fields in "Optional fields" are optional. Non-body locations are marked as `path.`, `query.`, or `header.`.

| `operation_id` | Required fields | Optional fields | Response fields | Constraints |
| --- | --- | --- | --- | --- |
| `cx.server.describe` | none | `query.service_type: string - filter service type` | `service_did: did - service DID`; `service_type: string`; `protocol_version: string`; `supported_features: string[]`; `supported_bindings: object[]`; `supported_operations: operation_id[]`; `auth_metadata: object?`; `limits: object?` | `public_metadata`; must not expose private topology or secrets. |
| `cx.identity.describe_registry` | none | none | `service_did: did`; `registry_mode: enum(writer,witness,replica)`; `supported_receipts: string[]`; `protocol_version: string`; `profiles: string[]` | `public_metadata`; rate-limitable. |
| `cx.identity.resolve` | `did: did - DID to resolve` | `include: string[] - extra evidence such as key_log/receipts` | `did_document: object`; `key_log_head: id?`; `seq: int?`; `receipts: object[]?`; `method_evidence: object?` | Private or pairwise DIDs may require presentation proof. |
| `cx.identity.get_document` | `query.did: did` | `query.version: string - version or head` | `did_document: object`; `head_event_hash: string?`; `seq: int?`; `receipts: object[]?` | Same visibility as `cx.identity.resolve`. |
| `cx.identity.get_log` | `query.did: did` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `has_more: boolean` | Private or pairwise DIDs MUST require holder-approved proof. |
| `cx.identity.submit_did_operation` | `did: did`; `seq: int`; `patch: object`; `proofs: proof[]` | `prev_event_hash: string` | `status: enum(accepted,duplicate)`; `head_event_hash: string`; `seq: int`; `receipts: object[]?` | MUST satisfy DID method / key-log authorization; idempotent by `did+seq`. |
| `cx.identity.get_receipts` | `query.did: did`; `query.head: string` | none | `receipts: object[]`; `threshold_met: boolean?` | Expose only minimal witness receipts. |
| `cx.repo.describe` | none | `query.repo_id: did` | `repo_did: did`; `head_commit: id`; `supported_signatures: string[]`; `limits: object?` | Only repos visible to the caller. |
| `cx.repo.list_commits` | `query.repo_id: did` | `query.cursor: cursor`; `query.limit: int` | `commits: object[]`; `next_cursor: cursor?`; `has_more: boolean` | Limited by repo-read access, history visibility, and Space policy. |
| `cx.repo.get_commit` | `query.commit_id: id` | `query.repo_id: did`; `query.include_operations: boolean` | `commit: object`; `operations: object[]?`; `proofs: object[]?` | Invisible resources return `not_found`. |
| `cx.repo.get_operations` | at least one of `operation_ids: id[]` or `event_ids: id[]` | `repo_id: did`; `include_payload: boolean` | `operations: object[]`; `missing: id[]`; `unauthorized: id[]?` | Payload visibility follows Space policy / E2EE envelope rules. |
| `cx.repo.sync` | `repo_id: did` | `since: cursor`; `limit: int`; `filters: object` | `operations: object[]`; `next_cursor: cursor?`; `has_more: boolean` | Repo owner, authorized replica, or delegated service only. |
| `cx.repo.submit_commit` | `repo_id: did`; `commit: object` | `expected_head: string`; `idempotency_key: string` | `status: enum(accepted,duplicate)`; `commit_id: id`; `head_commit: id?`; `sync_token: token` | MUST verify commit signature, CAS, capability, and Space policy. |
| `cx.sync.client_sync` | none | `since: token`; `filter: object`; `set_presence: enum(online,offline,unavailable)`; `timeout_ms: int` | `next_batch: token`; `spaces: object?`; `to_device: object?`; `account_data: object?`; `device_lists: object?` | `user_session` must bind principal/device. |
| `cx.sync.describe` | none | none | `service_did: did`; `supported_sync_profiles: string[]`; `limits: object`; `frontier: object?` | Private frontier may require authentication. |
| `cx.sync.subscribe` | `query.space_id: id` | `query.cursor: cursor` | stream frame: `type: string`; `seq: int`; `cursor: cursor?`; `payload: object` | Space read + service delegation; private plaintext only inside the authorized visibility boundary. |
| `cx.sync.backfill` | `query.space_id: id` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `prev_cursor: cursor?`; `next_cursor: cursor?`; `limited: boolean?` | Enforce history visibility, membership frontier, and E2EE epoch policy. |
| `cx.sync.get_snapshot_head` | `query.space_id: id` | none | `snapshot_ref: id`; `state_hash: string`; `frontier: object`; `signature: signature` | Snapshot manifest MUST be signed. |
| `cx.federation.transaction` | `path.txn_id: id`; `origin: did`; `destination: did`; `service_binding_ref: object`; `operations: object[]` | `receipts: object[]`; `frontier: object` | `ok: boolean`; `accepted: id[]`; `rejected: object[]`; `next_retry_at: datetime?` | `service_signature`; destination DID, URL, policy, and binding must match. |
| `cx.federation.push_operations` | `origin: did`; `destination: did`; `space_id: id`; `service_binding_ref: object`; `operations: object[]` | none | `accepted: id[]`; `rejected: object[]`; `quarantine: id[]?` | Every operation is independently signature and authorization checked. |
| `cx.federation.pull_operations` | `query.space_id: id` | `query.after_cursor: cursor`; `query.limit: int` | `operations: object[]`; `snapshot_bootstrap?: object`; `next_cursor: cursor?`; `has_more: boolean` | Requester needs backfill rights and plaintext-visibility eligibility. |
| `cx.federation.space_members` | `query.space_id: id` | `query.cursor: cursor`; `query.limit: int` | `members: object[]`; `membership_frontier: object`; `next_cursor: cursor?` | Participant Principal Servers or policy-allowed services only. |
| `cx.federation.verify_actor` | `actor_id: did`; `purpose: enum(event_source,federation_join,device_binding)`; `signature: signature` | `space_id: id`; `challenge: string`; `signed_payload_hash: string` | `valid: boolean`; `actor_id: did`; `verified_key_id: string?`; `key_log_head: id?`; `did_document_ref: string?`; `expires_at: datetime?`; `warnings: string[]` | Cache/diagnostic only; never replaces local DID, key-log, capability, or Space policy verification. |
| `cx.directory.describe` | none | none | `service_did: did`; `resource_types: string[]`; `discovery_profiles: string[]`; `restricted_query_proof: boolean?` | `public_metadata`; rate-limitable. |
| `cx.directory.search_spaces` | none | `query: string`; `organization_did: did`; `parent_space_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | Hidden resources must not leak existence. |
| `cx.directory.resolve_space` | one of `space_id: id`, `alias: string`, `invite_token: string`, `signed_link: string` | `requester: did`; `proofs: proof[]` | `space_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `via_services: did[]?` | Secret/restricted Spaces use uniform `not_found`. |
| `cx.directory.search_organizations` | none | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | Only public or authorized-discoverable organizations. |
| `cx.directory.resolve_organization` | one of `organization_did: did` or `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | Organization resolution does not disclose members or topology. |
| `cx.directory.search_actors` | none | `query: string`; `space_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | Must not reveal pairwise/private DIDs. |
| `cx.directory.search_users` | `query.q: string` | `query.space_id: id`; `query.limit: int` | `results: object[]` | Mention autocomplete is constrained by shared Space / directory policy. |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string` | `did: did`; `handle: string`; `verified: boolean`; `claims: object[]?` | Private handles require presentation. |
| `cx.blob.upload` | `size: int` | `space_id: id`; `sha256: string`; `media_type: string`; `filename: string`; `purpose: string`; binary/multipart body; `header.Content-Type: string` | `blob_ref: string`; `size: int`; `media_type: string?`; `sha256: string`; `upload_receipt: object?` | Upload capability, quota, and media policy apply; `Content-Type` defaults to `application/octet-stream`. |
| `cx.blob.head` | `query.blob_ref: string` | `header.Authorization: token`; `header.X-Contrix-Wait-For: token` | headers include `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?` | Private blobs must verify actor/device/Space/purpose/expiry; headers must not leak invisible resources. |
| `cx.blob.get` | `query.blob_ref: string` | `header.Authorization: token`; `header.Range: string`; `header.X-Contrix-Wait-For: token` | bytes; headers include `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?`, `Content-Range?`, `Location?` | Private blobs must verify actor/device/Space/purpose/expiry; Range and redirects must not leak invisible resources. |
| `cx.push.register_device` | `device_id: id`; `push_gateway: url`; `push_key: string` | `platform: string`; `app_id: string`; `display_name: string` | `ok: boolean`; `registration_id: id?`; `expires_at: datetime?` | Only same principal/device can register. |
| `cx.push.unregister_device` | `device_id: id` | `push_key: string`; `app_id: string` | `ok: boolean` | Same device/principal or device-revocation path. |
| `cx.push.notify` | `notification: object` | `notification.event_id: id`; `notification.space_id: id`; `notification.sender: did`; `notification.push_hint: string`; `notification.counts: object`; `notification.devices: object[]` | `rejected: object[]` | Only authorized Sync or notification-service callers; E2EE notifications MUST be minimized. |
| `cx.device_messages.put` | `path.txn_id: id`; `messages: object` | none | `ok: boolean`; `delivered: object?`; `unknown_devices: object?` | Idempotent by sender + txn_id; target must be authorized device. |
| `cx.device_messages.get` | none | `query.from: token`; `query.limit: int` | `events: object[]`; `next_batch: token?`; `limited: boolean?` | Only the current device queue. |
| `cx.keys.upload` | `device_id: id`; `device_signature: signature` | `one_time_keys: object`; `fallback_keys: object` | `one_time_key_counts: object`; `fallback_keys: object?` | Key must link to self-signing / principal key. |
| `cx.keys.query` | `device_keys: object` | `timeout_ms: int` | `device_keys: object`; `failures: object?` | Query scope may be relationship / Space limited. |
| `cx.keys.claim` | `one_time_keys: object` | none | `one_time_keys: object`; `failures: object?` | One-time key MUST be atomically consumed. |
| `cx.authz.get_effective_grants` | `query.space_id: id`; `query.subject: did` | `query.at: string` | `grants: object[]`; `state_hash: string?`; `evaluated_at: datetime` | Subject, Space admin, or authorized service only. |
| `cx.authz.get_invites` | `query.subject: did or string` | `query.space_id: id`; `query.cursor: cursor` | `invites: object[]`; `next_cursor: cursor?` | Secret invites are not enumerable. |
| `cx.authz.check` | `actor: did`; `action: string`; `resource: object` | `context: object` | `allowed: boolean`; `reason_code: string?`; `grants: object[]?`; `obligations: object[]?` | Policy allow does not create capability. |
| `cx.policy.check` | `request_id: string`; `request_canonical_hash: string`; `action: string`; `actor: did`; `source: object` | `space_id: id`; `event_preview: object`; `auth_context: object` | `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `reason_code: string`; `expires_at: datetime`; `obligations: object[]?`; `signature: signature` | Minimal disclosure only; cache by request hash. |
| `cx.moderation.report` | `space_id: id`; `target_ref: id`; `reason: enum`; `reporter: did` | `description: string`; `evidence_refs: id[]` | `report_id: id`; `status: string`; `routed_to: did[]?` | Reporter must see target; report visible only to moderators. |
| `cx.applet.ping` | none | none | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | Must not leak private namespace. |
| `cx.applet.describe` | none | none | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | Public mode returns only public capabilities. |
| `cx.applet.transaction` | `path.txn_id: id`; `source_service_did: did`; `events: object[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet verifies event signature, namespace, and capability. |
| `cx.applet.query_actor` | `path.actor_id: did` | none | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | Actor id must match the namespace. |
| `cx.applet.query_space` | `path.space_id_or_alias: string` | none | `exists: boolean`; `space_id: id?`; `title: string?`; `external_ref: object?` | Must match portal namespace or authorized query. |
| `cx.applet.protocol_metadata` | `path.protocol: string` | none | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | Instance list may require authorization. |
| `cx.applet.third_party_users` | `query.protocol: string`; external ids | none | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | Query fields must be inside the registration namespace. |
| `cx.applet.third_party_locations` | `query.protocol: string`; external ids | none | `space_id: id?`; `exists: boolean`; `external_ref: object?` | Query fields must be inside the portal namespace. |
| `cx.media.ice_config` | `space_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `mode: string` | none | `ttl_seconds: int`; `ice_servers: object[]`; `policy: object`; `signature: signature` | Actor needs call/media capability; Media Service must be delegated. |

## 3. Repo API

### 3.1 Submit Commit

```text
POST /api/v1/repo/submit-commit
```

Request example (not a complete schema):

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "commit": {
    "commit_id": "cx:commit:01JS0KE...",
    "prev": ["cx:commit:01JS0KD..."],
    "operations": [],
    "signature": {}
  }
}
```

Response example (not a complete schema):

```json
{
  "status": "accepted",
  "commit_id": "cx:commit:01JS0KE...",
  "sync_token": "opaque"
}
```

When `expected_state_hash` verification fails, return `409 cas_conflict`.

The protocol-level repo write unit is a signed commit. Implementations MAY accept a single operation at an SDK or local API layer, but before network propagation, sync, or audit it MUST be wrapped in a signed commit. Receivers MUST NOT treat bare operations that are not part of a commit as canonical history.

### 3.2 Incremental Sync

```text
POST /api/v1/repo/sync
```

Request example (not a complete schema):

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "since": "cursor-or-operation-id",
  "limit": 500
}
```

Response example (not a complete schema):

```json
{
  "operations": [],
  "next_cursor": "opaque",
  "has_more": true
}
```

## 4. Identity API

```text
POST /api/v1/identity/resolve
```

Request example (not a complete schema):

```json
{
  "did": "did:web:alice.example"
}
```

Response example (not a complete schema):

```json
{
  "did_document": {
    "id": "did:web:alice.example",
    "verification_method": [],
    "service": []
  },
  "key_log_head": "cx:keyevt:01JS...",
  "seq": 5
}
```

The resolver MUST return enough method-specific evidence for clients to verify control history.

## 5. Sync API

### 5.1 Client Incremental Sync

```text
POST /api/v1/sync
```

This endpoint maps to `cx.sync.client_sync` and is used by clients to fetch account / Space filtered incremental views. Request and response shapes are defined in `client-sync.md`.

### 5.2 Space Incremental Stream Subscription

```text
GET /api/v1/sync/subscribe?space_id=<space_id>&cursor=<cursor>
```

Frame:

```json
{
  "type": "event",
  "seq": 106,
  "payload": {}
}
```

The same semantic stream MAY be carried by WebSocket, SSE, or long polling, but the default HTTP/JSON reference path is `/api/v1/sync/subscribe`. `/sync/stream` is used only as an internal transport frame name and is not a new canonical operation.

## 6. Directory API

```text
POST /api/v1/directory/search-spaces
POST /api/v1/directory/resolve-space
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

Directory endpoints MUST apply discoverability checks, requestor proof, moderation policy, and authorization filtering per result.

For hidden or unauthorized resources, `resolve-*` SHOULD return an indistinguishable `not_found`.

## 7. Blob API

### 7.1 Upload

```text
POST /api/v1/blob/upload
```

Content type MAY be `application/octet-stream` or `multipart/form-data`.

Response example (not a complete schema):

```json
{
  "blob_ref": "cx:blob:sha256:e3b0...",
  "size": 102450,
  "media_type": "image/png"
}
```

### 7.2 Download

```text
HEAD /api/v1/blob/get?blob_ref=<blob_ref>
GET /api/v1/blob/get?blob_ref=<blob_ref>
```

Clients MUST re-check hash value against `blob_ref`.

## 8. Standard Error Response

```json
{
  "ok": false,
  "error": {
    "code": "cas_conflict",
    "message": "expected_state_hash mismatch",
    "retry_after_ms": 2000
  }
}
```

## 9. Standard Error Codes

| Code | HTTP Status | Meaning |
| --- | --- | --- |
| `bad_json` | 400 | JSON cannot be parsed. |
| `bad_query` | 400 | Query parameters cannot be parsed or violate schema. |
| `missing_param` | 400 | Required parameter is missing. |
| `invalid_param` | 400 | Parameter value is invalid. |
| `unauthenticated` | 401 | Authentication material is missing or cannot be verified. |
| `invalid_signature` | 401 | Signature verification failed. |
| `auth_expired` | 401 | Authentication token or grant has expired. |
| `soft_logged_out` | 401 | Token was softly logged out; client should re-authenticate while preserving local device keys. |
| `capability_denied` | 403 | Caller lacks required capability. |
| `space_frozen` | 403 | Space is frozen or archived. |
| `not_found` | 404 | Resource missing or not visible. |
| `unrecognized_endpoint` | 404 | Path under a protocol namespace is not declared or implemented. |
| `method_not_allowed` | 405 | Known path does not support the HTTP method. |
| `cas_conflict` | 409 | `expected_state_hash` mismatch. |
| `epoch_mismatch` | 409 | MLS epoch is stale. |
| `duplicate_conflict` | 409 | Same idempotency key maps to different canonical request body. |
| `stale_frontier` | 409 / 503 | Local sync or auth frontier has not reached the requested point. |
| `quota_exceeded` | 413 | Quota exceeded. |
| `payload_too_large` | 413 | Request body or blob exceeds limits. |
| `temporarily_unavailable` | 503 | Service is temporarily unavailable. |
| `rate_limited` | 429 | Request rate exceeded. |
| `timeout` | 408 / 504 | Sync frontier wait, long-poll, or upstream request timed out. |
| `sync_token_expired` | 400 / 410 | Client sync token expired; fall back to initial sync. |
| `unknown_did` | 422 | DID resolution failed. |
| `schema_violation` | 422 | Payload does not match schema. |
| `unsupported_feature` | 501 | Service does not support the requested feature. |
| `internal_error` | 500 | Internal node error. |

Clients receiving `429` MUST prefer the `Retry-After` header and fall back to body `retry_after_ms` only when the header is absent. `503` responses with `Retry-After` must be handled the same way. Clients receiving `409` SHOULD retry after backing off and fetching latest state.

## 10. Security and Abuse Defense

Services SHOULD use identical failure semantics for high-risk paths:

- Directory lookup, join probing, and public metadata endpoints SHOULD NOT return distinguishable information between `not_found` and `forbidden`.
- Federation and policy-check edges SHOULD log source service DID and source domain hash, then apply `rate_limited` / `temporarily_unavailable` controls.
- Requests with missing/invalid signatures SHOULD be rejected with audit trails while preserving normal service availability for authenticated principals.
- Requests carrying authentication material in URLs SHOULD be rejected with redacted logs and must not enter normal authentication fallback.

