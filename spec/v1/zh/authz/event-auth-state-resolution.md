---
title: Event Auth、Move/Anchor/Lattice 与状态收敛
status: candidate
normative: true
stability: v1
updated: 2026-06-10
sidebar:
  label: Event Auth & State Resolution
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret v1 的 canonical history 由 signed Move、Anchor DAG 与 per-cell Lattice 三个协议原语构成。协议状态不再由全局 winner 算法、单 host proof 或独立 MLS 中间态驱动。

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
| Anchor | ordering authority 对一组 Move frontier 的承诺，包含 `predecessor_refs[]`、`frontier[]`、`state_root` 与 `anchorer_signature`。 |
| Genesis Anchor | 某个 Realm 的 Anchor DAG 根 Anchor。它是唯一允许 `predecessor_refs=[]` 的 Anchor，且 v1 要求 `frontier=[]`；它给该 Realm 的首个 reducer-input Event 提供 `anchor_ref` 基线，本身不是 Event，也不写 cell。 |
| Anchor DAG | 某个 Realm 内所有已接受 Anchor 的有向无环图。Genesis Anchor 没有 predecessor。 |
| Cell | 可被 Lattice 合并的最小协议状态单元，标识为 `ck:cell:<component>:<subject>` 或等价 canonical tuple。 |
| Lattice | Realm schema 为每个 cell family 选择的封闭核心代数类型。`join()` 返回值或 bottom (`⊥`)。 |
| Bottom (`⊥`) | 该 cell 在当前 Anchor frontier 下无有效单值或存在非法状态。`bottom=reject` 时依赖它的 Move fail closed；`bottom=expose` 时可向 projection 暴露多值诊断。 |
| Effective State | 某个 Anchor view 的 `frontier` 中所有 Move 经 Lattice join 后得到的 cell map。 |
| Pending Move | 通过本地格式/签名初检但尚未被 Anchor frontier 覆盖的 Move。Pending Move 不影响 effective state。 |

### 2.1 三原语关系总览

下图把 Move / Anchor / Lattice 三个原语的协作关系画成一张图。**Move 提交意图、Anchor 给出 finality、Lattice 决定 per-cell 收敛值或 ⊥**——三层缺一不可。

```mermaid
flowchart LR
    subgraph M ["Move（actor / service DID 单签）"]
        direction TB
        Mbox["preconditions[] (cell, predicate)<br/>effects[] (cell, lattice_op)<br/>anchor_ref<br/>refs[] (authorized_by / state_witness / ...)"]
    end

    subgraph A ["Anchor DAG（ordering / finality）"]
        direction TB
        A1["Anchor N-1<br/>frontier / state_root"]
        A2["Anchor N<br/>frontier ⊇ N-1<br/>state_root = H(per-cell join)<br/>anchorer_signature"]
        A1 --> A2
    end

    subgraph L ["Cell × Lattice（per-cell deterministic join）"]
        direction TB
        Cells["cas_register / or_set / mv_register<br/>fsm / counter / ordered_log"]
        Bot["⊥ bottom<br/>bottom=reject → 依赖 Move fail closed<br/>bottom=expose → 暴露多值诊断 + 等待 conflict-recovery"]
        Cells -. "并发冲突 / 非法状态" .-> Bot
    end

    Mbox -- "anchor_ref（提交基线，受 max_anchor_staleness_ms 限制）" --> A
    Mbox -- "preconditions 校验" --> Cells
    A -- "frontier 覆盖后 effects 才进 effective state" --> Cells
```

读图要点：

- Move 的 issuer 永远是单签；委员会 / 多签 / threshold 在 Anchor 层表达，不在 Move 层。
- Anchor 是持久承诺，**不修改 cell**——cell 变化只来自 frontier 内 Move 的 effects 经 Lattice join 后产生。
- Pending Move（已签名但 anchor_ref 未被覆盖）不进 effective state；超出 `max_anchor_staleness_ms` 后必须 rebase 重签。
- ⊥ 不是错误终态：`bottom=expose` 的 cell 可由带 `state_witness` + `inclusion_proof` 的 conflict-recovery Move 收回。

### 2.2 Event、Move、Anchor、Lattice 的分层

Cokret v1 在线路上只有 signed Event Envelope；**Move 不是第二种 wire object**。当一个 Event 同时携带 `preconditions[]`、`effects[]` 与 `anchor_ref` 时，reducer / verifier 把这个 Event 按 Move 语义解释：`preconditions[]` 描述提交者认为的 pre-state，`effects[]` 描述要写入哪些 cell，`anchor_ref` 描述这次写入基于哪个 Anchor view。没有这三个字段的 durable Event 仍可作为审计、通知或账户私有状态事实存在，但不是共享 Realm 的 reducer-input Move。

Anchor 也不是 Event。Anchor 是 ordering authority 对一组 reducer-input Event digest 的签名承诺：`frontier[]` 引用的是这些 Event 的 `event_digest`，`state_root` 承诺的是同一 Anchor view 下所有 cell 经过 Lattice join 后的结果。因此，Event 提供签名事实，Move 是 reducer 对 reducer-input Event 的视图，Anchor 决定哪些 Move 进入 effective set，Lattice 决定这些 Move effects 在每个 cell 上收敛为 value 还是 `⊥`。

状态收敛不由某台服务器的当前数据库决定。任何实现者、客户端、Principal Server、Sync Service 或 federation peer，只要拿到相同的 verified Event bytes、相同的 Anchor DAG / effective anchor view、相同的 Realm schema 与 reducer profile，就 MUST 重算出相同的 effective state、bottom diagnostics 与 `state_root`。服务端可以缓存和加速这个计算，但缓存结果不是协议真相源。

## 3. Move（Reducer-input Event 的协议视图）

"Move" 是 reducer-input Event 在 Lattice/Anchor 层的协议视图，不是独立 wire 对象。Wire schema 只有 signed Event（见 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)），下表给出 Event 与 Move 的字段对应关系：

```text
Move (reducer view of signed Event) {
  event_id        = ck:event:<uuidv7>                 // 来自 Event.event_id（producer-assigned UUIDv7）
  event_digest    = H(canonical bytes excluding proofs and unsigned)
                                                       // 内容指纹；等价于 proof.event_digest
  issuer          DID                                  // 来自 Event.actor_id
  realm_id        Realm id                             // 来自 Event.realm_id
  preconditions   [(cell_id, predicate)]               // 来自 Event.preconditions[]
  effects         [(cell_id, lattice_op)]              // 来自 Event.effects[]
  anchor_ref      Anchor.id                            // 来自 Event.anchor_ref
  refs            [(ref_id, role)]                     // 来自 Event.refs[]
  hlc             advisory timestamp                   // 来自 Event.hlc
  proof           detached JWS                         // 来自 Event.proofs[]
}
```

身份与去重模型（normative）：

- `event_id` 是 producer 在签名前分配的 typed UUIDv7（`ck:event:<uuidv7>`），是 actor chain 与 dedup 的稳定 wire id。它进入 canonical bytes 并被 `proof.event_digest` 覆盖。
- `event_digest` 是 canonical event bytes（不含 `proofs` 与 `unsigned`，包含 `hlc` 与所有其它顶层字段）的哈希，编码为 `<algo>:<hex>`，等价于 `proof.event_digest`。它是 Event 的内容指纹；Anchor `frontier[]` 直接引用 `event_digest`，dot / lattice / hash profile 的引用字段使用 `event_id` 或 `event_digest`。
- 同一 `event_id` 的两次提交若 `event_digest` 不同，节点 MUST 拒绝并记为冲突（见 [`operations-sync.md`](../sync/operations-sync.md) §15）。`event_id` 在签名前由 producer 分配，因此节点不能仅凭 digest 区分 actor 意图；正确实现 MUST 把 (event_id, event_digest) 都纳入 dedup key。

规则：

1. canonical bytes MUST 覆盖 `event_id`、`actor_id`、`realm_id`、`preconditions`、`effects`、`anchor_ref`、`refs`、`hlc` 与所有其它 signed 顶层字段。`proofs` 与 `unsigned` MUST NOT 进入 canonical bytes（它们是对 canonical bytes 的签名或后置 advisory）。`realm_id` 必须进入以防止跨 Realm 重放。
2. `preconditions[]` 与 `effects[]` 是 set；同一 Event 是多 cell 原子 CAS。任一 precondition 不成立时，整个 Event FAIL，MUST NOT 部分应用 effects。`effects[]` MUST 至少含 1 项（纯查询 reducer-input event 不存在）。
3. `anchor_ref` MUST 指向接收方已知的 Anchor DAG 节点，并且相对本地 current anchor view 不超过 Realm 声明的 `max_anchor_staleness_ms`。
4. `refs[]` 是语义依赖，每个元素 `{id, role, critical?}`。常见 role 包括 `authorized_by`、`attestation`、`parent_event`、`after`、`audit_pair`（隐私敏感业务 Event 与 `ck.audit.accessed` 的同 batch 配对）、`recovery_capability`、`state_witness`（§8.1，conflict recovery Event 必备 — 引用签名 snapshot / compaction Anchor）、`inclusion_proof`（§8.1，conflict recovery Event 必备 — Merkle inclusion proof bytes 或 ref）。`critical` 默认 `true`；未识别的 critical role MUST fail closed，未识别的非 critical role MAY 被忽略。`role="authorized_by"` 的 `id` MUST 是 `ck:grant:<uuid>` 或 profile 明确注册的不可变 grant record id；不得引用裸 Event id、policy name、human-readable role 或可变 membership cell。reducer 必须能从该 id 反查 grant canonical digest、issuer、subject、actions、scope、parent grant 链和 revoke/supersede 状态。

   **Critical role 注册表（normative）**：除上列通用 role 外，委托 / 授权链路与 lattice supersession 排序使用以下 role；每个 role 在此显式声明 critical 与否，消除 [`capabilities.md` §10.1 / §10.2](./capabilities.md) 防滚动续期与 cycle detection 依赖“未注册 role”的可实现性缺口（“未识别 critical role MUST fail closed”对这些 role 不再适用，因为它们已注册）：

   | role | critical | 语义与归属 |
   | --- | --- | --- |
   | `parent_grant` | **critical (`true`)** | `ck.capability.delegate` event 指向父 grant id；cycle detection（capabilities.md §10.2）与 revoke 因果传播（capabilities.md §10.3）的图边来源。缺失或不可反查时 delegate Move MUST fail closed。 |
   | `delegation_expiry_anchor` | **critical (`true`)** | 无限期 parent 派生 child 链时冻结的固定到期 anchor（capabilities.md §10.1“固定 anchor 防滚动续期”）。整条 child 链的 `effective_expires_at` MUST ≤ 该 anchor，re-delegate MUST NOT 刷新。携带它的 delegate Move 缺失该 anchor 绑定时 MUST fail closed。 |
   | `auth_frontier` | 非 critical（advisory，`false`） | 记录签发时点 parent `auth_state_digest` / `auth_frontier`，用于审计 child grant 基于哪个 parent policy/frontier 派生（capabilities.md §10.2）。**它不替代实时 revoke/freshness 校验**：缺失时 reducer 仍 MUST 按当前 frontier 重新验证，因此标为非 critical。 |
   | `policy_decision` | 非 critical（advisory，`false`） | 指向一次 `ck.self.policy.check`（默认 path `/_cokret/self/policy/check`）等 policy decision 的诊断引用，仅供审计；**MUST NOT** 被当作授权来源（grant 来源仍以 `authorized_by` 的 grant id 为准，见 capabilities.md §10.3）。缺失可忽略。 |
   | `after` | **critical（用作 supersession 排序边时，`true`）** | 声明跨 batch 的 supersession 边：携带方 Move 取代其指向的 predecessor Move。当被 `mv_register`（§5.3.2）或 `cas_register`（§5.3.3）join 用于 supersession / 链化排序时，该 ref MUST 视为 critical，MUST NOT 按非 critical role 忽略，且 MUST 可反查到已 anchored 的 predecessor Event；缺失或不可反查时该边 MUST NOT 参与排序，受影响 candidate 按并发多 head 处理（确定性 fallback 见 §5.3.2），实现 MUST NOT 静默选边。 |

   advisory（非 critical）授权域 role 的缺失 MAY 被忽略，但实现 MUST NOT 因为存在 `auth_frontier` / `policy_decision` ref 就跳过实时授权校验。
