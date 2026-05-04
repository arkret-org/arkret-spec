# 授权约束 Schema

## 1. 概述

本规范定义了 Contrix v1 能力授权中约束的形式 schema。约束细化了能力授权可以行使的条件和方式。

## 2. 约束结构

### 2.1 基础 Schema

所有约束使用同一个 typed flat object 结构。`constraint_type`、`effect` 和 `priority` 是通用字段；类型专属字段直接放在同一对象上，不再包入另一层 `parameters`。Grant、policy、proposal 和 conformance schema 都 MUST 使用这一种结构。

```json
{
  "constraint_id": "string",
  "constraint_type": "enum",
  "effect": "allow|deny|quarantine|require_review",
  "priority": 0
}
```

`constraint_id` 是可选稳定标识，用于审计、UI diff 和局部更新；未提供时，评估器可用 constraint 在 grant 内的数组位置和 canonical hash 作为诊断标识。

### 2.2 约束类型

| 约束类型 | 说明 | 版本 |
|----------|------|------|
| `temporal` | 基于时间的约束 | v1 |
| `field_access` | 字段级读写控制 | v1 |
| `type_restriction` | 对象类型限制 | v1 |
| `scope_limitation` | Space / Flow / View 范围（room / card 为 flow.kind） | v1 |
| `delegation_control` | 委托深度和路径 | v1 |
| `rate_limiting` | 操作频率限制 | v1 |
| `approval_workflow` | 审批要求 | v1 |
| `claim_based` | 声明/证明要求 | v1 |
| `accountability` | 责任方追踪 | v1 |
| `encryption_requirement` | 强制加密 | v1 |
| `container_move` | 看板 / collection 移动范围 | v1 |

## 3. 时间约束

### 3.1 时间窗口

```json
{
  "constraint_type": "temporal",
  "effect": "allow",
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-05-26T00:00:00Z",
  "recurrence": {
    "frequency": "daily|weekly|monthly",
    "days": ["monday", "tuesday", "wednesday"],
    "window_start": "09:00:00",
    "window_end": "17:00:00",
    "timezone": "UTC"
  }
}
```

### 3.2 持续时间限制

```json
{
  "constraint_type": "temporal",
  "effect": "allow",
  "max_duration": "8h",
  "max_session_duration": "1h",
  "inactivity_timeout": "30m"
}
```

## 4. 字段访问约束

### 4.1 字段写入允许

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "scope": "write",
  "fields": ["title", "body", "fields.status"],
  "condition": {
    "when": "object_is_owned_by_actor"
  }
}
```

### 4.2 字段写入拒绝

```json
{
  "constraint_type": "field_access",
  "effect": "deny",
  "scope": "write",
  "fields": ["id", "created_by", "created_at"]
}
```

### 4.3 字段读取可见性

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "scope": "read",
  "fields": ["title", "fields.status"],
  "sensitive_fields": ["fields.ssn", "fields.salary"],
  "sensitive_handling": "redact|hash|omit"
}
```

## 5. 类型限制

### 5.1 对象类型 / 声明 hint 允许列表

```json
{
  "constraint_type": "type_restriction",
  "effect": "allow",
  "object_type_allow": ["flow", "message", "morph"],
  "space_kind_allow": ["board", "list"],
  "flow_kind_allow": ["card"],
  "flow_semantic_kind_allow": ["task_cluster", "customer_case"],
  "morph_type_allow": ["document", "customer_case"],
  "facet_allow": ["stateful", "replyable", "documentable"],
  "morph_type_deny": ["credential"]
}
```

`object_type_allow` 只按对象类型收窄范围，不赋予能力。`space_kind_allow` 只用于区分 `Space.kind`，例如 `board` / `list` 工作流容器；它不得把容器 Space 升级为独立 membership 或 E2EE 边界。`flow_kind_allow` 只用于区分 `Flow.kind`，例如 `card` / `room`；`flow_semantic_kind_allow` 用于业务语义分类。`facet_allow` 只按 Space schema / Morph profile 已声明的 facet hint 继续收窄范围，不授予写入、排序、状态转换或 renderer 能力，也不替代 `object_type_allow` / `morph_type_allow`。Morph 语义 SHOULD 通过 `morph_type_allow` 和显式 profile 继续细分。

## 6. 范围限制

### 6.1 流程范围限制（Flow/Space）

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
  "allowed_flow_refs": [
    "cx:flow:01js0r00m00000000000000000"
  ],
  "allowed_branches": ["discussion"],
  "denied_flow_refs": [
    "cx:flow:01js0r00m99999999999999900"
  ]
}
```

`allowed_branches` 只限制 Flow branch 范围，不自动授予对应 branch 的 message read/write 权限。Message 操作仍必须命中 `cx.message.*` action，并满足 branch access、history visibility 和 E2EE key eligibility。

### 6.2 视图限制

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
  "allowed_view_kinds": ["collection"],
  "allowed_view_renderers": ["board", "list"],
  "denied_view_kinds": ["graph"],
  "denied_view_renderers": ["admin"]
}
```

