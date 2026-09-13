---
title: 安全域确认与跨域事务
status: candidate
normative: true
stability: v1
updated: 2026-09-13
---

本文规范关键字按 [规范语言](../conformance/normative-language.md) 解释。

## 1. 安全域与配置

v1 的安全域标识就是 RealmId。一个 Realm 的权限、成员、硬唯一槽位、密钥访问和 MLS 安全状态共享一条确认序列。Circle 仍按 scope 隔离授权和读权限，但不产生另一条可能与父 Realm 撤销并行生效的安全序列。不同 Realm 的确认独立。普通业务值不进入安全序列的 `delta/state_root`，但 ordinary Event 身份按 §5.4 由同一 Seal 序列周期收录并关闭数据基准。不能根据 Event 名称推测是否需要安全执行，必须对 canonical registry 的有效 write 求值。

`notary_configuration` 是 closed `{signer, max_clock_error_ms}`；signer 是唯一冻结 descriptor，没有配置 kind、签署者数组或容错参数。`notary` 保留为治理签署权的机器名称，不表示另一个 service_kind。配置由 `realm.create` 或已确认 `realm.notary` Event 身份引用。每个 Realm 同一阶段只有一个治理 Station 执行安全命令、确定顺序与耐久结果；其它 Station 是该 Realm 的治理结果消费 Station。一个 Station 对不同 Realm 可以承担不同职责。

**身份签署权与执行职责。** collaboration/direct_conversation 的 signer 是经已接纳部署 policy 明确选定的治理 Station 服务身份，默认是创建者 Account Station。principal_control、agent_control、applet_managed_control 的 Seal signer 继续由各自已登记的 device/controller/root 授权规则确定；治理执行由该控制 Realm 对应的 Account Station 承担。这里的单 Station 执行不把用户密钥交给 Station，也不以服务签名替代该唯一持钥签名。root/controller 的 Event producer proof、恢复批准及 possession proof 独立保留。身份控制 Realm 不通过 ordinary genesis-notary 查询改写 signer 来源。

治理 Station 完整验证原始输入、授权和状态；持钥方只对该次已认证准备的 exact body 签名，按既有身份规则核对自己的意图。签署与执行可以是不同职责，不能因此形成第二条确认序列或额外通用共签证书。签名输入与原子提交遵循 §2–§3。

治理方不可用时该 Realm 的安全变更暂停。恶意治理方或被攻陷的唯一签署者可能谎报或分叉；验签证明来源与内容绑定，不证明执行诚实，也不提供 Byzantine 容错。已知冲突必须停止受影响安全域并保留证据；不得自动选主、按时间/digest 选胜者或用旧备份自启 lineage。普通数据继续按原有授权、撤销传播与 E2EE 规则处理。

## 2. 提案、执行和确认

Seal 的 `realm_id/configuration_ref/notary_seq/predecessor_ref` 唯一绑定安全位置。genesis 高度 0 且 `predecessor_ref=null`；其它高度必须携同 Realm 唯一已确认 predecessor，且高度恰为 predecessor 加一。Seal 的内容地址输入是去除 `id` 与 `notary_signature` 后的完整 canonical body；更改 command 顺序、结果、前态、配置或任何关闭证据都会改变 Seal digest。`notary_signature` 是一个 closed JWS signature；签名 payload 恰为 `JCS({context:"ak.seal.commit.v1",seal_digest})`。配置与位置已经由完整 body 绑定，不重复携带。没有 view、阶段票据或签名数组。

`command_results` 给出原子 command unit 的实际执行顺序。每项 `unit_event_digests` 是已登记 unit 的确切成员顺序，`event_digest` 等于首成员；单命令为单元素数组。bootstrap/cascade 只能使用各自已登记的 unit 验证器，任意批次不能自行组成 unit。整个确认历史中同一 Event 只进入一个 unit。治理 Station与选择独立重放的审计者必须取得并验证所有命令的原始 Event、依赖与结果；治理结果消费 Station按 §9 认证所需结论，不重算已经确认的历史执行。`result_digest` 按 seal schema 的封闭投影从实际注册写入后的完整状态与 reason_code 重算，禁止哈希任意 HTTP response。失败 effects 为空；成功 effects 按 CellRef 排序，每个触及 Cell 只保留执行完该 unit 全部有序 write 后的一个完整 state，包括 bootstrap D 初始值。每个 effect.state 使用该 Cell 固定模型在 snapshot chunk schema 中的完整 state 形状：S 为 `{revision_event_id,value}`，D causal_register 为 `{covered_event_ids,winner:{event_id,depth,value}}`，其它 D 模型保留完整集合、墓碑、条目或 issuer 分量；不得把 D 改写成单 revision 或仅业务显示值。封闭摘要输入见 seal schema 的 `command_result_digest_input`，同形空数组仍由 canonical family 唯一解释。命令在其顺序位置重新执行授权、确切前置 revision、领域约束和全部写入。`delta` 恰为本 Seal committed units 内所有 security 成员摘要的 canonical sorted set；bootstrap D 成员共享原子 outcome 但不进入该集合；普通数据与失败命令不在其中。

