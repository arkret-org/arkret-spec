---
title: 账号服务器信任与结果消费
status: candidate
normative: true
stability: v1
updated: 2026-09-10
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

服务器结果 MUST 绑定请求的完整账号及该 operation 所需的 Realm/effective scope、对象/动作与当前或历史观察坐标。需要 accepted Seal basis 的治理事实或签署准备结果 MUST 绑定准确 basis；纯身份/PCR 定位结果不因此追加 Seal 或 authoring 权限。客户端只消费本次认证请求的结果，不把已缓存的另一个账号、Station、scope 或操作的成功状态搬到当前请求。

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

本节所有 self operation 的预算错误分开处理：收到的 request canonical bytes 超过其上限使用
HTTP 413 / `payload_too_large`；合规请求所需完整响应无法满足结果预算使用 `limit_exceeded`
（既有 HTTP 映射为 413），不截断原子事实。仅结构或数组项数违反 schema、且 request bytes 未超界
使用 HTTP 422 / `schema_violation`。HTTP/gRPC/MQ 保持同一错误原因分类；SDK 本地预检不得把
请求字节错误混成结果预算错误。统一优先级见 scalability-constraints §2.1.9。

`ak.self.seals.read.mls_governance_proof.v1` 的 self surface MUST 使用
`mls-governance-proof-bundle.schema.json#/$defs/self_read_request_body` 与 `self_read_outcome`。
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

Realm/Circle 的公开 leaves 意图还 MUST 与 encryption-and-audit §2.5.1 的 PublicMessage 握手及
§5.1.1 的 Genesis 公开 GroupInfo/tree 交叉验证。服务器按确切公开 staged transition 解释 consumed
Proposal、Add/Remove/Update 和新 leaf instance，不能仅凭提交者自报 leaves 或相等的前后三元组
构造来源。公开 tree 与必要 accepted leaf provenance 同此 admission 原子保存；不得要求成员 secrets
或声称已验证秘密 MAC。minimal-metadata 只使用其既有 pairwise 公开材料，Sidecar 合同不受本条扩展。

解释 staged transition 时，服务器 MUST 先按 [`../crypto-media/encryption-and-audit.md` §5.2.1](../crypto-media/encryption-and-audit.md)
的固定顺序判定每条 consumed Proposal 与该 Commit 自身的 RFC 9420 sender class 与 Proposal 类型：只有
[`mls-proposal-admission-registry.json`](../../artifacts/registry/mls-proposal-admission-registry.json) 的 active row
可以进入 leaf provenance 计算。ExternalSender、NewMemberProposal、NewMemberCommit、`external_init` 与未登记
codepoint 的 AppCustom MUST 以 `unsupported_feature` fail closed，MUST NOT 误报 `schema_violation`，也 MUST NOT
发布部分 transition、部分 leaf 来源或“已接纳但未消费”的中间态。Member sender 的叶必须在 exact accepted base 中
已占用，且其 credential 与 signature key 等于该 Event 已验证的 producer `executed_by ?? actor_id`；不满足时按同一
节的第 7 步返回 `failed_precondition` 或 `signature_invalid`，不得降级成不受支持特性。

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
`MlsAcceptedArtifactRequestBody {effective_scope, mls_group_id, artifact_ref}`，仅选择一个已知 Realm/Circle
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

### 5.2.1 认证收件人的 Welcome 引用发现

`ak.self.seals.read.mls_welcome_refs.v1`（`POST /_arkret/self/seals/mls-welcome-refs`）在请求者自己的
Account Station 上接收 closed `MlsWelcomeRefsRequestBody {effective_scope, mls_group_id, limit?, cursor?}`。
scope 精确选择一个 Realm 或 Circle，group 必须属于此 scope。limit 默认 20、最小 1、最大 100；
请求 canonical bytes 与完整响应 canonical bytes 各自不得超过 64 KiB。响应为 closed
`MlsWelcomeRefsOutcome {welcome_refs, next_cursor?, limited}`，只返回真实 `ak.mls.welcome` Event refs，
不返回 artifact bytes、Seal 证明或客户端检查点。`limited=true` 当且仅当存在 next_cursor；此时至少返回
一个 ref；末页允许空列表且不携 next_cursor。单个 opaque cursor 最多 4096 字符，服务器必须在签发前
计算包括 cursor 和容器在内的完整响应字节，不能签发无法装入下一合法请求的 cursor。若相同 scope/group、
effective limit 和 continuation 的下一请求无法满足 64 KiB，必须在返回未完成第一页前以 `limit_exceeded`
失败；不得先给调用者一个无法继续的成功窗口。

