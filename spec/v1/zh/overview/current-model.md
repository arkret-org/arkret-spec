---
title: 当前模型说明
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文给出 Contrix v1 的统一对象模型读法，确保实现、文档和交互层对同一套协作语义采用一致解释。

## 2. Flow 是统一协作对象

`Flow` 承载同一事项的正式表达与讨论过程：

- `tracks` 的 key：定义 Flow 当前启用的能力轨道（key 是 track 稳定名）
- `tracks.<name>.is_primary=true`：可显式定义默认主入口；若未显式设置且存在 key `synthesis`，默认主入口派生为 `synthesis`
- `state`（active/archived/redacted）= 物理生命周期；`stage`（draft/proposed/planned/in_progress/blocked/done/cancelled/superseded，必填）= 业务进度。两者正交，分别由 `cx.flow.archive` 家族与 `cx.flow.stage.set` 维护。详见 [`models/common-fields.md` §5.3](../models/common-fields.md)。
- 业务语义通过 Realm schema/profile、`fields`、Relation、labels、Morph type 或 facet 表达

## 3. Flow 的标准 Track

`Flow.tracks` 是 track 定义 map（key 是 track 稳定名）。v1 标准化两个 track name：

- `synthesis`：正式表达、结构化字段、状态推进、标题、摘要、正文
- `discussion`：成员、消息、历史可见性、通知与可选 E2EE

轨道规则：

- `synthesis` 与 `discussion` 都可独立启用或关闭；`tracks` map 只要求至少有一个 active track。「只聊天不归纳」（仅 `discussion`）和「只承载结构化正文不开讨论」（仅 `synthesis`）都是合法形态。
- 关闭 track 用 `tracks.<name>.enabled: set false`（冻结新写入、保留历史），或从 map 中删除 key。primary track 不能空缺：若被关闭的是当前 primary，MUST 在同一 `cx.flow.tracks.update` patch 中把 primary 转给另一个 active track。
- `discussion` 的额外护栏：reducer MUST NOT 隐式创建 `discussion` track——切换 primary 到 `discussion` 时，若该 track 尚未 enabled，必须在同一 patch 中同时写 `tracks.discussion.enabled: set true` + `tracks.discussion.is_primary: set true`。`synthesis` 没有此特殊约束（默认即标准 primary 候选，见 [`models/flow-and-message.md` §4.5](../models/flow-and-message.md)）。
- 任何 track 启用、关停或切换 primary 通过单一 event `cx.flow.tracks.update`（payload 为 `cx.patch.v1` 形态）原子完成，不改变 `flow_id`；详见 [`models/flow-and-message.md` §4.8](../models/flow-and-message.md)。

## 4. 工作流容器

工作流容器是独立的 `Space` 对象（`cx:space:`）。Space 是产品结构节点，不形成自己的 boundary；它的 metadata 写入 `realm_id` 指向的 home Realm，子资源默认落点由 `default_realm_ref` 解析：

- `Board Space`（`kind=board`）
- `List Space`（`kind=list`）
- 未来可扩展：`swimlane` / `calendar_bucket` / `page_group` / …（profile 注册）

Flow 在 `Board Space` / `List Space` 中的位置通过 `contains` relation 与 `cx.flow.move` / `cx.flow.reorder` 维护。Space 之间的层级用 Space 自己的 `parent_ref` + `cx.space.parent` 表达，可跨 Realm 做导航，但不级联 Realm 权限或密钥。

## 5. View 的职责

`View` 只负责查询和渲染：

- 看板/列表使用 `View.kind="collection"`，再通过 renderer 表达 `board` / `list` 视图样式
- View filter / columns / layout 变化写入 `cx.view.update`
- 拖拽 Flow、切换 List、修改 rank 写入真实对象事件：`cx.flow.move` / `cx.flow.reorder` / `cx.space.update`


## 6. 权限与成员边界

Realm membership、Flow 更新权限与 discussion access 使用统一授权模型裁剪：

- `cx.member.state` 控制 Realm membership
- `cx.flow.*` 控制 Flow 自身与工作流位置
- Track 不携带独立 access；整 Flow 共享单一加密 scope（`Flow.scope_ref`：null = Realm-default scope，否则指向同 Realm 的 [Circle](../models/circle.md)）。
- 需要让 Flow 拥有独立 membership / history visibility / E2EE 时，把 `Flow.scope_ref` 指向一个 Circle；`cx.circle.member.state` 控制 Circle 成员状态（`Circle.members ⊆ Realm.members`）。
- Flow 可见性按整 Flow 单一 scope 判定：`scope_ref=null` 按 Realm-default policy；`scope_ref` 指向 Circle 时按该 Circle 自身 history visibility 与 membership 独立判断。
- Flow 可读不代表 Flow synthesis 可写——授权评估始终是 capability ∧ scope membership 两层 AND（详见 [`../models/circle.md` §8](../models/circle.md)）。

## 7. E2EE 边界

MLS 加密绑定到 Realm 或 Realm 内的 Circle:

- 默认（`Flow.scope_ref=null`）：Flow 落在 Realm-default MLS group；该 Realm 全员可解。
- 独立 Flow access：`Flow.scope_ref` 指向某 Circle 时，整个 Flow 落在该 Circle 的独立 MLS group / 独立成员 / 独立 history sharing。Circle key MUST NOT 从 Realm-default key 派生。
- MLS group 的 scope 绑定 `(realm_id, circle_id?)`：`scope=realm` 时承担 Realm-default 加密；`scope=circle` 时承担 Circle 加密。不存在 "track-internal MLS group"。
- 详见 [`../models/circle.md` §10](../models/circle.md)（含 Realm-member-removal 触发的 N+1 rotate amplification 与缓解策略）。

## 8. Agent 结果落点

Agent 的标准落点为：

- `Flow`：长期任务、决策、方案、研究等可持续对象
- `Message`：discussion 中的即时沟通或补充结论
- `Morph` / `Blob`：长报告、代码包、外部 transcript 或二进制成果

推荐做法是先将 agent 结果沉淀到带有明确 Realm schema/profile 或业务 `fields` 的 Flow，再按需要附加 Message / Morph / Blob 引用。

## 9. 统一读法

Contrix v1 的统一读法是：

1. `Realm` 是协作边界，不承担产品导航树职责。
2. `Flow` 是统一协作对象。
3. `synthesis` / `discussion` 是 Flow 的两个标准 track。
4. `Space` 是产品结构与工作流容器；`Board Space` / `List Space` 是其中两种形态。
5. `View` 只做投影，不持有真实对象语义。
