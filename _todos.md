# 续作：上一轮 deferred 项 + 高价值 BLOCKING

上一轮的 _todos.md 列出 A1–A10、B1–B5、C1–C2 全部完成；遗留 4 项延后到本轮，外加 _report.md 中 2 个易清的 BLOCKING。

## D. 延后项

| # | 任务 | 文件 |
| --- | --- | --- |
| D1 | `auth_weight` 11 档刻度重构为 (governance_layer, authority_kind) lattice。表改为 lattice，排序键由 lattice 偏序定义；scalar 仍可作派生字段。 | [event-auth-state-resolution.md §9.3.2](zh/authz/event-auth-state-resolution.md) |
| D2 | 补 state-resolution conformance vector：`same_layer_direct_vs_delegated`、`cross_layer_governance_vs_space_admin`（self_vs_admin 与 grant_revoke_race 已在现 fixture 中覆盖） | [state-resolution-fixture.json](zh/conformance/fixtures/state-resolution-fixture.json) + 镜像 |
| D3 | 拆 core / extension constraint set。`cx.profile.core_event_store.v1` 只 require core；扩展 type 由 profile gate。 | [constraint-schema.md §2.2](zh/authz/constraint-schema.md) + [conformance-profiles.json](artifacts/profiles/conformance-profiles.json) |

## E. 易清 BLOCKING（从 _report.md）

| # | 任务 | 来源 |
| --- | --- | --- |
| E1 | `default_join_rule` 不允许 `private`（不在 enum 内的死代码 defensive reject） | _report.md B-15 |
| E2 | `conformance-profiles.md` 中 "Flow（含 `card` / `room` kind）" 死语，Flow 当前已无 `kind` 字段 | _report.md B-20 |

## F. 不在本轮的范围

- _report.md 中其余 BLOCKING（B-02、B-03、B-04、B-06、B-07、B-08、B-09、B-10、B-11、B-12、B-14、B-16、B-17、B-18、B-19、B-21、B-22、B-23）—— 多数需要更深的 schema / openapi / 跨文件重构，单独立项
- reference validator / reducer / authz evaluator 实现 —— 离开本规范仓库
