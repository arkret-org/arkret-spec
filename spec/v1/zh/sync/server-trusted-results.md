---
title: 账号服务器信任与结果消费
status: candidate
normative: true
stability: v1
updated: 2026-09-09
sidebar:
  label: 服务器信任与结果
---

本文规范用语遵循 [规范性语言](../conformance/normative-language.md)。

## 1. 信任方与角色

普通客户端 MUST 信任当前完整 AccountId 所属 Station 在已认证账号会话下给出的治理验证结果。信任绑定完整 AccountId、Station service、当前设备/会话与所调用 operation；客户端 MUST NOT 将任意 Directory、远端 Realm 服务、Blob/Media endpoint、URL 或第三方自报的 verified 状态视为自己的 Station。建立账号会话之前，预期 Station 身份及认证绑定 MUST 已由接入流程确定，不能以待接入服务的自报形成循环信任。

角色按实际动作划分，不按程序或 SDK 包名划分：

| 动作 | 责任方 |
| --- | --- |
| 接纳 Event/Seal、联邦输入、历史 signer、DID method history/witness、授权/reducer/root 与有效分支 | 接纳/复制材料的服务器 |
| 查询当前或指定 accepted basis 的治理事实、成员 incarnation、历史访问范围及准备操作输入 | 自己 Station |
| 响应结构、请求/账号/Realm/scope/对象绑定、cursor 原子安装、用户意图与待签字节核对 | 客户端 |
| 设备私钥、用户带外设备信任、MLS Commit/Welcome/KeyPackage 密码学、内容/附件/备份认证与解密 | 端到端客户端 |
| 独立审计、服务间可移植证据及外部导入验证 | 实际承担该独立角色的验证者 |

客户端 MUST NOT 为认证自己 Station 的结果而下载完整治理闭包、重放历史 signer/Seal/reducer、重算治理 roots 或执行 omission challenge；此类工作也 MUST NOT 成为首页、进入 Realm、发送前准备、Welcome、Signal 或历史密钥恢复的前置。客户端的本地内容归约、解密及离线编辑不承担服务器治理接纳职责。

服务器 MUST 验证不可信客户端和远端服务的输入。共享 SDK 中的服务器 verifier MUST 保留独立适用范围，不能用客户端信任规则跳过首次 admission、联邦验证或审计验证。

## 2. 结果绑定与可用性

服务器结果 MUST 绑定请求的完整账号、Realm/effective scope、准确 accepted Seal basis、对象/动作及所需当前或历史观察坐标。客户端只消费本次认证请求的结果，不把已缓存的另一个账号、Station、scope 或操作的成功状态搬到当前请求。

已授权可见的查询中，尚未验证、依赖缺失、未决分支与有效的空状态 MUST 可区分。未验证材料 MUST NOT 被报告为 accepted、无权限、已删除或成功。存在性受保护的目标仍遵守相应 operation 的 outward-disclosure 与非枚举失败规则；内部验证原因不能通过错误码、响应大小或时序旁路泄露。

请求接受、后台排队、治理状态 accepted、操作完成与端到端内容可解密是不同状态。依赖治理结果的写入、成员变化或密钥释放 MUST 等待所需验证和当前授权；只读界面 MAY 展示已确认的局部内容。一个 Realm 的等待 MUST NOT 阻断其它 Realm 或账号导航。

缓存有效性 MUST 按 exact basis、规则/贡献上下文与相应 freshness 判断。leave/rejoin、设备撤销、key generation/fence、fork/recovery、权限变化及账号切换 MUST 使对应当前授权结果失效；历史 accepted 事实不能反向成为当前授权。已知撤销不得因旧结果尚在 TTL 内而继续使用。

服务器不可用时，客户端保留已确认的有限本地内容，并将需要刷新权威状态的操作置为等待；MUST NOT 以客户端完整治理重放作为恢复方式。客户端不提供对自己 Station 恶意伪造治理结果的独立检测保证。

## 3. 签署与端到端边界

服务器可以准备 exact basis、cell heads、预条件和 canonical 待签材料。客户端签署前 MUST 核对完整 actor/subject、Realm/scope、动作、用户意图与 exact bytes；签署后服务器 MUST NOT 补填 basis、替换目标或改写 payload。状态变化导致材料不再可接纳时，应按该操作的冲突与重试合同重新准备，不修改已签材料。

