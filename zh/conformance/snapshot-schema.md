# Snapshot, Chunk, and Encrypted Envelope Schema

## 1. 目标

Snapshot 用于快速 bootstrap Space 当前态。Snapshot 不是真相源；真相源仍然是签名 Operation / commit log。

## 2. Snapshot Manifest

```json
{
  "type": "snapshot_manifest",
  "snapshot_ref": "cx:snapshot:01JS0SN000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "reducer_profile": "cx.reducer.v1",
  "schema_profile_refs": ["cx.schema.core.v1"],
  "frontier": {
    "max_hlc": "01970e589d21-0004-a13f9c2e",
    "commit_hashes": ["sha256:..."]
  },
  "state_hash": "sha256:...",
  "chunks": [],
  "created_by": "did:web:index.example",
  "created_at": "2026-04-26T00:00:00Z",
  "signature": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:index.example#snapshot-key-1",
    "payload_hash": "sha256:...",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  }
}
```

## 3. Chunk Descriptor

```json
{
  "chunk_id": "cx:chunk:01JS0CH000000000000000000",
  "index": 0,
  "content_type": "application/json",
  "item_count": 1000,
  "byte_length": 524288,
  "digest": "sha256:...",
  "blob_ref": "cx:blob:sha256:..."
}
```

## 4. State Hash

`state_hash` MUST be Merkle root over canonical reducer output.  
Leaf hash:

```text
sha256(kind || ":" || id || ":" || sha256(canonical_json(object)))
```

## 5. Snapshot Signature

Manifest MUST contain exactly one normative `signature` field. `signature` MUST use the same detached proof shape as Event proof and MUST cover the canonical manifest payload excluding `signature`.

The signing DID MUST be one of:

- Space owner
- trusted index node
- witness quorum
- policy-approved snapshot issuer

Client MUST verify signature, signer authority, `state_hash`, frontier and every chunk digest before using snapshot. `proof`, `signed_by`, `generator_signature` and `state_signature` are not v1 snapshot manifest fields.

## 6. Encrypted Envelope

```json
{
  "type": "encrypted_envelope",
  "encryption_profile": "mls_rfc9420",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "epoch": 42,
  "cleartext_metadata": {
    "object_ref": "cx:message:...",
    "event_type": "cx.message.create"
  },
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:..."
}
```

Sync Service / index MAY route by `cleartext_metadata` but MUST NOT require plaintext content.
