---
title: Event Auth、CBA 双平面与状态收敛
status: candidate
normative: true
stability: v1
updated: 2026-07-30
sidebar:
  label: Event Auth & State Resolution
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret v1 的一致性层采用 **CBA（Control-plane Basis-committed Sealing）**：

- **数据面**（data plane）承载消息、内容、reaction、计数、协作文本、草稿和默认业务对象。数据面 Event 是签名因果 hash-DAG + Lattice / CRDT 输入；验签、授权与 `seal_ref` 验证通过后即可本地投影、转发和参与 join。数据面没有事件级 Seal finality 字段、没有 pending→effective 状态机、没有全局排序闸门。
- **控制面**（control plane）承载 membership、capability、policy、notary、lifecycle、MLS epoch / governance binding 以及显式 `sealed=true` 的对象。控制面 Move 由 Seal 裁决，提供 finality、治理 `state_root`、问责与 transparency。
- Seal 对数据面只做**观测承诺**（`data_view_root` / `data_event_set_root`）；`availability_receipt_digests[]` 则逐项绑定控制面 include 所需的完整 AvailabilityReceipt。二者都不把普通数据面 Event 升级为控制面 finality。

非目标：本文不提供全局总序、经济 finality、全文搜索、媒体分发、typing / presence 等派生层行为；不证明"不存在没人见过的 Event"；轻客户端不验证全 Realm reducer 执行。

## 2. 术语

| 术语 | 定义 |
| --- | --- |
| DataEvent | 只写 data plane cell 的签名 Event。它携带 `seal_ref`，不携带 `seal_basis`。 |
| Control Move | 只写 control plane cell 的 reducer-input Event。它携带 `seal_basis`，由 Seal 裁决。 |
| Seal | 控制面 Seal。它用 `predecessor_refs[] + delta[]` 定义递归控制面覆盖集、承诺治理 `state_root`，并可附带数据面观测承诺。 |
| Cell | 可被 Lattice 合并的最小状态单元，标识为 `ak:cell:<component>:<subject>` 或等价 canonical tuple。 |
| Plane | cell family 的安全分级：`data` 或 `control`。内建 family 由 event-kind registry 静态冻结；Realm schema 只能为 Realm-specific extension family 登记该值。plane 是安全边界，cell 是冲突域。 |
| Lattice | Realm schema 为每个 cell family 选择的封闭核心代数类型。`join()` 返回值或 bottom (`⊥`)。 |
| Bottom (`⊥`) | 某个 control cell 或 opt-in control object 在当前 seal view 下无有效单值或存在非法状态。数据面默认不产生协议级 `⊥`；普通冲突暴露为多 head。 |
| seal_ref | DataEvent 声明的授权基准：一个已接受控制面 Seal id。 |
| seal_basis | Control Move 签名覆盖的控制面基线：canonical sorted、duplicate-free `{leaves[]}`。Seal roots 由 receiver 从被引用 Seal 重算，不在 Event 复制。 |
| control_event_set_root | Seal 对递归控制面覆盖集 `covered_set(S)` 的 authenticated root。basis、inclusion、non-membership、receipt obligation 与 censorship evidence 都以它为锚点。 |
| KeyView | Seal 对某个 data cell 的观测记录，包含 cell、lattice type、heads / value digest 与 last covered event。 |
| Event Batch Receipt | issuer（relay / notary / witness / Station）对其选择承诺的 Event 集合签发的 receipt object（`ak.schema.event_batch_receipt.v1`）。数据面单事件"已看见"确认是其 `events[]` 单元素用法。它不是准入证明，不进入 state。 |
| AvailabilityReceipt | holder 对某个 Event bytes 在 retention 窗口内可获取的签名承诺。 |

## 3. Plane 判定

每个 cell family MUST 声明 `plane`。v1 内建 family 的声明在 `event-kind-registry.json` 中静态冻结；`ak.realm.policy_bundle.cell_lattices` 只允许为 Realm-specific extension family 登记 plane/lattice/bottom，MUST NOT shadow、覆盖或重新解释任何已登记内建 family。下列三类是协议撰写与 family 注册时的选择规则，不是 per-Realm 运行时选项：

- **强制 control**：authorization root、policy、membership、capability、notary、lifecycle、MLS epoch / key schedule / governance binding，以及现有规范中禁止作为 `mv_register` 授权根的 cell family。
- **默认 data**：消息、内容、reaction、普通 metadata、计数、协作文本、草稿和其它未声明为 control 的业务 cell。
- **opt-in control**：新增 data-like cell family 在登记时 MAY 声明 `sealed=true` 升入控制面，用于合规审计、强一致单值、法务保留或高风险 workflow；登记后该选择在 v1 内不可按 Realm 改写。

一个 Event MUST NOT 跨 plane 写入。若一个业务动作同时需要改治理状态和内容状态，producer MUST 拆成两个 Event：先提交控制面 Move，经 Seal 接受后，再用新的 `seal_ref` 产生 DataEvent。

数据面 schema MUST NOT 依赖硬性跨 cell invariant，例如全局唯一性、容量硬上限、跨 list 原子 move 或多对象单赢家裁决。需要这些 invariant 的对象 MUST 声明 `sealed=true` 升控制面，或使用本文件 §9.4 的 per-object sequencer。

## 4. DataEvent

DataEvent 是普通 Event Envelope 的一种语义形态。Wire object 仍是 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)。

```text
DataEvent {
  event_id / event_digest / proofs
  realm_id
  scope_ref
  kind
  actor_id / actor_seq / prev_refs[]
  causal_refs[]                  // 语义因果前驱 event_digest；可由 refs[role=causal] 表达
  seal_ref                 // 单个控制面 Seal id
  auth_context {
    actor_id
    key_id
    key_epoch
    credential_epoch?
  }
  payload
  hlc                            // 纯诊断
}
```

DataEvent 规则：

1. DataEvent MUST 携带 `seal_ref` 与 `auth_context`。
2. DataEvent MUST NOT 携带 `seal_basis`、`preconditions` 或任何 pending / finality 字段。
3. 注册 reducer contract 的全部派生写 MUST 只落入 data plane；否则 receiver MUST `schema_violation(reason=plane_cross_write)`。
4. `causal_refs[]` / `refs[]` 只表达业务因果，不承担全局完整性证明。
5. `event_digest` 是去除 `proofs`、`unsigned` 与 reducer-stamped `actor_kind` 后 canonical Event bytes 的 hash；签名 `scope_ref` 保留。
6. cell target、conflict domain 与 lattice op 由 receiver 从 reducer contract 和 `kind + payload` 重算。wire 上不存在 producer-selected write 或 conflict digest。

### 4.1 `auth_context` 与 epoch pinning

DataEvent 的 `auth_context` MUST pin 事件签名时 producer 声称的身份与授权 epoch：

```text
auth_context {
  key_id
  key_epoch
  credential_epoch?
}
```

Verifier MUST 证明：

1. 先派生 `signer_id = executed_by ?? actor_id`；`proofs[].verification_method` 的已验证 controller 投影 MUST 等于该 `signer_id`，且所选密钥 MUST 等于 `auth_context.key_id`。实现不得把 `did_core_id` 与 fragment 直接拼接成 DID URL。
2. `key_epoch` / `credential_epoch` 在 `seal_ref` 对应 seal 的控制面状态下有效。
3. verifier 从 `seal_ref` 的治理 `state_root` 解析 actor 对该 kind、`scope_ref` 和派生目标所需的全部 capability；producer 不选择候选 grant。

Verifier MUST NOT 只查"当前 DID 文档"来验证旧事件；DID/key/capability 的有效性以 `seal_ref` 对应控制面 seal 为准。

### 4.2 DataEvent 验证

```text
verify_data_event(E):
  1. 验 canonical bytes、event_digest、proofs[] 与 realm_id 绑定。
  2. 验 actor chain：actor_seq / prev_refs[] 对同 actor 成链；同高 sibling 按 actor fork 规则处理。
  3. 验 E 不含 seal_basis / preconditions；重算 scope_ref 与 data-plane reducer writes。
  4. 验 auth_context epoch pinning。
  5. 验 seal_ref (§4.3)。
  6. 对每个派生 write 执行该 data cell 的 lattice validate_op。
  7. 通过后进入本地 data DAG，可立即投影、转发和参与 join。
```

DataEvent 通过验证后不是"被 seal final"，而是**本地终态**：相同 data DAG 输入下，所有 verifier MUST 得到相同 data join 结果。后续发现的有效并发 DataEvent MAY 改变同一 data cell 的 join / exposed heads。

### 4.2.1 Direct Conversation participant source 与 root mask

当 Realm 声明 `ak.profile.direct_conversation_realm.v1` 时，authz check MUST 先识别机器 registry 中的
`ak.authority.direct_conversation_participant.v1` 与 profile root-owner mask，再做最终求交：

- 直接 participant Event 的 `authorization_ref` 必须是 exact source token，并有恰好一条 critical
  `direct_conversation_binding` Event ref；任意 cell/Event、membership、`created_by` 或本地 row 不得替代；
- verifier 在 `seal_ref` view 重算唯一 immutable binding 的有效性、exact-two participant/membership、
  Realm/Strand/MLS/lifecycle/resource 与 action-specific gate。dependency 缺失/冲突/freshness unknown 时
  pending/fail closed；
- `executed_by` Event 的 `authorization_ref` 仍绑定 executor delegation；participant source、Agent
  provision/runtime/participation 与 executor delegation 全部是 AND gate；
- owner aggregate 必须先与 profile phase mask 求交。active phase 的普通 owner operational coverage不能
  作为 participant source 的 fallback；
- authority reset/transfer 不改变 participant source。member leave/ban、Realm terminal 或 canonical main
  Strand terminal 是结构性 zero-window barrier：该终态 accepted 后，新写立即不再 admission；明确因果早于
  barrier 且已按旧 basis 合法接受的 Event 不追溯改写，因果晚于 barrier 的 Event 必须拒绝，依赖不完整的
  并发 Event 保持 pending，不能等待 retired fact 后再临时放行。

影响 immutable binding 可用性、membership、Realm/Strand terminal、MLS group、contact/consent 或 Agent
participation 的 accepted state 变化，MUST 在更新投影的同一事务边界把 participant authz cache stale；
federation 迟到 evidence 补齐后必须重验 pending closure。

### 4.3 `seal_ref` 验证与撤销

`seal_ref` 的语义是："我声称我的写入权基于这个控制面 seal"。

Receiver MUST：

1. 验 `seal_ref` 是本 Realm 已验证控制面 Seal。轻客户端 MAY 用该 seal `state_root` 下 membership / capability inclusion proof 验证所需授权 cell。
2. 在 `seal_ref` 的治理状态下解析该 kind/scope/派生目标需要的 capability，并证明 actor 持有所需写权限且未撤销。
3. 若 receiver 尚未观察到覆盖该 issuer / capability 的后续撤销 seal，则按 `seal_ref` 的授权状态接受。
4. 若 receiver 已观察到撤销 seal `R`，且 `R` 是 `seal_ref` 的后继，则只按缺口距离判定：

```text
if distance(seal_ref, R) <= revocation_freshness_window:
  MUST accept and retain the DataEvent in data-cell join input
else:
  MUST exclude the DataEvent from data-cell join input
```

超窗后的 receiver MAY 在本地保留 Event 供审计并对普通查询隐藏，也 MAY 在准入面直接拒绝；
两种形态对 reducer 输入必须完全等价：该 Event 及其依赖闭包不得参与任何 data-cell join、
`state_root` leaf 或授权判断。窗口内接受并保留在 data-cell join 输入是同一确定性结果，不是实现可选项。

**读取面的边界（normative）**：上述判定是 receiver 在其已验证控制面视图上的 Event admission / reducer-input
判定，不定义名为 `query_grade` 的 wire 字段，也不要求把“曾用旧但仍在窗口内的 basis”复制进 Event、查询行或
projection。`local` / `seen` / `observed` 是实现可保留的本地证据状态，`control_pending` / `control_sealed` 是
Control Move 生命周期，`fork_quarantine` 是分支处置；这些概念不得合并成一个跨 operation 的 grade enum。
具体读取操作若需要携带可验证的 freshness、observation 或 quarantine evidence，MUST 在该 operation 的
`response_schema_ref` 中登记独立、具名且可验证的字段；未登记的响应包装或私有 `query_grade` 字段不属于 v1 wire。

**`distance` 度量与窗口单位（normative）**：`revocation_freshness_window` 的权威字段是 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的 `revocation_freshness_window_ms`（integer，毫秒，`default 86400000`（24h），`minimum 0`）。`distance(seal_ref, R)` MUST 按**控制面 Seal DAG 上 notary 签署的提交时间差**度量：取撤销 Seal `R` 与 `seal_ref` 各自签名 transcript 内 notary 提交时间（沿 Seal DAG，`R` 是 `seal_ref` 后继，见 §6.3），求二者毫秒差。该度量只用进入 Seal 签名 transcript 的 notary 提交时间，**不**用 DataEvent 自报的 `created_at` 或本地接收时间——时间来自被签名的 Seal 拓扑，可验证、跨 receiver 确定复现。`distance > revocation_freshness_window_ms` 即超窗。

该字段的安全语义是 **Seal-distance grace（历史 basis 宽限）**，不是现实时间 TTL。给定同一旧 basis Seal、
后继撤销 Seal 与 Event，receiver 在撤销后一秒或三十天首次收到、在线接收或离线回放，MUST 得到相同结果；
不同 receiver 的到达时间与顺序也不得进入谓词。若两张 Seal 的距离在窗口内，中低风险 Event 不会仅因现实时间
流逝变成超窗；高风险 capability 仍按下文 effective window 0 处理。

该规则不判断事件真实签发时间，也不依赖本地接收时间。producer 在本地已知撤销 seal 后仍用旧 `seal_ref` 签 DataEvent，协议不把它单独定义为可证明 fault；但所有已观察到 `R` 且窗口超限的 receiver MUST 拒绝或隐藏这些事件（`seal_ref_stale`，§13）。

**并发分支撤销（normative，`open_set`）**：撤销 Seal `R` 与 `seal_ref` 并发时，receiver MUST 按已 join 的控制面视图重判 capability；若已撤销或授权 cell 进入 `⊥`，依赖 Event fail closed。并发分支不计算 `distance`、不享受新鲜度宽限。轻客户端无法验证 multi-leaf union basis 时必须 hold pending 或 fail closed。撤销 leaf 迟到后，receiver MUST 把已失效 Event 从 data-cell reducer 输入集中移除，并按仍授权且依赖闭包完整的 accepted Event 集合确定性重算。

追溯重验 MUST 闭包传播：直接/间接依赖被移除 Event 的 accepted Event 转为 `pending/dependency_missing`，其派生写也从 reducer 输入移除，直到闭包稳定。后续补齐后可重新验证，但不得沿用旧授权缓存。结果不得依赖撤销 leaf 的到达顺序。

**高风险 capability 的撤销即时性（normative）**：对 `risk_tier=high` capability（`risk_tier` 的权威源是 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json)，散文镜像见 [`capabilities.md`](./capabilities.md)）授权的 DataEvent，撤销**不享受**新鲜度窗口宽限：receiver 一旦观察到覆盖该 capability 的撤销 Seal `R`，MUST 对 `seal_ref` 早于 `R` 的此类 DataEvent fail closed（等效 `revocation_freshness_window_ms = 0`），无论 `distance`。承载此类 capability 授权判定的 cell family MUST 声明 `cell_role=authorization_root` 且 `plane=control`；若复用一个原本 data-like 的 cell family 作为该授权输入，则还 MUST 显式 `sealed=true` 升控制面，否则 Realm schema / reducer MUST 拒绝该声明。中低风险 DataEvent 仍按上面的窗口判定。

这里的“即时”严格表示 **`R` 已成为 receiver 可验证控制面视图的一部分之后零宽限**，不表示追溯否定 `R` 之前或与 `R` 并发、且按自身合法旧 CBA basis 已授权的操作。同一 ordered submit batch 也不产生隐式因果顺序：revoke 与依赖旧 grant 的 Event 若都指向 revoke 前 basis，后者仍按该 basis 判定；`sealed=true` 提供控制面 finality 与后继顺序，但不会把同批数组顺序改写为授权因果。需要阻断 compromised runtime 的部署 MUST 同时使用 session/introspection pause、ingress deny 或等价的运行时 kill switch；只有后续 Event 改用包含 `R` 的新 basis 后，协议内 capability revoke 才能证明性阻断它。producer 在本地已观察到 `R` 后仍用早于 `R` 的 `seal_ref` 继续签发 DataEvent，receiver / audit **SHOULD** 将其记录为 audit-loggable 可疑信号（stale-after-observed），供事后问责。

**Scope lifecycle 也是授权输入（normative）**：Realm / Circle lifecycle 与 capability 撤销使用同一 CBA 基线纪律。Circle-scoped DataEvent 的 `state=active` 必须在事件 `seal_ref` view 中求值；不得以 receiver 当前 projection 替代。基线后的线性 Circle archive 复用上述 `distance` / `revocation_freshness_window_ms`，tombstone 与 `open_set` 并发 archive / tombstone 等效 window=0；后续 restore 不追溯恢复跨过 archive barrier 的旧 `seal_ref`。Control Move 在其 `seal_basis` joined view admission，并由 `apply_seal` step 8 在冻结 predecessor joined governance state 重验。完整错误映射与 restore barrier 见 [`../models/circle.md` §6.1](../models/circle.md)。

Grant 晚于 producer 最新 seal 签发时，producer MUST 等下一个控制面 seal 后再签 data write。治理低频，等待 seal 是可接受成本。

### 4.4 数据面传播与 Event Batch Receipt

current-v1 数据面传播使用已登记的 direct push、cursor pull 与 exact-ID resolve；同步摘要只可作为 scope-relative federation diagnostic hint。RBSR / Negentropy 没有登记 operation、DTO 或可宣告 profile，不是 current-v1 能力；任何 future set reconciliation 都必须先通过独立收益 gate 并完整登记互操作合同。

Relay / notary / witness 收到 DataEvent 时 SHOULD 返回一个 Event Batch Receipt（receipt object，schema [`event-batch-receipt.schema.json`](../../artifacts/schemas/event-batch-receipt.schema.json)，schema id `ak.schema.event_batch_receipt.v1`，字段与概念分层见 [`../models/event-and-patch.md` §5](../models/event-and-patch.md)）。单事件确认即 `events[]` 只含该 Event 的 `{event_id, kind}` typed item：`scope` 携带 `realm_id`，`created_at` 为 issuer 看见该事件的时间。receipt 不携带 issuer frontier；需要前沿诊断时使用标准 frontier probe。

单元素 receipt 与批量 receipt 使用同一语义：它是 best-effort、set-bound integrity hint，不带协议级过期或序列语义。frontier probe 只能提示已知 scope 的差异，v1 不提供 issuer 漏发/扣发的历史无遗漏证明；equivocation 检测归 Seal 的 `notary_seq`（§7.1），receipt 的本地保留期由部署 retention policy 决定。

Event Batch Receipt 只证明"issuer 看见并承诺所列事件集合的 integrity"，不证明事件有效、不提议排序、不进入控制面 state、不提供范围 completeness。部署 MAY 不签发数据面 receipt；关闭后同账号 RYW 的可验证观察证据与数据面审查诊断能力降低。

## 5. Control Move

