---
title: Space Hierarchy
---

## 1. 目标

Contrix 支持 Space 之间形成层级或图状组织，用于表达组织、项目、频道、子项目、私有讨论、门户空间和知识库之间的关系。

本文件讨论 **Space-Space 层级**：Space 之间通过 `cx.space.child` / `cx.space.parent` 形成的父子关系。每个 Space 都是 security/sync/auth/E2EE 硬边界；层级只表示导航和可发现性，不表示自动权限继承。

**Place 层级不在本文范围内**。Place（Board / List / 等结构容器，`cx:place:`）是 Space 内部的轻量分组对象，永远不形成自己的 boundary。Place 之间嵌套（Board 包含 List）通过 Place 自身的 `parent_ref` + `cx.place.parent` reducer-input 表达，与 Space-Space 层级完全独立——见 [`space-and-place.md` §4](./space-and-place.md)。Place 嵌套必须在同一 Space 内；跨 Space 的引用走 Relation。

## 2. 设计原则

1. Space hierarchy 是有向图，不强制是树。一个 Space MAY 有多个 parent。
2. Child security-boundary Space 是独立 Space，拥有自己的 `space_id`、membership、policy、schema、history visibility 和 encryption epoch。
3. Parent 不得单方面把任意 Space 声明为 child。有效 parent-child 边 MUST 由双方确认，除非该 edge 被标记为 `unconfirmed_link`。
4. 权限、成员、历史可见性、加密密钥和配额默认不级联。
5. 任何级联都必须由 child Space 显式 opt-in，并且只能收窄，不能扩大 child 的本地安全边界。
6. 查询和同步遍历层级时，节点 MUST 对每个 Space 独立做授权检查。

## 3. 标准关系

以下 `cx.space.child` / `cx.space.parent` 关系仅用于 Space-Space 层级。Place 之间的父子嵌套不使用本文 schema，而是用 `cx.place.parent`（cas-register, bottom=reject）。

Space 层级使用 state event 表达，而不是普通对象 Relation。本文使用“边（edge）”表示有向图中的 parent-child 连接关系；对外 projection 字段统一使用 `edge_status` 表示该边的派生状态。

Parent 侧声明：

```json
{
  "kind": "cx.space.child",
  "payload": {
    "child_space_id": "cx:space:91085a00-8000-7000-8000-000000000000",
    "via": [
      "did:web:server.example"
    ],
    "order": "mV",
    "suggested": false,
    "canonical": true
  }
}
```

Child 侧确认：

```json
{
  "kind": "cx.space.parent",
  "payload": {
    "parent_space_id": "cx:space:cac3aba0-0400-7000-8000-000000000000",
    "via": [
      "did:web:server.example"
    ],
    "canonical": true
  }
}
```

`cx.space.child` 与 `cx.space.parent` 是兼容 Event kind；在 Move/Anchor/Lattice 状态中分别写入对应 cell family，subject 来自 `payload.child_space_id` 或 `payload.parent_space_id`。两类 payload 的 `status` 默认是 `active`；后续同 cell 的 Move 可用 `status="tombstoned"` 撤销该侧声明，或用 `status="rejected"` 表达该侧明确拒绝。`via` 只表示推荐的发现 / backfill 路由，不授予读取或写入能力。

如果同一操作者同时拥有 parent Space 与 child Space 的 `cx.space.hierarchy.manage` capability，客户端 MAY 在一个用户动作中连续提交两侧 state event。此时 UI 不需要额外的人工确认步骤；协议上的“双方确认”由 parent Space 中 accepted 的 `cx.space.child` 与 child Space 中 accepted 的 `cx.space.parent` 共同满足。若操作者只具备 parent 侧权限，客户端只能创建 `unconfirmed_link`，并等待 child 侧有权限 actor 接受或拒绝。

一条 parent-child 边只有在 parent 的 `cx.space.child` 与 child 的 `cx.space.parent` 同时 accepted 时，才是 confirmed 边。

