---
ckp: CKP-0016
title: Agent 参与策略与分层授权上限
normative: false
stability: v1
updated: 2026-06-09
status: accepted
created: 2026-06-09
authors:
  - chris@acroidea.com
depends_on: [CKP-0007, CKP-0008, CKP-0009]
discussion: internal (no public URL)
merged_into:
  - spec/v1/zh/models/realm-and-space.md
  - spec/v1/zh/models/circle.md
  - spec/v1/zh/models/flow-and-message.md
  - spec/v1/zh/authz/capabilities.md
  - spec/v1/zh/sync/service-surface.md
  - spec/v1/zh/models/private-objects.md
  - spec/v1/zh/conformance/conformance-profiles.md
  - spec/v1/zh/conformance/conformance-vectors.md
---

> Normative entry points:
>
> - [`spec/v1/zh/models/realm-and-space.md`](../zh/models/realm-and-space.md) §2.2 — Realm `agent_participation` policy component（ceiling）。
> - [`spec/v1/zh/models/circle.md`](../zh/models/circle.md) §7 — Circle `agent_participation` ceiling 的 tighten-only 校验。
> - [`spec/v1/zh/models/flow-and-message.md`](../zh/models/flow-and-message.md) §9.4 — Flow ceiling 与第三方 mention 投递路由规则。
> - [`spec/v1/zh/authz/capabilities.md`](../zh/authz/capabilities.md) §5.4 — participation actions 与 selection→grant 物化。
> - [`spec/v1/zh/sync/service-surface.md`](../zh/sync/service-surface.md) §10.1 — `ck.self.agent.participation.{set,get}` 与 session `scope_details.participation`。
> - [`spec/v1/zh/models/private-objects.md`](../zh/models/private-objects.md) §4.1 — controller-owned `ck.agent.participation.v1` account-data。
>
> Schema / registry artifacts: `contract-catalog.json`（source of truth；`operation-registry.json` / `capability-action-registry.json` 由它生成）、`account-data-type-registry.json`、`agent-operations.schema.json`、`realm.schema.json` / `circle.schema.json` / `flow.schema.json`、`profiles/conformance-profiles.json`。

## 1. 概要

本提案定义 `ck.profile.agent_participation_policy.v1`：在 CKP-0008 native personal agent 之上，增加一条由 **controller 设置、由分层 governance ceiling 约束** 的"参与策略"。它回答三个产品问题：

1. 用户如何按 Realm / Circle / Flow 分别决定"我的 agent 在这里能做到的最大行为"（能否以 agent 身份回复、是否接受其他用户的 @mention、是否允许代我执行）？
2. 这些 controller 选择如何受 全局部署策略 → Realm policy → Circle → Flow 这条链的逐层收紧约束，使内层对象的有效上限永不超过外层？
3. "不接受他人 @mention"等设置如何既由服务端强制执行，又传达给 agent runtime，使其主动按预期方式工作？

本提案不引入新的 enforcement 路径。它复用 CKP-0008 的 capability intersection、`ck.capability.grant`/`revoke`、`ck.realm.policy_components` 与现有 mention fanout，只新增三件事：参与策略 vocabulary、分层 ceiling 的 tighten-only 不变量、以及第三方 mention 投递的策略门。

非目标：本提案不覆盖 Applet / Ghost Actor（它们由 Realm policy 的 applet 分支与 CKP applet-integration 单独控制）。它只约束 native personal agents。

## 2. 参与策略 vocabulary

`AgentParticipation` 是三个正交布尔位的集合，描述 native personal agent 在某一 scope 内被允许的**自主行为上限**：

| 位 | 含义 | 默认 |
| --- | --- | --- |
| `reply` | agent 可以在该 scope 内以自身身份（reply-as-agent）写入 `ck.message.create` / `ck.reaction.add`。 | `false` |
| `accept_third_party_mention` | 由 **非 controller** 的 principal 发出、target 为该 agent 的 mention，会被投递给该 agent（notification fanout + agent `ck.self.events.subscribe` 投影），并可触发 agent 自主处理。`false` 时第三方 mention 对该 agent 不可见，只有 controller 自己的 mention / sidecar prompt 能到达。 | `false` |
| `act_on_behalf` | agent 可写入 `actor_id=controller, executed_by=agent` 的 act-on-behalf event（受 CKP-0008 §4.10 的 fresh approval / accountability 约束）。 | `false` |

三位构成一个偏序格（按蕴含关系）。一个 `AgentParticipation` 值 P1 ⊆ P2 当且仅当 P1 的每一位为真都蕴含 P2 对应位为真。空集（全 `false`）是最小元，全 `true` 是最大元。