没有有效 security write 的普通命令禁止成为 `command_results`。bootstrap 的 D 初始值作为已登记安全创建事务的原子结果存在，不能把后续普通更新借此升级为安全命令。普通 live 提交不得等待新的 Seal、KeyView 或业务值 root；它绑定一个既有开放 `data_basis`，由治理收录 outbox 异步进入后续数据 publication Seal。

相同基底的竞争命令最多一个通过身份前置条件。相同业务值、释放后重新成为 null、重复 epoch 号不能替代 revision 身份。拒绝无业务效果；exact retry 返回已持久结果。超时只表示结果未知，调用者查询同一命令，不产生另一个可能重复执行的命令。

## 3. 单写者耐久确认

治理 Station MUST 以耐久排他/fencing 取得该 Realm 唯一执行权，在同一数据库事务内锁定当前 confirmed predecessor，完整重验命令与读写依赖，并构造唯一候选 body。任何签名在对外可见之前，必须先耐久记录 `(realm_id, configuration_ref, notary_seq, predecessor_ref, body_digest, exact_body)`；同一位置不能签第二个不同 body。准备记录不构成 accepted 状态，也不开放权限。

持钥签署完成后，exact Seal、命令成功或拒绝的终态、全部 Cell effects、confirmed head、去重索引和 outbox MUST 原子提交。对外发布只能读取已经提交的 outbox。进程崩溃后先恢复候选与已确认位置，再重试相同 bytes；不能通过超时、换进程或回滚备份遗忘已经发出的签名。签名成功而数据库提交结果未知时必须先查询耐久事务结果，不能重新求值并签另一个 body。读取、幂等重试与恢复均以同一 durable ledger 为准。

同一业务前态的竞争命令按当前 revision CAS 至多一个成功；失败不写业务状态。单机排他、并发事务隔离、耐久 outbox 与 fencing 是实现义务，不是公开 prepare/commit 协议。v1 不接受多签配置、共识投票、prepared/view-change/new-view 载体或静默单签 fallback。

## 4. 授权轮换与顺序迁移

`ak.realm.notary` 必须按变更前 accepted policy 的真实 controller/业务授权规则签署并执行，不能只凭新 Station 自报身份。其最后 Seal 由旧 signer 签发，冻结 exact 新配置及旧配置最后可写位置；该事务完成后旧执行者拒绝任何后继业务写。正常 service key rotation 也走同一流程，不用当前 DID key 追溯改写冻结历史。

后继治理 Station 必须取得、验证并耐久保存完整已确认 prefix、终态去重记录、尚未交付 outbox 与该冻结边界，才可从唯一 predecessor 签发下一高度。未决本地事务必须先完成或回滚；不能携部分多域结果交接。交接证明使用 §9 的单签精确事实，不另造 ready 票据。旧方冻结后新方未就绪期间安全变更暂停，不承诺无中断迁移。

身份控制 Realm 的正常轮换还须满足其 device/controller/recovery 规则。Account/PCR 不能借迁移更换 AccountId 的 Station 或复活永久失效 Account；同一 Station 身份的耐久运维恢复不等于跨 Station 账号迁移。旧权威及连续历史不可恢复时不得自封新权威；多节点故障切换与无旧权威的恢复不在 current-v1 内。

## 5. 授权关闭与有限期

### 5.1 精确依赖坐标

