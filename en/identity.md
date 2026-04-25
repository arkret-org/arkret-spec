# Identity Layer Draft

## 1. Goal

Contrix New uses **DIDs as the stable identity root** and follows an atprotocol-inspired pattern of "handle entry point + DID root anchor + document-based service discovery", while defining its own DID generation, key-rotation, and recovery rules.

The identity layer must solve:

- stable identification for humans, organizations, agents, and services
- separating the DID's "birth anchor" from later control keys
- handle migration without breaking historical references
- device delegation, agent delegation, key recovery, and key rotation
- keeping the DID stable across ordinary key loss, compromise, and rotation whenever recovery remains possible

## 2. Core Principles

### 2.1 Stable Principal References MUST Use DIDs

Protocol-level principal references MUST use DIDs rather than handles.

This includes:

- object authors
- object updaters
- grant issuers
- grant subjects
- run actors
- memory authors
- service node identities

### 2.2 Handles Are Human Entry Points, Not Primary Keys

Handles are mutable and migratable, so:

- historical ops must not use handles as identity anchors
- ACLs and capabilities must not bind to handles
- object fields such as `created_by` and `updated_by` must store DIDs

### 2.3 DID Documents Are the Root of Service Discovery

After resolving a DID, a Contrix client SHOULD discover:

- identity-registry endpoints
- repo endpoints
- relay endpoints
- index endpoints
- blob endpoints
- capability endpoints
- notification endpoints

from the DID document.

### 2.4 DIDs Should Persist While Keys Rotate

The core `did:uuid` position in Contrix is:

- ordinary key rotation MUST NOT change the DID
- the hash embedded in the DID anchors the **inception key**, not necessarily the currently active control key
- the legitimacy of the current control key depends on a verifiable historical authorization chain, not on direct equality with the hash embedded in the DID

In other words, Contrix uses:

- **initial match**
- **process authorization**

as its identity-validation model.

## 3. Native Contrix DID Method

## 3.1 Default DID Method

Contrix defines its default native DID method as:

- `did:uuid:<uuid-v8>`

Where:

- `did:uuid` is the method name
- `<uuid-v8>` is a UUID v8 generated with the Contrix bit layout

The first version recommends:

- MUST support `did:uuid`
- SHOULD support `did:web` for org/service interoperability
- MAY support `did:plc`
- MAY support `did:key` for testing or temporary principals

## 3.2 Textual Form

The canonical textual form of `<uuid-v8>` SHOULD use:

- lowercase hexadecimal
- the standard UUID hyphen form `8-4-4-4-12`

Example:

```text
did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992
```

## 3.3 DID vs Inception Public Key

A Contrix DID is not a random identifier.  
It MUST be jointly determined by:

1. the generation timestamp
2. the hash algorithm identifier
3. a hash fragment of the **inception public key**

This means:

- you cannot manufacture a "new identity" by changing only the timestamp while keeping the same hash-algorithm identifier and inception-key hash fragment
- the 74-bit DID fragment records the identity's birth-time anchor
- later control keys may change as long as the change process has a complete authorization chain
- a new DID MAY be created only when there is no valid recovery path and the operator intentionally reboots the identity

## 4. UUID v8 Bit Layout

The default Contrix DID suffix uses a 128-bit UUID v8 with the following custom bit layout.

### 4.1 Bit Segments

- first 44 bits: Unix millisecond timestamp
- next 4 bits: Hash Algorithm ID
- next 4 bits: Version, fixed to `0x8`
- next 12 bits: beginning of the inception-key hash fragment
- next 2 bits: Variant, fixed to `0b10`
- final 62 bits: continuation of the inception-key hash fragment

In other words:

- the timestamp uses 44 bits
- the hash-algorithm identifier uses 4 bits
- all remaining non-standard UUID bits are used for the public-key hash
- the public-key hash uses 74 bits total

## 4.2 Endianness Requirement

Contrix MUST use **big-endian** bit filling, parsing, and comparison when handling the full 128-bit UUID value.

This is mandatory.  
Without this rule, different languages may serialize/parse the 128-bit value differently, which would break interoperability and verification.

Concrete requirements:

- the timestamp is written into the top 44 bits in big-endian order
- the Hash Algorithm ID is written immediately after the timestamp
- public-key hash bits are filled from high to low bit positions
- Version and Variant bits must be explicitly skipped and must never be overwritten by hash filling

