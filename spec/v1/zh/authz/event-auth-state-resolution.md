---
title: Event Auth、Move/Anchor/Lattice 与状态收敛
sidebar:
  label: Event Auth & State
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
  id              = H(canonical bytes excluding sig)
  issuer          DID
  space_id        Space id
  preconditions   [(cell_id, predicate)]
  effects         [(cell_id, lattice_op)]
  anchor_ref      Anchor.id
  refs            [(ref_id, role)]
  hlc             advisory timestamp
  sig             issuer signature over canonical bytes
}
```

规则：

1. `id` 由 canonical bytes 派生，MUST 覆盖 `issuer`、`space_id`、`preconditions`、`effects`、`anchor_ref`、`refs` 与 `hlc`。`sig` 本身 MUST NOT 进入 canonical bytes（它是对 canonical bytes 的签名）。`space_id` 必须进入以防止跨 Space 重放。
2. `preconditions[]` 与 `effects[]` 是 set；同一 Move 是多 cell 原子 CAS。任一 precondition 不成立时，整个 Move FAIL，不能部分应用 effects。`effects[]` MUST 至少含 1 项（纯查询 Move 不存在）。
3. `anchor_ref` MUST 指向接收方已知的 Anchor DAG 节点，并且相对本地 current anchor view 不超过 Space 声明的 `max_anchor_staleness_ms`。
4. `refs[]` 是语义依赖，每个元素 `{id, role, critical?}`。常见 role 包括 `authorized_by`、`attestation`、`parent_move`、`after`、`recovery_capability`、`state_witness`（§8.1，conflict recovery Move 必备 — 引用签名 snapshot / compaction Anchor）、`inclusion_proof`（§8.1，conflict recovery Move 必备 — Merkle inclusion proof bytes 或 ref）。`critical` 默认 `true`；未识别的 critical role MUST fail closed，未识别的非 critical role MAY 被忽略。
5. `hlc` 是诊断与 freshness 辅助字段，不参与 winner 选择；核心收敛由 Anchor 与 Lattice 决定。
6. Move 的 issuer 只有单签。委员会、多签、host、threshold quorum 均在 Anchor 层表达，不在 Move issuer 层表达。

### 3.1 Predicate

核心 predicate（wire 字段 `{op, value?, values?, predicate_id?}`，schema 见 [`move.schema.json`](../../artifacts/schemas/move.schema.json) `predicate`）：

| `op` | 必填字段 | 语义 |
| --- | --- | --- |
| `head_eq` | `value` | 当前 cell value / head 必须等于指定值。单 cell basis 是该 predicate 的特例。 |
| `head_in` | `values` | 当前 cell value / exposed heads 必须属于集合。用于冲突修复 Move。 |
| `satisfies` | `predicate_id` | 当前 cell value 必须满足 schema 注册的 deterministic predicate（按 `predicate_id` 派发到该 cell schema 声明的可验证 predicate 实现）。仅允许引用封闭 Lattice 可验证的字段。 |
| `contains` | `value`（单元素）或 `values`（子集检查） | 当前 set / OR-set / covered frontier 必须包含指定元素或 frontier subset。 |

Predicate 不得读取本地数据库顺序、HTTP 到达时间、未签名服务端状态或外部 wall clock。

### 3.2 Effect

Effect 的 `lattice_op` 必须与目标 cell 的 Lattice type 兼容。`lattice_op` 的 wire 字段为 `{type, tag?, value?, from?, to?, reason?, issuer_seq?}`（schema 见 [`move.schema.json`](../../artifacts/schemas/move.schema.json) `lattice_op`）：

| Lattice type | `op.type` | 必填字段 | 可选字段 |
| --- | --- | --- | --- |
| `or-set` | `add` | `tag`、`value` | — |
| `or-set` | `remove` | `tag` | `reason` |
| `mv-register` | `set` | `value` | — |
| `cas-register` | `set` | `value` | — |
| `fsm` | `transition` | `from`、`to` | `reason` |
| `counter` | `inc` / `dec` | `value`（非负整数增量） | `tag`（per-counter 维度） |
| `ordered-log` | `append` | `value`（entry payload）、`issuer_seq` | — |

`op.value` 与 entry payload 必须满足该 cell schema；接收方 MUST 拒绝多余字段（`additionalProperties=false`）。

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

### 4.2 `state_root` Canonical Merkle 编码

§4 rule 5 要求 `state_root` 是该 Anchor view 下所有 cell value / bottom 的 canonical Merkle root。本节锁定具体编码以保证不同实现互通。

#### 4.2.1 Leaf 编码

每个有过 effect 的 cell 一条 leaf：

```text
leaf_input = canonical_json({
  "cell":  "<CellRef wire string>",
  "state": <state_object>
})
leaf_hash  = sha256(leaf_input)
```

`<state_object>` 取决于 cell 当前 join 结果：

| Lattice 结果 | `state_object` |
| --- | --- |
| `Value(v)` | `{ "value": v }` |
| `Bottom(b)` | `{ "bottom": <Bottom canonical JSON, **省略 `anchor_view` 字段**> }` |

`bottom.anchor_view` 必须省略，因为 state_root 自身已经定义于一个具体的
Anchor view，把同 view 写进 leaf 会造成自引用并破坏 root 的稳定性。
`bottom` 的其他字段（`kind` / `cells[]` / `move_ids[]` / `heads[]` / `details` /
`escalated_at`）保留进 leaf——它们是该 cell 在该 view 下状态的一部分，跨 view
可能不同，是 state_root 必须捕获的差异。

#### 4.2.2 树形

1. 收集该 Anchor view 下所有有过至少一次 effect 的 cell。
2. 对每个 cell 计算 `leaf_hash`（4.2.1）。
3. 把 `(cell_wire, leaf_hash)` 元组按 `cell_wire` Unicode code point 升序排序。
4. 把排序后的 `leaf_hash` 列表按 RFC 6962-style binary Merkle tree 算 root：
   - 偶数个：两两配对 `parent = sha256(left || right)`，逐层向上。
   - 奇数个：最后一个 leaf 直接提升到上一层（**不复制**）。
   - 单个 leaf：root = leaf_hash。
   - 空列表：root = `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空字节 SHA-256）。
