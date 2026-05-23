---
cxp: CXP-0002
title: Flow Type (Work Item Type)
status: draft
created: 2026-05-23
authors:
  - did:web:contrix.example
depends_on: [CXP-0003]
---

## 1. Summary

引入 `cx:flow_type:` 一等对象,声明 Realm 内某个 Flow 业务类型(Task / Sub-task / Bug / Story / Initiative / ...)的字段集合、必填项、允许的 workflow、父子层级。Flow 上新增可选 `flow_type_ref: id:flow_type`,reducer 在 `cx.flow.create` / `cx.flow.update` 时按 type 声明做字段验证。

## 2. Motivation

Jira 截图里 "Sub-task / Task" tab 切换 = 每个 Space 内 Flow 的有限**类型集合**,不同类型有各自字段集与 layout。Linear 的 "Issue type"、Asana 的 "Custom item type"、GitHub Project 的 "Item type" 都是同类概念。

当前协议:Flow 是匿名统一对象,业务类型靠 `fields.<custom>` + Realm schema/profile 字符串隐式表达([flow-and-message.md §2](../zh/models/flow-and-message.md):"业务语义分类不属于 Flow 顶层字段")。这个原则对 wire / reducer 是对的(不要把业务字典塞进协议固定列表),但缺少一个让 Realm admin **可治理地声明类型**的机制:

- 没有"这个 Realm 允许哪些 Flow 类型"的真源
- 没有"task 必须有 assignee,bug 必须有 severity"的 reducer-enforced 校验
- 没有"sub-task 必须有 parent task"的层级约束
- UI 无法 per-type 切换 layout / icon / 默认 workflow

## 3. Specification

### 3.1 `cx:flow_type:` 对象

Schema id: `cx.schema.flow_type.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:flow_type` | `cx:flow_type:<uuid>` | Flow type ID。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm。 |
| `key` | yes | `string` | `^[a-z][a-z0-9_]{0,63}$`;在 `(realm_id, key)` 唯一;**create-locked**(与 morph_type 同理,授权 / selector 不能被 silent rename)。 | 机器名(`task`, `subtask`, `bug`, `story`, ...)。 |
| `name` | yes | `string` | 1..64 chars。 | 显示名。 |
| `description` | no | `string` | ≤512 chars。 | 描述。 |
| `icon` | no | `object` | `{emoji?, blob_ref?}` | 类型图标。 |
| `color` | no | `object` | 同 [CXP-0001](./0001-label-entity.md) `color`。 | 类型主题色(用于 UI tag 渲染)。 |
| `parent_type_refs` | no | `array<id:flow_type>` | 允许多个父类型(例如 `subtask` 的父可以是 `task` 也可以是 `bug`)。 | 父子层级:本 type 的 Flow MUST 有 `cx.flow.parent --> flow` Relation 指向一个 `flow_type ∈ parent_type_refs` 的 Flow。 |
| `field_requirements` | no | `array<FieldRequirement>` | 见 §3.2。 | 字段必填 / 推荐 / 禁止表;**依赖 [CXP-0003 Field Catalog](./0003-field-catalog.md) 的 `cx:field_def:`**。 |
| `allowed_workflow_ref` | no | `id:workflow` | 见 [CXP-0005](./0005-workflow-state-machine.md)。 | 本 type 默认 / 唯一允许的 workflow。 |
| `allowed_relation_kinds` | no | `array<string>` | — | 本 type 的 Flow 允许出现哪些 outgoing Relation kind(白名单收紧)。 |
| `default_stage` | no | `enum(common-fields §5.3.2 的 8 值)` | — | `cx.flow.create` 未指定 stage 时的 fallback。**注意**:协议级 stage 仍要求 actor 必填(common-fields §5.3.1),本字段仅供 client 端 picker 预填。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5。archive 后已用该 type 的 Flow 不脱钩,但 picker 隐藏。 | 生命周期。 |
| 公共字段 | — | — | created_by / created_at / updated_by / updated_at / state_changed_at | 见 common-fields。 |

### 3.2 `FieldRequirement` 子结构

```json
{
  "field_def_ref": "cx:field_def:<uuid>",
  "requirement": "required" | "recommended" | "optional" | "forbidden",
  "visible_when_empty": true,
  "default_value": { "...": "..." }
}
```

- `required`:`cx.flow.create` 必须在 `fields` 中提供;缺失 → `schema_violation`
- `forbidden`:`cx.flow.create` / `update` 出现该字段 → `schema_violation`
- `recommended` / `optional`:reducer 不强制,仅 UI hint
- `visible_when_empty`:对应 Jira "Hide when empty" 分隔线之上(true)/ 之下(false)

### 3.3 Flow 顶层新增字段

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `flow_type_ref` | no | `id:flow_type` | 引用的 `flow_type.realm_id == flow.realm_id`。**create-locked**(避免类型切换导致历史 grant 失效);需要换 type 走显式 `cx.flow.type.migrate`(参见 §3.4)。 |

未设置 `flow_type_ref` 时,Flow 是 anonymous(沿用当前协议行为)。