收件身份仅从已认证会话推导，禁止 caller 指定任意 recipient。收件 endpoint 完全由该会话 SessionGrant 的
signed `holder_binding` 分支确定：`human_device` 与 `agent_runtime` 分支绑定完整 AccountId（包括 Station）
与设备或 Agent 的精确认证 endpoint；minimal-metadata pairwise 收件人使用
`{kind="minimal_metadata_pairwise",realm_id,actor_id,verification_method}` 分支，它在完整 AccountId 之外还
绑定 exact verification method 与 Realm affinity，并按
[`../identity/key-management.md` §6.5](../identity/key-management.md) 在每次 admission 重新判定当前持有与
撤销。AgentRuntime 使用获准 Agent 的认证引用、method 和 session endpoint，controller 的会话不能代领；
pairwise 窗口同样不得由 controller、其它设备或 Realm membership 代领。本请求保持封闭的
`{effective_scope, mls_group_id, limit?, cursor?}`，MUST NOT 为任何 endpoint class 新增 proof 字段。
`holder_binding.realm_id` 必须与 `effective_scope` 所选 Realm（Circle scope 取其所属 Realm）逐字一致，
否则按不可见规则返回 `not_found`。
每页必须重新检查当前 Realm/PCR/Circle 资格、精确 recipient、成员 incarnation 和私有 Circle 可见性；
不可见或不存在统一 `not_found`，当前 accepted 权威结果尚不可用返回 `frontier_unavailable`，不得退回旧授权。

服务器维护按 recipient、scope/group 与稳定接纳序号可索引的 Welcome 资格记录。只枚举当前 winning
transition chain 上已经 accepted、未 quarantine、未撤销、未到期且尚未终结消费的 Welcome。Event、
accepted transition/eligibility 及索引必须同事务发布；普通提交、联邦接纳、exact retry、collision/quarantine
和 recovery 都必须接入同一边界。不得通过扫描全 Realm Events、全成员目录或对每个候选重放 ancestry
来建立一页。查询工作和临时内存必须由页限制及固定字节预算界定，历史长度不参与单页扫描界限。

首次请求冻结稳定 observation upper bound；顺序为稳定接纳序号、Event ref，后续新增不插入此窗口。
cursor 为 operation-specific opaque continuation，绑定完整认证 endpoint、scope/group、effective limit、
固定筛选、观察上界、accepted eligibility revision 和最后输出坐标。后续请求必须使用同一 effective limit。
篡改、跨账户/设备/Agent/Station/scope/group、资格 revision 改变、窗口过期或索引修复导致窗口不可继续，
均返回 `cursor_invalid`；当前读取权限已失去仍按上述不可见规则处理。winning chain、recipient method、
incarnation、撤销、到期或消费变化必须使受影响窗口失效；无关 Seal 更新不得使窗口失效。
客户端只重开此 scope/group 的发现窗口，不得因此重扫全部 Realms。服务器必须保留窗口所需索引版本，
或显式使 cursor 失效；不得静默跨越未决索引槽位、重标新窗口为旧窗口或漏掉旧记录。

发现和分页均无消费副作用；device-message ACK 只确认通知队列投递，不删除尚可发现的 Welcome。
重复发现不重复 consume KeyPackage，不恢复已删除的私钥，也不证明本设备仍持有解密材料。
ordinary single-use KeyPackage 和 last-resort 的终态必须按 exact claim/Welcome 记录，不能用整个已发布
KeyPackage 的状态替代；last-resort 一个 claim 消费不隐藏其它仍合法 claim。既有 exact-retry consume
receipt、私钥生命周期及本地 E2E durable checkpoint 规则继续适用，缺失私钥走既有恢复或重新加入。

客户端逐个 ref 复用 §5.2 的当前 accepted-artifact 判断和已有 exact Event 读取，并完成真实 MLS
Commit/Proposal/Welcome、recipient、claim 与本地 tree 的 E2E 校验。安装仍服从既有 durable snapshot
barrier；没有收到队列消息就不能伪造消息 ID 或 ACK。发现的总分页开销与后续 artifact 读取开销必须分别
度量。schema/count-only 错误使用 `schema_violation`；实际请求字节超界使用 413 `payload_too_large`，
完整响应或合法 continuation 无法封装使用 `limit_exceeded`；不得截断 ref
或返回越界的部分成功结果。HTTP、gRPC `SelfSeals/MlsWelcomeRefs` 与 MQ
`self.seals.read.mls_welcome_refs` 共享上述认证、请求、响应及错误语义。

