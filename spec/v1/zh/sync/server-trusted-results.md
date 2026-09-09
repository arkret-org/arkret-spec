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

## 6. 规范与 conformance

full/e2ee 客户端 conformance 检查请求绑定、结果消费、端到端密码学和恢复行为；服务器 conformance 检查治理历史、DID/外部证据、admission、当前授权与共享增量状态。客户端没有治理历史 verifier 不构成不合规；服务器接受未经验证的远端材料构成不合规。

相同 fixture 可以提供服务器有效/无效输入及客户端成功/pending/错绑定结果，但 MUST 分别标明角色；不能要求客户端执行服务器 verifier runner 才能声明产品 profile。SDK 发布同时包含两种角色时，仍须分别证明各自适用的条款。

第三方 conformance artifact、service delegation、公开身份声明及其发行者历史由自己 Station 验证并提供带来源和有效期的结果。服务器代核验不能将自报 claim 变成独立认证；客户端不必下载完整 artifact/authority 证据链。
