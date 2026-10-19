---
title: Realm Bot／Ghost 与私有控制流
status: candidate
normative: true
stability: v1
updated: 2026-10-19
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
控制方法可为原生文档声明的方法或有效 updateKeys 成员的标准 did:key 方法；后者只是控制 key，不能把该 key DID 当作主体身份。
校验 `project(initial_resolution.did) == actor_id.realm_actor_id.principal_id`，并保留完整原 DID、
方法证据和原始签名。不得从 core 反拼 DID，不得以 Service 声明、namespace 命中或自带公钥验签替代身份权威。
Applet 可托管 DID 日志并保管主体控制密钥、Device 私钥与私有 MLS 状态；治理 Station 只管理授权与公开验证材料。
治理方或管理员有权暂停主体，不因此取得主体私钥或代签权。

Ghost 的 SCID **MUST** 独立于 Service 和 controller；创建时完整 DID 的 host 与注册 Service 的
已验证 bare DID host 相同，host 后至少有一个路径分段，并匹配登记的 actors namespace。
Bot／Ghost 的 AppletId、初始角色和创建来源不可改；当前管理 Service 是独立状态。
同 core 合法密钥／定位更新保持身份；换 core 创建新主体。退役身份保留占用，不得重新创建复活。

主体只参加自己的 Realm 及其中明确授权的 Circle。同 Applet 在另一 Realm 创建另一个完整主体。
不得加入个人 PCR、个人 Agent 控制 Realm、固定参与者 DirectConversation 或个人 Agent Sidecar。
Circle-only 场景仍满足父 Realm 最小成员前提，但父成员资格不自动授父内容读取。
不得为解决依赖读取而放开父 Realm；使用既有获准 exact 依赖读取。

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
| `ak.realm.actor.manager.change` | 新接受的主体控制方法 | §7 的主体、治理许可及新 Service 接受；manager 与 generation 原子改变 |
| `ak.device.authorize`／`ak.device.revoke` 的 realm 分支 | 主体当前控制方法 | §5 的有限设备授权或真实撤销安全事务 |
| `ak.profile.create`／`ak.profile.update` 的 realm 分支 | 主体当前控制方法 | 本人私有资料维护；全主体 create-once 与后继 CAS；公开使用另核实际 scope 的 publish／review |

上述控制分支都只写本主体所在 realm_control。Service 或 Device 签名 **MUST NOT** 冒充控制方法。
create 与业务 Event 的 `applet_id`、真实 `authorization_ref` 仍必填且精确绑定。
本人控制分支要求 `applet_id` 等于 accepted identity，**MUST NOT** 携带 `executed_by` 或 envelope
`authorization_ref`；这是精确的 realm actor＋允许 kind＋控制方法例外，不是全局取消 Applet 授权。
governance status 不命中例外。manager.change 在 payload 中另持真实 `management_authorization_ref`。

创建保留 `ak.applet.bot.provision`／`ak.applet.ghost.provision`，按 candidate.creation_scope 验权。
创建许可与安装是不同事实；安装不会自动创建主体、Device、成员、Profile、grant child 或 MLS 成员。
持续自动 Ghost 许可可在明确 namespace、scope、配额、过期与当前安装约束下多次创建，
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
| realm_actor_control | actor_id | resolution、control_method_kid；create／control.update |
| realm_actor_manager | actor_id | service_id、registration_ref、binding_ref；create／manager.change |
| realm_actor_status | actor_id、gate | active／paused／retired；create 两行／status.set 指定行 |
| realm_actor_device_generation | actor_id | current_device_generation_ref；create=1，reset／manager.change=old+1 |
| realm_actor_device_authorization | actor_id、device_id | 准确 realm Device 授权及原 authorize EventId；device.authorize |
| realm_actor_device_revocation_proposals | actor_id、device_id | 原不可变 proposal 与真实命令结果折叠；device.revoke |
| realm_actor_profile | actor_id | profile_id 与允许的 Profile 值；profile.create／update |

create 的所有行、去重／配额／tuple 约束、原件、签署事实、Commit 和结果 **MUST** 同事务成功或全部不写。
创建后没有 Device／Profile 行是合法未创建；identity／control／manager／双 gate／generation 缺项是错误，不能兜底初始化。
expected_revision 只在 typed payload；target 行首写显式 null，后继精确比较原 row revision。
治理任期变更不改已有 row 的原 revision。写入仍锁内检查最新 gates／撤销／manager，历史 revision 不构成当前 allow。

新增纯派生：`realm_actor_accepted_event_ref` 是真实接受 Event／Commit 的四坐标；
`realm_actor_resolution_projection` 是 create.initial_resolution 或 update.next_resolution 加
resolution_event_ref=原 EventId、updated_at=Event.created_at；`realm_actor_profile_id` 在 create 时由 EventId
retype，在 update 时为精确 target_ref；`realm_actor_profile_value` 在锁定的 actor-local Profile 上按允许字段创建／patch。
来源坐标在 Commit 定值后、同一接受事务写入，producer 不自报，且不进入自身 Event／Commit preimage。
selector 的 literal 只允许 actor.create 初始化 owner／governance 两行，不是通用循环或表达式。
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

所有 DeviceMessage、KeyPackage claim／consume、Welcome、MLS sender／receiver、队列、receipt、
历史 signer 查询及 credential 都 **MUST** 支持明确 realm actor 分支，和 Account／Agent 分支互斥。
路由由已验证 RealmId 的当前治理方决定，不能塞入假 account_id 或用 principal-only fallback。
RFC9420 BasicCredential 使用完整 ActorId 的 canonical bytes；Device 与 key 继续显式绑定。
每次提交、队列交付、读取和 MLS 接入重核实际 scope 的当前权限，撤权竞态不得因已有队列或签名有效而放行。
治理迁移导入尚未终结的队列／claim／cursor，迁移不自行加入／移除 MLS，也不传 Applet 私有 MLS 状态。

