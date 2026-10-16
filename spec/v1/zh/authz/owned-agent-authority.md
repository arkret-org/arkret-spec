---
title: 自有 Agent 受限授权
status: candidate
normative: true
stability: v1
updated: 2026-10-15
---

## 0. 规范语言

本文中的 **MUST** / **MUST NOT** 按 [normative-language.md](../conformance/normative-language.md) 解释。本文的机器裁决源为 [owned-agent-authority-registry.json](../../artifacts/registry/owned-agent-authority-registry.json)，承载仍使用 v1 的 Capability Grant、Policy、普通 Event admission 与 typed current result；不新增身份、profile、session 或私有数据库授权路径。

## 1. 显式自有授权来源

有效成员 **MAY** 向协议已验证的自有 Agent 明确签发受限 `ak.capability.grant`，无需另持通用 `ak.capability.grant` action、普通 parent `authority_control` 或管理员补签。该例外只通过单个 `issuer_authority_refs[0].kind="owned_agent"` 表达，**MUST NOT** 与其它 ref 混合。Event author **MUST** 是 ref 中完整 controller account ActorId，等于 grant issuer；subject **MUST** 是被钉定的完整 Agent account ActorId，禁止 condition subject、service author、executed_by 与主体相似性替代。

controller 自身 **MUST NOT** 是 canonical provisioning 所证明的 Agent；不能通过 Agent 再 provision 子 Agent 重入该专用来源绕过 terminal 限制。此判定不用 Actor Profile 分类字面值。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `owned_agent` | 常量 | 专用自有执行来源。 |
| `realm_id` | yes | `RealmId` | 等于 grant 与 Event 的 Realm | 实际协作治理域。 |
| `controller_account_id` | yes | `AccountId` | 完整两个分量 | 原授权主人。 |
| `controller_join_event_id` | yes | `EventId` | exact current join generation | 主人 membership binding。 |
| `agent_join_event_id` | yes | `EventId` | exact current Agent join | subject 的 membership incarnation。 |

治理 Station **MUST** 验证 accepted provisioning/accountability、独立 Agent 身份、当前 ownership、两个 exact join 与 `agent_controller_binding`；Agent join 的 controller 与 generation **MUST** 逐字匹配 ref。未知、terminal、错账号／Station／Realm／scope **MUST** fail closed。此来源不直接引用主人某条 grant，允许在原确认范围内使用主人当前等效合法来源；accepted ownership material 与 current lifecycle 的取材沿用 [Agent runtime evidence](../identity/key-management.md) 已登记的闭包。跨站 current 取材未登记或不可验证时 **MUST NOT** 放行。

ref 是签名覆盖的 immutable 意图，**MUST NOT** 带 producer-selected revision、digest 或 Commit snapshot。grant.id 仍由 Event ID 重类型派生；唯一签名仍为主人 Event envelope proof。reducer 对该来源派生 `authority_depth=1`、`authority_root_refs=[该 owned_agent ref]`，后者是自有执行根而非 Realm authority-root，**MUST NOT** 被用来取得 root controller 资格。grant **MUST** 显式带普通 `authority_control`，`max_authority_depth=0` 且 `authority_regrant_allowed=false`；任何下游 `kind="grant"` ref 引用它都 **MUST** 拒绝。普通 grant 的不可转授与 root-transfer 语义不变。

## 2. 动作与持续上界

专用来源只能签发 registry 的 `supported_actions`。v1 登记消息创建、reaction add/remove、作者自己的 revise/redact、event/Strand/object 的已登记读取；其它 action、admin/moderation、授权管理、聚合 action、服务面 action 与 `act_on_behalf` **MUST NOT** 通过此来源取得。它们若有独立正式授权，仍受本节对自有 Agent 的动态硬上界和其它审批门约束。不能把 owner/admin 聚合或 UI preset 静默复制给 Agent。

每个普通 Collaboration Realm 内自有 Agent 的实际操作 **MUST** 同时满足：主人当前有效行动权、原签明确 scope/action/constraint、Agent requested/key/session ceiling、当前管理限制、participation/governance ceiling，以及动作自身的 membership/history/E2EE/approval 门。该动态上界 **MUST** 对管理员直接给 Agent 的普通 grant、membership-derived reading 与所有替代授权路径同样生效。独立 Direct 的 participant authority 按其原合同求值，**MUST NOT** 引入不相关群的权限；Sidecar 的 roster/读取来源仍是其专用来源，但同 Realm 管理限制、主人当前内容读取边界与群动作禁令不能被 Sidecar 绕过。