## 4.3 Bit Indexing

It is recommended to number the UUID bits from `bit 0 .. bit 127`, high to low.

The mapping is:

- `bit 0 .. bit 43`: Unix millisecond timestamp
- `bit 44 .. bit 47`: Hash Algorithm ID
- `bit 48 .. bit 51`: Version = `1000`
- `bit 52 .. bit 63`: public-key hash `hash[0..11]`
- `bit 64 .. bit 65`: Variant = `10`
- `bit 66 .. bit 127`: public-key hash `hash[12..73]`

## 5. Hash Algorithm ID and Hash Input

## 5.1 Initial Hash Algorithm ID Registry

The initial registry is:

- `0x0`: reserved
- `0x1`: SHA-256
- `0x2`: SHA-512/256
- `0x3`: SHA3-256
- `0x4`: BLAKE3-256
- `0x5 .. 0xE`: reserved for future specs
- `0xF`: experimental/private use

## 5.2 Inception Public Key

Every `did:uuid` DID Document MUST designate exactly one immutable **inception public key**.

Suggested field name:

- `inception_key`

Its value should point to one key id in `verificationMethod`.

That key is used for:

- generating the DID suffix
- acting as the permanent historical anchor of the identity
- providing the trust starting point for later control-key chains

For compatibility with earlier drafts, implementations MAY temporarily accept:

- `anchor_key`

as a transitional alias for `inception_key`, but the normative field name should be `inception_key`.

## 5.3 Hash Input Rule

The public-key hash fragment inside the DID MUST be derived from the **canonical byte representation of the inception public key**, not from:

- the current control key
- the full certificate bytes
- recovery keys

This matters because:

- the DID needs a stable birth-time fingerprint
- certificate metadata changes must not create meaningless DID churn
- later key rotation must not break historical identity references

Suggested canonical encodings:

- Ed25519: raw 32-byte public key
- secp256k1: compressed SEC1 33-byte public key
- P-256: compressed SEC1 33-byte public key

## 5.4 Hash Function and Truncation

The initial recommendation is:

- `Hash Algorithm ID = 0x1`
- use `SHA-256(inception_key_bytes)`
- take the first 74 bits of the digest

Then fill those bits in big-endian order into the UUID:

- first `bit 52 .. bit 63`
- then skip Variant
- then `bit 66 .. bit 127`

Implementations MUST avoid overwriting:

- Version bits
- Variant bits

## 5.5 Generation Constraints

When generating a new `did:uuid` DID:

- the timestamp MUST reflect the Unix millisecond generation time and be truncated to 44 bits
- the Hash Algorithm ID MUST match the actual hash function in use
- the 74-bit hash fragment MUST come from the inception key's canonical byte representation

The following MUST be rejected as invalid:

- changing only the timestamp while keeping the same Hash Algorithm ID and 74-bit inception-key fragment
- using a Hash Algorithm ID that does not match the actual hash function in use
- using little-endian bit packing

Ordinary key rotation MUST NOT mint a new DID.  
A new DID MAY be minted only when the identity is unrecoverable and intentionally rebooted.

## 6. DID Document Model

## 6.1 Minimum Fields

A Contrix DID Document should include at least:

- `id`
- `alsoKnownAs`
- `inception_key`
- `verificationMethod`
- `authentication`
- `assertionMethod`
- `service`
- `key_log`

## 6.2 Suggested Service Types

The initial service types are:

- `ContrixIdentityRegistry`
- `ContrixRepo`
- `ContrixRelay`
- `ContrixIndex`
- `ContrixBlob`
- `ContrixCapabilities`
- `ContrixNotifications`

### 6.2.1 Who Stores the Identity Document

Contrix does not require DID documents to be written directly to a blockchain.  
The initial recommendation is:

- **the principal keeps signed local copies of identity state**
- **an open network of `ContrixIdentityRegistry` nodes stores resolvable online copies**
- **any third party may run read replicas / audit replicas**

That means:

- the principal's own repo SHOULD retain identity-related operations and checkpoints for audit and recovery
- the publicly resolvable current DID document SHOULD be hosted by multiple `ContrixIdentityRegistry` nodes
- clients MAY read from registries, replicas, local caches, or exported checkpoints, but MUST re-verify the signature chain

