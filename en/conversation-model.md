# Conversation Model Draft

## 1. Goal

Contrix is not a chat-first protocol, but it must formally support:

- channel-style chat
- topic-style discussion
- threads/replies
- `@mention`
- edits
- recalls
- reactions

These capabilities must also interoperate with boards, items, runs, and memories rather than living in a separate silo.

## 2. Design Principles

### 2.1 Conversation Is Part of the Object Graph

Conversation is not a separate universe. Conversation objects must link to:

- spaces
- boards
- items
- runs
- memories

### 2.2 Conversation Must Not Become the Root Model Again

Contrix does not go back to a room/message-first design.

The correct approach is:

- formal conversation objects
- while keeping space/object-graph/repo-ops as the protocol root

### 2.3 Separate Durable Notes from Timeline Messages

Both `comment` and `message` exist, but with different roles:

- `comment`: a durable object-level note / review / approval note
- `message`: a timeline message inside a channel or topic

## 3. Conversation Object Set

The current draft introduces:

- `channel`
- `topic`
- `message`

and defines `reaction` as standard derived state on top of messages.

## 4. Channel

Channel is a long-lived conversation space.

Suitable for:

- team chat
- board discussion areas
- organization-wide announcement streams
- agent execution broadcast streams

Suggested fields:

```json
{
  "id": "cx:channel:01JS1000000000000000000000",
  "type": "entity",
  "schema": "cx.schema.entity.v1",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "channel",
  "title": "release-chat",
  "content": {
    "format": "markdown",
    "text": "General release coordination chat"
  },
  "fields": {
    "channel_kind": "chat",
    "visibility": "space",
    "default_topic_mode": "inline",
    "archived": false
  }
}
```

Suggested `channel_kind` values:

- `chat`
- `announce`
- `support`
- `activity`

## 5. Topic

Topic is a thread or discussion topic object.

It may:

- belong to a channel
- or anchor directly to another object

Suggested fields:

```json
{
  "id": "cx:topic:01JS1000000000000000000001",
  "type": "entity",
  "schema": "cx.schema.entity.v1",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "topic",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "anchor_ref": "cx:entity:01JS0IT000000000000000000",
  "title": "Legal review follow-up",
  "fields": {
    "topic_kind": "thread",
    "status": "open"
  },
  "created_by": "did:web:alice.example.com"
}
```

`anchor_ref` may point to:

- `space`
- `board`
- `entity`
- `run`
- `memory`

This means:

- an item may have a default topic
- a run may also have its own execution topic

## 6. Message

Message is the atomic timeline object inside a channel or topic.

Suggested fields:

```json
{
  "id": "cx:message:01JS1000000000000000000002",
  "type": "entity",
  "schema": "cx.schema.entity.v1",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "entity_type": "message",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "topic_id": "cx:topic:01JS1000000000000000000001",
  "created_by": "did:web:alice.example.com",
  "content": {
    "format": "markdown",
    "text": "@bob please confirm the legal risk for this item."
  },
  "reply_to_ref": null,
  "state": "active",
  "fields": {
    "revision_root": "cx:message:01JS1000000000000000000002"
  }
}
```

## 7. `@mention` Design

### 7.1 Separate the UI from the Protocol Representation

The UI may let users type:

- `@alice.example.com`
- `@bob`
- `@some item title`

But the protocol must not store plain text only.

### 7.2 Canonical Storage

The canonical protocol representation SHOULD store:

- `mentions[].kind = principal | object`
- `mentions` Relations pointing to DID-backed actor profile Entities or stable Entity IDs

This guarantees:

- handle migration does not break historical mentions
- object renames do not break historical mentions

### 7.3 Mention Notifications

Mention notifications should be derived results rather than part of the message truth itself.

That means:

- messages store mention references
- inbox/notification state is derived by indexes or relays

## 8. Edit, Recall, and Reaction

### 8.1 Edit

Editing uses `cx.message.revise` to form a revision chain.

Principles:

- do not silently rewrite history
- show the newest revision by default
- expose revision chains to audit views

### 8.2 Recall

Recall uses `message.redact`.

Principles:

- show a tombstone in default views
- do not continue leaking the body in normal views
- do not promise global physical erasure

### 8.3 Reaction

Reactions should be expressed via separate ops:

- `cx.reaction.add`
- `cx.reaction.remove`

Reduction rule:

- use `(message_id, actor, reaction_key)` as the OR-Set key

## 9. Difference Between Comments and Messages

To avoid semantic confusion, Contrix should state clearly:

- `comment` is better for object review, approval notes, and audit-facing annotations
- `message` is better for continuous chat, thread conversation, and channel timelines

If an item needs both:

- use `comment` for review remarks
- use `topic/message` for lightweight discussion

## 10. Sync Model

### 10.1 Chat Mode

Recommended sync:

- channel metadata
- open topics
- the most recent N messages
- live message/reaction/redaction increments

### 10.2 Topic Mode

Recommended sync:

- topic metadata
- anchor object
- the most recent N messages
- reverse backfill cursor

### 10.3 Board Mode

Recommended sync:

- board/item current state
- the discussion summary for the currently opened item
- recent comments and recent message summaries

## 11. Conflict and Convergence

### 11.1 Message Creation

Message creation is append-only.

Suggested timeline ordering:

1. `hlc`
2. `actor`
3. `actor_seq`
4. `op_id`

### 11.2 Message Edit

Concurrent revisions coexist in the revision chain.  
The default view shows the latest visible revision.

### 11.3 Message Recall

If revision and redaction are concurrent:

- redaction wins in default views
- audit views may still expose the full history

### 11.4 Redaction Before the Original Message Arrives

Receivers SHOULD keep dangling redactions and apply them once the target message arrives.

## 12. Private and Ephemeral Signals

The following should not be modeled as durable shared objects:

- typing
- transient presence
- local drafts

They may be:

- ephemeral relay signals
- or actor-private state

## 13. Initial Design Decisions

The current draft recommends fixing:

- `channel/topic/message` as formal conversation objects
- `@mention` as structured DID/entity references and `mentions` Relations
- edits as revision chains
- recalls as redaction/tombstone semantics
- reactions converging through OR-Set rules
- board/chat/topic modes sharing one sync protocol with different profiles

## 14. Further Work

The next round still needs:

- a rich-text block structure
- attachment embedding semantics inside messages
- channel-member visibility and history rules
- a formal inbox/notification schema
