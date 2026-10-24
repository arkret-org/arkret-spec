---
title: Realm Bot／Ghost 与私有控制流
status: candidate
normative: true
stability: v1
updated: 2026-10-20
---

# Realm Bot／Ghost 与私有控制流

规范关键词遵循 [规范语言](../conformance/normative-language.md)。

## 1. 范围与身份

本合同只适用于 Applet 在普通协作 Realm（含原生 Portal）中创建的 Bot／Ghost。
普通 Account、Organization 与个人 Agent 的 AccountId、独立 DID、PCR、恢复和授权合同保持各自定义。
Applet **MUST NOT** 为本合同主体创建 Account 或独立 PCR；Applet 无须兼任 Station。
本合同不定义兼容解码、旧身份映射或账号迁站。

`RealmActorId` 是仅含 `realm_id, principal_id` 的 closed object；`ActorId` 新分支是
`{kind:"realm",realm_actor_id:RealmActorId}`。其字段定义见
[common-ids](../../artifacts/schemas/common-ids.schema.json)。比较、去重、授权、成员资格、索引和
MLS credential **MUST** 使用完整带 kind 的 ActorId，不得降为裸 DID core、显示名或 DeviceId。
AccountId 仍永久绑定 `principal_id, station_id`；RealmActorId 永久绑定 RealmId 与独立主体 DID core。
治理交接改变当前治理 Station，**MUST NOT** 改变 RealmId、RealmActorId、主体 DID、DeviceId 或 MLS 身份。

每个主体持有独立 did:webvh。创建时 **MUST** 方法原生验证完整 WebVH inception／连续日志／witness，
控制方法 **MUST** 为 DID Document 声明、且与 active updateKeys／nextKeyHashes 分离的方法；原生 update key 只能签 DID 日志，不能签本合同控制 Event、Device 或业务。
校验 `project(initial_resolution.did) == actor_id.realm_actor_id.principal_id`，并保留完整原 DID、
方法证据和原始签名。不得从 core 反拼 DID，不得以 Service 声明、namespace 命中或自带公钥验签替代身份权威。
Applet **MUST** 安排 DID 文档与完整原生日志的托管，并保管主体控制密钥、Device 私钥与私有 MLS 状态；可使用公共运行时、独立托管组件或 Station 的托管设施，但不要求成为 Station。治理 Station 管理授权、accepted 控制状态与公开验证材料，不强制承担原始 HTTP 托管。受管 WebVH 的 inception **MUST** 设置 portable=true，后继 **MUST** 保持该有效能力；这只保障 Applet 的合法托管迁址，不是 Realm 治理交接前置。
治理方或管理员有权暂停主体，不因此取得主体私钥或代签权。

Bot／Ghost 的 SCID **MUST** 独立于 Service 和 controller；托管 host/path 与管理 Service 的地址独立，
不要求同域、额外路径分段或 actors namespace 匹配，不产生受管 DID 地址空间的排他占用。原生 URL、安全网络目标、完整连续日志、持钥证明与创建授权仍全部验证。
Bot／Ghost 的 AppletId、初始角色和创建来源不可改；当前管理 Service 是独立状态。
同 core 合法密钥／定位更新保持身份；换 core 创建新主体。退役身份保留占用，不得重新创建复活。

主体只参加自己的 Realm 及其中明确授权的 Circle。同 Applet 在另一 Realm 创建另一个完整主体。
不得加入个人 PCR、个人 Agent 控制 Realm、固定参与者 DirectConversation 或个人 Agent Sidecar。
Circle-only 场景仍满足父 Realm 最小成员前提，但父成员资格不自动授父内容读取。
不得为解决依赖读取而放开父 Realm；使用既有获准 exact 依赖读取。

