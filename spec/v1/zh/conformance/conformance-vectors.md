---
title: Conformance Vectors
status: candidate
normative: true
stability: v1
updated: 2026-09-16
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

本节逐条定义 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 登记的一致性向量，
其中一部分另有可执行 fixture 证据。每条给出该向量 MUST 证明的判定点；适用面、profile 与正文依据以 registry 行为准。
`normative-clause-registry.json` 的 `coverage_scope.executable_fixture_categories` 列出的条款类别中，
每个向量 MUST 有一份 fixture 用 `security_evidence` 把本节的判定点逐条映射到该 fixture 内可解析的 case；
尚未闭合的 (条款, 向量) 对必须逐条登记在同一 registry 的 `executable_evidence_exemptions` 里，该清单只减不增。
fixture 存在、suite id 已登记或向量 active 都不等于参考实现已执行：认证器 MUST 拒绝未映射的 suite，
也 MUST 拒绝缺少逐 case 实际断言结果的运行。全部判定按本规范
当前的 Event / RealmCommit 边界解释：Event 只承载 producer 意图，接纳由当前治理 Station 的 `RealmCommit` 表达，
一条 `RealmCommit` 恰好接纳一条 Event，Realm、每个 Circle 与每个 Sidecar 各有独立 commit stream。

### 3.1 Account 与偏好

`ak.vector.account.blocklist_projection.v1` MUST 证明：个人 blocklist 是 holder-private 的整值 CAS 更新；
target 闭包完整；共享历史先接收后按 holder 侧投影过滤；解除屏蔽后投影可从既有材料重建；过滤结果不可被外部枚举。

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
也不得直接通过写入执行；必须存在可复现的 proposal / review 生命周期；审核通过后产生可验证的审批完成 Event，
再由独立 action Event 执行。

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
`refs[role=causal]` 指向的前驱在本地不可解析或尚未取得有效 `RealmCommit` 时，依赖它的 Event MUST fail closed 或保持本地等待，
MUST NOT 被静默接受、补造前驱或按到达顺序自行判定成立；前驱取得 Commit 后同一 Event 才可被接纳。

`ak.vector.authority_commit_projection.revoked_authorization_fails_closed.v1` MUST 证明：
Event 提交与其 `RealmCommit` 之间授权被撤销时，该 Event MUST 以确定性失败被拒，MUST NOT 因为已经排队、
已经本地投影或使用同一 request key 重试而被放行；已 revoked 的授权 MUST NOT 在重试路径上复活。

`ak.vector.authority_commit_projection.invalid_proof_fails_closed.v1` MUST 证明：
producer proof 或 `RealmCommit` 签名无效、绑定错误 `governance_generation`、或 `previous_commit_ref` /
`stream_position` 链接不成立时，消费方 MUST 拒绝该 Commit 并保持依赖它的状态未变更，
MUST NOT 降级为“签名可疑但内容看起来合理”的接受路径。

`ak.vector.authority_commit_projection.exact_retry_preserves_authorization_and_cas.v1` MUST 证明：
以 exact 相同 canonical bytes 重试等待中的 Event 时，`refs[role=authorized_by]` 与领域 `expected_revision`
MUST 逐字保留：重试 MUST NOT 剥除授权引用、MUST NOT 把陈旧 CAS 改写成当前值、也 MUST NOT 因为“已经试过一次”而跳过
当前授权重判。陈旧 CAS 的重试仍 MUST 以确定性失败被拒，不产生 Commit。

### 3.5 Consent 与 identity link

`ak.vector.consent.cache_invalidation.v1` MUST 证明：consent 处于 active 时被缓存的 private contact discovery
结果、invite capability gate 与 PSI 索引，在 subject 撤销 consent 后立即失效——directory lookup 不再返回该 peer，
下一次 invite 提交 MUST 前置条件失败并重判 capability gate，`any` 范围的撤销 MUST 失效全部 scope cache，
PSI 索引在下一轮轮转中排除该 peer。

