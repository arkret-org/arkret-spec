# Capability Model

## 1. 目标

Contrix 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- `flow`、`message`、`space`、`morph`、`view` 的动作集不同。
- Flow 的 `synthesis` 与 `discussion` branch 需要独立裁剪。
- agent 必须被精细授权。
- 授权变化必须可审计。

## 2. 基本原则

### 2.1 授权主体 SHOULD 是稳定 principal

grant 的 `issuer` 与 `subject` SHOULD 使用 DID。

Handle、邮箱、域名用户名等人类可读标识 MUST NOT 作为权限主体主键。

### 2.2 权限必须显式表达

不要依赖以下隐式假设：

- 进入 Space 就拥有全部能力。
- 能编辑 Flow synthesis 就一定能在 discussion 里发消息。
- discussion moderator 天然拥有全量 Flow 管理权。

### 2.3 权限判定基于当时有效的 capability 集

操作是否合法，应由该时点有效 grant 集决定。

### 2.4 DID 是主体，Claim 是条件

权限模型分三层：

```txt
Identity: DID
Human-readable binding: Handle
Authorization condition: Claim / Attestation
```

## 3. Grant 对象

示例：

```json
{
  "id": "cx:grant:01js0gr0000000000000000000",
  "type": "capability",
  "schema": "cx.schema.capability.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject": "did:web:agent.copy.example.com",
  "actions": [
    "cx.flow.read",
    "cx.flow.update",
    "cx.message.create",
    "cx.morph.read",
    "cx.morph.update"
  ],
  "resources": [
    {
      "kind": "object",
      "space_id": "cx:space:01js0sp0000000000000000000",
      "object_type": "flow",
      "scope": "space_wide"
    },
    {
      "kind": "morph",
      "space_id": "cx:space:01js0sp0000000000000000000",
      "morph_type": "document",
      "scope": "space_wide"
    }
  ],
  "constraints": [
    {
      "constraint_type": "temporal",
      "effect": "allow",
      "expires_at": "2026-04-30T00:00:00Z"
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "scope": "write",
      "fields": ["title", "description", "brief", "summary", "body", "fields.status"]
    }
  ]
}
```

### 3.1 条件化 Grant

Grant 的 `subject` 可以是具体 DID，也可以是条件选择器。

条件化 grant MUST 明确 claim issuer、claim type、有效状态和适用资源范围。节点 MUST NOT 仅凭 handle 字符串后缀、邮箱域名或显示名判断条件成立。

## 4. Resource Selector

Contrix v1 支持以下 `kind`：

- `space`
- `flow`
- `message`
- `morph`
- `object`
- `relation`
- `event`
- `actor`
- `view`
- `schema`
- `policy`
- `invite`
- `read_marker`
- `space_kind:<kind>`
- `flow_kind:<kind>`
- `flow_semantic_kind:<kind>`
- `morph_type:<type>`
- `relation_kind:<type>`

资源选择器应把 Space (kind=board) / Space (kind=list) 表达为 `space` + `kind` 约束，而不是把它们当成独立主对象域。

## 5. 动作集合

动作名称与 `operations-sync.md` 中的事件 kind 对齐，使用 `cx.<domain>.<action>` 点分记法。通配符 `cx.<domain>.*` 表示该域的管理权限。

### 5.1 通用动作

- `cx.space.discover`
- `cx.object.read`
- `cx.object.read_metadata`
- `cx.object.read_content`
- `cx.object.archive`
- `cx.object.restore`

### 5.2 Flow 与工作流动作

- `cx.flow.create`
- `cx.flow.read`
- `cx.flow.update`
- `cx.flow.archive`
- `cx.flow.restore`
- `cx.flow.convert`
- `cx.flow.move`
- `cx.flow.reorder`
- `cx.flow.branch.enable`
- `cx.flow.branch.disable`
- `cx.flow.branch.update`
- `cx.flow.branch.set_primary`
- `cx.flow.branch.member`
- `cx.flow.branch.history_visibility`
- `cx.flow.branch.policy_components`
- `cx.relation.create`
- `cx.relation.update`
- `cx.relation.delete`
- `cx.container.move_item`
- `cx.container.rebalance`
- `cx.view.*`

Flow 权限只覆盖 Flow 自身字段、branch 配置和 position / relation 管理，不自动授予 Message 正文权限。

### 5.3 Discussion 与消息动作

