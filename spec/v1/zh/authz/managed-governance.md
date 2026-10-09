---
title: Realm 用户、Agent 与 Applet 精细治理
status: candidate
normative: true
stability: v1
updated: 2026-10-09
---

## 0. 规范语言与载体

本文的 **MUST**、**MUST NOT**、**MAY** 按 [规范语言](../conformance/normative-language.md) 解释。
管理规则使用 `ak.policy.set`、[Policy schema](../../artifacts/schemas/policy.schema.json) 及其既有 typed current。
审批准入使用唯一 [ApprovalSignature](../../artifacts/schemas/approval-signature.schema.json)，不另造授权签名类型。
[management review operations](../../artifacts/schemas/management-review-operations.schema.json) 只承载私有耐久申请状态；
它不进入 Realm history，不是 grant、membership、runtime pairing 或公开模式。

## 1. 身份、默认值与规则组合

Agent selector **MUST** 使用 accepted ownership 的完整 controller／Agent AccountId。
Applet selector 是 `all`、完整请求人 Actor、exact `(applet_id,effective_scope)` installation，或经 accepted
managed provision 验证的完整 Bot／Ghost Actor。Profile、同 DID host、URL、显示名和裸 principal **MUST NOT** 替代这些事实。
requester 的 actor_id 必须是当次真实认证请求人（安装／调用人为完整 Account，创建为 exact Service），不能倒用安装者；requester 只对安装、创建申请与调用人的决策匹配；持续交付 **MUST NOT** 因无法确定当次请求人而跳过 installation／managed actor 规则。

同一 Policy 内只取当前操作、动作、资源与主体全部匹配的规则；最高 priority 的匹配规则组决定结果，
同 priority 按 `deny > quarantine > require_review > allow` 取严。没有匹配规则时才使用该 Policy 的 `default_effect`。
管理 default 为 require_review 时必须携 default_operations（仅可审批操作）及 default_review_requirement；未选操作默认 deny，
可用显式 allow 规则放行；不能为连续读取／执行配置一个无法消费的审批。
因此同一 Policy 可以“默认禁止，Alice 例外允许，Bob 需要审批”。多个适用 Policy、Realm 与实际 Circle／Strand 父层
按同一取严顺序求交；精确主体 allow **MUST NOT** 覆盖另一适用 Policy 或父 scope 的 deny。
完整权威 current 证明没有适用管理 Policy 时管理门为 allow；unknown、stale、fork、超时、私有缓存缺行与不完整分页
**MUST NOT** 当作无配置。allow 只放行治理门，不生成业务能力、安装或加入事实。

Agent／Applet 管理 Policy 的 `ak.policy.set` payload **MUST** 携精确 nullable `expected_revision`。
首次 `null` 只来自完整权威无记录证明；更新须命中当前 revision，Policy id 禁止换成另一族逃避 CAS。
写入者通过 `ak.self.current_results.read.exact.v1` 的 `selector={kind:policy,policy_id}` 读取同 cut Policy typed current；
仅当前有本 scope `ak.policy.set` 权限者可读 Agent／Applet Policy。真正不存在返回 exact `never_written`，无权或隐藏返回 not_found；不提供 Policy 枚举。
写入者须有该 scope 当前 `ak.policy.set` 权限；用户例外不是成员自行修改管理员 Policy 的入口。

## 2. 操作分离

Agent 管理操作为 `join/authorize/execute/read/deliver/publish/serve`。join 包括初次加入与离群重入，
不控制群外 provision；禁止 join **MUST NOT** 自动停止已有 Agent。authorize 限制所有新 grant／扩权路径，
execute/read/deliver 持续约束既有行为。owned_agent 来源与全部普通替代 grant 均保留主人动态硬上界。

publish 只控制主人开启本 scope public 意图的接纳；serve 持续控制 public 请求交付及公开出站。
主人 public 模式、当前 serve 放行、实际 caller/action/resource 权限及主人／Agent行动上界 **MUST** 同时成立。
管理员 **MUST NOT** 代签主人模式；serve 被禁止时保留原签 public 意图但停止后续公开服务，合法私有协作不因此被封禁。
Realm public 不表示跨 Realm、匿名或全网可调用。publish 被禁止只阻止新开启；停止已公开服务须限制 serve。

Applet 操作是 `install/create_bot/map_ghost/join/authorize/execute/read/deliver/publish/serve/invoke`。
install 保留 `ak.realm.admin` 门；普通成员没有隐式安装权。create_bot/map_ghost 分别要求真实创建 grant，
accepted installation、当前治理及所要求审批；禁止新创建不自动停用既有主体。具体主体的持续操作仍按本节相应门判定。
Applet 的 public 意图由受管主体原签 Profile 的 reserved applet_interaction 成员确定；请求接纳须 public、serve／invoke管理门、
实际调用人动作／资源权、Service 业务 parent、终端主体权限及 Device／membership 全部成立。public 展示不授予任何调用能力。
invoke 按完整 caller 和实际动作／资源匹配；调用人无权时不能借 Applet 强权限执行。代表人执行额外重验本人的 current 权限。

