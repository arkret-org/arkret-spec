---
title: 授权约束 Schema
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 概述

本规范定义了 Cokret v1 能力授权中约束的形式 schema。约束细化了能力授权可以行使的条件和方式。

> _Example (informative)._ 本文各小节的 JSON 代码块均为说明性示例，用于展示典型 typed constraint 的语义组合。约束对象的**权威 wire 字段集合**以 [`../../artifacts/schemas/grant-constraint.schema.json`](../../artifacts/schemas/grant-constraint.schema.json)（`additionalProperties:false`）为准；示例中若出现该 schema 未声明的概念性字段名（用于阐述意图）或形如 `"a|b"` 的取值占位，均不构成合法 wire 取值，实现 MUST 以 schema 为准。

职责切分是 normative：

- **Constraint** 是 grant / policy 内的静态声明，描述“这个能力最多可在什么范围内、以什么附加条件行使”。它可以声明需要某类 claim、approval、device/session 或 challenge，但不直接携带一次运行时 allow 结果。
- **Control Move precondition** 只表达 cell 原子性、state freshness 和 reducer 可验证的因果条件；它不替代授权，也不负责发起外部 claim 查询。DataEvent 不携带 `preconditions[]`，其数据面约束由 causal refs、`seal_ref` 与 Lattice 规则表达。
- **Policy Server obligation** 是运行时 claim / approval / challenge 的唯一动态评估出口。任何需要检查 issuer revocation、presentation audience、request hash、approval nonce、challenge proof 或外部状态的 constraint，MUST 被归约为 `ck.self.policy.query.check`（默认 path `/_cokret/self/policy/check`）obligation，并由 Policy Server 返回可签名、可重放防护的 proof；reducer 只验证 obligation proof 与原始 request / DataEvent 或 Control Move canonical hash 绑定一致。

因此，`claim_based` constraint 中的 `requires_claims[]`、approval 字段和 challenge 字段是声明性要求，不得被实现解释成“只要 grant 中列出就自动通过”。没有对应 Policy Server proof / accepted approval Event / reducer 可验证 claim evidence 时，相关动作 MUST fail closed 或进入 pending。

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
- `effect`：封闭枚举，取值 ∈ `{allow, deny, quarantine, require_review}`。`allow` 声明约束满足时的允许条件；`deny` / `quarantine` / `require_review` 声明命中即生效的拒绝 / 隔离 / 待审条件。未注册的 `effect` 值 MUST fail closed。完整求值规则（任一 deny / quarantine / require_review 命中即生效，所有 allow 命中才 ALLOWED）见 §15。
- `evaluation_class`：可缓存性/依赖范围 hint，决定授权评估器能否走 fast path。每个 `constraint_type` 在 §2.3 有 canonical evaluation_class；实现 MAY 在不破坏正确性的前提下收紧（如把声明的 `grant_local` 实际当 `stateless` 缓存），但 MUST NOT 放宽（不得把 `external` 当 `stateless` 缓存）。

授权评估按 §15 "任一 deny / quarantine / require_review 命中即生效" 裁决；多条 allow 同时通过时，审计 UI 基于 constraint id / 数组位置归因。

### 2.2 约束类型

v1 提供 **8 个 constraint family**。某些 family 内通过 `subtype` 区分子语义；当 family + subtype 共同决定 evaluation_class 或 wire shape 时，subtype 必须显式声明。

约束类型分为 **core** 与 **extension** 两组：

- **core**：所有声明 `ck.profile.core_event_store.v1` 的实现 MUST 支持。这些类型表达最小授权语义。
- **extension**：profile-gated。实现声明对应 profile 时 MUST 支持；未声明 MUST fail closed（不得 silent ignore，避免 grant 在弱实现上语义放宽）。

| 约束 family | subtype（可选） | 类别 | 说明 | 启用 profile |
|-------------|---------------|------|------|------|
| `temporal` | （省略 = 普通时间窗口） | core | `not_before` / `expires_at` 时间窗口。 | core |
| `temporal` | `edit_window` | extension | `applies_to_actions=["ck.message.revise.own"]` + `message_edit_window` 限定自助编辑窗口。 | `ck.profile.chat_mvp.v1` |
| `temporal` | `redact_window` | extension | `applies_to_actions=["ck.message.redact.own"]` + `message_redact_window` 限定自助撤回窗口。 | `ck.profile.chat_mvp.v1` |
| `field_access` | （省略 = 列表比较） | core | 写入面 `allowed_write_fields` / `denied_write_fields`（§4.1 / §4.2）与读取面 `allowed_read_fields` / `denied_read_fields` / `sensitive_fields` / `sensitive_handling`（§4.3）。 | core |
| `type_restriction` | — | core | 对象类型 / Realm kind / Morph type / facet 限制。 | core |
| `scope_limitation` | （省略 = 普通 scope） | core | Realm / Strand / View / track 范围。 | core |
| `scope_limitation` 带 `allowed_relation_kinds` / `allowed_*_container_refs` | — | extension | 看板 / 容器移动范围。 | `ck.profile.kanban_mvp.v1` |
| `delegation_control` | — | core | 委托深度、路径、`delegation_scope` 等。 | core |
| `quota` | `rate` | core | 操作频率（`max_operations` + `period` + `burst`）。 | core |
| `quota` | `resource` | extension | 资源大小 / 数量（`blob_max_bytes` / `max_resources` / `max_total_blob_bytes`）。 | `ck.profile.constraint.resource_limit.v1` |
| `claim_based` | `claim` | extension | `requires_claims[]` 凭证 / 证明要求；包含原 `accountability`（responsible / guardian / controller 通过 claim 表达）和原 `device_session`（device binding 通过 claim issuer = device cross-signing key 表达）。 | `ck.profile.constraint.claim_based.v1` |
| `claim_based` | `approval` | extension | 预审批 / proposal-then-approve / approval workflow。 | `ck.profile.constraint.approval_workflow.v1` |
| `confidentiality` | `encryption` | extension | 强制加密、key 轮换、key issuer。 | `ck.profile.constraint.encryption_requirement.v1` |
| `confidentiality` | `visibility` | extension | 对象 / 消息可见性裁剪、`deny_redacted_history`。 | `ck.profile.constraint.visibility_control.v1` |

