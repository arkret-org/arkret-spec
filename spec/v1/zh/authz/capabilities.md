---
title: Capability Model
---

## 1. 目标

Contrix 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- `flow`、`message`、`space`、`morph`、`view` 的动作集不同。
- Flow 的 `synthesis` 与 `discussion` track 共享父 Space 的 access；需要让 discussion 拥有独立 access 域时升级到 child Space (`Flow.discussion_space_ref`)。
- agent 必须被精细授权。
- 授权变化必须可审计。

## 2. 基本原则

### 2.1 授权主体 SHOULD 是稳定 principal

grant 的 `issuer` 与 `subject` SHOULD 使用 DID。

Handle、邮箱、域名用户名等人类可读标识 MUST NOT 作为权限主体主键。

### 2.2 权限必须显式表达

不要依赖以下隐式假设：

- 进入 Space 就拥有全部能力。
- 能编辑 Flow synthesis 就一定能在 discussion 里发消息，除非有效 access policy 明确继承并授予该动作。
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

ID 语义：

- `cx:grant:<ulid>` 是签名 Capability Grant object 的规范 ID，`cx.schema.capability.v1` 的 `id`、grant reference 和 revoke payload 均使用它。
- `cx:capability:<ulid>` 只表示抽象 capability definition 引用；不得作为签名 grant object ID 使用。

示例：

```json
{
  "id": "cx:grant:01js0gr0000000000000000000",
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
      "fields_write_allow": ["title", "summary", "body", "fields.status"]
    }
  ],
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:acme.example.com#device-1",
      "payload_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "..."
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
- `place`
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
- `notification`
- `read_marker`
- `blob`

资源选择器应把 Place（`kind=board/list/...`）、Flow track、Morph type 和 Relation kind 表达为 canonical resource selector + typed constraint，而不是把它们当成新的 selector kind。Flow 的业务语义通过 schema/profile、`fields`、Relation、labels、Morph type 或 facet 约束表达，不放在顶层字段上。

## 5. 动作集合

动作名称与标准 event kind / operation id 的语义对齐，使用 `cx.<domain>.<action>` 点分记法。Wire 层 `actions[]` 字段 MUST 是具体动作字符串；**不接受任何 wildcard / segment 通配**（含 `*`、`cx.<domain>.*`、`cx.<domain>.<sub>.*`）。`capability-grant.schema.json` 已用 pattern 静态拒绝 wildcard。

机器可读的 canonical 动作集（含 `risk_tier`、`required_constraints`、`target_event_kinds`、`profile`）MUST 来自 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json)；本节的散文枚举只是该 registry 的 human-readable 镜像，新增 / 修改动作 MUST 先改 `contract-catalog.json` 的 `capability_action_registry` 节并跑 `tools/artifact_pipeline.py generate`，再回流到本节。

裸名动作（例如 `space.upgrade` 或 `space.hierarchy.manage`）一律不接受。`cx.space.admin` 覆盖普通 Space 管理动作，但不自动覆盖 E2EE key export、legal hold bypass 或审计降级——后者必须在 grant `actions[]` 中显式列出对应 high-risk 动作。

### 5.1 通用动作

- `cx.space.discover`
- `cx.space.create`
- `cx.space.update`
- `cx.space.lifecycle.archive`
- `cx.space.lifecycle.freeze`
- `cx.space.lifecycle.tombstone`
- `cx.space.lifecycle.destroy`
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
- `cx.flow.move`
- `cx.flow.reorder`
- `cx.flow.track.enable`
- `cx.flow.track.disable`
- `cx.flow.track.update`
- `cx.flow.track.set_primary`
- `cx.relation.create`
- `cx.relation.update`
- `cx.relation.delete`
- `cx.place.create`
- `cx.place.update`
- `cx.place.parent`
- `cx.place.archive`
- `cx.place.tombstone`
- `cx.container.move_item`
- `cx.container.rebalance`
- `cx.view.create`
- `cx.view.update`
- `cx.view.reconcile`

Flow 权限只覆盖 Flow 自身字段、track 配置和 position / relation 管理。Message 正文权限按有效 Space 判断：未设 `discussion_space_ref` 时使用父 Space 的 capability；设了 `discussion_space_ref` 时使用 child Space 的 capability，与父 Space 独立。

### 5.3 Discussion 与消息动作

- `cx.event.read`
- `cx.message.create`
- `cx.message.revise`
- `cx.message.revise.own`
- `cx.message.redact`
- `cx.message.redact.own`
- `cx.reaction.add`
- `cx.reaction.remove`
- `cx.flow.track.read`
- `cx.flow.track.admin`

### 5.4 管理动作

- `cx.space.admin`
- `cx.space.hierarchy.manage`
- `cx.space.upgrade`
- `cx.space.moderate`
- `cx.flow.admin`
- `cx.schema.define`
- `cx.schema.update`
- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.derived`
- `cx.capability.revoke`
- `cx.policy.manage`
- `cx.policy.set`
- `cx.policy.rule`
- `cx.policy.action`
- `cx.invite.create`
- `cx.invite.cancel`
- `cx.invite.third_party`
- `cx.invite.claim`
- `cx.invite.revoke`
- `cx.approval.vote`
- `cx.moderation.decision`（写入 anchored moderation state cell；详见 [`policy-server.md` §7.1](./policy-server.md)）
- `cx.moderation.decision.lift`（解除已 anchored 的 moderation 决策）

