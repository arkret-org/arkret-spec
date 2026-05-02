# Architecture Draft

## 1. Goal

The top-level architecture of Contrix must satisfy four things at once:

- decentralized identity and publication
- shared collaborative objects across many principals
- human-friendly operational interfaces
- AI-agent-friendly execution and memory semantics

This requires the protocol to separate identity, writes, distribution, queries, presentation, and memory from the beginning, instead of collapsing them into a single service role.

## 2. Overall Model

Contrix uses a **principal server + principal repo + identity registry + client-side projection** architecture.

A `Principal Server` is the service boundary controlled by a principal or explicitly delegated through DID service metadata and Space policy. It may host repo, sync, blob, push, and policy capabilities on one deployment while the protocol keeps those responsibilities separate. Search, inbox, notifications, and View projection are client- or SDK-local derived capabilities by default.

Contrix does not define an independent third-party distribution server as a core role. Cross-principal and cross-organization propagation is handled by sync and federation between participating Principal Servers.

### 2.1 Principal Repo

Each principal has its own repo for publishing signed commits and operations.

It is responsible for:

- actor-verifiable publication
- historical traceability
- retransmission after offline periods
- the audit baseline

This borrows from atproto's repo idea, but Contrix repos publish **collaboration operations**, not public-content distribution records.

A Principal Repo is a logical verifiable publication log, not a server. It may be carried by:

- a local append-only log on a user device
- repo storage and `/repo/*` APIs embedded in a Principal Server
- read-only storage replicas
- a Principal Server service endpoint declared in the DID Document

The concrete storage shape is implementation-defined: database tables, commit / operation blobs in object storage, a filesystem append-only log, a Merkle log, a CAR-like block store, or a combination of these. The protocol requires stable access to canonical commit bytes, operation/event bytes, hashes, signatures, heads, cursors, and proof material.

Repo authority comes from principal signatures over commits / operations, the DID control chain, commit hash chains, and idempotent sequence rules, not from the Principal Server that hosts it. A Principal Server can deny service, lag, or lose replicas, but it cannot forge valid writes for a principal.

### 2.2 Principal Server

The Principal Server hosts or proxies:

- principal repo submission, reading, and replication
- space-scoped incremental sync, backfill, and subscriptions
- blob, push, policy, and device-message support
- federation transactions with other Principal Servers

The Principal Server is not the identity itself and cannot forge commits or operations for a principal. Its authority comes from DID service delegation, Space policy, capabilities, and signed events.

Plaintext rule:

- Non-E2EE or non-content-encrypted private content MUST NOT be submitted to a third-party service that is not explicitly delegated by the sender, recipient, or Space policy.
- If a Space declares a shared Space Host, that host MUST be a trusted Principal Server or organization service DID listed by Space policy.
- Clients MUST verify the target service before submitting plaintext content.
- Any service that receives or stores private bodies, attachment previews, full-text indexes, notification summaries, embeddings, or reversible derived summaries MUST be declared in Space policy as `plaintext_visible_services`.
- Recipient Principal Servers are visibility boundaries for non-encrypted content delivered to their recipients; they are not transparent forwarding layers.
- Untrusted third-party services may receive only public content, encrypted envelopes, or opaque payloads.

### 2.3 Client Query / Projection

Clients or SDKs may materialize synchronized, authorized, and decrypted events into current state, search indexes, inboxes, notifications, and View projections. These are local derived experiences, not mandatory protocol services.

The protocol constrains the following boundaries:

- View is a synchronized projection definition, not the truth source for projected objects.
- Query, search, and projection must not bypass Space policy, Room membership, history visibility, E2EE visibility, or capability.
- Any delegated search / projection service that receives private plaintext, body summaries, embeddings, notification summaries, or reversible derived content MUST be listed in `plaintext_visible_services`.
- Derived output is not a truth source and must be recomputable from signed events, reducer profiles, View definitions, and causal frontiers.

### 2.4 Blob Store

The blob store serves attachments, large objects, and optionally snapshot chunks.

Blob addressing may be multi-source, and integrity should be based on content hashes rather than a single URL.

### 2.5 Capability Authority

Capability authority is a logical role rather than a required standalone deployment.

It is responsible for:

- publishing authorization policy
- serving grant/revoke/delegate related state
- providing cacheable authorization inputs for repos, sync services, and projection executors