> v1 共 8 个核心 typed family，narrow-scoped 子类作为可选 `subtype` 表达：`edit_window` / `redact_window` 走 `temporal` (subtype 标记)；`container_move` 走 `scope_limitation`；`rate_limiting` / `resource_limit` 走 `quota` (`subtype=rate` / `resource`)；`approval_workflow` / `accountability` 走 `claim_based` (`subtype=approval` / `accountability`)；device/session binding **不是独立 subtype**，并入 `claim_based` `subtype=claim`，通过 claim issuer = device cross-signing key 表达；`encryption_requirement` / `visibility_control` 走 `confidentiality` (`subtype=encryption` / `visibility`)。底层字段或 subtype 值——`recurrence` / `max_session_duration` / `condition.kind` / `requires_claims[]` 等都是合法字段（见 §3 / §4 / §10）。canonical 8 family：`temporal` / `field_access` / `type_restriction` / `scope_limitation` / `delegation_control` / `quota` / `claim_based` / `confidentiality`。

未注册的 `constraint_type` 或未注册的 `(constraint_type, subtype)` 组合 MUST fail closed。新增 family / subtype 必须先在本表登记，并在 grant-constraint schema 的 `constraint_type` 与 `subtype` enum 中注册。

### 2.3 evaluation_class 分类

每个 `constraint_type` 的 canonical `evaluation_class`。授权评估器 MUST 按此分类决定缓存键；实现声明的 `evaluation_class` 与 canonical 不一致时 MUST 视作不一致 conformance 错误。

| (constraint_type, subtype) | canonical evaluation_class | 缓存键建议 | 备注 |
| --- | --- | --- | --- |
| `temporal`（无 subtype、无 `recurrence`） | `stateless` | 全局缓存，TTL = `expires_at - now` | `not_before` / `expires_at` 是纯时间预算 |
| `temporal` 带 `recurrence`、`subtype=session` 或 `applies_to_actions` | `stateless` | TTL ≤ 下一个 recurrence 边界或 window 剩余时间 | 仍是纯函数，但 TTL 必须缩短 |
| `field_access`（无 `condition`） | `stateless` | (constraint_digest, op_kind) | 仅 allow / deny 列表比较 |
| `field_access` 带 `condition.kind` | `realm_state` | (realm_id, frontier_digest, op_target) | 大多数 condition.kind（如 `object_is_owned_by_actor`）依赖对象当前 owner |
| `type_restriction` | `stateless` | (constraint_digest, op_target_type) | |
| `scope_limitation`（普通 scope） | `stateless` | (constraint_digest, op_target) | |
| `scope_limitation`（带 `allowed_*_container_refs` / `wip_limit_override`） | `realm_state` | (realm_id, frontier_digest, target_container_id) | 看目标 List policy / WIP |
| `scope_limitation`（带 `blob_presign_scope` / `allowed_endpoints` / `allowed_data_classes`） | `stateless` | (constraint_digest, op_target) | 对 presign / agent / applet 请求字段做集合或模式匹配 |
| `delegation_control` | `grant_local` | (grant_id) | 只看 grant 自身 path / depth |
| `quota` (`subtype=rate`) | `external` | 不可缓存 | 必须查 actor 历史计数 |
| `quota` (`subtype=resource`，`blob_max_bytes` 单次) | `stateless` | 单次操作的字节计数无需历史 | |
| `quota` (`subtype=resource`，`max_total_blob_bytes` 累计) | `external` | 不可缓存 | 必须查 scope 内累计 |
| `claim_based` (`subtype=claim`) | `external` | 不可缓存 | 必须查 claim issuer revocation 状态 |
| `claim_based` (`subtype=approval`) | `external` | 不可缓存 | 等待 approval event |
| `claim_based` (`subtype=accountability`) | `grant_local` | (grant_id) | guardian / responsible 在 grant 中声明 |
| `claim_based` (`subtype=claim`，device/session binding 子情形：claim issuer = device cross-signing key) | `realm_state` | (realm_id, frontier_digest, actor_device_id) | device/session binding 不是独立 subtype（见 §2.2），它是 `subtype=claim` 的子情形；当需校验设备 / session 状态（来自 principal control stream）时该子判定为 `realm_state` |
| `confidentiality` (`subtype=encryption`，纯静态声明：`encryption_required` / `min_encryption_level` / `allow_plaintext_fallback` / `require_audit_trail` / `approved_key_issuers` 列表成员比较) | `stateless` | (constraint_digest, op_target) | 仅做布尔标志与 issuer 列表集合比较，不读取 Realm state |
| `confidentiality` (`subtype=encryption`，依赖 Realm 加密态：需对照 Realm `encryption_profile`、active Audit Applet Binding 或当前 MLS key schedule 的判定) | `realm_state` | (realm_id, frontier_digest) | 仅这些依赖项走 slow path |
| `confidentiality` (`subtype=visibility`) | `realm_state` | (realm_id, frontier_digest) | 看 Realm `history_visibility` |

