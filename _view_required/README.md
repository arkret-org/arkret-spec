# View Support Review

本目录是本轮 View 协议产品化审查的临时工作区。

结论：不应把 `kanban`、`thread`、`table`、`chat` 等产品形态都提升为协议核心类型；也不应让 View 原语承担对象职责。协议核心应先定义 Entity 的可组合 `facets`，View 只是对 facet/relation graph 的查询与渲染。

当前标准 Entity facets：

```text
container, replyable, schedulable, assignable, stateful,
rankable, reviewable, notifiable, documentable, renderable
```

当前 View response family 仍保留以下机器返回形态，但它们不定义对象能力：

```text
collection, timeline, graph, document, composite
```

产品 preset 由 facet composition 派生：

| Preset | Required / typical facets |
| --- | --- |
| `kanban` | card items are usually `stateful` + `rankable`; relation-backed boards use container entities with `container`. |
| `thread` / `chat` / `forum` | anchors use `replyable`; messages are renderable timeline entries. |
| `calendar` / `gantt` | items use `schedulable`; dependencies are relation edges. |
| `review_queue` / `moderation_queue` | items use `reviewable` plus optional `assignable` / `stateful`. |
| `document` | root uses `documentable`; sections are contained/renderable entities. |
| `dashboard` | composite view over other facet queries. |

设计含义：

- Kanban card 是满足某组 facets 的 Entity 使用 `card` renderer 的结果，不是独立协议对象。
- Thread/chat/message/task/run/memory 都可以作为 `collection.items[*].entity` 或 `timeline.entries[*].entity` 投影，关键取决于 facets 与 relation。
- `entity_type` 只提供语义标签；facet 才声明字段组、允许关系、标准操作与投影能力。
- preset 只约束 facet composition 和 UI 语义，不新增真相源。

文件：

- `view_requirements.md`：每个核心原语的系统难点和产品级完善要求。
- `todos.md`：对照当前协议后的缺口、修复项和完成状态。
