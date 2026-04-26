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

Its value should point to one key id in `verification_method`.

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
- `inception_key`
- `verification_method`
- `authentication`
- `assertion_method`
- `service`
- `key_log`

A public-persona DID Document MAY include `also_known_as`.  
A pairwise DID Document for a specific verifier, organization, device, or bilateral relationship SHOULD NOT contain public handles, email addresses, organization usernames, or linkable historical aliases.

Contrix canonical JSON field names MUST use lowercase words joined with underscores.  
When interoperating with W3C DID Core native JSON / JSON-LD, adapters MUST preserve the raw document as-is and map field names into the normalized principal view:

| DID Core raw field | Contrix canonical field |
| --- | --- |
| `alsoKnownAs` | `also_known_as` |
| `verificationMethod` | `verification_method` |
| `assertionMethod` | `assertion_method` |
| `publicKeyMultibase` | `public_key_multibase` |
| `serviceEndpoint` | `service_endpoint` |

The same rule applies to W3C Verifiable Credentials raw fields in Contrix canonical representation: `credentialSubject -> credential_subject`, `validFrom -> valid_from`, `validUntil -> valid_until`, and `credentialStatus -> credential_status`. Raw standards documents can be preserved as external evidence, but internal protocol objects, indexes, policy inputs, and normalized views MUST use snake_case fields.

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
      "verification_method": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
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
- `authentication` / `assertion_method` describe the currently effective control-key set
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
    "verification_method": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1",
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
  "also_known_as": [
    "contrix://alice.example.com"
  ],
  "inception_key": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
  "verification_method": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "public_key_multibase": "z6Mki..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "public_key_multibase": "z6Mks..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "public_key_multibase": "z6Mkr..."
    }
  ],
  "authentication": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
  ],
  "assertion_method": [
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
      "service_endpoint": "https://alice.example.com/cx/repo"
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#relay",
      "type": "ContrixRelay",
      "service_endpoint": "https://relay.example.net/cx"
    }
  ]
}
```

## 6.8 External DID Method Compatibility

Contrix should not require every DID method to look natively like `did:uuid`.  
If Contrix wants to support `did:plc`, `did:web`, or future DID methods, it SHOULD use a three-layer model:

1. **method-specific resolution**
2. **normalized principal view**
3. **Contrix-specific capability binding**

That means:

- first resolve the raw DID document and history according to that DID method's own rules
- then map the result into one normalized structure that Contrix can consume uniformly
- finally decide whether that identity is sufficient for Contrix writes, recovery, service discovery, and authorization

### 6.8.1 Do Not Rewrite Foreign DID Documents

For external DID methods, Contrix SHOULD:

- preserve the raw DID document as-is
- preserve the raw history proof or resolution evidence
- construct a **normalized principal view** in local/cache space

Contrix MUST NOT:

- rewrite a foreign DID document into a fake `did:uuid` document
- pretend a foreign DID natively supports fields it does not actually define
- discard method-specific proof details

So this layer is not "replace the original document". It is "build a standardized projection on top of the original document".

### 6.8.2 Normalized Principal View

Contrix should define one internal normalized structure:

```json
{
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "did_method": "did:plc",
  "support_profile": "compatible",
  "raw_document_hash": "bafy...",
  "raw_history_ref": "https://plc.directory/did:plc:ewvi7nxzyoun6zhxrhs64oiz/log",
  "claimed_aliases": [
    "at://alice.example.com"
  ],
  "current_control_keys": [
    {
      "id": "did:plc:ewvi7nxzyoun6zhxrhs64oiz#atproto",
      "type": "Multikey",
      "public_key_multibase": "zQ3sh..."
    }
  ],
  "service_bindings": [
    {
      "service_type": "AtprotoPersonalDataServer",
      "service_endpoint": "https://pds.example.com"
    }
  ],
  "contrix_bindings": [],
  "evidence": {
    "resolver": "did:plc-adapter",
    "resolved_at": "2026-04-26T08:00:00Z"
  }
}
```

This is not a new DID-method standard. It is Contrix's internal consumption layer.

### 6.8.3 Why a Normalized View Is Needed

Different DID methods may have very different document formats, history models, and recovery models:

- `did:uuid` has `inception_key + key_log`
- `did:plc` has its own operation log and directory resolution logic
- `did:web` may only expose the current document without a strong history chain

Without this layer, upper Contrix modules would:

- add custom parsing branches for every DID method
- leak business logic into identity resolution
- lose a clean common input for capabilities, service discovery, and audit

So the right design is not "finish after a one-to-one field mapping". It is:

- **preserve the raw document**
- **emit one normalized standard view**
- **make Contrix business decisions on top of that normalized view**

## 6.9 Method Adapter

Each supported DID method SHOULD have its own `method adapter`.

The adapter is responsible for:

- parsing the raw DID document
- parsing method-specific history / proof material
- validating method-specific constraints
- generating the normalized principal view
- reporting the method's `support_profile` inside Contrix

Suggested minimum adapter output:

- `did`
- `did_method`
- `claimed_aliases`
- `current_control_keys`
- `service_bindings`
- `history_strength`
- `recovery_strength`
- `contrix_support_profile`
- `evidence`

### 6.9.1 `support_profile`

Contrix SHOULD at least distinguish:

- `native`
- `compatible`
- `limited`

Suggested meaning:

- `native`: natively supports Contrix anchor, history, recovery, and service-binding semantics
- `compatible`: can stably resolve DID, current control authority, and part of the history, but requires adapter mapping
- `limited`: can resolve identity and the current document, but lacks enough history, recovery, or service semantics for stronger interoperability

### 6.9.2 Positioning of `did:plc`

The most reasonable current position is:

- `did:plc` is `compatible` inside Contrix

Why:

- it has a stable DID
- it has its own history and resolution system
- but its document shape and service semantics are not designed as native Contrix primitives

So for `did:plc`, Contrix should:

- resolve the raw PLC document and history
- map them into the normalized principal view
- then decide which Contrix features are available

It should not require `did:plc` to directly look like `did:uuid`.

## 6.10 Service-Binding Mapping Rules

Successfully resolving an identity document does not mean every service entry inside it automatically becomes a Contrix service.

Contrix MUST distinguish:

- **identity-level service bindings**
- **Contrix-native service bindings**
- **external ecosystem bindings**

For example, with `did:plc`:

- `AtprotoPersonalDataServer` is an atproto ecosystem service
- it is not automatically equivalent to `ContrixRepo`
- it only becomes a Contrix service binding if an adapter or sidecar explicitly declares that the endpoint also speaks the Contrix interface

This rule matters.  
Otherwise the system would confuse "identity can be resolved" with "Contrix service discovery is already complete".

## 6.11 Contrix Identity Sidecar

When a foreign DID method does not contain enough Contrix-specific service information, Contrix SHOULD allow a sidecar document.

Suggested entry points:

- a custom service entry inside the DID document
- or `/.well-known/contrix-identity.json`

The sidecar can provide:

- Contrix repo / relay / index / blob / authz endpoints
- Contrix support profile information
- optional capability bootstrap information

Rules:

- the sidecar must not override the raw DID subject or control semantics
- the sidecar may only add Contrix-specific information after the DID subject has already been validated
- the sidecar itself SHOULD be signed by the currently valid control key

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

- `also_known_as: ["contrix://alice.example.com"]`

Where:

- `contrix://<handle>` is the canonical handle URI form

