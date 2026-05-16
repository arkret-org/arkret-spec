# Proposal — Agent Workspace 与 Source Flow 协作模式

Status: **Rev 8 — Final / Merged**（2026-05-17 完整化 + 合并到主协议）
Created: 2026-05-16
Last revised: 2026-05-17 (Rev 8)
Scope: v1（尽量复用现有原语，最小协议改动）
Canonical merged location: [`spec/v1/zh/extensions/agent-workspace-profile.md`](spec/v1/zh/extensions/agent-workspace-profile.md)

> **Rev 8 完整化决定**（解决 Rev 7 §14.2 列出的 4 项 follow-up）：
> 1. **Conformance vectors**：在主合并文件中列出完整 43 项 vector，不再 "follow-up"
> 2. **Workspace MLS membership**：复用标准 Space membership（`cx.member.state`），不新增 `workspace_visible` 字段；profile 声明 owner = controller principal，members = controller-owned agents
> 3. **`attached_authority.inline_copy` 删除**：v1 仅保留 `anchored_event_ref` + `state_witness` 两种 evidence_kind；inline_copy（air-gapped 场景）推迟到 v2
> 4. **Workspace teardown / migration**：复用标准 `cx.space.tombstone` 生命周期；跨 deployment 迁移通过 DID Document service entry 更新；详细规则在主合并文件 §10



> **Rev 7 关键修订**（作者自审发现 5 项必修 + 4 项 follow-up）：
> 1. **`head_eq: null` 实际不阻止 singleton 覆盖**（Rev 6 自欺）—— [event-auth-state-resolution.md:423-431](spec/v1/zh/authz/event-auth-state-resolution.md) 算法允许 basis=null 覆盖任何 settled value。改用 **empty sentinel pattern**：cell schema 声明初值 `"__unset__"`，reservation Move predicate = `head_eq: "__unset__"`；singleton 由算法 `basis≠settled and basis≠null → ⊥` 真正成立
> 2. **删除不可达 transition 边**：transparency `reconfirmed_after_loss → lost`（Message redaction 是 terminal，不能 un-redact）；source_authority `ok → revoked`（重复列）+ `reconfirmed_after_revoke → ok`（authority_grant_ref 绑定原 grant_id，re-grant 是新 grant 与已有 task 无关）
> 3. **Cleanup capability holder 统一**：仅 controller principal 持 `cx.capability.agent_workspace.cleanup`，可显式 delegate 给自己 sync node 的 system actor（标准 capability delegation）
> 4. **§4.7 reverse publish 加 read-then-write**：controller 写 execution.transition 前必须读 cell head（avoid `from=active` 盲写在多设备场景失败）
> 5. **`redirect_event_commitment` 删除**：原本是 SHA-256(agent_task_id ‖ nonce)，但 nonce 放哪都不对（公开则反向枚举复活；私存则第三方无法验证）。pair_id 已足够双端关联，commitment 是冗余且有反枚举风险

> **Rev 7 显式列为 follow-up 的项**（非阻断）：
> - Conformance vectors 完整覆盖（FSM 共 13 条合法 transition + 至少 9 条非法 + saga/recovery/orphan = 34+，而非 §6.2 列的 19 个）
> - Workspace root MLS group membership normative（"controller 设备 + workspace_visible agents"）
> - `attached_authority.inline_copy` size limit（或删除 inline_copy 仅保留 anchored_event_ref / state_witness）
> - Workspace teardown / 跨 deployment 迁移流程

> **Rev 6 关键修订**（第五轮审议 7 项，已全部落地，保留作为变更历史）：
> 1. **reservation Move 用 `head_eq: null` 显式 predicate**（不是"无 predicate"）；cas-register 算法 `basis = null = 允许 first set` 的语义只在 predicate 显式存在时才表达"我期望 cell 为空"
> 2. **recovery Move 改为符合 [§8 冲突修复](spec/v1/zh/authz/event-auth-state-resolution.md)**：`head_in [conflict_heads]` + state_witness + inclusion_proof + recovery_capability refs；不是 `head_eq=⊥`（spec 没有这个 predicate）；声明 recovery capability 由 controller principal 持有
> 3. **三正交 cell 在全文统一应用**：删除 §3.6 schema 中的 `state/state_changed_at`；§4.1 / §4.3 / §4.8 / §6.2 / §7 全部改为三 transition 事件名
> 4. **Watcher 必须先读当前 cell**：二次失效（如 `reconfirmed_after_loss → lost`）需要 watcher 按当前 state 写合法 transition，不能盲目 `from=ok`
> 5. **Orphan reservation 不留 follow-up**：定义 reservation TTL + idempotent retry + cleanup Move
> 6. **§7 文档树彻底删 Message schema 变更条目**（与 Rev 5 "Message schema 不变"对齐）
> 7. **`source_export_policy_attestation` 签名描述消除循环**：明确签名覆盖除 `signature` 外的 required 字段 + domain separator + schema id

> **Rev 5 关键修订**（第四轮审议 7 项，已全部落地，保留作为变更历史）：
> 1. **cas-register 真实语义**：并发不同值 → `⊥`（不是"first-anchored wins"，那是 Rev 4 编造）。沿用 MLS genesis 同款"`cas-register + bottom=reject` + 显式 recovery Move（predicate `head_eq=⊥` + 确定性 winner 规则）"模式
> 2. **跨 Space 改 reservation saga**：workspace root 中 cell 存"预分配的 mirror_space_id"作为 reservation token；`cx.space.create` 是独立后续 Move；不假设跨 Space 原子性
> 3. **agent_task FSM 拆为 3 个正交 cell**：execution_state / transparency / source_authority；agent runtime 执行条件是三个 cell 的合法组合；解决"同时 transparency_lost 与 source_authority_revoked"无法表达问题
> 4. **profile vs feature 分层**：源 Space 的 mention_redirect 只看 `cx.feature.mention_redirect.v1` critical_extension；mirror Space 的 routing/agent_task 才依赖 `cx.profile.agent_workspace.v1`；不互相耦合
> 5. **`content_hash` canonicalization 现在定义**：复用 [encoding.md](spec/v1/zh/conformance/encoding.md) 已有的 RFC 8785/JCS canonical JSON profile + SHA-256；不留 follow-up
> 6. **清理 §3.6 cas-register 残留文本** + **§7 文档树删 Message schema context_anchor 字段说明**（context_anchor 在 agent_task 上）

> **Rev 4 关键修订**（第三轮审议 7 项，已全部落地，保留作为变更历史）：
> 1. **`critical_extensions.scope` 修为 `payload`**——`payload.content` 不在 [event-schema.json:977-988](spec/v1/artifacts/schemas/event-schema.json) 合法枚举中；细化定位用独立 `schema_ref` 字段
> 2. **两层并发 race 都解决**：新增 workspace root 级 cell `mirror_space_by_source:<source_space_id>`（防 mirror Space 创建竞态）+ 保留原 `mirror_flow_by_source:<source_flow_id>`（防 mirror Flow 创建竞态）
> 3. **澄清 cas-register vs fail-bottom**：cas-register precondition `from=unset`；first-anchored Move 是 winner，后续 Moves `failed_precondition`（**不是**双方都 fail ⊥）；conformance vector 重写
> 4. **`agent_task.state` 改 FSM lattice**：用 `transition` op（`from` / `to` / `reason`），不用 cas-register；非法转换 reducer reject；多 watcher 写同一 transition 自然 idempotent（第二个见 cell 已在 to-state，preconditioin 失败）
> 5. **全局清理 Rev 3 残留**：`redirect_to_*` / `human_readable_summary` / `authority_snapshot` / "Message schema 加 context_anchor" 等旧表述
> 6. **attestation canonical schema 补齐**：`attached_authority` 字段正式扩入 capability-grant schema；`source_export_policy_attestation` 落 schema；移除"MUST 包含可选字段"自相矛盾表述，统一为"如携带则 MUST 满足结构"
> 7. **Grant revoke → task FSM**：新增 `source_authority_revoked` 状态 + watcher 模式；与 `transparency_lost` 平行（来源不同：前者是 capability 失效，后者是 stub 被 redact），处理路径类似

> **Rev 3 关键修订**（第二轮审议 6 项 critical，已全部落地，保留作为变更历史）：
> 1. **任务生命周期从 Message 拆出**：不复用 `cx.message.update` 或新增 Message state；引入独立对象 `cx.schema.agent_task.v1` + 事件家族 `cx.agent_task.{create,state,cancel}`，绑定 redirect_pair_id
> 2. **`critical_extensions` 移到 Event 顶层 `requirements.critical_extensions[]`**（符合 [event-and-patch.md:43](spec/v1/zh/models/event-and-patch.md) 既有模型），不放在 content block
> 3. **Mirror 唯一性单独定义 cell**：`agent_workspace.mirror_flow_by_source:<source_flow_id>`，明确 fail-bottom 语义；不依赖通用 cas-register"deterministic winner"
> 4. **全局清理 Rev 1 残留**：`cx.flow.member.*` / `cx.message.update` / `quote_external` / `trigger_message_ref` 全部替换
> 5. **跨 Space 副作用改"观察后写入"**：mirror reducer 不消费 source Space 事件；源端 redact / 状态变化由 controller / agent runtime 观察后**在 mirror Space 显式写 reconciliation 事件**
> 6. **Authority 校验复用 source Space 的 capability grant**：不在 event 内嵌 `authority_snapshot`，改为引用源 Space 已有的 `cx:grant:...`（capability grant 在 invite 时写入即完成"authority cache"）；export policy 改为"mirror 端只验证 carried attestation 完整性，无法强制 enforce"

**Rev 3 v1 最小范围（最终）**：
- 2 个新 content block：`cx.content.mention_redirect`、`cx.content.import_attestation`
- 1 个新对象 + 事件家族：`cx.schema.agent_task.v1` + `cx.agent_task.{create,state,cancel}`
- 1 个新 Space profile：`cx.profile.agent_workspace.v1`
- 1 个新 cas-register cell key 命名空间：`agent_workspace.mirror_flow_by_source`
- 4 个 normative 引导（agent_member_profile / resolve_mirror_flow / agent_membership_change / 合规 attestation）

---

## 1. 背景与动机

用户经常需要在协作 Flow（工作群、项目讨论）中调用自己的 AI agent 干活，但同时希望：

- **指令内容不暴露**给 Flow 其他成员（私密性）
- **agent 的存在与权限范围**对 Flow 其他成员可见（透明度 / 信任）
- agent 团队的复杂度（多个专长 agent、内部讨论、试错过程）**不污染源 Flow**
- 跨多个源 Space 工作时有**统一入口**回到自己的 agent workspace

现有 spec 提供了所有基础原语（Flow / Message / Relation / cross-Space references / capability），但没有把它们组合成一个 normative pattern。本提案补齐这一层。

## 2. 核心架构（Agreed）

