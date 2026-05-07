---
title: Event Auth、Move/Anchor/Lattice 与状态收敛
---

## 1. 目标

Contrix v1 的 canonical history 由 signed Move、Anchor DAG 与 per-cell Lattice 三个协议原语构成。协议状态不再由全局 winner 算法、单 host proof 或独立 MLS 中间态驱动。

本文件定义：

- Move 如何表达多 cell 原子条件写。
- Anchor 如何给 Move 批次提供最终性、state root 与 ordering commitment。
- Lattice 如何在每个 cell 上确定性合并并暴露 bottom (`⊥`)。
- 授权、撤销、E2EE、冲突修复和恢复路径如何统一落在三原语上。

非目标：本文不定义全文搜索、媒体分发、projection 查询优化、实时 typing/presence 等派生层行为。

## 2. 术语

| 术语 | 定义 |
| --- | --- |
| Move | 一个 actor / service DID 签名的事务意图，包含 `preconditions[]`、`effects[]`、`anchor_ref` 与语义依赖 `refs[]`。 |
| Anchor | ordering authority 对一组 Move frontier 的承诺，包含 `predecessor_refs[]`、`frontier[]`、`state_root` 与 `anchorer_sig`。 |
| Anchor DAG | 某个 Space 内所有已接受 Anchor 的有向无环图。Genesis Anchor 没有 predecessor。 |
| Cell | 可被 Lattice 合并的最小协议状态单元，标识为 `cx:cell:<component>:<subject>` 或等价 canonical tuple。 |
| Lattice | Space schema 为每个 cell family 选择的封闭核心代数类型。`join()` 返回值或 bottom (`⊥`)。 |
| Bottom (`⊥`) | 该 cell 在当前 Anchor frontier 下无有效单值或存在非法状态。`bottom=reject` 时依赖它的 Move fail closed；`bottom=expose` 时可向 projection 暴露多值诊断。 |
| Effective State | 某个 Anchor view 的 `frontier` 中所有 Move 经 Lattice join 后得到的 cell map。 |
| Pending Move | 通过本地格式/签名初检但尚未被 Anchor frontier 覆盖的 Move。Pending Move 不影响 effective state。 |

## 3. Move

Move 的 wire schema 见 [`move.schema.json`](../../artifacts/schemas/move.schema.json)。Normative 形态：

```text
Move {
  id              = H(canonical bytes)
  issuer          DID
  space_id        Space id
  preconditions   [(cell_id, predicate)]
  effects         [(cell_id, lattice_op)]
  anchor_ref      Anchor.id
  refs            [(claim_id, role)]
  hlc             advisory timestamp
  sig             issuer signature over canonical bytes
}
```

规则：

1. `id` 由 canonical bytes 派生，MUST 覆盖 `anchor_ref`、`preconditions`、`effects`、`refs`、`hlc` 与 `issuer`。
2. `preconditions[]` 与 `effects[]` 是 set；同一 Move 是多 cell 原子 CAS。任一 precondition 不成立时，整个 Move FAIL，不能部分应用 effects。
3. `anchor_ref` MUST 指向接收方已知的 Anchor DAG 节点，并且相对本地 current anchor view 不超过 Space 声明的 `max_anchor_staleness_ms`。
4. `refs[]` 是语义依赖，元素必须带 role。常见 role 包括 `authorized_by`、`attestation`、`parent_move`、`after`、`recovery_capability`。未识别的 critical role MUST fail closed。
5. `hlc` 是诊断与 freshness 辅助字段，不参与 winner 选择；核心收敛由 Anchor 与 Lattice 决定。
6. Move 的 issuer 只有单签。委员会、多签、host、threshold quorum 均在 Anchor 层表达，不在 Move issuer 层表达。

### 3.1 Predicate

核心 predicate：

| Predicate | 语义 |
| --- | --- |
| `head_eq` | 当前 cell value / head 必须等于指定值。单 cell basis 是该 predicate 的特例。 |
| `head_in` | 当前 cell value / exposed heads 必须属于集合。用于冲突修复 Move。 |
| `satisfies` | 当前 cell value 必须满足 schema 注册的 deterministic predicate。仅允许引用封闭 Lattice 可验证的字段。 |
| `contains` | 当前 set / OR-set / covered frontier 必须包含指定元素或 frontier subset。 |

Predicate 不得读取本地数据库顺序、HTTP 到达时间、未签名服务端状态或外部 wall clock。

### 3.2 Effect

