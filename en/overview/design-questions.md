# Design Questions And Decisions

## 1. Purpose

This document lists the protocol questions first, then records the chosen answers.

The reason is simple: if the protocol does not first define which questions it is actually solving, the object model, sync model, authorization model, and view model will drift apart and collapse into a vague "sort of a board, sort of a chat, sort of not a protocol" state.

## 2. Question Inventory and Chosen Decisions

### 2.1 What Is the Root Model of the Protocol?

Question:

- Is it chat-first?
- board-first?
- database-first?

Decision:

- Contrix is **space-first + entity-graph-first + event-first**.
- Chat, topic, Kanban, tree, graph, and Gantt are presentation profiles over the same collaboration graph. Protocol-level projection families are defined only by View `kind`.
- The protocol root is not a room, message, task, or board. It is `Space + Actor + Entity + Relation + Event + View`.

### 2.2 If the System Should Render as a Board, What Is the Canonical Data Shape?

Question:

- Is the underlying model just "columns and cards"?
- Or is there a more stable substrate?

Decision:

- The board substrate is not "column arrays + card arrays".
- The canonical substrate is `Entity + Relation + View`; column arrays and card arrays are only derived projections.
- `board`, `collection`, `task`, `message`, and `topic` are semantic Entity type labels. They do not automatically grant container, drag, reply, or card-rendering behavior.
- Entity capabilities come from explicit `facets` or the Space schema profile. For example, board / collection objects typically need `container`; card-renderable objects typically need `renderable`; drag ordering typically needs `rankable` or relation rank.
- In complex boards, a board contains column collections through explicit `contains` Relations, and a column collection contains Entities matching `collection.item_facets` through explicit `contains` Relations.
- `card` is not a core `entity_type`; it is an item render surface declared by `collection.item_render="card"`.
- Kanban is not a separate protocol-level projection family, nor an independent projection contract created by `kind + renderer`. It is a board display of `CollectionProjectionResponse`, expressed by `renderer = "board"`, `collection.item_render = "card"`, and `collection.grouping`.

### 2.3 If the Protocol Should Support Chat or Topic Mode, How Should That Work?

Question:

- Is `comment` enough?
- Or are formal conversation objects required?

Decision:

- The protocol defines `channel/topic/message` as standard semantic labels, not new protocol roots; conversation behavior still comes from facets such as `replyable`, `renderable`, and `notifiable`, or from the Space schema profile.
- `channel` is a long-lived conversation space.
- `topic` is a thread/topic that may anchor through Relations to `space / board / task / run / memory`.
- `message` is a timeline message.
- `comment` remains, but it is positioned as a durable object-local review/note, not the generic chat timeline primitive.

### 2.4 How Do Boards and Chat Connect?

Question:

- Is item discussion stored as comments or chat threads?
- What is the relation between boards and topics?

Decision:

- A task Entity may have its own default `topic`.
- A board Entity may have one or more `channel`s and `topic`s.
- A `topic` may anchor to `task / run / memory / board`.
- Humans should be able to inspect an item in a board and jump directly into the same item's thread/chat.

### 2.5 Should `@user` Be Supported?

Question:

- Is plain text `@alice` enough?
- What happens if the handle changes later?

Decision:

- The protocol supports `@user` and `@object`.
- The UI may accept `@handle` or `@title`.
- The canonical protocol representation MUST store structured `mentions` Relations.
- Principal mentions always reference DIDs.
- Object mentions always reference stable Entity IDs.
- Handle migration does not change historical mention targets.

### 2.6 Should Message Editing Be Supported?

Question:

- If a user sends the wrong content, can it be changed?

Decision:

- Yes.
- Editing uses `message.revise` to build a revision chain.
- The default view shows the latest visible revision.
- Audit views may expose the revision chain.

### 2.7 Should Message Recall Be Supported?

Question:

- Can a decentralized system really "recall" a message?

Decision:

- The protocol supports **logical recall** via `redact / withdraw` semantics.
- Default human-facing views should show a tombstone such as "message recalled".
- The protocol does not promise global physical erasure of already replicated copies.
- Stronger deletion behavior, if needed, must rely on retention policy, attachment key revocation, or storage-side GC.