### 5.5 服务动作

- `cx.events.query`
- `cx.events.subscribe`
- `cx.sync.account`
- `cx.sync.describe`
- `cx.sync.get_snapshot_head`
- `cx.blob.upload`
- `cx.blob.get`
- `cx.blob.head`
- `cx.call.configure_media_service`
- `cx.mls.genesis`
- `cx.mls.proposal`
- `cx.mls.commit`
- `cx.mls.welcome`
- `cx.mls.keypackage`
- `cx.audit.accessed`
- `cx.audit.query`
- `cx.audit.export`

v1 不再注册独立的 `cx.mls.epoch` event；每个 group 的当前 epoch 由 winner `cx.mls.commit.next_epoch` 直接表达，没有"推进 epoch"这个独立可授权动作。

Audit action 只授权受控审计代理执行“先记录后解密”、读取审计视图或导出审计材料。若 Audit Agent 已经是 MLS group 成员，持有 epoch key 本身不受 capability 系统密码学约束；Space policy 必须同时声明 auditable E2EE profile、审计代理身份、plaintext-visible service disclosure、成员可见提示和 `cx.audit.accessed` 写入要求。

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
- `space_kind_allow`
- `place_kind_allow`
- `morph_type_allow`
- `facet_allow`
- `allowed_flow_refs`
- `allowed_space_refs`
- `allowed_view_refs`
- `allowed_tracks`
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

上表中的扁平名称是 `constraint-schema.md` 中 typed constraint 对象的 shorthand 别名。完整约束结构和求值规则以 `constraint-schema.md` 为准。

`discussion` 不是独立资源类型。需要限制 discussion track 时，使用 `object_type_allow=["flow"]` 和 `allowed_tracks=["discussion"]`；不得引入按 track profile 名称授权的 v1 grant 字段。`tracks[].profile` 只是 Flow track 的语义/profile hint，不能单独授予读取、发送或成员权限。

Facet 只在 grant 显式包含 `facet_allow` / `facet_deny` 这类 typed constraint 时作为范围收窄条件参与第 7 步 constraints 判断；未声明 facet constraint 的 grant 不会因为目标对象具有 `stateful`、`assignable` 或其他 facet 而自动允许或自动拒绝。`facet=stateful` 不引入独立授权动作：修改 Morph `state` 仍必须命中 `cx.morph.update` 或 profile 注册的更具体 action、目标 resource selector、`morph_type_allow`、字段写约束、schema state transition policy 和其他有效 constraints。若 grant 允许 `cx.morph.update` 且没有字段/类型/策略拒绝，缺少 `facet_allow=["stateful"]` 本身不得成为拒绝理由；若 grant 显式声明 `facet_allow` 且目标 facets 不匹配，则 constraint 不满足。

