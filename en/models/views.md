# View Model Draft

## 1. Goal

Contrix must remain human-friendly, so the protocol must support natural projections into:

- boards, lists, tables, calendars, and Gantt views
- timelines, activity feeds, chat, topic forums, and single-thread discussions
- graphs and trees
- documents
- dashboards, review queues, inboxes, notifications, memory reviews, and agent run views

These presentation modes are facet-composition `renderer` values, not new protocol roots. All of them must come from the same substrate:

```txt
Space + Actor + Entity + Relation + Event
```

Views observe and organize this collaboration graph. They do not define a separate truth source.

## 2. Design Principles

### 2.1 Views Are Not the Truth of Objects

Views do not carry the canonical truth of underlying objects.

### 2.2 The Same Object May Appear in Multiple Views

A task Entity may appear in:

- `collection` projection + `renderer=board` + `item_render=card`
- `collection` projection + `renderer=row`
- `collection` projection + `renderer=calendar`
- a `timeline` thread anchor

A message Entity may appear in:

- `timeline` projection + `renderer=chat`
- `timeline` projection + `renderer=thread`
- `timeline` projection + `renderer=timeline`

### 2.3 Entity Facets Are the Capability Center

The protocol must not let a View kind implicitly grant object capabilities. Whether an Entity can act as a container, be replied to, be scheduled, be assigned, or enter a review queue MUST be declared by Entity `facets` or by the Space schema profile:

- `container`: can contain, order, and move other Entities.
- `replyable`: can be replied to, forming thread/chat/forum projections.
- `schedulable`: has a time window for calendar/gantt projections.
- `assignable`: can be assigned to an actor/team/agent.
- `stateful`: has a controlled state machine.
- `rankable`: has stable manual ordering.
- `reviewable`: can enter review or moderation queues.
- `notifiable`: can derive inbox/notification/read state.
- `documentable`: can act as a document or section root.
- `renderable`: declares allowed default render surfaces.

`entity_type` is a semantic label; facets define field sets, allowed relations, standard operations, and projection capabilities. `kanban`, `table`, `thread`, `chat`, `review_queue`, and similar product shapes SHOULD be described as facet compositions rather than View-defined object capabilities.

### 2.4 Few Response Families, Many Renderers

Views still need machine-verifiable response families. The protocol keeps five `View.kind` values as response families:

- `collection`
- `timeline`
- `graph`
- `document`
- `composite`

These `kind` values constrain response contracts, cursors, and frontiers only. They do not define object capabilities. New product shapes SHOULD add a renderer / facet profile first, not a new top-level `kind`.

### 2.5 Shared / Private / System Must Coexist

The first version should support:

- `shared`
- `private`
- `system`