### 2.6 Client / Agent

Contrix clients are not limited to GUI applications. They also include:

- CLI clients
- webhook workers
- CI agents
- autonomous agents
- background automations

Agents are first-class protocol participants, not just plugins hanging off a UI.

### 2.7 Principal Server Deployment Profiles

Contrix defines capabilities as service roles. Real deployments may combine multiple roles in one process, domain, or node. Combining roles does not merge their security boundaries: service DID, `service_type`, capability, Space policy, plaintext visibility, and endpoint contracts must remain distinguishable.

Use **Principal Server** directly. Deployment differences are expressed by deployment profile, which service roles are embedded or split, delegation source, public-infrastructure dependency, compliance requirements, and plaintext-boundary obligations.

| Deployment level | Must self-host | Usually public or managed | Fits |
| --- | --- | --- | --- |
| Individual / small team | Principal Server | Identity Resolver, Directory, Push Gateway, TURN / Media Relay | Individuals, families, small projects, small teams. |
| Standard organization | Organization-delegated Principal Server, Auth / Account Server; add Admin / Policy Server when centralized authorization and audit are needed | Identity Resolver, Directory, Push Gateway, TURN / Media Relay | Companies, schools, communities, ordinary collaboration organizations. |
| High-security organization | One or more organization-delegated Principal Servers, Auth / Account Server, Identity Resolution Infrastructure, Policy / Authz Server, Blob / Media Server | Public Directory, Push Gateway, or external federation gateways are optional | Government, enterprise, healthcare, finance, high-compliance organizations. |
| Classified / isolated network | Principal Server, Identity Resolution Infrastructure, Auth / Account Server, Directory Server, Policy / Authz Server, Repo / Blob Server, Sync / Federation Server, Audit / Compliance Server | Public services are normally not dependencies; cross-domain collaboration must use controlled gateways, invitation bundles, or trust bundles that define resolver context | Military, intranet, fully isolated, or strongly controlled networks. |

The minimum individual or small-team deployment has one Principal Server:

```text
Principal Server
├─ principal endpoint
├─ repo storage
├─ sync / federation endpoint
├─ local policy
├─ blob storage
└─ basic app view / inbox
```

It may use public infrastructure by default:

- Identity Resolver: public DID / handle resolution; concretely this may be implemented by a `did:uuid` registry / witness, a `did:web` method resolver, a local `did:key` resolver, or `did:keri` witnesses / watchers / resolvers.
- Directory Server: public Space, Organization, Actor, and Applet discovery.
- Push Gateway: blind mobile or desktop notification delivery.
- TURN / Media Relay: media relay and NAT traversal.

Auth / Account Server and Identity Resolution Infrastructure do not need to be deployed by the same operator. A standard organization may run its own login entry point, SSO, device pairing, and session management while continuing to use the public `did:uuid` resolver for user DIDs, a local `did:key` resolver, or `did:keri` resolvers / witnesses / watchers. The login server proves which DID a service account or device is currently bound to; the identity resolver only returns or verifies that DID's control keys, key state, key log / KERI log, and service-delegation evidence; Organization Policy / Authz then decides whether the DID may access organization Spaces, repos, or admin actions.

`did:web` and other method-specific DIDs MAY resolve through their own domain or external network rules; organization-private `did:uuid` MAY resolve only inside the organization's or enclave's resolver trust domain. Clients and servers must select resolvers according to local trust policy and must not assume that all `did:uuid` identifiers share the same resolver entry point.

Ordinary users should not need to self-host Directory Server, Push Gateway, Identity Resolution Infrastructure, TURN / Media Relay, or Moderation / Compliance Server. Search, inbox, notification, and View projection can be local client features. With `did:key`, identity resolution can be fully local; with `did:keri`, deployments usually need KERI log / witness / watcher / OOBI infrastructure but not a traditional centralized registry. These infrastructure roles should be self-hosted only when an organization needs identity sovereignty, network isolation, compliance audit, independence from public networks, or controlled cross-organization federation.

Advanced implementations still declare capabilities and security boundaries through the following service roles. Multiple roles may be combined in one deployment, but service DID, `service_type`, capability, Space policy, plaintext visibility, and endpoint contracts must remain distinguishable.

