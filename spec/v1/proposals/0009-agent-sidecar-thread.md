---
cxp: CXP-0009
title: Agent Sidecar Thread（Agent 旁路私聊线程）
normative: false
stability: v1
updated: 2026-05-26
status: draft
created: 2026-05-26
authors:
  - chris@acroidea.com
depends_on: [CXP-0007, CXP-0008]
discussion: https://github.com/contrix-dev/contrix-spec/discussions/cxp-0009
---

## 1. 概要

本提案定义 `cx.profile.agent_sidecar_thread.v1`:controller 可以从某个 Flow、Message、track 或 cursor 位置开启一个只对自己和自己的 native AI agent 可见的私有上下文线程。

Sidecar thread 不在目标 Flow 内创建隐藏消息。它用一个 private Circle + private Flow 承载私聊历史,再用 private Relation 锚定到目标上下文。目标 Flow 成员默认看不到 sidecar 的存在、内容、活动节奏或通知。

## 2. 动机

CXP-0008 解决"个人 AI agent 如何创建、认证、授权和运行"。但它没有解决一个独立产品需求:

> 用户在某个 Flow / Message 上想问自己的 AI assistant:"帮我分析这段讨论,先不要发到 Flow 里。"

现有 primitive 只能部分表达:

- `account_data` / `actor_private_event` 适合保存 draft、pending request、cursor 和偏好,不适合承载多 principal 的可回复、可通知、可恢复对话历史。
- `to-device` 适合设备工作流和点对点投递,不适合作为 durable collaboration history。
- Flow 的 track 不是 access 域。当前 normative spec 明确 Flow 永远只有一个 effective encryption scope;需要"宽公开上下文 + 窄私密讨论"时应使用两个 Flow + Relation。
- Circle 已提供 Realm 内密码学子边界,是表达 controller-agent 私聊的正确底座。

因此本提案把 sidecar 设计成一个标准 profile,而不是在目标 Flow 内增加 per-message ACL 或 hidden thread。

## 3. 设计不变量

1. **目标 Flow 内没有隐藏消息**:sidecar 内容不写入目标 Flow 的 `discussion`、`synthesis` 或任何 track。
2. **默认保护存在性隐私**:目标 Flow 成员默认不能推断 sidecar 是否存在。
3. **上下文引用不是 capability**:`context_ref` 只说明 sidecar 从哪里被打开,不授予 agent 读取目标 Flow / Message 的权利。
4. **Sidecar home 必须显式选择**:sidecar 可以落在 controller home Realm,也可以落在目标上下文 Realm;选择本身影响 membership、retention、audit 和存在性隐私。
5. **独立 E2EE scope**:sidecar 使用自己的 Circle MLS group。不得从目标 Flow / Realm 的 MLS key 派生 sidecar key,也不得反向继承目标 Flow history key。
6. **内容转入必须显式**:把目标内容带入 sidecar 是一次显式披露。默认只引用上下文,不复制目标 message body。
7. **发布必须显式**:sidecar 中的内容只有通过新的 shared event 才能进入目标 Flow。
8. **Controller accountability**:sidecar 只能为 controller 自己 accountable 的 native agent 创建;Applet Ghost Actor 不走本 profile。

## 4. 规格草案

### 4.1 Profile 声明

```text
cx.profile.agent_sidecar_thread.v1
```

该 profile 依赖:

- CXP-0007 / Circle primitive。
- CXP-0008 / native personal agent provisioning、agent key proof、capability intersection。

### 4.2 Operation 编排入口

新增 profile operation:

```text
POST /api/v1/agents/{agent_principal_id}/sidecar-threads:ensure
operation_id: cx.agent.sidecar_thread.ensure
profile: cx.profile.agent_sidecar_thread.v1
```

该 operation 是幂等编排入口。它创建或复用一条 controller-agent sidecar thread,并返回 private Circle、private Flow 与 private Relation 的引用。

请求:

