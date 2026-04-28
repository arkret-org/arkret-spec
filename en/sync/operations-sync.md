# Operations And Sync Draft

## 1. Goal

Contrix is a distributed protocol for publishing, distributing, querying, and converging collaborative objects.

The sync layer must support all of the following:

- actor-verifiable publication
- append-only audit logs
- fast current-state recovery
- board-mode synchronization
- chat/topic-mode synchronization
- offline writes
- eventual convergence

## 2. Core Roles

The initial draft distinguishes:

- `client`
- `agent`
- `repo`
- `principal_server`
- `sync_service`
- `index`
- `blob store`

### 2.1 Repo

A repo is the publication source for one principal.

A repo is a protocol logical object, not necessarily a server process. It contains at least:

- a commit log: the principal-signed commit chain
- an operation / event store: collaboration operations referenced by commits
- a head / cursor: the current published frontier
- proof material: signatures, hashes, DID key-state references, and optional witness receipts

A repo MAY be maintained locally by a client, hosted by a Principal Server, or replicated by read-only replicas. Network `/repo/*` endpoints are the Principal Server API surface for accessing a repo; they are not the repo authority itself. Receivers MUST verify commit signatures, DID control chains, hash chains, monotonic sequence rules, and operation idempotency.

Implementations MAY store a repo in a database, object storage, append-only files, a Merkle log, a content-addressed block store, or another storage engine. The protocol does not require a database model; it requires a verifiable commit log, operation/event store, head / cursor, and proof material.

### 2.2 Principal Server / Sync Service

A Principal Server is the service boundary controlled or explicitly delegated by a principal; the sync service is its space incremental sync capability. It is not an independent third-party server role and must not receive plaintext private content unless delegated by the relevant principal or Space policy. It MUST NOT write non-encrypted private bodies, attachment previews, full-text indexes, notification summaries, embeddings, or reversible derived summaries into derived services absent from `plaintext_visible_services`.

### 2.3 Index

An index is the materialization and query layer.

### 2.4 Blob Store

The blob store is responsible for attachments and large content.

## 3. Repo-first Publication Model

Contrix uses a repo-first model:

1. actors write to their own repos first
2. repos publish commits
3. Principal Servers / sync services exchange authorized space operations
4. indexes reduce them into current state

This model applies equally to:

- board/entity updates
- topic/message flows
- run/memory persistence

## 4. Repo Commit

The draft uses commits as the repo publication unit.

