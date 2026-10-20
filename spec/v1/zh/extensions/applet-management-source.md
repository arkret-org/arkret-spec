---
title: Applet 配置、审批与 Realm 主体接纳
status: candidate
normative: true
stability: v1
updated: 2026-10-21
---

# Applet 配置、审批与 Realm 主体接纳

规范关键词遵循 [规范语言](../conformance/normative-language.md)。

## 1. 权威与职责

本合同只处理 Applet Realm Bot／Ghost，身份、控制流、签名与材料的完整定义在
[Realm actors](./realm-actors.md)。普通成员仍以自己的 Account／Device 证明操作者身份，
目标 Realm 当前治理 Station 独立验证其管理权限。操作者所属 Station 不承载新 Bot／Ghost 的账号权威。

Applet runtime 持有主体 DID／Device 私钥并生成候选；治理 Station 接受原签 Event、管理控制流、
保留审批与结果。Applet 不必兼任 Station。治理方不得伪造主体、生成代签 Device，或中转私钥。

能力发现 MUST 按上述职责使用真实服务角色。独立 Applet 使用 `service_kind=applet_service`，
只有实际实现全部成员时才可声明 `ak.operation_bundle.applet_service.applet.v1`；
该 bundle 包含现有 Applet edge 操作，包括主体候选 author 和配置 execute。
治理 Station 的 `ak.operation_bundle.station.applet.v1` 不包含这两项 Applet 专属执行操作，
仍保留其它已有 Station 方向 edge 操作；双向 transaction 的方向、来源签名和接纳规则不变。
管理员配置 submit 保留在 `ak.operation_bundle.station.applet_install.v1`，由治理站执行。
通用 describe 与 Applet edge describe 是两个既有操作，角色通用 describe bundle 仍独立保留。
合并部署也必须按每个 endpoint 的真实 Service 身份和角色声明能力；共同进程或地址不授予代签权，
不得借用另一个角色的 bundle，也不得以 HTTP 路由存在替代完整能力声明或完整实现验证。

## 2. 管理员主动配置

配置 intent 固定 request_id、effective_scope、new_bot 或 existing_realm_actor 选择。
existing 选择必须包含同 Realm 的完整 ActorId.realm，匹配当前 Applet／manager，不能用显示名或裸 core 认领。
governor 检查真实 Account 操作者权限、current registration、安装与 Policy，持久化意图后再调用 runtime。
execution_intent 绑定 Applet／Service、原始治理任期、scope、registration／epoch、操作者和选择；
execution_request 外层绑定当前治理方、时窗与签名。recover 可由新任治理方处理原意图，但不得改写意图。

runtime MUST 验当前治理链、请求签名、准确 Applet／Service／scope 与有效期，按原 request_id／完整 intent
去重。它准备独立 DID／控制 key，返回控制 PoP 与 Service 原签创建 Event，不在本地宣称已被治理接纳。
身份生成阶段是 candidate；治理方把精确候选与管理员意图绑定，执行所需 review，沿标准 self Event submit 接受。
治理前验证候选创建权限与当前状态，不能把最初管理员点击当作永久授权。
created／reused 结果必须带原真实创建 Commit；pending／unknown 没有伪造 Commit。

管理员已有本次真实管理授权时，不重复请求其批准同一意图；Policy 的多方审批仍按精确候选执行。
取消、重试、故障恢复保持原 request_id、canonical intent 与结果，不二次扣 quota、不重新创建 identity。
未知结果只能恢复／重试原请求，不能当失败退款后偷偷新建。转治理前必须完整导入私有意图和结果 ledger。

## 3. 自动 Ghost 与按操作审批

治理方可授持续自动 Ghost 创建许可，约束 namespace、scope、quota、有效期及当前安装。
每个 create 仍核许可、完整主体签名与 tuple 唯一性；不因此要求每个 Ghost 都另点确认。
require_review 才创建审批；deny 零写。管理员主动 Bot 配置与 Applet 自动创建使用同一候选和接纳合同。

review target 固定完整原签 Event；create 是 Service Event 内含独立候选，join／publish 是实际主体 Device
的原签 Event。外层 approval 不回填到 Event 中。新批准不能解除撤权、换掉候选或让 requester 自批。
current registration、scope、权限或 Policy basis 改变时，未消费批准按既有 superseded 规则处理；
刷新传输 nonce 不能延长原意图／review TTL。已接受 exact 重试只恢复原结果。

## 4. Subject 与 Device 来源

管理方从所属 Realm 私有控制流直接校验 accepted identity、manager、双 status、generation 和 Device。
Service 签 terminal child 时，subject 必须是自己的 realm actor，授权链仍受原 parent／安装／scope 上界；
没有预先 Device 不妨碍创建 child，但 child 不自行授权 Device 或成员资格。
Realm actor 本人控制维护沿原生方法分支；真实设备业务按各实际 scope 求所有权限条件的交集。

这里只读取已有准入状态，不接纳附带的 Account/PCR 来源包，不发布第二个主体 current 接口。
获准材料仅由 Realm actor material 操作给出 signed current／原件／exact 结果；普通业务历史读者仅得最小公钥。
subject、批准人或管理 Service 相同 DID／key 不构成身份等价；比较完整 ActorId。

## 5. 交接与完整性

handoff 按 [Realm actors §9](./realm-actors.md#9-治理交接与验收)迁入完整控制和操作私态，实际落盘重导出验证。
在导入完整性未知时拒绝新的接受和不存在断言。历史批准、已消费结果与原签 Commit 不重签，不改写源任期。
当前治理方可签本次材料响应，但这不使旧许可重新生效，也不授其主体控制权。

`ak.vector.applet.management_source.v1` 继续覆盖配置签名、审批、重试、自动 Ghost 与候选/接纳分离；主体原生控制由 Realm actor 专项向量覆盖。

Applet 受管 Bot／Ghost 的持续同身份恢复由当前管理 Service、accepted recovery policy 与 DID 原生后继共同授权，见 [Realm 主体§10](../extensions/realm-actors.md)。普通创建许可不授予任意映射接管；恢复不重复申请创建，不产生新身份，恢复 current／pending／终态和安全收尾随原 Realm 交接。
