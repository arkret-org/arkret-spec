---
title: 授权约束 Schema
---

## 1. 概述

本规范定义了 Contrix v1 能力授权中约束的形式 schema。约束细化了能力授权可以行使的条件和方式。

## 2. 约束结构

### 2.1 基础 Schema

所有约束使用同一个 typed flat object 结构。`constraint_type`、`effect`、`evaluation_class` 是通用字段；类型专属字段直接放在同一对象上。Grant、policy、proposal 和 conformance schema 都 MUST 使用这一种结构。

```json
{
  "constraint_id": "string",
  "constraint_type": "temporal",
  "effect": "allow",
  "evaluation_class": "stateless"
}
```

字段语义：

- `constraint_id`：可选稳定标识，用于审计、UI diff 和局部更新；未提供时，评估器可用 constraint 在 grant 内的数组位置和 canonical hash 作为诊断标识。
- `evaluation_class`：可缓存性/依赖范围 hint，决定授权评估器能否走 fast path。每个 `constraint_type` 在 §2.3 有 canonical evaluation_class；实现 MAY 在不破坏正确性的前提下收紧（如把声明的 `grant_local` 实际当 `stateless` 缓存），但 MUST NOT 放宽（不得把 `external` 当 `stateless` 缓存）。

授权评估按 §15 "任一 deny / quarantine / require_review 命中即生效" 裁决；多条 allow 同时通过时，审计 UI 基于 constraint id / 数组位置归因。

### 2.2 约束类型

v1 提供 **8 个 constraint family**。某些 family 内通过 `subtype` 区分子语义；当 family + subtype 共同决定 evaluation_class 或 wire shape 时，subtype 必须显式声明。

约束类型分为 **core** 与 **extension** 两组：

- **core**：所有声明 `cx.profile.core_event_store.v1` 的实现 MUST 支持。这些类型表达最小授权语义。
- **extension**：profile-gated。实现声明对应 profile 时 MUST 支持；未声明 MUST fail closed（不得 silent ignore，避免 grant 在弱实现上语义放宽）。

| 约束 family | subtype（可选） | 类别 | 说明 | 启用 profile |
|-------------|---------------|------|------|------|
| `temporal` | （省略 = 普通时间窗口） | core | `not_before` / `expires_at` 时间窗口。 | core |
| `temporal` | `edit_window` | extension | `applies_to_actions=["cx.message.revise"]` + `message_edit_window` 限定编辑窗口。 | `cx.profile.chat_mvp.v1` |
| `temporal` | `redact_window` | extension | `applies_to_actions=["cx.message.redact"]` + `message_redact_window` 限定撤回窗口。 | `cx.profile.chat_mvp.v1` |
| `field_access` | （省略 = 列表比较） | core | `fields_write_allow` / `fields_write_deny` 等。 | core |
| `type_restriction` | — | core | 对象类型 / Space kind / Morph type / facet 限制。 | core |
| `scope_limitation` | （省略 = 普通 scope） | core | Space / Flow / View / branch 范围。 | core |
| `scope_limitation` 带 `relation_kind_allow` / `allowed_*_container_refs` | — | extension | 看板 / 容器移动范围。 | `cx.profile.kanban_mvp.v1` |
| `delegation_control` | — | core | 委托深度、路径、subset_only 等。 | core |
| `quota` | `rate` | core | 操作频率（`max_operations` + `period` + `burst`）。 | core |
| `quota` | `resource` | extension | 资源大小 / 数量（`blob_max_bytes` / `max_resources` / `max_total_blob_bytes`）。 | `cx.profile.constraint.resource_limit.v1` |
| `claim_based` | `claim` | extension | `requires_claims[]` 凭证 / 证明要求；包含原 `accountability`（responsible / guardian / controller 通过 claim 表达）和原 `device_session`（device binding 通过 claim issuer = device cross-signing key 表达）。 | `cx.profile.constraint.claim_based.v1` |
| `claim_based` | `approval` | extension | 预审批 / proposal-then-approve / approval workflow。 | `cx.profile.constraint.approval_workflow.v1` |
| `confidentiality` | `encryption` | extension | 强制加密、key 轮换、key issuer。 | `cx.profile.constraint.encryption_requirement.v1` |
| `confidentiality` | `visibility` | extension | 对象 / 消息可见性裁剪、`deny_redacted_history`。 | `cx.profile.constraint.visibility_control.v1` |