`authorization_closures` 每项按 `command_event_id, dependency_kind, authorization_event_id, generation_event_id, scope_ref, actions, frontier` 绑定本 Seal 成功关闭命令。`dependency_kind` 是封闭判别，不能省略、使用扩展值或根据 Event 名称猜测。唯一机器真源为 [contract registry 的 authorization_dependency_registry](../../artifacts/registry/contract-registry.json)：kind、允许的 scope kind、确切 action 集合、来源与关闭规则一并登记；schema 与共享类型从该表生成约束。actions 必须是非空、canonical 排序去重的已登记 action 子集，拒绝通配、未知 action 及不合 kind/scope/action 的组合。表内 action 集合只是结构上界，不自动授予动作或宣称所有 Event 都使用该依赖。

历史授权求值器 MUST 从原 Event 绑定的已认证历史状态展开每个**实际必需**的依赖，使用与 closure 相同的 `(dependency_kind, authorization_event_id, generation_event_id, scope_ref, action)`。每个 action 分别求值，多个适用关闭集合取交集。不能以另一条未被采用的可选授权路径补救原 Event 已关闭的依赖，也不能把所有可选路径都当成必需依赖。generation 是确切建立该开放区间的已确认 Event，不是业务整数、当前 Cell revision、时间或本地计数器。整数代际与 Event 的对应必须由连续已认证的状态变更证明；禁止伪造 EventId。

scope 指**依赖自身**的登记范围，closure 所在 Seal 的 Realm 必须是其权威所属 Realm。PCR device/grant/Contact 依赖指向原 PCR，不枚举消息可能流向的业务 Realm；Circle membership/lifecycle 指向确切 Circle；Sidecar 不产生第二份成员名单。`realm_genesis` 不可作为依赖 scope，必须在验证真实 genesis 后展开其 RealmId。跨 scope 使用仅由实际授权规则展开，不能凭 id 前缀、接收 Station 或当前显示关系推测覆盖。未获授权的 PCR、Circle、Sidecar 原文和 frontier 不能因证明依赖而被公开；按 §9 认证获准披露的确切事实。

### 5.2 来源与关闭边界

下表的 A/G 分别指 authorization_event_id / generation_event_id，所有起点及关闭都必须是确切已确认成功的登记转换。

| dependency_kind | A / G | 关闭与必要边界 |
| --- | --- | --- |
| `device_generation` | PCR create / create 或建立所用 generation 的 reanchor | 下一 reanchor 关闭旧代；归属 PCR，不依赖原 Station 在线。 |
| `device_authorization` | exact device.authorize / 同一 Event | revoke 关闭所观察的该授权实例；另保留 device_generation。 |
| `agent_key_authorization` | exact agent.key.authorize / 同一 Event | revoke 或显式 supersedes 关闭该实例；不能把同 key bytes 当作同实例。 |
| `capability_grant` | exact grant / 同一 Event | revoke/relinquish；递归展开实际父 grant 及根代，不记录无关的可选 grant。 |
| `realm_authority_generation` | Realm create / create 或 authority.reset | reset 关闭旧根代；owner transfer 不关闭它。participant baseline 不依赖根代。 |
| `realm_controller_assignment` | Realm create / create 或 owner.transfer | transfer 只关闭旧 controller 的直接授权任期，不关闭任期内合法签发且尚有效的 grant。 |
| `member_join` | 真正建立 join 的 member.state、circle.member.state、invite.accept 或登记 bootstrap member Event / 同一 Event | leave/ban/级联关闭确切 join；rejoin 是新实例，旧 Agent/controller join binding 不复活。 |
| `agent_active` | Agent PCR create / create 或实际 resume | pause/deactivate 关闭 active 区间；相同 key 的 resume 开新区间而不更换 key authorize 起点。 |
| `realm_unarchived` | Realm create / create 或实际 restore | archive 关闭；仅适用于规则要求未归档的 ordinary action。 |
| `realm_unfrozen` | Realm create / create 或实际 unfreeze | freeze 关闭；与 archive 区间独立，保留正式例外动作。 |
| `realm_nonterminal` | Realm create / 同一 Event | 第一次 tombstone/destroy 关闭，不可重开；继承到依赖它的 Circle/Sidecar，不合成子对象写入。 |
| `circle_active` | Circle create / create 或实际 restore | archive/tombstone 关闭当前开放区间；父 Realm gates 独立。restore 不重建未被移除的 membership/MLS leaf。 |
| `accountability` | 实际建立 active accountability 值的 identity.accountability_grant 或 agent.provision / 同一 Event | 实际 revoke/replacement 关闭；Actor Profile 声明不授权。 |
| `applet_registration` | 实际建立 accepted registration 实例的 applet.registration / 同一 Event | security registration 实例被替换时关闭；连续重申同 epoch 与全部 security bindings 不开新代，替换离开再改回则是新实例。 |
| `mls_leaf` | creator 的 Genesis，或确切 durable Add proposal / Genesis，或真正消费 Add 的 Commit | 真正消费 Remove 的 Commit 关闭该 leaf 实例。无关 Commit/Update 不开新代；同 index/key 的 Remove+Add 仍是新实例。 |
| `contact_direction_scope` | issuer 该 round 的真实 request/acceptance 起点 / 起点或将所需 Contact scope 从无改为有的 scope_update | 删除该 scope 或 round terminal 关闭。保留的 scope 不换代，重新加入的 scope 开新代；双方方向分别验证。 |
| `consent_grant` | 实际使用的 ConsentGrant / 同一 Event | ConsentRevoke 关闭确切 observed grant tag。仅登记求值器明确要求的持久 ordinary action 使用它；不扩展到 Contact/Personal DM 或仅 live 的私有操作。 |

