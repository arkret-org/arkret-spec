---
title: Snapshot, Chunk, and Encrypted Envelope Schema
status: candidate
normative: true
stability: v1
updated: 2026-07-30
sidebar:
  label: Snapshot & Envelope
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Snapshot 用于快速 bootstrap Realm 当前态。Snapshot 不是真相源；真相源仍然是 signed Event Envelope 和可验证 Event history。

Snapshot manifest 的自身主标识字段使用通用 `id`，其值 MUST 是 `ak:snapshot:*` typed identifier。其他对象、chunk payload、challenge 请求或 API hint 指向该 manifest 时使用 `snapshot_ref`；`_ref` 不用于 manifest 自身 primary identity。

## 2. Snapshot Manifest

```json
{
  "id": "ak:snapshot:0196419a-8000-7000-8000-000000000000",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "reducer_profile": "ak.reducer.core.v1",
  "security_class": "high_assurance",
  "schema_profile_refs": [
    "ak.profile.core_event_store.v1"
  ],
  "frontier": {
    "event_ids": [
      "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-"
    ],
    "timeline_hlc": "01970e589d21-0004-a13f9c2e"
  },
  "event_set_commitment": {
    "algorithm": "merkle_event_set_v1",
    "root": "sha256:...",
    "covered_event_count": 42000,
    "covered_event_ids": [
      "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-"
    ]
  },
  "state_digest": "sha256:...",
  "chunks": [
    {
      "chunk_ref": "ak:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
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
  "created_by": "ak:did_core:webvh:z5CVGhWHEfRe1HhKLRueCrxfD",
  "created_at": "2026-04-26T00:00:00Z",
  "authority_binding": {
    "issuer": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example",
    "authority_kind": "realm_policy_snapshot_issuer",
    "auth_state_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "auth_frontier": [
      "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-"
    ],
    "checked_at": "2026-04-26T00:00:00Z"
  },
  "signature": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example#snapshot-key-1",
    "payload_digest": "sha256:...",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  }
}
```

## 3. Chunk Descriptor

```json
{
  "chunk_ref": "ak:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "digest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "size_bytes": 524288
}
```

Chunk descriptor 中的 `chunk_ref` 指向一个 snapshot chunk payload。Payload 本身是 canonical JSON，最小格式如下：

```json
{
  "type": "snapshot_chunk",
  "snapshot_ref": "ak:snapshot:0196419a-8000-7000-8000-000000000000",
  "index": 0,
  "reducer_profile": "ak.reducer.core.v1",
  "items": [
    {
      "kind": "strand",
      "id": "ak:strand:AVgnD-1YLmV6g-_RiZro8Yzmydn3Q8upFMpAgJW9bsbj",
      "object": {
        "id": "ak:strand:AVgnD-1YLmV6g-_RiZro8Yzmydn3Q8upFMpAgJW9bsbj",
        "kind": "strand",
        "schema": "ak.schema.strand.v1"
      },
      "source_event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-"
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

Chunk 边界 MAY 由实现按本地传输目标大小选择，但 MUST 以完整 `items[]` 元素为边界；实现 MUST NOT 把单个 item 或 JSON token 切开。每个 chunk payload 仍必须是上方 `snapshot_chunk` object 的完整 canonical JSON。把整份 reducer state bytes 先序列化、再按 byte range 切块的 dev bundle 形态不是合法的 `ak.schema.snapshot.v1` chunk payload；这类实现 MUST NOT 把 byte-range chunk 描述为 manifest `chunks[]` 的标准 chunk。

Snapshot-assisted pruning 只能删除或压缩某个存储边界内的 raw payload / derived material；它不删除协议历史事实。若实现因 retention、track archive、Realm tombstone 或 hard erasure 裁剪了对象内容，snapshot chunk MUST 继续包含 reducer profile 声明的最小 verification stub，或在 `soft_failed` / `quarantined` / conflict digest 中提交其存在。Consumer 不得把 snapshot 中缺少 stub 的对象解释为“从未存在”，除非 event-set commitment 和 reducer profile 明确证明该对象不在 covered event set 中。

## 4. State Hash

`state_digest` MUST 是 canonical reducer 输出之上的 Merkle root。该 Merkle root 使用 [`encoding.md`](./encoding.md) §3.3.1 的统一 RFC 6962 域分隔规则：领域 leaf digest 去掉 suite 前缀并解码为 raw bytes 后作为 `leaf_data`；leaf 为 `sha256(0x00 || leaf_data)`，内部节点为 `sha256(0x01 || left_raw || right_raw)`；奇数层尾节点提升到上一层且不复制；单 leaf root 等于带 `0x00` 前缀的 leaf hash；空 leaf 集合 root 为 `sha256` 空字节，即 `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

