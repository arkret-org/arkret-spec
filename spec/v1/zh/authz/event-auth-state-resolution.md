---
title: Event Auth、CBA 双平面与状态收敛
status: candidate
normative: true
stability: v1
updated: 2026-07-02
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
| Event Batch Receipt | issuer（relay / notary / witness / Principal Server）对其选择承诺的 Event 集合签发的 receipt object（`ck.schema.event_batch_receipt.v1`）。数据面单事件"已看见"确认是其 `events[]` 单元素用法（原 SeenReceipt，已合并，见 §4.4）。它不是准入证明，不进入 state。 |
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

**`distance` 度量与窗口单位（normative）**：`revocation_freshness_window` 的权威字段是 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的 `revocation_freshness_window_ms`（integer，毫秒，`default 86400000`（24h），`minimum 0`）。`distance(seal_ref, R)` MUST 按**控制面 Seal DAG 上 notary 签署的提交时间差**度量：取撤销 Seal `R` 与 `seal_ref` 各自签名 transcript 内 notary 提交时间（沿 Seal DAG，`R` 是 `seal_ref` 后继，见 §6.3），求二者毫秒差。该度量只用进入 Seal 签名 transcript 的 notary 提交时间，**不**用 DataEvent 自报的 `created_at` 或本地接收时间——时间来自被签名的 Seal 拓扑，可验证、跨 receiver 确定复现。`distance > revocation_freshness_window_ms` 即超窗。

该规则不判断事件真实签发时间，也不依赖本地接收时间。producer 在本地已知撤销 seal 后仍用旧 `seal_ref` 签 DataEvent，协议不把它单独定义为可证明 fault；但所有已观察到 `R` 且窗口超限的 receiver MUST 拒绝或隐藏这些事件（`stale_seal_ref`，§13）。

**并发分支撤销（normative，`open_set`）**：上面 step 3 的"尚未观察到覆盖该 issuer/capability 的**后续**撤销 seal 即接受"与 step 4 的后继距离判定，**前提都是撤销 Seal `R` 与 `seal_ref` 在 Seal DAG 上构成后继关系**。`single_did` / `threshold` notary profile 要求 Seal 单链唯一（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `notary_profile`），后继关系恒成立。但 `open_set` profile **显式允许多个并发 Seal leaf**，此时 `R` 与 `seal_ref` 可能**并发**（互不可达，既非后继也非前驱）。并发时 receiver **MUST NOT** 因"`R` 不是 `seal_ref` 的后继 / 后续"就套用 step 3 接受或跳过 step 4——那会让一个其授权 capability 已在并发分支被撤销的 DataEvent 被全体 receiver 接受并 join，撤销在并发窗口内对数据面完全失效（fail-open），并与 merge 后控制面状态矛盾。receiver MUST 改按其**已 join 的控制面视图**重判：取 receiver 已观察的全部 Seal leaf 的 union covered set，按 §6.3 在 predecessor joined governance state 上对该 capability 授权 cell 做 per-cell Lattice join（§9）；若 joined view 中该 capability 已被 `R` 撤销、或承载其授权判定的 cell 进入 `⊥`，receiver MUST 对依赖它的 DataEvent fail closed（`stale_seal_ref`）。并发分支**不计算 `distance`、不享受新鲜度窗口宽限**（等效 window=0），直接按 joined view 的撤销结果处置；`risk_tier=high` capability 在并发分支同样 MUST fail closed。这保证撤销在 `open_set` 并发窗口内对数据面同样生效，且因 joined view 对所有已 join 同一 leaf 集的 receiver 确定相同而跨 receiver 收敛到一致拒绝。轻客户端若无法独立验证 multi-leaf union basis（§4 多 leaf basis 规则），遇到并发撤销 MUST 保守 fail closed 或 hold pending 直到取得可验证的 joined view。该义务由 conformance vector `ck.vector.cba_lattice.open_set_concurrent_revocation_fail_closed.v1` 固定。

**高风险 capability 的撤销即时性（normative）**：对 `risk_tier=high` capability（`risk_tier` 的权威源是 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json)，散文镜像见 [`capabilities.md`](./capabilities.md)）授权的 DataEvent，撤销**不享受**新鲜度窗口宽限：receiver 一旦观察到覆盖该 capability 的撤销 Seal `R`，MUST 对 `seal_ref` 早于 `R` 的此类 DataEvent fail closed（等效 `revocation_freshness_window_ms = 0`），无论 `distance`；承载此类 capability 授权判定的 cell family SHOULD 声明 `sealed=true` 升控制面。中低风险 DataEvent 仍按上面的窗口判定。此外，producer 在本地已观察到 `R` 后仍用早于 `R` 的 `seal_ref` 继续签发 DataEvent，虽不构成可证明 fault，receiver / audit **SHOULD** 将其记录为 audit-loggable 可疑信号（stale-after-observed），供事后问责——这与"不可证明 fault"不矛盾：不自动惩罚，但留痕。需要强撤销即时性的 Realm SHOULD 缩短 `revocation_freshness_window_ms`，或将相关 cell family 声明为 `sealed=true`。

Grant 晚于 producer 最新 seal 签发时，producer MUST 等下一个控制面 seal 后再签 data write。治理低频，等待 seal 是可接受成本。

