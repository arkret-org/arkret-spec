---
title: Snapshot, Chunk, and Encrypted Envelope Schema
sidebar:
  label: Snapshot & Envelope
---

## 1. 目标

Snapshot 用于快速 bootstrap Space 当前态。Snapshot 不是真相源；真相源仍然是 signed Event Envelope 和可验证 Event history。

## 2. Snapshot Manifest

```json
{
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

Snapshot-assisted pruning 只能删除或压缩某个存储边界内的 raw payload / derived material；它不删除协议历史事实。若实现因 retention、track archive、Space tombstone 或 hard erasure 裁剪了对象内容，snapshot chunk MUST 继续包含 reducer profile 声明的最小 verification stub，或在 `soft_failed` / `quarantined` / conflict digest 中提交其存在。Consumer 不得把 snapshot 中缺少 stub 的对象解释为“从未存在”，除非 event-set commitment 和 reducer profile 明确证明该对象不在 covered frontier 中。

## 4. State Hash

`state_hash` MUST be Merkle root over canonical reducer output.  
Leaf hash:

```text
sha256(kind || ":" || id || ":" || sha256(canonical_json(object)))
```

Leaf 集合 MUST 与所有 chunk `items[].object` 一一对应。Merkle leaf 排序使用 `(kind, id)` canonical byte order；同一 `(kind,id)` 不得出现多个 leaf。不同 reducer profile 产生的 `state_hash` 不保证可比较，Snapshot consumer MUST 要求 `reducer_profile` 精确匹配或使用明确声明的 equivalent profile。

## 5. Snapshot Signature

Manifest MUST contain exactly one normative `signature` field. `signature` MUST use the same detached proof shape as Event proof and MUST cover the canonical manifest payload excluding `signature`.

The signing DID MUST be one of:

- Space owner
- Space creator or active Space admin
- trusted snapshot issuer
- witness quorum
- policy-approved snapshot issuer

Client MUST verify signature, signer authority, `state_hash`, frontier, `event_set_commitment` and every chunk digest before using snapshot. Signer authority MUST be evaluated as of the manifest `created_at`, using accepted Space auth state that covers the snapshot frontier and all relevant admin / snapshot-issuer grant or revoke events known up to `created_at`. If the signer was revoked before `created_at`, or the verifier cannot establish revoke freshness for the signer authority, the snapshot MUST be quarantined or rejected with `snapshot_issuer_revoked`.

**Maximum acceptance window (normative)**: a manifest is acceptable for snapshot bootstrap only if **all** of the following hold at adoption time:

- `(now - manifest.created_at) ≤ snapshot_max_acceptance_age_ms`. Default `snapshot_max_acceptance_age_ms = 2_592_000_000` (30 days). `security_class=high_assurance` Spaces MUST tighten to ≤ `604_800_000` (7 days). Beyond the window, even a previously valid snapshot MUST be rejected — the client MUST request a fresh manifest, since auth state and policy will have drifted enough that even a legitimate old snapshot cannot represent current state safely.
- The signer's authority chain (Space owner / admin / trusted issuer / witness quorum membership) is still **resolvable** under current auth state. If the chain has been pruned (e.g. by Space tombstone, governance reset, or auth-chain compaction beyond the manifest era) the snapshot MUST be rejected.
- `(now - signer.revoked_at) < 0` if the signer has been revoked at all. A revoke effective strictly **after** `created_at` does NOT retroactively invalidate the manifest, but the client MUST always replay events after the snapshot frontier before using current state for new writes.

`proof`, `signed_by`, `generator_signature` and `state_signature` are not v1 snapshot manifest fields.

## 6. Inclusion and Omission Defense

Snapshot signer authority only proves who signed the reduced state; it does not by itself prove the signer included every accepted Event it should have included. For that reason v1 snapshot manifests MUST carry `event_set_commitment`.

`event_set_commitment.root` commits to the ordered set of Event Envelope IDs and canonical event hashes covered by the snapshot frontier. Implementations MUST support one of:

- `ordered_event_id_sha256_v1`: SHA-256 over canonical JSON array entries `{event_id,event_hash,actor_id,actor_seq,hlc}` sorted by `(actor_id, actor_seq, event_id)`.
- `merkle_event_set_v1`: Merkle root over the same canonical entries.

High-assurance profiles MUST support inclusion challenge. Spaces with `security_class=high_assurance` MUST execute it before adopting any snapshot; other profiles SHOULD.

The challenge wire shape (POSTed to `verification_hints.inclusion_proof_url`):

Request body:

```json
{
  "snapshot_ref": "cx:snapshot:01js0sn0000000000000000000",
  "challenge_id": "cx:txn:01js0ch0000000000000000000",
  "samples": [
    {
      "kind": "event_id",
      "event_ids": ["cx:event:01js0ev0000000000000000000", "cx:event:01js0ev0000000000000000001"]
    },
    {
      "kind": "actor_seq_range",
      "actor_id": "did:webvh:...:alice.example",
      "from_seq": 100,
      "to_seq": 199
    }
  ],
  "issued_at": "2026-04-26T00:00:00Z"
}
```

Response body:

```json
{
  "snapshot_ref": "cx:snapshot:01js0sn0000000000000000000",
  "challenge_id": "cx:txn:01js0ch0000000000000000000",
  "commitment_algorithm": "merkle_event_set_v1",
  "commitment_root": "sha256:...",
  "proofs": [
    {
      "kind": "event_id",
      "event_id": "cx:event:01js0ev0000000000000000000",
      "merkle_branch": ["sha256:...", "sha256:..."],
      "leaf_canonical_entry": {
        "event_id": "cx:event:01js0ev0000000000000000000",
        "event_hash": "sha256:...",
        "actor_id": "did:webvh:...:alice.example",
        "actor_seq": 100,
        "hlc": "01970e589d21-0004-a13f9c2e"
      }
    },
    {
      "kind": "actor_seq_range",
      "actor_id": "did:webvh:...:alice.example",
      "from_seq": 100,
      "to_seq": 199,
      "ordered_set_slice": [
        {"event_id": "cx:event:...", "event_hash": "sha256:...", "actor_seq": 100, "hlc": "..."},
        "..."
      ],
      "gap_attribution": [
        {"actor_seq": 142, "category": "soft_failed", "digest_index": 7},
        {"actor_seq": 167, "category": "quarantined", "digest_index": 3}
      ]
    }
  ],
  "issuer_signature": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:server.example#snapshot-key-1",
    "payload_hash": "sha256:...",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  }
}
```

Sampling and verification rules (normative):

1. **Random sampling**: client MUST draw samples independent of issuer hints. For event_id samples, draw `n ≥ max(20, ceil(log2(covered_event_count)))` distinct IDs uniformly from the client's local Event set in the snapshot frontier. For actor_seq_range samples, draw at least 3 ranges of length 100 each from distinct actors known to be active in the snapshot.
2. **Branch verification**: each `proofs[i].merkle_branch` MUST verify under `commitment_algorithm` against `commitment_root`; `commitment_root` MUST equal the manifest's `event_set_commitment.root` (no rebinding allowed).
3. **Gap attribution**: for each missing `actor_seq` within a sampled range, the response MUST cite an entry in `verification_hints.{soft_failed_digest, quarantined_digest, conflict_records_digest}` (`digest_index` is the position in the digest's commitment list) — silent gaps are forbidden.
4. **Signature**: `issuer_signature` MUST be from a DID listed in §5 (Space owner / creator / admin / trusted snapshot issuer / witness quorum) and verifiable as of manifest `created_at`.
5. **Failure**: if any sampled accepted Event is absent, any branch fails verification, any gap lacks attribution, or signature verification fails, client MUST reject with error `inclusion_proof_failed` (see [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)). If the signer's authority is revoked at or before `created_at`, client MUST reject with `snapshot_issuer_revoked`.
6. **Freshness**: response MUST be received within the manifest's `verification_hints.challenge_window_seconds`; expired responses MUST be retried, not silently accepted.

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
    "event_kind": "cx.message.create"
  },
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:..."
}
```

Sync Service MAY route by `cleartext_metadata` but MUST NOT require plaintext content.
