---
title: Snapshot, Chunk, and Encrypted Envelope Schema
status: candidate
normative: true
stability: v1
updated: 2026-09-12
sidebar:
  label: Snapshot & Envelope
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Snapshot 用于快速 bootstrap Realm 当前态。Snapshot 不是真相源；真相源仍然是 signed Event Envelope 和可验证 Event history。

Snapshot manifest 的自身主标识字段使用通用 `id`，其值 MUST 是 `ak:realm_state_snapshot:*` typed identifier。其他对象、chunk payload、challenge 请求或 API hint 指向该 manifest 时使用 `realm_state_snapshot_ref`；`_ref` 不用于 manifest 自身 primary identity。

## 2. Snapshot Manifest

以下是字段齐全的结构示意；尖括号表示由实际状态、原始材料或签名产生的值，不是可接受的 wire 字节或摘要 KAT。可执行字节向量见 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json)。

```text
{
  "id": <RealmStateSnapshotId>,
  "realm_id": <RealmId>,
  "reducer_profile": "ak.reducer.core.v1",
  "security_class": "standard",
  "schema_profile_refs": [<SchemaProfileRef>],
  "eligibility_context": {
    "authority_refs": [<已确认 SealId>],
    "closure_command_refs": [<适用关闭命令 EventId>],
    "reducer_contract_digest": <SHA-256(JCS(完整 canonical contract-registry.json))>
  },
  "state_digest": <完整 Cell 状态根>,
  "frontier": {
    "event_ids": [<输入边界上未被覆盖的 EventId>],
    "timeline_hlc": <Hlc>
  },
  "event_set_commitment": {
    "algorithm": "merkle_event_set_v1",
    "root": <原始 Event 输入集合根>,
    "covered_event_count": <输入 Event 数>
  },
  "chunks": [{"chunk_ref": <内容寻址 BlobId>, "size_bytes": <canonical payload 字节数>}],
  "created_by": <完整 ActorId>,
  "created_at": <canonical UTC timestamp>,
  "authority_binding": {
    "authority_kind": "realm_policy_state_snapshot_issuer",
    "auth_state_digest": <签发者授权状态承诺>,
    "auth_frontier": [<已确认授权 EventId>],
    "checked_at": <canonical UTC timestamp>
  },
  "signature": {
    "kind": "detached_jws",
    "verification_method": <签发者 DID URL>,
    "payload_digest": <manifest 签名原像摘要>,
    "created_at": <canonical UTC timestamp>,
    "jws": <detached JWS>
  }
}
```

`closure_command_refs` 在没有适用关闭命令时为 `[]`；`verification_hints` 和 witness 列表按下文条件携带，不能用示意中的 `standard` 分支省略 high-assurance 所要求的证据。

## 3. Chunk Descriptor

```json
{
  "chunk_ref": "ak:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "size_bytes": 524288
}
```

Chunk descriptor 中的 `chunk_ref` 指向一个 snapshot chunk payload。Payload 是
[`realm-state-snapshot-chunk.schema.json`](../../artifacts/schemas/realm-state-snapshot-chunk.schema.json)
（`ak.schema.realm_state_snapshot_chunk.v1`，封闭 schema）一个实例的 canonical JSON：

```text
{
  "chunk_kind": "realm_state_snapshot_chunk",
  "realm_state_snapshot_ref": <manifest.id>,
  "index": 0,
  "reducer_profile": "ak.reducer.core.v1",
  "items": [
    {
      "kind": "cell",
      "id": <invite.live_target CellRef>,
      "state": {"revision_event_id": <确认命令 EventId>, "value": null},
      "state_model": "sequenced_state"
    },
    {
      "kind": "cell",
      "id": <strand.lifecycle CellRef>,
      "state": {
        "covered_event_ids": [<创建 EventId>, <归档 EventId>],
        "heads": [{"event_id": <归档 EventId>, "value": "archived"}]
      },
      "state_model": "causal_register"
    }
  ],
  "conflict_records": [],
  "soft_failed": [],
  "quarantined": [],
  "erasure_stubs": [],
  "eligibility_context_digest": <SHA-256(JCS(manifest.eligibility_context))>,
  "replay_events": [<完整原始 Event>],
  "replay_authority_refs": [<所需确切安全历史 SealId>]
}
```