### 6.3 看板移动限制

```json
{
  "constraint_type": "container_move",
  "effect": "allow",
  "relation_kind_allow": ["contains"],
  "allowed_view_refs": ["cx:view:01js0vw0000000000000000000"],
  "allowed_from_container_refs": ["cx:space:01js0c10000000000000000000"],
  "allowed_to_container_refs": ["cx:space:01js0c20000000000000000000"],
  "wip_limit_override": false
}
```

`container_move` MUST 在授权判定中早于 operation 生效。目标 List 禁止写入、WIP 超限且无 override、或 `relation_kind` 不在 allow list 时，`cx.flow.move` / `cx.container.move_item` 不得直接生效。

## 7. 委托控制

### 7.1 委托深度

```json
{
  "constraint_type": "delegation_control",
  "effect": "allow",
  "max_delegation_depth": 2,
  "delegation_path": ["did:web:org.example.com"],
  "prohibit_subdelegation": false
}
```

### 7.2 委托范围

```json
{
  "constraint_type": "delegation_control",
  "effect": "allow",
  "delegation_scope": "narrowing_only",
  "allow_scope_expansion": false,
  "require_parent_reference": true
}
```

## 8. 频率限制

### 8.1 操作频率

```json
{
  "constraint_type": "rate_limiting",
  "effect": "allow",
  "max_operations": 100,
  "period": "1h",
  "burst": 10,
  "scope": "per_space|global"
}
```

### 8.2 资源频率

```json
{
  "constraint_type": "rate_limiting",
  "effect": "allow",
  "max_resources": 1000,
  "resource_type": "object",
  "period": "24h",
  "scope": "per_space"
}
```

## 9. 审批工作流

### 9.1 预审批

```json
{
  "constraint_type": "approval_workflow",
  "effect": "require_review",
  "approval_required": true,
  "approval_mode": "before_commit",
  "approval_actor_refs": [
    "did:web:manager.example.com"
  ],
  "approval_relation": "controller",
  "timeout": "72h",
  "auto_reject_on_timeout": true
}
```

### 9.2 提案模式

```json
{
  "constraint_type": "approval_workflow",
  "effect": "require_review",
  "approval_mode": "proposal_then_approve",
  "proposal_morph_type": "proposal",
  "approval_threshold": "majority|unanimous|quorum",
  "approvers": [
    "did:web:approver1.example.com",
    "did:web:approver2.example.com"
  ]
}
```

## 10. 基于声明的约束

### 10.1 声明要求

```json
{
  "constraint_type": "claim_based",
  "effect": "allow",
  "requires_claims": [
    {
      "claim_type": "org_membership",
      "issuer": "did:web:acme.com",
      "organization": "did:web:acme.com",
      "status": "active",
      "roles": ["employee", "contractor"]
    }
  ],
  "trusted_claim_issuers": [
    "did:web:acme.com"
  ],
  "claim_refresh_required": true,
  "claim_max_age": "24h"
}
```

### 10.2 声明验证

```json
{
  "constraint_type": "claim_based",
  "effect": "allow",
  "validation_mode": "strict|lenient",
  "allow_expired_claims": false,
  "allow_revoked_claims": false,
  "minimum_trust_level": "high"
}
```

## 11. 责任约束

### 11.1 责任方

```json
{
  "constraint_type": "accountability",
  "effect": "allow",
  "accountability_required": true,
  "responsible_actor": "did:web:guardian.example.com",
  "accountability_relation": "guardian",
  "log_all_operations": true,
  "require_signature": true
}
```

### 11.2 监护人审批

```json
{
  "constraint_type": "accountability",
  "effect": "require_review",
  "guardian_approval_required": true,
  "guardian_actor_refs": [
    "did:web:parent1.example.com",
    "did:web:parent2.example.com"
  ],
  "approval_threshold": "any|all"
}
```

## 12. 加密要求

### 12.1 强制加密

```json
{
  "constraint_type": "encryption_requirement",
  "effect": "allow",
  "encryption_required": true,
  "min_encryption_level": "mls_rfc9420",
  "allow_plaintext_fallback": false,
  "require_audit_trail": true
}
```

### 12.2 密钥管理

```json
{
  "constraint_type": "encryption_requirement",
  "effect": "allow",
  "key_rotation_period": "7d",
  "max_key_age": "30d",
  "require_key_backup": true,
  "approved_key_issuers": [
    "did:web:keys.example.com"
  ]
}
```

## 13. 约束求值

### 13.1 求值顺序

约束按优先级顺序求值：