`ak.vector.identity_link.eager_invalidation.v1` MUST 证明：principal 在 Realm 中的 active identity link，
在该 Realm 接受 ban、leave、remove 任一 membership 迁移，或 capability revoke 使该 link 不再满足
可见性门限后，directory、sync cache、invite cache 与本地 profile 投影 MUST 立即失效；后续 lookup 不得返回旧 link；
既有 session 与 device claim MUST 在下一次授权检查时失败或降级到最小披露状态。

`ak.vector.identity_link.policy_tightening_invalidation.v1` MUST 证明：披露策略、历史可见性、
linked Realm 可见性或 Circle effective-scope 可见性中任一项被收紧后，所有受影响 cache MUST 按当前策略失效；
未重新通过当前策略门限的旧 link MUST NOT 返回，接口只能给出当前允许的最小身份信息。

### 3.6 Contact 与 Direct Conversation

`ak.vector.contact.next_prepare_input.v1` MUST 证明：`ak.self.contact.read.list.v1` 投影携带封闭的
`next_prepare_input` 后继游标——accepted 行 MUST 携带它，五个不可作者化的 `contact_state` 值 MUST NOT 携带；
其 `contact_round_id`、`version` 与 `predecessor_event_ref` 逐字复制进 scope update 与 tombstone 两个 prepare 阶段；
`version` 是下一条 Event 的 version，`predecessor_event_ref` 是当前谱系头而不是该头的前驱；
过期游标以 `contact_lineage_conflict` 或 `contact_scope_stale` 拒绝，且 MUST 重新读取而不是猜测或原样重试。

`ak.vector.contact.pending_incoming_prepare.v1` MUST 证明：本 Station 已验证的 incoming request 投影包含
exact `request_event_ref` 与可选的原始 `request_message`；客户端只提交 peer 与 ref、核对准备好的意图并签名，
不解析请求 Event、也不验证外部 receipt 或历史；服务端加载 durable evidence，并对过期、持有者错误、peer 错误、
glare 与已消费 slot 一律零写入拒绝；Contact 镜像永不通过 Event resolve 暴露。

`ak.vector.direct_conversation.founding_unit.v1` MUST 证明：caller 自行作者化的 first-valid founding unit——
对四个有序 Event ID 的 `founding_unit_digest` 逐字节 KAT，`realm_id` 与 `main_strand_id` 分别由第一与第三个
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
服务端可验证的发送阻塞原因。`personal_blocked` 与 `history_key_unavailable` 不在封闭 wire 枚举中——
holder blocklist 状态加密给 holder 设备、历史密钥安装是设备私有——因此携带其一的响应判 `schema_violation`；
它们只由封闭的客户端本地阻塞集合承载，永不出现在任何 wire 面，也不把解析器状态变成 suspended。
`presence_offline` 与 `keypackage_empty` 仍可由服务端验证，但只返回给既有的 exact pair 参与者；
非参与者探测得到与不存在的 pair 完全相同的不透明失败。

### 3.7 编码与 proof context

`ak.vector.encoding.event_digest.v1` MUST 证明：event digest 的 preimage 是移除 `event_id`、`proofs` 与
`unsigned` 后的 canonical Event Envelope；`event_id` 由该 digest 一次前向派生，因此 MUST NOT 出现在 preimage 中。
`event_id` 的 33 octets 为 suite code 拼接完整 digest 后做无 padding base64url。实现 MUST NOT 把 transport
envelope、HTTP header、Station sync 面的 metadata 或本地接收时间放入 event digest；同一 Event 在不同读取面上
MUST 得到相同 digest。