此结构示意展示两种 Cell；其余模型使用 schema 对应分支。`replay_events` 及授权依赖必须覆盖全部 chunks 的真实重算需求，不得把空证据的摘要序列化 KAT 当成可接受的恢复证明。

**`items[]` 承载 reducer cell，不承载对象（normative）**。Snapshot 是确切资格上下文下的
Realm 状态缓存，普通 Cell 不需要 covering Seal，安全 Cell 保留实际确认 revision。其内容按
[`contract-registry.json`](../../artifacts/registry/contract-registry.json) `cell_writes[]` 登记的 cell
与其注册模型的完整状态。v1 没有登记任何「cell → canonical object」的组装规则——`ak.strand.create` 只把
`payload.object` 写进 `ak.component.strand.object.v1`，metadata / tracks / lifecycle / stage / position
各在自己的 cell 里——因此 snapshot MUST NOT 携带渲染后的对象：那会让 `state_digest` 取决于某一家实现的
私有 renderer。consumer 从 cell 派生展示对象的方式与它从 Event 重放派生的方式相同；对象的 `created_by` /
`created_at` 等 envelope 事实来自 `retype(id)` 指向的 create Event（[`../models/common-fields.md` §6.0](../models/common-fields.md)），不进 snapshot。

`items[]` 是封闭的单分支联合，每个元素逐字为 `{"kind": "cell", "id": <cell_wire_id>, "state": <state_object>, "state_model": <registered_model>}`：

- `kind` 逐字为 `"cell"`；`id` 是完整 canonical cell 引用 `ak:cell:<component>:<subject>`（[`encoding.md` §4](./encoding.md)）。
- 每个 item 必须声明与 canonical family 相同的 `state_model`。`causal_register` 的 state 是 `{covered_event_ids,heads}`，每个 head 是 `{event_id,value}`；覆盖身份与头身份去重，head 必须属于覆盖集合。`sequenced_state` 是 `{revision_event_id,value}`，其它集合/日志/计数模型使用 schema 的完整状态形状。模型不匹配或只给显示值均拒绝。
- 写过的 null、多值 heads 和已删除 dots 都必须保留；未写入者无 item，不能用缺席表示多头冲突。private family 不进入共享快照。每个 CellRef 在整个 manifest 唯一，按 canonical CellRef 排序分块。
- **scope 与披露权限（normative）**：Realm snapshot 只承载注册的 Realm 共享 scope（`scope_ref.kind` 为 `realm` 或 `realm_genesis`）的 Cell 与输入边界。Circle、Sidecar、actor-private 或其它受限 scope 的 Cell、原始 `replay_events`、引用及附加列表 MUST NOT 因下载 Realm snapshot 而泄露；依赖某个摘要不赋予读取该摘要所指材料的权限。依赖解析仍 MUST 遵守各既有接口的 scope、history visibility 和 capability 规则。若重算需要的材料不能合法取得，恢复保持 pending/unavailable；issuer MUST NOT 静默删去受限输入后把同一上下文声明为 complete。
- 每个 chunk 的 `eligibility_context_digest` 必须等于 `SHA-256(JCS(manifest.eligibility_context))`；该上下文精确绑定已确认 authority refs、关闭命令和 reducer 合同；`reducer_contract_digest` 恰为所使用完整 canonical `contract-registry.json` 对象的 `SHA-256(JCS(...))`，不使用语言生成代码或 HTTP 返回值的摘要。相同 scope/上下文才可直接合并普通状态；不同上下文先合并原始证据再重算资格与 coverage。
- `replay_events` 与 `replay_authority_refs` 是可重算材料，不是可丢弃的附件。恢复方必须取得活跃与未来关闭可能重新显露的旧值、原 producer 证明、因果及授权闭包。缺材料 pending；完整性根不能替代内容可用性。不得只凭快照签名任意删除覆盖历史。