Leaf hash：

```text
sha256(kind || ":" || id || ":" || sha256(canonical_json(object)))
```

Leaf 集合 MUST 与所有 chunk `items[].object` 一一对应。Merkle leaf 排序使用 `(kind, id)` canonical byte order；同一 `(kind,id)` 不得出现多个 leaf。空 Realm 或空 reducer output MAY 产生 `covered_event_count = 0` 与空 `frontier.event_ids`；此时 `state_digest` MUST 使用上文空 leaf 集合 root。不同 reducer profile 产生的 `state_digest` 不保证可比较，Snapshot consumer MUST 要求 `reducer_profile` 精确匹配或使用明确声明的 equivalent profile。

## 5. Snapshot Signature

Manifest MUST 仅包含一个 normative `signature` 字段。`signature` MUST 使用与 Event proof 相同的 detached proof 结构，并 MUST 覆盖 manifest payload（排除 `signature` 自身）的 canonical 编码。被签名 transcript 因此包含 `id`、`realm_id`、`reducer_profile`、`schema_profile_refs`、`state_digest`、`frontier`、`event_set_commitment`、`chunks[]` descriptor（`chunk_ref` / `digest` / `size_bytes`）、`security_class`、`verification_hints`、`created_by`、`created_at` 与 `authority_binding`；字段清单与顺序 MUST 与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) `signature` 的 `x-canonical-bytes-include` 完全对齐。其中 `security_class` 被纳入签名输入，使 `high_assurance → standard` 降级无法在不使签名失效的情况下完成。consumer MUST 先验证该 transcript，再逐个验证 chunk payload digest。

签名 DID MUST 属于以下之一：

- Realm owner
- Realm creator or active Realm admin
- trusted snapshot issuer
- witness quorum（`authority_kind="witness_quorum"`，其 attestation 载体、context、canonical
  projection 与 admission 规则见 §5.1）
- policy-approved snapshot issuer

Client 在使用 snapshot 之前 MUST 校验 signature、`authority_binding`、`state_digest`、frontier、`event_set_commitment` 与每个 chunk 的 digest。其中 manifest 内部一致性 MUST 包含：当 `event_set_commitment.covered_event_ids` 存在时，consumer MUST 校验它与 `frontier.event_ids` 是**同一个 event id 集合**（集合相等；两个字段绑定的都是同一 snapshot frontier——`frontier` 声明 reducer state 的截止边界，`event_set_commitment` 承诺到达该同一边界的 event 集合，见 §2 示例与 §6），任何不一致 MUST 拒绝该 snapshot，不得以其中一侧为准继续 bootstrap。签名者权限 MUST 以 manifest `created_at` 为时点进行评估；manifest 必须携带 `authority_binding`，其中 `issuer` 必须等于 `created_by`，`auth_frontier` / `auth_state_digest` 必须覆盖 snapshot frontier 以及在 `created_at` 之前可知的全部相关 admin / snapshot-issuer grant 或 revoke 事件的 accepted Realm auth state。`auth_state_digest` 是 issuer-local opaque commitment：verifier MUST 检查它与 `auth_frontier` 绑定一致，并 MUST 按自己可取得的 accepted auth state 回放或查询来判定签名者在 `created_at` 的授权与撤销新鲜度；除非部署 profile 另行声明可复算的 auth-state canonical encoding，verifier MUST NOT 只因无法逐字重算该 digest 就接受或拒绝。若签名者在 `created_at` 之前已被撤销，或 verifier 无法确认其权限的撤销新鲜度，snapshot MUST 被隔离或以 `snapshot_issuer_revoked` 拒绝。

**最大接受窗口（normative）**：仅当采纳时同时满足以下**全部**条件，manifest 才可用于 snapshot bootstrap：