### 5.3 当前成员加入身份

`ak.self.seals.read.membership_authority.v1`（`POST /_arkret/self/seals/membership-authority`）只查询一个
`MembershipAuthorityRequestBody {effective_scope, actor_id, seal_basis}`。scope 为 Realm 或 Circle；actor 使用完整
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
`HistoryAuthorityRequestBody {effective_scope, actor_id, seal_basis}`。其当前账号、Agent 实际认证 AccountId、
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

### 5.5 当前 MLS 叶移除判定

`ak.self.seals.read.mls_membership_removal.v1`（`POST /_arkret/self/seals/mls-membership-removal`）
接收 closed `MlsMembershipRemovalRequestBody {effective_scope, mls_group_id, local_mls_leaves,
seal_basis, base_group_state_ref, epoch}`。scope 仅限 Realm/Circle，不包含 Sidecar。leaves 使用 §5 的唯一
MlsSecurityFrontierLeaf 类型与 1..65536 项、严格递增索引、无重复 credential_ref 和请求整体 8 MiB
边界，必须来自本地已验证的完整 current tree；不得使用 pending tree、仅当前可见成员或 lazy roster 子集。
group 必须由 scope 派生，epoch 是该 base transition 的 post-transition epoch，包括 accepted Genesis 的 0。

自己 Station MUST 逐次检查实际认证账号的当前 scope 可见性与成员信息读取资格，再在同一观察下核对
seal_basis 等于当前完整 accepted antichain、base_group_state_ref 等于该 basis 的唯一 winning epoch head
transition_ref、epoch 等于其 next_epoch，并核对完整 leaves 等于 §5.1 保存的 exact base post-transition
公开输入。不可见或不存在统一 not_found；可见目标的陈旧 basis/base/epoch 或不同 leaves 返回 state_mismatch。
缺 accepted 状态、冲突或依赖返回 frontier_unavailable，MUST NOT 选择最大 epoch 或另一个分支继续。

判定必须使用每个 exact leaf 在 accepted Genesis/Add 时获得的 Realm join、Circle activation（如适用）、
设备 generation 或 Agent method 授权及 credential/key 绑定。服务器 MUST 在接纳时将这些已验证来源与
transition/leaf ledger 原子持久化；沿 winning successor 对保留叶继承来源，对合法新增或重新加入的叶记录
新的来源。普通 MLS Update/Commit path 只更新 RFC 9420 允许更新的 encryption_key，继承原 endpoint、
membership incarnation、signature_key 与其 authorization binding；设备/Agent 签名密钥或授权改变必须按
[MLS 历史叶绑定](../crypto-media/encryption-and-audit.md) 的 replacement/remove+add 规则建立新 leaf instance。
服务器 MUST 解析 winning transition 的确切 accepted proposal_refs 与所需公开 Proposal/KeyPackage 输入，
按真实 Remove/Add 区分保留叶和新增叶；即使新增叶复用了同一 index、ActorId 和 credential_ref，仍记录新的
admission 来源。缺少可验证公开输入时返回 frontier_unavailable，不以相等的前后三元组推断叶被保留。
不能只用 leaf_index、相同 ActorId、
当前目录状态或新一次 join 替代旧叶的加入身份。公开 leaves 本身不携 incarnation，不能伪称仅凭该数组已
证明加入身份；缺少上述来源时返回 frontier_unavailable，由服务器恢复其验证索引，不要求客户端补历史。

服务器按当前 basis 的标准 Realm/Circle 成员、设备撤销/generation/fence 与 Agent 授权规则完整计算：
仅当该叶原有资格已明确失效时，将其 index 放入移除集合。leave/rejoin 不恢复旧 incarnation 的叶；同 Actor
的新合法叶不因此被一并移除。尚未验证、Bottom、暂时不可读取或缺材料不能当作明确失效；任一叶无法判定时
整个请求失败，不返回部分集合。结果不授予 caller MLS Commit 权限，不豁免正常 authoring、signed basis、
CAS、credential 与 RFC 9420 检查；需要移除自己的客户端遵循既有退出/其他有权成员提交规则，不能自签
违反 MLS 约束的 Remove。