- tombstone / archive / redaction 按各自注册 family 归约；普通 lifecycle 与 redaction 使用固定 D 模型，Circle 等关闭安全 scope 的命令仍使用 S 模型。它们不产生独立的 snapshot item stub 分支；hard erasure 另按下一条处理。
- **hard erasure（normative）**：若某 cell 的 canonical 值已因 hard erasure（存储边界内的删除动作，不是 Event）而无法复现，issuer MUST NOT 伪造或以占位值代替该 leaf；该 cell MUST NOT 出现在 `items[]`，而 MUST 以 `{"cell_ref", "stub"}` 列入 `erasure_stubs[]`，`stub` 是被 erasure receipt `retained_stub_digest` 绑定的 `ak.schema.erasure_verification_stub.v1`（[`erasure-verification-stub.schema.json`](../../artifacts/schemas/erasure-verification-stub.schema.json)）。consumer MUST 把它解释为 `[erased]` 占位，MUST NOT 解释为「从未存在」。含 erasure stub 的 snapshot 的 `state_digest` 与未裁剪 issuer 的不可比，consumer MUST NOT 据此判定分叉。
- **四个附加列表的承诺（normative）**：`conflict_records[]`、`soft_failed[]`、`quarantined[]`、`erasure_stubs[]` 都不是 `state_digest` 的 leaf。manifest `verification_hints.<list>_digest` = `<suite>:hex(H(canonical_json(<该列表按 chunk index 升序拼接成的数组>)))`，`H` 与 `state_digest` 同 suite。`erasure_stubs_digest` 在任一 chunk 的 `erasure_stubs[]` 非空时 MUST 存在；high-assurance snapshot MUST 通过 `verification_hints` 提交这些集合的 digest，不能静默隐藏影响授权、可见性、E2EE epoch 或对象状态的非 accepted 输入或 `⊥` cell。
- **恢复后仍须能精确回答 membership（normative）**：因果寄存器覆盖查询的完整坐标是 `(CellRef, eligibility_context, EventId)`。恢复方 MUST 根据已重算验证的该 Cell `covered_event_ids`，或在同一上下文中重放原始输入，精确判断旧 Event 是否属于该 Cell 的覆盖集 `C`。全局 `event_set_commitment` 的 membership 索引或 inclusion proof 只证明原始 Event 属于 snapshot 输入集合；它不能单独证明该 Event 写入了某个 Cell、在当前上下文有资格贡献，或已进入该 Cell 的 `C`。原始材料的 membership 路径仍是保留索引并重算同一 root/count，或获取该 root 下的有效证明；恢复因果覆盖时还 MUST 校验 registry 目标、资格和该 Cell 状态。缺证据时 MUST hold / fail closed，MUST NOT 当成 `false`。未经有权 fence，实现 MUST NOT 只保留最近 N 次写入、删除 `value=null` 的 head，或删除「该 Event 曾被该 Cell 覆盖」这一事实；否则迟到分支会复活已取代的写入。原始 Event 集的三值 membership 判定（`covered` / `not_covered` / hold）由 active 向量 `ak.vector.realm_state_snapshot.restore_covered_membership.v1`（[`conformance-vectors.md` §3.8](./conformance-vectors.md)）承载，机器 fixture 是 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_restore_covered_membership` 块；该向量不单独证明每 Cell 的资格与覆盖，后者还须验证目标派生、完整状态和上下文重放。
- content-addressed `chunk_ref` 的内嵌 suite/digest MUST 覆盖 chunk payload 的 canonical JSON bytes，是该 bytes 的唯一 wire commitment；descriptor 不携 sibling `digest`。Manifest `state_digest` 不直接覆盖 descriptor 文本，而覆盖下节定义的 cell leaves。

conformance：`ak.vector.realm_state_snapshot.state_digest_recompute.v1`（[`conformance-vectors.md` §3.7](./conformance-vectors.md)）固定所列注册模型的 leaf 原像、leaf、root、suite、chunk 边界与全部拒绝路径；两个实现对同一 fixture MUST 算出同一 `state_digest`。

Chunk 边界 MAY 由实现按本地传输目标大小选择，但 MUST 以完整 `items[]` 元素为边界；实现 MUST NOT 把单个 item 或 JSON token 切开。每个 chunk payload 仍必须是上方 `ak.schema.realm_state_snapshot_chunk.v1` object 的完整 canonical JSON。把整份 reducer state bytes 先序列化、再按 byte range 切块的 dev bundle 形态不是合法的 `ak.schema.realm_state_snapshot_chunk.v1` chunk payload；这类实现 MUST NOT 把 byte-range chunk 描述为 manifest `chunks[]` 的标准 chunk。

Snapshot-assisted pruning 只能删除或压缩某个存储边界内的 raw payload / derived material；它不删除协议历史事实。若实现因 retention、track archive、Realm tombstone 或 hard erasure 裁剪了 cell 内容，snapshot MUST 按上文 hard erasure 规则以 `erasure_stubs[]` 提交其存在。Consumer 不得把 snapshot 中缺少的 cell 解释为“从未存在”，除非 event-set commitment 和 reducer profile 明确证明该 cell 不在 covered event set 的写入范围内。

## 4. State Hash

快照 `state_digest` 承诺全部已声明 Cell 状态；manifest 签名额外绑定可见 scope 和资格上下文；它不等于 Seal 的安全 `state_root`，也不证明全网消息收齐。普通数据不需要 covering Seal。

leaf_data 恰为 `JCS({cell:item.id,state_model:item.state_model,state:item.state})` 的 UTF-8 字节，按 CellRef 的 Unicode code point 升序。每个 chunk 先验内容摘要、模型、完整原始材料和资格上下文，再进行归约比对。所有 chunks 合并后用 RFC6962 的 H(0x00 || leaf_data)、H(0x01 || left || right) 和空树规则重算 state_digest；不重复提升奇数尾节点。suite 从 manifest 已认证的 reducer/Realm 授权上下文解析，不能依据待验证值自选。

manifest 签名同时绑定 `eligibility_context`、chunk 列表、state_digest 与 event_set_commitment。相同 Cell 显示值而不同覆盖身份、授权上下文或 tombstone，必须产生不同被签材料。只校验 state_digest 相同不能跳过 eligibility_context 比较。恢复后的已知撤销更新可重新分类旧 Event，必须保留足够原始数据；明确硬删除的数据只能报告不可恢复。

## 5. Snapshot Signature

本节与 §6 的 manifest authority、历史 commitments 和 witness/challenge 验证由接纳外部 snapshot 的服务器或独立审计者执行。普通客户端消费自己 Account Station 已确认的 snapshot，只核对来源、请求 Realm/basis、格式及下载内容 hash/端到端认证；不得下载治理历史、执行 omission challenge 或 raw replay 来认证自己 Station 的结果。相关角色边界见 [服务器可信结果](../sync/server-trusted-results.md)。

Manifest MUST 仅包含一个 normative `signature` 字段。`signature` MUST 使用与 Event proof 相同的 detached proof 结构，并 MUST 覆盖 manifest payload（排除 `signature` 自身）的 canonical 编码。被签名 transcript 因此包含 `id`、`realm_id`、`reducer_profile`、`schema_profile_refs`、`state_digest`、`frontier`、`event_set_commitment`、`chunks[]` descriptor（content-addressed `chunk_ref` / `size_bytes`）、`security_class`、`verification_hints`、`created_by`、`created_at`、`authority_binding` 与 `eligibility_context`；字段清单与顺序 MUST 与 [`realm-state-snapshot.schema.json`](../../artifacts/schemas/realm-state-snapshot.schema.json) `signature` 的 `x-canonical-bytes-include` 完全对齐。其中 `security_class` 被纳入签名输入，使 `high_assurance → standard` 降级无法在不使签名失效的情况下完成。consumer MUST 先验证该 transcript，再从每个 `chunk_ref` 恢复 suite/digest 并验证 chunk payload。

签名 DID MUST 属于以下之一：

- Realm owner
- Realm creator or active Realm admin
- trusted snapshot issuer
- witness quorum（`authority_kind="witness_quorum"`，其 attestation 载体、context、canonical
  projection 与 admission 规则见 §5.1）
- policy-approved snapshot issuer

接纳外部 snapshot 的服务器在采用之前 MUST 校验 signature、`authority_binding`、`state_digest`、frontier、`event_set_commitment` 与每个 chunk 的 digest。`frontier.event_ids` 是 snapshot 边界，`event_set_commitment` 只承载该边界内完整 reducer-input Event 集合的 root 与 count；consumer MUST 从已验证 Event 集重算 commitment，不得接受额外的 Event id 镜像字段。签名者权限 MUST 以 manifest `created_at` 为时点进行评估；manifest 的唯一 issuer 来源是 `created_by`，`auth_frontier` / `auth_state_digest` 必须覆盖 snapshot frontier 以及在 `created_at` 之前可知的全部相关 admin / snapshot-issuer grant 或 revoke 事件的 accepted Realm auth state。`auth_state_digest` 是 issuer-local opaque commitment：verifier MUST 检查它与 `auth_frontier` 绑定一致，并 MUST 按自己可取得的 accepted auth state 回放或查询来判定签名者在 `created_at` 的授权与撤销新鲜度；除非部署 profile 另行声明可复算的 auth-state canonical encoding，verifier MUST NOT 只因无法逐字重算该 digest 就接受或拒绝。若签名者在 `created_at` 之前已被撤销，或 verifier 无法确认其权限的撤销新鲜度，snapshot MUST 被隔离或以 `realm_state_snapshot_issuer_revoked` 拒绝。

**最大接受窗口（normative）**：仅当采纳时同时满足以下**全部**条件，manifest 才可用于 snapshot bootstrap：

- `(now - manifest.created_at) ≤ realm_state_snapshot_max_acceptance_age_ms`。默认 `realm_state_snapshot_max_acceptance_age_ms = 2_592_000_000`（30 天）；`security_class=high_assurance` 的 Realm MUST 收紧到 ≤ `604_800_000`（7 天）。超出该窗口后，即使曾经有效的 snapshot 也 MUST 被拒绝——接纳服务器 MUST 请求新的 manifest，因为 auth state 与 policy 的漂移已使旧 snapshot 无法安全代表当前状态。
- 签名者属于 §5 列出的任一合法类别，且其权限链在当前 auth state 下仍**可解析**。如果该链已被裁剪（例如 Realm tombstone、governance reset 或越过 manifest 时代的 auth-chain compaction），snapshot MUST 被拒绝。
- 撤销新鲜度以 `authority_binding.auth_frontier` / `auth_state_digest` 解析出的签名者撤销状态为准（snapshot manifest 无独立 `signer.revoked_at` wire 字段；撤销时点是从该 auth state 派生的逻辑值）。判定规则:由 auth state 解析出的签名者撤销生效时点 MUST NOT exist，**或** 严格晚于 `manifest.created_at`。严格在 `created_at` **之后**生效的撤销不追溯使 manifest 失效，但接纳服务器在为当前写入提供治理结果前 MUST 验证 snapshot frontier 之后的必要治理增量。依赖缺失时该操作保持 pending/unavailable；客户端不自行补做历史验证。服务器可按 §6.2 的外部 snapshot 接纳规则重建所需状态。

### 5.1 Snapshot Witness Attestation（normative）

`authority_binding.witness_attestations[]` 是**独立于 manifest 的对象族**
`realm_state_snapshot_witness_attestation`（[`realm-state-snapshot.schema.json#/$defs/realm_state_snapshot_witness_attestation`](../../artifacts/schemas/realm-state-snapshot.schema.json)），
不是顶层 `signature` 的复签。每行是闭合 `{witness_id, proof}`：`witness_id` 是该 witness 的稳定
`did_core_id`，`proof` 是共享 detached proof。