```
┌─────────────────────────────────────────────────────────────┐
│   Source Space（公开协作 / 组织 / 项目 / 跨组织）            │
│   ┌──────────────────────┐                                  │
│   │ Source Flow          │  agent_X 作为 member 加入        │
│   │  - Alice             │  (read_only / mention_respond)   │
│   │  - Bob               │                                  │
│   │  - agent_X (Alice's) │  Alice @ agent_X → stub mention  │
│   └──────────────────────┘                                  │
└───────────────────│─────────────────────────────────────────┘
                    │ derived_from (cross-Space references)
                    │ + cx.content.import_attestation (re-encrypted)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│   Alice's Agent Workspace Root Space                        │
│   （在 Alice 的 principal server，DID Document advertise）   │
│   ┌──────────────────────────┐                              │
│   │ Mirror Space             │  members = Alice + her agents│
│   │  per source Space        │  独立 MLS group / E2EE 边界  │
│   │   ┌────────────────────┐ │                              │
│   │   │ Mirror Flow        │ │  per source Flow             │
│   │   │  - Alice           │ │                              │
│   │   │  - agent_X (primary)│ │                             │
│   │   │  - agent_Y (consult)│ │                             │
│   │   └────────────────────┘ │                              │
│   └──────────────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

**两个独立治理域**：
- Source Flow agent membership = 源 Space 治理（公开声明）
- Mirror Flow agent membership = controller 独占治理（私人组队）
- **不自动同步**；变更通过 notification 推送，controller 显式决定

**三层结构**：
1. `agent_workspace_root`（Space，每 controller 一个）—— 入口 / 索引
2. `mirror_space`（Space，per source Space）—— 独立 E2EE 边界 / 独立 retention
3. `mirror_flow`（Flow，per source Flow）—— 实际工作 Flow

**触发机制**：用户在 source Flow `@my_agent` → 在 source Flow 留 stub mention（透明）+ 在 mirror Flow 写真实指令 + `context_anchor` 锚回触发点

## 3. Spec 改动清单（v1）

> **重大更新（草稿审阅发现）**：`cx.schema.agent_authority.v1` 已存在并且非常完整——`controller` / `responsible_actor` / `acting_mode` / `knowledge_sources[]`（含 visibility = `metadata_only` / `derived_summary` / `plaintext` / `ciphertext_only`）/ `join_policy.allowed_space_ids` / `presence_policy.allowed_triggers` 都已规范化。
>
> 这意味着本提案大量"新增"内容其实是**对现有原语的组合 + normative 引导**，不是发明新机制。下面具体改动相应大幅缩水。

### 3.1 改动 A — 标准化 Agent Member Capability Profile

**目标**：把"加 agent 到 Flow，限定 read-only / mention-respond"打包成可声明的 capability preset，避免每个客户端各自拼 constraint。

**文件**：
- `spec/v1/zh/authz/capabilities.md` — 新增章节"§N. Agent Member Profile"
- `spec/v1/zh/extensions/agent-protocol-interop.md` — 引用此 profile
- `artifacts/profiles/` — 新增 `agent-member-profiles.json`

**标准 preset names**：

| Name | 含义 | 允许动作 |
|---|---|---|
| `cx.agent_member.observer` | 只观察，不互动 | `read_history`, `read_messages` |
| `cx.agent_member.read_only` | 只读 + 反应 | observer + `react` |
| `cx.agent_member.mention_respond_only` | 仅在被 @ 时回复 | read_only + `message.create where in_reply_to.mentions=self` |
| `cx.agent_member.full_collaborator` | 完整成员（同人类） | 标准 member capability set |

**⚠️ Rev 2 修订（membership 模型）**：v1 中**没有 Flow-level membership**——`cx.flow.member.add` 是虚构 API。Agent 加入 = `cx.member.state` 在 Space 级。这给我们两种 per-Flow scoping 路径：

**路径 A（默认，粗粒度）**：Agent 加入源 **Space**
- Agent 拿到 Space 级 MLS 解密边界，能看 Space 内所有 Flow
- Capability constraint 可限定写权限到具体 Flow（`object_ref=cx:flow:...`）
- 适合"agent 对整个项目都可见"的场景

**路径 B（细粒度，要求源 Flow 升级）**：源 Flow MUST 先设置 `discussion_space_ref` 指向 child Space；agent 加入 child Space
- Agent 只看该 Flow 的讨论时间线，看不到 Space 内其他 Flow
- Child Space 独立 MLS group / 独立 retention / 独立 history visibility
- 适合"agent 严格 per-Flow scope"的场景，但要求源 Flow 提前规划 discussion_space_ref（不能事后窄化）

**路径选择**：本提案不强制；source Space admin / Flow creator 根据需要选。`cx.profile.agent_workspace.v1` 在 mirror 端不关心源是 A 还是 B，只通过 `derived_from` Relation 指向源对象。

**Reducer 行为**：邀请 agent 通过现有标准 path：
- `cx.invite.create` 携带 `capability_grant_refs[]`（或等价 invite payload 字段）
- `agent_member_profile` 在 invite 客户端层展开为 `cx.capability.grant` 事件序列（写入 Space）
- Reducer 验证：grant 的 grantee = agent DID + agent 的 `agent_authority.controller`（当 `acting_mode=delegated_assistant`）== inviter principal
- 运行时 capability check 不依赖 profile name

**Constraint kind 新增需求**：`mention_respond_only` 不是字符串 DSL，需要在 [constraint-schema.md](spec/v1/zh/authz/constraint-schema.md) 注册一个标准 constraint kind，建议命名 `mention_respond_only`，semantics: "actor 只能写入 `cx.message.create` 当且仅当 `in_reply_to` 指向 mention sender 为 self 的消息"。Reducer-evaluable，不能交给客户端自由解释。

**Source Space agent disable policy**：profile-level "no agents" 限制由现有 Space-level capability policy 表达——拒绝向 agent DID 颁发任何写/读 grant 即可，**不引入新机制**。

**MUST**：profile 是声明性 sugar，不绕过 capability 检查；任何 grant escalation 仍走 §authz 标准流程。

---

### 3.2 改动 B — Space Profile `cx.profile.agent_workspace.v1`

**目标**：标准化 controller 私人 agent workspace 的 Space 形状、成员约束、跨 Space 引用治理、retention。

**文件**：
- `spec/v1/zh/extensions/` — 新增 `agent-workspace-profile.md`
- `spec/v1/zh/identity/identity-did.md` — 在 service endpoint 章节补充 `ContrixAgentWorkspace` 类型
- `artifacts/profiles/conformance-profiles.json` — 注册 profile
- `artifacts/schemas/space.schema.json` — 把 `agent_workspace` 加入合法 profile 枚举

**Profile 声明（要点）**：

```json
{
  "profile_id": "cx.profile.agent_workspace.v1",
  "scope": "space",
  "membership": {
    "owner": "single_controller_principal",
    "allowed_member_kinds": ["controller_principal", "controller_owned_agent"],
    "max_human_members": 1,
    "agents_only_from_controller_did_document": true
  },
  "e2ee": {
    "required": true,
    "mls_group": "per_space"
  },
  "discoverability": "secret",
  "history_visibility": "joined",
  "retention": {
    "default_flow_retention_days": null,
    "stale_import_attestation_handling": "lock_lazy"
  },
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

> **Rev 2 修订**：原版本只声明 `max_to_per_from=1`，只能防"一个 mirror 指向多个 source"，**不能**防"同一个 source Flow 被两个 mirror Flow 同时指向"——后者正是多设备并发首次创建的典型场景。现补 `max_from_per_to=1`（或等价的 `one_to_one`），由 reducer cas-register 收敛冲突。

**DID Document service entry（Rev 2 修订）**：

```json
{
  "id": "did:web:alice.example#agent-workspace",
  "type": "ContrixAgentWorkspaceService",
  "serviceEndpoint": "https://alice-principal.example/api/v1/agent_workspace"
}
```

> **Rev 2 修订**：原版本直接发布 `cx:space:<workspace_root_id>` 是元数据泄露——任何 DID Document reader 都能枚举出 Alice 的 workspace Space ID。Rev 2 只发布 HTTPS endpoint；workspace root Space ID 由 controller 鉴权后通过 endpoint resolve。

**Workspace resolve API**：

```
GET /api/v1/agent_workspace/root
Authorization: DID-signed (controller's principal key) or session token
→ 200 { "workspace_root_space_id": "cx:space:..." }
→ 401/403 不暴露 workspace 存在性
```

未鉴权请求 MUST 返回 401/403 而非 404（避免存在性枚举）。

**子结构约定**：
- Workspace root Space 内通过 `cx.relation.derived_from` 把每个 mirror Space 关联到对应源 Space
- Mirror Space 内每条 mirror Flow 通过 `cx.relation.derived_from` 关联到对应源 Flow
- 跨 Space `derived_from` 走 [relation.md §4](spec/v1/zh/models/relation.md)（已有机制）

**Lazy 创建语义（Rev 5：reservation saga + cas-register `bottom=reject` + 显式 recovery）**：

> Rev 4 写的"cas-register precondition `from=unset` + first-anchored wins"是**编造的语义**——[event-auth-state-resolution.md:290](spec/v1/zh/authz/event-auth-state-resolution.md) 明确 cas-register **并发不同值返回 ⊥**；predicate ops 也只有 `head_eq / head_in / satisfies / contains`，没有 `from=unset`。Rev 5 改为沿用 spec 已有的 **MLS genesis 同款模式**（[encryption-and-audit.md §5.1](spec/v1/zh/crypto-media/encryption-and-audit.md)："同一 (scope, mls_group_id) 的 genesis cell 使用 cas-register + bottom=reject。并发重复 genesis 会使该 cell 返回 ⊥，后续 Move 必须 fail closed 直到 recovery Move 修复"）。

**双层 reservation cell**：

| 层 | Cell key | 命名空间 | Cell value（reservation token） | Lattice |
|---|---|---|---|---|
| **L1** | `mirror_space_by_source:<source_space_id>` | **workspace root Space** | `cx:space:<pre-allocated mirror_space_id>` | `cas-register + bottom=reject` |
| **L2** | `mirror_flow_by_source:<source_flow_id>` | **mirror Space** | `cx:flow:<pre-allocated mirror_flow_id>` | `cas-register + bottom=reject` |

**关键设计**：cell value 不是"已存在的 Space/Flow ID"，而是**客户端预分配的 UUIDv7 ID**（reservation token）。`cx.space.create` / `cx.flow.create` 是分离的后续 Move，**不假设跨 Space 原子性**。

**并发创建 reservation saga（Rev 7 修订：empty sentinel `"__unset__"` + 符合 §8 的 recovery）**：

> **Rev 7 关键修订**：Rev 6 的 `head_eq: null` predicate 实际不阻止覆盖——[event-auth-state-resolution.md:423-431](spec/v1/zh/authz/event-auth-state-resolution.md) 算法 `if basis_required != settled and basis_required is not null: return ⊥`，basis=null 不触发 ⊥，允许 LWW 覆盖。改用 **empty sentinel pattern**：cell schema 声明初值是字面字符串 `"__unset__"`，reservation Move predicate = `head_eq: "__unset__"`。第二个并发 Move 会因 `basis="__unset__" ≠ settled=reservation_id and basis is not null → ⊥`。

**Cell schema 声明 initial value（需要在 spec schema 层支持）**：

```json
{
  "cell_namespace": "mirror_space_by_source",
  "lattice": { "type": "cas-register", "bottom": "reject" },
  "value_schema": { "type": "string", "pattern": "^(__unset__|cx:space:[uuidv7])$" },
  "initial_value": "__unset__"
}
```

> **Spec PR 依赖（Rev 7 显式列出）**：当前 spec 的 cell schema 没有 `initial_value` 字段；本提案 MUST 与 spec 维护者协作把 "cell schema 可声明 initial_value" 提为 schema 扩展。否则 fallback 是"workspace root Space genesis 时显式写 'initialize all reservation cells to `__unset__`' Move"，但这要求知道所有 source_space_id 上界，不实际。empty sentinel pattern 要求 spec 支持该字段。

**Reservation 流程**：

1. 客户端调用 `agent_workspace.resolve_mirror_flow(source_flow_id)`；返回已存在则复用
2. 若 query 返回空，客户端**预分配** UUIDv7 `mirror_space_id` 和 `mirror_flow_id`
3. **L1 reservation Move**（在 workspace root Space）：
   - lattice op：`set`，cell = `mirror_space_by_source:<source_space_id>`，value = pre-allocated `mirror_space_id`
   - **predicate**：`head_eq: "__unset__"` —— 与 cell schema 声明的 initial_value 一致
   - capability ref：controller principal 的 `cx.capability.agent_workspace.reserve` grant
4. L1 收敛三种情况：
   - **happy path**：settled=`"__unset__"`，basis=`"__unset__"`，match → current = mirror_space_id
   - **cell 已 set**（因果晚）：settled=existing_id，basis=`"__unset__"`，`basis≠settled and basis is not null` → **⊥**（singleton 真正成立）
   - **真并发同时写不同 reservation token**：同 anchor batch 内 siblings `(b1, v1)=(__unset__, idA)` 和 `(b2, v2)=(__unset__, idB)` 满足 `b1==b2 and v1!=v2` → **⊥**
5. **L1 reservation 成功后**，写**独立后续 Move** `cx.space.create(id=mirror_space_id)`，写入 controller 的 principal control stream
6. mirror Space 存在后，进入 **L2 reservation Move**（在 mirror Space 内）；mirror Space genesis 时同样把 `mirror_flow_by_source` cell namespace 初始化为 `"__unset__"`
7. L2 成功后写独立 `cx.flow.create(id=mirror_flow_id)` Move

**Recovery Move（Rev 6 修订：严格符合 [§8 冲突修复](spec/v1/zh/authz/event-auth-state-resolution.md) 协议）**：

L1 / L2 cell 进入 ⊥ 后（bottom diagnostic 带 `heads = [candidate_A, candidate_B, ...]`），客户端写 recovery Move：

```text
Move {
  preconditions: [
    (cell, head_in [candidate_A, candidate_B])    // §8 标准形式，不是 head_eq=⊥
  ],
  effects: [
    (cell, set lex-min(candidates))               // deterministic decision
  ],
  refs: [
    (cx:grant:<workspace_recovery_capability>,    role="authorized_by"),
    (pre_conflict_state_witness,                  role="state_witness",     critical=true),
    (snapshot_inclusion_proof,                    role="inclusion_proof",   critical=true)
  ]
}
```

**Recovery capability**：

- 新增 capability action `cx.capability.agent_workspace.recover`
- 该 capability 由 controller principal 自我持有，在 workspace root Space genesis 时通过 `cx.capability.grant(subject=controller_did, action=agent_workspace.recover, ...)` 写入
- 仅 controller principal 可 issue recovery Move；agent / 外部 actor 不能 recover（否则攻击者可篡改 winner）
- mirror Space 的同名 capability 在 mirror Space genesis 时类似 grant

**State witness / inclusion proof 要求**：

- `pre_conflict_state_witness` 指向 ⊥ 发生前最近一个 effective state snapshot（[event-auth-state-resolution.md §8.1](spec/v1/zh/authz/event-auth-state-resolution.md)）
- `snapshot_inclusion_proof` 证明该 snapshot 在 sync node 的 Anchor 中 inclusion
- 这两个 refs **MUST critical=true**——open_set / threshold profile 下没有它们 recovery 可被多 verifier 看作不同决议

**Orphan reservation 处理（Rev 7 修订：cleanup 写回 `"__unset__"` sentinel + capability holder 统一）**：

reservation 成功但后续 `cx.space.create` / `cx.flow.create` 失败（崩溃 / 网络 / 服务端 reject）会让 cell 指向不存在的 Space / Flow ID。处理协议：

1. **TTL 字段**：reservation Move 的 effects 携带 `reservation_ttl_seconds`（默认 600s）作为 lattice op 附加 metadata
2. **观察期**：在 `reservation_anchored_at + ttl` 之内，client 应完成 follow-up create Move
3. **Resolve API 行为**：`agent_workspace.resolve_mirror_flow` MUST 不返回未完成 reservation——只返回 `(reservation_id, create_event_id)` 两端都存在的 mapping
4. **Cleanup Move**（Rev 7 修订）：
   - **Capability holder**：**仅 controller principal 持** `cx.capability.agent_workspace.cleanup`。Controller MAY 通过标准 capability delegation 把它 grant 给自己 sync node 的 system actor（让 housekeeping 自动跑）；但 capability **根源是 controller**，不是 sync node 凭空持有
   - precondition：`head_eq <reservation_id>`（针对那个 stale value）
   - effect：lattice op `set` to `"__unset__"`（恢复到 sentinel 状态，下次 reservation 又可以 `head_eq: "__unset__"` 走 happy path）
   - evidence ref：MUST 携带 `ttl_evidence: { reservation_anchored_at, ttl_seconds, current_time }` 让 reducer 验证 `current_time ≥ reservation_anchored_at + ttl`；防止 cleanup 滥用清空有效 reservation
5. **Idempotent retry**：client 在 TTL 内可以 retry follow-up create Move（事件 idempotency 由 `cx.space.create.id` 的固定 UUIDv7 保证——同 ID 第二次 create 是 no-op）
6. **失败重新预约**：cleanup 后，下一个 client 可以重新走步骤 1-7 用新 UUIDv7 reservation

**单 server 部署的常见情况**：若 workspace root 在 controller 自己 principal server（多数情况），server 自然 serialize 写入请求；只有第一个 reservation Move 被 accept，后续被 server validate_op reject 为 `reservation_cell_already_set`——不进入分布式 ⊥ 路径。⊥ recovery 主要应对多 master / 多 sync node 拓扑。

**Conformance vectors（Rev 6 修订）**：

- "单 server 并发首次创建"：两个 client 同时请求；server validate_op 拒绝第二个，返回 `reservation_cell_already_set`
- "多 master 并发 → ⊥ → §8 recovery"：两个 Move 在不同 sync node anchor，cell → ⊥；客户端读到 ⊥ 后写 recovery Move（含 head_in + state_witness + inclusion_proof + recovery_capability）；cell 收敛到 lex-min winner
- "Recovery Move 缺 state_witness 或 inclusion_proof critical ref → reject"
- "Recovery Move issuer 无 `cx.capability.agent_workspace.recover` → `unauthorized` reject"
- "Recovery winner 必须 deterministic"：相同 (candidate_a, candidate_b) 输入下，lex-min 选择必须可重现
- "Orphan reservation TTL cleanup"：reservation 成功但 follow-up create 未在 TTL 内提交 → sync node 写 cleanup Move → cell 回到 null，可重新 reserve
- "Resolve API 不返回 unfinished reservation"

**新增 service operation `agent_workspace.resolve_mirror_flow`**：

```
GET /api/v1/agent_workspace/mirror_flow?source_flow_id=<id>
Authorization: DID-signed (controller's principal) or session token
→ 200 { "mirror_flow_id": "cx:flow:...", "mirror_space_id": "cx:space:..." }
→ 404 { "reason": "not_provisioned" }    # 仅向已鉴权 controller 返回
→ 401 / 403                              # 未鉴权或非 owner，不暴露 workspace 存在性
```

- 该 op 在 controller 自己的 principal server 服务，**仅对 controller 自己可读**
- 实现 SHOULD 在 sync node 的本地索引 view `(source_flow_id → mirror_flow_id)` 上完成，无需写入 frontier
- 跨 deployment：source_flow_id 解析到 mirror_flow_id 不要求源 deployment 参与；纯 controller 端事实
- **Spec 落点（Rev 2 修订）**：MUST 同时进入以下规范文件，避免散落：
  - `spec/v1/zh/sync/service-http-binding.md` —— HTTP 路径 / 鉴权
  - `spec/v1/zh/sync/service-api-schema.mdx` —— operation schema
  - `artifacts/registry/operation-registry.json` —— 注册 `operation_id`
  - `artifacts/openapi/contrix-service-api.openapi.yaml` —— OpenAPI 形状
  - `artifacts/registry/non-http-bindings.yaml` —— 非 HTTP 绑定
  - `artifacts/registry/error-code-registry.json` —— `not_provisioned`、`workspace_not_initialized` 等 reason_code

---

### 3.3 改动 C — Content Block `cx.content.mention_redirect`

**目标**：source Flow 中的 @-mention-my-agent 不携带指令正文，只携带"我把指令送到了我的私人 workspace"的透明 stub；具备 spec-level 可识别性（不是字符串约定）。

**文件**：
- `spec/v1/zh/models/content-types.md` — 新增 `cx.content.mention_redirect`
- `artifacts/schemas/` — 新增 `content-mention-redirect.schema.json`

**Content block schema sketch（Rev 3 修订）**：

```json
{
  "kind": "cx.content.mention_redirect",
  "body": "Alice asked her agent privately",
  "target_actor_id": "did:web:alice-agent.example",
  "authority_grant_ref": "cx:grant:01964200-0000-7000-8000-bbbbbbbbbbbb",
  "redirect_pair_id": "01964200-0000-7000-8000-aaaaaaaaaaaa"
}
```

> **Rev 7 修订**：删除 `redirect_event_commitment` 字段。原本意图是 SHA-256(agent_task_id ‖ nonce) 让两端可验证一致，但 nonce 无处可放：写在 mention_redirect content 公开则 hash 可反向枚举出 agent_task_id（反枚举攻击复活）；私存又无法第三方验证；本地 controller 客户端比对只需 `redirect_pair_id`（已经 opaque + sender-generated UUID）即可关联两端。commitment 是冗余且有副作用，删除。

**承载该 content 的 Event 顶层 requirements（Rev 4 修订：scope 修为 `payload`）**：

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

> **Rev 4 修订**：Rev 3 写的 `scope: "payload.content"` 不在 [event-schema.json:977-988](spec/v1/artifacts/schemas/event-schema.json) `criticalExtension.scope` 的合法 enum（`event | payload | proof | authz | reducer | projection | encryption`）内，schema 会 reject 整条 event。修正为 `scope: "payload"`，由 `schema_ref` 定位到具体 content block schema。这与现有模型对齐。

> **Rev 3 修订摘要**（与 Rev 2 差异）：
> - **`critical_extensions` 从 content block 内挪到 Event 顶层 `requirements.critical_extensions[]`**——符合 [event-and-patch.md:43](spec/v1/zh/models/event-and-patch.md) 既有模型："`requirements.{schema[], reducer, features[], critical_extensions[]}` 全部进入 canonical bytes 与 event digest；接收方 MUST fail closed 对未知 critical 项"。content block 内部不是 fail-closed 的权威位置。
> - **删除 `authority_snapshot`，改用 `authority_grant_ref`** —— 引用 source Space 中已存在的 `cx:grant:...`（agent 加入时由 inviter 写入的 capability grant，其中已经携带 `attached_authority_event_ref` 指向 controller 的 agent_authority）。Reducer 验证：
>   1. `cx:grant:...` 在源 Space 有效（active state）
>   2. grant 的 grantee == `target_actor_id`
>   3. grant 的关联 agent_authority 中 controller / responsible_actor == sender principal
>   不需要在 mention_redirect event 内嵌大量身份证据——身份证据已经是源 Space 的事实（在 invite 时锚定）。
> - 顶层 `body` 保留 Rev 2 设计；`redirect_pair_id` 保留；~~`redirect_event_commitment`~~ **Rev 7 已删除**（见 §3.3 schema 注 + §14）。

**`attached_authority` 字段正式扩入 capability-grant schema（Rev 4 修订：补 canonical shape）**：

> Rev 3 引入了"capability grant 携带 attached_authority"作为依赖，但当前 [capability-grant.schema.json](spec/v1/artifacts/schemas/capability-grant.schema.json) 没有这个字段（只是 `additionalProperties` 通过）。Rev 4 把它正式 spec 为可选 typed 字段。

`capability-grant.schema.json` 新增可选顶层字段：

```json
{
  "attached_authority": {
    "type": "object",
    "description": "Optional binding to a cx.schema.agent_authority.v1 attestation. Required when grant subject is an agent DID with acting_mode=delegated_assistant.",
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
      },
      {
        "properties": {
          "evidence_kind": { "const": "inline_copy" },
          "authority_inline": { "$ref": "./agent-authority.schema.json" }
        },
        "required": ["authority_inline"]
      }
    ]
  }
}
```

**Reducer 校验规则**：

- Grant subject 是 agent DID 且其 `agent_authority.acting_mode == "delegated_assistant"` 时，`attached_authority` **MUST 必填**（grant event 不带 → schema validation reject）
- `evidence_kind=anchored_event_ref`：reducer SHOULD 异步通过 controller's principal server 验证 inclusion proof；不可达时降级为 `unverified_authority` 标记，grant 仍 active 但 audit 显示 unverified
- `evidence_kind=state_witness`：reducer 校验 `witness_signature` 由 controller's principal server 当前注册的 key 签发；TTL 由 `valid_until` 控制；过期后 grant 自动失效（写一条 housekeeping `cx.capability.revoke`）
- `evidence_kind=inline_copy`：完整 agent_authority 内嵌；reducer 校验内嵌结构合法 + controller 字段一致 + 内嵌 event 自身的签名链

**mention_redirect reducer 流程**：

1. 解析 `authority_grant_ref` → 在源 Space 取到对应 `cx:grant:...` 当前 state
2. 校验 grant active（非 revoked / 非 expired）
3. 校验 `grant.subject == content.target_actor_id`
4. 校验 `grant.attached_authority` 的 controller 字段 == event sender principal（按 evidence_kind 分支验证）
5. 任一失败 → `unauthorized` reject 整条 event

`source_export_policy_attestation` 的 canonical schema 见 §10.3。

**规则（Rev 4 修订：与新 schema 对齐）**：
- `target_actor_id` MUST 是 sender principal 的 controlled agent。reducer 通过 `authority_grant_ref` 找到源 Space active grant 验证（见下"agent_authority 引用证据强度"）；不满足 MUST `unauthorized` reject
- `redirect_pair_id` 是 opaque UUID（sender 生成），不暴露 mirror Space / Flow / Event ID；source Flow 第三方读者拿不到任何 mirror 端定位信息
- ~~`redirect_event_commitment` 字段 Rev 7 已删除~~（见上方 schema 注；hash 反枚举风险 > 它带来的验证价值）
- 顶层 `body` 字段（Content Block schema 必填）= 发送者客户端生成的脱敏摘要；E2EE Space 中 server MUST NOT 生成或重写
- redact 行为：源 Flow 撤回 stub 触发 watcher 写 mirror `agent_task.state(to=transparency_lost)`（§4.8）；mirror 撤回 agent_task 不影响 source Flow stub（两个独立 redaction 域 + observe-then-write 模式）

**Target 必须是 sender 自己 agent（normative）**：

- Reducer MUST 检查 `target_actor_id` 在 sender principal 控制下（通过 `cx.schema.agent_authority.v1` 验证 `controller == sender principal`）
- 不满足时 reducer MUST **拒绝 `mention_redirect` event**（`unauthorized`，reason `redirect_target_not_owned`），**不得静默降级为普通 `cx.content.mention`**——降级会让客户端误以为路由成功而其实指令公开泄露
- 客户端 SHOULD 在发送前本地预校验；若用户想公开 @ 别人的 agent（典型场景：找 Bob 的客服 bot 问问题），客户端 MUST 使用 `cx.content.mention`，**不使用** `mention_redirect`
- 这避免了"我以为我在偷偷指挥别人家的 agent，但其实别人 agent 公开收到了"这类隐私事故

**`body` 字段可见性披露（Rev 4 修订：原 `human_readable_summary` 已统一为顶层 `body`）**：

mention_redirect content block 的顶层 `body` 字段是 Content Block schema 必填项，对 source Flow 所有成员可见。这是一个易被忽视的元数据泄露点：

- 客户端 MUST 在 compose UI 中显式提示用户："此摘要将对源 Flow 所有成员可见"（或等价语义）
- 客户端 MUST NOT 自动从私有指令正文派生 `body`（防止 LLM 助记直接把敏感词带出来）
- Spec **建议默认值** = 与 sender 同一 locale 的通用文案，如 `"<sender_handle> 私下询问了 agent"` / `"<sender_handle> asked their agent privately"`；客户端 MAY 让用户自由编辑但 MUST 显示"对外可见"提示
- 服务端 / reducer 不验证 `body` 内容（属于客户端 UX policy 范畴）；但 server MUST NOT 重写或生成 `body`（E2EE 边界约束）

**与现有 `cx.content.mention` 的关系**：`mention_redirect` 是显式 routing 变体；普通 `cx.content.mention` 不触发 routing，是标准公开 @。两者 wire-level 不可互相降级（参见上文"Target 必须是 sender 自己 agent"规则）。

---

### 3.4 改动 D — `context_anchor` 字段（在 agent_task 顶层）+ Cross-Space E2EE 引用语义

> **Rev 5 澄清**：`context_anchor` **不**在 Message schema 上，**在 `cx.schema.agent_task.v1` 顶层**（见 §3.6）。本节描述的是 anchor 字段的 normative 语义；具体挂载点是 agent_task，不修改 Message schema。

**目标**：mirror Flow 中的 message / event 携带标准化的"源 Flow 上下文锚"，让 agent 能精确定位被讨论的源消息且不越权读后续内容。

**文件**：
- `spec/v1/zh/models/flow-and-message.md` — 在 Message schema §8.2 增加可选顶层字段 `context_anchor`
- `artifacts/schemas/message.schema.json` — 字段定义
- `spec/v1/zh/models/content-types.md` — 新增 `cx.content.import_attestation` content block

**`context_anchor` 字段（挂在 `cx.schema.agent_task.v1` 顶层，Rev 5）**：

```json
{
  "context_anchor": {
    "source_space_id": "cx:space:<source>",
    "source_flow_id": "cx:flow:<source>",
    "source_anchor_ref": "cx:anchor:<frontier anchor at trigger time>",
    "source_frontier_hash": "sha256:...",
    "trigger_redirect_pair_id": "<同 mention_redirect 的 redirect_pair_id>",
    "anchor_created_at": "2026-05-16T10:00:00Z"
  }
}
```

> **Rev 2 修订**：
> - `source_cursor_event_id` 单 event ID **不是**完整 frontier。DAG 模型下"≤ 该 event"是欠定义的。改为 `source_anchor_ref` 指向源 Space 在触发时刻的 Anchor，配合 `source_frontier_hash` 校验。语义对齐 [event-auth-state-resolution.md](spec/v1/zh/authz/event-auth-state-resolution.md) 的 anchor / frontier 概念。
> - `trigger_message_ref` 字段被移除——改用 `trigger_redirect_pair_id`，与 mention_redirect 的 opaque pair_id 对齐，不暴露 source message ID。

**字段挂载位置（Rev 3）**：`context_anchor` 现在挂在 `cx.schema.agent_task.v1` 顶层（不再挂在 Message），因为它属于 task 的属性，而非通用 Message 的属性。Message schema 不变。

**只读上界的性质澄清**：
- "agent 在处理此指令时只读到 anchor"是 **runtime policy**（agent runtime 自律），**不是 capability constraint**——agent 如果仍是源 Space/child Space 成员，技术上能读到任意时间点
- 如需 normative enforce，需要新增 capability constraint kind `read_bounded_by_anchor`（grants agent capability constrained to `source_frontier ≤ anchor`）。本提案 **v1 不引入** 此 constraint，仅作为 follow-up
- Profile MAY 通过 agent runtime 行为合规性要求把 SHOULD 抬到 MUST（合规部署）

**Content block `cx.content.import_attestation`（重命名 + 性质澄清）**：

> **Rev 2 修订**：原 `cx.content.quote_external` 容易让 reader 误以为是"来自源作者的真实引用"。改名为 `import_attestation` 明确：**这是 importer 声称"我从某 Space 看到了这条内容"，签名只能证明 importer 自己的声明，不能证明原作者明文确实如此。**

```json
{
  "kind": "cx.content.import_attestation",
  "body": "（重加密引入的源消息正文 - 纯文本 fallback）",
  "claimed_origin": {
    "space_id": "cx:space:<source>",
    "flow_id": "cx:flow:<source>",
    "message_id": "cx:message:<source>",
    "actor_id": "did:web:bob.example",
    "created_at": "2026-05-16T09:55:00Z"
  },
  "importer": {
    "actor_id": "did:web:alice-agent.example",
    "imported_at": "2026-05-16T10:00:01Z"
  },
  "import_signature": "<importer 对 (claimed_origin || canonical_content_hash || importer || imported_at) 的签名>",
  "optional_proofs": {
    "origin_event_hash": "sha256:...",
    "origin_author_proof_ref": "cx:event:<原作者签名 event 引用>",
    "source_frontier_ref": "cx:anchor:<导入时源 Space frontier>"
  },
  "content": { "kind": "cx.content.text", "body": "..." }
}
```

**规则**：
- `importer.actor_id` 是把内容从源 MLS group 转移到目标 MLS group 的 actor；reader UI MUST 显著区分"原作者直接发言"vs"由 X importer 声称引自"
- `import_signature` 防止 importer 字段被第三方篡改，但**不证明 `claimed_origin` 真实存在**
- `optional_proofs.origin_event_hash` / `origin_author_proof_ref` 在 importer 有能力获取时 SHOULD 提供，提升信任级别
- `optional_proofs.source_frontier_ref` 与 `context_anchor.source_anchor_ref` 对齐
- 源消息后续被 redact 不自动撤回 import_attestation（两个独立 redaction 域）；mirror Space SHOULD 通过周期性 reconcile 把 stale import 标记为 `origin_locked`

**Fallback 渲染**：未支持本 block 的客户端 MUST 显示 `body` + 一行"（importer 声称引自另一 Space）"通用提示——不显示 `claimed_origin` 的具体 ID（避免暴露 source 是否存在）。

---

### 3.5 改动 E — Cross-Space Agent Membership 变更通知

**目标**：源 Flow 加/减 agent 时，把变更推到该 agent 所属 controller 的 workspace，让 controller 在自己的 mirror Space 看到并决定是否对应调整。

**文件**：
- `spec/v1/zh/discovery/push-notifications.md` — 新增 `notification_type=agent_membership_change`
- `spec/v1/zh/models/private-objects.md` §3 — 在 notification_type 枚举加入新值

**Notification payload**（脱敏后）：

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

**规则**：
- 推送目标 actor = agent DID Document 的 `controller` 字段所指 principal
- E2EE workspace：preview 由源 Space 中的 *invited agent 自己*（或 inviter controller，如果就是同一 principal）在客户端脱敏后置入；服务端不得明文重写
- 收到通知后 controller client SHOULD 在 mirror Flow（如果存在）写一条 `cx.system.notice` 提示；不自动改 mirror Flow membership

### 3.6 改动 F — `cx.schema.agent_task.v1` 对象 + 事件家族（Rev 3 新增）

**目标**：Rev 2 把任务生命周期塞进 Message state 是错误的（Message state enum 是 `{active, redacted, deleted}` 不可扩，且没有 `cx.message.update` event kind）。Rev 3 把 agent task 单独建模为一等对象。

**文件**：
- `spec/v1/zh/extensions/agent-workspace-profile.md` — 新增 agent_task 章节
- `artifacts/schemas/agent-task.schema.json` — 新增对象 schema
- `artifacts/registry/event-kind-registry.json` — 注册 `cx.agent_task.create` / `cx.agent_task.execution.transition` / `cx.agent_task.transparency.transition` / `cx.agent_task.source_authority.transition` / `cx.agent_task.cancel`（Rev 6 修订：5 个事件，三 cell 独立 transition）
- `artifacts/registry/id-kind-registry.json` — 注册 typed ID 前缀 `cx:agent_task:`

**对象 schema sketch（Rev 6 修订：移除单 state 字段，状态在 3 个独立 FSM cell）**：

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
  "created_at": "2026-05-16T10:00:00Z"
}
```

> **Rev 6 修订**：删除 `state` 与 `state_changed_at` 字段——agent_task 的状态在三个独立 FSM cell（见下文 FSM cells 章节），不在 object schema 顶层。query 时通过 cell head 读，不通过 object snapshot 读。这避免了"object 顶层 state 字段 vs FSM cell head"双源 truth。

**FSM cells（Rev 5 修订：拆为 3 个正交 cell，每个独立 FSM）**：

> Rev 4 用单 state cell 把 execution、transparency、source_authority 混在一起，导致"同时 transparency_lost 与 source_authority_revoked"无法表达（FSM 一次只能在一个 state）。Rev 5 拆为 3 个正交 FSM cell，agent runtime 执行条件 = 三者的合法组合。

每个 agent_task 对象关联三个独立 FSM cell：

| Cell key | Lattice | 描述 | states |
|---|---|---|---|
| `agent_task.<task_id>.execution_state` | `fsm` | 任务主流程 | `pending_source_stub`, `active`, `completed`, `cancelled_stub_rejected`, `cancelled_orphan`, `cancelled_by_controller` |
| `agent_task.<task_id>.transparency` | `fsm` | 源 stub 透明度 | `ok`, `lost`, `reconfirmed_after_loss` |
| `agent_task.<task_id>.source_authority` | `fsm` | 源 Space 内 agent 的 capability 状态 | `ok`, `revoked`, `reconfirmed_after_revoke` |

**Agent runtime 执行 gate（核心 invariant）**：

```text
agent_task may be executed iff:
  execution_state == "active"
  AND transparency ∈ {"ok", "reconfirmed_after_loss"}
  AND source_authority ∈ {"ok", "reconfirmed_after_revoke"}