`accept_third_party_mention` 与 `reply` 正交：一个 agent 可以"接受他人 mention 但只读不回"（监听摘要场景），也可以"能回复但不接受他人 mention"（仅 controller 私下驱动）。

## 3. 设计不变量

1. **分层 ceiling 单调收紧**：存在四级 ceiling——deployment（global）⊇ Realm ⊇ Circle ⊇ Flow。对每一位 b，若某级 ceiling 的 b 为 `false`，则其所有内层 ceiling 的 b MUST 也为 `false`。reducer MUST 拒绝放宽父级的内层 ceiling，错误形态对齐 [`circle.md` §7](../zh/models/circle.md) 的 floor downgrade（`failed_precondition`, `reason="agent_participation_ceiling_widen"`）。
2. **Effective = controller selection ∩ 所有 enclosing ceiling ∩ CKP-0008 intersection**。任一来源缺失或 unknown MUST fail closed 为 `false`。
3. **Ceiling 默认 deny**：未显式声明 `agent_participation` 的 scope，其 ceiling 取 **父级 ceiling**（继承，不放宽）；deployment 顶层默认全 `false`，与 `ck.profile.sovereign_deployment.v1` 的 deny-default agent 语义一致。部署若要开放，必须显式声明。
4. **Selection 不是 enforcement**：controller selection 只是"愿望"。真正的 enforcement 是 reducer 对 materialized capability grant 的常规校验 + dispatcher 对 mention 的投递门。selection 通过物化为既有 primitive 生效，不新增并行校验栈。
5. **Native agent 与 Applet 分离**：参与策略只作用于 native personal agents。Realm policy MUST 能分别声明二者（沿用 CKP-0008 §4.9）。
6. **服务端权威、runtime 知情**：服务端是硬边界；agent runtime 额外收到 resolved 策略副本，用于主动遵守（不尝试越权），但 runtime 副本不是安全边界。

## 4. 分层 ceiling 的 wire 形态

### 4.1 Realm ceiling

`ck.realm.policy_components` 增加 `agent_participation` 组件，由持有 `ck.realm.admin` 的 principal 写入（复用既有 realm-admin action，不新增独立 action）：

```json
{
  "agent_participation": {
    "native_agent": {
      "reply": true,
      "accept_third_party_mention": true,
      "act_on_behalf": false
    }
  }
}
```

`native_agent` 子键与未来可能的 `applet_agent` 子键并列，保证 native agent 与 Applet/Ghost Actor 的策略不可被合并成单一开关（不变量 5）。未声明 `agent_participation` 时，Realm ceiling 继承 deployment ceiling。

### 4.2 Circle ceiling

Circle policy 增加 **可选** `agent_participation` 字段。注意它是**扁平三位** `{reply, accept_third_party_mention, act_on_behalf}`，不带 §4.1 Realm 的 `native_agent` 外层包裹——参与策略只约束 native personal agent，Circle / Flow 层无需区分 `applet_agent`（Applet 由 Realm policy 的 applet 分支单独控制）。reducer 在写入时 MUST 校验其每一位 ⊆ 父 Realm ceiling 的 `native_agent` 对应位（tighten-only），违反 fail closed。未声明时继承 Realm `native_agent` ceiling。该校验复用 [`circle.md` §7](../zh/models/circle.md) 既有的 floor-tighten 校验框架（与 `validate_metadata_floor_tightens` 同形）。

### 4.3 Flow ceiling

Flow object 增加 **可选** `agent_participation` 字段，形态与 Circle 相同（扁平三位、native-agent-only）。其有效父级 ceiling 为：`Flow.scope_circle_id` 指向 Circle 时取该 Circle ceiling；否则取 Realm-default `native_agent` ceiling。reducer 校验 tighten-only，未声明时继承父级。

### 4.4 Effective ceiling 解析

对某 `(scope)`，effective ceiling 是从该 scope 沿 Flow → Circle（若有）→ Realm → deployment 链路逐级取交（按位 AND）。由于不变量 1 已保证单调收紧，逐级 AND 等价于"取最内层显式声明值"，但实现 MUST 以逐级 AND 求值以对抗历史上违反不变量的数据（fail closed）。

## 5. Controller selection 与物化

### 5.1 Account-data 存储

controller 的 selection 存为 controller-owned account-data type `ck.agent.participation.v1`：

```text
ck.agent.participation.v1:<agent_principal_id>:<scope_key>
```

