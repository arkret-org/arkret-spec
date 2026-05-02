# Contrix Protocol

> Status: this English draft is stale after the 2026-05 object model refactor.
> Use `../zh/` and `../artifacts/` as the current normative protocol text until the English translation is regenerated.

## 1. Positioning

`contrix-spec` is the **Contrix v1 decentralized collaboration protocol**. Contrix uses:

- **DID principals** as the identity root
- **Space / Subject / Room / Board / List / Card / Message / Morph / Relation collaboration graphs** as the data root
- **signed Event + per-actor event chains** as the audit root
- **capabilities** as the authorization root
- **views/projections** as the human presentation root
- **Events** as the collaboration fact root
- **Subject, Room, Board, List, Card, and Message** as standard collaboration semantics, with **Morph + schema/profile-declared facets** for open extension objects

Its goal is not to wrap a chat protocol in a Kanban shell. Its goal is to define one protocol that can project into boards, Room conversations, Subject-centered work surfaces, tables, calendars, trees, graphs, Gantt views, and agent memory.

## 2. Design Goals

Contrix v1 focuses on:

1. Stable identity  
   All principals use DIDs as stable identifiers, while handles remain portable human-readable entry points.
2. Object-centric collaboration  
   The protocol root is Space, Actor, Subject, Room, Board, List, Card, Message, Morph, Relation, Event, and View. Subject is the semantic center; Card, Room, Document, Run, and Memory are collaboration surfaces around it.
3. Decentralized synchronization  
   The source of truth is signed operations and repo commits, not a single central database.
4. Multiple interaction modes  
   The same protocol supports Kanban, list, table, calendar, Gantt, chat, thread, forum, tree, graph, and similar modes.
5. Human-friendly presentation  
   Data must naturally project into boards, timelines, Subject activity, topic surfaces, message streams, and review queues.
6. AI-friendly participation  
   The protocol natively supports agent principals, delegation, run logs, and memory extraction.
7. Audit and recovery  
   Edits, recalls, authorization changes, and conflict resolution must remain explainable and auditable.

## 3. Non-goals

The following are explicitly out of scope for the base interoperability profile:

- making chat messages the only data root again
- using room state machines as the universal substrate
- global consensus chains
- hard-coupling the spec to a specific SaaS UI
- treating embeddings or vector stores as the protocol source of truth
- implementing extremely complex field-level or byte-range ACLs from day one

## 4. Spec Map

This directory is structurally aligned with the Chinese v1 specification. The Chinese version is the leading normative text where an English file is still abbreviated.

Main document groups:

`architecture.md` now defines Principal Server deployment profiles, and `service-surface.md` maps Principal Server capabilities to service namespaces and deployment profiles.