```

任一 cell 不在允许集合 → agent runtime MUST 暂停。两个失效维度可同时存在（一个 task 可以**既** transparency=`lost` **又** source_authority=`revoked`），UI 显示两个独立 banner，controller 分别决策两个维度。

**事件家族（Rev 5 修订）**：

```text
cx.agent_task.create               → 创建 agent_task，初始化所有 3 个 cell（默认 execution=pending_source_stub|active, transparency=ok, source_authority=ok）
cx.agent_task.execution.transition → 写 execution_state cell
cx.agent_task.transparency.transition → 写 transparency cell
cx.agent_task.source_authority.transition → 写 source_authority cell
cx.agent_task.cancel               → 便捷事件（reducer 等价于 execution.transition → cancelled_by_controller）
```

每个 transition event 用 `transition` lattice op（[event-schema.json:1098,1105](spec/v1/artifacts/schemas/event-schema.json)），payload 含 `op=transition` + `from` + `to` + `reason` + 可选 `evidence_refs`。

**示例 transition payload**：

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

**合法 transition 表（每 cell 独立）**：

**Cell 1: `execution_state`**

```text
[initial create]    → pending_source_stub        (Phase 1 with source routing)
[initial create]    → active                     (direct task creation, no source routing)

pending_source_stub → active                     (Phase 3 reconcile)
pending_source_stub → cancelled_stub_rejected    (Phase 2 source-side reject)
pending_source_stub → cancelled_orphan           (TTL housekeeping)
pending_source_stub → cancelled_by_controller
active              → completed                  (controller mark complete)
active              → cancelled_by_controller
```

Terminal：`completed`, `cancelled_*` 出度为零。

**Cell 2: `transparency`**（Rev 7 修订：删除不可达边）

```text
[initial]                  → ok                            (default)

ok                          → lost                          (watcher: source stub redacted)
lost                        → reconfirmed_after_loss        (controller continues with audit-marked task)
```

`lost` 和 `reconfirmed_after_loss` 都是**实质 terminal**——源 stub redaction 是 Message terminal state，无法 un-redact；不存在二次 redaction trigger，所以无 `reconfirmed_after_loss → lost` 这种边。

**Cell 3: `source_authority`**（Rev 7 修订：删除不可达边）

```text
[initial]                  → ok                            (default)

