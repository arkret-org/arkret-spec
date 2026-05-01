# Capability Model

## 1. 目标

Contrix 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- 跨组织协作很常见
- Room、Board、List、Card、Message、Morph、View 的动作集不同
- agent 必须被精细授权
- 授权变化必须可审计

## 2. 基本原则

### 2.1 授权主体 SHOULD 是稳定 principal

grant 的 `issuer` 与 `subject` SHOULD 使用 DID。

Handle、邮箱、域名用户名等人类可读标识 MUST NOT 作为权限主体主键。

协议允许条件化授权，但条件必须落到可验证 claim / attestation，而不是裸字符串匹配。

### 2.2 权限必须显式表达

不要依赖以下隐式假设：

- 进入 Space 就拥有全部能力
- 能编辑 Card 就一定能撤回 linked Room 里的别人的消息
- Room owner 天然拥有全量 Board/Card 管理权

### 2.3 权限判定基于当时有效的 capability 集

操作是否合法，应由该时点有效 grant 集决定。

### 2.4 DID 是主体，Claim 是条件

权限模型分三层：

```txt
Identity: DID
Human-readable binding: Handle
Authorization condition: Claim / Attestation
```

也就是说：

- DID 回答“这个 Actor 是谁”
- Handle 帮助人类发现和显示
- Claim / Attestation 回答“这个 Actor 当前是否满足某个权限条件”

例如 `alice.google.com` 或 `alice:google.com` 可以作为组织命名空间内的 handle，但不能直接作为 grant subject。组织成员权限应由 Google 签发的 `org_membership` claim 表达。

## 3. Grant 对象

示例：

```json
{
  "grant_id": "cx:grant:01JS0GR000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject": "did:web:agent.copy.example.com",
  "scope": {
    "space_ids": ["cx:space:01JS0SP000000000000000000"],
    "object_types": ["card", "morph"],
    "morph_types": ["run", "memory"],
    "facets": ["stateful", "assignable"],
    "actions": [
      "cx.card.read",
      "cx.card.update",
      "cx.morph.read",
      "cx.morph.update",
      "cx.run.create",
      "cx.memory.create"
    ]
  },
  "constraints": {
    "expires_at": "2026-04-30T00:00:00Z",
    "fields_write_allow": [
      "title",
      "body",
      "labels",
      "due_at"
    ],
    "max_delegation_depth": 0
  }
}
```

### 3.1 条件化 Grant

Grant 的 `subject` 可以是具体 DID，也可以是条件选择器。

具体 DID grant：

```json
{
  "subject": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "constraints": {
    "requires_claims": [
      {
        "claim_type": "org_membership",
        "issuer": "did:web:google.com",
        "organization": "did:web:google.com",
        "status": "active"
      }
    ]
  }
}
```

条件化 grant：

```json
{
  "subject": {
    "kind": "condition",
    "requires_claims": [
      {
        "claim_type": "org_membership",
        "issuer": "did:web:google.com",
        "organization": "did:web:google.com",
        "status": "active"
      }
    ]
  }
}
```

两者区别：

- 具体 DID grant：授权某个 Actor，但要求它在操作时仍满足条件
- 条件化 grant：授权所有满足条件的 Actor

条件化 grant MUST 明确 claim issuer、claim type、有效状态和适用资源范围。节点 MUST NOT 仅凭 handle 字符串后缀、邮箱域名或显示名判断条件成立。

## 4. Resource Selector

Contrix v1 支持以下 `kind`：

- `space`
- `room`
- `board`
- `list`
- `card`
- `message`
- `morph`
- `object`
- `relation`
- `event`
- `actor`
- `view`
- `schema`
- `policy`
- `object_type:<type>`
- `morph_type:<type>`
- `relation_kind:<type>`
- `view`
- `run`
- `memory`
- `schema`
- `policy`
- `invite`
- `read_marker`

## 5. 动作集合

