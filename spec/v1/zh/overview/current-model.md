---
title: 当前模型说明
status: candidate
normative: false
stability: v1
updated: 2026-07-13
---

## 0. 文档定位

本文是当前对象模型的非规范导览；所有约束均以所链接的对象专属文件为准。

## 1. 目标

本文给出 Arkret v1 的统一对象模型读法，确保实现、文档和交互层对同一套协作语义采用一致解释。

### 1.1 从常见产品概念理解 Arkret

Arkret 不是把某个产品的对象名搬进协议，而是把常见协作产品拆成更稳定的协议边界：

| 产品 / 场景概念 | Arkret 中的落点 | 避免误读为 |
| --- | --- | --- |
| 聊天群、即时通讯群组、频道 | `Realm` 提供成员与历史边界；一个或多个 `Strand(tracks.discussion)` 承载对话 | `Message` 本身不是房间；`discussion` track 也不是独立 ACL。 |
| 房间式协作场景 | 通常拆为 `Realm`（状态、成员与历史边界）+ `Strand/Message`（协作主题与消息）+ `View`（时间线 / 话题投影） | v1 core 不使用通用 `Room` 对象根。 |
| Trello Board / List / Card | `Space(kind=board)` / `Space(kind=list)` / `Strand`，位置由 `ak.strand.move` 与派生 `contains` Relation 表达 | View renderer 不是对象真相；拖拽不能只改 View。 |
| Jira issue / workflow status / issue links | `Strand` / `stage` + workflow profile / `Relation(depends_on, blocks, assigned_to, references...)` | Jira-style workflow status 不等于 `state`；`metadata.fields.status` 也不是互操作真相。 |
| Watchers、订阅、勿扰 | `ak.strand.watch.set` cell + actor-private push rules / DND | Watch 不是访问权；静音不改变别人是否能读对象。 |
| 小程序 / Bot / 集成服务 | Applet、Agent、Ghost Actor、Morph / Relation 扩展 | 安装一个客户端或插件不等于创建 protocol principal。 |
| 用户与自己 AI Agents 的 Realm-context 私密工作区 | 独立 `Agent Sidecar` 对象与 native Sidecar scope；desired roster 由 controller 与其 active owned Agents 中当前 Realm active members 派生，独立 MLS 直接绑定 Sidecar | Sidecar 不是普通 Circle、Circle profile、Direct Conversation 或第四个 Track。 |

## 2. Strand 是统一协作对象

`Strand` 承载同一事项的正式表达与讨论过程：

- `tracks` 的 key：定义 Strand 当前启用的能力轨道（key 是 track 稳定名）
- `tracks.<name>.is_primary=true`：可显式定义默认主入口；若未显式设置且存在 key `synthesis`，默认主入口派生为 `synthesis`
- `state`（active/archived/redacted）= 物理生命周期；`stage`（draft/proposed/planned/in_progress/blocked/done/cancelled/superseded，可选）= 业务进度。两者正交，分别由 `ak.strand.archive` 家族与 `ak.strand.stage.set` 维护。详见 [`models/common-fields.md` §5.3](../models/common-fields.md)。
- 业务语义通过 Realm schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 表达

Jira / Trello 一类产品里的细粒度 workflow status（例如 QA、Review、Ready for release）不是新的协议字段。跨实现互操作在 Strand 携带 `stage` 时只依赖 8 个粗粒度值；细粒度状态应由 Realm workflow profile、`metadata.fields` 或 Morph schema 声明，并在需要跨 Realm dashboard 聚合时映射回 `stage`。

## 3. Strand 的标准 Track

`Strand.tracks` 是 track 定义 map（key 是 track 稳定名）。v1 标准化两个 track name：

- `synthesis`：正式表达、结构化字段、状态推进、标题、摘要、正文
- `discussion`：消息时间线、通知入口与讨论 UI；成员、历史可见性和 E2EE 由整个 Strand 的 effective scope 决定，不由 track 自己持有

这两个名称同时是当前
[`track-name-registry.json`](../../artifacts/registry/track-name-registry.json) 的完整 active
集合；正则只约束登记语法，未登记名称不能进入 `Strand.tracks`。

Track 可独立启用或关闭，也可原子切换 primary；「只聊天不归纳」和「只承载结构化正文不开讨论」都是合法模型形态。完整的 active/primary 不变量、`discussion` 启用护栏与 `ak.strand.tracks.update` patch 规则只由 [`models/strand-and-message.md` §4.5–§4.8](../models/strand-and-message.md) 规范定义，本导览不重复承载。

## 4. 工作流容器

容器选型的 normative 判定顺序以 [`architecture.md` §2.0](./architecture.md) 为准；本节只说明当前模型读法。

工作流容器是独立的 `Space` 对象（`ak:space:`）。Space 是产品结构节点，不形成自己的 boundary；它的 metadata 写入 `realm_id` 指向的 home Realm，子资源默认落点由 `default_realm_id` 解析：

- `Board Space`（`kind=board`）
- `List Space`（`kind=list`）
- 未来可扩展：`swimlane` / `calendar_bucket` / `page_group` / …（profile 注册）

