# View Protocol TODOs

## 已发现缺口

- [x] 顶层支持的 View kind 没有统一列出，且中文数据结构文档缺 `moderation_queue`。
- [x] 除 `kanban` 外，其他 View kind 没有机器可验证的 typed config。
- [x] `/index/query` 的 `projection` 只支持 `raw` 和 `kanban`，与顶层 View kind 不一致。
- [x] 非 Kanban 投影没有标准 response profile；graph/tree/timeline/chat/list/table 等只能退回 generic object。
- [x] 图/树视图缺少 node/edge/lazy link/truncation 的响应 contract。
- [x] 时间线/聊天/活动类视图缺少 entry sort_key、redaction/tombstone 和 cursor contract。
- [x] row/queue/table/calendar/gantt 等缺少 item/entity/frontier/count 的响应 contract。
- [x] `View.query` 允许空 query；graph/tree、conversation、context_timeline 缺少最低 anchor/relation 约束。
- [x] conformance fixture 只有 Kanban 专项，缺少 row/timeline/graph 三类基础投影覆盖。
- [x] zh/en schema、OpenAPI、fixtures 容易漂移，需要本轮继续保持镜像一致。

## 本轮修复范围

- [x] 在 View schema 中加入 `tabular`、`time_window`、`timeline`、`conversation`、`graph`、`queue`、`matrix`、`document`、`dashboard` typed configs。
- [x] 为每个非 Kanban View kind 建立 required config 条件。
- [x] 扩展 OpenAPI `QueryRequest.projection` 到所有 View kind。
- [x] 增加 `RowProjectionResponse`、`TimelineProjectionResponse`、`GraphProjectionResponse`，并接入 `/index/query` response `oneOf`。
- [x] 增加 row/timeline/graph projection fixtures。
- [x] 更新中英文 View 文档、HTTP binding、data structures。