### 4.4 数据面传播与 Event Batch Receipt

数据面传播使用 gossip、anti-entropy 或 RBSR 类集合调和。同步摘要可以作为 federation probe 的 data frontier。

Relay / notary / witness 收到 DataEvent 时 SHOULD 返回一个 Event Batch Receipt（receipt object，schema [`event-batch-receipt.schema.json`](../../artifacts/schemas/event-batch-receipt.schema.json)，schema id `ck.schema.event_batch_receipt.v1`，字段与概念分层见 [`../models/event-and-patch.md` §5](../models/event-and-patch.md)）。单事件确认即 `events[]` 只含该 `event_digest` 的单元素 receipt：`scope` 携带 `realm_id`，`created_at` 为 issuer 看见该事件的时间，`frontier` 为签发时 issuer 前沿。

> **合并说明（normative）**：v1 早期草案曾把这一用途单列为 "SeenReceipt"（`{realm_id, event_digest, received_at, receipt_seq, expires_at, issuer, signature}`）。它与 Event Batch Receipt 语义同层——issuer 签名的、非 canonical、只保 set integrity 的 hint——且从未注册 schema，故收敛为 Event Batch Receipt 的单元素用法，协议中不再存在独立的 SeenReceipt 对象。旧结构的 `receipt_seq` 与 `expires_at` 一并取消：全规范无消费者——issuer 侧漏发/扣发检测由 [`../sync/operations-sync.md` §6.4](../sync/operations-sync.md) range-completeness attestation 与 frontier probe 承担，equivocation 检测归 Seal 的 `notary_seq`（§7.1）；receipt 是 best-effort hint 且"已看见"是不可撤销的事实陈述，过期语义没有可执行含义，receipt 的保留期属部署本地 retention 决策。

Event Batch Receipt 只证明"issuer 看见并承诺所列事件集合的 integrity"，不证明事件有效、不提议排序、不进入控制面 state、不提供范围 completeness。部署 MAY 不签发数据面 receipt；关闭后同账号 RYW（`grade=seen`）与数据面审查诊断能力降低。

## 5. Control Move

Control Move 是写 control plane cell 的 Event。它仍使用 Event Envelope，但 MUST 携带 `seal_basis`，MUST NOT 携带 `seal_ref`。唯一例外是 [`ck.realm.create`](../models/realm-and-space.md#25-ckrealmcreate-reducer-bootstrapnormative) 所属 Realm bootstrap event set：Realm 创建前不存在可引用的 accepted Seal，因此 create 及同一 submit batch 内由同一 actor 写入同一 Realm 初始配置的 bootstrap follow-up event MAY 携带 bootstrap `effects[]` / `preconditions[]` 而不携带 `seal_basis`；此例外不得推广到 batch 外或非 bootstrap Control Move。

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
2. `leaves[]` MUST 只引用 accepted Seal。单 leaf basis 是轻 producer 的默认形态。account client 铸造单 leaf basis 的注册来源是 `ck.self.events.query.frontier` 的 `realm_id` 形响应（Realm Seal view `{realm_id, seal_id, control_event_set_root, state_root, hlc?}`，见 `../sync/service-http-binding.md`）；该来源不可用时 MUST fail closed，不得伪造 basis。
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

`completeness_root` 是控制面 per-actor 区间承诺，MUST 使用 §6.2.2 的统一 Seal Merkle 组合规则。leaf 集合为当前 `covered_set(S)` 中每个 control-plane actor 的连续 actor_seq 覆盖区间；每个 leaf 的 `leaf_data = canonical_json({ "actor_id": <did>, "from_seq": <integer>, "to_seq": <integer>, "event_digests": [<digest>...] })` 的 UTF-8 字节，其中 `event_digests[]` 是该 actor 在 `[from_seq,to_seq]` 内按 `actor_seq ASC, event_digest ASC` 排列的控制面 Event digest。leaf 按 `(actor_id, from_seq, to_seq)` canonical code point / integer 顺序排列。对同一 actor，相邻 Seal 的 interval set MUST 单调：已承诺区间不得收缩、不得产生未解释的 gap，`to_seq` 只能非降；compaction Seal MAY 合并相邻连续区间，但合并后覆盖的 digest 集合必须逐字节等价。空控制面覆盖集的 `completeness_root` 为 §6.2.2 空树 root。Auditor 的 `completeness_monotonic` 即按该 interval 偏序验证每个 actor 的覆盖区间非缩、无回退、无重写。

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

Seal MUST 签 `control_event_set_root`。默认 root 是对 canonical 升序 `covered_set(S)` 的 RFC 6962 Merkle root，**精确字节规则按 §6.2.2 的统一 Seal Merkle 组合规则**（leaf = `H(0x00 || event_digest_raw_bytes)`，内部节点 = `H(0x01 || left || right)`，`H` 为该 Realm 声明的 hash suite，v1 default `sha256`）：

- leaf 顺序：`covered_set(S)` 内每个控制面 `event_digest` 按其 `<suite>:<hex>` wire 值的 Unicode code point 升序排列；进入树前 MUST 去掉 `sha256:` 前缀并解码为 raw bytes 作为 `H(0x00 || …)` 的输入（§6.2.2）；
- inclusion proof 使用 Merkle audit path；
- non-membership proof 使用 sorted-neighbor proof；
- 空集合 root 使用 §6.2.2 定义的 RFC 6962 空树 root（`H` over the empty byte string）；
- 更复杂的 radix trie / zkVM state proof MAY 在后续规范中作为规模触发机制定义，但 v1 core 不依赖它。

`control_event_set_root` 是 `seal_basis`、控制面 receipt obligation、inclusion list、censorship evidence 与 seal transparency 的共同锚点。`delta[]` 只是本批新增集合；root 承诺的是递归覆盖集。Compaction Seal MAY 显式携带 `covered_event_digests[]`，但 receiver MUST 验证它等于 `delta[]` 与所有 predecessor 覆盖集的并集。

**Compaction 节律是结构性义务（normative）**：因为累计覆盖集由 `predecessor_refs + delta` 递归定义，compaction Seal（携带 `covered_event_digests[]` 或等价可验证全覆盖 manifest 的 Seal）是新 verifier 唯一的有界 bootstrap 物化点。Realm MUST 在 create payload 中声明 `seal_compaction_max_interval_ms`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)，默认 86,400,000 ms；`open_set` 部署 MUST ≤ 24h，`threshold` 部署 MUST ≤ 7d，`single_did` SHOULD ≤ 24h）。notary 超出声明间隔仍未签发 compaction Seal 时，receiver SHOULD 触发治理健康告警；新 verifier 此时只能退回从 genesis 走链或从最近已验证 compaction Seal 接链。该义务由 conformance vector `ck.vector.cba_lattice.seal_compaction_interval_enforced.v1` 固定。

