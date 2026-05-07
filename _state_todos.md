# Move · Anchor · Lattice v1 重构记录

当前 v1 已放弃旧 state slot winner / hub-writer / peer-mesh quarantine 模型。

## 已完成

- `event-auth-state-resolution.md` 重写为 Move、Anchor、Lattice 三原语。
- registry 现在使用 `cell_family` / `cell_subject` / `lattice` / `bottom`。
- 旧单 host wire contract 已移除，Anchorer 由 `anchorer` cell 表达。
- 新增 `move.schema.json`、`anchor.schema.json`、`bottom.schema.json`，并注册 `cx.schema.move.v1` / `cx.schema.anchor.v1` / `cx.schema.bottom.v1`。
- Space schema 改为 `anchor_profile`、`anchorer`、`max_anchor_staleness_ms`、`cell_lattices`、`co_write_policy`。
- state-resolution fixture 已替换为 `move-anchor-lattice-fixture.json`。
- 各核心 Lattice type 在 `event-auth-state-resolution.md` §5.3 补齐 normative `join()` / `validate_op()` 参考实现（or-set / mv-register / cas-register / fsm / counter / ordered-log）。
- Anchor compaction / recovery Anchor / multi-leaf 收敛新增 conformance vectors（`conformance-vectors.md` §2.6-2.8）。
- Bottom diagnostics 在 `contrix-service-api.openapi.yaml` 暴露为 `BottomDiagnostic` / `MoveStateView` / `CellQueryEnvelope` 三个 typed DTO；`client-sync-response.schema.json` 同步补 `move_states[]` / `bottoms[]` 字段，对应 `service-surface.md` §5.5 wire 形态。

## 后续工程化

（无未完成项；v1.1+ 新增工作请加入根 `_todos.md` 表格。）