- `(now - manifest.created_at) ≤ snapshot_max_acceptance_age_ms`。默认 `snapshot_max_acceptance_age_ms = 2_592_000_000`（30 天）；`security_class=high_assurance` 的 Realm MUST 收紧到 ≤ `604_800_000`（7 天）。超出该窗口后，即使曾经有效的 snapshot 也 MUST 被拒绝——client MUST 请求新的 manifest，因为 auth state 与 policy 的漂移已使旧 snapshot 无法安全代表当前状态。
- 签名者属于 §5 列出的任一合法类别，且其权限链在当前 auth state 下仍**可解析**。如果该链已被裁剪（例如 Realm tombstone、governance reset 或越过 manifest 时代的 auth-chain compaction），snapshot MUST 被拒绝。
- 撤销新鲜度以 `authority_binding.auth_frontier` / `auth_state_digest` 解析出的签名者撤销状态为准（snapshot manifest 无独立 `signer.revoked_at` wire 字段；撤销时点是从该 auth state 派生的逻辑值）。判定规则:由 auth state 解析出的签名者撤销生效时点 MUST NOT exist，**或** 严格晚于 `manifest.created_at`。严格在 `created_at` **之后**生效的撤销不追溯使 manifest 失效，但 client 在用当前状态写入新 Event 前 MUST 先重放 snapshot frontier 之后的事件。若该重放无法完整补齐（backfill 缺依赖、source 不可达或 frontier 之后事件无法完整重放），client MUST fail closed，MUST NOT 基于不完整的 post-snapshot 状态写入新 Event；此时按 §6.2 raw replay fallback 处理或要求新的 manifest / 重新初始同步。

### 5.1 Snapshot Witness Attestation（normative）

`authority_binding.witness_attestations[]` 是**独立于 manifest 的对象族**
`snapshot_witness_attestation`（[`snapshot.schema.json#/$defs/snapshot_witness_attestation`](../../artifacts/schemas/snapshot.schema.json)），
不是顶层 `signature` 的复签。每行是闭合 `{witness_id, proof}`：`witness_id` 是该 witness 的稳定
`did_core_id`，`proof` 是共享 detached proof。

**独立 context**。该族在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)
登记的唯一 context 是 `ak.snapshot-witness-attestation-proof-v1`；schema 侧的
`x-arkret-proof-context` 注解与本节 MUST 逐字一致。顶层 `ak.snapshot-proof-v1` MUST NOT 被复用
为 witness 的隐式别名；用 manifest context 生成的 witness 签名即使密码学验签通过也 MUST 以
`signature_invalid` 拒绝。

**canonical projection（精确、非"至少"）**。`proof.payload_digest` 是下列闭合对象的 canonical
JSON（[`encoding.md` §2](./encoding.md)，JCS）SHA-256 typed digest。projection 的所有取值都从
manifest 与该行 `witness_id` 重算，proof 自身、`signature`、整个 `witness_attestations[]`、
`verification_hints`、`chunks[]`、`created_by`（其值 MUST 等于已纳入的 `issuer`）与
`authority_binding.checked_at` 都**不进入** projection——这正是 witness 不会签到包含自己签名的
transcript、因而无签名循环的原因：

```text
{
  "context": "ak.snapshot-witness-attestation-proof-v1",
  "witness_id": <this row's witness_id>,
  "snapshot_id": <manifest.id>,
  "realm_id": <manifest.realm_id>,
  "reducer_profile": <manifest.reducer_profile>,
  "schema_profile_refs": <manifest.schema_profile_refs>,
  "security_class": <manifest.security_class>,
  "state_digest": <manifest.state_digest>,
  "frontier": <manifest.frontier>,
  "event_set_commitment": <manifest.event_set_commitment>,
  "issuer": <manifest.authority_binding.issuer>,
  "authority_kind": <manifest.authority_binding.authority_kind>,
  "auth_state_digest": <manifest.authority_binding.auth_state_digest>,
  "auth_frontier": <manifest.authority_binding.auth_frontier>,
  "snapshot_created_at": <manifest.created_at>
}
```

`payload_digest = "sha256:" + lowercase_hex(SHA-256(RFC8785_JCS(projection)))`。verifier MUST 自己
从 manifest 重算该 projection 并比对；MUST NOT 接受任何其它 transcript，也 MUST NOT 因 issuer
声称某种私有 projection 而放宽。