- [gap-analysis.md](./overview/gap-analysis.md)
- [design-questions.md](./overview/design-questions.md)
- [architecture.md](./overview/architecture.md)
- [matrix-core-differences.md](./overview/matrix-core-differences.md)
- [identity-did.md](./identity/identity-did.md)
- [identity-handles.md](./identity/identity-handles.md)
- [key-management.md](./identity/key-management.md)
- [object-model-core.md](./models/object-model-core.md)
- [object-model-standard.md](./models/object-model-standard.md)
- [data-structures.md](./models/data-structures.md)
- [conversation-model.md](./models/conversation-model.md)
- [operations-sync.md](./sync/operations-sync.md)
- [capabilities.md](./authz/capabilities.md)
- [views.md](./models/views.md)
- [agent-memory.md](./extensions/agent-memory.md)
- [service-surface.md](./sync/service-surface.md)
- [service-http-binding.md](./sync/service-http-binding.md)
- [api-conventions.md](./sync/api-conventions.md)
- [transport-bindings.md](./sync/transport-bindings.md)
- [discovery-directory.md](./discovery/discovery-directory.md)
- [conformance-profiles.md](./conformance/conformance-profiles.md)
- [conformance-suite.md](./conformance/conformance-suite.md)
- [query-schema.md](./conformance/query-schema.md)
- [grant-constraint-schema.md](./authz/grant-constraint-schema.md)
- [encoding.md](./conformance/encoding.md)
- [encoding-conformance-vectors.md](./conformance/encoding-conformance-vectors.md)
- [snapshot-schema.md](./conformance/snapshot-schema.md)
- [service-api-schema.md](./sync/service-api-schema.md)
- [read-notification-schema.md](./discovery/read-notification-schema.md)
- [schema-registry.md](./conformance/schema-registry.md)
- [media-and-blob.md](./crypto-media/media-and-blob.md)
- [webrtc-signaling.md](./crypto-media/webrtc-signaling.md)
- [state-resolution-conformance-vectors.md](./conformance/state-resolution-conformance-vectors.md)
- [redaction-conformance-vectors.md](./conformance/redaction-conformance-vectors.md)
- [capability-conformance-vectors.md](./conformance/capability-conformance-vectors.md)
- [federation-wire.md](./sync/federation-wire.md)
- [sovereign-deployment.md](./sync/sovereign-deployment.md)
- [applet-integration.md](./extensions/applet-integration.md)
- [applet-schema.md](./extensions/applet-schema.md)
- [encryption-and-audit.md](./crypto-media/encryption-and-audit.md)
- [devices-and-auth.md](./crypto-media/devices-and-auth.md)
- [content-types.md](./models/content-types.md)
- [federation.md](./sync/federation.md)
- [push-notifications.md](./discovery/push-notifications.md)
- [moderation.md](./authz/moderation.md)
- [profiles-presence.md](./discovery/profiles-presence.md)
- [read-receipts.md](./discovery/read-receipts.md)
- [third-party-invites.md](./sync/third-party-invites.md)
- [client-preferences.md](./discovery/client-preferences.md)
- [event-auth-state-resolution.md](./authz/event-auth-state-resolution.md)
- [device-crypto-verification.md](./crypto-media/device-crypto-verification.md)
- [client-sync.md](./sync/client-sync.md)
- [sync-conformance-vectors.md](./conformance/sync-conformance-vectors.md)
- [policy-server.md](./authz/policy-server.md)
- [account-lifecycle.md](./authz/account-lifecycle.md)
- [glossary.md](./overview/glossary.md)
- [space-hierarchy.md](./models/space-hierarchy.md)
- [agent-protocol-interop.md](./extensions/agent-protocol-interop.md)
- [mimi-interop.md](./extensions/mimi-interop.md)
- [tsp-integration.md](./identity/tsp-integration.md)
- [progressive-disclosure.md](./identity/progressive-disclosure.md)


## 5. Core Design Decisions

### 5.1 Identity

- `principal_id = DID URI`
- handles are strictly separated from DIDs
- the default DID method is `did:uuid`
- `did:uuid` is based on a custom UUID v8: 44-bit millisecond timestamp + 4-bit hash algorithm id + 74-bit inception-key hash fragment
- DID hash filling and validation MUST use big-endian ordering
- ordinary key rotation MUST NOT change the DID
- current control keys are inherited from `inception_key` through `key_log` and do not need to directly equal the DID fragment
- DID documents are stored and replicated through multiple identity registry / witness / replica nodes rather than one central directory
- handle resolution follows an atprotocol-inspired bidirectional model, adapted for collaboration and multi-service discovery
- version one SHOULD support `did:web` for org/service interoperability
- external DID methods such as `did:plc` and `did:web` use a `method adapter + normalized principal view + sidecar` compatibility layer; raw documents and history are preserved instead of being rewritten into fake `did:uuid` documents

### 5.2 Data

- each principal owns its own repo
- shared state is reduced from the authorized Event / operation set
- `space` is the replication, authorization, schema, and policy boundary
- `subject` is the thin semantic center for the thing being discussed, advanced, referenced, or remembered
- `room`, `board`, `list`, `card`, and `message` are first-class standard objects
- `morph` is the open extension object carrier
- `relation` is first-class and represents containment, dependency, replies, references, assignments, mentions, and similar links
- `event` is the collaboration fact and audit root
- `view` is a projection and does not own core data
- Card and Room are surfaces that may be grouped through `subject --has_surface--> surface`; surface links do not grant capabilities by themselves
- `schema/policy` are formal objects rather than unresolved references
- `invite/read_marker/notification` complete the join/read/attention path for human collaboration

