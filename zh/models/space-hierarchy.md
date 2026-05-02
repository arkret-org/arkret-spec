# Space Hierarchy

## 1. 目标

Contrix 支持 Space 之间形成层级或图状组织，用于表达组织、项目、频道、子项目、私有讨论、门户空间和知识库之间的关系。

但 Space 仍然是复制、授权、schema、policy、membership、history visibility、加密和索引的硬边界。层级关系默认只表示导航和可发现性，不表示自动权限继承。

## 2. 设计原则

1. Space hierarchy 是有向图，不强制是树。一个 Space MAY 有多个 parent。
2. Child Space 是独立 Space，拥有自己的 `space_id`、membership、policy、schema、history visibility 和 encryption epoch。
3. Parent 不得单方面把任意 Space 声明为 child。有效 parent-child edge MUST 由双方确认，除非 edge 被标记为 `unconfirmed_link`。
4. 权限、成员、历史可见性、加密密钥和配额默认不级联。
5. 任何级联都必须由 child Space 显式 opt-in，并且只能收窄，不能扩大 child 的本地安全边界。
6. 查询和同步遍历层级时，节点 MUST 对每个 Space 独立做授权检查。

## 3. 标准关系

Space 层级使用 state event 表达，而不是普通对象 Relation。

Parent 侧声明：

```json
{
  "type": "cx.space.child",
  "state_key": "cx:space:ch11d010000000000000000000",
  "content": {
    "child_space_id": "cx:space:ch11d010000000000000000000",
    "via": ["did:web:server.example"],
    "order": "mV",
    "suggested": false,
    "canonical": true
  }
}
```

Child 侧确认：

```json
{
  "type": "cx.space.parent",
  "state_key": "cx:space:parent01000000000000000000",
  "content": {
    "parent_space_id": "cx:space:parent01000000000000000000",
    "via": ["did:web:server.example"],
    "canonical": true
  }
}
```

一个 edge 只有在 parent 的 `cx.space.child` 与 child 的 `cx.space.parent` 同时 accepted 时，才是 confirmed edge。

## 4. Edge 状态

层级 edge 状态：

- `confirmed`：双方 state event 均 accepted。
- `unconfirmed_link`：只有一侧声明，客户端 MAY 展示为外部链接，但不得自动展开。
- `rejected`：任一侧 policy 明确拒绝。
- `tombstoned`：任一侧删除或归档该 edge。

Index 在默认 hierarchy 查询中 SHOULD 只返回 confirmed edge。需要显示外部引用时 MAY 返回 unconfirmed link，但必须标记状态。

## 5. 禁止隐式级联

以下内容 MUST NOT 因 parent-child edge 自动级联：

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

Child Space MAY 使用 `cx.space.inheritance_policy` 显式声明可继承项：

```json
{
  "type": "cx.space.inheritance_policy",
  "state_key": "cx:space:parent01000000000000000000",
  "content": {
    "parent_space_id": "cx:space:parent01000000000000000000",
    "inherits": {
      "membership": false,
      "capability_bundles": ["viewer", "commenter"],
      "policy_rules": ["server_acl", "media_blocklist"],
      "notification_defaults": true
    },
    "mode": "narrow_only",
    "max_depth": 1
  }
}
```

继承规则：

- `mode` MUST 为 `narrow_only`。继承只能收窄或附加限制，不能绕过 child 本地 policy。
- Child local deny / revoke / ban MUST 覆盖 inherited allow。
- 继承 capability MUST 在 child 中物化为 derived grant，且记录 parent grant、继承策略和有效 causal frontier。
- 继承 membership 只有在 `membership=true` 且 child join rule 允许时才生效；默认 false。
- `max_depth` 默认 1，MUST NOT 无限级联。

## 7. Capability 继承

继承授权使用 `cx.capability.derived`：

