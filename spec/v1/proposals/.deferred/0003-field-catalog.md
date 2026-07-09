---
akp: AKP-0003
title: Field Catalog (typed custom fields)
normative: false
stability: v1
updated: 2026-05-25
status: deferred-to-v1.1
created: 2026-05-23
authors:
  - did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:arkret.example
---

## 1. Summary

引入 `ak:field_def:` 一等对象,把 Realm 内的扩展字段从 `fields: object` 黑盒升级为**有类型 / 有校验 / 有显示元数据 / 可在多个 Strand type 之间复用**的目录。AKP-0002 Strand Type、AKP-0004 Form Layout、AKP-0005 Workflow 都建立在此基础上。

## 2. Motivation

Jira 右侧 "Fields" 边栏列出几十个可重复使用的字段(Approvals / Goals / Issue color / Project / Request Type / [CHART] Time in Status / ...),底部"Reuse 40 fields from other work types and spaces"和 "Can't find a field? Go to custom fields"。Linear 的 "Properties"、Asana 的 "Custom Fields"、Notion 的 "Property" 都是同类机制。

当前协议:`fields: object` 是 untyped 扩展容器([common-fields.md §3](../../zh/models/common-fields.md):"字段 schema 由对象类型自身的 `schema_refs` 决定")。问题:

- 改一个字段的显示名 / widget 要在每个使用它的 schema 中改一遍
- 没有"这个 Realm 当前可用哪些字段"的可枚举真源
- 客户端无法 type-aware 渲染(date picker / select / multi-select / person picker / number / 等)
- 同一字段在不同 Strand type 之间的复用没有引用关系

## 3. Specification

### 3.1 `ak:field_def:` 对象

Schema id: `ak.schema.field_def.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:field_def` | `ak:field_def:<uuid>` | Field def ID。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm。 |
| `key` | yes | `string` | `^[a-z][a-z0-9_]{0,63}$`;`(realm_id, key)` 唯一;**create-locked**(字段 key 即对象 `fields.<key>` 路径,silent rename 会破坏 selector / forbidden-wire 守卫)。 | 物理字段 key。 |
| `name` | yes | `string` | 1..64 chars。 | 显示名(可 i18n,通过 profile)。 |
| `description` | no | `string` | ≤512 chars。 | 字段说明。 |
| `icon` | no | `object` | `{emoji?, blob_ref?}` | 图标。 |
| `data_type` | yes | `enum(string, text, number, integer, boolean, date, datetime, duration, actor_ref, object_ref, blob_ref, select, multi_select, rich_text, url, email, ...)` | profile 可扩;协议核心提供 ~15 种 v1 类型。 | 字段数据类型,决定校验规则与默认 widget。 |
| `options` | conditional | `array<FieldOption>` | `data_type ∈ {select, multi_select}` 时必填 | 见 §3.2。 |
| `constraints` | no | `object` | 见 §3.3。 | 类型相关的额外约束(min / max / regex / required_if / ...)。 |
| `widget_hint` | no | `string` | profile-declared widget id。 | UI 渲染提示(覆盖 data_type 的默认 widget)。 |
| `reusable` | no | `boolean` | 默认 `true`。 | 是否允许多个 strand_type 引用本字段。`false` 表示"只属于某个 type 的私有字段",reducer 拒绝跨 type 引用。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5。 | 生命周期。 |
| 公共字段 | — | — | created_by / created_at / updated_by / updated_at / state_changed_at | — |

### 3.2 `FieldOption`(`select` / `multi_select`)

```json
{
  "key": "high",
  "label": "High",
  "color": { "palette": "red" },
  "description": "Significant business impact",
  "archived": false,
  "rank": "a000"
}
```

- `key` create-locked 一旦使用就不能改(同 label / strand_type)
- `label` 可改
- `archived=true` 的 option 不出现在 picker 但已选中的 Strand 保留(同 label.archived 模式)
- `rank` 用于 picker 排序,LWW lattice

### 3.3 `constraints` 对象按 data_type

| data_type | constraint 字段 |
| --- | --- |
| `string` / `text` | `min_length`, `max_length`, `regex` |
| `number` / `integer` | `min`, `max`, `step` |
| `date` / `datetime` | `min`, `max` |
| `duration` | `unit`(seconds / minutes / hours),`min`, `max` |
| `actor_ref` | `actor_kind_allow: array<enum>`(user / agent / service / ...) |
| `object_ref` | `object_kind_allow: array<string>`(`ak:strand:` / `ak:morph:` / ...) |
| `blob_ref` | `mime_allow: array<string>`, `max_size_bytes` |
| `select` | `default_option_key` |
| `multi_select` | `min_selections`, `max_selections` |
| `url` | `scheme_allow: array<string>`(`https` / `mailto` / ...) |

所有 data_type 通用:`required_if: <expression-ref>` — 不在 v1 范围,留给 profile 扩展。