A DID document SHOULD have at least one primary handle.  
This rule applies only to public-persona DIDs.  
Pairwise DIDs, temporary DIDs, device DIDs, agent execution DIDs, and privacy-sensitive relationship DIDs SHOULD NOT be forced to bind a public handle.
If historical aliases need to be retained, `also_known_as` may contain multiple handle URIs.

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

After resolving a handle, the client MUST verify that the DID document's `also_known_as` contains:

- `contrix://<handle>`

If this bidirectional verification fails, the handle MUST not be treated as a trusted binding.

## 7.7 Handles Must Not Be Authorization Primary Keys

Handles are human-readable entry points, not authorization subjects.

The protocol layer MUST NOT use the following directly as grant subjects or Event actors:

- handles
- emails
- domain usernames
- organization namespace strings, such as `alice:google.com`

The correct model is:

```txt
grant subject = DID
authorization condition = verified claim / attestation
```

For example, `alice.google.com` may be a handle in the Google organization namespace, but it can only be a field inside a `verified_handle` or `org_membership` claim.

Authorization MUST check:

- whether the claim issuer is trusted
- whether the claim subject matches the current Actor DID
- whether the claim is within its validity window
- whether the claim has not been revoked
- whether the claim contents satisfy the grant constraint

Nodes MUST NOT infer organization access from string suffixes alone. `alice.google.com`, `alice:google.com`, or `alice@google.com` do not by themselves prove that the Actor still belongs to Google.