5. `hlc` 是诊断与 freshness 辅助字段，不参与 winner 选择；核心收敛由 Anchor 与 Lattice 决定。
6. Event 的 issuer 只有单签。委员会、多签、host、threshold quorum 均在 Anchor 层表达，不在 Event issuer 层表达。

**Anchor staleness window（normative）**：Realm 字段 `max_anchor_staleness_ms` 是 reducer-input Event `anchor_ref` 相对 receiver 当前 Anchor view 的 Realm 级硬上限。`realm.schema.json` 的默认值 86,400,000 ms（24h）只用于低风险离线写入 / 兼容性兜底；实现和部署 MUST NOT 把该默认值理解为所有写入的推荐 freshness window。接收方计算某个 Move 的有效 staleness window 时 MUST 取下列约束的最小值：

```text
effective_anchor_staleness_ms =
  min(
    Realm.max_anchor_staleness_ms,
    action / capability freshness window if declared,
    cell-family or cell-role freshness window if declared,
    deployment / profile override if declared
  )
```

若 `M.anchor_ref` 超过该有效窗口，receiver MUST 以 `anchor_ref_stale`（或等价 `failed_precondition` reason）拒绝或 quarantine 该 Move；producer SHOULD rebase 到最新可验证 Anchor view 并重新签名，而不是把过旧 Move 继续推入 Anchor pipeline。

推荐窗口（informative defaults）：

| 写入类别 | 推荐有效窗口 |
| --- | --- |
| 高频协作 UI（`ck.flow.move` / `ck.flow.reorder` / reaction 等） | 30s–5min |
| 普通内容写入（message / comment / non-critical field patch） | 5–30min |
| 弱网 / 移动端离线队列（低风险，提交前可自动 rebase） | 30min–2h |
| 低频审计 / sovereign backfill / regulated diagnostic write | 6–24h |
| 高风险或安全根 cell（`anchorer_root` / authorization / policy / membership / lifecycle） | MUST NOT 只依赖 24h 上限；MUST 按 capability freshness / policy freshness / profile gate 使用更短窗口，通常为分钟级或要求 current frontier fresh |

`max_anchor_staleness_ms` 不是恶意多 anchorer / 多 leaf 冲突放大的完整防线。`open_set` / `threshold` / federation profile 还 MUST 依赖 peer health、stale-peer quarantine、range completeness / witness、rate limit、compaction cadence 与 capability revocation 来限制攻击者用旧 basis Move 反复制造 `⊥`。缩短 staleness window 只能降低旧状态 Move 被接受的时间窗口，不能替代 signer 治理与 abuse control。

### 3.1 Predicate

核心 predicate（wire 字段 `{op, value?, values?, predicate_id?}`，schema 见 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json) `predicate`）：

| `op` | 必填字段 | 语义 |
| --- | --- | --- |
| `head_eq` | `value` | 当前 cell value / head 必须等于指定值。单 cell basis 是该 predicate 的特例。 |
| `head_in` | `values` | 当前 cell value / exposed heads 必须属于集合。用于冲突修复 Move。 |
| `satisfies` | `predicate_id` | 当前 cell value 必须满足 schema 注册的 deterministic predicate（按 `predicate_id` 派发到该 cell schema 声明的可验证 predicate 实现）。仅允许引用封闭 Lattice 可验证的字段。 |
| `contains` | `value`（单元素）或 `values`（子集检查） | 当前 set / OR-set / covered frontier 必须包含指定元素或 frontier subset。 |

Predicate MUST NOT 读取本地数据库顺序、HTTP 到达时间、未签名服务端状态或外部 wall clock。

### 3.2 Effect

Effect 的 `lattice_op` 必须与目标 cell 的 Lattice type 兼容。`lattice_op` 的 wire 字段为 `{kind, tag?, value?, from?, to?, reason?, issuer_seq?}`（schema 见 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json) `lattice_op`）：

| Lattice type | `op.kind` | 必填字段 | 可选字段 |
| --- | --- | --- | --- |
| `or_set` | `add` | `tag`、`value` | — |
| `or_set` | `remove` | `tag` | `reason` |
| `mv_register` | `set` | `value` | — |
| `cas_register` | `set` | `value` | — |
| `fsm` | `transition` | `from`、`to` | `reason` |
| `counter` | `inc` / `dec` | `value`（非负整数增量） | `tag`（per-counter 维度） |
| `ordered_log` | `append` | `value`（entry payload）、`issuer_seq` | — |

`op.value` 与 entry payload 必须满足该 cell schema；接收方 MUST 拒绝多余字段（`additionalProperties=false`）。

同一 Move MAY 写多个 cell。Realm schema MAY 声明 `co_write_policy` 限制哪些 cell family 可以同 Move 写入；违反时 Move MUST `schema_violation` reject。

## 4. Anchor

Anchor 的 wire schema 见 [`anchor.schema.json`](../../artifacts/schemas/anchor.schema.json)。Normative 形态：

```text
Anchor {
  id                 = "ck:anchor:" || <algo> || ":" || hex(H(anchor_canonical_bytes))
  realm_id            Realm id
  predecessor_refs    [Anchor.id]
  frontier            [event_digest]              // hash of each covered reducer-input Event's canonical bytes
  state_root          hash
  anchorer_signature        sig | multi_sig | threshold_sig    // signature over anchor_canonical_bytes
  anchored_at         RFC3339 UTC timestamp signed by anchorer
  hlc                 advisory timestamp
}
```

身份与去自引用模型（normative）：

- `id` 是 Anchor 的 wire-stable typed reference，形态为 `ck:anchor:<algo>:<hex>`。它的 hex 部分等于 `H(anchor_canonical_bytes)`，hash algo 跟 Realm `digest_algorithm`。`id` **不**进入 `anchor_canonical_bytes`——它在 wire 上是 H 的输出而不是输入，所以不会形成 `id = H(... id ...)` 自引用。
- `anchorer_signature` **不**进入 `anchor_canonical_bytes`：anchor 签名覆盖 canonical bytes，本身不是 canonical bytes 的成员。
- canonical bytes 由下表"transcript fields"列出的字段按 canonical JSON 编码（[`conformance/encoding.md`](../conformance/encoding.md) §2）形成，**不含** `id` 与 `anchorer_signature`，**包含** `realm_id` / `predecessor_refs` / `frontier` / `state_root` / `anchored_at` / `hlc` 与所有其它 signed 顶层字段（如 hash transition 下的 `previous_state_root` / `previous_digest_algorithm`）。

| 字段 | canonical bytes | anchorer_signature transcript | 来源 |
| --- | --- | --- | --- |
| `id` | excluded: H output | excluded | wire-derived |
| `realm_id` | included | included | anchor body |
| `predecessor_refs` | included | included | anchor body |
| `frontier` | included | included | anchor body |
| `state_root` | included | included | anchor body |
| `previous_state_root` (transition only) | included | included | anchor body |
| `previous_digest_algorithm` (transition only) | included | included | anchor body |
| `anchored_at` | included | included | anchor body |
| `hlc` | included | included | anchor body |
| `anchorer_signature` | excluded: covers canonical bytes | excluded: does not sign itself | wire signature |

接收方 verifier MUST：

a. 从 wire 收到的 Anchor 中提取 `anchor_canonical_bytes`（按上表）。
b. 重新计算 `H(anchor_canonical_bytes)` 并校验 `id` 的 hex 部分逐字节相等；不一致 `digest_mismatch`。
c. 用 `anchorer_signature` 的公钥验证签名覆盖的是 `anchor_canonical_bytes`（不是 `id`、不是其它派生形态）；不一致 `invalid_signature`。
d. 同一 wire bytes 在重排键顺序、注入额外 proof 字段或更换 `anchorer_signature` 后 hash 不变是 attack；canonical JSON + `additionalProperties=false` + 上表显式排除清单确保 attack 必然在 (b) 或 (c) 失败。

规则：

1. `predecessor_refs=[]` 仅允许 Genesis Anchor。Genesis Anchor MUST 同时满足 `frontier=[]`；它表示该 Realm Anchor DAG 的根基线，不覆盖任何 Move。任何 `predecessor_refs=[]` 但 `frontier` 非空的 Anchor MUST `schema_violation` / reject。
2. 单调性：`A.frontier` MUST 是所有 predecessor frontier 的 superset。
3. Anchor 是持久承诺；它不修改 cell。Cell 变化只来自 frontier 内 Move 的 effects。
4. `anchorer_signature` 的合法签发者由 anchorer cell 在 predecessor joined view 下的 effective value 决定。
5. `state_root` MUST 是该 Anchor view 下所有 cell 当前 Lattice value / bottom diagnostics 的 canonical Merkle root。
6. `anchored_at` MUST 由 anchorer 写入并被 `anchorer_signature` 覆盖。它只用于 freshness 诊断和 `state_changed_at` 等 reducer-derived 投影时间，MUST NOT 参与 Lattice winner 选择。
7. 负向：任何尝试把 `id` 或 `anchorer_signature` 放进 canonical bytes 的实现 MUST 失败（test 见 §4 Anchor canonical 负向向量条目）；frontier 中含非 `<algo>:<hex>` 形态（例如 `ck:event:<uuid>`）的 Anchor MUST `schema_violation`。

### 4.1 Anchor View 与 Signed Compaction

多个 Anchor leaf 并存时，节点 MUST 计算 deterministic effective anchor view：

```text
effective_anchor_view(leaves):
  predecessor_refs = sorted(leaves.ids)
  frontier         = union(leaves.frontier)
  state_root       = recompute(frontier)
```

该 view 是本地纯函数，不需要签名，也不是新的 Anchor object。只有当 anchorer / committee 想压缩 Anchor DAG 时，才签发一个持久 compaction Anchor。Compaction Anchor 的 `frontier` 与 deterministic view 等价，并带有效 `anchorer_signature`。

Anchor view 的计算者可以是任何 verifier。`single_did` profile 下，单一 anchorer 负责签发通常的线性 Anchor；`threshold` / `open_set` profile 下，多个服务或 peer 可以产生 leaf Anchor。无论拓扑如何，接收方都不能直接相信远端声称的物化状态：它必须拉取 Anchor frontier 覆盖的 Event bytes，按 §6 验证 Move，再按 §5 Lattice 规则重算 `state_root`。若本地缺少 frontier 中的 Event 或重算 root 与 Anchor `state_root` 不一致，该 Anchor 不得进入 effective state，只能 backfill、quarantine 或 reject。

