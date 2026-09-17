---
title: 服务器当前结果与有界基线
status: candidate
normative: true
stability: v1
updated: 2026-09-18
sidebar:
  label: 当前结果与基线
---

本文规范用语遵循 [规范性语言](../conformance/normative-language.md)。

## 1. 权威来源

治理 Station 按目标 stream 的 RealmCommit 顺序接纳 Event，并在同一事务内更新该领域的当前结果。客户端 MUST
把 Station 返回的 typed current result 作为共享状态的当前权威视图；Event timeline 用于审计与内容读取，不要求客户端
重放 Event 来恢复共享状态。

Realm、每个 Circle、每个 Sidecar 分别拥有独立 commit stream。当前结果响应携带本次视图所覆盖 stream 的
`stream_heads[]`；不同 stream 之间不存在隐含总顺序。producer Event 不携 predecessor，只有 RealmCommit 的
`previous_commit_ref` 串联同一 stream。

机器合同为
[current-result-registry](../../artifacts/registry/current-result-registry.json)、
[typed-current-result schema](../../artifacts/schemas/typed-current-result.schema.json) 与
[account-current-result schema](../../artifacts/schemas/account-current-result.schema.json)。实现 MUST NOT 发明协议级通用状态键、
通用合并算法或客户端求值规则。

**value 形状的唯一命名方式（normative）**：typed current result 的 value 形状由该 family 的
`result_writes[].value_schema_ref` 以 JSON Pointer 指向 `typed-current-result.schema.json`
的一个 `$defs` 成员，**MUST NOT** 另外获得自己的 `ak.schema.*` id。
`schema-registry.json` 登记的是 **wire schema**——被签名、被传输、被 `payload.schema` 或 DTO
`$ref` 按 id 引用的对象；typed current result 的 value 不是其中任何一种，它是 reducer 的输出，
唯一的读取路径就是那条指针。给某个 value 单独发一个 schema id，会让它看起来像 wire schema，
并诱导实现按 id 绑定而绕过登记的写入合同。`ak.schema.result_projection.v1` 仍然登记，
因为那是该**文件整体**的 id；`realm_authority_root_value` 曾是唯一带独立 id 的 value 例外，该 id 已撤销；
它的写入方本来就只引用指针，所以除那个 id 之外没有任何东西被移除。

## 2. 领域 selector 与 revision

每条结果是一个 closed typed object，包含领域 `selector`、`revision` 与完整领域值。v1 登记的 selector kind 为：

- `realm_profile`：当前 Realm profile；
- `realm_policy`：当前 Realm policy，值是 `ak.realm.policy` 选定的封闭引用 `{policy_id}`，
  **不是** Policy 文档本体（见 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)）；
- 以下十二个是 **per-Realm 单例 Realm facet**，subject 为 JSON null
  （[`../conformance/encoding.md` §9.5.1](../conformance/encoding.md) 禁止把 envelope 的
  `realm_id` 再写进 subject），各由同名 facet Event kind 单独承载：
  `realm_schema`、`realm_join_rule`、`realm_discovery`、`realm_alias`、`realm_policy_bundle`、
  `realm_asset_privacy_policy`、`realm_plaintext_visible_services`、`realm_media_service`、
  `realm_read_receipt_policy`、`realm_tombstone`、`realm_destroy`、`realm_set_default_strand`。
  [`../models/realm-and-space.md` §2.6.0](../models/realm-and-space.md) 另以同一形态命名了
  `realm_archive` 与 `realm_freeze`，但二者尚未登记为 `result_kinds[]` 行，故**不在**本清单内；
  在它们登记之前，本清单的数目以本行为准；
- `realm_link`：以 `(target_realm_id, link_kind)` 选择一条 Realm 间链接
  （见 [`../models/realm-links.md` §5](../models/realm-links.md)）；