动作名称与 `operations-sync.md` 中的事件 kind 对齐，使用 `cx.<domain>.<action>` 点分记法。通配符 `cx.<domain>.*` 表示该域的管理权限。

### 5.1 通用动作

- `cx.space.discover`
- `cx.object.read`
- `cx.object.read_metadata`
- `cx.object.read_content`
- `cx.object.archive`
- `cx.object.restore`

### 5.2 看板与对象动作

- `cx.board.create`
- `cx.board.update`
- `cx.board.archive`
- `cx.list.create`
- `cx.list.update`
- `cx.list.reorder`
- `cx.card.create`
- `cx.card.read`
- `cx.card.update`
- `cx.card.archive`
- `cx.card.move`
- `cx.card.reorder`
- `cx.card.link_room`
- `cx.card.unlink_room`
- `cx.card.set_primary_room`
- `cx.relation.create` (assigned_to、contains 等)
- `cx.container.move_item` (通用 container / collection 模型的 item 移动)
- `cx.container.rebalance`
- `cx.relation.*`
- `cx.attachment.*`
- `cx.view.*`

看板拖拽权限 SHOULD 优先使用 `cx.card.move`、`cx.card.reorder`、`cx.list.reorder` 等标准对象 action。需要通用 collection profile 时，才使用 `cx.container.move_item`、`cx.container.rebalance`，并结合 `relation_kind_allow`、`allowed_from_container_refs`、`allowed_to_container_refs`、`allowed_view_refs` 和字段写入约束表达。实现 SHOULD 避免直接授予宽泛的 `cx.relation.*`。

### 5.3 会话动作

- `cx.event.read`
- `cx.room.create`
- `cx.room.update`
- `cx.room.member`
- `cx.room.archive`
- `cx.message.create`
- `cx.reaction.add`
- `cx.message.update` (任意消息) / `cx.message.update.own` (仅自己)
- `cx.message.redact` (任意消息) / `cx.message.redact.own` (仅自己)
- `cx.room.*`

### 5.4 Run 与 Memory 动作

- `cx.run.create`
- `cx.run.update`
- `cx.memory.create`
- `cx.memory.confirm`
- `cx.memory.invalidate`
- `cx.memory.curate`

### 5.5 管理动作

- `cx.space.admin`
- `cx.board.admin`
- `cx.room.admin`
- `cx.schema.*`
- `cx.capability.*`
- `cx.policy.*`
- `cx.invite.*`

### 5.6 服务动作

- `cx.sync.*`
- `cx.index.*`
- `cx.blob.*`

### 5.7 人类界面与个人状态动作

- `cx.read.marker`
- `cx.notification.read`
- `cx.notification.ack`
- `cx.invite.accept`

### 5.8 社交动作

- `cx.social_post.create`
- `cx.social_post.reply`
- `cx.social_post.react`
- `cx.social_post.repost`
- `cx.social_post.quote`
- `cx.relation.create` (follows 关系)
- `cx.relation.*` (followers 管理)
- `cx.social_circle.*`
- `cx.audience_policy.*`

## 6. Constraints

Contrix v1 支持：

- `expires_at`
- `not_before`
- `fields_write_allow`
- `fields_write_deny`
- `object_type_allow`
- `morph_type_allow`
- `facet_allow`
- `memory_kind_allow`
- `allowed_room_refs`
- `allowed_board_refs`
- `allowed_list_refs`
- `allowed_card_refs`
- `allowed_view_refs`
- `relation_kind_allow`
- `allowed_from_container_refs`
- `allowed_to_container_refs`
- `wip_limit_override`
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

建议最小结构：