### 4.2 `state_root` Canonical Merkle 编码

§4 rule 5 要求 `state_root` 是该 Anchor view 下所有 cell value / bottom 的 canonical Merkle root。本节锁定具体编码以保证不同实现互通。

State root 使用的 hash 算法由 Realm 的 `digest_algorithm`（create-locked，默认 `sha256`）决定。本节伪代码以 `H(...)` 表示该 algo 的哈希函数；wire 上 hash value 形如 `<algo>:<hex>`，详见 [`encoding.md`](../conformance/encoding.md) §3。

#### 4.2.1 Leaf 编码

每个有过 effect 的 cell 一条 leaf：

```text
leaf_input = canonical_json({
  "cell":  "<CellRef wire string>",
  "state": <state_object>
})
leaf_digest  = H(0x00 || leaf_input)
```

`<state_object>` 取决于 cell 当前 join 结果：

| Lattice 结果 | `state_object` |
| --- | --- |
| `Value(v)` | `{ "value": v }` |
| `Bottom(b)` | `{ "bottom": <Bottom canonical JSON, **省略 `anchor_view` 字段**> }` |

`bottom.anchor_view` 必须省略，因为 state_root 自身已经定义于一个具体的
Anchor view，把同 view 写进 leaf 会造成自引用并破坏 root 的稳定性。
`bottom` 的其他字段（`kind` / `cells[]` / `event_ids[]` / `heads[]` / `details` /
`escalated_at`）保留进 leaf——它们是该 cell 在该 view 下状态的一部分，跨 view
可能不同，是 state_root 必须捕获的差异。

`state_root` leaf MUST NOT 包含 `batch_index`、Anchor 内接收顺序、本地数据库序号或其它历史排序字段。`state_root` 只承诺该 Anchor view 下的 **当前 cell state**；历史顺序与完整性由 Anchor `frontier[]`、actor chain `(actor_id, actor_seq)`、range completeness attestation 或 event-set commitment 承诺。两个 Anchor view 若归约出完全相同的 cell map，必须得到相同 `state_root`，即使其 Move 被不同批次或不同接收顺序合入。

#### 4.2.2 树形

1. 收集该 Anchor view 下所有有过至少一次 effect 的 cell。
2. 对每个 cell 计算 `leaf_digest`（4.2.1）。
3. 把 `(cell_wire, leaf_digest)` 元组按 `cell_wire` Unicode code point 升序排序。
4. 把排序后的 `leaf_digest` 列表按 RFC 6962 domain-separated binary Merkle tree 算 root：
   - 偶数个：两两配对 `parent = H(0x01 || left || right)`，逐层向上。
   - 奇数个：最后一个 leaf 直接提升到上一层（**不复制**）。
   - 单个 leaf：root = leaf_digest。
   - 空列表：root = `H("")` 用 algo 的空字节摘要值。
5. wire 形式：`state_root = "<algo>:" + lower_hex(root)`，`<algo>` 即 Realm `digest_algorithm`。

#### 4.2.3 增量重算

实现 SHOULD 缓存 cell → leaf_digest 表，在 `apply_anchor` 接受新 Anchor 后只
重算受影响 cell 的 leaf 与所属 Merkle 分支；wire 上的 `state_root` 必须等于
全量重算结果。等价性由 conformance vector
[`ck.vector.state_root.incremental.v1`](../conformance/conformance-vectors.md)
（§2.9）固定，覆盖单 cell 修改、半数修改、全量修改、空 frontier 与 schema-evolution
（新增 cell + 删除旧 effect）共四个 case；增量结果与全量重算 MUST bit-exact 一致。

#### 4.2.4 跨实现互通

不同 conformant 实现处理同一 Move/Anchor 历史 MUST 产出相同 state_root。
偏离上述编码（不同 leaf shape、不同 tree 形、不同空 list 处理、错误的 hash algo）即视为
v1 wire-incompatible，必须用独立 profile 声明。

#### 4.2.5 Digest Suite Transition（hash / canonicalization）

Realm 一旦在 create event 中固定 `digest_algorithm`（取值为 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json) 的 active **digest suite** id，即 canonicalization × hash 元组，见 [`encoding.md`](../conformance/encoding.md) §3.1–§3.3），所有后续 Anchor / Move / state_root MUST 用同一 suite。需要切换 suite——无论是 hash 分量升级（例如 sha256 → blake3 性能升级、→ 抗量子 hash family），还是归一化编码分量切换（例如 canonical JSON → deterministic CBOR，即 `sha256` → `cbor.sha256`）——时：

1. **Transition Anchor**：anchorer 签发一个特殊的 compaction Anchor，其 wire 字段同时携带 `previous_state_root`（旧 suite）和 `state_root`（新 suite）。Receiver 按旧 suite 的完整定义（旧归一化 + 旧 hash）重算 frontier 验证 `previous_state_root` 与本地一致；按新 suite 的完整定义重算同 frontier 验证 `state_root`。两者都通过才能 accept transition Anchor。
2. **`digest_algorithm` cell update**：transition Anchor 的 frontier 包含一个 Move 把 Realm 的 `digest_algorithm` cell（`cas_register, bottom=reject`）从旧值 `head_eq=<old>` 改为 `set=<new>`。
3. **后续 Anchor**：新 anchor 只用新 suite。客户端做长历史 inclusion proof 时，跨 transition Anchor 的 proof 由 transition Anchor 的双 root 桥接——proof 在 transition 之前用旧 suite 验证，之后用新 suite 验证。transition 之前已签名的历史 bytes 不被改写（签名字节不可变根约束）。
4. **hash 分量禁止降级**：suite 的 hash 分量只允许从更弱 algo 升级到更强 algo（按 digest-suite registry `hash_strength_order` 声明的顺序），MUST NOT 降级。v1 order：`sha256 < blake3` 在性能侧；安全侧 v1 视为同等抗碰撞强度。未来加法注册 algorithm-diversity 或抗量子 hash 时该 order 随 registry 扩展。
5. **归一化分量横向切换**：canonicalization 分量之间无强弱序，切换是横向迁移，前提是新旧 suite 在 registry 中均为 active、且目标 suite 的 encoding profile（如 `ck.profile.encoding.cbor.v1`）已被 Realm 的参与方声明。单次 transition MAY 同时切换两个分量，但 hash 分量仍受第 4 条约束。

实现不强制支持 suite transition；声明 `ck.profile.hash_transition.v1` 的实现 MUST 支持（该 profile 覆盖两类分量的切换，profile id 沿用历史名）。这条机制保证了未来 digest 定义升级路径不需要硬分叉。

### 4.3 Anchor Batch 语义

`apply_anchor(A)` MUST 按批处理语义执行：

```text
pre_state = joined_state(A.predecessor_refs)
new_moves = A.frontier - union(predecessor.frontier)

for M in deterministic_order(new_moves):
  if verify_move(M, pre_state) fails:
    reject A with rejected_anchor(reason=move_verification_failed)

post_state = apply_all_effects_atomically(pre_state, new_moves)
assert merkle_root(post_state) == A.state_root
```

同一 Anchor 内的 `new_moves` 视为并发批。一个 Move MUST NOT 通过读取同批另一个 Move 的 effect 满足 precondition。若需要顺序，提交方 MUST 分成多个 Anchor，或在 `refs(role="after")` 中声明并由 anchorer 按下一 Anchor 处理。

Anchor frontier 是 all-or-nothing：anchorer MUST NOT 把在 batch pre-state 下无法通过 `verify_move` 的 Move 放入 frontier。Receiver 发现任一 `new_moves` 校验失败时 MUST 拒绝整个 Anchor；失败 Move 的 effects 不进入任何 cell `join()` 输入、不进入 `state_root`，也不得被标为 `effective`。节点 MAY 把这些 Move 保留为 pending / diagnostic 输入，但必须等生产者重新基于有效 Anchor frontier 提交。

同批配对 invariant 是例外形式的**批级验证**，不允许读取同批 effect：若业务 Event 携带 `refs[role="audit_pair"]`，anchorer / reducer MUST 在应用任何 effect 前验证该 ref 指向同一 Anchor batch 内的 `ck.audit.accessed` event，且 audit payload 的 `paired_event_id` 与 `paired_event_digest` 回指该业务 Event。配对失败时拒绝业务 Event；audit Event 自身仍可按普通 durable Event 入库，供失败审计和告警使用。该规则用于 `ck.flow.watch.set.others` 等 fail-closed 隐私门槛，不改变 precondition 读取模型。

### 4.4 Anchorer Cell

每个 Realm 有一个 anchorer cell：

```text
cell = ck:cell:ck.component.anchorer.v1:<realm_id>
lattice = cas_register
bottom = reject
```

它的 value 定义下一批 Anchor 的授权规则，例如：

- `single_did`: 单一 DID / service key。
- `threshold`: k-of-n committee。
- `open_set`: 允许集合内任一 DID 签发 leaf Anchor，DAG join 后收敛。
- `mixed`: 主 anchorer + fallback recovery anchorer。