### 3.4 Event 家族

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `ak.field_def.create` | yes | 创建 |
| `ak.field_def.update` | yes | patch(不改 key、data_type;改 data_type 走 §3.5) |
| `ak.field_def.archive` | yes | active → archived |
| `ak.field_def.restore` | yes | archived → active |
| `ak.field_def.tombstone` | yes | terminal |
| `ak.field_def.option.add` | yes | select / multi_select 加 option |
| `ak.field_def.option.update` | yes | 改 label / color / archived / rank |
| `ak.field_def.type_migrate` | yes | **high tier**;改 data_type 需要 transformation rule;参考 Morph schema_migrate 模式 |

### 3.5 与对象 `fields` 黑盒的关系

未启用本提案的 Realm:`fields: object` 仍是 untyped 黑盒,行为不变。

启用 profile `ak.profile.field_catalog.v1` 的 Realm:

- 对象的 `fields.<key>` 中,`<key>` 出现的所有路径 reducer **MAY**(profile-declared)校验该 key 必须等于某个 active `field_def.key`;否则 `schema_violation`,`reason="field_def_not_registered"`。
- 该 field 的 value MUST 通过 field_def 的 `data_type` + `constraints` 校验。
- forbidden-wire:无新条目;此提案是收紧 `fields` 内部,不改顶层路径。

### 3.6 Capability

| action | risk_tier | target event kinds |
| --- | --- | --- |
| `ak.field_def.manage` | medium | create / update / archive / restore / tombstone / option.* |
| `ak.field_def.type_migrate` | high | `ak.field_def.type_migrate` |

字段值的写入仍走原 `ak.strand.update` / `ak.morph.update` capability,不引入新 action。

## 4. Interactions with normative spec

- 新增文件:`spec/v1/zh/models/field-def.md`。
- 新增 schema:`field-def.schema.json`。
- 新增 id-kind:`field_def`。
- 新增 event_kinds(8 条)+ capability actions(2 条)。
- 新增 profile:`ak.profile.field_catalog.v1`。
- **不**改现有 Strand / Morph / Realm 顶层 schema(本提案是 fields 内部收紧,不引入顶层字段)。
- `common-fields.md` §3 的 `fields` 行追加 note:"启用 `ak.profile.field_catalog.v1` 时本字段每个 key MUST 引用一个 `ak:field_def:`"。

## 5. Rationale & alternatives

### 5.1 为什么不是 schema-on-the-side?

候选 A:用 Realm schema_refs[] 声明扩展 schema(JSON Schema 形态),由 reducer 加载并校验 `fields`。

否决理由:
- JSON Schema 是字段集合 contract,不承载 widget / icon / option color / archive 等 UI / 运行时元数据
- 跨 Realm 复用一个字段需要每个 Realm 内置同一个 schema,没有 first-class 引用关系
- 改一个字段的显示名要做 schema migration,过重

### 5.2 为什么不复用 Morph 来表达 field_def?

Morph 是异质对象的开放扩展层。field_def 是元数据(用于校验其他对象的 `fields`),如果落到 Morph 会丢掉:
- reducer 在写入对象 `fields` 时引用 field_def 的能力(需要 typed ID)
- capability action `ak.field_def.manage` 的 selector 表达

### 5.3 为什么 data_type 是 fixed enum 而不是 string 任意值?

reducer 必须能 type-aware 校验;允许任意 data_type 字符串就退化成无校验。Profile 可扩(声明新的 data_type 与对应校验规则),但 core 协议只认核心枚举。

## 6. Open questions

- [ ] data_type 的核心枚举具体是哪些?草案给出 15 种,可能过宽,需要剪裁。
- [ ] `actor_ref` 的 cardinality 由谁声明?是 field_def 一个字段(`single` vs `multi`)还是 widget_hint?建议字段本身分 `actor_ref` 与 `multi_actor_ref` 两个 data_type。
- [ ] select option 的 `archived` 是否要走独立 event `ak.field_def.option.archive`?目前是 `ak.field_def.option.update` 改 `archived=true`,简单但缺少 capability 切分。
- [ ] field_def `tombstone` 后,使用该 field 的对象上 `fields.<key>` 是清除还是保留?建议保留(audit),但 picker / projection 标记 "deprecated field"。
- [ ] 跨 Realm field_def 引用是否允许?默认拒绝;但 organization-level shared field catalog(给跨 Realm dashboard 用)可能需要。

## 7. Migration plan

(accepted 阶段填)

## 8. References

- Jira "Fields" sidebar(用户提供截图,2026-05-23):Date and time fields / Other fields 分组,"Reuse 40 fields from other work types and spaces" 提示。
- Linear display options / issue properties context: <https://linear.app/docs/display-options>
- Asana Custom Fields: <https://asana.com/guide/help/premium/custom-fields>
- Notion Database properties
