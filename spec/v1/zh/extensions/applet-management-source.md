---
title: Applet 账号来源、远端配置与管理审批
status: candidate
normative: true
stability: v1
updated: 2026-10-19
---

## 0. 范围与权威

本文的 MUST／MUST NOT 按[规范语言](../conformance/normative-language.md)解释。本文补充
[Applet integration](./applet-integration.md)、[managed governance](../authz/managed-governance.md)与
[Device lifecycle](../crypto-media/device-lifecycle.md)，不修改 Device §8.2.2.1 既有业务转发原像。
字段顺序和closed分支以 [management source schema](../../artifacts/schemas/applet-management-source.schema.json)、
[configuration schema](../../artifacts/schemas/applet-configuration-operations.schema.json)、
[review schema](../../artifacts/schemas/management-review-operations.schema.json)为准。
来源附件不是 Event 成员、可复制 PCR、身份预登记、激活或新的 Device 认证方式。

## 1. C、S、B 与原操作者

C 是 Applet Service／runtime，持有受管 Principal／Device 私钥、MLS 与耐久运行状态。
S 是完整 AccountId.station_id 所标识的账号 Station，接纳原四 Event 创建、PCR／Device控制并提供限定来源；
合法 PCR handoff 后 current Commit 的 governor 可以不同于 S，须沿连续权威链验证。
B 是目标 Realm 当前治理 Station，决定本 scope 的安装、parent／child、Policy、审批、成员与业务。
管理员的账号站仅提供操作者权威来源，不决定 Bot／Ghost 的账号归属。

C MAY 兼任 S，但 MUST 实现实际 Station 合同；同 host、URL、组织、DID 托管或持私钥不能推导此角色。
普通 Applet＋独立 S、S==B、C／S 共部署继续合法，不能强制所有 Applet 兼任 Station。
C的DID服务角色必须是已登记applet_service，S／B为正式station；兼任指服务端同时实现两项职责，
不允许同host或兼任声明绕过既有Service注册／DID serviceKind的身份约束。
共部署也 MUST 分别验证 Service、Station、Principal 与 Device 的签名职责；S 不因托管记录取得 runtime 私钥。

## 2. 账号创建与 B 配置请求

S MUST 在自己的合法来源 scope 按原 creation grant／Policy／必要 review、短期 authoring request 与同站四 Event
原子事务创建。create_bot／map_ghost 仍约束实际来源创建／映射，不新增跨 scope creation target，不拆原事务。
B 仅批准本 Realm 使用具体主体；其管理员不因发起请求成为 S 管理员，B 的许可不是 S 的 creation grant 或审批票。

`ak.self.applet.configuration.command.submit.v1` 接受 command=configure／cancel／recover 及 immutable intent。
新configure的B MUST 验证真实完整 Account 操作者在 exact scope 当前显式 ak.realm.admin、原授权全部约束、安装／Service／epoch；
配置动作标签为 ak.applet.configure，仅标识本有界配置行为，不是源站 provision、管理 require_review 操作或业务许可。
cancel仅取消本请求人原配置，recover仅查询并恢复原操作／终态，核当前真实身份与原intent／可见性，不要求仍持新建配置的管理员权；恢复原结果也不授新业务权。
配置不要求 B 提供 S 的创建 grant；若实际授权来源或动作 Policy 要求 operation approval，MUST 沿登记的
applet_configuration.approval_signatures 载体绑定exact operation及原请求：
原管理员授权来源的批准仍以ak.realm.admin求值，使用eligibility.operation_action_overrides的该精确operation/action行；
ak.applet.configure动作Policy自己的审批另按对应action_overrides执行，两层独立，不能将原admin约束改名跳过。
各请求审批原像仅剔除 approval_signatures，并保留独立 ak.realm.admin 批准资格。未满足任何原约束必须拒绝，不能改名绕过 deny。

B MUST 先耐久固定 (applet_id, full originating actor, request_id)、intent canonical digest、当前安装实例、
generation、状态和唯一结果，再调用 `ak.edge.applet.configuration.command.execute.v1`。
execution_intent 包含完整原操作者、B／任期、scope、registration_ref／epoch、C 和 selection；
B 对 execution_request 原签，外层同时使用现 Service RFC9421 认证。C MUST 从真实 B authority、签名、
exact Applet／安装与有限期核验新执行命令；cancel／recover只接受已耐久保存的相同intent及该Realm当前合法B的真实签名，不用撤销安装阻止停止／结果恢复，不能信任调用者填的管理员字段或普通 C 自签转述。
C 在 S 仍只以自己合法创建资格执行，不能将 B 命令直接交给 S 当 provision 批准。
new_bot 与 existing_account 选择 MUST 区分；existing 必须验证本 C accepted 所属，不能据裸 Account 建立信任。

