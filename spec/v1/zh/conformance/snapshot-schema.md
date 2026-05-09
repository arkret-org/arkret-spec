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
  "snapshot_ref": "cx:snapshot:0196419a-8000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "reducer_profile": "cx.reducer.v1",
  "schema_profile_refs": ["cx.profile.core_event_store.v1"],
  "frontier": {
    "event_ids": ["cx:event:019640ed-8000-7000-8000-000000000000"],
    "timeline_hlc": "01970e589d21-0004-a13f9c2e"
  },
  "event_set_commitment": {
    "algorithm": "merkle_event_set_v1",
    "root": "sha256:...",
    "covered_event_count": 42000,
    "covered_frontier": ["cx:event:019640ed-8000-7000-8000-000000000000"]
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
  "snapshot_ref": "cx:snapshot:0196419a-8000-7000-8000-000000000000",
  "index": 0,
  "reducer_profile": "cx.reducer.v1",
  "items": [
    {
      "kind": "card",
      "id": "cx:flow:019640c5-0000-7000-8000-000000000000",
      "object": {
        "id": "cx:flow:019640c5-0000-7000-8000-000000000000",
        "kind": "card",
        "schema": "cx.schema.flow.v1"
      },
      "source_event_id": "cx:event:019640ed-8000-7000-8000-000000000000"
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

`state_hash` MUST 是 canonical reducer 输出之上的 Merkle root。  
Leaf hash：

```text
sha256(kind || ":" || id || ":" || sha256(canonical_json(object)))
```

Leaf 集合 MUST 与所有 chunk `items[].object` 一一对应。Merkle leaf 排序使用 `(kind, id)` canonical byte order；同一 `(kind,id)` 不得出现多个 leaf。不同 reducer profile 产生的 `state_hash` 不保证可比较，Snapshot consumer MUST 要求 `reducer_profile` 精确匹配或使用明确声明的 equivalent profile。

## 5. Snapshot Signature

Manifest MUST 仅包含一个 normative `signature` 字段。`signature` MUST 使用与 Event proof 相同的 detached proof 结构，并 MUST 覆盖 manifest payload（排除 `signature` 自身）的 canonical 编码。

签名 DID MUST 属于以下之一：

- Space owner
- Space creator or active Space admin
- trusted snapshot issuer
- witness quorum
- policy-approved snapshot issuer

Client 在使用 snapshot 之前 MUST 校验 signature、签名者权限、`state_hash`、frontier、`event_set_commitment` 与每个 chunk 的 digest。签名者权限 MUST 以 manifest `created_at` 为时点进行评估，依据是覆盖 snapshot frontier 以及在 `created_at` 之前可知的全部相关 admin / snapshot-issuer grant 或 revoke 事件的 accepted Space auth state。如果签名者在 `created_at` 之前已被撤销，或 verifier 无法确认其权限的撤销新鲜度，snapshot MUST 被隔离或以 `snapshot_issuer_revoked` 拒绝。

**最大接受窗口（normative）**：仅当采纳时同时满足以下**全部**条件，manifest 才可用于 snapshot bootstrap：

- `(now - manifest.created_at) ≤ snapshot_max_acceptance_age_ms`。默认 `snapshot_max_acceptance_age_ms = 2_592_000_000`（30 天）；`security_class=high_assurance` 的 Space MUST 收紧到 ≤ `604_800_000`（7 天）。超出该窗口后，即使曾经有效的 snapshot 也 MUST 被拒绝——client MUST 请求新的 manifest，因为 auth state 与 policy 的漂移已使旧 snapshot 无法安全代表当前状态。
- 签名者的权限链（Space owner / admin / trusted issuer / witness quorum membership）在当前 auth state 下仍**可解析**。如果该链已被裁剪（例如 Space tombstone、governance reset 或越过 manifest 时代的 auth-chain compaction），snapshot MUST 被拒绝。
- 若签名者曾被撤销，则 `(now - signer.revoked_at) < 0`。严格在 `created_at` **之后**生效的撤销不追溯使 manifest 失效，但 client 在用当前状态写入新 Event 前 MUST 先重放 snapshot frontier 之后的事件。

`proof`、`signed_by`、`generator_signature` 与 `state_signature` 不是 v1 snapshot manifest 字段。

## 6. Inclusion 与 Omission 防御

Snapshot signer authority 只能证明谁签发了 reduced state；它不能证明签名者已包含本应包含的全部 accepted Event。因此 v1 snapshot manifest MUST 携带 `event_set_commitment`。

`event_set_commitment.root` 承诺 snapshot frontier 覆盖的 Event Envelope ID 与 canonical event hash 的有序集合。实现 MUST 至少支持以下一种算法：

- `ordered_event_id_sha256_v1`：对按 `(actor_id, actor_seq, event_id)` 排序的 canonical JSON 条目 `{event_id,event_hash,actor_id,actor_seq,hlc}` 计算 SHA-256。
- `merkle_event_set_v1`：基于同样的 canonical 条目构造 Merkle root。

High-assurance profile MUST 支持 inclusion challenge。`security_class=high_assurance` 的 Space MUST 在采纳任何 snapshot 之前执行该挑战；其他 profile SHOULD 执行。

挑战 wire 格式（POST 到 `verification_hints.inclusion_proof_url`）：

请求体：

```json
{
  "snapshot_ref": "cx:snapshot:0196419a-8000-7000-8000-000000000000",
  "challenge_id": "cx:txn:019640c8-8000-7000-8000-000000000000",
  "samples": [
    {
      "kind": "event_id",
      "event_ids": ["cx:event:019640ed-8000-7000-8000-000000000000", "cx:event:019640ed-8000-7000-8000-000000000001"]
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

响应体：

```json
{
  "snapshot_ref": "cx:snapshot:0196419a-8000-7000-8000-000000000000",
  "challenge_id": "cx:txn:019640c8-8000-7000-8000-000000000000",
  "commitment_algorithm": "merkle_event_set_v1",
  "commitment_root": "sha256:...",
  "proofs": [
    {
      "kind": "event_id",
      "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
      "merkle_branch": ["sha256:...", "sha256:..."],
      "leaf_canonical_entry": {
        "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
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

采样与验证规则（normative）：

1. **随机采样**：client MUST 独立于 issuer 提示进行采样。event_id 样本 MUST 从 client 本地位于 snapshot frontier 内的 Event 集合中均匀抽取 `n ≥ max(20, ceil(log2(covered_event_count)))` 个不同 ID。actor_seq_range 样本 MUST 来自该 snapshot 已知活跃的不同 actor，每个长度 100，至少 3 段。
2. **分支验证**：每个 `proofs[i].merkle_branch` MUST 在 `commitment_algorithm` 下针对 `commitment_root` 验证通过；`commitment_root` MUST 等于 manifest 的 `event_set_commitment.root`（不允许重新绑定）。
3. **缺口归因**：对于采样范围内每个缺失的 `actor_seq`，响应 MUST 在 `verification_hints.{soft_failed_digest, quarantined_digest, conflict_records_digest}` 之一中给出对应条目（`digest_index` 是该 digest 承诺列表中的位置）——禁止静默缺口。
4. **签名**：`issuer_signature` MUST 来自 §5 列出的 DID（Space owner / creator / admin / trusted snapshot issuer / witness quorum），并 MUST 以 manifest `created_at` 为时点可验证。
5. **失败处理**：若任一采样到的 accepted Event 缺失、任一分支验证失败、任一缺口缺少归因，或签名验证失败，client MUST 以错误 `inclusion_proof_failed` 拒绝（见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；若签名者在 `created_at` 当时或之前已被撤销，client MUST 以 `snapshot_issuer_revoked` 拒绝。
6. **新鲜度**：响应 MUST 在 manifest 的 `verification_hints.challenge_window_seconds` 内收到；过期响应 MUST 重试，不得静默接受。

`verification_hints.conflict_records_digest`、`soft_failed_digest` 与 `quarantined_digest` 承诺非 accepted 或未决输入的集合。snapshot MUST NOT 静默隐藏会影响授权、可见性、E2EE epoch 或对象状态的 conflict、soft-fail 或 quarantine 记录。

## 7. Encrypted Envelope

```json
{
  "type": "encrypted_envelope",
  "encryption_profile": "mls_rfc9420",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "epoch": 42,
  "cleartext_metadata": {
    "object_ref": "cx:message:...",
    "event_kind": "cx.message.create"
  },
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:..."
}
```

Sync Service MAY 依据 `cleartext_metadata` 路由，但 MUST NOT 要求 plaintext content。
