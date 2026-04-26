# Contrix New Protocol

## 1. Positioning

`contrix-spec-new` is a **new decentralized collaboration protocol** draft. It is not a light revision of the old `contrix-spec`.

The old `contrix-spec` still largely inherited a Matrix-like "rooms + events + messages" worldview.  
The new Contrix explicitly shifts to:

- **DID principals** as the identity root
- **Space / Entity / Relation collaboration graphs** as the data root
- **append-only repos + ops** as the audit root
- **capabilities** as the authorization root
- **views/projections** as the human presentation root
- **Events** as the collaboration fact root
- **memory/run/message/task** as standard Entity types

Its goal is not to wrap a chat protocol in a Kanban shell. Its goal is to define one protocol that can project into boards, chat/topic flows, tables, calendars, trees, graphs, Gantt views, and agent memory.

## 2. Design Goals

The first phase of Contrix New focuses on:

1. Stable identity  
   All principals use DIDs as stable identifiers, while handles remain portable human-readable entry points.
2. Object-centric collaboration  
   The protocol root is Space, Actor, Entity, Relation, Event, and View; boards, tasks, messages, memories, and runs are standard Entity types.
3. Decentralized synchronization  
   The source of truth is signed operations and repo commits, not a single central database.
4. Multiple interaction modes  
   The same protocol supports Kanban, list, table, calendar, Gantt, chat, thread, forum, tree, graph, and similar modes.
5. Human-friendly presentation  
   Data must naturally project into boards, timelines, topic streams, message streams, and review queues.
6. AI-friendly participation  
   The protocol natively supports agent principals, delegation, run logs, and memory extraction.
7. Audit and recovery  
   Edits, recalls, authorization changes, and conflict resolution must remain explainable and auditable.

## 3. Non-goals

The following are explicitly out of scope for the first version:

- making chat messages the only data root again
- using room state machines as the universal substrate
- global consensus chains
- hard-coupling the spec to a specific SaaS UI
- treating embeddings or vector stores as the protocol source of truth
- implementing extremely complex field-level or byte-range ACLs from day one

## 4. Spec Map

This directory is structurally aligned with the Chinese draft. The Chinese version currently carries the most detailed wording; the English files provide aligned headings, responsibilities, and core decisions.

Main document groups:

- [gap-analysis.md](./gap-analysis.md)
- [design-questions.md](./design-questions.md)
- [architecture.md](./architecture.md)
- [identity-did.md](./identity-did.md)
- [identity-handles.md](./identity-handles.md)
- [key-management.md](./key-management.md)
- [object-model-core.md](./object-model-core.md)
- [object-model-standard.md](./object-model-standard.md)
- [conversation-model.md](./conversation-model.md)
- [operations-sync.md](./operations-sync.md)
- [capabilities.md](./capabilities.md)
- [views.md](./views.md)
- [agent-memory.md](./agent-memory.md)
- [service-surface.md](./service-surface.md)
- [api-conventions.md](./api-conventions.md)
- [conformance-profiles.md](./conformance-profiles.md)
- [query-schema.md](./query-schema.md)
- [grant-constraint-schema.md](./grant-constraint-schema.md)
- [encoding.md](./encoding.md)
- [snapshot-schema.md](./snapshot-schema.md)
- [service-api-schema.md](./service-api-schema.md)
- [read-notification-schema.md](./read-notification-schema.md)
- [schema-registry.md](./schema-registry.md)
- [media-and-blob.md](./media-and-blob.md)
- [federation-wire.md](./federation-wire.md)
- [applet-integration.md](./applet-integration.md)
- [applet-schema.md](./applet-schema.md)
- [encryption-and-audit.md](./encryption-and-audit.md)
- [devices-and-auth.md](./devices-and-auth.md)
- [content-types.md](./content-types.md)
- [federation.md](./federation.md)
- [push-notifications.md](./push-notifications.md)
- [moderation.md](./moderation.md)
- [profiles-presence.md](./profiles-presence.md)
- [webrtc-signaling.md](./webrtc-signaling.md)
- [read-receipts.md](./read-receipts.md)
- [third-party-invites.md](./third-party-invites.md)
- [client-preferences.md](./client-preferences.md)
- [matrix-compat-gap.md](./matrix-compat-gap.md)
- [event-auth-state-resolution.md](./event-auth-state-resolution.md)
- [device-crypto-verification.md](./device-crypto-verification.md)
- [sync-v2.md](./sync-v2.md)
- [policy-server.md](./policy-server.md)
- [account-lifecycle.md](./account-lifecycle.md)
- [glossary.md](./glossary.md)
- [space-hierarchy.md](./space-hierarchy.md)
- [agent-protocol-interop.md](./agent-protocol-interop.md)
- [transport-bindings.md](./transport-bindings.md)