closed `MlsMembershipRemovalOutcome` 字段顺序为 `account_id, query_digest, seal_basis, epoch_head,
remove_leaf_indices`。account_id 为实际认证的完整 AccountId（AgentRuntime 不改写成 controller）；
query_digest 为 SHA-256(`ak.mls-membership-removal-query-v1` + NUL + JCS(exact request))，因此也绑定
完整叶列表及 scope/group/base/epoch；它不是恶意服务器的认证证明。basis 必须与请求一致，epoch_head
使用 §5 的唯一 MlsEpochHead 类型。indices 是请求中真实 occupied leaf indices 的严格递增、无重复子集，
0..65536 项；只有完整求值成功才允许空集合。完整响应 canonical bytes ≤1 MiB，不分页、不截断；
请求 canonical bytes 超界按统一合同返回 413 payload_too_large；完整响应预算无法满足返回 limit_exceeded，
结构或数组项数非法返回 schema_violation。gRPC
`SelfSeals/MlsMembershipRemoval` 与 MQ `self.seals.read.mls_membership_removal` 采用相同合同。

客户端仅核对完整账号/Station/会话、exact query/basis/epoch head 和索引子集，再对仍相同的本地 MLS tree
执行明确 indices 的 Remove；MUST NOT 扩成同 Actor 全部叶的 Remove。应用前若本地 base、epoch、leaves、
scope 或会话变化，或已知权限变化，则丢弃结果重新查询；迟到响应不能安装到新树。客户端不回放
membership Events、不构造私有历史 frontier，也不因 lazy member 缺失猜测移除。查询失败只让本 scope 的
自动移除保持未就绪，不阻塞账号列表和其它 Realm；实际 MLS tree、Commit 与内容密码学继续在客户端验证。

### 5.6 按次 current 与精确历史签名公钥

普通客户端 MUST 通过唯一 `ak.self.signer_keys.read.resolve.v1`（`POST /_arkret/self/signer-keys/query`）从自己 Account Station 取得签名公钥结果，不下载或重放 Agent PCR、Account gate、DID history、Seal lineage 或 ASRE 闭包。Station MUST 验证来源，或复用来源完整的耐久验证结果；每次请求另行执行当前披露权限。peer portable evidence、controller gate 与服务器 verifier 保留，不能把远端未验证公钥重新包装为 self 成功。

closed `SignerKeyQueryRequestBody` 字段依次为 `request_id, realm_id, recipient_account_id, queries`；closed `SignerKeyQueryOutcome` 依次为 `request_id, realm_id, recipient_account_id, results`。机读合同为 `signer-key-operations.schema.json` 的 `query_request_body/query_outcome`。recipient_account_id MUST 逐字等于认证 SessionGrant 的完整账号，其 Station MUST 是服务本请求的自己 Station。结果 context MUST 逐字回显请求；每个请求 selector 恰有一个结果，不省略、不重复、不加入额外项。未认证请求遵循既有 401 合同；recipient 与会话完整账号或服务 Station 不符 MUST 返回 `404 not_found`，不执行 selector 查询。self 不接受 peer 压缩提示或 portable dependencies。

`queries` 为 1..64 个唯一 selector，按以下四种 closed 分支及字段顺序编码：

| 分支 | 字段顺序 |
| --- | --- |
| 当前普通设备 | `verification_mode:"current_admission", sender_kind:"account_device", actor, device_id, verification_method` |
| 当前 Agent | `verification_mode:"current_admission", sender_kind:"agent", actor, verification_method` |
| 历史普通设备 | `verification_mode:"historical_event", sender_kind:"account_device", actor, device_id, verification_method, event_id` |
| 历史 Agent | `verification_mode:"historical_event", sender_kind:"agent", actor, verification_method, event_id` |

actor MUST 为实际 signer 的完整 Account ActorId，不以 principal 加本机 Station 猜测。普通设备 method 的 DID 经登记 adapter 投影 MUST 等于 actor.account_id.principal_id，fragment MUST 逐字等于 device_id；Agent 必须有独立已验证的 Agent 分类。current 普通设备 selector 也 MUST 绑定待验证 Signal 的原 proof method，不能仅按设备 ID 取任意当前键。历史 selector MUST 与 exact Event 的 `executed_by ?? actor_id`、实际 producer proof method/device、realm_id 一致。