主人权限求值 **MUST** 使用完整 controller 身份及同一 actual resource、target、字段、有效期、claim、policy；不能拿 Agent 的 claim/device/session 证明主人有权。Agent 自己的条件另行独立验证。多来源先按 [constraint-schema §15.4](./constraint-schema.md) 合并全部匹配来源的 deny/quarantine/review；allow 必须存在一条完整覆盖该 action/resource 的合法路径，禁止跨 grant 拼接。不复制静态 action 列表，不要求旧 parent grant ID 永久相等。

`*.own` 的唯一已登记 subject 映射是独立作者自己的对象：主人当前持有同一 own action 的资源／时间／字段上界，Agent 仅能操作 canonical author 为 Agent 的对象。主人消息不是 Agent 自己的消息。身份固定的 approver、指定 Device、对象所有者或未登记 claim substitution **MUST NOT** 因 controller 关系改写；无法保留条件时拒绝。创建消息不替换 actor_id，runtime 用 Agent 的有效 key 签名。

签发时 **MUST** 对每个 action/resource selector 验证主人当前可表达的权限覆盖，保留原确认有效期与更严约束；quota 的可用余额只在实际消费时原子判定，签发不消费行动额度。每次执行 **MUST** 重验 current 上界。quota **MUST** 使用被选主人来源的原 `(grant_id,constraint_id,controller ActorId,slice,window)` counter，与主人和其它自有 Agent 共享扣减；Agent 自己的更严 quota 另行满足。多完整合法 allow 路径按 canonical grant ID 无符号 UTF-8 顺序选取当前可满足的路径，选择与 reserve 在同一 quota authority 原子完成；global deny 不因选路径消失，换 Agent/ref/session 或新发授权不重置父 counter。多 counter reservation **MUST** 与业务效果原子提交或以耐久唯一 reservation、失败幂等释放闭合。重试沿原 operation identity 只计一次；跨 authority 无共同 reservation authority 时 hard quota fail closed，不接受异步 overshoot。

上界 **MUST** 覆盖 history/query/scan、Blob/附件、订阅每次后续交付、notification/定向投递及未来 epoch 访问材料，不能只在 session、订阅建立或 Event authoring 时检查。常规成员读取仍按 membership/history visibility，**MUST NOT** 强加显式 `ak.event.read` grant。Strand 所有 track 共用一个 Realm/Circle effective scope；track/字段 constraint 只收窄行为，不产生独立 membership、读取边界或 MLS group。

**Agent 内容会话交集（normative）**：机器合同为 registry 的 `session_content_authority_contract`，具名裁决见 `ak.vector.agent.session_content_authority.v1`。Agent Auth 的 capability-grant 交集 **MUST** 解释为目标 action/resource 上已经成立的完整合法授权路径，不限于 literal `ak.capability.grant`。来源按实际资源 profile 求值：普通 Realm/Circle 的读取使用 exact active membership 与 history visibility；独立 Direct 使用其 accepted participant authority；Sidecar 使用 exact `(realm_id, controller_account_id, sidecar_id)` 的专用 desired/effective authority；其它动作仅能使用该动作已登记的 grant 或 profile authority。读取来源 **MUST NOT** 派生 write/reply/publish 权限，也不得由 provisioning、accountability、私有 requested scope 或 participation selection 单独制造任何内容权限。

机器向量中的 verified gate predicate **MUST** 对应实际 action/resource 的适用门，不能由默认 action 推出未登记的读取选择位。`participation_current_denied` 显式使用已有完整 capability grant 的 `ak.message.create`，在执行时撤回 `reply_message` selection；原合法会话和 grant 不替代当前 selection。membership/profile 的独立读取仍按其原合同求值，selection 本身不授予或撤回读取资格。

签发时 **MUST** 先按每个 action/resource 验证 durable 来源资格，再与 immutable provision ceiling、current accepted key ceiling、本次 session request、资源 policy／管理限制及适用的主人 current 上界求交。该步骤不代替执行时的 history、participation、MLS、quota、approval 等独立门；MLS 尚未完成可保留合法的读取 ceiling，但 **MUST NOT** 因会话已签发就交付业务 payload。普通群与 Sidecar 使用本节主人动态内容上界；独立 Direct 继续使用其 participant 合同，**MUST NOT** 强加其它群的 membership、grant 或管理限制。

