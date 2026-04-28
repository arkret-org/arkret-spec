# Spec Map

## 1. Objective

This is the protocol reading entrypoint for the English draft. It is organized by protocol planes to prevent getting lost in a long list of standalone files.

If this map conflicts with any specific document, the normative rules in that document take precedence.

## 2. Recommended Reading Order

When learning the protocol for the first time, we recommend this sequence:

1. `overview/architecture.md`: understand layer responsibilities, concrete server roles, and trust boundaries.
2. `overview/glossary.md`: clarify terms, especially Principal / Actor / Organization / Space / Principal Server / Repo.
3. `models/object-model-core.md` and `models/object-model-standard.md`: understand the collaboration graph and standard object types.
4. `identity/identity-did.md`, `identity/identity-handles.md`, `identity/progressive-disclosure.md`: understand identity, handle, and privacy disclosure.
5. `authz/capabilities.md` and `authz/event-auth-state-resolution.md`: understand permissions and Space state transitions.
6. `sync/operations-sync.md`, `sync/client-sync.md`, `sync/service-surface.md`: understand write, sync, and service surfaces.
7. Read extensions by use case: Applet, Agent, WebRTC, Social, Directory, Moderation, Federation, Sovereign Deployment.

## 3. Core Boundary Model

### 3.1 Principal / Actor / Organization

- Principal is the identity root, usually represented by a DID.
- Actor is the Principal view inside a Space or collaboration graph.
- Organization is a Principal that provides governance, issuance, service delegation, and official endorsement.
- Organization is not the Space; Space is the collaboration boundary.

### 3.2 Space / Feed / View

- Space is the boundary for replication, authorization, schema, policy, membership, history visibility, and E2EE.
- Feed is an observable social/activity projection, not a replacement for Space.
- View is a projection definition and does not hold truth data.

### 3.3 Principal Server / Repo / Sync / Index

- Repo is a verifiable append-only publication log, not a server.
- Principal Server provides `/repo/*` APIs for accessing or hosting repos.
- Principal Server is the controlled or delegated service boundary; Sync Service is its Space sync capability.
- Index is the query/materialization layer, not the source of truth.

### 3.4 Discoverability / Join Rule / History Visibility

- Discoverability controls whether a resource can be found.
- Join Rule controls how a member can join.
- History Visibility determines how much historical data can be seen after joining.
- These must be evaluated independently.

### 3.5 Capability / Moderation / Personal Blocklist

- Capability defines base action permissions.
- Moderation Policy can deny, quarantine, or require review; it does not grant permissions.
- Personal blocklists are user-local and only shape local client experience.

### 3.6 Public Feed / Circle Feed

- Public Feed is suitable for open indexing, following, and broadcasting.
- Circle Feed must use Audience Policy, recipient snapshots, and optional E2EE.
- A “post then hide” approach is not a valid privacy mechanism.

## 4. Document Groups

### 4.1 Overview and Decisions

| Document | Purpose |
| --- | --- |
| `README.md` | Project positioning, goals, and entry points. |
| `spec-map.md` | This document. |
| `overview/architecture.md` | Top-level architecture, Principal Server deployment profiles, deployment topology, and trust boundaries. |
| `overview/matrix-core-differences.md` | Core differences and tradeoffs compared with Matrix. |
| `overview/design-questions.md` | Key open design questions and decision records. |
| `overview/gap-analysis.md` | Current implementation gaps and priority. |
| `overview/glossary.md` | Global terminology. |

### 4.2 Identity, Organization, and Privacy

| Document | Purpose |
| --- | --- |
| `identity/identity-did.md` | DID, `did:uuid`, DID Document, key log, and organization ownership. |
| `identity/identity-handles.md` | Handle resolution, bidirectional binding, claim / attestation model. |
| `identity/progressive-disclosure.md` | Progressive disclosure, presentation requests, disclosure policy, private storage. |
| `identity/tsp-integration.md` | TSP as optional trust transport binding. |
| `identity/key-management.md` | Keys, recovery, and Accountable Actor. |

### 4.3 Object Model and Interaction

| Document | Purpose |
| --- | --- |
| `models/object-model-core.md` | Core objects: Space, Actor, Entity, Relation, Event, View. |
| `models/object-model-standard.md` | Standard types: Task, Message, Run, Memory, Social Post, etc. |
| `models/data-structures.md` | Object field-level definitions: requiredness, types, enums, constraints. |
| `models/conversation-model.md` | Channel, Topic, Message, Thread, Mention, Reaction. |
| `models/views.md` | Board, Table, Timeline, Graph projections. |
| `models/content-types.md` | Rich text, media, poll, and content block typing. |
| `models/social-graph.md` | Social feed, circle, contact/follow, and audience policy. |

### 4.4 Authorization, Governance, and State