`scope_key` 是 effective_scope 的 canonical 派生：`realm:<realm_uuid>` / `circle:<realm_uuid>:<circle_uuid>` / `flow:<realm_uuid>:<flow_uuid>`。payload：

```json
{
  "type": "ck.agent.participation.v1",
  "agent_principal_id": "did:webvh:...:agents:summary-assistant",
  "scope": { "kind": "flow", "realm_id": "ck:realm:...", "flow_id": "ck:flow:..." },
  "selection": {
    "reply": true,
    "accept_third_party_mention": false,
    "act_on_behalf": false
  }
}
```

声明 `encrypted_at_rest=true`。owner 为 controller principal；reducer 据 key pattern 做归属校验。

### 5.2 物化到既有 primitive

`ck.self.agent.participation.set` operation 在校验 `selection ⊆ effective_ceiling` 后，把 effective selection（= selection ∩ effective ceiling）物化为既有 primitive：

- `reply` effective=true ⇒ 维护一条 `ck.capability.grant`：`actions=[ck.message.create, ck.reaction.add]`，resource selector = 该 scope（`kind="realm"` 或 `kind="object"`/`object_type="flow"`/`allowed_object_refs` 或 Circle selector），subject=agent。effective=false ⇒ 撤销对应 grant（`ck.capability.revoke`）。
- `act_on_behalf` effective=true ⇒ 追加 CKP-0008 §4.10 的 act-on-behalf grant（`approval_required` / `controller_approval_required` constraints）。false ⇒ revoke。
- `accept_third_party_mention` 不物化为 grant；它写入 reducer 可读的 effective-policy 投影（§6），由 dispatcher 在 mention fanout 时消费。

物化是幂等的：重复 set 收敛到同一 grant 集合。selection 改变导致的 grant 增删 MUST 是 atomic 编排（要么全部写入，要么全部失败），不得留下半物化状态。

## 6. 第三方 mention 投递路由（normative）

[`flow-and-message.md` §9.4](../zh/models/flow-and-message.md) 的 mention fanout 增加 agent gate：

当一条 `ck.message.create` / `ck.message.revise` 的 mention target 是一个 **native personal agent** principal 时，dispatcher / reducer 在派生该 agent 的 mention notification 前 MUST：

1. 解析该 message 所在 effective_scope（Flow → Circle/Realm）的、针对该 agent 的 effective participation（§4.4 ceiling ∩ §5 controller selection）。
2. 若 mention 作者 == 该 agent 的 controller principal：照常投递（仍受该 agent 是否被授权读取该 scope 约束）。
3. 若 mention 作者 != controller 且 effective `accept_third_party_mention=false`：MUST NOT 为该 agent 派生任何 mention notification、inbox row、push wakeup，也 MUST NOT 把该 mention 纳入该 agent 的 `ck.self.events.subscribe` 投影。该抑制只针对 agent 自身；对 message 的其他人类 target、shared history、其它投影无影响。
4. 若 `accept_third_party_mention=true`：照常投递，并受 `level=muted`、blocklist、DND、rate-limit 等既有更高优先级规则约束（沿用 §9.4 现有覆盖顺序）。

该 gate 是 reducer/dispatcher 强制规则，不依赖 agent runtime 自觉。`ck.message.mention.broadcast`（audience mention）命中 agent 时同样适用本 gate；CKP-0008 §4.9 已要求自动化 actor 的 audience mention 采用更低 quota 与 accountability 约束。

## 7. 传达给 agent runtime

### 7.1 Session grant overlay

`ck.profile.agent_auth.v1` 的 session-grant 响应 `scope_details`（CKP-0008 §4.6）增加 `participation` 数组，承载本次 `agent_scope_request` 覆盖范围内、已解析的 effective 策略：

```json
{
  "scope_details": {
    "realm_ids": ["ck:realm:..."],
    "flow_ids": ["ck:flow:..."],
    "participation": [
      {
        "scope": { "kind": "flow", "realm_id": "ck:realm:...", "flow_id": "ck:flow:..." },
        "reply": true,
        "accept_third_party_mention": false,
        "act_on_behalf": false
      }
    ]
  }
}
```

runtime MUST 把该 `participation` 视为本 session 的行为契约：`reply=false` 的 scope 不尝试写入；`accept_third_party_mention=false` 的 scope 即使（因实现 bug）收到第三方 mention 也 MUST NOT 自主响应；`act_on_behalf=false` 不构造 `executed_by` event。

### 7.2 读取 operation

```text
GET /_cokret/self/agents/{agent_principal_id}/participation
operation_id: ck.self.agent.participation.get
```