**相同 Event 建立多个条件。** Genesis E0 同时建立 root generation、controller assignment 和独立 lifecycle gates，并不使这些条件相同。E0/E0 的 owner transfer cut 只能命中 controller assignment，既发 grant 所用 root generation 保持；authority reset 则按实际根代依赖关闭。archive→freeze→restore 后仍然 frozen；随后 unfreeze 的新写必须使用各 gate 各自的开放 G，不能被另一个 gate 的旧 cut 误命中。

**不复活与不重复关闭。** 只有真正关闭一个开放区间的成功转换才能生成该区间的 closure。no-op、exact retry、已经 archive 后的 terminal 升级，不得给已关闭区间另选一个 frontier；终态升级仍可关闭其它尚开放的独立 gate。restore/resume/rejoin 只让作者在新上下文重签新的 Event，不改变旧 Event 的坐标或把被排除历史重新纳入。Circle tombstone 不可 restore；相同名称的新 Circle 有新 create Event/ID，旧 scope 与旧成员实例不会自动迁入。终态 Realm 的 successor 同理。

**派生与密码学。** install、Sidecar desired roster 只展开真实 registration、grant、membership、controller、key 等依赖，不虚构 install/Sidecar 授权 Event 或独立 generation。MLS leaf 授权与内容 epoch 的密码学可用性分别验证：有 leaf 不证明持有消息所用 epoch 的合法 key；无关 epoch 推进不表示该 leaf 重新 join。未知 Add/Remove 或来源不能用 leaf_index、epoch 数字或当前 roster 补成历史证明。

一般 policy、join-rule 和业务约束仍在已认证历史上下文求值，不能因后续 policy 更新私自撤销既发授权。只有明确登记的独立撤权条件才产生上述 closure；扩充这类语义必须同步修改 canonical 表、来源证明和验证器。对象展示生命周期、运行态 readiness/presence、private participation、Account 当前服务状态、session/DPoP、cache TTL 和外部 DID 当前查询都不制造历史关闭坐标；这些路径原有 live gate 独立保留，确切已知 revoke 仍立即阻止新 live 提交。

### 5.3 历史集合与有限期

frontier 必须是该依赖/action 关闭边界的完整 Event heads；其 prev_refs/causal_refs 完整祖先闭包就是允许保留的历史集。关闭条目只能由上述成功命令语义派生，不能因为治理 Station 见过某条聊天而随意产生。撤销不用等所有接收站，因而真实离线消息也可能被排除。每个 receiver 使用同一已认证证据重算 eligible/pending/quarantined；缺少来源、完整关闭清单或必要 frontier 材料是 pending，签名矛盾或非法 kind/source/组合是 invalid，不能以空清单或任意 allow 回调宣称完成。已发生的展示不可回滚，历史导入不得再触发 live 效果。完整规则见 [授权与状态归约](./event-auth-state-resolution.md)。