Effect 的 `lattice_op` 必须与目标 cell 的 Lattice type 兼容：

| Lattice type | 常见 op |
| --- | --- |
| `or-set` | `add(tag,value)`、`remove(tag)` |
| `mv-register` | `set(value)` |
| `cas-register` | `set(value)` |
| `fsm` | `transition(from,to,reason)` |
| `counter` | `inc(tag,n)`、`dec(tag,n)` |
| `ordered-log` | `append(entry, issuer_seq)` |

同一 Move MAY 写多个 cell。Space schema MAY 声明 `co_write_policy` 限制哪些 cell family 可以同 Move 写入；违反时 Move MUST `schema_violation` reject。

## 4. Anchor

Anchor 的 wire schema 见 [`anchor.schema.json`](../../artifacts/schemas/anchor.schema.json)。Normative 形态：

```text
Anchor {
  id                 = H(canonical bytes)
  space_id            Space id
  predecessor_refs    [Anchor.id]
  frontier            [Move.id]
  state_root          hash
  anchorer_sig        sig | multi_sig | threshold_sig
  hlc                 advisory timestamp
}
```

规则：

1. `predecessor_refs=[]` 仅允许 genesis Anchor。
2. 单调性：`A.frontier` MUST 是所有 predecessor frontier 的 superset。
3. Anchor 是持久承诺；它不修改 cell。Cell 变化只来自 frontier 内 Move 的 effects。
4. `anchorer_sig` 的合法签发者由 anchorer cell 在 predecessor joined view 下的 effective value 决定。
5. `state_root` MUST 是该 Anchor view 下所有 cell 当前 Lattice value / bottom diagnostics 的 canonical Merkle root。

### 4.1 Anchor View 与 Signed Compaction

多个 Anchor leaf 并存时，节点 MUST 计算 deterministic effective anchor view：

```text
effective_anchor_view(leaves):
  predecessor_refs = sorted(leaves.ids)
  frontier         = union(leaves.frontier)
  state_root       = recompute(frontier)
```

该 view 是本地纯函数，不需要签名，也不是新的 Anchor object。只有当 anchorer / committee 想压缩 Anchor DAG 时，才签发一个持久 compaction Anchor。Compaction Anchor 的 `frontier` 与 deterministic view 等价，并带有效 `anchorer_sig`。

### 4.2 Anchor Batch 语义

`apply_anchor(A)` MUST 按批处理语义执行：

```text
pre_state = joined_state(A.predecessor_refs)
new_moves = A.frontier - union(predecessor.frontier)

for M in deterministic_order(new_moves):
  verify_move(M, pre_state)

post_state = apply_all_effects_atomically(pre_state, new_moves)
assert merkle_root(post_state) == A.state_root
```

同一 Anchor 内的 `new_moves` 视为并发批。一个 Move 不得通过读取同批另一个 Move 的 effect 满足 precondition。若需要顺序，提交方 MUST 分成多个 Anchor，或在 `refs(role="after")` 中声明并由 anchorer 按下一 Anchor 处理。

### 4.3 Anchorer Cell

每个 Space 有一个 anchorer cell：

```text
cell = cx:cell:cx.component.anchorer.v1:<space_id>
lattice = cas-register
bottom = reject
```

它的 value 定义下一批 Anchor 的授权规则，例如：

- `single_did`: 单一 DID / service key。
- `threshold`: k-of-n committee。
- `open_set`: 允许集合内任一 DID 签发 leaf Anchor，DAG join 后收敛。
- `mixed`: 主 anchorer + fallback recovery anchorer。

变更 anchorer 是普通 Move，由旧 anchorer 签发的后续 Anchor finalize；新 anchorer 不得自签自己上位。

如果 anchorer cell 在某个 effective view 下为 `⊥`，Anchor 层进入 Space-wide pause：普通 Anchor 不得推进，只有 genesis 声明的 recovery anchorer / emergency quorum MAY 签发恢复 Anchor。该暂停不同于普通 cell-scoped bottom，必须在 API / UX 中明确暴露。

## 5. Lattice

每个 cell family 在 Space schema 或 canonical registry 中声明：

```text
Lattice {
  type        ∈ closed_core_set
  bottom      ∈ {reject, expose}
  parameters  type-specific
}
```

v1 封闭核心集：

