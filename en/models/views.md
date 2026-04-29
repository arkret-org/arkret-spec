# View Model Draft

## 1. Goal

Contrix must remain human-friendly, so the protocol must support natural projections into:

- boards
- lists
- tables
- calendars
- timelines
- graphs
- activity feeds
- chat
- topic forums
- single-thread discussions
- memory review queues
- agent run views

All of these presentation modes must come from the same substrate:

```txt
Space + Actor + Entity + Relation + Event
```

Views observe and organize this collaboration graph. They do not define a separate truth source.

## 2. Design Principles

### 2.1 Views Are Not the Truth of Objects

Views do not carry the canonical truth of underlying objects.

### 2.2 The Same Object May Appear in Multiple Views

A task Entity may appear in:

- a Kanban board
- a list
- a calendar
- a thread anchor

A message Entity may appear in:

- a chat timeline
- a topic thread
- an activity feed

### 2.3 Shared / Private / System Must Coexist

The first version should support:

- `shared`
- `private`
- `system`

### 2.4 Unified Context Timeline

One work item may require board, graph, and chat perspectives at the same time.  
This should be supported by a context projection instead of splitting canonical meaning:

- anchor on one entity (`anchor_entity_id`);
- fetch related entities, relations, and timeline events together;
- sort deterministically by `hlc`, with `event_id` as tie-break;
- render as a single timeline and allow the UI to segment cards/edges/messages.

Canonical truth is still `Event + Entity + Relation`. A `View` only defines read-time organization.

## 3. View Object

Suggested fields:

```json
{
  "id": "cx:view:01JS0VW000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "created_by": "did:web:acme.example.com",
  "kind": "kanban",
  "name": "Release Flow",
  "visibility": "shared",
  "query": {
    "entity_types": ["task", "issue"],
    "filters": [
      { "field": "archived", "op": "neq", "value": true }
    ]
  },
  "order_by": [
    { "field": "fields.rank", "direction": "asc" }
  ],
  "visible_fields": [
    "title",
    "assignees",
    "due_at",
    "labels"
  ]
}
```

## 4. Standard `kind` Values

### 4.1 Work-object Views

- `kanban`
- `list`
- `table`
- `calendar`
- `timeline`
- `graph`
- `tree`
- `gantt`
- `matrix`
- `document`
- `dashboard`

### 4.2 Conversation Views

- `chat`
- `forum`
- `thread`
- `activity`
- `inbox`
- `notifications`

### 4.3 Review and Agent Views

- `review_queue`
- `memory_review`
- `agent_runs`
- `context_timeline`

## 5. Query Model

Views should use structured queries to define object scope.

### 5.1 Board Query Example

```json
{
  "entity_types": ["task", "issue"],
  "filters": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "archived", "op": "eq", "value": false }
  ]
}
```

### 5.2 Chat Query Example

```json
{
  "entity_types": ["message"],
  "filters": [
    { "field": "fields.redacted", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "belongs_to",
    "to_entity_id": "cx:entity:01JS1000000000000000000000"
  }
}
```

### 5.3 Topic Query Example

```json
{
  "entity_types": ["topic"],
  "filters": [
    { "field": "fields.status", "op": "eq", "value": "open" }
  ]
}
```

### 5.4 Notification Query Example

```json
{
  "entity_types": ["message", "task", "invite", "run", "memory"],
  "filters": [
    { "field": "derived.notification_state", "op": "eq", "value": "unread" },
    { "field": "derived.recipient", "op": "eq", "value": "did:web:alice.example.com" }
  ]
}
```

### 5.5 Dependency Graph Query Example

```json
{
  "entity_types": ["task"],
  "relation": {
    "kind": "depends_on",
    "direction": "out",
    "depth": 4
  }
}
```

### 5.6 Context Timeline Query Example

Aggregate status updates, relations, messages, and reviews for one task context:

