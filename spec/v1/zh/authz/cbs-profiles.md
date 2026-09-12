---
title: 安全域确认与跨域事务
status: candidate
normative: true
stability: v1
updated: 2026-09-12
---

本文规范关键字按 [规范语言](../conformance/normative-language.md) 解释。

## 1. 安全域与配置

v1 的安全域标识就是 RealmId。一个 Realm 的权限、成员、硬唯一槽位、密钥访问和 MLS 安全状态共享一条确认序列。Circle 仍按 scope 隔离授权和读权限，但不产生另一条可能与父 Realm 撤销并行生效的安全序列。不同 Realm 的确认独立；普通数据完全不进入该序列。不能根据 Event 名称推测是否需要 Seal，必须对 canonical registry 的有效 write 求值。

`notary_configuration.kind=quorum` 是唯一配置。`n=3f+1`，其中 f 为 `fault_tolerance`，每次确认需要恰 `2f+1` 个不同 voter。f=0 是单副本、无故障容错的配置。actor、verification_method、frozen key digest 三个维度都必须唯一；同一配置内多个 key 不把一个 voter 变成多票。不得用多个配置的签名拼 quorum。

配置由 `realm.create` 或已确认 `realm.notary` Event 身份引用。成员不能因进程重启、时钟前进或租约超时自启新 lineage。notary 只拥有排序和确认职责，不取得 controller 许可或客户端 MLS 私钥。

## 2. 提案、执行和确认

Seal 的 `realm_id/configuration_ref/notary_seq/predecessor_ref` 唯一绑定安全位置。`view` 只在 `notary_signature` certificate 内，不能改变 Seal identity。genesis 高度 0 且 `predecessor_ref=null`；其它高度必须携同 Realm 唯一已确认 predecessor，且高度恰为 predecessor 加一。Seal 的内容地址输入是去除 `id` 与 `notary_signature` 后的完整 canonical body；更改 command 顺序、结果、前态、配置或任何关闭证据都会改变 Seal digest。commit JWS 签 `JCS({context:"ak.seal.commit.v1",seal_digest,configuration_ref,notary_seq,view})`，其中 seal_digest 是 canonical body 摘要。不同 view 对同一 body 的证书不产生两个 Seal 身份。

`command_results` 给出原子 command unit 的实际执行顺序。每项 `unit_event_digests` 是已登记 unit 的确切成员顺序，`event_digest` 等于首成员；单命令为单元素数组。bootstrap/cascade 只能使用各自已登记的 unit 验证器，任意批次不能自行组成 unit。整个确认历史中同一 Event 只进入一个 unit。实际投票/执行副本与选择独立重放的审计者必须取得并验证所有命令的原始 Event、依赖与结果；非投票消费者按 §9 认证所需结论，不重算已经确认的历史执行。`result_digest` 按 seal schema 的封闭投影从实际注册写入后的完整状态与 reason_code 重算，禁止哈希任意 HTTP response。失败 effects 为空；成功 effects 按 CellRef 排序，每个触及 Cell 只保留执行完该 unit 全部有序 write 后的一个完整 state，包括 bootstrap D 初始值。每个 effect.state 使用该 Cell 固定模型在 snapshot chunk schema 中的完整 state 形状：S 为 `{revision_event_id,value}`，D causal_register 为 `{covered_event_ids,heads}`，其它 D 模型保留完整集合、墓碑、条目或 issuer 分量；不得把 D 改写成单 revision 或仅业务显示值。封闭摘要输入见 seal schema 的 `command_result_digest_input`，同形空数组仍由 canonical family 唯一解释。命令在其顺序位置重新执行授权、确切前置 revision、领域约束和全部写入。`delta` 恰为本 Seal committed units 内所有 security 成员摘要的 canonical sorted set；bootstrap D 成员共享原子 outcome 但不进入该集合；普通数据与失败命令不在其中。

没有有效 security write 的普通命令禁止送入 Seal。bootstrap 的 D 初始值作为已登记安全创建事务的原子结果存在，不能把后续普通更新借此升级为安全命令。普通提交不得等待新的 Seal、KeyView、完整性根、周期签名或原账号 Station。

