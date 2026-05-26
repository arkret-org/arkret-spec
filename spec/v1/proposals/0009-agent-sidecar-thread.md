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

> **Coupled-accept dependency**: 本提案直接引用 CXP-0008 §4.5/§4.6/§4.10 的 wire 形态(`cx.agent.key.authorize` payload、`agent_key_proof` proof_kind、Event Envelope 的 signed `executed_by`/`authorization_ref` 字段、`cx.agent.draft.v1` 命名空间)。CXP-0008 在 review 阶段对这些字段的任何修改 MUST 在本提案同步,二者 SHOULD lockstep 推进 `draft → review → accepted`。

## 1. 概要

本提案定义 `cx.profile.agent_sidecar_thread.v1`:controller 可以从某个 Flow、Message、track 或 cursor 位置开启一个只对自己和自己在当前 Realm 内的 native AI agents 可见的私有上下文线程。

Sidecar thread 不在目标 Flow 内创建隐藏消息。它用一个 private Circle + private Flow 承载私聊历史,再用 private Relation 锚定到目标上下文。目标 Flow 成员默认看不到 sidecar 的存在、内容、活动节奏或通知。

v1 采用固定的 controller-Realm agent Circle:同一个 `(realm_id, controller_principal_id)` 在本 profile 下有且仅有一个 user-agent sidecar Circle。该 Circle 包含 controller 与该 controller 在当前 Realm 内所有 eligible native personal agents;不同上下文的 sidecar private Flows 复用这一个 Circle。

客户端 MAY 把 sidecar 投影成 controller-local personal track / tab。这个 personal track 只是本地或 controller-private projection,不是目标 Flow `tracks` map 的成员,不改变目标 Flow 的 canonical metadata 或 access model。

## 2. 动机

CXP-0008 解决"个人 AI agent 如何创建、认证、授权和运行"。但它没有解决一个独立产品需求:

> 用户在某个 Flow / Message 上想问自己的 AI assistant:"帮我分析这段讨论,先不要发到 Flow 里。"

现有 primitive 只能部分表达:

- `account_data` / `actor_private_event` 适合保存 draft、pending request、cursor 和偏好,不适合承载多 principal 的可回复、可通知、可恢复对话历史。
- `to-device` 适合设备工作流和点对点投递,不适合作为 durable collaboration history。
- Flow 的 track 不是 access 域。当前 normative spec 明确 Flow 永远只有一个 effective encryption scope;需要"宽公开上下文 + 窄私密讨论"时应使用两个 Flow + Relation。
- Circle 已提供 Realm 内密码学子边界,是表达 controller-agent 私聊的正确底座。

因此本提案把 sidecar 设计成一个标准 profile,而不是在目标 Flow 内增加 per-message ACL 或 hidden thread。

产品上仍可把 sidecar 呈现为"我的 AI track"。关键区别是:该 track-like entry 来自 controller-private index 与 sidecar private Flow,不是目标 Flow 的 canonical track。

## 3. 设计不变量