两侧 state event 位于不同 Space 的 event chain，`prev_refs` 不要求跨 Space 直接连接。实现 MUST 通过各自 Space 的 accepted event、event digest、state key 和 auth refs 验证双方声明；需要把双方绑定成同一条边时，双方 content SHOULD 包含对侧 Space id、对侧层级 state event ref 或 edge nonce / digest commitment。缺少对侧可验证声明时，该边只能是 `unconfirmed_link`。

## 4. 层级边状态

层级边状态（`edge_status`）取值：

- `confirmed`：双方 state event 均 accepted，且两侧 payload `status` 均为 `active` 或未声明。
- `unconfirmed_link`：只有一侧声明，客户端 MAY 展示为外部链接，但不得自动展开。
- `rejected`：任一侧 payload `status="rejected"`，或 policy 明确拒绝。
- `tombstoned`：任一侧 payload `status="tombstoned"`，或 Space lifecycle / replacement 使该边失效。

`edge_status` 是 projection 输出字段，不是 `cx.space.child` / `cx.space.parent` payload 中必须持久化的字段。实现 MUST 从双方 accepted state event、两侧 payload status、policy 结果和 tombstone / replacement 状态派生该值。

客户端默认 hierarchy projection SHOULD 只返回 confirmed 边。需要显示外部引用时 MAY 返回 `unconfirmed_link`，但必须标记状态。

`unconfirmed_link` 没有功能性效力。它不得触发 inheritance policy、生效的 derived grant、成员同步、自动订阅、history visibility 展开、E2EE key share、配额继承或 policy cascade。Parent 侧已 accepted 的 `cx.space.child` 不会因为 child 迟迟未确认而自动撤销；它只保持为 parent Space 中的可审计声明，直到 parent tombstone / replace 该声明、child 确认、或 child / policy 明确拒绝。Projection 和 UI 可以展示 pending / rejected 状态，但授权和同步 MUST 按未确认处理。

## 5. 禁止隐式级联

以下内容 MUST NOT 因 parent-child 边自动级联：

- membership
- capability grant
- admin / moderation 权限
- history visibility
- E2EE group key / MLS epoch
- schema mutation
- policy server
- retention / legal hold
- notification rule
- Applet write permission

例如，Alice 是 parent Space 成员，不代表 Alice 自动能读取 child Space；Bob 是 parent Space 管理员，也不代表 Bob 自动能审核 child Space。

## 6. 显式继承策略

Child Space MAY 使用 `cx.space.inheritance_policy` 显式声明可继承项（Move 写入以 `payload.parent_space_id` 为 subject 的 inheritance policy cell，每个 parent 独立 cell）：

```json
{
  "kind": "cx.space.inheritance_policy",
  "payload": {
    "parent_space_id": "cx:space:cac3aba0-0400-7000-8000-000000000000",
    "inherits": {
      "membership": false,
      "capability_bundles": [
        "viewer",
        "commenter"
      ],
      "policy_rules": [
        "server_acl",
        "media_blocklist"
      ],
      "notification_defaults": true
    },
    "mode": "narrow_only",
    "max_depth": 1
  }
}
```

继承规则：

- `cx.space.inheritance_policy` 写入 `cx:cell:cx.component.space.inheritance_policy.v1:<parent_space_id>` 的 cell（cas-register, bottom=reject）；`cell_subject` 由 `payload.parent_space_id` 派生（每个 parent 独立 cell）。payload `status` 默认是 `active`；`status="tombstoned"` 表示 child 停止使用该 parent 的继承策略。
- `cx.space.inheritance_policy` 只有在目标 parent-child 边已 confirmed 后才可生效。若确认缺失、被拒绝、tombstoned 或无法在 backfill / snapshot 上限内验证，继承策略 MUST soft-fail 或视为 unset。
- `mode` MUST 为 `narrow_only`。继承只能收窄或附加限制，不能绕过 child 本地 policy。
- Child local deny / revoke / ban MUST 覆盖 inherited allow。
- 继承 capability MUST 在 child 中物化为 derived grant，且记录 parent grant、继承策略和有效 causal frontier。
- 继承 membership 只有在 `membership=true` 且 child join rule 允许时才生效；默认 false。
- `max_depth` 默认 1，MUST NOT 无限级联。