**签名顺序与列表绑定（normative）**。签名严格分两步且不可交换：

1. witness 先对上述**无签名** projection 出具 attestation；此时 manifest 的
   `witness_attestations[]` 与顶层 `signature` 都还不存在于 projection 输入中。
2. issuer 再把**最终**的 `witness_attestations[]` 写入 manifest 并签顶层 `signature`。该列表
   MUST 按 `witness_id` 的 UTF-8 字节序升序排列且 `witness_id` 全局唯一；顶层 signature 覆盖
   完整 `authority_binding`，因此增删、改写或重排任何一行都会使顶层 signature 失效。

verifier MUST 先验顶层 signature，再逐行验 witness attestation；顺序非升序或 `witness_id` 重复
MUST 以 `schema_violation` 拒绝，MUST NOT 先归一化再接受。

**quorum admission（normative）**。`authority_binding.authority_kind = "witness_quorum"` 时
`witness_attestations[]` MUST 存在且非空（schema 条件必备）。admission 的全部授权输入 MUST 只来自
`authority_binding.auth_frontier` / `auth_state_digest` 在 `manifest.created_at` 解析出的 accepted
Realm auth/policy state：

- **授权 witness set**：`witness_id` MUST 在该 state 的授权 snapshot-witness 集合内；不在集合内的行
  MUST 以 `snapshot_authority_unverified` 拒绝，且不计入 quorum。
- **key validity 与撤销新鲜度**：`proof.verification_method` 的 controller `full_id` MUST 由已登记
  method adapter 验证并 `project(full_id) == witness_id`（禁止完整 DID 与 `did_core_id` 直接字符串
  比较）；该 key 在 `manifest.created_at` MUST 处于有效且未撤销状态，判定规则与 §5 对 issuer 的
  撤销新鲜度规则相同。verifier 无法确认撤销新鲜度时 MUST 隔离或拒绝，MUST NOT 计入 quorum。
- **去重**：quorum 计数以 `witness_id` 为单位。同一 witness 的多个 key 或多份签名只计一次。
- **threshold**：threshold MUST 由上述 accepted auth/policy state 给出。`verification_hints.witness_quorum`
  是 issuer 自报的**声明值**，不是 threshold 来源：它已落在顶层签名 transcript 内，verifier MUST 把它
  与 policy 推导出的 threshold 比对，不相等 MUST 以 `snapshot_authority_unverified` 拒绝。去重后的有效
  witness 数低于 policy threshold 时同样 MUST 以 `snapshot_authority_unverified` 拒绝。

**v1 没有"等价 quorum proof"**。v1 只有 `witness_attestations[]` 这一个 typed carrier。任何未在本节
定义的替代 quorum 证据 MUST NOT 被接受，实现 MUST NOT 用私有字段、`x_*` 扩展或带外材料补洞；
需要新的 quorum 形态时，必须先在本节定义 closed union 分支、独立 context 与验证合同，而不是让
verifier 各自解释。

conformance：`ak.vector.snapshot.witness_quorum_attestation.v1` MUST 覆盖缺失 attestations、重复
signer、未授权 witness、已撤销 witness、阈值不足、错误 context、错误 projection、witness 列表被改写、
有效 quorum，以及顶层 issuer signature 对最终 witness 集合的绑定。

`proof`、`verification_method`、`generator_signature` 与 `state_signature` 不是 v1 snapshot manifest 顶层字段。v1 manifest 只允许 §（上文）的**单一** `signature`（detached proof，内部含 `verification_method`）；上述易混淆名作为 manifest 顶层字段时 MUST 拒绝。权威字段集以 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 为准。

## 6. Inclusion 与 Omission 防御

Snapshot signer authority 只能证明谁签发了 reduced state；它不能证明签名者已包含本应包含的全部 accepted Event。因此 v1 snapshot manifest MUST 携带 `event_set_commitment`。

`event_set_commitment.root` 承诺 snapshot frontier 覆盖的 Event Envelope ID 与 canonical event hash 的有序集合。输入 leaf entry MUST 按 `(actor_id, actor_seq, event_id)` 排序；每个 entry 的 canonical JSON object 字段语义为 `{event_id,event_digest,actor_id,actor_seq,hlc}`。实现 MUST 至少支持以下一种算法：

