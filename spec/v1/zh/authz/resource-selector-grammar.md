---
title: 资源选择器语法
---

## 1. 概述

本规范定义 Contrix v1 capability 授权中的资源选择器。资源选择器只回答“授权命中哪些资源”，不单独表达动作、字段、track、claim 或审批约束；这些约束必须由 grant 的 `actions` 与 `constraints` 表达。

Contrix v1 capability 使用以下 canonical resource selector 模型：

- `flow` 是统一协作主对象，默认入口由 track primary 解析规则得到，不是 selector domain。
- `message` 总是属于某个 Flow 的 `discussion` track。
- `Board Space` 与 `List Space` 是 Realm 的工作流容器形态，不是独立 selector domain。
- `morph` 用于开放扩展对象。
- 跨对象类型授权才使用 `object` selector。

## 2. Canonical JSON Resource Selector

**Capability grant 的 canonical / normative 表示是 JSON resource selector**。协议签名、hash、registry
schema、wire grant 与 conformance 测试 MUST 以本节定义的 JSON 形态为准。字符串 shorthand（§3）只是
为 CLI、日志、UI 和文档辅助提供的非 normative 派生形态，不进入签名输入，也不参与一致性判定。

```json
{
  "resources": [
    {
      "kind": "realm",
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000"
    },
    {
      "kind": "flow",
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "flow_id": "cx:flow:019640c5-0400-7000-8000-000000000000"
    },
    {
      "kind": "morph",
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "morph_type": "customer_case"
    }
  ],
  "constraints": [
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "object_type_allow": ["flow"],
      "allowed_tracks": ["synthesis"]
    }
  ]
}
```

### 2.1 Board/List 选择

Board 与 List 使用 `kind="space"` 选择器，配合 `space_kind_allow` 约束限制 Space 形态（`board`、`list` 等 profile 注册的 Space kind）。实现 MUST NOT 接受 `kind="board"` 或 `kind="list"` 作为 canonical resource selector kind；需要把权限范围扩到整个 Realm（覆盖所有 Space）时再使用 `kind="realm"`。

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:019640b6-8000-7000-8000-000000000000"
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

### 2.2 Flow track 选择

Flow 的 synthesis / discussion 能力面使用 `kind="flow"` 选择器，再用 `allowed_tracks` 限制 track 范围。实现 MUST NOT 接受 card 或 room 作为 canonical resource selector domain。

```json
{
  "resources": [
    {
      "kind": "flow",
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "flow_id": "cx:flow:019640c5-0400-7000-8000-000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_type": "type_restriction",
      "effect": "allow",
      "allowed_tracks": ["discussion"]
    }
  ]
}
```

`allowed_tracks=["discussion"]` 不会自动授予 message 读取或发送能力；message 权限仍必须命中 `cx.message.*` action，并在已有 Realm 授权内满足 `allowed_tracks` action scope、history visibility 和 E2EE key eligibility。

## 3. 字符串 Shorthand（可选 CLI / 日志形态，non-normative）

字符串 shorthand 不进入 signature、hash、registry 或 wire grant；它只是把 §2 的 JSON selector 折叠成
单行 ASCII，方便 CLI、admin tool、debug 日志、文档示例与人工 review 阅读。任何 shorthand 解析器的
输出 MUST 等价于一个合法 §2 JSON selector；无法等价映射的 shorthand MUST fail closed。

实现 MAY 完全不实现 shorthand，仅消费 JSON selector；此时 shorthand 仅为人类阅读形态，不构成
互操作要求。下面给出一份 reference EBNF 与词法规则供 CLI 工具实现参考。

### 3.1 EBNF 语法（reference）

```text
selector             ::= disjunction
disjunction          ::= conjunction ("," conjunction)*
conjunction          ::= selector_term ("+" selector_term)*

selector_term        ::= wildcard_selector
                      | realm_selector
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

realm_selector       ::= "realm" ":" (realm_id | "*")

space_selector       ::= "space" ":" (space_id | "*")

flow_selector        ::= "flow" ":" realm_part ":" (flow_id | "*")

message_selector     ::= "message" ":" realm_part ":" flow_part ":" (message_id | "*")

morph_selector       ::= "morph" ":" realm_part ":" (morph_id | morph_type | "*")

relation_selector    ::= "relation" ":" realm_part ":" (relation_id | relation_kind | "*")

view_selector        ::= "view" ":" realm_part ":" (view_id | "*")

event_selector       ::= "event" ":" realm_part ":" (event_id | "*")

actor_selector       ::= "actor" ":" (did | "*")

schema_selector      ::= "schema" ":" (schema_id | "*")

policy_selector      ::= "policy" ":" realm_part ":" (policy_id | "*")

invite_selector      ::= "invite" ":" realm_part ":" (invite_id | "*")

object_selector      ::= "object" ":" realm_part ":" (object_ref | object_type | "*")

blob_selector        ::= "blob" ":" (blob_ref | "*")

notification_selector ::= "notification" ":" realm_part ":" "*"

read_marker_selector ::= "read_marker" ":" realm_part ":" "*"

realm_part           ::= realm_id | "*"
flow_part            ::= flow_id | "*"
```

