# 资源选择器语法

## 1. 概述

本规范定义 Contrix v1 capability 授权中的资源选择器。资源选择器定义能力授权适用的目标对象范围。

Contrix v1 不再使用 `entity` 作为通用资源选择器。标准对象使用明确类型选择器；开放扩展对象使用 `morph` 选择器；需要跨对象类型表达时使用 `object` 选择器。

## 2. 语法定义

### 2.1 EBNF 语法

```ebnf
selector             ::= space_selector
                      | room_selector
                      | board_selector
                      | list_selector
                      | card_selector
                      | message_selector
                      | morph_selector
                      | relation_selector
                      | view_selector
                      | object_selector
                      | wildcard_selector
                      | conjunction_selector
                      | disjunction_selector

space_selector       ::= "space" ":" space_id
                      | "space" ":" "*"

room_selector        ::= "room" ":" space_id ":" room_id
                      | "room" ":" space_id ":*"
                      | "room" ":" "*"

board_selector       ::= "board" ":" space_id ":" board_id
                      | "board" ":" space_id ":*"
                      | "board" ":" "*"

list_selector        ::= "list" ":" space_id ":" board_id ":" list_id
                      | "list" ":" space_id ":" board_id ":*"
                      | "list" ":" space_id ":*"

card_selector        ::= "card" ":" space_id ":" card_id
                      | "card" ":" space_id ":*"
                      | "card" ":" "*" ":" card_id
                      | "card" ":" "*"

message_selector     ::= "message" ":" space_id ":" room_id ":" message_id
                      | "message" ":" space_id ":" room_id ":*"
                      | "message" ":" space_id ":*"

morph_selector       ::= "morph" ":" space_id ":" morph_type
                      | "morph" ":" space_id ":" morph_id
                      | "morph" ":" "*" ":" morph_type
                      | "morph" ":" space_id ":*"

relation_selector    ::= "relation" ":" space_id ":" relation_kind
                      | "relation" ":" "*" ":" relation_kind

view_selector        ::= "view" ":" space_id ":" view_id
                      | "view" ":" space_id ":*"

object_selector      ::= "object" ":" space_id ":" object_type
                      | "object" ":" space_id ":" object_ref
                      | "object" ":" "*" ":" object_type
                      | "object" ":" space_id ":*"

wildcard_selector    ::= "*"
                      | "space" ":" "*"

conjunction_selector ::= selector "+" selector

disjunction_selector ::= selector "," selector
```

### 2.2 词法规则

- `space_id`：`cx:space:` 后接 ULID。
- `room_id`：`cx:room:` 后接 ULID。
- `board_id`：`cx:board:` 后接 ULID。
- `list_id`：`cx:list:` 后接 ULID。
- `card_id`：`cx:card:` 后接 ULID。
- `message_id`：`cx:message:` 后接 ULID。
- `morph_id`：`cx:morph:` 后接 ULID。
- `morph_type`：Space schema 中注册的开放对象类型。
- `object_type`：标准对象类型或 `morph`。
- `object_ref`：任一 canonical object id。
- `relation_kind`：字符串标识符，例如 `contains`、`assigned_to`、`links_room`。
- `view_id`：`cx:view:` 后接 ULID。
- 空白字符被忽略（引号内字符串除外）。

## 3. 选择器求值

### 3.1 Space 选择器

`space:cx:space:01JS0SP000000000000000000`

- 匹配：特定 Space。
- 适用：该 Space 中的所有标准对象、Morph、Relation、Event 和 View。

`space:*`

- 匹配：所有 Space。
- 配合：`max_delegation_depth=0`、短有效期和审批约束，防止意外扩展。

### 3.2 标准对象选择器

`card:cx:space:...:*`

- 匹配：该 Space 中所有 Card。
- 不匹配：Room、Message、Morph 或其他对象。

`card:cx:space:...:cx:card:01JS0CARD000000000000000`

- 匹配：特定 Card。
- 最高特异性。

