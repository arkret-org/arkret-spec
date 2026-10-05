---
title: Conformance Vectors
status: candidate
normative: true
stability: v1
updated: 2026-10-05
see_also:
  - normative-language.md
  - ../sync/authority-commit-log.md
---

# 一致性向量

规范关键字按[规范语言](./normative-language.md)解释。

## 1. 当前基线

Authority-commit 基线由 `ak.vector.authority_commit.independent_streams.v1` 覆盖，机器样例位于
`artifacts/fixtures/authority-commit-fixture.json`，并由 `tools/test_authority_commit_protocol.py` 执行。

该向量必须证明：

1. Realm、每个 Circle、每个 Sidecar 各自从 position 0 开始，分别维护连续
   `previous_commit_ref`；不得存在跨 stream position 或 predecessor。
2. Event 不携带 `previous_commit_ref`，最终 predecessor 只属于治理 Station 签署的 `RealmCommit`。
3. 私有 handoff manifest 覆盖所有 stream heads；公开 authority bundle 只公开 Realm stream head。
4. join locator 只是提示；snapshot 与获准 stream tails 来自验证后的当前治理 Station。
5. MLS Add Commit 与全部 Welcome deliveries 在同一 authority transaction 全成或全败。

`ak.vector.mls.welcome_recipient_delivery_queue.v1` MUST 证明：同事务入队的
`MlsWelcomeDelivery` 在 account delta 与同队列补拉中保持原始签名对象，和
`DeviceMessageEnvelope` 以闭合 `delivery_kind` 分支交错排序；两者共用位置、只读 cursor 与累计 ACK。
Welcome 使用 `(recipient_actor_id, recipient_endpoint, welcome_id)` 耐久去重，human device 与 Agent runtime
分别使用自己的认证 endpoint。相同 ID 不同 bytes、跨 endpoint／旧 Agent authorization 的 token、
未持久化就 ACK、遗漏截断页或静默丢弃 Welcome 均必须 fail closed；不能恢复独立 Welcome-ref GET。
同一向量还 MUST 覆盖未 ACK delivery 超过内容 `expires_at` 仍可补拉、容量满拒绝新
DeviceMessage 或 MLS Commit+Welcome 并保持原队列与请求幂等 ledger 零变更，以及 ACK 后
跨两分支累计取消；`lost` 只能由持久证据证明历史缺口或故障。

`ak.vector.mls.cross_station_welcome_replication.v1` MUST 证明：跨站 recipient 的 Welcome 由治理 Station 在 Commit
接纳事务内写入指向其 routing service 的 outbox intent，随该 `ak.mls.commit` 的 committed-replication item 以
已认证治理请求签名覆盖的 immutable `genesis_event_ref` 和 `welcomes[]` 送达；后期 epoch 的 base ref 不得代替 Genesis，
缺失／错配／重放改变 ref 或非 Commit 带 ref 均失败关闭、零写。成员站以本地 claim ledger 复核并与 Commit replica 同一事务入队，复核失败的 Welcome 不入队也不阻止
Commit replica，经 scan 已保存 Commit 后的重放补写 Welcome 并返回 `duplicate`，复制 Welcome 计入但不因容量被拒绝。
`ak.vector.keypackage.recipient_claim_read.v1` MUST 证明：`ak.self.keys.keypackages.read.claim.v1` 只向 claim record
的 exact endpoint 返回逐字节相同的原 claim outcome，其它情形统一 `keypackage_unknown`，接收端读取并验证 receipt 后才
解密。`ak.vector.federation.authority_forward_genesis_material.v1` MUST 证明：跨站 Genesis 经 `authority_forward` 携
`mls_genesis_material` 被接纳并保存为 public Blob，缺失／多余、成员超过 5592406 字符为 `schema_violation`，摘要不符为
`digest_mismatch`，均零写入；两个成员各自的上限已蕴含 8388608 bytes 的响应上限，不另设合计拒绝。三者分别由
`mls-cross-station-welcome-replication-fixture.json`、`keypackage-recipient-claim-read-fixture.json` 与
`federation-authority-forward-genesis-material-fixture.json` 的可执行用例承载。

## 2. 领域向量

Typed reducer、身份、能力、媒体与扩展领域的向量必须使用本规范定义的 Event/RealmCommit 边界，并由 vector registry 登记。

### 2.5.7 领域加密向量

领域加密向量必须使用 current MLS group state、key-access revision 与对应 stream 的 committed Event reference。

### 2.5.8 审计与媒体向量

审计对象和媒体引用仍必须验证 producer proof、typed ID 与内容摘要；接纳性另由 RealmCommit 表达。

### 5.9 Read receipt

Read receipt 的隐私与合并向量改为 typed reducer 输入，不使用 OR-set dot。

### 5.10 Account data

Account-private 数据不进入 RealmCommit；当它引用 Realm 事实时必须绑定 exact committed ref。

### 5.11 View 与 client preference

View/preference 向量必须明确区分 Account-private 状态和 authority-committed Realm 状态。

### 5.12 Client sync

同步向量按每条获准 Realm/Circle/Sidecar stream 分别检查连续 position 和 predecessor。

### 5.13 Preference conflict

Account-private preference 冲突由其自身 CAS 合同处理，不得借用 Realm stream 的位置。

### 5.14 Bootstrap

Bootstrap 向量验证 nonce-bound current authority bundle、typed snapshot 和获准 stream tails，不从邀请人 Station 或 genesis Station 拉取全历史。

Snapshot/current row 向量 MUST 包括同 Realm 两条可见 stream 具有相同数字 position 的情形：每个 closed typed
result 都携必填 `source_stream_ref`，逐字等于 `revision.commit_id` 所指 covering Commit 的 stream；按该 stream
核对 head、floor 与可读 Commit 的 exact ID/position。缺 `source_stream_ref`、指向隐藏/外 Realm stream、
指向另一条同 position stream、revision 超过其 head、同一完整 selector 重复、floor 集合不匹配，均 MUST
整份拒绝且零新增 row/tail/cursor。合法 floor 前 row 由 exact 签名 snapshot 承诺，floor 后可读 row
须与 covering Commit 逐字匹配；`CurrentRevision` 与 `expected_revision` 仍是二元 CAS。

### 5.15 PCR device_status 同 cut 终局

`ak.vector.security_transaction.resilience.v1` 的 SecurityRotation revoke 分支与 `device-lifecycle.md` §5.5.3 的设备折叠 MUST 联合验证：proposal Event/Commit 与 `revoke_proposal` 同事务写入，终局前为 pending；`accepted` 与 revoke accepted step 原子可见，`rejected` 与 aborted/expired 原子可见，已接纳 proposal 的终止不留下永久 pending；Event/Commit 已 accepted 但 command result rejected 时只清该 dot 的 pending，另一 transaction 的 pending/accepted dot 不变。不同结果、不同覆盖 Commit、缺 Event/Commit、结果先于 proposal、读取未覆盖同一 PCR head 或事务结果不可读都 fail closed；rollback 零 Event/Commit/proposal/terminal，精确重放不增写。

`security-transaction-resilience-fixture.json` 固定 closed proposal/result 的形状正反例；行为仍须由 runner 验证，shape fixture 不代替签名与事务验证。v1 不存在 PCR fork 证据摄入或 `conflicted` 折叠（`device-lifecycle.md` §5.5.3）。

### 10.12.1 Push envelope

Push 只提供不可信通知提示；客户端仍从自己的 Account Station 验证 Commit/current。

### 10.12.3 Push 重放

重复通知不得产生第二个 Commit；幂等键是 Event ID 和已验证 commit ID。

### 11.10.3 Private object 存在性

未授权请求对隐藏 scope 的 absent/forbidden 使用不可枚举的统一结果。

### 11.10.4 Private object revision

获权读取返回 typed revision 和所属 stream position，不返回其它隐藏 stream 的 head。

### 22.5 DID handoff

DID route 只是 authority locator 信号；权威身份仍由 genesis 和 old→new 双签 handoff chain 证明。

### 22.6 DID freshness

解析结果必须满足调用点登记的 freshness，但不得把更新 route 当作已完成的 authority handoff。

## 3. 向量定义

本节逐条定义 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 登记的一致性向量。
每条给出该向量 MUST 证明的判定点；适用面、profile、状态与正文依据以 registry 行为准。`status=active` 的向量
MUST 由 `spec/v1/artifacts/fixtures/` 下的 fixture 以 `vector_id`／`negative_cases_vector_id`／`name`／`covers_vectors`
可追溯地承载，`tools/check_vector_registry_traceability.py` 与 Cotest strict vector registry gate 执行同一判定；
尚无 fixture 的现行义务登记为 `reserved`，registry 行写明原因与激活条件，其判定点仍按本节定义，但在激活前
不构成认证证据，任何实现不得声称已通过。
`normative-clause-registry.json` 的 `coverage_scope.executable_fixture_categories` 列出的条款类别中，
每个向量 MUST 有一份 fixture 用 `security_evidence` 把本节的判定点逐条映射到该 fixture 内可解析的 case；
尚未闭合的 (条款, 向量) 对必须逐条登记在同一 registry 的 `executable_evidence_exemptions` 里，该清单只减不增。
fixture 存在、suite id 已登记或向量 active 都不等于参考实现已执行：认证器 MUST 拒绝未映射的 suite，
也 MUST 拒绝缺少逐 case 实际断言结果的运行。全部判定按本规范
当前的 Event / RealmCommit 边界解释：Event 只承载 producer 意图，接纳由当前治理 Station 的 `RealmCommit` 表达，
一条 `RealmCommit` 恰好接纳一条 Event，Realm、每个 Circle 与每个 Sidecar 各有独立 commit stream。