- `realm_inheritance_policy`：以 `source_realm_id` 选择自某一父 Realm 继承的策略——
  继承是 per-parent 的，单例 subject 会让一个父 Realm 的继承覆盖另一个；
- `member_state`：以完整 `actor_id` 选择成员状态；
- `strand`：以 `strand_id` 选择 Strand；
- `strand_position`：以 `typed_pair(id:space(board_space_id), id:strand(strand_id))` 选择一条
  Strand 在某个 Board 上的位置，值为 `{list_space_id, rank}` 或 `null`（尚未上板）
  （见 [`../models/realm-and-space.md` §3.6](../models/realm-and-space.md)）；
- `space_parent`：以 `space_id` 选择一个 Space 的结构父，值为单成员对象 `{parent_space_id}`（成员可空，null 即 root），**值本身不是裸 null**——本 family 的 compare-and-set 是对已存字段的谓词，裸 null 没有字段可比
  （见 [`../models/realm-and-space.md` §3.5](../models/realm-and-space.md)）；
- `space_child_scope_policy`：以 `space_id` 选择该 Space 的子资源 placement policy，值为封闭 policy 对象或 `null`（未声明）；
  它由 `ak.space.create` 与 `ak.space.update` 顶层 `child_scope_policy` 成员上的专用非 patch 写维护（见 [`../models/circle.md` §7.1](../models/circle.md)）；
- `message_reactions`：以被表态对象的 `payload.target_ref` 选择该 target 的 reaction 断言集合（v1 core 的 target MUST 是同一 effective scope 内的 `ak:message:`，见 [`../models/strand-and-message.md` §9.8.2](../models/strand-and-message.md)）；值是 `keyed-set projection` 的 dot 集合，**不是** `(target_ref, key, members[], count)` 默认视图——后者是它之上的读侧折叠（§9.8.3）；
- `mls_group`：以 Realm 或 Circle `scope_ref` 选择 MLS group；
- `realm_authority_root`：singleton，值为 `typed-current-result.schema.json` 的封闭 `realm_authority_root_value`（由各写入方的 `value_schema_ref` 以 JSON Pointer 指向；它没有、也 MUST NOT 有自己的 `ak.schema.*` id，见上节末段与 [`realm-and-space.md` §2.5.1](../models/realm-and-space.md)）；
- `agent_key`：以 `(agent_id, agent_key_id)` 选择一把 Agent 签名 key 的 registered authorization 投影；
- `agent_status`：以 `agent_id` 选择该 Agent 的 lifecycle 值；
- `agent_provisioning`：以 `agent_id` 选择一条 Agent provisioning 事实，值为四个 create-locked 成员 `{controller_principal_id, principal_control_realm_id, controller_authorization_ref, requested_scope_digest}`；它是 `commit-ordered projection`，由 `ak.agent.provision` 的四个原子投影之一写入，subject 是 Agent DID 而**不是**完整 account ActorId（见 [`../identity/key-management.md` §3.6.3](../identity/key-management.md)）；
- `agent_selector_claim`：以 `(controller principal, agent_slug)`（**不含** Station）选择一条 controller-scoped Agent selector 绑定，值为 `{subject_account_id, visibility, audience?, expires_at?}`；`subject_account_id` 显式 null 即 unbind；它是 `commit-ordered projection`，有两个写入方（独立的 `ak.agent.selector_claim` 与 `ak.agent.provision` 的 selector 投影，后者的 AccountId 由已登记派生 `agent_account_id_from_provision` 产出），见 [`../models/actor.md` §3.3](../models/actor.md)；
- `agent_pcr_genesis_declaration`：以 `principal_control_realm_id` 选择该 realm id 的前向声明，值为单成员索引 `{agent_id}`；Agent PCR genesis 不携带指回 provision 的 ref，因此对本家族的反查**就是**那条绑定，无行即 fail closed 且零写入（同上 §3.6.3）；
- `realm_genesis`：singleton，create-locked identity/security core（`ak.schema.realm_genesis.v1`），由 `ak.realm.create` 的 registered write 一次写入；
- `realm_history_access`：singleton，Realm history-access FSM 当前值（`since_join` / `all_history_for_current_members`）；
- `identity_resolution`：singleton，Realm 当前 did resolution 的五成员 `resolution_projection`；genesis object 携带 `initial_resolution` 时由 `ak.realm.create` 条件初始化，此后只由 `ak.identity.resolution.update` 改写（见 [`../identity/identity-did.md` §4.2](../identity/identity-did.md)）；
- `identity_accountability`：以 `(issuer principal, subject principal, 归一化 exact scope set)` 选择一条问责背书；第三个分量按 `ak.accountability_scope_set.v1` 摘要，因此 wire 上的单个字符串与它的单元素数组落在同一个 subject；它有两个写入方（独立的 `ak.identity.accountability_grant` 与 `ak.agent.provision` 的原子问责投影），见 [`../models/actor.md` §3.3.1](../models/actor.md)；
- `capability_grant`：以 `grant_id` 选择一条 Capability Grant 的完整投影（含 reducer 派生的 `authority_depth` / `authority_root_refs`，见 [`capabilities.md` §10](../authz/capabilities.md)）；
- `pin`：以完整封闭的 `pin_scope`（`{kind, id}`）选择一个 pin scope 的 tagged 断言集；它是 `keyed-set projection`，
  三条 `ak.pin.*` 各加一条断言，roster、remove-wins 与冲突视图都是读侧折叠（见 [`../models/pins.md` §4.1](../models/pins.md)）；