1. **目标 Flow 内没有隐藏消息**:sidecar 内容不写入目标 Flow 的 `discussion`、`synthesis` 或任何 track。
2. **默认保护存在性隐私**:目标 Flow 成员默认不能推断 sidecar 是否存在。
3. **上下文引用不是 capability**:`context_ref` 只说明 sidecar 从哪里被打开,不授予 agent 读取目标 Flow / Message / Relation 的权利。
4. **Sidecar 属于目标 Realm**:sidecar Circle、private Flow 与 private Relation MUST 创建在目标上下文所在 Realm,不引入额外 Realm fallback。
5. **独立 E2EE scope**:sidecar 使用自己的 Circle MLS group。不得从目标 Flow / Realm 的 MLS key 派生 sidecar key,也不得反向继承目标 Flow history key。
6. **内容转入必须显式**:把目标内容带入 sidecar 是一次显式披露。默认只引用上下文,不复制目标 message body。
7. **发布必须显式**:sidecar 中的内容只有通过新的 shared event 才能进入目标 Flow。
8. **Controller accountability**:sidecar 只能为 controller 自己 accountable 的 native agent 创建;Applet Ghost Actor 不走本 profile。
9. **每个 controller-Realm 一个 sidecar Circle(v1 取舍)**:本 profile 不按 agent、participant set 或 context 创建多个 sidecar Circle。这是有意的 v1 取舍——把 Circle / Flow reuse 简化为可枚举的两个常量,代价是 controller 在该 Realm 内激活新 native agent 即获得该 controller 所有 sidecar Flow 历史(MLS join 之后)的访问权;agent 选择只影响消息路由 / UI 呈现,不是密码学可见性边界。需要 per-context 或 per-agent 隔离的产品形态必须由独立 profile 表达,不在本 CXP 范围。
10. **新 agent eligibility 是 high-trust 动作**:当 controller 在已存在 sidecar Circle 的 Realm 内激活(active 状态)一个新 native personal agent 时,客户端 UI MUST 在该 agent 激活流程中向 controller 显式披露 "该 agent 将自动获得你现有 AI sidecar 私聊的访问权"(以及涉及的 Realm 列表 / sidecar 数量)。该披露是 invariant 9 的 UX 配套;不实现该披露的客户端不符合本 profile。具体 wire 路径见 CXP-0008 §4.5 pairing approval 流程。

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
POST /api/v1/agent-sidecar-threads:ensure
operation_id: cx.agent.sidecar_thread.ensure
profile: cx.profile.agent_sidecar_thread.v1
```

该 operation 是幂等编排入口。它创建或复用一条 controller-context sidecar thread,并返回 private Circle / Flow / Relation 的 typed IDs。实现 MAY 提供 `POST /api/v1/agents/{agent_principal_id}/sidecar-threads:ensure` 作为单 agent 快捷 binding,但 canonical operation 语义由 `controller_principal_id`、`context_ref` 与 fixed controller-Realm sidecar Circle 决定。

请求:

```json
{
  "controller_principal_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:users.example:alice",
  "addressed_agent_principal_ids": [
    "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
    "did:webvh:QmYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x:users.example:agents:research-assistant"
  ],
  "context_ref": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "flow_id": "cx:flow:01970000-0000-7000-8000-000000000001",
    "track": "discussion",
    "message_id": "cx:message:01970000-0000-7000-8000-000000000071"
  }
}
```

`context_ref` 是本 profile 定义的 polymorphic reference descriptor:它可以锚定 Flow、Message、Relation 或 profile-defined cursor 位置,不是单一具体 object id,所以使用 `_ref` 后缀。descriptor 内部字段仍按自身 value category 命名:`realm_id` / `flow_id` / `message_id` / `relation_id` 是具体 object IDs;`track` 是 FlowTrack key;若未来加入 cursor,字段名应使用 `cursor`,值为 `cx:cursor:<base64url>`。

`context_ref.realm_id` REQUIRED。`context_ref` MUST 解析到唯一 target endpoint:要么 `relation_id`,要么 `flow_id` 加可选 `track` 并可选一个 terminal anchor(`message_id` 或 future `cursor`),要么 bare `flow_id`。若携带 `message_id`,该 Message MUST 属于 `flow_id`;`track` 只是上下文定位 / audit hint,不是独立 access scope。`normalized_context_ref` 是校验通过后的 `context_ref` canonical JSON form,用于幂等复用 key,不得包含未注册字段。

`ensure` request 不携带目标内容复制字段。默认不复制目标 message body;任何 target content transfer 都必须通过后续显式、单独授权的 sidecar action 表达(见 §4.10)。

v1 `cx.agent.sidecar_thread.ensure` request schema 是 closed schema。除已注册 extension profile 明确声明的扩展字段外,实现 MUST reject unknown top-level fields,避免 caller 通过未定义字段暗示新的 reuse、visibility 或 content-transfer 语义。

响应:

```json
{
  "ok": true,
  "private_circle_id": "cx:circle:01970000-0000-7000-8000-000000000080",
  "private_flow_id": "cx:flow:01970000-0000-7000-8000-000000000081",
  "private_relation_id": "cx:relation:01970000-0000-7000-8000-000000000082",
  "pending_member_reconciliation": [
    {
      "agent_principal_id": "did:webvh:QmYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x:users.example:agents:research-assistant",
      "reason": "missing_mls_keypackage"
    }
  ]
}
```

Response 遵循 [`api-conventions.md` §4](../zh/sync/api-conventions.md#4-标准响应-envelope) 的简单 idempotent mutation 形态:`ok=true` 表示 ensure 成功。是否本次新建 Circle / Flow / Relation 不是协议真源;调用方只应使用返回的 typed IDs。

`pending_member_reconciliation[]` 是可选字段,出现时列出 §4.5.0 表中处于 "pending join" 状态的 eligible agents(典型 reason: `missing_mls_keypackage`)。该字段不出现等价于"所有 eligible agents 都已 active member"。客户端可以据此向 controller 展示 "等待 agent runtime 上线" 的 UI 提示;但 access-control 判定不依赖该字段——它只是 observability hint,不是 grant 形态。

Sidecar 所属 Realm 是 `context_ref.realm_id` 的派生结果;`ensure` response MUST NOT 再提供 `sidecar_realm_id` 或 `effective_scope` 作为第二真源。若客户端需要展示或校验 scope,使用 request 中的 `context_ref.realm_id` 与 response 中的 `private_circle_id` 派生 `{kind:"circle", realm_id: context_ref.realm_id, circle_id: private_circle_id}`,或读取 private Flow materialized object 上的 reducer-stamped `effective_scope`。

Sidecar thread 由 `private_flow_id`(承载 thread history 的 Flow)和 `private_relation_id`(把 private Flow 锚定回目标上下文的 Relation)共同物化;它本身是 profile-level projection concept,没有独立 typed object id。幂等复用 key 是 `(controller_principal_id, normalized_context_ref)`,controller-private projection 的 stable identity SHOULD 使用 `private_flow_id`。

#### 4.2.1 并发 ensure 的幂等性(normative)

`cx.agent.sidecar_thread.ensure` 是 idempotent operation。Reducer / service layer MUST 在两个层面 enforce idempotency:

- **Sidecar Circle**:以 `(realm_id, controller_principal_id)` 为唯一性 key。并发 `cx.circle.create` 路径(本 profile 触发的)MUST 收敛到单一 Circle;后到的 create 路径 MUST 解析为既有 `circle_id`,而**不是**返回 `failed_precondition` 或重复创建。实现层可以通过 `controller_agent_circle_key` lookup index、reducer-level unique constraint 或 controller principal sequencer 实现该收敛——具体路径由 implementation 选择,但可观察行为必须等同于 strict idempotency。
- **Sidecar private Flow**:以 `(controller_principal_id, normalized_context_ref)` 为唯一性 key。并发 `cx.flow.create` 路径 MUST 收敛到单一 Flow;Relation 同理(`(realm_id, relation_kind="agent_sidecar_of", from_ref=private_flow_id, to_ref)` 已经是 relation registry 默认去重 key)。

`ensure` 在两个 reducer 路径上都返回 idempotent success 时,即使没有任何新 durable event 写入,response 仍 `ok=true` 并返回既有 typed IDs。客户端不应依赖响应区分 "本次创建" vs "本次复用"。

幂等性失败的诊断信号(如 reducer 因 race 而 deadlock 或 conflict)MUST 通过 retry 收敛,不应升级为 caller 可见的 `failed_precondition`,以免客户端误以为是 capability / policy 拒绝。

### 4.3 创建时机与复用粒度

Sidecar private Flow SHOULD lazy-create。controller-Realm sidecar Circle 也 SHOULD lazy-create:第一次 `cx.agent.sidecar_thread.ensure` 需要该 `(realm_id, controller_principal_id)` 的 agent sidecar scope 时创建或复用,并同时 reconcile eligible agent membership。实现不应在用户打开目标 Flow、创建 agent、加入 Realm 或生成普通 draft 时预先为每个 Flow / agent 创建 private Flow 或 sidecar Circle。

推荐创建触发点:

- controller 在目标 Flow / Message 上显式打开 "Ask AI" / "My AI" / sidecar UI。
- controller 选择某个 agent 并发送第一条 sidecar message。
- agent 需要围绕目标上下文发起多轮私有对话,并通过 CXP-0008 的 structured approval request 获得 controller 批准。
- controller 把 one-shot draft 升级为可持续 sidecar conversation。

不推荐创建触发点:

- 只打开目标 Flow 页面。
- 只拥有某个 agent。
- 只存在 `draft_only` account-data 草稿。
- 只因为 agent 有 read permission 或 watch 了某个 Flow。

默认 Flow 复用粒度是 `same_controller_context`:一个 private Flow 对应一个 `(controller_principal_id, normalized_context_ref)`。这更符合产品体验:用户在某个 Flow / Message 上打开一个 "My AI" 私有上下文,可以在同一个 sidecar 中让多个 agents 协作。

默认 Circle 复用粒度固定为 `per_realm_controller_agent_pool`:同一个 `(realm_id, controller_principal_id)` 在本 profile 下复用同一个 sidecar Circle。这个 Circle 承载该 controller 在该 Realm 内所有 sidecar private Flows。

这两个复用策略是 v1 profile constants,不作为 request 字段暴露;§4.2 的 closed schema 已经拒绝任何未注册顶层字段。需要其它复用模型的产品形态必须由独立 profile / CXP 定义。

若用户有多个 AI agents,默认行为 SHOULD 是:

- 同一 Flow / Message 上下文默认复用同一个 sidecar private Flow。
- controller 在请求中的 `addressed_agent_principal_ids[]` 只表示本轮对话要提示、通知或期望响应的 agents;它不是访问控制边界。
- 该 controller 在当前 Realm 内所有 eligible native personal agents 都是同一个 sidecar Circle 的 members,因此原则上能读取该 Circle scope 下 join epoch 之后的所有 sidecar private Flow 内容。
- UI SHOULD 把该 sidecar 呈现为一个 "My AI" personal track projection,内部可以显示本轮 addressed agents,但不得暗示未 addressed 的 eligible agents 被密码学隔离。

`addressed_agent_principal_ids[]` 是 **per-ensure ephemeral list**:服务端 MUST NOT 把它持久化为 sidecar Circle 状态、sidecar Flow metadata 或 sidecar private Relation `fields`。它的唯一服务端语义是本次 ensure 触发的 notification fanout target(即对哪些 agents 发出 "你被 controller 点名" 信号);超出该作用域不影响任何 durable state。Controller-private projection(§4.13)可以自行跟踪 addressed history 作为 UI hint,但那是 controller-side 的 account-data,不是 sidecar 自身状态。Subsequent ensure 提供不同的 addressed list 时,服务端只按新 list 做 routing,不与历史 list 合并、累积或对比。

当新的 eligible agent 加入 controller-Realm sidecar Circle 时,它默认只能获得加入后 future epoch 的 sidecar 内容。历史内容是否回填必须由 controller 显式批准,且受 target content transfer 与 E2EE history policy 约束。

### 4.4 Realm 归属

Sidecar 不引入独立归属 Realm。对于 Flow / Message / Relation / track / cursor 上下文,sidecar 所属 Realm MUST 等于 `context_ref.realm_id`。因此 private Circle 的父 Realm、private Flow 的 `realm_id`、private Relation 的 `realm_id`、retention / audit / federation delivery surface 都是目标上下文所在 Realm。

该规则依赖 CXP-0007 的现有能力:只要 private Flow 的 `scope_circle_id` 指向 user-agent sidecar Circle,非 Circle 成员就不能收到该 Flow 的 events envelope / payload,也不应看到该 Flow 的存在、活动节奏、watcher 列表、private Relation 或 notification。换言之,"当前 Realm 内的私有 Circle + private Flow"已经足以表达"我的 AI 私聊",不需要把它移动到另一个 Realm。

`cx.agent.sidecar_thread.ensure` MUST fail closed,除非以下 Realm-local 条件全部成立:

- `context_ref.realm_id` 可解析且与目标 Flow / Message / Relation 所在 Realm 一致。
- controller 是该 Realm active member。
- 所有 eligible sidecar agents 都是该 Realm active member;profile 不创建隐藏 Realm member。
- Realm policy 允许该 controller 创建或复用 user-agent sidecar Circle。
- Circle membership 满足 `Circle.members ⊆ Realm.members`。

Sidecar profile MUST NOT 创建隐藏 Realm member 来绕过 Circle membership 不变量。跨 Realm personal assistant、controller private workspace 或全局 AI inbox 是独立产品形态,不属于本 CXP 的默认路径;若未来需要,应由单独 profile / CXP 定义,不得作为本 operation 的 fallback。

### 4.5 Circle 粒度

在本 Realm 模型下,一个 controller 在当前 Realm 内拥有一个专门的 user-agent sidecar Circle,用于承载该 controller 与自己所有 eligible agents 的 private sidecar Flows。这个模型简单,也避免引入额外私有 Realm。

关键约束是:Circle 是密码学可见性边界。如果多个 private Flows 复用同一个 Circle,则该 Circle 的所有成员原则上处在同一 MLS group 中。只要某 agent 是该 Circle member,它就应被视为能访问该 Circle scope 下 join epoch 之后的 sidecar private Flows。`addressed_agent_principal_ids[]` 只能影响消息路由、通知和 UI 展示,不能收窄可见性。

推荐默认:

- 在目标 Realm 中,按 `(realm_id, controller_principal_id)` 创建或复用 user-agent sidecar Circle。
- 同一个 Circle MUST 承载该 controller 在该 Realm 内所有 sidecar private Flows。
- 该 Circle 的成员是 controller + 当前 Realm 内所有 eligible sidecar agents。
- 同一个 Flow / Message 上的多个 agents 共用一个 private Flow 与这个 Circle;不同 Flow / Message 上下文也复用同一个 Circle。

`eligible_sidecar_agent(realm, controller, agent)` 当且仅当以下条件全部成立:

1. `agent` 是 native personal agent principal,不是 Applet Ghost Actor。
2. `agent` 通过 active `cx.identity.accountability_grant` accountable to `controller`。
3. `controller` 与 `agent` 都是该 Realm active member。
4. `agent`、agent key authorization 与运行时状态均 active,未 paused、deactivated、revoked 或 pairing expired。`pairing_expired` 是 CXP-0008 §4.3.1 定义的 provisioning-specific 状态投影,不一定出现在 Actor Profile.status 上;实现 MUST 同时查询 provisioning service 状态,不得仅凭 Actor Profile.status=`active` 即判定 eligibility,否则未完成 pairing 的 agent 会被错算为 eligible。
5. Realm policy 允许该 controller 的 personal agents 参与 `cx.profile.agent_sidecar_thread.v1`。

Sidecar Circle 的 active membership MUST 收敛为:

```text
{controller_principal_id} ∪ {agent | eligible_sidecar_agent(realm_id, controller_principal_id, agent)}
```

实现不得把未 eligible 的 agent 静默加入该 Circle,也不得把 eligible agent 仅因本轮未 addressed 而排除出该 Circle。

#### 4.5.0 Eligibility 与 MLS membership 的三态(normative)

`eligible_sidecar_agent` 是 access-control 判定,与 agent 是否实际进入 MLS group 解耦。三种状态:

| Eligibility | MLS member 状态 | 含义 | `ensure` 行为 |
| --- | --- | --- | --- |
| `eligible` + 有可用 KeyPackage | active member | 已加入 sidecar Circle MLS group | normal;ensure 直接使用既有 membership |
| `eligible` + 无可用 KeyPackage(runtime 离线 / 未续 KeyPackage / Welcome 未投递) | **pending join** | 是 Circle 的 access-control member,但尚未 cryptographically 加入 MLS group | ensure SHOULD succeed;membership async reconcile;response 通过 `pending_member_reconciliation[]` 标记该 agent |
| `not eligible`(condition 1–5 任一不成立) | not member | 不是 Circle member | ensure MUST 不把它加入 Circle;若 caller 在 `addressed_agent_principal_ids[]` 中 address 该 agent,ensure MUST `failed_precondition`(`reason="addressed_agent_not_eligible"`) |

"pending join" 是临时状态,不是长期访问边界。Eligible 但暂时无 KeyPackage 的 agent 仍然算 sidecar Circle 的 access-control member——它一旦发布新 KeyPackage,服务端 MUST 异步把它加入 MLS group(下一次 epoch commit 或专门的 reconciliation 任务),不需要 controller 重新批准。

实现不得把 "pending join" 错误地呈现为"未获访问权";Controller UI 在 sidecar 成员列表中 SHOULD 显示这类 agent 为 "pending(waiting for runtime)"。

#### 4.5.1 `controller_agent_circle_key` 派生(normative)

`controller_agent_circle_key` MUST 是 `(realm_id, controller_principal_id)` 的确定性 profile-local key,具体规则:

1. **Canonical realm_id**:按 typed prefix 解析得到 `cx:realm:<uuid>`,uuid 部分按 RFC 4122 lowercase hex 形式归一(去除任意空白)。无法解析为 typed prefix 时 fail closed。
2. **Canonical controller_principal_id**:按 [W3C DID Core](https://www.w3.org/TR/did-core/) 解析,移除 fragment(`#...`)与 query(`?...`),只保留 `did:<method>:<method-specific-id>` 部分;method-specific-id 内部不做大小写归一(method 自身定义其大小写敏感性)。无法解析为合法 DID URI 时 fail closed。
3. 对两个 canonical 字符串做 Unicode NFC normalize。
4. 以 UTF-8 编码以下 canonical string(分隔符是单个 0x0A 字节;不允许 CRLF):

   ```text
   cx.agent_sidecar_circle.v1\n<canonical_realm_id>\n<canonical_controller_principal_id>
   ```

