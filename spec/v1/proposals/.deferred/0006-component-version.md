---
cxp: CXP-0006
title: Component & Version classifiers
normative: false
stability: v1
updated: 2026-05-25
status: deferred-to-v1.1
created: 2026-05-23
authors:
  - did:web:cokret.example
---

## 1. Summary

引入两个轻量结构性分类对象:

- `ck:component:` — Realm 内的子分类("Frontend / Backend / Mobile"或"Auth / Billing / Search"),比 Space 更轻量,纯标签 + owner,不形成自己的 boundary 或 navigation tree。
- `ck:version:` — 时间限定的发布窗口("v1.2 release","2026 Q3 GA"),Flow 通过 Relation `targets_version` / `fixed_in_version` 关联。

Flow / Morph 通过 Relation 与它们关联,projection 提供按 component / version 分组的视图。

## 2. Motivation

Jira 截图左栏 "Components" 和 "Versions" 是 first-class 实体而不是 free-form 字符串。Trello / Asana / Linear 都有"label" 但没有这两个;它们专属于 Jira 这类**工程 issue 跟踪**场景。

当前协议:全部塞 `fields.<custom>` 或 labels。问题:

- "Component" 有 owner / lead / description / archived 等元数据,labels 装不下
- "Version" 有 `released_at` / `release_state`(unreleased → released → archived),是有时间窗口的实体
- 跨 Realm dashboard 想问"所有 Realm 内 component=Auth 的 Flow 有多少"需要 first-class 引用

不是所有 Realm 都需要这两个;本提案显式 profile-gated。

## 3. Specification

### 3.1 `ck:component:` 对象

Schema id: `ck.schema.component.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:component` | `ck:component:<uuid>` | Component ID。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm。 |
| `key` | yes | `string` | `^[a-z][a-z0-9_-]{0,63}$`;`(realm_id, key)` 唯一;**create-locked**。 | 机器名。 |
| `name` | yes | `string` | 1..128 chars。 | 显示名。 |
| `description` | no | `string` | ≤512 chars。 | 描述。 |
| `icon` | no | `object` | `{emoji?, blob_ref?}` | 图标。 |
| `color` | no | `object` | 同 [CXP-0001](./0001-label-entity.md) `color`。 | 主题色。 |
| `lead_actor_id` | no | `did` | 必须解析到 active actor。 | 组件负责人 DID。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5。 | 生命周期。 |
| 公共字段 | — | — | created_by / created_at / updated_by / updated_at / state_changed_at | — |

应用关系:`flow --in_component--> component`(many-to-many)。

### 3.2 `ck:version:` 对象

Schema id: `ck.schema.version.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:version` | `ck:version:<uuid>` | Version ID。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm。 |
| `key` | yes | `string` | `^[a-z0-9][a-z0-9._-]{0,63}$`(允许 `1.2.3` 形态;create-locked)。 | 机器名。 |
| `name` | yes | `string` | 1..128 chars。 | 显示名("v1.2 GA","2026 Q3 release")。 |
| `description` | no | `string` | ≤512 chars。 | 描述。 |
| `start_date` | no | `date` | — | 计划启动日。 |
| `release_date` | no | `date` | — | 计划发布日;`released_at` 实际发布时填写。 |
| `released_at` | conditional | `timestamp` | `release_state ∈ {released, archived}` 时必填;**reducer-derived**(由 `ck.version.release` event 写入)。 | 实际发布时刻。 |
| `release_state` | yes | `enum(unreleased, released, archived)` | 转换:unreleased → released(`ck.version.release`)→ archived(`ck.version.archive`);archived 不可逆(用 tombstone 完全清除)。 | 发布状态机。**与对象 `state`(active/archived/tombstoned)正交**:对象 state 是物理生命周期,release_state 是发布周期。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5。 | 物理生命周期。 |
| 公共字段 | — | — | created_by / created_at / updated_by / updated_at / state_changed_at | — |

应用关系:
- `flow --targets_version--> version`("这个 Flow 计划在该 version 落地")
- `flow --fixed_in_version--> version`("这个 bug 实际在该 version 修复")

### 3.3 Event 家族