| Service role | Common `service_type` | Main services | Truth source? | Plaintext boundary |
| --- | --- | --- | --- | --- |
| Principal Server | `principal_server` | Principal-controlled entry point; may aggregate repo, sync, federation, device messages, policy, and blob capabilities. | No; truth comes from signed repos / events. | May receive non-encrypted content only within principal or Space-policy delegation. |
| Identity Resolution Infrastructure | `identity_registry` or method-specific resolver | DID Documents, DID key logs, KERI event logs, handle bindings, receipts / witnesses, watchers, OOBI, service discovery. | One verifiable source for identity control history; `did:key` may resolve locally by algorithm. | Should not receive Space bodies. |
| Auth / Account Server | `auth_server` or deployment-specific | Passkeys, OIDC, SSO, device pairing, session grants, account recovery, soft logout. | No; it proves service-account login and binds it to DID / device. | Password recovery must not grant E2EE plaintext or DID control by itself. |
| Sync / Federation Server | `principal_server` or `sync_node` | Client sync, Space subscription, backfill, snapshot heads, cross-domain federation transactions. | No; it propagates and backfills. | May forward non-encrypted private content only to authorized Principal Servers or `plaintext_visible_services`. |
| Directory Server | `directory_service` | Authorized search and exact resolution for Spaces, Organizations, Actors, handles, and Applets. | No; derived discovery layer. | Returns minimum discoverable data and must not expose private topology. |
| Blob / Media Server | `blob_node` / `media_service` | Blob upload, HEAD / GET authenticated download, thumbnails, previews, retention, media policy. | Content hash is verifiable; metadata is service-declared. | Private downloads, previews, and thumbnails require authorization. |
| Device / Key Server | `device_key_service` | To-device messages, one-time keys, fallback keys, device lists, secret-backup metadata. | No; device trust comes from signature chains. | Should not be able to decrypt E2EE bodies. |
| Authz / Policy Server | `authz_service` / `policy_server` | Capability queries, grant / invite queries, policy decisions, risk scoring, quarantine / review. | No; decisions must trace to signed policy / grants. | Policy previews use minimum disclosure unless plaintext-visible authority is explicit. |
| Push Gateway | `push_gateway` | Push device registration, unregister, blind notification delivery, mobile push adapters. | No. | Must not receive E2EE plaintext or body summaries by default. |
| Applet Server | `applet_service` | Bots, bridges, external SaaS, portal Spaces, ghost actors, Applet transactions. | No; writes still require capabilities and signatures. | Plaintext visibility is limited by explicit Space / principal authorization. |
| MIMI Provider Facade | `mimi_provider_facade` | MIMI provider discovery, room binding, key material, submit message, groupInfo, consent, identifier query, abuse report, proxy download. | No; MIMI room state is an interoperability projection of Contrix Space/Channel state. | May process ciphertext, metadata, or plaintext only within `cx.mimi.room_binding` and Space policy authorization. |
| Agent Runtime Server | `agent_runtime` | Agent runs, tool execution, memory promotion, A2A / ACP / MCP handoff. | No; outputs become protocol facts only after writing to Repo / Space. | Agent visibility is bounded by capability, device / session, and Space policy. |
| Realtime Media Server | `media_service` / `sfu_service` / `turn_service` | WebRTC assist, ICE config, TURN / STUN, SFU / MCU, recording. | No. | SFU / TURN normally should not see plaintext; MCU / recording requires explicit authorization. |
| Moderation / Compliance Server | `moderation_service` | Reports, review queues, server ACLs, policy lists, appeals, legal hold / erasure workflows. | No; results must become auditable policy / moderation events. | Receives only minimum evidence or explicitly authorized plaintext. |

The protocol does not require every server type to be publicly deployed. Actual support must be declared through DID Document service entries, `GET /api/v1/server/describe`, `supported_operations`, conformance profiles, and Space policy.

## 3. Architectural Planes

### 3.1 Identity Plane

Responsible for:

- DID resolution
- handle resolution
- service discovery
- key rotation and recovery
- DID-log writes and replication
- registry / witness / replica coordination

### 3.2 Write Plane

Responsible for:

- operation creation
- repo commit creation
- signing
- publishing to the repo

### 3.3 Sync And Federation Plane

Responsible for:

- sync streams
- space incremental sync
- deduplication and cursoring
- Principal Server federation transactions

### 3.4 Query Plane

Responsible for:

- current-state queries
- view queries
- search
- memory retrieval

