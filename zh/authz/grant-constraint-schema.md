# Grant Constraint Schema

## 1. 目标

Capability grant 通过 constraint 限定 subject 能做什么、在哪里做、何时做、以什么身份或设备做。本文定义 grant 如何嵌入 `constraint-schema.md` 中的标准 typed constraint。`constraint-schema.md` 是约束对象的规范性结构；本文不定义第二套 grant-only 扁平结构。

## 2. Grant Envelope

```json
{
  "type": "capability_grant",
  "grant_id": "cx:grant:01js0gr0000000000000000000",
  "issuer": "did:web:acme.example",
  "subject": "did:web:alice.example",
  "scope": {},
  "constraints": [],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-07-26T00:00:00Z",
  "revocation_ref": "cx:revocation-list:default",
  "proof": {}
}
```

## 3. Scope

```json
{
  "space_ids": ["cx:space:01js0sp0000000000000000000"],
  "object_types": ["card", "message", "morph"],
  "morph_types": ["run", "memory"],
  "facets": ["stateful", "replyable", "renderable"],
  "actions": ["cx.card.create", "cx.card.update", "cx.message.create"]
}
```

Scope MUST be allow-list based。未列出的动作默认拒绝。标准对象 SHOULD 使用 `object_types` 过滤；开放对象 SHOULD 使用 `morph_types` 过滤；`facets` 只作为 Space schema / Morph profile 已声明 hint 的范围收窄约束，不替代对象类型、动作列表或 capability 判定。

## 4. Constraint

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
    "scope": "write",
    "fields": ["title", "fields.status"]
  },
  {
    "constraint_type": "type_restriction",
    "effect": "allow",
    "object_type_allow": ["card", "morph"],
    "morph_type_allow": ["run", "memory"],
    "facet_allow": ["stateful", "replyable"]
  }
]
```

Grant `constraints` MUST be an array of typed constraint objects. Evaluation order is defined in `constraint-schema.md`: deny / quarantine / require_review constraints are evaluated before allow constraints within the same category, then `priority` breaks ties.

## 5. Claim Constraint

```json
{
  "constraint_type": "claim_based",
  "effect": "allow",
  "claim_type": "contrix_org_membership_credential",
  "issuer": ["did:web:google.example"],
  "subject_matches_actor": true,
  "claims": {
    "org": "did:web:google.example",
    "member": true
  }
}
```

## 6. Approval Constraint

```json
{
  "constraint_type": "approval_workflow",
  "effect": "require_review",
  "mode": "required",
  "approvers": ["did:web:manager.example"],
  "threshold": 1,
  "expires_after_ms": 86400000,
  "reason_required": true
}
```

## 7. Delegation

Grant MAY allow delegation:

```json
{
  "constraint_type": "delegation_control",
  "effect": "allow",
  "delegation": {
    "allowed": true,
    "max_depth": 1,
    "subset_only": true
  }
}
```

Delegated grant MUST be equal or narrower than parent grant.

## 8. Evaluation

节点判断动作是否允许时 MUST 检查：

1. grant signature
2. issuer authority
3. subject match
4. action in scope
5. resource in scope
6. time validity
7. revocation status
8. field constraints
9. relation / container move constraints
10. claim constraints
11. approval constraints
12. delegation chain

任何一步失败 MUST 拒绝。

## 9. Container Move Constraint

看板拖拽和有序集合移动 SHOULD 使用 `container_move` constraint 限定范围。

```json
{
  "constraint_type": "container_move",
  "effect": "allow",
  "priority": 0,
  "relation_kind_allow": ["contains"],
  "allowed_view_refs": ["cx:view:01js0vw0000000000000000000"],
  "allowed_from_container_refs": ["cx:list:01js0c10000000000000000000"],
  "allowed_to_container_refs": ["cx:list:01js0c20000000000000000000"],
  "wip_limit_override": false
}
```

规则：

- `relation_kind_allow` 限定可移动的 Relation 类型，避免 `assigned_to`、`depends_on` 和 `contains` 被同一宽泛授权混用。
- `allowed_from_container_refs` 与 `allowed_to_container_refs` 分别限制可移出和可移入的列 / collection。
- `allowed_view_refs` 限定授权适用的 View；同一个 Card 出现在多个 View 时不得自动继承移动权。
- `wip_limit_override=false` 时，若目标列 `wip_limit_enforcement` 为 `reject` 或 `require_review`，移动必须失败或进入审批路径。
