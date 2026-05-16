# Proposal — Agent Workspace 与 Source Flow 协作模式

Status: **Draft**（讨论中，未进入正式 spec）
Created: 2026-05-16
Scope: v1（尽量复用现有原语，最小协议改动）

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
                    │ + re-encrypted quote_external
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

**Reducer 行为**：源 Flow 加入 agent 时，邀请 event 携带 `agent_member_profile: <name>`；reducer 把它展开为标准 capability grant 写入。运行时 capability check 不依赖 profile name，只依赖展开后的 grant，保证 audit 完整。

**MUST**：profile 是声明性 sugar，不绕过 capability 检查；任何 grant escalation 仍走 §authz 标准流程。

**与 `cx.schema.agent_authority.v1` 的关系**：现有 [encryption-and-audit.md §4.1](spec/v1/zh/crypto-media/encryption-and-audit.md) 已定义 `cx.schema.agent_authority.v1` 承担 controller↔agent 绑定 + knowledge_sources + capability delegation。本提案的 `agent_member_profile` MUST 通过 agent_authority 表达；reducer 验证 agent join source Flow 时检查 agent_authority 中 controller 是否为 inviter principal，capability grant 是否覆盖 `agent_member_profile` 展开的动作集。**不引入新的"controller 字段"，全部走 agent_authority。**

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
    "stale_quote_external_handling": "lock_lazy"
  },
  "relation_profiles": [
    {
      "relation_kind": "derived_from",
      "from_type": "space",
      "to_type": "space",
      "cardinality": "many_to_one",
      "max_to_per_from": 1,
      "scope": "global"
    },
    {
      "relation_kind": "derived_from",
      "from_type": "flow",
      "to_type": "flow",
      "cardinality": "many_to_one",
      "max_to_per_from": 1,
      "scope": "global"
    }
  ]
}
```

**DID Document service entry**：

```json
{
  "id": "did:web:alice.example#agent-workspace",
  "type": "ContrixAgentWorkspace",
  "serviceEndpoint": "cx:space:01964200-0000-7000-8000-000000000000"
}
```

**子结构约定**：
- Workspace root Space 内通过 `cx.relation.derived_from` 把每个 mirror Space 关联到对应源 Space
- Mirror Space 内每条 mirror Flow 通过 `cx.relation.derived_from` 关联到对应源 Flow
- 跨 Space `derived_from` 走 [relation.md §4](spec/v1/zh/models/relation.md)（已有机制）

**Lazy 创建语义**：
- Workspace root 在 controller 首次启用 agent 集成时创建一次（client-driven，写入 DID Document）
- Mirror Space / Mirror Flow 在**首次 @ mention** 或 controller 在 UI 显式开启时 lazy 创建
- 并发首次创建走 Move precondition `cardinality=many_to_one` 自动去重

**并发首次创建详细规则（防多设备竞态）**：

Alice 在两个设备同时第一次 `@my-agent` 时，两个设备都会尝试创建 mirror Space + mirror Flow。规则：

1. 客户端 SHOULD 在生成创建 Move **之前**先调用 `agent_workspace.resolve_mirror_flow(source_flow_id)`（见下）查询是否已存在；存在则复用，不创建。
2. 若 query 返回空，客户端按 §4.1 流程生成创建 Move。Move 的 precondition MUST 包含 `derived_from(mirror_flow→source_flow_id)` cell 为空（`many_to_one` 的标准 lattice check）。
3. 两个设备的 Move 同时到达 reducer：因 Move precondition 检查的是同一 cell，**reducer 按 `event-auth-state-resolution.md` 标准 cas-register 规则确定性选 winner**；loser Move `failed_precondition` 返回 `mirror_flow_already_exists`，payload 包含 winner mirror_flow_id。
4. Loser 设备 MUST 撤销本地 draft 状态，把用户输入的指令重写为指向 winner mirror_flow 的 `cx.message.create`，重新提交。**MUST NOT** 直接 retry 创建 Move（会再次失败）。
5. Client UX MUST 对用户透明（看起来就像消息发出了），不暴露 race；audit trail 由两条 Move 的 reducer 结果记录。

**新增 service operation `agent_workspace.resolve_mirror_flow`**：

```
GET /v1/agent_workspace/mirror_flow?source_flow_id=<id>
→ 200 { "mirror_flow_id": "cx:flow:...", "mirror_space_id": "cx:space:..." }
→ 404 { "reason": "not_provisioned" }
```

- 该 op 在 controller 自己的 principal server 服务，**对 controller 自己可读**
- 实现 SHOULD 在 sync node 的本地索引 view `(source_flow_id → mirror_flow_id)` 上完成，无需写入 frontier
- 跨 deployment：source_flow_id 解析到 mirror_flow_id 不要求源 deployment 参与；纯 controller 端事实

---

### 3.3 改动 C — Content Block `cx.content.mention_redirect`

**目标**：source Flow 中的 @-mention-my-agent 不携带指令正文，只携带"我把指令送到了我的私人 workspace"的透明 stub；具备 spec-level 可识别性（不是字符串约定）。

**文件**：
- `spec/v1/zh/models/content-types.md` — 新增 `cx.content.mention_redirect`
- `artifacts/schemas/` — 新增 `content-mention-redirect.schema.json`

**Schema sketch**：

```json
{
  "kind": "cx.content.mention_redirect",
  "target_actor_id": "did:web:alice-agent.example",
  "redirect_to_space_id": "cx:space:<alice mirror space>",
  "redirect_to_flow_id": "cx:flow:<alice mirror flow>",
  "redirect_event_id": "cx:event:<alice mirror flow 中真实指令 event>",
  "visibility_note": "redirect_only",
  "human_readable_summary": "Alice asked her agent privately"
}
```

**规则**：
- `target_actor_id` MUST 是 sender principal 的 controlled agent（agent 的 `cx.schema.agent_authority.v1` 中 controller 字段引用 sender principal）。reducer 验证此关系；不满足 MUST `unauthorized` reject
- `redirect_to_*` 字段是 opaque references；source Flow 其他成员看到的只是"Alice mentioned her agent and routed privately"，**不能展开**到 mirror Space（cross-Space reference 走 §4.5 反枚举，默认 `locked`）
- `human_readable_summary` 是发送者客户端生成的脱敏摘要；E2EE Space 中 server MUST NOT 生成或重写
- redact 行为：源 Flow 撤回 stub 不影响 mirror Flow 中真实指令；mirror Flow 撤回真实指令不影响 source Flow stub（两个独立 redaction 域）

**Target 必须是 sender 自己 agent（normative）**：

- Reducer MUST 检查 `target_actor_id` 在 sender principal 控制下（通过 `cx.schema.agent_authority.v1` 验证 `controller == sender principal`）
- 不满足时 reducer MUST **拒绝 `mention_redirect` event**（`unauthorized`，reason `redirect_target_not_owned`），**不得静默降级为普通 `cx.content.mention`**——降级会让客户端误以为路由成功而其实指令公开泄露
- 客户端 SHOULD 在发送前本地预校验；若用户想公开 @ 别人的 agent（典型场景：找 Bob 的客服 bot 问问题），客户端 MUST 使用 `cx.content.mention`，**不使用** `mention_redirect`
- 这避免了"我以为我在偷偷指挥别人家的 agent，但其实别人 agent 公开收到了"这类隐私事故

**`human_readable_summary` 可见性披露（normative）**：

`human_readable_summary` 对 source Flow 的所有成员可见。这是一个易被忽视的元数据泄露点：

- 客户端 MUST 在 compose UI 中显式提示用户："此摘要将对源 Flow 所有成员可见"（或等价语义）
- 客户端 MUST NOT 自动从私有指令正文派生 summary（防止 LLM 助记直接把敏感词带出来）
- Spec **建议默认值** = 与 sender 同一 locale 的通用文案，如 `"<sender_handle> 私下询问了 agent"` / `"<sender_handle> asked their agent privately"`；客户端 MAY 让用户自由编辑但 MUST 显示"对外可见"提示
- 服务端 / reducer 不验证 summary 内容（属于客户端 UX policy 范畴）；但 server MUST NOT 重写或生成 summary（E2EE 边界约束）

**与现有 `cx.content.mention` 的关系**：`mention_redirect` 是显式 routing 变体；普通 `cx.content.mention` 不触发 routing，是标准公开 @。两者 wire-level 不可互相降级（参见上文"Target 必须是 sender 自己 agent"规则）。

---

### 3.4 改动 D — `context_anchor` 字段 + Cross-Space E2EE 引用语义

**目标**：mirror Flow 中的 message / event 携带标准化的"源 Flow 上下文锚"，让 agent 能精确定位被讨论的源消息且不越权读后续内容。

**文件**：
- `spec/v1/zh/models/flow-and-message.md` — 在 Message schema §8.2 增加可选顶层字段 `context_anchor`
- `artifacts/schemas/message.schema.json` — 字段定义
- `spec/v1/zh/models/content-types.md` — 新增 `cx.content.quote_external` content block

**Message `context_anchor` 字段**：

```json
{
  "context_anchor": {
    "source_space_id": "cx:space:<source>",
    "source_flow_id": "cx:flow:<source>",
    "source_cursor_event_id": "cx:event:<source frontier cap>",
    "trigger_message_ref": "cx:message:<stub redirect message>",
    "anchor_created_at": "2026-05-16T10:00:00Z"
  }
}
```

**语义**：
- `source_cursor_event_id` 是**只读上界**——agent 处理此指令时 SHOULD 只读取源 Flow 中 ≤ 该 event 的历史；超出此 cursor 的新内容不在本次任务上下文（防止 agent 越权监听后续聊天）
- 该约束是 SHOULD（reducer 不强制，client / agent runtime 实施）；如需 normative enforce，走 §3.5 capability constraint

**Content block `cx.content.quote_external`**：

```json
{
  "kind": "cx.content.quote_external",
  "origin_space_id": "cx:space:<source>",
  "origin_flow_id": "cx:flow:<source>",
  "origin_message_id": "cx:message:<source>",
  "origin_actor_id": "did:web:bob.example",
  "origin_created_at": "2026-05-16T09:55:00Z",
  "re_encrypted_by": "did:web:alice-agent.example",
  "re_encrypted_at": "2026-05-16T10:00:01Z",
  "re_encryption_attestation": "<signature over origin_message_id + canonical content hash + re_encrypted_by + re_encrypted_at>",
  "content": { "kind": "cx.content.text", "body": "（重加密引入的源消息正文）" }
}
```

**规则**：
- `re_encrypted_by` 是把内容从源 MLS group 转移到目标 MLS group 的 actor；reader MUST 看到此字段作为信任来源标识
- `re_encryption_attestation` 是 `re_encrypted_by` 对 `(origin_message_id, canonical_content_hash, re_encrypted_by, re_encrypted_at)` 的签名；防止 attribution 伪造
- reader UI MUST 显示"由 X 重加密引用自另一 E2EE Space"，不可呈现为原作者直接发言
- 源消息后续被 redact 不会自动撤回 quote_external（两个独立 redaction 域）；但 mirror Space MAY 显示 `origin_locked` 状态以提示

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

## 4. 生命周期场景（Normative）

### 4.1 用户首次 @-自己的-agent

1. Alice 在 source Flow type `@my-agent <text>`
2. Client 检测 `target` 是 Alice 自己的 agent → 弹"send to private workspace"确认
3. 确认后：
   - 客户端写 `cx.message.create` 到 source Flow，content = `cx.content.mention_redirect`（无指令正文）
   - 同一批 Move 中写 `cx.message.create` 到 mirror Flow，content = 真实指令，`context_anchor` 锚回 source Flow frontier
   - 如果 mirror Space / mirror Flow 不存在，先批量写 `cx.space.create` + `cx.flow.create` + `cx.relation.create(derived_from)`
4. Source Flow 其他成员看到 stub（透明）；mirror Flow 接收真实指令

### 4.2 用户增加新 agent 到 source Flow

1. Alice 在 source Flow `cx.flow.member.add(agent_Y)` with `agent_member_profile`
2. 源 Space reducer 验证：
   - agent_Y DID Document `controller == Alice's principal`
   - Alice 在源 Flow 有 `member.add` capability + 源 Space 允许 agent