The current task list and next backlog live in [_tasks.md](./_tasks.md).

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
- `entity` is the unified carrier for collaboration objects
- `relation` is first-class and represents containment, dependency, replies, references, assignments, mentions, and similar links
- `event` is the collaboration fact and audit root
- `view` is a projection and does not own core data
- `board/task/channel/topic/message/memory/run` are standard Entity types, not protocol roots
- `schema/policy` are formal objects rather than unresolved references
- `invite/read_marker/notification` complete the join/read/attention path for human collaboration

### 5.3 Boards and Conversation

- boards are projected from standard Entity types, Relations, and a Kanban View
- chat is projected from standard `channel/topic/message` Entities, Relations, and a Chat View
- topic mode is projected from `topic/message` Entities and `belongs_to/replies_to` Relations
- the same `task`, `run`, or `memory` may have a default discussion topic through Relations
- `@user` and `@object` may be authored as text in the UI, but must be stored as structured Entity/Actor references and `mentions` Relations

### 5.4 Sync

- repo commits are the actor-side publication unit
- operation logs are the audit truth source
- relays are the distribution/subscription layer, not the sole truth source
- indexes/appviews are the query/materialization layer, not the sole truth source
- the service layer requires a minimum interoperable identity-registry / repo / relay / index / blob / authz surface
- board/chat/topic/tree/graph are sync profiles and View projections, not separate protocols
- commit/op submission must be idempotent by design
- authorization validity must converge under the same reducer ordering
- recall converges through redaction semantics, not guaranteed global erasure
- relays / indexes may forward encrypted payloads without decrypting them
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

## 6. Relation to the Legacy `contrix-spec`

The old specification remains useful as a reference, but the new specification does **not** aim for data-model compatibility by default.

Useful inheritance:

- JSON/HTTP friendliness
- signing and audit discipline
- decentralized service discovery
- layered thinking around attachments, sync, and indexing

Assumptions that should be dropped or weakened:

- room-first abstractions
- messages/events carrying every business object
- a homeserver as the only central entry point
- reconstructing business state from chat history

## 7. Normative Language

Normative language in this directory follows RFC 2119 style keywords:

- `MUST`
- `SHOULD`
- `MAY`

If a section is clearly framed as a recommendation, draft direction, or future extension, it is non-binding.

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

## 9. Next Priorities

Once this framework stabilizes, the next priorities should be:

1. Test vectors  
   Cross-implementation vectors for canonical JSON, event hashes, signatures, state resolution, redaction, and sync tokens.
2. OpenAPI consolidation  
   Merge the service, sync, device crypto, and policy-server endpoint drafts into a single OpenAPI surface.
3. Conformance suite  
   Automated interoperability tests for repo, relay, index, E2EE client, Applet, and policy-server profiles.
4. Space version v2 candidates  
   Freeze any incompatible auth/state/redaction changes into a future Space version rather than mutating v1.

## 10. One-sentence Summary

Contrix New is meant to solve:

- decentralized collaborative objects
- a unified data model for boards and chat/topic interaction
- stable identity and authorization
- AI-agent writable, searchable, auditable long-term memory

It is not meant to be another renamed chat protocol.
