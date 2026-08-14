---
title: CBA profile、并发类别与终态
status: candidate
normative: true
stability: v1
updated: 2026-07-30
---

# CBA profile、并发类别与终态

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本章是 CBA finality profile、控制操作并发类别、genesis、proposal 决议义务及依赖 bundle
的唯一规范来源。Seal 是唯一控制状态接受事实。

## 1. Finality profile

Realm genesis MUST 签名并 create-lock `notary_profile`：

| profile | Seal 形态 | conformance |
| --- | --- | --- |
| `single_did` | 单 signer、单 predecessor 链 | Kernel 基础 profile，MUST 支持 |
| `threshold` | k-of-n、单 predecessor 链 | 可选独立 profile |
| `mixed` | primary authority 加独立 recovery authority、单 predecessor 链 | 可选独立 profile |
| `open_set` | 多 leaf Seal DAG | 高成本可选 profile |

profile 变更必须由变更前 profile 下 accepted Control Move 完成。receiver 不支持目标 profile 时
MUST fail closed；不得按单个 Event 降级或偷换 profile。只声明单链 profile 的实现不需要运行
open-set vectors。

## 2. 控制并发类别

每个 control reducer contract MUST 固定声明以下一类，producer 不得选择：

| 类别 | 语义 |
| --- | --- |
| `merge_safe` | 可交换集合或 append-only evidence；open-set leaf 可自动 join。 |
| `exclusive` | 单值 policy/lifecycle；并发不可比较写进入 `⊥`，依赖方 fail closed，随后走显式 recovery。 |
| `security_barrier` | authority、membership、device revoke、MLS epoch 等；open-set 必须有相交 quorum。 |

在 `single_did`、`threshold`、`mixed` 的单链中，Seal predecessor 顺序提供 barrier。
`open_set` Realm MUST 有一个 protocol-singleton security-barrier control cell。每个
`security_barrier` Move MUST：

1. 以该 cell 当前 head 为 `barrier_parent_head`；
2. 以既有 `head_eq` precondition 做 CAS；
3. 携带同一 barrier authority set 的 k-of-n attestations，且 `2k > n`；
4. 让每个 attestation 只签 `control_move_digest` 与 `barrier_parent_head`；
5. 由 signer 持久化 `(authority_set_ref, barrier_parent_head, control_move_digest)`，并拒绝为
   同一 parent 签第二个不同 digest。

`authority_set_ref` 在所有 CBA authority/quorum 场景中统一为
`{authority_set_id, authority_set_digest}`：id 是登记的 `ak.authority_set.*.v1` policy
symbol，digest 是该 policy 在当前 CBA basis 中的 canonical digest。任何 signer、lease、
receipt 或 barrier verifier 都 MUST 同时校验 id 与 digest，不得用可变名称解析替代 basis-bound
policy bytes。需要跨服务或离线验证的对象 MUST 携带完整
`ak.schema.authority_set_policy.v1` concrete policy；接收方按
`authority-set-policy-registry.json` 的 template 从 accepted basis 与 CBA closure 重新派生，
并校验 `SHA-256(JCS(policy))`。inline policy 与 registry row 均不得替代 accepted source。

barrier attestation 没有独立 height、state root、历史日志或可被 DataEvent 引用的 id；它随
Control Move 被 Seal 覆盖，不构成第二套 checkpoint。有效双签是可归责 equivocation，相关
分支 MUST fail closed 并进入 recovery。

“子集继续工作”只无条件适用于 `merge_safe`。不得宣传所有 open-set 治理操作都可在 quorum
不可达时继续。

## 3. Seal 唯一性与 genesis

submitted、pending、receipt、transparency entry、availability receipt、snapshot 和 compaction
均不改变控制状态。只有 Control Move 进入一个密码学有效、其 covered set 与 `state_root`
重算一致的 accepted Seal 后才生效。