3. 成功后推送 `agent_membership_change` 到 Alice 的 workspace
4. Alice 的 mirror Flow（如果存在）显示"agent_Y 已加入源 Flow"——**不自动加入 mirror Flow**，Alice 显式决定

### 4.3 用户从 source Flow 移除 agent

1. `cx.flow.member.remove(agent_X)`
2. 该 agent 在源 Flow 的所有 capability grant 失效；后续 read / write 拒绝
3. 推送 `agent_membership_change` 到 Alice 的 workspace
4. **Alice 的 mirror Flow 不自动移除 agent_X**——历史记忆有保留价值
5. 后续 mirror Flow 中 `context_anchor` 引用源 Flow 但 agent_X 已无读权，display 降级 `locked`（§4.5 反枚举）

### 4.4 用户在 mirror Flow 加新 consulting agent

1. Alice 在 mirror Flow `cx.flow.member.add(agent_Z)`
2. mirror Space reducer 验证 agent_Z DID controller == Alice（profile MUST）
3. **agent_Z 对 source Flow 没有任何访问能力**——它只能基于 mirror Flow 中已存在内容（包括 primary agent 重加密引入的 quote_external）工作
4. 如果 agent_Z 需要源 Flow 上下文，**必须**由 primary agent（in source Flow）摘要重加密引入

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