**独立 context**。该族在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)
登记的唯一 context 是 `ak.realm_state_snapshot_witness_attestation_proof.v1`；schema 侧的
`x-arkret-proof-context` 注解与本节 MUST 逐字一致。顶层 `ak.realm_state_snapshot_proof.v1` MUST NOT 被复用
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
  "context": "ak.realm_state_snapshot_witness_attestation_proof.v1",
  "witness_id": <this row's witness_id>,
  "realm_state_snapshot_id": <manifest.id>,
  "realm_id": <manifest.realm_id>,
  "reducer_profile": <manifest.reducer_profile>,
  "schema_profile_refs": <manifest.schema_profile_refs>,
  "security_class": <manifest.security_class>,
  "state_digest": <manifest.state_digest>,
  "frontier": <manifest.frontier>,
  "event_set_commitment": <manifest.event_set_commitment>,
  "issuer": <manifest.created_by>,
  "authority_kind": <manifest.authority_binding.authority_kind>,
  "auth_state_digest": <manifest.authority_binding.auth_state_digest>,
  "auth_frontier": <manifest.authority_binding.auth_frontier>,
  "realm_state_snapshot_created_at": <manifest.created_at>,
  "eligibility_context": <manifest.eligibility_context>
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
  MUST 以 `realm_state_snapshot_authority_unverified` 拒绝，且不计入 quorum。