### 6.2.1 治理 `state_root` 的 Merkle 计算规则（normative）

Seal 顶层的治理 `state_root`（§6 Seal schema、§4 Control Move `seal_basis.state_root`、§6.3 step 10 "重算治理 state_root"、§7.1 log entry 中的同名字段）是对**当前 joined 治理状态全部 control cell** 的 authenticated Merkle root。它与 §6.2 `control_event_set_root`、§6.4 三个观测 root 同属一个 Seal 的承诺族，**MUST 使用 §6.2.2 的统一 Seal Merkle 组合规则**（带 `0x00` / `0x01` 域分隔），使一个 Realm 实现可对全部 Seal 级 root 共用同一套 Merkle 代码与 conformance vector 形状，并使 governance root 获得与观测 root 同等的 leaf/node 第二原像域分隔。

leaf 集合与顺序：

- **成员**：`state_root` 覆盖**当前 joined 治理视图 `J(L)`（§6.3.1）下每一个 non-`⊥` 物化值的 control cell**——即至少被 `covered(L)` 中某个 Control Move effect 命中、且按其 lattice join 后得到确定值的 control cell。data plane cell 不进入 `state_root`（数据面承诺走 §6.4 `data_view_root`）。
- **每个 cell 的 leaf 输入**：`leaf_preimage = canonical_json({ "cell": "<cell_wire_id>", "state": <state_object> })`，其中
  - `<cell_wire_id>` 是该 cell 的 canonical tuple 引用 `ck:cell:<component>:<subject>`（[`conformance/encoding.md` §4](../conformance/encoding.md)）；
  - `<state_object>` 在 cell 物化为具体值时为 `{ "value": <lattice_value> }`。`⊥`（`failed_bottom`，§9.1.1）cell **一律不进入** `state_root` leaf 集；它通过失败状态、冲突 heads 与 §9.5 recovery witness 暴露，不作为治理 root 成员编码。
  - `canonical_json` 按 [`conformance/encoding.md` §2](../conformance/encoding.md)（RFC 8785 JCS 同口径）。
- **leaf hash**：`leaf = H(0x00 || leaf_preimage_utf8_bytes)`（§6.2.2；先取 canonical JSON 的 UTF-8 字节，再前缀 `0x00`）。
- **leaf 顺序**：按 `<cell_wire_id>` 的 Unicode code point 升序排列；树构造本身不再排序（§6.2.2）。

inclusion proof 使用 Merkle audit path，non-membership 使用 sorted-neighbor proof，与 §6.2 / §6.4 同形。空治理视图（无任何 non-`⊥` control cell）的 `state_root` 为 §6.2.2 的 RFC 6962 空树 root。`apply_seal`（§6.3 step 10/11）重算的 `state_root` MUST 按本规则计算并与 Seal 声明值逐字节比对；不匹配 MUST 拒绝（`rejected_seal`）。

### 6.2.2 Seal Merkle 组合规则（RFC 6962，normative）

本节定义 §6.2 `control_event_set_root`、§6.2.1 `state_root` 与 §6.4 三个观测 root **共用**的 byte-level Merkle 组合规则，使一个实现可共用一套 Merkle 代码。`H` 取该 Realm 声明的 hash suite（v1 default-MUST `sha256`，见 [`conformance/encoding.md` §3.1](../conformance/encoding.md)）；wire 输出形态为 `<suite>:<lowercase_hex>`。