5. wire 形式：`state_root = "sha256:" + lower_hex(root)`。

#### 4.2.3 增量重算

实现 SHOULD 缓存 cell → leaf_hash 表，在 `apply_anchor` 接受新 Anchor 后只
重算受影响 cell 的 leaf 与所属 Merkle 分支；wire 上的 `state_root` 必须等于
全量重算结果。

#### 4.2.4 跨实现互通

不同 conformant 实现处理同一 Move/Anchor 历史 MUST 产出相同 state_root。
偏离上述编码（不同 leaf shape、不同 tree 形、不同空 list 处理）即视为
v1 wire-incompatible，必须用独立 profile 声明。

### 4.3 Anchor Batch 语义

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

### 4.4 Anchorer Cell

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

协议判断只区分 value 与 `⊥`，但实现 MUST 保留结构化诊断（wire schema 见 [`bottom.schema.json`](../../artifacts/schemas/bottom.schema.json) `cx.schema.bottom.v1`）：

```text
Bottom {
  kind         ∈ {conflict, invalid_transition, missing_dependency,
                  unauthorized, anchorer_split, schema_error}
  cells[]      cell_ids 参与诊断（多 cell 原子 Move 失败时 >1）
  move_ids[]   anchored Move ids 触发该诊断（结构性 ⊥ 可为空）
  anchor_view? {leaves[], state_root?} 观察该 ⊥ 的 Anchor view，便于复算
  heads[]?     kind=conflict 时候选 head 值；UI / 审计可见，授权 MUST NOT 据此选 winner
  details?     kind-specific structured details
  escalated_at? 跨过 Space.bottom_escalation_after_ms 时的时间戳
}
```