```json
{
  "controller_principal_id": "did:webvh:alice.example",
  "agent_principal_id": "did:webvh:alice.example:agents:summary-assistant",
  "context_ref": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "flow_id": "cx:flow:01970000-0000-7000-8000-000000000001",
    "track": "discussion",
    "message_id": "cx:message:01970000-0000-7000-8000-000000000071"
  },
  "reuse_policy": "same_controller_agent_context",
  "sidecar_home_policy": "controller_home_preferred",
  "metadata_policy": {
    "target_ref_visible_to_agent": true,
    "copy_target_content": "never"
  }
}
```

响应:

```json
{
  "sidecar_thread_id": "01970000-0000-7000-8000-000000000090",
  "created": true,
  "sidecar_realm_id": "cx:realm:01970000-0000-7000-8000-000000000900",
  "private_circle_id": "cx:circle:01970000-0000-7000-8000-000000000080",
  "private_flow_id": "cx:flow:01970000-0000-7000-8000-000000000081",
  "relation_ref": "cx:relation:01970000-0000-7000-8000-000000000082",
  "effective_scope": {
    "kind": "circle",
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000900",
    "circle_id": "cx:circle:01970000-0000-7000-8000-000000000080"
  }
}
```

`sidecar_thread_id` 是 operation response 内的 opaque stable id。除非 accepted migration 明确注册 `cx:agent_sidecar_thread:` typed id,它不得作为 v1 canonical object id 进入 artifact。

### 4.3 Sidecar Home Realm

Sidecar 必须显式选择 home Realm。该选择决定 Circle 的父 Realm、Flow 所属 Realm、retention policy、audit surface、federation delivery 和 agent membership 要求。

| 模式 | Sidecar home Realm | 优点 | 代价 |
| --- | --- | --- | --- |
| `controller_home` | controller 的 personal / principal-control / private workspace Realm | 不要求 agent 成为目标 Realm member;目标 Flow 默认看不到 sidecar;更符合"我的 AI 私聊" | 需要跨 Realm private Relation 指向目标上下文;目标 Realm policy 可能限制可引用性或内容复制。 |
| `context_realm` | 目标 Flow 所在 Realm | audit / retention 留在目标 Realm 管辖内;适合组织内受管 agent | Circle.members 必须是父 Realm members,因此 agent 可能需要成为目标 Realm member;这可能泄露 agent 存在或改变成员治理。 |

本提案倾向默认 `controller_home_preferred`:如果部署提供 controller home Realm,sidecar SHOULD 落在 controller home Realm;只有 Realm policy 或组织合规要求 sidecar 留在目标 Realm 时,才使用 `context_realm`。

若使用 `context_realm`,实现 MUST 先证明 agent 已是目标 Realm active member,或通过正常 Realm membership 流程加入。Sidecar profile MUST NOT 创建隐藏 Realm member 来绕过 CXP-0007 的 `Circle.members ⊆ Realm.members` 不变量。

若使用 `controller_home`,sidecar Relation 是跨 Realm weak-semantic reference。它不复制目标内容,不授予目标读权,也不在目标 Realm 写任何反向对象。

### 4.4 组合 durable objects

Accepted profile SHOULD 编排以下 durable material:

1. private Circle。
2. private Flow。
3. 从 sidecar Flow 指向目标上下文的 private Relation。
4. controller-private account-data index,用于多设备 UI 找回 sidecar。

私有 Circle:

```json
{
  "kind": "cx.circle.create",
  "payload": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000900",
    "circle_id": "cx:circle:01970000-0000-7000-8000-000000000080",
    "title": "Agent sidecar",
    "directory_visibility": "members",
    "join_rule": "invite",
    "history_visibility": "joined",
    "metadata_encryption_floor": "full_encrypted",
    "encryption_profile": "mls_rfc9420"
  }
}
```

默认成员为:

- controller principal / controller authorized devices;
- 通过 CXP-0008 key pairing 接受的 agent principal runtime device 或 workload identity。

添加任何其他成员都是 high-risk operation,MUST 要求 controller 显式批准。

私有 Flow:

