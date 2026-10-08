---
title: Agent 公开与私人交互
status: candidate
normative: true
stability: v1
updated: 2026-10-04
---

## 0. 规范语言

本文 MUST／MUST NOT／SHOULD 按 [规范性语言](../conformance/normative-language.md) 解释。

## 1. 模式与权威

Agent 在每个 Realm 具有独立的 `interaction_mode=private|public`。它不是 Agent 身份子类、lifecycle、
selector visibility 或 participation selection。完整 AccountId 的两个分量 MUST 一起比较。
Circle／Strand MUST 继承所属 Realm 的模式，不提供局部覆盖；其读取授权、membership、MLS 与 participation
ceiling 仍各自求交，只能进一步拒绝动作。公开只表示该实际 scope 的授权成员可读，不表示全网公开。

唯一写入 Event 为 Realm-scoped `ak.agent.interaction.set`，唯一 current family 为 `agent_interaction`，
selector 为 `{kind:"agent_interaction",agent_account_id:<完整 AccountId>}`；Realm 由 source stream 指定，
不得再写入 subject。其 closed payload 按顺序为：

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `agent_account_id` | yes | AccountId | 当前有效 Agent 的完整账号 |
| `controller_account_id` | yes | AccountId | 当前已接纳 provisioning／accountability 的 controller |
| `interaction_mode` | yes | enum(private, public) | 显式整体置换，不接受 null |
| `expected_revision` | no | typed revision | 首次省略；已有记录必须逐字匹配 `{commit_id,stream_position}` |

模式是治理端可见的控制事实，payload MUST 为明文控制材料；不能藏入 Message 密文、Profile、Account Data
或 participation selection。Event MUST 经现有 `ak.self.events.command.submit.v1` 提交到 Realm 当前治理
Station，不新增 REST endpoint、storage key 或通用 resolver。读取复用 exact typed current read 与
authorized snapshot／replication，使用同一 Realm stream revision，不造第二份 CAS/version。

admission class `agent_controller_self_authored_proof` MUST 验证 authenticated original requester account、Event account
author 和 payload.controller_account_id 逐字相等，并验证其 current active Realm membership、Agent exact
active membership／controller generation、有效 ownership／provisioning／accountability 与设备 producer proof。
Service author、Agent 自改、第三方管理员及任何 executed_by 代行 MUST 被拒绝；Realm capability 不得替代
controller 签名或放宽该谓词。动作不授予任何 capability。required authority 未决时 MUST fail closed。
经 own Station 转交治理 Station 时，original requester 按现行 self／peer submit 的可信传递合同验证，
MUST NOT 把 peer transport 的 Service bearer 身份冒充主人，也不得要求转发 service 自著模式 Event。
CAS 失配 MUST 以既有 `failed_precondition` 零写入拒绝；Event、whole-value current 与 RealmCommit 原子接纳。
same-value 设置也产生新 revision；不触发补发、不改变 membership generation，不驱动 MLS Add／Remove。

**Human／Agent 的共同授权原则（normative）**：普通协作 Realm 的 membership 本身不授予
`ak.message.create`，此规则同时适用于 human 与 Agent。Realm authority-root 的 current controller
按 [realm-and-space §2.5](./realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative) 取得 owner
operational authority；其它账号依其自身有效 capability grant 求值。Agent 是独立完整 AccountId，
MUST NOT 继承 controller 的 root／owner／admin／grant。产品可通过成员角色或下面的显式配置流程
简化授权输入，但 MUST 实际签署并接纳相应 grant；角色标签、入群和 UI 开关均不是授权源。
独立 Direct 的已登记 participant authority source 保持原合同，不由本段追加普通 Realm grant。

普通主人可通过 [自有 Agent 受限来源](../authz/owned-agent-authority.md) 明确授权，无需另持通用 grant action 或管理员补签；这是一条独立签名的 terminal grant，不是继承。全部普通协作授权路径在动作、读取和投递时继续受主人当前权限与有效管理禁令的硬上界。

value 恰为 `{controller_account_id,interaction_mode}`，按同一 stream 的 committed position 整体置换。
controller binding 与当前 ownership 不一致时，该值不可授权动作。首写前只有治理端同一 current cut 验证
never-written 才得到已确认默认 `private`；snapshot 缺项、缓存缺失、stale／fork／未取得 head 均为 unknown，
MUST NOT 伪装成 private，MUST 阻止需模式判定的发送／执行。首次公开必须主人显式签署 `public` 设置。