相同基底的竞争命令最多一个通过身份前置条件。相同业务值、释放后重新成为 null、重复 epoch 号不能替代 revision 身份。拒绝无业务效果；exact retry 返回已持久结果。超时只表示结果未知，调用者查询同一命令，不产生另一个可能重复执行的命令。

## 3. 持久投票与 view change

安全性要求至少 n-f 个 replica 遵守以下 PBFT 规则，签名 quorum 本身不证明实现遵守了规则。每个 replica 在发送任何投票前持久化配置、高度、view、完整提案 digest、prepare 证明及已确认 prefix。崩溃恢复先恢复这些记录，不允许清空后重新投票。

每高度只处理 predecessor 已确认的提案。primary 是 canonical voter 顺序中的 `view mod n`；voter 先验证提案与重放结果，再对同一坐标至多发送一个 prepare。得到 2f+1 个不同 voter 的同值 prepare 后，持久化 prepared certificate，再发送绑定同一值的 commit。得到 2f+1 个 commit 才确认。prepare、commit 和 view-change 使用不同签名域，不能跨阶段计票。prepare 使用 `context="ak.seal.prepare.v1"` 和相同坐标，view-change 使用 `context="ak.seal.view_change.v1"` 并绑定完整新 view 及证据集合。prepared 记录保护该已投值；本地超时不能解锁。合法 new-view 集合选择了更高 prepared view 的值时，replica 在验证完整证据并持久化新 view 后转投所选值；不能为保留一个较低本地 prepare 永久拒绝合法 new view。选择继承某 prepared 值时必须逐字保留其 body，不能改结果或时间。最终 `notary_signature` 只承载 commit 签名。

超时可请求递增 view，不解锁已 prepared 的值。新 view 的 primary 收集 2f+1 个不同 voter 的 view-change 记录，每份包括已确认 prefix 及该高度最高 prepared certificate。按最高 prepared view 唯一选值；同 view 不同 prepared 值属于可验证故障，不能任选。没有 prepared certificate 才能提出新值。所有 replica 验证完整 view-change 集及选值规则后才进入新 view。落后 replica 必须先取得和验证所需已确认 prefix。

不超过 f 个 Byzantine replica 时，两个 quorum 的交集至少 f+1，因此不可能合法确认两个相同高度的不同值。发现双确认时停止该安全域、保留证据，不做 digest 选胜者、不把权限 join 成多值，也不影响无关域普通消息的密码学验证。活性依赖最终通信、至少 2f+1 可用 replica 及公平重试，不承诺永久分区中推进安全决定。

### 3.1 复制协议签名输入

prepare 与 commit 的 canonical transcript 都恰含 `context,seal_digest,configuration_ref,notary_seq,view`，context 分别为 `ak.seal.prepare.v1` 与 `ak.seal.commit.v1`。realm 与 predecessor 由 seal_digest 的完整 body 传递绑定。签名采用 Seal `signature` 的同一 closed JWS carrier，但 payload_digest 必须按对应 phase transcript 计算，不能把 prepare 签名放进最终 commit certificate。

prepared certificate 恰为 `{seal_body,view,signatures}`；signatures 必须为同一 body/view 的 2f+1 个 prepare 签名，按 verification_method 排序。view-change 的 unsigned statement 恰为 `{realm_id,configuration_ref,notary_seq,new_view,confirmed_predecessor_ref,prepared}`，prepared 为该 voter 最高 prepared certificate 或 null。genesis 的 confirmed_predecessor_ref 为 null；其它高度为已确认 predecessor。签名输入恰为 `JCS({context:"ak.seal.view_change.v1",statement:<该完整对象>})`，以同一 signature carrier 传送。new-view certificate 是按 signer 排序的恰 2f+1 项 `{statement,signature}`；所有 statement 的 realm/configuration/height/new_view/predecessor 必须相同，每个 prepared.view 严格小于 new_view，且递归验证完整 body 与 prepare quorum。重复 signer、任意额外字段或不满足最高 view 选值规则均拒绝。

投票消息的传输、重试与本地存储格式不属于公开 Service API，但上述签名对象、计票规则和选择结果属于规范。实现不能因为使用另一种内部传输而改变证书字节或阈值。