`ak.vector.encoding.canonical_event_tie_break.v1` MUST 证明：[`encoding.md` §3.4](./encoding.md) 的
canonical 展示顺序——对一组互不排序的候选 Event，排序键是**解码后的 digest octets** 的 unsigned lexicographic
升序，octets 相同而 suite 不同时以 canonical suite id 的 UTF-8 unsigned bytewise 升序作第二键。向量 MUST
包含一条 wire string 顺序与 decoded octets 顺序**相反**的 case，证明直接比较 `<suite>:<hex>` 或 base64url
字符串会得到错误序列。全部候选 MUST 保留且没有 winner：该顺序 MUST NOT 决定授权、admission、finality、
`stream_position` 或 `previous_commit_ref`，也 MUST NOT 使任一候选被删除或遮蔽。digest preimage MUST 逐字
使用移除 `event_id`、`proofs` 与 `unsigned` 后的 canonical Event body；加入额外业务字段的实现 MUST 失败。
仅 `proofs` 或 `unsigned` 不同而 canonical preimage 逐字相同的两个输入 MUST NOT 被报成 collision；同 suite、
同 octets 而 canonical preimage 不同 MUST fail closed，MUST NOT 回退到 `event_id`、`created_at`、到达顺序或
实现私有 ID。向量同时明示 producer 击败一个已知随机 digest 的期望尝试数约为 2，因此该顺序是 producer-biased
的展示排列而不是公平选举。

`ak.vector.encoding.extension_slot_roundtrip.v1` MUST 证明：schema 明示的 `x_*` 槽位与
`critical_extensions[].parameters` 中未识别的内容，在 decode 与 encode、存储、联邦转发与 backfill 之后逐字节保留，
并继续进入 canonical bytes。该向量的输入 MUST 是**具体 canonical schema 明示允许扩展槽**的合法对象；
任意容器上的 `x_*` 正例 MUST NOT 被推广成“所有 schema 都允许扩展”。向量 MUST 固定扩展值与 canonical 输出
bytes／digest，并逐项证明往返后未知成员、嵌套值、数组顺序与字符串内容都没有被丢弃、补默认或归一化。

路径 MUST 逐条给出观测，不得以其中一条代表全部：decode／encode 往返、存储读回、联邦转发后的对端读取、
backfill 重放，以及 canonical bytes／digest／签名校验。字节比较沿用
[`encoding.md` §2](./encoding.md) 的既有 canonical 合同，MUST NOT 把 JSON 空白或对象成员的书写顺序
引入新的保留义务。改变扩展槽内容 MUST 改变适用的 canonical digest 与签名校验结果，
从而把观测点钉在“扩展内容确实进入了 canonical bytes”而不是“对象仍能解析”。

同一向量 MUST 保留两组负向对照：schema 未声明的字段仍 MUST 被拒绝，不得借扩展槽规则放行；
声明了本构建不支持的 critical extension 的对象仍 MUST 整体 fail closed
（判定见 `ak.vector.sdk.unknown_critical_feature_fail_closed.v1`），
MUST NOT 为了让 roundtrip 正例通过而绕过 criticality 验证。未知
`critical_extensions[].parameters` 的逐字节保留只在该 critical feature 已被支持时才被要求。

`ak.vector.encoding.result_selector_uri.v1` MUST 证明：canonical MIMI room URI 是 typed current result 的
subject 来源；哈希化 subject、URI fragment 截断与 caller 自行分配的备用 room 标识符一律拒绝。

`ak.vector.proof_context.transcript.event_envelope.v1` MUST 证明：`ak.event_proof.v1` 的 transcript KAT——
digest 输入恰好删除 `event_id`、`proofs`、`unsigned` 三个成员；canonical binding bytes 与 detached JWS 逐字节固定；
同一未签名 body 在 `ak.extension_manifest_proof.v1` 下重放 MUST 拒绝。

`ak.vector.proof_context.transcript.event_batch_receipt.v1` MUST 证明：`ak.receipt_proof.v1` 的 transcript KAT——
digest 输入删除 `proofs`；canonical binding bytes 与 detached JWS 逐字节固定；同一未签名 body 在
`ak.registration_did_evidence_control_proof.v1` 下重放 MUST 拒绝。

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

