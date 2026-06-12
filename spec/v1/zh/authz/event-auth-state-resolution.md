---
title: Event Auth、CBA 双平面与状态收敛
status: candidate
normative: true
stability: v1
updated: 2026-06-11
sidebar:
  label: Event Auth & State Resolution
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret v1 的一致性层采用 **CBA（Control-plane Basis-committed Sealing）**：

- **数据面**（data plane）承载消息、内容、reaction、计数、协作文本、草稿和默认业务对象。数据面 Event 是签名因果 hash-DAG + Lattice / CRDT 输入；验签、授权与 `seal_ref` 验证通过后即可本地投影、转发和参与 join。数据面没有事件级 Seal finality 字段、没有 pending→effective 状态机、没有全局排序闸门。
- **控制面**（control plane）承载 membership、capability、policy、notary、lifecycle、MLS epoch / governance binding 以及显式 `sealed=true` 的对象。控制面 Move 由 Seal 裁决，提供 finality、治理 `state_root`、问责与 transparency。
- Seal 对数据面只做**观测承诺**（`data_view_root` / `data_event_set_root` / `availability_root`），不做数据面准入，不让未观测的数据面 Event 失效，也不把数据面结果升级为控制面 finality。

非目标：本文不提供全局总序、经济 finality、全文搜索、媒体分发、typing / presence 等派生层行为；不证明"不存在没人见过的 Event"；轻客户端不验证全 Realm reducer 执行。

## 2. 术语

| 术语 | 定义 |
| --- | --- |
| DataEvent | 只写 data plane cell 的签名 Event。它携带 `seal_ref`，不携带 `seal_basis`。 |
| Control Move | 只写 control plane cell 的 reducer-input Event。它携带 `seal_basis`，由 Seal 裁决。 |
| Seal | 控制面 Seal。它用 `predecessor_refs[] + delta[]` 定义递归控制面覆盖集、承诺治理 `state_root`，并可附带数据面观测承诺。 |
| Cell | 可被 Lattice 合并的最小状态单元，标识为 `ck:cell:<component>:<subject>` 或等价 canonical tuple。 |
| Plane | Realm schema 对 cell family 的安全分级：`data` 或 `control`。plane 是安全边界，cell 是冲突域。 |
| Lattice | Realm schema 为每个 cell family 选择的封闭核心代数类型。`join()` 返回值或 bottom (`⊥`)。 |
| Bottom (`⊥`) | 某个 control cell 或 opt-in control object 在当前 seal view 下无有效单值或存在非法状态。数据面默认不产生协议级 `⊥`；普通冲突暴露为多 head。 |
| seal_ref | DataEvent 声明的授权基准：一个已接受控制面 Seal id。 |
| seal_basis | Control Move 签名覆盖的控制面基线：`{leaves[], control_event_set_root, state_root}`。 |
| control_event_set_root | Seal 对递归控制面覆盖集 `covered_set(S)` 的 authenticated root。basis、inclusion、non-membership、receipt obligation 与 censorship evidence 都以它为锚点。 |
| KeyView | Seal 对某个 data cell 的观测记录，包含 cell、lattice type、heads / value digest 与 last covered event。 |
| SeenReceipt | relay / notary / witness 对某个数据面 Event 的签名"已看见"回执。它不是准入证明，不进入 state。 |
| AvailabilityReceipt | holder 对某个 Event bytes 在 retention 窗口内可获取的签名承诺。 |

## 3. Plane 判定

Realm schema 中每个 cell family MUST 声明 `plane`：

- **强制 control**：authorization root、policy、membership、capability、notary、lifecycle、MLS epoch / key schedule / governance binding，以及现有规范中禁止作为 `mv_register` 授权根的 cell family。
- **默认 data**：消息、内容、reaction、普通 metadata、计数、协作文本、草稿和其它未声明为 control 的业务 cell。
- **opt-in control**：任意 data cell family MAY 声明 `sealed=true` 升入控制面，用于合规审计、强一致单值、法务保留或高风险 workflow。

一个 Event MUST NOT 跨 plane 写入。若一个业务动作同时需要改治理状态和内容状态，producer MUST 拆成两个 Event：先提交控制面 Move，经 Seal 接受后，再用新的 `seal_ref` 产生 DataEvent。