```json
{
  "type": "cx.capability.derived",
  "state_key": "cx:grant:der1ved0100000000000000000",
  "content": {
    "source_grant": "cx:grant:parentv1ewer00000000000000",
    "source_space_id": "cx:space:parent01000000000000000000",
    "target_space_id": "cx:space:ch11d010000000000000000000",
    "actions": ["cx.space.discover", "cx.object.read"],
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

1. target Space 存在 confirmed parent edge。
2. child Space 有 accepted `cx.space.inheritance_policy`。
3. derived grant 的 action/scope/expiry 不得宽于 source grant。
4. source grant 被 revoke 后，derived grant MUST 在其 causal 后继中失效。
5. derived grant 不得再向下无限派生，除非下一级 child 也显式 opt-in 且未超过 `max_depth`。

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

Child Space 的历史可见性独立计算。Parent 成员不因层级关系获得 child 历史。

E2EE 要求：

- 每个 encrypted Space MUST 有独立 MLS group。
- Parent MLS group key MUST NOT 用于解密 child。
- Child MAY 通过 invite / welcome flow 把 parent 成员加入 child MLS group，但这是显式 membership 变化。
- Archive/export 可以按 hierarchy 批量发起，但每个 Space 的 key、policy 和 authorization 独立验证。

## 10. Query and Sync

Hierarchy 查询：

```http
GET /api/v1/index/space-hierarchy?space_id=<id>&depth=2&include_unconfirmed=false
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `space_id` | query | `id` | required | 根 Space。 |
| `depth` | query | `int` | optional | 查询深度；服务端 MUST enforce 最大值。 |
| `include_unconfirmed` | query | `boolean` | optional | 是否包含未确认 edge。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `root` 或 `root_space_id` | `object` 或 `id` | required | 根 Space 摘要或 ID。 |
| `children` | `object[]` | required | 子 Space 摘要数组。 |
| `edges` | `object[]` | optional | 层级边列表。 |
| `next_cursor` | `cursor` | optional | 分页 cursor。 |

响应示例（非完整 schema）：

```json
{
  "root_space_id": "cx:space:parent01000000000000000000",
  "children": [
    {
      "space_id": "cx:space:ch11d010000000000000000000",
      "edge_state": "confirmed",
      "accessible": true,
      "summary": {
        "name": "Design",
        "avatar": "blob:..."
      }
    },
    {
      "space_id": "cx:space:ch11dpr1vate00000000000000",
      "edge_state": "confirmed",
      "accessible": false,
      "lazy_link": true
    }
  ]
}
```

规则：

- Index MUST 对每个 child 独立检查 read capability。
- 无权限 child 只能返回 `space_id`、`edge_state` 和 `lazy_link=true`，不得泄露名称、成员、Room/Card 摘要、消息摘要或统计。
- `depth` MUST 有服务端上限。
- 遍历时发现 cycle，MUST 截断并返回 `cycle_detected=true`。
- Sync 不得默认订阅所有 descendants。客户端必须显式设置 `include_descendants` 或列出 child space ids。

## 11. Cycle Handling

Space hierarchy 是图，但 UI 层级遍历必须防循环。

节点在写入 confirmed edge 时 SHOULD 检查是否产生 cycle。若无法完整检查，Index 在查询时 MUST 使用 visited set 截断。

Cycle 不应导致事件 reject，除非 Space policy 明确要求 acyclic hierarchy。默认行为是允许图状组织，但层级查询截断循环。

## 12. Archive and Deletion

Parent archive / tombstone 不自动 archive child。Child archive / tombstone 不自动修改 parent。

推荐流程：

1. Parent 提交 `cx.space.archive_proposal`，列出 affected children。
2. 每个 child 管理员独立批准或拒绝。
3. 被批准的 child 提交自己的 archive/tombstone event。
4. Parent 更新 child edge 为 tombstoned。

强制级联删除非常危险，MUST 只允许在同一 controller、同一 retention policy 且 child 显式 opt-in 的受管层级中使用。

## 13. Applet and Portal Spaces

Portal Space MAY 被挂在组织、项目或 Room-oriented Space 下。Applet registration 的 namespace 命中不等于 parent Space 权限。

Applet 对 child Portal Space 写入仍需：

- confirmed parent/child edge，若业务要求。
- child Space 的 explicit capability。
- child Space 的 policy server / moderation 检查。
- E2EE 边界提示，若 bridge 到非 E2EE 外部系统。

## 14. 与 Matrix Space 的关系

Contrix 的 Space hierarchy 借鉴 Matrix `m.space.child` / `m.space.parent` 的双向确认经验，但区别是：

- Contrix Space 是权限和对象图边界，不只是 room directory。
- Room / Board / List / Card / Message / Morph / Relation 仍然承载业务对象层级，不应把所有对象拆成子 Space。
- 权限和加密默认不继承。
- 跨 Space 深度查询必须 Lazy Link，不能自动拼接泄露。