```json
{
  "kind": "cx.flow.create",
  "payload": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000900",
    "flow_id": "cx:flow:01970000-0000-7000-8000-000000000081",
    "title": "Sidecar with Summary Assistant",
    "tracks": {
      "discussion": {
        "enabled": true,
        "is_primary": true,
        "profile": "agent_sidecar"
      }
    },
    "scope_circle_id": "cx:circle:01970000-0000-7000-8000-000000000080"
  }
}
```

Sidecar 消息是该 private Flow 内的普通 `cx.message.create` event。普通私聊不需要额外定义 `cx.agent.sidecar_message.create`。

私有 Relation:

```json
{
  "kind": "cx.relation.create",
  "payload": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000900",
    "relation_id": "cx:relation:01970000-0000-7000-8000-000000000082",
    "relation_kind": "agent_sidecar_of",
    "from_ref": "cx:flow:01970000-0000-7000-8000-000000000081",
    "to_ref": "cx:message:01970000-0000-7000-8000-000000000071",
    "fields": {
      "target_realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
      "context_track": "discussion"
    },
    "scope_circle_id": "cx:circle:01970000-0000-7000-8000-000000000080"
  }
}
```

`agent_sidecar_of` 是候选 weak-semantic relation kind。该 relation fact MUST 存在 sidecar private scope 内。实现 MUST NOT 在目标公开 Flow 写 target-side reverse relation,因为这会泄露 sidecar 存在性。

### 4.5 授权校验

`cx.agent.sidecar_thread.ensure` MUST fail closed,除非以下校验全部通过:

- `controller_principal_id` 已认证,或由 fresh controller approval 表示。
- `agent_principal_id` 是 accountable to controller 的 native agent principal。
- controller、agent 与 agent key 均处于 active,未 suspended、未 deactivated、未 revoked。
- Realm policy 允许 native personal agents 与 agent sidecar threads。
- controller 在相关 frontier 上有权读取目标上下文。
- 创建或复用 private Circle / Flow 满足 Circle、Flow、Relation 与 E2EE policy。
- 如果 `sidecar_home_policy` 解析为 `context_realm`,agent Realm membership 必须符合普通 Realm membership 规则。
- 如果 `sidecar_home_policy` 解析为 `controller_home`,cross-Realm reference policy 必须允许保存指向目标上下文的 opaque reference。
- 如果 `target_ref_visible_to_agent=true`,向 agent 披露目标标识符必须被 policy 与 capability 覆盖。
- 如果目标内容被复制进 sidecar,该复制必须是显式的、被单独授权的,并作为 sidecar Circle scope 下的 sidecar content 记录。

Agent runtime SHOULD NOT 只凭宽泛的 "create hidden channels" grant 调用该 operation。如果 agent 在没有既有授权的情况下发起 sidecar request,服务 SHOULD 像 CXP-0008 一样返回 structured human approval request。

### 4.6 Capability vocabulary

候选 capability actions:

| Action | 含义 |
| --- | --- |
| `cx.agent.sidecar_thread.ensure` | 为特定上下文创建或查找 controller-agent sidecar。 |
| `cx.agent.sidecar_thread.read` | 读取 sidecar metadata 与 private Flow messages。通常编译为对 private Flow 的 `cx.events.subscribe`。 |
| `cx.agent.sidecar_thread.write` | 向 sidecar private Flow 写入 `cx.message.create`。 |
| `cx.agent.sidecar_thread.publish` | 将选定 sidecar content 发布到目标 Flow,受 CXP-0008 reply-as-agent / act-on-behalf 规则约束。 |

候选 constraints:

