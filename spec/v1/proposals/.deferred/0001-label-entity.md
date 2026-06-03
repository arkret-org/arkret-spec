---
cxp: CXP-0001
title: Label as first-class entity
normative: false
stability: v1
updated: 2026-05-25
status: deferred-to-v1.1
created: 2026-05-23
authors:
  - did:web:cokret.example
---

## 1. Summary

把当前 `labels: array<string>`(common-fields §3 的裸 string 数组,OR-Set 收敛)升级为一等对象 `ck:label:`(带 id / 颜色 / 标题 / 描述 / scope 的可独立编辑实体),通过 `flow --labeled_with--> label` Relation 应用到 Flow / Morph 等对象。

## 2. Motivation

Trello 的 label 是 board 级实体,改一次颜色或标题,所有挂着这个 label 的 card 同步更新。GitHub Issue 的 label 同样是 repo 级实体。当前协议里 `labels: array<string>` 是 inline 裸串:

- 改一个 label 的显示名需要在每个 Flow 上重新 patch
- 没有颜色 / 描述 / 图标的承载
- 无法做权限切分("谁可以创建新 label" vs "谁可以贴 label")
- 无法做 audit("这个 label 是谁创建的")

Jira / Linear / Asana 都是一等 label 实体。本提案把这层 gap 补上。

参考形态(用户提供的 Trello 截图):
- Label picker:已存在 label 列表(颜色块 + 标题)+ 创建按钮 + "色盲友好模式" toggle
- Label create form:Title 输入 + 调色板(6×6 named palette + remove color)

## 3. Specification

### 3.1 `ck:label:` 对象

Schema id: `ck.schema.label.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:label` | `ck:label:<uuid>`(UUIDv7) | Label 对象 ID。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm;能看 Realm 即可看其下 Label。 |
| `key` | yes | `string` | `^[a-z][a-z0-9_-]{0,63}$`;在 `(realm_id, key)` 上 reducer 强制唯一。 | 机器名(稳定,用于 search filter / API)。**create-locked**,与 morph_type 同理(防止 grant selector 漂移)。 |
| `name` | yes | `string` | 1..64 chars。 | 显示名(可改,与 key 解耦)。 |
| `color` | yes | `object` | `{palette: <enum>, hex?: "#rrggbb"}`;palette ∈ `{green, yellow, orange, red, purple, blue, teal, pink, lime, sky, gray, ...}`(profile 可扩);hex 是显式覆盖 fallback,渲染端按主题 / colorblind mode 选 palette token。 | 调色板引用。 |
| `description` | no | `string` | ≤256 chars。 | 标签语义说明(hover / 管理界面)。 |
| `icon` | no | `object` | `{emoji?: string, blob_ref?: id:blob}` | 可选图标。 |
| `scope` | no | `enum(realm, space, personal)` | 默认 `realm`。`space` 需绑定 `space_ref`;`personal` 由 actor-private state 承载,不写共享 cell。 | 可见性范围。 |
| `space_ref` | conditional | `id:space` | `scope=space` 时必填。 | Space 子树限定的 picker 范围。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5;archive 后已应用的 Relation 不自动脱钩,但 picker 隐藏。 | 生命周期。 |
| `stage` | n/a | — | Label 不参与 stage 轴。 | — |
| 公共字段 | — | — | `created_by` / `created_at` / `updated_by` / `updated_at` / `state_changed_at` | 同 common-fields §3。 |

### 3.2 Event 家族(沿用 common-fields §5.2 模板)

| event kind | reducer_input | payload | 说明 |
| --- | --- | --- | --- |
| `ck.label.create` | yes | full object | 创建 label。 |
| `ck.label.update` | yes | `ck.patch.v1`(path 不含 `key`) | 改 name / color / description / icon / scope。 |
| `ck.label.archive` | yes | object_lifecycle_payload | active → archived。 |
| `ck.label.restore` | yes | object_lifecycle_payload | archived → active。 |
| `ck.label.tombstone` | yes | object_lifecycle_payload | active/archived → tombstoned,不可逆。 |

### 3.3 应用到 Flow / Morph:`labeled_with` Relation

```text
flow  --labeled_with-->  label    cardinality: many-to-many
morph --labeled_with-->  label    cardinality: many-to-many
```

- 写入:`ck.relation.create relation_kind=labeled_with`
- 删除:`ck.relation.tombstone`
- 冲突收敛:Relation 集合,OR-Set
- **跨 Realm 约束**:`from_ref.realm_id == to_ref.realm_id`,否则 `schema_violation`(避免审计边界逃逸,与 Realm 是安全边界一致)。

### 3.4 与现有 `labels: array<string>` 的关系

