# Architecture Draft

## 1. Goal

The top-level architecture of Contrix must satisfy four things at once:

- decentralized identity and publication
- shared collaborative objects across many principals
- human-friendly operational interfaces
- AI-agent-friendly execution and memory semantics

This requires the protocol to separate identity, writes, distribution, queries, presentation, and memory from the beginning, instead of collapsing them into a single service role.

## 2. Overall Model

Contrix uses a **principal repo + identity registry + space relay + query index** architecture.

### 2.1 Principal Repo

Each principal has its own repo for publishing signed commits and operations.

It is responsible for:

- actor-verifiable publication
- historical traceability
- retransmission after offline periods
- the audit baseline

This borrows from atproto's repo idea, but Contrix repos publish **collaboration operations**, not social records for feeds.

### 2.2 Space Relay

The relay aggregates, deduplicates, forwards, and serves authorized operations relevant to a space across multiple principal repos.

It is responsible for:

- space-scoped distribution
- cursor/firehose subscriptions
- fast fanout
- preliminary authorization filtering

The relay is not the only truth source and should not be able to rewrite actor history.

### 2.3 Query Index / AppView

The index materializes authorized operations into queryable current state and projections.

It is responsible for:

- current-state reduction
- complex querying
- full-text search
- view inputs for rendering
- reporting and metrics
- optional embedding/vector indexing

The index is a derived layer, not the truth source.

### 2.4 Blob Store

The blob store serves attachments, large objects, and optionally snapshot chunks.

Blob addressing may be multi-source, and integrity should be based on content hashes rather than a single URL.

### 2.5 Capability Authority

Capability authority is a logical role rather than a required standalone deployment.

It is responsible for:

- publishing authorization policy
- serving grant/revoke/delegate related state
- providing cacheable authorization inputs for repos, relays, and indexes

### 2.6 Client / Agent

Contrix clients are not limited to GUI applications. They also include:

- CLI clients
- webhook workers
- CI agents
- autonomous agents
- background automations

Agents are first-class protocol participants, not just plugins hanging off a UI.

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

### 3.3 Distribution Plane

Responsible for:

- relay firehoses
- space incremental sync
- deduplication and cursoring

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
- allowing relays to forward opaque payloads without decrypting them

### 3.8 Portability Plane

Responsible for:

- export / import
- snapshot + op replay
- service replacement
- migration across multiple repos / relays / indexes

## 4. Deployment Topologies

Contrix does not require all roles to be separately deployed.

### 4.1 Single-user / Small-team Topology

One deployment may host:

- identity registry
- repo
- relay
- index
- blob

This is suitable for:

- small teams
- private experiments
- single-organization deployments

### 4.2 Multi-organization Collaboration Topology

A common pattern is:

- each organization maintains its own principal repos
- one or more shared space relays exist
- multiple query indexes serve different parties

This maps well to cross-company delivery and supply-chain collaboration.

### 4.3 Agent-first Topology

In agent-heavy environments, a common pattern is:

- a user/org DID acts as the authority
- an agent DID receives constrained capabilities
- run logs are written to an agent repo
- a space relay aggregates them into the collaboration space
- an index materializes human review queues

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
- which ops were inside a commit
- whether sequence and signatures are valid

A repo must not unilaterally define the shared current state of a space.

### 6.2 The Relay Accelerates Distribution but Must Not Rewrite History

A relay may:

- cache
- order
- deduplicate
- serve cursor-based subscriptions

A relay must not:

- forge actor ops
- silently drop still-valid historical ops

### 6.3 The Index Interprets State but Must Not Replace the Audit Chain

An index may:

- serve current state
- provide search
- return board/list/graph projections

An index must not become the only verifiable source.

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
- space relays are the distribution layer
- indexes/appviews are the materialized query layer
- blobs are a separate content layer
- capabilities form an explicit authorization layer
- runs and memories are first-class protocol objects
- the same data model serves both human UIs and agent memory
- confidentiality and portability are explicit protocol planes rather than deployment afterthoughts

## 9. Further Work

The next round still needs to define:

- the precise repo commit encoding
- the relay firehose subscription protocol
- the index query surface
- capability cache consistency strategy
- interoperability requirements with multiple relays and indexes
- encrypted-envelope and key-distribution interfaces
- consistency boundaries for export / import