落地要点：

- 8 family（按 subtype 展开后约 14 行）中接近一半是 `external` / `realm_state`——这是大型授权图不可整体缓存的根因。fast path（仅 `stateless` + `grant_local`）SHOULD 用于读取 marker、reaction 等低风险动作；写入与高风险动作 MUST 跑完整集合。
- `evaluation_class` 同时承担 lint 锚点：实现声明的依赖与 canonical 不一致时，conformance lint MUST 报错。

### 2.4 字段扁平化与未来嵌套化（normative for new fields）

v1 constraint object 上 approval / accountability / claim 相关字段是扁平结构（`approval_required` / `approval_mode` / `approval_actor_ids` / `approval_relation` / `accountability_required` / `guardian_approval_required` / `controller_approval_required` 等），简化 schema 验证。

**新字段命名规则（normative，对扩展 profile 适用）**：扩展 profile 引入新的 approval / claim / accountability 子字段时，应避免展开成新顶层 flat field。新字段若在概念上属于现有 family，MUST 通过以下两种路径之一表达：

1. **在 `condition` / `requires_claims[]` 中携带**：approval workflow 的额外配置（如 reviewer roster、escalation policy）可写入 `requires_claims[].value_constraints`，或新增以 `x_` 前缀命名的扩展嵌套对象（例如 `x_approval_extension`，仅扩展 profile 使用，core profile 不引入新顶层 flat field）。**注意**：`grant-constraint.schema.json` 顶层是 `additionalProperties:false` + `patternProperties:"^x_[a-z][a-z0-9_]{0,63}$"`，因此扩展嵌套对象 MUST 使用 `x_` 前缀；不带前缀的裸名会被 schema 拒绝，实现 MUST NOT 为容纳它而改用更松的本地 schema。
2. **以新 `subtype` 区分**：若新字段语义无法通过既有 subtype 覆盖，应注册新 subtype（如 `claim_based.subtype=quorum_approval`）而不是继续在 flat namespace 加字段。


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
    "days": ["mon", "tue", "wed"],
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
  "max_duration": "PT8H",
  "max_session_duration": "PT1H",
  "inactivity_timeout": "PT30M"
}
```

> Duration 字段使用 ISO 8601 持续时间格式（`P[n]Y[n]M[n]DT[n]H[n]M[n]S`）。`grant-constraint.schema.json` 中相应字段的 `pattern` 即此格式；`"8h"` / `"1h"` / `"30m"` compact 形态在 v1 wire 上 MUST 被 schema validator 拒绝。

## 4. 字段访问约束

### 4.1 字段写入允许

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "allowed_write_fields": ["metadata.title", "content", "metadata.fields.review_status"],
  "condition": {
    "kind": "object_is_owned_by_actor"
  }
}
```

`condition.kind` 是封闭的命名 condition enum；未注册的 kind MUST fail closed。v1 enum 见 grant-constraint schema：`object_is_owned_by_actor`、`actor_is_assignee`、`actor_is_responsible`、`actor_is_guardian`、`actor_is_controller`、`object_in_actor_container`、`object_is_unencrypted`、`object_is_encrypted`、`always`、`never`。

**`⊥` / unknown freshness 时 fail closed**：若 condition 依赖的 cell 处于 `⊥`（cas_register bottom）或 freshness 状态为 `unknown`，condition 评估 MUST fail closed，不得 silent allow；该规则对所有 `realm_state` 类 condition 适用。

实现 MUST NOT 在 `condition` 上引入字符串 DSL 字段；新增 condition 必须先在 grant-constraint schema 的 `condition.kind` enum 中注册，并在本节文档化语义，再由实现使用。

### 4.2 字段写入拒绝

```json
{
  "constraint_type": "field_access",
  "effect": "deny",
  "denied_write_fields": ["id", "created_by", "created_at"]
}
```