`bottom=reject` 的 cell 被 Move precondition 读取时，Move MUST fail closed（state code `failed_bottom`），错误至少包含 `cells[]` 与 `move_ids[]`。`bottom=expose` 的 cell MAY 返回 `{status:"conflict", heads:[...]}` 给 projection；它不得被授权路径当作 allow。

`anchorer_split` 是特殊 kind：当 anchorer cell（cas-register, bottom=reject）出现并发 set 时该诊断生效；它对应 §13 的 `anchorer_paused` Space 状态，仅 recovery anchorer / emergency quorum 签发的 Anchor 可恢复推进。

### 5.2 序内因果

Lattice `join()` 输入是 Move set，而不是本地接收序列。需要顺序语义的 type 必须把顺序编码进 op：

- `fsm` 通过 `transition.from` / `transition.to` 校验路径。
- `ordered-log` 通过 `issuer_seq`、`parent_entry` 或 entry hash 链校验 append。
- `cas-register` 通过 Move precondition `head_eq` 表达 basis。

若某 lattice type 对同一输入 set 不能给出 deterministic value / bottom，则该 type 的实现不符合 v1。

### 5.3 Lattice 参考实现

下列伪代码为各核心 Lattice type 的 normative `join()` 与 `validate_op()` 行为；参考向量在 [`conformance-vectors.md`](../conformance/conformance-vectors.md) §2。

#### 5.3.1 `or-set`

Observed-remove set。每个 add op 必须携带唯一 `tag`；remove op 引用同 `tag`。Tag 由提交方按 `cell_subject` 内规则确定性派生（如 `<grant_kind>:<peer>:<scope>`），允许同一 (cell, semantics) 上不同 Move 共享 tag 自动幂等。

```text
join(moves) -> Set<{tag, value}>:
  adds   = { (eff.tag, eff.value) | M ∈ moves, eff ∈ M.effects, eff.op.type=="add" }
  removes = { eff.tag | M ∈ moves, eff ∈ M.effects, eff.op.type=="remove" }
  return  { (t, v) ∈ adds | t ∉ removes }

validate_op(op):
  op.type ∈ {add, remove}
  op.tag matches schema tag pattern (non-empty, deterministic)
  if add: op.value satisfies schema
```

`bottom` 永远不出现（or-set 总有合法 join 值）。`bottom=expose` 仅用于 projection 在多 head 场景把 add/remove 并发可视化，不影响协议授权判断。

#### 5.3.2 `mv-register`

Multi-value register。所有未被后续 set 取代的并发值都暴露。

```text
join(moves) -> Set<value>:
  candidates = { (M.id, eff.value) | M ∈ moves, eff ∈ M.effects, eff.op.type=="set" }
  // 取因果最大集：去掉被任何后继 Move 偏序覆盖的 candidate
  return  { v | (m, v) ∈ candidates, ¬∃(m', _) ∈ candidates: m' > m via Move.refs("after") }

validate_op(op):
  op.type == "set"
  op.value satisfies schema
```

`bottom=expose` 是 mv-register 的常态：projection 以 `{status:"conflict", heads:[...]}` 暴露多值。授权路径不得用 mv-register 表达。

#### 5.3.3 `cas-register`

Compare-and-swap register。Move 通过 precondition `head_eq` 声明 basis；并发不同 set 返回 `⊥`。Move 的因果序由 (a) Anchor batch 包含关系，与 (b) 跨 batch 时 `Move.refs(role="after")` 显式声明给出；同 Anchor batch 内的 sibling Moves 视为并发。

```text
join(moves) -> value | ⊥:
  // 按 Anchor batch index 升序 + 同 batch 内按 head_eq 链化（pre-state value → effect value）
  // 跨 batch 时若需要绕过 head_eq 链化，使用 Move.refs(role="after")
  current = null
  for batch in moves grouped by anchor_ref ordered by anchor index:
    settled = current
    siblings = []
    for M in batch with effect on this cell:
      pre = find precondition(head_eq) on this cell in M
      basis = pre.value if pre else null   // null = 允许 first set
      siblings.append((basis, M.effect.value))
    if ∃ siblings (b1, v1), (b2, v2) with b1==b2 and v1!=v2:
      return ⊥
    if siblings is non-empty:
      // 取共享 basis 后唯一新 value（已在上一步保证唯一）
      basis_required = unique(siblings.map(b))
      if basis_required != settled and basis_required is not null:
        return ⊥                  // basis 不匹配 pre-state
      current = unique(siblings.map(v))
  return current

validate_op(op):
  op.type == "set"
  op.value satisfies schema
```

