# View Support Review

本目录是本轮 View 协议产品化审查的临时工作区。

当前 `artifacts/schemas/view.schema.json` 顶层支持 22 种 `View.kind`：

```text
kanban, list, table, calendar, gantt, chat, thread, forum, tree, graph,
timeline, review_queue, matrix, document, dashboard, activity, inbox,
notifications, memory_review, agent_runs, context_timeline, moderation_queue
```

分组：

| Profile | View kinds |
| --- | --- |
| board | `kanban` |
| row | `list`, `table`, `calendar`, `gantt`, `matrix`, `document`, `dashboard`, `review_queue`, `memory_review`, `agent_runs`, `moderation_queue`, `inbox`, `notifications` |
| timeline | `timeline`, `activity`, `context_timeline`, `chat`, `thread`, `forum` |
| graph | `graph`, `tree` |

文件：

- `view_requirements.md`：每种 View 的系统实现难点和产品级完善要求。
- `todos.md`：对照当前协议后的缺口、修复项和本轮完成状态。

