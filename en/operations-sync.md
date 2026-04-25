# Operations And Sync Draft

## 1. Goal

Contrix New is a distributed protocol for publishing, distributing, querying, and converging collaborative objects.

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
- `relay`
- `index`
- `blob store`

### 2.1 Repo

A repo is the publication source for one principal.

### 2.2 Relay

A relay is the workspace distribution layer.

### 2.3 Index

An index is the materialization and query layer.

### 2.4 Blob Store

The blob store is responsible for attachments and large content.

## 3. Repo-first Publication Model

Contrix New uses a repo-first model:

1. actors write to their own repos first
2. repos publish commits
3. relays aggregate authorized workspace ops
4. indexes reduce them into current state

This model applies equally to:

- board/item updates
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
  "ops": [
    "cx:op:01JS0OP000000000000000000",
    "cx:op:01JS0OQ000000000000000000"
  ],
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 5. Operation Envelope

Every op MUST have a common envelope.

```json
{
  "op_id": "cx:op:01JS0OP000000000000000000",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "actor": "did:web:alice.example.com",
  "type": "cx.item.update",
  "target_ref": "cx:item:01JS0IT000000000000000000",
  "causal": {
    "deps": [
      "cx:op:01JS0OO000000000000000000"
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

### 7.1 Workspace / Board / Collection / View

- `cx.workspace.create`
- `cx.workspace.update`
- `cx.board.create`
- `cx.board.update`
- `cx.collection.create`
- `cx.collection.update`
- `cx.collection.move`
- `cx.view.create`
- `cx.view.update`

### 7.2 Item / Comment / Relation / Attachment

- `cx.item.create`
- `cx.item.update`
- `cx.item.move`
- `cx.item.reorder`
- `cx.comment.create`
- `cx.comment.update`
- `cx.comment.redact`
- `cx.relation.create`
- `cx.relation.delete`
- `cx.attachment.add`
- `cx.attachment.remove`

### 7.3 Channel / Topic / Message

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
- `cx.message.react`
- `cx.message.unreact`

### 7.4 Run / Memory

- `cx.run.create`
- `cx.run.update`
- `cx.run.complete`
- `cx.run.fail`
- `cx.memory.create`
- `cx.memory.update`
- `cx.memory.confirm`
- `cx.memory.invalidate`
- `cx.memory.supersede`

### 7.5 Capability

- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.revoke`

### 7.6 Private and Ephemeral State

The following are not recommended as durable shared ops:

- typing
- live presence
- local drafts

They MAY be synchronized through relay-ephemeral channels or actor-private state.

## 8. Operation-body Principle

Non-create operations SHOULD carry deltas rather than full object snapshots.

Examples:

- `cx.item.update` carries field deltas
- `cx.item.move` carries target container and new rank
- `cx.message.revise` carries only new content
- `cx.message.redact` carries only the target message and reason

## 9. Validation Flow

Any repo, relay, or index receiving an op should validate at least:

1. the signature is valid
2. the actor DID resolves
3. the key was valid at the operation time
4. `workspace_id` matches the target workspace
5. the capability was effective at the operation time
6. causal dependencies do not violate basic constraints

## 10. Snapshot

Snapshots are acceleration layers, not truth sources.

```json
{
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "snapshot_id": "cx:snap:01JS0SN000000000000000000",
  "covers_frontier": [
    "cx:op:01JS0OP000000000000000000",
    "cx:op:01JS0OQ000000000000000000"
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

## 11. Sync Surfaces

### 11.1 Repo Sync

For actor-history recovery and audit replay.

### 11.2 Workspace Sync

For workspace current-state and incremental synchronization.

### 11.3 Firehose Subscription

For real-time event distribution.

### 11.4 Query Surface

For views, search, memory retrieval, and thread queries.

## 12. Board / Chat / Topic Sync Profiles

### 12.1 Board Mode

Default sync:

- board/item/collection current state
- comment summaries for the currently opened item
- default-topic summaries for the currently opened item

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

## 13. First-time Workspace Join

Recommended flow:

1. fetch workspace metadata
2. fetch the latest snapshot manifest
3. download snapshot chunks
4. fetch op increments after the snapshot frontier
5. run the reducer locally
6. enter cursor-based incremental subscription

## 14. Selective Sync

Selective sync is a key protocol capability.

The first version should support at least:

- workspace
- board
- channel
- topic
- object kind
- target refs
- watched items
- watched runs
- changes since cursor

## 15. Conflicts and Convergence

### 15.1 No Global Consensus

The first version of Contrix does not introduce a global consensus chain.

It requires:

- for the same workspace
- over the same effective op set
- all correct reducers

to converge to the same current state.

### 15.2 Base Ordering Rule

When two ops have no explicit causal ordering, compare in this order:

1. `hlc`
2. `actor`
3. `actor_seq`
4. `op_id`

## 16. Field-level Merge and Object-level Convergence

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

- `message.create` is append-only
- `message.revise` forms a revision chain
- default views show the latest visible revision

### 16.5 Reaction

Reactions converge using `(message_id, actor, reaction_key)` as the OR-Set key.

## 17. Ordering Model

Drag-and-drop ordering should use:

- `container_id`
- `rank`

where `rank` is recommended to be a fractional-indexing string.

Message timeline display order should use:

- `hlc + actor + actor_seq + op_id`

## 18. Tombstones, Redaction, and Restore

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

## 19. Blob Sync

Blob content should not be forced into the same stream as metadata.

Recommended behavior:

- sync metadata first
- fetch content on demand
- validate by content hash

## 20. Local Storage Guidance

Clients SHOULD maintain three local layers:

- raw commits / raw ops
- reduced snapshots
- materialized indexes

## 21. Initial Design Decisions

The current draft recommends fixing:

- repo commits as actor publication units
- ops as shared-state reduction units
- one sync protocol across board/chat/topic modes
- recalls as redaction/tombstone semantics
- convergence through fixed reducer rules

## 22. Further Work

The next round still needs:

- cursor encoding
- HLC text format
- snapshot chunk schemas
- a standard sync surface for read markers
- wire-level relay/index interfaces
