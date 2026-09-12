---
title: Event Authorization and State Resolution
status: candidate
normative: true
stability: v1
updated: 2026-09-12
---

本文规范关键字按 [规范语言](../conformance/normative-language.md) 解释。

## 1. 权威来源与执行模型

本文件定义共享 Event 的授权、确定性投影和安全事务生效。规范类型与字段形状以 `event-envelope.schema.json`、`seal.schema.json` 及 `contract-registry.json` 为机读真源。未知 kind、字段、状态模型、条件或 critical reference MUST 拒绝，缺少已声明证据 MUST pending，不能推断为 allow。

每项注册 Cell write 声明 `execution=data|security` 与 `state_model`。先从签名 Event 求值该 write 的封闭 `condition`，再派生目标与效果。存在任意有效 security write 时，整个 Event 是原子安全命令；否则是普通数据。没有有效效果的 reducer Event MUST 拒绝。producer MUST NOT 自报执行类别。

普通数据使用 `causal_register`、`or_set`、`ordered_log` 或 issuer-local `counter`。安全状态使用 `sequenced_state`，按安全域确认命令顺序执行，不定义无序 join。转移表与 CAS 前置条件属于领域验证规则，不是另一种共享寄存器类型。

原子 bootstrap unit 内的所有 Event 共同等待该 unit 的安全决定；D 初始效果不能提前使创建整体成功。后续独立的普通编辑不继承这种等待。安全许可与普通结果 MUST 使用不同注册写入目标，D 效果不能覆盖 S 字段。

## 2. 独立接收站准入

用户 MAY 将同一生产者签名 Event 直接提交给任意合资格接收站。接收站 MUST 验证完整 AccountId、producer proof、可携带 signer evidence、注册 admission 分支、授权依赖、scope、重放及资源界限。原账号 Station 不拥有排他的首次准入权；接收站 MUST NOT 以原站在线、原站补签或原站 session introspection 作为普通提交前置条件。

Event `proofs` 恰有一个 `producer_event_proof`，其 signer evidence 解析到该实际 signing key。设备 key 不以 self-reported key 或任意 DID 当前 key 替代。genesis/recovery 按注册的独立根权力验证，不能由普通 capability 冒充。第三方存储收据不是 Event proof，不授予权限。

普通单条 Event 可直接使用 `ak.self.events.command.submit.v1` 的 `ProofAuthenticatedPublication` 分支：`event.proofs` 自身完成请求身份认证，不需要 SessionGrant、handoff、原站设备检查回调或 B 上的新账号。该分支只返回确切提交的结果，不能访问私有账户数据，不能提交安全命令或 bootstrap unit；缺证据 pending，已提供但无效的会话凭据不能被忽略后回退。

采用会话的其它消费面通过 audience、nonce 与持钥证明绑定完整 AccountId 和 scope。会话签发与更新遵守其登记的账户服务合同，不是普通 body-proof 提交的依赖。它 MUST NOT 赋予原站备份解锁、私有 push route、账户管理或未授权的数据访问。

普通数据 `auth_context` 绑定生产者 key 坐标和已确认的 `authority_refs`。接收站 MUST 验证全部相关 grant constraints、父委托链、成员、设备、安装授权和 scope。refs 可以长期缓存，MUST NOT 因 Seal 年龄、无 heartbeat 或签署者离线自动过期。显式业务授权的有效期仍执行，见 §5。

Agent state lease、controller gate attestation 和设备投影 attestation 的短 TTL 只约束需要“当前查询结果”的消费面；普通数据验证证明在其 observation 时有效后，可以缓存复用。设备的真实期限从已签 `authorization_window` 读取，Agent 从确切 key/delegation 授权读取，不能把缓存 TTL 当成资格期限。签名 issuer 及其授权证据也按相同的固定历史依据验证，不递归引入每消息在线刷新。安全操作仍执行其注册的当前状态检查。

接收站在同一事务中记录 Event、证明依赖、分类与 outbox；已知 revoke fence 与该 scope 的 live admission MUST 串行化并持久化。相同 Event 身份的重放不重复业务效果，且不能绕过 producer proof 的精确重试验证。

未知撤销允许传播窗口：分区站可按完整且未被本地已知事实否定的授权继续普通聊天。获知撤销后 MUST 立即挡受影响资格的新 live 提交。无法证明全球没有未知更新不等于缺少已引用依赖。

## 3. 历史分类与因果依赖

K 为完整已验证输入证据集合。持久分类由 K、对应安全域的确认前缀和注册规则确定，不读取本站首次到达顺序、当前墙钟或收据来源。

- pending：缺必要依赖，不能得到最终分类。
- eligible：历史授权与全部适用关闭约束成立，且执行依赖可用。
- quarantined：保留必要证据，但不进入普通业务投影、不触发新通知或副作用。
- 数学签名、绑定或结构非法：拒绝，不进入业务因果覆盖。

实际曾发生的投递、用户已看到的内容或泄露不能回滚，不属于持久 Cell 投影的收敛保证。历史回放 MUST NOT 重新触发 live 通知、自动化或密钥释放。

普通因果引用不等于执行依赖。引用/回复隔离内容不自动撤销回复者；对隔离基底应用 patch、依赖失效 grant 的操作 MUST 停止投影。有权作者可对有效基底发新的因果写修复，不按接收顺序清空历史。

