# Capability Model Draft

## 1. Goal

Contrix uses a capability-oriented authorization model rather than relying on membership alone or vague roles.

This is necessary because:

- cross-organization collaboration is common
- boards, chat, topics, and memories have different action sets
- agents need constrained grants
- authorization changes must remain auditable

## 2. Core Principles

### 2.1 Authorization Subjects SHOULD Be Stable Principals

Grant `issuer` and `subject` SHOULD use DIDs.

Human-readable identifiers such as handles, emails, or domain usernames MUST NOT be used as authorization subject primary keys.

The protocol allows conditional authorization, but conditions must reduce to verifiable claims / attestations rather than raw string matching.

### 2.2 Authorization Must Be Explicit

Avoid assumptions such as:

- joining a space implies all abilities
- being allowed to edit items implies recalling other people's messages
- channel owners inherently have all moderation powers

### 2.3 Authorization Decisions Depend on the Effective Capability Set

Whether an operation is valid should be decided by the effective grant set at that time.

### 2.4 DID Is the Subject, Claim Is the Condition

The authorization model has three layers:

```txt
Identity: DID
Human-readable binding: Handle
Authorization condition: Claim / Attestation
```

That means:

- DID answers who the Actor is
- Handle helps humans discover and display the Actor
- Claim / Attestation answers whether the Actor currently satisfies an authorization condition

For example, `alice.google.com` or `alice:google.com` may be a handle inside an organization namespace, but it cannot be a grant subject. Organization access should be represented through an `org_membership` claim issued by Google.


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

### 3.1 Conditional Grants

A grant `subject` may be a concrete DID or a condition selector.

Concrete DID grant:

```json
{
  "subject": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "constraints": {
    "requires_claims": [
      {
        "claim_type": "org_membership",
        "issuer": "did:web:google.com",
        "organization": "did:web:google.com",
        "status": "active"
      }
    ]
  }
}
```

Conditional grant:

```json
{
  "subject": {
    "kind": "condition",
    "requires_claims": [
      {
        "claim_type": "org_membership",
        "issuer": "did:web:google.com",
        "organization": "did:web:google.com",
        "status": "active"
      }
    ]
  }
}
```

The difference:

- concrete DID grant: grants one Actor, but requires that Actor to still satisfy conditions at operation time
- conditional grant: grants all Actors satisfying the condition

Conditional grants MUST specify the claim issuer, claim type, effective status, and resource scope. Nodes MUST NOT rely only on handle suffixes, email domains, or display names.

## 4. Resource Selector

The first version should support the following `kind` values:

- `space`
- `board`
- `collection`
- `entity`
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

- `create_entity`
- `edit_entity`
- `move_entity`
- `reorder_entity`
- `create_task`
- `edit_task`
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

- `manage_space`
- `manage_board`
- `manage_schema`
- `manage_capabilities`
- `manage_policy`
- `manage_invites`

### 5.6 Service Actions

- `sync_ops`
- `index_space`
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
- `entity_type_allow`
- `memory_kind_allow`
- `allowed_channel_refs`
- `visibility_allow`
- `blob_max_bytes`
- `encryption_required`
- `message_edit_window`
- `max_delegation_depth`
- `rate_limit`
- `approval_required`
- `approval_mode`
- `approval_actor_refs`
- `approval_relation`
- `accountability_required`
- `guardian_approval_required`
- `controller_approval_required`
- `requires_claims`
- `trusted_claim_issuers`
- `claim_refresh_required`
- `claim_max_age`

## 7. Claim / Attestation

Claim / Attestation is a verifiable statement from an issuer about a subject.

It represents conditions such as organization membership, organization role, guardian relationship, device trust, protected-actor status, MFA level, and risk level.

Suggested minimal shape:

```json
{
  "claim_id": "cx:claim:01JS0CLM00000000000000000",
  "issuer": "did:web:google.com",
  "subject": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "claim_type": "org_membership",
  "claims": {
    "organization": "did:web:google.com",
    "status": "active",
    "roles": ["employee", "engineer"],
    "handle": "alice.google.com"
  },
  "not_before": "2026-04-01T00:00:00Z",
  "expires_at": "2026-05-01T00:00:00Z",
  "revocation_ref": "cx:event:01JS0RVK0000000000000000",
  "proof": {
    "type": "DataIntegrityProof",
    "verification_method": "did:web:google.com#key-1",
    "signature": "base64url..."
  }
}
```

Initial claim types:

- `verified_handle`
- `verified_email_domain`
- `org_membership`
- `org_role`
- `employment_status`
- `guardian_relationship`
- `protected_actor_status`
- `agent_controller`
- `device_trust`
- `mfa_level`
- `risk_level`
- `certification`

Claim verification requires at least:

1. the `issuer` is trusted by the current Space / Policy
2. the `subject` matches the current actor DID, or matches the verified relationship semantics
3. the proof signature is valid
4. the current time is within `not_before` and `expires_at`
5. the claim has not been revoked
6. the claim content satisfies the grant's `requires_claims`

### 7.1 Handle Binding Claim

Handle may appear as a claim field, but not as an authorization primary key.

Example:

```json
{
  "claim_type": "verified_handle",
  "issuer": "did:web:google.com",
  "subject": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "claims": {
    "handle": "alice.google.com",
    "namespace": "google.com",
    "status": "active"
  }
}
```

When that handle can no longer be verified, expires, or is revoked by the organization, permissions depending on that claim naturally stop applying.

Historical Events still keep the original DID as `actor_id`, so handle reuse cannot rewrite responsibility.