## 3. 可执行审批与申请生命周期

只有 join、publish、create_bot、map_ghost 支持本管理族的 require_review；其它管理操作 **MUST NOT** 配置
require_review，须用可直接执行的 allow／deny／quarantine 或动作自身已登记审批合同。
join 与 publish 用完整已 producer 签署的 `ak.member.state`／`ak.agent.interaction.set` Event 作为候选，
通过原 Event admission 的 `approval_signatures` 消费批准。两个治理 action 标签 `ak.agent.join`、`ak.agent.publish`
只选择该审批门，不把 subject-only join 或 controller-only 模式改变成持 grant 即可代写。
Bot／Ghost 本人 join 使用原签 `ak.member.state`，治理 action 为 `ak.applet.join`，不推断 Agent ownership；
Applet 服务发布使用受管主体在该业务 scope 的原签 `ak.profile.create`／`ak.profile.update`，以 `profile_fields.applet_interaction={effective_scope,mode:"public"|"private"}` 表达本 scope 意图；
对应管理发布 action `ak.applet.publish`。该 reserved profile 成员必须通过闭合类型核验，不能由普通展示字段或缺值推断 public。
private 或未写入不开放公开服务；private 切换不要求 publish 审批，serve 仍是持续上界。Service 可为自己的 accepted 受管主体申请审批，不能代 Device 签署该 profile/join Event。
Bot／Ghost 创建批准完整 provision RequestBody，签名放在该 operation 的外层 `approval_signatures`；
审批目标原像剔除这个证据字段，不能改写 authoring request 或四个 Event。

申请通过 `ak.self.management_review.command.request.v1`；查询通过 `ak.self.management_review.read.status.v1`；
批准／拒绝／取消通过 `ak.self.management_review.command.decide.v1`。请求人 **MUST** 是当前合法 controller
（Agent join／publish），或 exact installed Applet Service（Bot／Ghost创建、本人 join／服务发布）。Service 请求沿正式 RFC 9421 Service
认证，个人请求沿自身 SessionGrant 认证；不得由 Bot 冒充 Service或以 runtime pairing 批准替代 Realm 审批。

Station **MUST** 在返回 pending 前耐久固定 request id、候选 canonical digest、请求人、scope、management operation、
ownership/provision、controller join、候选 Agent join意图、installation/epoch、当前 Policy revisions、原 interaction／Profile revision、原签范围及 expires_at。
申请 TTL **MUST** 不超过 24 hours；创建还受 authoring request 更短期限限制；Policy 变化或任一绑定变化使未消费批准 superseded，
不能靠新 Policy 更宽松就复活旧批准。一个请求 id 的 exact retry 返回同一 outcome；同 id 异 canonical candidate 拒绝 `duplicate_conflict`。
同一请求人、scope、operation、候选摘要只允许一个非 terminal 申请；不同候选是不同请求，批准不得换主体、公钥、external tuple 或 scope。

审批者 **MUST** 持有实际 scope 当前 `ak.realm.admin`，并满足命中规则／治理审批的指定审批人及 threshold。
申请人不得自批；review_requirement或default_review_requirement固定approver_actor_ids、threshold和max_age_seconds；threshold不得超过distinct授权批准人的数目。多人threshold按完整Actor资格核验，并对同principal的跨Station重复票去重；自批始终拒绝。
每个批准沿唯一 ApprovalSignature 的 `context_kind=management` context，绑定 operation、action、effective scope、exact request_id、request digest、
initiating actor、批准人、nonce和签名时刻；initiating actor 必须等于候选 Event 的实际 producer（executed_by 存在时为它，否则为 actor_id），创建时为 Service。
申请人 controller／Service 单独绑定在 ledger，并不改写实际 producer；申请人、实际 producer及受益主体均不得自批；不得以 UI 管理员标签或私有布尔值代替。
Station 保留审批签名、历史 key 验证依据和当前资格；decision 只从 pending 转移，批准达到全部 threshold 才变 approved。
拒绝／取消／过期／superseded **MUST** terminal，迟到签名与重放不得复活。请求人只能取消自己未消费的请求，管理员可拒绝。