空 genesis Seal 非法。首 Seal MUST 原子覆盖完整 Realm bootstrap unit。该 unit 内的 `ak.realm.create` MUST 物化**五条 registered write**，
逐条与 [`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)
的注册投影一致（该节是唯一权威来源，本清单不得与其漂移）：

1. signed genesis intent（`ak.component.realm.genesis.v1`）；
2. create 审计日志条目（`ak.component.realm.create.v1`，`issuer_seq=0`）；
3. founding notary（`ak.component.notary.v1`）；
4. reducer profile（`ak.component.realm.reducer_profile.v1`）；
5. founding authority root cell（`ak.component.realm.authority_root.v1`），其
   `controller_id` / `controller_epoch` / `authority_generation` / `capability_action_registry_digest`
   分别由 create envelope 的 `actor_id` 与 create payload 确定性派生。

profile、policy bundle、join rule、history visibility、条件 sharing/discovery/alias/plaintext/delivery 与 creator membership 是同一 bootstrap registry 中按序签名的显式 facet；它们不是 create reducer 的隐式写入。缺槽、错序或条件槽不闭合时整个 unit MUST 原子拒绝。

对 MLS-backed scope，首 Seal 还 MUST 声明将由后续 `ak.mls.genesis` 建立 epoch-0 binding 的
bootstrap requirement；epoch-0 binding 本身由首个覆盖 `ak.mls.genesis` 的 Seal 验证。

创建者的 root authority 只来自第 5 条 authority-root cell。v1 **没有** founding
`ak.capability.grant`：不得要求、也不得接受"紧随 create 的封闭 self grant"作为 genesis 必需项；
缺少该 cell 时整个 bootstrap unit MUST 原子拒绝（`failed_precondition`，
`reason="realm_authority_root_missing"`）。base policy（`ak.realm.policy_bundle`）与其它初始 facet 的必选/条件规则由 §2.5 的 bootstrap registry 唯一决定；实现不得把它们降级成 create 后可补写的普通 follow-up。

缺少任一 founding required cell、使用空 `control_event_set_root`、或先接受空 Seal 再补
authority（含 authority-root cell），均为 `genesis_seal_invalid`。MLS epoch-0 binding 不属于可在 `ak.mls.genesis`
之前物化的 founding cell；其后续 Seal 义务不得被解释为允许补写其它 founding authority。

## 4. Proposal 有界决议

authority 接受 proposal ingress 时签发的 Control Proposal Ack MUST 包含：

```text
proposal_digest, received_at, decision_due_at, absolute_due_at,
defer_count, authority_set_ref, authority_acks[]
```

**闭合 genesis 的 ingress authority**：普通路径中的 `authority_set_ref` 来自已经生效的
Realm authority set。ordinary Realm 与 managed Agent PCR 的登记闭合 genesis Event 虽然免
`seal_basis`，仍是 Control Move，因而在 durable proposal ingress 时 **MUST 各自具有 Control
Proposal Ack**；`AnchorUnit` transport context 只证明无 basis 单元的闭合形态，不得据此让这两类
durable ingress 省略 receipt。receipt、canonical Event、pending Control index 与 wakeup MUST
按本文件的统一提交规则原子落库，不能先接受 Event 再等待首 Seal 时补 pending row。这里的“具有”
约束的是 durable ingress 事务，不等于所有来源都必须在
`EventInitialSubmission.control_proposal_ack` 中预先携带 Control Proposal Ack；wire 责任由下列两个来源决定。

human self-principal PCR 的 `[ak.realm.create, ak.device.authorize]` genesis unit 是唯一闭合 genesis
例外：它不是向外部 authority 提交的 proposal。create 的 identity-root commitment、founding device
对 exact authorize payload/Event 的 possession proof 与整单元原子验证已经闭合内容授权；因此该 unit
**MUST NOT** 携 AuthorizationLease 或 Control Proposal Ack，但两条 canonical Event、pending Control
index 与首 Seal obligation 仍必须原子建立。不得把此例外扩大到 ordinary Realm、managed Agent PCR、
organization PCR 或 re-anchor/recovery。

该 authority set 正由单元创建，不能循环要求尚未生效的 founding notary state 作为 receipt
验证前提，但允许以下两个互斥且可独立验证的 ingress authority 来源：

1. 若 founding signer authority 可从单元外的已接受证据与候选 genesis 完整确定，则该 signer
   MAY 直接签 receipt。managed Agent PCR 的唯一此类路径是：从候选 signed create 重算 founding
   `NotaryValue` / `authority_set_ref`，再以 accepted Agent DID delegation 验证当前 controller
   device；receipt signer 是 controller device，不能伪装成 Agent key。候选 create、Agent DID、
   controller DID、Realm 与 `authorization_ref` 任一不闭合即 fail closed。
2. 否则，完成全量预准入并为同一有序单元签发 `AuthorizationLease` 的 Principal Server MAY
   签发 receipt；receipt 的 `authority_set_ref` MUST 等于这些 lease 的
   `authority_set_digest`，且每个 receipt 仍逐一绑定 exact Event digest，并以自身真实 admission
   verification method 产生唯一 `authority_acks[0]`。此路径的 caller MUST 为完整单元逐项携带
   同序 lease，MUST NOT 预填 `control_proposal_ack`；admitting Principal Server 在重新验证
   完整 lease-bound unit 后、提交事务内签发 receipt。这样 receipt 时间与 durable ingress 是同一
   事实，也避免单 Event receipt 请求无法独立重建完整 genesis unit 的循环。

第二条不是把 Principal Server 冒充为 founding notary，也不得与其它服务 receipt 拼成虚构
notary quorum。两条路径都只确认 ingress，不产生授权、accepted state 或 finality；首个 accepted
Seal 仍 MUST 由单元声明的 founding notary 签署并独立重算 genesis state。已有 accepted Realm
authority、reanchor、recovery 或普通 Control Move 不得使用第二条例外。

两条来源在 wire 上互斥：来源 1 的 caller 携带 authority-signed
`control_proposal_ack`；来源 2 的 caller 携带完整 anchor-unit lease set 且 Ack 字段为空，
由同一 admitting server 在原子 ingress 中产生并返回 receipt。实现不得同时接受两种证据，也不得
把来源 2 的 lease 当作可调用单 Event receipt endpoint 的凭据。

**authority-authored self-principal PCR Move**：human PCR genesis 已由 accepted Seal 建立后，若
Control Move 同时满足 `realm_id=principal_control_realm_id(actor_id)`、current notary profile 为
`single_did(actor_id)`、proof method 精确为该 principal 当前 active accepted device 的 canonical DID URL（该 URL
由 principal 当前 `full_id` 构成且 fragment 等于 `device_id`，不得把 `principal_id` 直接拼接 fragment），并通过 generation/fence、current Seal basis 与完整 Event signature 校验，
则该 device 就是 proposal authority 且已经 author exact Move；这不是需要另一个 authority 签收的
proposal。此类 Move **MUST** 省略独立 Control Proposal Ack，admitting service 仍须原子持久化
canonical Event 与无 Ack 的 pending Control row，并只在同一 current device（或随后合法替代 authority）
签署的 accepted successor Seal 覆盖该 digest 后 materialize effect。duplicate 必须回放首次 admission，
不得补签 Ack 或推进期限。任一 profile、principal、device method、accepted generation 或 Seal basis不匹配
都必须 fail closed，且不得使用本例外。managed Agent controller delegation、organization governance、
ordinary Realm、re-anchor/recovery 与任意 threshold/mixed notary 继续走上文的显式 Ack/quorum 轨道。

Realm 可通过 `proposal_decision_window_ms`、`proposal_absolute_deadline_ms` 与
`max_proposal_defers` 声明更严格的有效值；协议硬上限：

- `decision_due_at - received_at` 不得超过 24 hours；
- 最多 2 次 signed defer；
- 每次 defer 必须带 closed `reason_code` 和新的 `decision_due_at`；
- `absolute_due_at - received_at` 不得超过 72 hours，且 defer 不得改变 `absolute_due_at`。
- Realm 参数 MUST 满足
  `proposal_decision_window_ms <= proposal_absolute_deadline_ms`；若
  `max_proposal_defers > 0`，该关系 MUST 为严格小于。两窗口相等时
  `max_proposal_defers` MUST 为 `0`。Realm create / policy reducer 必须在写入前校验，
  违反时以 `schema_violation` 拒绝整个 Control Move。

每个 defer MUST 引用完整canonical Ack-set digest，绑定同一 proposal / Realm /
authority set，并由该receipt set要求的quorum对同一payload产生canonical `proofs[]`；
`defer_count` 恰好加一，且不得改变 `absolute_due_at`。期限内必须出现 include in
accepted Seal、signed reject 或 signed defer。reject 与 defer 只是
可验证决议，不提供 finality；只有 include 后的 Seal 提供 finality。超过绝对期限仍无决议时，
客户端可生成 censorship evidence 并进入 authority health/recovery/rotation；协议不能强迫
停机或恶意 authority 接受 proposal。

不得把该义务称作“接受 SLA”，也不得声称 deadline 本身提供 finality。

机读合同为
[`control-proposal-decision.schema.json`](../../artifacts/schemas/control-proposal-decision.schema.json)。

## 5. CbaProofBundle

peer durable submit 或 dependency response MAY 携带：

```text
CbaProofBundle {
  target_seal_ref,
  seals[],
  control_moves[],
  inclusion_proofs[],
  availability_proofs[]
}
```

bundle 不签名、不创建新身份，也不是真相源。receiver MUST 独立验证对象 digest、签名、
profile、predecessor/leaf closure、inclusion proof、state root 与 reducer 输出。
`single_did`/`threshold`/`mixed` 按 predecessor digest/range 补齐；`open_set` 按 target leaves
补 ancestry closure。sender MAY 发送完整、可验证的有界超集；receiver 不得要求字节相同的
“最小 bundle”。

每个 bundle 只服务一个 `target_seal_ref`。全部可归属 Realm 的 Seal、Control Move、proof
与 receipt MUST 属于 target 的同一 Realm；跨 Realm 对象是永久 `schema_violation`，不得当成
缺依赖。数组必须按各对象 canonical id/digest 的 UTF-8 bytes 严格递增排列并去重；receiver
MUST 拒绝乱序或重复输入，不得静默排序/删项后继续。超集只允许包含从 target 沿 predecessor /
leaf、Seal delta/covered set、inclusion 或 availability obligation 可达的对象；不可达对象是
过度披露与放大输入，MUST 拒绝。

验证顺序固定为：

```text
结构、Realm、数量与 canonical order
→ 对象 id/digest/signature
→ predecessor/leaf 与 inclusion/availability proof
→ covered Control Move canonical acceptance
→ roots 与 reducer 重算
→ target Seal projection
→ 引用 target 的 Event authorization
```

同批到达但尚未进入合法 accepted Seal 的 Control Move 不能授权后续 Event。验证失败不得产生
Event、Seal、reducer、projection 或 frontier 的部分副作用；实现 MAY 缓存已独立验证的原始对象，
但缓存不是 accepted state。

Kernel 硬上限：

- canonical bundle body ≤ 8 MiB；
- `seals[]` ≤ 256；
- `control_moves[]` ≤ 1,024；
- 两类 proof 合计 ≤ 2,048；
- 从 target leaf 向 genesis 的单路径深度 ≤ 4,096；
- dependency fetch 最多连续 8 轮；每轮必须使 missing set 严格缩小。

超限返回 `limit_exceeded`，不得按部分 bundle 改变控制状态。依赖不足返回
`dependency_missing` 并给出精确、UTF-8 bytewise 排序、去重且有界的
`missing_seal_refs[]` 与 `missing_event_digests[]`；结构性 Event 引用缺失另用
`missing_event_ids[]`。对象完整但授权失败使用已登记的最窄 capability/policy reason（无更窄
reason 时才用 `policy_denied`），不得新增含混的泛化“authorization rejected”reason，也不得与缺依赖混淆。

peer dependency fetch 复用 `QUERY /_arkret/peer/events/resolve` 的只读
`PeerEventsResolveRequestBody` / `PeerEventsResolveOutcome`。resolve 响应不得直接接受 Event 或
Seal；闭包补齐后仍须通过新的 peer submit 请求重新求值。收到任何 submit 响应后，后续求值必须
使用新的 `Idempotency-Key`；只有完全未收到响应的逐字节 transport retry 才复用原 key。

## 6. 最小正反例

正例：single-chain receiver 缺两个 predecessor，收到含三个 Seal 的可验证超集，忽略多余
已知 Seal 后接受 target。

反例：open-set 高风险 membership Move 只有不相交的两个少数签名集合。即使两个分支各自形成
普通 Seal，也必须拒绝，不能用本地到达顺序选 winner。

反例：Control Proposal Ack 到期但未进 Seal。该 proposal 仍未接受；客户端只产生 fault evidence，
不得把 receipt 投影成治理状态。