**运算符优先级**：`+`（合取/AND）优先级高于 `,`（析取/OR）。即 `a+b,c` 解析为 `(a AND b) OR c`。需要表达 `a AND (b OR c)` 时，MUST 使用 §2 JSON canonical selector，不得仅用 shorthand 表达。

### 3.2 词法规则（reference）

- `realm_id`：`cx:realm:` 后接 UUIDv7。
- `space_id`：`cx:space:` 后接 UUIDv7。
- `flow_id`：`cx:flow:` 后接 UUIDv7。
- `message_id`：`cx:message:` 后接 UUIDv7。
- `morph_id`：`cx:morph:` 后接 UUIDv7。
- `relation_id`：`cx:relation:` 后接 UUIDv7。
- `view_id`：`cx:view:` 后接 UUIDv7。
- `event_id`：`cx:event:` 后接 UUIDv7。
- `policy_id`：`cx:policy:` 后接 UUIDv7。
- `invite_id`：`cx:invite:` 后接 UUIDv7。
- `schema_id`：schema registry id，例如 `cx.schema.flow.v1` 或反向域名 schema id。
- `did`：DID URI。
- `blob_ref`：Blob typed ID，wire form 为 `cx` blob 前缀后接 UUIDv7，或 content-addressed sha256 blob ref。
- `morph_type`：Realm schema 中注册的开放对象类型。
- `relation_kind`：关系类型，例如 `contains`、`assigned_to`、`promoted_from_discussion`、`summarized_from`。
- `object_type`：标准对象类型或 `morph`。
- `object_ref`：任一 canonical object id。
- 空白字符被忽略，引号内字符串除外。

### 3.3 Parser 硬上限（normative，DoS 防护）

资源选择器在 capability evaluation 路径中被频繁解析，恶意构造的嵌套表达式可触发指数级 parser 行为。所有 selector parser（无论是 §2 JSON 形态还是 §3 shorthand 形态）MUST 强制以下硬上限；任何超限输入 MUST fail closed 并返回 `selector_too_complex` error code：

| 限制项 | 上限 | 说明 |
| --- | --- | --- |
| Selector 字符串总长度（shorthand） | 4096 字节 | 超长 shorthand MUST 直接拒绝，不进入 tokenizer。|
| `resources[]` 数组长度（JSON） | 256 项 | 单个 grant 的 resource 集合上限。|
| Disjunction(`,`) / conjunction(`+`) 总 token 数（shorthand） | 256 token | 包括 selector_term + 运算符。|
| Disjunction 分支数 | 16 项 | 逗号分隔的 top-level alternative 数量；超过即 `selector_too_complex`。|
| Conjunction 展开后总项数 | 64 项 | JSON selector 或 shorthand 归一化后的 AND 项总数；防止嵌套组合指数展开。|
| 嵌套深度（任意 selector 树） | 8 层 | 包括逗号 / 加号 / 引用 / 子 selector 嵌套。|
| 单个 `selector_term` 字段值长度 | 1024 字节 | DID、URL、UUIDv7、复合 id 都包含在内。|
| `requires_claims[]` 在 subject selector 中的项数 | 32 项 | 每个 claim object 内部字段亦受单字段上限。|
| `requires_claims[].subjects[]` / DID 列表长度 | 16 项 | 任一 claim object 内按 DID / subject 列表约束展开的对象数量。|
| Constraint object 内嵌套层级 | 4 层 | approval / claim object 内部最多 4 层嵌套。|

实现 MUST 在解析入口先验证 byte-size 与 token-count 上限，再做语法解析；不得让恶意输入进入 EBNF 递归下降。`selector_too_complex` error 必须独立于 `invalid_param`，以便审计层将疑似 DoS 攻击与普通格式错误区分。

`additionalProperties` / 未注册字段不计入嵌套深度，但实现 MUST 对未知字段总数同样设上限（建议同 selector_term 上限 256）以防止 schema 旁路放大攻击面。

## 4. Selector Terms

### 4.1 Realm 选择器

`realm:cx:realm:0196419b-0000-7000-8000-000000000000`

- 匹配：特定 Realm。
- 适用：该 Realm 中的对象、Event、View、policy、invite、read marker、notification 和 Blob 引用。
- 不含义：不自动匹配 linked Realm 的内容，除非 selector 或继承策略明确声明。