### 3.1 Account 与偏好

`ak.vector.account.blocklist_projection.v1` MUST 证明：个人 blocklist 是 holder-private account-data 值，只经 `ak.account_data.set` 以 `expected_server_revision` 整值 CAS 更新；
target 闭包完整；共享历史先接收后按 holder 侧投影过滤；新的 holder-private 请求由服务端按既有权限转发、仅在持钥客户端过滤；解除屏蔽后投影可从既有材料重建；服务端提交响应不随 block 命中变化。持钥客户端的自动回执可能因过滤而不同，向发送方明确暴露这一隐私限制。

`ak.vector.actor_private_events.submit.v1` MUST 证明：`ak.device.push_route`、`ak.agent.action_request`、
`ak.agent.action_reject`、`ak.agent.draft.propose` 只经 `ak.self.actor_private_events.command.submit.v1` 接纳，不产生 RealmCommit；
exact retry 返回首次 outcome；同 event_id 异 bytes 为 `duplicate_conflict`、push route revision 失配为 `cas_conflict`、
owner 不属本 Station 为 `param_invalid`，均零写入；`ak.self.events.command.submit.v1` 对任一 actor-private kind 返回
`unsupported_event_kind`。

### 3.2 Agent signer evidence

`ak.vector.agent.signer_evidence_binding.v1` MUST 证明：可复用的 current Agent 状态、同 Station 与独立 receiver
两条历史 admission 路径、独立 lifecycle gate、canonical witness、恢复后仍使用原 genesis producer proof、
Station 已接纳的 controller 设备绑定、MLS 交叉绑定，以及每一处篡改都 fail closed。设备签名 key 只能由原授权
evidence 解析，`RealmCommit` 签名按对应 generation 的治理 Station historical service key 验证，两者不得互换。

`ak.vector.agent.historical_evidence_materialization.v1` MUST 证明：历史 Agent 物化冻结原始状态与带标签的接纳结果——
原 producer proof 加授权 evidence，或一份独立的 receiver receipt。相同 selector 与相同接纳结果重放返回同一 root；
冲突的接纳结果或 root 不得覆盖既有物化。完整历史 method evidence 按原 proof 时刻求值，与验证方当前时刻的过期状态无关。

### 3.3 授权与 capability

`ak.vector.auth.sensitive_field_handling.v1` MUST 证明：`field_access.sensitive_fields` 的读投影处理中，
`redact` / `hash` / `omit` 都移除原值；`hash` 使用带密钥或加盐的摘要纪律；无法执行的处理方式回退为 `omit`。

`ak.vector.capability.authority_chain.v1` MUST 证明：多层授权链由单一 grant 形态构成，每个 grant 在
`issuer_authority_refs` 中记录自己据以签发的上游 grant；撤销祖先在读取时使其后代失效，且不产生任何级联写入。
派生有效性必须可验证且带时间边界。

`ak.vector.capability.authority_audit.v1` MUST 证明：capability 物化保留 exact issuer 与具体 subject ActorId，
派生最大深度与 canonical 排序去重后的 root identity 集合，并要求每个父级 subject ActorId 与子级 issuer ActorId
完整相等。producer 自带的派生成员与同 DID 跨 Station 重放 MUST 拒绝；缺父级保持 dependency-pending；
相互独立的 reducer 必须产生相同的投影输入。

`ak.vector.capability.approval_constraint.v1` MUST 证明：即使持有高权限 grant，approval constraint 未满足时
也不得直接通过写入执行。审批证据是 `ak.schema.approval_signature.v1`（[`../authz/constraint-schema.md` §9.2](../authz/constraint-schema.md)），
随 `EventAdmissionSubmission.approval_signatures[]` 与目标 Event 一同提交，**不是**第二条 Event，也不改变目标 `event_id`。
向量 MUST 覆盖：`signing_bytes` 逐字节重算、`approval_context` 两支（grant 与 realm_governance）、
`approval_target` 两支（Event 与 operation）、换 body／`event_id`／Realm／action／operation／发起 Account／
context／nonce 的拒绝、`approved_at` 时间边界、同一 approver 重复计票只算一票，以及 nonce 只在成功接纳时消费
（未达 quorum 与验证失败 MUST NOT 提前消费，exact 重放返回原 outcome，换目标返回 `approval_nonce_reused`）。
形状错误 MUST 报 `schema_violation`，密码学错误 MUST 报 `signature_invalid`，两者不得互相冒充。

`ak.vector.authz.approval_signature_bytes.v1`、`ak.vector.authz.approval_signature_governance_context.v1`
与 `ak.vector.authz.approval_signature_operation_target.v1` 是上一条要求的**字节级**落地：三条接纳向量分别
覆盖 `grant`+`event`、`realm_governance`+`event` 与 `grant`+`operation`，每条都携带 `signing_bytes` 的十六进制、
detached payload 与真实 Ed25519 签名，验证者 MUST 能独立重算并验签。`operation` 接纳向量 MUST 使用
capability action registry 中真实可达的 carrier operation；v1 固定为 `ak.strand.create` 经
`ak.self.events.command.submit.v1` 的 `EventAdmissionSubmission.approval_signatures[]`，不得再用无 carrier 的
`non_event_surface` action 只证明字节可签。
`ak.vector.authz.approval_signature_negative.v1` 是与之配对的否例束，MUST 按三类分别给出稳定 code：
换字节或错构造（含丢域前缀、先摘要后签、把 producer proof 当 approval proof）→ `signature_invalid`；
形状错误 → `schema_violation`；签名有效但不可接纳 → `claim_required` 或 `failed_precondition`。

`ak.vector.capability.revoke_downstream_recheck.v1` MUST 证明：grant G 授权的 Event E 与由 G 派生的 child grant C
授权的 pending Event P，在 `ak.capability.revoke` 撤销 G 被接纳后，P MUST fail closed 或隔离并给出稳定
reason code；allow cache 与 policy decision cache 中依赖 G 或 C 的条目 MUST 在同一 reducer 事务内失效；
历史 E 保留审计事实，MUST NOT 被重算成另一个结论；后续 snapshot 与导出不得把 G 当作当前有效授权。已 revoked 的 `grant_id` 是终态：同 id 的 re-add 或 re-grant MUST NOT 使它复活，新授权只能是新的 `grant_id`。

`ak.vector.capability.applet_bridge_non_event_grant_authority.v1` MUST 证明：profile 声明的 non-event grant
authority 只允许 Realm admin 对 active bridge registration 签发的 exact `ak.applet.ghost.provision` grant；
owner 捷径与任何绑定漂移 MUST 拒绝。

`ak.vector.capability.direct_conversation_participant_authority.v1` MUST 证明：Direct Conversation 参与者权限是
profile 作用域内的非 grant 来源，跨 root generation 变更仍然成立，要求该 pair 唯一且不可变的绑定，
且不得据以签发子 grant。

### 3.4 Authority-commit 投影

`ak.vector.authority_commit_projection.ordinary_event_requires_commit_before_shared_effect.v1` MUST 证明：
非状态变更的共享 Event 与状态变更 Event 一样，只有在取得覆盖它的有效 `RealmCommit` 之后才成为共享事实。
在此之前，Account Station MUST NOT 报告 accepted、MUST NOT 更新共享 current、MUST NOT 向其它成员 fanout，
也 MUST NOT 让它成为任何后续 Event 的授权依据；此时唯一允许的是本地排队或草稿显示，且该本地显示 MUST 与
committed 结果可区分，不具备协议接纳效力。有效 `RealmCommit` 到达后，同一条 Event 正常进入 `committed` 并可被消费。
`authorization_ref` 能在已提交 typed 状态中解析只是接纳的必要条件之一，MUST NOT 被当作免除 Commit 的理由。