device-signed PCR Seal 与用户 DID 控制操作仍由授权设备持钥签署；签署设备消费自己 Station 准备并验证的治理输入，MUST NOT 因签名者角色被要求重放账号或 Realm 的全部治理历史。普通在线操作不得无条件增加额外通用 challenge/prepare/commit 轮次；仅使用该 operation 已登记的准备与提交合同。

服务器提供的设备授权事实不等于用户带外确认。客户端 MUST 保留设备密钥绑定、既有带外验证状态、密钥变化处理、KeyPackage 自签、MLS transcript 与内层内容认证。服务器无法读取的 encrypted MemberIdentity 明文及内层 proof 不能声称已由服务器核验；客户端仍验证其 realm/actor/subject 与密码学绑定，公开 signer 授权由自己 Station 提供。

内容寻址 hash、加密附件 segment AEAD、备份认证和下载边界检查继续适用。Blob/Media 的外部传输与直接密钥释放仍遵守其已确认 binding 和 plaintext visibility。地址簿私有发现的 PSI/VOPRF 及其密码学证明由参与该私有协议的客户端处理，MUST NOT 为服务器验证而上传联系人明文。

## 4. 服务器验证复用

客户端确认自己已知的 Control Move 是否被 Seal 接受时，MUST 使用
`ak.self.control_proposal_decisions.read.get.v1` 的 exact `(realm_id, proposal_digest)` 结果。
自己 Station 返回 `proposal_state=sealed` 且绑定同一 Event kind、digest 与 `accepted_seal_id`，即可确认该 Event
已被接受；pending/deferred/overdue/rejected 不得当作 sealed。客户端保留已签 intent 的确切内容与摘要绑定，
但 MUST NOT 为这项确认拉取 Seal 前驱闭包、DID history 或治理重放检查点。若还需取得接纳后追加的 Event envelope，
只 resolve 已知的确切 Event 并核对原始签署输入不变。存在多个有效直接 covering Seals 时，`accepted_seal_id`
MUST 选择其中 canonical 字节序最小的一项；隔离的 Seal 不参与选择。它不是完整 frontier，不得直接代替 authoring
`seal_basis`；选择项变化本身不表示原 Event 不再被接受。服务器先按当前会话检查该 Event 可见性，查询命中的 durable
proposal/covering-Seal 状态；不得为单 Event 确认枚举整个站点的 canonical Events。

同一服务器 MUST 将治理接纳与逐请求授权分离。对相同 Realm/scope、exact accepted basis、canonical bytes/acceptance pin、历史 authority 与规则/贡献上下文，验证结果及派生视图 MUST 持久共享；不得只因用户、设备、请求 ID 或重复读取变化而重新全量验证。并发相同目标的计算 MUST 合并，所有等待者分别执行当前读取/动作授权。

accepted bytes、验证标记、视图根和必要索引 MUST 原子提交。重启后只恢复有完整验证来源的结果；缺失、受损、规则或贡献上下文失效的部分必须重建。原始材料持久化不等于已验证状态，内存中句柄缓存不能替代耐久视图。

新增历史只执行实际新增验证和必要依赖计算；分支合并、fence/recovery 或规则变化只重算真实受影响部分。根计算若按现行编码需要读取累计集合，实现 MUST 如实保留并计量该成本，不得把响应分页或落盘称为恒定时间验证。首次参与某段历史的服务器仍承担必要完整验证。

## 5. MLS 绑定结果

`ak.self.seals.read.mls_governance_proof.v1` 的 self surface MUST 使用
`mls-governance-proof-bundle.schema.json#/$defs/self_read_request` 与 `self_read_outcome`。
名称中的 proof 不赋予客户端独立治理验证职责。Peer 同名 operation 继续使用独立的
`read_request/read_outcome` 证明合同；self MUST NOT 接受旧 proof DTO 或返回 Merkle/历史材料。

请求字段按 `effective_scope, mls_group_id, local_mls_leaves, seal_basis, base_group_state_ref?,
proposed_group_genesis_binding?, previous_epoch, next_epoch` 排列。scope 仅限 Realm/Circle，group 必须由 scope
派生；leaves 必须是本地 MLS 已验证的 current/pending 完整叶集合，按 leaf_index 严格递增，1..65536 项，
credential_ref 不重复且每项不超过 2048 字符，请求 canonical bytes 不超过 8 MiB。它不是全部 Realm 历史。
epoch 只允许 0→0 或 n→n+1；后者必须提供准确的 base_group_state_ref。0→0 禁止 base ref；只有未存在
accepted Genesis 时携 proposed_group_genesis_binding，proposal、accepted immutable Genesis 和并发冲突仍遵守
现有 Genesis 错误合同。固定使用 `ak.security_frontier.v1` 选择规则和 full MLS binding profile。