有限期资格的 `existence_anchors` 绑定授权 Event、generation 和精确 Event frontier；anchor 只认证 Event 存在于有效窗，不表达授权关闭匹配，因此不携 dependency_kind，也不能替代上述依赖/source 验证。治理 Station 从确切授权状态派生有效窗，不接受 producer 复制的到期时间。完整 frontier 及祖先必须在冻结签名 body 前可用并通过历史授权校验。

设配置声明治理 Station 的可信 UTC 时钟误差至多 ε=`max_clock_error_ms`。冻结 anchor 或带显式期限的安全命令时，治理 Station MUST 确认本机可信时钟与 `sealed_at` 相差不超过 ε，且所有被锚定/批准 Event 已存在；整个 `[sealed_at-2ε,sealed_at+2ε]` 必须落在资格有效窗内。时钟不能保证误差界就不得出具该事实。重试只恢复已耐久冻结的同一 body 和存在观测，不对新到数据倒签。

这仅是对可信治理执行者观测的认证，不证明实际创建时间，也不提供独立多方时间见证。没有合格 anchor 的有限期数据可在 live 有效窗暂时接纳，稳定历史保持待证；完整关闭/到期证据排除其资格时进入 quarantine。producer 时间、普通 IngressReceipt 或期后新建的倒签 Seal 均不能替代。无期限普通聊天不需要期限 anchor，但仍适用下一节统一的数据身份收录与基准关闭。

### 5.4 普通数据收录与基准关闭

ordinary Event（已登记原子 bootstrap unit 内的初始 D 成员除外）签名携带 `data_basis`，其值是同 Realm 一个已确认 SealId。该 basis 建立数据区间身份，不授予写权、不代替授权来源、也不要求它是 receiver 当时看到的最新 Seal；只要该 basis 尚未由已确认 `data_closures` 关闭，合法离线写仍可接纳。已关闭 basis 上后到 Event 只有在最终允许集合中有 authenticated inclusion 时 eligible，有 authenticated non-membership 时 quarantined，缺完整证明时 pending。

Seal 的数据字段与安全字段严格分离：`data_delta[]` 是本 Seal 新收录 ordinary Event digest；`data_event_set_root` 是 predecessor 累计数据身份集合根；`data_closure_announcements[]` 公告将关闭的旧 basis 与最早关闭时刻；`data_closures[]` 在宽限后冻结该 basis 的 allowed-set commitment。`data_delta` 不进入 `delta`、`control_event_set_root`、`state_root` 或 `command_results`。同一 Event 身份最多首次收录一次，exact retry 返回原结果；已收录身份不得从累计集合移除。

数据目标批次周期固定为 `T=300000 ms`，公告宽限固定为 `G=300000 ms`，二者不得复用或由 Realm 改写为其它 profile。首个已完整验证且尚未收录的 ordinary Event 到达治理 Station 时，在与接收记录同一持久边界登记 dirty 和最迟批次时刻；后续来件不得重置最老时限。正常服务条件下治理 Station在 T 内签发收录 Seal，并可公告关闭一个位于该 Seal 已确认前缀内的旧 basis。公告的最早关闭时刻必须保守证明距公告 Seal 认证时间至少 G；高频安全 Seal 可搭载到期工作但不得缩短 G。

公告与其最终关闭义务必须持久化。即使宽限后没有新 Event，也须产生一个具有关闭效果的收尾 Seal；收尾 Seal 自身不被自动公告关闭，最后义务完成后恢复空闲。无新待收录身份、无未完成公告、无安全/治理工作时不得生成 heartbeat 或整点空 Seal。pending、重复、查询、单纯本地时间经过不新建 dirty。治理停机恢复后续接原冻结义务，不补造停机期间的一串空 Seal。

冻结 allowed set 与接收写入必须使用同一串行化边界。治理 Station 已返回“完整验证并耐久承诺纳入本轮关闭集合”的结果后，关闭不得遗漏该身份；只保存缺依赖请求不属于该成功。若关闭先提交，后来请求按已关闭证明分类，不能补写冻结集合。收尾时可同时收录新身份并为其尚未被公告覆盖的新 basis 建立下一项关闭义务，但不得推迟已有公告期限。