5. `controller_agent_circle_key = base32(sha256(canonical_bytes))[:24].lower()`(base32 alphabet 按 RFC 4648 §6 标准表,去除 padding,结果转 lowercase)。

该 key 是 profile-local 派生值,不是 canonical object id。实际 Circle 仍使用 `cx:circle:<uuid>`;派生值只用于 deterministic short name、idempotent lookup 与 conformance fixture。

不同客户端实现 MUST 对相同 `(realm_id, controller_principal_id)` 输入得到 bit-identical `controller_agent_circle_key`;否则 sidecar Circle 双源——不同设备会创建两个 Circle,破坏 invariant 9。Conformance vector 至少覆盖一组 mixed-case / fragment-bearing DID 输入,保证派生函数收敛。

#### 4.5.2 Circle 与 sidecar private Flow 的关系(normative)

二者使用不同的 reuse key,关系为一对多:

| 实体 | Reuse key | 创建 / 复用粒度 |
| --- | --- | --- |
| Sidecar user-agent Circle | `(realm_id, controller_principal_id)` | 同一 controller 在同一 Realm 中复用唯一 sidecar Circle |
| Sidecar private Flow | `(controller_principal_id, normalized_context_ref)` | 同一 (controller, context) 复用一个 Flow,Flow `scope_circle_id` 指向上面那个 Circle |