服务器 MUST 对每次请求检查当前账号的 Realm/Circle 可见性，并读取 exact seal_basis 的已接受 joined state，
不得静默替换为当前单一 head。沿现有 frontier registry、exact local leaves 与不可变 Genesis binding 计算
security_frontier_digest；其公式与 peer verifier 相同。服务器不得返回未验证的 cells 或用空状态掩盖依赖缺失。
successor 的 epoch cell 必须具有 next_epoch=请求 previous_epoch 且 transition_ref=请求 base_group_state_ref；
不匹配返回 state_mismatch。权限检查不能由共享历史缓存命中代替。

响应字段按 `query_digest, seal_basis, live_digest_suite, governance_binding, epoch_head?` 排列。
query_digest 为 SHA-256(UTF8("ak.mls-governance-frontier-query-v1") || 0x00 || JCS(exact request))。
它绑定请求，MUST NOT 被解释为对恶意服务器的认证证明。响应不重复 leaves；完整 canonical bytes 不超过
1 MiB，超界失败而不截断、不分页。epoch_head 为请求 basis 的完整 winning epoch cell 值，可直接进入已签
head_eq；没有 accepted epoch 时省略，缺材料或 Bottom 必须失败，不能以省略表示未验证。

客户端 MUST 校验 exact query、basis、scope/group/epoch、profile、用户提议和本地 leaves 的绑定；接收已签
MLS binding 时还要核对服务器给出的 security_frontier_digest 与该 binding 相等。客户端保留 MLS tree、
transcript、Commit/Welcome、credential/KeyPackage 和 AEAD 检查，MUST NOT 再取治理闭包、Merkle witnesses
或本地重放生成相同结果。缓存只保存有界请求/结果，绑定账号会话并在已知权限变化时失效，迟到响应不得跨
会话安装。历史 MLS transition 的治理判断由自己 Station 在其准确已签 basis 完成，不能用当前授权替代历史
成员判断，也不能用历史授权替代当前读取许可。

### 5.1 Accepted transition 的公开输入

EventInitialSubmission 与 EventFederationSubmission 在 event 之后、authorization_lease 之前携带
mls_frontier_leaves；该字段仅在 ak.mls.genesis/ak.mls.commit 必填，其它 kind 禁止（包括 null）。
数组使用 MlsSecurityFrontierLeaf 的同一 closed 类型、1..65536 项、严格递增 leaf_index、无重复 credential_ref
及 2048 字符 credential 边界，整体 submission 的 canonical bytes 仍不得超过 8 MiB。

该集合 MUST 与最终签署的 Genesis/Commit 的 post-transition 公开叶意图相同。scope、group、epochs、
base_group_state_ref、Genesis binding 与治理 basis 从该 Event 自身的签署字段取得；服务器在 exact basis
按同一 registry 投影公式重算 security_frontier_digest，MUST 与 signed governance_binding 相等。
preflight 的另一组叶、旧的 claim 前叶集合、少叶/多叶、错完整 ActorId 或并发赢家的不同输入均不得替代。
未验证或无法取得所需历史 authority 的输入不得标为 accepted。

该 evidence 位于 Event digest preimage 外；它的完整内容通过现有 security_frontier_digest 和 Event proof
绑定，不新增自引用 Event ID、独立 signature 或客户端治理 checkpoint。服务器 MUST 将它与首次 durable
admission、accepted Event 和必要关联索引原子持久化；同 Event 的冲突输入不得覆盖既有输入。Peer push/resolve
转发首次接纳的完全相同输入，接收服务器独立验证，不因源服务器自报或缓存命中而跳过。

普通 self frontier query 的临时缓存、短命 claim record、消息到达次序或“第一个空 leaf index”均不是 accepted
输入的替代来源。服务器结果对 exact accepted transition 提供其公开叶意图，客户端将它与真实 RFC 9420
tree、credential/signature key、GroupContext 和 exact Proposal/Commit bytes 绑定；不能把服务器的治理结果
当作服务器已经应用私有 MLS tree。冷 Welcome 不再依赖完整治理历史来猜测叶的成员归属。

### 5.2 已知 MLS artifact 的接纳结果