## 2. 成员与披露

模式 MUST NOT 修改 Realm／Circle membership 或 [Sidecar §5](./sidecar.md#5-参与者与有效访问) 的派生集合。
Sidecar 参与者始终为主人加上该 Realm 内全部 active、ownership／runtime-key authorization 有效的自有
active member Agents；不得自行邀请、添加、移除或退出。公开 Agent 也参与这个私有 scope。
desired 不等于 effective，实际访问继续受独立 Sidecar MLS readiness、历史读取权与 key 可达性约束。

普通第三方产品成员列表、profile preview 与 picker MUST NOT 展示私人 Agent 的参与候选；不得从第三方
猜出的 ID／裸文本补全 private selector、确认 profile 或生成存在性 stub。主人私有候选仍需获授权完整
AccountId；公开候选缺 selector 时沿用 [actor §3.3](./actor.md) 的明确 fallback。
已公开 Agent 临时 gate 关闭不改变模式，不允许为按钮查询 controller-private selection。

本合同不伪造协议 membership／MLS roster、成员数或树，也不删已授权可读成员事件。底层身份已经可读时，
MUST NOT 承诺该 Agent 的存在不可知；不新增披露适用于尚未披露的事实。Mode Event／current 受原 Realm
控制材料读取授权，读取者可能因此知道私人身份；UI 隐藏不构成协议不存在性证明。Sidecar 的对象、活动、
请求、mention、内容和计数仍 MUST 对其他群成员按原私有 scope 严格隔离。

## 3. 入站与执行

公开 Agent MAY 在原授权范围接收第三方请求、回复或主动群发，但必须分别通过 capability、key scope、
session、lifecycle、membership／history／E2EE 及 current selection／各级 ceiling；公开不是所有动作授权。

私人 Agent 的第三方 direct／audience mention MUST 不产生定向 request、notification、inbox、push 或
该 Agent 的 mention subscribe 投影；原群消息及其它合法目标保留。主人手工构造共享 scope 的私人 Agent
mention 也不能唤醒它，应另写 Sidecar 请求；不因作者是主人而绕过请求 scope。该限制不删除普通 history，也不代替
读取授权：Agent MAY 读取获准群上下文供主人私有协作，但 MUST NOT 从 history scan、watch、reply、
assignment、调度或工具入口把外部请求变成对外交互。

普通共享 Realm／Circle scope 的 Agent producer／executor MUST 在接纳时为当前 public；private／unknown
MUST 拒绝其共享消息创建／编辑、reaction、共享对象／Relation／assignment 修改及对外通知、Signal 或工具
副作用。`actor_id=controller,executed_by=agent` 同样受此门约束，不能用代行隐藏 Agent。请求、执行与回复
必须保持原 scope。主人自著的普通群消息不受此 Agent 出站门影响；私人 Agent 仍可在 Sidecar 或主人独立
Direct 内按原权限调用私有工具、产生私有动作，不自动扩大到其它用户的 Direct。

私人模式不禁止维持已授权成员资格所必需的 `ak.mls.genesis`／`ak.mls.commit`、Agent 自身的
`ak.member.state`，以及只影响自身的 Strand watch／read cursor。此例外只免除交互模式门，MUST 继续通过
原有 producer、membership、MLS roster／governance 和目标主体授权；不得借维护 Event 修改第三方成员、
共享协作对象或产生第三方通知。PCR／Agent control Realm 的身份治理独立于普通协作 Realm 的交互模式。

服务端 MUST 强制可验证的 author／executor／scope／模式与 action 门；E2EE 正文里的 mention 或模型
上下文不能假装由无密钥服务端读出。持钥客户端和 runtime MUST 验证内容触发、私有 provenance 与队列绑定。
明文场景派生器执行内容门；无法识别密文内容的 blind wakeup MUST NOT 成为私人 Agent 的执行授权。
sidecar/direct 的 controller 请求与 private scope 内 Agent 协作不属于外部请求。
已明确处于获授权 Sidecar／主人 Direct 的私有请求不依赖群内模式读取成功；模式 unknown 不能阻止这些
独立已确定 scope 的私有协作，也不能授权任何共享动作。

## 4. Composer 与私有信息流

普通 Realm composer 只含公开 Agent 时 MUST 使用普通共享 Strand，即使作者是主人；只含主人的私人
Agent（可含主人自身）时 MUST 使用 Sidecar。两种模式混合，或私人 Agent 与外部／audience 混合 MUST
阻止发送，不自动拆分、不丢目标、不公开私人请求。模式 unknown MUST 保留草稿并阻止发送。
第三方手工构造 private mention 不转其消息到主人的 Sidecar，也不删除原消息，只抑制私人触发。
普通字面 @ 不寻址。原 Strand 每份草稿与每次发送／重试 MUST 按当前有效完整 AccountId mention
重新判路由；没有 Agent mention 使用原 Strand，公开 Agent 使用原 Strand。Sidecar 合并历史、旧私密
session、旧 addressed targets 或 last verified request 均不得隐式填入目标或使下一条消息继续私密发送。
用户删除／解绑私人 Agent mention 后，无 Agent mention 的新消息恢复原 Strand 路由与受众提示。
已接纳 Sidecar 私密历史保持私密，只供原获授权参与者读取；改变新草稿路由不发布或迁移旧历史。

Circle composer 中主人向私人 Agent 的交互 MUST 阻止；不得把 Circle 请求、引用、附件或上下文转到
Realm Sidecar。公开 Agent 在 Circle 仍须本 Circle 读取／membership／MLS 门；父 Realm join 不替代这些门。
独立 Direct 保持独立 scope，私人 Agent 只接受主人获授权请求，外部 Direct 不构成绕过入口。

Message accepted 后 scope immutable。新增 mention 的 revise、reply、reaction、quote／forward／export、
附件／Blob／preview 都 MUST 遵守原 scope 和内容读取边界，不将已有共享消息“编辑成”Sidecar 消息。
主人编辑共享消息新增私人交互 MUST 阻止并提示另写 Sidecar 请求；第三方手工引用仍按 §3 抑制触发。
草稿恢复、目标／模式／scope／账号变更、重试 MUST 重校当前状态，撤销先前的共享确认，私有失败不得转群。

同一个公开 Agent 的 Sidecar 私有上下文 MUST NOT 自动用于公开回复。持钥 runtime MUST 按完整 controller
AccountId、Realm、actual scope 和 request／exchange 隔离上下文、队列及回复；Sidecar 中多 Agent 私有
输出、工具结果或摘要不可因 public 模式自动出站。显式成果发布沿用 [Sidecar §8](./sidecar.md#8-private-view-与显式发布)：
主人最终 allowlist 确认、自著新普通 Event，不复制 private envelope、私有身份引用／metadata 或历史。
该发布不开放私人 Agent 的共享 producer 身份；服务器不承担不可验证的密文语义信息流判定。

### 4.1 公开回复配置与有效状态（normative）

提供公开 Agent 回复配置的产品 MUST 提供可读的正常配置入口；用户 MUST NOT 被要求先寻找高级
权限页面、复制 DID 或手填 action token 才能完成普通消息回复配置。入口可以嵌入 Add Agent 或
成员设置，但仅 Add／Join、Public 模式写入及 participation replace 仍 MUST NOT 自动生成 grant。

“允许此 Agent 在此 scope 回复”是一个需明确确认的产品操作，而不是新的协议 operation 或授权
预设。产品 MUST 在确认前绑定已获授权的完整 Agent AccountId，展示实际 Realm／Circle／Strand、
拟授动作、有效期／限制和是否将 Agent 模式改为 public。默认只选择本次回复所需的
`ak.message.create` 和最窄适用 scope；扩至整个 Realm 或增加 reaction／其它动作 MUST 明确展示
并获确认。若使用 [capabilities §9.1](../authz/capabilities.md#91-agent-授权预设展开normative)
的注册 preset，MUST 完整展开并展示其动作，不得把仅消息权限冒称为包含 reaction 的 preset。

一次用户确认 MAY 驱动数个既有独立写入：获授权 issuer 自著的 `ak.capability.grant`、controller
自著的 `ak.agent.interaction.set` 与 controller-only participation replace。产品 MUST 分别验证
各自 signer、issuer 上界、scope／resource 和 CAS；已验证主人为自有 Agent 配置支持动作时 MUST 使用
[自有受限来源](../authz/owned-agent-authority.md)，主人当前可在该范围发言时不得要求管理员另给授权。
非自有／不支持该来源的动作仍需正式获权 issuer，不得借 Agent key/session 或服务代签补齐。
已存在且覆盖已确认账号／action／resource 的有效 grant MUST 复用；不得为正常刷新或重启
重复签发。该协调不是原子 batch，没有跨 Realm Event 与私有 participation 的统一事务或成功回执。
任一步拒绝或 unknown MUST 保留各步真实结果，不能把其它步骤的成功显示为全部配置完成。

UI MUST 区分“已选择允许回复”“所需配置已确认接纳”和“当前可以回复”。最后一项只可来自
当前已验证的完整账号／scope 绑定、public mode、有效消息 authority、内容／服务面 scope、
membership／lifecycle、current participation／各级 ceiling、runtime session/key 及实际 scope
MLS readiness 的共同满足；本地开关、过期观察、配对成功或模型已经运行均不能替代这些输入。
unknown MUST 显示待核实并驱动已有恢复路径，已确认缺授权 MUST 向获权 controller／issuer 显示
该具体缺项及正常配置入口。不得为此向第三方披露 controller-private selection、私人 Agent
存在性或私有诊断；第三方继续使用既有通用拒绝。此有效状态是本地产品诊断，不是新的 wire
字段、Account Data key、权限证明或服务端准入来源，最终动作仍由原门独立求值。

异步提交开始时 MUST 就地显示进度并阻止同一意图重复点击；queued／结果未知不得显示成功，
须用既有耐久 authoring 身份恢复同一 signed submission，不能另造 grant Event。成功提示必须
来自正式接纳结果，GrantId 只从被接纳的 EventId 按现行规则派生；失败须就地显示可处理状态。

## 5. 转换、非追溯与验收

fanout 按派生时的 current mode 与第三方 gate 一次性求值；之后模式／gate 改变不补发、不撤销旧派生。
实际动作接纳另查 current mode 与授权：public 转 private 后已排队请求不得用旧 public session 继续共享
出站。Private 转 public 不重放旧外部请求、不公开旧 private history。旧公开消息、已知身份与旧 key 不承诺
抹除；controller／Agent 离组或撤销后的准入、delivery、MLS remove／rotate 按原合同立即收紧。

响应不得增加 private 目标特有错误、可查询 stub、派生计数或回执。无效／未披露目标的统一拒绝与时序分布
须覆盖负向向量，不承诺每次网络耗时相等。正式 fixture 绑定 `ak.vector.agent.interaction_mode.v1`，覆盖
controller-only CAS／unknown、roster 不变、路由矩阵、强行 mention、各共享写／代行门、切换竞态和私有上下文隔离；
机器 schema 验收不替代 SDK／服务／客户端／E2EE 实机验收。

公开回复配置验收 MUST 包含：human joined 但无消息 authority、Realm root controller、Agent
不得继承 controller authority、仅 mode／selection 不能生成 grant、普通入口的一次明确 scope
确认、无 issuer／越过全局 ceiling／错 Station 或 scope、部分接受／响应丢失／重复点击，以及
restart／重新配对／清库后的重新核对。保留同一完整账号与 Realm 的恢复 MUST 复用仍有效的
grant；新账号、新 Station 或新 Realm MUST 重新取得明确绑定的授权，不得按同名 Agent 复活
旧权限。清理本地 endpoint 私态时，配对／密钥恢复／MLS 入群按原合同分别完成，不能以服务端
grant 尚在宣称 endpoint 已可发送。明确拒绝的密文不重放，修复权限后用新请求实测；旧 private
请求、context 与 acknowledged history 不因新 grant 自动发布或重执行。产品 MUST 以独立空库
首次配置和保留状态重启分别验证真实 mention → model → 同 scope 的已接纳、可显示加密回复，
不能以手工插 grant、修数据库、恢复已有会话或延长等待预算替代冷启动验收。


## Realm 公开治理门

controller-only public模式接纳另须通过publish治理；持续公开请求和共享出站还须通过serve治理与实际caller/action/resource授权。管理者不能代写主人模式。模式public而serve失效时保留原签意图、拒绝新公开交付，不停止原本合法的私有协作。审批和用户差异化规则按 [managed-governance.md](../authz/managed-governance.md) 执行。