## 4. 配置 handoff

旧配置确认 `realm.notary` 时冻结最后可写高度和新配置 bytes。新配置每个 voter 必须取得并验证完整已确认 prefix、终态结果、prepared 事务及锁后才达到本地 ready，才能给第一个后继 Seal 投票。第一个后继的完整新配置 commit quorum 就是交接确认，不另发未定义的 ready wire object。后继只引用旧配置的最后 Seal。ready 只是投票前的本地资格，不能执行命令或改写交接内容。

旧配置在确认 handoff 后拒绝新业务高度，只提供已确认数据与交接证明。新配置未 ready 时安全命令等待；普通消息继续按已验证授权缓存工作。备份、自报新 controller 或过期时间都不能跳过 handoff。恢复必须使用事先确认的独立恢复权，且保持唯一 lineage 与未决锁。

## 5. 授权关闭与有限期

`authorization_closures` 每项精确绑定本 Seal 成功撤销命令、目标授权 Event、generation Event、scope、actions 和完整 Event frontier。授权 Event 指向 grant、设备/身份授权或成员实例的登记起点；generation 不得用可重复的业务状态名称替代。frontier 的完整祖先闭包就是允许保留的历史集。多个适用关闭集合取交集。

关闭条目必须由命令语义派生，不能因为 notary 见过某条聊天而随意产生。撤销不用等所有接收站，因而真实离线消息也可能被排除。每个 receiver 使用相同证据重算 eligible/pending/quarantined；已发生的展示不可回滚，历史导入不得再触发 live 效果。完整规则见 [授权与状态归约](./event-auth-state-resolution.md)。

有限期资格的 `existence_anchors` 绑定授权 Event、generation 和精确 Event frontier；安全域从确切授权状态派生有效窗，不接受 producer 复制的到期时间。每个 anchor 的 frontier 及祖先必须在 prepare 前完整可用并通过历史授权校验。该可选字段只服务显式有限期许可；不得要求无期限聊天定期取得 anchor。

设配置声明诚实 replica 的真实 UTC 时钟误差至多 ε=`max_clock_error_ms`。首次 prepare anchor 或带显式期限的安全命令时，replica MUST 确认本机可信时钟与 `sealed_at` 相差不超过 ε，且所有被锚定或批准的 Event 已存在；该批 Event 已存在这一观测时点于是落在 `[sealed_at-2ε,sealed_at+2ε]`。整个区间必须位于资格有效窗内才签 prepare；时钟不能保证误差界就不投这种票。view change 只能继承完整的原 prepared certificate，不对旧数据重新声明早期存在。commit 可以晚到，但不能改原 body 或该时间证明。

该证明不声称 Event 的实际创建时间位于此区间，只证明资格有效期内已经存在。至少 f+1 个诚实 prepare voter 保证时间见证；quorum 的安全假设和时钟误差假设均属于该保证的前提。没有合格 anchor 的有限期数据可在 live 有效窗暂时接纳，稳定历史保持待证；完整关闭/到期证据已排除其资格时进入 quarantine。producer 时间、普通 IngressReceipt、期后新建的倒签 Seal 均不能补这个证明。无期限普通聊天不需要 anchor，也不需要周期 Seal。

## 6. 跨 Realm 原子性

只读缓存授权不等于跨域原子事务。若一个操作的不变量要求多个 Realm 的安全资源同时变化，prepare 前必须冻结完整参与 Realm 集、每域读写 CellRef、确切前态、命令内容摘要，以及唯一 decision Realm。participant 按 RealmId canonical 顺序拿锁，锁同时覆盖影响授权的读取资源。

每个 prepare 是参与域的确认记录，持久绑定完全相同的事务摘要和参与集合。commit 需要全部参与者的 exact prepare 证明；commit/abort 由唯一 decision 域确认且互斥。参与者只能凭该终态生效及解锁，不能超时自行 abort。晚到 prepare 不重新打开已 abort 的事务；handoff 保留未决锁。