数据面 schema MUST NOT 依赖硬性跨 cell invariant，例如全局唯一性、容量硬上限、跨 list 原子 move 或多对象单赢家裁决。需要这些 invariant 的对象 MUST 声明 `sealed=true` 升控制面，或使用本文件 §9.4 的 per-object sequencer。

## 4. DataEvent

DataEvent 是普通 Event Envelope 的一种语义形态。Wire object 仍是 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)。

```text
DataEvent {
  event_id / event_digest / proofs
  realm_id
  kind
  actor_id / actor_seq / prev_refs[]
  causal_refs[]                  // 语义因果前驱 event_digest；可由 refs[role=causal] 表达
  seal_ref                 // 单个控制面 Seal id
  auth_context {
    did
    key_id
    key_epoch
    credential_epoch?
    capability_refs[]
  }
  effects[]                      // 仅 data plane cells
  payload
  conflict_keys_digest?          // 可选诊断：effects[] 派生 cell id 集合的摘要
  hlc                            // 纯诊断
}
```

DataEvent 规则：

1. DataEvent MUST 携带 `seal_ref` 与 `auth_context`。
2. DataEvent MUST NOT 携带 `seal_basis`、`preconditions` 或任何 pending / finality 字段。
3. `effects[]` MUST 只引用 data plane cell。若任一 effect 指向 control plane cell，receiver MUST `schema_violation(reason=plane_cross_write)`。
4. `causal_refs[]` / `refs[]` 只表达业务因果，不承担全局完整性证明。
5. `event_digest` 是去除 `proofs` 与 `unsigned` 后 canonical Event bytes 的 hash；`proofs[]` 验证 actor / device / service 对该 digest 的签名。
6. `conflict_keys_digest`（可选）是对 `effects[]` 派生出的 canonical 升序 cell id 列表的摘要。producer 与 verifier 各自按自己的 schema 版本派生该集合；不一致只产生 `schema_derivation_mismatch` 诊断，用于及早暴露两侧 schema 派生分歧。该字段**不是**安全边界：无论它是否存在，verifier MUST 一律从 `effects[]` 派生冲突域。

### 4.1 `auth_context` 与 epoch pinning

DataEvent 的 `auth_context` MUST pin 事件签名时 producer 声称的身份与授权 epoch：

```text
auth_context {
  did
  key_id
  key_epoch
  credential_epoch?
  capability_refs[]
}
```

Verifier MUST 证明：

1. `proofs[].verification_method` 对应 `auth_context.did#key_id` 或等价 DID verification method。
2. `key_epoch` / `credential_epoch` 在 `seal_ref` 对应 seal 的控制面状态下有效。
3. `capability_refs[]` 在该 seal 的治理 `state_root` 中可解析、未撤销，并覆盖 DataEvent 的 `effects[]`。

Verifier MUST NOT 只查"当前 DID 文档"来验证旧事件；DID/key/capability 的有效性以 `seal_ref` 对应控制面 seal 为准。

### 4.2 DataEvent 验证

```text
verify_data_event(E):
  1. 验 canonical bytes、event_digest、proofs[] 与 realm_id 绑定。
  2. 验 actor chain：actor_seq / prev_refs[] 对同 actor 成链；同高 sibling 按 actor fork 规则处理。
  3. 验 E 不含 seal_basis / preconditions，且 effects[] 仅写 data plane cell。
  4. 验 auth_context epoch pinning。
  5. 验 seal_ref (§4.3)。
  6. 对每个 effect 执行该 data cell 的 lattice validate_op。
  7. 通过后进入本地 data DAG，可立即投影、转发和参与 join。
```

DataEvent 通过验证后不是"被 seal final"，而是**本地终态**：相同 data DAG 输入下，所有 verifier MUST 得到相同 data join 结果。后续发现的有效并发 DataEvent MAY 改变同一 data cell 的 join / exposed heads。

### 4.3 `seal_ref` 验证与撤销

`seal_ref` 的语义是："我声称我的写入权基于这个控制面 seal"。

Receiver MUST：

