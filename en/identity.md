# Identity Layer Draft

## 1. Goal

Contrix New uses **DIDs as the stable identity root** and follows an atprotocol-inspired pattern of "handle entry point + DID root anchor + document-based service discovery", while defining its own DID generation and succession rules.

The identity layer must solve:

- stable identification for humans, organizations, agents, and services
- binding identity anchor keys to service endpoints
- handle migration without breaking historical references
- device delegation, agent delegation, key recovery, and identity succession
- generating a new DID when the identity anchor public key changes, and linking old and new identities through documents

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

- repo endpoints
- relay endpoints
- index endpoints
- blob endpoints
- capability endpoints
- notification endpoints

from the DID document.

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

## 3.3 DID vs Anchor Public Key

A Contrix DID is not a random identifier.  
It MUST be jointly determined by:

1. the generation timestamp
2. the hash algorithm identifier
3. a hash fragment of the identity anchor public key

This means:

- you cannot manufacture a "new identity" by changing only the timestamp while keeping the same hash-algorithm identifier and key-hash fragment
- if the identity anchor public key changes, the DID must also change
- if only a certificate is reissued while the anchor public key stays the same, the DID MUST NOT change

## 4. UUID v8 Bit Layout

The default Contrix DID suffix uses a 128-bit UUID v8 with the following custom bit layout.

### 4.1 Bit Segments

- first 44 bits: Unix millisecond timestamp
- next 4 bits: Hash Algorithm ID
- next 4 bits: Version, fixed to `0x8`
- next 12 bits: beginning of the public-key hash fragment
- next 2 bits: Variant, fixed to `0b10`
- final 62 bits: continuation of the public-key hash fragment

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

## 5.2 Identity Anchor Public Key

Every `did:uuid` DID Document MUST designate exactly one **identity anchor public key**.

Suggested field name:

- `anchor_key`

Its value should point to one key id in `verificationMethod`.

That key is used for:

- generating the DID suffix
- acting as the root anchor for identity succession validation

## 5.3 Hash Input Rule

The public-key hash fragment inside the DID MUST be derived from the **canonical byte representation of the identity anchor public key**, not from the full certificate bytes.

This is important because:

- certificate metadata changes must not create meaningless DID churn
- only anchor public-key changes should cause DID changes

Suggested canonical encodings:

- Ed25519: raw 32-byte public key
- secp256k1: compressed SEC1 33-byte public key
- P-256: compressed SEC1 33-byte public key

## 5.4 Hash Function and Truncation

The initial recommendation is:

- `Hash Algorithm ID = 0x1`
- use `SHA-256(anchor_key_bytes)`
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
- the 74-bit hash fragment MUST come from the anchor key's canonical byte representation

The following MUST be rejected as invalid:

- changing only the timestamp while keeping the same Hash Algorithm ID and 74-bit key-hash fragment
- using a Hash Algorithm ID that does not match the actual hash function in use
- using little-endian bit packing

## 6. DID Document Model

## 6.1 Minimum Fields

A Contrix DID Document should include at least:

- `id`
- `alsoKnownAs`
- `anchor_key`
- `verificationMethod`
- `authentication`
- `assertionMethod`
- `service`

## 6.2 Suggested Service Types

The initial service types are:

- `ContrixRepo`
- `ContrixRelay`
- `ContrixIndex`
- `ContrixBlob`
- `ContrixCapabilities`
- `ContrixNotifications`

## 6.3 Identity-succession Fields

To support a new DID after an anchor-key change, the spec defines two fields:

- `superseded_by`
- `supersedes`

Their meaning is:

- `superseded_by`: stored in the old DID document, meaning this identity has been replaced by a new DID
- `supersedes`: stored in the new DID document, meaning this identity originates from the previous DID

### 6.3.1 Why Not `transfer`

The spec does not use `transfer` as the formal field name because that sounds like ownership transfer.

The real semantics here are:

- migration after compromise
- recovery after key leakage
- a new DID caused by anchor-key rotation

`superseded_by / supersedes` is therefore more precise.

## 6.4 Lock Rule

Once a DID document sets `superseded_by`, the document enters the **locked** state.

In the locked state:

- no fields may change afterward
- the handle may not change
- service endpoints may not change
- `verificationMethod` may not change
- no extension fields may change

Implementations SHOULD serve logically identical document contents once locked.  
At the protocol level, the document is frozen.

## 6.5 Valid Old/New DID Relation

When a new DID document claims `supersedes = <old_did>`, the following SHOULD hold:

1. the new DID uses a different anchor key
2. the new DID therefore carries a different 74-bit key-hash fragment
3. the new DID timestamp is not earlier than the old one
4. the old DID document should eventually set `superseded_by = <new_did>`

In other words:

- the new DID must not be just the old DID plus a new timestamp
- the new DID must embody a new anchor-key identity

## 6.6 DID Document Example

```json
{
  "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ],
  "anchor_key": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#anchor-1",
  "supersedes": "did:uuid:0196fd30-70ab-8121-8b12-8f0d7c882110",
  "verificationMethod": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#anchor-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mki..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mks..."
    }
  ],
  "authentication": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "assertionMethod": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
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

Frozen old-document example:

```json
{
  "id": "did:uuid:0196fd30-70ab-8121-8b12-8f0d7c882110",
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ],
  "anchor_key": "did:uuid:0196fd30-70ab-8121-8b12-8f0d7c882110#anchor-1",
  "superseded_by": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "locked": true
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

## 9. Key Model

A principal identity is not the same thing as one device or one process.

The initial model distinguishes:

- identity anchor key
- principal signing key
- device key
- delegated agent key
- ephemeral execution key

### 9.1 Identity Anchor Key

Used for:

- generating `did:uuid`
- anchoring identity succession
- proving the old/new DID relationship

If this key changes, the DID must change as well.

### 9.2 Principal Signing Key

Used for:

- publishing formal identity documents
- issuing high-authority capabilities
- delegating to devices or agents

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

### 9.5 Ephemeral Execution Key

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
5. re-hashing the document's `anchor_key` with the hash function selected by that Hash Algorithm ID reproduces the leading 74-bit DID fragment
6. if the document has `superseded_by`, it is locked and must not continue mutating
7. if the document has `supersedes`, the new DID must not be a timestamp-only variation of the old DID
8. if a device/agent/execution key is used, the delegation chain is complete

## 12. Initial Design Decisions

The current draft recommends fixing:

- `did:uuid` as the default DID method
- `did:uuid` based on a custom UUID v8
- a UUID layout containing a 44-bit millisecond timestamp, 4-bit Hash Algorithm ID, and 74-bit anchor-key hash fragment
- big-endian hash filling and validation as mandatory
- `superseded_by` on old identities
- `supersedes` on new identities
- locking old documents once `superseded_by` is set
- an atprotocol-like handle model with `alsoKnownAs + primary_handle`

## 13. Further Work

The next round still needs:

- the wire-level resolution/distribution protocol for `did:uuid`
- a formal schema for `anchor_key` and document signature chains
- a formal reciprocal-validation flow for `supersedes/superseded_by`
- a formal Handle ABNF