`realm:*`

- 匹配：所有可评估 Realm。
- 要求：SHOULD 始终配合短有效期、`max_delegation_depth=0`、审批和审计理由。

### 4.2 Space 选择器

`space:cx:space:019640b6-8000-7000-8000-000000000000`

- 匹配：特定结构 Space。
- 适用：Space metadata、Space lifecycle、Space parent、board/list 类 workflow container 操作。
- 不含义：不自动授予该 Space `default_realm_ref` 指向 Realm 的 membership、history 或 E2EE key；也不自动授予 Space 下资源的读取权，除非资源 selector / action / constraint 同时命中。

`space:*`

- 匹配：所有可评估 Space。
- 要求：SHOULD 配合 `realm_id`、`space_kind_allow`、短有效期和审计理由。

### 4.3 Flow 选择器

`flow:cx:realm:...:*`

- 匹配：该 Realm 中所有 Flow。
- 若只允许某个 track 范围，必须使用 `allowed_tracks`。

`flow:cx:realm:...:cx:flow:019640c5-0400-7000-8000-000000000000`

- 匹配：特定 Flow。
- 不匹配：Message、Morph、Relation、View 或 Board/List 容器。

### 4.4 Message 选择器

`message:cx:realm:...:cx:flow:...:*`

- 匹配：某个 Flow `discussion` track 内的所有 Message。
- 不授予 Flow synthesis 字段写入权限。
- 不绕过 discussion 所属 Realm（源 Realm 或 `discussion_realm_ref` linked Realm）的 membership、history visibility、redaction 或 E2EE key eligibility。

### 4.5 Morph 选择器

`morph:cx:realm:...:customer_case`

- 匹配：该 Realm 中所有 `morph_type=customer_case` 的 Morph。
- 不匹配：标准 Flow、Message 或 Relation。

`morph:cx:realm:...:cx:morph:01964140-0000-7000-8000-000000000000`

- 匹配：特定 Morph。

### 4.6 Object 选择器

`object` 是跨对象类型的通用选择器，只应在授权面确实需要同时覆盖多类对象时使用。实现 SHOULD 优先使用更具体的 `realm`、`flow`、`message`、`morph`、`relation` 或 `view` selector。

`object:cx:realm:...:flow`

- 匹配：该 Realm 中所有 `type=flow` 的对象。
- 若只允许某个 track 范围，必须额外使用 `allowed_tracks`。

`object:cx:realm:...:cx:flow:019640c5-0400-7000-8000-000000000000`

- 匹配：给定对象引用。

### 4.7 Relation 与 View 选择器

`relation:cx:realm:...:contains`

- 匹配：该 Realm 中所有 `contains` 关系。
- 不授予被 relation 指向对象的读取权；跨 Realm 展开必须重新执行目标 Realm 授权。

`view:cx:realm:...:cx:view:019641be-0000-7000-8000-000000000000`

- 匹配：特定 View 定义。
- 查询结果仍按底层对象授权裁剪。

### 4.8 Event、Actor、Policy、Invite 与 Schema 选择器

这些 selector 主要用于管理、审计、schema / policy 更新、邀请和 actor-private 状态：

- `event:<realm>:<event_id>` 匹配特定 Event；`event:<realm>:*` 匹配 Realm 内 Event metadata。读取 Event payload 仍受对象、track、history、redaction 和 E2EE 约束。
- `actor:<did>` 匹配 principal / service / agent DID；不得匹配 handle、邮箱或 OAuth subject。`actor:*` 不是 v1 合法 selector：`resource-selector.schema.json` 要求 `actor_id` 是具体 DID，parser / reducer 若遇到 actor wildcard MUST 以 `schema_violation` + `selector_actor_wildcard_forbidden` 拒绝。
- `policy:<realm>:<policy_id>` 与 `schema:<schema_id>` 用于 policy / schema 管理授权。
- `invite:<realm>:<invite_id>` 用于邀请创建、查看、撤销或接受。

## 5. 选择器组合

### 5.1 合取 (+)

`realm:cx:realm:...+flow:cx:realm:...:*`

- 表示两个 selector 同时命中时才授权。
- 常用于把宽泛 selector 与额外资源范围或环境约束组合。

### 5.2 析取 (,)

`realm:cx:realm:01964195-0000-7000-8000-000000000000,realm:cx:realm:01964195-8000-7000-8000-000000000000`

- 表示任一 selector 命中即可。

Canonical JSON 中，多个 `resources[]` 的默认语义是 OR；同一 grant 内 constraints 按各自定义求交或 fail-closed。

## 6. 匹配算法

给定目标资源和 selector：