## 7. Capability 继承

继承授权使用 `cx.capability.derived`。Move 写入以 `payload.grant_id` 为 subject 的 derived capability cell：

```json
{
  "kind": "cx.capability.derived",
  "payload": {
    "grant_id": "cx:grant:aec076e6-8020-7000-8000-000000000000",
    "source_grant": "cx:grant:cac3abad-85dc-7600-8000-000000000000",
    "source_space_id": "cx:space:cac3aba0-0400-7000-8000-000000000000",
    "target_space_id": "cx:space:91085a00-8000-7000-8000-000000000000",
    "actions": [
      "cx.space.discover",
      "cx.object.read"
    ],
    "constraints": [
      {
        "constraint_type": "temporal",
        "effect": "allow",
        "expires_at": "2026-05-01T00:00:00Z"
      },
      {
        "constraint_type": "delegation_control",
        "effect": "allow",
        "inherited_depth": 1
      }
    ]
  }
}
```

`cx.capability.derived` MUST satisfy：

1. target Space 存在 confirmed parent 边。
2. child Space 有 accepted `cx.space.inheritance_policy`（subject=该 parent space id）。
3. derived grant 的 action/scope/expiry 不得宽于 source grant。
4. source grant 被 revoke 后，derived grant MUST 在其 causal 后继中失效（参见 `authz/event-auth-state-resolution.md` §8 委托链 revocation 传播规则）。
5. derived grant 不得再向下无限派生，除非下一级 child 也显式 opt-in 且未超过 `max_depth`。
6. `refs[]` MUST 同时包含两条 `role="authorized_by"` 条目：source grant 的 accepted `cx.capability.grant` 事件 id 与 target child 的 `cx.space.inheritance_policy`（subject=parent space id）事件 id。

> **reducer-only event**：`cx.capability.derived` 是 reducer 在满足上述 6 条规则时**自动生成**的派生 grant；它 **MUST NOT** 作为可被普通 actor 直接 grant 的 capability action 出现在任何 `cx.capability.grant.actions[]` 列表中。`capability.action.registry`（[`capabilities.md §5.4`](../authz/capabilities.md)）已显式将其从可授予 action 集合中排除。若 reducer 收到 `cx.capability.grant` 包含 `actions[] = ["cx.capability.derived"]`，MUST 以 `schema_violation` 拒绝。允许该 action 被直接 grant 等价于让任何持有 `cx.capability.grant` 的 actor 绕过 §7 全部 6 条 inheritance 检查直接发出派生授权——这是 inheritance policy bypass。

## 8. Schema and Policy Cascade

Schema MAY 通过继承复用，但 child MUST 记录实际生效 schema refs。父级 schema 更新不会自动改变 child 的 reducer 行为，除非 child 提交新的 `cx.space.schema` state event 接受该版本。

Policy 继承只适合以下收窄型规则：

- server ACL blocklist
- media blocklist
- retention upper bound
- maximum attachment size
- external federation deny list
- required policy server

以下 policy 不应从 parent 自动继承：

- allow join
- grant admin
- decrypt history
- lower retention below legal hold
- disable audit

## 9. History and Encryption

Child security-boundary Space 的历史可见性独立计算。Parent 成员不因层级关系获得 child 历史。Container Space 没有独立历史可见性；其对象历史按最近 security-boundary 祖先 Space 与具体 Flow track policy 计算。

E2EE 要求：

- 每个 encrypted Space MUST 有独立 MLS group。
- Parent MLS group key MUST NOT 用于解密 child。
- Child MAY 通过 invite / welcome flow 把 parent 成员加入 child MLS group，但这是显式 membership 变化。
- Archive/export 可以按 hierarchy 批量发起，但每个 Space 的 key、policy 和 authorization 独立验证。
- Place（Board / List 等结构容器）永远不创建 MLS group；Flow / Message 的 E2EE 永远绑定到所属 Space。Flow 通过 `discussion_space_ref` 引用 child Space 时，该 child Space 拥有独立 MLS group。

## 10. Query and Sync