prepare 不释放密钥或执行外部副作用。单次 approval 的 nonce 必须在同一确认事务中唯一消费。外部 sink 还必须接受幂等键/fencing 或提供可恢复执行 owner；Event 去重不能代替外部动作幂等。结果未知时保留待核实状态，不能换 Event 再执行一次。decision quorum 不可用可以阻塞安全事务，但不把普通聊天拖进该事务。

### 6.1 封闭事务载体与执行

Seal 的 `transaction_records` 是唯一事务载体，kind 恰为 prepare/commit/abort/apply。每项携完整同一 `transaction_manifest`：command_event_id、canonical 排序的 participants 和 decision_realm_id。participant 恰含 realm_id、basis_ref、read_cell_refs、write_cell_refs；决策 Realm 固定为排序第一项，不由 coordinator 随意选择。每个 basis 必须在原命令的签名 seal_basis 中，完整读写集由注册 reducer 与全部授权检查的实际依赖重算，漏锁、额外资源或未登记效果均拒绝。

按参与 Realm 顺序逐域 prepare，域内按 CellRef 顺序申请读/写冲突锁。锁取得前重新验证完整前态；前态已改变则由 decision 域确认 abort。prepare 不把原命令列入 command_results/delta，也不把候选权限暴露为有效。普通只读缓存资格的 D 消息不是事务参与者。

commit Seal 只由固定 decision 域签发，必须携按 participant 顺序排列、每域恰一个 same-manifest prepare Seal；缺任一不能 commit。abort 可以在未集齐 prepare 时确认，但不得与已有 commit 竞争成两个终态。participant 收到决定后以 apply 记录原子落实 staged 效果或丢弃候选并释放锁；重复 apply 无额外效果。迟到 prepare 在已知 abort 下拒绝，尚未知终态的锁必须待确切决定补齐。

逻辑事务终态在 decision Seal 确认时唯一确定，participant 的异步 apply 不创造另一个业务决定。读取尚未物化的安全结果时必须补齐并应用该决定或返回 pending，不能拿部分 apply 宣称事务部分成功。command_results/delta 只在原命令的效果所属域 apply 成功时包含该命令；读取参与域不会凭空产生业务 write。所有 auxiliary records 由完整 Seal body 认证，实际参与执行者随连续安全 prefix 重放；非参与消费者也可按 §9 的 transaction 结论验证 exact manifest/phase。不能用只含 Cell 的 state_root 冒充 prepared-lock 完整证明。

### 6.2 依赖、隔离与取得证明

跨域参与集合由安全执行的实际权威依赖闭包派生：命令目标写入、所有 preconditions/pre_state_requirements 的安全 Cell，以及当前授权校验读取的 PCR generation、设备/Agent key、父 grant、成员、scope、policy、单次消费状态，逐一记录所属 Realm 和 CellRef；不存在项也锁其确切目标，禁止幻读。只验证不可变历史签名 bytes 不取得状态锁；普通 D 的缓存授权不进入该集合。实现必须完成全部规则求值而不能因短路先遇 allow 就漏掉其它适用限制。父授权链有上限且参与域超过 schema 上限时拒绝，不截断。

各域 prepare 的 staged 结果与锁由该域复制日志持久化，服务端在验证原始 Event 与跨域 `seal_basis` 后派生内部事务记录，不接受 producer 自报读写集作为权威。既有 self/peer Seal submit 接收完整 Seal；依赖通过每个目标 Realm 的 exact Seal/Event resolve 独立取得，一个 CbsProofBundle 始终只承载其 target Realm。不同 Realm 的 bundle 不能混成一个，也不得为满足跨域验证绕过原有 PCR/Circle disclosure 权限；证明不足返回 pending，不能降级使用当前查询布尔值。

单次批准按 §8 绑定具体 target Realm、批准 nonce、操作种类与预先签署的完整普通 EventId。消费只在该 target Realm 的安全事务发生；同一 controller/Realm/nonce 不能用于另一个命令，已签批准不能复制到另一 Realm。批准者账户/PCR 的可撤销资格若要求当前有效，同样进入读锁集合。副作用执行记录随唯一 command outcome 恢复，未知执行结果不得产生第二次授权。

## 7. 证明消费