C MUST 耐久保存 inner execution_intent 与创建／选择结果，在响应前持久化原密钥及源结果；
execution_outcome 由 C 原签绑定同 request_id／intent_digest／Service，created／reused 包含完整 Account 和原四 CommittedEventRef，
顺序固定 provision、PCR genesis、accountability、初始 Profile。B 核签名和绑定，再从实际操作来源核 accepted 归属，
不能将配置结果本身当来源注册或业务许可。B 的 response.intent_digest 指 execution_intent 摘要，self 请求的本地 intent 摘要另存，不混用。
pending、created、reused、denied、cancelled 只描述 C 的源阶段；B 的 admission_status 独立，不能表示 MLS／public ready。
created／reused 的真实源事实不会被 B cancel 抹去；B 拒绝接入是合法终态。

B MUST 对实际 Device 原签 join／public Profile 分别执行 allow／require_review／deny。
allow 不重复弹人工批准，require_review 只签最终具体候选，不签空配置意图、不使用 S scope provision 充当 B creation target。
来源创建 scope／epoch 与 B 业务安装分别核验；B parent／child 仍绑定 B 自身 exact epoch。
Ghost 保留原 (Applet, hosting Station, protocol, instance, external_id) 唯一键及原 reuse；不同 B／频道不能重复创世。

## 3. 按实际操作提交 subject 与 review 来源

### 3.1 Service child 的 subject 来源

C 原签 terminal child 时 producer 是 C、subject 是受管 Account，不能要求 subject 已有该 child、Device 业务证明或 membership。
在现 self/events 单 event_submission 的 EventAdmissionSubmission.subject_managed_source 提交 purpose=managed_subject 来源。
仅适用于真实 C 原签 ak.capability.grant、exact terminal managed subject。S==B MUST 直接读取本地同事务事实并禁止多带附件；
S!=B MUST 携带有效来源。同站只表示不需要外部附件；若该managed PCR已合法移交，仍须沿既有native路径
取得并验证实际PCR governor的current，不能把本库旧投影当成权威或设立第二writer。普通 Service Event、Human、Agent、native PCR、批次／atomic unit 与 peer ingress 禁带该成员。
B MUST 验真实 Service parent、允许 role、完整 Account、C／Applet 归属、原件与 current、实际 scope／安装／epoch、
动作／资源／期限／quota，在接纳 child 的同事务保留最小私有 audit。失败不得写入可复用来源预登记，
不得补假本地 PCR 行。合法的普通安全失败日志不成为授权依据。

仅下放实际启动所需最小动作；child 与来源验证均不等于 join批准、内容读取、解密或public许可。
Realm subject-only join 按原安装引用执行；Circle join 保留真实最小 child、父 Realm membership revision、
ak.circle.member.add／ak.applet.join exact Device pair 与独立 E2EE 条件。

### 3.2 直接管理申请

C 向 B 既有 management_review.request 提交 managed_source（purpose=management_review），
C 为 requester，候选 actual Account Device 为 producer，S 提供来源。只适用于 managed join／publish 的 Event target。
Human／Agent、creation target、其它 operation 与本地来源分支禁带；外站 managed 缺证不得降级 Human 或猜本地 PCR。
managed_source.device_source 必须包含同 cut projection 及原授权 coordinates／revision／generation／accepted_at，
核真实 Account／Device／VM／key、active状态、原有限授权窗口覆盖候选 created_at 与当前时刻，核候选 producer proof。
S必须从原accepted authorize及当前generation验证该候选所需的原签exact scope/action pair（Circle join含两个动作），
不能只核公钥或把Service取材认证当Device scope许可；B另验实际业务门，不要求S持有B本地业务grant。
source proof 对这些字段作本用途绑定；不使用原 authority_forward 的 event_authorization 或伪造业务 body digest。
最终本人业务仍走原 Device→S→B 接纳及业务转发证据，allow 不能制造假 review 以取得来源。

## 4. 有限取材与 B 返回 S 的 scope 确认