pending/approved 本身没有业务效果，**MUST NOT** 产生 membership、Welcome、群材料、读取／订阅或公开执行资格。
最终业务接纳 **MUST** 再验原签候选、全部 current 管理门、批准人权利、ownership、生命周期、controller membership、
安装／epoch、业务 grant 及原 Join／MLS 条件；该审批不是免检 token。消费 ledger、nonce、exact business outcome 和业务
接纳 **MUST** 属于同一可恢复治理事务；失败零业务效果且不消费，结果不确定保留恢复 intent，exact retry返回原 accepted outcome。
已成功的消费与历史批准证据不被后续 Policy 变化改写；新交付仍受当前门。部署不得用收到 approve response 代替业务 accepted。

## 4. Applet 授权来源与持续上界

Applet Service 的业务 parent subject 与 child issuer **MUST** 是逐字段相同的 `ActorId.service`；
Bot／Ghost 是独立 `ActorId.account`，不得再构造 Service 同 principal 的 Account 来绕过类型相等。
合法 Realm issuer 给 Service 的创建 grant 与业务 parent 是分别审批的许可；创建 action、问责、provision、URL、
namespace、requested_scopes 与 `applet_authority` 绑定均不是业务转授权。

业务 parent **MUST** 有明确普通 `authority_control`，批准本 Applet 可接收下放的 `allowed_managed_actor_roles`，
实际业务 actions/resources、期限、quota和审批要求；其 `applet_authority` 绑定 exact Applet／Service／registration epoch。
Service 可通过既有 Event admission 原签 terminal child；Event.actor_id 与 grant issuer 都为该 Service，不携 executed_by。
child subject **MUST** 是 accepted provision 属于本 Applet 的具体 Bot／Ghost完整 Account，并在批准 role与实际 scope内。
`issuer_authority_refs.kind=grant` 指向真实有效parent；depth、roots、逐动作／资源贡献、全部约束收窄沿普通 lineage合同计算。
child **MUST** 显式 `max_authority_depth=0`、`authority_regrant_allowed=false`；Service不能授予第三方或另一Applet的主体。

parent 与 child 各 **MUST** 恰有一条 allow、grant_local 的 `applet_authority`。parent 的 `executed_by` **MUST** 等于其 Service subject（亦为 child issuer）；child 的 `executed_by` **MUST** 等于其完整 Bot／Ghost Account subject。两条绑定的 `applet_id`、`registration_epoch` **MUST** 相同；accepted provision 另外证明该 Account 的 Applet／Service 管理归属、角色与 hosting Station，不能靠 namespace 或同 principal 推断。child 复制 Service executor、缺失／重复绑定、混入其它 Applet／epoch／Station 均拒绝。

这是普通约束收窄中有且仅有的受管 terminal executor 重绑定：仅将上述已验证 Service parent 的绑定 executor 换成其已批准具体 Account，不能删掉绑定、保留第二条 Service 绑定或扩大任何其它约束。普通 authority_control、动作／资源／期限、所有 deny／review／quarantine 与共享 ancestor quota 继续原收窄／持续上界；本规则不授权一般 delegation，也不使 terminal child 可再转授。持续 parent 求值使用其 Service 主体事实，child 执行使用其真实 Account producer 事实；不能以一个求值上下文替代两者。Service→Account child 不授权 Service 借用它签 Account 的业务 Event，subject_only 本人同意仍要求该 Account 原签。

这项 Service child准入不需要另授一个无限通用 cap.grant 能力；它是“真实parent允许的一层terminal下放”的封闭准入，
Service身份／historical signer证据沿 accepted registration与原签grant解析。Station不能代Service签Event。
没有普通控制、role许可、实际业务 action 或有效 parent均拒绝。创建 grant不能当message action的parent。

parent revoke、期限、registration实例／epoch或相应scope安装失效即时使child ineffective，不逐个铸造child revoke。
Service 可沿 self/events 的封闭原 issuer 分支原签撤销自己的 accepted terminal child，携 exact revision；业务 parent 已失效也不阻止合法收权，不赋一般 revoke 权。child revoke只影响自己；parent共享quota按原parent／constraint／Service／时间切片原子消耗，新增主体／设备／child不重置总额。
所有 membership-derived reading、直接 grant、订阅、Blob、未来MLS材料及跨站新交付 **MUST** 继续受该managed主体的
当前 Applet业务上界与安装fence限制；不能用另一许可入口绕过来源。
普通成员读取不必另外创建child read grant，但上游须覆盖读取：Event／Commit／history、Welcome及MLS状态供给要求
`ak.event.read` 上界；内容／附件还要求对应 `ak.object.read_content` 与原对象／history资格；依赖metadata只披露该合法操作所需材料。