`ak.self.seals.read.mls_accepted_artifact.v1`（`POST /_arkret/self/seals/mls-accepted-artifact`）接收
`MlsAcceptedArtifactRequest {effective_scope, mls_group_id, artifact_ref}`，仅选择一个已知 Realm/Circle
内的 Genesis、Commit 或 Welcome。请求 canonical bytes 上限 64 KiB；完整结果上限 16 MiB，独立于请求上限，
无 continuation。请求不得携证明基点、客户端检查点、完整历史或 caller 自报的叶集合。

`MlsAcceptedArtifactOutcome` 按顺序包含：

| 字段 | 含义 |
| --- | --- |
| query_digest | SHA-256(`ak.mls-accepted-artifact-query-v1` + NUL + JCS(request)) |
| seal_basis | 服务器完成当前授权与接纳判断的完整 accepted antichain |
| transition_head | artifact 对应的已接纳 Genesis/Commit，使用 MlsEpochHead 唯一类型 |
| governance_binding | 该 transition 的原始 signed governance binding |
| mls_frontier_leaves | §5.1 在该 transition admission 中原子保存的 exact final public leaves |
| current_epoch_head | seal_basis 下当前唯一 winning epoch 的完整 MlsEpochHead |

服务器 MUST 同时检查当前请求者的 Realm/PCR/Circle 读取资格和该 artifact 的精确读取可见性；先前作者身份、
旧成员身份、临时 claim、可读一个 Event 或共享验证缓存命中都不替代当前范围授权。Welcome 还必须匹配本会话
实际获准的 device/Agent/pairwise recipient。查询不得扩大历史内容、私有 Circle 或设备收件人的读取权限。

成功只表示：artifact 已被非隔离 accepted Seal 覆盖；Genesis/Commit 自身就是 transition_head.transition_ref，
Welcome 的 commit_ref 则等于该 ref；transition_head 是 current_epoch_head 的 exact accepted predecessor chain
在目标 epoch 的祖先。并发候选不得按到达顺序、最大 epoch 或单独的 covering Seal 任择。未 sealed 或当前验证
尚未完成返回 frontier_unavailable；不属于当前 winning chain 返回 state_mismatch；不可见与不存在统一 not_found。
若相应 basis 暴露冲突或缺依赖，MUST 失败，不以旧缓存、空叶集合或另一个候选填补。

服务器从已验证状态和确切已接纳索引判断以上事实，可共享相同历史结果，但逐次执行当前授权。返回的 leaf input
必须对应 transition 自身，而不是现在的 directory 或后续 epoch 的成员集合。查询结果不包含 ancestry Events，
不要求客户端重放链；多个调用者不各自从 Genesis 建立治理证明。

客户端只在匹配的 Account Station/账号会话及尚未失效的范围内消费结果；跨账号或已知撤销之后到达的结果不得安装。
它检查 query、scope/group、目标 Event ref、epoch、binding 和实际 RFC 9420 tree/credential/signature key/Commit/
Welcome transcript 的相符性，保留实际端到端密码学。此结果是服务器接纳判断，不是客户端 VerifiedMlsGovernanceFrontier；
不得制造空 checkpoint、page digest 或全历史 fallback。必要的真实 Proposal/Commit bytes 仍按已知 exact refs 获取，
不得扩展成遍历所有治理历史。旧 accepted-artifact helper 及其历史候选排序/祖先重放缓存须删除。

### 5.3 当前成员加入身份

`ak.self.seals.read.membership_authority.v1`（`POST /_arkret/self/seals/membership-authority`）只查询一个
`MembershipAuthorityRequest {effective_scope, actor_id, seal_basis}`。scope 为 Realm 或 Circle；actor 使用完整
ActorId；seal_basis 必须等于本次服务器当前 accepted antichain，陈旧或不同 basis 返回 state_mismatch。
请求与完整响应分别不超过 64 KiB；不支持批量成员、通配范围或 continuation。

`MembershipAuthorityOutcome` 字段顺序为 `account_id, query_digest, seal_basis, authorization_incarnation`。
account_id 是与实际认证会话绑定的完整 AccountId；AgentRuntime 使用其 Agent AccountId，不改写成 controller 或人类账号。query_digest 为
SHA-256(`ak.membership-authority-query-v1` + NUL + JCS(request))；basis 与 request 相等；incarnation 使用
history-key 的唯一 AuthorizationIncarnation 类型，表示此 basis 下 actor 当前有效的那次 Realm join，以及
Circle scope 需要的当前 Circle activation。返回已失效的旧 join、把最大 actor_seq 当 join、按 Events 到达顺序
选择，或对冲突任取一个分支均禁止。Circle activation 必须按既有标准因果规则覆盖当前 Realm incarnation。