Control Move 是写 control plane cell 的 Event，通常 MUST 携带 `seal_basis` 且 MUST NOT 携带 `seal_ref`。v1 只有两个封闭 anchor-unit 例外：

1. [`ak.realm.create`](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative) bootstrap。自体 principal PCR 是 root-signed create + delegated first `ak.device.authorize`；event-derived Realm 使用下列两个互斥封闭分支——v1 **没有**"紧随 create 的封闭 self founding grant"槽位。创建者的 root authority 来自 create 注册 reducer contract 写入的 `ak.component.realm.authority_root.v1` cell；同批 create 之后的 Event MAY 使用绑定同批前序 `ak.realm.create.event_id` 的 staged authority-root proof，batch 之外一律要求 accepted Seal 下的 root-cell inclusion proof（[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)）：
   - 普通 Collaboration 分支必须提交 bootstrap registry 的完整有序闭包：`ak.realm.create`；同批同 actor 的 initial facets `profile → policy_bundle → join_rule → history_access → discovery → optional alias → conditional plaintext_visible_services`；最后是 creator 的 required `ak.member.state{join}`。成员 Event 直接携完整 `member_id: ActorId`，不存在 create 隐式 join 或成员级 route 写入；
   - 1:1 Direct Conversation 分支必须恰好提交 `ak.realm.create → peer ak.member.state{join} → main ak.strand.create → founder ak.member.state{join}` 四条，不得携普通 Collaboration facet。固定 baseline 由 Direct Conversation reducer contract 机械投影；末槽是带 `head_eq null` 的显式 founder genesis membership。Strand 平时是携 `seal_ref + auth_context` 的 DataEvent；但该 exact unit 的 Genesis Seal 覆盖全部四条，无法引用一张尚不存在的 Seal，因此在且仅在该 unit 内免 basis。

   不在该列表内的 Control Move 一律要求 `seal_basis`。
2. B 模型 [`ak.device.reanchor`](../identity/key-management.md) + replacement authorize 原子 unit。它不携带 `seal_basis`，而在 payload 的 `pre_fence_seal_frontier` 固定完整当前 accepted Seal frontier，并由 RecoveryTransaction 对 frontier digest 做 CAS。授权 fence 在完整 unit 验证/提交后立即生效；确定性治理写由首个新-generation Seal 覆盖。

这两个例外不得推广到 batch 外、普通设备入册或其他 Control Move。机器执行闭包分别由 `ak.vector.identity.root_anchor_exclusivity.v1` 与 `ak.vector.identity.device_reanchor.v1` 覆盖。

**无 basis 不等于 DataEvent（normative）**：上述 caller-proven closed anchor unit 中的 Event 仍是
Control Move，并进入 §7.2 的 Control Proposal Ack / pending / bounded-decision 轨道；只有在
`EventSubmitContext=AnchorUnit` 已验证整个封闭有序单元时，wire validator 才可允许
`seal_basis` 缺失而 `control_proposal_ack` 存在。标准上下文中无 `seal_basis` 的 DataEvent
仍 MUST 拒绝该 receipt。实现不得用“anchor 禁止 receipt”或“只有存在 `seal_basis` 才写 pending
Control index”的启发式替代这个上下文判定。

```text
ControlMove {
  event_id / event_digest / proofs
  realm_id
  scope_ref
  actor_id / actor_seq / prev_refs[]
  preconditions[]
  seal_basis {
    leaves[]                     // accepted Seal id, canonical 升序去重
  }
  refs[]
  payload
}
```

Control Move 规则：

1. `seal_basis.leaves[]` 进入 canonical Event bytes，并由 `event_digest` / `proofs[]` 覆盖。producer 不复制 `control_event_set_root` 或 `state_root`。
2. `leaves[]` MUST 只引用 accepted Seal，按 unsigned-byte order 严格排序、去重。单 leaf basis 是轻 producer 的默认形态。account client 从 `ak.self.seals.read.frontier.v1` 取得完整 current Seal antichain；该来源不可用时 MUST fail closed。
3. 多 leaf basis 只有已验证每个 Seal signature、predecessor closure、control covered set 与 joined state 的 producer MAY 签；轻客户端 MUST NOT 签自己无法验证的 multi-leaf union。旁路 proof bundle只补依赖，不进入 Event digest。
4. reducer contract 的派生写 MUST 只引用 control plane cell。若需同时写 data cell，必须拆成后续 DataEvent。
5. `preconditions[]` 与全部派生写是原子集合；任一 precondition 不成立，整个 Control Move 失败。

### 5.1 Control Move 验证

```text
verify_control_move(M, pre_state):
  1. 验 canonical bytes、event_digest、proofs[] 与 realm_id。
  2. 验 seal_basis.leaves[] 均在接收 Seal 的 predecessor closure 内。
  3. 解析并验证 leaves[] Seal，重算各自 control_event_set_root/state_root，再重建 union covered set 与 joined governance state。
  4. 验 refs[] 中所有 critical ref 已知且 valid。
  5. 对每个 precondition 读取 pre_state 并判定。
  6. 从 kind + payload 派生全部 write，对每项执行 lattice validate_op 与 authz check；DM profile 还必须在同一 seal_basis joined view 求值 participant source 与 root-owner phase mask。
  6b. 对每个命中 cas_register cell 的注册写入，从本 Move 自身签名 seal_basis 重建的 view 派生该 cell 的完整活跃 heads H_c(B)（§9.3.1.1）。
      这是自动派生的身份守卫，不要求 wire 重复携带 head_eq；它在 Seal 接受时按 §6.3 step 8b 与冻结 predecessor 基线逐身份比较。
  7. PASS / FAIL。
```

轻节点可以依赖被引用 Seal 自身 `control_event_set_root` 的 inclusion / non-membership proof 和治理 state inclusion proof 做局部验证；缺 proof 时 MUST fail closed，不得盲信未验证 root。`ak.device.reanchor.pre_fence_seal_frontier` 仍保留 roots，因为它们参与 recovery frontier CAS，不受本节 Event seal_basis 去重影响。

## 6. Seal

Finality profile、控制并发类别、非空 genesis、proposal 有界决议与 `CbaProofBundle` 的权威合同见
[`cba-profiles.md`](./cba-profiles.md)。本文件只定义 Seal 的编码、root 与 reducer 计算。

Seal 是唯一控制状态接受事实。submitted/pending/receipt、snapshot、transparency、
availability 与 compaction 均不得创建第二种 finality。

Genesis Seal 的 `predecessor_refs` 必须为空，但 covered set 不得为空。它必须原子覆盖完整 founding
anchor unit，使 create 的 genesis intent、create 审计日志、founding notary、reducer profile 与 founding
authority root cell（`ak.component.realm.authority_root.v1`）五条投影，以及 profile/policy/membership 显式 facet 同时可从该 Seal 验证；create 的五条即
[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)
登记的 `ak.realm.create` registered write 全集，v1 不含任何 founding `ak.capability.grant`。MLS-backed scope 的 `ak.mls.genesis` 以该 accepted Genesis
Seal 为 `seal_basis`；**首个覆盖该 Move 的后继 Seal** MUST 验证并物化 epoch-0 governance
binding，在该 Seal 之前不得接受 MLS application DataEvent。先接受空 Seal 再补 founding
authority（含 authority-root cell）仍一律 `genesis_seal_invalid`；epoch-0 binding 的这一后继时序不是 founding repair。

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
  sealed_at                   // 签名覆盖的 normative notary commit time；freshness / receipt SLA / projection 输入
  hlc                           // 诊断

  data_view_root?               // observational
  data_event_set_root?          // observational
  availability_receipt_digests[] // signed exact receipt digests；always present
}
```

### 6.0 Seal 运作闭环总览（normative）

Seal 的完整运作闭环固定如下；本总览只汇总本节后续规则，不创建另一套 finality、签名或覆盖语义：

1. producer 先按 Realm schema 与 event-kind registry 把写入分类为 DataEvent 或 Control Move。DataEvent
   携 `seal_ref`，引用一个已经接受的控制面授权视图；Control Move 携 `seal_basis`，冻结其 precondition、
   capability 与 reducer 求值基线。除 §5 登记的 anchor-unit 例外外，二者不得互换字段或跨 plane 写入。
2. Control Move 即使已通过 Event schema、proof、basis 与 proposal admission，也只处于 pending；只有某个
   accepted Seal 把其 `event_digest` 列入 `delta[]` 后，它才进入该 Seal 的递归 `covered_set`、治理 reducer
   与 `state_root`。Seal 被拒绝时，`delta[]` 内任何 Move 都不因此生效。
3. notary 以完整 `predecessor_refs[]` 的 joined governance state 为冻结基线构造 Seal。除 Genesis 例外外，
   `notary_signature` 必须使用该 predecessor view 的 `ak.component.notary.v1` cell 中逐字冻结的 signer
   descriptor；不得查询 current DID document 或用当前同名 verification method 的新 key 替换。包含
   `ak.realm.notary` rotation Move 的 Seal 仍由旧 descriptor 授权并签名，只有其 accepted 后继 Seal 才使用
   rotation 安装的新 descriptor。Genesis Seal 从其 `delta[]` 中唯一完整 Realm anchor unit 的 create notary
   descriptor 取得 founding key。
4. Seal body 签入 `predecessor_refs[]`、`delta[]`、全部 control roots、notary slot/time 与 optional data
   observation roots；`id` 与 `notary_signature` 自身不进入 body。receiver 重算 body hash 得到 Seal id，并用
   第 3 步选出的 frozen descriptor 验同一 body 的签名。因此替换签名不会改变 Seal id，但 current key 对同一
   body 产生的密码学有效签名也不能冒充历史 notary authorization。
5. receiver 按 §6.3 从 predecessor closure 重建 covered set 与 joined governance state，验证每个 delta
   Control Move、registered dependency、quorum、completeness 与 roots，然后原子应用 reducer writes。任一步
   失败均拒绝整个 Seal 且不产生部分治理状态；全部匹配才写入 accepted Seal DAG，并使后继 Seal 可递归继承
   该 `covered_set`。
6. accepted Seal 的控制面承诺不可追溯改写。后发现 Event fork 或完整 digest collision 时，既有 Seal、它当时
   实际应用的 canonical bytes 与确定性 reducer 输出按 §6.3.2–§6.3.3 保留；冲突变体及相关未来推进进入
   quarantine/recovery，不得把 later-arriving variant 重放成旧 Seal 输入，也不得声称旧 Seal 从未覆盖原 Move。
7. DataEvent 不走上述 finality 闭环。它在自己的 proof、actor chain、`seal_ref` 授权与 data reducer 校验通过后
   进入 data DAG；后续 Seal 的 `data_view_root` / `data_event_set_root` 至多证明 notary 观察过某个局部集合，
   不把 DataEvent 加入 `covered_set`、不使其 final，也不能用 omission 拒绝一个原本有效的 DataEvent。

`completeness_root` 是控制面 **listed-set + actor-seq envelope** 承诺，MUST 使用 §6.2.2 的统一 Seal Merkle 组合规则。leaf 集合为当前 `covered_set(S)` 中每个 control-plane actor 的 actor_seq 包络区间；每个 leaf 的 `leaf_data = canonical_json({ "actor_id": <did_core_id>, "from_seq": <integer>, "to_seq": <integer>, "event_digests": [<digest>...] })` 的 UTF-8 字节，其中 `event_digests[]` 是该 actor 在 `[from_seq,to_seq]` 内按 `actor_seq ASC, event_digest ASC` 排列的**已列出控制面 Event** digest。leaf 按 `(actor_id, from_seq, to_seq)` canonical code point / integer 顺序排列。对同一 actor，任一 Seal 相对其**每个 predecessor** 的 interval set MUST 单调：已承诺包络不得收缩，`to_seq` 只能非降，已列 digest 不得删除；DAG 上互不可达的并发 leaf 之间不要求可比。compaction Seal MAY 合并相邻包络，但已列 digest 集合必须逐字节等价。空控制面覆盖集的 `completeness_root` 为 §6.2.2 空树 root。由于 actor_seq 链可混合 data/control event，区间内未列 seq **不声明其 plane，也不证明不存在被扣发的 Control Move**；验证者不得把该 root 宣传为历史完整性证明。控制面已知扣发线索依赖 §7.2 Control Proposal Ack obligation / inclusion list；v1 不提供历史无遗漏证明。Auditor 的 `completeness_monotonic` 只沿每条 Seal predecessor edge 验证包络与 listed-set 非缩，不得把未列 seq 当作可机械验证的 gap，也不得按 transparency `log_index` 相邻项误作线性比较。

### 6.1 Seal id 与签名 transcript

`id = ak:seal:<digest-suite>:<hex>`（与 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) `special_forms[kind=seal]` 的 `wire_form` / `payload_pattern` 逐字一致），`<digest-suite>` MUST 是 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json) 的 active 行且等于该 Realm 的 `digest_algorithm`，`H` 取该 suite 的 hash；hex MUST 等于 `H(seal_canonical_bytes)`。`id` 与 `notary_signature` 不进入 `seal_canonical_bytes`。除这两个字段外，所有顶层字段都进入 canonical bytes 和 signature transcript，包括 `control_event_set_root`、`notary_seq` 与所有 optional observational roots。

Receiver MUST：

1. 重算 `H(seal_canonical_bytes)` 并与 `id` hex 比对。
2. 验 `notary_signature` 覆盖同一 canonical bytes。
3. 拒绝任何非 canonical list order 或重复项；`delta[]` 最多 4096 条，`availability_receipt_digests[]` 最多 65536 条，且完整 Seal canonical body 仍不得超过 8 MiB。

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

`control_event_set_root` 是 Seal、控制面 receipt obligation、inclusion list、censorship evidence 与 seal transparency 的共同锚点。`delta[]` 只是本批新增集合；Control Move 仅用 `seal_basis.leaves[]` 引用该承诺；root 承诺的是递归覆盖集。Compaction Seal MAY 显式携带 `covered_event_digests[]`，但 receiver MUST 验证它等于 `delta[]` 与所有 predecessor 覆盖集的并集。

**compaction 不消除精确 membership 的信息量（normative）**：累计覆盖集 root 压缩的是**承诺**，不是任意 Event 的成员关系。`cas_register` 的合并式（§9.3.1.4）需要判断某个身份是否属于对端的 `C`，因此实现 MUST 在本地索引、共享索引或可验证证明中保留足以精确回答该 membership 的信息；MUST NOT 宣称「只保留一个 root 就能以常数空间精确回答任意 membership」。缺证据时 MUST hold / fail closed，MUST NOT 把「查不到」当成 `false`。

**Compaction 节律是结构性义务（normative）**：因为累计覆盖集由 `predecessor_refs + delta` 递归定义，compaction Seal（携带 `covered_event_digests[]` 或等价可验证全覆盖 manifest 的 Seal）是新 verifier 唯一的有界 bootstrap 物化点。Realm MUST 在 create payload 中声明 `seal_compaction_max_interval_ms`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)，默认 86,400,000 ms；`open_set` 部署 MUST ≤ 24h，`threshold` 部署 MUST ≤ 7d，`single_signer` SHOULD ≤ 24h）。notary 超出声明间隔仍未签发 compaction Seal 时，receiver SHOULD 触发治理健康告警；新 verifier 此时只能退回从 genesis 走链或从最近已验证 compaction Seal 接链。该义务由 conformance vector `ak.vector.cba_lattice.seal_compaction_interval_enforced.v1` 固定。

### 6.2.1 治理 `state_root` 的 Merkle 计算规则（normative）

Seal 顶层的治理 `state_root`（§6 Seal schema、§6.3 step 10 "重算治理 state_root"、§7.1 log entry 中的同名字段）是对**当前 joined 治理状态全部 control cell** 的 authenticated Merkle root。它与 §6.2 `control_event_set_root`、§6.4 三个观测 root 同属一个 Seal 的承诺族，**MUST 使用 §6.2.2 的统一 Seal Merkle 组合规则**（带 `0x00` / `0x01` 域分隔），使一个 Realm 实现可对全部 Seal 级 root 共用同一套 Merkle 代码与 conformance vector 形状，并使 governance root 获得与观测 root 同等的 leaf/node 第二原像域分隔。

leaf 集合与顺序：

- **成员（单一判据）**：一个 control cell 进入 `state_root` leaf 集合，当且仅当它被 `covered(L)` 中某个 Control Move 的注册 reducer contract 命中，且在 joined 治理视图下得到 non-`⊥` 的确定值。data plane cell 不进入 `state_root`。
  - **`cas_register` 例外（normative）**：`cas_register` cell 的成员判据是「该 cell 在 `covered(L)` 下的活跃 heads 集合 `H_c` 非空」。**未写入的 cell 不占 leaf；一旦发生过写入，即使业务值是 `null`、即使 heads 异值处于 `⊥`，该 leaf 也 MUST 出现在 `state_root` 中。** 理由是 §9.3.1.2 把「从未写入」与「释放为 `null`」定义成两个不同的写入状态，而单纯的 non-membership proof 无法区分它们；把 `⊥` 排除在 root 之外同样会让「未写入」与「冲突」不可区分。
  - **`state_root` 只承认注册 reducer 输出（normative）**：未在 canonical reducer contract `cell_writes[]` 登记的隐含写入 MUST NOT 进入 `state_root`、inclusion proof 或轻客户端授权判据。散文中的“顺带写入”没有规范效力。
- **每个 cell 的 leaf 输入**：`leaf_preimage = canonical_json({ "cell": "<cell_wire_id>", "state": <state_object> })`，其中
  - `<cell_wire_id>` 是该 cell 的 canonical tuple 引用 `ak:cell:<component>:<subject>`（[`conformance/encoding.md` §4](../conformance/encoding.md)）；
  - `<state_object>` 在 cell 物化为具体值时为 `{ "value": <lattice_value> }`。`fsm` 与 `cas_register` 一样是因果寄存器（§9.3.1.5），因此**写过的 `fsm` cell 一律进入** `state_root`——包括 heads 异 `to` 处于 `⊥` 的那些——其 `<state_object>` 与 `cas_register` 同形为 `{ "heads": […] }`；未写入的 cell 不占 leaf。其余 `bottom=reject` lattice（`or_set` / `counter` / `mv_register` / `ordered_log` 各自的 `⊥` 形态）落 `failed_bottom`（§9.1.1）的 cell **一律不进入** `state_root` leaf 集；它通过失败状态、冲突 heads 与 §9.5 recovery witness 暴露，不作为治理 root 成员编码。
  - **`cas_register` 的 `state_object`（normative）**：`cas_register` cell 的 `<state_object>` 是完整活跃 heads 的封闭形态

    ```json
    {"heads":[{"event_id":"<EventId>","value":null}]}
    ```

    - `heads[]` 按每个 `event_id` 解码后的 33-octet token（[`../conformance/encoding.md` §4](../conformance/encoding.md)：suite code 字节后接完整 digest 字节）作 unsigned lexicographic 升序排列，身份在数组内唯一；`value` 是该写入的完整 canonical JSON 值。MUST NOT 直接比较 `ak:event:` wire string。该顺序只固定 bytes，MUST NOT 被用来在 heads 之间挑选 winner——异值 heads 一律按 §9.3.1.2 落 `⊥`。
    - MUST NOT 另存冗余的 `settled_value` / `bottom` 字段：业务 settled value 与 `⊥` 判定按 §9.3.1.2 从 `heads` 唯一派生。空 `heads` 不是合法 leaf（未写入的 cell 不占 leaf），因此它与「释放为 `null`」不会混淆。
    - `leaf_preimage`、`canonical_json` 口径与 leaf hash 规则不变；只有 `<state_object>` 的形状与上一条的成员判据改变。
    - 业务读接口 MUST 返回派生的业务值，MUST NOT 把内部 `heads` 数组当作领域值直接返回。
    - 一份有效的完整 CAS state leaf 证明认证的是**完整 heads**；单个 Event 的 inclusion proof 只证明它曾被覆盖，MUST NOT 被用来断言它仍是当前 head。对 multi-leaf view，MUST 先证明每个输入 view 的完整 state 与 `C` membership，再按 §9.3.1.4 重建。
    - 承诺只能检测篡改，不能单独证明计算正确：Seal / snapshot 的接受仍须复算，或满足已登记且明确的验证 / 信任路径。一个 producer 签下任意 `heads` 并不使其成为有效状态。
  - `canonical_json` 按 [`conformance/encoding.md` §2](../conformance/encoding.md)（RFC 8785 JCS 同口径）。
- **leaf hash**：`leaf = H(0x00 || leaf_preimage_utf8_bytes)`（§6.2.2；先取 canonical JSON 的 UTF-8 字节，再前缀 `0x00`）。
- **leaf 顺序**：按 `<cell_wire_id>` 的 Unicode code point 升序排列；树构造本身不再排序（§6.2.2）。

inclusion proof 使用 Merkle audit path，non-membership 使用 sorted-neighbor proof，与 §6.2 / §6.4 同形。空治理视图（无任何 non-`⊥` control cell）的 `state_root` 为 §6.2.2 的 RFC 6962 空树 root。`apply_seal`（§6.3 step 10/11）重算的 `state_root` MUST 按本规则计算并与 Seal 声明值逐字节比对；不匹配 MUST 拒绝（`rejected_seal`）。

### 6.2.2 Seal Merkle 组合规则（RFC 6962，normative）

本节定义 §6.2 `control_event_set_root`、§6.2.1 `state_root` 与 §6.4 三个观测 root **共用**的 byte-level Merkle 组合规则，使一个实现可共用一套 Merkle 代码。`H` 取该 Realm 声明的 hash suite（v1 default-MUST `sha256`，见 [`conformance/encoding.md` §3.1](../conformance/encoding.md)）；wire 输出形态为 `<suite>:<lowercase_hex>`。

- **leaf**：`leaf = H(0x00 || leaf_data)`。各 root 的 `leaf_data` 由其领域规则给出：`state_root` 为 §6.2.1 的 `leaf_preimage` UTF-8 字节；`data_view_root` 为 `canonical_json(KeyView)` UTF-8 字节（§6.4）；`control_event_set_root` / `data_event_set_root` 为对应 `<suite>:<hex>` digest 去前缀解码后的 raw bytes（§6.2 / §6.4）。AvailabilityReceipt 不再构造冗余 root，而由 Seal 的 signed canonical digest list 直接承诺。
- **内部节点**：`node = H(0x01 || left || right)`，`left` / `right` 为左右子节点的 raw hash 输出字节。
- **leaf 顺序**：树构造本身不排序；各领域规则先声明 leaf 顺序（`state_root` / `data_view_root` 按 cell_id code point 升序；`control_event_set_root` / `data_event_set_root` 按 digest wire 值 canonical 升序）。
- **奇数层**：某一层节点数为奇数时，尾节点**原样提升**到上一层，**MUST NOT 复制**（RFC 6962：在不超过当前节点数的最大 2 的幂处分割，右子树可较小）。
- **单 leaf 树**：root 等于该单 leaf 的 `H(0x00 || leaf_data)`（**注意带 `0x00` 前缀**，不是裸 `leaf_data` 的 hash）。
- **空集合**：root 为 `H` over the empty byte string；`sha256` 下即 `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（与 RFC 6962 §2.1 `MTH({}) = SHA-256()` 一致）。

