---
title: Agent Sidecar
status: candidate
normative: true
stability: v1
updated: 2026-10-05
---

## 0. 规范语言

本文中的 **MUST** / **SHOULD** / **MAY** 按
[`conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 对象边界

Agent Sidecar（`ak:sidecar:`）是绑定到一个 `(realm_id, controller_account_id)` 的个人 AI 私有工作区。
它是一等协议对象和原生安全 scope，不是 Circle、Circle profile、Direct Conversation、Strand Track，
也不是某个 Agent 的 1:1 会话。

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
| 目的 | Realm 内显式沟通圈与安全边界 | controller 与其当前 Realm 内 active owned Agents 的个人协作上下文 |
| 参与者 | 显式可治理成员子集 | 由 ownership/lifecycle 与 exact Realm member_state revisions 派生，不可编辑 |
| scope | `scope_ref.kind="circle"` | `scope_ref.kind="sidecar"` |
| 跨边界映射 | 不允许自动映射到圈外 Strand | 可在普通 Strand shell 中显示 private view；durable publish 必须创建新 Event |
| MLS | Circle membership 驱动 | ownership、lifecycle、runtime-key authorization 与 exact Realm membership 派生目标 roster；MLS/key readiness 只决定 effective 收敛状态 |

协议中不存在 Sidecar backing Circle。实现 MUST NOT 为 Sidecar 创建、隐藏、保留或模拟 Circle 对象、
Circle membership、Circle role/admin、Circle join rule、Circle invite 或 `SC-` 保留名称。

每个 `(realm_id, controller_account_id)` MUST 至多存在一个 non-tombstoned Sidecar。

## 2. Sidecar 对象与身份

Schema id：`ak.schema.agent_sidecar.v1`。

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `id` | yes | `id:sidecar` | Event-derived 44 字符 token；`retype(create_event.event_id,"sidecar")` |
| `schema` | yes | const | `ak.schema.agent_sidecar.v1` |
| `realm_id` | yes | `id:realm` | 从 create Event scope 派生，create-locked |
| `controller_account_id` | yes | `did_core_id` | 等于 create Event `actor_id`，create-locked |
| `state` | yes | enum | `active | suspended | tombstoned`，reducer-derived |
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

create Event 使用 parent Realm scope，因为 Sidecar 尚未存在：

```json fragment
{
  "scope_ref": {"kind":"realm", "realm_id":"ak:realm:..."},
  "payload": {}
}
```
payload MUST NOT 携带 `sidecar_id`、完整 Sidecar object、`controller_account_id`、成员、Circle ID、Strand ID、
Relation ID、state 或 timestamp。Receiver MUST 重算 Sidecar ID；payload 携带这些字段必须在 schema 层拒绝。

`sidecar_create` 以派生 `sidecar_id` 为 subject，保存已接受 genesis intent。
Reducer 另以 `(realm_id, controller_account_id)` 执行原子 singleton reservation；相同 key 的 exact replay 幂等，
不同 create Event 必须 fail closed，不得 LWW、merge 或创建第二个 Sidecar。

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

`ak.sidecar.context.attach` 把一个已经存在的普通 Strand 或 Relation 记录为 Sidecar 的 source/UI context。
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

context attach 只控制 private view 放置位置。它不得：

- 把 Sidecar Event 写入普通 Strand timeline；
- 改变普通 Strand 的计数、未读、搜索、通知或 history；
- 让普通 Strand 成员获得 Sidecar 访问权；
- 创建 `agent_sidecar_of` Relation；
- 复用 source Strand Event ID 作为 private Event ID。

## 5. 参与者与有效访问

Sidecar 没有独立的 membership 管理面。其 MLS 目标参与者是 Sidecar stream 当前 committed head 上的纯派生集合：

```text
desired_agent_ids(S, F) =
  active_authorized_owned_agents(S.controller_account_id, F)
  ∩ active_realm_member_ids(S.realm_id, F)
```

其中 `F` 是读取或 admission 使用的 accepted authority-committed current results。`active_authorized_owned_agents` 来自 canonical
Agent ownership/provisioning、lifecycle 与 Agent runtime-key authorization truth；它不包含 target action grant、
participation selection 或 MLS readiness。`active_realm_member_ids` 来自 `S.realm_id` 自己的 Realm membership
truth。完整 MLS 目标 roster 是 `S.controller_account_id` 加上这个 Agent 集合；无需再维护第二个 participant 字段或
派生函数。controller 自身也必须是该 Realm 的 active member，否则 Sidecar 进入 suspended/readiness blocked，
不得继续分发新 epoch 内容。caller、controller、Realm admin、Agent 或 service 均不得在 Sidecar 内设置、
替换、追加、邀请、移除或转让 participant。

不得用 profile extension 或任何未注册 Event kind 恢复同义成员列表；receiver MUST 将未注册
kind 按 unknown Event kind 处理。

专用读取面公开两个只读集合：

- `desired_agent_ids`：同名派生函数 `desired_agent_ids(S, F)` 的只读 wire 投影；它不是 caller-authored、
  reducer-stored 或需要随 membership 变更同步改写的字段；
- `effective_agent_ids`：`desired_agent_ids` 中已经成为当前 accepted Sidecar MLS epoch 成员、并完成目标设备
  Welcome/KeyPackage consume 与 key readiness 的 Agent。

建立 canonical Agent ownership 本身 **MUST NOT** 使 Agent 出现在任何 Sidecar 的 `desired_agent_ids`，也不得
触发 MLS Add、寻址、投递、capability 签发、Realm membership 或 participation selection。只有该 Agent 同时是
exact `S.realm_id` 的 active member 时，它才进入该 Sidecar 的 desired 集合并产生该 Sidecar 自己的 MLS
reconciliation obligation；不会影响 controller 在其它 Realm 的 Sidecar。

每个 Sidecar `S` 的 desired/effective 集合必须以 exact `(S.realm_id, S.controller_account_id, S.id)` 独立求值。
来自其它 Realm 或其它 Sidecar 的 membership、Welcome、KeyPackage consume 或 MLS readiness **MUST NOT**
满足本 Sidecar 的任何条件。因而，对 `S1=(R1,C)` 完成 Agent membership 与 MLS reconciliation 不得改变
`S2=(R2,C)` 的 `desired_agent_ids`、`effective_agent_ids` 或 MLS membership，其中 `R1 != R2`。

Agent pause/deactivate、ownership 终止或 current Realm membership loss 会自动收窄派生的
`desired_agent_ids`，并产生该 Sidecar 的 MLS Remove/rotate obligation；它们不需要也不得触发第二次
Sidecar roster write。KeyPackage、Welcome、consume 或设备 key 尚未就绪只会使 desired Agent 暂未进入
`effective_agent_ids`。`effective_agent_ids` **MUST** 是 `desired_agent_ids` 的子集；Sidecar 仅在 controller
device、accepted MLS group 均就绪且两个集合相等时为 `ready`。这里的 controller device 不是任何 payload 字段，
而是 accepted Sidecar `ak.mls.genesis` 按
[`../crypto-media/encryption-and-audit.md` §5.1](../crypto-media/encryption-and-audit.md) 的创建者坐标从 Event
`actor_id` 与唯一 producer proof 的 `verification_method` fragment 派生得到。

resource-scoped capability、Agent participation selection 与 action policy 继续独立约束 Agent 可以读取之外执行
的 write、reply、mention、publish 等操作；它们不是第二套 MLS membership，也不得改变上述派生 roster。

## 6. 原生 MLS 绑定

Sidecar 拥有独立 MLS group，但该 group 直接绑定 `sidecar_id`，不绑定 Circle ID 或 membership typed current result。
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
  "controller_account_id": "ak:did_core:webvh:zExampleControllerScid",
  "desired_agent_ids": ["ak:did_core:webvh:zExampleDesiredAgentScid"]
}
```
`desired_agent_ids` 按 UTF-8 字节序排序去重。authority transcript 恰为上方五个成员，不包含 `effective_agent_ids`：
effective 是当前 MLS reconciliation 的结果，不是参与者 authority 的输入。`authority_stream_head` 同样**不是** transcript
成员，它是 `mls_context` 中与 `participant_authority_digest` 并列的独立字段（见
[`../sync/service-http-binding.md` §5](../sync/service-http-binding.md) 的 `AgentSidecarView`），承载派生 `desired_agent_ids`
所依据的 accepted EventId refs。它只能包含 Sidecar genesis、
ownership、Agent lifecycle/runtime-key authorization 与 exact Realm membership 的 accepted refs；不得包含 Circle membership、
Sidecar selection Event、action participation selection 或 MLS/key-readiness 结果。

Sidecar 的 `ak.mls.genesis`、每次 MLS Commit Event、pre-Genesis proposal 与 MLS GroupContext extension
都 MUST 在唯一 `mls_governance_binding` 中同时携带已签名的 `participant_authority_digest` 和
`authority_stream_head`；两字段的格式与 `AgentSidecarView.mls_context` 对应字段相同，后者只是读取投影，
不能代替签名载体。Realm／Circle scope MUST NOT 携带这两个字段。签名前应在同一 accepted authority cut
由上述允许的 refs 派生 `desired_agent_ids`、五成员 transcript 和摘要，并以 UTF-8 字节序排列、去重
`authority_stream_head`。Station 接受 Genesis／Commit 时 MUST 以其明确承诺的 cut 重算 roster 和摘要，
逐字段比对 Event payload binding、MLS GroupContext extension 与 accepted refs；遗漏、过期 cut、摘要不符、
额外或未排序 refs 均 MUST fail closed，零 Event／RealmCommit／MLS epoch／Welcome 副作用。并发 authority
变更先于该 MLS Event 接受时，旧 cut 不可继续获准；应以新 cut 重新生成并签名，而不能由服务器改写签名 binding。

`authority_stream_head` 最多 64 项，等于 binding decoder 的 `maximum_collection_items`（见
[`../crypto-media/encryption-and-audit.md` §2.5.1](../crypto-media/encryption-and-audit.md)）。任何 authority 变更若会使某个
Sidecar 的派生 cut 超过 64 项，治理 Station MUST 在**接受该变更时**以既有 `failed_precondition` 零写入拒绝，
不得拖到 MLS Genesis／Commit 时失败；不另设 reason，也不调高 decoder 上限。

新 desired Agent 在 Welcome、KeyPackage consume 与设备 readiness 全部完成前不得接收 Sidecar payload。
Agent 失去 desired 资格后，服务端必须立即停止新寻址/投递，并保留 MLS remove/rotate obligation；旧 epoch
key、旧 session 或本地缓存不能继续授权新写。

## 7. 生命周期

Sidecar state 是 accepted controller/Realm/ownership/Realm policy facet revision 的纯函数，不存在 actor-authored
Sidecar archive/restore/member Event：

| 源 | 目标 | 条件 |
| --- | --- | --- |
| active | suspended | controller 暂时失去 Realm active、policy 或 key readiness |
| suspended | active | 所有暂时条件恢复 |
| active/suspended | tombstoned | controller principal 或 parent Realm 进入不可逆 terminal |

`tombstoned` 不可逆。Sidecar terminal 只终止 native Sidecar scope、MLS 与 private projection，不触发或
修改任何 Circle lifecycle。

**没有 actor-authored erase，也没有重建（normative）**：Sidecar state 是 Sidecar stream 当前 committed head 的纯函数，
v1 **没有**注册任何 Sidecar erase / tombstone Event 或 operation；tombstone 只由上表右列的上游 terminal
派生。§1 的「每个 `(realm_id, controller_account_id)` 至多一个 non-tombstoned Sidecar」因此是**永久 reservation**：
一旦某个 `(realm_id, controller_account_id)` 的 Sidecar 进入 `tombstoned`，同一 key **MUST NOT** 再有新的
`ak.sidecar.create` 被接受（§3.1 的 singleton reservation 按 key 而不是按 live 状态判定）。理由是
tombstone 的两个触发条件本身都是上游终态：controller principal 或 parent Realm 已不可逆终止，重建
Sidecar 没有可用的 controller authority。

## 8. Private view 与显式发布

`ak.agent.sidecar.exchange.control` 写 `agent_sidecar_exchange_controls` typed current result：subject 是
`(payload.sidecar_id, canonical_json(payload.source_context_ref))`，value 是以 canonical Event dot 标记的
完整 encrypted control carrier 集合。`exchange_id` 只存在于
`ak.schema.agent_sidecar_exchange_control.v1` 认证密文明文中，MUST NOT 为了寻址复制到外层 payload 或
result selector。获授权参与者解密集合元素后，按 plaintext `exchange_id`、`basis_event_ids` 与 `action`
折叠 coordinator reassignment 和 terminal state；错误 controller／scope／context、无法认证的密文、
未覆盖 basis 或非法状态迁移都必须在 keyed-set add 之前拒绝，且不得留下部分写入。

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
遵循 [`client-sync.md` §5](../sync/client-sync.md) 与 [`current-results.md` §3–§5](../sync/current-results.md)。

已接纳回复及其验证依赖可取得时，consumer MUST 自动补齐并重新验证，然后更新原讨论中的私密投影，
不等待下一条用户消息或手动刷新。断线、cursor 失效或客户端重启后 MUST 自动恢复同一已接纳历史与
回复，按 Event id 去重，不重发请求、不再次执行 Agent、不清除身份密钥、MLS 私有状态或待发送草稿。
来源 Strand current／watch 的独立读取失败不得取消获授权 Sidecar 的续传；任何重试仍服从现有授权、
分页、generation 和撤权门。服务不可用时不承诺回复产生或固定完成时限，但恢复不能依赖用户刷新。

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

读取只通过 `ak.self.agent.sidecar.resource.get.v1` 与 `ak.self.agent.sidecar.query.list`。返回 Sidecar、
`desired_agent_ids` 只读派生投影、`effective_agent_ids`、MLS readiness、pending reconciliation 和 source
context mappings。
普通 Circle/Strand/Relation list 不得泄漏 Sidecar 存在、private Event、计数、未读、搜索或通知差异。

## 10. 验收不变量

1. `retype(ak.sidecar.create.event_id) == sidecar.id`。
2. schema 与 registry 中不存在 `backing_circle_id` 或 `ak.sidecar.access.replace`。
3. Sidecar create 不产生 Circle/member/Strand/Relation write。
4. `desired_agent_ids` 只能从 Sidecar stream 当前 committed head 派生；任何 operation 均不可写入或覆盖它。
5. native `scope_ref.kind="sidecar"` 进入 digest、delivery/query 与 RealmCommit 验证。加密时从已签名外层
   Event 的 exact `scope_ref` 重构 closed pre-encryption header；最小 wire envelope 不复制
   scope、`sidecar_id`、AAD 或其 digest。接收方必须按
   [`../crypto-media/encryption-and-audit.md` §2.3](../crypto-media/encryption-and-audit.md) 从外层 Event 与 exact
   winning group state 重构并验证，不得从密文 wire 枚举 Sidecar 的存在、数量与活跃度。
   逐字节 KAT（含 Realm 与 Sidecar 两个 scope 摘要不同的断言）在
   `ak.vector.encoding.encrypted_envelope_digest.v1`。
6. Sidecar view 映射不改变 source Strand history；publish 创建新普通 Event。
7. 同 ID + 不同 canonical genesis bytes 必须 conflicting-reuse fail closed。
8. 同一 controller 在两个 Realm 中的 Sidecar 必须独立求值：只为其中一个 Realm 建立的 membership 与该
   Sidecar 的 MLS readiness 不得使 Agent 进入另一个 Sidecar 的 `desired_agent_ids` / `effective_agent_ids`，
   也不得触发另一个 Sidecar 的 MLS Add、payload delivery 或 future epoch key 交付。

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