`ak.vector.relation.conflict_resolution.v1` MUST 证明：`ak.relation.resolve` 是唯一登记载体，用于了结一个
Relation 主冲突域——`retain_candidate` 恰好保留一个被覆盖候选并沿用其原 RelationId，`void_all` 使被覆盖集合
不留 active 边但保留事实。每次解决都绑定完整的冻结基线；缺失、重复、已被取代或外来的成员使整条提交被拒。
内联诊断最多携带十六个候选，更大的集合使用同一套完整分页载体。并发解决由 `expected_revision` compare-and-set 串行化：落后 revision 的解决以 `failed_precondition` 拒绝且零写入，
全部 Event 身份保留；后续获授权的解决以当前裁决的 `CurrentRevision` 为 `expected_revision` 接纳后取代它。冻结基线之外新发现的候选
重新置回 `require_review` 作为显式跨域检查。

### 3.9 Federation 与 MIMI

`ak.vector.federation.idempotency_after_key_revoke.v1` MUST 证明：origin service 以 active service key 提交的
peer 批次被接纳后，若该 key 随后被撤销、destination 已接纳的授权前缀前进，则攻击者重放完全相同的 body、
签名与 `Idempotency-Key` 时：仅命中历史幂等缓存的 MUST 返回 `historical_only` 而不重新接受为当前授权写入；
origin service binding 已被 Realm policy 移除的 MUST 返回 `capability_denied`；
`origin_key_state_digest` 或授权依据与缓存条目不一致时，receiver MUST 重新执行完整授权判定，
不得只凭 `Idempotency-Key` 放行。

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

### 3.11 邀请

`ak.vector.invite.claim_reducer_state_machine.v1` MUST 证明：`ak.invite.claim` 的 Realm reducer 权限——
`binding_proof` 与 `subject_proof` 的签名 transcript、`token_commitment` 匹配、`verification_id` allowlist 复查、
`claim_nonce` 重放拒绝、pending 到 claimed 的成员提案转换，以及过期清理，都在接纳之前执行。

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

`ak.vector.message.poll_reducer.v1` MUST 证明：已接纳的 Message Event 是 Poll 的唯一真值来源；
完整 ActorId 与 Realm、Circle 分区保留因果响应集合；封闭的因果头按未签名 UTF-8 摘要顺序选出唯一完整投票；
到达排列、迟到依赖、环、作废，以及可交换、可结合、幂等的副本并集，在头集合、胜者、选择项与计票上必须收敛。

`ak.vector.reaction.remove_wins_join.v1` MUST 证明：reaction 的 add 与 remove 并发合并以 remove 取胜；
redaction 之后 reaction 不复活；跨 MLS epoch 的 reaction 仍绑定目标 Event 与 scope；
capability revoke 之后该 actor 的新 reaction fail closed，既有 reaction 保留为历史事实。

`ak.vector.read_cursor.multi_device_merge.v1` MUST 证明：多设备阅读游标合并以因果优先——
因果上占优的位置即使 HLC 更小也胜出；HLC 取最大值只用于裁决因果并发的位置；HLC 相等时由 `device_id` 打破平局；
因果闭包无法判定时保持 provisional。

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

`ak.vector.sdk.envelope_precheck_rejects_before_consumption.v1` MUST 证明：不满足 `ak.schema.event.v1`
或其事件种类所声明 payload class 的 Event Envelope 以 `schema_violation` 被拒，且在 reducer 状态、投影、查询结果
与本地缓存中都观测不到任何效果；重试、重连与 backfill 路径都不会重新接纳它，也不会把它规整、补默认值或修复成可接纳
形态。观测点是被消费效果的缺席，而不是 schema 判定本身。

`ak.vector.sdk.envelope_forbidden_top_level_fields.v1` MUST 证明：`hlc`、`producer_revision`、`domain_refs`、
`requirements` 出现在 Event 顶层时逐个以 `schema_violation` 被拒，而不是被忽略或剥除；`proofs`、`scope_ref`、
`actor_id` 与 `refs[role=authorized_by]` 各自缺失时同样被拒，且不从默认值、传输层、会话或相邻 Event 合成替代值后
进入验证路径。