[`conformance/encoding.md` §3.3.1](../conformance/encoding.md) 的 snapshot
`state_digest` 与 event-set commitment 复用本节 byte-level 规则，并只在
`leaf_data` 构造与排序键上作领域特化。实现 MUST 为所有这些 root 使用同一套
`0x00` leaf / `0x01` node 域分隔代码。

### 6.3 Seal 接受规则

```text
apply_seal(A):
  1. 校验 predecessor_refs 均已知、同 Realm、且不是 fork_quarantine。
  2. 校验 notary_seq 单调性和 notary_signature；`sealed_at` MUST 不早于全部 predecessor 的 `sealed_at`。若 `sealed_at` 晚于 verifier 当前时钟加 `hard_future_skew_ms`，进入非终态 `seal_deferred_future_skew`，等待本地时钟推进后从 step 1 重判，不得终态拒绝该 Seal 或其后继。
   2b. 在 predecessor joined governance state 的 `ak.component.notary.v1` cell 上按唯一 `notary.kind` 校验 frozen signer descriptor：`single_signer` 使用唯一 `notary.signer`；`threshold` 使用至少 `threshold` 个互异 `members[]` slot；`open_set` 使用合法 slot descriptor；`mixed` 普通 Seal 使用 primary descriptor，只有 §7.2 / §9.5 / §6.3.2 recovery 条件成立时才可使用 `recovery_members[]` descriptor。§6.3.2 的 dedicated fork-resolution Seal 是该允许集的封闭成员：使用 `recovery_members[]` descriptor 且本 Seal `delta[]` 含任一 `ak.fork.resolution` Move 时，`delta[]` 的每一项 MUST 都是 `ak.fork.resolution`；混入任何其它 Control Move MUST 整体 `rejected_seal`，code=`seal_signer_unauthorized`。该约束是 per-Seal 的封闭性，不禁止 §7.2 / §9.5 各自的 recovery Seal 在自己的 `delta[]` 中携带其对应 kind——recovery signer 不得把无关普通 Move 搭在一份 fork-resolution Seal 上，也不得把 fork resolution 搭在一份 §9.5 cell-recovery Seal 上。没有已登记 recovery 路径的 Realm 保持 fail-closed 死状态，不得回退 primary descriptor 或未签 operator command。每个 descriptor 逐字冻结 `actor_id + verification_method + key_kind + jose_algorithm + frozen_public_key_b64u + frozen_public_key_digest`；controller 投影必须等于 actor_id。配置 admission 对 members、recovery_members 及其交集分别强制 actor_id、verification_method、frozen_public_key_digest 三个维度各自唯一，禁止跨 slot 复用 key digest。`multi_signature.signatures[]` 按 verification_method 字节序、method 唯一；每个 protected `kid` 逐字等于 verification_method，`alg` 逐字等于 descriptor.jose_algorithm；`none`、unknown `crit`、非 canonical protected/base64url/ECDSA 编码与 key_kind/alg 错配一律拒绝。验签不得查询或替换为 current DID key。`ak.realm.notary` 后继 Move 必须先由旧 descriptor 授权，再安装新 descriptor。genesis Seal 的 `predecessor_refs=[]` 例外从本 Seal `delta[]` 中唯一完整 Realm anchor unit 的 create notary descriptor 求值。不满足时 MUST `rejected_seal`，code=`seal_signer_unauthorized`。
  3. 校验 delta[] canonical 升序去重及 4096 条上限；超限在签 Seal 前拒绝。
  4. 校验 delta[] 与所有 predecessor covered_set 不相交。
  5. 校验 delta[] 每项都是已知、签名有效、且未被本 Seal predecessor closure 覆盖的 Control Move digest；若 predecessor joined governance state 的 effective `availability_policy.applies_to` 含 `seal_include`，还 MUST 验证 `availability_receipt_digests[]` canonical 升序且恰好包含每项所需、无多余的 full canonical AvailabilityReceipt digest，数量不超过 65536，并经 typed governance-dependency resolve 取得完整 receipt 与 holder signer evidence，验证 holder 数、role 与 retention 下限
     （"尚未 sealed" 的判定范围见下方并发 leaf 规则）。`predecessor_refs=[]` 的唯一 genesis Seal 没有 predecessor availability authority，其 `availability_receipt_digests[]` MUST 为空，receiver MUST NOT 从本 Seal `delta[]`、本批 reducer projection、软件默认值或 current Realm state 臆造 policy / eligible holder 并执行 availability gate；genesis 接受后物化的默认或显式 availability policy 从引用该 genesis 的首个 successor Seal 起生效。本例外只跳过不存在的 predecessor availability gate，不跳过 genesis 的 Event proof、notary、coverage、completeness、state-root 或 registered reducer 校验。
  6. 计算 covered_set(A) = delta(A) union predecessor covered sets。
  7. 校验 control_event_set_root == root(covered_set(A)).
  7b. 从 covered_set(A) 按 §6 的 per-actor interval 规则重建 leaf 集，使用 §6.2.2 重算 completeness_root 并逐字节比对；不匹配则拒绝该 Seal。
  8. 在 predecessor joined governance state 下批量 verify_control_move(delta[])
     （"批量"= delta[] 内每个 Move 的 preconditions[] 均对**同一冻结 predecessor 基线**求值，
      同批前序 Move 的 projected write MUST NOT 提前进入后续 Move 的 precondition 基线；与 §6.3.1 step 3 同一 frozen-baseline 规则）。
   8b. 对 delta[] 中每个命中 `cas_register` cell 的注册写入，按 §9.3.1.3 第 3 项执行**完整 heads 守卫**：
      该 Move 自身签名 `seal_basis` 重建的 `H_c(B)` MUST 逐身份等于冻结 predecessor 基线的 `H_c(P)`；
      不相等即 stale，MUST 以 `failed_precondition` 拒绝该 Move（并按 step 9 拒绝整个 Seal），
      即使两边业务 settled value 相同。该守卫对每个注册目标自动派生，不要求 wire 重复携带 `head_eq`。
  9. 任一 Control Move 失败则拒绝整个 Seal。
  10. 原子应用由 Control Move kind + payload 派生的注册 reducer writes，重算治理 state_root。
  11. state_root 匹配则接受；否则拒绝并生成 seal fault 诊断。
```

Seal 被拒绝时，其 `delta[]` 内 Control Move 不因此有效。节点 MAY 保留这些 Move 作为 pending / diagnostic 输入，但 MUST NOT 让它们推进 query 或授权。

`apply_seal` 对给定已验证依赖集合的终态结果 MUST 是纯函数。本地墙钟只决定 `seal_deferred_future_skew` 何时重新求值，不得把同一个 cryptographically valid Seal 永久分成“某 receiver 接受、另一 receiver 拒绝”两种终态。

**并发 leaf 覆盖同一 pending Control Move（normative）**：步骤 5 中 "尚未 sealed" 的判定范围**只**是本 Seal 的 predecessor closure，即步骤 6 递归并集所得的 predecessor `covered_set`——等价于步骤 4 的不相交校验；receiver **MUST NOT** 以自身全局已接受 Seal 集合作为判定范围。特别地，`open_set` profile 下某 Control Move 已被另一个**并发**（不在本 Seal predecessor closure 内的）已接受 Seal leaf 覆盖时，receiver **MUST NOT** 因此拒绝本 Seal；否则接受结果将随 leaf 到达顺序变化，产生永久分叉，违反 §6.3.1 "`J(L)` 是 `L` 的纯函数、与到达顺序无关" 的收敛保证。同一 Control Move 被多个并发 leaf 覆盖是合法状态：`covered(L)` 按 Control Move digest 内容寻址取并集，重复覆盖自然去重，join 结果不受影响。

#### 6.3.1 Deterministic joined control view（multi-leaf join，normative）

`notary.kind=single_signer|threshold` 下 Seal 单链唯一，任一时刻只有一个 control head，"当前治理状态"无歧义。`notary.kind=open_set` 允许多个并发 Seal leaf；[`../sync/federation.md` §2.4](../sync/federation.md) 与 realm.schema 据此引用的 **"deterministic joined control views"** 即指本节定义的 join；它是 §4.3 并发分支撤销重判、§6.4 观测承诺与跨 receiver 收敛的共同基准:

给定 receiver 已观察、已 `apply_seal` 接受、且**非** `fork_quarantine` 的全部 Seal leaf 集合 `L = {S_1, …, S_n}`，joined control view `J(L)` 按以下确定性步骤计算，对任意观察到相同 `L` 的 receiver 结果唯一:

1. **覆盖集并集**:`covered(L) = ⋃_i covered_set(S_i)`（§6.2 递归覆盖集的并集）。因 `covered_set` 仅取并集、Control Move digest 内容寻址，`covered(L)` 与 leaf 到达顺序无关。
2. **Move 应用偏序**:`covered(L)` 内的 Control Move 按其 Seal DAG 因果序构成偏序；线性（有因果先后）的 Move 按因果序应用。
3. **并发 Move 的 canonical 枚举顺序**:对偏序中**互不可达**（并发）的 Control Move，按 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的 producer-biased canonical presentation order 升序枚举。该顺序只固定重放与诊断 bytes；per-cell join 的输入仍是完整 Move 集，任何读路径都不得据此选择“最大 head”。
   - **precondition 求值基线（frozen predecessor，normative）**:每个 Move `M` 的 `preconditions[]` **MUST** 对 `M` 在 `covered(L)` 内**因果前驱**的 joined 治理状态求值——即冻结在"`M` 及所有与 `M` 并发的 Move 尚未应用"的那个 predecessor 基线上；线性化中排在 `M` 之前的**并发** Move 的 projected writes **MUST NOT** 进入 `M` 的 precondition 求值基线。这与全协议 CBA basis 规则同一（`ak.vector.cba_lattice.same_batch_does_not_advance_authorization_basis.v1`）:同批 / 并发前序 writes 只提供原子提交便利，不自我满足后续 precondition。
   - **对强一致 cell 的后果**:因此同一 `cas_register` / `fsm` cell 上的两个并发互斥写**都**通过各自 precondition（都看见同一冻结基线），在 step 4 join 到 `⊥`——枚举顺序 **MUST NOT** 被用来给任何治理或数据 domain 静默选出单一 winner。
   - **同 Seal 排重义务（normative）**：notary 能同时观察同一拟议 `delta[]`，因此对命中同一 `bottom=reject` cell、且在冻结基线下 projected writes 互斥的 Move，MUST 至多 include 一条；其余 MUST signed-reject（`reason_code="cas_conflict"`）或 defer 到后续 Seal 重新按新 basis admission。`apply_seal` MUST 重算此条件；同一 Seal 覆盖两条此类互斥 Move 时整个 Seal MUST `rejected_seal`，不得先把 cell join 到 `⊥`。该义务不为 Move 选择协议 winner：notary 可以拒绝全部，也可以依其公开调度 policy 选择至多一条；跨不可达 Seal leaf 的真正并发仍按 step 4 / §9.5 产生 `⊥`。
4. **per-cell Lattice join**:每个 control cell 按其声明的 lattice（§9）合并 `covered(L)` 中所有命中该 cell 的 Move 效果；`cas_register` / `fsm` 等强一致 cell 上的并发互斥写按 §9.1.1 进入 `⊥`（`bottom=reject` 则该 cell 物化为 `failed_bottom`，依赖它的后续 Move fail closed，按 §9.5 conflict-recovery 解析）。
   - **`cas_register` 的合并形态（normative）**：本步对 `cas_register` 求值的是 §9.3.1.1 的完整状态 `(C, H_c)`，多 leaf 之间按 §9.3.1.4 的合并式求最小上界，**不是**对业务值或 Bottom 标签取并。写过的 `cas_register` cell（含业务 `null` 与异值 `⊥`）按 §6.2.1 的 `cas_register` 例外**进入** `state_root`。`⊥` 状态下**普通** Control Move 仍不能写该 cell（§9.3.1.3 与 §9.1.1「`⊥` 不是本地粘滞标志」一段：普通写入不得以含异值 heads 的签名 basis 写入），唯一出路是 §9.5.1 的 conflict-recovery Move；但一个只观察到部分分支的 receiver **MUST NOT** 把 `⊥` 记成永久标志——它在补齐 leaf 后按本式重新求值。
   - **其它 `bottom=reject` lattice（典型 `fsm`）**：落 `⊥` 的 cell 是治理终态，**不进入** `state_root`（§6.2.1）;它**不能**被普通后续 Control Move 收敛，唯一出路是 §9.5 的 conflict-recovery Move。
5. **结果**:`J(L)` 是所有 control cell 的 join 结果集合；它就是 receiver 在 step 8 `verify_control_move` 与所有授权判定（capability / membership / policy）所用的 "predecessor joined governance state"。

`J(L)` 是 `L` 的纯函数（不依赖到达顺序、本地时钟或接收方身份），因此观察到相同 leaf 集的 receiver 得到逐 cell 相同的治理状态；leaf 集不同的 receiver 在缺失 leaf 补齐后收敛到同一 `J`。compaction Seal（§6.2）把 `covered(L)` 物化为有界 bootstrap 点，使新 verifier 无需重放全链即可重建 `J`。

#### 6.3.2 已 Seal Control Move 与后发现 fork 的衔接（normative）

accepted Seal 的 `covered_set`、`control_event_set_root`、`completeness_root` 与 `state_root` 是不可追溯改写的签名承诺。某个已覆盖 Control Move 后续因同 `event_id` 双变体或 actor over-fork 被检出时，receiver MUST quarantine 全部原始 sibling bytes，但保留已被 accepted Seal 覆盖的 digest 与确定性 reducer 输出作为该历史 Seal 输入。

唯一 DID-root recovery 例外：合法 `ak.device.reanchor` 的 `pre_fence_seal_frontier` predecessor closure 内的历史 Seal/Event 完整保留；closure 外、仅由旧 device generation 签发的 Event/Seal 保留原始 bytes 但进入 `fork_quarantine`，不得进入当前 joined view。该例外改变的是旧 generation 对**当前** view 的贡献，不改写 closure 内任何 accepted Seal 承诺。首个新-generation Seal 必须以 `pre_fence_seal_frontier` leaves 为精确 predecessors，delta 覆盖 re-anchor unit；不满足不得成为 accepted Seal。

