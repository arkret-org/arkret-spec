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

本规范定义 Contrix 的 consent state machine，与 capability / invite 正交。模型借鉴自 [`draft-ietf-mimi-protocol`](https://datatracker.ietf.org/doc/draft-ietf-mimi-protocol/) 的 consent 概念，并完整融入 Contrix 的 signed Event + state slot 架构。

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

## 3. Event Family

### 3.1 `cx.consent.grant`

```json
{
  "kind": "cx.consent.grant",
  "space_id": "cx:space:01js0aps000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "payload": {
    "consent_id": "cs-2026-05-07-bob-invite",
    "peer": "did:web:bob.example.com",
    "scope": "invite",
    "not_before": "2026-05-07T00:00:00Z",
    "valid_until": "2026-12-31T00:00:00Z",
    "evidence_ref": "cx:event:01js0pres000000000000000000",
    "reason": "Bob completed verified contact discovery"
  }
}
```

字段：

- `consent_id`：state slot 主键（`state_subject_field=payload.consent_id`）。同一 holder 对同一 peer 的不同 scope 用不同 consent_id；同 consent_id 的 grant/revoke 共享 slot。
- `peer`：counterparty DID 或 pairwise DID。
- `scope`：详见 §4。
- `not_before` / `valid_until`：时间窗口（可选）。窗口外 consent 不生效，相当于 implicit revoke。
- `evidence_ref`：可选审计链——指向引发此 consent 的 claim disclosure / presentation response / invite proof event。
- `reason`：人类可读理由（仅审计，不参与授权）。

`actor_id` MUST 是 holder 自己（或 holder DID Document 显式授权的 controller / agent）。其他 actor 提交的 `cx.consent.grant` 在 holder 的 principal control Space MUST `capability_denied` reject。

### 3.2 `cx.consent.revoke`

```json
{
  "kind": "cx.consent.revoke",
  "space_id": "cx:space:01js0aps000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "payload": {
    "consent_id": "cs-2026-05-07-bob-invite",
    "revoked_at": "2026-06-15T10:00:00Z",
    "reason": "Bob harassment incident #4711"
  }
}
```

`payload.consent_id` MUST 等于被撤销 grant 的 consent_id。reducer 把 revoke 当作对该 consent slot 的 supersede（与 `cx.capability.grant` ↔ `cx.capability.revoke` 同一模式）。

撤销在 frontier 后立即生效；frontier 之前已经被 peer 凭借 consent 发出的 invite / contact 不会被追溯失效（已经发出的 invite 由 invite revoke 单独处理）。

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

## 5. Reducer 与 State Slot

`cx.consent.grant` 与 `cx.consent.revoke` 共享 state slot，主键 `(space_id, "cx.consent.grant", consent_id)`：

- slot 上最新 accepted event 决定该 consent 当前状态：
  - `cx.consent.grant`：grant 生效（在 `not_before` / `valid_until` 窗口内）。
  - `cx.consent.revoke`：revoke 生效；slot effective state = revoked。
- consent slot 的派生 effective state 由 reducer 物化为 `Consent` 对象（详见 [`models/data-structures.md`](../models/data-structures.md)，本节定义事件层面）。
- 不同 consent_id 是独立 slot；查询 `(holder, peer, scope)` 时 reducer 遍历该 holder 全部 consent slot 匹配。

## 6. 与 Invite / Contact 流程的整合

### 6.1 Invite 前置 gate

Peer 发送 `cx.invite.create` / `cx.invite.third_party` 时，invite service / facade SHOULD 在投递前查询 holder 的 consent state：

1. 调用 holder 的 principal control Space（或受托 contact discovery service）查询 `(peer=requester, scope="invite" OR scope="any")` 的最新 accepted consent event。
2. 若当前 effective state 不存在或为 revoked：
   - **`require_explicit_consent` profile**：invite MUST `consent_required` reject。Peer SHOULD 通过 `cx.private_contact_discovery.v1` 等机制请求 holder 显式授权后重试。
   - **default profile**：invite MAY 进入 holder 的 quarantine inbox（"陌生人邀请"），由 holder 在 UI 上 review 后转为 grant 或 reject。
3. 若 effective state 是 grant 且未过期：invite 正常处理。

policy MAY 声明 `cx.space.policy_components` 中的 `preauth` component 包含 `require_consent: true`，对该 Space 的所有 invite 强制走显式 consent 路径。

### 6.2 Contact / DM 前置 gate

类似地，发起 1:1 message Space、WebRTC call、presence subscription 时，发起方 SHOULD 验证目标的 consent state（scope = `direct_message` / `voice_call` / `video_call` / `presence`）。

`cx.private_contact_discovery.v1` 在返回 reachability proof 时，可附带 holder 当前 consent state hash（不暴露具体 consent 内容，只声明 grant/revoke 状态），让发起方在尝试联系前判断是否需要先请求 consent。

## 7. MIMI Interop

MIMI 协议有 `request_consent` / `update_consent` 操作（`cx.mimi.request_consent` / `cx.mimi.update_consent`），见 [`extensions/mimi-interop.md`](../extensions/mimi-interop.md) §10。Facade 映射规则：

- 接收 MIMI consent update：facade MUST 先验证 actor 是声明 holder 或受授权 controller，然后归约为 holder principal control Space 的 `cx.consent.grant` 或 `cx.consent.revoke`。
- 发送 Contrix consent state 到 MIMI：facade MUST 把当前 consent slot effective state 翻译为 MIMI consent message，并保留 consent_id 作为 inter-protocol correlation。
- consent state 不暴露具体 evidence_ref / reason 跨 provider；只暴露最小 `(peer, scope, granted/revoked)` 三元组。

## 8. 隐私与审计

- consent state 是 holder 私有；服务端 MUST NOT 把它暴露给非 holder actor 或非授权 service。
- consent grant / revoke 的 backfill 受 holder principal control Space 的 history visibility 与 access policy 约束。
- audit projection MAY 记录 consent state 变化（用于合规审查），但 audit access 必须经 holder 授权或 legal hold 边界。
- pairwise DID / pseudonym 场景下，consent 可绑定 pairwise DID 而非真实 principal DID；reducer 不强制 consent.peer 必须是 principal DID。

## 9. 与未来 Capability Constraint 的关系

未来 v1.x profile MAY 引入 capability constraint type `consent_required`，使某些 capability grant 在执行时 runtime check holder consent。本规范定义的 consent state machine 是该 constraint 的查询源。在引入该 constraint 前，consent gate 在 invite / contact service 层实现，不参与 reducer 授权计算。
