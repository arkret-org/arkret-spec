---
title: CBA profile、并发类别与终态
status: candidate
normative: true
stability: v1
updated: 2026-07-28
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

barrier attestation 没有独立 height、state root、历史日志或可被 DataEvent 引用的 id；它随
Control Move 被 Seal 覆盖，不构成第二套 checkpoint。有效双签是可归责 equivocation，相关
分支 MUST fail closed 并进入 recovery。

“子集继续工作”只无条件适用于 `merge_safe`。不得宣传所有 open-set 治理操作都可在 quorum
不可达时继续。

## 3. Seal 唯一性与 genesis

submitted、pending、receipt、transparency entry、availability receipt、snapshot 和 compaction
均不改变控制状态。只有 Control Move 进入一个密码学有效、其 covered set 与 `state_root`
重算一致的 accepted Seal 后才生效。

空 genesis Seal 非法。首 Seal MUST 原子覆盖并物化：

1. Realm metadata；
2. creator joined membership；
3. founding authority/notary；
4. founding grant；
5. base policy；
6. 对 MLS-backed scope 必需的 epoch-0 governance binding。

缺少任一 required cell、使用空 `control_event_set_root`、或先接受空 Seal 再补 authority，
均为 `invalid_genesis_seal`。

## 4. Proposal 有界决议

authority 接受 proposal ingress 时签发的 proposal receipt MUST 包含：

```text
proposal_digest, received_at, decision_due_at, absolute_due_at,
defer_count, authority_set_ref, signature
```

协议硬上限：

- `decision_due_at - received_at` 不得超过 24 hours；
- 最多 2 次 signed defer；
- 每次 defer 必须带 closed `reason_code` 和新的 `decision_due_at`；
- `absolute_due_at - received_at` 不得超过 72 hours，且 defer 不得改变 `absolute_due_at`。

期限内必须出现 include in accepted Seal、signed reject 或 signed defer。reject 与 defer 只是
可验证决议，不提供 finality；只有 include 后的 Seal 提供 finality。超过绝对期限仍无决议时，
客户端可生成 censorship evidence 并进入 authority health/recovery/rotation；协议不能强迫
停机或恶意 authority 接受 proposal。

不得把该义务称作“接受 SLA”，也不得声称 deadline 本身提供 finality。

## 5. CBAProofBundle

peer durable submit 或 dependency response MAY 携带：

```text
CBAProofBundle {
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

Kernel 硬上限：

- canonical bundle body ≤ 8 MiB；
- `seals[]` ≤ 256；
- `control_moves[]` ≤ 1,024；
- 两类 proof 合计 ≤ 2,048；
- 从 target leaf 向 genesis 的单路径深度 ≤ 4,096；
- dependency fetch 最多连续 8 轮；每轮必须使 missing set 严格缩小。

超限返回 `resource_limit_exceeded`，不得按部分 bundle 改变控制状态。依赖不足返回
`dependency_missing` 并给出精确、去重、有界的 `missing_seal_refs[]` 与
`missing_event_digests[]`；对象完整但授权失败返回 `policy_denied`，二者不得混淆。

## 6. 最小正反例

正例：single-chain receiver 缺两个 predecessor，收到含三个 Seal 的可验证超集，忽略多余
已知 Seal 后接受 target。

反例：open-set 高风险 membership Move 只有不相交的两个少数签名集合。即使两个分支各自形成
普通 Seal，也必须拒绝，不能用本地到达顺序选 winner。

反例：proposal receipt 到期但未进 Seal。该 proposal 仍未接受；客户端只产生 fault evidence，
不得把 receipt 投影成治理状态。
