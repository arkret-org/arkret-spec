# View Support Review

本目录是本轮 View 协议产品化审查的临时工作区。

结论：不应把 `kanban`、`thread`、`table`、`chat` 等产品形态都提升为协议核心类型。协议核心只保留少数可验证的投影原语，产品形态通过 `preset` 表达。

当前核心 `View.kind`：

```text
collection, timeline, graph, document, composite
```

产品 preset 映射：

| Core kind | Presets |
| --- | --- |
| `collection` | `kanban`, `list`, `table`, `calendar`, `gantt`, `review_queue`, `matrix`, `inbox`, `notifications`, `memory_review`, `agent_runs`, `moderation_queue` |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `activity`, `context_timeline` |
| `graph` | `graph`, `tree` |
| `document` | `document` |
| `composite` | `dashboard` |

设计含义：

- Kanban card 是 `collection` item 的一种 card render surface，不是独立协议对象。
- Thread/chat/message/task/run/memory 都可以作为 `collection.items[*].entity` 或 `timeline.entries[*].entity` 投影。
- 顶层 reducer、cursor、authz、schema 和 OpenAPI 只需要支持 5 类原语。
- preset 只约束配置模板和 UI 语义，不新增真相源。

文件：

- `view_requirements.md`：每个核心原语的系统难点和产品级完善要求。
- `todos.md`：对照当前协议后的缺口、修复项和完成状态。