```json
{
  "claim_id": "cx:claim:01JS0CLM00000000000000000",
  "issuer": "did:web:google.com",
  "subject": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "claim_type": "org_membership",
  "claims": {
    "organization": "did:web:google.com",
    "status": "active",
    "roles": ["employee", "engineer"],
    "handle": "alice.google.com"
  },
  "not_before": "2026-04-01T00:00:00Z",
  "expires_at": "2026-05-01T00:00:00Z",
  "revocation_ref": "cx:event:01JS0RVK0000000000000000",
  "proof": {
    "type": "DataIntegrityProof",
    "verification_method": "did:web:google.com#key-1",
    "signature": "base64url..."
  }
}
```

Contrix v1 支持的 claim 类型：

- `verified_handle`
- `verified_email_domain`
- `org_membership`
- `org_role`
- `employment_status`
- `guardian_relationship`
- `protected_actor_status`
- `agent_controller`
- `device_trust`
- `mfa_level`
- `risk_level`
- `certification`

Claim 验证至少要求：

1. `issuer` 是当前 Space / Policy 信任的 claim issuer
2. `subject` 与当前 actor DID 一致，或符合被验证的关系语义
3. proof 签名有效
4. 当前时点在 `not_before` 与 `expires_at` 范围内
5. claim 未被 revoke
6. claim 内容满足 grant 的 `requires_claims`

### 7.1 Handle Binding Claim

Handle 可以作为 claim 的字段，但不能作为权限主键。

例如：

```json
{
  "claim_type": "verified_handle",
  "issuer": "did:web:google.com",
  "subject": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "claims": {
    "handle": "alice.google.com",
    "namespace": "google.com",
    "status": "active"
  }
}
```

当该 handle 无法验证、过期或被组织撤销时，依赖该 claim 的权限自然失效。

但是历史 Event 的 `actor_id` 仍然指向 DID，不会因为 handle 被回收而指向新人。

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

- accountability 不等于 capability
- owner / guardian / controller 不会自动把自己的权限传给 subject
- subject 要执行操作，仍然必须命中显式 grant
- 高风险动作 MAY 要求 responsible / guardian / controller approval
- Event SHOULD 记录 grant、delegation chain、approval 证据和 run 上下文

### 8.1 Approval Constraint

当 grant 带有审批约束时，subject 不能直接让目标操作生效。

示例：

```json
{
  "constraints": {
    "approval_required": true,
    "approval_mode": "before_commit",
    "approval_actor_refs": [
      "did:web:alice.example.com"
    ],
    "approval_relation": "controller"
  }
}
```

`approval_mode` v1 取值：

- `before_commit`：审批先发生，目标 Event 才能进入有效集合
- `proposal_then_approve`：subject 只能创建 proposal，审批后由系统或审批人产生目标 Event
- `after_commit_review`：允许先执行，但必须进入审计/复核队列

`approval_relation` v1 取值：

- `responsible`
- `controller`
- `guardian`
- `space_admin`
- `custom`

未成年人或受保护主体相关操作，若 policy 要求 guardian approval，节点 MUST 校验对应 approval 证据。

### 8.2 Proposal 模式

高风险操作建议使用 proposal 模式：

```txt
actor -> proposal.created
guardian/controller -> proposal.approved
system/human -> card.updated 或 morph.updated
```

这样 agent 或受限 Actor 可以提出意图，但不会直接修改高风险状态。

## 9. Agent 安全授权

给 agent 授权时 SHOULD 默认：

- 只授予明确 Space / Room / Board / Card / Morph / View 范围
- 只授予所需动作
- 只授予有限时效
- 只授予允许的对象种类
- 尽量限制可写字段与可写 memory 类型
- 要求必要的 controller / responsible actor approval

高风险模式包括：

- 给 agent 长期全 Space 管理权
- 让 agent 直接继承 human owner 全权限
- 不设过期时间
- 不保留 run 审计链
- 不记录 responsible / controller / operator
- 高风险操作不需要 approval

## 10. Delegation

委托表示 subject 可以将其能力的一部分再授予第三方。

若 `max_delegation_depth = 0`，则不可继续委托。  
若大于 0，则：

- 每次再授权 MUST 递减深度
- 再授权不得扩大原始资源范围和动作范围
- 委托链 MUST 可验证

