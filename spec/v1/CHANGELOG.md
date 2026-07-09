# Arkret v1 协议变更登记（CHANGELOG）

> 本文件是「机器可发现的协议演化记录」的人类可读一面。它与
> `artifacts/migration/{renames,removed-event-kinds,removed-operation-ids,deprecated-profile-ids}.json`
> 及 `artifacts/registry/{forbidden-model-terms,forbidden-wire-fields}.json` 互为两面：被
> `hard_reject` / `migration_only` / `compat_only` / `docs_only` 标记或在 `allowed_contexts`
> 中含 `changelog` 的标识符，在本文件中留存为可追溯条目。
>
> 规范效力以各 migration / registry artifact 与 conformance 文档为准；本文件只承载登记与导航，不新增独立 wire 约束。
> 计数与漂移以 `python tools/artifact_pipeline.py check` 与 `tools/lint_artifacts.py` 的输出为权威。

## 登记模板

### Extension profile 变更登记模板

每次新增或退役 registry 项（event kind / operation id / profile id / schema id / wire field 等）时，按下表补一条：

| 字段 | 说明 |
| --- | --- |
| `date` | 变更登记日期（`YYYY-MM-DD`）。 |
| `change_kind` | `added` / `removed` / `renamed` / `deprecated`。 |
| `identifier` | 受影响的 canonical 标识符（如 `ck.profile.*.v1`、`ck.<event>.v1`、`operation_id`）。 |
| `replacement` | 若为 rename / removal，指向替代标识符；否则留空。 |
| `migration_artifact` | 承载该条的机读 artifact 路径（如 `artifacts/migration/renames.json`）。 |
| `rejection_level` | 与 migration artifact 一致（`hard_reject` / `migration_only` / `compat_only` / `docs_only`）。 |
| `notes` | 设计决策与 migration group 关联说明。 |

## 条目

（v1 窗口内尚无独立于 migration artifact 的额外登记条目；已发生的 rename / removal 以对应
`artifacts/migration/*.json` 与 `artifacts/registry/forbidden-*.json` 为权威记录面。）