1. 验 `seal_ref` 是本 Realm 已验证控制面 Seal。轻客户端 MAY 用该 seal `state_root` 下 membership / capability inclusion proof 验证所需授权 cell。
2. 在 `seal_ref` 的治理状态下解析 `auth_context.capability_refs[]`，并证明 issuer 持有所需写权限且未撤销。
3. 若 receiver 尚未观察到覆盖该 issuer / capability 的后续撤销 seal，则按 `seal_ref` 的授权状态接受。
4. 若 receiver 已观察到撤销 seal `R`，且 `R` 是 `seal_ref` 的后继，则只按缺口距离判定：

```text
if distance(seal_ref, R) <= revocation_freshness_window:
  MAY accept but mark query grade stale
else:
  MUST reject or hide the DataEvent
```

该规则不判断事件真实签发时间，也不依赖本地接收时间。producer 在本地已知撤销 seal 后仍用旧 `seal_ref` 签 DataEvent，协议不把它单独定义为可证明 fault；但所有已观察到 `R` 且窗口超限的 receiver MUST 拒绝或隐藏这些事件。需要强撤销即时性的 Realm SHOULD 缩短 `revocation_freshness_window`，或将相关 cell family 声明为 `sealed=true`。

Grant 晚于 producer 最新 seal 签发时，producer MUST 等下一个控制面 seal 后再签 data write。治理低频，等待 seal 是可接受成本。

### 4.4 数据面传播与 SeenReceipt

数据面传播使用 gossip、anti-entropy 或 RBSR 类集合调和。同步摘要可以作为 federation probe 的 data frontier。

Relay / notary / witness 收到 DataEvent 时 SHOULD 返回：

```text
SeenReceipt {
  realm_id
  event_digest
  received_at
  receipt_seq
  expires_at
  issuer
  signature
}
```

SeenReceipt 只证明"被某个主体看见"，不证明事件有效、不提议排序、不进入控制面 state。部署 MAY 关闭 SeenReceipt；关闭后同账号 RYW 与数据面审查诊断能力降低。

## 5. Control Move

Control Move 是写 control plane cell 的 Event。它仍使用 Event Envelope，但 MUST 携带 `seal_basis`，MUST NOT 携带 `seal_ref`。

```text
ControlMove {
  event_id / event_digest / proofs
  realm_id
  actor_id / actor_seq / prev_refs[]
  preconditions[]
  effects[]                      // 仅 control plane cells
  seal_basis {
    leaves[]                     // accepted Seal id, canonical 升序去重
    control_event_set_root       // leaves view 覆盖的控制面事件集合 root
    state_root                   // leaves view 下的治理 state root
  }
  refs[]
  payload
}
```

Control Move 规则：

1. `seal_basis` 的三个字段全部进入 canonical Event bytes，并由 `event_digest` / `proofs[]` 覆盖。
2. `leaves[]` MUST 只引用 accepted Seal。单 leaf basis 是轻 producer 的默认形态。account client 铸造单 leaf basis 的注册来源是 `ck.self.events.frontier` 的 `realm_id` 形响应（Realm Seal view `{realm_id, seal_id, control_event_set_root, state_root, hlc?}`，见 `../sync/service-http-binding.md`）；该来源不可用时 MUST fail closed，不得伪造 basis。
3. 多 leaf basis 只有完整 verifier 或持有 signed view certificate / state transition proof 的 producer MAY 签；轻客户端 MUST NOT 签自己无法验证的 multi-leaf union basis。
4. `effects[]` MUST 只引用 control plane cell。若需同时写 data cell，必须拆成后续 DataEvent。
5. `preconditions[]` 与 `effects[]` 是原子集合；任一 precondition 不成立，整个 Control Move 失败。

### 5.1 Control Move 验证

```text
verify_control_move(M, pre_state):
  1. 验 canonical bytes、event_digest、proofs[] 与 realm_id。
  2. 验 seal_basis.leaves[] 均在接收 Seal 的 predecessor closure 内。
  3. 验 seal_basis.control_event_set_root 与 leaves view 的控制面事件集合一致。
  4. 验 seal_basis.state_root 与 leaves view 的治理 state 一致。
  5. 验 refs[] 中所有 critical ref 已知且 valid。
  6. 对每个 precondition 读取 pre_state 并判定。
  7. 对每个 effect 执行 lattice validate_op 与 authz check。
  8. PASS / FAIL。
```

轻节点可以依赖 `control_event_set_root` 的 inclusion / non-membership proof 和治理 state inclusion proof 做局部验证；缺 proof 时 MUST fail closed，不得盲信未验证 root。