```json
{
  "commit_id": "cx:commit:01JS0CMT000000000000000000",
  "repo_did": "did:web:alice.example.com",
  "prev_commit": "cx:commit:01JS0CMP000000000000000000",
  "seq": 144,
  "created_at": "2026-04-22T08:30:00Z",
  "operations": [
    "cx:operation:01JS0OP000000000000000000",
    "cx:operation:01JS0OQ000000000000000000"
  ],
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 5. Operation Envelope

Every operation MUST have a common envelope.

```json
{
  "operation_id": "cx:operation:01JS0OP000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor": "did:web:alice.example.com",
  "type": "cx.entity.update",
  "target_ref": "cx:entity:01JS0EN000000000000000000",
  "causal": {
    "deps": [
      "cx:operation:01JS0OO000000000000000000"
    ],
    "hlc": "2026-04-22T08:31:03.221Z-0007-did:web:alice.example.com",
    "actor_seq": 42
  },
  "body": {},
  "authz_ref": "cx:grant:01JS0GR000000000000000000",
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 6. Why `deps + hlc + actor_seq`

A single timestamp is not enough for distributed collaboration convergence.

The draft uses:

- `deps` for direct causal dependency
- `hlc` for near-real-time logical ordering
- `actor_seq` for actor-local monotonic sequence

## 7. Operation Families

### 7.1 Space / Schema / Policy

- `cx.space.create`
- `cx.space.update`
- `cx.schema.define`
- `cx.schema.update`
- `cx.policy.set`

### 7.2 Board / Collection / View

- `cx.board.create`
- `cx.board.update`
- `cx.collection.create`
- `cx.collection.update`
- `cx.collection.move`
- `cx.view.create`
- `cx.view.update`

### 7.3 Entity / Comment / Relation / Attachment

- `cx.entity.create`
- `cx.entity.update`
- `cx.entity.delete`
- `cx.entity.restore`
- `cx.relation.move` (for list/order reposition)
- `cx.comment.create`
- `cx.comment.update`
- `cx.comment.redact`
- `cx.relation.create`
- `cx.relation.delete`
- `cx.attachment.add`
- `cx.attachment.remove`

### 7.4 Channel / Topic / Message

- `cx.channel.create`
- `cx.channel.update`
- `cx.channel.archive`
- `cx.topic.create`
- `cx.topic.update`
- `cx.topic.close`
- `cx.topic.reopen`
- `cx.message.create`
- `cx.message.revise`
- `cx.message.redact`
- `cx.reaction.add`
- `cx.reaction.remove`

### 7.5 Run / Memory

- `cx.run.create`
- `cx.run.update`
- `cx.run.complete`
- `cx.run.fail`
- `cx.memory.create`
- `cx.memory.update`
- `cx.memory.confirm`
- `cx.memory.invalidate`
- `cx.memory.supersede`

### 7.6 Invite / Read State

- `cx.invite.create`
- `cx.invite.cancel`
- `cx.invite.accept`
- `cx.read.marker`

### 7.7 Capability

- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.revoke`

### 7.8 Private and Ephemeral State

The following are not recommended as durable shared operations:

- typing
- live presence
- local drafts

They MAY be synchronized through sync ephemeral channels or actor-private state.

## 8. Operation-body Principle

Non-create operations SHOULD carry deltas rather than full object snapshots.

Examples:

- `cx.entity.update` carries field deltas
- `cx.relation.move` / `cx.entity.update` for order-sensitive repositioning
- `cx.message.revise` carries only new content
- `cx.message.redact` carries only the target message and reason

## 9. Validation Flow

Any repo, sync service, or index receiving an operation should validate at least:

1. the signature is valid
2. the actor DID resolves
3. the key was valid at the operation time
4. `space_id` matches the target Space
5. the capability was effective at the operation time
6. causal dependencies do not violate basic constraints

## 10. Snapshot

Snapshots are acceleration layers, not truth sources.

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "snapshot_id": "cx:snap:01JS0SN000000000000000000",
  "covers_frontier": [
    "cx:operation:01JS0OP000000000000000000",
    "cx:operation:01JS0OQ000000000000000000"
  ],
  "generated_at": "2026-04-22T08:40:00Z",
  "generator": "did:web:index.example.com",
  "reducer_version": "0.1.0",
  "chunks": [
    {
      "kind": "items",
      "url": "https://index.example.com/cx/snapshots/01/items.json"
    },
    {
      "kind": "messages",
      "url": "https://index.example.com/cx/snapshots/01/messages.json"
    }
  ]
}
```

Implementations SHOULD let the snapshot manifest additionally carry:

- `schema_profile_refs`
- `chunk_digests`
- `generator_signature`

That allows clients to verify before trusting a snapshot:

- which frontier it covers
- which reducer and schema profile produced it
- whether chunk contents were tampered with

## 11. Sync Surfaces

### 11.1 Repo Sync

For actor-history recovery and audit replay.

### 11.2 Space Sync

For space current-state and incremental synchronization.

### 11.3 Sync Stream Subscription

For real-time event distribution.

### 11.4 Query Surface

For views, search, memory retrieval, and thread queries.

### 11.5 Authz / Invite Surface

For:

- fetching invites
- fetching effective grant sets
- checking whether an operation is writable at the current frontier

## 12. Board / Chat / Topic Sync Profiles

### 12.1 Board Mode

Default sync:

- board/entity/collection current state
- comment summaries for the currently opened entity
- default-topic summaries for the currently opened entity

### 12.2 Chat Mode

Default sync:

- channel metadata
- open topics
- recent N messages
- live message/reaction/redaction increments

### 12.3 Topic Mode

Default sync:

- topic metadata
- anchor object
- recent N messages
- reverse backfill cursor

## 13. First-time Space Join

Recommended flow:

1. fetch space metadata
2. fetch invite / grant views relevant to the current principal
3. fetch the latest snapshot manifest
4. download snapshot chunks
5. fetch operation increments after the snapshot frontier
6. run the reducer locally
7. enter cursor-based incremental subscription

If the client starts with a handle rather than a DID, it MUST first complete handle-to-DID resolution and bidirectional verification before step 1.

## 14. Selective Sync

Selective sync is a key protocol capability.

The first version should support at least:

- space
- board
- channel
- topic
- object kind
- target refs
- watched objects
- watched runs
- changes since cursor

## 15. Idempotency, Deduplication, and Replay

In decentralized sync, duplicate submission and duplicate delivery are normal, not exceptional.

Therefore:

- `commit_id` and `operation_id` MUST be globally stable
- the exact same `commit_id` / `operation_id` payload MAY be accepted multiple times
- if the same ID is reused with different content, nodes MUST reject it and record a conflict
- sync services and indexes SHOULD deduplicate by `operation_id` rather than counting deliveries

This prevents:

- client retries from causing duplicate writes
- multi-Principal-Server loops from causing duplicate fanout
- indexes from overcounting because of repeated delivery

## 16. Conflicts and Convergence

### 15.1 No Global Consensus

The first version of Contrix does not introduce a global consensus chain.

It requires:

- for the same space
- over the same effective operation set
- all correct reducers

to converge to the same current state.

### 15.2 Base Ordering Rule

When two operations have no explicit causal ordering, compare in this order:

1. `hlc`
2. `actor`
3. `actor_seq`
4. `operation_id`

## 17. Field-level Merge and Object-level Convergence

### 16.1 Scalar Fields

Examples:

- `title`
- `body`
- `status`
- `priority`

Suggested strategy:

- LWW by causal order

### 16.2 Set Fields

Examples:

- `labels`
- `assignees`
- `watchers`

Suggested strategy:

- OR-Set

### 16.3 Ordered Fields

Examples:

- `rank`
- `container_id`

These should be handled via move/reorder semantics.

### 16.4 Message

- `cx.message.create` is append-only
- `cx.message.revise` forms a revision chain
- default views show the latest visible revision

### 16.5 Reaction

Reactions converge using `(message_id, actor, reaction_key)` as the OR-Set key.

## 18. Ordering Model

Drag-and-drop ordering should use:

- `container_id`
- `rank`

where `rank` is recommended to be a fractional-indexing string.

Message timeline display order should use:

- `hlc + actor + actor_seq + operation_id`

## 19. Tombstones, Redaction, and Restore

### 18.1 Object Deletion

Object deletion SHOULD use tombstones.

### 18.2 Message Recall

Message recalls should use redaction rather than physical disappearance.

Required semantics:

- default views show "recalled" or equivalent
- normal views should not keep leaking the body
- no promise of global physical erasure

### 18.3 Redaction Before the Original Message Arrives

Receivers SHOULD keep dangling redactions and apply them once the target message arrives.

## 20. Authorization-time Convergence

Authorization cannot rely only on wall-clock time; otherwise revocations, late operations, and offline writes become inconsistent.

The initial recommendation is:

- grant / delegate / revoke are themselves operations
- whether a business operation is valid is decided by the effective authorization set under the same reducer ordering
- if a write is ordered after the relevant revoke, it MUST be treated as invalid
- if ordering cannot be established, implementations SHOULD fail closed

That means authorization semantics must follow the same causal and ordering rules as the rest of the protocol.

## 21. Visibility and Encrypted Payloads

ACLs are not the same thing as ciphertext protection, and sync services should not be forced to understand every body they forward.

The first version should therefore distinguish:

- routable metadata: `space_id`, `target_ref`, `type`, `causal`
- cleartext indexable metadata: light workflow fields such as `status`, `labels`, `priority`, and `due_at`; if such fields expose private content or sensitive organization state, the receiving Index MUST be listed in `plaintext_visible_services`
- opaque encrypted payload: message bodies, attachment contents, sensitive memory bodies

Implementations MAY encrypt content using the envelope format named by `policy.encryption_profile`.  
Even when a sync service or index cannot decrypt the payload, it SHOULD still be able to forward it, deduplicate it, and preserve causal structure.

## 22. Blob Sync

Blob content should not be forced into the same stream as metadata.

Recommended behavior:

- sync metadata first
- fetch content on demand
- validate by content hash

## 23. Local Storage Guidance

Clients SHOULD maintain three local layers:

- raw commits / raw operations
- reduced snapshots
- materialized indexes

## 24. Initial Design Decisions

The current draft recommends fixing:

- repo commits as actor publication units
- operations as shared-state reduction units
- one sync protocol across board/chat/topic modes
- invite / grant / snapshot as the main space-bootstrap flow
- commit/operation retries as idempotent by design
- authorization validity converging under the same reducer ordering
- encrypted payloads being forwardable through non-decrypting sync services and indexes
- recalls as redaction/tombstone semantics
- convergence through fixed reducer rules

## 25. Further Work

The next round still needs:

- cursor encoding
- HLC text format
- snapshot chunk schemas
- formal schemas for snapshot signatures and chunk digests
- an encrypted-payload envelope schema
- a standard sync surface for read markers
- wire-level sync/index interfaces

