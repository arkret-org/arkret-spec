# Grant Constraint Schema

## 1. 目标

Capability grant 通过 constraint 限定 subject 能做什么、在哪里做、何时做、以什么身份或设备做。本文 **不** 定义独立 grant envelope；它只描述 grant 的 `constraints[]` 数组中各类 typed constraint 在 grant 上下文里的常见组合。

权威定义层级：

- **Grant envelope（顶层结构、字段名、必填性、签名规则）**：以
  [`models/data-structures.md` §13 Capability Grant](../models/data-structures.md)
  与机器 schema [`artifacts/schemas/capability-grant.schema.json`](../../artifacts/schemas/capability-grant.schema.json)
  为准。Grant 使用 `id`（`cx:grant:<ulid>`，前缀即对象种类）、
  `schema="cx.schema.capability.v1"`、`actions[]`、`resources[]`、
  `constraints[]`、`proofs[]`（**复数**）等字段。
- **Constraint object 形态（`constraint_type` 列表、`effect` 枚举、各类 typed sub-fields）**：
  以 [`constraint-schema.md`](./constraint-schema.md) 为准。本文不引入新的
  `constraint_type` 值，也不引入与 `constraint-schema.md` 不同的 inner shape。
  发现冲突时以 `constraint-schema.md` 为准。

## 2. Grant Envelope（引用）

Grant envelope 的字段名、必填性、签名规则与示例见 `models/data-structures.md` §13。**本文不重复 envelope 字段表**，避免出现第二套 grant-only 扁平结构。

只复述以下两条对 grant 至关重要的规则：

- 撤销状态不由 envelope 字段或未注册的 revocation-list 对象决定。Contrix v1
  的 grant 撤销 MUST 表达为 accepted `cx.capability.revoke` Event，且该 Event
  的 payload MUST 指向被撤销的 `id`（`cx:grant:<ulid>`）。授权判定使用当前动作
  因果前沿中的 grant / revoke frontier；无法确认高风险动作的 revoke freshness 时，
  必须按 [`capabilities.md` §18.2 Revocation Freshness](./capabilities.md)
  soft-fail 或 fail closed。
- Contrix v1 不注册 `cx:revocation-list:*` typed ID；实现不得生成或要求解析
  这种引用。

完整 envelope 的最小示例（与 `data-structures.md` §13 / schema 一致）：

```json
{
  "id": "cx:grant:01js0gr0000000000000000000",
  "schema": "cx.schema.capability.v1",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "issuer": "did:web:acme.example",
  "subject": "did:web:alice.example",
  "actions": [
    "cx.flow.create",
    "cx.flow.update",
    "cx.message.create"
  ],
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:01js0sp0000000000000000000"
    }
  ],
  "constraints": [],
  "delegable": false,
  "valid_from": "2026-04-26T00:00:00Z",
  "valid_until": "2026-07-26T00:00:00Z",
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:acme.example#governance-key-1",
      "payload_hash": "sha256:...",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "..."
    }
  ]
}
```

资源 selector 的语法见 [`resource-selector-grammar.md`](./resource-selector-grammar.md)
与 [`artifacts/schemas/resource-selector.schema.json`](../../artifacts/schemas/resource-selector.schema.json)。

## 3. 常见 Constraint 组合

> 以下示例只展示在 grant 上下文常见的几种 typed constraint。完整字段与求值规则
> 见 [`constraint-schema.md`](./constraint-schema.md)。本文不再重复 inner field
> 列表；如果两处描述出现差异，以 `constraint-schema.md` 为准。

### 3.1 Field-level 与 Type 限制

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

### 3.2 Claim 约束

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

### 3.3 Approval 约束

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

### 3.4 Delegation 控制

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

## 4. 求值

节点判断动作是否允许时按 [`capabilities.md` §18 Authorization Algorithm](./capabilities.md)
执行；约束求值规则见 [`constraint-schema.md` §15 Evaluation](./constraint-schema.md)。
本文不再列举单独算法步骤，避免与上述两处不一致。

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