Hierarchy 查询是客户端本地或可选受托 projection 语义，不要求远端 endpoint。

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `space_id` | query | `id` | required | 根 Space。 |
| `depth` | query | `int` | optional | 查询深度；服务端 MUST enforce 最大值。 |
| `include_unconfirmed` | query | `boolean` | optional | 是否包含未确认边。 |
| `include_edges` | query | `boolean` | optional | 是否返回独立 `edges` 列表；默认 MAY 只返回 `children`。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `root_space_id` | `id` | required | 根 Space ID。 |
| `root` | `object` | optional | 根 Space 摘要；无权限或本地只需要 ID 时 MAY 省略。 |
| `children` | `object[]` | required | 子 Space 摘要数组；每个 child entry MUST 包含 `space_id` 和 `edge_status`。 |
| `edges` | `object[]` | optional | 层级边列表；每条边 MUST 包含 `edge_status`。 |
| `next_cursor` | `cursor` | optional | 分页 cursor。 |
| `cycle_detected` | `boolean` | optional | 遍历是否因 cycle 被截断。 |

响应示例（非完整 schema）：

```json
{
  "root_space_id": "cx:space:cac3aba0-0400-7000-8000-000000000000",
  "children": [
    {
      "space_id": "cx:space:91085a00-8000-7000-8000-000000000000",
      "edge_status": "confirmed",
      "accessible": true,
      "summary": {
        "name": "Design",
        "avatar": "blob:..."
      }
    },
    {
      "space_id": "cx:space:91085b6c-076a-7380-8000-000000000000",
      "edge_status": "confirmed",
      "accessible": false,
      "lazy_link": true
    }
  ]
}
```

规则：

- Projection executor MUST 对每个 child 独立检查 read capability。
- 无权限 child 只能返回 `space_id`、`edge_status` 和 `lazy_link=true`，不得泄露名称、成员、Flow 摘要、Message 摘要或统计。
- `depth` MUST 有服务端上限。
- 遍历时发现 cycle，MUST 截断并返回 `cycle_detected=true`。
- Sync 不得默认订阅所有 descendants。客户端必须显式设置 `include_descendants` 或列出 child space ids。

## 11. Cycle Handling

Space hierarchy 是图，但 UI 层级遍历必须防循环。

节点在写入 confirmed 边时 SHOULD 检查是否产生 cycle。若无法完整检查，projection executor 在查询时 MUST 使用 visited set 截断。

Cycle 不应导致事件 reject，除非 Space policy 明确要求 acyclic hierarchy。默认行为是允许图状组织，但层级查询截断循环。

## 12. Archive and Deletion

Parent archive / tombstone 不自动 archive child。Child archive / tombstone 不自动修改 parent。

推荐流程：

1. Parent 提交 `cx.space.archive_proposal`，列出 affected children。
2. 每个 child 管理员独立批准或拒绝。
3. 被批准的 child 提交自己的 archive/tombstone event。
4. Parent 更新 child 边为 tombstoned。

强制级联删除非常危险，MUST 只允许在同一 controller、同一 retention policy 且 child 显式 opt-in 的受管层级中使用。

## 13. Applet and Portal Spaces

Portal Space MAY 被挂在组织、项目或 discussion-oriented Flow 所在 Space 下。Applet registration 的 namespace 命中不等于 parent Space 权限。

Applet 对 child Portal Space 写入仍需：

- confirmed parent/child 边，若业务要求。
- child Space 的 explicit capability。
- child Space 的 policy server / moderation 检查。
- E2EE 边界提示，若 bridge 到非 E2EE 外部系统。

## 14. 与 Matrix Space 的关系

Contrix 的 Space hierarchy 借鉴 Matrix `m.space.child` / `m.space.parent` 的双向确认经验，但区别是：

- Contrix security-boundary Space 是权限和对象图边界，不只是 room directory。
- Flow / Board Place / List Place / Message / Morph / Relation 仍然承载业务对象层级，不应把所有对象拆成 child security-boundary Space。
- 权限和加密默认不继承。
- 跨 Space 深度查询必须 Lazy Link，不能自动拼接泄露。
