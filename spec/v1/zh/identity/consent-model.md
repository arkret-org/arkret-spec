---
title: Consent 模型
status: candidate
normative: true
stability: v1
updated: 2026-09-16
sidebar:
  label: Consent 模型
---

## 0. 规范语言

本文中的规范关键字按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 边界

Consent 是 holder 在 Principal Control Realm（PCR）中维护的方向性许可，用于 invite、通话发起与 presence 等不以 Contact 为授权依据的动作。Contact request/response、Contact-based create/send 与 Personal DM 只读取双方 holder-signed Contact facts，不读取 Consent。

Consent 不授予 Realm capability，也不替代目标 Realm 的 membership、policy 或 authorization 检查。它只决定 holder 的 Station 是否允许相应首次接触继续进入目标 operation。

## 2. 稳定身份与 current result

每条 Consent 由 producer 分配的 `consent_id` 唯一标识。typed current result selector 是该稳定 `consent_id`，value 包含：

- 完整 peer ActorId；
- `consent_scope`；
- 可选 `not_before`、`expires_at`、约束、证据引用与理由；
- `active | revoked | expired` 状态。

current revision 不是 value 的成员：typed current result 的 `revision` 与 `value` 同层，是封闭的 `{commit_id, stream_position}`（见 [`sync/current-results.md` §2](../sync/current-results.md)），`commit_id` 即产生该 revision 的 RealmCommit。

同一 `consent_id` 在任一时刻只有一个 current value。治理 Station按 PCR Realm stream 的 Commit 顺序执行 reducer；协议不暴露集合标签、写索引或合流元数据。

## 3. Event

### 3.1 `ak.consent.grant`

Grant payload 使用 `event-payload.schema.json#/$defs/consent_grant_payload`：

```json fragment
{
  "consent_id": "ak:consent:018f2d40-0000-7000-8000-000000000001",
  "peer": {"kind": "actor", "actor_id": "did:webvh:example.net:u:bob"},
  "consent_scope": "invite"
}
```
`consent_id` 必须尚未存在；相同 Event 的重试返回同一提交结果，不产生第二条 Consent。另一个 Event 复用该 ID 必须以 `failed_precondition` 拒绝。

### 3.2 `ak.consent.revoke`

Revoke payload 使用同一稳定 ID，并要求调用方签入 current revision：

```json fragment
{
  "consent_id": "ak:consent:018f2d40-0000-7000-8000-000000000001",
  "expected_revision": {
    "commit_id": "ak:realm_commit:0Zm5xr9E1cVJm2Q7pT4sN8bK6hW3yD1gXfL0aRtUvOc",
    "stream_position": 7
  },
  "reason": "holder_request"
}
```
治理 Station必须在 commit 事务中同时验证目标存在、仍为 active 且 current revision 等于 `expected_revision`。成功后 revision 变为接纳该 Event 的 RealmCommit 的 `{commit_id, stream_position}` 并进入 `revoked`；stale revision、未知 ID、重复撤销或主体不匹配均拒绝。撤销只影响后续 admission，不追溯撤销已经提交的其它 Realm Event。

### 3.3 Producer 与提交

Grant/Revoke Event 的 actor 与认证 holder 必须是 holder PCR 当前 authority-root controller，`authorization_ref` 必须绑定该控制权。服务只接受调用方给出的 `EventCommitSubmission { event }`，不得代写、重建或代签 Event。只有当前治理 Station签发的 `RealmCommit` 使更新生效。

## 4. Scope

`consent_scope` 的 closed 值为：

| 值 | 语义 |
| --- | --- |
| `invite` | peer 可发起 Realm/Strand invite。 |
| `voice_call` | peer 可发起语音通话。 |
| `video_call` | peer 可发起视频通话。 |
| `presence` | peer 可观察 holder presence。 |
| `any` | 覆盖全部具体 scope。 |

### 4.1 `any` 与撤销

`any` 是一条独立 Consent，不隐式创建其它记录。撤销某个具体 scope 不影响 `any`；若 holder 希望停止全部许可，客户端必须分别对相关 active `consent_id` 提交带正确 revision 的 Revoke Event。UI 必须在确认前列出仍会保持 active 的 Consent。