服务器先检查本次认证会话、Realm 成员信息的当前读取资格与 Circle 隐私边界，逐次检查目标在该 scope 的当前
成员状态。Scope/target 不可见或目标未加入统一 not_found；accepted state 缺依赖或无法取得唯一 incarnation
返回 frontier_unavailable。历史验证共享不共享上述请求授权；不得把查询变成跨 Circle 的成员枚举入口。
成功不授予 caller MLS Add、消息发送或历史密钥释放权限，后续提交仍执行标准授权及其 signed basis/CAS。

客户端检查 exact request digest、Account Station/账号会话、scope 对应的 incarnation 分支与 basis 后，将该结果
用于 MLS Add 或历史请求的 intent authoring。它不获取 membership Event/Seal 全闭包，不自行回放 join/leave。
结果缺失时该操作保持未就绪；账号切换、已知离开/撤销或 basis 更新后，迟到结果不得覆盖新上下文。
服务器使用已 accepted 的标准 reducer/CAS head 与因果索引求值，不能以即时 directory 的显示状态替代。

### 5.4 当前历史授权与范围下界

`ak.self.seals.read.history_authority.v1`（`POST /_arkret/self/seals/history-authority`）查询
`HistoryAuthorityRequest {effective_scope, actor_id, seal_basis}`。其当前账号、Agent 实际认证 AccountId、
成员可见性、scope 隐私、exact antichain、缺失/冲突与迟到响应边界均遵循 §5.3；请求与完整响应各 ≤64 KiB。
query_digest 使用 SHA-256(`ak.history-authority-query-v1` + NUL + JCS(request))，不与 membership 查询互换。

`HistoryAuthorityOutcome` 顺序为 `account_id, query_digest, seal_basis, authorization_incarnation,
join_epoch, history_floor_epoch`。所有结果来自同一个已 accepted basis：

- incarnation 使用 §5.3 的当前 Realm join / Circle activation 因果身份。
- join_epoch 是既有 winning MLS lineage 与该 incarnation 所决定的加入轮次。尚无唯一可用 MLS lineage 时
  返回 frontier_unavailable，包括 all_history_for_current_members；不能猜测为 0。
- history_floor_epoch 按 scope 自己的 accepted history_access cell 求值：since_join 为 join_epoch，
  all_history_for_current_members 为 0。Circle 不继承 Realm policy；缺失、Bottom 或未知策略均不可用。
  floor 必须为 0 或 join_epoch，接收方不据此推断另一种治理策略或自行回放历史。

发起方用该结果填写 HistoryKeyRequest 的 incarnation 并选择恢复范围下界；不签入治理检查点。响应源查询
目标 actor 的当前结果，在签名 manifest 之前裁剪候选范围，且目标 incarnation 必须仍与原请求一致。
此查询不授予历史密钥读取、manifest 提交或密钥释放权限：服务器仍逐次校验 requester/source/endpoint、
当前成员、T1、retention、receipt 与请求绑定。当前策略收紧或 leave/rejoin 后不得复用旧授权结果释放密钥。
客户端仍验证 HPKE/MLS、AEAD、签名及 exact packet/recipient/scope 绑定，不获取治理历史作为此查询的前置。
首次缺少输入时只让该历史任务保持 pending，不阻塞已可读的新消息或全局账号同步。

## 6. 规范与 conformance

full/e2ee 客户端 conformance 检查请求绑定、结果消费、端到端密码学和恢复行为；服务器 conformance 检查治理历史、DID/外部证据、admission、当前授权与共享增量状态。客户端没有治理历史 verifier 不构成不合规；服务器接受未经验证的远端材料构成不合规。

相同 fixture 可以提供服务器有效/无效输入及客户端成功/pending/错绑定结果，但 MUST 分别标明角色；不能要求客户端执行服务器 verifier runner 才能声明产品 profile。SDK 发布同时包含两种角色时，仍须分别证明各自适用的条款。

第三方 conformance artifact、service delegation、公开身份声明及其发行者历史由自己 Station 验证并提供带来源和有效期的结果。服务器代核验不能将自报 claim 变成独立认证；客户端不必下载完整 artifact/authority 证据链。