**self 历史接收方唯一（normative）**：receiver 固定为 recipient_account_id.station_id / 当前认证服务，不是 caller 可选择字段。Station 仅对自己已耐久接纳且本次 requester 可读的 exact Event 返回历史结果；仅 origin 或任意第三方曾接纳不构成自己的历史成功。必要材料仍通过既有标准 federation/dependency 接口取得并验证，完成本地 accepted 与来源保留后才能返回。未接纳、不可读或缺依据使用 unavailable，不得为本查询新增远端 receiver 选择、私有 peer API 或新的 receipt 族。peer Agent portable historical evidence 中的 receiver 与独立 receipt 仍保留，且 MUST 绑定本地接收方；其独立接纳时间不得混同原 producer 时间。

current 成功项按序为 `{selector,status:"resolved",key,checked_at}`。key 复用 closed `StationSigningKey {actor, verification_method, public_key_b64u, authorization_ref}`：actor/method 必须与 selector 相同，32-byte Ed25519 public_key_b64u 必须规范无填充 base64url，authorization_ref 必须为该 key 的真实适用 accepted 授权 Event。当前 Agent 与设备都使用同一入口；Station 可将请求有界拆为既有 peer current 16-selector 查询，转换后仍须核对原 self method/actor，不能放宽总体预算或省略来源验证。

**不缓存 current 授权（normative）**：每次 current 验证 MUST 发起此有界查询。结果只能供请求它的那次验证；同次批处理、或结果产生前已经在途且完全相同的查询 MAY 合并，MUST NOT 将完成结果用于未来 Signal、操作或重连。checked_at 只记录求值时刻，不是租约，不产生 TTL 复用权。稳定公钥 bytes MAY 缓存，但缓存命中不能跳过 fresh current 查询；客户端不建立跨 Realm checkpoint 失效扫描或 signer 订阅。服务器实际写入仍逐次授权。迟到响应、会话/账号变化、已知相关撤销或 Signal TTL 失效时不能继续消费结果。每次 Signal 查询的网络成本是此合同的明确代价，后续优化不得以 TTL 缓存冒充精确失效。

历史普通设备成功项按序为 `{selector,status:"resolved",key,accepted_at}`，key 是独立 closed `HistoricalDeviceSigningKey {actor, verification_method, public_key_b64u}`。Station MUST 从 exact Event 原 `StationAdmissionProof` 已签入的 `producer_verification_method`、`producer_signing_key_did` 与 `accepted_at` 取得实际历史公钥和原 producer 接纳时间，并验证 Event/producer proof/admission 的 exact digest、签名、origin Station 与 signer/device 绑定。依据 [event-and-patch §3.1](../models/event-and-patch.md)，origin 已在与设备撤销共享的持久线性化边界内完成授权；后来 revoke、fence、换代或当前目录 NegativeHit MUST NOT 追溯否定此前合法接纳。MUST NOT 使用当前 `keys/query` 或后来授权补认过去签名，也 MUST NOT 把 Station signer evidence ref 冒充 producer evidence。此分支不新增 mandatory Device ASRE、不返回虚构 authorization_ref 或 signer_evidence_ref；其完整依据是请求绑定的原 accepted Event 与 admission。

历史 Agent 成功项按序为 `{selector,status:"resolved",key,accepted_at,signer_evidence_ref}`，key 使用上述 StationSigningKey 并保留真实 authorization_ref，供端到端历史 MLS leaf 绑定使用。Station MUST 验证 exact Event 原 producer evidence 与本地适用的 admission/独立 receipt，以原接纳语境确认 Agent key/授权。accepted_at MUST 等于原 producer admission 时间，MUST NOT 填入 receiver 独立接纳时间。signer_evidence_ref 是 Station 实际验证所用 immutable frozen 历史来源地址，不是客户端可独立使用的完整 Event 证书；客户端不 hydrate。它 MAY 与 Event 内原 producer_signer_resolution_evidence_ref 不同，但 Station MUST 验证两者的真实来源关系。不得以后来 current 授权修补历史，或因历史 signer 后来离开/撤销而否定有效历史。

所有不可用项按序为 `{selector,status:"unavailable"}`。拒绝/缺失结果不得提升消息为 verified。当前分支的撤销/冲突/过期与历史原接纳无效/缺材料均使用此同形结果，不能以细分 reason 泄漏隐藏状态；服务器内部 MAY 记录原因。