> v1 已删除 `temporal.session` / `temporal.recurrence` / `field_access.condition` / `claim_based.accountability` / `claim_based.device_session` 这些原 v1 草案中独立的扩展 subtype。其语义由更通用的 `claim_based.claim` + `temporal.{not_before, expires_at}` 表达：会话时长通过 session token claim 的 `expires_at` 表达；周期窗口通过 issuer 颁发短期 claim 表达；字段条件通过 schema-defined deterministic predicate 表达；责任 / device 通过 claim issuer 表达。删除目的是把 constraint family 数从 23 alias 收敛到 7 个核心 typed family（temporal / field_access / type_restriction / scope_limitation / delegation_control / quota / claim_based / confidentiality）。

未注册的 `constraint_type` 或未注册的 `(constraint_type, subtype)` 组合 MUST fail closed。新增 family / subtype 必须先在本表登记，并在 grant-constraint schema 的 `constraint_type` 与 `subtype` enum 中注册。

### 2.3 evaluation_class 分类

每个 `constraint_type` 的 canonical `evaluation_class`。授权评估器 MUST 按此分类决定缓存键；实现声明的 `evaluation_class` 与 canonical 不一致时 MUST 视作不一致 conformance 错误。

| (constraint_type, subtype) | canonical evaluation_class | 缓存键建议 | 备注 |
| --- | --- | --- | --- |
| `temporal`（无 subtype、无 `recurrence`） | `stateless` | 全局缓存，TTL = `expires_at - now` | `not_before` / `expires_at` 是纯时间预算 |
| `temporal` 带 `recurrence`、`subtype=session` 或 `applies_to_actions` | `stateless` | TTL ≤ 下一个 recurrence 边界或 window 剩余时间 | 仍是纯函数，但 TTL 必须缩短 |
| `field_access`（无 `condition`） | `stateless` | (constraint_hash, op_kind) | 仅 allow / deny 列表比较 |
| `field_access` 带 `condition.kind` | `space_state` | (space_id, frontier_hash, op_target) | 大多数 condition.kind（如 `object_is_owned_by_actor`）依赖对象当前 owner |
| `type_restriction` | `stateless` | (constraint_hash, op_target_type) | |
| `scope_limitation`（普通 scope） | `stateless` | (constraint_hash, op_target) | |
| `scope_limitation`（带 `allowed_*_container_refs` / `wip_limit_override`） | `space_state` | (space_id, frontier_hash, target_container_id) | 看目标 List policy / WIP |
| `delegation_control` | `grant_local` | (grant_id) | 只看 grant 自身 path / depth |
| `quota` (`subtype=rate`) | `external` | 不可缓存 | 必须查 actor 历史计数 |
| `quota` (`subtype=resource`，`blob_max_bytes` 单次) | `stateless` | 单次操作的字节计数无需历史 | |
| `quota` (`subtype=resource`，`max_total_blob_bytes` 累计) | `external` | 不可缓存 | 必须查 scope 内累计 |
| `claim_based` (`subtype=claim`) | `external` | 不可缓存 | 必须查 claim issuer revocation 状态 |
| `claim_based` (`subtype=approval`) | `external` | 不可缓存 | 等待 approval event |
| `claim_based` (`subtype=accountability`) | `grant_local` | (grant_id) | guardian / responsible 在 grant 中声明 |
| `claim_based` (`subtype=device_session`) | `space_state` | (space_id, frontier_hash, actor_device_id) | 设备 / session 状态来自 principal control stream |
| `confidentiality` (`subtype=encryption`) | `space_state` | (space_id, frontier_hash) | 取 Space `encryption_profile` / `audit_assurance` |
| `confidentiality` (`subtype=visibility`) | `space_state` | (space_id, frontier_hash) | 看 Space `history_visibility` |

落地要点：

