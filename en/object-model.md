# Object Model Draft

## 1. Goal

The Contrix New object model must support human collaboration, cross-organization work, boards, chat, topic threads, trees, dependency graphs, AI-agent runs, and long-term agent memory.

The protocol therefore centers on a **collaboration graph + event log + view projections**, not on rooms, columns/cards, or message timelines as the root abstraction.

The core protocol abstractions are:

```txt
Space
Actor
Entity
Relation
Event
View
```

In one sentence:

> In a Space, Actors produce Events that change a graph of Entities and Relations; Views project that graph into chat, boards, tables, calendars, trees, graphs, Gantt charts, review queues, and other interfaces.

## 2. Design Principles

### 2.1 Stable IDs Are Separate from Display Names

Protocol references MUST use stable IDs rather than titles, display names, handles, or URL paths.

### 2.2 Entities Belong to Spaces, Not UIs

The same Entity may appear in multiple Views and may be used by both humans and agents.

Tasks, messages, documents, comments, runs, memories, decisions, and file metadata are all Entities with different `entity_type` values.

### 2.3 Relations Are First-class

Cross-object structure MUST NOT be hidden entirely inside Entity fields.

Dependencies, containment, replies, references, derivation, assignment, mentions, and subscriptions SHOULD be represented as Relations.

### 2.4 Events Are Facts

Events describe what happened. They should not be silently overwritten.

Current state may be reduced from authorized Events/operations and may be materialized by indexes or appviews, but canonical history MUST come from the authorized event/operation set.

### 2.5 Views Are Projections

Boards, chat, tables, calendars, trees, graphs, Gantt charts, and inboxes are Views.

Views do not own data. A View defines query scope, relation expansion, grouping, sorting, layout, visible fields, and interaction hints.

### 2.6 Schemas Constrain the Abstraction

The protocol allows open Entity types, but not uncontrolled JSON sprawl.

Spaces SHOULD register EntitySchema and RelationSchema records to constrain fields, relations, actions, and default views.

## 3. ID Scheme

The initial draft recommends prefixed stable IDs with ULID-like suffixes:

- `cx:space:<ulid>`
- `cx:actor:<ulid>`
- `cx:entity:<ulid>`
- `cx:rel:<ulid>`
- `cx:event:<ulid>`
- `cx:view:<ulid>`
- `cx:schema:<ulid>`
- `cx:policy:<ulid>`
- `cx:invite:<ulid>`
- `cx:read:<ulid>`

Semantic prefixes MAY exist as compatibility aliases, but the protocol layer SHOULD normalize them to Entity IDs:

- `cx:task:<ulid>` means `entity_type = "task"`
- `cx:message:<ulid>` means `entity_type = "message"`
- `cx:doc:<ulid>` means `entity_type = "document"`
- `cx:run:<ulid>` means `entity_type = "run"`
- `cx:mem:<ulid>` means `entity_type = "memory"`

## 4. Core Object Set

The protocol core object set is:

- `space`
- `actor`
- `entity`
- `relation`
- `event`
- `view`
- `schema`
- `policy`
- `invite`
- `read_marker`

The following are no longer protocol roots. They are standard Entity or View types:

- board
- collection
- item/task
- channel
- topic
- message
- comment
- attachment
- run
- memory
- notification

## 5. Shared Envelope

Canonical objects SHOULD share these base fields:

```json
{
  "id": "cx:entity:01JS0000000000000000000000",
  "kind": "entity",
  "space_id": "cx:space:01JS0000000000000000000000",
  "created_at": "2026-04-22T08:00:00Z",
  "created_by": "did:web:alice.example.com",
  "updated_at": "2026-04-22T08:05:00Z",
  "updated_by": "did:web:agent.example.com",
  "visibility": "space",
  "archived": false,
  "tombstoned": false,
  "schema_ref": "cx:schema:01JS0SC000000000000000000",
  "version": 7
}
```

## 6. Space

Space is the collaboration, replication, authorization, schema, and policy boundary.

```json
{
  "id": "cx:space:01JS0SP000000000000000000",
  "kind": "space",
  "space_type": "project",
  "owner": "did:web:acme.example.com",
  "name": "Acme Delivery Space",
  "visibility": "private",
  "parent_space_id": null,
  "default_policy_ref": "cx:policy:01JS0PL000000000000000000",
  "default_schema_refs": ["cx:schema:01JS0SC000000000000000000"],
  "default_view_id": "cx:view:01JS0VW000000000000000000"
}
```

## 7. Actor

Actor is the subject that performs actions. It may be a user, agent, system, integration, or team.

Actor identity is defined by [identity.md](./identity.md). Actor references in protocol data MUST use DIDs or stable actor IDs.

When an Actor needs to appear inside the collaboration graph, implementations SHOULD create an `entity_type = "actor_profile"` Entity mirror. Relations such as `assigned_to`, `mentions`, and `contains` can then consistently point to Entities.

## 8. Entity

Entity is the primary collaboration object. It represents anything that can be created, discussed, related, changed, tracked, authorized, or projected.

```json
{
  "id": "cx:entity:01JS0EN000000000000000000",
  "kind": "entity",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "task",
  "schema_version": 1,
  "title": "Finalize onboarding copy review",
  "content": {
    "format": "markdown",
    "text": "Coordinate product, design, legal, and agent-generated suggestions."
  },
  "fields": {
    "status": "in_progress",
    "rank": "mV",
    "priority": "high",
    "due_at": "2026-04-28T00:00:00Z",
    "labels": ["launch", "copy"]
  },
  "created_by": "did:web:alice.example.com",
  "created_at": "2026-04-22T08:00:00Z",
  "updated_by": "did:web:agent.copy.example.com",
  "updated_at": "2026-04-22T08:05:00Z"
}
```

