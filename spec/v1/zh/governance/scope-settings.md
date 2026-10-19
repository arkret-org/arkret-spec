---
title: Scope 设置、继承与约束
status: candidate
normative: true
stability: v1
updated: 2026-10-19
---

## 0. 规范语言与适用范围

本文的 **MUST** / **MUST NOT** / **SHOULD** 按 [规范语言](../conformance/normative-language.md) 解释。
本文汇总 Realm、Circle、Sidecar、Space、Strand 的现行设置关系；不新增 Event、字段、Policy kind、
current family、HTTP operation 或密钥交付途径。各项的唯一作者入口、签名、revision 与接纳规则仍由链接的专章定义。

**Realm 治理域**与 **Realm-default scope** MUST 区分：前者承载共同的 authority、federation 与授权上下文，
后者是该域内的一条内容安全 scope。Circle、Sidecar 是同一治理域内另外的原生 scope；
Realm-scoped 控制 Event 不因此成为 Circle/Sidecar 内容读取权，也不表示其全部设置自动向内传播。

下文使用以下关系分类，不构成 wire 枚举：

- **独立配置**：只消费目标 scope 的 current；没有父值 fallback、合并或上层值补全。
- **继承同值**：专章明确只有上层作者入口，下层使用该值，不能局部覆盖。
- **上限求交**：适用的上层限制与本层限制同时满足，下层不能用 allow 绕过上层 deny。
- **资格／生命周期约束**：上层事实改变本层有效资格或写入门，不复制或改写本层 canonical state。
- **同 scope 适用**：对象使用其已绑定 scope 的合同；对象／Track 没有第二套安全 scope。
- **放置约束**：容器只允许或拒绝 placement，不自动改绑对象、开启 MLS 或授予权限。

未登记的继承关系 MUST NOT 从 ID、名称、目录树、ownership、管理员身份或可读父对象推导。
required authority unknown / stale / fork / 不完整时 MUST 按对应合同失败关闭；缺数据不是默认值证明。

## 1. 对象边界矩阵

