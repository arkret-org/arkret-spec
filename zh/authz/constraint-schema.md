# 授权约束 Schema

## 1. 概述

本规范定义了 Contrix v1 能力授权中约束的形式 schema。约束细化了能力授权可以行使的条件和方式。

## 2. 约束结构

### 2.1 基础 Schema

所有约束遵循以下结构：

```json
{
  "constraint_id": "string",
  "constraint_type": "enum",
  "effect": "allow|deny|quarantine|require_review",
  "parameters": {},
  "priority": "integer"
}
```

### 2.2 约束类型

| 约束类型 | 说明 | 版本 |
|----------|------|------|
| `temporal` | 基于时间的约束 | v1 |
| `field_access` | 字段级读写控制 | v1 |
| `type_restriction` | 实体类型限制 | v1 |
| `scope_limitation` | Space/channel/view 范围 | v1 |
| `delegation_control` | 委托深度和路径 | v1 |
| `rate_limiting` | 操作频率限制 | v1 |
| `approval_workflow` | 审批要求 | v1 |
| `claim_based` | 声明/证明要求 | v1 |
| `accountability` | 责任方追踪 | v1 |
| `encryption_requirement` | 强制加密 | v1 |

## 3. 时间约束

### 3.1 时间窗口

```json
{
  "constraint_type": "temporal",
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
    "when": "entity_is_owned_by_actor"
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

### 5.1 实体类型允许列表

```json
{
  "constraint_type": "type_restriction",
  "effect": "allow",
  "entity_type_allow": ["task", "message", "document"],
  "entity_type_deny": ["run", "memory"]
}
```

### 5.2 Memory 类型限制

```json
{
  "constraint_type": "type_restriction",
  "memory_kind_allow": ["episodic", "semantic"],
  "memory_kind_deny": ["sensitive", "credentials"]
}
```

## 6. 范围限制

### 6.1 Channel 限制

```json
{
  "constraint_type": "scope_limitation",
  "allowed_channel_refs": [
    "cx:channel:01JS0CH000000000000000000"
  ],
  "denied_channel_refs": [
    "cx:channel:01JS0CH999999999999999999"
  ]
}
```

### 6.2 视图限制

```json
{
  "constraint_type": "scope_limitation",
  "allowed_view_kinds": ["kanban", "list"],
  "denied_view_kinds": ["graph", "admin"]
}
```

## 7. 委托控制

### 7.1 委托深度

```json
{
  "constraint_type": "delegation_control",
  "max_delegation_depth": 2,
  "delegation_path": ["did:web:org.example.com"],
  "prohibit_subdelegation": false
}
```

### 7.2 委托范围

```json
{
  "constraint_type": "delegation_control",
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
  "max_resources": 1000,
  "resource_type": "entity",
  "period": "24h",
  "scope": "per_space"
}
```

## 9. 审批工作流

### 9.1 预审批

```json
{
  "constraint_type": "approval_workflow",
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
  "approval_mode": "proposal_then_approve",
  "proposal_entity_type": "proposal",
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
3. 所有 allow 约束（最低优先级优先）
4. 所有 require_review 约束
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
  "actions": ["read", "create_entity", "write_memory"],
  "resources": [
    {
      "kind": "entity",
      "space_id": "cx:space:...",
      "entity_type": "task"
    }
  ],
  "constraints": [
    {
      "constraint_type": "temporal",
      "expires_at": "2026-05-01T00:00:00Z"
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "scope": "write",
      "fields": ["title", "fields.status", "fields.priority"]
    },
    {
      "constraint_type": "accountability",
      "accountability_required": true,
      "responsible_actor": "did:web:owner.example.com"
    },
    {
      "constraint_type": "approval_workflow",
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
      "requires_claims": [{
        "claim_type": "org_role",
        "roles": ["on_call"]
      }]
    }
  ]
}
```