例:Alice 在 Realm 内有 eligible agents `{S, R}`,她在 Flow F1 的 message M1 与 Flow F2 的 message M2 分别打开 sidecar。结果:

- 一个 Circle `C_{A}`(由 `(realm, Alice)` 派生),成员为 Alice + `{S, R}`。
- 两个 sidecar private Flow `F'_{A,F1,M1}` 与 `F'_{A,F2,M2}`,二者 `scope_circle_id = C_A`。
- 两条 sidecar private Relation `agent_sidecar_of`,分别从 `F'_{A,F1,M1}` 指向 M1、从 `F'_{A,F2,M2}` 指向 M2,`scope_circle_id` 同样指向 `C_A`。

高敏感上下文若不想让某些 agent 看到对话内容,本 profile 内的唯一手段是 controller 选择不创建 sidecar(改用 `draft_only` / one-shot approval 流程),或先把不期望看到该对话的 agent deactivate。实现 MUST NOT 在本 profile 下为单个 sidecar 偷偷创建第二个 Circle 以绕开 invariant 9。

#### 4.5.3 历史 backfill 的密码学边界(normative)

MLS 协议本身不允许向新成员转移过去 epoch 的 group secrets。把一个新 eligible agent 加入 controller-Realm sidecar Circle 时:

- 新 agent **MUST NOT** 获得 MLS 历史 epoch 密钥;它只能解密 join 之后该 Circle scope 下所有 sidecar private Flows 的 future epoch payload。
- 若 controller 显式同意把 sidecar history backfill 给该 agent,实现 MUST 通过 application-level message resend 完成(controller 设备解密历史 plaintext,在新 epoch 下重新加密发送),不得通过共享 MLS exporter secret、past commit secret 或等价手段。
- 该 backfill 是显式 plaintext 披露动作,与 §4.10 "目标内容转入" 接受同等的 capability、approval 与 audit 约束。
- 实现 MUST NOT 把 "backfill 给新成员" 实现为静默后台 sync,该动作 SHOULD 在 UI 上显式向 controller 呈现并要求确认。