- `cx.event.read`
- `cx.message.create`
- `cx.message.revise`
- `cx.message.revise.own`
- `cx.message.redact`
- `cx.message.redact.own`
- `cx.reaction.add`
- `cx.reaction.remove`
- `cx.flow.branch.read`
- `cx.flow.branch.admin`

### 5.4 管理动作

- `cx.space.admin`
- `cx.flow.admin`
- `cx.schema.*`
- `cx.capability.*`
- `cx.policy.*`
- `cx.invite.create`
- `cx.invite.revoke`
- `cx.invite.*`
- `cx.approval.vote`

### 5.5 服务动作

- `cx.sync.*`
- `cx.blob.*`

### 5.6 人类界面与个人状态动作

- `cx.read.marker`
- `cx.notification.read`
- `cx.notification.ack`
- `cx.invite.accept`

## 6. Constraints

Contrix v1 支持：

- `expires_at`
- `not_before`
- `fields_write_allow`
- `fields_write_deny`
- `flow_kind_allow`
- `flow_semantic_kind_allow`
- `morph_type_allow`
- `facet_allow`
- `allowed_flow_refs`
- `allowed_space_refs`
- `allowed_view_refs`
- `allowed_branches`
- `room_kind_allow`
- `relation_kind_allow`
- `allowed_from_container_refs`
- `allowed_to_container_refs`
- `visibility_allow`
- `blob_max_bytes`
- `encryption_required`
- `message_edit_window`
- `max_delegation_depth`
- `rate_limit`
- `approval_required`
- `approval_mode`
- `approval_actor_refs`
- `approval_relation`
- `accountability_required`
- `guardian_approval_required`
- `controller_approval_required`
- `requires_claims`
- `trusted_claim_issuers`
- `claim_refresh_required`
- `claim_max_age`

## 7. Claim / Attestation

Claim / Attestation 表示某个 issuer 对某个 subject 的可验证声明。

它用于表达组织成员、组织角色、监护关系、设备可信度、年龄/保护状态、认证等级等条件。

建议最小结构保持不变，权限判断仍必须基于 DID、claim issuer、有效期、撤销状态和最小披露范围。

## 8. Accountable Actor 授权

Capability 必须支持“有直接身份但需要责任主体/监护主体/控制主体”的 Actor。

这类 Actor 包括：

- AI agent
- 服务机器人
- 自动化账号
- 未成年人账号
- 受保护主体账号
- 企业托管账号
- 第三方集成账号

核心规则：

- accountability 不等于 capability。
- owner / guardian / controller 不会自动把自己的权限传给 subject。
- subject 要执行操作，仍然必须命中显式 grant。
- 高风险动作 MAY 要求 responsible / guardian / controller approval。
- Event SHOULD 记录 grant、delegation chain、approval 证据和执行上下文。

### 8.1 Proposal 模式

高风险操作建议使用 proposal 模式：

```txt
actor -> proposal.created
guardian/controller -> proposal.approved
system/human -> `cx.flow.update` 或 `cx.morph.update`
```

## 9. Agent 安全授权

给 agent 授权时 SHOULD 默认：

- 只授予明确 Space / Flow / Message / Morph / View 范围。
- 只授予所需动作。
- 只授予有限时效。
- 尽量限制可写字段、可写 branch 和可写 Morph 类型。
- 需要时要求 controller / responsible actor approval。

高风险模式包括：

- 给 agent 长期全 Space 管理权。
- 让 agent 直接继承 human owner 全权限。
- 不设过期时间。
- 不保留 agent 执行审计链。
- 高风险操作不需要 approval。

## 10. Delegation

委托表示 subject 可以将其能力的一部分再授予第三方。

若 `max_delegation_depth = 0`，则不可继续委托。  
若大于 0，则：

- 每次再授权 MUST 递减深度。
- 再授权不得扩大原始资源范围和动作范围。
- 委托链 MUST 可验证。

## 11. 有效权限集合

Contrix v1 采用 allow-grant + explicit revoke 模型。

也就是说：

- 协议层没有通用 `deny` grant。
- 有效权限集合是所有当前有效 grant 的并集。
- revoke 通过显式 Event 把 grant 从有效集合移出。

## 12. Revocation

撤销必须是显式操作，而不是删除 grant 记录。

示例：

```json
{
  "type": "cx.capability.revoke",
  "body": {
    "grant_ref": "cx:grant:01js0gr0000000000000000000",
    "reason": "contract ended"
  }
}
```

## 13. Invite、通知与已读状态

