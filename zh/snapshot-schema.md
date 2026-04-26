# Snapshot, Chunk, and Encrypted Envelope Schema Draft

## 1. 目标

Snapshot 用于快速 bootstrap Space 当前态。Snapshot 不是真相源；真相源仍然是签名 op / commit log。

## 2. Snapshot Manifest

```json
{
  "type": "snapshot_manifest",
  "snapshot_id": "cx:snapshot:01JS0SN000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "reducer_profile": "cx.reducer.v1",
  "schema_profile": "cx.schema.core.v1",
  "frontier": {
    "max_hlc": "01970e589d21-0004-a13f9c2e",
    "commit_hashes": ["sha256:..."]
  },
  "state_hash": "sha256:...",
  "chunks": [],
  "created_by": "did:web:index.example",
  "created_at": "2026-04-26T00:00:00Z",
  "proof": {}
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

Manifest MUST be signed by one of:

- Space owner
- trusted index node
- witness quorum
- policy-approved snapshot issuer

Client MUST verify signature and `state_hash` before using snapshot.

## 6. Encrypted Envelope

```json
{
  "type": "encrypted_envelope",
  "encryption_profile": "mls_rfc9420",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "epoch": 42,
  "cleartext_metadata": {
    "entity_id": "cx:entity:...",
    "event_type": "message.create"
  },
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:..."
}
```

Relay / index MAY route by `cleartext_metadata` but MUST NOT require plaintext content.