- `ordered_event_id_sha256_v1`：对排序后的 entry array 计算 `sha256(canonical_json(entries))`；空集合输入为 canonical JSON `[]`。
- `merkle_event_set_v1`：先对每个 entry 计算 `sha256(canonical_json(entry))` 作为 `leaf_data`，再按 [`encoding.md`](./encoding.md) §3.3.1 的统一 RFC 6962 规则计算 `sha256(0x00 || leaf_data)` leaf 与 `sha256(0x01 || left || right)` internal node；空集合 root 为 `sha256` 空字节。无域分隔的 root MUST 拒绝。

### 6.1 能力边界（normative — what omission challenge can and cannot prove）

Inclusion challenge 的安全保证范围 **MUST** 在 spec 文本与实现 UI 中按下表理解，任何超出该范围的安全声明都是夸大:

| 能力 | 可证明? | 说明 |
| --- | --- | --- |
| issuer 是否对**它声明覆盖的集合**保持内部一致 | 可证明 | challenge 抽样命中即可重算 commitment root,确认 issuer 未声明地重写它声明过的某个 event 内容。 |
| issuer 是否漏掉了**新客户端不知道的** actor 或 event 分支 | 不可证明 | bootstrap 客户端只能用 issuer-provided frontier 或 issuer-listed active actor 集合抽样；它**不知道**该追问 issuer 未列出的 actor。issuer 可以构造一个自洽但缺失若干 actor 的 snapshot，新客户端拿不出对照。 |
| issuer 是否对**客户端已知的** event_id / actor_seq range 区间漏掉了事件 | 仅在附加条件下可证明 | 客户端 SHOULD 用自己已 cache 的 event_id / actor_seq range 抽样；命中 0 个 `kind="event_id"` 样本时挑战形同虚设。`security_class=high_assurance` 部署 SHOULD 在 challenge `samples[]` 中混入**至少一个**客户端自有的 sample seal。 |
| issuer 是否同时签发了多版本不一致的 snapshot(split-view) | 不可证明 | inclusion challenge 是 issuer-side 单向 query;两份 issuer 给不同 client 的不同 snapshot 互相不知道。Split-view 检测必须依赖 federation §4.5 frontier exchange 或 §8 fork-detection。 |

简言之: **`event_set_commitment` + inclusion challenge 是"已知集合包含性 + 内容一致性"检查，不是 omission 完整性证明**。任何 spec 措辞、UI 文案、安全审计声明 MUST NOT 把 inclusion challenge 描述为"防止 issuer 漏发任何事件"。

### 6.2 High-assurance bootstrap 的额外要求

`security_class=high_assurance` 的 Realm MUST 在采纳任何 snapshot 之前执行该挑战；其他 profile SHOULD 执行。同时，该 security_class 的 bootstrap 客户端 **MUST** 使用下列两个充分路径之一补足 §6.1 的边界缺失；`actor_seq_ranges[]` 只是两个路径都可使用的区间内部一致性材料，不是第三个独立充分路径：

1. **Independent witness path**：从至少一个独立 witness（部署 policy 明确列出且非 snapshot issuer 控制）拉取该 Realm 在 `manifest.created_at` 时刻的 active actor-set commitment 与 actor sequence upper-bound commitment，client 用其与 snapshot manifest 中声明的 actor set 比对；不一致 MUST quarantine。`event_set_commitment` MUST 同时携带 schema 中的 `actor_seq_ranges[]`，为每个已见证 actor 绑定 `[from_seq, to_seq]` 与该区间的 commitment `root`；该 commitment 使用 `event_set_commitment.algorithm` 声明的现有算法（`ordered_event_id_sha256_v1` 或 `merkle_event_set_v1`）计算，不引入第三种 wire algorithm。
2. **Raw replay path**：无独立 witness actor-set commitment 可用时，bootstrap 客户端 **MUST NOT** 把 snapshot 本身作为 high-assurance accepted state；它只能作为加速索引，实际授权决策 MUST 由原始 Event 完整回放得到。回放尚未完成时，snapshot completeness 保持 unverified / degraded；独立 witness 或 federation peer 后续提供 cross-source confirmation 后方可升级。