CbsProofBundle、exact Seal resolve、governance dependency resolve 继续承载可验证的安全状态证明。多域 `seal_basis.leaves` 每域恰一个已确认 head，canonical 排列；同域多 leaf 无效。不能从缺失证明推导未撤销，也不能以额外 service 回执替换 quorum。

客户端 MLS Commit 保留 staged state 和 exact outbound bytes，唯一确认后安装；明确拒绝后才销毁暂存并重建。epoch 数字不是 fork winner。已知移除者的新发言立即被 gate 阻止；未见移除的分区副本仍可能暂时接纳旧 epoch，这是允许的撤销传播窗口。

## 8. 单次 Agent 批准的发布

`ak.agent.action_approve` 是目标 Realm 的安全命令，同时完成批准与 nonce 唯一分配；它不再是等待各接收站分别消费的私有批准。payload.approved_event_id 绑定 Agent 预先签署的完整普通 Event；后者不引用未来的 approval 或 Seal，因此没有内容地址自引用。提交 wrapper 必须携带 publication_event，其 bytes 在批准前可用于验证，但不得提前业务投递。

批准的 actor 必须是该 Agent 的当前合法 controller，禁止 executed_by 代替实际 controller 签署；目标 Event 的完整 Agent AccountId、signer、Realm/scope、proposed_action、target、draft_content_digest（若存在）与批准内容全部匹配。执行器先验证原 Event 的全部规则，仅将正在确认的这一个 approval obligation 留待本命令满足；其它缺少的许可、批准或依赖不能跳过。controller/PCR/key/grant 的实际当前安全读取加入跨 Realm 事务，期限在安全确认的有界时钟规则下验证。

唯一消费 Cell 是 `ak.component.agent.approval_consumption.v1`，subject 为 `[canonical_json(controller ActorId), approval_nonce]`，所在域恰为原 Event 的 Realm。初态必须未写入，成功值为完整 approved_event_id，revision 为批准命令 EventId。nonce 不释放；竞争批准至多一个成功，失败无发布效果。exact retry 返回原 outcome。批准者对不同 Realm 的批准是不同显式权限，不接受复制到另一个 Realm。

确认后原 Event 按 D 模型发布，发送及重试保持 exact bytes。接收者用现有 cbs_proof_bundles 携带/解析该批准命令的 covering Seal 和确切消费 Cell 证明；这是允许的相关依赖，即使其 Seal 晚于原 Event 的 auth_context。必须校验消费值等于当前 EventId，不能用同内容、同 nonce 或同 Agent 的其它 Event 代替。cbs_proof_bundles 本身不授权。存储者必须与原 Event 一并保留这份证明，历史分类仍执行其它适用关闭约束。

批准确认和待发布 outbox 必须原子持久化，崩溃只恢复原 Event；目标数据缺失时 pending，不换身份重建。私有 draft 的 published 状态从已确认批准与确切发布结果派生，不是共享准入权威。外部副作用仍要求唯一 command outcome 与下游幂等/fencing。未要求单次批准的普通 Agent 消息完全不走此流程。

## 9. 非投票接收者的 quorum 结论（normative）

### 9.1 责任与唯一载体

非投票 Station MUST 接受本节认证的确切安全事实作为相应治理验证依据，不得仅因自己没有重放完整历史而拒绝。
“独立验证”在该角色指验证信任起点、配置、quorum、事实与操作绑定；实际执行/投票副本和明确进行独立重放的 auditor
继续完整验证命令、历史授权、CAS、结果、事务与根。承担多个角色的进程必须分别满足各角色义务。
普通客户端仍消费自己 Station 的结果，不取得本节证明。注册/genesis 尚无先验 Seal，仍验证完整原子 anchor unit、
外部身份根和精确 RealmId；不能由待证明的 notary 自证其起点、PCR/controller delegation 或外部 DID。

唯一新增的公共证据是 [seal-conclusion.schema.json](../../artifacts/schemas/seal-conclusion.schema.json)。
它认证已确认事实，不修改 Seal canonical bytes、PBFT commit transcript、state_root 或既有 Merkle 树，
不引入安全命令、独立授权、controller 权力、witness 服务或新的确认序列。原 Seal/证明可按既有方式离线验证；
其中未获授权的正文、整 Cell、相邻叶或辅助记录不得为满足消费者重放而披露。