比较收敛时必须比较相同可见 scope 和完整必要证据。加密正文的语义验证另外要求同样的必要密钥；Station 只能判定可验证 envelope/密文/公开依赖，不能把不可解密当成正文有效。

## 4. 授权关闭

安全撤销决定绑定目标授权实例、action/scope 和精确因果 frontier。关闭集合 C_R 为 frontier 与其完整祖先集合。该决定 MUST 由有权的安全域确认，不能由普通 Event 或任意接收站收据签发。

普通 Event 不等待关闭决定。实际撤销时汇集可获得的目标历史，不等待所有副本在线；关闭证明只承诺选定集合，不证明世界历史收齐。最大 actor_seq、wall clock、HLC 和摘要排序 MUST NOT 代替完整 Event 身份。

使用已关闭资格的 e，仅在历史授权成立且 e 属于每个适用 C_R 时保持 eligible；否则 quarantined。多个适用 cut 允许集取交集，不以较宽后继 cut 复活被另一关闭排除的事件。缺 membership 证明时 pending，不把本地查不到当成 non-membership。

新加入、重新授权与恢复产生新授权实例或 generation；旧 Event 不得换标签进入新代。父 grant 关闭按 action 传递，多个匹配 grant 的 constraints 仍全部求值。Owner transfer 不隐含整代撤权，authority reset 按其登记范围使旧 generation 失效。

离线分支中真实的旧消息也可能因未被 cut 覆盖而隔离。UI MUST 表达重分类，不能声称已证明这些消息产生在撤销之后。已知撤销禁止新 live 投递，但仍可存储和验证历史证据。

普通对象归档不产生授权 cut。Circle archive/tombstone 关闭整个有效 scope，属于安全命令。普通 archive/restore 由独立的已确认写入权限验证，restore 不要求对象先 active。

## 5. 有限期与时间证明

live gate 以可信误差边界检查显式 not_before/expires_at；时钟无法满足界限时，仅依赖该时间条件的操作 fail closed。持久历史投影不使用 receiver 当前时间，session 到期也不使历史 Event 作废。

producer created_at 不能证明期限内存在。有限期资格的普通 Event 可在期限内按本地验证暂时投递；期限结束后的稳定历史必须有该资格安全域确认的期限内存在锚，覆盖确切 Event/因果集合及有效窗。证明采用 Seal `existence_anchors` 及配置的有界时钟 prepare 规则，详见 [安全域确认](./cbs-profiles.md) §5，不能仅信任 Seal 自报时间。缺锚则待证/隔离，期后补签不能倒灌。

无到期的普通聊天不要求期限锚或周期 Seal。高风险有限期命令在安全事务内验证期限，不使用普通分区放行规则。可信时间证明不能取得时 MUST 保持失败/待证，不能降级为 producer 时间。

## 6. 因果寄存器

写入身份由 canonical Event 身份与注册 Cell target 唯一确定，业务值不是身份。写过的 null、未写入、同值多个 head、ABA 与异值多个 head MUST 可区分。不得按 `(value,from)` 去重或接因果边。

在同一已验证资格上下文内，C 为已纳入的效果身份集合，H 为仍活跃的 heads：

```text
C = C1 ∪ C2
H = (H1 ∩ H2) ∪ (H1 \ C2) ∪ (H2 \ C1)
```

后继只覆盖自己签名因果上下文中的 heads；不能吸收接收站后来看到的并发写。全值并发写保留全部 heads；patch 必须绑定确切可用基底。普通前置检查只对签名 basis 成立，不承诺两个离线写中只成功一个。

先从 K 求 eligible 效果，再合并该集合的 C/H。隔离写没有业务覆盖权，不能压掉合法旧值。资格撤回可能重新显露较早但仍合法的值；这不等于资格集合不变时因丢覆盖导致旧 head 复活。

C/H 快照 MUST 绑定资格上下文，即安全确认前缀、授权与关闭依赖和 reducer 合同。不同上下文的快照 MUST NOT 直接 join；先并 K 再重算。业务资格撤回不是普通膨胀型 CRDT delta。

一致性向量 `ak.vector.lattice.causal_register_supersession.v1` 与 `ak.vector.lattice.domain_transition_heads.v1` 验证同值身份、ABA、部分观察与领域转移的因果归约。

## 7. 其他普通状态与结构

OR-set 按精确 observed-remove dots 合并；移除只覆盖签名上下文实际观察的 dot。counter 仅按登记的 issuer-local 分片合并。ordered_log 是不可变 Event 集，canonical 排序只用于序列化/展示，不产生权限、因果或唯一赢家。

空间 parent 在各自 basis 验无环、自指、同 Realm 和可读 scope。合流后先求单一 settled parent，多值为 unresolved；然后将有向环中的 parent 边全部标 unresolved。不得生成 contains、伪装 root 或按到达顺序选边。有权后继 reparent 可修复。指向终态或不相容 scope 的边不产生有效导航，placement 从不授予读取权。

普通状态转移表属于注册领域合同。多头归档冲突保守限制当前操作面，restore 观察有关 heads 后可收敛；terminal tombstone 不可逆。时刻调度产生显式已授权后继 Event，不能按各站首次到达时间改写持久历史。