这些人类友好能力必须进入权限模型，而不是留给产品私有后门：

- 创建 / 取消 invite 需要 `cx.invite.create` / `cx.invite.revoke`
- 接受发给自己的 invite 需要 `cx.invite.accept`
- 写入自己的 `read_marker` 需要 `cx.read.marker`
- 读取 notification 需要 `cx.notification.read`
- `cx.notification.ack` 只应影响自己的派生 inbox 状态

## 14. Role 只是 bundle

产品层可以提供：

- `space_admin`
- `board_manager`
- `contributor`
- `observer`
- `discussion_moderator`
- `agent_writer`

但这些 role 在协议层只是 capability bundle，不是主语义。

## 15. 读权限与可发现性

读权限不只是“能不能 fetch 内容”，还包括：

- 能否发现对象存在。
- 能否看到 discussion 历史。
- 能否看到被撤回消息的元信息。
- 能否读取附件内容。

初版至少区分：

- `discover`
- `read_metadata`
- `read_content`
- `read_history`

## 16. Flow / Discussion 场景下的权限建议

Contrix v1 至少区分：

- 修改 Flow synthesis。
- 开启或关闭 discussion branch。
- 管理 discussion membership。
- 普通发送消息。
- 编辑自己的消息。
- 编辑任意消息。
- 撤回自己的消息。
- 撤回任意消息。
- 转换 `kind="card"` / `kind="room"`。

这能避免把“能改 Flow”错误地和“能进 discussion”混成一种权限。

## 17. 决策执行位置

权限检查不应只在客户端发生。

权限检查 MUST 至少在以下位置执行：

- client 预检查
- Events API 接收写入时
- Sync Service 分发前
- 受托 search / projection 服务返回结果前
- blob store 下发内容前

## 18. 最小权限判定算法与性能优化

给定一个操作，节点理论上的判定全链路如下：

1. 解析 actor DID。
2. 验证签名链。
3. 查找当时有效 grant 集。
4. 展开 delegation，并执行 cycle detection。
5. 判断 resource selector 是否覆盖 target。
6. 判断 action 是否匹配。
7. 判断 constraints 是否满足。
8. 若 grant 或 constraint 要求 claim，拉取并验证 claim / attestation。
9. 判断 claim issuer 是否可信。
10. 判断 claim 是否有效、未过期、未撤销。
11. 若需要 approval，校验 responsible / guardian / controller approval 证据。
12. 应用 revoke 和 superseding 规则。

### 18.1 高频交互的 O(1) 快速路径

在“discussion 消息收发”或“Flow 状态拖拽”等高频交互场景下，声称支持主客户端或 Principal Server profile 的实现 SHOULD 提供 capability 快照缓存或语义等价 fast path。

高频 fast path 典型事件：

- `cx.message.create`
- `cx.reaction.add`
- `cx.flow.update`
- `cx.flow.move`
- `cx.flow.reorder`
- `cx.flow.convert`

Fast path 只能缓存基础 capability 是否允许。Moderation / Policy Server 的 `deny`、`quarantine`、`require_review`、rate limit、legal hold 和 abuse policy 仍 MUST 在写入接收、分发和查询返回前执行。

## 19. 设计决定

Contrix v1 固定：

- 权限采用 capability 模型。
- Flow、discussion、agent 执行都使用统一 grant 体系。
- `cx.message.revise.own` 与 `cx.message.redact` 分开。
- invite / notification / read marker 进入统一 capability 体系。
- 协议级语义采用 allow-grant + explicit revoke。
- agent 使用窄权限、短时效、可审计授权。
- accountable Actor 是通用授权对象。
- owner / guardian / controller 不导致权限自动继承。
- grant 主体使用 DID 或 condition selector，不使用 handle 作为权限主键。

## 20. 规范性收敛

以下授权事项在 v1 中按本节和引用文档执行，不再作为开放问题：

- Resource selector 语法由 `resource-selector-grammar.md` 和 `resource-selector.schema.json` 固定。
- Constraint schema 由 `constraint-schema.md` 固定。
- 多个 grant 命中时，允许动作取并集，但约束按最严格规则相交。
- Moderation policy 不得凭空授予 capability。
- Approval proof 与 proposal 状态机由本文件、`event-auth-state-resolution.md` 和 conformance vectors 固定。
- Claim / attestation envelope 使用 `data-structures.md` 的 Proof、`identity-handles.md` 的 claim / VC 规则和 `progressive-disclosure.md` 的 presentation 规则。
