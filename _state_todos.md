# Move · Anchor · Lattice v1 重构记录

当前 v1 已放弃旧 state slot winner / hub-writer / peer-mesh quarantine 模型。

## 已完成

- `event-auth-state-resolution.md` 重写为 Move、Anchor、Lattice 三原语。
- registry 现在使用 `cell_family` / `cell_subject` / `lattice` / `bottom`。
- 旧单 host wire contract 已移除，Anchorer 由 `anchorer` cell 表达。
- 新增 `move.schema.json`、`anchor.schema.json`，并注册 `cx.schema.move.v1` / `cx.schema.anchor.v1`。
- Space schema 改为 `anchor_profile`、`anchorer`、`max_anchor_staleness_ms`、`cell_lattices`、`co_write_policy`。
- state-resolution fixture 已替换为 `move-anchor-lattice-fixture.json`。

## 后续工程化

- 为每个核心 Lattice type 补参考实现。
- 为 Anchor compaction / recovery Anchor 补更多 conformance vectors。
- 为 API 层 bottom diagnostics 增加 OpenAPI DTO。