## 8. 安全状态与 Seal

v1 每个 Realm 构成一个安全域，域内身份控制、授权政策、MLS group 和硬唯一对象共用确认序列。Circle 按 scope 隔离读写权限，不另启可绕过父域撤销的安全序列。不同 Realm 独立；producer 不能另选域缩小联合约束。安全命令的 seal_basis 每域仅一个确认 head；签名 basis 必须位于该域当前确认前缀上。对命令实际读取或写入的每个安全 Cell，从签名 basis 派生 revision（从未写入为 absence），并在执行位置与当前 revision 比较；变化则持久拒绝，业务值相同也不能通过。仅无关 Cell 的后继不使命令失效；显式要求 exact frontier 的专用操作仍执行自己的强前置条件。跨域 apply 复用已 prepare 并锁定的读写状态，不把 prepare 自己推进的 Seal 当作 stale basis。

安全域按有持久投票状态与 view change 的 PBFT 确认日志执行，n=3f+1，确认 quorum=2f+1。n=1 为无副本容错部署。阈值签名本身不替代共识。签名绑定 domain/configuration/height/view/parent 与完整命令/结果，投票前持久化防双签状态；安全性以不超过 f 个故障副本为前提，活性需要最终通信和可用 quorum。

Seal 只确认该域的安全命令。每条命令在确认顺序处对实际状态执行 CAS 与领域转移；相同前置 revision 的竞争命令最多一个成功。失败命令无业务效果且结果持久，超时不等于失败。

安全 root 只承诺该域状态，不承诺普通消息完整性。普通消息不进入 delta，不产生 KeyView、普通数据覆盖 root 或周期空 Seal。普通快照同步不要求签署者在线。

配置 handoff 由旧配置确认冻结后继权，新配置取得完整前缀与未决锁后确认就绪才激活。新旧配置不得混票；旧备份不得自启平行分支。notary 资格不是 controller 权力，不能取得客户端 MLS 私钥。

`head_eq`/`head_in` 保留领域值检查；它们不携带第二份 revision 镜像。安全 CAS 的身份比较从原签名 basis 独立派生，普通数据只对自己的已签因果 basis 检查值，不获得互斥成功保证。

## 9. 跨域与不可逆效果

能共域的不变量直接共域。跨域事务在 prepare 前固定参与域全集、读写资源、内容摘要与唯一决策域，按 canonical domain ID 全序拿冲突锁。各参与域确认并持久化 prepare；只有带全部 exact prepare 证明的唯一 commit 才生效。

commit/abort 在同一决策域日志互斥，参与者仅按认证终态解锁；晚到 prepare 不重开 aborted 事务。超时不强行解锁，配置迁移不丢未决锁。锁限实际冲突资源，不笼统锁整个 Realm；决策 quorum 不可用时安全操作可以阻塞，普通聊天不加入该事务。

prepare 不释放秘密。单次 controller approval 需要唯一消费事务，绑定 nonce 与完整冻结命令，不能两站分别消费。相同 Event 去重不保证外部动作只执行一次；外部执行需幂等键/fencing 或可恢复 owner，结果不明时待核实，不能换 Event 重试另一次动作。

## 10. MLS、恢复与快照

成员或真实密钥访问改变先关闭受影响新 key-access，直到 Commit 覆盖该变化。普通消息与无关 metadata 不推进 epoch。客户端保存 exact outbound bytes 与 staged state，确认唯一 Commit 后才安装状态并交付 Welcome。超时查同一结果；明确失败才丢 staged secrets 并从真实当前 epoch 重建。

被移除者仍可构造旧 epoch 密文。已知移除的 receiver 阻止新发言，历史按关闭证明分类；未知移除的分区站仍可能暂时接纳，这是传播窗口。保留成员的合法迟到旧 epoch 历史不因 epoch 较小自动作废，不能为解密回滚密钥。

PCR/root genesis 保持注册原子起点，恢复 generation 单调且权力来自预先授权的恢复策略。旧签名备份不证明最新，缺连续证据或安全 quorum 不自证接管。稳定 Direct Conversation 全部私有状态丢失时暂停，不新建同 pair 的平行 group。

普通快照保留必要活跃值、覆盖 membership、授权/关闭证明，以及未来资格重算可能需要的旧值和认证因果关系。可用归档可以承载旧内容，但不能只存一个 root 然后声称可恢复。不能证明旧值以后无用就不得 GC；依法硬删除后明确不可恢复。

同步复用 direct push、cursor pull、exact-ID dependency resolve。证据最终送达要求存在可达持有者；恶意独占持有者不交付时不承诺活性。配额和背压不得通过各站任意截掉不同 heads 伪装收敛。

## 11. 安全状态根与序列化

`covered(S)` 是 `S.delta` 与唯一 predecessor 的 covered 集合的并集。`control_event_set_root` 仅覆盖成功安全命令；拒绝结果由 Seal 的签名 `command_results` 直接承诺。普通数据从不进入该集合。genesis 注册原子 unit 的初始 D 效果仍由完整 unit 复算，不能宣称这些数据以后必须被 Seal 覆盖。

