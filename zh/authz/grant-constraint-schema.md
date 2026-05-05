# Grant Constraint Examples

> **指针页（保留示例）**。Grant envelope 字段、签名规则与必填性以
> [`models/data-structures.md` §13](../models/data-structures.md) 与
> [`artifacts/schemas/capability-grant.schema.json`](../../artifacts/schemas/capability-grant.schema.json)
> 为准；`constraint_type` 列表、`effect` 枚举、各类 typed sub-fields 与求值规则以
> [`constraint-schema.md`](./constraint-schema.md) 为准；授权算法以
> [`capabilities.md` §18](./capabilities.md) 为准。本文只列举 grant 上下文中常见的
> typed constraint 组合示例，不引入新规则；如有冲突以上述权威文档为准。
>
> Grant 撤销 MUST 表达为 accepted `cx.capability.revoke` Event 指向 `cx:grant:<ulid>`；
> Contrix v1 不注册 `cx:revocation-list:*` typed ID。

## 1. Field-level 与 Type 限制

```json
[
  {
    "constraint_type": "temporal",
    "effect": "allow",
    "not_before": "2026-04-26T00:00:00Z",
    "expires_at": "2026-07-26T00:00:00Z"
  },
  {
    "constraint_type": "field_access",
    "effect": "allow",
    "fields_write_allow": ["title", "fields.status"]
  },
  {
    "constraint_type": "type_restriction",
    "effect": "allow",
    "object_type_allow": ["flow", "morph"],
    "space_kind_allow": ["board", "list"],
    "morph_type_allow": ["document", "customer_case"],
    "facet_allow": ["stateful", "replyable"]
  }
]
```

## 2. Claim 约束

```json
{
  "constraint_type": "claim_based",
  "effect": "allow",
  "requires_claims": [
    {
      "claim_type": "contrix_org_membership_credential",
      "trusted_issuers": ["did:web:google.example"],
      "subject_matches_actor": true,
      "value_constraints": {
        "org": "did:web:google.example",
        "member": true
      }
    }
  ]
}
```

## 3. Approval 约束

```json
{
  "constraint_type": "approval_workflow",
  "effect": "require_review",
  "mode": "before_commit",
  "approvers": ["did:web:manager.example"],
  "approval_threshold": 1,
  "expires_after": "PT24H",
  "reason_required": true
}
```

## 4. Delegation 控制

```json
{
  "constraint_type": "delegation_control",
  "effect": "allow",
  "max_delegation_depth": 1,
  "subset_only": true
}
```

Delegated grant MUST 等于或窄于 parent grant。`max_delegation_depth`、
`delegation_path`、`prohibit_subdelegation` 见 `constraint-schema.md` §7.1。

## 5. Container Move Constraint

看板拖拽和有序集合移动 SHOULD 使用 `container_move` constraint 限定范围。
完整字段见 [`constraint-schema.md` §6.3](./constraint-schema.md)；下例展示 grant
上下文中的常见组合：

```json
{
  "constraint_type": "container_move",
  "effect": "allow",
  "priority": 0,
  "relation_kind_allow": ["contains"],
  "allowed_view_refs": ["cx:view:01js0vw0000000000000000000"],
  "allowed_from_container_refs": ["cx:space:01js0c10000000000000000000"],
  "allowed_to_container_refs": ["cx:space:01js0c20000000000000000000"],
  "wip_limit_override": false
}
```

规则：

- `relation_kind_allow` 限定可移动的 Relation 类型，避免 `assigned_to`、
  `depends_on` 和 `contains` 被同一宽泛授权混用。
- `allowed_from_container_refs` 与 `allowed_to_container_refs` 分别限制可移出
  和可移入的列 / collection。
- `allowed_view_refs` 限定授权适用的 View；同一个 Flow item 出现在多个 View
  时不得自动继承移动权。
- `wip_limit_override=false` 时，若目标列 `wip_limit_enforcement` 为 `reject`
  或 `require_review`，移动必须失败或进入审批路径。