累计集合和每个冻结 allowed set 使用完整 typed digest、canonical 排序与 RFC 6962 commitment。服务通过登记的有界分页 material 接口返回 root、member_count、页 continuation 及 inclusion/non-membership 完整性证明；只给若干 inclusion、最大 actor_seq、时间戳、cursor 或本地 scan 不证明排除。material 的 scope disclosure 与原 Event 可见性相同；Seal 元数据读取权不获得私有 Circle/Event 名单。producer/SDK 使用持久 outbox 向治理 Station 送达 exact bytes 并取得可验证收录结果；第三方接收 Station 没有强制转发义务，也不得替用户隐式 rebase、换 basis 重签或重发通知。

数据关闭只冻结旧 basis 的允许身份集合，不证明实际创作时间，也不保证已收录 Event 永久具备授权资格。所有 authorization closure、有限期、执行依赖、已知 revoke 与后到历史重分类继续取交集。正常新编辑绑定仍开放的确认 Seal basis；某个来源 Event 位于旧已关闭集合不等于其合法后继必须也属于该旧集合。

## 6. 跨 Realm 原子性

current-v1 仅支持同一治理 Station、同一可原子提交存储内的多 Realm 安全事务。单个 StationId 不足以证明共用事务存储。所有必要参与域的完整安全读写依赖、signed basis、当前 revision、授权、单次 nonce 消费、所有域的 Seal 与 outbox MUST 在同一串行化事务内成功或失败；按 RealmId、CellRef canonical 顺序锁定，读依赖和不存在目标也纳入冲突检查，不能因授权求值短路漏锁。

需要不同治理 Station 同时锁定当前状态或共同更新的不变量不受支持。执行前发现此拓扑 MUST 返回 `failed_precondition` 且零写入、零 nonce 消费、零密钥释放、零外部副作用，不能先提交一个域后宣称整体成功。公共 wire 不存在 transaction manifest、prepare/commit/abort/apply records 或 decision Realm；单 Station 的数据库恢复记录不得伪装为第二套公开治理日志。

**实际消费者。** 单次 Agent 批准、恢复级联、依赖多个 Realm 当前可撤销 controller/PCR/key/grant 的安全命令都执行此完整闭包检查，不能用远端历史读证明冒充当前读锁。若其实际规则要求远端当前资格，则在该拓扑下明确不支持。只检查不可变历史 producer 签名或已确认事实不产生状态锁；普通 D 消息与原本允许撤销传播窗口的读取继续使用既有认证事实与 known-revoke gate，不因联邦本身进入事务。需要远端材料而材料未知时依旧 pending，不把未知解释成未撤销。

单次 approval 仍绑定 target Realm、nonce 与完整预签 EventId，在同一确认事务唯一消费。外部 sink 必须支持幂等键/fencing 或可恢复执行 owner；数据库成功不证明外部动作已经完成。结果未知时查询同一 outcome，不换 EventId 再执行一次。多 Station 协调的重新引入由延期设计承接。

## 7. 证明消费

CbsProofBundle、exact Seal resolve、governance dependency resolve 继续承载可验证的安全状态证明。多域 `seal_basis.leaves` 每域恰一个已确认 head，canonical 排列；同域多 leaf 无效。不能从缺失证明推导未撤销，也不能以额外 service 回执替换已认证治理签名。

客户端 MLS Commit 保留 staged state 和 exact outbound bytes，唯一确认后安装；明确拒绝后才销毁暂存并重建。epoch 数字不是 fork winner。已知移除者的新发言立即被 gate 阻止；未见移除的分区副本仍可能暂时接纳旧 epoch，这是允许的撤销传播窗口。

## 8. 单次 Agent 批准的发布

`ak.agent.action_approve` 是目标 Realm 的安全命令，同时完成批准与 nonce 唯一分配；它不再是等待各接收站分别消费的私有批准。payload.approved_event_id 绑定 Agent 预先签署的完整普通 Event；后者不引用未来的 approval 或 Seal，因此没有内容地址自引用。提交 wrapper 必须携带 publication_event，其 bytes 在批准前可用于验证，但不得提前业务投递。

批准的 actor 必须是该 Agent 的当前合法 controller，禁止 executed_by 代替实际 controller 签署；目标 Event 的完整 Agent AccountId、signer、Realm/scope、proposed_action、target、draft_content_digest（若存在）与批准内容全部匹配。执行器先验证原 Event 的全部规则，仅将正在确认的这一个 approval obligation 留待本命令满足；其它缺少的许可、批准或依赖不能跳过。controller/PCR/key/grant 的实际当前安全读取加入跨 Realm 事务，期限在安全确认的有界时钟规则下验证。

