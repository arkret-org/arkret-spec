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

`event_id, kind, realm_id?, scope_ref, actor_id, executed_by?, authorization_ref?, applet_id?, external_ref?, created_at, semantic_refs?, payload, producer_proof`。

`realm_id` 仅在 `ak.realm.create` 的现有派生例外中省略。`semantic_refs` 只表示注册的业务引用。Event 不得携带 `producer_revision`、`hlc`、`domain_refs`、`preconditions`、`commit_authorization_state`、`commit_base`、`expected_revision`、`requirements` 或 `unsigned`。该封闭禁用集合的机读投影是 [`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json) 的 `producer_event_envelope_root` context。

Event 不指向“上一个 Event”。producer 可能离线签名，且多个 producer 会并发；让 Event 绑定 head 会导致合法排队请求因其它写先提交而重签，MLS 请求甚至需要重建密码材料。最终顺序只能由接纳方分配。

## 3. RealmCommit 与逐 stream 单链

治理 Station 验证 Event 的 canonical ID、producer proof、current authorization、typed payload、领域不变量和 current target revision 后，在同一事务中写入 Event、领域状态、outbox 与 `RealmCommit`。

一条 `RealmCommit` 恰好接纳一条 Event：`event_ref` 与 `stream_position` 都是单值。多条 Event 的原子性是**事务级**的——治理 Station 在同一个接纳事务内接纳整组 Event，并为每条各自签发同一 stream 上连续的 RealmCommit；不存在覆盖多条 Event 的单张 Commit。

每个 `RealmCommit` 必须携带 `stream_ref`、`stream_position` 与 `previous_commit_ref`：

`RealmCommit.signature` 使用 `ak.realm_commit_signature.v1`。签名方必须是
`governance_generation` 对应、且由已验证 genesis→handoff authority chain 授权的治理 Station service signing
key；`verification_method` 必须属于该 exact service identity。验证方从完整 Commit 删除 `signature`，对其余实际存在
成员作 RFC 8785 JCS，重算 `sha256:` 小写 SHA-256 digest；再以
`UTF8("ak.realm_commit_signature.v1\n") || RFC8785_JCS({context,signature_algorithm,verification_method,signed_digest,created_at})`
为 Ed25519 输入。验证方必须先逐字比较重算 digest，再按上述 authority chain 解析 key；不得信任 carrier 自报 digest 或
仅按自报 `verification_method` 选 key。

- `stream_ref` 必须由 Event 的 effective scope 和注册 kind 派生，caller 不得选择；
- 每条 stream 的 position 从 0 开始严格加一；
- position 0 的 `previous_commit_ref` 必须为 null；
- 其它 position 必须引用同一 stream 的 position - 1 Commit；
- predecessor 不得引用另一 Realm、Circle 或 Sidecar stream；
- `commit_id` 是去掉 signature 后 closed body 的 content-addressed typed ID；
- signature 只能由 `governance_generation` 对应的治理 Station service key 产生。

`governance_generation` 是**治理 Station 任期代次**，只由已接受的 `ak.realm.governance_station.change` 递增，其 `payload.expected_governance_generation` 就是对该计数器的 CAS。它与 authority-root typed current result 的 `authority_generation`（授权委派代次，只由 `ak.realm.authority.reset` 递增）是两个不同的计数器，MUST NOT 互相替代；一次 planned handoff 不改变任何 grant 的有效性。

同一 governing Station 对多个 Realm 执行 [`../governance/join-policy.md` §4](../governance/join-policy.md) 的
`parent_membership` gate 时，接纳事务必须按 RealmId canonical bytes 排序锁定每个 Realm 的 current authority tenure
`(service_id, governance_generation)`、目标 policy／link rows 与 source authoritative `member_state` lookup。各 Realm 的
`governance_generation` 只须分别为 current，数值不得跨 Realm 比较；`authority_generation` 也不能替代它。只有全部 tenure
的 `service_id` 相同且所有依赖处于同一内部原子事务 cut 时才能继续。同 Station 的分库实现若不能形成该 cut，必须
fail closed，不能以 saga、cache 或 snapshot 近似。

source membership、target link 或任一 Realm handoff 与 join 并发时，统一锁序给出唯一线性结果：依赖变更先提交则 join
零写入失败；join 先提交则该次 admission 有效，后续 source change 不追溯撤销目标 membership。handoff 后必须从新 tenure
rows 重新判断 co-governance；旧 generation 的内存 projection 不得继续授权。

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

默认后提交的合法 typed Event 覆盖同一 target 的旧 current。确需避免覆盖的 kind 必须在自己的 payload 中定义 `expected_revision`，其类型是 [`current-results.md`](./current-results.md) 的封闭 `revision`，即 `{commit_id, stream_position}` 二元组，比较是**逐字段相等**；它不是裸 Commit ID，也不是计数器。比较失败时整个请求 rejected，不产生 Commit。account-private 面按 key 计数的 `expected_server_revision` 是另一个东西，不要与它混用。

跨 stream 不提供原子提交。跨 Realm/Circle/Sidecar 工作流使用 exact committed ref、幂等 saga 和明确补偿 Event。

`exact committed ref` 是闭合四元组 `event_id + commit_id + stream_ref + stream_position`。
任何 verifier 仍必须验证 Commit 签名与 authority chain；caller-supplied Event、仅 Event ID、猜测性 scan
或脱离已验证读取结果的 ref 都不是已接纳证明。该合同只解析各自 stream 内的位置，不建立任何跨 stream 顺序。

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

Snapshot 是当前治理 Station 签署的 closed `realm-state-snapshot.schema.json` 对象：内联 `current_state_entries[]` 是可见范围内的 typed current result rows，并与 `governance_generation`、调用方获准的全部 `visible_stream_heads[]`、`retention_and_history_floor` 取自同一 durable cut。它不含另一个 `sections`／`chunk_digests` wire 层、独立 typed-current chunk/tree、state root、RealmCommit、fixed reducer semantics 或稀疏 Merkle proof。签名确认当前治理方对这份 materialization 负责；它不证明隐藏 stream 不存在，也不构成独立 omission proof。

加入流程必须为：

1. invite、分享链接、邀请人 Station 或 Directory 提供 `realm_id` 和 authority locator candidate；
2. 客户端取得 genesis Event/Commit、完整连续 handoff chain 和当前方 nonce-bound assertion；
3. join Event 经自己的 Account Station 转发到已验证的当前治理 Station；
4. 只有 membership Commit 成功后才获得可见性；
5. 申请人的 Station 从当前治理 Station 拉取签名 Snapshot 和获准 stream 的 tail。

不得默认从邀请人 Station、初始治理 Station 或 genesis 开始拉取全部 Event。历史范围必须同时受 `history_access`、join position、Circle membership、retention 和 MLS epoch 可读性限制。

## 8. 治理 Station 更换

只支持旧治理方在线的计划 handoff。controller 先提交 `ak.realm.governance_station.change` 到 Realm stream；旧方随后冻结所有 stream，生成包含每条 final head 的 Snapshot，并签署 `RealmAuthorityHandoff`。新方必须完成验证和导入后签署 acceptance。

handoff 的旧方 `ak.realm_authority_handoff_old_signature.v1` 与新方
`ak.realm_authority_handoff_new_acceptance_signature.v1` 共享同一个 unsigned projection：从完整 handoff 同时删除
`old_authority_signature` 和 `new_authority_acceptance_signature`，除此之外保留全部实际存在成员。两份
`signed_digest` 必须相同；旧方 key 必须属于 `from_generation/from_service_id` 在冻结 cut 上仍为 current 的治理
Station，新方 key 必须属于 `to_generation/to_service_id`，且只能在完整验证并导入 frozen handoff 后签 acceptance。
两者分别用自己的 context prefix 与完整五成员 signature envelope 按本章 §3 的相同 RFC 8785 JCS、SHA-256、Ed25519
构造签名；验证方独立重算投影、digest、prefix 和签名输入，且不得互换 old/new context 或 key。

Handoff 必须绑定：连续 generation、旧/新 service identity、change Event、Realm-stream final change Commit、全部 `final_stream_heads` 的 canonical digest、Snapshot ID/digest，以及旧方和新方签名。

新 generation 在每条已有 stream 上的第一个 Commit 必须以前一 generation 导入的该 stream final head 为 predecessor。旧方在 handoff 生效后永久拒绝新写；新方在未完整导入前不得启动。

旧方永久丢失且没有完成 handoff 时，不允许自动选主、管理员自封或从备份恢复同一 Realm 的写权。可验证缓存保持只读；需要继续协作时创建显式 successor Realm，新的 Realm 不继承旧 position 或 MLS group。

## 9. MLS 边界

治理 Station 只跟踪 MLS 公开状态，不持有成员 secret。共享 Event 只保留 `ak.mls.genesis` 与 `ak.mls.commit`。Proposal 内联于 Commit；Welcome 是 recipient delivery；KeyPackage/claim 是专用 ledger；失败是本地诊断。

每个 MLS effective scope 属于其对应 Realm、Circle 或 Sidecar stream。`key_access_revision` 只由该 scope stream 上改变 current joined 成员集合的 membership Event 在同一事务加一；endpoint authorization 与 policy 变化不推进它，已撤销 endpoint 的发送由 send gate 同 cut 拒绝。encrypted application Event 的 epoch、group state ref 和 key-access revision 必须都等于 current，否则拒绝。

Add 使用 `MlsCommitSubmission` 原子提交 Commit Event 和全部 producer-signed Welcome deliveries。治理 Station 在同一事务中提交 Commit、更新 public state、写本站 recipient queues 和 outbox；跨站 recipient 的 Welcome 写入指向其 routing service 的 outbox intent，随 Commit 的 committed-replication item 由成员站在同一 replica 事务按本地 claim ledger 复核入队；任一本站可判定的 Welcome 无效则零写入。Handoff 迁移 public tree、epoch、revision、claim 状态和 Welcome queues，但不迁移任何成员 private MLS state。