### 2.8 How Is Information Synchronized?

Question:

- Are board sync and chat sync two separate protocols?

Decision:

- No. One protocol, multiple sync profiles.
- Actors write to their own repos first.
- Principal Servers exchange authorized Space operations.
- Clients materialize current state and queries locally by default; delegated search services are optional extensions.
- Board, chat, topic, tree, and graph modes differ in filters and projections, not protocol identity.

### 2.9 How Is History Backfilled?

Question:

- Chat wants a recent message window.
- Boards want current state.
- Topics want recoverable thread history.

Decision:

- First recovery should prefer snapshot + Operation increments.
- Messages/topics support cursor + backfill.
- Board mode defaults to current state + recent relevant discussion summary.
- Chat mode defaults to channel metadata + a recent timeline window + live increments.

### 2.10 How Are Conflicts Resolved?

Question:

- What if two users edit a title concurrently?
- What if two users drag the same card?
- What if a message is edited and redacted concurrently?

Decision:

- All convergence comes from fixed reducer rules.
- Scalar fields use LWW by causal order.
- Set fields use OR-Set.
- Ordering uses fractional indexing.
- Messages are append-only timeline entries.
- `message.revise` builds a revision chain.
- `message.redact` dominates message visibility in the default view.

### 2.11 How Is Authorization Unified?

Question:

- Are board editing, message sending, recalling, and channel moderation the same kind of permission?

Decision:

- No. All of them are represented in capabilities, but as distinct actions.
- The minimum split includes:
  - board/item actions
  - channel/topic/message actions
  - moderation/redaction actions
  - run/memory actions
- `edit_own_message` and `redact_any_message` must not be conflated.

### 2.12 What Role Do AI Agents Play Here?

Question:

- Are agents just plugins, or protocol participants?

Decision:

- Agents are first-class principals.
- Agents may receive constrained board/message/memory grants.
- Agent outputs may be persisted as `run` and `memory`.
- Messages, comments, and topics may all serve as memory-extraction sources.

## 3. Overall Best-solution Plan

Taken together, the protocol adopts the following overall plan:

1. Fix the root model as `Space + Actor + Entity + Relation + Event + View`.
2. Model boards with `Entity.facets`, `contains/belongs_to` Relations, and the `View{kind="collection"}` collection projection; `renderer="board"` is only a board presentation profile hint, and `board/collection/task` are common semantic labels.
3. Model conversation with facets such as `replyable/renderable`, `belongs_to/replies_to/mentions` Relations, and Chat/Thread Views; `channel/topic/message` are common semantic labels.
4. Keep `comment` for durable object-level notes, while `message` handles timeline conversation.
5. Standardize `@mention` as structured DID/entity references and `mentions` Relations.
6. Use revision chains for editing and redaction/tombstones for recalls.
7. Reuse the same repo-first + Principal Server sync + client projection model across board/chat/topic modes.
8. Resolve conflicts through fixed reducer rules rather than client-specific heuristics.
9. Unify all permissions under capabilities rather than implicit roles.

## 4. Where These Decisions Must Be Written Back

Based on this question inventory, the rest of the spec must explicitly cover:

- [object-model-core.md](../models/object-model-core.md) and [object-model-standard.md](../models/object-model-standard.md)  
  The `Space/Actor/Entity/Relation/Event/View` root model and the semantic mapping for board/chat/task/message/run/memory.
- [conversation-model.md](../models/conversation-model.md)  
  Mention/edit/redaction/reaction semantics.
- [operations-sync.md](../sync/operations-sync.md)  
  Board/chat/topic sync profiles and conflict-resolution behavior.
- [capabilities.md](../authz/capabilities.md)  
  Message, topic, channel, recall, and moderation actions.
- [views.md](../models/views.md)  
  `chat/forum/thread/inbox` and related projections.

## 5. Current Conclusion

The right direction for Contrix is not to choose between "board protocol" and "chat protocol".

The right direction is:

- one object graph for work and communication
- one sync model for both
- one authorization model for both
- multiple views for humans and agents