`ak.self.applet.authority.read.material.v1` 保留原 exact scope／指定 grant_ids 读取，另有互斥 managed_source_request 分支。
C 请求本 Service、本主体、exact operation_binding 及尚不含本轮来源／确认的 operation_request。
S MUST 从 accepted 原件验证 C 与主体归属，并验证该 operation 的实际 C producer／requester及候选，重算 binding.request_digest；
只为已 accepted 自己托管主体生成 source。无任意账户、PCR、grant 查询或枚举；未知／隐藏／无权统一 not_found。
源材料原样覆盖四 accepted Event／Commit、Service与S的历史验证材料、必要 current 及合法 governing chain，
必要 authority_bundles 只证明实际 governing source，不授 PCR 复制／一般读取。源操作 scope 不能误当 B 业务 scope。
S 同次冻结自己负责的 current 取材；外部 PCR governor 的 current 须独立取得有效权威证据，未知不得由 S 猜测代签。

原 exact-scope request 可加 device_scope_request，含 S、subject、Device、完整 Principal 原签 control_event 与 nonce。
B MUST 只为当前合法 C 的自己 exact scope／指定业务 parent，核 current active安装，返回额外 device_scope_confirmation。
control_event 必须为该 subject 自己 PCR 的 ak.device.authorize，Device／scope／C／Applet 与安装一致；
B只确认自己安装及C的资格，不据声明替S认证subject归属或接纳Device，也不要求待创建Device已认证；
S必须从自己accepted原件验证实际subject、C归属及Principal控制。S 核 confirmation 中 B／任期／scope／installation／nonce
和完整 request 摘要；裸 current JSON、C 缓存或另一个主体的确认均无效。
C 只将该有限确认交 S，不因可读自身 parent 而转交整条私有链。

S 的 self/events EventAdmissionSubmission.device_scope_confirmations 为按授权 scopes 顺序逐项对应的有限数组；
仅受管 Principal 原签 authorize／replacement authorize 扩外站 scope 时携带，S 本地 scope 直接同事务验证，不混入本地确认。
若managed PCR已合法handoff，当前PCR governor沿原native控制路径完成该事务；hosting S不是第二writer。
原peer authority_forward的eligible managed native-PCR单Event authorize分支可原样携device_scope_confirmations，
当前PCR governor验证完整B确认、hosting S／subject及自身PCR连续权威；其它peer业务／Human／replication／atomic分支禁带。
这不是管理review／subject来源peer分支，也不改变Device业务forward原像。
S或其合法当前PCR governor MUST 验 Principal accepted controller／method、候选 Device 完整 possession transcript、PCR generation／CAS、
原授权动作和逐 scope 有效安装依据，在原 Device 控制事务接纳；confirmation不替代这些门。
confirmation 各自 nonce／request_digest 绑定 C 取材的完整 exact material request；S 依据 control_event、scope和
C提交的实际 grant_ids 重建请求核验，不能由一个裸 digest 声称匹配。为此 confirmation 中携带有界 grant_ids，
不携 grant 原文。B 在最终业务 cut 再核 current；短期确认不授未来业务 lease 或全局快照。

## 5. 唯一原像、期限与容量

四个新签名 domain 见 proof-context-registry：ak.applet.management_source.v1、ak.applet.device_scope_confirmation.v1、
ak.applet.configuration_command.v1、ak.applet.configuration_outcome.v1。
每个 proof 都用既有 Ed25519 compact detached JWS（protected header 仅 alg=Ed25519，base64url无padding），
JWS payload 是 UTF8(domain) || 0x00 || RFC8785_JCS(host with only proof omitted)。
verification_method 不进入unsigned host，但必须属于该证明角色且投影为 host 绑定的完整 S、B 或 C；不能选任意验过的 key。
其它原签 Event、Commit、Service history、Device证明仍独立核验，source signer不替代它们。

operation_binding.request_digest = SHA-256(RFC8785_JCS(operation_request 投影))。
child 的投影是整个 EventAdmissionSubmission；review 的投影是整个 review request。
只剔除 subject_managed_source、managed_source、device_scope_confirmations 及 approval_signatures 这四个本轮顶层可变证据成员；
原 Event（包括producer proof）、候选与配置引用均保留。外层审批票只从本操作锚剔除，
实际接纳仍独立全验；operation-target ApprovalSignature按原规则覆盖含来源附件的请求、仅剔除approval_signatures，
顺序是先来源proof、再审批票，避免审批与来源互相签署。不剔除嵌套原件签名。
每个source proof签自己的全部原件／current与同一个操作锚，避免相互含最终proof摘要成环；完整外层HTTP body仍被签名。
source_request.operation_request 必须已是该投影，不能嵌入另一个source请求制造递归历史。
child／review proof仅对应各自operation与purpose，不可移植到原Device业务forward或其它target。