This splits storage responsibility into three layers:

1. the actor keeps raw signed state
2. registries provide online resolution and write entry points
3. replicas provide high-availability reads and external auditability

### 6.2.2 How Arbitrary Writes Are Prevented

No blockchain does not mean anybody can mutate identity state.

Contrix protects DID-document updates using:

- the DID self-certifying anchor: the DID must verify back to `inception_key`
- an append-only identity log: `key_log` is not rewriteable
- proof of current authority: updates must be authorized by the control-key set valid at that time, or by the recovery policy
- ordering constraints: each DID update SHOULD carry `prev_event_hash` and monotonic `seq`
- multi-replica validation: registries and replicas must independently validate events

Each identity update is recommended to be packaged as a `did_op`:

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "seq": 12,
  "prev_event_hash": "bafy...",
  "patch": {
    "add_authentication": [
      "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-4"
    ]
  },
  "proofs": [
    {
      "verificationMethod": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
      "jws": "..."
    }
  ]
}
```

Registries MUST reject:

- updates with invalid signatures
- updates whose `seq` goes backward, or reuses the same `seq` with different content
- updates whose `prev_event_hash` does not match the current head
- updates whose authority chain cannot be derived from `inception_key`

Therefore a single malicious registry may:

- deny service
- delay service
- lie about stale state

but it cannot make an **invalid update** become valid for correct clients.

### 6.2.3 How Fast Writes and Reads Work Without a Blockchain

Contrix does not chase "one global consensus chain for the whole network".  
Instead it requires:

- **an ordered append-only log per DID**
- **fast replication of that log across multiple registries / replicas**

Its performance model is therefore closer to:

- directory services
- transparency logs
- witness quorums

than to blockchains.

Recommended behavior:

- writes use normal HTTPS / XRPC requests
- a writer submits the update to `n` registry / witness nodes
- once the writer receives at least `k-of-n` valid receipts, the DID update is considered committed
- reads may come from any registry, read replica, local cache, or CDN

This has three benefits:

- write latency is closer to a normal replicated database than to block production time
- reads can be localized, cached, and CDN-served
- the network does not need one global total order across all DIDs

If a client needs strong read-after-write, a simple rule is:

- first query a registry that already returned a receipt
- or attach an expected `min_seq` / `expected_head` to the read

### 6.2.4 Suggested Roles for Registry, Witness, and Replica

To avoid sliding into a single-directory pattern, Contrix SHOULD distinguish:

- `registry writer`
- `witness`
- `read replica`

Where:

- a `registry writer` accepts DID updates and performs primary validation and distribution
- a `witness` may not serve general reads, but issues receipts for a given head
- a `read replica` focuses on read availability, caching, and auditability, and may not participate in write confirmation

The safest initial direction is:

- write confirmation requires receipts from multiple independent operators
- read resolution scales horizontally through read replicas

That is more decentralized than a "single primary directory + passive mirrors" pattern.

## 6.3 Current Control Keys and `key_log`

Contrix SHOULD split DID-document information into:

1. **anchor information that does not change across rotation**
2. **current control information that may change across rotation**

Where:

- `inception_key` is the immutable anchor
- `authentication` / `assertionMethod` describe the currently effective control-key set
- `key_log` is an append-only key-event log proving how the current control keys were reached from the inception key

That means:

- the current control keys do not need to directly equal the DID fragment
- but they MUST be traceable back to `inception_key` through `key_log`

## 6.4 `key_log` Event Model

The first version recommends these event types:

- `inception`
- `rotate`
- `recover`
- `deactivate`

Suggested fields:

```json
{
  "event_id": "cx:keyevt:01JS0KE000000000000000000",
  "seq": 2,
  "type": "rotate",
  "performed_at": "2026-04-25T08:00:00Z",
  "prev_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "next_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
  ],
  "authorized_by": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "reason": "routine_rotation",
  "proof": {
    "type": "JCSDetachedJWS",
    "verificationMethod": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1",
    "jws": "..."
  }
}
```

Rules:

- `seq` MUST increase monotonically
- old events MUST NOT be rewritten
- each `rotate` / `recover` event MUST be authorized by the control-key set valid at that time, or by the recovery policy
- a `deactivate` event means the DID no longer accepts new control writes

## 6.5 Recovery Model

To handle "the current private key is lost but the DID should remain the same", Contrix SHOULD support recovery mechanisms.

Suggested fields:

- `recovery_keys`
- or `recovery_policy`

Recovery semantics:

- if the current control key is lost but recovery keys remain available, the DID MUST stay unchanged
- the new control key is installed through `key_log.type = recover`
- that `recover` event must be verifiable under the recovery policy

If neither the current control key nor any valid recovery path exists, the DID SHOULD be treated as:

- `unrecoverable`
- or `deactivated`

## 6.6 Exceptional Identity Reboot

The normal `did:uuid` rule is:

- **change keys, not DID**

But a new DID MAY be created in exceptional cases:

- the old DID is unrecoverable
- the operator explicitly abandons the old DID and reboots identity
- a product or social layer wants to declare that the new identity succeeds the old one

Only in this **identity reboot** case should the spec use:

- `superseded_by`
- `supersedes`

They should not be used for routine key rotation.

If an old DID document can still be legitimately updated and sets `superseded_by`, that old document SHOULD enter a locked state.  
But for unrecoverable DIDs, clients MUST not assume that a bidirectional link will always be available.

## 6.7 DID Document Example

```json
{
  "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ],
  "inception_key": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
  "verificationMethod": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mki..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mks..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mkr..."
    }
  ],
  "authentication": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
  ],
  "assertionMethod": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
  ],
  "recovery_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1"
  ],
  "key_log": [
    {
      "event_id": "cx:keyevt:01JS0KE000000000000000000",
      "seq": 0,
      "type": "inception",
      "performed_at": "2026-04-25T08:00:00Z",
      "next_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1"
      ]
    },
    {
      "event_id": "cx:keyevt:01JS0KF000000000000000000",
      "seq": 1,
      "type": "rotate",
      "performed_at": "2026-05-01T09:00:00Z",
      "prev_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1"
      ],
      "next_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
      ],
      "authorized_by": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1"
      ],
      "reason": "routine_rotation"
    },
    {
      "event_id": "cx:keyevt:01JS0KG000000000000000000",
      "seq": 2,
      "type": "recover",
      "performed_at": "2026-05-10T11:00:00Z",
      "prev_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
      ],
      "next_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
      ],
      "authorized_by": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1"
      ],
      "reason": "key_loss"
    }
  ],
  "service": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#repo",
      "type": "ContrixRepo",
      "serviceEndpoint": "https://alice.example.com/cx/repo"
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#relay",
      "type": "ContrixRelay",
      "serviceEndpoint": "https://relay.example.net/cx"
    }
  ]
}
```

## 7. Handle Design

## 7.1 Relation to atprotocol

Contrix roughly follows atprotocol on handles:

1. handles are separate from DIDs
2. handles are the user-visible identifier
3. DID documents explicitly declare handle bindings
4. resolution requires bidirectional verification

## 7.2 Handle Form

The first version recommends DNS-like hostnames:

- `alice.example.com`
- `ops.example.com`
- `agent.release.example.com`

## 7.3 Handle Binding Inside the DID Document

Suggested form:

- `alsoKnownAs: ["contrix://alice.example.com"]`

Where:

- `contrix://<handle>` is the canonical handle URI form