仅由 snapshot issuer 自己声明并签发的 `actor_seq_ranges[]`，即使所有已声明 actor 的区间、root 与 count 均自洽，也只能证明这些区间内部无洞；它 MUST NOT 被解释为“没有未知 actor 被整体省略”的证明。整 actor 省略负例由 `ak.vector.snapshot.inclusion_challenge.v1` 承载。

非 high-assurance profile SHOULD 在 UI 中把"由第三方 snapshot 加速 bootstrap"标记为 lower-trust 状态，与从原始 Event 回放出的 high-trust 状态区分。

挑战 wire 格式（POST 到 `verification_hints.inclusion_proof_url`）：

请求体：

```json
{
  "snapshot_ref": "ak:snapshot:0196419a-8000-7000-8000-000000000000",
  "challenge_id": "ak:transaction:019640c8-8000-7000-8000-000000000000",
  "samples": [
    {
      "kind": "event_id",
      "event_ids": ["ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-", "ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY"]
    },
    {
      "kind": "actor_seq_range",
      "actor_id": "ak:did_core:webvh:zExampleAliceScid",
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
  "snapshot_ref": "ak:snapshot:0196419a-8000-7000-8000-000000000000",
  "challenge_id": "ak:transaction:019640c8-8000-7000-8000-000000000000",
  "commitment_algorithm": "merkle_event_set_v1",
  "commitment_root": "sha256:...",
  "proofs": [
    {
      "kind": "event_id",
      "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
      "merkle_branch": [
        "sha256:...",
        "sha256:..."
      ],
      "leaf_canonical_entry": {
        "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
        "event_digest": "sha256:...",
        "actor_id": "ak:did_core:webvh:zExampleAliceScid",
        "actor_seq": 100,
        "hlc": "01970e589d21-0004-a13f9c2e"
      }
    },
    {
      "kind": "actor_seq_range",
      "actor_id": "ak:did_core:webvh:zExampleAliceScid",
      "from_seq": 100,
      "to_seq": 199,
      "ordered_set_slice": [
        {
          "event_id": "ak:event:...",
          "event_digest": "sha256:...",
          "actor_seq": 100,
          "hlc": "..."
        },
        "..."
      ],
      "gap_attribution": [
        {
          "actor_seq": 142,
          "category": "soft_failed",
          "digest_index": 7
        },
        {
          "actor_seq": 167,
          "category": "quarantined",
          "digest_index": 3
        }
      ]
    }
  ],
  "issuer_signature": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example#snapshot-key-1",
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

> **向量登记状态**：上述采样规则 1（`n ≥ max(20, ceil(log2(covered_event_count)))` 的 event_id 抽样、至少 3 段 `actor_seq_range`）与规则 2 的 merkle branch 验证注册为 active 向量 `ak.vector.snapshot.inclusion_challenge.v1`，并由 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_inclusion_challenge` fixture 及其 registered runner 承载。实现 MUST 按本节 prose 与 fixture 规则执行挑战，并将该 active vector 纳入 high-assurance bootstrap 校验。

`verification_hints.conflict_records_digest`、`soft_failed_digest` 与 `quarantined_digest` 承诺非 accepted 或未决输入的集合。snapshot MUST NOT 静默隐藏会影响授权、可见性、E2EE epoch 或对象状态的 conflict、soft-fail 或 quarantine 记录。

## 7. Encrypted Envelope

加密载荷统一使用 `ak.schema.encrypted_envelope.v1`（artifact [`encrypted-envelope.schema.json`](../../artifacts/schemas/encrypted-envelope.schema.json)）。字段语义与约束以 [`../crypto-media/encryption-and-audit.md` §2.3.1](../crypto-media/encryption-and-audit.md) 为权威；snapshot chunk 中的密文 MUST 是同一 envelope 形态：

```json
{
  "scheme": "mls_rfc9420",
  "version": "1.0",
  "group_id": "base64url",
  "epoch": 42,
  "content_type": "application/json",
  "ciphertext": "base64url",
  "aad_visibility_event_id": "routing_digest",
  "aad": {
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "event_kind": "ak.message.create",
    "event_ref_digest": "sha256:..."
  },
  "key_ref": {
    "algorithm": "MLS",
    "group_state_ref": "ak:event:..."
  },
  "payload_digest": "sha256:...",
  "aad_digest": "sha256:..."
}
```

Principal Server sync surface MAY 依据 `aad` 路由元数据投递，但 MUST NOT 要求 plaintext content。