```json
{
  "anchor_entity_id": "cx:entity:01JS0TASK000000000000000000",
  "entity_types": ["task", "message", "topic", "memory", "relation"],
  "filters": [
    { "field": "fields.archived", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "contains",
    "direction": "both",
    "source_entity_id": "cx:entity:01JS0TASK000000000000000000",
    "depth": 3
  },
  "order_by": [
    { "field": "event_hlc", "direction": "asc" }
  ],
  "context": {
    "event_kinds": [
      "cx.entity.update",
      "cx.relation.create",
      "cx.relation.move",
      "cx.message.create",
      "cx.task.assign",
      "cx.redaction",
      "cx.memory.create"
    ],
    "relation_kinds": [
      "contains",
      "assigned_to",
      "depends_on",
      "replies_to",
      "mentions"
    ],
    "event_tiebreak": "event_id"
  }
}
```

Context timeline requirements:

- `event_hlc` is the primary order key. If missing, fallback to `created_at` with `timestamp_untrusted`.
- `event_id` MUST be used as deterministic tie-break.
- unauthorized entities/relations MUST be filtered only; do not leak existence by error shape.
- repeated queries under same `space_frontier` and authorization context MUST be deterministic in order and filtered set.

## 6. Grouping, Ordering, and Visibility

### 6.1 `group_by`

The first version should support:

- `status`
- `assignee`
- `priority`
- `memory_kind`
- `run_status`
- `channel`
- `topic_status`
- `custom:<field_name>`

### 6.2 `order_by`

The first version should support:

- `rank`
- `created_at`
- `updated_at`
- `due_at`
- `priority`
- `started_at`
- `ended_at`
- `last_message_at`

### 6.3 `visible_fields`

These define the shared minimum display contract. Clients may locally enhance the display as long as authorization is respected.

## 7. Standard Projection Rules

### 7.1 Kanban

The canonical input for Kanban views should be:

- `entity_type = "board"`
- `entity_type = "collection"`
- `entity_type = "task"` or another work object type
- `kind = "contains"` / `belongs_to`
- `kind = "kanban"`

rather than some UI-private array-of-columns structure.

### 7.2 Chat

The canonical input for chat views should be:

- `channel`
- `topic`
- `message`
- `belongs_to` / `replies_to` / `mentions` Relations

### 7.3 Topic

The canonical input for thread/topic views should be:

- `topic`
- `message`
- `attached_to` / `belongs_to` / `replies_to` Relations

### 7.4 Graph

Graph views should use Entity types plus one or more Relation types, directions, and expansion depths.

### 7.5 Tree

Tree views should use `contains` or `belongs_to` Relations with a root Entity and expansion depth.

## 8. Human-friendliness Requirements

Implementations SHOULD guarantee at least:

1. a default title and summary for each core object
2. task Entity projections that work naturally as cards or rows
3. message Entity projections that work naturally as bubbles or timeline rows
4. topic Entity projections that work naturally as forum-thread rows
5. memory Entity projections that work naturally as review rows or graph nodes
6. run Entity projections that work naturally as timeline rows or activity blocks
7. notification projections that work naturally as inbox rows or badge sources

## 9. Shared / Private / System

### 9.1 Shared

Belongs to the space and is visible to the team.

### 9.2 Private

Stored locally only, or in an actor-private repo.

### 9.3 System

Automatically generated by the protocol or product, for example:

- Assigned to Me
- Needs Review
- Candidate Memories
- Failed Agent Runs
- Mentioned Messages
- Notifications
- Unread Topics

## 10. View Authorization

Creating and updating shared views should be controlled by capabilities.

If a view query matches objects the user is not authorized to read, the returned result MUST be filtered.

## 11. View Degradation and Compatibility

When schemas or fields change, views should degrade gracefully instead of breaking data.

Examples:

- show a warning when a field disappears
- show a tombstone when a message was redacted
- skip missing relation edges in a graph

## 12. Initial Design Decisions

The current draft recommends fixing:

- views as independent objects
- structured JSON queries first
- standard `kanban/chat/forum/thread/inbox/notifications` and related view kinds
- boards and chat as standard projections rather than protocol roots
- shared/private/system coexistence

## 13. Further Work

The next round still needs:

- a formal query JSON schema
- default card/chat/thread rendering conventions
- generation rules for system views