ok                          → revoked                       (watcher: source grant revoke / member remove)
revoked                     → reconfirmed_after_revoke      (controller continues with already-imported content)
```

`revoked` 和 `reconfirmed_after_revoke` 也是**实质 terminal**——mention_redirect.authority_grant_ref 绑定到**原 grant_id**，原 grant 一旦 revoked 对该 task 永久失效。Source 之后 re-grant 是新 grant_id，与已存在 task 无关；不存在 "恢复" 或"二次 revoke"路径。

**Reducer 行为**：

- 非合法 transition（`from=X, to=Y` 不在表中）→ `failed_precondition`（reason=`invalid_task_fsm_transition`，response 含 `(cell_key, current_state)`）
- 多 watcher idempotent：FSM `from` precondition 天然保证只有第一个 watcher 成功，后续 `failed_precondition` no-op
- 并发互斥 transition（同 cell 同 from 不同 to，causally concurrent）→ cell `⊥`；按 §3.2 同款 recovery saga 处理（deterministic winner = 优先 terminal 状态 / 否则 lex-min state 名）

**为什么三正交 cell 优于组合状态**：

- 组合状态需要枚举 `n × m × k` 状态（这里 6×3×3 = 54），不可维护
- 正交 cell 让"两个失效维度同时存在"自然可表达
- agent runtime gate 是显式的 invariant 检查（不是状态机迁移）
- watcher 关心的维度独立写（transparency watcher 不需要懂 source_authority）

**为什么不在 Message 上堆 state**：

- Message state enum 是 `{active, redacted, deleted}`（[message.schema.json:121](spec/v1/artifacts/schemas/message.schema.json)），改动会破坏现有 reducer
- 没有 `cx.message.update` event；只有 revise/redact
- Task 是有独立 lifecycle 的工作单元，conceptually 不是 message
- Agent runtime / controller UI 都需要查询"我有哪些 active task"，独立对象更易索引

**与 Message 的关系**：

- agent_task 是 mirror Flow 时间线中的一种对象（与 Message 并列）
- agent 执行 task 产出的回复以 `cx.message.create` 写入同一 mirror Flow，用 `cx.relation.references(from=message, to=agent_task)` 关联
- controller 与 agent 的对话延续仍是 Message——agent_task 只是"任务"原子单元

## 4. 生命周期场景（Normative）

### 4.1 用户首次 @-自己的-agent（Rev 3：Saga + agent_task 事件家族）

> **Rev 3 修订**：使用独立 `cx.agent_task.*` 事件家族而非虚构的 `cx.message.update` + Message state 扩展。

**前置**：客户端 SHOULD 先调用 `agent_workspace.resolve_mirror_flow(source_flow_id)`；不存在则按 §3.2 lazy 创建流程先 provision mirror Space + mirror Flow（写入 `agent_workspace.mirror_flow_by_source:<source_flow_id>` 唯一性 cell）。

**Phase 1 — Mirror 端创建 pending task**：

1. 客户端生成 `redirect_pair_id`（UUID）
2. 在 mirror Space 写 `cx.agent_task.create`（Rev 6 修订：初始化三个 FSM cell 的初值）：
   - `target_agent_id` = Alice 的 agent
   - `instruction.body` = 真实指令正文
   - `context_anchor.trigger_redirect_pair_id` = 步骤 1 生成的 ID
   - `context_anchor.source_anchor_ref` = source Flow 当前 frontier 的 Anchor
   - `context_anchor.source_frontier_hash` = 该 frontier 的 hash
   - **三 cell 初值**：`execution_state=pending_source_stub`, `transparency=ok`, `source_authority=ok`
3. Agent runtime 见 execution_state cell head = `pending_source_stub` MUST NOT 执行——等待 Phase 3

**Phase 2 — Source 端写 stub**：

4. 在 source Space 写 `cx.message.create`，content = `cx.content.mention_redirect`：
   - 同一 `redirect_pair_id`（双端关联的 opaque UUID）
   - `authority_grant_ref` = 源 Space 中 Alice 给 agent 的 capability grant
   - Event 顶层 `requirements.critical_extensions[] = [{id:"cx.feature.mention_redirect.v1", scope:"payload", fail_closed:true, schema_ref:"cx.schema.content.mention_redirect.v1"}]`

**Phase 3 — Mirror 端 reconcile**：

5. 客户端在 stub Move 确认 anchored 后，写 `cx.agent_task.execution.transition` 到 mirror Space（Rev 6 修订事件名）：
   - cell = `agent_task.<task_id>.execution_state`
   - lattice op = `transition`，`from=pending_source_stub`, `to=active`
   - `evidence_refs = [cx:event:<source stub event id>]`（单方面记录，供 audit；source Space 不存反向引用）
6. Agent runtime 见三 cell 满足执行 gate（`execution_state=active` ∧ `transparency ∈ {ok, reconfirmed_after_loss}` ∧ `source_authority ∈ {ok, reconfirmed_after_revoke}`）才开始执行

**失败路径**：

- **Phase 2 在 source Space 被 reject**（capability 失效 / grant 已 revoke / 源 Space 拒绝 redirect）：
  - 客户端 MUST 写 `cx.agent_task.execution.transition`：`from=pending_source_stub, to=cancelled_stub_rejected`
  - Task 保留供 audit；agent 不执行
- **Phase 1 成功但客户端断网，Phase 2/3 未完成**：
  - execution_state cell 停在 `pending_source_stub`
  - Mirror Space 的 sync node SHOULD 在 `created_at + TTL`（默认 24h）后自动 anchor 一条 `cx.agent_task.execution.transition(from=pending_source_stub, to=cancelled_orphan, reason=ttl_expired)`
  - **重要**：这是 sync node 代行的 housekeeping，事件的 `created_by` 仍是 controller 的 principal（或 system actor，需在 §authz 注册一个 housekeeping capability），不是 reducer "凭空"产生——保持 event 都有签名来源
  - Reconcile 协议：客户端重连后通过 `agent_workspace.list_pending_tasks` op 查询自己未完成的 pending pairs，决定 retry 或 cancel

**冗余字段语义**：mirror agent_task 在 Phase 3 后存的 `source_stub_event_ref` 是单方面 audit 锚；source Space 不存反向引用（避免 source Space 看到 mirror 元数据）。

### 4.2 用户增加新 agent 到 source（Rev 3 修订）

> Rev 3：spec 没有 Flow-level membership；agent 加入是 Space 级 `cx.member.state` + 写入 `cx.capability.grant`。

1. Alice 在源 Space 写 `cx.member.state`(actor=agent_Y, state=member) **以及** `cx.capability.grant`(grantee=agent_Y, constraints=`agent_member_profile`展开的 grant 集)
2. 如果走 §3.1 路径 B（per-Flow scope），agent_Y 加入的是 Flow 的 `discussion_space_ref` child Space，不是父 Space
3. 源 Space reducer 验证：
   - `cx.capability.grant.attached_authority` 中 agent_authority controller == Alice's principal（按 §3.3 的三种证据形式之一）
   - Alice 在源 Space 有 `member.invite` / `capability.grant` 能力
4. 成功后推送 `agent_membership_change` 到 Alice 的 workspace（详见 §3.5）
5. Alice 的 mirror Space（如果存在）显示"agent_Y 已加入源 Space"——**不自动加入 mirror Space**，Alice 显式决定

### 4.3 用户从 source 移除 agent（Rev 4 修订：触发 task FSM 转换）

1. Alice 在源 Space 写 `cx.capability.revoke`(grant=<agent_Y grant>) **以及** `cx.member.state`(actor=agent_Y, state=removed)
2. 该 agent 在源 Space 的所有 capability grant 失效；后续 read / write 拒绝
3. 推送 `agent_membership_change` 到 Alice 的 workspace
4. **Watcher 触发的 source_authority cell transition（Rev 7 修订：read-then-write + 简化为 2 条边）**：
   - Watcher（controller's client / agent runtime / sync node housekeeping）观察到 `cx.capability.revoke` 或 `cx.member.state(removed)` 事件被 anchor
   - 对该 agent 在 Alice 的 mirror Space 中所有 execution_state ∈ {pending_source_stub, active} 的 agent_task：
     - **先读** `agent_task.<task_id>.source_authority` cell 当前 head
     - 当前 = `ok` → 写 `cx.agent_task.source_authority.transition(from=ok, to=revoked)`；`reason = "source_grant_revoked"`，`evidence_refs = [<revoke event>]`
     - 当前 ∈ `{revoked, reconfirmed_after_revoke}` → no-op skip（已是 terminal 失效，不重复写）
   - 已经处于 `transparency=lost` 的 task：transparency cell 状态不变；source_authority cell 独立写 → `revoked`。两个 banner 并存

> **Rev 7 修订**：Rev 6 列了二次失效边（`reconfirmed_after_revoke → revoked`），但分析表明这条边不可达（authority_grant_ref 绑定原 grant_id，re-grant 是新 grant 与已有 task 无关）。删除该边后，watcher 简化为"ok → revoked 单方向"；多 watcher 并发由 FSM `from=ok` precondition 保证只第一个成功。
5. Agent runtime 因 source_authority ∈ {revoked} 不满足执行 gate（§3.6），MUST 停止执行
6. UI banner："source 已撤销此 agent 的权限；任务暂停，等待你确认"
7. Controller 决策（写 source_authority cell）：
   - 继续（基于已导入到 mirror 的内容，不能再 fetch 源）：transition `from=revoked, to=reconfirmed_after_revoke`
   - 取消整个任务：分开两步（或便捷事件 `cx.agent_task.cancel`）—— `execution_state` transition to `cancelled_by_controller`
8. **Alice 的 mirror Space 不自动移除 agent_Y**——历史记忆有保留价值
9. 后续 mirror Space 中 `context_anchor` 引用源对象但 agent_Y 已无读权，display 降级 `locked`（[relation.md §4.5](spec/v1/zh/models/relation.md) 反枚举）

**与 transparency 的关系（Rev 5：两个正交维度）**：

| 触发 | 写哪个 cell | 含义 | Controller 选项 |
|---|---|---|---|
| source stub 被 redact | `transparency` → `lost` | 透明度证据丢失，但 agent 技术上仍能读 source | transition `transparency` to `reconfirmed_after_loss` 或 cancel 整 task |
| source grant revoke / 成员移除 | `source_authority` → `revoked` | agent 技术上失去 source read 能力 | transition `source_authority` to `reconfirmed_after_revoke` 或 cancel 整 task |

两者**完全独立**——同一 task 可以同时处于 `transparency=lost` + `source_authority=revoked`；controller 分别 reconfirm / cancel 两个维度。Agent runtime gate 检查三个 cell 的合法组合。

### 4.4 用户在 mirror Space 加新 consulting agent（Rev 3 修订）

1. Alice 在 mirror Space 写 `cx.member.state`(actor=agent_Z) + `cx.capability.grant`(grantee=agent_Z)
2. mirror Space reducer 验证 agent_Z 的 agent_authority controller == Alice（profile MUST）
3. **agent_Z 对源 Space 没有任何访问能力**——它只能基于 mirror Space 中已存在内容（包括 primary agent 通过 import_attestation 引入的内容）工作
4. 如果 agent_Z 需要源 Flow 上下文，**必须**由 primary agent（在源 Space）摘要重加密引入

### 4.5 Source Flow / Source Space 被 archive 或 delete

1. Source Flow `state=deleted`
2. Mirror Flow 的 `context_anchor`、`derived_from` 引用变为 stale；UI 标记 `origin_locked`
3. Mirror Flow 本身不受影响（独立治理域）
4. 推送通知 `agent_membership_change(change_kind=source_deleted)` 给 controller

### 4.6 Controller 离开 source Space

1. Alice 失去源 Flow 访问
2. Alice 自己的 agent 在源 Flow 的 membership：取决于源 Space governance（可能 cascade 移除，可能保留）
3. Mirror Flow 继续存在；Alice 仍可回看历史
4. 后续无法触发新 @-routing（不再是源成员）

### 4.7 反向写回（agent 工作产出回到 source Flow）

> 这是闭环的关键一步：mirror Flow 里 agent 产出回复后，怎么把这个回复发回 source Flow？

**v1 默认路径：controller 手动 publish**

1. Mirror Flow 中 agent 产出一条 `cx.message.create`（content 为草稿）；agent 用 `cx.relation.references(from=draft_message, to=agent_task_id)` 关联回该任务
2. Controller 在 mirror Flow UI 看到草稿，可编辑、修改、追问 agent 重写
3. Controller 满意后点击 "publish to source Flow"，客户端：
   - 在 source Flow 写 `cx.message.create`，**`created_by = controller principal`**（不是 agent）
   - content 可选包含 `cx.content.import_attestation` 块引用 mirror Flow 的 agent 草稿（用于审计与归属透明）
   - 在 mirror Flow 写 `cx.relation.create(published_to, from=mirror_message, to=source_message)` 标记已发布
   - 在 mirror Space 写 `cx.agent_task.execution.transition` 收尾该 task（Rev 7 修订：read-then-write）：
     - **先读** `agent_task.<task_id>.execution_state` cell 当前 head
     - 当前 = `active` → 写 `from=active, to=completed`
     - 当前 ∈ terminal 状态（`cancelled_*` / `completed`）→ abort publish 流程，告知 controller "任务已不在 active 状态"（可能另一设备已 cancel）
     - 当前 = `pending_source_stub`（不可能到达 publish 步骤，但防御）→ abort
   - controller 离线期间 task 状态可能变化（另一设备触发 cancel、TTL housekeeping 等），盲写 `from=active` 会 `failed_precondition`；read-then-write 让 UI 清晰处理
4. Audit 后果：source Flow 看到的是 Alice 自己的发言；如果 Alice 选择包含 import_attestation，其他成员能看到"由 agent_X 起草"——**完全由 Alice 决定披露程度**

**为什么不让 agent 直接发**：

- 现在 spec 没有 `on_behalf_of` Message 字段（v1 显式不做，见 §5）
- agent 直接发会让 audit 上 sender = agent DID，但意图来自 Alice——归属混淆
- Controller 手动 publish 是**最简单、最安全、不需要新协议的实现**

**支持的变体**（v1 内可由客户端选择）：

- ✅ **Publish as self**（默认）：sender = controller，可选 quote agent draft
- ✅ **Publish verbatim**：直接把 agent 草稿文字 paste 进新 message，不带 quote attribution（controller 完全承担）
- ✅ **Don't publish**：不回 source Flow，纯私下讨论结束

**v2 路径（推迟）**：

如果 v2 引入 `on_behalf_of` Message 字段 + delegation attestation，agent 才能以 `created_by=agent` + `on_behalf_of=controller` 的方式直接发到 source Flow。此模式需要：

- Source Space 接受这种"双签名"消息的 policy hook
- Capability `agent_member_profile.may_publish_on_behalf` 显式 grant
- audit UI 标准化的"agent 代表 X 发"渲染

v1 不做，因为 controller 手动 publish 已经覆盖 95% 用例且零协议成本。

### 4.8 Source stub 被 redact 后的 mirror task 处理（Rev 3 重写：observe-then-write）

> Source stub 是"agent 私下被指挥"这一事实的**透明度证据**。stub 被 redact 后透明度丢失，mirror 端任务可能已经执行或正在执行——需要明确语义。
>
> **Rev 3 关键修订**：mirror Space reducer **不能**消费 source Space 事件（跨 Space reducer 副作用不成立）。改为"controller / agent runtime **观察** source Space 后**在 mirror Space 显式写** reconciliation 事件"。

**架构原则**：
- mirror Space reducer 只消费 mirror Space 本地事件
- 跨 Space 联动 = **客户端 / agent runtime 作为 watcher** 同步两边状态后写入对应事件
- 没有"reducer cascade"——所有跨 Space 状态变化都有 audit-trail 事件
- 这样跨 deployment / sovereign realm 也工作

**Trigger**：source Space 中针对 `mention_redirect` event 的 `cx.redaction` 事件被 anchor。

**Reconciliation 流程**：

1. **Watcher**（controller's client、agent runtime、或两者）观察到该 redaction 事件
2. Watcher 在 mirror Space 写 transparency cell transition（Rev 6 事件名）：
   - 通过 `redirect_pair_id` 查找对应 `agent_task`
   - 写 `cx.agent_task.transparency.transition`（FSM op，见 §3.6 三 cell 模型）：
     - **先读** `agent_task.<task_id>.transparency` cell 当前 head
     - 当前 = `ok` → 写 `cx.agent_task.transparency.transition(from=ok, to=lost)`；`reason = "source_stub_redacted"`，`evidence_refs = [cx:event:<source redaction event>]`
     - 当前 ∈ `{lost, reconfirmed_after_loss}` → no-op skip（Rev 7：删除原"reconfirmed_after_loss → lost"边，因为 Message redaction 是 terminal 不可达）
   - `created_by = watcher's actor DID`（不是凭空；watcher 的签名是 audit 来源）
3. **Reconciliation responsibility 优先级**（决定谁负责写）：
   - Controller's online client（首选，能立刻响应）
   - Agent runtime（如果 controller 离线，agent 自己负责暂停）
   - Sync node housekeeping（最后兜底，TTL 触发，使用 system actor capability）
4. **多方同时写 reconciliation 的 idempotent 处理（Rev 6 修订：FSM read-then-write + from precondition）**：
   - 每个 watcher 先读 transparency cell head，再按当前 state 写合法 transition（见步骤 2）
   - 第一个 watcher 写 `transition(from=<X>, to=lost)` 成功；cell 已 transition 到 `lost`
   - 第二个 watcher 后到达：先读看到 cell = `lost` → 决定 skip（避免无效 transition）
   - 即使第二个 watcher 用了过时的 read（race），其 transition `from=<X>` precondition 在 anchor 时不再成立 → `failed_precondition` no-op，不污染状态
   - 不需要 cas-register 或 tuple dedupe；FSM `from` precondition + watcher read-then-write 双层保证
5. Agent runtime 见 transparency cell = `lost` MUST 停止执行（即使 execution_state 还是 `active`）
6. Client UI MUST 显示 banner："source 已撤回此次 mention；任务暂停，等待你确认"

**Controller 决策路径（Rev 6 修订事件名）**：

- 继续：controller 写 `cx.agent_task.transparency.transition`(from=`lost`, to=`reconfirmed_after_loss`)；agent 继续
- 取消整任务（不是 transparency cell 的 transition；是 execution cell）：写 `cx.agent_task.execution.transition`(from=`active`, to=`cancelled_by_controller`)；或便捷事件 `cx.agent_task.cancel`

**为什么 watcher 模式优于 reducer cascade**：

- mirror Space reducer 不需要跨域 fetch source Space 状态
- 跨 deployment / sovereign realm 自然工作
- 每个状态变化都有签名 audit-trail（watcher 是谁、看到了什么、何时写入）
- watcher 不可达时不会"卡住"——其他 watcher 可以接力，TTL housekeeping 兜底

**潜在问题：watcher 撒谎/延迟**：

- Watcher 写假 `transparency_lost` 但实际 source stub 未被 redact——`evidence_refs` 含 event ID，任何后续 audit 可独立 fetch source Space 验证
- Watcher 漏看 redaction——多 watcher 并行 + TTL housekeeping 兜底；客户端 reconnect 时 SHOULD 主动 reconcile pending/active tasks 的 source stub 当前状态

## 5. v1 显式不做的事

- ❌ **`cx.grant.delegate_read`（scoped read 委托新增）**——MLS E2EE 下无法干净实现；**而且 spec 已有 `cx.schema.agent_authority.v1` 的 `knowledge_sources[]` 表达非 plaintext 范围的访问**（`visibility=metadata_only|derived_summary|ciphertext_only`），覆盖了大量场景；plaintext 跨 E2EE 边界继续走"primary agent 重加密引入"模式
- ❌ **Server-side @ mention 路由**——routing 是 client UX，server 不重写消息；source Flow stub 和 mirror Flow 真实指令是**两条独立 event**，由客户端通过 §4.1 saga 协调（**不是**单步原子提交），不存在 server-side fork
- ❌ **`on_behalf_of` Message 字段**——v1 仍以 agent DID 作为 `created_by`；agent 代表 controller 发言的语义由 capability constraint（agent_member_profile）+ `cx.schema.agent_authority.v1` `controller` 字段（按 §3.3 的三种证据形式）联合表达，足够 audit
- ❌ **Mirror Space 单点 deterministic 命名 `f(controller, source_space) → mirror_id`**——通过 controller 私有 sync node 维护索引 view + Relation 关联即可，不必引入全局确定性命名（避免元数据泄露 + 命名冲突）

## 6. 互操作 & Conformance

### 6.1 影响 profile

**Rev 5 分层澄清**：源 Space 中的 `mention_redirect` 与 mirror Space 的 `agent_workspace` profile 是**两个独立 enforcement 层**：

