---
title: Scope 设置、继承与约束
status: candidate
normative: true
stability: v1
updated: 2026-10-19
---

## 0. 规范语言与适用范围

本文的 **MUST** / **MUST NOT** / **SHOULD** 按 [规范语言](../conformance/normative-language.md) 解释。
普通协作内容使用 Realm 的提交流。Space 提供导航与放置检查，Strand 组织协作事项和 Track。个人 Sidecar 独立签名、提交及加密。各项设置的作者、revision 与接纳要求见下列专章。权威状态缺失、过期、分叉或无法核实时，执行者 MUST 按相应协议拒绝依赖该状态的动作。

## 1. 对象边界矩阵

| 对象 | 成员、历史与密钥 | 主要依据 |
| --- | --- | --- |
| Realm | 拥有成员 current、历史策略、授权和可选 MLS group。Realm link 不传播成员、策略或密钥。 | [Realm](../models/realm-and-space.md)、[Realm link](../models/realm-links.md) |
| Sidecar | 用户归属站按主人启用、所有权、生命周期及有效运行端派生参与者。每个 Sidecar 固定使用独立 MLS，其私有流不进入来源项目的站际转发。 | [Sidecar](../models/sidecar.md) |
| Space | 父子关系用于导航，放置约束可拒绝创建或移动。Space 的可见性不授予子对象读取资格。 | [Space 层级](../models/space-hierarchy.md) |
| Strand | 普通 Strand 和所有 Track 使用其 Realm 的成员、历史和 MLS 边界，仍须按动作、字段和 Track 验证授权。 | [Strand](../models/strand-and-message.md) |

来源对象与 Sidecar 的关联只定位私有视图。向项目发布时，作者 MUST 提交经过独立授权的普通 Event。项目成员或管理员不能通过来源关联取得 Sidecar 内容或历史密钥。

## 2. 设置与约束

| 设置 | 解析规则 | 权威依据 |
| --- | --- | --- |
| 成员与进入 | Realm 独立配置 join rule 和目录可见性。`parent_membership` 在准入时验证来源成员资格；Space 层级、Realm link 和 Sidecar attach 不产生 join。 | [Realm](../models/realm-and-space.md)、[Sidecar](../models/sidecar.md) |
| 历史与已读披露 | 普通对象遵守所属 Realm 的历史门和唯一已读披露策略。个人偏好依 Strand、Realm、default 的顺序解析，发送仍须满足 Realm 的 required 或 disabled 设置。Sidecar 使用其私有读取与 MLS 历史合同。 | [历史](./history-visibility.md)、[已读](../discovery/read-receipts.md)、[个人偏好](../discovery/client-preferences.md) |
| Agent 与 Applet | Agent 交互模式取所属 Realm 的设置。Strand participation 可在 Realm 的上限内收紧。管理 Policy 按已登记的实际目标、动作与资源求交；Space 树不传递权限。 | [Agent 交互](../models/agent-interaction.md)、[管理治理](../authz/managed-governance.md) |
| 治理、生命周期与保留 | Realm 治理站验证本 Realm 的生命周期与授权，Sidecar 的私有资格由用户归属站管理。保留、披露与解密分别判定。 | [联邦](../sync/federation.md)、[Sidecar](../models/sidecar.md)、本文 §4–§5 |

## 3. 加密与放置

接受 Realm MLS Genesis 后，应用内容 MUST 按对应 group 与 epoch 发送；禁止撤销激活、替换 group 或回退明文。公开治理材料按 Event 注册类别处理。Sidecar 的私有 group 独立激活和验证。任何一方的密钥均不能代替另一方的密钥。

Space 的可选布尔字段 `child_scope_policy` 为 true 时，接纳方 MUST 在写入放置关系的同一事务内验证目标 Realm 已接受 MLS Genesis。该约束覆盖 Strand 创建及移动、Space 初始放置及改挂、结构性 contains。条件不成立时拒绝该写入；不得自动开启 MLS、改绑对象或复制密钥。字段缺省与显式 false 的更新语义由 [Realm 与 Space](../models/realm-and-space.md) 定义。

## 4. Retention 与 legal hold 的跨 scope 适用边界

### 4.1 保留、披露与解密分别判断

对任何保留或删除判定，执行者 MUST 区分实际数据对象及其 scope、持有副本的 Station / service、
适用策略与合法来源。保留某个 Event、密文 Blob 或审计原件，不授予其读取、复制披露、索引、
跨 scope 发布或解密权；管理员、hold 请求者、存储服务和治理 Station 均不能因此获得 MLS secrets。