`room:cx:space:...:*`

- 匹配：该 Space 中所有 Room。
- 注意：Room 读取和写入仍必须通过 Room membership / history visibility / E2EE 检查。

`message:cx:space:...:cx:room:...:*`

- 匹配：某个 Room 内所有 Message。
- 不授予 Card 权限，即使该 Room 被某 Card 链接。

### 3.3 Morph 选择器

`morph:cx:space:...:memory`

- 匹配：该 Space 中所有 `morph_type=memory` 的 Morph。
- 不匹配：标准 Message 或 Card。

`morph:cx:space:...:cx:morph:01JS0MO000000000000000000`

- 匹配：特定 Morph。

`morph:*:run`

- 匹配：所有可访问 Space 中的所有 `run` Morph。
- 要求：`space:*` 或明确的 Space policy 委托。

### 3.4 Object 选择器

`object` 是跨对象类型的通用选择器，用于授权面确实需要同时覆盖多类对象的情况。实现 SHOULD 优先使用更具体的 `room`、`card`、`message` 或 `morph` 选择器。

`object:cx:space:...:card`

- 匹配：该 Space 中所有 `type=card` 的对象。

`object:cx:space:...:cx:card:01JS0CARD000000000000000`

- 匹配：给定对象引用。

### 3.5 Relation 选择器

`relation:cx:space:...:links_room`

- 匹配：该 Space 中所有 `links_room` 关系。
- 注意：创建或读取 Card-to-Room relation 不授予目标 Room 内容访问权。

`relation:*:assigned_to`

- 匹配：所有可访问 Space 中的所有 `assigned_to` 关系。

### 3.6 View 选择器

`view:cx:space:...:cx:view:01JS0VW000000000000000000`

- 匹配：特定 View。
- 权限：`read` 允许读取 View 定义，但查询结果仍按底层对象授权裁剪。

`view:cx:space:...:*`

- 匹配：该 Space 中的所有 View。

### 3.7 通配符选择器

`*`

- 匹配：所有可访问上下文中的所有资源。
- 使用：需极其谨慎并设置时间限制。
- 要求：SHOULD 始终包含 `expires_at`、approval constraint 和审计理由。

## 4. 选择器组合

### 4.1 合取 (+)

`space:cx:space:...+card:cx:space:...:*`

- 匹配：特定 Space 中的所有 Card。
- 冗余：Space 已由 Card 选择器隐含。
- 有用：组合不同资源类型或额外环境条件时。

### 4.2 析取 (,)

`space:cx:space:A,space:cx:space:B`

- 匹配：Space A 或 Space B。

`card:cx:space:...:*,room:cx:space:...:*`

- 匹配：该 Space 中的 Card 或 Room。

## 5. JSON 表示

虽然语法定义了字符串选择器，但能力授权的 canonical 表示是 JSON：

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:01JS0SP000000000000000000"
    },
    {
      "kind": "card",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "card_id": "cx:card:01JS0CARD000000000000000"
    },
    {
      "kind": "morph",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "morph_type": "memory"
    }
  ]
}
```

## 6. 匹配算法

给定目标资源和选择器：

```text
function matches(target, selector):
    if selector.kind == "space":
        return target.space_id == selector.space_id or selector.space_id == "*"

    if selector.kind in ["room", "board", "list", "card", "message", "morph"]:
        if target.space_id != selector.space_id and selector.space_id != "*":
            return false
        if target.type != selector.kind:
            return false
        if selector.object_id and target.id != selector.object_id:
            return false
        if selector.morph_type and target.morph_type != selector.morph_type:
            return false
        if selector.board_id and target.board_id != selector.board_id:
            return false
        if selector.room_id and target.room_id != selector.room_id:
            return false
        return true

    if selector.kind == "object":
        if target.space_id != selector.space_id and selector.space_id != "*":
            return false
        if selector.object_ref and target.id != selector.object_ref:
            return false
        if selector.object_type and target.type != selector.object_type:
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