| 检查 | 责任端 | 触发条件 | 失败行为 |
|---|---|---|---|
| `cx.feature.mention_redirect.v1` | 源 Space reducer / 服务端 | Event 顶层 `requirements.critical_extensions[]` 含此 feature id | 服务端未声明支持 → reject 整条 event；与 mirror 端是否支持 `agent_workspace` profile **无关** |
| `cx.feature.import_attestation.v1` | mirror Space reducer / 服务端（或源 Space，若 controller 选择把 import_attestation 写回源） | 同上 | 同上 |
| `cx.profile.agent_workspace.v1` | mirror Space 自身（profile 声明 invariants） | Space 创建时 profile 声明 | 不支持的服务端**只**拒绝针对该 mirror Space 的写入；**不**影响源 Space 的 mention_redirect 接受 |

**Profile 影响**：

- `client_basic`：MUST 能正常发送 / 接收 source Flow 中的 mention_redirect（仅需支持 critical_extensions feature check）；MAY 不实现 mirror Space 端的 agent_workspace profile
- `agent_runtime`：SHOULD 实现完整 mirror Space + agent_task FSM + watcher 逻辑
- `enterprise_client`：SHOULD 实现，并提供 mirror Space UI

> **Rev 5 修订**：Rev 4 §9.2 写"不支持 agent_workspace profile 的服务端 MUST reject mention_redirect"是层级混淆——mention_redirect 是源 Space 能力，与 mirror 端 profile 无关。源 Space 拒绝 mention_redirect 的依据是 feature critical_extension 不支持，**不是** mirror profile 不支持。

### 6.2 Conformance vectors（Rev 2 修订与扩充）

需在 `artifacts/conformance/` 添加：

1. ✅ **agent_member_profile 展开**：声明 preset → 展开为标准 `cx.capability.grant` 事件序列；reducer 不依赖 preset name
2. ✅ **mention_redirect 不暴露 private IDs**：source Flow 第三方 reader 拿到 stub 后 MUST NOT 能从字段中提取 mirror Space/Flow/Event ID
3. ✅ **mention_redirect target 必须是 sender 的 agent**：sender ≠ controller(target_actor_id) → reducer `unauthorized` reject（**不降级**为普通 mention）
4. ✅ **mention_redirect critical_extensions 强制**：未声明 `cx.feature.mention_redirect.v1` 支持的 reducer MUST fail-closed reject 整条 event
5. ✅ **mention_redirect authority_grant_ref 校验（Rev 3）**：reducer 通过 `authority_grant_ref` 找到源 Space 中 active 的 `cx:grant:...`，验证 grant 的 grantee == `target_actor_id`，grant 的 attached_authority controller == sender principal；任一不满足 → `unauthorized`
6. ✅ **import_attestation 性质**：篡改 `import_signature` → reader 标记 `import_signature_invalid`；篡改 `claimed_origin.message_id` 但保留有效 signature → 标记 `unverifiable_origin`（**不**等同于"伪造"，因为 importer 仅声称）
7. ✅ **Mirror 基数双向收紧（Rev 2）**：尝试给同一 mirror Flow 第二个 `derived_from` source Flow → `cardinality_violation`；尝试同一 source Flow 被两个 mirror Flow 指向 → `cardinality_violation`
8. ✅ **多设备并发首次创建竞态**：两设备同时为同一 source Flow 创建 mirror Flow，**MUST 收敛到一个 winner**，loser 设备的本地 draft 自动重定向
9. ✅ **agent_membership_change 通知脱敏**：E2EE workspace 收到的 preview MUST 由客户端预先脱敏
10. ✅ **Mirror Flow consulting agent 不能读源 Flow**：agent_Z 通过 cross-Space reference 尝试 fetch source content → `unauthorized`
11. ✅ **Source Flow archive 后 mirror context_anchor 降级**：stale anchor MUST 显示 `origin_locked`
12. ✅ **Saga Phase 2 失败回滚（Rev 6）**：source stub Move 被 reject → 客户端在 mirror 写 `cx.agent_task.execution.transition(from=pending_source_stub, to=cancelled_stub_rejected)`；agent runtime MUST NOT 执行
13. ✅ **Saga orphan GC（Rev 6）**：execution_state cell 停在 `pending_source_stub` 超过 TTL → sync node housekeeping 写 `cx.agent_task.execution.transition(from=pending_source_stub, to=cancelled_orphan)`
14. ✅ **Source stub redacted → mirror transparency=lost（Rev 6 observe-then-write + read-then-write）**：watcher 先读 transparency cell head，按当前 state 选合法 transition，写 `cx.agent_task.transparency.transition(from=<observed>, to=lost, evidence_refs=[cx:event:<redaction>])`；agent runtime 停止执行；多 watcher 并发写通过 FSM from precondition 自然 idempotent
15. ✅ **二次失效 transition（Rev 6 新增）**：transparency 在 `reconfirmed_after_loss` 时再次被 redact → watcher 写 `from=reconfirmed_after_loss, to=lost`（合法 transition）；conformance vector 验证 reducer 接受
16. ✅ **DID Document 不暴露 workspace Space ID（Rev 2）**：`ContrixAgentWorkspaceService` endpoint 未鉴权 GET 返回 401/403 而非 404
17. ✅ **Unsupported profile fail-closed（Rev 5 修订）**：不支持 `cx.profile.agent_workspace.v1` 的服务端拒绝针对该 mirror Space 的 agent_task / import_attestation 写入；源 Space 的 mention_redirect 接受由 `cx.feature.mention_redirect.v1` critical_extension 独立检查
18. ✅ **Reservation orphan TTL cleanup（Rev 6 新增）**：reservation cell 写成功但 follow-up `cx.space.create` / `cx.flow.create` 未在 TTL 内提交 → housekeeping 写 cleanup Move，cell 回到 null 允许重新 reserve
19. ✅ **Recovery Move 完整 refs（Rev 6 新增）**：缺 state_witness 或 inclusion_proof critical ref → reject；issuer 无 `cx.capability.agent_workspace.recover` → unauthorized reject

## 7. 文档树变更总览

| 路径 | 操作 | 说明 |
|---|---|---|
| `spec/v1/zh/authz/capabilities.md` | 编辑 | 新增 Agent Member Profile 章节 |
| `spec/v1/zh/extensions/agent-workspace-profile.md` | **新增** | Space profile 定义 + lazy 创建语义 + 生命周期 |
| `spec/v1/zh/extensions/agent-protocol-interop.md` | 编辑 | 关联到 agent-workspace-profile |
| `spec/v1/zh/identity/identity-did.md` | 编辑 | 新增 `ContrixAgentWorkspace` service entry |
| `spec/v1/zh/models/content-types.md` | 编辑 | 新增 `mention_redirect` + `import_attestation` block |
| ~~`spec/v1/zh/models/flow-and-message.md`~~ | ~~编辑 Message context_anchor~~ | **Rev 5 删除**：Message schema 不变；context_anchor 在 agent_task 顶层（§3.6） |
| `spec/v1/zh/discovery/push-notifications.md` | 编辑 | 新增 `agent_membership_change` notification type |
| `spec/v1/zh/models/private-objects.md` | 编辑 | notification_type 枚举扩展 |
| `spec/v1/zh/spec-map.md` | 编辑 | 把 agent-workspace pattern 加入阅读路径 |
| `artifacts/profiles/agent-member-profiles.json` | **新增** | 4 个 capability preset |
| `artifacts/profiles/conformance-profiles.json` | 编辑 | 注册 `cx.profile.agent_workspace.v1` |
| `artifacts/schemas/content-mention-redirect.schema.json` | **新增** | block schema（Rev 7：含 authority_grant_ref / redirect_pair_id；删除 redirect_event_commitment） |
| `artifacts/schemas/content-import-attestation.schema.json` | **新增** | block schema（替代 Rev 1 `content-quote-external`） |
| `artifacts/schemas/agent-task.schema.json` | **新增** | `cx.schema.agent_task.v1` 对象 + context_anchor；**Rev 6：无顶层 state 字段，状态在三个独立 FSM cell** |
| `artifacts/registry/event-kind-registry.json` | 编辑 | 注册 5 个事件（Rev 6）：`cx.agent_task.create` / `cx.agent_task.execution.transition` / `cx.agent_task.transparency.transition` / `cx.agent_task.source_authority.transition` / `cx.agent_task.cancel` |
| `artifacts/registry/id-kind-registry.json` | 编辑 | 注册 `cx:agent_task:` typed ID 前缀 |
| `artifacts/registry/cell-key-registry.json`（若存在） | 编辑 | 注册 5 个 cell key namespace（Rev 6）：`mirror_space_by_source` / `mirror_flow_by_source` / `agent_task.<id>.execution_state` / `agent_task.<id>.transparency` / `agent_task.<id>.source_authority` |
| `artifacts/schemas/capability-grant.schema.json` | 编辑 | 新增 `attached_authority` 可选字段（3 个 evidence_kind oneOf，§3.3） |
| `artifacts/schemas/content-source-export-policy-attestation.schema.json` | **新增** | source_export_policy_attestation canonical schema（§10.3） |
| `artifacts/schemas/space.schema.json` | 编辑 | profile 枚举增加 `cx.profile.agent_workspace.v1` |
| `artifacts/conformance/agent-workspace/*` | **新增** | 16 个 conformance vector（见 §6.2） |

---

## 8. 自审：可能的漏掉点 & 风险

> 写完上面 7 节后做的 second-pass，列出仍不确定或可能漏掉的点。

### 8.1 已识别但未在主提案中详述的点

**A. 源 Space 整体禁用 agent 的策略**
源 Space admin 可能要全局禁止"任何人加 agent"。该能力通过现有 capability constraint policy 表达（拒绝向 agent DID 颁发任何 grant，或 `cx.member.state` 转换中校验 actor 类型）。**`agent_member_profile` 不绕过 Space-level "agents disabled" policy**——已在 §3.1 写明。

**B. Agent 身份验证：已通过 `cx.schema.agent_authority.v1` 解决**
~~`controller` 字段是否存在的疑问~~ 已 grep 验证：spec 已经有 [`cx.schema.agent_authority.v1`](spec/v1/zh/crypto-media/encryption-and-audit.md) 承担 controller↔agent 绑定 + capability delegation + knowledge_sources，[schema-registry.md:62](spec/v1/zh/conformance/schema-registry.md) 已注册。本提案 §3.1 已修正为引用此 schema，**不引入新字段**。
**剩余确认项**：grep 检查 `agent_authority.v1` 的实际 JSON schema 是否在 `artifacts/schemas/` 已落地、字段名是否与本提案 reducer 校验逻辑一致。

**C. 跨 deployment / federation 场景**
源 Space 在组织 B 的 deployment，controller workspace 在 deployment A。跨 deployment 的：
- `derived_from` Relation 创建——走现有 [federation.md](spec/v1/zh/sync/federation.md) cross-realm reference 规则
- `agent_membership_change` notification 跨 deployment 推送——走 push gateway 跨域语义
- Mirror Space 是否能在 deployment A 持有 import_attestation 的"重加密自 deployment B"内容——*技术上没问题*（重加密在 controller client 完成），但合规上某些 deployment 可能禁止外部数据驻留
- **风险**：本提案没明确说明跨 deployment 是否所有改动都互操作；conformance vector 需要包含一个 cross-deployment 场景

**D. Other party 的 agent 被 mention**
Alice @ Bob's-agent（Bob 的 agent）—— `mention_redirect` 的 reducer 校验要求 `target.controller == sender`，Alice 不满足。此时事件 reject 还是降级为普通 `cx.content.mention`？
- **建议**：reducer 拒绝 `mention_redirect`（明确这是 self-routing 专用 block）；客户端要发普通 mention 用 `cx.content.mention`
- 这条需要写进 §3.3 改动 C 的 normative MUST

**E. Agent 主动写入 mirror Flow（无 @ 触发）**
Primary agent 在 source Flow 观察到值得关注的事，主动写 alert 到 mirror Flow。agent 怎么知道 mirror Flow 的 ID？
- 路径：agent 查 controller DID Document `ContrixAgentWorkspace` service → 找到 workspace root → 查 Relation 找 mirror Space for source Space → 找 mirror Flow for source Flow → 不存在则创建
- **风险**：这要求 agent runtime 有 workspace root 的写入权——隐含 capability。需要在 §3.2 改动 B profile 里明确：controller's agents MUST 有 mirror Space 内 capability。建议：profile 声明默认 capability grant
- **未在主提案中具体写出**

**F. 并发首次创建竞态**
Alice 在两个设备同时第一次 @-agent，两个设备都尝试创建 mirror Space + mirror Flow。
- 解决：双层专用唯一性 cell `mirror_space_by_source` + `mirror_flow_by_source`，**Rev 7 终版**：cell schema 声明 `initial_value="__unset__"`，reservation Move predicate = `head_eq: "__unset__"`（empty sentinel pattern）；recovery Move 用 [§8 冲突修复](spec/v1/zh/authz/event-auth-state-resolution.md) 标准（`head_in [conflict_heads]` + state_witness + inclusion_proof + `cx.capability.agent_workspace.recover` capability），见 §3.2。Rev 4 `from=unset` / Rev 5 `head_eq=⊥` / Rev 6 `head_eq: null` 都是编造或不足语义，Rev 7 通过 empty sentinel 真正对齐 spec
- 但是 winner 的 mirror Flow ID 在不同设备上不同——loser 设备会本地有一个失效 mirror Flow draft，需要 client 重定向
- **风险**：UX 上可能造成"我刚刚发的消息去哪了"困惑。建议：client SHOULD 在创建前先 query workspace index；server 提供 `mirror_flow_for(source_flow_id)` 查询 op
- **未在主提案中明确**

**G. Workspace root 的 default View / inbox 结构**
Controller 可能有 N 个 mirror Space, 每个有 M 个 mirror Flow——怎么导航？
- 应该有标准化 View profile：按 source Space group、按最近 activity sort、按 unread count filter
- **未在主提案中规定**——建议作为 §3.2 改动 B 的子项添加，或作为后续 follow-up proposal

**H. Mention redirect stub 的可读性 vs 隐私 trade-off**
mention_redirect 顶层 `body` 字段（Rev 4 起命名；Rev 2 曾命名为 `human_readable_summary`）是 sender client 生成。Sender 可能写"Alice asked her agent privately"（最小化），也可能写"Alice asked agent to draft legal review for this thread"（高暴露）。
- **风险**：用户不知道这个 summary 对其他 source Flow 成员可见，可能不慎泄露指令意图
- **建议**：spec MUST 把 mention_redirect 顶层 `body` 限定为发送方明确指定（不自动从指令内容派生）；client UI MUST 显示 "this summary is visible to all source Flow members"

**I. Retention 解耦带来的 GDPR / 数据驻留**
Source Space 被组织要求 retention=90 days；mirror Space 在 controller 私人服务器上 retention=forever。mirror 中的 import_attestation 在源消息已合规删除后仍保留——可能违反"被遗忘权"。
- **风险**：合规风险，提案需要明确建议
- **建议**：profile 提供 `inherit_retention_from_source: boolean` 选项；某些合规 deployment MUST 把 import_attestation 视为派生数据并 cascade retention

**J. Agent 团队"重加密引入"的信任放大问题**
Primary agent 把源消息重加密引入 mirror。如果 primary agent 自身被 prompt injection 或被攻陷，引入的 import_attestation 可能内容被篡改但 import_signature 仍是 primary agent 自己签的（合法）。
- **风险**：security 层面的"agent 内容污染"
- **缓解**：reader UI MUST 显著区分"原作者直接发言"vs"由 X agent 重加密引入"——这一条已在 §3.4 写了，但需要在 security threat model 文档里 cross-reference

**K. v0 → v1 迁移**
现有 Flow 已有 agent member，没有 workspace。引入 profile 后，存量 agent 是否回填 workspace？
- **建议**：MUST NOT 自动回填；workspace 是 opt-in；现有 agent 在 source Flow 行为不变（普通 member）
- **未在主提案中明确**

**L. Mirror Flow 的反向写回（agent 代表 controller 在 source Flow 发言）**
讨论完，agent 在 mirror Flow 产出回复，controller 批准后发到 source Flow。怎么发？
- 选项 1：controller 自己发——简单，audit 显示 controller authored
- 选项 2：agent 发——audit 显示 agent authored
- **目前提案没指定**——但这是核心 UX。建议：v1 默认选项 1（controller 自己按按钮 publish），选项 2 留到 v2 配合 `on_behalf_of` 字段做
- 需要在 §4.1 lifecycle 流程末尾加一段"反向写回"

**M. Conformance vector 数目**
列了 8 个，但 §8 自审里又冒出至少 5 个边界场景（D / F / I / J / K）需要测试。最终可能 12-15 个 vector。

### 8.2 协议层面更深的潜在问题

**N. `mention_redirect` 与 `cx.content.mention` 的 reducer 协同**
普通 `mention` Relation 会被 reducer 写入 `cx.relation.mentions(from=message, to=actor)`。`mention_redirect` 是否也产生 mentions Relation？如果产生，audit 上"X 被 mention 了"的事实是公开的（已经接受）；Rev 4 起 mention_redirect 已不含 `redirect_to_*` 字段，所以 mentions Relation 自然不会泄露 mirror 端定位信息（pair_id / commitment hash 都是 opaque）。
- 建议：`mention_redirect` 仍产生 `cx.relation.mentions`，但 Relation 本身不含 redirect 数据；redirect 数据只在 content block 中

**O. MLS group 在 mirror Space 加新 agent 时的 backward security**
Mirror Space MLS group 加新 consulting agent → 标准 MLS welcome → 新 agent 拿到当前 group state，能读 join 之前的历史（如果 history_visibility=joined）
- 这正常，no spec change，但要在 agent_workspace_profile 里明确 default `history_visibility=joined`（已写在 §3.2）
- **额外考虑**：consulting agent 加入后能看到 primary agent 之前的 import_attestation 内容——这是预期还是问题？预期，因为 controller 显式拉进来的。

