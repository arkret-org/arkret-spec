# Object Model Draft

## 1. Goal

The Contrix New object model must simultaneously support:

- human team collaboration
- cross-organization collaboration
- board-oriented workflows
- chat and topic discussion
- AI-agent execution traces
- AI-agent long-term memory

The protocol therefore has to revolve around a **work object graph**, not a room-event model or a single UI pattern such as columns-and-cards.

## 2. Design Principles

### 2.1 Stable IDs Are Separate from Display Names

Object references MUST use stable IDs rather than:

- titles
- display names
- handles
- URL paths

### 2.2 Objects Belong to Workspaces, Not UIs

The same object may appear in multiple views and may be used by both humans and agents.

### 2.3 Current State Comes from Reduction, Not Central Overwrite

Current state is reduced from the set of authorized operations rather than silently overwritten by a single central database.

### 2.4 Boards and Chat Share the Same Object Graph

Boards, threads, chat, and forums should all be standard projections of the same object graph rather than separate incompatible data models.

## 3. ID Scheme

The draft recommends stable prefixed IDs with ULID-like random suffixes.

Examples:

- `cx:ws:<ulid>`
- `cx:board:<ulid>`
- `cx:col:<ulid>`
- `cx:item:<ulid>`
- `cx:comment:<ulid>`
- `cx:rel:<ulid>`
- `cx:blob:<ulid>`
- `cx:channel:<ulid>`
- `cx:topic:<ulid>`
- `cx:message:<ulid>`
- `cx:view:<ulid>`
- `cx:run:<ulid>`
- `cx:mem:<ulid>`
- `cx:schema:<ulid>`
- `cx:policy:<ulid>`
- `cx:invite:<ulid>`
- `cx:read:<ulid>`

## 4. Shared Object Metadata

All objects SHOULD share the following base fields:

```json
{
  "id": "cx:item:01JS0000000000000000000000",
  "kind": "item",
  "workspace_id": "cx:ws:01JS0000000000000000000000",
  "created_at": "2026-04-22T08:00:00Z",
  "created_by": "did:web:alice.example.com",
  "updated_at": "2026-04-22T08:05:00Z",
  "updated_by": "did:web:agent.example.com",
  "archived": false,
  "tombstoned": false,
  "version": 7
}
```

## 5. Core Object Set

The initial core object set is:

- workspace
- board
- collection
- item
- comment
- relation
- attachment
- channel
- topic
- message
- view
- run
- memory
- schema
- policy
- invite
- read_marker

Where:

- `item` is the main work object
- `comment` is a durable object-level note
- `channel/topic/message` are conversation objects
- `view` is a projection
- `run` is an execution trace
- `memory` is a long-term knowledge object
- `schema` defines field and object-type constraints
- `policy` defines retention, visibility, encryption, and moderation defaults
- `invite` is the explicit workspace-join bootstrap object
- `read_marker` is actor-private but syncable read state

## 6. Workspace

Workspace is the replication and authorization boundary.

It defines:

- default replication scope
- default authorization scope
- default relay/index/blob services
- default schema/policy

Example:

```json
{
  "id": "cx:ws:01JS0WS000000000000000000",
  "kind": "workspace",
  "owner": "did:web:acme.example.com",
  "name": "Acme Delivery Workspace",
  "description": "Cross-org product delivery and agent automation workspace",
  "visibility": "private",
  "default_policy_ref": "cx:policy:01JS...",
  "default_schema_ref": "cx:schema:01JS..."
}
```

## 7. Board

Board is shared work context, not the protocol's top-level root object.

It can represent:

- product projects
- delivery flows
- incident response boards
- agent review queues

Example:

```json
{
  "id": "cx:board:01JS0BD000000000000000000",
  "kind": "board",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "Release Readiness",
  "description": "Shared launch board for human and agent coordination",
  "status_field": "status",
  "rank_field": "rank",
  "default_view_id": "cx:view:01JS0VW000000000000000000",
  "default_channel_id": "cx:channel:01JS1000000000000000000000",
  "field_schema_ref": "cx:schema:01JS0SC000000000000000000"
}
```

## 8. Collection

Collection is a generic grouping object rather than a Kanban-only column.

It may represent:

- a lane
- a list group
- a folder
- a query segment

Example:

```json
{
  "id": "cx:col:01JS0CL000000000000000000",
  "kind": "collection",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "board_id": "cx:board:01JS0BD000000000000000000",
  "name": "Needs Review",
  "collection_kind": "lane",
  "rank": "m",
  "state_token": "needs_review"
}
```

## 9. Item

Item is the most important business object in the protocol.

### 9.1 Semantics

It represents a collaborative unit of work, not merely a UI card.

### 9.2 Suggested Fields