#### Component

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `ck.component.create` | yes | 创建 |
| `ck.component.update` | yes | patch(不改 key) |
| `ck.component.archive` | yes | active → archived |
| `ck.component.restore` | yes | archived → active |
| `ck.component.tombstone` | yes | terminal |

#### Version

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `ck.version.create` | yes | 创建,默认 release_state=unreleased |
| `ck.version.update` | yes | patch 元数据(不改 key、release_state、released_at) |
| `ck.version.release` | yes | unreleased → released;reducer 写入 `released_at = event.created_at` |
| `ck.version.archive` | yes | released → archived(release_state);object state 不变 |
| `ck.version.tombstone` | yes | object state terminal,不可逆 |

注:**release_state 与 object state 是两个独立 axis**(与 stage / state 正交的同模式)。release_state 是 component-spec scope 的"对外发布周期",state 是协议物理生命周期。

### 3.4 Capability

| action | risk_tier | target event kinds |
| --- | --- | --- |
| `ck.component.manage` | medium | component.* |
| `ck.version.manage` | medium | version.create / update / archive / tombstone |
| `ck.version.release` | medium | `ck.version.release`(独立切分,因为发布是一次性高影响动作) |
| `ck.flow.classify` | low | `ck.relation.create / delete` 限 `relation_kind ∈ {in_component, targets_version, fixed_in_version}` |

## 4. Interactions with normative spec

- 新增文件:`spec/v1/zh/models/component-and-version.md`。
- 新增 schema:`component.schema.json`、`version.schema.json`。
- 新增 id-kind:`component`、`version`。
- 新增 event_kinds(component 5 + version 5 = 10 条)+ capability actions(4 条)。
- 新增 Relation kinds:`in_component`、`targets_version`、`fixed_in_version`。
- 新增 profile:`ck.profile.engineering_classifiers.v1`(打包 component + version,因为典型用例是工程 issue tracking)。

## 5. Rationale & alternatives

### 5.1 为什么不用 Label?

- Label 是平的 tag,没有 owner / release date / 状态机
- 同一对象贴多个 component / version 关系语义不同(version 有 targets vs fixed_in 之分,label 只有"贴上"一种)
- 跨 Realm dashboard 需要 typed reference,纯字符串 label 不够

### 5.2 为什么 Component 不是 Space 的一种 kind?

- Space 形成 navigation tree / boundary 派生 / `default_realm_id` 等结构语义
- Component 是纯分类标签,贴上去就完事,不应承担容器语义
- 一个 Flow 可以在多个 component(many-to-many),Space 是 1:N 的位置语义

### 5.3 为什么 Version 不是 Realm 的子对象?

候选 A:Realm 上嵌入 `versions: array`。

否决理由:同 label / component:audit / capability / lifecycle 都缺。

### 5.4 为什么 release_state 与 object state 是两个 axis?

与 CXP-0004 之前讨论过的 stage / state 正交是同一原则。released 的 version 仍可被对象 archive(物理停用),archived 物理 state 的 version 也可保留 released_at(历史记录)。两个 axis 不可坍缩。

## 6. Open questions

- [ ] Component 是否需要 hierarchy(`parent_space_id`)?Jira 允许 nested components。建议 v1 不嵌套,保持平铺。
- [ ] Version 是否需要 dependencies(`blocks_release_of`)?engineering team 常用。建议作为 Relation 而非内嵌字段。
- [ ] release_state archived 是否需要 unarchive?(发布的 version 已是事实,反向只能用 tombstone)
- [ ] 跨 Realm dashboard 引用 component / version:同 Realm 限制,还是允许 organization-level shared?postpone。
- [ ] Bug 模板 + component / version 的联动:`ck:flow_type:` 是否声明默认 component / version?这把 CXP-0002 / CXP-0003 / CXP-0006 都耦合起来,留给 form_layout 表达 picker default,不在 schema 层面强联动。

## 7. Migration plan

(accepted 阶段填)

## 8. References

- Jira Components: <https://support.atlassian.com/jira-software-cloud/docs/configure-jira-components/>
- Jira Versions: <https://support.atlassian.com/jira-cloud-administration/docs/manage-versions/>
- 用户提供 Jira "Components" / "Versions" 左栏截图,2026-05-23
- CXP-0001 Label(对照:component / version vs label 的差异)
