# Service Surface And Bootstrap Draft

## 1. Goal

If the spec has only object models, sync principles, and capabilities but no minimal wire-level service surface, real interoperability is still weak.

Contrix therefore needs an initial definition for:

- how identity registries accept DID operations and receipts
- how repos publish and serve commits / operations
- how Principal Servers expose space sync streams and backfill
- how indexes serve queries and materialize inbox / notifications
- how blob services upload and verify content
- how invites / grants participate in first-time space join

This document defines a **minimum interoperable service surface**.  
Implementations do not have to use HTTP specifically, but they MUST provide semantically equivalent interfaces.

This file explains service semantics by role. Field-level request / response schemas, authentication modes, access restrictions, and idempotency rules for REST endpoints are canonical in [service-http-binding.md](service-http-binding.md#24-field-level-schema-index); JSON snippets or field lists in this file are illustrative and are not complete schemas.

## 2. Core Principles

### 2.1 DID Documents Are for Discovery, Not Bulk State

DID Documents SHOULD be used to:

- declare principal server, identity-registry, repo, sync service, index, blob, and capability endpoints
- declare service DIDs or service endpoints

They should not directly carry:

- full current grant state
- space current state
- large inbox or notification payloads

### 2.2 No Single Service Is the Sole Truth Source

- the repo is the actor publication truth source
- the sync service is the controlled synchronization surface of a Principal Server
- the index is the query/materialization layer
- the blob service is the content layer

Clients should be able to cross-check frontier, hashes, and reducer profiles across those layers.

### 2.3 Interfaces Must Support Idempotent Retries

Network retries, offline replay, and synchronization across multiple Principal Servers are normal in decentralized systems.

Write interfaces therefore MUST support:

- idempotent `commit_id`
- idempotent `operation_id`
- repeated submission without repeated effect

### 2.4 Services Must Publish Compatibility Profiles

Each service SHOULD publish:

- `protocol_version`
- `supported_features`
- `supported_reducer_profiles`
- `supported_schema_profiles`

Without that, clients cannot safely decide whether to use the service.

### 2.5 Concrete Servers And Service Surface Composition

In deployment, a "server" is a combination of one or more service surfaces; it is not automatically a protocol truth source. Implementations may merge servers, but `server/describe` must still declare `service_type`, `supported_operations`, authentication methods, limits, and profiles.

Common combinations:

| Concrete server | Required / optional | Typical REST namespaces | Main capability |
| --- | --- | --- | --- |
| Principal Server | Required; every principal or organization needs at least one controlled entry point | `/server`, `/sync`, `/federation`, and optionally delegated `/repo`, `/index`, `/blob`, `/authz`, `/device_messages`, `/keys` | Controlled user/org entry point, client sync, federation transactions, discovery aggregation, plaintext visibility enforcement. |
| Identity Registry / Resolver | Required; may use multiple registries / witnesses | `/identity`, `/server` | DID Documents, DID logs, handle bindings, receipts, witnesses, service endpoint discovery. |
| Auth / Account Server | Usually required for hosted services; may be embedded in self-hosting | Exposed through `auth_metadata`; login paths may be deployment-specific | Login, passkeys/OIDC/SSO, session grants, device pairing, account recovery; does not replace DID control. |
| Repo Server | Required; local or remote | `/repo`, `/server` | Commit submission, Operation / commit reads, repo sync, audit replay, hash-chain verification. |
| Sync / Federation Server | Required; usually part of the Principal Server | `/sync`, `/federation`, `/server` | Client sync, subscriptions, backfill, snapshot heads, cross-domain transactions, replay and destination-binding checks. |
| Index / AppView Server | Strongly recommended; some capability may be local-client only | `/index`, `/server` | Current state, query, search, inbox, notification, View projection, embedding/vector index. |
| Directory Server | Optional, common for public or organization deployments | `/directory`, `/server` | Authorized search and resolution for Spaces, Organizations, Actors, handles, and Applets. |
| Blob / Media Server | Required for attachments and snapshot chunks | `/blob`, `/server` | Blob upload, authenticated download, HEAD, Range, thumbnails, previews, retention, media safety. |
| Device / Key Server | Required for E2EE profiles | `/device_messages`, `/keys`, `/server` | To-device messages, one-time keys, fallback keys, device lists, key-backup metadata. |
| Authz / Policy Server | Recommended as a separate service for shared Spaces and organization governance | `/authz`, `/contrix/v1/check`, `/server` | Effective grants, invite queries, capability precheck, signed policy decisions, risk / quarantine. |
| Push Gateway | Optional for mobile/desktop notifications | `/push`, `/server` | Push device registration, unregister, blind notification delivery, APNs/FCM/vendor adapters. |
| Applet Server | Optional for integrations, bridges, and automations | `/applet`, `/server` | Applet describe, transactions, ghost actors, portal Spaces, third-party lookup. |
| Agent Runtime Server | Optional but recommended for agent workloads | Service surfaces defined by `extensions/agent-*`, usually writing results through `/repo` | Agent execution, tool calls, run logs, memory, A2A/ACP/MCP handoff. |
| Realtime Media Server | Optional for calls and meetings | `/contrix/v1/ice-config`, plus WebRTC signaling / TURN / SFU profiles | ICE config, TURN/STUN, SFU/MCU, recording policy, short-lived media credentials. |
| Moderation / Compliance Server | Recommended as a separate service for public or organization deployments | `/moderation`, `/server` | Reports, review queues, server ACLs, policy lists, appeals, legal hold / erasure workflows. |

Recommended deployment profiles:

- `personal_node`: Principal Server + Repo + Sync/Federation + Blob + Device/Key + Authz, with optional local Index.
- `organization_workserver`: Principal Server + Repo + Sync/Federation + Index + Directory + Blob + Device/Key + Authz + Push.
- `public_federation_ingress`: restricted Principal/Federation + Policy + Moderation + Directory; plaintext is not visible by default.
- `applet_bridge`: Applet Server + Repo writer + Authz precheck, limited to authorized namespace and capability.
- `agent_runtime`: Agent Runtime + Repo writer + Memory/Index integration; all durable writes are signed by principal / agent DID.

Clients MUST resolve DID Documents and Space policy first, then verify `server/describe`. Sharing a domain name does not imply shared authority or the same plaintext visibility scope.

## 3. Common Service Description Endpoint

Every service is recommended to provide:

```text
GET /api/v1/server/describe
```

Example:

```json
{
  "service_did": "did:web:alice.example.net",
  "service_type": "principal_server",
  "protocol_version": "0.2-draft",
  "supported_features": [
    "sync_stream",
    "snapshot",
    "notification-index"
  ],
  "supported_reducer_profiles": [
    "cx.reducer.v1"
  ],
  "supported_schema_profiles": [
    "cx.schema.v1"
  ],
  "auth_metadata": {
    "oauth_issuer": "https://auth.example.com",
    "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
    "supported_auth_methods": ["passkey", "oidc", "device_pairing"],
    "did_binding_methods": ["session_grant", "did_http_signature"]
  },
  "max_body_bytes": 1048576
}
```

Service type naming rules:

- DID Document `service.type` uses protocol registered names such as `ContrixPrincipalServer`, `ContrixRepo`, and `ContrixIndex`.
- `describe` responses use lower-case runtime `service_type` values such as `principal_server`, `repo_node`, `sync_node`, `index_node`, `appview_node`, `identity_registry`, `auth_server`, `blob_node`, `directory_service`, `device_key_service`, `authz_service`, `policy_server`, `push_gateway`, `applet_service`, `agent_runtime`, `media_service`, `sfu_service`, `turn_service`, and `moderation_service`.
- Conformance profiles use `cx.profile.*` ids such as `cx.profile.principal_server.v1`.
- Implementations MUST keep these three naming layers distinct.

### 3.1 Identity Registry Surface

Identity registries should expose at least the following semantics:

#### 3.1.1 Describe the Registry

```text
GET /api/v1/identity/describe
```

It should return:

- `service_did`
- `registry_mode = writer | witness | replica`
- supported receipt types
- current software version and compatibility profile

#### 3.1.2 Fetch the Current DID Document

```text
GET /api/v1/identity/document?did=<did>
```

The response SHOULD contain:

- the current materialized DID Document
- the current `head_event_hash`
- the current `seq`
- optional witness receipts

#### 3.1.3 Fetch the DID Log

```text
GET /api/v1/identity/log?did=<did>&cursor=<cursor>&limit=<n>
```

Used for:

- audit
- reconstructing the DID Document
- checking that `key_log` matches the registry head

#### 3.1.4 Submit a DID Update

```text
POST /api/v1/identity/submit-did-operation
```

The request body SHOULD contain:

- `did`
- `seq`
- `prev_event_hash`
- `patch`
- `proofs`

Requirements:

- replaying the same `did + seq` with identical content MUST be idempotently accepted
- reusing the same `did + seq` with different content MUST be rejected
- the registry MUST validate the authorization chain back to `inception_key`

#### 3.1.5 Fetch Receipt / Witness Proofs

```text
GET /api/v1/identity/receipts?did=<did>&head=<event-hash>
```

#### 3.1.6 Recommended Write Confirmation

The initial recommendation is:

- writer clients submit the `did_operation` to multiple registries / witnesses
- at least `k-of-n` receipts are required before the update is considered committed
- reads may attach `expected_head` or `min_seq`

That keeps DID writes in the world of ordinary network requests rather than global block consensus.

## 4. Repo Surface

Repos should expose at least the following semantics:

### 4.1 Describe the Repo

```text
GET /api/v1/repo/describe
```

It should return:

- `repo_did`
- current head commit
- supported signature algorithms
- whether batch operation fetch is supported

### 4.2 List Commits

```text
GET /api/v1/repo/commits?cursor=<cursor>&limit=<n>
```

Used for:

- actor-history recovery
- audit replay
- filling missing commits

### 4.3 Get One Commit

```text
GET /api/v1/repo/commit?commit_id=<id>
```

### 4.4 Batch-fetch Operations

```text
POST /api/v1/repo/operations
```

The request body may carry a set of `operation_id` values.

### 4.5 Submit a Commit

```text
POST /api/v1/repo/submit-commit
```

Requirements:

- re-submitting the exact same bytes for the same `commit_id` MUST be idempotently accepted
- reusing the same `commit_id` with different bytes MUST be rejected
- the repo SHOULD return the new head, the accepted operation list, and causal sync tokens for read-your-writes queries

## 5. Sync Surface

The sync surface is the space incremental sync capability exposed by a Principal Server. It is not an independent third-party server role. Clients should use only the current principal's controlled/delegated Principal Server, the peer principal's controlled/delegated Principal Server, or a shared Space Host explicitly listed by Space policy.

This section defines three distinct operations:

- `POST /api/v1/sync`: client aggregate incremental sync, defined in `client-sync.md`.
- `GET /api/v1/sync/subscribe`: Space operation stream subscription.
- `GET /api/v1/sync/backfill`: cursor-based historical backfill.

Implementations MUST NOT collapse these into a single ambiguous stream operation. Other transports MAY use different frame names, but they must map to the canonical operations above.

### 5.1 Describe the Sync Service

```text
GET /api/v1/sync/describe
```

### 5.2 Space Sync Stream Subscription

```text
GET /api/v1/sync/subscribe?space_id=<id>&cursor=<cursor>
```

Implementations may use:

- SSE
- WebSocket
- long polling

but they must provide stable cursor semantics.

### 5.3 Incremental Backfill

```text
GET /api/v1/sync/backfill?space_id=<id>&cursor=<cursor>&limit=<n>
```

### 5.4 Snapshot Head

```text
GET /api/v1/sync/snapshot-head?space_id=<id>
```

Used to fetch the currently recommended snapshot manifest.

### 5.5 Plaintext and Service Trust

If a Space does not use E2EE or content-layer encryption:

- clients MUST NOT submit message bodies, comment bodies, plaintext attachments, sensitive memory bodies, or reversible derived summaries to unauthorized third-party services
- `repo/submit-commit`, `sync`, `sync/subscribe`, and `sync/backfill` must target a Principal Server delegated by the principal DID, Organization DID, or Space policy
- Index, AppView, Directory, Push Gateway, Blob preview, and Policy preview services that receive body text, body summaries, attachment previews, full-text indexes, or reversible derived content MUST be declared in Space policy as `plaintext_visible_services`
- shared Space Hosts that can see plaintext must be declared as plaintext-visible services in Space policy
- recipient Principal Servers can see non-encrypted content delivered to their recipients; clients and Space policy MUST treat them as content visibility boundaries
- untrusted services may receive only public content, encrypted envelopes, or opaque payloads

## 6. Index Surface

Indexes should expose at least the following semantics:

### 6.1 Describe the Index

```text
GET /api/v1/index/describe
```

### 6.2 Fetch Current Object State

```text
GET /api/v1/index/entity?entity_id=<id>
```

### 6.3 Structured Query

```text
POST /api/v1/index/query
```

The request body SHOULD accept:

- `kind`
- filters
- ordering
- cursor
- limit

### 6.4 Thread / Topic Query

```text
GET /api/v1/index/thread?topic_id=<id>&cursor=<cursor>
```

### 6.5 Inbox / Notification Query

```text
GET /api/v1/index/notifications?cursor=<cursor>&state=unread
```

```text
GET /api/v1/index/inbox?scope=<scope>&cursor=<cursor>
```

### 6.6 Full-Text Search

```text
POST /api/v1/index/search
```

### 6.7 Plaintext Index Boundary

Index / AppView services are derived layers, not truth sources, but they can hold highly searchable plaintext projections. Therefore:

- full-text search, embeddings, notification summaries, inbox previews, and report projections for non-E2EE private Spaces may only be generated or stored by services listed in `plaintext_visible_services`
- indexes not listed in `plaintext_visible_services` MUST receive only public content, encrypted envelopes, irreversible hashes, minimum routing metadata, or policy-allowed stripped previews
- clients MUST verify service DID, `service_type`, supported profile, Space policy delegation, and plaintext-visible declaration before selecting an Index
- Index output MUST NOT expand visibility; query results, notifications, search hits, and previews remain constrained by the underlying Space policy and capability rules

## 7. Blob Surface

Blob services should expose at least:

### 7.1 Upload a Blob

```text
POST /api/v1/blob/upload
```

Returning:

- `blob_ref`
- `sha256`
- `size`

### 7.2 Inspect Blob Headers

```text
HEAD /api/v1/blob/get?blob_ref=<ref>
```

### 7.3 Download a Blob

```text
GET /api/v1/blob/get?blob_ref=<ref>
```

Blob validation MUST be content-hash based rather than URL based.

## 8. Capability / Invite Surface

Even though grant / revoke / invite are themselves objects or operations, the service layer still needs query surfaces.

At minimum, the following are recommended:

```text
GET /api/v1/authz/effective-grants?space_id=<id>&subject=<did>
```

```text
GET /api/v1/authz/invites?space_id=<id>&subject=<did-or-handle>
```

```text
POST /api/v1/authz/check
```

The `check` surface is useful for:

- repo-side prechecks before accepting writes
- fast filtering before sync distribution
- local UX warnings before a client sends a write

## 9. Space Bootstrap Flow

The recommended first-time join flow is:

1. the user enters a handle, DID, or space link
2. the client resolves the DID and completes handle bidirectional verification
3. the client discovers Principal Server / identity registry / repo / sync / index / blob / authz services from DID Documents and Space policy
4. the client fetches invite / grant views relevant to the principal
5. the client fetches space metadata and the snapshot head
6. the client downloads the snapshot manifest and chunks
7. the client fetches backfill / sync-stream increments after the frontier
8. the client runs the reducer locally
9. the client establishes personal state such as read markers and notification cursors

## 10. Freshness and Multi-service Coexistence

When multiple Principal Servers or indexes coexist, services SHOULD expose:

- current frontier
- snapshot frontier
- reducer profile
- last materialization time

Clients MAY compare these values to decide:

- which service is fresher
- whether they need to fall back to repo replay
- whether an index is merely behind versus actually inconsistent

For identity registries, services SHOULD also expose:

- the current DID head
- `seq`
- a receipt-set summary

Clients may use those values to decide whether a registry is:

- serving the freshest head
- merely a lagging replica
- or potentially forked / malicious

## 11. Transport Security and Ciphertext

The service surface SHOULD distinguish:

- metadata needed for routing
- optional end-to-end encrypted content

If a payload is already encrypted under `policy.encryption_profile`, then:

- repos / sync services / indexes MAY be unable to decrypt the body
- but they SHOULD still preserve hash, cursor, causality, and target references

## 12. Initial Design Decisions

The current draft recommends fixing:

- a minimum principal server / identity-registry / repo / sync / index / blob / authz service surface
- HTTP/JSON paths as the default reference binding while preserving transport-equivalent semantics
- idempotent write interfaces
- DID writes confirmed by multi-registry / witness receipts rather than blockchains
- bootstrap covering invite / grant / snapshot / backfill
- services publishing reducer / schema / feature profiles

## 13. Further Work

The next round still needs:

- formal request/response schemas for each endpoint
- cursor encoding
- sync-stream frame format
- error codes and retry semantics
- auth-token or signed-request formats
- identity receipt / witness proof schemas