唯一消费 Cell 是 `ak.component.agent.approval_consumption.v1`，subject 为 `[canonical_json(controller ActorId), approval_nonce]`，所在域恰为原 Event 的 Realm。初态必须未写入，成功值为完整 approved_event_id，revision 为批准命令 EventId。nonce 不释放；竞争批准至多一个成功，失败无发布效果。exact retry 返回原 outcome。批准者对不同 Realm 的批准是不同显式权限，不接受复制到另一个 Realm。

确认后原 Event 按 D 模型发布，发送及重试保持 exact bytes。接收者用现有 cbs_proof_bundles 携带/解析该批准命令的 covering Seal 和确切消费 Cell 证明；这是允许的相关依赖，即使其 Seal 晚于原 Event 的 auth_context。必须校验消费值等于当前 EventId，不能用同内容、同 nonce 或同 Agent 的其它 Event 代替。cbs_proof_bundles 本身不授权。存储者必须与原 Event 一并保留这份证明，历史分类仍执行其它适用关闭约束。

批准确认和待发布 outbox 必须原子持久化，崩溃只恢复原 Event；目标数据缺失时 pending，不换身份重建。私有 draft 的 published 状态从已确认批准与确切发布结果派生，不是共享准入权威。外部副作用仍要求唯一 command outcome 与下游幂等/fencing。未要求单次批准的普通 Agent 消息完全不走此流程。

## 9. 治理结果证明（normative）

### 9.1 责任与唯一载体

治理结果消费 Station MUST 接受本节认证的确切安全事实作为相应治理验证依据，不得仅因自己没有重放完整历史而拒绝。
“独立验证”在该角色指验证信任起点、配置、唯一签名、事实与操作绑定；治理 Station和明确进行独立重放的 auditor
继续完整验证命令、历史授权、CAS、结果、事务与根。承担多个角色的进程必须分别满足各角色义务。
普通客户端仍消费自己 Station 的结果，不取得本节证明。注册/genesis 尚无先验 Seal，仍验证完整原子 anchor unit、
外部身份根和精确 RealmId；不能由待证明的 notary 自证其起点、PCR/controller delegation 或外部 DID。

唯一新增的公共证据是 [seal-conclusion.schema.json](../../artifacts/schemas/seal-conclusion.schema.json)。
它认证已确认事实，不修改 Seal canonical bytes、Seal 签名 transcript、state_root 或既有 Merkle 树，
不引入安全命令、独立授权、controller 权力、witness 服务或新的确认序列。原 Seal/证明可按既有方式离线验证；
其中未获授权的正文、整 Cell、相邻叶或辅助记录不得为满足消费者重放而披露。

### 9.2 签名与配置认证

`certificate` 恰为 `statement, signature`。statement 顺序为 `realm_id, configuration_ref, authority_seal_ref, target_seal_ref, results`。唯一 signature 使用 Seal 的 closed JWS carrier，payload 为 `JCS({context:"ak.seal.conclusion.v1",statement:<完整 statement>})`，payload_digest 是该 payload 的 SHA-256 typed digest。protected alg/kid MUST 匹配已认证配置的冻结 signer；拒绝额外签名、unknown crit、非 canonical 编码及跨 context 签名。Seal commit 与治理结果证明不能互相替代。

签署者 MUST 已完整验证并耐久接纳 authority_seal_ref，target 必须是该已确认 lineage 上的祖先或自身；必须实际持有并验证所证明的目标状态与结果。身份控制持钥者可消费自己 Station 准备的精确输入，职责边界与 §1 相同，不重新取得全历史。证明不自报 current、TTL 或全网最新，查询不创建空 Seal。若已有获授权 Seal/Cell 证明完整覆盖所需事实，直接复用；需要隐藏无权读取的周边状态或精确中间 command effect 时才使用该独立读证明，不要求两份证明叠加。

消费者从已验证 Realm genesis 或耐久可信配置开始，不能由 candidate 自报配置、当前 DID key 或裸 service signature 自证起点。`configuration_handoffs` 只带实际必需的连续轮换。`handoff_certificate` 恰为 `statement, signature`，statement 顺序为 `realm_id, configuration_ref, handoff_seal_ref, next_configuration_ref, next_configuration`，payload 为 `JCS({context:"ak.seal.configuration_handoff.v1",statement})`，payload_digest 为 SHA-256。旧 signer 在已确认最终轮换 Seal 后认证 exact 新配置及旧写权永久冻结，后继不得自签替代。