## 6. Seal

Seal 的 wire schema 见 [`seal.schema.json`](../../artifacts/schemas/seal.schema.json)。

```text
Seal {
  id
  realm_id
  predecessor_refs[]
  delta[]                       // 本 Seal 新增的控制面 event_digest, canonical 升序
  control_event_set_root        // covered_set(S) 的 authenticated root
  state_root                    // 仅治理 cell
  completeness_root             // 控制面 per-actor 区间承诺
  notary_seq
  notary_signature
  sealed_at                   // 诊断
  hlc                           // 诊断

  data_view_root?               // observational
  data_event_set_root?          // observational
  availability_root?            // observational
  coverage_scope?               // observational
}
```

### 6.1 Seal id 与签名 transcript

`id = ck:seal:<algo>:<hex>`，hex MUST 等于 `H(seal_canonical_bytes)`。`id` 与 `notary_signature` 不进入 `seal_canonical_bytes`。除这两个字段外，所有顶层字段都进入 canonical bytes 和 signature transcript，包括 `control_event_set_root`、`notary_seq` 与所有 optional observational roots。

Receiver MUST：

1. 重算 `H(seal_canonical_bytes)` 并与 `id` hex 比对。
2. 验 `notary_signature` 覆盖同一 canonical bytes。
3. 拒绝任何非 canonical list order 或重复项。

### 6.2 `control_event_set_root`

Seal 的累计控制面覆盖集不作为必需 wire 字段出现，而由递归规则定义：

```text
covered_set(S) = set(S.delta) union covered_set(P) for every P in S.predecessor_refs
```

Seal MUST 签 `control_event_set_root`。默认 root 是对 canonical 升序 `covered_set(S)` 的 RFC6962 Merkle root：

- inclusion proof 使用 Merkle audit path；
- non-membership proof 使用 sorted-neighbor proof；
- 空集合 root 使用 RFC6962 空树 root；
- 更复杂的 radix trie / zkVM state proof MAY 在后续规范中作为规模触发机制定义，但 v1 core 不依赖它。

`control_event_set_root` 是 `seal_basis`、控制面 receipt obligation、inclusion list、censorship evidence 与 seal transparency 的共同锚点。`delta[]` 只是本批新增集合；root 承诺的是递归覆盖集。Compaction Seal MAY 显式携带 `covered_event_digests[]`，但 receiver MUST 验证它等于 `delta[]` 与所有 predecessor 覆盖集的并集。

**Compaction 节律是结构性义务（normative）**：因为累计覆盖集由 `predecessor_refs + delta` 递归定义，compaction Seal（携带 `covered_event_digests[]` 或等价可验证全覆盖 manifest 的 Seal）是新 verifier 唯一的有界 bootstrap 物化点。Realm MUST 在 create payload 中声明 `seal_compaction_max_interval_ms`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)，默认 86,400,000 ms；`open_set` 部署 MUST ≤ 24h，`threshold` 部署 MUST ≤ 7d，`single_did` SHOULD ≤ 24h）。notary 超出声明间隔仍未签发 compaction Seal 时，receiver SHOULD 触发治理健康告警；新 verifier 此时只能退回从 genesis 走链或从最近已验证 compaction Seal 接链。该义务由 conformance vector `ck.vector.cba_lattice.seal_compaction_interval_enforced.v1` 固定。

### 6.3 Seal 接受规则

```text
apply_seal(A):
  1. 校验 predecessor_refs 均已知、同 Realm、且不是 fork_quarantine。
  2. 校验 notary_seq 单调性和 notary_signature。
  3. 校验 delta[] canonical 升序去重。
  4. 校验 delta[] 与所有 predecessor covered_set 不相交。
  5. 校验 delta[] 每项都是已知、签名有效、尚未 sealed 的 Control Move digest。
  6. 计算 covered_set(A) = delta(A) union predecessor covered sets。
  7. 校验 control_event_set_root == root(covered_set(A)).
  8. 在 predecessor joined governance state 下批量 verify_control_move(delta[])。
  9. 任一 Control Move 失败则拒绝整个 Seal。
  10. 原子应用 Control Move effects，重算治理 state_root。
  11. state_root 匹配则接受；否则拒绝并生成 seal fault 诊断。
```

