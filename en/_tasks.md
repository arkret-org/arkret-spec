# Contrix New Tasks

## Current-round Tasks

- [x] Add `design-questions.md`  
  List the protocol questions first, then converge on explicit decisions.
- [x] Rewrite `README.md`  
  Expand the spec map into "question inventory + architecture + objects + conversation + sync + authorization + views + memory".
- [x] Add `conversation-model.md`  
  Define the interaction model for board/chat/topic/mention/edit/recall/reaction.
- [x] Rewrite `object-model.md`  
  Promote `channel/topic/message` to first-class objects.
- [x] Rewrite `operations-sync.md`  
  Define board/chat/topic sync profiles, redaction semantics, and conflict convergence.
- [x] Rewrite `capabilities.md`  
  Bring message, topic, channel, recall, and moderation actions into the capability model.
- [x] Rewrite `views.md`  
  Ensure the protocol naturally projects into kanban/chat/forum/thread/inbox and similar interfaces.
- [x] Add `service-surface.md`  
  Define the minimum repo / relay / index / blob / authz service surface and bootstrap flow.
- [x] Fill in `schema / policy / invite / read_marker / notification`  
  Write previously referenced-but-undefined objects back into the protocol.
- [x] Fill in sync and authorization details  
  Define idempotent submission, authorization-time convergence, encrypted forwarding, and invite/read-state permissions.

## Current-round Acceptance Criteria

- [x] The protocol question inventory is explicit
- [x] The board data model is explicit as `board + collection + item + view`
- [x] The chat/topic model is explicit as `channel + topic + message`
- [x] `@mention` is defined as structured DID/object references
- [x] Recall is defined as redaction/tombstone rather than implicit physical deletion
- [x] Board/chat/topic sync and conflict rules are written back into the spec
- [x] The minimum service surface and workspace bootstrap are written into the spec
- [x] `schema/policy/invite/read_marker/notification` are formally defined
- [x] Idempotent submission and authorization-time rules are written into the spec

## Next-round Backlog

- [ ] Define a formal query JSON schema
- [ ] Define a formal grant-constraint schema
- [ ] Define cursor / HLC / rank / commit-hash encodings
- [ ] Define snapshot manifest and chunk schemas
- [ ] Define formal request/response schemas for each service endpoint
- [ ] Define snapshot-signature / chunk-digest / encrypted-envelope schemas
- [ ] Define formal schemas and query surfaces for read markers / inbox / notifications
