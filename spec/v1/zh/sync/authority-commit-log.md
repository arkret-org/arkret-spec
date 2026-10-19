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

普通 `ak.mls.commit` 的本地恢复 MUST 绑定完整冻结 Event 与 exact retry unit。客户端只有取得现有受权载体的确定性治理拒绝、且该结果排除同 Event 早先已接纳及仍在处理的成功尝试时，才 MAY 释放 exact own pending candidate。治理 `rejected` 的生产者 MUST 在相同 Event 的幂等／接纳互斥边界内查重；已有 Commit MUST 返回原 Commit，不能后来改报 rejected。不存在这种排他终局语义的响应只能保留 unknown，不能依据标签或 HTTP 状态猜测。

零写入语义 Problem（包括 `failed_precondition`／`governance_binding_mismatch`）只证明该次处理未写入，不能证明早先丢响应尝试未成功。请求层400/422、transport failure、权限丢失、不可见／not_found、retryable/unavailable MUST NOT 释放候选。已有受权 exact Event 读取或 exact retry 可以恢复原 accepted Commit；读取缺失不证明全局未接纳。不新增普通 Commit 查询面、共享 pending 或 Genesis wire。unknown MUST 耐久保留原冻结提交字节、重试身份、candidate bytes／身份及恢复 checkpoint，重启不得重签、重加密或恢复 pre-authoring snapshot。

本地拒绝恢复 MUST 先耐久记录绑定 exact Event 的终局证据与清理意图，再只清 exact own candidate 并耐久保存密码状态，最后完成队列终止与 staged checkpoint retirement；实现 MAY 以一个本地原子事务完成，否则各阶段 MUST 幂等恢复。MUST 保持已安装 epoch、application ratchet、Signal nonce 和其它 candidate；候选不匹配时不得误删。清理后崩溃重启须从耐久清理结果续接，不能重新安装冻结的旧 pending checkpoint。已取得 accepted Commit 时 MUST 保留成功事实，迟到请求错误不得覆盖；与排他拒绝冲突的受权结果 MUST 保留证据、停止破坏性清理，不按到达顺序选终局。

## 5. Typed reducer 与并发

共享状态按同一 stream 的 Commit position 顺序执行 typed reducer。协议不提供 typed current result key、通用 CRDT、deterministic projection、rank、dot、通用 predicate 或 state-root DSL。

默认后提交的合法 typed Event 覆盖同一 target 的旧 current。确需避免覆盖的 kind 必须在自己的 payload 中定义 `expected_revision`，其类型是 [`current-results.md`](./current-results.md) 的封闭 `revision`，即 `{commit_id, stream_position}` 二元组，比较是**逐字段相等**；它不是裸 Commit ID，也不是计数器。比较失败时整个请求 rejected，不产生 Commit。account-private 面按 key 计数的 `expected_server_revision` 是另一个东西，不要与它混用。

跨 stream 不提供原子提交。跨 Realm/Circle/Sidecar 工作流使用 exact committed ref、幂等 saga 和明确补偿 Event。