Station MUST 将原 accepted Event、admission 与验证其签名必需的来源及保留关系维持在同一耐久接纳边界；该要求也适用于 ordinary DataEvent，不能仅给 Control Event 保留历史 Station signer 来源。GC MUST NOT 先删除仍可读取 Event 所需的来源。原 Station signer ref 沿现有治理依赖接口精确定位，已完整验证的耐久状态可复用，不重新拉取整段历史。缺失或损坏不可把裸缓存公钥当作成功；应 unavailable，正常新接纳不得以“以后再补”跳过保留义务。

历史结果 MAY 按自己 Station/recipient、Realm、exact Event、派生本地 receiver、完整 actor/device/method、原 producer admission 坐标与适用 Agent source ref 缓存；MUST NOT 跨账号或模式复用，不授予后续读取或 current 权限。客户端仍验真实 producer 签名、历史 MLS active leaf/epoch/group、AAD/AEAD 与 replay/TTL；自己 Station 成功不等于加密内容认证成功。minimal-metadata 不使用本普通 signer 查询，继续其专用 MLS 身份合同。

请求 canonical JSON MUST ≤64 KiB，完整响应 ≤1 MiB，单结果 ≤16 KiB；无分页或递归依赖下载。请求字节超限为 `413 payload_too_large`，schema/count-only 错误为 `422 schema_violation`，合法请求无法返回预算内完整结果为 `limit_exceeded`，不得返回部分成功。HTTP/gRPC/MQ 采用同一请求、结果与角色边界。

### 5.7 已登录当前 Principal 与 PCR 定位

