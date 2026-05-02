# Snapshot, Chunk, and Encrypted Envelope Schema

## 1. 目标

Snapshot 用于快速 bootstrap Space 当前态。Snapshot 不是真相源；真相源仍然是 signed Event Envelope 和可验证 Event history。

## 2. Snapshot Manifest

```json
{
  "type": "snapshot_manifest",
  "snapshot_ref": "cx:snapshot:01js0sn0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "reducer_profile": "cx.reducer.v1",
  "schema_profile_refs": ["cx.profile.core_event_store.v1"],
  "frontier": {
    "event_ids": ["cx:event:01js0ev0000000000000000000"],
    "timeline_hlc": "01970e589d21-0004-a13f9c2e"
  },
  "event_set_commitment": {
    "algorithm": "merkle_event_set_v1",
    "root": "sha256:...",
    "covered_event_count": 42000,
    "covered_frontier": ["cx:event:01js0ev0000000000000000000"]
  },
  "state_hash": "sha256:...",
  "chunks": [
    {
      "chunk_ref": "cx:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "size_bytes": 524288
    }
  ],
  "verification_hints": {
    "inclusion_proof_url": "https://server.example/snapshots/01js0sn/proofs",
    "challenge_window_seconds": 86400,
    "witness_quorum": 2,
    "conflict_records_digest": "sha256:...",
    "soft_failed_digest": "sha256:...",
    "quarantined_digest": "sha256:..."
  },
  "created_by": "did:web:server.example",
  "created_at": "2026-04-26T00:00:00Z",
  "signature": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:server.example#snapshot-key-1",
    "payload_hash": "sha256:...",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  }
}
```

## 3. Chunk Descriptor

```json
{
  "chunk_ref": "cx:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "size_bytes": 524288
}
```

Chunk descriptor 中的 `chunk_ref` 指向一个 snapshot chunk payload。Payload 本身是 canonical JSON，最小格式如下：

```json
{
  "type": "snapshot_chunk",
  "snapshot_ref": "cx:snapshot:01js0sn0000000000000000000",
  "index": 0,
  "reducer_profile": "cx.reducer.v1",
  "items": [
    {
      "kind": "card",
      "id": "cx:flow:01js0ca0000000000000000000",
      "object": {
        "id": "cx:flow:01js0ca0000000000000000000",
        "type": "flow",
        "kind": "card",
        "schema": "cx.schema.flow.v1"
      },
      "source_event_id": "cx:event:01js0ev0000000000000000000"
    }
  ],
  "conflict_records": [],
  "soft_failed": [],
  "quarantined": []
}
```

规则：

- `items` MUST 按 `(kind, id)` canonical byte order 排序。
- `object` 是该 reducer profile 在 snapshot frontier 下的 materialized canonical object，包括 active object、active Relation、以及 reducer profile 声明需要保留的 tombstone / redaction verification stub。
- `source_event_id` 是产生该 materialized object 当前版本的最后 accepted Event；字段级 merge 时 MAY 指向最后改变该对象任一字段的 Event。
- chunk `sha256` MUST 覆盖 chunk payload 的 canonical JSON bytes。Manifest `state_hash` 不直接覆盖 descriptor 文本，而覆盖下节定义的 reducer output leaves。
- `conflict_records`、`soft_failed` 和 `quarantined` 可为空，但 high-assurance snapshot MUST 通过 manifest `verification_hints` 提交这些集合的 digest，不能静默隐藏影响授权、可见性、E2EE epoch 或对象状态的非 accepted 输入。

## 4. State Hash

`state_hash` MUST be Merkle root over canonical reducer output.  
Leaf hash:

```text
sha256(kind || ":" || id || ":" || sha256(canonical_json(object)))
```

Leaf 集合 MUST 与所有 chunk `items[].object` 一一对应。Merkle leaf 排序使用 `(kind, id)` canonical byte order；同一 `(kind,id)` 不得出现多个 leaf。不同 reducer profile 产生的 `state_hash` 不保证兼容，Snapshot consumer MUST 要求 `reducer_profile` 精确匹配或使用明确声明的 compatible profile。

## 5. Snapshot Signature

Manifest MUST contain exactly one normative `signature` field. `signature` MUST use the same detached proof shape as Event proof and MUST cover the canonical manifest payload excluding `signature`.

The signing DID MUST be one of:

- Space owner
- trusted snapshot issuer
- witness quorum
- policy-approved snapshot issuer

Client MUST verify signature, signer authority, `state_hash`, frontier, `event_set_commitment` and every chunk digest before using snapshot. `proof`, `signed_by`, `generator_signature` and `state_signature` are not v1 snapshot manifest fields.

## 6. Inclusion and Omission Defense

Snapshot signer authority only proves who signed the reduced state; it does not by itself prove the signer included every accepted Event it should have included. For that reason v1 snapshot manifests MUST carry `event_set_commitment`.

`event_set_commitment.root` commits to the ordered set of Event Envelope IDs and canonical event hashes covered by the snapshot frontier. Implementations MUST support one of:

- `ordered_event_id_sha256_v1`: SHA-256 over canonical JSON array entries `{event_id,event_hash,actor_id,actor_seq,hlc}` sorted by `(actor_id, actor_seq, event_id)`.
- `merkle_event_set_v1`: Merkle root over the same canonical entries.

High-assurance profiles MUST support inclusion challenge:

1. Client asks the snapshot issuer or witness for inclusion proofs for sampled Event IDs and actor sequence ranges.
2. Issuer returns Merkle branches or ordered-set slices bound to `event_set_commitment.root`.
3. Client rejects or quarantines the snapshot if any sampled accepted Event is missing, if an actor sequence range has a gap not represented in `soft_failed` / `quarantined`, or if the proof root differs.

`verification_hints.conflict_records_digest`, `soft_failed_digest` and `quarantined_digest` commit to non-accepted or unresolved inputs. A snapshot MUST NOT silently hide conflict, soft-fail or quarantine records that affect authorization, visibility, E2EE epoch or object state.

## 7. Encrypted Envelope

```json
{
  "type": "encrypted_envelope",
  "encryption_profile": "mls_rfc9420",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "epoch": 42,
  "cleartext_metadata": {
    "object_ref": "cx:message:...",
    "event_type": "cx.message.create"
  },
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:..."
}
```

Sync Service MAY route by `cleartext_metadata` but MUST NOT require plaintext content.