- 8 family（按 subtype 展开后约 14 行）中接近一半是 `external` / `space_state`——这是大型授权图不可整体缓存的根因。fast path（仅 `stateless` + `grant_local`）SHOULD 用于读取 marker、reaction 等低风险动作；写入与高风险动作 MUST 跑完整集合。
- `evaluation_class` 同时承担 lint 锚点：实现声明的依赖与 canonical 不一致时，conformance lint MUST 报错。

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
  "fields_write_allow": ["title", "body", "fields.status"],
  "condition": {
    "kind": "object_is_owned_by_actor"
  }
}
```

`condition.kind` 是封闭的命名 condition enum；未注册的 kind MUST fail closed。v1 enum 见 grant-constraint schema：`object_is_owned_by_actor`、`actor_is_assignee`、`actor_is_responsible`、`actor_is_guardian`、`actor_is_controller`、`object_in_actor_container`、`object_is_unencrypted`、`object_is_encrypted`、`always`、`never`。

实现 MUST NOT 在 `condition` 上引入字符串 DSL 字段；新增 condition 必须先在 grant-constraint schema 的 `condition.kind` enum 中注册，并在本节文档化语义，再由实现使用。

### 4.2 字段写入拒绝

```json
{
  "constraint_type": "field_access",
  "effect": "deny",
  "fields_write_deny": ["id", "created_by", "created_at"]
}
```

### 4.3 字段读取可见性

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "fields_read_allow": ["title", "fields.status"],
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
  "object_type_allow": ["flow", "message", "morph", "place"],
  "place_kind_allow": ["board", "list"],
  "morph_type_allow": ["document", "customer_case"],
  "facet_allow": ["stateful", "replyable", "documentable"],
  "morph_type_deny": ["credential"]
}
```

`object_type_allow` 只按对象类型收窄范围，不赋予能力。`space_kind_allow` 在 v1 已无规范用途——Space 顶层 `kind` 字段已删除（v1 中所有 Space 都是同一种安全边界，无 kind 区分）。该约束保留 schema 字段是为了未来扩展 profile 注册新 Space kind 时可重新启用；当前 v1 实现 SHOULD 把它视为 no-op。**结构容器（看板、列、泳道、calendar bucket 等）由 Place 对象承担**——使用 `place_kind_allow` 收窄到 Place.kind（例如 `["board", "list"]` 或 profile 注册的新 kind）；place_kind_allow 不会把 Place 升级为独立 membership 或 E2EE 边界（Place 永远透明回退到所属 Space）。Flow 不再有顶层模式或业务分类约束；业务语义 SHOULD 通过 Space schema/profile、`fields`、Relation、labels、Morph type 或 facet 约束表达。`facet_allow` 只按 Space schema / Morph profile 已声明的 facet hint 继续收窄范围，不授予写入、排序、状态转换或 renderer 能力，也不替代 `object_type_allow` / `morph_type_allow`。Morph 语义 SHOULD 通过 `morph_type_allow` 和显式 profile 继续细分。

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

`discussion` 不是独立实体或 selector kind。授权 discussion branch 应使用 `allowed_branches=["discussion"]`。`branches[].profile` 只是 branch-local profile hint，v1 grant constraint 不定义按 profile 名称授权的字段；能否读取、发送或管理消息仍由 action、branch access、history visibility 和 E2EE key eligibility 决定。

`allowed_branches` 和 `denied_branches` 的元素 MUST 使用 Flow `branches[].name` 的同一命名规则：`^[a-z][a-z0-9_]{0,63}$`。`synthesis` 与 `discussion` 是 v1 标准 branch 名；profile MAY 声明其他 branch 名，但不得用 profile 名称替代 branch name。

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