### 9.2 签名与配置认证

`certificate` 字段顺序为 `statement, signatures`。statement 顺序为
`realm_id, configuration_ref, authority_seal_ref, target_seal_ref, results`。
每个 signature 使用 Seal 的 closed JWS carrier，payload 为
`JCS({context:"ak.seal.conclusion.v1",statement:<完整 statement>})`；`payload_digest` 固定为该 payload
的 SHA-256 typed digest。JWS protected alg/kid 必须匹配配置 frozen key；payload 必须是 exact canonical bytes，
拒绝 unknown crit、非 canonical 编码及跨 context 签名。恰好 `2f+1` 个不同 configured voters 的签名才有效，
按 verification_method UTF-8 顺序排列；actor、method、frozen key 三维唯一，不混不同配置、不把一个 voter 的多把 key 算多票。
`f=0` 使用同一结构的一票 quorum。此签名不是 commit/prepare/view-change，不能在这些阶段计票；反之亦然。

签署者 MUST 已完整验证并耐久接纳 authority_seal_ref；该 Seal 在其合法配置的确认位置上，target_seal_ref 必须是
同一已确认 lineage 上的祖先或自身。结论可针对交接前的历史 target，但签署者必须实际持有并验证该目标状态与结果，
不得仅对另一服务的查询结果重签。结论没有自报 current、TTL 或“全网最新”含义；authority_seal_ref 是签署时已有的
确认状态坐标，不是新的 Seal。派生读签名不需要创建空 Seal 或为查询启动一次新的 PBFT 决定。

消费者 MUST 从已验证 Realm genesis 配置或已耐久认证的配置开始。`configuration_handoffs` 只含实际必需的连续交接，
不得用 candidate 自报配置、当前 DID key、裸 service signer 或新组自签替代。首次起点及历史 producer signer 的
不可变原始依赖仍走既有 exact resolve，不因本节删除。冷缓存缺这些材料则未决，不能用同 Realm 名称猜起点。

`handoff_certificate` 同样为 `statement, signatures`；statement 顺序为
`realm_id, configuration_ref, handoff_seal_ref, next_configuration_ref, next_configuration`。
签名 payload 为 `JCS({context:"ak.seal.configuration_handoff.v1",statement})`，payload_digest 同样使用 SHA-256。
旧配置在其最终 handoff Seal 已确认后才签，逐项认证其中 exact realm.notary Event 安装的新配置，以及旧组后继写权冻结。
签署与存储这份结论不另产生控制决定。旧组 MUST 将完整 quorum 交接结论耐久交付并复制到新组后才允许新组激活；
新组仍必须按 §4 取得完整已确认前缀、未决事务及锁。新组首次后继 Seal 的 commit quorum 仍是执行层就绪确认。

消费者按链顺序用当前可信旧配置验 handoff quorum，检查 Realm、配置引用及 descriptor 合法性，再安装 exact 新配置。
后一个交接或最终结论由新配置 quorum 签署，签署资格包含其已完成 §4 就绪。拒绝跳步、循环、重复/竞争配置、
混票、已知不连续前缀和与耐久可信状态相冲突的交接。证书链不得扩大为读取各配置时期的全部私有历史。
配置交接之后，旧组不得为新查询签署结论；已有历史结论不因正常交接、key 轮换或转交而追溯失效。
新组可为已完整继承并验证的历史 target 签结论，不要求退役旧组上线。

本节依赖各配置不超过 f 个 Byzantine 副本的故障假设。超过该界限时不能靠结论验签证明计算正确；已知双确认或
配置冲突仍停止受影响安全域。不能以“信任 quorum”为由忽略已知反证或让不具备完整验证能力的副本投票/签结论。

### 9.3 封闭查询与确定性结果

