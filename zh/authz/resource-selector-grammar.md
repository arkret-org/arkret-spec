# 资源选择器语法

## 1. 概述

本规范定义 Contrix v1 capability 授权中的资源选择器。资源选择器只回答“授权命中哪些资源”，不单独表达动作、字段、branch、claim 或审批约束；这些约束必须由 grant 的 `actions` 与 `constraints` 表达。

Contrix v1 capability 使用以下 canonical resource selector 模型：

- `flow` 是统一协作主对象，默认入口由 branch primary 解析规则得到，不是 selector domain。
- `message` 总是属于某个 Flow 的 `discussion` branch。
- `Space(kind=board)` 与 `Space(kind=list)` 是 Space 的工作流容器形态，不是独立 selector domain。
- `morph` 用于开放扩展对象。
- 跨对象类型授权才使用 `object` selector。

## 2. 语法定义

### 2.1 EBNF 语法

字符串 selector 是 JSON canonical selector 的可读 shorthand。协议签名、hash、registry schema 和 wire grant 以 JSON 表示为准。

```ebnf
selector             ::= disjunction
disjunction          ::= conjunction ("," conjunction)*
conjunction          ::= selector_term ("+" selector_term)*

selector_term        ::= wildcard_selector
                      | space_selector
                      | flow_selector
                      | message_selector
                      | morph_selector
                      | relation_selector
                      | view_selector
                      | event_selector
                      | actor_selector
                      | schema_selector
                      | policy_selector
                      | invite_selector
                      | object_selector
                      | blob_selector
                      | notification_selector
                      | read_marker_selector

wildcard_selector    ::= "*"

space_selector       ::= "space" ":" (space_id | "*")

flow_selector        ::= "flow" ":" space_part ":" (flow_id | "*")

message_selector     ::= "message" ":" space_part ":" flow_part ":" (message_id | "*")

morph_selector       ::= "morph" ":" space_part ":" (morph_id | morph_type | "*")

relation_selector    ::= "relation" ":" space_part ":" (relation_id | relation_kind | "*")

view_selector        ::= "view" ":" space_part ":" (view_id | "*")

event_selector       ::= "event" ":" space_part ":" (event_id | "*")

actor_selector       ::= "actor" ":" (did | "*")

schema_selector      ::= "schema" ":" (schema_id | "*")

policy_selector      ::= "policy" ":" space_part ":" (policy_id | "*")

invite_selector      ::= "invite" ":" space_part ":" (invite_id | "*")

object_selector      ::= "object" ":" space_part ":" (object_ref | object_type | "*")

blob_selector        ::= "blob" ":" (blob_ref | "*")

notification_selector ::= "notification" ":" space_part ":" "*"

read_marker_selector ::= "read_marker" ":" space_part ":" "*"

space_part           ::= space_id | "*"
flow_part            ::= flow_id | "*"
```

**运算符优先级**：`+`（合取/AND）优先级高于 `,`（析取/OR）。即 `a+b,c` 解析为 `(a AND b) OR c`。需要表达 `a AND (b OR c)` 时，MUST 使用 JSON canonical selector 或在字符串 shorthand 中拆分为独立 selector。

### 2.2 词法规则

- `space_id`：`cx:space:` 后接 ULID。
- `flow_id`：`cx:flow:` 后接 ULID。
- `message_id`：`cx:message:` 后接 ULID。
- `morph_id`：`cx:morph:` 后接 ULID。
- `relation_id`：`cx:relation:` 后接 ULID。
- `view_id`：`cx:view:` 后接 ULID。
- `event_id`：`cx:event:` 后接 ULID。
- `policy_id`：`cx:policy:` 后接 ULID。
- `invite_id`：`cx:invite:` 后接 ULID。
- `schema_id`：schema registry id，例如 `cx.schema.flow.v1` 或反向域名 schema id。
- `did`：DID URI。
- `blob_ref`：Blob typed ID，wire form 为 `cx` blob 前缀后接 ULID，或 content-addressed sha256 blob ref。
- `morph_type`：Space schema 中注册的开放对象类型。
- `relation_kind`：关系类型，例如 `contains`、`assigned_to`、`promoted_from_discussion`、`summarized_from`。
- `object_type`：标准对象类型或 `morph`。
- `object_ref`：任一 canonical object id。
- 空白字符被忽略，引号内字符串除外。