source、scope确认的 evaluated_at <= now < expires_at，寿命最多60秒，不能超出实际current、Device授权与问责有效期；
nonce至少128 bit CSPRNG，body中的nonce签名绑定不替代原HTTP防重放。
command 的 issued_at <= now < expires_at，寿命最多300秒；execution_outcome 是耐久历史结果，认证恢复不把它当current允许。
已accepted的原child／控制Event按原Event幂等fence恢复唯一结果，先验当前真实C认证／原请求可见性，不因来源过期重复接纳；
新业务不得借旧结果绕current。source nonce 不要求已存在Device；binding B identity／generation／scope／subject／C／候选必须与实际请求一致。
S／B各自current独立求AND，没有跨站同一锁定快照。合法key／endpoint／governor更新按原历史证据链验证，不硬编码原hosting key。

source整体最多2 MiB；review／单Event控制提交／material请求响应各最多4 MiB canonical UTF-8 bytes；
configuration 请求／响应各最多256 KiB，scope确认每份最多16 KiB且最多64份。
material 最多64 grants／256 current results；source最多8 authority bundles，每条连续handoff／Service历史最多64个条目，
超过上限必须拒绝 too_large，不能截断、缺证降级或读全PCR。原业务provenance sibling 1 MiB独立保持。
字节限值包含嵌套原件、proof、current与其它请求成员；JSONSchema的x-arkret-max-canonical-bytes必须由实际接收器执行。

## 6. 审批、幂等与恢复

review request_id、候选、requester／producer／subject、scope／operation、初始期限和批准依据耐久固定。
full body摘要用于单次传输幂等；本文managed Event-target申请的不可变 intent_digest 是§5操作锚投影的摘要，
保留configuration_ref及完整原签Event。既有creation申请继续按原最终RequestBody仅剔除其approval_signatures求业务target摘要，
再沿既有私有intent绑定，不能把嵌套的可追加creation审批票纳入不可变intent或误改原业务批准目标。
同request入口可更新 fresh来源，不能修改intent、重置TTL、重建pending或重新扣业务quota。
传输nonce／签名时间更新不supersede；Policy／Profile／membership／Device授权实例／安装epoch／任期等真实批准绑定变化使未消费批准superseded。
同id异intent返回duplicate_conflict。Event-target批准仍签原实际Event，不额外签私有review的来源附件；
operation-target批准仍签对应实际RequestBody，按§5仅剔除approval_signatures并保留该请求自己的来源附件。
两者均不得改写ApprovalContext.initiating_actor，不得把私有review envelope当成原业务批准目标。
configuration_ref 若存在须命中B本地同scope配置结果的Account／intent；B按本地配置意图与具体Account关联取得原操作者，不能仅依赖C可省略的configuration_ref；
B将原操作者纳入禁止自批集合，
不能因C代理抹去原操作者。其它请求人／producer／受益人自批禁令、threshold和同principal跨站去重保持。

status／decide／cancel／consume 必须消费同一个verified来源基础与 B current；源过期／不可达暂停新批准和业务接纳，
C可在原request入口续证。原请求人取消自己的未消费请求、当前合格B审批者拒绝请求仅用已验证历史绑定及当前实际权限，
不要求源站新鲜证明；不得因此批准或恢复业务。当前真实认证的原请求人可恢复自己的terminal／consumed结果，即使旧source已过期；
不能接受过期HTTP、被撤销身份或凭猜到id读取。无权／隐藏／未知统一not_found，必要source audit只供本操作合法参与者。
B拒绝pending不产生child／membership／Welcome／群资料／public权，已单独合法接纳的child也不是pending的副作用。
成功业务、批准／nonce／quota消费及exact outcome必须同一可恢复事务；失败零业务效果且不消费。

配置重试的外层full body fence与inner immutable intent fence分开。新鲜外签或同意图重新投递不能重造号、换S、
覆盖密钥或重复源创建计数；重启／丢响应必须恢复原C/S操作结果，unknown不得猜失败退款。
configure／cancel共享inner intent；cancel仅停止尚未完成的配置和B新接纳，不能抹掉已created／reused源事实。
C只能把cancelled作为确未接受创建的终态；与S竞态结果未知时保持pending并恢复原结果。
B停止本Realm业务／投递，S按自己权限和操作结果处理；两站没有共同锁，不承诺整体回滚。
source创建数量／B接入次数按各自实际合同结算，原Ghost唯一／reuse和mapping quota语义不变，不增加全局预算中心。