`state_root` 的每个 leaf 恰为 `JCS({cell:<CellRef>,state:{revision_event_id:<EventId>,value:<value>}})`。成员恰为该安全域中已执行成功注册 write 的 `sequenced_state` cell；未写入者无 leaf，写过 null 者保留 leaf。revision 是最后成功写入的 Event 身份，不能用值或 Seal ID 替代。安全 register 的 value 是完整登记业务值；安全 set 的 value 是按 tag_id 排序的全部活跃 `{tag_id,value}` 项，空集为 []，不保存已移除项。安全 set 不进行离线 merge，确切 revision 已防止旧命令复活被删除的 dot。安全 log 保留按登记键排序的完整不可变 entries。上述内部表示不同于可能剥离 tags 的查询展示值；只有 D OR-set 必须保留 removed_tag_ids。D cell、未登记隐含写入、候选命令都不进入安全 root。

cell leaf 按完整 CellRef 的 Unicode code point 升序；covered digest 按 typed digest wire bytes 升序，leaf_data 为完整 typed digest 的 UTF-8 字节，保留 suite 前缀。所有树使用 RFC6962：leaf=H(0x00 || leaf_data)，node=H(0x01 || left || right)，空树=H(empty)，单 leaf 为其带域分隔 leaf hash，递归在小于长度的最大 2 的幂处分割。根的 suite 来自已验证安全配置，不从待验证对象自报摘要推断。

inclusion 使用 index/tree_size/audit path；non-membership 使用认证相邻 leaf 与端点范围证明。只持有单个 Event inclusion 不证明它仍是当前 revision。投票 replica 必须有验证其安全命令所需的完整权限与材料并重放归约；无法验证不得投票。非投票 receiver 可以验证已认证配置 lineage、2f+1 commit certificate 和其有权读取的确切 Cell/历史证明，依赖同一 quorum 的故障界限，不必下载不相干私有 scope 的正文或完整控制历史。任意 service 自签 root 或未验证配置不能替代这条认证路径。普通 snapshot 的 state_digest 与本安全 root 是不同集合，不得逐字比较后声称前者已被 Seal 认证。

## 12. Notary 与 reducer 配置

每 Realm 的 `ak.component.notary.v1` 是 `sequenced_state` singleton，genesis 由 realm.create 的显式配置写入；后继仅 realm.notary 和唯一 handoff 生效。owner transfer 不隐含 notary change，notary change 不授予 controller 权力。恢复/旧备份不产生新的自授权 lineage。

`ak.component.realm.reducer_profile.v1` 同样为安全 singleton，genesis 写入明确 active profile，后继仅 realm.upgrade。前置绑定当前 revision 与 source profile，target 和 source→target edge 必须已注册。竞争升级至多一个成功，不产生控制 Bottom。旧数据按其签名授权上下文中的 reducer 合同解释，安全命令在其确认顺序处解释；接收站不得用 latest 软件默认静默重写历史。

## 13. Hash suite transition

`ak.realm.digest_suite_transition` 在唯一安全序列确认，并且是该 Seal 唯一成功命令。payload 的 from suite 等于 predecessor live suite，to suite 必须 active 且不降级。Transition Event 和其 receipt 保留原 suite；Transition Seal 及后态 root 使用新 suite，`previous_state_root` 使用旧 suite 重算前态，`previous_digest_algorithm` 必须匹配 from suite。typed 历史引用不重哈希；安全 covered 树按 §11 以完整 typed digest 字节构造。

transition 的 snapshot commitment 按原 suite 验证其声明的确切数据集合；它不要求全网普通消息停止或完整收齐。普通离线 Event 使用自身已签授权上下文中有效的 suite；与升级并发的合法旧 suite 数据仍按原合同验证，不能因接收站先见升级便拒绝。安全后继只用新 live suite。genesis 的 realm.create 使用固定 SHA-256 身份桥接，其余 bootstrap 和首 Seal 使用创建意图声明的 suite。

`ak.vector.hash_transition.dual_root_recompute.v1` 与 `ak.vector.hash_transition.fail_closed.v1` 覆盖前后双 root、错 suite、错 snapshot、降级、错误前态和延迟旧授权数据分支。`ak.vector.identity.device_reanchor.v1` 与 `ak.vector.identity.root_anchor_exclusivity.v1` 仍要求唯一已授权恢复起点，不能借 suite 更换自启身份谱系。

## 14. 控制面 Control Proposal Ack 与 inclusion obligation