- **key validity 与撤销新鲜度**：`proof.verification_method` 的 controller `did` MUST 由已登记
  method adapter 验证并 `project(did) == witness_id`（禁止DID 与 `did_core_id` 直接字符串
  比较）；该 key 在 `manifest.created_at` MUST 处于有效且未撤销状态，判定规则与 §5 对 issuer 的
  撤销新鲜度规则相同。verifier 无法确认撤销新鲜度时 MUST 隔离或拒绝，MUST NOT 计入 quorum。
- **去重**：quorum 计数以 `witness_id` 为单位。同一 witness 的多个 key 或多份签名只计一次。
- **threshold**：threshold MUST 仅由上述 accepted auth/policy state 给出。manifest 不携带 threshold
  镜像；去重后的有效 witness 数低于 policy threshold 时 MUST 以
  `realm_state_snapshot_authority_unverified` 拒绝。

**v1 没有"等价 quorum proof"**。v1 只有 `witness_attestations[]` 这一个 typed carrier。任何未在本节
定义的替代已认证治理签名 证据 MUST NOT 被接受，实现 MUST NOT 用私有字段、`x_*` 扩展或带外材料补洞；
需要新的 quorum 形态时，必须先在本节定义 closed union 分支、独立 context 与验证合同，而不是让
verifier 各自解释。