选择器定义授权的资源范围。完整授权需要：

1. **资源匹配**：目标资源必须匹配选择器。
2. **动作匹配**：操作动作必须在授权的 `actions` 数组中。
3. **Room 边界检查**：Room / Message 访问必须额外满足 Room membership、history visibility 和 E2EE key eligibility。
4. **Card-Room link 不传播权限**：Card 可见不代表 linked Room 可读；Room 可读也不代表 linked Card 可写。
5. **约束**：授权中的所有 constraints 必须满足。

## 8. 安全考虑

### 8.1 通配符扩展

`*` 和 `object:*:*` 选择器可能匹配非预期资源。缓解措施：

- 始终配合 `expires_at` 使用。
- 与 `object_type_allow`、`morph_type_allow`、`facet_allow` 约束组合。
- 通配符授权要求管理员审批。
- 审计通配符授权使用。

### 8.2 Facet 限制

Facet 是能力 mixin，不是对象身份。实现不得只因为对象声明了 `replyable`、`assignable` 或 `rankable` facet 就绕过标准对象授权规则。

Facet 选择适合：

- 限定 Morph 类型族的能力范围。
- 在确有需要时为标准对象增加附加能力约束。

### 8.3 选择器注入

验证选择器输入以防止注入攻击：

- 使用定义的语法进行严格解析。
- 拒绝格式错误的选择器。
- 限制选择器复杂度深度。

### 8.4 隐私泄露

过于宽泛的选择器可能暴露私有信息：

- `space:*` 可能暴露非预期 Space。
- `room:*` 可能误授会话历史读取能力。
- 在多租户环境中避免使用全局选择器。
- 使用 Space 和 Room 级别隔离。

## 9. 性能考虑

### 9.1 选择器索引

为高效匹配：

- 按 `space_id` 索引授权（最常见过滤器）。
- 按标准对象 `type` 索引。
- 按 `room_id`、`board_id`、`card_id`、`morph_type` 建立局部索引。
- 单独缓存通配符授权。

### 9.2 求值顺序

按以下顺序求值选择器以优化性能：

1. 精确 `space_id` 匹配。
2. 精确对象 ID 匹配。
3. Room / Board / Card 局部范围匹配。
4. 基于对象类型或 Morph 类型的匹配。
5. Facet 约束匹配。
6. 通配符匹配。

## 10. 示例

### 10.1 基本 Card 授权

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:alice.example.com",
  "actions": ["cx.card.read", "cx.card.update"],
  "resources": [
    {
      "kind": "card",
      "space_id": "cx:space:...",
      "card_id": "cx:card:01JS0CARD000000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "scope": "write",
      "fields": ["title", "status"]
    }
  ]
}
```

### 10.2 Room Message 授权

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:bob.example.com",
  "actions": ["cx.message.create"],
  "resources": [
    {
      "kind": "room",
      "space_id": "cx:space:...",
      "room_id": "cx:room:01JS0ROOM000000000000000"
    }
  ]
}
```

该授权只允许在目标 Room 内发消息，不授予 linked Card 的编辑能力。

### 10.3 Morph 类型授权

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:agent.example.com",
  "actions": ["cx.morph.create", "cx.morph.update"],
  "resources": [
    {
      "kind": "morph",
      "space_id": "cx:space:...",
      "morph_type": "run"
    }
  ],
  "constraints": [
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "facet_allow": ["reviewable", "documentable"]
    }
  ]
}
```

## 11. 一致性

实现 MUST：

- 接受本规范定义的 JSON 资源选择器。
- 支持精确 ID 匹配。
- 支持标准对象类型匹配。
- 支持 Morph 类型匹配。
- 支持 Space 级别通配符。
- 验证选择器结构。
- 对非法选择器返回清晰错误。

实现 SHOULD：

- 优化选择器求值。
- 缓存选择器匹配结果。
- 记录通配符选择器使用。
- 提供选择器解释 / 调试工具。