除 [`cbs-profiles.md` §4](./cbs-profiles.md) 定义的 authority-authored human
self-principal PCR Move 外，控制面 pending Control Move MUST 在 `proposal_intake_sla_ms` 内得到签名
Control Proposal Ack（控制提案签收）或签名 rejection。该例外已由 current accepted device 作为
exact Move 的 author/authority，不产生第二份 Ack 或 decision deadline，但仍必须进入 pending Control
index，并且只有 accepted successor Seal 能使其生效。**`ak.device.revoke` 明确不属于此 Ack-less 例外**：为使可验证 `signed_reject` 始终具有唯一 `proposal_ack_digest`，每个 accepted revoke 都 MUST 将 canonical Ack 与 accepted Event、derived exact device/generation record、pending index 原子持久化；无有效 Ack 时零写入。`proposal_intake_sla_ms` 的权威字段是
[`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的 `proposal_intake_sla_ms`（integer，毫秒，`default 86400000`（24h），`minimum 0`，v1 wire hard `maximum 86400000`），与 `seal_compaction_max_interval_ms`（§6.2）同量级；其 wire 上限登记于 [`scalability-constraints.md`](../conformance/scalability-constraints.md) §4。SLA 计时以 notary 签署的提交时间为准，不用本地接收时间。

**Proposal 有界决议（normative）**：`proposal_intake_sla_ms` 只管「多久确认收到」。authority
接受 proposal ingress 后签发的 Ack 还 MUST 承诺：

```text
proposal_digest, received_at, decision_due_at, absolute_due_at,
defer_count=0, authority_set_ref, authority_acks[]
```

机读合同为
[`control-proposal-decision.schema.json`](../../artifacts/schemas/control-proposal-decision.schema.json)。
`ak.self.events.command.submit.v1` / `ak.peer.events.command.submit.v1` 对 accepted 或 byte-identical
duplicate Control Move MUST 在 `EventsSubmitOutcome.control_proposal_acks[]` 返回已持久化的
原 Ack；authority-authored self-principal PCR Move 必须省略该数组项，DataEvent 也不得进入该数组。
重复提交不得重签或延长任何 deadline。
Realm 的 `proposal_decision_window_ms` 给出首个决议窗口（default 30,000ms，协议硬上限
24h），`proposal_absolute_deadline_ms` 给出从 signed `received_at` 起不可延长的绝对窗口
（default 90,000ms，协议硬上限 72h），`max_proposal_defers` 给出 defer 次数上限
（default 2，协议硬上限 2）。profile / deployment MAY 声明更短窗口或更少 defer，
不得放宽协议硬上限。`ak.realm.create` 与任何更新这些 Realm 参数的 Control Move 在写入前
MUST 校验 `proposal_decision_window_ms <= proposal_absolute_deadline_ms`；违反时整个 Event
MUST 以 `schema_violation` 拒绝。若 `max_proposal_defers > 0`，两者 MUST 严格小于，以保证
至少存在一个严格递增且不晚于 `absolute_due_at` 的 defer deadline；两者相等时
`max_proposal_defers` MUST 为 `0`。该判定基于签名 payload 与冻结 basis，是所有 reducer
必须执行的确定性跨字段校验。

**外部 authority Ack set（normative）**：当接收 Event 的 Station 不持有当前
notary authority，或单个 signer 不能满足 配置 quorum 时，它不得用服务密钥代签。
proposal author 必须对每个真实 authority 使用
`ak.self.control_proposal_acks.command.issue.v1` 的 typed request；本地 Agent/device signer
使用完全相同的 request、canonical digest 与 outcome transcript，只省略 HTTP hop。每个
authority 独立验证最终签名 Event、genesis/basis 当前 notary policy、
Realm、`proposal_digest`、signer membership 与 deadlines，随后签发一次
`ControlProposalAuthorityAck`。同一 `(proposal_digest, authority_set_ref, verification_method)` 的
byte-identical retry MUST 返回首次持久化的 authority Ack；不同 Event bytes、authority set
或时间字段 MUST `duplicate_conflict`，不得重签延长期限。

typed request 必须携带显式 `publication_mode=online|delayed`。`online` 分支 MUST 不携带
`authorization_lease`，authority 按当前 accepted basis、当前权限与最终签名 Event 重新求值；它不产生
离线窗口。`delayed` 分支 MUST 携带 `authorization_lease`，并独立验证 lease 的 basis、actor/device、
scope/action、issuer、有效期及与 exact Event 的绑定。字段组合不匹配、lease 无效或过期时 MUST 拒绝，
不得删除 lease 或替换 mode 后在同一次请求中降级为 online。request canonical digest 覆盖 mode、Event、
lease（若有）与 proof bundles；HTTP session/DPoP 或 service signature 认证该请求。authority Ack proof 只覆盖
下述 immutable Ack body 和 proposal identity，不替代 request authentication，也不把 lease 权限扩展到
Ack deadline。transport outcome 丢失后相同 canonical request 返回首次持久化 Ack；调用方重新在线求值
必须显式构造新的 `online` request，authority 仍按当前权限校验，且命中同一 proposal/authority 的既有
Ack 时不得重签或延长期限。

member签名 transcript 是
`JCS({context:"ak.control_proposal_authority_ack_proof.v1",
payload_digest:SHA-256(JCS(authority_ack_without_signature)),verification_method,
created_at:received_at})`；proof的`payload_digest`与`created_at`必须逐字匹配，禁止签任意摘要后
只比较字段。每个member的`decision_due_at`必须恰等于
`received_at + proposal_decision_window_ms`，`absolute_due_at`必须恰等于
`received_at + proposal_absolute_deadline_ms`；所有加法按UTC instant计算，溢出或超协议上限拒绝。

author 将互异 authority Ack 按 `signature.verification_method` canonical 升序组装为唯一
`ControlProposalAck`。receiver 必须：

1. 逐项重算 member statement digest并验真实签名，按 verification method 去重，只把 genesis
   或 Event basis 解析出的当前 authority member计入 quorum；
2. 要求所有 member 的 Realm、proposal digest与authority-set ref逐字一致，且
   `max(received_at)-min(received_at) <= proposal_intake_sla_ms`；
3. 令set级 `received_at=max(member.received_at)`、
   `decision_due_at=min(member.decision_due_at)`、
   `absolute_due_at=min(member.absolute_due_at)`，并要求
   `received_at <= decision_due_at <= absolute_due_at`；set级字段与该计算不一致即拒绝；
4. 按精确 quorum 配置验证 2f+1 个不同 voter；同域不接受多 lineage 拼接；
5. 把canonical Ack set、accepted Event、pending index与wakeup原子提交。closed anchor Event
   不能因无 `seal_basis` 跳过该 pending index；覆盖它的 accepted Seal 必须在同一原子事务写入
   Seal lineage / cell effects 并把每个 `delta[]` digest 从 pending 标记为 sealed，任一 digest
   不存在时整笔 Seal 提交回滚。duplicate Event
   返回byte-identical Ack set；Ack集合、成员时间、顺序或签名不同均不得覆盖首次事实。

`EventInitialSubmission.control_proposal_ack` 与
`EventFederationSubmission.control_proposal_ack` 是该证据的唯一输入位置，只允许 Control
Move；DataEvent携带时必须 schema/admission拒绝。`cbs_proof_bundles[]`只补basis closure，不得
承载或替代Ack。收集未在共同窗口内达到quorum时，本proposal永久不能以零散authority Ack入库；
producer必须author并签署新的Control Move Event，authority不得为旧digest重新计时。
`proposal_ack_digest = SHA-256(JCS(the complete canonical ControlProposalAck including
authority signatures))`；同一有效authority集合只有一种排序和一种digest。
该外部成员签发、共同窗口、quorum、duplicate/equivocation与decision-set binding由
`ak.vector.cbs.external_control_proposal_ack_quorum.v1`固定。

每个决议窗口到期前，authority MUST 产生以下之一：

1. proposal digest 被 accepted Seal 的 covered set 覆盖；
2. `signed_reject`，携带 closed `reason_code`；
3. `signed_defer`，携带 closed `reason_code`、严格递增且不晚于 `absolute_due_at` 的新
   `decision_due_at`，并把 `defer_count` 恰好加一。

`signed_reject.reason_code` 的封闭集合为 `capability_denied`、`cas_conflict`、
`policy_denied`、`schema_violation`、`superseded`；
`signed_defer.reason_code` 的封闭集合为 `dependency_missing`、`quorum_unreachable`、
`temporarily_unavailable`。实现不得接受
未登记字符串，也不得把 defer 原因用于 terminal reject。

每个 defer MUST 引用完整 canonical Ack-set digest，绑定同一 proposal、Realm 与 authority
set，并由当前 Ack quorum 对同一 decision payload 产生按 verification method canonical
排序的 `proofs[]`。`decision_digest=SHA-256(JCS(decision_without_proofs))`，每个proof的
`payload_digest`必须等于该值、`created_at`必须等于`decided_at`，签名transcript固定为
`JCS({context:"ak.control_proposal_decision_proof.v1",payload_digest,
verification_method,created_at})`；proof不得跨 Ack set、decision kind 或 defer count拼接。它还必须
原样保留 `absolute_due_at`。`signed_reject` 与 `signed_defer` 是可验证的 authority
决议，**不是** proposal 被接受，也不提供 finality；只有第 1 项中的 accepted Seal 提供
控制面 finality。该义务不得命名为“接受 SLA”，也不得声称 deadline 本身提供 finality。
receiver 本地收到 Event、Ack、decision 或 Seal 的时间 MUST NOT 进入规范计算。

签名 decision 的标准提交面是 `ak.self.control_proposal_decisions.command.submit.v1`，标准观察面是 `ak.self.control_proposal_decisions.read.get.v1`；机读 request/outcome 位于 [`control-proposal-decision.schema.json`](../../artifacts/schemas/control-proposal-decision.schema.json)。submit receiver MUST 先从 durable store 读取 accepted proposal 与首次 canonical Ack，重算 `proposal_ack_digest`，再验证 exact Realm/proposal/authority set/deadline/defer chain/quorum 并原子写 decision；caller 不能随请求创建或替换 Ack。read 只投影 canonical Ack、verified decision chain 与 covering Seal，不能生成 decision 或清 pending。对 `ak.device.revoke`，`signed_reject` 通过 proposal Event 与 reducer-derived `ak.schema.device_revocation_state.v1` record 传递性绑定 exact device/generation；只清该 proposal，其他同目标 pending record仍保持 gate。terminal reject 必须对应同一安全序列中该命令的 rejected outcome；安全日志唯一终态先持久化再对外签发 decision。commit/reject 不能由不同接收站的先到顺序竞争，exact retry 返回同一持久结果。

**逾期是治理健康 fault，不改变密码学接受结果（normative）**：在当前
`decision_due_at` 前没有上述三者，或到达 `absolute_due_at` / defer 上限后仍未 include /
signed-reject 时：

1. Realm governance health 投影进入 `degraded`，记录 proposal digest、Ack、当前
   decision chain 与 deadline；
2. 产生稳定诊断 `control_proposal_decision_overdue`，并允许形成 censorship evidence；
3. 依赖该 pending Move 的 authoring/readiness，以及无法证明旧授权在 pending revoke /
   ban / notary change 下仍安全的写入 MUST fail closed；
4. 与该 Move 无关、仍由 accepted 旧 Seal 合法授权的 DataEvent MUST NOT 被全局误伤；
5. 后来抵达且按 Seal 规则有效的 Seal仍正常 accepted；fault 作为可审计证据保留。

不得因“迟到”把同一 cryptographically valid Seal 在不同 receiver 上分成 accepted /
rejected 两种终态。协议不能强迫停机或恶意 authority 接受 proposal；它能保证的是合规
authority 给出有界、可验证的决议，并为失约提供 health/fault/recovery/rotation 入口。
上述 Ack、两次 defer 上界、绝对期限与迟到 Seal 规则由 conformance vector
`ak.vector.cbs.proposal_bounded_decision.v1` 固定。

`ak.self.seals.read.frontier.v1` 与 `ak.peer.seals.read.frontier.v1` 的 Realm current Seal discovery MUST 返回同一 closed
`RealmSealFrontierView`：`seal_basis.leaves[]` 恰含该 Realm 的一个唯一确认 head。该 View 按 `kind, realm_id, seal_basis, live_digest_suite, governance_health, observation_coordinate` 顺序携带字段。
`live_digest_suite` MUST 来自 exact `seal_basis` 的已验证 joined effective state，包含已经接受的 digest-suite transition；
不得从 Seal ID 的哈希前缀猜测。`observation_coordinate={service_id,sequence,observed_at}` 中的 current 仅表示该 service
在该坐标的 durable view，不是 global wall-clock latest。Peer 响应的 Event `heads[]` 不能替代 Seal leaves。
自己的 authenticated Account Station 负责验证历史与 已确认安全状态与 roots；客户端核对 Realm、会话和本次请求绑定后
直接使用该 View，不得为订阅、签署 basis 或取得 digest suite 拉取闭包、重放历史或重算 roots。
Peer server 对 foreign governance 仍独立解析和验证；上述 self 信任不得扩展到任意 remote service 或代替 E2EE 检查。
服务结果不能被当成某个 Seal 自身签署了额外字段。

`RealmSealFrontierView.governance_health` MUST 从已验证的
Ack / decision chain 与 accepted Seal covered set 派生；pending 明细最多返回 128 项，
按内嵌 Ack 的 `(control_proposal_ack.absolute_due_at, control_proposal_ack.proposal_digest)`
canonical 升序。每个 pending 项只携 `control_proposal_ack`、`decisions[]`（仅 `signed_defer`，
按 `defer_count` 升序）与 `decision_state`，不镜像 `proposal_digest`、`absolute_due_at`、
`defer_count` 或当前 `decision_due_at`：`proposal_digest` 与 `absolute_due_at` 取自
`control_proposal_ack`（全链原样保留）；`defer_count = decisions.length`；当前决议期限即 DTO
语义中的 `current_decision_due_at`，对应 ack / decision 的字段名 `decision_due_at`，取
`decisions[]` 末项的 `decision_due_at`，无 defer 时取 `control_proposal_ack.decision_due_at`。
`pending_proposals_complete` MUST 显式说明该数组是否包含此 observation coordinate 的全部
Ack-required 未决项；超过 128 项时只返回 canonical 前 128 项并置为 false、`status=degraded`。
这是有明确不完整标记的诊断样本，MUST NOT 被当成安全事项的完整性证明。consumer MUST NOT
根据未出现于样本中的 digest 推断不存在 pending revoke / ban / notary gate；服务 MUST 从完整
持久记录按请求的真实授权依赖执行 gate，无法证明无影响的操作仍 fail closed。独立验证过的
`seal_basis` MUST NOT 因诊断样本超预算而不可读；recovery 与调度 MUST NOT 以 health=healthy
作为启动前提。Ack-less 项没有决议时钟；不能为使样本完整而补造 Ack。

`status` 仅表示当前决议可用性：样本完整且所有未决项均未 overdue 时为 `healthy`，否则为
`degraded`。healthy 不等于没有 pending 收紧门，也不等于 MLS 私钥与 Welcome 已恢复。
迟到但合法的 Seal 覆盖 proposal 后，该 proposal MUST 从 pending 集合移除，历史 deadline fault
仍 MUST 保留可审计的原 Ack、完整 decision chain 与 covering Seal。历史记录不再内嵌于
`ControlGovernanceHealth`，MUST NOT 决定当前 status，也 MUST NOT 因数量超过 128 而阻断 frontier。

历史读取复用标准 Event query 的可续接分页和 exact control-proposal decision read：获授权的
审计者枚举可见控制 Event，按其完整 digest 读取原 Ack/decision/accepted_seal_id，再 resolve 并
验证 covering Seal 的签名 `sealed_at` 与 covered set。每段 signed-defer 的签名时间是否满足
前一期 deadline、terminal decision 或 covering Seal 是否迟到，由原签名材料重算；MUST NOT
用当前墙钟给早已按期终结的事项补造历史 fault。Event query 枚举的是已接受历史，尚未接受或
已拒绝 proposal 的持有者复用原 Ack 的 digest 做 exact read；这不是面向任意用户的全 Realm
待办枚举授权。持久问责材料 MUST 按既有审计与授权规则可得；不得为了恢复 healthy 删除记录、
清除未决 revoke、静默换 Ack authority 或截断签名链。

### 14.1 持久恢复与积压终结（normative）

在当前合法签发或恢复权威、必要持久材料仍可用、故障停止、已准入积压有限且调度公平的条件下，
实现 MUST 能继续处理受支持控制操作。恢复首先核对持久 frontier、签名位置、原 Ack/decision/
Seal 与当前 authority/fence；旧进程或轮换前 key 的重新上线不恢复已失去的签发资格。
同一 voter 的全部 worker MUST 共用持久 frontier CAS 与原子接受边界。lease 超时只是本地
调度条件，不授权并发控制谱系；崩溃后先查原 durable outcome，未知结果只精确重投或查询。

已 sealed/rejected 的请求返回原结果；旧 basis 或超出 replay window 的请求经当前已登记的
合法决议路径终结，不能改写原签名 basis。暂缺 Ack/依赖、损坏记录与已验证不合法的请求 MUST
区分：隔离单项调度故障、保留安全 gate 与可诊断恢复入口，MUST NOT 伪造 signed-reject。
同 Realm 已证明无依赖的就绪工作和其他 Realm MUST 获得公平处理机会；扫描预算不是队列总量
上限，重复重启或固定读取第一页不能使已准入义务永久饿死。安全收紧与合法 recovery 要有处理
机会，但不得违反 barrier 排批或整张 Seal 的原子验证。

合法准入串行化互斥 CAS/领域状态 请求：可以排批、拒绝旧 basis、由有权 author 读取新 heads 后
重新签署，但 MUST NOT 把普通请求竞争制造成 accepted Bottom。新 Event 自动重试只有在该
action 的语义、当前权限、目标身份/incarnation 和用户意图均仍成立时才允许；未知语义、值替换
及外部副作用不得由服务默认覆盖。自动重试不是修改签名事件的通道。原意图已由其他合法操作
满足时可停止本地动作，但不能声称原 Event 已 accepted。

恢复投影 MUST 用同一已验证历史重建 唯一 revision、结果与 roots；缓存损坏产生的假 Bottom
不能通过另签业务命令掩盖。轮换后的旧 Ack 仍绑定原 authority set；当前 signer 不能用新
key 冒签旧 obligation 的 reject。若没有现行 covering Seal/terminal decision/recovery 的合法
处置路径，必须明确报告所缺权威或材料，不能把无限 defer 宣称为恢复保证。

**compaction 不承担终局（normative）**：首个 Seal **MUST NOT** 是 compaction Seal；
compaction 前的普通 signing pass 出现任何硬错误时 compaction **MUST** 停止并上浮；
compaction 成功 **MUST NOT** 作为普通 pending Move 已按期取得 proposal 决议的替代证据。

无声遗漏构成 censorship evidence：

```text
CensorshipEvidence {
  control_proposal_ack
  seal_ref
  control_event_set_root_non_membership_proof
  missing_rejection_or_defer_proof
}
```

Censorship evidence 是普通 Control Move，event kind 为 **`ak.notary.fault.censorship`**（payload schema：`notary_fault_censorship_payload`），写入 `ak.component.notary_fault.v1` cell。它**不**自动罢免 notary：reducer 记录审计 fault 并 MUST 触发治理告警。



## 15. Actor 分叉与内容地址碰撞

普通 actor 同位置 sibling 按已验证因果身份保留，执行依赖与授权分类仍逐个验证。超过登记资源界限或属于领域禁止的 sibling 集时，完整争议 scope 隔离；不能只保留先到者。安全命令竞争由唯一确认顺序及 revision 守卫处理，不产生安全状态 join。

相同 EventId 的不同 canonical bytes 是内容地址碰撞，必须保存完整 variants、隔离普通效果并停止依赖该碰撞的安全操作。已经确认的历史 Seal、原始 bytes 和结果不可追溯改写。`ak.fork.resolution` 是登记的安全命令，按完整 subject 与原始 variant bytes 验证 `canonical_winner` / `void_all`；对应 resolution Cell 必须未写入，`head_eq:null` 加确切 revision 防止二次裁决。它不授权任意 Cell reset，不修复已破坏的 quorum 假设，也不通过合并多个 Seal 选出安全 lineage。

collision 的 winner_index 只定位 `conflict_evidence.variants` 中完整 canonical bytes；不能用碰撞的 digest、长度或另一种临时摘要代替。已确认 canonical_winner 是相同 ID 整组隔离的唯一例外：待准入 bytes 必须与确切 winner 相等，并重新验证结构、Realm、suite、完整 AccountId、签名和授权；不得把一个变体的签名直接赋给另一个变体。复用历史 proof 集时也必须对 winner bytes 重新验签。loser 只保留取证，不参与 D 投影。

后继 resolution 只改变其后的有效资格与执行 gate，不能重算已经确认的旧结果或越过未解决碰撞做 compaction。需要当前状态修复时，由有权主体在该已确认裁决之后提交明确的领域安全命令；不存在自动恢复被隔离权限的机制。peer 清除 stale 还须完成 federation 登记的 exact-scope alignment，不能因本地已见裁决或全局 root 相等便替 peer 作证。