### 3.4 Event 家族

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `cx.flow_type.create` | yes | 创建 type |
| `cx.flow_type.update` | yes | patch type(不改 key) |
| `cx.flow_type.archive` | yes | active → archived |
| `cx.flow_type.restore` | yes | archived → active |
| `cx.flow_type.tombstone` | yes | terminal |
| `cx.flow.type.migrate` | yes | **高 tier**;改一个已存在 Flow 的 `flow_type_ref`;reducer 校验所有 required 字段在新 type 下仍满足;audit-required。 |

### 3.5 Reducer 校验流程(`cx.flow.create` / `cx.flow.update`)

1. 解析 `flow.flow_type_ref`(若有);找到对应 type 的 `field_requirements`。
2. 对每个 `required` field_def → `fields[<field_def.key>]` 必须存在且通过 field_def 的 typed 校验。
3. 对每个 `forbidden` field_def → `fields[<field_def.key>]` 不得出现。
4. 若 type 声明 `parent_type_refs[]` 非空 → 必须在同一事件 batch 中或事先存在 `cx.relation.create relation_kind=cx.flow.parent` 指向合法父类型 Flow。
5. 若 type 声明 `allowed_relation_kinds[]` → 后续 `cx.relation.create` 若超出白名单 MUST `schema_violation`。
6. 若 type 声明 `allowed_workflow_ref` → Flow 的 workflow_state_ref(参见 [CXP-0005](./0005-workflow-state-machine.md))MUST 来自该 workflow。

## 4. Interactions with normative spec

- 新增文件:`spec/v1/zh/models/flow-type.md`。
- 新增 schema:`flow-type.schema.json`。
- 新增 id-kind:`flow_type`。
- 新增 event_kinds(6 条)+ capability actions(`cx.flow_type.manage`、`cx.flow.type.migrate` high tier 等)。
- 新增 Relation kind:`cx.flow.parent`(若未存在),用于父子 Flow。
- `flow.schema.json` 增加 `flow_type_ref` optional property。
- `flow-and-message.md` §3 表新增 `flow_type_ref` 行;新增章节描述类型校验流程。
- **不**改 Flow 现有 `fields` 黑盒约束;type 是收紧而非替代。
- profile gate:`cx.profile.flow_type.v1`,未启用时 `flow_type_ref` MUST 缺省;reducer 不会调用 type-validation 路径。

## 5. Rationale & alternatives

### 5.1 为什么不是直接在 Realm schema 里 inline 声明 type 表?

候选 A:`Realm.fields.flow_type_profiles: map<key, profile>`(类似现在的 `morph_type_profiles`)。

否决理由:
- type 的生命周期 / audit / 跨 Realm 复用都缺乏 first-class 表达
- 改一个 type 要 PATCH Realm 对象,与"高 tier 的 schema-evolution"耦合过紧
- 想给 type 加 description / icon / color 都要往 Realm.fields 里塞
- Morph 是异常情况(异质对象的开放扩展),Flow 是标准对象,处理范式应该更结构化

### 5.2 为什么不复用 Morph?

候选 B:把"业务类型 Flow"统统改为 Morph。

否决理由:
- Morph 是"协议未固化为标准类型"的扩展缓冲层([morph.md §1](../zh/models/morph.md));Flow 已经是标准对象
- Flow 的 tracks / discussion / state / stage / position 都是标准能力,改成 Morph 会失去这些
- 业务 type 不等于异质对象,只是字段集 + 校验 + UI 的收紧

### 5.3 为什么 `flow_type_ref` create-locked?

与 morph_type、label.key 同理:type ref 是授权 / selector / workflow gate 的 key,silent rename 会让旧 grant 失效。需要换 type 走显式 `cx.flow.type.migrate`(audit-required, high tier)。

## 6. Open questions

- [ ] 是否允许一个 Flow **没有** type(anonymous Flow)?默认允许(profile-gated),否则会破坏现有 v1 行为。
- [ ] type 是否可以跨 Realm 复用?目前设计是 Realm-scoped。Linked Realm 场景下是否需要继承?
- [ ] `cx.flow.parent` Relation 是否应该是 cardinality `many_to_one` 强约束(一个 sub-task 只能有一个 parent)?Jira 是 1:N,Linear 是 1:N。建议 cardinality=many_to_one。
- [ ] type 删除后 historical Flow 上的 `flow_type_ref` 如何处理?reducer 不应清除引用(保留 audit),但 picker / projection 把这些 Flow 标记为 "deprecated type"。
- [ ] 是否需要"system-builtin types"作为 v1 兜底(`task`/`subtask`/`bug`/`story`)?这会引入协议级 type fixed enum,违背"类型由 Realm 声明"的原则。建议**不**做 builtin,留给 default profile。

## 7. Migration plan

(accepted 阶段填)

## 8. References

- Jira work item type(用户提供截图,2026-05-23):Sub-task / Task tab,parent / subtask 层级
- Linear issue creation / type context: <https://linear.app/docs/creating-issues>
- Asana Custom Item Types
- CXP-0003 Field Catalog(本提案的 field-level 依赖)
- CXP-0005 Workflow(本提案的 workflow-level 依赖)