If a handle binding cannot be verified, expires, or is revoked, permissions depending on that binding claim naturally stop applying. Historical Events still keep the original DID as actor, so handle reuse cannot change historical accountability.

## 7.8 Privacy-Preserving Handles and Claim Proofs

Contrix MUST keep identity resolution separate from attribute proof.

A DID Document is only for verifiable control material, service discovery entry points, and the minimum routing data required by Contrix. It MUST NOT be used as a public attribute bundle for the subject. In particular, publicly or semi-publicly resolvable DID Documents MUST NOT directly list the following unless the subject intentionally wants them to be linked:

- email addresses, such as `alice@google.com`
- cross-organization handles, such as `alice:google.com` or `alice:facebook.com`
- account names, profile URLs, or login names from other ecosystems
- reused verification methods, dedicated service endpoints, or endpoint usernames that link multiple personas

When a subject needs to prove control of a handle or an organization attribute to a verifier, Contrix MUST use verifiable claims / attestations instead of placing every handle in the DID Document.

### 7.8.1 Standards Basis

This design aligns with the following W3C documents:

- DID Core's privacy section states that public DID Documents should avoid personal data; service endpoint URLs containing usernames can leak personal information; DID controllers can reduce correlation risk by using a pairwise DID for each relationship; and reusing the same verification method or dedicated endpoint across DID Documents weakens pairwise unlinkability. See [DID Core 10.1-10.6](https://www.w3.org/TR/did-1.0/#privacy-considerations).
- VC Data Model v2.0 defines selective disclosure and unlinkable disclosure, explains that zero-knowledge proof mechanisms can let a holder prove possession of a VC containing a value without disclosing the value, and requires securing mechanisms not to leak information that enables verifier correlation across presentations. See [VC Data Model 5.7](https://www.w3.org/TR/vc-data-model-2.0/#zero-knowledge-proofs) and [8.9](https://www.w3.org/TR/vc-data-model-2.0/#the-principle-of-data-minimization).
- Data Integrity BBS Cryptosuites v1.0 defines `bbs-2023` base proofs, derived proofs, selective pointers, anonymous holder binding, and credential-bound pseudonyms, and states that BBS signatures directly provide selective disclosure and unlinkable proofs. See [VC DI BBS](https://www.w3.org/TR/vc-di-bbs/).

### 7.8.2 Recommended Protocol Pattern

For cross-organization handles such as `alice@google.com` and `alice@facebook.com`, Contrix recommends this pattern:

1. Alice uses a Google-specific DID for the Google relationship, for example `did:uuid:g_pairwise...`.
2. Alice uses a separate Facebook-specific DID for the Facebook relationship, for example `did:uuid:f_pairwise...`.
3. The two DIDs MUST NOT reuse the same verification method, dedicated service endpoint, endpoint username, `also_known_as`, or public profile URL.
4. Google, or a trusted issuer, issues a `ContrixHandleCredential` or `ContrixOrgMembershipCredential` to `did:uuid:g_pairwise...`.
5. Facebook, or a trusted issuer, issues a separate credential to `did:uuid:f_pairwise...`.
6. When Alice proves identity to a Google verifier, the wallet only generates a verifiable presentation containing Google-related claims.
7. A Google verifier MUST NOT require Alice to disclose a Facebook credential, Facebook DID, cross-domain subject identifier, or any other unnecessary handle.

If the verifier only needs to know that the subject has a valid account in the Google organization, the presentation SHOULD disclose an abstract claim:

```json
{
  "type": ["VerifiableCredential", "ContrixOrgMembershipCredential"],
  "issuer": "did:web:google.example",
  "credential_subject": {
    "id": "did:uuid:g_pairwise...",
    "org": "did:web:google.example",
    "member": true,
    "handle_verified": true
  },
  "valid_from": "2026-04-26T00:00:00Z",
  "valid_until": "2026-07-26T00:00:00Z",
  "credential_status": {
    "type": "PrivacyPreservingStatusList"
  }
}
```

If the verifier truly needs to display the Google handle, the presentation MAY disclose:

```json
{
  "credential_subject": {
    "id": "did:uuid:g_pairwise...",
    "handle": "alice@google.com",
    "handle_verified": true
  }
}
```

That disclosure MUST be bound to a single verifier challenge/domain and MUST NOT automatically disclose any other organization handle.

### 7.8.3 Presentation Request

Verifier requests MUST use minimum-disclosure requests and MUST NOT request "all aliases" or "all accounts".

Suggested request shape:

```json
{
  "type": "ContrixPresentationRequest",
  "audience": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "accepted_issuers": [
    "did:web:google.example",
    "did:web:trusted-hr.example"
  ],
  "required_claims": [
    {
      "type": "ContrixOrgMembershipCredential",
      "constraints": {
        "org": "did:web:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_subject_identifier"
  ]
}
```

Wallets MUST show the holder exactly which claims will be disclosed.  
Wallets SHOULD reject or warn on requests for unrelated handles, global subject identifiers, credential ids, or unnecessary demographic attributes.

### 7.8.4 Proof Mechanisms

Contrix SHOULD support at least two proof profiles:

- `sd-jwt-vc`: suitable for broad JOSE interoperability and claim-level selective disclosure.
- `vc-di-bbs-2023`: REQUIRED for high-privacy profiles that need unlinkable derived proofs or non-correlatable presentation behavior.

When `vc-di-bbs-2023` is used:

- the issuer creates a base proof and gives it only to the holder
- the holder creates a derived proof using only the selected claim pointers
- the verifier validates the derived proof against the issuer public key and verifier challenge
- the verifier MUST NOT receive undisclosed claims, the base proof, or unrelated credential identifiers

The implementation profile MUST pin the exact cryptosuite version and test vectors used for interoperability. Because BBS support is still evolving across implementations, Contrix deployments MAY start with `sd-jwt-vc` for broad compatibility, but MUST NOT claim unlinkability unless the selected proof mechanism actually provides it.

### 7.8.5 Revocation and Status Checks

Credential status checks MUST be designed to avoid verifier-driven correlation.

Contrix implementations SHOULD use privacy-preserving status lists, cached status material, or verifier-independent revocation proofs. They SHOULD NOT require the verifier to submit a unique credential id, subject DID, or handle to a centralized status endpoint during every presentation.

### 7.8.6 Authorization Semantics

Capability policy MAY depend on verified claims, but the grant subject remains a DID.

Correct:

```txt
grant subject = did:uuid:g_pairwise...
condition = has valid ContrixOrgMembershipCredential where org = did:web:google.example
```

Incorrect:

```txt
grant subject = alice@google.com
```

If the holder later presents a different pairwise DID for a different organization, the verifier MUST treat it as a separate privacy context unless the holder explicitly supplies a linking proof.

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
  "claims_endpoint": "https://alice.example.com/cx/claims",
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

## 8.1 Claim Discovery

Identity Profile MAY expose `claims_endpoint` for discovering claims held or publicly presented by this DID.

Whether a claim can be used for authorization depends on whether the resource Space / Policy trusts the claim issuer, not on the subject presenting it.

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

## 10. Accountable Actor

Contrix distinguishes the **identity subject**, the **accountable subject**, and the **authorization subject**.

Some Actors have their own DID and can sign directly, but still need a traceable responsible or guardian party. Examples include:

- AI agents
- service bots
- CI / automation
- minors
- protected-user accounts
- enterprise-managed accounts
- third-party integration accounts

The protocol SHOULD support `accountability` metadata instead of special-casing agent ownership.

Suggested minimal shape:

```json
{
  "actor_id": "did:web:agent.copy.example.com",
  "actor_type": "agent",
  "accountability": {
    "mode": "accountable",
    "responsible_actor_id": "did:web:alice.example.com",
    "controller_actor_ids": [
      "did:web:alice.example.com"
    ],
    "guardian_actor_ids": [],
    "operator_actor_ids": [
      "did:web:agents.vendor.example.com"
    ],
    "not_before": "2026-04-22T00:00:00Z",
    "expires_at": null,
    "revocation_ref": "cx:rel:01JS0RV000000000000000000"
  }
}
```

Field semantics:

- `responsible_actor_id`: the person, organization, or team ultimately accountable for the Actor's behavior
- `controller_actor_ids`: Actors that can configure, suspend, deactivate, or authorize the Actor
- `guardian_actor_ids`: Actors with guardian/consent responsibility for minors or protected Actors
- `operator_actor_ids`: Actors that host, run, or provide infrastructure for the Actor
- `revocation_ref`: verifiable reference for revocation or accountability changes

Protocol nodes MUST NOT interpret accountability as capability.

That means:

- an agent having an owner does not automatically inherit the owner's permissions
- a minor having a guardian does not automatically give the guardian full access to the minor's private content
- an operator hosting an agent does not automatically act on behalf of that agent

Those permissions must still be expressed through explicit capability grants.

Accountability is used for traceability, emergency control, high-risk approval, compliance/guardian constraints, and audit display.

## 11. Device, Agent, and Delegated Actor Delegation

Device, agent, automation-account, and delegated-Actor delegations should express at least:

- `issuer`
- `subject_key`
- `subject_did` or execution subject
- `scope`
- `not_before`
- `expires_at`
- `revocation_ref`
- `accountability_ref`, if the subject is not fully self-accountable
- `approval_policy_ref`, if some actions require controller / guardian / responsible-actor approval

## 12. Validation Rules

Any Contrix node accepting writes should validate at least:

1. the actor is a valid DID
2. the DID document resolves successfully
3. the UUID v8 bit layout of `did:uuid` is valid
4. the embedded Hash Algorithm ID is known and supported
5. re-hashing the document's `inception_key` with the hash function selected by that Hash Algorithm ID reproduces the leading 74-bit DID fragment
6. the `key_log` is append-only, `seq` is monotonic, and old events were not rewritten
7. the current control keys in `authentication` / `assertion_method` can be derived from `inception_key` through valid `key_log` events
8. each `rotate` / `recover` event was authorized by the control-key set valid at that time, or by the recovery policy
9. if a `deactivate` event exists, later control writes MUST be rejected
10. if a device/agent/execution key is used, the delegation chain is complete
11. if DID state came from a registry / replica, its `head_event_hash` and receipt-set summary are not self-contradictory
12. if the Actor is declared accountable / guarded / operated, its accountability relation is valid at operation time
13. if the action requires guardian / controller / responsible-actor approval, the approval evidence is complete and unexpired
14. if an action depends on a handle, organization membership, email control, or another attribute, the corresponding claim / presentation must be verified instead of trusting strings in the DID Document directly
15. if a presentation claims selective disclosure or unlinkable proof behavior, the proof profile, issuer key, challenge, domain, audience, status, and disclosed claim set must be verified
16. if a DID is marked as a pairwise/private context, clients MUST NOT require it to publish `also_known_as` and MUST NOT automatically merge it with other DIDs as the same subject

Important note:

- the DID fragment is required to match the `inception_key`
- it is not required to directly match the currently active control key
- DID Documents should not be treated as cross-organization identity profiles; cross-organization attributes should be proven through minimum-disclosure presentations as needed

## 13. Initial Design Decisions

The current draft recommends fixing:

- `did:uuid` as the default DID method
- `did:uuid` based on a custom UUID v8
- a UUID layout containing a 44-bit millisecond timestamp, 4-bit Hash Algorithm ID, and a 74-bit **inception-key** hash fragment
- big-endian hash filling and validation as mandatory
- ordinary key rotation MUST NOT change the DID
- current control keys may differ from the DID fragment, but must be provably derivable from `inception_key` through `key_log`
- `key_log` as the standard proof chain for rotation and recovery
- `superseded_by / supersedes` reserved for exceptional identity reboot after unrecoverable loss, not routine rotation
- an atprotocol-like handle model with `also_known_as + primary_handle`
- public-persona DIDs MAY use `also_known_as` for handle binding; pairwise/private DIDs SHOULD NOT be forced to publish handles
- dynamic attributes such as handles, organization membership, and email control must be expressed through VCs / attestations / presentations
- high-privacy scenarios SHOULD use selective disclosure; unlinkable presentation claims require a proof profile that actually supports unlinkability, such as `vc-di-bbs-2023`
- Accountable Actor as a general model, not only for agents, also for minors, managed accounts, and automation subjects
- accountability is not capability; permissions must still be explicitly granted

## 14. Further Work

The next round still needs:

- the wire-level resolution/distribution protocol for `did:uuid`
- a formal schema for `key_log` events and proof envelopes
- a formal `recovery_policy` grammar
- a formal schema for `accountability` and guardian/controller/operator relations
- a formal approval proof envelope schema
- formal schemas for `ContrixPresentationRequest`, `ContrixOrgMembershipCredential`, `ContrixHandleCredential`, and privacy-preserving status lists
- conformance test vectors for the `sd-jwt-vc` and `vc-di-bbs-2023` proof profiles
- log compression / checkpoint rules for larger deployments
- a formal Handle ABNF