Seal 被拒绝时，其 `delta[]` 内 Control Move 不因此有效。节点 MAY 保留这些 Move 作为 pending / diagnostic 输入，但 MUST NOT 让它们推进 query 或授权。

### 6.4 数据面观测承诺

Seal MAY 附带：

```text
KeyView {
  cell_id
  lattice_type
  heads[] / value_digest?
  last_covered_event?
}
```

**观测 root 的计算规则（normative，三个 root 同构）**：

- `data_view_root` = 按 `cell_id` Unicode code point 升序排列的 KeyView 记录的 RFC 6962 Merkle root；leaf 输入为 `H(0x00 || canonical_json(KeyView))`，内部节点为 `H(0x01 || left || right)`，空集合用该 algo 的空树 root。
- `data_event_set_root` = 该 seal 窗口内 notary 观察到的数据面 `event_digest` 集合（canonical 升序）的 RFC 6962 Merkle root。
- `availability_root` = 该 seal 窗口内 notary 接受的 AvailabilityReceipt 的 canonical bytes 摘要集合（canonical 升序）的 RFC 6962 Merkle root。
- 三者的 inclusion proof 一律使用 Merkle audit path，non-membership 一律使用 sorted-neighbor proof——与 §6.2 `control_event_set_root` 的证明形态一致，实现可共用同一套 Merkle 代码与 conformance vector 形状。

轻客户端对单个 data cell 的标准查询凭证是 **KeyViewProof**（wire schema：[`key-view-proof.schema.json`](../../artifacts/schemas/key-view-proof.schema.json)）：`{realm_id, seal_id, data_view_root, key_view, audit_path[]}`，verifier 重算 leaf 并沿 audit path 收敛到该 Seal 签名覆盖的 `data_view_root`。

这些字段是 observational：

- 未进入 `data_view_root` / `data_event_set_root` 的 DataEvent 不因此无效。
- `observed` query grade 只表示某个 seal 见过并承诺过该局部结果；未来未观测的有效并发 DataEvent MAY 改变该 data cell 的 join。
- Receiver MUST NOT 用 observational roots 拒绝有效 DataEvent。

## 7. 问责、审查与 transparency

### 7.1 Signer slot 与 equivocation

每个 notary signer 维护自己的 `notary_seq`。同一 signer 对同一 `(realm_id, notary_seq)` 签出两个 canonical bytes 不同的 Seal，或 `notary_seq=k+1` 不以自身 `notary_seq=k` 为 DAG 祖先，构成 equivocation。

Equivocation evidence 是普通 Control Move，event kind 为 **`ck.notary.fault.equivocation`**（已注册于 event-kind registry；payload schema 见 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) `notary_fault_equivocation_payload`：`{signer_id, seal_a, seal_b}`），写入专用 `ck.component.notary_fault.v1` control cell（`or_set`，bottom=expose）。授权条件是两个满足 slot 规则的冲突签名本身；验签即授权，无需额外 capability，reducer MUST NOT 要求 grant。

接受 fault 记录后：

- receiver MUST 拒绝 fault signer 后续 Seal；
- 冲突 slot 中两个 Seal 及其后继进入 `fork_quarantine`；
- fork resolution 前，普通 joined governance view MUST NOT 纳入 quarantined Seal；
- 仅 fork-resolution compaction Seal 或 genesis recovery path 可恢复推进。

Threshold signer 使用委员会级 slot。若 2k > n，两个 threshold 签名的 quorum 交集可指认至少一个双签成员；否则部署 policy MUST 声明放弃自动指认。该声明是机器可校验项：threshold notary 的 Realm create payload MUST 携带 `notary.forensic_attribution ∈ {quorum_intersection, waived}`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)），且取值与 `2k>n` 的算术关系由 reducer 校验、由 conformance vector `ck.vector.cba_lattice.threshold_forensic_attribution.v1` 固定。

### 7.2 控制面 receipt 与 inclusion obligation

控制面 pending Control Move MUST 在 `receipt_sla_ms` 内得到签名 receipt 或签名 rejection。

到期 receipt 在后续 Seal 中必须三选一：

1. include；
2. signed-reject，附可验证原因；
3. 有限次 defer，附原因与新的到期边界。

无声遗漏构成 censorship evidence：

```text
CensorshipEvidence {
  receipt
  seal_ref
  control_event_set_root_non_membership_proof
  missing_rejection_or_defer_proof
}
```