Realm、Sidecar 的 stream 独立。现有 [历史 §3.2](./history-visibility.md#32-retention-不裁剪-commit-链normative)
的 Commit 链保留规则适用于这些 stream：retention 不删除 accepted RealmCommit，不产生或移动
readable floor；到期 Event 仍占同一 Commit 槽位，以 withheld 表达不可披露。authority bundle 必需
genesis / handoff 原件继续保留。Snapshot 中的 `retention_and_history_floor` 仍只表达 history / join floor。

Realm 的 `history_access`、Sidecar 私有参与者门及 MLS key availability 不因 retention 变长、
暂停删除或进入 hold 而放宽。hold 中保留的副本也不得通过普通 scan / search / snapshot 暴露给无权主体。

### 4.2 Blob、派生副本与删除

[Blob §5 / §8](../crypto-media/media-and-blob.md)以 Blob owning Realm、引用授权、来源 scope、
retention、live references 与 legal hold 共同判断访问／GC。Blob 的 `realm_id` 不代替引用它的
私有 Sidecar 内容读取资格；Space reparent、Strand move 或 source-context attach 不构成删除授权或 hold 解除。

已生效且覆盖该对象的 legal hold 阻止物理删除；普通视图仍可 redaction / withheld。Blob bearer
presign 的 hold 检查、强一致回查及拒绝继续按 Blob 专章；不能把“保留”解释为持 bearer URL 可读。
缩略图、preview、转码、搜索文本、embedding 与通知摘要仍须随真实源的撤回／擦除重新裁剪、删除或最小化；
已有 hold 覆盖的保留材料不得因该普通披露失效被物理删除，也不得反向恢复普通访问。

部署本地的 `retention_expires_at` / `legal_hold` 是本 Station 保留元数据，
不是 canonical moderation decision，不能改写其它 Station 的决定或授权，见 [审核 §2.6](./content-moderation.md#26-moderation-决策-must-committed)。
Realm terminal、GC 与 erasure receipt 仍按 [Realm §2.6](../models/realm-and-space.md)区分；
terminal 不自动擦除，hold 可以阻止适用的物理删除，receipt 必须如实记录结果。

满足 [Realm §2.6.2](../models/realm-and-space.md#262-跨-station-erasure-receipt-fanoutnormative) 的既有 hard-erasure
适用条件时，issuing / receiving Station MUST 继续履行 exact receipt / retained stub、peer 投递、耐久重试、
签名 acknowledgement、接收方实际擦除结果及 incomplete / timeout 义务。`accepted` / `duplicate`
acknowledgement 只确认接收，不证明物理删除完成；完成或阻断以接收方自己的实际 erasure receipt 为准。
本机普通 retention / GC 不等于全网擦除；本节不扩大该 hard-erasure 合同的触发条件或目标，也不创建第二套删除确认。

### 4.3 现行 v1 的保留控制范围

当前 v1 复用已登记的保留、披露、删除及授权合同。以下是明确未定义的通用能力，不是实现必须补齐的缺口：

- 统一的用户可配置 scope TTL、Realm 治理域／未来 scope wildcard 保留设置，以及 Sidecar 独立保留字段或继承。
- retention 专用的最低／最高期限双轴、期限覆盖或多策略冲突求解器；已有 Policy 的授权约束与求值规则保持原合同。
- 通用 hold 设立／解除 Event、管理入口、组织权限、跨 scope 扩张、peer hold 命令或确认 ledger。
- 为保留密文而托管／导出成员 MLS secrets、保证未来解密的历史密钥归档服务。

`policy_kind=retention` 是现有分类，`retention_policy_id` 是现有投影；两者本身不提供通用 lifetime
字段或 scope selector。本节不删除或变更这些机器形态，不把部署存储配置解释为 Arkret 协议设置。
部署已有且合法适用的存储保留／清理安排只约束其实际受控副本，并继续满足 Commit 链、必要原件、
引用、hold 与披露约束；不得以本机安排宣称所有参与方、远端服务器或备份均已物理删除。

停止普通披露与后台清理完成分别判断；已真实适用的 hold／保留限制继续阻止不合法删除。
失败或部分完成 MUST 使用该操作已有的结果合同如实表达；本节不增加统一错误、成功回执或新的查询服务。
hold 解除不恢复内容可见性，后续清理由原流程重新判断资格，不新增自动解除或期限重置业务。

已登记 Blob hold、部署本地保留元数据、擦除回执与专用读取／presign／删除检查继续生效。
不能用“未定义通用 hold”忽略已覆盖目标的禁止删除或强一致检查；也 MUST NOT 由部署私有字段、
Space 子树、裸 Realm ID 或未认证配置伪造新的 Arkret current、跨 scope 权力或成功结果。
任何未来新增业务须另行正式定义，不得通过本节或现有扩展成员自行发布为 current-v1 支持。

## 5. 明文服务的跨 scope 适用边界

唯一 Realm 名单作者为 `ak.realm.plaintext_visible_services`，current 为
`realm_plaintext_visible_services`；它完整替换声明集合。每项按现有 payload 声明 service identity、
`service_kind`、`purposes`、`data_classes`、`visibility` 与可选期限。名单不另造 Sidecar policy，
`purposes` 自由文本与 ServiceDescribe 自报能力都不能替代 `data_classes` 或实际授权。

跨 scope 使用同一服务时，必须同时成立：

1. 该内容所属 Realm 当前声明允许该服务接收对应 data class，并满足该服务专章的额外条件。
2. 内容提供者在实际交付时有权读取／处理目标 exact scope 的相应内容；scope membership、history、
   lifecycle、capability / policy 及所需 MLS readiness 继续独立验证。
3. 存在该具体功能已登记的明文或受限 key 交付路径。MLS 业务明文由获授权客户端显式选取／提供；
   治理 Station 不能因为服务被列入名单就解密、发布历史 epoch secrets 或赋予持续解密能力。
4. 输出、索引、缓存、派生摘要与通知继续遵守原目标的披露和撤权边界，不能扩大到其它 Realm、
   其它 controller 或其它 Sidecar；选取已有内容不自动授权后续新内容。

名单只放行对应的服务治理门，不授予服务 Realm membership，也不替代 Sidecar 的有效参与者与
私有访问合同。若某功能不能用已登记路径证明目标授权与合法交付，MUST fail closed；不能在现有
service entry 的扩展成员中塞入未登记 scope selector 以声称授权成立。

| 功能 | 必须继续满足的独立合同 |
| --- | --- |
| search / projection | [Search §4 / §5](../sync/privacy-preserving-search.md)：服务、data class、index retention、generation 与目标授权；search hit 不构成权限 |
| thumbnail / attachment preview | [Blob §5.3](../crypto-media/media-and-blob.md)：`thumbnail` / `attachment_preview` data class、源引用和输出可见性；不得为预览取得整组 MLS secret |
| 解密媒体 SFU / MCU | [媒体 §8.2](../crypto-media/media-service-binding.md#82-治理绑定normative)：媒体服务声明、`media_plaintext` 名单、当前 toggle / MLS 覆盖和用户确认；只沿已登记 call / focus / participant frame-key 路径 |
| Push | [Push §5](../discovery/push-notifications.md)：名单不放宽 blind-wakeup metadata 限制；可见通知另须该专用 profile 与目标授权 |
| holder-private account data | Realm 名单不授权个人 blocklist 等 account-private 内容；见 [client-preferences](../discovery/client-preferences.md) |
| Sidecar 私有上下文 | [Sidecar §5 / §8 / §9](../models/sidecar.md)：只能沿现有获授权私有路径；source attach、Realm 管理权或公开 Agent 模式不开放私有内容 |

当前 v1 不增加 Sidecar 专属 service-consent Event / current、scope selector、例外名单、
通用后台明文订阅或第三方删除证明平台。这些是明确未定义的通用能力，不是现有功能需要等待的新前置。
内容提供者的合法授权仍由本节四项条件及该功能已有合同证明，不另造统一的 scope 同意记录。

媒体、Push、search、preview、Agent / Sidecar 已登记的持续服务、current 重验、撤权与必要的专用
确认继续按原合同执行；不因此增加逐次弹窗，也不移除媒体警示、controller 原签、审批或其它现有要求。
没有已登记输入路径的后台跨私有 scope 取材 MUST NOT 开放；修复具体功能的来源或接线不足不能借机新增任意明文导出。
撤权阻止后续输入，索引／缓存按原来源与撤回／保留合同处理；不能宣称已交付外部的明文可被协议追回。
§4.2 已有 erasure receipt 义务保持，不因不增加通用第三方证明而被免除。
