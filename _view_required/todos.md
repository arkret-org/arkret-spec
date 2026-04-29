# View Protocol TODOs

## 已发现缺口

- [x] 旧设计把 22 个产品形态都放进顶层 `View.kind`，导致 schema、OpenAPI、conformance 和实现面过宽。
- [x] Kanban card 被隐含建模成特殊卡片对象，抽象度不足；thread/message/run/memory 作为 card 显示需要靠自然语言解释。
- [x] `/index/query.projection` 暴露所有产品形态，导致 response `oneOf` 和 cursor 语义膨胀。
- [x] Row/Kanban/Queue/Calendar/Gantt/Matrix 本质都是集合投影，但此前分散到多个配置 profile。
- [x] `dashboard` 被当作 row-like projection，不足以表达 widget 局部 frontier 和局部错误。
- [x] `document` 被当作 row-like projection，不足以表达 section/body/redaction contract。
- [x] conformance fixture 曾把 Kanban 当成独立 projection，没有证明 kanban 是 collection preset。
- [x] zh/en schema、OpenAPI、fixtures 容易漂移，需要保持镜像一致。

## 本轮修复范围

- [x] 将 canonical `View.kind` 收敛到 `collection`、`timeline`、`graph`、`document`、`composite`。
- [x] 增加 `preset` registry，并用 schema 约束 preset 到核心 kind 的映射。
- [x] 增加通用 `collection` config，覆盖 card/row/tile/message render、field/relation/time/matrix grouping、count/WIP/conflict policy。
- [x] 将 OpenAPI `QueryRequest.projection` 收敛到 `raw` + 5 个核心投影原语，并增加 `preset`。
- [x] 增加 `CollectionProjectionResponse`，把 Kanban/Row 类响应降级为兼容 legacy schema。
- [x] 增加 `DocumentProjectionResponse` 与 `CompositeProjectionResponse`。
- [x] 将 Kanban sync fixture 改为 `projection="collection", preset="kanban"`。

## 后续产品化守门

- [ ] 新增产品形态时优先新增 preset，不得新增顶层 `View.kind`，除非证明 5 个原语无法表达其 reducer/cursor/authz contract。
- [ ] 实现者 MUST 在 feature discovery 中声明支持的 core projection 与 preset，而不是声明大量互不兼容的 endpoint。
- [ ] UI layout hint 不得绕过 `collection` / `timeline` / `graph` / `document` / `composite` 的机器 contract。