### 6.3 容器移动范围（scope_limitation 含 container 字段）

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
  "relation_kind_allow": ["contains"],
  "allowed_view_refs": ["cx:view:01js0vw0000000000000000000"],
  "allowed_from_container_refs": ["cx:space:01js0c10000000000000000000"],
  "allowed_to_container_refs": ["cx:space:01js0c20000000000000000000"],
  "wip_limit_override": false
}
```

`scope_limitation` 约束中的容器移动字段 MUST 在授权判定中早于 operation 生效。目标 List 禁止写入、WIP 超限且无 override、或 `relation_kind` 不在 allow list 时，`cx.flow.move` / `cx.container.move_item` 不得直接生效。

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

## 8. 配额 (Quota)

### 8.1 操作频率（subtype=rate）

```json
{
  "constraint_type": "quota",
  "subtype": "rate",
  "effect": "allow",
  "max_operations": 100,
  "period": "1h",
  "burst": 10,
  "scope": "per_space|global"
}
```

### 8.2 资源限制（subtype=resource）

```json
{
  "constraint_type": "quota",
  "subtype": "resource",
  "effect": "allow",
  "max_resources": 1000,
  "resource_type": "object",
  "period": "24h",
  "scope": "per_space"
}
```

## 9. 审批工作流（claim_based, subtype=approval）

### 9.1 预审批

```json
{
  "constraint_type": "claim_based",
  "subtype": "approval",
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
  "constraint_type": "claim_based",
  "subtype": "approval",
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

## 10. 基于声明的约束（claim_based, subtype=claim）

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

## 11. 责任约束（claim_based, subtype=accountability）

### 11.1 责任方

```json
{
  "constraint_type": "claim_based",
  "subtype": "accountability",
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
  "constraint_type": "claim_based",
  "subtype": "accountability",
  "effect": "require_review",
  "guardian_approval_required": true,
  "guardian_actor_refs": [
    "did:web:parent1.example.com",
    "did:web:parent2.example.com"
  ],
  "approval_threshold": "any|all"
}
```

## 12. 加密要求（confidentiality, subtype=encryption）

### 12.1 强制加密

```json
{
  "constraint_type": "confidentiality",
  "subtype": "encryption",
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
  "constraint_type": "confidentiality",
  "subtype": "encryption",
  "effect": "allow",
  "key_rotation_period": "7d",
  "max_key_age": "30d",
  "require_key_backup": true,
  "approved_key_issuers": [
    "did:web:keys.example.com"
  ]
}
```

## 13. 可见性控制（confidentiality, subtype=visibility）

### 13.1 对象可见性

```json
{
  "constraint_type": "confidentiality",
  "subtype": "visibility",
  "effect": "allow",
  "visibility_allow": ["world_readable", "shared", "joined"],
  "deny_redacted_history": true
}
```

`visibility_allow` 限制 actor 可访问的对象/消息可见性级别。取值与 `history_visibility` 枚举一致：`world_readable`、`shared`、`invited`、`joined`、`restricted`。

## 14. 历史规则示例（已合并到上述 family）

### 14.1 Blob 大小限制

```json
{
  "constraint_type": "quota",
  "subtype": "resource",
  "effect": "allow",
  "blob_max_bytes": 10485760,
  "max_total_blob_bytes": 104857600,
  "scope": "per_space"
}
```

`blob_max_bytes` 限制单次上传 blob 的最大字节数。`max_total_blob_bytes` 限制 scope 内的累计 blob 大小。

### 14.2 消息编辑窗口

```json
{
  "constraint_type": "temporal",
  "subtype": "edit_window",
  "applies_to_actions": ["cx.message.revise"],
  "effect": "allow",
  "message_edit_window": "15m",
  "message_redact_window": "24h",
  "allow_redact_after_window": false
}
```

`message_edit_window` 限制发送后可编辑消息的时间窗口。`message_redact_window` 限制可撤回消息的时间窗口。超时后 `cx.message.revise.own` 或 `cx.message.redact.own` MUST 被拒绝，除非 actor 持有更高权限的 `cx.message.revise` 或 `cx.message.redact`。

## 15. 约束求值

### 15.1 求值规则（normative）

求值规则是**任一命中即生效**的全或无模型，不再依赖跨 effect 的优先级排序：

```
1. 任一 deny 命中            → DENIED
2. 任一 quarantine 命中      → QUARANTINED
3. 任一 require_review 命中  → REQUIRES_REVIEW
4. 所有 allow 命中           → ALLOWED
5. 否则                      → DENIED (default deny)
```

所有 effect 都按集合命中检查，没有"权重"或"优先级"参与裁决。审计 UI 可按 constraint id 或 grant 内数组位置归因。

### 15.2 约束组合

当多个约束适用时：

- 所有 `allow` 约束必须同时满足（AND 逻辑）才得出 ALLOWED；任一不满足即 DENIED。
- `deny` / `quarantine` / `require_review` 三类之间的 precedence 由 §15.1 的步骤顺序决定（deny 优于 quarantine 优于 require_review）。
- 这种全或无模型让授权评估器可以把每个 effect 类别当作集合命中检查，缓存键无需按权重编排。

### 15.3 求值算法

```
function evaluate_constraints(operation, grant_constraints):
    deny       = [c for c in grant_constraints if c.effect == "deny"]
    quarantine = [c for c in grant_constraints if c.effect == "quarantine"]
    review     = [c for c in grant_constraints if c.effect == "require_review"]
    allow      = [c for c in grant_constraints if c.effect == "allow"]

    if any(matches(operation, c) for c in deny):
        return DENIED
    if any(matches(operation, c) for c in quarantine):
        return QUARANTINED
    if any(matches(operation, c) for c in review):
        return REQUIRES_REVIEW
    if all(matches(operation, c) for c in allow):
        return ALLOWED  # diagnostic: matching constraint_id/array index explains the outcome
    return DENIED
```

实现 SHOULD 按 §2.3 的 `evaluation_class` 分组：先跑 `stateless` 与 `grant_local` 的 fast path（命中即可短路返回 DENIED / QUARANTINED / REQUIRES_REVIEW），再跑 `space_state` 与 `external` 的 slow path（必要时走异步 / 缓存绑定 frontier）。`external` 类约束 MUST NOT 缓存。

## 16. 约束匹配

### 16.1 时间匹配

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

### 16.2 字段访问匹配

```javascript
function matches_field_access(operation, constraint):
    if operation.mode == "read":
        allow = constraint.fields_read_allow
        deny = constraint.fields_read_deny
        fields = operation.read_fields
    else:
        allow = constraint.fields_write_allow
        deny = constraint.fields_write_deny
        fields = operation.write_fields

    for field in fields:
        if field in deny:
            return false
        if allow and field not in allow:
            return false
        if constraint.condition:
            if not meets_condition(operation, constraint.condition):
                return false

    return true
```

## 17. 安全考虑

### 17.1 约束规避

防止规避的措施：

- 严格约束验证
- 不隐式放松约束
- 约束违规审计日志
- 约束求值频率限制

### 17.2 基于时间的攻击

缓解措施：

- 使用服务器时间进行验证
- 允许合理时钟偏差（±5 分钟）
- 记录时间验证失败
- 监控时间操纵尝试

### 17.3 声明伪造

防止伪造的措施：

- 验证声明发行者签名
- 检查声明撤销状态
- 验证声明新鲜度
- 仅使用受信声明发行者

## 18. 性能考虑

### 18.1 约束缓存

缓存约束求值结果：

- 键：(grant_id, operation_type, resource_type)
- TTL：基于约束时间边界
- 失效：约束变更时

### 18.2 优化策略

- 按类型索引约束
- 预计算约束组合
- 对简单约束使用快速路径
- 批量约束求值

## 19. 一致性

实现 MUST：

- 支持所有 core v1 约束类型，以及本实现声明的 profile 所要求的 extension 约束类型；未声明对应 profile 时遇到 extension 约束 MUST fail closed，不得 silent ignore
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

## 20. 示例

### 20.1 带约束的 Agent 授权

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
      "object_type_allow": ["flow"]
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "fields_write_allow": ["title", "fields.status", "fields.priority"]
    },
    {
      "constraint_type": "claim_based",
  "subtype": "accountability",
      "effect": "allow",
      "accountability_required": true,
      "responsible_actor": "did:web:owner.example.com"
    },
    {
      "constraint_type": "claim_based",
  "subtype": "approval",
      "effect": "require_review",
      "approval_required": true,
      "approval_mode": "after_commit_review"
    }
  ]
}
```

### 20.2 临时提升访问权限

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

### 20.3 Grant 上下文常见组合

Grant envelope 字段、签名规则与必填性以
[`models/data-structures.md` §13](../models/data-structures.md) 与
[`artifacts/schemas/capability-grant.schema.json`](../../artifacts/schemas/capability-grant.schema.json)
为准；下述示例展示 grant 上下文中的典型 typed constraint 组合，不引入新规则。

> Grant 撤销 MUST 表达为 accepted `cx.capability.revoke` Event 指向 `cx:grant:<ulid>`；
> Contrix v1 不注册 `cx:revocation-list:*` typed ID。

#### 20.3.1 Field-level 与 Type 限制

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
    "object_type_allow": ["flow", "morph", "place"],
    "place_kind_allow": ["board", "list"],
    "morph_type_allow": ["document", "customer_case"],
    "facet_allow": ["stateful", "replyable"]
  }
]
```

#### 20.3.2 Claim 约束

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

#### 20.3.3 Approval 约束

```json
{
  "constraint_type": "claim_based",
  "subtype": "approval",
  "effect": "require_review",
  "mode": "before_commit",
  "approvers": ["did:web:manager.example"],
  "approval_threshold": 1,
  "expires_after": "PT24H",
  "reason_required": true
}
```

#### 20.3.4 Delegation 控制

```json
{
  "constraint_type": "delegation_control",
  "effect": "allow",
  "max_delegation_depth": 1,
  "subset_only": true
}
```

Delegated grant MUST 等于或窄于 parent grant。`max_delegation_depth`、
`delegation_path`、`prohibit_subdelegation` 见 §7.1。

#### 20.3.5 Container Move Scope Constraint

看板拖拽和有序集合移动 SHOULD 使用 `scope_limitation` constraint 的容器移动字段限定范围。完整字段
见 §6.3；下例展示 grant 上下文中的常见组合：

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
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
