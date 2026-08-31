---
title: Agent Sidecar
status: candidate
normative: true
stability: v1
updated: 2026-08-07
---

## 0. 规范语言

本文中的 **MUST** / **SHOULD** / **MAY** 按
[`conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 对象边界

Agent Sidecar（`ak:sidecar:`）是绑定到一个 `(realm_id, controller_id)` 的个人 AI 私有工作区。
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
| 参与者 | 显式可治理成员子集 | 由 ownership/lifecycle 与 exact Realm membership frontier 派生，不可编辑 |
| scope | `scope_ref.kind="circle"` | `scope_ref.kind="sidecar"` |
| 跨边界映射 | 不允许自动映射到圈外 Strand | 可在普通 Strand shell 中显示 private view；durable publish 必须创建新 Event |
| MLS | Circle membership 驱动 | ownership、lifecycle、runtime-key authorization 与 exact Realm membership 派生目标 roster；MLS/key readiness 只决定 effective 收敛状态 |

协议中不存在 Sidecar backing Circle。实现 MUST NOT 为 Sidecar 创建、隐藏、保留或模拟 Circle 对象、
Circle membership、Circle role/admin、Circle join rule、Circle invite 或 `SC-` 保留名称。

每个 `(realm_id, controller_id)` MUST 至多存在一个 non-tombstoned Sidecar。

## 2. Sidecar 对象与身份

Schema id：`ak.schema.agent_sidecar.v1`。

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `id` | yes | `id:sidecar` | Event-derived 44 字符 token；`retype(create_event.event_id,"sidecar")` |
| `schema` | yes | const | `ak.schema.agent_sidecar.v1` |
| `realm_id` | yes | `id:realm` | 从 create Event scope 派生，create-locked |
| `controller_id` | yes | `did_core_id` | 等于 create Event `actor_id`，create-locked |
| `encryption_profile` | yes | const | `mls_rfc9420` |
| `state` | yes | enum | `active | suspended | tombstoned`，reducer-derived |
| `state_changed_at` | conditional | timestamp | 非 active 时必填 |
| `created_at` | yes | timestamp | 等于 accepted create Event `created_at` |
| `updated_at` | no | timestamp | reducer-derived |

`backing_circle_id`、成员列表、管理员、title、summary、directory visibility、join rule 与 history visibility
均不是 Sidecar 字段。

## 3. 创建与原生 scope

### 3.1 `ak.sidecar.create`

`ak.sidecar.create` 是 Sidecar 唯一 genesis Event：

```text
sidecar_id = retype_event_token(event.event_id, "sidecar")
realm_id = event.scope_ref.realm_id
controller_id = event.actor_id
created_at = event.created_at
```

create Event 使用 parent Realm scope，因为 Sidecar 尚未存在：

```json
{
  "scope_ref": {"kind":"realm", "realm_id":"ak:realm:..."},
  "payload": {"encryption_profile":"mls_rfc9420"}
}
```

payload MUST NOT 携带 `sidecar_id`、完整 Sidecar object、`controller_id`、成员、Circle ID、Strand ID、
Relation ID、state 或 timestamp。Receiver MUST 重算 Sidecar ID；payload 携带这些字段必须在 schema 层拒绝。

`ak.component.sidecar.create.v1` 以派生 `sidecar_id` 为 subject，保存已接受 genesis intent。
Reducer 另以 `(realm_id, controller_id)` 执行原子 singleton reservation；相同 key 的 exact replay 幂等，
不同 create Event 必须 fail closed，不得 LWW、merge 或创建第二个 Sidecar。

### 3.2 后续 Event scope

Sidecar create accepted 后，全部 Sidecar-private Event 必须使用：

```json
{
  "kind": "sidecar",
  "realm_id": "ak:realm:...",
  "sidecar_id": "ak:sidecar:..."
}
```

Receiver MUST 验证 Sidecar 存在、Realm 一致、actor 属于当前有效访问集合，并将完整 `scope_ref`
纳入 Event digest、AAD、query/delivery 裁剪与 Seal coverage。普通 Circle API、Circle capability 与 Circle
membership proof 不能授权 Sidecar Event。

## 4. Context attach：映射，不创建对象

`ak.sidecar.context.attach` 把一个已经存在的普通 Strand 或 Relation 记录为 Sidecar 的 source/UI context。
它只写 `ak.component.sidecar.context.v1`，不创建 private Strand、Relation 或任何其它协议对象。

payload 是：

```json
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

Sidecar 没有独立的 membership 管理面。其 MLS 目标参与者是 accepted frontier 上的纯派生集合：

```text
desired_agent_ids(S, F) =
  active_authorized_owned_agents(S.controller_id, F)
  ∩ active_realm_member_ids(S.realm_id, F)
```

其中 `F` 是读取或 admission 使用的 accepted control frontier。`active_authorized_owned_agents` 来自 canonical
Agent ownership/provisioning、lifecycle 与 Agent runtime-key authorization truth；它不包含 target action grant、
participation selection 或 MLS readiness。`active_realm_member_ids` 来自 `S.realm_id` 自己的 Realm membership
truth。完整 MLS 目标 roster 是 `S.controller_id` 加上这个 Agent 集合；无需再维护第二个 participant 字段或
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

每个 Sidecar `S` 的 desired/effective 集合必须以 exact `(S.realm_id, S.controller_id, S.id)` 独立求值。
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

Sidecar 拥有独立 MLS group，但该 group 直接绑定 `sidecar_id`，不绑定 Circle ID 或 membership cell。
不存在 controller-global Sidecar MLS group：不同 `sidecar_id` 的 Add/Remove/Update、Welcome、epoch、future
epoch key 与 reconciliation 状态彼此隔离，任何一项都不得跨 Sidecar 复用或传播。

`participant_authority_digest` 必须覆盖：

```json
{
  "domain": "ak.sidecar.participant_authority.v1",
  "sidecar_id": "ak:sidecar:...",
  "realm_id": "ak:realm:...",
  "controller_id": "ak:did_core:webvh:zExampleControllerScid",
  "desired_agent_ids": ["ak:did_core:webvh:zExampleDesiredAgentScid"]
}
```

`desired_agent_ids` 按 UTF-8 字节序排序去重。authority transcript 恰为上方五个成员，不包含 `effective_agent_ids`：
effective 是当前 MLS reconciliation 的结果，不是参与者 authority 的输入。`control_frontier` 同样**不是** transcript
成员，它是 `mls_context` 中与 `participant_authority_digest` 并列的独立字段（见
[`../sync/service-http-binding.md` §5](../sync/service-http-binding.md) 的 `AgentSidecarView`），承载派生 `desired_agent_ids`
所依据的 accepted refs。它只能包含 Sidecar genesis、
ownership、Agent lifecycle/runtime-key authorization 与 exact Realm membership 的 accepted refs；不得包含 Circle membership、
Sidecar selection Event、action participation selection 或 MLS/key-readiness 结果。

新 desired Agent 在 Welcome、KeyPackage consume 与设备 readiness 全部完成前不得接收 Sidecar payload。
Agent 失去 desired 资格后，服务端必须立即停止新寻址/投递，并保留 MLS remove/rotate obligation；旧 epoch
key、旧 session 或本地缓存不能继续授权新写。

## 7. 生命周期

Sidecar state 是 accepted controller/Realm/ownership/policy frontier 的纯函数，不存在 actor-authored
Sidecar archive/restore/member Event：

| 源 | 目标 | 条件 |
| --- | --- | --- |
| active | suspended | controller 暂时失去 Realm active、policy 或 key readiness |
| suspended | active | 所有暂时条件恢复 |
| active/suspended | tombstoned | controller principal 或 parent Realm 进入不可逆 terminal |

`tombstoned` 不可逆。Sidecar terminal 只终止 native Sidecar scope、MLS 与 private projection，不触发或
修改任何 Circle lifecycle。

**没有 actor-authored erase，也没有重建（normative）**：Sidecar state 是 accepted frontier 的纯函数，
v1 **没有**注册任何 Sidecar erase / tombstone Event 或 operation；tombstone 只由上表右列的上游 terminal
派生。§1 的「每个 `(realm_id, controller_id)` 至多一个 non-tombstoned Sidecar」因此是**永久 reservation**：
一旦某个 `(realm_id, controller_id)` 的 Sidecar 进入 `tombstoned`，同一 key **MUST NOT** 再有新的
`ak.sidecar.create` 被接受（§3.1 的 singleton reservation 按 key 而不是按 live 状态判定）。理由是
tombstone 的两个触发条件本身都是上游终态：controller principal 或 parent Realm 已不可逆终止，重建
Sidecar 没有可用的 controller authority。

## 8. Private view 与显式发布

客户端 MAY 在普通 Strand shell 中显示 Sidecar-private view，但必须明确标记 private provenance，且
进入/退出 Sidecar 不得改变普通 Strand canonical history。

真正发布到普通 Strand 必须由 controller 对最终 allowlist payload 显式确认，并创建一条新的普通
Strand Event：

- 新 Event 有自己的 Event ID、签名、scope 与 authorization；
- 不复制 private Event envelope；
- 不泄漏 `sidecar_id`、private Event ID、MLS material、Agent scratchpad/tool output、exchange/control plaintext；
- 失败或重试不得产生部分 shared durable output。

Circle 内容不得使用本节映射或发布规则跨越 Circle 边界。

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
4. `desired_agent_ids` 只能从 accepted frontier 派生；任何 operation 均不可写入或覆盖它。
5. native `scope_ref.kind="sidecar"` 进入 digest、delivery/query 与 Seal 验证。加密时从已签名外层
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
- `ak.vector.sidecar.union_history_frontier.v1`
- `ak.vector.sidecar.non_disclosure_surface_matrix.v1`
- `ak.vector.sidecar.revoke_fail_closed.v1`
- `ak.vector.sidecar.explicit_publish.v1`
- `ak.vector.sidecar.accepted_request_identity.v1`
- `ak.vector.sidecar.hosted_ui_matrix.v1`

## 11. 规范性引用

- Event/ID 派生：[`common-fields.md`](./common-fields.md)、[`event-and-patch.md`](./event-and-patch.md)
- Agent ownership/lifecycle：[`actor.md`](./actor.md)、[`../identity/key-management.md`](../identity/key-management.md)
- MLS：[`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)
- Circle 边界：[`circle.md`](./circle.md)
