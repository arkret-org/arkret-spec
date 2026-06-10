---
title: Snapshot, Chunk, and Encrypted Envelope Schema
status: candidate
normative: true
stability: v1
updated: 2026-06-10
sidebar:
  label: Snapshot & Envelope
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Snapshot 用于快速 bootstrap Realm 当前态。Snapshot 不是真相源；真相源仍然是 signed Event Envelope 和可验证 Event history。

Snapshot manifest 的自身主标识字段使用通用 `id`，其值 MUST 是 `ck:snapshot:*` typed identifier。其他对象、chunk payload、challenge 请求或 API hint 指向该 manifest 时使用 `snapshot_ref`；`_ref` 不用于 manifest 自身 primary identity。

## 2. Snapshot Manifest

```json
{
  "id": "ck:snapshot:0196419a-8000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "reducer_profile": "ck.reducer.v1",
  "security_class": "high_assurance",
  "schema_profile_refs": ["ck.profile.core_event_store.v1"],
  "frontier": {
    "event_ids": ["ck:event:019640ed-8000-7000-8000-000000000000"],
    "timeline_hlc": "01970e589d21-0004-a13f9c2e"
  },
  "event_set_commitment": {
    "algorithm": "merkle_event_set_v1",
    "root": "sha256:...",
    "covered_event_count": 42000,
    "covered_frontier": ["ck:event:019640ed-8000-7000-8000-000000000000"]
  },
  "state_digest": "sha256:...",
  "chunks": [
    {
      "chunk_ref": "ck:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "digest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "size_bytes": 524288
    }
  ],
  "verification_hints": {
    "verification_profile": "high_assurance",
    "inclusion_proof_url": "https://server.example/snapshots/0196419a-8000-7000-8000-000000000000/proofs",
    "challenge_window_seconds": 86400,
    "witness_quorum": 2,
    "conflict_records_digest": "sha256:...",
    "soft_failed_digest": "sha256:...",
    "quarantined_digest": "sha256:..."
  },
  "created_by": "did:web:server.example",
  "created_at": "2026-04-26T00:00:00Z",
  "authority_binding": {
    "issuer": "did:web:server.example",
    "authority_kind": "realm_policy_snapshot_issuer",
    "auth_state_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "auth_frontier": ["ck:event:019640ed-8000-7000-8000-000000000000"],
    "checked_at": "2026-04-26T00:00:00Z"
  },
  "signature": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:server.example#snapshot-key-1",
    "payload_digest": "sha256:...",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  }
}
```

## 3. Chunk Descriptor

```json
{
  "chunk_ref": "ck:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "digest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "size_bytes": 524288
}
```

Chunk descriptor 中的 `chunk_ref` 指向一个 snapshot chunk payload。Payload 本身是 canonical JSON，最小格式如下：