## 11. 有效权限集合

Contrix v1 采用 **allow-grant + explicit revoke** 模型。

也就是说：

- 协议层没有通用 `deny` grant
- 有效权限集合是“所有当前有效 grant 的并集”
- revoke 通过显式 Operation 把 grant 从有效集合移出

部署层 MAY 叠加本地 deny policy，但那不属于协议级互操作语义。

## 12. Revocation

撤销必须是显式操作，而不是删除 grant 记录。

示例：

```json
{
  "type": "cx.capability.revoke",
  "body": {
    "grant_ref": "cx:grant:01JS0GR000000000000000000",
    "reason": "contract ended"
  }
}
```

## 13. Invite、通知与已读状态

这些人类友好能力必须进入权限模型，而不是留给产品私有后门：

- 创建 / 取消 invite 需要 `manage_invites`
- 接受发给自己的 invite 需要 `accept_invite`
- 写入自己的 `read_marker` 需要 `write_read_markers`
- 读取 notification 需要 `read_notifications`
- `ack_notifications` 只应影响自己的派生 inbox 状态

其中：

- `invite` 不等于 grant
- `notification` 是派生对象，但其可见性仍受底层 source object ACL 约束
- `read_marker` 默认是 owner-private state

## 14. Role 只是 bundle

产品层可以提供：

- `space_admin`
- `board_manager`
- `contributor`
- `observer`
- `room_moderator`
- `agent_writer`

但这些 role 在协议层只是 capability bundle，不是主语义。

## 15. 读权限与可发现性

读权限不只是“能不能 fetch 内容”，还包括：

- 能否发现对象存在
- 能否看到消息历史
- 能否看到被撤回消息的元信息
- 能否读取附件内容

初版至少区分：

- `discover`
- `read_metadata`
- `read_content`
- `read_history`

## 16. 会话场景下的权限建议

Contrix v1 至少区分：

- 普通发送消息
- 编辑自己的消息
- 编辑任意消息
- 撤回自己的消息
- 撤回任意消息
- 管理 Room、Room member、Card-linked Room

这能避免把“撤回别人的消息”错误地和“能发消息”混成一种权限。

## 17. 决策执行位置

权限检查不应只在客户端发生。

权限检查 MUST 至少在以下位置执行：

- client 预检查
- repo 接收写入时
- Sync Service 分发前
- index 返回查询前
- blob store 下发内容前

## 18. 最小权限判定算法与性能优化

给定一个操作，节点理论上的判定全链路如下：

1. 解析 actor DID
2. 验证签名链
3. 查找当时有效 grant 集
4. 展开 delegation：**必须包含死循环检测 (Cycle Detection)**。推演引擎 MUST 维护一个 `visited_grant_ids` 栈，当发现当前 grant ID 已存在于栈中时，MUST 立即阻断并返回 `deny`，防止恶意构造的环形委托耗尽节点资源。
5. 判断 resource selector 是否覆盖 target
6. 判断 action 是否匹配
7. 判断 constraints 是否满足
8. 若 grant 或 constraint 要求 claim，拉取并验证 claim / attestation
9. 判断 claim issuer 是否可信
10. 判断 claim 是否有效、未过期、未撤销
11. 若需要 approval，校验 responsible / guardian / controller approval 证据
12. 应用 revoke 和 superseding 规则

若多个 grant 同时命中，建议：

- 先按 resource selector 取覆盖目标的 grant
- 再做 action 并集
- 再用 constraints 取交集或更严格约束
- 最后应用 revoke、过期、delegation depth、claim、approval 等裁剪规则

### 18.1 高频交互的 O(1) 快速路径 (Fast Path)

在“聊天消息收发”或“卡片状态拖拽”等高频交互场景下，每一步操作都执行上述 12 步深层推演将导致极其严重的性能瓶颈。因此，节点实现 SHOULD 引入 **Capability 快照缓存 (Authz Snapshot Bitmap)**：