返回该 agent 在 controller 可见范围内所有已解析 effective 策略的 map，供 controller UI 展示与 runtime 主动刷新。响应同时携带每个 scope 的 `ceiling` 与 `selection` 两个分量，便于 UI 区分"被 governance 封顶"与"controller 自己关闭"。

### 7.3 防御纵深

即使 runtime 忽略 §7.1 契约：

- `reply` 越权被 reducer 拒绝（无对应 `ck.message.create` grant → `failed_precondition`）。
- 第三方 mention 在 §6 已被 dispatcher 拦下，runtime 根本收不到。
- `act_on_behalf` 越权被 receiver 的 `executed_by` / `authorization_ref` 校验拒绝（CKP-0008 §4.10）。

runtime 副本只为减少无谓尝试与改善 UX，不承担安全边界。

## 8. Operations 与 capability actions

### 8.1 Operations（service-surface §10.1）

```text
PUT  /_cokret/self/agents/{agent_principal_id}/participation   ck.self.agent.participation.set
GET  /_cokret/self/agents/{agent_principal_id}/participation   ck.self.agent.participation.get
```

`set` 请求体：

```json
{
  "scope": { "kind": "flow", "realm_id": "ck:realm:...", "flow_id": "ck:flow:..." },
  "selection": { "reply": true, "accept_third_party_mention": false, "act_on_behalf": false }
}
```

`set` MUST fail closed，除非：caller 是该 agent 的 controller；该 agent active；`selection ⊆ effective_ceiling(scope)`；scope 可解析且 controller 是该 Realm active member。超出 ceiling 的位返回 `failed_precondition`（`reason="agent_participation_exceeds_ceiling"`），并在 error detail 中列出被封顶的位，使 UI 能解释"为何不能开启"。

### 8.2 Capability actions（capabilities.md §5.4）

- `ck.self.agent.participation.set`（controller-only aggregate admin；profile=`ck.profile.agent_participation_policy.v1`；`target_event_kinds=[ck.capability.grant, ck.capability.revoke]` + controller-private `ck.agent.participation.v1` account-data 写入。account-data 写入不纳入 grantable set，由 controller 对自身 account-data 的固有写权批准——与 CKP-0009 sidecar projection 同构）。**这是本提案唯一新增的 capability action。**

各级 ceiling 均复用既有 action，不新增独立 action：Realm ceiling 由持有 `ck.realm.admin` 的 principal 写入 `ck.realm.policy_components` 的 `agent_participation` 组件；Circle / Flow ceiling 通过既有 `ck.circle.manage` / `ck.flow.admin` 写入对应 object 的 `agent_participation` 字段。

## 9. 与 normative spec 的交互

- ✅ `zh/models/realm-and-space.md` §2.2：增加 `agent_participation` policy component 与 deployment 继承规则。
- ✅ `zh/models/circle.md` §7（字段表 §2）：增加 Circle `agent_participation` 字段与 tighten-only 校验（与 floor 同框架）。
- ✅ `zh/models/flow-and-message.md` §3（Flow 字段表）增加 `agent_participation` 字段、§9.4.5 增加第三方 mention 投递 gate。
- ✅ `zh/authz/capabilities.md` §5.4：增加 `ck.self.agent.participation.set` 与 selection→grant 物化说明（Realm ceiling 复用 `ck.realm.admin`，无新增 action）。
- ✅ `zh/models/private-objects.md` §4.1：注册 `ck.agent.participation.v1` controller-owned account-data。
- ⏳ `zh/sync/service-surface.md` §10.1、`zh/conformance/conformance-profiles.md`、`zh/conformance/conformance-vectors.md` 的散文合并尚待完成（见 §11.2）；operation / profile 已进 registry、openapi、bindings 与 `conformance-profiles.json`。

### 9.1 Artifact 改动

- `contract-catalog.json`（source of truth）增加两个 operation 与一个 capability action；`operation-registry.json` / `capability-action-registry.json` 由 `tools/artifact_pipeline.py generate` 生成，**MUST NOT 手改生成产物**（否则 `artifact_pipeline.py check` 报 drift）。
  - `operation_registry`：`ck.self.agent.participation.set` / `ck.self.agent.participation.get`。
  - `capability_action_registry`：仅 `ck.self.agent.participation.set`（Realm / Circle / Flow ceiling 复用 `ck.realm.admin` / `ck.circle.manage` / `ck.flow.admin`，不新增 action）。
