---
title: Agent Workspace Profile
sidebar:
  label: Agent Workspace
---

> **状态：extension profile（非 v1 core 互操作必需）**。本文档定义 `cx.profile.agent_workspace.v1`——允许用户在源协作 Realm 中调用自己的 agent 干活，同时把"agent 透明度"（公开 mention）与"agent 工作过程"（私人 mirror Realm）分离。Contrix v1 core 互操作 **不要求** 实现 agent workspace；不实现的 client/server 通过 `cx.feature.mention_redirect.v1` critical_extension 检查自然 fail-closed。

## 1. 目标

用户经常需要在协作 Flow（工作群、项目讨论）中调用自己的 AI agent 干活，同时希望：

- **指令内容不暴露**给 Flow 其他成员（私密性）
- **agent 的存在与权限范围**对 Flow 其他成员可见（透明度 / 信任）
- agent 团队的复杂度（多个专长 agent、内部讨论、试错过程）**不污染源 Flow**
- 跨多个源 Realm 工作时有**统一入口**回到自己的 agent workspace

本 profile 提供的核心机制：

1. Agent 通过标准 `cx.member.state` 加入源 Realm，公开声明
2. 用户的 principal server 上有一个 **agent workspace root Realm**（per-controller，DID Document advertise）
3. 用户在源 Flow `@my-agent` 时，触发 mention_redirect content block 作为 source-side stub + 私密指令落到 mirror Realm 的 `agent_task` 对象
4. Agent 在 mirror Realm 工作；通过 import_attestation 把源 Realm 内容重加密到 mirror Realm 工作上下文
5. 任务完成后 controller 决定是否将 agent 产出 publish 回源 Flow

### 1.1 信任模型与适用边界

本 profile 的 v1 默认行为**针对单 controller、controller 可信 agent runtime、本地 watcher** 场景做了协议简化。在以下假设下,本 profile 的"watcher 投递有 SLA 延迟但不强制 freshness gate"是合理的设计:

| 假设 | 说明 |
| --- | --- |
| Agent 是 controller 自己的 AI | mirror Realm owner = controller principal;agent 只服务这一个 controller |
| Agent runtime 由 controller 自审 / 自托管 | runtime 代码或运行环境 controller 有控制权(自己跑 / 用熟悉的 vendor / 等价信任根) |
| Publish-back 经过 controller 显式审批 | agent 不能直接把 mirror 内容发回源 Realm;必须 controller 用自己 principal 身份转发 |
| 源 Realm 已直接强制 read access | agent 被踢出源 Realm 后,源 Realm events API 立即返回 403、MLS commit 立即不下发新 epoch 密钥给 agent;**这一层不依赖 watcher** |

在上述假设下,watcher SLA 延迟(默认 60+30s)的最坏后果是:

- Agent 多跑了一段已无意义的处理(已被踢出 / 已被 redact 的源上下文)
- Controller UI 在 watcher 通知到达之前没看到"source_authority revoked"标记
- Controller 如果没注意到自己刚踢了 agent 就批准了 agent 草稿 publish-back → 已被踢的 agent 输出仍然进入源 Realm(但 publish 用的是 controller 身份,源 Realm audit 看到的是 controller 作者)

这些后果都**可通过 controller 自己的审批与 audit 链路追溯**,不构成"未授权第三方读取私密"或"协议级权限绕过"。所以 v1 把 stale window 收紧 / 引入 freshness gate / lease 等机制视为**过度工程**,保留为 follow-up 议题(见下方"v1 不强制 freshness gate 的代价")。

**不属于 v1 本 profile 默认覆盖范围**(部署如有以下需求需自行加强):

| 场景 | 为什么超出 v1 默认 |
| --- | --- |
| Agent runtime 跑在第三方 cloud(controller 无代码可见性) | runtime 可能"故意慢"绕过 watcher 信号;v1 假设 runtime 可信 |
| Mirror Realm 跨 deployment(controller / mirror / 源 Realm 在不同信任域) | watcher 跨域投递延迟更高,90s 是乐观估计;受控部署需要 frontier freshness gate 或 source-issued lease |
| Agent 多租户 SaaS(同一 runtime 服务多个 controller) | 一个 controller 的 revoke 不应影响其他 controller 的 task;watcher 设计需要分租 |
| 合规 / 监管要求"revoke 立即生效"(法律意义上) | best-effort SLA 不构成法律承诺;需要 sync gate 或 hardware-enforced freshness |

这些场景的实现 SHOULD 在自家 profile 中显式声明 "stricter freshness model";reserved profile id `cx.profile.agent_workspace.strict.v1` 已在 registry 中预留,目前不绑定具体 normative 要求,实现可使用私有 profile 直到该 reserved id 被规范填充。

### 1.2 v1 不强制 freshness gate 的代价(设计取舍登记)

三种 freshness 收紧方案 — frontier freshness gate / source-issued lease / 协议级硬上限 — 均被 v1 默认 profile **拒绝**,原因:

- 引入 sync gate 把每次 agent 执行都加上一次回往源 Realm 的 RTT,在典型 single-controller 场景下是不必要的开销
- 默认 profile 不应假设跨 deployment(那是另一类信任模型的事情,见 §1.1)
- audit log + controller 审批已经覆盖了主要风险面;额外 freshness 机制是双重保险但代价大

**v1 默认 profile 显式接受的代价**:agent 在 source revoke 发生与 mirror watcher 通知到达之间(默认 ≤ 90 秒,实际可能更长)可能继续基于过期源上下文执行任务、生成草稿。controller 在 publish-back 审批节点 SHOULD 自己核对 agent 是否仍是源 Realm 合法成员(UI 帮助见 §7.5)。

### 1.3 软指引:Agent runtime 与 Controller UI 应当怎么自助补救

不强制 reducer 引入 freshness gate,但 v1 对 agent runtime 与 controller UI 给出 SHOULD 级别的实现建议:

- **Agent runtime SHOULD 自行暂停**:当 agent runtime 在调用源 Realm 的 events / blob / capability check 时收到 `403 capability_denied` 或等价"我已不再是该 Realm 成员"信号时,SHOULD **不等 watcher**,直接把当前 agent_task 标 paused 并通知 controller。这是 runtime-side 主动行为,不依赖 mirror reducer 状态。
- **Controller UI SHOULD 显示 freshness 提示**:agent_task 的 `source_authority` cell 上次更新时间超过部署声明的 `freshness_advisory_threshold_ms`(默认 5 分钟,部署 MAY 自调)时,UI **SHOULD** 在 task 列表上显示"授权未最近验证"小标记,让 controller 在审批 publish-back 前格外谨慎。该 threshold 是 UI hint 性质,不进 reducer 决策。
- **publish-back 审批 SHOULD 携带 source membership 提示**:UI 在 controller 点"发回源 Flow"按钮时,SHOULD 旁注"agent 当前在源 Realm 的最新已知 membership 状态:active / unknown / revoked",信息源是 mirror Realm 内 `source_authority` cell + watcher 最近一次成功通知时间。

