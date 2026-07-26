---
title: 资源选择器语法
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 概述

本规范定义 Arkret v1 capability 授权中的资源选择器。资源选择器只回答“授权命中哪些资源”，不单独表达动作、字段、track、claim 或审批约束；这些约束必须由 grant 的 `actions` 与 `constraints` 表达。

Arkret v1 capability 使用以下 canonical resource selector 模型：

- `strand` 是统一协作主对象，默认入口由 track primary 解析规则得到，不是 selector domain。
- `message` 总是属于某个 Strand 的 `discussion` track。
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
      "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000"
    },
    {
      "kind": "strand",
      "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
      "strand_id": "ak:strand:019640c5-0400-7000-8000-000000000000"
    },
    {
      "kind": "morph",
      "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
      "morph_kind": "customer_case"
    }
  ],
  "constraints": [
    {
      "constraint_kind": "kind_restriction",
      "effect": "allow",
      "allowed_object_kinds": ["strand"],
      "allowed_tracks": ["synthesis"]
    }
  ]
}
```

### 2.1 Board/List 选择

Board 与 List 使用 `kind="space"` 选择器，配合 `allowed_space_kinds` 约束限制 Space 形态（`board`、`list` 等 profile 注册的 Space kind）。实现 MUST NOT 接受 `kind="board"` 或 `kind="list"` 作为 canonical resource selector kind；需要把权限范围扩到整个 Realm（覆盖所有 Space）时再使用 `kind="realm"`。

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "ak:space:019640b6-8000-7000-8000-000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_kind": "kind_restriction",
      "effect": "allow",
      "allowed_space_kinds": ["board"]
    }
  ]
}
```

List 内 item 移动 SHOULD 同时约束 `allowed_from_container_refs`、`allowed_to_container_refs`、`allowed_relation_kinds` 或对应 strand move payload 字段。

### 2.2 Circle 选择

Circle 使用 `kind="circle"` 选择器，配合 `allowed_circle_ids` constraint 或具体 `circle_id` 限制 Circle-scoped 管理 grant。Circle selector 只表达子事件 / 子消息边界对象本身；它不会替代 Circle membership、history visibility、delivery/query eligibility、MLS-backed Circle 的 epoch eligibility 或 `ak.audit.accessed` 配对要求。

```json
{
  "resources": [
    {
      "kind": "circle",
      "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
      "circle_id": "ak:circle:019640d0-0000-7000-8000-000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_kind": "kind_restriction",
      "effect": "allow",
      "allowed_circle_ids": ["ak:circle:019640d0-0000-7000-8000-000000000000"]
    }
  ]
}
```

### 2.3 Strand track 选择

Strand 的 synthesis / discussion 能力面使用 `kind="strand"` 选择器，再用 `allowed_tracks` 限制 track 范围。实现 MUST NOT 接受 card 或 room 作为 canonical resource selector domain。

```json
{
  "resources": [
    {
      "kind": "strand",
      "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
      "strand_id": "ak:strand:019640c5-0400-7000-8000-000000000000"
    }
  ],
  "constraints": [
    {
      "constraint_kind": "kind_restriction",
      "effect": "allow",
      "allowed_tracks": ["discussion"]
    }
  ]
}
```

`allowed_tracks=["discussion"]` 不会自动授予 message 读取或发送能力；message 权限仍必须命中 `ak.message.*` action，并在已有 Realm 授权内满足 `allowed_tracks` action scope、history visibility 和 E2EE key eligibility。

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
                      | circle_selector
                      | strand_selector
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
                      | read_cursor_selector

wildcard_selector    ::= "*"

realm_selector       ::= "realm" ":" (realm_id | "*")

space_selector       ::= "space" ":" realm_part ":" (space_id | "*")

circle_selector      ::= "circle" ":" realm_part ":" (circle_id | "*")

strand_selector        ::= "strand" ":" realm_part ":" (strand_id | "*")