`ak.vector.sdk.unknown_critical_feature_fail_closed.v1` MUST 证明：声明了本构建不识别的 critical extension 的
对象以 `unsupported_feature` 整体拒收，判定取自 criticality 声明而非扩展体是否恰好可解析，且拒收发生在任何 payload
成员被消费、落盘、投影或转发之前；未声明 critical 的未知扩展仍被接纳并在往返中逐字节保留，因此把全部未知值一律拒收的
实现在此失败。

`ak.vector.sdk.requirements_mismatch_fail_closed.v1` MUST 证明：声明的 `requirements` 指向本构建不提供的能力时
以 `unsupported_feature` 拒收，这是与未知 critical extension 不同的判定；提供该能力的构建接纳同一个对象，从而把
观测点钉在 requirements 检查而不是 schema 失败上。

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

`ak.vector.sidecar.context_locator_recovery.v1` MUST 证明：仅 controller 可用的完整分页与结构化 Event 配对
即可恢复私有 Sidecar 上下文定位符，无需新增任何披露端点。

`ak.vector.sidecar.existence_privacy.v1` MUST 证明：以既非 controller、也不属于其 owned Agent 的调用方视角——
账号 Event 流与扫描对目标 Realm 返回零条引用 Sidecar native scope 的 Event；不存在可用于枚举 Sidecar 或
来源上下文映射的协议 Relation；Realm directory 对 `sidecar_id` 与 controller 映射零命中；
Sidecar 内 Event 不触发来源 Strand 参与者的通知；Sidecar 作用域的 Event 不出现在 Realm `RealmCommit`
的明文安全 metadata 中，只能作为不透明承诺。

`ak.vector.sidecar.explicit_publish.v1` MUST 证明：只有显式的 controller 确认才创建一条被 allowlist 允许的
普通共享 Event，且其中零私有标识符、零历史、零定位符。

`ak.vector.sidecar.multi_agent_publish.v1` MUST 证明：Agent 执行 publish 时 `actor_id` 与 `executed_by`
MUST 是单一 Agent DID，不得出现 Agent 组式的复合归属；另一 Agent 的 grant 不覆盖该内容或缺少新鲜审批时
MUST fail closed；它凭自己的 grant 可独立发布，归属仍是其单一 DID。

`ak.vector.sidecar.hosted_projection.v1` MUST 证明：context attach 只建立来源上下文映射，额外的 track 或
message 字段按封闭 schema 拒绝且不创建 Strand 或 Relation；本地交换投影缓存删除并重建后不重复 request
或 Agent 执行，回显位于已见共享位置之后并按稳定键排序；主 Strand 的标题、面包屑与 Track 页签在两种模式下
保持可见，缺失的 Sidecar 私有视图显示空态而不回退到共享读写；合并视图按 Sidecar Event id 去重并持续显示
来源与仅 controller 可见标识；只有 request 与显式面向用户的响应可进入回显，内部协作 Event 与 Sidecar 内
native Event 不创建回显；第二设备得到相同排序、状态与去重结果，且无需在来源 Realm 重放私有 Event。

`ak.vector.sidecar.hosted_ui_matrix.v1` MUST 证明：Chrome 与 Edge 上执行 hosted 的多 Track、多模式、多设备、
多 Agent 与响应式 UI 矩阵，状态保持且具备增量切换证据。

`ak.vector.sidecar.non_disclosure_surface_matrix.v1` MUST 证明：每一个共享列表、展开、动态、导出、URL、
日志与遥测面都不披露 Sidecar 定位符、身份、内容或折叠输入。

`ak.vector.sidecar.revoke_fail_closed.v1` MUST 证明：已接纳的 Agent revoke、暂停或停用立即停止新的投递、
执行与写入，同时不隐式终结既有交换。

`ak.vector.sidecar.union_history_checkpoint.v1` MUST 证明：Sidecar 并集历史暴露的检查点受请求方自身资格限制，
绝不把历史可见性扩大到请求主体的 effective access 之外。