## 3. Canonical JSON 表示

Capability grant 的 canonical 表示必须使用 JSON resource selector。字符串 selector 只能用于 UI、CLI、日志和测试说明。

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:01js0sp0000000000000000000"
    },
    {
      "kind": "flow",
      "space_id": "cx:space:01js0sp0000000000000000000",
      "flow_id": "cx:flow:01js0ca1000000000000000000"
    },
    {
      "kind": "morph",
      "space_id": "cx:space:01js0sp0000000000000000000",
      "morph_type": "customer_case"
    }
  ],
  "constraints": [
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "object_type_allow": ["flow"],
      "allowed_branches": ["synthesis"]
    }
  ]
}
```

### 3.1 Board/List 选择

Board 与 List 使用 `kind="space"` 选择器，再用约束限制 Space kind 或具体容器引用。实现 MUST NOT 接受 `kind="board"` 或 `kind="list"` 作为 canonical resource selector kind。

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:01js0bd0000000000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "space_kind_allow": ["board"]
    }
  ]
}
```

List 内 item 移动 SHOULD 同时约束 `allowed_from_container_refs`、`allowed_to_container_refs`、`relation_kind_allow` 或对应 flow move payload 字段。

### 3.2 Flow branch 选择

Flow 的 synthesis / discussion 能力面使用 `kind="flow"` 选择器，再用 `allowed_branches` 限制 branch 范围。实现 MUST NOT 接受 card 或 room 作为 canonical resource selector domain。

```json
{
  "resources": [
    {
      "kind": "flow",
      "space_id": "cx:space:01js0sp0000000000000000000",
      "flow_id": "cx:flow:01js0ca1000000000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "allowed_branches": ["discussion"]
    }
  ]
}
```

`allowed_branches=["discussion"]` 不会自动授予 message 读取或发送能力；message 权限仍必须命中 `cx.message.*` action，并满足有效 branch access、history visibility 和 E2EE key eligibility。

## 4. 选择器求值

### 4.1 Space 选择器

`space:cx:space:01js0sp0000000000000000000`

- 匹配：特定 Space。
- 适用：该 Space 中的对象、Event、View、policy、invite、read marker、notification 和 Blob 引用。
- 不含义：不自动匹配 child Space 的内容，除非 selector 或继承策略明确声明。

`space:*`

- 匹配：所有可评估 Space。
- 要求：SHOULD 始终配合短有效期、`max_delegation_depth=0`、审批和审计理由。

### 4.2 Flow 选择器

`flow:cx:space:...:*`

- 匹配：该 Space 中所有 Flow。
- 若只允许某个 branch 范围，必须使用 `allowed_branches`。

`flow:cx:space:...:cx:flow:01js0ca1000000000000000000`

- 匹配：特定 Flow。
- 不匹配：Message、Morph、Relation、View 或 Board/List 容器。

### 4.3 Message 选择器

`message:cx:space:...:cx:flow:...:*`

- 匹配：某个 Flow `discussion` branch 内的所有 Message。
- 不授予 Flow synthesis 字段写入权限。
- 不绕过 branch-scoped membership、history visibility、redaction 或 E2EE key eligibility。

### 4.4 Morph 选择器

`morph:cx:space:...:customer_case`

- 匹配：该 Space 中所有 `morph_type=customer_case` 的 Morph。
- 不匹配：标准 Flow、Message 或 Relation。

`morph:cx:space:...:cx:morph:01js0m00000000000000000000`

- 匹配：特定 Morph。

### 4.5 Object 选择器