```json
{
  "type": "snapshot_chunk",
  "snapshot_ref": "ck:snapshot:0196419a-8000-7000-8000-000000000000",
  "index": 0,
  "reducer_profile": "ck.reducer.v1",
  "items": [
    {
      "kind": "flow",
      "id": "ck:flow:019640c5-0000-7000-8000-000000000000",
      "object": {
        "id": "ck:flow:019640c5-0000-7000-8000-000000000000",
        "kind": "flow",
        "schema": "ck.schema.flow.v1"
      },
      "source_event_id": "ck:event:019640ed-8000-7000-8000-000000000000"
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
- chunk `digest` MUST 是 `<alg>:<hex>` 形态，并覆盖 chunk payload 的 canonical JSON bytes。Manifest `state_digest` 不直接覆盖 descriptor 文本，而覆盖下节定义的 reducer output leaves。
- `conflict_records`、`soft_failed` 和 `quarantined` 可为空，但 high-assurance snapshot MUST 通过 manifest `verification_hints` 提交这些集合的 digest，不能静默隐藏影响授权、可见性、E2EE epoch 或对象状态的非 accepted 输入。

Snapshot-assisted pruning 只能删除或压缩某个存储边界内的 raw payload / derived material；它不删除协议历史事实。若实现因 retention、track archive、Realm tombstone 或 hard erasure 裁剪了对象内容，snapshot chunk MUST 继续包含 reducer profile 声明的最小 verification stub，或在 `soft_failed` / `quarantined` / conflict digest 中提交其存在。Consumer 不得把 snapshot 中缺少 stub 的对象解释为“从未存在”，除非 event-set commitment 和 reducer profile 明确证明该对象不在 covered frontier 中。

## 4. State Hash

`state_digest` MUST 是 canonical reducer 输出之上的 Merkle root。  
Leaf hash：

```text
sha256(kind || ":" || id || ":" || sha256(canonical_json(object)))
```

Leaf 集合 MUST 与所有 chunk `items[].object` 一一对应。Merkle leaf 排序使用 `(kind, id)` canonical byte order；同一 `(kind,id)` 不得出现多个 leaf。不同 reducer profile 产生的 `state_digest` 不保证可比较，Snapshot consumer MUST 要求 `reducer_profile` 精确匹配或使用明确声明的 equivalent profile。

## 5. Snapshot Signature

Manifest MUST 仅包含一个 normative `signature` 字段。`signature` MUST 使用与 Event proof 相同的 detached proof 结构，并 MUST 覆盖 manifest payload（排除 `signature` 自身）的 canonical 编码。被签名 transcript 因此包含 `id`、`realm_id`、`reducer_profile`、`schema_profile_refs`、`state_digest`、`frontier`、`event_set_commitment`、`chunks[]` descriptor（`chunk_ref` / `digest` / `size_bytes`）、`security_class`、`verification_hints`、`created_by`、`created_at` 与 `authority_binding`；字段清单与顺序 MUST 与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) `signature` 的 `x-canonical-bytes-include` 完全对齐。其中 `security_class` 被纳入签名输入，使 `high_assurance → standard` 降级无法在不使签名失效的情况下完成。consumer MUST 先验证该 transcript，再逐个验证 chunk payload digest。

签名 DID MUST 属于以下之一：

- Realm owner
- Realm creator or active Realm admin
- trusted snapshot issuer
- witness quorum
- policy-approved snapshot issuer

Client 在使用 snapshot 之前 MUST 校验 signature、`authority_binding`、`state_digest`、frontier、`event_set_commitment` 与每个 chunk 的 digest。签名者权限 MUST 以 manifest `created_at` 为时点进行评估；manifest 必须携带 `authority_binding`，其中 `issuer` 必须等于 `created_by`，`auth_frontier` / `auth_state_digest` 必须覆盖 snapshot frontier 以及在 `created_at` 之前可知的全部相关 admin / snapshot-issuer grant 或 revoke 事件的 accepted Realm auth state。如果签名者在 `created_at` 之前已被撤销，或 verifier 无法确认其权限的撤销新鲜度，snapshot MUST 被隔离或以 `snapshot_issuer_revoked` 拒绝。

**最大接受窗口（normative）**：仅当采纳时同时满足以下**全部**条件，manifest 才可用于 snapshot bootstrap：

- `(now - manifest.created_at) ≤ snapshot_max_acceptance_age_ms`。默认 `snapshot_max_acceptance_age_ms = 2_592_000_000`（30 天）；`security_class=high_assurance` 的 Realm MUST 收紧到 ≤ `604_800_000`（7 天）。超出该窗口后，即使曾经有效的 snapshot 也 MUST 被拒绝——client MUST 请求新的 manifest，因为 auth state 与 policy 的漂移已使旧 snapshot 无法安全代表当前状态。
- 签名者的权限链（Realm owner / admin / trusted issuer / witness quorum membership）在当前 auth state 下仍**可解析**。如果该链已被裁剪（例如 Realm tombstone、governance reset 或越过 manifest 时代的 auth-chain compaction），snapshot MUST 被拒绝。
- 撤销新鲜度以 `authority_binding.auth_frontier` / `auth_state_digest` 解析出的签名者撤销状态为准（snapshot manifest 无独立 `signer.revoked_at` wire 字段；撤销时点是从该 auth state 派生的逻辑值）。判定规则:由 auth state 解析出的签名者撤销生效时点 MUST NOT exist，**或** 严格晚于 `manifest.created_at`。严格在 `created_at` **之后**生效的撤销不追溯使 manifest 失效，但 client 在用当前状态写入新 Event 前 MUST 先重放 snapshot frontier 之后的事件。若该重放无法完整补齐（backfill 缺依赖、source 不可达或 frontier 之后事件无法完整重放），client MUST fail closed，MUST NOT 基于不完整的 post-snapshot 状态写入新 Event；此时按 §6.2 raw replay fallback 处理或要求新的 manifest / 重新初始同步。

`proof`、`verification_method`、`generator_signature` 与 `state_signature` 不是 v1 snapshot manifest 字段。

## 6. Inclusion 与 Omission 防御

Snapshot signer authority 只能证明谁签发了 reduced state；它不能证明签名者已包含本应包含的全部 accepted Event。因此 v1 snapshot manifest MUST 携带 `event_set_commitment`。

`event_set_commitment.root` 承诺 snapshot frontier 覆盖的 Event Envelope ID 与 canonical event hash 的有序集合。实现 MUST 至少支持以下一种算法：

- `ordered_event_id_sha256_v1`：对按 `(actor_id, actor_seq, event_id)` 排序的 canonical JSON 条目 `{event_id,event_digest,actor_id,actor_seq,hlc}` 计算 SHA-256。
- `merkle_event_set_v1`：基于同样的 canonical 条目构造 Merkle root。

### 6.1 能力边界（normative — what omission challenge can and cannot prove）

Inclusion challenge 的安全保证范围 **MUST** 在 spec 文本与实现 UI 中按下表理解，任何超出该范围的安全声明都是夸大:

| 能力 | 可证明? | 说明 |
| --- | --- | --- |
| issuer 是否对**它声明覆盖的集合**保持内部一致 | 可证明 | challenge 抽样命中即可重算 commitment root,确认 issuer 未声明地重写它声明过的某个 event 内容。 |
| issuer 是否漏掉了**新客户端不知道的** actor 或 event 分支 | 不可证明 | bootstrap 客户端只能用 issuer-provided frontier 或 issuer-listed active actor 集合抽样；它**不知道**该追问 issuer 未列出的 actor。issuer 可以构造一个自洽但缺失若干 actor 的 snapshot，新客户端拿不出对照。 |
| issuer 是否对**客户端已知的** event_id / actor_seq range 区间漏掉了事件 | 仅在附加条件下可证明 | 客户端 SHOULD 用自己已 cache 的 event_id / actor_seq range 抽样；命中 0 个 `kind="event_id"` 样本时挑战形同虚设。`security_class=high_assurance` 部署 SHOULD 在 challenge `samples[]` 中混入**至少一个**客户端自有的 sample anchor。 |
| issuer 是否同时签发了多版本不一致的 snapshot(split-view) | 不可证明 | inclusion challenge 是 issuer-side 单向 query;两份 issuer 给不同 client 的不同 snapshot 互相不知道。Split-view 检测必须依赖 federation §4.5 frontier exchange 或 §8 fork-detection。 |

简言之: **`event_set_commitment` + inclusion challenge 是"已知集合包含性 + 内容一致性"检查，不是 omission 完整性证明**。任何 spec 措辞、UI 文案、安全审计声明 MUST NOT 把 inclusion challenge 描述为"防止 issuer 漏发任何事件"。

### 6.2 High-assurance bootstrap 的额外要求

`security_class=high_assurance` 的 Realm MUST 在采纳任何 snapshot 之前执行该挑战；其他 profile SHOULD 执行。同时，该 security_class 的 bootstrap 客户端 **MUST** 至少满足以下一条以补足 §6.1 的边界缺失:

1. **Witness quorum on actor set**:从至少一个独立 witness(部署 policy 明确列出且非 snapshot issuer 控制)拉取该 Realm 在 `manifest.created_at` 时刻的 active actor set commitment 与 actor sequence upper-bound commitment,client 用其与 snapshot manifest 中声明的 actor set 比对；不一致 MUST quarantine。
2. **Per-actor sequence upper-bound**:`event_set_commitment` MUST 携带 schema 中的 `actor_seq_ranges[]`，为每个 actor 绑定 `[from_seq, to_seq]` 与该区间的 commitment `root`；该 commitment 使用 `event_set_commitment.algorithm` 声明的现有算法（`ordered_event_id_sha256_v1` 或 `merkle_event_set_v1`）计算，不引入第三种 wire algorithm。Client 校验该 actor 在 snapshot frontier 后到达的事件 `actor_seq > to_seq`。
3. **Raw replay fallback**:无 witness quorum 可用时,bootstrap 客户端 **MUST NOT** 把 snapshot 作为 high-assurance accepted state——只能当作加速索引，实际授权决策仍 MUST 走原始 Event 回放，直到独立 witness 上线或 federation peer 提供 cross-source confirmation。

非 high-assurance profile SHOULD 在 UI 中把"由第三方 snapshot 加速 bootstrap"标记为 lower-trust 状态，与从原始 Event 回放出的 high-trust 状态区分。

挑战 wire 格式（POST 到 `verification_hints.inclusion_proof_url`）：

请求体：

```json
{
  "snapshot_ref": "ck:snapshot:0196419a-8000-7000-8000-000000000000",
  "challenge_id": "ck:transaction:019640c8-8000-7000-8000-000000000000",
  "samples": [
    {
      "kind": "event_id",
      "event_ids": ["ck:event:019640ed-8000-7000-8000-000000000000", "ck:event:019640ed-8000-7000-8000-000000000001"]
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
  "snapshot_ref": "ck:snapshot:0196419a-8000-7000-8000-000000000000",
  "challenge_id": "ck:transaction:019640c8-8000-7000-8000-000000000000",
  "commitment_algorithm": "merkle_event_set_v1",
  "commitment_root": "sha256:...",
  "proofs": [
    {
      "kind": "event_id",
      "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
      "merkle_branch": ["sha256:...", "sha256:..."],
      "leaf_canonical_entry": {
        "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
        "event_digest": "sha256:...",
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
        {"event_id": "ck:event:...", "event_digest": "sha256:...", "actor_seq": 100, "hlc": "..."},
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
    "payload_digest": "sha256:...",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  }
}
```

采样与验证规则（normative）：

1. **随机采样**：client MUST 独立于 issuer 提示进行采样。event_id 样本 MUST 从 client 本地位于 snapshot frontier 内的 Event 集合中均匀抽取 `n ≥ max(20, ceil(log2(covered_event_count)))` 个不同 ID。actor_seq_range 样本 MUST 来自该 snapshot 已知活跃的不同 actor，每个长度 100，至少 3 段。
2. **分支验证**：每个 `proofs[i].merkle_branch` MUST 在 `commitment_algorithm` 下针对 `commitment_root` 验证通过；`commitment_root` MUST 等于 manifest 的 `event_set_commitment.root`（不允许重新绑定）。
3. **缺口归因**：对于采样范围内每个缺失的 `actor_seq`，响应 MUST 在 `verification_hints.{soft_failed_digest, quarantined_digest, conflict_records_digest}` 之一中给出对应条目（`digest_index` 是该 digest 承诺列表中的位置）——禁止静默缺口。
4. **签名**：`issuer_signature` MUST 来自 §5 列出的 DID（Realm owner / creator / admin / trusted snapshot issuer / witness quorum），并 MUST 以 manifest `created_at` 为时点可验证。
5. **失败处理**：若任一采样到的 accepted Event 缺失、任一分支验证失败、任一缺口缺少归因，或签名验证失败，client MUST 以错误 `inclusion_proof_failed` 拒绝（见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；若签名者在 `created_at` 当时或之前已被撤销，client MUST 以 `snapshot_issuer_revoked` 拒绝。
6. **新鲜度**：响应 MUST 在 manifest 的 `verification_hints.challenge_window_seconds` 内收到；过期响应 MUST 重试，MUST NOT 静默接受。

> **可执行向量**：上述采样规则 1（`n ≥ max(20, ceil(log2(covered_event_count)))` 的 event_id 抽样、至少 3 段 `actor_seq_range`）与规则 2 的 merkle branch 验证由 [`conformance-vectors.md` §3.6](./conformance-vectors.md) `ck.vector.snapshot.inclusion_challenge.v1` 固化（结构与断言在 prose 中给定，`commitment_root` / `samples[]` / `proofs[].merkle_branch` / `gap_attribution` 等具体字节值以 `spec/v1/artifacts/fixtures/` 的 fixture 生成物为权威）。实现 MUST 按该向量与本节 prose 规则执行挑战，MUST NOT 以“缺向量/缺 fixture”为由跳过 high-assurance bootstrap 校验。

`verification_hints.conflict_records_digest`、`soft_failed_digest` 与 `quarantined_digest` 承诺非 accepted 或未决输入的集合。snapshot MUST NOT 静默隐藏会影响授权、可见性、E2EE epoch 或对象状态的 conflict、soft-fail 或 quarantine 记录。

## 7. Encrypted Envelope

加密载荷统一使用 `ck.schema.encrypted_envelope.v1`（artifact [`encrypted-envelope.schema.json`](../../artifacts/schemas/encrypted-envelope.schema.json)）。字段语义与约束以 [`../crypto-media/encryption-and-audit.md` §2.3.1](../crypto-media/encryption-and-audit.md) 为权威；snapshot chunk 中的密文 MUST 是同一 envelope 形态：

```json
{
  "scheme": "mls-rfc9420",
  "version": "1.0",
  "group_id": "base64url",
  "epoch": 42,
  "content_type": "application/json",
  "ciphertext": "base64url",
  "aad_visibility_event_id": "routing_digest",
  "aad": {
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "event_kind": "ck.message.create",
    "event_ref_digest": "sha256:..."
  },
  "key_ref": {
    "algorithm": "MLS",
    "group_state_ref": "ck:event:..."
  },
  "payload_digest": "sha256:...",
  "aad_digest": "sha256:..."
}
```

Sync Service MAY 依据 `aad` 路由元数据投递，但 MUST NOT 要求 plaintext content。
