---
title: Agent Workspace Profile
sidebar:
  label: Agent Workspace
---

> **状态：extension profile（非 v1 core 互操作必需）**。本文档定义 `cx.profile.agent_workspace.v1`——允许用户在源协作 Space 中调用自己的 agent 干活，同时把"agent 透明度"（公开 mention）与"agent 工作过程"（私人 mirror Space）分离。Contrix v1 core 互操作 **不要求** 实现 agent workspace；不实现的 client/server 通过 `cx.feature.mention_redirect.v1` critical_extension 检查自然 fail-closed。
>
> 设计历史与多轮 review 见 `proposal_agent_workspace.md`（仓库根目录）。本文档是 normative 合并视图。

## 1. 目标

用户经常需要在协作 Flow（工作群、项目讨论）中调用自己的 AI agent 干活，同时希望：

- **指令内容不暴露**给 Flow 其他成员（私密性）
- **agent 的存在与权限范围**对 Flow 其他成员可见（透明度 / 信任）
- agent 团队的复杂度（多个专长 agent、内部讨论、试错过程）**不污染源 Flow**
- 跨多个源 Space 工作时有**统一入口**回到自己的 agent workspace

本 profile 提供的核心机制：

1. Agent 通过标准 `cx.member.state` 加入源 Space，公开声明
2. 用户的 principal server 上有一个 **agent workspace root Space**（per-controller，DID Document advertise）
3. 用户在源 Flow `@my-agent` 时，触发 mention_redirect content block 作为 source-side stub + 私密指令落到 mirror Space 的 `agent_task` 对象
4. Agent 在 mirror Space 工作；通过 import_attestation 把源 Space 内容重加密到 mirror Space 工作上下文
5. 任务完成后 controller 决定是否将 agent 产出 publish 回源 Flow

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│   Source Space（公开协作 / 组织 / 项目）                    │
│   ┌──────────────────────┐                                  │
│   │ Source Flow          │  agent_X 作为 Space member 加入  │
│   │  - Alice             │  capability constraint           │
│   │  - Bob               │  (read_only / mention_respond)   │
│   │  - agent_X (Alice's) │                                  │
│   │                      │  Alice 写 cx.content.mention_     │
│   │                      │  redirect → source-side stub     │
│   └──────────────────────┘                                  │
└───────────────────│─────────────────────────────────────────┘
                    │ derived_from (cross-Space references)
                    │ + cx.content.import_attestation
                    ▼
┌─────────────────────────────────────────────────────────────┐
│   Alice's Agent Workspace Root Space（DID Doc advertise）   │
│   ┌──────────────────────────┐                              │
│   │ Mirror Space             │  members = Alice + her agents│
│   │  per source Space        │  独立 MLS group / E2EE 边界  │
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
| 源 Space 的 agent membership | 源 Space governance（可能是 Space admin、organization admin） | 公开协作的"声明" |
| Workspace / Mirror Space 的成员 | controller 独占 | 私人工作流的"组队" |

**不自动同步**；变更通过 notification 推送，controller 显式决定。

## 3. 标准化协议表面

| 类别 | 名称 | 描述 |
|---|---|---|
| Space profile | `cx.profile.agent_workspace.v1` | Workspace root + mirror Space 的 schema 约束 |
| 对象 | `cx.schema.agent_task.v1` | mirror Space 内的任务对象 |
| Typed ID | `cx:agent_task:` | UUIDv7 |
| Event | `cx.agent_task.create` | 创建 agent_task |
| Event | `cx.agent_task.execution.transition` | execution_state cell transition |
| Event | `cx.agent_task.transparency.transition` | transparency cell transition |
| Event | `cx.agent_task.source_authority.transition` | source_authority cell transition |
| Event | `cx.agent_task.cancel` | 便捷取消（alias） |
| Content block | `cx.content.mention_redirect` | 源 Space 中的 routing stub |
| Content block | `cx.content.import_attestation` | mirror Space 中的跨 Space 重加密引用 |
| Capability action | `cx.capability.agent_workspace.reserve` | 写 reservation Move |
| Capability action | `cx.capability.agent_workspace.recover` | 写 recovery Move |
| Capability action | `cx.capability.agent_workspace.cleanup` | 写 orphan cleanup Move |
| Capability constraint kind | `mention_respond_only` | agent 仅在被 @ 时回复 |
| Capability constraint kind | `import_to_external_space` | source-side policy：是否允许 import 到外部 Space |
| Cell namespace | `mirror_space_by_source` | workspace root 内的 source→mirror Space 唯一性 cell |
| Cell namespace | `mirror_flow_by_source` | mirror Space 内的 source→mirror Flow 唯一性 cell |
| Cell namespace | `agent_task.<id>.execution_state` | per-task execution FSM |
| Cell namespace | `agent_task.<id>.transparency` | per-task transparency FSM |
| Cell namespace | `agent_task.<id>.source_authority` | per-task source_authority FSM |
| Feature id | `cx.feature.mention_redirect.v1` | critical_extension marker |
| Feature id | `cx.feature.import_attestation.v1` | critical_extension marker |
| Notification type | `agent_membership_change` | 源 Space agent 成员变更通知到 controller |
| Service operation | `agent_workspace.resolve_mirror_flow` | controller-only resolve |
| Service operation | `agent_workspace.list_pending_tasks` | controller-only orphan reconciliation |
| DID Document service | `ContrixAgentWorkspaceService` | HTTPS endpoint，鉴权后 resolve workspace_root_space_id |

## 4. Agent 加入源 Space（路径 A / B）

Spec v1 中**没有 Flow-level membership**（[flow.schema.json](../../artifacts/schemas/flow.schema.json) 无 members 字段）。Agent 加入有两种 per-Flow scoping 路径：

**路径 A（默认，粗粒度）**：Agent 加入源 **Space**
- Agent 拿到 Space 级 MLS 解密边界，能看 Space 内所有 Flow
- Capability constraint 限定写权限到具体 Flow（`object_ref=cx:flow:...`）
- 适合"agent 对整个项目都可见"

**路径 B（细粒度）**：源 Flow 先设置 `discussion_space_ref` 指向 child Space；agent 加入 child Space
- Agent 只看该 Flow 讨论时间线
- Child Space 独立 MLS group / retention / history visibility
- 要求源 Flow 提前规划 `discussion_space_ref`

本 profile 不强制选择；source Space admin / Flow creator 自决。Mirror 端通过 `derived_from` Relation 指向源对象，不关心源是 A 还是 B。

**邀请 agent 的标准流程**（不引入新 event kind）：

1. inviter 写 `cx.invite.create` 携带 `capability_grant_refs[]`
2. agent accept 后 reducer 写 `cx.member.state(actor=agent_did, state=member)` + 对应 `cx.capability.grant`
3. capability grant 的 `attached_authority` 字段（见 §5）证明 agent 由 inviter principal 控制

**标准 capability constraint preset（normative pattern）**：

| Preset name | 含义 | 展开为标准 grant 的 actions |
|---|---|---|
| `cx.agent_member.observer` | 只观察 | `read_history`, `read_messages` |
| `cx.agent_member.read_only` | 只读 + 反应 | observer + `react` |
| `cx.agent_member.mention_respond_only` | 仅在被 @ 时回复 | read_only + `message.create where in_reply_to.mentions=self` (使用新 constraint kind `mention_respond_only`) |
| `cx.agent_member.full_collaborator` | 完整成员 | 标准 member capability set |

Preset 是声明性 sugar；reducer 不依赖 preset name，依赖展开后的 grant。

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

> v1 仅支持 `anchored_event_ref` 和 `state_witness` 两种 evidence_kind。Rev 7 草案的 `inline_copy` 已删除（air-gapped 场景推迟到 v2，避免 grant event 体积膨胀）。

**Reducer 校验**：

- `evidence_kind=anchored_event_ref`：reducer SHOULD 异步通过 controller's principal server 验证 inclusion proof；不可达时降级为 `unverified_authority` 标记但仍可接受 grant
- `evidence_kind=state_witness`：reducer 校验 `witness_signature` 由 controller's principal server 当前注册的 key 签发；TTL 由 `valid_until` 控制；过期后 grant 自动失效

## 6. Mirror Space 创建与并发竞态（reservation saga）

### 6.1 双层 reservation cell

| 层 | Cell key | 命名空间 | Cell value | Lattice |
|---|---|---|---|---|
| **L1** | `mirror_space_by_source:<source_space_id>` | **workspace root Space** | `cx:space:<mirror_space_id>` 或 sentinel | `cas-register + bottom=reject`，schema 声明 `initial_value="__unset__"` |
| **L2** | `mirror_flow_by_source:<source_flow_id>` | **mirror Space** | `cx:flow:<mirror_flow_id>` 或 sentinel | 同上 |

> **Spec PR 依赖**：当前 cell schema 没有 `initial_value` 字段。本 profile 落地依赖该字段被 spec 接受。在该字段落地前，实现 MAY 在 Space genesis 时显式写"初始化所有已知 reservation cell 为 `'__unset__'`"Move（实际不可枚举所有 source_space_id，仅作为 fallback）。

### 6.2 Reservation 流程

1. 客户端调用 `agent_workspace.resolve_mirror_flow(source_flow_id)`；存在则复用
2. 若 query 返回空，客户端**预分配** UUIDv7 `mirror_space_id` 和 `mirror_flow_id`
3. **L1 reservation Move**（workspace root Space）：
   - lattice op：`set`，cell = `mirror_space_by_source:<source_space_id>`，value = `mirror_space_id`
   - predicate：`head_eq: "__unset__"`
   - capability：controller's `cx.capability.agent_workspace.reserve` grant
4. L1 收敛三种情况：
   - **happy path**（cell 当前 head = `"__unset__"`，predicate 满足）：lattice op accepted，cell 推进到 `mirror_space_id`
   - **cell 已 set**（cell 当前 head = existing_id，predicate `head_eq:"__unset__"` 不满足）：按 [event-auth-state-resolution.md:640](../authz/event-auth-state-resolution.md) `if not predicate(v): FAIL_PRECONDITION` → reducer 返回 `failed_precondition`（reason=`reservation_cell_already_set`，response 含 winner cell value）。**不进入 ⊥**——⊥ 只发生在 lattice join 阶段，predicate 不满足在 join 之前的 validation 阶段就 fail
   - **真并发同时写不同 reservation token**（causally concurrent，双方 predicate 都满足）：lattice join 阶段 siblings `(unset, idA)` 和 `(unset, idB)` 满足 `b1==b2 and v1!=v2` → cell → `⊥`（bottom=reject，依赖该 cell 的后续 Move MUST `failed_bottom`），触发 §6.3 recovery saga
5. **L1 成功后**，写独立后续 `cx.space.create(id=mirror_space_id)` Move 到 controller 的 principal control stream
6. mirror Space 存在后写 **L2 reservation Move**，同样 `head_eq: "__unset__"`
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
- Deterministic winner：lex-min on candidate `cx:space:` / `cx:flow:` UUIDv7 字符串
- State_witness / inclusion_proof MUST `critical=true`

### 6.4 Orphan reservation 处理

> **Rev 9 修订**：原 Rev 8 写 "reservation Move effects 携带 `reservation_ttl_seconds`" 不合规——[event-schema.json:1125](../../artifacts/schemas/event-schema.json) `lattice_op` `additionalProperties: false`，wire 上无法附加自定义字段。TTL 改放到 event payload；clock 改用 Anchor-based time，不用自报 wall clock。

1. **TTL 存放位置（修订）**：reservation Move 的 **Event payload** 顶层携带可选 `reservation_ttl_seconds`（默认 600s）字段，由 `cx.agent_task.reservation_meta.v1` payload class 定义。**不**塞进 `lattice_op` metadata。
2. **Resolve API filtering**：`resolve_mirror_flow` MUST 仅返回 reservation + create Move 都存在的 mapping，不返回未完成 reservation
3. **Cleanup Move（Rev 9 修订）**：
   - Capability holder：**仅 controller principal**；可标准 capability delegation 给自己 sync node 的 system actor
   - lattice op：`set`，cell = `mirror_*_by_source:<source_id>`，value = `"__unset__"`
   - predicate：`head_eq: <reservation_id>`（指向当前 stale value）
   - **TTL 证据（Anchor-based time，不用自报 wall clock）**：cleanup Event payload MUST 携带 `ttl_evidence: { reservation_anchor_ref, reservation_anchor_index, current_anchor_ref, current_anchor_index, ttl_anchor_distance }`：
     - `reservation_anchor_ref` / `reservation_anchor_index`：reservation Move 被 anchor 时的 Anchor 引用 + 该 Anchor 在 DAG 中的 index（由源 Space anchorer 签发，可独立验证）
     - `current_anchor_ref` / `current_anchor_index`：cleanup 提交时刻的 effective Anchor
     - reducer 验证：`current_anchor_index >= reservation_anchor_index + ttl_anchor_distance`，其中 `ttl_anchor_distance` 是 schema 声明的最小 anchor 距离（按典型 anchor cadence 折算自 600s）
   - **替代方案**（更弱但实现简单）：housekeeping authority（controller 自己的 sync node）以 system actor 签发 `clock_witness` attestation 携带 `signed_current_time`；reducer 验证签名 + 接受 issuer 自报时间。这条仅适用于单 server 部署，不适用 multi-master
4. **Idempotent retry**：`cx.space.create.id` / `cx.flow.create.id` 是固定 UUIDv7，重试相同 ID 是 no-op

## 7. `agent_task` 对象与三正交 FSM

### 7.1 对象 schema

```json
{
  "id": "cx:agent_task:01964200-0000-7000-8000-cccccccccccc",
  "schema": "cx.schema.agent_task.v1",
  "space_id": "cx:space:<mirror space>",
  "flow_id": "cx:flow:<mirror flow>",
  "target_agent_id": "did:web:alice-agent.example",
  "instruction": {
    "kind": "cx.content.text",
    "body": "总结源 Flow 的讨论并起草回复",
    "format": "markdown"
  },
  "encrypted_payload": null,
  "context_anchor": {
    "source_space_id": "cx:space:<source>",
    "source_flow_id": "cx:flow:<source>",
    "source_anchor_ref": "cx:anchor:<frontier at trigger time>",
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
- `target_actor_id`：MUST 是 sender principal 的 controlled agent（通过 `authority_grant_ref` 解析的 grant 的 `attached_authority.controller == sender_principal` 验证）；不满足 reducer MUST `unauthorized` reject（不降级为普通 `cx.content.mention`）
- `authority_grant_ref`：引用源 Space 中已 active 的 grant；reducer 校验 grant active + grant.subject == target_actor_id + grant.attached_authority.controller == sender principal
- `redirect_pair_id`：opaque UUIDv7，sender 生成；双端关联，不暴露 mirror Space / Flow / Event ID

### 8.2 `cx.content.import_attestation`

```json
{
  "kind": "cx.content.import_attestation",
  "body": "（重加密引入的源消息正文 - 纯文本 fallback）",
  "claimed_origin": {
    "space_id": "cx:space:<source>",
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
    "source_frontier_ref": "cx:anchor:<导入时源 Space frontier>"
  },
  "source_export_policy_attestation": null,
  "content": { "kind": "cx.content.text", "body": "..." }
}
```

**性质**：这是 "importer 声称'我从某 Space 看到了这条内容'"，`import_signature` 只能证明 importer 自己的声明，**不能**证明原作者明文确实如此。reader UI MUST 显著区分"原作者直接发言"vs"由 X importer 声称引自"。

**Source export policy attestation**（可选；如携带 MUST 满足 canonical schema）：

```json
{
  "authority_did": "did:web:source-space-admin.example",
  "source_space_id": "cx:space:<source>",
  "policy_hash": "sha256:...",
  "policy_decision": "allow",
  "importer_actor_id": "did:web:alice-agent.example",
  "import_destination_space_id": "cx:space:<mirror>",
  "content_hash": "sha256:...",
  "source_frontier_ref": "cx:anchor:...",
  "issued_at": "2026-05-17T10:00:00Z",
  "valid_until": "2026-05-17T11:00:00Z",
  "signature": "..."
}
```

- `content_hash`：JCS-canonicalized JSON of the `content` field + SHA-256 + `sha256:` 前缀。复用 [encoding.md](../conformance/encoding.md) RFC 8785/JCS profile
- `signature` canonical signing input = JCS-canonicalized `{schema_id: "cx.schema.content.source_export_policy_attestation.v1", domain: "cx.domain.export_policy_attestation.v1", body: <除 signature 外的所有 required 字段>}` + SHA-256

**Mirror reducer 行为**（不强制 export policy）：

- 缺 attestation → 接受 event，audit 标记 `export_attestation_missing`
- 携带但签名无效 / 字段不一致 → 接受 event，audit 标记 `export_attestation_invalid`
- 签名有效 → 接受 event，audit 标记 `export_attestation_verified`
- **任何情况都不拒绝**——mirror 无能力判断源 policy；真正的 export gate 在 source-side agent runtime（agent runtime conformance profile 可把该检查从 SHOULD 抬到 MUST）

## 9. Space profile `cx.profile.agent_workspace.v1`

```json
{
  "profile_id": "cx.profile.agent_workspace.v1",
  "scope": "space",
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
      "initial_value": "__unset__"
    },
    {
      "namespace": "mirror_flow_by_source",
      "applies_to_role": "mirror_space",
      "lattice": "cas-register",
      "bottom": "reject",
      "initial_value": "__unset__"
    }
  ],
  "relation_profiles": [
    {
      "relation_kind": "derived_from",
      "from_type": "space",
      "to_type": "space",
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

- Workspace root Space owner = controller principal
- Members = `{controller's authorized devices} ∪ {agents with active capability_grant.attached_authority.controller == workspace_owner}`
- 加入通过标准 `cx.member.state`；不引入新 `workspace_visible` 字段
- Mirror Space 继承相同 membership 规则

**Unsupported profile fail-closed**：未声明支持本 profile 的服务端 **对 mirror Space 写入** MUST fail-closed（拒绝 `cx.agent_task.*` / `cx.content.import_attestation`，返回 `profile_unsupported`）。源 Space 接受 `mention_redirect` 不依赖本 profile——依赖 `cx.feature.mention_redirect.v1` critical_extension 是否被源 Space 服务端支持。

## 10. Workspace teardown / 跨 deployment 迁移

### 10.1 Teardown

Controller 不再使用 workspace：

1. Controller 写 `cx.space.tombstone(workspace_root_space_id)`（标准 Space lifecycle）
2. 所有 mirror Space 通过 `derived_from(workspace_root)` 关联，housekeeping 写 cascade `cx.space.tombstone(mirror_space_id)`
3. mirror Space tombstone 后所有 agent_task 自动 unreachable；execution_state cell 不再 readable
4. 源 Space 中已存在的 `mention_redirect` event **保留**（audit trail 不可逆）；它们的 `authority_grant_ref` 仍指向源 Space 中的 grant，与 workspace teardown 解耦
5. DID Document 移除 `ContrixAgentWorkspaceService` service entry

### 10.2 跨 deployment 迁移

Controller 从 deployment A 迁到 deployment B：

1. 在 deployment B 创建新的 workspace root Space
2. 写新 DID Document service entry，service endpoint 指向 deployment B
3. 旧 workspace（deployment A）保留作为 audit 历史；可标记 `migrated_to: <new_workspace_root_space_id>`
4. 源 Space 中已存在的 `mention_redirect` 与旧 workspace 关联（通过 `authority_grant_ref` 在源 Space 中的 grant，与 deployment 无关）；新发的 `mention_redirect` 会通过新 DID resolve 到新 workspace
5. mirror Space 内容**不自动迁移**——controller 可选导出 / 重新建立（v2 提供工具）

### 10.3 源 Space archive / Flow delete

- 源 Flow `state=deleted` → mirror 中 `context_anchor` 引用 lazy `locked`（[relation.md §4.5](../models/relation.md)）
- 不触发 mirror task 状态变化（mirror 任务可能已完成，保留 audit 价值）

## 11. Service operations

### 11.1 `agent_workspace.resolve_mirror_flow`

```
GET /api/v1/agent_workspace/mirror_flow?source_flow_id=<id>
Authorization: DID-signed (controller's principal) or session token
→ 200 { "mirror_flow_id": "cx:flow:...", "mirror_space_id": "cx:space:..." }
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

仅发布 HTTPS endpoint，不发布 `workspace_root_space_id`（防元数据枚举）。

## 13. 生命周期场景

### 13.1 用户首次 @-自己的-agent（Saga）

**前置**：客户端调用 `resolve_mirror_flow(source_flow_id)`；不存在则按 §6 reservation saga lazy 创建 mirror Space + Flow。

**Phase 1 — Mirror 端创建 pending task**：

1. 客户端生成 `redirect_pair_id`（UUIDv7）
2. 在 mirror Space 写 `cx.agent_task.create`（初始化 3 cell：execution_state=pending_source_stub, transparency=ok, source_authority=ok）
3. Agent runtime 见 execution_state=`pending_source_stub` MUST NOT 执行

**Phase 2 — Source 端写 stub**：

4. 在源 Space 写 `cx.message.create`，content = `cx.content.mention_redirect`，含 `redirect_pair_id` + `authority_grant_ref`，Event 顶层 `requirements.critical_extensions` 含 `cx.feature.mention_redirect.v1`

**Phase 3 — Mirror 端 reconcile**：

5. stub Move accepted 后，客户端写 `cx.agent_task.execution.transition(from=pending_source_stub, to=active, evidence_refs=[<source stub event id>])`
6. Agent runtime 见三 cell 满足 gate 才开始执行

**失败路径**：

- Phase 2 reject → 写 `execution.transition(from=pending_source_stub, to=cancelled_stub_rejected)`
- Phase 1 成功但 Phase 2/3 未完成 → TTL 后 sync node housekeeping 写 `execution.transition(to=cancelled_orphan)`

### 13.2 源 Space 加 / 移除 agent

加：标准 `cx.invite.create` + `cx.member.state` + `cx.capability.grant`（含 `attached_authority`）。reducer 验证 attached_authority.controller == inviter principal。成功后推 `agent_membership_change` notification 到 controller's workspace。

移：标准 `cx.capability.revoke` + `cx.member.state(removed)`。Watcher 触发 source_authority cell transition（见 §13.5）。

### 13.3 用户在 mirror Space 加 consulting agent

Controller 在 mirror Space 写 `cx.member.state(agent_Z)` + `cx.capability.grant`。Reducer 验证 agent_Z 的 attached_authority.controller == controller principal。**agent_Z 不自动获得源 Space 访问**——它只工作于 mirror 中已存在内容（含 primary agent import_attestation 引入的）。

### 13.4 Source stub 被 redact → transparency=lost（observe-then-write）

1. Watcher 观察源 Space `cx.redaction(target=<mention_redirect event>)` anchored
2. Watcher **先读** transparency cell 当前 head：
   - 当前 = `ok` → 写 `cx.agent_task.transparency.transition(from=ok, to=lost, evidence_refs=[<redaction event>])`
   - 当前 ∈ {`lost`, `reconfirmed_after_loss`} → no-op skip
3. Agent runtime 见 transparency=`lost` 停止执行
4. Controller 决策：
   - 继续：写 `transparency.transition(from=lost, to=reconfirmed_after_loss)`
   - 取消整任务：写 `execution.transition(from=active, to=cancelled_by_controller)`

### 13.5 Source grant revoke → source_authority=revoked

1. Watcher 观察源 Space `cx.capability.revoke(grant=<agent_grant>)` anchored
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
   - 在源 Flow 写 `cx.message.create`，**`created_by = controller principal`**（不是 agent）
   - content MAY 含 `cx.content.import_attestation` 标注 agent 草稿（audit 透明，由 Alice 决定披露程度）
   - **read-then-write**：先读 `agent_task.<id>.execution_state` cell head：
     - 当前 = `active` → 写 `execution.transition(from=active, to=completed)`
     - 当前 ∈ terminal → abort publish 流程，告知 controller "任务已不在 active"

## 14. Cross-Space agent membership 变更通知

新 notification type `agent_membership_change`，已加入 [private-objects.md §3.2](../models/private-objects.md) 的 `notification_type` enum 与 [`notification.schema.json`](../../artifacts/schemas/notification.schema.json)。[push-notifications.md](../discovery/push-notifications.md) 的 rule 引擎按现有 `notification_type` 字段匹配，无需新增 rule kind。

```json
{
  "notification_type": "agent_membership_change",
  "source_event_id": "cx:event:<membership change in source Flow>",
  "space_id": "cx:space:<workspace root or mirror space>",
  "preview": {
    "change_kind": "add | remove | profile_change",
    "agent_did": "did:web:alice-agent.example",
    "source_space_id": "cx:space:<source>",
    "source_flow_id": "cx:flow:<source>",
    "new_capability_profile": "cx.agent_member.read_only"
  }
}
```

- 推送目标 = agent 的 `agent_authority.controller` principal
- E2EE preview MUST 由客户端预先脱敏；服务端不得明文重写

## 15. Conformance vectors

本 profile MUST 提供 43 个 conformance vector，分组如下。Vector fixtures 位于 `artifacts/conformance/agent-workspace/`。

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
25. **Recovery 无 capability reject**：issuer 无 `cx.capability.agent_workspace.recover` → `unauthorized`
26. **Orphan TTL cleanup**：reservation 后 follow-up create 未在 TTL 内 → housekeeping cleanup → cell 回到 `"__unset__"`

### 15.5 mention_redirect（5 vectors）

27. **不暴露 private IDs**：source Flow 第三方 reader MUST NOT 从 stub 字段提取 mirror IDs
28. **Target 必须 sender 的 agent**：sender ≠ grant.attached_authority.controller → `unauthorized` reject
29. **不降级为普通 mention**：critical_extension `fail_closed=true` → 未声明支持 MUST reject
30. **authority_grant_ref 校验**：grant 已 revoked / subject 不匹配 / attached_authority.controller 不匹配 → `unauthorized`
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

42. **Mirror Space derived_from 基数**：尝试同 source Flow 第二个 mirror Flow → `cardinality_violation`
43. **agent_membership_change 通知脱敏**：E2EE preview MUST 由客户端预先脱敏

## 16. 安全 / 隐私要点

- **DID Document 不暴露 workspace Space ID**：service entry 仅 HTTPS endpoint；workspace_root_space_id 通过鉴权后 resolve API 取得；未鉴权 GET 返回 401/403 不返 404
- **mention_redirect 不暴露 mirror 端定位**：仅含 `redirect_pair_id`（sender opaque UUID）和 `authority_grant_ref`（指向源 Space 已 active 的 grant）
- **`body` 字段披露**：客户端 MUST 提示用户该字段对源 Flow 成员可见
- **Watcher 撒谎防护**：`evidence_refs` 含可独立 fetch 验证的 event ID；多 watcher 并行 + TTL housekeeping 兜底
- **Cleanup 滥用防护**：cleanup Move MUST 携带 `ttl_evidence`，reducer 验证 `current_time ≥ reservation_anchored_at + ttl`

## 17. 显式不在 v1 范围

- ❌ `cx.grant.delegate_read`（scoped read 委托）：MLS E2EE 下无法干净实现；`knowledge_sources[]` + import_attestation 已覆盖
- ❌ Server-side @ mention 自动路由：routing 是 client UX，server 不重写消息
- ❌ `on_behalf_of` Message 字段：v1 由 controller 手动 publish 覆盖（§13.6）
- ❌ Mirror Space deterministic 命名 `f(controller, source_space) → mirror_id`
- ❌ `attached_authority.inline_copy` evidence_kind（air-gapped 场景推迟到 v2）
- ❌ Workspace 内容跨 deployment 自动迁移（v2 提供工具）

## 18. 规范性引用

- 公共字段：[common-fields.md](../models/common-fields.md)
- Capabilities：[capabilities.md](../authz/capabilities.md)
- Event auth / lattice：[event-auth-state-resolution.md](../authz/event-auth-state-resolution.md)
- Encryption / agent authority：[encryption-and-audit.md](../crypto-media/encryption-and-audit.md)
- Push notifications：[push-notifications.md](../discovery/push-notifications.md)
- Content types：[content-types.md](../models/content-types.md)
- Relation cross-Space：[relation.md](../models/relation.md)
- Federation：[federation.md](../sync/federation.md)
- Service binding：[service-http-binding.md](../sync/service-http-binding.md)
- Encoding (JCS)：[encoding.md](../conformance/encoding.md)
- Agent protocol interop：[agent-protocol-interop.md](./agent-protocol-interop.md)