message_selector     ::= "message" ":" realm_part ":" strand_part ":" (message_id | "*")

morph_selector       ::= "morph" ":" realm_part ":" (morph_id | morph_kind | "*")

relation_selector    ::= "relation" ":" realm_part ":" (relation_id | relation_kind | "*")

view_selector        ::= "view" ":" realm_part ":" (view_id | "*")

event_selector       ::= "event" ":" realm_part ":" (event_id | "*")

actor_selector       ::= "actor" ":" did
                      (* actor wildcard 非法：`actor:*` MUST schema_violation，见 §4.8 / §8.1 *)

schema_selector      ::= "schema" ":" (schema_ref | "*")

policy_selector      ::= "policy" ":" realm_part ":" (policy_id | "*")

invite_selector      ::= "invite" ":" realm_part ":" (invite_id | "*")

object_selector      ::= "object" ":" realm_part ":" (object_ref | object_kind | "*")

blob_selector        ::= "blob" ":" (blob_ref | "*")

notification_selector ::= "notification" ":" realm_part ":" "*"

read_cursor_selector ::= "read_cursor" ":" realm_part ":" "*"

realm_part           ::= realm_id | "*"
strand_part            ::= strand_id | "*"
```

**运算符优先级**：`+`（合取/AND）优先级高于 `,`（析取/OR）。即 `a+b,c` 解析为 `(a AND b) OR c`。需要表达 `a AND (b OR c)` 时，MUST 使用 §2 JSON canonical selector，不得仅用 shorthand 表达。

Shorthand 中位于对象-id 位置的 `*` 只表示“省略对应 canonical id 字段”，绝不是 canonical JSON 的字段值。例如 `strand:<realm>:*` 解析为 `{"kind":"strand","realm_id":<realm>}`，MUST NOT 产生 `"strand_id":"*"`。同理适用于 `space_id`、`circle_id`、`message_id`、`morph_id`、`relation_id`、`view_id`、`event_id`、`policy_id`、`invite_id` 与 `object_ref`。`realm_part="*"` 只允许能由全局 kind 安全表达的 shorthand；对 Realm-local kind，若对象 id 也为 `*`，parser MUST 拒绝 `selector_missing_realm_scope`。

### 3.2 词法规则（reference）

- `realm_id`：`ak:realm:` 后接 UUIDv7。
- `space_id`：`ak:space:` 后接 UUIDv7。
- `circle_id`：`ak:circle:` 后接 UUIDv7。
- `strand_id`：`ak:strand:` 后接 UUIDv7。
- `message_id`：`ak:message:` 后接 UUIDv7。
- `morph_id`：`ak:morph:` 后接 UUIDv7。
- `relation_id`：`ak:relation:` 后接 UUIDv7。
- `view_id`：`ak:view:` 后接 UUIDv7。
- `event_id`：`ak:event:` 后接 UUIDv7。
- `policy_id`：`ak:policy:` 后接 UUIDv7。
- `invite_id`：`ak:invite:` 后接 UUIDv7。
- `schema_ref`：schema registry id，例如 `ak.schema.strand.v1` 或反向域名 schema id。Shorthand 与 canonical JSON 都只使用 `schema_ref`；parser MUST 拒绝 `schema_id` 等未声明 token。
- `did`：DID URI。
- `blob_ref`：Blob typed ID，wire form 为 `ak:blob:` 前缀后接 UUIDv7（blob metadata ID），或 `ak:blob:<suite>:<hex>` content-addressed ref（suite ∈ digest-suite registry active rows，v1 即 `sha256` / `blake3`）。
- `morph_kind`：Realm schema 中注册的开放对象类型。
- `relation_kind`：关系类型，例如 `contains`、`assigned_to`、`promoted_from_discussion`、`summarized_from`。
- `object_kind`：标准对象类型或 `morph`。
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
| 嵌套深度（任意 selector 树） | 8 层 | 包括逗号 / 加号 / 引用 / 子 selector 嵌套；canonical 上限单一真相源见 [`scalability-constraints.md` §3](../conformance/scalability-constraints.md)。|
| 单个 `selector_term` 字段值长度 | 1024 字节 | DID、URL、UUIDv7、复合 id 都包含在内。|
| `required_claims[]` 在 subject selector 中的项数 | 32 项 | 每个 claim object 内部字段亦受单字段上限；`grant-constraint.schema.json` 的 `required_claims` 已用 `maxItems:32` 静态强制本上限。|
| `required_claims[]` 内 DID / 列表字段长度（`trusted_issuers[]` / `roles[]` 等；schema 无 `subjects[]` 字段） | 16 项 | 任一 claim object 内 DID 列表（`trusted_issuers`）或角色列表（`roles`）等展开的对象数量；`grant-constraint.schema.json` 对 `trusted_issuers` / `roles` 强制 `maxItems:16`。|
| Constraint object 内嵌套层级 | 4 层 | approval / claim object 内部最多 4 层嵌套。|
| Selector JSON canonical form 总 byte | 64 KiB | 即便所有单项上限均未触发，整个 JSON canonical form 序列化后的 byte 总长仍 MUST ≤ 64 KiB（与 [`../conformance/encoding.md §8.6`](../conformance/encoding.md) cursor opaque payload 上限一致）；超过即 `selector_too_complex`，防止以 256 × 1024 byte selector_term 合法堆叠为 DoS 面。|

实现 MUST 在解析入口先验证 byte-size 与 token-count 上限，再做语法解析；不得让恶意输入进入 EBNF 递归下降。`selector_too_complex` error 必须独立于 `invalid_param`，以便审计层将疑似 DoS 攻击与普通格式错误区分。

`additionalProperties` / 未注册字段不计入嵌套深度，但实现 MUST 把单个 grant 内未知字段总数限制为 ≤ 256（与 `selector_term` 上限一致）；超过即 `selector_too_complex`。此外，未知字段所占 byte **MUST** 同样计入上表的 64 KiB Selector JSON canonical form 总 byte 上限——实现 MUST NOT 因字段未注册就把它排除在 byte 预算之外，否则攻击者可用大量未知字段绕过 byte 上限放大攻击面。

## 4. Selector Terms

### 4.1 Realm 选择器

`realm:ak:realm:0196419b-0000-7000-8000-000000000000`

- 匹配：特定 Realm。
- 适用：该 Realm 中的对象、Event、View、policy、invite、read cursor、notification 和 Blob 引用。
- 不含义：不自动匹配 linked Realm 的内容，除非 selector 或继承策略明确声明。

`realm:*`

- 匹配：所有可评估 Realm。
- 要求：SHOULD 始终配合短有效期、`max_delegation_depth=0`、审批和审计理由。

### 4.2 Space 选择器

`space:ak:realm:0196419b-0000-7000-8000-000000000000:ak:space:019640b6-8000-7000-8000-000000000000`

- 匹配：特定结构 Space。
- 适用：Space metadata、Space lifecycle、Space parent、board/list 类 workflow container 操作。
- 不含义：不自动授予该 Space `default_realm_id` 指向 Realm 的 membership、history 或 E2EE key；也不自动授予 Space 下资源的读取权，除非资源 selector / action / constraint 同时命中。

`space:ak:realm:0196419b-0000-7000-8000-000000000000:*`

- 匹配：指定 Realm 内所有可评估 Space。
- 要求：MUST 携带 `realm_id`；SHOULD 配合 `allowed_space_kinds`、短有效期和审计理由。

### 4.3 Strand 选择器

`strand:ak:realm:...:*`

- 匹配：该 Realm 中所有 Strand。
- 若只允许某个 track 范围，必须使用 `allowed_tracks`。

`strand:ak:realm:...:ak:strand:019640c5-0400-7000-8000-000000000000`

- 匹配：特定 Strand。
- 不匹配：Message、Morph、Relation、View 或 Board/List 容器。

### 4.4 Message 选择器

`message:ak:realm:...:ak:strand:...:*`

- 匹配：某个 Strand `discussion` track 内的所有 Message。
- 不授予 Strand synthesis 字段写入权限。
- 不绕过 Strand 的 effective scope（`Strand.scope_circle_id=null` 时为父 Realm scope，否则为该 [Circle](../models/circle.md) scope）的 membership、history visibility、redaction 或 E2EE key eligibility。

### 4.5 Morph 选择器

`morph:ak:realm:...:customer_case`

- 匹配：该 Realm 中所有 `morph_kind=customer_case` 的 Morph。
- 不匹配：标准 Strand、Message 或 Relation。

`morph:ak:realm:...:ak:morph:01964140-0000-7000-8000-000000000000`

- 匹配：特定 Morph。

### 4.6 Object 选择器

`object` 是跨对象类型的通用选择器，只应在授权面确实需要同时覆盖多类对象时使用。实现 SHOULD 优先使用更具体的 `realm`、`strand`、`message`、`morph`、`relation` 或 `view` selector。

`object:ak:realm:...:strand`

- 匹配：该 Realm 中所有 `type=strand` 的对象。
- 若只允许某个 track 范围，必须额外使用 `allowed_tracks`。

`object:ak:realm:...:ak:strand:019640c5-0400-7000-8000-000000000000`

- 匹配：给定对象引用。

### 4.7 Relation 与 View 选择器

`relation:ak:realm:...:contains`

- 匹配：该 Realm 中所有 `contains` 关系。
- 不授予被 relation 指向对象的读取权；跨 Realm 展开必须重新执行目标 Realm 授权。

`view:ak:realm:...:ak:view:019641be-0000-7000-8000-000000000000`

- 匹配：特定 View 定义。
- 查询结果仍按底层对象授权裁剪。

### 4.8 Event、Actor、Policy、Invite 与 Schema 选择器

这些 selector 主要用于管理、审计、schema / policy 更新、邀请和 actor-private 状态：

- `event:<realm>:<event_id>` 匹配特定 Event；`event:<realm>:*` 匹配 Realm 内 Event metadata。读取 Event payload 仍受对象、track、history、redaction 和 E2EE 约束。
- `actor:<did>` 匹配 principal / service / agent DID；不得匹配 handle、邮箱或 OAuth subject。`actor:*` 不是 v1 合法 selector：`resource-selector.schema.json` 要求 `actor_id` 是具体 DID，parser / reducer 若遇到 actor wildcard MUST 以 `schema_violation` + `selector_actor_wildcard_forbidden` 拒绝。
- `policy:<realm>:<policy_id>` 与 `schema:<schema_ref>` 用于 policy / schema 管理授权。canonical JSON 字段名为 `schema_ref`。
- `invite:<realm>:<invite_id>` 用于邀请创建、查看、撤销或接受。

## 5. 选择器组合

### 5.1 合取 (+)

`realm:ak:realm:...+strand:ak:realm:...:*`

- 表示两个 selector 同时命中时才授权。
- 常用于把宽泛 selector 与额外资源范围或环境约束组合。

### 5.2 析取 (,)

`realm:ak:realm:01964195-0000-7000-8000-000000000000,realm:ak:realm:01964195-8000-7000-8000-000000000000`

- 表示任一 selector 命中即可。

Canonical JSON 中，多个 `resources[]` 的默认语义是 OR；同一 grant 内 constraints 按各自定义求交或 fail-closed。

**Constraint 与 `resources[]` 的绑定粒度（normative）**：v1 的 `constraints[]` 作用于该 grant 内**全部**命中资源，对所有命中资源统一求值（allow 约束相交 AND，见 [`constraint-schema.md` §15.2](./constraint-schema.md)）；v1 **不存在** per-resource 局部约束语法——无法表达"对资源 A 施加约束 X、对资源 B 施加约束 Y"。因此当授予者需要对不同资源施加**异构**约束时，**MUST** 拆分为多个 grant（每个 grant 一组同质资源 + 对应约束），**MUST NOT** 把多个资源放进同一 grant 后期望 constraint 按资源分别绑定——后者会让所有约束对所有命中资源统一生效（典型表现为意外放宽：授予者以为"对 A 给字段 X、对 B 给字段 Y"，实际等价于对 A∪B 都给 X∪Y）。实现 / IAM 工具 SHOULD 在 UI 中提示该表达力边界，避免误授过宽。

**deny 侧对偶陷阱（normative，安全后果）**：上述"约束作用于全部命中资源"对 `deny` / `quarantine` / `require_review` 约束**同样成立**，且其错向后果是**意外放宽授权命中面**而非收紧，安全代价更高。一条 `deny` / `quarantine` / `require_review` 约束作用于该 grant 内**全部**命中资源，**无法**只对 `resources[]` 中的某个子集生效。**求值口径澄清（normative，与 [`constraint-schema.md` §15.3](./constraint-schema.md) 算法一致）**：这里"作用于全部命中资源"指该约束在求值时对**每个被求值的 (action, target)** 按其 `matches(operation, c)` 谓词独立判定——谓词命中该 target 即生效；"全部命中资源"是该谓词在 grant selector 下可命中的资源**全集**，**不是**"对 grant 的 `resources[]` 无条件统一拒绝"。即约束的作用域 = 谓词可命中集合，但实际是否对某次 operation 生效仍取决于该次 target 是否命中谓词。因此：

- 若授予者意图"对资源 A 拒绝（deny）、对资源 B 允许"，**MUST** 把 A、B 拆成**两个独立 grant**（A 的 grant 内放 deny，B 的 grant 内放 allow），**MUST NOT** 把 A、B 放进同一 grant 后期望该 deny 只命中 A。在同一 grant 内放 deny，会让该 deny 连带拒绝本应允许的 B（典型表现为意外收紧 B），或反过来——授予者误以为"该 grant 已对 A 设 deny 兜底"，但实际若 B 不命中该 deny 的 `matches` 谓词，B 仍按 grant 的 allow 放行，A 的 deny 并不能阻止**另一个**命中 B 的 grant 放行 B（跨 grant deny 全局生效见 [`constraint-schema.md` §15.4](./constraint-schema.md)，但**同 grant 内**的 deny 仍只在该 grant 的命中资源集上按 `matches` 求值）。
- 需要 **per-resource deny** 语义时，授予者 **MUST** 拆 grant：把需要拒绝的资源单独放入一个只含 deny / quarantine / require_review 约束的 grant，把允许的资源放入另一个 allow grant。依赖单 grant 内 deny 做"部分资源拒绝"是 v1 表达力之外的误用。
- 安全后果：deny 侧拆分不当会同时引入两类风险——(i) 把 deny 写宽（误拒合法资源，可用性受损）；(ii) 把 deny 误当作对某资源的兜底但该 deny 谓词实际不命中目标资源，导致以为已拒绝的资源仍可经同一或另一 grant 放行（授权放大）。实现 / IAM 工具 **MUST** 在 UI 中对"同一 grant 混放 deny 与多资源"给出显式告警，**SHOULD** 引导拆 grant，而不是只在 allow 侧 SHOULD 警告。

## 6. 匹配算法

给定目标资源和 selector：

```text
function matches(target, selector):
    if selector.kind == "*":
        return true

    if selector.realm_id and selector.realm_id != "*" and target.realm_id != selector.realm_id:
        return false

    realm_local_kinds = {
      "strand", "message", "morph", "object", "relation", "view",
      "event", "policy", "invite"
    }
    if selector.kind in realm_local_kinds and not selector.realm_id:
        raise SchemaViolation("selector_missing_realm_scope")

    if selector.match_scope is absent:
        selector.match_scope = "exact"

    # fail-closed：非法的 match_scope / kind 组合 MUST 拒绝整个 grant，
    # 不得 `return false` 静默跳过该条目（与 §6 表的 schema_violation 裁决一致）。
    if selector.match_scope not in {"exact", "children", "subtree", "realm_wide"}:
        raise SchemaViolation("unknown match_scope")
    if selector.match_scope == "realm_wide" and not selector.realm_id:
        raise SchemaViolation("realm_wide selector missing realm_id")
    # children / subtree 仅对 space 有效；realm_wide 对 space / circle / object / morph 有效（见 §6 表）。
    if selector.match_scope in {"children", "subtree"} and selector.kind != "space":
        raise SchemaViolation("children/subtree match_scope only valid for space")
    if selector.match_scope == "realm_wide" and selector.kind not in {"space", "circle", "object", "morph"}:
        raise SchemaViolation("realm_wide match_scope only valid for space/circle/object/morph")

    if selector.kind == "realm":
        return target.type == "realm" and (
            selector.realm_id == "*" or target.id == selector.realm_id or target.realm_id == selector.realm_id
        )

    if selector.kind == "strand":
        if target.type != "strand":
            return false
        if selector.strand_id and selector.strand_id != target.id:
            return false
        return true

    if selector.kind == "message":
        if target.type != "message":
            return false
        if selector.strand_id and target.strand_id != selector.strand_id:
            return false
        if selector.message_id and selector.message_id != target.id:
            return false
        return true

    if selector.kind == "morph":
        if target.type != "morph":
            return false
        if selector.morph_id and selector.morph_id != target.id:
            return false
        if selector.morph_kind and selector.morph_kind != target.morph_kind:
            return false
        return true

    if selector.kind == "object":
        if selector.object_ref and selector.object_ref != target.id:
            return false
        if selector.object_kind and selector.object_kind != target.type:
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

    if selector.kind == "space":
        if target.type != "space":
            return false
        if selector.space_id:
            if selector.match_scope == "exact":
                return selector.space_id == target.id
            # children / subtree：target.parent_space_id / target.ancestor_space_ids
            # MUST 在被授权操作的 CBA basis 下确定性解析；parent cell 多 head / ⊥ 时
            # MUST fail closed（failed_bottom，space_parent_chain_in_bottom_state），
            # 不得任取一个 head。见本节 match_scope 表后的 normative 段。
            if selector.match_scope == "children":
                return target.parent_space_id == selector.space_id
            if selector.match_scope == "subtree":
                return selector.space_id == target.id or selector.space_id in target.ancestor_space_ids
        return selector.match_scope == "realm_wide"

    if selector.kind == "circle":
        if target.type != "circle":
            return false
        if selector.circle_id:
            return selector.circle_id == target.id
        return selector.match_scope == "realm_wide"

    if selector.kind == "blob":
        return target.type == "blob" and (
            not selector.blob_ref or selector.blob_ref == target.id
        )

    if selector.kind == "notification":
        # realm-scoped, *-only：schema 强制 realm_id required 且无 notification_id；
        # realm 裁剪已由顶部 realm_id guard 完成，此处只判类型。
        return target.type == "notification"

    if selector.kind == "read_cursor":
        # realm-scoped, *-only：同 notification，realm 裁剪由顶部 guard 完成。
        return target.type == "read_cursor"

    return false
