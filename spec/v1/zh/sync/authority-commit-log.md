---
title: Authority Commit Log
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - federation.md
  - client-sync.md
---

# 权威提交日志

本章的逐 stream 连续性、私有 handoff head 清单与公开 bundle 不泄漏规则由
`ak.vector.authority_commit.independent_streams.v1` 覆盖。三类必须拒绝的情形各有可执行负例向量：
断链与 position 跳号由 `ak.vector.authority_commit.stream_continuity_negative.v1` 覆盖；同一
`(realm_id, stream_ref, governance_generation, stream_position)` 上的双 Commit 冻结由
`ak.vector.authority_commit.equivocation_freeze.v1` 覆盖；planned handoff 生效后旧 Station 的写入拒绝由
`ak.vector.authority_commit.post_handoff_write_rejected.v1` 覆盖。

本章定义 Arkret v1 共享 Realm 状态的唯一接纳、排序、复制、恢复与治理方更换协议。规范关键字按[规范语言](../conformance/normative-language.md)解释。

## 1. 单治理方、多个可见性 stream

每个 Realm 在任一时刻恰有一个当前治理 Station。该 Station 分别维护：

- 一条 Realm stream；
- 每个 Circle 各一条 Circle stream；
- 每个 Sidecar 各一条 Sidecar stream。

三类 stream 彼此没有全局 position，也没有跨 stream 总序。实现可在内部使用同一数据库 WAL，但不得把内部序号暴露为协议顺序。这样，无权读取某个 Circle 或 Sidecar 的主体不会从 Realm-wide position 缺口推断隐藏活动。

Realm membership、policy 和 authority 变更只提交到 Realm stream。治理 Station 在处理子 stream Event 时，必须先在内部读取已经提交的 Realm current state；该授权 revision 是接纳事务内部输入，不是 producer 可提供或替换的证明。

## 2. Producer Event

共享 Event 是 closed producer-signed object，只含：

`event_id, kind, realm_id?, scope_ref, actor_id, executed_by?, authorization_ref?, applet_id?, external_ref?, created_at, refs?, payload, proofs`。