`ak.vector.authority_commit_projection.same_batch_does_not_advance_authorization_basis.v1` MUST 证明：
普通有序提交批次中较早 Event 的投影写入，不得成为同批次后续 Event 的授权依据；依赖方必须等待随后的 `RealmCommit`。
该义务约束的是**批内投影不得自行创造授权**，而不是禁止全部批内授权来源：
[`../models/realm-and-space.md` §2.5.1](../models/realm-and-space.md#251-bootstrap-步骤) 登记的 genesis batch
staged authority-root proof 是封闭例外，其 create Event MUST 是同批 slot 0、`controller_actor_id` MUST 等于 signed
envelope `actor_id`、follow-up MUST 在登记白名单内、整个 unit 原子成败。因此本向量 MUST 同时给出三组对照：
普通批次借前序未提交投影提权被拒、该前序 Event 取得 Commit 之后同一后续请求被接纳、
以及合法 staged founding unit 被接纳而槽位或 actor 漂移的 unit 被整体拒绝。
把合法 founding unit 一并拒掉的实现在此失败。每条 Event 仍各自对应一条 `RealmCommit`，
合法原子 unit 不需要等待下一次外部请求才能完成。

`ak.vector.authority_commit_projection.state_change_requires_expected_revision_and_commit.v1` MUST 证明：
状态变更 Event 在其自身 stream 上出现有效 `RealmCommit` 接纳之前不得进入 `committed`；判定依据是该 Commit 本身，
因为 v1 不提供可重算的共享状态根可供申诉。`expected_revision` 的适用范围是**该 kind 的领域 payload 定义了 CAS 时**
（见 [`../sync/authority-commit-log.md` §5](../sync/authority-commit-log.md#5-typed-reducer-与并发)），
不是所有状态变更都必须携带通用 CAS；Event 顶层携带 `expected_revision` 仍 MUST `schema_violation`。
所携带的 `revision` 是 `{commit_id, stream_position}` 二元组，比较是逐字段相等，MUST NOT 退化成裸 Commit ID 或计数器。
等待期间的可观测结果只能是本地的 `queued` / `forwarding` 或明确失败，协议不新增共享 pending 返回值。

`ak.vector.authority_commit_projection.causal_predecessor_unavailable_fails_closed.v1` MUST 证明：
`semantic_refs[role=causal]` 指向的前驱在本地不可解析或尚未取得有效 `RealmCommit` 时，依赖它的 Event MUST fail closed 或保持本地等待，
MUST NOT 被静默接受、补造前驱或按到达顺序自行判定成立；前驱取得 Commit 后同一 Event 才可被接纳。

`ak.vector.authority_commit_projection.revoked_authorization_fails_closed.v1` MUST 证明：
Event 提交与其 `RealmCommit` 之间授权被撤销时，该 Event MUST 以确定性失败被拒，MUST NOT 因为已经排队、
已经本地投影或使用同一 request key 重试而被放行；已 revoked 的授权 MUST NOT 在重试路径上复活。

`ak.vector.authority_commit_projection.invalid_proof_fails_closed.v1` MUST 证明：
producer proof 或 `RealmCommit` 签名无效、绑定错误 `governance_generation`、或 `previous_commit_ref` /
`stream_position` 链接不成立时，消费 Station / 独立审计 verifier MUST 拒绝该 Commit 并保持依赖它的状态未变更，
MUST NOT 降级为“签名可疑但内容看起来合理”的接受路径。

`ak.vector.authority_commit_projection.exact_retry_preserves_authorization_and_cas.v1` MUST 证明：
以 exact 相同 canonical bytes 重试等待中的 Event 时，`semantic_refs[role=authorized_by]` 与领域 `expected_revision`
MUST 逐字保留：重试 MUST NOT 剥除授权引用、MUST NOT 把陈旧 CAS 改写成当前值、也 MUST NOT 因为“已经试过一次”而跳过
当前授权重判。陈旧 CAS 的重试仍 MUST 以确定性失败被拒，不产生 Commit。

### 3.5 Consent 与 identity link

`ak.vector.consent.cache_invalidation.v1` MUST 证明：consent 处于 active 时被缓存的 private contact discovery
结果、invite capability gate 与 PSI 索引，在 subject 撤销 consent 后立即失效——directory lookup 不再返回该 peer，
下一次 invite 提交 MUST 前置条件失败并重判 capability gate，`any` 范围的撤销 MUST 失效全部 scope cache，
PSI 索引在下一轮轮转中排除该 peer。

v1 不登记通用 identity-link 当前查询或披露操作，因此原四层 directory／sync／invite／本地 profile 的当前 lookup 与统一失效向量不适用。客户端为验证已接受历史 MLS 消息而保存的 IdentityLink 仍按消息对应的历史 Event、Commit、MLS epoch 与 leaf 验签；成员离开、ban 或 policy 收紧不追溯清除该历史认证证据。任何已登记操作若在当前 cut 披露身份，仍须按该操作自己的 current authorization、membership 和 visibility gate 重验，不能把历史 IdentityLink 当作当前披露许可。

### 3.6 Contact 与 Direct Conversation

`ak.vector.contact.next_prepare_input.v1` MUST 证明：`ak.self.contact.read.list.v1` 投影携带封闭的
`next_prepare_input` 后继游标——accepted 行 MUST 携带它，五个不可作者化的 `contact_state` 值 MUST NOT 携带；
其 `contact_round_id`、`version` 与 `predecessor_event_ref` 逐字复制进 scope update 与 tombstone 两个 prepare 阶段；
`version` 是下一条 Event 的 version，`predecessor_event_ref` 是当前谱系头而不是该头的前驱；
过期游标以 `contact_lineage_conflict` 或 `contact_scope_stale` 拒绝，且 MUST 重新读取而不是猜测或原样重试。
founding edge 与方向无关：normal responder 的 accepted Event 是自己方向的 version 1；normal requester 与 glare 双方
以各自的 request Event ID 作 bootstrap predecessor，首个 successor 的 `version` MUST 为 2——因此 normal requester 在
对方接受后立刻收窄 scope 或 tombstone MUST 被接受，而不是当作 glare 专属形状拒绝；三个方向的 `complete_through`
与该 version 1 一致；首个 successor 的 issuer、contact round、head 或 version 任一不符 MUST 零写入拒绝。

`ak.vector.contact.pending_incoming_prepare.v1` MUST 证明：本 Station 已验证的 incoming request 投影包含
exact `request_event_ref` 与可选的原始 `request_message`；客户端只提交 peer 与 ref、核对准备好的意图并签名，
不解析请求 Event、也不验证外部 receipt 或历史；服务端加载 durable evidence，并对过期、持有者错误、peer 错误、
glare 与已消费 slot 一律零写入拒绝；Contact 镜像永不通过 Event resolve 暴露。

`ak.vector.direct_conversation.founding_unit.v1` MUST 证明：caller 自行作者化的 first-valid founding unit——
对四个有序 Event ID 的 `founding_unit_digest` 逐字节 KAT，`realm_id` 与 `main_strand_id` 分别由第一与第四个
Event ID 重类型得到，founder 成员身份显式表达，self 与 peer 载体分支形状封闭；拒绝服务端分配的标识符、
保留或物化中的草稿、协调者选举、重排、第五条 Event 以及任何被携带的坐标字段。

`ak.vector.direct_conversation.founding_authoring_material.v1` MUST 证明：`creation_required` 解析结果携带
`next_founding_input`，其成员名与 founding unit 提交完全一致，恰好一个 `founding_authority_evidence` 分支，
不含 Event 字节或坐标；材料无法装配时返回 `temporarily_unavailable`；提交侧必须重新验证，绝不信任回显副本。

`ak.vector.direct_conversation.founding_admission.v1` MUST 证明：每个
`(founder_id, trust_domain_id, pair_key)` slot 在同 Station、双 Station 与 founder 多设备并发下只接纳一个
founding unit——首个有效 unit 胜出，失败方得到 `direct_conversation_slot_already_committed` 且零写入；
逐字重放返回字节相同的 receipt 且不推进 `accepted_at`；同一幂等键配不同 unit 判 `duplicate_conflict`；
任一崩溃点都收敛到同一坐标；federation 分支把缺失的有界依赖报成顶层可重试 `dependency_missing` 而非部分成功。

`ak.vector.direct_conversation.founder_loss_terminality.v1` MUST 证明：失去 founder 的 Direct Conversation
绝不转移既有 pair slot——完全相同的 `(principal_id, station_id)` 通过普通恢复重新作为原 founder 续用；
超时、root Contact 恢复策略、第三方背书与事后双边指定一律零写入。非 founder 一方保持 `awaiting_founder`，
封闭 wire 联合体中不存在 `founder_unrecoverable` 状态；只有确实不同的稳定参与者对才派生新的 `pair_key`，
且不继承任何历史、MLS 状态、密钥、审计身份或权限。

`ak.vector.direct_conversation.send_blocker_authority.v1` MUST 证明：Direct Conversation 解析器只报告
服务端可验证的发送阻塞原因。`personal_blocked` 不在封闭 wire 枚举中——
holder blocklist 状态加密给 holder 设备——因此携带它的响应判 `schema_violation`；
它只由封闭的客户端本地阻塞集合承载，永不出现在任何 wire 面，也不把解析器状态变成 suspended。缺少现行 MLS 发送状态时客户端另行 fail closed，不恢复旧 history-key 专用 blocker。
`presence_offline` 与 `keypackage_empty` 仍可由服务端验证，但只返回给既有的 exact pair 参与者；
非参与者探测得到与不存在的 pair 完全相同的不透明失败。

七个 `ak.vector.direct_conversation.admission.{binding_invalid,invite_forbidden,member_count_invalid,
participant_authority_denied,root_mask_violation,terminal_forbidden,third_party_member_forbidden}.v1` **MUST** 逐项执行
`direct-conversation-admission-fixture.json`：每项至少一条允许对照、每个已登记 mutation 的 exact reason 拒绝、
RealmCommit／Event／projection／outbox 全零写入；exact-two 项还必须区分 write rejection 与 resolver 的只读
`suspended` blocker；pair 外 invite 的双重命中必须稳定选择 `direct_conversation_third_party_member_forbidden`，destroy/tombstone 与 root
mask 的双重命中必须稳定选择 `direct_conversation_terminal_forbidden`。不得以 founding-unit aggregate 拒绝、一个泛化 failure 或诊断文本
匹配代替任一规则。

### 3.7 编码与 proof context

`ak.vector.event_id.content_bound.v1` MUST 证明：event digest 的 preimage 是移除 `event_id`、`producer_proof` 与
`unsigned` 后的 canonical Event Envelope；`event_id` 由该 digest 一次前向派生，因此 MUST NOT 出现在 preimage 中。
`event_id` 的 33 octets 为 suite code 拼接完整 digest 后做无 padding base64url；携带的 `event_id` 与重算不符、
suite code 不符或未登记、reserved nibble 非零、带 padding 或解码长度错误均 MUST 拒绝。按
[`encoding.md` §5](./encoding.md)，transport envelope、HTTP header、Station sync 面的 metadata 与本地接收时间
都不进入该 preimage。

`ak.vector.encoding.canonical_event_tie_break.v1` MUST 证明：[`encoding.md` §3.4](./encoding.md) 的
canonical 展示顺序——对一组互不排序的候选 Event，排序键是**解码后的 digest octets** 的 unsigned lexicographic
升序，octets 相同而 suite 不同时以 canonical suite id 的 UTF-8 unsigned bytewise 升序作第二键。向量 MUST
包含一条 wire string 顺序与 decoded octets 顺序**相反**的 case，证明直接比较 `<suite>:<hex>` 或 base64url
字符串会得到错误序列。全部候选 MUST 保留且没有 winner：该顺序 MUST NOT 决定授权、admission、finality、
`stream_position` 或 `previous_commit_ref`，也 MUST NOT 使任一候选被删除或遮蔽。digest preimage MUST 逐字
使用移除 `event_id`、`producer_proof` 与 `unsigned` 后的 canonical Event body；加入额外业务字段的实现 MUST 失败。
仅 `producer_proof` 或 `unsigned` 不同而 canonical preimage 逐字相同的两个输入 MUST NOT 被报成 collision；同 suite、
同 octets 而 canonical preimage 不同 MUST fail closed，MUST NOT 回退到 `event_id`、`created_at`、到达顺序或
实现私有 ID。向量同时明示 producer 击败一个已知随机 digest 的期望尝试数约为 2，因此该顺序是 producer-biased
的展示排列而不是公平选举。

`ak.vector.encoding.extension_slot_roundtrip.v1` MUST 证明：具体 schema 明示的 `x_*` 槽位中未识别的内容，
在 decode 与 encode、存储、联邦转发与 backfill 之后逐字节保留，
并继续进入 canonical bytes。该向量的输入 MUST 是**具体 canonical schema 明示允许扩展槽**的合法对象；
任意容器上的 `x_*` 正例 MUST NOT 被推广成“所有 schema 都允许扩展”。向量 MUST 固定扩展值与 canonical 输出
bytes／digest，并逐项证明往返后未知成员、嵌套值、数组顺序与字符串内容都没有被丢弃、补默认或归一化。

路径 MUST 逐条给出观测，不得以其中一条代表全部：decode／encode 往返、存储读回、联邦转发后的对端读取、
backfill 重放，以及 canonical bytes／digest／签名校验。字节比较沿用
[`encoding.md` §2](./encoding.md) 的既有 canonical 合同，MUST NOT 把 JSON 空白或对象成员的书写顺序
引入新的保留义务。改变扩展槽内容 MUST 改变适用的 canonical digest 与签名校验结果，
从而把观测点钉在“扩展内容确实进入了 canonical bytes”而不是“对象仍能解析”。

同一向量 MUST 保留 schema 未声明字段的负向对照：该字段仍 MUST 被拒绝，不得借某个具体 schema 的扩展槽规则
推广成任意对象都接受扩展。通用 `critical_extensions` carrier 在 current-v1 为 reserved，不属于本向量输入；其重新激活
必须与具体 schema、typed model、criticality 判定和 canonical-preservation 向量同批落地。

`ak.vector.encoding.result_selector_uri.v1` MUST 证明：canonical MIMI room URI 是 typed current result 的
subject 来源；哈希化 subject、URI fragment 截断与 caller 自行分配的备用 room 标识符一律拒绝。

`ak.event_proof.v1` 的 transcript KAT 由 `ak.vector.encoding.signature_binding_payload.v1` 系列与
`ak.vector.encoding.crypto.ed25519_detached_jws.v1` 承载：binding object 的 `event_digest` 取上述 preimage，
canonical binding bytes 与 detached JWS 逐字节固定；`context` 作为 binding object 成员进入签名输入
（[`encoding.md` §6.0.2](./encoding.md)），因此同一未签名 body 在另一 proof context 下重放不能通过验证。

`ak.vector.encoding.derived_relation_evidence.v1` MUST 证明：机器 fixture 中每一条派生结论都以它所命名的
输入被重算，而不是与输入并列书写。每条关系 MUST 声明封闭词表中的 relation、其全部输入引用与输出引用；引用只能是
同一 fixture 内的 case 或跨 fixture 文件的 JSON pointer。引用不可解析、解析为 `null`、输入键集与该 relation 的
定义不匹配、输出引用与某个输入引用指向同一位置（自证），以及把否例 case 的材料当作接纳证据使用，一律 MUST 失败，
MUST NOT 降级为跳过。已登记的关系 MUST 至少覆盖：canonical preimage 到 `event_id` 的前向派生、`retype`、
只改保留 nibble 的否例派生、原像成员回读、`project(did)` 的 core projection、canonical JSON 摘要、值相等，
以及带域前缀的 Ed25519 占有签名验签。关系声明本身是强制项：删除某条声明 MUST 使检查失败，
MUST NOT 使该义务静默归零。

### 3.8 Event kind 与对象寻址

`ak.vector.event_kind.realm_alias_single_carrier.v1` MUST 证明：Realm alias 意图恰由一个已登记 Event kind 承载；
命名空间激活另行保证跨 Realm 的名称唯一；解析同时要求这两项事实；过期的 `expected_revision` 拒绝；
RealmId 的可读形态不依赖签发者。

`ak.vector.view.terminal_state_patch.v1` MUST 证明：共享 View 的移除是把 `state` 置为 `tombstoned` 的
`ak.view.update` patch，因此该 patch MUST 被接受；`state_changed_at` 由 reducer 派生，actor 提供的值
MUST 被 `view.schema.json` 拒绝。

`ak.vector.realm_link.transition_matrix.v1` MUST 证明：Realm Link 迁移合同——全部已声明初态与迁移被接受；
`tombstoned` 是终态，只允许字节等价重放；未声明迁移以 `realm_link_invalid_transition` 拒绝；
同 revision 的竞争迁移被串行化，过期命令拒绝且不改变已确认状态；一般图环仍然有效；
自引用以 `realm_link_self_reference` 拒绝。

`ak.vector.relation.primary_domain_cas.v1` MUST 证明：每个直接写 Relation shape 只有一个
`primary_conflict_domain` current-result subject；create/update/tombstone 都携 signed domain 与领域
`expected_revision`，domain 不匹配、stale revision、错误 RelationId 与 active domain 上的重复 create 都零写入拒绝。
两个离线作者从同一 revision 竞争时至多一个取得 RealmCommit，反向提交顺序同样成立；exact replay 返回原 Commit。
tombstone 后携其 revision 可创建新 event-derived RelationId。`relation_kind/from_ref/to_ref` create-lock，改变身份必须
显式 tombstone + create，update 触及身份字段必须 `schema_violation`；派生 `contains` / `watches` 直接写入仍拒绝。

### 3.9 Federation 与 MIMI

`ak.vector.federation.idempotency_after_key_revoke.v1` MUST 证明：已接纳的 closed peer submit 请求在 origin service key 撤销后，以相同 body、签名和 `Idempotency-Key` 重放仍由当前 transport gate 返回 `signature_invalid` 且零新写入，不因历史缓存命中返回成功。key 仍有效但 Realm origin binding 已移除时返回 `capability_denied`；key-state 或授权 basis 变化必须重跑授权。只有当前认证和授权均通过且 basis 不变，才可逐项重放原结果而不重复写入。

`ak.vector.mimi.provider_directory_signature.v1` MUST 证明：provider directory 携带完整的必需安全核心与能力声明，
其 detached JWS 在 exact canonical unsigned 投影上验证通过；缺必需能力或能力数组为空、被篡改的 endpoint、
cipher suite、content profile 或 room policy 组件、proof controller 不等于 `service_id`、未知扩展试图改变路由、
过期的 `created_at`、以开发摘要冒充签名，以及 HTTP 签名有效但 directory JWS 无效（及其反向）一律 MUST 拒绝。

`ak.vector.mimi.identifier_query_source_signature.v1` MUST 证明：每个 identifiers PSI 查询携带 per-request
的 RFC 9421 provider-source 签名；缺失或无效签名在 PSI 求值之前失败；`Arkret-Operation` header 存在但未签入
MUST 在覆盖集检查处失败，签入后被替换 MUST 在签名验证处失败；端点指向某一个 MIMI room 时 `mimi-room-uri`
为必需项；provider directory 读取不继承该 profile。

`ak.vector.mimi.room_update_branched_effect.v1` MUST 证明：语义化的 update kind 判别式恰好选中一个分支——
`ak.mimi.room_binding` 要求一条匹配的、caller 自行作者化且原样接纳的 Event，其余每个 kind 都是 receipt-only
并禁止该 Event；全部准入前的分支错误共享同一个对外桶。

### 3.10 身份与恢复

`ak.vector.identity.device_reanchor.v1` MUST 证明：完整 recovery unit 冻结唯一的 canonical 毫秒级作者化检查点，
该检查点被两条 Event 的 `created_at` 与两份 producer proof 的 `created_at` 逐字节共享；不一致、非 canonical 时间、
缺少签名前下界，或检查点落在适用窗口之外，都在任何写入之前被拒绝。有效 unit 只能通过唯一合法 PCR
`RealmCommit` 序列中的已提交结果推进 device generation；pending 或 rejected 的竞争候选既不推进也不隔离
已确认的 generation。

`ak.vector.identity.recovery_key_role_separation.v1` MUST 证明：recovery policy 内联的角色分离——
`methods[]` 中 `recovery_unlock.keys[]` 的每个 recovery-proof signing entry 必须携带独立 `backup_hpke` entry；
`backup_hpke.key_agreement_ref` 在同一份已接纳 policy 内唯一；proof 验证只能使用 signing entry；
全部 `recovery_public_key` envelope 的已签名 `recovery_policy_ref`、`recipient_key_ref` 与 `hpke_suite`
只能解析到同一 signing entry 内有效的 `backup_hpke`。悬空或重复 ref、已撤销或过期 entry、签名与 HPKE 复用材料、
suite 不匹配、把 signing ref 当 recipient，以及只在 DID Document 声明而未进入 session 或 envelope 引用 policy 的情形，
一律 MUST 拒绝。

`ak.vector.identity.recovery_secret_handoff.v1` MUST 证明：没有预先存在的独立 guardian、witness 或组织权威时，
旧 secret 泄露后的同 DID 原地 handoff 必须拒绝并重铸 DID；存在独立权威时，只接受带 durable checkpoint 的
两-entry 分阶段 handoff，并在 re-anchor、新 recovery policy、全部旧 backup-HPKE active envelope 的新 series
重新封装与 active-series 指针推进全部完成之后，最后才撤销旧 policy key。runner MUST 覆盖任一阶段崩溃后的幂等续跑。

`ak.vector.identity.recovery_policy_publication.v1` MUST 证明：canonical 恢复策略提交形态、封闭的 method entry
有效性、PCR allowlist 与 reducer 准入、接纳依据的物化，以及 fail-closed 的重试语义。

`ak.vector.identity.pcr_outward_exposure_registry.v1` MUST 证明：每个 PCR 对外载体都有 exact 登记的
operation、direction、schema、pointer 与 policy 反向边；private kind 一条都没有；
共享 Realm 的 Actor Profile 解析把未知、未授权与 selector 错误三类失败合并为同一结果。

`ak.vector.identity.public_resolution_minimization.v1` MUST 证明：未认证的 principal 解析响应只包含
service 背书的 current 投影与 method 历史证据；任何 PCR id、Event、receipt 与历史字段都被禁止。

`ak.vector.identity.test_signing_material_rejected.v1` MUST 证明：`test-material-registry.json` 登记的公开
测试签名材料，在正式的身份验证、授权与信任准入路径上一律被拒绝——签名验证通过本身不构成准入，因为这些材料的私钥
随规范公布，密码学上分不出持有者是不是本人。指纹按算法定义的公钥字节计算，同一公钥换 kid、DID、JWK 成员顺序或
传输编码仍被识别。拒绝发生在验证结论被用于授权之前，不写入已验证绑定、解析缓存或已接纳的鉴权状态，也不降级为更弱的
证据类别、`limited_trust` 钉扎或可重试的 `unavailable`。未登记的材料仍按现有身份与信任规则正常验证；隔离的
conformance harness 可以执行这些材料，而正式验证 API MUST NOT 提供切换到测试信任路径的配置项、feature flag、
环境变量或运行时开关。

`ak.vector.identity.reserved_test_identifier_rejected.v1` MUST 证明：`test-material-registry.json` 的 DID、
key id 与 trust domain 三条保留标识规则各自独立判定，命中其一 MUST NOT 被视为蕴含其余——DID 规则按 method 与
SCID 段匹配，key id 规则只看 fragment（因此把 fixture 的 key id 重新挂到部署 DID 下仍被拒），trust domain 规则按
`ak:trust_domain` typed identifier 的值匹配而不做 DNS 后缀猜测。仅出现 `test`、`fixture`、`did:key`、`example`
字样不构成保留，尾部相同的部署域不被拒绝。负例 MUST 先满足其余全部身份与信任前提，不得拿一个本来就无效的标识
冒充保留标识拒收成功。

`ak.vector.identity.human_pcr_genesis_constructive.v1` MUST 证明：human Principal Control Realm 的 genesis
是可构造的而不是可断言的。向量携带合法 `ak.realm.create` 的完整 canonical preimage bytes，其中内联封闭的
`founding_device_descriptor` 与 `initial_resolution`；`event_digest` 由该 bytes 重算，拼接 suite code 得到 33 octets，
`retype` 得到逐字节对应的 `realm_id`；`project(initial_resolution.did)` MUST 等于 create 的 actor principal。
保留高 nibble 非零的否例 MUST 由该接纳形态**只改这一个 nibble**派生，并报 `realm_id_not_event_derived`。
同一 human DID 在第二个 Station 上的合法 genesis MUST 重算出不同的 `realm_id`，两条 case 之间只允许 account
Station 与 generation-0 governance Station 不同，从而把“一个 DID 在两个 Station 上是两个互不迁移的 PCR”
钉成重算结果而不是文字声明。founding `ak.device.authorize` MUST 携带同一 derived Realm，
并复用该 descriptor 冻结的 `founding_authorize_payload_digest`。account 维度唯一性是状态判定：event-derived 下
第二次 genesis 必然得到不同 `realm_id`，因此 MUST NOT 由标识相等触发拒绝；向量以独立 state case 给出显式前置状态、
零写入与判定依据（[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md)）。

`ak.vector.signer_key.historical_commit_coordinate.v1` MUST 证明：account subscribe 与 per-stream scan 的已验证
`stream_row{commit,event}` 及本次冻结 self 提交 Event 与 bound accepted outcome 原 Commit 配对是封闭坐标来源；
self 提交 MUST 核对请求、分支、aggregate slot、内容引用及完整账号/Station/会话绑定，不能推进 head/floor
或强制下载 PCR 历史。两个 historical selector 都携完整
`committed_event_ref` 并拒绝裸 `event_id`。selector target 与 key `authorization_ref` 分别验证且允许不相等；
resolved key 同时携 authorization stream 的 current `revision` 与 `governance_generation`。向量必须分别拒绝
EventId／commit_id／stream_ref／stream_position／Realm 错配、current projection 嵌套 Event 伪造来源、按数组下标
关联、redacted row、换账号迟到 response 和 current-query 降级；重启恢复、乱序 outcome、受限历史 scan 与
逐字回显 selector 的 unavailable 必须保持同一完整坐标。单条 Agent 回复由 account 或 per-stream
verified row 到达、没有后续 Account 帧且产品 fold 已有变化时，仍必须主动查询历史签名证据；证据到达
后重新验证同一消息，不依赖刷新。暂时查询失败须保持待验并能在授权的正常恢复/重试后收敛，换账号
迟到结果、缺失 envelope 或失败的 MLS leaf authorization 不能因此展示正文。
向量还 MUST 覆盖 Human 自己 PCR 的原 self-admission 与 accepted fullAccount binding、Agent PCR genesis
的原 accepted provision/完整 controllerAccount/原 delegation 同事务事实及独立历史授权。错 slot、外来 Commit、
sibling Account、foreign admission、非 Human actual producer、registration 早序缺授权、current row 补事实、
缺授权四坐标、推进 head/floor、PCR history 读取前置与 current-query fallback 都必须零写拒绝。

### 3.11 邀请

`ak.vector.invite.claim_reducer_state_machine.v1` MUST 证明：`ak.invite.claim` 的 Realm reducer 在同一 accepted authority cut
核对唯一 accepted create Event/Commit、纯状态 `invite_lifecycle` 与有效 Realm policy；`binding_proof` 与 `subject_proof`
的签名 transcript、create Event 的 `token_commitment` 匹配、`verification_id` allowlist 复查、accepted claim 的
`claim_nonce` 与 commitment 唯一性，均在接纳前检查。接纳时 exact claim Event/Commit、`pending -> claimed`、可重建
派生索引与 subject-bound membership proposal 原子成立；后续 accept 以该 claim Event 的 exact ref 和 subject 校验。
被拒 claim 零共享 projected write，过期终态只能由独立 accepted `ak.invite.revoke` 推进。

`ak.vector.invite.consumed_token_resubject_rejected.v1` MUST 证明：已被原子消费并签发了绑定某 subject 的
`binding_proof` 的第三方邀请 token，不能被再次签发给不同 subject——验证服务 MUST 拒绝第二次签发，
仅当请求绑定同一 `(invite_id, claim_nonce, subject_id, binding_proof_digest)` 时才允许在可恢复窗口内幂等重投递
同一份既有 `binding_proof`；reducer MUST 以 `duplicate_conflict` 拒绝改绑 subject 的 `ak.invite.claim`；
对外失败响应 MUST 与 `not_found` 不可区分，具体 reason code 只写入服务端审计日志。

`ak.vector.invite.failure_indistinguishable.v1` MUST 证明：第三方 claim 端点与 invite locator 解析端点各自的
全部失败类别共享同一个对外响应形状与有界的时延分布。

`ak.vector.invite.oob_code_entropy.v1` MUST 证明：低于生产最低熵的离线 OOB code claim MUST 被 reducer 或验证服务
拒绝；有效窗口或 claim 次数超过策略上限的 lookup 形态 MUST 失效，不得进入 pending invite 或已接纳成员资格。

`ak.vector.invite.provisioning_activation_binding.v1` MUST 证明：第三方邀请私有材料的生命周期——
provisioning 对 `request_id` 幂等并拒绝同 id 不同意图；激活只在新鲜且成员逐一匹配的 Station 接纳背书上绑定；
一条 provisioning 记录绝不重绑到第二个 invite；重启后完全相同的重试返回原绑定；带外投递在激活之前绝不开始。

### 3.12 Patch 与 reducer

`ak.vector.patch.atomic_application.v1` MUST 证明：字段 patch 相对已声明前态原子应用；部分应用的 patch
或未绑定前态 MUST 被拒绝，且目标对象不发生任何变化。

`ak.vector.patch.projection_prestate_binding.v1` MUST 证明：strand update 与 tracks update 钉在数据面的
`target_ref` 路由上，而 stage set 遵循自身已登记的执行合同；reducer 投影从唯一登记的基值重算，
与接收方本地投影无关，缺依赖时保持挂起，缺失或多个基值、以及非 canonical 的投影后态均以
`reducer_projection_failed` 拒绝。

`ak.vector.patch.redactable_content_slot_unset_ban.v1` MUST 证明：对照
[`redactable-field-registry.json`](../../artifacts/registry/redactable-field-registry.json)，
`$op="unset"` 作用于任一已登记内容载体槽位都以 `patch_unset_redactable_field` 拒绝；
同一槽位的明文与加密形态判定完全一致；`$op="set"` 写入空正文仍属普通作者化；
`metadata.title`、`metadata.summary` 与 `metadata.fields.*` 接受 unset，使可选字段不会变成只写一次。

`ak.vector.strand_tracks_update.atomic.v1` MUST 证明：单条 `ak.strand.tracks.update` 对 `tracks` 的原子 patch——
单条 Event 内把 primary 从一个 track 切到另一个时，reducer 投影中不得出现两个 `is_primary=true`
或零个 `is_primary=true` 的中间态；启停与 profile 更新在同一次 typed current 更新内完成，不得拆成多次独立写入；
合并后 `tracks` 至多一个 `is_primary=true`，违反时整条 Event 以 `schema_violation` 拒绝且 `tracks` 不变；
patch path 中的 TrackName 必须先与 active registry 集合比较，未登记名称 MUST `schema_violation`，
不得因匹配基础正则而创建。

### 3.13 内容与消息

`ak.vector.message.poll_reducer.v1` MUST 证明：只有已接纳的明文 Message ContentBlock 可成为 v1 正式 Poll 输入；加密消息带 `poll_response_heads[]` 零写入拒绝，解密后的 poll 形状不参与正式计票。完整 ActorId 与 Realm、Circle 分区保留全部 response；同一 authority stream 中最大 Commit position 选出唯一当前票。错指 poll、actor 或 scope 的明文 heads 零写入拒绝；到达排列、迟到 position、前缀缺口、作废以及可交换、可结合、幂等的副本并集，在当前票、选择项与计票上必须收敛。

`ak.vector.reaction.authority_order_join.v1` MUST 证明：同一 actor、target、key、scope 的 add/remove 按同一 authority stream 的 Commit position 取最后一条断言，同时到达的候选不产生因果推断；同位置不同 Event fail closed；
redaction 之后 reaction 默认视图不复活；跨 MLS epoch 的 reaction 仍绑定目标 Event 与 scope；
capability revoke 之后该 actor 的新 reaction fail closed，既有 reaction 保留为历史事实。

`ak.vector.read_cursor.multi_device_merge.v1` MUST 证明：多设备阅读游标合并以同一 `CommitStreamRef` 上的
`stream_position` 支配优先——占优的位置即使 HLC 更小也胜出；不同 stream 或同一 Event 的两个位置互不支配，才取 HLC
最大值；HLC 相等时由 `device_id` 打破平局；Station 不持有 position 已提交坐标时以 `temporarily_unavailable` 零写入拒绝。

### 3.14 SDK 与 to-device

`ak.vector.sdk.event_type_axes.v1` MUST 证明：官方 SDK 暴露正交且封闭的外层提交类型与 payload 保护类型，
非法组合在编译期失败，已验证的值通过与服务准入相同的 canonical schema 与 transcript 序列化。该向量的执行合同是
工具中立的 `named_suite`：fixture 登记可解析的程序片段或构造步骤、预期的成功或类型错误、以及各自对应的判定点，
由各语言实现的 adapter 对 exact SDK 发布物编译并执行。向量 MUST NOT 把某一语言编译器的私有错误号或诊断措辞
当作协议错误码，判定只看“该片段是否编译通过”。

四个判定点 MUST 分开观测：（a）producer `Event`、authority `RealmCommit` 与
`PlainPayload<T>` / `MlsEncryptedPayload<T>` / 具体 MLS 协议 payload 是彼此不可互换的封闭类型；
（b）非法的 outer × payload 组合在网络提交前编译失败；（c）未经验证的 wire 字节或草稿值不能直接交给只接受
verified 值的 submit API，且 verified submission 在公开类型／API 面上不可原地修改；
（d）合法组合成功构造，并以与服务准入相同的 canonical schema／transcript 序列化出固定输出。
（d）同时用于排除“任何片段都编译失败”的伪通过——只有 compile-fail 用例而没有成功对照的实现在此失败。

取值来源 MUST 是 canonical 合同本身：[`contract-registry.json`](../../artifacts/registry/contract-registry.json)、
由它生成的 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json)，以及 Event／RealmCommit
与相关 payload schema。fixture MUST NOT 手抄另一套事件分类或轴枚举。
`ak.vector.encoding.open_registry_unknown_roundtrip.v1` 证明的是开放注册集保留未知字符串，
MUST NOT 被当作本向量的替代证据。

`ak.vector.sync.to_device_message_idempotency.v1` MUST 证明：`DeviceMessageEnvelope` 要求发送方分配的
`device_message_id`；未被确认的字节相同重投只执行一次 durable handler 副作用；
同键但意图冲突的复用以 `duplicate_conflict`（reason `device_message_id_conflict`）失败；
不同 id 始终是不同的逻辑消息。

`ak.vector.sdk.envelope_precheck_rejects_before_consumption.v1` MUST 证明：Event Envelope 不满足完整
`ak.schema.event.v1` 校验（其中已按 `Event.kind` 选择并执行 payload class）时以 `schema_violation` 被拒，且在
reducer 状态、投影、查询结果、本地缓存与出向 effect port 中都观测不到任何效果；重试、重连与 backfill 路径都不会重新接纳它，
也不会把它规整、补默认值或修复成可接纳形态。观测点是被消费效果的缺席，而不是另一个独立 payload acceptance gate；payload catalog
仅可作为同一 canonical schema 合同的对账／authoring seam，不得形成第二套 acceptance semantics。

`ak.vector.sdk.envelope_forbidden_top_level_fields.v1` MUST 证明：`hlc`、`producer_revision`、`domain_refs`、
`requirements` 出现在 Event 顶层时逐个以 `schema_violation` 被拒，而不是被忽略或剥除；Event root required 的
`producer_proof`、`scope_ref` 与 `actor_id` 各自缺失时同样被拒，且不从默认值、传输层、会话或相邻 Event 合成替代值后
进入验证路径。`semantic_refs` 是 optional；只有具体 event-kind admission selector 能要求某一 role，本通用向量不得把
`semantic_refs[role=authorized_by]` 虚构成所有 Event 的 required member。

`ak.vector.sdk.unknown_critical_feature_fail_closed.v1` 与
`ak.vector.sdk.requirements_mismatch_fail_closed.v1` 在 current-v1 均为 **reserved**：Event/root schema、typed SDK model 与
operation catalog 没有通用 `critical_extensions` / `requirements` carrier，因此不存在可执行输入。实现不得用私有对象或
fixture-only matcher 声称通过。未来重新激活这两个向量时，必须在同一 contract release 登记一个具体 closed carrier、
criticality 判定、`unsupported_feature` producer、canonical bytes 与 preservation 规则、storage/forward/backfill consumer，
以及接受与拒绝向量。

### 3.15 媒体

`ak.vector.webrtc.media_plaintext_downgrade.v1` MUST 证明：Realm policy 未授权媒体服务解密、
SFU service DID 不在 `plaintext_visible_services`、以及未显示必需的明文告警却试图加入解密型会议，
三种情况 MUST 全部拒绝 join 与 media key 发布；前两种的稳定失败原因是已登记的
`media_plaintext_service_not_authorised`，第三种 MUST 以等价的稳定 reason code 拒绝 join。

### 3.16 Agent Sidecar

`ak.vector.sidecar.ensure_idempotent.v1` MUST 证明：同一 `(realm_id, controller_account_id)` 的并发 prepare 与
create 收敛到唯一 Sidecar；`sidecar_id` 等于胜出 create Event 的 `event_id` 按 sidecar id kind 重类型得到的
同一 token，调用方不得提交或覆盖它；exact draft 可接受，任一被变异的 draft MUST 冲突且零写入，
重放已接纳 draft 幂等返回同一 Sidecar；context attach 只投影 `(sidecar_id, source_context_ref)` 映射，
不创建 Circle、membership、Strand 或 Relation，同映射重放幂等，另一来源上下文产生另一映射但仍复用同一 Sidecar。

`ak.vector.sidecar.eligibility_states.v1` MUST 证明：owned Agent 中尚未发布 KeyPackage 的成员属于
`desired_agent_ids` 但不属于 effective access，ensure 返回 `access_readiness=key_material_pending`，
Sidecar 不存在明文分支；该 Agent 经 Sidecar MLS Welcome 加入后只获得加入后的未来 epoch 密钥，
完整 readiness 证据成立才进入 effective access；Agent 被停用或离开当前 Realm 后派生的 desired 集合自动移除它，
服务端立即停止寻址与投递并产生 durable MLS removal obligation，随后由合格 committer 提交真实 remove；
此后该 Agent 的 proof、写入与查询 MUST fail closed。

`ak.vector.sidecar.mls_bootstrap_binding.v1` MUST 证明：participant 集合精确等于 controller 加当前 Realm 作用域的
`desired_agent_ids`，排序去重后的 authority transcript digest 与 `participant_authority_digest` 一致；
Sidecar Genesis 提案、签名 Event 与 MLS GroupContext extension 的唯一 governance binding 都带相同
`participant_authority_digest` 和已排序去重的 `authority_stream_head`，且后续 Add／Remove／Update Commit
在各自 accepted authority cut 重算并签署这两个字段；缺少任一字段、旧 cut、摘要或 refs 变异、
非 Sidecar binding 私带这些字段均零写入拒绝，读取投影不能替代签名 binding；
只有一个 genesis 通过标准 Event 准入与 CAS 成为 canonical 胜者，服务端不得生成 MLS 私有状态、伪造
GroupInfo 或 ratchet-tree 摘要、也不得提供绕过 Event proof 的 bootstrap 端点；全部 binding 变异 MUST fail closed，
native Sidecar scope 缺少匹配的 `sidecar_binding`、以及普通 Realm 或 Circle 携带该字段，都必须拒绝；
creator 设备只从该 genesis Event 唯一 producer proof 的 `verification_method` fragment 投影，
变异该 proof MUST fail closed，payload 携带 creator 主体或设备标识 MUST 判 `schema_violation`；
崩溃恢复重放字节相同的 Event 并激活已接纳的临时快照，失败方的快照必须销毁并通过胜者 group 重新加入。

`ak.vector.sidecar.mls_effective_access.v1` MUST 证明：desired 成员资格、已投递 Welcome 或已认领 KeyPackage
单独都不是 effective 证据，任何不完整组合保持 pending；已接纳的 Add Commit、引用该 Commit 且绑定匹配的
已接纳 Welcome，与该设备已认证会话对同一 claim 的消费三者齐备后，该设备才生效，同 principal 的其它设备
不会自动获得密钥；Agent 被停用或离开当前 Realm 后服务端立即停止寻址与投递并移除 effective access，
只产生 durable removal obligation，不持有 MLS 私有状态的 Station 不得伪造 Commit，新发送保持 fail closed；
真实 Remove Commit 推进 epoch 后，旧 Welcome 与消费记录不能使已移除设备复活。

`ak.vector.sidecar.accepted_request_identity.v1` MUST 证明：runtime producer 与 controller consumer 只把交换身份
绑定到已接纳的 request Event id，并拒绝消息级、本地意图与未被接纳的身份。

`ak.vector.sidecar.canonical_sibling_digest.v1` MUST 证明：同序列的 request 与 control 兄弟项按 canonical
已接纳 Event envelope 摘要的字节序最大值选取，绝不使用 Event id、到达顺序或数据库顺序。

`ak.vector.sidecar.exchange_binding_closed_loop.v1` MUST 证明：显式响应闭环——runtime 的 addressed 与 self
资格、重启去重门、协调者完成策略、因果 request refs、controller 校验、非回显情形的 fail-closed 处理，
以及 controller 作者化的 durable 关闭控制。

`ak.vector.sidecar.exchange_binding_containment.v1` MUST 证明：交换绑定或控制 schema id、以及 `exchange_id`
出现在明文或共享作用域中一律判硬拒绝或无效；publish 输出、Account Data 与公开或共享面都不携带任何交换材料。

`ak.vector.sidecar.exchange_projection_recovery.v1` MUST 证明：从已接纳的私有历史重建 Event 折叠与本地缓存恢复；
因果折叠校验；不与 Account Data 合并；controller 控制的排序与兄弟项裁决；终态吸收；重新指派；
按响应集合的动作映射；以及投影 schema 的状态不变量。
实时消费与恢复另须按 sidecar §8.2 在生产 account-stream 路径验证同 cut 历史/current 与投影验证 basis 原子安装，
缺尾／较新 current 拒绝部分安装、上一完整 cut 保留、重连和重启自动恢复，不以刷新或后续请求触发恢复。

`ak.vector.sidecar.context_locator_recovery.v1` MUST 证明：仅 controller 可用的完整分页与结构化 Event 配对
即可恢复私有 Sidecar 上下文定位符，无需新增任何披露端点。

`ak.vector.sidecar.existence_privacy.v1` MUST 证明：以既非 controller、也不属于其 owned Agent 的调用方视角——
账号 Event 流与扫描对目标 Realm 返回零条引用 Sidecar native scope 的 Event；不存在可用于枚举 Sidecar 或
来源上下文映射的协议 Relation；Realm directory 对 `sidecar_id` 与 controller 映射零命中；
Sidecar 内 Event 不触发来源 Strand 参与者的通知；Sidecar 作用域的 Event 不出现在 Realm `RealmCommit`
的明文安全 metadata 中，只能作为不透明承诺。

`ak.vector.sidecar.explicit_publish.v1` MUST 证明：只有显式的 controller 确认才创建一条被 allowlist 允许的
普通共享 Event，且其中零私有标识符、零历史、零定位符。

`ak.vector.agent.selector_label_known_account.v1` 的 `agent-participation-fixture.json` MUST 同时验证可读短输入的显式候选选择：完整 AccountId 与可见 token 范围逐字节绑定，未选择字符串不派生目标，token 改字/删除/chip 移除后不以另一处同名文本复活，跨 Station 与改名不改绑；私有 holder 备注不进入共享正文或 metadata。其 composer routing cases 按 sidecar §8.1 覆盖普通 Realm、自有/混合/audience 目标、显式 shared、Circle、Direct 与已寄宿 Sidecar；混合私有目标阻止发送，不自动拆分或降级群发送。运行该本地合同向量不替代真实 MLS、private-failure、publish 与第二设备的 live 验收。

`ak.vector.sidecar.multi_agent_publish.v1` MUST 证明：Agent 执行 publish 时 `actor_id` 与 `executed_by`
MUST 是单一 Agent DID，不得出现 Agent 组式的复合归属；另一 Agent 的 grant 不覆盖该内容或缺少新鲜审批时
MUST fail closed；它凭自己的 grant 可独立发布，归属仍是其单一 DID。

`ak.vector.sidecar.hosted_projection.v1` MUST 证明：context attach 只建立来源上下文映射，额外的 track 或
message 字段按封闭 schema 拒绝且不创建 Strand 或 Relation；本地交换投影缓存删除并重建后不重复 request
或 Agent 执行，回显位于已见共享位置之后并按稳定键排序；主 Strand 的标题、面包屑与 Track 页签在固定合并展示中
保持可见，缺失的 Sidecar 私有视图显示可恢复空态而不回退到共享读写；合并视图按 Sidecar Event id 去重并持续显示
来源与私密可见边界标识；只有 request 与显式面向用户的响应可进入回显，内部协作 Event 与 Sidecar 内
native Event 不创建回显；第二设备得到相同排序、状态与去重结果，且无需在来源 Realm 重放私有 Event。
controller 读取自己的 request／response 不要求 publish／审批／模式切换，不生成普通 Event；其它普通成员
不接收、不显示这些私密消息。`ak.schema.agent_sidecar_view_state.v1` 不接受 `display_mode`，只保存现有
pin／局部折叠／HLC，固定合并展示不引入新的授权或存储键。

以下具名验收适用于提供 Sidecar 上下文交互的生产客户端，MUST 使用当前构建、真实服务与真实 MLS，
并保存逐边界证据；artifact/schema 或组件测试通过不替代本表。Sidecar reserved vector 的激活规则不变，
登记这些验收不表示已有实现通过，也不把没有 runner 的向量改为 active。

`ak.vector.sidecar.view_state_closed.v1` 由 `sidecar-view-state-schema-fixture.json` 的 JSON Schema runner
执行无模式 plaintext 正例及两个旧模式字段拒绝负例；它只证明 closed shape，不替代上述生产验收或
其它 Sidecar reserved vector 的 MLS／隐私／恢复证据。

| Case | 场景与必须观察的结果 |
| --- | --- |
| `sidecar_owner_merged_private_read` | 同一来源 Strand 由 controller 和另一普通成员各自打开。controller 不点击 publish／审批／模式按钮就看到已验证私密请求与回复；普通成员无该消息、私密计数、未读或通知；普通 Strand durable history 没有新增回显 Event。 |
| `sidecar_live_reply_same_cut` | 连续至少三次已绑定 `@me/slug` 请求；每次分别证明请求接纳、回复接纳、客户端验证及原讨论可见。回复均无需刷新、重开卡片或下一条请求；生产订阅与补拉路径安装的 history/current 同 cut，Event id 不重复。 |
| `sidecar_incomplete_cut_recovery` | 暂扣私密 tail 或 historical signer／MLS 依赖，交付较新 current。不能展示未验证新回复或推进 checkpoint；当前授权仍允许时上一完整 cut 可标明非最新并保持可读。恢复依赖后自动验证同 cut 并显示回复，不清除密钥或重发请求。 |
| `sidecar_restart_exactly_once` | 分别在回复接纳后、历史/current 事务耐久前和耐久后断线／终止客户端。重连／重启从安全 checkpoint 自动恢复，reply 一次可见、Agent 无重复执行；cursor 失效只重建对应基线。正常 Signal drain／续订不累积故障退避；Signal 不到达时仍自动续传 committed reply。 |
| `sidecar_responsive_bounded_history` | 在声明的设备、历史规模、单批预算和退避参数下，注入验证等待并连续输入、滚动、取消；页面持续可操作。工作量随受影响增量增长，不因无关 render 重放全部历史；相关读取授权／历史 signer 证据／MLS basis 变化仍重新验证。当前读取资格丧失时旧缓存不得替代权限；Agent 作者化撤销不追溯剥夺 controller 仍获准读取的历史。 |
| `sidecar_partial_failure_isolation` | 对可证明 Realm-scope 的 source Strand，Realm 存在其它无关 Circle／Sidecar 不得使 exact watch/current 判定不可用。单独使 source Strand watch/current 请求暂不可用，或私密缓存持久化失败；普通讨论仍可操作，Sidecar 不丢弃安全 checkpoint、不依赖刷新恢复、不进入阻塞重试；耐久失败不得虚报投影完成。 |
| `sidecar_bound_mention_draft_acceptance` | 主人行不在当前成员显示列表但 verified controller 与完整 Agent AccountId 已绑定时，标签仍为 `@me/slug`。pending／失败保留草稿和选择；发送途中修改草稿或切换账号/scope，迟到成功不清除新输入；重复点击不重复请求。 |

`ak.vector.sidecar.non_disclosure_surface_matrix.v1` MUST 证明：每一个共享列表、展开、动态、导出、URL、
日志与遥测面都不披露 Sidecar 定位符、身份、内容或折叠输入。

`ak.vector.sidecar.revoke_fail_closed.v1` MUST 证明：已接纳的 Agent revoke、暂停或停用立即停止新的投递、
执行与写入，同时不隐式终结既有交换。

`ak.vector.sidecar.union_history_checkpoint.v1` MUST 证明：Sidecar 并集历史暴露的检查点受请求方自身资格限制，
绝不把历史可见性扩大到请求主体的 effective access 之外。

`ak.vector.signer_key.human_current_privacy.v1` 与 `ak.vector.contact.peer_endpoint_selector.v1`
用 `current-signer-contact-endpoint-fixture.json` 执行 closed schema 正反例：human current 只含公钥且不可
替代 Agent/history；Contact 两字段 endpoint 只属于 accepted human。真实跨站取材、撤销与 exact round
来源签名必须另行用服务与联合测试验证，schema 通过不代表 live 授权通过。

`ak.vector.applet.self_actor_contract.v1` 验证封闭 schema、轮换／首装参考状态机、独立明文签名
和 SDK MLS 群隔离。此证据只覆盖合同与密码学组件，不证明独立 runtime 安装生命周期。
`ak.vector.applet.self_actor_live_lifecycle.v1` 保持 reserved，激活条件见 Applet client/invocation 合同 §4。

`ak.vector.direct_conversation.chat_topic_structure.v1`：由 `direct-conversation-structure-fixture.json` 与 artifact structure gate 逐项执行 Space 密文／明文互斥、解密 plaintext 封闭字段集、独立 Space(kind=topic) 的密文载体、Strand.topic 的显式整体 set/unset、必需完整 CAS、非法 null／子路径／rank 负例，并校验九项 participant action、独立 main/target、root Topic 以及 List／Board 不得充当 Topic 的边界；不宣称此 wire 向量已代替真实 MLS、双设备、跨站或 Agent 产品验收。

`ak.vector.agent.interaction_mode.v1`：`agent-participation-fixture.json` 与 artifact fixture gate 执行已确认
private 默认／unknown 区分、controller-only／CAS／委托禁止、共享 action 门及公开／私人 composer 矩阵，
`event-kind-payload-coverage-fixture.json` 执行模式 payload 的 closed schema 正反例。Containment assertions
固定 Sidecar roster 不变、Circle 不跨界、Message scope 不迁移、上下文不自动发布及 fanout 非追溯；
同 fixture 的 `reply_configuration_contract` 决策表验证 human／Agent 独立消息 authority、明确配置
与仅 preference／mode 的区别、grant issuer／scope／ceiling、逐步骤接纳和 unknown、有效状态与
重启／重新配对／重置／提交响应丢失边界。机读产品合同绑定 canonical registry 中
`did_evidence_boundary_registry.agent_participation_runtime_contract.product_configuration`；它不
引入 wire、profile 或通用自动授权。真实冷启动／保留状态重启的 mention、模型与已显示密文回复
须按 agent-interaction §5 另行验收。
这些声明与决策表不证明生产端的模型信息流、真实 MLS、时序侧信道或第二设备已经通过，实施需另行验收。

### 3.26 治理结果消费角色

`ak.vector.authority_commit_projection.result_consumption_roles.v1` MUST 证明普通 full/e2ee 客户端
只消费已持久接纳、绑定完整账号的自己 Station 的既有原件，不执行方法历史或 retained signer discovery；
错账号/base/selector/scope、混 cut、回退/同位置换 Commit、无 exact floor anchor 与 boolean-only 结果拒绝。
客户端 producer/MLS/attachment 验证保留；Station 与独立审计者的历史、治理签名、nonce/链验证不被角色
分工削弱。角色策略 fixture 的通过只证明机器职责与输入边界；原治理密码学、生产接线和真实跨站验收
仍须各自执行，不能由策略 fixture 推断通过。