```json
{
  "id": "cx:item:01JS0IT000000000000000000",
  "kind": "item",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "board_id": "cx:board:01JS0BD000000000000000000",
  "container_id": "cx:col:01JS0CL000000000000000000",
  "item_type": "task",
  "title": "Finalize onboarding copy review",
  "body": "Coordinate product, design, legal, and agent-generated suggestions.",
  "status": "in_progress",
  "rank": "mV",
  "priority": "high",
  "assignees": [
    "did:web:bob.example.com",
    "did:web:agent.copy.example.com"
  ],
  "discussion_topic_id": "cx:topic:01JS1000000000000000000001",
  "labels": [
    "launch",
    "copy"
  ],
  "due_at": "2026-04-28T00:00:00Z",
  "visibility": "workspace"
}
```

### 9.3 `item_type`

The first version should support at least:

- `task`
- `issue`
- `goal`
- `request`
- `decision`
- `note`

## 10. Comment

Comment is an object-level durable explanation object and should not simply be treated as a synonym for `message`.

It is suitable for:

- review notes
- change explanations
- audit-facing annotations
- approval remarks

Example:

```json
{
  "id": "cx:comment:01JS0CM000000000000000000",
  "kind": "comment",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "target_ref": "cx:item:01JS0IT000000000000000000",
  "thread_root_ref": "cx:comment:01JS0CM000000000000000000",
  "reply_to_ref": null,
  "body": "Agent proposed three alternative copy variants. Human review pending."
}
```

## 11. Relation

Relation expresses semantic links between objects.

Suggested fields:

```json
{
  "id": "cx:rel:01JS0RL000000000000000000",
  "kind": "relation",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "from_ref": "cx:item:01JS0IT000000000000000000",
  "to_ref": "cx:mem:01JS0ME000000000000000000",
  "relation_type": "derived_from",
  "directed": true
}
```

## 12. Attachment

Attachment is split into metadata and blob content.

Example:

```json
{
  "id": "cx:blob:01JS0AT000000000000000000",
  "kind": "attachment",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "target_ref": "cx:item:01JS0IT000000000000000000",
  "blob_cid": "bafy...",
  "name": "review-notes.pdf",
  "mime_type": "application/pdf",
  "size": 129034,
  "sha256": "base64url..."
}
```

## 13. Channel

Channel is a long-lived conversation space.

It is suitable for:

- team chat
- board discussion areas
- agent broadcast streams
- announcement streams

Example:

```json
{
  "id": "cx:channel:01JS1000000000000000000000",
  "kind": "channel",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "release-chat",
  "description": "General release coordination chat",
  "channel_kind": "chat",
  "visibility": "workspace",
  "default_topic_mode": "inline"
}
```

## 14. Topic

Topic is a thread or discussion object.

It may:

- belong to a channel
- or anchor directly to another collaboration object

Example:

```json
{
  "id": "cx:topic:01JS1000000000000000000001",
  "kind": "topic",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "anchor_ref": "cx:item:01JS0IT000000000000000000",
  "topic_kind": "thread",
  "title": "Legal review follow-up",
  "status": "open"
}
```

## 15. Message

Message is the atomic timeline object inside a channel or topic.

Example:

```json
{
  "id": "cx:message:01JS1000000000000000000002",
  "kind": "message",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "topic_id": "cx:topic:01JS1000000000000000000001",
  "sender": "did:web:alice.example.com",
  "reply_to_ref": null,
  "body": {
    "format": "markdown",
    "text": "@bob please confirm the legal risk for this item."
  },
  "mentions": [
    {
      "kind": "principal",
      "ref": "did:web:bob.example.com"
    },
    {
      "kind": "object",
      "ref": "cx:item:01JS0IT000000000000000000"
    }
  ],
  "revision_root": "cx:message:01JS1000000000000000000002",
  "visible_state": "active"
}
```

Protocol-level `mentions` must use DIDs or stable object refs rather than storing only raw textual `@xxx` strings.

## 16. View

View is an independent object, though its detailed behavior is defined in [views.md](./views.md).

It defines:

- query scope
- grouping logic
- ordering rules
- visible fields
- layout hints

View is a projection, not the truth.

## 17. Run

Run is an execution-trace object for agents and automations.

Example:

```json
{
  "id": "cx:run:01JS0RN000000000000000000",
  "kind": "run",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "board_id": "cx:board:01JS0BD000000000000000000",
  "agent_id": "did:web:agent.copy.example.com",
  "triggered_by": "did:web:alice.example.com",
  "goal_ref": "cx:item:01JS0IT000000000000000000",
  "status": "running",
  "input_refs": [
    "cx:item:01JS0IT000000000000000000"
  ],
  "output_refs": [],
  "summary": null
}
```

## 18. Memory

Memory is a long-term knowledge object. It is neither a comment nor a vector chunk.

Example:

```json
{
  "id": "cx:mem:01JS0ME000000000000000000",
  "kind": "memory",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "subject_ref": "cx:item:01JS0IT000000000000000000",
  "memory_kind": "decision",
  "title": "Copy variants require legal approval before publishing",
  "body": "Team decided that all onboarding copy touching billing must be reviewed by legal.",
  "source_refs": [
    "cx:comment:01JS0CM000000000000000000",
    "cx:message:01JS1000000000000000000002",
    "cx:run:01JS0RN000000000000000000"
  ],
  "confidence": 0.92,
  "status": "confirmed"
}
```

