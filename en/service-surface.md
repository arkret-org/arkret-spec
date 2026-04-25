# Service Surface And Bootstrap Draft

## 1. Goal

If the spec has only object models, sync principles, and capabilities but no minimal wire-level service surface, real interoperability is still weak.

Contrix therefore needs an initial definition for:

- how identity registries accept DID operations and receipts
- how repos publish and serve commits / ops
- how relays expose workspace firehoses and backfill
- how indexes serve queries and materialize inbox / notifications
- how blob services upload and verify content
- how invites / grants participate in first-time workspace join

This document defines a **minimum interoperable service surface**.  
Implementations do not have to use HTTP or XRPC specifically, but they MUST provide semantically equivalent interfaces.

## 2. Core Principles

### 2.1 DID Documents Are for Discovery, Not Bulk State

DID Documents SHOULD be used to:

- declare identity-registry / repo / relay / index / blob / capability endpoints
- declare service DIDs or service endpoints

They should not directly carry:

- full current grant state
- workspace current state
- large inbox or notification payloads

### 2.2 No Single Service Is the Sole Truth Source

- the repo is the actor publication truth source
- the relay is the distribution layer
- the index is the query/materialization layer
- the blob service is the content layer

Clients should be able to cross-check frontier, hashes, and reducer profiles across those layers.

### 2.3 Interfaces Must Support Idempotent Retries

Network retries, offline replay, and multi-relay loops are normal in decentralized systems.

Write interfaces therefore MUST support:

- idempotent `commit_id`
- idempotent `op_id`
- repeated submission without repeated effect

### 2.4 Services Must Publish Compatibility Profiles

Each service SHOULD publish:

- `protocol_version`
- `supported_features`
- `supported_reducer_profiles`
- `supported_schema_profiles`

Without that, clients cannot safely decide whether to use the service.

## 3. Common Service Description Endpoint

Every service is recommended to provide:

```text
GET /xrpc/cx.server.describe
```

Example:

```json
{
  "service_did": "did:web:relay.example.net",
  "service_type": "ContrixRelay",
  "protocol_version": "0.2-draft",
  "supported_features": [
    "firehose",
    "snapshot",
    "notification-index"
  ],
  "supported_reducer_profiles": [
    "cx.reducer.v1"
  ],
  "supported_schema_profiles": [
    "cx.schema.v1"
  ],
  "max_body_bytes": 1048576
}
```

### 3.1 Identity Registry Surface

Identity registries should expose at least the following semantics:

#### 3.1.1 Describe the Registry

```text
GET /xrpc/cx.id.describe
```

It should return:

- `service_did`
- `registry_mode = writer | witness | replica`
- supported receipt types
- current software version and compatibility profile

#### 3.1.2 Fetch the Current DID Document

```text
GET /xrpc/cx.id.getDocument?did=<did>
```

The response SHOULD contain:

- the current materialized DID Document
- the current `head_event_hash`
- the current `seq`
- optional witness receipts

#### 3.1.3 Fetch the DID Log

```text
GET /xrpc/cx.id.getLog?did=<did>&cursor=<cursor>&limit=<n>
```

Used for:

- audit
- reconstructing the DID Document
- checking that `key_log` matches the registry head

#### 3.1.4 Submit a DID Update

```text
POST /xrpc/cx.id.submitDidOp
```

The request body SHOULD contain:

- `did`
- `seq`
- `prev_event_hash`
- `patch`
- `proofs`

Requirements:

- replaying the same `did + seq` with identical content MUST be idempotently accepted
- reusing the same `did + seq` with different content MUST be rejected
- the registry MUST validate the authorization chain back to `inception_key`

#### 3.1.5 Fetch Receipt / Witness Proofs

```text
GET /xrpc/cx.id.getReceipts?did=<did>&head=<event-hash>
```

#### 3.1.6 Recommended Write Confirmation

The initial recommendation is:

- writer clients submit the `did_op` to multiple registries / witnesses
- at least `k-of-n` receipts are required before the update is considered committed
- reads may attach `expected_head` or `min_seq`

That keeps DID writes in the world of ordinary network requests rather than global block consensus.

## 4. Repo Surface

Repos should expose at least the following semantics:

### 4.1 Describe the Repo

```text
GET /xrpc/cx.repo.describe
```

It should return:

- `repo_did`
- current head commit
- supported signature algorithms
- whether batch op fetch is supported

### 4.2 List Commits

```text
GET /xrpc/cx.repo.listCommits?cursor=<cursor>&limit=<n>
```

Used for:

- actor-history recovery
- audit replay
- filling missing commits

### 4.3 Get One Commit

```text
GET /xrpc/cx.repo.getCommit?commit_id=<id>
```

### 4.4 Batch-fetch Ops

```text
POST /xrpc/cx.repo.getOps
```

The request body may carry a set of `op_id` values.

### 4.5 Submit a Commit

```text
POST /xrpc/cx.repo.submitCommit
```