### 2.6 Unified Context Timeline

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
  "kind": "collection",
  "renderer": "board",
  "title": "Release Flow",
  "visibility": "shared",
  "query": {
    "facets": ["stateful", "rankable"],
    "filters": [
      { "field": "archived", "op": "neq", "value": true }
    ]
  },
  "collection": {
    "item_facets": ["stateful", "rankable"],
    "item_render": "card",
    "item_order_by": [
      { "field": "fields.rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "field",
      "field": "fields.status",
      "lanes": [
        { "key": "todo", "title": "Todo", "rank": "F" },
        { "key": "in_progress", "title": "In Progress", "rank": "V" },
        { "key": "done", "title": "Done", "rank": "k" }
      ],
      "hidden_count_policy": "omit"
    }
  },
  "visible_fields": [
    "title",
    "assignees",
    "due_at",
    "labels"
  ]
}
```

## 4. Standard `kind` and `renderer`

Each top-level `kind` maps to a machine-verifiable response profile; object capabilities come from facets. `layout` is only a UI hint and never replaces the profile config.

| Core kind | Common renderers | Required config | Standard projection response |
| --- | --- | --- | --- |
| `collection` | `board`, `row`, `table`, `calendar`, `gantt`, `custom` | `collection` | `CollectionProjectionResponse` |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `custom` | `timeline`; conversation renderers also require `conversation` or anchor/relation | `TimelineProjectionResponse` |
| `graph` | `graph`, `tree` | `graph` | `GraphProjectionResponse` |
| `document` | `document` | `document` | `DocumentProjectionResponse` |
| `composite` | `dashboard` | `dashboard` | `CompositeProjectionResponse` |

For non-raw projections, Index / AppView MUST return `view_id`, `frontier`, and the standard response for the core primitive. Clients must not treat an arbitrary object array as a standard View projection.

A Kanban card, table row, calendar event, and review queue item are different render surfaces over `collection.items[*]`. A `thread` or `message` Entity MAY be displayed as a Kanban card when it satisfies `query.facets` / `collection.item_facets` and authorization trimming.

## 5. Query Model

Views should use structured queries to define object scope.

### 5.1 Board Query Example

```json
{
  "facets": ["stateful", "rankable"],
  "filters": [
    { "field": "fields.status", "op": "in", "value": ["todo", "in_progress"] },
    { "field": "archived", "op": "eq", "value": false }
  ]
}
```

### 5.2 Chat Query Example

```json
{
  "facets": ["replyable", "renderable"],
  "filters": [
    { "field": "fields.redacted", "op": "eq", "value": false }
  ],
  "relation": {
    "kind": "belongs_to",
    "direction": "out",
    "target_entity_id": "cx:entity:01JS1000000000000000000000"
  }
}
```

### 5.3 Topic Query Example

```json
{
  "facets": ["replyable", "stateful"],
  "filters": [
    { "field": "fields.status", "op": "eq", "value": "open" }
  ]
}
```

### 5.4 Notification Query Example

```json
{
  "facets": ["notifiable"],
  "filters": [
    { "field": "derived.notification_state", "op": "eq", "value": "unread" },
    { "field": "derived.recipient", "op": "eq", "value": "did:web:alice.example.com" }
  ]
}
```

### 5.5 Dependency Graph Query Example

```json
{
  "facets": ["stateful"],
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
  "facets": ["stateful", "replyable", "reviewable", "documentable"],
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
      "cx.container.move_item",
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

- Entities with explicit facets, typically `container` board / collection entities and `renderable` item entities matching `collection.item_facets`
- Relation `relation_kind = "contains"` / `belongs_to`, explicitly selected by the View config rather than inferred from local defaults
- the protocol response family is `kind = "collection"`; `renderer = "board"` / card renderer only selects the board presentation profile

`board`, `collection`, and `task` are common semantic labels, but they do not grant behavior by themselves. `card` is not a core `entity_type`; it is an item render surface. Kanban is not a separate protocol-level projection family; it is `CollectionProjectionResponse` rendered with `renderer="board"` and `item_render="card"` from the Entity / Relation graph rather than from some UI-private array-of-columns structure.

For v1 interoperability, board-rendered collection views MUST use the machine-verifiable `collection` config in `view.schema.json` with `renderer="board"` and `item_render="card"`. Field-value boards use `cx.field_position.move` so the group value and rank converge atomically; collection boards MUST explicitly declare `collection.grouping.item_relation_kind` and use `cx.container.move_item` within a `scope_container_id` so one item has one active position per board scope. Projection item positions are discriminated: field-value positions use `model="field_value"`, while relation-backed positions use `model="relation"` and include `scope_container_id`, `container_id`, `relation_kind`, `relation_id`, and `rank`. WIP enforcement for `reject` and `require_review` MUST use the untrimmed canonical active column membership, while Index / AppView collection projections rendered as boards return authorization-trimmed `groups[]` with per-group cursors; `authorized_estimate` and `authorized_exact` counts are visibility-trimmed unless a separate aggregate-count policy grants hidden membership counts.

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
- standard `collection/timeline/graph/document/composite` core view kinds
- `kanban/chat/forum/thread/inbox/notifications` and related product shapes as renderers, not protocol roots or new projection families
- shared/private/system coexistence

## 13. Further Work

The next round still needs:

- a formal query JSON schema
- default card/chat/thread rendering conventions
- generation rules for system views