### 4.6 组合 durable objects

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
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "circle_id": "cx:circle:01970000-0000-7000-8000-000000000080",
    "title": "Agent sidecar",
    "display": {
      "short_name": "AI-A4F2N1QZ8K9M",
      "color_token": "teal",
      "symbol": {"glyph": "lock"}
    },
    "directory_visibility": "members",
    "join_rule": "invite",
    "history_visibility": "joined",
    "metadata_encryption_floor": "full_encrypted",
    "encryption_profile": "mls_rfc9420"
  }
}
```

`display.short_name` MUST 由 sidecar profile 派生,不接受 caller 提供任意字符串。派生规则:

```text
short_name = "AI-" + controller_agent_circle_key[:12].upper()
```

(`controller_agent_circle_key` 已是 §4.5.1 派生的小写 base32 字符串;取前 12 字符并大写得到 12-char 后缀,合计 15 字符,在 [`circle.md` §4](spec/v1/zh/models/circle.md) 的 24 字符上限内。)

理由:[`circle.md` §4](spec/v1/zh/models/circle.md) 在 `(realm_id, short_name)` 上有 reducer-enforced 唯一性约束。按 `(realm_id, controller_principal_id)` 派生既保证同一 controller-Realm sidecar Circle 可以稳定复用,又避免不同 controller 的 sidecar Circle 使用硬编码 short name 造成碰撞。

存在性侧信道防护:`directory_visibility=members` 已要求 non-member 不可见 Circle metadata,但 reducer 的唯一性校验仍是侧信道。本 profile 要求:

- reducer 在 sidecar Circle 创建路径上,若检测到 `(realm_id, short_name)` 碰撞**且**调用方不是已有 Circle 的 member,MUST 返回与 "Realm policy 拒绝" 同款 generic `failed_precondition`(`reason="sidecar_create_denied"`),不得返回 `short_name_already_taken` 这类可区分错误。
- 同一 controller 在同一 Realm 重复 ensure 时,returning member 的请求 idempotently 解析为既有 Circle,不触发唯一性错误路径。
- 上述规则只适用于 sidecar profile;一般 `cx.circle.create` 的唯一性错误语义不变。

默认成员为:

- controller principal / controller authorized devices;
- 该 controller 在当前 Realm 内所有 eligible native personal agent principal,以及其通过 CXP-0008 key pairing 接受的 runtime device 或 workload identity。

添加任何其他成员不属于本 profile。实现 MUST NOT 把其它 human actor、非 accountable agent、Applet Ghost Actor 或外部 service principal 加入 controller-Realm sidecar Circle;需要这类多人私密协作时应使用普通 Circle / Flow profile,不是 agent sidecar profile。

私有 Flow:

```json
{
  "kind": "cx.flow.create",
  "payload": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "flow_id": "cx:flow:01970000-0000-7000-8000-000000000081",
    "title": "Agent sidecar",
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

`tracks.discussion.profile="agent_sidecar"` 只是 FlowTrack 的 semantic hint,不创建独立权限、成员或 E2EE scope。读取 / 写入仍由 Flow `scope_circle_id`、`allowed_tracks` 与 sidecar capability policy 决定。

私有 Relation:

```json
{
  "kind": "cx.relation.create",
  "payload": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "relation_id": "cx:relation:01970000-0000-7000-8000-000000000082",
    "relation_kind": "agent_sidecar_of",
    "from_ref": "cx:flow:01970000-0000-7000-8000-000000000081",
    "to_ref": "cx:message:01970000-0000-7000-8000-000000000071",
    "fields": {
      "context_track": "discussion"
    },
    "scope_circle_id": "cx:circle:01970000-0000-7000-8000-000000000080"
  }
}
```

`to_ref` 可以是目标 Flow、Message 或 Relation;若 `context_ref` 包含 `relation_id`,则 `to_ref` 指向该 Relation;若包含 `message_id`,则 `to_ref` 指向该 Message;若只给出 `flow_id`,则 `to_ref` 指向该 Flow。`fields.context_track` 是 sidecar-local audit hint。

不在 `fields` 中重复 `target_realm_id`:本 CXP §3.4 / §4.4 已经保证 sidecar Realm = context Realm,Relation 自身 `realm_id` 与 `to_ref` 解析出的 Realm 必然相等;重复字段只会诱导实现误把它当作跨 Realm hint。

`agent_sidecar_of` 是标准化候选 relation kind:weak-semantic、non-structural、non-cascading,from endpoint 为 sidecar Flow,to endpoint 为目标 Flow / Message / Relation。该 relation fact MUST 存在 sidecar private scope 内。实现 MUST NOT 在目标公开 Flow 写 target-side reverse relation,因为这会泄露 sidecar 存在性。

这条规则不是 0009 另造的 scope 模型,而是复用 `circle.md` §6.1 的 Relation scope invariant:Relation fact 的 `effective_scope` MUST 不宽于参与端点中最窄的 scope。Sidecar relation 显式提交 `scope_circle_id=<sidecar Circle>`,使 private sidecar members 能从 private Flow 回到目标上下文,而 non-members 不能从目标侧枚举到这条边。

### 4.7 授权校验

`cx.agent.sidecar_thread.ensure` MUST fail closed,除非以下校验全部通过:

- `controller_principal_id` 已认证,或由 fresh controller approval 表示。
- `addressed_agent_principal_ids[]` MUST NOT 包含 `controller_principal_id` 自身;违反则 `failed_precondition`(`reason="controller_in_addressed_agents"`)。Controller 自己天然是 sidecar Circle member,不需要(也不应当)出现在 routing list 中。
- `addressed_agent_principal_ids[]` 中每个 agent 都满足 `eligible_sidecar_agent(realm, controller, agent)`;不满足时 `failed_precondition`(`reason="addressed_agent_not_eligible"`),见 §4.5.0。
- controller、所有 eligible agents 与相关 agent key 均处于 active,未 suspended、未 deactivated、未 revoked。
- Realm policy 允许 native personal agents 与 agent sidecar threads。
- controller 在相关 frontier 上有权读取目标上下文。
- 创建或复用 private Circle / Flow 满足 Circle、Flow、Relation 与 E2EE policy。
- controller 与所有 eligible sidecar agents 都必须是目标 Realm active members;不得创建隐藏成员或跨 Realm fallback。
- 向 sidecar Circle 披露目标标识符必须被 policy 与 capability 覆盖;由于 private Relation 对 sidecar Circle members 可见,该披露对象是该 controller 在当前 Realm 内所有 eligible agents,不是仅本轮 addressed agents。
- 如果目标内容被复制进 sidecar,该复制必须是显式的、被单独授权的,并作为 sidecar Circle scope 下的 sidecar content 记录。

Agent runtime SHOULD NOT 只凭宽泛的 "create hidden channels" grant 调用该 operation。如果 agent 在没有既有授权的情况下发起 sidecar request,服务 SHOULD 像 CXP-0008 一样返回 structured human approval request。

### 4.8 Capability vocabulary

候选 capability actions:

| Action | 注册形态 |
| --- | --- |
| `cx.agent.sidecar_thread.ensure` | 聚合 admin action。`capability-action-registry.json` MUST 声明 `target_event_kinds=[cx.circle.create,cx.circle.member.state,cx.flow.create,cx.relation.create]`。 Controller-private projection account-data(§4.13 `cx.agent.sidecar_projection.v1`)的写入**不**纳入此 action 的 grantable set——它由 controller principal 自己对自身 account-data 的固有写权批准,与 sidecar ensure 解耦,因此 ensure caller 不需要持有任何 account-data 写 grant 也能成功。 |
| `cx.agent.sidecar_thread.read` | 若作为新 action 注册,它应映射到 service operation targets:读取 sidecar metadata 与 private Flow messages,通常编译为对 private Flow 的 `cx.events.query` / `cx.events.subscribe`。若 registry 不支持 operation target,则不注册此 action,而复用现有 read/query actions。 |
| `cx.agent.sidecar_thread.write` | Profile action;`target_event_kinds=[cx.message.create]`,resource 必须限定为 sidecar private Flow。 |
| `cx.agent.sidecar_thread.publish` | Profile action;target event kinds 由最终发布目标决定,至少包括 `cx.message.create`,并受 CXP-0008 reply-as-agent / act-on-behalf attribution 规则约束。 |

这些 action 不满足"action 名称与单一 event kind 同名"的默认规则,因此 accepted migration MUST 按 `capabilities.md` §5.0 的聚合 admin / profile action 类别显式注册 `target_event_kinds` 或 operation targets,不得由 action 字符串拆解推断。

候选 constraints:

| 需求 | Canonical / profile 表达 |
| --- | --- |
| 允许 addressed agents / controllers | Profile-specific selector fields `allowed_agent_principal_ids`、`allowed_controller_principal_ids`,或后续 actor selector vocabulary。注意它限制请求可 address 的 agents,不改变 controller-Realm sidecar Circle 的 membership 规则。 |
| 限定 context Realm | resource selector `kind="realm"` 或 context object selector,不是新 constraint。 |
| 限定 context Flow | 现有 `allowed_flow_refs`。 |
| 限定 relation kind | 现有 `relation_kind_allow=["agent_sidecar_of"]`。 |
| 限制 sidecar 数量 / agent 数量 | `quota` / resource-limit family,字段为 `max_sidecars_per_context`、`max_sidecar_flows_per_controller_realm` 等 profile extension。 |
| Circle 复用策略 | v1 profile constant `per_realm_controller_agent_pool`,由 profile 固定,不是 grant constraint。 |
| 目标内容复制策略 | Profile-specific content-transfer action / constraint;`ensure` request 不携带复制策略字段。 |
| E2EE 要求 | 复用 confidentiality / encryption constraint;sidecar profile 默认要求 MLS-backed Circle scope。 |
| retention | `retention_policy_ref` 只能收紧目标 Realm retention,不得放宽。 |

### 4.9 E2EE 与 key management

Sidecar E2EE MUST 遵守 Circle 规则:

- Sidecar Circle 拥有自己的 MLS group 与 epoch chain。
- Sidecar MLS secrets MUST NOT 从目标 Realm / Flow / Circle secrets 派生。
- 目标 Flow MLS membership 不会自动包含 sidecar membership。
- Sidecar membership 不授予目标 Flow history keys。
- Sidecar Circle MLS membership 与目标 Flow / Realm default MLS membership 独立,即使二者同属一个 Realm。
- Event AAD MUST 绑定 sidecar effective scope 与 Circle 规则要求的 immutable event context。

Agent 参与 sidecar 必须是 normal MLS member,不是 controller 的 delegated device:

- agent runtime MUST 提供绑定到 `agent_principal_id` 且受 active `cx.agent.key.authorize` 支撑的 MLS KeyPackage 或等价 device/workload key package。
- KeyPackage signing key SHOULD 与 `cx.agent.key.authorize.verification_method` 绑定,使 agent key authorization、session proof 与 MLS membership 落在同一审计链。
- sidecar 创建被接受后,通过 profile-defined delivery path 向 agent runtime 发送 MLS Welcome。
- agent key rotation SHOULD 根据 key model 触发 MLS member update 或 remove/add。
- agent revoke / pause MUST 从 controller-Realm sidecar MLS group 移除 agent,并阻止未来的 sidecar session grant。
- 移除一个 agent MUST rotate 到新 epoch;被移除 agent 不应获得该 controller-Realm sidecar Circle 下任何 private Flow 的后续消息 key。
- 由于 §4.5.2 允许同一个 sidecar Circle 承载多个 sidecar private Flow,Circle MLS group 的 epoch rotation 适用于该 Circle scope 下**所有** sidecar private Flow,**不可**只 rotate 某一个 Flow。实现若以"按 Flow 独立 rotate"模型对待,会破坏 Circle 的密码学边界假设——任何仍在 Circle 中的 member 都能解密该 Circle scope 下任一 Flow 的未来 epoch。
- Cross-Realm fan-out 是 Realm-local 的:controller deactivate / pause 一个 agent 时,该 agent 可能是该 controller 在 N 个 Realm 各自 sidecar Circle 的 member。MLS rotation MUST 在该 agent 实际所在的每个 sidecar Circle 各执行一次,但**只**在这些 Circle;controller 的其他 Realm 内 sidecar Circle(该 agent 未加入的)不应被触发。Audit projection SHOULD 把该次 deactivation 关联到所有受影响的 sidecar Circle id,便于事后追溯。

Agent 已经解密过的历史 plaintext 无法被密码学撤回。Revocation 只保护未来 epoch 与未来 sync。

### 4.10 目标内容转入 sidecar

打开 sidecar 不会复制目标内容。

允许把目标内容带入 sidecar 的方式:

1. controller client 解密后,显式 quote 或 forward 选定内容到 sidecar。
2. agent 已经被授权读取目标 Flow / Circle,并通过普通 event read 获取内容。
3. Realm policy 显式授权 plaintext-visible service 摘要或转换选定目标内容。

任何被复制的目标内容都会成为新的 sidecar content,并在 sidecar Circle 下加密,对该 controller 在当前 Realm 内所有 eligible sidecar agents 可见(受 MLS join epoch 限制)。必要时可携带 `source_ref` / digest metadata,但 source metadata MUST NOT 泄露回目标 Flow。

### 4.11 从 sidecar 发布

发布到目标 Flow 不是对 sidecar 自身的 mutation,而是在目标上下文中生成新的 shared event:

- reply-as-agent: `actor_id = agent_principal_id`;
- act-on-behalf: `actor_id = controller_principal_id`, `executed_by = agent_principal_id`,并带 `authorization_ref`。

由于同一个 sidecar Circle 中可能有多个 eligible agents,Publish 时:

- `actor_id` / `executed_by` MUST 是**实际签发 publish 的单一 agent principal**——即调用 publish capability action、提供 `agent_key_proof` 并通过 capability / approval 校验的那个 agent;不得使用 "agent group" 或多个 DID 的复合值。
- 其他 agent 对该消息的协作仅通过 sidecar private Flow 的 audit history 可见,不进入 shared event 的 envelope 或 payload。
- 若产品需要表达"两个 agent 共同生成此消息",该归因 MAY 通过 sidecar-side audit projection 或 message body 内 controller-visible attribution 完成,但 wire 层 `executed_by` 始终是单一 DID。

目标 shared event MAY 包含 opaque approval reference 或 digest。除非 controller 明确选择公开,否则 MUST NOT 泄露 sidecar `private_flow_id`、`private_circle_id`、private messages、scratchpad 或 draft history。

### 4.12 通知与发现

Sidecar notifications 只投递给 sidecar Circle members 与 authorized devices / runtimes。目标 Flow 的 notification fanout MUST NOT 提及 sidecar activity。

**Invariant**: Sidecar private Flow MUST NOT 出现在普通 Realm navigation、board/list placement、public search、public relation expansion 或目标 Flow projections 中。Controller UI MAY 使用 controller-private account data 展示本地入口,例如"AI sidecar available"。

该不变量必须由 reducer / sync projection 层强制执行,不能依赖 UI client 自觉遵守。Accepted migration MUST 选择以下二者之一并在 conformance profile 中声明所选机制:

- (a) 在 [`flow-and-message.md`](spec/v1/zh/models/flow-and-message.md) 注册 Flow 字段 `navigation_visibility="scope_only"`(或等价 enum 值),sidecar private Flow 提交时该字段必填;reducer / projection 层依据该字段过滤 Realm-wide projection。
- (b) 在本 profile 注册 sidecar-specific projection rule,把"以 sidecar Circle 为 `scope_circle_id` 的 Flow 不可进入 Realm-wide projection"作为 reducer-enforced 规则,无需 Flow 字段。

两种实现路径达成同一可观察 invariant;选择由 §7.2 Q2 决议。在该决议落定前,本 profile 不预先 lock schema 形态,但 invariant 本身是规范要求。

### 4.13 Personal track projection

实现 MAY 把 sidecar 在目标 Flow UI 中呈现为 controller-local personal track,例如:

```text
Flow F
  Discussion
  Synthesis
  My AI
    Summary Assistant
    Research Assistant
```

该呈现必须遵守以下规则:

- Personal track projection MUST NOT 修改目标 Flow 的 `tracks` map。
- Personal track projection MUST NOT 写入目标 Flow metadata、target-side Relation、watch cell、unread cell、search index 或 notification state。
- Projection 的 stable identity SHOULD 使用 `private_flow_id` 或 controller-private index key,而不是用户可见名称。
- 用户可见名称只是 controller-private display label,不要求在 Flow 内全局唯一。若同一 controller 有多个同名 sidecar,客户端用 agent name、context snippet 或创建时间 disambiguate。
- 多个 AI agent 可以呈现为多个 personal track entry,也可以呈现在同一个 grouped personal track 下;wire 层可见性由 fixed controller-Realm sidecar Circle 决定,entry 只表达 addressed / display routing。
- Projection order、collapsed state、local label、pinning 等 UI 状态 SHOULD 存在 controller-private account data 中。
- 其他 Flow 成员的 projection、search、notification、sync delta 与 public API MUST NOT 因此出现"隐藏 track 数量"、"某用户有 AI track"或"sidecar 活跃"等可枚举信号。

候选 controller-private index:

```json
{
  "type": "cx.agent.sidecar_projection.v1",
  "target": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "flow_id": "cx:flow:01970000-0000-7000-8000-000000000001"
  },
  "entries": [
    {
      "private_flow_id": "cx:flow:01970000-0000-7000-8000-000000000081",
      "addressed_agent_principal_ids": [
        "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant"
      ],
      "display_label": "My AI",
      "presentation": "track_tab",
      "rank": "a0"
    }
  ]
}
```

`cx.agent.sidecar_projection.v1` 只是候选 account-data type。Accepted 前不得把它当作 registered artifact。

若 §7.2 Q1 决议把它标准化为 controller-private account-data,key pattern 建议为:

```text
cx.agent.sidecar_projection.v1:<controller_principal_id>:<target_realm_id>:<target_flow_id>
```

理由:projection index 按 controller 属人(controller-private),按 `(target_realm_id, target_flow_id)` 做 per-Flow 投影。CXP-0008 的 `cx.agent.draft.v1` 使用 `cx.agent.draft.v1:<agent_principal_id>:<draft_id>`(agent-attributed,per-draft)。二者 key 前缀不同(`cx.agent.sidecar_projection.v1` vs `cx.agent.draft.v1`)、key 第二段语义不同(controller vs agent),不会在 `cx.agent.*` 命名空间下冲突。注册时 MUST 在 `account-data-type-registry.json` 显式声明 key pattern 与 owner principal,reducer 据此做归属校验。

## 5. 与 normative spec 的交互

可能影响的 normative 文档:

- `zh/models/circle.md`: sidecar Circle 默认值、membership constraints、MLS member lifecycle。
- `zh/models/flow-and-message.md`: sidecar Flow profile 与 navigation rules。
- `zh/models/relation.md`: 候选 `agent_sidecar_of` relation kind 与 private-scope requirement。
- `zh/models/private-objects.md` 与 `zh/sync/client-sync.md`: controller-private sidecar index / personal track projection account data。
- `zh/authz/capabilities.md`: sidecar actions 与 constraints。
- `zh/identity/key-management.md`: 将 agent runtime key / MLS member key 绑定到 sidecar participation。
- `zh/sync/service-surface.md` 与 `service-http-binding.md`: `cx.agent.sidecar_thread.ensure`。
- `zh/conformance/conformance-profiles.md`: `cx.profile.agent_sidecar_thread.v1`。

Accepted 后可能需要的 artifacts:

- `operation-registry.json`: 增加 `cx.agent.sidecar_thread.ensure`。
- `capability-action-registry.json`: 增加 sidecar actions,并按 `capabilities.md` §5.0 显式声明 aggregate action 的 `target_event_kinds` / operation targets。`cx.agent.sidecar_thread.ensure` 至少覆盖 `cx.circle.create`、`cx.circle.member.state`、`cx.flow.create`、`cx.relation.create` 与 controller-private index 写入。
- relation vocabulary / schema:若 accepted,增加 `agent_sidecar_of`。
- Flow projection / schema registry:注册 `navigation_visibility="scope_only"` 或等价 profile-enforced projection rule,保证 sidecar Flow 不进入 Realm-wide navigation。
- `account-data-type-registry.json`: 若标准化,增加 controller-private sidecar index / personal track projection key pattern。
- OpenAPI: 增加 request / response schemas。
- conformance vectors: existence privacy、no target backlink、personal track projection non-leakage、lazy creation、single controller-Realm Circle reuse、addressed-agent-not-a-boundary、E2EE separation、revocation、publish boundary。

## 6. 设计理由与替代方案

### 6.1 为什么不做目标 Flow 内的隐藏消息

当前模型有意把 Flow 设计成单一 security scope。在同一个 Flow 内增加 per-message 或 per-thread hidden access,会产生一套与 Circle 并行的第二访问模型,复杂化 reducer、sync、E2EE AAD、notification fanout 和用户预期。

### 6.2 为什么不把 account_data 当成完整私聊

Account data 是 principal-private state。它适合 one-shot draft 或 local index,但不适合承载带 reply、notification、history、E2EE epoch 与 revocation semantics 的 durable two-principal conversation。

### 6.3 为什么不用 to-device

To-device 是 delivery machinery,不是 collaboration history。它不应该成为 agent work conversation 的存储模型。

### 6.4 为什么是 Circle + private Flow

它复用了现有 security boundaries:Circle 处理 E2EE 与 membership;Flow 处理 durable discussion;Relation 处理 context anchoring。新 profile 主要标准化一个安全组合方式和产品入口。

### 6.5 为什么 personal track 是 projection,不是 Flow track

把每个用户或每个 agent 的私有轨道放进目标 Flow `tracks` map,会让 Flow 变成多安全域容器,并引入 track 命名冲突、track metadata 存在性泄露、per-track E2EE、per-track notification、per-track search 裁剪等复杂问题。

把 sidecar 投影成 personal track 可以保留用户体验,同时保持协议层干净:目标 Flow 仍是单一 scope;私聊历史仍在 private Flow;可见性由 sidecar Circle 决定;个人入口只存在 controller-private account data 中。

### 6.6 为什么默认一个上下文一个 private Flow

默认按 `(controller, context_ref)` 创建 sidecar,更符合"在这个 Flow 上打开我的 AI 私聊"的产品模型。多个 agents 可以在同一个 private Flow 里协作,并共享同一个 sidecar Circle;这对用户来说比"每个 agent 一个隐藏私聊"更容易理解。

Lazy creation 也很重要:如果用户每打开一个 Flow 就为每个 agent 预建 private Flow,会制造大量空对象,也可能在 controller-private state、sync、audit 或计费层产生不必要的存在性与活动信号。

### 6.7 为什么默认 Realm-local user-agent Circle

当用户已经把自己的 agents 加入当前 Realm,并希望这些 agents 都参与自己的 AI 私聊时,Realm-local user-agent Circle 是最简单的模型:private Flow 留在当前 Realm,治理、retention、audit 与目标上下文一致,非 Circle 成员又看不到该 private Flow 的存在或事件。

v1 选择"每个 `(realm, controller)` 一个 Circle"而不是 participant set,是为了让 Flow reuse、Circle reuse 与 MLS scope 不互相打架。代价是清晰且显式的:该 controller 在当前 Realm 内所有 eligible agents 共享同一个 sidecar 可见性圈。用户新增 eligible agent 后,该 agent 进入同一 AI 私聊可见性圈,但不会自动获得过去 MLS epoch 的历史密钥;历史 backfill 仍必须显式批准。

## 7. 开放问题

### 7.1 已决记录

- [x] Relation kind 使用 `agent_sidecar_of`,注册为 weak-semantic、non-structural、non-cascading kind。`from_ref` 为 sidecar Flow,`to_ref` 为目标 Flow / Message / Relation。
- [x] 普通用户即使没有 general `cx.circle.create`,也可以通过受限 `cx.agent.sidecar_thread.ensure` 创建 sidecar composite。该 action 只允许 controller + accountable agents、profile-enforced private Circle / Flow / Relation,不等于授予普通 Circle 创建权。
- [x] Sidecar 所属 Realm 固定为目标上下文所在 Realm;本 CXP 不引入额外 Realm 选择或跨 Realm fallback。
- [x] 默认 Flow reuse 是 `same_controller_context`:同一个 `(controller, normalized_context_ref)` 一个 sidecar private Flow。
- [x] Circle reuse 固定为 `per_realm_controller_agent_pool`:同一个 `(realm, controller)` 在本 profile 下有且仅有一个 sidecar Circle,成员为 controller + 当前 Realm 内所有 eligible native personal agents。
- [x] `addressed_agent_principal_ids[]` 只影响路由 / 通知 / UI 呈现,不是密码学可见性边界。
- [x] `context_ref` 默认对 sidecar Circle members 可见为 opaque target ID,但不复制目标内容。High-secrecy `target_ref_visible_to_agent=false` 不属于 v1 single-Circle profile。
- [x] Agent 是 normal MLS member,KeyPackage 由 active `cx.agent.key.authorize` 支撑;不是 controller delegated device。
- [x] Sidecar Flow 从普通 Realm navigation / search / board / relation expansion 隐藏是 profile-enforced rule,不是 UI recommendation。
- [x] 多 agent projection 默认 grouped 为一个 controller-local "My AI" personal track;客户端 MAY 在该 grouped track 内显示多个 agent entry。
- [x] Retention 默认继承目标 Realm。Sidecar profile MAY 通过 `retention_policy_ref` 收紧,不得放宽。

### 7.2 仍需讨论

- [ ] `cx.agent.sidecar_projection.v1` 是否必须标准化为 controller-private account-data type,还是只标准化 projection invariants 与泄露边界?
- [ ] `navigation_visibility="scope_only"` 是否作为 Flow schema 字段注册,还是以 profile-specific projection rule 表达?
- [ ] Sidecar retention 是否需要 profile-level 最小值 / 最大值,例如默认至少 30 天或 until deletion?

### 7.3 存在性隐私 conformance vectors

Accepted profile SHOULD 增加以下 conformance fixtures:

1. Subscribe/query 隔离:non-sidecar-member 对目标 Realm `cx.events.subscribe` 与 `cx.events.query` 返回 zero events referencing sidecar Circle / Flow / Relation。
2. 反向 relation 不泄露:对 `to_ref=<target_message_id>` 的 relation query,non-sidecar-member 看不到 `agent_sidecar_of` 边。
3. Directory 不可枚举:non-member 对 Realm directory 调用返回 zero hits for sidecar Circle title、display、short_name 或 member_count。
4. Notification fanout 隔离:sidecar 内 `cx.message.create` 不触发目标 Flow members 的 notification。
5. Anchor leaf 隔离:sidecar `effective_scope=circle` event 不出现在目标 Realm default anchor leaf 明文 metadata 中;只能作为 opaque commitment。
6. Revocation 闭环:`cx.agent.deactivate` 后,agent 被移出 sidecar Circle MLS group,后续 `agent_key_proof` session grant fail closed,sidecar 写入全部拒绝。

## 8. 迁移计划

草案占位。若 accepted:

1. 注册 `cx.profile.agent_sidecar_thread.v1`。
2. 增加 `cx.agent.sidecar_thread.ensure` service operation 与 OpenAPI schemas。
3. 增加 sidecar capability actions,并把 context Flow / relation kind / quota / E2EE / retention 约束映射到现有 constraint vocabulary 或 profile-specific extension。
4. 注册 `agent_sidecar_of` private relation kind。
5. 增加 `navigation_visibility="scope_only"` 或等价 projection rule。
6. 如需要,增加 controller-private sidecar index / personal track projection account-data type。
7. 增加 privacy、lazy creation、single controller-Realm Circle reuse、addressed-agent-not-a-boundary、personal track projection non-leakage、E2EE separation、revocation 与 publish boundary 的 conformance vectors。

## 9. 引用

- CXP-0007 Circle primitive: `spec/v1/proposals/0007-circle-primitive.md`。
- CXP-0008 Personal Agent Provisioning: `spec/v1/proposals/0008-personal-agent-provisioning.md`。
- Flow / Message scope rules: `spec/v1/zh/models/flow-and-message.md`。
- Circle rules: `spec/v1/zh/models/circle.md`。
- Relation rules: `spec/v1/zh/models/relation.md`。