```

> `space` / `circle` 配合 `allowed_space_kinds` 等 constraint 在 selector 命中之后再做收窄（见 §6 末段与 §7）；`space` / `circle` / `object` / `morph` 的 `realm_wide` wildcard 形态 MUST 携带 `realm_id`，不得跨 Realm 命中（`object` / `morph` 的 `realm_wide` 命中该 Realm 内对应 `object_kind` / `morph_kind` 的全部资源，用于表达 Realm 全域的对象/Morph 授权）；`blob` 的目标身份字段为 `blob_ref`；`notification` / `read_cursor` 是 realm-scoped 的 \*-only selector，schema 已强制 `realm_id` 必填、不接受精确对象 id。

`match_scope` 的语义固定如下：

| 值 | 语义 |
| --- | --- |
| `exact` | 仅匹配 selector 指定的对象；缺省值。 |
| `children` | 仅对 `space` 有效，匹配直接子 Space；其它 kind 使用该值 MUST `schema_violation`。 |
| `subtree` | 仅对 `space` 有效，匹配该 Space 自身及所有后代 Space；后代关系必须来自已验证的 Space parent chain。 |
| `realm_wide` | 仅在 `realm_id` 存在时有效，匹配该 Realm 内该 kind 的全部资源；缺少 `realm_id` MUST `schema_violation`。 |

**`children` / `subtree` 的 ancestor chain 确定性锚定（normative，防 split authz）**：`children` 的 `target.parent_space_id` 与 `subtree` 的 `target.ancestor_space_ids`（Space parent chain）在并发 reparent 下可能出现多 head（同一 Space 的 parent cell 在不同 head 上指向不同 parent），若授权判定任取一个 head 解析 ancestor chain，则不同节点对"该 Space 是否落在 subtree 内"得出分歧（split authz）。为关闭该面：

- `children` / `subtree` match_scope 的 parent / ancestor chain **MUST** 在**被授权操作的 CBA basis**（DataEvent 的 `seal_ref` 指向的控制面 view，或 Control Move 的 `seal_basis` 指向的控制面 view；见 [`event-auth-state-resolution.md`](./event-auth-state-resolution.md)）下**确定性解析**。给定该 basis，目标 Space 的 parent chain 有唯一解，授权判定 MUST 用该唯一解，MUST NOT 用任意本地最新 head 或其他 basis 解析的 chain。
- 当目标 Space（或其 ancestor chain 上任一 Space）的 parent cell 在该 basis 下处于**多 head / `⊥`**（并发 reparent 未收敛、fork quarantine 等）时，该 `subtree` / `children` 授权分支 **MUST fail closed**：`matches` 对该目标返回不命中（授权按 deny 处理），相关 DataEvent / Control Move MUST `failed_bottom`（`reason="space_parent_chain_in_bottom_state"`），**MUST NOT** 任取一个 head 作为 parent 来判定命中。这与 §6 matches 算法对非法 match_scope 组合的 fail-closed 裁决一致：宁可拒绝也不在歧义 parent chain 下静默放行。
- `exact` match_scope 不解析 ancestor chain，不受本规则约束；`realm_wide` 按 `realm_id` 命中、亦不依赖 parent chain。

Selector match 之后，节点还必须执行 action、constraint、claim、approval、moderation、policy、`allowed_tracks` action scope、history visibility 和 E2EE key eligibility 检查。

## 7. 授权范围

完整授权需要同时满足：

1. **资源匹配**：目标资源必须匹配 selector。
2. **动作匹配**：操作动作必须逐字出现在授权 `actions[]` 中；`actions[]` 不存在 wildcard / segment 通配。通配只适用于资源 selector，不适用于 action token。
3. **约束匹配**：`allowed_space_kinds`、`allowed_morph_kinds`、`allowed_relation_kinds`、`allowed_tracks` 等约束必须满足。
4. **Track scope 检查**：Message 和 discussion track 访问必须在已有 Realm / capability 授权内满足 `allowed_tracks` action scope、history visibility 和 E2EE key eligibility；track 本身不授予 membership、history 或 E2EE key。
5. **跨对象不传播权限**：Relation、View、Strand 和 Message 的互相引用不自动传播读写权。
6. **策略检查**：moderation、retention、legal hold、plaintext-visible service 和 federation policy 不得被 selector 绕过。

## 8. 安全考虑

### 8.1 通配符扩展

`*`、`realm:*` 和 `object:*:*` 可能匹配非预期资源。`actor:*` 因会把 subject 侧授权扩大到任意 principal / service / agent，v1 明确禁止；若需要跨 actor 群组授权，必须用 subject condition + claim / organization policy 表达，而不是 actor selector 通配。

**治理面 wildcard 硬约束（normative）**：`policy:*`、`schema:*` 以及覆盖治理对象的 `object:*:policy` / `object:*:schema` 等通配，会把 policy / schema 管理面授权扩大到整个 Realm 的全部 policy / schema 对象，是与 `actor:*` 同级的高危授权放大面。因此这些治理面 wildcard **MUST** 满足以下二者之一，否则 receiver / reducer **MUST** 以 `schema_violation` + `selector_governance_wildcard_forbidden` 拒绝：

- **被拒绝**：部署 policy 声明不允许治理面 wildcard 时，`policy:*` / `schema:*` / 治理 `object` wildcard 一律 **MUST** 拒绝；或
- **被强收窄**：grant **MUST** 同时携带 `max_delegation_depth=0`（不可再委托）与有限 `effective_expires_at`（不得无限期），且 **MUST** 配管理员审批与审计理由。

非治理面 wildcard（`realm:*`、`object:*:<非治理类型>` 等）的缓解措施：

- 始终配合 `expires_at` 使用。
- 与 `allowed_object_kinds`、`allowed_space_kinds`、`allowed_morph_kinds`、`allowed_facets`、`allowed_tracks` 等约束组合。
- 要求管理员审批与审计理由。
- `max_delegation_depth` SHOULD 为 0。

### 8.2 非 canonical selector domain

实现 MUST reject canonical JSON 中的非标准 selector domain，例如 subject、room、card 等。Strand track 范围必须使用 `kind="strand"` 加 `allowed_tracks`；board / list / 其他结构容器必须使用 `kind="space"` 加 `allowed_space_kinds`（或在需要 Realm-级范围时用 `kind="realm"`）。

字符串 shorthand 也必须映射到上述 canonical domain；未声明的 selector domain MUST fail closed。

### 8.3 Facet 限制

Facet 是 Realm schema / Morph profile 声明后的 hint 或查询标签，不是对象身份，也不是 capability action。实现不得只因为对象声明了 `replyable`、`assignable` 或 `rankable` facet 就绕过标准对象授权规则。

### 8.4 隐私泄露

过宽 selector 可能暴露私有信息：

- `realm:*` 可能暴露非预期 Realm。
- `strand:*:*` 可能暴露对象存在性。
- `message:*:*:*` 可能误授讨论历史读取能力。
- 在多租户环境中避免使用全局 selector。
- 对 Board/List 容器的授权不得自动升级为源 Realm 或 linked Realm 授权。

## 9. 性能考虑

实现 SHOULD 按以下维度建立 selector 索引：

1. `realm_id`
2. `kind`
3. 精确对象 ID，例如 `strand_id`、`message_id`、`morph_id`
4. `morph_kind`、`relation_kind`
5. 通配符授权缓存

求值顺序 SHOULD 先做精确 ID 和 `realm_id` 裁剪，再执行对象类型、kind、constraint 和 policy 检查。

## 10. 一致性

实现 MUST：

- 接受本规范定义的 JSON resource selector。
- 支持精确 ID、Realm、Space、Circle、Strand、Message、Morph、Relation、View、Event、Actor、Policy、Invite、Schema、Blob、Notification、Read Cursor 和 Object 匹配。
- 拒绝非 canonical selector kind：`subject`、`room`、`card`、`board`、`list`。
- 对非法 selector 返回清晰错误。
- 在 selector 命中后继续执行 action、constraint、claim、policy、`allowed_tracks` action scope 和 E2EE 检查。

实现 SHOULD：

- 提供 selector 解释 / 调试工具。
- 缓存 selector 匹配结果。
- 记录通配符 selector 使用。