query 顺序为 `target_seal_ref, selectors, known_configuration_ref`（最后一项可选，仅为接收方已认证配置的传输提示，不能创造信任或读取权；其省略/变化不改变 target/selector 事实的签名）；selectors 为 1..64 个 closed 分支，按其 JCS UTF-8 bytes 严格排序、去重。
result 顺序为 `selector` 后接该分支的结果字段；results 必须 every-and-only 对应 query，使用相同顺序。
结论只在这个目标求值，不接受 caller 自报计算式、任意 allowed 布尔值或服务自行选择“更方便”的 basis。

| selector kind 与字段顺序 | 结果字段 | 必须认证的事实 |
| --- | --- | --- |
| `cell, cell_id` | `state` | target 结束状态的 exact Cell；未写入为 null；已写入为 `{revision_event_id,value}`，即使 value 为 null 仍保留对象和 revision。 |
| `cell_range, lower_cell_id, upper_cell_id` | `cells` | 按完整 CellRef Unicode code point 顺序，半开区间 `[lower_cell_id,upper_cell_id)` 中 every-and-only 已写入的安全 Cell，按 cell_id 严格排序；每项 `{cell_id,state}`。lower_cell_id 必须小于 upper_cell_id。空数组是该精确区间的不存在结论，不暴露邻居。 |
| `command, event_digest` | `result` | 该 exact target Seal.command_results 中包含此 Event 的 unit 的完整 command_result；null 仅表示该 Seal 没有该命令，不能推出整个历史不存在。 |
| `command_effect, event_digest, cell_id` | `state` | 此 Event 所属 unit 在 target 中完成时对这个 Cell 的最终成功写入；无成功写入为 null。不是整 Seal 结束状态，不能由后续写入替代。 |
| `transaction, record_index` | `record` | target.transaction_records 中该零起始位置的完整登记记录；越界为 null。消费者另验 expected phase、manifest、participants、command 与 decision Realm。 |
| `ancestry, ancestor_seal_ref` | `is_ancestor` | 该 Seal 是否属于 target 的同 Realm 确认前缀，含自身；不涉及普通 Event、全网观察或 current。 |

Cell 的 value 必须通过 canonical cell contract 的完整类型与语义校验；普通 D Cell 不得作为安全状态结论。
为新命令准备状态或解释治理政策时，消费者 MUST 同时认证目标 basis 的 ak.component.realm.reducer_profile.v1 与 ak.component.realm.digest_suite.v1（或其已认证的 immutable genesis 初值），按该确切 profile 和本地已登记规则求值；未知 profile 使用既有 unsupported_profile，不能用软件 latest 默认或服务自报 registry 替代。消费已确认 command outcome 不再重新判断当时业务规则；历史原文/密码材料仍按其原已认证 suite 与签名上下文解释，不重哈希旧引用。
command_effect 的非空状态必须属于已 committed unit，revision 是其最后成功写入的 Event；拒绝命令不得产生效果。
签署者按实际已保存的执行位置求值，消费者不重新构造同 Seal 中间前态。只消费“已 committed/rejected”可直接使用
command result；需要 effects/current membership 时分别取得相应事实。result_digest 不构成局部 effect 的 Merkle 证明。

cell_range 仅服务现有注册操作的确定性证明义务，不增加通用枚举权限。由调用操作的 registry、精确 scope/group/ActorId
与 basis 派生必要区间/Cell，不能让远端通过自选一个较小集合证明完整性。消费者必须核验其实际需要的全部区间/Cell
都已覆盖；多个子区间必须无缝覆盖所需区间，不能由“首尾存在”推断中间完整。区间过大时按有界区间分割为多次
既有查询；每个结果是完整子区间，不在 certificate 内截断、伪造终页或增加未登记 cursor。不能证明完整就未决。

### 9.4 披露、传输与失败

证书认证事实，不授予读取权。每次交付（包括缓存重放）MUST 按原 operation 的 authenticated requester、Source/Destination、
完整账号、scope、intent 和当前披露政策重新授权。证书、整值、command unit 成员、事务记录、配置交接以及外层错误/大小
都纳入披露检查；任一必要结果不可披露则整个 query 不成功，不得删字段、隐藏部分 cell_range 结果后声称完整。
未写入的 Cell 与存在的 Cell 使用相同 scope 授权判定，禁止借 absence 查询探测私有对象。