conformance：`ak.vector.realm_state_snapshot.witness_quorum_attestation.v1` MUST 覆盖缺失 attestations、重复
signer、未授权 witness、已撤销 witness、阈值不足、错误 context、错误 projection、witness 列表被改写、
有效 quorum，以及顶层 issuer signature 对最终 witness 集合的绑定。

`proof`、`verification_method`、`generator_signature` 与 `state_signature` 不是 v1 snapshot manifest 顶层字段。v1 manifest 只允许 §（上文）的**单一** `signature`（detached proof，内部含 `verification_method`）；上述易混淆名作为 manifest 顶层字段时 MUST 拒绝。权威字段集以 [`realm-state-snapshot.schema.json`](../../artifacts/schemas/realm-state-snapshot.schema.json) 为准。

## 6. Inclusion 与 Omission 防御

Snapshot signer authority 只能证明谁签发了 reduced state；它不能证明签名者已包含本应包含的全部 accepted Event。因此 v1 snapshot manifest MUST 携带 `event_set_commitment`。

`event_set_commitment.root` 承诺 snapshot frontier 覆盖的 Event Envelope ID 与 canonical event hash 的有序集合。输入 leaf entry MUST 按 `(actor_id, actor_seq, event_id)` 排序；每个 entry 的 canonical JSON object 必含 `{event_id,event_digest,actor_id,actor_seq}`；仅当原始签名 Event 携带 `hlc` 时，entry MUST 原样携带该值，原 Event 缺失时 MUST 省略，不能写 null，也不能用 receiver 的接收时间、当前时钟或本地 HLC 补造。实现 MUST 至少支持以下一种算法：

- `ordered_event_id_sha256_v1`：对排序后的 entry array 计算 `sha256(canonical_json(entries))`；空集合输入为 canonical JSON `[]`。
- `merkle_event_set_v1`：先对每个 entry 计算 `sha256(canonical_json(entry))` 作为 `leaf_data`，再按 [`encoding.md`](./encoding.md) §3.3.1 的统一 RFC 6962 规则计算 `sha256(0x00 || leaf_data)` leaf 与 `sha256(0x01 || left || right)` internal node；空集合 root 为 `sha256` 空字节。无域分隔的 root MUST 拒绝。

### 6.1 能力边界（normative — what omission challenge can and cannot prove）

Inclusion challenge 的安全保证范围 **MUST** 在 spec 文本与实现 UI 中按下表理解，任何超出该范围的安全声明都是夸大:

| 能力 | 可证明? | 说明 |
| --- | --- | --- |
| issuer 是否对**它声明覆盖的集合**保持内部一致 | 可证明 | challenge 抽样命中即可重算 commitment root,确认 issuer 未声明地重写它声明过的某个 event 内容。 |
| issuer 是否漏掉了**接纳服务器不知道的** actor 或 event 分支 | 不可证明 | 接纳服务器只能用 issuer-provided frontier 或 issuer-listed active actor 集合抽样；它**不知道**该追问 issuer 未列出的 actor。issuer 可以构造一个自洽但缺失若干 actor 的 snapshot，接纳服务器拿不出对照。 |
| issuer 是否对**接纳服务器已知的** event_id / actor_seq range 区间漏掉了事件 | 仅在附加条件下可证明 | 接纳服务器 SHOULD 用自己已保存 的 event_id / actor_seq range 抽样；命中 0 个 `kind="event_id"` 样本时挑战形同虚设。`security_class=high_assurance` 部署 SHOULD 在 challenge `samples[]` 中混入**至少一个**接纳服务器自有的 sample seal。 |
| issuer 是否同时签发了多版本不一致的 snapshot(split-view) | 不可证明 | inclusion challenge 是 issuer-side 单向 query;两份 issuer 给不同接纳者的不同 snapshot 互相不知道。Split-view 检测必须依赖 federation §4.5 frontier exchange 或 §8 fork-detection。 |

简言之: **`event_set_commitment` + inclusion challenge 是"已知集合包含性 + 内容一致性"检查，不是 omission 完整性证明**。任何 spec 措辞、UI 文案、安全审计声明 MUST NOT 把 inclusion challenge 描述为"防止 issuer 漏发任何事件"。

### 6.2 High-assurance bootstrap 的额外要求

`security_class=high_assurance` 的 Realm MUST 在采纳任何 snapshot 之前执行该挑战；其他 profile SHOULD 执行。同时，该 security_class 的接纳服务器 **MUST** 使用下列两个验证路径之一检查可取得的边界材料；这不消除 §6.1 的未知输入局限。`actor_seq_ranges[]` 只是两个路径都可使用的区间内部一致性材料，不是第三个独立验证路径：

1. **Independent witness path**：从至少一个独立 witness（部署 policy 明确列出且非 snapshot issuer 控制）拉取该 Realm 在 `manifest.created_at` 时刻的 active actor-set commitment 与 actor sequence upper-bound commitment，接纳服务器用其与 snapshot manifest 中声明的 actor set 比对；不一致 MUST quarantine。`event_set_commitment` MUST 同时携带 schema 中的 `actor_seq_ranges[]`，为每个已见证 actor 绑定 `[from_seq, to_seq]` 与该区间的 commitment `root`；该 commitment 使用 `event_set_commitment.algorithm` 声明的现有算法（`ordered_event_id_sha256_v1` 或 `merkle_event_set_v1`）计算，不引入第三种 wire algorithm。
2. **Raw replay path**：无独立 witness actor-set commitment 可用时，接纳服务器 **MUST NOT** 把 snapshot 本身作为 high-assurance accepted state；它只能作为加速索引，实际授权决策 MUST 由原始 Event 完整回放得到。回放尚未完成时，snapshot completeness 保持 unverified / degraded。独立 witness 或 federation peer 后续提供可验证的精确 Event 集合证据时，只能对该证据覆盖的授权 scope 和确切集合声明已核对；不能仅凭来源数量、actor 集合或 sequence 上界相同升级为全局完整。

上述检查仍全部必需，但 actor-set 与 sequence upper-bound commitment 只能核对独立 witness 实际见证的 actor/序号边界。同一 `(realm_id, actor_id, actor_seq)` 可以有多个合法 sibling；漏掉其中一条不会改变 actor 集合或最高 sequence。由 issuer 提供且内部自洽的 range root 也不能独立证明这些 sibling 已收齐。没有独立的精确 Event 身份集合证据，任一路径都 MUST NOT 声称全网全部分支完整；原始材料重放只能证明所取得输入的验证和归约。此限制不放松 signature、inclusion challenge、range commitment 或 raw replay 的既有要求，也不新增 witness wire 字段。

仅由 snapshot issuer 自己声明并签发的 `actor_seq_ranges[]`，即使所有已声明 actor 的区间、root 与 count 均自洽，也只能证明这些区间内部无洞；它 MUST NOT 被解释为“没有未知 actor 被整体省略”的证明。整 actor 省略负例由 `ak.vector.realm_state_snapshot.inclusion_challenge.v1` 承载。