| Constraint | 含义 |
| --- | --- |
| `allowed_agent_principal_ids` | 允许参与的 agents。 |
| `allowed_controller_principal_ids` | 允许拥有 sidecar 的 controllers。 |
| `allowed_context_realm_ids` | 允许开启 sidecar 的 context Realms。 |
| `allowed_context_flow_ids` | 更窄的目标 Flow allowlist。 |
| `allowed_sidecar_home_modes` | `controller_home`、`context_realm` 或两者。 |
| `max_sidecars_per_context` | 通常对 `(controller, agent, context_ref)` 取 `1`。 |
| `copy_target_content_policy` | `never`、`controller_explicit_selection` 或 profile-defined values。 |
| `e2ee_required` | sidecar 是否 MUST 使用 MLS-backed Circle scope。 |
| `retention_policy_ref` | sidecar history 的 retention / erasure policy。 |

### 4.7 E2EE 与 key management

Sidecar E2EE MUST 遵守 Circle 规则:

- Sidecar Circle 拥有自己的 MLS group 与 epoch chain。
- Sidecar MLS secrets MUST NOT 从目标 Realm / Flow / Circle secrets 派生。
- 目标 Flow MLS membership 不会自动包含 sidecar membership。
- Sidecar membership 不授予目标 Flow history keys。
- 如果 sidecar 落在 controller home Realm,目标 Realm MLS membership 与 sidecar MLS membership 完全分离。
- Event AAD MUST 绑定 sidecar effective scope 与 Circle 规则要求的 immutable event context。

Agent 参与 sidecar 需要一个具体的 cryptographic member:

- 推荐:agent runtime 提供绑定到 `agent_principal_id` 且受 active `cx.agent.key.authorize` 支撑的 MLS KeyPackage 或等价 device/workload key package。
- sidecar 创建被接受后,通过 profile-defined delivery path 向 agent runtime 发送 MLS Welcome。
- agent key rotation SHOULD 根据 key model 触发 MLS member update 或 remove/add。
- agent revoke / pause MUST 从 sidecar MLS group 移除 agent,并阻止未来的 sidecar session grant。

Agent 已经解密过的历史 plaintext 无法被密码学撤回。Revocation 只保护未来 epoch 与未来 sync。

### 4.8 目标内容转入 sidecar

打开 sidecar 不会复制目标内容。

允许把目标内容带入 sidecar 的方式:

1. controller client 解密后,显式 quote 或 forward 选定内容到 sidecar。
2. agent 已经被授权读取目标 Flow / Circle,并通过普通 event read 获取内容。
3. Realm policy 显式授权 plaintext-visible service 摘要或转换选定目标内容。

任何被复制的目标内容都会成为新的 sidecar content,并在 sidecar Circle 下加密。必要时可携带 `source_ref` / digest metadata,但 source metadata MUST NOT 泄露回目标 Flow。

### 4.9 从 sidecar 发布

发布到目标 Flow 不是对 sidecar 自身的 mutation,而是在目标上下文中生成新的 shared event:

- reply-as-agent: `actor_id = agent_principal_id`;
- act-on-behalf: `actor_id = controller_principal_id`, `executed_by = agent_principal_id`, with `authorization_ref`.

目标 shared event MAY 包含 opaque approval reference 或 digest。除非 controller 明确选择公开,否则 MUST NOT 泄露 sidecar private Flow id、sidecar Circle id、private messages、scratchpad 或 draft history。

### 4.10 通知与发现

Sidecar notifications 只投递给 sidecar Circle members 与 authorized devices / runtimes。目标 Flow 的 notification fanout MUST NOT 提及 sidecar activity。

Sidecar private Flow SHOULD NOT 出现在普通 Realm navigation、board/list placement、public search、public relation expansion 或目标 Flow projections 中。Controller UI MAY 使用 controller-private account data 展示本地入口,例如"AI sidecar available"。

## 5. 与 normative spec 的交互

可能影响的 normative 文档:

- `zh/models/circle.md`: sidecar Circle 默认值、membership constraints、MLS member lifecycle。
- `zh/models/flow-and-message.md`: sidecar Flow profile 与 navigation rules。
- `zh/models/relation.md`: 候选 `agent_sidecar_of` relation kind 与 private-scope requirement。
- `zh/models/private-objects.md` 与 `zh/sync/client-sync.md`: controller-private sidecar index account data。
- `zh/authz/capabilities.md`: sidecar actions 与 constraints。
- `zh/identity/key-management.md`: 将 agent runtime key / MLS member key 绑定到 sidecar participation。
- `zh/sync/service-surface.md` 与 `service-http-binding.md`: `cx.agent.sidecar_thread.ensure`。
- `zh/conformance/conformance-profiles.md`: `cx.profile.agent_sidecar_thread.v1`。

