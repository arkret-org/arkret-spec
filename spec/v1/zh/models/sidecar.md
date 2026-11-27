---
title: Agent Sidecar
status: candidate
normative: true
stability: v1
updated: 2026-11-27
---

## 0. 规范语言

本文中的 **MUST** / **SHOULD** / **MAY** 按
[`conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 对象边界

个人 Sidecar 是一个用户与其自有 Agent 共用的私有 MLS 事件流。每个完整的 `(controller_account_id, source_realm_id)` 只保留一个对象。来源项目和其中的 Strand／Relation 只定位客户端里的讨论位置。用户归属 Station H 是创建、排序、签收、MLS 接纳、队列投递、备份与恢复的唯一权威。

Sidecar 的 `realm_id` 使用 H 已接纳的主人 Human PCR 标识，作为固定治理坐标。首次 create 是主人在自己的 PCR 中签署的一条私有控制记录。后续私聊原件全部使用独立 Sidecar stream 与 MLS group。Agent 读取该流只取得获准的 Sidecar 原件；这个授权不开放 PCR 的控制流、账户私钥或 Account Data。源项目的 `source_realm_id` 永远不能替代治理坐标。G 离线、项目撤权、项目终止和治理交接都不改变 H 对这条流的接纳权。

旧实现已经由 G 签署的引用仍绑定原站、原流和原始签名。H 不得改写其签署方、把旧快照当作新私聊的起点，或为了创建个人 Sidecar 向 G 查询及导入旧记录。用户在 H 新建的私聊从自己的已接纳 create 和首次关联开始。

项目资料和项目动作按其实际来源授权。客户端或工具打开原文、附件、查询或调用项目工具时，须按实际执行者、动作和资源取得 G 当前授权。自动把原文、摘要或工具输出持久写入 Sidecar，还须有来源允许复制并持久保留给全部实际 MLS 接收端的依据；缺少此依据时仅保留可重新鉴权的引用。私聊正文与定位符不得作为项目读取凭证发送给 G。Circle 保持原跨界限制。H 与 G 即使为同一逻辑 Station，也分别执行这两套检查。

用户从 Contacts/Direct Messages 产品面点击自己的 Agent 时，客户端 MUST 使用
[`ak.self.direct_conversation.read.resolve.v1`](../identity/contact-and-direct-conversation.md#91-resolver-状态)
定位 `{controller, agent}` 的独立双成员 Direct Conversation Realm；尚不存在时由 controller 按
[contact-and-direct-conversation.md §5.4](../identity/contact-and-direct-conversation.md#54-create-判别与授权)
的 `direct_conversation_agent_genesis` 分支创建。resolve 只是查询入口，MUST NOT 承载 create phase。
该入口不得调用 Sidecar ensure，也不得要求当前 Realm/Strand context；Sidecar 只用于既有 Realm/Strand
内的 context-routed 私有协作。

Sidecar 与 Circle 功能正交：

| 维度 | Circle | Sidecar |
| --- | --- | --- |
| 目的 | Realm 内显式沟通圈与安全边界 | controller 与其明确启用的自有 Agents 的个人协作上下文 |
| 参与者 | 显式可治理成员子集 | 由 H 核实逐 Sidecar 的主人启用世代和当前原生资格 |
| scope | `scope_ref.kind="circle"` | `scope_ref.kind="sidecar"` |
| 跨边界映射 | 不允许自动映射到圈外 Strand | 可在普通 Strand shell 中显示 private view；durable publish 必须创建新 Event |
| MLS | Circle membership 驱动 | ownership、lifecycle、runtime-key authorization 与该 Sidecar 的当前启用世代 派生目标 roster；MLS/key readiness 只决定 effective 收敛状态 |

协议中不存在 Sidecar backing Circle。实现 MUST NOT 为 Sidecar 创建、隐藏、保留或模拟 Circle 对象、
Circle membership、Circle role/admin、Circle join rule、Circle invite 或 `SC-` 保留名称。

每个 `(source_realm_id, controller_account_id)` 在 H 至多存在一个 Sidecar。

## 2. Sidecar 对象与身份

Schema id：`ak.schema.agent_sidecar.v1`。

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `id` | yes | `id:sidecar` | Event-derived 44 字符 token；`retype(create_event.event_id,"sidecar")` |
| `schema` | yes | const | `ak.schema.agent_sidecar.v1` |
| `realm_id` | yes | `id:realm` | 主人的 Human PCR 治理坐标，从 create Event scope 派生，create-locked |
| `source_realm_id` | yes | `id:realm` | 主人原签 create payload 的来源项目，create-locked |
| `controller_account_id` | yes | `AccountId` | create actor 的完整 AccountId，create-locked |
| `state` | yes | enum | `active \| suspended \| tombstoned`，reducer-derived |
| `state_changed_at` | conditional | timestamp | 非 active 时必填 |
| `created_at` | yes | timestamp | 等于 accepted create Event `created_at` |
| `updated_at` | no | timestamp | reducer-derived |

`backing_circle_id`、成员列表、管理员、title、summary、directory visibility、join rule 与 history visibility
均不是 Sidecar 字段。

`ak.schema.agent_sidecar.v1` 的 schema identity 固定独立 MLS/RFC 9420 保护。Sidecar 的加密激活点是它
自己的 accepted `ak.mls.genesis`，因此 `ak.sidecar.create` payload 与物化 Sidecar 对象都不携带加密
profile 字段。

## 3. 创建与原生 scope

### 3.1 `ak.sidecar.create`

`ak.sidecar.create` 是 Sidecar 唯一 genesis Event：

```text
sidecar_id = retype_event_token(event.event_id, "sidecar")
realm_id = event.scope_ref.realm_id
controller_account_id = event.actor_id.account_id
created_at = event.created_at
```

create Event 使用主人的 Human PCR scope，payload 只携来源项目标识：

```json fragment
{
  "scope_ref": {"kind":"realm", "realm_id":"ak:realm:..."},
  "payload": {"source_realm_id":"ak:realm:..."}
}
```
payload MUST NOT 携带 `sidecar_id`、完整 Sidecar object、`controller_account_id`、成员、Circle ID、Strand ID、
Relation ID、state 或 timestamp。H 验证原签主人设备、其已接纳的 Human PCR 和完整账号，再从原 Event ID 重算 Sidecar ID。H 在同一事务中检查 singleton、保存 create 与首个 attach 两份原件并签收。相同原件重试恢复原回执，竞争失败或任一原件非法均零写入。源项目和项目复制队列不接收任何一个原件。

### 3.2 后续 Event scope

Sidecar create accepted 后，全部 Sidecar-private Event 必须使用：

```json fragment
{
  "kind": "sidecar",
  "realm_id": "ak:realm:...",
  "sidecar_id": "ak:sidecar:..."
}
```
Receiver MUST 验证 Sidecar 存在、Realm 一致、actor 属于当前有效访问集合，并将完整 `scope_ref`
纳入 Event digest、AAD、query/delivery 裁剪与 RealmCommit coverage。普通 Circle API、Circle capability 与 Circle
membership proof 不能授权 Sidecar Event。

## 4. Context attach：映射，不创建对象

`ak.sidecar.context.attach` 把主人本机已知的来源项目普通 Strand 或 Relation 记录为 Sidecar 的 source/UI context。
它只写 `sidecar_context`，不创建 private Strand、Relation 或任何其它协议对象。

payload 是：

```json fragment
{
  "sidecar_id": "ak:sidecar:...",
  "source_context_ref": {"kind":"strand", "strand_id":"ak:strand:..."},
  "version": 1
}
```
Relation context 使用 `{kind:"relation",relation_id}`。同一 `(sidecar_id, source_context_ref)` 的首次 attach
使用 `version=1` 且不带 predecessor；后续版本必须逐次递增并引用 current head。

H 使用已合法取得的普通位置引用；首次打开、切换或恢复私聊不得触发项目查询、订阅、预取、回执或补发。引用不能证明对来源正文的读取权。context attach 只控制 private view 放置位置。它不得：

- 把 Sidecar Event 写入普通 Strand timeline；
- 改变普通 Strand 的计数、未读、搜索、通知或 history；
- 让普通 Strand 成员获得 Sidecar 访问权；
- 创建 `agent_sidecar_of` Relation；
- 复用 source Strand Event ID 作为 private Event ID。

## 5. 参与者与有效访问

初始启用集合为空。主人用自己的当前设备，在精确 Sidecar scope 对同 H、自有且当前有效的 Agent 签署 `ak.sidecar.member.state`。本用途只允许 `agent_account_id` 为该 Agent 的完整 AccountId，`membership` 为 `join` 或 `leave`，第一次 join 省略 predecessor_event_ref，之后的 leave／join 必须引用同一 Sidecar、同一 Agent 的上一条原签。新请求重复当前状态或前驱不匹配时拒绝；完全相同的已接纳原件重试返回原 Commit。H 核对原签、ownership/provision、当前状态和该 scope 的成员转换并保存原件。只有主人可以改变此选择。该写入只作为对应 Sidecar 私有资格的持久依据，绝不写入或授予 Human PCR 或来源项目的 membership。新 Agent、项目入群或一次 mention 均不能触发启用。

`desired_agent_ids` 是该 Sidecar 中当前主人启用的 Agent 与当前有效的自有 Agent 的交集。每次重新启用使用新的 join Event ID。`effective_agent_ids` 还须满足该端点当前 key、同一启用世代的已接纳 MLS Add、精确 Welcome／claim 和 durable consume。空集合允许主人独立使用。Agent 所有权、端点或资格失效时 H 立即停止新交付并安排 MLS Remove／换钥，仍含已撤销叶的 epoch 不得发送新的私聊业务内容。撤权前已交付的材料遵守原有加密边界。

## 6. 原生 MLS 绑定

Sidecar 拥有独立 MLS group，但该 group 直接绑定 `sidecar_id`，不绑定 Circle ID 或 membership current state。
不存在 controller-global Sidecar MLS group：不同 `sidecar_id` 的 Add/Remove/Update、Welcome、epoch、future
epoch key 与 reconciliation 状态彼此隔离，任何一项都不得跨 Sidecar 复用或传播。

**独立受限握手合同（normative）**：Sidecar Proposal／Commit 的 wire 输入 MUST 是完整 RFC 9420
`PublicMessage` 形态 `MLSMessage`，复用既有 `ak.mls.commit` 与 `MlsCommitSubmission`；v1 Proposal 仅内联于
Commit，不新增独立 Proposal Event。治理 Station MUST 从本 Sidecar 的 accepted base public tree 对原始 bytes
验证实际 Commit 签名、Member sender 的完整 ActorId、全部 inline Proposal、post-Commit tree 与 GroupContext；
sender MUST 等于 signed Event 的 `actor_id`。`PrivateMessage`、裸 Proposal／Commit、替代摘要或 producer
提供的 post-state 断言均 MUST 以 `schema_violation` 零写入拒绝；Proposal reference 仍按
[`../crypto-media/encryption-and-audit.md` §2.2.2](../crypto-media/encryption-and-audit.md) 以 `unsupported_feature` 零写入。
Station MUST 在原接纳事务冻结 consumed Proposal 的原 wire ordinal、精确 TLS body、已验 sender 与 leaf target
provenance；Remove+Add 即使 leaf 元组相同仍是新 provenance，不能由最终 tree、desired roster 或 Welcome 补造。

`PublicMessage` 只描述 RFC wire 形态，**不授予公开或父 Realm 成员读取权**。握手 bytes、public tree 与历史
provenance MUST 继续经过本 Sidecar 既有当前及目标 accepted cut 的披露门；普通 Realm 成员、其它 Sidecar
参与者与无本 Sidecar 授权的 Agent 不得读取。准入仍以本节 Sidecar controller／desired authority 和已签 binding
为准，不继承 Realm／Circle committer 权限。治理 Station MUST NOT 取得 `membership_key` 或其它成员 secret，
也不得把 membership MAC 当作它的准入证据；成员 MUST 在本地验证 MAC。应用 payload 与 Welcome 保持原有
加密保护，不新增 Principal／Account／Device／Realm 外 locator 披露。不适用 Realm／Circle 的 creator-bootstrap
transaction；独立 group、stream、epoch 和下面的参与者签名绑定不变。

`participant_authority_digest` 必须覆盖：

```json fragment
{
  "domain": "ak.sidecar.participant_authority.v1",
  "sidecar_id": "ak:sidecar:...",
  "realm_id": "ak:realm:...",
  "controller_account_id": {
    "principal_id": "ak:did_core:webvh:zExampleControllerScid",
    "station_id": "ak:did_core:webvh:zExampleStationScid"
  },
  "desired_agents": [
    {
      "agent_id": "ak:did_core:webvh:zExampleDesiredAgentScid",
      "join_event_ref": "ak:event:..."
    }
  ]
}
```
摘要为 `sha256(JCS(preimage))`，唯一 closed 原像见
[`agent-operations.schema.json#/$defs/sidecar_participant_authority_preimage`](../../artifacts/schemas/agent-operations.schema.json#/$defs/sidecar_participant_authority_preimage)。
原像的 `realm_id` 为主人 Human PCR，`join_event_ref` 精确引用主人为该 Agent 签署并由 H 接纳的本 Sidecar 当前启用原件。按 agent_id UTF-8 字节排序，重复 Agent 拒绝。H 在接纳切点重核本人、有效 Agent、端点、签名、原 claim 与 RFC 成员转换。只有实际启用且有效的端点可以成为 Add 目标。不同 Sidecar、旧启用世代或旧 claim 不得互用。

主人可在签署本 Sidecar 的 `join` 时显式设置 `private_reply_allowed: true`。省略即只读；`leave` 不得携带该字段。只有当前获此授权的 Agent 本人可用已完成 consume 的实际端点在这条 Sidecar 中发加密回复。授权由 H 在首次备份准备及消息接纳时按当前启用原件、端点、会话和动作重新检查，不能用于主人 PCR、其它 Sidecar 或来源项目。主人以当前原件为前驱重新签署 `join` 改变回复权限；旧世代随即失效。

### 6.1 私有握手、历史与排队投递（normative）

主人设备首次为自有 Agent 领取 KeyPackage 时，使用本地 self claim 的 `claim_purpose=realm_membership`。其 `intended_realm_id` 为主人的 Human PCR，`mls_group_id` 为该 Sidecar 的规范组 ID，来源和目标 Station 均为 H。H 以原签创建、当前启用、Agent 的归属及当前端点核验参与资格，并在分配 KeyPackage 的同一事务重核。项目入群记录不能代替私有启用。H 不得为该领取建立 peer 转发或重试。

首次 Welcome 由 H 依本地真实会话和当前启用世代投递。H 同时核对原 Add、其原签 Welcome、claim、接收端及当前授权密钥。领取和 consume 前允许端点尚未 effective。业务历史要求该端点已 effective。每次实际发送队列字节前重核当前会话、端点和资格；撤权后已经排队的内容也不得交付。

H 为各获准主体签发私有历史依据。主人的历史可在同 H 的已授权设备恢复；Agent 的读取下界绑定其本 Sidecar 当前启用世代与受理的 MLS 状态。重新启用后拒绝旧世代的快照、Welcome 与日志游标，拒绝时不得推进检查点。H 验证历史原件、连续 commit 链、签名、MLS 与授权范围，允许获授权新设备独立验证并耐久安装。准备或写入首次备份根也由 H 核本次写动作、完整 Sidecar 与精确 MLS epoch。私有握手、历史、备份、同步及恢复均不得使用来源项目的站际 bootstrap、scan、事件转发、推送或离线补发。

## 7. 生命周期

主人账号有效且本地私有资格满足时可继续使用；账号暂停或实际 key 不可用时暂停相应供给。主人账号不可逆终止时结束私有工作区。项目退群、项目暂停／终止和治理交接仅影响后续项目资源访问与发布。保留曾合法持有的私人历史和草稿，重新打开项目引用须按当时权限。不可逆终态的 singleton 继续保留。

## 8. Private view 与显式发布

`ak.agent.sidecar.exchange.control` 写 `agent_sidecar_exchange_controls` current state：subject 是
`(payload.sidecar_id, canonical_json(payload.source_context_ref))`，value 是以 canonical Event dot 标记的
完整 encrypted control carrier 集合。`exchange_id` 只存在于
`ak.schema.agent_sidecar_exchange_control.v1` 认证密文明文中，MUST NOT 为了寻址复制到外层 payload 或
result selector。Station 按既有外层准入检查 controller、scope、source context、producer proof 与加密 carrier 的封闭形状，
通过后只把原 encrypted carrier 作为 canonical Event dot 加入该 current 集合；它不解密，也不以私密明文状态作为 keyed-set add 的前置。
获授权参与者解密集合元素后，按 plaintext `exchange_id`、`basis_event_ids` 与 `action`
折叠 coordinator reassignment 和 terminal state；错误 controller／scope／context、无法认证的密文、
未覆盖 basis 或非法状态迁移都必须在应用客户端的已验证 exchange 投影之前拒绝，且不得留下部分投影。
该读侧折叠不回写 current 集合，也不回滚已经接纳的 Event／RealmCommit。

提供 Sidecar 上下文交互的客户端 MUST 在原 source Strand 的讨论中，向当前获授权的 controller
合并展示普通 Strand 消息及其 Sidecar 的已验证 request 与显式 user-facing response，并明确标记
private provenance。该寄宿展示方式固定为合并展示，不提供 Sidecar-only 显示模式或显示模式切换；
pin／折叠只调整局部呈现，不改变该默认阅读入口。读取自己的私密消息 MUST NOT 以 publish、共享
审批、切换私密视图或手动刷新为前提。没有私密消息时保留普通讨论及输入入口，不隐藏原 Strand。

这只是 controller 的本地私密投影，不改变普通 Strand canonical history、成员、授权或 MLS roster。
除该 Sidecar 当前获授权的 controller／Agent 外，其它用户 MUST NOT 接收或读取这些 Sidecar 消息，
包括同一 source Strand 的其它成员；共享历史、通知、未读与搜索 MUST NOT 因该投影产生私密内容或
Sidecar 存在差异。controller 本人看到请求／回复不创建普通 Event，也不构成显式发布。

v1 exchange profile 固定 source-track routed origin 与 coordinator completion policy；
`ak.schema.agent_sidecar_exchange_projection.v1` cache 不携 `origin` / `completion_policy`，request-role
`ak.schema.agent_sidecar_event_exchange_binding.v1` 也不回显 `completion_policy`。consumer 直接从各自
schema identity 注入这些值，不能把省略解释为可选择其它 origin 或 completion policy。

真正发布到普通 Strand 必须由 controller 对最终 allowlist payload 显式确认，并创建一条新的普通
Strand Event：

- 新 Event 有自己的 Event ID、签名、scope 与 authorization；
- 不复制 private Event envelope；
- 不泄漏 `sidecar_id`、private Event ID、MLS material、Agent scratchpad/tool output、exchange/control plaintext；
- 失败或重试不得产生部分 shared durable output。

Circle 内容不得使用本节映射或发布规则跨越 Circle 边界。

### 8.1 Composer 发送路由

以下是 v1 客户端发送合同；本地发送意图与 [Agent 交互模式](./agent-interaction.md) 的 Realm current 分离。
只有已绑定完整 AccountId 的 mention 才计入直接目标；普通 `@me/slug` 字符串不触发 Sidecar。
原 Strand 的固定合并历史只决定阅读呈现，不决定下一条消息的发送 scope。客户端 MUST 对每份草稿、
每次发送与重试重新读取当前有效 token 绑定及模式／权限：当前消息没有 Agent mention 时使用原
Strand；只有当前消息明确绑定主人的私人 Agent 时才选择 Sidecar；公开 Agent 使用原 Strand。
旧 Sidecar session、以前的 addressed targets、last verified request、已显示的私密回复和恢复出来的
历史 MUST NOT 补入当前草稿的目标或使无 Agent mention 的消息保持私密发送。提及已编辑／删除／解绑
时即从当前寻址集合移除，不以旧 picker、旧请求或同名文本恢复；固定合并显示也不新增隐式私密入口。
没有 Agent 目标的普通草稿不要求以前 Agent 的模式或 Sidecar readiness；旧私密上下文的模式 unknown、
MLS 未就绪或恢复失败不得成为该普通草稿的发送门，仍须通过原 Strand 的正常授权。

| 当前入口/目标 | 默认与可选路由 | 发送前边界 |
| --- | --- | --- |
| 联系人 controller/Agent Direct Conversation | 保持该独立双成员 Direct Conversation | 不调用 Sidecar ensure，不要求 Realm/Strand context。 |
| 普通 Realm Strand，无 Agent mention | 原普通 Strand | 即使此前发送过私密消息或已恢复 Sidecar 历史，仍使用原 Strand；普通人类与 audience mention 沿用普通授权，不凭字符串或历史转私有。 |
| 普通 Realm Strand，只提及他人 Agent | 原普通 Strand | 沿用现有模式／触发／第三方授权门；不能路由到他人的 Sidecar。 |
| 普通 Realm Strand，只含公开 Agent（可含其它共享目标） | 普通共享 Strand，包括主人提及自己的公开 Agent | 模式不授予回复／读取／第三方投递权限；仍求交现有各门。 |
| 普通 Realm Strand，只含主人的私人 Agent（可含主人自身） | 私有 Sidecar | 不提供将私人请求直接“发送到群”的绕过；显式成果 publish 另走 §8。 |
| 普通 Realm Strand，私人／公开 Agent 混合，或私人 Agent 与外部／audience 混合 | 阻止发送，保留草稿并要求修改当前目标 | 不自动拆分、丢弃目标、转群或改变模式；unknown 模式也阻止发送。第三方手工构造 private mention 只抑制 Agent 触发，不改变原共享消息 scope。 |
| Circle Strand | 公开目标保持普通 Circle；主人私人 Agent 交互阻止发送 | 不提供 Realm Sidecar 路由，不复制 Circle 内容；公开目标仍需 Circle 读取／participation／E2EE 门。 |

客户端 MUST 在发送前展示实际 scope 与可读取者边界；Circle／Direct 显示其固定 scope。公开／私人模式
由主人独立设置，不是当前草稿的“发送到群”按钮。原 Strand 的发送 scope 与可读取者提示 MUST 随当前
草稿的实际路由更新，不能因为仍显示 Sidecar 历史而沿用私密提示。mention 是请求寻址子集，不是
加密收件人全体，也不得修改 derived roster。Sidecar
pending／not-ready／失败 MUST 保留草稿并拒绝私有发送，MUST NOT 降级普通 Strand。草稿、目标、模式、
scope／账号变化 MUST 撤销先前 shared 确认，恢复与重试重查当前模式及权限。Private publish
仍须 §8 的最终 allowlist 确认和新 Event；reply／revise／附件／引用等不得迁移已有 Message scope。

已验证 controller 关系与完整 Agent AccountId 满足 [`strand-and-message.md` §9.4.1](./strand-and-message.md)
时，本地 `@me/slug` 标签不依赖成员列表是否呈现主人行；标签不替代结构化绑定。发送异步进行时 MUST
保留草稿与已绑定目标，只有同一账号／scope／草稿意图的请求得到 bound accepted outcome 后才能清除
该请求的输入；失败或迟到的结果不得清除后续编辑。重复点击 MUST NOT 创建重复 request 或重复 Agent
执行。发送成功仅表示请求已接纳，不表示 Agent 已生成回复或用户已经看到回复。

### 8.2 实时私密阅读与恢复

真实生产 account-stream consumer、逐流补拉与重启恢复 MUST 对 Sidecar 使用同一验证和安装边界，
不能只在离线测试或未接线 follower 中执行：冻结经认证的 exact account／Realm／governance generation
及 Sidecar stream head，验证该 cut 所需的连续 committed history、typed current、historical signer 与
exact MLS group state，然后在同一耐久事务安装相互一致的私密历史、current 及重建派生投影的验证 basis；checkpoint
只能在该事务耐久完成后推进。派生投影 MAY 为非耐久缓存，但只能从完整安装且仍获授权的 cut
重建并发布到 UI，不得展示事务中的候选中间态。任一验证失败或依赖缺失时 MUST NOT 安装部分 current／投影或宣称最新
历史完整，MUST NOT 用另一个 Realm／Sidecar／generation 的 head、较新的 current 或部分事件凑齐该 cut。
遵循 [`client-sync.md` §5](../sync/client-sync.md) 与 [`current-state.md` §3–§5](../sync/current-state.md)。

已接纳回复及其验证依赖可取得时，consumer MUST 自动补齐并重新验证，然后更新原讨论中的私密投影，
不等待下一条用户消息或手动刷新。断线、cursor 失效或客户端重启后 MUST 自动恢复同一已接纳历史与
回复，按 Event id 去重，不重发请求、不再次执行 Agent、不清除身份密钥、MLS 私有状态或待发送草稿。
来源 Strand current／watch 的独立读取失败不得取消获授权 Sidecar 的续传；任何重试仍服从现有授权、
分页、generation 和撤权门。服务不可用时不承诺回复产生或固定完成时限，但恢复不能依赖用户刷新。

Agent runtime 对已通过既有 Account 帧／逐流验证的 durable pending 条目 MUST 按 exact `stream_ref`
及相应 cursor 的 scope／filter 绑定保留各流顺序、处理状态和恢复位置。一条共享流因群内交互模式
unknown 或暂不可确认而等待，MUST NOT 阻塞另一条已获授权 Sidecar／主人 Direct 流的独立请求与回复；
这些私有请求仍执行自己的完整授权、历史与 MLS 验证，不以取得群内 public 模式为前提。等待条目
MUST NOT 被静默丢弃、标为已处理或 ACK，也不得借另一条流的成功越过自身未完成位置或推进其 cursor。
独立调度不建立跨流总序，不豁免 [`client-sync.md` §5.2](../sync/client-sync.md) 的整份 Account 帧验证
与聚合 cursor 安装边界，也不改变该文 §10 的 recipient delivery 累计 ACK 合同。

历史验证、解密、补拉和缓存持久化 MUST 有界调度，不得在每次渲染、滚动或输入时同步重放全部私密
历史。实现 MAY 使用经验证的增量检查点与缓存，但 MUST 绑定完整 account、exact scope、generation、
已验证 head、历史 signer 与 MLS state；缓存命中不得省略这些安全边界。新增事件或依赖变化必须触发
相应重新验证，撤权立即禁止展示不可再读内容。验证／恢复等待 MUST 保持页面滚动、输入及取消可操作；
Agent 当前作者化或未来 epoch 参与资格的撤销不等于 controller 当前历史读取资格被撤销；合法已读历史
与历史 MLS state 保留仍遵守既有 history/access 合同，不得用当前作者化状态追溯删除主人历史。
自动重试 MUST 遵循退避与资源预算，不得因重试形成阻塞循环。正常 Signal 流 drain／续订或
健康连接上的 reconnect hint MUST NOT 累积故障次数并扩张错误退避；实际失败与正常续订分别处理。
Signal 只辅助唤醒，不替代 committed reply 的验证与续传，缺失或延迟的 Signal 不得使已接纳回复只能
等待下一条用户消息或手动刷新。

在当前授权仍允许读取时，已验证的上一完整 cut MAY 保留为明确标注非最新的历史；等待验证的新回复
MUST NOT 被伪装为已验证或当前结果。恢复提示只影响未就绪的私密部分，不阻塞普通讨论。没有可验证
历史时显示可恢复空态与具体状态，不使用共享消息、默认明文或未经认证的缓存冒充私密回复。

诊断和验收 MUST 区分请求接纳、模型完成、回复接纳、客户端接收、客户端验证与用户可见这六个边界；
发送成功、模型完成或订阅连接存活均不能单独证明回复显示成功。诊断记录 MUST 遵循既有私密日志／遥测
隔离，不向共享面输出私密正文、Event／Sidecar 定位符、密钥或 exchange material。

## 9. Ensure 与读取

`ak.self.agent.sidecar.command.ensure.v1` 使用 prepare/commit：prepare 固定 new/existing 分支、Event ID、
canonical unsigned bytes 与 digest；new 分支返回 create + context attach drafts，existing 分支只返回 attach。
commit 只接受在 exact drafts 上追加的 controller proofs，并原子提交。reservation 不分配 Sidecar ID；
Sidecar ID由已固定 create Event ID确定。

读取只通过 `ak.self.agent.sidecar.resource.get.v1` 与 `ak.self.agent.sidecar.read.list.v1`。返回 Sidecar、
`desired_agent_ids` 只读派生投影、`effective_agent_ids`、MLS readiness、pending reconciliation 和 source
context mappings。
普通 Circle/Strand/Relation list 不得泄漏 Sidecar 存在、private Event、计数、未读、搜索或通知差异。

## 10. 验收不变量

1. G 在首次创建前离线。H 原子创建并关联缓存中的来源位置，主人显式启用一个自有 Agent，Agent 完成 Welcome／consume，收发私人原件。换用另一已授权设备后，验证并恢复同一原件及其上下文；G 恢复服务后也收不到相关积压请求。
2. 撤销 H 的 Agent 权限后，已排队的私人材料不得送达；重新启用不接受上一启用世代的快照。其他自有 Agent 与其他 Sidecar 的权限保持各自独立。
3. 两个独立站点对外站项目的真实业务记录验证合法读取、排队后项目撤权零交付、重新入群拒绝旧项目快照且历史和检查点不推进。项目变化不得封锁用户自己的草稿。
4. 来源材料的读取、自动复制给实际接收组以及用户确认的显式发布分别验权；私有原件、标识、签名、密文和计数均不进入项目复制、推送、搜索或治理交接。

Sidecar 加密 envelope 的摘要使用注册的密文原像并由 `ak.vector.encoding.encrypted_envelope_digest.v1` 检验。

### 10.1 必跑 conformance vectors

`ak.vector.sidecar.view_state_closed.v1` 为 active schema-only 向量，通过
`sidecar-view-state-schema-fixture.json` 验证无模式 view-state shape 与旧模式字段拒绝；它不证明真实
MLS、主人合并显示、实时恢复或 UI 响应性。这些生产验收见
[`conformance-vectors.md` §3.16](../conformance/conformance-vectors.md)。

下列向量在 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 中当前均为 `reserved`：
尚无机器 fixture 承载，激活前不构成认证证据。每个向量在补齐 fixture 并回到 `active` 的同一变更中成为必跑项。

- `ak.vector.sidecar.mls_bootstrap_binding.v1`
- `ak.vector.sidecar.mls_effective_access.v1`
- `ak.vector.sidecar.ensure_idempotent.v1`
- `ak.vector.sidecar.eligibility_states.v1`
- `ak.vector.sidecar.existence_privacy.v1`
- `ak.vector.sidecar.hosted_projection.v1`
- `ak.vector.sidecar.multi_agent_publish.v1`
- `ak.vector.sidecar.exchange_binding_closed_loop.v1`
- `ak.vector.sidecar.exchange_projection_recovery.v1`
- `ak.vector.sidecar.exchange_binding_containment.v1`
- `ak.vector.sidecar.context_locator_recovery.v1`
- `ak.vector.sidecar.canonical_sibling_digest.v1`
- `ak.vector.sidecar.union_history_checkpoint.v1`
- `ak.vector.sidecar.non_disclosure_surface_matrix.v1`
- `ak.vector.sidecar.revoke_fail_closed.v1`
- `ak.vector.sidecar.explicit_publish.v1`
- `ak.vector.sidecar.accepted_request_identity.v1`

## 11. 规范性引用

- Event/ID 派生：[`common-fields.md`](./common-fields.md)、[`event-and-patch.md`](./event-and-patch.md)
- Agent ownership/lifecycle：[`actor.md`](./actor.md)、[`../identity/key-management.md`](../identity/key-management.md)
- MLS：[`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)
- Circle 边界：[`circle.md`](./circle.md)