`object` 是跨对象类型的通用选择器，只应在授权面确实需要同时覆盖多类对象时使用。实现 SHOULD 优先使用更具体的 `space`、`flow`、`message`、`morph`、`relation` 或 `view` selector。

`object:cx:space:...:flow`

- 匹配：该 Space 中所有 `type=flow` 的对象。
- 若只允许某个 branch 范围，必须额外使用 `allowed_branches`。

`object:cx:space:...:cx:flow:01js0ca1000000000000000000`

- 匹配：给定对象引用。

### 4.6 Relation 与 View 选择器

`relation:cx:space:...:contains`

- 匹配：该 Space 中所有 `contains` 关系。
- 不授予被 relation 指向对象的读取权；跨 Space 展开必须重新执行目标 Space 授权。

`view:cx:space:...:cx:view:01js0vw0000000000000000000`

- 匹配：特定 View 定义。
- 查询结果仍按底层对象授权裁剪。

### 4.7 Event、Actor、Policy、Invite 与 Schema 选择器

这些 selector 主要用于管理、审计、schema / policy 更新、邀请和 actor-private 状态：

- `event:<space>:<event_id>` 匹配特定 Event；`event:<space>:*` 匹配 Space 内 Event metadata。读取 Event payload 仍受对象、branch、history、redaction 和 E2EE 约束。
- `actor:<did>` 匹配 principal / service / agent DID；不得匹配 handle、邮箱或 OAuth subject。
- `policy:<space>:<policy_id>` 与 `schema:<schema_id>` 用于 policy / schema 管理授权。
- `invite:<space>:<invite_id>` 用于邀请创建、查看、撤销或接受。

## 5. 选择器组合

### 5.1 合取 (+)

`space:cx:space:...+flow:cx:space:...:*`

- 表示两个 selector 同时命中时才授权。
- 常用于把宽泛 selector 与额外资源范围或环境约束组合。

### 5.2 析取 (,)

`space:cx:space:01js0sa0000000000000000000,space:cx:space:01js0sb0000000000000000000`

- 表示任一 selector 命中即可。

Canonical JSON 中，多个 `resources[]` 的默认语义是 OR；同一 grant 内 constraints 按各自定义求交或 fail-closed。

## 6. 匹配算法

给定目标资源和 selector：

```text
function matches(target, selector):
    if selector.kind == "*":
        return true

    if selector.space_id and selector.space_id != "*" and target.space_id != selector.space_id:
        return false

    if selector.kind == "space":
        return target.type == "space" and (
            selector.space_id == "*" or target.id == selector.space_id or target.space_id == selector.space_id
        )

    if selector.kind == "flow":
        if target.type != "flow":
            return false
        if selector.flow_id and selector.flow_id != target.id:
            return false
        return true

    if selector.kind == "message":
        if target.type != "message":
            return false
        if selector.flow_id and selector.flow_id != "*" and target.flow_id != selector.flow_id:
            return false
        if selector.message_id and selector.message_id != target.id:
            return false
        return true

    if selector.kind == "morph":
        if target.type != "morph":
            return false
        if selector.morph_id and selector.morph_id != target.id:
            return false
        if selector.morph_type and selector.morph_type != target.morph_type:
            return false
        return true

    if selector.kind == "object":
        if selector.object_ref and selector.object_ref != target.id:
            return false
        if selector.object_type and selector.object_type != target.type:
            return false
        return true

    if selector.kind == "relation":
        if target.type != "relation":
            return false
        if selector.relation_id and selector.relation_id != target.id:
            return false
        if selector.relation_kind and selector.relation_kind != target.relation_kind:
            return false
        return true

    if selector.kind == "view":
        return target.type == "view" and (
            not selector.view_id or selector.view_id == target.id
        )

    if selector.kind == "event":
        return target.type == "event" and (
            not selector.event_id or selector.event_id == target.id
        )

    if selector.kind == "actor":
        return target.type == "actor" and (
            selector.actor_id == "*" or selector.actor_id == target.did
        )

    if selector.kind == "policy":
        return target.type == "policy" and (
            not selector.policy_id or selector.policy_id == target.id
        )

    if selector.kind == "invite":
        return target.type == "invite" and (
            not selector.invite_id or selector.invite_id == target.id
        )

    if selector.kind == "schema":
        return target.type == "schema" and (
            selector.schema_ref == "*" or selector.schema_ref == target.schema
        )

    return false
```