### 4.1.1 缓存失效

Revoke 被 RealmCommit 接纳后，holder Station必须立即使相应 invite gate、通话 gate、presence、private discovery 与 MIMI consent cache 失效。`any` 被撤销时，使该 peer 的全部具体 scope cache 失效。缓存不得把 current revision 回退或延迟已知撤销。

### 4.1.2 引入证据

holder 可把 active `invite` 或 `any` Consent 的 `CommittedEventRef` 作为 audience-bound introduction evidence。接收方必须向 holder 的 current authority 验证该 ID 当前仍 active；证据本身不复制 Consent value，也不授予目标 Realm 权限。

## 5. Effective Consent

查询 `(holder, peer, concrete_scope)` 时，以下任一 current record 可满足 gate：

- peer 完整 ActorId相等且 scope 等于 concrete scope 的 active record；
- peer 完整 ActorId相等且 scope=`any` 的 active record。

时间窗口必须包含当前验证时间。未知、不可验证、已过期或 authority freshness 不足一律视为未授权。不同 Realm 的 pairwise ActorId不得因 principal DID相同而聚合。

## 6. Operation admission

### 6.1 Invite gate

holder Station在 invite delivery admission 查询 holder PCR 的 typed current result；目标 Realm治理 Station不读取 holder PCR 状态，producer 也不把查询结果写入目标 Event。

`require_explicit_consent` policy 下，没有可验证 active Consent 的 delivery 必须静默丢弃。default policy 下可进入 holder-private quarantine 供 holder review；该 holder-private 数据以 account-data key `ak.account.holder_quarantine` 保存。对 requester 的响应必须保持 `status="deferred"` 且不披露 account existence、Consent 状态、送达或 quarantine 结果。

有 active Consent 只允许 invite 继续提交；目标 Realm仍独立执行其 current membership、capability、policy 与 typed revision 检查。

### 6.1.1 First-contact anti-abuse

holder Station必须在 invite delivery、Contact delivery 与 consent request 的共同入口执行 per-holder 新来源速率和总量限制。identity key 使用完整来源 principal/ActorId，不得只按 IP、域名或裸 DID 聚合。

#### 6.1.1.3 Chokepoint

限速判定与 holder-private queue 写入必须位于同一事务边界。超过限额、holder 不存在、policy deny 与成功排队对 requester 返回同一 opaque 结果；失败分支不得留下可观察副作用。

### 6.2 跨 Station

跨 Station requester 不得查询 holder 的 Consent 列表。holder Station只返回最小、短期、audience-bound admission outcome，且 requester 不得把该 outcome 当成 Realm authorization。

#### 6.2.2 主动披露

holder 可主动签发短期 green-light，绑定 holder、peer、scope、audience、PCR RealmCommit 与 expiry。验证方必须向 current authority确认 freshness；green-light 不包含 Consent value或其它 peer 列表。

## 7. MIMI 映射

MIMI update facade只接受调用方签署的 `EventCommitSubmission`，并按 decision 映射到 `ak.consent.grant` 或 `ak.consent.revoke`。facade不得构造 Event。对外投影只暴露最小 `(peer, scope, active)`，不暴露 reason、evidence 或 revision。

## 8. 隐私与管理

Consent list/get 仅允许 holder 或 holder 明确授权的 controller。peer 不能读取 holder 的 Consent ID、revision、expiry 或历史。管理 UI 可按 peer 聚合展示，但不得把聚合视图写回 wire。

### 8.1 本地聚合撤销

“撤销该 peer 的全部许可”是客户端编排：先从同一 current authority取得 holder 可见的全部 active Consent，再为每个 `consent_id` 用其精确 current revision签署 Revoke Event。任一竞争更新都使对应 Event stale；客户端必须刷新后重新确认，不得由服务端隐式扩大撤销集合。

## 9. Conformance

实现至少验证：唯一 `consent_id`、stale revision 拒绝、exact retry、`any` 与具体 scope 的独立性、撤销后 cache 即时失效、跨 Station anti-enumeration、pairwise ActorId隔离以及 requester 观察等价类。