Strand 在 `Board Space` / `List Space` 中的位置通过 `contains` relation 与 `ak.strand.move` / `ak.strand.reorder` 维护。Space 之间的层级用 Space 自己的 `parent_space_id` + `ak.space.parent` 表达，可跨 Realm 做导航，但不级联 Realm 权限或密钥。

## 5. View 的职责

`View` 只负责查询和渲染：

- 看板/列表使用 `View.kind="collection"`，再通过 renderer 表达 `board` / `list` 视图样式
- View filter / columns / layout 变化写入 `ak.view.update`
- 拖拽 Strand、切换 List、修改 rank 写入真实对象事件：`ak.strand.move` / `ak.strand.reorder` / `ak.space.update`

## 6. 权限与成员边界

Realm membership、Strand 更新权限与 discussion timeline 可见性使用统一授权模型裁剪：

- `ak.member.state` 控制 Realm membership
- `ak.strand.*` 控制 Strand 自身与工作流位置
- Track 不携带独立 access；整 Strand 共享单一 effective scope（`Strand.scope_circle_id`：null = Realm-default scope，否则指向同 Realm 的 [Circle](../models/circle.md)）。
- 需要让 Strand 拥有独立 membership / history visibility / 投递裁剪或 E2EE 时，把 `Strand.scope_circle_id` 指向一个 Circle；`ak.circle.member.state` 控制 Circle 成员状态（`Circle.members ⊆ Realm.members`）。
- Strand 可见性按整 Strand 单一 scope 判定：`scope_circle_id=null` 按 Realm-default policy；`scope_circle_id` 指向 Circle 时按该 Circle 自身 history visibility 与 membership 独立判断。
- Strand 可读不代表 Strand synthesis 可写——授权评估始终是 capability ∧ scope membership 两层 AND（详见 [`../models/circle.md` §8](../models/circle.md)）。

## 7. E2EE 边界

MLS 加密可绑定到 Realm 或 Realm 内的 MLS-backed Circle:

- 默认（`Strand.scope_circle_id=null`）：Strand 落在 Realm-default scope；若 Realm 为 MLS-backed，则该 Realm-default MLS group 覆盖此 Strand。
- 独立 Strand access：`Strand.scope_circle_id` 指向某 Circle 时，整个 Strand 落在该 Circle 的独立成员 / 独立 history sharing / 投递裁剪；若 Circle 为 `mls_rfc9420`，则使用该 Circle 的独立 MLS group。密钥派生禁令见 [`../models/circle.md` §10](../models/circle.md)。
- MLS group 的 scope 绑定 `(realm_id, circle_id?)`：`scope=realm` 时承担 Realm-default 加密；`scope=circle` 时承担 MLS-backed Circle 加密。不存在 "track-internal MLS group"。
- 详见 [`../models/circle.md` §10](../models/circle.md)（含 Realm-member-removal 触发的 MLS rotate amplification 与缓解策略）。

## 8. Agent 结果落点

Agent 的标准落点为：

- `Strand`：长期任务、决策、方案、研究等可持续对象
- `Message`：discussion 中的即时沟通或补充结论
- `Morph` / `Blob`：长报告、代码包、外部 transcript 或二进制成果

推荐做法是先将 agent 结果沉淀到带有明确 Realm schema/profile 或业务 `metadata.fields` 的 Strand，再按需要附加 Message / Morph / Blob 引用。

## 9. 统一读法

Arkret v1 的统一读法是：

1. `Realm` 是协作边界，不承担产品导航树职责。
2. `Strand` 是统一协作对象。
3. `synthesis` / `discussion` 是 Strand 的两个标准 track。
4. `Space` 是产品结构与工作流容器；`Board Space` / `List Space` 是其中两种形态。
5. `View` 只做投影，不持有真实对象语义。

## 10. 常见功能落点

下列能力在同类产品中常见，但 v1 core 不都固化为新的顶层对象；实现应按互操作强度选择落点：

| 功能 | 推荐落点 | 说明 |
| --- | --- | --- |
| Checklist / subtask | 需要独立负责人、截止时间、评论或审计时用子 `Strand` + `Relation(contains / depends_on / blocks)`；仅作为正文清单时用 content / profile-defined Morph | 不新增通用 `ChecklistItem` core 对象，避免与 Strand/Morph 重叠。 |
| 自定义字段 | `fields` + Realm schema/profile | 字段名、类型、必填性与迁移由 schema 声明；facet 只做 UI hint。 |
| 自动化 / Butler / Jira automation | Applet / Agent / policy-bound automation profile | 自动化触发的共享变化以 signed Event 落地，而不是只写投影缓存。 |
| Saved filter / personal board view | 共享视图用 `View`；个人列宽、折叠、临时 filter 用 actor-private account data | View 是共享投影定义；个人偏好不进入 Realm 共享历史。 |
| Watchers / assignment / mention | `ak.strand.watch.set`、`Relation(assigned_to)`、结构化 mention node | 访问权先由 Realm/Circle scope 判断，再叠加通知偏好。 |