Accepted 后可能需要的 artifacts:

- `operation-registry.json`: 增加 `cx.agent.sidecar_thread.ensure`。
- `capability-action-registry.json`: 增加 sidecar actions 与 constraints。
- relation vocabulary / schema:若 accepted,增加 `agent_sidecar_of`。
- `account-data-type-registry.json`: 若标准化,增加 controller-private sidecar index key pattern。
- OpenAPI: 增加 request / response schemas。
- conformance vectors: existence privacy、no target backlink、E2EE separation、revocation、publish boundary。

## 6. 设计理由与替代方案

### 6.1 为什么不做目标 Flow 内的隐藏消息

当前模型有意把 Flow 设计成单一 security scope。在同一个 Flow 内增加 per-message 或 per-thread hidden access,会产生一套与 Circle 并行的第二访问模型,复杂化 reducer、sync、E2EE AAD、notification fanout 和用户预期。

### 6.2 为什么不把 account_data 当成完整私聊

Account data 是 principal-private state。它适合 one-shot draft 或 local index,但不适合承载带 reply、notification、history、E2EE epoch 与 revocation semantics 的 durable two-principal conversation。

### 6.3 为什么不用 to-device

To-device 是 delivery machinery,不是 collaboration history。它不应该成为 agent work conversation 的存储模型。

### 6.4 为什么是 Circle + private Flow

它复用了现有 security boundaries:Circle 处理 E2EE 与 membership;Flow 处理 durable discussion;Relation 处理 context anchoring。新 profile 主要标准化一个安全组合方式和产品入口。

## 7. 开放问题

- [ ] Relation kind 应该使用 `agent_sidecar_of`,还是带 profile fields 的 `confidential_discussion_of`,还是 generic `references`?
- [ ] 普通用户即使没有 general `cx.circle.create`,是否也应获得受限的 sidecar-create operation?
- [ ] `controller_home` 应该是必需默认值,还是仅在 deployment 提供 controller home Realm 时作为 preferred default?
- [ ] Sidecar Circle 应该按 `(controller, agent)` 复用,还是按 `(controller, agent, context_ref)` 创建?
- [ ] `context_ref` 默认是否对 agent 可见?精确 target IDs 是否需要显式披露?
- [ ] Hosted agent runtime MLS membership 应该表达为 normal device、delegated device、workload member,还是新的 agent-member profile?
- [ ] Sidecar history 的默认 retention policy 是什么?
- [ ] Sidecar Flow 应由 profile 强制从普通 Realm navigation 隐藏,还是只建议 UI projection 省略?
- [ ] 哪些 conformance vectors 能证明目标 Flow 成员不能观察 sidecar 存在性?

## 8. 迁移计划

草案占位。若 accepted:

1. 注册 `cx.profile.agent_sidecar_thread.v1`。
2. 增加 `cx.agent.sidecar_thread.ensure` service operation 与 OpenAPI schemas。
3. 增加 sidecar capability actions 与 constraints。
4. 决定并注册 private relation kind。
5. 如需要,增加 controller-private sidecar index account-data type。
6. 增加 privacy、E2EE separation、revocation 与 publish boundary 的 conformance vectors。

## 9. 引用

- CXP-0007 Circle primitive: `spec/v1/proposals/0007-circle-primitive.md`。
- CXP-0008 Personal Agent Provisioning: `spec/v1/proposals/0008-personal-agent-provisioning.md`。
- Flow / Message scope rules: `spec/v1/zh/models/flow-and-message.md`。
- Circle rules: `spec/v1/zh/models/circle.md`。
- Relation rules: `spec/v1/zh/models/relation.md`。
