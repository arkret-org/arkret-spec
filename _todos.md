# contrix-spec Active TODO

更新时间: 2026-05-03

`contrix-spec` 是所有仓库的规范源。当前的首要任务不是继续扩章节，而是把 2026-05-03 的 `subject/room/card -> flow` 收敛彻底落到 artifact、fixture、OpenAPI、CI 和迁移指南，给下游仓库一个不会反复摇摆的 source of truth。

## 执行顺序

- [ ] Block A: 先冻结 active wire contract、legacy compatibility policy、forbidden pattern。
- [ ] Block B: 再同步 schema、registry、profile、fixture、OpenAPI、镜像文档。
- [ ] Block C: 最后输出跨仓库迁移说明和实现验收基线。

## 可并行 Lane

- [ ] Lane 1: `zh/` 规范文本。
- [ ] Lane 2: `artifacts/registry` / `schemas` / `profiles`。
- [ ] Lane 3: `fixtures` / negative vectors / conformance docs。
- [ ] Lane 4: `openapi` / service operation registry / mirror sync。
- [ ] Lane 5: `tools/artifact_pipeline.py` / CI drift guard。

## P0: Active Wire Contract Freeze

- [ ] 所有规范入口明确声明 active v1 wire contract 只保留 `flow`，不再保留 `subject` / `room` / `card` typed ID、schema ID、event kind。
- [ ] `legacy-compatibility-policy.json` 成为唯一 machine-readable 迁移源，供 CI、validator、importer 直接使用。
- [ ] forbidden pattern 扫描规则进入 pipeline，防止旧 contract 在文档、fixture、OpenAPI、示例中回流。
- [ ] 对无 direct alias 的 `link_surface` / `link_room` 类旧语义给出明确的 branch / projection 替代边界。

## P0: Artifact and Profile Sync

- [ ] `id-kind-registry.json`、`event-kind-registry.json`、schema registry、service operation registry 与中文规范逐项对齐。
- [ ] `conformance-profiles.json` 把 `chat_mvp`、`kanban_mvp`、`core_event_store` 的 required kinds / schemas / fixtures 全部对齐新 contract。
- [ ] OpenAPI、fixture、example payload、negative vector、mirror copy 不再引用 removed legacy 文件和字段。
- [ ] `zh/` 与 `artifacts/` 的 drift check 继续 fail closed。

## P0: Migration and Implementation Handoff

- [ ] 发布一次性历史导入规则:
- [ ] typed ID rewrite。
- [ ] schema rewrite。
- [ ] event kind rewrite。
- [ ] branch / projection 语义替换。
- [ ] 给 `contrix-rust-sdk`、`soland`、`yougen` 提供最小迁移清单和 blocker 顺序。
- [ ] 给 `cotest` 提供黑盒验证应拒绝的 legacy contract 集合。

## P1: Tooling and CI

- [ ] `tools/artifact_pipeline.py generate/sync/check` 直接输出 forbidden pattern、profile summary、registry diff。
- [ ] `.github/workflows/artifact-lint.yml` 在 mirror drift、legacy 回流、schema 漂移时 fail closed。
- [ ] 生成面向实现方的简明 compatibility matrix，避免每个仓库重复人工摘录。

## Definition of Done

- [ ] 下游仓库可以只依赖 `zh/` + `artifacts/` 就准确实现当前 active contract。
- [ ] CI 能自动阻止 removed legacy contract 重新进入规范源。
- [ ] `contrix-rust-sdk`、`soland`、`yougen` 的迁移不再依赖口头约定或人工解释。