该状态下 receiver MUST 对受影响 `(actor_id, actor_seq)` 之后的 Control Move fail closed，直到有 fork-resolution capability 的主体按 federation §4.5 证据签发 recovery / fork-resolution compaction Seal。该 Seal 的 `delta[]` MUST 覆盖唯一的 `ak.fork.resolution` Control Move；其 closed payload 由三部分构成：`subject` 是被裁决的争议对象、`conflict_evidence` 是证明该对象确实处于争议的**有界最小证据集**、`verdict` 是 `canonical_winner` 或 `void_all`。`subject` MUST 是整个 `(realm_id, actor_id, actor_seq)` 位置（`event_sibling_position`，Realm 取自本 Event envelope）或一个碰撞 `event_id`；`prev_frontier_digest` 属于 evidence，MUST NOT 进入 subject——否则同一位置的单桶越界与跨桶越界会形成两个可给出不同 winner 的 resolution cell。证据集的基数由 v1 上限唯一决定：单桶越界恰 17 条 `event_ids[]`，跨桶越界恰 65 条，领域不可 join 为 2..64 条并携已登记 `cell_family`（receiver 从 registry 取该 family 的 lattice 重跑不可 join 事实，不信任 producer 自报）。**授权唯一 MUST 是恰一个 critical `refs[]` `role=recovery_capability`**，其 action 精确为 `ak.fork.resolution`；可选 `attestation` / `inclusion_proof` refs MAY 作为补充证据；`role=state_witness` MUST 被拒绝——它在 §9.5 的语义是"见证 cell 在 `⊥` 之前的合法单值"，而本 cell 首次写入前没有任何活跃 head（§9.3.1.2 读作 `null`），不存在可见证的冲突前单值，因此 MUST NOT 复用 `recovery_witness_missing` 等 §9.5 reason。该拒绝与 §9.5.1 删除 `cas_register` recovery 的 witness 强制依赖同向。该 Move 按普通 `apply_seal` 与 `verify_control_move` 管线写入 `ak.component.fork_resolution.v1` cas-register cell，`cell_subject` 只由 `subject` 决定；不得扩展 Seal 顶层或新增独立 clear authority。sibling winner MUST 以 `event_id` 指认且 MUST 属于本 Move 自身的证据集；`void_all` 使该 Realm 内该位置的全部当前及未来变体终局作废，后到变体 MUST NOT 复活它——该 actor 的 authoring chain 因此停在被作废位置之下，所以 `void_all` 只在不存在任何合法变体时正确。**裁决不可被顺序改判（normative）**：该 Move MUST 携带目标 `ak.component.fork_resolution.v1` cell 的业务 precondition `head_eq: null`（登记于 event-kind registry 中 `ak.fork.resolution` 的 `admission_checks[]`）。该 cell 在写入基线下已有 settled value 时，第二条因果后继 resolution MUST 以 `failed_precondition` 拒绝；同一 Event 的 exact replay 仍按 EventId 幂等。§9.3.1.3 自动派生的完整 heads 守卫**不**覆盖这一条：一条 basis 已包含前一次裁决的后继满足 `H_c(B) = H_c(P)`，若无本条断言就能把 `canonical_winner` 改成另一个 winner 或 `void_all`、把 `void_all` 改回 `canonical_winner`，使上一句的「终局」在规范内部自相矛盾，并让 §4.5 的 per-peer alignment 在没有任何新证据时被重算。该 cell 落入 `⊥` 时 `head_eq` 按 §9.3.1 fail closed，因此本条不挡 §9.5 的恢复路径：并发冲突走 `ak.conflict.recovery`，顺序改判一律禁止。归一结果从 predecessor 已承诺状态写入后继，不能声称旧 Seal 从未覆盖原 Move。notary 在签发普通 Seal 前 SHOULD 检查 `delta[]` 中每个 Move 的已知 sibling 桶和跨桶累计计数，已越界者 MUST NOT 纳入普通 Seal。

#### 6.3.3 已 Seal Control Move 的完整 digest collision（normative）

上一节按 sibling **digest 可区分**书写：actor over-fork 的各 sibling 有不同 `event_digest`，因此“列出冲突 sibling digest 集、选定 canonical digest”是可执行的。同一 suite 下两个不同 canonical preimage 重算出同一
`event_id`（[`operations-sync.md` §12](../sync/operations-sync.md)）时该前提不成立：两个变体的
`event_digest` 逐字节相同，`covered_set`、`control_event_set_root` 与 `completeness_root` 里的 digest 无法指认 Seal 当初覆盖的是哪一个 preimage。因此本节在 §6.3.2 之上补充：

1. **归一裁决 MUST 按 canonical bytes 指认，不得按 digest 指认。** `subject.kind=event_id_collision` 时，`conflict_evidence.kind` MUST 是 `full_hash_collision` 且恰含两个 locator；两个 locator 解出的完整 canonical Event bytes MUST byte-distinct、各自独立通过结构 / suite 前置检查并重算为同一完整 `event_id`。**locator 携带的是 Event 的 digest 原像**（[`../conformance/encoding.md` §4](../conformance/encoding.md)：该原像按定义不含 `proofs` / `unsigned` / `event_id`），所以这里的 proof 校验指的是承载证据的 `collision_variant_record` 自身的 proof（下面第 2 段），**不是**被裁决 Event 的 producer proof——后者不在证据里，也不可能在。第 3 点说明它为什么不必在。locator 是封闭 XOR：`inline_canonical_bytes` 直接内联，或 `collision_variant_record` 引用 `ak.schema.collision_variant_record.v1`。**reference 分支是必需的而非便利**：接近 1 MiB 上限的原 Event 再经 base64 内联必然使 resolution Event 自身越过 §2.1.1 的 1 MiB 边界，那样的碰撞将不可裁决。引用时 payload 签入 `collision_variant_record_id` 与 `collision_variant_record_digest`；receiver MUST 经 `ak.self.seals.read.governance_dependencies.v1` / `ak.peer.seals.read.governance_dependencies.v1` 的 `collision_variant_record` selector 取得完整 record，重算 `collision_variant_record_digest = <Realm active suite>(JCS(record))`——原像是**含 `proof` 的完整 canonical record**，与 proof 自身的 `payload_digest`（其原像删去 `proof`）是两个不同摘要，不得互相代入——并与 locator 签入的值逐字比对；随后校验其 proof（context `ak.collision_variant_record_proof.v1`，controller 等于本 Move 的 `executed_by ?? actor_id` 且为已验证 recovery-capability 持有者）、`realm_id` 等于本 Event Realm、解码 bytes 长度与 `canonical_event_size_bytes` 一致、并独立重算出 `collision_event_id` 后，才可继续 `apply_seal`；record 缺失是 typed dependency missing，record 非法则拒绝 Seal。record 不进入 Seal `covered_set`——Seal 覆盖的是引用它的 resolution Move。`verdict.kind=canonical_winner` MUST 以 `winner_index ∈ {0,1}` 指向同一 Move 的 `conflict_evidence.variants[winner_index]`；该 locator 解出的完整 bytes 就是 winner，verdict 不得再携第三份 locator 或 preimage。`void_all` 明确作废本 Realm 内整组。receiver MUST 拒绝仅以 `event_id` / `event_digest`、另一 suite discriminator、长度或局部 byte slice 指认胜出变体的 Move，reason code `witness_disagreement`：在碰撞 suite 下这样的裁决没有指称。碰撞组可能跨 Realm；本 Move 只治理其 envelope `realm_id` 内的投影，winner MUST 是其 canonical bytes 内 `realm_id` 等于本 Realm 的变体，其它 Realm 由各自恢复权威独立裁决。
2. **不得事后重算历史 Seal 输入。** receiver MUST 把该 Seal 已物化的确定性 reducer 输出与它当初实际应用的 canonical bytes 一起钉住，并 MUST NOT 在检出碰撞后用任一变体重新推导它。未保留当初 bytes 的 receiver MUST 把该 Seal 覆盖区间视为不可验证并 fail closed，直到归一裁决到达；它 MUST NOT 用任取一个变体重算出的 `state_root` 冒充原承诺。
3. **accepted `canonical_winner` 是 winner bytes 的准入 authority（normative）**：该 Move 由 recovery capability 授权、被 accepted Seal 覆盖，并逐字承载 winner 的完整 canonical bytes，因此它自身就是准入依据。receiver（包括**只持有 loser** 的 receiver）MUST 在应用该 resolution 时，把 `conflict_evidence.variants[winner_index]` 解出的完整 canonical bytes 作为该 `event_id` 在本 Realm 的 accepted 变体，MUST NOT 因为本地已存在另一份同 `event_id` 的 bytes 而报 `witness_disagreement` 或再次整组 quarantine。准入前 MUST 独立重跑该 winner 自身的前置检查：结构与 schema、Realm 声明的 suite、`realm_id` 等于本 Realm、以及重算出的 `event_id` 逐字等于被裁决的 ID；任一项不成立 MUST 拒绝该 resolution 并保持原状态，MUST NOT 部分应用。

   **proof 从哪里来（normative）**：winner 的 producer / station-admission proof **不在证据里**——locator 携带 digest 原像，而原像按定义不含 `proofs`。它也不需要在：这两类 proof 绑定的是 `event_digest`，而碰撞的两个变体按定义算出**同一个** `event_digest`，因此 receiver 对该 `event_id` **已经持有并已验证过的** proof 集合对 winner bytes 原样成立。receiver MUST 复用它，并在准入时按 winner bytes 重新执行 proof binding 校验——这不是空转：若 verdict 指认的 bytes 算出别的 digest，该校验正是拒绝它的地方。receiver MUST NOT 为 winner 补签、重签或省略 proof。**准入后本地存储的 Event（normative）**：其 digest 原像逐字节等于 winner locator 解出的 bytes；`proofs` / `unsigned` / `actor_kind` 沿用 receiver 对该 `event_id` 已验证的既有值，MUST NOT 从 loser 原像重新派生。这些字段本就在原像之外（[`../conformance/encoding.md` §6](../conformance/encoding.md) 的 preimage 排除清单），因此该 Event 的 `event_digest` 与 `event_id` 不变，`covered_set` 与历史 `state_root` 不受影响。一个对该 `event_id` **一个变体都不持有**的 receiver 没有可准入的对象，它按普通 backfill 路径取 Event，不走本条。loser bytes MUST 作为 forensic 变体保留在碰撞 bucket 内，MUST NOT 进入 accepted 读取面；loser 派生的 writes 按 [`../sync/operations-sync.md` §12](../sync/operations-sync.md) 的既有移除规则处置。该准入不重算任何历史 Seal 的 `state_root` 或 reducer 输出（第 2 点）。已持有 winner 的 receiver 应用同一裁决是幂等 no-op。`void_all` 裁决后该 `event_id` 在本 Realm **没有** accepted 变体，后到的任一变体 MUST NOT 复活它。

   本条明确**不**采用两条替代方案：MUST NOT 让 receiver 经 peer 回填 winner bytes 再自行覆写（回填路径会先触发 §12 的碰撞检测，且各实现对 `received_at` / outbox / projection 的处置必然分叉），也 MUST NOT 把 collision 分型的 alignment 收缩为「只对原本就持有 winner 的 peer 可判定」（那会让 [`../sync/federation.md` §4.5.3](../sync/federation.md) 第二阶段对该分型形同虚设，只剩 operator 手工解除）。**准入的确定性元数据（normative）**：这样准入的 Event 的本地接收时间戳 MUST 取该 resolution Move 所在 Seal 的 `sealed_at`，其派生 projection MUST 与「本地一直持有 winner」的 receiver 逐字节一致——准入结果因此是 `(winner bytes, resolution Seal)` 的纯函数，不依赖本地历史。