按链顺序验证旧 signer，再安装 exact 新配置；拒绝跳步、循环、冲突与不连续前缀。后继激活还必须满足 §4 的完整执行材料继承。旧 signer 交接后不得为新查询出具事实；已签历史证明不因正常轮换追溯失效。证明链不能扩大读取权限或要求消费站重放全部私有历史。

该模型信任唯一治理执行者按规则求值；独立验签只证明授权来源与绑定。已知双确认、配置冲突或撤销不得被成功验签覆盖，不声明多副本容错。

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
或原样 missing query。全部 missing 时省略 conclusion_set；unknown、无权、缺材料/签署者不可用 共用 missing，不返回部分成功 query。
每次最多 128 个 query，每 query 64 个 selector，每 range 512 个 cell，每 certificate 的 canonical bytes 最多 8 MiB；
请求 ≤64 KiB，response ≤8 MiB。超限用既有 limit_exceeded，不拆签名对象。handoff 最多 256 项、每次 conclusion_set 最多
128 份 conclusion；可按 known_configuration_ref 省去接收方已独立认证的交接前缀；完整必要链仍超预算则 limit_exceeded，不声称存在未登记的配置分页，也不截断成“已认证最新”。不对外细分私有依赖缺失原因。

首次加入继续走有 intent gate 的 bootstrap，不开放成员级 resolve。bootstrap 的 `seal_conclusion` typed record 承载
同一 conclusion_set；来源站从已注册加入规则机械求完整事实集合，outer governance_facts 与 preconditions 必须与认证值一致。
受限 application-status 在 sealed 时 MUST 携同一 conclusion_set，仅证明此申请的 command 与成员结果；它不授权读取其他 Seal 正文。
CbsProofBundle 的 conclusion_set 为同一载体，治理结果消费可令 replay arrays 为空；容器本身不签名、不产生权威。

结论可跨请求缓存和由获授权持有者转交，历史 statement 不绑定 request_id 或重新计时。只允许无副作用地复用同一
事实；逐请求授权、已知撤销、有限期和实际动作检查不缓存成永久许可。冷查询确需新的治理结果签名时，若签署者
不可用则明确未决；不保证任意未缓存 selector 在签署者离线时可取得。不得将该读签名变成普通消息、重复读取或
已有证据消费的强制在线依赖。后台预取不扩张授权，也不得要求周期空 Seal。

### 9.5 业务消费与保留

治理结果消费 Station MUST 保存所用信任起点、认证配置、结论、必要 canonical bytes、实际语义/作用域与已知撤销依赖，
并与其局部接纳/投影原子持久化；不能把局部事实标记为整 Realm 已重放、治理执行就绪、全量 roster/历史完整或 GC 依据。
对同一不可变 target/selector 的计算和验签持久共享；每请求分别授权。收到原始 Seal 时仍按完整原始 bytes 验
其内容地址与签名，不把 conclusion 的 target 引用当成验过该 Seal 原文。

安全命令新执行仍在实际执行位置检查业务值与 signed basis 派生的 revision/锁；源站 accepted、authority intake、
committed、成员投影及 MLS Welcome 仍是不同阶段。配置已认证不表示全网最新，已知相关撤销立即阻止新的 live 效果，
普通消息保留未知撤销的传播窗口。普通 Event 签名/actor chain/CRDT、MLS transcript/秘密 MAC、HPKE/AEAD、
AvailabilityReceipt、archive 真正持久化和外部副作用幂等不由 治理结果证明替代。

多域消费者分别认证各域的 exact Cell/command 结果；一个域不能签发另一个域的权威事实。同 Station 本地事务保证所有参与域结果原子可见；任何部分结果不能推导跨 Station 原子成功。

历史恢复可用 exact epoch/transition、incarnation、T0 上界与 current ratchet 事实和必要 ancestry 结论替代治理 cut
重放，但每个请求 epoch 与区间必须完整认证；T1 首次入队、来源签名、接收密钥及解密检查不变。治理执行接管、独立审计、
内容恢复或 archive 耐久所需原始材料仍按其职责保留，不能因 reader 改用结论而删除唯一资料。