这三条都不阻塞 v1 互操作,实现可以选择不做(`watcher + audit` 仍是 protocol-level baseline)。

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│   Source Realm（公开协作 / 组织 / 项目）                    │
│   ┌──────────────────────┐                                  │
│   │ Source Flow          │  agent_X 作为 Realm member 加入  │
│   │  - Alice             │  capability constraint           │
│   │  - Bob               │  (read_only / mention_respond)   │
│   │  - agent_X (Alice's) │                                  │
│   │                      │  Alice 写 cx.content.mention_     │
│   │                      │  redirect → source-side stub     │
│   └──────────────────────┘                                  │
└───────────────────│─────────────────────────────────────────┘
                    │ derived_from (cross-Realm references)
                    │ + cx.content.import_attestation
                    ▼
┌─────────────────────────────────────────────────────────────┐
│   Alice's Agent Workspace Root Realm（DID Doc advertise）   │
│   ┌──────────────────────────┐                              │
│   │ Mirror Realm             │  members = Alice + her agents│
│   │  per source Realm        │  独立 MLS group / E2EE 边界  │
│   │   ┌────────────────────┐ │                              │
│   │   │ Mirror Flow        │ │  per source Flow             │
│   │   │  cx:agent_task: ×N │ │  3 独立 FSM cell             │
│   │   │  cx:message:  ×M   │ │  controller↔agent 对话       │
│   │   └────────────────────┘ │                              │
│   └──────────────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

**两个独立治理域**：

| 治理对象 | Admin | 决策依据 |
|---|---|---|
| 源 Realm 的 agent membership | 源 Realm governance（可能是 Realm admin、organization admin） | 公开协作的"声明" |
| Workspace / Mirror Realm 的成员 | controller 独占 | 私人工作流的"组队" |

**不自动同步**；变更通过 notification 推送，controller 显式决定。

## 3. 标准化协议表面

| 类别 | 名称 | 描述 |
|---|---|---|
| Realm profile | `cx.profile.agent_workspace.v1` | Workspace root + mirror Realm 的 schema 约束 |
| 对象 | `cx.schema.agent_task.v1` | mirror Realm 内的任务对象 |
| Typed ID | `cx:agent_task:` | UUIDv7 |
| Event | `cx.agent_task.create` | 创建 agent_task |
| Event | `cx.agent_task.execution.transition` | execution_state cell transition |
| Event | `cx.agent_task.transparency.transition` | transparency cell transition |
| Event | `cx.agent_task.source_authority.transition` | source_authority cell transition |
| Event | `cx.agent_task.cancel` | 便捷取消（alias） |
| Event | `cx.agent_workspace.reservation.set` | 写 reservation cell（cas-register `head_eq:"__unset__"` predicate）|
| Event | `cx.agent_workspace.reservation.recover` | 写 recovery Move 解 ⊥（`head_in [conflict_heads]` + state_witness + inclusion_proof + lex-min winner）|
| Event | `cx.agent_workspace.reservation.cleanup` | TTL 后重置 cell 到 sentinel；唯一可写 sentinel 的 event_kind（cell schema `sentinel_writers` 白名单）|
| Content block | `cx.content.mention_redirect` | 源 Realm 中的 routing stub |
| Content block | `cx.content.import_attestation` | mirror Realm 中的跨 Realm 重加密引用 |
| Capability action | `cx.capability.agent_workspace.reserve` | 写 reservation Move |
| Capability action | `cx.capability.agent_workspace.recover` | 写 recovery Move |
| Capability action | `cx.capability.agent_workspace.cleanup` | 写 orphan cleanup Move |
| Capability constraint kind | `mention_respond_only` | agent 仅在被 @ 时回复 |
| Capability constraint kind | `import_to_external_space` | source-side policy：是否允许 import 到外部 Realm |
| Cell namespace | `mirror_space_by_source` | workspace root 内的 source→mirror Realm 唯一性 cell |
| Cell namespace | `mirror_flow_by_source` | mirror Realm 内的 source→mirror Flow 唯一性 cell |
| Cell namespace | `agent_task.<id>.execution_state` | per-task execution FSM |
| Cell namespace | `agent_task.<id>.transparency` | per-task transparency FSM |
| Cell namespace | `agent_task.<id>.source_authority` | per-task source_authority FSM |
| Feature id | `cx.feature.mention_redirect.v1` | critical_extension marker |
| Feature id | `cx.feature.import_attestation.v1` | critical_extension marker |
| Notification type | `agent_membership_change` | 源 Realm agent 成员变更通知到 controller |
| Service operation | `agent_workspace.resolve_mirror_flow` | controller-only resolve |
| Service operation | `agent_workspace.list_pending_tasks` | controller-only orphan reconciliation |
| DID Document service | `ContrixAgentWorkspaceService` | HTTPS endpoint，鉴权后 resolve workspace_root_realm_id |

## 4. Agent 加入源 Realm（路径 A / B）

Spec v1 中**没有 Flow-level membership**（[flow.schema.json](../../artifacts/schemas/flow.schema.json) 无 members 字段）。Agent 加入有两种 per-Flow scoping 路径：

**路径 A（默认，粗粒度）**：Agent 加入源 **Realm**
- Agent 拿到 Realm 级 MLS 解密边界，能看 Realm 内所有 Flow
- Capability constraint 限定写权限到具体 Flow（`object_ref=cx:flow:...`）
- 适合"agent 对整个项目都可见"

**路径 B（细粒度）**：源 Flow 先设置 `discussion_realm_ref` 指向 linked Realm；agent 加入 linked Realm
- Agent 只看该 Flow 讨论时间线
- Child Realm 独立 MLS group / retention / history visibility
- 要求源 Flow 提前规划 `discussion_realm_ref`

本 profile 不强制选择；source Realm admin / Flow creator 自决。Mirror 端通过 `derived_from` Relation 指向源对象，不关心源是 A 还是 B。

**邀请 agent 的标准流程**（不引入新 event kind）：

1. inviter 写 `cx.invite.create` 携带 `capability_grant_refs[]`
2. agent accept 后 reducer 写 `cx.member.state(actor=agent_did, state=member)` + 对应 `cx.capability.grant`
3. capability grant 的 `attached_authority` 字段（见 §5）证明 agent 由 inviter principal 控制

**标准 capability constraint preset（normative pattern）**：

Preset 是**声明性 sugar**——客户端 / SDK 把 preset 名展开为标准 grant；reducer 与 `capability-grant.schema.json` MUST 只看展开后的 canonical `cx.<domain>.<action>` 数组,不接受 preset 名或裸名 action 直接进入 `actions[]` 字段(见 [`../authz/capabilities.md` §5](../authz/capabilities.md))。

| Preset name | 含义 | 展开为标准 grant 的 canonical actions(`cx.<domain>.<action>` 形态) |
|---|---|---|
| `cx.agent_member.observer` | 只观察 | `cx.event.read`(看时间线 / 历史事件) + `cx.object.read_content`(constrained by `object_type_allow=["message"]`,看 Message 正文) |
| `cx.agent_member.read_only` | 只读 + 反应 | observer 展开集 + `cx.reaction.add` |
| `cx.agent_member.mention_respond_only` | 仅在被 @ 时回复 | read_only 展开集 + `cx.message.create`(constrained by `mention_respond_only`,只允许 `in_reply_to` 指向 mention 自身为 sender 的消息;详见 [`../authz/constraint-schema.md`](../authz/constraint-schema.md)) |
| `cx.agent_member.full_collaborator` | 完整成员 | 标准 member capability set(`cx.event.read` + `cx.object.read_content` + `cx.reaction.add` + `cx.message.create` + `cx.message.revise.own` + `cx.message.redact.own` + `cx.flow.read`,无 `mention_respond_only` 约束) |

> **不接受裸名 action**:`read_history` / `read_messages` / `react` / `message.create` 等裸名在 wire / `capability-grant.schema.json` actions[] 字段中 MUST `schema_violation` 拒绝。Preset 仅在客户端层 / UI sugar / SDK helper 中使用;一旦展开到 grant,所有 action token MUST 是已注册的 `cx.<domain>.<action>` 形态(见 [`artifacts/registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json))。

## 5. `attached_authority` 扩入 capability-grant schema

`capability-grant.schema.json` 新增可选字段 `attached_authority`（**当 grant subject 是 agent DID 且其 `cx.schema.agent_authority.v1.acting_mode == "delegated_assistant"` 时必填**）：

```json
{
  "attached_authority": {
    "type": "object",
    "required": ["evidence_kind"],
    "oneOf": [
      {
        "properties": {
          "evidence_kind": { "const": "anchored_event_ref" },
          "authority_event_ref": { "type": "string", "pattern": "^cx:event:..." },
          "authority_event_hash": { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" },
          "anchor_inclusion_proof": { "type": "object" }
        },
        "required": ["authority_event_ref", "authority_event_hash"]
      },
      {
        "properties": {
          "evidence_kind": { "const": "state_witness" },
          "witness_issuer": { "type": "string", "pattern": "^did:..." },
          "witness_signature": { "type": "string" },
          "agent_id": { "type": "string" },
          "controller": { "type": "string" },
          "responsible_actor": { "type": "string" },
          "acting_mode": { "type": "string" },
          "valid_until": { "type": "string", "format": "date-time" }
        },
        "required": ["witness_issuer", "witness_signature", "agent_id", "controller", "valid_until"]
      }
    ]
  }
}
```

> evidence_kind 仅 `anchored_event_ref` 和 `state_witness` 两种。

**Reducer 校验**(同步前置 gate):

- `evidence_kind=anchored_event_ref`:reducer **MUST 同步**通过 controller's principal server 验证 inclusion proof,**才能让该 grant 释放任何 source Realm 访问 / capability / MLS Welcome**。验证未完成时 grant **MUST 进入 `pending_verification` 状态**——可写入 reducer / 落到 frontier(便于后续异步完成),但 reducer **MUST NOT** 让任何依赖该 grant 的下游动作生效:
  - 不向 agent 颁发 source Realm membership(`cx.member.state` 拒绝引用 `pending_verification` grant 作为 `authorized_by`)
  - 不向 agent 发送 MLS Welcome
  - 不在源 Realm history visibility 上把 agent DID 算作有授权 reader
  - 不允许 mirror 端 `cx.content.import_attestation` 引用该 grant 作为 `authority_grant_ref`
- controller's principal server 不可达时:grant 保持 `pending_verification`,**MUST NOT** 静默降级为 `unverified_authority` accepted state。运行时 SHOULD 重试,带指数退避;客户端 UI MUST 显式提示"agent 授权未验证,暂停操作"。
- 验证最终失败(controller 服务器明确否认 / hash 不匹配 / event 不存在)→ grant 状态 → `verification_rejected`,reducer **MUST** 同时撤销所有 transient 副作用(若有);agent 即使临时持有过期信息也不得继续动作。
- `evidence_kind=state_witness`:reducer **MUST 同步**校验 `witness_signature` 由 controller's principal server 当前注册的 key 签发;签名无效 = grant `verification_rejected`(不进入 pending)。签名输入 MUST 是 `utf8("cx-agent-authority-state-witness-v1\n") || canonical_json(state_witness evidence object with witness_signature omitted)`，并覆盖 `agent_id`、`controller`、`responsible_actor`、`acting_mode`、`valid_until` 和 `witness_issuer`。TTL 由 `valid_until` 控制;过期后 grant 自动失效。state_witness 形态的优点是**不依赖远端可达性**——witness 是预签发的离线凭证,适合 controller 服务器临时不可达但 controller 设备已经事先签了授权的场景。

**为什么是同步前置 gate**(设计取舍登记):

异步路径在 controller server 短暂不可达(攻击者制造 DNS 劫持 / TLS outage 的窗口)的情况下,**允许伪造的 attached_authority 在 agent 已经访问 source Realm 之后才被识破**——而那时已经读完 history、收到 MLS Welcome、写过 message,撤销已发生的访问是不可能的。同步 fail-closed gate 的代价是 controller 服务器宕机期间 agent onboarding 不能进行(但已 onboarding 的 agent 继续工作不受影响,因为它们的 grant 之前已完成同步验证)。需要离线 onboarding 场景的部署 SHOULD 使用 `evidence_kind=state_witness`(预签发离线凭证)。

## 6. Mirror Realm 创建与并发竞态（reservation saga）

### 6.1 双层 reservation cell

| 层 | Cell key | 命名空间 | Cell value | Lattice |
|---|---|---|---|---|
| **L1** | `mirror_space_by_source:<source_realm_id>` | **workspace root Realm** | `cx:realm:<mirror_realm_id>` 或 sentinel | `cas-register + bottom=reject`，schema 声明 `initial_value="__unset__"` |
| **L2** | `mirror_flow_by_source:<source_flow_id>` | **mirror Realm** | `cx:flow:<mirror_flow_id>` 或 sentinel | 同上 |

> **Spec 依赖**：[`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `cell_lattice` 包含可选 `initial_value` 字段（仅 cas-register 合法）。[`event-auth-state-resolution.md §5.3.3`](../authz/event-auth-state-resolution.md) cas-register `join` 算法在 schema 声明 `initial_value` 时使用 `current = cell_schema.initial_value`。本 profile 的两个 reservation cell schema 在 §9 profile 声明中直接使用 `initial_value="__unset__"`。

### 6.2 Reservation 流程

1. 客户端调用 `agent_workspace.resolve_mirror_flow(source_flow_id)`；存在则复用
2. 若 query 返回空，客户端**预分配** UUIDv7 `mirror_realm_id` 和 `mirror_flow_id`
3. **L1 reservation Move**（workspace root Realm）：
   - lattice op：`set`，cell = `mirror_space_by_source:<source_realm_id>`，value = `mirror_realm_id`
   - predicate：`head_eq: "__unset__"`
   - capability：controller's `cx.capability.agent_workspace.reserve` grant
4. L1 收敛三种情况：
   - **happy path**（cell 当前 head = `"__unset__"`，predicate 满足）：lattice op accepted，cell 推进到 `mirror_realm_id`
   - **cell 已 set**（cell 当前 head = existing_id，predicate `head_eq:"__unset__"` 不满足）：按 [event-auth-state-resolution.md:640](../authz/event-auth-state-resolution.md) `if not predicate(v): FAIL_PRECONDITION` → reducer 返回 `failed_precondition`（reason=`reservation_cell_already_set`，response 含 winner cell value）。**不进入 ⊥**——⊥ 只发生在 lattice join 阶段，predicate 不满足在 join 之前的 validation 阶段就 fail
   - **真并发同时写不同 reservation token**（causally concurrent，双方 predicate 都满足）：lattice join 阶段 siblings `(unset, idA)` 和 `(unset, idB)` 满足 `b1==b2 and v1!=v2` → cell → `⊥`（bottom=reject，依赖该 cell 的后续 Move MUST `failed_bottom`），触发 §6.3 recovery saga
5. **L1 成功后**，写独立后续 `cx.realm.create(id=mirror_realm_id)` Move 到 controller 的 principal control stream
6. mirror Realm 存在后写 **L2 reservation Move**，同样 `head_eq: "__unset__"`
7. L2 成功后写独立 `cx.flow.create(id=mirror_flow_id)` Move

### 6.3 Recovery Move（⊥ 状态修复）

按 [event-auth-state-resolution.md §8](../authz/event-auth-state-resolution.md) 冲突修复标准协议：

```text
Move {
  preconditions: [
    (cell, head_in [candidate_A, candidate_B, ...])
  ],
  effects: [
    (cell, set lex-min(candidates))
  ],
  refs: [
    (cx:grant:<recovery_capability>, role="authorized_by"),
    (pre_conflict_state_witness,     role="state_witness",     critical=true),
    (snapshot_inclusion_proof,       role="inclusion_proof",   critical=true)
  ]
}
```

- Recovery capability `cx.capability.agent_workspace.recover` 由 controller principal 自我持有
- Deterministic winner：lex-min on candidate `cx:realm:` / `cx:flow:` UUIDv7 字符串
- State_witness / inclusion_proof MUST `critical=true`

### 6.4 Orphan reservation 处理

1. **TTL 存放位置**：reservation Event 的 payload 顶层携带可选 `reservation_ttl_seconds`（默认 600s）字段，由 payload class `agent_workspace_reservation_set_payload` 定义（见 [`event-payload.schema.json#/$defs/agent_workspace_reservation_set_payload`](../../artifacts/schemas/event-payload.schema.json)）。承载该 payload 的 Event kind 是 `cx.agent_workspace.reservation.set`。TTL **不**塞进 `lattice_op` metadata，因为 [event-schema.json](../../artifacts/schemas/event-schema.json) `lattice_op` `additionalProperties: false`。
2. **Resolve API filtering**：`resolve_mirror_flow` MUST 仅返回 reservation + create Move 都存在的 mapping，不返回未完成 reservation
3. **Cleanup Move**：
   - Event kind：`cx.agent_workspace.reservation.cleanup`，payload class `agent_workspace_reservation_cleanup_payload`
   - Capability holder：**仅 controller principal**（capability `cx.capability.agent_workspace.cleanup`）；可标准 capability delegation 给自己 sync node 的 system actor
   - lattice op：`set`，cell = `mirror_*_by_source:<source_id>`，value = `"__unset__"`
   - predicate：`head_eq: <reservation_id>`（指向当前 stale value）
   - **TTL 证据（Anchor-based time，不用自报 wall clock）**：cleanup Event payload `ttl_evidence` 字段 MUST 含 `{reservation_anchor_ref, reservation_anchor_index, current_anchor_ref, current_anchor_index, ttl_anchor_distance}`：
     - `reservation_anchor_ref` / `reservation_anchor_index`：reservation Move 被 anchor 时的 Anchor 引用 + 该 Anchor 在 DAG 中的 index（由源 Realm anchorer 签发，可独立验证）
     - `current_anchor_ref` / `current_anchor_index`：cleanup 提交时刻的 effective Anchor
     - reducer 验证：`current_anchor_index >= reservation_anchor_index + ttl_anchor_distance`，其中 `ttl_anchor_distance` 是 schema 声明的最小 anchor 距离（按典型 anchor cadence 折算自 600s）
   - **替代方案**（更弱但实现简单）：housekeeping authority（controller 自己的 sync node）以 system actor 签发 `clock_witness` attestation 携带 `signed_current_time`；reducer 验证签名 + 接受 issuer 自报时间。这条仅适用于单 server 部署，不适用 multi-master
4. **Idempotent retry**：`cx.realm.create.id` / `cx.flow.create.id` 是固定 UUIDv7，重试相同 ID 是 no-op

## 7. `agent_task` 对象与三正交 FSM

### 7.1 对象 schema

```json
{
  "id": "cx:agent_task:01964200-0000-7000-8000-cccccccccccc",
  "schema": "cx.schema.agent_task.v1",
  "realm_id": "cx:realm:<mirror realm>",
  "flow_id": "cx:flow:<mirror flow>",
  "target_agent_id": "did:web:alice-agent.example",
  "instruction": {
    "kind": "cx.content.text",
    "body": "总结源 Flow 的讨论并起草回复",
    "format": "markdown"
  },
  "encrypted_payload": null,
  "context_anchor": {
    "source_realm_id": "cx:realm:<source>",
    "source_flow_id": "cx:flow:<source>",
    "source_anchor_ref": "cx:anchor:sha256:<frontier_digest_at_trigger_time>",
    "source_frontier_hash": "sha256:...",
    "trigger_redirect_pair_id": "01964200-0000-7000-8000-aaaaaaaaaaaa"
  },
  "source_stub_event_ref": null,
  "created_by": "did:web:alice.example",
  "created_at": "2026-05-17T10:00:00Z"
}
```

**关键**：对象 schema 顶层**无** `state` / `state_changed_at` 字段。任务状态在 3 个独立 FSM cell 上 query。

### 7.2 三个正交 FSM cell

| Cell key | Lattice | States |
|---|---|---|
| `agent_task.<task_id>.execution_state` | `fsm`, `bottom=reject` | `pending_source_stub`, `active`, `completed`, `cancelled_stub_rejected`, `cancelled_orphan`, `cancelled_by_controller` |
| `agent_task.<task_id>.transparency` | `fsm`, `bottom=reject` | `ok`, `lost`, `reconfirmed_after_loss` |
| `agent_task.<task_id>.source_authority` | `fsm`, `bottom=reject` | `ok`, `revoked`, `reconfirmed_after_revoke` |

### 7.3 Agent runtime 执行 gate（核心 invariant）

```text
agent_task may be executed iff:
  execution_state == "active"
  AND transparency ∈ {"ok", "reconfirmed_after_loss"}
  AND source_authority ∈ {"ok", "reconfirmed_after_revoke"}
```

任一不满足 → agent runtime MUST 暂停。两个失效维度可同时存在；UI 显示两个独立 banner。

### 7.4 合法 transition 表

**Cell 1: `execution_state`**

```text
[initial] → pending_source_stub      (Phase 1，源 routing 触发)
[initial] → active                   (direct task，无 source routing)

pending_source_stub → active                       (Phase 3 reconcile)
pending_source_stub → cancelled_stub_rejected      (Phase 2 源 reject)
pending_source_stub → cancelled_orphan             (TTL housekeeping)
pending_source_stub → cancelled_by_controller

active → completed                                 (controller mark complete)
active → cancelled_by_controller
```

Terminal：`completed`, `cancelled_*` 出度为零。

**Cell 2: `transparency`**

```text
[initial] → ok                                     (default)

ok → lost                                          (watcher: source stub redacted)
lost → reconfirmed_after_loss                      (controller continues)
```

`lost` 与 `reconfirmed_after_loss` 实质 terminal（Message redaction 是 terminal，无法 un-redact）。

**Cell 3: `source_authority`**

```text
[initial] → ok                                     (default)

ok → revoked                                       (watcher: source grant revoke / member remove)
revoked → reconfirmed_after_revoke                 (controller continues with imported content)
```

`revoked` 与 `reconfirmed_after_revoke` 实质 terminal（authority_grant_ref 绑定原 grant_id；re-grant 是新 grant 与 task 无关）。

### 7.5 事件家族

```text
cx.agent_task.create
  → 创建 agent_task；初始化 3 cell 初值（execution_state=pending_source_stub|active, transparency=ok, source_authority=ok）

cx.agent_task.execution.transition
  → 写 execution_state cell（transition op）

cx.agent_task.transparency.transition
  → 写 transparency cell

cx.agent_task.source_authority.transition
  → 写 source_authority cell

cx.agent_task.cancel
  → 便捷事件；reducer 等价于 cx.agent_task.execution.transition(from=<current>, to=cancelled_by_controller)
  → MUST NOT 改变 transparency / source_authority cell（保留 audit 痕迹）
```

#### Reducer 等价语义注（normative）

`cx.agent_task.cancel` 的 reducer 行为 MUST 与下列 `cx.agent_task.execution.transition` 完全等价：

```text
{
  task_id: <from cancel payload>,
  cell:    "agent_task.<task_id>.execution_state",
  op:      "transition",
  from:    <current execution_state cell head>,
  to:      "cancelled_by_controller",
  reason:  <optional pass-through from cancel.reason>,
  evidence_refs: []
}
```

具体规则：

1. **Cell scope**：只写 `execution_state` cell；transparency / source_authority cell 状态保持不变。这保留了 audit 痕迹（取消前的透明度 / 授权状态对历史回放仍可见）
2. **`from` 字段填充**：cancel 是便捷事件，wire 上不要求客户端提供 `from`。Reducer MUST 通过 read-then-write 模式（read current head → write transition）填充 `from`。Read-then-write 的 race（cell 已是 terminal）由 FSM `from` precondition 自然拒绝
3. **合法源 state**：cancel MUST 从非 terminal 的 `execution_state` 出发（`pending_source_stub` / `active`）；从 terminal state（`completed` / `cancelled_*`）发起的 cancel reducer MUST 返回 `failed_precondition`（reason=`invalid_task_fsm_transition`）
4. **Capability**：与 `cx.agent_task.execution.transition` 共享 controller-only capability 要求
5. **Cell registry binding**：本事件在 [contract-catalog event_kinds](../../artifacts/registry/contract-catalog.json) 中 `cell_family=cx.component.agent_task.execution_state.v1` + `lattice=fsm` + `cell_subject.field=payload.task_id`，与 `execution.transition` 完全一致
6. **`cancel.reason` 透传**：当 payload 含可选 `reason` 字符串，reducer MUST 把它写入合成 transition event 的 `reason` 字段；缺省 reducer MAY 填 `"cancelled_by_controller"`

Transition event payload：

```json
{
  "task_id": "cx:agent_task:...",
  "cell": "agent_task.cx:agent_task:....transparency",
  "op": "transition",
  "from": "ok",
  "to": "lost",
  "reason": "source_stub_redacted",
  "evidence_refs": ["cx:event:<source redaction event>"]
}
```

## 8. Content blocks

### 8.1 `cx.content.mention_redirect`

```json
{
  "kind": "cx.content.mention_redirect",
  "body": "Alice asked her agent privately",
  "target_actor_id": "did:web:alice-agent.example",
  "authority_grant_ref": "cx:grant:01964200-0000-7000-8000-bbbbbbbbbbbb",
  "redirect_pair_id": "01964200-0000-7000-8000-aaaaaaaaaaaa"
}
```

承载 Event 顶层 MUST 含 critical_extension：

```json
{
  "kind": "cx.message.create",
  "requirements": {
    "critical_extensions": [
      {
        "id": "cx.feature.mention_redirect.v1",
        "scope": "payload",
        "fail_closed": true,
        "schema_ref": "cx.schema.content.mention_redirect.v1"
      }
    ]
  },
  "payload": {
    "flow_id": "cx:flow:<source>",
    "content": { "kind": "cx.content.mention_redirect", "...": "..." }
  }
}
```

**字段规则**：

- `body`（必填，Content Block schema）：脱敏摘要，对源 Flow 所有成员可见。客户端 MUST 在 compose UI 显式提示 "this summary is visible to all source Flow members"；MUST NOT 自动从私有指令派生
- `target_actor_id`：MUST 是 sender principal 的 controlled agent（通过 `authority_grant_ref` 解析的 grant 的 `attached_authority.controller == sender_principal` 验证）；不满足 reducer MUST reject 并返回 `capability_denied`（不降级为普通 `cx.content.mention`）
- `authority_grant_ref`：引用源 Realm 中已 active 的 grant；reducer 校验 grant active + grant.subject == target_actor_id + grant.attached_authority.controller == sender principal
- `redirect_pair_id`：opaque UUIDv7，sender 生成；双端关联，不暴露 mirror Realm / Flow / Event ID

### 8.2 `cx.content.import_attestation`

```json
{
  "kind": "cx.content.import_attestation",
  "body": "（重加密引入的源消息正文 - 纯文本 fallback）",
  "claimed_origin": {
    "realm_id": "cx:realm:<source>",
    "flow_id": "cx:flow:<source>",
    "message_id": "cx:message:<source>",
    "actor_id": "did:web:bob.example",
    "created_at": "2026-05-17T09:55:00Z"
  },
  "importer": {
    "actor_id": "did:web:alice-agent.example",
    "imported_at": "2026-05-17T10:00:01Z"
  },
  "import_signature": "<importer 对 canonical signing input 的签名>",
  "optional_proofs": {
    "origin_event_hash": "sha256:...",
    "origin_author_proof_ref": "cx:event:<原作者签名 event 引用>",
    "source_frontier_ref": "cx:anchor:sha256:<source_frontier_digest>"
  },
  "source_export_policy_attestation": null,
  "content": { "kind": "cx.content.text", "body": "..." }
}
```

**性质**：这是 "importer 声称'我从某 Realm 看到了这条内容'"，`import_signature` 只能证明 importer 自己的声明，**不能**证明原作者明文确实如此。reader UI MUST 显著区分"原作者直接发言"vs"由 X importer 声称引自"。

**Source export policy attestation**（可选；如携带 MUST 满足 canonical schema）：

```json
{
  "authority_did": "did:web:source-realm-admin.example",
  "source_realm_id": "cx:realm:<source>",
  "policy_hash": "sha256:...",
  "policy_decision": "allow",
  "importer_actor_id": "did:web:alice-agent.example",
  "import_destination_realm_id": "cx:realm:<mirror>",
  "content_hash": "sha256:...",
  "source_frontier_ref": "cx:anchor:sha256:<source_frontier_digest>",
  "issued_at": "2026-05-17T10:00:00Z",
  "valid_until": "2026-05-17T11:00:00Z",
  "signature": "..."
}
```

- `content_hash`：JCS-canonicalized JSON of the `content` field + SHA-256 + `sha256:` 前缀。复用 [encoding.md](../conformance/encoding.md) RFC 8785/JCS profile
- `signature` canonical signing input = JCS-canonicalized `{schema_id: "cx.schema.content.source_export_policy_attestation.v1", domain: "cx.domain.export_policy_attestation.v1", body: <除 signature 外的所有 required 字段>}` + SHA-256

**Mirror reducer 行为**(双 profile 分离):

Mirror reducer 的行为**取决于源 Realm 声明的 governance level**。源 Realm 在自身 schema_refs / policy_components 中声明 `cx.profile.agent_workspace.governed.v1`(详见 §9.1)即被视作 governed source;其他默认按 permissive 处理。

**permissive 行为(默认,适用于无 governance 声明的源 Realm)**:
- 缺 attestation → 接受 event,audit 标记 `export_attestation_missing`
- 携带但签名无效 / 字段不一致 → 接受 event,audit 标记 `export_attestation_invalid`
- 签名有效 → 接受 event,audit 标记 `export_attestation_verified`
- **任何情况都不拒绝** — mirror 信任 source-side agent runtime 自觉执行 export policy

**governed 行为(源 Realm 声明 `cx.profile.agent_workspace.governed.v1` 时,reducer MUST 收紧)**:
- 缺 attestation → **reject**(`source_export_attestation_required`);event 不进入 mirror Realm accepted set
- 携带但签名无效 → **reject**(`source_export_attestation_invalid`);记 audit 但拒收
- 携带但 `policy_decision != "allow"` → **reject**(`source_export_attestation_denied`)
- 携带但 `content_hash` 与 `content` 字段 canonical hash 不匹配 → **reject**(`source_export_content_hash_mismatch`)
- 携带但 `import_destination_realm_id` 与本 mirror Realm 不匹配 → **reject**(`source_export_destination_mismatch`)
- 携带但已过 `valid_until` → **reject**(`source_export_attestation_expired`)
- 携带但 `authority_did` 不在源 Realm `export_policy_authorities[]` 中 → **reject**(`source_export_authority_unauthorized`)
- 所有校验通过 → 接受 event,audit 标记 `export_attestation_verified`

**为什么拆分两个 profile**(设计取舍登记):

permissive 模式假设"agent runtime 是受信代码,会自觉执行源 Realm 的 export policy"。该假设在 controller 自托管单实例、agent runtime 由 controller 自己审查代码的场景下成立。但对于:
- **受保护源 Realm**(企业项目群、合规边界内的资料、机密通信)
- **跨 deployment 协作**(agent runtime 跑在第三方 / cloud 上)
- **多方 mirror**(同一源 Realm 可能被多个 controller 各自 mirror)

permissive 让 export policy 沦为 audit log;一旦 agent runtime 有 bug / 被攻陷 / 故意绕过,内容已经在 mirror Realm 重加密落地——**事后撤销已经被 mirror 端读到的内容是不可能的**。

Governed profile 让**源 Realm 主动声明自己受保护**,mirror 端 reducer 据此**代表源 Realm 强制执行 export policy**。导入端拒收意味着内容**从未**进入 mirror history,attack window 关闭。

代价:governed profile 下,合法 import 也需要先取得 source-side 签发的 export attestation,引入一次回 source Realm policy authority 的同步调用(类似 attached_authority 的同步验证模式)。这是对**机密 / 合规 / 跨 deployment** 场景的应有摩擦。

> **诊断字段命名**:`source_export_attestation_required` / `_invalid` / `_denied` / `_destination_mismatch` / `_content_hash_mismatch` / `_expired` / `_authority_unauthorized` 这 7 个 reason_code 注册在 `error-code-registry.json` `reason_codes[]` 命名空间。

## 9. Realm profile `cx.profile.agent_workspace.v1`

```json
{
  "profile_id": "cx.profile.agent_workspace.v1",
  "scope": "realm",
  "applies_to_roles": ["workspace_root", "mirror_space"],
  "membership": {
    "owner": "single_controller_principal",
    "allowed_member_kinds": ["controller_principal", "controller_owned_agent"],
    "max_human_members": 1,
    "agent_subject_constraint": "grant.attached_authority.controller == workspace_owner"
  },
  "e2ee": {
    "required": true,
    "mls_group": "per_space"
  },
  "discoverability": "secret",
  "history_visibility": "joined",
  "retention": {
    "default_flow_retention_days": null,
    "stale_import_attestation_handling": "lock_lazy",
    "inherit_retention_from_source": false
  },
  "cell_schemas": [
    {
      "namespace": "mirror_space_by_source",
      "applies_to_role": "workspace_root",
      "lattice": "cas-register",
      "bottom": "reject",
      "initial_value": "__unset__",
      "sentinel_writers": ["cx.agent_workspace.reservation.cleanup"]
    },
    {
      "namespace": "mirror_flow_by_source",
      "applies_to_role": "mirror_space",
      "lattice": "cas-register",
      "bottom": "reject",
      "initial_value": "__unset__",
      "sentinel_writers": ["cx.agent_workspace.reservation.cleanup"]
    }
  ],
  "relation_profiles": [
    {
      "relation_kind": "derived_from",
      "from_type": "realm",
      "to_type": "realm",
      "cardinality": "one_to_one",
      "max_to_per_from": 1,
      "max_from_per_to": 1,
      "scope": "global",
      "on_conflict": "deterministic_winner"
    },
    {
      "relation_kind": "derived_from",
      "from_type": "flow",
      "to_type": "flow",
      "cardinality": "one_to_one",
      "max_to_per_from": 1,
      "max_from_per_to": 1,
      "scope": "global",
      "on_conflict": "deterministic_winner"
    }
  ]
}
```

**Membership normative**：

- Workspace root Realm owner = controller principal
- Members = `{controller's authorized devices} ∪ {agents with active capability_grant.attached_authority.controller == workspace_owner}`
- 加入通过标准 `cx.member.state`；不引入新 `workspace_visible` 字段
- Mirror Realm 继承相同 membership 规则

**Unsupported profile fail-closed**：未声明支持本 profile 的服务端 **对 mirror Realm 写入** MUST fail-closed（拒绝 `cx.agent_task.*` / `cx.content.import_attestation`，返回 `profile_unsupported`）。源 Realm 接受 `mention_redirect` 不依赖本 profile——依赖 `cx.feature.mention_redirect.v1` critical_extension 是否被源 Realm 服务端支持。

### 9.1 `cx.profile.agent_workspace.governed.v1`(受保护源 profile)

**目的**:让源 Realm 主动声明"我是受保护的,任何 agent 把我的内容导出到 mirror Realm 时,mirror 端 reducer 必须强制执行我的 export policy"。源 Realm 自身在 `policy_components` / `schema_refs` 中 import 该 profile,即把保护意愿写入 Realm 的 canonical state。

**声明位置**:**源 Realm**(不是 mirror Realm)的 schema / policy。受保护 Realm 在 create event 或随后的 `cx.realm.policy_components` Move 中加入:

```json
{
  "profile_id": "cx.profile.agent_workspace.governed.v1",
  "scope": "realm",
  "applies_to_roles": ["governed_source"],
  "export_policy": {
    "source_export_attestation_required": true,
    "min_attestation_strength": "anchored_event_ref",
    "max_attestation_ttl_seconds": 3600,
    "destination_space_must_be_pinned": true,
    "content_hash_must_match": true,
    "export_policy_authorities_field": "policy_components.export_policy_authorities"
  },
  "mirror_reducer_behavior": {
    "missing_attestation": "reject",
    "invalid_signature": "reject",
    "denied_decision": "reject",
    "destination_mismatch": "reject",
    "content_hash_mismatch": "reject",
    "expired": "reject",
    "authority_unauthorized": "reject"
  }
}
```

**`export_policy_authorities[]`**:源 Realm 在 policy_components 内声明哪些 DID 有权签发 export policy attestation。典型场景:
- 单 controller 个人 Realm:owner principal DID
- 组织受控群:organization DID + 显式委派的 admin DID
- 合规群:专门的 export-policy-authority service DID,由 compliance team 控制

attestation `authority_did` 字段 MUST 在该列表内,否则 mirror reducer reject `source_export_authority_unauthorized`。

> **wire 字段位置**: `export_policy_authorities[]` 位于 Realm `policy_components.export_policy_authorities` 路径下,由 `cx.profile.agent_workspace.governed.v1` 启用该字段的解析。reducer 在该 profile 未启用时忽略该字段。

**reducer 行为收紧**:见 §8.2"governed 行为"完整 reject 规则集。所有 reject 都是 reducer-time 硬性拒收;event 不进入 mirror Realm accepted set,不留下任何 read access。

**Permissive vs governed 选择**:

| 维度 | permissive(默认,`cx.profile.agent_workspace.v1`) | governed(`cx.profile.agent_workspace.governed.v1`) |
| --- | --- | --- |
| 适用场景 | 单 controller 自用 + 自审查 agent runtime | 企业 / 合规 / 跨 deployment / 第三方 agent runtime |
| 信任根 | "agent runtime 会自觉遵守 source export policy" | "源 Realm policy authority 签发 attestation" |
| 攻击窗口 | agent runtime 被攻陷 / buggy 可绕过 export | export attestation 签名失败即 reject |
| 性能成本 | import 0 额外回往 | import 需先取得 source-side attestation(一次回往 + TTL 缓存) |
| 默认决策 | 不拒绝,标 audit | reject 缺失 / 无效 attestation |

**实现要求**:支持 governed profile 的服务端 MUST:
- 在 `cx.server.describe.supported_features` 中声明 `cx.feature.governed_import.v1`
- 实现 §8.2 governed 行为完整 reject 规则
- 拒绝 attestation 时在响应 `reason_code` 中精确报告失败原因(便于 importer 调试)
- audit log 完整保留所有 reject 事件,作为合规取证基线

不支持 governed profile 的服务端在为 governed source 处理 import 时 MUST fail-closed(返回 `profile_unsupported`);**不得**降级为 permissive 处理。

### 9.2 `cx.profile.agent_workspace.lite.v1`(单 controller 轻量 profile)

**目的**:针对"controller 自己用、自己审、不需要 audit-grade 痕迹"的最小化部署(单 dev、hobbyist、本地实验),允许 mirror Realm 跳过 base agent workspace profile 中成本较高的 transparency/source_authority FSM 与强治理绑定语义,从而把实现门槛降低到一个"标准 Realm + reservation cell + import_attestation"即可上线的水平。

**applicability(必须同时满足)**:

- workspace_root + mirror Realm 均归属同一 controller principal,无第三方共享读
- 不打算公开 mirror Realm 内容做合规 / 监管 audit
- agent runtime 由 controller 自托管 / 自审查(与 base profile §1.1 假设一致甚至更强)
- 不打算把 mirror Realm 状态用作监管 / 法律证据

任一条不满足:**不得**采用 lite,SHOULD 留在 base `cx.profile.agent_workspace.v1`,或升级到 `cx.profile.agent_workspace.governed.v1`。

**从 base 中剥离(strict subset of writes)**:

| 维度 | base 默认 | lite |
| --- | --- | --- |
| transparency FSM cell(`agent_task.<id>.transparency`) | 必需,记录"源 stub 被 redact"等透明度信号 | **不存在**;controller 通过 UI hint 知道源 stub 状态,不写 cell |
| source_authority FSM cell(`agent_task.<id>.source_authority`) | 必需,记录"agent 被踢 / capability_grant revoke" | **不存在**;controller 通过 UI hint 看到,不写 cell |
| MLS Governance Binding(`mls_governance_binding.full.v1`) | 受 `mls_send_pause` 等 normative 规则约束 | 不强制要求 binding;mirror Realm MAY 维持普通 MLS group 即可 |
| `cx.agent_task.transparency.transition` / `source_authority.transition` event | reducer 接受 | **reducer reject**(`lite_profile_writes_disallowed_event_kind`) |

**从 base 保留(reads + cross-Realm writes 不变)**:

- `mirror_space_by_source` / `mirror_flow_by_source` reservation cell(失去这一层 mirror flow 无法被稳定寻址,无法工作)
- reservation cleanup 的 anchor-based TTL evidence(与 base 相同;lite 不接受 wall clock 或本地 monotonic clock 作为 reducer 依据)
- `agent_task.<id>.execution_state` cell(任务自身状态机,lite 仍需用来决定能否 publish-back)
- `cx.content.import_attestation` envelope(导入源内容仍需 attestation,只是 source-side export policy attestation 不强制)
- `cx.mention_redirect` content block 在源 Realm 一侧不变(源 Realm 是否接受不取决于 mirror profile)

**跨 Realm 边界 always full pipeline**:

publish-back(把 agent 草稿发回源 Flow)、`cx.mention_redirect` 投递、任何对源 Realm / 共享 Realm 的写入,**MUST** 走完整 pipeline(签名、capability、schema、源 Realm 的完整 lattice、目的 Realm 的 MLS group)。lite **不**是"跨 Realm 通信也能省略"的借口;它只松绑 mirror Realm 内部本地状态机。

**与 governed 互斥**:同一 Realm MUST NOT 同时声明 `cx.profile.agent_workspace.lite.v1` + `cx.profile.agent_workspace.governed.v1`——前者剥离 mirror 端 audit,后者要求 mirror 端硬执行源 export policy,二者目的相反;同时声明 reducer MUST reject `conflicting_agent_workspace_profiles`。

**Conformance**:实现 SHOULD 提供同一套 mirror Realm 既能跑 base 也能跑 lite 的测试 fixture(去掉 transparency / source_authority cell 后 base test 中所有读取这两个 cell 的步骤直接跳过 / 标 N/A),便于部署在 base ↔ lite 之间无破坏切换。

**升级路径**:lite → base 是允许的(下次 Realm schema update 时引入两个 FSM cell,初值 `ok`,旧 agent_task 不需要补 transition 历史)。base → lite 不允许(已存在的 transparency / source_authority cell 不能在不留 audit 的情况下删除)。

## 10. Workspace teardown / 跨 deployment 迁移

### 10.1 Teardown

Controller 不再使用 workspace：

1. Controller 写 `cx.realm.tombstone(workspace_root_realm_id)`（标准 Realm lifecycle）
2. 所有 mirror Realm 通过 `derived_from(workspace_root)` 关联，housekeeping 写 cascade `cx.realm.tombstone(mirror_realm_id)`
3. mirror Realm tombstone 后所有 agent_task 自动 unreachable；execution_state cell 不再 readable
4. 源 Realm 中已存在的 `mention_redirect` event **保留**（audit trail 不可逆）；它们的 `authority_grant_ref` 仍指向源 Realm 中的 grant，与 workspace teardown 解耦
5. DID Document 移除 `ContrixAgentWorkspaceService` service entry

### 10.2 跨 deployment 迁移

Controller 从 deployment A 迁到 deployment B：

1. 在 deployment B 创建新的 workspace root Realm
2. 写新 DID Document service entry，service endpoint 指向 deployment B
3. 旧 workspace（deployment A）保留作为 audit 历史；可标记 `migrated_to: <new_workspace_root_realm_id>`
4. 源 Realm 中已存在的 `mention_redirect` 与旧 workspace 关联（通过 `authority_grant_ref` 在源 Realm 中的 grant，与 deployment 无关）；新发的 `mention_redirect` 会通过新 DID resolve 到新 workspace
5. mirror Realm 内容**不自动迁移**——controller 可选导出 / 重新建立（迁移工具由独立 tooling profile 提供）

### 10.3 源 Realm archive / Flow delete

- 源 Flow `state=redacted` → mirror 中 `context_anchor` 引用 lazy `locked`（[relation.md §4.5](../models/relation.md)）
- 不触发 mirror task 状态变化（mirror 任务可能已完成，保留 audit 价值）

## 11. Service operations

### 11.1 `agent_workspace.resolve_mirror_flow`

```
GET /api/v1/agent_workspace/mirror_flow?source_flow_id=<id>
Authorization: DID-signed (controller's principal) or session token
→ 200 { "mirror_flow_id": "cx:flow:...", "mirror_realm_id": "cx:realm:..." }
→ 404 { "reason": "not_provisioned" }    # 仅对已鉴权 controller 返回
→ 401 / 403                              # 未鉴权或非 owner
```

- 仅 controller 自己可读
- MUST 不返回未完成 reservation（filter `reservation` + `create event` 都存在的 mapping）
- 未鉴权返回 401/403 而非 404（不暴露 workspace 存在性）

### 11.2 `agent_workspace.list_pending_tasks`

```
GET /api/v1/agent_workspace/pending_tasks
Authorization: DID-signed (controller's principal) or session token
→ 200 { "tasks": [{ "agent_task_id": "...", "execution_state": "pending_source_stub", ... }] }
```

- 仅列 execution_state ∈ {pending_source_stub, active} 的 task
- 用于客户端 reconcile 离线期间未完成的 Phase 2/3

## 12. DID Document service entry

```json
{
  "id": "did:web:alice.example#agent-workspace",
  "type": "ContrixAgentWorkspaceService",
  "serviceEndpoint": "https://alice-principal.example/api/v1/agent_workspace"
}
```

仅发布 HTTPS endpoint，不发布 `workspace_root_realm_id`（防元数据枚举）。

## 13. 生命周期场景

### 13.1 用户首次 @-自己的-agent（Saga）

**前置**：客户端调用 `resolve_mirror_flow(source_flow_id)`；不存在则按 §6 reservation saga lazy 创建 mirror Realm + Flow。

**Phase 1 — Mirror 端创建 pending task**：

1. 客户端生成 `redirect_pair_id`（UUIDv7）
2. 在 mirror Realm 写 `cx.agent_task.create`（初始化 3 cell：execution_state=pending_source_stub, transparency=ok, source_authority=ok）
3. Agent runtime 见 execution_state=`pending_source_stub` MUST NOT 执行

**Phase 2 — Source 端写 stub**：

4. 在源 Realm 写 `cx.message.create`，content = `cx.content.mention_redirect`，含 `redirect_pair_id` + `authority_grant_ref`，Event 顶层 `requirements.critical_extensions` 含 `cx.feature.mention_redirect.v1`

**Phase 3 — Mirror 端 reconcile**：

5. stub Move accepted 后，客户端写 `cx.agent_task.execution.transition(from=pending_source_stub, to=active, evidence_refs=[<source stub event id>])`
6. Agent runtime 见三 cell 满足 gate 才开始执行

**失败路径**：

- Phase 2 reject → 写 `execution.transition(from=pending_source_stub, to=cancelled_stub_rejected)`
- Phase 1 成功但 Phase 2/3 未完成 → TTL 后 sync node housekeeping 写 `execution.transition(to=cancelled_orphan)`

### 13.2 源 Realm 加 / 移除 agent

加：标准 `cx.invite.create` + `cx.member.state` + `cx.capability.grant`（含 `attached_authority`）。reducer 验证 attached_authority.controller == inviter principal。成功后推 `agent_membership_change` notification 到 controller's workspace。

移：标准 `cx.capability.revoke` + `cx.member.state(removed)`。Watcher 触发 source_authority cell transition（见 §13.5）。

### 13.3 用户在 mirror Realm 加 consulting agent

Controller 在 mirror Realm 写 `cx.member.state(agent_Z)` + `cx.capability.grant`。Reducer 验证 agent_Z 的 attached_authority.controller == controller principal。**agent_Z 不自动获得源 Realm 访问**——它只工作于 mirror 中已存在内容（含 primary agent import_attestation 引入的）。

### 13.4 Source stub 被 redact → transparency=lost（observe-then-write）

1. Watcher 观察源 Realm `cx.redaction(target=<mention_redirect event>)` anchored
2. Watcher **先读** transparency cell 当前 head：
   - 当前 = `ok` → 写 `cx.agent_task.transparency.transition(from=ok, to=lost, evidence_refs=[<redaction event>])`
   - 当前 ∈ {`lost`, `reconfirmed_after_loss`} → no-op skip
3. Agent runtime 见 transparency=`lost` 停止执行
4. Controller 决策：
   - 继续：写 `transparency.transition(from=lost, to=reconfirmed_after_loss)`
   - 取消整任务：写 `execution.transition(from=active, to=cancelled_by_controller)`

### 13.5 Source grant revoke → source_authority=revoked

1. Watcher 观察源 Realm `cx.capability.revoke(grant=<agent_grant>)` anchored
2. 对该 agent 所有 execution_state ∈ {pending_source_stub, active} 的 mirror task：
   - **先读** source_authority cell 当前 head
   - 当前 = `ok` → 写 `cx.agent_task.source_authority.transition(from=ok, to=revoked, evidence_refs=[<revoke event>])`
   - 当前 ∈ {`revoked`, `reconfirmed_after_revoke`} → no-op skip
3. Agent runtime 因 source_authority=`revoked` 不满足 gate，停止执行
4. Controller 决策：
   - 继续：写 `source_authority.transition(from=revoked, to=reconfirmed_after_revoke)`
   - 取消整任务：写 `execution.transition(to=cancelled_by_controller)`

### 13.6 反向写回（agent → source Flow）

v1 默认 controller 手动 publish：

1. Mirror Flow 中 agent 产出 `cx.message.create`（content 为草稿）；用 `cx.relation.references(from=draft_message, to=agent_task_id)` 关联
2. Controller 编辑 / 修改 / 追问 agent 重写
3. Controller 满意后点 "publish"：
   - 在源 Flow 写 `cx.message.create` 时，Event 顶层 **`actor_id = controller principal`**（不是 agent）；物化 Message 的 `created_by` 由 reducer 从该 `actor_id` 派生。
   - content MAY 含 `cx.content.import_attestation` 标注 agent 草稿（audit 透明，由 Alice 决定披露程度）
   - **read-then-write**：先读 `agent_task.<id>.execution_state` cell head：
     - 当前 = `active` → 写 `execution.transition(from=active, to=completed)`
     - 当前 ∈ terminal → abort publish 流程，告知 controller "任务已不在 active"

## 14. Cross-Realm agent membership 变更通知

新 notification type `agent_membership_change`，已加入 [private-objects.md §3.2](../models/private-objects.md) 的 `notification_type` enum 与 [`notification.schema.json`](../../artifacts/schemas/notification.schema.json)。[push-notifications.md](../discovery/push-notifications.md) 的 rule 引擎按现有 `notification_type` 字段匹配，无需新增 rule kind。

```json
{
  "notification_type": "agent_membership_change",
  "source_event_id": "cx:event:<membership change in source Flow>",
  "realm_id": "cx:realm:<workspace root or mirror realm>",
  "preview": {
    "change_kind": "add | remove | profile_change",
    "agent_did": "did:web:alice-agent.example",
    "source_realm_id": "cx:realm:<source>",
    "source_flow_id": "cx:flow:<source>",
    "new_capability_profile": "cx.agent_member.read_only"
  }
}
```

- 推送目标 = agent 的 `agent_authority.controller` principal
- E2EE preview MUST 由客户端预先脱敏；服务端不得明文重写

## 15. Conformance vectors

本 profile MUST 提供 44 个 conformance vector，分组如下。Vector fixtures 位于 `artifacts/conformance/agent-workspace/`。

### 15.1 execution_state FSM（12 vectors）

合法 transition（9）：
1. `[create] → pending_source_stub`
2. `[create] → active`（direct task）
3. `pending_source_stub → active`
4. `pending_source_stub → cancelled_stub_rejected`
5. `pending_source_stub → cancelled_orphan`
6. `pending_source_stub → cancelled_by_controller`
7. `active → completed`
8. `active → cancelled_by_controller`
9. Multiple watcher 写**同一** execution_state transition（例如 controller's client 与 agent runtime 同时尝试 `from=active, to=cancelled_by_controller`）→ 第一个 accepted，第二个 FSM `from` precondition 不再成立 → `failed_precondition` no-op。（transparency / source_authority cell 的多 watcher idempotent 在 §15.2 / §15.3 单独覆盖）

非法 transition（3）：
10. `completed → active` → `failed_precondition(invalid_task_fsm_transition)`
11. `cancelled_by_controller → active` → 同上
12. `active → pending_source_stub` → 同上

### 15.2 transparency FSM（4 vectors）

合法（2）：
13. `ok → lost`
14. `lost → reconfirmed_after_loss`

非法（2）：
15. `reconfirmed_after_loss → lost` → reject
16. `ok → reconfirmed_after_loss` → reject

### 15.3 source_authority FSM（4 vectors）

合法（2）：
17. `ok → revoked`
18. `revoked → reconfirmed_after_revoke`

非法（2）：
19. `reconfirmed_after_revoke → ok` → reject
20. `reconfirmed_after_revoke → revoked` → reject

### 15.4 Reservation / recovery（6 vectors）

21. **单 server 并发**：两 client 同时请求 → server validate_op 拒绝第二个，返回 `reservation_cell_already_set`
22. **多 master 并发 → ⊥**：两 Move 在不同 sync node anchor，cell → ⊥
23. **Recovery Move 收敛 winner**：客户端写 recovery Move（含 head_in + state_witness + inclusion_proof + recovery_capability），cell 收敛到 lex-min winner
24. **Recovery 缺 critical refs reject**：缺 state_witness 或 inclusion_proof → reject
25. **Recovery 无 capability reject**：issuer 无 `cx.capability.agent_workspace.recover` → `capability_denied`
26. **Orphan TTL cleanup**：reservation 后 follow-up create 未在 TTL 内 → housekeeping cleanup → cell 回到 `"__unset__"`

### 15.5 mention_redirect（5 vectors）

27. **不暴露 private IDs**：source Flow 第三方 reader MUST NOT 从 stub 字段提取 mirror IDs
28. **Target 必须 sender 的 agent**：sender ≠ grant.attached_authority.controller → `capability_denied` reject
29. **不降级为普通 mention**：critical_extension `fail_closed=true` → 未声明支持 MUST reject
30. **authority_grant_ref 校验**：grant 已 revoked / subject 不匹配 / attached_authority.controller 不匹配 → `capability_denied`
31. **`scope=payload` 合法 schema**：critical_extension 用合法 enum，schema validation 通过

### 15.6 import_attestation（5 vectors）

32. **import_signature 校验**：篡改 → reader 标记 `import_signature_invalid`
33. **content_hash 校验**：篡改 content → 标记 `content_hash_mismatch`
34. **`unverifiable_origin`**：claimed_origin 不可独立验证（不是"伪造"）
35. **`export_attestation_missing` 不拒绝**：缺 attestation → 接受但 audit 标记 missing
36. **`export_attestation_verified`**：完整 attestation + signature 有效 → audit 标记 verified

### 15.7 Saga / observe-then-write（5 vectors）

37. **Phase 2 reject → cancelled_stub_rejected**
38. **Source stub redact → transparency=lost**：watcher read-then-write 模式
39. **二次失效场景**：transparency=lost 同时 source_authority=revoked，两 cell 独立写入
40. **Cross-deployment watcher**：watcher 在不同 deployment 仍能观察 source 写入 mirror
41. **Reverse publish read-then-write**：controller publish 时另一设备已 cancel → publish abort

### 15.8 跨域 / 治理（3 vectors）

42. **Mirror Realm derived_from 基数**：尝试同 source Flow 第二个 mirror Flow → `cardinality_violation`
43. **agent_membership_change 通知脱敏**：E2EE preview MUST 由客户端预先脱敏
44. **Teardown 审计锚定**：workspace teardown 提交前 MUST 留下最终 audit anchor，外部系统在 Realm 删除后仍可引用

## 16. 安全 / 隐私要点

- **DID Document 不暴露 workspace Realm ID**：service entry 仅 HTTPS endpoint；workspace_root_realm_id 通过鉴权后 resolve API 取得；未鉴权 GET 返回 401/403 不返 404
- **mention_redirect 不暴露 mirror 端定位**：仅含 `redirect_pair_id`（sender opaque UUID）和 `authority_grant_ref`（指向源 Realm 已 active 的 grant）
- **`body` 字段披露**：客户端 MUST 提示用户该字段对源 Flow 成员可见
- **Watcher 撒谎防护**：`evidence_refs` 含可独立 fetch 验证的 event ID；多 watcher 并行 + TTL housekeeping 兜底
- **Cleanup 滥用防护**：cleanup Move MUST 携带 anchor-based `ttl_evidence`（详见 §6.4）；reducer 验证 `current_anchor_index >= reservation_anchor_index + ttl_anchor_distance`，**不接受自报 wall-clock**

## 17. 显式不在 v1 范围

- ❌ `cx.grant.delegate_read`（scoped read 委托）：MLS E2EE 下无法干净实现；`knowledge_sources[]` + import_attestation 已覆盖
- ❌ Server-side @ mention 自动路由：routing 是 client UX，server 不重写消息
- ❌ `on_behalf_of` Message 字段：v1 由 controller 手动 publish 覆盖（§13.6）
- ❌ Mirror Realm deterministic 命名 `f(controller, source_space) → mirror_id`
- ❌ `attached_authority.inline_copy` evidence_kind（air-gapped 场景延后到独立扩展 profile）
- ❌ Workspace 内容跨 deployment 自动迁移（迁移工具由独立 tooling profile 提供）

## 18. 规范性引用

- 公共字段：[common-fields.md](../models/common-fields.md)
- Capabilities：[capabilities.md](../authz/capabilities.md)
- Event auth / lattice：[event-auth-state-resolution.md](../authz/event-auth-state-resolution.md)
- Encryption / agent authority：[encryption-and-audit.md](../crypto-media/encryption-and-audit.md)
- Push notifications：[push-notifications.md](../discovery/push-notifications.md)
- Content types：[content-types.md](../models/content-types.md)
- Relation cross-Realm：[relation.md](../models/relation.md)
- Federation：[federation.md](../sync/federation.md)
- Service binding：[service-http-binding.md](../sync/service-http-binding.md)
- Encoding (JCS)：[encoding.md](../conformance/encoding.md)
- Agent protocol interop：[agent-protocol-interop.md](./agent-protocol-interop.md)