Censorship evidence 是普通 Control Move，event kind 为 **`ck.notary.fault.censorship`**（payload schema：`notary_fault_censorship_payload`），写入 `ck.component.notary_fault.v1` cell。它**不**自动罢免 notary：reducer 记录审计 fault 并 MUST 触发治理告警。

**问责闭环与 recovery 路径的绑定（normative）**：被告 notary 可能审查针对自己的 fault / censorship evidence。为此：

1. fault evidence Move 持有的 receipt（或经 federation probe 传播的副本）对 **recovery notary**（genesis `recovery_members` / `mixed` profile 的 fallback notary）构成与 inclusion list 等同的收录义务：recovery notary 签发任何 recovery / fork-resolution Seal 时，MUST include、signed-reject 或证明验证失败所有其已知的、处于义务窗口内的 fault evidence Move；
2. `single_did` 下，evidence 经 federation probe / SeenReceipt 渠道流转至 recovery notary；若 Realm 未声明可用 recovery 路径，问责退化为"证据可流转但不可生效"的审计态——这是 `single_did` 的诚实限制，也是 genesis 强制 `recovery_members` 组织分离的理由之一；
3. multi-signer profile 下，任何非 fault 方 signer 都可把 evidence 列入 inclusion list（§7.3），不必等待 recovery 路径。

### 7.3 Inclusion list

Multi-signer profile MAY 支持 FOCIL 式 inclusion list。非 proposer signer 对通过初检的控制面 Move 签发 inclusion list；下一 Seal MUST include、signed-reject 或证明验证失败，否则 receiver MUST 拒绝该 Seal。`single_did` profile 无法提供该机制。

Wire schema：[`inclusion-list.schema.json`](../../artifacts/schemas/inclusion-list.schema.json)（`ck.schema.inclusion_list.v1`）：`{realm_id, signer_id, list_seq, event_digests[], expiry_seal_count, created_at, signature}`。Receiver 校验规则（normative）：

1. `signer_id` 在签发时点是 Realm multi-signer notary profile 的合法非 proposer 成员；
2. `event_digests[]` canonical 升序、去重、每项持有效 receipt 且通过本地 verify；
3. `list_seq` 复用 §7.1 的 per-signer slot 语义——同一 `(realm_id, signer_id, list_seq)` 双签构成 equivocation evidence；
4. 自 list 被观察起的 `expiry_seal_count` 个后续 Seal 内（默认 1），每个列出 digest MUST 被 include、signed-reject 或附 batch pre-state 验证失败证明；任一 digest 三者皆无 → receiver MUST 拒绝该 Seal（`rejected_seal`，reason=`inclusion_list_violation`）；
5. inclusion list 自身不是 Seal，不推进治理状态；它只是问责对象。

该义务由 conformance vector `ck.vector.cba_lattice.inclusion_list_obligation.v1` 固定。

### 7.4 Seal transparency

Seal tuple SHOULD 发布到 append-only transparency log。独立 auditor 验证 append-only、`control_event_set_root` 单调、`completeness_root` 单调和签名有效性，并签发 attestation。客户端接受 `grade=witnessed` 前 MUST 验证 policy 要求的 witness / auditor attestation。

Wire schema：[`seal-transparency.schema.json`](../../artifacts/schemas/seal-transparency.schema.json)（`ck.schema.seal_transparency.v1`）定义两个对象：

- **log entry**：`{log_id, log_index, realm_id, seal_id, control_event_set_root, completeness_root, state_root, prev_entry_digest, logged_at, log_signature}`——`log_index` append-only，`prev_entry_digest` 形成 hash 链。同一 `(log_id, log_index)` 出现两个签名不同的 entry 即构成**可证明的 log fork**：split-view 攻击者要么一致发布、要么留下可出示的分叉证据。
- **auditor attestation**（`#/$defs/auditor_attestation`）：`{log_id, realm_id, from_index, to_index, head_entry_digest, auditor_id, checks{append_only, seal_signatures, set_root_monotonic, completeness_monotonic}, attested_at, signature}`——四项 checks 全部为 true 才可签发;auditor 无法断言任一项时 MUST NOT 出具。

`grade=witnessed` 的判定标准即"该 Seal 被 ≥ policy 要求份数的独立 auditor attestation 的已验证范围覆盖"。