1. **预计算**：基于当前特定的因果前沿 (Causal Frontier)，Sync Service 或 Index 节点针对活跃 Actor 预计算出针对特定目标（如当前 Room、Board 或 Card）的有效权限位图 (Permission Bitmap)。
2. **快速命中**：对于后续提交的纯业务 Operation（如 `send_message`, `react`, `card.update`），只要 Space 内没有发生新的 `cx.capability.*` 授权操作（或相关 Claim 撤销），节点直接查询 Bitmap 缓存即可，将 O(N) 的深层权限推演降维为 O(1)。
3. **缓存失效与回滚**：当发生乱序操作、离线回补导致因果前沿包含新的授权变更或过期触发时，受影响的快照缓存将自动失效，并在下一次被访问时或后台任务中触发重建。

## 19. 设计决定

Contrix v1 固定：

- 权限采用 capability 模型
- 看板、会话、memory、run 都使用统一 grant 体系
- `edit_own_message` 与 `redact_any_message` 分开
- invite / notification / read marker 进入统一 capability 体系
- 协议级语义采用 allow-grant + explicit revoke
- agent 使用窄权限、短时效、可审计授权
- accountable Actor 是通用授权对象，覆盖 agent、未成年人、托管账号和自动化主体
- owner / guardian / controller 不导致权限自动继承
- 高风险动作支持 approval constraint 与 proposal 模式
- grant 主体使用 DID 或 condition selector，不使用 handle 作为权限主键
- handle 可以作为 claim 字段，但权限判断必须基于可验证 claim / attestation
- 组织成员权限使用 `org_membership` / `org_role` 等 claim 表达
- claim 失效、过期或撤销会让依赖它的条件化权限自然失效

## 20. 规范性收敛

以下授权事项在 v1 中按本节和引用文档执行，不再作为开放问题：

- Resource selector 语法由 `grant-constraint-schema.md` 固定。selector MUST 显式声明 resource kind、id / pattern、Space scope 和是否允许子资源；默认不递归、不跨 Space。
- Constraint schema 由 `grant-constraint-schema.md` 固定。未知 constraint 在授权判定中 MUST fail closed，除非 grant 明确标注该 constraint 为 non-critical hint。
- 多个 grant 命中时，允许动作取并集，但约束按最严格规则相交；过期、撤销、delegation depth、claim 失效、approval 未满足和 policy deny 均优先于 allow。
- Moderation policy 与 capability 的关系固定为：capability 先给出基础可做，moderation / policy server 再给出 `allow`、`deny`、`quarantine`、`require_review` 或 `soft_fail`。Moderation policy 不得凭空授予 capability。
- Approval proof 与 proposal 状态机由本文件第 11 节、`event-auth-state-resolution.md` 和 `capability-conformance-vectors.md` 固定。高风险动作缺少 approval 时 MUST 进入 proposal / review / quarantine 路径，不得直接生效。
- Accountable Actor 默认 policy profile：agent、未成年人、托管账号和自动化主体 MUST 声明 `responsible_party`、可撤销 controller、审计范围和最大 delegation depth；缺失时只能获得显式低风险、短时效 grant。
- Claim / attestation envelope 使用 `data-structures.md` 的 Proof、`identity-handles.md` 的 claim / VC 规则和 `progressive-disclosure.md` 的 presentation 规则。依赖 claim 的授权 MUST 验证 issuer、audience、subject、有效期、撤销状态和最小披露范围。
- Condition selector 只能匹配可验证 claim / attestation / VC，不能匹配未签名目录结果、客户端 UI 标签、handle 文本或服务器本地角色缓存。
- Trusted claim issuer registry 来自 Space policy、Organization DID governance 或 explicit grant。Claim revocation 查询面 MUST 支持 fail-closed：无法确认 revocation status 且该 claim 是授权必要条件时，不得 allow。