| 对象 | 内容、历史与密钥边界 | 与其它对象的关系 |
| --- | --- | --- |
| Realm | Realm-default scope 有自己的 stream、history policy 与可选 MLS group；Realm 治理域另承担 authority / federation / capability 上下文 | Realm link 不是包含树，不传播成员、policy、retention 或密钥；见 [realm-links §6](../models/realm-links.md#6-link-不传播状态normative) |
| Circle | 自己的 stream、显式成员子集、history policy、投递裁剪与可选独立 MLS group | 不嵌套 Circle；受父 Realm current membership 与 lifecycle 约束；见 [Circle](../models/circle.md) |
| Sidecar | 自己的 stream 与固定独立 MLS 保护；参与者由 exact Realm / controller / Agent 权威事实派生 | 没有可编辑成员列表、join rule、directory visibility 或 history visibility 字段；不是 Circle；见 [Sidecar §2 / §5 / §6](../models/sidecar.md) |
| Space | 没有自己的 membership、MLS group 或历史策略；自身 metadata 与结构事实落在明确 Realm-default / Circle scope | parent/child 只表达导航；`child_scope_policy` 只控制放置；见 [space-hierarchy §2](../models/space-hierarchy.md) 与 [Circle §7.1](../models/circle.md#71-space-child-scope-policy) |
| Strand | 整个 Strand 绑定一个 Realm-default / Circle scope；所有 Track 共用其成员、history 与 MLS 边界 | 动作、字段与 Track 授权可收窄；Track 不产生独立安全边界；见 [Strand §4 / §5](../models/strand-and-message.md) |

Sidecar 的 source-context attach 只定位私有 view，不使 source Strand、所在 Circle、Space 或其成员获得
Sidecar 内容访问权，也不把 source 的 policy、MLS 或 history 复制给 Sidecar。实际发布仍按
[Sidecar §8](../models/sidecar.md#8-private-view-与显式发布)创建经过独立授权的新普通 Event。

## 2. 设置继承与约束矩阵

表中“同 scope”只指对象使用自己的实际 scope，不表达沿 Space 树或跨 Realm 传播。

| 设置 | Realm-default → Circle | Realm 治理域 → Sidecar | Space / Strand | 权威依据 |
| --- | --- | --- | --- | --- |
| MLS 激活、group、epoch、secret | 独立激活；无继承、派生或 fallback | 固定独立 MLS；未 ready 不提供明文业务降级 | 同 scope；Space 可通过放置约束要求目标已 MLS-backed | [加密 §2.3](../crypto-media/encryption-and-audit.md#23-应用载荷加密)、[Sidecar §6](../models/sidecar.md#6-原生-mls-绑定) |
| `history_access` | 独立配置及单向收紧；父 Realm history 不参与 cap | 无可配置的同名 history visibility；遵守 Sidecar 当前读取资格及 MLS 历史规则，不能套父 Realm 值 | 同 scope；没有 Space / Track 独立 history policy | [Circle §6.1 / §10](../models/circle.md)、[历史 §4](./history-visibility.md#4-mls-历史) |
| 已读披露策略 | 独立配置；禁止继承或取更严 | 不在现行已读策略合同内 | Strand 按消息 exact scope；Track 不单设策略 | [已读 §2.5](../discovery/read-receipts.md#25-scope-披露策略-disclosure-policy) |
| 成员／参与者 | 父 Realm current join 实例是 Circle 有效成员资格的必要条件；仍需显式 Circle join | controller 为该 Realm active member；Agent roster 从 ownership / lifecycle / runtime-key 与 exact Realm membership 派生 | 容器层级不授予成员资格；对象按 scope 验证 | [Circle §9.1](../models/circle.md)、[Sidecar §5](../models/sidecar.md#5-参与者与有效访问) |
| join rule、目录可见性 | Circle 自己配置；public Circle 只允许父 Realm 成员自助加入 | 没有这两个设置；第三方不得通过普通列表枚举 Sidecar | 不因 parent、contains 或可见容器扩大对象可见性 | [Circle §9.1 / §9.3](../models/circle.md)、[Sidecar §9](../models/sidecar.md#9-ensure-与读取) |
| Agent `interaction_mode` | 继承同一 Agent 在 Realm 的模式，Circle 不可覆盖 | 不改变 Sidecar 私有边界或派生 roster；public Agent 仍可参与其主人的私有 Sidecar | Strand 继承 Realm 模式，不能局部覆盖 | [Agent 交互 §1 / §2](../models/agent-interaction.md) |
| `agent_participation` | 上限求交；省略本层 component 时继承已验证父 ceiling，显式值只能逐位收紧 | 不形成 Sidecar 第二套成员或 MLS roster；动作仍验证其适用 action / policy | Strand 可继续收紧；Space 不构成 participation 继承层 | [公共字段 §4.4](../models/common-fields.md#44-agent_participation-wire-形态normative)、[Sidecar §5](../models/sidecar.md#5-参与者与有效访问) |
| Agent / Applet 管理 Policy | 多个适用 Policy 与实际 Realm / Circle / Strand 层按规定求交，下层 allow 不覆盖上层 deny | 验证该操作适用的 read / deliver / execute 等管理门；不因此授予 Sidecar 读取 | 只按已登记实际目标匹配，不沿 Space 树自动传播 | [管理治理 §1 / §2](../authz/managed-governance.md)、[自有 Agent 来源](../authz/owned-agent-authority.md) |
| capability、管理员／审核权 | 使用同 Realm 授权体系，但 grant 必须覆盖目标 Circle；Realm 管理身份不附赠私有读取或历史密钥 | Circle capability / proof 不能授权 Sidecar；实际操作使用专用权限与有效参与者门 | selector 不遍历 Space 子树；Track / 字段限制仍单独检查 | [selector §6](../authz/resource-selector-grammar.md#6-匹配算法)、[审核 §2.1](./content-moderation.md#21-审核权由-realm--circle-管理员行使)、[Sidecar §3.2](../models/sidecar.md#32-后续-event-scope) |
| archive / freeze / terminal | 父 Realm gate 约束 Circle；不合成 Circle lifecycle 写入；Circle 关闭不反向关闭 Realm | controller / Realm / policy / key readiness 派生 suspended 或 terminal；无自著 archive / restore / member Event | Realm gate 仍生效；Space 导航关系不等于子对象 lifecycle 级联 | [Circle §9.2](../models/circle.md#92-lifecycle-cascade)、[Sidecar §7](../models/sidecar.md#7-生命周期)、[Space](../models/space-hierarchy.md) |
| governance Station / federation | 由所属 Realm 治理域统一承担；Circle 无独立 federation identity，stream 仍独立 | 同一 current governor，独立 stream 与披露资格 | 无独立 federation；跨 Realm View / link 逐目标授权 | [Realm 字段](../models/realm-and-space.md#23-schema-id-与字段)、[federation](../sync/federation.md) |
| retention / legal hold | 对准确对象、stream、Blob 与实际保留副本求值，不从 Realm-default history / MLS 推导；未定义局部覆盖优先序 | 保留不扩大私有读取、参与者或密钥范围；未登记自动向所有 Sidecar 扩散的 hold | 不沿 Space 导航树推导；Strand 与派生内容按实际来源关联判定 | 本文 §4 |
| 明文可见服务 | Realm 名单是必要治理声明，不能代替目标 Circle 授权或解密材料取得合同 | 名单不能把 Sidecar 开放给 Realm 管理员／共享服务；只走已有获授权私有路径 | 按实际内容 scope 及具体服务合同检查；parent 不授权 | 本文 §5 |

个人已读偏好另按 `Strand → Realm → default` 顺序解析。这是 holder-private preference fallback，
不是上表已读治理策略的继承；发送仍受目标 exact scope 的 `required` / `disabled` 约束，见
[client-preferences §3.8](../discovery/client-preferences.md)。

## 3. 加密组合与放置

在没有额外适用部署／专用策略限制时，核心合同允许以下四种组合：

| Realm-default | Circle | 激活与发送判断 |
| --- | --- | --- |
| plaintext | plaintext | 各自未接受 Genesis，仍分别执行成员、history 与投递门 |
| plaintext | MLS | 只激活该 Circle；不能用其 group 发送 Realm-default 内容 |
| MLS | plaintext | 父 Realm 不隐式激活 Circle；不得把整个治理域展示为全部内容均已 E2EE |
| MLS | MLS | 两套独立 Genesis / group / epoch / secret；不能互相 fallback |

加密激活后不得 disable、替换 group 或退回明文；未取得目标 scope 的所需密钥不是改用父 scope
或明文的理由。上述应用内容规则不把公开治理控制材料改为密文，具体 Event payload class 仍按 registry。
`security_class` 标签本身不是另一套 Genesis 或密钥来源；已登记部署 profile 的额外限制仍须执行。

Space 的 `require_e2ee` 检查子资源实际 scope 是否 MLS-backed；`require_same_scope` 与
`require_scope_circle_id` 检查明确目标。Reducer MUST NOT 为通过 placement 自动改绑 scope、
开启 MLS 或复制父密钥。现行 v1 没有通用“父 Realm 加密 floor → Circle 取更严”的合同。

## 4. Retention 与 legal hold 的跨 scope 适用边界

### 4.1 保留、披露与解密分别判断

对任何保留或删除判定，执行者 MUST 区分实际数据对象及其 scope、持有副本的 Station / service、
适用策略与合法来源。保留某个 Event、密文 Blob 或审计原件，不授予其读取、复制披露、索引、
跨 scope 发布或解密权；管理员、hold 请求者、存储服务和治理 Station 均不能因此获得 MLS secrets。

Realm-default、Circle、Sidecar 的 stream 独立。现有 [历史 §3.2](./history-visibility.md#32-retention-不裁剪-commit-链normative)
的 Commit 链保留规则适用于这些 stream：retention 不删除 accepted RealmCommit，不产生或移动
readable floor；到期 Event 仍占同一 Commit 槽位，以 withheld 表达不可披露。authority bundle 必需
genesis / handoff 原件继续保留。Snapshot 中的 `retention_and_history_floor` 仍只表达 history / join floor。

Circle 自有 `history_access`、Sidecar 私有参与者门及 MLS key availability 不因 retention 变长、
暂停删除或进入 hold 而放宽。hold 中保留的副本也不得通过普通 scan / search / snapshot 暴露给无权主体。

### 4.2 Blob、派生副本与删除

[Blob §5 / §8](../crypto-media/media-and-blob.md)以 Blob owning Realm、引用授权、来源 scope、
retention、live references 与 legal hold 共同判断访问／GC。Blob 的 `realm_id` 不代替引用它的
Circle / Sidecar 内容读取资格；Space reparent、Strand move 或 source-context attach 不构成删除授权或 hold 解除。

已生效且覆盖该对象的 legal hold 阻止物理删除；普通视图仍可 redaction / withheld。Blob bearer
presign 的 hold 检查、强一致回查及拒绝继续按 Blob 专章；不能把“保留”解释为持 bearer URL 可读。
缩略图、preview、转码、搜索文本、embedding 与通知摘要仍须随真实源的撤回／擦除重新裁剪、删除或最小化；
已有 hold 覆盖的保留材料不得因该普通披露失效被物理删除，也不得反向恢复普通访问。

现有 moderation queue 的 `retention_expires_at` / `legal_hold` 是本 Station 保留元数据，
不是 canonical moderation decision，不能改写其它 Station 的决定或授权，见 [审核 §3.3](./content-moderation.md)。
Realm terminal、GC 与 erasure receipt 仍按 [Realm §2.6](../models/realm-and-space.md)区分；
terminal 不自动擦除，hold 可以阻止适用的物理删除，receipt 必须如实记录结果。

### 4.3 尚未闭合的策略选择

现行 Policy 的 `policy_kind=retention` 分类、Realm 的 `retention_policy_id` 投影、Blob hold 状态与
本地 queue 保留元数据，不足以定义统一的跨 scope 保留控制协议。v1 未闭合下列一般机制：

- Realm 治理域全体内容与 Realm-default 的 retention selector 如何区分；Circle / Sidecar 局部策略由谁写入、如何读取及如何组合。
- 多策略之间最短保留期、最低保留期、强制最长保留期与 hold 的冲突规则；不能不区分义务就一律取最短或最长。
- hold 的唯一签名作者、准确目标集合／来源闭包、设立与解除载体，以及跨 Station 下发、确认、撤销和失败恢复。

上述缺口不影响已登记 hold 对已确认目标的禁止删除义务，但 MUST NOT 由部署私有字段、
Space 子树遍历、裸 Realm ID 或未认证配置伪造新的 Arkret current、跨 scope 扩权或成功 receipt。
需要新通用控制流程时，必须先完成正式裁决与 carrier / schema / registry / SDK / 验收闭合。

## 5. 明文服务的跨 scope 适用边界

唯一 Realm 名单作者为 `ak.realm.plaintext_visible_services`，current 为
`realm_plaintext_visible_services`；它完整替换声明集合。每项按现有 payload 声明 service identity、
`service_kind`、`purposes`、`data_classes`、`visibility` 与可选期限。名单不另造 Circle / Sidecar policy，
`purposes` 自由文本与 ServiceDescribe 自报能力都不能替代 `data_classes` 或实际授权。

跨 scope 使用同一服务时，必须同时成立：

1. 该内容所属 Realm 当前声明允许该服务接收对应 data class，并满足该服务专章的额外条件。
2. 内容提供者在实际交付时有权读取／处理目标 exact scope 的相应内容；scope membership、history、
   lifecycle、capability / policy 及所需 MLS readiness 继续独立验证。
3. 存在该具体功能已登记的明文或受限 key 交付路径。MLS 业务明文由获授权客户端显式选取／提供；
   治理 Station 不能因为服务被列入名单就解密、发布历史 epoch secrets 或赋予持续解密能力。
4. 输出、索引、缓存、派生摘要与通知继续遵守原目标的披露和撤权边界，不能扩大到父 Realm、兄弟 Circle、
   其它 controller 或其它 Sidecar；选取已有内容不自动授权后续新内容。

名单只放行对应的服务治理门，不授予服务 Realm/Circle membership，也不替代 Sidecar 的有效参与者与
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

现行 service entry 没有闭合的 exact Circle / Sidecar scope consent / selector 合同；Realm-wide 声明
如何与“仅某 Circle 同意”“某 Sidecar 额外禁止”组合，以及服务获得持续输入时的受限授权、撤销／删除
证据，是待裁决项。现有专用功能仍按上表合同工作，不因该缺口自动获得通用后台明文访问。