## 8. AvailabilityReceipt

Digest membership 不能证明 bytes 可获取。Cokret v1 独立建模 availability：

```text
AvailabilityReceipt {
  realm_id
  event_id
  bytes_digest
  holder_id
  retention_until
  signature
}
```

规则：

- 控制面 Seal include 一个 Control Move 前，MUST 满足 Realm availability policy。小 Realm 默认要求 notary + 至少一个 witness 持有 bytes；组织 Realm MAY 要求 m-of-n storage witnesses。
- Snapshot / backfill 承诺 MUST 同样满足 availability policy。
- 数据面默认 SHOULD 在 relay 签 SeenReceipt 时同时签 availability 承诺；高对抗部署 MAY 要求更高 storage quorum。
- erasure coding / data availability sampling 不进 v1 core。

## 9. Lattice 与冲突语义

核心 Lattice type 保持封闭：`or_set`、`mv_register`、`cas_register`、`fsm`、`counter`、`ordered_log`。文本 / 列表 CRDT 可作为注册 profile 映射到 data plane cell，但不得改变 core type 的确定性要求。

### 9.1 Plane × Lattice 映射

| Lattice type | Data plane | Control plane |
| --- | --- | --- |
| `or_set` / `ordered_log` | 默认可用 | 撤销集合、审计日志等治理语义可用 |
| `counter` | 仅 issuer-local escrow 消耗可用 | 治理配额 / 审计计数可用 |
| `mv_register` | 默认普通属性冲突载体，暴露 heads，UI 或后续 Event 收敛 | 禁止作为授权根 |
| `cas_register` / `fsm` | 默认不可用；需 §9.4 opt-in | 治理 cell 标配；冲突走 bottom / recovery |

### 9.2 Data plane 冲突

数据面相同 cell 上的有效并发写按该 cell Lattice join：

- 可交换 op 正常 merge；
- 普通属性使用 `mv_register` 暴露多 heads；
- 文本 / 序列类 cell 使用注册 CRDT profile；
- 数据面默认不产生协议级 `⊥`，也不需要 recovery capability。

### 9.3 Counter / escrow 边界

数据面 counter 只允许本地可判定的 issuer-local 消耗：每个 issuer 只能消耗自己切片内的额度，并且消耗 Event 必须沿该 issuer actor chain 串行累计验证。

跨 issuer `transfer` 同时改变两个 issuer 的切片，属于跨 cell / 跨 issuer invariant；默认 MUST 升控制面，或使用 per-object sequencer 线性化。否则两个并发 transfer 可能单笔合法、合并后超支。

### 9.4 非治理强一致对象

看板位置、强单值状态机或其它非治理强一致对象三选一：

1. **默认 `mv_register` + user-pick**：并发结果暴露多 heads，任何有写权限者可再签一个 DataEvent 收敛。
2. **`sealed=true` 升控制面**：继承 Seal finality、`⊥` 和 recovery。
3. **per-object sequencer**：schema 指定某 DID 线性化该 cell 的 DataEvent；sequencer 失效时 MUST 退回 `mv_register` 或升控制面。

## 10. 查询语义

任何 query / projection 响应 MUST 携带：

```text
basis {
  seal_ref
  key_view_ref?
  grade
}
```

| grade | 语义 |
| --- | --- |
| `local` | 本地已知 data DAG 或 control cache 的结果，无外部承诺。 |
| `seen` | 相关 DataEvent 持有 SeenReceipt，但未被 seal 观测承诺。 |
| `observed` | 数据面结果进入某个 seal 的 `data_view_root` / `data_event_set_root`；这是观测承诺，不是 finality。 |
| `sealed` | Control Move 被已接受 Seal 覆盖并进入治理 `state_root`；仅控制面使用。 |
| `witnessed` | 对应 seal 另有 policy 要求的 witness / auditor attestation。 |
| `forked` | 查询依赖的控制面分支处于 `fork_quarantine`。 |
| `stale` | `seal_ref` 超 freshness window、seal 超期或撤销缺口超限。 |

轻客户端验证 query 结果时 MUST 验：

