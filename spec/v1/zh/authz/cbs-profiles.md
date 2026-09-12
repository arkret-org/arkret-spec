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

Seal 的 `realm_id/configuration_ref/notary_seq/predecessor_refs` 唯一绑定安全位置。`view` 只在 `notary_signature` certificate 内，不能改变 Seal identity。genesis 高度 0、无 predecessor；其它高度恰为已确认 predecessor 加一。predecessor 必须是同 Realm 的唯一确认 Seal。Seal 的内容地址输入是去除 `id` 与 `notary_signature` 后的完整 canonical body；更改 command 顺序、结果、前态、配置或任何关闭证据都会改变 Seal digest。commit JWS 签 `JCS({context:"ak.seal.commit.v1",seal_digest,configuration_ref,notary_seq,view})`，其中 seal_digest 是 canonical body 摘要。不同 view 对同一 body 的证书不产生两个 Seal 身份。

`command_results` 给出原子 command unit 的实际执行顺序。每项 `unit_event_digests` 是已登记 unit 的确切成员顺序，`event_digest` 等于首成员；单命令为单元素数组。bootstrap/cascade 只能使用各自已登记的 unit 验证器，任意批次不能自行组成 unit。整个确认历史中同一 Event 只进入一个 unit。所有命令的原始 Event、依赖与结果内容必须可用并独立验证。`result_digest` 按 seal schema 的封闭投影从实际注册写入后的完整状态与 reason_code 重算，禁止哈希任意 HTTP response。失败 effects 为空；成功 effects 按 CellRef 排序，每个触及 Cell 只保留执行完该 unit 全部有序 write 后的一个完整 state，包括 bootstrap D 初始值。命令在其顺序位置重新执行授权、确切前置 revision、领域约束和全部写入。`delta` 恰为本 Seal committed units 内所有 security 成员摘要的 canonical sorted set；bootstrap D 成员共享原子 outcome 但不进入该集合；普通数据与失败命令不在其中。

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

逻辑事务终态在 decision Seal 确认时唯一确定，participant 的异步 apply 不创造另一个业务决定。读取尚未物化的安全结果时必须补齐并应用该决定或返回 pending，不能拿部分 apply 宣称事务部分成功。command_results/delta 只在原命令的效果所属域 apply 成功时包含该命令；读取参与域不会凭空产生业务 write。所有 auxiliary records 由完整 Seal body 认证并随连续安全 prefix 重放，不能用只含 Cell 的 state_root 冒充 prepared-lock 完整证明。

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
