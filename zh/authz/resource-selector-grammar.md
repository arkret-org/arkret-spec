# 资源选择器语法

## 1. 概述

本规范定义了 Contrix v1 能力授权中资源选择器的形式语法。资源选择器定义了能力授权适用的目标对象。

## 2. 语法定义

### 2.1 EBNF 语法

```ebnf
selector            ::= space_selector
                     | entity_selector
                     | relation_selector
                     | view_selector
                     | wildcard_selector
                     | conjunction_selector
                     | disjunction_selector

space_selector      ::= "space" ":" space_id
                     | "space" ":" "*"

entity_selector     ::= "entity" ":" space_id ":" entity_type
                     | "entity" ":" space_id ":" entity_id
                     | "entity" ":" "*" ":" entity_type
                     | "entity" ":" space_id ":*"

relation_selector   ::= "relation" ":" space_id ":" relation_kind
                     | "relation" ":" "*" ":" relation_kind

view_selector       ::= "view" ":" space_id ":" view_id
                     | "view" ":" space_id ":*"

wildcard_selector   ::= "*"
                     | "space" ":" "*"

conjunction_selector ::= selector "+" selector

disjunction_selector ::= selector "," selector
```

### 2.2 词法规则

- `space_id`：`cx:space:` 后接 ULID
- `entity_id`：`cx:entity:` 后接 ULID
- `entity_type`：字符串标识符（如 `task`、`message`、`board`）
- `relation_kind`：字符串标识符（如 `contains`、`assigned_to`）
- `view_id`：`cx:view:` 后接 ULID
- 空白字符被忽略（引号内字符串除外）

## 3. 选择器求值

### 3.1 Space 选择器

`space:cx:space:01JS0SP000000000000000000`

- 匹配：特定 Space
- 适用：该 Space 中的所有实体、关系、事件

`space:*`

- 匹配：所有 Space
- 配合：`max_delegation_depth=0` 以防止意外扩展

### 3.2 实体选择器

`entity:cx:space:...:task`

- 匹配：该 Space 中所有 `entity_type=task` 的实体
- 不匹配：其他实体类型

`entity:cx:space:...:cx:entity:01JS0EN000000000000000000`

- 匹配：特定实体
- 最高特异性

`entity:*:task`

- 匹配：所有可访问 Space 中的所有 `task` 实体
- 要求：`space:*` 或 Space policy 委托

`entity:cx:space:...:*`

- 匹配：该 Space 中的所有实体
- 等价于：对实体操作使用 `space:cx:space:...`

### 3.3 关系选择器

`relation:cx:space:...:assigned_to`

- 匹配：该 Space 中所有 `assigned_to` 关系
- 适用：读取和创建这些关系

`relation:*:assigned_to`

- 匹配：所有可访问 Space 中的所有 `assigned_to` 关系

### 3.4 视图选择器

`view:cx:space:...:cx:view:01JS0VW000000000000000000`

- 匹配：特定视图
- 权限：`read` 允许读取视图定义

`view:cx:space:...:*`

- 匹配：该 Space 中的所有视图

### 3.5 通配符选择器

`*`

- 匹配：所有可访问上下文中的所有资源
- 使用：需极其谨慎并设置时间限制
- 应：始终包含 `expires_at`

## 4. 选择器组合

### 4.1 合取 (+)

`space:cx:space:...+entity:cx:space:...:task`

- 匹配：特定 Space 中的 Task 实体
- 冗余：Space 已由实体选择器隐含
- 有用：组合不同资源类型时

### 4.2 析取 (,)

`space:cx:space:A,space:cx:space:B`

- 匹配：Space A 或 Space B
- 适用：两个 Space 中的所有资源

`entity:cx:space:...:task,entity:cx:space:...:message`

- 匹配：该 Space 中的 Task 或 Message

## 5. JSON 表示

虽然语法定义了字符串选择器，但能力授权使用 JSON：

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:01JS0SP000000000000000000"
    },
    {
      "kind": "entity",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "entity_type": "task"
    },
    {
      "kind": "entity",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "entity_id": "cx:entity:01JS0EN000000000000000000"
    }
  ]
}
```

## 6. 匹配算法

给定目标资源和选择器：

```
function matches(target, selector):
    if selector.kind == "space":
        return target.space_id == selector.space_id or selector.space_id == "*"

    if selector.kind == "entity":
        if target.space_id != selector.space_id and selector.space_id != "*":
            return false
        if selector.entity_id and target.entity_id != selector.entity_id:
            return false
        if selector.entity_type and target.entity_type != selector.entity_type:
            return false
        return true

    if selector.kind == "relation":
        if target.space_id != selector.space_id and selector.space_id != "*":
            return false
        if selector.relation_kind and target.relation_kind != selector.relation_kind:
            return false
        return true

    # 其他 kind 的类似逻辑...
```

## 7. 授权范围

选择器定义了授权的**资源范围**。完整授权需要：

1. **资源匹配**：目标资源必须匹配选择器
2. **动作匹配**：操作动作必须在授权的 `actions` 数组中
3. **约束**：授权中的所有约束必须满足

## 8. 安全考虑

### 8.1 通配符扩展

`*` 选择器可能匹配非预期资源。缓解措施：

- 始终配合 `expires_at` 使用
- 与 `entity_type_allow` 约束组合
- 通配符授权要求管理员审批
- 审计通配符授权使用

### 8.2 选择器注入

验证选择器输入以防止注入攻击：

- 使用定义的语法进行严格解析
- 拒绝格式错误的选择器
- 限制选择器复杂度深度

### 8.3 隐私泄露

过于宽泛的选择器可能暴露私有信息：

- `*` 选择器可能暴露非预期 Space
- 在多租户环境中避免使用
- 使用 Space 级别隔离

## 9. 性能考虑

### 9.1 选择器索引

为高效匹配：

- 按 `space_id` 索引授权（最常见过滤器）
- 按 `entity_type` 索引（常见约束）
- 单独缓存通配符授权

### 9.2 求值顺序

按以下顺序求值选择器以优化性能：

1. 精确 `space_id` 匹配（最快）
2. 精确 `entity_id` 匹配
3. 基于类型的匹配
4. 通配符匹配（最慢）

## 10. 示例

### 10.1 基本 Task 授权

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:alice.example.com",
  "actions": ["read", "update"],
  "resources": [
    {
      "kind": "entity",
      "space_id": "cx:space:...",
      "entity_type": "task"
    }
  ],
  "constraints": {
    "fields_write_allow": ["title", "status"]
  }
}
```

### 10.2 多 Space 授权

```json
{
  "resources": [
    {"kind": "space", "space_id": "cx:space:A"},
    {"kind": "space", "space_id": "cx:space:B"}
  ]
}
```

### 10.3 特定实体授权

```json
{
  "resources": [
    {
      "kind": "entity",
      "space_id": "cx:space:...",
      "entity_id": "cx:entity:01JS0EN000000000000000000"
    }
  ]
}
```

## 11. 迁移路径

使用较简单字符串选择器的实现：

1. **阶段 1**：同时支持字符串和 JSON 选择器
2. **阶段 2**：新授权中使用 JSON 选择器
3. **阶段 3**：弃用字符串选择器格式

## 12. 一致性

实现 MUST：

- 接受本规范定义的 JSON 资源选择器
- 支持精确 ID 匹配
- 支持基于类型的匹配
- 支持 space 级别通配符
- 验证选择器结构
- 对非法选择器返回清晰错误

实现 SHOULD：

- 优化选择器求值
- 缓存选择器匹配结果
- 记录通配符选择器使用
- 提供选择器解释/调试工具