```
1. 所有 deny 约束（最高优先级优先）
2. 所有 quarantine 约束
3. 所有 require_review 约束
4. 所有 allow 约束（最低优先级优先）
```

在每个类别中，`priority` 值越大优先级越高。

### 13.2 约束组合

当多个约束适用时：

- 所有约束必须同时满足（AND 逻辑）
- 冲突解决：deny > quarantine > require_review > allow
- 每种约束类型可定义例外

### 13.3 求值算法

```
function evaluate_constraints(operation, grant_constraints):
    # 首先检查 deny 约束
    for constraint in grant_constraints:
        if constraint.effect == "deny":
            if matches(operation, constraint):
                return DENIED

    # 检查 quarantine 约束
    for constraint in grant_constraints:
        if constraint.effect == "quarantine":
            if matches(operation, constraint):
                return QUARANTINED

    # 检查 require_review 约束
    for constraint in grant_constraints:
        if constraint.effect == "require_review":
            if matches(operation, constraint):
                return REQUIRES_REVIEW

    # 所有 allow 约束必须通过
    for constraint in grant_constraints:
        if constraint.effect == "allow":
            if not matches(operation, constraint):
                return DENIED

    return ALLOWED
```

## 14. 约束匹配

### 14.1 时间匹配

```javascript
function matches_temporal(operation, constraint):
    now = current_timestamp()

    if constraint.not_before and now < constraint.not_before:
        return false
    if constraint.expires_at and now > constraint.expires_at:
        return false
    if constraint.recurrence:
        return matches_recurrence(now, constraint.recurrence)

    return true
```

### 14.2 字段访问匹配

```javascript
function matches_field_access(operation, constraint):
    if constraint.scope == "read":
        fields = operation.read_fields
    else:
        fields = operation.write_fields

    for field in fields:
        if field in constraint.fields:
            if constraint.effect == "deny":
                return false
            if constraint.condition:
                if not meets_condition(operation, constraint.condition):
                    return false

    return true
```

## 15. 安全考虑

### 15.1 约束规避

防止规避的措施：

- 严格约束验证
- 不隐式放松约束
- 约束违规审计日志
- 约束求值频率限制

### 15.2 基于时间的攻击

缓解措施：

- 使用服务器时间进行验证
- 允许合理时钟偏差（±5 分钟）
- 记录时间验证失败
- 监控时间操纵尝试

### 15.3 声明伪造

防止伪造的措施：

- 验证声明发行者签名
- 检查声明撤销状态
- 验证声明新鲜度
- 仅使用受信声明发行者

## 16. 性能考虑

### 16.1 约束缓存

缓存约束求值结果：

- 键：(grant_id, operation_type, resource_type)
- TTL：基于约束时间边界
- 失效：约束变更时

### 16.2 优化策略

- 按类型索引约束
- 预计算约束组合
- 对简单约束使用快速路径
- 批量约束求值

## 17. 一致性

实现 MUST：

- 支持所有 v1 约束类型
- 按正确顺序求值约束
- 返回正确的拒绝原因
- 记录约束违规
- 验证约束参数

实现 SHOULD：

- 缓存约束求值
- 优化常见约束模式
- 提供约束调试工具
- 支持约束模板
- 监控约束性能

## 18. 示例

### 18.1 带约束的 Agent 授权

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:agent.example.com",
  "actions": ["cx.object.read", "cx.flow.create", "cx.morph.create"],
  "resources": [
    {
      "kind": "flow",
      "space_id": "cx:space:...",
      "flow_id": "*"
    }
  ],
  "constraints": [
    {
      "constraint_type": "temporal",
      "effect": "allow",
      "expires_at": "2026-05-01T00:00:00Z"
    },
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "flow_kind_allow": ["card"]
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "scope": "write",
      "fields": ["title", "fields.status", "fields.priority"]
    },
    {
      "constraint_type": "accountability",
      "effect": "allow",
      "accountability_required": true,
      "responsible_actor": "did:web:owner.example.com"
    },
    {
      "constraint_type": "approval_workflow",
      "effect": "require_review",
      "approval_required": true,
      "approval_mode": "after_commit_review"
    }
  ]
}
```

### 18.2 临时提升访问权限

```json
{
  "constraints": [
    {
      "constraint_type": "temporal",
      "effect": "allow",
      "not_before": "2026-04-26T09:00:00Z",
      "expires_at": "2026-04-26T17:00:00Z",
      "recurrence": {
        "frequency": "weekly",
        "days": ["saturday", "sunday"],
        "timezone": "America/New_York"
      }
    },
    {
      "constraint_type": "claim_based",
      "effect": "allow",
      "requires_claims": [{
        "claim_type": "org_role",
        "roles": ["on_call"]
      }]
    }
  ]
}
```