### 4.3 字段读取可见性

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "allowed_read_fields": ["metadata.title", "metadata.fields.review_status"],
  "denied_read_fields": ["metadata.fields.internal_note"],
  "sensitive_fields": ["metadata.fields.ssn", "metadata.fields.salary"],
  "sensitive_handling": "redact|hash|omit"
}
```

`allowed_read_fields` / `denied_read_fields` / `sensitive_fields` / `sensitive_handling` 与 §4.1 / §4.2 的写入字段同属 `field_access` core family（effect=`allow`），表达读取面的字段裁剪与敏感字段处理；其求值见 §16.2（`allowed_read_fields` / `denied_read_fields` 的 admit/deny gate）与 §16.2.1（`sensitive_fields` / `sensitive_handling` 的读路径处理义务）。这四个读字段在 capabilities §6 中有对应扁平别名。

## 5. 类型限制

### 5.1 对象类型 / 声明 hint 允许列表

```json
{
  "constraint_type": "type_restriction",
  "effect": "allow",
  "allowed_object_types": ["strand", "message", "morph", "space"],
  "allowed_space_kinds": ["board", "list"],
  "allowed_morph_types": ["document", "customer_case"],
  "allowed_facets": ["stateful", "replyable", "documentable"],
  "denied_morph_types": ["credential"]
}
```

`allowed_object_types` 只按对象类型收窄范围，不赋予能力。v1 中所有 Realm 同属一种安全边界、无 kind 区分，**不存在 Realm-kind 维度的约束**；若未来真的引入 Realm kind，必须注册新约束版本或明确 profile 语义。需按结构收窄请用 `allowed_space_kinds`。**结构容器（看板、列、泳道、calendar bucket 等）由 Space 对象承担**——使用 `allowed_space_kinds` 收窄到 Space.kind（例如 `["board", "list"]` 或 profile 注册的新 kind）；allowed_space_kinds 不会把 Space 升级为独立 membership 或 E2EE 边界（Space 永远透明回退到所属 Realm）。Strand 不再有顶层模式或业务分类约束；业务语义 SHOULD 通过 Realm schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 约束表达。`allowed_facets` 只按 Realm schema / Morph profile 已声明的 facet hint 继续收窄范围，不授予写入、排序、状态转换或 renderer 能力，也不替代 `allowed_object_types` / `allowed_morph_types`。Morph 语义 SHOULD 通过 `allowed_morph_types` 和显式 profile 继续细分。

## 6. 范围限制

### 6.1 流程范围限制（Strand/Realm）

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
  "allowed_strand_ids": [
    "ck:strand:01964180-0280-7000-8000-000000000000"
  ],
  "allowed_tracks": ["discussion"],
  "denied_strand_ids": [
    "ck:strand:01964180-0289-7a52-94a5-294a5294a400"
  ]
}
```

`allowed_tracks` 只限制 Strand track 范围，不自动授予对应 track 的 message read/write 权限。Message 操作仍必须命中 `ck.message.*` action，并在已有 Realm 授权内满足 `allowed_tracks` action scope、history visibility 和 E2EE key eligibility。

`discussion` 不是独立实体或 selector kind。授权 discussion track 应使用 `allowed_tracks=["discussion"]`。`tracks.<name>.profile` 只是 track-local profile hint，v1 grant constraint 不定义按 profile 名称授权的字段；能否读取、发送或管理消息仍由 action、`allowed_tracks` action scope、history visibility 和 E2EE key eligibility 决定。

`allowed_tracks` 和 `denied_tracks` 的元素 MUST 使用 Strand `tracks` map key 的同一命名规则：`^[a-z][a-z0-9_]{0,63}$`。`synthesis` 与 `discussion` 是 v1 标准 track 名；profile MAY 声明其他 track 名，但不得用 profile 名称替代 track name。

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

### 6.3 结构容器移动范围（from/to container refs）

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
  "allowed_relation_kinds": ["contains"],
  "allowed_view_ids": ["ck:view:019641be-0000-7000-8000-000000000000"],
  "allowed_from_container_refs": ["ck:space:019640c0-8000-7000-8000-000000000000"],
  "allowed_to_container_refs": ["ck:space:019640c1-0000-7000-8000-000000000000"],
  "wip_limit_override": false
}
```

`scope_limitation` 约束中的 `allowed_from_container_refs` / `allowed_to_container_refs` MUST 在授权判定中早于 operation 生效。这里的 container 是结构容器概念，不是新的对象类型或 ID 前缀；v1 标准容器由 Space 承担（例如 Board / List / 泳道）。目标 List 禁止写入、WIP 超限且无 override、或 `relation_kind` 不在 allow list 时，`ck.strand.move` / `ck.container.move_item` 不得直接生效。

`allowed_space_ids` / `denied_space_ids` MUST 使用 `ck:space:` ID；`allowed_from_container_refs` / `allowed_to_container_refs` 表达可移出 / 可移入的结构容器，也 MUST 使用 `ck:space:`（或 profile 明确声明的 `ck:strand:` / `ck:morph:` 容器对象）。Realm-wide 范围收窄应写在 resource selector 的 `realm:` 维度，不得把 `ck:realm:` 塞进 Space 或 container 字段。

### 6.4 服务出口与 presign 范围

```json
{
  "constraint_type": "scope_limitation",
  "effect": "allow",
  "blob_presign_scope": {
    "allowed_purposes": ["media_inline", "thumbnail"],
    "realm_ids": ["ck:realm:0196419b-0000-7000-8000-000000000000"]
  },
  "allowed_endpoints": ["https://api.trusted.example"],
  "allowed_data_classes": ["public", "internal"]
}
```

`blob_presign_scope` 是 `ck.self.blob.command.presign` 的必需约束之一，限制可签发的 purpose、Realm 和可选 blob ref pattern。`allowed_endpoints` / `allowed_data_classes` 用于 agent、applet、export、connector 等会把数据发往外部 endpoint 的 action；实现 MUST 对请求中的目标 endpoint 与数据分类做 fail-closed 匹配，未知 data class 或 endpoint 不得按 allow 处理。

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
  "period": "PT1H",
  "burst": 10,
  "constraint_scope": "per_space|global"
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
  "blob_presign_max_ttl_seconds": 300,
  "max_artifact_bytes": 10485760,
  "period": "PT24H",
  "constraint_scope": "per_space"
}
```