**Canonical wire 形态（normative）**：anchorer cell value 的唯一合法 wire 形态与 Realm create payload 的 `anchorer` 字段一致（权威 schema：[`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `anchorer`，封闭 schema）——以 `type` 为标签的对象：

| `type` | 必填字段 | 说明 |
| --- | --- | --- |
| `single_did` | `did`（genesis 时还需 `recovery_members` / `controller_organization` / `recovery_controller_organizations`） | 单一 anchorer |
| `threshold` | `members[]`、`threshold` | k-of-n committee（k=`threshold`，n=`members` 长度） |
| `open_set` | `members[]` | 开放集合 |
| `mixed` | `did`、`recovery_members[]` | `did` 为主 anchorer，`recovery_members` 为 fallback |

该形态贯穿 genesis payload、anchorer cell 的 effective value 以及任何管理/产品面 API 对该 value 的下发。实现 MUST NOT 在 wire 上使用别名拼写——包括标签字段写作 `kind` / `kind_raw` / `shape`，阈值写作 `k` / `n`，或扁平化的 `single_did` / `threshold_dids` / `mixed_primary` / `mixed_recovery` 等字段名；读取端对这类别名 SHOULD 拒绝而非容错，避免多套拼写在生态内固化。

变更 anchorer 是普通 Move，由旧 anchorer 签发的后续 Anchor finalize；新 anchorer MUST NOT 自签自己上位。

如果 anchorer cell 在某个 effective view 下为 `⊥`，Anchor 层进入 Realm-wide pause：普通 Anchor MUST NOT 推进，只有 genesis 声明的 recovery anchorer / emergency quorum MAY 签发恢复 Anchor。该暂停不同于普通 cell-scoped bottom，MUST 在 API / UX 中明确暴露。

## 5. Lattice

每个 cell family 在 Realm schema 或 canonical registry 中声明：

```text
Lattice {
  type        ∈ closed_core_set
  bottom      ∈ {reject, expose}
  parameters  type-specific
}
```

v1 封闭核心集（core）：

| Type | Join 语义 | 用途 | 授权层禁用 |
| --- | --- | --- | --- |
| `or_set` | observed-remove set；add/remove 通过唯一 tag 收敛。 | capability grant set、device list、凭证撤销集合。 | — |
| `mv_register` | 并发 set 暴露多值；无单一 winner。 | 非安全草稿、可人工选择的偏好。 | MUST NOT 作授权根 |
| `cas_register` | 严格 CAS；并发不同值返回 `⊥`。 | anchorer、关键 singleton policy、host 指针类状态。 | — |
| `fsm` | 状态机迁移；非法迁移或并发不可合并迁移返回 `⊥`。 | membership、lifecycle、invite/approval。 | — |
| `counter` | PN-counter 求和。 | 配额、审计计数。 | — |
| `ordered_log` | append-only log；按 issuer chain 与 entry id 去重。 | 审计、消息历史、不可变操作日志。 | — |

依赖 actor 自报 timestamp 排序的 join、HTTP receive order、数据库自增 ID 均 MUST NOT 进入协议授权根。

Lattice type 分两层，授权语义与可用性截然不同；实现 MUST 按下表区分对待：

| 分层 | type | 可用性 | 授权层定位 |
| --- | --- | --- | --- |
| **core 封闭集**（无条件可用） | `or_set` / `mv_register` / `cas_register` / `fsm` / `counter` / `ordered_log` | v1 base profile 一律 MUST 实现 | 可作授权 / policy / membership / anchorer cell（`mv_register` 除外，见上表「授权层禁用」列） |
| **profile-gated 扩展集** | `lww_register` / `rga` | 仅当声明 [`ck.profile.collaborative_text.v1`](../conformance/conformance-profiles.md) 时可用；未声明的实现遇到这两种 type MUST fail closed（`unsupported_lattice_type`） | **MUST NOT 作授权 / policy / membership / anchorer / capability cell 根**；只用于 content / cosmetic cell（语义见 §5.0.1） |

core 集是 `Lattice.type ∈ closed_core_set` 的封闭代数；扩展集不进入该封闭集，其 join / validate 语义集中定义在 §5.0.1 与 §5.3.7 / §5.3.8。

Lattice 的作用不是让并发冲突消失，而是让同一输入集合的结果确定。对可合并类型（如 `or_set`、`counter`、`ordered_log`），所有 verifier 会得到同一个合并值；对不可安全自动选择的类型（如关键 `cas_register`、部分 `fsm`），并发或非法状态会收敛为同一个 `⊥`，而不是由某台服务器、HLC、actor id 或接收顺序挑一个 winner。依赖 `bottom=reject` cell 的后续 Move 必须 fail closed，直到 §8 的 conflict-recovery Move 把该 cell 恢复到明确 value。

例如两个客户端基于同一旧 Anchor 同时把同一个 Flow 移到不同 List，二者都生成合法 signed Event / Move。如果这两个 Move 进入同一 effective Anchor view，`ck.component.flow.position.v1` 的 `cas_register` join 会在所有 verifier 上返回同一个 conflict bottom；正确实现不得在 server A 显示 List-1、server B 显示 List-2 作为最终协议状态。它们可以在 projection 层展示冲突诊断或本地 pending UI，但共享 effective state 必须是同一个 `⊥`，并要求后续 recovery Move 修复。

#### 5.0.1 扩展 Lattice：`lww_register` / `rga`

`lww_register` 与 `rga` **不属于** v1 core 封闭集；它们由扩展 profile [`ck.profile.collaborative_text.v1`](../conformance/conformance-profiles.md) 引入，目的是支持协作文本与 cosmetic 字段。声明该 profile 的实现 MUST 完整实现下列 §5.3.7 / §5.3.8 中的 join 与 validate 语义；未声明的实现遇到使用这两种 type 的 cell schema MUST fail closed（`unsupported_lattice_type`）。

| Type | Join 语义 | 用途 | 授权层禁用 |
| --- | --- | --- | --- |
| `lww_register` | 按 anchor-derived order 选最近 set；同 anchor batch 并发用 deterministic tiebreaker。 | UI affordance：Flow `metadata.title` / `metadata.summary`、Morph 非关键字段、 emoji shortcuts、cosmetic preferences。 | **MUST NOT 作授权、policy、membership、anchorer、capability cell**。schema 静态拒绝。|
| `rga` | Replicated Growable Array：插入 op 携带 `(predecessor_id, element_id=issuer:seq)`，删除 op 写 tombstone；按 (anchor index, issuer, seq) 全序确定性合并。 | 协作文本编辑（Flow.content 富文本、Morph 文档段、Markdown 块的字符级编辑）、可插入的有序列表。 | **MUST NOT 作授权根**；只用于 content cell。|

`lww_register` 与 `rga` 的"时间"由 Anchor 批次索引与批次内确定性 tiebreaker 提供，**不**读取 actor 自报 HLC 或外部 wall clock。这是它们被允许出现在 conformance core 之外但仍是封闭代数的前提。

> **路线图注记（informative，2026-06 评审采纳）**：`rga`（2011）的已知短板是并发同位插入的 interleaving 异常（两段并发输入可能逐字符交错）与长历史 tombstone 增长。下一代候选方向：**Fugue**（interleaving-free 性质已形式化，并证明 RGA 不满足）与 **eg-walker**（event-graph 重放式，与 Cokret"Event 是事实日志、状态是重放投影"的模型天然同构，可直接消费 Move/Anchor event graph）。引入机制已就绪——新 lattice type 走本节既有的 profile-gated + `unsupported_lattice_type` fail-closed 加法路径，完全向后兼容。本注记不预占 type 名或 profile id；待选型验证（Fugue 纯 CRDT vs eg-walker 重放式）有实现结论后再注册。

### 5.1 Bottom Diagnostics

协议判断只区分 value 与 `⊥`，但实现 MUST 保留结构化诊断（wire schema 见 [`bottom.schema.json`](../../artifacts/schemas/bottom.schema.json) `ck.schema.bottom.v1`）：

```text
Bottom {
  kind         ∈ {conflict, invalid_transition, missing_dependency,
                  unauthorized, anchorer_split, schema_error}
  cells[]      cell_ids 参与诊断（多 cell 原子 Move 失败时 >1）
  event_ids[]   anchored reducer-input Event ids 触发该诊断（结构性 ⊥ 可为空）
  anchor_view? {leaves[], state_root?} 观察该 ⊥ 的 Anchor view，便于复算
  heads[]?     kind=conflict 时候选 head 值；UI / 审计可见，授权 MUST NOT 据此选 winner
  details?     kind-specific structured details
  escalated_at? 跨过 Realm.bottom_escalation_after_ms 时的时间戳
}
```

`bottom=reject` 的 cell 被普通 Move precondition 读取时，Move MUST fail closed（state code `failed_bottom`），错误至少包含 `cells[]` 与 `event_ids[]`。唯一例外是 §8 / §8.1 定义的 conflict-recovery Move：当 Move 同时携带有效 `state_witness`、`inclusion_proof`、recovery capability，并且其 predicate 只读取 witness 暴露的冲突 heads 时，verifier MUST NOT 在 predicate 求值前触发 `FAIL_BOTTOM`，而是按 §8 的 recovery 流程对 exposed heads 求值。`bottom=expose` 的 cell MAY 返回 `{status:"conflict", heads:[...]}` 给 projection；它 MUST NOT 被授权路径当作 allow。

`bottom=reject` 不是可被普通 CAS 写入直接覆盖的临时值。只要当前 effective view 下 cell value 为 `⊥`，任何普通 Move（包括携带 `head_eq` 的 cas_register set）读取或写入该 cell 时都 MUST `failed_bottom` / `failed_precondition`，`reason_code=cell_in_bottom_state`；实现不得把 `⊥` 当作 `null`、空 head 或任一候选 head。修复只能通过 §8 的 conflict-recovery Move 完成：该 Move MUST 引用冲突前 `state_witness`、`inclusion_proof` 与被授权的 recovery capability，并在新的 Anchor view 中把 cell 收敛到明确 value。若某 cell family 需要更专门的 recovery 事件，profile 可以在自己的 event kind 上定义 payload，但不能绕过本段的 witness 与 capability 要求。

`anchorer_split` 是特殊 kind：当 anchorer cell（cas_register, bottom=reject）出现并发 set 时该诊断生效；它对应 §13 的 `anchorer_paused` Realm 状态，仅 recovery anchorer / emergency quorum 签发的 Anchor 可恢复推进。

#### 5.1.1 Bottom 影响范围

`⊥` 是 cell state，不是默认的 Realm state。实现 MUST 按依赖闭包决定影响范围，MUST NOT 因为任意业务 cell 进入 `⊥` 而停止整个 Realm 的 Anchor 推进。

| 范围 | 触发 | 结果 |
| --- | --- | --- |
| Cell-local bottom | 普通业务 cell 在当前 effective view 下为 `⊥`，例如 `ck.component.flow.position.v1:<board_space_id>:<flow_id>`。 | 读取或写入该 cell 的普通 Move MUST fail closed；同一对象的其他独立 cell、其他对象和 Realm Anchor 推进不受直接影响。Projection MAY 把该字段显示为 conflict。 |
| Dependency bottom | 授权、policy、membership、capability、lifecycle 等治理 cell 为 `⊥`，并且某个 Move 的 precondition / authz check / reducer invariant 需要读取它。 | 依赖该 cell 的 Move MUST fail closed。这可能阻塞大量业务写入，但它仍是依赖链阻塞，不等同于 Anchor 层 Realm-wide pause。 |
| Realm-wide Anchor pause | `ck:cell:ck.component.anchorer.v1:<realm_id>` 为 `⊥`（`anchorer_split`）。 | 普通 Anchor MUST 停止推进；只有 genesis 声明的 recovery anchorer / emergency quorum MAY 签发恢复 Anchor。 |

Flow position 冲突的影响是第一类：该 Flow 的 canonical placement 未决，后续普通 position Move 不能继续；Flow 的 `metadata.title` / content / comments / watch 等独立 cell 仍可按各自 Lattice 和授权规则继续更新，其他 Flow 的更新也 MUST NOT 被阻塞。只有当某个后续 Move 显式读取该 position cell（例如“只允许移动当前位于 List-X 的 Flow”）时，才因 `cell_in_bottom_state` fail closed。

`bottom_escalation_after_ms` 只改变告警和 recovery 提示，不会把普通业务 cell 的 `⊥` 自动升级成 Realm-wide pause。Realm lifecycle 的 terminal state（例如 tombstoned / destroyed）属于 lifecycle reducer 语义，见 [`realm-and-space.md`](../models/realm-and-space.md)，不是本节定义的 Lattice bottom pause。

**Lattice type 与 bottom 行为对照**：

| Lattice type | bottom 是否出现 | bottom 配置语义 |
| --- | --- | --- |
| `or_set` | 永不 | bottom=expose 仅用于多 head 场景的 add/remove 并发可视化 |
| `mv_register` | 永不 reject；多值即 expose | bottom=expose 是常态：projection 暴露多个 head 给 UI，授权路径 MUST NOT 据此选 winner |
| `cas_register` | 出现：并发不同 set + 不同 basis 时返回 ⊥（非初始态缺 `head_eq` 的盲写在 verify_move 阶段即 `failed_precondition`，不进入 join，见 §5.3.3 Basis 强制） | bottom=reject 是标准（anchorer / 关键 singleton）；依赖该 cell 的 Move fail closed |
| `fsm` | 出现：非法 transition / 并发 divergent next_state 时返回 ⊥ | bottom=reject 是标准（membership / lifecycle / invite-approval）|
| `counter` | 永不 | bottom=expose 仅在配额跨界等场景作诊断 |
| `ordered_log` | 永不 | bottom=expose 用于审计、消息历史；并发 append 不阻塞 |
| `lww_register` | **永不出现于 value path**——并发 sibling 由 §5.3.7 deterministic tiebreaker 选 winner | bottom=expose 仅由诊断层暴露 lost siblings；**授权层 MUST NOT 据此选 winner**（schema 已静态禁止 lww_register 作授权根）|
| `rga` | **永不**——RGA 总有合法 deterministic order | bottom=expose 用于把并发 insert/delete 多值反馈给 projection，不阻塞协议判断 |

### 5.2 序内因果

Lattice `join()` 输入是 Move set，而不是本地接收序列。需要顺序语义的 type 必须把顺序编码进 op：

- `fsm` 通过 `transition.from` / `transition.to` 校验路径。
- `ordered_log` 通过 `issuer_seq`、`parent_entry` 或 entry hash 链校验 append。
- `cas_register` 通过 Move precondition `head_eq` 表达 basis。

若某 lattice type 对同一输入 set 不能给出 deterministic value / bottom，则该 type 的实现不符合 v1。

### 5.3 Lattice 参考实现

下列伪代码为各核心 Lattice type 的 normative `join()` 与 `validate_op()` 行为；参考向量在 [`conformance-vectors.md`](../conformance/conformance-vectors.md) §2。

#### 5.3.1 `or_set`

真正的 observed-remove set，按 **dot** 收敛。

- 每个 add op MUST 携带 `dot = "<event_id>:<effect_index>"`，由 add op 所在 Event 的 wire `event_id`（typed `ck:event:<uuidv7>`）与该 effect 在 `effects[]` 中的 0-based 下标拼接而成。`event_id` 已经全局唯一，dot 因此天然唯一。当需要在 dot 之上做内容指纹比对（例如对照 Anchor frontier）时使用 `event_digest` 作为辅助键，但 dot 自身只用 `event_id`。
- 每个 remove op MUST 携带 `observed_dots: [dot, ...]`——它枚举 remove issuer 在 enclosing Event 的 `anchor_ref` 对应 pre-state 下能看到的、想要撤销的具体 add dot。`observed_dots` MUST 升序去重，且每条 dot 必须能在该 anchor view 下解析为合法 add op。
- Add op MAY 在 `value` 内嵌入 schema-defined `intent` 字段（例如 consent 的 `(consent_id, peer, scope)` 元组）。`intent` 不参与 lattice join；它只是 projection 层把同 intent 的多 dot 折叠成一条 UI/审计行的辅助数据。

```text
join(moves) -> Set<(dot, value)>:
  adds          = { (eff.dot, eff.value)
                    | M ∈ moves, eff ∈ M.effects, eff.op.type=="add" }
  observed_dots = ⋃ { set(eff.observed_dots)
                      | M ∈ moves, eff ∈ M.effects, eff.op.type=="remove" }
  return        { (d, v) ∈ adds | d ∉ observed_dots }

validate_op(op):
  op.type ∈ {add, remove}
  if add:
    op.dot      == "<enclosing_event.event_id>:<effect_index>"
    op.value satisfies schema
  if remove:
    op.observed_dots is a finite, sorted, deduplicated list of dot strings
    each dot in op.observed_dots resolves to an add effect
      visible at enclosing Event's anchor_ref pre-state
```

**Regrant 语义**：先 add(d1)、再 remove(observed=[d1])、再 add(d2) 是合法序列；d2 的 dot 不在任何 `observed_dots` 中，因此 join 后 d2 仍 active——regrant 是显式支持的。

**Idempotency**：dot 由 `event_id` 派生（`event_id` 在签名前由 producer 分配的 typed UUIDv7），因此相同 add op 跨节点重放不产生重复 dot，但不同 issuer 对同一 intent 的并发 add 会产生不同 dot——这是 OR-Set 的预期行为，去重落在 projection / 授权判定（"intent 是否当前 active = 该 intent 下 ≥1 dot 仍在 join 集合"）。

**部分撤销**：remove op 只 invalidates 它枚举的 dots。撤销整个 intent 需要 issuer 列出该 intent 下当前所有 active dots；missing 一些就只是部分撤销，剩余 dot 仍 active。这是 OR-Set 的 normative 语义，不是 bug。

`bottom` 永远不出现（or_set 总有合法 join 值）。`bottom=expose` 仅用于 projection 在多 head 场景把 add/remove 并发可视化，不影响协议授权判断。

#### 5.3.2 `mv_register`

Multi-value register。所有未被后续 set 取代的并发值都暴露。

```text
join(moves) -> Set<value>:
  candidates = { (M.event_digest, eff.value) | M ∈ moves, eff ∈ M.effects, eff.op.type=="set" }
  // 取因果最大集：去掉被任何后继 Move 偏序覆盖的 candidate
  return  { v | (m, v) ∈ candidates, ¬∃(m', _) ∈ candidates: m' > m via Move.refs("after") }

validate_op(op):
  op.type == "set"
  op.value satisfies schema
```

**Supersession 偏序（normative）**：join 中 `m' > m` 的偏序按下列规则定义：

- **基础边**：candidate Move A 携带 `refs[role="after"]` 指向 candidate Move B（以 B 的 `event_id` / `event_digest` 引用）时，记 A > B。该边仅当 A、B 均已 anchored、且 B 可在本地反查到对应 Event 时成立（见 §3 critical role 注册表 `after` 行）。
- **传递闭包**：`>` 取上述基础边的传递闭包——A `after` B、B `after` C ⇒ A > C，即 A 同时覆盖 B 与 C。
- **断链语义与确定性 fallback**：链上任一 predecessor 缺失、未 backfill 或不可反查时，缺失边 MUST NOT 参与闭包计算；受其影响的 candidate 按并发处理，全部保留为 exposed heads（退化为多 head expose）。实现 MUST NOT 因为部分链可达就静默选边，也 MUST NOT 用 HLC、接收顺序或 issuer id 补序；predecessor backfill 之后按同一规则确定性重算。

`bottom=expose` 是 mv_register 的常态：projection 以 `{status:"conflict", heads:[...]}` 暴露多值。授权路径 MUST NOT 用 mv_register 表达。

#### 5.3.3 `cas_register`

Compare-and-swap register。Move 通过 precondition `head_eq` 声明 basis；并发不同 set 返回 `⊥`。Move 的因果序由 (a) Anchor batch 包含关系，与 (b) 跨 batch 时 `Move.refs(role="after")` 显式声明给出（`after` 边的偏序、反查与断链 fallback 语义同 §5.3.2）；同 Anchor batch 内的 sibling Moves 视为并发。

**Basis 强制（normative）**：cas_register 的 set effect 在目标 cell 的 settled 值为**非初始态**（不等于 `cell_schema.initial_value`；未声明 `initial_value` 时即不为 `null`）时，MUST 在同一 Move 上携带针对**本 cell** 的 `head_eq` precondition；缺失时，receiver MUST 在 verify_move（§6）阶段以 `failed_precondition` 拒绝该 Move 对该 cell 的 effect（按 §3 规则 2 多 cell 原子性，即整个 Move FAIL），不接受“无 CAS 强制写”。省略 `head_eq`（null basis）**仅**在 settled 为初始态时放行，用于 first set。[`operations-sync.md` §9.1](../sync/operations-sync.md) 对 `ck.flow.move` 的既有规则（非初始态下省略 `expected_position` MUST `failed_precondition`）是本条的实例；本条把它泛化为所有 cas_register cell 的 lattice 级通用要求。policy 明确允许“无条件覆盖”的特殊场景（如管理员强制重置）MUST 使用 profile 显式注册的专门高权限 event kind 或 §8 conflict-recovery 路径表达，而不是省略普通 set Move 的 `head_eq`。

**Cell schema 可选参数 `initial_value`**：cas_register cell schema MAY 声明 `initial_value`，该值在 cell 未被任何 Move 写过时作为 `current` 的初值。算法中 `initial` 即该初值（未声明时为 `null`），`current` 从 `initial` 起步。**单例 cell 模式**：schema 声明 `initial_value = "<sentinel>"` 时，配合 `head_eq: "<sentinel>"` predicate 的第一次 set Move 才能成功；后续携带过期 basis 的 Move 因 `basis ≠ settled` 触发 `⊥`，省略 `head_eq` 的 Move 因 settled 非初始态在 verify_move 阶段被 `failed_precondition` 拒绝（见上方 Basis 强制），从而强制 singleton 语义。

```text
join(moves, cell_schema) -> value | ⊥:
  // 按 Anchor batch index 升序 + 同 batch 内按 head_eq 链化（pre-state value → effect value）
  // 跨 batch 时若需要绕过 head_eq 链化，使用 Move.refs(role="after")
  initial = cell_schema.initial_value if defined else null
  current = initial
  for batch in moves grouped by anchor_ref ordered by anchor index:
    settled = current
    siblings = []
    for M in batch with effect on this cell:
      pre = find precondition(head_eq) on this cell in M
      basis = pre.value if pre else null   // null basis 仅在 settled == initial 时合法（first set）
      siblings.append((basis, M.effect.value))
    if ∃ siblings (b1, v1), (b2, v2) with b1==b2 and v1!=v2:
      return ⊥
    if siblings is non-empty:
      // 取共享 basis 后唯一新 value（已在上一步保证唯一）
      if count(distinct(siblings.map(b))) > 1:
        return ⊥
      basis_required = unique(siblings.map(b))
      if basis_required is null:
        if settled != initial:
          return ⊥                // 非初始态盲写：此类 Move 本应已在 verify_move 阶段
                                  // 以 failed_precondition 拒绝（见上方 Basis 强制）；
                                  // join 防御性兜底为 ⊥，MUST NOT 当作合法覆盖
      else if basis_required != settled:
        return ⊥                  // basis 不匹配 pre-state
      if count(distinct(siblings.map(v))) > 1:
        return ⊥
      current = unique(siblings.map(v))
  return current

validate_op(op, cell_schema, move_envelope):
  op.type == "set"
  op.value satisfies schema
  // when initial_value is declared, the sentinel is reserved for the
  // "unset" state. Only a Move whose enclosing Event kind is profile-declared
  // as a cleanup operation AND whose issuer holds the corresponding cleanup
  // capability MAY write the sentinel back. We deliberately key on event_kind
  // + capability rather than add an ad-hoc `from_cleanup_path` field to
  // `lattice_op` (lattice_op wire shape is closed, additionalProperties=false).
  // Cell schemas MAY declare `sentinel_writers[]` listing the event_kinds
  // permitted to write the sentinel; absent that list, no event_kind may
  // write the sentinel.
  if cell_schema.initial_value is defined:
    if op.value == cell_schema.initial_value:
      writers = cell_schema.sentinel_writers or []
      if move_envelope.event_kind not in writers:
        return SCHEMA_VIOLATION(reason=initial_value_reserved)
      // capability check is reducer's normal authz path; not duplicated here.
```

`bottom=reject` 是 cas_register 的标准配置：依赖该 cell 的 Move MUST `fail_bottom`（spec 状态码 `failed_bottom`）。anchorer cell、关键 singleton policy 与 host 指针均使用此组合。

#### 5.3.4 `fsm`

有限状态机。每个 transition op 声明 `from` / `to`；Schema 在 `parameters` 中声明合法 transition 表。

```text
join(moves) -> state | ⊥:
  state    = parameters.initial_state
  batches  = group_by_anchor_index(moves)
  for batch in batches ordered by anchor index:
    transitions = transition effects for this cell in batch
    if transitions is empty: continue
    if any transition.from != state: return ⊥
    if any (transition.from, transition.to) ∉ parameters.allowed_transitions: return ⊥
    next_states = distinct(transitions.map(to))
    if count(next_states) > 1: return ⊥
    state = unique(next_states)
  return state

validate_op(op):
  op.type == "transition"
  op.from, op.to ∈ parameters.states
  (op.from, op.to) ∈ parameters.allowed_transitions
```

membership / lifecycle / invite-approval 多用 `bottom=reject`。

同一 Anchor batch 内相同 `(from,to)` 的重复 transition 是幂等的；同一 `from` 指向不同 `to` 的 sibling transition 返回 `⊥`。跨 batch 顺序仅由 Anchor DAG index 决定；同 batch 内不得用 HLC、接收顺序或 actor id 选择状态机 winner。

**Realm bootstrap exception**: `ck.realm.create` 的 reducer 既是 Realm metadata 的 genesis, 也是 `created_by` 首份成员资格的 genesis — 二者必须原子完成（详见 [`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-ckrealmcreate-reducer-bootstrapnormative)）。任何后续 reducer / authz layer 在判定"`actor` 是否是 Realm 成员"时, MUST 以 `ck.component.member.state.v1` cell 的 reducer view 为准, 而该 cell 在 `ck.realm.create` commit 之后已经包含 `created_by`。"显式 `ck.member.state{join}` event 必须先到"是错误读法; create event 本身就是 genesis member 凭证。

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

validate_op(op, cell_schema, pre_state_value):
  op.type ∈ {inc, dec}
  op.value is a non-negative integer
  // 边界检查（normative）：越界 op 在 validate_op 阶段拒绝，不进入 join
  if parameters.max is defined and op.type == "inc"
     and pre_state_value + op.value > parameters.max:
    FAIL_PRECONDITION(reason=counter_bound_exceeded)
  if parameters.min is defined and op.type == "dec"
     and pre_state_value - op.value < parameters.min:
    FAIL_PRECONDITION(reason=counter_bound_exceeded)
  op.tag is optional but, when present, MUST match schema tag pattern
```

**边界规则（normative）**：cell schema MAY 在 `parameters` 中声明 `max`（与可选的 `min`）。声明后，任何使该 cell 在 batch pre-state 下的累计值越过 `parameters.max`（或低于 `parameters.min`）的 inc / dec op MUST 在 validate_op / verify_move 阶段以 `failed_precondition`（`reason=counter_bound_exceeded`）拒绝，不进入 join。join 本身保持上述无界 PN 求和定义，因此 counter 的 join 永不返回 `⊥`（与 §5.1 对照表一致）。同一 batch 内多个各自通过 validate_op 的并发 op 求和后仍可能越界——此时 join 照常返回求和值，越界情况作为 `bottom=expose` 类诊断暴露（§5.1 对照表 counter 行）；后续越界 op 在新的 pre-state 下被 validate_op 拒绝。

`bottom` 永远不出现。`bottom=expose` 仅在配额跨界等场景下作为诊断（actual value still defined）。

#### 5.3.6 `ordered_log`

Append-only log。Entry payload 通过 `op.value` 承载；每 issuer 子链由 `op.issuer_seq` 单调推进；跨 Move 全局去重依赖 `cell schema` 在 entry 内声明的稳定 entry id（如 `value.entry_id` 或 canonical-bytes-derived hash），具体由 cell schema `parameters.entry_id_field` 指定。

```text
join(moves) -> List<entry_record>:
  entries = []
  for M in moves:
    for eff in M.effects on this cell:
      if eff.op.type != "append": continue
      eid = canonical_entry_id(eff.op.value, schema.parameters.entry_id_field)
      entries.append({
        event_digest: M.event_digest, issuer: M.issuer,
        seq: eff.op.issuer_seq, value: eff.op.value, entry_id: eid
      })
  // 每 issuer 形成独立子链；同一 (issuer, seq) 重复 → 取最小 entry_id
  per_issuer = group_by(entries, key=issuer)
  for issuer, items in per_issuer:
    items = dedupe_by_entry_id(items)
    items = sort_by(seq)
    contiguous_prefix = longest prefix where item[i].seq == item[i-1].seq + 1
    emit entries after the prefix as pending_gap diagnostics(reason=dependency_missing)
    items = contiguous_prefix
  // 跨 issuer 不强制全局序；projection 可按 (effective_anchor_depth, hlc, issuer, seq) 展示
  return concat(per_issuer.values())

validate_op(op):
  op.type == "append"
  op.issuer_seq is non-negative integer; monotonic per (cell, issuer)
  op.value satisfies entry schema declared by cell parameters
```

`bottom` 永远不出现。审计、消息历史、不可变操作日志均使用 `bottom=expose`，并发 append 不阻塞协议判断。issuer 子链出现缺口时，缺口后的 entry MUST 保留为 pending / diagnostic 输入，但不得进入 cell value、state_root leaf 或授权判断；依赖补齐后按同一规则重算。

#### 5.3.7 `lww_register`（扩展：`ck.profile.collaborative_text.v1`）

Last-write-wins register。本节是该 lattice type 的 normative 行为，但**仅在实现声明 `ck.profile.collaborative_text.v1` 时启用**——未声明的实现遇到使用 `lww_register` 的 cell schema MUST 按 §5.4 fail closed。"时间"由 Anchor DAG 中可推导的 effective depth 提供，**不**读 actor HLC，也不把批次序号写入 `state_root` leaf：

- 跨 Anchor batch：后批次 effect 覆盖前批次。
- 同 Anchor batch（sibling Move）并发不同 set：用 deterministic tiebreaker `(issuer DID lex order, event_digest lex order)` 选 winner；记录 lost siblings 进 bottom diagnostics 但不影响最终 value。

**Open_set anchor profile 下的全序保证**：当 anchor profile 是 `open_set`、effective anchor view 由多个 leaf 的 `union` 构成时，sibling Move 集合 MUST 按 deterministic effective anchor view（§4.1）的 canonical join 计算，**而不是**基于任意单 leaf 的局部观察：

- 输入 sibling 集合 = `union(all leaves' frontier) ∩ {moves with effect on this cell within the same effective_anchor_depth}`。这里的 `effective_anchor_depth` 是从 Anchor DAG predecessor relation 推导出的 view-local depth，不是 Event、Move、leaf 或 `state_root` 中的 wire 字段；不同 leaf 给出不同 sibling 集合的情况由 join 强制统一。
- Tiebreaker key `(issuer DID lex order, event_digest lex order)` 的比较 MUST 按 NFC + ASCII byte order；两个 Event 的 `(issuer, event_digest)` 不可能完全相等（event_digest 是 canonical-bytes hash），所以 winner 永远唯一。
- 不同 conformant 节点对同一 anchor view 计算 sibling 集合 + tiebreaker MUST 产出相同 winner；任何偏差视为 reducer 实现 bug，conformance vector `ck.vector.lattice.lww_open_set.v1` 验证此性质。

```text
join(moves) -> value:
  current = parameters.initial_value   // schema 声明的初值，可为 null
  // 关键：moves 已经是 effective anchor view 全 union 的结果，不是单 leaf
  for effective_anchor_depth in sorted(unique depths derived from anchor view union):
    siblings = [M for M in moves
                if effective_anchor_depth_of(M, view) == effective_anchor_depth
                and M has set effect on this cell]
    if siblings is empty: continue
    if len(siblings) == 1:
      current = siblings[0].effect.value
    else:
      // 多节点对同一 view 必须计算同一 winner
      winner = min(siblings, key=(M.issuer, M.event_digest))   // canonical lex order
      current = winner.effect.value
      // 其它 siblings 进入 bottom_diagnostics（kind=conflict）但 value 已确定
  return current

validate_op(op):
  op.type == "set"
  op.value satisfies schema
  cell schema MUST NOT 列入 authorization_root / policy_root / anchorer_root
```

`bottom` 不出现于 value path。`bottom=expose` 仅当并发 sibling 出现时由诊断层暴露 lost values；授权层 MUST NOT 据此选 winner（cell 已被 schema 静态禁止作授权根）。

Schema 声明 cell 为 `lww_register` 时 MUST 同时声明 `cell_role ∈ {ui_affordance, content, draft, cosmetic}`；声明 `cell_role` 为 authorization-related 值时 schema_violation。这是把 lww_register 关在协议安全圈外的硬约束。realm.schema.json 在 `cell_lattice` 上有 `allOf` 条件强制此规则。

#### 5.3.8 `rga` (Replicated Growable Array，扩展：`ck.profile.collaborative_text.v1`)

Replicated Growable Array — 协作文本与有序列表插入。本节同 §5.3.7 一样**仅在实现声明 `ck.profile.collaborative_text.v1` 时启用**；未声明者按 §5.4 fail closed。每个 element 由 `(issuer, issuer_seq)` 二元组确定性命名；插入 op 携带 predecessor element id；删除 op 写 tombstone。

```text
op shape:
  insert: {type: "insert", predecessor: <element_id | "head">, element_id: "<issuer>:<seq>", value: <atom>}
  delete: {type: "delete", element_id: <element_id>}

element_id 形态：`<issuer-did>:<seq>`，issuer 即 Move issuer，seq 由 issuer 在该 cell 上单调递增（每次 insert 递增）。

join(moves) -> List<{element_id, value, deleted}>:
  inserts = {}    // element_id → {predecessor, value, effective_anchor_depth, issuer_lex}
  tombs   = set() // element_ids deleted
  for effective_anchor_depth, batch in moves grouped by effective anchor depth:
    for M in batch with effect on this cell:
      for eff in M.effects:
        if eff.op.type == "insert":
          inserts[eff.op.element_id] = {
            predecessor: eff.op.predecessor,
            value:       eff.op.value,
            effective_anchor_depth: effective_anchor_depth,
            issuer:      M.issuer,
          }
        elif eff.op.type == "delete":
          tombs.add(eff.op.element_id)

  // 构建 forest：每个 element 挂在它的 predecessor 下
  // 同一 predecessor 下多个 child 按 (effective_anchor_depth, issuer, seq) 升序排列
  result = []
  walk(predecessor="head"):
    children = [eid for eid, meta in inserts if meta.predecessor == predecessor]
    children.sort by (inserts[eid].effective_anchor_depth, inserts[eid].issuer, eid_seq(eid))
    for c in children:
      if c not in tombs:
        result.append({element_id: c, value: inserts[c].value, deleted: false})
      else:
        result.append({element_id: c, value: inserts[c].value, deleted: true})  // tombstone
      walk(c)
  walk("head")
  return result

validate_op(op):
  op.type ∈ {insert, delete}
  if insert: op.element_id = "<M.issuer>:<seq>", seq monotonic per (cell, issuer)
             op.predecessor 在已知 inserts 集合中，或 == "head"
             op.value satisfies element schema (atom: char | block | list_item)
  if delete: op.element_id 必须曾被某个 insert 引入
  cell schema MUST NOT 列入 authorization_root / policy_root / anchorer_root
```

`bottom` 不出现：RGA 总有合法 deterministic order。Tombstone 不被物理删除（保留以让长后到的 reference 能正确 walk）；redaction 通过 `delete` op + `ck.message.redact` 类规则实现 metadata-level 隐藏。

RGA 的开销：每个未 GC 的 element 持续占空间。Realm 可声明 `rga_compaction_after_anchors`（默认 10000）触发 compaction Anchor，把 fully-deleted、无后继 reference 的 tombstone 物理移除并签入压缩 state_root。

### 5.4 Profile MUST NOT 引入新 Lattice type

接收方不识别核心或已注册扩展 Lattice type MUST fail closed；扩展 cell family MUST 通过 schema/profile 显式声明并声明 fall-back 行为；任何引入新 lattice type 的 profile 必须先经过 v1 protocol-amendment 流程才能被 normative 集成（避免 implicit 协议分叉）。

v1 已注册扩展 Lattice type：

- `lww_register` / `rga` — `ck.profile.collaborative_text.v1`（§5.0.1、§5.3.7、§5.3.8）。

未声明 `ck.profile.collaborative_text.v1` 的实现遇到使用这两种 type 的 cell schema 时 MUST 返回 `unsupported_lattice_type` 并拒绝写入对应 cell；既有 Move 已被 anchored 的 RGA / lww 历史 SHOULD 仍能 backfill 但只能透出诊断态，MUST NOT 参与新 Move 的 reducer 决策。

## 6. Move 验证

```text
verify_move(M, pre_state):
  1. canonical bytes 哈希等于 M.event_digest 且等于 M.proof.event_digest；M.proof 由 M.issuer 控制的 key 签发。
  2. M.refs 中所有 critical ref 已知且自身 valid。
  3. M.anchor_ref 在本 Realm Anchor DAG 中，且未超过 max_anchor_staleness_ms。
  4. 对每个 (cell, predicate):
       L = schema.lattice(cell)
       v = pre_state[cell]
       if v == ⊥ and L.bottom == reject: FAIL_BOTTOM
       if not predicate(v): FAIL_PRECONDITION
  5. 对每个 (cell, op):
       schema.lattice(cell).validate(op)
       if schema.lattice(cell).type == cas_register and op.kind == "set"
          and pre_state[cell] != (schema.lattice(cell).initial_value if defined else null)
          and M 无针对本 cell 的 head_eq precondition:
         FAIL_PRECONDITION       // §5.3.3 Basis 强制：非初始态盲写
       self.authz.check(M.issuer, cell, op, M.refs)
  6. PASS
```

授权来源必须是 `refs(role="authorized_by")` 或等价 schema role 中的凭证链。`authorized_by` 引用的是不可变 grant record，而不是“某次 allow 判定”。reducer MUST 维护 `(grant_id -> dependent_event_id[])` 的本地索引或等价审计索引：当 `ck.capability.revoke` / supersede / parent grant revoke / claim revocation 进入 accepted state 时，节点必须能列出受影响的 pending、cached allow 和后续 delegated grant，并触发 recheck / quarantine / audit note。已经 anchored 的历史 Event 不被物理删除，但任何依赖已失效 grant 的后继写入、snapshot claim 或 policy decision cache MUST fail closed，reason=`authorized_grant_revoked` 或更具体的上游原因。

Capability cache 的 key MUST 包含 Anchor view / state root；当相关 grant/revoke/claim/policy cell 变化时 cache 立即失效。

## 7. Anchor 应用

```text
apply_anchor(A):
  1. 校验 predecessor_refs 均已知且属于同一 Realm。
  2. 校验 A.frontier 覆盖所有 predecessor frontier。
  3. 在 predecessor joined view 下读取 anchorer cell 并校验 A.anchorer_signature。
  4. 以 predecessor joined state 批量 verify 所有 new_moves；任一失败则拒绝整个 Anchor。
  5. 原子应用 new_moves effects，重算 state_root。
  6. state_root 匹配则接受 Anchor；否则拒绝 Anchor 并生成 anchor_fault 诊断。
```

Anchor 被拒绝时，其 frontier 内 Move 不因此变成 effective。节点 MAY 保留这些 Move 作为 pending / diagnostic 输入，但 MUST NOT 让它们推进 query 或授权。

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

修复权威来自冲突前 effective state 中的 governance / recovery capability。实现 MUST NOT 用冲突候选本身声明的新 policy、new anchorer 或 new admin 来授权修复。

### 8.1 Pre-conflict State Witness 强制要求

`open_set` 与 `threshold` Anchor profile 下，多个 verifier 在 ⊥ 发生瞬间持有的"冲突前 effective state"可能不同——peer A 的 state_root 与 peer B 的 state_root 可能源自不同的 Anchor leaf 子集。如果允许 recovery Move 仅口头引用"冲突前 effective state"，攻击者就可以选择对自己有利的 anchor view 子集来"证明"自己持有 recovery_capability，于是同一 ⊥ 出现两条互斥的修复 Move。这种攻击在 v1.0 之前的 §8 设计下没有防护手段。

为此，conflict-recovery Move MUST 显式提供两条 critical refs，否则 receiver MUST `failed_precondition` 拒绝：

1. **`pre_conflict_state_witness`** — 一个签名 snapshot 或 signed compaction Anchor 的 id，满足：
   - 它来自冲突 cell 进入 ⊥ 之前的 Anchor view（即该 witness 所引用 frontier 不包含触发冲突的任一 sibling Move）。
   - 它由 Realm 当前 anchorer cell value 授权的签名者签发（`single_did` / `threshold` / `open_set` 的 anchorer rule）。
   - 它的 `state_root` 中包含 recovery_capability 所授权的 cell value。

2. **`snapshot_inclusion_proof`** — 一个使用 §4.2 leaf/internal-node domain separation 的 Merkle inclusion proof，证明：
   - 引用的 `recovery_capability` grant cell value 真实属于 `pre_conflict_state_witness.state_root`（而不是攻击者本地伪造的 effective view）。
   - Inclusion proof 的 leaf 编码 MUST 按 §4.2.1 锁定的 leaf shape 计算（`H(0x00 || canonical_json({"cell": "<CellRef>", "state": <state_object>}))`）。
   - Proof path 的 sibling hash 序列 MUST 能重算出与 `pre_conflict_state_witness.state_root` 完全相同的 root。

Receiver 在 verify_move(M) 时，对 critical role ∈ {`state_witness`, `inclusion_proof`}：

- 若 ref 缺失或签名无效 → `failed_precondition`（`reason="recovery_witness_missing"`）。
- 若 inclusion proof 不能重算出 witness 的 `state_root` → `failed_precondition`（`reason="recovery_witness_invalid"`）。
- 若 witness frontier 与触发 ⊥ 的 sibling Move 之一存在因果路径（即 witness 不在冲突前）→ `failed_precondition`（`reason="recovery_witness_post_conflict"`）。
- 若 witness 的 state_root 不包含 recovery_capability cell 或包含的 cell value 与 grant 引用不一致 → `failed_precondition`（`reason="recovery_capability_not_anchored"`）。
- 若 witness 的 anchor frontier 早于本地 anchor head 超过 `recovery_witness_freshness_window`，或本地 frontier 在 witness 之后已观察到任何针对 `recovery_capability` 所引用 cell 的 accepted revoke / supersede event → `failed_precondition`（`reason="recovery_witness_revoke_lagging"`）。

  `recovery_witness_freshness_window` **MUST NOT** 固定为单纯的 "6 anchor cadence"：在低频 Realm 下 6 个 anchor cadence 的挂钟时长可达数天，会给"持有合法旧 witness + 等待 recovery_capability 被 revoke 后重放"的 stale-witness 攻击留下数天窗口。因此该窗口 **MUST** 取下列两项中**更严格**（更短挂钟时长）的一项：

  ```text
  recovery_witness_freshness_window =
    min(
      6 anchor cadence 对应的挂钟时长,
      recovery_capability 所引用 cell 关联 capability 的 revocation freshness window
        （见 capabilities.md §18.2 freshness_required_ms / freshness_hard_limit_ms）
    )
  ```

  即 witness 的新鲜度要求 **MUST NOT** 弱于其所证明的 capability 自身的 revocation freshness 约束。低频 Realm 下 anchor cadence 很长时，该 min 收敛到 capability 的 revocation freshness window（通常分钟级），强制 recovery witness 足够新鲜。该检查关闭上述 stale-witness 攻击面：witness 自身的签名时点是合法的，但若它无法反映已 anchored 的 revoke，receiver **MUST NOT** 据它接受 recovery Move。Realm 部署 MAY 在 deployment policy 内进一步收紧窗口，但 **MUST NOT** 放宽到上述 `min` 结果以上。

`single_did` Anchor profile 下，由于 anchor view 全网唯一，该机制等价于自然成立——但 wire 上仍 MUST 携带 witness ref，便于审计回放。这避免实现因为"现在用的是 single_did 就跳过校验"而在未来 anchorer 升级到 `open_set` 时无声留下盲区。

### 8.2 ⊥ 升级与 emergency recovery

长时间未修复的 `⊥` 不会自动选 winner。Realm MAY 声明 `bottom_escalation_after_ms`；超时后，客户端和服务端应提示 emergency recovery quorum，但仍需普通 Move + Anchor 生效，并仍 MUST 满足 §8.1 的 witness + inclusion proof 要求。emergency recovery quorum 的特殊之处仅在于 capability `subject` 由 genesis 声明的 emergency role 担任，而不在于跳过证据要求。

## 9. 部署 Profile

Hub、threshold、open federation、sovereign federation 和 E2EE 只是 anchorer cell value 与 Anchor uniqueness profile 的不同组合。

| Profile | Anchorer value | Anchor DAG 约束 |
| --- | --- | --- |
| `single_did` | 单一 service DID / host key。 | 可要求 signed Anchor 单链；compaction 由该 DID 签发。 |
| `threshold` | k-of-n committee key / signer set。 | 可要求 signed Anchor 单链；threshold sig 提供 uniqueness。 |
| `open_set` | 管理员 / federation peer DID 集合。 | 允许多 leaf；query 使用 deterministic effective anchor view。 |
| `mixed` | 主 anchorer + fallback recovery anchorer。 | 正常单链；anchorer fault / bottom 时 fallback 可签 recovery Anchor。 |

Realm create MUST 固定 genesis anchorer 与 recovery anchorer。`ck.schema.realm.v1` 要求 create payload 携带 `anchor_profile` 与 `anchorer`；`single_did` profile 还必须携带非空 `recovery_members`、主 anchorer 的 `controller_organization` 以及 recovery side 的 `recovery_controller_organizations`。后续变更走 anchorer cell 的普通 Move。

### 9.1 Anchor Profile 威胁与可用性矩阵

每种 anchor profile 在审查抗性、可用性、recovery 流畅度与 federation 复杂度上有不同 trade-off。Realm create 选择 profile 时 MUST 与 deployment / governance 团队对照本表评估。

| Profile | 审查抗性（anchorer 单方拒签） | 可用性（anchorer 故障） | Recovery 复杂度 | Federation 拓扑 | 主要威胁 |
| --- | --- | --- | --- | --- | --- |
| `single_did` | 弱：anchorer 可静默不签 → Realm 整体写入卡住，无法仲裁 | 弱：单点故障 = 全 Realm 写阻塞，必须等 anchorer 恢复 | 简单：anchorer 自己签即可 | 星型，所有 peer push 给单一 anchorer | **审查与 DOS**：anchorer 单方拒签某 actor / 某类 Move 是协议层无法防御的——必须由 governance / legal 层补偿；适合企业内可信 hub 与 personal_node，**不适合**对抗审查的开放协作 |
| `threshold` | 中：k 个签名者合谋才能审查 | 中：n-k 个签名者可继续推进 | 中：合谋抗性靠 threshold sig；恢复需要 ≥ k 个签名者重新组队 | 星型 + 多签名委员会 | **委员会 churn**：n-k 个签名者长时间离线 → 推进卡死；**recovery anchor 需要门限组重新签发** → 不能由单一 admin 解锁 |
| `open_set` | 强：任何 peer 都可签 leaf anchor → 单一审查者无法阻塞 | 强：peer 子集 outage 不影响其他 peer 推进 | 复杂：多 leaf join 形成 deterministic view；compaction Anchor cadence 决定查询性能 | mesh，所有 peer 互相交换 leaf anchor | **协调成本**：peer 间频繁交换 leaf anchor 与 compaction；**witness liveness 风险**：若没有定期 compaction Anchor，long-tail leaf 可能卡查询；conflict-recovery Move 需要的 state_witness 必须是 compaction Anchor 而非任意 leaf |
| `mixed` | 强（主 anchorer 健康时） + 强（fallback 时） | 强：主 anchorer 故障 → fallback recovery anchorer 接管 | 中：fallback 切换由 anchorer cell ⊥ 触发 + recovery quorum 签发 | 取决于主/fallback 各自类型 | **fallback 误触发**：主 anchorer 暂时不可达但仍健康时被错误判 fault → fallback 接管造成短暂双 leader；**recovery anchorer 选择**必须独立于主 anchorer，否则同一 outage 同时影响两者 |

### 9.2 Recovery Witness Liveness Profile

`open_set` 与 `threshold` profile 必须保证 conflict-recovery（§8.1）所需的 `state_witness` 与 `inclusion_proof` 可获得。这要求 **compaction Anchor 必须周期性签发**，否则 recovery Move 无 witness 可引用，⊥ 状态会无限期卡死。

| Profile | Compaction cadence 要求 | Snapshot witness liveness 要求 |
| --- | --- | --- |
| `single_did` | SHOULD 每 ≤ 1 周签发 compaction Anchor | SHOULD 每 ≤ 24h 发布 signed snapshot frontier |
| `threshold` | MUST 每 ≤ 7 天签发 compaction Anchor；超时 receiver SHOULD 提示 governance health alarm | MUST 每 ≤ 24h 发布 threshold-signed snapshot |
| `open_set` | MUST 每 ≤ 24h 由任一 peer 签发 compaction Anchor 收敛 leaf；超时所有 leaf 视为可恢复但不可作为 conflict-recovery witness（receiver fail closed for recovery Move） | MUST 每 ≤ 24h 至少有一个 peer 发布 signed snapshot |
| `mixed` | 主 anchorer 健康时同 single_did；fallback 期间 SHOULD 每 ≤ 24h | 同主 anchorer profile 要求 |

部署 profile（[`conformance-profiles.json` deployment_profiles](../../artifacts/profiles/conformance-profiles.json)）SHOULD 通过 `anchor_compaction_max_interval_ms` 与 `snapshot_witness_max_interval_ms` 字段表达上述硬上限；conformance test 验证实现暴露该 metric。

### 9.3 不可由协议防御的威胁（必须显式声明）

以下威胁 MUST 在 Realm create 时由 deployment 与 governance 层声明缓解措施，**协议层无法替代**：

- **`single_did` anchorer 审查与 DOS**：anchorer 拒签 = Realm 写阻塞。`single_did` profile MUST 在 Realm create 时同时声明非空 recovery anchorer 路径（wire 字段为 `anchorer.recovery_members[]`，语义等价于 recovery anchorer 集合），且至少一个 recovery controller MUST 与主 anchorer 在不同的 controlling organization；不满足者 reducer MUST 在 `ck.realm.create` 步骤返回 `anchorer_recovery_missing` 并拒绝创建。Receiver 不能只信任字符串不相等：它 MUST 用 DID resolver、deployment policy 或 `controller_organization` / `recovery_controller_organizations` evidence 验证组织多样性；无法验证时 MUST fail closed。声称对抗审查能力的部署 MUST NOT 选择 `single_did`，应使用 `threshold` 或 `open_set`。
- **`threshold` 委员会合谋**：k 个签名者可以联合审查特定 actor。Realm MUST 在 governance policy 中声明委员会成员选拔、轮换与 quorum recovery 流程。
- **`open_set` peer 集合污染**：若 anchorer cell 中加入了恶意 peer，它可签发恶意 leaf。anchorer cell 是 cas_register + bottom=reject，所以新增 peer 必须由当前合法 anchorer 签发的 Move 加入；但**初始 genesis anchorer 设置错误是不可恢复的**——MUST 在 genesis 时审慎选择并多方签名 verify。
- **签名 key 失窃与 anchorer key rotation**：anchorer 签名 key 失窃 → 攻击者可签发任意 Anchor。Recovery 路径必须是 genesis 时声明的 recovery_anchorer 通过 ⊥ + recovery Move 替换被泄露的 anchorer cell；deployment SHOULD 强制 anchorer key 用 HSM / threshold key 而非软件 key。

`server-threat-model.md` §2.1 已涵盖对应通用攻击面；本节专门点出**不可由协议层规避、必须由 governance 与 deployment 主动设防的部分**。

## 10. E2EE 与 MLS

E2EE Realm 通过 **MLS Governance Binding**（profile `ck.profile.mls_governance_binding.full.v1`，规范定义见 `crypto-media/encryption-and-audit.md §2.5`）把 MLS epoch 与 governance state 强绑定。本节只描述其在 Move / Anchor / Lattice 层的语义；commit-side `governance_binding` 的字段、profile 与 GroupContext extension 编码不重复，见上述规范文档。

MLS commit 是 Move，不是 Anchor。它写入三个 well-known cell（cell family 由 `ck.component.mls_epoch.v1` / `ck.component.key_schedule.v1` / `ck.component.covered_frontier.v1` 给出，cell_subject 为 MLS group id 或 realm id）：

```text
Move(MLS commit) {
  preconditions: [
    (mls_epoch_cell,        head_eq prev_epoch),                  // cas_register
    (covered_frontier_cell, contains governance_frontier_required) // or_set / set semantics
  ],
  effects: [
    (mls_epoch_cell,        set new_epoch),
    (key_schedule_cell,     set new_schedule),
    (covered_frontier_cell, add attested_governance_frontier)
  ]
}
```

`covered_frontier_cell` 是声明"该 MLS group 当前已绑定的 governance Anchor frontier"的 cell（`or_set`，bottom=expose）：每个 MLS commit 把它绑定到的 governance Anchor 加入；E2EE message Move 在 preconditions 中要求 `contains` 自身 `anchor_ref` 所代表的 governance frontier。

E2EE message Move（即在加密 payload 上下文中提交的 Move，例如 `ck.message.create` 在 E2EE Realm）MUST 在 preconditions 中证明 `covered_frontier_cell` 覆盖其 `anchor_ref` 所需 governance frontier。MLS 滞后只阻塞 E2EE message / key schedule Move（它们引用 `covered_frontier_cell`），不阻塞 governance / recovery Move（它们不引用该 cell）。

Move 在 Anchor 前是 pending；被 Anchor 后是否可用于 E2EE 由 `covered_frontier_cell` precondition 决定。

## 11. Redaction 与 Erasure

Redaction 是写入 redaction / erasure cell 的 Move。Redaction effect 必须保留足以验证 `event_id` / `event_digest`、签名、anchor inclusion、target id、授权凭证和 tombstone stub 的最小数据。

对 `ordered_log` 历史，redaction 不删除 log entry id；它写入同 target 的 redaction cell，使 projection 隐藏或替换 payload。审计、legal hold 与 erasure receipt 规则见隐私和安全文档。

## 12. Snapshot、GC 与恢复

1. 未被任何 Anchor frontier 覆盖、且未被 active pending Move / recovery Move 引用的 Move MAY GC。
2. 已 Anchor 的 Move MUST 保留审计 stub；payload 可按 retention / erasure 规则裁剪。
3. Anchor DAG 可通过 signed compaction Anchor 压缩；压缩 MUST NOT 丢失 frontier、state_root、签名验证链或必要 bottom diagnostics。
4. Snapshot 是 Anchor view 的 materialized state_root 证明，不是独立真相源。没有可验证 Anchor / Move inclusion proof 的 snapshot MUST NOT 用于授权 allow。

## 13. 失败状态

| 状态 | 语义 | 关联 Bottom kind |
| --- | --- | --- |
| `pending_anchor` | Move 已通过本地初检，等待 Anchor。 | — |
| `effective` | Move 被已接受 Anchor frontier 覆盖，并已进入 state_root。 | — |
| `failed_precondition` | Move 在本地预检、pending 或被拒绝 Anchor 的诊断视图中不满足 precondition；包括 conflict-recovery Move 缺失或无效的 `state_witness` / `inclusion_proof` ref（§8.1）。进入已接受 Anchor frontier 的 Move 不得处于该状态；若 Anchor batch pre-state 下任一 Move 校验失败，整个 Anchor MUST `rejected_anchor`。`reason` 字段细分 `recovery_witness_missing` / `recovery_witness_invalid` / `recovery_witness_post_conflict` / `recovery_capability_not_anchored`。 | — |
| `failed_bottom` | Move 依赖 `bottom=reject` 的 cell。 | 由 §5.1 中对应的 kind 触发（如 `conflict`、`invalid_transition`、`schema_error`）。 |
| `rejected_anchor` | Anchor 签名、单调性、Move batch 或 state_root 校验失败。 | — |
| `anchorer_paused` | anchorer cell 为 `⊥`；Realm-wide Anchor 推进暂停，只允许 recovery Anchor。 | `anchorer_split`（§5.1）。 |

实现 MAY 在 API 层继续使用兼容错误码，但必须映射到本表语义。Move 的当前状态字段在 sync wire 上以 `event_state` 暴露（见 [`sync/service-surface.md`](../sync/service-surface.md) §5.3）。

## 14. 规模上限

Move/Anchor/Lattice 必须受 [`scalability-constraints.md`](../conformance/scalability-constraints.md) 约束：

- 单个 Move canonical size 默认不超过 1 MiB。
- 单个 Move 的 `preconditions + effects` 默认不超过 256。
- 单个 Anchor 新增 Move 默认不超过 1,000。
- Anchor DAG leaf 数超过实现声明上限时，节点 SHOULD 请求或生成 compaction Anchor。
- 单次 Lattice join 超过预算时，节点 MUST 返回可恢复错误或使用可验证 state_root + inclusion proof；MUST NOT 用本地接收顺序替代。

实现 SHOULD 为每个 core lattice type 提供增量 API，但 wire 互操作只依赖 deterministic full join 语义。
