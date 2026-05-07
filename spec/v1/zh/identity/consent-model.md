---
title: Holder-Private Consent Model
---

## 1. 目标

Contrix 的访问授权由 **capability + invite** 两条路径承担。但二者都不能完整表达一类语义：

> "我同意 / 不同意来自 X 的联系请求。"

这是 **持有人私有 (holder-private) 决策**，独立于：

- 任何 Space 的 membership（成员关系）
- 任何 capability grant（能力授权）
- 任何 invite token（邀请凭证）

它是 invite / direct contact 路径上的**前置 gate**：在"是否给 Alice 发出 invite"之前，先看"Alice 是否同意接收来自 Bob 的 invite"。

本规范定义 Contrix 的 consent state，与 capability / invite 正交。模型借鉴自 [`draft-ietf-mimi-protocol`](https://datatracker.ietf.org/doc/draft-ietf-mimi-protocol/) 的 consent 概念，并完整落在 Contrix 的 Move / Anchor / Lattice 三原语之上：consent 是 holder 控制的 Space 内某个 consent cell（or-set lattice）的当前 join 值，由签名 Move 维护。

## 2. 设计原则

### 2.1 Consent 是 holder 私有状态

Consent grant / revoke 表达的是 **holder 自己的决定**。它写入 holder 的 principal control Space（或等价的 actor-private 流），不暴露给任何协作 Space。

- 写入方：holder 自己（或 holder 显式授权的 controller / agent）。
- 可见方：默认仅 holder；MAY 通过 holder 主动 disclose 给 peer 作为"green light"信号。
- 不进入协作 Space：consent 状态不暴露 holder 的隐私偏好给 Space 内的其他成员。

### 2.2 Consent 不授予 Space 权限

Consent 表达"我接受联系"，但加入 Space、写入 Space、解密 E2EE 内容仍需独立的 capability + membership。Consent 是 invite 流程上游的过滤器，不替代下游授权。

### 2.3 Consent 与 capability 正交

| 维度 | Consent | Capability |
| --- | --- | --- |
| 关系 | holder ↔ peer pair | actor ↔ resource action |
| 持有方 | holder（被联系方） | actor（执行动作方） |
| 写入位置 | holder principal control Space | 目标 Space |
| 用途 | invite / contact 前置 gate | 执行动作 (read/write/admin/...) 时的权限判断 |
| 撤销 | `cx.consent.revoke` | `cx.capability.revoke` |

二者可独立存在：peer 持有"对 Alice 的 invite capability"，但 Alice 没 consent → invite 路径仍被 gate；Alice consent 给了 Bob，但 Bob 没 capability → invite 不能执行。

## 3. Consent Cell 与 Move 形态

### 3.1 Consent Cell

Consent state 写入 holder 控制的 Space（默认是 holder 的 principal control Space）内一个 or-set lattice cell：

```text
cell_id  = cx:cell:cx.component.consent.grant.v1:<consent_id>
lattice  = or-set
bottom   = reject  // or-set never produces ⊥; declared value follows registry
```

- `consent_id` 是 consent 槽的 subject。同一 holder 对同一 peer 的不同 scope 用不同 consent_id；同 consent_id 上所有 add / remove tag op 收敛于同一 cell。
- 因 or-set 不会产生 ⊥，`bottom` 字段的 wire 值（registry 中为 `reject`）对 consent 行为不构成约束；effective consent 始终由 or-set join 决定。

### 3.2 `cx.consent.grant` Move

```text
Move(cx.consent.grant) {
  issuer    = holder DID（或 holder DID Document 显式授权的 controller / agent）
  space_id  = holder principal control Space
  preconditions = []          // grant 不依赖 cell 既有状态
  effects   = [
    (cx:cell:cx.component.consent.grant.v1:<consent_id>,
     {type: "add",
      tag:  "grant:<consent_id>:<peer>:<scope>",
      value: {
        consent_id:   <consent_id>,
        peer:         "did:web:bob.example.com",
        scope:        "invite",
        not_before:   "2026-05-07T00:00:00Z",
        valid_until:  "2026-12-31T00:00:00Z",
        evidence_ref: "cx:move:sha256:01js0pres...",
        reason:       "Bob completed verified contact discovery"
      }})
  ]
  refs       = [
    (id="cx:grant:01js0hsc000000000000000000",
     role="authorized_by")
  ]
  anchor_ref = <holder principal control Space 的最新 Anchor>
}
```

字段语义：

- `consent_id`：consent cell subject。同一 holder 对同一 peer 的不同 scope 用不同 consent_id。
- `peer`：counterparty DID 或 pairwise DID。
- `scope`：详见 §4。
- `not_before` / `valid_until`：时间窗口（可选）。窗口外 consent 不生效，相当于 implicit revoke（不需要单独的 revoke Move）。
- `evidence_ref`：可选审计链——指向引发此 consent 的 claim disclosure / presentation response / invite proof Move。
- `reason`：人类可读理由（仅审计，不参与授权）。

Issuer MUST 是 holder 自己（或 holder DID Document 显式授权的 controller / agent）。其他 actor 提交的 grant Move 在 holder 的 principal control Space MUST `unauthorized` reject。

`tag` 内容要求确定性可复现。推荐编码 `grant:<consent_id>:<peer>:<scope>`；同样 (consent_id, peer, scope) 的两个 grant Move 共享同一 tag，or-set 自动幂等去重。

### 3.3 `cx.consent.revoke` Move

```text
Move(cx.consent.revoke) {
  issuer    = holder DID
  space_id  = holder principal control Space
  preconditions = [
    (cx:cell:cx.component.consent.grant.v1:<consent_id>,
     {op: "contains", value: "grant:<consent_id>:<peer>:<scope>"})
  ]
  effects   = [
    (cx:cell:cx.component.consent.grant.v1:<consent_id>,
     {type: "remove",
      tag:  "grant:<consent_id>:<peer>:<scope>",
      value: {
        revoked_at: "2026-06-15T10:00:00Z",
        reason:     "Bob harassment incident #4711"
      }})
  ]
  refs       = [(id="cx:grant:01js0hsc000000000000000000", role="authorized_by")]
  anchor_ref = <holder principal control Space 的最新 Anchor>
}
```

或 grant Move 写一个单 tag、revoke Move 在同一 tag 上 remove。precondition `contains` 仅用于诊断（缺失时 Move fail_precondition，避免无意义 revoke）；or-set 的去重语义保证多 issuer 重复 revoke 收敛。

撤销在该 revoke Move 进入 Anchor frontier 后立即生效——consent cell 的 or-set join 值不再含该 grant tag。frontier 之前 peer 凭借 consent 发出的 invite / contact 不会被追溯失效（已经发出的 invite 由 invite revoke 单独处理）。

## 4. Scope 枚举

| Scope | 语义 |
| --- | --- |
| `invite` | peer 可发送 Space / Flow invite |
| `direct_message` | peer 可发起 1:1 消息（DM Space）|
| `voice_call` | peer 可发起 WebRTC 语音通话 |
| `video_call` | peer 可发起 WebRTC 视频通话 |
| `presence` | peer 可观察 holder presence |
| `any` | 全部 scope（覆盖所有上述类型）|

`scope=any` 是便利值，等价于显式 grant 所有具体 scope。撤销 `any` consent 同时撤销所有具体 scope；撤销具体 scope 不影响其他 scope。

## 5. Cell Join 与 Effective Consent

Consent cell 是 or-set lattice。Effective consent 由当前 Anchor view 下 cell 的 or-set join 派生：

- `effective_grants(cell) = { grant_value | tag in or-set.add_tags - or-set.remove_tags }`
- 一个 grant 当前生效（即 invite / contact 路径上 gate 放行）当且仅当：
  - 存在对应 tag 在 or-set add 集合且未被 remove；
  - 当前时间 ∈ `[not_before, valid_until]`（窗口字段缺省视为 `(-∞, +∞)`）。
- 不同 consent_id 是独立 cell；查询 `(holder, peer, scope)` 时 invite / contact service 遍历该 holder 全部 consent cell 匹配。
- 同 Anchor 批内并发 grant 与 revoke 在 or-set join 后唯一确定（add tag 和 remove tag 各自集合化收敛），不产生 ⊥。审计 / sodmin 视图可暴露并发的 add / remove 序列以提示决策不连续，但 invite gate 仍按"当前 add tag 集合 - remove tag 集合"判定。

物化 `Consent` 对象（详见 [`models/data-structures.md`](../models/data-structures.md)）由 holder client / sodmin 从该 cell 当前 join 值生成；它不是协议授权根，而是 UX / 审计辅助视图。

## 6. 与 Invite / Contact 流程的整合

### 6.1 Invite 前置 gate

Peer 发送 invite Move 时，invite service / facade SHOULD 在 Move 接受 / 投递前查询 holder 的 consent cell：

1. 调用 holder 的 principal control Space（或受托 contact discovery service）查询所有候选 consent cell（subject 由 holder consent 命名约定决定），跑 or-set join 后筛选 `(peer=requester, scope="invite" OR scope="any")` 当前活跃的 grant tag。
2. 若没有匹配的活跃 grant：
   - **`require_explicit_consent` profile**：invite Move MUST `failed_precondition` reject（consent gate 可表达为 invite Move 的 precondition：`contains("grant:*:requester:invite|any")`）。Peer SHOULD 通过 `cx.private_contact_discovery.v1` 等机制请求 holder 显式授权后重试。
   - **default profile**：invite MAY 进入 holder 的 quarantine inbox（"陌生人邀请"），由 holder 在 UI 上 review 后构造 grant Move 或丢弃。
3. 若有匹配活跃 grant 且当前时间在 `[not_before, valid_until]`：invite Move 正常 anchor。

policy MAY 声明 `cx.space.policy_components` 中的 `preauth` component 包含 `require_consent: true`，对该 Space 的所有 invite Move 强制以 consent cell precondition 表达。

### 6.2 Contact / DM 前置 gate

类似地，发起 1:1 message Space、WebRTC call、presence subscription 时，发起方 SHOULD 验证目标的 consent state（scope = `direct_message` / `voice_call` / `video_call` / `presence`）。

`cx.private_contact_discovery.v1` 在返回 reachability proof 时，可附带 holder 当前 consent state hash（不暴露具体 consent 内容，只声明 grant/revoke 状态），让发起方在尝试联系前判断是否需要先请求 consent。

## 7. MIMI Interop

MIMI 协议有 `request_consent` / `update_consent` 操作（`cx.mimi.request_consent` / `cx.mimi.update_consent`），见 [`extensions/mimi-interop.md`](../extensions/mimi-interop.md) §10。Facade 映射规则：

- 接收 MIMI consent update：facade MUST 先验证 actor 是声明 holder 或受授权 controller，然后构造 grant 或 revoke Move 写入 holder principal control Space 的 consent cell。
- 发送 Contrix consent state 到 MIMI：facade MUST 把当前 consent cell or-set join 值翻译为 MIMI consent message，并保留 consent_id 作为 inter-protocol correlation。
- consent state 不暴露具体 evidence_ref / reason 跨 provider；只暴露最小 `(peer, scope, granted/revoked)` 三元组。

## 8. 隐私与审计

- consent state 是 holder 私有；服务端 MUST NOT 把它暴露给非 holder actor 或非授权 service。
- consent grant / revoke 的 backfill 受 holder principal control Space 的 history visibility 与 access policy 约束。
- audit projection MAY 记录 consent state 变化（用于合规审查），但 audit access 必须经 holder 授权或 legal hold 边界。
- pairwise DID / pseudonym 场景下，consent 可绑定 pairwise DID 而非真实 principal DID；reducer 不强制 consent.peer 必须是 principal DID。

## 9. 与未来 Capability Constraint 的关系

未来 v1.x profile MAY 引入 capability constraint type `consent_required`，使某些 capability grant 在 Move 验证时 runtime check holder consent。本规范定义的 consent cell 是该 constraint 的查询源。在引入该 constraint 前，consent gate 由 invite / contact service 在投递前查询 cell join 值实现，不直接出现在 Move precondition 上。