`blob_presign_max_ttl_seconds` 是 `ck.self.blob.command.presign` 的必需约束之一，服务端 MUST 将请求的 `max_age_seconds` 收窄到该值、deployment policy 上限和协议硬上限 3600 秒三者的最小值。`max_artifact_bytes` 限制 applet / agent / export 等操作可产生或外发的单个 artifact 大小。

## 9. 审批工作流（claim_based, subtype=approval）

### 9.1 预审批

```json
{
  "constraint_type": "claim_based",
  "subtype": "approval",
  "effect": "require_review",
  "approval_required": true,
  "approval_mode": "before_commit",
  "approval_actor_ids": [
    "did:web:manager.example.com"
  ],
  "approval_relation": "controller",
  "timeout": "PT72H",
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
  "approval_threshold": "majority",
  "approval_actor_ids": [
    "did:web:approver1.example.com",
    "did:web:approver2.example.com"
  ]
}
```

### 9.3 Approval signature replay protection（normative）

本节的 **approval signature** 与 [`policy-server.md` §5](./policy-server.md) 的 **policy decision signature** 是两套独立的 replay 防护证据，各有独立的 nonce 命名空间与绑定字段，MUST NOT 互相替代或共享 nonce：approval signature 由 approver DID 签发、绑定 `(grant_id 或 proposal_id, nonce, ...)`，证明"某 approver 批准了该 Move"；policy decision signature 由 Policy Server 签发、绑定 `(request_id, request_canonical_digest, auth_state_digest, ...)`，证明"Policy Server 对该请求给出了某 decision"。一次授权可同时需要两者。

无论是 §9.1 预审批还是 §9.2 提案模式，每个 approval signature 都是 reducer 在判定"目标 Move 是否被批准"时直接消费的密码学证据。为防止同一个 approver 的同一份签名被跨 grant、跨 proposal、跨 request body 重放，approval signature 的 canonical signing input **MUST** 绑定下列字段（缺一即 `invalid_signature`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `grant_id` 或 `proposal_id` | id | 该 approval 所针对的具体 grant id（§9.1 路径）或 proposal Event id（§9.2 路径）。两者互斥，必填其一。 |
| `request_canonical_digest` | hash | 被批准的请求 body 的 [RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785) JSON Canonicalization Scheme (JCS) SHA-256 摘要（`sha256:` 前缀）。同一 approver 给"批准 Alice 写 message X"的签名不能被改写后用于"批准 Alice 写 message Y"。 |
| `approver_did` | did | 签发该 approval 的 actor DID。 |
| `approved_at` | timestamp | 签名时间。reducer MUST 拒绝 `approved_at > now + clock_skew_tolerance` 或 `approved_at < grant.not_before`。此处 `clock_skew_tolerance` 取 [`../conformance/encoding.md`](../conformance/encoding.md) §7.2 两层 drift 模型的硬上界 `hard_future_skew_ms`（默认 300_000，即 5 分钟）——approval 属授权 state event，采用硬上界作为 future-drift reject 边界；实现 MUST NOT 自定义更宽容差。该 5 分钟容差与 [`../crypto-media/media-and-blob.md`](../crypto-media/media-and-blob.md) §3.7 presign TTL 校验采用的 `expected_future_skew_ms`（30 秒软容差）是**不同场景的独立阈值**：presign 是短 TTL bearer URL，取更紧的软容差；approval 取硬上界。两者均锚定 encoding §7.2 同一模型，非冲突。 |
| `nonce` | string | approver 私有的、per-approval 唯一的随机字符串（≥ 128 bit 熵）。reducer MUST 在每个 grant / proposal 范围内拒绝同 `(approver_did, nonce)` 的第二次出现。 |
| `action` | string | 被批准的 capability action token（与 grant `actions[]` 中的元素一致）。 |
| `realm_id` | id | 被批准动作所在的 Realm ID。防止跨 Realm 重放（同一 approver 在 Realm A 的批准不能被用于 Realm B 的同 action）。 |

**Reducer normative**:

1. reducer MUST 校验 approval signature 由 `approver_did` 的当前 active verification method 签发，且 verification method 在 `approved_at` 时间点未被 revoke;
2. reducer MUST 维护 per-(grant_id 或 proposal_id, approver_did) 的 nonce 集合; 同 `(approver_did, nonce)` 的二次提交 MUST 返回 `failed_precondition` reason=`approval_nonce_reused`;
3. `timeout` 过期后，所有未达 threshold 的 approval signature MUST 被视为失效——后续即便补够数量，也 MUST 重新由 approver 在新 nonce 下重签;
4. `approval_mode=before_commit` 与 `approval_mode=proposal_then_approve` 都适用本节; `after_commit_review`(若 profile 注册) 单独定义自己的 replay 边界。