4. **碰撞区间不得被 compaction 跨越。** compaction Seal 的意义是给新 verifier 一个有界 bootstrap 物化点（§6.2）。区间内存在未归一的完整 digest collision 时，notary MUST NOT 签发跨越该区间的 compaction Seal——新 verifier 无法从 digest 重建被覆盖的 preimage，物化点因此不可复现。归一裁决自身承载 canonical bytes，可以是 compaction Seal。
5. **跨 suite discriminator 只是诊断。** 实现 MAY 对同一 canonical preimage 另算一个**不同** active suite 的 digest 作为紧凑区分符；由于 `blake3` 是 profile-gated 的 `v1_optional_interop`（[`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)），它 MUST NOT 成为裁决的唯一指称，也 MUST NOT 成为对端验证该裁决的前提。

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
- `availability_receipt_digests[]` 不是 Merkle root：它是 Seal 直接签名的 full canonical AvailabilityReceipt digest 列表，只能包含本次 `delta[]` admission 所需 receipts，canonical 升序、无重复、无多余。
- 三者的 inclusion proof 使用 Merkle audit path，non-membership 使用 sorted-neighbor proof——与 §6.2 `control_event_set_root`、§6.2.1 `state_root` 的证明形态一致，实现可共用 §6.2.2 的 Merkle 代码。v1 core 只规定 root 的计算语义；若 deployment profile 或具体 operation 需要传输观测证明，必须由该 profile / operation 另行登记 wire schema 与验证规则，不存在跨所有 query 响应通用的观测证明对象。

这些字段是 observational：

- 未进入 `data_view_root` / `data_event_set_root` 的 DataEvent 不因此无效。
- `data_event_set_root` / `data_view_root` 的 observation evidence 只表示某个 seal 见过并承诺过该局部结果；未来未观测的有效并发 DataEvent MAY 改变该 data cell 的 join。
- Receiver MUST NOT 用 observational roots 拒绝有效 DataEvent。

### 6.5 Notary control cell（normative）

每个 Realm 恰有一个 protocol-singleton cell `ak:cell:ak.component.notary.v1:null`，其 value shape 与 `realm.schema.json` 的 `notary` 相同，lattice=`cas_register`、bottom=`reject`、plane=`control`。genesis value 由 `ak.realm.create` 的注册 reducer projection 从 `payload.object.notary` 写入；后继值只能由 `ak.realm.notary` Control Move 写入，并以当前 head 作 CAS。实现不得通过未登记 kind、部署私有端点或数据库直写改变该 cell。

### 6.6 Realm reducer-profile control cell（normative）

每个 Realm 恰有一个 protocol-singleton cell `ak:cell:ak.component.realm.reducer_profile.v1:null`，value 是 [`reducer-profile-registry.json`](../../artifacts/registry/reducer-profile-registry.json) 中 active `ak.reducer.*` profile ID，lattice=`cas_register`、bottom=`reject`、plane=`control`。

Genesis value 由 `ak.realm.create` 的注册 reducer projection 从 `payload.object.reducer_profile` 写入；后继值只能由 `ak.realm.upgrade` 写入同一 cell。Upgrade payload 只携带 `target_reducer_profile`，并且 Event 的 `preconditions[]` 必须包含 `{cell_id:"ak:cell:ak.component.realm.reducer_profile.v1:null", predicate:{op:"head_eq", value:<source-profile>}}`。Target 未注册时返回 `unsupported_profile`；registry 没有 source→target `upgrade_edges` 时返回 `failed_precondition`；cell 为 `⊥` 时按 §9.1.1 返回 `failed_bottom`、reason=`cell_in_bottom_state`。

Profile view 必须逐 Event 求值：DataEvent 使用 `seal_ref` 认证的 joined control state；Control Move 使用 `seal_basis` 指定的 frozen predecessor `J(L)`。`ak.realm.upgrade` 自身由 source profile 解释；只有 governance basis 已包含该 accepted upgrade 的后继才由 target profile 解释。与 upgrade 并发且 basis 不含它的 Event 仍使用 source profile。实现不得读取本地 latest profile、软件默认值、接收顺序或 Event 自报字段。

同一前驱上的并发互斥 upgrade 按 §9.3.1 的 `cas_register` join 进入 `⊥`；恢复只使用 §9.5 的 `ak.conflict.recovery`。不得为 profile 另设 epoch、frontier、CAS 或冲突算法。若 target row 与 edge 已知、upgrade 在 source profile 下有效，但本 build 未实现 target reducer，receiver 仍接受 upgrade 并把验证 frontier 推进到该 Event；target-profile 后继返回 `unsupported_profile` 且不得进入 accepted state。

## 7. 问责、审查与 transparency

### 7.1 Signer slot 与 equivocation

每个 notary signer 维护自己的 `notary_seq`。同一 signer 对同一 `(realm_id, notary_seq)` 签出两个 canonical bytes 不同的 Seal，或 `notary_seq=k+1` 不以自身 `notary_seq=k` 为 DAG 祖先，构成 equivocation。

Equivocation evidence 是普通 Control Move，event kind 为 **`ak.notary.fault.equivocation`**（已注册于 event-kind registry；payload schema 见 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) `notary_fault_equivocation_payload`：`{signer_id, seal_a, seal_b}`），写入专用 `ak.component.notary_fault.v1` control cell（`or_set`，bottom=expose）。授权条件是两个满足 slot 规则的冲突签名本身；验签即授权，无需额外 capability，reducer MUST NOT 要求 grant。

接受 fault 记录后：

- receiver MUST 拒绝 fault signer 后续 Seal；
- 冲突 slot 中两个 Seal 及其后继进入 `fork_quarantine`；
- fork resolution 前，普通 joined governance view MUST NOT 纳入 quarantined Seal；
- 仅 fork-resolution compaction Seal 或 genesis recovery path 可恢复推进。

**以 quarantined Seal 作 `seal_ref` 锚点的 DataEvent（normative）**：当一条 DataEvent 的 `seal_ref` 指向已进入 `fork_quarantine` 的 Seal 时，receiver MUST NOT 用该 quarantined seal 的授权状态接受它进入 joined view，也 MUST NOT 直接按 `seal_ref_stale` 永久拒绝（quarantine 是控制面分叉、未必表示该 DataEvent 的授权基准非法）。receiver MUST 把它降级保持 **observed-only**（§13 `data_observed`，不参与 join、不投影为生效内容），并 hold pending 直到该 slot 的 fork resolution 产生胜出分支：
  - 若 `seal_ref` 的 Seal 属**胜出分支**（resolution 后不再 quarantined），receiver MUST 用胜出分支下的授权状态按 §4.2 / §4.3 **重判**该 DataEvent，通过则正常接受；
  - 若 `seal_ref` 的 Seal 属**落败分支**（resolution 后被弃），receiver MUST 按 `seal_ref_stale` 拒绝或隐藏该 DataEvent，producer 需以胜出分支的新 `seal_ref` 重新签发。

  该处理与 §4.3 撤销新鲜度判定正交（前者针对控制面分叉，后者针对单链撤销），与 [`../sync/operations-sync.md`](../sync/operations-sync.md) 的 observed-only / backfill 保持语义（observed-only 的 DataEvent 不进 canonical join），不引入新状态。

Threshold signer 使用委员会级 slot。若 2k > n，两个 threshold 签名的 quorum 交集可指认至少一个双签成员；否则部署 policy MUST 声明放弃自动指认。该声明是机器可校验项：threshold notary 的 Realm create payload MUST 携带 `notary.forensic_attribution ∈ {quorum_intersection, waived}`（[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)），且取值与 `2k>n` 的算术关系由 reducer 校验、由 conformance vector `ak.vector.cba_lattice.threshold_forensic_attribution.v1` 固定。本条判据是**事后指认**：`2k>n` 保证共同成员存在且必然双签，共同成员是否诚实不影响可指认性。[`cba-profiles.md` §2](./cba-profiles.md) 的 barrier 串行化另有更强的 `2k > n + f`，要求交集中至少有一个**诚实** signer；两条不等式服务于不同断言，MUST NOT 互相代入，也 MUST NOT 因为一方不成立而放松另一方。

### 7.2 控制面 Control Proposal Ack 与 inclusion obligation

除 [`cba-profiles.md` §4](./cba-profiles.md) 定义的 authority-authored human
self-principal PCR Move 外，控制面 pending Control Move MUST 在 `proposal_intake_sla_ms` 内得到签名
Control Proposal Ack（控制提案签收）或签名 rejection。该例外已由 current accepted device 作为
exact Move 的 author/authority，不产生第二份 Ack 或 decision deadline，但仍必须进入 pending Control
index，并且只有 accepted successor Seal 能使其生效。**`ak.device.revoke` 明确不属于此 Ack-less 例外**：为使可验证 `signed_reject` 始终具有唯一 `proposal_ack_digest`，每个 accepted revoke 都 MUST 将 canonical Ack 与 accepted Event、derived exact device/generation record、pending index 原子持久化；无有效 Ack 时零写入。`proposal_intake_sla_ms` 的权威字段是
[`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的 `proposal_intake_sla_ms`（integer，毫秒，`default 86400000`（24h），`minimum 0`，v1 wire hard `maximum 86400000`），与 `seal_compaction_max_interval_ms`（§6.2）同量级；其 wire 上限登记于 [`scalability-constraints.md`](../conformance/scalability-constraints.md) §4。SLA 计时以 notary 签署的提交时间为准（与 §4.3 `distance` 同源），不用本地接收时间。

**Proposal 有界决议（normative）**：`proposal_intake_sla_ms` 只管「多久确认收到」。authority
接受 proposal ingress 后签发的 Ack 还 MUST 承诺：

```text
proposal_digest, received_at, decision_due_at, absolute_due_at,
defer_count=0, authority_set_ref, authority_acks[]
```

机读合同为
[`control-proposal-decision.schema.json`](../../artifacts/schemas/control-proposal-decision.schema.json)。
`ak.self.events.command.submit.v1` / `ak.peer.events.command.submit.v1` 对 accepted 或 byte-identical
duplicate Control Move MUST 在 `EventsSubmitOutcome.control_proposal_acks[]` 返回已持久化的
原 Ack；authority-authored self-principal PCR Move 必须省略该数组项，DataEvent 也不得进入该数组。
重复提交不得重签或延长任何 deadline。
Realm 的 `proposal_decision_window_ms` 给出首个决议窗口（default 30,000ms，协议硬上限
24h），`proposal_absolute_deadline_ms` 给出从 signed `received_at` 起不可延长的绝对窗口
（default 90,000ms，协议硬上限 72h），`max_proposal_defers` 给出 defer 次数上限
（default 2，协议硬上限 2）。profile / deployment MAY 声明更短窗口或更少 defer，
不得放宽协议硬上限。`ak.realm.create` 与任何更新这些 Realm 参数的 Control Move 在写入前
MUST 校验 `proposal_decision_window_ms <= proposal_absolute_deadline_ms`；违反时整个 Event
MUST 以 `schema_violation` 拒绝。若 `max_proposal_defers > 0`，两者 MUST 严格小于，以保证
至少存在一个严格递增且不晚于 `absolute_due_at` 的 defer deadline；两者相等时
`max_proposal_defers` MUST 为 `0`。该判定基于签名 payload 与冻结 basis，是所有 reducer
必须执行的确定性跨字段校验。

**外部 authority Ack set（normative）**：当接收 Event 的 Station 不持有当前
notary authority，或单个 signer 不能满足 threshold/mixed quorum 时，它不得用服务密钥代签。
proposal author 必须对每个真实 authority 使用
`ak.self.control_proposal_acks.command.issue.v1` 的 typed request；本地 Agent/device signer
使用完全相同的 request、canonical digest 与 outcome transcript，只省略 HTTP hop。每个
authority 独立验证最终签名 Event、AuthorizationLease、genesis/basis 当前 notary policy、
Realm、`proposal_digest`、signer membership 与 deadlines，随后签发一次
`ControlProposalAuthorityAck`。同一 `(proposal_digest, authority_set_ref, verification_method)` 的
byte-identical retry MUST 返回首次持久化的 authority Ack；不同 Event bytes、authority set
或时间字段 MUST `duplicate_conflict`，不得重签延长期限。

member签名 transcript 是
`JCS({context:"ak.control_proposal_authority_ack_proof.v1",
payload_digest:SHA-256(JCS(authority_ack_without_signature)),verification_method,
created_at:received_at})`；proof的`payload_digest`与`created_at`必须逐字匹配，禁止签任意摘要后
只比较字段。每个member的`decision_due_at`必须恰等于
`received_at + proposal_decision_window_ms`，`absolute_due_at`必须恰等于
`received_at + proposal_absolute_deadline_ms`；所有加法按UTC instant计算，溢出或超协议上限拒绝。

author 将互异 authority Ack 按 `signature.verification_method` canonical 升序组装为唯一
`ControlProposalAck`。receiver 必须：

1. 逐项重算 member statement digest并验真实签名，按 verification method 去重，只把 genesis
   或 Event basis 解析出的当前 authority member计入 quorum；
2. 要求所有 member 的 Realm、proposal digest与authority-set ref逐字一致，且
   `max(received_at)-min(received_at) <= proposal_intake_sla_ms`；
3. 令set级 `received_at=max(member.received_at)`、
   `decision_due_at=min(member.decision_due_at)`、
   `absolute_due_at=min(member.absolute_due_at)`，并要求
   `received_at <= decision_due_at <= absolute_due_at`；set级字段与该计算不一致即拒绝；
4. 按 `single_signer` / `threshold` / `mixed` 当前 profile 计算互异 member quorum；open-set 按
   `(Realm, signer slot)`独立authority Ack，不得把互不相干leaves拼成threshold；
5. 把canonical Ack set、accepted Event、pending index与wakeup原子提交。closed anchor Event
   不能因无 `seal_basis` 跳过该 pending index；覆盖它的 accepted Seal 必须在同一原子事务写入
   Seal lineage / cell effects 并把每个 `delta[]` digest 从 pending 标记为 sealed，任一 digest
   不存在时整笔 Seal 提交回滚。duplicate Event
   返回byte-identical Ack set；Ack集合、成员时间、顺序或签名不同均不得覆盖首次事实。

`EventInitialSubmission.control_proposal_ack` 与
`EventFederationSubmission.control_proposal_ack` 是该证据的唯一输入位置，只允许 Control
Move；DataEvent携带时必须 schema/admission拒绝。`cba_proof_bundles[]`只补basis closure，不得
承载或替代Ack。收集未在共同窗口内达到quorum时，本proposal永久不能以零散authority Ack入库；
producer必须author并签署新的Control Move Event，authority不得为旧digest重新计时。
`proposal_ack_digest = SHA-256(JCS(the complete canonical ControlProposalAck including
authority signatures))`；同一有效authority集合只有一种排序和一种digest。
该外部成员签发、共同窗口、quorum、duplicate/equivocation与decision-set binding由
`ak.vector.cba.external_control_proposal_ack_quorum.v1`固定。

每个决议窗口到期前，authority MUST 产生以下之一：

1. proposal digest 被 accepted Seal 的 covered set 覆盖；
2. `signed_reject`，携带 closed `reason_code`；
3. `signed_defer`，携带 closed `reason_code`、严格递增且不晚于 `absolute_due_at` 的新
   `decision_due_at`，并把 `defer_count` 恰好加一。

`signed_reject.reason_code` 的封闭集合为 `capability_denied`、`cas_conflict`、
`policy_denied`、`schema_violation`、`superseded`；
`signed_defer.reason_code` 的封闭集合为 `dependency_missing`、`quorum_unreachable`、
`temporarily_unavailable`。实现不得接受
未登记字符串，也不得把 defer 原因用于 terminal reject。

每个 defer MUST 引用完整 canonical Ack-set digest，绑定同一 proposal、Realm 与 authority
set，并由当前 Ack quorum 对同一 decision payload 产生按 verification method canonical
排序的 `proofs[]`。`decision_digest=SHA-256(JCS(decision_without_proofs))`，每个proof的
`payload_digest`必须等于该值、`created_at`必须等于`decided_at`，签名transcript固定为
`JCS({context:"ak.control_proposal_decision_proof.v1",payload_digest,
verification_method,created_at})`；proof不得跨 Ack set、decision kind 或 defer count拼接。它还必须
原样保留 `absolute_due_at`。`signed_reject` 与 `signed_defer` 是可验证的 authority
决议，**不是** proposal 被接受，也不提供 finality；只有第 1 项中的 accepted Seal 提供
控制面 finality。该义务不得命名为“接受 SLA”，也不得声称 deadline 本身提供 finality。
receiver 本地收到 Event、Ack、decision 或 Seal 的时间 MUST NOT 进入规范计算。

签名 decision 的标准提交面是 `ak.self.control_proposal_decisions.command.submit.v1`，标准观察面是 `ak.self.control_proposal_decisions.read.get.v1`；机读 request/outcome 位于 [`control-proposal-decision.schema.json`](../../artifacts/schemas/control-proposal-decision.schema.json)。submit receiver MUST 先从 durable store 读取 accepted proposal 与首次 canonical Ack，重算 `proposal_ack_digest`，再验证 exact Realm/proposal/authority set/deadline/defer chain/quorum 并原子写 decision；caller 不能随请求创建或替换 Ack。read 只投影 canonical Ack、verified decision chain 与 covering Seal，不能生成 decision 或清 pending。对 `ak.device.revoke`，`signed_reject` 通过 proposal Event 与 reducer-derived `ak.schema.device_revocation_state.v1` record 传递性绑定 exact device/generation；只清该 proposal，其他同目标 pending record仍保持 gate。decision/Seal 对同一 proposal 使用 terminal CAS：先 accepted 的合法 terminal 结果获胜，另一结果 fail closed；byte-identical replay 返回首次结果。

**逾期是治理健康 fault，不改变密码学接受结果（normative）**：在当前
`decision_due_at` 前没有上述三者，或到达 `absolute_due_at` / defer 上限后仍未 include /
signed-reject 时：

1. Realm governance health 投影进入 `degraded`，记录 proposal digest、Ack、当前
   decision chain 与 deadline；
2. 产生稳定诊断 `control_proposal_decision_overdue`，并允许形成 censorship evidence；
3. 依赖该 pending Move 的 authoring/readiness，以及无法证明旧授权在 pending revoke /
   ban / notary change 下仍安全的写入 MUST fail closed；
4. 与该 Move 无关、仍由 accepted 旧 Seal 合法授权的 DataEvent MUST NOT 被全局误伤；
5. 后来抵达且按 Seal 规则有效的 Seal仍正常 accepted；fault 作为可审计证据保留。

不得因“迟到”把同一 cryptographically valid Seal 在不同 receiver 上分成 accepted /
rejected 两种终态。协议不能强迫停机或恶意 authority 接受 proposal；它能保证的是合规
authority 给出有界、可验证的决议，并为失约提供 health/fault/recovery/rotation 入口。
上述 Ack、两次 defer 上界、绝对期限与迟到 Seal 规则由 conformance vector
`ak.vector.cba.proposal_bounded_decision.v1` 固定。

`ak.self.seals.read.frontier.v1` 与 `ak.peer.seals.read.frontier.v1` 的 Realm current Seal discovery MUST 返回同一 closed
`RealmSealFrontierView`：`seal_basis.leaves[]` 是 canonical bytewise sorted、duplicate-free 的完整 non-quarantined accepted
Seal leaf antichain；`single_signer`/`threshold` authority 下恰一项，`open_set` 下不得只返回任意一项。该 View 还携
`observation_coordinate={service_id,sequence,observed_at}`；“current”只表示该 service 在该 coordinate 的 verified durable
view，不是 global wall-clock latest。Peer 响应的 Event `heads[]` 不是 Seal leaves，不能替代 `seal_basis`。consumer 必须
resolve 并验证每个 leaf Seal 及路径，再自行重算 joined control state/roots；服务返回的 head/root hint（若其它 surface
存在）不得冒充某一 Seal 的签名 root 或授权真相。

`RealmSealFrontierView.governance_health` MUST 从已验证的
Ack / decision chain 与 accepted Seal covered set 派生；pending 明细最多返回 128 项，
按内嵌 Ack 的 `(control_proposal_ack.absolute_due_at, control_proposal_ack.proposal_digest)`
canonical 升序。每个 pending 项只携 `control_proposal_ack`、`decisions[]`（仅 `signed_defer`，
按 `defer_count` 升序）与 `decision_state`，不镜像 `proposal_digest`、`absolute_due_at`、
`defer_count` 或当前 `decision_due_at`：`proposal_digest` 与 `absolute_due_at` 取自
`control_proposal_ack`（全链原样保留）；`defer_count = decisions.length`；当前决议期限即 DTO
语义中的 `current_decision_due_at`，对应 ack / decision 的字段名 `decision_due_at`，取
`decisions[]` 末项的 `decision_due_at`，无 defer 时取 `control_proposal_ack.decision_due_at`。
超过读取上限时 readiness MUST fail closed，不能静默截断后报告 `healthy`。该 View 不是新的
可写真相源。迟到但合法的 Seal 覆盖 proposal 后，proposal 从 `pending_proposals[]` 移除，但失约证据
MUST 进入 `retained_faults[]`，携带原 Ack、完整 signed-defer chain、accepted Seal id
与其签名 `sealed_at`；按 `(accepted_at, control_proposal_ack.proposal_digest)` canonical 升序，
最多 128 项，超限同样 fail closed。只要 pending overdue 或 retained fault 非空，`status` MUST 为
`degraded`，不得因 proposal 后来取得 finality 而把已发生的 deadline fault 抹除。

**compaction 不承担终局（normative）**：首个 Seal **MUST NOT** 是 compaction Seal；
compaction 前的普通 signing pass 出现任何硬错误时 compaction **MUST** 停止并上浮；
compaction 成功 **MUST NOT** 作为普通 pending Move 已按期取得 proposal 决议的替代证据。

无声遗漏构成 censorship evidence：

```text
CensorshipEvidence {
  control_proposal_ack
  seal_ref
  control_event_set_root_non_membership_proof
  missing_rejection_or_defer_proof
}
```

Censorship evidence 是普通 Control Move，event kind 为 **`ak.notary.fault.censorship`**（payload schema：`notary_fault_censorship_payload`），写入 `ak.component.notary_fault.v1` cell。它**不**自动罢免 notary：reducer 记录审计 fault 并 MUST 触发治理告警。

**问责闭环与 recovery 路径的绑定（normative）**：被告 notary 可能审查针对自己的 fault / censorship evidence。为此：

1. fault evidence Move 持有的 Control Proposal Ack（或经 federation probe 传播的副本）对 **recovery notary**（genesis `recovery_members` / `mixed` profile 的 fallback notary）构成与 inclusion list 等同的收录义务：recovery notary 签发任何 recovery / fork-resolution Seal 时，MUST include、signed-reject 或证明验证失败所有其已知的、处于义务窗口内的 fault evidence Move；
2. `single_signer` 下，evidence 经 federation probe / Event Batch Receipt 渠道流转至 recovery notary；若 Realm 未声明可用 recovery 路径，问责退化为"证据可流转但不可生效"的审计态——这是 `single_signer` 的诚实限制，也是 genesis 强制 `recovery_members` 组织分离的理由之一；
3. multi-signer profile 下，任何非 fault 方 signer 都可把 evidence 列入 inclusion list（§7.3），不必等待 recovery 路径。

### 7.3 Inclusion list

Multi-signer profile MAY 支持 FOCIL 式 inclusion list。非 proposer signer 对通过初检的控制面 Move 签发 inclusion list；下一 Seal MUST include、signed-reject 或证明验证失败，否则 receiver MUST 拒绝该 Seal。`single_signer` profile 无法提供该机制。

Wire schema：[`inclusion-list.schema.json`](../../artifacts/schemas/inclusion-list.schema.json)（`ak.schema.inclusion_list.v1`）：`{realm_id, signer_id, list_seq, event_digests[], expiry_seal_count, created_at, signature}`。Receiver 校验规则（normative）：

1. `signer_id` 在签发时点是 Realm multi-signer notary profile 的合法非 proposer 成员；
2. `event_digests[]` canonical 升序、去重、每项持有效 receipt 且通过本地 verify；
3. `list_seq` 复用 §7.1 的 per-signer slot 语义——同一 `(realm_id, signer_id, list_seq)` 双签构成 equivocation evidence；
4. 自 list 被观察起的 `expiry_seal_count` 个后续 Seal 内（默认 1），每个列出 digest MUST 被 include、signed-reject 或附 batch pre-state 验证失败证明；任一 digest 三者皆无 → receiver MUST 拒绝该 Seal（`rejected_seal`，reason=`inclusion_list_violation`）；
5. inclusion list 自身不是 Seal，不推进治理状态；它只是问责对象。

该义务由 conformance vector `ak.vector.cba_lattice.inclusion_list_obligation.v1` 固定。

### 7.4 Seal transparency

Seal tuple SHOULD 发布到 append-only transparency log。独立 auditor 验证 append-only、Seal DAG 每条 predecessor edge 上 `control_event_set_root` extension 与 `completeness_root` interval 非缩、以及签名有效性，并签发 attestation。`log_index` 相邻但 DAG 互不可达的并发 entry 不参与单调性比较。具体 operation / profile 若把该 attestation 绑定为响应证据，客户端 MUST 验证 policy 要求的 witness / auditor attestation；v1 core 不据此引入跨 query 通用的等级字段。

Wire schema：[`seal-transparency.schema.json`](../../artifacts/schemas/seal-transparency.schema.json)（`ak.schema.seal_transparency.v1`）定义两个对象：

- **log entry**：`{log_id, log_index, realm_id, seal_id, control_event_set_root, completeness_root, state_root, prev_entry_digest, logged_at, log_signature}`——`log_index` append-only，`prev_entry_digest` 形成 hash 链。同一 `(log_id, log_index)` 出现两个签名不同的 entry 即构成**可证明的 log fork**：split-view 攻击者要么一致发布、要么留下可出示的分叉证据。
- **auditor attestation**（`#/$defs/auditor_attestation`）：`{log_id, realm_id, from_index, to_index, head_entry_digest, auditor_id, checks{append_only, seal_signatures, set_root_monotonic, completeness_monotonic}, attested_at, signature}`——四项 checks 全部为 true 才可签发；auditor 无法断言任一项时 MUST NOT 出具。

采信 Seal transparency attestation 的判定标准是“该 Seal 被至少 `Realm.audit_policy.seal_transparency_min_attestations` 份、且满足 `seal_transparency_auditor_independence` 的独立 auditor attestation 的已验证范围覆盖”；每个 auditor 必须位于 `seal_transparency_auditor_ids[]`。`audit_policy` 缺失时客户端 MUST NOT 把该 attestation 作为 v1 已验证证据；具体 operation / profile 还必须显式登记承载字段及验证规则。

## 8. AvailabilityReceipt

Digest membership 不能证明 bytes 可获取。Arkret v1 独立建模 availability：

```text
AvailabilityReceipt {
  realm_id, event_id, bytes_digest, holder_service_id, retention_expires_at,
  holder_signer_evidence_ref, signature
}
```

需要内容寻址时，selector digest 由 `H(JCS(AvailabilityReceipt))` 计算并覆盖完整签名内容；receipt wire 本身不回显该 digest。

其中 `bytes_digest = H(UTF8("ak.availability_event_bytes.v1") || 0x00 || JCS(complete accepted EventEnvelope with only unsigned removed))`，`H` 使用该 Realm 的 digest suite。`event_id`、`actor_kind` 与所有 accepted producer / station proofs 都在 preimage 内；因此它覆盖实际保留的准入证明字节，但仍须与按普通 Event preimage 重算的 `event_digest` / `event_id` 及逐项 proof 验证交叉核对。

规则：

- `Realm.availability_policy` 是本义务的唯一机器承载，结构见 `realm.schema.json`。缺失时按 `{min_holders:1, applies_to:["seal_include"], minimum_retention_ms:86400000}` 解释；不得按“Realm 大小”或产品类别自行选择隐式门槛。v1 不携 `holder_roles`，eligible holder 只按 predecessor accepted closure 的下列两个互斥分支派生：
  - ordinary Collaboration / Direct Conversation Realm：从全部 effective joined membership 的完整 `member_id: ActorId` 派生目标 Station，并按 service DID 去重。account 分支使用 `account_id.station_id`；service 分支使用 `service_id`。leave/ban、`via_ids`、Event actor、notary、当前 resolver 与本批 post-state 均不产生 holder。暂时无法解析 endpoint 只影响投递重试，不改变 membership 或 holder identity。
  - `purpose="principal_control" | "agent_control" | "applet_managed_control"` 的 create-locked control Realm：human / Agent PCR genesis 按 `realm-and-space.md` §2.8.1、Applet managed principal genesis 按 `applet-integration.md` 明确不产生 member state，因此唯一 holder 是从 predecessor closure 中唯一 accepted `ak.realm.create` 的 actual-author `ActorId` 导出的 origin service。receiver 必须先完整验证该 create 的 Station admission proof、proof 所引用的 historical `AuthenticatedSignerResolutionEvidence`、`signer_id == route(actual_author_actor_id)` 以及 Event/Realm/proof binding，才可把该 frozen service DID 加入 holder set。genesis unit 内出现多个不同 route-derived origin service、缺 admission proof或 signer binding 不一致时整个 closure 无合法 holder；不得从 current account row、session、resolver、notary 或部署配置回填。
- notary 在 Seal include 一个 Control Move 前 MUST 收集满足 effective policy 的签名 AvailabilityReceipt；device-signed PCR notary 使用 `ak.self.seals.command.issue_availability_receipts.v1`，以 exact predecessor antichain 与待 include Event digest 集取得 holder 选择的 `sealed_at`、receipt commitments 和完整 typed dependencies，再用同一 `sealed_at` 与 canonical digest 列表签 Seal。`apply_seal` receiver MUST 按 §6.3 step 5 独立验证 full canonical digest、receipt 的 event/digest、holder DID、签发时冻结的 `AuthenticatedSignerResolutionEvidence`、accepted holder eligibility、互异 holder 数与 `retention_expires_at >= Seal.sealed_at + minimum_retention_ms`。不得用 current resolver 代替历史签名 key；不满足时拒绝 Seal，而不是降级为诊断。
- policy 的 `applies_to` 含 `snapshot` 或 `backfill` 时，相关签发服务在作出 bytes-available 承诺前 MUST 收集同样门槛的 receipts，并把 receipt digest / proof 随响应或承诺 root 暴露给 verifier；verifier 缺少可验证门槛时 MUST NOT 声称 availability 已满足。
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

控制面 cell 在 join 无法收敛到单一合法值时进入 `⊥`（bottom）。`⊥` 的暴露语义由 cell family 的 **`bottom` policy** 决定，取值为封闭枚举 `bottom ∈ {expose, reject, inert}`：

| `bottom` | 语义 |
| --- | --- |
| `expose` | join 产生 `⊥` 时把冲突 heads 暴露给读路径与后续 Move（不直接 fail-closed 写入）；典型用于 `or_set` 形态的并存/审计语义（如 §7.1 `(or_set, bottom=expose)` notary fault cell、moderation_state cell）。 |
| `reject` | join 产生 `⊥` 时，所有依赖该 cell 的 Control Move precondition、DataEvent 授权判定与读路径 MUST fail closed，返回 `failed_bottom`（`reason=cell_in_bottom_state`，见 §13）；典型用于 `cas_register` / `fsm` 等强单值治理 cell。 |
| `inert` | 该 lattice 的数学 join 不产生 `⊥`，因此本字段不引入额外 reject / expose 语义；普通 `or_set` / `ordered_log` / `counter` 使用此值。若领域定义了独立冲突条件，必须另行登记为 `expose` 或 `reject`，不得借 `inert` 绕过。 |

声明来源与默认值：

- `bottom` policy 是 **cell family 属性**，由 Realm schema 的 cell family 声明（与 `lattice` 同处声明，权威载体为 [`registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 对应 cell 的 `bottom` 字段）。
- 每个 core lattice type 的默认 `bottom`：`cas_register` / `fsm` 默认 `reject`（强单值治理 cell，冲突即 fail-closed）；`or_set` / `ordered_log` / `counter` 的 join 在数学上永不产生 `⊥`，未显式定义领域冲突语义时 registry MUST 登记 `bottom=inert`（例如 capability grant 与 consent grant 这类普通 observed-remove 集合），reducer MUST NOT 据其产生 reject 语义；见 [`capabilities.md` §12.1](./capabilities.md) 与 [`../identity/consent-model.md`](../identity/consent-model.md)。若某个 or_set cell family 显式登记 `bottom=expose` 并由领域文档定义 exposed multi-head 处理（例如 `ak.component.moderation_state.v1`），实现 MUST 执行该领域规则，不得用普通 or_set 的 inert 默认覆盖它。`mv_register` 不产生 `⊥`（暴露多 heads 而非 bottom）。registry 对 `mv_register` cell 登记的 `bottom=expose` **只表示读路径暴露多 heads**，MUST NOT 被解读为该 lattice 能进入 `⊥`：实现 MUST NOT 为 `mv_register` cell 生成 `failed_bottom` 状态、对应的 bottom-state reason code 或任何其它 `⊥` 分支，`head_eq` 的「`⊥` 时 fail closed」在该 lattice 上不可达。多 heads 的收敛由领域合同与后续因果写入负责（§9.2、§9.4）。
- cell family 未显式声明 `bottom` 时，reducer MUST 按上述 per-lattice-type 默认处理；MUST NOT 把未声明当作 `expose` 放宽强单值治理 cell。

> `bottom=reject` cell 进入 `⊥` 后的恢复路径由 §9.5 control cell `⊥` recovery 定义（conflict-recovery Move）。

**`⊥` 是状态的函数，不是本地粘滞标志（normative）**：一个 cell 是否为 `⊥`，MUST 由该 view 下 §9.3.1.2 的读取规则重新求值，MUST NOT 由「本 receiver 曾经观察到 `⊥`」这一事实锁死。反例：两个并发分支各写 `A`、`B`，随后各自在**尚未观察到对方**时合法续写同一个 `T`；完整 view 的两个活跃 head 都是 `T`，读作 `T`。若只先收到 `A` / `B` 的 receiver 把 `⊥` 记成永久标志，它与先收到完整历史的 receiver 会给出不同终态，违反 §6.3.1「`J(L)` 是 `L` 的纯函数、与到达顺序无关」。因此：先前在无冲突分支中合法产生的后继照常参与合并；**普通写入能否以包含异值 heads 的签名 basis 写该 cell，按 §9.3.1.4 的 recovery-restricted family 分层判定**——清单内的 family 只能由 §9.5 的有权 recovery 发起，清单外的 family 允许一次有权普通写自愈。因此实现 MUST NOT 把「见过 Bottom 即永久死」当作本节语义。

### 9.2 Data plane 冲突

数据面相同 cell 上的有效并发写按该 cell Lattice join：

- 可交换 op 正常 merge；
- 普通属性使用 `mv_register` 暴露多 heads；
- 文本 / 序列类 cell 使用注册 CRDT profile；
- 数据面默认不产生协议级 `⊥`，也不需要 recovery capability。

### 9.3 Counter / escrow 边界

数据面 counter 只允许本地可判定的 issuer-local 消耗：每个 issuer 只能消耗自己切片内的额度，并且消耗 Event 必须沿该 issuer actor chain 串行累计验证。

同一 issuer 在同一 `(actor_id, actor_seq, prev_frontier_digest)` sibling 桶内产生多个 counter/escrow 消耗 Event 时，receiver MUST 把该桶视为 issuer-local escrow equivocation。命中同一 issuer 切片的全部派生消耗对该切片 fail closed，直到 fork-resolution 产生 canonical 单分支。

跨 issuer `transfer` 同时改变两个 issuer 的切片，属于跨 cell / 跨 issuer invariant；默认 MUST 升控制面，或使用 per-object sequencer 线性化。否则两个并发 transfer 可能单笔合法、合并后超支。

### 9.3.1 core lattice join 与 `head_eq` predicate（normative）

本节是 Control Move `preconditions[]` 中 `Predicate` 与 core lattice join 规则的散文权威；schema 只给字段形状，不能替代本节的求值语义。

- **`head_eq`**：完整 `preconditions[]` 条目的 wire 形态为 `{cell_id:"ak:cell:...", predicate:{op:"head_eq", value:<json>}}`。Reducer MUST 在该 Move 的 `seal_basis` 治理 view 下读取目标 cell 的 settled value，并按 canonical JSON whole-value compare 与 `predicate.value` 比较；二者 bit-exact 相等时通过。cell 缺失时 settled value 为 `null`，因此省略业务字段与显式缺省不得被当作匹配。若目标 cell 在该 basis 下为 `⊥`，`head_eq` MUST fail closed（failure status `failed_bottom`，`reason=cell_in_bottom_state`，见 §13）。
- **`cas_register`**：`cas_register` 是**因果寄存器**：它的内部状态是一组仍然活跃的写入身份，业务读取才收敛为单值。定义、准入与合并规则见下面四节；`head_eq` 比较的始终是本节 §9.3.1.2 派生出的业务 settled value，不是内部 heads 数组。
- **`fsm`**：`fsm` 与 `cas_register` 同为**因果寄存器**，只是每个活跃 head 携带的值是该写入的目标状态 `to`，且写入要额外通过转移表准入。transition write MUST 声明 `from` 与 `to`；`from` 是对写入自身签名 basis 的准入断言，不进入状态、也不是 join 的接边依据。定义、读取、准入与合并规则见下面 §9.3.1.5–§9.3.1.8；实现 MUST NOT 把 op 序列按到达顺序解释成一条转移路径。
- **`ordered_log`**：每个 reducer-projected `op.kind="append"` write MUST 携带 `issuer_seq`，且其值 MUST 逐字等于 envelope `actor_seq`；其它 op kind 禁止该字段。`issuer_seq` 是为 self-contained projected op 保留的 issuer 因果坐标，不是 cell-local counter。对同一 `(write.cell, actor_id)`，它允许因 actor 在其它 cell 写入而产生任意非负间隔；不得要求从 0 开始连续，也不得把间隔后的 entry 留在 pending。

  joined value 是全部已验证 append Event 的 grow-only 集合。entry identity 由 Event identity 决定；reducer 以 `(actor_id, issuer_seq, event_digest)` 承载并按该三元组 canonical 升序序列化，其中 digest 比较遵守 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的 decoded-octets 规则。该排序只固定 bytes，**不选择 winner**。相同 `(actor_id, issuer_seq)` 的多个合法 sibling 全部进入 cell value；同一 Event 的 exact replay 幂等去重。不同 canonical Event preimage 得到同一 Event identity/digest 属于 hash collision，必须在 Event acceptance 层整组 quarantine，不能由 lattice 选边；仅 `proofs` / reducer stamps 不同且 producer digest preimage 相同仍是同一 Event 内容。

  `ordered_log` 不产生 `⊥`，也不定义“issuer equivocation loser”。同高 sibling MAY 作为审计诊断暴露，但诊断必须列出完整 sibling set，不得包含 `winner` / `loser`，不得把任一 sibling 从 timeline、joined value、`state_root` 或 `data_view_root` 排除。一个 actor 后续 Event 是否覆盖完整 frontier由 actor-chain / completeness 规则判断，不得因某 cell 出现同高 sibling而截断该 actor 在本 cell 的未来 entries。

  任何需要唯一 current value、授权、finality 或不可逆副作用的 family MUST 使用独立注册的 CAS/FSM/领域 projection。该 projection 必须对完整 ordered-log head set 求值并采用单调或 fail-closed 规则；不得从日志顺序、digest 或任一 sibling 中机械选 winner。`ordered_log` 自身只保存事实，不授予权力。

`ak.realm.create` 的 append 同样携带从 envelope `actor_seq` 投影的 `issuer_seq=0`；它不是本 lattice 的特殊计数规则。
- **`or_set` / `counter` / `mv_register`**：`or_set` 按 observed-remove dot 集合 join；`counter` 只在 §9.3 允许的 issuer-local 切片内求和；`mv_register` 暴露并发 heads 而不产生 `⊥`。领域文档可进一步收窄这些 lattice 的合法 projected writes，但不得改变交换、结合、幂等的 core join 要求。


#### 9.3.1.1 `cas_register` 的状态：Event 身份与活跃 heads（normative）

固定一个 Realm 与一个已验证治理 view `V`。令 `C(V)` 为 `V` 的 Control Move 覆盖集（§6.2 递归 `covered_set` 的并集，按 Event 身份去重；多个 Seal 覆盖同一 Event 只计一次）。构造 `C(V)` 与下述状态之前 MUST 先完成 signed basis 验证、注册投影、授权、依赖闭包与 §6.3.3 碰撞归一验证。

对一个 `cas_register` cell `c`，其状态 `H_c(V)` 是一个从 **EventId 到 canonical JSON value** 的有限映射，记录**仍活跃、尚未被因果后继取代**的写入：

- **写入身份就是已有的 EventId**；cell 与 Realm 是外层上下文，MUST NOT 为此新增 op 序号、parent 字段或业务世代。
- 一个 Event 对同一个具体 cell MUST 最多产生一个最终 CAS 写。条件投影 MUST 先求值再检验此约束：互斥条件的两行不是两次写（`ak.watch.set` 即此形态）；`patch` 的若干子操作在签名基线执行后 MUST 只派生一个最终写值。同一个 Event 对**不同** cell 各写一次是允许的。
- 同身份、同 canonical effect 是 **exact replay**，幂等；同身份、不同 effect 是验证错误或 §6.3.3 碰撞路径，MUST NOT 交给 lattice 选一个。碰撞隔离完成前不满足本节的身份唯一假设。
- `H_c(V)` 是**验证后派生**的 reducer 状态并进入状态承诺（§6.2.1），**不是 producer 自报 effects**。receiver MUST NOT 信任调用方自报的 head 集合。
- `C` 按 Realm/view 共享，**MUST NOT 每个 cell 复制一份历史覆盖集**。持久化时 `C` 的更新与该 Event 全部 cell heads 的更新 MUST 原子提交；MUST NOT 先暴露「已覆盖 Event」，稍后才补其投影。

历史 Seal 保留它当初实际应用的 canonical bytes 与 effect；receiver MUST NOT 用一份归一裁决选出的 winner 字典重算这些旧根（§6.3.3 第 2 点）。本代数只合并**同一已验证贡献规则**下的 view：`ak.device.reanchor` fence 或 §6.3.2 fork-resolution 若改变哪些历史分支可进入当前 view，MUST 先按其注册规则重建相应状态，MUST NOT 把 fence 前后的缓存无条件套入集合并。

#### 9.3.1.2 读取、`null` 与 `⊥`（normative）

业务读取仍是单值 CAS，由 `H_c(V)` 唯一派生：

- `H_c(V)` 为空：该 cell **未写入**，settled value 为 `null`。
- `H_c(V)` 的全部 canonical value 相等：settled value 即该值，**包括 `null`**。
- `H_c(V)` 含两个及以上不同 canonical value：`⊥`（`failed_bottom`，§9.1.1）。`bottom=reject` 时业务读取与所有依赖它的 Move precondition fail closed。

由此：

- **不存在 per-family 的 registered initial value**。`cas_register` 未写入初始态在全协议恒为 `null`。registry MUST NOT 声明 `initial_value` 或 `sentinel_writers`，reducer 也 MUST NOT 派生 `initial_value_reserved` 拒绝分支；每个 cell family 的真实初始化数据由它注册的 create / genesis 写入承载。本条不取消对象领域默认值，也不改 `fsm` 的注册初始状态。
- **同值并发 heads MUST 保留全部 EventId**，MUST NOT 压成一个无身份的 value：否则只观察过分支 `x` 的后继会误删它从未见过的 `y`。
- **释放是一次新的写入 `value=null`，其 head 必须保留**。MUST NOT 删除 cell 后宣称它从未被写过：空 heads 与「释放为 null」在状态承诺里必须可区分（§6.2.1）。
- `failed_bottom` 与合法 JSON `null` 在 SDK 类型与 wire 解析中 MUST 区分。

#### 9.3.1.3 写入、Seal 准入与同批（normative）

普通 `cas_register` 写入 `w` 按以下唯一规则执行：

1. **基线来自 `w` 自身签名的 `seal_basis`**：从它重建已验证 view `B`。所有实际 CAS 写入自动派生**完整 heads 比较守卫**（目标 cell 在 `B` 下的 `H_c(B)`）；业务条款另行要求的 `head_eq` 在同一个 `B` 上求值（例如 `ak.invite.create` 对其 slot 的显式 `head_eq: null`，[`../models/governance-objects.md` §5.3](../models/governance-objects.md)）。**MUST NOT 要求所有 CAS 写入都在 wire 重复携带旧业务值或目标 cell 的 `head_eq`**：签名 basis 已固定完整前态。
2. 注册 patch / effect MUST 只在 `B` 上派生一次，MUST NOT 随「哪一个 Seal 先覆盖它」重新解释；生成式 effects 与 producer 自报 effects MUST NOT 混用。
3. 对拟覆盖 `w` 的 Seal 的冻结 predecessor view `P`（§6.3 step 8 / §6.3.1 step 3 的同一冻结基线），继续执行既有授权与生命周期重验，并 MUST 要求每个被写 CAS cell 的**完整 heads 相等**：`H_c(B) = H_c(P)`（身份集合相等，值已由身份唯一确定）。不相等即 stale，MUST 以 `failed_precondition` 拒绝，**即使两边的业务 settled value 相同**。本条 MUST NOT 被放宽成「整个 Realm basis leaves 相等」：无关 cell 的变化不使本次 CAS 失效。
4. `w` 成为新 head，并取代该 cell 在 `B` 中的**全部** heads。因第 3 项，这也正是 `P` 的全部 heads。
5. 一个 Seal 的同批写全部针对冻结的 `P`，MUST NOT 靠 `delta[]` 数组顺序满足另一条写入的前置条件。同批命中 `bottom=reject` cell 的**异值**互斥写按 §6.3.1 step 3「同 Seal 排重义务」拒绝整个 Seal；**同值**写允许保留多个身份。合法并发 Seal 的结果按 §9.3.1.4 合并；同一个 Event 被多个并发 Seal 覆盖仍只是一次写入。

第 3 项封闭 stale ABA：一个基线停在某次空位上的写入，即使目标 cell 在被占用又释放之后重新读到同一个业务值，也 MUST NOT 因此通过——业务值相等不足以通过，head 身份集合必须相等。

**自派生目标的守卫形态（normative）**：`ak.audit.applet_binding.create` 的 binding cell 与 `ak.call.create` 的 call state cell，其 `cell_subject` 直接派生自本 Event 的 `event_id`（前者 `cas_register`，后者 `fsm`；两者同为因果寄存器，守卫形态一致）。若强制这类 Event 把该具体 `cell_id` 写进被 digest 覆盖的 `preconditions[]`，就会形成「Event digest → 自己的 cell_id → 被 digest 覆盖的 preconditions → Event digest」的哈希自引用，而 `preconditions[].cell_id` 只允许具体字符串、没有待求值的 self target。因此规范 MUST NOT 泛化「所有 CAS 写都在 wire 显式 `head_eq`」；守卫一律采用第 1 项的**自动派生身份守卫**——在 EventId 算出后派生目标 cell 并读取 `B` / `P` 即可，不引入新 placeholder、预计算 ID 或首写免检通道。已登记的业务 `head_eq` 条件 MUST 继续签名并执行，MUST NOT 被静默删除。

**两类无 `seal_basis` anchor unit 例外（normative，封闭）**：Realm genesis 的空治理基线，以及 `ak.device.reanchor` 由签名 `pre_fence_seal_frontier` / 原子 replacement unit 固定的基线。它们 MUST 经各自既有的闭合验证派生确定上下文；该例外 MUST NOT 被扩成「新 cell 或首写一律免检」的通用例外。

#### 9.3.1.4 两个已验证状态的合并（normative）

对两个已验证状态 `(C1,H1)`、`(C2,H2)`（同一 cell、同一 Realm、同一贡献规则），合并按**身份**求值；相同身份的值已由身份唯一性保证一致：

```text
C = C1 ∪ C2
H = (H1 ∩ H2)
    ∪ { h ∈ H1 | id(h) ∉ C2 }
    ∪ { h ∈ H2 | id(h) ∉ C1 }
```

即：另一边**从没见过**的 head 必须保留；另一边**见过却已不把它当 head**，说明它已被取代。实现 MUST NOT 只对 heads 取并集，也 MUST NOT 仅凭单个 Event 的 inclusion proof 就断言它仍是完整当前 heads。

该合并满足结合律、交换律与幂等性：令 `R = C \ ids(H)` 为「已知但不活跃」的身份（含不写本 cell 的 Event），则 `(C,H)` 与 `(C,R)` 一一对应，上式等价于 `C = C1 ∪ C2`、`R = R1 ∪ R2`、`ids(H) = C \ R`，三者都是集合并；按 `(C,R)` 的分量包含关系它就是最小上界。新写入只增大 `C` 与 `R`，MUST NOT 复活旧身份。**可合并的是完整状态 `(C,H)`**，不是丢掉 `C`/`H` 之后的业务值或 Bottom 标签。

对因果闭合 view，写入 `e` 活跃当且仅当 view 内没有任何写入 `f` 的签名写入基线包含 `e`；对两个这样的 view 取并，`e` 不活跃当且仅当至少一个 view 已使它不活跃——这恰是 `R` 的并。因此**增量合并等价于对完整因果历史求极大活跃写入集合**，不需要枚举任何路径。

**MUST NOT 按业务值绑定取代关系（normative）**：实现 MUST NOT 按 `(value, from)` 去重、MUST NOT 把 `Y.from == X.value` 当作取代边、MUST NOT 枚举极大链取终值，也 MUST NOT 要求 projector 把 `head_eq` 的 `value` 复制进 `op.from`。按值绑定的 join 与该投影规则 MUST NOT 作为可选语义并存：按值接边无法区分 `A→B→A` 与 `A→B→A→B`（两者产生相同的去重 `(value,from)` 集合，却应分别读 `A` 和 `B`），并在合法值复用下产生阶乘条极大链。`fsm` 合法使用的 `from` / `to` 不受本条约束。

**Bottom 不是本地粘滞标志（normative）**：见 §9.5。先前在无冲突分支中合法产生的后继，仍按其实际因果上下文参与合并。

**含异值 heads 的 basis 写入按 family 分层（normative，仅 `cas_register`）**：`⊥` 之后能否由一次普通写恢复，取决于**写该 cell 所需的授权与 precondition 闭包是否读它自己**。闭包自指的 family 在 `⊥` 之后不存在任何可被授权的主体，重试多少张 Seal 都无效，只能由独立恢复权威修复；闭包不自指的 family 没有这个障碍，禁止普通写只会把一个可自愈的 cell 变成死格。

**`fsm` 不参与本分层**：每条普通 transition 都声明 `from`，而 §9.3.1.7 第 2 项要求 `from` 逐字等于 `H_c(B)` 派生的 settled value；`⊥` 下该 settled value 不存在，因此**任何** `fsm` family 的普通写都 fail closed，唯一出路恒为 §9.5 的 conflict-recovery Move。这是构造性结论，所以 `fsm` family MUST NOT 出现在下面的登记清单里——列进去会让人误以为该清单是 `fsm` 的真相来源，而它只登记 `cas_register` 侧的判定结果。

对 `cas_register`：

- **sole-recovery family（已登记清单，`cas_register` 侧）**：`ak.component.fork_resolution.v1`、`ak.component.identity.resolution.v1`、`ak.component.invite.live_target.v1`、`ak.component.mls.epoch.v1`、`ak.component.realm.authority_root.v1`、`ak.component.realm.organization_recovery_key.v1`、`ak.component.realm.reducer_profile.v1`。对这些 family，普通写入 MUST NOT 以包含异值 heads 的签名 basis 写该 cell；唯一出路是 §9.5 的 `ak.conflict.recovery`。该清单的机器可读真相是 [`registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中 `ak.conflict.recovery` 写入的 `sole_recovery_families`。清单只描述「哪些 family 没有普通写出路」，**不**限制 recovery 能针对哪些 cell：`ak.conflict.recovery` 对任何处于 `⊥` 的因果寄存器 cell 仍然可用（§9.5.1）。清单成员可以增加，因为增加只会收紧自愈、不会去掉任何 cell 的出路；成员减少等同新增 normative 规则，必须逐条论证该 family 的写入闭包确实不自指。
  - `ak.component.realm.authority_root.v1`：[`capabilities.md` §5](./capabilities.md) 把 root authority 定义为该 cell 的 current controller，且 operational authorization MUST 使用该 cell 在同一 Seal basis 下的 inclusion proof、MUST NOT 回退到 `realm_state.owner` / membership / `created_by`；§6 又把它定为 v1 授权图的唯一 genesis base case。
  - `ak.component.invite.live_target.v1`：四个写入方都携带该 slot 的业务 `head_eq`，而 §9.3.1 规定 `head_eq` 在 `⊥` 下 MUST fail closed。
  - `ak.component.fork_resolution.v1`：§6.3.2 禁止在已 settled 的 subject 上再写一条 resolution，因此它也没有普通写出路。
  - `ak.component.mls.epoch.v1`：`ak.mls.commit` 的 base-epoch 业务 precondition 读该 cell，`⊥` 下 fail closed，普通 Commit 因此永远推不动 epoch。
  - `ak.component.identity.resolution.v1`：`ak.identity.resolution.update` 的准入要求恰一个针对该 cell 的 `head_eq` guard，`⊥` 下按 §9.3.1 fail closed；另一个写入方 `ak.realm.create` 只在 genesis 命中。
  - `ak.component.realm.organization_recovery_key.v1`：`register` 要求该 cell 为 unset，`rotate` 的 `head_eq` 明写「mismatch、missing 或 Bottom 一律 `failed_precondition` 且零写入」，两个写入方在 `⊥` 下都不可用。
  - `ak.component.realm.reducer_profile.v1`：`ak.realm.upgrade` 必须携带该 cell settled source profile 的 `head_eq`；§7.1 已就此写明「并发互斥 upgrade 进入 `⊥`，恢复只使用 §9.5 的 `ak.conflict.recovery`」，本条只是把它并入统一判据。
- **其余因果寄存器 family**：`⊥` 之后，一次**对该 action 本来就有权**的普通写 MAY 以包含异值 heads 的签名 basis 写该 cell，并按第 4 项取代该 cell 的全部 heads，使其收敛回单值。该写入 MUST 通过它自身全部既有的授权、生命周期与业务 precondition；本条只解除「目标恰好处于 `⊥`」这一项额外阻断，MUST NOT 被用来放宽任何其它检查。特别地，若该写入自身的某个 `head_eq` 或业务 precondition 读的正是这个 cell，它按 §9.3.1 在 `⊥` 下仍然 fail closed——本条不会给它开口子，只是没有为它额外加一道禁令。它在 lattice 层与 §9.5.1 的 recovery 写同形，因此实现 MUST NOT 为它另造 op、另设 reset 通道，或按到达顺序截断历史（§9.5.1 第 5 项同样适用）。

自愈写与 recovery 写都只取代**自己见过的** heads：basis 未覆盖的分支仍按本节合并式参与合并，两条并发且异值的自愈写仍然冲突。

**取证只走已登记的精确披露面（normative）**：合并式需要的三类输入——对端 view 的完整 CAS state leaf、某个身份是否属于对端 `C`、以及碰撞归一依赖——MUST 通过已登记的读取面与证明取得：完整 state leaf 与 membership 走 §6.2.1 的 `state_root` inclusion / non-membership proof 与 §6.2 的 `control_event_set_root`；碰撞变体走 §6.3.3 的 `collision_variant_record` selector；`event_sibling_position` 的穷尽性走 [`../sync/federation.md` §4.5.1](../sync/federation.md) 的 `ak.peer.events.read.sibling_positions.v1`。实现 MUST NOT 为 CAS 新增私有下载接口、operator 命令或数据库直读来补齐这些输入；缺证据时 MUST hold / fail closed，MUST NOT 把「查不到」当成「对方没见过」——后者会让已被取代的写入复活。

conformance 入口：`ak.vector.lattice.cas_register_supersession.v1`（join 与合并闭合）与 `ak.vector.cba_lattice.cas_mixed_basis.v1`（写入准入、stale ABA 与自派生目标）。

#### 9.3.1.5 `fsm` 的状态：Event 身份与活跃 transition heads（normative）

`fsm` 与 `cas_register` 是**同一套因果状态**，只是每个 head 携带的值是它写入的目标状态 `to`，并且
写入要额外通过一层转移表准入。§9.3.1.1 的取值范围、身份唯一性、验证前置与 `C` 共享规则**逐条**
对 `fsm` 生效，本节只写它与 `cas_register` 的差别。

固定一个 Realm 与一个已验证治理 view `V`，`C(V)` 同 §9.3.1.1。对一个 `fsm` cell `c`，其状态
`H_c(V)` 是一个从 **EventId 到该写入的 `to` 值**的有限映射，记录**仍活跃、尚未被因果后继取代**的
transition 写入。

- **`from` 不进入状态**。`from` 是写入时对自己签名 basis 的**准入断言**（§9.3.1.7 第 2 项），
  不是 head 的成员，也不是 join 时的接边依据。实现 MUST NOT 按 `(from,to)` 去重、
  MUST NOT 把 `Y.from == X.to` 当作取代边、MUST NOT 按输入顺序把 op 序列解释成一条路径。
  §9.3.1.4 对 `cas_register` 写的那条「按值接边无法区分 `A→B→A` 与 `A→B→A→B`」
  **对 `fsm` 同样成立**，且此处更易触发：四个可逆 lifecycle family 与 membership 都会复用值。
- **注册初始状态保留**。这是 `fsm` 与 `cas_register` 的唯一状态差别：`H_c(V)` 为空时该 cell
  未写入，settled value 是它在 reducer contract 里登记的初始状态，而不是 `null`。
  §9.3.1.2 那条「不存在 per-family 的 registered initial value」只约束 `cas_register`。
- **同一写入的重投与同一 basis 的两个写入是两回事**。同身份、同 canonical effect 是 exact
  replay，按身份幂等去重成一个 head；两个**不同身份**的写入即使 basis 相同、`(from,to)` 相同，
  也各自是一个 head——它们是两个真实的并发写入，压成一个会让只见过其中之一的后继误删另一个。

#### 9.3.1.6 读取、初始态与 `⊥`（normative）

业务读取由 `H_c(V)` 唯一派生：

- `H_c(V)` 为空：cell 未写入，settled value 为该 family 登记的初始状态。
- `H_c(V)` 的全部 `to` 相等：settled value 即该状态，**并发的多个同值写入身份 MUST 全部保留**。
- `H_c(V)` 含两个及以上不同 `to`：`⊥`（`failed_bottom`，§9.1.1）。`bottom=reject` 时业务读取与
  依赖它的 Move precondition fail closed。

**写过的 `fsm` cell 进入 `state_root`（normative）**：与 §6.2.1 的 `cas_register` 例外同源同理。
一旦 `H_c(V)` 非空，该 cell 的 leaf MUST 出现在 `state_root` 中，**即使它处于 `⊥`**；未写入的
cell 不占 leaf。理由与 `cas_register` 逐字相同：把 `⊥` 排除在 root 之外会让「从未写入」与「冲突」
在 non-membership proof 下不可区分，而这两者在本节里是不同的状态——前者读初始态，后者 fail
closed。§6.2.1 原先「非 `cas_register` 的 `⊥` cell 一律不进入 `state_root`」对 `fsm` 不再适用；
其余 `bottom=reject` lattice 不变。

**`terminal_states` 与已登记 self-loop（normative）**：终态是转移表的性质，不是 join 的性质。
一个已登记的 `s→s` self-loop 在终态 `s` 上**合法**，它写入一个新身份、`to` 仍是 `s`，读取不变；
从终态 `s` 出发指向 `s` 以外任何状态的转移**非法**，在准入期拒绝。实现 MUST NOT 把「终态上的
任何 transition 都非法」当作等价简化，也 MUST NOT 在 join 期靠 self-loop 的存在改变后继转移的
合法性——一次合法 self-loop 之后，从 `s` 出发的其它已登记转移仍然合法。

#### 9.3.1.7 写入、Seal 准入与同批（normative）

普通 `fsm` 写入 `w`（声明 `from`、`to`）按以下唯一规则执行。第 1、3、4、5 项与 §9.3.1.3 逐条相同，
第 2 项是 `fsm` 独有的转移表准入：

1. **基线来自 `w` 自身签名的 `seal_basis`**，从它重建已验证 view `B`；目标 cell 的完整 heads
   `H_c(B)` 是自动派生的身份守卫，不要求在 wire 上重复携带。
2. **转移表准入在 `B` 上求值**：`from` MUST 逐字等于 `H_c(B)` 派生出的 settled value
   （空 heads 时为登记初始状态）；`from` 与 `to` MUST 都属于登记的 `states`；`(from,to)` MUST
   属于登记的 `allowed_transitions`；`from` 为终态时只允许已登记的 `from→from` self-loop。
   任一项不成立 MUST 以 `failed_precondition` 拒绝该 Event。`H_c(B)` 为 `⊥` 时 settled value
   不存在，普通写入 MUST fail closed（唯一出路是 §9.5 的 conflict-recovery Move）。
   **准入结论 MUST NOT 从未经验证的 `to` 反推**：缺少验证写入路径、basis 或授权所需的依赖或证明时
   MUST pending 或 fail closed，MUST NOT 先采信 `to` 再补验证。
3. 对拟覆盖 `w` 的 Seal 的冻结 predecessor view `P`，MUST 要求 `H_c(B) = H_c(P)`（身份集合相等）。
   不相等即 stale，MUST 以 `failed_precondition` 拒绝，**即使两边的 settled 状态相同**——这正是
   `A→B→A` 之后重新读到 `A` 的那条 stale ABA。
4. `w` 成为新 head，并取代该 cell 在 `B` 中的**全部** heads。因第 3 项，这也正是 `P` 的全部 heads。
5. 同批写全部针对冻结的 `P`。同批命中同一 cell 的**异 `to`** 写按 §6.3.1 step 3「同 Seal 排重
   义务」拒绝整个 Seal；**同 `to`** 写允许保留多个身份。

**同批拒绝与 `⊥` 不是同一件事（normative）**：同批异 `to` 写是**准入期**的确定性拒绝，只发生在第 5 项那一种情形——同一个 Seal 的同一批里出现异 `to` 写，此时 Seal 尚未接受，以 `rejected_seal` 拒绝整个 Seal，对所有 receiver 给出相同结论。`⊥` 则是**合并期**的状态：分别落在合法并发 Seal 里的异 `to` 写都已被接受，cell 读作 `failed_bottom`（Bottom 诊断 reason 为 `same_from_different_to`）。两者 MUST NOT 互相代入，各 family 现有的冲突枚举文案 MUST 逐族核对后才收敛。实现 MUST NOT 用「先到者赢」拒绝无法因果排序的合法并发写入——那会让结果取决于投递顺序，违反 §6.3.1 的 `J(L)` 纯函数要求。

#### 9.3.1.8 两个已验证状态的合并（normative）

合并式与 §9.3.1.4 **逐字相同**，只是 `H` 的值域是 `to`：

```text
C = C1 ∪ C2
H = (H1 ∩ H2)
    ∪ { h ∈ H1 | id(h) ∉ C2 }
    ∪ { h ∈ H2 | id(h) ∉ C1 }
```

§9.3.1.4 给出的结合律、交换律、幂等性与最小上界证明只用到「身份集合的并」这一个性质，与 head 携带
的是业务值还是 `to` 无关，因此**对 `fsm` 原样成立**；迟到分支的论证同理——`e` 不活跃当且仅当至少
一个 view 已使它不活跃。实现 MUST NOT 为 `fsm` 另立一套按到达顺序的折叠语义。

由此，§9.5.1 item 5 禁止的那条「按最后一个 `recovery_reset` 截断 op 序列」对 `fsm` 与
`cas_register` 一样**不再需要**：recovery 是一次有权的新身份写入，只取代自身 basis 覆盖的完整
heads（§9.5.1）。未被该 recovery 覆盖的迟到分支继续参与合并；两个并发的异 `to` recovery 仍然
冲突，MUST NOT 由到达顺序裁定。

**共享 membership 折叠 MUST 与本节同义（normative）**：MLS membership、governance proof 与
Station notary 各自持有的 membership transition 折叠是本 lattice 的消费者，不是它的第二种语义。
它们 MUST 按本节求值；保留一份按 `(from,to)` 去重或按 `recovery_reset` 切片的并行实现，等于让
同一个 cell 在两个消费面上读出不同状态。

actor-private 的 `fsm_cas` 保留它自己在 `actor_private_contracts` 下的 revision 与私有作用域合同；
它 MAY 共享本节的合法边校验，MUST NOT 被强制采用共享面的 Seal heads 算法。

conformance 入口：`ak.vector.lattice.fsm_causal_heads.v1`（顺序置换、分批合并、ABA、self-loop、
同值多身份、缺依赖、迟到分支与并发 recovery，并覆盖 MLS membership 消费面）。

### 9.3.2 digest suite transition Seal（normative）

Realm 的 `digest_algorithm` 只能通过控制面 suite-transition Control Move 改变。transition Move MUST 经 Seal 接受，并在该 Transition Seal 上同时承诺旧 suite 与新 suite：

1. transition Move 的 payload MUST 声明 `from_digest_algorithm`、`to_digest_algorithm`、`transition_realm_state_snapshot_ref` 与 `realm_state_snapshot_commitment`；`from_digest_algorithm` MUST 等于所有 predecessor joined view 唯一、非 `Bottom` 的当前 Realm live suite，`to_digest_algorithm` MUST 是 digest-suite registry 的 active row，且不得违反 registry 的 no-downgrade strength order。Transition Seal MUST 是 compaction Seal，`delta` MUST every-and-only 包含一份 `ak.realm.digest_suite_transition` Move；同一 Seal 混入普通 Move、包含多份 transition Move、不是 compaction，或 predecessor views 不能 join 为同一 live suite 时均 MUST `rejected_seal`。
2. Transition Move Event 及其 AvailabilityReceipt 在 transition 前的 live suite 下完成 authoring 与 admission：Event `event_id` / `event_digest`、receipt `bytes_digest` / `payload_digest` / full receipt digest，以及 transition payload 的 `realm_state_snapshot_commitment` MUST 使用 `from_digest_algorithm`。这些已签对象进入 Transition Seal 时不得换 suite、改写或重新签名。
3. Transition Seal 是新 suite frontier 的第一个 Seal。它的 `id`、notary signature `payload_digest`、`control_event_set_root`、`completeness_root` 与普通 `state_root` MUST 使用 `to_digest_algorithm`；`previous_state_root` MUST 使用 `from_digest_algorithm`。`control_event_set_root` / `completeness_root` 以新 suite 对 covered Event digest wire values 重建 Merkle tree，即使其中包含 transition 前已签的旧 suite Event digest。`predecessor_refs`、`delta`、`covered_event_digests` 与 `availability_receipt_digests` 是对既有 typed content identifiers / digests 的引用，保留各自原 suite，不得按 Transition Seal suite 重哈希。
4. Verifier MUST 用旧 suite 重算 transition **前**治理 view 的 `previous_state_root`，用新 suite 重算应用 transition Move **后**治理 view 的 `state_root`，并验证以旧 suite 生成的 `realm_state_snapshot_commitment` 对同一 control/data frontier 的 inclusion。`previous_digest_algorithm` MUST 等于 transition Move 的 `from_digest_algorithm`。任一 Event、receipt、Seal id、notary payload、root、snapshot commitment、suite identity 或 suite strength 判定不匹配时，Transition Seal MUST `rejected_seal`。

上述状态机的认证入口是 `ak.vector.hash_transition.dual_root_recompute.v1` 与 `ak.vector.hash_transition.fail_closed.v1`（`hash-transition-fixture.json`）。声明 `ak.profile.hash_transition.v1` 的实现 MUST 执行双 suite 正例以及缺 root、错 suite、snapshot mismatch、降级、非 Transition Seal 携带 `previous_state_root`、迁移后旧 suite 再现的全部负例。
5. Transition Seal 接受后，该 Realm 内所有后续 Event digest、Seal id、state_root、Merkle leaf 与 receipt digest MUST 使用 `to_digest_algorithm`；旧 suite 只可出现在历史对象、Transition Seal 的 `previous_state_root`，以及 Transition Seal 对旧 Event / receipt / predecessor 的原样 typed 引用中。不得从任意待验证 digest 的 prefix 反向选择 live suite；verifier MUST 从已验证 predecessor joined `ak.component.realm.digest_suite.v1` 状态取得 `from_digest_algorithm`，并仅在验证 transition Move 与双 root 后原子推进到 `to_digest_algorithm`。

Realm genesis 另有一次非 transition 的固定桥接：`ak.realm.create` Event / Realm token 及该 Event 的 AvailabilityReceipt 按 [`../conformance/encoding.md` §4.3](../conformance/encoding.md) 固定使用 SHA-256 code `0x01`；同一首 Seal 内除 create 外的其余 founding Events 及其 receipts MUST 使用已验证 create payload 的 `digest_algorithm`。首 Seal 同样以该声明 suite 生成 Seal id、notary payload、累计 roots 与 post-state root。因此声明 BLAKE3 的 genesis 是一个有界 mixed set：仅 create Event / receipt 是 SHA-256，其他 founding Events / receipts 与 Seal 自身均为 BLAKE3；累计 root 把这些已签 typed digest wire values 原样当作 leaf data。不得据 create Event digest prefix 把 Realm live suite 降为 SHA-256。除该固定 genesis bridge 和上述 suite-transition bridge 外，不存在 Realm 内 mixed-suite authoring。

### 9.4 非治理强一致对象

看板位置、强单值状态机或其它非治理强一致对象在规范撰写与 family 注册时三选一；一旦进入 v1 registry，该选择即被冻结，不是 Realm policy 或 `cell_lattices` 的动态开关：

1. **默认 `mv_register` + user-pick**：并发结果暴露多 heads，任何有写权限者可再签一个 DataEvent 收敛。
2. **`sealed=true` 升控制面**：继承 Seal finality、`⊥` 和 recovery。
3. **per-object sequencer**：schema 指定某 DID 线性化该 cell 的 DataEvent；sequencer 失效时 MUST 退回 `mv_register` 或升控制面。

### 9.5 control cell `⊥` recovery（normative）

`bottom=reject` 的控制面 cell（典型 `cas_register` / `fsm`）join 到 `⊥`（§9.1.1）后，所有依赖它的 Control Move precondition、DataEvent 授权判定与读路径 fail closed（`failed_bottom`）。把该 cell 从 `⊥` 拉回单一合法值有两条途径，**本节定义的 conflict-recovery Move 对任何处于 `⊥` 的因果寄存器 cell 都可用**；此外，§9.3.1.4 的 sole-recovery 清单**之外**的 `cas_register` family 还可以由一次对该 action 本来就有权的普通写自愈，那条路径不需要 recovery capability，也 MUST NOT 为它另造 reset 通道。清单内的 family 与**全部** `fsm` family 没有普通写出路（后者见 §9.3.1.7 第 2 项），recovery 是其唯一途径。`bottom=expose` cell 的 `⊥` 暴露多 heads、由后续普通 Move 收敛，**不**适用本节、也不需要 recovery capability。

**`ak.component.notary.v1` 的 `⊥` 构造性不可恢复（normative）**：它不在 recovery-restricted 清单内，且 MUST NOT 被加入——一次 conflict-recovery Move 本身需要一张被接受的 Seal，而验证 Seal 必须先读该 cell 的已接受 notary 配置；该 cell 处于 `⊥` 时读路径 fail closed，因此任何恢复 Seal 都无法被接受。实现与后续规范修订 MUST NOT 为该 cell 发明救援路径；保证它不进入 `⊥` 的是 §6.3 的单控制谱系与本节其余准入，不是事后恢复。

conflict-recovery Move 是一条 kind 为 `ak.conflict.recovery` 的 Control Move，
payload 为 `{target_cell_id, resolved_value, reason?}`。它在 registry 中登记为
[`../models/event-and-patch.md` §2.4.2](../models/event-and-patch.md) 的 `cell_ref` +
`reset` 形态：目标 cell 由签名 payload 的完整 `cell_id` 给出，
写入值为 `resolved_value`。

该恢复写入必须由已注册的 `ak.conflict.recovery` contract 唯一派生；
不得用 `refs[]` role、producer 自报 effects 或未注册 kind 替代。识别不只依赖
kind 名：下列条件全部为 MUST，reducer 仅在 cell 处于 `⊥` 时接受它。

**lattice 分型（normative）**：下面第 1 至 5 项的 `state_witness` 家族要求**只适用于非因果寄存器的 `bottom=reject` cell**（registry 中今天是 `ordered_log`）。**因果寄存器（`cas_register` 与 `fsm`，§9.3.1.1–§9.3.1.8）的 recovery 准入一律按 §9.5.1 求值**：它们的目标冲突由**当前签名 basis 下的完整 heads** 证明，不依赖「冲突前合法值」的 inclusion witness。第 6 项（必须 sealed）与「recovery capability 来源」一段对两类同样适用。

**op 形态由目标 cell 的 lattice 决定（normative）**：`ak.conflict.recovery` 的注册 contract 不声明目标 lattice，因此 `reset` 派生成哪一种 lattice op 由目标 cell 自己的 lattice 决定——`cas_register` 是 `set`，`fsm` 是只带 `to` 的 `transition`（§9.5.1）。目标 cell 的 lattice 无法表达「收敛到单一合法值」这件事时，该 reset **不可投影**，receiver MUST 以 schema violation 拒绝整条 Move，MUST NOT 退化成任何一种该 lattice 恰好接受的 op。这是 fail-closed 方向：recovery 的授权很强，它写不进去总好过写成别的东西。

它 MUST 满足：

1. **携带 recovery 授权与见证 ref**：`refs[]` MUST 含 `role=recovery_capability`（critical，授权本次 recovery 的 grant）与至少一个 `role=state_witness`（critical，见证 `⊥` 之前该 cell 合法单值的 frontier + inclusion proof）。缺 `state_witness` MUST `recovery_witness_missing`。这两个 role 已登记于 [`event-and-patch.md` §2.2](../models/event-and-patch.md) 的 `SemanticRef.role`。
2. **witness 可重建 state_root**：`state_witness` 的 inclusion proof MUST 能重建该 witness frontier 的 `state_root`；不能则 `recovery_witness_invalid`。
3. **witness 严格 pre-conflict**：`state_witness` frontier MUST NOT 有到触发 `⊥` 的任一 sibling Move 的因果路径（即必须早于冲突）；否则 `recovery_witness_post_conflict`。这保证 recovery 锚定的是冲突前的合法状态，而非把冲突之一单方面"洗白"。
4. **recovery_capability 已 sealed 且在 witness 下成立**：`recovery_capability` grant 引用的 cell MUST 出现在 `state_witness` 的 `state_root` 中且取值不冲突；否则 `recovery_capability_not_sealed`。
5. **witness 不陈旧、未被撤销**：`state_witness` 到 recovery Move `seal_basis.leaves[]` 的签名 Seal 时间差 MUST ≤ Realm `recovery_witness_freshness_window_ms`（默认 86,400,000 ms，最大 604,800,000 ms）；差值使用 `max(leaves[].sealed_at) - witness_seal.sealed_at`，负值或 DAG 不可达同样拒绝。local frontier 还 MUST NOT 已观察到针对该 `recovery_capability` 的 revoke / supersede 晚于 witness frontier；违反则 `recovery_witness_revoke_lagging`（receiver MUST 拒绝 stale witness replay）。
6. **必须 sealed**：conflict-recovery Move 是控制面 Move，MUST 经控制面 Seal 接受（继承 Seal finality），使"从 `⊥` 恢复到的单值"跨 receiver canonical 一致——与 §7.1 fork-resolution 的跨 receiver 确定性同纪律。reducer 在 cell 处于 `⊥` 时，**仅**接受满足上述全部条件的 conflict-recovery Move 写入该 cell（这是 `bottom=reject` cell 在 `⊥` 下对 `failed_bottom` 的唯一例外），把 cell 解析为该 Move 声明的单一合法值。

**recovery capability 来源**：`recovery_capability` 由 Realm 的恢复权威持有——即 §7.2 闭环里的 **recovery notary**（genesis `recovery_members` / `mixed` profile 的 fallback notary）所辖的 recovery / fork-resolution 授权；它与 §7.1 的 fork-resolution、[`event-and-patch.md` §2.6](../models/event-and-patch.md) over-fork repair 复用同一恢复权威，不引入新授权主体。`single_signer` 且未声明可用 recovery 路径的 Realm，control cell `⊥` 是诚实的死状态（与 §7.2 第 2 点"证据可流转但不可生效"同一限制，也是 genesis 强制 `recovery_members` 组织分离的理由之一）。

#### 9.5.1 因果寄存器（`cas_register` / `fsm`）的 recovery（normative）

对因果寄存器，`ak.conflict.recovery` 仍是已注册的有权 Control Move，但它的 `reset` **派生为一次新的身份写入**（写入身份仍是该 recovery Event 的 EventId），而不是一个抹掉历史的开关：

1. **目标冲突由签名 basis 证明**：recovery Move 的签名 `seal_basis` MUST 证明目标 cell 在该 basis 下确有**异值 heads**（`cas_register` 见 §9.3.1.2 第三种情形，`fsm` 见 §9.3.1.6 的同 `from` 异 `to`）。recovery 取代的对象就是这些**完整 heads**。
2. **授权仍独立验证**：授权 MUST 由已登记的 recovery authority / capability 路径验证（本节「recovery capability 来源」一段）。MUST NOT 因为目标处于 `⊥` 就放过 capability 撤销、作用域或 authority generation 验证。若恢复权威本身不可验证，MUST 走既有 Realm recovery / fence 路径或保持 fail closed，MUST NOT 自签解锁。
2b. **目标不限于 sole-recovery 清单**：`payload.target_cell_id` 可以指向任何处于 `⊥` 的因果寄存器 cell；`ak.conflict.recovery` 写入登记的 `sole_recovery_families` 只说明哪些 family **没有**普通写出路（§9.3.1.4），MUST NOT 被实现成对清单外目标的拒绝条件——那会把尚未逐条审计的 family 变成永久死格。限制 recovery 不被当作通用覆盖通道的是本节既有的两条：目标 MUST 已处于 `⊥`，且授权 MUST 由已登记 recovery authority 验证。
3. **Seal 准入仍比较完整 heads**：覆盖该 recovery 的 Seal 仍按 §9.3.1.3 第 3 项要求 `H_c(B) = H_c(P)`。任一新分支已进入 `P` 时，MUST 重新生成并授权一条新的 recovery。
4. **recovery 只取代自己见过的 heads**：迟到的、recovery basis 未覆盖的分支仍按 §9.3.1.4 参与合并；两条并发且异值的 recovery 仍然冲突。
5. **禁止按到达顺序截断历史**：实现 MUST NOT 用「日志里最后一次 reset 之后的 op」这类接收顺序切片实现本节（例如对 op 序列取 `rposition(reset)` 再截断），也 MUST NOT 把恢复解释成「遗忘此前所有分支」。历史 view 仍按 §9.3.1.4 从已承诺输入重建。

**`state_witness` 在本路径不是准入条件（normative）**：`cas_register` recovery MUST NOT 要求「目标 cell 冲突前合法值的 inclusion witness」，且 `recovery_witness_freshness_window_ms` 对本路径不适用。两条理由：首次写入就冲突时目标此前根本不存在，不存在可见证的冲突前单值；冲突长期未修时，旧 witness 过期不应剥夺**仍然有效**的恢复权威修复该 cell 的能力。目标冲突由第 1 项证明，恢复权威有效性由第 2 项证明，两者分开。MUST NOT 借「删除目标旧值 witness」绕过第 2 项的任何一项验证。

**`fsm` 的写入形态与附加准入（normative）**：`ak.conflict.recovery` 的注册 contract 不声明目标 lattice
（目标由 `payload.target_cell_id` 指认），因此它的 `reset` 派生成哪一种 op 由**目标 cell 自己的 lattice**
决定：`cas_register` 派生为 `set`，`fsm` MUST 派生为一条**只携带 `to = resolved_value` 的 `transition`**。

该 recovery transition **MUST NOT 携带 `from`**。目标处于 `⊥` 意味着 `H_c(B)` 至少有两个不同的 `to`
（§9.3.1.6），这条写入一次取代它们全部，因此它离开的来源是一个**集合**，没有任何单一状态能代表它。
实现 MUST NOT 从中挑一个（末位 head、最小 head、冲突前的旧值都不行）——那是一个 producer 不可见、
两个 receiver 可以做出不同选择的裁决。

准入按该集合逐个求值：对 `H_c(B)` 的**每一个** head `h`，`(h.to, resolved_value)` MUST ∈ 登记的
`allowed_transitions`；任一不成立 MUST 拒绝该 Event。`H_c(B)` 为空时 MUST 拒绝——空 heads 不构成
§9.5.1 第 1 项要求的目标冲突证明。该逐 head 检查覆盖另两条要求，不需要额外查表：`allowed_transitions`
只指名登记的 `states`，故 `resolved_value ∈ states` 由它蕴含；而登记为 `terminal_states` 的状态在
`allowed_transitions` 里 MUST NOT 有除已登记 self-loop 之外的出边（见下），故「从终态出发的 recovery
MUST 被拒绝，已登记 self-loop 除外」同样由它蕴含。

**registry 不变式（normative）**：`terminal_states` 的每个成员在同一 family 的 `allowed_transitions`
中 MUST NOT 作为 `from` 出现，除非该条目是 `s → s` 的已登记 self-loop（§9.3.1.6）。上一段的等价性
依赖这条不变式，因此它 MUST 由 artifacts 门禁强制，MUST NOT 只作为编写约定。

准入之外它与 `cas_register` 的 recovery 逐字相同：同一条身份写入、同一套 heads 取代关系、同一条
§9.3.1.8 合并式，因此第 5 项「禁止按接收顺序截断」对 `fsm` 一样是 MUST，MUST NOT 用 `rposition(reset)`
之类的到达序切片实现它。恢复写入本身也 MUST 保持可被取代：它成为该 cell 的一个普通 head，后继合法
transition 以它为 `from` 继续推进，未被其 basis 覆盖的迟到分支仍按 §9.3.1.8 参与合并。

**与 §7.1 的层次区分**：§7.1 恢复的是 **Seal-DAG 分叉**（equivocation / `fork_quarantine`）；本节恢复的是**未分叉治理状态内单个 cell 的 `⊥`**。两者由同一恢复权威书写、都经 Seal 接受，但作用对象不同，不可互相替代。该恢复路径由 conformance vector `ak.vector.cba_lattice.conflict_recovery_move.v1` 固定。

## 10. 查询语义

v1 不定义跨所有 query / search / projection 响应通用的 `basis` / `grade` 包装。每个可互操作响应的字段以 operation registry 的 `response_schema_ref` 及其 OpenAPI binding 为准；实现不得自行附加未登记的通用证明类型，并把它解释为 core 互操作契约。

需要可验证结果的 operation / profile 必须显式登记其响应中的 Seal extension path、control state proof、observational proof、witness attestation 或 receipt proof 字段，并给出对应 schema 与验证规则。未登记这些字段时，响应只具有该 operation 已声明的读取语义，不得声称额外的 `observed`、`sealed` 或 `witnessed` 等级。

## 11. E2EE 与 MLS

MLS security frontier binding 与普通 `seal_ref` 正交：

- MLS epoch、key schedule 与 active security-frontier projection 属于 control plane。
- E2EE message 属于 data plane，必须携带普通 admission 的 `seal_ref`，并独立证明其消息 epoch / key schedule 绑定当前 security frontier。
- MLS commit 是 Control Move，写 MLS control cells，并由 Seal 裁决。

E2EE message 不等待数据面 Seal；它等待普通 Event admission 成立，并要求 current winning MLS group state 已覆盖最新 key-access frontier。普通 capability 或 metadata 变化不触发 MLS gate。

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
| `seal_deferred_future_skew` | Seal 的 `sealed_at` 暂时超过本地时钟允许的 future skew；非终态，receiver MUST hold 并随时钟推进重判。 |
| `fork_quarantine` | 控制面分叉已被证明，相关 Seal 不得进入普通 joined view。 |
| `seal_ref_stale` | DataEvent 的 `seal_ref` 与其后继撤销 Seal 之间的 notary-committed Seal distance 超出历史 basis grace；不得解释为 Event 首次投递或接收时间超过现实 TTL。 |

本表是 reducer 判定状态；其到服务 error code 的映射以 [`operations-error-mapping.json`](../../artifacts/registry/operations-error-mapping.json) 为准，实现 MUST NOT 引入未登记错误码。

## 14. 规模上限

Move / DataEvent / Seal / Lattice 必须受 [`scalability-constraints.md`](../conformance/scalability-constraints.md) 约束：

- 单个 Event canonical size 默认不超过 1 MiB。
- 单个 Event 的 `preconditions` 不超过 256；单个 reducer contract 的派生 writes 不超过 256。
- 单个 Seal 新增 Control Move 默认不超过 1,000。
- Seal `delta[]` 是本批新增控制面 digest；累计覆盖集由 predecessor 递归定义。实现 MAY 在达到 deployment 上限前生成 compaction Seal，但 compaction MUST 保留 `control_event_set_root`、`state_root`、notary signature chain 与 receipt obligation 证明。
- 单次 Lattice join 超预算时，节点 MUST 返回可恢复错误，或要求缩小已登记 operation 的查询 / projection 范围；MUST NOT 用本地接收顺序替代。

## 15. 规范性引用

- Event Envelope：[../models/event-and-patch.md](../models/event-and-patch.md)。
- Capability 与 freshness：[capabilities.md](./capabilities.md)。
- Query：[../conformance/query-schema.md](../conformance/query-schema.md)。
- Federation 与 transparency：[../sync/federation.md](../sync/federation.md)。
- Snapshot：[../conformance/realm-state-snapshot-schema.md](../conformance/realm-state-snapshot-schema.md)。
- Wire schemas：`artifacts/schemas/event-envelope.schema.json`、`artifacts/schemas/seal.schema.json`、`artifacts/schemas/query.schema.json`、`artifacts/schemas/availability-receipt.schema.json`。