本次请求的 `requested_scope` 是会话 action/operation 请求，**不是** provision 的 immutable `requested_scope`；`agent_scope_request` 仅收窄目标。内容会话 **MUST** 有非空、已验证的 Realm 或 Strand selector；省略／空 selector **MUST NOT** 表示所有内容资源。Realm selector 不授予该 Realm 内所有 Circle、Direct 或 Sidecar 的读取资格；每次仍按 actual scope 的 profile 检查 exact binding，Sidecar 身份从 accepted Sidecar binding 派生，不新增 request-side participant 或 sidecar selector。`scope_details` 沿既有 closed 结构物化资源和 typed constraints；`capability_grant_refs` 仅列实际使用的 literal grant，没有 literal grant 的合法读取允许该数组为空，**MUST NOT** 伪造 grant ref。`policy_refs` 也不要求合成默认 allow Policy：只有完整 current 治理证据证明没有适用限制时才使用既有默认值，unknown／缺行仍拒绝。

签发与消费 **MUST NOT** 把不同路径的 action、resource、constraint 分别求并集后拼出完整 allow。现有扁平 ceiling 无法精确保留多路径相关性时，issuer **MUST** 保守收窄到可表达的共同覆盖或要求按资源重新申请会话，**MUST NOT** 放大为笛卡尔积。所有来源的匹配 deny/quarantine/review 仍按既有规则取严，conditional authority 的未物化条件、history 窗口、mandatory provision constraints 与 quota 在实际消费时继续重验，不能因未出现在 `scope_details` 的有限字段中被丢弃。

**服务会话续接与 current 来源（normative）**：初始服务会话可没有内容 action；在合法 membership／Direct／Sidecar 来源建立后，runtime **MUST** 用既有 `ak.gate.account.command.issue_session_grant.v1`、新 proof challenge 与新的签名 request intent 申请所需 content action 和 selector。新签发不要求 predecessor session 已含该 action，也不要求 controller 为正常会话签发再次在线批准；它 **MUST** 在已验证 provision/key ceiling 内重新求交，不能补回上层遗漏的 action。immutable provision 缺项仍须 provision 新 Agent，key 缺项仍须正式 key 续权／轮换。旧会话的 immutable claims 不改变；新 issue 建立独立 session chain，不隐式 supersede 旧链，旧链仍只能行使原 ceiling 并受同样 current 门约束，需要终止时走既有 revoke。

`ak.gate.account.command.refresh_session_grant.v1` 只轮换 predecessor 的既有 action/resource/constraint ceiling，不接收新 scope request，不增加内容 action、资源或条件权限；必须复验 current holder/key/lifecycle 与该 ceiling 的权威来源，无法满足时拒绝，runtime 通过 fresh issue 申请较窄或新增的合法范围。正常 refresh 沿既有 issuer-ledger transaction 原子 supersede predecessor 并继承 `session_id`；exact issue/refresh replay 沿既有 byte-identical／terminal 合同，**MUST NOT** 借重试重算并返回扩权凭据。参与选择更新仅在原授权 ceiling 内生效，旧 session overlay 不能替代 current selection。

同一 Station 内来源资格 **MUST** 由 owning Station 从 accepted、完整且 exact-account/resource 绑定的有效权威状态提供给 issuer，并与签发结果绑定；部署内 channel 沿 `service-http-binding §2.2.3`，不新增公开 operation、receipt 或 evidence carrier。current/freshness 的含义沿来源原合同：独立 Direct 继续使用已验证授权区间与已知撤销规则，不新增逐次 source lease／origin 查询。introspection 返回 exact credential 的冻结 ceiling，**不是** membership／主人 current／Sidecar effective 的替代证明；每次实际读取、排队后交付与未来 epoch 材料领取 **MUST** 在目标资源 authority 的准入边界重验适用的当前有效门。来源按其原合同已知撤回后即使 JWT 未过期也不得继续供给；unknown/stale/fork、取材失败或跨独立治理边界没有已登记且可验证的来源时 fail closed。已领取的历史密文／本地密钥不能被追溯收回，不得把停止新供给宣称为抹除既有知识。