```text
function matches(target, selector):
    if selector.kind == "*":
        return true

    if selector.realm_id and selector.realm_id != "*" and target.realm_id != selector.realm_id:
        return false

    if selector.kind == "realm":
        return target.type == "realm" and (
            selector.realm_id == "*" or target.id == selector.realm_id or target.realm_id == selector.realm_id
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
            selector.actor_id == target.did
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

Selector match 之后，节点还必须执行 action、constraint、claim、approval、moderation、policy、`allowed_tracks` action scope、history visibility 和 E2EE key eligibility 检查。

## 7. 授权范围

完整授权需要同时满足：

1. **资源匹配**：目标资源必须匹配 selector。
2. **动作匹配**：操作动作必须逐字出现在授权 `actions[]` 中；`actions[]` 不存在 wildcard / segment 通配。通配只适用于资源 selector，不适用于 action token。
3. **约束匹配**：`space_kind_allow`、`morph_type_allow`、`relation_kind_allow`、`allowed_tracks` 等约束必须满足。`realm_kind_allow` 在 v1 没有规范用途（v1 中所有 Realm 同属一种安全边界），v1 实现 SHOULD 把它视为 always-allow（详见 [`constraint-schema.md` §5](./constraint-schema.md)）。
4. **Track scope 检查**：Message 和 discussion track 访问必须在已有 Realm / capability 授权内满足 `allowed_tracks` action scope、history visibility 和 E2EE key eligibility；track 本身不授予 membership、history 或 E2EE key。
5. **跨对象不传播权限**：Relation、View、Flow 和 Message 的互相引用不自动传播读写权。
6. **策略检查**：moderation、retention、legal hold、plaintext-visible service 和 federation policy 不得被 selector 绕过。

## 8. 安全考虑

### 8.1 通配符扩展

`*`、`realm:*` 和 `object:*:*` 可能匹配非预期资源。`actor:*` 因会把 subject 侧授权扩大到任意 principal / service / agent，v1 明确禁止；若需要跨 actor 群组授权，必须用 subject condition + claim / organization policy 表达，而不是 actor selector 通配。通配缓解措施：

- 始终配合 `expires_at` 使用。
- 与 `object_type_allow`、`space_kind_allow`、`morph_type_allow`、`facet_allow`、`allowed_tracks` 等约束组合（`realm_kind_allow` 在 v1 已无规范用途，组合时按 always-allow 处理）。
- 要求管理员审批与审计理由。
- `max_delegation_depth` SHOULD 为 0。

### 8.2 非 canonical selector domain

实现 MUST reject canonical JSON 中的非标准 selector domain，例如 subject、room、card 等。Flow track 范围必须使用 `kind="flow"` 加 `allowed_tracks`；board / list / 其他结构容器必须使用 `kind="space"` 加 `space_kind_allow`（或在需要 Realm-级范围时用 `kind="realm"`）。

字符串 shorthand 也必须映射到上述 canonical domain；未声明的 selector domain MUST fail closed。

### 8.3 Facet 限制

Facet 是 Realm schema / Morph profile 声明后的 hint 或查询标签，不是对象身份，也不是 capability action。实现不得只因为对象声明了 `replyable`、`assignable` 或 `rankable` facet 就绕过标准对象授权规则。

### 8.4 隐私泄露

过宽 selector 可能暴露私有信息：

- `realm:*` 可能暴露非预期 Realm。
- `flow:*:*` 可能暴露对象存在性。
- `message:*:*:*` 可能误授讨论历史读取能力。
- 在多租户环境中避免使用全局 selector。
- 对 Board/List 容器的授权不得自动升级为源 Realm 或 linked Realm 授权。

## 9. 性能考虑

实现 SHOULD 按以下维度建立 selector 索引：

1. `realm_id`
2. `kind`
3. 精确对象 ID，例如 `flow_id`、`message_id`、`morph_id`
4. `morph_type`、`relation_kind`
5. 通配符授权缓存

求值顺序 SHOULD 先做精确 ID 和 `realm_id` 裁剪，再执行对象类型、kind、constraint 和 policy 检查。

## 10. 一致性

实现 MUST：

- 接受本规范定义的 JSON resource selector。
- 支持精确 ID、Realm、Flow、Message、Morph、Relation、View、Event、Actor、Policy、Invite、Schema 和 Object 匹配。
- 拒绝非 canonical selector kind：`subject`、`room`、`card`、`board`、`list`。
- 对非法 selector 返回清晰错误。
- 在 selector 命中后继续执行 action、constraint、claim、policy、`allowed_tracks` action scope 和 E2EE 检查。

实现 SHOULD：

- 提供 selector 解释 / 调试工具。
- 缓存 selector 匹配结果。
- 记录通配符 selector 使用。