- **leaf**：`leaf = H(0x00 || leaf_data)`。各 root 的 `leaf_data` 由其领域规则给出：`state_root` 为 §6.2.1 的 `leaf_preimage` UTF-8 字节；`data_view_root` 为 `canonical_json(KeyView)` UTF-8 字节（§6.4）；`control_event_set_root` / `data_event_set_root` / `availability_root` 为对应 `<suite>:<hex>` digest 去前缀解码后的 raw bytes（§6.2 / §6.4）。
- **内部节点**：`node = H(0x01 || left || right)`，`left` / `right` 为左右子节点的 raw hash 输出字节。
- **leaf 顺序**：树构造本身不排序；各领域规则先声明 leaf 顺序（`state_root` / `data_view_root` 按 cell_id code point 升序；`control_event_set_root` / `data_event_set_root` 按 digest wire 值 canonical 升序；`availability_root` 按 receipt digest canonical 升序）。
- **奇数层**：某一层节点数为奇数时，尾节点**原样提升**到上一层，**MUST NOT 复制**（RFC 6962：在不超过当前节点数的最大 2 的幂处分割，右子树可较小）。
- **单 leaf 树**：root 等于该单 leaf 的 `H(0x00 || leaf_data)`（**注意带 `0x00` 前缀**，不是裸 `leaf_data` 的 hash）。
- **空集合**：root 为 `H` over the empty byte string；`sha256` 下即 `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（与 RFC 6962 §2.1 `MTH({}) = SHA-256()` 一致）。

> **与 snapshot Merkle 的区分（normative）**：本组合规则（带 `0x00` / `0x01` 域分隔、单 leaf 带前缀）适用于 **Seal 级 root**；[`conformance/encoding.md` §3.3.1](../conformance/encoding.md) 的 snapshot / event-set Merkle 规则（无前缀、单 leaf 等于裸 digest）适用于 **snapshot `state_digest` 与 event-set commitment**。二者是两个独立的 Merkle 族，实现 MUST NOT 互换：Seal root 用本节规则，snapshot root 用 encoding.md §3.3.1 规则。

### 6.3 Seal 接受规则

```text
apply_seal(A):
  1. 校验 predecessor_refs 均已知、同 Realm、且不是 fork_quarantine。
  2. 校验 notary_seq 单调性和 notary_signature。
  3. 校验 delta[] canonical 升序去重。
  4. 校验 delta[] 与所有 predecessor covered_set 不相交。
  5. 校验 delta[] 每项都是已知、签名有效、且未被本 Seal predecessor closure 覆盖的 Control Move digest
     （"尚未 sealed" 的判定范围见下方并发 leaf 规则）。
  6. 计算 covered_set(A) = delta(A) union predecessor covered sets。
  7. 校验 control_event_set_root == root(covered_set(A)).
  8. 在 predecessor joined governance state 下批量 verify_control_move(delta[])。
  9. 任一 Control Move 失败则拒绝整个 Seal。
  10. 原子应用 Control Move effects，重算治理 state_root。
  11. state_root 匹配则接受；否则拒绝并生成 seal fault 诊断。