**内容会话带外批准（normative）**：机读合同为 registry 的 `session_human_approval_contract`。仅当普通 Collaboration Realm／Circle 内，本次所需的内容动作全部缺少显式 Agent grant，而已验 holder proof、current Agent／controller、provision／key ceiling、exact membership／ownership、authorize／execute 管理门、participation、主人在同一资源上的完整行动权与必要条件全部满足时，Account Authority **MUST** 返回 HTTP403 RFC9457 `claim_required`，closed extensions 严格为 `reason_code="human_approval_required"` 与 opaque `approval_request_id`。可批准动作限 registry 的 eligible_actions；缺少 own 对象等必要事实视为未知。deny／quarantine／require_review、条件不满足、未知来源、上层缺项及 Direct／Sidecar 专用路径 **MUST NOT** 被转换为此分支。批准不是绕过任何门的例外。

Controller 通过既有带外 UI，明确确认 exact Agent／scope／actions／constraints，再按 §1 的 owned_agent 或已有合法 delegation 来源原签并提交 `ak.capability.grant`。Agent 用新的 proof challenge／新的签名 request intent 重试现有 issue operation，在可选 `approval_evidence_refs` 中引用 accepted grant Event；该数组非空、最多32项、去重并按 canonical EventId UTF-8 字节序排序，属于 request_canonical_digest 覆盖的原始请求。每项 **MUST** 为当前有效、controller 原签、subject exact Agent 且确实用于本次 action/resource 的 accepted grant；Event、covering Commit、current grant 与完整来源仍由 owning Station 核验。错类型、未accepted、伪造、跨账号／资源、撤回／失效或未使用引用 **MUST** 失败关闭。引用只收窄已成立来源，不制造授权；实际使用的 GrantId 沿既有 scope_details 冻结，执行时继续重查 current 门。

`approval_request_id` 只是本次拒绝的关联提示，**MUST NOT** 充当 bearer、批准证据、authority source、重试 request identity，或仅凭它取回私有意图；不新增公开 approval operation、独立审批权限系统或非 Event 授权 carrier。此拒绝 **MUST NOT** 创建 session、issuer reservation／proof replay 或业务效果，不返回 CAPTCHA／OTP／browser redirect／password prompt。已有合法来源的正常签发与 refresh **MUST NOT** 要求人类再次批准；refresh 不接收此引用或扩大 predecessor ceiling。已完成 issue exact replay 沿原 durable outcome，不重新求交，也不因本分支改变历史结果。

**Sidecar 引导分阶段（normative）**：首次 Welcome／claim read／consume 的资格使用 exact current desired authority、accepted Add/Welcome/claim lineage 与 current Agent endpoint，以及 requested/key/session、主人内容上界和 read/deliver 管理门。Welcome／未来 epoch 访问材料的内容读取映射为 `ak.event.read`，目标从 accepted Add/Commit/Welcome lineage 派生到 exact Sidecar scope，不能按父 Realm 或 runtime 自报目标放行。claim read／consume 保留各自 service operation、exact recipient ledger／receipt 与 profile gate，不因它们是 ledger 操作要求 `ak.message.create` 或其它内容写 grant；它们也不额外授予 Welcome／payload 读取权。**MUST NOT** 为取得建立 effective 所需的材料提前要求该 endpoint 已 effective。desired 本身也不是业务 payload 读取资格；只有该 endpoint 完成既有 Welcome 验证、durable MLS state 与 consume 后才按 effective 门供给业务 payload。其它 Sidecar 的 effective、父 Realm membership 单独或另一 endpoint 的 consume 均不得替代；撤回 desired 后旧 queued Welcome 与未来 epoch 材料同样拒绝。

## 3. 管理限制与默认值