> **理由**: 没有 nonce 与完整 canonical input 绑定时,attacker 可以收集 approver 一次合法批准的签名，把它附加到任意 body hash 相同但语义不同的请求中(canonical hash 碰撞 / 上下文混淆),或把它跨 Realm / 跨 grant 重放。固定 input 集合 + nonce 是 Authority forgery 防线的必要条件。

## 10. 基于声明的约束（claim_based, subtype=claim）

### 10.1 声明要求

```json
{
  "constraint_type": "claim_based",
  "subtype": "claim",
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
  "claim_max_age": "PT24H"
}
```

### 10.2 声明验证

```json
{
  "constraint_type": "claim_based",
  "subtype": "claim",
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
  "approval_threshold": "unanimous"
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
  "key_rotation_period": "P7D",
  "max_key_age": "P30D",
  "require_key_backup": true,
  "approved_key_issuers": [
    "did:web:keys.example.com"
  ]
}
```

**evaluation_class 拆分（normative）**：`confidentiality(encryption)` 约束不是整体 `realm_state`。其纯静态声明部分——`encryption_required` / `min_encryption_level` / `allow_plaintext_fallback` / `require_audit_trail` 这些布尔/枚举标志，以及 `approved_key_issuers` 的列表成员比较（"某 issuer DID 是否在列表中"是封闭集合比较）——只读取 grant 自身内容，求值器 MUST 按 `stateless` 对待，可走 fast path，不得仅因约束 family 是 `confidentiality(encryption)` 就把这些纯静态判定整体降级到 slow path。只有当判定真正需要对照 Realm 当前加密态时——即比较 Realm `encryption_profile` / active Audit Applet Binding，或对照当前 MLS key schedule 判断实际使用的 key issuer 是否落在 `approved_key_issuers` 内——该子判定才是 `realm_state`，按 §2.3 第二行处理。实现 MUST 按子判定的真实依赖分类，而不是按 family 一刀切。

## 13. 可见性控制（confidentiality, subtype=visibility）

### 13.1 对象可见性

```json
{
  "constraint_type": "confidentiality",
  "subtype": "visibility",
  "effect": "allow",
  "allowed_history_visibility_values": ["world_readable", "shared", "invited", "joined", "restricted"],
  "deny_redacted_history": true
}
```

`allowed_history_visibility_values` 的取值 MUST 来自 `history_visibility` 权威枚举的完整集合：`world_readable`（注意是 `world_readable`，不是 `world`）、`shared`、`invited`、`joined`、`restricted`。上例列出全部五个合法值以展示权威枚举；实际 grant 中 `allowed_history_visibility_values` 通常只声明该枚举的一个**子集**（例如 `["world_readable", "shared", "joined"]`）来限制 actor 可访问的对象/消息可见性级别，未列入的级别即不被该约束允许。出现枚举外的值（如 `world`）时 receiver MUST `schema_violation`。

## 14. 其它常用示例

### 14.1 Blob 大小限制

```json
{
  "constraint_type": "quota",
  "subtype": "resource",
  "effect": "allow",
  "blob_max_bytes": 10485760,
  "max_total_blob_bytes": 104857600,
  "constraint_scope": "per_space"
}
```

`blob_max_bytes` 限制单次上传 blob 的最大字节数。`max_total_blob_bytes` 限制 `constraint_scope` 内的累计 blob 大小。

### 14.2 消息编辑窗口与撤回窗口

规范形是两条独立约束（各自 `subtype` + `applies_to_actions`，与 §2.2 表一致）：

```json
[
  {
    "constraint_type": "temporal",
    "subtype": "edit_window",
    "applies_to_actions": ["ck.message.revise.own"],
    "effect": "allow",
    "message_edit_window": "PT15M",
    "allow_redact_after_window": true
  },
  {
    "constraint_type": "temporal",
    "subtype": "redact_window",
    "applies_to_actions": ["ck.message.redact.own"],
    "effect": "allow",
    "message_redact_window": "PT24H"
  }
]
```

**字段语义**：

- `message_edit_window`：发送后可编辑消息（`ck.message.revise.own`）的时间窗口，从被编辑 Message 的 `created_at` 起算。
- `message_redact_window`：发送后可撤回消息（`ck.message.redact.own`）的时间窗口，从被撤回 Message 的 `created_at` 起算。
- `allow_redact_after_window`（默认 `false`）：控制**编辑窗口关闭后撤回是否仍被允许**。它只在约束声明了 `message_edit_window` 时有意义：
  - `false`（默认）：未单独声明 `message_redact_window` 时，撤回与编辑共享同一时窗——编辑窗口过期后 `ck.message.redact.own` 一并被拒。
  - `true`：编辑窗口过期后仍允许撤回（典型"消息可删但不可改"产品语义）；此时撤回判定回退到 `message_redact_window`（若声明）或无上限（若未声明）。
  - 当 `message_redact_window` 已显式声明时，它对撤回具有权威性，`allow_redact_after_window` 不再改变撤回判定（上例中 `PT24H` 是权威撤回窗，`allow_redact_after_window=true` 仅显式表达"撤回不被 15 分钟编辑窗连带锁死"）。