```

Seal 被拒绝时，其 `delta[]` 内 Control Move 不因此有效。节点 MAY 保留这些 Move 作为 pending / diagnostic 输入，但 MUST NOT 让它们推进 query 或授权。

**并发 leaf 覆盖同一 pending Control Move（normative）**：步骤 5 中 "尚未 sealed" 的判定范围**只**是本 Seal 的 predecessor closure，即步骤 6 递归并集所得的 predecessor `covered_set`——等价于步骤 4 的不相交校验；receiver **MUST NOT** 以自身全局已接受 Seal 集合作为判定范围。特别地，`open_set` profile 下某 Control Move 已被另一个**并发**（不在本 Seal predecessor closure 内的）已接受 Seal leaf 覆盖时，receiver **MUST NOT** 因此拒绝本 Seal；否则接受结果将随 leaf 到达顺序变化，产生永久分叉，违反 §6.3.1 "`J(L)` 是 `L` 的纯函数、与到达顺序无关" 的收敛保证。同一 Control Move 被多个并发 leaf 覆盖是合法状态：`covered(L)` 按 Control Move digest 内容寻址取并集，重复覆盖自然去重，join 结果不受影响。

#### 6.3.1 Deterministic joined control view（multi-leaf join，normative）

`single_did` / `threshold` notary profile 下 Seal 单链唯一，任一时刻只有一个 control head，"当前治理状态"无歧义。`open_set` profile 允许多个并发 Seal leaf（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `notary_profile`），[`../sync/federation.md` §2.4](../sync/federation.md) 与 realm.schema 据此引用的 **"deterministic joined control views"** 即指本节定义的 join；它是 §4.3 并发分支撤销重判、§6.4 query grade 与跨 receiver 收敛的共同基准:

给定 receiver 已观察、已 `apply_seal` 接受、且**非** `fork_quarantine` 的全部 Seal leaf 集合 `L = {S_1, …, S_n}`，joined control view `J(L)` 按以下确定性步骤计算，对任意观察到相同 `L` 的 receiver 结果唯一:

1. **覆盖集并集**:`covered(L) = ⋃_i covered_set(S_i)`（§6.2 递归覆盖集的并集）。因 `covered_set` 仅取并集、Control Move digest 内容寻址，`covered(L)` 与 leaf 到达顺序无关。
2. **Move 应用偏序**:`covered(L)` 内的 Control Move 按其 Seal DAG 因果序构成偏序；线性（有因果先后）的 Move 按因果序应用。
3. **并发 Move 的确定性定序**:对偏序中**互不可达**（并发）的 Control Move，按 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的统一 canonical 全序（`event_digest` bytewise 最大优先的全序展开）线性化后应用——保证带 `preconditions[]` 的并发 Move 在所有 receiver 上以同一顺序求值。
4. **per-cell Lattice join**:每个 control cell 按其声明的 lattice（§9）合并 `covered(L)` 中所有命中该 cell 的 Move 效果；`cas_register` / `fsm` 等强一致 cell 上的并发互斥写按 §9.1.1 进入 `⊥`（`bottom=reject` 则该 cell 物化为 `failed_bottom`，依赖它的后续 Move fail closed，按 §9.5 conflict-recovery 解析）。
5. **结果**:`J(L)` 是所有 control cell 的 join 结果集合；它就是 receiver 在 step 8 `verify_control_move` 与所有授权判定（capability / membership / policy）所用的 "predecessor joined governance state"。

`J(L)` 是 `L` 的纯函数（不依赖到达顺序、本地时钟或接收方身份），因此观察到相同 leaf 集的 receiver 得到逐 cell 相同的治理状态；leaf 集不同的 receiver 在缺失 leaf 补齐后收敛到同一 `J`。compaction Seal（§6.2）把 `covered(L)` 物化为有界 bootstrap 点，使新 verifier 无需重放全链即可重建 `J`。

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

**观测 root 的计算规则（normative，三个 root 同构）**——三者均按 §6.2.2 的统一 Seal Merkle 组合规则（`leaf = H(0x00 || leaf_data)`、`node = H(0x01 || left || right)`、单 leaf 带前缀、空集合用 RFC 6962 空树 root）计算，仅 `leaf_data` 与 leaf 顺序按各自领域规则不同：

- `data_view_root` = 按 `cell_id` Unicode code point 升序排列的 KeyView 记录的 root；每个 leaf 的 `leaf_data` 为 `canonical_json(KeyView)` 的 UTF-8 字节。
- `data_event_set_root` = 该 seal 窗口内 notary 观察到的数据面 `event_digest` 集合（按 wire 值 canonical 升序）的 root；每个 leaf 的 `leaf_data` 为对应 digest 去 `sha256:` 前缀解码后的 raw bytes。
- `availability_root` = 该 seal 窗口内 notary 接受的 AvailabilityReceipt 的 canonical bytes 摘要集合（canonical 升序）的 root；leaf_data 同上为 raw digest bytes。
- 三者的 inclusion proof 一律使用 Merkle audit path，non-membership 一律使用 sorted-neighbor proof——与 §6.2 `control_event_set_root`、§6.2.1 `state_root` 的证明形态一致，实现共用 §6.2.2 同一套 Merkle 代码与 conformance vector 形状。

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

**以 quarantined Seal 作 `seal_ref` 锚点的 DataEvent（normative）**：当一条 DataEvent 的 `seal_ref` 指向已进入 `fork_quarantine` 的 Seal 时，receiver MUST NOT 用该 quarantined seal 的授权状态接受它进入 joined view，也 MUST NOT 直接按 `stale_seal_ref` 永久拒绝（quarantine 是控制面分叉、未必表示该 DataEvent 的授权基准非法）。receiver MUST 把它降级保持 **observed-only**（§13 `data_observed`，不参与 join、不投影为生效内容），并 hold pending 直到该 slot 的 fork resolution 产生胜出分支：
  - 若 `seal_ref` 的 Seal 属**胜出分支**（resolution 后不再 quarantined），receiver MUST 用胜出分支下的授权状态按 §4.2 / §4.3 **重判**该 DataEvent，通过则正常接受；
  - 若 `seal_ref` 的 Seal 属**落败分支**（resolution 后被弃），receiver MUST 按 `stale_seal_ref` 拒绝或隐藏该 DataEvent，producer 需以胜出分支的新 `seal_ref` 重新签发。

  该处理与 §4.3 撤销新鲜度判定正交（前者针对控制面分叉，后者针对单链撤销），与 [`../sync/operations-sync.md`](../sync/operations-sync.md) 的 observed-only / backfill 保持语义（observed-only 的 DataEvent 不进 canonical join），不引入新状态。

Threshold signer 使用委员会级 slot。若 2k > n，两个 threshold 签名的 quorum 交集可指认至少一个双签成员；否则部署 policy MUST 声明放弃自动指认。该声明是机器可校验项：threshold notary 的 Realm create payload MUST 携带 `notary.forensic_attribution ∈ {quorum_intersection, waived}`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)），且取值与 `2k>n` 的算术关系由 reducer 校验、由 conformance vector `ck.vector.cba_lattice.threshold_forensic_attribution.v1` 固定。

### 7.2 控制面 receipt 与 inclusion obligation

控制面 pending Control Move MUST 在 `receipt_sla_ms` 内得到签名 receipt 或签名 rejection。`receipt_sla_ms` 的权威字段是 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的 `receipt_sla_ms`（integer，毫秒，`default 86400000`（24h），`minimum 0`），与 `seal_compaction_max_interval_ms`（§6.2）同量级；其 wire 上限登记于 [`scalability-constraints.md`](../conformance/scalability-constraints.md) §4。SLA 计时以 notary 签署的提交时间为准（与 §4.3 `distance` 同源），不用本地接收时间。

到期 receipt 在后续 Seal 中必须三选一：

1. include；
2. signed-reject，附可验证原因；
3. **有限次 defer**，附原因与新的到期边界；同一 pending Control Move 的累计 defer 次数 MUST NOT 超过 `max_receipt_defers`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)，integer，`default 3`，`minimum 0`，上限登记于 [`scalability-constraints.md`](../conformance/scalability-constraints.md) §4）；超过该上限仍未 include / signed-reject 即等同无声遗漏，构成下面的 censorship evidence。

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
2. `single_did` 下，evidence 经 federation probe / Event Batch Receipt 渠道流转至 recovery notary；若 Realm 未声明可用 recovery 路径，问责退化为"证据可流转但不可生效"的审计态——这是 `single_did` 的诚实限制，也是 genesis 强制 `recovery_members` 组织分离的理由之一；
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
- **auditor attestation**（`#/$defs/auditor_attestation`）：`{log_id, realm_id, from_index, to_index, head_entry_digest, auditor_id, checks{append_only, seal_signatures, set_root_monotonic, completeness_monotonic}, attested_at, signature}`——四项 checks 全部为 true 才可签发；auditor 无法断言任一项时 MUST NOT 出具。

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
- 数据面默认 SHOULD 在 relay 签 Event Batch Receipt（§4.4）时同时签 availability 承诺；高对抗部署 MAY 要求更高 storage quorum。
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