**P. agent_workspace_root 本身的 E2EE 与 multi-device 同步**
Controller 多设备访问 workspace root。Root 本身的 MLS group 成员是 controller 的多设备 + 所有 agents（？）。这跟普通 Space 的多设备 sync 一样，复用现有机制，但 spec 应该明确：workspace root 的 default membership 模式
- **未在主提案中写明**——建议在 §3.2 profile 中声明：root Space membership = `[controller's all devices] ∪ [controller's all agents marked workspace_visible]`

**Q. agent 的 `cx.schema.agent_authority.v1` 中 controller 字段是否已存在？**
依赖项 B 的核心。需要确认 [identity/key-management.md](spec/v1/zh/identity/key-management.md) 现状。如果现状没有 `controller` 字段或语义模糊，本提案要预先解决——但这超出本 proposal scope。
- **行动**：写完 draft 后必须 grep 验证

### 8.3 提案完成度评估

| 维度 | 状态 |
|---|---|
| 主架构清晰度 | ✅ |
| 5 项改动具体到文件 / schema | ✅ |
| 生命周期场景 normative 描述 | ✅ |
| Conformance vectors 列举 | 🟡 部分（8 个，可能需 12-15） |
| 反向写回（agent → source Flow） | ✅ 已补（§4.7） |
| 跨 deployment 互操作 | 🟡 未完整（resolve_mirror_flow 已说明端侧无需源 deployment 参与，但跨 deployment import_attestation 合规未深入） |
| 与现有 spec 依赖项确认 | ✅ `agent_authority.v1` schema 已 grep 验证存在 |
| Security threat model 整合 | 🔴 未做 |
| 迁移路径 | ✅ 已补（§9） |
| Workspace navigation View / inbox | 🔴 未做 |
| 合规 / retention 详细策略 | 🔴 未做 |
| 并发首次创建竞态 | ✅ 已补（§3.2 + `resolve_mirror_flow` op） |
| Other-party agent mention 处理 | ✅ 已补（§3.3 normative） |
| `human_readable_summary` 泄露 | ✅ 已补（§3.3 normative） |

### 8.4 建议下一步

1. ✅ **已完成**：grep 验证 §8.2 (B/Q) — `cx.schema.agent_authority.v1` schema 已存在于 [`spec/v1/artifacts/schemas/agent-authority.schema.json`](spec/v1/artifacts/schemas/agent-authority.schema.json)，含 `controller` / `responsible_actor` / `knowledge_sources[]` / `join_policy` 完整字段；本提案应**全部基于此 schema 组合**，不引入新身份字段。
2. ✅ **已补**：D（other-party agent mention 必拒绝，§3.3）、F（并发首次创建 + resolve op，§3.2）、H（summary 可见性披露 normative，§3.3）、L（反向写回流程，§4.7）、K（迁移与回退，§9）
3. **followup proposal**：G / I（workspace navigation、retention 合规、security threat model）—— scope 足够大，独立 spike 更合适
4. **暂留 open question**：J（agent 信任放大）—— 等 security review 给方向
5. ✅ **已 Rev 3 修订**：`cx.flow.member.add` 不存在；改用 `cx.member.state` + `cx.capability.grant` 标准 path；agent_member_profile 在客户端层展开为多条 grant event（见 §3.1）

### 8.5 草稿后 grep 复审带来的范围缩水

| 原提案"新增" | 复审发现 | 修订结果 |
|---|---|---|
| Agent member capability preset | 可通过 `agent_authority.effective_grant_refs[]` 表达 | 由 normative pattern 而非新 preset；**preset names 仍有 UX 价值，但 reducer 不依赖 preset name** |
| Cross-Space scoped 读 | `knowledge_sources[]` 已支持 4 档 visibility | 完全复用，**消除提案中的"scoped read 委托"困扰** |
| Agent join 限定 | `join_policy.allowed_space_ids` 已存在 | 复用 |
| Mention 触发 | `presence_policy.allowed_triggers` 含 `mention` | 复用 |
| Controller↔agent 绑定 | `agent_authority.controller` 字段已存在 | 复用 |

**结论**：本提案 v1 实质性新增协议表面只剩 3 件：
1. `cx.content.mention_redirect` content block（§3.3，必需）
2. `cx.content.import_attestation` content block（§3.4，必需）
3. `cx.profile.agent_workspace.v1` Space profile（§3.2，组合现有原语，主要是 normative 约束 + DID Document service entry advertisement）

其他改动（§3.1 agent member preset、§3.5 membership change notification）是组合现有原语的 normative 引导，不引入新 wire-level shape。

**这是好消息**：提案的协议 risk 比起最初评估要低很多。v1 ship-able 路径清晰。

---

## 9. 迁移与回退

### 9.1 现存部署（pre-proposal）行为

本提案落地时，可能已经存在：

- 部分 Space 已经把 agent 作为成员加入了 Flow，但没有 agent_workspace 配套
- 部分客户端已经实现私有 @ routing 但用了非标准 content kind / 字段命名
- 部分 agent runtime 已经实现 `cx.schema.agent_authority.v1` 但 `knowledge_sources` 用法不一致

### 9.2 兼容规则（normative）

**对存量 agent member**：

- 提案落地**不**强制存量 agent 回填 workspace；workspace 是 opt-in 行为
- Source Flow 中已存在的 agent member 继续按现有 capability grant 工作
- Controller 在 client 首次启用 agent_workspace 集成时，client SHOULD 列出当前所有"以 controller 为 `agent_authority.controller`"的 agent，让用户决定是否为每个 source Flow lazy 创建 mirror Flow

**对未实现本提案的客户端**：

- 收到 `cx.content.mention_redirect`：**没有 fallback 路径**——sender MUST 用 Event 顶层 `requirements.critical_extensions[]` `fail_closed=true` 声明本扩展（§3.3），未实现该扩展的客户端 / reducer MUST reject 整条 event。这保护隐私 invariant（避免旧客户端把 stub 错误展开）。
- 收到 `cx.content.import_attestation`：sender MAY 选择是否在 Event 顶层加 `requirements.critical_extensions[]`：
  - 加了（fail_closed）→ 未实现客户端 MUST reject
  - 未加 → 未实现客户端 MAY 把它当未知 content block，显示顶层 `body` 字段 + 通用提示"（来自另一 Space，由 X 引入）"——这是因为 import_attestation 的隐私敏感性低于 mention_redirect（内容已经在 mirror Space 内授权可见）
- 客户端实现 SHOULD 在 service describe 时声明对 `cx.feature.mention_redirect.v1` / `cx.feature.import_attestation.v1` 的支持，便于 sender 预检

**对未实现 `agent_workspace` profile 的服务端（Rev 5 修订：层级分清）**：

- `cx.profile.agent_workspace.v1` 是 mirror Space 的 **安全 profile**——normative 含义包括双层 reservation cell + recovery saga + agent_task FSM 三正交 cell + ID 不暴露 invariant
- 未声明支持该 profile 的服务端 **对 mirror Space 写入** MUST fail-closed：拒绝接受针对该 Space 的 `cx.agent_task.*` event / mirror 端的 `cx.content.import_attestation` 写入；返回 `profile_unsupported`
- **但是**：源 Space 中的 `mention_redirect` 接受**不**依赖 mirror profile——它依赖 `cx.feature.mention_redirect.v1` critical_extension 是否被源 Space 服务端支持（§6.1 表）。两者是独立检查
- 客户端 SHOULD 在发送 mention_redirect 前通过 `service.describe` 检查源 Space 服务端是否支持 `cx.feature.mention_redirect.v1`；在写 mirror Space 前检查目标服务端是否支持 `cx.profile.agent_workspace.v1`
- 不支持 mirror profile 时，UI 提示用户"此 server 不支持私有 agent workspace（mirror 端不可用）"，但仍可发送 source-side mention_redirect（如果源 server 支持 critical_extension）

### 9.3 回退路径（rollback）

如果提案后续在 v1.x 修订时发现严重问题，回退策略：

- `mention_redirect` 与 `import_attestation` block 一旦 ship 进 schema-registry，不应删除（向后兼容）；但 MAY 在新 minor 版本中标记 deprecated 并引导客户端用替代 block
- `agent_workspace` profile 可标记 deprecated；现有 workspace Space 保留为普通 Space（成员、E2EE、retention 保持）
- 已存在的 mirror Flow 与 source Flow 的 `derived_from` Relation 永远保留（这是事实，不应回退）

### 9.4 与 conformance profile 的关系

- `client_basic` profile：MUST 实现 §6.1 列出的 fallback 渲染；MAY 不实现 agent_workspace
- `agent_runtime` profile：SHOULD 完整实现本提案
- `enterprise_client`：SHOULD 完整实现；针对 §9.2 的"列出现存 agent member 让用户回填"是 SHOULD（默认开启提示，避免存量混乱）

### 9.5 数据迁移工具（建议）

非 normative，但建议提供 reference implementation：

- `contrix-cli agent-workspace bootstrap` ——为当前 principal 创建 workspace root + 写入 DID Document service entry
- `contrix-cli agent-workspace backfill --source-flow=<id>` ——为指定源 Flow 创建 mirror Space + mirror Flow（不自动回填历史消息，只建结构）
- `contrix-cli agent-workspace audit` ——列出所有以 controller 为 `agent_authority.controller` 的 agent 与它们所在的 source Flow，标注哪些有 / 没有 mirror Flow

---

## 10. Rev 2 Review Acknowledgement & Trace

### 10.1 审议项验证结果

2026-05-16 spec review 提出 8 项 critical + 7 项 follow-up，全部经 grep 验证成立：

| # | 审议项 | 验证 spec 路径 | Rev 2 修订位置 |
|---|---|---|---|
| 1 | `cx.flow.member.add` 不存在 | [current-model.md:53](spec/v1/zh/overview/current-model.md)、[flow.schema.json](spec/v1/artifacts/schemas/flow.schema.json) 无 members 字段；grep 全仓无 `cx.flow.member` event | §2 架构图、§3.1（路径 A/B）、§4.1 |
| 2 | 基数方向写反 | [relation.md:68](spec/v1/zh/models/relation.md) `many_to_one` semantic | §3.2 relation_profiles 加 `max_from_per_to=1` |
| 3 | 跨 Space 非原子 | Move/Anchor 单 Space 语义 | §4.1 改 saga |
| 4 | ID 泄露 | mention_redirect 字段公开 mirror IDs | §3.2 DID Document HTTPS only；§3.3 删 redirect_to_* / 加 redirect_pair_id |
| 5 | content block 缺 body | [content-types.md:45](spec/v1/zh/models/content-types.md) MUST | §3.3 / §3.4 加顶层 body |
| 6 | controller 非 required | [agent-authority.schema.json:6](spec/v1/artifacts/schemas/agent-authority.schema.json) required 不含 controller | §3.1 仅在 `acting_mode=delegated_assistant` 时按本提案视为 required；§3.3 携 authority_snapshot |
| 7 | fallback 与强校验矛盾 | 旧 reducer 把未知 content 当普通接受 | §3.3 critical_extensions 字段；§9.2 unsupported fail-closed |
| 8 | cursor ≠ frontier | DAG / Anchor 模型 | §3.4 改 source_anchor_ref + source_frontier_hash |

### 10.2 Follow-up 修订追踪

| Follow-up | Rev 2 落点 |
|---|---|
| `agent_member_profile` 不用虚构 event；用 `cx.capability.grant` + invite refs | §3.1 |
| `mention_respond_only` 需注册 constraint kind | §3.1（新增 constraint_schema 落点） |
| `resolve_mirror_flow` 落 service-http-binding / openapi / operation-registry | §3.2 op 章节 |
| `quote_external` → `import_attestation` 性质澄清 | §3.4 |
| Unsupported profile fail-closed | §9.2 |
| Source stub redaction → mirror `transparency_lost` | §4.8（新增 lifecycle 场景） |
| Source Space export / re-encryption 合规 | §10.3（下面） |

### 10.3 合规：Source E2EE 数据外发的本质（Rev 3 修订）

> 审议指出：把 source E2EE 明文复制到 private workspace **本质是数据外发**，不只是普通引用。
>
> **Rev 3 关键修订**：mirror Space reducer **无法**enforce 源 Space policy（跨 Space reducer 不可能做这种判断——源 policy 在另一个治理域）。真正的 export gate 在 **source-side agent runtime / 合规层**，mirror reducer 只能验证事件携带的 attestation 完整性。

**实际分工（Rev 3 normative）**：

| 层 | 职责 | 失败行为 |
|---|---|---|
| **Source Space policy** | 声明 `import_to_external_space=deny` constraint；将该 policy hash 包含在源 Space schema/policy event 中 | policy 本身的 cas-register / lattice 由源 Space 自主 |
| **Source-side agent runtime（actual enforcement gate）** | 在 importer 准备 import_attestation 前 fetch 源 Space 当前 policy；若 deny 则 **MUST 拒绝 import**——不写出该事件 | 若 agent runtime 不合规、绕过 policy 直接写 mirror，是 agent 失信行为，audit 上可追责（agent 签名留痕） |
| **Source-side policy authority（可选 attestation）** | 在 importer 请求 export 许可时颁发 `source_export_policy_attestation`，签名包含 `(source_space_id, policy_hash, importer_actor_id, valid_until)` | attestation 不可达时，importer SHOULD 拒绝 import（fail-closed by importer） |
| **Mirror Space reducer** | 验证 `import_attestation` event 携带的 `source_export_policy_attestation` 签名完整性；签名缺失 / 无效 → 仍接受 event 但标记 `unverified_export`（**不**拒绝） | mirror 不能"判定"源 policy；只能记录 attestation 状态供 audit |
| **合规审计 / DLP 层** | 周期性扫描 mirror Space，列出 `unverified_export` 或可疑导入；触发人工 / 自动告警 | 与 mirror reducer 解耦 |

**Normative 要求（Rev 4 修订：消除 MUST 与 optional 的矛盾 + 补 canonical schema）**：

1. 源 Space policy schema MUST 支持声明 `import_to_external_space` capability constraint（合法值：`allow` | `deny` | `require_attestation`；默认 `allow`）。该 constraint 仅在源 Space 治理域内生效——它指导 source-side agent runtime 是否产出 import 事件，**不**穿透到 mirror Space reducer。
2. `cx.content.import_attestation` event 的 `source_export_policy_attestation` 字段**可选**（不是 MUST）；**如果**携带，**MUST**满足以下 canonical schema：