| Type | Join 语义 | 用途 |
| --- | --- | --- |
| `or-set` | observed-remove set；add/remove 通过唯一 tag 收敛。 | capability grant set、device list、凭证撤销集合。 |
| `mv-register` | 并发 set 暴露多值；无单一 winner。 | 非安全草稿、可人工选择的偏好。 |
| `cas-register` | 严格 CAS；并发不同值返回 `⊥`。 | anchorer、关键 singleton policy、host 指针类状态。 |
| `fsm` | 状态机迁移；非法迁移或并发不可合并迁移返回 `⊥`。 | membership、lifecycle、invite/approval。 |
| `counter` | PN-counter 求和。 | 配额、审计计数。 |
| `ordered-log` | append-only log；按 issuer chain 与 entry id 去重。 | 审计、消息历史、不可变操作日志。 |

`lww-register`、依赖 actor 自报 timestamp 排序的 join、HTTP receive order、数据库自增 ID 均不得进入协议授权根。

### 5.1 Bottom Diagnostics

协议判断只区分 value 与 `⊥`，但实现 MUST 保留结构化诊断：

```text
Bottom {
  kind: conflict | invalid_transition | missing_dependency | unauthorized | anchorer_split | schema_error
  cells[]
  move_ids[]
  details
}
```

`bottom=reject` 的 cell 被 Move precondition 读取时，Move MUST fail closed，错误至少包含 `upstream_bottom`、cell id 与相关 Move ids。`bottom=expose` 的 cell MAY 返回 `{status:"conflict", heads:[...]}` 给 projection；它不得被授权路径当作 allow。

### 5.2 序内因果

Lattice `join()` 输入是 Move set，而不是本地接收序列。需要顺序语义的 type 必须把顺序编码进 op：

- `fsm` 通过 `transition.from` / `transition.to` 校验路径。
- `ordered-log` 通过 `issuer_seq`、`parent_entry` 或 entry hash 链校验 append。
- `cas-register` 通过 Move precondition `head_eq` 表达 basis。

若某 lattice type 对同一输入 set 不能给出 deterministic value / bottom，则该 type 的实现不符合 v1。

## 6. Move 验证

```text
verify_move(M, pre_state):
  1. canonical bytes 与 M.id 匹配；M.sig 由 M.issuer 控制的 key 签发。
  2. M.refs 中所有 critical ref 已知且自身 valid。
  3. M.anchor_ref 在本 Space Anchor DAG 中，且未超过 max_anchor_staleness_ms。
  4. 对每个 (cell, predicate):
       L = schema.lattice(cell)
       v = pre_state[cell]
       if v == ⊥ and L.bottom == reject: FAIL_BOTTOM
       if not predicate(v): FAIL_PRECONDITION
  5. 对每个 (cell, op):
       schema.lattice(cell).validate(op)
       authz.check(M.issuer, cell, op, M.refs)
  6. PASS
```

授权来源必须是 `refs(role="authorized_by")` 或等价 schema role 中的凭证链。Capability cache 的 key MUST 包含 Anchor view / state root；当相关 grant/revoke/claim/policy cell 变化时 cache 立即失效。

## 7. Anchor 应用

```text
apply_anchor(A):
  1. 校验 predecessor_refs 均已知且属于同一 Space。
  2. 校验 A.frontier 覆盖所有 predecessor frontier。
  3. 在 predecessor joined view 下读取 anchorer cell 并校验 A.anchorer_sig。
  4. 以 predecessor joined state 批量 verify 所有 new_moves。
  5. 原子应用 new_moves effects，重算 state_root。
  6. state_root 匹配则接受 Anchor；否则拒绝 Anchor 并生成 anchor_fault 诊断。
```

Anchor 被拒绝时，其 frontier 内 Move 不因此变成 effective。节点 MAY 保留这些 Move 作为 pending / diagnostic 输入，但不得让它们推进 query 或授权。

## 8. 冲突修复

冲突修复没有特殊事件类型。它是普通 Move：

```text
Move {
  preconditions: [
    (cell, head_in [conflict_head_A, conflict_head_B])
  ],
  effects: [
    (cell, set decision)
  ],
  refs: [
    (recovery_capability, role="authorized_by")
  ]
}
```

修复权威来自冲突前 effective state 中的 governance / recovery capability。不得用冲突候选本身声明的新 policy、new anchorer 或 new admin 来授权修复。

长时间未修复的 `⊥` 不会自动选 winner。Space MAY 声明 `bottom_escalation_after_ms`；超时后，客户端和服务端应提示 emergency recovery quorum，但仍需普通 Move + Anchor 生效。

## 9. 部署 Profile