- `invite_lifecycle`：以 `invite_id` 选择一条 Invite 的流程状态轴；它是 `transition_contracts` 登记的
  状态机 family，值只有状态名本身（见 [`../models/governance-objects.md` §5.3](../models/governance-objects.md)）；
- `invite_live_target`：以 `canonical_json(invitee_account_id)` 选择该 invitee 在本 Realm 的唯一 live
  direct invite 槽位，值为 `{create_event_id}` 或 `null`（空槽）；**subject 不含 `realm_id`**；
- `invite_directed_invitee`：以 `invite_id` 选择该 Invite 的 create-locked 定向目标 `{invitee_account_id}`；
  它是 `invite_live_target` 的反向索引，三方（3PID）Invite 不写这条，故其前态为**缺失**而不是 `null`；
- `call_state` / `call_focus` / `call_moderation` / `call_roster` / `call_mute_override`：以 `call_id` 选择 `ak.call.state` 对应轴的 commit-ordered 投影（见 [`call-state.md` §4.1](../crypto-media/call-state.md)）；
- `call_recording_state` / `call_transcript_state`：以 `(call_id, recording_id)` 段键选择该段捕获的许可状态；
- `call_recording_artifact` / `call_transcript_artifact`：以 `(call_id, recording_id)` 段键选择该段捕获的 ready/failed 结果；
- `call_summary`：以 `call_id` 选择 write-once 的终态通话摘要。

selector 的身份字段来自已接纳 Event 的 typed payload，不得由调用方另行声明或由服务端按显示名称猜测。新增领域结果
必须先扩展 registry 与 schema；未知 selector 必须拒绝，不能退化为任意 JSON。

`revision` 是 closed `{commit_id, stream_position}`。`commit_id` MUST 指向最后改变该结果的 RealmCommit，
`stream_position` MUST 等于该 commit 在所属 stream 的位置。二者共同提供可验证的当前版本；时间戳、到达顺序与
EventId 均不得替代 revision。

领域写操作需要并发保护时，payload 使用该领域定义的 `expected_revision`。Station 只在它与当前 typed revision
逐字段相等时接纳；不相等返回 `failed_precondition` 并提供调用者有权读取的 current result。首次创建可使用该领域
schema 明确允许的 `null`，不得使用字符串哨兵或通用条件表达式。

### 2.1 生命周期轴与转换合同