Requirements:

- re-submitting the exact same bytes for the same `commit_id` MUST be idempotently accepted
- reusing the same `commit_id` with different bytes MUST be rejected
- the repo SHOULD return the new head and the accepted op list

## 5. Relay Surface

Relays should expose at least the following semantics:

### 5.1 Describe the Relay

```text
GET /xrpc/cx.relay.describe
```

### 5.2 Workspace Firehose Subscription

```text
GET /xrpc/cx.relay.subscribe?space_id=<id>&cursor=<cursor>
```

Implementations may use:

- SSE
- WebSocket
- long polling

but they must provide stable cursor semantics.

### 5.3 Incremental Backfill

```text
GET /xrpc/cx.relay.backfill?space_id=<id>&cursor=<cursor>&limit=<n>
```

### 5.4 Snapshot Head

```text
GET /xrpc/cx.relay.getSnapshotHead?space_id=<id>
```

Used to fetch the currently recommended snapshot manifest.

## 6. Index Surface

Indexes should expose at least the following semantics:

### 6.1 Describe the Index

```text
GET /xrpc/cx.index.describe
```

### 6.2 Fetch Current Object State

```text
GET /xrpc/cx.index.getObject?ref=<stable-ref>
```

### 6.3 Structured Query

```text
POST /xrpc/cx.index.query
```

The request body SHOULD accept:

- `kind`
- filters
- ordering
- cursor
- limit

### 6.4 Thread / Topic Query

```text
GET /xrpc/cx.index.getThread?topic_id=<id>&cursor=<cursor>
```

### 6.5 Inbox / Notification Query

```text
GET /xrpc/cx.index.getNotifications?cursor=<cursor>&state=unread
```

```text
GET /xrpc/cx.index.getInbox?scope=<scope>&cursor=<cursor>
```

## 7. Blob Surface

Blob services should expose at least:

### 7.1 Upload a Blob

```text
POST /xrpc/cx.blob.upload
```

Returning:

- `blob_cid`
- `sha256`
- `size`

### 7.2 Inspect Blob Headers

```text
HEAD /xrpc/cx.blob.get?blob_cid=<cid>
```

### 7.3 Download a Blob

```text
GET /xrpc/cx.blob.get?blob_cid=<cid>
```

Blob validation MUST be content-hash based rather than URL based.

## 8. Capability / Invite Surface

Even though grant / revoke / invite are themselves objects or ops, the service layer still needs query surfaces.

At minimum, the following are recommended:

```text
GET /xrpc/cx.authz.getEffectiveGrants?space_id=<id>&subject=<did>
```

```text
GET /xrpc/cx.authz.getInvites?space_id=<id>&subject=<did-or-handle>
```

```text
POST /xrpc/cx.authz.check
```

The `check` surface is useful for:

- repo-side prechecks before accepting writes
- fast filtering before relay distribution
- local UX warnings before a client sends a write

## 9. Space Bootstrap Flow

The recommended first-time join flow is:

1. the user enters a handle, DID, or workspace link
2. the client resolves the DID and completes handle bidirectional verification
3. the client discovers identity registry / repo / relay / index / blob / authz services from the DID Document
4. the client fetches invite / grant views relevant to the principal
5. the client fetches workspace metadata and the snapshot head
6. the client downloads the snapshot manifest and chunks
7. the client fetches backfill / firehose increments after the frontier
8. the client runs the reducer locally
9. the client establishes personal state such as read markers and notification cursors

## 10. Freshness and Multi-service Coexistence

When multiple relays or indexes coexist, services SHOULD expose:

- current frontier
- snapshot frontier
- reducer profile
- last materialization time

Clients MAY compare these values to decide:

- which service is fresher
- whether they need to fall back to repo replay
- whether an index is merely behind versus actually inconsistent

For identity registries, services SHOULD also expose:

- the current DID head
- `seq`
- a receipt-set summary

Clients may use those values to decide whether a registry is:

- serving the freshest head
- merely a lagging replica
- or potentially forked / malicious

## 11. Transport Security and Ciphertext

The service surface SHOULD distinguish:

- metadata needed for routing
- optional end-to-end encrypted content

If a payload is already encrypted under `policy.encryption_profile`, then:

- repos / relays / indexes MAY be unable to decrypt the body
- but they SHOULD still preserve hash, cursor, causality, and target references

## 12. Initial Design Decisions

The current draft recommends fixing:

- a minimum identity-registry / repo / relay / index / blob / authz service surface
- XRPC-style paths as a recommendation rather than a hard requirement
- idempotent write interfaces
- DID writes confirmed by multi-registry / witness receipts rather than blockchains
- bootstrap covering invite / grant / snapshot / backfill
- services publishing reducer / schema / feature profiles

## 13. Further Work

The next round still needs:

- formal request/response schemas for each endpoint
- cursor encoding
- firehose frame format
- error codes and retry semantics
- auth-token or signed-request formats
- identity receipt / witness proof schemas
