# Capability Model Draft

## 1. Goal

Contrix New uses a capability-oriented authorization model rather than relying on membership alone or vague roles.

This is necessary because:

- cross-organization collaboration is common
- boards, chat, topics, and memories have different action sets
- agents need constrained grants
- authorization changes must remain auditable

## 2. Core Principles

### 2.1 Authorization Subjects SHOULD Be Stable Principals

Grant `issuer` and `subject` SHOULD use DIDs.

### 2.2 Authorization Must Be Explicit

Avoid assumptions such as:

- joining a workspace implies all abilities
- being allowed to edit items implies recalling other people's messages
- channel owners inherently have all moderation powers

### 2.3 Authorization Decisions Depend on the Effective Capability Set

Whether an operation is valid should be decided by the effective grant set at that time.

## 3. Grant Object

Example:

```json
{
  "grant_id": "cx:grant:01JS0GR000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject": "did:web:agent.copy.example.com",
  "resource": {
    "kind": "board",
    "refs": [
      "cx:board:01JS0BD000000000000000000"
    ]
  },
  "actions": [
    "read",
    "edit_item",
    "create_run",
    "write_memory"
  ],
  "constraints": {
    "expires_at": "2026-04-30T00:00:00Z",
    "fields_write_allow": [
      "title",
      "body",
      "labels",
      "due_at"
    ],
    "max_delegation_depth": 0
  }
}
```

## 4. Resource Selector

The first version should support the following `kind` values:

- `workspace`
- `board`
- `collection`
- `item`
- `comment`
- `channel`
- `topic`
- `message`
- `view`
- `run`
- `memory`
- `schema`
- `policy`
- `invite`
- `read_marker`

## 5. Action Set

### 5.1 Common Actions

- `discover`
- `read`
- `read_metadata`
- `read_content`
- `create`
- `update`
- `archive`
- `restore`

### 5.2 Board and Object Actions

- `create_item`
- `edit_item`
- `move_item`
- `reorder_item`
- `assign_item`
- `comment`
- `manage_relations`
- `manage_attachments`
- `manage_views`

### 5.3 Conversation Actions

- `read_history`
- `send_message`
- `react`
- `edit_own_message`
- `edit_any_message`
- `redact_own_message`
- `redact_any_message`
- `manage_channels`
- `manage_topics`

### 5.4 Run and Memory Actions

- `create_run`
- `update_run`
- `write_memory`
- `confirm_memory`
- `invalidate_memory`
- `curate_memory`

### 5.5 Administrative Actions

- `manage_workspace`
- `manage_board`
- `manage_schema`
- `manage_capabilities`
- `manage_policy`
- `manage_invites`

### 5.6 Service Actions

- `relay_ops`
- `index_workspace`
- `store_blobs`

### 5.7 Human-facing and Personal-state Actions

- `write_read_markers`
- `read_notifications`
- `ack_notifications`
- `accept_invite`

## 6. Constraints

The first version recommends support for:

- `expires_at`
- `not_before`
- `fields_write_allow`
- `fields_write_deny`
- `item_type_allow`
- `memory_kind_allow`
- `allowed_channel_refs`
- `visibility_allow`
- `blob_max_bytes`
- `encryption_required`
- `message_edit_window`
- `max_delegation_depth`
- `rate_limit`
- `approval_required`

## 7. Safe Authorization for Agents

When granting to agents, implementations SHOULD default to:

- explicit workspace / board / channel scope only
- only the required actions
- time-bounded grants
- restricted object kinds
- restricted writable fields and memory kinds

High-risk patterns include:

- long-lived full-workspace admin grants
- agents inheriting complete human-owner authority
- grants without expiry
- execution without run audit trails

## 8. Delegation

Delegation means a subject may re-grant part of its authority to another subject.

If `max_delegation_depth = 0`, further delegation is disallowed.  
If it is greater than zero:

- each re-grant MUST reduce depth
- the re-grant must not expand the original scope
- the delegation chain MUST be verifiable

## 9. Effective Permission Set

Contrix v1 uses an **allow-grant + explicit revoke** model.

That means:

- there is no generic protocol-level `deny` grant
- the effective permission set is the union of all currently valid grants
- revoke ops explicitly remove grants from that effective set

Deployments MAY layer local deny policies on top, but those are outside wire-level interoperability semantics.

## 10. Revocation

Revocation must be explicit rather than deleting grant records.

Example:

```json
{
  "type": "cx.capability.revoke",
  "body": {
    "grant_ref": "cx:grant:01JS0GR000000000000000000",
    "reason": "contract ended"
  }
}
```

## 11. Invites, Notifications, and Read State

These human-facing capabilities must be part of the authorization model rather than product-private backdoors:

- creating or canceling invites requires `manage_invites`
- accepting an invite addressed to oneself requires `accept_invite`
- writing one's own `read_marker` requires `write_read_markers`
- reading notifications requires `read_notifications`
- `ack_notifications` should affect only the caller's derived inbox state

Where:

- `invite` is not the same thing as a grant
- `notification` is a derived object, but its visibility is still constrained by the ACLs of the underlying source object
- `read_marker` is owner-private by default

## 12. Roles Are Only Bundles

Product layers may define:

- `workspace_admin`
- `board_manager`
- `contributor`
- `observer`
- `channel_moderator`
- `agent_writer`

But these are only convenience bundles of capabilities, not primary protocol semantics.

## 13. Read Access and Discoverability

Read authorization is not just "can content be fetched?" It also includes:

- whether an object may be discovered
- whether message history may be seen
- whether recalled-message metadata may be seen
- whether attachment content may be fetched

The first version should at least distinguish:

- `discover`
- `read_metadata`
- `read_content`
- `read_history`

## 14. Authorization Guidance for Conversation

The first version should minimally distinguish:

- sending messages
- editing one's own messages
- editing any message
- recalling one's own messages
- recalling any message
- managing channels/topics

This prevents "can recall other people's messages" from being accidentally bundled into "can send messages".

## 15. Where Decisions Are Enforced

Authorization checks should not happen only on clients.

They should happen at least in:

- client-side prechecks
- repo write acceptance
- relay distribution
- index query serving
- blob content serving

## 16. Minimal Authorization Algorithm

Given an operation, a node should at least:

1. resolve the actor DID
2. verify the signature chain
3. find the effective grant set
4. expand delegation
5. check whether the selector covers the target
6. check whether the action matches
7. check whether the constraints are satisfied
8. apply revocation and superseding rules

When multiple grants match, the recommended behavior is:

- first select grants whose resource selectors cover the target
- then union their allowed actions
- then intersect or tighten constraints to the strictest effective shape
- finally apply revocation, expiry, and delegation-depth trimming

## 17. Initial Design Decisions

The current draft recommends fixing:

- capability-based authorization
- one grant system across boards, conversation, runs, and memories
- `edit_own_message` distinct from `redact_any_message`
- invites / notifications / read markers inside the same capability model
- allow-grant + explicit revoke as the protocol-level semantic
- narrow, time-bounded, auditable grants for agents

## 18. Further Work

The next round still needs:

- a formal resource-selector grammar
- a formal constraint schema
- a formal algorithm for grant merging and strictest-constraint reduction
- a moderation-policy integration story