Service通过 `ak.self.applet.authority.read.material.v1` 用自己的 Service认证取得自己exact scope／指定grant的
原文、accepted Event／Commit及同cut current结果。只接受parent.subject等于该Service且绑定本Applet的grant，
已失效／terminal仍可用于受限审计；不提供其他grant枚举、群history、私钥或SessionGrant。
结果每个grant与请求、registration、scope、Realm/current generation、revision及effective head **MUST**一致；
Station接纳child仍重读权威current，不信任Service缓存allow。完整审计也不把私有parent原文写入共享Event。

## 5. 多 scope、设备与撤销

创建来源是immutable provenance；每个业务scope独立验证当前installation、主体current状态、Device有效授权范围、
membership/history、grant及治理。撤销scope A不使scope B合法路径自动失效，也不能借B访问A。
单主体停用使用该完整Account原有Account lifecycle/current status；由合法Account Authority按原issuer-ledger合同接纳，
不新增Agent pause假身份、不赋Service控制人类恢复的权限；删除成员／撤child可单独停止该scope业务。
单Device撤销只影响该Device；所有scope无有效安装时全部新业务与新群材料拒绝，但身份历史与合法撤销控制保留。
本主体 PCR 的合法 key revoke／身份轮换控制可沿 accepted provenance 和原 Account Authority／principal 控制合同验证，不要求仍 active 的业务 installation；
此例外只读取精确 signer／resolution／Device 授权和控制所需原文，不提供群资料，不允许创建、扩 scope 或恢复业务。
Devicescope扩展须主体自己通过普通replacement authorize及完整possession transcript原签；Service HTTP key不能代签。

只在真实Bot／Ghost Device具备合法MLS状态时取得群内容，Applet Service不成为群内容接收主体。
future delivery fence不等待MLS Remove；密码学移除仍由合法committer推进epoch，不承诺擦除已交付内容／secret。
新交付／附件／持续subscription／notification／epoch材料与远端供给 **MUST** 每次过current屏障，缓存不能保持旧allow。

## 6. 披露与验收

申请人只读自己request，审批人只读合法scope审批所需候选；隐藏request、无权、未知统一not_found。
批准权不提供Sidecar、private selection或群私有内容。对外解释只披露本人可见的scope、门类、pending／accepted／effective差别，
不得泄露其他成员、parentgrant或审批存在性。
规范fixture及可执行门 **MUST** 覆盖默认例外／上级deny、批准前无效果、ownership/epoch/current变化、并发和exactretry、
Serviceparent→terminalchild、siblings／多scope／quota、错误Account／Device、无session认证及future delivery撤权。
协议验证通过不证明SDK、Station、bridge、UI或真实跨站MLS流程已实现。


`ak.vector.applet.managed_governance.v1` 由managed-governance-fixture.json与正式pipeline的managed_governance_contract gate执行；包含真实RFC9421 Ed25519签名原像和反变异，仍不声明生产E2E通过。

Ghost preview 已存在映射时返回 `existing_managed_actor` anchors；provision 以同一 closed reuse 字段提交，不再调用 author，也不重写四 Event。新 scope 仍须当前 map_ghost 许可及审批；reuse 不重复消耗创建数量 quota，若批准 mapping 次数 quota 则按映射操作一次消费。

Profile 意图的 effective_scope 必须等于 Event.scope_ref 及目标 Profile 实际 Realm／Circle；同一主体多 scope 使用各 scope 各自的 Profile，不复用 PCR 创建 Profile。创建四 Event 中的初始 Profile 不得公开业务服务；之后由主体原签在实际业务 scope 建立或修改 Profile，public create 与 update 都经过同一 publish／review 门，任何 patch 变体均不能绕过。

管理申请 target 与 operation 必须唯一匹配：join→本人 join Event，publish→开启 public 的真实 interaction／Profile Event，create_bot/map_ghost→相应 creation RequestBody；必须核 Event kind、目标完整主体、actual scope及 public transition。创建审批的目标摘要按最终 RequestBody（只剔除 approval_signatures）重算；private pending 请求外包装摘要不得代替 ApprovalSignature 的原业务摘要。

management ApprovalSignature 的 context.request_id 必须命中同一可见 pending ledger，签署时刻不得早于该 request 建立；不同 request 的批准不能转借。decision 与消费都验证这个签名绑定；已 superseded 的申请即使相同候选也不能用新 ledger 回收旧批准。

误合入的 client-pull、Service 同 core Applet Account 与专用 invocation/result/relay 合同已撤回；
不保留可选 transport、exchange/cancel、专用消息块／proof domain 或 invoke capability。业务使用实际动作授权，
内容使用具体 Bot／Ghost Device 的原生 MLS／Blob 通道。AK-NC-083／084／085 仅保留失效编号记录，不构成有效协议要求。