管理 carrier 为 `ak.policy.set` 的 generic Policy，`policy_kind="agent"`，rule `kind="agent"`；使用 [policy.schema.json](../../artifacts/schemas/policy.schema.json) 的 closed `agent_target` 与 `agent_operations`。写入者 **MUST** 通过该 Realm/scope 当前 `ak.policy.set` coverage（含正式 policy/manage/root coverage），不能凭 UI 管理员角色或 controller 身份写入。policy.id/Realm 绑定与原签不变。该 Agent／Applet 管理 Policy 的 closed payload **MUST** 按字段顺序携带 `{policy_id,expected_revision,value}`：`expected_revision` 是 required nullable `CurrentRevision`，`null` 只表达已由完整当前治理证据证明的首次写，object 必须逐字匹配该 typed Policy row 的最后 `{commit_id,stream_position}`。未知／遗漏／私有缓存缺行不是首次写证据；错修订必须零效果拒绝。该字段 **MUST NOT** 进入 Event 顶层、Policy value 或 Agent source ref；除 Agent／Applet 管理 Policy 外其它 kind/family 的 payload **MUST NOT** 携带它。已成为 Agent Policy 的 id **MUST NOT** 重绑为其它 policy kind/family 绕过 CAS；解除禁令须明确更新同一 Agent Policy 的规则，并通过其当前精确修订。已 accepted 的 exact Event retry 沿原 durable outcome，不重做 current CAS。

`agent_target.kind` 是 `all`、`controller` 或 `agent`；后两者只携对应完整 AccountId，selector 只使用 verified ownership，不用 slug、profile 标签或裸 principal。`agent_operations` 是非空去重数组：`join`、`authorize`、`execute`、`read`、`deliver`、`publish`、`serve`。`actions` 与 `resources` 若存在为 AND 收窄；动作使用内容 action token，不能借服务面 scope 授予内容。读取或投递先映射所需内容动作；不能确定映射则拒绝。execute 的具体操作仍通过已有 action mapping，不新增权限 action。

默认经完整当前治理证据确认无适用 Agent policy 时，管理 gate 为 allow：有效成员可自行添加、明确授权自有 Agent，无管理员逐次批准。该 allow 不是动作权限或自动全选。证据 unknown/stale/fork 与私有缓存缺行 **MUST NOT** 当作 absent。rule 内部按既有 priority 与同 priority 取严规则；多个适用 Policy 及 Realm/Circle/Strand 层的结果按 deny > quarantine > require_review > allow 求交，不允许用户设置或较窄 scope allow 覆盖父级有效限制。审批未有登记 carrier 的操作 **MUST NOT** 接纳 require_review 配置，不能用审批要求制造永远无法满足的分支。

`join` 禁令只阻止新的 Agent join（含离开后重新加入），不改变已有成员；`authorize` 禁令阻止向匹配 Agent 新签发授权／扩权，包含自有来源与管理员独立 grant，获权管理员须通过正式 Policy 更新／解除限制而非另签 grant 绕过。停止已有 Agent 的行为必须显式限制 execute/read/deliver。controller selector 对该主人当前及未来全部 Agents 持续生效，不枚举设置时清单；specific Agent 不误伤 sibling 或主人。重建同名、换 runtime/grant/session、重新授权或提高主人权限都不能绕过。禁令不跨完整 AccountId 推断、不控制群外 Agent provisioning 或全局 lifecycle，也不赋予管理员读取 private selection/Sidecar 内容的权利。

## 4. 主人撤回、恢复与重试

`ak.capability.revoke` 增加专用收权分支：target 为 owned_agent grant 时，original issuer/controller 的完整 account 签名可以撤回该 grant，无需通用 revoke action、管理员批准或 Agent runtime 在线。该分支 **MUST** 检查 target、original issuer/ref、账号当前签名资格、exact grant current revision/CAS，禁止 executed_by。它不要求被授动作仍有效、join generation 仍 active 或通过管理 join/authorize gate；即使已离群或 binding 已终止，只要原账号仍有合法签名资格也可以关闭自己签出的记录，不能恢复身份／权限。terminal account 的新写屏障仍适用。其它 grant 的普通 revoke target guard 不变。

原 issuer 可通过现有 `ak.self.current_results.read.exact.v1` 的 exact `{kind:"capability_grant",grant_id:<grant_id>}` selector 读取自己签出的 owned_agent grant（包含 ineffective/terminal）及 revision；仍只读、有签名会话资格、非枚举，未知／无权返回同一通用 not_found，不返回 never_written。授权不能借猜测 ID 披露其它 grant。管理员独立 grant 仍按其原 revoke 资格关闭；主人可用 participation 自己的更严 gate 阻止使用，不能冒充管理员 issuer。