| 扁平名称 | Typed `constraint_type` | `subtype` | 对应字段 |
|----------|------------------------|----------|----------|
| `expires_at` | `temporal` | — | `expires_at` |
| `not_before` | `temporal` | — | `not_before` |
| `fields_write_allow` | `field_access` | — | `fields_write_allow` |
| `fields_write_deny` | `field_access` | — | `fields_write_deny` |
| `space_kind_allow` | `type_restriction` | — | `space_kind_allow` |
| `place_kind_allow` | `type_restriction` | — | `place_kind_allow`（限定 Place 的 kind，例如 board / list / swimlane）|
| `morph_type_allow` | `type_restriction` | — | `morph_type_allow` |
| `facet_allow` | `type_restriction` | — | `facet_allow` |
| `allowed_flow_refs` | `scope_limitation` | — | `allowed_flow_refs` |
| `allowed_space_refs` | `scope_limitation` | — | `allowed_space_refs` |
| `allowed_view_refs` | `scope_limitation` | — | `allowed_view_refs` |
| `allowed_tracks` | `scope_limitation` | — | `allowed_tracks` |
| `relation_kind_allow` | `scope_limitation` | — | `relation_kind_allow` |
| `allowed_from_container_refs` | `scope_limitation` | — | `allowed_from_container_refs` |
| `allowed_to_container_refs` | `scope_limitation` | — | `allowed_to_container_refs` |
| `visibility_allow` | `confidentiality` | `visibility` | `visibility_allow` |
| `blob_max_bytes` | `quota` | `resource` | `blob_max_bytes` |
| `encryption_required` | `confidentiality` | `encryption` | `encryption_required` |
| `message_edit_window` | `temporal` | `edit_window` | `message_edit_window` |
| `max_delegation_depth` | `delegation_control` | — | `max_delegation_depth` |
| `rate_limit` | `quota` | `rate` | `max_operations`, `period` |
| `approval_required` | `claim_based` | `approval` | `approval_required` |
| `approval_mode` | `claim_based` | `approval` | `approval_mode` |
| `approval_actor_refs` | `claim_based` | `approval` | `approval_actor_refs` |
| `approval_relation` | `claim_based` | `approval` | `approval_relation` |
| `accountability_required` | `claim_based` | `accountability` | `accountability_required` |
| `guardian_approval_required` | `claim_based` | `accountability` | `guardian_approval_required` |
| `controller_approval_required` | `claim_based` | `accountability` | `controller_approval_required` |
| `requires_claims` | `claim_based` | `claim` | `requires_claims` |
| `trusted_claim_issuers` | `claim_based` | `claim` | `trusted_claim_issuers` |
| `claim_refresh_required` | `claim_based` | `claim` | `claim_refresh_required` |
| `claim_max_age` | `claim_based` | `claim` | `claim_max_age` |

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
- 尽量限制可写字段、可写 track 和可写 Morph 类型。
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
  "kind": "cx.capability.revoke",
  "payload": {
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
- 开启或关闭 discussion track。
- 管理父 Space 或 `discussion_space_ref` child Space 的成员。
- 普通发送消息。
- 编辑自己的消息。
- 编辑任意消息。
- 撤回自己的消息。
- 撤回任意消息。
- 切换 primary track。

这能避免把"能改 Flow"和"能进入 discussion"混成一种权限——普通 discussion 时按父 Space capability 判断，独立 child Space 时按 child Space capability 判断。

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

Facets 不属于独立授权输入。算法不得在上述步骤之外读取 Morph facets、View renderer 或 track profile 来授予、拒绝或升级权限。第 7 步若检查 Space schema、Morph profile 或 reducer policy，只能读取其中明确声明的字段规则、状态机、RelationProfile 或 policy 条件；不得把 facets 本身当作状态机、动作或授权规则。

### 18.1 高频交互的 O(1) 快速路径

在“discussion 消息收发”或“Flow 状态拖拽”等高频交互场景下，声称支持主客户端或 Principal Server profile 的实现 SHOULD 提供 capability 快照缓存或语义等价 fast path。

高频 fast path 典型事件：

- `cx.message.create`
- `cx.reaction.add`
- `cx.flow.update`
- `cx.flow.move`
- `cx.flow.reorder`

Fast path 只能缓存基础 capability 是否允许。Moderation / Policy Server 的 `deny`、`quarantine`、`require_review`、rate limit、legal hold 和 abuse policy 仍 MUST 在写入接收、分发和查询返回前执行。

Capability fast path cache MUST 绑定确定性授权状态，而不是只绑定 subject/action/resource 三元组。每个 cache entry 至少包含：

- `space_id`、scope / track / object selector、subject DID、action 和 constraint profile。
- `auth_state_hash`：由当前 accepted capability grant/revoke、membership、policy、必要 claim status、device/session control checkpoint 和相关 state event canonical digest 计算出的确定性 hash。
- `auth_frontier`：参与该 hash 的 state event head set 或 snapshot frontier。
- 命中的 grant event id、revoke tombstone / superseding event id（如有）、claim status evidence 和过期时间。

规则：

- 任何影响该 scope 的 accepted grant、revoke、membership、policy、claim status、device/session revoke 或 Space lifecycle 变化，MUST 立即把对应 cache entry 标记 stale。"立即"指节点本地 reducer 在 `apply_anchor` 完成的同一事务边界内；分布式 fanout 的传播延迟由 §18.2 freshness 检查兜底，**不得**作为延迟标记 stale 的理由。
- **Moderation state cell 与 cache 的关系**：anchored moderation decision（写入 `cx.component.moderation_state.v1`，见 [`policy-server.md` §7.1](./policy-server.md)）**默认不**触发 capability cache invalidation——moderation 是 deny / quarantine 后置层，不是 capability 来源。但若 grant 的 constraint 显式声明 `depends_on_moderation_state=true`（典型场景：moderator role grant 依赖被 moderation cell 标记的 actor 不在其中），则该 cell 的变化 MUST 触发对应 grant cache 失效。grant constraint 默认 `depends_on_moderation_state=false`。
- Cache entry 的 `auth_state_hash` 与当前 accepted auth state hash 不一致时，MUST 回退到完整授权判定；不得继续用旧 grant 允许新写入。
- 已被 GC 的 grant 仍必须保留足以验证 revoke 的 tombstone、revocation index、snapshot witness 或 state root 证据。实现不得因为 grant payload 已压缩或归档而让旧 cache 重新生效。
- `partial_auth_state`、soft-failed auth chain 或无法确认 revoke freshness 的状态不得生成 allow cache；只能生成 deny / unknown / pending 诊断。
- 多 Principal Server 部署中，cache TTL 只是额外保险，不得替代 revoke fanout、frontier 对账和 `auth_state_hash` 失效。

### 18.2 撤销新鲜度 (Revocation Freshness)

授权判定要回答两个问题：①当前已同步的 frontier 下，subject 是否被 grant？②该 frontier 是否足够新，以至于"还没看到的 revoke"概率足够低？open_set / threshold anchor profile 下 ②不能凭单节点状态独立断言——必须显式建模 freshness 不确定性。

**Freshness 状态分级**：节点对自己当前 frontier 的新鲜度判定 MUST 落入以下三个状态之一：

- `fresh`：节点已观察到 anchor frontier 更新时间在 `freshness_required_ms` 窗口内，或持有 ≥1 受信 anchorer / witness 在该窗口内签发的 frontier attestation。
- `stale`：上一次 anchor frontier 更新或受信 attestation 超出 `freshness_required_ms` 窗口，但仍小于 `freshness_hard_limit_ms`。
- `unknown`：节点处于网络分区、frontier 来源不可达、anchorer 长时间无新签发，或本地时钟与受信时间源 drift 超出 `clock_skew_tolerance_ms`。

**`freshness_unknown` ≠ allow**：当判定的状态是 `stale` 或 `unknown` 时，节点 MUST 按动作风险等级强制降级，绝不能因"找不到 revoke 证据"就默认为"未撤销"：

| 动作风险等级 | `fresh` | `stale` | `unknown` |
| --- | --- | --- | --- |
| 高风险（`cx.space.lifecycle.destroy`、`cx.capability.revoke`、`cx.space.admin`、`cx.policy.manage`、E2EE key export、legal hold bypass、跨域 grant、sovereign export） | allow | **MUST fail closed**（`revocation_freshness_unknown`） | **MUST fail closed**（`revocation_freshness_unknown`） |
| 中风险（`cx.flow.update`、`cx.member.state`、`cx.invite.create`、跨 Space relation 创建、policy_components 修改） | allow | allow + audit log + 异步 re-check | **MUST fail closed**，可携带 `retry_after_ms` |
| 低风险高频（`cx.message.create`、`cx.reaction.add`、`cx.read.marker`、`cx.flow.move`、`cx.flow.reorder`） | allow | allow + 加快后台 frontier 同步 | **本地 pending（不对外生效）**：客户端 MAY 在本地 UI 中乐观显示作者自己看到的状态，但 MUST NOT 把该 Move 同步给其他成员、不得 fanout、不得 push notify、不得进入 anchor pipeline 直到 freshness 恢复。frontier 恢复 fresh 后再做完整 re-validate；validate 失败的本地 pending Move MUST 静默丢弃，不写入 redaction（因为它从未 anchored）。 |

设计取舍：早期草案允许低风险 `unknown` allow + 后续重放校验。该设计在分区下会让恶意 actor 故意制造分区然后高频写入；即使后续 redaction 也已经污染过其他成员的 inbox / notification / 通话邀请。**v1 改为本地 pending 模式**：分区期间作者自己看得见自己的写入（保留 UX），但分区另一侧的成员看不到任何被分区动作影响的内容，分区恢复时被 invalidate 的 Move 直接丢弃，无副作用。

实现 MUST：

- 在 `server/describe.limits` 暴露 `freshness_required_ms`、`freshness_hard_limit_ms`、`clock_skew_tolerance_ms`，让客户端协商。默认值：高风险 `freshness_required_ms = 30_000`、`freshness_hard_limit_ms = 300_000`；中风险 `freshness_required_ms = 300_000`；clock_skew_tolerance_ms = 60_000。
- 在 `unknown` / `stale` 拒绝响应中返回 `freshness_state`、`last_known_frontier_age_ms`、`anchorer_status`、`retry_after_ms`，让客户端 UI 区分"被拒绝"和"暂时不能确认"。
- 客户端在低风险 `unknown` 模式下 MUST 在 UI 中标记本地 pending 写入为 `pending_local`（例如灰色发送中状态），并暴露"分区恢复后可能丢弃"的提示。
- 不得用 cache TTL 静默掩盖 `unknown` 状态。任何高风险动作 fast path 命中后，若 cache entry 的 `auth_state_hash` 对应的 frontier 已超出 `freshness_required_ms`，MUST 从 cache 降级回完整判定。
- 不得通过把高风险动作降级为中风险（例如把 `cx.capability.revoke` 标记为 "low_risk_followup"）来绕过本表。动作风险等级 MUST 由 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 的 `risk_tier` 字段声明，不接受 grant-side override。
- 单个分区窗口内允许的本地 pending 数量 MUST 限制（默认 ≤ 1000 / Space / 5 minutes），超过后客户端 SHOULD 转为离线模式提示用户，避免 pending 队列爆炸。

**默认 fail closed**：当实现无法确定动作风险等级、或动作来自尚未注册的 capability action 时，freshness 判定 MUST 默认按高风险处理（`stale` / `unknown` 即拒绝），而不是按低风险放行。这条 default 是为了让任何未来引入的高风险动作在进入 capability registry 前不会被旧实现误判为低风险路径。

## 19. 设计决定

Contrix v1 固定：

- 权限采用 capability 模型。
- Flow、discussion、agent 执行都使用统一 grant 体系；Flow track 完全继承父 Space access，独立访问域升级到 child Space。
- `cx.message.revise.own` 与 `cx.message.redact` 分开。
- invite / notification / read marker 进入统一 capability 体系。
- 协议级语义采用 allow-grant + explicit revoke。
- agent 使用窄权限、短时效、可审计授权。
- accountable Actor 是通用授权对象。
- owner / guardian / controller 不导致权限自动继承。
- grant 主体使用 DID 或 condition selector，不使用 handle 作为权限主键。

## 20. 规范性收敛

以下授权事项在 v1 中按本节和引用文档执行：

- Resource selector 语法由 `resource-selector-grammar.md` 和 `resource-selector.schema.json` 固定。
- Constraint schema 由 `constraint-schema.md` 固定。
- 多个 grant 命中时，允许动作取并集，但约束按最严格规则相交。
- Moderation policy 不得凭空授予 capability。
- Approval proof 与 proposal 状态机由本文件、`event-auth-state-resolution.md` 和 conformance vectors 固定。
- Claim / attestation envelope 使用 `data-structures.md` 的 Proof、`identity-handles.md` 的 claim / VC 规则与 §16 的 presentation 规则。