1. Mirror Flow 中 agent 产出一条 `cx.message.create`（content 为草稿）；agent 用 `cx.relation.references` 关联回 `context_anchor.trigger_message_ref`
2. Controller 在 mirror Flow UI 看到草稿，可编辑、修改、追问 agent 重写
3. Controller 满意后点击 "publish to source Flow"，客户端：
   - 在 source Flow 写 `cx.message.create`，**`created_by = controller principal`**（不是 agent）
   - content 可选包含 `cx.content.quote_external` 块引用 mirror Flow 的 agent 草稿（用于审计与归属透明）
   - 在 mirror Flow 写 `cx.relation.create(published_to, from=mirror_message, to=source_message)` 标记已发布
4. Audit 后果：source Flow 看到的是 Alice 自己的发言；如果 Alice 选择包含 quote_external，其他成员能看到"由 agent_X 起草"——**完全由 Alice 决定披露程度**

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

## 5. v1 显式不做的事

- ❌ **`cx.grant.delegate_read`（scoped read 委托新增）**——MLS E2EE 下无法干净实现；**而且 spec 已有 `cx.schema.agent_authority.v1` 的 `knowledge_sources[]` 表达非 plaintext 范围的访问**（`visibility=metadata_only|derived_summary|ciphertext_only`），覆盖了大量场景；plaintext 跨 E2EE 边界继续走"primary agent 重加密引入"模式
- ❌ **Server-side @ mention 路由**——routing 是 client UX，server 不重写消息；source Flow stub 和 mirror Flow 真实指令是**两条独立 event**，由客户端原子提交，不存在 server-side fork
- ❌ **`on_behalf_of` Message 字段**——v1 仍以 agent DID 作为 `created_by`；agent 代表 controller 发言的语义由 capability constraint（agent_member_profile）+ DID Document `controller` 字段联合表达，足够 audit
- ❌ **Mirror Space 单点 deterministic 命名 `f(controller, source_space) → mirror_id`**——通过 controller 私有 sync node 维护索引 view + Relation 关联即可，不必引入全局确定性命名（避免元数据泄露 + 命名冲突）