## 6. 创建与控制更新签名

唯一创建 payload 是 `ak.schema.realm_actor_create.v1` 的 RealmActorCreateCandidate，包含完整 actor、
Applet、Service、角色、128-bit 以上随机 request_id、creation_scope、registration_ref、
creation_authorization_ref、initial_resolution、完整 method_history_evidence、control_method_kid、expires_at、
仅 Ghost 必填的 external_ref、control_signature。所有精确成员以 closed schema 为准。
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
同方法更新 DID 历史／locator 仍签新 PoP。没有旧有效方法时不支持本合同同 ID 恢复；可暂停／退役并创建替代者。
普通账号与 Agent 的既有恢复不受此限制影响。

四个新增 detached context 为 creation、control_acceptance、manager_acceptance、material，完整名见
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

一次接受原子换 manager 与 generation，旧 manager 业务链和旧 Devices 失效。新 Service 不继承旧 parent／child、
安装 epoch 或 Device；独立取得安装／grant、显式 owner resume、授权新 Device 后才可业务使用。
governance gate 不受 owner resume 影响。中断保持 paused，以 exact 结果续跑，不自动回滚旧 key／manager。
Ghost 初始 host 检查保留历史事实；转交要求新 registration 显式接纳已有完整 DID namespace 及原生连续性，
不强迫 DID 改成新 Service host。

无需失联旧 Service 再签，但必须仍有主体有效控制授权。无 key 不得由管理员直接接管同身份。
协议不转移私钥，也不能证明部署人员没有复制新 key；runtime 必须实际隔离新 key。
普通 Service 同 core 的端点／key 更新继续原 registration／DID 规则，不伪装为 manager.change。

## 8. Exact 控制材料与历史验签

`ak.self.realm_actor.read.material.v1` 对应 `POST /_arkret/self/realm-actors/material`。
写入复用原 self Event submit。请求公共字段为 actor_id、purpose、request_nonce；nonce 为至少 128-bit
CSPRNG base64url，22–128 字符。current 加 1–16 个同 actor 唯一 selectors；event 加完整 target CommittedEventRef；
outcome 加原登记操作请求的 target_request_digest。禁止 wildcard、跨主体查找、无界设备列表。

控制方法可读自身材料；当前管理 Service 可读其主体必要材料，安装失效不使身份读取死锁；原 Service 可按私有
ledger 恢复自己创建意图的 exact 结果；真实 Account 必须有具名 audit 许可。普通成员／Device 不可读 current
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

current.entries 与请求 selector 一一同序、无遗漏无额外；每项为 present row 或 never_written selector。
只有尚未授权 Device、从未有 revoke proposal、尚未创建 Profile 可 never_written；已撤销／fenced 行保留。
identity／control／manager／双 status／generation 创建后必有，缺项 fail closed。
event 返回原 event、commit、producer_signer_fact，逐项校原 target 与签名；不声称提供全流证明。
outcome 返回原 target_request_digest 与登记的真实结果；accepted 必有原 Commit，pending／unknown 不等于完成。
请求／响应各最多 4 MiB，超限整体拒绝，不能截断后签部分数据。

历史 producer fact 新增 realm_device／realm_control，共有 kind、event_id、actor_id、verification_method、
public_key_b64u、accepted_at。realm_device 另有 device_id、authorization_event_id、authorized_generation_ref；
不携控制流 position 或授权 Commit 坐标。realm_control 另有 control_event_ref，只向获准私有审计披露。
完整 DID／授权依据留在治理私态。SHA256(JCS(fact)) 在目标 Commit 计算 ID／签名前冻结，accepted_at 与 committed_at
相同；外层 target 坐标随后建立，不能放回 fact 形成自引用。
普通业务历史 signer 查询绑定原 target、完整 actor、实际 method，只返回必要公钥，不泄露控制 current、历史或列表。
Account 管理员与 Service 仍使用各自既有 fact 分支。

Applet authority material 只保留 Service 安装／grant 材料；被替代的 Account managed_source 和跨 PCR Device
scope confirmation 不再作为主体入口。Realm actor 材料只有本节一个 current／Event／outcome 入口。

## 9. 治理交接与验收

单 Realm handoff 必须迁入已初始化控制流的完整 head、Event／Commit、全部 current、原 DID evidence、fact、
manager／双 gates／generation、pending 安全事务、去重／quota／tuple／nonce／outcome ledger、
Device／MLS 队列、claim 与 cursor。新站必须实际导入并重导出比对，不能只验证 manifest 摘要后宣布就绪。
缺任一接受所需私态或未导入已签 acceptance，均拒绝启用新任期；旧站不得在换任后接受新写。
不转 Applet 私钥／私有 MLS 状态，不把管理记录转交宣称为无 key 的身份恢复。

规范验证至少覆盖身份隔离、独立流初建、候选／审批篡改、正常／错误轮换、Device PoP／generation／CAS、
material 值与 nonce／requester_actor_id／cut 绑定、双 gate／撤权竞态、管理转交、完整导入与隐私十组。
schema 验证只证明结构；真实签名 KAT、跨字段接纳、事务效果和生产联合验收分别报告，不相互替代。

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.realm_actor_control.v1 -->
- `@method`、`@target-uri`、`@authority`、`arkret-operation`
- `arkret-realm-actor-control`、`destination-service-id`
- `content-digest`（有 body 时）、`idempotency-key`（操作使用时）
<!-- END ak-http-signature-covered-set -->

`ak.vector.realm_actor.contract.v1` 的真实签名 KAT 与十组参考验收由 tools/test_realm_actor_contract.py 执行；不替代生产联合验收。