### 5.3 Boards and Conversation

- boards are modeled with standard Board/List/Card objects and View projections
- chat is modeled with Room/Message; a Room can be a Subject discussion surface
- topic mode is modeled as `subject_kind="topic"` plus Card, Room, Document, Run, or Memory surfaces
- the same Subject may have multiple discussion, status, document, run, and memory surfaces through Relations
- `@user` and `@object` may be authored as text in the UI, but must be stored as structured Actor/Object references and `mentions` Relations

### 5.4 Sync

- repo commits are the actor-side publication unit
- operation logs are the audit truth source
- Principal Servers / Sync Services are the controlled sync/subscription layer, not the sole truth source
- search, inbox, notifications, and View projection are client-local derived layers by default, not sole truth sources
- the service layer requires a minimum interoperable principal-server / identity-registry / repo / sync / blob / authz surface
- board/chat/topic/tree/graph are sync profiles and View projections, not separate protocols
- commit/operation submission must be idempotent by design
- authorization validity must converge under the same reducer ordering
- recall converges through redaction semantics, not guaranteed global erasure
- sync services / indexes may forward encrypted payloads without decrypting them; plaintext private content must not be submitted to undelegated third-party services
- the DID fragment anchors `inception_key`; ordinary key rotation keeps the same DID, while exceptional identity reboot is reserved for unrecoverable cases

### 5.5 Authorization

- authorization uses a capability model
- delegation must be explicit, verifiable, and revocable
- agents must operate under narrow, time-bounded, auditable grants
- accountable Actors such as agents, minors, and managed accounts must trace to responsible / guardian / controller parties
- accountability is not capability; permissions must still be explicitly granted
- high-risk actions support approval constraints and proposal mode
- authorization subjects use DIDs or condition selectors; handles are not authorization primary keys
- dynamic conditions such as organization membership, roles, and handle bindings are expressed through verifiable claims / attestations
- DID Documents are not cross-organization identity profiles; public-persona DIDs may declare handles, while pairwise/private DIDs do not publish handles by default and prove attributes through minimum-disclosure VCs / presentations
- sending messages, editing, recalling, and moderating are distinct actions

## 6. Engineering Principles

Implementations should preserve:

- JSON/HTTP friendliness without making REST the only protocol binding
- signing and audit discipline
- decentralized service discovery
- layered thinking around attachments, sync, and indexing

The protocol does not assume:

- room-first abstractions
- messages/events carrying every business object
- a single mandatory directory or control-plane as the only entry point
- reconstructing business state from chat history

## 7. Normative Language

Normative language in this directory follows RFC 2119 style keywords:

- `MUST`
- `SHOULD`
- `MAY`

`MUST`, `SHOULD`, and `MAY` are normative. Examples, explanatory background, migration notes, and sections explicitly marked non-normative do not change conformance requirements.

## 8. Deliverables in This Round

This round moves the protocol from a directional sketch to a "question inventory + unified interaction model + self-consistent framework", with emphasis on:

- a concrete protocol question inventory
- a unified abstraction for board/chat/topic
- structured `@mention` semantics
- edit / recall / redaction semantics
- board/chat/topic sync profiles
- conflict-resolution rules per object type
- a minimum service surface and Space bootstrap
- missing objects such as `schema/policy/invite/read_marker/notification`
- idempotent submission, authorization timing, and encrypted-payload forwarding semantics

## 9. One-sentence Summary

Contrix is meant to solve:

- decentralized collaborative objects
- a unified data model for boards and chat/topic interaction
- stable identity and authorization
- AI-agent writable, searchable, auditable long-term memory

It is not meant to be another renamed chat protocol.