普通已登录客户端 MUST 使用 [identity-did.md §4.2.3](../identity/identity-did.md#423-已认证账号的当前-principal-与唯一-pcr) 的 `ak.self.current_principal.read.resolve.v1`，取得 exact AccountId 的已接纳 current projection 与唯一 PCR。Station 验证外部方法历史；客户端只校验请求/会话/route 与字段绑定，不下载公开 attestation/history 或账号审计闭包。`observed_at` 与 projection `updated_at` 均不授予未来操作权限。本入口只解决已认证账号定位，不替代首次 Station 接入、公证服务或媒体路由绑定；Realm genesis notary 见 §5.8，已加入 Realm 的媒体服务绑定见 §5.9。

### 5.8 Realm genesis 的 notary 签署输入

`ak.self.genesis_notary.read.resolve.v1`（`POST /_arkret/self/genesis-notary/query`）向已认证账号返回它即将 author 的 Realm genesis 所需的 notary 配置。它是 §3 的签署准备输入，不是授权结果：成功不创建 Realm、不预留标识、不授予 create 或 authoring 权限，也不替代 caller 对 `ak.realm.create` 及其所在 bootstrap unit 的真实签名。

closed `GenesisNotaryRequestBody` 字段按序为 `request_id, account_id, intended_purpose`。`account_id` MUST 逐字等于当前认证会话的完整账号，且其 Station MUST 是服务本请求的自己 Station。`intended_purpose` 是 closed `collaboration | direct_conversation`，MUST 等于 caller 将写入 genesis 的 `purpose`；`principal_control`、`agent_control` 与 `applet_managed_control` 的 signer 由各自已接纳的身份规则确定，MUST NOT 从本入口取得，服务器也 MUST NOT 以服务密钥替代 principal、设备或 Agent 的 signer。

closed `GenesisNotaryOutcome` 字段按序为 `request_id, account_id, intended_purpose, notary, observed_at`。`notary` 复用 [realm.schema.json](../../artifacts/schemas/realm.schema.json) 的唯一 `notary` 类型，是可逐字写入 `payload.object.notary` 的完整值。Station MUST 按 [event-auth-state-resolution.md §6.5](../authz/event-auth-state-resolution.md#65-notary-control-cellnormative) 的默认与本部署 trust domain 已接纳的 policy 确定该值，并对其中每个 descriptor 完成 service DID 的 method-native 当前状态验证与该 verification method 的 assertion 能力核对。descriptor 的 `verification_method` MUST 由 Station 按其真实 Seal 签名密钥选定并逐字返回；客户端与共享 SDK MUST NOT 以固定 fragment、DID 字符串拼接、describe 字段或另取的当前 DID Document 构造它。结果 MUST NOT 携带 method history evidence、witness 记录、normalized DID Document、signer evidence 闭包或 Realm 标识。

客户端在签署前 MUST 核对：closed 结构与预算、`request_id`、完整 `account_id` 与当前会话/预期 Station route、`intended_purpose` 等于自己将写入的 `purpose`，以及每个 descriptor 的自洽性——`verification_method` 的 controller DID 经登记 adapter 投影等于该 descriptor 的 `actor_id`、`key_kind` 与 `jose_algorithm` 是登记的 active 组合、`frozen_public_key_digest` 等于 `frozen_public_key_b64u` 解码字节的 SHA-256，且 `actor_id`、`verification_method`、`frozen_public_key_digest` 三个维度在全部 slot 及其并集内各自不重复。本两类 purpose 的每个 descriptor 的 `actor_id.kind` MUST 为 `service`。signer 归属由部署 policy 决定：默认是 `account_id.station_id` 所属服务身份，部署也 MAY 指定已接纳的独立 notary 服务；客户端 MUST 按结果原样使用，MUST NOT 把非本 Station 的 signer 替换成自己的 Station，也 MUST NOT 因它不是本 Station 而自行增删 slot。任一项不符 MUST 放弃创建；MUST NOT 改写、补齐、部分采用或与本地默认值合并该值，也 MUST NOT 为核对它下载 service DID method history、witness 记录或 signer evidence 闭包。

`observed_at` 只标记本次观察，MUST NOT 被当作有效期或授权租约。一旦 genesis 被接纳，冻结的 descriptor 就是历史 Seal signer 事实：Station 后续更换签名密钥 MUST 走 `ak.realm.notary` Control Move，MUST NOT 追溯改写已接纳的 genesis 值，也 MUST NOT 因本结果陈旧而使已接纳 Realm 失效。一次结果只用于本次创建意图；账号、Station 或 session 变化后 MUST 重新查询，迟到结果 MUST NOT 安装。

请求与响应 canonical JSON 各 MUST ≤ 65536 bytes。请求字节超限 MUST 返回 `413 payload_too_large`；closed 字段/类型不符或 purpose 不在值空间内 MUST 返回 `422 schema_violation`；合法响应无法在预算内完整返回 MUST 返回 `limit_exceeded`。未认证沿用既有 401。错会话账号、错 Station 或目标不可见 MUST 返回同一 `404 not_found`。已认证且可见但本 Station 尚无可用已验证 notary 配置——签名密钥未就绪、部署 policy 依赖缺失或方法状态未决——MUST 返回 `503 temporarily_unavailable`，MUST NOT 返回占位 descriptor、空对象或旧缓存。

### 5.9 已加入 Realm 的媒体服务绑定

`ak.self.media_service_binding.read.resolve.v1`（`POST /_arkret/self/media-service-bindings/query`）为已加入 Realm 的成员返回该 Realm 当前已接纳 `ak.component.realm.media_service.v1` cell 所锚定媒体服务的已验证路由与签名公钥。它只解析服务身份、用途与路由，MUST NOT 被解释为加入通话、领取 backend token、释放媒体密钥或授权明文可见服务。

closed `MediaServiceBindingRequestBody` 字段按序为 `request_id, realm_id`。请求 MUST NOT 携带 caller 自选的 service id、DID、base URL、候选 origin 或 method evidence；服务身份只从该 Realm 当前已接纳 cell 取得。

closed `MediaServiceBindingOutcome` 字段按序为 `request_id, realm_id, seal_basis, route, signing_keys, observed_at, expires_at`。`seal_basis` 是 Station 完成本次可见性与 cell 求值的完整 accepted antichain。`route` 使用唯一 `ServiceResolutionProjection` 类型（[service-surface.md §2.6](./service-surface.md)，字段顺序 `service_id, service_kind, did, method_history_head, version_id, resolution_event_ref, base_url`）；其 `service_id` MUST 逐字等于该 cell 当前值的 `service_id`，`service_kind` MUST 为 `media_service`。`signing_keys` 是 1..16 个 closed `{verification_method, public_key_b64u}`，逐项取自同一已验证当前 DID Document 中该服务的 assertion 能力 Ed25519 公钥；`verification_method` 在结果内唯一，其去 fragment 的 controller DID MUST 等于 `route.did`。结果 MUST NOT 携带 method history evidence、witness 记录、normalized DID Document、describe 全文或任何第三方 attestation 闭包。

Station MUST 逐次检查本次认证会话对该 Realm 的当前成员可见性，再在同一观察下读取已接纳 cell，并按 [service-surface.md §2.6](./service-surface.md) 完成 DID method-native 当前状态验证、唯一 ArkretService 入口选择与 describe 反向绑定，同时保持已接纳 method 状态不回退。不可见、非成员或该 Realm 没有已接纳媒体锚定统一 `404 not_found`；可见但依赖不足、方法状态未决或 describe 反向绑定尚未完成 MUST 返回 `503 temporarily_unavailable`，MUST NOT 返回空 route、旧缓存或未验证候选。检测到同一 service DID 的分叉或状态回退 MUST fail closed，MUST NOT 改用另一个候选 origin。

客户端 MUST 核对 closed 结构与预算、`request_id`、`realm_id`、完整账号/Station/会话与预期 route，并把 `route.service_id` 与自己已安装的 `ak.realm.media_service` 当前值逐字比较；不相等 MUST fail closed（`media_service_binding_uncovered`），MUST NOT 采用结果中的路由。客户端还 MUST 核对该 cell 的 `ice_config_endpoint` 与每个 `foci[].token_endpoint` 的 origin 落在 `route.base_url` 之内，再向它们发起请求。`participant_binding.issuer_kid` 与 ICE config 响应签名的 kid MUST 命中 `signing_keys` 中的某个 `verification_method`；不命中 MUST 返回 `token_issuer_unauthorised`。客户端 MUST NOT 为验签逐 token 在线解析 DID，也 MUST NOT 自行获取 service DID 日志、witness 记录或 describe。

`expires_at` 只界定本结果中路由与签名公钥的复用窗口，MUST NOT 晚于 `observed_at` 之后 300 秒，也 MUST NOT 超过 Station 自身已验证 method evidence 或绑定的有效边界；它不是授权租约，不延长任何 backend token、TURN credential 或 participant binding 的 TTL。窗口内该 cell 变化、Realm 成员或 Circle 资格变化、账号或 Station 切换以及已知的 service 分叉 MUST 立即使结果失效；过期或失效后 MUST 重新查询，迟到结果 MUST NOT 安装到新上下文。

本结果不改变媒体明文与密钥释放边界：`media_service_decrypts`、`plaintext_visible_services`、当前 epoch `security_frontier_digest` 覆盖与用户明确确认仍按 [media-service-binding.md §8.2](../crypto-media/media-service-binding.md) 在客户端判定，SFrame/AEAD、录制与转写 exporter label、backend token 分支与 TTL 检查继续由客户端执行。

请求与完整响应 canonical JSON 各 MUST ≤ 65536 bytes。请求字节超限 MUST 返回 `413 payload_too_large`；closed 字段/类型或数组项数非法 MUST 返回 `422 schema_violation`；合法响应无法在预算内完整返回 MUST 返回 `limit_exceeded`，MUST NOT 截断 `signing_keys`。未认证沿用既有 401。

## 6. 规范与 conformance

full/e2ee 客户端 conformance 检查请求绑定、结果消费、端到端密码学和恢复行为；服务器 conformance 检查治理历史、DID/外部证据、admission、当前授权与共享增量状态。客户端没有治理历史 verifier 不构成不合规；服务器接受未经验证的远端材料构成不合规。

相同 fixture 可以提供服务器有效/无效输入及客户端成功/pending/错绑定结果，但 MUST 分别标明角色；不能要求客户端执行服务器 verifier runner 才能声明产品 profile。SDK 发布同时包含两种角色时，仍须分别证明各自适用的条款。

第三方 service delegation、公开身份声明及其发行者历史由自己 Station 验证；只有具体 operation 已登记的结果才能交给普通客户端消费。Realm genesis notary 与已加入 Realm 的媒体服务绑定分别由 §5.8、§5.9 的登记载体承担；尚未登记专用载体的第三方服务资格仍由各自 operation 的既有合同处理，普通客户端只能把相应功能视为未验证/不可用。Conformance artifact 是 `service-surface.md` §3 规定的 verifier/admin/auditor portable claim，不是普通客户端的运行时结果。实现 MUST NOT 为上述空档新造通用 service 结果，也不得让普通客户端回退到自行验证 artifact 或发行者历史。服务器代核验不能将自报 claim 变成独立认证。