查询复用 `ak.self.seals.read.resolve.v1` 与 `ak.peer.seals.read.resolve.v1` 的 `conclusion_queries` 分支，
与原 `seal_refs` 互斥。既有 self/peer 授权与 history_traversal_access 边界不变；普通 self 客户端不以此取得治理证明。
response 使用 `conclusion_set, missing_conclusion_queries`，每个 query 恰对应一份匹配全部 selectors 的结论
或原样 missing query。全部 missing 时省略 conclusion_set；unknown、无权、缺材料/无 quorum 共用 missing，不返回部分成功 query。
每次最多 128 个 query，每 query 64 个 selector，每 range 512 个 cell，每 certificate 的 canonical bytes 最多 8 MiB；
请求 ≤64 KiB，response ≤8 MiB。超限用既有 limit_exceeded，不拆签名对象。handoff 最多 256 项、每次 conclusion_set 最多
128 份 conclusion；可按 known_configuration_ref 省去接收方已独立认证的交接前缀；完整必要链仍超预算则 limit_exceeded，不声称存在未登记的配置分页，也不截断成“已认证最新”。不对外细分私有依赖缺失原因。

首次加入继续走有 intent gate 的 bootstrap，不开放成员级 resolve。bootstrap 的 `seal_conclusion` typed record 承载
同一 conclusion_set；来源站从已注册加入规则机械求完整事实集合，outer governance_facts 与 preconditions 必须与认证值一致。
受限 application-status 在 sealed 时 MUST 携同一 conclusion_set，仅证明此申请的 command 与成员结果；它不授权读取其他 Seal 正文。
CbsProofBundle 的 conclusion_set 为同一载体，非投票消费可令 replay arrays 为空；容器本身不签名、不产生权威。

结论可跨请求缓存和由获授权持有者转交，历史 statement 不绑定 request_id 或重新计时。只允许无副作用地复用同一
事实；逐请求授权、已知撤销、有限期和实际动作检查不缓存成永久许可。冷查询确需新 quorum 读签名时，若 quorum
不可用则明确未决；不保证任意未缓存 selector 在 quorum 离线时可取得。不得将该读签名变成普通消息、重复读取或
已有证据消费的强制在线依赖。后台预取不扩张授权，也不得要求周期空 Seal。

### 9.5 业务消费与保留

非投票站 MUST 保存所用信任起点、认证配置、结论、必要 canonical bytes、实际语义/作用域与已知撤销依赖，
并与其局部接纳/投影原子持久化；不能把局部事实标记为整 Realm 已重放、投票 ready、全量 roster/历史完整或 GC 依据。
对同一不可变 target/selector 的计算和验签持久共享；每请求分别授权。收到原始 Seal 时仍按完整原始 bytes 验
其内容地址与签名，不把 conclusion 的 target 引用当成验过该 Seal 原文。

安全命令新执行仍在实际执行位置检查业务值与 signed basis 派生的 revision/锁；源站 accepted、authority intake、
committed、成员投影及 MLS Welcome 仍是不同阶段。配置已认证不表示全网最新，已知相关撤销立即阻止新的 live 效果，
普通消息保留未知撤销的传播窗口。普通 Event 签名/actor chain/CRDT、MLS transcript/秘密 MAC、HPKE/AEAD、
AvailabilityReceipt、archive 真正持久化和外部副作用幂等不由 quorum 结论替代。

跨域消费者按各域独立配置验证所需 transaction/Cell/command 结论，必须覆盖同一 manifest 全体 participants，
只在固定 decision Realm 使用唯一 commit/abort；实际参与执行者继续本域锁、完整求值与 apply。未物化的结果仍须
完成 apply 或 pending。一个域不能通过签自己的结论取得另一个域的身份、状态或授权权威。

历史恢复可用 exact epoch/transition、incarnation、T0 上界与 current ratchet 事实和必要 ancestry 结论替代治理 cut
重放，但每个请求 epoch 与区间必须完整认证；T1 首次入队、来源签名、接收密钥及解密检查不变。投票接管、独立审计、
内容恢复或 archive 耐久所需原始材料仍按其职责保留，不能因 reader 改用结论而删除唯一资料。