**关键:reducer fail-closed 单源**,通过 Realm profile 选择模式:

- Profile **未启用** typed label(默认 v1 行为):沿用现行 `array<string>` 自由 tag,`ck.label.*` event MUST 被 reducer 拒绝(`schema_violation`,`reason="label_profile_not_enabled"`)。
- Profile **启用** typed label(`ck.profile.label.typed.v1` opt-in):
  - 对象顶层 `labels: array<string>` MUST 由 reducer 派生(只读投影),actor 直接写入 MUST `schema_violation`(与 `watches` Relation / `contains` Relation 的双源约束同模式)。
  - `ck.label.*` 是 label CRUD 真源;`labeled_with` Relation 是应用真源。
  - 客户端展示用的 `labels: array<string>` 由 reducer 从已应用的 `labeled_with` Relation + label `name` 派生(label 改名时投影自动更新)。

### 3.5 Capability split

| action | risk_tier | target event kinds |
| --- | --- | --- |
| `ck.label.manage` | medium | `ck.label.create`, `ck.label.update`, `ck.label.archive`, `ck.label.restore`, `ck.label.tombstone` |
| `ck.label.apply` | low | `ck.relation.create` 限 `relation_kind=labeled_with` + `ck.relation.tombstone` 限同 kind(通过 capability constraint `relation_kind_allow`) |

理由:Trello / GitHub 常见场景是"只有 admin 能扩调色板,所有成员都能贴 label"。

## 4. Interactions with normative spec

- 新增文件:`spec/v1/zh/models/label.md`(详尽 normative 描述)。
- 新增 schema:`spec/v1/artifacts/schemas/label.schema.json`。
- 新增 id-kind:`label` → `ck:label:` 加入 `id-kind-registry.json`。
- 新增 event_kinds(catalog + registry 同步)5 条;新增 capability actions 2 条。
- 新增 relation_kind:`labeled_with`(应该已在 relation profile 里能声明,确认即可)。
- 新增 profile:`ck.profile.label.typed.v1`,声明启用此提案。
- `common-fields.md` §3 的 `labels: array<string>` 行追加 note:"启用 `ck.profile.label.typed.v1` 时本字段降级为 reducer-derived 投影"。
- **不**新增 forbidden-wire 字段(单源约束通过 profile gate 而非 wire-level reject 表达,因为旧 array<string> 形态仍合法)。

## 5. Rationale & alternatives

### 5.1 为什么不是只加一个"label registry"sidecar?

候选 A:保留 `labels: array<string>`,新增一个 Realm-level "label palette" map `{key → {name, color, description}}` 作为纯展示 sidecar。

否决理由:
- 没有 id / lifecycle / audit,改名会丢失历史归属
- 调色板和应用关系没有 referential integrity(贴的 label 可能指向已删除 key)
- 没有 per-Space / personal scope 表达

### 5.2 为什么不直接在 Flow 上挂内嵌 label object 数组?

候选 B:`flow.labels: array<LabelObject>`(内嵌)。

否决理由:
- 改一个 label 颜色要 patch 所有 Flow,违反 normalization
- E2EE 场景下 label 元数据也被加密,无法在 picker 阶段渲染
- 集合字段 OR-Set 收敛不直观(嵌套对象在并发更新下歧义)

### 5.3 为什么用 Relation 而不是 Flow 上的 `label_refs: array<id:label>`?

Relation 已经是协议级一等概念,有 lifecycle / cross-Realm 校验 / audit / capability gating;再造一个数组路径会重复机制。Trello 的应用关系也是隐式的多对多。

## 6. Open questions

- [ ] `color.palette` 的固定 token 集合用哪一套?Trello 12 色 / Linear 8 色 / Tailwind 22 色?建议把 token 集放在 profile 里,protocol 只规定 `palette` 是个 token string。
- [ ] `scope=personal` 是否真的需要协议级表达?或者完全留给客户端 actor-private state?
- [ ] 跨 Realm 引用 label 的场景(用 Realm A 的 label 给 Realm B 的 Flow 贴)需要吗?默认拒绝,但 Linked Realm 场景可能合理。
- [ ] Label `key` create-locked 与 morph_type 同模式,还是允许低 tier rename(并接受 grant selector 失效)?
- [ ] 是否需要 `ck.label.merge` event(把两个 label 合并,自动迁移所有 `labeled_with`)?这是 Trello / GitHub 都有的高频运维操作。

## 7. Migration plan

(accepted 阶段填)

## 8. References

- Trello label UI(用户提供截图,2026-05-23 conversation)
- GitHub Issue labels: <https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels>
- Linear labels: <https://linear.app/docs/labels>
- Asana custom fields(对照 §2 提到的 "fields 而非 label" 的另一种产品形态)