明确 revoke/relinquish 是旧 grant ID 的 terminal，**MUST NOT** 因主人获权、禁令解除、resume、缓存恢复或旧签名重放重新 active；主人可以重新确认、签发新的 Event-derived GrantId，并通过全部当前门。暂时父权限归零、pause 或管理 gate 关闭只使 active grant ineffective，不把它投影成 revoked；条件恢复后仅在原选择/有效期/ownership/exact join 仍有效时重算，不增加动作或 scope。离组重入、错 Station/Realm、Agent incarnation 变化 **MUST** 新的明确授权。

exact signed Event 重试先确认已有 durable admission outcome：已 accepted 的历史结果返回原 outcome，不能因当前撤权改判或再次扣额；未 accepted 的候选在新接纳位置重查 current。未知结果保留原 submission 查明，明确拒绝的旧密文不得因权限恢复重放；只能经新的明确业务意图产生新提交。

## 5. Current 依赖、远端与审计

治理 Station **MUST** 在原子 admission transaction 锁定／校验 controller 与 Agent membership、ownership/lifecycle、grant/root/policy/claim、target revision 及父权限来源；依赖按 canonical key 排序，变更竞争整条候选零效果失败或保留 dependency pending。owner transfer 不改写旧普通 root grant，但 Agent 新操作重查原 controller 当前上界，新 Realm owner 不成为 Agent controller。授权失效不等待逐 Agent revoke、leave 或 cleanup，服务不能合成签名 Event。

各实际 scope 的治理 Station 是 Event 接纳权威；Circle/Sidecar 与父 Realm 的可撤销依赖在同治理 Station 事务内重读，不制造跨 stream 总序。远端读取／delivery enforcing service 只有在其实际交付点取得治理 Station 的经认证 current 判定并把 exact request/内容动作/resource/接收者绑定于同一串行交付屏障时才能放行；缺少已登记 current 取材／交付屏障则 fail closed，可路由回治理服务，不允许有限 TTL 的旧 allow 冒充撤权即时生效。客户端消费已 accepted 历史 Commit 不要求在线证明全球最新，也不重算历史接纳。

每次权限收缩阻止未来服务读取/交付与未来材料领取；MLS roster/epoch 移除仍须合法 author、Commit、客户端 rotate/remove，不能宣称撤权擦除了已有 epoch secrets 或已交付密文/明文。cache 的 digest/revision 依赖必须包含 controller 权限与管理 Policy，并在未知、冷启动、重启时重建，不复用旧 allow。同站原子准入、远端新交付屏障和密码学排除是分别验收的终点。

审计保留 controller 原签意图、Agent 自己签名、实际 admission basis、所用父路径/共享 quota 与管理裁决；这些是 verifier-private backing，不把父 grant/private selection 原文塞进共享 Event。独立重放须得到相同结果；第三方拒绝使用已登记通用错误，主人可看自己授权和适用失效范围，不向第三方泄露私有父来源。

## 6. 产品与 conformance

Add Agent／Reply as agent 正常入口 **MUST** 展示完整账号、实际 scope、最窄动作与当前管理限制，明确确认后用上述自有来源 author Grant，并分别配置 mode/participation；两者独立，不冒报跨服务原子成功。不要求用户手填 DID/action，也不要求可发言主人找管理员补签。selected、accepted、effective 分开显示，主人可撤回与重新授权；管理员入口区分禁止新增、禁止授权及限制已有行为，scope/主体/期限与最终 current 结果可核对。

机器 fixture 与反变异 **MUST** 覆盖普通成员无 grant/revoke action 的自助、错主体/scope/binding、不可转授、全部 grant 路径动态上界、全局 deny/身份条件、多父路径/共享 quota、部分收权/expiry/root transfer、管理员按主人覆盖未来 Agents、禁止新增不误停已有、撤回/重新授权、未知依赖、并发与 exact retry、读取及订阅/附件/未来材料屏障、重启和独立 replay。静态 fixture 通过不证明 SDK、服务、客户端或真实加密回复已实现。


## 7. 精细治理与审批

同Policy默认值、用户例外、publish/serve分离及申请/批准/消费完整合同 **MUST** 按 [managed-governance.md](./managed-governance.md) 执行。join与publish现在有登记的ApprovalSignature carrier；其它管理操作没有本族review carrier时仍禁止require_review。个人Agent保留owned_agent专用terminal来源及所有替代路径的动态主人上界，不能把Applet业务grant链迁为owned_agent。