Initial standard `entity_type` values include:

- `space_profile`
- `actor_profile`
- `task`
- `issue`
- `goal`
- `request`
- `decision`
- `note`
- `document`
- `comment`
- `message`
- `channel`
- `topic`
- `board`
- `collection`
- `attachment`
- `run`
- `memory`
- `schema`
- `policy`
- `invite`
- `read_marker`

Entity fields SHOULD describe intrinsic object properties. Cross-object semantics SHOULD use Relations.

## 9. Relation

Relation represents a semantic link between two Entities.

```json
{
  "id": "cx:rel:01JS0RL000000000000000000",
  "kind": "relation",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "relation_type": "depends_on",
  "from_entity_id": "cx:entity:01JS0TASK0000000000000000",
  "to_entity_id": "cx:entity:01JS0TASK0000000000000001",
  "directed": true,
  "fields": {
    "strength": "hard"
  },
  "created_by": "did:web:alice.example.com",
  "created_at": "2026-04-22T08:10:00Z"
}
```

Initial standard `relation_type` values:

- `contains`
- `belongs_to`
- `replies_to`
- `references`
- `depends_on`
- `blocks`
- `duplicates`
- `relates_to`
- `assigned_to`
- `mentions`
- `derived_from`
- `subscribes`
- `supersedes`
- `attached_to`

## 10. Event

Event is the collaboration fact and audit record.

```json
{
  "id": "cx:event:01JS0EV000000000000000000",
  "kind": "event",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "event_type": "entity.updated",
  "target": {
    "kind": "entity",
    "id": "cx:entity:01JS0EN000000000000000000"
  },
  "payload": {
    "changes": {
      "fields.status": {
        "old": "todo",
        "new": "in_progress"
      }
    }
  },
  "occurred_at": "2026-04-22T08:20:00Z",
  "recorded_at": "2026-04-22T08:20:01Z",
  "transaction_id": "cx:txn:01JS0TX000000000000000000"
}
```

Low-level Events SHOULD use generic forms such as `entity.created`, `entity.updated`, `relation.created`, `relation.deleted`, `view.created`, and `view.updated`.

Business events such as `message.sent`, `task.assigned`, or `dependency.added` MAY exist as semantic sugar, but they MUST be reducible to `entity.*` or `relation.*`.

## 11. Command and Event

Clients SHOULD submit Commands. The receiver validates the Command, emits Events, reduces current state, and notifies Views.

```txt
Command -> Validate -> Event -> Reduce Current State -> Notify Views
```

## 12. View

View is a projection object. See [views.md](./views.md).

Standard `view_type` values include:

- `chat`
- `kanban`
- `table`
- `list`
- `calendar`
- `gantt`
- `graph`
- `tree`
- `timeline`
- `feed`
- `document`
- `matrix`
- `dashboard`
- `inbox`
- `review_queue`

## 13. Standard Semantic Mapping

### 13.1 Board / Collection / Card

Boards are represented as:

- board: `entity_type = "board"`
- collection/lane: `entity_type = "collection"`
- card/task: `entity_type = "task"` or another work object type
- board contains collection: `board --contains--> collection`
- collection contains task: `collection --contains--> task`
- Kanban display: `view_type = "kanban"`

### 13.2 Chat / Channel / Topic / Message

Chat is represented as:

- channel: `entity_type = "channel"`
- topic/thread: `entity_type = "topic"`
- message: `entity_type = "message"`
- topic belongs to channel: `topic --belongs_to--> channel`
- message belongs to topic or channel: `message --belongs_to--> topic`
- message replies to message: `message --replies_to--> message`
- chat display: `view_type = "chat"` or `view_type = "thread"`

Mentions MUST also be represented as structured `mentions` Relations.

### 13.3 Dependency Graphs and Trees

Dependency graphs use task Entities plus `depends_on` Relations.

Trees use `contains` or `belongs_to` Relations with a `tree` View.

### 13.4 Run / Memory

AI-agent objects are Entities:

- run: `entity_type = "run"`
- memory: `entity_type = "memory"`
- run input: `run --references--> source`
- memory source: `memory --derived_from--> message/comment/run/document`

Memory is not an embedding chunk. Vector indexes are derived data.

## 14. Schema

Schemas SHOULD define Entity types, field types, allowed Relations, default Views, and action semantics.

## 15. Policy

Policy is a formal object. It SHOULD cover retention, default visibility, redaction display, encryption profile, relay/blob defaults, and export defaults.

## 16. Invite, Read Marker, and Notification

Invite is the explicit bootstrap object for joining a Space. It is not itself a capability grant.

Read marker is actor-private durable state.

Notification SHOULD be a derived inbox projection from Events, Entities, and Relations, not canonical truth.

## 17. Derived Data

The following SHOULD NOT be canonical truth objects:

- embedding vectors
- search indexes
- local UI layout cache
- temporary ordering cache
- LLM context windows
- typing/presence signals
- notification materialization

## 18. Initial Decisions

The draft fixes:

- the protocol root as `Space + Actor + Entity + Relation + Event + View`
- Entity as the collaboration object
- Relation as a first-class object
- Event as the fact and audit root
- View as projection
- Command as intent and Event as fact
- Schema as the guardrail against unstructured JSON sprawl
- board, chat, task, message, run, and memory as semantic-layer concepts rather than protocol roots