B freeze禁止新决定与接纳；现有handoff按authority-commit-log §10的management_private_state_digest／私有manifest绑定并完整迁入本scope最小私有配置／review／消费／audit与exact结果恢复材料，
完整性依原私有状态迁入门验证，不能从普通成员Snapshot重建。旧任期pending／approved使之superseded；
terminal／consumed历史结果保留唯一。来源／配置命令的新操作须绑定新B任期，旧proof不转借。
未完成配置不得在缺私态时重新启动创建；不新增公开迁移接口或新身份生命周期。

## 7. 自动 Ghost、隐私与验收

S为C的真实map_ghost创建／映射许可与B为实际join／publish的范围管理许可分别设置；B不能一次授出S的创建权。
自动Ghost可在各自权威scope一次授真实grant／Policy范围许可，逐次机器核验平台／实例／位置、exact scope、数量／期限、父scope deny；
单候选review票不能复用为无限自动许可。S创建、B join／publish、读取／解密／外发方向与独立E2EE／MLS Add分别核权。
外部tuple与成员事实由Bridge按既有合同验证；C签名证明归责，不独立证明外部真人。
解绑或成员变化按实际scope停止后续业务，不全局删除共享Ghost，不承诺追回已交付内容，不新增通用外部同步协议。

来源只留实际child接受audit／私有review及其必要恢复，不能进入成员history、replication、scan、snapshot或普通signer查询。
原共享历史最小signer fact保持。有限scope确认不泄露parent原文；C／S分离仍只走限定供证，共部署可内部同类型组装。
准备、源创建、Device、child、membership、MLS、publish各自如实显示，source_created不能显示ready。

`ak.vector.applet.management_source.v1` 由正式fixture与可执行合同检查覆盖MR-1～MR-9／CR-1～CR-12：
同站／分离、无循环启动、allow无假review、直接review全生命周期、错身份／用途／scope／epoch／Device／nonce、
签名与原像反变异、原件／current闭包、源失效／续证、冷恢复／并发／handoff、源创建但B拒绝、
自动Ghost范围与quota、原操作者独立审批及最小披露。规范模型／KAT不代表生产代码或真实双站MLS验收通过。

结构／禁带／未知字段错误返回schema_violation，超量返回too_large；原签或新proof数学失败返回signature_invalid，
身份／scope／安装或实际授权不成立返回capability_denied或既有精确域错误。取材未知／不可用保持temporarily_unavailable，
不得转allow；同id异intent返回duplicate_conflict，隐藏／无权／未知查询统一not_found。不得将未知源站降级成Human。

pending响应只是非终态进度观察，不是最终accepted outcome；同immutable intent再次提交可观察原操作进度，
MUST NOT 启动第二次源操作。C的terminal源结果字节冻结，B的admission_status另由实际原join／review结果观察，
来源已创建不等于准入或ready。外层body fence不能把第一次pending永久当完成，也不能借刷新外签重复副作用。
普通Event／payload既有容量不变；4 MiB控制提交上限仅用于新subject／Device确认适用分支，不放宽其它原限制。

execution_request 的顶层 governance_station_id／governance_generation 标识本次实际治理签名者，
execution_intent 内相应字段固定原始命令任期。新configure二者必须相等；C从独立可信治理起点验证当前Realm权威，
不能把命令、header或own-Station配置当治理trust。cancel／recover可由合法handoff后的新B签署，但必须验证连续交接、
同原scope及C已经耐久保存的完整旧intent，不能要求新B持有旧Station私钥。新B原样恢复已迁入intent，不改旧intent摘要。
recover只恢复C／S已经存在的同一操作／结果；未知或原命令从未到达返回not_found／原未决状态，
不得签发新的source preview／authoring request或启动原本未执行的创建。原B退出后其新签名不再授权治理操作。
B普通原请求人可在当前真实认证下recover，不要求旧审批／安装继续active；任何新接入仍走新B当前业务门。

未完成配置命令在B／C各自按(Applet, exact scope, governance Station)最多64个；达到上限返回rate_limited，
不得启动新的S副作用。实现还须施加有限的全服务队列／存储配额。unknown的耐久去重／结果恢复记录不能因队列清理
被删除或释放成新创建许可；源创建与B准入各自的实际quota继续独立核验。