- `account-data-type-registry.json`：`ck.agent.participation.v1`，key pattern `ck.agent.participation.v1:<agent_principal_id>:<scope_key>`，`encrypted_at_rest=true`。
- `realm.schema.json` / `circle.schema.json` / `flow.schema.json`：分别增加 `agent_participation`（Realm policy component 为 `{ native_agent: { … } }`；Circle / Flow object 为扁平三位）。
- `agent-operations.schema.json`：`ck.self.agent.participation.{set,get}` 的 request / response `$defs`（`agent_participation`、`agent_participation_scope`、`agent_participation_set_request_body`、`agent_participation_entry`、`agent_participation_outcome`）。
- `profiles/conformance-profiles.json`：注册新 profile。
- ⏳ session `scope_details.participation[]` overlay（§7.1）尚未落入 schema（待补，见 §11.2）。

## 10. 设计理由

### 10.1 为什么复用 ceiling-floor 框架而不是新建权限模型

Cokret 的加密 floor 已经是一条"内层只能收紧"的单调链（circle.md §7）。agent 参与上限在语义上完全同构（governance 设上限、内层不得放宽），复用同一 reducer 校验框架能避免引入第二套继承语义，也让"内层不得大于外层"的不变量与现有 floor 共享 conformance 思路。

### 10.2 为什么 selection 物化为既有 grant 而非新建 enforcement

CKP-0008 已经规定 agent 的 `ck.message.create` 必须被 capability grant 授权。若再为 `reply` 增加一条独立判定，会出现双源。把 selection 物化为 grant，使 reply 的 enforcement 完全落在既有 capability 校验上，selection 只是该 grant 的 controller-friendly 前端。

### 10.3 为什么 `accept_third_party_mention` 不物化为 grant

mention 接受是 **inbound 路由** 决策（"要不要把别人的 @ 推给我的 agent"），不是 agent 的 **outbound 能力**。capability grant 模型描述主体能做什么，不描述"谁能触达该主体"。因此它落在 dispatcher 的 fanout gate 上，与 `level=muted` / blocklist 同层，而不是 grant。

### 10.4 为什么同时下发给 runtime 又在服务端强制

纯服务端强制能保证安全，但 runtime 会反复尝试被拒的写入、浪费 quota、产生噪声 audit。纯 runtime 自律不安全。两者结合：服务端是硬边界，runtime 契约让 agent 安静地按预期工作。

## 11. 开放问题

### 11.1 已决记录

- [x] 参与策略三位：`reply` / `accept_third_party_mention` / `act_on_behalf`，正交布尔，默认全 `false`。
- [x] 四级 ceiling（deployment ⊇ Realm ⊇ Circle ⊇ Flow），tighten-only，复用 floor 校验框架。
- [x] selection 存 controller-owned `ck.agent.participation.v1` account-data，物化为既有 grant + dispatcher gate，不新增 enforcement 栈。
- [x] 第三方 mention 投递作为 dispatcher fanout gate（§6），controller 自己的 mention 不受此 gate。
- [x] runtime 通过 session `scope_details.participation` + `participation.get` 获得 resolved 契约；服务端权威。

### 11.2 仍需讨论

尚待完成的散文 / schema 合并（registry / openapi / bindings / schema artifacts 已落地，以下为人读 normative 散文与 schema overlay 的缺口）：

- [ ] `zh/sync/service-surface.md` §10.1：补 `ck.self.agent.participation.{set,get}` 两个 operation 的散文条目与 session `scope_details.participation` overlay 说明。
- [ ] `zh/conformance/conformance-profiles.md`：补 `ck.profile.agent_participation_policy.v1` 的散文注册（artifact `conformance-profiles.json` 已注册）。
- [ ] `zh/conformance/conformance-vectors.md`：补 ceiling tighten-only、effective=ceiling∩selection、第三方 mention gate、selection-within-ceiling、session overlay 五个 feature 的 conformance vector。
- [ ] session `scope_details.participation[]` overlay（§7.1）的 schema 落点：其形态 SHOULD 与 `agent-operations.schema.json#/$defs/agent_participation_entry`（`{scope, selection, ceiling, effective}`）对齐，而非 §7.1 当前示例的扁平形态——两处需统一后再落 schema。

## 12. 引用

- CKP-0007 Circle primitive：`spec/v1/proposals/0007-circle-primitive.md`。
- CKP-0008 Personal Agent Provisioning：`spec/v1/proposals/0008-personal-agent-provisioning.md`。
- CKP-0009 Agent Sidecar Thread：`spec/v1/proposals/0009-agent-sidecar-thread.md`。
- Mention fanout：`spec/v1/zh/models/flow-and-message.md` §9.4。
- Encryption floor tighten-only：`spec/v1/zh/models/circle.md` §7。