`bottom=reject` 是 cas-register 的标准配置：依赖该 cell 的 Move MUST `fail_bottom`（spec 状态码 `failed_bottom`）。anchorer cell、关键 singleton policy 与 host 指针均使用此组合。

#### 5.3.4 `fsm`

有限状态机。每个 transition op 声明 `from` / `to`；Schema 在 `parameters` 中声明合法 transition 表。

```text
join(moves) -> state | ⊥:
  ordered  = topological_sort(moves)
  state    = parameters.initial_state
  for M in ordered:
    eff = find transition effect for this cell
    if eff.op.from != state: return ⊥          // 非法 transition
    if eff.op.(from,to) ∉ parameters.allowed_transitions: return ⊥
    state = eff.op.to
  // 并发 sibling Move 在同 state 上选择不同 to，且都不可合并 → ⊥
  if siblings produce divergent next_state:
    return ⊥
  return state

validate_op(op):
  op.type == "transition"
  op.from, op.to ∈ parameters.states
  (op.from, op.to) ∈ parameters.allowed_transitions
```

membership / lifecycle / invite-approval 多用 `bottom=reject`。

#### 5.3.5 `counter`

PN-counter（positive/negative split counter）。每个 (issuer, tag) 维护独立的 inc / dec 计数。`op.value` 是非负整数增量；`op.tag` 可选（per-counter 维度）。

```text
join(moves) -> integer:
  per_issuer_tag = empty map<(issuer, tag?), (pos, neg)>
  for M in moves:
    for eff in M.effects on this cell:
      key = (M.issuer, eff.op.tag)            // tag absent → null sentinel
      (pos, neg) = per_issuer_tag.get(key, (0,0))
      if eff.op.type == "inc": pos += eff.op.value
      if eff.op.type == "dec": neg += eff.op.value
      per_issuer_tag[key] = (pos, neg)
  return  Σ (pos - neg) over all keys

validate_op(op):
  op.type ∈ {inc, dec}
  op.value is a non-negative integer (overflow guard at parameters.max)
  op.tag is optional but, when present, MUST match schema tag pattern
```

`bottom` 永远不出现。`bottom=expose` 仅在配额跨界等场景下作为诊断（actual value still defined）。

#### 5.3.6 `ordered-log`

Append-only log。Entry payload 通过 `op.value` 承载；每 issuer 子链由 `op.issuer_seq` 单调推进；跨 Move 全局去重依赖 `cell schema` 在 entry 内声明的稳定 entry id（如 `value.entry_id` 或 canonical-bytes-derived hash），具体由 cell schema `parameters.entry_id_field` 指定。

```text
join(moves) -> List<entry_record>:
  entries = []
  for M in moves:
    for eff in M.effects on this cell:
      if eff.op.type != "append": continue
      eid = canonical_entry_id(eff.op.value, schema.parameters.entry_id_field)
      entries.append({
        move_id: M.id, issuer: M.issuer,
        seq: eff.op.issuer_seq, value: eff.op.value, entry_id: eid
      })
  // 每 issuer 形成独立子链；同一 (issuer, seq) 重复 → 取最小 entry_id
  per_issuer = group_by(entries, key=issuer)
  for issuer, items in per_issuer:
    items = dedupe_by_entry_id(items)
    items = sort_by(seq)
    items MUST form a contiguous chain：item[i].seq == item[i-1].seq + 1
  // 跨 issuer 不强制全局序；projection 可按 (anchor_index, hlc, issuer, seq) 展示
  return concat(per_issuer.values())

validate_op(op):
  op.type == "append"
  op.issuer_seq is non-negative integer; monotonic per (cell, issuer)
  op.value satisfies entry schema declared by cell parameters
```