#### 9.1.1 `bottom` policy（normative）

控制面 cell 在 join 无法收敛到单一合法值时进入 `⊥`（bottom）。`⊥` 的暴露语义由 cell family 的 **`bottom` policy** 决定，取值为封闭枚举 `bottom ∈ {expose, reject}`：

| `bottom` | 语义 |
| --- | --- |
| `expose` | join 产生 `⊥` 时把冲突 heads 暴露给读路径与后续 Move（不直接 fail-closed 写入）；典型用于 `or_set` 形态的并存/审计语义（如 §7.1 `(or_set, bottom=expose)` notary fault cell、moderation_state cell）。 |
| `reject` | join 产生 `⊥` 时，所有依赖该 cell 的 Control Move precondition、DataEvent 授权判定与读路径 MUST fail closed，返回 `failed_bottom`（`reason=cell_in_bottom_state`，见 §13）；典型用于 `cas_register` / `fsm` 等强单值治理 cell。 |

声明来源与默认值：

- `bottom` policy 是 **cell family 属性**，由 Realm schema 的 cell family 声明（与 `lattice` 同处声明，权威载体为 [`registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 对应 cell 的 `bottom` 字段）。
- 每个 core lattice type 的默认 `bottom`：`cas_register` / `fsm` 默认 `reject`（强单值治理 cell，冲突即 fail-closed）；`or_set` / `ordered_log` / `counter` 的 join 在数学上永不产生 `⊥`，未显式定义领域冲突语义时其 `bottom` 字段对收敛 **inert**（例如 capability grant 与 consent grant 这类普通 observed-remove 集合，即使 registry 为占位登记 `reject`，reducer 也 MUST NOT 据其产生 reject 语义；见 [`capabilities.md` §12.1](./capabilities.md) 与 [`../identity/consent-model.md`](../identity/consent-model.md)）。若某个 or_set cell family 显式登记 `bottom=expose` 并由领域文档定义 exposed multi-head 处理（例如 `ck.component.moderation_state.v1`），实现 MUST 执行该领域规则，不得用普通 or_set 的 inert 默认覆盖它。`mv_register` 不产生 `⊥`（暴露多 heads 而非 bottom），无 `bottom` 语义。
- cell family 未显式声明 `bottom` 时，reducer MUST 按上述 per-lattice-type 默认处理；MUST NOT 把未声明当作 `expose` 放宽强单值治理 cell。

> `bottom=reject` cell 进入 `⊥` 后的恢复路径由 §9.5 control cell `⊥` recovery 定义（conflict-recovery Move）。

### 9.2 Data plane 冲突

数据面相同 cell 上的有效并发写按该 cell Lattice join：

- 可交换 op 正常 merge；
- 普通属性使用 `mv_register` 暴露多 heads；
- 文本 / 序列类 cell 使用注册 CRDT profile；
- 数据面默认不产生协议级 `⊥`，也不需要 recovery capability。

### 9.3 Counter / escrow 边界

数据面 counter 只允许本地可判定的 issuer-local 消耗：每个 issuer 只能消耗自己切片内的额度，并且消耗 Event 必须沿该 issuer actor chain 串行累计验证。

同一 issuer 在同一 `(actor_id, actor_seq, prev_frontier_digest)` sibling 桶内产生多个 counter / escrow 消耗 Event 时，receiver MUST 把该桶视为 issuer-local escrow equivocation，而不是在 sibling 间选择 winner 或把消耗简单求和。该桶中命中同一 issuer 切片的全部 counter 消耗 effects MUST 对该切片 fail closed：在 actor chain repair / fork-resolution 产生 canonical 单分支前，这些消耗不得进入 counter cell value、不得减少可用余额、也不得被后续消耗作为已花费前缀跳过。其它不依赖该切片的 cell 可按其自身 lattice 规则继续 join。若某领域需要 sibling fork 下仍保持 counter 强一致，必须把该 counter cell 声明为 `sealed=true` 升控制面或使用 §9.4 per-object sequencer。

跨 issuer `transfer` 同时改变两个 issuer 的切片，属于跨 cell / 跨 issuer invariant；默认 MUST 升控制面，或使用 per-object sequencer 线性化。否则两个并发 transfer 可能单笔合法、合并后超支。

### 9.3.1 core lattice join 与 `head_eq` predicate（normative）

本节是 Control Move `preconditions[]` 中 `Predicate` 与 core lattice join 规则的散文权威；schema 只给字段形状，不能替代本节的求值语义。

- **`head_eq`**：谓词形态为 `{kind:"head_eq", cell:"ck:cell:...", value:<json>}`。Reducer MUST 在该 Move 的 `seal_basis` 治理 view 下读取目标 cell 的 settled value，并按 canonical JSON whole-value compare 与 `value` 比较；二者 bit-exact 相等时通过。cell 缺失时 settled value 为 `null`，因此省略业务字段与显式缺省不得被当作匹配。若目标 cell 在该 basis 下为 `⊥`，`head_eq` MUST fail closed（failure status `failed_bottom`，`reason=cell_in_bottom_state`，见 §13）。
- **`cas_register`**：set effect 在目标 cell 的 settled 值为非初始态时，Control Move MUST 携带命中本 cell 的 `head_eq` precondition；DataEvent 若声明使用 CAS 语义，MUST 通过 causal refs 与领域 lattice 规则表达同等约束。缺失 CAS basis 时 receiver MUST 以 `failed_precondition` 拒绝该 effect，并按多 cell 原子性拒绝整个 reducer input，不得实现无条件覆盖。并发且互不可达的 CAS set 若都在各自 `seal_basis` 下通过但写入不同值，join 结果为 `⊥`；同值重复 set 幂等。
- **`fsm`**：transition effect MUST 声明 `from` 与 `to`。同一 CBA basis 内相同 `(from,to)` 的重复 transition 是幂等的；同一 `from` 指向不同 `to` 的 sibling transition 返回 `⊥`。跨 basis 顺序仅由 causal refs 与 Seal DAG 决定；同一 basis 内不得用 HLC、接收顺序或 actor id 选择状态机 winner。
- **`ordered_log`**：entry MUST 绑定 issuer 与 issuer-local seq。每个 issuer 子链只把从起点开始的连续 prefix 纳入 cell value；issuer 子链出现缺口时，缺口后的 entry MUST 保留为 pending / diagnostic 输入，但不得进入 cell value、`state_root` leaf 或授权判断。依赖补齐后按同一规则确定性重算。
- **`or_set` / `counter` / `mv_register`**：`or_set` 按 observed-remove dot 集合 join；`counter` 只在 §9.3 允许的 issuer-local 切片内求和；`mv_register` 暴露并发 heads 而不产生 `⊥`。领域文档可进一步收窄这些 lattice 的合法 effect，但不得改变交换、结合、幂等的 core join 要求。

### 9.3.2 digest suite transition Seal（normative）

Realm 的 `digest_algorithm` 只能通过控制面 suite-transition Control Move 改变。transition Move MUST 经 Seal 接受，并在该 Transition Seal 上同时承诺旧 suite 与新 suite：

1. transition Move 的 payload MUST 声明 `from_digest_algorithm`、`to_digest_algorithm`、`transition_snapshot_ref` 与 `snapshot_commitment`；`from_digest_algorithm` MUST 等于当前 Realm live suite，`to_digest_algorithm` MUST 是 digest-suite registry 的 active row，且不得违反 registry 的 no-downgrade strength order。
2. Transition Seal body MUST 携带 `previous_state_root`，其 suite prefix 等于 `from_digest_algorithm`，并继续携带普通 `state_root`，其 suite prefix 等于 `to_digest_algorithm`。`previous_state_root` 是 §3.3 Realm 级 suite 排他的唯一豁免字段。
3. Verifier MUST 用旧 suite 重算 transition 前治理 view 的 `previous_state_root`，用新 suite 重算 transition 后治理 view 的 `state_root`，并验证 `snapshot_commitment` 对同一 control/data frontier 的 inclusion。任一 root、snapshot commitment 或 suite strength 判定不匹配时，Transition Seal MUST `rejected_seal`。
4. Transition Seal 接受后，该 Realm 内所有后续 Event digest、Seal id、state_root、Merkle leaf 与 receipt digest MUST 使用 `to_digest_algorithm`；旧 suite 只可出现在历史对象和该 Transition Seal 的 `previous_state_root` 中。

### 9.4 非治理强一致对象

看板位置、强单值状态机或其它非治理强一致对象三选一：

1. **默认 `mv_register` + user-pick**：并发结果暴露多 heads，任何有写权限者可再签一个 DataEvent 收敛。
2. **`sealed=true` 升控制面**：继承 Seal finality、`⊥` 和 recovery。
3. **per-object sequencer**：schema 指定某 DID 线性化该 cell 的 DataEvent；sequencer 失效时 MUST 退回 `mv_register` 或升控制面。

### 9.5 control cell `⊥` recovery（normative）

`bottom=reject` 的控制面 cell（典型 `cas_register` / `fsm`）join 到 `⊥`（§9.1.1）后是**死状态**：所有依赖它的 Control Move precondition、DataEvent 授权判定与读路径 fail closed（`failed_bottom`）。把该 cell 从 `⊥` 拉回单一合法值，唯一途径是本节定义的 **conflict-recovery Move**。`bottom=expose` cell 的 `⊥` 暴露多 heads、由后续普通 Move 收敛，**不**适用本节、也不需要 recovery capability。

conflict-recovery Move 不是新 event kind，而是一条**针对该 cell 的 Control Move**，由它携带的 `refs[]` role 与 reducer 的"`⊥` 唯一例外接受"规则识别。它 MUST 满足：

1. **携带 recovery 授权与见证 ref**：`refs[]` MUST 含 `role=recovery_capability`（critical，授权本次 recovery 的 grant）与至少一个 `role=state_witness`（critical，见证 `⊥` 之前该 cell 合法单值的 frontier + inclusion proof）。缺 `state_witness` MUST `recovery_witness_missing`。这两个 role 已登记于 [`event-and-patch.md` §2.2](../models/event-and-patch.md) 的 `SemanticRef.role`。
2. **witness 可重建 state_root**：`state_witness` 的 inclusion proof MUST 能重建该 witness frontier 的 `state_root`；不能则 `recovery_witness_invalid`。
3. **witness 严格 pre-conflict**：`state_witness` frontier MUST NOT 有到触发 `⊥` 的任一 sibling Move 的因果路径（即必须早于冲突）；否则 `recovery_witness_post_conflict`。这保证 recovery 锚定的是冲突前的合法状态，而非把冲突之一单方面"洗白"。
4. **recovery_capability 已 sealed 且在 witness 下成立**：`recovery_capability` grant 引用的 cell MUST 出现在 `state_witness` 的 `state_root` 中且取值不冲突；否则 `recovery_capability_not_sealed`。
5. **witness 不陈旧、未被撤销**：`state_witness` MUST NOT 早于允许的 freshness window，且 local frontier MUST NOT 已观察到针对该 `recovery_capability` 的 revoke / supersede 晚于 witness frontier；违反则 `recovery_witness_revoke_lagging`（receiver MUST 拒绝 stale witness replay）。
6. **必须 sealed**：conflict-recovery Move 是控制面 Move，MUST 经控制面 Seal 接受（继承 Seal finality），使"从 `⊥` 恢复到的单值"跨 receiver canonical 一致——与 §7.1 fork-resolution 的跨 receiver 确定性同纪律。reducer 在 cell 处于 `⊥` 时，**仅**接受满足上述全部条件的 conflict-recovery Move 写入该 cell（这是 `bottom=reject` cell 在 `⊥` 下对 `failed_bottom` 的唯一例外），把 cell 解析为该 Move 声明的单一合法值。

**recovery capability 来源**：`recovery_capability` 由 Realm 的恢复权威持有——即 §7.2 闭环里的 **recovery notary**（genesis `recovery_members` / `mixed` profile 的 fallback notary）所辖的 recovery / fork-resolution 授权；它与 §7.1 的 fork-resolution、[`event-and-patch.md` §2.6](../models/event-and-patch.md) over-fork repair 复用同一恢复权威，不引入新授权主体。`single_did` 且未声明可用 recovery 路径的 Realm，control cell `⊥` 是诚实的死状态（与 §7.2 第 2 点"证据可流转但不可生效"同一限制，也是 genesis 强制 `recovery_members` 组织分离的理由之一）。

**与 §7.1 的层次区分**：§7.1 恢复的是 **Seal-DAG 分叉**（equivocation / `fork_quarantine`）；本节恢复的是**未分叉治理状态内单个 cell 的 `⊥`**。两者由同一恢复权威书写、都经 Seal 接受，但作用对象不同，不可互相替代。该恢复路径由 conformance vector `ck.vector.cba_lattice.conflict_recovery_move.v1` 固定。

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
| `seen` | 相关 DataEvent 被至少一个服务或 witness 签发的 Event Batch Receipt 覆盖，但未被 seal 观测承诺。 |
| `observed` | 数据面结果进入某个 seal 的 `data_view_root` / `data_event_set_root`；这是观测承诺，不是 finality。 |
| `sealed` | Control Move 被已接受 Seal 覆盖并进入治理 `state_root`；仅控制面使用。 |
| `witnessed` | 对应 seal 另有 policy 要求的 witness / auditor attestation。 |
| `forked` | 查询依赖的控制面分支处于 `fork_quarantine`。 |
| `stale` | `seal_ref` / 撤销信息仍在 freshness window 内但需要刷新控制面后才能提升等级的降级接受结果；一旦撤销缺口或 seal freshness 超出 hard limit，结果 MUST 拒绝或隐藏（`stale_seal_ref`），不得以 `grade=stale` 返回。 |

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
2. DataEvent 的 GC 由 data DAG sync、Event Batch Receipt、AvailabilityReceipt、retention policy 与 application retention 决定；GC 不得破坏仍需验证的 actor chain、causal refs 或 availability commitment。
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