## 8. Accountable Actor Grants

Capability must support Actors that have direct identity but require a responsible party, guardian, controller, or operator.

These Actors include:

- AI agents
- service bots
- automation accounts
- minors
- protected-user accounts
- enterprise-managed accounts
- third-party integration accounts

Core rules:

- accountability is not capability
- owner / guardian / controller does not automatically pass permissions to the subject
- the subject must still match an explicit grant to act
- high-risk actions MAY require responsible / guardian / controller approval
- Events SHOULD record grant, delegation chain, approval evidence, and run context

### 8.1 Approval Constraint

When a grant carries an approval constraint, the subject cannot directly make the target action effective.

```json
{
  "constraints": {
    "approval_required": true,
    "approval_mode": "before_commit",
    "approval_actor_refs": [
      "did:web:alice.example.com"
    ],
    "approval_relation": "controller"
  }
}
```

Initial `approval_mode` values:

- `before_commit`: approval occurs before the target Event enters the effective set
- `proposal_then_approve`: the subject may only create a proposal; approval later causes the target Event
- `after_commit_review`: execution may proceed, but it must enter an audit/review queue

Initial `approval_relation` values:

- `responsible`
- `controller`
- `guardian`
- `space_admin`
- `custom`

If policy requires guardian approval for a minor or protected Actor, nodes MUST validate the corresponding approval evidence.

### 8.2 Proposal Mode

High-risk actions should use proposal mode:

```txt
actor -> proposal.created
guardian/controller -> proposal.approved
system/human -> entity.updated
```

This lets an agent or restricted Actor express intent without directly mutating high-risk state.

## 9. Safe Authorization for Agents

When granting to agents, implementations SHOULD default to:

- explicit Space / Entity / View scope only
- only the required actions
- time-bounded grants
- restricted object kinds
- restricted writable fields and memory kinds
- required controller / responsible-actor approval where needed

High-risk patterns include:

- long-lived full-Space admin grants
- agents inheriting complete human-owner authority
- grants without expiry
- execution without run audit trails
- no recorded responsible / controller / operator
- high-risk actions without approval

## 10. Delegation

Delegation means a subject may re-grant part of its authority to another subject.

If `max_delegation_depth = 0`, further delegation is disallowed.  
If it is greater than zero:

- each re-grant MUST reduce depth
- the re-grant must not expand the original scope
- the delegation chain MUST be verifiable

## 11. Effective Permission Set

Contrix v1 uses an **allow-grant + explicit revoke** model.

That means:

- there is no generic protocol-level `deny` grant
- the effective permission set is the union of all currently valid grants
- revoke ops explicitly remove grants from that effective set

Deployments MAY layer local deny policies on top, but those are outside wire-level interoperability semantics.

## 12. Revocation

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

## 13. Invites, Notifications, and Read State

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

## 14. Roles Are Only Bundles

Product layers may define:

- `space_admin`
- `board_manager`
- `contributor`
- `observer`
- `channel_moderator`
- `agent_writer`

But these are only convenience bundles of capabilities, not primary protocol semantics.

## 15. Read Access and Discoverability

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

## 16. Authorization Guidance for Conversation

The first version should minimally distinguish:

- sending messages
- editing one's own messages
- editing any message
- recalling one's own messages
- recalling any message
- managing channels/topics

This prevents "can recall other people's messages" from being accidentally bundled into "can send messages".

## 17. Where Decisions Are Enforced

Authorization checks should not happen only on clients.

They should happen at least in:

- client-side prechecks
- repo write acceptance
- Sync Service distribution
- index query serving
- blob content serving

## 18. Minimal Authorization Algorithm

Given an operation, a node should at least:

1. resolve the actor DID
2. verify the signature chain
3. find the effective grant set
4. expand delegation
5. check whether the selector covers the target
6. check whether the action matches
7. check whether the constraints are satisfied
8. if the grant or constraint requires claims, fetch and validate the claims / attestations
9. check that claim issuers are trusted
10. check that claims are effective, unexpired, and not revoked
11. if approval is required, validate responsible / guardian / controller approval evidence
12. apply revocation and superseding rules

When multiple grants match, the recommended behavior is:

- first select grants whose resource selectors cover the target
- then union their allowed actions
- then intersect or tighten constraints to the strictest effective shape
- finally apply revocation, expiry, delegation-depth, claim, and approval trimming

## 19. Initial Design Decisions

The current draft recommends fixing:

- capability-based authorization
- one grant system across boards, conversation, runs, and memories
- `edit_own_message` distinct from `redact_any_message`
- invites / notifications / read markers inside the same capability model
- allow-grant + explicit revoke as the protocol-level semantic
- narrow, time-bounded, auditable grants for agents
- Accountable Actor as a general grant subject covering agents, minors, managed accounts, and automation subjects
- owner / guardian / controller does not imply automatic permission inheritance
- high-risk actions support approval constraints and proposal mode
- grant subjects use DIDs or condition selectors, not handles as authorization primary keys
- handles may appear as claim fields, but authorization checks must use verifiable claims / attestations
- organization access is represented through claims such as `org_membership` and `org_role`
- claim expiry or revocation naturally disables permissions depending on that claim

## 20. Further Work

The next round still needs:

- a formal resource-selector grammar
- a formal constraint schema
- a formal algorithm for grant merging and strictest-constraint reduction
- a moderation-policy integration story
- approval proof and proposal state machine
- default policy profiles for Accountable Actors
- formal claim / attestation envelope schema
- formal condition selector syntax
- trusted claim issuer registry and claim revocation query surface