## 6. 互操作 & Conformance

### 6.1 影响 profile

- `client_basic`：MUST 不实现 agent workspace 也能正常发送 / 接收 source Flow 消息；遇到 `cx.content.mention_redirect` MUST 当作 opaque text 显示（fallback 到 `human_readable_summary`）
- `agent_runtime`：SHOULD 实现完整 agent workspace 模式
- `enterprise_client`：SHOULD 实现，并提供 mirror Space UI

### 6.2 Conformance vectors（新增）

需在 `artifacts/conformance/` 添加：

1. ✅ **agent_member_profile 展开**：声明 preset → 展开为标准 grant，验证 capability check 等价
2. ✅ **mention_redirect 不可越权展开**：第三方 reader 尝试展开 `redirect_to_space_id` MUST `locked`
3. ✅ **mention_redirect target 必须是 sender 的 agent**：sender ≠ controller(target_actor_id) → `unauthorized`
4. ✅ **quote_external attestation 校验**：篡改 origin_message_id → reader 标记 `attestation_invalid`
5. ✅ **mirror Space derived_from 基数收紧**：尝试给同一 mirror Flow 加第二个 `derived_from` Source Flow → `cardinality_violation`
6. ✅ **agent_membership_change 通知脱敏**：E2EE workspace 收到的 preview MUST 由客户端预先脱敏
7. ✅ **Mirror Flow consulting agent 不能读源 Flow**：agent_Z 通过 cross-Space reference 尝试 fetch source content → `unauthorized`
8. ✅ **Source Flow archive 后 mirror context_anchor 降级**：stale anchor MUST 显示 `origin_locked`