## 19. Schemas and Custom Fields

Contrix must support custom fields, but it should not allow unconstrained JSON sprawl.

Suggested schema object:

- `cx:schema:<id>`

Referenced by a workspace or board.

Example:

```json
{
  "id": "cx:schema:01JS0SC000000000000000000",
  "kind": "schema",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "default-item-schema",
  "applies_to": [
    "item"
  ],
  "version": 3,
  "fields": [
    {
      "name": "priority",
      "type": "enum",
      "required": false,
      "options": ["low", "medium", "high"]
    },
    {
      "name": "due_at",
      "type": "datetime",
      "required": false
    }
  ]
}
```

Suggested field types:

- `text`
- `number`
- `bool`
- `date`
- `datetime`
- `enum`
- `multi_enum`
- `principal_ref`
- `object_ref`
- `url`

Schemas SHOULD explicitly declare:

- `applies_to`
- `version`
- `fields`
- `migration_notes`

That keeps reducers, views, and import/export flows interpretable across schema upgrades.

## 20. Policy

The protocol already references `policy`, so it must be a formal object rather than an implementation-private assumption.

Example:

```json
{
  "id": "cx:policy:01JS0PL000000000000000000",
  "kind": "policy",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "workspace-default-policy",
  "retention": {
    "messages_days": 3650,
    "candidate_memories_days": 90
  },
  "default_visibility": "workspace",
  "redaction_mode": "tombstone",
  "encryption_profile": "workspace-envelope-v1",
  "allow_external_relays": true
}
```

`policy` SHOULD cover at least:

- retention
- default visibility
- redaction display
- encryption profile
- relay / blob / export defaults

## 21. Invite

In a decentralized collaboration protocol, "how another principal joins a workspace" cannot be left to product-private invite links.

Contrix should support an explicit `invite` object:

```json
{
  "id": "cx:invite:01JS0IV000000000000000000",
  "kind": "invite",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject_did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "subject_handle": "alice.example.com",
  "proposed_role": "contributor",
  "proposed_grant_refs": [
    "cx:grant:01JS0GR000000000000000000"
  ],
  "expires_at": "2026-05-01T00:00:00Z",
  "status": "pending"
}
```

The semantics of `invite` are:

- it is a join-bootstrap object
- it is not itself a capability grant
- after the invite is accepted, the related grants enter the effective set

## 22. Read Marker

A human-friendly collaboration system needs durable read state; otherwise inbox, thread, and chat views cannot converge reliably.

The draft therefore recommends actor-private `read_marker` objects:

```json
{
  "id": "cx:read:01JS0RD000000000000000000",
  "kind": "read_marker",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "owner": "did:web:alice.example.com",
  "scope_kind": "channel",
  "scope_ref": "cx:channel:01JS1000000000000000000000",
  "last_seen_message_ref": "cx:message:01JS1000000000000000000002",
  "last_seen_hlc": "2026-04-22T08:31:03.221Z-0007-did:web:alice.example.com",
  "updated_at": "2026-04-22T08:40:00Z"
}
```

`read_marker` SHOULD:

- be visible only to its owner by default
- support scopes such as channel / topic / inbox / view
- sync as durable state across multiple devices

## 23. Notification

Notifications are required for human-facing UX, but they should not become canonical truth objects.

The initial recommendation is therefore:

- `notification` is a derived inbox object
- it is derived from mentions, assignments, invites, run failures, memory review events, and similar signals
- it may be materialized by an index or relay, while canonical truth remains the underlying source object and op

Example:

```json
{
  "id": "cx:notif:01JS0NF000000000000000000",
  "actor": "did:web:alice.example.com",
  "notification_kind": "mention",
  "source_ref": "cx:message:01JS1000000000000000000002",
  "target_ref": "cx:topic:01JS1000000000000000000001",
  "delivery_state": "unread",
  "created_at": "2026-04-22T08:31:05Z"
}
```

## 24. Derived Data

The following should not be treated as canonical truth objects:

- embedding vectors
- inverted search indexes
- local UI layout caches
- temporary sorting caches
- LLM context windows
- typing/presence transient state

These belong to derived or ephemeral layers.

## 25. Initial Design Decisions

The current draft recommends fixing:

- all objects explicitly belong to a workspace
- `item` is the main business object
- `channel/topic/message` are formal conversation objects
- `comment` is a durable object-local explanation object
- `view` is a projection definition
- `run` is an execution-trace object
- `memory` is a long-term knowledge object
- `schema/policy` are formal objects
- `invite` is explicit join bootstrap
- `read_marker` is durable actor-private state
- `notification` is derived, not canonical truth

## 26. Further Work

The next round still needs:

- a formal schema-object format
- a formal schema for policy objects
- an invite / join / leave state machine
- a formal query surface for read markers and notifications
- a standard checklist structure
- a rich-text block structure for messages
- history visibility rules for topics/channels
- memory supersession/invalidation semantics