`realm_id` 仅在 `ak.realm.create` 的现有派生例外中省略。`refs` 只表示注册的业务引用。Event 不得携带 `producer_revision`、`hlc`、`domain_refs`、`preconditions`、`commit_authorization_state`、`commit_base`、`expected_revision`、`requirements` 或 `unsigned`。该封闭禁用集合的机读投影是 [`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json) 的 `producer_event_envelope_root` context。

Event 不指向“上一个 Event”。producer 可能离线签名，且多个 producer 会并发；让 Event 绑定 head 会导致合法排队请求因其它写先提交而重签，MLS 请求甚至需要重建密码材料。最终顺序只能由接纳方分配。

## 3. RealmCommit 与逐 stream 单链

治理 Station 验证 Event 的 canonical ID、producer proof、current authorization、typed payload、领域不变量和 current target revision 后，在同一事务中写入 Event、领域状态、outbox 与 `RealmCommit`。

一条 `RealmCommit` 恰好接纳一条 Event：`event_ref` 与 `stream_position` 都是单值。多条 Event 的原子性是**事务级**的——治理 Station 在同一个接纳事务内接纳整组 Event，并为每条各自签发同一 stream 上连续的 RealmCommit；不存在覆盖多条 Event 的单张 Commit。

每个 `RealmCommit` 必须携带 `stream_ref`、`stream_position` 与 `previous_commit_ref`：

- `stream_ref` 必须由 Event 的 effective scope 和注册 kind 派生，caller 不得选择；
- 每条 stream 的 position 从 0 开始严格加一；
- position 0 的 `previous_commit_ref` 必须为 null；
- 其它 position 必须引用同一 stream 的 position - 1 Commit；
- predecessor 不得引用另一 Realm、Circle 或 Sidecar stream；
- `commit_id` 是去掉 signature 后 closed body 的 content-addressed typed ID；
- signature 只能由 `governance_generation` 对应的治理 Station service key 产生。

`governance_generation` 是**治理 Station 任期代次**，只由已接受的 `ak.realm.governance_station.change` 递增，其 `payload.expected_governance_generation` 就是对该计数器的 CAS。它与 authority-root typed current result 的 `authority_generation`（授权委派代次，只由 `ak.realm.authority.reset` 递增）是两个不同的计数器，MUST NOT 互相替代；一次 planned handoff 不改变任何 grant 的有效性。

同一个 Event 最多有一个 successful Commit。exact retry 返回同一 Commit；拒绝和暂不可用不占 position。同一 `(realm_id, stream_ref, governance_generation, stream_position)` 上出现两个不同但签名有效的 Commit 是治理方 equivocation，消费方必须冻结该 Realm 的相关 stream，不得自动选 winner。

## 4. 写入状态

Account Station 对本地提交只可报告 `queued`、`forwarding`、`committed` 或明确失败。没有取得当前治理 Station 的有效 `RealmCommit` 时，不得报告 accepted、更新共享 current 或向其它成员 fanout。

治理 Station 一次请求只返回：

- `committed`：新 Commit；
- `duplicate`：同一 Event 的已有 Commit；
- `rejected`：确定性拒绝；
- `retryable_unavailable`：尚未产生共享事实，可用 exact Event 重试。

协议没有共享 pending、Ack、defer、RealmCommit prepare 或 closure 阶段。

## 5. Typed reducer 与并发

共享状态按同一 stream 的 Commit position 顺序执行 typed reducer。协议不提供 typed current result key、通用 CRDT、deterministic projection、rank、dot、通用 predicate 或 state-root DSL。

默认后提交的合法 typed Event 覆盖同一 target 的旧 current。确需避免覆盖的 kind 必须在自己的 payload 中定义 `expected_revision`，其值为该领域 current row 最后一个 Commit ID。比较失败时整个请求 rejected，不产生 Commit。

跨 stream 不提供原子提交。跨 Realm/Circle/Sidecar 工作流使用 exact committed ref、幂等 saga 和明确补偿 Event。

`exact committed ref` 是闭合四元组 `event_id + commit_id + stream_ref + stream_position`。
Directory 需要按公告来源向 source Station 取证时，必须调用
`ak.peer.events.read.resolve_committed.v1`。请求闭合为
`{realm_id, source_ref_access, refs[]}`：`source_ref_access` 是 source Station 签发且绑定 exact
Directory、Realm、当前 discovery Event、有效期与允许四元组集合的 `DirectorySourceRefAccess`；
`refs[]` 的每项必须逐字属于 carrier 的 `source_refs`。source Station 每次调用都重新验证已认证 caller
等于 `directory_id`、proof/expiry、当前 announce 未被撤销或取代，以及每个四元组仍匹配 exact
`RealmCommit + Event`。任一检查失败均零返回、零副作用。

其它业务不得把这个 Directory 专用 operation 当作通用 peer history API。任何 verifier 仍必须验证
Commit 签名与 authority chain；caller-supplied Event、仅 Event ID、猜测性 scan 或脱离 carrier 的 ref
都不是已接纳证明。该合同只解析各自 stream 内的位置，不建立任何跨 stream 顺序。

## 6. 读取、验证与完整性边界

消费方对每条获准 stream 独立验证：

1. authority generation 由 genesis + 连续 handoff chain 授权；
2. Commit signature 和 content-addressed ID 正确；
3. position 连续且 predecessor 等于本地 head；
4. `event_ref` 对应 exact Event ID；
5. Event producer proof 正确；
6. `stream_ref` 与 Event effective scope 一致。

消费方只能证明自己获准读取的 stream 没有缺口。它不能、也不得要求证明无权查看的 Circle/Sidecar 是否完整；这是一条明确的隐私边界。治理 Station 仍可在接纳前扣留 Event，因此 base v1 不提供独立 omission proof。

## 7. Snapshot 与 join bootstrap

Snapshot 是当前治理 Station 签署的 typed current sections，必须绑定 `governance_generation` 和调用方获准的全部 stream heads。它不含 typed current result chunks、state root、RealmCommit、fixed reducer semantics 或稀疏 Merkle proof。

加入流程必须为：

1. invite、分享链接、邀请人 Station 或 Directory 提供 `realm_id` 和 authority locator candidate；
2. 客户端取得 genesis Event/Commit、完整连续 handoff chain 和当前方 nonce-bound assertion；
3. join Event 经自己的 Account Station 转发到已验证的当前治理 Station；
4. 只有 membership Commit 成功后才获得可见性；
5. 申请人的 Station 从当前治理 Station 拉取签名 Snapshot 和获准 stream 的 tail。

不得默认从邀请人 Station、初始治理 Station 或 genesis 开始拉取全部 Event。历史范围必须同时受 `history_access`、join position、Circle membership、retention 和 MLS epoch 可读性限制。

## 8. 治理 Station 更换

只支持旧治理方在线的计划 handoff。controller 先提交 `ak.realm.governance_station.change` 到 Realm stream；旧方随后冻结所有 stream，生成包含每条 final head 的 Snapshot，并签署 `RealmAuthorityHandoff`。新方必须完成验证和导入后签署 acceptance。

Handoff 必须绑定：连续 generation、旧/新 service identity、change Event、Realm-stream final change Commit、全部 `final_stream_heads` 的 canonical digest、Snapshot ID/digest，以及旧方和新方签名。

新 generation 在每条已有 stream 上的第一个 Commit 必须以前一 generation 导入的该 stream final head 为 predecessor。旧方在 handoff 生效后永久拒绝新写；新方在未完整导入前不得启动。

旧方永久丢失且没有完成 handoff 时，不允许自动选主、管理员自封或从备份恢复同一 Realm 的写权。可验证缓存保持只读；需要继续协作时创建显式 successor Realm，新的 Realm 不继承旧 position 或 MLS group。

## 9. MLS 边界

治理 Station 只跟踪 MLS 公开状态，不持有成员 secret。共享 Event 只保留 `ak.mls.genesis` 与 `ak.mls.commit`。Proposal 内联于 Commit；Welcome 是 recipient delivery；KeyPackage/claim 是专用 ledger；失败是本地诊断。

每个 MLS effective scope 属于其对应 Realm、Circle 或 Sidecar stream。`key_access_revision` 在会改变新 epoch 密钥获得者的 membership、endpoint authorization 或相关 policy 变化时递增。encrypted application Event 的 epoch、group state ref 和 key-access revision 必须都等于 current，否则拒绝。

Add 使用 `MlsCommitSubmission` 原子提交 Commit Event 和全部 producer-signed Welcome deliveries。治理 Station 在同一事务中提交 Commit、更新 public state、写 recipient queues 和 outbox；任一 Welcome 无效则零写入。Handoff 迁移 public tree、epoch、revision、claim 状态和 Welcome queues，但不迁移任何成员 private MLS state。