接纳服务器不得把未经其验证的第三方 snapshot 声明为 accepted。普通客户端使用自己 Station 已确认结果时，不因未执行本地历史重放而显示 lower-trust/degraded；服务器尚未确认的结果保持 pending。

挑战 wire 格式（POST 到 `verification_hints.inclusion_proof_url`）：

请求体：

```json
{
  "realm_state_snapshot_ref": "ak:realm_state_snapshot:0196419a-8000-7000-8000-000000000000",
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
  "realm_state_snapshot_ref": "ak:realm_state_snapshot:0196419a-8000-7000-8000-000000000000",
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

1. **随机采样**：接纳服务器 MUST 独立于 issuer 提示进行采样。event_id 样本 MUST 从 接纳服务器本地位于 snapshot frontier 内的 Event 集合中均匀抽取 `n ≥ max(20, ceil(log2(covered_event_count)))` 个不同 ID。actor_seq_range 样本 MUST 来自该 snapshot 已知活跃的不同 actor，每个长度 100，至少 3 段。
2. **分支验证**：每个 `proofs[i].merkle_branch` MUST 在 `commitment_algorithm` 下针对 `commitment_root` 验证通过；`commitment_root` MUST 等于 manifest 的 `event_set_commitment.root`（不允许重新绑定）。
3. **缺口归因**：对于采样范围内每个缺失的 `actor_seq`，响应 MUST 在 `verification_hints.{soft_failed_digest, quarantined_digest, conflict_records_digest}` 之一中给出对应条目（`digest_index` 是该 digest 承诺列表中的位置）——禁止静默缺口。
4. **签名**：`issuer_signature` MUST 来自 §5 列出的 DID（Realm owner / creator / admin / trusted snapshot issuer / witness quorum），并 MUST 以 manifest `created_at` 为时点可验证。
5. **失败处理**：若任一采样到的 accepted Event 缺失、任一分支验证失败、任一缺口缺少归因，或签名验证失败，接纳服务器 MUST 以错误 `inclusion_proof_failed` 拒绝（见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；若签名者在 `created_at` 当时或之前已被撤销，接纳服务器 MUST 以 `realm_state_snapshot_issuer_revoked` 拒绝。
6. **新鲜度**：响应 MUST 在 manifest 的 `verification_hints.challenge_window_seconds` 内收到；过期响应 MUST 重试，MUST NOT 静默接受。

> **向量登记状态**：上述采样规则 1（`n ≥ max(20, ceil(log2(covered_event_count)))` 的 event_id 抽样、至少 3 段 `actor_seq_range`）与规则 2 的 merkle branch 验证注册为 active 向量 `ak.vector.realm_state_snapshot.inclusion_challenge.v1`，并由 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_inclusion_challenge` fixture 及其 registered runner 承载。实现 MUST 按本节 prose 与 fixture 规则执行挑战，并将该 active vector 纳入 high-assurance bootstrap 校验。

`verification_hints.conflict_records_digest`、`soft_failed_digest` 与 `quarantined_digest` 承诺非 accepted 或未决输入的集合。snapshot MUST NOT 静默隐藏会影响授权、可见性、E2EE epoch 或对象状态的 conflict、soft-fail 或 quarantine 记录。

## 7. Encrypted Envelope

加密载荷统一使用 `ak.schema.encrypted_envelope.v1`（artifact [`encrypted-envelope.schema.json`](../../artifacts/schemas/encrypted-envelope.schema.json)）。字段语义与约束以 [`../crypto-media/encryption-and-audit.md` §2.3](../crypto-media/encryption-and-audit.md) 为权威；snapshot chunk 中的密文 MUST 是同一 envelope 形态：

```json
{
  "version": "1.0",
  "content_type": "application/json",
  "encryption_context": {
    "epoch": 42,
    "group_state_ref": "ak:event:..."
  },
  "ciphertext": "base64url"
}
```

Station sync surface 只按 outer signed Event 与已注册的最小 routing context 投递；不得从密文 envelope 要求或读取复制的 scope、kind、group、scheme、sender 或 plaintext content。