对 Realm Bot／Ghost 的 mention 使用同 Realm 的完整 `subject_actor_id`，由 Applet 的获准原生 Device
内容流消费者在验证原件并完成必要的 MLS 解密后处理，按完整接收 ActorId、source EventId 和用途耐久去重。
不生成普通 Account Notification、不借 Account subscribe、不拼造账号或增加操作／权限。
mention 不授予实际执行权；未知外部执行结果不得重做，详细边界见
[`strand-and-message.md` §9.4.2](../models/strand-and-message.md#942-普通-mention-的通知派生)。

## 2. 私有控制流

`scope_ref` 与 `stream_ref` 增加同形 closed 分支 `{kind:"realm_control",realm_id}`。
每个 Realm 至多一个，所有本 Realm 的 Applet 主体共用；不产生新 RealmId、独立成员集、authority root 或任期。
这只是控制 Event 的归属与隔离流，**MUST NOT** 被当作消息、Blob、Call、MLS、KeyPackage、
Device 业务授权、Circle／Sidecar 创建或通用 capability 的 effective scope。
管理权限在所属 Realm 或 candidate 指定 Circle 核验，不给此流通用 read／write grant。

首个成功 `ak.realm.actor.create` 原子初始化此流，position=0、previous=null；没有另一个 stream.create
或 Realm genesis。并发首建在当前治理方锁内排序，只能有一个 position=0。
未初始化流不出现在 handoff heads；初始化后 **MUST** 永久保留流身份、head 与历史，最后一个主体退役也不删除。
治理换任继续原 position／predecessor；各流独立连续，不制造全 Realm 总序。

本流 Event 是 `durable_event` 与 reducer input，接受必须有真实 RealmCommit；不是 actor-private 无 Commit Event。
普通成员的 snapshot、scan、subscribe 和复制权不含此流。不得用成员资格、公开 Profile 或业务 Event
反推读取控制流的权利。本合同只新增 §8 的 exact 材料操作，不新增公共全流 scan。
向获准主体提供 exact 原件会暴露该原件的 position；不得宣称这种披露隐藏了所有活动量，或把过滤结果当无遗漏证明。

## 3. 接纳、权限与审批

新增 Event 的 payload 与签名 transcript 见 [realm-actor schema](../../artifacts/schemas/realm-actor.schema.json)。
治理方 **MUST** 从 kind、完整 actor、真实签署方法与 scope 选择唯一接纳分支；零匹配或多匹配拒绝。

| Event | 实际 producer | 接纳与效果 |
| --- | --- | --- |
| `ak.realm.actor.create` | 获准 Applet Service | `realm_actor_creation`；§6 的候选及真实创建许可；初始化身份／控制／manager／双 gate／generation |
| `ak.realm.actor.control.update` | 主体当前控制方法 | `realm_actor_control`；同 core 连续性、旧方法 Event 签名、新方法 PoP、control CAS |
| `ak.realm.actor.status.set`，owner | 主体当前控制方法 | 原生控制；仅改 owner gate，actor 必须等于 payload.target_actor_id |
| `ak.realm.actor.status.set`，governance | 有权 Account 的真实 Device | 普通 capability 与适用 review；`ak.realm.actor.manage` |
| `ak.realm.actor.devices.reset` | 主体当前控制方法 | generation CAS，严格 old+1；不创建新 Device |
| `ak.realm.actor.manager.change` | 新接受的主体控制方法 | §7／§10.6 的原生更新权转交、治理许可及新 Service 接受；manager、最终 control 与 generation 原子改变 |
| `ak.realm.actor.recovery.begin` | 当前管理 Service | §10 的持续恢复权、原生计划、新 PoP；先暂停并隔离旧设备 |
| `ak.realm.actor.control.reset` | 当前管理 Service | §10 的 exact pending 与已发布原生证据；完成同身份恢复 |
| `ak.realm.actor.recovery.set` | 有权 Account 的真实 Device | 具名 manage 与适用审批，设置恢复许可；不授业务权限 |
| `ak.device.authorize`／`ak.device.revoke` 的 realm 分支 | 主体当前控制方法 | §5 的有限设备授权或真实撤销安全事务 |
| `ak.profile.create`／`ak.profile.update` 的 realm 分支 | 主体当前控制方法 | 本人私有资料维护；全主体 create-once 与后继 CAS；公开使用另核实际 scope 的 publish／review |

上述控制分支都只写本主体所在 realm_control。Service 或 Device 签名 **MUST NOT** 冒充控制方法；两个恢复 Service 分支按§10单独验证。
create 与业务 Event 的 `applet_id`、真实 `authorization_ref` 仍必填且精确绑定。
本人控制分支要求 `applet_id` 等于 accepted identity，**MUST NOT** 携带 `executed_by` 或 envelope
`authorization_ref`；这是精确的 realm actor＋允许 kind＋控制方法例外，不是全局取消 Applet 授权。
governance status 与 recovery.set 不命中例外。recovery.begin／control.reset 是仅限当前 manager Service 的另一封闭例外，按§10核 accepted 恢复权且不带业务 authorization_ref。manager.change 在 payload 中另持真实 `management_authorization_ref`。

创建保留 `ak.applet.bot.provision`／`ak.applet.ghost.provision`，按 candidate.creation_scope 验权。
创建许可与安装是不同事实；安装不会自动创建主体、Device、成员、Profile、grant child 或 MLS 成员。
持续自动 Ghost 许可可在明确 external protocol／instance、scope、配额、过期与当前 Service 安装约束下多次创建，
每次仍核真实许可但不重复要求管理员交互；Policy 要求逐候选审批时才进入对应审批。
管理员主动创建 Bot 已通过真实管理授权与适用审批时，不再伪造一轮 Applet 向管理员的同意申请。
批准必须绑定精确 candidate／Service Event，不批准一个未确定主体身份的占位请求。

`ak.realm.actor.manage`、`ak.realm.actor.manager.change`、`ak.realm.actor.audit` 使用
closed `{kind:"realm_actor",actor_id}` resource，必须同时匹配完整 actor 与所属 Realm。
管理员名称、membership、持有同 key 或相同 AppletId 不自行授权；Bot／Ghost 不成为独立审批批准人。
审计许可只授具名目标的必要材料，不能枚举本流其它主体。

governance 与 owner 各有 active／paused／retired 独立 gate，独立 CAS。
任一 retired 是不可逆终态；否则任一 paused 阻断业务；owner resume 不能解除 governance pause。
两个 active 仍需当前 manager、安装、grant、Device、成员与 Policy 全部有效。
卸载或 paused 后允许合法控制更新、撤销和安全收尾；不因此恢复业务、新设备权限或 grant。
retired 禁止控制更新、manager 转交、重新授权或恢复，仅保留获准审计与收权。

## 4. Current、CAS 与派生

所有新 row 都是 `selector,source_stream_ref,revision,value`，source_stream_ref 必须是所属 Realm 的
realm_control；revision 复用 `{commit_id,stream_position}`，来自原接受 Commit，不是整流最新 head。
每个 selector **MUST** 携带完整 realm actor；多主体流不得使用 PCR 的单主体 selector。

| family | 额外 selector | value／writer |
| --- | --- | --- |
| realm_actor_identity | actor_id | applet_id、actor_role、creation_service_id、creation_ref；仅 create |
| realm_actor_control | actor_id | resolution、control_method_kid；create／control.update／control.reset／manager.change |
| realm_actor_manager | actor_id | service_id、registration_ref、binding_ref；create／manager.change |
| realm_actor_status | actor_id、gate | active／paused／retired；create 两行／status.set 指定行／recovery.begin 的 owner paused |
| realm_actor_device_generation | actor_id | current_device_generation_ref；create=1，devices.reset／manager.change／recovery.begin=old+1；control.reset 不再递增 |
| realm_actor_recovery | actor_id | kind、enabled、pending；create／recovery.begin／control.reset／recovery.set／status.set(retired) |
| realm_actor_device_authorization | actor_id、device_id | 准确 realm Device 授权及原 authorize EventId；device.authorize |
| realm_actor_device_revocation_proposals | actor_id、device_id | 原不可变 proposal 与真实命令结果折叠；device.revoke |
| realm_actor_profile | actor_id | profile_id 与允许的 Profile 值；profile.create／update |

create 的所有行、去重／配额／tuple 约束、原件、签署事实、Commit 和结果 **MUST** 同事务成功或全部不写。
创建后没有 Device／Profile 行是合法未创建；identity／control／manager／双 gate／generation／recovery 缺项是错误，不能兜底初始化。
expected_revision 只在 typed payload；target 行首写显式 null，后继精确比较原 row revision。
治理任期变更不改已有 row 的原 revision。写入仍锁内检查最新 gates／撤销／manager，历史 revision 不构成当前 allow。

新增纯派生：`realm_actor_accepted_event_ref` 是真实接受 Event／Commit 的四坐标；
`realm_actor_resolution_projection` 是 create.initial_resolution、control.update／manager.change.next_resolution 或 control.reset 的 exact pending target，加
resolution_event_ref=原 EventId、updated_at=Event.created_at；`realm_actor_profile_id` 在 create 时由 EventId
retype，在 update 时为精确 target_ref；`realm_actor_profile_value` 在锁定的 actor-local Profile 上按允许字段创建／patch。
来源坐标在 Commit 定值后、同一接受事务写入，producer 不自报，且不进入自身 Event／Commit preimage。
selector 的 literal 只允许 actor.create 的 owner／governance 两行及 recovery.begin 的 owner pause，不是通用循环或表达式。
writer condition 可精确读取 `envelope.actor_id.kind`；admission envelope_path 只允许 `actor_id.kind`、`scope_ref.kind`。

## 5. Device、HTTP 与业务身份

Device 仍用原 DeviceId，authority key 为完整 RealmActorId＋DeviceId。
`ak.device.authorize` 的新 binding 为 `realm_managed_delegation`，由 current 控制方法签 Event，
Device 自己用 Ed25519 签 possession proof。authorized_by 必须等于 actor.realm_actor_id.principal_id。
payload 的 `expected_control_revision` 与 `expected_device_revision`（仅首次为 null）均锁内 CAS；
authorized_generation_ref 等于本主体当前 generation，不得由空目录、Service epoch、DID version 或首 Device 初始化。

raw Device PoP 分域为 `ak.device_authorize_realm_actor_possession_proof.v1`，输入
`UTF8(context + LF) || JCS(transcript)`。完整 transcript 是从 envelope 注入 actor_id，加 payload 的
device_id、device_public_key_did、hpke_key、algorithms、device_key_algorithm、authorized_by、
authorization_binding_kind、authorized_generation_ref、not_before、expires_at、scopes、applet_id、
expected_control_revision、expected_device_revision。不得含签名、Event／Commit ID、recovery_session、
pairing challenge 或第二份主体字段。expires_at 必须有限非 null；非空 scope／action 配对全部属于同一 Realm。
列表按既有 canonical 排序去重规则验原输入，不重排后验签。

首 Device 不依赖尚不存在的 Device、child 或 membership。每次新授权仍逐 scope 验 active 安装和新增许可。
永久撤销 DeviceId 不得重新授权，替换须新 DeviceId／key。revoke 仍创建真实 revocation_pending，
由接纳事务导出 exact 授权实例与 generation，沿原 proposal／terminal 事务折叠；不能把 pending 当永久撤销。
首次接纳 MUST 在同一事务保存原请求摘要、Event／Commit、signer fact、exact DeviceAuthorize 引用与原 generation、
pending 命令 ledger、设备隔离与必要 MLS removal 意图。缺少完整 ledger 不是 pending，读取 MUST unavailable。
当前治理方的撤销 worker MUST 锁内验证当前治理资格与原命令状态；每笔 proposal 的 terminal 只写一次，
相同结果和坐标的 exact 重试返回原件，改变结果或原坐标 MUST conflict。
accepted MUST 与永久撤销效果及必要收尾任务入账原子提交；它不表示所有异步 MLS Remove 已完成。
rejected MUST 与明确终止该命令的记录原子提交，不得产生该命令的永久撤销或后继不可逆效果。
拒绝不删除原提案，不清除其它提案的 pending／accepted，也不撤回独立 generation fence 或状态 gate。
reset 仅 fence 旧 generation。控制 key 更新默认不撤 Device，需要时显式 reset。
runtime 使用设备前必须核对原 Event／Commit、完整 actor、key、PoP、授权实例及自身持有的私钥。

`Arkret-Managed-Device` 是 base64url_no_pad(JCS) 的六字段：actor_id、device_id、authorization_event_id、
applet_id、effective_scope、nonce；actor_id 仅 realm 分支。请求直达所属 Realm 当前治理方，以 accepted
Device key 按 ak.http_signature.scenario.applet_managed_device.v1 做 RFC9421 签名。签名有效不等于业务有权，不发 SessionGrant。

控制 HTTP 场景 `ak.http_signature.scenario.realm_actor_control.v1` 使用
`Arkret-Realm-Actor-Control=base64url_no_pad(JCS({actor_id,control_ref,nonce}))`；control_ref 是 current
control 来源的完整 CommittedEventRef，不能从两字段 revision 猜 EventId。
当前已接受控制方法按本场景登记的组件签 RFC9421。
只允许 §3 本人控制命令、§8 材料及 exact 结果恢复；不得发消息、MLS 或 capability grant。
首次创建由 Service 认证；管理绑定可信时可帮助 runtime 读取 exact current，但不能代签控制 Event。
控制轮换未知结果时保留旧方法直到恢复原结果。当前方法无法认证时，由原登记 Service 的受限 ledger 权限恢复创建结果，或使用新 current 方法恢复本人结果；失效 key 不具有 HTTP 认证资格。

KeyPackage claim／consume、Welcome、MLS sender／receiver、Welcome 收件队列、receipt、
历史 signer 查询及 credential 都 **MUST** 支持明确 realm actor 分支，和 Account／Agent 分支互斥。
Realm Bot／Ghost 的受管设备收件队列 **MUST** 只承载 `delivery_kind="mls_welcome"`，
沿用现有 list、opaque cursor、耐久处理及累计 ACK。它们不是 DeviceMessage 的发送方或接收方，
不得调用 `ak.self.device_messages.command.send.v1`；该操作不在受管设备白名单中。
若受管设备收到 `device_message` 或其它未登记分支，**MUST** 拒绝处理且不得 ACK 覆盖该项，
不得将其转换成 Welcome 或伪造 AccountId。频道文字、图片、提及与回复继续走获准原生 Event 内容流。
普通 Account／个人 Agent 的 DeviceMessage 机制不变，不新增操作、权限、审批或私有消息通道。
固定验收向量 `ak.vector.sync.delivery_ack.v1` 包含 Welcome-only 与非法 DeviceMessage 不处理／不 ACK 的分支。
路由由已验证 RealmId 的当前治理方决定，不能塞入假 account_id 或用 principal-only fallback。
RFC9420 BasicCredential 使用完整 ActorId 的 canonical bytes；Device 与 key 继续显式绑定。
每次提交、队列交付、读取和 MLS 接入重核实际 scope 的当前权限，撤权竞态不得因已有队列或签名有效而放行。
治理迁移导入尚未终结的队列／claim／cursor，迁移不自行加入／移除 MLS，也不传 Applet 私有 MLS 状态。

## 6. 创建与控制更新签名

唯一创建 payload 是 `ak.schema.realm_actor_create.v1` 的 RealmActorCreateCandidate，包含完整 actor、
Applet、Service、角色、128-bit 以上随机 request_id、creation_scope、registration_ref、
creation_authorization_ref、initial_resolution、完整 method_history_evidence、control_method_kid、expires_at、
仅 Ghost 必填的 external_ref、control_signature、recovery={kind:"manager_native",enabled:true}。所有精确成员以 closed schema 为准。
WebVH 证据遵守既有 1 MiB／4096 log entries 等限制。主体控制方法必须由这些原生证据授权。

candidate.control_signature 使用 `ak.realm_actor_creation_signature.v1`，签完整 candidate 仅删除此签名。
Service 再签包含 candidate 的 Event；Event actor 是 candidate.service_id 的 Service actor，无 executed_by；
envelope.applet_id 与 authorization_ref 逐字对应 candidate。candidate 不含最终 EventId 或 CommitId，依赖无环。
审批签名由提交外层保存，绑定精确 Event／登记摘要，不能回填到被批准 Event 内。

去重键为 RealmId＋AppletId＋request_id，固定完整 candidate bytes；Ghost 另锁 Realm／Applet／外部 tuple，
身份唯一性锁完整 actor。首次过期拒绝；已接受精确重试先验认证／披露权，再恢复原结果，不再扣配额或重建。
未知结果只可恢复／重试原请求，不能换 nonce 延长意图、取消尚未证明不存在的效果或重造主体。

control.update 保留旧有效方法签完整 Event；新方法用
`ak.realm_actor_control_acceptance_signature.v1` 签
actor_id、expected_revision、next_resolution、method_history_evidence、next_control_method_kid 的精确注入 transcript。
旧方法批准、新方法 PoP、同 DID core 原生连续性缺一不可。顺序是持久化意图、DID 中保留有效旧方法并加入新方法、
Realm 接受更新、最后移除旧方法；未知结果先恢复原结果再移除旧方法。
同方法更新 DID 历史／locator 仍签新 PoP。没有旧有效 control 方法时 **MUST** 使用§10的已登记同身份恢复，不能借正常轮换跳过旧签。全部合法原生更新材料也丢失时保持不可用；本合同不提供 Ghost 外部映射重绑或原身份退役后复活。
普通账号与 Agent 的既有恢复不受此限制影响。

五个 Realm actor detached context 为 creation、control_acceptance、manager_acceptance、material、recovery_acceptance，完整名见
[proof registry](../../artifacts/registry/proof-context-registry.json)。它们复用 closed Ed25519 signature：
context、signature_algorithm、verification_method、signed_digest、created_at、sig。
signed_digest=`sha256:lowercase_hex(SHA256(JCS(unsigned_projection)))`；实际签
`UTF8(context + LF) || JCS({context,signature_algorithm,verification_method,signed_digest,created_at})`。
sig 是 64-byte Ed25519 的 canonical base64url_no_pad。只删本族指定签名，保留嵌套签名；注入 transcript
逐成员重建，拒绝未知 context、附加字段或非 canonical 编码。Event producer_proof 与 RealmCommit 算法不改。

## 7. 管理 Service 转交

同 AppletId 可以换管理 Service，但必须先 owner paused，再由新 runtime 生成隔离的新控制 key，
用 §6 正常轮换接纳新方法，最后以新方法签 manager.change。owner gate 此时必须仍 paused；
current control update 必须晚于旧 manager binding，新公钥不同于旧 binding 时冻结的控制公钥。
比较真实公钥和原件，不只比较 fragment。旧 key 不得再作新命令签署者。

payload 锁 expected_manager_revision、expected_control_revision、expected_device_generation_revision、
expected_generation；new_generation 必须 old+1。new_service_id／new_registration_ref 绑定新 Service，
management_authorization_ref 是治理方授予该新 Service、该完整 actor 的真实管理变更许可，仍验当前 review。
新 Service 用 `ak.realm_actor_manager_acceptance_signature.v1` 签注入 actor_id／固定 applet_id 后，
只去掉 new_service_signature 的 payload transcript；主体新控制方法再签完整 Event。

一次接受原子换 manager、最终原生 resolution 与 generation，旧 manager 业务链和旧 Devices 失效。新 Service 不继承旧 parent／child、
安装 epoch 或 Device；独立取得安装／grant、显式 owner resume、授权新 Device 后才可业务使用。
governance gate 不受 owner resume 影响。中断保持 paused，以 exact 结果续跑，不自动回滚旧 key／manager。
新旧 Service 的登记与 scope 安装 **MUST** 并存；只切换完整目标 actor，不追加共享 DID 接管名单，不改变其它主体的登记、parent、manager、恢复许可或 Device。新 Service 不得因此管理同 Applet 的全部主体；原 Service 即使已无主体也不自动卸载。原 AppletId 与已验证 publisher/controller 来源不变，禁止跨 Applet 转交。

转交无需旧 Service 的普通业务签名，但 **MUST** 满足§10.6的原生更新权交接、主体有效新控制授权与原治理许可。只有日常 control key 或管理员许可不足以转交 DID；无合法原生材料不得接管同身份。
协议不转移私钥，也不能证明部署人员没有复制新 key；runtime 必须实际隔离新 key。
普通 Service 同 core 的端点／key 更新继续原 registration／DID 规则，不伪装为 manager.change。

本节只覆盖同一 Applet、全部数据与密钥完整保留的 Service 变更。保留历史控制/native 材料、Device 与 MLS 私态、原签 outbox、cursor/ACK、tuple、未决意图和固定结果，不表示旧 key、旧 Device 或旧 grant 永久有效。不同 Service 仍须执行上述隔离新密钥、原生更新权转交与 generation 递增；owner paused 时先依原合同终结 pending。旧共享 parent 继续服务其它主体，新 Service 已迁入主体不受下一次转交影响。

同一 ServiceId 只换机器／进程时，manager 与 generation 不因部署而变；旧实例 **MUST** 停止写入同一 custody journal、native next key 与 MLS ratchet 后再启新实例，高可用亦保持单一写序。数据副本或摘要相等不证明旧实例已停，也不授予治理权。同 Service 登记的安全 epoch 若改变，仍按其实际依赖处理授权失效。

DID 地址优先独立稳定。确需改变 host/path 时，按 identity-did 的同 SCID 原生迁址验证有效前驱 portable、直接前驱、预承诺更新 key、完整 history 与适用 witness，并经本合同 control/manager 接纳新 resolution。仅 Core 相同不足以接纳；历史 anchor 仍与其历史文档的完整 DID／原签字节严格匹配，不改写历史 VM。新定位从已验证 accepted resolution 得出，不从 Core 猜 URL，不只信 HTTP redirect；接纳新地址与完整证据后不依赖旧 host 永久在线。仅持旧 URL 的外部解析器在旧域名失联后未必能发现新址，本合同不新增全球 Core 查询服务。发布日志不可回滚，不重签 sibling，不以业务服务或治理方改变自动触发迁址。

Realm 治理交接沿 §9 完整移交所有 Service 登记、scope grants、管理 current、历史证据、pending/outcome、去重与聚合 quota；不搬 Applet 私钥、MLS 私态或 DID 原始托管，不要求各主体迁址或全部 Applet 在线签名。manager.change 与 handoff 以冻结 cut 和前态 CAS 排序，只有当前治理方接纳。普通 Account／个人 Agent 与 PCR 规则不变；丢失密钥恢复仍走独立恢复合同，本节不提供接管、退役复活或映射替换。

## 8. Exact 控制材料与历史验签

`ak.self.realm_actor.read.material.v1` 对应 `POST /_arkret/self/realm-actors/material`。
写入复用原 self Event submit。请求公共字段为 actor_id、purpose、request_nonce；nonce 为至少 128-bit
CSPRNG base64url，22–128 字符。current 加 1–16 个同 actor 唯一 selectors；event 加完整 target CommittedEventRef；
outcome 加原登记操作请求的 target_request_digest。禁止 wildcard、跨主体查找、无界设备列表。

控制方法可读自身材料；当前管理 Service 可读其主体必要材料，安装失效不使身份读取死锁；原 Service 可按私有
ledger 恢复自己创建／恢复意图的 exact 结果；真实 Account 必须有具名 audit 许可。普通成员／Device 不可读 current
或控制历史。首 Device 装配可由 Service 代取 exact authorize；Device 自取仅限自己的这一原件，仍用原授权列表中
有权的业务 effective_scope，不能把 realm_control 填进 Device scope。
无主体与无权限同 not_found 外观；无 ledger 或迁入不完整返回 unavailable，不能宣称未执行。

响应是 [RealmActorMaterial](../../artifacts/schemas/realm-actor-material.schema.json)：realm_id、actor_id、purpose、
request_digest、request_nonce、requester_actor_id、governance_generation、authority_ref、control_stream_head、issued_at、
expires_at、result、signature。request_digest 是完整本次读取请求 SHA256(JCS)，不同于原操作 target_request_digest；
requester_actor_id 来自真实认证 caller，不接受自报。authority_ref 沿已验证治理链，gen0 为 Realm genesis，后继为生效 handoff。
current、head、披露权限和 nonce 在同一 cut 获取，不拼接多次读取。最多 60 秒有效，且不得超过相关授权／方法窗口；
signature.created_at 等于 issued_at，issued_at < expires_at。签整个 host 仅删 signature，context 为
`ak.realm_actor_material_signature.v1`。它不是写入 allow 租约，所有写仍重核 current。

current/event 的 head 必非 null。outcome 可在主体创建前恢复完整 ledger 已记录的 intent／拒绝／取消；
仅当同 cut 证明此 Realm 控制流从未初始化时 head=null，不能据此推断该请求没执行。
旧任期 Event 保留原签 Event／Commit，外层由当前治理方签，不能改写历史任期。

current.entries 与请求 selector 一一同序、无遗漏无额外；每项为
`{status:"present",current_state:CurrentState,source_ref:CommittedEventRef}` 或
`{status:"never_written",selector}`。source_ref MUST 是同一读取事务中产生该 selector 当前值的真实
原 accepted Event／Commit：stream_ref 逐字等于 row.source_stream_ref，且为目标 Realm 的 realm_control；
commit_id／stream_position 逐字等于 row.revision，位置不得超过 control_stream_head。
原件必须存在且确为该主体 selector 的来源；原件缺失、来源不一致或交接材料不完整 MUST unavailable，
不得猜 EventId、用控制流 head 替代或返回 never_written。多个初始化 selector 可以引用同一个 create，
各项来源不必等于最新 head。source_ref 纳入既有整份材料签名与请求者、nonce、摘要、任期和窗口绑定；
需要原件时，调用者使用原 event 分支以该完整引用读取并验签。该字段仅扩展私有 current entry，
不扩展通用 CurrentState、公共读取、Device 披露或恢复资格，不新增接口、权限或审批。
只有尚未授权 Device、从未有 revoke proposal、尚未创建 Profile 可 never_written；已撤销／fenced 行保留。
identity／control／manager／双 status／generation／recovery 创建后必有，缺项 fail closed。
event 返回原 event、commit、producer_signer_fact，逐项校原 target 与签名；不声称提供全流证明。
outcome 返回原 target_request_digest 与登记的真实结果；accepted 必有原 Commit，pending／unknown 不等于完成。
Realm Device revoke 以原 self 请求摘要定位 closed `device_revoke` 结果，字段依次为
`status="device_revoke"`、`proposal_ref`、`device_id`、`authorization_ref`、`authorized_generation_ref`、
`state`、`decided_at`。两个 ref 都是同一 Realm 私有控制流的 CommittedEventRef；authorization 必须对应
该主体、设备在 proposal 接纳时解析的原授权实例及正整数代次，不能由调用者自报。
`state=pending|accepted|rejected`；pending 的 decided_at 必为 null，terminal 必为首次真实决定时间。
proposal Commit 只证明登记，原 submit_response_body 的 committed／duplicate 不代表永久撤销。
无已接纳申请才返回 unknown；已接纳但 ledger 缺失、来源不完整或相互冲突 MUST unavailable。
既有外层签名继续绑定完整主体、Realm、治理任期、请求摘要、nonce、请求者及时间窗口；权限和受限 Device
披露边界不扩大。治理交接 MUST 完整移交 ledger、第一次 terminal、原授权来源及待执行收尾任务；
接任方原样提供结果，不重算 terminal，不复活已永久撤销设备。
请求／响应各最多 4 MiB，超限整体拒绝，不能截断后签部分数据。

历史 producer fact 新增 realm_device／realm_control，共有 kind、event_id、actor_id、verification_method、
public_key_base64url、accepted_at。realm_device 另有 device_id、authorization_event_id、authorized_generation_ref；
不携控制流 position 或授权 Commit 坐标。realm_control 另有 control_event_ref，只向获准私有审计披露。
完整 DID／授权依据留在治理私态。SHA256(JCS(fact)) 在目标 Commit 计算 ID／签名前冻结，accepted_at 与 committed_at
相同；外层 target 坐标随后建立，不能放回 fact 形成自引用。
普通业务历史 signer 查询绑定原 target、完整 actor、实际 method，只返回必要公钥，不泄露控制 current、历史或列表。
Account 管理员与 Service 仍使用各自既有 fact 分支。

Applet authority material 只保留 Service 安装／grant 材料；被替代的 Account managed_source 和跨 PCR Device
scope confirmation 不再作为主体入口。Realm actor 材料使用本节唯一的 current／Event／outcome 合同；Account 跨站承运见下节。

### 8.1 Account 跨站私有审计材料读取（normative）

Account 调用自己的账号 Station 的 self material 入口。目标 Realm 在外站治理时，账号 Station **MUST** 使用
`ak.peer.realm_actor.read.material.v1`（`POST /_arkret/peer/realm-actors/material`）。closed 请求按顺序为
requester_account_id（完整 AccountId）、request（原 self material 请求），定义见
[peer_request](../../artifacts/schemas/realm-actor-material.schema.json#/$defs/peer_realm_actor_material_request_body)。不能向外站转发 bearer、
SessionGrant 或 DPoP，不能把服务器身份当作 Account，不能补造读 Event 或改用普通 scan。

账号 Station 先认证实际 Account 与当前 session／Device，从认证结果构造 requester_account_id，验证目标 Realm
当前治理链与目的站；按既有 S2S 场景签完整外层请求、operation、source／destination 与重放窗口。
治理 Station **MUST** 验证 requester_account_id.station_id 等于已认证 Source-Service-ID，且自身为目标 Realm
当前治理站。来源站只能声明本站 Account；授权求值主体是完整 AccountId，而不是承运 Service 或单独 principal_id。

治理站在同一 Realm cut 核精确 `{kind:realm_actor,actor_id}` 的 `ak.realm.actor.audit` 权限、生命周期、适用 Policy、
材料完整性及披露边界。管理权限、管理员标签或成员资格不隐含 audit。无目标与无权限同 not_found；私态未完整导入、
治理未决等不能签成功或 never_written，返回 unavailable。Account 同站读取执行相同审计检查。

成功响应复用本节原 outcome 与签名上下文。request_digest **MUST** 绑定内层 request，request_nonce 原样返回，
requester_actor_id 为来源站认证的完整 Account Actor；外层 requester 绑定由 S2S 请求签名负责。当前治理任期、
控制流 head、结果原件与签名规则均不变。内层、外层请求及响应各最多 4 MiB；1～16 个同主体 selectors 和最多
60 秒且不超过相关授权窗口的原预算继续适用。不得截断签名材料。

账号站交付前 **MUST** 验证治理链、治理方签名、实际 requester、目标、nonce、内层 request_digest、结果、任期与时窗，
并再次确认原 session／Device 有效。已观察到新治理任期或相关撤权时丢弃结果；无法确认则关闭。远端授权 cut 与本地
最终交付分别线性化，不宣称跨站原子事务。响应使用 no-store，不成为写权限租约。治理站负责供给 peer，账号站负责
消费；支持声明遵守 operation bundle 的全部可达规则。无法供给 peer 不得降级到外站 self 或副本推测。

本分支只承运真实 Account 已有的精确审计权限；Service、控制方法及受限 Device 仍走原直接治理站认证路径。
不新增列表、私钥读取或主体迁移，不改变普通 Account／组织／个人 Agent 的 DID、PCR 与设备规则。

## 9. 治理交接与验收

单 Realm handoff 必须迁入已初始化控制流的完整 head、Event／Commit、全部 current、原 DID evidence、fact、
manager／双 gates／generation／recovery current、恢复 pending／原生计划／终态 ledger、pending 安全事务、去重／quota／tuple／nonce／outcome ledger、
Device／MLS 队列、claim 与 cursor，以及 Realm Device 的不可变 Blob 上传用途绑定（完整 BlobRef、
exact ScopeRef、实际上传 Actor、原 Device／authorization 实例、接受时间，见
[device-lifecycle §16.1](../crypto-media/device-lifecycle.md#161-原签-scopeaction-配对normative)）。
新站必须实际导入并重导出比对，不能只验证 manifest 摘要后宣布就绪。
缺任一接受所需私态或未导入已签 acceptance，均拒绝启用新任期；旧站不得在换任后接受新写。
不转 Applet 私钥／私有 MLS 状态，不把管理记录转交宣称为无原生材料的身份恢复。

规范验证至少覆盖身份隔离、独立流初建、候选／审批篡改、正常／错误轮换、Device PoP／generation／CAS、
material 值与 nonce／requester_actor_id／cut 绑定、双 gate／撤权竞态、管理转交、完整导入与隐私十组。
schema 验证只证明结构；真实签名 KAT、跨字段接纳、事务效果和生产联合验收分别报告，不相互替代。

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.realm_actor_control.v1 -->
- `@method`、`@target-uri`、`@authority`、`arkret-operation`
- `arkret-realm-actor-control`、`destination-service-id`
- `content-digest`（有 body 时）、`idempotency-key`（操作使用时）
<!-- END ak-http-signature-covered-set -->

`ak.vector.realm_actor.contract.v1` 的真实签名 KAT、原生日志链与参考验收由 tools/test_realm_actor_contract.py 执行；不替代生产联合验收。

## 10. Applet 同身份密钥重置（normative）

本节只适用于本合同 Realm Bot／Ghost，所有准入、CAS、原生验证、原子效果与禁止项均为 **MUST**／**MUST NOT** 要求。普通 Account／Organization／个人 Agent 的 DID、PCR 和恢复不改。创建明确授权持续恢复，不逐次人工审批；恢复不改变身份、历史作者、外部 tuple、ProfileId 或成员记录，不复活已撤权限。

### 10.1 独立 DID 的恢复权如何落实

#### 10.1.1 分开三种密钥职责

| 材料 | 持有者与用途 | 明确不授予 |
| --- | --- | --- |
| Applet Service 认证／签名 key | 管理服务证明自己的稳定 Service 身份，签恢复 Event 和 HTTP 请求 | 单独更改任意主体 DID、伪造主体 Device 签名 |
| 每主体 DID update key 与预承诺的下一 update key | Applet 隔离的身份管理密钥库；签标准 WebVH 后继日志 | 直接签业务、Device PoP、MLS 或一般控制 Event |
| 主体日常 control key 与各 Device key | control key 维护主体控制状态；Device key 按有限授权登录／业务／MLS | 更改 DID 原生 updateKeys、替换 Applet 管理者或给自己增加恢复权 |

每个主体使用不同的原生更新密钥和控制密钥，不把 Applet Service 签名 key 直接复用为所有主体的 update key。control key 必须是该主体 DID Document 明确声明的方法，与全部 active／预承诺 update 公钥分离；具体控制用途由 Realm accepted control 选定，不从文档成员资格直接授予业务权限。Device key 仍不进入 DID Document。

与未公开 next key 的分离检查使用 control 公钥的标准 multikey hash 对比 nextKeyHashes，不要求提前公开 next 私钥或破坏预承诺隐藏性。验证者可核验已登记材料和证明，不能据创建成功声称已经证明未来备份一定可恢复。

创建候选新增 closed `recovery: {kind:"manager_native", enabled:true}`，其内容进入既有候选持钥签名、Service Event 和创建批准摘要。创建检查 WebVH inception 的 active update key 和非空 next commitment，并验证独立 control 方法。创建即初始化恢复 current，不等待首设备，也不把普通安装或普通成员资格当作恢复权。

#### 10.1.2 使用标准 WebVH 原生连续性，不发明管理者万能签名

采用现有 `did:webvh:1.0` adapter。原生 pre-rotation 的规则是：下一日志的更新公钥必须命中前一日志的 `nextKeyHashes`，该下一日志由其生效的更新 key 签署；预承诺在创建时建立。参考 [WebVH v1.0 参数与预轮换](https://identity.foundation/didwebvh/v1.0/#pre-rotation-key-hash-generation-and-verification)。Arkret 的具体分工和以下收紧是本合同规定，不声称外部方法自带 Realm 管理权限。

本主体 profile 固定每代一把 active update key、一把预承诺 next key；每次日志推进同时提交新一代 commitment，不能关闭 pre-rotation、回用 spent key 或把当前 active key 的散列当作下一代承诺。Applet 在发布前耐久保存需要的 next／next-next 私钥及精确日志意图；存储方式可为独立密钥库／外部 signer，不要求向 Station 导出任何私钥。

例：accepted 日志承诺了“下一把更新 key”。日常 control key 丢失后，Applet 生成新 control key，用已预承诺的下一更新 key 签后继日志；该日志移除旧 control 方法、声明新 control 方法并承诺再下一更新 key。治理 Station 独立验证 inception 到目标的原生链、SCID、entry hash、签名、适用 witness、新 key PoP 以及当前管理权限，然后才更新 Realm 的 accepted control。DID core 和外部账号映射保持不变。

不得把 Service DID 的恢复成功自动等同于各主体 DID 可更新，不得在 WebVH parameters 添加 `recovery`／`governance`／`manager` 私有参数，也不得把 DID Document 的 `controller=某Service` 当作 updateKeys 验证的替代。恢复授权分两处，各有职责：**DID 原生 commitment 决定谁能更新日志；Realm accepted manager＋recovery current 决定谁能把这次更新接纳为本 Realm 的主体控制状态。**

#### 10.1.3 故障边界

| 丢失情况 | 结论 |
| --- | --- |
| 仅 Device key 丢失，control key 有效 | 原 device revoke／authorize 流程；不强制整主体 reset |
| control key 或全部 Device key 丢失，Applet 管理凭据与原生 next 更新材料仍在 | 本合同同身份 reset；不需要旧 control 签名或每次管理员点击 |
| 当前 active update key 丢失，但预承诺 next key 仍在 | 可依合法 pre-rotation 推进；不能误要求已丢的 active key 再签后继 |
| 原生更新材料在完整隔离备份中 | 先恢复精确材料、确认当前链及未消费代次，再走同一 reset |
| 所有可用原生 next 更新材料及其备份也丢失 | 保留原 DID 的更新不再有密码学依据；仅有 Service 登录权或管理员批准不能绕过。主体暂停／退役；不承诺必能同身份恢复 |
| Applet Service 自己失联或凭据丢失 | 先按 Service 自身合同恢复同一 Service；换 Service 走§10.6管理转交，不自动继承权限 |

“Applet 能重置”要求它仍保有事先建立的恢复能力，并非没有任何证明也能改密钥。管理密钥库与日常 runtime 不应处于同一个故障副本；协议可以检查公钥分离及原生证明，不能证明私钥在现实中从未被复制或备份一定可用。

### 10.2 Realm 恢复授权与停用规则

新增第九类 current `realm_actor_recovery`，selector 为完整 `actor_id`，来源为所属 Realm 的 `realm_control`，revision 沿用原 `{commit_id,stream_position}`。value 为 closed `{kind:"manager_native", enabled:boolean, pending:null|RecoveryIntent}`。create 初始化 enabled=true、pending=null；不单独复制一个可能与 manager 漂移的 service_id。恢复每次同时读取并锁定本 row 和 `realm_actor_manager`。

`RecoveryIntent` 固定为 `{begin_ref,candidate_digest,manager_revision,control_revision,device_generation_ref}`：begin_ref 是原接受 begin 的完整 CommittedEventRef；candidate_digest 为该 Event payload 的 SHA256(JCS)，包含新方法签名；两项 revision 冻结 begin 前态，device_generation_ref 为 begin 产生的新代次。精确目标和原生计划从 begin_ref 对应不可变原件取得，不接受另一份未绑定的候选副本；begin_ref 在 Commit 定值后同事务写入，不进入自身签名原像。策略前态从该原件的 recovery_ref 追溯。

新增 `ak.realm.actor.recovery.set`：有 `ak.realm.actor.manage` 的真实 Account Device，按既有精确主体资源和适用审批设置 enabled；payload 为 `target_actor_id, expected_recovery_revision, expected_manager_revision, enabled`。相同 enabled 的重写不产生新授权代次；精确重试只返回原结果。变更时未完成 intent 终结为 cancelled，不回滚已经产生的 generation fence 或已发布 DID 日志。

这是预先登记的持续身份维护许可，不依赖业务 grant 到期续签。每次 reset 仍核 current manager、recovery.enabled 和 Service 本身当前有效身份，但不重复管理员审批。管理员可以提前禁用恢复；需要全面停止主体活动时使用独立 governance paused／retired。禁用恢复不等于强制撤销现有业务 Device，界面与协议必须明确区分。

卸载、业务许可过期、owner paused、governance paused 不消灭合法身份维护入口，允许收权和换锁，但不能恢复业务、新 Device 授权或安装。任一 gate 为 retired、Realm 已终结、recovery disabled、manager 不匹配均拒绝新恢复。恢复不能把 governance paused 改为 active，也不能复活 retired。

### 10.3 为什么分准备与完成两个 Event

WebVH 日志发布与 Station 接纳不是同一数据库事务。不能假装一次跨服务写天然原子：先发布新日志可能使旧控制方法已失效，Station 却尚未接受新方法；只在最后撤旧设备又留下恢复期间旧设备继续写入的窗口。

新增 `ak.realm.actor.recovery.begin` 和 `ak.realm.actor.control.reset` 两个 durable Event，都进入原 `realm_control`。加上 recovery.set，本轮是**新增三个 Event、一个 current family、一个 detached context**；不新增 Realm、Account、PCR、SessionGrant 或另一个恢复 HTTP 服务。

#### 10.3.1 begin：冻结精确意图，先隔离旧设备

实际 producer 为当前 manager Service。Event.actor_id 为其真实 service actor；`applet_id` 精确等于目标 identity，不能冒充 realm actor，无 executed_by。envelope 不携业务 `authorization_ref`；新增独立 `realm_actor_recovery` admission 分支，从 typed recovery_ref＋manager_ref 取持续维护授权。这里的 Service 例外只覆盖这两个 kind，不能扩大到普通 control／Device／业务 Event。

begin payload 固定以下字段，所有 revision 均非 null，target_actor_id 必须 realm 分支：

`target_actor_id, request_id, manager_ref, recovery_ref, expected_control_revision, expected_owner_status_revision, expected_governance_status_revision, expected_device_generation_revision, expected_generation, new_generation, replaces_recovery_ref, next_resolution, method_history_evidence, next_control_method_kid, expires_at, control_signature`。

- request_id 使用至少 128-bit 随机值；去重域为完整 actor＋manager binding＋request_id。manager_ref／recovery_ref 是对应 current 来源的完整 CommittedEventRef，不把二字段 revision 猜成 EventId。
- method_history_evidence 在 begin 中使用 closed `webvh_recovery_plan={log_entries,witness_records}`，不携带声称已发布验证成功的 evidence receipt；accepted 前缀的 witness 必须齐全，未接受后继的 witness 可在 finish 补齐，已携带的 witness 一律核验。finish 使用原有完整 `webvh_method_history_evidence`，两种载体不得互换。
- next_resolution／method_history_evidence 是本次拟发布的精确原生后继和完整前缀，验证必须延伸已接受 anchor、保持 core 与 locator；不允许删除已接受前缀、sibling fork 或回滚。可包含先前被取消但已发布的合法后继，最终目标必须与本次新 control 方法一致。证据上限沿现有 1 MiB／4096 entries。
- 准备阶段验证原生签名／commitment、旧前缀与新 control PoP；最终发布可用性和适用 witness 完整性仍在 finish 核验，不能把 begin 的计划当已生效 DID。签名 bytes、目标日志和私钥必须先在 Applet 耐久保存。
- 新 control key 与当前 key、update keys 不同；新方法 PoP 使用 `ak.realm_actor_recovery_acceptance_signature.v1`，签 `{applet_id,service_id,payload_without_control_signature}`；service_id 来自实际 Event.actor，payload 包含完整 target、前态、目标材料、request_id 和有效期。复用既有六字段 detached Ed25519 envelope 与 JCS／digest／分域字节算法；不含未来 EventId／CommitId。外层 Service 再签完整 Event。
- 首次接受需未过期，expires_at 不超过 Event.created_at 后 10 分钟；一旦 durable begin 接受，这个期限只证明首次意图新鲜，不使等待发布的 intent 自动失效。继续有效性由当前授权、pending 精确匹配和终态控制。
- replaces_recovery_ref 无 pending 时显式 null；有 pending 时必须精确指向被替代 begin 原件，同事务把旧 intent 标为 superseded。不能无前态覆盖另一恢复。新 begin 每次都按最新 generation 再推进一次，不复用旧隔离代次。

begin 的本地原子效果：保存全部原件和签署事实、写唯一 pending（保存 begin_ref、精确候选摘要和目标、原 control／manager／policy 前态、接受后的 generation）、owner gate 设 paused、generation 严格 old+1、旧 Device／会话／队列准入 fence、创建必要 MLS 安全收尾意图、写 Commit 和 outcome。失败全部零写入。governance gate 不变；新控制方法此时还不能使用。

pending 期间禁止 owner resume、control.update、manager.change、新 Device authorize／devices.reset 及主体业务；允许治理暂停／退役／禁用恢复、必要旧设备收尾、exact 读取、同 manager 明确替换 pending。防止另一路写入使恢复准备时的隔离失效。

#### 10.3.2 reset：验证已发布原生证据并接纳新控制方法

Applet 在 begin 已接受后发布／取得该精确 DID 后继及所需 witness，再由同一当前 manager Service 提交 control.reset。payload 固定 `target_actor_id, recovery_begin_ref, expected_recovery_revision, expected_manager_revision, expected_control_revision, expected_device_generation_revision, published_method_history_evidence`。

finish 必须匹配仍有效的唯一 pending，manager binding 不变、enabled=true、Realm 未终结、任一 gate 未 retired、owner 仍 paused、generation 等于 begin 接受后的值；新证据的日志前缀与终点逐字／摘要匹配 begin 目标，不能临时换新 key、locator 或日志分支。witness 材料可以在发布后补齐，但不能改变所批准日志。按既有 adapter 验完整 DID／currentness／witness；缺证据或未知状态保持 pending，不伪造成功。

新方法 PoP 的授权时点冻结为 begin 接受时，finish 引用已接受原件，不把其初始 expires_at 当作第二次授权截止，也不重新使用过期 Service HTTP 凭据。若原生合法 current 已推进到另一目标，不能把旧 target 当最新接受：须以新证据和新 PoP 明确 supersede pending。

同事务更新 control 的 resolution／control_method_kid、清空 pending、写真实 Commit／outcome／私有证据。Device generation 不再额外加一（begin 已推进），历史 Device 行保留但不能恢复成新代有效设备。owner 仍 paused，governance gate 仍不变。由新 control 方法显式恢复 owner active，再按当前安装／grant／scope 条件授权新 Device；MLS 完成独立重新加入／安全收尾前不能宣告业务 ready。

不要求旧 control 签名，不接受单独 Service 声明，不以 begin 成功当作 reset 成功，也不因为签名结构合法就跳过原生验签。已有成员、外部映射和仍合法 grant 不需重新批准，但不会自动产生新 Device 或 MLS leaf。

#### 10.3.3 撤销、重试与崩溃

- Service 用原 HTTP 认证和原 self Event submit，不使用已丢失 control key 的 HTTP 场景；exact current／event／outcome 继续用 realm-actors/material。当前 manager 可恢复自己的恢复意图结果，原 manager 的已登记请求只保留受限 exact 结果披露，不授予 current 或继续写权限。
- 恢复／替换请求和结果先耐久再响应；断线后查 exact outcome，unknown 不是未执行，不自动换 request_id 再做一次。首次请求过期与已接受意图的结果恢复是不同规则。nonce／HTTP 认证各按既有规则，不放宽过期凭据。
- 治理禁用／退役与 finish 共用主体锁并重核 current。禁用先胜则 finish 零写入；finish 先胜则保留接受事实，随后禁用不倒改历史。已发布 DID 不回滚，pending 取消后仍 paused／旧设备无效；重新启用后须新 begin，证据延伸实际合法链。
- 任一 status.set 接受 retired 时，同事务清除 pending 并写 cancelled outcome；owner retired 仍不因恢复被改写。governance paused 可以保留 pending，finish 只换锁而不解除暂停。这个 status Event 的 recovery row writer 已在 canonical registry 登记，不能作为未登记的隐式副作用。
- Applet 在 begin 前已发布的合法后继也不能直接生效；可以提交指向它的 begin，再 finish。目标前缀冲突拒绝。若 pending 新 key 又丢失，用最新合法原生材料准备新的 begin 并显式 supersede；无可用原生材料则保持不可用。
- begin 后不设自动 resume 或自动回退定时器。恢复可由管理者替换意图继续，或由治理者禁用／退役结束；取消不声称能撤销外部已发生的原生日志发布。

### 10.4 Device、MLS 与历史边界

begin 的 generation fence 必须覆盖 Event 接纳、HTTP、session、Signal、to-device、队列交付、KeyPackage claim／consume、Welcome／MLS 新接入；保留历史签名按原时点验证。新 key 不改变旧消息签名，也不允许给旧 DeviceId 重新贴一个新代次以复活。

generation fence 不是 MLS Remove Commit。begin 必须为所有受影响的已登记旧 generation 设备／leaf 耐久建立安全收尾库存；治理方只保存授权移除意图、proposal 和队列状态，实际有权 MLS 参与方执行 Remove／Update。私有库存唯一键为完整 actor_id＋fenced_generation＋device_id＋group_id＋leaf_index，至少保留 begin_ref、已授权收尾意图、已接受 Remove／Update Commit 或 pending、队列状态；替代恢复须合并仍未完成库存，不因新 begin 丢弃旧收尾。完成证据必须证明受影响旧 leaf 已移除，或由独立获准的新 generation leaf／key 安全替换；其他成员的普通 Update 不能作为该旧 leaf 的收尾完成证明。这是私有交接库存，不新增通用 current 或公开读取接口。移除尚未完成的 group 不能把“未来密文对旧 key 已保密”标为完成，也不能因新身份 key 已就绪跳过安全 gate。找不到可执行的有权 MLS 参与方时保持不可用并显式报未完成，不伪造服务器可解密／代签的能力。

恢复不找回遗失的 MLS epoch secret 或历史解密密钥；只有原先合法的内容备份能恢复历史。Applet 私钥及 MLS 私态不进入 Realm handoff。现有普通账号 SecurityRotationTransaction 不直接套给 realm actor；generation reset 的原子库存与完成 gate 按本节及 device-lifecycle 的受管分支执行。

### 10.5 治理 Station 交接与私态披露

随同一 Realm 交接 recovery current、完整 begin／finish／policy Event 与 Commit、pending 的精确计划及原生证据、nonce／request 去重与终态 ledger、旧 generation fence 和 MLS 安全收尾库存。新站实际导入并比对后才激活；旧站不能继续接受 finish。

intent 绑定稳定 Realm／完整 actor／manager binding，不把旧治理 Station 永久写成恢复权持有者。新站验证原任期已接受 begin，按新任期提交 finish；HTTP destination／response authority 用当前治理方。治理交接不变更 manager 或 recovery.enabled，不重签旧 Event，不让 begin 的初始 10 分钟期限把合法交接后的续跑拒掉。

恢复材料仍是私有 exact 数据。recovery current 的 selector 加入现有请求上限，普通成员不能枚举恢复状态、方法历史或设备目录。业务历史 fact 不新增恢复流位置或密钥库信息；恢复 Event 的真实 producer 是 Service，MUST 使用私有 realm_recovery_service 历史 signer fact，不伪装业务 Service 或 realm_control signer。

### 10.6 更换管理 Service 必须交接原生更新权

只更换日常 control key 不够：旧管理 Service 若仍掌握 DID 下一更新 key，依然掌握原生更新能力。因此§7的 manager.change 必须同时满足本节前置，manager_ref 更新不能代替原生连续性证明。

转交流程：先保持 owner paused、无 pending；新 Service 独立产生新的日常 control key、未来两代 update keys。旧原生更新持有者用它已预承诺的 next key 推进过渡日志，承诺新 Service 产生的首把 update key；新 Service 再消费该承诺签最终日志，最终 active update key 与下一 commitment 均由新 Service 隔离掌握，旧日常方法从最终文档移除。

为避免“新旧方法必须同时仍有效”的死锁，先按现有 control.update 接受新日常 control key，期间原生日志保留旧方法；随后完成上述更新权转交，manager.change 由新日常 control key 签署，并附最终 resolution／完整原生证据、新 Service 接受签名与原治理管理变更许可。最终证据还必须含该 accepted 新 control 方法。新 Service 的接受签名覆盖完整目标证据与所有前态，不能只签 service_id。

manager.change 在现 payload 上明确增加 `next_resolution, method_history_evidence`，复用当前 accepted control_method_kid；扩大的 payload 进入现有 manager_acceptance 签名。转交目标文档必须保留该方法而移除旧日常方法，native 证据须从现 accepted resolution 延伸到接收方 active／next 阶段；不得靠两个新自报公钥证明交接。

manager.change 原子更新 manager、control 的最终 resolution、generation，保持 recovery.enabled 的治理决定，pending 必须为 null；旧 Service 的恢复权因 manager binding 变更立即失效。新的 binding 通过其 exact manager.change Event 原件冻结最终原生 head 与接收方已验证的 key／commitment，后续正常 control.update 或 reset 只接受它的合法后继，不另存可能漂移的最新 DID head。原根证明保留历史；当前日常方法仍不得与 update key 混用。

转交需要原生更新能力仍可执行，不能声称只要原主体 control key 或管理员许可就能转走 DID。旧 Service 离线但合法备份／外部 signer 可用时仍可完成；所有更新材料失去时不允许管理员伪造连续性。这是本合同明确收紧的转交前提，不影响普通 Realm 治理交接。

原管理方掌握历史 key 时仍可能发布冲突历史。治理方必须拒绝不延伸 accepted head 的 sibling／回滚，并按现有 witness／冲突规则处理；不能宣称预轮换本身在整个外部世界证明唯一历史，也不能证明旧运营者未复制新私钥。要保证外部观察者一致仍取决于原生 witness 与托管可用性；本合同不把治理 Station 私有 current 冒充通用 DID resolver 的权威。


### 10.7 派生、错误与可验证结果

恢复 current 的 kind 恒为 manager_native。enabled 的保留值来自锁定 prestate；pending 来自原接受 begin 原件和本次真实 Commit，不从调用者自报 Commit 派生。control.reset 的方法与 resolution 来自 exact pending 目标；manager.change 保留 accepted control 方法并接受 payload.next_resolution。上述派生由 realm_actor_contract.derivations 登记，禁止隐式读取整流最新无关行。

recovery.set 将 enabled 设为相同值的新 Event 以 failed_precondition 拒绝且不写 Commit；同 Event exact replay 返回原结果。retired 的 status.set 原子清 pending，原 enabled 值保留但 retired 始终优先阻断。

原 begin Event 的 submit outcome 永远保留 accepted；流程状态另用 exact material 的 `outcome={status:"recovery",begin_ref,state,terminal_ref}`。state 为 pending 时 terminal_ref 必须 null；completed／cancelled／superseded 必须指向真实接受的 finish／set或retired／替代begin。请求 target_request_digest 绑定原 begin 请求。不能把取消流程写成原 Event 从未接受。已接受请求的精确重试仍核认证和披露权，不重新执行，也不能跳过当前凭据失效。

错误沿既有 Problem envelope，映射如下；具体流程终态通过上述 exact lifecycle outcome 查询，不把通用失败猜成已取消。缺依赖保持不可用，不把未知当未执行；所有失败不得写半个 current／Commit。

| 情况 | code／reason_code |
| --- | --- |
| Service 或新方法签名无效 | signature_invalid |
| 原生链、commitment、已提供 witness 无效 | failed_precondition／identity_method_evidence_invalid |
| manager 不匹配、恢复 disabled、任一 gate retired | capability_denied |
| typed CAS、pending、generation 不匹配，或相同 enabled 的新写入 | failed_precondition |
| 同去重域 request_id 携不同候选摘要 | duplicate_conflict |
| 缺发布、必需 witness、确切依赖或 MLS 安全收尾 | dependency_missing |

验收必须覆盖 KR-1～KR-12：完整身份、native真实签验与错误commitment、key职责、持续权限、字段签名、prepare原子性、发布崩溃续跑、撤销竞态、Device／MLS门、原生管理交接、治理交接实际库存、隐私及普通账号范围。参考模型不替代生产事务或真实多站联调。

### 10.8 恢复 Service 的私有历史验签事实

`realm_recovery_service` 仅用于 `realm.actor.recovery.begin` 与 `realm.actor.control.reset` 的原生产者事实。字段顺序为 kind、event_id、actor_id、target_actor_id、verification_method、public_key_base64url、accepted_at、applet_id、registration_epoch、registration_ref、manager_ref、recovery_ref；全部必填，禁止额外字段。actor_id MUST 为实际签名 Service，target_actor_id MUST 为完整 Realm ActorId；Event 的 Realm、Applet、目标主体和记录 MUST 一致。该事实不含业务 authorization_ref，不改变原恢复资格。

registration_ref MUST 是接纳截点有效且经方法原生验证的 Applet Service 登记原件的完整 CommittedEventRef；registration_epoch MUST 绑定该登记，不能用业务安装有效性代替。verification_method 与 public_key_base64url MUST 来自该登记在 accepted_at 的真实 DID 历史，并验证原 Event producer proof。

manager_ref 与 recovery_ref MUST 分别取自接纳事务锁内 manager 与 recovery current 的实际原写入 CommittedEventRef，不得用 head 或调用者声明补造。begin 的 manager_ref 与 recovery_ref MUST 逐字等于 payload.manager_ref 与 payload.recovery_ref；reset 的 recovery_ref MUST 逐字等于 payload.recovery_begin_ref，并满足其 expected_recovery_revision；reset 的 manager_ref MUST 满足 expected_manager_revision。两引用 MUST 属于同一目标 Realm 的 realm_control 流且严格早于本次 Commit。登记、管理关系、恢复 enabled／pending、双 gate、原生恢复材料及 CAS 仍依本节原接纳规则检查，缺失或不一致 MUST 拒绝且零副作用。

原 Event、fact、绑定 fact 摘要的 RealmCommit、恢复 current、generation／fence 及请求结果 MUST 在同一事务冻结。fact 不含自身 target Commit，不能形成摘要环。治理交接 MUST 按完整私有 signer inventory 移交这些原件；缺项或篡改 MUST 阻止导入激活。历史验签沿原接受治理链验证 Commit、fact 摘要及原 Service 签名，不重新要求当前安装、当前业务 grant 或当前管理者仍有效。

该分支只经 realm-actors/material 具名 exact event、获准私有审计及治理私有移交披露；普通成员 signer query、scan、snapshot、subscribe 和普通 peer 复制不得返回该材料。记录只含原签名公钥及授权来源坐标，不含私钥、原生日志或恢复计划。卸载及业务 grant 撤销后的合法恢复 MUST 可验证；错主体、错 Service／登记、错 manager／recovery 原写入、错误签名、越权披露 MUST 拒绝。本条不修改普通 Account／组织／个人 Agent 的身份与恢复，也不新增恢复 HTTP 接口。

## 11. MLS 领取与跨治理交接续跑

本节只补充 Realm Bot／Ghost 的 Device 分支。普通 Account／Agent 的账号所属 Station、领取／入群证明
与 consume 规则保持原合同。本节是 device-lifecycle §9、encryption-and-audit §2.2 中固定账号 Station
规则的明确 Realm actor 分支；不能把“固定账号站”检查直接应用到 Realm actor，也不能全局删除该检查。

### 11.1 完整领取身份与原生授权

`keypackages_claim_request_body` 与 `peer_keypackages_claim_fields` 的 Realm target
使用 `target_actor_id`（完整 realm ActorId）与非空 `target_device_ids`；与 Account／Agent target
严格互斥。Realm requester 使用 `requester_actor_id`，其 `requester_authorization.kind=realm_device`，
仍携真实 requester_device_id、device_authorize_event_id、verification_method、signed_at 与 signature。
不得携 requester_account_id 或 Agent 身份；完整 ActorId 位于原 unsigned request 中，不能只签裸 principal。
Account Device 与 Agent 原分支不得携 Realm 身份字段；缺身份或混合分支必须拒绝。

任一端为 Realm actor 时，claim_purpose 必须是 realm_membership；所属 RealmId 必须等于
intended_realm_id，实际 group／effective scope 只可为该 Realm 或其获准 Circle。禁止个人 PCR、
DirectConversation、Sidecar 和 realm_control。原 requester 签名与服务请求签名覆盖完整 closed 请求及
现有 service_binding；新增字段不得从签名投影、request digest、幂等或限速键中排除。双方继续核真实
Device key、授权实例、generation、双 gate、manager、当前安装／grant、成员／邀请条件与 Policy。
同 Realm 并不自动授予读取、领取或加入权限。

Realm requester 核验外站普通 Account Device 时，使用 device-lifecycle §8.2.1 的
`ak.peer.keys.read.lookup.v1` Realm requester 分支，由当前治理站签服务请求；只允许同 Realm 的
`mls_group_admission` 用途，目标仍为普通 Account Device。此扩展只闭合既有领取后的来源设备核验，
不新增 Bot 专用 MLS 权限或人工审批。普通成员客户端与 Realm Device 均沿用既有
`ak.mls.commit`、当前 membership 与 policy；MLS Add／Welcome 不替代成员准入或目标设备授权。

Realm target 的领取 CAS 权威是该 Realm 当时的 current governor。它在领取成功事务中从已验证治理状态
派生 `claim_authority_ref`，写入原 `peer_keypackage_claim_receipt` 并纳入现有 receipt 签名。
该引用复用 RealmCommit.authority_ref 类型，不由 requester 自报；必须能通过原 governance genesis／change
和连续 handoff 证明在 claimed_at 确实由 receipt.destination_id 治理该 Realm。Account／Agent target 的
receipt 不携该字段。首次领取必须将 exact request、receipt、claim records、当时的完整已验签发 Station
方法历史与原治理来源同时耐久保存；只保存一个 authority ID 或未签名 verified 标记不够。

### 11.2 分别验证领取与入群证明

Realm actor 的 Add 仍由有权 MLS 参与方生成并签署，治理 Station 不取得成员 secret 或代签。
实际接受该 Add 的治理 Station 在原接受事务内核验 exact claim、原 receipt、授权实例、public MLS
transition 和全部 Welcome，原子生成 `mls_add_authority_attestation`。其 attestor_station_id 必须是
该 accepted Add Commit 的治理权威；新增受签的 claim_authority_ref 必须逐字等于原 claim receipt 的字段。
不能由当下治理方重写领取日期、领取权威或原回执，也不能用当前允许代替 Add 接纳时的历史依据。

realm 分支的 `roster_add_record` 必须分别保留：

- `claim_issuer_resolution`：原领取时完整验证并冻结的 Station 方法历史，service_id 等于
  claim_receipt.destination_id，在 claimed_at 验原领取回执。
- `attestor_resolution`：Add attestation 签发时完整验证并冻结的 Station 方法历史，service_id 等于
  attestation.attestor_station_id，在 attested_at 验原入群证明。

两者即使同站也分别绑定其职责；正常 key 轮换不能以今日 DID key 替换原历史方法。Account／Agent
record 仍只携 attestor_resolution，按固定 Station 合同验证双签；不得携 Realm 专用 claim_issuer_resolution
或 claim_authority_ref。所有实际存在的 record 字段均进入原 ordered records_digest 和 manifest 签名。

领取方与 Add 接受方不同，必须属于**同 Realm 已验证的连续治理历史**：原领取 ref 与 claimed_at 对应
旧治理方；Add Commit 的 authority_ref／原签名与接受截点对应新治理方。治理方、own Station 和获准审计方
必须验证原 authority bundle／完整交接链及 exact Add 来源，缺失／分叉／错误 Realm／时点不符均拒绝。
新治理方还必须在激活前实际导入完整私有 claim ledger，接受 Add 时锁内核 exact claim 尚有效且未被消费、
取消或绑定别的 Welcome。只验两份 Station 签名、只比较 ID、只持交接摘要，均不能代替这些检查。
相同签发 Station 也必须检查原领取与 Add 的治理来源，不能靠 core 相等忽略中间换任或原件冲突。

原领取完整历史随同私态交接，不能要求已退出的旧站在交接后再次在线签发新证明。受权 roster read 仅披露
该 record 的必要历史 closure；不披露完整 claim batch、私有移交 manifest、nonce、其它主体库存或私钥。
原 authority bundle 的签名承诺和来源验证不因此获得普通私态读取权。

普通客户端仍从已绑定的自己 Station（Realm Device 为当前已验证治理站）的认证 self 结果消费
claim_receipt_signing_key 与 attestation_signing_key，分别将原 kid 的无网络 core 投影绑定到
claim_receipt.destination_id 与 attestation.attestor_station_id；不能再要求 realm 分支两个 core 相同。
两份历史签名、完整记录摘要、原请求 selector、Add Proposal／完整 ActorId／Device／leaf key 和 RFC MLS
验证仍全部独立执行。客户端不执行方法历史 verifier，也不因本合同接受第三方自报公钥；Station 必须先完成
上述历史治理验证。缺证时整份受权 roster 为 revision_unavailable，不能只返回容易验证的记录。

已有 2 MiB peer／完整 self 页双预算、每页最多8条与不能拆单条 record 的规则保持；计算边界必须包含
两份实际 closure、实际签名、所有引用及公钥投影。单条超限仍整体 revision_unavailable，不截断历史、
不跳项或引入由 kid 猜路由的网络补证。realm record 的新增字段不得绕过 records_digest。

### 11.3 Consume、未知结果与连续交接

claim 接受后响应丢失时，继续使用原 peer claims/query 的 claim_request_id 与 request_digest 精确恢复。
若 Realm target 的目的站已经交接，请求发往当前治理方；若 Realm requester 的来源站也已交接，当前来源
治理方可凭该 original request 的完整 requester_actor_id、同 Realm 连续治理链及自己的实际导入请求账本
恢复结果。接收方从已移交的原请求核该资格；不能仅凭新 source 身份、相同 request_id 或相同 AppletId 放行。
原 source_id／destination_id／参与者签名／request digest 保持原字节，查询采用当前传输认证；这只恢复
已登记的精确结果，不允许旧 destination 的未知原请求在新站作为 fresh claim 执行。未知仍返回 unknown，
不得伪造 never_claimed、把未到期意图重造为新领取或凭过期 HTTP 凭据继续请求。

Realm recipient 的 durable receipt 中 `recipient_id` 固定等于该 claim 原 receipt.destination_id，
表示历史领取权威；完整 recipient_actor_id 和 Device／authorization／claim／Welcome 绑定照旧。
它不是 HTTP 目的地。新的 consume 请求及结果恢复直达已验证当前治理 Station，以新鲜凭据按现有
HTTP 场景认证；不得为了适配新路由改写已经签署的 payload、请求摘要、claim_id 或旧回执。
Account／Agent 的 recipient_id 仍按原固定 Station 合同。

新治理方在同一接受事务核实际导入的原 claim、Welcome digest／binding、Device、当前 generation／撤销、
Realm scope、授权、claim 期限与未终结状态。未接受的请求不得因交接延长期限或免除当前权限；
已接受 exact consume 重试先核当前认证和披露权，再返回原首次 consume receipt 字节，不再次消费、
不重签原结果、不从当前投影补造过去成功。响应丢失不等于未执行，不能换 claim 或换请求来猜测结果。
新签发 consume receipt 由实际当前治理方签署，历史 recipient_id 仍指原 claim issuer。

已接受 Add／attestation／Welcome 在交接中保持原件；后继 governor 不重新接受历史 Add。
原 claim receipt、unsigned request、原历史方法、领取治理来源、未终结和终结 ledger、accepted Add／
attestation、Welcome 绑定、queue／ACK／cursor 与 consume 原结果都必须在同一冻结 cut 纳入实际导出、
导入与重新导出比对。management_private_state 的私有 canonical 导出包括这些域，即使某域为空也要
可验证；其现有加盐摘要由双签 handoff 覆盖，不新增公开库存面。

旧站冻结后不能接受新的 claim／Add／consume；新站实际完整导入并激活前不能接受。未迁入原件／
方法历史／ledger、重复消费、缺 Welcome 绑定、原权限失效或与当前 scope 不符均零效果拒绝。
多次交接保留原领取权威及全部连续交接证明，不把最近旧站冒充原签发者。治理转移本身不增删 MLS leaf、
不撤销合法 Device、不自动重新领取，不改变主体身份，也不豁免独立 MLS 安全收尾门。

具名验收为 RA-CLAIM-1 和 RA-HANDOFF-1～6：完整身份正反例、旧 claim／新 Add、已接受 Add 的后继读取、
consume 未知结果精确恢复、错误链／缺库存／过期／撤销零效果、连续交接与冻结竞态、普通账号回归及隐私预算。
schema／真实双签 KAT／参考状态机分别报告，不算真实数据库或双站生产联调通过。
