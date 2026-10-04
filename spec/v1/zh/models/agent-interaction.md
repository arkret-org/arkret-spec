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
普通字面 @ 不寻址。已打开 Sidecar 保持私有，公开 Agent 参与其中不使会话自动发布。

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

## 5. 转换、非追溯与验收

fanout 按派生时的 current mode 与第三方 gate 一次性求值；之后模式／gate 改变不补发、不撤销旧派生。
实际动作接纳另查 current mode 与授权：public 转 private 后已排队请求不得用旧 public session 继续共享
出站。Private 转 public 不重放旧外部请求、不公开旧 private history。旧公开消息、已知身份与旧 key 不承诺
抹除；controller／Agent 离组或撤销后的准入、delivery、MLS remove／rotate 按原合同立即收紧。

响应不得增加 private 目标特有错误、可查询 stub、派生计数或回执。无效／未披露目标的统一拒绝与时序分布
须覆盖负向向量，不承诺每次网络耗时相等。正式 fixture 绑定 `ak.vector.agent.interaction_mode.v1`，覆盖
controller-only CAS／unknown、roster 不变、路由矩阵、强行 mention、各共享写／代行门、切换竞态和私有上下文隔离；
机器 schema 验收不替代 SDK／服务／客户端／E2EE 实机验收。
