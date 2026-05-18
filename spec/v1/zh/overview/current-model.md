---
title: 当前模型说明
---

## 1. 目标

本文给出 Contrix v1 的统一对象模型读法，确保实现、文档和交互层对同一套协作语义采用一致解释。

## 2. Flow 是统一协作对象

`Flow` 承载同一事项的正式表达与讨论过程：

- `tracks` 的 key：定义 Flow 当前启用的能力轨道（key 是 track 稳定名）
- `tracks.<name>.is_primary=true`：可显式定义默认主入口；若未显式设置且存在 key `synthesis`，默认主入口派生为 `synthesis`
- 业务语义通过 Space schema/profile、`fields`、Relation、labels、Morph type 或 facet 表达

## 3. Flow 的标准 Track

`Flow.tracks` 是 track 定义 map（key 是 track 稳定名）。v1 标准化两个 track name：

- `synthesis`：正式表达、结构化字段、状态推进、标题、摘要、正文
- `discussion`：成员、消息、历史可见性、通知与可选 E2EE

轨道规则：

- `discussion` 可独立启用或关闭
- `cx.flow.track.set_primary` 切换显式 primary track，不改变 `flow_id`
- `cx.flow.track.enable`、`cx.flow.track.disable`、`cx.flow.track.set_primary` 管理 track 生命周期与默认入口（legacy 单点 event；v1 仍 active）
- 新统一 event `cx.flow.tracks.update` 可在一条事件内原子地修改 tracks map（`cx.patch.v1` payload），覆盖上面 4 个 legacy event 的写入面；新客户端 SHOULD 优先使用统一 event，详见 [`models/flow-and-message.md` §4.8](../models/flow-and-message.md)。

## 4. 工作流容器

工作流容器是独立的 `Place` 对象（`cx:place:`），住在 Space 内但不形成自己的 boundary：

- `Board Place`（`kind=board`）
- `List Place`（`kind=list`）
- 未来可扩展：`swimlane` / `calendar_bucket` / `page_group` / …（profile 注册）

Flow 在 `Board Place` / `List Place` 中的位置通过 `contains` relation 与 `cx.flow.move` / `cx.flow.reorder` 维护。Place 之间的层级用 Place 自己的 `parent_ref` + `cx.place.parent` 表达。

## 5. View 的职责

`View` 只负责查询和渲染：

- 看板/列表使用 `View.kind="collection"`，再通过 renderer 表达 `board` / `list` 视图样式
- View filter / columns / layout 变化写入 `cx.view.update`
- 拖拽 Flow、切换 List、修改 rank 写入真实对象事件：`cx.flow.move` / `cx.flow.reorder` / `cx.place.update`


## 6. 权限与成员边界

Space membership、Flow 更新权限与 discussion access 使用统一授权模型裁剪：

- `cx.member.state` 控制 Space membership
- `cx.flow.*` 控制 Flow 自身与工作流位置
- Track 不携带独立 access；discussion 时间线默认完全继承父 Space。
- 需要让 discussion 拥有独立 membership / history visibility / E2EE 时，必须创建 child Space 并通过 `Flow.discussion_space_ref` 引用；child Space 上的 `cx.member.state` 控制 discussion 成员状态。
- Flow synthesis 可见性 ≠ discussion 可见性：未设置 `discussion_space_ref` 时按父 Space history visibility 判断；设置时按 child Space policy 独立判断。
- discussion 可读不代表 Flow synthesis 可写。

## 7. E2EE 边界

MLS 加密绑定到 Space：

- 默认（未设 `discussion_space_ref`）：整个父 Space 共用一个加密边界，Flow synthesis 与 discussion 共享同一 MLS group。
- 独立 discussion access：父 Space 与 `discussion_space_ref` child Space 是两个独立 Space，各自拥有独立 MLS group、独立成员、独立 history sharing。
- 不存在 "track-internal MLS group"：MLS group 的 scope 永远绑定到某个具体 `space_id`。

## 8. Agent 结果落点

Agent 的标准落点为：

- `Flow`：长期任务、决策、方案、研究等可持续对象
- `Message`：discussion 中的即时沟通或补充结论
- `Morph` / `Blob`：长报告、代码包、外部 transcript 或二进制成果

推荐做法是先将 agent 结果沉淀到带有明确 Space schema/profile 或业务 `fields` 的 Flow，再按需要附加 Message / Morph / Blob 引用。

## 9. 统一读法

Contrix v1 的统一读法是：

1. `Space` 是协作边界。
2. `Flow` 是统一协作对象。
3. `synthesis` / `discussion` 是 Flow 的两个标准 track。
4. `Board Place` / `List Place` 是工作流形态。
5. `View` 只做投影，不持有真实对象语义。