```json
{
  "source_export_policy_attestation": {
    "type": "object",
    "required": [
      "authority_did",
      "source_space_id",
      "policy_hash",
      "policy_decision",
      "importer_actor_id",
      "import_destination_space_id",
      "content_hash",
      "source_frontier_ref",
      "issued_at",
      "valid_until",
      "signature"
    ],
    "properties": {
      "authority_did": {
        "type": "string",
        "description": "签发该 attestation 的 policy authority（通常是源 Space 的 admin actor 或 designated policy server）"
      },
      "source_space_id": { "type": "string", "pattern": "^cx:space:..." },
      "policy_hash": {
        "type": "string",
        "pattern": "^sha256:[0-9a-f]{64}$",
        "description": "issuance 时刻源 Space `import_to_external_space` policy 的 canonical hash"
      },
      "policy_decision": {
        "type": "string",
        "enum": ["allow", "require_attestation_granted"]
      },
      "importer_actor_id": { "type": "string" },
      "import_destination_space_id": {
        "type": "string",
        "pattern": "^cx:space:...",
        "description": "签名绑定到目标 mirror Space ID——防止 attestation 被劫持复用到其他 Space"
      },
      "content_hash": {
        "type": "string",
        "pattern": "^sha256:[0-9a-f]{64}$",
        "description": "被导入内容的 canonical content hash。算法（Rev 5 normative）：1) 取被导入的 cx.content.import_attestation.content 对象（即 importer 重加密后即将写入 mirror 的内容 block）；2) 按 spec/v1/zh/conformance/encoding.md 定义的 RFC 8785 / JCS canonical JSON profile 序列化；3) SHA-256 over canonical bytes；4) 前缀 'sha256:'。校验端用相同算法对收到的 content 重算并比对。"
      },
      "source_frontier_ref": {
        "type": "string",
        "pattern": "^cx:anchor:...",
        "description": "issuance 时刻源 Space 的 anchor frontier"
      },
      "issued_at": { "type": "string", "format": "date-time" },
      "valid_until": { "type": "string", "format": "date-time" },
      "signature": {
        "type": "string",
        "description": "authority_did 对 canonical signing input 的签名。Canonical signing input（Rev 6 修订：消除循环签名）= JCS-canonicalized JSON 对象 `{schema_id: \"cx.schema.content.source_export_policy_attestation.v1\", domain: \"cx.domain.export_policy_attestation.v1\", body: <除 signature 外的所有 required 字段，按 JCS 序列化>}`。SHA-256 over canonical bytes → 输入签名算法。验证端用同一算法重算 canonical input + 公钥验签。`schema_id` + `domain` 是 domain separator，防止 signature 被 replay 到其他 attestation 类型。"
      }
    },
    "additionalProperties": false
  }
}
```

3. **importer（source-side agent runtime）SHOULD 在 import 前主动检查源 Space 当前 policy**；合规部署 MAY 在 agent runtime conformance profile 中把 SHOULD 抬到 MUST，但**这是 agent runtime 行为合规要求，不是 mirror reducer 强制项**——这是真正的 export gate
4. mirror reducer 见 `import_attestation`：
   - 缺 `source_export_policy_attestation` → 接受 event，audit 标记 `export_attestation_missing`
   - 携带但签名无效 / 字段不一致（destination ≠ 当前 mirror Space / content hash 不匹配）→ 接受 event，audit 标记 `export_attestation_invalid`
   - 签名有效 → 接受 event，audit 标记 `export_attestation_verified`
   - **任何情况都不拒绝**——mirror 无能力判断源 policy，只能记录 attestation 状态供合规层 audit
5. `inherit_retention_from_source` profile flag 表达"mirror Space retention ≤ source 当前 retention"，由 mirror Space 自身 retention reducer 实施（在 mirror Space 内合法）；不需要跨 Space enforcement
6. 合规扫描工具（独立服务，建议名 `cx.compliance.export_audit`）周期性扫描 mirror Space 的 import_attestation events，按 `export_attestation_{missing,invalid,verified}` 分组报告——这是真正的 DLP / compliance 层入口

**未落地的合规问题（follow-up）**：
- 跨司法辖区的 import（数据驻留）：需要专门 spike
- "被遗忘权"级联：source 用户删号后，mirror 中相关 import_attestation 的处理策略
- agent runtime conformance suite 怎么测试"在 import 前 fetch 源 policy"——这是 black-box 行为，标准 conformance 难以验证；建议提供 reference agent runtime + 红队 test harness

### 10.4 v1 最小范围（Rev 3 最终）

经过 Rev 3 收敛，v1 实质性新增协议表面：

**新对象 + 事件家族（Rev 3 关键）**：
1. `cx.schema.agent_task.v1` 对象 + typed ID `cx:agent_task:` + 9 个 state 枚举
2. 事件家族 `cx.agent_task.create` / `cx.agent_task.state` / `cx.agent_task.cancel`
3. 状态机：§3.6 中定义的合法转换边 + **FSM lattice `transition` op** on `agent_task.state` cell（Rev 4 修正）

**新 content blocks**：
4. `cx.content.mention_redirect` content block（含 `authority_grant_ref`、`redirect_pair_id`、`redirect_event_commitment`；`critical_extensions` 在 Event 顶层 `requirements` 而非 block 内）
5. `cx.content.import_attestation` content block（"importer 声称"性质 + 可选 origin proofs）

**新 Space profile**：
6. `cx.profile.agent_workspace.v1`（含 cardinality 双向收紧、唯一性 cell、unsupported fail-closed 规则、HTTPS service entry）

**新 cas-register cell namespace**：
7. ~~`agent_workspace.mirror_flow_by_source:<source_flow_id>` (cas-register with from=unset)~~ → **Rev 5 取代**：双层 reservation cell `mirror_space_by_source` + `mirror_flow_by_source`，`cas-register + bottom=reject` + recovery Move 协议（§3.2）

**Normative 引导（组合现有原语）**：
8. §3.1 agent_member_profile 通过 `cx.capability.grant` + `cx.member.state` 展开（注册新 constraint kind `mention_respond_only`）
9. §3.2 `agent_workspace.resolve_mirror_flow` + `agent_workspace.list_pending_tasks` op（落 6 个规范文件）
10. §3.3 三种 `attached_authority` 证据形式（anchored event ref / state witness / inline copy）
11. §3.5 `agent_membership_change` notification type
12. §4.8 observe-then-write 模式（多 watcher + idempotent state writes + sync node TTL housekeeping）
13. §10.3 合规分工（source-side agent runtime 是真正的 export gate；mirror reducer 仅验证 attestation 完整性）

### 10.5 Rev 2 → Rev 3 修订追踪

第二轮审议 6 项 critical 全部成立，已逐项落地：

| # | 审议项 | Rev 3 修订位置 |
|---|---|---|
| 1 | `cx.message.update` + 新 Message state 不成立 | §3.6 新对象 `cx.schema.agent_task.v1` + 事件家族；§4.1 / §4.8 完全重写为 agent_task 事件 |
| 2 | `critical_extensions` 放错层级 | §3.3 移到 Event 顶层 `requirements.critical_extensions[]`（按 [event-and-patch.md:43](spec/v1/zh/models/event-and-patch.md) 既有模型） |
| 3 | 唯一性并发规则模糊 | §3.2 引入专用 cell（**Rev 5 终版**：双层 `mirror_space_by_source` + `mirror_flow_by_source`，`cas-register + bottom=reject` + recovery Move with `head_eq=⊥` lex-min winner）；conformance vector 12 / 13 / 14 描述 |
| 4 | Rev 1 残留文本 | 全局清理：`cx.flow.member.*` → `cx.member.state` + `cx.capability.grant`；`cx.message.update` → `cx.agent_task.state`；`quote_external` → `import_attestation`；`trigger_message_ref` → `trigger_redirect_pair_id`；文件树更新 |
| 5 | 跨 Space 副作用应改观察后写入 | §4.8 完全重写为 watcher pattern：reducer 不消费跨 Space 事件；多 watcher + TTL housekeeping；`evidence_refs` 提供独立可验证 audit trail |
| 6 | Authority / export policy 不能 cache enforce | §3.3 改用 source Space 已有的 `cx:grant:...`（三种证据形式：anchored event ref / state witness / inline copy）；§10.3 重写：source-side agent runtime 是真正的 export gate，mirror reducer 只验证 attestation 完整性（缺失/无效 → `unverified_export` 标记，不拒绝） |

### 10.6 Rev 2 → Rev 3 删除项

| 删除字段 / 概念 | 替代 |
|---|---|
| `mention_redirect.authority_snapshot` | `mention_redirect.authority_grant_ref` 引用源 Space 已有 grant |
| `mention_redirect.critical_extensions` (block 内) | Event 顶层 `requirements.critical_extensions[]` |
| Message state 新增枚举（`pending_source_stub` 等 6 个） | 全部移到 `agent_task.state`；Message schema 不变 |
| `cx.message.update`（虚构事件） | `cx.agent_task.state` |
| relation_profile `many_to_one` 残留 | `one_to_one` + 双向 max + 专用唯一性 cell |
| §4.8 中的"mirror reducer auto-converts" | watcher observe-then-write 模式 |
| "reducer 拒绝 import_attestation 当源 policy=deny" | mirror reducer 只标 `unverified_export`；真正的 enforce 在 source-side agent runtime |

### 10.7 Rev 3 完成度评估

| 维度 | 状态 |
|---|---|
| 主架构清晰度 | ✅ |
| 不依赖虚构 event kind | ✅（agent_task 是正式提议的新对象，不再借用 Message） |
| 不假设跨 Space reducer 副作用 | ✅（observe-then-write） |
| critical_extensions 落点正确 | ✅（Event requirements 顶层） |
| 唯一性并发规则明确 | ✅（双层 reservation cell + `cas-register + bottom=reject` + recovery Move；Rev 5 终版） |
| Rev 1 / Rev 2 残留清理 | ✅（grep 验证无残留） |
| 跨 deployment 互操作 | 🟡 partial（watcher 模式天然 cross-deployment-friendly；但 §10.3 跨司法辖区合规仍是 follow-up） |
| 反向写回（agent → source Flow） | ✅（§4.7） |
| 迁移路径 | ✅（§9） |
| Security threat model 整合 | 🔴 未做（follow-up） |
| Workspace navigation View / inbox | 🔴 未做（follow-up） |

**Rev 3 状态**：架构层面闭环；6 项第二轮 critical 已全部 verified 修复。**理论上**可以拿给同一 reviewer 跑第三轮，或者拿给独立 reviewer。建议第三轮 review 重点检查：

- agent_task 状态机的边界用例（reducer 实现层面是否需要补充非法转换 fixture）
- `authority_grant_ref` 在源 Space grant 被 revoke 之后的处理（mention_redirect 已发出但 grant 失效——是否需要 mirror 端额外 reconciliation）
- observe-then-write 中"撒谎 watcher"的对抗性场景细化
- conformance vector 是否覆盖 16 个场景全部分支

**Open follow-ups（明确推迟）**：
- `read_bounded_by_anchor` capability constraint（agent 读源 Flow 的 frontier 上界 normative enforcement）
- `on_behalf_of` Message 字段（v2，agent 直接代表 controller 在 source Flow 发言）
- Workspace navigation / inbox View 标准化
- 跨司法辖区合规 + 被遗忘权级联
- Security threat model 整合（含 agent 信任放大）

### 10.5 与原 Rev 1 的删除项

为避免持续维护两版冲突，原 Rev 1 §3.3 / §3.4 schema 已被新版覆盖；本节列出**被删除**的具体字段，供已基于 Rev 1 草稿开始实现的实现者参考：

| 删除字段 | 替代方案 |
|---|---|
| `mention_redirect.redirect_to_space_id` | 删除；用 `redirect_pair_id` |
| `mention_redirect.redirect_to_flow_id` | 删除；用 `redirect_pair_id` |
| `mention_redirect.redirect_event_id` | 删除；用 `redirect_event_commitment`（hash） |
| `mention_redirect.visibility_note` | 删除（无效字段） |
| `mention_redirect.human_readable_summary` | 改名为顶层 `body`（Content Block 必填） |
| `context_anchor.source_cursor_event_id` | 改名为 `source_anchor_ref` + `source_frontier_hash` |
| `context_anchor.trigger_message_ref` | 改名为 `trigger_redirect_pair_id` |
| `quote_external.re_encrypted_by` | 改名为 `importer.actor_id` |
| `quote_external.re_encryption_attestation` | 改名为 `import_signature` |
| `cx.content.quote_external`（kind） | 改名为 `cx.content.import_attestation` |
| DID Document `serviceEndpoint = cx:space:...` | 改为 HTTPS URL |

---

## 11. Rev 3 → Rev 4 修订追踪

第三轮审议 7 项全部成立，已逐项落地：

| # | 审议项 | Rev 4 修订位置 |
|---|---|---|
| 1 (P0) | `critical_extensions.scope` 用 `payload.content` 不在合法枚举内 | §3.3 改为 `scope: "payload"` + `schema_ref: cx.schema.content.mention_redirect.v1`；与 [event-schema.json:977-988](spec/v1/artifacts/schemas/event-schema.json) 对齐 |
| 2 (P0) | mirror Space 首次创建竞态未覆盖 | §3.2 新增 workspace root 级 cell `mirror_space_by_source:<source_space_id>` + 保留 mirror Space 内的 `mirror_flow_by_source:<source_flow_id>`，双层 cas-register |
| 3 (P0) | fail-bottom 与 winner 矛盾 | §3.2 重写：cas-register precondition `from=unset`；first-anchored Move 是 winner，loser `failed_precondition`；删除"双方都 fail / ⊥ collapse"错误表述；§6.2 conformance vector 同步重写 |
| 4 (P1) | agent_task.state 应该是 FSM lattice | §3.6 改为 `transition` op + FSM（见 [event-schema.json:1098,1105](spec/v1/artifacts/schemas/event-schema.json)）；event payload 含 `op=transition` + `from` + `to`；多 watcher 写同一 transition 自然 idempotent（from-state precondition） |
| 5 (P1) | Rev 3 残留 `redirect_to_*` / `human_readable_summary` | §3.3 规则段重写为新字段命名（`redirect_pair_id` / `redirect_event_commitment` / 顶层 `body`）；§9.2 fallback 段重写为 critical_extensions fail_closed 路径 |
| 6 (P1) | attestation canonical schema 缺失 + "MUST 包含可选字段"矛盾 | §3.3 新增 `attached_authority` 作为 capability-grant.schema.json 可选字段的完整 oneOf schema（3 种 evidence_kind）；§10.3 改为"如携带 MUST 满足结构"+ 列完整 schema（含 destination / content hash / frontier ref 签名绑定）；mirror reducer 仅 audit 标记，不拒绝 |
| 7 (P1) | grant revoke / agent removal 未进 task lifecycle | §3.6 FSM 增加 `source_authority_revoked` / `reconfirmed_after_source_revoked` / `cancelled_after_source_revoked` 三个 state + 8 条新 transition 边；§4.3 重写为 observe-then-write 触发模式，与 transparency_lost 平行处理 |

### 11.1 Rev 3 → Rev 4 删除项

| 删除字段 / 概念 | 替代 |
|---|---|
| `critical_extensions.scope = "payload.content"` | `scope = "payload"` + `schema_ref` 定位到 content block schema |
| Rev 3 §3.2 "fail-bottom 双方都 fail" 语义 | cas-register `from=unset` 标准 precondition + first-anchored winner |
| `cas-register on agent_task.state` | `transition` op + FSM lattice |
| `human_readable_summary` 字段名残留 | 统一为 Content Block 顶层 `body` |
| `redirect_to_*` 字段残留 | `redirect_pair_id` + `redirect_event_commitment` |
| "import_attestation MUST 包含可选字段" 自相矛盾 | "可选；如携带 MUST 满足 canonical schema" |
| mirror reducer 拒绝缺失 attestation | mirror 仅 audit 标记 `export_attestation_{missing, invalid, verified}` |
| §4.3 仅"display locked"对 revoke 的处理 | watcher 触发 `cx.agent_task.state(to=source_authority_revoked)` FSM 转换 |

### 11.2 Rev 4 完成度评估

| 维度 | 状态 |
|---|---|
| schema 合法性（critical_extensions.scope / agent_task.state lattice） | ✅ |
| 两层并发 race（mirror_space + mirror_flow） | ✅ |
| cas-register vs ⊥ 语义清晰 | ✅ |
| FSM transition 表完整 + 二次失效边覆盖 | ✅ |
| canonical attestation schema 落地 | ✅（attached_authority + source_export_policy_attestation 都有完整 oneOf / properties 表达） |
| Grant revoke watcher lifecycle | ✅（§4.3 + FSM state） |
| Rev 1/2/3 残留清理 | ✅（grep 验证无 normative 残留；仅 §10/§11 trace 表保留作为历史） |
| `mention_redirect` redact 后 task 处理 | ✅（§4.8 transparency_lost） |
| 反向写回 | ✅（§4.7） |
| 跨 deployment 互操作 | 🟡 partial（watcher 模式天然 cross-deployment-friendly；跨司法辖区合规仍为 follow-up） |
| Security threat model | 🔴 follow-up |
| Workspace navigation View / inbox | 🔴 follow-up |

**Rev 4 实质新增协议表面（最终）**：

1. 新对象 `cx.schema.agent_task.v1` + typed ID `cx:agent_task:` + 12-state FSM
2. 事件家族 `cx.agent_task.create / state / cancel`，state 用 `transition` lattice op
3. 2 个 content block：`cx.content.mention_redirect`、`cx.content.import_attestation`
4. 1 个 Space profile：`cx.profile.agent_workspace.v1`
5. 2 个 cas-register cell namespace：`mirror_space_by_source`（workspace root 内）、`mirror_flow_by_source`（mirror Space 内）
6. `capability-grant.schema.json` 新可选字段 `attached_authority`（3 种 evidence_kind）
7. `cx.content.import_attestation` 新可选字段 `source_export_policy_attestation`（含 destination / content hash 签名绑定）
8. 2 个 service ops：`resolve_mirror_flow` + `list_pending_tasks`
9. 2 个 feature ids：`cx.feature.mention_redirect.v1`、`cx.feature.import_attestation.v1`（用于 critical_extensions）
10. 1 个新 capability constraint kind：`mention_respond_only`
11. 1 个新 capability constraint kind：`import_to_external_space`（值 `allow|deny|require_attestation`）
12. 1 个新 notification type：`agent_membership_change`

**Rev 4 状态**：架构层面闭环；7 项第三轮 critical 已 verified 修复。建议第四轮 review 重点检查：

- FSM transition 表是否覆盖所有合规组合（特别是 reconfirmed_* 后的二次失效路径）
- `attached_authority` 在 grant revoke 后的 evidence 处理（cached evidence 失效检测）
- ~~`source_export_policy_attestation` 的 `content_hash` canonicalization 算法~~ **Rev 5 已定义**：复用 [encoding.md](spec/v1/zh/conformance/encoding.md) RFC 8785/JCS profile + SHA-256；见 §10.3 schema content_hash description
- 两层 cell 跨 Space 的 reducer 信任边界（workspace root 级 cell 是否需要额外的 controller-only 写保护，避免其他 agent 通过它干扰）
- conformance vectors 是否覆盖所有 transition 边的合法 / 非法两侧

---

## 12. Rev 4 → Rev 5 修订追踪

第四轮审议 7 项全部成立，已逐项落地：

| # | 审议项 | Rev 5 修订位置 |
|---|---|---|
| 1 (P0) | cas-register "first-anchored wins / no bottom" 违反核心语义 | §3.2 完全重写：cas-register **真实语义是并发不同值 → ⊥**（参考 [event-auth-state-resolution.md:290](spec/v1/zh/authz/event-auth-state-resolution.md)）；改为 `cas-register + bottom=reject` + 显式 recovery Move（predicate `head_eq=⊥` + lex-min winner），与 [MLS genesis 模式](spec/v1/zh/crypto-media/encryption-and-audit.md) 一致 |
| 2 (P0) | 镜像 Space/Flow 原子创建跨 Space 不成立 | §3.2 改 reservation saga：cell 存"预分配 ID"作为 reservation token；`cx.space.create` / `cx.flow.create` 是独立后续 Move；不假设跨 Space 原子性 |
| 3 (P1) | §3.6 仍残留 cas-register / from_state 文本 | §3.6 / §4.8 / §4.3 统一改为 `op=transition` + `from` / `to` + `failed_precondition` 幂等；从 cas-register 描述彻底切走 |
| 4 (P1) | `source_authority_revoked` + `transparency_lost` 不可组合表达 | §3.6 把 agent_task 拆为 **3 个正交 FSM cell**（execution_state / transparency / source_authority）；agent runtime 执行 gate = 三者合法组合检查；§4.3 / §4.8 写正交 cell |
| 5 (P2) | profile / feature fail-closed 层级混淆 | §6.1 新增分层表（feature critical_extension on source vs profile on mirror）；§9.2 改为"源 Space mention_redirect 依赖 feature；mirror 端 agent_workspace profile 仅控 mirror 写入"；两者解耦 |
| 6 (P2) | Message schema context_anchor 残留矛盾 | §3.4 标题加澄清；§7 文档树删 `flow-and-message.md` 的 context_anchor 编辑条目，明确 context_anchor 在 agent_task 顶层 |
| 7 (P2) | content_hash canonicalization 不能留作 follow-up | §10.3 schema content_hash description 完整定义算法（RFC 8785/JCS + SHA-256，复用 [encoding.md](spec/v1/zh/conformance/encoding.md) profile）；§11.2 follow-up 列表标记已完成 |

### 12.1 Rev 4 → Rev 5 删除项

| 删除字段 / 概念 | 替代 |
|---|---|
| cas-register `from=unset` predicate | 不存在的 predicate；改用 `cas-register + bottom=reject` + recovery Move `head_eq=⊥` |
| "first-anchored Move 是 winner" | 并发不同值 → ⊥；recovery 阶段按 lex-min 选 winner |
| 单 agent_task `state` cell + 12 states | 3 个正交 cell（execution_state / transparency / source_authority）+ agent runtime gate invariant |
| `state ∈ {pending_source_stub, active, transparency_lost, source_authority_revoked, ...}` enum | 拆为 3 个独立 FSM 的 states（见 §3.6 表） |
| `cx.agent_task.state` 单事件 | 拆为 `cx.agent_task.execution.transition` / `cx.agent_task.transparency.transition` / `cx.agent_task.source_authority.transition` 三事件 |
| "同一 Move 创建 mirror Space + 写 root cell" 跨 Space 原子假设 | reservation saga：cell 存 pre-allocated ID；create event 独立 Move |
| §9.2 "mirror profile 不支持 → 拒绝 mention_redirect" | 拆为 feature check（源 Space）vs profile check（mirror Space），各自独立 enforcement |
| §7 文档树 `flow-and-message.md` Message schema 加 context_anchor | 删除——context_anchor 在 agent_task schema 顶层 |
| §10.3 content_hash canonicalization 作为 follow-up | 现在已定义：RFC 8785/JCS + SHA-256（复用 encoding.md profile） |

### 12.2 Rev 5 实质新增协议表面

1. `cx.schema.agent_task.v1` + `cx:agent_task:` typed ID + **3 个正交 FSM cell**：
   - `agent_task.<id>.execution_state`（6 states）
   - `agent_task.<id>.transparency`（3 states）
   - `agent_task.<id>.source_authority`（3 states）
2. 事件家族 `cx.agent_task.create / execution.transition / transparency.transition / source_authority.transition / cancel`（共 5 个）
3. 2 个 content block：`mention_redirect`、`import_attestation`
4. 1 个 Space profile：`cx.profile.agent_workspace.v1`
5. 2 个 reservation cell namespace：
   - `mirror_space_by_source` 在 workspace root；lattice = `cas-register + bottom=reject`
   - `mirror_flow_by_source` 在 mirror Space；同上
   - **recovery Move 协议**：predicate `head_eq=⊥` + lex-min deterministic winner
6. `capability-grant.schema.json` 扩 `attached_authority`（3 个 evidence_kind oneOf）
7. `cx.content.import_attestation` 可选 `source_export_policy_attestation`（完整 schema + content_hash canonicalization 定义）
8. 2 个 service ops：`resolve_mirror_flow` + `list_pending_tasks`
9. 2 个 feature id：`cx.feature.mention_redirect.v1`、`cx.feature.import_attestation.v1`
10. 2 个新 capability constraint kind：`mention_respond_only`、`import_to_external_space`
11. 1 个新 notification type：`agent_membership_change`
12. 1 个独立合规服务建议：`cx.compliance.export_audit`

### 12.3 Rev 5 完成度评估

| 维度 | 状态 |
|---|---|
| cas-register 语义合规（用 spec 真实 lattice） | ✅ |
| 跨 Space 原子性不假设 | ✅（reservation saga） |
| FSM 多维度可组合（transparency + source_authority 同时存在可表达） | ✅（3 正交 cell） |
| critical_extensions.scope 合法 | ✅（payload） |
| FSM 用 `op=transition` 不混 cas-register | ✅（§3.6 / §4.3 / §4.8 全部统一） |
| feature vs profile 分层 | ✅（§6.1 表 + §9.2 重写） |
| content_hash canonicalization 现在定义 | ✅ |
| Message schema 不变 | ✅（context_anchor 在 agent_task） |
| Authority / export attestation canonical schema | ✅ |
| Rev 1-4 残留清理 | ✅ |
| Security threat model | 🔴 follow-up |
| Workspace navigation View / inbox | 🔴 follow-up |
| 跨司法辖区合规 / 被遗忘权 | 🔴 follow-up |

**Rev 5 状态**：架构层面闭环；7 项第四轮审议（含 2 个 P0 阻断项）已 verified 修复。

### 12.4 建议第五轮 review 重点

- **3 正交 cell 的边界用例**：尤其是 `transparency` 与 `source_authority` 同时为 `reconfirmed_*` 时，agent runtime 是否应执行（按 gate 规则应该执行——验证 conformance vector 是否包含）
- **Recovery saga 在 multi-master 场景的可活性**：双方都看到 ⊥ 但 sync 延迟 → 是否可能两方都写不同 recovery winner（理论上 lex-min 确定但实现可能有 bug）
- **reservation 与 Space create 解耦后的孤儿 ID 处理**：reservation cell 写成功但 `cx.space.create` 失败 → cell 保留指向不存在的 Space ID。需要明确清理/重试策略
- **`agent_task.cancel` 便捷事件 reducer 行为**：是只写 execution cell，还是同时把 transparency / source_authority 重置为 ok？需要 normative 决定
- ~~**`reconfirmed_after_revoke → ok` 这种"恢复"边的安全含义**~~ **Rev 7 已删除该边**：authority_grant_ref 绑定原 grant_id，re-grant 是新 grant 与已有 task 无关；不存在合法的"恢复"路径

---

## 13. Rev 5 → Rev 6 修订追踪

第五轮审议 7 项全部成立（含 2 个 P0 阻断项），已逐项落地：

| # | 审议项 | Rev 6 修订位置 |
|---|---|---|
| 1 (P0) | reservation cell "无 predicate" 不阻止覆盖 | §3.2 改为显式 `head_eq: null` predicate；说明 validate_op 层在 cell 是 singleton 时强制 reject（reason=`reservation_cell_already_set`）；引用 [event-auth-state-resolution.md:421-422](spec/v1/zh/authz/event-auth-state-resolution.md) 语义 |
| 2 (P0) | recovery Move `head_eq=⊥` 是编造 | §3.2 完全重写为 [§8 冲突修复](spec/v1/zh/authz/event-auth-state-resolution.md) 标准形式：`head_in [conflict_heads]` + state_witness + inclusion_proof + recovery_capability；新增 `cx.capability.agent_workspace.recover` capability 由 controller principal 持有 |
| 3 (P1) | 三正交 cell 没贯穿全文 | §3.6 schema sketch 删 `state/state_changed_at`；§4.1 / §4.3 / §4.8 / §6.2 / §7 全部替换为 `cx.agent_task.execution.transition` / `cx.agent_task.transparency.transition` / `cx.agent_task.source_authority.transition` 三事件名 |
| 4 (P1) | 二次失效 watcher 盲写 `from=ok` | §4.3 / §4.8 改为 **read-then-write 模式**：watcher 先读 cell head，按当前 state（`ok` / `reconfirmed_after_loss` / `reconfirmed_after_revoke`）选合法 transition；多 watcher 并发通过 FSM `from` precondition + read-then-write 双层保证 idempotent |
| 5 (P1) | reservation orphan 留 follow-up 不行 | §3.2 新增 normative orphan 处理协议：reservation TTL（默认 600s）+ idempotent retry（create event UUIDv7 固定 ID）+ cleanup Move（capability `cx.capability.agent_workspace.cleanup`）+ resolve API 仅返回已完成 mapping |
| 6 (P2) | 文件树仍有 Message schema 残留 | §7 已删除（line 1037 改为 ~~strikethrough~~ + "Rev 5 删除"注） |
| 7 (P2) | attestation signature 循环签名 | §10.3 schema content_hash description 重写：canonical signing input = JCS-canonicalized `{schema_id, domain, body=除 signature 外的 required fields}` + SHA-256 + domain separator；防 replay 到其他 attestation 类型 |

### 13.1 Rev 5 → Rev 6 删除项

| 删除字段 / 描述 | 替代 |
|---|---|
| reservation Move "无 predicate" | 显式 `head_eq: null` + validate_op 层 singleton enforcement |
| recovery Move predicate `head_eq=⊥` | [§8 冲突修复](spec/v1/zh/authz/event-auth-state-resolution.md) 标准：`head_in [conflict_heads]` + state_witness + inclusion_proof + recovery_capability refs |
| §3.6 agent_task object 顶层 `state` / `state_changed_at` 字段 | 删除——状态在 3 个 FSM cell 上 query |
| `cx.agent_task.state` 单一事件名 | 拆为 3 个：`cx.agent_task.execution.transition` / `cx.agent_task.transparency.transition` / `cx.agent_task.source_authority.transition` |
| `from_state` / `to_state` 字段名 | `from` / `to` (统一为 FSM transition op 标准字段名) |
| Watcher 盲目 `from=ok` 假设 | Read-then-write：先读 cell head 选合法 transition |
| reservation orphan 留 follow-up | Normative TTL + cleanup Move + resolve API filtering |
| §7 文件树 `message.schema.json` 编辑 context_anchor | ~~已 strikethrough 删除~~ |
| attestation signature "对上述所有字段签名"（循环） | Canonical signing input 排除 signature 字段 + domain separator |

### 13.2 Rev 6 完成度评估

| 维度 | 状态 |
|---|---|
| cas-register predicate 显式 + validate_op singleton enforcement | ✅ |
| Recovery Move 严格符合 [§8 协议](spec/v1/zh/authz/event-auth-state-resolution.md) | ✅ |
| Recovery capability normative 定义 | ✅（controller principal 持 `cx.capability.agent_workspace.recover`） |
| 三 cell 模型全文一致 | ✅（schema / events / lifecycle / conformance / file tree 全部统一） |
| Watcher read-then-write 模式 | ✅（§4.3 + §4.8） |
| 二次失效 transition 边覆盖 | ✅（watcher 按当前 state 写合法 transition） |
| Reservation orphan 处理 | ✅（TTL + cleanup Move + resolve API filtering） |
| Message schema 不变 | ✅（§7 文件树残留已清） |
| Attestation signature 无循环 | ✅（canonical signing input + domain separator） |
| Rev 1-5 残留清理 | ✅ |
| Security threat model | 🔴 follow-up |
| Workspace navigation View / inbox | 🔴 follow-up |
| 跨司法辖区合规 / 被遗忘权 | 🔴 follow-up |

### 13.3 建议第六轮 review 重点

- **`reservation_cell_already_set` 失败语义**：spec 是否需要在 validate_op 层显式新增"singleton cell 标记 + basis=null 但 settled≠null reject"规则？这是依赖项，本提案当前 SHOULD 标记，需 spec PR 把它抬成 MUST
- **Recovery state_witness / inclusion_proof 的具体可用 anchor view**：在 multi-master 部署中，不同 sync node 的 anchor view 可能不同；reviewer 持有的 state_witness 必须来自 ⊥ 发生 *之前* 的 effective state，但"之前"在 anchor 偏序下可能模糊。需明确选择规则（参见 [§8.1 Pre-conflict State Witness](spec/v1/zh/authz/event-auth-state-resolution.md)）
- **三 cell 的 conformance vector 完整性**：需要列出每 cell 每条合法 transition 边的正例 vector + 每条非法 transition 的负例 vector（execution 9 边 + transparency 3 边 + source_authority 5 边 = 17 个正例 + 各 cell 的非法 transition 负例至少 3 个）
- **`cx.agent_task.cancel` 便捷事件的 reducer 语义**：是 alias 写 `execution.transition(to=cancelled_by_controller)`，还是同时 reset transparency / source_authority 为 ok？建议 v1 仅写 execution cell（其他 cell 保留 audit 痕迹）
- **reservation cleanup capability 攻击面**：`cx.capability.agent_workspace.cleanup` 由 sync node system actor 持有时，如何防止 sync node 滥用 cleanup 清空有效 reservation？建议 cleanup Move MUST 携带 `evidence: ttl_expired_at >= reservation_ts + ttl`，reducer 验证

---

## 14. Rev 6 → Rev 7 修订追踪（作者自审）

第六轮 review 没有外部 reviewer，由作者自审发现 5 项必修 + 4 项 follow-up：

| # | 自审发现 | Rev 7 修订位置 |
|---|---|---|
| 1 (P0) | `head_eq: null` 实际不阻止 singleton 覆盖 | §3.2 改用 **empty sentinel `"__unset__"` pattern**：cell schema 声明 `initial_value="__unset__"`，reservation predicate = `head_eq: "__unset__"`；singleton 由算法 `basis≠settled and basis≠null → ⊥` 真正成立。新增 spec PR 依赖（cell schema initial_value 字段）作为 known dependency |
| 2 (P0) | 不可达 transition 边 | §3.6 删除：transparency `reconfirmed_after_loss → lost`、source_authority 重复的 `ok → revoked` + `reconfirmed_after_revoke → ok`；transparency 与 source_authority 各简化为 2 条合法 transition |
| 3 (P1) | Cleanup capability holder 不一致 | §3.2 统一：仅 controller principal 持 `cx.capability.agent_workspace.cleanup`，可标准 capability delegation 给 sync node system actor；cleanup Move MUST 携带 `ttl_evidence` 让 reducer 验证防滥用 |
| 4 (P1) | §4.7 reverse publish 缺 read-then-write | §4.7 加 read-then-write：先读 execution_state cell head，按当前 state 选 transition 或 abort；防御多设备 race |
| 5 (P2) | `redirect_event_commitment` 反枚举副作用 | §3.3 删除该字段：nonce 公开则反向 enumerate agent_task_id；私存则第三方无法验证；`redirect_pair_id` 已足够双端关联，commitment 是冗余 + 有副作用 |

### 14.1 Rev 6 → Rev 7 删除项

| 删除字段 / 描述 | 替代 |
|---|---|
| `head_eq: null` predicate | `head_eq: "__unset__"` 字面 sentinel + cell schema `initial_value="__unset__"` |
| validate_op 层 "singleton + basis=null + settled≠null reject" 软性约束 | empty sentinel pattern + cas-register 算法自然强制 |
| transparency `reconfirmed_after_loss → lost` 边 | 删除（不可达，Message redaction 是 terminal） |
| source_authority `ok → revoked` 重复条目 | 删除（已在第一条 ok → revoked 表达） |
| source_authority `reconfirmed_after_revoke → ok` 边 | 删除（authority_grant_ref 绑定原 grant_id，re-grant 是新 grant 与 task 无关） |
| source_authority `reconfirmed_after_revoke → revoked` 边 | 删除（同上） |
| `cx.content.mention_redirect.redirect_event_commitment` 字段 | 删除（nonce 矛盾 + 反枚举风险 > 验证价值）；`redirect_pair_id` 单独承担双端关联 |
| Cleanup capability 由"controller 或 sync node system actor 持有" | "controller 持有，可 delegate 给 sync node" |
| §4.7 controller 盲写 `from=active` | read-then-write，按当前 state 选 transition |

### 14.2 Rev 7 显式 follow-up（非阻断，留待后续提案 / spec PR）

| 项 | 说明 |
|---|---|
| Conformance vectors 完整覆盖 | §6.2 列了 19 个；FSM 完整覆盖需 execution 9 合法 + 3 非法 + transparency 2 合法 + 2 非法 + source_authority 2 合法 + 2 非法 + saga/recovery/orphan 6 + 其他 8 = **34+**。需要分批补 |
| Workspace root MLS group membership normative | 默认 = "controller 设备 + workspace_visible agents"；workspace_visible flag 在哪声明，default 值如何，需补 |
| `attached_authority.inline_copy` size limit | 内嵌完整 agent_authority 含 knowledge_sources[]，膨胀风险。建议删除 inline_copy 仅保留 anchored_event_ref / state_witness 两种 |
| Workspace teardown / 跨 deployment 迁移 | Controller 解散 workspace、跨 deployment 迁移 workspace root、redirect_pair_id audit trail 的持久化策略 |

### 14.3 Rev 7 显式 spec PR 依赖

为本提案落地必需的 spec-level 变更：

1. **Cell schema `initial_value` 字段** —— 用于声明 cas-register cell 的初值（empty sentinel pattern 的基础）；当前 spec 无此字段，需 schema 扩展
2. **Capability action 注册**：`cx.capability.agent_workspace.reserve` / `recover` / `cleanup` —— 在 capability action registry
3. **Cell key namespace 注册** —— 5 个 cell namespace 进 cell-key-registry
4. **Feature id 注册** —— `cx.feature.mention_redirect.v1` / `cx.feature.import_attestation.v1`
5. **Constraint kind 注册** —— `mention_respond_only` / `import_to_external_space`

### 14.4 Rev 7 完成度评估

| 维度 | 状态 |
|---|---|
| cas-register singleton 真正成立（empty sentinel） | ✅（依赖 spec PR `initial_value` 字段） |
| Transition 表无不可达边 | ✅ |
| Cleanup capability holder 一致 | ✅ |
| Watcher / publish 一致使用 read-then-write | ✅ |
| `redirect_event_commitment` 反枚举副作用消除 | ✅ |
| Conformance vectors 完整 | 🟡 follow-up（已识别需 34+） |
| Workspace MLS membership normative | 🔴 follow-up |
| `inline_copy` size 限制 | 🔴 follow-up |
| Workspace teardown / migration | 🔴 follow-up |
| Spec PR 依赖明确列出 | ✅（§14.3） |
| Rev 1-6 残留清理 | ✅ |
| Security threat model | 🔴 follow-up |

**Rev 7 状态**：作者自审已修完 5 项实质阻断；剩余 follow-up 已明确列为后续提案 / spec PR 工作；spec PR 依赖 5 项显式列出。本提案可以拿给独立 reviewer 跑第六轮（外部）review，重点确认：

1. Empty sentinel pattern 是否被 spec 维护者接受为 cell schema `initial_value` 字段
2. Reservation cleanup 的 `ttl_evidence` 字段是否需要更强的反 backdating 设计
3. 二次失效 transition 边删除后，是否真的没有遗漏场景（例如：某种 federation 场景下 source Space 状态变化是否需要重新建立 transition）