Hub、threshold、open federation、sovereign federation 和 E2EE 只是 anchorer cell value 与 Anchor uniqueness profile 的不同组合。

| Profile | Anchorer value | Anchor DAG 约束 |
| --- | --- | --- |
| `single_did` | 单一 service DID / host key。 | 可要求 signed Anchor 单链；compaction 由该 DID 签发。 |
| `threshold` | k-of-n committee key / signer set。 | 可要求 signed Anchor 单链；threshold sig 提供 uniqueness。 |
| `open_set` | 管理员 / federation peer DID 集合。 | 允许多 leaf；query 使用 deterministic effective anchor view。 |
| `mixed` | 主 anchorer + fallback recovery anchorer。 | 正常单链；anchorer fault / bottom 时 fallback 可签 recovery Anchor。 |

Space create MUST 固定 genesis anchorer 与 recovery anchorer。后续变更走 anchorer cell 的普通 Move。

## 10. E2EE 与 MLS

MLS commit 是 Move，不是 Anchor。它写入普通 cell：

```text
Move(MLS commit) {
  preconditions: [
    (mls_epoch_cell, head_eq prev_epoch),
    (covered_frontier_cell, contains governance_frontier_required_by_message)
  ],
  effects: [
    (mls_epoch_cell, set new_epoch),
    (key_schedule_cell, set new_schedule),
    (covered_frontier_cell, set attested_governance_frontier)
  ]
}
```

E2EE message Move 若依赖 `mls_bound` cell，MUST 在 preconditions 中证明 `covered_frontier_cell` 覆盖其 `anchor_ref` 所需 governance frontier。MLS 滞后只阻塞 E2EE message / key schedule Move，不阻塞 governance recovery Move。

Move 在 Anchor 前是 pending；被 Anchor 后是否可用于 E2EE 由 `covered_frontier_cell` precondition 决定。

## 11. Redaction 与 Erasure

Redaction 是写入 redaction / erasure cell 的 Move。Redaction effect 必须保留足以验证 Move id、签名、anchor inclusion、target id、授权凭证和 tombstone stub 的最小数据。

对 `ordered-log` 历史，redaction 不删除 log entry id；它写入同 target 的 redaction cell，使 projection 隐藏或替换 payload。审计、legal hold 与 erasure receipt 规则见隐私和安全文档。

## 12. Snapshot、GC 与恢复

1. 未被任何 Anchor frontier 覆盖、且未被 active pending Move / recovery Move 引用的 Move MAY GC。
2. 已 Anchor 的 Move MUST 保留审计 stub；payload 可按 retention / erasure 规则裁剪。
3. Anchor DAG 可通过 signed compaction Anchor 压缩；压缩不得丢失 frontier、state_root、签名验证链或必要 bottom diagnostics。
4. Snapshot 是 Anchor view 的 materialized state_root 证明，不是独立真相源。没有可验证 Anchor / Move inclusion proof 的 snapshot 不得用于授权 allow。

## 13. 失败状态

| 状态 | 语义 |
| --- | --- |
| `pending_anchor` | Move 已通过本地初检，等待 Anchor。 |
| `effective` | Move 被已接受 Anchor frontier 覆盖，并已进入 state_root。 |
| `failed_precondition` | Move 在 Anchor batch pre-state 下 precondition 不成立。 |
| `failed_bottom` | Move 依赖 `bottom=reject` 的 cell。 |
| `rejected_anchor` | Anchor 签名、单调性、Move batch 或 state_root 校验失败。 |
| `anchorer_paused` | anchorer cell 为 `⊥`；Space-wide Anchor 推进暂停，只允许 recovery Anchor。 |

实现 MAY 在 API 层继续使用兼容错误码，但必须映射到本表语义。

## 14. 规模上限

Move/Anchor/Lattice 必须受 [`scalability-constraints.md`](../conformance/scalability-constraints.md) 约束：

- 单个 Move canonical size 默认不超过 1 MiB。
- 单个 Move 的 `preconditions + effects` 默认不超过 256。
- 单个 Anchor 新增 Move 默认不超过 1,000。
- Anchor DAG leaf 数超过实现声明上限时，节点 SHOULD 请求或生成 compaction Anchor。
- 单次 Lattice join 超过预算时，节点 MUST 返回可恢复错误或使用可验证 state_root + inclusion proof；不得用本地接收顺序替代。

实现 SHOULD 为每个 core lattice type 提供增量 API，但 wire 互操作只依赖 deterministic full join 语义。