**双窗口与 subtype**：一个 `temporal` 约束 MAY 同时携带 `message_edit_window` 与 `message_redact_window`；其 `subtype` 取 `edit_window` 或 `redact_window` 之一，`applies_to_actions` MUST 列出它治理的全部 action。求值器按字段各自对应的 action enforce（`message_edit_window` → `ck.message.revise.own`；`message_redact_window` → `ck.message.redact.own`），与 `subtype` 标签本身无关。等价地，部署 MAY 把两者拆成两条独立约束（`subtype=edit_window` 一条 + `subtype=redact_window` 一条）。两种写法语义一致。

**超时行为**：窗口超时后 `ck.message.revise.own` 或 `ck.message.redact.own` MUST 被拒绝（`failed_precondition`），**除非** actor 持有更高权限的 `ck.message.revise` 或 `ck.message.redact`（不带 `.own` 后缀，典型是 moderator / admin）——后者不受 `.own` 时窗约束，使管理员可在窗口外撤回。

**无时限（unbounded）**：不在任何生效 grant 上声明 `message_redact_window`（且无 `allow_redact_after_window=false` 把撤回连带锁进编辑窗）即等价"撤回无时限"——`ck.message.redact.own` 仅受 capability 本身约束，不受时间限制。Realm 管理员据此可在"设最大撤回时限"（声明 `message_redact_window`）与"无时限"（省略）之间选择；编辑窗口同理。该约束族为 `extension` 类（profile `ck.profile.chat_mvp.v1`），未启用该 profile 的实现遇到这些字段 MUST fail closed（见 §2.2）。

求值器对这些字段的 enforce 义务由 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中对应 action 的 `required_constraints` 声明（`ck.message.revise.own` → `message_edit_window`；`ck.message.redact.own` → `message_redact_window`）。非 `.own` 的 `ck.message.revise` / `ck.message.redact` 可由 Realm policy 或 grant 自行声明更窄 temporal constraint，但 v1 core 不把自助窗口作为管理员 / moderator action 的 mandatory constraint。

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
- 当 `deny` / `quarantine` / `require_review` 三类 effect 同时命中时，按 §15.1 的步骤顺序**短路求值（short-circuit order）**返回首个命中的类别（deny → quarantine → require_review）。这是确定性的求值短路顺序，**不是**跨 effect 的"优先级 / 权重"裁决——与 §15 / §15.1 "没有优先级参与裁决"一致：每个 effect 类别内部仍是"任一命中即生效"的全或无判断，短路顺序只决定多类别同时命中时先报告哪一个。
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

实现 SHOULD 按 §2.3 的 `evaluation_class` 分组：先跑 `stateless` 与 `grant_local` 的 fast path（命中即可短路返回 DENIED / QUARANTINED / REQUIRES_REVIEW），再跑 `realm_state` 与 `external` 的 slow path（必要时走异步 / 缓存绑定 frontier）。`external` 类约束 MUST NOT 缓存。

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
        allow = constraint.allowed_read_fields
        deny = constraint.denied_read_fields
        fields = operation.read_fields
    else:
        allow = constraint.allowed_write_fields
        deny = constraint.denied_write_fields
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

#### 16.2.1 敏感字段处理（normative）

`field_access` 的 `sensitive_fields` / `sensitive_handling` 是**读路径义务**，不是 admit/deny gate：`matches_field_access` 返回 `true` 后，产生 read projection 的一方（projection 服务、受托查询节点或客户端读模型层；E2EE Realm 中为持有明文的成员侧）在向请求方返回结果之前 **MUST** 对命中 `sensitive_fields`（按 §4.3 的 dotted-path 规则匹配）的每个字段按 `sensitive_handling` 处理后才可输出：

- `redact`：以不可逆占位（如 `null` 或 `"[redacted]"`）替换字段值，MUST NOT 返回原值或可逆派生。
- `hash`：以 profile 固定的 keyed/salted digest 替换原值（MUST NOT 使用裸明文哈希，避免低熵字典攻击；摘要构造复用 [`../governance/content-moderation.md` §3.4](../governance/content-moderation.md) 的 keyed/salted digest 纪律）。
- `omit`：从响应中整体删除该字段键。