1. 从自己上一个 accepted Seal 到响应 Seal 的 extension path；
2. policy 要求的 witness / auditor signature；
3. 自己关心的 control cell state proof 或 data KeyViewProof（[`key-view-proof.schema.json`](../../artifacts/schemas/key-view-proof.schema.json)，验证规则见 §6.4）；
4. 自己持有 receipt 的 inclusion / rejection / defer 证明。

轻客户端不验证全局 state transition。

## 11. E2EE 与 MLS

MLS governance binding 是 `seal_ref` 模式的特例：

- MLS epoch、key schedule、covered_seals_cell 属于 control plane。
- E2EE message 属于 data plane，必须携带 `seal_ref`，并证明其消息 epoch / key schedule 在该 seal 下有效。
- MLS commit 是 Control Move，写 MLS control cells，并由 Seal 裁决。

E2EE message 不等待数据面 seal；它只等待其 `seal_ref` 对应的 MLS / membership / capability 控制状态可验证。

## 12. Snapshot、GC 与恢复

1. 未被任何控制面 Seal 覆盖集覆盖、且未被 active pending Control Move / recovery Move 引用的 Control Move MAY GC。
2. DataEvent 的 GC 由 data DAG sync、SeenReceipt、AvailabilityReceipt、retention policy 与 application retention 决定；GC 不得破坏仍需验证的 actor chain、causal refs 或 availability commitment。
3. 已 seal 的 Control Move MUST 保留审计 stub；payload 可按 retention / erasure 规则裁剪。
4. Snapshot 是某个 accepted Seal 的 materialized proof，不是独立真相源。没有可验证 Seal / inclusion proof 的 snapshot MUST NOT 用于授权 allow。

## 13. 失败状态

| 状态 | 语义 |
| --- | --- |
| `data_local` | DataEvent 通过验签、授权与 `seal_ref` 验证，进入本地 data DAG。 |
| `data_observed` | DataEvent 或其 cell join 被某个 Seal observational root 覆盖。 |
| `control_pending` | Control Move 已通过本地初检，等待 Seal。 |
| `control_sealed` | Control Move 被已接受 Seal 覆盖集覆盖并进入治理 `state_root`。 |
| `failed_precondition` | Control Move precondition 不满足，或 DataEvent `seal_ref` / auth_context 校验失败。 |
| `failed_plane` | Event 跨 plane 写入或 data schema 使用禁止的硬性 invariant。 |
| `failed_bottom` | Control Move 依赖 `bottom=reject` 的 control cell。 |
| `rejected_seal` | Seal 签名、slot、delta、root、batch 或 `state_root` 校验失败。 |
| `fork_quarantine` | 控制面分叉已被证明，相关 Seal 不得进入普通 joined view。 |
| `stale_seal_ref` | DataEvent 的 `seal_ref` 相对已知撤销 seal 超出 freshness window。 |

实现 MAY 在 API 层继续使用兼容错误码，但必须映射到本表语义。

## 14. 规模上限

Move / DataEvent / Seal / Lattice 必须受 [`scalability-constraints.md`](../conformance/scalability-constraints.md) 约束：

- 单个 Event canonical size 默认不超过 1 MiB。
- 单个 Event 的 `preconditions + effects` 默认不超过 256。
- 单个 Seal 新增 Control Move 默认不超过 1,000。
- Seal `delta[]` 是本批新增控制面 digest；累计覆盖集由 predecessor 递归定义。实现 MAY 在达到 deployment 上限前生成 compaction Seal，但 compaction MUST 保留 `control_event_set_root`、`state_root`、notary signature chain 与 receipt obligation 证明。
- 单次 Lattice join 超预算时，节点 MUST 返回可恢复错误或要求更窄 KeyViewProof；MUST NOT 用本地接收顺序替代。

## 15. 规范性引用

- Event Envelope：[../models/event-and-patch.md](../models/event-and-patch.md)。
- Capability 与 freshness：[capabilities.md](./capabilities.md)。
- Query：[../conformance/query-schema.md](../conformance/query-schema.md)。
- Federation 与 transparency：[../sync/federation.md](../sync/federation.md)。
- Snapshot：[../conformance/snapshot-schema.md](../conformance/snapshot-schema.md)。
- Wire schemas：`artifacts/schemas/event-envelope.schema.json`、`artifacts/schemas/seal.schema.json`、`artifacts/schemas/query.schema.json`、`artifacts/schemas/availability-receipt.schema.json`。