| Document | Purpose |
| --- | --- |
| `authz/capabilities.md` | Capability, delegation, revocation, and claim conditions. |
| `authz/grant-constraint-schema.md` | Grant constraint schema. |
| `authz/event-auth-state-resolution.md` | Space versioning, auth refs, membership, state resolution. |
| `authz/policy-server.md` | Policy Server risk gating and signed decisions. |
| `authz/moderation.md` | Reporting, Space/Organization moderation policy, and personal filtering endpoints. |
| `security/server-threat-model.md` | Server-side abuse and anti-abuse patterns. |
| `authz/account-lifecycle.md` | Lock, disable, erase, and session revocation. |

### 4.5 Sync, Service, and Federation

| Document | Purpose |
| --- | --- |
| `sync/operations-sync.md` | Repo-first publication, operations, snapshots, and conflict resolution. |
| `sync/client-sync.md` | Client incremental sync, timeline, state_after, to_device behavior. |
| `sync/service-surface.md` | Minimal service surface and concrete service composition: principal server, identity, repo, sync, index, directory, blob, authz, device/key, push, applet, agent, media, moderation. |
| `sync/service-http-binding.md` | HTTP/JSON binding entrypoints, request/response, standard errors. |
| `sync/service-api-schema.md` | Core request/response schema. |
| `sync/api-conventions.md` | Error handling, pagination, idempotency, feature discovery. |
| `sync/transport-bindings.md` | Non-HTTP transport binding profiles and semantic mapping requirements. |
| `sync/federation.md` | Federation model across service domains. |
| `sync/federation-wire.md` | Federation transaction and wire format. |
| `sync/sovereign-deployment.md` | High-assurance sovereign networks, controlled external collaboration, revoke/import/export workflows. |

### 4.6 Discovery, Directory, and User State

| Document | Purpose |
| --- | --- |
| `discovery/discovery-directory.md` | Space / Organization / Actor / Applet discoverability and directory services. |
| `discovery/profiles-presence.md` | Actor profiles, presence, typing, and directory visibility. |
| `discovery/client-preferences.md` | Account metadata, private labels, notification preferences, personal blocklist. |
| `discovery/push-notifications.md` | Push rules, push gateway, and E2EE redaction. |
| `discovery/read-receipts.md` | Read receipts and read markers. |
| `discovery/read-notification-schema.md` | Read and notification schema. |

### 4.7 Crypto, Device, and Media

| Document | Purpose |
| --- | --- |
| `crypto-media/device-crypto-verification.md` | Device identity, cross-signing, to-device flow, secret storage, key backup. |
| `crypto-media/devices-and-auth.md` | Multi-device, login, authentication, SSO. |
| `crypto-media/encryption-and-audit.md` | MLS E2EE and auditability. |
| `crypto-media/media-and-blob.md` | Blob metadata, thumbnails, authenticated media. |
| `crypto-media/webrtc-signaling.md` | Voice/video signaling, meeting support, TURN/STUN/ICE, SFU/MCU. |

### 4.8 Extensions and Integration

| Document | Purpose |
| --- | --- |
| `extensions/applet-integration.md` | Applet integration, bridge, bot, ghost actor, portal Space. |
| `extensions/applet-schema.md` | Applet schema and OpenAPI draft. |
| `extensions/agent-memory.md` | Agent memory, run lifecycle, promotion and review. |
| `extensions/agent-protocol-interop.md` | A2A / ACP legacy / external agent protocol handoff. |
| `sync/third-party-invites.md` | 3PID invites and claim flow. |
| `models/space-hierarchy.md` | Space parent/child, inheritance, lazy links, cycle handling. |

### 4.9 Conformance, Encoding, and Validation

| Document | Purpose |
| --- | --- |
| `conformance/encoding.md` | Canonical JSON, IDs, hashes, signatures, cursor, HLC, rank. |
| `conformance/encoding-conformance-vectors.md` | Consistency vectors for canonical JSON, hashes, signatures, HLC, cursor. |
| `conformance/schema-registry.md` | Standard schema and event type registry. |
| `conformance/state-resolution-conformance-vectors.md` | Concurrency and state-resolution vectors for membership/capability/governance. |
| `conformance/redaction-conformance-vectors.md` | Redaction constraints and visibility vectors. |
| `conformance/capability-conformance-vectors.md` | Delegated capability, revoke rollback, and approval constraints. |
| `conformance/query-schema.md` | Index / View / Inbox query syntax. |
| `conformance/snapshot-schema.md` | Snapshot manifest, chunking, signatures, encrypted envelopes. |
| `conformance/conformance-suite.md` | Interoperability suite structure and vector prioritization. |
| `conformance/conformance-profiles.md` | Implementation profiles and conformance scope. |
| `conformance/sync-conformance-vectors.md` | Client sync, pagination, snapshot, and MLS epoch backfill vectors. |

## 5. Split Principles

New content should continue to follow these rules:

- If it changes identity, DID, handles, or claims, place it in Identity.
- If it changes shared-state validity, place it in Authorization/Governance.
- If it changes service API or transport behavior, place it in Sync/Service/Federation.
- New business capabilities should be extension profiles first (social, agent, applet, webrtc).
- Do not model deployment roles as identity subjects; do not present UI projections as sources of truth.