未声明 `sensitive_handling` 时默认 `omit`。enforce 方无法对某命中字段施加要求的处理（例如无 key 计算 keyed digest）时 **MUST** 降级为 `omit` 而非返回原值。该义务的一致性向量尚待补充(见 [`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md))。

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
- 允许的时钟偏差容差 MUST 取 [`../conformance/encoding.md`](../conformance/encoding.md) §（两层 drift 模型）的 `hard_future_skew_ms`（默认 300_000，即 ±5 分钟）作为约束 / claim 时间有效性这一较宽场景的 normative 上界容差；该值与 media-and-blob §5.4.3 presign 的短 TTL 场景容差（`expected_future_skew_ms`，±30s）是**不同场景的两个独立阈值**，均派生自 encoding.md 的同一两层 drift 模型，二者交叉引用、不应被实现各自任取。
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

约束求值结果的可缓存性 MUST 按 §2.3 的 `evaluation_class` 分类决定缓存键，并与 fast-path capability cache 共用授权状态绑定规则：缓存 entry MUST 绑定确定性 `auth_state_digest`（覆盖当前 accepted grant/revoke、membership、policy、必要 claim status、device/session seal 等），MUST NOT 仅以 `(grant_id, operation_type, resource_type)` 之类的 subject/action/resource 三元组为键——后者无法在底层授权状态变化时失效，是 [`capabilities.md` §18.1](./capabilities.md) 明令禁止的反模式。

- 缓存键、TTL 与失效语义以 §2.3 evaluation_class 表与 [`capabilities.md` §18.1](./capabilities.md) 的 `auth_state_digest` 绑定为准。
- `external` 类约束 MUST NOT 缓存（见 §2.3 / §15.3）。

#### 18.1.1 `depends_on_moderation_state`（缓存依赖标记，非求值约束）

`depends_on_moderation_state` 是 constraint object 上的一个 **boolean 缓存失效 hint**，**不是** §2.2 的 8 个 constraint family 之一，也不参与 §15 的 allow/deny 求值。它的唯一作用是声明“本 grant 的授权决策是否依赖 `ck.component.moderation_state.v1` cell（见 [`policy-server.md` §7.1](./policy-server.md)）”，从而决定该 cell 变化时是否 MUST 让 grant 的 fast-path cache entry 失效。

- 默认 `false`：普通 grant（`ck.strand.update` / `ck.message.create` / 组织成员 grant 等）不因每次 moderation 决策抖动失效。
- 当满足 [`capabilities.md` §18.1](./capabilities.md) 列出的三类触发条件之一（moderator-role grant、condition-selector subject 引用 moderation state、constraint 引用 moderation queue / cell）时，`constraints[]` 中 MUST 显式包含 `depends_on_moderation_state=true`，缺失即 `schema_violation`。其中“条件 (2)（`actions[]` 含 moderation 写入动作）”由 [`capability-grant.schema.json`](../../artifacts/schemas/capability-grant.schema.json) 的 `if/then` 静态强制；条件 (1)、(3) 为 reducer-side lint。
- 归属：在 [`capabilities.md` §6](./capabilities.md) 约束清单与映射表中登记于“moderation 缓存依赖标记”分组（不归入任一 constraint family）；机读权威源为 [`grant-constraint.schema.json`](../../artifacts/schemas/grant-constraint.schema.json) 的 `depends_on_moderation_state` 属性。
- 一个 `{"depends_on_moderation_state": true}` 不需要 `constraint_type`/`effect` 之外的求值语义；它与同一 grant 内的其它 typed constraint 并列承载，仅供缓存失效引擎读取。

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
  "grant_id": "ck:grant:...",
  "subject": "did:web:agent.example.com",
  "actions": ["ck.object.read", "ck.strand.create", "ck.morph.create"],
  "resources": [
    {
      "kind": "strand",
      "realm_id": "ck:realm:...",
      "strand_id": "*"
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
      "allowed_object_types": ["strand"]
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "allowed_write_fields": ["metadata.title", "metadata.fields.review_status", "metadata.fields.priority"]
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
        "days": ["sat", "sun"],
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
[`../models/governance-objects.md` §4](../models/governance-objects.md) 与
[`artifacts/schemas/capability-grant.schema.json`](../../artifacts/schemas/capability-grant.schema.json)
为准；下述示例展示 grant 上下文中的典型 typed constraint 组合，不引入新规则。

> Grant 撤销 MUST 表达为 accepted `ck.capability.revoke` Event 指向 `ck:grant:<uuid>`；
> Cokret v1 不注册 `ck:revocation-list:*` typed ID。

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
    "allowed_write_fields": ["metadata.title", "metadata.fields.review_status"]
  },
  {
    "constraint_type": "type_restriction",
    "effect": "allow",
    "allowed_object_types": ["strand", "morph", "space"],
    "allowed_space_kinds": ["board", "list"],
    "allowed_morph_types": ["document", "customer_case"],
    "allowed_facets": ["stateful", "replyable"]
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
      "claim_type": "cokret_org_membership_credential",
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
  "approval_mode": "before_commit",
  "approval_actor_ids": ["did:web:manager.example"],
  "approval_threshold": "quorum",
  "timeout": "PT24H",
  "reason_required": true
}
```

#### 20.3.4 Delegation 控制

```json
{
  "constraint_type": "delegation_control",
  "effect": "allow",
  "max_delegation_depth": 1,
  "delegation_scope": "narrowing_only"
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
  "allowed_relation_kinds": ["contains"],
  "allowed_view_ids": ["ck:view:019641be-0000-7000-8000-000000000000"],
  "allowed_from_container_refs": ["ck:space:019640c0-8000-7000-8000-000000000000"],
  "allowed_to_container_refs": ["ck:space:019640c1-0000-7000-8000-000000000000"],
  "wip_limit_override": false
}
```

规则：

- `allowed_relation_kinds` 限定可移动的 Relation 类型，避免 `assigned_to`、
  `depends_on` 和 `contains` 被同一宽泛授权混用。
- `allowed_from_container_refs` 与 `allowed_to_container_refs` 分别限制可移出
  和可移入的列 / collection。
- `allowed_view_ids` 限定授权适用的 View；同一个 Strand item 出现在多个 View
  时不得自动继承移动权。
- `wip_limit_override=false` 时，若目标列 `wip_limit_enforcement` 为 `reject`
  或 `require_review`，移动必须失败或进入审批路径。