某个领域结果若带有生命周期轴（状态机），该轴的转换真源是 contract registry 的
`event_kind_registry.transition_contracts` 中同名 family 条目：它封闭该轴的状态集合、入口
（`initial_state` / `initial_states` / `template` 三者恰取其一）、终态与允许的 `(from, to)` 边。
本节只定义合同的读法，不复制任何一张转换表。

- 写入该 family 的 Event MUST 使用 `transition` 投影并声明 `from` 与 `to`；MUST NOT 使用整值投影。
  整值写入会绕过 `allowed_transitions`，使转换表退化为注释而不是规则。
- `from` 与 `to` 各自 MUST 恰好声明 `const` 与 `field` 之一。一行需要承载多条边（前态取值不止一个）时
  用 `field` 指向 payload 中已封闭该取值集合的字段，不得在 registry 里另抄一份常量。
- 未在 `transition_contracts` 中登记的 family MUST NOT 使用 `transition` 投影：没有状态集合的
  `from` / `to` 对没有任何可校验的对象。
- 终态 MUST NOT 带出边。终态性只由转换表本身承载；实现不得以约定、服务端表或默认值补充。

该合同缺失时 MUST 视为失败，不得当作「该轴无约束」：读不到转换表的检查只能证明没有人检查过。

## 3. 当前结果响应

`AccountCurrentResult.current` 是 closed：

- `realm_id`：结果所属 Realm；
- `governance_generation`：当前治理 Station 任期代次；
- `stream_heads[]`：调用者获准读取的 Realm/Circle/Sidecar stream heads；
- `entries[]`：closed typed results。

同一 selector 在同一 revision 下必须具有完全相同的 canonical bytes。发现相同 revision、不同值时，客户端 MUST
拒绝整批响应并重新获取当前 authority bundle；不得任择覆盖。较新 revision 原子替换旧值；来自旧
`governance_generation` 的响应不得覆盖新任期结果。

响应只包含调用者当前有权读取的 selector。省略不表示空值、删除或权限；领域若允许显式空值，必须由其 typed value
表达。成员退出、Circle 撤权或 Station 更换后，客户端必须按新授权范围清除不可再见的缓存，但不得由响应差异推断隐藏对象。

## 4. 有界基线与续传

`AccountCurrentResult.coverage` 携带 `realm_id`、`stream_heads[]` 与 `complete_for_authorized_streams`。只有在：

1. 所有获准 stream 都已扫描到所声明 head；
2. 对应 entries 已耐久安装；
3. 本次读取期间 `governance_generation` 未改变；

三项同时成立时，服务端才可返回 `complete_for_authorized_streams=true`。

分页 cursor 必须绑定 `realm_id`、`governance_generation`、每个已覆盖 stream head 与最后一个稳定排序键。缺页、重复页、
`governance_generation` 改变或任一 head 改变时，客户端 MUST 废止该基线并从当前 authority bundle 重新开始。Circle 与 Sidecar 的
分页进度分别绑定各自 stream；不得借 Realm stream head 声明它们已完整。

Realm join bootstrap 默认从当前治理 Station 获取 authority bundle、获准 stream heads、committed Events 与 current
results。邀请人服务器只转交邀请和当前 governance Station 定位证据；它不是 bootstrap 真相源，除非它恰好就是经验证的
current governance Station。

## 5. 预算与失败

单次响应必须遵循 transport 的 canonical 与 wire 大小上限。分页只能在完整 entry 之间切分；一个 entry 不得截断。
结果暂不可计算、依赖 commit 缺失或授权状态不完整时，服务端 MUST fail closed，并要求调用者从当前 governance Station
重新同步；不得伪造默认值、让客户端从部分 Event 猜测结果或跨 stream 拼出虚假的全局顺序。

当前结果不授予写权限。每次提交仍由治理 Station针对当前 capability、成员资格、policy、领域 revision 与 MLS 约束重新校验。