Selector match 之后，节点还必须执行 action、constraint、claim、approval、moderation、policy、branch access、history visibility 和 E2EE key eligibility 检查。

## 7. 授权范围

完整授权需要同时满足：

1. **资源匹配**：目标资源必须匹配 selector。
2. **动作匹配**：操作动作必须在授权 `actions` 中，或被明确的通配动作覆盖。
3. **约束匹配**：`space_kind_allow`、`morph_type_allow`、`relation_kind_allow`、`allowed_branches` 等约束必须满足。
4. **Branch access 检查**：Message 和 discussion branch 访问必须满足有效 branch access、history visibility 和 E2EE key eligibility。
5. **跨对象不传播权限**：Relation、View、Flow 和 Message 的互相引用不自动传播读写权。
6. **策略检查**：moderation、retention、legal hold、plaintext-visible service 和 federation policy 不得被 selector 绕过。

## 8. 安全考虑

### 8.1 通配符扩展

`*`、`space:*` 和 `object:*:*` 可能匹配非预期资源。缓解措施：

- 始终配合 `expires_at` 使用。
- 与 `object_type_allow`、`space_kind_allow`、`morph_type_allow`、`facet_allow`、`allowed_branches` 等约束组合。
- 要求管理员审批与审计理由。
- `max_delegation_depth` SHOULD 为 0。

### 8.2 非 canonical selector domain

实现 MUST reject canonical JSON 中的非标准 selector domain，例如 subject、room、card、board 和 list。Flow branch 范围必须使用 `kind="flow"` 加 `allowed_branches`；board / list 容器必须使用 `kind="space"` 加 `space_kind_allow`。

字符串 shorthand 也必须映射到上述 canonical domain；未声明的 selector domain MUST fail closed。

### 8.3 Facet 限制

Facet 是 Space schema / Morph profile 声明后的 hint 或查询标签，不是对象身份，也不是 capability action。实现不得只因为对象声明了 `replyable`、`assignable` 或 `rankable` facet 就绕过标准对象授权规则。

### 8.4 隐私泄露

过宽 selector 可能暴露私有信息：

- `space:*` 可能暴露非预期 Space。
- `flow:*:*` 可能暴露对象存在性。
- `message:*:*:*` 可能误授讨论历史读取能力。
- 在多租户环境中避免使用全局 selector。
- 对 Board/List 容器的授权不得自动升级为父 Space 或 child Space 授权。

## 9. 性能考虑

实现 SHOULD 按以下维度建立 selector 索引：

1. `space_id`
2. `kind`
3. 精确对象 ID，例如 `flow_id`、`message_id`、`morph_id`
4. `morph_type`、`relation_kind`
5. 通配符授权缓存

求值顺序 SHOULD 先做精确 ID 和 `space_id` 裁剪，再执行对象类型、kind、constraint 和 policy 检查。

## 10. 一致性

实现 MUST：

- 接受本规范定义的 JSON resource selector。
- 支持精确 ID、Space、Flow、Message、Morph、Relation、View、Event、Actor、Policy、Invite、Schema 和 Object 匹配。
- 拒绝非 canonical selector kind：`subject`、`room`、`card`、`board`、`list`。
- 对非法 selector 返回清晰错误。
- 在 selector 命中后继续执行 action、constraint、claim、policy、branch access 和 E2EE 检查。

实现 SHOULD：

- 提供 selector 解释 / 调试工具。
- 缓存 selector 匹配结果。
- 记录通配符 selector 使用。