A DID document SHOULD have at least one primary handle.  
If historical aliases need to be retained, `alsoKnownAs` may contain multiple handle URIs.

## 7.4 Display Fields in the Identity Profile

To make UI integration easier, Contrix SHOULD allow the identity profile to contain:

- `primary_handle`
- `display_name`
- `previous_handles`

Where:

- `primary_handle` is the current default user-facing handle
- `previous_handles` can be used to expose migration history

## 7.5 Handle Resolution

Handle resolution should follow an atprotocol-like dual path:

1. DNS TXT
2. HTTPS well-known

Recommended order:

1. query `_contrix.<handle>` TXT
2. if absent, fetch `https://<handle>/.well-known/contrix-did`

Well-known example:

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992"
}
```

## 7.6 Bidirectional Verification

After resolving a handle, the client MUST verify that the DID document's `alsoKnownAs` contains:

- `contrix://<handle>`

If this bidirectional verification fails, the handle MUST not be treated as a trusted binding.

## 8. Identity Profile

To avoid stuffing all collaboration details into the DID document, Contrix SHOULD allow an extended identity profile.

Suggested endpoint:

```text
GET /.well-known/contrix-identity.json
```

Example:

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "kind": "user",
  "primary_handle": "alice.example.com",
  "display_name": "Alice",
  "previous_handles": [
    "alice-old.example.com"
  ],
  "repo_endpoint": "https://alice.example.com/cx/repo",
  "relay_endpoints": [
    "https://relay.example.net/cx"
  ],
  "index_endpoints": [
    "https://index.example.net/cx"
  ],
  "blob_endpoint": "https://blob.example.net/cx",
  "capability_endpoint": "https://authz.example.net/cx",
  "updated_at": "2026-04-25T08:00:00Z"
}
```

## 9. Key and Recovery Model

A principal identity is not the same thing as one device or one process.

The initial model distinguishes:

- inception key
- principal signing key
- device key
- delegated agent key
- recovery key
- ephemeral execution key

### 9.1 Inception Key

Used for:

- generating `did:uuid`
- acting as the permanent anchor of identity history
- providing the start of the `key_log`

The public half of this key MUST remain permanently verifiable.  
It MAY cease to be used as an active control key.

### 9.2 Principal Signing Key

Used for:

- publishing formal identity documents
- executing ordinary control-key rotation
- issuing high-authority capabilities

### 9.3 Device Key

Used for:

- day-to-day commit/op signing
- client sync authentication

### 9.4 Delegated Agent Key

Used for:

- long-lived agents
- service bots
- CI / automation

It MUST carry scope and expiry.

### 9.5 Recovery Key

Used for:

- recovering from current-control-key loss
- forced switching after severe compromise
- authorizing `key_log.type = recover`

Recovery keys SHOULD be stored separately from day-to-day control keys.

### 9.6 Ephemeral Execution Key

Used for:

- a single run
- a single automation task
- a short-lived container or sandbox execution

## 10. Device and Agent Delegation

Device and agent delegations should express at least:

- `issuer`
- `subject_key`
- `subject_did` or execution subject
- `scope`
- `not_before`
- `expires_at`
- `revocation_ref`

## 11. Validation Rules

Any Contrix node accepting writes should validate at least:

1. the actor is a valid DID
2. the DID document resolves successfully
3. the UUID v8 bit layout of `did:uuid` is valid
4. the embedded Hash Algorithm ID is known and supported
5. re-hashing the document's `inception_key` with the hash function selected by that Hash Algorithm ID reproduces the leading 74-bit DID fragment
6. the `key_log` is append-only, `seq` is monotonic, and old events were not rewritten
7. the current control keys in `authentication` / `assertionMethod` can be derived from `inception_key` through valid `key_log` events
8. each `rotate` / `recover` event was authorized by the control-key set valid at that time, or by the recovery policy
9. if a `deactivate` event exists, later control writes MUST be rejected
10. if a device/agent/execution key is used, the delegation chain is complete
11. if DID state came from a registry / replica, its `head_event_hash` and receipt-set summary are not self-contradictory

Important note:

- the DID fragment is required to match the `inception_key`
- it is not required to directly match the currently active control key

## 12. Initial Design Decisions

The current draft recommends fixing:

- `did:uuid` as the default DID method
- `did:uuid` based on a custom UUID v8
- a UUID layout containing a 44-bit millisecond timestamp, 4-bit Hash Algorithm ID, and a 74-bit **inception-key** hash fragment
- big-endian hash filling and validation as mandatory
- ordinary key rotation MUST NOT change the DID
- current control keys may differ from the DID fragment, but must be provably derivable from `inception_key` through `key_log`
- `key_log` as the standard proof chain for rotation and recovery
- `superseded_by / supersedes` reserved for exceptional identity reboot after unrecoverable loss, not routine rotation
- an atprotocol-like handle model with `alsoKnownAs + primary_handle`

## 13. Further Work

The next round still needs:

- the wire-level resolution/distribution protocol for `did:uuid`
- a formal schema for `key_log` events and proof envelopes
- a formal `recovery_policy` grammar
- log compression / checkpoint rules for larger deployments
- a formal Handle ABNF
