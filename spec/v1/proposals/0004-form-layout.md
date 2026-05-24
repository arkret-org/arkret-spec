---
cxp: CXP-0004
title: Form Layout (per-type detail view arrangement)
status: deferred-to-v1.1
created: 2026-05-23
authors:
  - did:web:contrix.example
depends_on: [CXP-0002, CXP-0003]
---

## 1. Summary

引入 `cx:form_layout:` 一等对象,声明 Flow / Morph 单对象详情面板中字段的排列、分组、"hide when empty" 分隔、tab 切分。Realm admin 通过它统一治理 UI 布局,避免每个客户端硬编码。

## 2. Motivation

Jira 截图最直观的功能是"Work item layout":per-work-type 拖拽字段顺序、"Hide when empty"分隔线、字段 tabs。Linear 的 "Issue templates"、Notion 的 "Database template"、Asana 的 "Task template" 局部承担类似职责。

当前协议:`View` 只服务 collection(Board / List)的查询与渲染([current-model.md §5](../zh/overview/current-model.md))。**没有"单 Flow 详情面板"的字段布局定义**;客户端只能各自硬编码"标题在上、状态在右、字段在左"。

## 3. Specification

### 3.1 `cx:form_layout:` 对象

Schema id: `cx.schema.form_layout.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:form_layout` | `cx:form_layout:<uuid>` | Layout ID。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm。 |
| `name` | yes | `string` | 1..128 chars。 | Layout 显示名(管理界面用)。 |
| `target_object_kind` | yes | `enum(flow, morph)` | v1 范围;后续可扩。 | 这份 layout 用于哪类对象。 |
| `target_type_ref` | conditional | `id:flow_type \| id:morph_type_key` | `target_object_kind=flow` 时引用 `cx:flow_type:`;`target_object_kind=morph` 时引用 `morph_type` 字符串 key。 | 该 layout 绑定的 type。**未设置**则为该 object_kind 的 fallback default layout。 |
| `sections` | yes | `array<Section>` | 至少 1 个 section。 | 详情面板分区,见 §3.2。 |
| `tabs` | no | `array<Tab>` | 可选 tab 切分。 | 见 §3.3。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5。 | 生命周期。 |
| 公共字段 | — | — | created_by / created_at / updated_by / updated_at / state_changed_at | — |

### 3.2 `Section` 子结构

```json
{
  "key": "always_visible",
  "kind": "always_visible" | "hide_when_empty" | "collapsed" | "readonly",
  "title": "Details",
  "rank": "a000",
  "fields": [
    {
      "field_def_ref": "cx:field_def:<uuid>",
      "width": "full" | "half" | "third",
      "readonly_for_roles": ["viewer"]
    }
  ]
}
```

- `kind=always_visible`:Jira "Hide when empty" 之上,永远显示
- `kind=hide_when_empty`:字段值为空时隐藏(对应 Jira 截图中那条虚线分隔)
- `kind=collapsed`:默认折叠,用户展开后显示
- `kind=readonly`:字段强制只读(覆盖 field_def 的 widget 行为)

`rank` 用于 section 排序,LWW lattice 同 board position rank。

### 3.3 `Tab` 子结构

```json
{
  "key": "comments",
  "title": "Comments and activity",
  "rank": "a000",
  "section_keys": ["activity_feed"]
}
```

- tab 包含多个 section
- 不在任何 tab 的 section 显示在"主面板"(Jira 截图里左侧 layout 区)

### 3.4 Layout 选择算法(reducer 不参与,纯客户端 / projection)

客户端在打开 Flow 详情面板时按以下顺序找 layout:

1. Flow 有 `flow_type_ref` → 查找 active `form_layout` 中 `target_object_kind=flow` 且 `target_type_ref=<this flow_type>`
2. 找不到 → 查找该 object_kind 的 fallback layout(`target_type_ref` 缺省)
3. 仍找不到 → 客户端硬编码 default

多个 layout 命中同一 type 时(治理冲突),按 `created_at` 取最早(deterministic);profile 可声明优先级规则。

### 3.5 Event 家族

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `cx.form_layout.create` | yes | 创建 |
| `cx.form_layout.update` | yes | patch sections / tabs |
| `cx.form_layout.archive` | yes | active → archived |
| `cx.form_layout.restore` | yes | archived → active |
| `cx.form_layout.tombstone` | yes | terminal |
| `cx.form_layout.copy` | yes | "Copy work item layout"(Jira 截图右下按钮);复制一份新 layout 对象,target 可改 |

### 3.6 Capability

| action | risk_tier | target event kinds |
| --- | --- | --- |
| `cx.form_layout.manage` | medium | create / update / archive / restore / tombstone / copy |

## 4. Interactions with normative spec

- 新增文件:`spec/v1/zh/models/form-layout.md`。
- 新增 schema:`form-layout.schema.json`。
- 新增 id-kind:`form_layout`。
- 新增 event_kinds(6 条)+ capability actions(1 条)。
- 新增 profile:`cx.profile.form_layout.v1`。
- **reducer 不校验 layout 内容**:layout 是纯展示元数据,wire 上 layout 引用的 field_def / flow_type 不存在时,reducer 在 layout 写入时校验引用合法性,但**不**联动校验 Flow 数据。
- View(`cx:view:`)与 form_layout 关系:View 服务 collection(多对象列表),form_layout 服务 detail(单对象)。两者职责正交。

## 5. Rationale & alternatives

### 5.1 为什么不扩展 View 来承担 detail layout?

候选 A:`cx:view: kind=detail` + renderer 表达字段排列。

否决理由:
- View 的语义是"查询 + 渲染对象集合",detail 是单对象;两者的 filter / sort / column 概念不通用
- View 的 renderer 选择由对象 type 派生,detail layout 需要 per-type 精确选择,职责混合会乱

### 5.2 为什么 layout 是 first-class 对象而不是 Realm schema 内嵌?

- 改一份 layout 应该有独立 audit / capability(`cx.form_layout.manage` ≠ `cx.realm.update`)
- "Copy layout" 是高频运维操作,需要 first-class event
- 跨 Realm template marketplace(未来)需要 layout 是可独立分发的对象

### 5.3 为什么 reducer 不校验 layout 联动?

layout 是纯 hint,引用的 field_def / flow_type 在 layout 写入时存在即可。运行时 layout 引用了 archived field_def,projection 跳过该 section 即可,不需要 wire-level reject。这与 Realm policy / Realm schema 是同样的"声明式 + 客户端容忍" 设计。

## 6. Open questions

- [ ] `Section.kind=hide_when_empty` 的"empty" 判定:`null` 算空,`""` 算空,`[]` 算空?需要标准化。
- [ ] 是否允许同一 field_def 在同一 layout 出现多次(主面板 + sidebar 各一次)?
- [ ] tab 是否要支持嵌套?(Jira 不支持,Notion 支持)。建议不嵌套,扁平 tabs 已经覆盖 90% 场景。
- [ ] layout 是否可跨 Realm 复用 / 继承?profile-level 决策。
- [ ] Mobile / 紧凑 UI 是否需要独立 layout?或者由客户端 responsive 处理?建议后者,但留 `layout_variant` 字段 placeholder。

## 7. Migration plan

(accepted 阶段填)

## 8. References

- Jira "Work item layout"(用户提供截图,2026-05-23):drag-fields 排列、"Hide when empty" 分隔、Sub-task / Task tab、"Copy work item layout" 按钮、右侧 Fields 边栏 + custom fields 跳转
- Notion database template
- Asana task templates
- CXP-0002 Flow Type(layout 的 type 锚点)
- CXP-0003 Field Catalog(layout 的字段引用对象)