`bottom` 永远不出现。审计、消息历史、不可变操作日志均使用 `bottom=expose`，并发 append 不阻塞协议判断。

### 5.4 Profile 不得引入新 Lattice type

接收方不识别核心 Lattice type MUST fail closed；扩展 cell family MUST 通过 schema/profile 显式声明并声明 fall-back 行为；任何引入新 lattice type 的 profile 必须先经过 v1 protocol-amendment 流程才能被 normative 集成（避免 implicit 协议分叉）。

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
    (recovery_capability,        role="authorized_by"),
    (pre_conflict_state_witness, role="state_witness", critical=true),
    (snapshot_inclusion_proof,   role="inclusion_proof", critical=true)
  ]
}
```

修复权威来自冲突前 effective state 中的 governance / recovery capability。不得用冲突候选本身声明的新 policy、new anchorer 或 new admin 来授权修复。

### 8.1 Pre-conflict State Witness 强制要求

`open_set` 与 `threshold` Anchor profile 下，多个 verifier 在 ⊥ 发生瞬间持有的"冲突前 effective state"可能不同——peer A 的 state_root 与 peer B 的 state_root 可能源自不同的 Anchor leaf 子集。如果允许 recovery Move 仅口头引用"冲突前 effective state"，攻击者就可以选择对自己有利的 anchor view 子集来"证明"自己持有 recovery_capability，于是同一 ⊥ 出现两条互斥的修复 Move。这种攻击在 v1.0 之前的 §8 设计下没有防护手段。

为此，conflict-recovery Move MUST 显式提供两条 critical refs，否则 receiver MUST `failed_precondition` 拒绝：

1. **`pre_conflict_state_witness`** — 一个签名 snapshot 或 signed compaction Anchor 的 id，满足：
   - 它来自冲突 cell 进入 ⊥ 之前的 Anchor view（即该 witness 所引用 frontier 不包含触发冲突的任一 sibling Move）。
   - 它由 Space 当前 anchorer cell value 授权的签名者签发（`single_did` / `threshold` / `open_set` 的 anchorer rule）。
   - 它的 `state_root` 中包含 recovery_capability 所授权的 cell value。

2. **`snapshot_inclusion_proof`** — 一个 RFC 6962 风格的 Merkle inclusion proof，证明：
   - 引用的 `recovery_capability` grant cell value 真实属于 `pre_conflict_state_witness.state_root`（而不是攻击者本地伪造的 effective view）。
   - Inclusion proof 的 leaf 编码 MUST 按 §4.2.1 锁定的 leaf shape 计算（`canonical_json({"cell": "<CellRef>", "state": <state_object>})`）。
   - Proof path 的 sibling hash 序列 MUST 能重算出与 `pre_conflict_state_witness.state_root` 完全相同的 root。

Receiver 在 verify_move(M) 时，对 critical role ∈ {`state_witness`, `inclusion_proof`}：

- 若 ref 缺失或签名无效 → `failed_precondition`（`reason="recovery_witness_missing"`）。
- 若 inclusion proof 不能重算出 witness 的 `state_root` → `failed_precondition`（`reason="recovery_witness_invalid"`）。
- 若 witness frontier 与触发 ⊥ 的 sibling Move 之一存在因果路径（即 witness 不在冲突前）→ `failed_precondition`（`reason="recovery_witness_post_conflict"`）。
- 若 witness 的 state_root 不包含 recovery_capability cell 或包含的 cell value 与 grant 引用不一致 → `failed_precondition`（`reason="recovery_capability_not_anchored"`）。

`single_did` Anchor profile 下，由于 anchor view 全网唯一，该机制等价于自然成立——但 wire 上仍 MUST 携带 witness ref，便于审计回放。这避免实现因为"现在用的是 single_did 就跳过校验"而在未来 anchorer 升级到 `open_set` 时无声留下盲区。

### 8.2 ⊥ 升级与 emergency recovery

长时间未修复的 `⊥` 不会自动选 winner。Space MAY 声明 `bottom_escalation_after_ms`；超时后，客户端和服务端应提示 emergency recovery quorum，但仍需普通 Move + Anchor 生效，并仍 MUST 满足 §8.1 的 witness + inclusion proof 要求。emergency recovery quorum 的特殊之处仅在于 capability `subject` 由 genesis 声明的 emergency role 担任，而不在于跳过证据要求。

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

MLS commit 是 Move，不是 Anchor。它写入三个 well-known cell（cell family 由 `cx.component.mls_epoch.v1` / `cx.component.key_schedule.v1` / `cx.component.covered_frontier.v1` 给出，cell_subject 为 MLS group id 或 space id）：

```text
Move(MLS commit) {
  preconditions: [
    (mls_epoch_cell,        head_eq prev_epoch),                  // cas-register
    (covered_frontier_cell, contains governance_frontier_required) // or-set / set semantics
  ],
  effects: [
    (mls_epoch_cell,        set new_epoch),
    (key_schedule_cell,     set new_schedule),
    (covered_frontier_cell, add attested_governance_frontier)
  ]
}
```

`covered_frontier_cell` 是声明"该 MLS group 当前已绑定的 governance Anchor frontier"的 cell（`or-set`，bottom=expose）：每个 MLS commit 把它绑定到的 governance Anchor 加入；E2EE message Move 在 preconditions 中要求 `contains` 自身 `anchor_ref` 所代表的 governance frontier。

E2EE message Move（即在加密 payload 上下文中提交的 Move，例如 `cx.message.create` 在 E2EE Space）MUST 在 preconditions 中证明 `covered_frontier_cell` 覆盖其 `anchor_ref` 所需 governance frontier。MLS 滞后只阻塞 E2EE message / key schedule Move（它们引用 `covered_frontier_cell`），不阻塞 governance / recovery Move（它们不引用该 cell）。

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

| 状态 | 语义 | 关联 Bottom kind |
| --- | --- | --- |
| `pending_anchor` | Move 已通过本地初检，等待 Anchor。 | — |
| `effective` | Move 被已接受 Anchor frontier 覆盖，并已进入 state_root。 | — |
| `failed_precondition` | Move 在 Anchor batch pre-state 下 precondition 不成立；包括 conflict-recovery Move 缺失或无效的 `state_witness` / `inclusion_proof` ref（§8.1）。`reason` 字段细分 `recovery_witness_missing` / `recovery_witness_invalid` / `recovery_witness_post_conflict` / `recovery_capability_not_anchored`。 | — |
| `failed_bottom` | Move 依赖 `bottom=reject` 的 cell。 | 由 §5.1 中对应的 kind 触发（如 `conflict`、`invalid_transition`、`schema_error`）。 |
| `rejected_anchor` | Anchor 签名、单调性、Move batch 或 state_root 校验失败。 | — |
| `anchorer_paused` | anchorer cell 为 `⊥`；Space-wide Anchor 推进暂停，只允许 recovery Anchor。 | `anchorer_split`（§5.1）。 |

实现 MAY 在 API 层继续使用兼容错误码，但必须映射到本表语义。Move 的当前状态字段在 sync wire 上以 `move_state` 暴露（见 [`sync/service-surface.md`](../sync/service-surface.md) §5.5）。

## 14. 规模上限

Move/Anchor/Lattice 必须受 [`scalability-constraints.md`](../conformance/scalability-constraints.md) 约束：

- 单个 Move canonical size 默认不超过 1 MiB。
- 单个 Move 的 `preconditions + effects` 默认不超过 256。
- 单个 Anchor 新增 Move 默认不超过 1,000。
- Anchor DAG leaf 数超过实现声明上限时，节点 SHOULD 请求或生成 compaction Anchor。
- 单次 Lattice join 超过预算时，节点 MUST 返回可恢复错误或使用可验证 state_root + inclusion proof；不得用本地接收顺序替代。

实现 SHOULD 为每个 core lattice type 提供增量 API，但 wire 互操作只依赖 deterministic full join 语义。