## 7. 文档树变更总览

| 路径 | 操作 | 说明 |
|---|---|---|
| `spec/v1/zh/authz/capabilities.md` | 编辑 | 新增 Agent Member Profile 章节 |
| `spec/v1/zh/extensions/agent-workspace-profile.md` | **新增** | Space profile 定义 + lazy 创建语义 + 生命周期 |
| `spec/v1/zh/extensions/agent-protocol-interop.md` | 编辑 | 关联到 agent-workspace-profile |
| `spec/v1/zh/identity/identity-did.md` | 编辑 | 新增 `ContrixAgentWorkspace` service entry |
| `spec/v1/zh/models/content-types.md` | 编辑 | 新增 `mention_redirect` + `quote_external` block |
| `spec/v1/zh/models/flow-and-message.md` | 编辑 | Message §8.2 新增 `context_anchor` 字段 |
| `spec/v1/zh/discovery/push-notifications.md` | 编辑 | 新增 `agent_membership_change` notification type |
| `spec/v1/zh/models/private-objects.md` | 编辑 | notification_type 枚举扩展 |
| `spec/v1/zh/spec-map.md` | 编辑 | 把 agent-workspace pattern 加入阅读路径 |
| `artifacts/profiles/agent-member-profiles.json` | **新增** | 4 个 capability preset |
| `artifacts/profiles/conformance-profiles.json` | 编辑 | 注册 `cx.profile.agent_workspace.v1` |
| `artifacts/schemas/content-mention-redirect.schema.json` | **新增** | block schema |
| `artifacts/schemas/content-quote-external.schema.json` | **新增** | block schema |
| `artifacts/schemas/message.schema.json` | 编辑 | `context_anchor` 字段 |
| `artifacts/schemas/space.schema.json` | 编辑 | profile 枚举 |
| `artifacts/conformance/agent-workspace/*` | **新增** | 8 个 conformance vector |

---

## 8. 自审：可能的漏掉点 & 风险

> 写完上面 7 节后做的 second-pass，列出仍不确定或可能漏掉的点。

### 8.1 已识别但未在主提案中详述的点

**A. 源 Space 整体禁用 agent 的策略**
源 Space admin 可能要全局禁止"任何人加 agent"。这个能力 spec 里应该已经通过 capability constraint 表达（拒绝 `cx.flow.member.add` when target.kind=agent），但应该在 §3.1 改动 A 里明确：**`agent_member_profile` 不绕过 Space-level "agents disabled" policy**。建议：在 agent_member_profile 章节加一句 normative。

**B. Agent 身份验证：已通过 `cx.schema.agent_authority.v1` 解决**
~~`controller` 字段是否存在的疑问~~ 已 grep 验证：spec 已经有 [`cx.schema.agent_authority.v1`](spec/v1/zh/crypto-media/encryption-and-audit.md) 承担 controller↔agent 绑定 + capability delegation + knowledge_sources，[schema-registry.md:62](spec/v1/zh/conformance/schema-registry.md) 已注册。本提案 §3.1 已修正为引用此 schema，**不引入新字段**。
**剩余确认项**：grep 检查 `agent_authority.v1` 的实际 JSON schema 是否在 `artifacts/schemas/` 已落地、字段名是否与本提案 reducer 校验逻辑一致。

**C. 跨 deployment / federation 场景**
源 Space 在组织 B 的 deployment，controller workspace 在 deployment A。跨 deployment 的：
- `derived_from` Relation 创建——走现有 [federation.md](spec/v1/zh/sync/federation.md) cross-realm reference 规则
- `agent_membership_change` notification 跨 deployment 推送——走 push gateway 跨域语义
- Mirror Space 是否能在 deployment A 持有 quote_external 的"重加密自 deployment B"内容——*技术上没问题*（重加密在 controller client 完成），但合规上某些 deployment 可能禁止外部数据驻留
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
- 解决：`derived_from` cardinality `many_to_one` + Move precondition，reducer 自动收敛到一个 winner
- 但是 winner 的 mirror Flow ID 在不同设备上不同——loser 设备会本地有一个失效 mirror Flow draft，需要 client 重定向
- **风险**：UX 上可能造成"我刚刚发的消息去哪了"困惑。建议：client SHOULD 在创建前先 query workspace index；server 提供 `mirror_flow_for(source_flow_id)` 查询 op
- **未在主提案中明确**