### 3.5 Presentation Plane

Responsible for:

- kanban/list/table/calendar/timeline/graph/activity projections
- human review queues
- agent-run timelines

### 3.6 Memory Plane

Responsible for:

- run trace capture
- episodic memory
- semantic memory
- memory promotion, supersession, and forgetting

### 3.7 Confidentiality Plane

Responsible for:

- distinguishing visibility from encrypted payloads
- content-encryption envelopes
- key distribution and rotation
- allowing sync services to forward opaque payloads without decrypting them

### 3.8 Portability Plane

Responsible for:

- export / import
- snapshot + operation replay
- service replacement
- migration across multiple repos / Principal Servers / delegated search services

## 4. Deployment Topologies

Contrix does not require all roles to be separately deployed.

### 4.1 Single-user / Small-team Topology

One deployment may host:

- identity registry
- repo
- sync service
- blob

This is suitable for:

- small teams
- private experiments
- single-organization deployments

### 4.2 Multi-organization Collaboration Topology

A common pattern is:

- each organization maintains its own principal repos
- each participant uses its own Principal Server or explicitly delegated organization server
- Principal Servers exchange Space operations through federation transactions
- participants generate local views from their own authorized data, or explicitly use delegated search / projection extensions

This maps well to cross-company delivery and supply-chain collaboration.

### 4.3 Agent-first Topology

In agent-heavy environments, a common pattern is:

- a user/org DID acts as the authority
- an agent DID receives constrained capabilities
- run logs are written to an agent repo
- the agent Principal Server syncs run logs into the collaboration Space
- clients or delegated projection extensions materialize human review queues

## 5. Core Architecture Direction

Contrix is explicitly:

- space-first
- object-first
- repo-first
- collaboration-first

That means:

- rooms are no longer the universal world model
- messages are no longer the universal atomic unit
- UIs no longer need to reconstruct business state from chat history
- the protocol directly models tasks, decisions, memories, execution traces, and relations as first-class objects

## 6. Trust Boundaries

### 6.1 The Repo Proves What an Actor Published

A repo can prove:

- which principal published which commits
- which operations were inside a commit
- whether sequence and signatures are valid

A repo must not unilaterally define the shared current state of a space.

### 6.2 The Principal Server Syncs but Must Not Rewrite History

A Principal Server may:

- cache
- order
- deduplicate
- serve cursor-based subscriptions
- exchange federation transactions with other Principal Servers

A Principal Server must not:

- forge actor operations
- silently drop still-valid historical operations
- forward plaintext private content to services not delegated by a principal or Space policy
- copy non-encrypted private content to Push, Blob preview, Policy preview, or any delegated search / projection service that is not declared in `plaintext_visible_services`

### 6.3 Projection Interprets State but Must Not Replace the Audit Chain

Client-local projection or a delegated search / projection service may:

- serve current state
- provide search
- return board/list/graph projections

Derived output must not become the only verifiable source.

### 6.4 Capability Is the Legitimacy Boundary

Whether a write is allowed must be decided by the effective capability set, not by:

- whatever the UI currently looks like
- some local implicit role table on one server

## 7. Humans and AI Share the Same Protocol

Contrix does not want two separate systems:

- one for human boards
- one for AI memory

Instead, the protocol should guarantee:

- AI-written objects can be reviewed by humans
- human-created objects can be understood and referenced by AI
- tasks, comments, relations, runs, and memories can interlink
- everything can be projected into usable interfaces

## 8. Initial Architecture Decisions

The current draft recommends fixing the following directions:

- principal repos are the actor publication baseline
- identity registries / witnesses are the DID-document resolution and write layer
- Principal Servers / Sync Services are the controlled sync and federation layer
- search / View projection is a client-local derived experience by default; delegated search services are optional extensions
- blobs are a separate content layer
- capabilities form an explicit authorization layer
- runs and memories are first-class protocol objects
- the same data model serves both human UIs and agent memory
- confidentiality and portability are explicit protocol planes rather than deployment afterthoughts

## 9. Further Work

The next round still needs to define:

- the precise repo commit encoding
- the sync stream subscription protocol
- the client-side query / projection contract
- capability cache consistency strategy
- interoperability requirements with multiple Principal Servers and delegated search / projection extensions
- encrypted-envelope and key-distribution interfaces
- consistency boundaries for export / import