`exact committed ref` 是闭合四元组 `event_id + commit_id + stream_ref + stream_position`。
消费 Station 与独立审计 verifier 仍必须验证 Commit 签名与 authority chain；普通客户端按
[`server-trusted-results.md` §2.1](./server-trusted-results.md#21-普通客户端消费既有治理结果normative)
消费自己的已认证 Station 验证后转达的原件，不重放方法历史。caller-supplied Event、仅 Event ID、猜测性 scan
或脱离已验证读取结果的 ref 都不是已接纳证明。该合同只解析各自 stream 内的位置，不建立任何跨 stream 顺序。

### 5.1 登记式原子单元（normative）

公共入口复用 `ak.self.events.command.submit.v1` 与 `ak.peer.events.command.submit.v1`，不增加通用事务端点。
`contract-registry.json.atomic_unit_registry` 是可接纳单元、typed request、顺序来源、转发及复制范围的唯一登记。
caller MUST 选择已登记 closed branch，MUST NOT 提交任意 `events[]`、`atomic=true`、自选 predicate、步骤或跨 stream 计划。
普通 Realm bootstrap、Direct Conversation founding、membership compensation 保留原 typed shape、专有授权和重放 fence；
MLS Commit + Welcome 保留专用合同。共享执行框架 MUST NOT 把「共用事务机制」解释成这些业务可以互换参数。

共同接纳规则：治理 Station 在任何效果前固定完整 canonical unit bytes；锁定 current authority、唯一 Realm／effective stream
及全部适用 current 授权依据；逐 slot 验证 Event ID／digest、完整 actor、实际 producer proof、当前设备／Agent／controller／
Applet 与两层 approval，并执行该单元登记的 staged 依赖和业务 CAS。所有 Event、逐 Event 连续 RealmCommit、typed current／
durable fact、必要私密审计、完整请求与原 outcome、outbox MUST 在同一事务耐久提交；失败 MUST 零写入且不占 position。
只有登记的 staged 依赖可使用同 unit 前一 slot，不能从 caller 数组推导任意依赖或先提交部分效果。
每个单元只有一个 indivisible outcome，无 per-item partial；不新增 unit-level acceptance receipt。

完整 canonical 请求的 exact retry MUST 返回第一次记录的接纳原件与结果，不能重新运行 reducer、CAS 或 fanout；
既有 outcome 的 `status:duplicate` 标记可按其登记 schema 返回，除该重放标记外原 Commit／业务结果必须逐字保持；
不同 bytes 复用同一登记的业务 fence MUST `duplicate_conflict`。原结果和 fence 是耐久事实，不是短期 HTTP cache。
transport-only producer evidence 刷新不改变内层 signed unit；peer 外层 `canonical_hash/full_body` replay 与内层 unit fence
分别核对，外层不同不能授权内层再次接纳。存储中已出现部分 unit、原结果或 fence 未决时 MUST `revision_unavailable`，
不能把缺记录当成首次写。恢复／handoff 必须保留可验证原件、完整 unit 接纳关系、业务 fence 与适用私密审计；
尚不能重建原 outcome 时只可失败关闭，MUST NOT 重新执行。

所有公共多 Event 单元 MUST 处于同一治理 Station、同一 Realm 和同一 Realm／Circle／Sidecar stream；
读取父 Realm current 的授权 cut 不产生跨 stream Event 原子性。跨 stream／跨站工作流继续使用 committed ref、幂等恢复与明确补偿。
Recovery／SecurityRotation 是 durable workflow，不能包装成单笔「全部回滚」的 Event 单元或通用 Saga DSL。

`authority_forward` 是首次接纳：本轮只为 `audit_paired_event` 增加 typed `atomic_submission`，
其它既有 self-only 单元不能因此被转发。`registered_atomic_unit` 是已 source-committed 单元的整体复制：
接收方验证原 source Commit／proof／signer fact、顺序与本机披露资格，整体保存／物化或零写；不重审首次 approval、
不重签 Commit、不产生第二轮 fanout。回传 source acceptance outcome 仅描述原治理站事实，不是接收方新增 finality。

### 5.2 业务与审计配对单元（normative）

`audit_paired_event_unit_submission` 固定为 `{unit_kind:"audit_paired_event",events:[business_submission,audit_submission]}`；
每个 slot 均是既有 `EventAdmissionSubmission`，保留各自 producer proof 与 required approval signatures。
第一 slot 仅允许登记的跨 actor `ak.strand.watch.set` 或 `ak.circle.member.state`，第二 slot 恰一条 `ak.audit.accessed`。
二者的 `realm_id`、derived effective scope／stream、完整 `actor_id`、actual producer（`executed_by` 存在时取它）
及签名 key MUST 一致；各自委托、当前授权、key/session/provision ceiling 与 approval 仍独立成立。
同一锁定 origin cut 可支持两个 slot，但不可用只绑定 business Event 的证明替代 audit Event 证明；
peer 携 fixed `atomic_producer_evidence[2]`，按 business／audit 顺序各自复用 Device／Agent 的既有 typed 证明。
Device 的 `event_authorization.event_id` 分别等于该 slot Event ID；`forward_body_digest` 均绑定完整 peer request
仅删除整个 `atomic_producer_evidence` 后的 canonical bytes，避免证明自引用。每个 slot 的窗口、原授权 ref、revision、PCR tenure
与 accepted_at 独立核对且来自同 origin cut。Service producer 的对应 slot 为 closed 空对象并沿用 Service历史核验；
不得携顶层单 Event 的 producer evidence，不能省掉任何 slot 的历史／当前检查。

audit payload 的 `writer_actor_id` MUST 等于 business 的完整 actor；`target_actor_id` 与 `target_ref` 按
`atomic_unit_registry.audit_pairs` 从业务 payload 派生，分别是 Watch 的 watcher／Strand 或 Circle 的 member／Circle。
`access_kind` 分别为 `watch_set_others`／`circle_member_set_others`；`paired_event_id` 和唯一 critical
`semantic_refs{role:"audit_pair"}` 的 id MUST 等于 business Event ID，且其内嵌 digest 与业务 canonical digest 一致。
business MUST NOT 反向引用 audit；先构造 business，再构造 audit，避免 ID 原像循环。
当前 caller 必须同时满足业务权限与 `ak.audit.accessed`；配对记录不提供新权限、不替代 CAS，也不携 caller 自报的结果 head。
Watcher／member MUST 与 writer 完整 ActorId 不相等；本人操作保留既有单提交入口。
每个 business Event ID 和 audit Event ID 都是 single-use fence；任一 ID 与不同 unit bytes 再配对必须 `duplicate_conflict`，
已单独接纳的 Event 不能补配后再次接纳或占据新位置。

Watch `.others` 的 level 仅可为 `mentions_only|participating|all`，不得清空／代写 `muted` 或 `level_public=true`，
整值 CAS 规则保持。Circle 跨 actor成员改写统一走此单元：`ak.circle.member.manage` 或
`ak.circle.member.add.others` 必须按自身 constraints／risk／approval 合法授权，且均不得绕过审计；
父 Realm join revision、FSM、Circle 当前资格和精确 scope 门保持，不隐式授予成员资格或历史 key。
缺 slot、多 slot、乱序、未登记 kind、错配、跨 scope、混 producer/key、缺 approval 或 CAS 冲突均整组零写拒绝。

`atomic_submission` 的跨站首次接纳必须使用 §5.1 的 authority-forward 角色及每次新鲜 device／Agent evidence；
完整 Account Station、current governor 与 S2S covered body 必须绑定。每条 source Commit 后的复制只允许
`audit_paired_event_federation_submission` 携恰两条原完整 committed Event，保持 business／audit 顺序及同 stream 连续位置。
普通 `committed_replication` 不得拆开接纳任何配对 slot；`registered_atomic_unit` 不得携首次接纳 producer evidence 或
private approval signatures。披露任一完整 slot 不合法、来源缺项或已有部分／冲突时整 unit 拒绝；有界 scan 中的 withheld
记录仍只证明原 Commit 存在，不能据其部分物化或证明从未写入。Snapshot／handoff 的原有完整性与披露门保持。

### 5.3 带审计的 Watch 精确读取（normative）

唯一消费面为 `ak.self.strand.watch.command.audit_read.v1` 与
`ak.peer.strand.watch.command.audit_read.v1`，绑定见 [HTTP §3.3.2](./service-http-binding.md#332-带审计的-watch-精确读取normative)。
它们是会写 durable audit Event 的 command，不是普通只读 query。self 请求只有 `audit_submission: EventAdmissionSubmission`；
Event MUST 是 `ak.audit.accessed{access_kind:"watch_audit_read"}`，不得携 `paired_event_id`。
Realm、Strand 与 watcher 唯一取自 Event 的 `realm_id`、`payload.target_ref` 与完整 `payload.target_actor_id`；
`actor_id`／`writer_actor_id` MUST 等于当前认证 effective Account。`purpose` 与 `accessed_at` 是 signed intent，不替代授权，
服务端 accepted 时间取 RealmCommit 的 `committed_at`。不重复携 caller selector、result id 或猜测的 head。

current governor 在一个事务 cut 中检查完整 auditor 的当前父 Realm membership、Strand 当前 lifecycle／scope、
`ak.realm.notification.audit` 与 `ak.audit.accessed` 两种权限、所有当前 producer／controller／Agent／Applet／approval 门，
以及 Watch 原件／durable current 完整性。Circle 下还必须是当前 effective member，或明确持有约束到该 Circle 的
`ak.circle.audit`。后一情形仅为本 command 的 `watch_audit_read` audit Event 提供记录这次获授权读取的受控接纳例外；
不授予普通 Circle Event 写入、membership、内容历史或 MLS key。普通 Event 提交／projection 不得复用此例外。
授权、scope、完整性或 audit 接纳失败时不写 audit、不释放值。成功在同事务接纳一条 audit、签一个 RealmCommit，
并耐久冻结该 exact Watch observation 与 canonical self request 绑定；事务提交后才释放 `watch_audit_read_outcome`。
其 `audit_commit` 逐字绑定请求 Event；`current` 复用 `StrandWatchCurrentOutcome`，保留 never_written 与 current:null，
其 Realm／selector／generation 正确且 `stream_head` 恰为该 audit Commit 的同 stream coordinate。

完整 canonical self request 与唯一 audit Event ID 是一次读取的耐久 fence。第一次只接纳一次；exact retry 只能返回原冻结结果，
不得重新查询最新值、再次写 audit 或用旧 audit 读新状态。同 audit ID 换 request bytes／approval evidence MUST
`duplicate_conflict`；先前仅经普通入口／其它操作 accepted 的 audit 没有这份绑定结果，不能改作读票。
`watch_audit_read` 本身 MUST 只在这两个 command 首接纳；standalone 普通 Event-submit 或 caller 提供 accepted audit ref
不得开放读取。其它 audit access_kind 的既有入口保持。

回放私有结果仍须当前 disclosure／delivery 许可；它不是可永久重放的授权 cache。已知撤权或不可见为 `not_found`；
未确认 current authority／scope／导入完整性、丢失 replay material 或已观察更高 governance generation 为 `revision_unavailable`。
同 generation 的后续 Watch 更新不替换冻结结果；获准重放的值仍是原 audit cut 的观察，不是最新值或未来 CAS 租约。
handoff 后旧 generation 的冻结结果不能作为新当前前态；需要新审计 Event 取得新观察，旧 audit 不重接纳。
审计 Event 表示治理站完成这次获授权读取，不证明网络成功或用户已看到；最终本地 session／device／Account／Agent
交付 gate 撤回时必须扣住结果，已经完成的治理审计不补造回滚或客户端收到的证明。

跨站先复用 nonce-bound authority bundle 确认唯一 current governor；Account Station 不向外站传 bearer／DPoP／session grant，
peer 以 S2S signature、完整 auditor Account Station 和新鲜 actual-producer device／Agent evidence完成 audit Event 首接纳。
本 command 的 actual producer 必须为 Account 的 Device 或 Agent runtime，完整 signer Account Station 必须等于 auditor Station；不接纳 Service producer 或 Service 代签。peer 必携恰一种 fresh device／Agent evidence。Event-origin producer proof 不可由服务端代签。每次转发 proof 刷新不改变 signed audit／canonical self request；
治理站只重放原 read fence，本地最终重验原 credential、device generation、撤回与 Agent 内容上界。
普通本人 Watch self／peer read 保持原只读合同，`.others` 不授予它们读取他人，公开 level 或 Agent provenance 也不补造审计票。

## 6. 读取、验证与完整性边界

消费 Station 与独立审计者对每条获准 stream 独立验证以下六项。普通客户端的原件、
账号/cut/连续性检查及独立 producer/MLS 验证按 `server-trusted-results.md` §2.1；不能把 Station
治理历史职责强加给普通客户端，也不能免除 Station 的任何一项验证：

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
2. 申请人的 Account Station 取得并验证 genesis Event/Commit、完整连续 handoff chain 和当前方 nonce-bound assertion；
   普通客户端只经自己的已认证 Station 发起准备并消费既有结果，不选择外站或执行方法历史；
3. join Event 经自己的 Account Station 转发到已验证的当前治理 Station；
4. 只有 membership Commit 成功后才获得可见性；
5. 申请人的 Station 从当前治理 Station 拉取签名 Snapshot 和获准 stream 的 tail。

不得默认从邀请人 Station、初始治理 Station 或 genesis 开始拉取全部 Event。历史范围必须同时受 `history_access`、join position、Circle membership、retention 和 MLS epoch 可读性限制。

## 8. 治理 Station 更换

先按 §8.1 的 accepted 来源资格门排除 Human PCR 与未验证来源，再支持旧治理方在线的计划 handoff。controller 先提交 `ak.realm.governance_station.change` 到 Realm stream；旧方随后冻结所有 stream，生成包含每条 final head 的 Snapshot，并签署 `RealmAuthorityHandoff`。新方必须完成验证和导入后签署 acceptance。

handoff 的旧方 `ak.realm_authority_handoff_old_signature.v1` 与新方
`ak.realm_authority_handoff_new_acceptance_signature.v1` 共享同一个 unsigned projection：从完整 handoff 同时删除
`old_authority_signature` 和 `new_authority_acceptance_signature`，除此之外保留全部实际存在成员。两份
`signed_digest` 必须相同；旧方 key 必须属于 `from_generation/from_service_id` 在冻结 cut 上仍为 current 的治理
Station，新方 key 必须属于 `to_generation/to_service_id`，且只能在完整验证并导入 frozen handoff 后签 acceptance。
两者分别用自己的 context prefix 与完整五成员 signature envelope 按本章 §3 的相同 RFC 8785 JCS、SHA-256、Ed25519
构造签名；验证方独立重算投影、digest、prefix 和签名输入，且不得互换 old/new context 或 key。

Handoff 必须绑定：连续 generation、旧/新 service identity、change Event、Realm-stream final change Commit、全部 `final_stream_heads` 的 canonical digest、Snapshot ID/digest，以及旧方和新方签名。

Watch 交接 MUST 保留全部已写 selector 的 durable current，包括带 revision 的 `value:null`，并完整验证其 accepted 来源与同 cut reducer 物化；新治理站只有完成该证明后才可通过本人 exact read 肯定返回 `never_written`。成员 snapshot 缺项不证明从未写入；完整性与交付规则见 [Strand §8.3.1](../models/strand-and-message.md#831-跨站本人精确-watch-读取normative)。

新 generation 在每条已有 stream 上的第一个 Commit 必须以前一 generation 导入的该 stream final head 为 predecessor。旧方在 handoff 生效后永久拒绝新写；新方在未完整导入前不得启动。

### 8.1 PCR 治理归属与交接资格（normative）

**Human PCR 固定于账号 Station。** 对已完整验证并接纳的 Human 注册创世，genesis `governance_station_id` MUST 等于创世 actor 的完整 `AccountId.station_id`，之后始终由该逻辑 Station 身份治理。Human 来源由已验证的 `purpose=principal_control`、`registration_anchor` 接纳、完整 ordered genesis unit 与 accepted receipt 共同证明；仅字段缺席、purpose、profile、DID 拼写、调用方角色标签或 current 投影均不能证明来源。该来源与完整 Account／inception PCR 永久绑定，后续委托、恢复、身份 resolution 更新或路由变化均不能将其改判为 Organization。

Human PCR MUST NOT 接纳 `ak.realm.governance_station.change`；旧方冻结／导出交接、新方导入／签 acceptance／激活以及 authority bundle/current assertion 消费均须执行同一资格门。即使 controller、旧／新 Station 都签名、私态完整或新旧 Service 恰好同属企业，也 MUST 在改变任何 Event、Commit、head、generation、私态或通知前以 `failed_precondition` 零效果拒绝。未知或未验证来源保持 unresolved，不得回落到普通 Realm 或可迁移主体。不能先冻结 Human 再以“迁入尚未完成”长期停用它。

固定的是 Station DID core 身份，不是机器、进程、数据库、endpoint 或某一 signing key。同一 Station 的合法部署迁移、endpoint／key 更新仍按原身份与服务证据验证，不创建 handoff、不推进治理任期；账号认证、设备 current、pairing、session、recovery、KeyPackage 与 Consent 仍在 owning Station TCB 的同一权威边界内，可拆进程／库，但不能拆成第二个业务 writer。只比较 Account 字段仍不足以验证 Commit、当前设备或请求权限。Station 永久停止后的 Human Account／PCR 不跨站延续，见 [`account-lifecycle.md` §2](../identity/account-lifecycle.md#2-分层)。

**其它主体保留共享 planned handoff。** Organization 必须证明 accepted organization-governed `delegated_pcr_genesis` 与独立组织权威；Agent 必须证明 accepted `agent_control` 创世及原 controller provision；Applet-managed Bot/Ghost 必须证明 accepted `applet_managed_control` 创世及原 managed provision。它们按本章原有当前 controller、generation/head CAS、旧方在线、完整冻结导入和双签门执行，不因非 Human 标签自动获准。完整 AccountId 的 `station_id` 仍是 hosting 身份，合法交接后可以不同于 PCR governor；初始同站 provision／唯一性约束不改写为任意远程 genesis。交接不更换 inception PCR ID、AccountId、既有 Event／Commit 或 MLS group，不递增 authority-root 委派代次，也不改变原 Grant／Revoke 的效力。普通 Collaboration／Direct Conversation 的共享 handoff 不受 Human 限制。机器合同为既有 PCR profile 的 `pcr_governance_policy`；allowlist 并集不是每种主体的接纳许可。

Human 的 PCR genesis／Commit／current assertion MUST NOT 经 `ak.open.realm_authority.read.bundle.v1` 公开披露；该入口按既有反枚举合同返回不可区分的 `not_found`。其原生私有验证仍核 accepted genesis、原签名与当前授权，不新增公共发现或 PCR 历史面。

以下 PCR handoff／公开 authority bundle／hosting 代理规则只适用于上述已验证且满足交接门的非 Human PCR；不得用于 Human，亦不开放任意账号跨 Station 替换。

公开 `RealmAuthorityBundle` 对 PCR 只提供既有最小权威证书链：genesis Event／Commit、治理变更 Event／Commit、双签 handoff 与 nonce-bound current assertion。对应 kind 的该项外露必须在 PCR exposure registry 显式登记。它不授予 PCR membership、普通历史 scan、完整 Snapshot 或任何 Consent／设备／恢复内容读取权；私有 frozen stream head 清单与迁入材料仍只交给已验证的交接参与方。未经独立信任的候选地址只是 locator hint。

旧方冻结点必须同时阻止新的控制 Event 与相关 native 私有接受事务；只冻结 Commit 而让 quota、去重或 delivery CAS 继续前进，不构成完整 handoff。完整迁入必须保留所有当前与历史来源、精确重试结果、撤权 tombstone、高水位、未完成私有事务及其业务 fence，不能从成员可读 floor、缺项 Snapshot 或当前设备 key 重建。新方必须对本地导入状态与旧方冻结材料作完整性比较，并在同一激活事务中建立唯一接受位置；任一缺项或未知域都保持不可用，不能签 acceptance。

获准的非 Human PCR handoff MUST 携 `pcr_private_state_digest`；普通非 PCR handoff MUST 不携该成员。Human PCR 不存在合法 handoff。私有 handoff request 同时携闭合 `pcr_private_state` manifest：`realm_id,holder_account_id,governance_generation,effective_stream_head,nonce,state_digest`，顺序与 `authority-commit-operations.schema.json` 一致。realm／完整 holder 必须匹配 inception PCR，generation/head 必须等于旧任期冻结截点；nonce 至少128 bit CSPRNG，仅旧／新治理方持有。`state_digest` 是完整冻结 native 私有状态导出 canonical bytes 的 SHA256；公开 `pcr_private_state_digest = SHA256(RFC8785_JCS(pcr_private_state))`。双签沿原 unsigned projection 覆盖该实际成员，context 不变。公开 authority bundle 只携带该加盐承诺，不携 manifest、nonce、私有导出或主体集合。

私有导出与传输仍是既有操作式迁入，不新增公开下载面或普通 peer scan 权。双方必须验证其格式、完整持有者范围及所有 native 域，比较实际耐久导入／重新导出的 canonical 状态与原 state_digest，并同时验证全部 canonical Event／Commit／current／历史签署事实。单独持有相同 manifest、字节文件、Snapshot 或声称导入完成的 flag 均不足以激活。格式或域不受支持时必须在旧方冻结前报告不可迁移；新方发现任何缺项、未知格式、冲突或摘要不等则零激活。导出不得含旧 Station 的全站 signing key；quota 等 holder-private keyed state 必须独立耐久、完整迁移，不能因治理 key 轮换／handoff 换盐而重置同源额度或去重。

Consent current、撤销导致的 holder-private quarantine 更新，以及依赖 Consent 的最终 private delivery CAS 必须归属于同一个 PCR authority 原子接受边界。hosting Station 代理时不得分拆此事务，不得用预检或短期允许回执在自己的独立数据库完成最终写入。其展示／同步副本不得成为第二个授权账本；受权读取、通知、代理命令与最终交付仍须使用正式登记的 exact carrier，并绑定完整 holder Account、当前治理任期及实际请求。未完成这些载体的实现必须在交接前拒绝启动该能力，不能以交接后的永久功能缺失冒称完成。

旧方永久丢失且没有完成 handoff 时，不允许自动选主、管理员自封或从备份恢复同一 Realm 的写权。可验证缓存保持只读；需要继续协作时创建显式 successor Realm，新的 Realm 不继承旧 position 或 MLS group。

## 9. MLS 边界

治理 Station 只跟踪 MLS 公开状态，不持有成员 secret。共享 Event 只保留 `ak.mls.genesis` 与 `ak.mls.commit`。Proposal 内联于 Commit；Welcome 是 recipient delivery；KeyPackage/claim 是专用 ledger；失败是本地诊断。

每个 MLS effective scope 属于其对应 Realm、Circle 或 Sidecar stream。`key_access_revision` 只由该 scope stream 上改变 current joined 成员集合的 membership Event 在同一事务加一；endpoint authorization 与 policy 变化不推进它，已撤销 endpoint 的发送由 send gate 同 cut 拒绝。encrypted application Event 的 epoch、group state ref 和 key-access revision 必须都等于 current，否则拒绝。

Add 使用 `MlsCommitSubmission` 原子提交 Commit Event 和全部 producer-signed Welcome deliveries。治理 Station 在同一事务中提交 Commit、更新 public state、写本站 recipient queues 和 outbox；跨站 recipient 的 Welcome 写入指向其 routing service 的 outbox intent，随 Commit 的 committed-replication item 由成员站在同一 replica 事务按本地 claim ledger 复核入队；任一本站可判定的 Welcome 无效则零写入。Handoff 迁移 public tree、epoch、revision、claim 状态和 Welcome queues，但不迁移任何成员 private MLS state。

## Account Device signer fact commitment and transfer (Normative)

原RealmCommit在committed_at后signature前 MAY 有 producer_signer_fact_digest；schema仅为旧原件解码允许缺省，新普通 Human／accepted Applet-managed Bot/Ghost Device 与 Applet Service 业务接纳 MUST 携带，其它 producer/PCR native 分支禁止。摘要为 SHA256(RFC8785_JCS(historical_producer_signer_fact))；该联合仅包含 Account Device fact 与 Service fact；原 Human Device 的字段、编码和摘要不变，受管 Device 按自身 accepted provenance 冻结同一 Account Device 形状。fact不含业务targetCommitId/position；Event内容ID先固定，fact准备后入Commit，最终所有字段设完才按现 content-ID规则排commit_id/signature重算ID，再按现RealmCommit signature投影仅排signature签完整对象（包含commit_id与factdigest）。MUST NOT 改字段后保留旧ID/签名，也不得把fact targetCommitId塞回摘要造成环。原proof context与版本不变。

原immutable fact MUST 与原accepted Commit同寿命持久保留；v1不删除accepted Commit。retention/redaction/withheld只改变合法披露，不补造或替换原事实，也不允许带隐藏row metadata。

计划handoff MUST 同冻结cut迁移全部原digest-bearing Commit/fact及原既有合法private audit。现RealmAuthorityHandoff在final_stream_heads_digest后携historical_signer_facts_digest，现handoff_request在原四字段后携historical_signer_facts；newhandoff即使无facts亦携空数组及其digest。inventory是完整 {target,producer_signer_fact}，按stream_ref JCS UTF8、numeric stream_position、event_id UTF8、commit_id UTF8排序；digest为SHA256(JCS数组)。target只能由原已accepted Commit配出，逐项核Commitfactdigest。new governor MUST 在冻结 cut 下将已导入原件中全部 digest-bearing Full Commit 的 exact target 集合与 inventory entry target 集合作相等比较：没有重复、缺项或额外项，逐项签名不能代替全集核验。交接治理授权负责迁移所有 stream 的冻结原件（含依法迁移的隐藏 stream/private audit），MUST NOT 以普通成员 readable floor 裁剪此全集；普通 peer Full 披露仍受原成员可见性与 floor 门约束，不能借交接权限扩大普通查询。原非流请求预算不扩，超过既有预算返回 limit_exceeded，禁止 partial 导入后启动。禁止从snapshot current补历史，漏项/冲突/digest错零导入，完成原chain/原件/facts原子导入前不得签new acceptance或启动authority。

old/new handoff unsigned projection仍仅删两signature，保留handoff_id及所有实际字段，新增inventorydigest由两个原context覆盖。旧无digesthandoff只可exact 旧已签原件解码，不能迁移或宣称已闭合新digest-bearing历史。旧没有完整source/digest的Commit保持旧原字节与Unavailable，不重签后冒原记录。正式切换须将全部原件签名/ID消费者同批同步，未支持新成员的消费者failclosed。

本条款复用检验向量 `ak.vector.signer_key.historical_commit_coordinate.v1`；签名字节夹具仅证明密码学转录，不替代原接纳事务与实际交接验证。

普通成员获准读取 exact Applet Service Event 后，self signer query 的 `historical_event` / `service` selector MUST 只披露该原件在接纳时冻结的 ServiceHistoricalSigningKey 和原 Commit committed_at。该 key 按 public_key_b64u、applet_id、registration_epoch、registration_ref、authorization_ref、effective_scope 顺序闭合；后两引用分别为原 accepted registration 与原 installation capability grant 创建事件的完整 committed coordinate，effective_scope 为该 Event 的已核安装 scope。历史 target 必须由该可读原 Event/Commit 构造；查询不可借这些引用读取隐藏原件。current Service selector 禁止。缺材料、错 target、错 scope、非 Service actor、未获准读取均只返回 unavailable，不得用 current DID key 或 runtime completion 补出历史答案。

治理 Station MUST 在接受事务同一 authority/registration/installation/grant 锁定截点重核原 Service DID epoch、原 producer Ed25519 proof、method、grant 约束及 scope，并逐字比较签 Commit 前准备的最小 fact。Service fact 依次含 event_id、actor（actual_signer 的完整 Service actor）、verification_method、key、accepted_at；accepted_at 是原目标 Commit 的 committed_at，fact 内不得含目标 Commit 坐标，以免摘要循环。原 Commit 摘要、fact 与 canonical Event 同事务冻结。peer replication、peer scan 与 planned handoff 的原 producer_signer_fact/inventory 使用 Account Device/Service 闭合联合，逐项核原治理签名、原 fact digest 与原 producer proof，复制原字节，不重新按当前 key/安装状态授权。普通 Applet 创建、问责记录仍保原读取权限；最小公钥投影不包含 private runtime fixed set、私钥、控制 Realm 历史或私有 Profile 内容。

## 10. Applet 管理私态的既有交接

所有新建且合法的Realm handoff MUST 携 management_private_state_digest，私有handoff request MUST 携
management_private_state（含realm_id、governance_generation、final_stream_heads_digest、nonce、state_digest）。
状态为空仍携同类加盐承诺，不能按Applet安装／review存在与否决定外露。两份现handoff签名覆盖新承诺，nonce至少128bit CSPRNG。
state_digest绑定完整冻结配置／review ledger、原intent／候选、来源／批准依据、终态／消费／quota／nonce与exact恢复结果
的canonical私有导出；双方以实际完整导入／重新导出比较，缺项／未知保持不可激活，不只比较manifest。
公开authority bundle只携加盐承诺，无manifest、私态或下载面。该增补不是PCR资格例外，不允许Human PCR handoff。
旧任期活动批准superseded、terminal／consumed结果唯一恢复，详见[Applet来源§6](../extensions/applet-management-source.md#6-审批幂等与恢复)。