**G. Workspace root 的 default View / inbox 结构**
Controller 可能有 N 个 mirror Space, 每个有 M 个 mirror Flow——怎么导航？
- 应该有标准化 View profile：按 source Space group、按最近 activity sort、按 unread count filter
- **未在主提案中规定**——建议作为 §3.2 改动 B 的子项添加，或作为后续 follow-up proposal

**H. Mention redirect stub 的可读性 vs 隐私 trade-off**
`human_readable_summary` 字段是 sender client 生成。Sender 可能写"Alice asked her agent privately"（最小化），也可能写"Alice asked agent to draft legal review for this thread"（高暴露）。
- **风险**：用户不知道这个 summary 对其他 source Flow 成员可见，可能不慎泄露指令意图
- **建议**：spec MUST 把 `human_readable_summary` 限定为发送方明确指定（不自动从指令内容派生）；client UI MUST 显示 "this summary is visible to all source Flow members"

**I. Retention 解耦带来的 GDPR / 数据驻留**
Source Space 被组织要求 retention=90 days；mirror Space 在 controller 私人服务器上 retention=forever。mirror 中的 quote_external 在源消息已合规删除后仍保留——可能违反"被遗忘权"。
- **风险**：合规风险，提案需要明确建议
- **建议**：profile 提供 `inherit_retention_from_source: boolean` 选项；某些合规 deployment MUST 把 quote_external 视为派生数据并 cascade retention

**J. Agent 团队"重加密引入"的信任放大问题**
Primary agent 把源消息重加密引入 mirror。如果 primary agent 自身被 prompt injection 或被攻陷，引入的 quote_external 可能内容被篡改但 attestation 仍是 primary agent 自己签的（合法）。
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
普通 `mention` Relation 会被 reducer 写入 `cx.relation.mentions(from=message, to=actor)`。`mention_redirect` 是否也产生 mentions Relation？如果产生，audit 上"X 被 mention 了"的事实是公开的（已经接受），但应该不要让 mentions Relation 携带 `redirect_to_*` 数据。
- 建议：`mention_redirect` 仍产生 `cx.relation.mentions`，但 Relation 本身不含 redirect 数据；redirect 数据只在 content block 中

**O. MLS group 在 mirror Space 加新 agent 时的 backward security**
Mirror Space MLS group 加新 consulting agent → 标准 MLS welcome → 新 agent 拿到当前 group state，能读 join 之前的历史（如果 history_visibility=joined）
- 这正常，no spec change，但要在 agent_workspace_profile 里明确 default `history_visibility=joined`（已写在 §3.2）
- **额外考虑**：consulting agent 加入后能看到 primary agent 之前重加密引入的 quote_external——这是预期还是问题？预期，因为 controller 显式拉进来的。

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
| 跨 deployment 互操作 | 🟡 未完整（resolve_mirror_flow 已说明端侧无需源 deployment 参与，但跨 deployment quote_external 合规未深入） |
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
5. **仍待 grep 验证**：`cx.flow.member.add` 是否已支持携带 `agent_member_profile` 引用，或需要扩展 event payload schema（§3.1 改动 A 实施前必须确认）

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
2. `cx.content.quote_external` content block（§3.4，必需）
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

- 收到 `cx.content.mention_redirect` MUST fallback 为显示 `human_readable_summary` 字符串（已在 §6.1 声明）
- 收到 `cx.content.quote_external` MUST fallback 为显示 `content` 字段 + 一行 "（来自另一 Space，由 X 引入）" 通用提示
- 这两个 block 的 schema MUST 标记 `unknown_content_block_fallback_safe: true` 让旧客户端可识别 fallback

**对未实现 `agent_workspace` profile 的服务端**：

- 服务端 reducer 把该 profile 当作"未知 Space profile"处理：保留 Space 字段，按 Space schema 标准规则归约；不实施 profile 特定的 cardinality 收紧（即 `derived_from many_to_one` 不强制）
- 这意味着混合部署下 mirror Space 行为可能稍微宽松，但**不破坏 wire 互操作**

### 9.3 回退路径（rollback）

如果提案后续在 v1.x 修订时发现严重问题，回退策略：

- `mention_redirect` 与 `quote_external` block 一旦 ship 进 schema-registry，不应删除（向后兼容）；但 MAY 在新 minor 版本中标记 deprecated 并引导客户端用替代 block
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
